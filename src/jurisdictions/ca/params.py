"""OSFI Capital Adequacy Requirements (CAR) Guideline 2026 -- regulatory parameters.

Every constant below is transcribed from the text of the OSFI CAR Guideline
(effective fiscal Q1 2026, "valid until the end of the reporting period on
January 31, 2027"), chapters 1, 3, 4, 7 and 8. Each carries a citation of the
form ``CAR Ch.<n> s.<section> [Table <t>] [Basel Framework <ref>]``: the OSFI
chapter and section/table, followed by the Basel cross-reference OSFI prints in
square brackets at the end of the paragraph. OSFI paragraph numbers are cited
only where the CAR text itself cross-references them (e.g. "paragraph 90" for
the real-estate eligibility requirements).

The verbatim transcription of every table is in
``docs/jurisdictions/CA_parameter_reference.md``.

Currency: CAR footnote 6 to Chapter 1 -- "All dollar values in this guideline
are in Canadian dollars, unless otherwise noted." Thresholds below are stated
in CAD millions exactly as printed; the engine is currency-agnostic and takes
inputs already converted.

References:
    - OSFI CAR 2026 Chapter 1 (minimums, floor, buffers, D-SIB, DSB)
    - OSFI CAR 2026 Chapter 3 (operational risk: SA and SSA)
    - OSFI CAR 2026 Chapter 4 (credit risk standardized approach, CRM)
    - OSFI CAR 2026 Chapter 7 (SA-CCR)
    - OSFI CAR 2026 Chapter 8 (CVA)
    - Basel Framework CRE20-22, CRE52, MAR50, OPE25, RBC20, RBC30, RBC40
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import OBSCategory, RatingBucket, SCRAGrade, ShortTermRating

R = RatingBucket

# =========================================================================
#  Chapter 1 -- minimum ratios, buffers, D-SIB, DSB, leverage
# =========================================================================

CET1_MINIMUM: Final[float] = 0.045
"""CAR Ch.1 s.1.6.1 Table 2 (CET1 4.5%) [Basel Framework RBC20]."""
TIER1_MINIMUM: Final[float] = 0.060
"""CAR Ch.1 s.1.6.1 Table 2 (Tier 1 6.0%)."""
TOTAL_CAPITAL_MINIMUM: Final[float] = 0.080
"""CAR Ch.1 s.1.6.1 Table 2 (Total 8.0%)."""

CAPITAL_CONSERVATION_BUFFER: Final[float] = 0.025
"""CAR Ch.1 s.1.7.1 Table 4 -- "The capital conservation buffer is 2.5% of RWA" [RBC 30.2]."""

CCYB_MAXIMUM_RECIPROCATED: Final[float] = 0.025
"""CAR Ch.1 s.1.7.2 -- CCyB "ranging from 0% to 2.5% of total risk-weighted assets";
reciprocity mandatory up to 2.5% (footnote 19) [RBC 30.8, 30.9, 30.13 FAQ3/4]."""

DSIB_SURCHARGE: Final[float] = 0.010
"""CAR Ch.1 s.1.8 -- "D-SIBs will be subject to a CET1 surcharge equal to 1% of RWAs"
[BCBS RBC 40.7 to 40.23]."""

DSB_MINIMUM: Final[float] = 0.000
DSB_MAXIMUM: Final[float] = 0.040
"""CAR Ch.1 s.1.9 -- "The level of the DSB will range between 0 and 4.0% of a D-SIB's total
RWA". The *current* level is NOT stated in CAR: it is set in OSFI's semi-annual (June and
December) DSB announcements (s.1.9, footnote 31). Annex 2 notes 1% "as at May 1, 2020" and
footnote 35 uses 2% only as an example."""
# TODO: VERIFY -- current DSB level is set by OSFI's semi-annual DSB announcement, not by CAR;
# the engine takes it as an input (default None -> 0 with a warning note).

DSIB_TARGET_CET1_EX_DSB: Final[float] = 0.080
DSIB_TARGET_TIER1_EX_DSB: Final[float] = 0.095
DSIB_TARGET_TOTAL_EX_DSB: Final[float] = 0.115
"""CAR Ch.1 s.1.10 Table 8 -- D-SIB targets "8.0% plus DSB / 9.5% plus DSB / 11.5% plus DSB"."""
SMSB_TARGET_CET1: Final[float] = 0.070
SMSB_TARGET_TIER1: Final[float] = 0.085
SMSB_TARGET_TOTAL: Final[float] = 0.105
"""CAR Ch.1 s.1.10 Table 8 -- SMSB targets 7.0% / 8.5% / 10.5%."""

GSIB_HLA_BY_BUCKET: Final[dict[int, float]] = {1: 0.010, 2: 0.015, 3: 0.020, 4: 0.025, 5: 0.035}
"""CAR Ch.1 Annex 1 ("Relationship with Basel Committee G-SIB Framework"): OSFI adopted the BCBS
G-SIB methodology, HLA "range from 1% to 3.5% RWA" (footnote 41 -> RBC 40.1-40.6); "the higher
of the D-SIB and G-SIB surcharges will apply". Bucket rates transcribed from Basel Framework
RBC40.4 Table 1 (CAR itself does not tabulate the buckets)."""

LEVERAGE_MINIMUM: Final[float] = 0.030
"""OSFI Leverage Requirements Guideline (2023) s.IV paragraph 17 -- "Institutions are expected to
maintain a leverage ratio that meets or exceeds 3% at all times" [LEV 20.7]; also CAR Ch.4 s.4.1.4
("Banks are required to have a minimum Leverage Ratio of 3%" [CRE 20.24])."""
DSIB_LEVERAGE_BUFFER_SHARE_OF_HLA: Final[float] = 0.50
"""OSFI Leverage Requirements Guideline (2023) s.IV -- "The leverage ratio buffer will be set at 50%
of a D-SIB's higher-loss absorbency risk-weighted requirements. For example, a D-SIB subject to a
1% higher-loss absorbency requirement would be subject to a 0.5% leverage ratio buffer
requirement." [LEV 40.1-40.2]. Met with Tier 1; applies to D-SIBs only."""
DSIB_LEVERAGE_REQUIREMENT: Final[float] = 0.035
"""LR s.IV -- "This means that DSIBs are expected to maintain a leverage ratio that meets or exceeds
3.5% at all times" (with the 1% D-SIB surcharge); also CAR Ch.4 s.4.1.4 and Ch.1 Table 7 / LR
Table 1 Tier 1 leverage ranges 3%-3.50%."""
DSIB_LEVERAGE_BUFFER: Final[float] = DSIB_LEVERAGE_BUFFER_SHARE_OF_HLA * DSIB_SURCHARGE
"""0.5% = 50% x the 1% D-SIB surcharge (LR s.IV); confirmed against the Leverage Requirements
Guideline (the previous TODO: VERIFY is resolved). Where a G-SIB surcharge above 1% applies (the
higher of the D-SIB and G-SIB surcharges, CAR Ch.1 Annex 1), the buffer is 50% of that HLA.
Institution-specific authorized leverage ratios are set bilaterally and are not modelled."""

