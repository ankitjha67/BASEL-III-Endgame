"""EU CRR3 Pillar 1 parameters: securitisation, SA-CVA, leverage, large exposures, CCPs.

Every constant is transcribed from the supplied legal texts with the article,
paragraph and table that states it:

* **CRR3** -- Regulation (EU) 2024/1623 (OJ L, 19.6.2024). Authority for the
  articles it inserts or replaces: Articles 382a, 383-383z (SA-CVA, point (200)-(201),
  OJ pp.132-154), 394(2), 395(2a), 400(1)(i), 400(2)(i), 402(1)-(2) (points
  (203)-(206), pp.159-160), 429(5)-(6), 429a(1)(ca)/(da), 429c(3)-(6), 429f(1)/(3),
  429g(1) (points (209)-(213), pp.160-161), 465(13). "p." = OJ page of the act.
* **Consolidated CRR** (02013R0575, version 09.07.2024) -- for the unamended
  articles: securitisation Articles 242-270a (cons. pp.296-335), CCP Articles
  300-311 (pp.394-402), large exposures Articles 387-403 (pp.552-570) and the
  leverage ratio Articles 429-429g (pp.628-642). "cons. p." = page of that PDF.

Formulas printed as images in the extracted text were read from the rendered
PDF pages (cons. pp.318-319, 331-332; CRR3 OJ pp.137-138, 147).

Where neither text settles a value the constant carries ``# TODO: VERIFY``. All
EUR thresholds are kept in EUR millions; the calculators convert them with a
caller-supplied reporting-currency-per-EUR rate.
"""

from __future__ import annotations

from typing import Final

# =========================================================================
#  Securitisation -- Articles 242-270a (consolidated CRR, not amended by CRR3)
# =========================================================================

SEC_RW_MAX: Final[float] = 12.50
"""Articles 254(7), 259(1), 261(1): 1 250 % risk weight."""
SEC_RW_FLOOR: Final[float] = 0.15
"""Articles 259(1) and 261(1): 'in all cases subject to a floor of 15 %'; Article 263(6) for
non-senior SEC-ERBA tranches."""
SEC_RW_FLOOR_STS_SENIOR: Final[float] = 0.10
"""Articles 260 and 262: 'risk-weight floor for senior securitisation positions = 10 %'."""
SEC_RW_FLOOR_RESEC: Final[float] = 1.00
"""Article 269(1)(c): re-securitisation risk-weight floor of 100 %."""
SEC_RW_FLOOR_NPE: Final[float] = 1.00
"""Article 269a(2): NPE securitisation floor of 100 %, except when Article 263 is applied."""
SEC_RW_NPE_QUALIFYING_SENIOR: Final[float] = 1.00
"""Article 269a(3): senior position in a qualifying traditional NPE securitisation = 100 %."""
SEC_RW_NPE_LOOK_THROUGH_FLOOR: Final[float] = 0.50
"""Article 269a(6): look-through below 100 % allowed for that senior position, floor 50 %."""
SEC_NPE_QUALIFYING_DISCOUNT_MIN: Final[float] = 0.50
"""Article 269a(1)(b): non-refundable purchase price discount of at least 50 %."""
SEC_CAPITAL_TO_RW: Final[float] = 12.5
"""Articles 259(1), 261(1): the 12,5 multiplier on K (and Article 267(3)(a) EL x 12,5)."""
SEC_OWN_FUNDS_RATIO: Final[float] = 0.08
"""Article 255(2)/(6): K_IRB / K_SA = RWEA x 8 % / exposure value; Article 269a(5) CR_max."""

SEC_SA_P: Final[float] = 1.0
"""Article 261(1): p = 1 for a securitisation exposure that is not a re-securitisation."""
SEC_SA_P_STS: Final[float] = 0.5
"""Article 262: p = 0,5 for STS positions under the SEC-SA."""
SEC_SA_P_RESEC: Final[float] = 1.5
"""Article 269(1)(b): p = 1,5 for re-securitisations."""
SEC_SA_W_LGD: Final[float] = 0.5
"""Article 261(2): K_A = (1 - W) K_SA + W x 0,5."""
SEC_SA_UNKNOWN_DELINQUENCY_MAX: Final[float] = 0.05
"""Article 261(2): delinquency status unknown for more than 5 % of the pool -> 1 250 %."""

SEC_IRBA_P_FLOOR: Final[float] = 0.3
"""Article 259(1): p = max[0,3; A + B (1/N) + C K_IRB + D LGD + E M_T]."""
SEC_IRBA_STS_SCALAR: Final[float] = 0.5
"""Article 260: p = max[0,3; 0,5 (A + B (1/N) + C K_IRB + D LGD + E M_T)]."""
SEC_IRBA_GRANULAR_N: Final[float] = 25.0
"""Article 259(1) look-up table: granular where N >= 25."""
SEC_IRBA_MIXED_POOL_MIN_SHARE: Final[float] = 0.95
"""Article 258(1)(a): K_IRB computable on at least 95 % of the underlying exposure amount."""

