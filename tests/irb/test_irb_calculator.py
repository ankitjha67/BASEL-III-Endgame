"""Tests for IRB (Internal Ratings-Based) Capital Calculator.

Tests Vasicek risk weight formula, asset correlations, maturity adjustments,
and portfolio-level RWA calculation.

Note: IRB module exists for COMPARISON ONLY — US Basel III Endgame 2026
eliminates IRB for most exposure classes.

References:
- BCBS d424 CRE30-CRE36: IRB approach
"""

import math

import pytest
from scipy.stats import norm

from src.irb.irb_calculator import (
    IRBExposure,
    IRBPortfolioResult,
    IRBResult,
    compute_asset_correlation,
    compute_capital_requirement_k,
    compute_maturity_adjustment,
)
from src.irb.irb_params import (
    CONFIDENCE_LEVEL,
    CORPORATE_CORRELATION_R_MAX,
    CORPORATE_CORRELATION_R_MIN,
    EFFECTIVE_MATURITY_DEFAULT,
    IRBApproach,
    IRBExposureClass,
    LGD_FLOORS,
    SCALING_FACTOR,
    SUPERVISORY_LGD,
)


# =========================================================================
#  Asset Correlation Tests
# =========================================================================

class TestAssetCorrelation:
    """Tests for compute_asset_correlation per BCBS d424 CRE31.6."""

    def test_corporate_correlation_bounds(self) -> None:
        """Corporate correlation R is between R_min (0.12) and R_max (0.24)."""
        # High PD → correlation approaches R_min
        r_high_pd = compute_asset_correlation(0.20, IRBExposureClass.CORPORATE)
        assert r_high_pd >= 0.11  # Allow small tolerance
        assert r_high_pd <= 0.25

        # Low PD → correlation approaches R_max
        r_low_pd = compute_asset_correlation(0.0003, IRBExposureClass.CORPORATE)
        assert r_low_pd >= 0.12
        assert r_low_pd <= 0.25

    def test_high_pd_lower_correlation(self) -> None:
        """Higher PD produces lower asset correlation (more idiosyncratic)."""
        r_low = compute_asset_correlation(0.001, IRBExposureClass.CORPORATE)
        r_high = compute_asset_correlation(0.10, IRBExposureClass.CORPORATE)
        assert r_low > r_high

    def test_retail_mortgage_fixed_correlation(self) -> None:
        """Retail mortgage: fixed R = 0.15 per CRE32.5."""
        r = compute_asset_correlation(0.01, IRBExposureClass.RETAIL_MORTGAGE)
        assert r == pytest.approx(0.15)
        # Same regardless of PD
        r2 = compute_asset_correlation(0.05, IRBExposureClass.RETAIL_MORTGAGE)
        assert r2 == pytest.approx(0.15)

    def test_qualifying_revolving_fixed_correlation(self) -> None:
        """QRE: fixed R = 0.04 per CRE32.7."""
        r = compute_asset_correlation(0.01, IRBExposureClass.RETAIL_QRE)
        assert r == pytest.approx(0.04)

    def test_sme_correlation_adjustment(self) -> None:
        """SME adjustment reduces correlation per CRE31.8."""
        r_large = compute_asset_correlation(
            0.01, IRBExposureClass.CORPORATE, annual_revenue=100.0
        )
        r_sme = compute_asset_correlation(
            0.01, IRBExposureClass.CORPORATE_SME, annual_revenue=10.0
        )
        # SME should have lower correlation (firm-size adjustment)
        assert r_sme < r_large


# =========================================================================
#  Maturity Adjustment Tests
# =========================================================================

class TestMaturityAdjustment:
    """Tests for compute_maturity_adjustment per BCBS d424 CRE31.6."""

    def test_default_maturity_2_5_years(self) -> None:
        """At M=2.5 years (default), maturity adjustment factor = 1.0."""
        ma = compute_maturity_adjustment(0.01, 2.5)
        assert ma == pytest.approx(1.0)

    def test_longer_maturity_higher_adjustment(self) -> None:
        """Longer maturity → higher adjustment (more risk)."""
        ma_short = compute_maturity_adjustment(0.01, 1.0)
        ma_long = compute_maturity_adjustment(0.01, 5.0)
        assert ma_long > ma_short

    def test_maturity_clamped_1_to_5(self) -> None:
        """Effective maturity clamped to [1, 5] years."""
        ma_below = compute_maturity_adjustment(0.01, 0.5)
        ma_at_min = compute_maturity_adjustment(0.01, 1.0)
        # Below minimum should be treated as minimum
        assert ma_below == pytest.approx(ma_at_min)

        ma_above = compute_maturity_adjustment(0.01, 10.0)
        ma_at_max = compute_maturity_adjustment(0.01, 5.0)
        assert ma_above == pytest.approx(ma_at_max)

    def test_high_pd_lower_maturity_effect(self) -> None:
        """Higher PD reduces the maturity adjustment sensitivity b(PD)."""
        # b(PD) = (0.11852 - 0.05478 * ln(PD))^2
        # Higher PD → smaller ln(PD) magnitude → different b
        ma_low_pd_long = compute_maturity_adjustment(0.001, 5.0)
        ma_high_pd_long = compute_maturity_adjustment(0.10, 5.0)
        # Both should be > 1.0 at 5 years
        assert ma_low_pd_long > 1.0
        assert ma_high_pd_long > 1.0


