"""OSFI CAR 2026 Chapter 4 -- credit risk standardized approach, CCFs and CRM.

Implements risk-weight assignment for every :class:`~src.jurisdictions.base.AssetClass`
under OSFI CAR Guideline 2026 Chapter 4 (sections 4.1.1-4.1.24), the off-balance-sheet CCFs
(s.4.1.18), the currency-mismatch multiplier (s.4.1.16) and credit risk mitigation (s.4.3):
the comprehensive approach with the supervisory haircut table and the substitution approach
for guarantees and credit derivatives (incl. CMHC / Government of Canada mortgage insurance).

Real estate uses OSFI's whole-loan approach (Tables 10-13); CAR prints no loan-splitting
option. Residential exposures that are income-producing, that are variable-rate fixed-payment
mortgages in negative amortisation (LTV > 65%, 3+ months), or that do not meet Guideline B-20
expectations take the Table 11 weights.

Regime-specific ``SAExposure.flags`` keys read by this module (all default ``False``):

==========================================  ==============================================
``ca_smsb_simplified``                      Category I/II SMSB simplified treatment (<= $500M)
``ca_canadian_sovereign``                   Government of Canada / Bank of Canada (0%)
``ca_zero_rw_supranational``                BIS, IMF, ECB, EU, ESM, EFSF (0%)
``ca_canadian_province_territory``          Province/territory or agent of the Crown (0%)
``ca_pse_non_own_services_guarantee``       PSE support outside own services -> corporate
``ca_mdb_zero_rw_eligible``                 MDB on the 0% list (footnote 14)
``ca_scra_100pct_election``                 SCRA 100% election for all unrated banks
``ca_bank_exposure_not_in_local_currency``  Triggers the SCRA sovereign floor
``ca_due_diligence_uplift``                 ECRA/rated: one bucket higher after due diligence
``ca_covered_bond_ineligible``              Covered bond fails paras 48-51 -> issuer rating
``ca_corporate_100pct_election``            100% to all corporate exposures (para 60)
``ca_unrated_ig_identification``            Institution identifies all unrated IG/non-IG
``ca_listed_securities``                    Corporate (or parent) has listed securities
``ca_us_gse``                               US government-sponsored enterprise (20%)
``ca_sme_retail_sbe``                       Unrated SME meeting para 83 -> 75% retail SBE
``ca_issue_specific_rating``                SL: rating is issue-specific (Table 9 applies)
``ca_apply_printed_transactor_rw``          Use the printed 15% transactor RW (see params)
``ca_primary_residence``                    RRE secures borrower's primary residence
``ca_vrfp_negative_amortization``           Variable-rate fixed-payment, LTV > 65%, payments
                                            below interest for >= 3 consecutive months
``ca_b20_noncompliant``                     RRE not meeting Guideline B-20 expectations
``ca_junior_lien_other_institution``        Junior lien behind another lender (x1.25)
``ca_reverse_mortgage``                     Reverse mortgage (Table 14)
``ca_reverse_mortgage_non_qualifying``      Reverse mortgage failing paras 116-117
``ca_nha_mbs``                              NHA MBS guaranteed by CMHC (0%)
``ca_counterparty_corporate``               RRE borrower is a corporate (unsecured RW)
``ca_counterparty_individual``              CRE borrower is an individual/SBE (75%);
                                            CRE otherwise defaults to the corporate RW
``ca_counterparty_sme``                     RE borrower is an SME (85%)
``ca_credit_card_undrawn``                  Undrawn credit/charge card line (25% CCF)
``ca_cre_loss_test_exemption``              IPCRE meets footnote 51 loss tests
``ca_borrower_hedged``                      Currency mismatch naturally/financially hedged
``ca_adc_subordinated_tranche``             Subordinated/mezzanine ADC tranche (300%)
``ca_high_rise_without_presale``            5+ storey project without 50% pre-sales
``ca_cash_or_gold`` / ``ca_items_in_transit`` / ``ca_threshold_deduction_item`` /
``ca_pv_future_spread_income`` / ``ca_credit_enhancing_io_strip``   other-asset buckets
``ca_collateral_currency_mismatch``         Apply Hfx = 8% to collateral
``ca_guarantee_currency_mismatch``          Apply Hfx = 8% to the guarantee
``ca_guarantor_government_of_canada``       NHA / provincial insurance, GoC backstop (0%)
``ca_guarantor_prudentially_regulated``     Unrated guarantor is a regulated FI
==========================================  ==============================================

References:
    - OSFI CAR 2026 Ch.4 s.4.1 (Tables 1-14), s.4.2.3.5 (Table 15), s.4.3
    - Basel Framework CRE20, CRE21, CRE22, CRE60
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    Jurisdiction,
    OBSCategory,
    PFPhase,
    RatingBucket,
    RiskWeightResult,
    SAExposure,
    SCRAGrade,
)
from src.jurisdictions.ca import params as p

_RATING_ORDER: tuple[RatingBucket, ...] = (
    RatingBucket.AAA_TO_AA_MINUS,
    RatingBucket.A_PLUS_TO_A_MINUS,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS,
    RatingBucket.BB_PLUS_TO_BB_MINUS,
    RatingBucket.B_PLUS_TO_B_MINUS,
    RatingBucket.BELOW_B_MINUS,
)


@dataclass(frozen=True)
class RWOutcome:
    """Risk weight with the OSFI exposure class and the provision that produced it."""

    risk_weight: float
    regime_class: str
    citation: str
    notes: list[str] = field(default_factory=list)


def _flag(e: SAExposure, key: str) -> bool:
    """Read a regime-specific boolean flag (module docstring lists the keys)."""
    return bool(e.flags.get(key, False))


def _uplift(rating: RatingBucket) -> RatingBucket:
    """Move a rating one bucket worse (CAR Ch.4 s.4.1.4 / 4.1.7 due diligence, [CRE 20.20])."""
    if rating == RatingBucket.UNRATED:
        return rating
    idx = _RATING_ORDER.index(rating)
    return _RATING_ORDER[min(idx + 1, len(_RATING_ORDER) - 1)]


def _rated_lookup(e: SAExposure, table: dict[RatingBucket, float]) -> tuple[float, list[str]]:
    """Look up an ECAI-based table, applying the due-diligence uplift when flagged.

    CAR Ch.4 s.4.1.4, 4.1.5, 4.1.7 -- "the institution must assign a risk weight at least one
    bucket higher than the 'base' risk weight" where due diligence shows higher risk
    [CRE 20.20, 20.39, 20.42].
    """
    rating = e.rating
    notes: list[str] = []
    if _flag(e, "ca_due_diligence_uplift"):
        rating = _uplift(rating)
        notes.append("due-diligence uplift: one rating bucket higher (CRE 20.20)")
    return table[rating], notes


# =========================================================================
#  s.4.1.1 - 4.1.3 Sovereigns, PSEs, MDBs
# =========================================================================

def sovereign_rw(e: SAExposure) -> RWOutcome:
    """Sovereign / central bank risk weight.

    CAR Ch.4 s.4.1.1: Government of Canada and Bank of Canada 0%; BIS/IMF/ECB/EU/ESM/EFSF 0%
    [CRE 20.10]; otherwise Table 1 by external rating [CRE 20.7], or, for unrated sovereigns
    with an OECD/ECA consensus risk score, Table 2 [CRE 20.9].
    """
    if _flag(e, "ca_canadian_sovereign"):
        return RWOutcome(p.CANADA_SOVEREIGN_RW, "Sovereign (Canada)",
                         "CAR Ch.4 s.4.1.1 (Canadian sovereign 0%)")
    if _flag(e, "ca_zero_rw_supranational"):
        return RWOutcome(p.SUPRANATIONAL_ZERO_RW, "Sovereign (BIS/IMF/ECB/EU/ESM/EFSF)",
                         "CAR Ch.4 s.4.1.1 [Basel Framework, CRE 20.10]")
    if e.rating == RatingBucket.UNRATED and e.oecd_crc is not None:
        return RWOutcome(p.ECA_SCORE_RW[e.oecd_crc], "Sovereign (ECA score)",
                         "CAR Ch.4 s.4.1.1 Table 2 [Basel Framework, CRE 20.9]")
    return RWOutcome(p.SOVEREIGN_RW[e.rating], "Sovereign",
                     "CAR Ch.4 s.4.1.1 Table 1 [Basel Framework, CRE 20.7]")


def pse_rw(e: SAExposure) -> RWOutcome:
    """Non-central government PSE risk weight.

    CAR Ch.4 s.4.1.2: provinces/territories and agents of the Crown receive the Government of
    Canada weight; other PSEs one category above the sovereign (Table 3) [CRE 20.11]; PSE
    guarantees outside own municipal/public services are corporate exposures on the PSE's
    rating [CRE 20.12].
    """
    if _flag(e, "ca_canadian_province_territory"):
        return RWOutcome(p.CANADA_SOVEREIGN_RW, "PSE (province/territory)",
                         "CAR Ch.4 s.4.1.2 (same RW as Government of Canada) [CRE 20.12]")
    if _flag(e, "ca_pse_non_own_services_guarantee"):
        out = corporate_rw(e)
        return RWOutcome(out.risk_weight, "PSE treated as corporate",
                         "CAR Ch.4 s.4.1.2 [CRE 20.12] -> " + out.citation, out.notes)
    return RWOutcome(p.PSE_RW_BY_SOVEREIGN_RATING[e.sovereign_rating], "PSE",
                     "CAR Ch.4 s.4.1.2 Table 3 [Basel Framework, CRE 20.11]")


def mdb_rw(e: SAExposure) -> RWOutcome:
    """Multilateral development bank risk weight.

    CAR Ch.4 s.4.1.3: 0% for MDBs meeting the eligibility criteria (footnote 14 list)
    [CRE 20.14]; otherwise Table 4 [CRE 20.15].
    """
    if _flag(e, "ca_mdb_zero_rw_eligible"):
        return RWOutcome(p.MDB_ZERO_RW, "MDB (0% eligible)",
                         "CAR Ch.4 s.4.1.3 [Basel Framework, CRE 20.14]")
    return RWOutcome(p.MDB_RW[e.rating], "MDB",
                     "CAR Ch.4 s.4.1.3 Table 4 [Basel Framework, CRE 20.15]")


# =========================================================================
#  s.4.1.4 Banks (incl. securities firms and FIs treated as banks, OSFI insurers)
# =========================================================================

def _is_bank_short_term(e: SAExposure) -> bool:
    """Short-term bank exposure test.

    CAR Ch.4 s.4.1.4 -- original maturity of three months or less, or goods-movement trade
    exposures with original maturity of six months or less [CRE 20.19, 20.31].
    """
    m = e.original_maturity_months
    if m is None:
        return False
    if m <= p.BANK_SHORT_TERM_MAX_MONTHS:
        return True
    return e.is_trade_related and m <= p.BANK_TRADE_SHORT_TERM_MAX_MONTHS


def bank_rw(e: SAExposure) -> RWOutcome:
    """Bank exposure risk weight (ECRA for rated, SCRA for unrated).

    CAR Ch.4 s.4.1.4: SMSB simplified 40% / 20% (paragraph 26); issue-specific short-term
    ratings via Table 15 [CRE 21.16-21.18]; ECRA Table 5 [CRE 20.18-20.20]; SCRA Table 6 with
    the 30% enhanced Grade A weight [CRE 20.21], the optional 100% election, and the sovereign
    floor for foreign-currency exposures [CRE 20.32].
    """
    short = _is_bank_short_term(e)
    if _flag(e, "ca_smsb_simplified"):
        rw = p.SMSB_BANK_SHORT_TERM_RW if short else p.SMSB_BANK_RW
        return RWOutcome(rw, "Bank (SMSB simplified)", "CAR Ch.4 s.4.1.4 (paragraph 26)")
    if e.short_term_rating is not None:
        return RWOutcome(p.SHORT_TERM_ISSUE_RW[e.short_term_rating], "Bank (short-term rated)",
                         "CAR Ch.4 s.4.2.3.5 Table 15 [Basel Framework, CRE 21.16]")
    if e.rating != RatingBucket.UNRATED:
        table = p.BANK_ECRA_SHORT_TERM_RW if short else p.BANK_ECRA_BASE_RW
        rw, ecra_notes = _rated_lookup(e, table)
        return RWOutcome(rw, "Bank (ECRA)",
                         "CAR Ch.4 s.4.1.4 Table 5 [Basel Framework, CRE 20.18-20.20]", ecra_notes)
    notes: list[str] = []
    if _flag(e, "ca_scra_100pct_election"):
        rw = p.BANK_SCRA_ELECTION_RW
        cite = "CAR Ch.4 s.4.1.4 (SCRA 100% election) [CRE 20.21]"
    else:
        grade = e.scra_grade
        if grade is None:
            grade = SCRAGrade.B
            notes.append("no SCRA grade supplied: Grade B per CAR Ch.4 s.4.1.4 [CRE 20.27]")
        if short:
            rw = p.BANK_SCRA_SHORT_TERM_RW[grade]
        else:
            rw = p.BANK_SCRA_BASE_RW[grade]
            if grade == SCRAGrade.A and e.scra_grade_a_enhanced:
                rw = p.BANK_SCRA_GRADE_A_ENHANCED_RW
                notes.append("Grade A with CET1 >= 14% and Tier 1 leverage >= 5%: 30%")
        cite = "CAR Ch.4 s.4.1.4 Table 6 [Basel Framework, CRE 20.21-20.31]"
    if _flag(e, "ca_bank_exposure_not_in_local_currency"):
        trade_exempt = e.is_trade_related and (
            e.residual_maturity_years is not None and e.residual_maturity_years < 1.0)
        if not trade_exempt:
            floor = p.SOVEREIGN_RW[e.sovereign_rating]
            if floor > rw:
                notes.append(f"SCRA sovereign floor applied ({floor:.0%}) [CRE 20.32]")
                rw = floor
    return RWOutcome(rw, "Bank (SCRA)", cite, notes)


def covered_bond_rw(e: SAExposure) -> RWOutcome:
    """Covered bond risk weight.

    CAR Ch.4 s.4.1.5: SMSB simplified 20% (paragraph 47); eligible rated bonds Table 7, unrated
    bonds Table 8 from the issuer's ECRA/SCRA weight [CRE 20.38]; ineligible bonds on the
    issuer's rating (paragraph after [CRE 20.39]).
    """
    if _flag(e, "ca_smsb_simplified"):
        return RWOutcome(p.SMSB_COVERED_BOND_RW, "Covered bond (SMSB simplified)",
                         "CAR Ch.4 s.4.1.5 (paragraph 47)")
    if _flag(e, "ca_covered_bond_ineligible"):
        issuer = bank_rw(e)
        return RWOutcome(issuer.risk_weight, "Covered bond (ineligible -> issuer)",
                         "CAR Ch.4 s.4.1.5 -> " + issuer.citation, issuer.notes)
    if e.covered_bond_rated and e.rating != RatingBucket.UNRATED:
        rw, notes = _rated_lookup(e, p.COVERED_BOND_RATED_RW)
        return RWOutcome(rw, "Covered bond (rated)",
                         "CAR Ch.4 s.4.1.5 Table 7 [Basel Framework, CRE 20.38]", notes)
    issuer = bank_rw(e)
    rw = p.COVERED_BOND_UNRATED_RW.get(round(issuer.risk_weight, 4), issuer.risk_weight)
    return RWOutcome(rw, "Covered bond (unrated)",
                     "CAR Ch.4 s.4.1.5 Table 8 [Basel Framework, CRE 20.38]",
                     [f"issuer RW {issuer.risk_weight:.0%} via {issuer.citation}"] + issuer.notes)


# =========================================================================
#  s.4.1.7 Corporates, SMEs, specialised lending
# =========================================================================

def _is_sme(e: SAExposure) -> bool:
    """Corporate SME test (CAR Ch.4 s.4.1.7 paragraph 64, sales <= $75M) [CRE 20.47]."""
    if not (e.is_sme or e.asset_class == AssetClass.CORPORATE_SME):
        return False
    return e.annual_turnover is None or e.annual_turnover <= p.SME_SALES_THRESHOLD_CAD_M


def corporate_rw(e: SAExposure) -> RWOutcome:
    """General corporate and corporate SME risk weight.

    CAR Ch.4 s.4.1.7: SMSB simplified 100% (paragraph 58); US GSEs 20%; optional 100% election
    (paragraph 60); rated Table 9 [CRE 20.42-20.43]; short-term issue ratings Table 15; unrated
    SMEs 85% or 75% as retail SBEs (paragraph 64) [CRE 20.47]; unrated non-SMEs 100%, or -- where
    the institution identifies all unrated exposures as IG / non-IG (paragraphs 62-63) -- 65%
    IG / 150% non-IG [cross-ref CRE 20.44, 20.46].
    """
    if _flag(e, "ca_smsb_simplified"):
        return RWOutcome(p.SMSB_CORPORATE_RW, "Corporate (SMSB simplified)",
                         "CAR Ch.4 s.4.1.7 (paragraph 58)")
    if _flag(e, "ca_us_gse"):
        return RWOutcome(p.US_GSE_RW, "Corporate (US GSE)", "CAR Ch.4 s.4.1.7 (paragraph 58)")
    if _flag(e, "ca_corporate_100pct_election"):
        return RWOutcome(p.CORPORATE_ELECTION_RW, "Corporate (100% election)",
                         "CAR Ch.4 s.4.1.7 (paragraph 60)")
    if e.short_term_rating is not None:
        return RWOutcome(p.SHORT_TERM_ISSUE_RW[e.short_term_rating], "Corporate (short-term rated)",
                         "CAR Ch.4 s.4.2.3.5 Table 15 [Basel Framework, CRE 21.16]")
    if e.rating != RatingBucket.UNRATED:
        rw, notes = _rated_lookup(e, p.CORPORATE_RATED_RW)
        return RWOutcome(rw, "Corporate (rated)",
                         "CAR Ch.4 s.4.1.7 Table 9 [Basel Framework, CRE 20.42-20.43]", notes)
    notes = []
    if e.asset_class == AssetClass.CORPORATE_SME and not _is_sme(e):
        notes.append("sales above $75M: not an SME under CAR Ch.4 paragraph 64")
    if _is_sme(e):
        if _flag(e, "ca_sme_retail_sbe"):
            return RWOutcome(p.SME_RETAIL_SBE_RW, "Corporate SME (regulatory retail SBE)",
                             "CAR Ch.4 s.4.1.7 (paragraph 64) [Basel Framework, CRE 20.47]")
        return RWOutcome(p.CORPORATE_SME_UNRATED_RW, "Corporate SME (unrated)",
                         "CAR Ch.4 s.4.1.7 (paragraph 64) [Basel Framework, CRE 20.47]")
    identifies = e.flags.get("ca_unrated_ig_identification", e.is_investment_grade is not None)
    if identifies:
        meets_listing_or_size = _flag(e, "ca_listed_securities") or (
            e.annual_turnover is None or e.annual_turnover > p.IG_LISTED_OR_SALES_THRESHOLD_CAD_M)
        if e.is_investment_grade and meets_listing_or_size:
            return RWOutcome(p.CORPORATE_UNRATED_IG_RW, "Corporate (unrated IG)",
                             "CAR Ch.4 s.4.1.7 (paragraphs 62-63) [CRE 20.44, 20.46]", notes)
        if e.is_investment_grade:
            notes.append("IG but neither listed nor sales > $75M (paragraph 63): non-IG")
        return RWOutcome(p.CORPORATE_UNRATED_NON_IG_RW, "Corporate (unrated non-IG)",
                         "CAR Ch.4 s.4.1.7 (paragraph 62) [cross-ref CRE 20.44]",
                         notes + ["TODO: VERIFY 150% as printed (Basel CRE20.44: 100%)"])
    return RWOutcome(p.CORPORATE_UNRATED_RW, "Corporate (unrated)",
                     "CAR Ch.4 s.4.1.7 (paragraph 62, footnote 23) [CRE 20.43-20.44]", notes)


def specialised_lending_rw(e: SAExposure) -> RWOutcome:
    """Project, object and commodities finance risk weight.

    CAR Ch.4 s.4.1.7 "Specialized lending": issue-specific ratings via Table 9 (issuer ratings
    not permitted) [CRE 20.50]; unrated OF/CF 100%; PF 130% pre-operational, 100% operational,
    80% high-quality operational [CRE 20.51-20.52]. SMSB simplified 100% (paragraph 58).
    """
    if _flag(e, "ca_smsb_simplified"):
        return RWOutcome(p.SMSB_CORPORATE_RW, "Specialized lending (SMSB simplified)",
                         "CAR Ch.4 s.4.1.7 (paragraph 58)")
    if e.rating != RatingBucket.UNRATED and _flag(e, "ca_issue_specific_rating"):
        rw, notes = _rated_lookup(e, p.CORPORATE_RATED_RW)
        return RWOutcome(rw, "Specialized lending (issue rated)",
                         "CAR Ch.4 s.4.1.7 Table 9 [Basel Framework, CRE 20.50]", notes)
    if e.asset_class == AssetClass.SPECIALISED_LENDING_PF:
        phase = e.pf_phase or PFPhase.PRE_OPERATIONAL
        rw = {
            PFPhase.PRE_OPERATIONAL: p.SL_PF_PRE_OPERATIONAL_RW,
            PFPhase.OPERATIONAL: p.SL_PF_OPERATIONAL_RW,
            PFPhase.HIGH_QUALITY_OPERATIONAL: p.SL_PF_HIGH_QUALITY_RW,
        }[phase]
        notes = [] if e.pf_phase else ["phase not supplied: pre-operational assumed"]
        return RWOutcome(rw, f"Project finance ({phase.value})",
                         "CAR Ch.4 s.4.1.7 [Basel Framework, CRE 20.51-20.52]", notes)
    kind = "Object finance" if e.asset_class == AssetClass.SPECIALISED_LENDING_OF else (
        "Commodities finance")
    return RWOutcome(p.SL_OBJECT_COMMODITY_RW, kind,
                     "CAR Ch.4 s.4.1.7 [Basel Framework, CRE 20.51]")


# =========================================================================
#  s.4.1.8 Subordinated debt, equity
# =========================================================================

def subordinated_rw(e: SAExposure) -> RWOutcome:
    """Subordinated debt / non-equity capital instruments (CAR Ch.4 s.4.1.8 para 78) [CRE 20.60]."""
    return RWOutcome(p.SUBORDINATED_DEBT_RW, "Subordinated debt / other capital instruments",
                     "CAR Ch.4 s.4.1.8 (paragraph 78) [Basel Framework, CRE 20.60]")


def equity_rw(e: SAExposure) -> RWOutcome:
    """Equity risk weight.

    CAR Ch.4 s.4.1.8: 400% speculative unlisted, 250% all other equity (paragraph 75)
    [CRE 20.57-20.58]; 100% legislated programmes up to 10% of Total capital (paragraph 77)
    [CRE 20.59]; significant investments in commercial entities below 10% of CET1: 250%
    [CRE 20.62]. CAR 2026 contains no equity transitional schedule. The US-specific
    ``PUBLICLY_TRADED`` / ``NON_PUBLIC`` categories have no CAR counterpart and take 250%.
    """
    t = e.equity_type or EquityType.GENERAL
    cite_general = "CAR Ch.4 s.4.1.8 (paragraph 75) [Basel Framework, CRE 20.57]"
    if t == EquityType.SPECULATIVE_UNLISTED:
        return RWOutcome(p.EQUITY_SPECULATIVE_UNLISTED_RW, "Equity (speculative unlisted)",
                         "CAR Ch.4 s.4.1.8 (paragraphs 75-76) [CRE 20.57-20.58]")
    if t == EquityType.LEGISLATIVE_PROGRAMME:
        return RWOutcome(p.EQUITY_LEGISLATED_PROGRAMME_RW, "Equity (legislated programme)",
                         "CAR Ch.4 s.4.1.8 (paragraph 77) [Basel Framework, CRE 20.59]",
                         ["100% only up to 10% of Total capital in aggregate"])
    if t == EquityType.SIGNIFICANT_FI:
        return RWOutcome(p.SIGNIFICANT_COMMERCIAL_INVESTMENT_RW, "Equity (significant / threshold)",
                         "CAR Ch.4 s.4.1.8 [CRE 20.62]; s.4.1.23 250% threshold items")
    notes = []
    if t in (EquityType.PUBLICLY_TRADED, EquityType.NON_PUBLIC):
        notes.append(f"{t.value} has no CAR sub-category: general equity 250%")
    return RWOutcome(p.EQUITY_GENERAL_RW, "Equity (general)", cite_general, notes)


# =========================================================================
#  s.4.1.9 Retail
# =========================================================================

def retail_rw(e: SAExposure) -> RWOutcome:
    """Retail risk weight.

    CAR Ch.4 s.4.1.9: regulatory retail (paragraph 83: orientation, product, <= $1.5M,
    0.2% granularity) 75%; transactors (paragraph 84) -- printed 15%, conservative 45% placeholder
    applied by default (see params TODO); other retail 100% [CRE 20.65-20.68]. SMSB simplified
    75% (paragraph 81).
    """
    agg = e.aggregate_retail_exposure_to_obligor
    regulatory = e.meets_regulatory_retail_criteria and (
        agg is None or agg <= p.RETAIL_MAX_AGGREGATE_CAD_M)
    if e.asset_class == AssetClass.RETAIL_OTHER or not regulatory:
        return RWOutcome(p.RETAIL_OTHER_RW, "Retail (non-regulatory)",
                         "CAR Ch.4 s.4.1.9 [Basel Framework, CRE 20.67-20.68]")
    if _flag(e, "ca_smsb_simplified"):
        return RWOutcome(p.SMSB_RETAIL_RW, "Retail (SMSB simplified)",
                         "CAR Ch.4 s.4.1.9 (paragraph 81)")
    if e.asset_class == AssetClass.RETAIL_TRANSACTOR or e.is_transactor:
        if _flag(e, "ca_apply_printed_transactor_rw"):
            return RWOutcome(p.RETAIL_TRANSACTOR_RW_AS_PRINTED, "Retail (transactor)",
                             "CAR Ch.4 s.4.1.9 (as printed: 15%) [cross-ref CRE 20.68]",
                             ["TODO: VERIFY printed 15% conflicts with CRE20.68 (45%)"])
        return RWOutcome(p.RETAIL_TRANSACTOR_RW_CONSERVATIVE, "Retail (transactor)",
                         "CAR Ch.4 s.4.1.9 [Basel Framework, CRE 20.68(2)]",
                         ["TODO: VERIFY conservative 45% placeholder; CAR text prints 15%"])
    return RWOutcome(p.RETAIL_REGULATORY_RW, "Retail (regulatory)",
                     "CAR Ch.4 s.4.1.9 [Basel Framework, CRE 20.68(1)]")


# =========================================================================
#  s.4.1.11 Residential real estate, s.4.1.14 reverse mortgages, s.4.1.15 MBS
# =========================================================================

def _ltv_band(ltv: float, bands: tuple[tuple[float, float], ...],
              above: float) -> tuple[float, int]:
    """Return (risk weight, band index) for an LTV schedule with inclusive upper bounds."""
    for i, (upper, rw) in enumerate(bands):
        if ltv <= upper:
            return rw, i
    return above, len(bands)


def heloc_ltv(drawn: float, undrawn: float, other_senior_loans: float,
              property_value: float) -> float:
    """LTV for a HELOC with the 75% CCF on the undrawn amount.

    CAR Ch.4 s.4.1.11 -- "In calculating the LTV ratio for purposes of Home equity lines of credit
    (HELOC), a 75% credit conversion factor should be applied to the undrawn exposure".
    """
    if property_value <= 0:
        raise ValueError("property value must be positive")
    return (drawn + p.HELOC_LTV_UNDRAWN_CCF * undrawn + other_senior_loans) / property_value


def reverse_mortgage_rw(e: SAExposure) -> RWOutcome:
    """Reverse mortgage effective risk weight (CAR Ch.4 s.4.1.14 Table 14, OSFI-specific).

    Bands <= 35% / 55% / 65% / 80% current LTV -> 30 / 35 / 45 / 60%. Above 80% LTV the portion
    above 80% is deducted from CET1 and the remainder risk-weighted at 100% (150% if the
    paragraph 116-117 criteria are not met). The deduction is reported in ``notes``; the
    returned weight is the RWA per unit of total exposure.
    """
    ltv = e.ltv if e.ltv is not None else 1.0
    non_q = _flag(e, "ca_reverse_mortgage_non_qualifying")
    if not non_q and ltv <= p.REVERSE_MORTGAGE_DEDUCTION_LTV:
        rw, _ = _ltv_band(ltv, p.REVERSE_MORTGAGE_BANDS, p.REVERSE_MORTGAGE_ABOVE_80_REMAINDER_RW)
        return RWOutcome(rw, "Reverse mortgage", "CAR Ch.4 s.4.1.14 Table 14")
    remainder_rw = (p.REVERSE_MORTGAGE_NON_QUALIFYING_REMAINDER_RW if non_q
                    else p.REVERSE_MORTGAGE_ABOVE_80_REMAINDER_RW)
    if ltv <= p.REVERSE_MORTGAGE_DEDUCTION_LTV:
        return RWOutcome(remainder_rw, "Reverse mortgage (non-qualifying)",
                         "CAR Ch.4 s.4.1.14 Table 14")
    kept = p.REVERSE_MORTGAGE_DEDUCTION_LTV / ltv
    return RWOutcome(remainder_rw * kept, "Reverse mortgage (> 80% LTV)",
                     "CAR Ch.4 s.4.1.14 Table 14",
                     [f"{1 - kept:.4f} of the exposure (above 80% LTV) is deducted from CET1"])


def _re_counterparty_rw(e: SAExposure) -> tuple[float, str]:
    """'Risk weight of the counterparty' for real estate (CAR Ch.4 s.4.1.11-4.1.12).

    75% for individuals and SBEs, 85% for SMEs, otherwise the unsecured counterparty weight
    [CRE 20.88-20.89].
    """
    if _flag(e, "ca_counterparty_sme") or e.is_sme:
        return p.RRE_NON_QUALIFYING_SME_RW, "SME 85%"
    if _flag(e, "ca_counterparty_corporate"):
        out = corporate_rw(e.model_copy(update={"asset_class": AssetClass.CORPORATE}))
        return out.risk_weight, f"corporate unsecured RW ({out.citation})"
    return p.RRE_NON_QUALIFYING_INDIVIDUAL_RW, "individual/SBE 75%"


def residential_re_rw(e: SAExposure) -> RWOutcome:
    """Residential real estate risk weight (whole-loan approach).

    CAR Ch.4 s.4.1.11: SMSB simplified 35% / 75% at 80% LTV (paragraph 96); general RRE
    Table 10 [CRE 20.82]; income-producing RRE Table 11 -- also applied to variable-rate
    fixed-payment mortgages with LTV > 65% and >= 3 months of payments below interest
    (paragraph 101(i)) and to B-20 non-compliant exposures [CRE 20.80, 20.84]; non-qualifying
    IPRRE 150%; non-qualifying general RRE at the counterparty weight [CRE 20.88-20.89];
    junior liens x1.25 (footnote 42). Reverse mortgages s.4.1.14, NHA MBS s.4.1.15.
    """
    if _flag(e, "ca_nha_mbs"):
        return RWOutcome(p.NHA_MBS_RW, "NHA MBS (CMHC guaranteed)", "CAR Ch.4 s.4.1.15")
    if _flag(e, "ca_reverse_mortgage") or _flag(e, "ca_reverse_mortgage_non_qualifying"):
        return reverse_mortgage_rw(e)
    ltv = e.ltv
    notes: list[str] = []
    if _flag(e, "ca_smsb_simplified") and e.is_regulatory_real_estate:
        if ltv is None:
            notes.append("LTV not supplied: treated as > 80%")
        rw = (p.SMSB_RRE_LOW_LTV_RW if ltv is not None and ltv <= p.SMSB_RRE_LTV_THRESHOLD
              else p.SMSB_RRE_HIGH_LTV_RW)
        return RWOutcome(rw, "RRE (SMSB simplified)", "CAR Ch.4 s.4.1.11 (paragraph 96)", notes)

    cash_flow = e.is_cash_flow_dependent and not _flag(e, "ca_primary_residence")
    if e.is_cash_flow_dependent and not cash_flow:
        notes.append("primary residence excluded from IPRRE treatment [CRE 20.81]")
    vrfp = _flag(e, "ca_vrfp_negative_amortization") and ltv is not None and (
        ltv > p.VRFP_LTV_TRIGGER)
    b20 = _flag(e, "ca_b20_noncompliant") and e.is_regulatory_real_estate
    table11 = cash_flow or vrfp or b20
    if vrfp:
        notes.append("variable-rate fixed-payment, LTV > 65%, negative amortisation >= 3 months")
    if b20:
        notes.append("Guideline B-20 expectations not met: Table 11")

    if not e.is_regulatory_real_estate:
        if table11:
            return RWOutcome(p.RRE_IPRE_NON_QUALIFYING_RW, "RRE income-producing (non-qualifying)",
                             "CAR Ch.4 s.4.1.11 (paragraph 101)", notes)
        rw, why = _re_counterparty_rw(e)
        return RWOutcome(rw, "RRE (non-qualifying)",
                         "CAR Ch.4 s.4.1.11 [Basel Framework, CRE 20.88-20.89]", notes + [why])

    if ltv is None:
        ltv = 1.0 + 1e-9
        notes.append("LTV not supplied: highest LTV band applied")
    if table11:
        rw, band = _ltv_band(ltv, p.RRE_INCOME_PRODUCING_LTV_BANDS,
                             p.RRE_INCOME_PRODUCING_ABOVE_100_RW)
        cap = p.RRE_IPRE_NON_QUALIFYING_RW
        cls, cite = "RRE income-producing", "CAR Ch.4 s.4.1.11 Table 11 [CRE 20.80, 20.84]"
    else:
        rw, band = _ltv_band(ltv, p.RRE_GENERAL_LTV_BANDS, p.RRE_GENERAL_ABOVE_100_RW)
        cap = _re_counterparty_rw(e)[0]
        cls, cite = "RRE general", "CAR Ch.4 s.4.1.11 Table 10 [Basel Framework, CRE 20.82]"
    if _flag(e, "ca_junior_lien_other_institution") and band > 0:
        rw = min(rw * p.JUNIOR_LIEN_MULTIPLIER, max(cap, rw))
        notes.append("junior lien x1.25 (CAR Ch.4 footnote 42)")
    return RWOutcome(rw, cls, cite, notes)


# =========================================================================
#  s.4.1.12 Commercial real estate, s.4.1.13 ADC
# =========================================================================

def commercial_re_rw(e: SAExposure) -> RWOutcome:
    """Commercial real estate risk weight (whole-loan approach).

    CAR Ch.4 s.4.1.12: SMSB simplified 100% (paragraph 105); general CRE Table 12 -- LTV <= 60%
    min(60%, counterparty RW), else counterparty RW [CRE 20.85]; income-producing CRE Table 13
    70/90/110% [CRE 20.87-20.89] unless the footnote 51 loss tests are met; non-qualifying IPCRE
    150%, non-qualifying general CRE at counterparty RW [CRE 20.88-20.89].
    """
    if _flag(e, "ca_smsb_simplified") and e.is_regulatory_real_estate:
        return RWOutcome(p.SMSB_CRE_RW, "CRE (SMSB simplified)",
                         "CAR Ch.4 s.4.1.12 (paragraph 105)")
    notes: list[str] = []
    cash_flow = e.is_cash_flow_dependent
    if cash_flow and _flag(e, "ca_cre_loss_test_exemption"):
        cash_flow = False
        notes.append("footnote 51 loss tests met: general CRE treatment")
    if _flag(e, "ca_counterparty_sme") or e.is_sme:
        cp_rw, why = p.CRE_COUNTERPARTY_SME_RW, "SME 85%"
    elif _flag(e, "ca_counterparty_individual"):
        cp_rw, why = p.CRE_COUNTERPARTY_INDIVIDUAL_RW, "individual/SBE 75%"
    else:
        out = corporate_rw(e.model_copy(update={"asset_class": AssetClass.CORPORATE}))
        cp_rw, why = out.risk_weight, f"corporate unsecured RW ({out.citation})"
    if not e.is_regulatory_real_estate:
        if cash_flow:
            return RWOutcome(p.CRE_IPRE_NON_QUALIFYING_RW, "CRE income-producing (non-qualifying)",
                             "CAR Ch.4 s.4.1.12 (paragraph 109)", notes)
        return RWOutcome(cp_rw, "CRE (non-qualifying)",
                         "CAR Ch.4 s.4.1.12 [Basel Framework, CRE 20.88-20.89]", notes + [why])
    ltv = e.ltv
    if ltv is None:
        ltv = 1.0 + 1e-9
        notes.append("LTV not supplied: highest LTV band applied")
    if cash_flow:
        rw, _ = _ltv_band(ltv, p.CRE_INCOME_PRODUCING_LTV_BANDS, p.CRE_INCOME_PRODUCING_ABOVE_80_RW)
        return RWOutcome(rw, "CRE income-producing",
                         "CAR Ch.4 s.4.1.12 Table 13 [Basel Framework, CRE 20.87-20.89]", notes)
    rw = min(p.CRE_GENERAL_CAP_RW, cp_rw) if ltv <= p.CRE_GENERAL_LTV_THRESHOLD else cp_rw
    return RWOutcome(rw, "CRE general", "CAR Ch.4 s.4.1.12 Table 12 [Basel Framework, CRE 20.85]",
                     notes + [why])


def adc_rw(e: SAExposure) -> RWOutcome:
    """Land acquisition, development and construction risk weight.

    CAR Ch.4 s.4.1.13: 150% [CRE 20.90]; 100% for residential ADC with pre-sales > 50% or equity
    at risk >= 25% (land LTV <= 60%; high-rise needs the 50% pre-sales) [CRE 20.91];
    subordinated/mezzanine ADC tranche 300% (OSFI-specific).
    """
    if _flag(e, "ca_adc_subordinated_tranche"):
        return RWOutcome(p.ADC_SUBORDINATED_TRANCHE_RW, "ADC (subordinated tranche)",
                         "CAR Ch.4 s.4.1.13 (paragraph 113)")
    if e.is_adc_presold_or_equity_at_risk and not _flag(e, "ca_high_rise_without_presale"):
        return RWOutcome(p.ADC_RESIDENTIAL_QUALIFYING_RW, "ADC residential (qualifying)",
                         "CAR Ch.4 s.4.1.13 (paragraph 113) [Basel Framework, CRE 20.91]")
    return RWOutcome(p.ADC_RW, "ADC", "CAR Ch.4 s.4.1.13 [Basel Framework, CRE 20.90]")


# =========================================================================
#  s.4.1.21 Defaulted, s.4.1.23 Other assets
# =========================================================================

def defaulted_rw(e: SAExposure) -> RWOutcome:
    """Defaulted exposure risk weight (unsecured / unguaranteed portion).

    CAR Ch.4 s.4.1.21: defaulted RRE not materially dependent on property cash flows 100%
    (paragraph 144) [CRE 20.107]; otherwise 150% if specific provisions < 20% of the outstanding
    amount, 100% if >= 20% [CRE 20.106].
    """
    if e.asset_class == AssetClass.RESIDENTIAL_RE and not e.is_cash_flow_dependent:
        return RWOutcome(p.DEFAULTED_RRE_RW, "Defaulted RRE",
                         "CAR Ch.4 s.4.1.21 (paragraph 144) [Basel Framework, CRE 20.107]")
    if e.specific_provision_pct >= p.DEFAULTED_PROVISION_THRESHOLD:
        return RWOutcome(p.DEFAULTED_HIGH_PROVISION_RW, "Defaulted (provisions >= 20%)",
                         "CAR Ch.4 s.4.1.21 [Basel Framework, CRE 20.106]")
    return RWOutcome(p.DEFAULTED_LOW_PROVISION_RW, "Defaulted (provisions < 20%)",
                     "CAR Ch.4 s.4.1.21 [Basel Framework, CRE 20.106]")


def other_assets_rw(e: SAExposure) -> RWOutcome:
    """Other assets (CAR Ch.4 s.4.1.23) [CRE 20.109-20.110]."""
    cite = "CAR Ch.4 s.4.1.23 [Basel Framework, CRE 20.109-20.110]"
    if _flag(e, "ca_cash_or_gold"):
        return RWOutcome(p.OTHER_CASH_GOLD_RW, "Other assets (cash / gold bullion)", cite)
    if _flag(e, "ca_items_in_transit"):
        return RWOutcome(p.OTHER_ITEMS_IN_TRANSIT_RW, "Other assets (items in transit)", cite)
    if _flag(e, "ca_credit_enhancing_io_strip"):
        return RWOutcome(p.OTHER_SECURITISATION_IO_RW, "Other assets (CE I/O strip)", cite)
    if _flag(e, "ca_threshold_deduction_item") or _flag(e, "ca_pv_future_spread_income"):
        return RWOutcome(p.OTHER_THRESHOLD_ITEMS_RW, "Other assets (250% items)", cite)
    return RWOutcome(p.OTHER_ASSETS_RW, "Other assets", cite)


# =========================================================================
#  Dispatcher, currency mismatch, CCF
# =========================================================================

_DISPATCH = {
    AssetClass.SOVEREIGN: sovereign_rw,
    AssetClass.PSE: pse_rw,
    AssetClass.MDB: mdb_rw,
    AssetClass.BANK: bank_rw,
    AssetClass.COVERED_BOND: covered_bond_rw,
    AssetClass.CORPORATE: corporate_rw,
    AssetClass.CORPORATE_SME: corporate_rw,
    AssetClass.SPECIALISED_LENDING_PF: specialised_lending_rw,
    AssetClass.SPECIALISED_LENDING_OF: specialised_lending_rw,
    AssetClass.SPECIALISED_LENDING_CF: specialised_lending_rw,
    AssetClass.SUBORDINATED_DEBT: subordinated_rw,
    AssetClass.EQUITY: equity_rw,
    AssetClass.RETAIL_REGULATORY: retail_rw,
    AssetClass.RETAIL_TRANSACTOR: retail_rw,
    AssetClass.RETAIL_OTHER: retail_rw,
    AssetClass.RESIDENTIAL_RE: residential_re_rw,
    AssetClass.COMMERCIAL_RE: commercial_re_rw,
    AssetClass.LAND_ADC: adc_rw,
    AssetClass.DEFAULTED: defaulted_rw,
    AssetClass.OTHER_ASSETS: other_assets_rw,
}


def apply_currency_mismatch(e: SAExposure, out: RWOutcome) -> RWOutcome:
    """Currency-mismatch multiplier.

    CAR Ch.4 s.4.1.16 (paragraph 123): unhedged residential real estate exposures to individuals
    where > 10% of qualifying income is in a foreign currency -> RW x 1.5, capped at 150%
    [CRE 20.92-20.93]. OSFI's scope is RRE only (Basel also covers retail).
    ``currency_matches_borrower_income = False`` is read as the > 10% condition being met.
    """
    if (e.asset_class != AssetClass.RESIDENTIAL_RE or e.currency_matches_borrower_income
            or _flag(e, "ca_borrower_hedged") or _flag(e, "ca_counterparty_corporate")):
        return out
    rw = min(out.risk_weight * p.CURRENCY_MISMATCH_MULTIPLIER, p.CURRENCY_MISMATCH_RW_CAP)
    return RWOutcome(rw, out.regime_class, out.citation + "; CAR Ch.4 s.4.1.16 x1.5 cap 150%",
                     out.notes + ["currency mismatch multiplier applied [CRE 20.92]"])


def assign_risk_weight(e: SAExposure) -> RWOutcome:
    """Risk weight for any exposure (CAR Ch.4 s.4.1), incl. default and currency mismatch.

    Exposures flagged ``is_defaulted`` (or in the DEFAULTED class) take the s.4.1.21 treatment
    [CRE 20.104-20.107]; the currency-mismatch multiplier then applies (s.4.1.16).
    """
    if e.is_defaulted or e.asset_class == AssetClass.DEFAULTED:
        out = defaulted_rw(e)
    else:
        out = _DISPATCH[e.asset_class](e)
    return apply_currency_mismatch(e, out)


def ccf_for(e: SAExposure) -> float:
    """Credit conversion factor for the off-balance-sheet notional.

    CAR Ch.4 s.4.1.18 [CRE 20.94-20.101]: 100% credit substitutes, repos, securities lent,
    forward purchases; 50% NIFs/RUFs and transaction-related contingents; 40% commitments
    regardless of maturity; 25% undrawn credit and charge cards (OSFI-specific, applies even
    where unconditionally cancellable); 20% short-term trade LCs; 10% unconditionally
    cancellable. Reverse-mortgage undrawn amounts 40% (s.4.1.14). Undefined category -> 100%.
    """
    if e.off_balance_notional == 0.0:
        return 0.0
    if _flag(e, "ca_credit_card_undrawn"):
        return p.CREDIT_CARD_UNDRAWN_CCF
    if _flag(e, "ca_reverse_mortgage"):
        return p.REVERSE_MORTGAGE_UNDRAWN_CCF
    if e.obs_category is None:
        return p.CCF[OBSCategory.OTHER_100]
    return p.CCF[e.obs_category]


# =========================================================================
#  s.4.3 Credit risk mitigation
# =========================================================================

def scaled_haircut(h10: float, nr_business_days: int, tm_business_days: int) -> float:
    """Scale a 10-day haircut: H = H10 x sqrt((NR + TM - 1) / 10).

    CAR Ch.4 s.4.3.3(iii)(d) (paragraph 249) [CRE 22.59].
    """
    return float(h10 * ((nr_business_days + tm_business_days - 1) / 10.0) ** 0.5)


def comprehensive_exposure(e_amt: float, c_amt: float, he: float, hc: float, hfx: float) -> float:
    """E* = max{0, E(1 + He) - C(1 - Hc - Hfx)} (CAR Ch.4 s.4.3.3(iii)(c), [CRE 22.46])."""
    return max(0.0, e_amt * (1.0 + he) - c_amt * (1.0 - hc - hfx))


def maturity_mismatch_adjust(protection: float, t_protection_years: float,
                             t_exposure_years: float, original_protection_years: float) -> float:
    """Pa = P x (t - 0.25) / (T - 0.25), with recognition conditions.

    CAR Ch.4 s.4.3.1(iv) [CRE 22.12-22.13]: no recognition where the protection's original
    maturity is < 1 year or residual maturity < 3 months; t = min(T, residual protection),
    T = min(5, residual exposure maturity).
    """
    if t_protection_years >= t_exposure_years:
        return protection
    if (original_protection_years < p.MATURITY_MISMATCH_MIN_ORIGINAL_YEARS
            or t_protection_years < p.MATURITY_MISMATCH_MIN_RESIDUAL_YEARS):
        return 0.0
    big_t = min(p.MATURITY_MISMATCH_T_CAP_YEARS, t_exposure_years)
    t = min(big_t, t_protection_years)
    lo = p.MATURITY_MISMATCH_MIN_RESIDUAL_YEARS
    return protection * (t - lo) / (big_t - lo)


def private_mi_split(original_loan: float, outstanding: float) -> tuple[float, float]:
    """Split a privately insured mortgage with a Government of Canada backstop.

    CAR Ch.4 s.4.3.5(vi) (paragraph 274): deductible portion = 10% of the original loan amount
    (capped at the outstanding balance); backstop portion = outstanding less deductible, treated
    as a sovereign exposure. Returns (deductible, backstop).
    """
    deductible = min(outstanding, p.PRIVATE_MI_DEDUCTIBLE_PCT_ORIGINAL * original_loan)
    return deductible, outstanding - deductible


_ELIGIBLE_GUARANTORS = {AssetClass.SOVEREIGN, AssetClass.PSE, AssetClass.MDB, AssetClass.BANK}


def guarantor_rw(e: SAExposure) -> float | None:
    """Risk weight of an eligible guarantor, or ``None`` if not eligible.

    CAR Ch.4 s.4.3.5(v) [CRE 22.76]: sovereigns, PSEs, MDBs, banks, securities firms and other
    prudentially regulated FIs; other entities only if externally rated. NHA / provincial
    mortgage insurance and the Government of Canada backstop -> 0% (paragraph 273).
    """
    if _flag(e, "ca_guarantor_government_of_canada"):
        return p.CANADA_SOVEREIGN_RW
    cls = e.guarantor_asset_class
    if cls is None:
        return None
    eligible = cls in _ELIGIBLE_GUARANTORS or _flag(e, "ca_guarantor_prudentially_regulated") or (
        e.guarantor_rating != RatingBucket.UNRATED)
    if not eligible:
        return None
    synthetic = SAExposure(exposure_id=e.exposure_id + ":guarantor", asset_class=cls,
                           rating=e.guarantor_rating, sovereign_rating=e.guarantor_rating)
    return _DISPATCH[cls](synthetic).risk_weight


def risk_weight_result(e: SAExposure) -> RiskWeightResult:
    """Full SA calculation for one exposure: CCF, comprehensive-approach collateral, substitution.

    Exposure = on-balance + CCF x off-balance (CAR Ch.4 s.4.1.18). Eligible financial collateral
    reduces the exposure via E* (s.4.3.3(iii), haircut key ``collateral_haircut_class`` in
    ``params.SUPERVISORY_HAIRCUTS``; Hfx 8% when flagged). An eligible guarantee with a lower
    risk weight covers min(G x (1 - Hfx), E*) at the guarantor weight (s.4.3.5(vi) [CRE 22.79,
    22.82]); ``risk_weight`` is then the blended weight on the post-CRM exposure.
    """
    out = assign_risk_weight(e)
    ccf = ccf_for(e)
    gross = e.on_balance_amount + ccf * e.off_balance_notional
    notes = list(out.notes)
    exposure = gross
    if e.financial_collateral_value > 0:
        key = e.collateral_haircut_class or ""
        if key in p.SUPERVISORY_HAIRCUTS:
            hfx = p.HFX_10D if _flag(e, "ca_collateral_currency_mismatch") else 0.0
            exposure = comprehensive_exposure(gross, e.financial_collateral_value, 0.0,
                                              p.SUPERVISORY_HAIRCUTS[key], hfx)
            notes.append(f"comprehensive approach: Hc={p.SUPERVISORY_HAIRCUTS[key]:.3f}, "
                         f"Hfx={hfx:.2f} (CAR Ch.4 s.4.3.3(iii) [CRE 22.46-22.52])")
        else:
            notes.append(f"collateral not recognised: haircut class '{key}' not eligible")
    rwa = exposure * out.risk_weight
    rw = out.risk_weight
    if e.guarantee_amount > 0 and exposure > 0:
        g_rw = guarantor_rw(e)
        if g_rw is not None and g_rw < out.risk_weight:
            hfx = p.HFX_10D if _flag(e, "ca_guarantee_currency_mismatch") else 0.0
            covered = min(exposure, e.guarantee_amount * (1.0 - hfx))
            rwa = covered * g_rw + (exposure - covered) * out.risk_weight
            rw = rwa / exposure
            notes.append(f"substitution: {covered:.4f} at guarantor RW {g_rw:.0%}, obligor RW "
                         f"{out.risk_weight:.0%} (CAR Ch.4 s.4.3.5(vi) [CRE 22.79])")
        else:
            notes.append("guarantee not recognised (ineligible or not lower RW) [CRE 22.76]")
    return RiskWeightResult(
        exposure_id=e.exposure_id, jurisdiction=Jurisdiction.CA,
        regime_exposure_class=out.regime_class, risk_weight=rw, ccf=ccf,
        exposure_amount=exposure, rwa=rwa, citation=out.citation, notes=notes,
    )
