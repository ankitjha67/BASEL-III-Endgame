"""Tests for Pillar 2 — ICAAP, Buffer Calculator, and IRRBB.

Validates:
- Buffer stack computation (CET1 min + CCB + CCyB + G-SIB + P2A + mgmt)
- MDA quartile determination and distribution constraints
- Pillar 2A risk assessment and add-on calculation
- Capital plan projection
- Stress scenario computation and SCB derivation
- ICAAP master function
- IRRBB EVE and NII calculations

All amounts in USD millions ($M).

References:
- BCBS d309: Pillar 2 (Supervisory Review Process)
- BCBS d368: Interest Rate Risk in the Banking Book
- 12 CFR 217.10-11: Capital buffers
- 12 CFR 217.11(a)(4)(iv): MDA restrictions
"""

import math
from datetime import date

import pytest

from src.pillar2.pillar2_params import (
    CCB_RATE,
    CET1_MINIMUM,
    DEFAULT_PILLAR_2A_RATES,
    ESLR_TOTAL,
    GSIB_SURCHARGE_DEFAULT,
    MANAGEMENT_BUFFER_DEFAULT,
    MDARestrictionQuartile,
    Pillar2AAddOnRates,
    Pillar2RiskCategory,
    PillarTwoThresholds,
    SCB_FLOOR,
    SLR_MINIMUM,
    StressScenarioType,
)
from src.pillar2.buffer_calculator import (
    BufferStackResult,
    MDAAnalysis,
    compute_buffer_distance,
    compute_buffer_stack,
    compute_mda_analysis,
    determine_mda_quartile,
    evaluate_distribution,
)
from src.pillar2.icaap_engine import (
    ConcentrationRiskAssessment,
    ICAAPresult,
    PensionRiskAssessment,
    StressScenarioResult,
    assess_pillar2a_risks,
    build_capital_plan,
    compute_icaap,
    compute_scb_from_stress,
    compute_stress_scenario,
)
from src.pillar2.irrbb.irrbb_params import (
    DEFAULT_USD_SHOCKS,
    IRRBBScenario,
    TIME_BUCKETS_MIDPOINTS,
    compute_scenario_shocks,
    get_shock_params,
)
from src.pillar2.irrbb.irrbb_calculator import (
    CashFlowBucket,
    CurrencyCashFlows,
    calculate_eve_change,
    calculate_nii_change,
    compute_irrbb,
    discount_factor,
)


# =========================================================================
#  Test Parameters
# =========================================================================

class TestPillar2Params:
    """Tests for Pillar 2 regulatory parameters."""

    def test_cet1_minimum(self) -> None:
        """CET1 minimum is 4.5% per 12 CFR 217.10(a)(1)."""
        assert CET1_MINIMUM == 0.045

    def test_ccb_rate(self) -> None:
        """CCB rate is 2.5% per 12 CFR 217.11(a)(4)."""
        assert CCB_RATE == 0.025

    def test_scb_floor(self) -> None:
        """SCB floor is 2.5% per 12 CFR 217.11(a)(2)(iv)."""
        assert SCB_FLOOR == 0.025

    def test_eslr_total(self) -> None:
        """Enhanced SLR is 5.0% per 12 CFR 217.11(d)(4)."""
        assert ESLR_TOTAL == 0.05

    def test_default_pillar_2a_rates(self) -> None:
        """Default Pillar 2A add-on rates are positive."""
        rates = DEFAULT_PILLAR_2A_RATES
        assert rates.concentration_risk > 0
        assert rates.irrbb > 0
        assert rates.model_risk > 0
        assert rates.total_add_on > 0

    def test_pillar_two_thresholds(self) -> None:
        """PillarTwoThresholds produces correct combined buffer."""
        t = PillarTwoThresholds()
        assert t.effective_ccb == max(CCB_RATE, t.scb)
        assert t.combined_buffer_requirement == pytest.approx(
            t.effective_ccb + t.ccyb + t.gsib_surcharge
        )
        assert t.total_cet1_requirement == pytest.approx(
            CET1_MINIMUM + t.combined_buffer_requirement
        )


# =========================================================================
#  Test Buffer Calculator
# =========================================================================

