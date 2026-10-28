"""Tests for the Equity risk class parameters and calculator.

Regulatory basis: US ERBA NPR (March 2026) §__.208(b)(5), §__.209(b)(5)
Table 8, §__.209 Table 11 and the curvature paragraph.
"""

from __future__ import annotations

import math

import pytest

from src.core.enums import (
    CorrelationScenario,
    EquityBucket,
    EquityMarket,
    RiskClass,
    RiskMeasure,
)
from src.core.models import Sensitivity
from src.market_risk.frtb.sbm.equity import EquityCalculator
from src.market_risk.frtb.sbm.equity_params import (
    EQUITY_DELTA_RW,
    EQUITY_INTRA_CORR,
    EQUITY_LARGE_CAP_THRESHOLD_USD_M,
    EQUITY_REPO_RW,
    EQUITY_VEGA_RW,
    build_equity_intra_bucket_corr_matrix,
    get_equity_curvature_rw,
    get_equity_delta_rw,
    get_equity_inter_bucket_corr,
    get_equity_intra_corr,
    get_equity_repo_rw,
    get_equity_vega_rw,
    is_other_sector_bucket,
)


def _eq(
    bucket: str,
    value: float,
    label: str = "DEFAULT",
    measure: RiskMeasure = RiskMeasure.DELTA,
    option_maturity: float | None = None,
) -> Sensitivity:
    return Sensitivity(
        risk_class=RiskClass.EQUITY,
        risk_measure=measure,
        bucket=bucket,
        tenor=None,
        label=label,
        value=value,
        option_maturity=option_maturity,
    )


class TestEquityTable8:
    """ERBA NPR §__.209(b)(5) Table 8."""

    def test_spot_risk_weights_exact(self) -> None:
        expected = {
            1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55,
            5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,
            9: 0.70, 10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25,
        }
        assert EQUITY_DELTA_RW == expected

    def test_repo_risk_weights_are_spot_over_100(self) -> None:
        for b, rw in EQUITY_DELTA_RW.items():
            assert EQUITY_REPO_RW[b] == pytest.approx(rw / 100.0)

    def test_regulatory_example_bucket_8(self) -> None:
        """Bucket 8 (liquid large financials/real estate/tech): 50% spot, 0.50% repo."""
        assert get_equity_delta_rw(8) == 0.50
        assert get_equity_repo_rw(8) == pytest.approx(0.005)
        assert get_equity_delta_rw(8, is_repo=True) == pytest.approx(0.005)

    def test_intra_bucket_correlations(self) -> None:
        for b in (1, 2, 3, 4):
            assert get_equity_intra_corr(b) == 0.15
        for b in (5, 6, 7, 8):
            assert get_equity_intra_corr(b) == 0.25
        assert get_equity_intra_corr(9) == 0.075
        assert get_equity_intra_corr(10) == 0.125
        assert get_equity_intra_corr(12) == 0.80
        assert get_equity_intra_corr(13) == 0.80
        assert is_other_sector_bucket(11)
        assert len(EQUITY_INTRA_CORR) == 13

    def test_inter_bucket_gamma_rules(self) -> None:
        assert get_equity_inter_bucket_corr(1, 10) == 0.15   # sector vs sector
        assert get_equity_inter_bucket_corr(12, 13) == 0.75  # index vs index
        assert get_equity_inter_bucket_corr(12, 3) == 0.45   # regulatory example: index vs sector
        assert get_equity_inter_bucket_corr(5, 13) == 0.45
        assert get_equity_inter_bucket_corr(11, 1) == 0.0    # other sector
        assert get_equity_inter_bucket_corr(12, 11) == 0.0

    def test_vega_risk_weights_table_11(self) -> None:
        for b in (1, 2, 3, 4, 5, 6, 7, 8, 12, 13):
            assert get_equity_vega_rw(b) == pytest.approx(0.7778)
        for b in (9, 10, 11):
            assert get_equity_vega_rw(b) == 1.0
        assert len(EQUITY_VEGA_RW) == 13

    def test_curvature_rw_equals_delta_rw(self) -> None:
        for b in range(1, 14):
            assert get_equity_curvature_rw(b) == EQUITY_DELTA_RW[b]

    def test_large_cap_threshold(self) -> None:
        assert EQUITY_LARGE_CAP_THRESHOLD_USD_M == 2_000.0  # $2 billion in $M

    def test_enums(self) -> None:
        assert len(EquityBucket) == 13
        assert EquityBucket.B11_OTHER_SECTOR.value == 11
        assert EquityBucket.B10_LIQUID_SMALL_CAP.value == 10
        assert {m.name for m in EquityMarket} == {"EMERGING", "LIQUID_MARKET"}

    def test_spot_repo_correlations(self) -> None:
        corr = build_equity_intra_bucket_corr_matrix(
            4, 8, CorrelationScenario.MEDIUM,
            issuers=["A", "A", "B", "B"],
            is_repo=[False, True, False, True],
        )
        assert corr[0, 1] == pytest.approx(0.999)          # same issuer spot vs repo
        assert corr[0, 2] == pytest.approx(0.25)           # different issuer spot vs spot
        assert corr[0, 3] == pytest.approx(0.25 * 0.999)   # different issuer spot vs repo
        assert corr[1, 3] == pytest.approx(0.25)           # different issuer repo vs repo


