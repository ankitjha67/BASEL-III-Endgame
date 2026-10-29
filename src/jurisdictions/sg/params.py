"""Regulatory parameters for Singapore -- MAS Notice 637 (version effective 1 January 2026).

Every constant below is transcribed from the text of MAS Notice 637, "Notice on
Risk Based Capital Adequacy Requirements for Banks Incorporated in Singapore"
(20 September 2023, last revised 9 October 2025). Each value carries the
paragraph / table that produced it; page numbers are the Notice's own page
footers (e.g. "p. 7-41"). The verbatim transcription is kept in
``docs/jurisdictions/SG_parameter_reference.md``.

Currency: MAS states its absolute thresholds in Singapore dollars (S$). The
engine is currency-agnostic; the SG regime expects inputs already converted
to SGD millions, so thresholds below are expressed in S$ millions.

References:
    - MAS Notice 637 Part IV (paras 4.1.5-4.1.32, 4.2.2), Part V (Table 5-3),
      Part VII Division 3 (paras 7.3.1-7.3.125, Tables 7-1 to 7-22),
      Annex 7B (Table 7B-1), Annex 7D (SA-CCR, Table 7D-1), Annex 7H
      (Sections 6-7), Annex 7J (Tables 7J-1 to 7J-3), Annex 7M (Tables
      7M-1, 7M-2), Part VIII Division 5 (paras 8.5.10-8.5.18, Tables 8-26,
      8-27), Part IX (paras 9.1.2-9.1.21)
"""

from __future__ import annotations

from datetime import date
from typing import Final

from src.jurisdictions.base import OBSCategory, RatingBucket, ShortTermRating

# =========================================================================
#  Credit quality grades -- Annex 7M (p. 7-271)
# =========================================================================

CQS_BY_RATING: Final[dict[RatingBucket, int | None]] = {
    # Table 7M-1: grade 1 = AAA..AA-, 2 = A+..A-, 3 = BBB+..BBB-, 4 = BB+..BB-,
    # 5 = B+..B-, 6 = CCC+ and below (Fitch / Moody's / S&P).
    RatingBucket.AAA_TO_AA_MINUS: 1,
    RatingBucket.A_PLUS_TO_A_MINUS: 2,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS: 3,
    RatingBucket.BB_PLUS_TO_BB_MINUS: 4,
    RatingBucket.B_PLUS_TO_B_MINUS: 5,
    RatingBucket.BELOW_B_MINUS: 6,
    RatingBucket.UNRATED: None,
}
"""Table 7M-1 -- Credit Quality Grades for SA(CR) Exposures (Annex 7M, p. 7-271)."""

ST_GRADE_BY_RATING: Final[dict[ShortTermRating, str]] = {
    # Table 7M-2: I = F-1/P-1/A-1 (incl. A-1+ and A-1-, para 1.1(a)), II = F-2/P-2/A-2,
    # III = F-3/P-3/A-3, IV = Others (all non-prime and B or C ratings, para 1.1(b)).
    ShortTermRating.A1_P1: "I",
    ShortTermRating.A2_P2: "II",
    ShortTermRating.A3_P3: "III",
    ShortTermRating.OTHERS: "IV",
}
"""Table 7M-2 -- Credit Quality Grades for Short-term SA(CR) Exposures (Annex 7M, p. 7-271)."""

# Key ``None`` = "Unrated" column in the tables below.
RWTable = dict[int | None, float]

# =========================================================================
#  SA(CR) risk weights -- Part VII Division 3 Sub-division 3
# =========================================================================

CASH_ITEM_RW: Final[float] = 0.0
"""Para 7.3.40 (p. 7-42): cash items (incl. gold bullion, 7.3.1(a)(ii)) 0%."""
CASH_EQUIVALENT_IN_COLLECTION_RW: Final[float] = 0.20
"""Para 7.3.41 (p. 7-42): cheques, drafts and other items drawn on other banks ... 20%."""

SOVEREIGN_RW: Final[RWTable] = {1: 0.0, 2: 0.20, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.50, None: 1.00}
"""Table 7-1 (para 7.3.42, p. 7-42): central government and central bank asset class."""
SG_GOVERNMENT_SGD_RW: Final[float] = 0.0
"""Para 7.3.43 (p. 7-42): Singapore Government / the Authority, SGD-denominated and SGD-funded."""
SUPRANATIONAL_ZERO_RW: Final[float] = 0.0
"""Para 7.3.46 (p. 7-42): BIS, IMF, ECB, EU, ESM, EFSF -- 0%."""