class TestBufferCalculator:
    """Tests for buffer stack computation."""

    def test_buffer_stack_basic(self) -> None:
        """Buffer stack with default parameters."""
        result = compute_buffer_stack(total_rwa=1_000_000.0)
        # Combined buffer = CCB (2.5%) + CCyB (0%) + G-SIB (1.5%)
        assert result.combined_buffer_rate == pytest.approx(0.025 + 0.0 + 0.015)
        assert result.effective_cet1_minimum == pytest.approx(
            0.045 + 0.025 + 0.015
        )
        assert result.combined_buffer_amount == pytest.approx(
            0.04 * 1_000_000.0
        )

    def test_buffer_stack_with_scb(self) -> None:
        """Buffer stack with SCB above floor."""
        result = compute_buffer_stack(
            total_rwa=1_000_000.0,
            scb_rate=0.04,
        )
        # SCB 4% > CCB floor 2.5%, so effective CCB = 4%
        assert result.ccb_or_scb_rate == pytest.approx(0.04)
        assert result.combined_buffer_rate == pytest.approx(0.04 + 0.0 + 0.015)

    def test_buffer_stack_scb_below_floor(self) -> None:
        """SCB below 2.5% floor uses the floor."""
        result = compute_buffer_stack(
            total_rwa=1_000_000.0,
            scb_rate=0.02,
        )
        assert result.ccb_or_scb_rate == pytest.approx(0.025)

    def test_buffer_stack_with_ccyb(self) -> None:
        """Buffer stack with active CCyB."""
        result = compute_buffer_stack(
            total_rwa=1_000_000.0,
            ccyb_rate=0.015,
        )
        assert result.ccyb_rate == pytest.approx(0.015)
        assert result.combined_buffer_rate == pytest.approx(
            0.025 + 0.015 + 0.015
        )

    def test_buffer_stack_invalid_rwa(self) -> None:
        """Raises ValueError for non-positive RWA."""
        with pytest.raises(ValueError, match="Total RWA must be positive"):
            compute_buffer_stack(total_rwa=0.0)

    def test_buffer_stack_invalid_ccyb(self) -> None:
        """Raises ValueError for CCyB out of range."""
        with pytest.raises(ValueError, match="CCyB rate"):
            compute_buffer_stack(total_rwa=1_000_000.0, ccyb_rate=0.03)

    def test_buffer_stack_components(self) -> None:
        """Buffer stack has correct number of components."""
        result = compute_buffer_stack(
            total_rwa=1_000_000.0,
            pillar_2a_addon=0.03,
            management_buffer=0.01,
            planning_buffer=0.005,
        )
        # CET1_MIN + CCB + CCyB + GSIB + P2A + MGMT + PLANNING = 7
        assert len(result.components) == 7

    def test_internal_targets(self) -> None:
        """Internal targets include P2A and management buffers."""
        result = compute_buffer_stack(
            total_rwa=1_000_000.0,
            pillar_2a_addon=0.03,
            management_buffer=0.01,
            planning_buffer=0.005,
        )
        assert result.internal_cet1_target == pytest.approx(
            result.effective_cet1_minimum + 0.03 + 0.01 + 0.005
        )


class TestMDADetermination:
    """Tests for MDA quartile determination per 12 CFR 217.11(a)(4)(iv)."""

    def test_above_buffer(self) -> None:
        """CET1 above combined buffer: no restrictions."""
        q, payout = determine_mda_quartile(0.13, 0.045, 0.04)
        assert q == MDARestrictionQuartile.ABOVE_BUFFER
        assert payout == 1.0

    def test_quartile_4(self) -> None:
        """75-100% buffer utilization: max 60% payout."""
        # Min = 4.5%, buffer = 4%, effective = 8.5%
        # CET1 = 8.4% -> utilization = (8.4-4.5)/4.0 = 97.5% -> Q4
        q, payout = determine_mda_quartile(0.084, 0.045, 0.04)
        assert q == MDARestrictionQuartile.QUARTILE_4
        assert payout == 0.6

    def test_quartile_3(self) -> None:
        """50-75% buffer utilization: max 40% payout."""
        # utilization = (7.0-4.5)/4.0 = 62.5%
        q, payout = determine_mda_quartile(0.07, 0.045, 0.04)
        assert q == MDARestrictionQuartile.QUARTILE_3
        assert payout == 0.4

    def test_quartile_2(self) -> None:
        """25-50% buffer utilization: max 20% payout."""
        # utilization = (5.7-4.5)/4.0 = 30%
        q, payout = determine_mda_quartile(0.057, 0.045, 0.04)
        assert q == MDARestrictionQuartile.QUARTILE_2
        assert payout == 0.2

    def test_quartile_1(self) -> None:
        """0-25% buffer utilization: max 0% payout."""
        # utilization = (5.0-4.5)/4.0 = 12.5%
        q, payout = determine_mda_quartile(0.05, 0.045, 0.04)
        assert q == MDARestrictionQuartile.QUARTILE_1
        assert payout == 0.0

    def test_below_minimum(self) -> None:
        """Below CET1 minimum: distributions prohibited."""
        q, payout = determine_mda_quartile(0.04, 0.045, 0.04)
        assert q == MDARestrictionQuartile.BELOW_MINIMUM
        assert payout == 0.0

    def test_mda_analysis(self) -> None:
        """MDA analysis produces correct distributable amount."""
        mda = compute_mda_analysis(
            cet1_ratio=0.13,
            cet1_capital=195_000.0,
            total_rwa=1_500_000.0,
            combined_buffer=0.04,
            distributable_earnings=10_000.0,
        )
        assert mda.quartile == MDARestrictionQuartile.ABOVE_BUFFER
        assert mda.maximum_payout_ratio == 1.0
        assert mda.mda_amount == pytest.approx(10_000.0)
        assert not mda.breaches_minimum
        assert not mda.distributions_restricted

    def test_evaluate_distribution_permitted(self) -> None:
        """Distribution is permitted when within MDA."""
        result = evaluate_distribution(
            proposed_amount=5_000.0,
            action_type="dividend",
            cet1_capital=195_000.0,
            total_rwa=1_500_000.0,
            combined_buffer=0.04,
            distributable_earnings=10_000.0,
        )
        assert result.is_permitted
        assert result.remaining_mda == pytest.approx(5_000.0)

    def test_evaluate_distribution_denied(self) -> None:
        """Distribution denied when exceeding MDA."""
        result = evaluate_distribution(
            proposed_amount=15_000.0,
            action_type="buyback",
            cet1_capital=195_000.0,
            total_rwa=1_500_000.0,
            combined_buffer=0.04,
            distributable_earnings=10_000.0,
        )
        assert not result.is_permitted


