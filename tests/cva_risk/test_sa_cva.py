"""Closed-form tests for SA-CVA — ERBA NPR §__.224–§__.225.

All monetary values in USD millions ($M).
"""

from __future__ import annotations

import math

import pytest

from src.cva_risk.cva_params import CVACreditQuality, CVASector
from src.cva_risk.cva_params import SACVARiskFactorType as RC
from src.cva_risk.sa_cva import SACVACalculator, SACVASensitivity

IG = CVACreditQuality.INVESTMENT_GRADE
SPEC = CVACreditQuality.SPECULATIVE_GRADE
R = 0.01


def ir(ccy: str, tenor: float | None, cva: float, hdg: float = 0.0, infl: bool = False) -> SACVASensitivity:
    return SACVASensitivity(risk_class=RC.INTEREST_RATE, currency=ccy, tenor=tenor,
                            is_inflation=infl, cva_sensitivity=cva, hedge_sensitivity=hdg)


def fx(ccy: str, cva: float, hdg: float = 0.0, vega: bool = False) -> SACVASensitivity:
    return SACVASensitivity(risk_class=RC.FX, currency=ccy, cva_sensitivity=cva,
                            hedge_sensitivity=hdg, is_vega=vega)


def ccs(entity: str, tenor: float, cva: float, hdg: float = 0.0, sector=CVASector.FINANCIALS,
        quality=IG, **kw) -> SACVASensitivity:
    return SACVASensitivity(risk_class=RC.COUNTERPARTY_CREDIT_SPREAD, entity_id=entity, tenor=tenor,
                            cva_sensitivity=cva, hedge_sensitivity=hdg, sector=sector,
                            credit_quality=quality, **kw)


@pytest.fixture
def calc() -> SACVACalculator:
    return SACVACalculator()


