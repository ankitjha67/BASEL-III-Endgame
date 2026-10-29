"""EU CRR3 regulatory parameters -- Regulation (EU) No 575/2013 as amended by Reg. (EU) 2024/1623.

Every constant used by the EU package is defined here with the article,
paragraph and table that states it. Two source texts are used:

* **CRR3** -- Regulation (EU) 2024/1623 of 31 May 2024 (OJ L, 19.6.2024),
  applicable from 1 January 2025 (Article 2). It is the authority for every
  article it inserts or replaces (Articles 92(3)-(6), 111, 115(-1)/(1),
  117(1), 120(1)-(2), 121, 122 Table 1 and (2), 122a, 123, 123a, 124-126a,
  127(2)-(3), 128, 129(4)-(5), 133, 134(3), 197, 224 Tables 1-4, 228,
  311a-324, 384-386, 465, 495-495h, 501(2), 501a(1), Annex I). Page numbers
  ("p.") refer to the OJ page numbering of the 189-page act.
* **Consolidated CRR** as of 09.07.2024 -- used only for provisions CRR3
  did not replace (Articles 92(1)-(1a), 114, 116(1)/(3), 117(2), 118,
  120(3), 127(1), 128 (pre-CRR3 version, for legacy equity weights), 131,
  134(1)-(2)/(4), 223(2)-(5), 224(2), 274(2), 278, 382(4), 501(1)).

Where neither text settles a value the constant carries ``# TODO: VERIFY``.
The Capital Requirements Directive (2013/36/EU) buffer rates are NOT in
either text and are flagged accordingly.

All monetary thresholds stated in EUR by the Regulation are kept in EUR
millions; the engine is currency-agnostic and expects inputs already
converted into the reporting currency in millions.
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import OBSCategory, RatingBucket

# =========================================================================
#  Credit quality steps (Article 136; CQS1-6 map one-to-one onto ratings)
# =========================================================================

CQS_OF_RATING: Final[dict[RatingBucket, int]] = {
    RatingBucket.AAA_TO_AA_MINUS: 1,
    RatingBucket.A_PLUS_TO_A_MINUS: 2,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS: 3,
    RatingBucket.BB_PLUS_TO_BB_MINUS: 4,
    RatingBucket.B_PLUS_TO_B_MINUS: 5,
    RatingBucket.BELOW_B_MINUS: 6,
}
"""Inverse of :func:`src.jurisdictions.base.rating_bucket_from_cqs` (Article 136)."""

# =========================================================================
#  Central governments / central banks -- Article 114 (consolidated)
# =========================================================================

SOVEREIGN_RW_BY_CQS: Final[dict[int, float]] = {
    1: 0.00,
    2: 0.20,
    3: 0.50,
    4: 1.00,
    5: 1.00,
    6: 1.50,
}
"""Article 114(2) Table 1."""
SOVEREIGN_RW_UNRATED: Final[float] = 1.00
"""Article 114(1): 100 % unless paragraphs 2 to 7 apply."""
SOVEREIGN_RW_ECB: Final[float] = 0.00
"""Article 114(3): exposures to the ECB."""
SOVEREIGN_RW_MS_DOMESTIC: Final[float] = 0.00
"""Article 114(4): Member State central governments/central banks, denominated and funded in
domestic currency."""

# =========================================================================
#  Regional governments / local authorities -- Article 115 (CRR3 point (45))
# =========================================================================

RGLA_RW_RATED_BY_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.50,
    3: 0.50,
    4: 1.00,
    5: 1.00,
    6: 1.50,
}
"""Article 115(-1) Table 1 (CRR3 p.42) -- rated RGLAs; also rated PSEs via Article 116(2)."""
RGLA_RW_UNRATED_BY_SOVEREIGN_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.50,
    3: 1.00,
    4: 1.00,
    5: 1.00,
    6: 1.50,
}
"""Article 115(1) Table 2 (CRR3 p.42) -- unrated RGLA by the sovereign's CQS."""
RGLA_RW_UNRATED_SOVEREIGN_UNRATED: Final[float] = 1.00
"""Article 115(1) second subparagraph: sovereign unrated -> 100 %."""
RGLA_RW_MS_DOMESTIC: Final[float] = 0.20
"""Article 115(5) (CRR3 p.43): Member State RGLA, domestic currency."""

# =========================================================================
#  Public sector entities -- Article 116
# =========================================================================

PSE_RW_UNRATED_BY_SOVEREIGN_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.50,
    3: 1.00,
    4: 1.00,
    5: 1.00,
    6: 1.50,
}
"""Article 116(1) Table 2 (consolidated, not replaced by CRR3)."""
PSE_RW_UNRATED_SOVEREIGN_UNRATED: Final[float] = 1.00
"""Article 116(1) second subparagraph."""
PSE_RW_SHORT_TERM: Final[float] = 0.20
"""Article 116(3): original maturity of three months or less."""
PSE_SHORT_TERM_MAX_MONTHS: Final[float] = 3.0
"""Article 116(3)."""

