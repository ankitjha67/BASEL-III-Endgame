"""Tests for the EU CRR3 Pillar 1 package (securitisation, SA-CVA, leverage, LE, CCP).

Every expected value is either a cell of a CRR table or a hand calculation from the
CRR formula with the inputs stated in the test.
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import AssetClass, Jurisdiction, RatingBucket
from src.jurisdictions.eu.pillar1 import EUPillar1
from src.jurisdictions.eu.pillar1 import ccp as ccp_mod
from src.jurisdictions.eu.pillar1 import large_exposures as le_mod
from src.jurisdictions.eu.pillar1 import leverage as lev_mod
from src.jurisdictions.eu.pillar1 import params as prm
from src.jurisdictions.eu.pillar1 import sa_cva as cva_mod
from src.jurisdictions.eu.pillar1 import securitisation as sec
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

RC = CVARiskClass


def _kssfa(k: float, a_pt: float, d_pt: float, p: float) -> float:
    """Hand transcription of K_SSFA (Articles 259(1)/261(1))."""
    a = -1.0 / (p * k)
    u = d_pt - k
    lo = max(a_pt - k, 0.0)
    return (math.exp(a * u) - math.exp(a * lo)) / (a * (u - lo))


def _t(**kw: object) -> SecTrancheInput:
    base: dict[str, object] = {
        "tranche_id": "t",
        "exposure_amount": 100.0,
        "attachment": 0.15,
        "detachment": 0.25,
    }
    base.update(kw)
    return SecTrancheInput(**base)  # type: ignore[arg-type]


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
def test_protocol_conformance(proto: type) -> None:
    calc = EUPillar1()
    assert isinstance(calc, proto)
    assert calc.jurisdiction is Jurisdiction.EU


# =========================================================================
#  Securitisation tables -- Articles 259, 263, 264
# =========================================================================


def test_irba_p_table_cells() -> None:
    t = prm.SEC_IRBA_P_TABLE
    assert t[("NON_RETAIL", "SENIOR_GRANULAR")] == (0.0, 3.56, -1.85, 0.55, 0.07)
    assert t[("NON_RETAIL", "SENIOR_NON_GRANULAR")] == (0.11, 2.61, -2.91, 0.68, 0.07)
    assert t[("NON_RETAIL", "NON_SENIOR_GRANULAR")] == (0.16, 2.87, -1.03, 0.21, 0.07)
    assert t[("NON_RETAIL", "NON_SENIOR_NON_GRANULAR")] == (0.22, 2.35, -2.46, 0.48, 0.07)
    assert t[("RETAIL", "SENIOR")] == (0.0, 0.0, -7.48, 0.71, 0.24)
    assert t[("RETAIL", "NON_SENIOR")] == (0.0, 0.0, -5.78, 0.55, 0.27)


@pytest.mark.parametrize(
    ("cqs", "row"),
    [
        (1, (0.15, 0.20, 0.15, 0.70)),
        (4, (0.30, 0.45, 0.40, 1.40)),
        (10, (1.20, 1.40, 3.30, 4.20)),
        (15, (3.10, 3.40, 10.50, 10.50)),
        (17, (4.60, 5.05, 12.50, 12.50)),
    ],
)
def test_erba_table2_cells(cqs: int, row: tuple[float, ...]) -> None:
    assert prm.SEC_ERBA_LONG_TERM[cqs] == row


@pytest.mark.parametrize(
    ("cqs", "row"),
    [
        (1, (0.10, 0.10, 0.15, 0.40)),
        (6, (0.30, 0.40, 0.60, 1.35)),
        (11, (1.20, 1.35, 4.05, 5.00)),
        (17, (4.15, 4.55, 12.50, 12.50)),
    ],
)
def test_erba_table4_sts_cells(cqs: int, row: tuple[float, ...]) -> None:
    assert prm.SEC_ERBA_LONG_TERM_STS[cqs] == row


def test_short_term_tables() -> None:
    assert sec.erba_rw(None, "A-1/P-1", True, 1.0, 0.1, sts=False) == 0.15
    assert sec.erba_rw(None, "A-2/P-2", True, 1.0, 0.1, sts=False) == 0.50
    assert sec.erba_rw(None, "A-3/P-3", True, 1.0, 0.1, sts=False) == 1.00
    assert sec.erba_rw(None, "OTHERS", True, 1.0, 0.1, sts=False) == 12.5
    assert sec.erba_rw(None, "A-2/P-2", True, 1.0, 0.1, sts=True) == 0.30


# =========================================================================
#  SEC-ERBA interpolation and thickness -- Article 263(4)-(6)
# =========================================================================


def test_erba_maturity_interpolation_senior() -> None:
    # CQS 5 senior: 40 % at 1y, 50 % at 5y; M_T = 3 -> 45 %
    assert sec.erba_rw("CQS5", None, True, 3.0, 0.1, sts=False) == pytest.approx(0.45)
    # M_T bounded to [1, 5] (Art. 257(2))
    assert sec.erba_rw("CQS5", None, True, 0.2, 0.1, sts=False) == pytest.approx(0.40)
    assert sec.erba_rw("CQS5", None, True, 9.0, 0.1, sts=False) == pytest.approx(0.50)


def test_erba_non_senior_thickness() -> None:
    # CQS 5 non-senior: 60 % / 160 % -> 110 % at 3y; T = 0,10 -> x 0,9 = 99 %
    assert sec.erba_rw("CQS5", None, False, 3.0, 0.10, sts=False) == pytest.approx(0.99)
    # T = 0,6 -> min(T, 50 %) -> x 0,5 = 55 % (>= senior 45 %)
    assert sec.erba_rw("CQS5", None, False, 3.0, 0.60, sts=False) == pytest.approx(0.55)


def test_erba_non_senior_floors() -> None:
    # CQS 1 non-senior 1y: 15 % x 0,5 = 7,5 % -> floor 15 % (Art. 263(6))
    assert sec.erba_rw("AAA", None, False, 1.0, 0.8, sts=False) == pytest.approx(0.15)
    # CQS 2 non-senior at 5y, thick: 90 % x 0,5 = 45 % >= senior 30 %
    assert sec.erba_rw("CQS2", None, False, 5.0, 0.9, sts=False) == pytest.approx(0.45)


def test_rating_mapping_and_all_other() -> None:
    assert sec.long_term_cqs("AA-") == 4
    assert sec.long_term_cqs("BBB-") == 10
    assert sec.long_term_cqs("CCC") == 17
    assert sec.long_term_cqs("7") == 7
    assert sec.long_term_cqs("D") is None
    assert sec.erba_rw("D", None, True, 2.0, 0.1, sts=False) == 12.5


# =========================================================================
#  SSFA, SEC-SA and SEC-IRBA hand-worked examples
# =========================================================================


def test_sec_sa_mezzanine_hand_worked() -> None:
    # K_SA 8 %, W 10 % -> K_A = 0,9 x 0,08 + 0,1 x 0,5 = 0,122 (Art. 261(2))
    assert sec.k_a(0.08, 0.10) == pytest.approx(0.122)
    r = EUPillar1().securitisation(_t(k_sa=0.08, w=0.10))
    expected = 12.5 * _kssfa(0.122, 0.15, 0.25, 1.0)
    assert expected == pytest.approx(6.781671, rel=1e-6)
    assert r.approach is SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(expected)
    assert r.rwa == pytest.approx(100 * expected)


def test_sec_sa_straddle_blend() -> None:
    # A = 5 % < K_A = 12,2 % < D = 20 %: blended branch of Art. 261(1)
    r = EUPillar1().securitisation(_t(k_sa=0.08, w=0.10, attachment=0.05, detachment=0.20))
    exp = (0.122 - 0.05) / 0.15 * 12.5 + (0.20 - 0.122) / 0.15 * 12.5 * _kssfa(
        0.122, 0.05, 0.20, 1.0
    )
    assert r.risk_weight == pytest.approx(exp)
    assert r.risk_weight == pytest.approx(10.802344, rel=1e-6)


def test_sec_sa_below_ka_1250() -> None:
    r = EUPillar1().securitisation(_t(k_sa=0.08, w=0.10, attachment=0.0, detachment=0.10))
    assert r.risk_weight == 12.5


def test_sec_sa_floors_sts_and_non_sts() -> None:
    senior = {"k_sa": 0.08, "attachment": 0.30, "detachment": 1.0, "is_senior": True}
    non_sts = EUPillar1().securitisation(_t(**senior))
    assert non_sts.risk_weight == pytest.approx(0.15)  # 9,13 % -> 15 % floor (Art. 261(1))
    sts = EUPillar1().securitisation(_t(**senior, is_stc=True))
    assert sts.risk_weight == pytest.approx(0.10)  # Art. 262 senior floor 10 %
    # STS non-senior keeps the 15 % floor
    sts_ns = EUPillar1().securitisation(
        _t(k_sa=0.08, attachment=0.40, detachment=0.5, is_stc=True)
    )
    assert sts_ns.risk_weight >= 0.15


def test_sec_irba_hand_worked() -> None:
    # Non-retail senior granular: p = max(0,3; 3,56/100 - 1,85x0,05 + 0,55x0,4 + 0,07x3)
    p = sec.irba_p(0.05, 0.4, 100.0, 3.0, senior=True, retail=False)
    assert p == pytest.approx(0.0356 - 0.0925 + 0.22 + 0.21)
    t = _t(
        k_irb=0.05,
        lgd_pool=0.4,
        n_effective=100.0,
        maturity_years=3.0,
        attachment=0.10,
        detachment=1.0,
        is_senior=True,
    )
    r = EUPillar1().securitisation(t)
    assert r.approach is SecApproachUsed.SEC_IRBA
    # 12,5 x K_SSFA = 1,78 % -> 15 % floor (Art. 259(1))
    assert 12.5 * _kssfa(0.05, 0.10, 1.0, p) == pytest.approx(0.017760, rel=1e-4)
    assert r.risk_weight == pytest.approx(0.15)
    sts = EUPillar1().securitisation(t.model_copy(update={"is_stc": True}))
    assert sts.risk_weight == pytest.approx(0.10)


def test_sec_irba_non_senior_non_granular() -> None:
    p = sec.irba_p(0.05, 0.4, 10.0, 3.0, senior=False, retail=False)
    assert p == pytest.approx(0.22 + 0.235 - 0.123 + 0.192 + 0.21)
    t = _t(k_irb=0.05, lgd_pool=0.4, n_effective=10.0, maturity_years=3.0,
           attachment=0.06, detachment=0.10)  # fmt: skip
    assert EUPillar1().securitisation(t).risk_weight == pytest.approx(
        12.5 * _kssfa(0.05, 0.06, 0.10, p)
    )
    assert 12.5 * _kssfa(0.05, 0.06, 0.10, p) == pytest.approx(5.796798, rel=1e-6)


def test_irba_p_retail_sts_and_floor() -> None:
    p = sec.irba_p(0.05, 0.4, 1000.0, 2.0, senior=False, retail=True)
    assert p == pytest.approx(-0.289 + 0.22 + 0.54)
    p_sts = sec.irba_p(0.05, 0.4, 1000.0, 2.0, senior=False, retail=True, sts=True)
    assert p_sts == pytest.approx(0.3)  # 0,5 x 0,471 = 0,2355 -> floor 0,3 (Art. 260)


def test_effective_number_and_lgd() -> None:
    assert sec.effective_number([10, 10, 10, 10]) == pytest.approx(4.0)
    assert sec.exposure_weighted_lgd([0.4, 0.2], [1.0, 3.0]) == pytest.approx(0.25)
    assert sec.simplified_n(0.02) == pytest.approx(50.0)
    assert sec.mixed_pool_capital(0.04, 0.08, 0.96) == pytest.approx(0.96 * 0.04 + 0.04 * 0.08)
    with pytest.raises(ValueError):
        sec.mixed_pool_capital(0.04, 0.08, 0.90)


def test_tranche_maturity_legal() -> None:
    assert sec.tranche_maturity_from_legal(6.0) == pytest.approx(5.0)
    assert sec.tranche_maturity_from_legal(3.0) == pytest.approx(2.6)


# =========================================================================
#  Hierarchy -- Article 254
# =========================================================================


def test_hierarchy_rated_non_sts_switches_to_erba() -> None:
    # SEC-SA RW 678 % > 25 % -> SEC-ERBA (Art. 254(2)(b))
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, w=0.10, external_rating="CQS8", maturity_years=1.0)
    )
    assert r.approach is SecApproachUsed.SEC_ERBA
    # non-senior CQS 8 at 1y: 170 % x (1 - 0,10) = 153 %
    assert r.risk_weight == pytest.approx(1.53)


def test_hierarchy_rated_low_rw_stays_sec_sa() -> None:
    # Senior: SEC-SA 15 % <= 25 % and SEC-ERBA (CQS 1, 1y) 15 % <= 75 % -> SEC-SA
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, attachment=0.30, detachment=1.0, is_senior=True, external_rating="AAA")
    )
    assert r.approach is SecApproachUsed.SEC_SA
    elect = _t(k_sa=0.08, attachment=0.30, detachment=1.0, is_senior=True,
               external_rating="AAA", flags={"eu_254_3_erba_election": True})  # fmt: skip
    assert EUPillar1().securitisation(elect).approach is SecApproachUsed.SEC_ERBA
    auto = elect.model_copy(update={"flags": {"eu_254_2_c_auto": True}})
    assert EUPillar1().securitisation(auto).approach is SecApproachUsed.SEC_ERBA


def test_hierarchy_unrated_without_ksa_is_1250() -> None:
    r = EUPillar1().securitisation(_t())
    assert r.approach is SecApproachUsed.RW_1250 and r.risk_weight == 12.5


def test_hierarchy_sa_prohibited_uses_erba() -> None:
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, external_rating="CQS3", flags={"eu_sec_sa_prohibited": True})
    )
    assert r.approach is SecApproachUsed.SEC_ERBA


def test_delinquency_unknown_over_5pct() -> None:
    r = EUPillar1().securitisation(_t(k_sa=0.02, flags={"eu_delinquency_unknown_over_5pct": True}))
    assert r.risk_weight == 12.5
    assert sec.k_a_with_unknown_delinquency(0.10, 0.04) == pytest.approx(0.96 * 0.10 + 0.04)
    assert sec.k_a_with_unknown_delinquency(0.10, 0.06) == 1.0


def test_iaa_uses_erba_tables() -> None:
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, internal_assessment_rating="CQS3", is_senior=True,
           attachment=0.3, detachment=1.0, flags={"eu_iaa_permitted": True})
    )  # fmt: skip
    assert r.approach is SecApproachUsed.SEC_IAA
    assert r.risk_weight == pytest.approx(0.25)  # Table 2, CQS 3 senior 1y


def test_resecuritisation() -> None:
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, w=0.3, attachment=0.30, detachment=1.0, is_resecuritisation=True)
    )
    assert r.approach is SecApproachUsed.SEC_SA
    # W = 0 (Art. 269(1)(a)), p = 1,5 -> tiny RW -> 100 % floor (269(1)(c))
    assert r.risk_weight == pytest.approx(1.00)
    thin = EUPillar1().securitisation(
        _t(k_sa=0.08, attachment=0.10, detachment=0.15, is_resecuritisation=True)
    )
    assert thin.risk_weight == pytest.approx(12.5 * _kssfa(0.08, 0.10, 0.15, 1.5))


# =========================================================================
#  STS / STC -- Articles 243, 260, 262, 264, 270
# =========================================================================


def test_sts_erba_and_sa() -> None:
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, w=0.10, external_rating="CQS6", is_stc=True, maturity_years=5.0)
    )
    assert r.approach is SecApproachUsed.SEC_ERBA  # STS SEC-SA > 25 % (254(2)(a))
    assert r.risk_weight == pytest.approx(1.35 * 0.9)  # Table 4 CQS 6 non-senior 5y, T = 0,1


def test_synthetic_sts_investor_not_preferential() -> None:
    base = {"k_sa": 0.08, "attachment": 0.30, "detachment": 1.0, "is_senior": True,
            "is_stc": True, "is_synthetic": True}  # fmt: skip
    investor = EUPillar1().securitisation(_t(**base))
    assert investor.risk_weight == pytest.approx(0.15)
    assert investor.notes
    originator = EUPillar1().securitisation(_t(**base, flags={"eu_originator": True}))
    assert originator.risk_weight == pytest.approx(0.10)  # Art. 270(1)


def test_sts_243_not_met() -> None:
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, attachment=0.3, detachment=1.0, is_senior=True, is_stc=True,
           flags={"eu_243_criteria_not_met": True})
    )  # fmt: skip
    assert r.risk_weight == pytest.approx(0.15)


# =========================================================================
#  Output floor p (Art. 465(13)), caps (267, 268), NPE (269a), 270a
# =========================================================================


def test_output_floor_p_for_irba_positions() -> None:
    t = _t(k_irb=0.05, lgd_pool=0.4, n_effective=100.0, k_sa=0.08, attachment=0.10,
           detachment=0.30)  # fmt: skip
    r = EUPillar1(year=2027, for_output_floor=True).securitisation(t)
    assert r.approach is SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(12.5 * _kssfa(0.08, 0.10, 0.30, 0.5))
    later = EUPillar1(year=2033, for_output_floor=True).securitisation(t)
    assert later.risk_weight == pytest.approx(12.5 * _kssfa(0.08, 0.10, 0.30, 1.0))
    sts = EUPillar1(year=2027, for_output_floor=True).securitisation(
        t.model_copy(update={"is_stc": True})
    )
    assert sts.risk_weight == pytest.approx(12.5 * _kssfa(0.08, 0.10, 0.30, 0.25))


def test_look_through_cap_267() -> None:
    t = _t(k_sa=0.01, w=0.0, attachment=0.005, detachment=1.0, is_senior=True,
           flags={"eu_267_look_through": True})  # fmt: skip
    r = EUPillar1().securitisation(t)
    # look-through RW = 12,5 x 1 % = 12,5 % < 15 % floor; 267(4) lets it apply
    assert r.approach is SecApproachUsed.LOOK_THROUGH
    assert r.risk_weight == pytest.approx(0.125)


def test_max_capital_268() -> None:
    # K_SA 0,5 %, senior A = 2 %: SEC-SA gives the 15 % floor; Art. 268 cap expressed as a
    # RW on a single-tranche holding = 12,5 x 0,005 / 0,98 = 6,38 % -> binds
    t = _t(k_sa=0.005, attachment=0.02, detachment=1.0, is_senior=True,
           flags={"eu_268_max_capital": True, "eu_originator": True})  # fmt: skip
    r = EUPillar1().securitisation(t)
    assert r.risk_weight == pytest.approx(12.5 * 0.005 / 0.98)
    assert "268" in r.citation and r.notes
    # investor using SEC-SA: no Article 268 cap
    inv = EUPillar1().securitisation(t.model_copy(update={"flags": {"eu_268_max_capital": True}}))
    assert inv.risk_weight == pytest.approx(0.15)
    # not binding where the cap exceeds the RW
    t2 = _t(k_sa=0.02, attachment=0.03, detachment=0.20,
            flags={"eu_268_max_capital": True, "eu_sponsor": True})  # fmt: skip
    assert EUPillar1().securitisation(t2).risk_weight == pytest.approx(
        12.5 * _kssfa(0.02, 0.03, 0.20, 1.0)
    )


def test_npe_floor_and_qualifying_senior() -> None:
    npe = EUPillar1().securitisation(
        _t(k_sa=0.08, attachment=0.40, detachment=1.0, is_senior=True, is_npl_securitisation=True)
    )
    assert npe.risk_weight == pytest.approx(1.00)  # Art. 269a(2)
    q = _t(k_sa=0.06, attachment=0.40, detachment=1.0, is_senior=True,
           is_npl_securitisation=True, flags={"eu_269a_qualifying_traditional": True,
                                              "eu_267_look_through": True})  # fmt: skip
    # 269a(6): look-through 12,5 x 6 % = 75 % < 100 % -> 75 % (floor 50 %)
    assert EUPillar1().securitisation(q).risk_weight == pytest.approx(0.75)
    # ERBA positions are not floored (Art. 269a(2) 'except when Article 263 is applied')
    rated = EUPillar1().securitisation(
        _t(k_sa=0.08, w=0.1, external_rating="CQS1", is_npl_securitisation=True)
    )
    assert rated.approach is SecApproachUsed.SEC_ERBA and rated.risk_weight < 1.0


def test_npe_formulas() -> None:
    cr = sec.npe_max_capital(1000, 300, 200, 800, 1000, 0, 500)
    assert cr == pytest.approx(80 + max(300 - 160, 0) + 40)
    rw = sec.npe_senior_look_through_rw(1000, 500, 300, 200, 800, 1000, 200, 0)
    assert rw == pytest.approx((1000 + 12.5 * 140 + 500) / (640 + 200))
    assert sec.non_refundable_purchase_price_discount(1000, 300, 100, 50) == pytest.approx(550)


def test_additional_rw_270a() -> None:
    r = EUPillar1().securitisation(
        _t(k_sa=0.08, attachment=0.3, detachment=1.0, is_senior=True,
           flags={"eu_270a_breach": True})
    )  # fmt: skip
    assert r.risk_weight == pytest.approx(0.15 * 3.5)
    assert sec.additional_rw_270a(5.0) == 12.5


def test_synthetic_maturity_mismatch() -> None:
    out = sec.synthetic_maturity_mismatch_rwea(10.0, 100.0, 2.0, 4.0)
    assert out == pytest.approx(10 * (1.75 / 3.75) + 100 * (2 / 3.75))


def test_bad_tranche() -> None:
    with pytest.raises(ValueError):
        EUPillar1().securitisation(_t(attachment=0.3, detachment=0.3))


# =========================================================================
#  SA-CVA -- Articles 383-383z
# =========================================================================


def _s(rc: CVARiskClass, bucket: str, rf: str = "", s_cva: float = 0.0, s_hedge: float = 0.0,
       measure: str = "DELTA", name: str = "", **flags: bool) -> CVASensitivityInput:  # fmt: skip
    return CVASensitivityInput(risk_class=rc, measure=measure, bucket=bucket, risk_factor=rf,
                               s_cva=s_cva, s_hedge=s_hedge, name=name, flags=flags)  # fmt: skip


def test_sacva_table_cells() -> None:
    assert prm.SACVA_IR_RW_SPECIFIED == {"1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074,
                                         "10Y": 0.0074, "30Y": 0.0074}  # fmt: skip
    assert prm.SACVA_IR_TENOR_CORR[("1Y", "30Y")] == 0.31
    assert prm.SACVA_IR_TENOR_CORR[("5Y", "30Y")] == 0.68
    assert prm.SACVA_CCS_RW[4] == 0.05 and prm.SACVA_CCS_RW[15] == 0.12
    assert prm.SACVA_RCS_RW[11] == 0.015 and prm.SACVA_RCS_RW[19] == 0.05
    assert prm.SACVA_EQ_RW[2] == 0.60 and prm.SACVA_EQ_RW[12] == 0.15
    assert prm.SACVA_COM_RW[4] == 0.40 and prm.SACVA_COM_RW[6] == 0.80
    assert prm.SACVA_CCS_CROSS_CORR[("FIN", "COVERED")] == 0.20
    assert prm.SACVA_CCS_CROSS_CORR[("INDEX", "OTHER")] == 0.0
    assert prm.SACVA_RCS_CROSS_CORR[("SOV", "RGLA")] == 0.75
    assert prm.SACVA_M_CVA == 1.0 and prm.SACVA_R == 0.01


def test_sacva_ir_single_bucket_hand_worked() -> None:
    sens = [
        _s(RC.INTEREST_RATE, "EUR", "1Y", s_cva=100.0, s_hedge=40.0),
        _s(RC.INTEREST_RATE, "EUR", "5Y", s_cva=50.0),
    ]
    ws1, ws5, h1 = 0.0111 * 60.0, 0.0074 * 50.0, 0.0111 * 40.0
    kb = math.sqrt(ws1**2 + ws5**2 + 2 * 0.72 * ws1 * ws5 + 0.01 * h1**2)
    r = EUPillar1().sa_cva(sens)
    assert r.k_by_class["INTEREST_RATE_DELTA"] == pytest.approx(kb)
    assert r.k_total == pytest.approx(kb)
    assert r.rwa == pytest.approx(12.5 * kb)
    assert r.m_cva == 1.0 and r.r_hedging_disallowance == 0.01


def test_sacva_ir_inflation_and_other_currency() -> None:
    sens = [
        _s(RC.INTEREST_RATE, "EUR", "10Y", s_cva=100.0),
        _s(RC.INTEREST_RATE, "EUR", "INFLATION_10Y", s_cva=100.0),
    ]
    a, b = 0.0074 * 100, 0.0111 * 100
    exp = math.sqrt(a * a + b * b + 2 * 0.40 * a * b)
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(exp)
    other = [_s(RC.INTEREST_RATE, "BRL", "PARALLEL", s_cva=100.0)]
    assert EUPillar1().sa_cva(other).k_total == pytest.approx(1.58)
    # reporting currency is a specified currency (Art. 383c(2))
    pln = [_s(RC.INTEREST_RATE, "PLN", "1Y", s_cva=100.0)]
    assert EUPillar1(reporting_currency="PLN").sa_cva(pln).k_total == pytest.approx(1.11)


def test_sacva_ir_cross_bucket() -> None:
    sens = [
        _s(RC.INTEREST_RATE, "EUR", "5Y", s_cva=100.0),
        _s(RC.INTEREST_RATE, "USD", "5Y", s_cva=-50.0),
    ]
    a, b = 0.74, -0.37
    exp = math.sqrt(a * a + b * b + 2 * 0.5 * a * b)
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(exp)


def test_sacva_fx_erm2_and_cross() -> None:
    sens = [_s(RC.FX, "USD", s_cva=100.0), _s(RC.FX, "DKK", s_cva=100.0, eu_erm2_currency=True)]
    a, b = 11.0, 11.0 / 3
    exp = math.sqrt(a * a + b * b + 2 * 0.6 * a * b)
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(exp)
    assert EUPillar1(erm2_currencies=["DKK"]).sa_cva(
        [_s(RC.FX, "DKK", s_cva=100.0)]
    ).k_total == pytest.approx(11.0 / 3)


def test_sacva_ccs_intra_bucket_names() -> None:
    unrelated = [
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "4", "5Y", s_cva=100.0, name="A"),
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "4", "5Y", s_cva=100.0, name="B"),
    ]
    exp = math.sqrt(2 * 25.0 + 2 * 0.5 * 25.0)
    assert EUPillar1().sa_cva(unrelated).k_total == pytest.approx(exp)
    related = [
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "4", "5Y", s_cva=100.0, name="A", **{"group:G": True}),
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "4", "1Y", s_cva=100.0, name="B", **{"group:G": True}),
    ]
    exp2 = math.sqrt(2 * 25.0 + 2 * 0.9 * 0.9 * 25.0)
    assert EUPillar1().sa_cva(related).k_total == pytest.approx(exp2)


def test_sacva_ccs_index_series_and_bucket10() -> None:
    idx = [
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "12", "5Y", s_cva=100.0, name="ITRX",
           **{"series:41": True}),
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "12", "5Y", s_cva=100.0, name="ITRX",
           **{"series:40": True}),
    ]  # fmt: skip
    a = 1.5
    assert EUPillar1().sa_cva(idx).k_total == pytest.approx(math.sqrt(2 * a * a + 2 * 0.9 * a * a))
    cb = [_s(RC.COUNTERPARTY_CREDIT_SPREAD, "10", "5Y", s_cva=100.0, name="X", eu_cqs1=True)]
    assert EUPillar1().sa_cva(cb).k_total == pytest.approx(1.5)
    cb2 = [_s(RC.COUNTERPARTY_CREDIT_SPREAD, "10", "5Y", s_cva=100.0, name="X")]
    assert EUPillar1().sa_cva(cb2).k_total == pytest.approx(2.5)


def test_sacva_ccs_cross_bucket_and_no_vega() -> None:
    sens = [
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "4", "5Y", s_cva=100.0, name="A"),  # FIN IG 5 %
        _s(RC.COUNTERPARTY_CREDIT_SPREAD, "9", "5Y", s_cva=100.0, name="B"),  # MS CB 1 %
    ]
    exp = math.sqrt(25 + 1 + 2 * 0.20 * 5 * 1)
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(exp)
    with pytest.raises(ValueError):
        EUPillar1().sa_cva([_s(RC.COUNTERPARTY_CREDIT_SPREAD, "4", "5Y", 1.0, measure="VEGA")])


def test_sacva_rcs_ig_hy_halving() -> None:
    sens = [
        _s(RC.REFERENCE_CREDIT_SPREAD, "4", s_cva=100.0),  # FIN IG 5 %
        _s(RC.REFERENCE_CREDIT_SPREAD, "14", s_cva=100.0),  # FIN HY 12 %
    ]
    exp = math.sqrt(25 + 144 + 2 * (1.0 / 2) * 5 * 12)
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(exp)
    sov_rgla = [
        _s(RC.REFERENCE_CREDIT_SPREAD, "1", s_cva=100.0),  # MS sov 0,5 %
        _s(RC.REFERENCE_CREDIT_SPREAD, "13", s_cva=100.0),  # RGLA HY 4 %
    ]
    exp2 = math.sqrt(0.25 + 16 + 2 * (0.75 / 2) * 0.5 * 4)
    assert EUPillar1().sa_cva(sov_rgla).k_total == pytest.approx(exp2)


def test_sacva_rcs_single_net_per_bucket() -> None:
    sens = [
        _s(RC.REFERENCE_CREDIT_SPREAD, "5", "A", s_cva=100.0),
        _s(RC.REFERENCE_CREDIT_SPREAD, "5", "B", s_cva=-40.0),
    ]
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(0.03 * 60)


def test_sacva_equity_and_commodity() -> None:
    eq = [_s(RC.EQUITY, "12", s_cva=10.0), _s(RC.EQUITY, "13", s_cva=10.0)]
    a, b = 1.5, 2.5
    exp = math.sqrt(a * a + b * b + 2 * 0.75 * a * b)
    assert EUPillar1().sa_cva(eq).k_total == pytest.approx(exp)
    eq_v = [_s(RC.EQUITY, "12", s_cva=10.0, measure="VEGA"), _s(RC.EQUITY, "9", s_cva=10.0,
            measure="VEGA")]  # fmt: skip
    a, b = 7.8, 10.0
    assert EUPillar1().sa_cva(eq_v).k_by_class["EQUITY_VEGA"] == pytest.approx(
        math.sqrt(a * a + b * b + 2 * 0.45 * a * b)
    )
    com = [_s(RC.COMMODITY, "4", s_cva=10.0), _s(RC.COMMODITY, "13", s_cva=10.0)]
    assert EUPillar1().sa_cva(com).k_total == pytest.approx(math.sqrt(16 + 25))
    com2 = [_s(RC.COMMODITY, "4", s_cva=10.0), _s(RC.COMMODITY, "5", s_cva=10.0)]
    assert EUPillar1().sa_cva(com2).k_total == pytest.approx(math.sqrt(16 + 36 + 2 * 0.2 * 24))


def test_sacva_sb_bounded_and_hedge_disallowance() -> None:
    # perfect hedge in one bucket: WS = 0, K_b = sqrt(R) x WS_hedge
    sens = [_s(RC.FX, "USD", s_cva=100.0, s_hedge=100.0)]
    assert EUPillar1().sa_cva(sens).k_total == pytest.approx(math.sqrt(0.01) * 11.0)
    kb, sb = cva_mod.bucket_capital([3.0, -4.0], [0.0, 0.0], [[1.0, 0.0], [0.0, 1.0]])
    assert kb == pytest.approx(5.0) and sb == pytest.approx(-1.0)


def test_sacva_total_and_mcva() -> None:
    sens = [_s(RC.FX, "USD", s_cva=100.0), _s(RC.EQUITY, "5", s_cva=10.0),
            _s(RC.FX, "USD", s_cva=10.0, measure="VEGA")]  # fmt: skip
    r = EUPillar1().sa_cva(sens)
    assert r.k_total == pytest.approx(11.0 + 3.0 + 10.0)
    assert set(r.k_by_class) == {"FX_DELTA", "EQUITY_DELTA", "FX_VEGA"}
    assert EUPillar1(m_cva=1.5).sa_cva(sens).k_total == pytest.approx(1.5 * 24.0)
    with pytest.raises(ValueError):
        EUPillar1(m_cva=0.8).sa_cva(sens)


# =========================================================================
#  Leverage -- Articles 429-429g
# =========================================================================


def _lev(**kw: object) -> LeverageInputs:
    base: dict[str, object] = {
        "on_balance_sheet_assets": 1000.0,
        "tier1_deductions": 10.0,
        "derivative_rc": 20.0,
        "derivative_cash_vm_received": 5.0,
        "derivative_pfe_addon": 30.0,
        "written_credit_derivative_notional": 50.0,
        "written_credit_derivative_offsets": 20.0,
        "sft_gross_assets": 100.0,
        "sft_netted_cash_payables": 10.0,
        "sft_ccr_addon": 5.0,
        "obs_notional_by_ccf": {0.4: 100.0, 0.0: 50.0, 0.1: 20.0},
        "central_bank_reserves": 40.0,
        "client_cleared_trade_exposures_exempt": 3.0,
    }
    base.update(kw)
    return LeverageInputs(**base)  # type: ignore[arg-type]


def test_leverage_aggregation() -> None:
    r = EUPillar1().leverage_exposure(_lev())
    assert r.on_balance_sheet == pytest.approx(990.0)
    assert r.derivatives == pytest.approx(1.4 * (15.0 + 30.0) + 30.0)
    assert r.sfts == pytest.approx(95.0)
    assert r.off_balance_sheet == pytest.approx(40.0 + 5.0 + 2.0)  # UCC 0 % -> 10 % (429f(3))
    assert r.exclusions == pytest.approx(3.0)  # reserves NOT excluded without 429a(5)
    assert r.total_exposure == pytest.approx(990 + 93 + 95 + 47 - 3)


def test_leverage_central_bank_exclusion_and_flags() -> None:
    r = EUPillar1().leverage_exposure(
        _lev(flags={"eu_429a_5_exceptional_circumstances": True, "eu_rc_net_of_vm": True,
                    "eu_429a_4_condition_failed": True})
    )  # fmt: skip
    assert r.exclusions == pytest.approx(40.0)
    assert r.derivatives == pytest.approx(1.4 * 50.0 + 30.0)
    assert lev_mod.adjusted_leverage_requirement(1000.0, 200.0) == pytest.approx(0.03 * 1.25)
    assert lev_mod.leverage_ratio(50.0, 1000.0) == pytest.approx(0.05)
    assert lev_mod.leverage_requirement(0.02) == pytest.approx(0.04)


# =========================================================================
#  Large exposures -- Articles 392-400
# =========================================================================


def _le(cid: str, v: float, **kw: object) -> LargeExposureInput:
    return LargeExposureInput(counterparty_id=cid, exposure_value=v, **kw)  # type: ignore[arg-type]


def test_le_limit_and_breach_edges() -> None:
    rows = EUPillar1().large_exposures(
        [_le("a", 250.0), _le("b", 250.01), _le("c", 100.0), _le("d", 99.0)], 1000.0, False
    )
    assert [r.breach for r in rows] == [False, True, False, False]
    assert rows[0].limit == pytest.approx(250.0) and rows[0].limit_pct_of_tier1 == 0.25
    assert [r.reportable for r in rows] == [True, True, True, False]  # 10 % edge inclusive


def test_le_reporting_eur_300m() -> None:
    rows = EUPillar1().large_exposures([_le("x", 300.0), _le("y", 299.0)], 5000.0, False)
    assert [r.reportable for r in rows] == [True, False]
    rows_fx = EUPillar1(reporting_ccy_per_eur=1.1).large_exposures([_le("x", 300.0)], 5000.0, False)
    assert rows_fx[0].reportable is False  # EUR 300m = 330 in reporting currency


def test_le_institution_eur_150m() -> None:
    bank = {"counterparty_asset_class": AssetClass.BANK}
    small = EUPillar1().large_exposures([_le("b", 140.0, **bank)], 400.0, False)[0]
    assert small.limit == pytest.approx(150.0) and not small.breach
    tiny = EUPillar1().large_exposures([_le("b", 140.0, **bank)], 100.0, False)[0]
    assert tiny.limit == pytest.approx(100.0) and tiny.breach  # 100 % of Tier 1 ceiling
    big = EUPillar1().large_exposures([_le("b", 260.0, **bank)], 1000.0, False)[0]
    assert big.limit == pytest.approx(250.0) and big.breach
    lower = EUPillar1(le_institution_floor_eur_m=100.0).large_exposures(
        [_le("b", 140.0, **bank)], 400.0, False
    )[0]
    assert lower.limit == pytest.approx(100.0)


def test_le_gsii_and_exemptions() -> None:
    g = _le("g", 160.0, counterparty_is_gsib=True)
    assert EUPillar1().large_exposures([g], 1000.0, True)[0].breach
    assert not EUPillar1().large_exposures([g], 1000.0, False)[0].breach
    ex = EUPillar1().large_exposures(
        [_le("s", 900.0, flags={"eu_400_1_a": True}), _le("q", 900.0, is_exempt=True)],
        1000.0,
        False,
    )
    assert all(not r.breach and r.reportable for r in ex)
    assert "400(1)(a)" in ex[0].citation


def test_le_helpers() -> None:
    assert le_mod.mortgage_reduction(100.0, 80.0, 100.0, True, 0.20) == pytest.approx(45.0)
    assert le_mod.mortgage_reduction(100.0, 80.0, 100.0, True, 0.25) == pytest.approx(100.0)
    assert le_mod.mortgage_reduction(100.0, 30.0, 100.0, False, 0.60) == pytest.approx(70.0)
    assert le_mod.partial_exemption_400_2_i(100.0, "MUTUAL_GUARANTEE_SCHEME") == pytest.approx(20)
    assert le_mod.trading_book_excess_factor(0.5, False) == 2.0
    assert le_mod.trading_book_excess_factor(0.5, True) == 3.0
    assert le_mod.trading_book_excess_factor(3.0, True) == 9.0
    assert le_mod.trading_book_excess_permitted(5.0, 0.0, True)
    assert not le_mod.trading_book_excess_permitted(0.0, 6.1, False)


# =========================================================================
#  CCPs -- Articles 300-311
# =========================================================================


def test_ccp_qccp_trade_and_kcm() -> None:
    x = CCPExposureInput(ccp_id="c", trade_exposure=100.0, default_fund_contribution=10.0,
                         k_ccp=50.0, total_default_fund=500.0)  # fmt: skip
    r = EUPillar1().ccp_exposure(x)
    assert r.trade_rw == 0.02 and r.trade_rwa == pytest.approx(2.0)
    # K_i = max(50 x 10/500; 0,08 x 0,02 x 10) = 1 -> RWEA 12,5 (Art. 308)
    assert r.default_fund_rwa == pytest.approx(12.5)
    assert r.total_rwa == pytest.approx(14.5)
    assert ccp_mod.k_cm_prefunded(10.0, 0.1, 500.0) == pytest.approx(0.08 * 0.02 * 10.0)


def test_ccp_client_variants() -> None:
    base = {"ccp_id": "c", "trade_exposure": 100.0, "is_client_cleared_via_member": True}
    assert EUPillar1().ccp_exposure(CCPExposureInput(**base)).trade_rwa == pytest.approx(2.0)
    j = CCPExposureInput(**base, flags={"eu_305_3_joint_default": True})
    assert EUPillar1().ccp_exposure(j).trade_rwa == pytest.approx(4.0)
    nr = CCPExposureInput(**base, flags={"eu_306_1_c_no_reimbursement": True})
    assert EUPillar1().ccp_exposure(nr).trade_rwa == 0.0
    ns = CCPExposureInput(**base, flags={"eu_305_2_not_met": True})
    assert EUPillar1().ccp_exposure(ns).trade_rw == pytest.approx(1.50)


def test_ccp_non_qualifying_and_ceasing() -> None:
    x = CCPExposureInput(ccp_id="n", is_qualifying=False, trade_exposure=100.0,
                         default_fund_contribution=10.0,
                         ccp_rating=RatingBucket.A_PLUS_TO_A_MINUS)  # fmt: skip
    r = EUPillar1().ccp_exposure(x)
    assert r.trade_rw == pytest.approx(0.50)  # Art. 122 Table 1 CQS 2
    assert r.default_fund_rwa == pytest.approx(125.0)  # Art. 309: K = DF, x 12,5
    c = CCPExposureInput(ccp_id="q", trade_exposure=100.0, flags={"eu_311_ceasing": True})
    assert EUPillar1().ccp_exposure(c).trade_rw == pytest.approx(1.00)  # unrated corporate


def test_ccp_cap_303_2_and_fallbacks() -> None:
    x = CCPExposureInput(ccp_id="c", trade_exposure=100.0, default_fund_contribution=10.0,
                         k_ccp=10_000.0, total_default_fund=500.0)  # fmt: skip
    r = EUPillar1().ccp_exposure(x)
    # K_i = 200 -> 2 500 + 2 > cap 100 % x 100 + 12,5 x 10 = 225
    assert r.total_rwa == pytest.approx(225.0)
    miss = CCPExposureInput(ccp_id="c", trade_exposure=0.0, default_fund_contribution=10.0)
    assert EUPillar1().ccp_exposure(miss).default_fund_rwa == pytest.approx(125.0)
    cash = CCPExposureInput(ccp_id="c", trade_exposure=0.0, default_fund_contribution=10.0,
                            flags={"eu_df_cash_only": True})  # fmt: skip
    assert EUPillar1().ccp_exposure(cash).default_fund_rwa == 0.0