PSE_RW: Final[RWTable] = {1: 0.20, 2: 0.50, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.50, None: 0.50}
"""Table 7-2 (para 7.3.47, p. 7-42): PSE asset class."""
PSE_SOVEREIGN_TREATED_RW: Final[dict[int, RWTable]] = {
    1: {1: 0.0, 2: 0.0, 3: 0.0, 4: 1.00, 5: 1.00, 6: 1.50, None: 0.0},
    2: {1: 0.20, 2: 0.20, 3: 0.20, 4: 1.00, 5: 1.00, 6: 1.50, None: 0.20},
}
"""Table 7-3 (para 7.3.48, p. 7-43): PSEs treated as the central government, keyed by the
central government's credit quality grade (1 or 2), then by the PSE's grade."""

MDB_RW: Final[RWTable] = {1: 0.20, 2: 0.30, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.50, None: 0.50}
"""Table 7-4 (para 7.3.50, p. 7-43): MDB asset class."""
QUALIFYING_MDB_RW: Final[float] = 0.0
"""Para 7.3.51 (p. 7-43): qualifying MDBs (Annex 7O list) -- 0%."""

BANK_RATED_RW: Final[dict[int, float]] = {1: 0.20, 2: 0.30, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.50}
"""Table 7-5 row 1 (para 7.3.52, p. 7-44): bank asset class, rated."""
BANK_RATED_SHORT_TERM_RW: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.20,
    3: 0.20,
    4: 0.50,
    5: 0.50,
    6: 1.50,
}
"""Table 7-5 row 2 (para 7.3.52, p. 7-44): rated bank short-term exposures."""
BANK_SHORT_TERM_MAX_ORIGINAL_MONTHS: Final[float] = 3.0
"""Para 7.3.52(a) / 7.3.58(a): short-term = original maturity of 3 months or less."""
BANK_TRADE_SHORT_TERM_MAX_ORIGINAL_MONTHS: Final[float] = 6.0
"""Para 7.3.52(b) / 7.3.58(b): movement of goods across borders, original maturity <= 6 months."""

ST_ISSUE_RW: Final[dict[str, float]] = {"I": 0.20, "II": 0.50, "III": 1.00, "IV": 1.50}
"""Tables 7-6 (bank, p. 7-44), 7-11 (general corporate, p. 7-49) and 7-13 (corporate SME,
p. 7-50): short-term exposures with issue-specific external credit assessments. The three
tables are identical."""

BANK_SCRA_RW: Final[dict[str, float]] = {"A": 0.40, "B": 0.75, "C": 1.50}
"""Table 7-7 row 1 (para 7.3.58, p. 7-46): bank asset class, unrated (assessment grades)."""
BANK_SCRA_SHORT_TERM_RW: Final[dict[str, float]] = {"A": 0.20, "B": 0.50, "C": 1.50}
"""Table 7-7 row 2 (para 7.3.58, p. 7-46): unrated bank short-term exposures."""
BANK_SCRA_GRADE_A_ENHANCED_RW: Final[float] = 0.30
"""Para 7.3.59 (p. 7-46): 30% instead of 40% where CET1 ratio >= 14% and Tier 1 leverage >= 5%."""
SCRA_A_ENHANCED_CET1: Final[float] = 0.14
"""Para 7.3.59(a): counterparty CET1 ratio meets or exceeds 14%."""
SCRA_A_ENHANCED_LEVERAGE: Final[float] = 0.05
"""Para 7.3.59(b): counterparty Tier 1 leverage ratio meets or exceeds 5%."""
BANK_IMPLICIT_SUPPORT_RATINGS_UNTIL: Final[date] = date(2028, 12, 31)
"""Para 7.3.53 (p. 7-44): ratings incorporating implicit government support usable up to
31 December 2028; from 1 January 2029 they must not be used (except public banks)."""

COVERED_BOND_RATED_RW: Final[dict[int, float]] = {
    1: 0.10,
    2: 0.20,
    3: 0.20,
    4: 0.50,
    5: 0.50,
    6: 1.00,
}
"""Table 7-8 (para 7.3.64, p. 7-48): covered bonds with issue-specific external assessments."""
COVERED_BOND_UNRATED_RW: Final[dict[float, float]] = {
    0.20: 0.10,
    0.30: 0.15,
    0.40: 0.20,
    0.50: 0.25,
    0.75: 0.35,
    1.00: 0.50,
    1.50: 1.00,
}
"""Table 7-9 (para 7.3.65, p. 7-48): covered bonds without issue-specific assessments, keyed by
the risk weight of the issuing bank (Table 7-5 or Table 7-7)."""

