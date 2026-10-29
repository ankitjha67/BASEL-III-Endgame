"""Basel Framework (BCBS) regulatory parameters -- the international baseline.

Every constant below is transcribed from the consolidated Basel Framework
(BIS, generated 29/10/2026) and carries its paragraph reference. Page
numbers are the "n / 1429" page footers of that document. Where an equation
in the Framework is an image that did not survive text extraction, the
equation is taken from BCBS d424 (Basel III: Finalising post-crisis reforms,
Dec 2017) and the d424 paragraph is cited as well; where neither text
settles a value the constant carries a ``TODO: VERIFY`` marker.

The verbatim transcription is ``docs/jurisdictions/BCBS_parameter_reference.md``.

References:
    - Basel Framework CRE20 (SA individual exposures, pp. 179-217)
    - Basel Framework CRE21 (use of external ratings, pp. 218-224)
    - Basel Framework CRE22 (credit risk mitigation, pp. 225-249)
    - Basel Framework CRE52 (SA-CCR, pp. 434-462), CRE90 (transition, p. 514)
    - Basel Framework MAR50 (CVA framework, pp. 722-750)
    - Basel Framework OPE25 (operational risk standardised approach, pp. 769-783)
    - Basel Framework RBC20, RBC30, RBC40, RBC90 (pp. 138-177)
    - Basel Framework LEV20, LEV40 (pp. 787-813), SCO40 (pp. 15-24)
    - BCBS d424 (Dec 2017) for equations rendered as images in the Framework

Monetary thresholds stated by the Framework in EUR are kept in EUR (millions)
as stated; the engine is currency-agnostic and expects inputs in the same
unit (see the module docstrings that consume them).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from src.jurisdictions.base import (
    OBSCategory,
    PFPhase,
    RatingBucket,
    RealEstateTreatment,
    SCRAGrade,
    ShortTermRating,
)

R = RatingBucket

# =========================================================================
#  National discretions (regime options) -- BCBS defaults
# =========================================================================


@dataclass(frozen=True)
class BCBSOptions:
    """National-discretion switches in the Basel Framework, with BCBS defaults.

    Each field documents the paragraph that grants the discretion. The
    default is the treatment the Framework states as the base rule; where
    the Framework offers two options without naming a base rule (PSE Option
    1 vs Option 2, CRE20.11) the engine default is stated and flagged.
    """

    external_ratings_allowed: bool = True
    """CRE20.17/20.42/20.44: jurisdiction allows external ratings (ECRA, Table 10)
    vs. not (SCRA for all banks, CRE20.44-20.46 for corporates)."""

    pse_option: int = 1
    """CRE20.11: Option 1 (sovereign rating, Table 3) or Option 2 (PSE rating,
    Table 4). The Framework sets no default; Option 1 is the engine default."""

    pse_treated_as_sovereign: bool = False
    """CRE20.12: certain domestic PSEs may be treated as sovereigns."""

    domestic_sovereign_rw: float | None = None
    """CRE20.8: lower RW for domestic-currency, domestically funded exposures to
    the sovereign of incorporation (and CRE22.84 for sovereign guarantees).
    None = discretion not exercised."""

    use_eca_scores: bool = False
    """CRE20.9: supervisors may recognise ECA country risk scores (Table 2)."""

    investment_grade_corporate_65: bool = True
    """CRE20.46: non-ratings jurisdictions *may* apply 65% to investment-grade
    corporates (only used when ``external_ratings_allowed`` is False)."""

    residential_re_treatment: RealEstateTreatment = RealEstateTreatment.WHOLE_LOAN
    """CRE20.82 (whole loan, base) or CRE20.83 (loan splitting, national alternative)."""

    commercial_re_treatment: RealEstateTreatment = RealEstateTreatment.WHOLE_LOAN
    """CRE20.85 (whole loan, base) or CRE20.86 (loan splitting, national alternative)."""

    cre_cash_flow_exemption: bool = False
    """CRE20.87 footnote 122: CF-dependent regulatory CRE may use CRE20.85-20.86
    where the 0.3% / 0.5% loss tests are met."""

    legislative_programme_equity_100: bool = False
    """CRE20.59: national supervisors *may* allow 100% for equity under national
    legislated programmes (aggregate cap 10% of Total capital)."""

    defaulted_50pct_discretion: bool = False
    """CRE20.106 footnote 129: national discretion to reduce the RW to 50% when
    specific provisions are no less than 50% of the outstanding amount."""

    equity_transition_year: int | None = None
    """CRE90.1 five-year linear phase-in from 1 January 2023. None = fully phased-in."""

    ilm_equal_one: bool = False
    """OPE25.11: national discretion to set ILM = 1 for all banks."""

    include_loss_data_bucket1: bool = False
    """OPE25.11: national discretion to include internal loss data for BI bucket 1."""

    output_floor_transitional_cap: bool = False
    """RBC90.2: national discretion to cap the floor-driven RWA increase at 25%
    of pre-floor RWA during the phase-in period."""

    ccr_cva_materiality_option: bool = False
    """MAR50.9: banks at or below EUR 100bn non-centrally-cleared notional may set
    CVA capital = 100% of CCR capital (not modelled through ``ba_cva_capital``)."""


DEFAULT_OPTIONS: Final[BCBSOptions] = BCBSOptions()

# =========================================================================
#  CRE20 -- sovereigns, PSEs, MDBs (pp. 181-185)
# =========================================================================

SOVEREIGN_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.7 Table 1 (p. 181-182)
    R.AAA_TO_AA_MINUS: 0.00,
    R.A_PLUS_TO_A_MINUS: 0.20,
    R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00,
    R.B_PLUS_TO_B_MINUS: 1.00,
    R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 1.00,
}

ECA_SCORE_RW: Final[dict[int, float]] = {
    # CRE20.9 Table 2 (p. 182): ECA risk scores 0-1 / 2 / 3 / 4-6 / 7
    0: 0.00, 1: 0.00, 2: 0.20, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.50,
}

SUPRANATIONAL_ZERO_RW: Final[float] = 0.0
"""CRE20.10: BIS, IMF, ECB, EU, ESM and EFSF may receive 0%."""

PSE_OPTION1_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.11 Table 3 (p. 183) -- based on the external rating of the sovereign
    R.AAA_TO_AA_MINUS: 0.20,
    R.A_PLUS_TO_A_MINUS: 0.50,
    R.BBB_PLUS_TO_BBB_MINUS: 1.00,
    R.BB_PLUS_TO_BB_MINUS: 1.00,
    R.B_PLUS_TO_B_MINUS: 1.00,
    R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 1.00,
}

PSE_OPTION2_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.11 Table 4 (p. 183) -- based on the external rating of the PSE
    R.AAA_TO_AA_MINUS: 0.20,
    R.A_PLUS_TO_A_MINUS: 0.50,
    R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00,
    R.B_PLUS_TO_B_MINUS: 1.00,
    R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 0.50,
}

MDB_ELIGIBLE_ZERO_RW: Final[float] = 0.0
"""CRE20.14: 0% for MDBs meeting the eligibility criteria (footnote 91 list)."""

MDB_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.15 Table 5 (p. 185) -- "base" risk weights, ratings jurisdictions
    R.AAA_TO_AA_MINUS: 0.20,
    R.A_PLUS_TO_A_MINUS: 0.30,
    R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00,
    R.B_PLUS_TO_B_MINUS: 1.00,
    R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 0.50,
}

MDB_NO_RATINGS_RW: Final[float] = 0.50
"""CRE20.15: non-ratings jurisdictions risk-weight non-0% MDBs at 50%."""

# =========================================================================
#  CRE20 -- banks (pp. 185-190)
# =========================================================================

BANK_ECRA_BASE_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.18 Table 6 (p. 186) -- "base" risk weight (no unrated column: SCRA applies)
    R.AAA_TO_AA_MINUS: 0.20,
    R.A_PLUS_TO_A_MINUS: 0.30,
    R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00,
    R.B_PLUS_TO_B_MINUS: 1.00,
    R.BELOW_B_MINUS: 1.50,
}

BANK_ECRA_SHORT_TERM_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.18 Table 6 (p. 186) -- risk weight for short-term exposures (CRE20.19)
    R.AAA_TO_AA_MINUS: 0.20,
    R.A_PLUS_TO_A_MINUS: 0.20,
    R.BBB_PLUS_TO_BBB_MINUS: 0.20,
    R.BB_PLUS_TO_BB_MINUS: 0.50,
    R.B_PLUS_TO_B_MINUS: 0.50,
    R.BELOW_B_MINUS: 1.50,
}

BANK_SCRA_BASE_RW: Final[dict[SCRAGrade, float]] = {
    # CRE20.21 Table 7 (p. 188) -- "base" risk weight
    SCRAGrade.A: 0.40,
    SCRAGrade.B: 0.75,
    SCRAGrade.C: 1.50,
}

BANK_SCRA_SHORT_TERM_RW: Final[dict[SCRAGrade, float]] = {
    # CRE20.21 Table 7 (p. 188) -- risk weight for short-term exposures (CRE20.31)
    SCRAGrade.A: 0.20,
    SCRAGrade.B: 0.50,
    SCRAGrade.C: 1.50,
}

BANK_SCRA_GRADE_A_ENHANCED_RW: Final[float] = 0.30
"""CRE20.21 footnote 98: 30% for Grade A banks with CET1 >= 14% and Tier 1 leverage >= 5%."""
SCRA_ENHANCED_CET1_THRESHOLD: Final[float] = 0.14
"""CRE20.21 footnote 98."""
SCRA_ENHANCED_LEVERAGE_THRESHOLD: Final[float] = 0.05
"""CRE20.21 footnote 98."""

BANK_SHORT_TERM_MAX_ORIGINAL_MATURITY_MONTHS: Final[float] = 3.0
"""CRE20.19 / CRE20.31: original maturity of three months or less."""
BANK_TRADE_SHORT_TERM_MAX_ORIGINAL_MATURITY_MONTHS: Final[float] = 6.0
"""CRE20.19 / CRE20.31: movement of goods across borders, six months or less."""
SCRA_SOVEREIGN_FLOOR_TRADE_EXEMPT_MAX_MONTHS: Final[float] = 12.0
"""CRE20.32: floor does not apply to short-term (maturity below one year) self-liquidating
trade-related contingent items arising from the movement of goods."""

# =========================================================================
#  CRE20 -- covered bonds (pp. 190-192)
# =========================================================================

COVERED_BOND_RATED_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.38 Table 8 (p. 191) -- issue-specific rating
    R.AAA_TO_AA_MINUS: 0.10,
    R.A_PLUS_TO_A_MINUS: 0.20,
    R.BBB_PLUS_TO_BBB_MINUS: 0.20,
    R.BB_PLUS_TO_BB_MINUS: 0.50,
    R.B_PLUS_TO_B_MINUS: 0.50,
    R.BELOW_B_MINUS: 1.00,
}

COVERED_BOND_UNRATED_RW: Final[dict[float, float]] = {
    # CRE20.38 Table 9 (p. 192) -- risk weight of the issuing bank -> covered-bond RW
    0.20: 0.10,
    0.30: 0.15,
    0.40: 0.20,
    0.50: 0.25,
    0.75: 0.35,
    1.00: 0.50,
    1.50: 1.00,
}

COVERED_BOND_RRE_MAX_LTV: Final[float] = 0.80
"""CRE20.34(2): cover-pool residential real estate LTV 80% or lower."""
COVERED_BOND_CRE_MAX_LTV: Final[float] = 0.60
"""CRE20.34(3): cover-pool commercial real estate LTV 60% or lower."""
COVERED_BOND_BANK_ASSET_CAP: Final[float] = 0.15
"""CRE20.34(4): claims on banks (RW <= 30%) cannot exceed 15% of issuance."""
COVERED_BOND_MIN_OVERCOLLATERALISATION: Final[float] = 0.10
"""CRE20.35: cover pool nominal must exceed outstanding by at least 10%."""

# =========================================================================
#  CRE20 -- corporates and specialised lending (pp. 193-197)
# =========================================================================

CORPORATE_RW: Final[dict[RatingBucket, float]] = {
    # CRE20.43 Table 10 (p. 194). Note the Table 10 buckets: "BB+ to BB-" 100%,
    # "Below BB-" 150% -- so B+ to B- and below B- both map to 150%.
    R.AAA_TO_AA_MINUS: 0.20,
    R.A_PLUS_TO_A_MINUS: 0.50,
    R.BBB_PLUS_TO_BBB_MINUS: 0.75,
    R.BB_PLUS_TO_BB_MINUS: 1.00,
    R.B_PLUS_TO_B_MINUS: 1.50,
    R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 1.00,
}

CORPORATE_NO_RATINGS_RW: Final[float] = 1.00
"""CRE20.44: non-ratings jurisdictions, all corporates except IG (CRE20.46) and SME (CRE20.47)."""
CORPORATE_INVESTMENT_GRADE_RW: Final[float] = 0.65
"""CRE20.46: 'investment grade' corporates in non-ratings jurisdictions."""
CORPORATE_SME_RW: Final[float] = 0.85
"""CRE20.47: unrated SMEs (ratings jurisdictions) and all SMEs (non-ratings jurisdictions)."""
SME_TURNOVER_THRESHOLD_EUR_M: Final[float] = 50.0
"""CRE20.47: consolidated group annual sales <= EUR 50 million (stated in EUR)."""

SL_OBJECT_COMMODITY_RW: Final[float] = 1.00
"""CRE20.51(1): object and commodities finance without issue-specific rating."""
SL_PROJECT_FINANCE_RW: Final[dict[PFPhase, float]] = {
    # CRE20.51(2) / CRE20.52 (p. 196)
    PFPhase.PRE_OPERATIONAL: 1.30,
    PFPhase.OPERATIONAL: 1.00,
    PFPhase.HIGH_QUALITY_OPERATIONAL: 0.80,
}

# =========================================================================
#  CRE20 -- subordinated debt and equity (pp. 197-200), CRE90.1 (p. 514)
# =========================================================================

SUBORDINATED_DEBT_RW: Final[float] = 1.50
"""CRE20.60: subordinated debt and capital instruments other than equities (incl. other TLAC)."""
EQUITY_GENERAL_RW: Final[float] = 2.50
"""CRE20.57: all other equity holdings."""
EQUITY_SPECULATIVE_UNLISTED_RW: Final[float] = 4.00
"""CRE20.57 / CRE20.58: speculative unlisted equity."""
EQUITY_LEGISLATIVE_PROGRAMME_RW: Final[float] = 1.00
"""CRE20.59: national legislated programmes (national discretion)."""
EQUITY_LEGISLATIVE_PROGRAMME_CAP_OF_TOTAL_CAPITAL: Final[float] = 0.10
"""CRE20.59: aggregate cap of 10% of Total capital."""
THRESHOLD_DEDUCTION_ITEM_RW: Final[float] = 2.50
"""CRE20.109: significant FI common shares, MSRs and DTAs not deducted under CAP30.32-30.33."""
COMMERCIAL_ENTITY_INDIVIDUAL_MATERIALITY: Final[float] = 0.15
"""CRE20.61(1): 15% of the bank's capital for individual investments."""
COMMERCIAL_ENTITY_AGGREGATE_MATERIALITY: Final[float] = 0.60
"""CRE20.61(2): 60% of the bank's capital for the aggregate."""
COMMERCIAL_ENTITY_EXCESS_RW: Final[float] = 12.50
"""CRE20.62: investments in excess of the materiality thresholds -> 1250%."""

