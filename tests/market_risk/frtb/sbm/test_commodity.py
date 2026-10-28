"""Tests for the Commodity risk class parameters and calculator.

Regulatory basis: US ERBA NPR (March 2026) §__.208(b)(6), §__.209(b)(6)
Tables 9-10, §__.209 Table 11 and the curvature paragraph.
"""

from __future__ import annotations

import math

import pytest

from src.core.enums import (
    CommodityBucket,
    CorrelationScenario,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.models import Sensitivity
from src.market_risk.frtb.sbm.commodity import CommodityCalculator
from src.market_risk.frtb.sbm.commodity_params import (
    COMMODITY_BUCKETS,
    COMMODITY_DELTA_MATURITIES,
    COMMODITY_DELTA_RW,
    COMMODITY_INTRA_CORR,
    COMMODITY_RHO_BASIS,
    COMMODITY_RHO_TENOR,
    COMMODITY_VEGA_RW,
    build_commodity_intra_bucket_corr_matrix,
    compute_commodity_tenor_correlation,
    get_commodity_curvature_rw,
    get_commodity_delta_rw,
    get_commodity_inter_bucket_corr,
    get_commodity_intra_corr,
)


def _cm(
    bucket: str,
    value: float,
    tenor: GIRRTenor | None = None,
    label: str = "DEFAULT",
    measure: RiskMeasure = RiskMeasure.DELTA,
    option_maturity: float | None = None,
) -> Sensitivity:
    return Sensitivity(
        risk_class=RiskClass.COMMODITY,
        risk_measure=measure,
        bucket=bucket,
        tenor=tenor,
        label=label,
        value=value,
        option_maturity=option_maturity,
    )


class TestCommodityTables9And10:
    """ERBA NPR §__.209(b)(6) Tables 9 and 10."""

    def test_delta_risk_weights_exact(self) -> None:
        expected = {
            1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45,
            7: 0.20, 8: 0.35, 9: 0.25, 10: 0.35, 11: 0.50, 12: 0.30,
        }
        assert COMMODITY_DELTA_RW == expected
        assert COMMODITY_BUCKETS == list(range(1, 13))

    def test_regulatory_example_freight(self) -> None:
        assert get_commodity_delta_rw(4) == 0.80
        assert get_commodity_curvature_rw(4) == 0.80

    def test_intra_correlations_exact(self) -> None:
        expected = {
            1: 0.55, 2: 0.95, 3: 0.40, 4: 0.80, 5: 0.60, 6: 0.65,
            7: 0.55, 8: 0.45, 9: 0.15, 10: 0.40, 11: 0.15, 12: 0.50,
        }
        assert COMMODITY_INTRA_CORR == expected
        assert get_commodity_intra_corr(2) == 0.95

    def test_tenor_and_basis_correlations(self) -> None:
        assert COMMODITY_RHO_TENOR == 0.99
        assert COMMODITY_RHO_BASIS == 0.999
        assert compute_commodity_tenor_correlation(1.0, 1.0) == 1.0
        assert compute_commodity_tenor_correlation(0.25, 30.0) == 0.99
        assert compute_commodity_tenor_correlation(1.0, 2.0) == 0.99  # flat, not exp decay

    def test_inter_bucket_gamma(self) -> None:
        assert get_commodity_inter_bucket_corr(1, 2) == 0.20  # no energy-group 40% rule
        assert get_commodity_inter_bucket_corr(1, 12) == 0.20
        assert get_commodity_inter_bucket_corr(11, 1) == 0.0
        assert get_commodity_inter_bucket_corr(12, 11) == 0.0

    def test_delta_maturity_grid(self) -> None:
        assert COMMODITY_DELTA_MATURITIES == [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0]

    def test_vega_rw(self) -> None:
        assert COMMODITY_VEGA_RW == 1.0

    def test_enum(self) -> None:
        assert len(CommodityBucket) == 12
        assert CommodityBucket.B4_FREIGHT.value == 4
        assert CommodityBucket.B12_COMMODITY_INDEX.value == 12

    def test_full_correlation_structure(self) -> None:
        corr = build_commodity_intra_bucket_corr_matrix(
            3, 2,
            tenors=[1.0, 2.0, 1.0],
            basis_flags=["WTI", "WTI", "BRENT"],
            scenario=CorrelationScenario.MEDIUM,
        )
        assert corr[0, 1] == pytest.approx(0.95 * 0.99)          # different tenor
        assert corr[0, 2] == pytest.approx(0.95 * 0.999)         # different location
        assert corr[1, 2] == pytest.approx(0.95 * 0.99 * 0.999)  # both


class TestCommodityCalculator:
    """Calculator behaviour under the NPR parameters."""

    @pytest.fixture
    def calc(self) -> CommodityCalculator:
        return CommodityCalculator()

    def test_freight_delta(self, calc: CommodityCalculator) -> None:
        result = calc.calculate([_cm("4", 1e6)])
        assert result.delta_charge == pytest.approx(0.80 * 1e6)

    def test_two_tenors_flat_99pct(self, calc: CommodityCalculator) -> None:
        sens = [_cm("2", 1e6, tenor=GIRRTenor.Y1), _cm("2", 1e6, tenor=GIRRTenor.Y10)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        ws = 0.35 * 1e6
        rho = 0.95 * 0.99
        expected = math.sqrt(2 * ws**2 + 2 * rho * ws**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_spot_vs_forward(self, calc: CommodityCalculator) -> None:
        """A sensitivity with no tenor is spot (maturity 0) -> 99% vs a forward."""
        sens = [_cm("7", 1e6), _cm("7", 1e6, tenor=GIRRTenor.Y1)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        ws = 0.20 * 1e6
        rho = 0.55 * 0.99
        expected = math.sqrt(2 * ws**2 + 2 * rho * ws**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_bucket_11_zero_gamma(self, calc: CommodityCalculator) -> None:
        sens = [_cm("11", 1e6), _cm("1", 1e6)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        k11 = 0.50 * 1e6
        k1 = 0.30 * 1e6
        assert result.capital_charge == pytest.approx(math.sqrt(k11**2 + k1**2), rel=1e-9)

    def test_energy_buckets_gamma_20pct(self, calc: CommodityCalculator) -> None:
        sens = [_cm("1", 1e6), _cm("2", 1e6)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        k1 = 0.30 * 1e6
        k2 = 0.35 * 1e6
        expected = math.sqrt(k1**2 + k2**2 + 2 * 0.20 * k1 * k2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_vega(self, calc: CommodityCalculator) -> None:
        sens = [
            _cm("5", 1e5, measure=RiskMeasure.VEGA, option_maturity=1.0),
            _cm("5", 1e5, measure=RiskMeasure.VEGA, option_maturity=3.0),
        ]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        rho = 0.60 * math.exp(-0.01 * 2.0 / 1.0)
        expected = math.sqrt(2 * 1e10 + 2 * rho * 1e10)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_curvature_squared_rho_and_shock_size(self, calc: CommodityCalculator) -> None:
        sens = [
            _cm("4", 50_000.0, label="DRY", measure=RiskMeasure.CURVATURE),
            _cm("4", 50_000.0, label="TANKER", measure=RiskMeasure.CURVATURE),
        ]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        rho = 0.80 * 0.999
        expected = math.sqrt(2 * 50_000.0**2 + 2 * rho**2 * 50_000.0**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)
        assert result.bucket_results[0].weighted_sensitivities[0].risk_weight == 0.80
