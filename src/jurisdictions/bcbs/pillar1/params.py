"""Basel Framework (BCBS) parameters for securitisation, SA-CVA, leverage exposure,
large exposures and CCP exposures.

Every constant is transcribed from the consolidated Basel Framework (BIS,
generated 29/10/2026) with its paragraph reference; page numbers are the
"n / 1429" page footers. Equations that are images in the Framework were
read from the rendered PDF pages (cited by page). BCBS d424 was used only as
a cross-check for MAR50 (it predates the July 2020 CVA revisions, so where
the two differ the Framework governs -- see the reference document § 7).

The verbatim transcription is ``docs/jurisdictions/BCBS_pillar1_reference.md``.

References:
    - Basel Framework CRE40-CRE45 (securitisation, pp. 348-419)
    - Basel Framework MAR50.27-50.77 (SA-CVA, pp. 730-750)
    - Basel Framework LEV30 (leverage ratio exposure measure, pp. 790-810)
    - Basel Framework LEX10-LEX40 (large exposures, pp. 937-958)
    - Basel Framework CRE54 (exposures to central counterparties, pp. 483-494)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# =========================================================================
#  Securitisation -- general (CRE40)
# =========================================================================

SEC_RW_MAX: Final[float] = 12.50
"""CRE40.31, CRE40.41, CRE41.10, CRE41.13(1), CRE44.24(1): 1250% risk weight."""

SEC_CAPITAL_RATIO: Final[float] = 0.08
"""CRE41.2: K_SA = weighted-average RW x 8% ("a weighted-average risk weight of
100% means that K_SA would equal 0.08")."""

SEC_RW_PER_UNIT_K: Final[float] = 12.5
"""CRE41.13(2) / CRE44.24(2): risk weight = K_SSFA x 12.5."""

TRANCHE_MATURITY_FLOOR_YEARS: Final[float] = 1.0
"""CRE40.22: "In all cases, M_T will have a floor of one year ..." (p. 353)."""
TRANCHE_MATURITY_CAP_YEARS: Final[float] = 5.0
"""CRE40.22: "... and a cap of five years." (p. 353)."""
TRANCHE_MATURITY_LEGAL_FACTOR: Final[float] = 0.80
"""CRE40.22(2): M_T = 1 + 80% x (M_L - 1) (formula image, p. 353)."""

MIXED_POOL_IRBA_MIN_SHARE: Final[float] = 0.95
"""CRE40.46: SEC-IRBA for a mixed pool where K_IRB can be calculated on at least
95% of the underlying exposure amounts; capital = d x K_IRB + (1 - d) x K_SA (p. 359)."""

SENIOR_LOOK_THROUGH_CAP_BELOW_FLOOR_ALLOWED: Final[bool] = True
"""CRE40.51: where the look-through cap is below the 15% floor, the cap is used."""

CLEAN_UP_CALL_MAX_REMAINING: Final[float] = 0.10
"""CRE40.28(3): clean-up call exercisable only when 10% or less of the original
portfolio / securities / reference portfolio remains."""

# =========================================================================
#  SEC-SA (CRE41)
# =========================================================================

SEC_SA_DELINQUENT_LGD: Final[float] = 0.5
"""CRE41.8: K_A = (1 - W) x K_SA + 0.5 x W (formula image, p. 394)."""

SEC_SA_MAX_UNKNOWN_DELINQUENCY_SHARE: Final[float] = 0.05
"""CRE41.9-41.10: delinquency status unknown for no more than 5% -> adjusted K_A;
more than 5% -> 1250%."""

SEC_SA_P: Final[float] = 1.0
"""CRE41.12: p = 1 for a securitisation exposure that is not a resecuritisation."""
SEC_SA_P_RESEC: Final[float] = 1.5
"""CRE41.16(3): p = 1.5 for resecuritisation exposures."""
SEC_SA_P_STC: Final[float] = 0.5
"""CRE41.21: p = 0.5 for an exposure to an STC securitisation."""

SEC_SA_FLOOR: Final[float] = 0.15
"""CRE41.15: floor risk weight of 15%."""
SEC_SA_FLOOR_RESEC: Final[float] = 1.00
"""CRE41.18: resecuritisation floor risk weight of 100%."""
SEC_STC_FLOOR_SENIOR: Final[float] = 0.10
"""CRE41.22 / CRE42.14 / CRE44.29: STC floor 10% for senior tranches."""
SEC_STC_FLOOR_NON_SENIOR: Final[float] = 0.15
"""CRE41.22 / CRE42.14 / CRE44.29: STC floor 15% for non-senior tranches."""

# =========================================================================
#  SEC-ERBA (CRE42) -- Tables 1-4
# =========================================================================

ERBA_SHORT_TERM_RW: Final[dict[str, float]] = {
    # CRE42.2 Table 1 (p. 398); "All other ratings" = 1250%
    "A-1/P-1": 0.15,
    "A-2/P-2": 0.50,
    "A-3/P-3": 1.00,
}
ERBA_STC_SHORT_TERM_RW: Final[dict[str, float]] = {
    # CRE42.12 Table 3 (p. 402); "All other ratings" = 1250%
    "A-1/P-1": 0.10,
    "A-2/P-2": 0.30,
    "A-3/P-3": 0.60,
}

ERBA_LONG_TERM_GRADES: Final[tuple[str, ...]] = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+/CCC/CCC-", "Below CCC-",
)
"""CRE42.4 Table 2 / CRE42.13 Table 4 row labels (pp. 398-399, 402-403)."""