EQUITY_PHASE_IN_START_YEAR: Final[int] = 2023
"""CRE90.1: five-year linear phase-in from 1 January 2023."""
EQUITY_PHASE_IN_START_RW: Final[float] = 1.00
"""CRE90.1: the applicable risk weight starts at 100%."""
EQUITY_PHASE_IN_STEP_GENERAL: Final[float] = 0.30
"""CRE90.1: +30 percentage points at the end of each year (other equity)."""
EQUITY_PHASE_IN_STEP_SPECULATIVE: Final[float] = 0.60
"""CRE90.1: +60 percentage points at the end of each year (speculative unlisted)."""
EQUITY_PHASE_IN_YEARS: Final[int] = 5
"""CRE90.1: until the end of Year 5."""

# =========================================================================
#  CRE20 -- retail (pp. 200-201)
# =========================================================================

RETAIL_REGULATORY_RW: Final[float] = 0.75
"""CRE20.68(1)."""
RETAIL_TRANSACTOR_RW: Final[float] = 0.45
"""CRE20.68(2)."""
RETAIL_OTHER_RW: Final[float] = 1.00
"""CRE20.68(3)."""
RETAIL_MAX_AGGREGATE_EXPOSURE_EUR_M: Final[float] = 1.0
"""CRE20.65(2): EUR 1 million per counterparty (stated in EUR)."""
RETAIL_GRANULARITY_LIMIT: Final[float] = 0.002
"""CRE20.65(3): 0.2% of the overall regulatory retail portfolio."""