CORPORATE_RW: Final[RWTable] = {1: 0.20, 2: 0.50, 3: 0.75, 4: 1.00, 5: 1.50, 6: 1.50, None: 1.00}
"""Table 7-10 (para 7.3.67, p. 7-49): general corporate asset sub-class."""
CORPORATE_SME_RW: Final[RWTable] = {
    1: 0.20,
    2: 0.50,
    3: 0.75,
    4: 1.00,
    5: 1.50,
    6: 1.50,
    None: 0.85,
}
"""Table 7-12 (para 7.3.71, p. 7-50): corporate SME asset sub-class."""
SME_REVENUE_THRESHOLD_SGD_M: Final[float] = 100.0
"""Para 7.3.4 (p. 7-28): small business = reported annual (consolidated group) revenue
<= S$100 million."""
CORPORATE_SHORT_TERM_MAX_ORIGINAL_MONTHS: Final[float] = 12.0
# TODO: VERIFY -- paras 7.3.69(a) / 7.3.73(a) refer to "unrated short-term" corporate exposures
# without defining short-term; one-year original maturity used (only drives the 100% floor).
UNRATED_ST_FLOOR_IF_ISSUE_50_OR_100: Final[float] = 1.00
"""Paras 7.3.55(a) / 7.3.69(a) / 7.3.73(a): unrated short-term exposure to an entity whose rated
short-term issue attracts 50% or 100% -- not lower than 100%."""
UNRATED_FLOOR_IF_ISSUE_150: Final[float] = 1.50
"""Paras 7.3.55(b) / 7.3.69(b) / 7.3.73(b): any unrated exposure to an entity whose rated
short-term issue attracts 150% -- 150% (unless recognised CRM)."""

SL_RATED_RW: Final[dict[int, float]] = {1: 0.20, 2: 0.50, 3: 0.75, 4: 1.00, 5: 1.50, 6: 1.50}
"""Table 7-14 (para 7.3.75, p. 7-50): specialised lending, issue-specific assessments only."""
SL_PF_HIGH_QUALITY_OPERATIONAL_RW: Final[float] = 0.80
"""Table 7-15 row 1 (para 7.3.76, p. 7-51): PF operational phase and high quality (7.3.77(b))."""
SL_PF_OPERATIONAL_RW: Final[float] = 1.00
"""Table 7-15 row 2: PF operational phase, not high quality."""
SL_PF_OTHER_RW: Final[float] = 1.30
"""Table 7-15 row 3: any other project finance exposure (incl. pre-operational)."""
SL_OF_CF_RW: Final[float] = 1.00
"""Table 7-15 row 4: object finance and commodities finance exposures."""

SPECULATIVE_UNLISTED_EQUITY_RW: Final[float] = 4.00
"""Para 7.3.80(a) (p. 7-53): speculative unlisted equity exposures (7.3.81) -- 400%."""
OTHER_EQUITY_RW: Final[float] = 2.50
"""Para 7.3.80(b): all other equity exposures -- 250%."""
SUBORDINATED_DEBT_RW: Final[float] = 1.50
"""Para 7.3.80(c): subordinated debt and regulatory capital instruments other than equities."""
MAJOR_STAKE_EXCESS_RW: Final[float] = 12.50
"""Para 7.3.82 (p. 7-53): 1250% to the major-stake (non-FI) excess portions."""
MAJOR_STAKE_INDIVIDUAL_LIMIT: Final[float] = 0.15
"""Para 7.3.82(a): individual major-stake exposure portion above 15% of Eligible Total Capital."""
MAJOR_STAKE_AGGREGATE_LIMIT: Final[float] = 0.60
"""Para 7.3.82(b): aggregate major-stake exposures above 60% of Eligible Total Capital."""

EQUITY_PHASE_IN: Final[tuple[tuple[date, float, float], ...]] = (
    # (effective from, speculative unlisted RW, all other equity RW)
    (date(2024, 7, 1), 1.60, 1.30),
    (date(2025, 12, 31), 2.20, 1.60),
    (date(2026, 12, 31), 2.80, 1.90),
    (date(2027, 12, 31), 3.40, 2.20),
    (date(2028, 12, 31), 4.00, 2.50),
)
"""Table 7-16 (para 7.3.85, p. 7-55): phase-in of equity risk weights from 1 July 2024."""

RETAIL_TRANSACTOR_RW: Final[float] = 0.45
"""Table 7-17 (para 7.3.86, p. 7-55): regulatory retail transactor."""
RETAIL_NON_TRANSACTOR_RW: Final[float] = 0.75
"""Table 7-17: regulatory retail non-transactor."""
OTHER_RETAIL_RW: Final[float] = 1.00
"""Para 7.3.87 (p. 7-55): other retail asset class."""
REGULATORY_RETAIL_MAX_SGD_M: Final[float] = 2.0
"""Para 7.3.1(i)(iii) (p. 7-25): total exposure to obligor group not more than S$2 million."""
REGULATORY_RETAIL_GRANULARITY: Final[float] = 0.002
"""Para 7.3.1(i)(iv): total exposure to obligor <= 0.2% of the regulatory retail pool."""