# (senior 1y, senior 5y, non-senior 1y, non-senior 5y)
ErbaRow = tuple[float, float, float, float]

ERBA_LONG_TERM_RW: Final[dict[str, ErbaRow]] = {
    # CRE42.4 Table 2 (pp. 398-399, verified against the rendered p. 399)
    "AAA": (0.15, 0.20, 0.15, 0.70),
    "AA+": (0.15, 0.30, 0.15, 0.90),
    "AA": (0.25, 0.40, 0.30, 1.20),
    "AA-": (0.30, 0.45, 0.40, 1.40),
    "A+": (0.40, 0.50, 0.60, 1.60),
    "A": (0.50, 0.65, 0.80, 1.80),
    "A-": (0.60, 0.70, 1.20, 2.10),
    "BBB+": (0.75, 0.90, 1.70, 2.60),
    "BBB": (0.90, 1.05, 2.20, 3.10),
    "BBB-": (1.20, 1.40, 3.30, 4.20),
    "BB+": (1.40, 1.60, 4.70, 5.80),
    "BB": (1.60, 1.80, 6.20, 7.60),
    "BB-": (2.00, 2.25, 7.50, 8.60),
    "B+": (2.50, 2.80, 9.00, 9.50),
    "B": (3.10, 3.40, 10.50, 10.50),
    "B-": (3.80, 4.20, 11.30, 11.30),
    "CCC+/CCC/CCC-": (4.60, 5.05, 12.50, 12.50),
    "Below CCC-": (12.50, 12.50, 12.50, 12.50),
}

