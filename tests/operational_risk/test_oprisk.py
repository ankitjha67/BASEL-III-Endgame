"""Tests for the ERBA NPR §__.150 operational risk calculator.

Validates the US business-indicator approach as written in the March 2026
re-proposal (12 CFR 217.150) and the §__.101 definitions:

- RWA = 12.5 x BIC, no internal loss multiplier (§__.150(a))
- BIC closed form and marginal form agree; 12% / 15% / 18% tiers (§__.150(b))
- ILDC = min(Avg3y|TII - TIE|, 2.25% x Avg3y IEA) + Avg3y dividends
  (§__.150(c)(1)(i))
- Noninterest component with 0.7 net service-line reduction and
  operational losses added (§__.150(c)(1)(ii))
- Three-period averaging, 12-quarter IEA averaging, quarterly loss sums
- Loss event data: $20,000 threshold, ten years, seven event types
- Reporting (OR1, FFIEC 101, HC-R, loss data summary)

All amounts in $M unless suffixed _usd.
"""

from __future__ import annotations

import pytest

from src.operational_risk import (
    BIC_COEFFICIENTS,
    BIC_THRESHOLD_1_USD_M,
    BIC_THRESHOLD_2_USD_M,
    ILDC_INTEREST_CAP_RATE,
    ILM,
    LOSS_COLLECTION_THRESHOLD_USD,
    LOSS_DATA_YEARS,
    NIC_INVESTMENT_MANAGEMENT_FACTOR,
    RWA_CONVERSION_FACTOR,
    SERVICES_NET_INCOME_FACTOR,
    BusinessIndicatorInputs,
    FinancialStatementData,
    LossComponentData,
    LossEventType,
    OperationalLossData,
    OpRiskCalculator,
    OpRiskReportGenerator,
    OpRiskResult,
    ServiceLine,
    ServiceLineData,
    compute_bic,
    compute_bic_closed_form,
)
from src.operational_risk.or_params import (
    BIC_TIER_2_INTERCEPT_USD_M,
    BIC_TIER_3_INTERCEPT_USD_M,
    IEA_AVERAGING_QUARTERS,
    LOSS_THRESHOLD_USD,
    RETAIL_CARD_THIRD_PARTY_FRAUD_EVENT_TYPE,
    aggregate_quarterly_losses_to_periods,
    average_interest_earning_assets,
    average_over_periods,
    compute_bcbs_reference_ilm,
    compute_ilm,
    compute_loss_component,
)

# =========================================================================
#  Fixtures — the closed-form worked example from the task
# =========================================================================

def _worked_example_inputs(**overrides: object) -> BusinessIndicatorInputs:
    """Three identical years:

    NII 10,000; IEA 300,000 (cap 6,750 binds); dividends 100;
    noninterest income 8,000; realized G/L 0; noninterest expense for BI
    3,000; service-line income 2,000 / expense 500; op losses 200.

    ILDC = 6,750 + 100 = 6,850
    NIC  = |8,000 - 3,000 - 0.7 x 1,500| + 200 = 3,950 + 200 = 4,150
    BI   = 11,000 -> BIC = 120 + 0.15 x 10,000 = 1,620 -> RWA = 20,250
    """
    base: dict[str, object] = dict(
        total_interest_income=[15_000.0, 15_000.0, 15_000.0],
        total_interest_expense=[5_000.0, 5_000.0, 5_000.0],
        interest_earning_assets=[300_000.0, 300_000.0, 300_000.0],
        dividend_income=100.0,
        total_noninterest_income=8_000.0,
        realized_gains_losses_htm_securities=0.0,
        realized_gains_losses_afs_debt_securities=0.0,
        noninterest_expense_for_bi=3_000.0,
        service_lines=[
            ServiceLineData(
                service_line=ServiceLine.INVESTMENT_MANAGEMENT,
                noninterest_income=1_000.0,
                noninterest_expense_for_bi=200.0,
            ),
            ServiceLineData(
                service_line=ServiceLine.INVESTMENT_SERVICES,
                noninterest_income=600.0,
                noninterest_expense_for_bi=200.0,
            ),
            ServiceLineData(
                service_line=ServiceLine.NON_LENDING_TREASURY_SERVICES,
                noninterest_income=400.0,
                noninterest_expense_for_bi=100.0,
            ),
        ],
        total_operational_losses=[200.0, 200.0, 200.0],
    )
    base.update(overrides)
    return BusinessIndicatorInputs(**base)  # type: ignore[arg-type]


