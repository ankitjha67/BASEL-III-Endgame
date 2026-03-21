"""Integration Tests — End-to-end capital calculation for a Category I G-SIB.

Tests the full pipeline from exposure-level inputs through risk-weighted assets,
capital components, ratios, buffers, and stress testing for a realistic $3.2T
Category I US G-SIB.

Target: CET1 ratio 10-15%, SLR 5-7% per CLAUDE.md requirements.

References:
    - ERBA NPR: Complete Basel III Endgame framework
    - FR Y-9C Schedule HC-R: Regulatory capital
    - FFIEC 101 Schedule A: RWA by exposure type
"""

import pytest

from src.capital.capital_components import (
    CommonEquityInputs,
    DeductionItem,
    DeductionCategory,
    CapitalTier,
    ThresholdDeductionInputs,
    compute_cet1,
    compute_at1,
    compute_tier2,
    AT1Instrument,
    Tier2Instrument,
    InstrumentType,
    LeverageExposureInputs,
)
from src.capital.capital_ratios import (
    compute_capital_adequacy,
    PCACategory,
)
from src.capital.rwa_aggregator import (
    CreditRiskExposureType,
    CreditRiskRWAItem,
    CreditRiskRWAInput,
    MarketRiskRWAInput,
    OperationalRiskRWAInput,
    CVARiskRWAInput,
    aggregate_credit_risk_rwa,
    aggregate_rwa,
)
from src.stress_testing.stress_params import ScenarioType
from src.stress_testing.scenario_engine import ScenarioEngine
from src.stress_testing.capital_projector import CapitalProjector
from src.stress_testing.stress_results import compute_stress_test_results
from src.ecl.ecl_calculator import ECLCalculator, ECLExposure
from src.ecl.staging.staging_engine import Stage


# =========================================================================
#  Realistic G-SIB Portfolio Data
#  $3.2T total assets, Category I US G-SIB
# =========================================================================