ERBA_STC_LONG_TERM_RW: Final[dict[str, ErbaRow]] = {
    # CRE42.13 Table 4 (pp. 402-403)
    "AAA": (0.10, 0.10, 0.15, 0.40),
    "AA+": (0.10, 0.15, 0.15, 0.55),
    "AA": (0.15, 0.20, 0.15, 0.70),
    "AA-": (0.15, 0.25, 0.25, 0.80),
    "A+": (0.20, 0.30, 0.35, 0.95),
    "A": (0.30, 0.40, 0.60, 1.35),
    "A-": (0.35, 0.40, 0.95, 1.70),
    "BBB+": (0.45, 0.55, 1.50, 2.25),
    "BBB": (0.55, 0.65, 1.80, 2.55),
    "BBB-": (0.70, 0.85, 2.70, 3.45),
    "BB+": (1.20, 1.35, 4.05, 5.00),
    "BB": (1.35, 1.55, 5.35, 6.55),
    "BB-": (1.70, 1.95, 6.45, 7.40),
    "B+": (2.25, 2.50, 8.10, 8.55),
    "B": (2.80, 3.05, 9.45, 9.45),
    "B-": (3.40, 3.80, 10.15, 10.15),
    "CCC+/CCC/CCC-": (4.15, 4.55, 12.50, 12.50),
    "Below CCC-": (12.50, 12.50, 12.50, 12.50),
}

ERBA_THICKNESS_CAP: Final[float] = 0.50
"""CRE42.5(2): RW = (table RW after maturity adjustment) x (1 - min(T, 50%)) (image, p. 399)."""

ERBA_FLOOR: Final[float] = 0.15
"""CRE42.7: floor risk weight of 15% (non-STC)."""

# =========================================================================
#  SEC-IRBA (CRE44)
# =========================================================================

IRBA_P_FLOOR: Final[float] = 0.3
"""CRE44.17(1) / CRE44.28(1): 0.3 denotes the p-parameter floor."""
IRBA_STC_P_SCALAR: Final[float] = 0.5
"""CRE44.28: p = max[0.3; 0.5 x (A + B/N + C x K_IRB + D x LGD + E x M_T)] (image, p. 415)."""
IRBA_GRANULAR_N: Final[float] = 25.0
"""CRE44.17 Table 1: "granular (N>=25)" / "non-granular (N<25)"."""

# (A, B, C, D, E)
IrbaRow = tuple[float, float, float, float, float]

IRBA_P_TABLE: Final[dict[str, IrbaRow]] = {
    # CRE44.17 Table 1 (p. 413) -- identical to CRE44.28 Table 2 (pp. 415-416)
    "WHOLESALE_SENIOR_GRANULAR": (0.0, 3.56, -1.85, 0.55, 0.07),
    "WHOLESALE_SENIOR_NON_GRANULAR": (0.11, 2.61, -2.91, 0.68, 0.07),
    "WHOLESALE_NON_SENIOR_GRANULAR": (0.16, 2.87, -1.03, 0.21, 0.07),
    "WHOLESALE_NON_SENIOR_NON_GRANULAR": (0.22, 2.35, -2.46, 0.48, 0.07),
    "RETAIL_SENIOR": (0.0, 0.0, -7.48, 0.71, 0.24),
    "RETAIL_NON_SENIOR": (0.0, 0.0, -5.78, 0.55, 0.27),
}

IRBA_FLOOR: Final[float] = 0.15
"""CRE44.26: floor risk weight of 15%."""

IRBA_SIMPLIFIED_MAX_C1: Final[float] = 0.03
"""CRE44.22: simplified N / LGD where the largest exposure share C1 <= 0.03."""
IRBA_SIMPLIFIED_LGD: Final[float] = 0.50
"""CRE44.22(1)-(2): LGD set to 0.50 under the simplified method."""

# =========================================================================
#  NPL securitisations (CRE45)
# =========================================================================

NPL_MIN_W: Final[float] = 0.90
"""CRE45.1: NPL securitisation where W >= 90%."""
NPL_RW_FLOOR: Final[float] = 1.00
"""CRE45.4: RW under SEC-IRBA, SEC-SA or the look-through approach floored at 100%."""
NPL_SENIOR_RW: Final[float] = 1.00
"""CRE45.5: 100% for the senior tranche of a traditional NPL securitisation with
NRPPD >= 50% of the outstanding pool balance."""
NPL_SENIOR_NRPPD_MIN: Final[float] = 0.50
"""CRE45.5: NRPPD threshold of 50%."""

