"""Tests for Capital Components calculator.

Tests CET1, AT1, Tier 2 capital calculations, regulatory deductions,
and threshold deductions per 12 CFR 217.20-22.

References:
- 12 CFR 217.20-22: Capital components and deductions
- ERBA NPR pp. 34-92: Regulatory capital framework
"""

import pytest

from src.capital.capital_components import (
    AT1Instrument,
    AT1Result,
    CET1Result,
    CapitalTier,
    CommonEquityInputs,
    DeductionCategory,
    DeductionItem,
    InstrumentType,
    ThresholdDeductionInputs,
    Tier2Instrument,
    Tier2Result,
    TotalCapitalResult,
    compute_at1,
    compute_cet1,
    compute_threshold_deductions,
    compute_tier2_amortization,
)
from src.capital.capital_params import (
    DTA_AGGREGATE_THRESHOLD,
    DTA_THRESHOLD_PERCENT,
    MSA_RISK_WEIGHT,
    TIER2_ALLOWANCE_CAP_SA,
)


# =========================================================================
#  Fixtures — realistic Category I G-SIB data ($3.2T institution)
# =========================================================================

@pytest.fixture
def large_gsib_equity_inputs() -> CommonEquityInputs:
    """Equity inputs for a ~$200B CET1 G-SIB (pre-deductions)."""
    return CommonEquityInputs(
        common_stock=25_000.0,       # $25B par
        surplus=85_000.0,            # $85B additional paid-in
        retained_earnings=95_000.0,  # $95B retained
        aoci=-3_000.0,               # -$3B unrealized losses
        treasury_stock=5_000.0,      # $5B treasury
        minority_interest_cet1=1_000.0,  # $1B qualifying minority
    )


@pytest.fixture
def standard_deductions() -> list[DeductionItem]:
    """Standard set of CET1 deductions."""
    return [
        DeductionItem(
            category=DeductionCategory.GOODWILL,
            amount=30_000.0,
            tier=CapitalTier.CET1,
            description="Goodwill net of DTL",
        ),
        DeductionItem(
            category=DeductionCategory.OTHER_INTANGIBLES,
            amount=5_000.0,
            tier=CapitalTier.CET1,
            description="Other intangibles net of DTL",
        ),
        DeductionItem(
            category=DeductionCategory.DTA_CARRYFORWARD,
            amount=2_000.0,
            tier=CapitalTier.CET1,
            description="DTAs from NOL carryforwards",
        ),
        DeductionItem(
            category=DeductionCategory.DEFINED_BENEFIT_PENSION,
            amount=500.0,
            tier=CapitalTier.CET1,
        ),
    ]


@pytest.fixture
def threshold_inputs() -> ThresholdDeductionInputs:
    """Threshold deduction inputs (MSA, DTA timing, significant investments)."""
    return ThresholdDeductionInputs(
        significant_investments_cet1=8_000.0,
        mortgage_servicing_assets=6_000.0,
        dta_timing_differences=7_000.0,
    )


# =========================================================================
#  CET1 Tests
# =========================================================================