CONSERVATION_RATIOS_NON_DSIB: Final[tuple[tuple[float, float], ...]] = (
    (0.05125, 1.00), (0.0575, 0.80), (0.06375, 0.60), (0.070, 0.40),
)
"""CAR Ch.1 s.1.7.1 Table 5 -- upper bound of CET1 range -> minimum conservation ratio;
above 7.0% -> 0% [RBC 30.4]."""
CONSERVATION_RATIOS_DSIB: Final[tuple[tuple[float, float, float], ...]] = (
    (0.05375, 0.03125, 1.00), (0.0625, 0.0325, 0.80), (0.07125, 0.03375, 0.60),
    (0.080, 0.035, 0.40),
)
"""CAR Ch.1 s.1.8 Table 7 -- (CET1 upper bound, Tier 1 leverage upper bound, conservation ratio);
above 8.0% CET1 / 3.50% leverage -> 0%."""

# =========================================================================
#  Chapter 1 s.1.5 -- capital floor (output floor)
# =========================================================================

FLOOR_ADJUSTMENT_FACTOR: Final[float] = 0.675
"""CAR Ch.1 s.1.5.1 (paragraph 33) -- "The floor adjustment factor is set at 67.5% until
further notice. OSFI will provide at least two years prior notice to resuming an increase in
the floor adjustment factor." [RBC 20.11-20.12]. No year-by-year schedule is printed."""
FLOOR_FACTOR_NEW_IRB_APPROVAL: Final[float] = 0.90
"""CAR Ch.1 s.1.4 -- "For institutions approved to use the IRB approach, upon approval, the floor
adjustment factor will be set at 90%"."""
FLOOR_FACTOR_MAX_STEP_DOWN: Final[float] = 0.075
"""CAR Ch.1 s.1.4 -- reductions "by up to 7.5%, after at least four quarters at a set level"."""
FLOOR_ALLOWANCE_MULTIPLIER: Final[float] = 12.5
"""CAR Ch.1 s.1.5.1-1.5.2 -- "12.5 times" general allowances / shortfall / excess provisions."""
CAR_2026_FIRST_YEAR: Final[int] = 2026
"""Guideline effective for fiscal 2026 (cover note: "Guideline (Effective January 2026)")."""

# =========================================================================
#  Chapter 3 -- operational risk
# =========================================================================

SA_REQUIRED_AGI_THRESHOLD_CAD_M: Final[float] = 1_500.0
"""CAR Ch.3 s.3.2 / Ch.1 s.1.3.3 -- SA mandatory for D-SIBs and SMSBs with adjusted gross income
greater than $1.5 billion (CAD)."""
SSA_AGI_COEFFICIENT: Final[float] = 0.15
"""CAR Ch.3 s.3.3 -- ORC_SSA = (AGI over previous 12 fiscal quarters / 3) x 15%."""
SSA_NII_CAP_PCT_IEA: Final[float] = 0.0225
"""CAR Ch.3 s.3.3 -- AGI uses "the lesser of (i) the absolute value of net interest income, and
(ii) 2.25% of interest earning assets"."""
ILDC_IEA_CAP: Final[float] = 0.0225
"""CAR Ch.3 s.3.4.1 -- ILDC = Min[Abs(II - IE); 2.25% x IEA] + Dividend income [OPE 25.4-25.5]."""

BIC_BASE_COEFFICIENT: Final[float] = 0.12
BIC_INCREMENT_1: Final[float] = 0.03
BIC_THRESHOLD_1_CAD_M: Final[float] = 1_500.0
BIC_INCREMENT_2: Final[float] = 0.03
BIC_THRESHOLD_2_CAD_M: Final[float] = 45_000.0
"""CAR Ch.3 s.3.4.1 -- "12% of BI, plus 3% of BI above $1.5 billion (if any), plus 3% of BI above
$45 billion (if any)" [OPE 25.7]; i.e. marginal 12% / 15% / 18%. Footnote 8 worked example:
BI = $50B -> BIC = $7.605B."""

LOSS_COMPONENT_MULTIPLIER: Final[float] = 15.0
"""CAR Ch.3 s.3.4.1 -- LC = 15 x average annual net operational losses over 10 years [OPE 25.8]."""
ILM_EXPONENT: Final[float] = 0.8
"""CAR Ch.3 s.3.4.1 -- ILM = ln(exp(1) - 1 + (LC/BIC)^0.8) [OPE 25.8-25.9]."""
LOSS_DATA_YEARS: Final[int] = 10
"""CAR Ch.3 s.3.4.1 -- 10 years of high-quality loss data; otherwise ILM >= 1 [OPE 25.10]."""
LOSS_DATA_THRESHOLD_CAD: Final[float] = 30_000.0
"""CAR Ch.3 s.3.4.3 -- minimum loss-event threshold "set at $30,000" (CAD, net of recoveries)
[OPE 25.18]."""
LOSS_EXCLUSION_MATERIALITY: Final[float] = 0.05
"""CAR Ch.3 s.3.4.5 -- exclusion requests only for events > 5% of average annual losses
[OPE 25.32]."""
OPRISK_RWA_MULTIPLIER: Final[float] = 12.5
"""CAR Ch.3 s.3.3/3.4 -- "RWA for operational risk are equal to 12.5 times ORC"."""

