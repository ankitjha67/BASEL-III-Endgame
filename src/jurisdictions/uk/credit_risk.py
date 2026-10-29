"""UK PRA Basel 3.1 standardised approach to credit risk (SA-CR) and CRM.

Implements, for the jurisdiction-neutral :class:`~src.jurisdictions.base.SAExposure`:

* risk-weight assignment for every :class:`~src.jurisdictions.base.AssetClass`
  under the PRA Rulebook Credit Risk: Standardised Approach (CRR) Part,
  Articles 111-137 (PS1/26 Appendix 1, Annex D), including the Credit Risk:
  General Provisions (CRR) Part rule 4.2/4.3 equity transitional schedule;
* the Article 111 Table A1 conversion factors;
* the Article 123B currency-mismatch multiplier;
* credit risk mitigation under the Credit Risk Mitigation (CRR) Part: the
  Financial Collateral Comprehensive Method (Arts 223-227, E* = max{0, E(1+HE) -
  C(1-HC-Hfx)}) with the Art 224 supervisory volatility adjustments, the Art 226
  scaling, the Art 239 maturity-mismatch adjustment, and the Risk-Weight
  Substitution Method for guarantees (Arts 233, 235).

Regime-specific inputs the base contract does not carry are read from
``SAExposure.flags`` under the keys documented in :data:`UK_FLAGS`.

References:
    - PRA Rulebook: CRR Firms: (CRR) Instrument 2026 (PRA2026/1), Annexes C, D, F
    - PRA PS1/26 "Implementation of the Basel 3.1 standards" (January 2026)

All amounts in millions of the reporting currency (GBP for a UK firm; the engine
is currency-agnostic and labels them $M).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final

from src.jurisdictions.base import (
    AssetClass,
    CreditRWAResult,
    EquityType,
    Jurisdiction,
    OBSCategory,
    PFPhase,
    RatingBucket,
    RiskWeightResult,
    SAExposure,
    SCRAGrade,
    ShortTermRating,
)
from src.jurisdictions.uk import params as p

PART: Final[str] = "PRA Rulebook Credit Risk: Standardised Approach (CRR) Part"
CRM_PART: Final[str] = "PRA Rulebook Credit Risk Mitigation (CRR) Part"
GP_PART: Final[str] = "PRA Rulebook Credit Risk: General Provisions (CRR) Part"

UK_FLAGS: Final[dict[str, str]] = {
    "uk_central_government_or_boe": (
        "Obligor is the UK central government or the Bank of England (Art 114(4))."
    ),
    "ecb": "Obligor is the European Central Bank (Art 114(3)).",
    "eca_score_used": "Use oecd_crc as the ECA MEIP score under Art 137 Table 9.",
    "regional_government": (
        "PSE-class obligor is a regional government or local authority (Art 115)."
    ),
    "uk_devolved_administration": (
        "Scottish Government, Welsh Government or NI Executive (Art 115(2))."
    ),
    "uk_entity": "RGLA/PSE established in the UK (Art 115(5) sterling 20%).",
    "mdb_listed_zero_rw": "MDB listed in Art 117(2) (0%).",
    "international_organisation": "International organisation listed in Art 118(1) (0%).",
    "goods_movement": "Exposure arose from the movement of goods (Arts 120(2A), 121(4)).",
    "foreign_currency_exposure": (
        "Unrated bank exposure not in the debtor's local currency (Art 121(6))."
    ),
    "due_diligence_notch_up": (
        "Due diligence requires a one-CQS-higher risk weight (Arts 120(4), 122(4), 129(4A))."
    ),
    "corporate_ig_permission": (
        "Firm holds the Art 122(6) investment-grade permission (also a config option)."
    ),
    "obligor_is_natural_person": (
        "Real-estate obligor is one or more natural persons (Art 124L(1)(a))."
    ),
    "social_housing": (
        "Social housing / housing co-operative exposure (Arts 124E(1)(d)-(e), 124L(1)(d))."
    ),
    "payroll_or_pension_loan": "Retail loan meeting Art 123(4)(a)-(d) (35%).",
    "senior_charges_not_held": (
        "Charges ranking ahead are held by others (Arts 124F(2), 124G(2), 124H(2), 124I(3))."
    ),
    "residential_adc": "ADC exposure finances residential real estate (Art 124K(2)); default True.",
    "residential_re_non_cf": "Defaulted exposure is RRE not materially CF-dependent (Art 127(3)).",
    "higher_risk_equity": (
        "Unlisted equity in a business existing < 5 years (Glossary; Art 133(4))."
    ),
    "particularly_high_risk": "Exposure associated with particularly high risk (Art 128).",
    "cash": "Cash in hand / equivalent cash items (Art 134(3), 0%).",
    "cash_in_collection": "Cash items in the process of collection (Art 134(3), 20%).",
    "gold_bullion": "Gold bullion backed by bullion liabilities (Art 134(4), 0%).",
    "uk_residential_mortgage_commitment": (
        "UK residential mortgage commitment (Table A1 row (4), 50%)."
    ),
    "commitment_to_issue_obs_item": (
        "Commitment to issue the OBS item in obs_category (Art 111(1)(c))."
    ),
    "commitment_unconditionally_cancellable": (
        "That commitment is unconditionally cancellable (Table A1 row (7))."
    ),
    "repo_style": "Repo / securities lending: 5-day liquidation period (Art 224(2)(b)).",
    "capital_market_transaction": (
        "Other capital-market-driven transaction: 10-day period (Art 224(2)(c))."
    ),
    "collateral_currency_mismatch": (
        "Collateral currency differs from exposure currency (Art 223(1), Hfx)."
    ),
    "guarantee_currency_mismatch": (
        "Guarantee currency differs from the exposure currency (Art 233(3))."
    ),
    "cd_without_restructuring": (
        "Credit derivative excluding restructuring as a credit event (Art 233(2))."
    ),
    "currency_mismatch_hedged": (
        "Natural/financial hedge covers >= 90% of instalments (Art 123B(2))."
    ),
    "guarantor_<flag>": (
        "Any flag above prefixed 'guarantor_' is passed to the guarantor's exposure."
    ),
}
"""Documented ``SAExposure.flags`` keys read by the UK regime."""


@dataclass(frozen=True)
class UKCreditConfig:
    """Firm-level choices and the reporting year for the UK SA-CR.

    Reference: Art 122(6) (IG permission), Credit Risk: General Provisions (CRR)
    Part rules 4.1-4.10 (equity transitional; IRB firms; opt-out under 4.9).
    """

    year: int = 2027
    irb_firm: bool = False
    """Firm had IRB permission on 31 December 2026 (GP Part rule 4.1/4.4)."""
    corporate_ig_permission: bool = False
    """Firm has the Art 122(6) PRA permission for unrated corporates."""
    equity_transitional_opt_out: bool = False
    """GP Part rule 4.9: firm elects full Art 133 risk weights instead of 4.5-4.8 (IRB firms)."""
    notes: tuple[str, ...] = field(default_factory=tuple)


# =========================================================================
#  Rating helpers
# =========================================================================

_CQS_BY_BUCKET: Final[dict[RatingBucket, int]] = {
    RatingBucket.AAA_TO_AA_MINUS: 1,
    RatingBucket.A_PLUS_TO_A_MINUS: 2,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS: 3,
    RatingBucket.BB_PLUS_TO_BB_MINUS: 4,
    RatingBucket.B_PLUS_TO_B_MINUS: 5,
    RatingBucket.BELOW_B_MINUS: 6,
}
_ST_KEY: Final[dict[ShortTermRating, str]] = {
    ShortTermRating.A1_P1: "1",
    ShortTermRating.A2_P2: "2",
    ShortTermRating.A3_P3: "3",
    ShortTermRating.OTHERS: "OTHERS",
}


def cqs_of(rating: RatingBucket, notch_up: bool = False) -> int | None:
    """Credit quality step of a long-term rating bucket (None if unrated).

    Reference: Art 113(1) / Art 136 mapping per Implementing Regulation (EU)
    2016/1799; ``notch_up`` applies the due-diligence one-step uplift of
    Arts 120(4) / 122(4) / 129(4A) (p. 41, 44, 61).
    """
    cqs = _CQS_BY_BUCKET.get(rating)
    if cqs is None:
        return None
    return min(6, cqs + 1) if notch_up else cqs


def _flag(exposure: SAExposure, key: str, default: bool = False) -> bool:
    """Read a documented UK flag (see :data:`UK_FLAGS`; no regulatory content)."""
    return exposure.flags.get(key, default)


@dataclass
class _RW:
    """Intermediate risk-weight outcome (no regulatory content)."""

    rw: float
    regime_class: str
    citation: str
    notes: list[str] = field(default_factory=list)


# =========================================================================
#  Conversion factors -- Article 111 Table A1
# =========================================================================


def _ccf_for_category(category: OBSCategory, exposure: SAExposure) -> tuple[float, str]:
    """CCF for one OBS category per Art 111(1)(b) Table A1 (p. 30-32)."""
    if category is OBSCategory.COMMITMENT_OTHER and _flag(
        exposure, "uk_residential_mortgage_commitment"
    ):
        return p.CCF_NIF_RUF_UK_MORTGAGE_COMMITMENT, f"{PART} Art 111 Table A1 row (4)(b)"
    table: dict[OBSCategory, tuple[float, str]] = {
        OBSCategory.UNCONDITIONALLY_CANCELLABLE: (p.CCF_UNCONDITIONALLY_CANCELLABLE, "row (7)"),
        OBSCategory.COMMITMENT_OTHER: (p.CCF_OTHER_COMMITMENT, "row (5)"),
        OBSCategory.NIF_RUF: (p.CCF_NIF_RUF_UK_MORTGAGE_COMMITMENT, "row (4)(a)"),
        OBSCategory.TRANSACTION_RELATED_CONTINGENT: (p.CCF_TRADE_AND_PERFORMANCE, "row (6)(b)-(c)"),
        OBSCategory.SHORT_TERM_TRADE_LC: (p.CCF_TRADE_AND_PERFORMANCE, "row (6)(a)"),
        OBSCategory.DIRECT_CREDIT_SUBSTITUTE: (p.CCF_FULL_RISK, "row (1)"),
        OBSCategory.SECURITIES_LENDING_COLLATERAL: (p.CCF_FULL_RISK, "row (2)(c) / Art 111(1A)"),
        OBSCategory.FORWARD_ASSET_PURCHASE: (p.CCF_FULL_RISK, "row (2)(b)"),
        OBSCategory.OTHER_100: (p.CCF_FULL_RISK, "row (1)(f) / (2)(f)"),
    }
    value, row = table[category]
    return value, f"{PART} Art 111 Table A1 {row}"


def conversion_factor(exposure: SAExposure) -> tuple[float, str]:
    """Conversion factor for the off-balance-sheet notional of an exposure.

    Reference: Art 111(1)(b)-(c) and Table A1 (p. 29-32). For a commitment to
    issue an off-balance sheet item (flag ``commitment_to_issue_obs_item``) the
    lower of the item's CF and the commitment's CF applies (Art 111(1)(c)).
    A missing ``obs_category`` with a non-zero notional is treated at 100%
    (conservative: row (1)(f)/(2)(f) 'other items').
    """
    if exposure.off_balance_notional == 0.0 and exposure.obs_category is None:
        return 0.0, f"{PART} Art 111(1)(a) (on-balance sheet only)"
    category = exposure.obs_category or OBSCategory.OTHER_100
    value, cite = _ccf_for_category(category, exposure)
    if _flag(exposure, "commitment_to_issue_obs_item"):
        commitment_cf = (
            p.CCF_UNCONDITIONALLY_CANCELLABLE
            if _flag(exposure, "commitment_unconditionally_cancellable")
            else p.CCF_OTHER_COMMITMENT
        )
        if commitment_cf < value:
            return commitment_cf, f"{PART} Art 111(1)(c) (lower of item and commitment CF)"
        return value, f"{cite}; Art 111(1)(c)"
    return value, cite


# =========================================================================
#  Exposure-class risk weights
# =========================================================================


def sovereign_rw(exposure: SAExposure) -> _RW:
    """Central governments / central banks -- Art 114 and Art 137 (p. 35-36, 69-70)."""
    cls = "Central governments or central banks (Art 112(1)(a))"
    if _flag(exposure, "ecb"):
        return _RW(p.SOVEREIGN_ECB_RW, cls, f"{PART} Art 114(3)")
    if _flag(exposure, "uk_central_government_or_boe") and exposure.domestic_currency_funded:
        return _RW(p.SOVEREIGN_UK_STERLING_RW, cls, f"{PART} Art 114(4)")
    if _flag(exposure, "eca_score_used") and exposure.oecd_crc is not None:
        return _RW(p.ECA_MEIP_RW_TABLE_9[exposure.oecd_crc], cls, f"{PART} Art 137(2) Table 9")
    cqs = cqs_of(exposure.rating)
    if cqs is not None:
        return _RW(p.SOVEREIGN_RW_TABLE_1[cqs], cls, f"{PART} Art 114(2) Table 1 (CQS {cqs})")
    return _RW(p.SOVEREIGN_UNRATED_RW, cls, f"{PART} Art 114(1)")


def rgla_rw(exposure: SAExposure) -> _RW:
    """Regional governments or local authorities -- Art 115 (p. 36-37)."""
    cls = "Regional governments or local authorities (Art 112(1)(b))"
    if _flag(exposure, "uk_devolved_administration"):
        sov = exposure.model_copy(
            update={"flags": {**exposure.flags, "uk_central_government_or_boe": True}}
        )
        inner = sovereign_rw(sov)
        return _RW(
            inner.rw,
            "Central governments or central banks (Art 112(1)(a))",
            f"{PART} Art 115(2) -> {inner.citation}",
        )
    if _flag(exposure, "uk_entity") and exposure.domestic_currency_funded:
        return _RW(p.RGLA_UK_STERLING_RW, cls, f"{PART} Art 115(5)")
    cqs = cqs_of(exposure.rating)
    if cqs is not None:
        return _RW(p.RGLA_RATED_TABLE_1B[cqs], cls, f"{PART} Art 115(1)(b) Table 1B (CQS {cqs})")
    sov_cqs = cqs_of(exposure.sovereign_rating)
    if sov_cqs is not None:
        return _RW(
            p.RGLA_UNRATED_SOVEREIGN_BASED_TABLE_1A[sov_cqs],
            cls,
            f"{PART} Art 115(1)(a)(i) Table 1A (sovereign CQS {sov_cqs})",
        )
    return _RW(p.RGLA_UNRATED_NO_SOVEREIGN_RATING_RW, cls, f"{PART} Art 115(1)(a)(ii)")


def pse_rw(exposure: SAExposure) -> _RW:
    """Public sector entities -- Art 116 (UK and, via 116(3A), third-country) (p. 37-38)."""
    if _flag(exposure, "regional_government") or _flag(exposure, "uk_devolved_administration"):
        return rgla_rw(exposure)
    cls = "Public sector entities (Art 112(1)(c))"
    months = exposure.original_maturity_months
    if months is not None and months <= p.PSE_SHORT_TERM_MAX_MONTHS:
        return _RW(p.PSE_SHORT_TERM_RW, cls, f"{PART} Art 116(3)")
    cqs = cqs_of(exposure.rating)
    if cqs is not None:
        return _RW(p.PSE_RATED_TABLE_2A[cqs], cls, f"{PART} Art 116(2) Table 2A (CQS {cqs})")
    sov_cqs = cqs_of(exposure.sovereign_rating)
    if sov_cqs is not None:
        return _RW(
            p.PSE_UNRATED_SOVEREIGN_BASED_TABLE_2[sov_cqs],
            cls,
            f"{PART} Art 116(1)(a) Table 2 (sovereign CQS {sov_cqs})",
        )
    return _RW(p.PSE_UNRATED_NO_SOVEREIGN_RATING_RW, cls, f"{PART} Art 116(1)(b)")


def mdb_rw(exposure: SAExposure) -> _RW:
    """Multilateral development banks and international organisations -- Arts 117-118 (p. 38-40)."""
    if _flag(exposure, "international_organisation"):
        return _RW(
            p.INTERNATIONAL_ORGANISATION_RW,
            "International organisations (Art 112(1)(e))",
            f"{PART} Art 118(1)",
        )
    cls = "Multilateral development banks (Art 112(1)(d))"
    if _flag(exposure, "mdb_listed_zero_rw"):
        return _RW(p.MDB_LISTED_RW, cls, f"{PART} Art 117(2)")
    cqs = cqs_of(exposure.rating)
    if cqs is not None:
        return _RW(p.MDB_RATED_TABLE_2B[cqs], cls, f"{PART} Art 117(1)(a) Table 2B (CQS {cqs})")
    return _RW(p.MDB_UNRATED_RW, cls, f"{PART} Art 117(1)(b)")


def _is_short_term_institution(exposure: SAExposure) -> tuple[bool, str]:
    """Original-maturity tests of Arts 120(2)/(2A) and 121(3)/(4) (p. 40, 43)."""
    months = exposure.original_maturity_months
    if months is None:
        return False, ""
    if months <= p.INSTITUTION_SHORT_TERM_MAX_MONTHS:
        return True, "<= 3 months"
    goods = _flag(exposure, "goods_movement") or exposure.is_trade_related
    if goods and months <= p.INSTITUTION_TRADE_GOODS_MAX_MONTHS:
        return True, "<= 6 months, movement of goods"
    return False, ""


def institution_rw(exposure: SAExposure) -> _RW:
    """Institutions -- Arts 119-121 (ECRA for rated, SCRA grades for unrated) (p. 40-43)."""
    cls = "Institutions (Art 112(1)(f))"
    notch = _flag(exposure, "due_diligence_notch_up")
    short, why = _is_short_term_institution(exposure)
    if exposure.short_term_rating is not None:
        key = _ST_KEY[exposure.short_term_rating]
        return _RW(
            p.INSTITUTION_SHORT_TERM_ASSESSMENT_TABLE_4A[key],
            cls,
            f"{PART} Art 120(2B) Table 4A (short-term CQS {key}); Art 120(3)",
        )
    cqs = cqs_of(exposure.rating, notch_up=notch)
    if cqs is not None:
        if short:
            return _RW(
                p.INSTITUTION_RATED_SHORT_TERM_TABLE_4[cqs],
                cls,
                f"{PART} Art 120(2)/(2A) Table 4 (CQS {cqs}, {why})",
            )
        return _RW(p.INSTITUTION_RATED_TABLE_3[cqs], cls, f"{PART} Art 120(1) Table 3 (CQS {cqs})")

    notes: list[str] = []
    grade = exposure.scra_grade
    if grade is None:
        grade = SCRAGrade.C
        notes.append("No SCRA grade supplied: Grade C assumed (conservative; Art 121(1)(c)).")
    if short:
        rw = p.INSTITUTION_SCRA_SHORT_TERM_TABLE_5A[grade.value]
        cite = f"{PART} Art 121(3)/(4) Table 5A (Grade {grade.value}, {why})"
    elif grade is SCRAGrade.A and exposure.scra_grade_a_enhanced:
        rw = p.INSTITUTION_SCRA_GRADE_A_ENHANCED_RW
        cite = f"{PART} Art 121(5) (Grade A, CET1 >= 14%, leverage >= 5%)"
    else:
        rw = p.INSTITUTION_SCRA_TABLE_5[grade.value]
        cite = f"{PART} Art 121(2) Table 5 (Grade {grade.value})"

    if _flag(exposure, "foreign_currency_exposure"):
        trade_exempt = exposure.is_trade_related and (
            exposure.original_maturity_months is not None
            and exposure.original_maturity_months
            < 12.0 * p.INSTITUTION_SOVEREIGN_FLOOR_TRADE_MAX_YEARS
        )
        if not trade_exempt:
            sov_cqs = cqs_of(exposure.sovereign_rating)
            floor = (
                p.SOVEREIGN_RW_TABLE_1[sov_cqs] if sov_cqs is not None else p.SOVEREIGN_UNRATED_RW
            )
            if floor > rw:
                notes.append(f"Sovereign floor {floor:.0%} applied (Art 121(6)).")
                rw = floor
                cite += "; Art 121(6) sovereign floor"
    return _RW(rw, cls, cite, notes)


def _is_sme(exposure: SAExposure) -> bool:
    """SME test: Glossary 'SME' -- annual turnover <= GBP 44 million (p. 9)."""
    if exposure.is_sme or exposure.asset_class is AssetClass.CORPORATE_SME:
        return True
    return (
        exposure.annual_turnover is not None
        and exposure.annual_turnover <= p.SME_TURNOVER_THRESHOLD_GBP_M
    )


def corporate_rw(exposure: SAExposure, config: UKCreditConfig) -> _RW:
    """General and SME corporates -- Art 122 (p. 43-45)."""
    cls = "Corporates (Art 112(1)(g))"
    notch = _flag(exposure, "due_diligence_notch_up")
    if exposure.short_term_rating is not None:
        key = _ST_KEY[exposure.short_term_rating]
        return _RW(
            p.CORPORATE_SHORT_TERM_TABLE_6A[key],
            cls,
            f"{PART} Art 122(3) Table 6A (short-term CQS {key})",
        )
    cqs = cqs_of(exposure.rating, notch_up=notch)
    if cqs is not None:
        return _RW(p.CORPORATE_RATED_TABLE_6[cqs], cls, f"{PART} Art 122(2) Table 6 (CQS {cqs})")
    if _is_sme(exposure):
        return _RW(p.CORPORATE_SME_UNRATED_RW, cls + " -- SME", f"{PART} Art 122(11)")
    if config.corporate_ig_permission or _flag(exposure, "corporate_ig_permission"):
        if exposure.is_investment_grade:
            return _RW(p.CORPORATE_UNRATED_IG_RW, cls, f"{PART} Art 122(6)(a) (investment grade)")
        notes = (
            []
            if exposure.is_investment_grade is False
            else [
                "IG assessment missing under the Art 122(6) permission: "
                "treated as not investment grade."
            ]
        )
        return _RW(
            p.CORPORATE_UNRATED_NON_IG_RW,
            cls,
            f"{PART} Art 122(6)(b) (not investment grade)",
            notes,
        )
    return _RW(p.CORPORATE_UNRATED_RW, cls, f"{PART} Art 122(5)")


def specialised_lending_rw(exposure: SAExposure) -> _RW:
    """Specialised lending -- Arts 122A-122B (p. 45-47)."""
    cls = "Corporates -- specialised lending (Art 122A)"
    cqs = cqs_of(exposure.rating, notch_up=_flag(exposure, "due_diligence_notch_up"))
    if cqs is not None:
        return _RW(
            p.CORPORATE_RATED_TABLE_6[cqs],
            cls,
            f"{PART} Art 122B(1) -> Art 122(2) Table 6 (issue-specific CQS {cqs})",
        )
    if exposure.asset_class is AssetClass.SPECIALISED_LENDING_OF:
        return _RW(p.SL_OBJECT_FINANCE_RW, cls + " -- object finance", f"{PART} Art 122B(2)(a)")
    if exposure.asset_class is AssetClass.SPECIALISED_LENDING_CF:
        return _RW(
            p.SL_COMMODITIES_FINANCE_RW, cls + " -- commodities finance", f"{PART} Art 122B(2)(b)"
        )
    phase = exposure.pf_phase
    pf = cls + " -- project finance"
    if phase is PFPhase.HIGH_QUALITY_OPERATIONAL:
        return _RW(p.SL_PF_HIGH_QUALITY_OPERATIONAL_RW, pf, f"{PART} Art 122B(4)-(5)")
    if phase is PFPhase.OPERATIONAL:
        return _RW(
            p.SL_PF_OPERATIONAL_RW, pf, f"{PART} Art 122B(2)(c) (operational phase, Art 122B(3))"
        )
    notes = (
        []
        if phase is PFPhase.PRE_OPERATIONAL
        else ["PF phase not supplied: pre-operational assumed."]
    )
    return _RW(
        p.SL_PF_PRE_OPERATIONAL_RW, pf, f"{PART} Art 122B(2)(c) (pre-operational phase)", notes
    )


def _retail_exceeds_limit(exposure: SAExposure) -> bool:
    """Aggregate owed > GBP 880,000 test of Arts 123(1)(b)(ii) / 123A(1)(b)(ii) (p. 47-48)."""
    agg = exposure.aggregate_retail_exposure_to_obligor
    return agg is not None and agg > p.RETAIL_AGGREGATE_LIMIT_GBP_M


def retail_rw(exposure: SAExposure, config: UKCreditConfig) -> _RW:
    """Retail -- Arts 123, 123A (p. 47-48).

    An SME failing the Art 123(1)(b) conditions is not a retail exposure and is
    risk weighted as a corporate (Art 122). A natural-person exposure above the
    limit is 'other retail' (100%).
    """
    if exposure.is_sme and (
        _retail_exceeds_limit(exposure) or not exposure.meets_regulatory_retail_criteria
    ):
        inner = corporate_rw(exposure, config)
        inner.notes.append("SME fails the Art 123(1)(b) retail conditions: corporate treatment.")
        return inner
    cls = "Retail (Art 112(1)(h))"
    if _flag(exposure, "payroll_or_pension_loan"):
        return _RW(p.RETAIL_PAYROLL_PENSION_LOAN_RW, cls, f"{PART} Art 123(4)")
    if exposure.asset_class is AssetClass.RETAIL_OTHER:
        return _RW(p.RETAIL_OTHER_RW, cls + " -- other retail", f"{PART} Art 123(3)(c)")
    regulatory = exposure.meets_regulatory_retail_criteria and not _retail_exceeds_limit(exposure)
    if not regulatory:
        return _RW(
            p.RETAIL_OTHER_RW, cls + " -- other retail", f"{PART} Art 123(3)(c) (fails Art 123A)"
        )
    if exposure.asset_class is AssetClass.RETAIL_TRANSACTOR or exposure.is_transactor:
        return _RW(
            p.RETAIL_TRANSACTOR_RW,
            cls + " -- regulatory retail transactor",
            f"{PART} Art 123(3)(a); Glossary 'transactor exposure'",
        )
    return _RW(
        p.RETAIL_REGULATORY_RW, cls + " -- regulatory retail", f"{PART} Art 123(3)(b); Art 123A"
    )


# -------------------------------------------------------------------------
#  Real estate
# -------------------------------------------------------------------------


def _loan_amount(exposure: SAExposure) -> float:
    """Loan amount for the LTV: outstanding plus undrawn committed amount, Art 124C(2) (p. 52)."""
    return exposure.on_balance_amount + exposure.off_balance_notional


def _property_value(exposure: SAExposure) -> float | None:
    """Property value (Art 124D) from ``property_value`` or, failing that, loan / LTV (Art
    124C(1))."""
    if exposure.property_value:
        return exposure.property_value
    if exposure.ltv:
        return _loan_amount(exposure) / exposure.ltv
    return None


def _ltv(exposure: SAExposure) -> float | None:
    """LTV per Art 124C(1)-(3) (p. 52): supplied ``ltv`` (which includes senior/pari passu
    loans)."""
    if exposure.ltv is not None:
        return exposure.ltv
    value = exposure.property_value
    if value:
        return _loan_amount(exposure) / value
    return None


def _senior_charges(exposure: SAExposure, value: float) -> float:
    """Amount of charges ranking ahead not held by the institution (Arts 124F(2)(a), 124H(2)(a)).

    The base contract has no field for it; when ``senior_charges_not_held`` is set
    and the Art 124C LTV (which includes all senior loans, Art 124C(3)) is given,
    senior charges = LTV x value - own loan amount.
    """
    if not _flag(exposure, "senior_charges_not_held"):
        return 0.0
    ltv = exposure.ltv
    if ltv is None:
        return 0.0
    return max(0.0, ltv * value - _loan_amount(exposure))


def real_estate_counterparty_rw(exposure: SAExposure, config: UKCreditConfig) -> tuple[float, str]:
    """Counterparty risk weight for real estate -- Art 124L(1)(a)-(e) (p. 58)."""
    if _flag(exposure, "social_housing"):
        unsecured = corporate_rw(exposure, config).rw
        return max(p.RE_COUNTERPARTY_SOCIAL_HOUSING_FLOOR_RW, unsecured), f"{PART} Art 124L(1)(d)"
    if _is_sme(exposure):
        retail_like = exposure.meets_regulatory_retail_criteria and not _retail_exceeds_limit(
            exposure
        )
        if retail_like:
            return p.RE_COUNTERPARTY_RETAIL_SME_RW, f"{PART} Art 124L(1)(b)"
        return p.RE_COUNTERPARTY_OTHER_SME_RW, f"{PART} Art 124L(1)(c)"
    default_np = exposure.asset_class is AssetClass.RESIDENTIAL_RE
    if _flag(exposure, "obligor_is_natural_person", default_np):
        return p.RE_COUNTERPARTY_NATURAL_PERSON_RW, f"{PART} Art 124L(1)(a)"
    inner = corporate_rw(exposure.model_copy(update={"asset_class": AssetClass.CORPORATE}), config)
    return inner.rw, f"{PART} Art 124L(1)(e) -> {inner.citation}"


def _loan_split(
    exposure: SAExposure,
    config: UKCreditConfig,
    ead: float,
    share: float,
    secured_rw: float,
    article: str,
) -> tuple[float, str, list[str]]:
    """Loan-splitting blend: secured_rw up to share x value, counterparty RW on the rest.

    Reference: Art 124F(1)-(2) (RRE, 20%) and Art 124H(1)-(2) (CRE to natural
    persons/SMEs, 60%) (p. 55-57). Pari passu third-party charges (para 2(b)) are
    not modelled (no base field). Returns the exposure-weighted average RW.
    """
    cp_rw, cp_cite = real_estate_counterparty_rw(exposure, config)
    notes: list[str] = []
    value = _property_value(exposure)
    if value is None:
        notes.append("No property value/LTV: whole exposure at the counterparty RW (conservative).")
        return cp_rw, f"{PART} {article}(1)(b); {cp_cite}", notes
    if ead <= 0.0:
        return secured_rw, f"{PART} {article}(1)(a)", notes
    eligible = max(0.0, share * value - _senior_charges(exposure, value))
    secured = min(ead, eligible)
    blended = (secured * secured_rw + (ead - secured) * cp_rw) / ead
    notes.append(
        f"Loan split: {secured:,.3f} at {secured_rw:.0%}, {ead - secured:,.3f} at {cp_rw:.0%}."
    )
    return blended, f"{PART} {article}(1)(a)-(b); {cp_cite}", notes


def _band_lookup(table: tuple[tuple[float, float], ...], ltv: float) -> float:
    """First risk weight whose inclusive upper LTV bound covers ``ltv`` (helper)."""
    for upper, rw in table:
        if ltv <= upper:
            return rw
    return table[-1][1]


def cre_cash_flow_rw(exposure: SAExposure) -> tuple[float, str, list[str]]:
    """Regulatory CRE materially dependent on cash flows -- Art 124I(1)-(3) (p. 57)."""
    ltv = _ltv(exposure)
    notes: list[str] = []
    junior = _flag(exposure, "senior_charges_not_held")
    if ltv is None:
        notes.append("LTV missing: highest LTV band applied (conservative).")
        ltv = float("inf")
    if junior:
        return _band_lookup(p.CRE_CF_DEPENDENT_JUNIOR_TABLE, ltv), f"{PART} Art 124I(3)", notes
    return _band_lookup(p.CRE_CF_DEPENDENT_TABLE, ltv), f"{PART} Art 124I(1)-(2)", notes


def residential_re_rw(exposure: SAExposure, config: UKCreditConfig, ead: float) -> _RW:
    """Residential real estate -- Arts 124, 124A, 124E-124G, 124J, 124L (p. 50-58)."""
    cls = "Real estate -- residential (Art 112(1)(i))"
    if not exposure.is_regulatory_real_estate:
        cls_o = cls + " -- other real estate"
        if exposure.is_cash_flow_dependent:
            return _RW(p.OTHER_RE_CF_DEPENDENT_RW, cls_o, f"{PART} Art 124J(1)")
        rw, cite = real_estate_counterparty_rw(exposure, config)
        return _RW(rw, cls_o, f"{PART} Art 124J(2); {cite}")
    if exposure.is_cash_flow_dependent:
        ltv = _ltv(exposure)
        notes: list[str] = []
        if ltv is None:
            notes.append("LTV missing: highest Table 6B band applied (conservative).")
            ltv = float("inf")
        rw = _band_lookup(p.RRE_CF_DEPENDENT_TABLE_6B, ltv)
        cite = f"{PART} Art 124G(1) Table 6B"
        if _flag(exposure, "senior_charges_not_held") and ltv > p.RRE_CF_JUNIOR_LTV_THRESHOLD:
            rw *= p.RRE_CF_JUNIOR_MULTIPLIER
            cite += "; Art 124G(2) x1.25"
        return _RW(rw, cls + " -- materially dependent on cash flows", cite, notes)
    rw, cite, notes = _loan_split(
        exposure,
        config,
        ead,
        p.RRE_LOAN_SPLIT_SECURED_SHARE,
        p.RRE_LOAN_SPLIT_SECURED_RW,
        "Art 124F",
    )
    return _RW(rw, cls + " -- not materially dependent on cash flows (loan splitting)", cite, notes)


def commercial_re_rw(exposure: SAExposure, config: UKCreditConfig, ead: float) -> _RW:
    """Commercial real estate -- Arts 124, 124A, 124E, 124H-124J, 124L (p. 50-58)."""
    cls = "Real estate -- commercial (Art 112(1)(i))"
    if not exposure.is_regulatory_real_estate:
        cls_o = cls + " -- other real estate"
        if exposure.is_cash_flow_dependent:
            return _RW(p.OTHER_RE_CF_DEPENDENT_RW, cls_o, f"{PART} Art 124J(1)")
        cp_rw, cp_cite = real_estate_counterparty_rw(exposure, config)
        return _RW(max(p.OTHER_CRE_NON_CF_FLOOR_RW, cp_rw), cls_o, f"{PART} Art 124J(3); {cp_cite}")
    if exposure.is_cash_flow_dependent:
        rw, cite, notes = cre_cash_flow_rw(exposure)
        return _RW(rw, cls + " -- materially dependent on cash flows", cite, notes)
    natural_or_sme = _flag(exposure, "obligor_is_natural_person") or _is_sme(exposure)
    if natural_or_sme:
        rw, cite, notes = _loan_split(
            exposure,
            config,
            ead,
            p.CRE_LOAN_SPLIT_SECURED_SHARE,
            p.CRE_LOAN_SPLIT_SECURED_RW,
            "Art 124H",
        )
        return _RW(rw, cls + " -- natural person/SME, loan splitting", cite, notes)
    cp_rw, cp_cite = real_estate_counterparty_rw(exposure, config)
    cf_rw, cf_cite, notes = cre_cash_flow_rw(exposure)
    rw = max(p.CRE_NON_CF_OTHER_OBLIGOR_FLOOR_RW, min(cp_rw, cf_rw))
    return _RW(
        rw,
        cls + " -- other obligor, not cash-flow dependent",
        f"{PART} Art 124H(3): max(60%, min({cp_cite}; {cf_cite}))",
        notes,
    )


def adc_rw(exposure: SAExposure) -> _RW:
    """Land acquisition, development and construction -- Art 124K (p. 58)."""
    cls = "Real estate -- ADC (Art 124K)"
    if exposure.is_adc_presold_or_equity_at_risk and _flag(exposure, "residential_adc", True):
        return _RW(p.ADC_RESIDENTIAL_QUALIFYING_RW, cls, f"{PART} Art 124K(2)")
    return _RW(p.ADC_RW, cls, f"{PART} Art 124K(1)")


def defaulted_rw(exposure: SAExposure) -> _RW:
    """Exposures in default -- Art 127 (p. 59).

    Applies to the part not secured by recognised collateral or covered by
    recognised unfunded protection (Art 127(1)-(2)); CRM is applied by
    :func:`assign_risk_weight` before this weight is used.
    """
    cls = "Exposures in default (Art 112(1)(j))"
    rre_non_cf = (
        exposure.asset_class is AssetClass.RESIDENTIAL_RE and not exposure.is_cash_flow_dependent
    ) or _flag(exposure, "residential_re_non_cf")
    if rre_non_cf:
        return _RW(p.DEFAULTED_RRE_NON_CF_RW, cls, f"{PART} Art 127(3)")
    if exposure.specific_provision_pct >= p.DEFAULTED_PROVISION_THRESHOLD:
        return _RW(p.DEFAULTED_HIGH_PROVISION_RW, cls, f"{PART} Art 127(1)(b) (SCRA >= 20%)")
    return _RW(p.DEFAULTED_LOW_PROVISION_RW, cls, f"{PART} Art 127(1)(a) (SCRA < 20%)")


def covered_bond_rw(exposure: SAExposure) -> _RW:
    """Eligible covered bonds -- Art 129(4)-(5) (p. 61-62)."""
    cls = "Eligible covered bonds (Art 112(1)(l))"
    if exposure.covered_bond_rated:
        cqs = cqs_of(exposure.rating, notch_up=_flag(exposure, "due_diligence_notch_up"))
        if cqs is not None:
            return _RW(
                p.COVERED_BOND_RATED_TABLE_7[cqs], cls, f"{PART} Art 129(4) Table 7 (CQS {cqs})"
            )
    issuer = institution_rw(
        exposure.model_copy(
            update={
                "asset_class": AssetClass.BANK,
                "short_term_rating": None,
                "original_maturity_months": None,
            }
        )
    )
    rw = p.COVERED_BOND_UNRATED_MAP.get(round(issuer.rw, 4))
    if rw is None:
        higher = sorted(k for k in p.COVERED_BOND_UNRATED_MAP if k >= issuer.rw)
        rw = p.COVERED_BOND_UNRATED_MAP[higher[0]] if higher else p.COVERED_BOND_UNRATED_MAP[1.50]
    return _RW(
        rw,
        cls,
        f"{PART} Art 129(5) (issuer RW {issuer.rw:.0%} via {issuer.citation})",
        issuer.notes,
    )


def equity_rw(exposure: SAExposure, config: UKCreditConfig) -> _RW:
    """Equity -- Art 133(3)-(6) with the GP Part rule 4.2/4.3 transitional (p. 20-21, 68)."""
    cls = "Subordinated debt, equity and other own funds instruments (Art 112(1)(p)) -- equity"
    etype = exposure.equity_type or EquityType.GENERAL
    notes: list[str] = []
    if etype is EquityType.SIGNIFICANT_FI:
        return _RW(
            p.EQUITY_SIGNIFICANT_FI_THRESHOLD_RW,
            cls,
            f"{PART} Art 133(6)(c) -> Own Funds (CRR) Part Art 48(4)",
        )
    higher_risk = _flag(exposure, "higher_risk_equity") or etype is EquityType.SPECULATIVE_UNLISTED
    if etype is EquityType.SPECULATIVE_UNLISTED and not _flag(exposure, "higher_risk_equity"):
        notes.append(
            "SPECULATIVE_UNLISTED mapped to 'higher risk equity exposure' (UK test: unlisted "
            "and business < 5 years)."
        )
    if etype is EquityType.LEGISLATIVE_PROGRAMME:
        notes.append("No legislative-programme carve-out in Art 133: general equity weight.")
    full_rw = p.EQUITY_HIGHER_RISK_RW if higher_risk else p.EQUITY_RW
    full_cite = f"{PART} Art 133(4)" if higher_risk else f"{PART} Art 133(3)"
    schedule = p.EQUITY_HIGHER_RISK_TRANSITIONAL_RW if higher_risk else p.EQUITY_TRANSITIONAL_RW
    in_transition = config.year in schedule
    if in_transition and not (config.irb_firm and config.equity_transitional_opt_out):
        rule = "4.3" if higher_risk else "4.2"
        if config.irb_firm:
            notes.append(
                "IRB firm (rule 4.6): higher of legacy IRB equity RW and this transitional RW; "
                "legacy IRB RW not modelled."
            )
        return _RW(
            schedule[config.year], cls, f"{GP_PART} rule {rule} ({config.year}); {full_cite}", notes
        )
    return _RW(full_rw, cls, full_cite, notes)


def other_items_rw(exposure: SAExposure) -> _RW:
    """Other items -- Art 134 and Art 113(5) (p. 35, 68-69)."""
    cls = "Other items (Art 112(1)(q))"
    if _flag(exposure, "cash"):
        return _RW(p.CASH_RW, cls, f"{PART} Art 134(3) (cash)")
    if _flag(exposure, "gold_bullion"):
        return _RW(p.GOLD_BULLION_RW, cls, f"{PART} Art 134(4)")
    if _flag(exposure, "cash_in_collection"):
        return _RW(p.CASH_IN_COLLECTION_RW, cls, f"{PART} Art 134(3) (items in collection)")
    return _RW(p.OTHER_TANGIBLE_ASSETS_RW, cls, f"{PART} Art 134(1)-(2) / Art 113(5)")


def apply_currency_mismatch(
    exposure: SAExposure, rw: float, regime_class: str | None = None
) -> tuple[float, str | None]:
    """Art 123B(1): x1.5, capped at 150%, for unhedged retail and residential RE (p. 49).

    Only exposures assigned to the retail (Art 112(1)(h)) or real estate
    (Art 112(1)(i)) classes qualify, so defaulted / high-risk exposures and SMEs
    reclassified as corporates are excluded (``regime_class`` check).
    """
    eligible = exposure.asset_class in (
        AssetClass.RETAIL_REGULATORY,
        AssetClass.RETAIL_TRANSACTOR,
        AssetClass.RETAIL_OTHER,
        AssetClass.RESIDENTIAL_RE,
    )
    if regime_class is not None and not regime_class.startswith(("Retail", "Real estate")):
        eligible = False
    if (
        not eligible
        or exposure.currency_matches_borrower_income
        or _flag(exposure, "currency_mismatch_hedged")
    ):
        return rw, None
    return min(
        rw * p.CURRENCY_MISMATCH_MULTIPLIER, max(rw, p.CURRENCY_MISMATCH_RW_CAP)
    ), f"{PART} Art 123B(1) x1.5 (cap 150%)"


def base_risk_weight(exposure: SAExposure, config: UKCreditConfig, ead: float) -> _RW:
    """Risk weight before CRM substitution, following the Table A2 class hierarchy.

    Reference: Art 112(2) Table A2 -- where an exposure meets several classes it
    is assigned to the highest-ranked one: (3) subordinated debt/equity, (4)
    particularly high risk, (5) default, then covered bonds, real estate,
    MDB/IO, institutions, sovereigns, RGLAs, PSEs, retail, corporates, other (p. 32-34).
    """
    ac = exposure.asset_class
    if ac is AssetClass.EQUITY:
        return equity_rw(exposure, config)
    if ac is AssetClass.SUBORDINATED_DEBT:
        return _RW(
            p.SUBORDINATED_DEBT_RW,
            "Subordinated debt, equity and other own funds instruments (Art 112(1)(p))",
            f"{PART} Art 133(5)",
        )
    if _flag(exposure, "particularly_high_risk"):
        return _RW(p.HIGH_RISK_RW, "Particularly high risk (Art 112(1)(k))", f"{PART} Art 128(1)")
    if ac is AssetClass.DEFAULTED or exposure.is_defaulted:
        return defaulted_rw(exposure)
    if ac is AssetClass.COVERED_BOND:
        return covered_bond_rw(exposure)
    if ac is AssetClass.RESIDENTIAL_RE:
        return residential_re_rw(exposure, config, ead)
    if ac is AssetClass.COMMERCIAL_RE:
        return commercial_re_rw(exposure, config, ead)
    if ac is AssetClass.LAND_ADC:
        return adc_rw(exposure)
    if ac is AssetClass.MDB:
        return mdb_rw(exposure)
    if ac is AssetClass.BANK:
        return institution_rw(exposure)
    if ac is AssetClass.SOVEREIGN:
        return sovereign_rw(exposure)
    if ac is AssetClass.PSE:
        return pse_rw(exposure)
    if ac in (AssetClass.RETAIL_REGULATORY, AssetClass.RETAIL_TRANSACTOR, AssetClass.RETAIL_OTHER):
        return retail_rw(exposure, config)
    if ac in (
        AssetClass.SPECIALISED_LENDING_PF,
        AssetClass.SPECIALISED_LENDING_OF,
        AssetClass.SPECIALISED_LENDING_CF,
    ):
        return specialised_lending_rw(exposure)
    if ac in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME):
        return corporate_rw(exposure, config)
    return other_items_rw(exposure)


# =========================================================================
#  Credit risk mitigation -- Credit Risk Mitigation (CRR) Part
# =========================================================================


def liquidation_period(exposure: SAExposure) -> int:
    """Liquidation period by transaction type -- Art 224(2)(a)-(c) (p. 204-205)."""
    if _flag(exposure, "repo_style"):
        return p.LIQUIDATION_PERIOD_REPO
    if _flag(exposure, "capital_market_transaction"):
        return p.LIQUIDATION_PERIOD_CAPITAL_MARKET
    return p.LIQUIDATION_PERIOD_SECURED_LENDING


def supervisory_haircut(key: str, liquidation_days: int = 10, revaluation_days: int = 1) -> float:
    """Supervisory volatility adjustment H for a collateral key.

    Reference: Art 224(1) Tables 1-3 (p. 203-204); where revaluation is less
    frequent than daily, Art 226(1) H = Hm * sqrt((NR + (Tm - 1)) / Tm) (p. 206).
    Raises KeyError for an unknown key.
    """
    row = p.SUPERVISORY_HAIRCUTS[key]
    hm = row[liquidation_days]
    if revaluation_days <= 1:
        return hm
    return hm * math.sqrt((revaluation_days + liquidation_days - 1) / liquidation_days)


def scale_haircut(h_n: float, t_m: float, t_n: float) -> float:
    """Art 226(2): Hm = Hn * sqrt(Tm / Tn) for non-standard liquidation periods (p. 206)."""
    return h_n * math.sqrt(t_m / t_n)


def maturity_mismatch_adjust(value: float, protection_years: float, exposure_years: float) -> float:
    """Art 239(2)-(3): CVAM / GA = value * (t - t*) / (T - t*), t* = 0.25 (p. 218-219).

    T = min(exposure residual maturity, 5); t = min(protection maturity, T). No
    recognition if the protection has < 3 months residual maturity (Art 237(1)).
    """
    big_t = min(exposure_years, p.MATURITY_MISMATCH_T_CAP_YEARS)
    t = min(protection_years, big_t)
    if t >= big_t:
        return value
    if protection_years < p.MATURITY_MISMATCH_MIN_RESIDUAL_YEARS:
        return 0.0
    return value * (t - p.MATURITY_MISMATCH_T_STAR) / (big_t - p.MATURITY_MISMATCH_T_STAR)


def fccm_exposure(
    exposure_value: float, collateral_value: float, h_e: float, h_c: float, h_fx: float
) -> float:
    """Financial Collateral Comprehensive Method -- Art 223(2), (3), (5) (p. 201-202).

    E* = max{0, E * (1 + HE) - C * (1 - HC - Hfx)}.
    """
    c_va = collateral_value * (1.0 - h_c - h_fx)
    return max(0.0, exposure_value * (1.0 + h_e) - c_va)


@dataclass
class _CRMOutcome:
    """Exposure after funded protection (no regulatory content)."""

    on_star: float
    off_star: float
    notes: list[str]
    citations: list[str]


def apply_funded_protection(exposure: SAExposure) -> _CRMOutcome:
    """Apply eligible financial collateral with the FCCM.

    Reference: Art 223(4)(a) (E with off-balance sheet items at 100%), Art 223(5)
    (E*), Art 228(1) (for off-balance sheet items E* is the value to which the
    Art 111 percentages are applied) (p. 201-207). Collateral is applied to the
    drawn amount first and any remainder to the undrawn notional. HE = 0 (the
    exposure is a loan, not a lent security). No maturity mismatch is assumed
    (the base contract does not carry collateral maturity).
    """
    on, off = exposure.on_balance_amount, exposure.off_balance_notional
    if exposure.financial_collateral_value <= 0.0:
        return _CRMOutcome(on, off, [], [])
    key = exposure.collateral_haircut_class
    if key is None or key not in p.SUPERVISORY_HAIRCUTS:
        return _CRMOutcome(
            on, off, [f"Collateral key {key!r} not in Art 224 Tables 1-3: not recognised."], []
        )
    days = liquidation_period(exposure)
    h_c = supervisory_haircut(key, days)
    h_fx = p.FX_MISMATCH_HAIRCUT[days] if _flag(exposure, "collateral_currency_mismatch") else 0.0
    c_va = exposure.financial_collateral_value * max(0.0, 1.0 - h_c - h_fx)
    on_star = fccm_exposure(on, exposure.financial_collateral_value, 0.0, h_c, h_fx)
    remaining = max(0.0, c_va - on)
    off_star = max(0.0, off - remaining)
    note = f"FCCM: HC {h_c:.4%}, Hfx {h_fx:.4%}, {days}-day liquidation; C_VA {c_va:,.3f}."
    return _CRMOutcome(on_star, off_star, [note], [f"{CRM_PART} Arts 223-224, 228(1)"])


def guarantee_cover(exposure: SAExposure, exposure_100: float) -> tuple[float, list[str]]:
    """Covered amount E_g under the Risk-Weight Substitution Method.

    Reference: Art 233(1)-(4) (G, credit-derivative restructuring haircut, G* =
    G(1 - Hfx) with a 10-day Hfx) and Art 235(1)(a) (E_g = min{GA, E}) (p. 212-214).
    """
    g = exposure.guarantee_amount
    notes: list[str] = []
    if _flag(exposure, "cd_without_restructuring"):
        g = (1.0 - p.CD_NO_RESTRUCTURING_HAIRCUT) * min(g, exposure_100)
        notes.append("Credit derivative without restructuring: Art 233(2) 40% reduction / 60% cap.")
    if _flag(exposure, "guarantee_currency_mismatch"):
        g *= 1.0 - p.FX_MISMATCH_HAIRCUT[p.LIQUIDATION_PERIOD_CAPITAL_MARKET]
        notes.append("Art 233(3)-(4): Hfx 8% (10-day) applied to the guarantee.")
    return min(g, exposure_100), notes


def _guarantor_exposure(exposure: SAExposure) -> SAExposure:
    """Synthetic direct exposure to the protection provider (Art 235(1)(a) r_g)."""
    flags = {
        k[len("guarantor_") :]: v for k, v in exposure.flags.items() if k.startswith("guarantor_")
    }
    if exposure.guarantor_asset_class is None:
        raise ValueError("guarantor_asset_class is required for unfunded credit protection")
    return SAExposure(
        exposure_id=f"{exposure.exposure_id}#guarantor",
        asset_class=exposure.guarantor_asset_class,
        on_balance_amount=1.0,
        rating=exposure.guarantor_rating,
        sovereign_rating=exposure.sovereign_rating,
        domestic_currency_funded=exposure.domestic_currency_funded,
        flags=flags,
    )


def assign_risk_weight(exposure: SAExposure, config: UKCreditConfig) -> RiskWeightResult:
    """Risk weight, CF, exposure value and RWEA for one exposure (UK SA-CR).

    Steps: (1) conversion factor (Art 111 Table A1); (2) funded protection by
    FCCM (CRM Part Arts 223-228); (3) exposure value = drawn* + CF x undrawn*;
    (4) class risk weight (Arts 114-134, Table A2 ordering); (5) Art 123B
    currency mismatch; (6) unfunded protection by the Risk-Weight Substitution
    Method, RW = (E_n r_n + E_g r_g) / E (CRM Part Art 235(1)); (7) RWEA = exposure
    value x RW (Art 113(1)-(2)).
    """
    ccf, ccf_cite = conversion_factor(exposure)
    crm = apply_funded_protection(exposure)
    ead = crm.on_star + ccf * crm.off_star
    base = base_risk_weight(exposure, config, ead)
    notes = list(crm.notes) + list(base.notes)
    citations = [base.citation]
    if exposure.off_balance_notional:
        citations.append(ccf_cite)
    citations.extend(crm.citations)

    rw, cm_cite = apply_currency_mismatch(exposure, base.rw, base.regime_class)
    if cm_cite:
        citations.append(cm_cite)

    if exposure.guarantee_amount > 0.0 and exposure.guarantor_asset_class is not None:
        exposure_100 = crm.on_star + crm.off_star
        if exposure_100 > 0.0:
            covered, g_notes = guarantee_cover(exposure, exposure_100)
            g_rw = base_risk_weight(_guarantor_exposure(exposure), config, 1.0)
            share = covered / exposure_100
            blended = (1.0 - share) * rw + share * g_rw.rw
            if blended < rw:
                notes.extend(g_notes)
                notes.append(f"Guarantee covers {share:.1%} at {g_rw.rw:.0%} ({g_rw.citation}).")
                citations.append(f"{CRM_PART} Arts 233, 235(1)")
                rw = blended
            else:
                notes.append("Guarantor RW not lower than the obligor's: substitution not applied.")

    rw = rw * p.SUPPORT_FACTOR
    return RiskWeightResult(
        exposure_id=exposure.exposure_id,
        jurisdiction=Jurisdiction.UK,
        regime_exposure_class=base.regime_class,
        risk_weight=rw,
        ccf=ccf,
        exposure_amount=ead,
        rwa=ead * rw,
        citation="; ".join(citations),
        notes=notes,
    )


def portfolio_rwa(exposures: list[SAExposure], config: UKCreditConfig) -> CreditRWAResult:
    """Aggregate SA credit RWEA by regime exposure class (Art 92(3)(a), Art 113)."""
    lines = [assign_risk_weight(e, config) for e in exposures]
    rwa_by: dict[str, float] = {}
    exp_by: dict[str, float] = {}
    for line in lines:
        rwa_by[line.regime_exposure_class] = rwa_by.get(line.regime_exposure_class, 0.0) + line.rwa
        exp_by[line.regime_exposure_class] = (
            exp_by.get(line.regime_exposure_class, 0.0) + line.exposure_amount
        )
    return CreditRWAResult(
        jurisdiction=Jurisdiction.UK,
        total_exposure=sum(x.exposure_amount for x in lines),
        total_rwa=sum(x.rwa for x in lines),
        rwa_by_class=rwa_by,
        exposure_by_class=exp_by,
        line_items=lines,
    )


def split_mixed_real_estate(
    exposure: SAExposure, residential_value: float, commercial_value: float
) -> tuple[SAExposure, SAExposure]:
    """Split a mixed real estate exposure -- Art 124(4) (p. 50-51).

    The exposure is split into a residential and a commercial part according to
    the ratio of the property values securing it; each part keeps the
    regulatory/other status of the original (Art 124(4) applies Art 124J to both
    unless both parts are regulatory real estate exposures).
    """
    total = residential_value + commercial_value
    if total <= 0.0:
        raise ValueError("property values must be positive")
    w = residential_value / total

    def part(share: float, cls: AssetClass, value: float, suffix: str) -> SAExposure:
        return exposure.model_copy(
            update={
                "exposure_id": f"{exposure.exposure_id}#{suffix}",
                "asset_class": cls,
                "on_balance_amount": exposure.on_balance_amount * share,
                "off_balance_notional": exposure.off_balance_notional * share,
                "property_value": value,
            }
        )

    return (
        part(w, AssetClass.RESIDENTIAL_RE, residential_value, "RRE"),
        part(1.0 - w, AssetClass.COMMERCIAL_RE, commercial_value, "CRE"),
    )