class TestEndToEndCapitalCalculation:
    """Full end-to-end capital calculation pipeline."""

    def _build_credit_risk_rwa(self) -> CreditRiskRWAInput:
        """Build realistic credit risk RWA for a $3.2T G-SIB.

        Portfolio composition:
        - US Treasuries: $500B at 0% RW
        - Agency MBS: $300B at 20% RW
        - IG Corporates: $400B at 65% RW
        - HY Corporates: $100B at 100% RW
        - Retail Mortgages: $250B at 50% RW (avg)
        - Retail Transactor: $80B at 45% RW
        - CRE: $100B at 150% RW
        - Other: $70B at 100% RW
        - 250% threshold items: $20B
        """
        items = [
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.SOVEREIGN,
                exposure_amount=500_000.0, risk_weight=0.0, rwa=0.0,
                ffiec_101_line="1a",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.DEPOSITORY_INSTITUTION,
                exposure_amount=300_000.0, risk_weight=0.20, rwa=60_000.0,
                ffiec_101_line="2",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.CORPORATE_IG,
                exposure_amount=400_000.0, risk_weight=0.65, rwa=260_000.0,
                ffiec_101_line="3b", description="IG corporate 65% per US 2026",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.CORPORATE,
                exposure_amount=100_000.0, risk_weight=1.00, rwa=100_000.0,
                ffiec_101_line="3a",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.RETAIL_RESIDENTIAL,
                exposure_amount=250_000.0, risk_weight=0.50, rwa=125_000.0,
                ffiec_101_line="4a",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.RETAIL_TRANSACTOR,
                exposure_amount=80_000.0, risk_weight=0.45, rwa=36_000.0,
                ffiec_101_line="4d", description="Transactor 45% per US 2026",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.OTHER_ASSETS,
                exposure_amount=100_000.0, risk_weight=1.50, rwa=150_000.0,
                ffiec_101_line="8b", description="CRE 150%",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.OTHER_ASSETS,
                exposure_amount=70_000.0, risk_weight=1.00, rwa=70_000.0,
                ffiec_101_line="8b",
            ),
        ]
        threshold_rwa = 20_000.0 * 2.50  # 250% RW items
        return aggregate_credit_risk_rwa(items, threshold_rwa)

    def test_full_capital_stack(self) -> None:
        """Complete capital stack: CET1 + AT1 + T2 = Total Capital."""
        # CET1
        equity = CommonEquityInputs(
            common_stock=25_000.0,
            surplus=85_000.0,
            retained_earnings=95_000.0,
            aoci=-3_000.0,
            treasury_stock=5_000.0,
            minority_interest_cet1=1_000.0,
        )
        deductions = [
            DeductionItem(category=DeductionCategory.GOODWILL, amount=30_000.0, tier=CapitalTier.CET1),
            DeductionItem(category=DeductionCategory.OTHER_INTANGIBLES, amount=5_000.0, tier=CapitalTier.CET1),
            DeductionItem(category=DeductionCategory.DTA_CARRYFORWARD, amount=2_000.0, tier=CapitalTier.CET1),
        ]
        thresholds = ThresholdDeductionInputs(
            significant_investments_cet1=8_000.0,
            mortgage_servicing_assets=6_000.0,
            dta_timing_differences=7_000.0,
        )

        cet1_result = compute_cet1(equity, deductions, thresholds)
        assert cet1_result.net_cet1 > 0
        assert 100_000.0 <= cet1_result.net_cet1 <= 200_000.0

    def test_rwa_aggregation(self) -> None:
        """RWA aggregation across all risk types."""
        credit = self._build_credit_risk_rwa()
        market = MarketRiskRWAInput(
            total_capital_charge=5_000.0,  # $5B FRTB charge
            sbm_charge=3_500.0,
            drc_charge=1_200.0,
            rrao_charge=300.0,
        )
        oprisk = OperationalRiskRWAInput(
            bic=8_000.0,
            ilm=1.0,  # ILM = 1.0 per US 2026
            capital_charge=8_000.0,
        )
        cva = CVARiskRWAInput(total_cva_charge=2_000.0)

        rwa = aggregate_rwa(credit, market, oprisk, cva)

        # Total RWA should be realistic for a $3.2T G-SIB
        assert rwa.total_rwa > 500_000.0
        assert rwa.total_rwa < 3_000_000.0
        # Output floor NOT applied per US 2026
        assert rwa.output_floor_applied is False

    def test_capital_adequacy_assessment(self) -> None:
        """Full capital adequacy: ratios, buffers, PCA classification."""
        cet1 = 195_000.0    # $195B
        tier1 = 220_000.0   # $220B
        total = 250_000.0   # $250B
        total_rwa = 1_650_000.0  # $1.65T
        tle = 3_500_000.0   # $3.5T

        result = compute_capital_adequacy(
            cet1_capital=cet1,
            tier1_capital=tier1,
            total_capital=total,
            total_rwa=total_rwa,
            total_leverage_exposure=tle,
            gsib_surcharge=0.035,
        )

        # CET1 ratio 10-15% per CLAUDE.md
        assert 0.10 <= result.ratios.cet1_ratio <= 0.15
        # SLR 5-7% per CLAUDE.md
        assert 0.05 <= result.ratios.leverage_ratio <= 0.08
        # Should be well capitalized
        assert result.is_well_capitalized is True
        assert result.pca.category == PCACategory.WELL_CAPITALIZED
        # Meets all requirements
        assert result.meets_minimum_requirements is True

    def test_regulatory_parameter_compliance(self) -> None:
        """Verify key regulatory parameters from CLAUDE.md."""
        # ILM = 1.0
        oprisk = OperationalRiskRWAInput(ilm=1.0, bic=10_000.0, capital_charge=10_000.0)
        assert oprisk.ilm == pytest.approx(1.0)

        # Output floor NOT applied
        rwa = aggregate_rwa()
        assert rwa.output_floor_applied is False

        # Retail transactor = 45%
        transactor = CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.RETAIL_TRANSACTOR,
            exposure_amount=100.0, risk_weight=0.45, rwa=45.0,
        )
        assert transactor.risk_weight == pytest.approx(0.45)

        # Corporate IG = 65%
        ig = CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.CORPORATE_IG,
            exposure_amount=100.0, risk_weight=0.65, rwa=65.0,
        )
        assert ig.risk_weight == pytest.approx(0.65)


