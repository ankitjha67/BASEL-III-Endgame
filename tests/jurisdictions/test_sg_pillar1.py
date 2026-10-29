"""Tests for the Singapore Pillar 1 package -- MAS Notice 637 / MAS Notice 656.

Covers transcribed table cells (Tables 7-28 to 7-33, 7M-3, 7M-4, 8-28 to 8-39, 4D-1, Annex 7C),
hand-worked SEC-SA / SEC-IRBA / SEC-ERBA examples (the Notice prints no securitisation worked
example), STC floors, resecuritisation and NPL treatment, SA-CVA single- and cross-bucket
cases, the leverage exposure measure, large-exposure limit and breach edges, CCP K_CM, and
protocol conformance for all five protocols.

References: MAS Notice 637 Part IV Division 2, Annexes 4C / 4D / 7C / 7M / 7V, Part VII
Divisions 1 (Sub-division 7), 6 and 7, Part VIII Division 5 Sub-division 3; MAS Notice 656.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
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
from src.jurisdictions.sg.pillar1 import SGPillar1, ccp, large_exposures, leverage
from src.jurisdictions.sg.pillar1 import params as p
from src.jurisdictions.sg.pillar1 import sa_cva as sc
from src.jurisdictions.sg.pillar1 import securitisation as sec

REL = 1e-9


@pytest.fixture()
def calc() -> SGPillar1:
    return SGPillar1()


def _kssfa(k: float, a: float, d: float, pp: float) -> float:
    """Independent K_SSFA (paras 7.6.45 / 7.6.75)."""
    aa = -1.0 / (pp * k)
    u = d - k
    lo = max(a - k, 0.0)
    return (math.exp(aa * u) - math.exp(aa * lo)) / (aa * (u - lo))


def _tr(**kw: Any) -> SecTrancheInput:
    base: dict[str, Any] = {
        "tranche_id": "t",
        "exposure_amount": 100.0,
        "attachment": 0.15,
        "detachment": 0.25,
    }
    base.update(kw)
    return SecTrancheInput(**base)


# =========================================================================
#  Protocol conformance
# =========================================================================


@pytest.mark.parametrize(
    "proto",
    [
        SecuritisationCalculator,
        SACVACalculator,
        LeverageCalculator,
        LargeExposuresCalculator,
        CCPCalculator,
    ],
)
def test_protocol_conformance(calc: SGPillar1, proto: type) -> None:
    assert isinstance(calc, proto)
    assert calc.jurisdiction is Jurisdiction.SG


# =========================================================================
#  Securitisation -- table cells
# =========================================================================

TABLE_7_30 = {
    1: (0.15, 0.20, 0.15, 0.70), 2: (0.15, 0.30, 0.15, 0.90), 3: (0.25, 0.40, 0.30, 1.20),
    4: (0.30, 0.45, 0.40, 1.40), 5: (0.40, 0.50, 0.60, 1.60), 6: (0.50, 0.65, 0.80, 1.80),
    7: (0.60, 0.70, 1.20, 2.10), 8: (0.75, 0.90, 1.70, 2.60), 9: (0.90, 1.05, 2.20, 3.10),
    10: (1.20, 1.40, 3.30, 4.20), 11: (1.40, 1.60, 4.70, 5.80), 12: (1.60, 1.80, 6.20, 7.60),
    13: (2.00, 2.25, 7.50, 8.60), 14: (2.50, 2.80, 9.00, 9.50), 15: (3.10, 3.40, 10.50, 10.50),
    16: (3.80, 4.20, 11.30, 11.30), 17: (4.60, 5.05, 12.50, 12.50),
    18: (12.50, 12.50, 12.50, 12.50),
}  # fmt: skip
TABLE_7_33 = {
    1: (0.10, 0.10, 0.15, 0.40), 2: (0.10, 0.15, 0.15, 0.55), 3: (0.15, 0.20, 0.15, 0.70),
    4: (0.15, 0.25, 0.25, 0.80), 5: (0.20, 0.30, 0.35, 0.95), 6: (0.30, 0.40, 0.60, 1.35),
    7: (0.35, 0.40, 0.95, 1.70), 8: (0.45, 0.55, 1.50, 2.25), 9: (0.55, 0.65, 1.80, 2.55),
    10: (0.70, 0.85, 2.70, 3.45), 11: (1.20, 1.35, 4.05, 5.00), 12: (1.35, 1.55, 5.35, 6.55),
    13: (1.70, 1.95, 6.45, 7.40), 14: (2.25, 2.50, 8.10, 8.55), 15: (2.80, 3.05, 9.45, 9.45),
    16: (3.40, 3.80, 10.15, 10.15), 17: (4.15, 4.55, 12.50, 12.50),
    18: (12.50, 12.50, 12.50, 12.50),
}  # fmt: skip


@pytest.mark.parametrize("grade", list(TABLE_7_30))
def test_table_7_30_cells(grade: int) -> None:
    assert p.ERBA_LONG_TERM_RW[grade] == TABLE_7_30[grade]
    s1, s5, n1, n5 = TABLE_7_30[grade]
    assert sec.erba_long_term_rw(grade, True, 1.0, 0.0) == pytest.approx(s1)
    assert sec.erba_long_term_rw(grade, True, 5.0, 0.0) == pytest.approx(s5)
    assert sec.erba_long_term_rw(grade, False, 1.0, 0.0) == pytest.approx(n1)
    assert sec.erba_long_term_rw(grade, False, 5.0, 0.0) == pytest.approx(n5)


@pytest.mark.parametrize("grade", list(TABLE_7_33))
def test_table_7_33_cells(grade: int) -> None:
    assert p.ERBA_LONG_TERM_RW_STC[grade] == TABLE_7_33[grade]


def test_tables_7_29_and_7_32() -> None:
    assert p.ERBA_SHORT_TERM_RW == {"I": 0.15, "II": 0.50, "III": 1.00, "IV": 12.50}
    assert p.ERBA_SHORT_TERM_RW_STC == {"I": 0.10, "II": 0.30, "III": 0.60, "IV": 12.50}


def test_table_7_28_and_7_31() -> None:
    expected = {
        "WHOLESALE_SENIOR_GRANULAR": (0.0, 3.56, -1.85, 0.55, 0.07),
        "WHOLESALE_SENIOR_NON_GRANULAR": (0.11, 2.61, -2.91, 0.68, 0.07),
        "WHOLESALE_NON_SENIOR_GRANULAR": (0.16, 2.87, -1.03, 0.21, 0.07),
        "WHOLESALE_NON_SENIOR_NON_GRANULAR": (0.22, 2.35, -2.46, 0.48, 0.07),
        "RETAIL_SENIOR": (0.0, 0.0, -7.48, 0.71, 0.24),
        "RETAIL_NON_SENIOR": (0.0, 0.0, -5.78, 0.55, 0.27),
    }
    assert expected == p.IRBA_P_PARAMS
    assert expected == p.IRBA_P_PARAMS_STC


@pytest.mark.parametrize(
    ("rating", "grade"),
    [("AAA", 1), ("Aaa", 1), ("AA+", 2), ("Aa1", 2), ("AA-", 4), ("A", 6), ("A2", 6),
     ("BBB-", 10), ("Baa3", 10), ("BB+", 11), ("B-", 16), ("CCC", 17), ("Caa3", 17),
     ("CC", 18), ("D", 18)],
)  # fmt: skip
def test_table_7m_3(rating: str, grade: int) -> None:
    assert sec.long_term_grade(rating) == grade


def test_table_7m_3_unknown_rating_raises() -> None:
    with pytest.raises(ValueError, match="unrecognised"):
        sec.long_term_grade("ZZZ")


@pytest.mark.parametrize(
    ("rating", "grade"),
    [("F1", "I"), ("A-1+", "I"), ("P-1", "I"), ("A-2", "II"), ("F3", "III"), ("B", "IV")],
)
def test_table_7m_4(rating: str, grade: str) -> None:
    assert sec.short_term_grade(rating) == grade


def test_annex_7c_ccfs() -> None:
    assert p.SEC_OBS_CCF == {
        "SERVICER_ADVANCE_UNCONDITIONALLY_CANCELLABLE": 0.10,
        "SERVICER_ADVANCE_OTHER": 1.00,
        "OTHER_FACILITY": 1.00,
    }


# =========================================================================
#  Securitisation -- formulas and worked examples
# =========================================================================


def test_tranche_maturity() -> None:
    # Annex 7V para 6.1(b): M_T = 1 + (M_L - 1) x 0.8, floor 1, cap 5
    assert sec.tranche_maturity_from_legal(4.0) == pytest.approx(3.4)
    assert sec.tranche_maturity_from_legal(10.0) == pytest.approx(5.0)
    assert sec.tranche_maturity_from_legal(0.5) == pytest.approx(1.0)
    # para 6.1(a): weighted-average cash-flow maturity
    assert sec.tranche_maturity_from_cash_flows([(1.0, 50.0), (3.0, 50.0)]) == pytest.approx(2.0)
    assert sec.tranche_maturity_from_cash_flows([(0.25, 100.0)]) == pytest.approx(1.0)


def test_k_a_and_unknown_w() -> None:
    assert sec.k_a(0.08, 0.10) == pytest.approx(0.122)
    # para 7.6.74: 96% known (K_A 0.122), 4% unknown -> 0.96 x 0.122 + 0.04
    assert sec.k_a_with_unknown_w(0.08, 0.10, 96.0, 4.0) == pytest.approx(0.96 * 0.122 + 0.04)
    with pytest.raises(ValueError, match="1250%"):
        sec.k_a_with_unknown_w(0.08, 0.10, 94.0, 6.0)


def test_k_sa_from_pool() -> None:
    # para 7.6.64: 80 RWA on 100 exposure -> 0.8 x 8% = 6.4%
    assert sec.k_sa_from_pool(80.0, 100.0) == pytest.approx(0.064)


def test_sec_sa_mezzanine_worked_example(calc: SGPillar1) -> None:
    # K_SA 8%, W 10% -> K_A 0.122; A 15%, D 25%, p = 1 (paras 7.6.73-7.6.77)
    r = calc.securitisation(_tr(k_sa=0.08, w=0.10))
    expected = _kssfa(0.122, 0.15, 0.25, 1.0) * 12.5
    assert expected == pytest.approx(6.781671216750432, rel=1e-12)
    assert r.approach is SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(expected, rel=REL)
    assert r.rwa == pytest.approx(100.0 * expected, rel=REL)


def test_sec_sa_senior_and_floor(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(k_sa=0.08, w=0.10, attachment=0.25, detachment=1.0,
                                is_senior=True))
    assert r.risk_weight == pytest.approx(0.7106005153176193, rel=1e-9)
    # very senior tranche hits the 15% floor (para 7.6.77)
    r2 = calc.securitisation(_tr(k_sa=0.02, attachment=0.5, detachment=1.0, is_senior=True))
    assert r2.risk_weight == pytest.approx(0.15)


def test_sec_sa_straddle_blend(calc: SGPillar1) -> None:
    # A = 10% < K_A = 12.2% < D = 20% -> para 7.6.77(c)
    r = calc.securitisation(_tr(k_sa=0.08, w=0.10, attachment=0.10, detachment=0.20))
    ks = _kssfa(0.122, 0.122, 0.20, 1.0)
    expected = (0.022 / 0.10) * 12.5 + (0.078 / 0.10) * 12.5 * ks
    assert r.risk_weight == pytest.approx(expected, rel=REL)
    assert r.risk_weight == pytest.approx(9.953515879897513, rel=1e-9)


def test_sec_sa_first_loss_1250(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(k_sa=0.08, w=0.10, attachment=0.0, detachment=0.10))
    assert r.risk_weight == pytest.approx(12.5)


def test_sec_sa_stc(calc: SGPillar1) -> None:
    # p = 0.5 (7.6.103) and 10% senior floor (7.6.104)
    r = calc.securitisation(_tr(k_sa=0.08, w=0.10, attachment=0.25, detachment=1.0,
                                is_senior=True, is_stc=True))
    assert r.risk_weight == pytest.approx(0.12470105974425409, rel=1e-9)
    r2 = calc.securitisation(_tr(k_sa=0.02, attachment=0.5, detachment=1.0, is_senior=True,
                                 is_stc=True))
    assert r2.risk_weight == pytest.approx(0.10)
    r3 = calc.securitisation(_tr(k_sa=0.02, attachment=0.5, detachment=1.0, is_senior=False,
                                 is_stc=True))
    assert r3.risk_weight == pytest.approx(0.15)


def test_stc_not_available_for_synthetic(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(k_sa=0.02, attachment=0.5, detachment=1.0, is_senior=True,
                                is_stc=True, is_synthetic=True))
    assert r.risk_weight == pytest.approx(0.15)
    assert any("STC" in n for n in r.notes)


def test_resecuritisation(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(k_sa=0.20, attachment=0.30, detachment=0.50,
                                is_resecuritisation=True, is_stc=True))
    assert r.risk_weight == pytest.approx(6.537222551294007, rel=1e-9)
    # floor 100% (7.6.82)
    r2 = calc.securitisation(_tr(k_sa=0.05, attachment=0.6, detachment=1.0, is_senior=True,
                                 is_resecuritisation=True))
    assert r2.risk_weight == pytest.approx(1.0)
    # no look-through cap for resecuritisation (7.1.17)
    r3 = calc.securitisation(_tr(k_sa=0.05, attachment=0.6, detachment=1.0, is_senior=True,
                                 is_resecuritisation=True), look_through_rw=0.2)
    assert r3.risk_weight == pytest.approx(1.0)


def test_sec_irba_worked_example(calc: SGPillar1) -> None:
    # Wholesale senior granular: p = max(0.3, 3.56/100 - 1.85 x 0.06 + 0.55 x 0.45 + 0.07 x 3)
    pp = sec.irba_p(0.06, 100.0, 0.45, 3.0, is_retail=False, is_senior=True)
    assert pp == pytest.approx(0.3821)
    r = calc.securitisation(_tr(k_irb=0.06, n_effective=100.0, lgd_pool=0.45, maturity_years=3.0,
                                attachment=0.20, detachment=1.0, is_senior=True,
                                flags={"use_sec_irba": True}))
    assert r.approach is SecApproachUsed.SEC_IRBA
    assert r.risk_weight == pytest.approx(0.15)  # K_SSFA x 12.5 = 0.0008 -> 15% floor
    # Non-senior granular, A = K_IRB: p = 0.16 + 0.0287 - 0.0618 + 0.0945 + 0.21 = 0.4314
    r2 = calc.securitisation(_tr(k_irb=0.06, n_effective=100.0, lgd_pool=0.45, maturity_years=3.0,
                                 attachment=0.06, detachment=0.12,
                                 flags={"use_sec_irba": True}))
    assert r2.risk_weight == pytest.approx(_kssfa(0.06, 0.06, 0.12, 0.4314) * 12.5, rel=REL)
    assert r2.risk_weight == pytest.approx(4.8615169651186445, rel=1e-9)


def test_sec_irba_p_variants() -> None:
    # STC: 0.5 x 0.3821 = 0.19105 -> floor 0.3 (7.6.99)
    assert sec.irba_p(0.06, 100.0, 0.45, 3.0, False, True, stc=True) == pytest.approx(0.3)
    # retail senior: -7.48 x 0.05 + 0.71 x 0.3 + 0.24 x 2 = 0.319
    assert sec.irba_p(0.05, 1.0, 0.3, 2.0, True, True) == pytest.approx(0.319)
    # non-granular key below N = 25
    assert sec.irba_p_key(False, True, 24.9) == "WHOLESALE_SENIOR_NON_GRANULAR"
    assert sec.irba_p_key(False, False, 25.0) == "WHOLESALE_NON_SENIOR_GRANULAR"


def test_effective_n_simplified() -> None:
    assert sec.effective_n_simplified(0.02) == pytest.approx(50.0)
    n = sec.effective_n_simplified(0.02, 0.15, 10)
    assert n == pytest.approx(1.0 / (0.02 * 0.15 + (0.13 / 9) * 0.8))
    with pytest.raises(ValueError):
        sec.effective_n_simplified(0.04)


def test_mixed_pool(calc: SGPillar1) -> None:
    assert sec.mixed_pool_k(0.06, 0.08, 0.96) == pytest.approx(0.96 * 0.06 + 0.04 * 0.08)
    with pytest.raises(ValueError):
        sec.mixed_pool_k(0.06, 0.08, 0.90)
    # d < 95% -> SA-pool hierarchy (7.6.81)
    r = calc.securitisation(_tr(k_irb=0.06, k_sa=0.08, w=0.10, n_effective=100.0,
                                lgd_pool=0.45, flags={"use_sec_irba": True}),
                            mixed_pool_irb_share=0.9)
    assert r.approach is SecApproachUsed.SEC_SA


def test_sec_irba_prohibited_falls_to_erba(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(k_irb=0.06, external_rating="AA-", is_senior=True,
                                maturity_years=3.0,
                                flags={"use_sec_irba": True, "sec_irba_prohibited": True}))
    assert r.approach is SecApproachUsed.SEC_ERBA
    assert r.risk_weight == pytest.approx(0.375)  # 0.30 + (0.45 - 0.30) x 2/4


def test_erba_interpolation_and_thickness(calc: SGPillar1) -> None:
    # Grade 8 (BBB+), non-senior, M_T = 2, T = 0.10: (1.70 + 0.90 x 0.25) x 0.9
    r = calc.securitisation(_tr(external_rating="BBB+", maturity_years=2.0, attachment=0.10,
                                detachment=0.20))
    assert r.risk_weight == pytest.approx(1.925 * 0.9)
    # thickness capped at 0.5 (7.6.52)
    rw = sec.erba_long_term_rw(8, False, 1.0, 0.8)
    assert rw == pytest.approx(1.70 * 0.5)
    # maturity beyond 5 years capped (Annex 7V para 6.3)
    assert sec.erba_long_term_rw(1, True, 7.0, 0.0) == pytest.approx(0.20)


def test_erba_short_term_and_stc(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(short_term_rating="A-2", is_senior=True))
    assert r.risk_weight == pytest.approx(0.50)
    r2 = calc.securitisation(_tr(short_term_rating="A-1", is_senior=True, is_stc=True))
    assert r2.risk_weight == pytest.approx(0.10)
    r3 = calc.securitisation(_tr(external_rating="AAA", is_senior=True, is_stc=True,
                                 maturity_years=1.0))
    assert r3.risk_weight == pytest.approx(0.10)


def test_erba_more_senior_floor(calc: SGPillar1) -> None:
    r = calc.securitisation(_tr(external_rating="AAA", maturity_years=1.0), more_senior_rw=0.3)
    assert r.risk_weight == pytest.approx(0.30)


def test_iaa(calc: SGPillar1) -> None:
    flags = {"abcp_programme": True, "iaa_approved": True}
    r = calc.securitisation(_tr(internal_assessment_rating="A", is_senior=True,
                                maturity_years=1.0, flags=flags))
    assert r.approach is SecApproachUsed.SEC_IAA
    assert r.risk_weight == pytest.approx(0.50)
    # worse than grade 10 -> 1250% (7.6.61(b))
    r2 = calc.securitisation(_tr(internal_assessment_rating="BB+", is_senior=True, flags=flags))
    assert r2.risk_weight == pytest.approx(12.5)
    # without approval the SEC-SA applies (7.6.58)
    r3 = calc.securitisation(_tr(internal_assessment_rating="A", k_sa=0.08,
                                 flags={"abcp_programme": True}))
    assert r3.approach is SecApproachUsed.SEC_SA


def test_hierarchy_1250_cases(calc: SGPillar1) -> None:
    assert calc.securitisation(_tr()).risk_weight == pytest.approx(12.5)
    r = calc.securitisation(_tr(k_sa=0.08, flags={"requirements_7_6_8_not_met": True}))
    assert r.approach is SecApproachUsed.RW_1250
    r2 = calc.securitisation(_tr(k_sa=0.08, flags={"delinquency_unknown_over_5pct": True}))
    assert r2.risk_weight == pytest.approx(12.5)


def test_npl_securitisation(calc: SGPillar1) -> None:
    # 100% floor under SEC-SA (7.6.88)
    r = calc.securitisation(_tr(k_sa=0.10, w=0.95, attachment=0.70, detachment=1.0,
                                is_senior=True, is_npl_securitisation=True))
    raw = max(_kssfa(0.10 * 0.05 + 0.95 * 0.5, 0.70, 1.0, 1.0) * 12.5, 0.15)
    assert r.risk_weight == pytest.approx(max(raw, 1.0))
    # senior with NRPPD >= 50%: 100% (7.6.89)
    r2 = calc.securitisation(_tr(k_sa=0.10, w=0.95, attachment=0.40, detachment=1.0,
                                 is_senior=True, is_npl_securitisation=True,
                                 flags={"npl_traditional_nrppd_50pct": True}))
    assert r2.risk_weight == pytest.approx(1.0)
    # F-IRBA K_IRB: SEC-IRBA not permitted (7.6.87) -> SEC-SA
    r3 = calc.securitisation(_tr(k_irb=0.10, k_sa=0.10, w=0.95, attachment=0.40,
                                 detachment=1.0, is_npl_securitisation=True,
                                 flags={"use_sec_irba": True, "kirb_foundation_irba": True}))
    assert r3.approach is SecApproachUsed.SEC_SA
    # look-through cap floored at 100% for NPL (7.6.88)
    r4 = calc.securitisation(_tr(k_sa=0.10, w=0.95, attachment=0.40, detachment=1.0,
                                 is_senior=True, is_npl_securitisation=True),
                             look_through_rw=0.5)
    assert r4.risk_weight >= 1.0


def test_senior_look_through_cap(calc: SGPillar1) -> None:
    # cap may go below the 15% floor (7.1.16)
    r = calc.securitisation(_tr(k_sa=0.08, w=0.10, attachment=0.25, detachment=1.0,
                                is_senior=True), look_through_rw=0.10)
    assert r.approach is SecApproachUsed.LOOK_THROUGH
    assert r.risk_weight == pytest.approx(0.10)
    # non-senior: no cap
    r2 = calc.securitisation(_tr(k_sa=0.08, w=0.10), look_through_rw=0.10)
    assert r2.approach is SecApproachUsed.SEC_SA


def test_max_capital_cap() -> None:
    # P x K_P x 12.5 (7.1.20): P 50%, K_P 8%, pool 1,000 -> cap 500
    rows = [sec.SecResultRow(tranche_id=str(i), jurisdiction=Jurisdiction.SG,
                             approach=SecApproachUsed.SEC_SA, risk_weight=12.5, rwa=400.0,
                             citation="") for i in range(2)]
    assert sec.max_capital_rwa(0.5, 0.08) == pytest.approx(0.5)
    assert sec.capped_securitisation_rwa(rows, 0.5, 0.08, 1000.0) == pytest.approx(500.0)


def test_invalid_tranche(calc: SGPillar1) -> None:
    with pytest.raises(ValueError):
        calc.securitisation(_tr(attachment=0.3, detachment=0.3, k_sa=0.08))


# =========================================================================
#  SA-CVA
# =========================================================================


def _s(rc: CVARiskClass, bucket: str, rf: str, s_cva: float, s_hedge: float = 0.0,
       measure: str = "DELTA", **kw: Any) -> CVASensitivityInput:
    return CVASensitivityInput(risk_class=rc, measure=measure, bucket=bucket, risk_factor=rf,
                               s_cva=s_cva, s_hedge=s_hedge, **kw)


def test_sa_cva_table_cells() -> None:
    assert p.IR_DELTA_RW_SPECIFIED == {"1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074,
                                       "10Y": 0.0074, "30Y": 0.0074, "INFLATION": 0.0111}
    assert p.IR_DELTA_CORR_SPECIFIED[("1Y", "30Y")] == 0.31
    assert p.IR_DELTA_CORR_SPECIFIED[("5Y", "10Y")] == 0.91
    assert p.IR_DELTA_RW_OTHER == 0.0158
    assert p.FX_DELTA_RW == 0.11
    assert p.CCS_RW["1a"] == (0.005, 0.02)
    assert p.CCS_RW["4"] == (0.03, 0.085)
    assert p.CCS_RW["8"] == (0.015, 0.05)
    assert [p.RCS_DELTA_RW[b] for b in range(1, 18)] == [
        0.005, 0.01, 0.05, 0.03, 0.03, 0.02, 0.015, 0.02, 0.04, 0.12, 0.07, 0.085, 0.055,
        0.05, 0.12, 0.015, 0.05]
    assert [p.EQ_DELTA_RW[b] for b in range(1, 14)] == [
        0.55, 0.60, 0.45, 0.55, 0.30, 0.35, 0.40, 0.50, 0.70, 0.50, 0.70, 0.15, 0.25]
    assert [p.COM_DELTA_RW[b] for b in range(1, 12)] == [
        0.30, 0.35, 0.60, 0.80, 0.40, 0.45, 0.20, 0.35, 0.25, 0.35, 0.50]
    assert p.SA_CVA_R == 0.01
    assert p.SA_CVA_M_CVA == 1.0


@pytest.mark.parametrize(
    ("b", "c", "gamma"),
    [("1", "2", 0.10), ("1", "8", 0.45), ("2", "6", 0.05), ("4", "5", 0.25), ("6", "7", 0.0),
     ("7", "8", 0.0), ("3", "1", 0.20)],
)
def test_table_8_32(b: str, c: str, gamma: float) -> None:
    assert sc.ccs_gamma(b, c) == pytest.approx(gamma)


@pytest.mark.parametrize(
    ("b", "c", "gamma"),
    [(1, 2, 0.75), (8, 9, 0.75), (1, 9, 0.375), (3, 10, 0.5), (2, 3, 0.05), (4, 6, 0.25),
     (11, 13, 0.25), (4, 13, 0.125), (15, 3, 0.0), (16, 2, 0.45), (17, 12, 0.45),
     (16, 17, 0.75), (7, 14, 0.5)],
)
def test_table_8_35(b: int, c: int, gamma: float) -> None:
    assert sc.rcs_gamma(b, c) == pytest.approx(gamma)


def test_equity_and_commodity_gamma_and_vega_rw() -> None:
    assert sc.eq_gamma(1, 10) == 0.15
    assert sc.eq_gamma(12, 13) == 0.75
    assert sc.eq_gamma(12, 5) == 0.45
    assert sc.eq_gamma(11, 5) == 0.0
    assert sc.eq_rw(5, "VEGA") == 0.78
    assert sc.eq_rw(12, "VEGA") == 0.78
    assert sc.eq_rw(9, "VEGA") == 1.0
    assert sc.eq_rw(13, "VEGA") == 1.0
    assert sc.com_gamma(1, 10) == 0.20
    assert sc.com_gamma(11, 2) == 0.0
    assert sc.com_rw(4, "DELTA") == 0.80


def test_sa_cva_ir_single_bucket(calc: SGPillar1) -> None:
    sens = [
        _s(CVARiskClass.INTEREST_RATE, "SGD", "1Y", 1000.0),
        _s(CVARiskClass.INTEREST_RATE, "SGD", "5Y", 500.0, 200.0),
    ]
    res = calc.sa_cva(sens)
    ws1, ws5, h5 = 11.1, 0.0074 * 300.0, 0.0074 * 200.0
    kb = math.sqrt(ws1**2 + ws5**2 + 2 * 0.72 * ws1 * ws5 + 0.01 * h5**2)
    assert res.k_by_class["INTEREST_RATE_DELTA"] == pytest.approx(kb, rel=REL)
    assert res.k_total == pytest.approx(kb, rel=REL)
    assert res.rwa == pytest.approx(12.5 * kb, rel=REL)
    assert res.m_cva == 1.0
    assert res.r_hedging_disallowance == 0.01


def test_sa_cva_ir_other_currency_and_vega() -> None:
    k = sc.risk_class_capital(CVARiskClass.INTEREST_RATE, "DELTA",
                              [_s(CVARiskClass.INTEREST_RATE, "HKD", "CURVE", 100.0),
                               _s(CVARiskClass.INTEREST_RATE, "HKD", "INFLATION", 100.0)])
    ws = 1.58
    assert k == pytest.approx(math.sqrt(2 * ws**2 + 2 * 0.4 * ws * ws), rel=REL)
    with pytest.raises(ValueError):
        sc.risk_class_capital(CVARiskClass.INTEREST_RATE, "DELTA",
                              [_s(CVARiskClass.INTEREST_RATE, "HKD", "5Y", 1.0)])
    kv = sc.risk_class_capital(CVARiskClass.INTEREST_RATE, "VEGA",
                               [_s(CVARiskClass.INTEREST_RATE, "USD", "RATE_VOL", 10.0,
                                   measure="VEGA"),
                                _s(CVARiskClass.INTEREST_RATE, "USD", "INFLATION_VOL", -5.0,
                                   measure="VEGA")])
    assert kv == pytest.approx(math.sqrt(100 + 25 - 2 * 0.4 * 50), rel=REL)


def test_sa_cva_fx_cross_bucket(calc: SGPillar1) -> None:
    res = calc.sa_cva([_s(CVARiskClass.FX, "USD", "SPOT", 1000.0),
                       _s(CVARiskClass.FX, "EUR", "SPOT", -500.0)])
    expected = math.sqrt(110.0**2 + 55.0**2 + 2 * 0.6 * 110.0 * -55.0)
    assert res.k_by_class["FX_DELTA"] == pytest.approx(expected, rel=REL)
    with pytest.raises(ValueError, match="reporting currency"):
        calc.sa_cva([_s(CVARiskClass.FX, "SGD", "SPOT", 1.0)])


def test_sa_cva_ccs_intra_and_cross_bucket(calc: SGPillar1) -> None:
    cc = CVARiskClass.COUNTERPARTY_CREDIT_SPREAD
    sens = [
        _s(cc, "2", "5Y", 100.0, name="G|A", is_investment_grade=True),
        _s(cc, "2", "1Y", 50.0, name="G|B", is_investment_grade=True),
        _s(cc, "3", "5Y", 200.0, name="X"),
    ]
    res = calc.sa_cva(sens)
    kb2 = math.sqrt(25.0 + 6.25 + 2 * 0.9 * 0.9 * 1.0 * 5.0 * 2.5)
    assert kb2 == pytest.approx(math.sqrt(51.5))
    s2 = min(7.5, kb2)  # S_b capped at K_b (8.5.32(e)(iii))
    expected = math.sqrt(kb2**2 + 14.0**2 + 2 * 0.05 * s2 * 14.0)
    assert res.k_by_class["COUNTERPARTY_CREDIT_SPREAD_DELTA"] == pytest.approx(expected, rel=REL)


def test_ccs_rho_components() -> None:
    k = ("2", "5Y", "A", "IG", "2")
    assert sc.ccs_rho(k, ("2", "5Y", "B", "IG", "2")) == pytest.approx(0.5)
    assert sc.ccs_rho(k, ("2", "1Y", "B", "NIG", "2")) == pytest.approx(0.9 * 0.5 * 0.8)
    idx = ("8", "5Y", "CDX|S40", "IG", "8")
    assert sc.ccs_rho(idx, ("8", "5Y", "CDX|S41", "IG", "8")) == pytest.approx(0.9)
    assert sc.ccs_rho(idx, ("8", "5Y", "ITRAXX|S40", "IG", "8")) == pytest.approx(0.8)


def test_ccs_bucket_1a_1b_aggregate_together() -> None:
    cc = CVARiskClass.COUNTERPARTY_CREDIT_SPREAD
    k = sc.risk_class_capital(cc, "DELTA", [
        _s(cc, "1a", "5Y", 1000.0, name="SOV", is_investment_grade=True),
        _s(cc, "1b", "5Y", 1000.0, name="PSE", is_investment_grade=True)])
    ws_a, ws_b = 5.0, 10.0
    assert k == pytest.approx(math.sqrt(ws_a**2 + ws_b**2 + 2 * 0.5 * ws_a * ws_b), rel=REL)


def test_ccs_vega_rejected(calc: SGPillar1) -> None:
    with pytest.raises(ValueError, match="8.5.30"):
        calc.sa_cva([_s(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "2", "5Y", 1.0,
                        measure="VEGA")])


def test_sa_cva_hedge_disallowance_perfect_hedge(calc: SGPillar1) -> None:
    # perfect hedge leaves sqrt(R) x |WS_hdg| (para 8.5.32(d)(ii))
    res = calc.sa_cva([_s(CVARiskClass.EQUITY, "5", "", 100.0, 100.0)])
    assert res.k_total == pytest.approx(math.sqrt(0.01) * 30.0, rel=REL)


def test_sa_cva_rcs_equity_commodity_cross_bucket(calc: SGPillar1) -> None:
    res = calc.sa_cva([
        _s(CVARiskClass.REFERENCE_CREDIT_SPREAD, "3", "", 100.0),
        _s(CVARiskClass.REFERENCE_CREDIT_SPREAD, "10", "", 100.0),
        _s(CVARiskClass.EQUITY, "5", "", 100.0, measure="VEGA"),
        _s(CVARiskClass.EQUITY, "13", "", 100.0, measure="VEGA"),
        _s(CVARiskClass.COMMODITY, "2", "", 100.0),
        _s(CVARiskClass.COMMODITY, "11", "", -100.0),
    ])
    rcs = math.sqrt(5.0**2 + 12.0**2 + 2 * 0.5 * 5.0 * 12.0)
    eqv = math.sqrt(78.0**2 + 100.0**2 + 2 * 0.45 * 78.0 * 100.0)
    com = math.sqrt(35.0**2 + 50.0**2)
    assert res.k_by_class["REFERENCE_CREDIT_SPREAD_DELTA"] == pytest.approx(rcs, rel=REL)
    assert res.k_by_class["EQUITY_VEGA"] == pytest.approx(eqv, rel=REL)
    assert res.k_by_class["COMMODITY_DELTA"] == pytest.approx(com, rel=REL)
    assert res.k_total == pytest.approx(rcs + eqv + com, rel=REL)


def test_sa_cva_m_cva_scaling() -> None:
    sens = [_s(CVARiskClass.FX, "USD", "SPOT", 1000.0)]
    assert SGPillar1(m_cva=1.5).sa_cva(sens).k_total == pytest.approx(1.5 * 110.0)
    with pytest.raises(ValueError):
        SGPillar1(m_cva=0.9).sa_cva(sens)


def test_sa_cva_empty(calc: SGPillar1) -> None:
    assert calc.sa_cva([]).k_total == 0.0


# =========================================================================
#  Leverage
# =========================================================================


def test_table_4d_1() -> None:
    assert p.LEVERAGE_CCF["DIRECT_CREDIT_SUBSTITUTE"] == 1.0
    assert p.LEVERAGE_CCF["NIF_RUF"] == 0.5
    assert p.LEVERAGE_CCF["TRANSACTION_RELATED_CONTINGENT"] == 0.5
    assert p.LEVERAGE_CCF["OTHER_COMMITMENT"] == 0.4
    assert p.LEVERAGE_CCF["SHORT_TERM_TRADE_CONTINGENT"] == 0.2
    assert p.LEVERAGE_CCF["UNCONDITIONALLY_CANCELLABLE"] == 0.1


def test_leverage_aggregation(calc: SGPillar1) -> None:
    inputs = LeverageInputs(
        on_balance_sheet_assets=1000.0, tier1_deductions=20.0, derivative_rc=50.0,
        derivative_pfe_addon=30.0, derivative_cash_vm_received=10.0,
        written_credit_derivative_notional=100.0, written_credit_derivative_offsets=30.0,
        sft_gross_assets=200.0, sft_netted_cash_payables=50.0, sft_ccr_addon=5.0,
        obs_notional_by_ccf={0.1: 100.0, 0.4: 200.0, 1.0: 50.0},
        central_bank_reserves=300.0, client_cleared_trade_exposures_exempt=8.0,
    )
    r = calc.leverage_exposure(inputs)
    assert r.on_balance_sheet == pytest.approx(980.0)
    assert r.derivatives == pytest.approx(1.4 * (40.0 + 30.0) + 70.0 - 8.0)
    assert r.exclusions == pytest.approx(8.0)
    assert r.sfts == pytest.approx(155.0)
    assert r.off_balance_sheet == pytest.approx(140.0)
    assert r.total_exposure == pytest.approx(980.0 + 160.0 + 155.0 + 140.0)
    assert leverage.leverage_ratio(43.05, r.total_exposure) == pytest.approx(0.03)


def test_leverage_vm_and_ccf_validation() -> None:
    assert leverage.derivative_exposure(50.0, 30.0, 10.0, cash_vm_eligible=False) == (
        pytest.approx(1.4 * 80.0))
    assert leverage.derivative_exposure(5.0, 0.0, 10.0) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        leverage.off_balance_exposure({0.75: 10.0})
    assert leverage.off_balance_exposure({0.5: 100.0}, allowances=60.0) == pytest.approx(0.0)
    assert leverage.written_credit_derivative_addon(10.0, 30.0) == 0.0


# =========================================================================
#  Large exposures
# =========================================================================


def _le(cid: str, value: float, **kw: Any) -> LargeExposureInput:
    return LargeExposureInput(counterparty_id=cid, exposure_value=value, **kw)


def test_le_general_limit_edges(calc: SGPillar1) -> None:
    rows = calc.large_exposures(
        [_le("at", 250.0), _le("over", 250.01), _le("rep", 100.0), _le("small", 99.99)],
        tier1_capital=1000.0, reporting_bank_is_gsib=False)
    by = {r.counterparty_id: r for r in rows}
    assert by["at"].limit == pytest.approx(250.0)
    assert by["at"].limit_pct_of_tier1 == 0.25
    assert not by["at"].breach
    assert by["over"].breach
    assert by["rep"].reportable
    assert not by["small"].reportable


def test_le_gsib_limit(calc: SGPillar1) -> None:
    rows = calc.large_exposures(
        [_le("g1", 150.0, counterparty_is_gsib=True), _le("g2", 151.0, counterparty_is_gsib=True),
         _le("trans", 151.0, counterparty_is_gsib=True, flags={"gsib_transition_period": True}),
         _le("nonhq", 151.0, counterparty_is_gsib=True,
             flags={"gsib_headquartered_in_singapore": False})],
        tier1_capital=1000.0, reporting_bank_is_gsib=True)
    by = {r.counterparty_id: r for r in rows}
    assert by["g1"].limit_pct_of_tier1 == 0.15
    assert not by["g1"].breach
    assert by["g2"].breach
    assert not by["trans"].breach and by["trans"].limit_pct_of_tier1 == 0.25
    assert not by["nonhq"].breach
    # non-G-SIB reporting bank: 25% even against a G-SIB
    r = calc.large_exposures([_le("g", 200.0, counterparty_is_gsib=True)], 1000.0, False)
    assert not r[0].breach


def test_le_exemptions(calc: SGPillar1) -> None:
    rows = calc.large_exposures(
        [_le("mas", 900.0, flags={"sg_government_or_mas": True}),
         _le("intra", 900.0, flags={"intraday_interbank": True}),
         _le("caller", 900.0, is_exempt=True)],
        tier1_capital=1000.0, reporting_bank_is_gsib=False)
    by = {r.counterparty_id: r for r in rows}
    assert not any(r.breach for r in rows)
    assert by["mas"].reportable  # exempt large exposures still reported (para 28(a))
    assert not by["intra"].reportable  # except intraday interbank (1(e))
    assert "Annex A para 1(a)" in by["mas"].citation


def test_le_helpers() -> None:
    assert large_exposures.requires_dependence_due_diligence(50.01, 1000.0)
    assert not large_exposures.requires_dependence_due_diligence(50.0, 1000.0)
    assert large_exposures.obs_exposure_value(100.0, 0.0) == pytest.approx(10.0)
    assert large_exposures.obs_exposure_value(100.0, 0.4) == pytest.approx(40.0)
    with pytest.raises(ValueError):
        large_exposures.large_exposures([], 0.0, False)


# =========================================================================
#  CCP
# =========================================================================


def _ccp(**kw: Any) -> CCPExposureInput:
    base: dict[str, Any] = {"ccp_id": "c", "trade_exposure": 1000.0}
    base.update(kw)
    return CCPExposureInput(**base)


def test_k_ccp_and_k_cm() -> None:
    assert ccp.k_ccp([100.0, 200.0]) == pytest.approx(300.0 * 0.2 * 0.08)
    with pytest.raises(ValueError):
        ccp.k_ccp([100.0], risk_weight=0.1)
    # K_CM = max(100 x 50 / (500 + 1500), 8% x 2% x 50) = 2.5
    assert ccp.k_cm(100.0, 50.0, 500.0, 1500.0) == pytest.approx(2.5)
    # floor binds: max(1 x 50 / 2000, 0.08) = 0.08
    assert ccp.k_cm(1.0, 50.0, 500.0, 1500.0) == pytest.approx(0.08)


def test_qccp_clearing_member(calc: SGPillar1) -> None:
    r = calc.ccp_exposure(_ccp(default_fund_contribution=50.0, k_ccp=100.0,
                               total_default_fund=2000.0,
                               ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS))
    assert r.trade_rw == pytest.approx(0.02)
    assert r.trade_rwa == pytest.approx(20.0)
    assert r.default_fund_rwa == pytest.approx(12.5 * 2.5)
    assert r.total_rwa == pytest.approx(20.0 + 31.25)
    floor = calc.ccp_exposure(_ccp(default_fund_contribution=50.0, k_ccp=1.0,
                                   total_default_fund=2000.0))
    assert floor.default_fund_rwa == pytest.approx(50.0 * 0.02)


def test_qccp_client_variants(calc: SGPillar1) -> None:
    kw: dict[str, Any] = {"is_client_cleared_via_member": True, "k_ccp": 0.0,
                          "total_default_fund": 1.0}
    assert calc.ccp_exposure(_ccp(**kw)).trade_rw == pytest.approx(0.02)
    r4 = calc.ccp_exposure(_ccp(**kw, flags={"client_no_joint_default_protection": True}))
    assert r4.trade_rw == pytest.approx(0.04)
    rb = calc.ccp_exposure(_ccp(**kw, ccp_rating=RatingBucket.AAA_TO_AA_MINUS,
                                flags={"client_conditions_not_met": True,
                                       "counterparty_is_bank": True}))
    assert rb.trade_rw == pytest.approx(0.20)  # Table 7-5 grade 1 bank


def test_qccp_settlement_only_default_fund(calc: SGPillar1) -> None:
    r = calc.ccp_exposure(_ccp(default_fund_contribution=50.0, k_ccp=100.0,
                               total_default_fund=2000.0,
                               flags={"settlement_risk_only_default_fund": True}))
    assert r.default_fund_rwa == 0.0


def test_non_qualifying_ccp(calc: SGPillar1) -> None:
    r = calc.ccp_exposure(_ccp(is_qualifying=False, default_fund_contribution=50.0,
                               ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS))
    assert r.trade_rw == pytest.approx(0.50)  # Table 7-10 grade 2 corporate
    assert r.trade_rwa == pytest.approx(500.0)
    assert r.default_fund_rwa == pytest.approx(625.0)  # 1250%
    # QCCP without K_CCP data is not qualifying (7.7.3(c))
    r2 = calc.ccp_exposure(_ccp(default_fund_contribution=50.0))
    assert r2.default_fund_rwa == pytest.approx(625.0)
    assert "7.7.3(c)" in r2.citation


def test_qccp_cap_at_non_qualifying(calc: SGPillar1) -> None:
    r = calc.ccp_exposure(_ccp(default_fund_contribution=50.0, k_ccp=10_000.0,
                               total_default_fund=2000.0,
                               ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS))
    assert r.total_rwa == pytest.approx(500.0 + 625.0)
    assert "7.7.5" in r.citation