# =========================================================================
#  Multilateral development banks / international organisations
# =========================================================================

MDB_RW_RATED_BY_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.30,
    3: 0.50,
    4: 1.00,
    5: 1.00,
    6: 1.50,
}
"""Article 117(1) Table 1 (CRR3 point (47), p.43)."""
MDB_RW_UNRATED: Final[float] = 0.50
"""Article 117(1) first subparagraph (CRR3): unrated MDB not in paragraph 2."""
MDB_RW_LISTED: Final[float] = 0.00
"""Article 117(2) (consolidated): listed MDBs (IBRD, IFC, IDB, ADB, AfDB, CEB, NIB, CDB, EBRD,
EIB, EIF, MIGA, IFFIm, IsDB, IDA, AIIB)."""
INTERNATIONAL_ORG_RW: Final[float] = 0.00
"""Article 118 (consolidated): EU/Euratom, IMF, BIS, EFSF, ESM, MS-established IFIs."""

# =========================================================================
#  Institutions -- Articles 120, 121, 131 (CRR3 points (49), (50))
# =========================================================================

INSTITUTION_RW_RATED_BY_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.30,
    3: 0.50,
    4: 1.00,
    5: 1.00,
    6: 1.50,
}
"""Article 120(1) Table 1 (CRR3 p.43)."""
INSTITUTION_RW_RATED_SHORT_TERM_BY_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.20,
    3: 0.20,
    4: 0.50,
    5: 0.50,
    6: 1.50,
}
"""Article 120(2) Table 2 (CRR3 p.43): original maturity <= 3 months, or trade <= 6 months."""
INSTITUTION_SHORT_TERM_MAX_MONTHS: Final[float] = 3.0
"""Articles 120(2) and 121(3)(a)(i): original maturity of three months or less."""
INSTITUTION_TRADE_SHORT_TERM_MAX_MONTHS: Final[float] = 6.0
"""Articles 120(2) and 121(3)(a)(ii): movement of goods across borders, original maturity <= 6
months."""

INSTITUTION_SCRA_RW: Final[dict[str, float]] = {"A": 0.40, "B": 0.75, "C": 1.50}
"""Article 121(3) Table 1 (CRR3 p.45), 'Risk weight' row."""
INSTITUTION_SCRA_RW_SHORT_TERM: Final[dict[str, float]] = {"A": 0.20, "B": 0.50, "C": 1.50}
"""Article 121(3) Table 1 (CRR3 p.45), 'Risk weight for short-term exposures' row."""
INSTITUTION_SCRA_RW_GRADE_A_ENHANCED: Final[float] = 0.30
"""Article 121(3)(b): Grade A, not short term, CET1 ratio >= 14 % and leverage ratio >= 5 %."""
SCRA_ENHANCED_CET1_MIN: Final[float] = 0.14
"""Article 121(3)(b)(ii)."""
SCRA_ENHANCED_LEVERAGE_MIN: Final[float] = 0.05
"""Article 121(3)(b)(iii)."""

SHORT_TERM_ASSESSMENT_RW_BY_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.50,
    3: 1.00,
    4: 1.50,
    5: 1.50,
    6: 1.50,
}
"""Article 131 Table 7 (consolidated): institutions and corporates with a short-term credit
assessment."""

# Mapping of the jurisdiction-neutral short-term rating buckets onto CQS for Article 131.
# TODO: VERIFY -- the CQS mapping of short-term ratings is set by Commission Implementing
# Regulation (EU) 2016/1799 (not in the source texts); A-1/P-1 -> CQS1, A-2/P-2 -> CQS2,
# A-3/P-3 -> CQS3 and all others -> CQS4 is assumed (CQS4-6 all carry 150 % so the
# placeholder is conservative for every non-prime short-term rating).
SHORT_TERM_RATING_CQS: Final[dict[str, int]] = {
    "A-1/P-1": 1,
    "A-2/P-2": 2,
    "A-3/P-3": 3,
    "OTHERS": 4,
}

# =========================================================================
#  Covered bonds -- Article 129(4)-(5) (CRR3 point (59), p.57-58)
# =========================================================================

COVERED_BOND_RW_RATED_BY_CQS: Final[dict[int, float]] = {
    1: 0.10,
    2: 0.20,
    3: 0.20,
    4: 0.50,
    5: 0.50,
    6: 1.00,
}
"""Article 129(4) Table 1."""
COVERED_BOND_RW_FROM_ISSUER_RW: Final[dict[float, float]] = {
    0.20: 0.10,  # point (a)
    0.30: 0.15,  # point (aa)
    0.40: 0.20,  # point (ab)
    0.50: 0.25,  # point (b)
    0.75: 0.35,  # point (ba)
    1.00: 0.50,  # point (c)
    1.50: 1.00,  # point (d)
}
"""Article 129(5): unrated covered bond RW as a function of the issuing institution's senior
unsecured RW."""