# =========================================================================
#  CRE20 -- real estate (pp. 201-212)
# =========================================================================

LTVBands = tuple[tuple[float, float], ...]
"""(upper LTV bound inclusive, risk weight); the last bound is +inf."""

INF: Final[float] = float("inf")

RRE_WHOLE_LOAN_RW: Final[LTVBands] = (
    # CRE20.82 Table 11 (p. 208)
    (0.50, 0.20),
    (0.60, 0.25),
    (0.80, 0.30),
    (0.90, 0.40),
    (1.00, 0.50),
    (INF, 0.70),
)

RRE_CASH_FLOW_RW: Final[LTVBands] = (
    # CRE20.84 Table 12 (p. 209)
    (0.50, 0.30),
    (0.60, 0.35),
    (0.80, 0.45),
    (0.90, 0.60),
    (1.00, 0.75),
    (INF, 1.05),
)

CRE_WHOLE_LOAN_LTV_THRESHOLD: Final[float] = 0.60
"""CRE20.85 Table 13: LTV <= 60% -> min(60%, RW of counterparty); > 60% -> RW of counterparty."""
CRE_WHOLE_LOAN_CAP_RW: Final[float] = 0.60
"""CRE20.85 Table 13 / CRE20.86."""

CRE_CASH_FLOW_RW: Final[LTVBands] = (
    # CRE20.87 Table 14 (p. 210)
    (0.60, 0.70),
    (0.80, 0.90),
    (INF, 1.10),
)

