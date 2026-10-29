"""Tests for the Canada (OSFI CAR 2026) regime package.

Every transcribed table cell is asserted (parametrised), plus worked examples for the formulas
(BIC footnote 8, ILM, SSA, SA-CCR multiplier, BA-CVA reduced/full, capital floor), boundaries
(LTV bands, maturity cut-offs, 20% provision test) and protocol conformance.

References: OSFI CAR 2026 Chapters 1, 3, 4, 7, 8 (see docs/jurisdictions/CA_parameter_reference.md)
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
)
from src.jurisdictions.ca import CARegime, OpRiskApproach, cva, saccr
from src.jurisdictions.ca import capital_stack as cs
from src.jurisdictions.ca import credit_risk as cr
from src.jurisdictions.ca import operational_risk as opr
from src.jurisdictions.ca import output_floor as of
from src.jurisdictions.ca import params as p

R = RatingBucket
REGIME = CARegime()


def exp(asset_class: AssetClass, **kw: object) -> SAExposure:
    """Build a $100M on-balance exposure."""
    base: dict[str, object] = {"exposure_id": "t", "asset_class": asset_class,
                               "on_balance_amount": 100.0}
    base.update(kw)
    return SAExposure(**base)  # type: ignore[arg-type]


def rw(e: SAExposure) -> float:
    """Risk weight via the regime."""
    return REGIME.risk_weight(e).risk_weight


# =========================================================================
#  Protocol
# =========================================================================

def test_protocol_conformance() -> None:
    assert isinstance(CARegime(), RegimeCalculator)
    assert REGIME.jurisdiction == Jurisdiction.CA
    assert "CAR" in REGIME.regime_name


# =========================================================================
#  Chapter 4 tables
# =========================================================================

@pytest.mark.parametrize("rating,expected", [
    (R.AAA_TO_AA_MINUS, 0.0), (R.A_PLUS_TO_A_MINUS, 0.20), (R.BBB_PLUS_TO_BBB_MINUS, 0.50),
    (R.BB_PLUS_TO_BB_MINUS, 1.0), (R.B_PLUS_TO_B_MINUS, 1.0), (R.BELOW_B_MINUS, 1.50),
    (R.UNRATED, 1.0),
])
def test_table1_sovereign(rating: RatingBucket, expected: float) -> None:
    assert rw(exp(AssetClass.SOVEREIGN, rating=rating)) == pytest.approx(expected)


@pytest.mark.parametrize("score,expected", [
    (0, 0.0), (1, 0.0), (2, 0.20), (3, 0.50), (4, 1.0), (5, 1.0), (6, 1.0), (7, 1.50),
])
def test_table2_eca_scores(score: int, expected: float) -> None:
    assert rw(exp(AssetClass.SOVEREIGN, oecd_crc=score)) == pytest.approx(expected)


def test_canadian_sovereign_and_supranationals_zero() -> None:
    assert rw(exp(AssetClass.SOVEREIGN, rating=R.UNRATED,
                  flags={"ca_canadian_sovereign": True})) == 0.0
    assert rw(exp(AssetClass.SOVEREIGN, flags={"ca_zero_rw_supranational": True})) == 0.0


@pytest.mark.parametrize("sov,expected", [
    (R.AAA_TO_AA_MINUS, 0.20), (R.A_PLUS_TO_A_MINUS, 0.50), (R.BBB_PLUS_TO_BBB_MINUS, 1.0),
    (R.BB_PLUS_TO_BB_MINUS, 1.0), (R.B_PLUS_TO_B_MINUS, 1.0), (R.BELOW_B_MINUS, 1.50),
    (R.UNRATED, 1.0),
])
def test_table3_pse(sov: RatingBucket, expected: float) -> None:
    assert rw(exp(AssetClass.PSE, sovereign_rating=sov)) == pytest.approx(expected)


def test_pse_province_and_guarantee_as_corporate() -> None:
    assert rw(exp(AssetClass.PSE, flags={"ca_canadian_province_territory": True})) == 0.0
    e = exp(AssetClass.PSE, rating=R.A_PLUS_TO_A_MINUS,
            flags={"ca_pse_non_own_services_guarantee": True})
    assert rw(e) == pytest.approx(0.50)  # corporate Table 9 on the PSE's rating


@pytest.mark.parametrize("rating,expected", [
    (R.AAA_TO_AA_MINUS, 0.20), (R.A_PLUS_TO_A_MINUS, 0.30), (R.BBB_PLUS_TO_BBB_MINUS, 0.50),
    (R.BB_PLUS_TO_BB_MINUS, 1.0), (R.B_PLUS_TO_B_MINUS, 1.0), (R.BELOW_B_MINUS, 1.50),
    (R.UNRATED, 0.50),
])
def test_table4_mdb(rating: RatingBucket, expected: float) -> None:
    assert rw(exp(AssetClass.MDB, rating=rating)) == pytest.approx(expected)


def test_mdb_zero_list() -> None:
    assert rw(exp(AssetClass.MDB, flags={"ca_mdb_zero_rw_eligible": True})) == 0.0


@pytest.mark.parametrize("rating,base,short", [
    (R.AAA_TO_AA_MINUS, 0.20, 0.20), (R.A_PLUS_TO_A_MINUS, 0.30, 0.20),
    (R.BBB_PLUS_TO_BBB_MINUS, 0.50, 0.20), (R.BB_PLUS_TO_BB_MINUS, 1.0, 0.50),
    (R.B_PLUS_TO_B_MINUS, 1.0, 0.50), (R.BELOW_B_MINUS, 1.50, 1.50),
])
def test_table5_bank_ecra(rating: RatingBucket, base: float, short: float) -> None:
    assert rw(exp(AssetClass.BANK, rating=rating, original_maturity_months=12)) == base
    assert rw(exp(AssetClass.BANK, rating=rating, original_maturity_months=3)) == short


@pytest.mark.parametrize("grade,base,short", [
    (SCRAGrade.A, 0.40, 0.20), (SCRAGrade.B, 0.75, 0.50), (SCRAGrade.C, 1.50, 1.50),
])
def test_table6_bank_scra(grade: SCRAGrade, base: float, short: float) -> None:
    assert rw(exp(AssetClass.BANK, scra_grade=grade, original_maturity_months=6)) == base
    assert rw(exp(AssetClass.BANK, scra_grade=grade, original_maturity_months=3)) == short


def test_scra_enhanced_grade_a_and_election() -> None:
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.A, scra_grade_a_enhanced=True)) == 0.30
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.A,
                  flags={"ca_scra_100pct_election": True})) == 1.0
    assert rw(exp(AssetClass.BANK)) == 0.75  # no grade supplied -> Grade B


def test_bank_short_term_boundaries() -> None:
    # 3 months boundary (inclusive); trade-related up to 6 months
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.B, original_maturity_months=3.0)) == 0.50
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.B, original_maturity_months=3.01)) == 0.75
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.B, original_maturity_months=6.0,
                  is_trade_related=True)) == 0.50
    assert rw(exp(AssetClass.BANK, scra_grade=SCRAGrade.B, original_maturity_months=6.5,
                  is_trade_related=True)) == 0.75


def test_scra_sovereign_floor() -> None:
    e = exp(AssetClass.BANK, scra_grade=SCRAGrade.A, sovereign_rating=R.BELOW_B_MINUS,
            flags={"ca_bank_exposure_not_in_local_currency": True})
    assert rw(e) == 1.50
    trade = exp(AssetClass.BANK, scra_grade=SCRAGrade.A, sovereign_rating=R.BELOW_B_MINUS,
                is_trade_related=True, residual_maturity_years=0.5, original_maturity_months=6,
                flags={"ca_bank_exposure_not_in_local_currency": True})
    assert rw(trade) == 0.20


def test_bank_smsb_simplified_and_due_diligence() -> None:
    assert rw(exp(AssetClass.BANK, flags={"ca_smsb_simplified": True})) == 0.40
    assert rw(exp(AssetClass.BANK, original_maturity_months=2,
                  flags={"ca_smsb_simplified": True})) == 0.20
    assert rw(exp(AssetClass.BANK, rating=R.A_PLUS_TO_A_MINUS,
                  flags={"ca_due_diligence_uplift": True})) == 0.50


@pytest.mark.parametrize("st,expected", [
    (ShortTermRating.A1_P1, 0.20), (ShortTermRating.A2_P2, 0.50),
    (ShortTermRating.A3_P3, 1.00), (ShortTermRating.OTHERS, 1.50),
])
def test_table15_short_term(st: ShortTermRating, expected: float) -> None:
    assert rw(exp(AssetClass.BANK, short_term_rating=st)) == expected
    assert rw(exp(AssetClass.CORPORATE, short_term_rating=st)) == expected


@pytest.mark.parametrize("rating,expected", [
    (R.AAA_TO_AA_MINUS, 0.20), (R.A_PLUS_TO_A_MINUS, 0.30), (R.BBB_PLUS_TO_BBB_MINUS, 0.50),
    (R.BB_PLUS_TO_BB_MINUS, 1.0), (R.B_PLUS_TO_B_MINUS, 1.0), (R.BELOW_B_MINUS, 1.50),
])
def test_table7_covered_bond_rated(rating: RatingBucket, expected: float) -> None:
    assert rw(exp(AssetClass.COVERED_BOND, rating=rating, covered_bond_rated=True)) == expected


@pytest.mark.parametrize("issuer,expected", [
    (0.20, 0.20), (0.30, 0.30), (0.40, 0.40), (0.50, 0.50), (0.75, 0.75), (1.00, 1.00),
    (1.50, 1.50),
])
def test_table8_covered_bond_unrated_map(issuer: float, expected: float) -> None:
    assert p.COVERED_BOND_UNRATED_RW[issuer] == expected


def test_covered_bond_unrated_from_scra_and_smsb() -> None:
    assert rw(exp(AssetClass.COVERED_BOND, scra_grade=SCRAGrade.A)) == 0.40
    assert rw(exp(AssetClass.COVERED_BOND, flags={"ca_smsb_simplified": True})) == 0.20


@pytest.mark.parametrize("rating,expected", [
    (R.AAA_TO_AA_MINUS, 0.20), (R.A_PLUS_TO_A_MINUS, 0.50), (R.BBB_PLUS_TO_BBB_MINUS, 0.75),
    (R.BB_PLUS_TO_BB_MINUS, 1.0), (R.B_PLUS_TO_B_MINUS, 1.50), (R.BELOW_B_MINUS, 1.50),
])
def test_table9_corporate(rating: RatingBucket, expected: float) -> None:
    assert rw(exp(AssetClass.CORPORATE, rating=rating)) == expected


def test_corporate_unrated_options() -> None:
    assert rw(exp(AssetClass.CORPORATE)) == 1.00
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True, annual_turnover=500)) == 0.65
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=False)) == 1.50
    # IG but neither listed nor sales > $75M -> non-IG
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True, annual_turnover=75)) == 1.50
    assert rw(exp(AssetClass.CORPORATE, is_investment_grade=True, annual_turnover=60,
                  flags={"ca_listed_securities": True})) == 0.65
    assert rw(exp(AssetClass.CORPORATE, rating=R.AAA_TO_AA_MINUS,
                  flags={"ca_corporate_100pct_election": True})) == 1.00
    assert rw(exp(AssetClass.CORPORATE, flags={"ca_us_gse": True})) == 0.20
    assert rw(exp(AssetClass.CORPORATE, flags={"ca_smsb_simplified": True})) == 1.00


def test_sme() -> None:
    assert rw(exp(AssetClass.CORPORATE_SME, annual_turnover=75.0)) == 0.85
    assert rw(exp(AssetClass.CORPORATE, is_sme=True, annual_turnover=10.0)) == 0.85
    assert rw(exp(AssetClass.CORPORATE_SME, annual_turnover=75.01)) == 1.00
    assert rw(exp(AssetClass.CORPORATE_SME, flags={"ca_sme_retail_sbe": True})) == 0.75
    assert rw(exp(AssetClass.CORPORATE_SME, rating=R.A_PLUS_TO_A_MINUS)) == 0.50


@pytest.mark.parametrize("phase,expected", [
    (PFPhase.PRE_OPERATIONAL, 1.30), (PFPhase.OPERATIONAL, 1.00),
    (PFPhase.HIGH_QUALITY_OPERATIONAL, 0.80),
])
def test_project_finance(phase: PFPhase, expected: float) -> None:
    assert rw(exp(AssetClass.SPECIALISED_LENDING_PF, pf_phase=phase)) == expected


def test_object_commodity_finance_and_rated_sl() -> None:
    assert rw(exp(AssetClass.SPECIALISED_LENDING_OF)) == 1.00
    assert rw(exp(AssetClass.SPECIALISED_LENDING_CF)) == 1.00
    assert rw(exp(AssetClass.SPECIALISED_LENDING_PF)) == 1.30  # phase missing -> pre-op
    assert rw(exp(AssetClass.SPECIALISED_LENDING_OF, rating=R.AAA_TO_AA_MINUS,
                  flags={"ca_issue_specific_rating": True})) == 0.20
    # issuer rating only -> not used
    assert rw(exp(AssetClass.SPECIALISED_LENDING_OF, rating=R.AAA_TO_AA_MINUS)) == 1.00


@pytest.mark.parametrize("etype,expected", [
    (EquityType.GENERAL, 2.50), (EquityType.SPECULATIVE_UNLISTED, 4.00),
    (EquityType.LEGISLATIVE_PROGRAMME, 1.00), (EquityType.PUBLICLY_TRADED, 2.50),
    (EquityType.NON_PUBLIC, 2.50), (EquityType.SIGNIFICANT_FI, 2.50),
])
def test_equity(etype: EquityType, expected: float) -> None:
    assert rw(exp(AssetClass.EQUITY, equity_type=etype)) == expected


def test_equity_no_transitional_and_subordinated() -> None:
    assert rw(exp(AssetClass.EQUITY)) == 2.50
    assert rw(exp(AssetClass.SUBORDINATED_DEBT)) == 1.50


def test_retail() -> None:
    assert rw(exp(AssetClass.RETAIL_REGULATORY)) == 0.75
    assert rw(exp(AssetClass.RETAIL_REGULATORY, aggregate_retail_exposure_to_obligor=1.5)) == 0.75
    assert rw(exp(AssetClass.RETAIL_REGULATORY, aggregate_retail_exposure_to_obligor=1.51)) == 1.0
    assert rw(exp(AssetClass.RETAIL_OTHER)) == 1.00
    assert rw(exp(AssetClass.RETAIL_REGULATORY, meets_regulatory_retail_criteria=False)) == 1.0
    assert rw(exp(AssetClass.RETAIL_OTHER, flags={"ca_smsb_simplified": True})) == 1.0
    assert rw(exp(AssetClass.RETAIL_REGULATORY, flags={"ca_smsb_simplified": True})) == 0.75


def test_transactor_conservative_default_and_printed_value() -> None:
    assert p.RETAIL_TRANSACTOR_RW_AS_PRINTED == 0.15
    assert rw(exp(AssetClass.RETAIL_TRANSACTOR)) == 0.45
    assert rw(exp(AssetClass.RETAIL_REGULATORY, is_transactor=True)) == 0.45
    assert rw(exp(AssetClass.RETAIL_TRANSACTOR,
                  flags={"ca_apply_printed_transactor_rw": True})) == 0.15
    assert any("VERIFY" in n for n in REGIME.risk_weight(exp(AssetClass.RETAIL_TRANSACTOR)).notes)


# --- Table 10 / Table 11 residential --------------------------------------

@pytest.mark.parametrize("ltv,expected", [
    (0.30, 0.20), (0.50, 0.20), (0.5001, 0.25), (0.60, 0.25), (0.65, 0.30), (0.70, 0.30),
    (0.75, 0.35), (0.80, 0.35), (0.85, 0.40), (0.90, 0.40), (0.95, 0.50), (1.00, 0.50),
    (1.01, 0.70),
])
def test_table10_general_rre(ltv: float, expected: float) -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=ltv)) == expected


@pytest.mark.parametrize("ltv,expected", [
    (0.50, 0.30), (0.60, 0.35), (0.70, 0.45), (0.80, 0.50), (0.90, 0.60), (1.00, 0.75),
    (1.20, 1.05),
])
def test_table11_income_producing_rre(ltv: float, expected: float) -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=ltv, is_cash_flow_dependent=True)) == expected


def test_rre_primary_residence_excluded_from_ipre() -> None:
    e = exp(AssetClass.RESIDENTIAL_RE, ltv=0.75, is_cash_flow_dependent=True,
            flags={"ca_primary_residence": True})
    assert rw(e) == 0.35


def test_vrfp_negative_amortisation() -> None:
    flags = {"ca_vrfp_negative_amortization": True}
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.75, flags=flags)) == 0.50  # Table 11
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.65, flags=flags)) == 0.30  # not > 65%
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.75, is_regulatory_real_estate=False,
                  flags=flags)) == 1.50


def test_b20_noncompliant() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.55,
                  flags={"ca_b20_noncompliant": True})) == 0.35


def test_rre_non_qualifying() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.5, is_regulatory_real_estate=False)) == 0.75
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False,
                  flags={"ca_counterparty_sme": True})) == 0.85
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False,
                  is_cash_flow_dependent=True)) == 1.50
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_regulatory_real_estate=False,
                  rating=R.AAA_TO_AA_MINUS, flags={"ca_counterparty_corporate": True})) == 0.20


def test_rre_missing_ltv_and_smsb() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE)) == 0.70
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.80, flags={"ca_smsb_simplified": True})) == 0.35
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.81, flags={"ca_smsb_simplified": True})) == 0.75


def test_junior_lien_multiplier() -> None:
    f = {"ca_junior_lien_other_institution": True}
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.45, flags=f)) == 0.20  # lowest band: none
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.75, flags=f)) == pytest.approx(0.4375)
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.95, flags=f)) == pytest.approx(0.625)
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=1.2, flags=f)) == pytest.approx(0.75)  # cap


def test_heloc_ltv() -> None:
    assert cr.heloc_ltv(100, 40, 200, 500) == pytest.approx((100 + 30 + 200) / 500)
    with pytest.raises(ValueError):
        cr.heloc_ltv(1, 1, 1, 0)


@pytest.mark.parametrize("ltv,expected", [
    (0.35, 0.30), (0.40, 0.35), (0.55, 0.35), (0.60, 0.45), (0.65, 0.45), (0.80, 0.60),
])
def test_table14_reverse_mortgage(ltv: float, expected: float) -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=ltv,
                  flags={"ca_reverse_mortgage": True})) == expected


def test_reverse_mortgage_above_80() -> None:
    r = REGIME.risk_weight(exp(AssetClass.RESIDENTIAL_RE, ltv=1.0,
                               flags={"ca_reverse_mortgage": True}))
    assert r.risk_weight == pytest.approx(0.80)  # 100% on the 80% kept, 20% deducted
    assert any("deducted" in n for n in r.notes)
    nq = exp(AssetClass.RESIDENTIAL_RE, ltv=1.0, flags={"ca_reverse_mortgage_non_qualifying": True})
    assert rw(nq) == pytest.approx(1.20)
    nq2 = exp(AssetClass.RESIDENTIAL_RE, ltv=0.5,
              flags={"ca_reverse_mortgage_non_qualifying": True})
    assert rw(nq2) == pytest.approx(1.50)


def test_nha_mbs_zero() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, flags={"ca_nha_mbs": True})) == 0.0


def test_currency_mismatch_rre_only() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.75,
                  currency_matches_borrower_income=False)) == pytest.approx(0.525)
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=1.2, is_cash_flow_dependent=True,
                  currency_matches_borrower_income=False)) == 1.50  # capped
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.75, currency_matches_borrower_income=False,
                  flags={"ca_borrower_hedged": True})) == 0.35
    # OSFI scope excludes retail (Basel CRE20.92 includes it)
    assert rw(exp(AssetClass.RETAIL_REGULATORY, currency_matches_borrower_income=False)) == 0.75


# --- Tables 12-13 commercial, ADC ----------------------------------------------

def test_table12_general_cre() -> None:
    ind = {"ca_counterparty_individual": True}
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.60, flags=ind)) == 0.60
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.61, flags=ind)) == 0.75
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.50, is_sme=True)) == 0.60
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.70, is_sme=True)) == 0.85
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.50, rating=R.AAA_TO_AA_MINUS)) == 0.20
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.70)) == 1.00  # unrated corporate


@pytest.mark.parametrize("ltv,expected", [
    (0.40, 0.70), (0.60, 0.70), (0.61, 0.90), (0.80, 0.90), (0.81, 1.10),
])
def test_table13_income_producing_cre(ltv: float, expected: float) -> None:
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=ltv, is_cash_flow_dependent=True)) == expected


def test_cre_other_cases() -> None:
    assert rw(exp(AssetClass.COMMERCIAL_RE, is_cash_flow_dependent=True,
                  is_regulatory_real_estate=False)) == 1.50
    assert rw(exp(AssetClass.COMMERCIAL_RE, is_regulatory_real_estate=False, is_sme=True)) == 0.85
    assert rw(exp(AssetClass.COMMERCIAL_RE, ltv=0.5, is_cash_flow_dependent=True,
                  flags={"ca_cre_loss_test_exemption": True,
                         "ca_counterparty_individual": True})) == 0.60
    assert rw(exp(AssetClass.COMMERCIAL_RE, flags={"ca_smsb_simplified": True})) == 1.00


def test_adc() -> None:
    assert rw(exp(AssetClass.LAND_ADC)) == 1.50
    assert rw(exp(AssetClass.LAND_ADC, is_adc_presold_or_equity_at_risk=True)) == 1.00
    assert rw(exp(AssetClass.LAND_ADC, is_adc_presold_or_equity_at_risk=True,
                  flags={"ca_high_rise_without_presale": True})) == 1.50
    assert rw(exp(AssetClass.LAND_ADC, flags={"ca_adc_subordinated_tranche": True})) == 3.00


# --- Defaulted, other assets -----------------------------------------------------

@pytest.mark.parametrize("prov,expected", [(0.0, 1.50), (0.1999, 1.50), (0.20, 1.00), (0.5, 1.00)])
def test_defaulted_provision_test(prov: float, expected: float) -> None:
    assert rw(exp(AssetClass.DEFAULTED, specific_provision_pct=prov)) == expected
    assert rw(exp(AssetClass.CORPORATE, is_defaulted=True, specific_provision_pct=prov)) == expected


def test_defaulted_rre() -> None:
    assert rw(exp(AssetClass.RESIDENTIAL_RE, ltv=0.5, is_defaulted=True)) == 1.00
    assert rw(exp(AssetClass.RESIDENTIAL_RE, is_defaulted=True, is_cash_flow_dependent=True)) == 1.5


@pytest.mark.parametrize("flag,expected", [
    (None, 1.00), ("ca_cash_or_gold", 0.0), ("ca_items_in_transit", 0.20),
    ("ca_threshold_deduction_item", 2.50), ("ca_pv_future_spread_income", 2.50),
    ("ca_credit_enhancing_io_strip", 12.50),
])
def test_other_assets(flag: str | None, expected: float) -> None:
    flags = {flag: True} if flag else {}
    assert rw(exp(AssetClass.OTHER_ASSETS, flags=flags)) == expected


def test_every_asset_class_dispatches() -> None:
    for ac in AssetClass:
        r = REGIME.risk_weight(exp(ac))
        assert r.jurisdiction == Jurisdiction.CA
        assert r.citation.startswith("CAR Ch.4")


# --- CCFs ---------------------------------------------------------------------------

@pytest.mark.parametrize("cat,expected", [
    (OBSCategory.UNCONDITIONALLY_CANCELLABLE, 0.10), (OBSCategory.COMMITMENT_OTHER, 0.40),
    (OBSCategory.NIF_RUF, 0.50), (OBSCategory.TRANSACTION_RELATED_CONTINGENT, 0.50),
    (OBSCategory.SHORT_TERM_TRADE_LC, 0.20), (OBSCategory.DIRECT_CREDIT_SUBSTITUTE, 1.0),
    (OBSCategory.SECURITIES_LENDING_COLLATERAL, 1.0), (OBSCategory.FORWARD_ASSET_PURCHASE, 1.0),
    (OBSCategory.OTHER_100, 1.0),
])
def test_ccf_table(cat: OBSCategory, expected: float) -> None:
    e = exp(AssetClass.CORPORATE, off_balance_notional=50.0, obs_category=cat)
    assert REGIME.ccf(e) == expected
    r = REGIME.risk_weight(e)
    assert r.exposure_amount == pytest.approx(100.0 + 50.0 * expected)


def test_ccf_commitment_regardless_of_maturity_and_cards() -> None:
    short = exp(AssetClass.CORPORATE, off_balance_notional=10,
                obs_category=OBSCategory.COMMITMENT_OTHER, commitment_original_maturity_years=0.5)
    assert REGIME.ccf(short) == 0.40
    card = exp(AssetClass.RETAIL_REGULATORY, off_balance_notional=10,
               obs_category=OBSCategory.UNCONDITIONALLY_CANCELLABLE,
               flags={"ca_credit_card_undrawn": True})
    assert REGIME.ccf(card) == 0.25
    assert REGIME.ccf(exp(AssetClass.CORPORATE)) == 0.0
    assert REGIME.ccf(exp(AssetClass.CORPORATE, off_balance_notional=1)) == 1.0
    rm = exp(AssetClass.RESIDENTIAL_RE, ltv=0.3, off_balance_notional=10,
             flags={"ca_reverse_mortgage": True})
    assert REGIME.ccf(rm) == 0.40


# --- CRM ------------------------------------------------------------------------------

@pytest.mark.parametrize("key,expected", [
    ("SOVEREIGN_AAA_AA_LE1Y", 0.005), ("SOVEREIGN_AAA_AA_1_3Y", 0.02),
    ("SOVEREIGN_AAA_AA_3_5Y", 0.02), ("SOVEREIGN_AAA_AA_5_10Y", 0.04),
    ("SOVEREIGN_AAA_AA_GT10Y", 0.04),
    ("OTHER_AAA_AA_LE1Y", 0.01), ("OTHER_AAA_AA_1_3Y", 0.03), ("OTHER_AAA_AA_3_5Y", 0.04),
    ("OTHER_AAA_AA_5_10Y", 0.06), ("OTHER_AAA_AA_GT10Y", 0.12),
    ("SECURITISATION_AAA_AA_LE1Y", 0.02), ("SECURITISATION_AAA_AA_1_3Y", 0.08),
    ("SECURITISATION_AAA_AA_3_5Y", 0.08), ("SECURITISATION_AAA_AA_5_10Y", 0.16),
    ("SECURITISATION_AAA_AA_GT10Y", 0.16),
    ("SOVEREIGN_A_BBB_LE1Y", 0.01), ("SOVEREIGN_A_BBB_1_3Y", 0.03), ("SOVEREIGN_A_BBB_3_5Y", 0.03),
    ("SOVEREIGN_A_BBB_5_10Y", 0.06), ("SOVEREIGN_A_BBB_GT10Y", 0.06),
    ("OTHER_A_BBB_LE1Y", 0.02), ("OTHER_A_BBB_1_3Y", 0.04), ("OTHER_A_BBB_3_5Y", 0.06),
    ("OTHER_A_BBB_5_10Y", 0.12), ("OTHER_A_BBB_GT10Y", 0.20),
    ("SECURITISATION_A_BBB_LE1Y", 0.04), ("SECURITISATION_A_BBB_1_3Y", 0.12),
    ("SECURITISATION_A_BBB_3_5Y", 0.12), ("SECURITISATION_A_BBB_5_10Y", 0.24),
    ("SECURITISATION_A_BBB_GT10Y", 0.24),
    ("SOVEREIGN_BB_LE1Y", 0.15), ("SOVEREIGN_BB_GT10Y", 0.15),
    ("MAIN_INDEX_EQUITY", 0.20), ("GOLD", 0.20), ("OTHER_LISTED_EQUITY", 0.30), ("CASH", 0.0),
])
def test_supervisory_haircuts(key: str, expected: float) -> None:
    assert p.SUPERVISORY_HAIRCUTS[key] == expected


def test_bb_non_sovereign_collateral_ineligible() -> None:
    assert "OTHER_BB_LE1Y" not in p.SUPERVISORY_HAIRCUTS
    r = REGIME.risk_weight(exp(AssetClass.CORPORATE, financial_collateral_value=50,
                               collateral_haircut_class="OTHER_BB_LE1Y"))
    assert r.exposure_amount == 100.0


def test_comprehensive_approach_worked_example() -> None:
    # E = 100, C = 80 main-index equity (Hc 20%), Hfx 8%: E* = 100 - 80 x 0.72 = 42.4
    e = exp(AssetClass.CORPORATE, financial_collateral_value=80,
            collateral_haircut_class="MAIN_INDEX_EQUITY",
            flags={"ca_collateral_currency_mismatch": True})
    r = REGIME.risk_weight(e)
    assert r.exposure_amount == pytest.approx(42.4)
    assert r.rwa == pytest.approx(42.4)
    assert cr.comprehensive_exposure(100, 200, 0.0, 0.0, 0.0) == 0.0
    assert cr.comprehensive_exposure(100, 50, 0.1, 0.04, 0.0) == pytest.approx(110 - 48)


def test_haircut_scaling_and_maturity_mismatch() -> None:
    # 10-day H = 0.20; daily remargining repo (TM 5, NR 1): H = 0.2 x sqrt(5/10)
    assert cr.scaled_haircut(0.20, 1, 5) == pytest.approx(0.2 * math.sqrt(0.5))
    assert cr.scaled_haircut(0.20, 1, 20) == pytest.approx(0.2 * math.sqrt(2.0))
    # Pa = 100 x (2 - 0.25)/(4 - 0.25)
    assert cr.maturity_mismatch_adjust(100, 2, 4, 3) == pytest.approx(100 * 1.75 / 3.75)
    assert cr.maturity_mismatch_adjust(100, 2, 8, 3) == pytest.approx(100 * 1.75 / 4.75)
    assert cr.maturity_mismatch_adjust(100, 0.2, 4, 3) == 0.0
    assert cr.maturity_mismatch_adjust(100, 0.5, 4, 0.9) == 0.0
    assert cr.maturity_mismatch_adjust(100, 5, 4, 5) == 100


def test_guarantee_substitution() -> None:
    e = exp(AssetClass.CORPORATE, guarantee_amount=60, guarantor_asset_class=AssetClass.SOVEREIGN,
            guarantor_rating=R.A_PLUS_TO_A_MINUS)
    r = REGIME.risk_weight(e)
    assert r.rwa == pytest.approx(60 * 0.20 + 40 * 1.00)
    assert r.risk_weight == pytest.approx(0.52)
    # FX mismatch haircut on the guarantee
    e2 = e.model_copy(update={"flags": {"ca_guarantee_currency_mismatch": True}})
    assert REGIME.risk_weight(e2).rwa == pytest.approx(60 * 0.92 * 0.2 + (100 - 55.2) * 1.0)
    # unrated corporate guarantor ineligible
    e3 = exp(AssetClass.RETAIL_OTHER, guarantee_amount=50,
             guarantor_asset_class=AssetClass.CORPORATE)
    assert REGIME.risk_weight(e3).rwa == pytest.approx(100.0)


def test_cmhc_insured_mortgage_zero() -> None:
    e = exp(AssetClass.RESIDENTIAL_RE, ltv=0.9, guarantee_amount=100,
            flags={"ca_guarantor_government_of_canada": True})
    assert REGIME.risk_weight(e).rwa == pytest.approx(0.0)


def test_private_mi_split() -> None:
    assert cr.private_mi_split(500, 400) == (50.0, 350.0)
    assert cr.private_mi_split(500, 30) == (30.0, 0.0)
    assert p.PRIVATE_MI_DEDUCTIBLE_RW_FACTOR == 2.2


def test_credit_rwa_aggregation() -> None:
    exps = [exp(AssetClass.CORPORATE), exp(AssetClass.RESIDENTIAL_RE, ltv=0.75),
            exp(AssetClass.SOVEREIGN, flags={"ca_canadian_sovereign": True})]
    res = REGIME.credit_rwa(exps)
    assert res.total_rwa == pytest.approx(135.0)
    assert res.total_exposure == pytest.approx(300.0)
    assert res.rwa_by_class["CORPORATE"] == pytest.approx(100.0)
    assert res.density == pytest.approx(0.45)


# =========================================================================
#  Chapter 3 operational risk
# =========================================================================

def _op_inputs(losses: list[float] | None = None) -> OpRiskInputs:
    return OpRiskInputs(
        interest_income=[10_000, 11_000, 12_000], interest_expense=[4_000, 5_000, 6_000],
        interest_earning_assets=[500_000, 520_000, 540_000], dividend_income=[100, 100, 100],
        fee_income=[3_000, 3_000, 3_000], fee_expense=[1_000, 1_000, 1_000],
        other_operating_income=[500, 500, 500], other_operating_expense=[700, 700, 700],
        net_pnl_trading_book=[800, -400, 600], net_pnl_banking_book=[100, 200, -300],
        annual_operational_losses=losses or [],
    )


def test_bic_footnote8_worked_example() -> None:
    assert opr.business_indicator_component(50_000) == pytest.approx(7_605)


@pytest.mark.parametrize("bi,expected", [
    (1_000, 120.0), (1_500, 180.0), (2_500, 180 + 150.0), (45_000, 180 + 0.15 * 43_500),
    (46_000, 180 + 0.15 * 43_500 + 180.0),
])
def test_bic_marginal_buckets(bi: float, expected: float) -> None:
    assert opr.business_indicator_component(bi) == pytest.approx(expected)


def test_business_indicator_components() -> None:
    c = opr.business_indicator(_op_inputs())
    assert c["ILDC"] == pytest.approx(min(6_000, 0.0225 * 520_000) + 100)
    assert c["SC"] == pytest.approx(3_000 + 700)
    assert c["FC"] == pytest.approx(600 + 200)
    assert c["BI"] == pytest.approx(6_100 + 3_700 + 800)


def test_ildc_cap_binds() -> None:
    i = _op_inputs().model_copy(update={"interest_earning_assets": [100_000] * 3})
    assert opr.business_indicator(i)["ILDC"] == pytest.approx(2_250 + 100)


def test_ilm_and_capital() -> None:
    assert opr.internal_loss_multiplier(100, 100) == pytest.approx(1.0)
    assert opr.internal_loss_multiplier(200, 100) == pytest.approx(
        math.log(math.e - 1 + 2 ** 0.8))
    bic = opr.business_indicator_component(10_600)
    low = [10.0] * 10
    res = REGIME.operational_risk(_op_inputs(low))
    lc = 15 * 10.0
    assert res.loss_component == pytest.approx(lc)
    assert res.ilm == pytest.approx(math.log(math.e - 1 + (lc / bic) ** 0.8))
    assert res.ilm < 1
    assert res.rwa == pytest.approx(12.5 * bic * res.ilm)


def test_ilm_floor_without_ten_years_or_standards() -> None:
    res = REGIME.operational_risk(_op_inputs([10.0] * 5))
    assert res.ilm == 1.0
    reg = CARegime(loss_data_standards_met=False)
    assert reg.operational_risk(_op_inputs([10.0] * 10)).ilm == 1.0
    high = REGIME.operational_risk(_op_inputs([500.0] * 5))
    assert high.ilm > 1.0  # ILM > 1 from available data is used
    assert REGIME.operational_risk(_op_inputs()).ilm == 1.0


def test_ssa_worked_example() -> None:
    reg = CARegime(is_dsib=False, op_risk_approach=OpRiskApproach.SSA)
    res = reg.operational_risk(_op_inputs())
    agi = [6_000 + 100 + 3_000 + 500 + 800 + 100, 6_000 + 100 + 3_000 + 500 + 400 + 200,
           6_000 + 100 + 3_000 + 500 + 600 + 300]
    assert res.capital == pytest.approx(0.15 * sum(agi) / 3)
    assert res.rwa == pytest.approx(12.5 * res.capital)


# =========================================================================
#  Chapter 1 floor and capital stack
# =========================================================================

@pytest.mark.parametrize("year", [2026, 2027, 2030])
def test_floor_factor_675(year: int) -> None:
    res = REGIME.output_floor(60.0, 100.0, year)
    assert res.floor_factor == 0.675
    assert res.add_on == pytest.approx(7.5)
    assert res.floored_rwa == pytest.approx(67.5)


def test_floor_not_binding_and_pre_2026_note() -> None:
    assert REGIME.output_floor(80.0, 100.0, 2026).add_on == 0.0
    assert REGIME.output_floor(60.0, 100.0, 2025).notes


def test_floor_allowances_and_institution_factor() -> None:
    res = of.apply_capital_floor(60, 100, 2026, general_allowances_t2_sa=0.4,
                                 provisioning_shortfall=0.2, excess_provisions_t2=0.0)
    floor_amt = 0.675 * (100 - 5)
    adjusted = 60 + 2.5 - 5
    assert res.add_on == pytest.approx(floor_amt - adjusted)
    assert CARegime(institution_floor_factor=0.90).output_floor(60, 100, 2026).add_on == 30
    assert not CARegime(uses_internal_models=False).output_floor(60, 100, 2026).applies
    with pytest.raises(ValueError):
        of.floor_factor(2026, 1.2)


def test_capital_stack_dsib() -> None:
    c = REGIME.capital_requirements(countercyclical_rate=0.0, stress_buffer=0.035)
    assert (c.cet1_minimum, c.tier1_minimum, c.total_capital_minimum) == (0.045, 0.06, 0.08)
    assert c.conservation_buffer == 0.025
    assert c.systemic_buffer == 0.01
    assert c.stress_buffer == 0.035
    assert c.cet1_requirement == pytest.approx(0.115)
    assert c.leverage_minimum == 0.03
    assert c.leverage_buffer == pytest.approx(0.005)


def test_capital_stack_dsb_input_and_flags() -> None:
    c = REGIME.capital_requirements()
    assert c.stress_buffer == 0.0
    assert "VERIFY" in c.citations["stress_buffer"]
    c2 = CARegime(domestic_stability_buffer=0.02).capital_requirements()
    assert c2.cet1_requirement == pytest.approx(0.10)  # footnote 35 example: 10% CET1
    with pytest.raises(ValueError):
        REGIME.capital_requirements(stress_buffer=0.05)
    with pytest.raises(ValueError):
        CARegime(is_dsib=False).capital_requirements(stress_buffer=0.01)


@pytest.mark.parametrize("bucket,expected", [(1, 0.01), (2, 0.015), (3, 0.02), (4, 0.025),
                                             (5, 0.035)])
def test_gsib_higher_of(bucket: int, expected: float) -> None:
    assert REGIME.capital_requirements(systemic_bucket_or_rate=bucket).systemic_buffer == expected


def test_gsib_rate_and_non_dsib() -> None:
    assert REGIME.capital_requirements(systemic_bucket_or_rate=0.005).systemic_buffer == 0.01
    smsb = CARegime(is_dsib=False).capital_requirements(countercyclical_rate=0.01)
    assert smsb.systemic_buffer == 0.0 and smsb.leverage_buffer == 0.0
    assert smsb.cet1_requirement == pytest.approx(0.08)
    with pytest.raises(ValueError):
        cs.gsib_surcharge(2.5)
    with pytest.raises(ValueError):
        REGIME.capital_requirements(countercyclical_rate=-0.01)


def test_target_ratios_table8() -> None:
    assert cs.target_ratios(True, 0.02) == pytest.approx({"CET1": 0.10, "Tier1": 0.115,
                                                          "Total": 0.135})
    assert cs.target_ratios(False) == {"CET1": 0.07, "Tier1": 0.085, "Total": 0.105}


@pytest.mark.parametrize("cet1,expected", [
    (0.050, 1.0), (0.05125, 1.0), (0.055, 0.8), (0.06, 0.6), (0.065, 0.4), (0.07, 0.4),
    (0.071, 0.0),
])
def test_table5_conservation(cet1: float, expected: float) -> None:
    assert cs.minimum_conservation_ratio(cet1, is_dsib=False) == expected


@pytest.mark.parametrize("cet1,lev,expected", [
    (0.053, None, 1.0), (0.06, None, 0.8), (0.07, None, 0.6), (0.075, None, 0.4),
    (0.09, None, 0.0), (0.09, 0.031, 1.0), (0.09, 0.0326, 0.6), (0.09, 0.036, 0.0),
])
def test_table7_dsib_conservation(cet1: float, lev: float | None, expected: float) -> None:
    assert cs.minimum_conservation_ratio(cet1, True, lev) == expected


# =========================================================================
#  Chapter 7 SA-CCR
# =========================================================================

def test_saccr_alpha_no_exemptions() -> None:
    for nonfin, pension in [(False, False), (True, False), (False, True)]:
        ns = SACCRNettingSetInput(netting_set_id="n", replacement_cost=10, aggregate_addon=20,
                                  counterparty_is_nonfinancial=nonfin,
                                  counterparty_is_pension_scheme=pension)
        r = REGIME.saccr_ead(ns)
        assert r.alpha == 1.4
        assert r.ead == pytest.approx(1.4 * 30)


def test_saccr_multiplier_worked_example() -> None:
    ns = SACCRNettingSetInput(netting_set_id="n", replacement_cost=10, aggregate_addon=20, mtm=-5)
    r = REGIME.saccr_ead(ns)
    mult = 0.05 + 0.95 * math.exp(-5 / (2 * 0.95 * 20))
    assert r.multiplier == pytest.approx(mult)
    assert r.ead == pytest.approx(1.4 * (10 + mult * 20))
    assert saccr.pfe_multiplier(-1e9, 20) == pytest.approx(0.05)
    assert saccr.pfe_multiplier(5, 20) == 1.0
    assert saccr.pfe_multiplier(-5, 0) == 1.0


def test_saccr_maturity_factors() -> None:
    assert saccr.maturity_factor_unmargined(0.5) == pytest.approx(math.sqrt(0.5))
    assert saccr.maturity_factor_unmargined(5) == 1.0
    assert saccr.maturity_factor_unmargined(0.001) == pytest.approx(math.sqrt(10 / 250))
    assert saccr.maturity_factor_margined(10) == pytest.approx(1.5 * math.sqrt(10 / 250))
    assert saccr.mpor_floor_business_days() == 10
    assert saccr.mpor_floor_business_days(remargin_period_bd=5) == 14
    assert saccr.mpor_floor_business_days(n_trades=5001) == 20
    assert saccr.cap_margined_ead(50, 40) == 40


@pytest.mark.parametrize("key,sf,corr,vol", [
    ("IR", 0.005, None, 0.50), ("FX", 0.04, None, 0.15),
    ("CREDIT_SN_AAA", 0.0038, 0.5, 1.0), ("CREDIT_SN_AA", 0.0038, 0.5, 1.0),
    ("CREDIT_SN_A", 0.0042, 0.5, 1.0), ("CREDIT_SN_BBB", 0.0054, 0.5, 1.0),
    ("CREDIT_SN_BB", 0.0106, 0.5, 1.0), ("CREDIT_SN_B", 0.016, 0.5, 1.0),
    ("CREDIT_SN_CCC", 0.06, 0.5, 1.0), ("CREDIT_INDEX_IG", 0.0038, 0.8, 0.8),
    ("CREDIT_INDEX_SG", 0.0106, 0.8, 0.8), ("EQUITY_SN", 0.32, 0.5, 1.2),
    ("EQUITY_INDEX", 0.20, 0.8, 0.75), ("COMMODITY_ELECTRICITY", 0.40, 0.4, 1.5),
    ("COMMODITY_OIL_GAS", 0.18, 0.4, 0.7), ("COMMODITY_METALS", 0.18, 0.4, 0.7),
    ("COMMODITY_AGRICULTURAL", 0.18, 0.4, 0.7), ("COMMODITY_OTHER", 0.18, 0.4, 0.7),
])
def test_saccr_table2(key: str, sf: float, corr: float | None, vol: float) -> None:
    assert saccr.supervisory_parameters(key) == (sf, corr, vol)


# =========================================================================
#  Chapter 8 BA-CVA
# =========================================================================

@pytest.mark.parametrize("sector,ig,hy", [
    ("SOVEREIGN", 0.005, 0.02), ("LOCAL_GOVERNMENT", 0.01, 0.04), ("FINANCIAL", 0.05, 0.12),
    ("BASIC_MATERIALS", 0.03, 0.07), ("CONSUMER", 0.03, 0.085), ("TECHNOLOGY", 0.02, 0.055),
    ("HEALTH_CARE", 0.015, 0.05), ("OTHER", 0.05, 0.12),
])
def test_ba_cva_table1(sector: str, ig: float, hy: float) -> None:
    assert cva.supervisory_rw(sector, "IG") == ig
    assert cva.supervisory_rw(sector, "HY_NR") == hy
    assert cva.supervisory_rw(sector, "NR") == hy


def test_ba_cva_reduced_worked_example() -> None:
    df = (1 - math.exp(-0.05)) / 0.05
    scva = 0.05 * 1 * 100 * df / 1.4
    out = REGIME.ba_cva_capital([{"ead": 100.0, "maturity": 1.0, "sector": "FINANCIAL",
                                  "credit_quality": "IG"}])
    assert out["k_reduced"] == pytest.approx(scva)
    assert out["k"] == pytest.approx(0.65 * scva)
    assert out["rwa"] == pytest.approx(12.5 * 0.65 * scva)


def test_ba_cva_two_counterparties_and_imm() -> None:
    a = 0.05 * 2 * 100 * 1.0 / 1.4
    b = 0.12 * 2 * 50 * 1.0 / 1.4
    out = cva.ba_cva([
        {"ead": 100.0, "maturity": 2.0, "sector": "FINANCIAL", "credit_quality": "IG", "imm": True},
        {"ead": 50.0, "maturity": 2.0, "sector": "OTHER", "credit_quality": "HY", "imm": True},
    ])
    expected = math.sqrt((0.5 * (a + b)) ** 2 + 0.75 * (a * a + b * b))
    assert out["k_reduced"] == pytest.approx(expected)


def test_ba_cva_full_with_direct_hedge() -> None:
    df = (1 - math.exp(-0.05)) / 0.05
    scva = 0.05 * 100 * df / 1.4
    hedge = 0.05 * 100 * df
    out = cva.ba_cva([{"ead": 100.0, "maturity": 1.0, "sector": "FINANCIAL",
                       "credit_quality": "IG", "hedge_notional": 100.0, "hedge_maturity": 1.0,
                       "hedge_relation": "DIRECT"}], hedged=True)
    k_hedged = abs(scva - hedge)  # rho^2 + (1 - rho^2) = 1, HMA = 0 for r = 100%
    assert out["k_hedged"] == pytest.approx(k_hedged)
    assert out["k_full"] == pytest.approx(0.25 * scva + 0.75 * k_hedged)
    assert out["k"] == pytest.approx(0.65 * out["k_full"])


def test_ba_cva_indirect_and_index_hedges() -> None:
    out = cva.ba_cva([
        {"ead": 100.0, "maturity": 1.0, "sector": "FINANCIAL", "credit_quality": "IG",
         "hedge_notional": 50.0, "hedge_relation": "SECTOR_REGION"},
        {"index_hedge": True, "notional": 50.0, "maturity": 1.0, "sector": "FINANCIAL",
         "credit_quality": "IG"},
    ], hedged=True)
    assert 0 < out["k_hedged"] < out["k_reduced"]
    assert p.BA_CVA_HEDGE_CORRELATION == {"DIRECT": 1.0, "LEGAL_RELATION": 0.8,
                                          "SECTOR_REGION": 0.5}


def test_cva_materiality_alternative() -> None:
    assert cva.below_materiality_threshold(150_000)
    assert not cva.below_materiality_threshold(150_001)
    assert cva.alternative_cva_capital(12.0, 100_000) == 12.0
    with pytest.raises(ValueError):
        cva.alternative_cva_capital(12.0, 200_000)


def test_discount_factor_edge() -> None:
    assert cva.discount_factor(0.0) == 1.0
    assert cva.discount_factor(5.0, imm=True) == 1.0
