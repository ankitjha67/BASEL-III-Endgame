"""Tests for the FX risk class parameters and calculator.

Regulatory basis: US ERBA NPR (March 2026) §__.208(b)(7), §__.209(b)(7),
§__.209 Table 11 and the curvature paragraph.
"""

from __future__ import annotations

import math

import pytest

from src.core.enums import CorrelationScenario, RiskClass, RiskMeasure
from src.core.models import Sensitivity
from src.market_risk.frtb.sbm.fx import FXCalculator
from src.market_risk.frtb.sbm.fx_params import (
    APPLY_FX_SPECIFIED_PAIR_REDUCTION,
    FX_CURVATURE_NON_REPORTING_CCY_DIVISOR,
    FX_DELTA_RW,
    FX_INTRA_CORR,
    FX_SPECIFIED_CURRENCIES,
    FX_VEGA_RW,
    get_fx_curvature_rw,
    get_fx_delta_rw,
    is_specified_fx_pair,
    parse_currency_pair,
    references_reporting_currency,
)

SQRT2 = math.sqrt(2)


def _fx(
    pair: str,
    value: float,
    measure: RiskMeasure = RiskMeasure.DELTA,
    option_maturity: float | None = None,
) -> Sensitivity:
    return Sensitivity(
        risk_class=RiskClass.FX,
        risk_measure=measure,
        bucket=pair,
        tenor=None,
        label=pair,
        value=value,
        option_maturity=option_maturity,
    )


class TestFXParams:
    """ERBA NPR §__.209(b)(7) parameters."""

    def test_base_risk_weight(self) -> None:
        assert FX_DELTA_RW == 0.15

    def test_specified_currency_list_exact(self) -> None:
        expected = {
            "USD", "AUD", "BRL", "CAD", "CNY", "EUR", "HKD", "INR", "JPY", "MXN",
            "NZD", "NOK", "SGD", "ZAR", "KRW", "SEK", "CHF", "TRY", "GBP",
        }
        assert FX_SPECIFIED_CURRENCIES == expected
        assert len(FX_SPECIFIED_CURRENCIES) == 19
        assert "RUB" not in FX_SPECIFIED_CURRENCIES

    def test_reduction_applied_by_default(self) -> None:
        assert APPLY_FX_SPECIFIED_PAIR_REDUCTION is True

    def test_gamma_and_vega(self) -> None:
        assert FX_INTRA_CORR == 0.60
        assert FX_VEGA_RW == 1.0

    @pytest.mark.parametrize("raw", ["EURUSD", "EUR/USD", "eur-usd", "EUR_USD", "EUR USD"])
    def test_parse_pair_formats(self, raw: str) -> None:
        assert parse_currency_pair(raw) == ("EUR", "USD")

    def test_parse_pair_invalid(self) -> None:
        assert parse_currency_pair("FX") is None
        assert parse_currency_pair("") is None

    def test_regulatory_example_eurusd(self) -> None:
        """EUR/USD: both specified -> 0.15 / sqrt(2)."""
        assert is_specified_fx_pair("EURUSD")
        assert get_fx_delta_rw("EURUSD") == pytest.approx(0.15 / SQRT2)

    def test_non_specified_pair_keeps_15pct(self) -> None:
        assert not is_specified_fx_pair("USDRUB")
        assert get_fx_delta_rw("USDRUB") == 0.15
        assert get_fx_delta_rw("USD/PLN") == 0.15

    def test_cross_pair_of_specified_currencies(self) -> None:
        """BRL/TRY: both on the list, so the reduction applies (currency-based)."""
        assert get_fx_delta_rw("BRLTRY") == pytest.approx(0.15 / SQRT2)

    def test_reduction_can_be_disabled(self) -> None:
        assert get_fx_delta_rw("EURUSD", apply_reduction=False) == 0.15

    def test_none_pair_returns_base(self) -> None:
        assert get_fx_delta_rw(None) == 0.15

    def test_curvature_rw_equals_delta_rw(self) -> None:
        assert get_fx_curvature_rw("EURUSD") == get_fx_delta_rw("EURUSD")
        assert get_fx_curvature_rw("USDRUB") == 0.15

    def test_references_reporting_currency(self) -> None:
        assert references_reporting_currency("EURUSD", "USD")
        assert not references_reporting_currency("EURGBP", "USD")
        assert references_reporting_currency("???", "USD")  # unparseable -> conservative

    def test_curvature_divisor_constant(self) -> None:
        assert FX_CURVATURE_NON_REPORTING_CCY_DIVISOR == 1.5