class TestBufferDistance:
    """Tests for buffer distance computation."""

    def test_buffer_distance_surplus(self) -> None:
        """Positive distance indicates surplus above threshold."""
        stack = compute_buffer_stack(total_rwa=1_000_000.0)
        distances = compute_buffer_distance(
            cet1_ratio=0.13, tier1_ratio=0.15,
            total_capital_ratio=0.18, leverage_ratio=0.065,
            buffer_stack=stack,
        )
        assert distances["cet1_vs_minimum"] > 0
        assert distances["cet1_vs_buffer"] > 0
        assert distances["slr_vs_minimum"] > 0
        assert distances["eslr_vs_requirement"] > 0


# =========================================================================
#  Test ICAAP Engine
# =========================================================================

class TestPillar2ARiskAssessment:
    """Tests for Pillar 2A risk add-on assessment."""

    def test_default_risk_assessments(self) -> None:
        """Default assessment produces 8 risk categories."""
        assessments = assess_pillar2a_risks(total_rwa=1_000_000.0)
        assert len(assessments) == 8
        categories = {a.category for a in assessments}
        assert Pillar2RiskCategory.CONCENTRATION_RISK in categories
        assert Pillar2RiskCategory.IRRBB in categories
        assert Pillar2RiskCategory.MODEL_RISK in categories

    def test_addon_amounts(self) -> None:
        """Add-on amounts equal rate * RWA."""
        rwa = 1_000_000.0
        assessments = assess_pillar2a_risks(total_rwa=rwa)
        for a in assessments:
            assert a.addon_amount == pytest.approx(a.addon_rate * rwa)

    def test_custom_concentration_risk(self) -> None:
        """Custom concentration risk assessment overrides default rate."""
        conc = ConcentrationRiskAssessment(
            single_name_addon=0.008,
            sector_addon=0.004,
            geographic_addon=0.003,
        )
        assessments = assess_pillar2a_risks(
            total_rwa=1_000_000.0,
            concentration_risk=conc,
        )
        conc_assessment = [
            a for a in assessments
            if a.category == Pillar2RiskCategory.CONCENTRATION_RISK
        ][0]
        assert conc_assessment.addon_rate == pytest.approx(0.015)


class TestCapitalPlan:
    """Tests for capital plan projections."""

    def test_basic_projection(self) -> None:
        """Basic 12-quarter projection with constant income and distributions."""
        plan = build_capital_plan(
            starting_cet1=180_000.0,
            starting_rwa=1_200_000.0,
            quarterly_net_income=5_000.0,
            quarterly_dividends=2_000.0,
            quarterly_buybacks=1_000.0,
            quarterly_rwa_growth=10_000.0,
            horizon_quarters=12,
        )
        assert len(plan.projections) == 12
        assert plan.total_capital_distributions == pytest.approx(
            12 * (2_000.0 + 1_000.0)
        )
        # CET1 grows by (5000 - 2000 - 1000) = 2000 per quarter
        assert plan.projections[-1].ending_cet1 == pytest.approx(
            180_000.0 + 12 * 2_000.0
        )

    def test_projection_ratio_declines_with_rwa_growth(self) -> None:
        """CET1 ratio declines when RWA growth outpaces capital generation."""
        plan = build_capital_plan(
            starting_cet1=180_000.0,
            starting_rwa=1_200_000.0,
            quarterly_net_income=2_000.0,
            quarterly_dividends=2_000.0,
            quarterly_rwa_growth=50_000.0,
            horizon_quarters=4,
        )
        # Net capital generation = 0, but RWA grows
        assert plan.ending_cet1_ratio < plan.projections[0].ending_cet1_ratio