class TestIntraBucket:
    def test_single_ir_factor(self, calc) -> None:
        """USD 5y, s = 100: WS = 0.74, K_b = K = 0.74 (no vega → 0)."""
        res = calc.calculate([ir("USD", 5.0, 100.0)])
        assert res.k_cva == pytest.approx(0.74)
        assert res.delta_charge == pytest.approx(0.74)
        assert res.vega_charge == 0.0
        assert res.rwa == pytest.approx(12.5 * 0.74)
        b = res.risk_class_results[0].bucket_results[0]
        assert b.capital_charge == pytest.approx(0.74)
        assert b.s_b == pytest.approx(0.74)

    def test_hedging_disallowance_floor(self, calc) -> None:
        """Perfect hedge: WS = 0, K_b = sqrt(R·WS_hdg²) = 0.1·WS_hdg."""
        res = calc.calculate([ir("USD", 5.0, 100.0, hdg=100.0)])
        assert res.k_cva == pytest.approx(math.sqrt(R) * 0.74)
        b = res.risk_class_results[0].bucket_results[0]
        assert b.sum_weighted_sensitivity == pytest.approx(0.0)
        assert b.hedge_disallowance_term == pytest.approx(R * 0.74 ** 2)

    def test_net_weighted_sensitivity(self, calc) -> None:
        """WS = RW·s^CVA − RW·s^Hdg; K_b² = WS² + R·(RW·s^Hdg)²."""
        res = calc.calculate([ir("USD", 1.0, 100.0, hdg=40.0)])
        ws = 0.0111 * 60.0
        ws_h = 0.0111 * 40.0
        assert res.k_cva == pytest.approx(math.sqrt(ws ** 2 + R * ws_h ** 2))

    def test_ir_tenor_correlation_matrix(self, calc) -> None:
        """USD 1y and 2y, ρ = 0.91."""
        res = calc.calculate([ir("USD", 1.0, 100.0), ir("USD", 2.0, 100.0)])
        w1, w2 = 1.11, 0.93
        assert res.k_cva == pytest.approx(math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.91 * w1 * w2))

    def test_ir_inflation_correlation(self, calc) -> None:
        res = calc.calculate([ir("EUR", 30.0, 100.0), ir("EUR", None, 100.0, infl=True)])
        w1, w2 = 0.74, 1.11
        assert res.k_cva == pytest.approx(math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.40 * w1 * w2))

    def test_other_currency_parallel_and_inflation(self, calc) -> None:
        """Non-specified currency: parallel RW 1.58%, inflation 1.58%, ρ 40%."""
        res = calc.calculate([ir("BRL", 1.0, 50.0), ir("BRL", 10.0, 50.0), ir("BRL", None, 100.0, infl=True)])
        w_par = 0.0158 * 100.0   # tenor sensitivities pooled into the parallel factor
        w_inf = 0.0158 * 100.0
        assert res.k_cva == pytest.approx(math.sqrt(w_par ** 2 + w_inf ** 2 + 2 * 0.4 * w_par * w_inf))
        assert len(res.risk_class_results[0].bucket_results[0].factors) == 2

    def test_same_factor_records_are_summed(self, calc) -> None:
        res = calc.calculate([ir("USD", 5.0, 60.0), ir("USD", 5.0, 40.0)])
        assert res.k_cva == pytest.approx(0.74)

    def test_ccs_tenor_name_quality_correlations(self, calc) -> None:
        """ρ = ρ_tenor × ρ_name × ρ_quality."""
        # Same name, different tenors: 0.9
        res = calc.calculate([ccs("A", 1.0, 100.0), ccs("A", 5.0, 100.0)])
        w = 0.05 * 100.0
        assert res.k_cva == pytest.approx(math.sqrt(2 * w ** 2 + 2 * 0.9 * w ** 2))
        # Different names, same tenor, different quality: 0.5 × 0.8
        res = calc.calculate([ccs("A", 5.0, 100.0), ccs("B", 5.0, 100.0, quality=SPEC)])
        wa, wb = 0.05 * 100.0, 0.12 * 100.0
        assert res.k_cva == pytest.approx(math.sqrt(wa ** 2 + wb ** 2 + 2 * 0.4 * wa * wb))
        # Affiliates, different tenor, same quality: 0.9 × 0.9
        res = calc.calculate([
            ccs("A", 1.0, 100.0, affiliate_group="G"), ccs("B", 3.0, 100.0, affiliate_group="G"),
        ])
        assert res.k_cva == pytest.approx(math.sqrt(2 * w ** 2 + 2 * 0.81 * w ** 2))

    def test_ccs_index_bucket_correlations(self, calc) -> None:
        kw = dict(is_index=True, sector=None)
        # Same index, different series, same tenor: 0.9
        res = calc.calculate([
            ccs("CDX.IG", 5.0, 100.0, index_series="S40", **kw),
            ccs("CDX.IG", 5.0, 100.0, index_series="S41", **kw),
        ])
        w = 0.015 * 100.0
        assert res.k_cva == pytest.approx(math.sqrt(2 * w ** 2 + 2 * 0.9 * w ** 2))
        # Different indices: 0.8
        res = calc.calculate([
            ccs("CDX.IG", 5.0, 100.0, **kw), ccs("ITRAXX", 5.0, 100.0, **kw),
        ])
        assert res.k_cva == pytest.approx(math.sqrt(2 * w ** 2 + 2 * 0.8 * w ** 2))
        assert res.risk_class_results[0].bucket_results[0].bucket == "8"

    def test_ccs_bucket_1c_government_backed_financial(self) -> None:
        s = ccs("GBF", 5.0, 1.0, government_backed_financial=True)
        assert s.bucket == 1
        assert s.risk_weight == 0.05

    def test_no_ccs_vega(self) -> None:
        with pytest.raises(ValueError):
            SACVASensitivity(risk_class=RC.COUNTERPARTY_CREDIT_SPREAD, is_vega=True, entity_id="A",
                             tenor=5.0, sector=CVASector.FINANCIALS, credit_quality=IG, cva_sensitivity=1.0)


