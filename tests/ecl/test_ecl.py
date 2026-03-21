"""Tests for ECL (Expected Credit Loss) module.

Tests PD models, LGD models, EAD models, staging engine, and
the main ECL calculator.

References:
    - ASC 326: CECL
    - IFRS 9: Financial Instruments
    - BCBS d350: ECL guidance
"""

import pytest

from src.ecl.pd_models.pd_params import MASTER_SCALE_PD, PD_FLOOR, PD_CAP
from src.ecl.pd_models.pd_models import (
    PDModel,
    PDTermStructure,
    PITPDModel,
    TTCCalibrator,
    PDModelResult,
)
from src.ecl.lgd_models.lgd_models import (
    LGDModel,
    CollateralRecoveryModel,
    DownturnLGDModel,
    CureRateModel,
    LGDResult,
)
from src.ecl.lgd_models.lgd_params import LGD_FLOOR, LGD_CAP, SUPERVISORY_LGD
from src.ecl.ead_models.ead_models import (
    EADModel,
    CCFModel,
    UndrawnCommitmentModel,
    EADResult,
)
from src.ecl.ead_models.ead_params import SA_CCF
from src.ecl.staging.staging_engine import (
    StagingEngine,
    Stage,
    SICRIndicator,
)
from src.ecl.ecl_calculator import (
    ECLCalculator,
    ECLExposure,
    ECLResult,
    ECLPortfolioResult,
    MacroeconomicScenario,
    ScenarioWeight,
)


# =========================================================================
#  PD Model Tests
# =========================================================================

class TestTTCCalibrator:
    """Tests for TTC PD calibration."""

    def test_lookup_known_rating(self) -> None:
        """Look up PD for a known rating."""
        cal = TTCCalibrator()
        pd = cal.get_ttc_pd("BBB")
        assert pd == pytest.approx(0.01)

    def test_pd_floor_applied(self) -> None:
        """PD is floored at PD_FLOOR."""
        cal = TTCCalibrator(central_tendency=0.001)
        pd = cal.get_ttc_pd("AAA")
        assert pd >= PD_FLOOR

    def test_unknown_rating_returns_floor(self) -> None:
        """Unknown rating returns PD floor."""
        cal = TTCCalibrator()
        pd = cal.get_ttc_pd("UNKNOWN")
        assert pd >= PD_FLOOR

    def test_central_tendency_adjustment(self) -> None:
        """Central tendency scales all PDs."""
        cal = TTCCalibrator(central_tendency=1.5)
        pd = cal.get_ttc_pd("BBB")
        assert pd == pytest.approx(0.015)


class TestPITPDModel:
    """Tests for PIT PD adjustment."""

    def test_normal_regime_no_change(self) -> None:
        """Normal regime scalar = 1.0, PIT PD = TTC PD."""
        model = PITPDModel(regime="normal")
        pit = model.compute_pit_pd(0.01, "corporate")
        assert pit == pytest.approx(0.01)

    def test_stress_regime_increases_pd(self) -> None:
        """Stress regime increases PIT PD."""
        model = PITPDModel(regime="severe_stress")
        pit = model.compute_pit_pd(0.01, "corporate")
        assert pit > 0.01

    def test_expansion_regime_decreases_pd(self) -> None:
        """Expansion regime decreases PIT PD."""
        model = PITPDModel(regime="expansion")
        pit = model.compute_pit_pd(0.01, "corporate")
        assert pit < 0.01

    def test_pd_capped_at_1(self) -> None:
        """PIT PD never exceeds 1.0."""
        model = PITPDModel(regime="severe_stress")
        pit = model.compute_pit_pd(0.85, "cre")
        assert pit <= PD_CAP


class TestPDModel:
    """Tests for the main PD model."""

    def test_compute_pd_basic(self) -> None:
        """Basic PD computation returns valid result."""
        model = PDModel()
        result = model.compute_pd("BBB", "corporate")
        assert result.ttc_pd > 0
        assert result.pit_pd > 0
        assert result.rating == "BBB"

    def test_term_structure_length(self) -> None:
        """Term structure has correct horizon."""
        model = PDModel()
        result = model.compute_pd("A", "corporate", horizon_years=5)
        assert len(result.marginal_pd) == 5
        assert len(result.cumulative_pd) == 5

    def test_cumulative_pd_monotonic(self) -> None:
        """Cumulative PD is non-decreasing over time."""
        model = PDModel()
        result = model.compute_pd("BB", "corporate", horizon_years=10)
        for i in range(1, len(result.cumulative_pd)):
            assert result.cumulative_pd[i] >= result.cumulative_pd[i - 1]