SEC_IRBA_P_TABLE: Final[dict[tuple[str, str], tuple[float, float, float, float, float]]] = {
    ("NON_RETAIL", "SENIOR_GRANULAR"): (0.0, 3.56, -1.85, 0.55, 0.07),
    ("NON_RETAIL", "SENIOR_NON_GRANULAR"): (0.11, 2.61, -2.91, 0.68, 0.07),
    ("NON_RETAIL", "NON_SENIOR_GRANULAR"): (0.16, 2.87, -1.03, 0.21, 0.07),
    ("NON_RETAIL", "NON_SENIOR_NON_GRANULAR"): (0.22, 2.35, -2.46, 0.48, 0.07),
    ("RETAIL", "SENIOR"): (0.0, 0.0, -7.48, 0.71, 0.24),
    ("RETAIL", "NON_SENIOR"): (0.0, 0.0, -5.78, 0.55, 0.27),
}
"""Article 259(1) look-up table of (A, B, C, D, E) (cons. p.319)."""

SEC_MT_FLOOR_YEARS: Final[float] = 1.0
"""Article 257(2): tranche maturity floor of 1 year."""
SEC_MT_CAP_YEARS: Final[float] = 5.0
"""Article 257(2): tranche maturity cap of 5 years."""
SEC_MT_LEGAL_MATURITY_FACTOR: Final[float] = 0.8
"""Article 257(1)(b): M_T = 1 + (M_L - 1) x 80 %."""

SEC_ERBA_THICKNESS_CAP: Final[float] = 0.5
"""Article 263(5): RW x [1 - min(T; 50 %)], T = D - A."""

SEC_ERBA_SHORT_TERM: Final[dict[int, float]] = {1: 0.15, 2: 0.50, 3: 1.00}
"""Article 263(2) Table 1 (CQS 1-3); all other ratings 1 250 %."""
SEC_ERBA_SHORT_TERM_STS: Final[dict[int, float]] = {1: 0.10, 2: 0.30, 3: 0.60}
"""Article 264(2) Table 3 (CQS 1-3); all other ratings 1 250 %."""

# Article 263(3) Table 2 (cons. p.323): CQS -> (senior 1y, senior 5y, non-senior 1y, non-senior 5y)
SEC_ERBA_LONG_TERM: Final[dict[int, tuple[float, float, float, float]]] = {
    1: (0.15, 0.20, 0.15, 0.70),
    2: (0.15, 0.30, 0.15, 0.90),
    3: (0.25, 0.40, 0.30, 1.20),
    4: (0.30, 0.45, 0.40, 1.40),
    5: (0.40, 0.50, 0.60, 1.60),
    6: (0.50, 0.65, 0.80, 1.80),
    7: (0.60, 0.70, 1.20, 2.10),
    8: (0.75, 0.90, 1.70, 2.60),
    9: (0.90, 1.05, 2.20, 3.10),
    10: (1.20, 1.40, 3.30, 4.20),
    11: (1.40, 1.60, 4.70, 5.80),
    12: (1.60, 1.80, 6.20, 7.60),
    13: (2.00, 2.25, 7.50, 8.60),
    14: (2.50, 2.80, 9.00, 9.50),
    15: (3.10, 3.40, 10.50, 10.50),
    16: (3.80, 4.20, 11.30, 11.30),
    17: (4.60, 5.05, 12.50, 12.50),
}
"""Article 263(3) Table 2; 'All other' = 1 250 % in every column."""

# Article 264(3) Table 4 (cons. p.325): STS
SEC_ERBA_LONG_TERM_STS: Final[dict[int, tuple[float, float, float, float]]] = {
    1: (0.10, 0.10, 0.15, 0.40),
    2: (0.10, 0.15, 0.15, 0.55),
    3: (0.15, 0.20, 0.15, 0.70),
    4: (0.15, 0.25, 0.25, 0.80),
    5: (0.20, 0.30, 0.35, 0.95),
    6: (0.30, 0.40, 0.60, 1.35),
    7: (0.35, 0.40, 0.95, 1.70),
    8: (0.45, 0.55, 1.50, 2.25),
    9: (0.55, 0.65, 1.80, 2.55),
    10: (0.70, 0.85, 2.70, 3.45),
    11: (1.20, 1.35, 4.05, 5.00),
    12: (1.35, 1.55, 5.35, 6.55),
    13: (1.70, 1.95, 6.45, 7.40),
    14: (2.25, 2.50, 8.10, 8.55),
    15: (2.80, 3.05, 9.45, 9.45),
    16: (3.40, 3.80, 10.15, 10.15),
    17: (4.15, 4.55, 12.50, 12.50),
}
"""Article 264(3) Table 4; 'All other' = 1 250 % in every column."""