class TestInterBucket:
    def test_s_b_cap_is_always_applied(self, calc) -> None:
        """USD 1y + 2y: ΣWS = 2 > K_b = sqrt(3.82) → S_b capped at K_b (fn. 510)."""
        sens = [ir("USD", 1.0, 100 / 1.11), ir("USD", 2.0, 100 / 0.93), ir("EUR", 5.0, 100 / 0.74)]
        res = calc.calculate(sens)
        k_usd = math.sqrt(2 + 2 * 0.91)
        assert k_usd < 2.0
        usd = next(b for b in res.risk_class_results[0].bucket_results if b.bucket == "USD")
        assert usd.sum_weighted_sensitivity == pytest.approx(2.0)
        assert usd.s_b == pytest.approx(k_usd)
        capped = math.sqrt(k_usd ** 2 + 1.0 + 2 * 0.5 * k_usd * 1.0)
        uncapped = math.sqrt(k_usd ** 2 + 1.0 + 2 * 0.5 * 2.0 * 1.0)
        assert res.k_cva == pytest.approx(capped)
        assert res.k_cva != pytest.approx(uncapped)

    def test_negative_floor(self, calc) -> None:
        sens = [ir("USD", 1.0, -100 / 1.11), ir("USD", 2.0, -100 / 0.93), ir("EUR", 5.0, 100 / 0.74)]
        res = calc.calculate(sens)
        usd = next(b for b in res.risk_class_results[0].bucket_results if b.bucket == "USD")
        assert usd.s_b == pytest.approx(-math.sqrt(2 + 2 * 0.91))

    def test_fx_gamma(self, calc) -> None:
        res = calc.calculate([fx("EUR", 100.0), fx("JPY", 50.0)])
        a, b = 11.0, 5.5
        assert res.k_cva == pytest.approx(math.sqrt(a ** 2 + b ** 2 + 2 * 0.6 * a * b))

    def test_ccs_table_4_gamma(self, calc) -> None:
        res = calc.calculate([
            ccs("A", 5.0, 100.0, sector=CVASector.FINANCIALS),                     # bucket 2, 5%
            ccs("B", 5.0, 100.0, sector=CVASector.TECHNOLOGY_TELECOM),             # bucket 5, 2%
        ])
        a, b = 5.0, 2.0
        assert res.k_cva == pytest.approx(math.sqrt(a ** 2 + b ** 2 + 2 * 0.20 * a * b))

    def test_rcs_gamma_and_bucket_8_quality(self, calc) -> None:
        sens = [
            SACVASensitivity(risk_class=RC.REFERENCE_CREDIT_SPREAD, bucket=1, cva_sensitivity=100.0),
            SACVASensitivity(risk_class=RC.REFERENCE_CREDIT_SPREAD, bucket=8, credit_quality="CCC",
                             cva_sensitivity=100.0),
        ]
        res = calc.calculate(sens)
        a, b = 0.5, 7.0
        assert res.k_cva == pytest.approx(math.sqrt(a ** 2 + b ** 2 + 2 * 0.5 * a * b))

    def test_equity_and_commodity(self, calc) -> None:
        eq = [
            SACVASensitivity(risk_class=RC.EQUITY, bucket=1, cva_sensitivity=10.0),
            SACVASensitivity(risk_class=RC.EQUITY, bucket=12, cva_sensitivity=10.0),
        ]
        res = calc.calculate(eq)
        a, b = 5.5, 1.5
        assert res.k_cva == pytest.approx(math.sqrt(a ** 2 + b ** 2 + 2 * 0.45 * a * b))
        co = [
            SACVASensitivity(risk_class=RC.COMMODITY, bucket=4, cva_sensitivity=10.0),
            SACVASensitivity(risk_class=RC.COMMODITY, bucket=11, cva_sensitivity=10.0),
        ]
        res = calc.calculate(co)
        assert res.k_cva == pytest.approx(math.sqrt(8.0 ** 2 + 5.0 ** 2))