@pytest.fixture
def calc() -> OpRiskCalculator:
    return OpRiskCalculator()


@pytest.fixture
def worked_example() -> BusinessIndicatorInputs:
    return _worked_example_inputs()


# =========================================================================
#  Parameters
# =========================================================================

class TestParameters:
    """Regulatory constants per ERBA NPR §__.150 / §__.101."""

    def test_no_ilm(self) -> None:
        assert ILM == 1.0

    def test_rwa_factor(self) -> None:
        assert RWA_CONVERSION_FACTOR == 12.5

    def test_interest_cap_rate(self) -> None:
        assert ILDC_INTEREST_CAP_RATE == 0.0225

    def test_bic_thresholds_in_usd_m(self) -> None:
        assert BIC_THRESHOLD_1_USD_M == 1_000.0
        assert BIC_THRESHOLD_2_USD_M == 30_000.0
        assert [c for _, c in BIC_COEFFICIENTS] == [0.12, 0.15, 0.18]

    def test_bic_intercepts_match_fn_230(self) -> None:
        """$120M = 0.12 x $1B; $4.47B = $120M + 0.15 x $29B."""
        assert pytest.approx(120.0) == BIC_TIER_2_INTERCEPT_USD_M
        assert pytest.approx(4_470.0) == BIC_TIER_3_INTERCEPT_USD_M

    def test_services_factor_applies_to_all_three_lines(self) -> None:
        assert SERVICES_NET_INCOME_FACTOR == 0.7
        assert NIC_INVESTMENT_MANAGEMENT_FACTOR is SERVICES_NET_INCOME_FACTOR or (
            NIC_INVESTMENT_MANAGEMENT_FACTOR == SERVICES_NET_INCOME_FACTOR
        )
        assert {s.value for s in ServiceLine} == {
            "INVESTMENT_MANAGEMENT",
            "INVESTMENT_SERVICES",
            "NON_LENDING_TREASURY_SERVICES",
        }

    def test_loss_threshold_is_20000_usd(self) -> None:
        """§__.150: $20,000 indexed threshold, not EUR 20,000 / $22,000."""
        assert LOSS_COLLECTION_THRESHOLD_USD == 20_000.0
        assert LOSS_THRESHOLD_USD == 20_000.0

    def test_ten_years_of_loss_data(self) -> None:
        assert LOSS_DATA_YEARS == 10

    def test_seven_event_types(self) -> None:
        assert len(LossEventType) == 7
        assert RETAIL_CARD_THIRD_PARTY_FRAUD_EVENT_TYPE is LossEventType.EXTERNAL_FRAUD

    def test_iea_averaging_quarters(self) -> None:
        assert IEA_AVERAGING_QUARTERS == 12


# =========================================================================
#  BIC — §__.150(b)
# =========================================================================