# =========================================================================
#  STC eligibility of underlying exposures (CRE40.94-40.95) -- criteria only
# =========================================================================

STC_MAX_RW_RRE_POOL_AVG: Final[float] = 0.40
"""CRE40.94(1): regulatory RRE, value-weighted average RW <= 40%."""
STC_MAX_RW_CRE_INDIVIDUAL: Final[float] = 0.50
"""CRE40.94(2): regulatory CRE / other RE / land ADC, individual RW <= 50%."""
STC_MAX_RW_RETAIL_INDIVIDUAL: Final[float] = 0.75
"""CRE40.94(3): regulatory retail, individual RW <= 75%."""
STC_MAX_RW_OTHER_INDIVIDUAL: Final[float] = 1.00
"""CRE40.94(4): any other exposure, individual RW <= 100%."""
STC_MAX_SINGLE_OBLIGOR_SHARE: Final[float] = 0.01
"""CRE40.95: single-obligor concentration <= 1% (2% under footnote 194 conditions)."""

# =========================================================================
#  SA-CVA (MAR50.27-50.77)
# =========================================================================

M_CVA: Final[float] = 1.0
"""MAR50.41: "The multiplier m_CVA is set at 1." (d424 CVA para 40 had 1.25 -- superseded)."""
R_HEDGING_DISALLOWANCE: Final[float] = 0.01
"""MAR50.53(1): hedging disallowance parameter R set at 0.01."""
CVA_RWA_MULTIPLIER: Final[float] = 12.5
"""MAR50.1: RWA = 12.5 x capital requirement."""

# --- Interest rate (MAR50.54-50.58) -------------------------------------
IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"USD", "EUR", "GBP", "AUD", "CAD", "SEK", "JPY"}
)
"""MAR50.56: the bank's reporting currency and USD, EUR, GBP, AUD, CAD, SEK, JPY."""
IR_CROSS_BUCKET_GAMMA: Final[float] = 0.5
"""MAR50.55: gamma_bc = 0.5 for all currency pairs."""
IR_TENORS: Final[tuple[str, ...]] = ("1Y", "2Y", "5Y", "10Y", "30Y", "INFLATION")
"""MAR50.56(1) / Table 3 risk factors."""
IR_DELTA_RW_SPECIFIED: Final[dict[str, float]] = {
    # MAR50.56(3) Table 3 (p. 739)
    "1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074, "10Y": 0.0074, "30Y": 0.0074,
    "INFLATION": 0.0111,
}
IR_DELTA_CORR_SPECIFIED: Final[dict[tuple[str, str], float]] = {
    # MAR50.56(4) Table 4 (p. 739), upper triangle
    ("1Y", "2Y"): 0.91, ("1Y", "5Y"): 0.72, ("1Y", "10Y"): 0.55, ("1Y", "30Y"): 0.31,
    ("1Y", "INFLATION"): 0.40,
    ("2Y", "5Y"): 0.87, ("2Y", "10Y"): 0.72, ("2Y", "30Y"): 0.45, ("2Y", "INFLATION"): 0.40,
    ("5Y", "10Y"): 0.91, ("5Y", "30Y"): 0.68, ("5Y", "INFLATION"): 0.40,
    ("10Y", "30Y"): 0.83, ("10Y", "INFLATION"): 0.40,
    ("30Y", "INFLATION"): 0.40,
}
IR_DELTA_RW_OTHER: Final[float] = 0.0158
"""MAR50.57(3): 1.58% for the parallel yield-curve shift and the inflation rate."""
IR_DELTA_CORR_OTHER: Final[float] = 0.40
"""MAR50.57(4): correlation yield curve / inflation 40%."""
IR_OTHER_FACTORS: Final[tuple[str, ...]] = ("CURVE", "INFLATION")
"""MAR50.57(1): parallel shift of the entire curve, and the inflation rate."""
IR_VEGA_FACTORS: Final[tuple[str, ...]] = ("IR_VOL", "INFLATION_VOL")
"""MAR50.58(1): all IR volatilities; all inflation volatilities."""
IR_VEGA_RW: Final[float] = 1.00
"""MAR50.58(3): 100%."""
IR_VEGA_CORR: Final[float] = 0.40
"""MAR50.58(4): 40%."""

