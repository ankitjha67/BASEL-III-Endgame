"""Tests for the UK PRA Pillar 1 package (securitisation, SA-CVA, leverage, LE, CCP).

Table cells are asserted against the PRA Rulebook transcription in
``docs/jurisdictions/UK_pillar1_reference.md``; worked examples are computed by
hand from the formulas of Securitisation (CRR) Part Arts 259 and 261, CVA Risk
Part rule 5.24, Leverage Ratio (CRR) Part Art 429, Large Exposures (CRR) Part
Art 395 and CCR (CRR) Part Arts 306-308.
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import AssetClass, Jurisdiction, RatingBucket
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
from src.jurisdictions.uk.pillar1 import UKPillar1
from src.jurisdictions.uk.pillar1 import ccp as ccp_mod
from src.jurisdictions.uk.pillar1 import large_exposures as le
from src.jurisdictions.uk.pillar1 import leverage as lev
from src.jurisdictions.uk.pillar1 import params as p
from src.jurisdictions.uk.pillar1 import sa_cva as cva
from src.jurisdictions.uk.pillar1 import securitisation as sec

U = UKPillar1()


def kssfa(k: float, a: float, d: float, pv: float) -> float:
    """Independent K_SSFA (Art 259(1) / 261(1)) for the hand-worked examples."""
    a_ = -1.0 / (pv * k)
    u, l_ = d - k, max(a - k, 0.0)
    return (math.exp(a_ * u) - math.exp(a_ * l_)) / (a_ * (u - l_))


def tranche(**kw: object) -> SecTrancheInput:
    """Securitisation position with sensible defaults."""
    base: dict[str, object] = dict(tranche_id="t", exposure_amount=100.0, attachment=0.10,
                                   detachment=0.30)
    base.update(kw)
    return SecTrancheInput(**base)  # type: ignore[arg-type]


# =========================================================================
#  Protocol conformance
# =========================================================================


@pytest.mark.parametrize(
    "proto",
    [SecuritisationCalculator, SACVACalculator, LeverageCalculator, LargeExposuresCalculator,
     CCPCalculator],
)
def test_protocol_conformance(proto: type) -> None:
    assert isinstance(U, proto)
    assert U.jurisdiction is Jurisdiction.UK


# =========================================================================
#  Securitisation -- table cells
# =========================================================================

P_CELLS = [
    ("NON_RETAIL_SENIOR_GRANULAR", (0.0, 3.56, -1.85, 0.55, 0.07)),
    ("NON_RETAIL_SENIOR_NON_GRANULAR", (0.11, 2.61, -2.91, 0.68, 0.07)),
    ("NON_RETAIL_NON_SENIOR_GRANULAR", (0.16, 2.87, -1.03, 0.21, 0.07)),
    ("NON_RETAIL_NON_SENIOR_NON_GRANULAR", (0.22, 2.35, -2.46, 0.48, 0.07)),
    ("RETAIL_SENIOR", (0.0, 0.0, -7.48, 0.71, 0.24)),
    ("RETAIL_NON_SENIOR", (0.0, 0.0, -5.78, 0.55, 0.27)),
]


@pytest.mark.parametrize("key,row", P_CELLS)
def test_p_parameter_table(key: str, row: tuple[float, ...]) -> None:
    """Art 259(1) / 261(1) look-up table."""
    assert p.P_PARAMETER_TABLE[key] == row


ERBA_CELLS = [
    (1, (0.15, 0.20, 0.15, 0.70)), (2, (0.15, 0.30, 0.15, 0.90)), (3, (0.25, 0.40, 0.30, 1.20)),
    (4, (0.30, 0.45, 0.40, 1.40)), (5, (0.40, 0.50, 0.60, 1.60)), (6, (0.50, 0.65, 0.80, 1.80)),
    (7, (0.60, 0.70, 1.20, 2.10)), (8, (0.75, 0.90, 1.70, 2.60)), (9, (0.90, 1.05, 2.20, 3.10)),
    (10, (1.20, 1.40, 3.30, 4.20)), (11, (1.40, 1.60, 4.70, 5.80)),
    (12, (1.60, 1.80, 6.20, 7.60)), (13, (2.00, 2.25, 7.50, 8.60)),
    (14, (2.50, 2.80, 9.00, 9.50)), (15, (3.10, 3.40, 10.50, 10.50)),
    (16, (3.80, 4.20, 11.30, 11.30)), (17, (4.60, 5.05, 12.50, 12.50)),
    (18, (12.5, 12.5, 12.5, 12.5)),
]


@pytest.mark.parametrize("cqs,row", ERBA_CELLS)
def test_erba_table_2(cqs: int, row: tuple[float, ...]) -> None:
    """Art 263(3) Table 2."""
    assert p.ERBA_TABLE_2[cqs] == pytest.approx(row)


STS_CELLS = [
    (1, (0.10, 0.10, 0.15, 0.40)), (4, (0.15, 0.25, 0.25, 0.80)), (7, (0.35, 0.45, 0.95, 1.70)),
    (10, (0.70, 0.85, 2.70, 3.45)), (11, (1.20, 1.35, 4.05, 5.00)),
    (14, (2.25, 2.50, 8.10, 8.55)), (16, (3.40, 3.80, 10.15, 10.15)),
    (17, (4.15, 4.55, 12.50, 12.50)),
]


@pytest.mark.parametrize("cqs,row", STS_CELLS)
def test_erba_table_4_sts(cqs: int, row: tuple[float, ...]) -> None:
    """Art 264(3) Table 4."""
    assert p.ERBA_TABLE_4_STS[cqs] == pytest.approx(row)


def test_erba_short_term_tables() -> None:
    """Art 263(2) Table 1 and Art 264(2) Table 3."""
    assert dict(p.ERBA_TABLE_1_SHORT_TERM) == {1: 0.15, 2: 0.50, 3: 1.00, 4: 12.5}
    assert dict(p.ERBA_TABLE_3_SHORT_TERM_STS) == {1: 0.10, 2: 0.30, 3: 0.60, 4: 12.5}


@pytest.mark.parametrize(
    "rating,cqs",
    [("AAA (sf)", 1), ("AA+", 2), ("AA-", 4), ("A", 6), ("BBB-", 10), ("BB", 12), ("B-", 16),
     ("CCC+ (sf)", 17), ("Caa2 (sf)", 17), ("Baa1", 8), ("D", 18), ("C", 18)],
)
def test_long_term_mapping(rating: str, cqs: int) -> None:
    """Art 270F(1) mapping (S&P / Fitch / Moody's rows)."""
    assert sec.long_term_cqs(rating) == cqs


def test_short_term_mapping() -> None:
    """Art 270F(1) short-term rows."""
    assert sec.short_term_cqs("A-1/P-1") == 1
    assert sec.short_term_cqs("A-2 (sf)") == 2
    assert sec.short_term_cqs("F3") == 3
    assert sec.short_term_cqs("B") == 4


def test_sec_sa_lgd_table() -> None:
    """Art 261(1)(a) LGD table and weighted average (Art 261(1)(b))."""
    assert p.SEC_SA_LGD_TABLE["REGULATORY_RRE_LTV_LE_100"] == 0.20
    assert p.SEC_SA_LGD_TABLE["OTHER_SENIOR_NON_RETAIL"] == 0.45
    assert p.SEC_SA_LGD_TABLE["OTHER_SUBORDINATED_NON_RETAIL"] == 0.75
    lgd = sec.sec_sa_pool_lgd([("REGULATORY_RRE_LTV_LE_100", 60.0), ("OTHER", 40.0)])
    assert lgd == pytest.approx(0.2 * 0.6 + 1.0 * 0.4)


# =========================================================================
#  Securitisation -- common parameters
# =========================================================================


def test_tranche_maturity() -> None:
    """Art 257(1)-(2)."""
    assert sec.tranche_maturity_from_legal(6.0) == pytest.approx(5.0)
    assert sec.tranche_maturity_from_legal(4.0) == pytest.approx(1 + 3 * 0.8)
    assert sec.tranche_maturity_from_legal(0.5) == 1.0
    assert sec.tranche_maturity_from_cash_flows([(1.0, 50.0), (3.0, 50.0)]) == pytest.approx(2.0)


def test_effective_number_and_simplified() -> None:
    """Art 259(4), (6)."""
    assert sec.effective_number([1.0] * 40) == pytest.approx(40.0)
    assert sec.effective_number([3.0, 1.0]) == pytest.approx(16 / 10)
    assert sec.simplified_n(0.02) == pytest.approx(50.0)
    n = sec.simplified_n(0.02, cm=0.10, m=5)
    assert n == pytest.approx(1 / (0.02 * 0.10 + (0.10 - 0.02) / 4 * max(1 - 5 * 0.02, 0)))
    with pytest.raises(ValueError):
        sec.simplified_n(0.05)


def test_k_a_and_k_pool() -> None:
    """Art 261(2) K_A; partially unknown delinquency; Art 259(7) K_POOL."""
    assert sec.k_a(0.08, 0.05) == pytest.approx(0.95 * 0.08 + 0.025)
    assert sec.k_a_partially_unknown(96.0, 0.08, 4.0) == pytest.approx((96 * 0.08 + 4) / 100)
    with pytest.raises(ValueError):
        sec.k_a_partially_unknown(90.0, 0.08, 10.0)
    assert sec.k_pool(0.96, 0.05, 0.10) == pytest.approx(0.96 * 0.05 + 0.04 * 0.10)
    with pytest.raises(ValueError):
        sec.k_pool(0.90, 0.05, 0.10)


# =========================================================================
#  Securitisation -- SEC-SA worked examples (Art 261)
# =========================================================================


def test_sec_sa_blended_case() -> None:
    """A < K_A < D: K_SA 8%, W 5% -> K_A 0.101; A 5%, D 15%, p = 1."""
    t = tranche(attachment=0.05, detachment=0.15, k_sa=0.08, w=0.05)
    r = U.securitisation(t)
    ka = 0.101
    expected = 12.5 * (ka - 0.05) / 0.10 + 12.5 * kssfa(ka, 0.05, 0.15, 1.0) * (0.15 - ka) / 0.10
    assert r.approach is SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(expected)
    assert r.risk_weight == pytest.approx(11.22797723737391)
    assert r.rwa == pytest.approx(100.0 * expected)


def test_sec_sa_above_ka() -> None:
    """A >= K_A: RW = 12.5 K_SSFA; K_A 8%, A 10%, D 30% -> 357.44%."""
    r = U.securitisation(tranche(k_sa=0.08))
    assert r.risk_weight == pytest.approx(3.5743646093234873)


def test_sec_sa_d_below_ka_is_1250() -> None:
    """D <= K_A: 1250%."""
    r = U.securitisation(tranche(attachment=0.0, detachment=0.05, k_sa=0.08))
    assert r.risk_weight == 12.5


def test_sec_sa_floors() -> None:
    """15% floor (Art 261(1)); 10% senior STS floor (Art 262)."""
    senior = tranche(attachment=0.15, detachment=1.0, k_sa=0.04, is_senior=True)
    assert U.securitisation(senior).risk_weight == pytest.approx(0.15)
    sts = senior.model_copy(update={"is_stc": True})
    assert 12.5 * kssfa(0.04, 0.15, 1.0, 0.5) < 0.10
    assert U.securitisation(sts).risk_weight == pytest.approx(0.10)
    non_senior_sts = sts.model_copy(update={"is_senior": False})
    assert U.securitisation(non_senior_sts).risk_weight == pytest.approx(0.15)


def test_sec_sa_p_formula_option() -> None:
    """Art 261(1) p = min[1, max[0.5, ...]]; Art 262 STS p = min[0.5, max[0.3, 0.5 x ...]]."""
    lin = 3.56 / 50 - 1.85 * 0.08 + 0.55 * 0.45 + 0.07 * 2.0
    assert sec.p_sec_sa(False, True, 50.0, 0.08, 0.45, 2.0) == pytest.approx(max(0.5, lin))
    assert sec.p_sec_sa(False, True, 50.0, 0.08, 0.45, 2.0, sts=True) == pytest.approx(0.3)
    big = sec.p_sec_sa(False, False, 5.0, 0.0, 1.0, 5.0)
    assert big == pytest.approx(1.0)
    t = tranche(k_sa=0.08, n_effective=50.0, lgd_pool=0.45, maturity_years=2.0, is_senior=True,
                attachment=0.10, detachment=0.30, flags={"sec_sa_calculate_p": True})
    assert U.securitisation(t).risk_weight == pytest.approx(
        max(0.15, 12.5 * kssfa(0.08, 0.10, 0.30, 0.5)))


def test_resecuritisation() -> None:
    """Art 269: W = 0, p = 1.5, floor 100%."""
    t = tranche(attachment=0.20, detachment=0.40, k_sa=0.10, w=0.3, is_resecuritisation=True)
    r = U.securitisation(t)
    assert r.risk_weight == pytest.approx(12.5 * kssfa(0.10, 0.20, 0.40, 1.5))
    assert r.risk_weight == pytest.approx(3.5445172105873057)
    senior = tranche(attachment=0.5, detachment=1.0, k_sa=0.05, is_resecuritisation=True,
                     is_senior=True)
    assert U.securitisation(senior).risk_weight == pytest.approx(1.0)


def test_delinquency_unknown_1250() -> None:
    """Art 261(2): delinquency unknown for > 5% -> 1250%."""
    t = tranche(k_sa=0.08, flags={"delinquency_unknown_over_5pct": True})
    assert U.securitisation(t).risk_weight == 12.5


# =========================================================================
#  Securitisation -- SEC-IRBA worked examples (Art 259)
# =========================================================================


def test_sec_irba_non_senior_granular() -> None:
    """K_IRB 6%, A 10%, D 20%, N 100, LGD 40%, M_T 3: p = 0.4209."""
    pv = sec.p_irba(False, False, 100.0, 0.06, 0.40, 3.0)
    assert pv == pytest.approx(0.16 + 2.87 / 100 - 1.03 * 0.06 + 0.21 * 0.40 + 0.07 * 3)
    assert pv == pytest.approx(0.4209)
    t = tranche(attachment=0.10, detachment=0.20, k_irb=0.06, n_effective=100.0, lgd_pool=0.40,
                maturity_years=3.0, k_sa=0.08)
    r = U.securitisation(t)
    assert r.approach is SecApproachUsed.SEC_IRBA
    assert r.risk_weight == pytest.approx(0.6353265659518815)


def test_sec_irba_p_floor_and_sts() -> None:
    """Art 259(1) p floor 0.3; Art 260 STS 0.5 scalar."""
    lin = -7.48 * 0.05 + 0.71 * 0.3 + 0.24 * 2.0
    assert sec.p_irba(True, True, 10.0, 0.05, 0.3, 2.0) == pytest.approx(max(0.3, lin))
    assert sec.p_irba(True, True, 10.0, 0.05, 0.3, 2.0, sts=True) == pytest.approx(0.3)


def test_sec_irba_precluded_falls_to_sa() -> None:
    """Art 258(2) / 254(1)(b)."""
    t = tranche(k_irb=0.06, n_effective=100.0, lgd_pool=0.4, k_sa=0.08,
                flags={"sec_irba_precluded": True})
    assert U.securitisation(t).approach is SecApproachUsed.SEC_SA


# =========================================================================
#  Securitisation -- SEC-ERBA (Art 263-264)
# =========================================================================


def test_erba_interpolation_senior() -> None:
    """AA- senior, M_T 3: 30% + 0.5 x (45% - 30%) = 37.5% (Art 263(4))."""
    t = tranche(external_rating="AA-", is_senior=True, maturity_years=3.0)
    r = U.securitisation(t)
    assert r.approach is SecApproachUsed.SEC_ERBA
    assert r.risk_weight == pytest.approx(0.375)


def test_erba_non_senior_thickness() -> None:
    """AA- non-senior M_T 3, T = 10%: (40% + 0.5 x 100%) x (1 - 0.1) = 81% (Art 263(5))."""
    t = tranche(external_rating="AA-", maturity_years=3.0, attachment=0.10, detachment=0.20)
    assert U.securitisation(t).risk_weight == pytest.approx(0.81)
    thick = t.model_copy(update={"detachment": 0.90})
    assert U.securitisation(thick).risk_weight == pytest.approx(0.45)


def test_erba_non_senior_floors() -> None:
    """Art 263(6): 15% floor, and not below the senior RW of the same rating/maturity."""
    t = tranche(external_rating="AAA", maturity_years=1.0, attachment=0.10, detachment=0.90)
    assert U.securitisation(t).risk_weight == pytest.approx(0.15)
    t5 = tranche(external_rating="A+", maturity_years=5.0, attachment=0.0, detachment=0.8)
    # non-senior 160% x 0.5 = 80% vs senior 50% -> 80%
    assert U.securitisation(t5).risk_weight == pytest.approx(0.80)
    assert sec.erba_long_term_rw(1, False, 1.0, 0.5, True) == pytest.approx(0.15)


def test_erba_short_term_and_sts() -> None:
    """Art 263(2) Table 1, Art 264(2) Table 3, Art 264(3) Table 4."""
    st = tranche(short_term_rating="A-2/P-2")
    assert U.securitisation(st).risk_weight == pytest.approx(0.50)
    assert U.securitisation(st.model_copy(update={"is_stc": True})).risk_weight == pytest.approx(
        0.30)
    sts = tranche(external_rating="BBB", is_senior=True, maturity_years=5.0, is_stc=True)
    assert U.securitisation(sts).risk_weight == pytest.approx(0.65)


def test_erba_all_other_is_1250() -> None:
    """Table 2 'All other' row."""
    assert U.securitisation(tranche(external_rating="D")).risk_weight == 12.5


def test_hierarchy_sec_sa_before_erba_and_254_2_override() -> None:
    """Art 254(1): SEC-SA before SEC-ERBA; Art 254(2): ERBA instead of SEC-SA when SEC-SA > 25%
    (STS) or SEC-SA > 25% / ERBA > 75% (non-STS)."""
    low = tranche(attachment=0.15, detachment=1.0, k_sa=0.04, is_senior=True,
                  external_rating="AAA", maturity_years=1.0)
    r = U.securitisation(low)
    assert r.approach is SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(0.15)
    high = tranche(k_sa=0.08, external_rating="AA-", maturity_years=3.0)
    r2 = U.securitisation(high)
    assert r2.approach is SecApproachUsed.SEC_ERBA
    assert r2.risk_weight == pytest.approx((0.40 + 0.5 * 1.0) * (1 - 0.2))
    auto = low.model_copy(update={"flags": {"auto_or_equipment_lease_pool": True}})
    assert U.securitisation(auto).approach is SecApproachUsed.SEC_ERBA


def test_unrated_without_pool_data_is_1250() -> None:
    """Art 254(7)."""
    r = U.securitisation(tranche())
    assert (r.approach, r.risk_weight) == (SecApproachUsed.RW_1250, 12.5)


def test_iaa() -> None:
    """Arts 254(5), 265-266: internal grade mapped to ERBA (A senior M 1 -> 50%)."""
    t = tranche(internal_assessment_rating="A", is_senior=True,
                flags={"iaa_permission": True, "abcp": True})
    r = U.securitisation(t)
    assert r.approach is SecApproachUsed.SEC_IAA
    assert r.risk_weight == pytest.approx(0.50)
    bad = t.model_copy(update={"flags": {**t.flags, "iaa_ig_at_first_assignment": False}})
    assert U.securitisation(bad).risk_weight == 12.5


def test_look_through_cap_overrides_floor() -> None:
    """Art 267(1), (4): senior cap = pool average RW, even below the floors."""
    t = tranche(attachment=0.15, detachment=1.0, k_sa=0.008, is_senior=True,
                flags={"look_through": True})
    r = U.securitisation(t)
    assert r.risk_weight == pytest.approx(0.10)
    assert "Art 267" in r.citation
    no_cap = t.model_copy(update={"is_resecuritisation": True})
    assert U.securitisation(no_cap).risk_weight == pytest.approx(1.0)


def test_npe_placeholder() -> None:
    """Art 269A: UK NPE Part not supplied -- BCBS CRE45.4/45.5 placeholders."""
    t = tranche(attachment=0.15, detachment=1.0, k_sa=0.04, is_senior=True,
                is_npl_securitisation=True)
    r = U.securitisation(t)
    assert r.risk_weight == pytest.approx(1.0)
    assert "TODO: VERIFY" in r.citation


def test_art_270_sme_senior_gets_sts_floor() -> None:
    """Art 270: senior SME positions may use Arts 260/262/264."""
    t = tranche(attachment=0.15, detachment=1.0, k_sa=0.04, is_senior=True,
                flags={"art270_sme_senior": True})
    assert U.securitisation(t).risk_weight == pytest.approx(0.10)


def test_qualifying_securitisation_262a() -> None:
    """Art 262A(2): X = 1 - 0.55 x property / exposure."""
    # property 100, exposure 100 -> X = 0.45
    assert sec.qualifying_securitisation_sec_sa_rw(0.5, 1.0, 100.0, 100.0) == 0.20
    assert sec.qualifying_securitisation_sec_sa_rw(0.0, 0.4, 100.0, 100.0) == 0.75
    blended = sec.qualifying_securitisation_sec_sa_rw(0.35, 0.55, 100.0, 100.0)
    assert blended == pytest.approx(0.20 * 0.10 / 0.20 + 0.75 * 0.10 / 0.20)


def test_maximum_capital_requirement() -> None:
    """Art 268(1A): U*Y + sum max(0, V_i - U) Z_i."""
    assert sec.maximum_capital_requirement(0.05, 8.0, [(0.5, 2.0), (0.03, 10.0)]) == (
        pytest.approx(0.05 * 8.0 + 0.45 * 2.0))
    with pytest.raises(ValueError):
        sec.maximum_capital_requirement(1.5, 8.0, [])


def test_synthetic_maturity_mismatch() -> None:
    """Art 252(1)(b): t* = 0.25."""
    v = sec.synthetic_maturity_mismatch_rwa(10.0, 50.0, 2.0, 5.0)
    assert v == pytest.approx(10.0 * 1.75 / 4.75 + 50.0 * 3.0 / 4.75)


# =========================================================================
#  SA-CVA
# =========================================================================


def s(rc: CVARiskClass, bucket: str, rf: str = "x", s_cva: float = 0.0, s_hedge: float = 0.0,
      measure: str = "DELTA", **kw: object) -> CVASensitivityInput:
    """Sensitivity builder."""
    return CVASensitivityInput(risk_class=rc, measure=measure, bucket=bucket, risk_factor=rf,
                               s_cva=s_cva, s_hedge=s_hedge, **kw)  # type: ignore[arg-type]


def test_sa_cva_parameters() -> None:
    """Rule 5.24: m_CVA 1, R 0.01; rule 5.25-5.30 cells."""
    assert (p.SA_CVA_M, p.SA_CVA_R) == (1.0, 0.01)
    assert dict(p.IR_DELTA_RW) == {"1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074, "10Y": 0.0074,
                                   "30Y": 0.0074, "INFLATION": 0.0111}
    assert p.IR_DELTA_CORRELATION[("1Y", "30Y")] == 0.31
    assert p.IR_DELTA_CORRELATION[("30Y", "10Y")] == 0.83
    assert (p.IR_OTHER_CCY_RW, p.FX_DELTA_RW, p.EQ_VEGA_RW_LARGE) == (0.0158, 0.11, 0.78)
    assert p.CCS_RW["2B"] == (0.035, 0.085)
    assert p.RCS_RW[9] == 0.04 and p.RCS_RW[15] == 0.12 and p.RCS_RW[17] == 0.05
    assert p.EQ_DELTA_RW[12] == 0.15 and p.COM_DELTA_RW[4] == 0.80
    assert p.EQ_LARGE_CAP_THRESHOLD_GBP_M == 1600.0


def test_sa_cva_single_bucket_fx() -> None:
    """FX: WS = 11% x 100 - 11% x 60 = 4.4; K_b = sqrt(4.4^2 + 0.01 x 6.6^2)."""
    r = U.sa_cva([s(CVARiskClass.FX, "USD", s_cva=100.0, s_hedge=60.0)])
    expected = math.sqrt(4.4**2 + 0.01 * 6.6**2)
    assert r.k_by_class["FX_DELTA"] == pytest.approx(expected)
    assert r.k_total == pytest.approx(expected)
    assert r.rwa == pytest.approx(12.5 * expected)
    assert (r.m_cva, r.r_hedging_disallowance) == (1.0, 0.01)


def test_sa_cva_cross_bucket_fx() -> None:
    """gamma 0.6: K = sqrt(11^2 + 5.5^2 + 2 x 0.6 x 11 x (-5.5))."""
    r = U.sa_cva([s(CVARiskClass.FX, "USD", s_cva=100.0), s(CVARiskClass.FX, "EUR", s_cva=-50.0)])
    assert r.k_total == pytest.approx(math.sqrt(121 + 30.25 - 2 * 0.6 * 11 * 5.5))


def test_sa_cva_ir_intra_bucket() -> None:
    """USD 1Y 1000 and 5Y -500: WS 11.1 and -3.7, rho 72%."""
    r = U.sa_cva([s(CVARiskClass.INTEREST_RATE, "USD", "1Y", 1000.0),
                  s(CVARiskClass.INTEREST_RATE, "USD", "5Y", -500.0)])
    assert r.k_total == pytest.approx(math.sqrt(11.1**2 + 3.7**2 - 2 * 0.72 * 11.1 * 3.7))


def test_sa_cva_ir_other_currency_and_vega() -> None:
    """Rule 5.25(8)-(9): 1.58%, curve-inflation 40%; (12)-(13): vega 100%, 40%."""
    r = U.sa_cva([s(CVARiskClass.INTEREST_RATE, "NOK", "CURVE", 100.0),
                  s(CVARiskClass.INTEREST_RATE, "NOK", "INFLATION", 100.0)])
    ws = 1.58
    assert r.k_total == pytest.approx(math.sqrt(2 * ws**2 + 2 * 0.4 * ws * ws))
    v = U.sa_cva([s(CVARiskClass.INTEREST_RATE, "GBP", "IR_VOL", 1.0, measure="VEGA"),
                  s(CVARiskClass.INTEREST_RATE, "GBP", "INFLATION_VOL", 1.0, measure="VEGA")])
    assert v.k_by_class["INTEREST_RATE_VEGA"] == pytest.approx(math.sqrt(2 + 0.8))


def test_sa_cva_counterparty_credit_spread_rho() -> None:
    """Rule 5.27(6): rho = 1 x 0.5 x 0.8 for distinct IG/HY names, same tenor."""
    r = U.sa_cva([
        s(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "2a", "5Y", 100.0, name="BANKX",
          is_investment_grade=True),
        s(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "2a", "5Y", 50.0, name="BANKY",
          is_investment_grade=False),
    ])
    assert r.k_total == pytest.approx(math.sqrt(25 + 36 + 2 * 0.4 * 30))
    k = ("1Y", "GRP/A", True)
    lr = ("5Y", "GRP/B", True)
    assert cva.ccs_rho(k, lr, False) == pytest.approx(0.9 * 0.9)
    assert cva.ccs_rho(("1Y", "ITRAXX/S40", True), ("1Y", "ITRAXX/S41", True), True) == 0.9
    assert cva.ccs_rho(("1Y", "ITRAXX", True), ("1Y", "CDX", True), True) == 0.8
    with pytest.raises(ValueError):
        U.sa_cva([s(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "1a", "1Y", 1.0, measure="VEGA")])


def test_sa_cva_ccs_cross_bucket() -> None:
    """Rule 5.27(2): bucket 1 vs 4 = 25%; sub-buckets 1a/1b share bucket 1."""
    r = U.sa_cva([
        s(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "1a", "5Y", 100.0, name="UKT",
          is_investment_grade=True),
        s(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "4", "5Y", 100.0, name="RETAILER",
          is_investment_grade=True),
    ])
    assert r.k_total == pytest.approx(math.sqrt(0.5**2 + 3.0**2 + 2 * 0.25 * 0.5 * 3.0))
    assert cva.gamma(CVARiskClass.COUNTERPARTY_CREDIT_SPREAD, "1A", "1B") == 1.0


@pytest.mark.parametrize(
    "b,c,g",
    [(1, 2, 0.75), (1, 8, 0.5), (1, 9, 0.375), (3, 10, 0.5), (16, 17, 0.75), (1, 16, 0.45),
     (8, 16, 0.45), (15, 3, 0.0), (5, 6, 0.25), (12, 13, 0.25)],
)
def test_sa_cva_reference_spread_gamma(b: int, c: int, g: float) -> None:
    """Rule 5.28(2)(a) table; (b) halved between buckets 1-14 of different quality."""
    assert cva.rcs_gamma(b, c) == pytest.approx(g)


@pytest.mark.parametrize(
    "b,c,g", [(1, 5, 0.15), (12, 13, 0.75), (12, 3, 0.45), (11, 12, 0.0), (11, 2, 0.0)]
)
def test_sa_cva_equity_gamma(b: int, c: int, g: float) -> None:
    """Rule 5.29(4)."""
    assert cva.equity_gamma(b, c) == g


def test_sa_cva_equity_and_commodity() -> None:
    """Single risk factor per bucket: sensitivities net within a bucket; vega 78% large cap."""
    r = U.sa_cva([s(CVARiskClass.EQUITY, "5", "A", 10.0), s(CVARiskClass.EQUITY, "5", "B", -4.0)])
    assert r.k_total == pytest.approx(0.30 * 6.0)
    v = U.sa_cva([s(CVARiskClass.EQUITY, "9", s_cva=1.0, measure="VEGA"),
                  s(CVARiskClass.EQUITY, "12", s_cva=1.0, measure="VEGA")])
    assert v.k_total == pytest.approx(math.sqrt(1.0 + 0.78**2 + 2 * 0.45 * 0.78))
    c = U.sa_cva([s(CVARiskClass.COMMODITY, "3", s_cva=10.0),
                  s(CVARiskClass.COMMODITY, "11", s_cva=10.0)])
    assert c.k_total == pytest.approx(math.sqrt(36 + 25))


def test_sa_cva_sb_capping_and_total_across_classes() -> None:
    """S_b capped at K_b (rule 5.24(2)); classes summed (rules 5.15, 5.17)."""
    sens = [s(CVARiskClass.FX, "USD", s_cva=100.0, s_hedge=100.0),
            s(CVARiskClass.FX, "EUR", s_cva=100.0),
            s(CVARiskClass.COMMODITY, "7", s_cva=10.0)]
    r = U.sa_cva(sens)
    k_usd = math.sqrt(0.01 * 11.0**2)
    s_usd = max(-k_usd, min(0.0, k_usd))
    fx = math.sqrt(k_usd**2 + 11.0**2 + 2 * 0.6 * s_usd * 11.0)
    assert r.k_by_class["FX_DELTA"] == pytest.approx(fx)
    assert r.k_total == pytest.approx(fx + 2.0)


# =========================================================================
#  Leverage
# =========================================================================


def test_leverage_aggregation() -> None:
    """Art 429(4), 429a, 429c-429f worked example."""
    inp = LeverageInputs(
        on_balance_sheet_assets=1000.0, tier1_deductions=10.0, derivative_rc=50.0,
        derivative_pfe_addon=30.0, derivative_cash_vm_received=20.0,
        written_credit_derivative_notional=40.0, written_credit_derivative_offsets=15.0,
        sft_gross_assets=200.0, sft_netted_cash_payables=50.0, sft_ccr_addon=5.0,
        obs_notional_by_ccf={0.1: 100.0, 0.4: 200.0, 0.0: 50.0}, central_bank_reserves=100.0,
        client_cleared_trade_exposures_exempt=20.0,
    )
    r = U.leverage_exposure(inp)
    assert r.derivatives == pytest.approx(1.4 * (30.0 + 30.0) + 25.0)
    assert r.sfts == pytest.approx(155.0)
    assert r.off_balance_sheet == pytest.approx(10.0 + 80.0 + 5.0)
    assert r.exclusions == pytest.approx(130.0)
    assert r.total_exposure == pytest.approx(1000 + 109 + 155 + 95 - 130)
    assert lev.leverage_ratio(61.45, r.total_exposure) == pytest.approx(0.05)


def test_leverage_flags() -> None:
    """Alpha 1 (CCR Part Art 274(2)); VM conditions unmet (Art 429c(3)); A1 netting unmet."""
    inp = LeverageInputs(on_balance_sheet_assets=0.0, derivative_rc=50.0,
                         derivative_cash_vm_received=20.0, derivative_pfe_addon=30.0,
                         central_bank_reserves=10.0,
                         flags={"alpha_one_counterparties": True, "cash_vm_conditions_met": False,
                                "central_bank_netting_conditions_met": False})
    r = U.leverage_exposure(inp)
    assert r.derivatives == pytest.approx(80.0)
    assert r.exclusions == 0.0


def test_sft_addon() -> None:
    """Art 429e(2)-(3)."""
    pairs = [(100.0, 90.0), (50.0, 70.0)]
    assert lev.sft_addon(pairs, under_master_netting=False) == pytest.approx(10.0)
    assert lev.sft_addon(pairs, under_master_netting=True) == 0.0


# =========================================================================
#  Large exposures
# =========================================================================


def lex(cid: str, value: float, **kw: object) -> LargeExposureInput:
    """Large exposure builder."""
    return LargeExposureInput(counterparty_id=cid, exposure_value=value, **kw)  # type: ignore[arg-type]


def test_le_general_limit_edges() -> None:
    """Art 395(1): 25% of Tier 1; breach only above the limit; reportable from 10%."""
    rows = U.large_exposures([lex("a", 250.0), lex("b", 250.01), lex("c", 99.0),
                              lex("d", 100.0)], 1000.0, False)
    assert [r.breach for r in rows] == [False, True, False, False]
    assert [r.reportable for r in rows] == [True, True, False, True]
    assert rows[0].limit == pytest.approx(250.0)
    assert rows[0].limit_pct_of_tier1 == pytest.approx(0.25)


def test_le_gbp_260m_reporting() -> None:
    """Art 394(1): >= GBP 260m reportable even below 10% of Tier 1."""
    rows = U.large_exposures([lex("a", 260.0)], 5000.0, False)
    assert rows[0].reportable and not rows[0].breach


def test_le_gsii_limit() -> None:
    """Art 395(1) third subparagraph: G-SII to G-SII 15%."""
    rows = U.large_exposures([lex("g", 160.0, counterparty_is_gsib=True)], 1000.0, True)
    assert rows[0].limit == pytest.approx(150.0) and rows[0].breach
    grace = lex("g", 160.0, counterparty_is_gsib=True, flags={"gsii_compliance_period": True})
    assert not U.large_exposures([grace], 1000.0, True)[0].breach
    assert not U.large_exposures([lex("g", 160.0, counterparty_is_gsib=True)], 1000.0,
                                 False)[0].breach


def test_le_institution_gbp_130m() -> None:
    """Art 395(1): institutions max(25% T1, GBP 130m), capped at 100% of T1."""
    bank = AssetClass.BANK
    small = U.large_exposures([lex("b", 129.0, counterparty_asset_class=bank)], 400.0, False)[0]
    assert small.limit == pytest.approx(130.0) and not small.breach
    tiny = U.large_exposures([lex("b", 110.0, counterparty_asset_class=bank)], 100.0, False)[0]
    assert tiny.limit == pytest.approx(100.0) and tiny.breach
    large = U.large_exposures([lex("b", 300.0, counterparty_asset_class=bank)], 1000.0, False)[0]
    assert large.limit == pytest.approx(250.0) and large.breach


def test_le_exemptions() -> None:
    """Art 400(1)/(2): exempt exposures do not breach but are still reported."""
    rows = U.large_exposures([lex("s", 900.0, flags={"art400_1_a": True}),
                              lex("x", 900.0, is_exempt=True)], 1000.0, False)
    assert all(r.reportable and not r.breach for r in rows)
    assert "Art 400(1)(a)" in rows[0].citation


def test_le_trading_book_excess() -> None:
    """Art 395(5), Art 397(2)-(3) Table 1."""
    assert le.trading_book_excess_factor(0.3, 5) == 2.0
    assert [le.trading_book_excess_factor(x, 11) for x in (0.3, 0.5, 0.7, 0.9, 2.0, 3.0)] == [
        2.0, 3.0, 4.0, 5.0, 6.0, 9.0]
    assert le.trading_book_excess_permitted(4000.0, 200.0, 1000.0, 5)
    assert not le.trading_book_excess_permitted(5100.0, 200.0, 1000.0, 5)
    assert not le.trading_book_excess_permitted(100.0, 300.0, 1000.0, 5)
    assert not le.trading_book_excess_permitted(100.0, 200.0, 1000.0, 11, 6100.0)


# =========================================================================
#  CCP
# =========================================================================


def test_qccp_trade_and_default_fund() -> None:
    """Art 306(1)(a) 2%; Art 308(2) K_i = max{K_CCP DF_i/(DF_CCP + DF_CM); 8% x 2% x DF_i}."""
    e = CCPExposureInput(ccp_id="c", trade_exposure=1000.0, default_fund_contribution=10.0,
                         k_ccp=50.0, total_default_fund=500.0)
    r = U.ccp_exposure(e)
    assert r.trade_rw == 0.02 and r.trade_rwa == pytest.approx(20.0)
    assert r.default_fund_rwa == pytest.approx(12.5 * 1.0)
    assert r.total_rwa == pytest.approx(32.5)
    assert ccp_mod.qccp_default_fund_capital(10.0, 0.1, 1000.0) == pytest.approx(0.016)


def test_non_qccp() -> None:
    """Art 306(1)(b) via Art 107(2)(b) (corporate, A -> 50%); Art 309 K = DF + UC."""
    e = CCPExposureInput(ccp_id="n", is_qualifying=False, trade_exposure=100.0,
                         default_fund_contribution=10.0, ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS)
    r = U.ccp_exposure(e)
    assert r.trade_rw == 0.50 and r.trade_rwa == pytest.approx(50.0)
    assert r.default_fund_rwa == pytest.approx(125.0)
    unrated = e.model_copy(update={"ccp_rating": RatingBucket.UNRATED})
    assert U.ccp_exposure(unrated).trade_rw == 1.0
    ceasing = CCPExposureInput(ccp_id="z", trade_exposure=100.0,
                               flags={"ccp_ceasing_conditions": True})
    assert U.ccp_exposure(ceasing).trade_rw == 1.0


def test_client_clearing_variants() -> None:
    """Art 305(2) 2%; Art 305(3) 4%; Art 306(1)(c) zero exposure value."""
    base = CCPExposureInput(ccp_id="c", trade_exposure=100.0, is_client_cleared_via_member=True)
    assert U.ccp_exposure(base).trade_rw == 0.02
    jd = base.model_copy(update={"flags": {"art305_3_joint_default_unprotected": True}})
    assert U.ccp_exposure(jd).trade_rw == 0.04
    fail = base.model_copy(update={"flags": {"art305_2_conditions_met": False},
                                   "ccp_rating": RatingBucket.AAA_TO_AA_MINUS})
    assert U.ccp_exposure(fail).trade_rw == 0.20
    zero = CCPExposureInput(ccp_id="c", trade_exposure=100.0,
                            flags={"cm_no_client_reimbursement": True})
    assert U.ccp_exposure(zero).trade_rwa == 0.0


def test_qccp_cap_art_303_2() -> None:
    """Art 303(2): QCCP requirement capped at the non-qualifying requirement."""
    e = CCPExposureInput(ccp_id="c", trade_exposure=0.0, default_fund_contribution=10.0,
                         k_ccp=1000.0, total_default_fund=20.0)
    r = U.ccp_exposure(e)
    assert r.default_fund_rwa == pytest.approx(125.0)
    assert "Art 303(2)" in r.citation


def test_qccp_missing_kccp_conservative() -> None:
    """K_CCP not supplied: conservative Art 309 fall-back."""
    e = CCPExposureInput(ccp_id="c", trade_exposure=0.0, default_fund_contribution=10.0)
    assert U.ccp_exposure(e).default_fund_rwa == pytest.approx(125.0)