class TestComputeCET1:
    """Tests for compute_cet1 function."""

    def test_gross_cet1_calculation(
        self, large_gsib_equity_inputs: CommonEquityInputs
    ) -> None:
        """Gross CET1 = stock + surplus + RE + AOCI - treasury + minority."""
        result = compute_cet1(large_gsib_equity_inputs, [])
        expected_gross = (
            25_000.0 + 85_000.0 + 95_000.0 + (-3_000.0)
            - 5_000.0 + 1_000.0
        )
        assert result.gross_cet1 == pytest.approx(expected_gross)
        assert result.gross_cet1 == pytest.approx(198_000.0)

    def test_cet1_with_no_deductions(
        self, large_gsib_equity_inputs: CommonEquityInputs
    ) -> None:
        """CET1 with no deductions equals gross CET1."""
        result = compute_cet1(large_gsib_equity_inputs, [])
        assert result.net_cet1 == result.gross_cet1
        assert result.total_deductions == 0.0

    def test_cet1_with_standard_deductions(
        self,
        large_gsib_equity_inputs: CommonEquityInputs,
        standard_deductions: list[DeductionItem],
    ) -> None:
        """CET1 with goodwill, intangibles, DTA deductions."""
        result = compute_cet1(large_gsib_equity_inputs, standard_deductions)

        assert result.goodwill_deduction == pytest.approx(30_000.0)
        assert result.other_intangibles_deduction == pytest.approx(5_000.0)
        assert result.dta_carryforward_deduction == pytest.approx(2_000.0)
        assert result.defined_benefit_pension_deduction == pytest.approx(500.0)

        expected_deductions = 30_000.0 + 5_000.0 + 2_000.0 + 500.0
        assert result.total_deductions == pytest.approx(expected_deductions)
        assert result.net_cet1 == pytest.approx(
            result.gross_cet1 - expected_deductions
        )

    def test_cet1_ignores_non_cet1_deductions(
        self, large_gsib_equity_inputs: CommonEquityInputs
    ) -> None:
        """Deductions tagged as AT1 or Tier2 should not reduce CET1."""
        deductions = [
            DeductionItem(
                category=DeductionCategory.GOODWILL,
                amount=10_000.0,
                tier=CapitalTier.AT1,  # Wrong tier — should be ignored
            ),
        ]
        result = compute_cet1(large_gsib_equity_inputs, deductions)
        assert result.goodwill_deduction == 0.0
        assert result.net_cet1 == result.gross_cet1

    def test_cet1_with_threshold_deductions(
        self,
        large_gsib_equity_inputs: CommonEquityInputs,
        standard_deductions: list[DeductionItem],
        threshold_inputs: ThresholdDeductionInputs,
    ) -> None:
        """Threshold deductions apply 10% individual / 15% aggregate tests."""
        result = compute_cet1(
            large_gsib_equity_inputs,
            standard_deductions,
            threshold_inputs,
        )
        # Net CET1 should be less than without thresholds
        result_no_threshold = compute_cet1(
            large_gsib_equity_inputs, standard_deductions
        )
        assert result.net_cet1 <= result_no_threshold.net_cet1

        # MSA below threshold should get 250% RW per US 2026
        assert result.msa_below_threshold_250rw >= 0.0
        assert result.total_250rw_rwa >= 0.0

    def test_cet1_aoci_negative_reduces_capital(self) -> None:
        """Negative AOCI (unrealized losses) reduces CET1."""
        positive_aoci = CommonEquityInputs(
            common_stock=10_000.0, surplus=50_000.0,
            retained_earnings=60_000.0, aoci=5_000.0,
        )
        negative_aoci = CommonEquityInputs(
            common_stock=10_000.0, surplus=50_000.0,
            retained_earnings=60_000.0, aoci=-5_000.0,
        )
        r_pos = compute_cet1(positive_aoci, [])
        r_neg = compute_cet1(negative_aoci, [])
        assert r_pos.net_cet1 > r_neg.net_cet1
        assert r_pos.net_cet1 - r_neg.net_cet1 == pytest.approx(10_000.0)

    def test_cet1_produces_realistic_amounts(
        self,
        large_gsib_equity_inputs: CommonEquityInputs,
        standard_deductions: list[DeductionItem],
    ) -> None:
        """Net CET1 for a large G-SIB should be in $100-250B range."""
        result = compute_cet1(large_gsib_equity_inputs, standard_deductions)
        assert 100_000.0 <= result.net_cet1 <= 250_000.0


# =========================================================================
#  Threshold Deduction Tests
# =========================================================================