class TestEquityCalculator:
    """Calculator behaviour under the NPR parameters."""

    @pytest.fixture
    def calc(self) -> EquityCalculator:
        return EquityCalculator()

    def test_bucket_8_spot_and_repo(self, calc: EquityCalculator) -> None:
        spot = calc.calculate([_eq("8", 1e6, label="JPM")])
        repo = calc.calculate([_eq("8", 1e6, label="JPM|REPO")])
        assert spot.delta_charge == pytest.approx(0.50 * 1e6)
        assert repo.delta_charge == pytest.approx(0.005 * 1e6)

    def test_bucket_11_sum_of_abs_ws(self, calc: EquityCalculator) -> None:
        """Other sector: K_b = sum |WS_k| -- opposite positions do NOT offset."""
        sens = [_eq("11", 1e6, label="X"), _eq("11", -1e6, label="Y")]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge == pytest.approx(2 * 0.70 * 1e6)
        assert result.bucket_results[0].net_weighted_sensitivity == pytest.approx(0.0)

    def test_bucket_11_zero_gamma(self, calc: EquityCalculator) -> None:
        """Bucket 11 has gamma = 0 with every other bucket."""
        sens = [_eq("11", 1e6, label="X"), _eq("1", 1e6, label="Y")]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        k11 = 0.70 * 1e6
        k1 = 0.55 * 1e6
        assert result.capital_charge == pytest.approx(math.sqrt(k11**2 + k1**2), rel=1e-9)

    def test_index_vs_sector_gamma_45pct(self, calc: EquityCalculator) -> None:
        sens = [_eq("12", 1e6, label="SPX"), _eq("3", 1e6, label="VALE")]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        k12 = 0.15 * 1e6
        k3 = 0.45 * 1e6
        expected = math.sqrt(k12**2 + k3**2 + 2 * 0.45 * k12 * k3)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_same_issuer_spot_repo_999(self, calc: EquityCalculator) -> None:
        sens = [_eq("8", 1e6, label="JPM"), _eq("8", 1e6, label="JPM|REPO")]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        ws_spot = 0.50 * 1e6
        ws_repo = 0.005 * 1e6
        expected = math.sqrt(ws_spot**2 + ws_repo**2 + 2 * 0.999 * ws_spot * ws_repo)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_different_issuers_bucket_rho(self, calc: EquityCalculator) -> None:
        sens = [_eq("5", 1e6, label="AAA"), _eq("5", 1e6, label="BBB")]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        ws = 0.30 * 1e6
        expected = math.sqrt(2 * ws**2 + 2 * 0.25 * ws**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_vega_rw_large_cap_and_small_cap(self, calc: EquityCalculator) -> None:
        large = calc.calculate([_eq("8", 1e5, label="JPM", measure=RiskMeasure.VEGA, option_maturity=1.0)])
        small = calc.calculate([_eq("9", 1e5, label="SML", measure=RiskMeasure.VEGA, option_maturity=1.0)])
        assert large.vega_charge == pytest.approx(0.7778 * 1e5)
        assert small.vega_charge == pytest.approx(1.0 * 1e5)

    def test_vega_bucket_11_sum_abs(self, calc: EquityCalculator) -> None:
        sens = [
            _eq("11", 1e5, label="X", measure=RiskMeasure.VEGA, option_maturity=1.0),
            _eq("11", -1e5, label="Y", measure=RiskMeasure.VEGA, option_maturity=1.0),
        ]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge == pytest.approx(2e5)

    def test_curvature_bucket_11(self, calc: EquityCalculator) -> None:
        """Other sector curvature: K_b = sum max(CVR_k, 0)."""
        sens = [
            _eq("11", 40_000.0, label="X", measure=RiskMeasure.CURVATURE),
            _eq("11", -10_000.0, label="Y", measure=RiskMeasure.CURVATURE),
        ]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        assert result.capital_charge == pytest.approx(40_000.0)

    def test_curvature_uses_squared_rho(self, calc: EquityCalculator) -> None:
        sens = [
            _eq("12", 50_000.0, label="SPX", measure=RiskMeasure.CURVATURE),
            _eq("12", 50_000.0, label="NDX", measure=RiskMeasure.CURVATURE),
        ]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        expected = math.sqrt(2 * 50_000.0**2 + 2 * 0.80**2 * 50_000.0**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)
        rw = result.bucket_results[0].weighted_sensitivities[0].risk_weight
        assert rw == 0.15

    def test_curvature_inter_bucket_gamma_squared(self, calc: EquityCalculator) -> None:
        sens = [
            _eq("12", 50_000.0, label="SPX", measure=RiskMeasure.CURVATURE),
            _eq("13", 50_000.0, label="EEM", measure=RiskMeasure.CURVATURE),
        ]
        result = calc._calculate_curvature_charge(sens, CorrelationScenario.MEDIUM)
        expected = math.sqrt(2 * 50_000.0**2 + 2 * 0.75**2 * 50_000.0**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)