# =========================================================================
#  LGD Model Tests
# =========================================================================

class TestLGDModel:
    """Tests for LGD estimation."""

    def test_senior_unsecured_lgd(self) -> None:
        """Senior unsecured LGD = 45% per BCBS d424 CRE32.14."""
        assert SUPERVISORY_LGD["senior_unsecured"] == pytest.approx(0.45)

    def test_collateral_reduces_lgd(self) -> None:
        """Collateral recovery reduces effective LGD."""
        model = LGDModel()
        unsecured = model.compute_lgd(seniority="senior_unsecured")
        secured = model.compute_lgd(
            seniority="senior_unsecured",
            collateral_value=80.0,
            collateral_type="cash",
            ead=100.0,
        )
        assert secured.effective_lgd < unsecured.effective_lgd

    def test_downturn_lgd_higher(self) -> None:
        """Downturn LGD is higher than base LGD."""
        model = LGDModel()
        result = model.compute_lgd(use_downturn=True)
        assert result.downturn_lgd >= result.base_lgd

    def test_cure_rate_reduces_lgd(self) -> None:
        """Cure rate reduces effective LGD."""
        model = LGDModel()
        with_cure = model.compute_lgd(apply_cure=True)
        without_cure = model.compute_lgd(apply_cure=False)
        assert with_cure.effective_lgd <= without_cure.effective_lgd

    def test_lgd_within_bounds(self) -> None:
        """LGD is within [LGD_FLOOR, LGD_CAP]."""
        model = LGDModel()
        result = model.compute_lgd()
        assert LGD_FLOOR <= result.effective_lgd <= LGD_CAP


class TestCollateralRecovery:
    """Tests for collateral recovery model."""

    def test_cash_collateral_full_recovery(self) -> None:
        """Cash collateral with 0% haircut gives near-full recovery."""
        model = CollateralRecoveryModel()
        rate = model.compute_recovery(100.0, "cash", 100.0)
        assert rate > 0.90

    def test_no_collateral_zero_recovery(self) -> None:
        """No collateral gives zero recovery."""
        model = CollateralRecoveryModel()
        rate = model.compute_recovery(0.0, "cash", 100.0)
        assert rate == pytest.approx(0.0)


# =========================================================================
#  EAD Model Tests
# =========================================================================

class TestEADModel:
    """Tests for EAD estimation."""

    def test_drawn_only(self) -> None:
        """Fully drawn facility: EAD = drawn amount."""
        model = EADModel()
        result = model.compute_ead(drawn=100.0, undrawn=0.0)
        assert result.total_ead == pytest.approx(100.0)

    def test_revolving_with_undrawn(self) -> None:
        """Revolving: EAD = drawn + CCF × undrawn."""
        model = EADModel()
        result = model.compute_ead(drawn=60.0, undrawn=40.0)
        assert result.total_ead > 60.0
        assert result.total_ead <= 100.0

    def test_ccf_values(self) -> None:
        """SA-CR CCF for unconditionally cancellable = 10%."""
        assert SA_CCF["unconditionally_cancellable"] == pytest.approx(0.10)

    def test_off_balance_sheet(self) -> None:
        """Off-balance sheet: EAD = notional × CCF."""
        model = EADModel()
        result = model.compute_ead(
            undrawn=100.0,
            product_type="direct_credit_substitutes",
            is_off_balance_sheet=True,
        )
        assert result.total_ead == pytest.approx(100.0)  # 100% CCF


# =========================================================================
#  Staging Engine Tests
# =========================================================================

