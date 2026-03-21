"""Comprehensive test suite for GIRR (General Interest Rate Risk) calculator.

Tests cover:
- Regulatory parameter validation
- Correlation calculations
- Delta risk charge computation
- Vega risk charge computation
- Curvature risk charge computation
- Correlation scenario comparisons
- Multi-currency inter-bucket aggregation
- Integration tests with realistic portfolios
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.enums import (
    CorrelationScenario,
    CurrencyCategory,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.models import (
    BucketResult,
    GIRRResult,
    RiskChargeResult,
    Sensitivity,
    WeightedSensitivity,
)
from src.market_risk.frtb.sbm.girr import GIRRCalculator
from src.market_risk.frtb.sbm.girr_params import (
    CORRELATION_FLOOR,
    DELTA_RISK_WEIGHTS,
    GAMMA_GIRR,
    HIGH_VOLATILITY_MULTIPLIER,
    LOW_VOLATILITY_CURRENCIES,
    RHO_INFLATION,
    RHO_XCCY_BASIS,
    RW_INFLATION,
    RW_XCCY_BASIS,
    TENORS,
    THETA,
    VEGA_RISK_WEIGHT,
    apply_correlation_scenario,
    compute_tenor_correlation,
    get_currency_category,
    get_delta_risk_weight,
)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _delta_sens(
    bucket: str = "USD",
    tenor: GIRRTenor = GIRRTenor.Y10,
    value: float = 1_000_000.0,
    label: str = "OIS",
    rf_type: GIRRRiskFactorType = GIRRRiskFactorType.YIELD_CURVE,
) -> Sensitivity:
    """Shortcut to build a GIRR delta sensitivity."""
    return Sensitivity(
        risk_class=RiskClass.GIRR,
        risk_measure=RiskMeasure.DELTA,
        bucket=bucket,
        risk_factor_type=rf_type,
        tenor=tenor if rf_type == GIRRRiskFactorType.YIELD_CURVE else None,
        label=label,
        value=value,
    )


def _vega_sens(
    bucket: str = "USD",
    tenor: GIRRTenor = GIRRTenor.Y10,
    value: float = 100_000.0,
    option_maturity: float = 1.0,
    label: str = "OIS",
) -> Sensitivity:
    """Shortcut to build a GIRR vega sensitivity."""
    return Sensitivity(
        risk_class=RiskClass.GIRR,
        risk_measure=RiskMeasure.VEGA,
        bucket=bucket,
        risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
        tenor=tenor,
        label=label,
        value=value,
        option_maturity=option_maturity,
    )


def _curvature_sens(
    bucket: str = "USD",
    tenor: GIRRTenor = GIRRTenor.Y10,
    value: float = 50_000.0,
    label: str = "OIS",
) -> Sensitivity:
    """Shortcut to build a GIRR curvature sensitivity."""
    return Sensitivity(
        risk_class=RiskClass.GIRR,
        risk_measure=RiskMeasure.CURVATURE,
        bucket=bucket,
        risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
        tenor=tenor,
        label=label,
        value=value,
    )


# =========================================================================
#  1. GIRR Parameters Tests
# =========================================================================

class TestGIRRParams:
    """Tests for regulatory parameter constants and helper functions."""

    def test_tenor_count(self) -> None:
        """12 standard tenors per MAR21.8."""
        assert len(TENORS) == 12

    def test_tenor_values(self) -> None:
        expected = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 25.0, 30.0]
        assert TENORS == expected

    def test_delta_risk_weights_values(self) -> None:
        """Verify exact risk weights per MAR21.9 Table 1."""
        assert DELTA_RISK_WEIGHTS[0.25] == 0.017
        assert DELTA_RISK_WEIGHTS[0.5] == 0.017
        assert DELTA_RISK_WEIGHTS[1.0] == 0.016
        assert DELTA_RISK_WEIGHTS[2.0] == 0.013
        assert DELTA_RISK_WEIGHTS[3.0] == 0.012
        assert DELTA_RISK_WEIGHTS[5.0] == 0.011
        assert DELTA_RISK_WEIGHTS[30.0] == 0.011

    def test_all_tenors_have_risk_weights(self) -> None:
        for t in TENORS:
            assert t in DELTA_RISK_WEIGHTS

    def test_high_volatility_multiplier(self) -> None:
        assert abs(HIGH_VOLATILITY_MULTIPLIER - math.sqrt(2)) < 1e-10

    def test_low_volatility_currencies(self) -> None:
        for ccy in ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "SEK"]:
            assert ccy in LOW_VOLATILITY_CURRENCIES

    def test_currency_category_low_vol(self) -> None:
        assert get_currency_category("USD") == CurrencyCategory.LOW_VOLATILITY
        assert get_currency_category("EUR") == CurrencyCategory.LOW_VOLATILITY
        assert get_currency_category("usd") == CurrencyCategory.LOW_VOLATILITY

    def test_currency_category_high_vol(self) -> None:
        assert get_currency_category("BRL") == CurrencyCategory.HIGH_VOLATILITY
        assert get_currency_category("TRY") == CurrencyCategory.HIGH_VOLATILITY
        assert get_currency_category("ZAR") == CurrencyCategory.HIGH_VOLATILITY
        assert get_currency_category("INR") == CurrencyCategory.HIGH_VOLATILITY

    def test_risk_weight_low_vol(self) -> None:
        rw = get_delta_risk_weight(0.25, "USD")
        assert rw == 0.017

    def test_risk_weight_high_vol(self) -> None:
        rw = get_delta_risk_weight(0.25, "BRL")
        assert abs(rw - 0.017 * math.sqrt(2)) < 1e-10

    def test_risk_weight_invalid_tenor(self) -> None:
        with pytest.raises(KeyError):
            get_delta_risk_weight(4.0, "USD")

    def test_inflation_risk_weight(self) -> None:
        assert RW_INFLATION == 0.016

    def test_xccy_basis_risk_weight(self) -> None:
        assert RW_XCCY_BASIS == 0.016

    def test_inter_bucket_correlation(self) -> None:
        assert GAMMA_GIRR == 0.50

    def test_vega_risk_weight(self) -> None:
        assert VEGA_RISK_WEIGHT == 1.0


# =========================================================================
#  2. Correlation Tests
# =========================================================================

class TestCorrelations:
    """Tests for tenor correlation and scenario adjustments."""

    def test_same_tenor_correlation(self) -> None:
        assert compute_tenor_correlation(1.0, 1.0) == 1.0

    def test_adjacent_tenor_1y_2y(self) -> None:
        """exp(-0.03 * |1-2|/min(1,2)) = exp(-0.03) ≈ 0.9704."""
        rho = compute_tenor_correlation(1.0, 2.0)
        expected = math.exp(-0.03 * 1.0)
        assert abs(rho - expected) < 1e-6

    def test_1y_10y_correlation(self) -> None:
        """exp(-0.03 * 9/1) = exp(-0.27) ≈ 0.7634."""
        rho = compute_tenor_correlation(1.0, 10.0)
        expected = math.exp(-0.03 * 9.0)
        assert abs(rho - expected) < 1e-6

    def test_10y_30y_correlation(self) -> None:
        """exp(-0.03 * 20/10) = exp(-0.06) ≈ 0.9418."""
        rho = compute_tenor_correlation(10.0, 30.0)
        expected = math.exp(-0.03 * 2.0)
        assert abs(rho - expected) < 1e-6

    def test_distant_tenor_hits_floor(self) -> None:
        """0.25Y to 30Y: exp(-0.03 * 119) = exp(-3.57) ≈ 0.028 → floored to 0.40."""
        rho = compute_tenor_correlation(0.25, 30.0)
        assert rho == CORRELATION_FLOOR

    def test_correlation_symmetry(self) -> None:
        assert compute_tenor_correlation(2.0, 10.0) == compute_tenor_correlation(10.0, 2.0)

    def test_correlation_range(self) -> None:
        """All tenor correlations must be in [0.40, 1.0]."""
        for t1 in TENORS:
            for t2 in TENORS:
                rho = compute_tenor_correlation(t1, t2)
                assert 0.40 <= rho <= 1.0

    def test_scenario_medium_no_change(self) -> None:
        assert apply_correlation_scenario(0.5, CorrelationScenario.MEDIUM) == 0.5

    def test_scenario_high(self) -> None:
        rho = apply_correlation_scenario(0.5, CorrelationScenario.HIGH)
        assert abs(rho - 0.625) < 1e-10  # min(1.0, 1.25 * 0.5)

    def test_scenario_low(self) -> None:
        rho = apply_correlation_scenario(0.5, CorrelationScenario.LOW)
        # max(2*0.5 - 1, 0.75*0.5) = max(0.0, 0.375) = 0.375
        assert abs(rho - 0.375) < 1e-10

    def test_scenario_high_cap_at_one(self) -> None:
        rho = apply_correlation_scenario(0.95, CorrelationScenario.HIGH)
        assert rho == 1.0  # min(1.0, 1.1875) → 1.0

    def test_scenario_low_uses_max_formula(self) -> None:
        """For rho=0.8: max(2*0.8-1, 0.75*0.8) = max(0.6, 0.6) = 0.6."""
        rho = apply_correlation_scenario(0.8, CorrelationScenario.LOW)
        assert abs(rho - 0.6) < 1e-10

    def test_scenario_low_high_rho(self) -> None:
        """For rho=0.9: max(2*0.9-1, 0.75*0.9) = max(0.8, 0.675) = 0.8."""
        rho = apply_correlation_scenario(0.9, CorrelationScenario.LOW)
        assert abs(rho - 0.8) < 1e-10


# =========================================================================
#  3. Delta Calculation Tests
# =========================================================================

class TestDeltaCalculation:
    """Tests for GIRR delta risk charge."""

    @pytest.fixture
    def calc(self) -> GIRRCalculator:
        return GIRRCalculator()

    def test_single_sensitivity_delta(self, calc: GIRRCalculator) -> None:
        """Single sensitivity: K_b = RW * |s|."""
        sens = [_delta_sens(value=1_000_000.0, tenor=GIRRTenor.Y10)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        # WS = 0.011 * 1,000,000 = 11,000
        expected = 11_000.0
        assert abs(result.capital_charge - expected) < 1.0

    def test_two_same_risk_factor_add(self, calc: GIRRCalculator) -> None:
        """Two sensitivities at same tenor+curve → they get correlated at 1.0."""
        sens = [
            _delta_sens(value=500_000.0, tenor=GIRRTenor.Y10),
            _delta_sens(value=500_000.0, tenor=GIRRTenor.Y10),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        # Two WS of 5500 each, same risk factor (rho=1.0) → K = 5500 + 5500 = 11000
        expected = 11_000.0
        assert abs(result.capital_charge - expected) < 1.0

    def test_offsetting_sensitivities(self, calc: GIRRCalculator) -> None:
        """Opposing sensitivities on same risk factor net out."""
        sens = [
            _delta_sens(value=1_000_000.0, tenor=GIRRTenor.Y10),
            _delta_sens(value=-1_000_000.0, tenor=GIRRTenor.Y10),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert abs(result.capital_charge) < 1.0

    def test_multi_tenor_diversification(self, calc: GIRRCalculator) -> None:
        """Multi-tenor → diversification benefit (charge < sum of individual)."""
        sens = [
            _delta_sens(tenor=GIRRTenor.Y1, value=1e6),
            _delta_sens(tenor=GIRRTenor.Y5, value=1e6),
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        sum_individual = 0.016 * 1e6 + 0.011 * 1e6 + 0.011 * 1e6
        assert result.capital_charge < sum_individual
        assert result.capital_charge > 0

    def test_multi_currency_inter_bucket(self, calc: GIRRCalculator) -> None:
        """Two currencies → inter-bucket aggregation with gamma=50%."""
        sens = [
            _delta_sens(bucket="USD", tenor=GIRRTenor.Y10, value=1e6),
            _delta_sens(bucket="EUR", tenor=GIRRTenor.Y10, value=1e6),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        # K_usd = K_eur = 11,000
        # S_usd = S_eur = 11,000
        # Total = sqrt(11000^2 + 11000^2 + 2*0.5*11000*11000) = 11000*sqrt(3)
        expected = 11_000.0 * math.sqrt(3)
        assert abs(result.capital_charge - expected) / expected < 0.01

    def test_inflation_sensitivity(self, calc: GIRRCalculator) -> None:
        """Inflation uses 1.6% RW, correlated at 40% with yield curve."""
        sens = [
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6),
            _delta_sens(rf_type=GIRRRiskFactorType.INFLATION, value=500_000.0, label="INFLATION"),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0
        # WS_10Y = 0.011 * 1M = 11,000
        # WS_infl = 0.016 * 500K = 8,000
        # K = sqrt(11000^2 + 8000^2 + 2*0.40*11000*8000)
        expected = math.sqrt(11000**2 + 8000**2 + 2 * 0.40 * 11000 * 8000)
        assert abs(result.capital_charge - expected) / expected < 0.01

    def test_xccy_basis_zero_correlation(self, calc: GIRRCalculator) -> None:
        """XCCY basis has 0% correlation to yield curve → Pythagorean addition."""
        sens = [
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6),
            _delta_sens(
                rf_type=GIRRRiskFactorType.CROSS_CURRENCY_BASIS,
                value=500_000.0, label="XCCY",
            ),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        # WS_10Y = 11,000, WS_xccy = 8,000
        # K = sqrt(11000^2 + 8000^2) ≈ 13,601
        expected = math.sqrt(11_000**2 + 8_000**2)
        assert abs(result.capital_charge - expected) / expected < 0.01

    def test_high_vol_currency_multiplier(self, calc: GIRRCalculator) -> None:
        """BRL (high-vol) gets sqrt(2) multiplier on risk weights."""
        sens = [_delta_sens(bucket="BRL", tenor=GIRRTenor.Y10, value=1e6)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        expected = 0.011 * math.sqrt(2) * 1e6
        assert abs(result.capital_charge - expected) / expected < 0.01

    def test_bucket_results_populated(self, calc: GIRRCalculator) -> None:
        """Verify bucket results are returned with correct structure."""
        sens = [_delta_sens()]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert len(result.bucket_results) == 1
        assert result.bucket_results[0].bucket == "USD"
        assert result.bucket_results[0].capital_charge > 0

    def test_cross_curve_correlation(self, calc: GIRRCalculator) -> None:
        """Different curves in same currency → rho * 0.999."""
        sens = [
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6, label="OIS"),
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6, label="SOFR_3M"),
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        # rho = 1.0 * 0.999 (same tenor, different curve)
        # K = sqrt(11000^2 + 11000^2 + 2*0.999*11000*11000)
        expected = math.sqrt(2 * 11000**2 + 2 * 0.999 * 11000**2)
        assert abs(result.capital_charge - expected) / expected < 0.01

    def test_empty_delta(self, calc: GIRRCalculator) -> None:
        """Empty sensitivities → zero charge."""
        result = calc._calculate_delta_charge([], CorrelationScenario.MEDIUM)
        assert result.capital_charge == 0.0


# =========================================================================
#  4. Correlation Scenario Tests
# =========================================================================

class TestCorrelationScenarios:
    """Tests comparing behavior across LOW/MEDIUM/HIGH scenarios."""

    @pytest.fixture
    def calc(self) -> GIRRCalculator:
        return GIRRCalculator()

    def test_same_direction_high_gives_highest(self, calc: GIRRCalculator) -> None:
        """Same-direction positions: higher correlation → higher charge."""
        sens = [
            _delta_sens(tenor=GIRRTenor.Y1, value=1e6),
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6),
        ]
        low = calc._calculate_delta_charge(sens, CorrelationScenario.LOW)
        med = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        high = calc._calculate_delta_charge(sens, CorrelationScenario.HIGH)
        assert high.capital_charge >= med.capital_charge - 1e-6
        assert med.capital_charge >= low.capital_charge - 1e-6

    def test_opposite_direction_low_gives_highest(self, calc: GIRRCalculator) -> None:
        """Opposite positions: lower correlation → less offset → higher charge."""
        sens = [
            _delta_sens(tenor=GIRRTenor.Y1, value=1e6),
            _delta_sens(tenor=GIRRTenor.Y10, value=-1e6),
        ]
        low = calc._calculate_delta_charge(sens, CorrelationScenario.LOW)
        med = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        high = calc._calculate_delta_charge(sens, CorrelationScenario.HIGH)
        assert low.capital_charge >= med.capital_charge - 1e-6
        assert med.capital_charge >= high.capital_charge - 1e-6

    def test_inter_bucket_scenario_scaling(self, calc: GIRRCalculator) -> None:
        """Inter-bucket gamma changes across scenarios."""
        sens = [
            _delta_sens(bucket="USD", tenor=GIRRTenor.Y10, value=1e6),
            _delta_sens(bucket="EUR", tenor=GIRRTenor.Y10, value=1e6),
        ]
        low = calc._calculate_delta_charge(sens, CorrelationScenario.LOW)
        med = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        high = calc._calculate_delta_charge(sens, CorrelationScenario.HIGH)
        # All should be positive
        assert low.capital_charge > 0
        assert med.capital_charge > 0
        assert high.capital_charge > 0


# =========================================================================
#  5. Vega Tests
# =========================================================================

class TestVegaCalculation:
    """Tests for GIRR vega risk charge."""

    @pytest.fixture
    def calc(self) -> GIRRCalculator:
        return GIRRCalculator()

    def test_single_vega_sensitivity(self, calc: GIRRCalculator) -> None:
        """RW = 100%, so WS = 1.0 * sensitivity value."""
        sens = [_vega_sens(value=100_000.0)]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        assert abs(result.capital_charge - 100_000.0) < 1.0

    def test_two_vega_same_maturity_tenor(self, calc: GIRRCalculator) -> None:
        """Same option maturity + underlying tenor → correlation = 1.0."""
        sens = [
            _vega_sens(value=50_000.0, option_maturity=1.0, tenor=GIRRTenor.Y5),
            _vega_sens(value=50_000.0, option_maturity=1.0, tenor=GIRRTenor.Y5),
        ]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        assert abs(result.capital_charge - 100_000.0) < 1.0

    def test_vega_different_maturities(self, calc: GIRRCalculator) -> None:
        """Different option maturities → correlation < 1.0 → diversification."""
        sens = [
            _vega_sens(value=100_000.0, option_maturity=0.5, tenor=GIRRTenor.Y5),
            _vega_sens(value=100_000.0, option_maturity=10.0, tenor=GIRRTenor.Y5),
        ]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge < 200_000.0  # Some diversification
        assert result.capital_charge > 100_000.0  # Still both contribute

    def test_vega_multi_currency(self, calc: GIRRCalculator) -> None:
        """Multi-currency vega uses inter-bucket gamma."""
        sens = [
            _vega_sens(bucket="USD", value=100_000.0),
            _vega_sens(bucket="EUR", value=100_000.0),
        ]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0

    def test_empty_vega(self, calc: GIRRCalculator) -> None:
        result = calc._calculate_vega_charge([], CorrelationScenario.MEDIUM)
        assert result.capital_charge == 0.0


# =========================================================================
#  6. Curvature Tests
# =========================================================================

class TestCurvatureCalculation:
    """Tests for GIRR curvature risk charge."""

    @pytest.fixture
    def calc(self) -> GIRRCalculator:
        return GIRRCalculator()

    def test_single_positive_curvature(self, calc: GIRRCalculator) -> None:
        sens = [_curvature_sens(value=50_000.0)]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        # K_b = sqrt(max(0, 50000)) = sqrt(50000) ... wait, for single CVR:
        # K_b = sqrt(max(0, sum_CVR + 0)) = sqrt(50000) ≈ 223.6
        # Actually: K_b = sqrt(max(0, 50000)) = sqrt(50000) ≈ 223.6
        # Hmm - actually for single element: sum_CVR = 50000, no cross-terms
        # K_b = sqrt(max(0, 50000)) = sqrt(50000)
        assert result.capital_charge == pytest.approx(math.sqrt(50_000.0), rel=1e-6)

    def test_negative_curvature_floored(self, calc: GIRRCalculator) -> None:
        """Negative total CVR → K_b = sqrt(max(0, ...)) = 0."""
        sens = [_curvature_sens(value=-50_000.0)]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge == 0.0

    def test_psi_both_positive(self) -> None:
        result = GIRRCalculator._psi(10.0, 20.0)
        assert result == 200.0

    def test_psi_both_negative(self) -> None:
        """Both negative → psi = 0 (no diversification benefit)."""
        result = GIRRCalculator._psi(-10.0, -20.0)
        assert result == 0.0

    def test_psi_mixed_signs(self) -> None:
        """Mixed signs → psi = -|x|*|y|."""
        result = GIRRCalculator._psi(10.0, -20.0)
        assert result == -200.0

    def test_psi_mixed_signs_reverse(self) -> None:
        result = GIRRCalculator._psi(-10.0, 20.0)
        assert result == -200.0

    def test_curvature_two_positive(self, calc: GIRRCalculator) -> None:
        """Two positive CVRs at correlated tenors."""
        sens = [
            _curvature_sens(value=50_000.0, tenor=GIRRTenor.Y5),
            _curvature_sens(value=50_000.0, tenor=GIRRTenor.Y10),
        ]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0

    def test_curvature_multi_currency(self, calc: GIRRCalculator) -> None:
        sens = [
            _curvature_sens(bucket="USD", value=50_000.0),
            _curvature_sens(bucket="EUR", value=50_000.0),
        ]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0

    def test_empty_curvature(self, calc: GIRRCalculator) -> None:
        result = calc._calculate_curvature_charge([], CorrelationScenario.MEDIUM)
        assert result.capital_charge == 0.0


# =========================================================================
#  7. Full Integration Tests
# =========================================================================

class TestGIRRIntegration:
    """End-to-end tests for the full GIRR calculator."""

    def test_full_calculate_returns_girr_result(self) -> None:
        calc = GIRRCalculator()
        sens = [_delta_sens(value=1e6)]
        result = calc.calculate(sens)
        assert isinstance(result, GIRRResult)
        assert result.delta_charge > 0
        assert result.total_charge >= result.delta_charge

    def test_empty_sensitivities_returns_zero(self) -> None:
        calc = GIRRCalculator()
        result = calc.calculate([])
        assert result.total_charge == 0.0

    def test_delta_only_portfolio(self) -> None:
        """Delta-only: vega and curvature charges should be zero."""
        calc = GIRRCalculator()
        sens = [_delta_sens(value=1e6)]
        result = calc.calculate(sens)
        assert result.delta_charge > 0
        assert result.vega_charge == 0.0
        assert result.curvature_charge == 0.0

    def test_max_across_scenarios(self) -> None:
        """Total charge = max(delta scenarios) + max(vega scenarios) + max(curv scenarios)."""
        calc = GIRRCalculator()
        sens = [
            _delta_sens(tenor=GIRRTenor.Y1, value=1e6),
            _delta_sens(tenor=GIRRTenor.Y10, value=1e6),
        ]
        result = calc.calculate(sens)
        # delta_charge should be max of 3 scenarios
        assert result.delta_charge == max(
            result.delta_low.capital_charge,
            result.delta_medium.capital_charge,
            result.delta_high.capital_charge,
        )

    def test_realistic_portfolio(self) -> None:
        """Multi-currency, multi-tenor portfolio with all risk measures."""
        calc = GIRRCalculator()
        sens = []

        # USD delta positions
        for tenor, val in [
            (GIRRTenor.Y2, 5e6),
            (GIRRTenor.Y5, -3e6),
            (GIRRTenor.Y10, 2e6),
            (GIRRTenor.Y30, -1e6),
        ]:
            sens.append(_delta_sens(bucket="USD", tenor=tenor, value=val))

        # EUR delta positions
        for tenor, val in [
            (GIRRTenor.Y5, 4e6),
            (GIRRTenor.Y10, -2e6),
        ]:
            sens.append(_delta_sens(bucket="EUR", tenor=tenor, value=val))

        # USD inflation
        sens.append(_delta_sens(
            bucket="USD",
            rf_type=GIRRRiskFactorType.INFLATION,
            value=1e6,
            label="INFLATION",
        ))

        # Vega
        sens.append(_vega_sens(bucket="USD", value=200_000.0, option_maturity=1.0))
        sens.append(_vega_sens(bucket="USD", value=-100_000.0, option_maturity=5.0))

        # Curvature
        sens.append(_curvature_sens(bucket="USD", value=30_000.0))

        result = calc.calculate(sens)
        assert result.total_charge > 0
        assert result.delta_charge > 0
        assert result.vega_charge > 0
        assert result.curvature_charge > 0

    def test_high_vol_vs_low_vol_comparison(self) -> None:
        """High-vol currency should produce higher charge than low-vol."""
        calc = GIRRCalculator()
        usd_sens = [_delta_sens(bucket="USD", value=1e6)]
        brl_sens = [_delta_sens(bucket="BRL", value=1e6)]
        usd_result = calc.calculate(usd_sens)
        brl_result = calc.calculate(brl_sens)
        assert brl_result.delta_charge > usd_result.delta_charge

    def test_validation_non_girr(self) -> None:
        """Non-GIRR sensitivities should be rejected."""
        calc = GIRRCalculator()
        sens = [Sensitivity(
            risk_class=RiskClass.EQUITY,
            risk_measure=RiskMeasure.DELTA,
            bucket="AAPL",
            value=1e6,
        )]
        from src.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            calc.calculate(sens)


# =========================================================================
#  8. Aggregation Unit Tests
# =========================================================================

class TestAggregation:
    """Tests for the aggregation utility functions."""

    def test_intra_bucket_single(self) -> None:
        from src.utils.aggregation import intra_bucket_aggregation
        ws = np.array([100.0])
        corr = np.array([[1.0]])
        k_b, s_b = intra_bucket_aggregation(ws, corr)
        assert abs(k_b - 100.0) < 1e-6
        assert abs(s_b - 100.0) < 1e-6

    def test_intra_bucket_two_correlated(self) -> None:
        from src.utils.aggregation import intra_bucket_aggregation
        ws = np.array([100.0, 100.0])
        rho = 0.5
        corr = np.array([[1.0, rho], [rho, 1.0]])
        k_b, s_b = intra_bucket_aggregation(ws, corr)
        expected = math.sqrt(100**2 + 100**2 + 2 * rho * 100 * 100)
        assert abs(k_b - expected) < 1e-6

    def test_inter_bucket_single(self) -> None:
        from src.utils.aggregation import inter_bucket_aggregation
        charges = {"USD": 100.0}
        net_sens = {"USD": 100.0}
        result = inter_bucket_aggregation(charges, net_sens, 0.50)
        assert abs(result - 100.0) < 1e-6

    def test_inter_bucket_two(self) -> None:
        from src.utils.aggregation import inter_bucket_aggregation
        charges = {"USD": 100.0, "EUR": 100.0}
        net_sens = {"USD": 100.0, "EUR": 100.0}
        result = inter_bucket_aggregation(charges, net_sens, 0.50)
        expected = math.sqrt(100**2 + 100**2 + 2 * 0.50 * 100 * 100)
        assert abs(result - expected) < 1e-6

    def test_inter_bucket_capping(self) -> None:
        """S_b is capped to [-K_b, K_b]."""
        from src.utils.aggregation import inter_bucket_aggregation
        charges = {"USD": 50.0}  # K_b = 50
        net_sens = {"USD": 200.0}  # S_b = 200, should be capped to 50
        result = inter_bucket_aggregation(charges, net_sens, 0.50)
        assert abs(result - 50.0) < 1e-6


# =========================================================================
#  9. Edge Cases
# =========================================================================

class TestEdgeCases:
    """Edge case and boundary tests."""

    @pytest.fixture
    def calc(self) -> GIRRCalculator:
        return GIRRCalculator()

    def test_very_large_sensitivity(self, calc: GIRRCalculator) -> None:
        """Handle very large values without overflow."""
        sens = [_delta_sens(value=1e12)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0
        assert math.isfinite(result.capital_charge)

    def test_very_small_sensitivity(self, calc: GIRRCalculator) -> None:
        sens = [_delta_sens(value=0.01)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge >= 0
        assert math.isfinite(result.capital_charge)

    def test_zero_sensitivity(self, calc: GIRRCalculator) -> None:
        sens = [_delta_sens(value=0.0)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert abs(result.capital_charge) < 1e-10

    def test_many_currencies(self, calc: GIRRCalculator) -> None:
        """Test with many buckets for inter-bucket aggregation."""
        currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "SEK", "BRL", "TRY"]
        sens = [_delta_sens(bucket=ccy, value=1e6) for ccy in currencies]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0
        assert len(result.bucket_results) == 10

    def test_all_tenors_single_currency(self, calc: GIRRCalculator) -> None:
        """All 12 tenors populated for one currency."""
        sens = [
            _delta_sens(tenor=GIRRTenor(t), value=1e6)
            for t in TENORS
        ]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge > 0
        assert len(result.bucket_results) == 1