# =========================================================================
#  Chapter 4 -- credit risk, standardized approach
# =========================================================================

SMSB_SIMPLIFIED_THRESHOLD_CAD_M: Final[float] = 500.0
"""CAR Ch.4 introduction / Appendix I -- simplified treatment for Category I/II SMSBs where the
asset-class grouping does not exceed $500 million."""

# --- s.4.1.1 Sovereigns ----------------------------------------------------
SOVEREIGN_RW: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.00, R.A_PLUS_TO_A_MINUS: 0.20, R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00, R.B_PLUS_TO_B_MINUS: 1.00, R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 1.00,
}
"""CAR Ch.4 s.4.1.1 Table 1 [CRE 20.7] ("BB+ to B-" = 100%)."""
CANADA_SOVEREIGN_RW: Final[float] = 0.00
"""CAR Ch.4 s.4.1.1 -- "exposures to the Canadian sovereign and central bank are to be
risk-weighted at 0%"; current tax assets treated as sovereign."""
ECA_SCORE_RW: Final[dict[int, float]] = {
    0: 0.00, 1: 0.00, 2: 0.20, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.50,
}
"""CAR Ch.4 s.4.1.1 Table 2 (ECA risk scores 0-1 / 2 / 3 / 4-6 / 7) [CRE 20.9]."""
SUPRANATIONAL_ZERO_RW: Final[float] = 0.00
"""CAR Ch.4 s.4.1.1 -- BIS, IMF, ECB, EU, ESM, EFSF receive 0% [CRE 20.10]."""

# --- s.4.1.2 PSEs ----------------------------------------------------------
PSE_RW_BY_SOVEREIGN_RATING: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.20, R.A_PLUS_TO_A_MINUS: 0.50, R.BBB_PLUS_TO_BBB_MINUS: 1.00,
    R.BB_PLUS_TO_BB_MINUS: 1.00, R.B_PLUS_TO_B_MINUS: 1.00, R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 1.00,
}
"""CAR Ch.4 s.4.1.2 Table 3 -- PSE risk weight "one category higher than the sovereign"
[CRE 20.11]. Canadian provinces/territories and agents whose debts are obligations of the parent
government receive the Government of Canada risk weight (s.4.1.2, [CRE 20.12])."""

# --- s.4.1.3 MDBs ----------------------------------------------------------
MDB_ZERO_RW: Final[float] = 0.00
"""CAR Ch.4 s.4.1.3 -- 0% for MDBs meeting the eligibility criteria (footnote 14 list)
[CRE 20.14]."""
MDB_RW: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.20, R.A_PLUS_TO_A_MINUS: 0.30, R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00, R.B_PLUS_TO_B_MINUS: 1.00, R.BELOW_B_MINUS: 1.50,
    R.UNRATED: 0.50,
}
"""CAR Ch.4 s.4.1.3 Table 4 [CRE 20.15]."""