SEC_254_2_SA_RW_THRESHOLD: Final[float] = 0.25
"""Article 254(2)(a)-(b): use SEC-ERBA instead of SEC-SA where SEC-SA RW > 25 %."""
SEC_254_2_ERBA_RW_THRESHOLD: Final[float] = 0.75
"""Article 254(2)(b): ... or SEC-ERBA RW > 75 % (non-STS positions)."""

SEC_270A_ADDITIONAL_RW_MIN_MULTIPLE: Final[float] = 2.5
"""Article 270a(1): additional risk weight 'of no less than 250 % of the risk weight, capped at
1 250 %' (supervisory minimum; the engine applies the minimum)."""

SEC_STS_POOL_SINGLE_OBLIGOR_MAX: Final[float] = 0.02
"""Article 243(1)(b) / (2)(a): single-obligor concentration <= 2 %."""
SEC_STS_POOL_RW_CAPS: Final[dict[str, float]] = {
    "RRE_WEIGHTED_AVERAGE": 0.40,
    "CRE_INDIVIDUAL": 0.50,
    "RETAIL_INDIVIDUAL": 0.75,
    "OTHER_INDIVIDUAL": 1.00,
}
"""Article 243(2)(b)(i)-(iv): SA risk-weight caps on the underlying exposures for STS capital
treatment (non-ABCP)."""
SEC_STS_ABCP_RW_CAPS: Final[dict[str, float]] = {
    "RETAIL_INDIVIDUAL": 0.75,
    "OTHER_INDIVIDUAL": 1.00,
}
"""Article 243(1)(a): ABCP underlying exposures."""
SEC_STS_RRE_LTV_MAX: Final[float] = 1.00
"""Article 243(2)(d): no RRE loan with LTV above 100 %."""

SEC_SYNTHETIC_MATURITY_MISMATCH_T_STAR: Final[float] = 0.25
"""Article 252(b): t* = 0,25."""
SEC_SYNTHETIC_UNDERLYING_MATURITY_CAP: Final[float] = 5.0
"""Article 252(a): maturity of the underlying exposures subject to a maximum of 5 years."""

# TODO: VERIFY -- the mapping of ECAI notches to the 17 securitisation credit quality steps
# of Tables 2 and 4 is set by Commission Implementing Regulation (EU) 2016/1801 (not in the
# source texts). The S&P-style notch -> CQS order below follows the row order of the BCBS
# SEC-ERBA table (Basel Framework CRE42, AAA ... CCC) that Tables 2/4 reproduce row for row;
# anything below CCC- is treated as 'all other' (1 250 %). Callers may pass 'CQS<n>' or '<n>'
# directly to bypass this mapping.
SEC_LONG_TERM_NOTCH_TO_CQS: Final[dict[str, int]] = {
    "AAA": 1,
    "AA+": 2,
    "AA": 3,
    "AA-": 4,
    "A+": 5,
    "A": 6,
    "A-": 7,
    "BBB+": 8,
    "BBB": 9,
    "BBB-": 10,
    "BB+": 11,
    "BB": 12,
    "BB-": 13,
    "B+": 14,
    "B": 15,
    "B-": 16,
    "CCC+": 17,
    "CCC": 17,
    "CCC-": 17,
}

# TODO: VERIFY -- short-term notch -> CQS mapping (Implementing Regulation (EU) 2016/1801, not
# supplied); A-1/P-1 -> 1, A-2/P-2 -> 2, A-3/P-3 -> 3, others -> 'all other ratings' (1 250 %).
SEC_SHORT_TERM_NOTCH_TO_CQS: Final[dict[str, int]] = {"A-1/P-1": 1, "A-2/P-2": 2, "A-3/P-3": 3}

SEC_OUTPUT_FLOOR_P: Final[dict[str, float]] = {"ARTICLE_262": 0.25, "ARTICLE_261": 0.5}
"""Article 465(13)(a)-(b) (CRR3 p.172): SEC-SA p in S-TREA for positions risk-weighted with the
SEC-IRBA or IAA in U-TREA, until 31 December 2032."""
SEC_OUTPUT_FLOOR_P_END_YEAR: Final[int] = 2032
"""Article 465(13)."""

# =========================================================================
#  SA-CVA -- Articles 383-383z (CRR3 points (200)-(201), OJ pp.132-154)
# =========================================================================

SACVA_M_CVA: Final[float] = 1.0
"""Article 383b(8): m_CVA 'equal to 1'; the competent authority may increase it."""
SACVA_R: Final[float] = 0.01
"""Article 383b(7): hedging disallowance parameter R = 0,01."""
SACVA_OWN_FUNDS_TO_RWA: Final[float] = 12.5
"""Article 92(6)(b) (CRR3 p.31): own funds requirements for CVA risk multiplied by 12,5."""