class TestAggregationAcrossClasses:
    def test_simple_sum_across_risk_classes_and_delta_vega(self, calc) -> None:
        sens = [
            ir("USD", 5.0, 100.0),                                                     # 0.74
            fx("EUR", 100.0),                                                          # 11.0
            fx("EUR", 10.0, vega=True),                                                # 10.0 (RW 100%)
            SACVASensitivity(risk_class=RC.EQUITY, bucket=9, is_vega=True, cva_sensitivity=10.0),  # 10.0
            SACVASensitivity(risk_class=RC.EQUITY, bucket=1, is_vega=True, cva_sensitivity=10.0),  # 7.8
        ]
        res = calc.calculate(sens)
        assert res.delta_charge == pytest.approx(0.74 + 11.0)
        eq_vega = math.sqrt(10.0 ** 2 + 7.8 ** 2 + 2 * 0.15 * 10.0 * 7.8)
        assert res.vega_charge == pytest.approx(10.0 + eq_vega)
        assert res.k_cva == pytest.approx(res.delta_charge + res.vega_charge)
        assert set(res.k_by_risk_class) == {"INTEREST_RATE:DELTA", "FX:DELTA", "FX:VEGA", "EQUITY:VEGA"}

    def test_ir_vega(self, calc) -> None:
        sens = [
            SACVASensitivity(risk_class=RC.INTEREST_RATE, is_vega=True, currency="USD", cva_sensitivity=10.0),
            SACVASensitivity(risk_class=RC.INTEREST_RATE, is_vega=True, currency="USD", is_inflation=True,
                             cva_sensitivity=10.0),
            SACVASensitivity(risk_class=RC.INTEREST_RATE, is_vega=True, currency="GBP", cva_sensitivity=10.0),
        ]
        res = calc.calculate(sens)
        k_usd = math.sqrt(2 * 100 + 2 * 0.4 * 100)
        s_usd = min(20.0, k_usd)
        assert res.k_cva == pytest.approx(math.sqrt(k_usd ** 2 + 100 + 2 * 0.5 * s_usd * 10.0))

    def test_m_cva_scales_linearly(self, calc) -> None:
        sens = [ir("USD", 5.0, 100.0), fx("EUR", 100.0), ccs("A", 5.0, 100.0)]
        base = calc.calculate(sens)
        doubled = calc.calculate(sens, m_cva=2.0)
        assert doubled.k_cva == pytest.approx(2.0 * base.k_cva)
        assert doubled.rwa == pytest.approx(2.0 * base.rwa)
        assert SACVACalculator(m_cva=1.5).calculate(sens).k_cva == pytest.approx(1.5 * base.k_cva)
        with pytest.raises(ValueError):
            SACVACalculator(m_cva=0.9)
        for rc in doubled.risk_class_results:
            assert rc.capital_charge == pytest.approx(2.0 * rc.capital_charge_unscaled)

    def test_empty(self, calc) -> None:
        res = calc.calculate([])
        assert res.k_cva == 0.0 and res.rwa == 0.0


class TestValidation:
    def test_bad_inputs(self) -> None:
        with pytest.raises(ValueError):
            ir("USD", 7.0, 1.0)                       # not a specified tenor
        with pytest.raises(ValueError):
            SACVASensitivity(risk_class=RC.FX, cva_sensitivity=1.0)  # no currency
        with pytest.raises(ValueError):
            ccs("A", 2.0, 1.0)                        # not a CCS tenor
        with pytest.raises(ValueError):
            SACVASensitivity(risk_class=RC.REFERENCE_CREDIT_SPREAD, bucket=18, cva_sensitivity=1.0)
        with pytest.raises(ValueError):
            SACVASensitivity(risk_class=RC.REFERENCE_CREDIT_SPREAD, bucket=8, cva_sensitivity=1.0)
        with pytest.raises(ValueError):
            SACVASensitivity(risk_class=RC.EQUITY, bucket=14, cva_sensitivity=1.0)
        with pytest.raises(ValueError):
            SACVASensitivity(risk_class=RC.COMMODITY, bucket=0, cva_sensitivity=1.0)