# --- s.4.1.4 Banks -----------------------------------------------------------
BANK_ECRA_BASE_RW: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.20, R.A_PLUS_TO_A_MINUS: 0.30, R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00, R.B_PLUS_TO_B_MINUS: 1.00, R.BELOW_B_MINUS: 1.50,
}
"""CAR Ch.4 s.4.1.4 Table 5 "Base" risk weight [CRE 20.18]."""
BANK_ECRA_SHORT_TERM_RW: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.20, R.A_PLUS_TO_A_MINUS: 0.20, R.BBB_PLUS_TO_BBB_MINUS: 0.20,
    R.BB_PLUS_TO_BB_MINUS: 0.50, R.B_PLUS_TO_B_MINUS: 0.50, R.BELOW_B_MINUS: 1.50,
}
"""CAR Ch.4 s.4.1.4 Table 5 "Risk weight for short-term exposures" [CRE 20.18-20.19]."""
BANK_SCRA_BASE_RW: Final[dict[SCRAGrade, float]] = {
    SCRAGrade.A: 0.40, SCRAGrade.B: 0.75, SCRAGrade.C: 1.50,
}
"""CAR Ch.4 s.4.1.4 Table 6 "Base" risk weight [CRE 20.21]."""
BANK_SCRA_SHORT_TERM_RW: Final[dict[SCRAGrade, float]] = {
    SCRAGrade.A: 0.20, SCRAGrade.B: 0.50, SCRAGrade.C: 1.50,
}
"""CAR Ch.4 s.4.1.4 Table 6 "Bank risk weight for short-term exposures" [CRE 20.21, 20.31]."""
BANK_SCRA_GRADE_A_ENHANCED_RW: Final[float] = 0.30
"""CAR Ch.4 s.4.1.4 (under Table 6) -- 30% where CET1 >= 14% and Tier 1 leverage >= 5% and Grade A
criteria are met [CRE 20.21]."""
BANK_SCRA_ELECTION_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.4 -- SCRA option: 100% to all unrated bank exposures, with prior notification
[CRE 20.21]."""
BANK_SHORT_TERM_MAX_MONTHS: Final[float] = 3.0
BANK_TRADE_SHORT_TERM_MAX_MONTHS: Final[float] = 6.0
"""CAR Ch.4 s.4.1.4 -- original maturity of three months or less; goods-movement trade exposures
of six months or less [CRE 20.19, 20.31]."""
SMSB_BANK_RW: Final[float] = 0.40
SMSB_BANK_SHORT_TERM_RW: Final[float] = 0.20
"""CAR Ch.4 s.4.1.4 (paragraph 26) -- Category I/II SMSB simplified bank treatment."""

SHORT_TERM_ISSUE_RW: Final[dict[ShortTermRating, float]] = {
    ShortTermRating.A1_P1: 0.20, ShortTermRating.A2_P2: 0.50,
    ShortTermRating.A3_P3: 1.00, ShortTermRating.OTHERS: 1.50,
}
"""CAR Ch.4 s.4.2.3.5 Table 15 -- issue-specific short-term ratings (banks and corporates)
[CRE 21.16]."""

# --- s.4.1.5 Covered bonds -----------------------------------------------------
COVERED_BOND_RATED_RW: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.20, R.A_PLUS_TO_A_MINUS: 0.30, R.BBB_PLUS_TO_BBB_MINUS: 0.50,
    R.BB_PLUS_TO_BB_MINUS: 1.00, R.B_PLUS_TO_B_MINUS: 1.00, R.BELOW_B_MINUS: 1.50,
}
"""CAR Ch.4 s.4.1.5 Table 7 [CRE 20.38] -- as printed, identical to the bank ECRA base weights
(the Basel CRE20.38 Table 8 schedule is 10/20/20/50/100%)."""
# TODO: VERIFY -- CAR Table 7 / Table 8 as printed give covered bonds the issuer-bank weights
# (no Basel CRE20.38 reduction). Conservative relative to Basel; confirm against the official
# OSFI publication.
COVERED_BOND_UNRATED_RW: Final[dict[float, float]] = {
    0.20: 0.20, 0.30: 0.30, 0.40: 0.40, 0.50: 0.50, 0.75: 0.75, 1.00: 1.00, 1.50: 1.50,
}
"""CAR Ch.4 s.4.1.5 Table 8 -- issuing-institution RW -> "Base" covered bond RW (identity map as
printed) [CRE 20.38]."""
SMSB_COVERED_BOND_RW: Final[float] = 0.20
"""CAR Ch.4 s.4.1.5 (paragraph 47) -- SMSB simplified 20%."""

# --- s.4.1.7 Corporates ----------------------------------------------------------
CORPORATE_RATED_RW: Final[dict[RatingBucket, float]] = {
    R.AAA_TO_AA_MINUS: 0.20, R.A_PLUS_TO_A_MINUS: 0.50, R.BBB_PLUS_TO_BBB_MINUS: 0.75,
    R.BB_PLUS_TO_BB_MINUS: 1.00, R.B_PLUS_TO_B_MINUS: 1.50, R.BELOW_B_MINUS: 1.50,
}
"""CAR Ch.4 s.4.1.7 Table 9 ("BB+ to BB-" 100%, "Below BB-" 150%) [CRE 20.42-20.43]."""
CORPORATE_ELECTION_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.7 (paragraph 60) -- 100% to all corporate exposures, with prior notification."""
CORPORATE_UNRATED_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.7 (paragraph 62) -- unrated corporates where the institution does not identify
all unrated exposures as IG / non-IG [CRE 20.44, footnote 23]."""
CORPORATE_UNRATED_IG_RW: Final[float] = 0.65
"""CAR Ch.4 s.4.1.7 (paragraphs 62-63) -- unrated "investment grade" corporates
[CRE 20.44, 20.46]."""
CORPORATE_UNRATED_NON_IG_RW: Final[float] = 1.50
"""CAR Ch.4 s.4.1.7 (paragraph 62) -- "Unrated corporate exposures that are not identified as
'investment grade' ... will be assigned a risk weight of 150%" [cross-ref CRE 20.44]."""
# TODO: VERIFY -- 150% as printed; Basel CRE20.44 assigns 100% to non-IG unrated corporates.
# Conservative relative to Basel; confirm against the official OSFI publication.
IG_LISTED_OR_SALES_THRESHOLD_CAD_M: Final[float] = 75.0
"""CAR Ch.4 s.4.1.7 (paragraph 63) -- IG corporate must have listed securities or consolidated
group annual sales of more than $75 million."""
US_GSE_RW: Final[float] = 0.20
"""CAR Ch.4 s.4.1.7 (paragraph 58) -- "U.S. GSEs must be risk-weighted at 20%"."""
SME_SALES_THRESHOLD_CAD_M: Final[float] = 75.0
"""CAR Ch.4 s.4.1.7 (paragraphs 58, 64) -- corporate SME: consolidated group annual sales less
than or equal to $75 million [CRE 20.47]."""
CORPORATE_SME_UNRATED_RW: Final[float] = 0.85
"""CAR Ch.4 s.4.1.7 (paragraph 64) -- unrated corporate SMEs 85% [CRE 20.47]."""
SME_RETAIL_SBE_RW: Final[float] = 0.75
"""CAR Ch.4 s.4.1.7 (paragraph 64) -- unrated SMEs meeting paragraph 83 -> regulatory retail SBE
at 75% [CRE 20.47]."""
SMSB_CORPORATE_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.7 (paragraph 58) -- SMSB simplified 100% (corporates, SMEs, SL)."""

# --- Specialized lending --------------------------------------------------------
SL_OBJECT_COMMODITY_RW: Final[float] = 1.00
SL_PF_PRE_OPERATIONAL_RW: Final[float] = 1.30
SL_PF_OPERATIONAL_RW: Final[float] = 1.00
SL_PF_HIGH_QUALITY_RW: Final[float] = 0.80
"""CAR Ch.4 s.4.1.7 -- unrated SL: OF/CF 100%; PF 130% pre-operational, 100% operational, 80%
high-quality operational [CRE 20.51-20.52]. Rated SL uses issue-specific ratings in Table 9 only
(issuer ratings not permitted) [CRE 20.50]."""

# --- s.4.1.8 Subordinated debt / equity -----------------------------------------
SUBORDINATED_DEBT_RW: Final[float] = 1.50
"""CAR Ch.4 s.4.1.8 (paragraph 78) -- subordinated debt and capital instruments other than
equities (incl. non-deducted other TLAC liabilities) 150% [CRE 20.60]."""
EQUITY_GENERAL_RW: Final[float] = 2.50
EQUITY_SPECULATIVE_UNLISTED_RW: Final[float] = 4.00
"""CAR Ch.4 s.4.1.8 (paragraph 75) -- 400% speculative unlisted, 250% all other equity
[CRE 20.57-20.58]."""
EQUITY_LEGISLATED_PROGRAMME_RW: Final[float] = 1.00
EQUITY_LEGISLATED_PROGRAMME_CAP_TOTAL_CAPITAL: Final[float] = 0.10
"""CAR Ch.4 s.4.1.8 (paragraph 77) -- 100% for national legislated programmes (incl. Specialized
Financing (Banks) Regulations), up to 10% of Total capital [CRE 20.59]."""
SIGNIFICANT_COMMERCIAL_INVESTMENT_RW: Final[float] = 2.50
SIGNIFICANT_COMMERCIAL_DEDUCTION_THRESHOLD_CET1: Final[float] = 0.10
"""CAR Ch.4 s.4.1.8 -- significant investments in commercial entities: amounts above 10% of CET1
deducted; below the threshold 250% [CRE 20.62]."""
# No equity transitional (phase-in) schedule appears anywhere in CAR 2026 (checked Ch.2 and
# Ch.4); the 250%/400% weights apply in full from fiscal 2026.

# --- s.4.1.9 Retail ----------------------------------------------------------------
RETAIL_REGULATORY_RW: Final[float] = 0.75
"""CAR Ch.4 s.4.1.9 -- regulatory retail (non-transactor) 75% [CRE 20.68]."""
RETAIL_TRANSACTOR_RW_AS_PRINTED: Final[float] = 0.15
"""CAR Ch.4 s.4.1.9 -- as printed in the supplied text: "Regulatory retail exposures that arise
from exposures to transactors (as defined in paragraph 84) will be risk-weighted at 15%"."""
RETAIL_TRANSACTOR_RW_CONSERVATIVE: Final[float] = 0.45
"""Basel Framework CRE20.68(2) transactor weight -- the paragraph OSFI cross-references for the
retail risk weights."""
# TODO: VERIFY -- the CAR text supplied prints 15% for transactors while citing CRE20.68
# (45%). The paragraph conflicts with its own Basel cross-reference and is far below the Basel
# level, so the engine applies the conservative 45% placeholder by default; set the exposure
# flag "ca_apply_printed_transactor_rw" to apply the printed 15%.
RETAIL_OTHER_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.9 -- non-regulatory retail 100% [CRE 20.68]."""
RETAIL_MAX_AGGREGATE_CAD_M: Final[float] = 1.5
"""CAR Ch.4 s.4.1.9 (paragraph 83) -- regulatory retail low-value criterion: aggregated exposure
to one counterparty cannot exceed $1.50 million [CRE 20.65]."""
RETAIL_GRANULARITY_LIMIT: Final[float] = 0.002
"""CAR Ch.4 s.4.1.9 (paragraph 83) -- 0.2% granularity criterion [CRE 20.65]."""
QRR_MAX_INDIVIDUAL_CAD_M: Final[float] = 0.150
"""CAR Ch.4 s.4.1.9 (paragraph 84) -- QRR maximum exposure to a single individual $150,000."""
TRANSACTOR_MAX_ACCRUED_INTEREST_CAD: Final[float] = 50.0
"""CAR Ch.4 s.4.1.9 (paragraph 84) -- transactor if accrued interest over 12 months < $50."""
SMSB_RETAIL_RW: Final[float] = 0.75
"""CAR Ch.4 s.4.1.9 (paragraph 81) -- SMSB simplified 75% (revolving and non-revolving)."""

# --- s.4.1.11 Residential real estate (whole-loan approach; no loan-splitting) ------
RRE_GENERAL_LTV_BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.50, 0.20), (0.60, 0.25), (0.70, 0.30), (0.80, 0.35), (0.90, 0.40), (1.00, 0.50),
)
RRE_GENERAL_ABOVE_100_RW: Final[float] = 0.70
"""CAR Ch.4 s.4.1.11 Table 10 -- general RRE, LTV <=50 20%, <=60 25%, <=70 30%, <=80 35%,
<=90 40%, <=100 50%, >100 70% [CRE 20.82]. Upper bounds inclusive."""
RRE_INCOME_PRODUCING_LTV_BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.50, 0.30), (0.60, 0.35), (0.70, 0.45), (0.80, 0.50), (0.90, 0.60), (1.00, 0.75),
)
RRE_INCOME_PRODUCING_ABOVE_100_RW: Final[float] = 1.05
"""CAR Ch.4 s.4.1.11 Table 11 -- income-producing RRE, 30/35/45/50/60/75/105% [CRE 20.80, 20.84]."""
RRE_IPRE_NON_QUALIFYING_RW: Final[float] = 1.50
"""CAR Ch.4 s.4.1.11 (paragraph 101) -- IPRRE where paragraph 90 requirements are not met: 150%."""
RRE_NON_QUALIFYING_INDIVIDUAL_RW: Final[float] = 0.75
RRE_NON_QUALIFYING_SME_RW: Final[float] = 0.85
"""CAR Ch.4 s.4.1.11 -- RRE not meeting paragraph 90: counterparty RW (individuals/SBEs 75%,
SMEs 85%, others unsecured counterparty RW) [CRE 20.88-20.89]."""
VRFP_LTV_TRIGGER: Final[float] = 0.65
VRFP_MIN_CONSECUTIVE_MONTHS: Final[int] = 3
"""CAR Ch.4 s.4.1.11 (paragraph 101(i)) -- variable-rate fixed-payment mortgage with LTV above 65%
whose payments do not cover the interest component for three or more consecutive months due to
rate increases -> Table 11 (or 150% if paragraph 90 is not met). OSFI-specific."""
IPRE_INCOME_SHARE_THRESHOLD: Final[float] = 0.50
"""CAR Ch.4 s.4.1.11 / 4.1.12 -- materially dependent if more than 50% of the income used to
assess serviceability comes from the property [CRE 20.79]."""
HELOC_LTV_UNDRAWN_CCF: Final[float] = 0.75
"""CAR Ch.4 s.4.1.11 -- "In calculating the LTV ratio for purposes of HELOC, a 75% credit
conversion factor should be applied to the undrawn exposure of the HELOC"."""
JUNIOR_LIEN_MULTIPLIER: Final[float] = 1.25
"""CAR Ch.4 footnote 42 -- junior lien held by a different institution: base RW x 1.25 (not applied
in the lowest LTV bucket; capped at the non-qualifying RW)."""
SMSB_RRE_LTV_THRESHOLD: Final[float] = 0.80
SMSB_RRE_LOW_LTV_RW: Final[float] = 0.35
SMSB_RRE_HIGH_LTV_RW: Final[float] = 0.75
"""CAR Ch.4 s.4.1.11 (paragraph 96) -- SMSB simplified RRE: 35% LTV <= 80%, 75% LTV > 80%."""
REVERSE_MORTGAGE_BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.35, 0.30), (0.55, 0.35), (0.65, 0.45), (0.80, 0.60),
)
REVERSE_MORTGAGE_DEDUCTION_LTV: Final[float] = 0.80
REVERSE_MORTGAGE_ABOVE_80_REMAINDER_RW: Final[float] = 1.00
REVERSE_MORTGAGE_NON_QUALIFYING_REMAINDER_RW: Final[float] = 1.50
REVERSE_MORTGAGE_UNDRAWN_CCF: Final[float] = 0.40
"""CAR Ch.4 s.4.1.14 Table 14 -- reverse mortgages: <=35% 30%, <=55% 35%, <=65% 45%, <=80% 60%;
>80%: amount above 80% LTV deducted from CET1, remainder 100% (150% if non-qualifying);
undrawn amounts 40% CCF. OSFI-specific (no Basel counterpart)."""
NHA_MBS_RW: Final[float] = 0.00
"""CAR Ch.4 s.4.1.15 -- NHA MBS guaranteed by CMHC 0%."""
NHA_MBS_SALE_RECEIVABLE_RW: Final[float] = 2.50
"""CAR Ch.4 s.4.1.15 -- receivables from sale of mortgages under NHA MBS programs 250%."""