ADC_RW: Final[float] = 1.50
"""Para 7.3.88 (p. 7-55): ADC asset sub-class -- 150%."""
ADC_RRE_QUALIFYING_RW: Final[float] = 1.00
"""Para 7.3.89 (p. 7-55): ADC secured by RRE meeting 7.3.17(f) underwriting and LTV <= 80%."""
ADC_RRE_MAX_LTV: Final[float] = 0.80
"""Para 7.3.89(b): LTV (on gross development value) <= 80%."""

RRE_LTV_UPPER_BOUNDS: Final[tuple[float, ...]] = (0.50, 0.60, 0.80, 0.90, 1.00)
"""Tables 7-18 / 7-19 LTV band upper bounds (inclusive); last band is LTV > 100%."""
RRE_GENERAL_RW: Final[tuple[float, ...]] = (0.20, 0.25, 0.30, 0.40, 0.50, 0.70)
"""Table 7-18 (para 7.3.91, p. 7-56): regulatory RRE not materially dependent on cash flows."""
RRE_CASH_FLOW_RW: Final[tuple[float, ...]] = (0.30, 0.35, 0.45, 0.60, 0.75, 1.05)
"""Table 7-19 (para 7.3.92, p. 7-57): regulatory RRE materially dependent on cash flows."""

CRE_GENERAL_LTV_THRESHOLD: Final[float] = 0.60
"""Table 7-20 (para 7.3.93, p. 7-57): LTV <= 60% vs > 60%."""
CRE_GENERAL_LOW_LTV_CAP: Final[float] = 0.60
"""Table 7-20: LTV <= 60% -> min(60%, risk weight of counterparty)."""
CRE_CASH_FLOW_LTV_UPPER_BOUNDS: Final[tuple[float, ...]] = (0.60, 0.80)
"""Table 7-21 LTV band upper bounds (inclusive); last band is LTV > 80%."""
CRE_CASH_FLOW_RW: Final[tuple[float, ...]] = (0.70, 0.90, 1.10)
"""Table 7-21 (para 7.3.95, p. 7-57): regulatory CRE materially dependent on cash flows."""
RE_COUNTERPARTY_INDIVIDUAL_RW: Final[float] = 0.75
"""Paras 7.3.94(a) / 7.3.98(a) (pp. 7-57, 7-58): individual or group of individuals -- 75%."""
RE_COUNTERPARTY_SMALL_BUSINESS_RW: Final[float] = 0.85
"""Paras 7.3.94(b) / 7.3.98(b): small business -- 85%."""
JUNIOR_CHARGE_MULTIPLIER: Final[float] = 1.25
"""Para 7.3.96 (p. 7-57): 1.25x for regulatory RE against a junior charge (not in the lowest LTV
bucket), capped at the other-real-estate risk weight."""
OTHER_RE_CASH_FLOW_RW: Final[float] = 1.50
"""Para 7.3.99 (p. 7-58): other real estate, materially dependent on cash flows -- 150%."""

THRESHOLD_INVESTMENT_RW: Final[float] = 2.50
"""Paras 6.1.5(p)(iii) / 7.3.104 (pp. 6-13, 7-59): undeducted major-stake FI ordinary shares."""
MAJOR_STAKE_SOLO_RW: Final[float] = 4.00
"""Paras 6.1.6 / 7.3.105 (p. 7-59): 400% (Solo level, with MAS approval)."""
OTHER_EXPOSURES_RW: Final[float] = 1.00
"""Para 7.3.106 (p. 7-59): any other SA(CR) exposure in the other exposures asset class."""

CURRENCY_MISMATCH_MULTIPLIER: Final[float] = 1.5
"""Para 7.3.107 (p. 7-60): 1.5x for unhedged exposures to individuals in a non-income currency."""
CURRENCY_MISMATCH_MAX_RW: Final[float] = 1.50
"""Para 7.3.107: subject to a maximum risk weight of 150%."""
CURRENCY_MISMATCH_HEDGE_COVERAGE: Final[float] = 0.90
"""Para 7.3.108 (p. 7-61): hedged = natural/financial hedges covering >= 90% of instalments."""

DEFAULTED_PROVISION_THRESHOLD: Final[float] = 0.20
"""Table 7-22 (para 7.3.109, p. 7-61): specific allowances vs 20% of the outstanding amount."""
DEFAULTED_LOW_PROVISION_RW: Final[float] = 1.50
"""Table 7-22: specific allowances < 20% -- 150%."""
DEFAULTED_HIGH_PROVISION_RW: Final[float] = 1.00
"""Table 7-22: specific allowances no less than 20% -- 100%."""
DEFAULTED_RRE_RW: Final[float] = 1.00
"""Para 7.3.110 (p. 7-61): defaulted regulatory RRE / other RE secured by RRE, not cash-flow
dependent -- 100%."""