RRE_LOAN_SPLIT_RW: Final[float] = 0.20
"""CRE20.83: 20% to the part of the exposure up to 55% of the property value."""
LOAN_SPLIT_PROPERTY_SHARE: Final[float] = 0.55
"""CRE20.83 / CRE20.86: 55% of the property value."""

JUNIOR_LIEN_MULTIPLIER: Final[float] = 1.25
"""CRE20.75 footnote 115: junior liens (whole loan): base RW x 1.25, not applied in the
lowest LTV bucket, capped at the RW applied when CRE20.71 is not met."""

OTHER_RE_INDIVIDUAL_RW: Final[float] = 0.75
"""CRE20.89(1): other RE (not CF-dependent), exposures to individuals."""
OTHER_RE_SME_RW: Final[float] = 0.85
"""CRE20.89(1): other RE (not CF-dependent), exposures to SMEs."""
OTHER_RE_CASH_FLOW_RW: Final[float] = 1.50
"""CRE20.89(2): other RE materially dependent on cash flows."""

LAND_ADC_RW: Final[float] = 1.50
"""CRE20.90."""
LAND_ADC_RESIDENTIAL_QUALIFYING_RW: Final[float] = 1.00
"""CRE20.91: residential ADC meeting the underwriting and pre-sale/equity-at-risk criteria."""

CRE_CF_EXEMPTION_LOSS_TEST_LTV60: Final[float] = 0.003
"""CRE20.87 fn 122(i): CRE losses up to 60% LTV must not exceed 0.3% of outstanding loans."""
CRE_CF_EXEMPTION_LOSS_TEST_OVERALL: Final[float] = 0.005
"""CRE20.87 fn 122(ii): overall CRE losses must not exceed 0.5% of outstanding loans."""

# =========================================================================
#  CRE20 -- currency mismatch, defaulted, other assets (pp. 212-217)
# =========================================================================

CURRENCY_MISMATCH_MULTIPLIER: Final[float] = 1.5
"""CRE20.92: unhedged retail and RRE exposures to individuals."""
CURRENCY_MISMATCH_RW_CAP: Final[float] = 1.50
"""CRE20.92: subject to a maximum risk weight of 150%."""
CURRENCY_MISMATCH_HEDGE_COVERAGE: Final[float] = 0.90
"""CRE20.93: hedges must cover at least 90% of the loan instalment."""

DEFAULTED_LOW_PROVISION_RW: Final[float] = 1.50
"""CRE20.106(1): specific provisions < 20% of outstanding."""
DEFAULTED_HIGH_PROVISION_RW: Final[float] = 1.00
"""CRE20.106(2): specific provisions >= 20% of outstanding."""
DEFAULTED_PROVISION_THRESHOLD: Final[float] = 0.20
"""CRE20.106."""
DEFAULTED_DISCRETION_RW: Final[float] = 0.50
"""CRE20.106 footnote 129: national discretion, provisions no less than 50%."""
DEFAULTED_DISCRETION_PROVISION_THRESHOLD: Final[float] = 0.50
"""CRE20.106 footnote 129."""
DEFAULTED_RRE_RW: Final[float] = 1.00
"""CRE20.107: defaulted RRE not materially dependent on cash flows."""
PAST_DUE_DAYS_DEFAULT: Final[int] = 90
"""CRE20.104: past due for more than 90 days."""

OTHER_ASSETS_RW: Final[float] = 1.00
"""CRE20.110: standard risk weight for all other assets."""
CASH_RW: Final[float] = 0.00
"""CRE20.110(1)(a): cash owned and held at the bank or in transit."""
GOLD_BULLION_RW: Final[float] = 0.00
"""CRE20.110(1)(b): gold bullion held at the bank or allocated, backed by bullion liabilities."""
CASH_ITEMS_IN_COLLECTION_RW: Final[float] = 0.20
"""CRE20.110(2)."""
NTH_TO_DEFAULT_RW_CAP: Final[float] = 12.50
"""CRE20.103: aggregated basket risk weights capped at 1250%."""

# =========================================================================
#  CRE20 -- off-balance-sheet CCFs (pp. 213-215)
# =========================================================================

