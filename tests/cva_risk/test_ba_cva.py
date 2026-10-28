"""Closed-form tests for BA-CVA — ERBA NPR §__.222.

All monetary values in USD millions ($M).
"""

from __future__ import annotations

import math

import pytest

from src.cva_risk.ba_cva import (
    BACVACalculator,
    BACVACounterparty,
    BACVAHedge,
    BACVAIndexConstituent,
    BACVANettingSet,
    BACVAPosition,
    compute_k_basic,
    compute_k_hedged,
    compute_k_unhedged,
    compute_scva,
    compute_scva_summary,
)
from src.cva_risk.cva_params import (
    BA_CVA_DISCOUNT_SCALAR,
    CVAApproach,
    CVACreditQuality,
    CVASector,
    supervisory_discount_factor,
)

IG = CVACreditQuality.INVESTMENT_GRADE
SPEC = CVACreditQuality.SPECULATIVE_GRADE
FIN = CVASector.FINANCIALS


def df(m: float) -> float:
    return (1.0 - math.exp(-0.05 * m)) / (0.05 * m)


def fin_ig(cp_id: str = "CP1", ead: float = 100.0, m: float = 2.0, **kw) -> BACVACounterparty:
    return BACVACounterparty(
        counterparty_id=cp_id, sector=FIN, credit_quality=IG,
        ead=ead, effective_maturity=m, **kw,
    )


@pytest.fixture
def calc() -> BACVACalculator:
    return BACVACalculator()


# =========================================================================
#  SCVA_c and K_unhedged
# =========================================================================

class TestSCVA:
    def test_single_unhedged_counterparty_closed_form(self, calc) -> None:
        """EAD 100, M 2, financials IG 5%, α 1.4.

        SCVA = (1/1.4)·0.05·2·100·DF(2), DF(2) = (1−e^−0.1)/0.1;
        K_unhedged = SCVA (single name); K_basic = 0.65·SCVA.
        """
        result = calc.calculate([fin_ig()])
        scva = (1 / 1.4) * 0.05 * 2.0 * 100.0 * df(2.0)
        assert df(2.0) == pytest.approx((1 - math.exp(-0.1)) / 0.1)
        assert result.counterparty_results[0].scva == pytest.approx(scva)
        assert result.counterparty_results[0].alpha == 1.4
        assert result.counterparty_results[0].risk_weight == 0.05
        assert result.k_unhedged == pytest.approx(scva)
        assert result.k_unhedged == pytest.approx(math.sqrt(0.25 * scva**2 + 0.75 * scva**2))
        assert result.k_hedged == pytest.approx(result.k_unhedged)
        assert result.k_basic == pytest.approx(0.65 * scva)
        assert result.k_ba_cva == pytest.approx(result.k_basic)
        assert result.rwa == pytest.approx(12.5 * 0.65 * scva)
        assert result.approach is CVAApproach.BA_CVA_REDUCED

    def test_commercial_end_user_alpha_one(self, calc) -> None:
        """α = 1.0 for counterparties under §__.114(e)(4)."""
        cp = BACVACounterparty(
            counterparty_id="CEU", sector=CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS,
            credit_quality=SPEC, ead=100.0, effective_maturity=2.0,
            is_commercial_end_user=True,
        )
        r = compute_scva(cp)
        assert r.alpha == 1.0
        assert r.scva == pytest.approx(0.07 * 2.0 * 100.0 * df(2.0))
        r14 = compute_scva(fin_ig())
        assert r14.alpha == 1.4

    def test_multiple_netting_sets_summed(self) -> None:
        """SCVA_c = (1/α)·RW_c·Σ_NS M_NS·EAD_NS·DF_NS."""
        cp = BACVACounterparty(
            counterparty_id="CP", sector=FIN, credit_quality=IG,
            netting_sets=[
                BACVANettingSet(netting_set_id="A", ead=100.0, effective_maturity=1.0),
                BACVANettingSet(netting_set_id="B", ead=50.0, effective_maturity=7.0),
            ],
        )
        expected = (1 / 1.4) * 0.05 * (1.0 * 100 * df(1.0) + 7.0 * 50 * df(7.0))
        assert compute_scva(cp).scva == pytest.approx(expected)

    def test_netting_set_maturity_from_positions_no_floor_or_cap(self) -> None:
        ns = BACVANettingSet(ead=10.0, positions=[
            BACVAPosition(notional=100.0, remaining_maturity=0.25),
            BACVAPosition(notional=100.0, remaining_maturity=12.0),
        ])
        assert ns.maturity == pytest.approx(6.125)
        short = BACVANettingSet(ead=10.0, positions=[BACVAPosition(notional=1.0, remaining_maturity=0.3)])
        assert short.maturity == 0.3
        assert short.discount_factor == pytest.approx(supervisory_discount_factor(0.3))
        long_ = BACVANettingSet(ead=10.0, positions=[BACVAPosition(notional=1.0, remaining_maturity=9.0)])
        assert long_.maturity == 9.0

    def test_sovereign_spec_vs_sub_spec(self) -> None:
        sov = CVASector.SOVEREIGN_MDB_SUPRANATIONAL
        spec = BACVACounterparty(counterparty_id="S", sector=sov, credit_quality=SPEC,
                                 ead=100.0, effective_maturity=1.0)
        sub = BACVACounterparty(counterparty_id="U", sector=sov, rating="CCC",
                                ead=100.0, effective_maturity=1.0)
        assert compute_scva(spec).risk_weight == 0.03
        assert compute_scva(sub).risk_weight == 0.07

    def test_two_counterparties_k_unhedged(self, calc) -> None:
        """K_unhedged = sqrt((0.5·ΣSCVA)² + 0.75·ΣSCVA²)."""
        cps = [fin_ig("A", 100.0, 2.0), fin_ig("B", 40.0, 5.0)]
        result = calc.calculate(cps)
        s = [r.scva for r in result.counterparty_results]
        expected = math.sqrt((0.5 * sum(s)) ** 2 + 0.75 * sum(x * x for x in s))
        assert result.k_unhedged == pytest.approx(expected)
        assert compute_k_unhedged(s) == pytest.approx(expected)
        assert result.k_basic == pytest.approx(0.65 * expected)
        # Diversification: combined < sum of standalone
        assert expected < sum(s)

    def test_ead_linearity_and_rwa(self, calc) -> None:
        r1 = calc.calculate([fin_ig(ead=100.0)])
        r2 = calc.calculate([fin_ig(ead=200.0)])
        assert r2.k_basic == pytest.approx(2.0 * r1.k_basic)
        assert r2.rwa == pytest.approx(12.5 * r2.k_basic)

    def test_summary_and_empty(self, calc) -> None:
        assert compute_scva_summary([fin_ig()])["CP1"] > 0
        empty = calc.calculate([])
        assert empty.k_basic == 0.0 and empty.rwa == 0.0

    def test_validation(self) -> None:
        with pytest.raises(ValueError):
            BACVACounterparty(counterparty_id="X", sector=FIN, credit_quality=IG,
                              ead=-1.0, effective_maturity=1.0)
        with pytest.raises(ValueError):
            BACVACounterparty(counterparty_id="X", sector=FIN, ead=1.0, effective_maturity=1.0)
        with pytest.raises(ValueError):
            BACVACounterparty(counterparty_id="X", sector=FIN, credit_quality=IG)


