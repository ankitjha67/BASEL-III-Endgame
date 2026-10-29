"""Tests for the BCBS Pillar 1 package (src/jurisdictions/bcbs/pillar1).

Table cells are asserted against the values read from the Basel Framework
(CRE42 Tables 1-4, CRE44 Table 1, MAR50 Tables 3-14), together with
hand-worked SEC-SA / SEC-IRBA / ERBA examples, SA-CVA single- and cross-bucket
cases, leverage aggregation, large-exposure limit edges, CCP K_CM and protocol
conformance.

References:
    - Basel Framework CRE40-CRE45, CRE54, MAR50.27-50.77, LEV30, LEX10-LEX40
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import AssetClass, Jurisdiction, RatingBucket
from src.jurisdictions.bcbs.pillar1 import BCBSPillar1, BCBSPillar1Options
from src.jurisdictions.bcbs.pillar1 import ccp as ccp_mod
from src.jurisdictions.bcbs.pillar1 import large_exposures as lex
from src.jurisdictions.bcbs.pillar1 import leverage as lev
from src.jurisdictions.bcbs.pillar1 import params as p
from src.jurisdictions.bcbs.pillar1 import sa_cva as sacva
from src.jurisdictions.bcbs.pillar1 import securitisation as sec
from src.jurisdictions.pillar1_base import (
    CCPCalculator,
    CCPExposureInput,
    CVARiskClass,
    CVASensitivityInput,
    LargeExposureInput,
    LargeExposuresCalculator,
    LeverageCalculator,
    LeverageInputs,
    SACVACalculator,
    SecApproachUsed,
    SecTrancheInput,
    SecuritisationCalculator,
)

CALC = BCBSPillar1()


def _ssfa(k: float, a_pt: float, d_pt: float, p_: float) -> float:
    """Independent re-statement of CRE41.11 / CRE41.13 for the hand examples."""
    if d_pt <= k:
        return 12.5
    a = -1.0 / (p_ * k)
    u = d_pt - k
    lo = max(a_pt - k, 0.0)
    kssfa = (math.exp(a * u) - math.exp(a * lo)) / (a * (u - lo))
    if a_pt >= k:
        return 12.5 * kssfa
    return 12.5 * (k - a_pt) / (d_pt - a_pt) + 12.5 * kssfa * (d_pt - k) / (d_pt - a_pt)


def _tranche(**kw: object) -> SecTrancheInput:
    base: dict[str, object] = {"tranche_id": "T", "exposure_amount": 100.0,
                               "attachment": 0.05, "detachment": 0.15}
    base.update(kw)
    return SecTrancheInput.model_validate(base)


# =========================================================================
#  Protocol conformance
# =========================================================================


@pytest.mark.parametrize("proto", [SecuritisationCalculator, SACVACalculator,
                                   LeverageCalculator, LargeExposuresCalculator,
                                   CCPCalculator])
def test_protocol_conformance(proto: type) -> None:
    assert isinstance(CALC, proto)
    assert CALC.jurisdiction == Jurisdiction.BCBS


# =========================================================================
#  CRE42 tables
# =========================================================================

ERBA_TABLE2 = {
    "AAA": (15, 20, 15, 70), "AA+": (15, 30, 15, 90), "AA": (25, 40, 30, 120),
    "AA-": (30, 45, 40, 140), "A+": (40, 50, 60, 160), "A": (50, 65, 80, 180),
    "A-": (60, 70, 120, 210), "BBB+": (75, 90, 170, 260), "BBB": (90, 105, 220, 310),
    "BBB-": (120, 140, 330, 420), "BB+": (140, 160, 470, 580), "BB": (160, 180, 620, 760),
    "BB-": (200, 225, 750, 860), "B+": (250, 280, 900, 950), "B": (310, 340, 1050, 1050),
    "B-": (380, 420, 1130, 1130), "CCC+/CCC/CCC-": (460, 505, 1250, 1250),
    "Below CCC-": (1250, 1250, 1250, 1250),
}
ERBA_TABLE4 = {
    "AAA": (10, 10, 15, 40), "AA+": (10, 15, 15, 55), "AA": (15, 20, 15, 70),
    "AA-": (15, 25, 25, 80), "A+": (20, 30, 35, 95), "A": (30, 40, 60, 135),
    "A-": (35, 40, 95, 170), "BBB+": (45, 55, 150, 225), "BBB": (55, 65, 180, 255),
    "BBB-": (70, 85, 270, 345), "BB+": (120, 135, 405, 500), "BB": (135, 155, 535, 655),
    "BB-": (170, 195, 645, 740), "B+": (225, 250, 810, 855), "B": (280, 305, 945, 945),
    "B-": (340, 380, 1015, 1015), "CCC+/CCC/CCC-": (415, 455, 1250, 1250),
    "Below CCC-": (1250, 1250, 1250, 1250),
}


@pytest.mark.parametrize("grade", list(ERBA_TABLE2))
def test_erba_table2_cells(grade: str) -> None:
    assert p.ERBA_LONG_TERM_RW[grade] == pytest.approx(tuple(x / 100 for x in ERBA_TABLE2[grade]))


@pytest.mark.parametrize("grade", list(ERBA_TABLE4))
def test_erba_table4_cells(grade: str) -> None:
    got = p.ERBA_STC_LONG_TERM_RW[grade]
    assert got == pytest.approx(tuple(x / 100 for x in ERBA_TABLE4[grade]))


def test_erba_short_term_tables() -> None:
    assert sec.erba_short_term_risk_weight("A-1/P-1") == 0.15
    assert sec.erba_short_term_risk_weight("A-2/P-2") == 0.50
    assert sec.erba_short_term_risk_weight("A-3/P-3") == 1.00
    assert sec.erba_short_term_risk_weight("NP") == 12.5
    assert sec.erba_short_term_risk_weight("A-1/P-1", stc=True) == 0.10
    assert sec.erba_short_term_risk_weight("A-2/P-2", stc=True) == 0.30
    assert sec.erba_short_term_risk_weight("A-3/P-3", stc=True) == 0.60
    assert sec.erba_short_term_risk_weight("B", stc=True) == 12.5


def test_erba_maturity_interpolation_senior() -> None:
    # CRE42.5(1): A senior, M_T = 3 -> 50% + (65% - 50%) x 2/4 = 57.5%
    assert sec.erba_long_term_risk_weight("A", True, 3.0, 0.5) == pytest.approx(0.575)
    # M_T floor 1 / cap 5 (CRE40.22)
    assert sec.erba_long_term_risk_weight("A", True, 0.2, 0.5) == pytest.approx(0.50)
    assert sec.erba_long_term_risk_weight("A", True, 9.0, 0.5) == pytest.approx(0.65)


def test_erba_thickness_non_senior() -> None:
    # BBB non-senior, M_T = 2: 220% + 90% x 1/4 = 242.5%; T = 0.10 -> x 0.9 = 218.25%
    rw = sec.erba_long_term_risk_weight("BBB", False, 2.0, 0.10)
    assert rw == pytest.approx(2.425 * 0.9)
    # T above 50% capped at 50% (CRE42.5(2))
    rw = sec.erba_long_term_risk_weight("BB", False, 1.0, 0.8)
    assert rw == pytest.approx(6.20 * 0.5)


def test_erba_non_senior_not_below_senior_and_floor() -> None:
    # AAA non-senior 1y 15% x (1 - 0.5) = 7.5% -> floor 15% and >= senior 15% (CRE42.7)
    assert sec.erba_long_term_risk_weight("AAA", False, 1.0, 0.6) == pytest.approx(0.15)
    # AA non-senior 1y: 30% x 0.5 = 15% < senior 25% -> 25%
    assert sec.erba_long_term_risk_weight("AA", False, 1.0, 0.9) == pytest.approx(0.25)


def test_erba_stc_floors_and_no_senior_comparison() -> None:
    # STC AAA senior 10%; non-senior 15% x (1 - 0.5) = 7.5% -> 15% floor (CRE42.14)
    assert sec.erba_long_term_risk_weight("AAA", True, 1.0, 0.5, stc=True) == pytest.approx(0.10)
    assert sec.erba_long_term_risk_weight("AAA", False, 1.0, 0.9, stc=True) == pytest.approx(0.15)
    # STC AA non-senior 1y: 15% x 0.5 -> 15% floor; STC senior AA 1y 15% (no CRE42.7 test)
    assert sec.erba_long_term_risk_weight("AA-", False, 1.0, 0.9, stc=True) == pytest.approx(0.15)


@pytest.mark.parametrize("raw,norm", [("aa-", "AA-"), ("CCC", "CCC+/CCC/CCC-"),
                                      ("CCC-", "CCC+/CCC/CCC-"), ("CC", "Below CCC-"),
                                      ("D", "Below CCC-"), ("BBB+", "BBB+")])
def test_rating_normalisation(raw: str, norm: str) -> None:
    assert sec.normalise_long_term_rating(raw) == norm


def test_rating_unknown() -> None:
    with pytest.raises(ValueError):
        sec.normalise_long_term_rating("XYZ")


# =========================================================================
#  SEC-SA
# =========================================================================


def test_k_a_formula() -> None:
    # CRE41.8: (1 - 0.1) x 0.08 + 0.5 x 0.1 = 0.122
    assert sec.k_a(0.08, 0.10) == pytest.approx(0.122)


def test_k_a_unknown_w() -> None:
    # CRE41.9: 96 known with K_A 0.10, 4 unknown -> 0.96 x 0.10 + 0.04 = 0.136
    assert sec.k_a_partially_unknown_w(96.0, 0.10, 4.0) == pytest.approx(0.136)
    # CRE41.10: >5% unknown -> None (1250%)
    assert sec.k_a_partially_unknown_w(94.0, 0.10, 6.0) is None


def test_sec_sa_mezzanine_hand_example() -> None:
    # K_SA 8%, W 0, A 5%, D 15%, p 1 -> straddle: 12.5x0.3 + 12.5 x K_SSFA x 0.7
    kssfa = (math.exp(-12.5 * 0.07) - 1.0) / (-12.5 * 0.07)
    expected = 12.5 * 0.03 / 0.10 + 12.5 * kssfa * 0.07 / 0.10
    assert expected == pytest.approx(9.5814, abs=1e-4)
    r = CALC.securitisation(_tranche(k_sa=0.08))
    assert r.approach == SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(expected)
    assert r.rwa == pytest.approx(100.0 * expected)


def test_sec_sa_first_loss_1250() -> None:
    r = CALC.securitisation(_tranche(k_sa=0.08, attachment=0.0, detachment=0.08))
    assert r.risk_weight == 12.5  # D <= K_A (CRE41.13(1))


def test_sec_sa_senior_floor_15() -> None:
    r = CALC.securitisation(_tranche(k_sa=0.08, attachment=0.30, detachment=1.0, is_senior=True))
    assert _ssfa(0.08, 0.30, 1.0, 1.0) < 0.15
    assert r.risk_weight == pytest.approx(0.15)


def test_sec_sa_mezz_above_ka() -> None:
    t = _tranche(k_sa=0.04, w=0.05, attachment=0.10, detachment=0.20)
    ka = 0.95 * 0.04 + 0.5 * 0.05
    assert CALC.securitisation(t).risk_weight == pytest.approx(
        max(_ssfa(ka, 0.10, 0.20, 1.0), 0.15))


def test_sec_sa_stc_p_and_floors() -> None:
    t = _tranche(k_sa=0.08, attachment=0.10, detachment=0.30, is_stc=True)
    assert CALC.securitisation(t).risk_weight == pytest.approx(
        max(_ssfa(0.08, 0.10, 0.30, 0.5), 0.15))
    senior = _tranche(k_sa=0.08, attachment=0.30, detachment=1.0, is_stc=True, is_senior=True)
    assert CALC.securitisation(senior).risk_weight == pytest.approx(0.10)


def test_stc_synthetic_ignored() -> None:
    t = _tranche(k_sa=0.08, attachment=0.30, detachment=1.0, is_stc=True, is_senior=True,
                 is_synthetic=True)
    r = CALC.securitisation(t)
    assert r.risk_weight == pytest.approx(0.15)
    assert any("CRE40.66" in n for n in r.notes)


def test_resecuritisation() -> None:
    t = _tranche(k_sa=0.10, attachment=0.20, detachment=0.40, is_resecuritisation=True,
                 external_rating="AAA", k_irb=0.05, lgd_pool=0.4, n_effective=100)
    r = CALC.securitisation(t)
    assert r.approach == SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(max(_ssfa(0.10, 0.20, 0.40, 1.5), 1.0))
    senior = _tranche(k_sa=0.02, attachment=0.5, detachment=1.0, is_resecuritisation=True)
    assert CALC.securitisation(senior).risk_weight == pytest.approx(1.0)  # CRE41.18 floor


def test_delinquency_unknown_1250() -> None:
    t = _tranche(k_sa=0.08, flags={"delinquency_unknown_over_5pct": True})
    assert CALC.securitisation(t).risk_weight == 12.5


# =========================================================================
#  SEC-IRBA
# =========================================================================

IRBA_TABLE1 = {
    "WHOLESALE_SENIOR_GRANULAR": (0, 3.56, -1.85, 0.55, 0.07),
    "WHOLESALE_SENIOR_NON_GRANULAR": (0.11, 2.61, -2.91, 0.68, 0.07),
    "WHOLESALE_NON_SENIOR_GRANULAR": (0.16, 2.87, -1.03, 0.21, 0.07),
    "WHOLESALE_NON_SENIOR_NON_GRANULAR": (0.22, 2.35, -2.46, 0.48, 0.07),
    "RETAIL_SENIOR": (0, 0, -7.48, 0.71, 0.24),
    "RETAIL_NON_SENIOR": (0, 0, -5.78, 0.55, 0.27),
}


@pytest.mark.parametrize("row", list(IRBA_TABLE1))
def test_irba_table1_cells(row: str) -> None:
    assert p.IRBA_P_TABLE[row] == pytest.approx(IRBA_TABLE1[row])


def test_irba_p_hand_example() -> None:
    # Wholesale senior granular, N = 100, K_IRB 6%, LGD 40%, M_T 3:
    # p = 3.56/100 - 1.85 x 0.06 + 0.55 x 0.4 + 0.07 x 3 = 0.3546
    assert sec.irba_p(0.06, 0.4, 3.0, True, False, 100.0) == pytest.approx(0.3546)
    # STC: max(0.3, 0.5 x 0.3546) = 0.3
    assert sec.irba_p(0.06, 0.4, 3.0, True, False, 100.0, stc=True) == pytest.approx(0.3)


def test_irba_p_floor_and_retail() -> None:
    # Retail senior: -7.48 x 0.1 + 0.71 x 0.5 + 0.24 x 1 = -0.153 -> 0.3
    assert sec.irba_p(0.10, 0.5, 1.0, True, True, None) == pytest.approx(0.3)
    # Retail non-senior: -5.78 x 0.02 + 0.55 x 0.6 + 0.27 x 5 = 1.5644
    assert sec.irba_p(0.02, 0.6, 5.0, False, True, None) == pytest.approx(1.5644)


def test_irba_granularity_boundary() -> None:
    assert sec.irba_p_row(False, False, 25.0) == "WHOLESALE_NON_SENIOR_GRANULAR"
    assert sec.irba_p_row(False, False, 24.99) == "WHOLESALE_NON_SENIOR_NON_GRANULAR"


def test_sec_irba_hand_example() -> None:
    t = _tranche(k_irb=0.06, lgd_pool=0.4, n_effective=100.0, maturity_years=3.0,
                 attachment=0.04, detachment=0.12, k_sa=0.08, external_rating="A")
    r = CALC.securitisation(t)
    assert r.approach == SecApproachUsed.SEC_IRBA
    p_ns = 0.16 + 2.87 / 100 - 1.03 * 0.06 + 0.21 * 0.4 + 0.07 * 3.0
    assert r.risk_weight == pytest.approx(max(_ssfa(0.06, 0.04, 0.12, p_ns), 0.15))


def test_irba_missing_inputs_raise() -> None:
    with pytest.raises(ValueError):
        CALC.securitisation(_tranche(k_irb=0.06))


def test_irba_stc_senior_floor_10() -> None:
    t = _tranche(k_irb=0.02, lgd_pool=0.3, n_effective=500.0, attachment=0.3, detachment=1.0,
                 is_senior=True, is_stc=True)
    assert CALC.securitisation(t).risk_weight == pytest.approx(0.10)


def test_effective_number_and_lgd() -> None:
    assert sec.effective_number([1.0, 1.0, 2.0]) == pytest.approx(16.0 / 6.0)
    assert sec.weighted_lgd([0.4, 0.6], [1.0, 3.0]) == pytest.approx(0.55)
    assert sec.simplified_n(0.02) == pytest.approx(50.0)
    # CRE44.22(1): C1 0.02, C_m 0.10, m 5: N = 1/(0.002 + 0.08 x 0.9 / 4) = 1/0.02
    assert sec.simplified_n(0.02, 0.10, 5) == pytest.approx(50.0)
    with pytest.raises(ValueError):
        sec.simplified_n(0.05)


def test_mixed_pool() -> None:
    assert sec.mixed_pool_capital(0.96, 0.05, 0.08) == pytest.approx(0.96 * 0.05 + 0.04 * 0.08)
    with pytest.raises(ValueError):
        sec.mixed_pool_capital(0.90, 0.05, 0.08)


# =========================================================================
#  Hierarchy, maturity, caps, NPL
# =========================================================================


def test_tranche_maturity() -> None:
    assert sec.tranche_maturity_from_legal(6.0) == pytest.approx(5.0)
    assert sec.tranche_maturity_from_legal(3.0) == pytest.approx(2.6)
    assert sec.tranche_maturity_from_cash_flows([(1.0, 50.0), (3.0, 50.0)]) == pytest.approx(2.0)
    assert sec.tranche_maturity_from_cash_flows([(0.25, 10.0)]) == pytest.approx(1.0)


def test_hierarchy_order() -> None:
    erba = CALC.securitisation(_tranche(external_rating="A", k_sa=0.08, is_senior=True))
    assert erba.approach == SecApproachUsed.SEC_ERBA
    no_erba = BCBSPillar1(BCBSPillar1Options(sec_erba_permitted=False))
    assert no_erba.securitisation(
        _tranche(external_rating="A", k_sa=0.08)).approach == SecApproachUsed.SEC_SA
    iaa = CALC.securitisation(_tranche(internal_assessment_rating="BBB", k_sa=0.08))
    assert iaa.approach == SecApproachUsed.SEC_IAA
    none = CALC.securitisation(_tranche())
    assert none.approach == SecApproachUsed.RW_1250 and none.risk_weight == 12.5
    dd = CALC.securitisation(_tranche(k_sa=0.08, flags={"due_diligence_failed": True}))
    assert dd.risk_weight == 12.5 and dd.citation == "CRE40.31"
    barred = CALC.securitisation(_tranche(k_irb=0.05, k_sa=0.08,
                                          flags={"irba_not_permitted": True}))
    assert barred.approach == SecApproachUsed.SEC_SA


def test_short_term_rating_erba() -> None:
    r = CALC.securitisation(_tranche(short_term_rating="A-2/P-2"))
    assert r.risk_weight == pytest.approx(0.50)


def test_senior_look_through_cap() -> None:
    t = _tranche(external_rating="BB", k_sa=0.04, attachment=0.3, detachment=1.0,
                 is_senior=True, maturity_years=1.0, flags={"senior_look_through_cap": True})
    r = CALC.securitisation(t)
    assert r.approach == SecApproachUsed.LOOK_THROUGH
    assert r.risk_weight == pytest.approx(0.50)  # 12.5 x 0.04
    low = _tranche(external_rating="A", k_sa=0.008, attachment=0.3, detachment=1.0,
                   is_senior=True, flags={"senior_look_through_cap": True})
    assert CALC.securitisation(low).risk_weight == pytest.approx(0.10)  # CRE40.51 below 15%


def test_npl_floor_and_senior_100() -> None:
    t = _tranche(k_sa=0.02, attachment=0.5, detachment=1.0, is_senior=True,
                 is_npl_securitisation=True, w=0.0)
    assert CALC.securitisation(t).risk_weight == pytest.approx(1.0)  # CRE45.4
    t2 = _tranche(k_sa=0.40, w=0.95, attachment=0.5, detachment=1.0, is_senior=True,
                  is_npl_securitisation=True, flags={"npl_nrppd_at_least_50pct": True})
    assert CALC.securitisation(t2).risk_weight == pytest.approx(1.0)  # CRE45.5
    t3 = t2.model_copy(update={"flags": {}})
    assert CALC.securitisation(t3).risk_weight > 1.0
    f_irb = _tranche(k_irb=0.3, lgd_pool=0.5, n_effective=50, k_sa=0.4, w=0.95,
                     is_npl_securitisation=True, flags={"kirb_foundation_approach": True})
    assert CALC.securitisation(f_irb).approach == SecApproachUsed.SEC_SA  # CRE45.3


def test_transaction_cap() -> None:
    rows = [CALC.securitisation(_tranche(tranche_id="a", k_sa=0.08, exposure_amount=10.0)),
            CALC.securitisation(_tranche(tranche_id="b", k_sa=0.08, attachment=0.15,
                                         detachment=0.30, exposure_amount=10.0))]
    capped = sec.apply_transaction_cap(rows, k_p=0.08, share_p=0.10, pool_exposure=100.0)
    assert sum(r.rwa for r in capped) == pytest.approx(12.5 * 0.08 * 0.10 * 100.0)
    loose = sec.apply_transaction_cap(rows, k_p=0.08, share_p=1.0, pool_exposure=1e6)
    assert [r.rwa for r in loose] == [r.rwa for r in rows]


def test_ssfa_edge_k_zero() -> None:
    assert sec.k_ssfa(0.0, 0.0, 0.1, 1.0) == 0.0
    with pytest.raises(ValueError):
        sec.k_ssfa(0.05, 0.2, 0.2, 1.0)


# =========================================================================
#  SA-CVA
# =========================================================================


def _s(rc: CVARiskClass, bucket: str, rf: str = "", s_cva: float = 0.0, s_hedge: float = 0.0,
       measure: str = "DELTA", **kw: object) -> CVASensitivityInput:
    d: dict[str, object] = {"risk_class": rc, "measure": measure, "bucket": bucket,
                            "risk_factor": rf, "s_cva": s_cva, "s_hedge": s_hedge}
    d.update(kw)
    return CVASensitivityInput.model_validate(d)


def test_cva_constants() -> None:
    assert p.M_CVA == 1.0 and p.R_HEDGING_DISALLOWANCE == 0.01


@pytest.mark.parametrize("tenor,rw", [("1Y", 0.0111), ("2Y", 0.0093), ("5Y", 0.0074),
                                      ("10Y", 0.0074), ("30Y", 0.0074), ("INFLATION", 0.0111)])
def test_ir_table3(tenor: str, rw: float) -> None:
    assert sacva.risk_weight(_s(CVARiskClass.INTEREST_RATE, "EUR", tenor)) == rw


def test_ir_table4_cells() -> None:
    t = p.IR_DELTA_CORR_SPECIFIED
    assert (t[("1Y", "2Y")], t[("1Y", "5Y")], t[("1Y", "10Y")], t[("1Y", "30Y")]) == (
        0.91, 0.72, 0.55, 0.31)
    assert (t[("2Y", "5Y")], t[("2Y", "10Y")], t[("2Y", "30Y")]) == (0.87, 0.72, 0.45)
    assert (t[("5Y", "10Y")], t[("5Y", "30Y")], t[("10Y", "30Y")]) == (0.91, 0.68, 0.83)
    assert all(v == 0.40 for k, v in t.items() if "INFLATION" in k)


def test_ir_other_currency_and_reporting_currency() -> None:
    assert sacva.risk_weight(_s(CVARiskClass.INTEREST_RATE, "BRL", "CURVE")) == 0.0158
    calc = BCBSPillar1(BCBSPillar1Options(reporting_currency="CHF"))
    res = calc.sa_cva([_s(CVARiskClass.INTEREST_RATE, "CHF", "5Y", s_cva=100.0)])
    assert res.k_total == pytest.approx(0.74)
    with pytest.raises(ValueError):
        sacva.risk_weight(_s(CVARiskClass.INTEREST_RATE, "BRL", "5Y"))


def test_ir_single_bucket_two_tenors() -> None:
    sens = [_s(CVARiskClass.INTEREST_RATE, "USD", "1Y", s_cva=100.0),
            _s(CVARiskClass.INTEREST_RATE, "USD", "10Y", s_cva=-50.0)]
    ws1, ws2 = 0.0111 * 100, 0.0074 * -50
    kb = math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * 0.55 * ws1 * ws2)
    res = CALC.sa_cva(sens)
    assert res.k_by_class["INTEREST_RATE_DELTA"] == pytest.approx(kb)
    assert res.rwa == pytest.approx(12.5 * kb)


def test_hedging_disallowance() -> None:
    # Perfect hedge on one factor: WS = 0, K_b = sqrt(R x WS_hdg^2) = 0.1 x |WS_hdg|
    res = CALC.sa_cva([_s(CVARiskClass.FX, "EUR", s_cva=1000.0, s_hedge=1000.0)])
    assert res.k_total == pytest.approx(math.sqrt(0.01) * 0.11 * 1000.0)


def test_fx_cross_bucket() -> None:
    sens = [_s(CVARiskClass.FX, "EUR", s_cva=100.0), _s(CVARiskClass.FX, "GBP", s_cva=200.0)]
    k1, k2 = 11.0, 22.0
    expected = math.sqrt(k1 ** 2 + k2 ** 2 + 2 * 0.6 * k1 * k2)
    assert CALC.sa_cva(sens).k_total == pytest.approx(expected)
    with pytest.raises(ValueError):
        CALC.sa_cva([_s(CVARiskClass.FX, "USD", s_cva=1.0)])


def test_cross_bucket_sb_bounding() -> None:
    # S_b bounded by K_b: hedged buckets with R term make K_b > |sum WS|
    kb = {"A": 2.0, "B": 3.0}
    sb = {"A": 5.0, "B": -1.0}
    k = sacva.class_capital(kb, sb, lambda _b, _c: 0.5)
    assert k == pytest.approx(math.sqrt(4 + 9 + 2 * 0.5 * 2.0 * -1.0))


@pytest.mark.parametrize("bucket,ig,hy", [("1a", 0.005, 0.02), ("1b", 0.01, 0.04),
                                          ("2", 0.05, 0.12), ("3", 0.03, 0.07),
                                          ("4", 0.03, 0.085), ("5", 0.02, 0.055),
                                          ("6", 0.015, 0.05), ("7", 0.05, 0.12),
                                          ("8", 0.015, 0.05)])
def test_ccs_table7(bucket: str, ig: float, hy: float) -> None:
    rc = CVARiskClass.COUNTERPARTY_CREDIT_SPREAD
    assert sacva.risk_weight(_s(rc, bucket, "5Y", is_investment_grade=True)) == ig
    assert sacva.risk_weight(_s(rc, bucket, "5Y", is_investment_grade=False)) == hy
    assert sacva.risk_weight(_s(rc, bucket, "5Y")) == hy  # not rated


def test_ccs_table6_cells() -> None:
    assert sacva.ccs_gamma("1", "2") == 0.10 and sacva.ccs_gamma("4", "1") == 0.25
    assert sacva.ccs_gamma("3", "5") == 0.25 and sacva.ccs_gamma("7", "8") == 0.0
    assert sacva.ccs_gamma("6", "8") == 0.45 and sacva.ccs_gamma("2", "6") == 0.05


def test_ccs_intra_bucket_rho() -> None:
    rc = CVARiskClass.COUNTERPARTY_CREDIT_SPREAD
    a = _s(rc, "2", "5Y", name="BankA", is_investment_grade=True)
    b = _s(rc, "2", "1Y", name="BankB", is_investment_grade=False)
    assert sacva.ccs_rho(a, b, False) == pytest.approx(0.9 * 0.5 * 0.8)
    b2 = _s(rc, "2", "5Y", name="BankB", is_investment_grade=True,
            flags={"legally_related:BankA": True})
    assert sacva.ccs_rho(a, b2, False) == pytest.approx(0.9)
    i1 = _s(rc, "8", "5Y", name="CDX.IG:41", is_investment_grade=True)
    i2 = _s(rc, "8", "5Y", name="CDX.IG:40", is_investment_grade=True)
    i3 = _s(rc, "8", "5Y", name="ITRAXX:40", is_investment_grade=True)
    assert sacva.ccs_rho(i1, i2, True) == pytest.approx(0.9)
    assert sacva.ccs_rho(i1, i3, True) == pytest.approx(0.8)


def test_ccs_bucket_aggregation_hand() -> None:
    rc = CVARiskClass.COUNTERPARTY_CREDIT_SPREAD
    sens = [_s(rc, "1a", "5Y", s_cva=1000.0, name="UST", is_investment_grade=True),
            _s(rc, "1b", "5Y", s_cva=500.0, name="CityX", is_investment_grade=True),
            _s(rc, "3", "5Y", s_cva=400.0, name="Corp", is_investment_grade=False)]
    ws1, ws2, ws3 = 0.005 * 1000, 0.01 * 500, 0.07 * 400
    k1 = math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * 0.5 * ws1 * ws2)  # rho_name 50%
    k3 = ws3
    s1, s3 = min(ws1 + ws2, k1), k3
    expected = math.sqrt(k1 ** 2 + k3 ** 2 + 2 * 0.20 * s1 * s3)
    res = CALC.sa_cva(sens)
    assert res.k_by_class["COUNTERPARTY_CREDIT_SPREAD_DELTA"] == pytest.approx(expected)
    with pytest.raises(ValueError):
        CALC.sa_cva([_s(rc, "2", "5Y", measure="VEGA", s_cva=1.0)])


def test_rcs_table10_and_gamma() -> None:
    expected = {1: 0.5, 2: 1.0, 3: 5.0, 4: 3.0, 5: 3.0, 6: 2.0, 7: 1.5, 8: 2.0, 9: 4.0,
                10: 12.0, 11: 7.0, 12: 8.5, 13: 5.5, 14: 5.0, 15: 12.0, 16: 1.5, 17: 5.0}
    for b, rw in expected.items():
        assert p.RCS_DELTA_RW[b] == pytest.approx(rw / 100)
    assert sacva.rcs_gamma(1, 2) == 0.75
    assert sacva.rcs_gamma(1, 9) == pytest.approx(0.375)  # different quality halved
    assert sacva.rcs_gamma(1, 8) == pytest.approx(0.5)    # same sector, IG vs HY: 100%/2
    assert sacva.rcs_gamma(3, 15) == 0.0
    assert sacva.rcs_gamma(16, 17) == 0.75
    assert sacva.rcs_gamma(10, 16) == 0.45                # 16/17 not halved
    assert sacva.rcs_gamma(4, 6) == 0.25


def test_rcs_cross_bucket_case() -> None:
    rc = CVARiskClass.REFERENCE_CREDIT_SPREAD
    sens = [_s(rc, "3", s_cva=100.0), _s(rc, "10", s_cva=-50.0)]
    k3, k10 = 5.0, 6.0
    expected = math.sqrt(k3 ** 2 + k10 ** 2 + 2 * 0.5 * 5.0 * -6.0)
    assert CALC.sa_cva(sens).k_total == pytest.approx(expected)


def test_equity_tables() -> None:
    assert [p.EQ_DELTA_RW[b] for b in range(1, 14)] == pytest.approx(
        [0.55, 0.60, 0.45, 0.55, 0.30, 0.35, 0.40, 0.50, 0.70, 0.50, 0.70, 0.15, 0.25])
    rc = CVARiskClass.EQUITY
    assert sacva.risk_weight(_s(rc, "5", measure="VEGA")) == 0.78
    assert sacva.risk_weight(_s(rc, "9", measure="VEGA")) == 1.00
    assert sacva.risk_weight(_s(rc, "12", measure="VEGA")) == 1.00  # TODO: VERIFY placeholder
    assert sacva.equity_gamma(1, 10) == 0.15 and sacva.equity_gamma(12, 13) == 0.75
    assert sacva.equity_gamma(13, 4) == 0.45 and sacva.equity_gamma(11, 12) == 0.0


def test_commodity_tables_and_vega() -> None:
    assert [p.COM_DELTA_RW[b] for b in range(1, 12)] == pytest.approx(
        [0.30, 0.35, 0.60, 0.80, 0.40, 0.45, 0.20, 0.35, 0.25, 0.35, 0.50])
    assert sacva.commodity_gamma(2, 7) == 0.20 and sacva.commodity_gamma(11, 1) == 0.0
    rc = CVARiskClass.COMMODITY
    sens = [_s(rc, "2", s_cva=10.0), _s(rc, "2", s_cva=10.0, measure="VEGA")]
    res = CALC.sa_cva(sens)
    assert res.k_by_class["COMMODITY_DELTA"] == pytest.approx(3.5)  # 35% x 10
    assert res.k_by_class["COMMODITY_VEGA"] == pytest.approx(10.0)
    assert res.k_total == pytest.approx(13.5)


def test_ir_vega_and_m_cva() -> None:
    rc = CVARiskClass.INTEREST_RATE
    sens = [_s(rc, "USD", "IR_VOL", s_cva=10.0, measure="VEGA"),
            _s(rc, "USD", "INFLATION_VOL", s_cva=10.0, measure="VEGA")]
    kb = math.sqrt(100 + 100 + 2 * 0.4 * 100)
    assert CALC.sa_cva(sens).k_total == pytest.approx(kb)
    calc = BCBSPillar1(BCBSPillar1Options(m_cva=1.5))
    assert calc.sa_cva(sens).k_total == pytest.approx(1.5 * kb)


def test_rows_with_same_factor_are_netted() -> None:
    rc = CVARiskClass.EQUITY
    res = CALC.sa_cva([_s(rc, "5", s_cva=100.0), _s(rc, "5", s_cva=-40.0)])
    assert res.k_total == pytest.approx(0.30 * 60.0)


def test_empty_sa_cva() -> None:
    res = CALC.sa_cva([])
    assert res.k_total == 0.0 and res.rwa == 0.0


# =========================================================================
#  Leverage
# =========================================================================


def test_leverage_aggregation() -> None:
    li = LeverageInputs(on_balance_sheet_assets=1000.0, tier1_deductions=10.0,
                        derivative_rc=50.0, derivative_pfe_addon=30.0,
                        derivative_cash_vm_received=20.0,
                        written_credit_derivative_notional=40.0,
                        written_credit_derivative_offsets=15.0,
                        sft_gross_assets=200.0, sft_netted_cash_payables=50.0,
                        sft_ccr_addon=5.0,
                        obs_notional_by_ccf={1.0: 10.0, 0.4: 100.0, 0.1: 200.0},
                        central_bank_reserves=100.0)
    r = CALC.leverage_exposure(li)
    assert r.on_balance_sheet == pytest.approx(990.0)
    assert r.derivatives == pytest.approx(1.4 * (30.0 + 30.0) + 25.0)
    assert r.sfts == pytest.approx(155.0)
    assert r.off_balance_sheet == pytest.approx(10.0 + 40.0 + 20.0)
    assert r.exclusions == 0.0
    assert r.total_exposure == pytest.approx(990.0 + 109.0 + 155.0 + 70.0)
    exempt = BCBSPillar1(BCBSPillar1Options(central_bank_reserves_exemption=True))
    assert exempt.leverage_exposure(li).total_exposure == pytest.approx(r.total_exposure - 100.0)


def test_leverage_rc_floor_and_flags() -> None:
    li = LeverageInputs(on_balance_sheet_assets=0.0, derivative_rc=10.0,
                        derivative_cash_vm_received=50.0, derivative_pfe_addon=1.0)
    assert CALC.leverage_exposure(li).derivatives == pytest.approx(1.4)
    li2 = li.model_copy(update={"flags": {"rc_net_of_cash_vm": True}})
    assert CALC.leverage_exposure(li2).derivatives == pytest.approx(1.4 * 11.0)


def test_leverage_bad_ccf() -> None:
    with pytest.raises(ValueError):
        CALC.leverage_exposure(LeverageInputs(on_balance_sheet_assets=0.0,
                                              obs_notional_by_ccf={0.75: 1.0}))


def test_sft_current_exposure() -> None:
    assert lev.sft_current_exposure([100.0, 50.0], [90.0, 70.0], True) == pytest.approx(0.0)
    assert lev.sft_current_exposure([100.0, 50.0], [90.0, 70.0], False) == pytest.approx(10.0)


def test_client_cleared_exclusion() -> None:
    li = LeverageInputs(on_balance_sheet_assets=0.0, derivative_rc=10.0,
                        client_cleared_trade_exposures_exempt=5.0)
    r = CALC.leverage_exposure(li)
    assert r.exclusions == pytest.approx(5.0)
    assert r.total_exposure == pytest.approx(14.0 - 5.0)


# =========================================================================
#  Large exposures
# =========================================================================


def _le(cid: str, v: float, **kw: object) -> LargeExposureInput:
    d: dict[str, object] = {"counterparty_id": cid, "exposure_value": v}
    d.update(kw)
    return LargeExposureInput.model_validate(d)


def test_le_limits_and_edges() -> None:
    rows = CALC.large_exposures(
        [_le("at25", 25.0), _le("above25", 25.0001), _le("below10", 9.99), _le("at10", 10.0),
         _le("gsib15", 15.0, counterparty_is_gsib=True),
         _le("gsib15+", 15.01, counterparty_is_gsib=True)],
        tier1_capital=100.0, reporting_bank_is_gsib=True)
    by = {r.counterparty_id: r for r in rows}
    assert not by["at25"].breach and by["above25"].breach  # "must not be higher than 25%"
    assert not by["below10"].reportable and by["at10"].reportable  # ">= 10%"
    assert by["gsib15"].limit_pct_of_tier1 == 0.15 and not by["gsib15"].breach
    assert by["gsib15+"].breach


def test_le_non_gsib_bank_uses_25_for_gsib_counterparty() -> None:
    rows = CALC.large_exposures([_le("g", 20.0, counterparty_is_gsib=True)], 100.0, False)
    assert rows[0].limit_pct_of_tier1 == 0.25 and not rows[0].breach


def test_le_exemptions() -> None:
    rows = CALC.large_exposures(
        [_le("sov", 80.0, counterparty_asset_class=AssetClass.SOVEREIGN),
         _le("pse", 80.0, counterparty_asset_class=AssetClass.PSE,
             flags={"pse_treated_as_sovereign": True}),
         _le("pse2", 80.0, counterparty_asset_class=AssetClass.PSE),
         _le("qccp", 80.0, flags={"qccp_clearing_exposure": True}),
         _le("intraday", 80.0, flags={"intraday_interbank": True}),
         _le("other", 80.0, is_exempt=True)], 100.0, False)
    by = {r.counterparty_id: r for r in rows}
    assert not by["sov"].breach and by["sov"].reportable
    assert not by["pse"].breach and by["pse2"].breach
    assert not by["qccp"].breach and by["qccp"].reportable
    assert not by["intraday"].breach and not by["intraday"].reportable
    assert not by["other"].breach and by["other"].reportable


def test_le_helpers() -> None:
    assert lex.covered_bond_exposure_value(100.0, True) == 20.0
    assert lex.covered_bond_exposure_value(100.0, False) == 100.0
    assert lex.obs_exposure_value(100.0, 0.0) == pytest.approx(10.0)
    assert lex.look_through_required(0.25, 100.0) and not lex.look_through_required(0.24, 100.0)
    assert lex.look_through_exposure(0.01, 1000.0, 5.0) == pytest.approx(0.05)
    assert lex.interdependence_check_required(5.01, 100.0)
    assert not lex.interdependence_check_required(5.0, 100.0)
    with pytest.raises(ValueError):
        CALC.large_exposures([], 0.0, False)


# =========================================================================
#  CCP
# =========================================================================


def test_kccp_and_kcm() -> None:
    kccp = ccp_mod.k_ccp([1000.0, 500.0])
    assert kccp == pytest.approx(1500.0 * 0.2 * 0.08)  # 24
    # K_CM = max(24 x 10 / 200, 0.0016 x 10) = 1.2
    assert ccp_mod.k_cm(kccp, 10.0, 200.0) == pytest.approx(1.2)
    # floor binds: max(1 x 10/1000, 0.016) = 0.016 (2% RW floor, footnote 245)
    assert ccp_mod.k_cm(1.0, 10.0, 1000.0) == pytest.approx(0.016)
    assert ccp_mod.sft_ead_for_kccp(100.0, 30.0, 20.0) == 50.0
    assert ccp_mod.sft_ead_for_kccp(10.0, 30.0, 20.0) == 0.0


def test_qccp_clearing_member() -> None:
    e = CCPExposureInput(ccp_id="C", trade_exposure=1000.0, default_fund_contribution=10.0,
                         k_ccp=24.0, total_default_fund=200.0)
    r = CALC.ccp_exposure(e)
    assert r.trade_rw == 0.02 and r.trade_rwa == pytest.approx(20.0)
    assert r.default_fund_rwa == pytest.approx(12.5 * 1.2)
    assert r.total_rwa == pytest.approx(35.0)


def test_qccp_client_variants() -> None:
    base = {"ccp_id": "C", "trade_exposure": 100.0, "is_client_cleared_via_member": True}
    assert CALC.ccp_exposure(CCPExposureInput.model_validate(base)).trade_rw == 0.02
    four = CCPExposureInput.model_validate(
        {**base, "flags": {"protected_against_joint_default": False}})
    assert CALC.ccp_exposure(four).trade_rw == 0.04
    bilateral = CCPExposureInput.model_validate({**base, "flags": {"client_conditions_met": False}})
    with pytest.raises(ValueError):
        CALC.ccp_exposure(bilateral)


def test_non_qccp() -> None:
    e = CCPExposureInput(ccp_id="N", is_qualifying=False, trade_exposure=100.0,
                         default_fund_contribution=10.0, ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS)
    r = CALC.ccp_exposure(e)
    assert r.trade_rw == 0.50 and r.default_fund_rwa == pytest.approx(125.0)
    bank = e.model_copy(update={"flags": {"ccp_is_bank": True}})
    assert CALC.ccp_exposure(bank).trade_rw == 0.30
    unrated = bank.model_copy(update={"ccp_rating": RatingBucket.UNRATED})
    assert CALC.ccp_exposure(unrated).trade_rw == 1.50


def test_qccp_cap() -> None:
    # K_CM so large that QCCP RWA exceeds the non-QCCP requirement (CRE54.40)
    e = CCPExposureInput(ccp_id="C", trade_exposure=0.0, default_fund_contribution=10.0,
                         k_ccp=1e6, total_default_fund=10.0, ccp_rating=RatingBucket.UNRATED)
    r = CALC.ccp_exposure(e)
    assert r.total_rwa == pytest.approx(125.0)
    assert "CRE54.40" in r.citation


def test_qccp_settlement_only_df_and_missing_inputs() -> None:
    e = CCPExposureInput(ccp_id="C", trade_exposure=10.0, default_fund_contribution=5.0,
                         flags={"settlement_only_default_fund": True})
    assert CALC.ccp_exposure(e).default_fund_rwa == 0.0
    with pytest.raises(ValueError):
        CALC.ccp_exposure(CCPExposureInput(ccp_id="C", trade_exposure=10.0,
                                           default_fund_contribution=5.0))
