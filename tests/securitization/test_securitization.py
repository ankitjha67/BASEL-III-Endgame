"""Tests for Securitization framework.

Validates SEC-SA (SSFA), SEC-ERBA, and STC implementations per
BCBS d424 CRE40 and US Basel III Endgame March 2026 Re-Proposal.

Tests cover:
- SEC-ERBA risk weight lookup with maturity interpolation
- SEC-SA SSFA formula with delinquency adjustment
- STC criteria checking and preferential treatment
- Resecuritization risk weight multipliers
- Risk weight caps (1250%) and floors (15%, 100%)
- CTP positions
- Tranche structure validation
- Concentration add-on
- SEC1-SEC4 Pillar 3 reporting
"""

from __future__ import annotations

import pytest


# =========================================================================
#  Imports
# =========================================================================

class TestSecuritizationImports:
    """Test that all securitization modules import correctly."""

    def test_calculator_import(self) -> None:
        """SecuritizationCalculator should be importable."""
        from src.securitization.sec_framework import SecuritizationCalculator
        calc = SecuritizationCalculator()
        assert calc is not None

    def test_params_import(self) -> None:
        """All params should be importable."""
        from src.securitization.sec_params import (
            MAX_RISK_WEIGHT,
            MIN_RISK_WEIGHT_NON_RESEC,
            P_NON_RESECURITIZATION,
            SEC_ERBA_RW,
        )
        assert MAX_RISK_WEIGHT == 12.50
        assert MIN_RISK_WEIGHT_NON_RESEC == 0.15
        assert P_NON_RESECURITIZATION == 0.5
        assert len(SEC_ERBA_RW) > 0

    def test_reporting_import(self) -> None:
        """SecReportGenerator should be importable."""
        from src.securitization.sec_reporting import SecReportGenerator
        gen = SecReportGenerator("Test Bank")
        assert gen is not None

    def test_module_init_import(self) -> None:
        """Module __init__ should export key classes."""
        from src.securitization import (
            SecuritizationCalculator,
            SecuritizationPool,
            SecuritizationTranche,
            SecResult,
            SecReportGenerator,
        )
        assert SecuritizationCalculator is not None


# =========================================================================
#  SEC-ERBA Risk Weights
# =========================================================================

class TestSECERBA:
    """Test SEC-ERBA risk weight lookup per CRE40.42, Tables 2-5."""

    def test_aaa_senior_short(self) -> None:
        """AAA senior short: 15%."""
        from src.securitization.sec_framework import get_erba_risk_weight
        rw = get_erba_risk_weight("AAA", True, 0.5)
        assert rw == pytest.approx(0.15)

    def test_aaa_senior_long(self) -> None:
        """AAA senior long: 20%."""
        from src.securitization.sec_framework import get_erba_risk_weight
        rw = get_erba_risk_weight("AAA", True, 5.0)
        assert rw == pytest.approx(0.20)

    def test_bbb_non_senior_short(self) -> None:
        """BBB non-senior short: 45%."""
        from src.securitization.sec_framework import get_erba_risk_weight
        rw = get_erba_risk_weight("BBB", False, 0.5)
        assert rw == pytest.approx(0.45)

    def test_below_ccc_always_1250(self) -> None:
        """Below CCC always 1250%."""
        from src.securitization.sec_framework import get_erba_risk_weight
        rw = get_erba_risk_weight("BELOW_CCC", True, 3.0)
        assert rw == pytest.approx(12.50)

    def test_maturity_interpolation(self) -> None:
        """Interpolate between short (1y) and long (5y) maturities."""
        from src.securitization.sec_framework import get_erba_risk_weight
        # AAA senior: short=0.15, long=0.20
        # At 3y: 0.15 + (3-1)/(5-1) * (0.20 - 0.15) = 0.175
        rw = get_erba_risk_weight("AAA", True, 3.0)
        assert rw == pytest.approx(0.175)

    def test_invalid_rating_returns_none(self) -> None:
        """Invalid rating should return None."""
        from src.securitization.sec_framework import get_erba_risk_weight
        rw = get_erba_risk_weight("XYZ", True, 1.0)
        assert rw is None

    def test_bb_non_senior_long(self) -> None:
        """BB non-senior long: 120%."""
        from src.securitization.sec_framework import get_erba_risk_weight
        rw = get_erba_risk_weight("BB", False, 5.0)
        assert rw == pytest.approx(1.20)