# --- s.4.1.12 Commercial real estate ------------------------------------------------
CRE_GENERAL_LTV_THRESHOLD: Final[float] = 0.60
CRE_GENERAL_CAP_RW: Final[float] = 0.60
"""CAR Ch.4 s.4.1.12 Table 12 -- LTV <= 60%: min(60%, RW of counterparty); LTV > 60%: RW of
counterparty [CRE 20.85]."""
CRE_COUNTERPARTY_INDIVIDUAL_RW: Final[float] = 0.75
CRE_COUNTERPARTY_SME_RW: Final[float] = 0.85
"""CAR Ch.4 s.4.1.12 -- "risk weight of the counterparty" = 75% individuals/SBEs, 85% SMEs,
otherwise
the unsecured counterparty RW."""
CRE_INCOME_PRODUCING_LTV_BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.60, 0.70), (0.80, 0.90),
)
CRE_INCOME_PRODUCING_ABOVE_80_RW: Final[float] = 1.10
"""CAR Ch.4 s.4.1.12 Table 13 -- IPCRE: <=60% 70%, <=80% 90%, >80% 110% [CRE 20.87-20.89]."""
CRE_IPRE_NON_QUALIFYING_RW: Final[float] = 1.50
"""CAR Ch.4 s.4.1.12 (paragraph 109) -- IPCRE not meeting paragraph 90: 150%."""
CRE_LOSS_TEST_60_LTV: Final[float] = 0.003
CRE_LOSS_TEST_OVERALL: Final[float] = 0.005
"""CAR Ch.4 footnote 51 -- IPCRE may use general CRE treatment if losses up to 60% LTV <= 0.3% and
overall CRE losses <= 0.5% of outstanding loans in any year."""
SMSB_CRE_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.12 (paragraph 105) -- SMSB simplified CRE 100%."""

# --- s.4.1.13 ADC -----------------------------------------------------------------------
ADC_RW: Final[float] = 1.50
ADC_RESIDENTIAL_QUALIFYING_RW: Final[float] = 1.00
ADC_SUBORDINATED_TRANCHE_RW: Final[float] = 3.00
"""CAR Ch.4 s.4.1.13 -- ADC 150%; qualifying residential ADC 100% (pre-sales > 50% or equity at
risk >= 25%; land LTV <= 60%); subordinated/mezzanine tranche 300% [CRE 20.90-20.91]."""
ADC_PRESALE_THRESHOLD: Final[float] = 0.50
ADC_EQUITY_AT_RISK_THRESHOLD: Final[float] = 0.25
ADC_LAND_LTV_MAX: Final[float] = 0.60
HIGH_RISE_MIN_STOREYS: Final[int] = 5
"""CAR Ch.4 s.4.1.13 -- high-rise (5+ storeys) eligible for 100% only with 50% pre-sales."""

# --- s.4.1.16 Currency mismatch ---------------------------------------------------------
CURRENCY_MISMATCH_MULTIPLIER: Final[float] = 1.5
CURRENCY_MISMATCH_RW_CAP: Final[float] = 1.50
CURRENCY_MISMATCH_FOREIGN_INCOME_SHARE: Final[float] = 0.10
CURRENCY_MISMATCH_HEDGE_COVERAGE: Final[float] = 0.90
"""CAR Ch.4 s.4.1.16 (paragraph 123) -- unhedged RRE exposures to individuals where > 10% of
qualifying income is in foreign currency: RW x 1.5, max 150%; hedges must cover >= 90% of the
instalment [CRE 20.92-20.93]. OSFI scope is RRE only (Basel: retail and RRE)."""

# --- s.4.1.18 CCFs -----------------------------------------------------------------------
CCF: Final[dict[OBSCategory, float]] = {
    OBSCategory.UNCONDITIONALLY_CANCELLABLE: 0.10,    # CRE 20.100
    OBSCategory.COMMITMENT_OTHER: 0.40,               # CRE 20.98 (regardless of maturity)
    OBSCategory.NIF_RUF: 0.50,                        # CRE 20.96
    OBSCategory.TRANSACTION_RELATED_CONTINGENT: 0.50,  # CRE 20.97
    OBSCategory.SHORT_TERM_TRADE_LC: 0.20,            # CRE 20.99
    OBSCategory.DIRECT_CREDIT_SUBSTITUTE: 1.00,       # CRE 20.95
    OBSCategory.SECURITIES_LENDING_COLLATERAL: 1.00,  # CRE 20.95
    OBSCategory.FORWARD_ASSET_PURCHASE: 1.00,         # CRE 20.95
    OBSCategory.OTHER_100: 1.00,                      # CRE 20.95 (other credit substitutes)
}
"""CAR Ch.4 s.4.1.18 -- 100% / 50% / 40% / 20% / 10% CCFs."""
CREDIT_CARD_UNDRAWN_CCF: Final[float] = 0.25
"""CAR Ch.4 s.4.1.18 -- "A 25% CCF will be applied to undrawn balances of credit card and charge
card exposures even if they meet the criteria in paragraph 135" (OSFI-specific)."""
UNSETTLED_OFF_BS_CCF: Final[float] = 1.00
"""CAR Ch.4 s.4.1.19 -- unsettled transactions not on balance sheet receive 100% CCF [CRE 70]."""