MATERIALITY_THRESHOLD_RW: Final[float] = 12.50
"""Para 7.3.113 (p. 7-62): 1250% to exposure below a protection materiality threshold."""
FCSA_FLOOR_RW: Final[float] = 0.20
"""Para 7.3.124 (p. 7-64): FC(SA) collateralised-portion floor of 20% (with 0%/10% exceptions)."""

# =========================================================================
#  CCFs -- Annex 7B, Table 7B-1 (pp. 7-179, 7-180)
# =========================================================================

CCF: Final[dict[OBSCategory, float]] = {
    OBSCategory.DIRECT_CREDIT_SUBSTITUTE: 1.00,  # item (a)
    OBSCategory.SECURITIES_LENDING_COLLATERAL: 1.00,  # item (b) / para 7.2.12 posted collateral
    OBSCategory.FORWARD_ASSET_PURCHASE: 1.00,  # item (c)
    OBSCategory.OTHER_100: 1.00,  # item (d)
    OBSCategory.NIF_RUF: 0.50,  # item (e)
    OBSCategory.TRANSACTION_RELATED_CONTINGENT: 0.50,  # item (f)
    OBSCategory.COMMITMENT_OTHER: 0.40,  # item (g), regardless of maturity
    OBSCategory.SHORT_TERM_TRADE_LC: 0.20,  # item (h), original maturity < 1 year
    OBSCategory.UNCONDITIONALLY_CANCELLABLE: 0.10,  # item (i)
}
"""Table 7B-1 standardised CCFs (Annex 7B para 1.1)."""
TRADE_LC_MAX_ORIGINAL_MONTHS: Final[float] = 12.0
"""Table 7B-1 item (h): self-liquidating trade items with an original maturity of below one year."""
TRADE_LC_LONG_DATED_CCF: Final[float] = 1.00
# TODO: VERIFY -- Table 7B-1 does not assign a CCF to self-liquidating trade items with an
# original maturity of one year or more; conservative placeholder of item (d) (100%).

# =========================================================================
#  CRM -- Annex 7J (FC(CA)) and Annex 7H Sections 6-7
# =========================================================================

SUPERVISORY_HAIRCUTS: Final[dict[str, float]] = {
    # Table 7J-1 (Annex 7J para 2.1, pp. 7-261, 7-262); 10-business-day holding period,
    # daily remargining/revaluation.  CQS1 includes short-term grade I; CQS2_3 includes
    # short-term grades II and III.
    "SOVEREIGN_CQS1_LE1Y": 0.005,
    "SOVEREIGN_CQS1_1Y_5Y": 0.02,
    "SOVEREIGN_CQS1_GT5Y": 0.04,
    "OTHER_CQS1_LE1Y": 0.01,
    "OTHER_CQS1_1Y_3Y": 0.03,
    "OTHER_CQS1_3Y_5Y": 0.04,
    "OTHER_CQS1_5Y_10Y": 0.06,
    "OTHER_CQS1_GT10Y": 0.12,
    "SECURITISATION_CQS1_LE1Y": 0.02,
    "SECURITISATION_CQS1_1Y_5Y": 0.08,
    "SECURITISATION_CQS1_GT5Y": 0.16,
    "SOVEREIGN_CQS2_3_LE1Y": 0.01,
    "SOVEREIGN_CQS2_3_1Y_5Y": 0.03,
    "SOVEREIGN_CQS2_3_GT5Y": 0.06,
    "OTHER_CQS2_3_LE1Y": 0.02,
    "OTHER_CQS2_3_1Y_3Y": 0.04,
    "OTHER_CQS2_3_3Y_5Y": 0.06,
    "OTHER_CQS2_3_5Y_10Y": 0.12,
    "OTHER_CQS2_3_GT10Y": 0.20,
    "SECURITISATION_CQS2_3_LE1Y": 0.04,
    "SECURITISATION_CQS2_3_1Y_5Y": 0.12,
    "SECURITISATION_CQS2_3_GT5Y": 0.24,
    "SOVEREIGN_CQS4": 0.15,  # all maturities; other issuers/securitisation not eligible
    "GOLD": 0.20,
    "MAIN_INDEX_EQUITY": 0.20,  # incl. convertible bonds
    "OTHER_LISTED_EQUITY": 0.30,  # listed on an approved or overseas exchange
    "CASH_SAME_CURRENCY": 0.0,
    "TRADING_BOOK_OTHER": 0.30,  # repo-style transactions in the trading book
    "NON_ELIGIBLE_LENT": 0.30,  # para 2.3: HE for non-eligible instruments lent/posted
}
"""Table 7J-1 -- Standard Supervisory Haircuts (H10)."""
FX_MISMATCH_HAIRCUT: Final[float] = 0.08
"""Annex 7J para 2.4 (p. 7-263) and Annex 7H para 6.2 (p. 7-253): HFX = 8% (10-day, daily MTM)."""
HAIRCUT_BASE_HOLDING_DAYS: Final[int] = 10
"""Annex 7J para 3.4 (p. 7-264): H10 is based on a 10-business-day holding period."""
MIN_HOLDING_PERIOD_DAYS: Final[dict[str, int]] = {
    "REPO_STYLE": 5,  # daily remargining
    "CAPITAL_MARKET": 10,  # OTC derivatives, margin lending, commodities lending; daily remargining
    "SECURED_LENDING": 20,  # daily revaluation
    "MIXED_NETTING_SET": 10,  # repo-style + other capital market transactions
}
"""Table 7J-2 (Annex 7J para 3.1, p. 7-263): minimum holding periods."""
LARGE_NETTING_SET_HOLDING_DAYS: Final[int] = 20
"""Table 7J-3 (p. 7-263): > 5,000 transactions or illiquid collateral -- 20 business days."""
LARGE_NETTING_SET_TRADES: Final[int] = 5000
"""Table 7J-3: number-of-transactions trigger."""
MATURITY_MISMATCH_OFFSET_YEARS: Final[float] = 0.25
"""Annex 7H para 7.4 (p. 7-254): PA = P x (t - 0.25) / (T - 0.25)."""
MATURITY_MISMATCH_T_CAP_YEARS: Final[float] = 5.0
"""Annex 7H para 7.4(c): T = min(5, residual maturity of the exposure)."""
MATURITY_MISMATCH_MIN_RESIDUAL_YEARS: Final[float] = 0.25
"""Annex 7H para 7.1 (p. 7-254): residual maturity of the mitigant of at least 3 months."""
MATURITY_MISMATCH_MIN_ORIGINAL_YEARS: Final[float] = 1.0
"""Annex 7H para 7.1: original maturity of the mitigant of at least one year."""