SACVA_IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"EUR", "SEK", "AUD", "CAD", "GBP", "JPY", "USD"}
)
"""Article 383c(2): euro, Swedish krona, Australian dollar, Canadian dollar, pound sterling, yen and
US dollar -- plus the institution's reporting currency and ERM II currencies (caller-supplied)."""
SACVA_IR_TENORS: Final[tuple[str, ...]] = ("1Y", "2Y", "5Y", "10Y", "30Y")
"""Article 383c(1): maturities 1, 2, 5, 10 and 30 years (risk-free and inflation)."""
SACVA_IR_RW_SPECIFIED: Final[dict[str, float]] = {
    "1Y": 0.0111,
    "2Y": 0.0093,
    "5Y": 0.0074,
    "10Y": 0.0074,
    "30Y": 0.0074,
}
"""Article 383k(1) Table 1 (OJ pp.143-144): buckets 1-5 by maturity."""
SACVA_IR_RW_OTHER: Final[float] = 0.0158
"""Article 383k(2): other currencies, risk-free rate delta."""
SACVA_INFLATION_RW_SPECIFIED: Final[float] = 0.0111
"""Article 383k(3)."""
SACVA_INFLATION_RW_OTHER: Final[float] = 0.0158
"""Article 383k(4)."""
SACVA_IR_VEGA_RW: Final[float] = 1.00
"""Article 383k(5): interest rate and inflation vega, all currencies, 100 %."""
SACVA_IR_TENOR_CORR: Final[dict[tuple[str, str], float]] = {
    ("1Y", "2Y"): 0.91,
    ("1Y", "5Y"): 0.72,
    ("1Y", "10Y"): 0.55,
    ("1Y", "30Y"): 0.31,
    ("2Y", "5Y"): 0.87,
    ("2Y", "10Y"): 0.72,
    ("2Y", "30Y"): 0.45,
    ("5Y", "10Y"): 0.91,
    ("5Y", "30Y"): 0.68,
    ("10Y", "30Y"): 0.83,
}
"""Article 383l(1) Table 1 (OJ p.144): risk-free rate tenor correlations (specified currencies)."""
SACVA_IR_INFLATION_CORR: Final[float] = 0.40
"""Article 383l(2): inflation vs risk-free rate delta, same currency; 383l(3): same for vega."""
SACVA_IR_CROSS_BUCKET: Final[float] = 0.5
"""Article 383m: 0,5 for all currency pairs (delta and vega)."""

SACVA_FX_RW: Final[float] = 0.11
"""Article 383n(1): 11 % delta."""
SACVA_FX_ERM2_DIVISOR: Final[float] = 3.0
"""Article 383n(2)(a): euro / ERM II currency pairs -- the 11 % divided by 3 (or the narrower
agreed band, 383n(2)(b)/(3))."""
SACVA_FX_VEGA_RW: Final[float] = 1.00
"""Article 383n(4)."""
SACVA_FX_CROSS_BUCKET: Final[float] = 0.60
"""Article 383o(1)-(2): 60 % delta and vega."""