# --- s.4.1.21 Defaulted ---------------------------------------------------------------------
DEFAULTED_PROVISION_THRESHOLD: Final[float] = 0.20
DEFAULTED_LOW_PROVISION_RW: Final[float] = 1.50
DEFAULTED_HIGH_PROVISION_RW: Final[float] = 1.00
DEFAULTED_RRE_RW: Final[float] = 1.00
"""CAR Ch.4 s.4.1.21 -- 150% if specific provisions < 20% of outstanding, 100% if >= 20%
[CRE 20.106]; defaulted RRE not cash-flow dependent 100% (paragraph 144) [CRE 20.107]."""

# --- s.4.1.23 Other assets --------------------------------------------------------------------
OTHER_CASH_GOLD_RW: Final[float] = 0.00
OTHER_ITEMS_IN_TRANSIT_RW: Final[float] = 0.20
OTHER_ASSETS_RW: Final[float] = 1.00
OTHER_THRESHOLD_ITEMS_RW: Final[float] = 2.50
OTHER_SECURITISATION_IO_RW: Final[float] = 12.50
"""CAR Ch.4 s.4.1.23 -- cash/gold 0%; cheques in transit 20%; fixed assets, prepaid, other 100%;
threshold-deduction items below thresholds and PV of future spread income subject to prepayment
250%; credit-enhancing I/O strips 1250% [CRE 20.109-20.110]."""