# =========================================================================
#  Operational risk -- Part IX (pp. 9-1 to 9-7)
# =========================================================================

BIC_BASE_COEFFICIENT: Final[float] = 0.12
"""Para 9.1.2(a)(i): 12% of the BI."""
BIC_TIER2_THRESHOLD_SGD_M: Final[float] = 1_500.0
"""Para 9.1.2(a)(ii): BI above S$1.5 billion."""
BIC_TIER2_INCREMENT: Final[float] = 0.03
"""Para 9.1.2(a)(ii): 3% of the BI above S$1.5 billion (marginal 15%)."""
BIC_TIER3_THRESHOLD_SGD_M: Final[float] = 45_000.0
"""Para 9.1.2(a)(iii): BI above S$45 billion."""
BIC_TIER3_INCREMENT: Final[float] = 0.03
"""Para 9.1.2(a)(iii): a further 3% of the BI above S$45 billion (marginal 18%)."""
ILDC_IEA_CAP: Final[float] = 0.0225
"""Para 9.1.3(a): ILDC caps |interest income - interest expense| at 2.25% of IEA."""
LC_MULTIPLE: Final[float] = 15.0
"""Para 9.1.2(b)(i): LC = 15 x average annual net losses."""
ILM_EXPONENT: Final[float] = 0.8
"""Para 9.1.2(b): ILM = ln(exp(1) - 1 + (LC/BIC)^0.8)."""
LOSS_YEARS_STANDARD: Final[int] = 10
"""Paras 9.1.2(b)(i) / 9.1.13: 10 consecutive financial years of loss data."""
LOSS_YEARS_MINIMUM: Final[int] = 5
"""Para 9.1.14: minimum 5-year observation period (with MAS approval)."""
ILM_ONE_BI_THRESHOLD_SGD_M: Final[float] = 1_500.0
"""Para 9.1.8(a): BI <= S$1.5 billion -> ILM = 1 unless MAS approves loss-data use."""
LOSS_THRESHOLD_SMALL_SGD_M: Final[float] = 0.03
"""Paras 9.1.20 / 9.1.21(a): S$30,000 net-loss inclusion threshold."""
LOSS_THRESHOLD_LARGE_SGD_M: Final[float] = 0.15
"""Para 9.1.21(b): S$150,000 threshold for the LC of banks with BI > S$1.5 billion."""
OPRISK_RWA_MULTIPLIER: Final[float] = 12.5
"""Para 9.1.1: operational RWA = 12.5 x operational risk capital requirement."""

