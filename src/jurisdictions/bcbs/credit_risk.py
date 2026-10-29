"""BCBS standardised approach for credit risk (CRE20, CRE21, CRE22).

Assigns Basel Framework risk weights to jurisdiction-neutral
:class:`~src.jurisdictions.base.SAExposure` inputs, applies CRE20 credit
conversion factors and CRE22 credit risk mitigation (comprehensive approach
with supervisory haircuts, the simple approach, and guarantee substitution).

National discretions are switched through :class:`BCBSOptions`; the
defaults are the Framework's base rules.

Exposure ``flags`` read by this module (all optional, default False):

=============================================  =============================================
Flag                                           Provision
=============================================  =============================================
``is_supranational_zero_rw``                   CRE20.10 BIS/IMF/ECB/EU/ESM/EFSF 0%
``is_zero_rw_mdb``                             CRE20.14 eligible MDB 0%
``due_diligence_uplift``                       CRE20.20 / 20.39 / 20.42 one bucket higher
``foreign_currency_exposure``                  CRE20.32 SCRA sovereign floor trigger
``covered_bond_ineligible``                    CRE20.34-20.37 not met -> bank exposure
``issue_specific_rating``                      CRE20.50 SL issue rating available
``exceeds_commercial_materiality_threshold``   CRE20.61-20.62 1250%
``counterparty_is_individual``                 CRE20.89(1) RE counterparty RW (RRE default)
``counterparty_is_corporate``                  CRE20.89(1) RE counterparty RW (CRE default)
``junior_lien``                                CRE20.75 fn 115 x1.25 multiplier
``defaulted_rre_non_cf``                       CRE20.107 (asset class DEFAULTED)
``is_cash`` / ``is_gold_bullion``              CRE20.110(1) 0%
``is_cash_in_collection``                      CRE20.110(2) 20%
``is_threshold_deduction_item``                CRE20.109 250%
``commitment_to_issue_obs_item``               CRE20.101 lower of CCFs (vs 40%)
``commitment_unconditionally_cancellable``     CRE20.101 lower of CCFs (vs 10%)
``collateral_currency_mismatch``               CRE22.52 Hfx = 8%
``guarantee_currency_mismatch``                CRE22.82-22.83 Hfx = 8%
``repo_style`` / ``capital_market_txn``        CRE22.57 minimum holding period 5 / 10 days
``crm_simple_approach``                        CRE22.33 simple approach instead of comprehensive
``guarantor_investment_grade``                 CRE22.76(3) corporate guarantor (no ratings)
``guarantee_domestic_currency_funded``         CRE22.84 domestic-sovereign guarantee RW
=============================================  =============================================

References:
    - Basel Framework CRE20.7-20.110 (pp. 181-217)
    - Basel Framework CRE21.16 (Table 15, p. 223)
    - Basel Framework CRE22.10-22.84 (pp. 226-249)
    - Basel Framework CRE90.1 (equity phase-in, p. 514)
    - BCBS d424 paras 129, 160, 172, 204 (CRM equations)

All monetary amounts in USD millions ($M) unless explicitly stated otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    Jurisdiction,
    OBSCategory,
    PFPhase,
    RatingBucket,
    RealEstateTreatment,
    RiskWeightResult,
    SAExposure,
    SCRAGrade,
)
from src.jurisdictions.bcbs import params as p
from src.jurisdictions.bcbs.params import BCBSOptions

R = RatingBucket

RATING_ORDER: tuple[RatingBucket, ...] = (
    R.AAA_TO_AA_MINUS,
    R.A_PLUS_TO_A_MINUS,
    R.BBB_PLUS_TO_BBB_MINUS,
    R.BB_PLUS_TO_BB_MINUS,
    R.B_PLUS_TO_B_MINUS,
    R.BELOW_B_MINUS,
)


@dataclass
class RWAssignment:
    """Pre-CRM risk weight of the obligor, with its provenance."""

    risk_weight: float
    regime_class: str
    citation: str
    notes: list[str] = field(default_factory=list)


def _flag(exposure: SAExposure, key: str) -> bool:
    """Read a documented boolean flag (module docstring table); defaults to False."""
    return bool(exposure.flags.get(key, False))


def _uplift(table: dict[RatingBucket, float], rating: RatingBucket) -> float:
    """Risk weight one rating bucket higher (CRE20.20, CRE20.39, CRE20.42 due diligence).

    "The bank must assign a risk weight at least one bucket higher than the
    'base' risk weight determined by the external rating."
    """
    idx = RATING_ORDER.index(rating)
    worse = RATING_ORDER[min(idx + 1, len(RATING_ORDER) - 1)]
    return max(table[worse], table[rating])


def band_rw(ltv: float, bands: p.LTVBands) -> float:
    """Look up an LTV-band risk weight; band upper bounds are inclusive.

    CRE20.82 Table 11, CRE20.84 Table 12, CRE20.87 Table 14 ("LTV <= 50%",
    "50% < LTV <= 60%", ...).
    """
    for upper, rw in bands:
        if ltv <= upper:
            return rw
    return bands[-1][1]


# =========================================================================
#  Sovereigns, PSEs, MDBs (CRE20.7-20.15)
# =========================================================================

def sovereign_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """Sovereign and central bank risk weight (CRE20.7 Table 1, CRE20.8-20.10)."""
    if _flag(exposure, "is_supranational_zero_rw"):
        return RWAssignment(p.SUPRANATIONAL_ZERO_RW, "SOVEREIGN_SUPRANATIONAL", "CRE20.10")
    if opts.domestic_sovereign_rw is not None and exposure.domestic_currency_funded:
        return RWAssignment(opts.domestic_sovereign_rw, "SOVEREIGN_DOMESTIC", "CRE20.8",
                            ["National discretion: domestic currency, domestically funded"])
    if opts.use_eca_scores and exposure.oecd_crc is not None:
        return RWAssignment(p.ECA_SCORE_RW[exposure.oecd_crc], "SOVEREIGN",
                            "CRE20.9 Table 2", [f"ECA risk score {exposure.oecd_crc}"])
    return RWAssignment(p.SOVEREIGN_RW[exposure.rating], "SOVEREIGN", "CRE20.7 Table 1")


def pse_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """Domestic PSE risk weight (CRE20.11 Tables 3/4, CRE20.12 sovereign treatment)."""
    if opts.pse_treated_as_sovereign:
        rw = p.SOVEREIGN_RW[exposure.sovereign_rating]
        return RWAssignment(rw, "PSE_AS_SOVEREIGN", "CRE20.12 / CRE20.7 Table 1")
    if opts.pse_option == 2:
        return RWAssignment(p.PSE_OPTION2_RW[exposure.rating], "PSE", "CRE20.11 Table 4")
    return RWAssignment(p.PSE_OPTION1_RW[exposure.sovereign_rating], "PSE", "CRE20.11 Table 3")


def mdb_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """MDB risk weight (CRE20.14 0% eligible MDBs, CRE20.15 Table 5 / 50%)."""
    if _flag(exposure, "is_zero_rw_mdb"):
        return RWAssignment(p.MDB_ELIGIBLE_ZERO_RW, "MDB_ZERO", "CRE20.14")
    if opts.external_ratings_allowed:
        return RWAssignment(p.MDB_RW[exposure.rating], "MDB", "CRE20.15 Table 5")
    return RWAssignment(p.MDB_NO_RATINGS_RW, "MDB", "CRE20.15")


# =========================================================================
#  Banks (CRE20.16-20.32, CRE21.16)
# =========================================================================

def is_short_term_bank_exposure(exposure: SAExposure) -> bool:
    """CRE20.19 / CRE20.31: original maturity <= 3 months, or trade-related <= 6 months."""
    m = exposure.original_maturity_months
    if m is None:
        return False
    if m <= p.BANK_SHORT_TERM_MAX_ORIGINAL_MATURITY_MONTHS:
        return True
    return exposure.is_trade_related and m <= p.BANK_TRADE_SHORT_TERM_MAX_ORIGINAL_MATURITY_MONTHS


def bank_rw(exposure: SAExposure, opts: BCBSOptions, *, issuer_basis: bool = False) -> RWAssignment:
    """Bank risk weight under ECRA (CRE20.18-20.20) or SCRA (CRE20.21-20.32).

    ``issuer_basis`` returns the issuing bank's "base" risk weight (no
    short-term or Table 15 treatment), as required for CRE20.38 Table 9.
    """
    short = is_short_term_bank_exposure(exposure) and not issuer_basis
    if (opts.external_ratings_allowed and not issuer_basis
            and exposure.short_term_rating is not None):
        return RWAssignment(p.SHORT_TERM_RATING_RW[exposure.short_term_rating],
                            "BANK_SHORT_TERM_RATED", "CRE21.16 Table 15")
    if opts.external_ratings_allowed and exposure.rating is not R.UNRATED:
        table = p.BANK_ECRA_SHORT_TERM_RW if short else p.BANK_ECRA_BASE_RW
        cite = "CRE20.18 Table 6 / CRE20.19 (short-term)" if short else "CRE20.18 Table 6"
        notes: list[str] = []
        if _flag(exposure, "due_diligence_uplift"):
            rw = _uplift(table, exposure.rating)
            notes.append("CRE20.20 due-diligence uplift one bucket")
        else:
            rw = table[exposure.rating]
        return RWAssignment(rw, "BANK_ECRA", cite, notes)

    # SCRA: all bank exposures where ratings are not allowed; unrated exposures otherwise
    notes = []
    grade = exposure.scra_grade
    if grade is None:
        grade = SCRAGrade.B
        notes.append("No SCRA grade supplied: CRE20.27 residual Grade B")
    if short:
        rw = p.BANK_SCRA_SHORT_TERM_RW[grade]
        cite = "CRE20.21 Table 7 / CRE20.31 (short-term)"
    elif grade is SCRAGrade.A and exposure.scra_grade_a_enhanced:
        rw = p.BANK_SCRA_GRADE_A_ENHANCED_RW
        cite = "CRE20.21 footnote 98 (CET1 >= 14%, leverage >= 5%)"
    else:
        rw = p.BANK_SCRA_BASE_RW[grade]
        cite = "CRE20.21 Table 7"
    if _flag(exposure, "foreign_currency_exposure"):
        trade_exempt = (exposure.is_trade_related
                        and exposure.original_maturity_months is not None
                        and exposure.original_maturity_months
                        < p.SCRA_SOVEREIGN_FLOOR_TRADE_EXEMPT_MAX_MONTHS)
        if not trade_exempt:
            floor = p.SOVEREIGN_RW[exposure.sovereign_rating]
            if floor > rw:
                notes.append(f"CRE20.32 sovereign floor {floor:.0%} applied")
                rw = floor
    return RWAssignment(rw, f"BANK_SCRA_{grade.value}", cite, notes)


def covered_bond_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """Covered bond risk weight (CRE20.38 Tables 8 and 9, CRE20.39).

    Rated (issue-specific) covered bonds use Table 8; unrated covered bonds
    use Table 9 on the issuing bank's ECRA/SCRA risk weight (``rating`` is
    read as the issuer rating when ``covered_bond_rated`` is False).
    Covered bonds failing CRE20.34-20.37 are treated as bank exposures.
    """
    if _flag(exposure, "covered_bond_ineligible"):
        a = bank_rw(exposure, opts)
        a.notes.append("CRE20.34-20.37 criteria not met: treated as bank exposure")
        return a
    if (opts.external_ratings_allowed and exposure.covered_bond_rated
            and exposure.rating is not R.UNRATED):
        if _flag(exposure, "due_diligence_uplift"):
            rw = _uplift(p.COVERED_BOND_RATED_RW, exposure.rating)
            return RWAssignment(rw, "COVERED_BOND_RATED", "CRE20.38 Table 8 / CRE20.39",
                                ["CRE20.39 due-diligence uplift one bucket"])
        return RWAssignment(p.COVERED_BOND_RATED_RW[exposure.rating], "COVERED_BOND_RATED",
                            "CRE20.38 Table 8")
    issuer = bank_rw(exposure, opts, issuer_basis=True)
    keys = sorted(p.COVERED_BOND_UNRATED_RW)
    key = next((k for k in keys if issuer.risk_weight <= k + 1e-12), keys[-1])
    return RWAssignment(p.COVERED_BOND_UNRATED_RW[key], "COVERED_BOND_UNRATED",
                        "CRE20.38 Table 9",
                        [f"Issuing bank RW {issuer.risk_weight:.0%} ({issuer.citation})",
                         *issuer.notes])


# =========================================================================
#  Corporates and specialised lending (CRE20.41-20.52)
# =========================================================================

def is_sme(exposure: SAExposure) -> bool:
    """CRE20.47: consolidated group annual sales <= EUR 50m (``annual_turnover`` in EUR m)."""
    if exposure.asset_class is AssetClass.CORPORATE_SME or exposure.is_sme:
        return True
    return (exposure.annual_turnover is not None
            and exposure.annual_turnover <= p.SME_TURNOVER_THRESHOLD_EUR_M)


def corporate_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """General corporate risk weight (CRE20.42-20.47, CRE21.16 Table 15)."""
    sme = is_sme(exposure)
    if opts.external_ratings_allowed:
        if exposure.short_term_rating is not None:
            return RWAssignment(p.SHORT_TERM_RATING_RW[exposure.short_term_rating],
                                "CORPORATE_SHORT_TERM_RATED", "CRE21.16 Table 15")
        if exposure.rating is not R.UNRATED:
            if _flag(exposure, "due_diligence_uplift"):
                return RWAssignment(_uplift(p.CORPORATE_RW, exposure.rating), "CORPORATE",
                                    "CRE20.42 Table 10",
                                    ["CRE20.42 due-diligence uplift one bucket"])
            return RWAssignment(p.CORPORATE_RW[exposure.rating], "CORPORATE", "CRE20.42 Table 10")
        if sme:
            return RWAssignment(p.CORPORATE_SME_RW, "CORPORATE_SME", "CRE20.47")
        return RWAssignment(p.CORPORATE_RW[R.UNRATED], "CORPORATE", "CRE20.43 Table 10 (unrated)")
    if sme:
        return RWAssignment(p.CORPORATE_SME_RW, "CORPORATE_SME", "CRE20.47")
    if opts.investment_grade_corporate_65 and exposure.is_investment_grade:
        return RWAssignment(p.CORPORATE_INVESTMENT_GRADE_RW, "CORPORATE_IG", "CRE20.46")
    return RWAssignment(p.CORPORATE_NO_RATINGS_RW, "CORPORATE", "CRE20.44")


def specialised_lending_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """Specialised lending risk weight (CRE20.48-20.52).

    Issue-specific ratings (flag ``issue_specific_rating``) use Table 10
    (CRE20.50; issuer ratings must not be used). Otherwise OF/CF 100% and
    PF 130% / 100% / 80% by phase (CRE20.51-20.52).
    """
    cls = exposure.asset_class.value
    if (opts.external_ratings_allowed and _flag(exposure, "issue_specific_rating")
            and exposure.rating is not R.UNRATED):
        return RWAssignment(p.CORPORATE_RW[exposure.rating], cls, "CRE20.50 / CRE20.42 Table 10")
    if exposure.asset_class is AssetClass.SPECIALISED_LENDING_PF:
        notes: list[str] = []
        phase = exposure.pf_phase
        if phase is None:
            phase = PFPhase.PRE_OPERATIONAL
            notes.append("No project phase supplied: pre-operational (conservative)")
        return RWAssignment(p.SL_PROJECT_FINANCE_RW[phase], f"{cls}_{phase.value}",
                            "CRE20.51(2) / CRE20.52", notes)
    return RWAssignment(p.SL_OBJECT_COMMODITY_RW, cls, "CRE20.51(1)")


# =========================================================================
#  Subordinated debt and equity (CRE20.53-20.62, CRE20.109, CRE90.1)
# =========================================================================

def equity_phase_in_rw(final_rw: float, step: float, year: int) -> float:
    """CRE90.1 five-year linear phase-in from 1 January 2023.

    "The applicable risk weight will start at 100% and increase by 60 [30]
    percentage points at the end of each year until the end of Year 5."
    Year 1 = 2023 (100%); the fully phased-in weight applies from 2028.
    """
    years_completed = max(0, min(year - p.EQUITY_PHASE_IN_START_YEAR, p.EQUITY_PHASE_IN_YEARS))
    return min(final_rw, p.EQUITY_PHASE_IN_START_RW + step * years_completed)


def equity_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """Equity risk weight (CRE20.57-20.62, CRE20.109, CRE90.1 transition)."""
    if _flag(exposure, "exceeds_commercial_materiality_threshold"):
        return RWAssignment(p.COMMERCIAL_ENTITY_EXCESS_RW, "EQUITY_COMMERCIAL_EXCESS", "CRE20.62")
    et = exposure.equity_type or EquityType.GENERAL
    notes: list[str] = []
    if et is EquityType.SIGNIFICANT_FI:
        return RWAssignment(p.THRESHOLD_DEDUCTION_ITEM_RW, "EQUITY_THRESHOLD_ITEM", "CRE20.109")
    if et is EquityType.LEGISLATIVE_PROGRAMME:
        if opts.legislative_programme_equity_100:
            return RWAssignment(p.EQUITY_LEGISLATIVE_PROGRAMME_RW, "EQUITY_LEGISLATIVE",
                                "CRE20.59",
                                ["Aggregate cap 10% of Total capital applies (CRE20.59)"])
        notes.append("CRE20.59 discretion not exercised: general equity")
        et = EquityType.GENERAL
    if et in (EquityType.PUBLICLY_TRADED, EquityType.NON_PUBLIC):
        notes.append(f"{et.value} is not a Basel bucket: general equity (CRE20.57)")
        et = EquityType.GENERAL
    if et is EquityType.SPECULATIVE_UNLISTED:
        final, step = p.EQUITY_SPECULATIVE_UNLISTED_RW, p.EQUITY_PHASE_IN_STEP_SPECULATIVE
        cls, cite = "EQUITY_SPECULATIVE", "CRE20.57-20.58"
    else:
        final, step, cls, cite = (p.EQUITY_GENERAL_RW, p.EQUITY_PHASE_IN_STEP_GENERAL,
                                  "EQUITY_GENERAL", "CRE20.57")
    if opts.equity_transition_year is not None:
        rw = equity_phase_in_rw(final, step, opts.equity_transition_year)
        if rw < final:
            notes.append(f"CRE90.1 phase-in {opts.equity_transition_year}: {rw:.0%}")
            cite = f"{cite} / CRE90.1"
        return RWAssignment(rw, cls, cite, notes)
    return RWAssignment(final, cls, cite, notes)


# =========================================================================
#  Retail (CRE20.63-20.68) and currency mismatch (CRE20.92-20.93)
# =========================================================================

def retail_rw(exposure: SAExposure) -> RWAssignment:
    """Retail risk weight (CRE20.65-20.68): 75% regulatory, 45% transactor, 100% other.

    ``aggregate_retail_exposure_to_obligor`` is read in EUR millions against
    the CRE20.65(2) EUR 1 million threshold.
    """
    agg = exposure.aggregate_retail_exposure_to_obligor
    regulatory = exposure.meets_regulatory_retail_criteria and (
        agg is None or agg <= p.RETAIL_MAX_AGGREGATE_EXPOSURE_EUR_M)
    if exposure.asset_class is AssetClass.RETAIL_OTHER or not regulatory:
        notes = [] if exposure.asset_class is AssetClass.RETAIL_OTHER else [
            "CRE20.65 regulatory retail criteria not met"]
        return RWAssignment(p.RETAIL_OTHER_RW, "RETAIL_OTHER", "CRE20.67 / CRE20.68(3)", notes)
    if exposure.asset_class is AssetClass.RETAIL_TRANSACTOR or exposure.is_transactor:
        return RWAssignment(p.RETAIL_TRANSACTOR_RW, "RETAIL_TRANSACTOR", "CRE20.66 / CRE20.68(2)")
    return RWAssignment(p.RETAIL_REGULATORY_RW, "RETAIL_REGULATORY", "CRE20.65 / CRE20.68(1)")


def apply_currency_mismatch(rw: float) -> float:
    """CRE20.92: 1.5x multiplier for unhedged retail/RRE to individuals, max RW 150%."""
    return min(rw * p.CURRENCY_MISMATCH_MULTIPLIER, p.CURRENCY_MISMATCH_RW_CAP)


# =========================================================================
#  Real estate (CRE20.69-20.91)
# =========================================================================

def re_counterparty_is_individual(exposure: SAExposure, *, default_individual: bool) -> bool:
    """Whether the RE counterparty is an individual (CRE20.89(1), CRE20.92 scope).

    Flag ``counterparty_is_individual`` decides when present; otherwise RRE
    defaults to an individual and CRE to a corporate, unless
    ``counterparty_is_corporate`` is set or the borrower is an SME.
    """
    if is_sme(exposure):
        return False
    individual = exposure.flags.get("counterparty_is_individual")
    if individual is not None:
        return bool(individual)
    return default_individual and not _flag(exposure, "counterparty_is_corporate")


def re_counterparty_rw(exposure: SAExposure, opts: BCBSOptions, *,
                       default_individual: bool) -> float:
    """Risk weight of the counterparty for real estate (CRE20.89(1)).

    Individuals 75%, SMEs 85%, other counterparties the unsecured RW
    (taken as the corporate risk weight, CRE20.42-20.46).
    """
    if is_sme(exposure):
        return p.OTHER_RE_SME_RW
    if re_counterparty_is_individual(exposure, default_individual=default_individual):
        return p.OTHER_RE_INDIVIDUAL_RW
    return corporate_rw(exposure.model_copy(update={"asset_class": AssetClass.CORPORATE}),
                        opts).risk_weight


def _loan_split_secured_share(exposure: SAExposure, exposure_amount: float) -> float | None:
    """Share of the exposure up to 55% of the property value (CRE20.83 / CRE20.86).

    Uses ``property_value`` or, failing that, (on + off notional) / LTV.
    Returns None where neither is available. Liens not held by the bank are
    not represented in :class:`SAExposure` and are not deducted.
    """
    value = exposure.property_value
    if value is None and exposure.ltv:
        value = (exposure.on_balance_amount + exposure.off_balance_notional) / exposure.ltv
    if value is None or exposure_amount <= 0:
        return None
    secured = min(exposure_amount, p.LOAN_SPLIT_PROPERTY_SHARE * value)
    return secured / exposure_amount


def residential_re_rw(exposure: SAExposure, opts: BCBSOptions,
                      exposure_amount: float) -> RWAssignment:
    """Residential real estate risk weight (CRE20.71-20.84, CRE20.88-20.89, CRE20.92)."""
    notes: list[str] = []
    cp_rw = re_counterparty_rw(exposure, opts, default_individual=True)
    to_individual = re_counterparty_is_individual(exposure, default_individual=True)
    if not exposure.is_regulatory_real_estate:
        if exposure.is_cash_flow_dependent:
            return RWAssignment(p.OTHER_RE_CASH_FLOW_RW, "RRE_OTHER_CF", "CRE20.89(2)")
        return RWAssignment(cp_rw, "RRE_OTHER", "CRE20.89(1)")
    ltv = exposure.ltv
    if ltv is None:
        ltv = p.INF
        notes.append("No LTV supplied: highest LTV band (conservative)")
    if exposure.is_cash_flow_dependent:
        rw = band_rw(ltv, p.RRE_CASH_FLOW_RW)
        cls, cite = "RRE_REGULATORY_CF", "CRE20.84 Table 12"
    elif opts.residential_re_treatment is RealEstateTreatment.LOAN_SPLITTING:
        share = _loan_split_secured_share(exposure, exposure_amount)
        if share is None:
            rw = band_rw(ltv, p.RRE_WHOLE_LOAN_RW)
            cls, cite = "RRE_REGULATORY", "CRE20.82 Table 11"
            notes.append("Loan splitting needs a property value: whole loan applied")
        else:
            rw = share * p.RRE_LOAN_SPLIT_RW + (1.0 - share) * cp_rw
            cls, cite = "RRE_REGULATORY_SPLIT", "CRE20.83"
            notes.append(f"Loan splitting: {share:.1%} at 20%, remainder at {cp_rw:.0%}")
    else:
        rw = band_rw(ltv, p.RRE_WHOLE_LOAN_RW)
        cls, cite = "RRE_REGULATORY", "CRE20.82 Table 11"
    if (_flag(exposure, "junior_lien") and cls != "RRE_REGULATORY_SPLIT"
            and ltv > p.RRE_WHOLE_LOAN_RW[0][0]):
        table = p.RRE_CASH_FLOW_RW if exposure.is_cash_flow_dependent else p.RRE_WHOLE_LOAN_RW
        cap = p.OTHER_RE_CASH_FLOW_RW if exposure.is_cash_flow_dependent else cp_rw
        rw = min(band_rw(ltv, table) * p.JUNIOR_LIEN_MULTIPLIER, cap)
        notes.append("CRE20.75 fn 115 junior-lien multiplier 1.25 (capped)")
    if to_individual and not exposure.currency_matches_borrower_income:
        rw = apply_currency_mismatch(rw)
        notes.append("CRE20.92 currency-mismatch multiplier 1.5x (max 150%)")
    return RWAssignment(rw, cls, cite, notes)


def commercial_re_rw(exposure: SAExposure, opts: BCBSOptions,
                     exposure_amount: float) -> RWAssignment:
    """Commercial real estate risk weight (CRE20.78, CRE20.85-20.89)."""
    notes: list[str] = []
    cp_rw = re_counterparty_rw(exposure, opts, default_individual=False)
    if not exposure.is_regulatory_real_estate:
        if exposure.is_cash_flow_dependent:
            return RWAssignment(p.OTHER_RE_CASH_FLOW_RW, "CRE_OTHER_CF", "CRE20.89(2)")
        return RWAssignment(cp_rw, "CRE_OTHER", "CRE20.89(1)")
    cf = exposure.is_cash_flow_dependent
    if cf and opts.cre_cash_flow_exemption:
        cf = False
        notes.append("CRE20.87 fn 122 exemption: non-CF treatment")
    if cf:
        ltv = exposure.ltv if exposure.ltv is not None else p.INF
        if exposure.ltv is None:
            notes.append("No LTV supplied: highest LTV band (conservative)")
        return RWAssignment(band_rw(ltv, p.CRE_CASH_FLOW_RW), "CRE_REGULATORY_CF",
                            "CRE20.87 Table 14", notes)
    capped = min(p.CRE_WHOLE_LOAN_CAP_RW, cp_rw)
    if opts.commercial_re_treatment is RealEstateTreatment.LOAN_SPLITTING:
        share = _loan_split_secured_share(exposure, exposure_amount)
        if share is not None:
            rw = share * capped + (1.0 - share) * cp_rw
            notes.append(f"Loan splitting: {share:.1%} at {capped:.0%}, remainder at {cp_rw:.0%}")
            return RWAssignment(rw, "CRE_REGULATORY_SPLIT", "CRE20.86", notes)
        notes.append("Loan splitting needs a property value: whole loan applied")
    if exposure.ltv is not None and exposure.ltv <= p.CRE_WHOLE_LOAN_LTV_THRESHOLD:
        return RWAssignment(capped, "CRE_REGULATORY", "CRE20.85 Table 13 (LTV <= 60%)", notes)
    return RWAssignment(cp_rw, "CRE_REGULATORY", "CRE20.85 Table 13 (LTV > 60%)", notes)


def land_adc_rw(exposure: SAExposure) -> RWAssignment:
    """Land ADC risk weight (CRE20.90 150%; CRE20.91 residential ADC 100%)."""
    if exposure.is_adc_presold_or_equity_at_risk:
        return RWAssignment(p.LAND_ADC_RESIDENTIAL_QUALIFYING_RW, "LAND_ADC_RESIDENTIAL",
                            "CRE20.91")
    return RWAssignment(p.LAND_ADC_RW, "LAND_ADC", "CRE20.90")


# =========================================================================
#  Defaulted and other assets (CRE20.104-20.110)
# =========================================================================

def defaulted_rw(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment:
    """Defaulted exposure risk weight (CRE20.106-20.107, footnote 129)."""
    rre_non_cf = (
        (exposure.asset_class is AssetClass.RESIDENTIAL_RE and not exposure.is_cash_flow_dependent)
        or _flag(exposure, "defaulted_rre_non_cf"))
    if rre_non_cf:
        return RWAssignment(p.DEFAULTED_RRE_RW, "DEFAULTED_RRE", "CRE20.107")
    prov = exposure.specific_provision_pct
    if opts.defaulted_50pct_discretion and prov >= p.DEFAULTED_DISCRETION_PROVISION_THRESHOLD:
        return RWAssignment(p.DEFAULTED_DISCRETION_RW, "DEFAULTED", "CRE20.106 footnote 129")
    if prov >= p.DEFAULTED_PROVISION_THRESHOLD:
        return RWAssignment(p.DEFAULTED_HIGH_PROVISION_RW, "DEFAULTED", "CRE20.106(2)")
    return RWAssignment(p.DEFAULTED_LOW_PROVISION_RW, "DEFAULTED", "CRE20.106(1)")


def other_assets_rw(exposure: SAExposure) -> RWAssignment:
    """Other assets risk weight (CRE20.109-20.110)."""
    if _flag(exposure, "is_cash"):
        return RWAssignment(p.CASH_RW, "OTHER_CASH", "CRE20.110(1)(a)")
    if _flag(exposure, "is_gold_bullion"):
        return RWAssignment(p.GOLD_BULLION_RW, "OTHER_GOLD", "CRE20.110(1)(b)")
    if _flag(exposure, "is_cash_in_collection"):
        return RWAssignment(p.CASH_ITEMS_IN_COLLECTION_RW, "OTHER_CASH_COLLECTION", "CRE20.110(2)")
    if _flag(exposure, "is_threshold_deduction_item"):
        return RWAssignment(p.THRESHOLD_DEDUCTION_ITEM_RW, "OTHER_THRESHOLD_ITEM", "CRE20.109")
    return RWAssignment(p.OTHER_ASSETS_RW, "OTHER_ASSETS", "CRE20.110")


# =========================================================================
#  Dispatcher
# =========================================================================

def obligor_risk_weight(exposure: SAExposure, opts: BCBSOptions,
                        exposure_amount: float | None = None) -> RWAssignment:
    """Pre-CRM risk weight for any :class:`AssetClass` (CRE20.7-20.110).

    ``exposure_amount`` (post-CCF) is used only by the loan-splitting
    approaches (CRE20.83 / CRE20.86).
    """
    if exposure_amount is None:
        exposure_amount = exposure.on_balance_amount + exposure.off_balance_notional
    ac = exposure.asset_class
    if exposure.is_defaulted or ac is AssetClass.DEFAULTED:
        return defaulted_rw(exposure, opts)
    if ac is AssetClass.SOVEREIGN:
        return sovereign_rw(exposure, opts)
    if ac is AssetClass.PSE:
        return pse_rw(exposure, opts)
    if ac is AssetClass.MDB:
        return mdb_rw(exposure, opts)
    if ac is AssetClass.BANK:
        return bank_rw(exposure, opts)
    if ac is AssetClass.COVERED_BOND:
        return covered_bond_rw(exposure, opts)
    if ac in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME):
        return corporate_rw(exposure, opts)
    if ac in (AssetClass.SPECIALISED_LENDING_PF, AssetClass.SPECIALISED_LENDING_OF,
              AssetClass.SPECIALISED_LENDING_CF):
        return specialised_lending_rw(exposure, opts)
    if ac is AssetClass.SUBORDINATED_DEBT:
        return RWAssignment(p.SUBORDINATED_DEBT_RW, "SUBORDINATED_DEBT", "CRE20.60")
    if ac is AssetClass.EQUITY:
        return equity_rw(exposure, opts)
    if ac in (AssetClass.RETAIL_REGULATORY, AssetClass.RETAIL_TRANSACTOR,
              AssetClass.RETAIL_OTHER):
        a = retail_rw(exposure)
        if not exposure.currency_matches_borrower_income and not is_sme(exposure):
            a.risk_weight = apply_currency_mismatch(a.risk_weight)
            a.notes.append("CRE20.92 currency-mismatch multiplier 1.5x (max 150%)")
        return a
    if ac is AssetClass.RESIDENTIAL_RE:
        return residential_re_rw(exposure, opts, exposure_amount)
    if ac is AssetClass.COMMERCIAL_RE:
        return commercial_re_rw(exposure, opts, exposure_amount)
    if ac is AssetClass.LAND_ADC:
        return land_adc_rw(exposure)
    return other_assets_rw(exposure)


# =========================================================================
#  Credit conversion factors (CRE20.94-20.101)
# =========================================================================

def ccf(exposure: SAExposure) -> float:
    """Credit conversion factor for the off-balance notional (CRE20.94-20.101)."""
    cat = exposure.obs_category
    if cat is None:
        return p.CCF_UNCLASSIFIED_DEFAULT if exposure.off_balance_notional > 0 else 0.0
    value = p.CCF[cat]
    if (cat is OBSCategory.SHORT_TERM_TRADE_LC and exposure.original_maturity_months is not None
            and exposure.original_maturity_months >= p.SHORT_TERM_TRADE_LC_MAX_MONTHS):
        value = p.SHORT_TERM_TRADE_LC_LONG_DATED_CCF
    if _flag(exposure, "commitment_unconditionally_cancellable"):
        value = min(value, p.CCF[OBSCategory.UNCONDITIONALLY_CANCELLABLE])
    elif _flag(exposure, "commitment_to_issue_obs_item"):
        value = min(value, p.CCF[OBSCategory.COMMITMENT_OTHER])
    return value


# =========================================================================
#  Credit risk mitigation (CRE22)
# =========================================================================

def haircut_table(opts: BCBSOptions) -> dict[str, float]:
    """CRE22.49 (ratings jurisdictions) or CRE22.50 (no ratings) supervisory haircuts."""
    return p.HAIRCUTS_RATINGS if opts.external_ratings_allowed else p.HAIRCUTS_NO_RATINGS


def scale_haircut(h10: float, holding_period_days: int, remargin_days: int = 1) -> float:
    """CRE22.59 / d424 para 172: H = H10 x sqrt((NR + (TM - 1)) / 10)."""
    return h10 * math.sqrt((remargin_days + holding_period_days - 1)
                           / p.HAIRCUT_BASE_HOLDING_PERIOD_DAYS)


def basket_haircut(weights_and_haircuts: list[tuple[float, float]]) -> float:
    """CRE22.55 / d424 para 168: H = sum_i a_i H_i (a_i currency weights)."""
    return sum(a * h for a, h in weights_and_haircuts)


def comprehensive_exposure(e: float, c: float, he: float, hc: float, hfx: float) -> float:
    """CRE22.46 / d424 para 160: E* = max{0, E(1 + He) - C(1 - Hc - Hfx)}."""
    return max(0.0, e * (1.0 + he) - c * (1.0 - hc - hfx))


def maturity_mismatch_adjust(protection: float, protection_residual_years: float,
                             exposure_residual_years: float,
                             protection_original_years: float | None = None) -> float:
    """CRE22.12-22.13 / d424 para 129: Pa = P x (t - 0.25) / (T - 0.25).

    t = min(T, residual maturity of protection); T = min(5, residual maturity
    of exposure). Protection is not recognised where its original maturity
    is below one year or its residual maturity below three months (CRE22.12).
    """
    if protection_residual_years < p.MATURITY_MISMATCH_MIN_RESIDUAL_YEARS:
        return 0.0
    big_t = min(p.MATURITY_MISMATCH_T_CAP_YEARS, exposure_residual_years)
    t = min(big_t, protection_residual_years)
    if t >= big_t:
        return protection
    if (protection_original_years is not None
            and protection_original_years < p.MATURITY_MISMATCH_MIN_ORIGINAL_YEARS):
        return 0.0
    return protection * (t - p.MATURITY_MISMATCH_OFFSET_YEARS) / (
        big_t - p.MATURITY_MISMATCH_OFFSET_YEARS)


def guarantee_after_fx(g: float, hfx: float = p.HAIRCUT_FX) -> float:
    """CRE22.82 / d424 para 204: GA = G x (1 - HFX)."""
    return g * (1.0 - hfx)


def cds_without_restructuring(hedge: float, underlying: float) -> float:
    """CRE22.75: 60% of the hedge, capped at 60% of the underlying obligation."""
    return p.CDS_NO_RESTRUCTURING_RECOGNITION * min(hedge, underlying)


def simple_approach_rwa(exposure_amount: float, collateral_value: float,
                        collateral_rw: float, counterparty_rw: float,
                        floor_exempt: bool = False) -> float:
    """CRE22.33: collateralised portion at the collateral RW (floor 20%), remainder at
    the counterparty RW. ``floor_exempt`` covers CRE22.36-22.39."""
    covered = min(exposure_amount, collateral_value)
    rw_c = collateral_rw if floor_exempt else max(collateral_rw, p.SIMPLE_APPROACH_RW_FLOOR)
    return covered * rw_c + (exposure_amount - covered) * counterparty_rw


def simple_approach_collateral_rw(key: str) -> tuple[float, bool] | None:
    """Collateral-instrument RW for the simple approach, keyed like the haircut table.

    Returns (risk weight, CRE22.39 zero-floor eligible) or None where the key
    is not eligible under CRE22.34. Where a haircut band spans several CRE20
    risk-weight buckets the highest RW in the band is used (conservative):
    sovereign A+..BBB- -> 50% (Table 1), other issuers AAA..AA- -> 20% and
    A+..BBB- -> 75% (Table 10), main-index equity -> 250% (CRE20.57).
    """
    if key == "CASH":
        return (0.0, True)                                       # CRE22.39(1)
    if key == "GOLD":
        return (p.GOLD_BULLION_RW, False)                        # CRE20.110(1)(b)
    if key.startswith("SOV_AAA_AA") or key.startswith("NR_SOV0"):
        return (p.SOVEREIGN_RW[R.AAA_TO_AA_MINUS], True)         # CRE22.39(2)
    if key.startswith("SOV_A_BBB") or key.startswith("NR_SOV20_50"):
        return (p.SOVEREIGN_RW[R.BBB_PLUS_TO_BBB_MINUS], False)
    if key.startswith("SOV_BB") or key.startswith("NR_SOV100"):
        return (p.SOVEREIGN_RW[R.BB_PLUS_TO_BB_MINUS], False)
    if key.startswith("OTHER_AAA_AA"):
        return (p.CORPORATE_RW[R.AAA_TO_AA_MINUS], False)
    if key.startswith("OTHER_A_BBB") or key.startswith("NR_IG"):
        return (p.CORPORATE_RW[R.BBB_PLUS_TO_BBB_MINUS], False)
    if key == "MAIN_INDEX_EQUITY":
        return (p.EQUITY_GENERAL_RW, False)
    return None


_ELIGIBLE_GUARANTORS = frozenset({AssetClass.SOVEREIGN, AssetClass.PSE, AssetClass.MDB,
                                  AssetClass.BANK})


def guarantor_risk_weight(exposure: SAExposure, opts: BCBSOptions) -> RWAssignment | None:
    """Risk weight of an eligible guarantor (CRE22.70, CRE22.76, CRE22.84), or None."""
    g_class = exposure.guarantor_asset_class
    if g_class is None:
        return None
    if g_class is AssetClass.SOVEREIGN and opts.domestic_sovereign_rw is not None and _flag(
            exposure, "guarantee_domestic_currency_funded"):
        return RWAssignment(opts.domestic_sovereign_rw, "GUARANTOR_SOVEREIGN_DOMESTIC", "CRE22.84")
    corporate = g_class in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME)
    if g_class not in _ELIGIBLE_GUARANTORS:
        if not corporate:
            return None
        if opts.external_ratings_allowed and exposure.guarantor_rating is R.UNRATED:
            return None      # CRE22.76(2)(a): other entities must be externally rated
        if not opts.external_ratings_allowed and not _flag(exposure, "guarantor_investment_grade"):
            return None      # CRE22.76(3)(a): investment-grade entities
    synthetic = SAExposure(
        exposure_id=f"{exposure.exposure_id}#guarantor",
        asset_class=g_class,
        rating=exposure.guarantor_rating,
        sovereign_rating=exposure.guarantor_rating,
        is_investment_grade=_flag(exposure, "guarantor_investment_grade"),
    )
    a = obligor_risk_weight(synthetic, opts)
    a.citation = f"CRE22.70 / CRE22.76 ({a.citation})"
    return a


def risk_weight_exposure(exposure: SAExposure, opts: BCBSOptions) -> RiskWeightResult:
    """Full CRE20-CRE22 treatment of one exposure: CCF, obligor RW, collateral, guarantee.

    Exposure amount = on-balance + CCF x off-balance (CRE20.94). Financial
    collateral uses the comprehensive approach (CRE22.40-22.59; He = 0 for a
    loan, H scaled from 10 days to the CRE22.57 minimum holding period with
    daily revaluation) or, with flag ``crm_simple_approach``, the simple
    approach (CRE22.33-22.39). Guarantees substitute the guarantor RW for the
    covered portion where lower (CRE22.70, CRE22.79-22.80). ``risk_weight``
    in the result is the effective RW = RWA / exposure_amount.
    """
    conv = ccf(exposure) if (exposure.off_balance_notional > 0
                             or exposure.obs_category is not None) else 0.0
    gross = exposure.on_balance_amount + conv * exposure.off_balance_notional
    obligor = obligor_risk_weight(exposure, opts, gross)
    notes = list(obligor.notes)
    citation = obligor.citation
    e_star = gross
    rwa_collateral_simple: float | None = None

    if exposure.financial_collateral_value > 0 and exposure.collateral_haircut_class:
        key = exposure.collateral_haircut_class
        if _flag(exposure, "crm_simple_approach"):
            info = simple_approach_collateral_rw(key)
            if info is None:
                notes.append(f"Collateral '{key}' not eligible under CRE22.34: not recognised")
            else:
                c_rw, zero_ok = info
                c_val = exposure.financial_collateral_value
                exempt = zero_ok and not _flag(exposure, "collateral_currency_mismatch")
                if exempt and key != "CASH":
                    c_val *= 1.0 - p.SIMPLE_APPROACH_SOVEREIGN_DISCOUNT     # CRE22.39(2)
                rwa_collateral_simple = simple_approach_rwa(gross, c_val, c_rw,
                                                            obligor.risk_weight, exempt)
                citation += " / CRE22.33 simple approach"
        else:
            table = haircut_table(opts)
            if key not in table:
                notes.append(f"Collateral '{key}' not eligible (CRE22.45/22.49-22.50): "
                             "not recognised")
            else:
                if _flag(exposure, "repo_style"):
                    tm = p.MIN_HOLDING_PERIOD_DAYS["REPO_STYLE"]
                elif _flag(exposure, "capital_market_txn"):
                    tm = p.MIN_HOLDING_PERIOD_DAYS["OTHER_CAPITAL_MARKET"]
                else:
                    tm = p.MIN_HOLDING_PERIOD_DAYS["SECURED_LENDING"]
                hc = scale_haircut(table[key], tm)
                hfx = scale_haircut(p.HAIRCUT_FX, tm) if _flag(
                    exposure, "collateral_currency_mismatch") else 0.0
                e_star = comprehensive_exposure(gross, exposure.financial_collateral_value,
                                                0.0, hc, hfx)
                notes.append(f"CRE22.46 E* = {e_star:.4f} (Hc {hc:.4f}, Hfx {hfx:.4f}, TM {tm}d)")
                citation += " / CRE22.46"

    if rwa_collateral_simple is not None:
        rwa = rwa_collateral_simple
        e_star = gross
    else:
        rwa = e_star * obligor.risk_weight

    if exposure.guarantee_amount > 0:
        g = guarantor_risk_weight(exposure, opts)
        if g is None:
            notes.append("Guarantor not eligible under CRE22.76: not recognised")
        elif g.risk_weight >= obligor.risk_weight:
            notes.append("CRE22.76: guarantor RW not lower than obligor RW: not recognised")
        else:
            ga = guarantee_after_fx(exposure.guarantee_amount) if _flag(
                exposure, "guarantee_currency_mismatch") else exposure.guarantee_amount
            covered = min(ga, e_star)
            uncovered_rwa = rwa * (e_star - covered) / e_star if e_star > 0 else 0.0
            rwa = covered * g.risk_weight + uncovered_rwa
            notes.append(f"CRE22.79-22.80 guarantee: {covered:.4f} at {g.risk_weight:.0%}")
            citation += f" / {g.citation}"

    eff_rw = rwa / e_star if e_star > 0 else obligor.risk_weight
    return RiskWeightResult(
        exposure_id=exposure.exposure_id,
        jurisdiction=Jurisdiction.BCBS,
        regime_exposure_class=obligor.regime_class,
        risk_weight=eff_rw,
        ccf=conv,
        exposure_amount=e_star,
        rwa=rwa,
        citation=citation,
        notes=notes,
    )