CCF: Final[dict[OBSCategory, float]] = {
    OBSCategory.UNCONDITIONALLY_CANCELLABLE: 0.10,     # CRE20.100
    OBSCategory.COMMITMENT_OTHER: 0.40,                # CRE20.98 (regardless of maturity)
    OBSCategory.NIF_RUF: 0.50,                         # CRE20.96
    OBSCategory.TRANSACTION_RELATED_CONTINGENT: 0.50,  # CRE20.97
    OBSCategory.SHORT_TERM_TRADE_LC: 0.20,             # CRE20.99 (maturity below one year)
    OBSCategory.DIRECT_CREDIT_SUBSTITUTE: 1.00,        # CRE20.95(1)
    OBSCategory.SECURITIES_LENDING_COLLATERAL: 1.00,   # CRE20.95(3) (and repos, CRE20.95(2))
    OBSCategory.FORWARD_ASSET_PURCHASE: 1.00,          # CRE20.95(4)
    OBSCategory.OTHER_100: 1.00,                       # CRE20.95(5)
}

CCF_UNCLASSIFIED_DEFAULT: Final[float] = 1.00
"""CRE20.95(5): credit substitutes not explicitly included in any other category."""
SHORT_TERM_TRADE_LC_MAX_MONTHS: Final[float] = 12.0
"""CRE20.99: 'short term' means a maturity below one year."""
SHORT_TERM_TRADE_LC_LONG_DATED_CCF: Final[float] = 1.00
"""Trade LC with maturity of one year or more falls outside CRE20.99.
TODO: VERIFY -- the Framework does not say which CCF applies to a self-liquidating trade
LC of one year or more; the conservative 100% residual of CRE20.95(5) is used."""

# =========================================================================
#  CRE21 -- short-term ratings (p. 222-223)
# =========================================================================

SHORT_TERM_RATING_RW: Final[dict[ShortTermRating, float]] = {
    # CRE21.16 Table 15
    ShortTermRating.A1_P1: 0.20,
    ShortTermRating.A2_P2: 0.50,
    ShortTermRating.A3_P3: 1.00,
    ShortTermRating.OTHERS: 1.50,
}

# =========================================================================
#  CRE22 -- credit risk mitigation (pp. 225-249)
# =========================================================================

SIMPLE_APPROACH_RW_FLOOR: Final[float] = 0.20
"""CRE22.33: risk weight on the collateralised portion floored at 20%."""
SIMPLE_APPROACH_REPO_EXEMPT_RW: Final[float] = 0.10
"""CRE22.38: repos meeting CRE22.36 receive 10%."""
SIMPLE_APPROACH_CORE_MARKET_PARTICIPANT_RW: Final[float] = 0.00
"""CRE22.38: 0% if the counterparty is a core market participant."""
SIMPLE_APPROACH_SAME_CCY_CASH_RW: Final[float] = 0.00
"""CRE22.39: 0% for same-currency cash on deposit or 0%-RW sovereign/PSE securities
whose market value has been discounted by 20%."""
SIMPLE_APPROACH_SOVEREIGN_DISCOUNT: Final[float] = 0.20
"""CRE22.39(2)."""
SIMPLE_APPROACH_MIN_REVALUATION_MONTHS: Final[int] = 6
"""CRE22.33: marked to market and revalued at least every six months."""

# Comprehensive approach supervisory haircuts (10-business-day, daily MtM and remargining).
# Key structure: "<ISSUER>_<BAND>_<MATURITY>" with
#   ISSUER   SOV (sovereigns, incl. PSEs treated as sovereigns and 0% MDBs, CRE22.51(1)),
#            OTHER (other issuers, CRE22.51(2)), SEC (securitisation exposures, CRE22.51(3))
#   BAND     AAA_AA (AAA to AA-/A-1), A_BBB (A+ to BBB-/A-2/A-3/P-3 and unrated bank
#            securities per CRE22.34(3)(b)), BB (BB+ to BB-)
#   MATURITY LE1Y, 1Y_3Y, 3Y_5Y, 5Y_10Y, GT10Y
# The CRE22.49 table merges cells: sovereign ">1y <= 3y" and ">3y <= 5y" share one value,
# as do sovereign ">5y <= 10y" and ">10y"; securitisation likewise (d424 Table 14 confirms).

HAIRCUTS_RATINGS: Final[dict[str, float]] = {
    # CRE22.49 table (pp. 236-237), d424 para 163 Table 14
    "SOV_AAA_AA_LE1Y": 0.005, "SOV_AAA_AA_1Y_3Y": 0.02, "SOV_AAA_AA_3Y_5Y": 0.02,
    "SOV_AAA_AA_5Y_10Y": 0.04, "SOV_AAA_AA_GT10Y": 0.04,
    "OTHER_AAA_AA_LE1Y": 0.01, "OTHER_AAA_AA_1Y_3Y": 0.03, "OTHER_AAA_AA_3Y_5Y": 0.04,
    "OTHER_AAA_AA_5Y_10Y": 0.06, "OTHER_AAA_AA_GT10Y": 0.12,
    "SEC_AAA_AA_LE1Y": 0.02, "SEC_AAA_AA_1Y_3Y": 0.08, "SEC_AAA_AA_3Y_5Y": 0.08,
    "SEC_AAA_AA_5Y_10Y": 0.16, "SEC_AAA_AA_GT10Y": 0.16,
    "SOV_A_BBB_LE1Y": 0.01, "SOV_A_BBB_1Y_3Y": 0.03, "SOV_A_BBB_3Y_5Y": 0.03,
    "SOV_A_BBB_5Y_10Y": 0.06, "SOV_A_BBB_GT10Y": 0.06,
    "OTHER_A_BBB_LE1Y": 0.02, "OTHER_A_BBB_1Y_3Y": 0.04, "OTHER_A_BBB_3Y_5Y": 0.06,
    "OTHER_A_BBB_5Y_10Y": 0.12, "OTHER_A_BBB_GT10Y": 0.20,
    "SEC_A_BBB_LE1Y": 0.04, "SEC_A_BBB_1Y_3Y": 0.12, "SEC_A_BBB_3Y_5Y": 0.12,
    "SEC_A_BBB_5Y_10Y": 0.24, "SEC_A_BBB_GT10Y": 0.24,
    # BB+ to BB-: sovereigns 15% for all maturities; other issuers / securitisation not eligible
    "SOV_BB_LE1Y": 0.15, "SOV_BB_1Y_3Y": 0.15, "SOV_BB_3Y_5Y": 0.15,
    "SOV_BB_5Y_10Y": 0.15, "SOV_BB_GT10Y": 0.15,
    "MAIN_INDEX_EQUITY": 0.20,      # main index equities (incl. convertible bonds)
    "GOLD": 0.20,                   # gold
    "OTHER_LISTED_EQUITY": 0.30,    # other equities / convertibles listed on a recognised exchange
    "CASH": 0.00,                   # cash in the same currency (CRE22.34(1))
}