SACVA_CCS_TENORS: Final[tuple[str, ...]] = ("0.5Y", "1Y", "3Y", "5Y", "10Y")
"""Article 383e(1): 0,5, 1, 3, 5 and 10 years."""
SACVA_CCS_RW: Final[dict[int, float]] = {
    1: 0.005,
    2: 0.005,
    3: 0.010,
    4: 0.050,
    5: 0.030,
    6: 0.030,
    7: 0.020,
    8: 0.015,
    9: 0.010,
    # bucket 10 depends on CQS: see SACVA_CCS_RW_BUCKET_10
    11: 0.050,
    12: 0.015,
    13: 0.020,
    14: 0.040,
    15: 0.120,
    16: 0.070,
    17: 0.085,
    18: 0.055,
    19: 0.050,
    20: 0.120,
    21: 0.050,
}
"""Article 383p(1) Table 1 (OJ pp.145-147): counterparty credit spread delta risk weights."""
SACVA_CCS_RW_BUCKET_10: Final[dict[str, float]] = {"CQS1": 0.015, "CQS2_3": 0.025}
"""Article 383p(1) Table 1, bucket 10 (third-country covered bonds): CQS 1 1,5 %, CQS 2-3 2,5 %."""
SACVA_CCS_INDEX_BUCKETS: Final[frozenset[int]] = frozenset({12, 21})
"""Article 383p(3): buckets 12 and 21 = qualified indices."""
SACVA_CCS_QUALITY_GROUPS: Final[tuple[frozenset[int], ...]] = (
    frozenset(range(1, 12)),
    frozenset(range(13, 21)),
)
"""Article 383q(1): rho_quality = 1 where both names are in buckets 1-11 or both in 13-20."""
SACVA_CCS_CROSS_GROUPS: Final[dict[int, str]] = {
    1: "SOV_RGLA", 2: "SOV_RGLA", 3: "SOV_RGLA", 13: "SOV_RGLA", 14: "SOV_RGLA",
    4: "FIN", 15: "FIN",
    5: "BASIC", 16: "BASIC",
    6: "CONSUMER", 17: "CONSUMER",
    7: "TECH", 18: "TECH",
    8: "HEALTH", 19: "HEALTH",
    9: "COVERED", 10: "COVERED",
    11: "OTHER", 20: "OTHER",
    12: "INDEX", 21: "INDEX",
}  # fmt: skip
"""Article 383r Table 1 row/column groups (OJ p.148)."""
_CCS_G = ("SOV_RGLA", "FIN", "BASIC", "CONSUMER", "TECH", "HEALTH", "COVERED", "OTHER", "INDEX")
_CCS_T = (
    (1.00, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.00, 0.45),
    (None, 1.00, 0.05, 0.15, 0.20, 0.05, 0.20, 0.00, 0.45),
    (None, None, 1.00, 0.20, 0.25, 0.05, 0.05, 0.00, 0.45),
    (None, None, None, 1.00, 0.25, 0.05, 0.15, 0.00, 0.45),
    (None, None, None, None, 1.00, 0.05, 0.20, 0.00, 0.45),
    (None, None, None, None, None, 1.00, 0.05, 0.00, 0.45),
    (None, None, None, None, None, None, 1.00, 0.00, 0.45),
    (None, None, None, None, None, None, None, 1.00, 0.00),
    (None, None, None, None, None, None, None, None, 1.00),
)
SACVA_CCS_CROSS_CORR: Final[dict[tuple[str, str], float]] = {
    (_CCS_G[i], _CCS_G[j]): float(_CCS_T[min(i, j)][max(i, j)])  # type: ignore[arg-type]
    for i in range(len(_CCS_G))
    for j in range(len(_CCS_G))
}
"""Article 383r Table 1: counterparty credit spread cross-bucket correlations (symmetric)."""
SACVA_CS_RHO_TENOR_DIFF: Final[float] = 0.90
"""Articles 383q(1)-(2), 383t(1)-(2): rho_tenor = 90 % for different vertices."""
SACVA_CS_RHO_NAME_RELATED: Final[float] = 0.90
"""Articles 383q(1), 383t(1): distinct but legally related names."""
SACVA_CS_RHO_NAME_UNRELATED: Final[float] = 0.50
"""Articles 383q(1), 383t(1): otherwise 50 %."""
SACVA_CS_RHO_INDEX_SERIES: Final[float] = 0.90
"""Articles 383q(2), 383t(2): same index, distinct series."""
SACVA_CS_RHO_INDEX_OTHER: Final[float] = 0.80
"""Articles 383q(2), 383t(2): different indices."""
SACVA_CS_RHO_QUALITY_DIFF: Final[float] = 0.80
"""Articles 383q, 383t: rho_quality = 80 % otherwise."""