# =========================================================================
#  Corporates -- Article 122 (CRR3 point (51))
# =========================================================================

CORPORATE_RW_RATED_BY_CQS: Final[dict[int, float]] = {
    1: 0.20,
    2: 0.50,
    3: 0.75,
    4: 1.00,
    5: 1.50,
    6: 1.50,
}
"""Article 122(1) Table 1 (CRR3 p.45)."""
CORPORATE_RW_UNRATED: Final[float] = 1.00
"""Article 122(2) (CRR3 p.46): 100 %; the pre-CRR3 sovereign floor is removed and there is NO 85
% SME weight."""

SME_TURNOVER_THRESHOLD_EUR_M: Final[float] = 50.0
"""Article 5, point (9) (CRR3 point (2)(b), p.22): annual turnover not exceeding EUR 50 000 000."""

# =========================================================================
#  Specialised lending -- Article 122a (CRR3 point (52))
# =========================================================================

SL_RW_RATED_BY_CQS: Final[dict[int, float]] = {1: 0.20, 2: 0.50, 3: 0.75, 4: 1.00, 5: 1.50, 6: 1.50}
"""Article 122a(2) Table 1 (CRR3 p.46)."""
SL_RW_OBJECT_FINANCE: Final[float] = 1.00
"""Article 122a(3)(a)."""
SL_RW_COMMODITIES_FINANCE: Final[float] = 1.00
"""Article 122a(3)(b)."""
SL_RW_PF_PRE_OPERATIONAL: Final[float] = 1.30
"""Article 122a(3)(c)(i)."""
SL_RW_PF_OPERATIONAL_HIGH_QUALITY: Final[float] = 0.80
"""Article 122a(3)(c)(ii): only where the Article 501a adjustment is not applied."""
SL_RW_PF_OPERATIONAL: Final[float] = 1.00
"""Article 122a(3)(c)(iii)."""
SL_RW_OF_HIGH_QUALITY_TRANSITIONAL: Final[float] = 0.80
"""Article 495b(3) (CRR3 p.177): high-quality unrated object finance, until 31 December 2032, if
501a not applied."""
SL_OF_HIGH_QUALITY_TRANSITIONAL_END_YEAR: Final[int] = 2032
"""Article 495b(3): 'until 31 December 2032'."""

# =========================================================================
#  Retail -- Articles 123, 123a (CRR3 points (53), (54))
# =========================================================================

RETAIL_RW: Final[float] = 0.75
"""Article 123(3)."""
RETAIL_TRANSACTOR_RW: Final[float] = 0.45
"""Article 123(3): transactor exposures."""
RETAIL_NON_QUALIFYING_NATURAL_PERSON_RW: Final[float] = 1.00
"""Article 123(4): natural persons not meeting all Article 123(1) criteria."""
RETAIL_PAYROLL_PENSION_LOAN_RW: Final[float] = 0.35
"""Article 123(5): pension/salary-backed loans meeting points (a)-(d)."""
RETAIL_MAX_AGGREGATE_EUR_M: Final[float] = 1.0
"""Article 123(1)(b): total amount owed not exceeding EUR 1 million (excluding RRE-secured up to
the property value)."""

CURRENCY_MISMATCH_MULTIPLIER: Final[float] = 1.5
"""Article 123a(1)."""
CURRENCY_MISMATCH_RW_CAP: Final[float] = 1.50
"""Article 123a(1): resulting risk weight not higher than 150 %."""
CURRENCY_MISMATCH_HEDGE_COVERAGE_MIN: Final[float] = 0.90
"""Article 123a(1)(b): hedges covering less than 90 % of each instalment do not remove the
mismatch."""

# =========================================================================
#  Immovable property -- Articles 124-126a (CRR3 points (55), (56))
# =========================================================================

RE_NON_QUALIFYING_IPRE_RW: Final[float] = 1.50
"""Article 124(1)(b): IPRE exposure not meeting Article 124(3), or the part above the lien."""
RE_SECURED_SHARE_OF_PROPERTY_VALUE: Final[float] = 0.55
"""Articles 125(1) and 126(1): the part of the exposure up to 55 % of the property value."""
RRE_SECURED_PART_RW: Final[float] = 0.20
"""Article 125(1): 20 % on the part up to 55 % of the property value (loan-splitting)."""
CRE_SECURED_PART_RW: Final[float] = 0.60
"""Article 126(1): 60 % on the part up to 55 % of the property value (loan-splitting)."""

RRE_IPRE_ETV_BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.50, 0.30),
    (0.60, 0.35),
    (0.80, 0.45),
    (0.90, 0.60),
    (1.00, 0.75),
    (float("inf"), 1.05),
)
"""Article 125(2) Table 1 (CRR3 p.54): (upper ETV bound inclusive, RW)."""

CRE_IPRE_ETV_BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.60, 0.70),
    (0.80, 0.90),
    (float("inf"), 1.10),
)
"""Article 126(2) Table 1 (CRR3 p.55): (upper ETV bound inclusive, RW)."""