# =========================================================================
#  Output floor -- Part V Table 5-3 (p. 5-4)
# =========================================================================

OUTPUT_FLOOR_SCHEDULE: Final[tuple[tuple[date, float], ...]] = (
    (date(2024, 7, 1), 0.50),
    (date(2025, 1, 1), 0.55),
    (date(2026, 1, 1), 0.60),
    (date(2027, 1, 1), 0.65),
    (date(2028, 1, 1), 0.70),
    (date(2029, 1, 1), 0.725),
)
"""Table 5-3 -- Output floor calibration (effective-from dates)."""
OUTPUT_FLOOR_MAX: Final[float] = 1.00
"""Para 5.1.6: MAS may set a higher percentage, in any case not more than 100%."""

# =========================================================================
#  Capital ratios and buffers -- Part IV (pp. 4-1 to 4-12)
# =========================================================================

DSIB_CET1_MIN: Final[float] = 0.065
"""Table 4-1 (para 4.1.5, p. 4-1): D-SIB minimum CET1 CAR 6.5%."""
DSIB_T1_MIN: Final[float] = 0.08
"""Table 4-1: D-SIB minimum Tier 1 CAR 8%."""
DSIB_TOTAL_MIN: Final[float] = 0.10
"""Table 4-1: D-SIB minimum Total CAR 10%."""
NON_DSIB_CET1_MIN: Final[float] = 0.045
"""Table 4-2 (para 4.1.6, p. 4-2): non-D-SIB minimum CET1 CAR 4.5%."""
NON_DSIB_T1_MIN: Final[float] = 0.06
"""Table 4-2: non-D-SIB minimum Tier 1 CAR 6%."""
NON_DSIB_TOTAL_MIN: Final[float] = 0.08
"""Table 4-2: non-D-SIB minimum Total CAR 8%."""
CONSERVATION_BUFFER: Final[float] = 0.025
"""Para 4.1.7 (p. 4-2): capital conservation buffer of 2.5% CET1."""
CCYB_MAX: Final[float] = 0.025
"""Para 4.1.17 / 4.1.18(a)(ii) / 4.1.29: CCyB 0-2.5%; foreign rates capped at 2.5% unless MAS
specifies otherwise; MAS may set a Singapore rate above 2.5% (para 4.1.30)."""
CONSERVATION_RATIOS: Final[tuple[float, ...]] = (1.00, 0.80, 0.60, 0.40, 0.0)
"""Tables 4-3 / 4-4 / 4-5 (pp. 4-4, 4-9): minimum capital conservation ratios by buffer quartile
(first, second, third, fourth quartile, above the top of the buffer)."""
LEVERAGE_MINIMUM: Final[float] = 0.03
"""Para 4.2.2 (p. 4-12): minimum leverage ratio of 3% at Solo and Group levels."""
DSIB_LEVERAGE_BUFFER: Final[float] = 0.0
# TODO: VERIFY -- Annex 11D row 27 (p. 11-164) refers to a "D-SIB leverage ratio buffer
# requirement", but no rate is set in the Notice text; placeholder 0% pending the MAS
# designation / supervisory letter that would set it.

# =========================================================================
#  SA-CCR -- Annex 7D (pp. 7-182 to 7-199)
# =========================================================================

SACCR_ALPHA: Final[float] = 1.4
"""Annex 7D para 1.1(a): alpha = 1.4 (no counterparty-type variation in the Notice)."""
SACCR_MULTIPLIER_FLOOR: Final[float] = 0.05
"""Annex 7D para 3.1(b)(ii): Floor = 5%."""
SACCR_MARGINED_MF_SCALAR: Final[float] = 1.5
"""Annex 7D para 3.36(b): MF(margined) = 3/2 x sqrt(MPOR / 1 year)."""
SACCR_MIN_MATURITY_YEARS: Final[float] = 10.0 / 250.0
"""Annex 7D para 3.36(a) and footnote 361: Mi floored at 10 business days (10/250 years)."""
SACCR_BUSINESS_DAYS_PER_YEAR: Final[float] = 250.0
"""Annex 7D footnote 361: a year represented by 250 business days."""
SACCR_SD_RATE: Final[float] = 0.05
"""Annex 7D para 3.28(a) (p. 7-194): SD = (exp(-0.05 S) - exp(-0.05 E)) / 0.05."""
SACCR_BASIS_SF_SCALAR: Final[float] = 0.5
"""Annex 7D para 3.41(a): basis hedging sets -- SF x 0.5."""
SACCR_VOLATILITY_SF_SCALAR: Final[float] = 5.0
"""Annex 7D para 3.41(b): volatility hedging sets -- SF x 5."""
SACCR_UNRATED_CREDIT_SF: Final[float] = 0.0106
"""Annex 7D para 3.42: unrated reference entity without IRBA mapping -- SF 1.06%."""

