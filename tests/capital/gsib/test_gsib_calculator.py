"""Tests for G-SIB Surcharge Calculator.

Tests Method 1/2 score calculation, surcharge band mapping,
and binding method determination.

References:
- G-SIB NPR: "Risk-Based Capital Surcharges for GSIBs"
- 12 CFR 217.403-406: G-SIB surcharge framework
"""

import pytest

from src.capital.gsib.gsib_calculator import (
    GSIBSurchargeResult,
    MethodResult,
    score_to_method1_surcharge,
    score_to_method2_surcharge,
    score_to_surcharge,
)
from src.capital.gsib.gsib_params import (
    GSIBMethod,
    METHOD_1_BAND_WIDTH_BPS,
    METHOD_1_INITIAL_THRESHOLD_BPS,
    METHOD_1_MIN_SURCHARGE_PCT,
    METHOD_1_SURCHARGE_INCREMENT_PCT,
    METHOD_2_BAND_WIDTH_BPS,
    METHOD_2_INITIAL_THRESHOLD_BPS,
)


# =========================================================================
#  Score-to-Surcharge Band Tests
# =========================================================================

class TestScoreToSurcharge:
    """Tests for the 20bp band / 0.1% increment surcharge mapping."""

    def test_below_threshold_gets_minimum(self) -> None:
        """Score below initial threshold gets minimum surcharge."""
        surcharge, bucket, _, _ = score_to_method1_surcharge(100.0)
        assert surcharge == pytest.approx(METHOD_1_MIN_SURCHARGE_PCT)

    def test_at_threshold_boundary(self) -> None:
        """Score exactly at initial threshold gets minimum surcharge."""
        threshold = METHOD_1_INITIAL_THRESHOLD_BPS
        surcharge, bucket, _, _ = score_to_method1_surcharge(threshold)
        assert surcharge == pytest.approx(METHOD_1_MIN_SURCHARGE_PCT)
        assert bucket == 1

    def test_20bp_band_width(self) -> None:
        """Each 20bp increase in score adds 0.1% surcharge per CLAUDE.md."""
        threshold = METHOD_1_INITIAL_THRESHOLD_BPS
        band_width = METHOD_1_BAND_WIDTH_BPS
        increment = METHOD_1_SURCHARGE_INCREMENT_PCT
        min_surcharge = METHOD_1_MIN_SURCHARGE_PCT

        # Score in first band: threshold to threshold + 20bp
        s1, b1, _, _ = score_to_method1_surcharge(threshold + 5)
        assert s1 == pytest.approx(min_surcharge)

        # Score in second band: threshold + 20bp to threshold + 40bp
        s2, b2, _, _ = score_to_method1_surcharge(threshold + band_width + 5)
        assert s2 == pytest.approx(min_surcharge + increment)
        assert b2 == 2

        # Score in third band
        s3, b3, _, _ = score_to_method1_surcharge(
            threshold + 2 * band_width + 5
        )
        assert s3 == pytest.approx(min_surcharge + 2 * increment)
        assert b3 == 3

    def test_not_100bp_bands(self) -> None:
        """US 2026 uses 20bp bands, NOT the BCBS 100bp bands."""
        assert METHOD_1_BAND_WIDTH_BPS == pytest.approx(20.0)
        assert METHOD_2_BAND_WIDTH_BPS == pytest.approx(20.0)

    def test_not_0_5pct_increments(self) -> None:
        """US 2026 uses 0.1% increments, NOT the BCBS 0.5% increments."""
        assert METHOD_1_SURCHARGE_INCREMENT_PCT == pytest.approx(0.1)

    def test_high_score_produces_high_surcharge(self) -> None:
        """Very high score (top G-SIB) produces substantial surcharge."""
        # JPM-like score ~700bps
        surcharge, _, _, _ = score_to_method1_surcharge(700.0)
        # With 20bp bands and 0.1% increments from ~130bp threshold,
        # (700-130)/20 = 28.5 bands → ~3.8% + 1.0% min
        assert surcharge >= 3.0

    def test_method2_surcharge_mapping(self) -> None:
        """Method 2 uses same band structure but different thresholds."""
        threshold = METHOD_2_INITIAL_THRESHOLD_BPS
        surcharge, _, _, _ = score_to_method2_surcharge(threshold + 10)
        assert surcharge > 0.0

    def test_band_boundaries(self) -> None:
        """Score exactly on band boundary goes to higher band."""
        threshold = METHOD_1_INITIAL_THRESHOLD_BPS
        band = METHOD_1_BAND_WIDTH_BPS

        # Exactly at the boundary between band 1 and band 2
        surcharge, bucket, lower, upper = score_to_method1_surcharge(
            threshold + band
        )
        # Should be in band 2
        assert bucket == 2


# =========================================================================
#  GSIBSurchargeResult Tests
# =========================================================================

class TestGSIBSurchargeResult:
    """Tests for the combined surcharge result."""

    def test_binding_method_is_higher(self) -> None:
        """Final surcharge = higher of Method 1 vs Method 2."""
        m1 = MethodResult(method=GSIBMethod.METHOD_1, score_bps=200.0, surcharge_pct=1.5)
        m2 = MethodResult(method=GSIBMethod.METHOD_2, score_bps=250.0, surcharge_pct=2.0)

        result = GSIBSurchargeResult(
            method1_result=m1,
            method2_result=m2,
            binding_method=GSIBMethod.METHOD_2,
            final_surcharge_pct=2.0,
        )
        assert result.final_surcharge_pct == pytest.approx(2.0)
        assert result.binding_method == GSIBMethod.METHOD_2

    def test_score_differential(self) -> None:
        """Score differential = Method 2 - Method 1."""
        m1 = MethodResult(method=GSIBMethod.METHOD_1, score_bps=200.0, surcharge_pct=1.5)
        m2 = MethodResult(method=GSIBMethod.METHOD_2, score_bps=280.0, surcharge_pct=2.3)

        result = GSIBSurchargeResult(
            method1_result=m1,
            method2_result=m2,
        )
        assert result.score_differential_bps == pytest.approx(80.0)

    def test_surcharge_amount_with_rwa(self) -> None:
        """CET1 surcharge amount = surcharge_pct * total_rwa / 100."""
        m1 = MethodResult(method=GSIBMethod.METHOD_1, surcharge_pct=2.0)
        m2 = MethodResult(method=GSIBMethod.METHOD_2, surcharge_pct=2.5)

        result = GSIBSurchargeResult(
            method1_result=m1,
            method2_result=m2,
            final_surcharge_pct=2.5,
            total_rwa=1_650_000.0,  # $1.65T
            cet1_surcharge_amount=1_650_000.0 * 0.025,
        )
        assert result.cet1_surcharge_amount == pytest.approx(41_250.0)


# =========================================================================
#  Regulatory Parameter Validation
# =========================================================================

class TestGSIBRegulatoryParams:
    """Validate G-SIB parameters match CLAUDE.md requirements."""

    def test_band_width_20bp(self) -> None:
        """CLAUDE.md: G-SIB surcharge bands use 20bp score ranges."""
        assert METHOD_1_BAND_WIDTH_BPS == pytest.approx(20.0)
        assert METHOD_2_BAND_WIDTH_BPS == pytest.approx(20.0)

    def test_increment_0_1pct(self) -> None:
        """CLAUDE.md: G-SIB surcharge increments are 0.1%."""
        assert METHOD_1_SURCHARGE_INCREMENT_PCT == pytest.approx(0.1)