IPRE_JUNIOR_LIEN_MULTIPLIER: Final[float] = 1.25
"""Article 124(6), third subparagraph: unknown ranking of other liens; not applied in the lowest
ETV bucket."""
RE_LOSS_RATE_HARD_TEST_EL: Final[float] = 0.003
"""Articles 125(2)/126(2) third subparagraph point (a): loss-rate limit 0,3 %."""
RE_LOSS_RATE_HARD_TEST_UL: Final[float] = 0.005
"""Articles 125(2)/126(2) third subparagraph point (b): loss-rate limit 0,5 %."""
RE_MACROPRUDENTIAL_RW_CEILING: Final[float] = 1.50
"""Article 124(9), fourth subparagraph: designated authority may not raise RE weights above 150
%."""

ADC_RW: Final[float] = 1.50
"""Article 126a(1)."""
ADC_RESIDENTIAL_QUALIFYING_RW: Final[float] = 1.00
"""Article 126a(2): residential ADC with pre-sales/pre-leases or substantial obligor equity at
risk."""

# =========================================================================
#  Defaulted exposures -- Article 127
# =========================================================================

DEFAULTED_RW_LOW_PROVISIONS: Final[float] = 1.50
"""Article 127(1)(a) (consolidated): specific CRAs < 20 % of the unsecured part."""
DEFAULTED_RW_HIGH_PROVISIONS: Final[float] = 1.00
"""Article 127(1)(b) (consolidated): specific CRAs >= 20 % of the unsecured part."""
DEFAULTED_PROVISION_THRESHOLD: Final[float] = 0.20
"""Article 127(1)."""
DEFAULTED_NON_IPRE_RE_RW: Final[float] = 1.00
"""Article 127(3) (CRR3 point (57)(b), p.56): defaulted non-IPRE RRE/CRE."""

# =========================================================================
#  Subordinated debt and equity -- Articles 128, 133, 48(4), 495a
# =========================================================================

SUBORDINATED_DEBT_RW: Final[float] = 1.50
"""Article 128(2) (CRR3 point (58), p.57)."""

EQUITY_RW_GENERAL: Final[float] = 2.50
"""Article 133(3) (CRR3 point (63), p.59)."""
EQUITY_RW_SPECULATIVE_UNLISTED: Final[float] = 4.00
"""Article 133(4): unlisted, short-term resale or venture capital (unless long-term >= 3 years)."""
EQUITY_RW_LEGISLATIVE_PROGRAMME: Final[float] = 1.00
"""Article 133(5): with prior permission, up to 10 % of own funds in aggregate."""
EQUITY_LEGISLATIVE_PROGRAMME_OWN_FUNDS_CAP: Final[float] = 0.10
"""Article 133(5)."""
EQUITY_RW_CENTRAL_BANK: Final[float] = 0.00
"""Article 133(6)."""
EQUITY_RW_NOT_DEDUCTED_FSE: Final[float] = 2.50
"""Article 48(4) (consolidated): significant FSE investments / DTAs below the threshold
deductions."""
EQUITY_LONG_TERM_HOLDING_YEARS: Final[float] = 3.0
"""Article 133(4) second subparagraph: long-term investment held (or intended) for three years or
longer."""

EQUITY_LEGACY_RW_GENERAL: Final[float] = 1.00
"""Pre-CRR3 Article 133(2) (consolidated 09.07.2024): 'Equity exposures shall be assigned
a risk weight of 100 %'.
Used as the 'risk weight applicable on 8 July 2024' for Article 495a(1)-(3)."""
EQUITY_LEGACY_RW_HIGH_RISK: Final[float] = 1.50
"""Pre-CRR3 Article 128(1)-(2)(a)-(b) (consolidated): venture capital / private equity 150 %."""
EQUITY_LEGACY_RW_CAP_495A1: Final[float] = 2.50
"""Article 495a(1): the legacy risk weight is capped at 250 %."""

EQUITY_PHASE_IN_GENERAL: Final[dict[int, float]] = {
    2025: 1.00,
    2026: 1.30,
    2027: 1.60,
    2028: 1.90,
    2029: 2.20,
}
"""Article 495a(1) (CRR3 p.176): floor schedule for Article 133(3) equity."""
EQUITY_PHASE_IN_SPECULATIVE: Final[dict[int, float]] = {
    2025: 1.00,
    2026: 1.60,
    2027: 2.20,
    2028: 2.80,
    2029: 3.40,
}
"""Article 495a(2) (CRR3 p.176): schedule for Article 133(4) equity."""

# =========================================================================
#  Other items -- Article 134, Article 113(5)
# =========================================================================

