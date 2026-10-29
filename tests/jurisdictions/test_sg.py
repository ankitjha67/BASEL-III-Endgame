"""Tests for the Singapore regime -- MAS Notice 637 (version effective 1 January 2026).

Every transcribed table cell is asserted (parametrized), alongside hand-computed worked
examples for the formulas (BIC/ILM, SA-CCR multiplier, BA-CVA, FC(CA), maturity mismatch),
the transitional schedules (output floor Table 5-3, equity Table 7-16) and band edges.

References: MAS Notice 637 Parts IV, V, VII, VIII Division 5, IX; Annexes 7B, 7D, 7H, 7J, 7M.
"""

from __future__ import annotations

import math
from datetime import date
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
    RegimeCalculator,
    SACCRNettingSetInput,
    SAExposure,
    SCRAGrade,
    ShortTermRating,
)
from src.jurisdictions.sg import SGRegime, cva, saccr
from src.jurisdictions.sg import capital_stack as cs
from src.jurisdictions.sg import credit_risk as cr
from src.jurisdictions.sg import operational_risk as orisk
from src.jurisdictions.sg import output_floor as of
from src.jurisdictions.sg import params as p

R = RatingBucket
RATED = [
    R.AAA_TO_AA_MINUS,
    R.A_PLUS_TO_A_MINUS,
    R.BBB_PLUS_TO_BBB_MINUS,
    R.BB_PLUS_TO_BB_MINUS,
    R.B_PLUS_TO_B_MINUS,
    R.BELOW_B_MINUS,
]
ALL_RATINGS = [*RATED, R.UNRATED]


def _exp(**kw: Any) -> SAExposure:
    """Build an exposure with $100m drawn by default."""
    base: dict[str, Any] = {"exposure_id": "t", "on_balance_amount": 100.0}
    base.update(kw)
    return SAExposure(**base)


@pytest.fixture()
def regime() -> SGRegime:
    return SGRegime()


def _rw(regime: SGRegime, **kw: Any) -> float:
    return regime.risk_weight(_exp(**kw)).risk_weight


# =========================================================================
#  Protocol conformance
# =========================================================================


def test_protocol_conformance(regime: SGRegime) -> None:
    assert isinstance(regime, RegimeCalculator)
    assert regime.jurisdiction is Jurisdiction.SG
    assert "MAS Notice 637" in regime.legal_basis
    assert "MAS Notice 637" in regime.regime_name


# =========================================================================
#  Annex 7M -- credit quality grades
# =========================================================================


@pytest.mark.parametrize(
    "rating,grade", list(zip(ALL_RATINGS, [1, 2, 3, 4, 5, 6, None], strict=True))
)
def test_table_7m1_grades(rating: RatingBucket, grade: int | None) -> None:
    assert cr.credit_quality_grade(rating) == grade


@pytest.mark.parametrize(
    "st,grade",
    [
        (ShortTermRating.A1_P1, "I"),
        (ShortTermRating.A2_P2, "II"),
        (ShortTermRating.A3_P3, "III"),
        (ShortTermRating.OTHERS, "IV"),
    ],
)
def test_table_7m2_short_term_grades(st: ShortTermRating, grade: str) -> None:
    assert p.ST_GRADE_BY_RATING[st] == grade


# =========================================================================
#  Sovereigns, PSEs, MDBs -- Tables 7-1 to 7-4
# =========================================================================

TABLE_7_1 = [0.0, 0.20, 0.50, 1.00, 1.00, 1.50, 1.00]