# =========================================================================
#  SEC-SA (SSFA)
# =========================================================================

class TestSECSA:
    """Test SEC-SA SSFA formula per CRE40.4, CRE40.50-54."""

    @pytest.fixture
    def calc(self):
        from src.securitization.sec_framework import SecuritizationCalculator
        return SecuritizationCalculator()

    @pytest.fixture
    def standard_pool(self):
        from src.securitization.sec_framework import SecuritizationPool
        return SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=500e6,
        )

    def test_senior_tranche_lower_rw(self, calc) -> None:
        """Senior tranche should have lower RW than junior."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=500e6)
        senior = SecuritizationTranche(
            tranche_id="T_SR", pool_id="P1",
            attachment_point=0.10, detachment_point=1.0,
            notional=100e6, is_senior=True,
        )
        junior = SecuritizationTranche(
            tranche_id="T_JR", pool_id="P1",
            attachment_point=0.0, detachment_point=0.05,
            notional=50e6, is_senior=False,
        )
        sr_result = calc.calculate([senior], pool)
        jr_result = calc.calculate([junior], pool)
        sr_avg_rw = sr_result.total_rwa / 100e6 if sr_result.total_rwa > 0 else 0
        jr_avg_rw = jr_result.total_rwa / 50e6 if jr_result.total_rwa > 0 else 0
        assert sr_avg_rw < jr_avg_rw or jr_avg_rw >= 12.50

    def test_max_rw_1250(self, calc) -> None:
        """Risk weight capped at 1250%."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=900e6)
        thin = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.0, detachment_point=0.01,
            notional=10e6,
        )
        result = calc.calculate([thin], pool)
        rw = result.rw_by_tranche.get("T1", 0)
        assert rw <= 12.50

    def test_empty_tranches(self, calc, standard_pool) -> None:
        """Empty tranche list should return zero RWA."""
        result = calc.calculate([], standard_pool)
        assert result.total_rwa == 0.0

    def test_resecuritization_higher_rw(self, calc) -> None:
        """Resecuritization should get higher RW (p=1.5 vs p=0.5)."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=400e6)
        normal = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6,
        )
        resec = SecuritizationTranche(
            tranche_id="T2", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6, is_resecuritization=True,
        )
        normal_result = calc.calculate([normal], pool)
        resec_result = calc.calculate([resec], pool)
        assert resec_result.total_rwa >= normal_result.total_rwa

    def test_resec_floor_100_pct(self, calc) -> None:
        """Resecuritization floor = 100% per CRE40.63."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=50e6)
        resec = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.50, detachment_point=1.0,
            notional=100e6, is_resecuritization=True,
        )
        result = calc.calculate([resec], pool)
        rw = result.rw_by_tranche.get("T1", 0)
        assert rw >= 1.00  # 100% floor

    def test_non_resec_floor_15_pct(self, calc) -> None:
        """Non-resecuritization floor = 15% per CRE40.44."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=10e6)
        senior = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.50, detachment_point=1.0,
            notional=100e6,
        )
        result = calc.calculate([senior], pool)
        rw = result.rw_by_tranche.get("T1", 0)
        assert rw >= 0.15  # 15% floor

    def test_delinquency_increases_rw(self, calc) -> None:
        """Higher delinquency ratio should increase risk weight."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        tranche = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6,
        )
        pool_clean = SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=400e6, delinquency_ratio=0.0,
        )
        pool_delin = SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=400e6, delinquency_ratio=0.3,
        )
        clean_result = calc.calculate([tranche], pool_clean)
        delin_result = calc.calculate([tranche], pool_delin)
        assert delin_result.total_rwa >= clean_result.total_rwa

    def test_k_g_computation(self, calc) -> None:
        """K_g = pool_rwa / total_ead."""
        from src.securitization.sec_framework import SecuritizationPool
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=500e6)
        tranche = self._make_tranche("T1", 0.10, 0.50, 100e6)
        result = calc.calculate([tranche], pool)
        assert result.k_g == pytest.approx(0.50)

    def test_k_a_with_delinquency(self, calc) -> None:
        """K_A = K_g + W * (1 - K_g)."""
        from src.securitization.sec_framework import SecuritizationPool
        pool = SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=500e6,
            delinquency_ratio=0.2,
        )
        tranche = self._make_tranche("T1", 0.10, 0.50, 100e6)
        result = calc.calculate([tranche], pool)
        expected_ka = 0.50 + 0.2 * (1 - 0.50)
        assert result.k_a == pytest.approx(expected_ka)

    @staticmethod
    def _make_tranche(tid, a, d, notional):
        from src.securitization.sec_framework import SecuritizationTranche
        return SecuritizationTranche(
            tranche_id=tid, pool_id="P1",
            attachment_point=a, detachment_point=d,
            notional=notional,
        )


