"""Tests for the UK PRA Basel 3.1 package (PS1/26 Appendix 1).

Each transcribed table cell is asserted (parametrised), with hand-computed
worked examples for the formulae (loan splitting, FCCM, substitution, BIC,
output floor, SA-CCR, BA-CVA) and the transitional schedules.
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
from src.jurisdictions.uk import UKRegime, cva, saccr
from src.jurisdictions.uk import credit_risk as cr
from src.jurisdictions.uk import operational_risk as orisk
from src.jurisdictions.uk import output_floor as of
from src.jurisdictions.uk import params as p

R = UKRegime()
R_2030 = UKRegime(year=2030)


def exp(asset_class: AssetClass, amount: float = 100.0, **kw: object) -> SAExposure:
    """Build a simple exposure."""
    return SAExposure(exposure_id="t", asset_class=asset_class, on_balance_amount=amount, **kw)


def rw(e: SAExposure, regime: UKRegime = R) -> float:
    """Risk weight under a regime."""
    return regime.risk_weight(e).risk_weight


# =========================================================================
#  Protocol conformance
# =========================================================================


def test_protocol_conformance() -> None:
    regime = UKRegime()
    assert isinstance(regime, RegimeCalculator)
    assert regime.jurisdiction is Jurisdiction.UK
    assert "PS1/26" in regime.legal_basis


# =========================================================================
#  Article 114 / 137 -- sovereigns
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", [(1, 0.0), (2, 0.20), (3, 0.50), (4, 1.0), (5, 1.0), (6, 1.50)]
)
def test_sovereign_table_1(cqs: int, expected: float) -> None:
    assert rw(exp(AssetClass.SOVEREIGN, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(
        expected
    )


def test_sovereign_unrated_and_uk_sterling() -> None:
    assert rw(exp(AssetClass.SOVEREIGN)) == 1.0
    uk = exp(
        AssetClass.SOVEREIGN,
        domestic_currency_funded=True,
        flags={"uk_central_government_or_boe": True},
    )
    assert rw(uk) == 0.0
    uk_fx = exp(AssetClass.SOVEREIGN, flags={"uk_central_government_or_boe": True})
    assert rw(uk_fx) == 1.0
    assert rw(exp(AssetClass.SOVEREIGN, flags={"ecb": True})) == 0.0


@pytest.mark.parametrize(
    "meip,expected",
    [(0, 0.0), (1, 0.0), (2, 0.20), (3, 0.50), (4, 1.0), (5, 1.0), (6, 1.0), (7, 1.50)],
)
def test_eca_table_9(meip: int, expected: float) -> None:
    e = exp(AssetClass.SOVEREIGN, oecd_crc=meip, flags={"eca_score_used": True})
    assert rw(e) == pytest.approx(expected)


# =========================================================================
#  Article 115 / 116 -- RGLAs and PSEs
# =========================================================================


@pytest.mark.parametrize(
    "cqs,t1a,t1b",
    [
        (1, 0.20, 0.20),
        (2, 0.50, 0.50),
        (3, 1.0, 0.50),
        (4, 1.0, 1.0),
        (5, 1.0, 1.0),
        (6, 1.50, 1.50),
    ],
)
def test_rgla_tables_1a_1b(cqs: int, t1a: float, t1b: float) -> None:
    bucket = rating_bucket_from_cqs(cqs)
    flags = {"regional_government": True}
    assert rw(exp(AssetClass.PSE, sovereign_rating=bucket, flags=flags)) == pytest.approx(t1a)
    assert rw(exp(AssetClass.PSE, rating=bucket, flags=flags)) == pytest.approx(t1b)


def test_rgla_special_cases() -> None:
    assert rw(exp(AssetClass.PSE, flags={"regional_government": True})) == 1.0
    uk_la = exp(
        AssetClass.PSE,
        domestic_currency_funded=True,
        flags={"regional_government": True, "uk_entity": True},
    )
    assert rw(uk_la) == pytest.approx(0.20)
    scot = exp(
        AssetClass.PSE, domestic_currency_funded=True, flags={"uk_devolved_administration": True}
    )
    assert rw(scot) == 0.0


@pytest.mark.parametrize(
    "cqs,t2,t2a",
    [
        (1, 0.20, 0.20),
        (2, 0.50, 0.50),
        (3, 1.0, 0.50),
        (4, 1.0, 1.0),
        (5, 1.0, 1.0),
        (6, 1.50, 1.50),
    ],
)
def test_pse_tables_2_2a(cqs: int, t2: float, t2a: float) -> None:
    bucket = rating_bucket_from_cqs(cqs)
    assert rw(exp(AssetClass.PSE, sovereign_rating=bucket)) == pytest.approx(t2)
    assert rw(exp(AssetClass.PSE, rating=bucket)) == pytest.approx(t2a)


@pytest.mark.parametrize("months,expected", [(3.0, 0.20), (3.01, 1.0)])
def test_pse_short_term_boundary(months: float, expected: float) -> None:
    assert rw(exp(AssetClass.PSE, original_maturity_months=months)) == pytest.approx(expected)


# =========================================================================
#  Articles 117-118 -- MDBs and international organisations
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", [(1, 0.20), (2, 0.30), (3, 0.50), (4, 1.0), (5, 1.0), (6, 1.50)]
)
def test_mdb_table_2b(cqs: int, expected: float) -> None:
    assert rw(exp(AssetClass.MDB, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(expected)


def test_mdb_other_cases() -> None:
    assert rw(exp(AssetClass.MDB)) == pytest.approx(0.50)
    assert rw(exp(AssetClass.MDB, flags={"mdb_listed_zero_rw": True})) == 0.0
    assert rw(exp(AssetClass.MDB, flags={"international_organisation": True})) == 0.0
    assert len(p.MDB_ZERO_RW_LIST) == 16


# =========================================================================
#  Articles 120-121 -- institutions
# =========================================================================


@pytest.mark.parametrize(
    "cqs,t3,t4",
    [
        (1, 0.20, 0.20),
        (2, 0.30, 0.20),
        (3, 0.50, 0.20),
        (4, 1.0, 0.50),
        (5, 1.0, 0.50),
        (6, 1.50, 1.50),
    ],
)
def test_institution_tables_3_4(cqs: int, t3: float, t4: float) -> None:
    bucket = rating_bucket_from_cqs(cqs)
    assert rw(exp(AssetClass.BANK, rating=bucket, original_maturity_months=12)) == pytest.approx(t3)
    assert rw(exp(AssetClass.BANK, rating=bucket, original_maturity_months=3)) == pytest.approx(t4)
    goods = exp(
        AssetClass.BANK, rating=bucket, original_maturity_months=6, flags={"goods_movement": True}
    )
    assert rw(goods) == pytest.approx(t4)
    goods7 = exp(
        AssetClass.BANK, rating=bucket, original_maturity_months=6.5, flags={"goods_movement": True}
    )
    assert rw(goods7) == pytest.approx(t3)


@pytest.mark.parametrize(
    "st,expected",
    [
        (ShortTermRating.A1_P1, 0.20),
        (ShortTermRating.A2_P2, 0.50),
        (ShortTermRating.A3_P3, 1.0),
        (ShortTermRating.OTHERS, 1.50),
    ],
)
def test_institution_table_4a(st: ShortTermRating, expected: float) -> None:
    assert rw(exp(AssetClass.BANK, short_term_rating=st)) == pytest.approx(expected)


@pytest.mark.parametrize(
    "grade,t5,t5a",
    [(SCRAGrade.A, 0.40, 0.20), (SCRAGrade.B, 0.75, 0.50), (SCRAGrade.C, 1.50, 1.50)],
)
def test_institution_tables_5_5a(grade: SCRAGrade, t5: float, t5a: float) -> None:
    assert rw(exp(AssetClass.BANK, scra_grade=grade, original_maturity_months=12)) == pytest.approx(
        t5
    )
    assert rw(exp(AssetClass.BANK, scra_grade=grade, original_maturity_months=3)) == pytest.approx(
        t5a
    )


def test_institution_grade_a_enhanced_and_floor() -> None:
    e = exp(
        AssetClass.BANK,
        scra_grade=SCRAGrade.A,
        scra_grade_a_enhanced=True,
        original_maturity_months=12,
    )
    assert rw(e) == pytest.approx(0.30)
    # Enhanced 30% only for > 3 months; short-term stays at Table 5A 20%
    e_st = e.model_copy(update={"original_maturity_months": 2.0})
    assert rw(e_st) == pytest.approx(0.20)
    # Art 121(6) sovereign floor for foreign-currency exposures
    fx = exp(
        AssetClass.BANK,
        scra_grade=SCRAGrade.A,
        original_maturity_months=12,
        sovereign_rating=RatingBucket.BB_PLUS_TO_BB_MINUS,
        flags={"foreign_currency_exposure": True},
    )
    assert rw(fx) == pytest.approx(1.0)
    trade = fx.model_copy(update={"is_trade_related": True, "original_maturity_months": 6.0})
    assert rw(trade) == pytest.approx(0.20)


def test_institution_missing_grade_is_conservative() -> None:
    res = R.risk_weight(exp(AssetClass.BANK, original_maturity_months=12))
    assert res.risk_weight == pytest.approx(1.50)
    assert any("Grade C" in n for n in res.notes)


def test_due_diligence_notch() -> None:
    e = exp(
        AssetClass.BANK,
        rating=RatingBucket.AAA_TO_AA_MINUS,
        original_maturity_months=12,
        flags={"due_diligence_notch_up": True},
    )
    assert rw(e) == pytest.approx(0.30)


# =========================================================================
#  Article 122 / 122B -- corporates and specialised lending
# =========================================================================


@pytest.mark.parametrize(
    "cqs,expected", [(1, 0.20), (2, 0.50), (3, 0.75), (4, 1.0), (5, 1.50), (6, 1.50)]
)
def test_corporate_table_6(cqs: int, expected: float) -> None:
    assert rw(exp(AssetClass.CORPORATE, rating=rating_bucket_from_cqs(cqs))) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    "st,expected",
    [
        (ShortTermRating.A1_P1, 0.20),
        (ShortTermRating.A2_P2, 0.50),
        (ShortTermRating.A3_P3, 1.0),
        (ShortTermRating.OTHERS, 1.50),
    ],
)
def test_corporate_table_6a(st: ShortTermRating, expected: float) -> None:
    assert rw(exp(AssetClass.CORPORATE, short_term_rating=st)) == pytest.approx(expected)


def test_corporate_unrated_options() -> None:
    assert rw(exp(AssetClass.CORPORATE)) == 1.0
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True)) == 1.0  # no permission
    perm = UKRegime(corporate_ig_permission=True)
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True), perm) == pytest.approx(0.65)
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=False), perm) == pytest.approx(1.35)
    assert rw(exp(AssetClass.CORPORATE), perm) == pytest.approx(1.35)
    # SME 85% overrides the IG permission (Art 122(6) 'subject to paragraph 11')
    assert rw(exp(AssetClass.CORPORATE_SME, is_investment_grade=True), perm) == pytest.approx(0.85)


@pytest.mark.parametrize("turnover,expected", [(44.0, 0.85), (44.01, 1.0)])
def test_sme_turnover_boundary(turnover: float, expected: float) -> None:
    assert rw(exp(AssetClass.CORPORATE, annual_turnover=turnover)) == pytest.approx(expected)


def test_no_support_factor() -> None:
    assert p.SUPPORT_FACTOR == 1.0
    assert rw(exp(AssetClass.CORPORATE_SME)) == pytest.approx(0.85)


@pytest.mark.parametrize(
    "ac,phase,expected",
    [
        (AssetClass.SPECIALISED_LENDING_OF, None, 1.0),
        (AssetClass.SPECIALISED_LENDING_CF, None, 1.0),
        (AssetClass.SPECIALISED_LENDING_PF, PFPhase.PRE_OPERATIONAL, 1.30),
        (AssetClass.SPECIALISED_LENDING_PF, PFPhase.OPERATIONAL, 1.0),
        (AssetClass.SPECIALISED_LENDING_PF, PFPhase.HIGH_QUALITY_OPERATIONAL, 0.80),
        (AssetClass.SPECIALISED_LENDING_PF, None, 1.30),
    ],
)
def test_specialised_lending(ac: AssetClass, phase: PFPhase | None, expected: float) -> None:
    assert rw(exp(ac, pf_phase=phase)) == pytest.approx(expected)


def test_specialised_lending_rated_uses_table_6() -> None:
    e = exp(AssetClass.SPECIALISED_LENDING_PF, rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS)
    assert rw(e) == pytest.approx(0.75)


# =========================================================================
#  Articles 123-123B -- retail and currency mismatch
# =========================================================================


def test_retail_weights() -> None:
    assert rw(exp(AssetClass.RETAIL_TRANSACTOR)) == pytest.approx(0.45)
    assert rw(exp(AssetClass.RETAIL_REGULATORY)) == pytest.approx(0.75)
    assert rw(exp(AssetClass.RETAIL_REGULATORY, is_transactor=True)) == pytest.approx(0.45)
    assert rw(exp(AssetClass.RETAIL_OTHER)) == 1.0
    assert rw(exp(AssetClass.RETAIL_REGULATORY, meets_regulatory_retail_criteria=False)) == 1.0
    assert rw(
        exp(AssetClass.RETAIL_REGULATORY, flags={"payroll_or_pension_loan": True})
    ) == pytest.approx(0.35)


@pytest.mark.parametrize("agg,expected", [(0.88, 0.75), (0.8801, 1.0)])
def test_retail_gbp_880k_boundary(agg: float, expected: float) -> None:
    assert rw(
        exp(AssetClass.RETAIL_REGULATORY, aggregate_retail_exposure_to_obligor=agg)
    ) == pytest.approx(expected)


def test_sme_over_retail_limit_is_corporate() -> None:
    e = exp(AssetClass.RETAIL_REGULATORY, is_sme=True, aggregate_retail_exposure_to_obligor=1.0)
    assert rw(e) == pytest.approx(0.85)


@pytest.mark.parametrize(
    "ac,base,expected",
    [
        (AssetClass.RETAIL_REGULATORY, 0.75, 1.125),
        (AssetClass.RETAIL_TRANSACTOR, 0.45, 0.675),
        (AssetClass.RETAIL_OTHER, 1.0, 1.50),
    ],
)
def test_currency_mismatch_multiplier(ac: AssetClass, base: float, expected: float) -> None:
    assert rw(exp(ac, currency_matches_borrower_income=False)) == pytest.approx(expected)
    hedged = exp(
        ac, currency_matches_borrower_income=False, flags={"currency_mismatch_hedged": True}
    )
    assert rw(hedged) == pytest.approx(base)


def test_currency_mismatch_cap_on_rre() -> None:
    e = exp(
        AssetClass.RESIDENTIAL_RE,
        105.0,
        property_value=100.0,
        ltv=1.05,
        is_cash_flow_dependent=True,
        currency_matches_borrower_income=False,
    )
    assert rw(e) == pytest.approx(1.50)  # 105% x 1.5 = 157.5% capped at 150%


def test_currency_mismatch_not_for_defaulted_or_reclassified() -> None:
    d = exp(AssetClass.RETAIL_OTHER, is_defaulted=True, currency_matches_borrower_income=False)
    assert rw(d) == pytest.approx(1.50)  # Art 127 150%, not 100% x 1.5 then capped
    d20 = d.model_copy(update={"specific_provision_pct": 0.25})
    assert rw(d20) == pytest.approx(1.0)
    sme = exp(
        AssetClass.RETAIL_REGULATORY,
        is_sme=True,
        aggregate_retail_exposure_to_obligor=2.0,
        currency_matches_borrower_income=False,
    )
    assert rw(sme) == pytest.approx(0.85)


def test_currency_mismatch_not_for_cre() -> None:
    e = exp(
        AssetClass.COMMERCIAL_RE,
        50.0,
        ltv=0.5,
        is_cash_flow_dependent=True,
        currency_matches_borrower_income=False,
    )
    assert rw(e) == pytest.approx(1.0)


# =========================================================================
#  Articles 124-124L -- real estate
# =========================================================================


@pytest.mark.parametrize(
    "ltv,expected",
    [
        (0.50, 0.30),
        (0.5001, 0.35),
        (0.60, 0.35),
        (0.65, 0.40),
        (0.70, 0.40),
        (0.75, 0.50),
        (0.80, 0.50),
        (0.85, 0.60),
        (0.90, 0.60),
        (0.95, 0.75),
        (1.00, 0.75),
        (1.0001, 1.05),
    ],
)
def test_rre_cash_flow_table_6b(ltv: float, expected: float) -> None:
    e = exp(
        AssetClass.RESIDENTIAL_RE,
        ltv * 100,
        property_value=100.0,
        ltv=ltv,
        is_cash_flow_dependent=True,
    )
    assert rw(e) == pytest.approx(expected)


@pytest.mark.parametrize("ltv,expected", [(0.50, 0.30), (0.70, 0.40 * 1.25), (0.95, 0.75 * 1.25)])
def test_rre_cash_flow_junior_multiplier(ltv: float, expected: float) -> None:
    e = exp(
        AssetClass.RESIDENTIAL_RE,
        10.0,
        property_value=100.0,
        ltv=ltv,
        is_cash_flow_dependent=True,
        flags={"senior_charges_not_held": True},
    )
    assert rw(e) == pytest.approx(expected)


def test_rre_loan_splitting_worked_example() -> None:
    # Loan 80 on property 100: 55 at 20% + 25 at 75% = 11 + 18.75 = 29.75 -> RW 37.1875%
    e = exp(AssetClass.RESIDENTIAL_RE, 80.0, property_value=100.0)
    res = R.risk_weight(e)
    assert res.rwa == pytest.approx(29.75)
    assert res.risk_weight == pytest.approx(29.75 / 80.0)


def test_rre_loan_splitting_below_55pct_is_20pct() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, 55.0, property_value=100.0)) == pytest.approx(0.20)
    assert rw(exp(AssetClass.RESIDENTIAL_RE, 30.0, ltv=0.30)) == pytest.approx(0.20)


def test_rre_loan_splitting_with_senior_charge() -> None:
    # Own loan 40, senior third-party charge 30 (LTV incl. senior = 70%) on property 100:
    # eligible = 55 - 30 = 25 at 20%, 15 at 75% -> 5 + 11.25 = 16.25
    e = exp(
        AssetClass.RESIDENTIAL_RE,
        40.0,
        property_value=100.0,
        ltv=0.70,
        flags={"senior_charges_not_held": True},
    )
    assert R.risk_weight(e).rwa == pytest.approx(16.25)


def test_rre_loan_splitting_sme_and_social_housing_counterparty() -> None:
    sme = exp(
        AssetClass.RESIDENTIAL_RE,
        100.0,
        property_value=100.0,
        is_sme=True,
        aggregate_retail_exposure_to_obligor=5.0,
    )
    assert R.risk_weight(sme).rwa == pytest.approx(55 * 0.20 + 45 * 0.85)
    social = exp(
        AssetClass.RESIDENTIAL_RE,
        100.0,
        property_value=100.0,
        flags={"social_housing": True, "obligor_is_natural_person": False},
    )
    assert R.risk_weight(social).rwa == pytest.approx(55 * 0.20 + 45 * 1.0)


def test_rre_other_real_estate() -> None:
    cf = exp(
        AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False, is_cash_flow_dependent=True
    )
    assert rw(cf) == pytest.approx(1.50)
    non_cf = exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False)
    assert rw(non_cf) == pytest.approx(0.75)


@pytest.mark.parametrize(
    "ltv,senior,expected",
    [
        (0.80, False, 1.0),
        (0.8001, False, 1.10),
        (0.60, True, 1.0),
        (0.6001, True, 1.25),
        (0.80, True, 1.25),
        (0.8001, True, 1.375),
    ],
)
def test_cre_cash_flow_124i(ltv: float, senior: bool, expected: float) -> None:
    e = exp(
        AssetClass.COMMERCIAL_RE,
        10.0,
        property_value=100.0,
        ltv=ltv,
        is_cash_flow_dependent=True,
        flags={"senior_charges_not_held": senior},
    )
    assert rw(e) == pytest.approx(expected)


def test_cre_non_cf_natural_person_loan_split() -> None:
    # Loan 70 on 100: 55 at 60% + 15 at 75% = 33 + 11.25 = 44.25
    e = exp(
        AssetClass.COMMERCIAL_RE,
        70.0,
        property_value=100.0,
        flags={"obligor_is_natural_person": True},
    )
    assert R.risk_weight(e).rwa == pytest.approx(44.25)
    sme = exp(
        AssetClass.COMMERCIAL_RE,
        70.0,
        property_value=100.0,
        is_sme=True,
        meets_regulatory_retail_criteria=False,
    )
    assert R.risk_weight(sme).rwa == pytest.approx(55 * 0.60 + 15 * 0.85)


def test_cre_non_cf_other_obligor_124h3() -> None:
    # Unrated corporate (100%), LTV 70%: max(60%, min(100%, 100%)) = 100%
    e = exp(AssetClass.COMMERCIAL_RE, 70.0, property_value=100.0, ltv=0.70)
    assert rw(e) == pytest.approx(1.0)
    # A-rated corporate (50%): max(60%, min(50%, 100%)) = 60%
    a = exp(
        AssetClass.COMMERCIAL_RE,
        70.0,
        property_value=100.0,
        ltv=0.70,
        rating=RatingBucket.A_PLUS_TO_A_MINUS,
    )
    assert rw(a) == pytest.approx(0.60)


def test_cre_other_real_estate_124j() -> None:
    assert (
        rw(
            exp(
                AssetClass.COMMERCIAL_RE,
                is_regulatory_real_estate=False,
                is_cash_flow_dependent=True,
            )
        )
        == 1.5
    )
    rated = exp(
        AssetClass.COMMERCIAL_RE,
        is_regulatory_real_estate=False,
        rating=RatingBucket.AAA_TO_AA_MINUS,
    )
    assert rw(rated) == pytest.approx(0.60)


def test_adc() -> None:
    assert rw(exp(AssetClass.LAND_ADC)) == pytest.approx(1.50)
    assert rw(exp(AssetClass.LAND_ADC, is_adc_presold_or_equity_at_risk=True)) == pytest.approx(1.0)
    commercial = exp(
        AssetClass.LAND_ADC, is_adc_presold_or_equity_at_risk=True, flags={"residential_adc": False}
    )
    assert rw(commercial) == pytest.approx(1.50)


def test_mixed_real_estate_split() -> None:
    e = exp(AssetClass.RESIDENTIAL_RE, 60.0)
    rre, cre = cr.split_mixed_real_estate(e, 75.0, 25.0)
    assert rre.on_balance_amount == pytest.approx(45.0)
    assert cre.on_balance_amount == pytest.approx(15.0)
    assert cre.asset_class is AssetClass.COMMERCIAL_RE
    with pytest.raises(ValueError):
        cr.split_mixed_real_estate(e, 0.0, 0.0)


def test_missing_ltv_is_conservative() -> None:
    e = exp(AssetClass.RESIDENTIAL_RE, is_cash_flow_dependent=True)
    assert rw(e) == pytest.approx(1.05)
    split = R.risk_weight(exp(AssetClass.RESIDENTIAL_RE))
    assert split.risk_weight == pytest.approx(0.75)


# =========================================================================
#  Articles 127-129 -- defaulted, high risk, covered bonds
# =========================================================================


@pytest.mark.parametrize("prov,expected", [(0.0, 1.50), (0.1999, 1.50), (0.20, 1.0), (0.5, 1.0)])
def test_defaulted_provision_test(prov: float, expected: float) -> None:
    assert rw(exp(AssetClass.DEFAULTED, specific_provision_pct=prov)) == pytest.approx(expected)
    assert rw(
        exp(AssetClass.CORPORATE, is_defaulted=True, specific_provision_pct=prov)
    ) == pytest.approx(expected)


def test_defaulted_rre_non_cf_100() -> None:
    e = exp(AssetClass.RESIDENTIAL_RE, is_defaulted=True, property_value=200.0)
    assert rw(e) == pytest.approx(1.0)
    cf = exp(AssetClass.RESIDENTIAL_RE, is_defaulted=True, is_cash_flow_dependent=True)
    assert rw(cf) == pytest.approx(1.50)


def test_high_risk() -> None:
    assert rw(exp(AssetClass.CORPORATE, flags={"particularly_high_risk": True})) == pytest.approx(
        1.50
    )


@pytest.mark.parametrize(
    "cqs,expected", [(1, 0.10), (2, 0.20), (3, 0.20), (4, 0.50), (5, 0.50), (6, 1.0)]
)
def test_covered_bond_table_7(cqs: int, expected: float) -> None:
    e = exp(AssetClass.COVERED_BOND, covered_bond_rated=True, rating=rating_bucket_from_cqs(cqs))
    assert rw(e) == pytest.approx(expected)


@pytest.mark.parametrize(
    "issuer_kw,expected",
    [
        ({"rating": RatingBucket.AAA_TO_AA_MINUS}, 0.10),  # issuer 20%
        ({"rating": RatingBucket.A_PLUS_TO_A_MINUS}, 0.15),  # issuer 30%
        ({"scra_grade": SCRAGrade.A}, 0.20),  # issuer 40%
        ({"rating": RatingBucket.BBB_PLUS_TO_BBB_MINUS}, 0.25),  # issuer 50%
        ({"scra_grade": SCRAGrade.B}, 0.35),  # issuer 75%
        ({"rating": RatingBucket.BB_PLUS_TO_BB_MINUS}, 0.50),  # issuer 100%
        ({"scra_grade": SCRAGrade.C}, 1.0),  # issuer 150%
    ],
)
def test_covered_bond_unrated_map(issuer_kw: dict[str, object], expected: float) -> None:
    assert rw(exp(AssetClass.COVERED_BOND, **issuer_kw)) == pytest.approx(expected)


# =========================================================================
#  Article 133 + GP Part 4.2/4.3 -- equity and subordinated debt
# =========================================================================


@pytest.mark.parametrize(
    "year,general,higher",
    [
        (2027, 1.60, 2.20),
        (2028, 1.90, 2.80),
        (2029, 2.20, 3.40),
        (2030, 2.50, 4.00),
        (2035, 2.50, 4.00),
    ],
)
def test_equity_transitional(year: int, general: float, higher: float) -> None:
    regime = UKRegime(year=year)
    assert rw(exp(AssetClass.EQUITY), regime) == pytest.approx(general)
    assert rw(exp(AssetClass.EQUITY, flags={"higher_risk_equity": True}), regime) == pytest.approx(
        higher
    )
    assert rw(
        exp(AssetClass.EQUITY, equity_type=EquityType.SPECULATIVE_UNLISTED), regime
    ) == pytest.approx(higher)


def test_equity_other_types() -> None:
    assert rw(exp(AssetClass.EQUITY, equity_type=EquityType.SIGNIFICANT_FI)) == pytest.approx(2.50)
    assert rw(
        exp(AssetClass.EQUITY, equity_type=EquityType.LEGISLATIVE_PROGRAMME), R_2030
    ) == pytest.approx(2.50)
    assert rw(
        exp(AssetClass.EQUITY, equity_type=EquityType.PUBLICLY_TRADED), R_2030
    ) == pytest.approx(2.50)
    opt_out = UKRegime(year=2027, irb_firm=True, equity_transitional_opt_out=True)
    assert rw(exp(AssetClass.EQUITY), opt_out) == pytest.approx(2.50)
    irb = UKRegime(year=2028, irb_firm=True)
    assert rw(exp(AssetClass.EQUITY), irb) == pytest.approx(1.90)


def test_subordinated_debt() -> None:
    assert rw(exp(AssetClass.SUBORDINATED_DEBT)) == pytest.approx(1.50)


# =========================================================================
#  Article 134 / 113(5) -- other items
# =========================================================================


@pytest.mark.parametrize(
    "flag,expected",
    [("cash", 0.0), ("gold_bullion", 0.0), ("cash_in_collection", 0.20), (None, 1.0)],
)
def test_other_items(flag: str | None, expected: float) -> None:
    flags = {flag: True} if flag else {}
    assert rw(exp(AssetClass.OTHER_ASSETS, flags=flags)) == pytest.approx(expected)


# =========================================================================
#  Article 111 Table A1 -- conversion factors
# =========================================================================


@pytest.mark.parametrize(
    "cat,expected",
    [
        (OBSCategory.UNCONDITIONALLY_CANCELLABLE, 0.10),
        (OBSCategory.COMMITMENT_OTHER, 0.40),
        (OBSCategory.NIF_RUF, 0.50),
        (OBSCategory.TRANSACTION_RELATED_CONTINGENT, 0.20),
        (OBSCategory.SHORT_TERM_TRADE_LC, 0.20),
        (OBSCategory.DIRECT_CREDIT_SUBSTITUTE, 1.0),
        (OBSCategory.SECURITIES_LENDING_COLLATERAL, 1.0),
        (OBSCategory.FORWARD_ASSET_PURCHASE, 1.0),
        (OBSCategory.OTHER_100, 1.0),
    ],
)
def test_table_a1(cat: OBSCategory, expected: float) -> None:
    e = SAExposure(
        exposure_id="o",
        asset_class=AssetClass.CORPORATE,
        off_balance_notional=10.0,
        obs_category=cat,
    )
    assert R.ccf(e) == pytest.approx(expected)
    assert R.risk_weight(e).exposure_amount == pytest.approx(10.0 * expected)


def test_ccf_special_rows() -> None:
    mort = SAExposure(
        exposure_id="m",
        asset_class=AssetClass.RESIDENTIAL_RE,
        off_balance_notional=10.0,
        obs_category=OBSCategory.COMMITMENT_OTHER,
        flags={"uk_residential_mortgage_commitment": True},
    )
    assert R.ccf(mort) == pytest.approx(0.50)
    issue = SAExposure(
        exposure_id="c",
        asset_class=AssetClass.CORPORATE,
        off_balance_notional=10.0,
        obs_category=OBSCategory.DIRECT_CREDIT_SUBSTITUTE,
        flags={"commitment_to_issue_obs_item": True},
    )
    assert R.ccf(issue) == pytest.approx(0.40)
    issue_ucc = issue.model_copy(
        update={"flags": {**issue.flags, "commitment_unconditionally_cancellable": True}}
    )
    assert R.ccf(issue_ucc) == pytest.approx(0.10)
    trade = issue.model_copy(update={"obs_category": OBSCategory.SHORT_TERM_TRADE_LC})
    assert R.ccf(trade) == pytest.approx(0.20)
    assert R.ccf(exp(AssetClass.CORPORATE)) == 0.0
    missing = SAExposure(
        exposure_id="x", asset_class=AssetClass.CORPORATE, off_balance_notional=1.0
    )
    assert R.ccf(missing) == 1.0


# =========================================================================
#  Credit Risk Mitigation (CRR) Part
# =========================================================================

HAIRCUT_CELLS = [
    ("SOV_CQS1_LE1Y", 0.707, 0.5, 0.354),
    ("SOV_CQS1_1_3Y", 2.828, 2, 1.414),
    ("SOV_CQS1_3_5Y", 2.828, 2, 1.414),
    ("SOV_CQS1_5_10Y", 5.657, 4, 2.828),
    ("SOV_CQS1_GT10Y", 5.657, 4, 2.828),
    ("SOV_CQS23_LE1Y", 1.414, 1, 0.707),
    ("SOV_CQS23_1_3Y", 4.243, 3, 2.121),
    ("SOV_CQS23_3_5Y", 4.243, 3, 2.121),
    ("SOV_CQS23_5_10Y", 8.485, 6, 4.243),
    ("SOV_CQS23_GT10Y", 8.485, 6, 4.243),
    ("SOV_CQS4_ALL", 21.213, 15, 10.607),
    ("OTHER_CQS1_LE1Y", 1.414, 1, 0.707),
    ("OTHER_CQS1_1_3Y", 4.243, 3, 2.121),
    ("OTHER_CQS1_3_5Y", 5.657, 4, 2.828),
    ("OTHER_CQS1_5_10Y", 8.485, 6, 4.243),
    ("OTHER_CQS1_GT10Y", 16.971, 12, 8.485),
    ("OTHER_CQS23_LE1Y", 2.828, 2, 1.414),
    ("OTHER_CQS23_1_3Y", 5.657, 4, 2.828),
    ("OTHER_CQS23_3_5Y", 8.485, 6, 4.243),
    ("OTHER_CQS23_5_10Y", 16.971, 12, 8.485),
    ("OTHER_CQS23_GT10Y", 28.284, 20, 14.142),
    ("SEC_CQS1_LE1Y", 2.828, 2, 1.414),
    ("SEC_CQS1_1_3Y", 11.314, 8, 5.657),
    ("SEC_CQS1_3_5Y", 11.314, 8, 5.657),
    ("SEC_CQS1_5_10Y", 22.627, 16, 11.314),
    ("SEC_CQS1_GT10Y", 22.627, 16, 11.314),
    ("SEC_CQS23_LE1Y", 5.657, 4, 2.828),
    ("SEC_CQS23_1_3Y", 16.971, 12, 8.485),
    ("SEC_CQS23_3_5Y", 16.971, 12, 8.485),
    ("SEC_CQS23_5_10Y", 33.941, 24, 16.971),
    ("SEC_CQS23_GT10Y", 33.941, 24, 16.971),
    ("SOV_ST_CQS1", 0.707, 0.5, 0.354),
    ("SOV_ST_CQS23", 1.414, 1, 0.707),
    ("OTHER_ST_CQS1", 1.414, 1, 0.707),
    ("OTHER_ST_CQS23", 2.828, 2, 1.414),
    ("SEC_ST_CQS1", 2.828, 2, 1.414),
    ("SEC_ST_CQS23", 5.657, 4, 2.828),
    ("MAIN_INDEX_EQUITY", 28.284, 20, 14.142),
    ("OTHER_LISTED_EQUITY", 42.426, 30, 21.213),
    ("CASH", 0, 0, 0),
    ("GOLD", 28.284, 20, 14.142),
]


@pytest.mark.parametrize("key,h20,h10,h5", HAIRCUT_CELLS)
def test_haircut_table(key: str, h20: float, h10: float, h5: float) -> None:
    assert cr.supervisory_haircut(key, 20) == pytest.approx(h20 / 100)
    assert cr.supervisory_haircut(key, 10) == pytest.approx(h10 / 100)
    assert cr.supervisory_haircut(key, 5) == pytest.approx(h5 / 100)
    # square-root-of-time consistency of the table itself (Art 226(2))
    assert cr.scale_haircut(h10 / 100, 20, 10) == pytest.approx(h20 / 100, abs=1e-5)


def test_haircut_table_complete() -> None:
    assert len(p.SUPERVISORY_HAIRCUTS) == len(HAIRCUT_CELLS)


@pytest.mark.parametrize("days,expected", [(20, 11.314), (10, 8), (5, 5.657)])
def test_fx_haircut_table_4(days: int, expected: float) -> None:
    assert p.FX_MISMATCH_HAIRCUT[days] == pytest.approx(expected / 100)


def test_haircut_revaluation_scaling() -> None:
    # Art 226(1): H = Hm sqrt((NR + Tm - 1)/Tm); 10-day 4%, revalued every 5 days -> 4% sqrt(14/10)
    assert cr.supervisory_haircut("SOV_CQS1_5_10Y", 10, 5) == pytest.approx(0.04 * math.sqrt(1.4))


def test_fccm_formula_worked_example() -> None:
    # E = 100, HE = 0, C = 50, HC = 4%, Hfx = 8%: E* = 100 - 50 x 0.88 = 56
    assert cr.fccm_exposure(100, 50, 0.0, 0.04, 0.08) == pytest.approx(56.0)
    assert cr.fccm_exposure(10, 50, 0.0, 0.0, 0.0) == 0.0


def test_fccm_applied_to_exposure() -> None:
    # Unrated corporate 100 drawn, collateral 50 of CQS1 sovereign 5-10y bonds,
    # 20-day secured lending
    e = exp(
        AssetClass.CORPORATE,
        100.0,
        financial_collateral_value=50.0,
        collateral_haircut_class="SOV_CQS1_5_10Y",
    )
    res = R.risk_weight(e)
    assert res.exposure_amount == pytest.approx(100 - 50 * (1 - 0.05657))
    repo = e.model_copy(
        update={"flags": {"repo_style": True, "collateral_currency_mismatch": True}}
    )
    assert R.risk_weight(repo).exposure_amount == pytest.approx(100 - 50 * (1 - 0.02828 - 0.05657))
    unknown = e.model_copy(update={"collateral_haircut_class": "NOPE"})
    assert R.risk_weight(unknown).exposure_amount == pytest.approx(100.0)


def test_fccm_off_balance_then_ccf() -> None:
    # Art 228(1): E* for the off-balance item, then the CF;
    # cash collateral 30, drawn 20, undrawn 50 at 40%
    e = SAExposure(
        exposure_id="f",
        asset_class=AssetClass.CORPORATE,
        on_balance_amount=20.0,
        off_balance_notional=50.0,
        obs_category=OBSCategory.COMMITMENT_OTHER,
        financial_collateral_value=30.0,
        collateral_haircut_class="CASH",
    )
    assert R.risk_weight(e).exposure_amount == pytest.approx(0.0 + 0.40 * 40.0)


@pytest.mark.parametrize(
    "t,big_t,expected",
    [
        (5, 5, 100.0),
        (2.25, 5, 100 * 2.0 / 4.75),
        (1.0, 10, 100 * 0.75 / 4.75),
        (0.2, 3, 0.0),
        (3, 2, 100.0),
    ],
)
def test_maturity_mismatch(t: float, big_t: float, expected: float) -> None:
    assert cr.maturity_mismatch_adjust(100.0, t, big_t) == pytest.approx(expected)


def test_guarantee_substitution_worked_example() -> None:
    # Unrated corporate 100, 60 guaranteed by a CQS1 institution (20%):
    # RW = 0.4 x 100% + 0.6 x 20% = 52%
    e = exp(
        AssetClass.CORPORATE,
        100.0,
        guarantee_amount=60.0,
        guarantor_asset_class=AssetClass.BANK,
        guarantor_rating=RatingBucket.AAA_TO_AA_MINUS,
    )
    assert rw(e) == pytest.approx(0.52)
    fx = e.model_copy(update={"flags": {"guarantee_currency_mismatch": True}})
    assert rw(fx) == pytest.approx(
        0.4 + 0.6 * 0.92 * 0.0 + (0.6 - 0.6 * 0.92) * 1.0 + 0.6 * 0.92 * 0.2
    )
    cd = e.model_copy(update={"flags": {"cd_without_restructuring": True}})
    assert rw(cd) == pytest.approx(1 - 0.36 + 0.36 * 0.2)


def test_guarantee_uk_sovereign() -> None:
    e = exp(
        AssetClass.CORPORATE,
        100.0,
        guarantee_amount=100.0,
        guarantor_asset_class=AssetClass.SOVEREIGN,
        domestic_currency_funded=True,
        flags={"guarantor_uk_central_government_or_boe": True},
    )
    assert rw(e) == pytest.approx(0.0)


def test_guarantee_not_applied_when_worse() -> None:
    e = exp(
        AssetClass.CORPORATE,
        100.0,
        rating=RatingBucket.AAA_TO_AA_MINUS,
        guarantee_amount=100.0,
        guarantor_asset_class=AssetClass.CORPORATE,
    )
    assert rw(e) == pytest.approx(0.20)


def test_credit_rwa_aggregation() -> None:
    res = R.credit_rwa([exp(AssetClass.CORPORATE, 100.0), exp(AssetClass.RETAIL_REGULATORY, 50.0)])
    assert res.total_rwa == pytest.approx(100.0 + 37.5)
    assert res.total_exposure == pytest.approx(150.0)
    assert res.density == pytest.approx(137.5 / 150.0)
    assert len(res.line_items) == 2


# =========================================================================
#  Operational Risk Part
# =========================================================================


def op_inputs(**kw: list[float]) -> OpRiskInputs:
    """Op-risk inputs with zero defaults."""
    zero = [0.0, 0.0, 0.0]
    base = dict(
        interest_income=zero,
        interest_expense=zero,
        interest_earning_assets=zero,
        dividend_income=zero,
        fee_income=zero,
        fee_expense=zero,
        other_operating_income=zero,
        other_operating_expense=zero,
        net_pnl_trading_book=zero,
        net_pnl_banking_book=zero,
    )
    base.update(kw)
    return OpRiskInputs(**base)


@pytest.mark.parametrize(
    "bi,expected",
    [
        (500.0, 60.0),
        (880.0, 105.6),
        (10_000.0, 105.6 + 9_120 * 0.15),
        (26_000.0, 105.6 + 25_120 * 0.15),
        (30_000.0, 105.6 + 25_120 * 0.15 + 4_000 * 0.18),
    ],
)
def test_bic_buckets(bi: float, expected: float) -> None:
    assert orisk.business_indicator_component(bi) == pytest.approx(expected)


def test_business_indicator_components() -> None:
    inputs = op_inputs(
        interest_income=[1000.0, 1100.0, 1200.0],
        interest_expense=[400.0, 500.0, 1300.0],
        interest_earning_assets=[30_000.0, 30_000.0, 30_000.0],
        dividend_income=[10.0, 20.0, 30.0],
        fee_income=[300.0, 300.0, 300.0],
        fee_expense=[100.0, 400.0, 100.0],
        other_operating_income=[50.0, 50.0, 50.0],
        other_operating_expense=[20.0, 20.0, 80.0],
        net_pnl_trading_book=[100.0, -200.0, 300.0],
        net_pnl_banking_book=[-30.0, 30.0, 0.0],
    )
    # ILDC: avg|NII| = (600 + 600 + 100)/3 = 433.33; cap 2.25% x 30,000 = 675; + avg DI 20
    assert orisk.interest_leases_dividend_component(inputs) == pytest.approx(1300 / 3 + 20)
    # SC: max(50, 40) + max(300, 200) = 350
    assert orisk.services_component(inputs) == pytest.approx(350.0)
    # FC: (100 + 200 + 300)/3 + (30 + 30 + 0)/3 = 200 + 20
    assert orisk.financial_component(inputs) == pytest.approx(220.0)
    res = R.operational_risk(inputs)
    bi = 1300 / 3 + 20 + 350 + 220
    assert res.business_indicator == pytest.approx(bi)
    bic = 880.0 * 0.12 + (bi - 880.0) * 0.15  # BI of ~1,023 crosses the GBP 0.88bn bucket
    assert res.bic == pytest.approx(bic)
    assert res.ilm == 1.0
    assert res.loss_component is None
    assert res.rwa == pytest.approx(12.5 * bic)


def test_ildc_cap_binds() -> None:
    inputs = op_inputs(
        interest_income=[500.0] * 3,
        interest_expense=[0.0] * 3,
        interest_earning_assets=[10_000.0] * 3,
    )
    assert orisk.interest_leases_dividend_component(inputs) == pytest.approx(225.0)


def test_ilm_is_one_regardless_of_losses() -> None:
    inputs = op_inputs(fee_income=[1000.0] * 3)
    lossy = inputs.model_copy(update={"annual_operational_losses": [5000.0] * 10})
    assert R.operational_risk(lossy).capital == pytest.approx(R.operational_risk(inputs).capital)
    assert pytest.approx(0.02) == p.OPRISK_LOSS_THRESHOLD_GBP_M


# =========================================================================
#  Output floor -- Art 92
# =========================================================================


@pytest.mark.parametrize(
    "year,x", [(2026, 0.0), (2027, 0.60), (2028, 0.65), (2029, 0.70), (2030, 0.725), (2040, 0.725)]
)
def test_floor_schedule(year: int, x: float) -> None:
    assert of.floor_factor(year) == pytest.approx(x)


def test_floor_without_transitional_election() -> None:
    assert of.floor_factor(2027, use_transitional=False) == pytest.approx(0.725)


def test_output_floor_binding_and_not() -> None:
    res = R.output_floor(600.0, 1000.0, 2030)
    assert res.applies and res.floored_rwa == pytest.approx(725.0)
    assert res.add_on == pytest.approx(125.0)
    res27 = R.output_floor(600.0, 1000.0, 2027)
    assert res27.floored_rwa == pytest.approx(600.0) and res27.add_on == 0.0
    assert not R.output_floor(600.0, 1000.0, 2026).applies


def test_output_floor_scope_and_of_adj() -> None:
    out = UKRegime(output_floor_in_scope=False).output_floor(600.0, 1000.0, 2030)
    assert not out.applies and out.floored_rwa == 600.0
    # OF-ADJ = 12.5 (IRB T2 5 - IRB CET1 2 - GCRA min(20, 1.25% x 800 = 10) + SA T2 1)
    #        = 12.5 x -6 = -75
    assert of.of_adj(5.0, 2.0, 20.0, 1.0, s_trea_credit_rwea=800.0) == pytest.approx(-75.0)
    res = R.output_floor_with_adjustments(
        600.0,
        1000.0,
        2030,
        irb_t2=5.0,
        irb_cet1=2.0,
        gcra=20.0,
        sa_t2=1.0,
        s_trea_credit_rwea=800.0,
    )
    assert res.floored_rwa == pytest.approx(650.0)


# =========================================================================
#  Capital stack
# =========================================================================


def test_capital_requirements() -> None:
    cap = R.capital_requirements(0.01, 0.02, 0.005)
    assert (cap.cet1_minimum, cap.tier1_minimum, cap.total_capital_minimum) == (0.045, 0.06, 0.08)
    assert cap.conservation_buffer == pytest.approx(0.025)
    assert cap.combined_buffer == pytest.approx(0.025 + 0.02 + 0.01 + 0.005)
    assert cap.cet1_requirement == pytest.approx(0.045 + 0.06)
    assert cap.leverage_buffer == pytest.approx(0.005)
    assert "TODO: VERIFY" in cap.citations["conservation_buffer"]
    with pytest.raises(ValueError):
        R.capital_requirements(2.0)
    with pytest.raises(ValueError):
        R.capital_requirements(-0.01)


# =========================================================================
#  SA-CCR -- CCR Part Art 274
# =========================================================================


def ns(**kw: object) -> SACCRNettingSetInput:
    """Netting set with RC 10, add-on 20."""
    base: dict[str, object] = dict(netting_set_id="n", replacement_cost=10.0, aggregate_addon=20.0)
    base.update(kw)
    return SACCRNettingSetInput(**base)  # type: ignore[arg-type]


def test_saccr_alpha_variants() -> None:
    assert R.saccr_ead(ns()).ead == pytest.approx(1.4 * 30.0)
    assert R.saccr_ead(ns(counterparty_is_nonfinancial=True)).ead == pytest.approx(30.0)
    assert R.saccr_ead(ns(counterparty_is_pension_scheme=True)).alpha == 1.0
    assert R.saccr_ead(ns(flags={"pension_compensation_entity": True})).alpha == 1.0


def test_saccr_multiplier() -> None:
    assert saccr.multiplier(10.0, 0.0, 20.0) == 1.0
    m = saccr.multiplier(-10.0, 0.0, 20.0)
    assert m == pytest.approx(0.05 + 0.95 * math.exp(-10.0 / (2 * 0.95 * 20.0)))
    assert saccr.multiplier(-1e9, 0.0, 1.0) == pytest.approx(0.05)
    assert saccr.multiplier(0.0, 0.0, 0.0) == 1.0


@pytest.mark.parametrize("year,share", [(2027, 0.60), (2028, 0.40), (2029, 0.20), (2030, 0.0)])
def test_saccr_alpha_addon_transitional(year: int, share: float) -> None:
    net = ns(counterparty_is_nonfinancial=True, flags={"legacy_pre_2027_trades": True})
    res = saccr.saccr_exposure(net, year=year, alpha_addon=12.0)
    assert res.ead == pytest.approx(30.0 + share * 12.0)
    stopped = ns(
        counterparty_is_nonfinancial=True,
        flags={"legacy_pre_2027_trades": True, "cva_transitional_applied": False},
    )
    assert saccr.saccr_exposure(stopped, year=year, alpha_addon=12.0).ead == pytest.approx(30.0)


def test_saccr_alpha_addon_default_approximation() -> None:
    net = ns(counterparty_is_nonfinancial=True, flags={"legacy_pre_2027_trades": True})
    assert saccr.saccr_exposure(net, year=2027).ead == pytest.approx(30.0 + 0.6 * 0.4 * 30.0)


# =========================================================================
#  CVA Risk Part
# =========================================================================

CVA_CELLS = [
    ("SOVEREIGN", 0.005, 0.020),
    ("LOCAL_GOVERNMENT", 0.010, 0.040),
    ("FINANCIAL", 0.050, 0.120),
    ("PENSION_FUND", 0.035, 0.085),
    ("BASIC_MATERIALS", 0.030, 0.070),
    ("CONSUMER", 0.030, 0.085),
    ("TECHNOLOGY", 0.020, 0.055),
    ("HEALTHCARE", 0.015, 0.050),
    ("OTHER", 0.050, 0.120),
]


@pytest.mark.parametrize("sector,ig,hy", CVA_CELLS)
def test_ba_cva_risk_weight_table(sector: str, ig: float, hy: float) -> None:
    assert cva.risk_weight(sector, "IG") == pytest.approx(ig)
    assert cva.risk_weight(sector, "HY_NR") == pytest.approx(hy)
    assert cva.risk_weight(sector, "NR") == pytest.approx(hy)


def test_ba_cva_constants() -> None:
    assert (p.BA_CVA_DS, p.BA_CVA_RHO, p.BA_CVA_BETA) == (0.65, 0.50, 0.25)
    assert p.BA_CVA_HEDGE_CORRELATION == {
        "DIRECT": 1.0,
        "LEGALLY_RELATED": 0.8,
        "SECTOR_REGION": 0.5,
    }
    assert cva.discount_factor(2.0) == pytest.approx((1 - math.exp(-0.1)) / 0.1)
    assert cva.discount_factor(2.0, imm=True) == 1.0


def test_ba_cva_reduced_worked_example() -> None:
    cps = [
        {"id": "A", "ead": 100.0, "maturity": 2.0, "sector": "FINANCIAL", "credit_quality": "IG"},
        {
            "id": "B",
            "ead": 50.0,
            "maturity": 5.0,
            "sector": "TECHNOLOGY",
            "credit_quality": "HY_NR",
        },
    ]
    df2, df5 = cva.discount_factor(2.0), cva.discount_factor(5.0)
    s_a = 0.05 / 1.4 * 2.0 * 100.0 * df2
    s_b = 0.055 / 1.4 * 5.0 * 50.0 * df5
    kr = math.sqrt((0.5 * (s_a + s_b)) ** 2 + 0.75 * (s_a**2 + s_b**2))
    out = R.ba_cva_capital(cps)
    assert out["k_reduced"] == pytest.approx(kr)
    assert out["k"] == pytest.approx(0.65 * kr)
    assert out["rwa"] == pytest.approx(12.5 * 0.65 * kr)


def test_ba_cva_pension_alpha_one() -> None:
    cp = {"ead": 100.0, "maturity": 1.0, "sector": "PENSION_FUND", "credit_quality": "IG"}
    out = cva.ba_cva([cp])
    s = 0.035 / 1.0 * 1.0 * 100.0 * cva.discount_factor(1.0)
    assert out["k_reduced"] == pytest.approx(s)  # single name: sqrt(0.25 s^2 + 0.75 s^2) = s


def test_ba_cva_full_with_hedge() -> None:
    cp = {
        "id": "A",
        "ead": 100.0,
        "maturity": 2.0,
        "sector": "FINANCIAL",
        "credit_quality": "IG",
        "hedge_notional": 40.0,
        "hedge_maturity": 2.0,
        "hedge_relation": "LEGALLY_RELATED",
    }
    out = cva.ba_cva([cp], hedged=True)
    df = cva.discount_factor(2.0)
    s = 0.05 / 1.4 * 2.0 * 100.0 * df
    term = 0.05 * 2.0 * 40.0 * df
    net = s - 0.8 * term
    kh = math.sqrt((0.5 * net) ** 2 + 0.75 * net**2 + (1 - 0.64) * term**2)
    assert out["k_hedged"] == pytest.approx(kh)
    assert out["k_full"] == pytest.approx(0.25 * s + 0.75 * kh)
    assert out["k"] == pytest.approx(0.65 * (0.25 * s + 0.75 * kh))
    # no hedge supplied -> full falls back to reduced
    assert cva.ba_cva([{**cp, "hedge_notional": 0.0}], hedged=True)["k_full"] == pytest.approx(s)


def test_ba_cva_index_hedge() -> None:
    idx = cva.IndexHedge(notional=50.0, maturity=3.0, constituent_rws=(0.05, 0.03))
    assert idx.rw() == pytest.approx(0.7 * 0.04)
    cp = {"id": "A", "ead": 100.0, "maturity": 2.0, "sector": "FINANCIAL", "credit_quality": "IG"}
    out = R.ba_cva_capital_with_index_hedges([cp], [idx])
    s = 0.05 / 1.4 * 2.0 * 100.0 * cva.discount_factor(2.0)
    ih = 0.028 * 3.0 * 50.0 * cva.discount_factor(3.0)
    assert out["k_hedged"] == pytest.approx(math.sqrt((0.5 * s - ih) ** 2 + 0.75 * s**2))


def test_cva_alternative_approach() -> None:
    assert cva.alternative_approach(12.0, 87_999.0) == pytest.approx(12.0)
    assert cva.alternative_approach(12.0, 88_000.0) is None
    assert cva.alternative_approach(12.0, 1.0, sa_cva_permission=True) is None


@pytest.mark.parametrize("year,cap", [(2027, 0.70), (2028, 0.80), (2029, 0.90)])
def test_cva_transitional_scalars(year: int, cap: float) -> None:
    # all legacy: legacy ratio 1 -> omega_bar = max(cap, 1 - (5-t)/5 * (1-cap)/0.5)
    t = {2027: 2, 2028: 3, 2029: 4}[year]
    w_bar = cva.intermediate_discount_scalar(year, 10.0, 0.0)
    assert w_bar == pytest.approx(max(cap, 1 - (5 - t) / 5 * (1 - cap) / 0.5))
    assert cva.intermediate_discount_scalar(year, 10.0, 10.0) == pytest.approx(1.0)
    assert cva.final_discount_scalar(year, 10.0, 0.0, 20.0) == pytest.approx(
        max(w_bar, (10 * w_bar + 10) / 20)
    )
    assert cva.intermediate_discount_scalar(2030, 10.0, 0.0) == 1.0


# =========================================================================
#  End-to-end sanity
# =========================================================================


def test_every_asset_class_assigns() -> None:
    for ac in AssetClass:
        res = R.risk_weight(exp(ac, 10.0, property_value=100.0))
        assert res.jurisdiction is Jurisdiction.UK
        assert 0.0 <= res.risk_weight <= 12.5
        assert res.citation