# --- FX (MAR50.59-50.62) -------------------------------------------------
FX_CROSS_BUCKET_GAMMA: Final[float] = 0.6
"""MAR50.60: gamma_bc = 0.6 for all currency pairs."""
FX_DELTA_RW: Final[float] = 0.11
"""MAR50.61(3): 11%."""
FX_VEGA_RW: Final[float] = 1.00
"""MAR50.62(3): 100%."""

# --- Counterparty credit spread (MAR50.63-50.65) -------------------------
CCS_BUCKETS: Final[tuple[str, ...]] = ("1a", "1b", "2", "3", "4", "5", "6", "7", "8")
"""MAR50.63 Table 5 (bucket 1 split into a) and b) for the Table 7 risk weights)."""
CCS_DELTA_RW: Final[dict[str, tuple[float, float]]] = {
    # MAR50.65(3) Table 7 (pp. 742-743): (IG, HY and NR)
    "1a": (0.005, 0.020), "1b": (0.010, 0.040), "2": (0.050, 0.120),
    "3": (0.030, 0.070), "4": (0.030, 0.085), "5": (0.020, 0.055),
    "6": (0.015, 0.050), "7": (0.050, 0.120), "8": (0.015, 0.050),
}
CCS_CROSS_BUCKET_GAMMA: Final[dict[tuple[str, str], float]] = {
    # MAR50.64 Table 6 (p. 742), upper triangle, buckets 1-8
    ("1", "2"): 0.10, ("1", "3"): 0.20, ("1", "4"): 0.25, ("1", "5"): 0.20,
    ("1", "6"): 0.15, ("1", "7"): 0.00, ("1", "8"): 0.45,
    ("2", "3"): 0.05, ("2", "4"): 0.15, ("2", "5"): 0.20, ("2", "6"): 0.05,
    ("2", "7"): 0.00, ("2", "8"): 0.45,
    ("3", "4"): 0.20, ("3", "5"): 0.25, ("3", "6"): 0.05, ("3", "7"): 0.00, ("3", "8"): 0.45,
    ("4", "5"): 0.25, ("4", "6"): 0.05, ("4", "7"): 0.00, ("4", "8"): 0.45,
    ("5", "6"): 0.05, ("5", "7"): 0.00, ("5", "8"): 0.45,
    ("6", "7"): 0.00, ("6", "8"): 0.45,
    ("7", "8"): 0.00,
}
CCS_TENORS: Final[tuple[str, ...]] = ("0.5Y", "1Y", "3Y", "5Y", "10Y")
"""MAR50.65(1): tenors 0.5, 1, 3, 5 and 10 years."""
CCS_RHO_TENOR_DIFFERENT: Final[float] = 0.90
"""MAR50.65(4)(1) / (5)(1): rho_tenor 100% same tenor, 90% otherwise."""
CCS_RHO_NAME_RELATED: Final[float] = 0.90
"""MAR50.65(4)(2): distinct but legally related names 90%."""
CCS_RHO_NAME_UNRELATED: Final[float] = 0.50
"""MAR50.65(4)(2): otherwise 50%."""
CCS_RHO_INDEX_DISTINCT_SERIES: Final[float] = 0.90
"""MAR50.65(5)(2): same index, distinct series 90%."""
CCS_RHO_INDEX_OTHER: Final[float] = 0.80
"""MAR50.65(5)(2): otherwise 80%."""
CCS_RHO_QUALITY_DIFFERENT: Final[float] = 0.80
"""MAR50.65(4)(3) / (5)(3): rho_quality 100% same credit quality, 80% otherwise."""
CCS_INDEX_BUCKET: Final[str] = "8"
"""MAR50.63(2): bucket 8 for qualified indices."""