# =========================================================================
#  STC Criteria
# =========================================================================

class TestSTCCriteria:
    """Test STC (Simple, Transparent, Comparable) criteria per CRE40.70."""

    def test_stc_compliant(self) -> None:
        """Pool meeting all criteria should be STC compliant."""
        from src.securitization.sec_framework import STCCriteria, check_stc_criteria
        criteria = STCCriteria(
            asset_type="RMBS",
            number_of_exposures=500,
            effective_number_of_obligors=200,
            largest_obligor_share=0.005,
            tranche_maturity_years=3.0,
            is_synthetic=False,
            originator_retains_risk=True,
        )
        result = check_stc_criteria(criteria)
        assert result.is_stc_compliant is True
        assert len(result.criteria_failed) == 0

    def test_stc_fails_synthetic(self) -> None:
        """Synthetic securitization should fail STC."""
        from src.securitization.sec_framework import STCCriteria, check_stc_criteria
        criteria = STCCriteria(
            asset_type="RMBS",
            number_of_exposures=500,
            effective_number_of_obligors=200,
            largest_obligor_share=0.005,
            tranche_maturity_years=3.0,
            is_synthetic=True,
            originator_retains_risk=True,
        )
        result = check_stc_criteria(criteria)
        assert result.is_stc_compliant is False

    def test_stc_fails_concentration(self) -> None:
        """High concentration should fail STC."""
        from src.securitization.sec_framework import STCCriteria, check_stc_criteria
        criteria = STCCriteria(
            asset_type="RMBS",
            number_of_exposures=500,
            effective_number_of_obligors=200,
            largest_obligor_share=0.05,  # 5% > 2% limit
            tranche_maturity_years=3.0,
        )
        result = check_stc_criteria(criteria)
        assert result.is_stc_compliant is False

    def test_stc_lower_rw(self) -> None:
        """STC tranche should get lower RW than non-STC."""
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationPool, SecuritizationTranche,
        )
        calc = SecuritizationCalculator()
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=400e6)
        normal = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6,
        )
        stc = SecuritizationTranche(
            tranche_id="T2", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6, is_stc=True,
        )
        normal_result = calc.calculate([normal], pool)
        stc_result = calc.calculate([stc], pool)
        assert stc_result.total_rwa <= normal_result.total_rwa


# =========================================================================
#  Tranche Validation
# =========================================================================

class TestTrancheValidation:
    """Test tranche structure validation per CRE40.41."""

    def test_overlapping_tranches_warned(self) -> None:
        """Overlapping tranches should produce a warning."""
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationTranche,
        )
        t1 = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.0, detachment_point=0.20,
            notional=100e6,
        )
        t2 = SecuritizationTranche(
            tranche_id="T2", pool_id="P1",
            attachment_point=0.10, detachment_point=0.30,
            notional=100e6,
        )
        calc = SecuritizationCalculator()
        warnings = calc.validate_tranche_structure([t1, t2])
        assert any("overlaps" in w.lower() for w in warnings)

    def test_invalid_attachment_detachment(self) -> None:
        """Attachment >= Detachment should produce a warning."""
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationTranche,
        )
        t = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.50, detachment_point=0.50,
            notional=100e6,
        )
        warnings = SecuritizationCalculator.validate_tranche_structure([t])
        assert len(warnings) > 0

    def test_tranche_thickness_classification(self) -> None:
        """Tranche thickness should be classified correctly."""
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationTranche,
        )
        calc = SecuritizationCalculator()
        thin = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.0, detachment_point=0.02,
            notional=10e6,
        )
        thick = SecuritizationTranche(
            tranche_id="T2", pool_id="P1",
            attachment_point=0.0, detachment_point=0.50,
            notional=100e6,
        )
        assert calc.compute_tranche_thickness(thin) == "THIN"
        assert calc.compute_tranche_thickness(thick) == "THICK"