SACVA_RCS_RW: Final[dict[int, float]] = {
    1: 0.005,
    2: 0.005,
    3: 0.010,
    4: 0.050,
    5: 0.030,
    6: 0.030,
    7: 0.020,
    8: 0.015,
    9: 0.010,
    # bucket 10 depends on CQS: see SACVA_CCS_RW_BUCKET_10 (same 1,5 % / 2,5 % split)
    11: 0.015,
    12: 0.020,
    13: 0.040,
    14: 0.120,
    15: 0.070,
    16: 0.085,
    17: 0.055,
    18: 0.050,
    19: 0.050,
    20: 0.120,
}
"""Article 383s(1) Table 1 (OJ pp.148-150): reference credit spread delta risk weights."""
SACVA_RCS_VEGA_RW: Final[float] = 1.00
"""Article 383s(2)."""
# TODO: VERIFY -- Article 383u Table 1 (OJ p.151) labels its rows/columns '1, 2 and 12',
# '3 and 14', '4 and 15', '5 and 16', '6 and 17', '7 and 18', '8 and 19', '9 and 10', '20',
# '11', '19': bucket 19 appears twice and bucket 13 not at all, so the printed labels are
# internally inconsistent with Article 383s Table 1 (3/13 = RGLA, 4/14 = financials, ...,
# 8/18 = health care, 11/19 = indices). The engine pairs each investment-grade sector bucket
# with its speculative-grade counterpart from Table 1 of Article 383s (3&13, 4&14, 5&15, 6&16,
# 7&17, 8&18), which is also the BCBS MAR50.67 Table 9 structure the correlation values match.
SACVA_RCS_CROSS_GROUPS: Final[dict[int, str]] = {
    1: "SOV", 2: "SOV", 12: "SOV",
    3: "RGLA", 13: "RGLA",
    4: "FIN", 14: "FIN",
    5: "BASIC", 15: "BASIC",
    6: "CONSUMER", 16: "CONSUMER",
    7: "TECH", 17: "TECH",
    8: "HEALTH", 18: "HEALTH",
    9: "COVERED", 10: "COVERED",
    20: "OTHER",
    11: "INDEX_IG",
    19: "INDEX_HY",
}  # fmt: skip
_RCS_G = (
    "SOV", "RGLA", "FIN", "BASIC", "CONSUMER", "TECH", "HEALTH", "COVERED", "OTHER",
    "INDEX_IG", "INDEX_HY",
)  # fmt: skip
_RCS_T = (
    (1.00, 0.75, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.00, 0.45, 0.45),
    (None, 1.00, 0.05, 0.15, 0.20, 0.15, 0.10, 0.10, 0.00, 0.45, 0.45),
    (None, None, 1.00, 0.05, 0.15, 0.20, 0.05, 0.20, 0.00, 0.45, 0.45),
    (None, None, None, 1.00, 0.20, 0.25, 0.05, 0.05, 0.00, 0.45, 0.45),
    (None, None, None, None, 1.00, 0.25, 0.05, 0.15, 0.00, 0.45, 0.45),
    (None, None, None, None, None, 1.00, 0.05, 0.20, 0.00, 0.45, 0.45),
    (None, None, None, None, None, None, 1.00, 0.05, 0.00, 0.45, 0.45),
    (None, None, None, None, None, None, None, 1.00, 0.00, 0.45, 0.45),
    (None, None, None, None, None, None, None, None, 1.00, 0.00, 0.00),
    (None, None, None, None, None, None, None, None, None, 1.00, 0.75),
    (None, None, None, None, None, None, None, None, None, None, 1.00),
)
SACVA_RCS_CROSS_CORR: Final[dict[tuple[str, str], float]] = {
    (_RCS_G[i], _RCS_G[j]): float(_RCS_T[min(i, j)][max(i, j)])  # type: ignore[arg-type]
    for i in range(len(_RCS_G))
    for j in range(len(_RCS_G))
}
"""Article 383u(1) Table 1 values (OJ p.151), symmetric."""
SACVA_RCS_IG_BUCKETS: Final[frozenset[int]] = frozenset(range(1, 11))
"""Article 383u(2): group of buckets 1 to 10."""
SACVA_RCS_HY_BUCKETS: Final[frozenset[int]] = frozenset(range(12, 19))
"""Article 383u(2): group of buckets 12 to 18."""
SACVA_RCS_IG_HY_DIVISOR: Final[float] = 2.0
"""Article 383u(2): correlations between the two groups divided by 2."""

SACVA_EQ_RW: Final[dict[int, float]] = {
    1: 0.55,
    2: 0.60,
    3: 0.45,
    4: 0.55,
    5: 0.30,
    6: 0.35,
    7: 0.40,
    8: 0.50,
    9: 0.70,
    10: 0.50,
    11: 0.70,
    12: 0.15,
    13: 0.25,
}
"""Article 383v(1) Table 1 (OJ pp.152-153): equity spot price delta risk weights."""
SACVA_EQ_VEGA_RW_LARGE: Final[float] = 0.78
"""Article 383v(5): 78 % for buckets 1 to 8 and bucket 12."""
SACVA_EQ_VEGA_RW_OTHER: Final[float] = 1.00
"""Article 383v(5): 100 % for all other buckets."""
SACVA_EQ_VEGA_LARGE_BUCKETS: Final[frozenset[int]] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 12})
"""Article 383v(5)."""
SACVA_EQ_CROSS_1_10: Final[float] = 0.15
"""Article 383w(a)."""
SACVA_EQ_CROSS_12_13: Final[float] = 0.75
"""Article 383w(b)."""
SACVA_EQ_CROSS_INDEX_SECTOR: Final[float] = 0.45
"""Article 383w(c)."""
SACVA_EQ_CROSS_OTHER: Final[float] = 0.0
"""Article 383w(d): bucket 11."""

SACVA_COM_RW: Final[dict[int, float]] = {
    1: 0.30,
    2: 0.35,
    3: 0.60,
    4: 0.40,
    5: 0.60,
    6: 0.80,
    7: 0.40,
    8: 0.45,
    9: 0.20,
    10: 0.35,
    11: 0.25,
    12: 0.35,
    13: 0.50,
}
"""Article 383x(1) Table 1 (OJ p.154): commodity spot price delta risk weights."""
SACVA_COM_VEGA_RW: Final[float] = 1.00
"""Article 383x(2)."""
SACVA_COM_CROSS: Final[float] = 0.20
"""Article 383z(1)(a)/(2)(a): 20 % within buckets 1-12."""
SACVA_COM_CROSS_OTHER: Final[float] = 0.0
"""Article 383z(1)(b)/(2)(b): 0 % where one bucket is 13."""