OTHER_ITEMS_TANGIBLE_RW: Final[float] = 1.00
"""Article 134(1) (consolidated)."""
OTHER_ITEMS_PREPAYMENTS_RW: Final[float] = 1.00
"""Article 134(2) (consolidated)."""
OTHER_ITEMS_CASH_RW: Final[float] = 0.00
"""Article 134(3) (CRR3 point (64)): cash owned and held, or in transit, and equivalent cash
items."""
OTHER_ITEMS_CASH_IN_COLLECTION_RW: Final[float] = 0.20
"""Article 134(3) (CRR3 point (64))."""
OTHER_ITEMS_GOLD_RW: Final[float] = 0.00
"""Article 134(4) (consolidated): gold bullion in own vaults / allocated, to the extent backed by
bullion liabilities."""
RESIDUAL_RW: Final[float] = 1.00
"""Article 113(5) (CRR3 point (44)(c)): any item for which no risk weight is provided."""

# =========================================================================
#  Off-balance-sheet items -- Article 111(2) and Annex I (CRR3 points (42), (255))
# =========================================================================

CCF_BY_BUCKET: Final[dict[int, float]] = {1: 1.00, 2: 0.50, 3: 0.40, 4: 0.20, 5: 0.10}
"""Article 111(2)(a)-(e) (CRR3 p.40)."""

OBS_BUCKET: Final[dict[OBSCategory, int]] = {
    OBSCategory.DIRECT_CREDIT_SUBSTITUTE: 1,  # Annex I bucket 1(a)
    OBSCategory.SECURITIES_LENDING_COLLATERAL: 1,  # Annex I bucket 1(c)
    OBSCategory.FORWARD_ASSET_PURCHASE: 1,  # Annex I bucket 1(d)
    OBSCategory.OTHER_100: 1,  # Annex I bucket 1(e)
    OBSCategory.NIF_RUF: 2,  # Annex I bucket 2(a)
    OBSCategory.TRANSACTION_RELATED_CONTINGENT: 2,  # Annex I bucket 2(b) (non-trade-finance)
    OBSCategory.COMMITMENT_OTHER: 3,  # Annex I bucket 3(a) regardless of maturity
    OBSCategory.SHORT_TERM_TRADE_LC: 4,  # Annex I bucket 4(a)(iii)
    OBSCategory.UNCONDITIONALLY_CANCELLABLE: 5,  # Annex I bucket 5(a)-(b)
}
"""Annex I classification of off-balance-sheet items (CRR3 Annex, pp.188-189)."""
TRADE_FINANCE_CONTINGENT_BUCKET: Final[int] = 4
"""Annex I bucket 4(a)(i)-(ii): trade-finance warranties, tender/performance bonds and non-
credit-substitute SBLCs."""
CCF_ARTICLE_5_10_EXEMPT: Final[float] = 0.00
"""Article 111(4) second subparagraph: arrangements meeting Article 5, point (10)(a)-(e)."""

UCC_TRANSITIONAL_FACTOR: Final[dict[int, float]] = {
    2025: 0.00,
    2026: 0.00,
    2027: 0.00,
    2028: 0.00,
    2029: 0.00,
    2030: 0.25,
    2031: 0.50,
    2032: 0.75,
}
"""Article 495d(1) (CRR3 p.179): multiplier on the bucket-5 percentage; 1.0 from 2033."""

# =========================================================================
#  Credit risk mitigation -- Articles 223-224 (FCCM)
# =========================================================================

# Article 224(1) Table 1 (CRR3 point (130), pp.94-95): (20-day, 10-day, 5-day) volatility
# adjustments in decimals, keyed by (issuer class, CQS group, residual maturity band).
# Issuer class: "SOV" = Article 197(1)(b); "OTH" = Article 197(1)(c)-(d); "SEC" = 197(1)(h).
# Maturity bands: "M1" m<=1, "M3" 1<m<=3, "M5" 3<m<=5, "M10" 5<m<=10, "M10P" m>10.
HAIRCUT_DEBT: Final[dict[tuple[str, str, str], tuple[float, float, float]]] = {
    ("SOV", "CQS1", "M1"): (0.00707, 0.005, 0.00354),
    ("SOV", "CQS1", "M3"): (0.02828, 0.02, 0.01414),
    ("SOV", "CQS1", "M5"): (0.02828, 0.02, 0.01414),
    ("SOV", "CQS1", "M10"): (0.05657, 0.04, 0.02828),
    ("SOV", "CQS1", "M10P"): (0.05657, 0.04, 0.02828),
    ("SOV", "CQS2_3", "M1"): (0.01414, 0.01, 0.00707),
    ("SOV", "CQS2_3", "M3"): (0.04243, 0.03, 0.02121),
    ("SOV", "CQS2_3", "M5"): (0.04243, 0.03, 0.02121),
    ("SOV", "CQS2_3", "M10"): (0.08485, 0.06, 0.04243),
    ("SOV", "CQS2_3", "M10P"): (0.08485, 0.06, 0.04243),
    ("SOV", "CQS4", "ALL"): (0.21213, 0.15, 0.10607),
    ("OTH", "CQS1", "M1"): (0.01414, 0.01, 0.00707),
    ("OTH", "CQS1", "M3"): (0.04243, 0.03, 0.02121),
    ("OTH", "CQS1", "M5"): (0.05657, 0.04, 0.02828),
    ("OTH", "CQS1", "M10"): (0.08485, 0.06, 0.04243),
    ("OTH", "CQS1", "M10P"): (0.16971, 0.12, 0.08485),
    ("OTH", "CQS2_3", "M1"): (0.02828, 0.02, 0.01414),
    ("OTH", "CQS2_3", "M3"): (0.05657, 0.04, 0.02828),
    ("OTH", "CQS2_3", "M5"): (0.08485, 0.06, 0.04243),
    ("OTH", "CQS2_3", "M10"): (0.16971, 0.12, 0.08485),
    ("OTH", "CQS2_3", "M10P"): (0.28284, 0.20, 0.14142),
    ("SEC", "CQS1", "M1"): (0.02828, 0.02, 0.01414),
    ("SEC", "CQS1", "M3"): (0.11314, 0.08, 0.05657),
    ("SEC", "CQS1", "M5"): (0.11314, 0.08, 0.05657),
    ("SEC", "CQS1", "M10"): (0.22627, 0.16, 0.11314),
    ("SEC", "CQS1", "M10P"): (0.22627, 0.16, 0.11314),
    ("SEC", "CQS2_3", "M1"): (0.05657, 0.04, 0.02828),
    ("SEC", "CQS2_3", "M3"): (0.16971, 0.12, 0.08485),
    ("SEC", "CQS2_3", "M5"): (0.16971, 0.12, 0.08485),
    ("SEC", "CQS2_3", "M10"): (0.33941, 0.24, 0.16971),
    ("SEC", "CQS2_3", "M10P"): (0.33941, 0.24, 0.16971),
}