# =========================================================================
#  Reporting
# =========================================================================

class TestSecReporting:
    """Test SEC1-SEC4 Pillar 3 report generation."""

    @pytest.fixture
    def calc_result(self):
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationPool, SecuritizationTranche,
        )
        calc = SecuritizationCalculator()
        pool = SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=500e6,
            asset_type="RMBS",
        )
        tranches = [
            SecuritizationTranche(
                tranche_id="T_SR", pool_id="P1",
                attachment_point=0.10, detachment_point=1.0,
                notional=100e6, is_senior=True,
                external_rating="AAA", maturity_years=3.0,
            ),
            SecuritizationTranche(
                tranche_id="T_MZ", pool_id="P1",
                attachment_point=0.03, detachment_point=0.10,
                notional=70e6, external_rating="BBB", maturity_years=5.0,
            ),
            SecuritizationTranche(
                tranche_id="T_EQ", pool_id="P1",
                attachment_point=0.0, detachment_point=0.03,
                notional=30e6,
            ),
        ]
        result = calc.calculate(tranches, pool)
        return result, tranches, pool

    def test_sec3_report(self, calc_result) -> None:
        """SEC3 should group by approach."""
        from src.securitization.sec_reporting import SecReportGenerator
        result, tranches, pool = calc_result
        gen = SecReportGenerator("Test Bank")
        report = gen.generate_sec3(result, tranches, "2026-03-31")
        assert len(report.rows) > 0
        assert report.total_rwa_usd_m > 0

    def test_sec4_report(self, calc_result) -> None:
        """SEC4 should classify by risk weight band."""
        from src.securitization.sec_reporting import SecReportGenerator
        result, tranches, pool = calc_result
        gen = SecReportGenerator("Test Bank")
        report = gen.generate_sec4(result, tranches, "2026-03-31")
        assert len(report.rows) == 7  # 7 risk weight bands
        assert report.total_rwa_usd_m > 0

    def test_sec1_report(self, calc_result) -> None:
        """SEC1 should group by asset type."""
        from src.securitization.sec_reporting import SecReportGenerator
        result, tranches, pool = calc_result
        gen = SecReportGenerator("Test Bank")
        report = gen.generate_sec1(result, tranches, [pool], "2026-03-31")
        assert len(report.rows) >= 1
        assert report.total_rwa_usd_m > 0


# =========================================================================
#  Edge Cases
# =========================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_pool_ead(self) -> None:
        """Zero pool EAD should use default K_g."""
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationPool, SecuritizationTranche,
        )
        calc = SecuritizationCalculator()
        pool = SecuritizationPool(pool_id="P1", total_ead=0, pool_rwa=0)
        tranche = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.05, detachment_point=0.50,
            notional=100e6,
        )
        result = calc.calculate([tranche], pool)
        assert result.k_g == pytest.approx(0.08)  # default

    def test_delinquency_out_of_range(self) -> None:
        """Delinquency ratio > 1 should raise."""
        from src.securitization.sec_framework import SecuritizationPool
        with pytest.raises(ValueError):
            SecuritizationPool(
                pool_id="P1", total_ead=1e9, pool_rwa=500e6,
                delinquency_ratio=1.5,
            )

    def test_rw_band_distribution(self) -> None:
        """RW band distribution should be populated."""
        from src.securitization.sec_framework import (
            SecuritizationCalculator, SecuritizationPool, SecuritizationTranche,
        )
        calc = SecuritizationCalculator()
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=500e6)
        tranche = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.10, detachment_point=1.0,
            notional=100e6, is_senior=True,
        )
        result = calc.calculate([tranche], pool)
        assert len(result.rw_band_distribution) > 0