HAIRCUTS_NO_RATINGS: Final[dict[str, float]] = {
    # CRE22.50 table (pp. 237-238), d424 para 164 Table 15.
    # Sovereign issuers by issuer risk weight: NR_SOV0 (0%), NR_SOV20_50 (20% or 50%),
    # NR_SOV100 (100%); NR_IG (other investment-grade non-securitisation, CRE22.34(4)(c));
    # NR_SEC (senior securitisation with SA RW < 100%).
    "NR_SOV0_LE1Y": 0.005, "NR_SOV0_1Y_3Y": 0.02, "NR_SOV0_3Y_5Y": 0.02,
    "NR_SOV0_5Y_10Y": 0.04, "NR_SOV0_GT10Y": 0.04,
    "NR_SOV20_50_LE1Y": 0.01, "NR_SOV20_50_1Y_3Y": 0.03, "NR_SOV20_50_3Y_5Y": 0.03,
    "NR_SOV20_50_5Y_10Y": 0.06, "NR_SOV20_50_GT10Y": 0.06,
    "NR_SOV100_LE1Y": 0.15, "NR_SOV100_1Y_3Y": 0.15, "NR_SOV100_3Y_5Y": 0.15,
    "NR_SOV100_5Y_10Y": 0.15, "NR_SOV100_GT10Y": 0.15,
    "NR_IG_LE1Y": 0.02, "NR_IG_1Y_3Y": 0.04, "NR_IG_3Y_5Y": 0.06,
    "NR_IG_5Y_10Y": 0.12, "NR_IG_GT10Y": 0.20,
    "NR_SEC_LE1Y": 0.04, "NR_SEC_1Y_3Y": 0.12, "NR_SEC_3Y_5Y": 0.12,
    "NR_SEC_5Y_10Y": 0.24, "NR_SEC_GT10Y": 0.24,
    "MAIN_INDEX_EQUITY": 0.20,
    "GOLD": 0.20,
    "OTHER_LISTED_EQUITY": 0.30,
    "CASH": 0.00,
    "OTHER_EXPOSURE_TYPES": 0.30,
}

HAIRCUT_FX: Final[float] = 0.08
"""CRE22.52 (collateral) and CRE22.83 (guarantees/credit derivatives): 8%, 10-business-day."""
HAIRCUT_NON_ELIGIBLE_SFT: Final[float] = 0.30
"""CRE22.54: SFTs lending/posting non-eligible instruments: 30% on the exposure."""
HAIRCUT_BASE_HOLDING_PERIOD_DAYS: Final[int] = 10
"""CRE22.49-22.50 / CRE22.59: the tables assume a 10-business-day holding period."""

MIN_HOLDING_PERIOD_DAYS: Final[dict[str, int]] = {
    # CRE22.57 table
    "REPO_STYLE": 5,
    "OTHER_CAPITAL_MARKET": 10,
    "SECURED_LENDING": 20,
}
HOLDING_PERIOD_LARGE_NETTING_SET_DAYS: Final[int] = 20
"""CRE22.58(1)/(2): > 5,000 trades or illiquid collateral -> 20 business days."""
LARGE_NETTING_SET_TRADES: Final[int] = 5000
"""CRE22.58(1)."""

MATURITY_MISMATCH_OFFSET_YEARS: Final[float] = 0.25
"""CRE22.13 / d424 para 129: Pa = P x (t - 0.25) / (T - 0.25)."""
MATURITY_MISMATCH_T_CAP_YEARS: Final[float] = 5.0
"""CRE22.13: T = min(five years, residual maturity of the exposure)."""
MATURITY_MISMATCH_MIN_ORIGINAL_YEARS: Final[float] = 1.0
"""CRE22.12: protection original maturity >= one year."""
MATURITY_MISMATCH_MIN_RESIDUAL_YEARS: Final[float] = 0.25
"""CRE22.12: protection residual maturity >= three months."""

CDS_NO_RESTRUCTURING_RECOGNITION: Final[float] = 0.60
"""CRE22.75: 60% recognition where restructuring is not a covered credit event."""
GUARANTEE_MATERIALITY_THRESHOLD_RW: Final[float] = 12.50
"""CRE22.79(2): portion below a materiality threshold -> 1250%."""

# =========================================================================
#  CRE52 -- SA-CCR (pp. 434-462)
# =========================================================================