HAIRCUT_SHORT_TERM_DEBT: Final[dict[tuple[str, str], tuple[float, float, float]]] = {
    ("SOV", "CQS1"): (0.00707, 0.005, 0.00354),
    ("SOV", "CQS2_3"): (0.01414, 0.01, 0.00707),
    ("OTH", "CQS1"): (0.01414, 0.01, 0.00707),
    ("OTH", "CQS2_3"): (0.02828, 0.02, 0.01414),
    ("SEC", "CQS1"): (0.02828, 0.02, 0.01414),
    ("SEC", "CQS2_3"): (0.05657, 0.04, 0.02828),
}
"""Article 224(1) Table 2 (CRR3 p.95): short-term credit assessments."""

HAIRCUT_OTHER: Final[dict[str, tuple[float, float, float]]] = {
    "MAIN_INDEX_EQUITY": (0.28284, 0.20, 0.14142),
    "OTHER_LISTED_EQUITY": (0.42426, 0.30, 0.21213),
    "CASH": (0.0, 0.0, 0.0),
    "GOLD": (0.28284, 0.20, 0.14142),
}
"""Article 224(1) Table 3 (CRR3 p.95). Main index convertibles share the equity row."""

HAIRCUT_FX: Final[tuple[float, float, float]] = (0.11314, 0.08, 0.05657)
"""Article 224(1) Table 4 (CRR3 p.95): Hfx."""

LIQUIDATION_PERIOD_INDEX: Final[dict[int, int]] = {20: 0, 10: 1, 5: 2}
"""Column index into the (20-day, 10-day, 5-day) tuples."""
LIQUIDATION_PERIOD_SECURED_LENDING: Final[int] = 20
"""Article 224(2)(a) (consolidated): secured lending transactions -- 20 business days."""
LIQUIDATION_PERIOD_REPO: Final[int] = 5
"""Article 224(2)(b): repurchase / securities lending or borrowing -- 5 business days."""
LIQUIDATION_PERIOD_CAPITAL_MARKET: Final[int] = 10
"""Article 224(2)(c): other capital-market-driven transactions -- 10 business days."""

# =========================================================================
#  Supporting factors -- Articles 501, 501a (retained by CRR3)
# =========================================================================

SME_SF_THRESHOLD_EUR_M: Final[float] = 2.5
"""Article 501(1) (consolidated): EUR 2 500 000."""
SME_SF_FACTOR_BELOW: Final[float] = 0.7619
"""Article 501(1): factor on the part of E* up to EUR 2.5m."""
SME_SF_FACTOR_ABOVE: Final[float] = 0.85
"""Article 501(1): factor on the part of E* above EUR 2.5m."""
INFRASTRUCTURE_SF: Final[float] = 0.75
"""Article 501a(1) (consolidated; points (a), (f), (o) amended by CRR3 point (247))."""

# =========================================================================
#  Output floor -- Article 92(3), Article 465 (CRR3 points (28), (237))
# =========================================================================

