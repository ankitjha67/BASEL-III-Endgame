"""Tests for the EU CRR3 package (Regulation (EU) 2024/1623 amending Regulation (EU) No 575/2013).

Every transcribed table cell is asserted (parametrized), formulas are checked
against hand-computed worked examples, and the CRR3 transitional schedules
(output floor, equity, UCC, Article 465 S-TREA weights) are exercised by year.
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    Jurisdiction,
    OBSCategory,
    OpRiskInputs,
    PFPhase,
    RatingBucket,
    RegimeCalculator,
    SACCRNettingSetInput,
    SAExposure,
    SCRAGrade,
    ShortTermRating,
    rating_bucket_from_cqs,
)
from src.jurisdictions.eu import (
    EURegime,
    capital_stack,
    credit_risk,
    cva,
    operational_risk,
    output_floor,
    saccr,
)
from src.jurisdictions.eu import params as prm

CQS = [1, 2, 3, 4, 5, 6]


def _x(ac: AssetClass, **kw: object) -> SAExposure:
    """Build an exposure with 100 drawn unless overridden."""
    kw.setdefault("on_balance_amount", 100.0)
    return SAExposure(exposure_id="t", asset_class=ac, **kw)  # type: ignore[arg-type]


def _rw(e: SAExposure, year: int = 2026) -> float:
    return EURegime(year=year).risk_weight(e).risk_weight


# =========================================================================
#  Protocol conformance
# =========================================================================


def test_protocol_conformance() -> None:
    reg = EURegime()
    assert isinstance(reg, RegimeCalculator)
    assert reg.jurisdiction == Jurisdiction.EU
    assert "2024/1623" in reg.legal_basis


def test_every_asset_class_returns_a_result() -> None:
    reg = EURegime()
    for ac in AssetClass:
        r = reg.risk_weight(_x(ac))
        assert r.jurisdiction == Jurisdiction.EU
        assert r.risk_weight >= 0.0
        assert r.citation


# =========================================================================
#  Sovereigns, RGLA, PSE, MDB -- Articles 114-118
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.0, 0.20, 0.50, 1.00, 1.00, 1.50], strict=True))
)
def test_sovereign_table_1(cqs: int, expected: float) -> None:
    assert _rw(_x(AssetClass.SOVEREIGN, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(
        expected
    )


def test_sovereign_special_cases() -> None:
    assert _rw(_x(AssetClass.SOVEREIGN)) == 1.00  # 114(1)
    assert _rw(_x(AssetClass.SOVEREIGN, flags={"eu_ecb": True})) == 0.0
    ms = _x(
        AssetClass.SOVEREIGN,
        rating=rating_bucket_from_cqs(4),
        domestic_currency_funded=True,
        flags={"eu_member_state": True},
    )
    assert _rw(ms) == 0.0  # 114(4)
    assert _rw(_x(AssetClass.SOVEREIGN, flags={"eu_international_org": True})) == 0.0  # 118


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.50, 0.50, 1.00, 1.00, 1.50], strict=True))
)
def test_rgla_rated_table_1(cqs: int, expected: float) -> None:
    e = _x(AssetClass.PSE, rating=rating_bucket_from_cqs(cqs), flags={"eu_rgla": True})
    assert _rw(e) == pytest.approx(expected)


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.50, 1.00, 1.00, 1.00, 1.50], strict=True))
)
def test_rgla_unrated_table_2(cqs: int, expected: float) -> None:
    e = _x(AssetClass.PSE, sovereign_rating=rating_bucket_from_cqs(cqs), flags={"eu_rgla": True})
    assert _rw(e) == pytest.approx(expected)


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.50, 1.00, 1.00, 1.00, 1.50], strict=True))
)
def test_pse_unrated_table_2(cqs: int, expected: float) -> None:
    assert _rw(_x(AssetClass.PSE, sovereign_rating=rating_bucket_from_cqs(cqs))) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.50, 0.50, 1.00, 1.00, 1.50], strict=True))
)
def test_pse_rated_via_115_minus_1(cqs: int, expected: float) -> None:
    assert _rw(_x(AssetClass.PSE, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(expected)


def test_pse_and_rgla_special_cases() -> None:
    assert _rw(_x(AssetClass.PSE)) == 1.00  # sovereign unrated
    assert _rw(_x(AssetClass.PSE, original_maturity_months=3)) == 0.20  # 116(3)
    assert _rw(_x(AssetClass.PSE, original_maturity_months=3.5)) == 1.00
    rgla_ms = _x(
        AssetClass.PSE,
        domestic_currency_funded=True,
        flags={"eu_rgla": True, "eu_member_state": True},
    )
    assert _rw(rgla_ms) == 0.20  # 115(5)
    as_sov = _x(
        AssetClass.PSE,
        sovereign_rating=rating_bucket_from_cqs(2),
        flags={"eu_treated_as_sovereign": True},
    )
    assert _rw(as_sov) == 0.20


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.30, 0.50, 1.00, 1.00, 1.50], strict=True))
)
def test_mdb_table_1(cqs: int, expected: float) -> None:
    assert _rw(_x(AssetClass.MDB, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(expected)


def test_mdb_unrated_and_listed() -> None:
    assert _rw(_x(AssetClass.MDB)) == 0.50
    assert _rw(_x(AssetClass.MDB, flags={"eu_mdb_listed": True})) == 0.0


# =========================================================================
#  Institutions -- Articles 120, 121, 131
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.30, 0.50, 1.00, 1.00, 1.50], strict=True))
)
def test_institution_rated_table_1(cqs: int, expected: float) -> None:
    assert _rw(_x(AssetClass.BANK, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(expected)


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.20, 0.20, 0.50, 0.50, 1.50], strict=True))
)
def test_institution_rated_short_term_table_2(cqs: int, expected: float) -> None:
    e = _x(AssetClass.BANK, rating=rating_bucket_from_cqs(cqs), original_maturity_months=3)
    assert _rw(e) == pytest.approx(expected)


def test_institution_trade_short_term_cutoff() -> None:
    base = {"rating": rating_bucket_from_cqs(2), "is_trade_related": True}
    assert _rw(_x(AssetClass.BANK, original_maturity_months=6, **base)) == 0.20
    assert _rw(_x(AssetClass.BANK, original_maturity_months=6.5, **base)) == 0.30


@pytest.mark.parametrize(
    "grade,long_rw,short_rw", [("A", 0.40, 0.20), ("B", 0.75, 0.50), ("C", 1.50, 1.50)]
)
def test_scra_table_1(grade: str, long_rw: float, short_rw: float) -> None:
    g = SCRAGrade(grade)
    assert _rw(_x(AssetClass.BANK, scra_grade=g)) == pytest.approx(long_rw)
    assert _rw(_x(AssetClass.BANK, scra_grade=g, original_maturity_months=2)) == pytest.approx(
        short_rw
    )


def test_scra_enhanced_grade_a_and_default_grade_c() -> None:
    assert _rw(_x(AssetClass.BANK, scra_grade=SCRAGrade.A, scra_grade_a_enhanced=True)) == 0.30
    # enhanced 30 % does not apply to short-term exposures (121(3)(b)(i))
    st = _x(
        AssetClass.BANK,
        scra_grade=SCRAGrade.A,
        scra_grade_a_enhanced=True,
        original_maturity_months=3,
    )
    assert _rw(st) == 0.20
    assert _rw(_x(AssetClass.BANK)) == 1.50  # 121(1)(c): not A or B -> C


def test_scra_sovereign_floor_for_foreign_currency() -> None:
    e = _x(
        AssetClass.BANK,
        scra_grade=SCRAGrade.A,
        sovereign_rating=rating_bucket_from_cqs(4),
        flags={"eu_not_domestic_currency": True},
    )
    assert _rw(e) == 1.00
    trade = e.model_copy(update={"is_trade_related": True, "original_maturity_months": 9})
    assert _rw(trade) == 0.40  # self-liquidating trade <= 1 year exempt


@pytest.mark.parametrize(
    "st,expected",
    [
        (ShortTermRating.A1_P1, 0.20),
        (ShortTermRating.A2_P2, 0.50),
        (ShortTermRating.A3_P3, 1.00),
        (ShortTermRating.OTHERS, 1.50),
    ],
)
def test_short_term_assessment_table_7(st: ShortTermRating, expected: float) -> None:
    e = _x(AssetClass.CORPORATE, short_term_rating=st)
    assert _rw(e) == pytest.approx(expected)
    b = _x(
        AssetClass.BANK,
        short_term_rating=st,
        rating=rating_bucket_from_cqs(1),
        original_maturity_months=2,
    )
    assert _rw(b) == pytest.approx(expected)


@pytest.mark.parametrize(
    "cqs,val", list(zip(CQS, [0.20, 0.50, 1.00, 1.50, 1.50, 1.50], strict=True))
)
def test_table_7_params(cqs: int, val: float) -> None:
    assert prm.SHORT_TERM_ASSESSMENT_RW_BY_CQS[cqs] == val


# =========================================================================
#  Covered bonds -- Article 129(4)-(5)
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.10, 0.20, 0.20, 0.50, 0.50, 1.00], strict=True))
)
def test_covered_bond_rated_table_1(cqs: int, expected: float) -> None:
    e = _x(AssetClass.COVERED_BOND, rating=rating_bucket_from_cqs(cqs), covered_bond_rated=True)
    assert _rw(e) == pytest.approx(expected)


@pytest.mark.parametrize(
    "issuer,expected",
    [
        (0.20, 0.10),
        (0.30, 0.15),
        (0.40, 0.20),
        (0.50, 0.25),
        (0.75, 0.35),
        (1.00, 0.50),
        (1.50, 1.00),
    ],
)
def test_covered_bond_issuer_mapping_129_5(issuer: float, expected: float) -> None:
    assert prm.COVERED_BOND_RW_FROM_ISSUER_RW[issuer] == expected


@pytest.mark.parametrize(
    "kw,expected",
    [
        ({"rating": rating_bucket_from_cqs(1)}, 0.10),
        ({"rating": rating_bucket_from_cqs(2)}, 0.15),
        ({"scra_grade": SCRAGrade.A}, 0.20),
        ({"scra_grade": SCRAGrade.B}, 0.35),
        ({"scra_grade": SCRAGrade.C}, 1.00),
        ({"scra_grade": SCRAGrade.A, "scra_grade_a_enhanced": True}, 0.15),
    ],
)
def test_covered_bond_unrated_from_issuer(kw: dict[str, object], expected: float) -> None:
    assert _rw(_x(AssetClass.COVERED_BOND, **kw)) == pytest.approx(expected)


# =========================================================================
#  Corporates and specialised lending -- Articles 122, 122a, 495b(3)
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.50, 0.75, 1.00, 1.50, 1.50], strict=True))
)
def test_corporate_table_1(cqs: int, expected: float) -> None:
    assert _rw(_x(AssetClass.CORPORATE, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(
        expected
    )


def test_corporate_unrated_100_no_sovereign_floor() -> None:
    e = _x(AssetClass.CORPORATE, sovereign_rating=rating_bucket_from_cqs(6))
    assert _rw(e) == 1.00  # CRR3 122(2) removed the sovereign floor
    assert (
        _rw(_x(AssetClass.CORPORATE, is_investment_grade=True)) == 1.00
    )  # no IG option outside floor


def test_no_85pct_sme_weight_but_supporting_factor() -> None:
    e = _x(AssetClass.CORPORATE_SME, is_sme=True, on_balance_amount=2.0)
    r = EURegime().risk_weight(e)
    assert r.rwa == pytest.approx(2.0 * 1.00 * 0.7619)


@pytest.mark.parametrize(
    "cqs,expected", list(zip(CQS, [0.20, 0.50, 0.75, 1.00, 1.50, 1.50], strict=True))
)
def test_specialised_lending_rated_table_1(cqs: int, expected: float) -> None:
    e = _x(AssetClass.SPECIALISED_LENDING_PF, rating=rating_bucket_from_cqs(cqs))
    assert _rw(e) == pytest.approx(expected)


@pytest.mark.parametrize(
    "phase,expected",
    [
        (PFPhase.PRE_OPERATIONAL, 1.30),
        (PFPhase.OPERATIONAL, 1.00),
        (PFPhase.HIGH_QUALITY_OPERATIONAL, 0.80),
        (None, 1.30),
    ],
)
def test_project_finance_phases(phase: PFPhase | None, expected: float) -> None:
    assert _rw(_x(AssetClass.SPECIALISED_LENDING_PF, pf_phase=phase)) == pytest.approx(expected)


def test_pf_high_quality_not_with_501a() -> None:
    e = _x(
        AssetClass.SPECIALISED_LENDING_PF,
        pf_phase=PFPhase.HIGH_QUALITY_OPERATIONAL,
        flags={"eu_infrastructure_501a": True},
    )
    r = EURegime().risk_weight(e)
    assert r.rwa == pytest.approx(100 * 1.00 * 0.75)


def test_object_and_commodities_finance() -> None:
    assert _rw(_x(AssetClass.SPECIALISED_LENDING_OF)) == 1.00
    assert _rw(_x(AssetClass.SPECIALISED_LENDING_CF)) == 1.00
    hq = _x(AssetClass.SPECIALISED_LENDING_OF, flags={"eu_object_finance_high_quality": True})
    assert _rw(hq, 2032) == 0.80
    assert _rw(hq, 2033) == 1.00  # 495b(3) ends 31 Dec 2032


# =========================================================================
#  Subordinated debt and equity -- Articles 128, 133, 48(4), 495a
# =========================================================================


def test_subordinated_debt() -> None:
    assert _rw(_x(AssetClass.SUBORDINATED_DEBT)) == 1.50


@pytest.mark.parametrize(
    "year,general,spec",
    [
        (2025, 1.00, 1.50),
        (2026, 1.30, 1.60),
        (2027, 1.60, 2.20),
        (2028, 1.90, 2.80),
        (2029, 2.20, 3.40),
        (2030, 2.50, 4.00),
        (2035, 2.50, 4.00),
    ],
)
def test_equity_phase_in_495a(year: int, general: float, spec: float) -> None:
    g = _x(AssetClass.EQUITY, equity_type=EquityType.GENERAL)
    s = _x(AssetClass.EQUITY, equity_type=EquityType.SPECULATIVE_UNLISTED)
    assert _rw(g, year) == pytest.approx(general)
    # 2025 speculative: max(legacy 150 %, 100 %) = 150 %
    assert _rw(s, year) == pytest.approx(spec)


@pytest.mark.parametrize(
    "year,val", [(2025, 1.00), (2026, 1.30), (2027, 1.60), (2028, 1.90), (2029, 2.20)]
)
def test_equity_general_schedule_params(year: int, val: float) -> None:
    assert prm.EQUITY_PHASE_IN_GENERAL[year] == val


@pytest.mark.parametrize(
    "year,val", [(2025, 1.00), (2026, 1.60), (2027, 2.20), (2028, 2.80), (2029, 3.40)]
)
def test_equity_speculative_schedule_params(year: int, val: float) -> None:
    assert prm.EQUITY_PHASE_IN_SPECULATIVE[year] == val


def test_equity_other_categories() -> None:
    assert _rw(_x(AssetClass.EQUITY, equity_type=EquityType.LEGISLATIVE_PROGRAMME)) == 1.00
    assert _rw(_x(AssetClass.EQUITY, equity_type=EquityType.SIGNIFICANT_FI)) == 2.50
    assert _rw(_x(AssetClass.EQUITY, flags={"eu_equity_central_bank": True})) == 0.0
    assert _rw(_x(AssetClass.EQUITY, equity_type=EquityType.PUBLICLY_TRADED), 2030) == 2.50
    lt = _x(
        AssetClass.EQUITY,
        equity_type=EquityType.SPECULATIVE_UNLISTED,
        flags={"eu_long_term_equity": True},
    )
    assert _rw(lt, 2030) == 2.50  # 133(4) second subparagraph
    gf = _x(AssetClass.EQUITY, flags={"eu_equity_grandfathered_495a3": True})
    assert _rw(gf, 2031) == 1.00


# =========================================================================
#  Retail -- Articles 123, 123a
# =========================================================================


def test_retail_weights() -> None:
    assert _rw(_x(AssetClass.RETAIL_REGULATORY)) == 0.75
    assert _rw(_x(AssetClass.RETAIL_TRANSACTOR)) == 0.45
    assert _rw(_x(AssetClass.RETAIL_OTHER)) == 1.00
    assert _rw(_x(AssetClass.RETAIL_REGULATORY, meets_regulatory_retail_criteria=False)) == 1.00
    assert _rw(_x(AssetClass.RETAIL_REGULATORY, flags={"eu_payroll_pension_loan": True})) == 0.35


def test_retail_eur_1m_boundary() -> None:
    assert _rw(_x(AssetClass.RETAIL_REGULATORY, aggregate_retail_exposure_to_obligor=1.0)) == 0.75
    assert _rw(_x(AssetClass.RETAIL_REGULATORY, aggregate_retail_exposure_to_obligor=1.01)) == 1.00


def test_currency_mismatch_multiplier() -> None:
    e = _x(AssetClass.RETAIL_REGULATORY, currency_matches_borrower_income=False)
    assert _rw(e) == pytest.approx(0.75 * 1.5)
    other = _x(AssetClass.RETAIL_OTHER, currency_matches_borrower_income=False)
    assert _rw(other) == pytest.approx(1.50)  # 100 % x 1,5 = 150 % cap
    erm2 = e.model_copy(update={"flags": {"eu_erm2_pair": True}})
    assert _rw(erm2) == 0.75
    corp = _x(AssetClass.CORPORATE, currency_matches_borrower_income=False)
    assert _rw(corp) == 1.00  # natural persons only


# =========================================================================
#  Real estate -- Articles 124-126a, 127(3)
# =========================================================================


@pytest.mark.parametrize(
    "ltv,expected_rwa",
    [
        (0.50, 100 * 0.20),  # entirely within 55 %
        (0.55, 100 * 0.20),  # boundary: 55 % of value = whole loan
        (0.80, 55 / 0.80 * 0.20 + (100 - 55 / 0.80) * 0.75),
        (1.00, 55 * 0.20 + 45 * 0.75),
    ],
)
def test_rre_loan_splitting_125_1(ltv: float, expected_rwa: float) -> None:
    r = EURegime().risk_weight(_x(AssetClass.RESIDENTIAL_RE, ltv=ltv))
    assert r.rwa == pytest.approx(expected_rwa)


def test_rre_loan_splitting_with_property_value_and_corporate_counterparty() -> None:
    e = _x(
        AssetClass.RESIDENTIAL_RE,
        property_value=100.0,
        flags={"eu_re_counterparty_corporate": True},
    )
    assert EURegime().risk_weight(e).rwa == pytest.approx(55 * 0.20 + 45 * 1.00)


@pytest.mark.parametrize(
    "etv,expected",
    [
        (0.40, 0.30),
        (0.50, 0.30),
        (0.5001, 0.35),
        (0.60, 0.35),
        (0.70, 0.45),
        (0.80, 0.45),
        (0.85, 0.60),
        (0.90, 0.60),
        (0.95, 0.75),
        (1.00, 0.75),
        (1.01, 1.05),
    ],
)
def test_rre_ipre_table_1(etv: float, expected: float) -> None:
    e = _x(AssetClass.RESIDENTIAL_RE, ltv=etv, is_cash_flow_dependent=True, is_owner_occupied=False)
    assert _rw(e) == pytest.approx(expected)


def test_rre_ipre_routes_to_loan_splitting() -> None:
    e = _x(
        AssetClass.RESIDENTIAL_RE,
        ltv=0.5,
        is_cash_flow_dependent=True,
        is_owner_occupied=False,
        flags={"eu_ipre_qualifying_natural_person": True},
    )
    assert _rw(e) == pytest.approx(0.20)
    hard = e.model_copy(update={"flags": {"eu_ipre_hard_test_met": True}})
    assert _rw(hard) == pytest.approx(0.20)


@pytest.mark.parametrize(
    "etv,expected", [(0.50, 0.70), (0.60, 0.70), (0.61, 0.90), (0.80, 0.90), (0.81, 1.10)]
)
def test_cre_ipre_table_1(etv: float, expected: float) -> None:
    assert _rw(_x(AssetClass.COMMERCIAL_RE, ltv=etv, is_cash_flow_dependent=True)) == pytest.approx(
        expected
    )


def test_cre_loan_splitting_126_1() -> None:
    r = EURegime().risk_weight(_x(AssetClass.COMMERCIAL_RE, ltv=1.0))
    assert r.rwa == pytest.approx(55 * 0.60 + 45 * 1.00)
    small = EURegime().risk_weight(_x(AssetClass.COMMERCIAL_RE, ltv=0.4))
    assert small.risk_weight == pytest.approx(0.60)  # flat 60 %, no "lower of" counterparty


def test_junior_lien_multiplier_124_6() -> None:
    flags = {"eu_junior_lien_unknown_ranking": True}
    low = _x(AssetClass.COMMERCIAL_RE, ltv=0.5, is_cash_flow_dependent=True, flags=flags)
    assert _rw(low) == pytest.approx(0.70)  # lowest bucket: not applied
    mid = _x(AssetClass.COMMERCIAL_RE, ltv=0.7, is_cash_flow_dependent=True, flags=flags)
    assert _rw(mid) == pytest.approx(0.90 * 1.25)
    high = _x(AssetClass.COMMERCIAL_RE, ltv=0.9, is_cash_flow_dependent=True, flags=flags)
    assert _rw(high) == pytest.approx(1.10 * 1.25)  # 137,5 % (cap at 150 % not reached)


def test_non_qualifying_real_estate_124_1() -> None:
    ipre = _x(
        AssetClass.COMMERCIAL_RE, is_regulatory_real_estate=False, is_cash_flow_dependent=True
    )
    assert _rw(ipre) == 1.50
    non = _x(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False)
    assert _rw(non) == 0.75  # counterparty (retail natural person)


def test_adc() -> None:
    assert _rw(_x(AssetClass.LAND_ADC)) == 1.50
    assert _rw(_x(AssetClass.LAND_ADC, is_adc_presold_or_equity_at_risk=True)) == 1.00


# =========================================================================
#  Defaulted and other items -- Articles 127, 134
# =========================================================================


@pytest.mark.parametrize("prov,expected", [(0.0, 1.50), (0.1999, 1.50), (0.20, 1.00), (0.5, 1.00)])
def test_defaulted_provision_test(prov: float, expected: float) -> None:
    assert _rw(_x(AssetClass.DEFAULTED, specific_provision_pct=prov)) == pytest.approx(expected)
    assert _rw(
        _x(AssetClass.CORPORATE, is_defaulted=True, specific_provision_pct=prov)
    ) == pytest.approx(expected)


def test_defaulted_non_ipre_re_100() -> None:
    assert _rw(_x(AssetClass.RESIDENTIAL_RE, is_defaulted=True, ltv=0.5)) == 1.00
    ipre = _x(AssetClass.COMMERCIAL_RE, is_defaulted=True, is_cash_flow_dependent=True)
    assert _rw(ipre) == 1.50


def test_other_items() -> None:
    assert _rw(_x(AssetClass.OTHER_ASSETS)) == 1.00
    assert _rw(_x(AssetClass.OTHER_ASSETS, flags={"eu_cash": True})) == 0.0
    assert _rw(_x(AssetClass.OTHER_ASSETS, flags={"eu_cash_in_collection": True})) == 0.20
    assert _rw(_x(AssetClass.OTHER_ASSETS, flags={"eu_gold": True})) == 0.0


# =========================================================================
#  CCFs -- Article 111, Annex I, Article 495d
# =========================================================================


@pytest.mark.parametrize(
    "cat,expected",
    [
        (OBSCategory.DIRECT_CREDIT_SUBSTITUTE, 1.00),
        (OBSCategory.SECURITIES_LENDING_COLLATERAL, 1.00),
        (OBSCategory.FORWARD_ASSET_PURCHASE, 1.00),
        (OBSCategory.OTHER_100, 1.00),
        (OBSCategory.NIF_RUF, 0.50),
        (OBSCategory.TRANSACTION_RELATED_CONTINGENT, 0.50),
        (OBSCategory.COMMITMENT_OTHER, 0.40),
        (OBSCategory.SHORT_TERM_TRADE_LC, 0.20),
        (OBSCategory.UNCONDITIONALLY_CANCELLABLE, 0.0),
    ],
)
def test_ccf_by_category_2026(cat: OBSCategory, expected: float) -> None:
    e = _x(
        AssetClass.CORPORATE, on_balance_amount=0.0, off_balance_notional=100.0, obs_category=cat
    )
    assert EURegime(year=2026).ccf(e) == pytest.approx(expected)


@pytest.mark.parametrize("bucket,pct", [(1, 1.00), (2, 0.50), (3, 0.40), (4, 0.20), (5, 0.10)])
def test_ccf_bucket_params(bucket: int, pct: float) -> None:
    assert prm.CCF_BY_BUCKET[bucket] == pct


@pytest.mark.parametrize(
    "year,expected",
    [
        (2025, 0.0),
        (2029, 0.0),
        (2030, 0.025),
        (2031, 0.05),
        (2032, 0.075),
        (2033, 0.10),
        (2040, 0.10),
    ],
)
def test_ucc_transitional_495d(year: int, expected: float) -> None:
    e = _x(
        AssetClass.CORPORATE,
        on_balance_amount=0.0,
        off_balance_notional=100.0,
        obs_category=OBSCategory.UNCONDITIONALLY_CANCELLABLE,
    )
    assert EURegime(year=year).ccf(e) == pytest.approx(expected)


def test_ccf_trade_finance_and_exemptions() -> None:
    e = _x(
        AssetClass.CORPORATE,
        on_balance_amount=0.0,
        off_balance_notional=10.0,
        obs_category=OBSCategory.TRANSACTION_RELATED_CONTINGENT,
        is_trade_related=True,
    )
    assert EURegime().ccf(e) == 0.20  # Annex I bucket 4(a)(i)
    ex = _x(
        AssetClass.CORPORATE,
        off_balance_notional=10.0,
        obs_category=OBSCategory.COMMITMENT_OTHER,
        flags={"eu_art5_10_exempt": True},
    )
    assert EURegime().ccf(ex) == 0.0
    missing = _x(AssetClass.CORPORATE, off_balance_notional=10.0)
    assert EURegime().ccf(missing) == 1.00  # conservative bucket 1


def test_exposure_amount_with_ccf() -> None:
    e = _x(
        AssetClass.CORPORATE,
        on_balance_amount=60.0,
        off_balance_notional=100.0,
        obs_category=OBSCategory.COMMITMENT_OTHER,
    )
    r = EURegime().risk_weight(e)
    assert r.exposure_amount == pytest.approx(100.0)
    assert r.rwa == pytest.approx(100.0)


# =========================================================================
#  CRM -- Articles 223-224, 235
# =========================================================================


@pytest.mark.parametrize(
    "key,days,expected",
    [
        ("SOV_CQS1_1", 20, 0.00707),
        ("SOV_CQS1_1", 10, 0.005),
        ("SOV_CQS1_1", 5, 0.00354),
        ("SOV_CQS1_2", 10, 0.02),
        ("SOV_CQS1_4", 10, 0.02),
        ("SOV_CQS1_7", 10, 0.04),
        ("SOV_CQS1_15", 10, 0.04),
        ("SOV_CQS2_3_1", 10, 0.01),
        ("SOV_CQS2_3_3", 10, 0.03),
        ("SOV_CQS2_3_5", 10, 0.03),
        ("SOV_CQS2_3_10", 10, 0.06),
        ("SOV_CQS2_3_11", 10, 0.06),
        ("SOV_CQS4", 10, 0.15),
        ("SOV_CQS4", 20, 0.21213),
        ("OTH_CQS1_1", 10, 0.01),
        ("OTH_CQS1_3", 10, 0.03),
        ("OTH_CQS1_5", 10, 0.04),
        ("OTH_CQS1_10", 10, 0.06),
        ("OTH_CQS1_12", 10, 0.12),
        ("OTH_CQS2_3_1", 10, 0.02),
        ("OTH_CQS2_3_2", 10, 0.04),
        ("OTH_CQS2_3_4", 10, 0.06),
        ("OTH_CQS2_3_6", 10, 0.12),
        ("OTH_CQS2_3_20", 10, 0.20),
        ("OTH_CQS2_3_20", 20, 0.28284),
        ("SEC_CQS1_1", 10, 0.02),
        ("SEC_CQS1_3", 10, 0.08),
        ("SEC_CQS1_5", 10, 0.08),
        ("SEC_CQS1_8", 10, 0.16),
        ("SEC_CQS1_30", 10, 0.16),
        ("SEC_CQS2_3_1", 10, 0.04),
        ("SEC_CQS2_3_2", 10, 0.12),
        ("SEC_CQS2_3_5", 10, 0.12),
        ("SEC_CQS2_3_9", 10, 0.24),
        ("SEC_CQS2_3_25", 10, 0.24),
        ("ST_SOV_CQS1", 10, 0.005),
        ("ST_SOV_CQS2_3", 10, 0.01),
        ("ST_OTH_CQS1", 10, 0.01),
        ("ST_OTH_CQS2_3", 10, 0.02),
        ("ST_SEC_CQS1", 10, 0.02),
        ("ST_SEC_CQS2_3", 10, 0.04),
        ("MAIN_INDEX_EQUITY", 10, 0.20),
        ("OTHER_LISTED_EQUITY", 10, 0.30),
        ("CASH", 10, 0.0),
        ("GOLD", 10, 0.20),
        ("MAIN_INDEX_EQUITY", 20, 0.28284),
        ("OTHER_LISTED_EQUITY", 5, 0.21213),
    ],
)
def test_supervisory_haircuts_224(key: str, days: int, expected: float) -> None:
    assert credit_risk.supervisory_haircut(key, days) == pytest.approx(expected)


def test_haircut_fx_and_unknown() -> None:
    assert prm.HAIRCUT_FX == (0.11314, 0.08, 0.05657)
    assert credit_risk.supervisory_haircut("OTH_CQS4", 10) is None
    assert credit_risk.supervisory_haircut("NONSENSE", 10) is None


def test_fccm_worked_example() -> None:
    # E = 100; C = 50 main-index equity, 20-day secured lending Hc = 28,284 %, FX mismatch 11,314 %
    e = _x(
        AssetClass.CORPORATE,
        financial_collateral_value=50.0,
        collateral_haircut_class="MAIN_INDEX_EQUITY",
        flags={"eu_collateral_fx_mismatch": True},
    )
    r = EURegime().risk_weight(e)
    assert r.exposure_amount == pytest.approx(100 - 50 * (1 - 0.28284 - 0.11314))
    repo = e.model_copy(update={"flags": {"eu_repo_style": True}})
    assert EURegime().risk_weight(repo).exposure_amount == pytest.approx(100 - 50 * (1 - 0.14142))


def test_fccm_off_balance_uses_100pct_then_ccf() -> None:
    e = _x(
        AssetClass.CORPORATE,
        on_balance_amount=0.0,
        off_balance_notional=100.0,
        obs_category=OBSCategory.COMMITMENT_OTHER,
        financial_collateral_value=50.0,
        collateral_haircut_class="CASH",
    )
    assert EURegime().risk_weight(e).exposure_amount == pytest.approx((100 - 50) * 0.40)


def test_fccm_unrecognised_collateral_is_ignored() -> None:
    e = _x(AssetClass.CORPORATE, financial_collateral_value=50.0)
    assert EURegime().risk_weight(e).exposure_amount == pytest.approx(100.0)


def test_guarantee_substitution_235() -> None:
    e = _x(
        AssetClass.CORPORATE,
        guarantee_amount=40.0,
        guarantor_asset_class=AssetClass.SOVEREIGN,
        guarantor_rating=rating_bucket_from_cqs(2),
    )
    r = EURegime().risk_weight(e)
    assert r.rwa == pytest.approx(40 * 0.20 + 60 * 1.00)
    worse = _x(
        AssetClass.CORPORATE,
        rating=rating_bucket_from_cqs(1),
        guarantee_amount=40.0,
        guarantor_asset_class=AssetClass.CORPORATE,
        guarantor_rating=rating_bucket_from_cqs(5),
    )
    assert EURegime().risk_weight(worse).rwa == pytest.approx(100 * 0.20)


# =========================================================================
#  Supporting factors -- Articles 501, 501a
# =========================================================================


@pytest.mark.parametrize(
    "e_star,expected",
    [
        (1.0, 0.7619),
        (2.5, 0.7619),
        (5.0, (2.5 * 0.7619 + 2.5 * 0.85) / 5.0),
        (10.0, (2.5 * 0.7619 + 7.5 * 0.85) / 10),
    ],
)
def test_sme_supporting_factor_formula(e_star: float, expected: float) -> None:
    assert credit_risk.sme_supporting_factor(e_star) == pytest.approx(expected)


def test_sme_sf_application_scope() -> None:
    sme_retail = _x(AssetClass.RETAIL_REGULATORY, is_sme=True, on_balance_amount=0.5)
    assert EURegime().risk_weight(sme_retail).rwa == pytest.approx(0.5 * 0.75 * 0.7619)
    big = _x(AssetClass.CORPORATE, annual_turnover=60.0, is_sme=True, on_balance_amount=1.0)
    assert EURegime().risk_weight(big).rwa == pytest.approx(1.0)  # turnover > EUR 50m
    adc = _x(AssetClass.LAND_ADC, is_sme=True, on_balance_amount=1.0)
    assert EURegime().risk_weight(adc).rwa == pytest.approx(1.5)  # ADC excluded (501(2)(a))
    dflt = _x(AssetClass.CORPORATE_SME, is_sme=True, is_defaulted=True, on_balance_amount=1.0)
    assert EURegime().risk_weight(dflt).rwa == pytest.approx(1.5)


def test_infrastructure_supporting_factor() -> None:
    e = _x(AssetClass.CORPORATE, flags={"eu_infrastructure_501a": True})
    assert EURegime().risk_weight(e).rwa == pytest.approx(75.0)


# =========================================================================
#  Operational risk -- Articles 312-314
# =========================================================================


@pytest.mark.parametrize(
    "bi_m,bic_m",
    [
        (500.0, 60.0),  # 0,12 x 0,5bn
        (1000.0, 120.0),  # boundary BI = 1
        (10000.0, (0.12 + 0.15 * 9) * 1000),
        (30000.0, 4470.0),  # boundary BI = 30
        (50000.0, (4.47 + 0.18 * 20) * 1000),
    ],
)
def test_bic_piecewise_313(bi_m: float, bic_m: float) -> None:
    assert operational_risk.business_indicator_component(bi_m) == pytest.approx(bic_m)


def test_bic_continuity_at_30bn() -> None:
    assert pytest.approx(0.12 + 0.15 * 29) == prm.BIC_CONSTANT_BUCKET_3_EUR_BN


def _opinputs() -> OpRiskInputs:
    return OpRiskInputs(
        interest_income=[3000, 3200, 3400],
        interest_expense=[1000, 1100, 1300],
        interest_earning_assets=[80000, 90000, 100000],
        dividend_income=[50, 60, 70],
        fee_income=[1500, 1600, 1700],
        fee_expense=[400, 500, 600],
        other_operating_income=[100, 100, 100],
        other_operating_expense=[150, 150, 150],
        net_pnl_trading_book=[200, -300, 400],
        net_pnl_banking_book=[-50, 60, 70],
        annual_operational_losses=[10.0] * 12,
    )


def test_operational_risk_worked_example() -> None:
    inp = _opinputs()
    r = EURegime().operational_risk(inp)
    ic = 2100.0  # mean(2000, 2100, 2100)
    ildc = min(ic, 0.0225 * 90000) + 60  # = 2025 + 60
    sc = 150 + 1600
    fc = 300 + 60
    bi = ildc + sc + fc
    assert r.business_indicator == pytest.approx(bi)
    bic = (0.12 + 0.15 * (bi / 1000 - 1)) * 1000
    assert r.bic == pytest.approx(bic)
    assert r.capital == pytest.approx(bic)
    assert r.rwa == pytest.approx(12.5 * bic)
    assert r.ilm == 1.0 and r.loss_component is None
    assert r.components["loss_data_collection_required"] == 1.0
    assert r.components["avg_annual_loss_10y_disclosure_only"] == pytest.approx(10.0)


def test_loss_data_threshold_316() -> None:
    assert operational_risk.loss_data_required(750.0)
    assert not operational_risk.loss_data_required(749.99)
    assert prm.OPRISK_LOSS_THRESHOLD_EUR == 20_000.0


# =========================================================================
#  Output floor -- Article 92(3), Article 465
# =========================================================================


@pytest.mark.parametrize(
    "year,x",
    [
        (2024, 0.0),
        (2025, 0.50),
        (2026, 0.55),
        (2027, 0.60),
        (2028, 0.65),
        (2029, 0.70),
        (2030, 0.725),
        (2040, 0.725),
    ],
)
def test_floor_factor_schedule(year: int, x: float) -> None:
    assert output_floor.floor_factor(year) == pytest.approx(x)


def test_floor_cap_465_2_worked_example() -> None:
    reg = EURegime()
    r = reg.output_floor(100.0, 300.0, 2027)  # 60 % x 300 = 180 > 125
    assert r.floored_rwa == pytest.approx(125.0)
    assert r.add_on == pytest.approx(25.0)
    r2 = reg.output_floor(100.0, 300.0, 2030)  # cap no longer available
    assert r2.floored_rwa == pytest.approx(217.5)
    nocap = EURegime(apply_465_2_cap=False).output_floor(100.0, 300.0, 2027)
    assert nocap.floored_rwa == pytest.approx(180.0)


def test_floor_not_binding_and_waiver() -> None:
    r = EURegime().output_floor(100.0, 120.0, 2030)
    assert r.floored_rwa == 100.0 and r.add_on == 0.0
    w = EURegime(individual_basis_floor_waiver=True).output_floor(100.0, 300.0, 2030)
    assert not w.applies and w.floored_rwa == 100.0
    pre = EURegime().output_floor(100.0, 300.0, 2024)
    assert not pre.applies


def test_floor_unrated_corporate_465_3() -> None:
    reg = EURegime(year=2032)
    e = _x(AssetClass.CORPORATE, flags={"eu_irb_pd_le_0_5pct": True})
    assert reg.credit_rwa_for_output_floor([e]).total_rwa == pytest.approx(65.0)
    assert reg.credit_rwa([e]).total_rwa == pytest.approx(100.0)  # U-TREA SA unaffected
    assert EURegime(year=2033).credit_rwa_for_output_floor([e]).total_rwa == pytest.approx(100.0)


@pytest.mark.parametrize(
    "year,rw_b", [(2026, 0.45), (2029, 0.45), (2030, 0.525), (2031, 0.60), (2032, 0.675)]
)
def test_floor_rre_465_5_and_9(year: int, rw_b: float) -> None:
    e = _x(AssetClass.RESIDENTIAL_RE, property_value=100.0, flags={"eu_465_5_eligible": True})
    rwa = EURegime(year=year).credit_rwa_for_output_floor([e]).total_rwa
    assert rwa == pytest.approx(55 * 0.10 + 25 * rw_b + 20 * 0.75)


def test_floor_rre_ends_2032_and_no_sme_sf() -> None:
    e = _x(
        AssetClass.RESIDENTIAL_RE,
        property_value=100.0,
        is_sme=True,
        on_balance_amount=50.0,
        flags={"eu_465_5_eligible": True},
    )
    assert EURegime(year=2026).credit_rwa_for_output_floor([e]).total_rwa == pytest.approx(
        50 * 0.10
    )
    after = EURegime(year=2033).credit_rwa_for_output_floor([e]).total_rwa
    assert after == pytest.approx(50 * 0.20 * credit_risk.sme_supporting_factor(50.0))


def test_floor_saccr_alpha_and_sec_p() -> None:
    assert output_floor.saccr_alpha_for_s_trea(2029, True) == 1.0
    assert output_floor.saccr_alpha_for_s_trea(2030, True) == 1.4
    assert output_floor.saccr_alpha_for_s_trea(2026, False) == 1.4
    assert output_floor.sec_sa_p_factor_for_s_trea("ARTICLE_262", 2032) == 0.25
    assert output_floor.sec_sa_p_factor_for_s_trea("ARTICLE_261", 2032) == 0.5
    assert output_floor.sec_sa_p_factor_for_s_trea("ARTICLE_261", 2033) is None


# =========================================================================
#  Capital stack -- Article 92(1)-(1a)
# =========================================================================


def test_minimum_ratios_92_1() -> None:
    c = EURegime().capital_requirements()
    assert (c.cet1_minimum, c.tier1_minimum, c.total_capital_minimum, c.leverage_minimum) == (
        0.045,
        0.06,
        0.08,
        0.03,
    )


def test_buffer_stacking() -> None:
    c = capital_stack.capital_requirements(
        systemic_bucket_or_rate=2,
        countercyclical_rate=0.01,
        o_sii_rate=0.02,
        systemic_risk_buffer_rate=0.005,
    )
    assert c.systemic_buffer == pytest.approx(0.02)  # max(G-SII 1,5 %, O-SII 2 %)
    assert c.leverage_buffer == pytest.approx(0.5 * 0.015)  # Art. 92(1a) on the G-SII rate
    assert c.combined_buffer == pytest.approx(0.025 + 0.01 + 0.02 + 0.005)
    assert c.cet1_requirement == pytest.approx(0.045 + 0.06)


def test_buffer_inputs_and_stress_buffer_not_stacked() -> None:
    c = EURegime().capital_requirements(0.01, 0.0, stress_buffer=0.02)
    assert c.stress_buffer == 0.0 and "stress_buffer" in c.citations
    assert c.systemic_buffer == 0.01
    with pytest.raises(ValueError):
        capital_stack.capital_requirements(7)
    with pytest.raises(ValueError):
        capital_stack.capital_requirements(0.0, -0.01)


# =========================================================================
#  SA-CCR -- Articles 274, 278
# =========================================================================


def test_saccr_alpha_and_multiplier() -> None:
    ns = SACCRNettingSetInput(netting_set_id="n", replacement_cost=10.0, aggregate_addon=20.0)
    r = EURegime().saccr_ead(ns)
    assert r.alpha == 1.4 and r.multiplier == 1.0
    assert r.ead == pytest.approx(1.4 * 30.0)
    nfc = ns.model_copy(update={"counterparty_is_nonfinancial": True})
    assert EURegime().saccr_ead(nfc).alpha == 1.4  # no NFC alpha relief in the CRR


def test_saccr_multiplier_worked_example() -> None:
    ns = SACCRNettingSetInput(
        netting_set_id="n",
        replacement_cost=0.0,
        aggregate_addon=20.0,
        mtm=-10.0,
        net_collateral=0.0,
    )
    m = 0.05 + 0.95 * math.exp(-10.0 / (2 * 0.95 * 20.0))
    r = saccr.saccr_ead(ns)
    assert r.multiplier == pytest.approx(m)
    assert r.ead == pytest.approx(1.4 * m * 20.0)
    assert saccr.pfe_multiplier(-5.0, 0.0) == 0.05


def test_saccr_floor_alpha_and_sold_options() -> None:
    ns = SACCRNettingSetInput(
        netting_set_id="n",
        replacement_cost=10.0,
        aggregate_addon=0.0,
        flags={"eu_u_trea_uses_imm": True},
    )
    assert saccr.saccr_ead(ns, 2029, for_output_floor=True).ead == pytest.approx(10.0)
    so = SACCRNettingSetInput(
        netting_set_id="s",
        replacement_cost=5.0,
        aggregate_addon=1.0,
        flags={"eu_sold_options_274_5": True},
    )
    assert saccr.saccr_ead(so).ead == 0.0


# =========================================================================
#  BA-CVA -- Articles 382-386
# =========================================================================


@pytest.mark.parametrize(
    "sector,ig,hy",
    [
        ("SOVEREIGN", 0.005, 0.020),
        ("RGLA_PSE", 0.010, 0.040),
        ("FINANCIAL", 0.050, 0.120),
        ("BASIC_MATERIALS", 0.030, 0.070),
        ("CONSUMER", 0.030, 0.085),
        ("TECHNOLOGY", 0.020, 0.055),
        ("HEALTHCARE", 0.015, 0.050),
        ("OTHER", 0.050, 0.120),
    ],
)
def test_bacva_table_1(sector: str, ig: float, hy: float) -> None:
    assert cva.risk_weight(sector, "IG") == ig
    assert cva.risk_weight(sector, "HY_NR") == hy


@pytest.mark.parametrize("rel,r", [("DIRECT", 1.0), ("LEGAL", 0.8), ("SECTOR", 0.5)])
def test_bacva_table_2(rel: str, r: float) -> None:
    assert prm.BACVA_HEDGE_CORRELATION[rel] == r


def test_bacva_reduced_worked_example() -> None:
    cps: list[dict[str, float | str | bool]] = [
        {"ead": 100.0, "maturity": 2.0, "sector": "FINANCIAL", "credit_quality": "IG"},
        {"ead": 50.0, "maturity": 5.0, "sector": "CONSUMER", "credit_quality": "HY_NR"},
    ]
    df = lambda m: (1 - math.exp(-0.05 * m)) / (0.05 * m)  # noqa: E731
    s1 = 0.05 * 2.0 * 100.0 * df(2.0) / 1.4
    s2 = 0.085 * 5.0 * 50.0 * df(5.0) / 1.4
    k = 0.65 * math.sqrt((0.5 * (s1 + s2)) ** 2 + 0.75 * (s1**2 + s2**2))
    out = EURegime().ba_cva_capital(cps)
    assert out["k_reduced"] == pytest.approx(k)
    assert out["k"] == pytest.approx(k)
    assert out["rwa"] == pytest.approx(12.5 * k)


def test_bacva_hedged_worked_example() -> None:
    cps: list[dict[str, float | str | bool]] = [
        {
            "ead": 100.0,
            "maturity": 3.0,
            "sector": "TECHNOLOGY",
            "credit_quality": "IG",
            "sn_hedge_notional": 20.0,
            "sn_hedge_maturity": 3.0,
            "sn_hedge_relation": "LEGAL",
        },
        {
            "index_hedge": True,
            "notional": 10.0,
            "maturity": 5.0,
            "sector": "OTHER",
            "credit_quality": "IG",
        },
    ]
    df = lambda m: (1 - math.exp(-0.05 * m)) / (0.05 * m)  # noqa: E731
    s = 0.02 * 3.0 * 100.0 * df(3.0) / 1.4
    term = 0.02 * 3.0 * 20.0 * df(3.0)
    snh, hma = 0.8 * term, (1 - 0.64) * term**2
    ih = 0.7 * 0.05 * 5.0 * 10.0 * df(5.0)
    k_red = 0.65 * math.sqrt((0.5 * s) ** 2 + 0.75 * s**2)
    k_hed = math.sqrt((0.5 * (s - snh) - ih) ** 2 + 0.75 * (s - snh) ** 2 + hma)
    out = cva.ba_cva_capital(cps, hedged=True)
    assert out["k_hedged"] == pytest.approx(k_hed)
    assert out["k"] == pytest.approx(0.25 * k_red + 0.65 * 0.75 * k_hed)


def test_bacva_exemptions_and_imm_df() -> None:
    cps: list[dict[str, float | str | bool]] = [
        {"ead": 100.0, "maturity": 2.0, "sector": "FINANCIAL", "credit_quality": "IG", "imm": True},
        {"ead": 70.0, "maturity": 2.0, "sector": "CONSUMER", "nfc_below_clearing_threshold": True},
        {"ead": 30.0, "maturity": 2.0, "sector": "FINANCIAL", "intragroup": True},
    ]
    out = cva.ba_cva_capital(cps)
    assert out["excluded_ead"] == pytest.approx(100.0)
    s = 0.05 * 2.0 * 100.0 / 1.4  # DF = 1 for IMM
    assert out["k_reduced"] == pytest.approx(0.65 * math.sqrt(0.25 * s**2 + 0.75 * s**2))
    assert cva.supervisory_discount_factor(0.0) == 1.0
    assert cva.simplified_cva_capital(125.0) == pytest.approx(10.0)


def test_bacva_same_counterparty_netting_sets_aggregate() -> None:
    one = cva.ba_cva_capital(
        [{"ead": 100.0, "maturity": 1.0, "sector": "OTHER", "counterparty_id": "A"}]
    )
    two = cva.ba_cva_capital(
        [
            {"ead": 60.0, "maturity": 1.0, "sector": "OTHER", "counterparty_id": "A"},
            {"ead": 40.0, "maturity": 1.0, "sector": "OTHER", "counterparty_id": "A"},
        ]
    )
    assert one["k_reduced"] == pytest.approx(two["k_reduced"])


# =========================================================================
#  Portfolio aggregation
# =========================================================================


def test_credit_rwa_aggregation() -> None:
    exps = [
        _x(AssetClass.CORPORATE),
        _x(AssetClass.RETAIL_REGULATORY),
        _x(AssetClass.SOVEREIGN, rating=RatingBucket.AAA_TO_AA_MINUS),
    ]
    res = EURegime().credit_rwa(exps)
    assert res.total_exposure == pytest.approx(300.0)
    assert res.total_rwa == pytest.approx(175.0)
    assert res.density == pytest.approx(175.0 / 300.0)
    assert sum(res.rwa_by_class.values()) == pytest.approx(175.0)
    assert len(res.line_items) == 3