# --- s.4.1.22 Funds ----------------------------------------------------------------------------
FUND_THIRD_PARTY_LTA_MULTIPLIER: Final[float] = 1.2
FUND_CCR_CVA_PROXY_MULTIPLIER: Final[float] = 1.5
FUND_PFE_PROXY_PCT_NOTIONAL: Final[float] = 0.15
FUND_LEVERAGE_RW_CAP: Final[float] = 12.50
"""CAR Ch.4 s.4.1.22 -- LTA third-party 1.2x; CCR x 1.5 in lieu of CVA; PFE proxy 15% of notional;
average RW x leverage capped at 1250% [CRE 60.4-60.14]."""

# --- s.4.3 CRM -----------------------------------------------------------------------------------
SIMPLE_APPROACH_RW_FLOOR: Final[float] = 0.20
"""CAR Ch.4 s.4.3.3(ii) -- simple approach 20% floor [CRE 22.33]."""
HFX_10D: Final[float] = 0.08
"""CAR Ch.4 s.4.3.3(iii) -- currency-mismatch haircut 8% (10-day, daily MTM) [CRE 22.52, 22.82]."""
NON_ELIGIBLE_SFT_HAIRCUT: Final[float] = 0.30
"""CAR Ch.4 s.4.3.3(iii) -- non-eligible instruments lent/posted in SFTs: 30% [CRE 22.54]."""
HOLDING_PERIOD_DAYS: Final[dict[str, int]] = {
    "REPO_STYLE": 5, "OTHER_CAPITAL_MARKET": 10, "SECURED_LENDING": 20,
}
"""CAR Ch.4 s.4.3.3(iii)(d) minimum holding periods [CRE 22.57]."""
MATURITY_MISMATCH_MIN_RESIDUAL_YEARS: Final[float] = 0.25
MATURITY_MISMATCH_MIN_ORIGINAL_YEARS: Final[float] = 1.0
MATURITY_MISMATCH_T_CAP_YEARS: Final[float] = 5.0
"""CAR Ch.4 s.4.3.1(iv) -- Pa = P x (t - 0.25)/(T - 0.25); protection recognised only with original
maturity >= 1 year and residual >= 3 months; T = min(5, residual maturity) [CRE 22.12-22.13]."""
CDS_NO_RESTRUCTURING_RECOGNITION: Final[float] = 0.60
"""CAR Ch.4 s.4.3.5(iv) -- 60% recognition when restructuring not covered [CRE 22.75]."""
PRIVATE_MI_DEDUCTIBLE_PCT_ORIGINAL: Final[float] = 0.10
PRIVATE_MI_DEDUCTIBLE_RW_FACTOR: Final[float] = 2.2
"""CAR Ch.4 s.4.3.5(vi) (paragraphs 274-275) -- privately insured mortgages with Government of
Canada backstop: deductible portion = 10% of original loan amount; may be risk-weighted as the
borrower exposure x 2.2 (footnote 97); backstop portion treated as sovereign."""

# Comprehensive-approach supervisory haircuts, 10-business-day holding period.
# CAR Ch.4 s.4.3.3(iii) haircut table (paragraph 240) [CRE 22.49]. Keys:
#   "<ISSUER>_<RATING>_<MATURITY>" with ISSUER in SOVEREIGN / OTHER / SECURITISATION,
#   RATING in AAA_AA (AAA to AA-/A-1), A_BBB (A+ to BBB-/A-2/A-3/P-3 and unrated bank
#   securities per para. 225), BB (BB+ to BB-, sovereigns only), MATURITY in LE1Y, 1_3Y, 3_5Y,
#   5_10Y, GT10Y.
_MATS: Final[tuple[str, ...]] = ("LE1Y", "1_3Y", "3_5Y", "5_10Y", "GT10Y")
_HC_AAA: Final[dict[str, tuple[float, float, float, float, float]]] = {
    "SOVEREIGN": (0.005, 0.02, 0.02, 0.04, 0.04),
    "OTHER": (0.01, 0.03, 0.04, 0.06, 0.12),
    "SECURITISATION": (0.02, 0.08, 0.08, 0.16, 0.16),
}
_HC_A_BBB: Final[dict[str, tuple[float, float, float, float, float]]] = {
    "SOVEREIGN": (0.01, 0.03, 0.03, 0.06, 0.06),
    "OTHER": (0.02, 0.04, 0.06, 0.12, 0.20),
    "SECURITISATION": (0.04, 0.12, 0.12, 0.24, 0.24),
}
SUPERVISORY_HAIRCUTS: Final[dict[str, float]] = {
    **{f"{iss}_AAA_AA_{m}": v
       for iss, vals in _HC_AAA.items() for m, v in zip(_MATS, vals, strict=True)},
    **{f"{iss}_A_BBB_{m}": v
       for iss, vals in _HC_A_BBB.items() for m, v in zip(_MATS, vals, strict=True)},
    **{f"SOVEREIGN_BB_{m}": 0.15 for m in _MATS},
    "MAIN_INDEX_EQUITY": 0.20,
    "GOLD": 0.20,
    "OTHER_LISTED_EQUITY": 0.30,
    "CASH": 0.00,
}
"""CAR Ch.4 s.4.3.3(iii) supervisory haircut table [CRE 22.49]. BB+ to BB- non-sovereign and
securitisation: not eligible (absent from the map)."""