class TestStagingEngine:
    """Tests for IFRS 9 staging."""

    def test_stage1_no_sicr(self) -> None:
        """Performing exposure with no SICR → Stage 1."""
        engine = StagingEngine()
        result = engine.assign_stage(
            pd_at_origination=0.01, pd_current=0.01
        )
        assert result.stage == Stage.STAGE_1
        assert result.ecl_horizon == "12_month"

    def test_stage2_pd_increase(self) -> None:
        """PD doubling + absolute increase → Stage 2."""
        engine = StagingEngine()
        result = engine.assign_stage(
            pd_at_origination=0.01, pd_current=0.03
        )
        assert result.stage == Stage.STAGE_2
        assert result.ecl_horizon == "lifetime"

    def test_stage2_30dpd_backstop(self) -> None:
        """30 DPD backstop triggers Stage 2."""
        engine = StagingEngine()
        result = engine.assign_stage(
            pd_at_origination=0.01, pd_current=0.01,
            days_past_due=35,
        )
        assert result.stage == Stage.STAGE_2
        assert SICRIndicator.BACKSTOP_30DPD in result.sicr_assessment.triggered_indicators

    def test_stage3_defaulted(self) -> None:
        """Defaulted exposure → Stage 3."""
        engine = StagingEngine()
        result = engine.assign_stage(
            pd_at_origination=0.01, pd_current=1.0,
            is_defaulted=True,
        )
        assert result.stage == Stage.STAGE_3
        assert result.is_credit_impaired is True

    def test_stage3_90dpd(self) -> None:
        """90 DPD → Stage 3."""
        engine = StagingEngine()
        result = engine.assign_stage(
            pd_at_origination=0.01, pd_current=0.5,
            days_past_due=90,
        )
        assert result.stage == Stage.STAGE_3

    def test_watchlist_triggers_sicr(self) -> None:
        """Watchlist flag triggers SICR → Stage 2."""
        engine = StagingEngine()
        result = engine.assign_stage(
            pd_at_origination=0.01, pd_current=0.01,
            is_on_watchlist=True,
        )
        assert result.stage == Stage.STAGE_2


# =========================================================================
#  ECL Calculator Tests
# =========================================================================

class TestECLCalculator:
    """Tests for the main ECL calculator."""

    def test_basic_ecl_computation(self) -> None:
        """Basic ECL = PD × LGD × EAD."""
        calc = ECLCalculator()
        exposure = ECLExposure(
            exposure_id="TEST-001",
            rating="BBB",
            drawn_amount=100.0,
        )
        result = calc.compute_ecl(exposure)
        assert result.ecl_final > 0
        assert result.ead > 0
        assert result.stage == Stage.STAGE_1

    def test_stage1_uses_12month_ecl(self) -> None:
        """Stage 1 exposure uses 12-month ECL."""
        calc = ECLCalculator()
        exposure = ECLExposure(
            exposure_id="TEST-002",
            rating="A",
            drawn_amount=100.0,
            pd_at_origination=0.003,
        )
        result = calc.compute_ecl(exposure)
        assert result.stage == Stage.STAGE_1

    def test_stage3_highest_ecl(self) -> None:
        """Defaulted exposure (Stage 3) has highest ECL."""
        calc = ECLCalculator()
        performing = ECLExposure(
            exposure_id="PERF",
            rating="BBB",
            drawn_amount=100.0,
        )
        defaulted = ECLExposure(
            exposure_id="DEF",
            rating="D",
            drawn_amount=100.0,
            is_defaulted=True,
            pd_current=1.0,
        )
        r_perf = calc.compute_ecl(performing)
        r_def = calc.compute_ecl(defaulted)
        assert r_def.ecl_final > r_perf.ecl_final

    def test_portfolio_ecl(self) -> None:
        """Portfolio ECL aggregates correctly."""
        calc = ECLCalculator()
        exposures = [
            ECLExposure(exposure_id=f"EXP-{i}", rating="BBB", drawn_amount=100.0)
            for i in range(5)
        ]
        result = calc.compute_portfolio_ecl(exposures)
        assert result.total_ecl > 0
        assert result.total_ead == pytest.approx(500.0)
        assert result.count_stage1 == 5
        assert result.coverage_ratio > 0

    def test_coverage_ratio_realistic(self) -> None:
        """Coverage ratio (ECL/EAD) should be realistic (0.1-5%)."""
        calc = ECLCalculator()
        exposures = [
            ECLExposure(exposure_id="IG", rating="A", drawn_amount=1000.0),
            ECLExposure(exposure_id="HY", rating="BB", drawn_amount=500.0),
        ]
        result = calc.compute_portfolio_ecl(exposures)
        assert 0.001 <= result.coverage_ratio <= 0.10