class TestThresholdDeductions:
    """Tests for compute_threshold_deductions per 12 CFR 217.22(d)."""

    def test_all_below_individual_threshold(self) -> None:
        """When all items are below 10%, no individual deductions occur."""
        cet1 = 200_000.0
        threshold = cet1 * DTA_THRESHOLD_PERCENT  # 20,000
        inputs = ThresholdDeductionInputs(
            significant_investments_cet1=15_000.0,  # Below 20,000
            mortgage_servicing_assets=10_000.0,
            dta_timing_differences=12_000.0,
        )
        result = compute_threshold_deductions(cet1, inputs)
        assert result["significant_investments_deduction"] == 0.0
        assert result["msa_deduction"] == 0.0
        assert result["dta_timing_deduction"] == 0.0

    def test_exceeding_individual_threshold(self) -> None:
        """Items exceeding 10% of CET1 are deducted."""
        cet1 = 100_000.0
        threshold = cet1 * DTA_THRESHOLD_PERCENT  # 10,000
        inputs = ThresholdDeductionInputs(
            significant_investments_cet1=15_000.0,  # 5,000 excess
            mortgage_servicing_assets=5_000.0,       # Below threshold
            dta_timing_differences=12_000.0,          # 2,000 excess
        )
        result = compute_threshold_deductions(cet1, inputs)
        assert result["significant_investments_deduction"] == pytest.approx(5_000.0)
        assert result["msa_deduction"] == pytest.approx(0.0)
        assert result["dta_timing_deduction"] == pytest.approx(2_000.0)

    def test_aggregate_threshold(self) -> None:
        """Below-threshold amounts exceeding 15% aggregate trigger deductions."""
        cet1 = 100_000.0
        # 15% aggregate = 15,000
        # Each item at threshold (10,000), total below = 30,000 > 15,000
        inputs = ThresholdDeductionInputs(
            significant_investments_cet1=10_000.0,
            mortgage_servicing_assets=10_000.0,
            dta_timing_differences=10_000.0,
        )
        result = compute_threshold_deductions(cet1, inputs)
        assert result["aggregate_threshold_deduction"] > 0.0

    def test_msa_250rw_per_us_2026(self) -> None:
        """MSA below threshold gets 250% RW (not deducted) per US 2026."""
        cet1 = 200_000.0
        inputs = ThresholdDeductionInputs(
            mortgage_servicing_assets=10_000.0,  # Well below 10% threshold
        )
        result = compute_threshold_deductions(cet1, inputs)
        assert result["msa_deduction"] == 0.0
        assert result["msa_below_threshold"] > 0.0
        assert result["msa_250rw_rwa"] == pytest.approx(
            result["msa_below_threshold"] * MSA_RISK_WEIGHT
        )

    def test_zero_inputs(self) -> None:
        """Zero threshold inputs produce zero deductions."""
        result = compute_threshold_deductions(
            200_000.0, ThresholdDeductionInputs()
        )
        assert result["significant_investments_deduction"] == 0.0
        assert result["aggregate_threshold_deduction"] == 0.0
        assert result["msa_250rw_rwa"] == 0.0


# =========================================================================
#  Tier 2 Amortization Tests
# =========================================================================

class TestTier2Amortization:
    """Tests for compute_tier2_amortization per 12 CFR 217.20(d)(1)(iv)."""

    def test_full_qualifying_above_5_years(self) -> None:
        """Instruments with >5 years maturity qualify at full face value."""
        assert compute_tier2_amortization(1_000.0, 10.0) == pytest.approx(1_000.0)
        assert compute_tier2_amortization(1_000.0, 5.0) == pytest.approx(1_000.0)

    def test_linear_amortization_under_5_years(self) -> None:
        """20% per year straight-line amortization in final 5 years."""
        assert compute_tier2_amortization(1_000.0, 4.0) == pytest.approx(800.0)
        assert compute_tier2_amortization(1_000.0, 3.0) == pytest.approx(600.0)
        assert compute_tier2_amortization(1_000.0, 2.0) == pytest.approx(400.0)
        assert compute_tier2_amortization(1_000.0, 1.0) == pytest.approx(200.0)

    def test_zero_at_maturity(self) -> None:
        """Zero remaining maturity produces zero qualifying amount."""
        assert compute_tier2_amortization(1_000.0, 0.0) == pytest.approx(0.0)

    def test_negative_maturity(self) -> None:
        """Negative maturity (past due) produces zero."""
        assert compute_tier2_amortization(1_000.0, -1.0) == pytest.approx(0.0)