# =========================================================================
#  Hedged BA-CVA
# =========================================================================

class TestHedges:
    def test_direct_single_name_hedge_closed_form(self, calc) -> None:
        """r_hc = 1: SNH = RW·M·B·DF, HMA = 0, K_hedged = |SCVA − SNH|."""
        cp = fin_ig()
        hedge = BACVAHedge(
            hedge_id="H1", hedge_type="SINGLE_NAME_CDS", counterparty_id="CP1",
            notional=50.0, maturity=2.0, reference_sector=FIN, reference_credit_quality=IG,
        )
        result = calc.calculate([cp], [hedge])
        scva = (1 / 1.4) * 0.05 * 2.0 * 100.0 * df(2.0)
        snh = 1.0 * 0.05 * 2.0 * 50.0 * df(2.0)
        cp_res = result.counterparty_results[0]
        assert cp_res.snh == pytest.approx(snh)
        assert cp_res.hma == 0.0
        assert result.hedge_mismatch_component == 0.0
        assert result.k_hedged == pytest.approx(abs(scva - snh))
        assert result.k_hedged == pytest.approx(
            math.sqrt((0.5 * (scva - snh)) ** 2 + 0.75 * (scva - snh) ** 2)
        )
        assert result.k_basic == pytest.approx(0.65 * (0.25 * scva + 0.75 * abs(scva - snh)))
        assert result.k_basic < 0.65 * scva
        assert result.approach is CVAApproach.BA_CVA_FULL
        assert result.hedge_count == 1

    def test_perfect_hedge_floors_at_quarter(self, calc) -> None:
        """K_hedged = 0 ⇒ K_basic = 0.65·0.25·K_unhedged (preamble pp. 456–457)."""
        cp = fin_ig()
        # SNH = SCVA when B = EAD / α (same RW, M, DF)
        hedge = BACVAHedge(
            hedge_id="H", hedge_type="SINGLE_NAME_CDS", counterparty_id="CP1",
            notional=100.0 / 1.4, maturity=2.0, reference_sector=FIN, reference_credit_quality=IG,
        )
        result = calc.calculate([cp], [hedge])
        assert result.k_hedged == pytest.approx(0.0, abs=1e-12)
        assert result.k_basic == pytest.approx(0.65 * 0.25 * result.k_unhedged)

    def test_affiliate_hedge_hma(self, calc) -> None:
        """r_hc = 0.8: SNH = 0.8·A, HMA = (1 − 0.64)·A², A = RW·M·B·DF."""
        cp = fin_ig()
        hedge = BACVAHedge(
            hedge_id="H", hedge_type="CONTINGENT_CDS", counterparty_id="CP1",
            relationship="AFFILIATE", notional=30.0, maturity=3.0,
            reference_sector=FIN, reference_credit_quality=SPEC,
        )
        result = calc.calculate([cp], [hedge])
        a = 0.12 * 3.0 * 30.0 * df(3.0)
        scva = result.counterparty_results[0].scva
        snh = 0.8 * a
        hma = (1 - 0.8 ** 2) * a ** 2
        assert result.counterparty_results[0].snh == pytest.approx(snh)
        assert result.counterparty_results[0].hma == pytest.approx(hma)
        expected = math.sqrt((0.5 * (scva - snh)) ** 2 + 0.75 * (scva - snh) ** 2 + hma)
        assert result.k_hedged == pytest.approx(expected)
        k_h, sys_, idio, hma_tot = compute_k_hedged([scva - snh], [hma], 0.0)
        assert k_h == pytest.approx(expected)
        assert hma_tot == pytest.approx(hma)

    def test_same_sector_region_hedge_correlation(self) -> None:
        h = BACVAHedge(
            hedge_id="H", hedge_type="SINGLE_NAME_CDS", counterparty_id="CP1",
            relationship="SAME_SECTOR_REGION", notional=1.0, maturity=1.0,
            reference_sector=FIN, reference_credit_quality=IG,
        )
        assert h.correlation == 0.5

    def test_index_hedge_times_0_7(self, calc) -> None:
        """IH = 0.7·RW·M·B·DF; K_hedged = sqrt((0.5·ΣSCVA − IH)² + 0.75·ΣSCVA²)."""
        cps = [fin_ig("A", 100.0, 2.0), fin_ig("B", 60.0, 3.0)]
        hedge = BACVAHedge(
            hedge_id="IDX", hedge_type="INDEX_CDS", notional=40.0, maturity=5.0,
            reference_sector=FIN, reference_credit_quality=IG,
        )
        result = calc.calculate(cps, [hedge])
        ih = 0.7 * 0.05 * 5.0 * 40.0 * df(5.0)
        assert hedge.risk_weight == pytest.approx(0.7 * 0.05)
        assert result.index_hedge_amount == pytest.approx(ih)
        s = [r.scva for r in result.counterparty_results]
        expected = math.sqrt((0.5 * sum(s) - ih) ** 2 + 0.75 * sum(x * x for x in s))
        assert result.k_hedged == pytest.approx(expected)
        assert result.hedge_mismatch_component == 0.0
        assert result.k_basic < 0.65 * result.k_unhedged

    def test_mixed_index_notional_weighted_rw(self) -> None:
        hedge = BACVAHedge(
            hedge_id="IDX", hedge_type="INDEX_CDS", notional=10.0, maturity=5.0,
            constituents=[
                BACVAIndexConstituent(weight=3.0, sector=FIN, credit_quality=IG),            # 5%
                BACVAIndexConstituent(weight=1.0, sector="TECHNOLOGY_TELECOM", credit_quality="BB"),  # 5.5%
            ],
        )
        assert hedge.risk_weight == pytest.approx(0.7 * (3 * 0.05 + 1 * 0.055) / 4)

    def test_hedge_validation(self) -> None:
        with pytest.raises(ValueError):
            BACVAHedge(hedge_id="H", hedge_type="SINGLE_NAME_CDS", notional=1.0, maturity=1.0,
                       reference_sector=FIN, reference_credit_quality=IG)  # no counterparty
        with pytest.raises(ValueError):
            BACVAHedge(hedge_id="H", hedge_type="INDEX_CDS", notional=1.0, maturity=1.0)
        with pytest.raises(ValueError):
            BACVAHedge(hedge_id="H", hedge_type="TOTAL_RETURN_SWAP", notional=1.0, maturity=1.0,
                       counterparty_id="CP1", reference_sector=FIN, reference_credit_quality=IG)

    def test_unknown_counterparty_rejected(self, calc) -> None:
        hedge = BACVAHedge(
            hedge_id="H", hedge_type="SINGLE_NAME_CDS", counterparty_id="NOPE",
            notional=1.0, maturity=1.0, reference_sector=FIN, reference_credit_quality=IG,
        )
        with pytest.raises(ValueError, match="unknown counterparty"):
            calc.calculate([fin_ig()], [hedge])

    def test_k_basic_formula(self) -> None:
        assert compute_k_basic(10.0, 4.0) == pytest.approx(0.65 * (0.25 * 10 + 0.75 * 4))
        assert BA_CVA_DISCOUNT_SCALAR == 0.65

    def test_calculate_reduced_and_full_wrappers(self, calc) -> None:
        cp = fin_ig()
        assert calc.calculate_reduced([cp]).approach is CVAApproach.BA_CVA_REDUCED
        hedge = BACVAHedge(
            hedge_id="H", hedge_type="SINGLE_NAME_CDS", counterparty_id="CP1",
            notional=1.0, maturity=1.0, reference_sector=FIN, reference_credit_quality=IG,
        )
        assert calc.calculate_full([cp], [hedge]).approach is CVAApproach.BA_CVA_FULL