@pytest.mark.parametrize("rating,rw", list(zip(ALL_RATINGS, TABLE_7_1, strict=True)))
def test_table_7_1_sovereign(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    assert _rw(regime, asset_class=AssetClass.SOVEREIGN, rating=rating) == pytest.approx(rw)


def test_para_7_3_43_singapore_government_sgd(regime: SGRegime) -> None:
    rw = _rw(
        regime,
        asset_class=AssetClass.SOVEREIGN,
        rating=R.UNRATED,
        domestic_currency_funded=True,
        flags={"singapore_government": True},
    )
    assert rw == 0.0
    # Not SGD-funded: falls back to Table 7-1
    rw2 = _rw(
        regime,
        asset_class=AssetClass.SOVEREIGN,
        rating=R.A_PLUS_TO_A_MINUS,
        flags={"singapore_government": True},
    )
    assert rw2 == pytest.approx(0.20)


def test_para_7_3_46_supranationals(regime: SGRegime) -> None:
    rw = _rw(
        regime,
        asset_class=AssetClass.SOVEREIGN,
        rating=R.UNRATED,
        flags={"supranational_zero_rw": True},
    )
    assert rw == 0.0


TABLE_7_2 = [0.20, 0.50, 0.50, 1.00, 1.00, 1.50, 0.50]


@pytest.mark.parametrize("rating,rw", list(zip(ALL_RATINGS, TABLE_7_2, strict=True)))
def test_table_7_2_pse(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    assert _rw(regime, asset_class=AssetClass.PSE, rating=rating) == pytest.approx(rw)


TABLE_7_3_ROW1 = [0.0, 0.0, 0.0, 1.00, 1.00, 1.50, 0.0]
TABLE_7_3_ROW2 = [0.20, 0.20, 0.20, 1.00, 1.00, 1.50, 0.20]


@pytest.mark.parametrize(
    "sov,rating,rw",
    [(R.AAA_TO_AA_MINUS, r, w) for r, w in zip(ALL_RATINGS, TABLE_7_3_ROW1, strict=True)]
    + [(R.A_PLUS_TO_A_MINUS, r, w) for r, w in zip(ALL_RATINGS, TABLE_7_3_ROW2, strict=True)],
)
def test_table_7_3_pse_treated_as_sovereign(
    regime: SGRegime, sov: RatingBucket, rating: RatingBucket, rw: float
) -> None:
    out = _rw(
        regime,
        asset_class=AssetClass.PSE,
        rating=rating,
        sovereign_rating=sov,
        flags={"pse_treated_as_sovereign": True},
    )
    assert out == pytest.approx(rw)


def test_table_7_3_not_available_for_grade_3_sovereign(regime: SGRegime) -> None:
    out = _rw(
        regime,
        asset_class=AssetClass.PSE,
        rating=R.UNRATED,
        sovereign_rating=R.BBB_PLUS_TO_BBB_MINUS,
        flags={"pse_treated_as_sovereign": True},
    )
    assert out == pytest.approx(0.50)  # Table 7-2 unrated


TABLE_7_4 = [0.20, 0.30, 0.50, 1.00, 1.00, 1.50, 0.50]


@pytest.mark.parametrize("rating,rw", list(zip(ALL_RATINGS, TABLE_7_4, strict=True)))
def test_table_7_4_mdb(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    assert _rw(regime, asset_class=AssetClass.MDB, rating=rating) == pytest.approx(rw)


def test_para_7_3_51_qualifying_mdb(regime: SGRegime) -> None:
    assert _rw(regime, asset_class=AssetClass.MDB, flags={"qualifying_mdb": True}) == 0.0


# =========================================================================
#  Banks -- Tables 7-5 to 7-7
# =========================================================================

TABLE_7_5_LT = [0.20, 0.30, 0.50, 1.00, 1.00, 1.50]
TABLE_7_5_ST = [0.20, 0.20, 0.20, 0.50, 0.50, 1.50]


@pytest.mark.parametrize("rating,rw", list(zip(RATED, TABLE_7_5_LT, strict=True)))
def test_table_7_5_bank_rated_long_term(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    assert _rw(regime, asset_class=AssetClass.BANK, rating=rating) == pytest.approx(rw)


@pytest.mark.parametrize("rating,rw", list(zip(RATED, TABLE_7_5_ST, strict=True)))
def test_table_7_5_bank_rated_short_term(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    out = _rw(regime, asset_class=AssetClass.BANK, rating=rating, original_maturity_months=3.0)
    assert out == pytest.approx(rw)


def test_bank_short_term_cutoffs(regime: SGRegime) -> None:
    a = R.A_PLUS_TO_A_MINUS
    # 3 months inclusive -> short-term; just above -> long-term
    assert _rw(regime, asset_class=AssetClass.BANK, rating=a, original_maturity_months=3.0) == 0.20
    assert _rw(regime, asset_class=AssetClass.BANK, rating=a, original_maturity_months=3.01) == 0.30
    # trade-related: up to 6 months
    assert (
        _rw(
            regime,
            asset_class=AssetClass.BANK,
            rating=a,
            original_maturity_months=6.0,
            is_trade_related=True,
        )
        == 0.20
    )
    assert (
        _rw(
            regime,
            asset_class=AssetClass.BANK,
            rating=a,
            original_maturity_months=6.5,
            is_trade_related=True,
        )
        == 0.30
    )


@pytest.mark.parametrize(
    "st,rw",
    [
        (ShortTermRating.A1_P1, 0.20),
        (ShortTermRating.A2_P2, 0.50),
        (ShortTermRating.A3_P3, 1.00),
        (ShortTermRating.OTHERS, 1.50),
    ],
)
@pytest.mark.parametrize(
    "asset_class",
    [AssetClass.BANK, AssetClass.CORPORATE, AssetClass.CORPORATE_SME],
)
def test_tables_7_6_7_11_7_13_short_term_issue(
    regime: SGRegime, asset_class: AssetClass, st: ShortTermRating, rw: float
) -> None:
    out = _rw(regime, asset_class=asset_class, short_term_rating=st, annual_turnover=50.0)
    assert out == pytest.approx(rw)


@pytest.mark.parametrize(
    "grade,lt,st",
    [(SCRAGrade.A, 0.40, 0.20), (SCRAGrade.B, 0.75, 0.50), (SCRAGrade.C, 1.50, 1.50)],
)
def test_table_7_7_scra(regime: SGRegime, grade: SCRAGrade, lt: float, st: float) -> None:
    assert _rw(regime, asset_class=AssetClass.BANK, scra_grade=grade) == pytest.approx(lt)
    assert _rw(
        regime, asset_class=AssetClass.BANK, scra_grade=grade, original_maturity_months=2.0
    ) == pytest.approx(st)


def test_para_7_3_59_grade_a_30pct(regime: SGRegime) -> None:
    out = _rw(
        regime, asset_class=AssetClass.BANK, scra_grade=SCRAGrade.A, scra_grade_a_enhanced=True
    )
    assert out == pytest.approx(0.30)
    # enhanced flag ignored for Grade B
    out_b = _rw(
        regime, asset_class=AssetClass.BANK, scra_grade=SCRAGrade.B, scra_grade_a_enhanced=True
    )
    assert out_b == pytest.approx(0.75)
    assert p.SCRA_A_ENHANCED_CET1 == 0.14 and p.SCRA_A_ENHANCED_LEVERAGE == 0.05


def test_unrated_bank_without_grade_is_grade_c(regime: SGRegime) -> None:
    assert _rw(regime, asset_class=AssetClass.BANK) == pytest.approx(1.50)


def test_para_7_3_62_sovereign_floor(regime: SGRegime) -> None:
    kw: dict[str, Any] = {
        "asset_class": AssetClass.BANK,
        "scra_grade": SCRAGrade.A,
        "sovereign_rating": R.BB_PLUS_TO_BB_MINUS,
        "flags": {"foreign_currency_exposure": True},
    }
    assert _rw(regime, **kw) == pytest.approx(1.00)
    # Para 7.3.63: self-liquidating trade items < 1 year exempt
    assert _rw(regime, **kw, is_trade_related=True, original_maturity_months=6.0) == pytest.approx(
        0.20
    )


def test_para_7_3_57_due_diligence_uplift(regime: SGRegime) -> None:
    out = _rw(
        regime,
        asset_class=AssetClass.BANK,
        rating=R.A_PLUS_TO_A_MINUS,
        flags={"due_diligence_uplift": True},
    )
    assert out == pytest.approx(0.50)


def test_para_7_3_55_unrated_floors(regime: SGRegime) -> None:
    assert _rw(
        regime,
        asset_class=AssetClass.BANK,
        scra_grade=SCRAGrade.A,
        original_maturity_months=2.0,
        flags={"st_issue_rw_50_or_100": True},
    ) == pytest.approx(1.00)
    assert _rw(
        regime,
        asset_class=AssetClass.BANK,
        scra_grade=SCRAGrade.A,
        flags={"st_issue_rw_150": True},
    ) == pytest.approx(1.50)


# =========================================================================
#  Covered bonds -- Tables 7-8, 7-9
# =========================================================================

TABLE_7_8 = [0.10, 0.20, 0.20, 0.50, 0.50, 1.00]


@pytest.mark.parametrize("rating,rw", list(zip(RATED, TABLE_7_8, strict=True)))
def test_table_7_8_covered_bond_rated(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    out = _rw(regime, asset_class=AssetClass.COVERED_BOND, rating=rating, covered_bond_rated=True)
    assert out == pytest.approx(rw)


@pytest.mark.parametrize(
    "issuer_rw,rw",
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
def test_table_7_9_covered_bond_unrated(issuer_rw: float, rw: float) -> None:
    assert cr.covered_bond_rw(False, R.UNRATED, issuer_rw) == pytest.approx(rw)


def test_table_7_9_via_issuer(regime: SGRegime) -> None:
    # Issuing bank rated A (Table 7-5: 30%) -> 15%
    out = _rw(regime, asset_class=AssetClass.COVERED_BOND, rating=R.A_PLUS_TO_A_MINUS)
    assert out == pytest.approx(0.15)
    # Unrated issuer Grade A enhanced (30%) -> 15%; Grade B (75%) -> 35%
    assert _rw(
        regime,
        asset_class=AssetClass.COVERED_BOND,
        scra_grade=SCRAGrade.A,
        scra_grade_a_enhanced=True,
    ) == pytest.approx(0.15)
    assert _rw(
        regime, asset_class=AssetClass.COVERED_BOND, scra_grade=SCRAGrade.B
    ) == pytest.approx(0.35)


# =========================================================================
#  Corporates -- Tables 7-10, 7-12; SME threshold
# =========================================================================

TABLE_7_10 = [0.20, 0.50, 0.75, 1.00, 1.50, 1.50, 1.00]
TABLE_7_12 = [0.20, 0.50, 0.75, 1.00, 1.50, 1.50, 0.85]


@pytest.mark.parametrize("rating,rw", list(zip(ALL_RATINGS, TABLE_7_10, strict=True)))
def test_table_7_10_general_corporate(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    assert _rw(regime, asset_class=AssetClass.CORPORATE, rating=rating) == pytest.approx(rw)


@pytest.mark.parametrize("rating,rw", list(zip(ALL_RATINGS, TABLE_7_12, strict=True)))
def test_table_7_12_corporate_sme(regime: SGRegime, rating: RatingBucket, rw: float) -> None:
    out = _rw(regime, asset_class=AssetClass.CORPORATE_SME, rating=rating, annual_turnover=80.0)
    assert out == pytest.approx(rw)


def test_sme_revenue_threshold_boundary(regime: SGRegime) -> None:
    # S$100m inclusive (para 7.3.4)
    assert _rw(regime, asset_class=AssetClass.CORPORATE, annual_turnover=100.0) == pytest.approx(
        0.85
    )
    assert _rw(
        regime, asset_class=AssetClass.CORPORATE_SME, annual_turnover=100.01
    ) == pytest.approx(1.00)
    assert _rw(regime, asset_class=AssetClass.CORPORATE, is_sme=True) == pytest.approx(0.85)


def test_no_investment_grade_corporate_option(regime: SGRegime) -> None:
    # MAS 637 has no 65% IG option for unrated corporates
    assert _rw(regime, asset_class=AssetClass.CORPORATE, is_investment_grade=True) == pytest.approx(
        1.0
    )


# =========================================================================
#  Specialised lending -- Tables 7-14, 7-15
# =========================================================================

TABLE_7_14 = [0.20, 0.50, 0.75, 1.00, 1.50, 1.50]


@pytest.mark.parametrize("rating,rw", list(zip(RATED, TABLE_7_14, strict=True)))
@pytest.mark.parametrize(
    "ac",
    [
        AssetClass.SPECIALISED_LENDING_PF,
        AssetClass.SPECIALISED_LENDING_OF,
        AssetClass.SPECIALISED_LENDING_CF,
    ],
)
def test_table_7_14_sl_rated(
    regime: SGRegime, ac: AssetClass, rating: RatingBucket, rw: float
) -> None:
    assert _rw(regime, asset_class=ac, rating=rating) == pytest.approx(rw)


@pytest.mark.parametrize(
    "ac,phase,rw",
    [
        (AssetClass.SPECIALISED_LENDING_PF, PFPhase.HIGH_QUALITY_OPERATIONAL, 0.80),
        (AssetClass.SPECIALISED_LENDING_PF, PFPhase.OPERATIONAL, 1.00),
        (AssetClass.SPECIALISED_LENDING_PF, PFPhase.PRE_OPERATIONAL, 1.30),
        (AssetClass.SPECIALISED_LENDING_PF, None, 1.30),
        (AssetClass.SPECIALISED_LENDING_OF, None, 1.00),
        (AssetClass.SPECIALISED_LENDING_CF, None, 1.00),
    ],
)
def test_table_7_15_sl_unrated(
    regime: SGRegime, ac: AssetClass, phase: PFPhase | None, rw: float
) -> None:
    assert _rw(regime, asset_class=ac, pf_phase=phase) == pytest.approx(rw)


# =========================================================================
#  Equity and subordinated debt -- paras 7.3.80-7.3.85, Table 7-16
# =========================================================================

TABLE_7_16 = [
    (date(2024, 7, 1), 1.60, 1.30),
    (date(2025, 12, 31), 2.20, 1.60),
    (date(2026, 12, 31), 2.80, 1.90),
    (date(2027, 12, 31), 3.40, 2.20),
    (date(2028, 12, 31), 4.00, 2.50),
]


@pytest.mark.parametrize("start,spec,other", TABLE_7_16)
def test_table_7_16_equity_phase_in(start: date, spec: float, other: float) -> None:
    assert cr.equity_phase_in_rw(start, True) == pytest.approx(spec)
    assert cr.equity_phase_in_rw(start, False) == pytest.approx(other)


def test_table_7_16_day_before_step() -> None:
    assert cr.equity_phase_in_rw(date(2025, 12, 30), False) == pytest.approx(1.30)
    assert cr.equity_phase_in_rw(date(2026, 12, 30), True) == pytest.approx(2.20)
    assert cr.equity_phase_in_rw(date(2035, 1, 1), True) == pytest.approx(4.00)
    # before the Notice's equity regime: fully phased-in (conservative)
    assert cr.equity_phase_in_rw(date(2024, 6, 30), False) == pytest.approx(2.50)


@pytest.mark.parametrize(
    "et,rw_2026",
    [
        (EquityType.SPECULATIVE_UNLISTED, 2.20),
        (EquityType.GENERAL, 1.60),
        (EquityType.PUBLICLY_TRADED, 1.60),
        (EquityType.NON_PUBLIC, 1.60),
        (EquityType.LEGISLATIVE_PROGRAMME, 1.60),
        (None, 1.60),
        (EquityType.SIGNIFICANT_FI, 2.50),
    ],
)
def test_equity_types_as_of_2026(regime: SGRegime, et: EquityType | None, rw_2026: float) -> None:
    assert _rw(regime, asset_class=AssetClass.EQUITY, equity_type=et) == pytest.approx(rw_2026)


def test_equity_fully_phased(regime: SGRegime) -> None:
    r29 = SGRegime(as_of=date(2029, 1, 1))
    assert _rw(r29, asset_class=AssetClass.EQUITY) == pytest.approx(2.50)
    assert (
        _rw(r29, asset_class=AssetClass.EQUITY, equity_type=EquityType.SPECULATIVE_UNLISTED) == 4.0
    )


def test_major_stake_400(regime: SGRegime) -> None:
    out = _rw(regime, asset_class=AssetClass.EQUITY, flags={"major_stake_solo_400": True})
    assert out == pytest.approx(4.00)


def test_subordinated_debt(regime: SGRegime) -> None:
    assert _rw(regime, asset_class=AssetClass.SUBORDINATED_DEBT, rating=R.AAA_TO_AA_MINUS) == 1.50


def test_major_stake_1250_worked_example() -> None:
    # ETC = 100: individual limit 15, aggregate limit 60.
    # Exposures 20, 15, 15, 15: individual excess 5 on the first; capped portions 15 x 4 = 60;
    # aggregate excess = 65 - 60 = 5; ratio 5/60.
    out = cr.major_stake_1250_amounts([20.0, 15.0, 15.0, 15.0], 100.0)
    assert out[0] == pytest.approx(5.0 + 15.0 * 5.0 / 60.0)
    assert out[1] == pytest.approx(15.0 * 5.0 / 60.0)
    assert sum(out) == pytest.approx(10.0)
    assert cr.major_stake_1250_amounts([10.0, 10.0], 100.0) == [0.0, 0.0]


# =========================================================================
#  Retail -- Table 7-17, para 7.3.87
# =========================================================================


def test_table_7_17_retail(regime: SGRegime) -> None:
    assert _rw(regime, asset_class=AssetClass.RETAIL_TRANSACTOR) == pytest.approx(0.45)
    assert _rw(regime, asset_class=AssetClass.RETAIL_REGULATORY, is_transactor=True) == 0.45
    assert _rw(regime, asset_class=AssetClass.RETAIL_REGULATORY) == pytest.approx(0.75)
    assert _rw(regime, asset_class=AssetClass.RETAIL_OTHER) == pytest.approx(1.00)


def test_regulatory_retail_s2m_cap(regime: SGRegime) -> None:
    kw: dict[str, Any] = {"asset_class": AssetClass.RETAIL_REGULATORY}
    assert _rw(regime, **kw, aggregate_retail_exposure_to_obligor=2.0) == pytest.approx(0.75)
    assert _rw(regime, **kw, aggregate_retail_exposure_to_obligor=2.01) == pytest.approx(1.00)
    assert _rw(regime, **kw, meets_regulatory_retail_criteria=False) == pytest.approx(1.00)


def test_failed_small_business_retail_goes_to_corporate_sme(regime: SGRegime) -> None:
    out = _rw(
        regime,
        asset_class=AssetClass.RETAIL_REGULATORY,
        is_sme=True,
        meets_regulatory_retail_criteria=False,
    )
    assert out == pytest.approx(0.85)


# =========================================================================
#  Real estate -- Tables 7-18 to 7-21, paras 7.3.88-7.3.99
# =========================================================================

RRE_CASES = [
    (0.50, 0.20, 0.30),
    (0.5001, 0.25, 0.35),
    (0.60, 0.25, 0.35),
    (0.6001, 0.30, 0.45),
    (0.80, 0.30, 0.45),
    (0.8001, 0.40, 0.60),
    (0.90, 0.40, 0.60),
    (0.9001, 0.50, 0.75),
    (1.00, 0.50, 0.75),
    (1.0001, 0.70, 1.05),
    (0.10, 0.20, 0.30),
    (1.50, 0.70, 1.05),
]


@pytest.mark.parametrize("ltv,general,cfd", RRE_CASES)
def test_tables_7_18_7_19_rre(regime: SGRegime, ltv: float, general: float, cfd: float) -> None:
    assert _rw(regime, asset_class=AssetClass.RESIDENTIAL_RE, ltv=ltv) == pytest.approx(general)
    assert _rw(
        regime, asset_class=AssetClass.RESIDENTIAL_RE, ltv=ltv, is_cash_flow_dependent=True
    ) == pytest.approx(cfd)


@pytest.mark.parametrize(
    "ltv,rating,individual,sme,rw",
    [
        (0.60, R.UNRATED, False, False, 0.60),  # min(60%, 100%)
        (0.60, R.AAA_TO_AA_MINUS, False, False, 0.20),  # min(60%, 20%)
        (0.60, R.UNRATED, True, False, 0.60),  # min(60%, 75%)
        (0.6001, R.UNRATED, False, False, 1.00),  # counterparty RW
        (0.6001, R.UNRATED, True, False, 0.75),
        (0.6001, R.UNRATED, False, True, 0.85),
        (0.90, R.A_PLUS_TO_A_MINUS, False, False, 0.50),
    ],
)
def test_table_7_20_cre_general(
    regime: SGRegime, ltv: float, rating: RatingBucket, individual: bool, sme: bool, rw: float
) -> None:
    out = _rw(
        regime,
        asset_class=AssetClass.COMMERCIAL_RE,
        ltv=ltv,
        rating=rating,
        is_sme=sme,
        flags={"obligor_is_individual": individual},
    )
    assert out == pytest.approx(rw)


@pytest.mark.parametrize(
    "ltv,rw",
    [(0.30, 0.70), (0.60, 0.70), (0.6001, 0.90), (0.80, 0.90), (0.8001, 1.10), (1.2, 1.10)],
)
def test_table_7_21_cre_cash_flow(regime: SGRegime, ltv: float, rw: float) -> None:
    out = _rw(regime, asset_class=AssetClass.COMMERCIAL_RE, ltv=ltv, is_cash_flow_dependent=True)
    assert out == pytest.approx(rw)


def test_other_real_estate(regime: SGRegime) -> None:
    # para 7.3.98: individual 75%, small business 85%, else unsecured obligor RW
    assert _rw(
        regime, asset_class=AssetClass.RESIDENTIAL_RE, ltv=0.5, is_regulatory_real_estate=False
    ) == pytest.approx(0.75)
    assert _rw(
        regime,
        asset_class=AssetClass.COMMERCIAL_RE,
        ltv=0.5,
        is_regulatory_real_estate=False,
        is_sme=True,
    ) == pytest.approx(0.85)
    assert _rw(
        regime,
        asset_class=AssetClass.COMMERCIAL_RE,
        ltv=0.5,
        is_regulatory_real_estate=False,
        rating=R.BB_PLUS_TO_BB_MINUS,
    ) == pytest.approx(1.00)
    # para 7.3.99: cash-flow dependent 150%
    assert _rw(
        regime,
        asset_class=AssetClass.COMMERCIAL_RE,
        ltv=0.5,
        is_regulatory_real_estate=False,
        is_cash_flow_dependent=True,
    ) == pytest.approx(1.50)
    # Missing LTV -> other real estate
    assert _rw(regime, asset_class=AssetClass.RESIDENTIAL_RE) == pytest.approx(0.75)


def test_para_7_3_96_junior_charge(regime: SGRegime) -> None:
    kw: dict[str, Any] = {
        "asset_class": AssetClass.RESIDENTIAL_RE,
        "flags": {"junior_charge": True},
    }
    assert _rw(regime, **kw, ltv=0.50) == pytest.approx(0.20)  # lowest bucket: no multiplier
    assert _rw(regime, **kw, ltv=0.70) == pytest.approx(0.375)  # 30% x 1.25
    assert _rw(regime, **kw, ltv=0.95) == pytest.approx(0.625)  # 50% x 1.25
    assert _rw(regime, **kw, ltv=1.20) == pytest.approx(0.75)  # 87.5% capped at 75% (other RE)
    cfd = _rw(regime, **kw, ltv=1.20, is_cash_flow_dependent=True)
    assert cfd == pytest.approx(1.3125)  # 105% x 1.25, below the 150% cap


def test_adc(regime: SGRegime) -> None:
    assert _rw(regime, asset_class=AssetClass.LAND_ADC) == pytest.approx(1.50)
    kw: dict[str, Any] = {"asset_class": AssetClass.LAND_ADC, "flags": {"adc_secured_by_rre": True}}
    assert _rw(regime, **kw, ltv=0.80) == pytest.approx(1.00)
    assert _rw(regime, **kw, ltv=0.8001) == pytest.approx(1.50)
    assert _rw(
        regime,
        asset_class=AssetClass.LAND_ADC,
        ltv=0.5,
        flags={"adc_secured_by_rre": True, "adc_meets_underwriting": False},
    ) == pytest.approx(1.50)


# =========================================================================
#  Currency mismatch -- para 7.3.107
# =========================================================================


@pytest.mark.parametrize(
    "kw,rw",
    [
        ({"asset_class": AssetClass.RETAIL_REGULATORY}, 1.125),
        ({"asset_class": AssetClass.RETAIL_TRANSACTOR}, 0.675),
        ({"asset_class": AssetClass.RETAIL_OTHER}, 1.50),
        ({"asset_class": AssetClass.RESIDENTIAL_RE, "ltv": 0.75}, 0.45),
        (
            {"asset_class": AssetClass.RESIDENTIAL_RE, "ltv": 1.10, "is_cash_flow_dependent": True},
            1.50,
        ),
        ({"asset_class": AssetClass.CORPORATE}, 1.00),  # out of scope
        ({"asset_class": AssetClass.COMMERCIAL_RE, "ltv": 0.7}, 1.00),  # out of scope
    ],
)
def test_currency_mismatch(regime: SGRegime, kw: dict[str, Any], rw: float) -> None:
    assert _rw(regime, currency_matches_borrower_income=False, **kw) == pytest.approx(rw)


def test_currency_mismatch_hedged_or_business(regime: SGRegime) -> None:
    assert _rw(
        regime,
        asset_class=AssetClass.RETAIL_REGULATORY,
        currency_matches_borrower_income=False,
        flags={"fx_hedged": True},
    ) == pytest.approx(0.75)
    assert _rw(
        regime,
        asset_class=AssetClass.RETAIL_REGULATORY,
        currency_matches_borrower_income=False,
        is_sme=True,
    ) == pytest.approx(0.75)


# =========================================================================
#  Defaulted -- Table 7-22, para 7.3.110
# =========================================================================


@pytest.mark.parametrize("prov,rw", [(0.0, 1.50), (0.1999, 1.50), (0.20, 1.00), (0.5, 1.00)])
def test_table_7_22_defaulted(regime: SGRegime, prov: float, rw: float) -> None:
    assert _rw(
        regime, asset_class=AssetClass.DEFAULTED, specific_provision_pct=prov
    ) == pytest.approx(rw)
    assert _rw(
        regime, asset_class=AssetClass.CORPORATE, is_defaulted=True, specific_provision_pct=prov
    ) == pytest.approx(rw)


def test_para_7_3_110_defaulted_rre(regime: SGRegime) -> None:
    assert _rw(regime, asset_class=AssetClass.RESIDENTIAL_RE, ltv=0.7, is_defaulted=True) == 1.00
    assert _rw(regime, asset_class=AssetClass.DEFAULTED, flags={"secured_by_rre": True}) == 1.00
    cfd = _rw(
        regime,
        asset_class=AssetClass.RESIDENTIAL_RE,
        ltv=0.7,
        is_defaulted=True,
        is_cash_flow_dependent=True,
    )
    assert cfd == pytest.approx(1.50)


# =========================================================================
#  Other assets -- paras 7.3.40, 7.3.41, 7.3.104-7.3.106
# =========================================================================


@pytest.mark.parametrize(
    "flags,rw",
    [
        ({"cash_item": True}, 0.0),
        ({"gold_bullion": True}, 0.0),
        ({"cash_item_in_collection": True}, 0.20),
        ({"threshold_250": True}, 2.50),
        ({"major_stake_solo_400": True}, 4.00),
        ({"residual_value_leased_asset": True}, 1.00),
        ({}, 1.00),
    ],
)
def test_other_assets(regime: SGRegime, flags: dict[str, bool], rw: float) -> None:
    assert _rw(regime, asset_class=AssetClass.OTHER_ASSETS, flags=flags) == pytest.approx(rw)


def test_every_asset_class_is_handled(regime: SGRegime) -> None:
    for ac in AssetClass:
        res = regime.risk_weight(_exp(asset_class=ac, ltv=0.5))
        assert res.risk_weight >= 0.0
        assert res.citation


# =========================================================================
#  CCFs -- Table 7B-1
# =========================================================================


@pytest.mark.parametrize(
    "cat,ccf",
    [
        (OBSCategory.DIRECT_CREDIT_SUBSTITUTE, 1.00),
        (OBSCategory.SECURITIES_LENDING_COLLATERAL, 1.00),
        (OBSCategory.FORWARD_ASSET_PURCHASE, 1.00),
        (OBSCategory.OTHER_100, 1.00),
        (OBSCategory.NIF_RUF, 0.50),
        (OBSCategory.TRANSACTION_RELATED_CONTINGENT, 0.50),
        (OBSCategory.COMMITMENT_OTHER, 0.40),
        (OBSCategory.SHORT_TERM_TRADE_LC, 0.20),
        (OBSCategory.UNCONDITIONALLY_CANCELLABLE, 0.10),
    ],
)
def test_table_7b1_ccf(regime: SGRegime, cat: OBSCategory, ccf: float) -> None:
    e = _exp(
        asset_class=AssetClass.CORPORATE,
        on_balance_amount=0.0,
        off_balance_notional=50.0,
        obs_category=cat,
    )
    assert regime.ccf(e) == pytest.approx(ccf)
    res = regime.risk_weight(e)
    assert res.exposure_amount == pytest.approx(50.0 * ccf)
    assert res.rwa == pytest.approx(50.0 * ccf * 1.0)


def test_commitment_ccf_regardless_of_maturity(regime: SGRegime) -> None:
    for years in (0.5, 1.0, 5.0):
        e = _exp(
            asset_class=AssetClass.CORPORATE,
            off_balance_notional=10.0,
            obs_category=OBSCategory.COMMITMENT_OTHER,
            commitment_original_maturity_years=years,
        )
        assert regime.ccf(e) == 0.40


def test_trade_lc_maturity_cutoff() -> None:
    assert cr.ccf_for(OBSCategory.SHORT_TERM_TRADE_LC, 11.9) == 0.20
    assert cr.ccf_for(OBSCategory.SHORT_TERM_TRADE_LC, 12.0) == 1.00  # TODO: VERIFY placeholder
    assert cr.ccf_for(None) == 1.00
    assert cr.ccf_commitment_on_item(0.40, 0.20) == 0.20  # Annex 7B para 1.2


# =========================================================================
#  CRM -- Annex 7J, Annex 7H
# =========================================================================

HAIRCUT_CELLS = [
    ("SOVEREIGN_CQS1_LE1Y", 0.005),
    ("SOVEREIGN_CQS1_1Y_5Y", 0.02),
    ("SOVEREIGN_CQS1_GT5Y", 0.04),
    ("OTHER_CQS1_LE1Y", 0.01),
    ("OTHER_CQS1_1Y_3Y", 0.03),
    ("OTHER_CQS1_3Y_5Y", 0.04),
    ("OTHER_CQS1_5Y_10Y", 0.06),
    ("OTHER_CQS1_GT10Y", 0.12),
    ("SECURITISATION_CQS1_LE1Y", 0.02),
    ("SECURITISATION_CQS1_1Y_5Y", 0.08),
    ("SECURITISATION_CQS1_GT5Y", 0.16),
    ("SOVEREIGN_CQS2_3_LE1Y", 0.01),
    ("SOVEREIGN_CQS2_3_1Y_5Y", 0.03),
    ("SOVEREIGN_CQS2_3_GT5Y", 0.06),
    ("OTHER_CQS2_3_LE1Y", 0.02),
    ("OTHER_CQS2_3_1Y_3Y", 0.04),
    ("OTHER_CQS2_3_3Y_5Y", 0.06),
    ("OTHER_CQS2_3_5Y_10Y", 0.12),
    ("OTHER_CQS2_3_GT10Y", 0.20),
    ("SECURITISATION_CQS2_3_LE1Y", 0.04),
    ("SECURITISATION_CQS2_3_1Y_5Y", 0.12),
    ("SECURITISATION_CQS2_3_GT5Y", 0.24),
    ("SOVEREIGN_CQS4", 0.15),
    ("GOLD", 0.20),
    ("MAIN_INDEX_EQUITY", 0.20),
    ("OTHER_LISTED_EQUITY", 0.30),
    ("CASH_SAME_CURRENCY", 0.0),
    ("TRADING_BOOK_OTHER", 0.30),
    ("NON_ELIGIBLE_LENT", 0.30),
]


@pytest.mark.parametrize("key,h10", HAIRCUT_CELLS)
def test_table_7j1_haircuts(key: str, h10: float) -> None:
    assert cr.supervisory_haircut(key) == pytest.approx(h10)


def test_table_7j1_complete() -> None:
    assert set(p.SUPERVISORY_HAIRCUTS) == {k for k, _ in HAIRCUT_CELLS}


def test_haircut_scaling_annex_7j_3_4() -> None:
    # H = H10 sqrt((NR + TM - 1)/10)
    assert cr.scale_haircut(0.20, 5) == pytest.approx(0.20 * math.sqrt(0.5))
    assert cr.scale_haircut(0.20, 20) == pytest.approx(0.20 * math.sqrt(2.0))
    assert cr.scale_haircut(0.08, 10, remargin_days=5) == pytest.approx(0.08 * math.sqrt(1.4))
    assert p.MIN_HOLDING_PERIOD_DAYS == {
        "REPO_STYLE": 5,
        "CAPITAL_MARKET": 10,
        "SECURED_LENDING": 20,
        "MIXED_NETTING_SET": 10,
    }
    assert p.FX_MISMATCH_HAIRCUT == 0.08
    assert p.LARGE_NETTING_SET_HOLDING_DAYS == 20 and p.LARGE_NETTING_SET_TRADES == 5000


def test_fcca_formula() -> None:
    # E* = max(0, E(1+HE) - C(1-HC-HFX))
    assert cr.exposure_after_collateral(100, 60, 0.0, 0.20, 0.08) == pytest.approx(100 - 60 * 0.72)
    assert cr.exposure_after_collateral(100, 200, 0.0, 0.0, 0.0) == 0.0
    assert cr.exposure_after_collateral(100, 50, 0.10, 0.0, 0.0) == pytest.approx(60.0)


def test_fcca_end_to_end(regime: SGRegime) -> None:
    # Corporate unrated (100%), E=100, main-index equity collateral 50 under secured lending:
    # HC = 0.20 x sqrt(2) ; E* = 100 - 50 (1 - HC)
    res = regime.risk_weight(
        _exp(
            asset_class=AssetClass.CORPORATE,
            financial_collateral_value=50.0,
            collateral_haircut_class="MAIN_INDEX_EQUITY",
        )
    )
    hc = 0.20 * math.sqrt(2.0)
    assert res.exposure_amount == pytest.approx(100 - 50 * (1 - hc))
    assert res.rwa == pytest.approx(res.exposure_amount * 1.0)
    # Repo-style with FX mismatch: HC = 0.2 sqrt(0.5), HFX = 0.08 sqrt(0.5)
    res2 = regime.risk_weight(
        _exp(
            asset_class=AssetClass.CORPORATE,
            financial_collateral_value=50.0,
            collateral_haircut_class="MAIN_INDEX_EQUITY",
            flags={"repo_style": True, "collateral_currency_mismatch": True},
        )
    )
    assert res2.exposure_amount == pytest.approx(100 - 50 * (1 - 0.28 * math.sqrt(0.5)))
    # Unknown haircut class -> not recognised
    res3 = regime.risk_weight(
        _exp(asset_class=AssetClass.CORPORATE, financial_collateral_value=50.0)
    )
    assert res3.exposure_amount == pytest.approx(100.0)


def test_maturity_mismatch_annex_7h_7_4() -> None:
    # P=100, t=2, T=4 -> 100 x 1.75 / 3.75
    assert cr.maturity_mismatch_adjust(100, 2.0, 4.0) == pytest.approx(100 * 1.75 / 3.75)
    # T capped at 5
    assert cr.maturity_mismatch_adjust(100, 3.0, 8.0) == pytest.approx(100 * 2.75 / 4.75)
    assert cr.maturity_mismatch_adjust(100, 5.0, 5.0) == 100  # no mismatch
    assert cr.maturity_mismatch_adjust(100, 0.2, 4.0) == 0.0  # residual < 3 months
    assert cr.maturity_mismatch_adjust(100, 2.0, 4.0, mitigant_original_years=0.9) == 0.0


def test_guarantee_substitution(regime: SGRegime) -> None:
    # Unrated corporate 100%, 60 guaranteed by AA sovereign (0%)
    res = regime.risk_weight(
        _exp(
            asset_class=AssetClass.CORPORATE,
            guarantee_amount=60.0,
            guarantor_asset_class=AssetClass.SOVEREIGN,
            guarantor_rating=R.AAA_TO_AA_MINUS,
        )
    )
    assert res.rwa == pytest.approx(40.0)
    assert res.risk_weight == pytest.approx(0.40)
    # FX mismatch: GA = 60 x 0.92
    res2 = regime.risk_weight(
        _exp(
            asset_class=AssetClass.CORPORATE,
            guarantee_amount=60.0,
            guarantor_asset_class=AssetClass.SOVEREIGN,
            guarantor_rating=R.AAA_TO_AA_MINUS,
            flags={"guarantee_currency_mismatch": True},
        )
    )
    assert res2.rwa == pytest.approx(100 - 60 * 0.92)
    # Guarantor not better than obligor -> not recognised
    res3 = regime.risk_weight(
        _exp(
            asset_class=AssetClass.CORPORATE,
            rating=R.AAA_TO_AA_MINUS,
            guarantee_amount=60.0,
            guarantor_asset_class=AssetClass.CORPORATE,
            guarantor_rating=R.BBB_PLUS_TO_BBB_MINUS,
        )
    )
    assert res3.rwa == pytest.approx(20.0)


def test_guarantor_classes(regime: SGRegime) -> None:
    def g(
        ac: AssetClass, rating: RatingBucket, flags: dict[str, bool] | None = None
    ) -> float | None:
        return regime._credit.guarantor_rw(
            _exp(
                asset_class=AssetClass.CORPORATE,
                guarantor_asset_class=ac,
                guarantor_rating=rating,
                flags=flags or {},
            )
        )

    assert g(AssetClass.PSE, R.UNRATED) == 0.50
    assert g(AssetClass.MDB, R.UNRATED, {"guarantor_qualifying_mdb": True}) == 0.0
    assert g(AssetClass.BANK, R.UNRATED) == 0.75
    assert g(AssetClass.BANK, R.UNRATED, {"guarantor_scra_grade_a": True}) == 0.40
    assert g(AssetClass.BANK, R.A_PLUS_TO_A_MINUS) == 0.30
    assert g(AssetClass.CORPORATE, R.A_PLUS_TO_A_MINUS) == 0.50
    assert g(AssetClass.RETAIL_OTHER, R.UNRATED) is None


def test_credit_rwa_portfolio(regime: SGRegime) -> None:
    exps = [
        _exp(exposure_id="a", asset_class=AssetClass.CORPORATE),
        _exp(exposure_id="b", asset_class=AssetClass.RESIDENTIAL_RE, ltv=0.75),
        _exp(exposure_id="c", asset_class=AssetClass.CORPORATE, rating=R.A_PLUS_TO_A_MINUS),
    ]
    res = regime.credit_rwa(exps)
    assert res.total_exposure == pytest.approx(300.0)
    assert res.total_rwa == pytest.approx(100 + 30 + 50)
    assert res.rwa_by_class["7.3.1(g)(i) general corporate"] == pytest.approx(150.0)
    assert res.density == pytest.approx(0.6)
    assert len(res.line_items) == 3


# =========================================================================
#  Operational risk -- Part IX
# =========================================================================


def _op_inputs(scale: float, losses: list[float]) -> OpRiskInputs:
    return OpRiskInputs(
        interest_income=[1000 * scale] * 3,
        interest_expense=[400 * scale] * 3,
        interest_earning_assets=[30000 * scale] * 3,
        dividend_income=[10 * scale] * 3,
        fee_income=[300 * scale] * 3,
        fee_expense=[100 * scale] * 3,
        other_operating_income=[50 * scale] * 3,
        other_operating_expense=[80 * scale] * 3,
        net_pnl_trading_book=[100 * scale, -50 * scale, 30 * scale],
        net_pnl_banking_book=[20 * scale] * 3,
        annual_operational_losses=losses,
    )


def test_bic_footnote_901_example() -> None:
    # BI = S$50bn -> BIC = S$7.605bn
    assert orisk.business_indicator_component(50_000.0) == pytest.approx(7_605.0)


@pytest.mark.parametrize(
    "bi,bic",
    [
        (1_000.0, 120.0),
        (1_500.0, 180.0),
        (2_500.0, 300.0 + 30.0),
        (45_000.0, 5_400.0 + 1_305.0),
        (46_000.0, 5_520.0 + 1_335.0 + 30.0),
    ],
)
def test_bic_marginal_buckets(bi: float, bic: float) -> None:
    assert orisk.business_indicator_component(bi) == pytest.approx(bic)


def test_bi_components_and_small_bank() -> None:
    # ILDC = min(600, 675) + 10 = 610; SC = 300 + 80 = 380; FC = 60 + 20 = 80 -> BI = 1070
    res = SGRegime().operational_risk(_op_inputs(1.0, [50.0] * 10))
    assert res.components["ILDC"] == pytest.approx(610.0)
    assert res.components["SC"] == pytest.approx(380.0)
    assert res.components["FC"] == pytest.approx(80.0)
    assert res.business_indicator == pytest.approx(1070.0)
    assert res.ilm == 1.0  # BI <= S$1.5bn (para 9.1.8(a))
    assert res.loss_component is None
    assert res.capital == pytest.approx(128.4)
    assert res.rwa == pytest.approx(12.5 * 128.4)


def test_ildc_iea_cap_binds() -> None:
    inp = _op_inputs(1.0, [])
    inp.interest_earning_assets = [20000.0] * 3  # cap 450 < 600
    comps = orisk.business_indicator_components(inp)
    assert comps["ILDC"] == pytest.approx(450.0 + 10.0)


def test_large_bank_ilm_computed() -> None:
    # BI = 10,700 ; BIC = 1284 + 0.03 x 9200 = 1560
    res = SGRegime().operational_risk(_op_inputs(10.0, [104.0] * 10))
    assert res.business_indicator == pytest.approx(10_700.0)
    assert res.bic == pytest.approx(1_560.0)
    assert res.loss_component == pytest.approx(1_560.0)
    assert res.ilm == pytest.approx(1.0)  # LC = BIC
    res2 = SGRegime().operational_risk(_op_inputs(10.0, [208.0] * 10))
    assert res2.ilm == pytest.approx(math.log(math.e - 1 + 2.0**0.8))
    assert res2.capital == pytest.approx(1_560.0 * res2.ilm)
    # Low losses: ILM < 1 (no floor in MAS 637)
    res3 = SGRegime().operational_risk(_op_inputs(10.0, [10.0] * 10))
    assert res3.ilm < 1.0


def test_ilm_fallbacks() -> None:
    # fewer than 5 years -> ILM = 1 (para 9.1.15)
    assert SGRegime().operational_risk(_op_inputs(10.0, [500.0] * 4)).ilm == 1.0
    # 5 years accepted (para 9.1.14)
    assert SGRegime().operational_risk(_op_inputs(10.0, [500.0] * 5)).ilm > 1.0
    # loss-data criteria failed -> ILM = 1 (para 9.1.10)
    r = SGRegime(loss_data_criteria_met=False)
    assert r.operational_risk(_op_inputs(10.0, [500.0] * 10)).ilm == 1.0
    # small bank with MAS approval -> ILM computed
    r2 = SGRegime(small_bank_ilm_approved=True)
    assert r2.operational_risk(_op_inputs(1.0, [500.0] * 10)).ilm > 1.0


def test_lc_uses_last_10_years() -> None:
    losses = [1000.0] * 2 + [10.0] * 10
    assert orisk.loss_component(losses) == pytest.approx(150.0)
    assert orisk.internal_loss_multiplier(100.0, 0.0) == 1.0


def test_oprisk_thresholds() -> None:
    assert p.LOSS_THRESHOLD_SMALL_SGD_M == 0.03
    assert p.LOSS_THRESHOLD_LARGE_SGD_M == 0.15
    assert p.BIC_TIER2_THRESHOLD_SGD_M == 1_500.0 and p.BIC_TIER3_THRESHOLD_SGD_M == 45_000.0


# =========================================================================
#  Output floor -- Table 5-3
# =========================================================================


@pytest.mark.parametrize(
    "year,factor",
    [
        (2023, 0.0),
        (2024, 0.50),
        (2025, 0.55),
        (2026, 0.60),
        (2027, 0.65),
        (2028, 0.70),
        (2029, 0.725),
        (2035, 0.725),
    ],
)
def test_table_5_3_output_floor(regime: SGRegime, year: int, factor: float) -> None:
    res = regime.output_floor(50.0, 100.0, year)
    assert res.floor_factor == pytest.approx(factor)
    assert res.applies is (factor > 0)
    assert res.floored_rwa == pytest.approx(max(50.0, factor * 100.0))


def test_output_floor_dates() -> None:
    assert of.floor_calibration(date(2024, 6, 30)) == 0.0
    assert of.floor_calibration(date(2024, 7, 1)) == 0.50
    assert of.floor_calibration(date(2028, 12, 31)) == 0.70
    assert of.floor_calibration(date(2029, 1, 1)) == 0.725


def test_annex_4a_worked_example() -> None:
    # Table 4A-1: nominated 76, standardised 140, 72.5% -> 101.5 binds
    res = of.output_floor(76.0, 140.0, 2029)
    assert res.floored_rwa == pytest.approx(101.5)
    assert res.add_on == pytest.approx(25.5)  # no 25% transitional cap


def test_output_floor_mas_specified() -> None:
    res = SGRegime(mas_floor_calibration=0.80).output_floor(50.0, 100.0, 2026)
    assert res.floor_factor == pytest.approx(0.80)
    assert of.output_floor(50.0, 100.0, 2026, 1.5).floor_factor == 1.0
    assert of.output_floor(50.0, 100.0, 2026, 0.5).floor_factor == 0.60  # lower ignored


# =========================================================================
#  Capital stack -- Part IV
# =========================================================================


def test_tables_4_1_4_2_minimums() -> None:
    d = SGRegime(is_dsib=True).capital_requirements()
    assert (d.cet1_minimum, d.tier1_minimum, d.total_capital_minimum) == (0.065, 0.08, 0.10)
    n = SGRegime(is_dsib=False).capital_requirements()
    assert (n.cet1_minimum, n.tier1_minimum, n.total_capital_minimum) == (0.045, 0.06, 0.08)
    assert d.conservation_buffer == 0.025
    assert d.leverage_minimum == 0.03
    assert d.leverage_buffer == 0.0
    assert d.systemic_risk_buffer == 0.0


def test_buffer_stack(regime: SGRegime) -> None:
    req = regime.capital_requirements(
        systemic_bucket_or_rate=0.0, countercyclical_rate=0.01, stress_buffer=0.02
    )
    assert req.stress_buffer == 0.0  # no SCB in MAS 637
    assert req.combined_buffer == pytest.approx(0.035)
    assert req.cet1_requirement == pytest.approx(0.10)
    with pytest.raises(ValueError):
        regime.capital_requirements(countercyclical_rate=-0.01)


def test_ccyb_weighted_average() -> None:
    rate = cs.countercyclical_buffer(
        {"SG": (60.0, 0.0, True), "HK": (30.0, 0.01, True), "XX": (10.0, 0.02, False)}
    )
    assert rate == pytest.approx(0.3 * 0.01)
    # foreign rate capped at 2.5%; Singapore not capped
    assert cs.countercyclical_buffer({"UK": (100.0, 0.03, True)}) == pytest.approx(0.025)
    assert cs.countercyclical_buffer({"SG": (100.0, 0.03, True)}) == pytest.approx(0.03)
    assert cs.countercyclical_buffer({}) == 0.0


@pytest.mark.parametrize(
    "cet1,ratio",
    [
        (0.060, 1.0),
        (0.065, 1.0),
        (0.07125, 1.0),
        (0.0713, 0.8),
        (0.0775, 0.8),
        (0.08375, 0.6),
        (0.084, 0.4),
        (0.09, 0.4),
        (0.0901, 0.0),
    ],
)
def test_table_4_3_dsib_conservation(cet1: float, ratio: float) -> None:
    assert cs.capital_conservation_ratio(cet1, 0.065, 0.025) == pytest.approx(ratio)


@pytest.mark.parametrize(
    "cet1,ratio",
    [(0.05125, 1.0), (0.0575, 0.8), (0.06375, 0.6), (0.07, 0.4), (0.0701, 0.0)],
)
def test_table_4_4_non_dsib_conservation(cet1: float, ratio: float) -> None:
    assert cs.capital_conservation_ratio(cet1, 0.045, 0.025) == pytest.approx(ratio)


@pytest.mark.parametrize(
    "cet1,ratio",
    [(0.0775, 1.0), (0.09, 0.8), (0.1025, 0.6), (0.115, 0.4), (0.1151, 0.0)],
)
def test_table_4_6_dsib_with_ccyb(cet1: float, ratio: float) -> None:
    assert cs.capital_conservation_ratio(cet1, 0.065, 0.05) == pytest.approx(ratio)


@pytest.mark.parametrize(
    "cet1,ratio", [(0.0575, 1.0), (0.07, 0.8), (0.0825, 0.6), (0.095, 0.4), (0.0951, 0.0)]
)
def test_table_4_7_non_dsib_with_ccyb(cet1: float, ratio: float) -> None:
    assert cs.capital_conservation_ratio(cet1, 0.045, 0.05) == pytest.approx(ratio)


# =========================================================================
#  SA-CCR -- Annex 7D
# =========================================================================


def test_saccr_alpha_all_counterparties(regime: SGRegime) -> None:
    for nonfin, pension in ((False, False), (True, False), (False, True)):
        ns = SACCRNettingSetInput(
            netting_set_id="n",
            replacement_cost=10.0,
            aggregate_addon=50.0,
            mtm=10.0,
            counterparty_is_nonfinancial=nonfin,
            counterparty_is_pension_scheme=pension,
        )
        res = regime.saccr_ead(ns)
        assert res.alpha == 1.4
        assert res.multiplier == 1.0
        assert res.ead == pytest.approx(1.4 * 60.0)


def test_saccr_multiplier_worked_example(regime: SGRegime) -> None:
    ns = SACCRNettingSetInput(
        netting_set_id="n",
        replacement_cost=0.0,
        aggregate_addon=50.0,
        mtm=-20.0,
        net_collateral=0.0,
    )
    res = regime.saccr_ead(ns)
    m = 0.05 + 0.95 * math.exp(-20.0 / (2 * 0.95 * 50.0))
    assert res.multiplier == pytest.approx(m)
    assert res.pfe == pytest.approx(m * 50.0)
    assert res.ead == pytest.approx(1.4 * m * 50.0)
    # deep out of the money -> floor 5%
    assert saccr.pfe_multiplier(-1e6, 1.0) == pytest.approx(0.05)
    assert saccr.pfe_multiplier(-5.0, 0.0) == 1.0


def test_saccr_maturity_factors_and_sd() -> None:
    assert saccr.maturity_factor_unmargined(0.25) == pytest.approx(0.5)
    assert saccr.maturity_factor_unmargined(5.0) == 1.0
    assert saccr.maturity_factor_unmargined(0.0) == pytest.approx(math.sqrt(10 / 250))
    assert saccr.maturity_factor_margined(10.0) == pytest.approx(1.5 * math.sqrt(10 / 250))
    assert saccr.supervisory_duration(0.0, 5.0) == pytest.approx((1 - math.exp(-0.25)) / 0.05)
    assert saccr.supervisory_duration(-1.0, 1.0) == pytest.approx((1 - math.exp(-0.05)) / 0.05)


TABLE_7D1 = [
    ("IR", 0.005, None, 0.50),
    ("FX", 0.04, None, 0.15),
    ("CREDIT_SN_CQS1", 0.0038, 0.50, 1.00),
    ("CREDIT_SN_CQS2", 0.0042, 0.50, 1.00),
    ("CREDIT_SN_CQS3", 0.0054, 0.50, 1.00),
    ("CREDIT_SN_CQS4", 0.0106, 0.50, 1.00),
    ("CREDIT_SN_CQS5", 0.016, 0.50, 1.00),
    ("CREDIT_SN_CQS6", 0.06, 0.50, 1.00),
    ("CREDIT_INDEX_CQS1_3", 0.0038, 0.80, 0.80),
    ("CREDIT_INDEX_CQS4_6", 0.0106, 0.80, 0.80),
    ("EQUITY_SN", 0.32, 0.50, 1.20),
    ("EQUITY_INDEX", 0.20, 0.80, 0.75),
    ("COMMODITY_ELECTRICITY", 0.40, 0.40, 1.50),
    ("COMMODITY_OIL_GAS", 0.18, 0.40, 0.70),
    ("COMMODITY_METALS", 0.18, 0.40, 0.70),
    ("COMMODITY_AGRICULTURAL", 0.18, 0.40, 0.70),
    ("COMMODITY_OTHER", 0.18, 0.40, 0.70),
]


@pytest.mark.parametrize("key,sf,rho,vol", TABLE_7D1)
def test_table_7d1(key: str, sf: float, rho: float | None, vol: float) -> None:
    assert p.SACCR_SUPERVISORY_PARAMS[key] == (pytest.approx(sf), rho, pytest.approx(vol))


def test_saccr_credit_sf_helpers() -> None:
    assert saccr.credit_supervisory_factor(R.AAA_TO_AA_MINUS) == 0.0038
    assert saccr.credit_supervisory_factor(R.BELOW_B_MINUS) == 0.06
    assert saccr.credit_supervisory_factor(R.UNRATED) == 0.0106
    assert saccr.credit_supervisory_factor(R.BBB_PLUS_TO_BBB_MINUS, index=True) == 0.0038
    assert saccr.credit_supervisory_factor(R.UNRATED, index=True) == 0.0106
    assert saccr.adjusted_supervisory_factor(0.005, basis=True) == pytest.approx(0.0025)
    assert saccr.adjusted_supervisory_factor(0.005, volatility=True) == pytest.approx(0.025)


# =========================================================================
#  BA-CVA -- Tables 8-26, 8-27
# =========================================================================

TABLE_8_26 = [
    ("SOVEREIGN", 0.005, 0.02),
    ("PSE", 0.01, 0.04),
    ("FINANCIAL", 0.05, 0.12),
    ("BASIC_MATERIALS", 0.03, 0.07),
    ("CONSUMER", 0.03, 0.085),
    ("TECHNOLOGY", 0.02, 0.055),
    ("HEALTHCARE", 0.015, 0.05),
    ("OTHER", 0.05, 0.12),
]


@pytest.mark.parametrize("sector,ig,hy", TABLE_8_26)
def test_table_8_26(sector: str, ig: float, hy: float) -> None:
    assert cva.counterparty_risk_weight(sector, "IG") == pytest.approx(ig)
    assert cva.counterparty_risk_weight(sector, "HY_NR") == pytest.approx(hy)


def test_table_8_27_and_scalars() -> None:
    assert p.BA_CVA_HEDGE_CORRELATION == {"COUNTERPARTY": 1.0, "RELATED": 0.8, "SECTOR": 0.5}
    assert (p.BA_CVA_DISCOUNT_SCALAR, p.BA_CVA_RHO, p.BA_CVA_ALPHA, p.BA_CVA_BETA) == (
        0.65,
        0.5,
        1.4,
        0.25,
    )
    assert cva.counterparty_risk_weight("unknown-sector", "IG") == 0.05


def test_ba_cva_reduced_single_counterparty(regime: SGRegime) -> None:
    df = (1 - math.exp(-0.25)) / 0.25
    s = 0.05 * 5.0 * 100.0 * df / 1.4
    out = regime.ba_cva_capital(
        [{"ead": 100.0, "maturity": 5.0, "sector": "FINANCIAL", "credit_quality": "IG"}]
    )
    assert out["k_reduced"] == pytest.approx(s)  # single name: K_reduced = SCVA
    assert out["k"] == pytest.approx(0.65 * s)
    assert out["rwa"] == pytest.approx(12.5 * 0.65 * s)


def test_ba_cva_reduced_two_counterparties() -> None:
    cps: list[dict[str, float | str | bool]] = [
        {"ead": 100.0, "maturity": 1.0, "sector": "CONSUMER", "credit_quality": "HY_NR"},
        {"ead": 50.0, "maturity": 2.0, "sector": "SOVEREIGN", "credit_quality": "IG"},
    ]
    s1 = 0.085 * 1.0 * 100.0 * cva.discount_factor(1.0) / 1.4
    s2 = 0.005 * 2.0 * 50.0 * cva.discount_factor(2.0) / 1.4
    k = math.sqrt((0.5 * (s1 + s2)) ** 2 + 0.75 * (s1**2 + s2**2))
    assert cva.ba_cva_capital(cps)["k_reduced"] == pytest.approx(k)
    # IMM bank: DF = 1
    k_imm = cva.ba_cva_capital(cps, imm_bank=True)["k_reduced"]
    s1i, s2i = 0.085 * 100.0 / 1.4, 0.005 * 100.0 / 1.4
    assert k_imm == pytest.approx(math.sqrt((0.5 * (s1i + s2i)) ** 2 + 0.75 * (s1i**2 + s2i**2)))


def test_ba_cva_full_perfect_hedge() -> None:
    # Hedge notional B = EAD/alpha on the counterparty itself -> SNH = SCVA, HMA = 0
    cps: list[dict[str, float | str | bool]] = [
        {
            "ead": 140.0,
            "maturity": 3.0,
            "sector": "FINANCIAL",
            "credit_quality": "IG",
            "hedge_notional": 100.0,
            "hedge_maturity": 3.0,
            "hedge_reference": "COUNTERPARTY",
        },
    ]
    out = cva.ba_cva_capital(cps, hedged=True)
    assert out["k_hedged"] == pytest.approx(0.0, abs=1e-9)
    assert out["k_full"] == pytest.approx(0.25 * out["k_reduced"])
    assert out["k"] == pytest.approx(0.65 * 0.25 * out["k_reduced"])


def test_ba_cva_full_indirect_and_index_hedge() -> None:
    cps: list[dict[str, float | str | bool]] = [
        {
            "ead": 140.0,
            "maturity": 3.0,
            "sector": "FINANCIAL",
            "credit_quality": "IG",
            "hedge_notional": 100.0,
            "hedge_maturity": 3.0,
            "hedge_reference": "SECTOR",
        },
        {
            "index_hedge": True,
            "notional": 20.0,
            "maturity": 2.0,
            "sector": "FINANCIAL",
            "credit_quality": "IG",
            "homogeneous": True,
        },
    ]
    out = cva.ba_cva_capital(cps, hedged=True)
    scva = 0.05 * 3.0 * 140.0 * cva.discount_factor(3.0) / 1.4
    term = 0.05 * 3.0 * 100.0 * cva.discount_factor(3.0)
    snh = 0.5 * term
    hma = (1 - 0.25) * term**2
    ih = 0.05 * 0.7 * 2.0 * 20.0 * cva.discount_factor(2.0)
    kh = math.sqrt((0.5 * (scva - snh) - ih) ** 2 + 0.75 * (scva - snh) ** 2 + hma)
    assert out["k_hedged"] == pytest.approx(kh)
    assert out["k_full"] == pytest.approx(0.25 * scva + 0.75 * kh)


def test_cva_ccr_election() -> None:
    assert cva.cva_rwa_ccr_election(150_000.0, 42.0) == 42.0
    assert cva.cva_rwa_ccr_election(150_000.1, 42.0) is None
    assert cva.discount_factor(0.0) == 1.0