# --- Reference credit spread (MAR50.66-50.69) ----------------------------
RCS_BUCKETS: Final[tuple[int, ...]] = tuple(range(1, 18))
"""MAR50.66 Table 8: buckets 1-7 IG, 8-14 HY and NR, 15 other, 16 IG index, 17 HY index."""
RCS_DELTA_RW: Final[dict[int, float]] = {
    # MAR50.68(3) Table 10 (p. 745) -- transcribed as printed (bucket 8 = 2.0%, 9 = 4.0%)
    1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015,
    8: 0.020, 9: 0.040, 10: 0.120, 11: 0.070, 12: 0.085, 13: 0.055, 14: 0.050,
    15: 0.120, 16: 0.015, 17: 0.050,
}
RCS_VEGA_RW: Final[float] = 1.00
"""MAR50.69(3): 100%."""
# Table 9 sector keys: "S1".."S7" = buckets 1/8 .. 7/14; "15", "16", "17"
RCS_CROSS_BUCKET_GAMMA: Final[dict[tuple[str, str], float]] = {
    # MAR50.67(1) Table 9 (p. 745), upper triangle
    ("S1", "S2"): 0.75, ("S1", "S3"): 0.10, ("S1", "S4"): 0.20, ("S1", "S5"): 0.25,
    ("S1", "S6"): 0.20, ("S1", "S7"): 0.15, ("S1", "15"): 0.00, ("S1", "16"): 0.45,
    ("S1", "17"): 0.45,
    ("S2", "S3"): 0.05, ("S2", "S4"): 0.15, ("S2", "S5"): 0.20, ("S2", "S6"): 0.15,
    ("S2", "S7"): 0.10, ("S2", "15"): 0.00, ("S2", "16"): 0.45, ("S2", "17"): 0.45,
    ("S3", "S4"): 0.05, ("S3", "S5"): 0.15, ("S3", "S6"): 0.20, ("S3", "S7"): 0.05,
    ("S3", "15"): 0.00, ("S3", "16"): 0.45, ("S3", "17"): 0.45,
    ("S4", "S5"): 0.20, ("S4", "S6"): 0.25, ("S4", "S7"): 0.05, ("S4", "15"): 0.00,
    ("S4", "16"): 0.45, ("S4", "17"): 0.45,
    ("S5", "S6"): 0.25, ("S5", "S7"): 0.05, ("S5", "15"): 0.00, ("S5", "16"): 0.45,
    ("S5", "17"): 0.45,
    ("S6", "S7"): 0.05, ("S6", "15"): 0.00, ("S6", "16"): 0.45, ("S6", "17"): 0.45,
    ("S7", "15"): 0.00, ("S7", "16"): 0.45, ("S7", "17"): 0.45,
    ("15", "16"): 0.00, ("15", "17"): 0.00,
    ("16", "17"): 0.75,
}
RCS_DIFFERENT_QUALITY_DIVISOR: Final[float] = 2.0
"""MAR50.67(2): between buckets 1-14 of different credit quality, gamma / 2."""