OUTPUT_FLOOR_FACTOR: Final[float] = 0.725
"""Article 92(3): x = 72,5 %."""
OUTPUT_FLOOR_FIRST_YEAR: Final[int] = 2025
"""CRR3 Article 2: the Regulation applies from 1 January 2025 (floor not in force before)."""
OUTPUT_FLOOR_TRANSITIONAL: Final[dict[int, float]] = {
    2025: 0.50,
    2026: 0.55,
    2027: 0.60,
    2028: 0.65,
    2029: 0.70,
}
"""Article 465(1)(a)-(e) (CRR3 p.172)."""
OUTPUT_FLOOR_CAP_MULTIPLE: Final[float] = 1.25
"""Article 465(2) (CRR3 p.172, formula rendered as an image in the OJ):
TREA = min{max{U-TREA; x * S-TREA}; 125 % * U-TREA}."""
OUTPUT_FLOOR_CAP_END_YEAR: Final[int] = 2029
"""Article 465(2): 'until 31 December 2029'."""
FLOOR_UNRATED_CORPORATE_RW: Final[float] = 0.65
"""Article 465(3): unrated corporates with IRB PD <= 0,5 %, until 31 December 2032 (S-TREA only)."""
FLOOR_UNRATED_CORPORATE_PD_MAX: Final[float] = 0.005
"""Article 465(3)."""
FLOOR_UNRATED_CORPORATE_END_YEAR: Final[int] = 2032
"""Article 465(3)."""
FLOOR_RRE_SECURED_RW: Final[float] = 0.10
"""Article 465(5)(a): part up to 55 % of property value, until 31 December 2032 (S-TREA only, MS
discretion)."""
FLOOR_RRE_SECURED_END_YEAR: Final[int] = 2032
"""Article 465(5)(a)."""
FLOOR_RRE_REMAINDER_SHARE: Final[float] = 0.80
"""Article 465(5)(b): remaining part up to 80 % of property value."""
FLOOR_RRE_REMAINDER_RW: Final[dict[int, float]] = {
    2025: 0.45,
    2026: 0.45,
    2027: 0.45,
    2028: 0.45,
    2029: 0.45,
    2030: 0.525,
    2031: 0.60,
    2032: 0.675,
}
"""Article 465(5)(b) (45 % until 2029) and Article 465(9)(a)-(c) (52,5 % / 60 % / 67,5 % in
2030-2032)."""
FLOOR_RRE_LOSS_RATE_MAX: Final[float] = 0.0025
"""Article 465(8)(d): average losses over eight years <= 0,25 %."""
FLOOR_SA_CCR_ALPHA_TRANSITIONAL: Final[float] = 1.0
"""Article 465(4): alpha replaced by 1 in S-TREA until 31 December 2029 where IMM is used for
U-TREA."""
FLOOR_SA_CCR_ALPHA_END_YEAR: Final[int] = 2029
"""Article 465(4)."""
FLOOR_SEC_P_FACTOR: Final[dict[str, float]] = {"ARTICLE_262": 0.25, "ARTICLE_261": 0.5}
"""Article 465(13)(a)-(b): SEC-SA p factor in S-TREA until 31 December 2032."""
FLOOR_SEC_P_END_YEAR: Final[int] = 2032
"""Article 465(13): 'until 31 December 2032'."""

# =========================================================================
#  Own funds requirements and buffers -- Article 92(1)-(1a); CRD (not in sources)
# =========================================================================

CET1_MINIMUM: Final[float] = 0.045
"""Article 92(1)(a) (consolidated)."""
TIER1_MINIMUM: Final[float] = 0.06
"""Article 92(1)(b)."""
TOTAL_CAPITAL_MINIMUM: Final[float] = 0.08
"""Article 92(1)(c)."""
LEVERAGE_MINIMUM: Final[float] = 0.03
"""Article 92(1)(d)."""
GSII_LEVERAGE_BUFFER_SHARE: Final[float] = 0.50
"""Article 92(1a): leverage ratio buffer = total exposure measure x 50 % of the G-SII buffer
rate."""
OWN_FUNDS_TO_RWA: Final[float] = 12.5
"""Article 92(6)(b) (CRR3 p.31): own funds requirements for points (b)-(f) multiplied by 12,5."""

# TODO: VERIFY -- capital conservation buffer rate is set by Article 129 of Directive 2013/36/EU
# (CRD), which is not among the source texts. 2.5 % used as placeholder.
CAPITAL_CONSERVATION_BUFFER: Final[float] = 0.025

# TODO: VERIFY -- G-SII buffer rates per sub-category are set by Article 131(4) and (9) of
# Directive 2013/36/EU (not in the source texts). Placeholder values for sub-categories 1-5.
GSII_BUFFER_BY_SUBCATEGORY: Final[dict[int, float]] = {
    1: 0.010,
    2: 0.015,
    3: 0.020,
    4: 0.025,
    5: 0.035,
}

# TODO: VERIFY -- O-SII buffer ceiling is set by Article 131(5)/(5a) CRD (not in the source texts).
OSII_BUFFER_CAP: Final[float] = 0.03

# TODO: VERIFY -- CCyB range is set by Article 136 CRD (not in the source texts); the engine
# takes the institution-specific CCyB rate as an input and only checks it is non-negative.
CCYB_MAX_STANDARD: Final[float] = 0.025