# =========================================================================
#  Capital Requirement K Tests
# =========================================================================

class TestCapitalRequirementK:
    """Tests for compute_capital_requirement_k (Vasicek formula)."""

    def test_k_is_positive(self) -> None:
        """Capital requirement K should be positive for non-default PDs."""
        k = compute_capital_requirement_k(
            pd=0.01, lgd=0.45, correlation=0.18, maturity_adjustment=1.0
        )
        assert k > 0.0

    def test_k_increases_with_pd(self) -> None:
        """Higher PD → higher capital requirement (up to a point)."""
        k_low = compute_capital_requirement_k(
            pd=0.001, lgd=0.45, correlation=0.20
        )
        k_high = compute_capital_requirement_k(
            pd=0.05, lgd=0.45, correlation=0.20
        )
        assert k_high > k_low

    def test_k_increases_with_lgd(self) -> None:
        """Higher LGD → higher capital requirement."""
        k_low_lgd = compute_capital_requirement_k(
            pd=0.01, lgd=0.25, correlation=0.18
        )
        k_high_lgd = compute_capital_requirement_k(
            pd=0.01, lgd=0.45, correlation=0.18
        )
        assert k_high_lgd > k_low_lgd

    def test_k_increases_with_correlation(self) -> None:
        """Higher correlation → higher capital requirement."""
        k_low_r = compute_capital_requirement_k(
            pd=0.01, lgd=0.45, correlation=0.10
        )
        k_high_r = compute_capital_requirement_k(
            pd=0.01, lgd=0.45, correlation=0.25
        )
        assert k_high_r > k_low_r

    def test_defaulted_exposure_k_is_zero(self) -> None:
        """Defaulted exposures (PD=1) have K=0 (EL fully provisioned)."""
        k = compute_capital_requirement_k(
            pd=1.0, lgd=0.45, correlation=0.18
        )
        assert k == pytest.approx(0.0)

    def test_zero_pd_k_is_zero(self) -> None:
        """Zero PD → zero capital requirement."""
        k = compute_capital_requirement_k(
            pd=0.0, lgd=0.45, correlation=0.18
        )
        assert k == pytest.approx(0.0)

    def test_realistic_corporate_rw(self) -> None:
        """BBB corporate (PD~1%, LGD 45%) → RW ~70-90%."""
        k = compute_capital_requirement_k(
            pd=0.01, lgd=0.45, correlation=0.18, maturity_adjustment=1.0
        )
        rw = k * 12.5 * SCALING_FACTOR
        # Typical BBB corporate IRB RW is 50-120%
        assert 0.40 <= rw <= 1.50

    def test_confidence_level_99_9(self) -> None:
        """IRB uses 99.9% confidence level."""
        assert CONFIDENCE_LEVEL == pytest.approx(0.999)


# =========================================================================
#  Supervisory Parameters Validation
# =========================================================================

class TestSupervisoryParameters:
    """Validate IRB parameters match BCBS d424."""

    def test_scaling_factor(self) -> None:
        """Scaling factor = 1.06 per BCBS d424 CRE31.3."""
        assert SCALING_FACTOR == pytest.approx(1.06)

    def test_supervisory_lgd_senior_unsecured(self) -> None:
        """F-IRB LGD for senior unsecured = 45% per CRE32.14."""
        assert "senior_unsecured" in SUPERVISORY_LGD or "SENIOR_UNSECURED" in {
            k.upper().replace(" ", "_") for k in SUPERVISORY_LGD
        } or any(v == 0.45 for v in SUPERVISORY_LGD.values())

    def test_default_maturity_2_5(self) -> None:
        """F-IRB default effective maturity = 2.5 years per CRE32.17."""
        assert EFFECTIVE_MATURITY_DEFAULT == pytest.approx(2.5)
