"""SA(CR) credit risk under MAS Notice 637 Part VII Division 3.

Implements the Singapore standardised approach for credit risk: asset-class
categorisation (para 7.3.1), credit quality grades from recognised ECAIs
(Annex 7M), the risk-weight tables (Tables 7-1 to 7-22), the currency-mismatch
multiplier (para 7.3.107), CCFs (Annex 7B Table 7B-1), and credit risk
mitigation -- the comprehensive approach FC(CA) with the standard supervisory
haircuts of Annex 7J and guarantee substitution (paras 7.3.112-7.3.113,
Annex 7H Sections 4, 6 and 7).

Singapore permits external ratings (recognised ECAIs: Fitch, Moody's, S&P --
Annex 7N), so rated exposures use the ECRA tables and unrated bank exposures
use the three-grade assessment (SCRA, Table 7-7). There is no 65% investment-
grade corporate option in the Notice; unrated corporates are 100% and unrated
corporate SMEs (revenue <= S$100 million) 85%. Real estate is risk-weighted on
a whole-loan basis only (Tables 7-18 to 7-21); the Notice contains no loan-
splitting option.

Regime-specific ``SAExposure.flags`` read by this module (all default False
unless stated):

=================================  ===========================================================
``singapore_government``           exposure to the Singapore Government or MAS (para 7.3.43)
``supranational_zero_rw``          BIS / IMF / ECB / EU / ESM / EFSF (para 7.3.46)
``pse_treated_as_sovereign``       PSE treated as its central government (para 7.3.48-7.3.49)
``qualifying_mdb``                 Annex 7O qualifying MDB (para 7.3.51)
``foreign_currency_exposure``      unrated bank exposure not in the counterparty's local
                                   currency -- sovereign floor of para 7.3.62
``due_diligence_uplift``           due diligence shows higher risk: one grade worse (7.3.57,
                                   7.3.66, 7.3.70, 7.3.74)
``st_issue_rw_50_or_100``          entity has a rated short-term issue at 50%/100% (7.3.55(a),
                                   7.3.69(a), 7.3.73(a))
``st_issue_rw_150``                entity has a rated short-term issue at 150% (7.3.55(b) etc.)
``obligor_is_individual``          obligor is an individual (default True for retail and RRE,
                                   False otherwise)
``junior_charge``                  regulatory RE exposure against a junior charge (7.3.96)
``adc_secured_by_rre``             ADC exposure secured by RRE (7.3.89)
``adc_meets_underwriting``         7.3.17(f) underwriting met for the ADC 100% (default True)
``secured_by_rre``                 defaulted exposure secured by RRE (7.3.110)
``fx_hedged``                      natural/financial hedge >= 90% of instalments (7.3.108)
``major_stake_solo_400``           major-stake FI investment risk-weighted at 400% (6.1.6)
``cash_item`` / ``gold_bullion``   cash items (7.3.40)
``cash_item_in_collection``        cheques/drafts in collection (7.3.41)
``residual_value_leased_asset``    lessor residual value (7.3.1(l)(iii)) -- 100%
``collateral_currency_mismatch``   collateral in a different currency (Annex 7J para 2.4)
``guarantee_currency_mismatch``    guarantee in a different currency (Annex 7H para 6.2)
``repo_style`` / ``capital_market``  holding-period class for haircuts (Table 7J-2); default
                                   secured lending (20 business days)
``guarantor_qualifying_mdb``       guarantor is a qualifying MDB
``guarantor_scra_grade_a``         unrated bank guarantor is SCRA Grade A (else Grade B)
=================================  ===========================================================

All amounts in SGD millions (the engine is currency-agnostic). Risk weights
are decimals (0.20 = 20%).

References:
    - MAS Notice 637 paras 7.2.11-7.2.17, 7.3.1-7.3.125 (pp. 7-13 to 7-65)
    - MAS Notice 637 Annex 7B (p. 7-179), Annex 7H Sections 4-7 (pp. 7-248 to 7-254),
      Annex 7J (pp. 7-259 to 7-264), Annex 7M (p. 7-271)
    - Basel Framework CRE20, CRE22 (for comparison only)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    OBSCategory,
    PFPhase,
    RatingBucket,
    SAExposure,
    SCRAGrade,
)
from src.jurisdictions.sg import params as p

# =========================================================================
#  Rating helpers
# =========================================================================


def credit_quality_grade(rating: RatingBucket) -> int | None:
    """Map a rating bucket to an MAS credit quality grade 1-6 (None = unrated).

    Reference: MAS Notice 637 Annex 7M Table 7M-1 (p. 7-271); para 7.3.23.
    """
    return p.CQS_BY_RATING[rating]


def _worsen(grade: int | None, uplift: bool) -> int | None:
    """Apply the one-grade due-diligence uplift of paras 7.3.57 / 7.3.70 / 7.3.74.

    Reference: MAS Notice 637 paras 7.3.57, 7.3.66, 7.3.70, 7.3.74 (pp. 7-45, 7-48, 7-49, 7-50).
    """
    if not uplift or grade is None:
        return grade
    return min(grade + 1, 6)


def _band_index(value: float, upper_bounds: tuple[float, ...]) -> int:
    """Index of the first band whose inclusive upper bound is >= value.

    Reference: LTV banding convention of Tables 7-18 to 7-21 ("50% < LTV <= 60%").
    """
    for i, bound in enumerate(upper_bounds):
        if value <= bound:
            return i
    return len(upper_bounds)


# =========================================================================
#  Table lookups (public, individually tested)
# =========================================================================


def sovereign_rw(rating: RatingBucket) -> float:
    """Central government / central bank risk weight.

    Reference: MAS Notice 637 Table 7-1, para 7.3.42 (p. 7-42).
    """
    return p.SOVEREIGN_RW[credit_quality_grade(rating)]


def pse_rw(
    rating: RatingBucket, sovereign_rating: RatingBucket, treated_as_sovereign: bool
) -> float:
    """PSE risk weight (Table 7-2, or Table 7-3 where treated as the central government).

    Reference: MAS Notice 637 paras 7.3.47-7.3.49, Tables 7-2 and 7-3 (pp. 7-42, 7-43).
    Table 7-3 applies only where the central government has grade "1" or "2".
    """
    grade = credit_quality_grade(rating)
    sov_grade = credit_quality_grade(sovereign_rating)
    if treated_as_sovereign and sov_grade in p.PSE_SOVEREIGN_TREATED_RW:
        return p.PSE_SOVEREIGN_TREATED_RW[sov_grade][grade]
    return p.PSE_RW[grade]


def mdb_rw(rating: RatingBucket, qualifying: bool) -> float:
    """MDB risk weight.

    Reference: MAS Notice 637 Table 7-4 and para 7.3.51 (p. 7-43).
    """
    if qualifying:
        return p.QUALIFYING_MDB_RW
    return p.MDB_RW[credit_quality_grade(rating)]


def bank_rw(
    rating: RatingBucket,
    *,
    short_term: bool = False,
    scra_grade: SCRAGrade | None = None,
    scra_grade_a_enhanced: bool = False,
    short_term_issue_grade: str | None = None,
) -> float:
    """Bank asset class risk weight (rated ECRA or unrated assessment grades).

    Reference: MAS Notice 637 paras 7.3.52-7.3.61, Tables 7-5, 7-6 and 7-7 (pp. 7-44 to 7-46).
    An unrated bank without an assessment grade is treated as Grade C -- para 7.3.60(b)(ii)
    and (c) require Grade C where the published requirements are not available.
    """
    if short_term_issue_grade is not None:
        return p.ST_ISSUE_RW[short_term_issue_grade]
    grade = credit_quality_grade(rating)
    if grade is not None:
        return p.BANK_RATED_SHORT_TERM_RW[grade] if short_term else p.BANK_RATED_RW[grade]
    g = (scra_grade or SCRAGrade.C).value
    if short_term:
        return p.BANK_SCRA_SHORT_TERM_RW[g]
    if g == "A" and scra_grade_a_enhanced:
        return p.BANK_SCRA_GRADE_A_ENHANCED_RW
    return p.BANK_SCRA_RW[g]


def covered_bond_rw(rated: bool, rating: RatingBucket, issuer_bank_rw: float) -> float:
    """Covered bond risk weight.

    Reference: MAS Notice 637 paras 7.3.64-7.3.65, Tables 7-8 and 7-9 (p. 7-48). An
    issue-specifically rated bond uses Table 7-8; otherwise Table 7-9 maps the issuing bank's
    risk weight (Table 7-5 or 7-7). An issuer weight between table columns is rounded up to the
    next column (conservative).
    """
    grade = credit_quality_grade(rating)
    if rated and grade is not None:
        return p.COVERED_BOND_RATED_RW[grade]
    for issuer_rw in sorted(p.COVERED_BOND_UNRATED_RW):
        if issuer_bank_rw <= issuer_rw + 1e-12:
            return p.COVERED_BOND_UNRATED_RW[issuer_rw]
    return p.COVERED_BOND_UNRATED_RW[1.50]


def corporate_rw(
    rating: RatingBucket, *, sme: bool = False, short_term_issue_grade: str | None = None
) -> float:
    """General corporate (Table 7-10) or corporate SME (Table 7-12) risk weight.

    Reference: MAS Notice 637 paras 7.3.67-7.3.74, Tables 7-10 to 7-13 (pp. 7-49, 7-50).
    """
    if short_term_issue_grade is not None:
        return p.ST_ISSUE_RW[short_term_issue_grade]
    table = p.CORPORATE_SME_RW if sme else p.CORPORATE_RW
    return table[credit_quality_grade(rating)]


def specialised_lending_rw(
    asset_class: AssetClass, rating: RatingBucket, pf_phase: PFPhase | None
) -> float:
    """Specialised lending risk weight (issue-specific rated, else Table 7-15).

    Reference: MAS Notice 637 paras 7.3.75-7.3.77, Tables 7-14 and 7-15 (pp. 7-50, 7-51).
    Issuer assessments must not be used (para 7.3.75); ``rating`` must be issue-specific.
    """
    grade = credit_quality_grade(rating)
    if grade is not None:
        return p.SL_RATED_RW[grade]
    if asset_class is AssetClass.SPECIALISED_LENDING_PF:
        if pf_phase is PFPhase.HIGH_QUALITY_OPERATIONAL:
            return p.SL_PF_HIGH_QUALITY_OPERATIONAL_RW
        if pf_phase is PFPhase.OPERATIONAL:
            return p.SL_PF_OPERATIONAL_RW
        return p.SL_PF_OTHER_RW
    return p.SL_OF_CF_RW


def equity_phase_in_rw(as_of: date, speculative_unlisted: bool) -> float:
    """Equity risk weight under the phase-in of Table 7-16.

    Reference: MAS Notice 637 paras 7.3.80, 7.3.85, Table 7-16 (pp. 7-53, 7-55). Dates before
    1 July 2024 are outside this Notice's equity regime; the fully phased-in weights are
    returned (conservative).
    """
    rw = p.SPECULATIVE_UNLISTED_EQUITY_RW if speculative_unlisted else p.OTHER_EQUITY_RW
    for start, spec, other in p.EQUITY_PHASE_IN:
        if as_of >= start:
            rw = spec if speculative_unlisted else other
    return rw


def rre_rw(ltv: float, cash_flow_dependent: bool) -> float:
    """Regulatory RRE risk weight by LTV band (whole-loan).

    Reference: MAS Notice 637 paras 7.3.91-7.3.92, Tables 7-18 and 7-19 (pp. 7-56, 7-57).
    """
    table = p.RRE_CASH_FLOW_RW if cash_flow_dependent else p.RRE_GENERAL_RW
    return table[_band_index(ltv, p.RRE_LTV_UPPER_BOUNDS)]


def cre_rw(ltv: float, cash_flow_dependent: bool, counterparty_rw: float) -> float:
    """Regulatory CRE risk weight (whole-loan).

    Reference: MAS Notice 637 paras 7.3.93-7.3.95, Tables 7-20 and 7-21 (p. 7-57).
    """
    if cash_flow_dependent:
        return p.CRE_CASH_FLOW_RW[_band_index(ltv, p.CRE_CASH_FLOW_LTV_UPPER_BOUNDS)]
    if ltv <= p.CRE_GENERAL_LTV_THRESHOLD:
        return min(p.CRE_GENERAL_LOW_LTV_CAP, counterparty_rw)
    return counterparty_rw


def other_re_rw(cash_flow_dependent: bool, counterparty_rw: float) -> float:
    """Other (non-regulatory) real estate risk weight.

    Reference: MAS Notice 637 paras 7.3.98-7.3.99 (p. 7-58).
    """
    return p.OTHER_RE_CASH_FLOW_RW if cash_flow_dependent else counterparty_rw


def is_lowest_ltv_bucket(ltv: float, residential: bool, cash_flow_dependent: bool) -> bool:
    """Whether the LTV falls in the lowest bucket of the applicable RE table.

    Reference: MAS Notice 637 para 7.3.96 (p. 7-57) -- the junior-charge multiplier does not
    apply in the lowest LTV bucket of Tables 7-18, 7-19, 7-20 or 7-21.
    """
    if residential:
        return ltv <= p.RRE_LTV_UPPER_BOUNDS[0]
    if cash_flow_dependent:
        return ltv <= p.CRE_CASH_FLOW_LTV_UPPER_BOUNDS[0]
    return ltv <= p.CRE_GENERAL_LTV_THRESHOLD


def defaulted_rw(specific_provision_pct: float) -> float:
    """Defaulted exposure risk weight by specific allowances.

    Reference: MAS Notice 637 para 7.3.109, Table 7-22 (p. 7-61): < 20% -> 150%,
    no less than 20% -> 100%.
    """
    if specific_provision_pct < p.DEFAULTED_PROVISION_THRESHOLD:
        return p.DEFAULTED_LOW_PROVISION_RW
    return p.DEFAULTED_HIGH_PROVISION_RW


def apply_currency_mismatch(rw: float) -> float:
    """Apply the 1.5x currency-mismatch multiplier, capped at 150%.

    Reference: MAS Notice 637 para 7.3.107 (p. 7-60). If the base weight already exceeds
    150% the cap is not applied downwards (the multiplier never reduces a weight).
    """
    return max(rw, min(rw * p.CURRENCY_MISMATCH_MULTIPLIER, p.CURRENCY_MISMATCH_MAX_RW))


# =========================================================================
#  CCF
# =========================================================================


def ccf_for(category: OBSCategory | None, original_maturity_months: float | None = None) -> float:
    """Standardised CCF for an off-balance sheet item.

    Reference: MAS Notice 637 para 7.2.11 and Annex 7B Table 7B-1 (pp. 7-179, 7-180). Item (h)
    (20%) is limited to self-liquidating trade items with an original maturity below one year.
    An item without a category is treated as item (d) (100%, conservative).
    """
    if category is None:
        return p.CCF[OBSCategory.OTHER_100]
    if (
        category is OBSCategory.SHORT_TERM_TRADE_LC
        and original_maturity_months is not None
        and original_maturity_months >= p.TRADE_LC_MAX_ORIGINAL_MONTHS
    ):
        return p.TRADE_LC_LONG_DATED_CCF
    return p.CCF[category]


def ccf_commitment_on_item(commitment_ccf: float, underlying_item_ccf: float) -> float:
    """CCF for a commitment to provide another off-balance sheet item: the lower of the two.

    Reference: MAS Notice 637 Annex 7B para 1.2 and footnote 339 (p. 7-179).
    """
    return min(commitment_ccf, underlying_item_ccf)


# =========================================================================
#  CRM -- FC(CA) haircuts, maturity mismatch, guarantees
# =========================================================================


def scale_haircut(h10: float, holding_period_days: int, remargin_days: int = 1) -> float:
    """Scale a 10-day haircut to the minimum holding period / remargining frequency.

    Reference: MAS Notice 637 Annex 7J para 3.4 (p. 7-264):
    H = H10 x sqrt((NR + (TM - 1)) / 10).
    """
    return h10 * math.sqrt(
        (remargin_days + (holding_period_days - 1)) / p.HAIRCUT_BASE_HOLDING_DAYS
    )


def supervisory_haircut(key: str, holding_period_days: int = 10, remargin_days: int = 1) -> float:
    """Standard supervisory haircut from Table 7J-1, scaled per Annex 7J para 3.4.

    Reference: MAS Notice 637 Annex 7J Table 7J-1 (pp. 7-261, 7-262) and para 3.4.
    Raises ``KeyError`` for an unknown key.
    """
    return scale_haircut(p.SUPERVISORY_HAIRCUTS[key], holding_period_days, remargin_days)


def exposure_after_collateral(e: float, c: float, he: float, hc: float, hfx: float) -> float:
    """FC(CA) adjusted exposure.

    Reference: MAS Notice 637 Annex 7J para 1.1 (p. 7-259):
    E* = max{0, [E(1 + HE) - C(1 - HC - HFX)]}.
    """
    return max(0.0, e * (1.0 + he) - c * (1.0 - hc - hfx))


def maturity_mismatch_adjust(
    value: float,
    mitigant_residual_years: float,
    exposure_residual_years: float,
    mitigant_original_years: float = 1.0,
) -> float:
    """Value of a credit risk mitigant adjusted for maturity mismatch.

    Reference: MAS Notice 637 Annex 7H paras 7.1 and 7.4 (p. 7-254):
    PA = P x (t - 0.25) / (T - 0.25), t = min(T, mitigant residual), T = min(5, exposure
    residual). Not recognised if the mitigant's original maturity < 1 year or residual
    maturity < 3 months where there is a mismatch.
    """
    t_cap = min(p.MATURITY_MISMATCH_T_CAP_YEARS, exposure_residual_years)
    if mitigant_residual_years >= exposure_residual_years:
        return value
    if (
        mitigant_residual_years < p.MATURITY_MISMATCH_MIN_RESIDUAL_YEARS
        or mitigant_original_years < p.MATURITY_MISMATCH_MIN_ORIGINAL_YEARS
    ):
        return 0.0
    t = min(t_cap, mitigant_residual_years)
    return (
        value * (t - p.MATURITY_MISMATCH_OFFSET_YEARS) / (t_cap - p.MATURITY_MISMATCH_OFFSET_YEARS)
    )


def guarantee_protected_amount(notional: float, currency_mismatch: bool) -> float:
    """Protected amount of a guarantee or credit derivative after the FX haircut.

    Reference: MAS Notice 637 Annex 7H para 6.2 (p. 7-253): GA = G x (1 - HFX), HFX = 8%.
    """
    return notional * (1.0 - p.FX_MISMATCH_HAIRCUT) if currency_mismatch else notional


def major_stake_1250_amounts(exposures: list[float], eligible_total_capital: float) -> list[float]:
    """Portion of each major-stake (non-FI) equity/sub-debt exposure risk-weighted at 1250%.

    Reference: MAS Notice 637 paras 7.3.82-7.3.83 (pp. 7-53, 7-54). For each exposure the
    excess over 15% of Eligible Total Capital is at 1250% (7.3.82(a)). The aggregate excess of
    all such exposures over 60% of Eligible Total Capital is allocated pro rata to the
    within-15% portions (7.3.83(a)-(e)). The ratio in 7.3.83(d) is capped at 1 so that no
    amount is counted twice (interpretive cap; the text does not state one).
    """
    limit = p.MAJOR_STAKE_INDIVIDUAL_LIMIT * eligible_total_capital
    capped = [min(x, limit) for x in exposures]
    individual_excess = [x - c for x, c in zip(exposures, capped, strict=True)]
    aggregate_excess = max(
        0.0, sum(exposures) - p.MAJOR_STAKE_AGGREGATE_LIMIT * eligible_total_capital
    )
    base = sum(capped)
    ratio = min(1.0, aggregate_excess / base) if base > 0 else 0.0
    return [ex + c * ratio for ex, c in zip(individual_excess, capped, strict=True)]


# =========================================================================
#  Engine
# =========================================================================


@dataclass
class SGRiskWeightOutcome:
    """Internal outcome of an SA(CR) risk-weight assignment (before CRM)."""

    risk_weight: float
    regime_class: str
    citation: str
    notes: list[str] = field(default_factory=list)


def _flag(exposure: SAExposure, key: str, default: bool = False) -> bool:
    """Read a regime-specific boolean flag (see module docstring)."""
    return exposure.flags.get(key, default)


def _st_issue_grade(exposure: SAExposure) -> str | None:
    """Short-term issue-specific grade (Table 7M-2), if any."""
    if exposure.short_term_rating is None:
        return None
    return p.ST_GRADE_BY_RATING[exposure.short_term_rating]


def _apply_st_issue_floors(
    rw: float, exposure: SAExposure, short_term: bool, notes: list[str]
) -> float:
    """Floors on unrated exposures to entities with rated short-term issues.

    Reference: MAS Notice 637 paras 7.3.55, 7.3.69, 7.3.73 (pp. 7-44, 7-49, 7-50).
    """
    if credit_quality_grade(exposure.rating) is not None or exposure.short_term_rating is not None:
        return rw
    if _flag(exposure, "st_issue_rw_150"):
        notes.append(
            "unrated exposure to entity with 150% short-term issue: 150% (7.3.55(b)/7.3.69(b))"
        )
        return max(rw, p.UNRATED_FLOOR_IF_ISSUE_150)
    if short_term and _flag(exposure, "st_issue_rw_50_or_100"):
        notes.append("unrated short-term exposure floored at 100% (7.3.55(a)/7.3.69(a))")
        return max(rw, p.UNRATED_ST_FLOOR_IF_ISSUE_50_OR_100)
    return rw


class SGCreditRiskEngine:
    """MAS Notice 637 SA(CR) risk-weight engine.

    Reference: MAS Notice 637 Part VII Division 3 (pp. 7-23 to 7-70).
    """

    def __init__(self, as_of: date) -> None:
        """Create the engine for a reporting date (drives the equity phase-in of Table 7-16)."""
        self.as_of = as_of

    # ------------------------------------------------------------------ helpers

    def _is_sme(self, exposure: SAExposure) -> bool:
        """Small business test: revenue <= S$100 million (para 7.3.4, p. 7-28)."""
        if exposure.annual_turnover is not None:
            return exposure.annual_turnover <= p.SME_REVENUE_THRESHOLD_SGD_M
        return exposure.is_sme or exposure.asset_class is AssetClass.CORPORATE_SME

    def _bank_short_term(self, exposure: SAExposure) -> bool:
        """Short-term bank exposure (paras 7.3.52(a)-(b) / 7.3.58(a)-(b), pp. 7-43 to 7-45)."""
        om = exposure.original_maturity_months
        if om is None:
            return False
        if om <= p.BANK_SHORT_TERM_MAX_ORIGINAL_MONTHS:
            return True
        return exposure.is_trade_related and om <= p.BANK_TRADE_SHORT_TERM_MAX_ORIGINAL_MONTHS

    def _bank(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Bank asset class (paras 7.3.52-7.3.63, pp. 7-43 to 7-48)."""
        notes: list[str] = []
        short_term = self._bank_short_term(exposure)
        st_grade = _st_issue_grade(exposure)
        grade = _worsen(
            credit_quality_grade(exposure.rating), _flag(exposure, "due_diligence_uplift")
        )
        rating = _rating_from_grade(grade)
        rw = bank_rw(
            rating,
            short_term=short_term,
            scra_grade=exposure.scra_grade,
            scra_grade_a_enhanced=exposure.scra_grade_a_enhanced,
            short_term_issue_grade=st_grade,
        )
        if st_grade is not None:
            cite = "MAS 637 para 7.3.54, Table 7-6"
        elif grade is not None:
            cite = "MAS 637 para 7.3.52, Table 7-5" + (" (short-term)" if short_term else "")
        else:
            if exposure.scra_grade is None:
                notes.append("unrated bank without assessment grade treated as Grade C (7.3.60)")
            cite = "MAS 637 paras 7.3.58-7.3.60, Table 7-7" + (
                " (short-term)" if short_term else ""
            )
            if (
                exposure.scra_grade is SCRAGrade.A
                and exposure.scra_grade_a_enhanced
                and not short_term
            ):
                cite = "MAS 637 para 7.3.59 (Grade A, CET1 >= 14% and leverage >= 5%)"
            trade_exempt = (
                exposure.is_trade_related
                and exposure.original_maturity_months is not None
                and exposure.original_maturity_months < p.TRADE_LC_MAX_ORIGINAL_MONTHS
            )
            if _flag(exposure, "foreign_currency_exposure") and not trade_exempt:
                floor = sovereign_rw(exposure.sovereign_rating)
                if floor > rw:
                    notes.append(f"sovereign floor {floor:.0%} applied (7.3.62)")
                    rw = floor
                    cite += "; para 7.3.62 sovereign floor"
        rw = _apply_st_issue_floors(rw, exposure, short_term, notes)
        return SGRiskWeightOutcome(rw, "7.3.1(e) bank", cite, notes)

    def _corporate(self, exposure: SAExposure, sme: bool) -> SGRiskWeightOutcome:
        """General corporate / corporate SME (paras 7.3.67-7.3.74, pp. 7-49, 7-50)."""
        notes: list[str] = []
        st_grade = _st_issue_grade(exposure)
        grade = _worsen(
            credit_quality_grade(exposure.rating), _flag(exposure, "due_diligence_uplift")
        )
        rw = corporate_rw(_rating_from_grade(grade), sme=sme, short_term_issue_grade=st_grade)
        if sme:
            cls, cite = "7.3.1(g)(ii) corporate SME", "MAS 637 para 7.3.71, Table 7-12"
            if st_grade is not None:
                cite = "MAS 637 para 7.3.72, Table 7-13"
        else:
            cls, cite = "7.3.1(g)(i) general corporate", "MAS 637 para 7.3.67, Table 7-10"
            if st_grade is not None:
                cite = "MAS 637 para 7.3.68, Table 7-11"
        om = exposure.original_maturity_months
        short_term = om is not None and om <= p.CORPORATE_SHORT_TERM_MAX_ORIGINAL_MONTHS
        rw = _apply_st_issue_floors(rw, exposure, short_term, notes)
        return SGRiskWeightOutcome(rw, cls, cite, notes)

    def unsecured_counterparty_rw(self, exposure: SAExposure) -> float:
        """Risk weight of the obligor for real estate counterparty-weight tests.

        Reference: MAS Notice 637 paras 7.3.94 and 7.3.98 (pp. 7-57, 7-58): individual 75%,
        small business 85%, otherwise the risk weight of an unsecured exposure to the obligor
        (here the general corporate weight, Table 7-10).
        """
        if _flag(
            exposure, "obligor_is_individual", exposure.asset_class is AssetClass.RESIDENTIAL_RE
        ):
            return p.RE_COUNTERPARTY_INDIVIDUAL_RW
        if self._is_sme(exposure):
            return p.RE_COUNTERPARTY_SMALL_BUSINESS_RW
        return corporate_rw(exposure.rating)

    def _real_estate(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Regulatory and other real estate, residential and commercial (7.3.91-7.3.103)."""
        notes: list[str] = []
        residential = exposure.asset_class is AssetClass.RESIDENTIAL_RE
        cfd = exposure.is_cash_flow_dependent
        cpty_rw = self.unsecured_counterparty_rw(exposure)
        other_rw = other_re_rw(cfd, cpty_rw)
        kind = "RRE" if residential else "CRE"
        if not exposure.is_regulatory_real_estate or exposure.ltv is None:
            if exposure.is_regulatory_real_estate:
                notes.append("no LTV supplied: treated as other real estate (7.3.17(g) not met)")
            cite = "MAS 637 para 7.3.99" if cfd else "MAS 637 para 7.3.98"
            return SGRiskWeightOutcome(
                other_rw, f"7.3.1(k)(iii) other real estate ({kind})", cite, notes
            )
        ltv = exposure.ltv
        if residential:
            rw = rre_rw(ltv, cfd)
            cite = "MAS 637 para 7.3.92, Table 7-19" if cfd else "MAS 637 para 7.3.91, Table 7-18"
        else:
            rw = cre_rw(ltv, cfd, cpty_rw)
            cite = (
                "MAS 637 para 7.3.95, Table 7-21"
                if cfd
                else "MAS 637 paras 7.3.93-7.3.94, Table 7-20"
            )
        if _flag(exposure, "junior_charge") and not is_lowest_ltv_bucket(ltv, residential, cfd):
            rw = min(rw * p.JUNIOR_CHARGE_MULTIPLIER, other_rw)
            cite += "; para 7.3.96 junior-charge x1.25 (capped at other-RE weight)"
        return SGRiskWeightOutcome(rw, f"7.3.1(k)(ii) regulatory real estate ({kind})", cite, notes)

    def _adc(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """ADC asset sub-class (paras 7.3.88-7.3.90, p. 7-55)."""
        if (
            _flag(exposure, "adc_secured_by_rre")
            and _flag(exposure, "adc_meets_underwriting", True)
            and exposure.ltv is not None
            and exposure.ltv <= p.ADC_RRE_MAX_LTV
        ):
            return SGRiskWeightOutcome(
                p.ADC_RRE_QUALIFYING_RW, "7.3.1(k)(i) ADC", "MAS 637 para 7.3.89"
            )
        return SGRiskWeightOutcome(p.ADC_RW, "7.3.1(k)(i) ADC", "MAS 637 para 7.3.88")

    def _equity(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Equity exposures (paras 7.3.80-7.3.85, Table 7-16; 6.1.5(p)(iii); 6.1.6)."""
        notes: list[str] = []
        et = exposure.equity_type
        if _flag(exposure, "major_stake_solo_400"):
            return SGRiskWeightOutcome(
                p.MAJOR_STAKE_SOLO_RW,
                "7.3.1(l)(ii) other exposures",
                "MAS 637 paras 6.1.6, 7.3.105 (Solo, MAS approval)",
            )
        if et is EquityType.SIGNIFICANT_FI:
            return SGRiskWeightOutcome(
                p.THRESHOLD_INVESTMENT_RW,
                "7.3.1(l)(i) other exposures",
                "MAS 637 paras 6.1.5(p)(iii), 7.3.104",
            )
        speculative = et is EquityType.SPECULATIVE_UNLISTED
        if et is EquityType.LEGISLATIVE_PROGRAMME:
            notes.append(
                "no legislated-programme carve-out in MAS 637: treated as other equity (7.3.80(b))"
            )
        rw = equity_phase_in_rw(self.as_of, speculative)
        full = p.SPECULATIVE_UNLISTED_EQUITY_RW if speculative else p.OTHER_EQUITY_RW
        cite = f"MAS 637 para 7.3.80({'a' if speculative else 'b'})"
        if rw < full:
            cite += f"; para 7.3.85 Table 7-16 phase-in as of {self.as_of.isoformat()}"
        return SGRiskWeightOutcome(rw, "7.3.1(h) equity and subordinated debt", cite, notes)

    def _retail(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Regulatory retail and other retail (paras 7.3.1(i)-(j), 7.3.86-7.3.87)."""
        notes: list[str] = []
        individual = _flag(exposure, "obligor_is_individual", not exposure.is_sme)
        if exposure.asset_class is AssetClass.RETAIL_OTHER:
            if not individual:
                notes.append(
                    "other retail is restricted to individuals (7.3.1(j)); small business "
                    "re-classified to corporate SME"
                )
                return self._corporate(exposure, sme=True)
            return SGRiskWeightOutcome(
                p.OTHER_RETAIL_RW, "7.3.1(j) other retail", "MAS 637 para 7.3.87"
            )
        qualifies = exposure.meets_regulatory_retail_criteria
        agg = exposure.aggregate_retail_exposure_to_obligor
        if agg is not None and agg > p.REGULATORY_RETAIL_MAX_SGD_M:
            qualifies = False
            notes.append("aggregate exposure above S$2 million (7.3.1(i)(iii))")
        if not qualifies:
            if individual:
                return SGRiskWeightOutcome(
                    p.OTHER_RETAIL_RW, "7.3.1(j) other retail", "MAS 637 para 7.3.87", notes
                )
            out = self._corporate(exposure, sme=self._is_sme(exposure))
            out.notes = notes + out.notes
            return out
        if exposure.asset_class is AssetClass.RETAIL_TRANSACTOR or exposure.is_transactor:
            return SGRiskWeightOutcome(
                p.RETAIL_TRANSACTOR_RW,
                "7.3.1(i)(A) regulatory retail transactor",
                "MAS 637 para 7.3.86, Table 7-17",
                notes,
            )
        return SGRiskWeightOutcome(
            p.RETAIL_NON_TRANSACTOR_RW,
            "7.3.1(i)(B) regulatory retail non-transactor",
            "MAS 637 para 7.3.86, Table 7-17",
            notes,
        )

    def _other_assets(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Cash items and other exposures (paras 7.3.40-7.3.41, 7.3.104-7.3.106)."""
        if _flag(exposure, "cash_item_in_collection"):
            return SGRiskWeightOutcome(
                p.CASH_EQUIVALENT_IN_COLLECTION_RW, "7.3.1(a) cash items", "MAS 637 para 7.3.41"
            )
        if _flag(exposure, "cash_item") or _flag(exposure, "gold_bullion"):
            return SGRiskWeightOutcome(p.CASH_ITEM_RW, "7.3.1(a) cash items", "MAS 637 para 7.3.40")
        if _flag(exposure, "major_stake_solo_400"):
            return SGRiskWeightOutcome(
                p.MAJOR_STAKE_SOLO_RW, "7.3.1(l)(ii) other exposures", "MAS 637 para 7.3.105"
            )
        if _flag(exposure, "threshold_250"):
            return SGRiskWeightOutcome(
                p.THRESHOLD_INVESTMENT_RW, "7.3.1(l)(i) other exposures", "MAS 637 para 7.3.104"
            )
        return SGRiskWeightOutcome(
            p.OTHER_EXPOSURES_RW, "7.3.1(l) other exposures", "MAS 637 para 7.3.106"
        )

    def _defaulted(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Defaulted exposures (paras 7.3.109-7.3.111, p. 7-61)."""
        rre = exposure.asset_class is AssetClass.RESIDENTIAL_RE or _flag(exposure, "secured_by_rre")
        if rre and not exposure.is_cash_flow_dependent:
            return SGRiskWeightOutcome(
                p.DEFAULTED_RRE_RW, "defaulted (RRE)", "MAS 637 para 7.3.110"
            )
        rw = defaulted_rw(exposure.specific_provision_pct)
        return SGRiskWeightOutcome(rw, "defaulted", "MAS 637 para 7.3.109, Table 7-22")

    # ------------------------------------------------------------------ dispatch

    def base_risk_weight(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Pre-CRM risk weight for any ``AssetClass`` (incl. currency-mismatch multiplier).

        Reference: MAS Notice 637 paras 7.3.39-7.3.111 (pp. 7-40 to 7-62).
        """
        out = self._base_rw_before_fx(exposure)
        if self._currency_mismatch_applies(exposure):
            new_rw = apply_currency_mismatch(out.risk_weight)
            if new_rw != out.risk_weight:
                out.notes.append(
                    f"currency mismatch x1.5 (cap 150%): {out.risk_weight:.0%} -> {new_rw:.0%}"
                )
                out.risk_weight = new_rw
                out.citation += "; para 7.3.107"
        return out

    def _currency_mismatch_applies(self, exposure: SAExposure) -> bool:
        """Scope of the currency-mismatch multiplier (paras 7.3.107-7.3.108, pp. 7-60, 7-61)."""
        if exposure.currency_matches_borrower_income or _flag(exposure, "fx_hedged"):
            return False
        if exposure.is_defaulted or exposure.asset_class is AssetClass.DEFAULTED:
            return False
        ac = exposure.asset_class
        if ac in (
            AssetClass.RETAIL_REGULATORY,
            AssetClass.RETAIL_TRANSACTOR,
            AssetClass.RETAIL_OTHER,
        ):
            return _flag(exposure, "obligor_is_individual", not exposure.is_sme)
        if ac is AssetClass.RESIDENTIAL_RE:
            return _flag(exposure, "obligor_is_individual", True)
        return False

    def _base_rw_before_fx(self, exposure: SAExposure) -> SGRiskWeightOutcome:
        """Dispatch on the asset class (para 7.3.1 categorisation)."""
        ac = exposure.asset_class
        if exposure.is_defaulted or ac is AssetClass.DEFAULTED:
            return self._defaulted(exposure)
        if ac is AssetClass.SOVEREIGN:
            if _flag(exposure, "singapore_government") and exposure.domestic_currency_funded:
                return SGRiskWeightOutcome(
                    p.SG_GOVERNMENT_SGD_RW, "7.3.1(b) central government", "MAS 637 para 7.3.43"
                )
            if _flag(exposure, "supranational_zero_rw"):
                return SGRiskWeightOutcome(
                    p.SUPRANATIONAL_ZERO_RW, "7.3.1(b) central government", "MAS 637 para 7.3.46"
                )
            notes = []
            if exposure.domestic_currency_funded and not _flag(exposure, "singapore_government"):
                notes.append(
                    "para 7.3.44 permits the host regulator's local-currency weight; "
                    "Table 7-1 weight retained (no host weight supplied)"
                )
            return SGRiskWeightOutcome(
                sovereign_rw(exposure.rating),
                "7.3.1(b) central government",
                "MAS 637 para 7.3.42, Table 7-1",
                notes,
            )
        if ac is AssetClass.PSE:
            treated = _flag(exposure, "pse_treated_as_sovereign")
            sov_grade = credit_quality_grade(exposure.sovereign_rating)
            table = "Table 7-3" if treated and sov_grade in (1, 2) else "Table 7-2"
            return SGRiskWeightOutcome(
                pse_rw(exposure.rating, exposure.sovereign_rating, treated),
                "7.3.1(c) PSE",
                f"MAS 637 paras 7.3.47-7.3.48, {table}",
            )
        if ac is AssetClass.MDB:
            q = _flag(exposure, "qualifying_mdb")
            return SGRiskWeightOutcome(
                mdb_rw(exposure.rating, q),
                "7.3.1(d) MDB",
                "MAS 637 para 7.3.51" if q else "MAS 637 para 7.3.50, Table 7-4",
            )
        if ac is AssetClass.BANK:
            return self._bank(exposure)
        if ac is AssetClass.COVERED_BOND:
            issuer = bank_rw(
                exposure.rating,
                scra_grade=exposure.scra_grade,
                scra_grade_a_enhanced=exposure.scra_grade_a_enhanced,
            )
            rated = (
                exposure.covered_bond_rated and credit_quality_grade(exposure.rating) is not None
            )
            cite = "MAS 637 para 7.3.64, Table 7-8" if rated else "MAS 637 para 7.3.65, Table 7-9"
            return SGRiskWeightOutcome(
                covered_bond_rw(rated, exposure.rating, issuer), "7.3.1(f) covered bond", cite
            )
        if ac in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME):
            return self._corporate(exposure, sme=self._is_sme(exposure))
        if ac in (
            AssetClass.SPECIALISED_LENDING_PF,
            AssetClass.SPECIALISED_LENDING_OF,
            AssetClass.SPECIALISED_LENDING_CF,
        ):
            rated = credit_quality_grade(exposure.rating) is not None
            return SGRiskWeightOutcome(
                specialised_lending_rw(ac, exposure.rating, exposure.pf_phase),
                "7.3.1(g)(iii) specialised lending",
                "MAS 637 para 7.3.75, Table 7-14"
                if rated
                else "MAS 637 paras 7.3.76-7.3.77, Table 7-15",
            )
        if ac is AssetClass.SUBORDINATED_DEBT:
            return SGRiskWeightOutcome(
                p.SUBORDINATED_DEBT_RW,
                "7.3.1(h) equity and subordinated debt",
                "MAS 637 para 7.3.80(c)",
            )
        if ac is AssetClass.EQUITY:
            return self._equity(exposure)
        if ac in (
            AssetClass.RETAIL_REGULATORY,
            AssetClass.RETAIL_TRANSACTOR,
            AssetClass.RETAIL_OTHER,
        ):
            return self._retail(exposure)
        if ac in (AssetClass.RESIDENTIAL_RE, AssetClass.COMMERCIAL_RE):
            return self._real_estate(exposure)
        if ac is AssetClass.LAND_ADC:
            return self._adc(exposure)
        return self._other_assets(exposure)

    # ------------------------------------------------------------------ CRM

    def guarantor_rw(self, exposure: SAExposure) -> float | None:
        """Risk weight of an eligible protection provider (substitution approach).

        Reference: MAS Notice 637 para 7.3.112(b)(i) (p. 7-62) -- the risk weight applicable to
        the eligible protection provider under Tables 7-1, 7-2, 7-4, 7-5/7-7 and 7-10. Returns
        None where no guarantor class is supplied.
        """
        gc = exposure.guarantor_asset_class
        r = exposure.guarantor_rating
        if gc is None:
            return None
        if gc is AssetClass.SOVEREIGN:
            return sovereign_rw(r)
        if gc is AssetClass.PSE:
            return p.PSE_RW[credit_quality_grade(r)]
        if gc is AssetClass.MDB:
            return mdb_rw(r, _flag(exposure, "guarantor_qualifying_mdb"))
        if gc is AssetClass.BANK:
            grade = SCRAGrade.A if _flag(exposure, "guarantor_scra_grade_a") else SCRAGrade.B
            return bank_rw(r, scra_grade=grade)
        if gc in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME):
            return corporate_rw(r, sme=gc is AssetClass.CORPORATE_SME)
        return None

    def collateral_haircut(self, exposure: SAExposure) -> float | None:
        """HC for the exposure's collateral, scaled to the holding period of Table 7J-2.

        Reference: MAS Notice 637 Annex 7J paras 1.5, 2.1, 3.1 and 3.4 (pp. 7-261 to 7-264).
        Default transaction type is secured lending (20 business days, daily revaluation).
        """
        key = exposure.collateral_haircut_class
        if key is None or key not in p.SUPERVISORY_HAIRCUTS:
            return None
        if _flag(exposure, "repo_style"):
            tm = p.MIN_HOLDING_PERIOD_DAYS["REPO_STYLE"]
        elif _flag(exposure, "capital_market"):
            tm = p.MIN_HOLDING_PERIOD_DAYS["CAPITAL_MARKET"]
        else:
            tm = p.MIN_HOLDING_PERIOD_DAYS["SECURED_LENDING"]
        return supervisory_haircut(key, tm)

    def ccf(self, exposure: SAExposure) -> float:
        """CCF for the exposure's off-balance part (Annex 7B Table 7B-1)."""
        if exposure.off_balance_notional == 0.0 and exposure.obs_category is None:
            return 0.0
        return ccf_for(exposure.obs_category, exposure.original_maturity_months)

    def assess(
        self, exposure: SAExposure
    ) -> tuple[float, float, float, float, SGRiskWeightOutcome]:
        """Full SA(CR) assessment: returns (ccf, E*, RWA, effective RW, base outcome).

        Reference: MAS Notice 637 paras 7.2.11 (E for off-balance items), Annex 7J para 1.1
        (E*), paras 7.3.112-7.3.113 (guarantee substitution; protection recognised only where
        the provider's risk weight is lower than the obligor's).
        """
        out = self.base_risk_weight(exposure)
        ccf = self.ccf(exposure)
        e = exposure.on_balance_amount + ccf * exposure.off_balance_notional
        e_star = e
        if exposure.financial_collateral_value > 0.0:
            hc = self.collateral_haircut(exposure)
            if hc is None:
                out.notes.append("collateral not recognised: no Table 7J-1 haircut class supplied")
            else:
                hfx = (
                    p.FX_MISMATCH_HAIRCUT
                    if _flag(exposure, "collateral_currency_mismatch")
                    else 0.0
                )
                if _flag(exposure, "collateral_currency_mismatch"):
                    tm = (
                        p.MIN_HOLDING_PERIOD_DAYS["REPO_STYLE"]
                        if _flag(exposure, "repo_style")
                        else p.MIN_HOLDING_PERIOD_DAYS["CAPITAL_MARKET"]
                        if _flag(exposure, "capital_market")
                        else p.MIN_HOLDING_PERIOD_DAYS["SECURED_LENDING"]
                    )
                    hfx = scale_haircut(p.FX_MISMATCH_HAIRCUT, tm)
                e_star = exposure_after_collateral(
                    e, exposure.financial_collateral_value, 0.0, hc, hfx
                )
                out.notes.append(f"FC(CA): E={e:.4f}, HC={hc:.4f}, HFX={hfx:.4f}, E*={e_star:.4f}")
                out.citation += "; Annex 7J para 1.1"
        rwa = e_star * out.risk_weight
        g_rw = self.guarantor_rw(exposure)
        if exposure.guarantee_amount > 0.0 and g_rw is not None and g_rw < out.risk_weight:
            ga = guarantee_protected_amount(
                exposure.guarantee_amount, _flag(exposure, "guarantee_currency_mismatch")
            )
            protected = min(ga, e_star)
            rwa = protected * g_rw + (e_star - protected) * out.risk_weight
            out.notes.append(f"guarantee substitution: {protected:.4f} at {g_rw:.0%} (7.3.112)")
            out.citation += "; para 7.3.112"
        elif exposure.guarantee_amount > 0.0:
            out.notes.append(
                "guarantee not recognised: provider weight not lower than obligor's (7.3.112)"
            )
        eff = rwa / e_star if e_star > 0 else out.risk_weight
        return ccf, e_star, rwa, eff, out


def _rating_from_grade(grade: int | None) -> RatingBucket:
    """Inverse of :func:`credit_quality_grade`."""
    for bucket, g in p.CQS_BY_RATING.items():
        if g == grade:
            return bucket
    return RatingBucket.UNRATED