# =========================================================================
#  Leverage ratio -- Articles 429-429g (consolidated; CRR3 points (209)-(213))
# =========================================================================

LEV_SACCR_ALPHA: Final[float] = 1.4
"""Article 429c(1) -> Part Three Title II Chapter 6 Section 3 (SA-CCR); Article 274(2) alpha 1,4."""
LEV_PFE_MULTIPLIER: Final[float] = 1.0
"""Article 429c(5): multiplier set to one (except client-cleared QCCP contracts)."""
LEV_UCC_CCF: Final[float] = 0.10
"""Article 429f(3) (CRR3 point (212)(b)): 10 % for unconditionally cancellable commitments,
by derogation from the Article 495d transitional."""
LEV_CCF_BY_BUCKET: Final[dict[int, float]] = {1: 1.00, 2: 0.50, 3: 0.40, 4: 0.20, 5: 0.10}
"""Article 429f(1) (CRR3 point (212)(a)) -> Article 111(2)(a)-(e)."""
LEV_MINIMUM: Final[float] = 0.03
"""Article 92(1)(d); also the 3 % in the Article 429a(7) adjusted-ratio formula."""
LEV_GSII_BUFFER_SHARE: Final[float] = 0.50
"""Article 92(1a): leverage ratio buffer = 50 % of the G-SII buffer rate."""

# =========================================================================
#  Large exposures -- Articles 387-403 (consolidated; CRR3 points (203)-(206))
# =========================================================================

LE_DEFINITION_PCT_T1: Final[float] = 0.10
"""Article 392: large exposure where the value is equal to or exceeds 10 % of Tier 1."""
LE_LIMIT_PCT_T1: Final[float] = 0.25
"""Article 395(1) first subparagraph: 25 % of Tier 1 capital."""
LE_INSTITUTION_FLOOR_EUR_M: Final[float] = 150.0
"""Article 395(1): institutions -- 25 % of Tier 1 or EUR 150 million, whichever is higher."""
LE_INSTITUTION_ABSOLUTE_CEILING_PCT_T1: Final[float] = 1.00
"""Article 395(1) second subparagraph: where EUR 150m > 25 % of Tier 1, an institution-set
reasonable limit that 'shall not exceed 100 % of the institution's Tier 1 capital'."""
LE_GSII_TO_GSII_PCT_T1: Final[float] = 0.15
"""Article 395(1) fourth subparagraph: G-SII to G-SII / non-EU G-SII, 15 % of Tier 1."""
LE_REPORTING_EUR_M: Final[float] = 300.0
"""Article 394(1) third subparagraph: exposures >= EUR 300 million but < 10 % of Tier 1."""
LE_TB_EXCESS_10_DAYS_MAX_PCT_T1: Final[float] = 5.00
"""Article 395(5)(c): trading-book exposure within 10 days of the excess <= 500 % of Tier 1."""
LE_TB_EXCESS_PERSISTING_MAX_PCT_T1: Final[float] = 6.00
"""Article 395(5)(d): excesses persisting > 10 days, in aggregate <= 600 % of Tier 1."""
LE_TB_EXCESS_SHORT_FACTOR: Final[float] = 2.00
"""Article 397(2): 200 % of the requirements where the excess has not persisted > 10 days."""
LE_TB_EXCESS_FACTORS: Final[tuple[tuple[float, float], ...]] = (
    (0.40, 2.00),
    (0.60, 3.00),
    (0.80, 4.00),
    (1.00, 5.00),
    (2.50, 6.00),
    (float("inf"), 9.00),
)
"""Article 397(3) Table 1: (upper bound of the excess as % of Tier 1, factor)."""
LE_MORTGAGE_REDUCTION_MAX_SHARE: Final[float] = 0.55
"""Article 402(1)-(2) (CRR3 point (206)): reduction by the pledged amount, at most 55 % of the
property value."""
LE_MORTGAGE_RRE_MAX_RW: Final[float] = 0.20
"""Article 402(1)(a) (CRR3): authorities have not set an RRE weight higher than 20 %."""
LE_MORTGAGE_CRE_MAX_RW: Final[float] = 0.60
"""Article 402(2)(a) (CRR3): authorities have not set a CRE weight higher than 60 %."""
LE_400_2_I_SHARE: Final[dict[str, float]] = {
    "BUCKET4_DOC_CREDIT_OR_BUCKET3_UNDRAWN_LE_1Y": 0.50,
    "MUTUAL_GUARANTEE_SCHEME": 0.80,
}
"""Article 400(2)(i) (CRR3 point (205)(b)(ii)): share of the item that may be exempted."""
LE_400_1_EXEMPTION_KEYS: Final[dict[str, str]] = {
    "eu_400_1_a": "Art. 400(1)(a): 0 % RW central governments, central banks, PSEs",
    "eu_400_1_b": "Art. 400(1)(b): 0 % RW international organisations / MDBs",
    "eu_400_1_c": "Art. 400(1)(c): explicitly guaranteed by 0 % RW sovereigns etc.",
    "eu_400_1_d": "Art. 400(1)(d): attributable to / guaranteed by 0 % RW sovereigns etc.",
    "eu_400_1_e": "Art. 400(1)(e): 0 % RW Member State RGLAs",
    "eu_400_1_f": "Art. 400(1)(f): Article 113(6)/(7) counterparties at 0 % RW",
    "eu_400_1_g": "Art. 400(1)(g): secured by cash deposits with the lender/group",
    "eu_400_1_h": "Art. 400(1)(h): secured by own certificates of deposit",
    "eu_400_1_i": "Art. 400(1)(i) (CRR3): bucket 5 undrawn facilities with LE draw-stop",
    "eu_400_1_j": "Art. 400(1)(j): clearing members' QCCP trade exposures and DF contributions",
    "eu_400_1_k": "Art. 400(1)(k): deposit guarantee scheme funding",
    "eu_400_1_l": "Art. 400(1)(l): clients' trade exposures under Article 305(2)/(3)",
    "eu_400_1_m": "Art. 400(1)(m): intra-resolution-group MREL holdings",
    "eu_400_1_n": "Art. 400(1)(n): Article 132c(3) minimum value commitments",
}
"""Article 400(1) points (a)-(n): exposures exempted from Article 395(1)."""
LE_400_2_EXEMPTION_KEYS: Final[dict[str, str]] = {
    "eu_400_2_a": "Art. 400(2)(a) (CRR3): covered bonds (Article 129)",
    "eu_400_2_b": "Art. 400(2)(b): 20 % RW Member State RGLAs",
    "eu_400_2_c": "Art. 400(2)(c): intragroup exposures under consolidated supervision",
    "eu_400_2_d": "Art. 400(2)(d): regional/central credit institutions of a network",
    "eu_400_2_e": "Art. 400(2)(e): promotional pass-through loans",
    "eu_400_2_f": "Art. 400(2)(f): overnight non-major-currency interbank",
    "eu_400_2_g": "Art. 400(2)(g): required minimum reserves at central banks",
    "eu_400_2_h": "Art. 400(2)(h): statutory liquidity holdings in government securities",
    "eu_400_2_j": "Art. 400(2)(j): legally required mortgage-bond bridging guarantees",
    "eu_400_2_k": "Art. 400(2)(k): CQS2-or-better RRE guarantees/collateral",
    "eu_400_2_l": "Art. 400(2)(l): CQS2-or-better export credit agency guarantees",
}
"""Article 400(2): competent-authority (full or partial) exemptions; Article 400(3) conditions."""