# --- Equity (MAR50.70-50.73) ---------------------------------------------
EQ_LARGE_CAP_THRESHOLD_USD_BN: Final[float] = 2.0
"""MAR50.70(2): large market cap >= USD 2 billion."""
EQ_DELTA_RW: Final[dict[int, float]] = {
    # MAR50.72(3) Table 12 (p. 748)
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,
    9: 0.70, 10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25,
}
EQ_VEGA_RW_LARGE_CAP: Final[float] = 0.78
"""MAR50.73(3): 78% for large market capitalisation buckets."""
EQ_VEGA_RW_OTHER: Final[float] = 1.00
"""MAR50.73(3): 100% for the other buckets."""
EQ_LARGE_CAP_BUCKETS: Final[frozenset[int]] = frozenset(range(1, 9))
"""MAR50.70 Table 11: buckets 1-8 are "Large" size.
TODO: VERIFY -- bucket 12 is "Large cap, advanced economies" qualified indices;
MAR50.73(3) does not say whether it is a "large market capitalisation bucket".
Conservative placeholder: bucket 12 vega RW = 100% (not 78%)."""
EQ_GAMMA_1_TO_10: Final[float] = 0.15
"""MAR50.71: 15% for all cross-bucket pairs within buckets 1-10."""
EQ_GAMMA_12_13: Final[float] = 0.75
"""MAR50.71: 75% between buckets 12 and 13."""
EQ_GAMMA_INDEX_VS_1_TO_10: Final[float] = 0.45
"""MAR50.71: 45% between 12 or 13 and any of buckets 1-10."""
EQ_GAMMA_OTHER_BUCKET: Final[float] = 0.0
"""MAR50.71: 0% for all pairs that include bucket 11."""

# --- Commodity (MAR50.74-50.77) ------------------------------------------
COM_DELTA_RW: Final[dict[int, float]] = {
    # MAR50.76(3) Table 14 (p. 750)
    1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45, 7: 0.20, 8: 0.35,
    9: 0.25, 10: 0.35, 11: 0.50,
}
COM_VEGA_RW: Final[float] = 1.00
"""MAR50.77(3): 100%."""
COM_GAMMA_1_TO_10: Final[float] = 0.20
"""MAR50.75: 20% within buckets 1-10."""
COM_GAMMA_OTHER_BUCKET: Final[float] = 0.0
"""MAR50.75: 0% for pairs including bucket 11."""

# =========================================================================
#  Leverage ratio exposure measure (LEV30)
# =========================================================================

LEV_ALPHA: Final[float] = 1.4
"""LEV30.14 / LEV30.16(1): alpha = 1.4; exposure = alpha x (RC + PFE) (LEV30.15, image p. 795)."""
LEV_PFE_MULTIPLIER: Final[float] = 1.0
"""LEV30.16(3)(1) / LEV30.22: the SA-CCR PFE multiplier is fixed at one."""
LEV_CCF: Final[dict[float, str]] = {
    # LEV30.49-30.54 (pp. 809): CCF -> paragraph
    1.00: "LEV30.49",
    0.50: "LEV30.50-30.51",
    0.40: "LEV30.52",
    0.20: "LEV30.53",
    0.10: "LEV30.54",
}

# =========================================================================
#  Large exposures (LEX10-LEX40)
# =========================================================================

LEX_LARGE_EXPOSURE_THRESHOLD: Final[float] = 0.10
"""LEX10.8 / LEX20.4(1): large exposure if >= 10% of Tier 1 capital (reporting)."""
LEX_GENERAL_LIMIT: Final[float] = 0.25
"""LEX20.1: must not be higher than 25% of Tier 1 capital at all times."""
LEX_GSIB_TO_GSIB_LIMIT: Final[float] = 0.15
"""LEX20.1 / LEX40.1: 15% for a G-SIB's exposures to another G-SIB."""
LEX_ECONOMIC_INTERDEPENDENCE_THRESHOLD: Final[float] = 0.05
"""LEX10.18: identify economic-interdependence connections where exposure > 5% of Tier 1."""
LEX_LOOK_THROUGH_THRESHOLD: Final[float] = 0.0025
"""LEX30.42-30.44: look-through required for underlying exposures >= 0.25% of Tier 1."""
LEX_OBS_CCF_FLOOR: Final[float] = 0.10
"""LEX30.6: SA CCFs with a floor of 10%."""
LEX_COVERED_BOND_MIN_EXPOSURE_FACTOR: Final[float] = 0.20
"""LEX30.38: qualifying covered bonds -- exposure value no less than 20% of nominal."""
LEX_LARGEST_EXPOSURES_REPORTED: Final[int] = 20
"""LEX20.4(4): largest 20 exposures reported irrespective of size."""
LEX_GSIB_PHASE_IN_MONTHS: Final[int] = 12
"""LEX40.1: new G-SIBs apply the 15% limit within 12 months."""