class TestStressScenario:
    """Tests for stress scenario computation."""

    def test_severely_adverse(self) -> None:
        """Severely adverse scenario with significant losses."""
        result = compute_stress_scenario(
            pre_stress_cet1=180_000.0,
            pre_stress_rwa=1_200_000.0,
            credit_losses=30_000.0,
            market_losses=10_000.0,
            operational_losses=5_000.0,
            ppnr=15_000.0,
            rwa_inflation=100_000.0,
        )
        # Net depletion = 45000 - 15000 = 30000
        assert result.cet1_depletion == pytest.approx(30_000.0)
        assert result.post_stress_cet1 == pytest.approx(150_000.0)
        assert result.post_stress_rwa == pytest.approx(1_300_000.0)
        assert result.post_stress_cet1_ratio == pytest.approx(
            150_000.0 / 1_300_000.0
        )
        assert not result.breaches_minimum  # 11.5% > 4.5%

    def test_breach_minimum(self) -> None:
        """Stress scenario that breaches the CET1 minimum."""
        result = compute_stress_scenario(
            pre_stress_cet1=60_000.0,
            pre_stress_rwa=1_000_000.0,
            credit_losses=40_000.0,
            market_losses=10_000.0,
            operational_losses=5_000.0,
            ppnr=5_000.0,
        )
        # Post CET1 = 60000 - 50000 = 10000, ratio = 1%
        assert result.breaches_minimum

    def test_scb_from_stress(self) -> None:
        """SCB computation from stress test results."""
        sr = compute_stress_scenario(
            pre_stress_cet1=180_000.0,
            pre_stress_rwa=1_200_000.0,
            credit_losses=30_000.0,
            market_losses=10_000.0,
            operational_losses=5_000.0,
            ppnr=15_000.0,
        )
        scb = compute_scb_from_stress(
            stress_results=[sr],
            planned_dividends_4q=0.005,
            pre_stress_cet1_ratio=180_000.0 / 1_200_000.0,
        )
        # Depletion in ratio terms + dividends
        pre_ratio = 180_000.0 / 1_200_000.0
        post_ratio = sr.post_stress_cet1_ratio
        expected = (pre_ratio - post_ratio) + 0.005
        assert scb == pytest.approx(max(expected, 0.025))


class TestICAAP:
    """Tests for the master ICAAP function."""

    def test_icaap_well_capitalized(self) -> None:
        """ICAAP for a well-capitalized G-SIB.

        Internal CET1 target = 4.5% + 2.5% + 0% + 1.5% + 3.2% + 1.0% + 0.5% = 13.2%
        So CET1 must exceed 13.2% to meet internal targets.
        """
        result = compute_icaap(
            cet1_capital=210_000.0,
            tier1_capital=235_000.0,
            total_capital=265_000.0,
            total_rwa=1_500_000.0,
            leverage_ratio=0.06,
            gsib_surcharge=0.015,
        )
        assert result.meets_pillar1_minimums
        assert result.meets_buffer_requirements
        # CET1 ratio = 14.0% > 13.2% internal target
        assert result.meets_internal_targets
        assert result.overall_adequate
        assert result.cet1_ratio == pytest.approx(210_000.0 / 1_500_000.0)
        assert result.total_pillar_2a_addon_rate > 0

    def test_icaap_undercapitalized(self) -> None:
        """ICAAP detects undercapitalization."""
        result = compute_icaap(
            cet1_capital=50_000.0,
            tier1_capital=55_000.0,
            total_capital=60_000.0,
            total_rwa=1_500_000.0,
        )
        # CET1 ratio = 3.33% < 4.5%
        assert not result.meets_pillar1_minimums
        assert not result.overall_adequate

    def test_icaap_invalid_rwa(self) -> None:
        """Raises ValueError for invalid RWA."""
        with pytest.raises(ValueError):
            compute_icaap(
                cet1_capital=195_000.0,
                tier1_capital=215_000.0,
                total_capital=240_000.0,
                total_rwa=0.0,
            )