SACCR_ALPHA: Final[float] = 1.4
"""CRE52.1 (and CRE99.125 worked example: 1.4 x (RC + AddOn)). No alpha exemption
for non-financial or pension counterparties exists in the Basel Framework."""
SACCR_MULTIPLIER_FLOOR: Final[float] = 0.05
"""CRE52.22-52.23: multiplier floored at 5%.
The CRE52.23 equation is an image in the Framework text; the transcription
multiplier = min{1; Floor + (1 - Floor) x exp[(V - C) / (2 x (1 - Floor) x AddOn)]}
is cross-checked against CRR Article 278(3) (identical structure, Floor_m = 5%).
TODO: VERIFY -- equation not machine-readable in the Basel Framework extraction."""
SACCR_MARGINED_MF_SCALAR: Final[float] = 1.5
"""CRE52.52 (the '3/2 multiplier' named in CRE52.2 FAQ1): MF = 3/2 x sqrt(MPOR / 1 year)."""
SACCR_BUSINESS_DAYS_PER_YEAR: Final[int] = 250
"""CRE52.49 / CRE52.53: standard market convention, 250 business days."""
SACCR_MIN_MATURITY_BUSINESS_DAYS: Final[int] = 10
"""CRE52.48-52.49: Mi floored at 10 business days."""
SACCR_MPOR_FLOOR_DAILY_DAYS: Final[int] = 10
"""CRE52.50(1): non-centrally-cleared, daily margin agreements."""
SACCR_MPOR_FLOOR_LARGE_DAYS: Final[int] = 20
"""CRE52.51(1)-(2): > 5000 transactions, illiquid collateral or hard-to-replace OTC derivatives."""
SACCR_BASIS_SF_SCALAR: Final[float] = 0.5
"""CRE52.73: basis transaction hedging sets."""
SACCR_VOLATILITY_SF_SCALAR: Final[float] = 5.0
"""CRE52.73: volatility transaction hedging sets."""

SACCR_SUPERVISORY_PARAMS: Final[dict[str, tuple[float, float | None, float]]] = {
    # CRE52.72 Table 2: (supervisory factor, correlation, supervisory option volatility)
    "IR": (0.0050, None, 0.50),
    "FX": (0.040, None, 0.15),
    "CREDIT_SN_AAA": (0.0038, 0.50, 1.00),
    "CREDIT_SN_AA": (0.0038, 0.50, 1.00),
    "CREDIT_SN_A": (0.0042, 0.50, 1.00),
    "CREDIT_SN_BBB": (0.0054, 0.50, 1.00),
    "CREDIT_SN_BB": (0.0106, 0.50, 1.00),
    "CREDIT_SN_B": (0.016, 0.50, 1.00),
    "CREDIT_SN_CCC": (0.060, 0.50, 1.00),
    "CREDIT_INDEX_IG": (0.0038, 0.80, 0.80),
    "CREDIT_INDEX_SG": (0.0106, 0.80, 0.80),
    "EQUITY_SN": (0.32, 0.50, 1.20),
    "EQUITY_INDEX": (0.20, 0.80, 0.75),
    "COMMODITY_ELECTRICITY": (0.40, 0.40, 1.50),
    "COMMODITY_OIL_GAS": (0.18, 0.40, 0.70),
    "COMMODITY_METALS": (0.18, 0.40, 0.70),
    "COMMODITY_AGRICULTURAL": (0.18, 0.40, 0.70),
    "COMMODITY_OTHER": (0.18, 0.40, 0.70),
}

# =========================================================================
#  MAR50 -- BA-CVA (pp. 722-729)
# =========================================================================

BA_CVA_RHO: Final[float] = 0.50
"""MAR50.14(2): supervisory correlation parameter."""
BA_CVA_DISCOUNT_SCALAR: Final[float] = 0.65
"""MAR50.14 / MAR50.20: DS_BA-CVA = 0.65 (not in d424; added by the July 2020 revision)."""
BA_CVA_BETA: Final[float] = 0.25
"""MAR50.20: floor on hedging recognition, K_full = beta K_reduced + (1 - beta) K_hedged."""
BA_CVA_ALPHA: Final[float] = 1.4
"""MAR50.15(5)."""
BA_CVA_DF_RATE: Final[float] = 0.05
"""MAR50.15 footnote 357: DF = (1 - exp(-0.05 M)) / (0.05 M) for non-IMM banks."""
BA_CVA_INDEX_RW_SCALAR: Final[float] = 0.7
"""MAR50.24(4): index hedge RW multiplied by 0.7."""
CVA_MATERIALITY_THRESHOLD_EUR_M: Final[float] = 100_000.0
"""MAR50.9(1): aggregate non-centrally-cleared notional <= EUR 100 billion (stated in EUR)."""
CVA_MATERIALITY_CCR_SHARE: Final[float] = 1.0
"""MAR50.9(2): CVA capital = 100% of CCR capital requirement."""
CVA_RWA_MULTIPLIER: Final[float] = 12.5
"""MAR50.1."""

BA_CVA_SECTORS: Final[tuple[str, ...]] = (
    "SOVEREIGN", "LOCAL_GOVERNMENT", "FINANCIAL", "BASIC_MATERIALS",
    "CONSUMER", "TECHNOLOGY", "HEALTH_CARE", "OTHER",
)

BA_CVA_RW: Final[dict[tuple[str, str], float]] = {
    # MAR50.16 Table 1 (p. 727): (sector, "IG" | "HY_NR")
    ("SOVEREIGN", "IG"): 0.005, ("SOVEREIGN", "HY_NR"): 0.020,
    # sovereigns including central banks and MDBs (d424 had 3.0% for HY/NR)
    ("LOCAL_GOVERNMENT", "IG"): 0.010, ("LOCAL_GOVERNMENT", "HY_NR"): 0.040,
    # local government, government-backed non-financials, education, public administration
    ("FINANCIAL", "IG"): 0.050, ("FINANCIAL", "HY_NR"): 0.120,
    # financials including government-backed financials
    ("BASIC_MATERIALS", "IG"): 0.030, ("BASIC_MATERIALS", "HY_NR"): 0.070,
    # basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying
    ("CONSUMER", "IG"): 0.030, ("CONSUMER", "HY_NR"): 0.085,
    # consumer goods and services, transportation and storage, administrative/support services
    ("TECHNOLOGY", "IG"): 0.020, ("TECHNOLOGY", "HY_NR"): 0.055,
    # technology, telecommunications
    ("HEALTH_CARE", "IG"): 0.015, ("HEALTH_CARE", "HY_NR"): 0.050,
    # health care, utilities, professional and technical activities
    ("OTHER", "IG"): 0.050, ("OTHER", "HY_NR"): 0.120,
}