# =========================================================================
#  Central counterparties (CRE54)
# =========================================================================

CCP_QCCP_TRADE_RW: Final[float] = 0.02
"""CRE54.7 / CRE54.14 / CRE54.20(1)-(2)(1): 2% on trade exposures to a QCCP."""
CCP_QCCP_CLIENT_NO_JOINT_DEFAULT_RW: Final[float] = 0.04
"""CRE54.16 / CRE54.20(2)(2): 4% where the client is not protected against the
joint default of the clearing member and another client."""
CCP_SETTLEMENT_ONLY_DF_RW: Final[float] = 0.0
"""CRE54.1 footnote 241: 0% for prefunded default funds covering settlement-risk-only products."""
CCP_KCCP_RW: Final[float] = 0.20
"""CRE54.29(1): RW of 20% (a minimum; footnote 244 allows supervisors to increase it)."""
CCP_KCCP_CAPITAL_RATIO: Final[float] = 0.08
"""CRE54.29(2): capital ratio 8%; K_CCP = sum_i EAD_i x RW x capital ratio (image, p. 491)."""
CCP_KCM_FLOOR_RATIO: Final[float] = 0.08
CCP_KCM_FLOOR_RW: Final[float] = 0.02
"""CRE54.36: K_CM_i = max(K_CCP x DF_i/(DF_CCP + DF_CM), 8% x 2% x DF_i) (image, p. 493);
footnote 245: "a floor on the default fund exposure risk weight of 2%"."""
CCP_NON_QUALIFYING_DF_RW: Final[float] = 12.50
"""CRE54.42: 1250% on funded and unfunded default fund contributions to a non-QCCP."""
CCP_QCCP_GRACE_MONTHS: Final[int] = 3
"""CRE54.6: trades with a former QCCP may be treated as QCCP trades for three months."""
CCP_MIN_MPOR_DAYS_OTC: Final[int] = 10
"""CRE54.8(2) / CRE54.33(1): minimum MPOR of 10 days for OTC trade exposures to CCPs."""
CCP_CLIENT_MIN_MPOR_DAYS: Final[int] = 5
"""CRE54.12: clearing member exposures to clients -- MPOR of at least five days."""
CAPITAL_TO_RWA: Final[float] = 12.5
"""RWA = 12.5 x capital requirement (reciprocal of the 8% capital ratio, RBC20.1)."""

# =========================================================================
#  National discretions / supervisory settings (defaults = BCBS base rules)
# =========================================================================


@dataclass(frozen=True)
class BCBSPillar1Options:
    """Discretions in the five Pillar 1 sections, with Framework defaults."""

    sec_erba_permitted: bool = True
    """CRE40.43(1) / CRE40.44: the jurisdiction permits the SEC-ERBA (and hence the SEC-IAA)."""

    m_cva: float = M_CVA
    """MAR50.41: m_CVA = 1; a supervisor may require a higher value."""

    reporting_currency: str = "USD"
    """MAR50.56 / MAR50.59: the bank's reporting currency (always a 'specified' IR
    currency; excluded from the FX buckets)."""

    central_bank_reserves_exemption: bool = False
    """LEV30.7: temporary exemption of central bank reserves (national discretion,
    exceptional macroeconomic circumstances; requires a recalibrated minimum)."""

    kccp_risk_weight: float = CCP_KCCP_RW
    """CRE54.29 footnote 244: 20% is a minimum; supervisors may increase it."""


DEFAULT_PILLAR1_OPTIONS: Final[BCBSPillar1Options] = BCBSPillar1Options()