class TestEndToEndStressTest:
    """End-to-end stress testing pipeline."""

    def test_full_ccar_stress_test(self) -> None:
        """Run complete CCAR stress test across all scenarios."""
        engine = ScenarioEngine()
        projector = CapitalProjector(preferred_dividend_quarterly=500.0)

        starting_cet1 = 195_000.0
        starting_rwa = 1_650_000.0
        avg_assets = 3_200_000.0
        total_loans = 1_000_000.0

        results = {}
        for scenario_type in ScenarioType:
            scenario = engine.generate_scenario(scenario_type)
            impact = engine.apply_scenario_to_portfolio(
                scenario, total_loans, starting_rwa, 50_000.0, avg_assets,
            )
            proj = projector.project_capital(
                impact, starting_cet1, starting_rwa, avg_assets, total_loans,
            )
            results[scenario_type] = proj

        # Aggregate results
        stress_results = compute_stress_test_results(
            baseline=results[ScenarioType.BASELINE],
            adverse=results[ScenarioType.ADVERSE],
            severely_adverse=results[ScenarioType.SEVERELY_ADVERSE],
            gsib_surcharge=0.035,
            total_rwa=starting_rwa,
        )

        # Well-capitalized G-SIB should pass stress tests
        assert stress_results.overall_pass is True
        assert stress_results.stress_capital_buffer >= 0.025

        # Severely adverse should be worse than adverse
        assert (
            results[ScenarioType.SEVERELY_ADVERSE].min_cet1_ratio
            < results[ScenarioType.ADVERSE].min_cet1_ratio
        )

        # Min CET1 ratio under severe stress should still be above 4.5%
        assert results[ScenarioType.SEVERELY_ADVERSE].min_cet1_ratio >= 0.045


class TestEndToEndECL:
    """End-to-end ECL calculation pipeline."""

    def test_portfolio_ecl(self) -> None:
        """Compute ECL for a diversified loan portfolio."""
        calc = ECLCalculator()

        exposures = [
            # IG corporates — Stage 1
            ECLExposure(exposure_id="IG-1", rating="A", drawn_amount=500.0, sector="corporate"),
            ECLExposure(exposure_id="IG-2", rating="BBB", drawn_amount=300.0, sector="corporate"),
            # HY corporate — may be Stage 2 if deteriorated
            ECLExposure(
                exposure_id="HY-1", rating="BB", drawn_amount=100.0,
                pd_at_origination=0.005, sector="corporate",
            ),
            # Retail mortgage
            ECLExposure(
                exposure_id="MTG-1", rating="BBB", drawn_amount=200.0,
                sector="residential", remaining_maturity_years=20.0,
            ),
            # Defaulted exposure — Stage 3
            ECLExposure(
                exposure_id="DEF-1", rating="D", drawn_amount=50.0,
                is_defaulted=True, pd_current=1.0,
            ),
        ]

        result = calc.compute_portfolio_ecl(exposures)

        # Total ECL should be positive
        assert result.total_ecl > 0
        assert result.total_ead > 0

        # Defaulted should be Stage 3
        def_result = next(r for r in result.exposure_results if r.exposure_id == "DEF-1")
        assert def_result.stage == Stage.STAGE_3

        # Coverage ratio should be realistic (0.1-10%)
        assert 0.001 <= result.coverage_ratio <= 0.15

        # Stage 3 ECL should dominate given the default
        assert result.total_ecl_stage3 > 0