BA_CVA_HEDGE_CORRELATION: Final[dict[str, float]] = {
    # MAR50.26 Table 2
    "DIRECT": 1.00,          # references counterparty c directly
    "LEGAL": 0.80,           # has legal relation with counterparty c
    "SECTOR_REGION": 0.50,   # shares sector and region with counterparty c
}

# =========================================================================
#  OPE25 -- operational risk standardised approach (pp. 769-772)
# =========================================================================

OPE_ILDC_IEA_CAP: Final[float] = 0.0225
"""OPE25.5 / d424 OpRisk para 6: ILDC = min(|II - IE|, 2.25% x IEA) + DI."""
OPE_BI_BUCKETS_EUR_M: Final[tuple[tuple[float, float], ...]] = (
    # OPE25.7 Table 1: (upper bound of the BI range in EUR millions, marginal coefficient)
    (1_000.0, 0.12),
    (30_000.0, 0.15),
    (INF, 0.18),
)
OPE_LC_MULTIPLE: Final[float] = 15.0
"""OPE25.8: LC = 15 x average annual operational risk losses over the previous 10 years."""
OPE_ILM_EXPONENT: Final[float] = 0.8
"""OPE25.8 / d424 OpRisk para 9: ILM = ln(exp(1) - 1 + (LC / BIC)^0.8)."""
OPE_LOSS_YEARS: Final[int] = 10
"""OPE25.10 / OPE25.15: 10-year observation period."""
OPE_MIN_LOSS_YEARS: Final[int] = 5
"""OPE25.10: minimum of five years during transition; below five -> BIC only."""
OPE_LOSS_THRESHOLD_EUR: Final[float] = 20_000.0
"""OPE25.18: minimum loss-event threshold EUR 20,000 (EUR, stated)."""
OPE_LOSS_THRESHOLD_DISCRETION_EUR: Final[float] = 100_000.0
"""OPE25.18: national discretion EUR 100,000 for buckets 2 and 3."""
OPE_RWA_MULTIPLIER: Final[float] = 12.5
"""OPE25.2: RWA = 12.5 x ORC."""

# =========================================================================
#  RBC20 / RBC90 -- minimums and output floor (pp. 138-177)
# =========================================================================

CET1_MINIMUM: Final[float] = 0.045
"""RBC20.1(1)."""
TIER1_MINIMUM: Final[float] = 0.06
"""RBC20.1(2)."""
TOTAL_CAPITAL_MINIMUM: Final[float] = 0.08
"""RBC20.1(3)."""

OUTPUT_FLOOR_FULL: Final[float] = 0.725
"""RBC20.4(2): 72.5% of standardised RWA."""
OUTPUT_FLOOR_SCHEDULE: Final[dict[int, float]] = {
    # RBC90.1 Table 1 (p. 177). d424 had the same calibration one year earlier (2022-2027).
    2023: 0.50,
    2024: 0.55,
    2025: 0.60,
    2026: 0.65,
    2027: 0.70,
    2028: 0.725,
}
OUTPUT_FLOOR_START_YEAR: Final[int] = 2023
"""RBC90.1: implemented as of 1 January 2023."""
OUTPUT_FLOOR_TRANSITIONAL_CAP: Final[float] = 0.25
"""RBC90.2: cap on the floor-driven increase, 25% of pre-floor RWA (phase-in period only)."""

# =========================================================================
#  RBC30 / RBC40 / SCO40 -- buffers (pp. 156-175, 15-24)
# =========================================================================

CAPITAL_CONSERVATION_BUFFER: Final[float] = 0.025
"""RBC30.2."""
CCYB_MAX_RECIPROCITY: Final[float] = 0.025
"""RBC30.9 / RBC30.12: CCyB varies between zero and 2.5% (reciprocity maximum,
footnote 78: national add-ons above 2.5% are not reciprocated)."""

CONSERVATION_RATIOS_BY_QUARTILE: Final[tuple[float, ...]] = (1.00, 0.80, 0.60, 0.40, 0.00)
"""RBC30.4 / RBC30.17: minimum capital conservation ratios (share of earnings retained)
for the 1st-4th quartiles of the buffer and above the buffer."""

GSIB_HLA_BY_BUCKET: Final[dict[int, float]] = {
    # RBC40.4 Table 1 (p. 170)
    1: 0.010,
    2: 0.015,
    3: 0.020,
    4: 0.025,
    5: 0.035,
}
GSIB_SCORE_RANGES_BPS: Final[dict[int, tuple[int, int]]] = {
    # RBC40.4 Table 1 score ranges
    1: (130, 229),
    2: (230, 329),
    3: (330, 429),
    4: (430, 529),
    5: (530, 629),
}
GSIB_CUTOFF_SCORE_BPS: Final[int] = 130
"""SCO40.21 / RBC40.4: cutoff score for G-SIB designation."""
GSIB_BUCKET_WIDTH_BPS: Final[int] = 100
"""SCO40.21 / RBC40.4: each bucket spans 100 bps."""
GSIB_NEW_BUCKET_INCREMENT: Final[float] = 0.01
"""RBC40.5: new buckets above bucket 5 increase in 1% increments (bucket 6 = 4.5%)."""

LEVERAGE_MINIMUM: Final[float] = 0.03
"""LEV20.7."""
GSIB_LEVERAGE_BUFFER_SHARE: Final[float] = 0.50
"""LEV40.2: leverage ratio buffer = 50% of the G-SIB higher loss-absorbency requirement."""