# =========================================================================
#  Operational risk -- Articles 312-324 (CRR3 point (155))
# =========================================================================

BIC_BUCKET_1_UPPER_EUR_BN: Final[float] = 1.0
"""Article 313 (CRR3 p.105, formula image): BI <= 1."""
BIC_BUCKET_2_UPPER_EUR_BN: Final[float] = 30.0
"""Article 313: 1 < BI <= 30."""
BIC_COEFF_1: Final[float] = 0.12
"""Article 313: 0,12 * BI."""
BIC_COEFF_2: Final[float] = 0.15
"""Article 313: 0,12 + 0,15 * (BI - 1)."""
BIC_COEFF_3: Final[float] = 0.18
"""Article 313: 4,47 + 0,18 * (BI - 30)."""
BIC_CONSTANT_BUCKET_3_EUR_BN: Final[float] = 4.47
"""Article 313: the constant 4,47 (= 0,12 + 0,15 * 29)."""
ILDC_ASSET_CAP: Final[float] = 0.0225
"""Article 314(2) (CRR3 p.106, formula image): ILDC = min(IC, 0,0225 * AC) + DC."""
OPRISK_LOSS_DATA_BI_THRESHOLD_EUR_M: Final[float] = 750.0
"""Article 316(1): institutions with BI >= EUR 750 million calculate the annual operational risk
loss."""
OPRISK_LOSS_DATA_WAIVER_BI_EUR_M: Final[float] = 1000.0
"""Article 316(1) second subparagraph: waiver possible where BI <= EUR 1 billion."""
OPRISK_LOSS_THRESHOLD_EUR: Final[float] = 20_000.0
"""Article 319(1): net loss >= EUR 20 000 (in EUR, not millions)."""
OPRISK_LOSS_THRESHOLD_DISCLOSURE_EUR: Final[float] = 100_000.0
"""Article 319(2): EUR 100 000 for Article 446 disclosure."""
OPRISK_LOSS_WINDOW_YEARS: Final[int] = 10
"""Article 318(1): 10-year window for net loss calculation."""
OPRISK_ILM: Final[float] = 1.0
"""Article 312: the own funds requirement IS the BIC -- no loss component / ILM in the EU
formula."""

# =========================================================================
#  SA-CCR -- Articles 274, 278 (consolidated)
# =========================================================================

SACCR_ALPHA: Final[float] = 1.4
"""Article 274(2) (consolidated, not amended by CRR3)."""
SACCR_MULTIPLIER_FLOOR: Final[float] = 0.05
"""Article 278(3): Floor_m = 5 %."""

# =========================================================================
#  CVA -- Articles 382, 384-386 (CRR3 points (198), (202))
# =========================================================================

BACVA_DS: Final[float] = 0.65
"""Article 384(2): DS_CVA = 0,65."""
BACVA_BETA: Final[float] = 0.25
"""Article 384(2): beta = 0,25."""
BACVA_ALPHA: Final[float] = 1.4
"""Article 384(2): alpha = 1,4."""
BACVA_RHO: Final[float] = 0.5
"""Article 384(2): rho = 0,5."""
BACVA_DF_RATE: Final[float] = 0.05
"""Article 384(2): DF = (1 - exp(-0,05 M)) / (0,05 M)."""
BACVA_INDEX_RW_SCALAR: Final[float] = 0.7
"""Article 384(2): RW_i^ind = Table 1 RW (or weighted average) x 0,7."""

BACVA_RW: Final[dict[str, tuple[float, float]]] = {
    "SOVEREIGN": (0.005, 0.020),
    "RGLA_PSE": (0.010, 0.040),
    "FINANCIAL": (0.050, 0.120),
    "BASIC_MATERIALS": (0.030, 0.070),
    "CONSUMER": (0.030, 0.085),
    "TECHNOLOGY": (0.020, 0.055),
    "HEALTHCARE": (0.015, 0.050),
    "OTHER": (0.050, 0.120),
}
"""Article 384(2) Table 1 (CRR3 p.157): sector -> (CQS 1-3, CQS 4-6 and not rated)."""

BACVA_HEDGE_CORRELATION: Final[dict[str, float]] = {"DIRECT": 1.00, "LEGAL": 0.80, "SECTOR": 0.50}
"""Article 384(2) Table 2 (CRR3 p.158): Article 386(3)(a)(i)/(ii)/(iii)."""

CVA_EXEMPTION_KEYS: Final[tuple[str, ...]] = (
    "nfc_below_clearing_threshold",  # Article 382(4)(a)
    "intragroup",  # Article 382(4)(b)
    "pension_scheme_transitional",  # Article 382(4)(c)
    "emir_exempt_or_zero_rw",  # Article 382(4)(d)
    "qccp_or_client_clearing",  # Article 382(3)
)
"""Article 382(3)-(4) (consolidated) exemptions from the own funds requirements for CVA risk."""