class TestBIC:
    """BIC closed form and marginal form per §__.150(b)."""

    @pytest.mark.parametrize("bi", [0.0, 500.0, 1_000.0, 11_000.0, 30_000.0, 50_000.0, 250_000.0])
    def test_closed_form_equals_marginal_form(self, bi: float) -> None:
        assert compute_bic(bi) == pytest.approx(compute_bic_closed_form(bi))

    def test_tier_1(self) -> None:
        assert compute_bic(500.0) == pytest.approx(0.12 * 500.0)

    def test_tier_1_boundary(self) -> None:
        assert compute_bic(1_000.0) == pytest.approx(120.0)

    def test_tier_2(self) -> None:
        """$10B: $120M + 0.15 x $9B = $1.47B."""
        assert compute_bic(10_000.0) == pytest.approx(120.0 + 0.15 * 9_000.0)

    def test_tier_2_boundary(self) -> None:
        assert compute_bic(30_000.0) == pytest.approx(4_470.0)

    def test_tier_3(self) -> None:
        """$50B: $4.47B + 0.18 x $20B = $8.07B."""
        assert compute_bic(50_000.0) == pytest.approx(4_470.0 + 0.18 * 20_000.0)
        assert compute_bic(50_000.0) == pytest.approx(8_070.0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            compute_bic(-1.0)
        with pytest.raises(ValueError, match="negative"):
            compute_bic_closed_form(-1.0)


# =========================================================================
#  Averaging helpers — §__.150(c)
# =========================================================================

class TestAveraging:
    def test_average_over_periods(self) -> None:
        assert average_over_periods([1.0, 2.0, 6.0]) == pytest.approx(3.0)

    def test_average_over_periods_requires_three(self) -> None:
        with pytest.raises(ValueError):
            average_over_periods([1.0, 2.0])

    def test_iea_twelve_quarter_ends(self) -> None:
        values = [100.0 + i for i in range(12)]
        assert average_interest_earning_assets(values) == pytest.approx(sum(values) / 12)

    def test_iea_wrong_count(self) -> None:
        with pytest.raises(ValueError):
            average_interest_earning_assets([1.0] * 11)

    def test_quarterly_losses_summed_into_periods(self) -> None:
        q = [1.0, 2.0, 3.0, 4.0, 10.0, 10.0, 10.0, 10.0, 0.0, 0.0, 0.0, 5.0]
        assert aggregate_quarterly_losses_to_periods(q) == [10.0, 40.0, 5.0]

    def test_quarterly_losses_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            aggregate_quarterly_losses_to_periods([-1.0] + [0.0] * 11)


# =========================================================================
#  Closed-form worked examples — full calculation
# =========================================================================

class TestWorkedExample:
    """Three identical years; see _worked_example_inputs docstring."""

    def test_ildc(self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs) -> None:
        r = calc.calculate(worked_example)
        bd = r.bi_component_breakdown
        assert bd is not None
        assert bd.avg_abs_net_interest_income == pytest.approx(10_000.0)
        assert bd.interest_cap == pytest.approx(6_750.0)
        assert bd.ildc_cap_applied is True
        assert bd.interest_component == pytest.approx(6_750.0)
        assert bd.avg_dividend_income == pytest.approx(100.0)
        assert r.ildc == pytest.approx(6_850.0)

    def test_noninterest_component(
        self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs
    ) -> None:
        r = calc.calculate(worked_example)
        bd = r.bi_component_breakdown
        assert bd is not None
        assert bd.avg_service_line_income == pytest.approx(2_000.0)
        assert bd.avg_service_line_expense_for_bi == pytest.approx(500.0)
        assert bd.avg_services_adjustment == pytest.approx(1_050.0)
        assert r.services_adjustment == pytest.approx(1_050.0)
        assert bd.avg_abs_net_noninterest == pytest.approx(3_950.0)
        assert bd.avg_total_operational_losses == pytest.approx(200.0)
        assert r.noninterest_component == pytest.approx(4_150.0)

    def test_bi_bic_rwa(
        self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs
    ) -> None:
        r = calc.calculate(worked_example)
        assert r.business_indicator == pytest.approx(11_000.0)
        assert r.bic == pytest.approx(1_620.0)
        assert r.capital_charge == pytest.approx(1_620.0)
        assert r.rwa == pytest.approx(20_250.0)
        assert r.ilm == 1.0
        assert r.bi_bucket.startswith("Tier 2")

    def test_bi_is_two_components(
        self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs
    ) -> None:
        r = calc.calculate(worked_example)
        assert r.business_indicator == pytest.approx(r.ildc + r.noninterest_component)
        assert not hasattr(r, "sc")
        assert not hasattr(r, "fc")

    def test_calculate_rwa_shortcut(
        self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs
    ) -> None:
        assert calc.calculate_rwa(worked_example) == pytest.approx(20_250.0)

    def test_bucket_breakdown_sums_to_bic(
        self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs
    ) -> None:
        r = calc.calculate(worked_example)
        assert sum(r.capital_charge_by_bucket.values()) == pytest.approx(r.bic)
        assert r.capital_charge_by_bucket["bucket_1_to_1B"] == pytest.approx(120.0)
        assert r.capital_charge_by_bucket["bucket_1B_to_30B"] == pytest.approx(1_500.0)
        assert "bucket_above_30B" not in r.capital_charge_by_bucket

    def test_scalar_inputs_give_same_answer(self, calc: OpRiskCalculator) -> None:
        """Pre-averaged scalars equal the three-year lists when signs are stable."""
        scalar = _worked_example_inputs(
            total_interest_income=15_000.0,
            total_interest_expense=5_000.0,
            interest_earning_assets=300_000.0,
            total_operational_losses=200.0,
        )
        assert calc.calculate(scalar).rwa == pytest.approx(20_250.0)

    def test_tier_3_example(self, calc: OpRiskCalculator) -> None:
        """BI = $50B -> BIC = $4.47B + 0.18 x $20B = $8.07B; RWA = $100.875B.

        Build BI = 50,000: ILDC = 20,000 (uncapped, cap = 0.0225 x 2M = 45,000)
        + 0 dividends; NIC = |40,000 - 10,000 - 0| + 0 = 30,000.
        """
        inputs = BusinessIndicatorInputs(
            total_interest_income=60_000.0,
            total_interest_expense=40_000.0,
            interest_earning_assets=2_000_000.0,
            dividend_income=0.0,
            total_noninterest_income=40_000.0,
            noninterest_expense_for_bi=10_000.0,
            total_operational_losses=0.0,
        )
        r = calc.calculate(inputs)
        assert r.business_indicator == pytest.approx(50_000.0)
        assert r.bi_component_breakdown is not None
        assert r.bi_component_breakdown.ildc_cap_applied is False
        assert r.bic == pytest.approx(8_070.0)
        assert r.rwa == pytest.approx(8_070.0 * 12.5)
        assert r.bi_bucket.startswith("Tier 3")
        assert r.capital_charge_by_bucket["bucket_above_30B"] == pytest.approx(3_600.0)

    def test_tier_1_example(self, calc: OpRiskCalculator) -> None:
        """BI = 500 -> BIC = 60; RWA = 750."""
        inputs = BusinessIndicatorInputs(
            total_interest_income=600.0,
            total_interest_expense=300.0,
            interest_earning_assets=100_000.0,
            total_noninterest_income=300.0,
            noninterest_expense_for_bi=100.0,
            total_operational_losses=0.0,
        )
        r = calc.calculate(inputs)
        assert r.business_indicator == pytest.approx(500.0)
        assert r.bic == pytest.approx(60.0)
        assert r.rwa == pytest.approx(750.0)


# =========================================================================
#  Formula details — §__.150(c)(1)(i)-(ii)
# =========================================================================

class TestFormulaDetails:
    def test_abs_inside_average_for_interest(self, calc: OpRiskCalculator) -> None:
        """Avg3y(|TII - TIE|): signs flip across years -> abs per year."""
        inputs = _worked_example_inputs(
            total_interest_income=[10_000.0, 2_000.0, 10_000.0],
            total_interest_expense=[2_000.0, 10_000.0, 2_000.0],
            interest_earning_assets=10_000_000.0,  # cap far above
        )
        bd = calc.calculate(inputs).bi_component_breakdown
        assert bd is not None
        # per-year |diff| = 8,000 each -> average 8,000 (not |avg diff| = 2,667)
        assert bd.avg_abs_net_interest_income == pytest.approx(8_000.0)

    def test_abs_inside_average_for_noninterest(self, calc: OpRiskCalculator) -> None:
        """Avg3y(|X_t| + L_t): a loss year contributes its magnitude."""
        inputs = _worked_example_inputs(
            total_noninterest_income=[8_000.0, 0.0, 8_000.0],
            noninterest_expense_for_bi=[3_000.0, 3_000.0, 3_000.0],
            service_lines=[],
            total_operational_losses=[0.0, 0.0, 0.0],
        )
        bd = calc.calculate(inputs).bi_component_breakdown
        assert bd is not None
        assert bd.period_abs_net_noninterest == pytest.approx([5_000.0, 3_000.0, 5_000.0])
        assert bd.noninterest_component == pytest.approx((5_000.0 + 3_000.0 + 5_000.0) / 3)

    def test_realized_gains_losses_enter_signed(self, calc: OpRiskCalculator) -> None:
        inputs = _worked_example_inputs(
            realized_gains_losses_htm_securities=-300.0,
            realized_gains_losses_afs_debt_securities=100.0,
        )
        r = calc.calculate(inputs)
        # |8,000 - 300 + 100 - 3,000 - 1,050| + 200 = 3,750 + 200
        assert r.noninterest_component == pytest.approx(3_950.0)

    def test_operational_losses_added_outside_abs(self, calc: OpRiskCalculator) -> None:
        """Losses add positively even when netted income is negative."""
        inputs = _worked_example_inputs(
            total_noninterest_income=1_000.0,
            noninterest_expense_for_bi=3_000.0,
            service_lines=[],
            total_operational_losses=500.0,
        )
        r = calc.calculate(inputs)
        assert r.noninterest_component == pytest.approx(2_000.0 + 500.0)

    def test_services_factor_applies_to_each_line_equally(
        self, calc: OpRiskCalculator
    ) -> None:
        """Putting all 1,500 of net service income in IS or NLTS gives the same BI."""
        results = []
        for line in ServiceLine:
            inputs = _worked_example_inputs(
                service_lines=[
                    ServiceLineData(
                        service_line=line,
                        noninterest_income=2_000.0,
                        noninterest_expense_for_bi=500.0,
                    )
                ]
            )
            results.append(calc.calculate(inputs).business_indicator)
        assert all(b == pytest.approx(11_000.0) for b in results)

    def test_services_netting_is_net_not_gross(self, calc: OpRiskCalculator) -> None:
        """0.7 x (income - expense), not 0.7 x income."""
        inputs = _worked_example_inputs()
        r = calc.calculate(inputs)
        assert r.services_adjustment == pytest.approx(0.7 * (2_000.0 - 500.0))
        assert r.services_adjustment != pytest.approx(0.7 * 2_000.0)

    def test_iea_from_twelve_quarter_ends(self, calc: OpRiskCalculator) -> None:
        quarters = [200_000.0] * 4 + [300_000.0] * 4 + [400_000.0] * 4  # avg 300,000
        inputs = _worked_example_inputs(interest_earning_assets=quarters)
        bd = calc.calculate(inputs).bi_component_breakdown
        assert bd is not None
        assert bd.avg_interest_earning_assets == pytest.approx(300_000.0)
        assert bd.interest_cap == pytest.approx(6_750.0)

    def test_losses_from_twelve_quarters(self, calc: OpRiskCalculator) -> None:
        quarterly = [50.0] * 12  # 200 per four-quarter period
        inputs = _worked_example_inputs(total_operational_losses=quarterly)
        assert calc.calculate(inputs).rwa == pytest.approx(20_250.0)

    def test_losses_derived_from_loss_data(self, calc: OpRiskCalculator) -> None:
        inputs = _worked_example_inputs(total_operational_losses=None)
        loss_data = OperationalLossData(
            annual_losses=[900.0] * 7 + [200.0, 200.0, 200.0],
        )
        assert calc.calculate(inputs, loss_data=loss_data).rwa == pytest.approx(20_250.0)
        assert OpRiskCalculator(loss_data=loss_data).calculate(inputs).rwa == pytest.approx(
            20_250.0
        )

    def test_missing_losses_raises(self, calc: OpRiskCalculator) -> None:
        inputs = _worked_example_inputs(total_operational_losses=None)
        with pytest.raises(ValueError, match="total_operational_losses"):
            calc.calculate(inputs)

    def test_dividends_outside_cap(self, calc: OpRiskCalculator) -> None:
        """Dividend income is added after the 2.25% cap."""
        r_lo = calc.calculate(_worked_example_inputs(dividend_income=100.0))
        r_hi = calc.calculate(_worked_example_inputs(dividend_income=1_100.0))
        assert r_hi.ildc - r_lo.ildc == pytest.approx(1_000.0)


# =========================================================================
#  No ILM — §__.150(a)
# =========================================================================

class TestNoILM:
    def test_result_rejects_other_ilm(self) -> None:
        with pytest.raises(ValueError, match="multiplier"):
            OpRiskResult(
                business_indicator=11_000.0,
                ildc=6_850.0,
                noninterest_component=4_150.0,
                bic=1_620.0,
                ilm=1.2,
                capital_charge=1_620.0,
                rwa=20_250.0,
            )

    def test_result_rejects_capital_not_equal_bic(self) -> None:
        with pytest.raises(ValueError, match="equal BIC"):
            OpRiskResult(
                business_indicator=11_000.0,
                ildc=6_850.0,
                noninterest_component=4_150.0,
                bic=1_620.0,
                capital_charge=1_944.0,
                rwa=24_300.0,
            )

    def test_compute_ilm_always_one(self) -> None:
        assert compute_ilm(1e9, 1.0) == 1.0
        assert compute_ilm() == 1.0

    def test_bcbs_reference_functions_are_isolated(self) -> None:
        """Reference formulas exist for benchmarking but are not in the US path."""
        import inspect

        from src.operational_risk import or_calculator

        src = inspect.getsource(or_calculator)
        assert "compute_bcbs_reference_ilm" not in src
        assert "compute_loss_component" not in src
        assert "LC_MULTIPLIER" not in src
        assert compute_loss_component(100.0, 10_000.0) == pytest.approx(1_500.0)
        assert compute_bcbs_reference_ilm(1_500.0, 1_620.0) > 0.0


# =========================================================================
#  Input validation
# =========================================================================

class TestInputValidation:
    def test_negative_iea_rejected(self) -> None:
        with pytest.raises(ValueError):
            _worked_example_inputs(interest_earning_assets=-1.0)

    def test_wrong_number_of_years_rejected(self) -> None:
        with pytest.raises(ValueError):
            _worked_example_inputs(total_interest_income=[1.0, 2.0])

    def test_iea_count_must_be_1_3_or_12(self) -> None:
        with pytest.raises(ValueError):
            _worked_example_inputs(interest_earning_assets=[1.0] * 5)

    def test_negative_losses_rejected(self) -> None:
        with pytest.raises(ValueError):
            _worked_example_inputs(total_operational_losses=[-1.0, 0.0, 0.0])

    def test_duplicate_service_line_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            _worked_example_inputs(
                service_lines=[
                    ServiceLineData(service_line=ServiceLine.INVESTMENT_SERVICES),
                    ServiceLineData(service_line=ServiceLine.INVESTMENT_SERVICES),
                ]
            )

    def test_validate_inputs_warnings(self) -> None:
        inputs = BusinessIndicatorInputs(
            total_interest_income=100.0,
            total_interest_expense=50.0,
            interest_earning_assets=0.0,
            total_noninterest_income=0.0,
            noninterest_expense_for_bi=0.0,
        )
        warnings = OpRiskCalculator.validate_inputs(inputs)
        assert any("interest-earning assets" in w for w in warnings)
        assert any("noninterest" in w for w in warnings)
        assert any("total_operational_losses" in w for w in warnings)
        # legacy alias
        assert OpRiskCalculator.validate_financial_data(inputs) == warnings

    def test_validate_inputs_clean(self, worked_example: BusinessIndicatorInputs) -> None:
        assert OpRiskCalculator.validate_inputs(worked_example) == []

    def test_service_line_exceeding_total_flagged(self) -> None:
        inputs = _worked_example_inputs(total_noninterest_income=1_000.0)
        warnings = OpRiskCalculator.validate_inputs(inputs)
        assert any("Service-line noninterest income exceeds" in w for w in warnings)

    def test_backward_compatible_aliases(self) -> None:
        assert FinancialStatementData is BusinessIndicatorInputs
        assert LossComponentData is OperationalLossData


# =========================================================================
#  Loss event data — §__.150 / §__.101
# =========================================================================

class TestLossEventData:
    def test_threshold_cannot_exceed_regulatory(self) -> None:
        with pytest.raises(ValueError, match="exceeds"):
            OperationalLossData(collection_threshold_usd=22_000.0)
        ok = OperationalLossData(collection_threshold_usd=10_000.0)
        assert ok.collection_threshold_usd == 10_000.0

    def test_default_threshold(self) -> None:
        assert OperationalLossData().collection_threshold_usd == 20_000.0

    def test_ten_year_requirement(self) -> None:
        assert OperationalLossData(annual_losses=[1.0] * 10).meets_ten_year_requirement
        assert not OperationalLossData(annual_losses=[1.0] * 9).meets_ten_year_requirement

    def test_negative_annual_losses_rejected(self) -> None:
        with pytest.raises(ValueError):
            OperationalLossData(annual_losses=[-100.0, 200.0])

    def test_most_recent_period_losses(self) -> None:
        ld = OperationalLossData(annual_losses=[1.0, 2.0, 3.0, 4.0, 5.0])
        assert ld.most_recent_period_losses() == [3.0, 4.0, 5.0]
        with pytest.raises(ValueError):
            OperationalLossData(annual_losses=[1.0, 2.0]).most_recent_period_losses()

    def test_event_type_keys_coerced(self) -> None:
        ld = OperationalLossData(
            losses_by_event_type={"EXTERNAL_FRAUD": 10.0, LossEventType.INTERNAL_FRAUD: 5.0}
        )
        assert ld.losses_by_event_type[LossEventType.EXTERNAL_FRAUD] == 10.0


# =========================================================================
#  Reporting
# =========================================================================

class TestReporting:
    @pytest.fixture
    def result(
        self, calc: OpRiskCalculator, worked_example: BusinessIndicatorInputs
    ) -> OpRiskResult:
        return calc.calculate(worked_example)

    def test_or1(self, result: OpRiskResult) -> None:
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_or1(result, "2026-03-31")
        assert len(report.rows) == 3
        assert report.rows[0].bi_amount_usd_m == pytest.approx(1_000.0)
        assert report.rows[1].bi_amount_usd_m == pytest.approx(10_000.0)
        assert report.rows[2].bi_amount_usd_m == pytest.approx(0.0)
        assert sum(r.bic_amount_usd_m for r in report.rows) == pytest.approx(1_620.0)
        assert report.total_rwa_usd_m == pytest.approx(20_250.0)
        assert report.ildc_usd_m == pytest.approx(6_850.0)
        assert report.noninterest_component_usd_m == pytest.approx(4_150.0)
        assert report.services_adjustment_usd_m == pytest.approx(1_050.0)
        assert report.avg_total_operational_losses_usd_m == pytest.approx(200.0)
        assert report.ilm_applied == 1.0
        assert any("§__.150(a)" in n for n in report.notes)

    def test_or1_notes_loss_data(self, result: OpRiskResult) -> None:
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_or1(
            result, "2026-03-31", loss_data=OperationalLossData(annual_losses=[1.0] * 10)
        )
        assert any("10 years held" in n for n in report.notes)

    def test_ffiec101(self, result: OpRiskResult) -> None:
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_ffiec101(result, "2026-03-31")
        assert len(report.lines) == 8
        by_line = {line.line_number: line.amount_usd_m for line in report.lines}
        assert by_line["14a"] == pytest.approx(11_000.0)
        assert by_line["14b"] == pytest.approx(6_850.0)
        assert by_line["14c"] == pytest.approx(4_150.0)
        assert by_line["14f"] == pytest.approx(1_620.0)
        assert by_line["14h"] == pytest.approx(20_250.0)
        assert report.total_oprisk_rwa_usd_m == pytest.approx(20_250.0)

    def test_hcr(self, result: OpRiskResult) -> None:
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_hcr_section(result, "2026-03-31")
        assert report.oprisk_rwa_usd_m == pytest.approx(result.rwa)
        assert report.oprisk_capital_usd_m == pytest.approx(result.bic)
        assert report.ilm == 1.0

    def test_loss_data_summary(self) -> None:
        gen = OpRiskReportGenerator("Test Bank")
        ld = OperationalLossData(
            annual_losses=[100.0] * 7 + [200.0, 150.0, 250.0],
            total_loss_events=50,
            largest_single_loss=100.0,
            losses_by_event_type={LossEventType.EXTERNAL_FRAUD: 300.0},
        )
        summary = gen.generate_loss_data_summary(ld)
        assert summary.data_years == 10
        assert summary.meets_ten_year_requirement is True
        assert summary.three_year_average_loss_usd_m == pytest.approx(200.0)
        assert summary.loss_threshold_usd == 20_000.0
        assert summary.losses_by_event_type == {"EXTERNAL_FRAUD": 300.0}
        assert not hasattr(summary, "loss_component_usd_m")
