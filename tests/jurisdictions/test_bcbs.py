"""Tests for the BCBS Basel Framework regime (src/jurisdictions/bcbs).

Every table cell transcribed in ``params.py`` is asserted against the value
read from the Basel Framework text (parametrized), together with
hand-computed worked examples, transitional schedules, band boundaries and
protocol conformance.

References:
    - Basel Framework CRE20-CRE22, CRE52, CRE90, MAR50, OPE25, RBC20, RBC30,
      RBC40, RBC90, LEV20, LEV40, SCO40
    - BCBS d424 (Dec 2017)
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    Jurisdiction,
    OBSCategory,
    OpRiskInputs,
    PFPhase,
    RatingBucket,
    RealEstateTreatment,
    RegimeCalculator,
    SACCRNettingSetInput,
    SAExposure,
    SCRAGrade,
    ShortTermRating,
)
from src.jurisdictions.bcbs import BCBSOptions, BCBSRegime, cva, saccr
from src.jurisdictions.bcbs import capital_stack as cs
from src.jurisdictions.bcbs import credit_risk as cr
from src.jurisdictions.bcbs import operational_risk as opr
from src.jurisdictions.bcbs import output_floor as of
from src.jurisdictions.bcbs import params as p

R = RatingBucket
AAA, A, BBB, BB, B, CCC, UR = (R.AAA_TO_AA_MINUS, R.A_PLUS_TO_A_MINUS, R.BBB_PLUS_TO_BBB_MINUS,
                               R.BB_PLUS_TO_BB_MINUS, R.B_PLUS_TO_B_MINUS, R.BELOW_B_MINUS,
                               R.UNRATED)
NO_RATINGS = BCBSOptions(external_ratings_allowed=False)


def exp(asset_class: AssetClass, **kw: Any) -> SAExposure:
    """Build an exposure with a $100M drawn balance unless overridden."""
    kw.setdefault("on_balance_amount", 100.0)
    return SAExposure(exposure_id="t", asset_class=asset_class, **kw)


def rw(e: SAExposure, opts: BCBSOptions | None = None) -> float:
    """Effective risk weight through the full regime path."""
    return BCBSRegime(opts).risk_weight(e).risk_weight


# =========================================================================
#  Protocol conformance
# =========================================================================

def test_protocol_conformance() -> None:
    regime = BCBSRegime()
    assert isinstance(regime, RegimeCalculator)
    assert regime.jurisdiction is Jurisdiction.BCBS
    assert "CRE20" in regime.legal_basis


def test_every_asset_class_assigns_a_weight() -> None:
    regime = BCBSRegime()
    for ac in AssetClass:
        res = regime.risk_weight(exp(ac))
        assert res.risk_weight >= 0
        assert res.citation
        assert res.jurisdiction is Jurisdiction.BCBS


# =========================================================================
#  CRE20 tables -- every cell
# =========================================================================

@pytest.mark.parametrize("rating,expected", [
    (AAA, 0.0), (A, 0.20), (BBB, 0.50), (BB, 1.0), (B, 1.0), (CCC, 1.50), (UR, 1.0)])
def test_sovereign_table1(rating: RatingBucket, expected: float) -> None:
    assert p.SOVEREIGN_RW[rating] == expected
    assert rw(exp(AssetClass.SOVEREIGN, rating=rating)) == pytest.approx(expected)


@pytest.mark.parametrize("score,expected", [
    (0, 0.0), (1, 0.0), (2, 0.20), (3, 0.50), (4, 1.0), (5, 1.0), (6, 1.0), (7, 1.50)])
def test_sovereign_eca_table2(score: int, expected: float) -> None:
    assert p.ECA_SCORE_RW[score] == expected
    assert rw(exp(AssetClass.SOVEREIGN, oecd_crc=score),
              BCBSOptions(use_eca_scores=True)) == pytest.approx(expected)


def test_sovereign_supranational_and_domestic_discretion() -> None:
    assert rw(exp(AssetClass.SOVEREIGN, rating=CCC,
                  flags={"is_supranational_zero_rw": True})) == 0.0
    opts = BCBSOptions(domestic_sovereign_rw=0.0)
    assert rw(exp(AssetClass.SOVEREIGN, rating=BBB, domestic_currency_funded=True), opts) == 0.0
    assert rw(exp(AssetClass.SOVEREIGN, rating=BBB), opts) == 0.50


@pytest.mark.parametrize("rating,expected", [
    (AAA, 0.20), (A, 0.50), (BBB, 1.0), (BB, 1.0), (B, 1.0), (CCC, 1.50), (UR, 1.0)])
def test_pse_option1_table3(rating: RatingBucket, expected: float) -> None:
    assert p.PSE_OPTION1_RW[rating] == expected
    assert rw(exp(AssetClass.PSE, sovereign_rating=rating, rating=AAA)) == pytest.approx(expected)


@pytest.mark.parametrize("rating,expected", [
    (AAA, 0.20), (A, 0.50), (BBB, 0.50), (BB, 1.0), (B, 1.0), (CCC, 1.50), (UR, 0.50)])
def test_pse_option2_table4(rating: RatingBucket, expected: float) -> None:
    assert p.PSE_OPTION2_RW[rating] == expected
    assert rw(exp(AssetClass.PSE, rating=rating, sovereign_rating=CCC),
              BCBSOptions(pse_option=2)) == pytest.approx(expected)


def test_pse_as_sovereign() -> None:
    assert rw(exp(AssetClass.PSE, sovereign_rating=AAA),
              BCBSOptions(pse_treated_as_sovereign=True)) == 0.0


@pytest.mark.parametrize("rating,expected", [
    (AAA, 0.20), (A, 0.30), (BBB, 0.50), (BB, 1.0), (B, 1.0), (CCC, 1.50), (UR, 0.50)])
def test_mdb_table5(rating: RatingBucket, expected: float) -> None:
    assert p.MDB_RW[rating] == expected
    assert rw(exp(AssetClass.MDB, rating=rating)) == pytest.approx(expected)


def test_mdb_zero_and_no_ratings() -> None:
    assert rw(exp(AssetClass.MDB, rating=BBB, flags={"is_zero_rw_mdb": True})) == 0.0
    assert rw(exp(AssetClass.MDB, rating=AAA), NO_RATINGS) == 0.50


@pytest.mark.parametrize("rating,base,short", [
    (AAA, 0.20, 0.20), (A, 0.30, 0.20), (BBB, 0.50, 0.20), (BB, 1.0, 0.50),
    (B, 1.0, 0.50), (CCC, 1.50, 1.50)])
def test_bank_ecra_table6(rating: RatingBucket, base: float, short: float) -> None:
    assert p.BANK_ECRA_BASE_RW[rating] == base
    assert p.BANK_ECRA_SHORT_TERM_RW[rating] == short
    assert rw(exp(AssetClass.BANK, rating=rating)) == pytest.approx(base)
    assert rw(exp(AssetClass.BANK, rating=rating, original_maturity_months=3)) == pytest.approx(
        short)


@pytest.mark.parametrize("grade,base,short", [
    (SCRAGrade.A, 0.40, 0.20), (SCRAGrade.B, 0.75, 0.50), (SCRAGrade.C, 1.50, 1.50)])
def test_bank_scra_table7(grade: SCRAGrade, base: float, short: float) -> None:
    assert p.BANK_SCRA_BASE_RW[grade] == base
    assert p.BANK_SCRA_SHORT_TERM_RW[grade] == short
    assert rw(exp(AssetClass.BANK, scra_grade=grade)) == pytest.approx(base)
    assert rw(exp(AssetClass.BANK, scra_grade=grade, original_maturity_months=2)) == \
        pytest.approx(short)
    # non-ratings jurisdictions apply SCRA even to rated banks (CRE20.21)
    assert rw(exp(AssetClass.BANK, scra_grade=grade, rating=AAA), NO_RATINGS) == pytest.approx(base)


def test_bank_scra_enhanced_30pct_and_default_grade() -> None:
    assert p.BANK_SCRA_GRADE_A_ENHANCED_RW == 0.30
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.A, scra_grade_a_enhanced=True)) == 0.30
    # enhanced flag is irrelevant outside Grade A
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.B, scra_grade_a_enhanced=True)) == 0.75
    assert rw(exp(AssetClass.BANK)) == 0.75   # CRE20.27 residual Grade B


@pytest.mark.parametrize("months,trade,short", [
    (3.0, False, True), (3.01, False, False), (6.0, True, True), (6.01, True, False),
    (6.0, False, False), (None, False, False)])
def test_bank_short_term_cutoffs(months: float | None, trade: bool, short: bool) -> None:
    e = exp(AssetClass.BANK, scra_grade=SCRAGrade.A, original_maturity_months=months,
            is_trade_related=trade)
    assert cr.is_short_term_bank_exposure(e) is short
    assert rw(e) == (0.20 if short else 0.40)


def test_bank_scra_sovereign_floor() -> None:
    e = exp(AssetClass.BANK, scra_grade=SCRAGrade.A, sovereign_rating=CCC,
            flags={"foreign_currency_exposure": True})
    assert rw(e) == 1.50                                       # CRE20.32 floor
    trade = e.model_copy(update={"is_trade_related": True, "original_maturity_months": 6})
    assert rw(trade) == 0.20                                   # short-term trade exempt
    assert rw(e.model_copy(update={"flags": {}})) == 0.40       # local currency: no floor


def test_bank_due_diligence_uplift() -> None:
    assert rw(exp(AssetClass.BANK, rating=A, flags={"due_diligence_uplift": True})) == 0.50
    assert rw(exp(AssetClass.BANK, rating=CCC, flags={"due_diligence_uplift": True})) == 1.50


@pytest.mark.parametrize("rating,expected", [
    (AAA, 0.10), (A, 0.20), (BBB, 0.20), (BB, 0.50), (B, 0.50), (CCC, 1.00)])
def test_covered_bond_rated_table8(rating: RatingBucket, expected: float) -> None:
    assert p.COVERED_BOND_RATED_RW[rating] == expected
    assert rw(exp(AssetClass.COVERED_BOND, rating=rating, covered_bond_rated=True)) == \
        pytest.approx(expected)


@pytest.mark.parametrize("issuer,expected", [
    (0.20, 0.10), (0.30, 0.15), (0.40, 0.20), (0.50, 0.25), (0.75, 0.35), (1.00, 0.50),
    (1.50, 1.00)])
def test_covered_bond_unrated_table9(issuer: float, expected: float) -> None:
    assert p.COVERED_BOND_UNRATED_RW[issuer] == expected


@pytest.mark.parametrize("kw,expected", [
    ({"rating": AAA}, 0.10), ({"rating": A}, 0.15), ({"rating": BBB}, 0.25),
    ({"rating": BB}, 0.50), ({"rating": CCC}, 1.00),
    ({"scra_grade": SCRAGrade.A}, 0.20), ({"scra_grade": SCRAGrade.B}, 0.35),
    ({"scra_grade": SCRAGrade.C}, 1.00),
    ({"scra_grade": SCRAGrade.A, "scra_grade_a_enhanced": True}, 0.15)])
def test_covered_bond_unrated_via_issuer(kw: dict[str, Any], expected: float) -> None:
    assert rw(exp(AssetClass.COVERED_BOND, **kw)) == pytest.approx(expected)


def test_covered_bond_ineligible_is_bank() -> None:
    assert rw(exp(AssetClass.COVERED_BOND, rating=A, covered_bond_rated=True,
                  flags={"covered_bond_ineligible": True})) == 0.30


@pytest.mark.parametrize("rating,expected", [
    (AAA, 0.20), (A, 0.50), (BBB, 0.75), (BB, 1.0), (B, 1.50), (CCC, 1.50), (UR, 1.0)])
def test_corporate_table10(rating: RatingBucket, expected: float) -> None:
    assert p.CORPORATE_RW[rating] == expected
    assert rw(exp(AssetClass.CORPORATE, rating=rating)) == pytest.approx(expected)


def test_corporate_sme_and_no_ratings() -> None:
    assert rw(exp(AssetClass.CORPORATE_SME)) == 0.85                       # unrated SME
    assert rw(exp(AssetClass.CORPORATE_SME, rating=AAA)) == 0.20           # rated SME: Table 10
    assert rw(exp(AssetClass.CORPORATE, rating=AAA), NO_RATINGS) == 1.00   # CRE20.44
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True), NO_RATINGS) == 0.65
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True),
              BCBSOptions(external_ratings_allowed=False,
                          investment_grade_corporate_65=False)) == 1.00
    assert rw(exp(AssetClass.CORPORATE_SME, rating=AAA), NO_RATINGS) == 0.85


@pytest.mark.parametrize("turnover,sme", [(50.0, True), (50.01, False), (None, False)])
def test_sme_threshold(turnover: float | None, sme: bool) -> None:
    e = exp(AssetClass.CORPORATE, annual_turnover=turnover)
    assert cr.is_sme(e) is sme
    assert rw(e) == (0.85 if sme else 1.00)


@pytest.mark.parametrize("st,expected", [
    (ShortTermRating.A1_P1, 0.20), (ShortTermRating.A2_P2, 0.50),
    (ShortTermRating.A3_P3, 1.00), (ShortTermRating.OTHERS, 1.50)])
def test_short_term_rating_table15(st: ShortTermRating, expected: float) -> None:
    assert p.SHORT_TERM_RATING_RW[st] == expected
    assert rw(exp(AssetClass.CORPORATE, short_term_rating=st)) == expected
    assert rw(exp(AssetClass.BANK, short_term_rating=st)) == expected


@pytest.mark.parametrize("phase,expected", [
    (PFPhase.PRE_OPERATIONAL, 1.30), (PFPhase.OPERATIONAL, 1.00),
    (PFPhase.HIGH_QUALITY_OPERATIONAL, 0.80), (None, 1.30)])
def test_project_finance(phase: PFPhase | None, expected: float) -> None:
    assert rw(exp(AssetClass.SPECIALISED_LENDING_PF, pf_phase=phase)) == expected


def test_object_commodity_finance_and_issue_rating() -> None:
    assert rw(exp(AssetClass.SPECIALISED_LENDING_OF)) == 1.00
    assert rw(exp(AssetClass.SPECIALISED_LENDING_CF)) == 1.00
    # issuer ratings must not be used (CRE20.50)
    assert rw(exp(AssetClass.SPECIALISED_LENDING_OF, rating=AAA)) == 1.00
    assert rw(exp(AssetClass.SPECIALISED_LENDING_OF, rating=AAA,
                  flags={"issue_specific_rating": True})) == 0.20
    assert rw(exp(AssetClass.SPECIALISED_LENDING_PF, rating=AAA, pf_phase=PFPhase.OPERATIONAL,
                  flags={"issue_specific_rating": True}), NO_RATINGS) == 1.00


def test_subordinated_debt() -> None:
    assert rw(exp(AssetClass.SUBORDINATED_DEBT)) == 1.50


@pytest.mark.parametrize("et,expected", [
    (EquityType.GENERAL, 2.50), (EquityType.SPECULATIVE_UNLISTED, 4.00),
    (EquityType.LEGISLATIVE_PROGRAMME, 2.50), (EquityType.PUBLICLY_TRADED, 2.50),
    (EquityType.NON_PUBLIC, 2.50), (EquityType.SIGNIFICANT_FI, 2.50), (None, 2.50)])
def test_equity_fully_phased(et: EquityType | None, expected: float) -> None:
    assert rw(exp(AssetClass.EQUITY, equity_type=et)) == expected


def test_equity_legislative_and_commercial_excess() -> None:
    opts = BCBSOptions(legislative_programme_equity_100=True)
    assert rw(exp(AssetClass.EQUITY, equity_type=EquityType.LEGISLATIVE_PROGRAMME), opts) == 1.00
    assert rw(exp(AssetClass.EQUITY,
                  flags={"exceeds_commercial_materiality_threshold": True})) == 12.50
    assert p.COMMERCIAL_ENTITY_INDIVIDUAL_MATERIALITY == 0.15
    assert p.COMMERCIAL_ENTITY_AGGREGATE_MATERIALITY == 0.60


@pytest.mark.parametrize("year,general,speculative", [
    (2022, 1.00, 1.00), (2023, 1.00, 1.00), (2024, 1.30, 1.60), (2025, 1.60, 2.20),
    (2026, 1.90, 2.80), (2027, 2.20, 3.40), (2028, 2.50, 4.00), (2035, 2.50, 4.00)])
def test_equity_phase_in_cre90(year: int, general: float, speculative: float) -> None:
    opts = BCBSOptions(equity_transition_year=year)
    assert rw(exp(AssetClass.EQUITY), opts) == pytest.approx(general)
    assert rw(exp(AssetClass.EQUITY, equity_type=EquityType.SPECULATIVE_UNLISTED), opts) == \
        pytest.approx(speculative)
    # legislative programme (CRE20.59) is outside the phase-in
    opts2 = BCBSOptions(equity_transition_year=year, legislative_programme_equity_100=True)
    assert rw(exp(AssetClass.EQUITY, equity_type=EquityType.LEGISLATIVE_PROGRAMME), opts2) == 1.0


@pytest.mark.parametrize("ac,kw,expected", [
    (AssetClass.RETAIL_REGULATORY, {}, 0.75),
    (AssetClass.RETAIL_TRANSACTOR, {}, 0.45),
    (AssetClass.RETAIL_REGULATORY, {"is_transactor": True}, 0.45),
    (AssetClass.RETAIL_OTHER, {}, 1.00),
    (AssetClass.RETAIL_REGULATORY, {"meets_regulatory_retail_criteria": False}, 1.00),
    (AssetClass.RETAIL_TRANSACTOR, {"meets_regulatory_retail_criteria": False}, 1.00),
    (AssetClass.RETAIL_REGULATORY, {"aggregate_retail_exposure_to_obligor": 1.0}, 0.75),
    (AssetClass.RETAIL_REGULATORY, {"aggregate_retail_exposure_to_obligor": 1.01}, 1.00),
])
def test_retail(ac: AssetClass, kw: dict[str, Any], expected: float) -> None:
    assert rw(exp(ac, **kw)) == expected


@pytest.mark.parametrize("ac,base", [
    (AssetClass.RETAIL_REGULATORY, 0.75), (AssetClass.RETAIL_TRANSACTOR, 0.45),
    (AssetClass.RETAIL_OTHER, 1.00)])
def test_retail_currency_mismatch(ac: AssetClass, base: float) -> None:
    e = exp(ac, currency_matches_borrower_income=False)
    assert rw(e) == pytest.approx(min(base * 1.5, 1.5))
    # SMEs are outside CRE20.92 (individuals only)
    assert rw(e.model_copy(update={"is_sme": True})) == pytest.approx(base)


# -------- Residential real estate --------

@pytest.mark.parametrize("ltv,expected", [
    (0.0, 0.20), (0.50, 0.20), (0.5001, 0.25), (0.60, 0.25), (0.6001, 0.30), (0.80, 0.30),
    (0.8001, 0.40), (0.90, 0.40), (0.9001, 0.50), (1.00, 0.50), (1.0001, 0.70), (1.5, 0.70)])
def test_rre_whole_loan_table11(ltv: float, expected: float) -> None:
    assert cr.band_rw(ltv, p.RRE_WHOLE_LOAN_RW) == expected
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=ltv)) == expected


@pytest.mark.parametrize("ltv,expected", [
    (0.50, 0.30), (0.5001, 0.35), (0.60, 0.35), (0.6001, 0.45), (0.80, 0.45), (0.8001, 0.60),
    (0.90, 0.60), (0.9001, 0.75), (1.00, 0.75), (1.0001, 1.05)])
def test_rre_cash_flow_table12(ltv: float, expected: float) -> None:
    assert cr.band_rw(ltv, p.RRE_CASH_FLOW_RW) == expected
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=ltv, is_cash_flow_dependent=True)) == expected


def test_rre_loan_splitting_worked_example() -> None:
    """CRE20.83 footnote 120: 70,000 loan on 100,000 property -> RWA 22,250."""
    opts = BCBSOptions(residential_re_treatment=RealEstateTreatment.LOAN_SPLITTING)
    res = BCBSRegime(opts).risk_weight(exp(AssetClass.RESIDENTIAL_RE, on_balance_amount=70.0,
                                           property_value=100.0, ltv=0.70))
    assert res.rwa == pytest.approx(0.20 * 55.0 + 0.75 * 15.0)
    assert res.rwa == pytest.approx(22.25)
    # fully within 55%: all at 20%
    low = BCBSRegime(opts).risk_weight(exp(AssetClass.RESIDENTIAL_RE, on_balance_amount=40.0,
                                           property_value=100.0, ltv=0.40))
    assert low.risk_weight == pytest.approx(0.20)
    # property value derived from LTV when not given
    derived = BCBSRegime(opts).risk_weight(exp(AssetClass.RESIDENTIAL_RE, on_balance_amount=70.0,
                                               ltv=0.70))
    assert derived.rwa == pytest.approx(22.25)


def test_rre_other_and_junior_lien_and_mismatch() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False)) == 0.75
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False, is_sme=True)) == 0.85
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False,
                  is_cash_flow_dependent=True)) == 1.50
    # junior lien: 1.25 x base, not in lowest bucket, capped at 75% (CRE20.75 fn 115)
    jl = {"junior_lien": True}
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.45, flags=jl)) == 0.20
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.85, flags=jl)) == pytest.approx(0.50)
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=1.2, flags=jl)) == pytest.approx(0.75)
    # currency mismatch: 1.5x, cap 150%
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.75,
                  currency_matches_borrower_income=False)) == pytest.approx(0.45)
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=1.2, is_cash_flow_dependent=True,
                  currency_matches_borrower_income=False)) == pytest.approx(1.50)
    # missing LTV: highest band
    assert rw(exp(AssetClass.RESIDENTIAL_RE)) == 0.70


# -------- Commercial real estate --------

@pytest.mark.parametrize("ltv,cp_rating,expected", [
    (0.60, UR, 0.60), (0.6001, UR, 1.00), (0.50, AAA, 0.20), (0.70, AAA, 0.20),
    (0.40, BBB, 0.60), (0.90, BBB, 0.75), (0.30, CCC, 0.60), (0.80, CCC, 1.50)])
def test_cre_whole_loan_table13(ltv: float, cp_rating: RatingBucket, expected: float) -> None:
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=ltv, rating=cp_rating)) == expected


def test_cre_counterparty_individual_and_sme() -> None:
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.5,
                  flags={"counterparty_is_individual": True})) == 0.60
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.7,
                  flags={"counterparty_is_individual": True})) == 0.75
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.7, is_sme=True)) == 0.85


@pytest.mark.parametrize("ltv,expected", [
    (0.60, 0.70), (0.6001, 0.90), (0.80, 0.90), (0.8001, 1.10), (2.0, 1.10)])
def test_cre_cash_flow_table14(ltv: float, expected: float) -> None:
    assert cr.band_rw(ltv, p.CRE_CASH_FLOW_RW) == expected
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=ltv, is_cash_flow_dependent=True)) == expected


def test_cre_cf_exemption_loan_splitting_and_other() -> None:
    e = exp(AssetClass.COMMERCIAL_RE, ltv=0.7, is_cash_flow_dependent=True)
    assert rw(e, BCBSOptions(cre_cash_flow_exemption=True)) == 1.00
    split = BCBSOptions(commercial_re_treatment=RealEstateTreatment.LOAN_SPLITTING)
    res = BCBSRegime(split).risk_weight(exp(AssetClass.COMMERCIAL_RE, on_balance_amount=70.0,
                                            property_value=100.0, ltv=0.7))
    assert res.rwa == pytest.approx(0.60 * 55.0 + 1.00 * 15.0)
    assert rw(exp(AssetClass.COMMERCIAL_RE, is_regulatory_real_estate=False, rating=A)) == 0.50
    assert rw(exp(AssetClass.COMMERCIAL_RE, is_regulatory_real_estate=False,
                  is_cash_flow_dependent=True)) == 1.50


def test_land_adc() -> None:
    assert rw(exp(AssetClass.LAND_ADC)) == 1.50
    assert rw(exp(AssetClass.LAND_ADC, is_adc_presold_or_equity_at_risk=True)) == 1.00


# -------- Defaulted and other assets --------

@pytest.mark.parametrize("prov,expected,expected_disc", [
    (0.0, 1.50, 1.50), (0.1999, 1.50, 1.50), (0.20, 1.00, 1.00), (0.4999, 1.00, 1.00),
    (0.50, 1.00, 0.50), (0.9, 1.00, 0.50)])
def test_defaulted_provision_test(prov: float, expected: float, expected_disc: float) -> None:
    e = exp(AssetClass.DEFAULTED, specific_provision_pct=prov)
    assert rw(e) == expected
    assert rw(e, BCBSOptions(defaulted_50pct_discretion=True)) == expected_disc
    # is_defaulted overrides any asset class
    assert rw(exp(AssetClass.CORPORATE, rating=AAA, is_defaulted=True,
                  specific_provision_pct=prov)) == expected


def test_defaulted_rre() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_defaulted=True, ltv=0.4)) == 1.00
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_defaulted=True, is_cash_flow_dependent=True)) == 1.5
    assert rw(exp(AssetClass.DEFAULTED, flags={"defaulted_rre_non_cf": True})) == 1.00


@pytest.mark.parametrize("flag,expected", [
    ("is_cash", 0.0), ("is_gold_bullion", 0.0), ("is_cash_in_collection", 0.20),
    ("is_threshold_deduction_item", 2.50), ("none", 1.00)])
def test_other_assets(flag: str, expected: float) -> None:
    assert rw(exp(AssetClass.OTHER_ASSETS, flags={flag: True})) == expected


# =========================================================================
#  CCFs (CRE20.94-20.101)
# =========================================================================

@pytest.mark.parametrize("cat,expected", [
    (OBSCategory.UNCONDITIONALLY_CANCELLABLE, 0.10), (OBSCategory.COMMITMENT_OTHER, 0.40),
    (OBSCategory.NIF_RUF, 0.50), (OBSCategory.TRANSACTION_RELATED_CONTINGENT, 0.50),
    (OBSCategory.SHORT_TERM_TRADE_LC, 0.20), (OBSCategory.DIRECT_CREDIT_SUBSTITUTE, 1.00),
    (OBSCategory.SECURITIES_LENDING_COLLATERAL, 1.00),
    (OBSCategory.FORWARD_ASSET_PURCHASE, 1.00), (OBSCategory.OTHER_100, 1.00)])
def test_ccf_table(cat: OBSCategory, expected: float) -> None:
    assert p.CCF[cat] == expected
    e = exp(AssetClass.CORPORATE, on_balance_amount=0.0, off_balance_notional=100.0,
            obs_category=cat)
    res = BCBSRegime().risk_weight(e)
    assert res.ccf == expected
    assert res.exposure_amount == pytest.approx(100.0 * expected)
    assert res.rwa == pytest.approx(100.0 * expected * 1.0)


def test_ccf_edge_cases() -> None:
    regime = BCBSRegime()
    # commitment CCF does not depend on maturity (CRE20.98)
    assert regime.ccf(exp(AssetClass.CORPORATE, obs_category=OBSCategory.COMMITMENT_OTHER,
                          commitment_original_maturity_years=0.5)) == 0.40
    # trade LC with maturity of one year or more is outside CRE20.99 (TODO: VERIFY 100%)
    assert regime.ccf(exp(AssetClass.CORPORATE, obs_category=OBSCategory.SHORT_TERM_TRADE_LC,
                          original_maturity_months=11.9)) == 0.20
    assert regime.ccf(exp(AssetClass.CORPORATE, obs_category=OBSCategory.SHORT_TERM_TRADE_LC,
                          original_maturity_months=12)) == 1.00
    # CRE20.101 lower of two CCFs (footnote 128 examples)
    assert regime.ccf(exp(AssetClass.CORPORATE, obs_category=OBSCategory.SHORT_TERM_TRADE_LC,
                          flags={"commitment_to_issue_obs_item": True})) == 0.20
    assert regime.ccf(exp(AssetClass.CORPORATE, obs_category=OBSCategory.DIRECT_CREDIT_SUBSTITUTE,
                          flags={"commitment_unconditionally_cancellable": True})) == 0.10
    assert regime.ccf(exp(AssetClass.CORPORATE, off_balance_notional=10.0)) == 1.00
    assert regime.ccf(exp(AssetClass.CORPORATE)) == 0.0


# =========================================================================
#  CRM (CRE22)
# =========================================================================

HAIRCUT_RATINGS_CELLS: dict[str, dict[str, list[float]]] = {
    "AAA_AA": {"SOV": [0.5, 2, 2, 4, 4], "OTHER": [1, 3, 4, 6, 12], "SEC": [2, 8, 8, 16, 16]},
    "A_BBB": {"SOV": [1, 3, 3, 6, 6], "OTHER": [2, 4, 6, 12, 20], "SEC": [4, 12, 12, 24, 24]},
    "BB": {"SOV": [15, 15, 15, 15, 15]},
}
MATS = ["LE1Y", "1Y_3Y", "3Y_5Y", "5Y_10Y", "GT10Y"]


@pytest.mark.parametrize("key,expected", [
    (f"{iss}_{band}_{m}", vals[i] / 100.0)
    for band, d in HAIRCUT_RATINGS_CELLS.items() for iss, vals in d.items()
    for i, m in enumerate(MATS)])
def test_haircuts_cre22_49(key: str, expected: float) -> None:
    assert p.HAIRCUTS_RATINGS[key] == pytest.approx(expected)


def test_haircuts_cre22_49_other_rows_and_ineligible() -> None:
    assert p.HAIRCUTS_RATINGS["MAIN_INDEX_EQUITY"] == 0.20
    assert p.HAIRCUTS_RATINGS["GOLD"] == 0.20
    assert p.HAIRCUTS_RATINGS["OTHER_LISTED_EQUITY"] == 0.30
    assert p.HAIRCUTS_RATINGS["CASH"] == 0.0
    for m in MATS:   # BB+ to BB-: other issuers / securitisation not eligible
        assert f"OTHER_BB_{m}" not in p.HAIRCUTS_RATINGS
        assert f"SEC_BB_{m}" not in p.HAIRCUTS_RATINGS


HAIRCUT_NO_RATINGS_CELLS: dict[str, list[float]] = {
    "NR_SOV0": [0.5, 2, 2, 4, 4], "NR_SOV20_50": [1, 3, 3, 6, 6],
    "NR_SOV100": [15, 15, 15, 15, 15], "NR_IG": [2, 4, 6, 12, 20], "NR_SEC": [4, 12, 12, 24, 24]}


@pytest.mark.parametrize("key,expected", [
    (f"{col}_{m}", vals[i] / 100.0)
    for col, vals in HAIRCUT_NO_RATINGS_CELLS.items() for i, m in enumerate(MATS)])
def test_haircuts_cre22_50(key: str, expected: float) -> None:
    assert p.HAIRCUTS_NO_RATINGS[key] == pytest.approx(expected)


def test_haircuts_cre22_50_other_rows() -> None:
    assert p.HAIRCUTS_NO_RATINGS["MAIN_INDEX_EQUITY"] == 0.20
    assert p.HAIRCUTS_NO_RATINGS["GOLD"] == 0.20
    assert p.HAIRCUTS_NO_RATINGS["OTHER_LISTED_EQUITY"] == 0.30
    assert p.HAIRCUTS_NO_RATINGS["CASH"] == 0.0
    assert p.HAIRCUTS_NO_RATINGS["OTHER_EXPOSURE_TYPES"] == 0.30
    assert p.HAIRCUT_FX == 0.08
    assert p.HAIRCUT_NON_ELIGIBLE_SFT == 0.30
    assert p.MIN_HOLDING_PERIOD_DAYS == {"REPO_STYLE": 5, "OTHER_CAPITAL_MARKET": 10,
                                         "SECURED_LENDING": 20}


def test_haircut_scaling_cre22_59() -> None:
    assert cr.scale_haircut(0.04, 10) == pytest.approx(0.04)                    # default table
    assert cr.scale_haircut(0.04, 5) == pytest.approx(0.04 * math.sqrt(0.5))     # repo
    assert cr.scale_haircut(0.04, 20) == pytest.approx(0.04 * math.sqrt(2.0))    # secured lending
    assert cr.scale_haircut(0.04, 10, 5) == pytest.approx(0.04 * math.sqrt(14 / 10))


def test_comprehensive_formula_and_basket() -> None:
    # E* = max{0, E(1+He) - C(1-Hc-Hfx)}
    assert cr.comprehensive_exposure(100, 80, 0.0, 0.04, 0.08) == pytest.approx(100 - 80 * 0.88)
    assert cr.comprehensive_exposure(100, 200, 0.0, 0.0, 0.0) == 0.0
    assert cr.comprehensive_exposure(100, 50, 0.02, 0.0, 0.0) == pytest.approx(52.0)
    assert cr.basket_haircut([(0.5, 0.02), (0.5, 0.20)]) == pytest.approx(0.11)


def test_comprehensive_in_risk_weight() -> None:
    e = exp(AssetClass.CORPORATE, financial_collateral_value=60.0,
            collateral_haircut_class="SOV_AAA_AA_5Y_10Y")
    res = BCBSRegime().risk_weight(e)
    hc = 0.04 * math.sqrt(2.0)       # secured lending, 20-day minimum holding period
    assert res.exposure_amount == pytest.approx(100 - 60 * (1 - hc))
    assert res.rwa == pytest.approx(res.exposure_amount * 1.0)
    fx = e.model_copy(update={"flags": {"collateral_currency_mismatch": True, "repo_style": True}})
    res_fx = BCBSRegime().risk_weight(fx)
    s = math.sqrt(0.5)
    assert res_fx.exposure_amount == pytest.approx(100 - 60 * (1 - 0.04 * s - 0.08 * s))
    cash = BCBSRegime().risk_weight(exp(AssetClass.CORPORATE, financial_collateral_value=150.0,
                                        collateral_haircut_class="CASH"))
    assert cash.rwa == 0.0
    inel = BCBSRegime().risk_weight(exp(AssetClass.CORPORATE, financial_collateral_value=50.0,
                                        collateral_haircut_class="OTHER_BB_LE1Y"))
    assert inel.rwa == pytest.approx(100.0)
    # non-ratings jurisdictions use the CRE22.50 table
    nr = BCBSRegime(NO_RATINGS).risk_weight(exp(
        AssetClass.CORPORATE, financial_collateral_value=50.0,
        collateral_haircut_class="NR_SOV100_LE1Y", flags={"capital_market_txn": True}))
    assert nr.exposure_amount == pytest.approx(100 - 50 * 0.85)


def test_simple_approach() -> None:
    assert cr.simple_approach_rwa(100, 60, 0.0, 1.0) == pytest.approx(60 * 0.2 + 40 * 1.0)
    assert cr.simple_approach_rwa(100, 60, 0.0, 1.0, floor_exempt=True) == pytest.approx(40.0)
    assert cr.simple_approach_rwa(100, 160, 0.5, 1.0) == pytest.approx(50.0)
    res = BCBSRegime().risk_weight(exp(AssetClass.CORPORATE, financial_collateral_value=40.0,
                                       collateral_haircut_class="CASH",
                                       flags={"crm_simple_approach": True}))
    assert res.rwa == pytest.approx(60.0)                   # CRE22.39(1) 0% on 40
    sov = BCBSRegime().risk_weight(exp(AssetClass.CORPORATE, financial_collateral_value=50.0,
                                       collateral_haircut_class="SOV_AAA_AA_LE1Y",
                                       flags={"crm_simple_approach": True}))
    assert sov.rwa == pytest.approx(60.0)                   # CRE22.39(2): value x 0.8 at 0%
    eq = BCBSRegime().risk_weight(exp(AssetClass.CORPORATE, financial_collateral_value=50.0,
                                      collateral_haircut_class="OTHER_LISTED_EQUITY",
                                      flags={"crm_simple_approach": True}))
    assert eq.rwa == pytest.approx(100.0)                   # not eligible in simple approach
    assert p.SIMPLE_APPROACH_RW_FLOOR == 0.20
    assert p.SIMPLE_APPROACH_REPO_EXEMPT_RW == 0.10


def test_maturity_mismatch_cre22_13() -> None:
    assert cr.maturity_mismatch_adjust(100, 2.0, 4.0) == pytest.approx(100 * 1.75 / 3.75)
    assert cr.maturity_mismatch_adjust(100, 3.0, 8.0) == pytest.approx(100 * 2.75 / 4.75)
    assert cr.maturity_mismatch_adjust(100, 5.0, 4.0) == 100.0
    assert cr.maturity_mismatch_adjust(100, 0.2, 4.0) == 0.0          # residual < 3 months
    assert cr.maturity_mismatch_adjust(100, 0.5, 4.0, 0.9) == 0.0     # original < 1 year


def test_guarantee_substitution() -> None:
    e = exp(AssetClass.CORPORATE, guarantee_amount=60.0,
            guarantor_asset_class=AssetClass.SOVEREIGN, guarantor_rating=AAA)
    res = BCBSRegime().risk_weight(e)
    assert res.rwa == pytest.approx(40.0)
    fx = e.model_copy(update={"flags": {"guarantee_currency_mismatch": True}})
    assert BCBSRegime().risk_weight(fx).rwa == pytest.approx(100 - 60 * 0.92)
    assert cr.guarantee_after_fx(100.0) == pytest.approx(92.0)
    # bank guarantor (ECRA A: 30%) on a corporate
    bank = exp(AssetClass.CORPORATE, guarantee_amount=100.0,
               guarantor_asset_class=AssetClass.BANK, guarantor_rating=A)
    assert BCBSRegime().risk_weight(bank).rwa == pytest.approx(30.0)
    # guarantor RW not lower: no recognition
    worse = exp(AssetClass.SOVEREIGN, rating=AAA, guarantee_amount=100.0,
                guarantor_asset_class=AssetClass.BANK, guarantor_rating=A)
    assert BCBSRegime().risk_weight(worse).rwa == 0.0
    # unrated corporate guarantor not eligible in ratings jurisdictions
    corp = exp(AssetClass.RETAIL_OTHER, guarantee_amount=100.0,
               guarantor_asset_class=AssetClass.CORPORATE)
    assert BCBSRegime().risk_weight(corp).rwa == pytest.approx(100.0)
    corp_ig = corp.model_copy(update={"flags": {"guarantor_investment_grade": True}})
    assert BCBSRegime(NO_RATINGS).risk_weight(corp_ig).rwa == pytest.approx(65.0)
    # collateral then guarantee on the remaining E*
    both = exp(AssetClass.CORPORATE, financial_collateral_value=50.0,
               collateral_haircut_class="CASH", guarantee_amount=20.0,
               guarantor_asset_class=AssetClass.SOVEREIGN, guarantor_rating=AAA)
    r2 = BCBSRegime().risk_weight(both)
    assert r2.exposure_amount == pytest.approx(50.0)
    assert r2.rwa == pytest.approx(30.0)
    assert cr.cds_without_restructuring(100, 80) == pytest.approx(48.0)


def test_credit_rwa_aggregation() -> None:
    exps = [exp(AssetClass.CORPORATE, rating=A), exp(AssetClass.RETAIL_REGULATORY),
            exp(AssetClass.CORPORATE, rating=AAA)]
    res = BCBSRegime().credit_rwa(exps)
    assert res.total_rwa == pytest.approx(50 + 75 + 20)
    assert res.total_exposure == pytest.approx(300.0)
    assert res.rwa_by_class["CORPORATE"] == pytest.approx(70.0)
    assert res.density == pytest.approx(145 / 300)


# =========================================================================
#  Operational risk (OPE25)
# =========================================================================

def op_inputs(scale: float = 1.0, losses: list[float] | None = None) -> OpRiskInputs:
    """Op-risk inputs in EUR millions."""
    def three(x: float) -> list[float]:
        return [x * scale] * 3
    return OpRiskInputs(
        interest_income=three(1000), interest_expense=three(400),
        interest_earning_assets=three(20000), dividend_income=three(10),
        fee_income=three(300), fee_expense=three(100), other_operating_income=three(50),
        other_operating_expense=three(80), net_pnl_trading_book=three(-60),
        net_pnl_banking_book=three(20), annual_operational_losses=losses or [])


@pytest.mark.parametrize("bucket,upper,alpha", [(1, 1000.0, 0.12), (2, 30000.0, 0.15),
                                                (3, math.inf, 0.18)])
def test_bic_table1(bucket: int, upper: float, alpha: float) -> None:
    assert p.OPE_BI_BUCKETS_EUR_M[bucket - 1] == (upper, alpha)


def test_bic_worked_example() -> None:
    """OPE25.7 footnote 363: BI EUR 35bn -> BIC EUR 5.37bn."""
    assert opr.business_indicator_component(35_000) == pytest.approx(5_370.0)
    assert opr.business_indicator_component(1_000) == pytest.approx(120.0)
    assert opr.business_indicator_component(30_000) == pytest.approx(120 + 29_000 * 0.15)
    assert opr.business_indicator_component(0) == 0.0
    assert [opr.bi_bucket(x) for x in (1000, 1000.01, 30000, 30000.01)] == [1, 2, 2, 3]


def test_bi_components() -> None:
    c = opr.business_indicator_components(op_inputs())
    assert c["ILDC"] == pytest.approx(min(600, 0.0225 * 20000) + 10)   # 450 + 10
    assert c["SC"] == pytest.approx(max(50, 80) + max(300, 100))
    assert c["FC"] == pytest.approx(60 + 20)
    # absolute values are taken year by year before averaging (OPE25.5 fn 362)
    inp = op_inputs().model_copy(update={"net_pnl_trading_book": [100.0, -100.0, 50.0]})
    assert opr.business_indicator_components(inp)["FC"] == pytest.approx(250 / 3 + 20)


def test_ilm_formula() -> None:
    assert opr.internal_loss_multiplier(100.0, 100.0) == pytest.approx(1.0)
    assert opr.internal_loss_multiplier(200.0, 100.0) == pytest.approx(
        math.log(math.e - 1 + 2 ** 0.8))
    assert opr.internal_loss_multiplier(0.0, 100.0) == pytest.approx(math.log(math.e - 1))
    assert opr.loss_component([10.0] * 4) is None
    assert opr.loss_component([10.0] * 5) == pytest.approx(150.0)
    assert opr.loss_component([999.0] * 2 + [10.0] * 10) == pytest.approx(150.0)


def test_operational_risk_end_to_end() -> None:
    small = BCBSRegime().operational_risk(op_inputs(losses=[50.0] * 10))
    assert small.business_indicator == pytest.approx(460 + 380 + 80)
    assert small.ilm == 1.0                            # bucket 1
    assert small.rwa == pytest.approx(12.5 * 0.12 * 920)
    big = op_inputs(scale=10.0, losses=[400.0] * 10)
    res = BCBSRegime().operational_risk(big)
    bic = opr.business_indicator_component(9200.0)
    ilm = math.log(math.e - 1 + (15 * 400 / bic) ** 0.8)
    assert res.bic == pytest.approx(bic)
    assert res.ilm == pytest.approx(ilm)
    assert res.capital == pytest.approx(bic * ilm)
    assert res.rwa == pytest.approx(12.5 * bic * ilm)
    assert BCBSRegime(BCBSOptions(ilm_equal_one=True)).operational_risk(big).ilm == 1.0
    assert BCBSRegime().operational_risk(op_inputs(10.0, [1.0] * 4)).ilm == 1.0
    inc = BCBSRegime(BCBSOptions(include_loss_data_bucket1=True)).operational_risk(
        op_inputs(losses=[50.0] * 10))
    assert inc.ilm == pytest.approx(opr.internal_loss_multiplier(750.0, 0.12 * 920))


# =========================================================================
#  Output floor (RBC20 / RBC90)
# =========================================================================

@pytest.mark.parametrize("year,factor", [
    (2022, 0.0), (2023, 0.50), (2024, 0.55), (2025, 0.60), (2026, 0.65), (2027, 0.70),
    (2028, 0.725), (2040, 0.725)])
def test_output_floor_schedule(year: int, factor: float) -> None:
    assert of.floor_factor(year) == factor


def test_output_floor_worked_example() -> None:
    """RBC20.13 Table 1: pre-floor 76, standardised 140 -> 101.5; RBC90.2 cap -> 95."""
    res = BCBSRegime().output_floor(76.0, 140.0, 2028)
    assert res.floored_rwa == pytest.approx(101.5)
    assert res.add_on == pytest.approx(25.5)
    assert res.applies
    capped = BCBSRegime(BCBSOptions(output_floor_transitional_cap=True)).output_floor(
        76.0, 140.0, 2027)
    assert capped.floored_rwa == pytest.approx(95.0)
    # cap does not apply once fully phased in
    full = BCBSRegime(BCBSOptions(output_floor_transitional_cap=True)).output_floor(
        76.0, 140.0, 2028)
    assert full.floored_rwa == pytest.approx(101.5)
    assert BCBSRegime().output_floor(100.0, 120.0, 2026).floored_rwa == 100.0
    pre = BCBSRegime().output_floor(76.0, 140.0, 2022)
    assert not pre.applies and pre.floored_rwa == 76.0


# =========================================================================
#  Capital stack (RBC20 / RBC30 / RBC40 / LEV)
# =========================================================================

def test_minimums_and_buffers() -> None:
    req = BCBSRegime().capital_requirements()
    assert (req.cet1_minimum, req.tier1_minimum, req.total_capital_minimum) == (0.045, 0.06, 0.08)
    assert req.conservation_buffer == 0.025
    assert req.leverage_minimum == 0.03
    assert req.systemic_risk_buffer == 0.0
    assert req.cet1_requirement == pytest.approx(0.07)


@pytest.mark.parametrize("bucket,hla", [(1, 0.010), (2, 0.015), (3, 0.020), (4, 0.025),
                                        (5, 0.035), (6, 0.045), (7, 0.055)])
def test_gsib_hla_and_leverage_buffer(bucket: int, hla: float) -> None:
    req = BCBSRegime().capital_requirements(systemic_bucket_or_rate=bucket,
                                            countercyclical_rate=0.01)
    assert req.systemic_buffer == pytest.approx(hla)
    assert req.leverage_buffer == pytest.approx(0.5 * hla)
    assert req.cet1_requirement == pytest.approx(0.045 + 0.025 + 0.01 + hla)


@pytest.mark.parametrize("score,bucket", [
    (0, 0), (129.9, 0), (130, 1), (229, 1), (230, 2), (329, 2), (330, 3), (430, 4), (529, 4),
    (530, 5), (629, 5), (630, 6)])
def test_gsib_bucket_from_score(score: float, bucket: int) -> None:
    assert cs.gsib_bucket_from_score(score) == bucket


def test_gsib_score_ranges_table() -> None:
    assert p.GSIB_SCORE_RANGES_BPS == {1: (130, 229), 2: (230, 329), 3: (330, 429),
                                       4: (430, 529), 5: (530, 629)}
    for b, (lo, hi) in p.GSIB_SCORE_RANGES_BPS.items():
        assert cs.gsib_bucket_from_score(lo) == b and cs.gsib_bucket_from_score(hi) == b


def test_systemic_rate_and_validation() -> None:
    req = BCBSRegime().capital_requirements(systemic_bucket_or_rate=0.02)
    assert req.systemic_buffer == 0.02 and req.leverage_buffer == pytest.approx(0.01)
    with pytest.raises(ValueError):
        BCBSRegime().capital_requirements(systemic_bucket_or_rate=1.5)
    with pytest.raises(ValueError):
        BCBSRegime().capital_requirements(countercyclical_rate=-0.01)


@pytest.mark.parametrize("cet1,ratio", [
    (0.045, 1.0), (0.05125, 1.0), (0.0513, 0.8), (0.0575, 0.8), (0.0576, 0.6), (0.06375, 0.6),
    (0.064, 0.4), (0.07, 0.4), (0.0701, 0.0)])
def test_conservation_ratios_rbc30_4(cet1: float, ratio: float) -> None:
    assert cs.conservation_ratio(cet1, 0.025) == ratio


@pytest.mark.parametrize("cet1,ratio", [
    (0.0575, 1.0), (0.07, 0.8), (0.0825, 0.6), (0.095, 0.4), (0.0951, 0.0)])
def test_conservation_ratios_rbc30_18(cet1: float, ratio: float) -> None:
    """RBC30.18: 2.5% CCyB -> combined buffer 5%."""
    assert cs.conservation_ratio(cet1, 0.05) == ratio


# =========================================================================
#  SA-CCR (CRE52)
# =========================================================================

SF_TABLE: dict[str, tuple[float, float | None, float]] = {
    "IR": (0.0050, None, 0.50), "FX": (0.04, None, 0.15),
    "CREDIT_SN_AAA": (0.0038, 0.5, 1.0), "CREDIT_SN_AA": (0.0038, 0.5, 1.0),
    "CREDIT_SN_A": (0.0042, 0.5, 1.0), "CREDIT_SN_BBB": (0.0054, 0.5, 1.0),
    "CREDIT_SN_BB": (0.0106, 0.5, 1.0), "CREDIT_SN_B": (0.016, 0.5, 1.0),
    "CREDIT_SN_CCC": (0.06, 0.5, 1.0), "CREDIT_INDEX_IG": (0.0038, 0.8, 0.8),
    "CREDIT_INDEX_SG": (0.0106, 0.8, 0.8), "EQUITY_SN": (0.32, 0.5, 1.2),
    "EQUITY_INDEX": (0.20, 0.8, 0.75), "COMMODITY_ELECTRICITY": (0.40, 0.4, 1.5),
    "COMMODITY_OIL_GAS": (0.18, 0.4, 0.7), "COMMODITY_METALS": (0.18, 0.4, 0.7),
    "COMMODITY_AGRICULTURAL": (0.18, 0.4, 0.7), "COMMODITY_OTHER": (0.18, 0.4, 0.7)}


@pytest.mark.parametrize("sub,expected", list(SF_TABLE.items()))
def test_saccr_table2(sub: str, expected: tuple[float, float | None, float]) -> None:
    sf, rho, vol = p.SACCR_SUPERVISORY_PARAMS[sub]
    assert sf == pytest.approx(expected[0])
    assert rho == expected[1]
    assert vol == pytest.approx(expected[2])


def test_saccr_sf_adjustments_and_mf() -> None:
    assert saccr.supervisory_factor("IR", basis=True) == pytest.approx(0.0025)
    assert saccr.supervisory_factor("EQUITY_SN", volatility=True) == pytest.approx(1.6)
    assert saccr.maturity_factor_unmargined(0.5) == pytest.approx(math.sqrt(0.5))
    assert saccr.maturity_factor_unmargined(3.0) == 1.0
    assert saccr.maturity_factor_unmargined(0.001) == pytest.approx(math.sqrt(10 / 250))
    assert saccr.maturity_factor_margined(10) == pytest.approx(1.5 * math.sqrt(10 / 250))
    assert saccr.mpor_floor() == 10
    assert saccr.mpor_floor(daily_margin=False, remargin_days=5) == 14
    assert saccr.mpor_floor(large_or_illiquid=True) == 20
    assert saccr.mpor_floor(large_or_illiquid=True, disputes=True) == 40


def test_saccr_ead() -> None:
    ns = SACCRNettingSetInput(netting_set_id="n1", replacement_cost=10.0, aggregate_addon=5.0,
                              mtm=10.0)
    res = BCBSRegime().saccr_ead(ns)
    assert res.alpha == 1.4 and res.multiplier == 1.0
    assert res.ead == pytest.approx(1.4 * 15.0)
    neg = SACCRNettingSetInput(netting_set_id="n2", replacement_cost=0.0, aggregate_addon=10.0,
                               mtm=-20.0)
    m = 0.05 + 0.95 * math.exp(-20.0 / (2 * 0.95 * 10.0))
    r2 = BCBSRegime().saccr_ead(neg)
    assert r2.multiplier == pytest.approx(m)
    assert r2.ead == pytest.approx(1.4 * m * 10.0)
    # multiplier floor 5%
    assert saccr.pfe_multiplier(-1e9, 0.0, 1.0) == pytest.approx(0.05)
    # excess collateral activates the multiplier
    assert saccr.pfe_multiplier(10.0, 30.0, 10.0) < 1.0
    # no alpha exemption for non-financial / pension counterparties in the Basel Framework
    nf = ns.model_copy(update={"counterparty_is_nonfinancial": True,
                               "counterparty_is_pension_scheme": True})
    assert BCBSRegime().saccr_ead(nf).alpha == 1.4
    assert saccr.pfe_multiplier(-5.0, 0.0, 0.0) == 1.0


# =========================================================================
#  BA-CVA (MAR50)
# =========================================================================

CVA_RW = {
    "SOVEREIGN": (0.005, 0.02), "LOCAL_GOVERNMENT": (0.01, 0.04), "FINANCIAL": (0.05, 0.12),
    "BASIC_MATERIALS": (0.03, 0.07), "CONSUMER": (0.03, 0.085), "TECHNOLOGY": (0.02, 0.055),
    "HEALTH_CARE": (0.015, 0.05), "OTHER": (0.05, 0.12)}


@pytest.mark.parametrize("sector,ig,hy", [(k, v[0], v[1]) for k, v in CVA_RW.items()])
def test_ba_cva_table1(sector: str, ig: float, hy: float) -> None:
    assert p.BA_CVA_RW[(sector, "IG")] == pytest.approx(ig)
    assert p.BA_CVA_RW[(sector, "HY_NR")] == pytest.approx(hy)
    assert cva.supervisory_rw(sector, "HY") == pytest.approx(hy)
    assert cva.supervisory_rw(sector, "NR") == pytest.approx(hy)


def test_ba_cva_params() -> None:
    assert p.BA_CVA_RHO == 0.5
    assert p.BA_CVA_DISCOUNT_SCALAR == 0.65
    assert p.BA_CVA_BETA == 0.25
    assert p.BA_CVA_HEDGE_CORRELATION == {"DIRECT": 1.0, "LEGAL": 0.8, "SECTOR_REGION": 0.5}
    assert cva.discount_factor(2.0) == pytest.approx((1 - math.exp(-0.1)) / 0.1)
    assert cva.discount_factor(2.0, imm=True) == 1.0
    with pytest.raises(ValueError):
        cva.supervisory_rw("UNKNOWN", "IG")
    with pytest.raises(ValueError):
        cva.normalise_credit_quality("AA")


def test_ba_cva_reduced_worked_example() -> None:
    cps: list[dict[str, float | str | bool]] = [
        {"ead": 100.0, "maturity": 2.0, "sector": "FINANCIAL", "credit_quality": "IG"},
        {"ead": 50.0, "maturity": 5.0, "sector": "CONSUMER", "credit_quality": "HY_NR"}]
    s1 = 0.05 / 1.4 * 2 * 100 * cva.discount_factor(2.0)
    s2 = 0.085 / 1.4 * 5 * 50 * cva.discount_factor(5.0)
    kr = math.sqrt((0.5 * (s1 + s2)) ** 2 + 0.75 * (s1 ** 2 + s2 ** 2))
    out = BCBSRegime().ba_cva_capital(cps)
    assert out["k_reduced"] == pytest.approx(kr)
    assert out["k"] == pytest.approx(0.65 * kr)
    assert out["rwa"] == pytest.approx(12.5 * 0.65 * kr)
    # single counterparty: K_reduced = SCVA
    one = BCBSRegime().ba_cva_capital(cps[:1])
    assert one["k_reduced"] == pytest.approx(s1)


def test_ba_cva_full_with_hedges() -> None:
    m, b = 2.0, 100.0
    cps: list[dict[str, float | str | bool]] = [
        {"ead": 100.0, "maturity": m, "sector": "FINANCIAL", "credit_quality": "IG",
         "hedge_notional": 40.0, "hedge_maturity": m, "hedge_relation": "LEGAL"},
        {"type": "INDEX_HEDGE", "notional": b, "maturity": m, "sector": "CONSUMER",
         "credit_quality": "IG"}]
    df = cva.discount_factor(m)
    scva = 0.05 / 1.4 * m * 100 * df
    term = 0.05 * m * 40 * df
    snh = 0.8 * term
    hma = (1 - 0.64) * term ** 2
    ih = 0.7 * 0.03 * m * b * df
    kh = math.sqrt((0.5 * (scva - snh) - ih) ** 2 + 0.75 * (scva - snh) ** 2 + hma)
    out = BCBSRegime().ba_cva_capital(cps, hedged=True)
    assert out["k_hedged"] == pytest.approx(kh)
    assert out["k_full"] == pytest.approx(0.25 * scva + 0.75 * kh)
    assert out["k"] == pytest.approx(0.65 * (0.25 * scva + 0.75 * kh))
    # perfect direct hedge: K_hedged -> 0, K_full = beta x K_reduced
    perfect: list[dict[str, float | str | bool]] = [
        {"ead": 1.4 * 50.0, "maturity": m, "sector": "FINANCIAL", "credit_quality": "IG",
         "hedge_notional": 50.0, "hedge_maturity": m, "hedge_relation": "DIRECT"}]
    o2 = cva.ba_cva_capital(perfect, hedged=True)
    assert o2["k_hedged"] == pytest.approx(0.0, abs=1e-12)
    assert o2["k_full"] == pytest.approx(0.25 * o2["k_reduced"])


def test_ba_cva_netting_sets_grouped_and_materiality() -> None:
    rows: list[dict[str, float | str | bool]] = [
        {"counterparty": "X", "ead": 60.0, "maturity": 1.0, "sector": "OTHER",
         "credit_quality": "IG"},
        {"counterparty": "X", "ead": 40.0, "maturity": 3.0, "sector": "OTHER",
         "credit_quality": "IG"}]
    s = 0.05 / 1.4 * (1.0 * 60 * cva.discount_factor(1.0) + 3.0 * 40 * cva.discount_factor(3.0))
    assert cva.ba_cva_capital(rows)["k_reduced"] == pytest.approx(s)
    assert cva.materiality_alternative(100_000.0, 12.0) == 12.0
    assert cva.materiality_alternative(100_000.1, 12.0) is None