# =========================================================================
#  Test IRRBB
# =========================================================================

class TestIRRBBParams:
    """Tests for IRRBB parameters."""

    def test_usd_shocks(self) -> None:
        """USD shock parameters per BCBS d368."""
        params = DEFAULT_USD_SHOCKS
        assert params.parallel_shock_bp == 200
        assert params.short_rate_shock_bp == 300
        assert params.long_rate_shock_bp == 150

    def test_get_shock_params_known_currency(self) -> None:
        """Known currency returns specific shocks."""
        gbp = get_shock_params("GBP")
        assert gbp.parallel_shock_bp == 250

    def test_get_shock_params_unknown_currency(self) -> None:
        """Unknown currency falls back to USD."""
        params = get_shock_params("XYZ")
        assert params.parallel_shock_bp == DEFAULT_USD_SHOCKS.parallel_shock_bp

    def test_scenario_shocks_parallel_up(self) -> None:
        """Parallel up produces uniform positive shocks."""
        shocks = compute_scenario_shocks(
            IRRBBScenario.PARALLEL_UP, DEFAULT_USD_SHOCKS
        )
        assert all(s == pytest.approx(0.02) for s in shocks)

    def test_scenario_shocks_parallel_down(self) -> None:
        """Parallel down produces uniform negative shocks."""
        shocks = compute_scenario_shocks(
            IRRBBScenario.PARALLEL_DOWN, DEFAULT_USD_SHOCKS
        )
        assert all(s == pytest.approx(-0.02) for s in shocks)

    def test_scenario_shocks_steepener(self) -> None:
        """Steepener: short-end negative, long-end positive."""
        shocks = compute_scenario_shocks(
            IRRBBScenario.STEEPENER, DEFAULT_USD_SHOCKS
        )
        # Short end (first bucket) should be negative
        assert shocks[0] < 0
        # Long end (last bucket) should be positive
        assert shocks[-1] > 0


class TestIRRBBCalculator:
    """Tests for IRRBB EVE and NII calculations."""

    @pytest.fixture
    def sample_buckets(self) -> list[CashFlowBucket]:
        """Create sample cash flow buckets for testing."""
        buckets: list[CashFlowBucket] = []
        midpoints = [0.5, 1.0, 2.0, 5.0, 10.0]
        base_rates = [0.04, 0.042, 0.045, 0.048, 0.05]
        for i, (mp, rate) in enumerate(zip(midpoints, base_rates)):
            buckets.append(CashFlowBucket(
                bucket_index=i,
                midpoint_years=mp,
                net_cash_flows=1000.0 if i < 3 else -800.0,
                base_rate=rate,
                asset_notional=5000.0,
                liability_notional=4000.0 if i < 3 else 6000.0,
            ))
        return buckets

    def test_discount_factor(self) -> None:
        """Discount factor decreases with higher rate or longer maturity."""
        df1 = discount_factor(0.05, 1.0)
        df2 = discount_factor(0.05, 5.0)
        assert df1 > df2
        assert df1 == pytest.approx(math.exp(-0.05))

    def test_eve_change_parallel_up(
        self, sample_buckets: list[CashFlowBucket]
    ) -> None:
        """EVE change under parallel up scenario."""
        result = calculate_eve_change(
            sample_buckets,
            IRRBBScenario.PARALLEL_UP,
        )
        assert result.scenario == IRRBBScenario.PARALLEL_UP
        assert result.base_eve != 0
        # Parallel up generally reduces EVE for positive duration
        # (depends on net position structure)
        assert result.eve_change != 0

    def test_nii_change(
        self, sample_buckets: list[CashFlowBucket]
    ) -> None:
        """NII change under parallel up scenario."""
        result = calculate_nii_change(
            sample_buckets,
            IRRBBScenario.PARALLEL_UP,
        )
        assert result.scenario == IRRBBScenario.PARALLEL_UP
        assert result.nii_change != 0

    def test_compute_irrbb_complete(
        self, sample_buckets: list[CashFlowBucket]
    ) -> None:
        """Complete IRRBB assessment across all scenarios."""
        ccf = CurrencyCashFlows(
            currency="USD",
            buckets=sample_buckets,
        )
        result = compute_irrbb(
            currency_cash_flows=[ccf],
            tier1_capital=200_000.0,
            total_rwa=1_500_000.0,
        )
        # 6 scenarios * 1 currency = 6 EVE results
        assert len(result.eve_result.scenario_results) == 6
        assert len(result.nii_result.scenario_results) == 6
        assert result.irrbb_capital_addon >= 0
        assert "USD" in result.currencies_analyzed
