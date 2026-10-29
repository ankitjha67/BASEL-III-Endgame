"""Tests for the Canada Pillar 1 package (securitization, SA-CVA, leverage, large exposures, CCP).

Sources: OSFI CAR 2026 Chapters 6, 7 and 8; OSFI Leverage Requirements Guideline (2023); OSFI
Guideline B-2 Large Exposure Limits (2028, consultation draft). Worked examples: CAR Ch.6
Appendix 6-3 (SEC-IRBA with dilution risk). See docs/jurisdictions/CA_pillar1_reference.md.
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.ca.pillar1 import CAPillar1
from src.jurisdictions.ca.pillar1 import ccp as cc
from src.jurisdictions.ca.pillar1 import large_exposures as le
from src.jurisdictions.ca.pillar1 import leverage as lv
from src.jurisdictions.ca.pillar1 import params as p
from src.jurisdictions.ca.pillar1 import sa_cva as sc
from src.jurisdictions.ca.pillar1 import securitisation as sec
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

CALC = CAPillar1()
C = CVARiskClass


def tranche(**kw: object) -> SecTrancheInput:
    base: dict[str, object] = {"tranche_id": "T", "exposure_amount": 100.0, "attachment": 0.2,
                               "detachment": 1.0}
    base.update(kw)
    return SecTrancheInput.model_validate(base)


# =========================================================================
#  Protocol conformance
# =========================================================================

def test_protocol_conformance() -> None:
    assert isinstance(CALC, SecuritisationCalculator)
    assert isinstance(CALC, SACVACalculator)
    assert isinstance(CALC, LeverageCalculator)
    assert isinstance(CALC, LargeExposuresCalculator)
    assert isinstance(CALC, CCPCalculator)
    assert CALC.jurisdiction == Jurisdiction.CA


# =========================================================================
#  Securitization -- table cells
# =========================================================================

@pytest.mark.parametrize("key,expected", [
    (("WHOLESALE", True, True), (0.0, 3.56, -1.85, 0.55, 0.07)),
    (("WHOLESALE", True, False), (0.11, 2.61, -2.91, 0.68, 0.07)),
    (("WHOLESALE", False, True), (0.16, 2.87, -1.03, 0.21, 0.07)),
    (("WHOLESALE", False, False), (0.22, 2.35, -2.46, 0.48, 0.07)),
    (("RETAIL", True, True), (0.0, 0.0, -7.48, 0.71, 0.24)),
    (("RETAIL", False, False), (0.0, 0.0, -5.78, 0.55, 0.27)),
])
def test_irba_p_table(key: tuple[str, bool, bool], expected: tuple[float, ...]) -> None:
    assert p.IRBA_P_TABLE[key] == expected


@pytest.mark.parametrize("rating,expected", [
    ("AAA", (0.15, 0.20, 0.15, 0.70)), ("AA-", (0.30, 0.45, 0.40, 1.40)),
    ("A", (0.50, 0.65, 0.80, 1.80)), ("BBB-", (1.20, 1.40, 3.30, 4.20)),
    ("BB", (1.60, 1.80, 6.20, 7.60)), ("B-", (3.80, 4.20, 11.30, 11.30)),
    ("CCC", (4.60, 5.05, 12.50, 12.50)), ("BELOW_CCC-", (12.5, 12.5, 12.5, 12.5)),
])
def test_erba_table2_cells(rating: str, expected: tuple[float, ...]) -> None:
    assert p.ERBA_LONG_TERM_RW[rating] == expected


@pytest.mark.parametrize("rating,expected", [
    ("AAA", (0.10, 0.10, 0.15, 0.40)), ("AA", (0.15, 0.20, 0.15, 0.70)),
    ("A-", (0.35, 0.40, 0.95, 1.70)), ("BBB", (0.55, 0.65, 1.80, 2.55)),
    ("BB-", (1.70, 1.95, 6.45, 7.40)), ("CCC", (4.15, 4.55, 12.50, 12.50)),
])
def test_stc_erba_table2prime_cells(rating: str, expected: tuple[float, ...]) -> None:
    assert p.STC_ERBA_LONG_TERM_RW[rating] == expected


def test_erba_short_term_tables() -> None:
    assert p.ERBA_SHORT_TERM_RW == {"A-1/P-1": 0.15, "A-2/P-2": 0.50, "A-3/P-3": 1.00,
                                    "OTHER": 12.50}
    assert p.STC_ERBA_SHORT_TERM_RW == {"A-1/P-1": 0.10, "A-2/P-2": 0.30, "A-3/P-3": 0.60,
                                        "OTHER": 12.50}
    assert sec.erba_short_term_rw("A-2") == 0.50
    assert sec.erba_short_term_rw("B", stc=True) == 12.50


def test_rating_normalisation() -> None:
    assert sec.normalise_rating("AA−") == "AA-"
    assert sec.normalise_rating("ccc+") == "CCC"
    assert sec.normalise_rating("CC") == "BELOW_CCC-"
    with pytest.raises(ValueError):
        sec.normalise_rating("ZZZ")


# =========================================================================
#  Securitization -- SEC-IRBA worked examples (CAR Ch.6 Appendix 6-3)
# =========================================================================

@pytest.mark.parametrize("k,a_pt,d_pt,lgd,senior,expected", [
    (0.2016, 0.30, 1.00, 0.8187, True, 0.2122),     # 6-3.A Tranche A: 21.22%
    (0.2016, 0.05, 0.30, 0.8187, False, 10.1385),   # 6-3.A Tranche B: 1013.85%
    (0.1347, 0.00, 0.2632, 1.00, False, 8.8694),    # 6-3.B Tranche B: 886.94%
    (0.0669, 0.05, 1.00, 0.45, True, 0.5167),       # 6-3.B Tranche A (i): 51.67%
    (0.1347, 0.30, 1.00, 1.00, True, 0.1116),       # 6-3.B Tranche A': 11.16% (unfloored)
])
def test_appendix_6_3_worked_examples(k: float, a_pt: float, d_pt: float, lgd: float,
                                      senior: bool, expected: float) -> None:
    pp = sec.irba_p(k, 100, lgd, 2.5, senior, retail=False)
    # Inputs are printed rounded to 2 decimals (K_IRB 20.16%), so allow 0.2% RW of slack.
    assert sec.ssfa_risk_weight(k, a_pt, d_pt, pp) == pytest.approx(expected, abs=2e-3)


def test_appendix_6_3a_tranche_c_and_total() -> None:
    assert sec.ssfa_risk_weight(0.2016, 0.0, 0.05, 0.3) == 12.5
    # 6-3.B implicit RW for Tranche A = max(15%, 1,193,985 / 950,000) = 125.68%
    rwa = 0.5167 * 950_000 + 0.1116 * 700_000 + 12.5 * 50_000
    assert max(0.15, rwa / 950_000) == pytest.approx(1.2568, abs=1e-3)


def test_irba_hierarchy_end_to_end() -> None:
    r = CALC.securitisation(tranche(attachment=0.3, k_irb=0.2016, n_effective=100,
                                    lgd_pool=0.8187, maturity_years=2.5, is_senior=True))
    assert r.approach == SecApproachUsed.SEC_IRBA
    assert r.risk_weight == pytest.approx(0.2122, abs=1e-4)
    assert r.rwa == pytest.approx(r.risk_weight * 100)


def test_irba_p_floor_stc_and_retail() -> None:
    assert sec.irba_p(0.05, 100, 0.45, 1.0, True, False) == pytest.approx(
        max(0.3, 3.56 / 100 - 1.85 * 0.05 + 0.55 * 0.45 + 0.07))
    assert sec.irba_p(0.05, 10, 0.45, 1.0, True, True) == pytest.approx(
        max(0.3, -7.48 * 0.05 + 0.71 * 0.45 + 0.24))
    raw = 0.22 + 2.35 / 10 - 2.46 * 0.05 + 0.48 * 0.45 + 0.07 * 5
    assert sec.irba_p(0.05, 10, 0.45, 7.0, False, False, stc=True) == pytest.approx(
        max(0.3, 0.5 * raw))


def test_irba_missing_inputs_raise() -> None:
    with pytest.raises(ValueError):
        CALC.securitisation(tranche(k_irb=0.05, lgd_pool=0.45))


def test_n_lgd_helpers() -> None:
    assert sec.effective_number([1, 1, 1, 1]) == pytest.approx(4.0)
    assert sec.weighted_lgd([0.4, 0.6], [1, 3]) == pytest.approx(0.55)
    n1, lgd1 = sec.simplified_n(0.02)
    assert n1 == pytest.approx(50.0) and lgd1 == 0.5
    n, lgd = sec.simplified_n(0.02, cm=0.10, m=10)
    assert n == pytest.approx(1 / (0.02 * 0.10 + (0.10 - 0.02) * max(1 - 0.2, 0) / 9))
    with pytest.raises(ValueError):
        sec.simplified_n(0.04)


def test_mixed_pool() -> None:
    assert sec.mixed_pool_k(0.06, 0.08, 0.96) == pytest.approx(0.96 * 0.06 + 0.04 * 0.08)
    with pytest.raises(ValueError):
        sec.mixed_pool_k(0.06, 0.08, 0.94)


# =========================================================================
#  Securitization -- SEC-SA hand-worked
# =========================================================================

def test_sec_sa_hand_worked_mezzanine() -> None:
    # K_A = 0.08, A = 5%, D = 15%, p = 1: a = -12.5, u = 0.07, l = 0
    a, u = -1 / 0.08, 0.07
    ks = (math.exp(a * u) - 1.0) / (a * u)
    expected = 12.5 * (0.03 / 0.10) + 12.5 * ks * (0.07 / 0.10)
    r = CALC.securitisation(tranche(attachment=0.05, detachment=0.15, k_sa=0.08))
    assert r.approach == SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(expected)
    assert r.risk_weight == pytest.approx(9.5814, abs=1e-4)


def test_sec_sa_hand_worked_senior_and_stc_floor() -> None:
    r = CALC.securitisation(tranche(k_sa=0.08, is_senior=True))
    assert r.risk_weight == pytest.approx(0.2789, abs=1e-4)
    stc = CALC.securitisation(tranche(k_sa=0.08, is_senior=True, is_stc=True))
    assert stc.risk_weight == p.STC_SENIOR_RW_FLOOR  # 3.11% -> 10% floor
    non_senior_stc = CALC.securitisation(tranche(attachment=0.5, k_sa=0.08, is_stc=True))
    assert non_senior_stc.risk_weight == p.STC_NON_SENIOR_RW_FLOOR


def test_sec_sa_delinquency_and_boundaries() -> None:
    assert sec.k_a(0.08, 0.10) == pytest.approx(0.9 * 0.08 + 0.05)
    assert sec.k_a_partial_unknown(0.10, 0.05) == pytest.approx(0.95 * 0.10 + 0.05)
    with pytest.raises(ValueError):
        sec.k_a_partial_unknown(0.10, 0.06)
    r = CALC.securitisation(tranche(attachment=0.0, detachment=0.08, k_sa=0.08))
    assert r.risk_weight == 12.5  # D <= K_A
    unknown = CALC.securitisation(tranche(k_sa=0.08,
                                          flags={"ca_delinquency_unknown_over_5pct": True}))
    assert unknown.approach == SecApproachUsed.RW_1250
    assert sec.k_ssfa(0.0, 0.1, 0.2, 1.0) == 0.0
    with pytest.raises(ValueError):
        CALC.securitisation(tranche(attachment=0.5, detachment=0.5, k_sa=0.08))


def test_synthetic_stc_not_eligible() -> None:
    r = CALC.securitisation(tranche(k_sa=0.08, is_senior=True, is_stc=True, is_synthetic=True))
    assert r.risk_weight == pytest.approx(0.2789, abs=1e-4)
    assert any("traditional" in n for n in r.notes)


# =========================================================================
#  Securitization -- SEC-ERBA, IAA, hierarchy
# =========================================================================

def test_erba_maturity_interpolation() -> None:
    assert sec.erba_long_term_rw("A", True, 3.0, 0.8) == pytest.approx(0.50 + 0.15 * 0.5)
    assert sec.erba_long_term_rw("A", True, 0.5, 0.8) == pytest.approx(0.50)  # M_T floor 1
    assert sec.erba_long_term_rw("A", True, 9.0, 0.8) == pytest.approx(0.65)  # M_T cap 5
    # Non-senior: thickness adjustment x [1 - min(T, 50%)]
    assert sec.erba_long_term_rw("BBB", False, 1.0, 0.10) == pytest.approx(2.20 * 0.90)
    assert sec.erba_long_term_rw("BBB", False, 2.0, 0.70) == pytest.approx(
        (2.20 + (3.10 - 2.20) * 0.25) * 0.5)


def test_erba_non_senior_not_below_senior_and_floor() -> None:
    assert sec.erba_long_term_rw("AAA", False, 1.0, 0.6) == pytest.approx(0.15)
    r = CALC.securitisation(tranche(attachment=0.4, external_rating="AAA", maturity_years=1.0))
    assert r.approach == SecApproachUsed.SEC_ERBA
    assert r.risk_weight == pytest.approx(0.15)


def test_erba_stc_floor_and_short_term() -> None:
    r = CALC.securitisation(tranche(external_rating="AAA", is_senior=True, is_stc=True))
    assert r.risk_weight == pytest.approx(0.10)
    st = CALC.securitisation(tranche(short_term_rating="A-1/P-1", is_senior=True))
    assert st.risk_weight == pytest.approx(0.15)


def test_hierarchy_irba_before_erba_and_capital_floor() -> None:
    t = tranche(attachment=0.3, k_irb=0.2016, n_effective=100, lgd_pool=0.8187,
                maturity_years=2.5, is_senior=True, external_rating="AA", k_sa=0.10)
    assert CALC.securitisation(t).approach == SecApproachUsed.SEC_IRBA
    t.flags["ca_capital_floor_calculation"] = True
    assert CALC.securitisation(t).approach == SecApproachUsed.SEC_ERBA
    t2 = tranche(k_irb=0.05, n_effective=100, lgd_pool=0.45, k_sa=0.08,
                 flags={"ca_irb_pool_excess_spread_as_sa": True})
    assert CALC.securitisation(t2).approach == SecApproachUsed.SEC_SA


def test_iaa_requires_approval() -> None:
    t = tranche(internal_assessment_rating="A", is_senior=True, maturity_years=1.0, k_sa=0.08)
    assert CALC.securitisation(t).approach == SecApproachUsed.SEC_SA
    t.flags["ca_iaa_approved"] = True
    r = CALC.securitisation(t)
    assert r.approach == SecApproachUsed.SEC_IAA
    assert r.risk_weight == pytest.approx(0.50)


def test_no_approach_is_1250() -> None:
    r = CALC.securitisation(tranche())
    assert r.approach == SecApproachUsed.RW_1250 and r.risk_weight == 12.5
    assert r.rwa == 1250.0


# =========================================================================
#  Securitization -- resecuritization, NPL, caps
# =========================================================================

def test_resecuritisation_p_and_floor() -> None:
    r = CALC.securitisation(tranche(k_sa=0.08, is_senior=True, is_resecuritisation=True,
                                    external_rating="AAA", is_stc=True))
    assert r.approach == SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(p.RESEC_RW_FLOOR)
    mezz = CALC.securitisation(tranche(attachment=0.05, detachment=0.15, k_sa=0.08,
                                       is_resecuritisation=True))
    assert mezz.risk_weight == pytest.approx(
        sec.ssfa_risk_weight(0.08, 0.05, 0.15, p.RESEC_P))
    none = CALC.securitisation(tranche(is_resecuritisation=True))
    assert none.approach == SecApproachUsed.RW_1250


def test_npl_floor_senior_option_and_firb_preclusion() -> None:
    r = CALC.securitisation(tranche(k_sa=0.08, is_senior=True, is_npl_securitisation=True))
    assert r.risk_weight == pytest.approx(1.00)
    hi = CALC.securitisation(tranche(attachment=0.05, detachment=0.15, k_sa=0.08,
                                     is_senior=True, is_npl_securitisation=True,
                                     flags={"ca_npl_nrppd_at_least_50pct": True}))
    assert hi.risk_weight == pytest.approx(1.00)
    t = tranche(k_irb=0.05, n_effective=100, lgd_pool=0.45, k_sa=0.08,
                is_npl_securitisation=True, flags={"ca_kirb_foundation_irb": True})
    assert CALC.securitisation(t).approach == SecApproachUsed.SEC_SA


def test_senior_look_through_cap_below_floor() -> None:
    t = tranche(attachment=0.1, k_sa=0.008, is_senior=True,
                flags={"ca_senior_look_through": True})
    r = CALC.securitisation(t)
    assert r.approach == SecApproachUsed.LOOK_THROUGH
    assert r.risk_weight == pytest.approx(0.10)  # below the 15% floor (s.6.6.5.1)


def test_max_capital_cap() -> None:
    t = tranche(attachment=0.0, detachment=1.0, k_irb=0.08, n_effective=100, lgd_pool=0.45,
                flags={"ca_apply_max_capital_cap": True})
    r = CALC.securitisation(t)
    assert r.risk_weight == pytest.approx(12.5 * 0.08)
    sa = CALC.securitisation(tranche(attachment=0.0, detachment=1.0, k_sa=0.08,
                                     flags={"ca_apply_max_capital_cap": True}))
    assert sa.risk_weight > 1.0  # investor using SEC-SA: no cap
    orig = CALC.securitisation(tranche(attachment=0.0, detachment=1.0, k_sa=0.08,
                                       flags={"ca_apply_max_capital_cap": True,
                                              "ca_is_originator": True}))
    assert orig.risk_weight == pytest.approx(1.0)


def test_tranche_maturity_helpers() -> None:
    assert sec.tranche_maturity_from_legal(2.0) == pytest.approx(1.8)
    assert sec.tranche_maturity_from_legal(10.0) == 5.0
    assert sec.tranche_maturity_from_legal(0.5) == 1.0
    assert sec.tranche_maturity_from_cash_flows([(1.0, 50.0), (3.0, 50.0)]) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        sec.tranche_maturity_from_cash_flows([])


# =========================================================================
#  SA-CVA
# =========================================================================

def s(rc: CVARiskClass, bucket: str, rf: str = "SINGLE", s_cva: float = 0.0,
      s_hedge: float = 0.0, measure: str = "DELTA", name: str = "",
      ig: bool | None = None) -> CVASensitivityInput:
    return CVASensitivityInput(risk_class=rc, measure=measure, bucket=bucket, risk_factor=rf,
                               s_cva=s_cva, s_hedge=s_hedge, name=name, is_investment_grade=ig)


def test_sa_cva_tables() -> None:
    assert p.SA_CVA_IR_DELTA_RW_SPECIFIED == {"1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074,
                                              "10Y": 0.0074, "30Y": 0.0074, "INFLATION": 0.0111}
    assert p.SA_CVA_IR_DELTA_CORR_SPECIFIED[("1Y", "30Y")] == 0.31
    assert p.SA_CVA_IR_DELTA_CORR_SPECIFIED[("10Y", "30Y")] == 0.83
    assert p.SA_CVA_CCS_RW["1a"] == (0.005, 0.020) and p.SA_CVA_CCS_RW["8"] == (0.015, 0.050)
    assert p.SA_CVA_RCS_RW[10] == 0.12 and p.SA_CVA_RCS_RW[16] == 0.015
    assert p.SA_CVA_EQ_DELTA_RW[9] == 0.70 and p.SA_CVA_EQ_DELTA_RW[12] == 0.15
    assert p.SA_CVA_COM_DELTA_RW[4] == 0.80 and p.SA_CVA_COM_DELTA_RW[11] == 0.50
    assert p.SA_CVA_M_CVA == 1.0 and p.SA_CVA_R == 0.01
    assert p.SA_CVA_EQ_LARGE_CAP_THRESHOLD_CAD_M == 2_500.0


def test_sa_cva_single_bucket_ir() -> None:
    sens = [s(C.INTEREST_RATE, "CAD", "5Y", 100.0),
            s(C.INTEREST_RATE, "CAD", "10Y", 50.0, 20.0)]
    ws5, ws10, h10 = 0.0074 * 100, 0.0074 * 30, 0.0074 * 20
    kb = math.sqrt(ws5 ** 2 + ws10 ** 2 + 2 * 0.91 * ws5 * ws10 + 0.01 * h10 ** 2)
    r = CALC.sa_cva(sens)
    assert r.k_by_class["INTEREST_RATE_DELTA"] == pytest.approx(kb)
    assert r.k_total == pytest.approx(kb) and r.rwa == pytest.approx(12.5 * kb)
    assert r.m_cva == 1.0 and r.r_hedging_disallowance == 0.01


def test_sa_cva_cross_bucket_ir_other_currency() -> None:
    sens = [s(C.INTEREST_RATE, "CAD", "5Y", 100.0), s(C.INTEREST_RATE, "BRL", "CURVE", 100.0),
            s(C.INTEREST_RATE, "BRL", "INFLATION", -20.0)]
    k_cad = 0.0074 * 100
    w1, w2 = 0.0158 * 100, 0.0158 * -20
    k_brl = math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.40 * w1 * w2)
    s_brl = max(-k_brl, min(w1 + w2, k_brl))
    expected = math.sqrt(k_cad ** 2 + k_brl ** 2 + 2 * 0.5 * k_cad * s_brl)
    assert CALC.sa_cva(sens).k_total == pytest.approx(expected)


def test_sa_cva_fx_and_hedge_disallowance() -> None:
    sens = [s(C.FX, "USD", s_cva=100.0, s_hedge=100.0)]
    r = CALC.sa_cva(sens)
    # perfect hedge: only the R term survives
    assert r.k_total == pytest.approx(math.sqrt(0.01 * (0.11 * 100) ** 2))
    two = CALC.sa_cva([s(C.FX, "USD", s_cva=100.0), s(C.FX, "EUR", s_cva=100.0)])
    assert two.k_total == pytest.approx(math.sqrt(2 * 11.0 ** 2 + 2 * 0.6 * 11.0 * 11.0))
    with pytest.raises(ValueError):
        CALC.sa_cva([s(C.FX, "CAD", s_cva=1.0)])


def test_sa_cva_counterparty_credit_spread_correlations() -> None:
    sens = [s(C.COUNTERPARTY_CREDIT_SPREAD, "2", "1Y", 100.0, name="BANKCO::A", ig=True),
            s(C.COUNTERPARTY_CREDIT_SPREAD, "2", "5Y", 100.0, name="BANKCO::B", ig=True),
            s(C.COUNTERPARTY_CREDIT_SPREAD, "2", "5Y", 100.0, name="OTHER", ig=False)]
    w_ig, w_hy = 0.05 * 100, 0.12 * 100
    r_ab = 0.9 * 0.9 * 1.0      # different tenor, legally related, same quality
    r_ac = 0.9 * 0.5 * 0.8      # different tenor, unrelated, different quality
    r_bc = 1.0 * 0.5 * 0.8      # same tenor, unrelated, different quality
    kb = math.sqrt(2 * w_ig ** 2 + w_hy ** 2 + 2 * r_ab * w_ig * w_ig
                   + 2 * r_ac * w_ig * w_hy + 2 * r_bc * w_ig * w_hy)
    assert CALC.sa_cva(sens).k_by_class["COUNTERPARTY_CREDIT_SPREAD_DELTA"] == pytest.approx(kb)
    with pytest.raises(ValueError):
        CALC.sa_cva([s(C.COUNTERPARTY_CREDIT_SPREAD, "2", "1Y", 1.0, measure="VEGA")])
    with pytest.raises(ValueError):
        CALC.sa_cva([s(C.COUNTERPARTY_CREDIT_SPREAD, "2", "2Y", 1.0)])


def test_sa_cva_gammas() -> None:
    assert sc.gamma(C.COUNTERPARTY_CREDIT_SPREAD, "1", "8") == 0.45
    assert sc.gamma(C.COUNTERPARTY_CREDIT_SPREAD, "3", "5") == 0.25
    assert sc.gamma(C.REFERENCE_CREDIT_SPREAD, "1", "2") == 0.75
    assert sc.gamma(C.REFERENCE_CREDIT_SPREAD, "1", "9") == pytest.approx(0.375)  # /2
    assert sc.gamma(C.REFERENCE_CREDIT_SPREAD, "1", "8") == pytest.approx(0.5)
    assert sc.gamma(C.REFERENCE_CREDIT_SPREAD, "8", "16") == 0.45
    assert sc.gamma(C.REFERENCE_CREDIT_SPREAD, "16", "17") == 0.75
    assert sc.gamma(C.EQUITY, "1", "10") == 0.15
    assert sc.gamma(C.EQUITY, "12", "13") == 0.75
    assert sc.gamma(C.EQUITY, "12", "3") == 0.45
    assert sc.gamma(C.EQUITY, "11", "3") == 0.0
    assert sc.gamma(C.COMMODITY, "2", "7") == 0.20 and sc.gamma(C.COMMODITY, "11", "1") == 0.0


def test_sa_cva_equity_vega_and_cross_bucket() -> None:
    sens = [s(C.EQUITY, "5", s_cva=100.0, measure="VEGA"),
            s(C.EQUITY, "9", s_cva=100.0, measure="VEGA")]
    k5, k9 = 0.78 * 100, 1.00 * 100
    expected = math.sqrt(k5 ** 2 + k9 ** 2 + 2 * 0.15 * k5 * k9)
    assert CALC.sa_cva(sens).k_by_class["EQUITY_VEGA"] == pytest.approx(expected)


def test_sa_cva_total_is_sum_of_classes_and_m_cva() -> None:
    sens = [s(C.COMMODITY, "4", s_cva=10.0), s(C.REFERENCE_CREDIT_SPREAD, "3", s_cva=10.0),
            s(C.EQUITY, "12", s_cva=10.0)]
    r = CALC.sa_cva(sens)
    assert r.k_total == pytest.approx(0.8 * 10 + 0.05 * 10 + 0.15 * 10)
    assert CAPillar1(m_cva=1.5).sa_cva(sens).k_total == pytest.approx(1.5 * r.k_total)
    with pytest.raises(ValueError):
        CAPillar1(m_cva=0.9).sa_cva(sens)
    with pytest.raises(ValueError):
        CALC.sa_cva([s(C.EQUITY, "1", s_cva=1.0, measure="GAMMA")])


# =========================================================================
#  Leverage
# =========================================================================

def test_leverage_aggregation() -> None:
    inp = LeverageInputs(
        on_balance_sheet_assets=1_000.0, tier1_deductions=20.0, derivative_rc=30.0,
        derivative_pfe_addon=50.0, derivative_cash_vm_received=10.0,
        written_credit_derivative_notional=40.0, written_credit_derivative_offsets=15.0,
        sft_gross_assets=200.0, sft_netted_cash_payables=50.0, sft_ccr_addon=5.0,
        obs_notional_by_ccf={0.10: 100.0, 0.25: 40.0, 0.40: 100.0, 1.0: 10.0},
        central_bank_reserves=60.0, client_cleared_trade_exposures_exempt=7.0)
    r = CALC.leverage_exposure(inp)
    assert r.on_balance_sheet == pytest.approx(980.0)
    assert r.derivatives == pytest.approx(1.4 * 80.0 + 25.0)
    assert r.sfts == pytest.approx(155.0)
    assert r.off_balance_sheet == pytest.approx(10.0 + 10.0 + 40.0 + 10.0)
    assert r.exclusions == pytest.approx(7.0)  # reserves not excluded without exemption
    assert r.total_exposure == pytest.approx(980 + 137 + 155 + 70 - 7)
    inp.flags["ca_central_bank_reserves_exemption"] = True
    assert CALC.leverage_exposure(inp).exclusions == pytest.approx(67.0)


def test_leverage_ccf_validation_and_helpers() -> None:
    with pytest.raises(ValueError):
        lv.off_balance_sheet({0.30: 10.0})
    assert lv.sft_current_exposure([100, 50], [90, 70], qualifying_mna=True) == 0.0
    assert lv.sft_current_exposure([100, 50], [90, 70], qualifying_mna=False) == 10.0
    assert lv.derivative_exposure(10, 10, 0.5) == pytest.approx(1.4 * 15)
    with pytest.raises(ValueError):
        lv.derivative_exposure(10, 10, 0.0)


def test_leverage_requirement() -> None:
    assert CALC.leverage_requirement(0.01) == pytest.approx(0.035)
    assert CALC.leverage_requirement(0.025) == pytest.approx(0.0425)
    assert CAPillar1(is_dsib=False).leverage_requirement() == 0.03
    assert CALC.leverage_requirement(0.01, authorized_ratio=0.04) == 0.04
    assert lv.leverage_conservation_ratio(0.0310) == 1.0
    assert lv.leverage_conservation_ratio(0.0330) == 0.60
    assert lv.leverage_conservation_ratio(0.0351) == 0.0


# =========================================================================
#  Large exposures
# =========================================================================

def lex(cid: str, value: float, **kw: object) -> LargeExposureInput:
    return LargeExposureInput.model_validate({"counterparty_id": cid, "exposure_value": value,
                                              **kw})


def test_le_limits_dsib() -> None:
    rows = CALC.large_exposures(
        [lex("a", 25.0), lex("b", 25.01), lex("c", 20.0, counterparty_is_gsib=True),
         lex("d", 20.5, flags={"ca_counterparty_is_canadian_dsib": True}), lex("e", 9.99)],
        tier1_capital=100.0, reporting_bank_is_gsib=False)
    by = {r.counterparty_id: r for r in rows}
    assert by["a"].limit_pct_of_tier1 == 0.25 and not by["a"].breach
    assert by["b"].breach
    assert by["c"].limit_pct_of_tier1 == 0.20 and not by["c"].breach
    assert by["d"].breach and by["d"].limit == pytest.approx(20.0)
    assert not by["e"].reportable and by["a"].reportable


def test_le_limits_gsib_and_smsb() -> None:
    rows = CALC.large_exposures(
        [lex("g", 15.5, counterparty_is_gsib=True),
         lex("d", 19.0, flags={"ca_counterparty_is_canadian_dsib": True}), lex("o", 24.0)],
        tier1_capital=100.0, reporting_bank_is_gsib=True)
    by = {r.counterparty_id: r for r in rows}
    assert by["g"].limit_pct_of_tier1 == 0.15 and by["g"].breach
    assert by["d"].limit_pct_of_tier1 == 0.20 and not by["d"].breach
    assert by["o"].limit_pct_of_tier1 == 0.25
    smsb = CAPillar1(is_dsib=False).large_exposures(
        [lex("g", 20.0, counterparty_is_gsib=True)], 100.0, False)
    assert smsb[0].limit_pct_of_tier1 == 0.25 and not smsb[0].breach


def test_le_exemptions() -> None:
    rows = CALC.large_exposures(
        [lex("goc", 80.0, flags={"ca_exempt_government_of_canada": True}),
         lex("intraday", 50.0, flags={"ca_exempt_intraday_interbank": True}),
         lex("ded1250", 30.0, flags={"ca_exempt_capital_deduction": True, "ca_rw_1250": True}),
         lex("caller", 40.0, is_exempt=True)],
        tier1_capital=100.0, reporting_bank_is_gsib=False)
    by = {r.counterparty_id: r for r in rows}
    assert not by["goc"].breach and by["goc"].reportable
    assert not by["intraday"].reportable and not by["intraday"].breach
    assert by["ded1250"].breach  # footnote 16
    assert not by["caller"].breach
    with pytest.raises(ValueError):
        CALC.large_exposures([lex("x", 1.0)], 0.0, False)


def test_le_helpers() -> None:
    assert le.structure_threshold(1_000.0) == pytest.approx(2.5)
    assert le.structure_threshold(100.0, is_dsib=False) == pytest.approx(1.5)
    assert le.covered_bond_exposure_value(100.0, True) == 25.0
    assert le.covered_bond_exposure_value(100.0, False) == 100.0
    assert le.obs_exposure_value(100.0, 0.0) == pytest.approx(10.0)
    assert le.ccp_clearing_exposure_value("SEGREGATED_IM", 50.0) == 0.0
    assert le.ccp_clearing_exposure_value("PREFUNDED_DF", 50.0) == 50.0
    with pytest.raises(ValueError):
        le.ccp_clearing_exposure_value("OTHER", 1.0)
    assert le.requires_interdependence_review(5.1, 100.0)
    assert not le.requires_interdependence_review(5.0, 100.0)


# =========================================================================
#  CCP
# =========================================================================

def test_kccp_and_kcm() -> None:
    assert cc.k_ccp([1_000.0, 500.0]) == pytest.approx(1_500 * 0.20 * 0.08)
    assert cc.k_ccp([100.0], rw=0.5) == pytest.approx(4.0)
    with pytest.raises(ValueError):
        cc.k_ccp([100.0], rw=0.1)
    assert cc.sft_ead_to_member(100.0, 30.0, 10.0) == 60.0
    assert cc.sft_ead_to_member(10.0, 30.0, 10.0) == 0.0
    assert cc.k_cm(10.0, 5.0, 20.0, 80.0) == pytest.approx(0.5)
    assert cc.k_cm(0.01, 5.0, 20.0, 80.0) == pytest.approx(0.08 * 0.02 * 5.0)  # floor


def test_qccp_clearing_member() -> None:
    r = CALC.ccp_exposure(CCPExposureInput(ccp_id="Q", trade_exposure=1_000.0,
                                           default_fund_contribution=5.0, k_ccp=10.0,
                                           total_default_fund=100.0))
    assert r.trade_rw == 0.02 and r.trade_rwa == pytest.approx(20.0)
    assert r.default_fund_rwa == pytest.approx(12.5 * 0.5)
    assert r.total_rwa == pytest.approx(26.25)


def test_qccp_client_variants() -> None:
    base = {"ccp_id": "Q", "trade_exposure": 100.0, "is_client_cleared_via_member": True}
    assert CALC.ccp_exposure(CCPExposureInput.model_validate(base)).trade_rw == 0.02
    four = CALC.ccp_exposure(CCPExposureInput.model_validate(
        {**base, "flags": {"ca_client_not_protected_joint_default": True}}))
    assert four.trade_rw == 0.04
    with pytest.raises(ValueError):
        CALC.ccp_exposure(CCPExposureInput.model_validate(
            {**base, "flags": {"ca_client_conditions_not_met": True}}))


def test_qccp_cap_and_missing_kccp() -> None:
    # K_CM large relative to the non-QCCP charge -> capped (s.7.1.8.1 C)
    r = CALC.ccp_exposure(CCPExposureInput(
        ccp_id="Q", trade_exposure=0.0, default_fund_contribution=1.0, k_ccp=1_000.0,
        total_default_fund=10.0, ccp_rating=RatingBucket.AAA_TO_AA_MINUS))
    assert r.total_rwa == pytest.approx(12.5 * 1.0)
    missing = CALC.ccp_exposure(CCPExposureInput(ccp_id="Q", trade_exposure=0.0,
                                                 default_fund_contribution=2.0))
    assert missing.default_fund_rwa == pytest.approx(25.0)


def test_non_qccp() -> None:
    r = CALC.ccp_exposure(CCPExposureInput(ccp_id="N", is_qualifying=False, trade_exposure=100.0,
                                           default_fund_contribution=2.0,
                                           ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS))
    assert r.trade_rw == 0.30 and r.trade_rwa == pytest.approx(30.0)
    assert r.default_fund_rwa == pytest.approx(25.0)
    unrated = CALC.ccp_exposure(CCPExposureInput(ccp_id="N", is_qualifying=False,
                                                 trade_exposure=100.0))
    assert unrated.trade_rw == 1.50
    grade_a = CALC.ccp_exposure(CCPExposureInput(ccp_id="N", is_qualifying=False,
                                                 trade_exposure=100.0,
                                                 flags={"ca_ccp_scra_grade_a": True}))
    assert grade_a.trade_rw == 0.40
    corp = CALC.ccp_exposure(CCPExposureInput(ccp_id="N", is_qualifying=False,
                                              trade_exposure=100.0,
                                              flags={"ca_ccp_treated_as_corporate": True}))
    assert corp.trade_rw == 1.00
    former = CALC.ccp_exposure(CCPExposureInput(ccp_id="F", is_qualifying=False,
                                                trade_exposure=100.0,
                                                flags={"ca_former_qccp_within_3_months": True}))
    assert former.trade_rw == 0.02