# =========================================================================
#  CCPs -- Articles 300-311 (consolidated, not amended by CRR3)
# =========================================================================

CCP_QCCP_TRADE_RW: Final[float] = 0.02
"""Article 306(1)(a): 2 % to trade exposures with QCCPs."""
CCP_CLIENT_JOINT_DEFAULT_RW: Final[float] = 0.04
"""Article 305(3): 4 % where the client is not protected against the joint default of the
clearing member and another client."""
CCP_DF_FLOOR_RW: Final[float] = 0.02
"""Article 308(2): K_i floor = 8 % x 2 % x DF_i."""
CCP_OWN_FUNDS_RATIO: Final[float] = 0.08
"""Article 308(2): the 8 % in 8 % x 2 % x DF_i."""
CCP_K_TO_RWA: Final[float] = 12.5
"""Articles 308(3), 309(2): risk-weighted exposure amount = own funds requirement x 12,5."""
CCP_QCCP_UNFUNDED_DF_RW: Final[float] = 0.0
"""Article 310: 0 % to unfunded contributions to the default fund of a QCCP."""
CCP_CASH_TRANSACTION_DF_RW: Final[float] = 0.0
"""Article 301(1) second subparagraph: 0 % to DF contributions covering only cash transactions."""
CCP_CLIENT_MPOR_MIN_DAYS: Final[int] = 5
"""Article 304(3)(a): clearing member's exposures to a client: MPOR >= 5 business days."""
CCP_CM_MPOR_MIN_DAYS: Final[int] = 10
"""Article 304(3)(b): clearing member's exposures to a CCP -- MPOR of at least 10 business days."""
CCP_CLIENT_MATURITY_FACTOR: Final[float] = 0.21
"""Article 304(4)-(5): maturity factor 0,21 for a clearing member's exposures to a client
(original exposure method / simplified SA-CCR)."""
CCP_CEASING_TRANSITION_MONTHS: Final[int] = 3
"""Article 311(2): treatment applies within three months of becoming aware."""