class TestFXCalculator:
    """Calculator behaviour under the NPR parameters."""

    @pytest.fixture
    def calc(self) -> FXCalculator:
        return FXCalculator()

    def test_delta_specified_pair(self, calc: FXCalculator) -> None:
        result = calc.calculate([_fx("EURUSD", 1e6)])
        assert result.delta_charge == pytest.approx(0.15 / SQRT2 * 1e6)

    def test_delta_other_pair(self, calc: FXCalculator) -> None:
        result = calc.calculate([_fx("USDRUB", 1e6)])
        assert result.delta_charge == pytest.approx(0.15 * 1e6)

    def test_two_pairs_gamma_60pct(self, calc: FXCalculator) -> None:
        sens = [_fx("EURUSD", 1e6), _fx("GBPUSD", 1e6)]
        result = calc._calculate_delta_charge(sens, CorrelationScenario.MEDIUM)
        ws = 0.15 / SQRT2 * 1e6
        expected = math.sqrt(2 * ws**2 + 2 * 0.60 * ws**2)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_vega_rw_100pct(self, calc: FXCalculator) -> None:
        result = calc.calculate([_fx("EURUSD", 100_000.0, RiskMeasure.VEGA, 1.0)])
        assert result.vega_charge == pytest.approx(100_000.0)

    def test_vega_same_pair_different_maturity(self, calc: FXCalculator) -> None:
        """Same pair: rho_delta = 1, only the option-maturity decay applies."""
        sens = [
            _fx("EURUSD", 1e5, RiskMeasure.VEGA, 1.0),
            _fx("EURUSD", 1e5, RiskMeasure.VEGA, 5.0),
        ]
        result = calc._calculate_vega_charge(sens, CorrelationScenario.MEDIUM)
        rho = math.exp(-0.01 * 4.0 / 1.0)
        expected = math.sqrt(2 * 1e10 + 2 * rho * 1e10)
        assert result.capital_charge == pytest.approx(expected, rel=1e-9)

    def test_curvature_divisor_default_off(self, calc: FXCalculator) -> None:
        result = calc.calculate([_fx("EURGBP", 30_000.0, RiskMeasure.CURVATURE)])
        assert result.curvature_charge == pytest.approx(30_000.0)

    def test_curvature_divisor_applied_when_elected(self) -> None:
        calc = FXCalculator(reporting_currency="USD", apply_curvature_divisor=True)
        non_usd = calc.calculate([_fx("EURGBP", 30_000.0, RiskMeasure.CURVATURE)])
        usd = calc.calculate([_fx("EURUSD", 30_000.0, RiskMeasure.CURVATURE)])
        assert non_usd.curvature_charge == pytest.approx(30_000.0 / 1.5)
        assert usd.curvature_charge == pytest.approx(30_000.0)

    def test_curvature_records_shock_size(self, calc: FXCalculator) -> None:
        result = calc._calculate_curvature_charge(
            [_fx("EURUSD", 30_000.0, RiskMeasure.CURVATURE)], CorrelationScenario.MEDIUM
        )
        rw = result.bucket_results[0].weighted_sensitivities[0].risk_weight
        assert rw == pytest.approx(0.15 / SQRT2)