# =========================================================================
#  Chapter 7 -- SA-CCR
# =========================================================================

SACCR_ALPHA: Final[float] = 1.4
"""CAR Ch.7 s.7.1.7 -- "EAD = alpha x (RC + PFE) ... alpha = 1.4" [CRE 52.1]. CAR prints no
exemption or alternative alpha for non-financial (commercial end-user) or pension counterparties."""
SACCR_MULTIPLIER_FLOOR: Final[float] = 0.05
"""CAR Ch.7 s.7.1.7.3 -- multiplier floored at 5% [CRE 52.23]."""
SACCR_MPOR_FLOOR_DAILY_BD: Final[int] = 10
SACCR_MPOR_FLOOR_LARGE_NETTING_SET_BD: Final[int] = 20
SACCR_MPOR_LARGE_NETTING_SET_TRADES: Final[int] = 5000
SACCR_MATURITY_FLOOR_BD: Final[int] = 10
SACCR_BUSINESS_DAYS_PER_YEAR: Final[int] = 250
"""CAR Ch.7 s.7.1.7.12 -- MF unmargined = sqrt(min(M,1y)/1y), M floored at 10 business days;
MF margined = 1.5 x sqrt(MPOR/1y); MPOR floors 10 bd (daily), 9 + N bd (non-daily), 20 bd for
netting sets > 5,000 trades or illiquid collateral [CRE 52.48-52.53]."""
SACCR_MARGINED_MF_SCALAR: Final[float] = 1.5

SACCR_SUPERVISORY_PARAMETERS: Final[dict[str, tuple[float, float | None, float]]] = {
    # key: (supervisory factor, correlation (None = not applicable), supervisory option vol)
    "IR": (0.005, None, 0.50),
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
"""CAR Ch.7 s.7.1.7 Table 2 -- Summary Table of Supervisory Parameters [CRE 52.72]."""

# =========================================================================
#  Chapter 8 -- CVA
# =========================================================================

BA_CVA_DISCOUNT_SCALAR: Final[float] = 0.65
"""CAR Ch.8 s.8.2.1 -- DS_BA-CVA = 0.65 [MAR 50.14]."""
BA_CVA_RHO: Final[float] = 0.50
"""CAR Ch.8 s.8.2.1 -- supervisory correlation rho = 50% [MAR 50.14]."""
BA_CVA_ALPHA: Final[float] = 1.4
"""CAR Ch.8 s.8.2.1 -- alpha = 1.4 in SCVA_c = (1/alpha) RW_c sum(M EAD DF) [MAR 50.15]."""
BA_CVA_BETA: Final[float] = 0.25
"""CAR Ch.8 s.8.2.2 -- K_full = beta K_reduced + (1 - beta) K_hedged, beta = 0.25 [MAR 50.20]."""
BA_CVA_DF_RATE: Final[float] = 0.05
"""CAR Ch.8 s.8.2.1 -- DF = (1 - exp(-0.05 M)) / (0.05 M) for non-IMM institutions [MAR 50.15]."""
BA_CVA_INDEX_RW_SCALAR: Final[float] = 0.7
"""CAR Ch.8 s.8.2.2 -- index hedge RW x 0.7 [MAR 50.24]."""
BA_CVA_HEDGE_CORRELATION: Final[dict[str, float]] = {
    "DIRECT": 1.00, "LEGAL_RELATION": 0.80, "SECTOR_REGION": 0.50,
}
"""CAR Ch.8 s.8.2.2 Table 2 -- r_hc [MAR 50.26]."""
BA_CVA_RISK_WEIGHTS: Final[dict[str, tuple[float, float]]] = {
    # sector key: (IG, HY and NR)
    "SOVEREIGN": (0.005, 0.020),
    "LOCAL_GOVERNMENT": (0.010, 0.040),
    "FINANCIAL": (0.050, 0.120),
    "BASIC_MATERIALS": (0.030, 0.070),
    "CONSUMER": (0.030, 0.085),
    "TECHNOLOGY": (0.020, 0.055),
    "HEALTH_CARE": (0.015, 0.050),
    "OTHER": (0.050, 0.120),
}
"""CAR Ch.8 s.8.2.1 Table 1 -- supervisory risk weights RW_c [MAR 50.16]:
sovereigns incl. central banks and MDBs; local government, government-backed non-financials,
education and public administration; financials incl. government-backed financials; basic
materials, energy, industrials, agriculture, manufacturing, mining and quarrying; consumer goods
and services, transportation and storage, administrative and support service activities;
technology, telecommunications; health care, utilities, professional and technical activities;
other sector."""
CVA_MATERIALITY_THRESHOLD_CAD_M: Final[float] = 150_000.0
"""CAR Ch.8 s.8.1 -- aggregate notional of non-centrally cleared derivatives <= $150 billion (CAD)
is below the materiality threshold; such an institution may set CVA capital = 100% of its CCR
capital requirement [MAR 50.9]."""
CVA_ALTERNATIVE_CCR_MULTIPLE: Final[float] = 1.00
"""CAR Ch.8 s.8.1 -- alternative treatment: 100% of the CCR capital requirement."""
SA_CVA_M_CVA: Final[float] = 1.0
"""CAR Ch.8 s.8.3.3 -- multiplier m_CVA set at 1 [MAR 50.41]."""
CVA_RWA_MULTIPLIER: Final[float] = 12.5
"""CAR Ch.8 s.8.1 -- RWA = 12.5 x CVA capital [MAR 50.1]."""