SACCR_SUPERVISORY_PARAMS: Final[dict[str, tuple[float, float | None, float]]] = {
    # key: (supervisory factor, correlation, supervisory option volatility) -- Table 7D-1
    "IR": (0.005, None, 0.50),
    "FX": (0.04, None, 0.15),
    "CREDIT_SN_CQS1": (0.0038, 0.50, 1.00),
    "CREDIT_SN_CQS2": (0.0042, 0.50, 1.00),
    "CREDIT_SN_CQS3": (0.0054, 0.50, 1.00),
    "CREDIT_SN_CQS4": (0.0106, 0.50, 1.00),
    "CREDIT_SN_CQS5": (0.016, 0.50, 1.00),
    "CREDIT_SN_CQS6": (0.06, 0.50, 1.00),
    "CREDIT_INDEX_CQS1_3": (0.0038, 0.80, 0.80),
    "CREDIT_INDEX_CQS4_6": (0.0106, 0.80, 0.80),
    "EQUITY_SN": (0.32, 0.50, 1.20),
    "EQUITY_INDEX": (0.20, 0.80, 0.75),
    "COMMODITY_ELECTRICITY": (0.40, 0.40, 1.50),
    "COMMODITY_OIL_GAS": (0.18, 0.40, 0.70),
    "COMMODITY_METALS": (0.18, 0.40, 0.70),
    "COMMODITY_AGRICULTURAL": (0.18, 0.40, 0.70),
    "COMMODITY_OTHER": (0.18, 0.40, 0.70),
}
"""Table 7D-1 -- Supervisory Parameters (Annex 7D para 3.40, pp. 7-199, 7-200)."""

# =========================================================================
#  BA-CVA -- Part VIII Division 5 (pp. 8-178 to 8-186)
# =========================================================================

BA_CVA_DISCOUNT_SCALAR: Final[float] = 0.65
"""Paras 8.5.13 / 8.5.16: DS_BA-CVA = 0.65."""
BA_CVA_RHO: Final[float] = 0.50
"""Para 8.5.14(c): rho = 50%."""
BA_CVA_ALPHA: Final[float] = 1.4
"""Para 8.5.14(b)(v): alpha = 1.4."""
BA_CVA_BETA: Final[float] = 0.25
"""Para 8.5.17(a): beta = 0.25."""
BA_CVA_DISCOUNT_RATE: Final[float] = 0.05
"""Para 8.5.14(b)(iv)(B) and footnote 826: DF = (1 - exp(-0.05 M)) / (0.05 M)."""
BA_CVA_INDEX_SAME_SECTOR_SCALAR: Final[float] = 0.7
"""Para 8.5.17(c)(v)(B): index hedge RW x 0.7."""
CVA_RWA_MULTIPLIER: Final[float] = 12.5
"""Para 8.5.1: CVA RWA = 12.5 x CVA risk capital requirement."""
CVA_CCR_ELECTION_NOTIONAL_SGD_M: Final[float] = 150_000.0
"""Para 8.5.10 (p. 8-180): non-centrally cleared derivatives notional <= S$150 billion may set
CVA RWA = CCR-SA RWA + CCR-IRBA RWA (no hedge recognition)."""

BA_CVA_RW: Final[dict[str, tuple[float, float]]] = {
    # sector: (credit quality grade "3" or better, grade "4" or worse / not rated) -- Table 8-26
    "SOVEREIGN": (
        0.005,
        0.02,
    ),  # central governments, central banks, BIS, IMF, ECB, EU, ESM, EFSF, MDBs
    "PSE": (0.01, 0.04),  # PSEs, education
    "FINANCIAL": (0.05, 0.12),
    "BASIC_MATERIALS": (
        0.03,
        0.07,
    ),  # basic materials, energy, industrials, agriculture, manufacturing, mining
    "CONSUMER": (0.03, 0.085),  # consumer goods/services, transportation/storage, admin & support
    "TECHNOLOGY": (0.02, 0.055),  # technology, telecommunications
    "HEALTHCARE": (0.015, 0.05),  # health care, utilities, professional and technical activities
    "OTHER": (0.05, 0.12),
}
"""Table 8-26 -- BA-CVA risk weights (p. 8-183)."""
BA_CVA_HEDGE_CORRELATION: Final[dict[str, float]] = {
    "COUNTERPARTY": 1.00,  # references counterparty c
    "RELATED": 0.80,  # parent, subsidiary, or same parent as counterparty c
    "SECTOR": 0.50,  # same sector (Table 8-26) and country/jurisdiction as counterparty c
}
"""Table 8-27 -- r_hc correlations (p. 8-187)."""
