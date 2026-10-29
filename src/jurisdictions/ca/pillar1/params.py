"""OSFI Pillar 1 parameters: securitization, SA-CVA, leverage, large exposures and CCPs.

Every constant is transcribed from the supplied OSFI text, with the OSFI section/paragraph and
the Basel Framework cross-reference OSFI prints in square brackets at the end of each paragraph:

- Securitization: OSFI *Capital Adequacy Requirements (CAR) Guideline (2026)* Chapter 6.
- SA-CVA: CAR 2026 Chapter 8 s.8.3.
- CCP exposures: CAR 2026 Chapter 7 s.7.1.8.
- Leverage exposure measure: OSFI *Leverage Requirements Guideline (2023)* ("LR"), effective
  February / April 2023. LR paragraph numbers are the guideline's own (the HTML conversion keeps
  the cross-references, e.g. "paragraph 53", not the paragraph labels, so the section headings are
  cited alongside).
- Large exposures: OSFI *Guideline B-2 Large Exposure Limits (2028)* ("B-2"), dated May 21, 2026,
  effective November 1, 2027 / January 1, 2028. **The supplied text is the consultation draft**
  ("Consultation closed August 19, 2026. We'll keep this draft on the site until the final
  guideline is released."). Scope: D-SIBs and Category I/II SMSBs (B-2 s.II).

Currency: CAR Ch.1 footnote 6 / Ch.8 footnote 4 -- "All dollar values in this guideline are in
Canadian dollars, unless otherwise noted." Dollar thresholds are CAD, as printed.

The verbatim transcription is ``docs/jurisdictions/CA_pillar1_reference.md``.
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import RatingBucket

R = RatingBucket

# =========================================================================
#  Chapter 6 -- Securitization
# =========================================================================

CAPITAL_TO_RWA: Final[float] = 12.5
"""CAR Ch.1 s.1.3 -- capital requirements are converted to RWA "by multiplying ... by 12.5"
(reciprocal of the 8% minimum); used for K_CM (CCP default funds) and CET1-deduction
equivalents."""

RW_1250: Final[float] = 12.50
"""CAR Ch.6 s.6.5.2 (paragraph 51) -- exposures to which no approach applies: 1250% [CRE 40.41]."""
CAPITAL_TO_RW: Final[float] = 12.5
"""CAR Ch.6 s.6.6.1.10 / s.6.6.4 -- risk weight = 12.5 x K_SEC [CRE 44.25, 41.14]."""

SEC_RW_FLOOR: Final[float] = 0.15
"""CAR Ch.6 s.6.6.1.10 (paragraph 106) [CRE 44.26], s.6.6.2.2 [CRE 42.7], s.6.6.4 [CRE 41.15] --
"The resulting risk weight is subject to a floor risk weight of 15%"."""
STC_SENIOR_RW_FLOOR: Final[float] = 0.10
STC_NON_SENIOR_RW_FLOOR: Final[float] = 0.15
"""CAR Ch.6 s.6.10.3 -- "Under all three approaches, the resulting risk weight is subject to a floor
risk weight of 10% for senior tranches, and 15% for non-senior tranches" [CRE 41.22, 42.14,
44.29]."""
RESEC_RW_FLOOR: Final[float] = 1.00
"""CAR Ch.6 s.6.7 -- resecuritization "subject to a floor risk weight of 100%" [CRE 41.18]."""
NPL_RW_FLOOR: Final[float] = 1.00
"""CAR Ch.6 s.6.12 -- NPL securitization RW under SEC-IRBA, SEC-SA or look-through "is floored at
100%" [CRE 45.4]."""
NPL_SENIOR_RW: Final[float] = 1.00
NPL_NRPPD_THRESHOLD: Final[float] = 0.50
"""CAR Ch.6 s.6.12 -- 100% RW for the senior tranche of a traditional NPL securitization where NRPPD
>= 50% of the outstanding pool balance (only where SEC-IRBA or SEC-SA would apply) [CRE 45.5]."""
NPL_W_THRESHOLD: Final[float] = 0.90
"""CAR Ch.6 s.6.2.1.11 -- NPL securitization: W >= 90% at cut-off and on any replenishment
[CRE 40.48, 45.1]."""

MIXED_POOL_KIRB_SHARE: Final[float] = 0.95
"""CAR Ch.6 s.6.5.2.3 -- SEC-IRBA with K = d K_IRB + (1-d) K_SA where K_IRB can be calculated for at
least 95% of the underlying exposures [CRE 40.46-40.47]."""

# --- Tranche maturity (s.6.2.1.16) ----------------------------------------------------------
TRANCHE_MATURITY_FLOOR_YEARS: Final[float] = 1.0
TRANCHE_MATURITY_CAP_YEARS: Final[float] = 5.0
"""CAR Ch.6 s.6.2.1.16 -- "In all cases, MT will have a floor of one year and a cap of five years"
[CRE 40.22]."""
LEGAL_MATURITY_FACTOR: Final[float] = 0.80
"""CAR Ch.6 s.6.2.1.16 -- M_T = 1 + (M_L - 1) x 80% on the basis of final legal maturity
[CRE 40.22]."""
PREPAYMENT_RATE_CAP: Final[float] = 0.20
"""CAR Ch.6 s.6.2.1.16 -- modelled annual prepayment rate capped at 20% (OSFI cash-flow M_T
method; not in the Basel CRE40.22 text)."""

# --- SEC-IRBA (s.6.6.1) ---------------------------------------------------------------------
IRBA_P_FLOOR: Final[float] = 0.3
"""CAR Ch.6 s.6.6.1.6 -- p = max[0.3; A + B/N + C K_IRB + D LGD + E M_T] [CRE 44.17]."""
STC_IRBA_P_SCALAR: Final[float] = 0.5
"""CAR Ch.6 s.6.10.3.1 -- STC: p = max[0.3; 0.5 x (A + B/N + C K_IRB + D LGD + E M_T)]
[CRE 44.28]."""
GRANULAR_N_THRESHOLD: Final[float] = 25.0
"""CAR Ch.6 s.6.6.1.6 look-up table -- granular "(N >= 25)", non-granular "(N < 25)"."""

IRBA_P_TABLE: Final[dict[tuple[str, bool, bool], tuple[float, float, float, float, float]]] = {
    # (asset class, senior, granular): (A, B, C, D, E)
    ("WHOLESALE", True, True): (0.0, 3.56, -1.85, 0.55, 0.07),
    ("WHOLESALE", True, False): (0.11, 2.61, -2.91, 0.68, 0.07),
    ("WHOLESALE", False, True): (0.16, 2.87, -1.03, 0.21, 0.07),
    ("WHOLESALE", False, False): (0.22, 2.35, -2.46, 0.48, 0.07),
    ("RETAIL", True, True): (0.0, 0.0, -7.48, 0.71, 0.24),
    ("RETAIL", True, False): (0.0, 0.0, -7.48, 0.71, 0.24),
    ("RETAIL", False, True): (0.0, 0.0, -5.78, 0.55, 0.27),
    ("RETAIL", False, False): (0.0, 0.0, -5.78, 0.55, 0.27),
}
"""CAR Ch.6 s.6.6.1.6 "Parameters to determine supervisory parameter p" (identical table in
s.6.10.3.1 for STC) [CRE 44.17, 44.28]. Retail rows do not depend on granularity."""
SIMPLIFIED_C1_MAX: Final[float] = 0.03
SIMPLIFIED_LGD: Final[float] = 0.50
"""CAR Ch.6 s.6.6.1.9 -- if C1 <= 3%, LGD may be set to 0.50 and N per the C1/Cm formula (or 1/C1)
[CRE 44.22]."""

# --- SEC-SA (s.6.6.4) -----------------------------------------------------------------------
SEC_SA_P: Final[float] = 1.0
"""CAR Ch.6 s.6.6.4 -- p = 1 for a securitization that is not a resecuritization [CRE 41.12]."""
STC_SEC_SA_P: Final[float] = 0.5
"""CAR Ch.6 s.6.10.3.3 -- p = 0.5 for an STC securitization [CRE 41.21]."""
RESEC_P: Final[float] = 1.5
"""CAR Ch.6 s.6.7 -- resecuritization p = 1.5 [CRE 41.16]."""
DELINQUENT_CAPITAL_FACTOR: Final[float] = 0.5
"""CAR Ch.6 s.6.6.4 -- K_A = (1 - W) K_SA + 0.5 W [CRE 41.8]."""
W_UNKNOWN_MAX_SHARE: Final[float] = 0.05
"""CAR Ch.6 s.6.6.4 -- delinquency status unknown for no more than 5% of the pool: adjusted K_A;
more than 5%: 1,250% [CRE 41.9-41.10]."""
DELINQUENCY_DAYS_PAST_DUE: Final[int] = 90
"""CAR Ch.6 s.6.6.4 -- delinquent = 90 days or more past due, bankruptcy, foreclosure, REO or
default [CRE 41.7]."""

# --- SEC-ERBA (s.6.6.2) ---------------------------------------------------------------------
ERBA_SHORT_TERM_RW: Final[dict[str, float]] = {
    "A-1/P-1": 0.15, "A-2/P-2": 0.50, "A-3/P-3": 1.00, "OTHER": 12.50,
}
"""CAR Ch.6 s.6.6.2.1 Table 1 "SEC-ERBA risk weights for short-term ratings" [CRE 42.2]."""
STC_ERBA_SHORT_TERM_RW: Final[dict[str, float]] = {
    "A-1/P-1": 0.10, "A-2/P-2": 0.30, "A-3/P-3": 0.60, "OTHER": 12.50,
}
"""CAR Ch.6 s.6.10.3.2 Table 1' (STC) [CRE 42.12]."""

ERBA_RATING_ORDER: Final[tuple[str, ...]] = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC", "BELOW_CCC-",
)
"""Rows of CAR Ch.6 Table 2 / Table 2' ("CCC+/CCC/CCC-" collapsed to "CCC")."""

ERBA_LONG_TERM_RW: Final[dict[str, tuple[float, float, float, float]]] = {
    # rating: (senior 1y, senior 5y, non-senior 1y, non-senior 5y)
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
    "CCC": (4.60, 5.05, 12.50, 12.50),
    "BELOW_CCC-": (12.50, 12.50, 12.50, 12.50),
}
"""CAR Ch.6 s.6.6.2.2 Table 2 "SEC-ERBA risk weights for long-term ratings" [CRE 42.4]."""

STC_ERBA_LONG_TERM_RW: Final[dict[str, tuple[float, float, float, float]]] = {
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
    "CCC": (4.15, 4.55, 12.50, 12.50),
    "BELOW_CCC-": (12.50, 12.50, 12.50, 12.50),
}
"""CAR Ch.6 s.6.10.3.2 Table 2' "SEC-ERBA risk weights for long-term ratings for STC
securitizations" [CRE 42.13]."""
ERBA_MATURITY_SHORT_YEARS: Final[float] = 1.0
ERBA_MATURITY_LONG_YEARS: Final[float] = 5.0
"""CAR Ch.6 s.6.6.2.2 -- "linear interpolation between the risk weights for one and five years"
[CRE 42.5]."""
ERBA_THICKNESS_CAP: Final[float] = 0.50
"""CAR Ch.6 s.6.6.2.2 -- non-senior RW x [1 - min(T, 50%)], T = D - A [CRE 42.5]."""

# --- Off-balance sheet securitization exposures (s.6.5.1.1) --------------------------------
SEC_CCF_CLIENT_VEHICLE_COMMITMENT: Final[float] = 0.40
SEC_CCF_SERVICER_ADVANCE_UCC: Final[float] = 0.10
SEC_CCF_OTHER_COMMITMENT: Final[float] = 1.00
"""CAR Ch.6 s.6.5.1.1 -- undrawn securitization commitments to fund client vehicle acquisitions 40%;
unconditionally cancellable servicer cash advances 10%; other securitization commitments that are
not credit risk mitigants 100% [CRE 40.20]."""

# --- Interest-only strips (s.6.5.1) -----------------------------------------------------------
IO_STRIP_CREDIT_ENHANCING_RW: Final[float] = 12.50
IO_STRIP_PREPAYMENT_RW: Final[float] = 2.50
IO_STRIP_OTHER_RW: Final[float] = 1.00
"""CAR Ch.6 s.6.5.1 -- credit-enhancing I/O strips 1250%; other unrated I/O strips subject to
prepayment risk 250%; not subject to prepayment risk 100% (OSFI-specific, consistent with CAR
s.4.1.23) [CAP 30.14]."""

# --- STC additional capital criteria (Appendix 6-1 D1-D2) --------------------------------------
STC_D1_MAX_RW: Final[dict[str, float]] = {
    "RESIDENTIAL_MORTGAGE_PORTFOLIO_AVERAGE": 0.40,
    "COMMERCIAL_MORTGAGE_INDIVIDUAL": 0.50,
    "RETAIL_INDIVIDUAL": 0.75,
    "OTHER_PORTFOLIO_AVERAGE": 1.00,
}
"""CAR Ch.6 Appendix 6-1 D1 -- maximum SA risk weights of the underlying exposures [CRE 40.94]."""
STC_D2_MAX_SINGLE_OBLIGOR_SHARE: Final[float] = 0.01
"""CAR Ch.6 Appendix 6-1 D2 -- single-obligor share <= 1% of the portfolio [CRE 40.95]."""

# =========================================================================
#  Chapter 8 s.8.3 -- SA-CVA
# =========================================================================

SA_CVA_M_CVA: Final[float] = 1.0
"""CAR Ch.8 s.8.3.3 -- "The multiplier mcva is set at 1" (OSFI may require a higher value)
[MAR 50.41]."""
SA_CVA_R: Final[float] = 0.01
"""CAR Ch.8 s.8.3.4 -- "R is the hedging disallowance parameter, set at 0.01" [MAR 50.53]."""
CVA_RWA_MULTIPLIER: Final[float] = 12.5
"""CAR Ch.8 s.8.1 -- RWA = 12.5 x CVA capital [MAR 50.1]."""

# --- Interest rate (s.8.3.5) --------------------------------------------------------------------
SA_CVA_IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"USD", "EUR", "GBP", "AUD", "CAD", "SEK", "JPY"})
"""CAR Ch.8 s.8.3.5 -- tenor-based risk factors for the reporting currency and USD, EUR, GBP, AUD,
CAD, SEK, JPY [MAR 50.56]."""
SA_CVA_IR_TENORS: Final[tuple[str, ...]] = ("1Y", "2Y", "5Y", "10Y", "30Y", "INFLATION")
SA_CVA_IR_DELTA_RW_SPECIFIED: Final[dict[str, float]] = {
    "1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074, "10Y": 0.0074, "30Y": 0.0074, "INFLATION": 0.0111,
}
"""CAR Ch.8 s.8.3.5 Table 3 "Risk weight for interest rate risk factors (specified currencies)"
[MAR 50.56]."""
SA_CVA_IR_DELTA_CORR_SPECIFIED: Final[dict[tuple[str, str], float]] = {
    ("1Y", "2Y"): 0.91, ("1Y", "5Y"): 0.72, ("1Y", "10Y"): 0.55, ("1Y", "30Y"): 0.31,
    ("2Y", "5Y"): 0.87, ("2Y", "10Y"): 0.72, ("2Y", "30Y"): 0.45,
    ("5Y", "10Y"): 0.91, ("5Y", "30Y"): 0.68,
    ("10Y", "30Y"): 0.83,
    ("1Y", "INFLATION"): 0.40, ("2Y", "INFLATION"): 0.40, ("5Y", "INFLATION"): 0.40,
    ("10Y", "INFLATION"): 0.40, ("30Y", "INFLATION"): 0.40,
}
"""CAR Ch.8 s.8.3.5 Table 4 "Correlations for interest rate risk factors (specified currencies)"
(upper triangle) [MAR 50.56]."""
SA_CVA_IR_DELTA_RW_OTHER: Final[float] = 0.0158
SA_CVA_IR_DELTA_CORR_OTHER: Final[float] = 0.40
"""CAR Ch.8 s.8.3.5 -- other currencies: parallel-shift and inflation risk factors, RW 1.58% each,
correlation 40% [MAR 50.57]."""
SA_CVA_IR_VEGA_RW: Final[float] = 1.00
SA_CVA_IR_VEGA_CORR: Final[float] = 0.40
"""CAR Ch.8 s.8.3.5 -- IR and inflation volatility RW 100%, correlation 40% [MAR 50.58]."""
SA_CVA_IR_GAMMA: Final[float] = 0.50
"""CAR Ch.8 s.8.3.5 -- cross-bucket correlation 0.5 for all currency pairs [MAR 50.55]."""

# --- FX (s.8.3.6) ------------------------------------------------------------
SA_CVA_FX_DELTA_RW: Final[float] = 0.11
"""CAR Ch.8 s.8.3.6 -- FX delta risk weight 11% [MAR 50.61]."""
SA_CVA_FX_VEGA_RW: Final[float] = 1.00
"""CAR Ch.8 s.8.3.6 -- FX volatility risk weight 100% [MAR 50.62]."""
SA_CVA_FX_GAMMA: Final[float] = 0.60
"""CAR Ch.8 s.8.3.6 -- cross-bucket correlation 0.6 [MAR 50.60]."""

# --- Counterparty credit spread (s.8.3.7) ------------------------------------------------------
SA_CVA_CCS_BUCKETS: Final[tuple[str, ...]] = ("1a", "1b", "2", "3", "4", "5", "6", "7", "8")
"""CAR Ch.8 s.8.3.7 Table 5 -- 1a sovereigns/central banks/MDBs; 1b local government,
government-backed non-financials, education, public administration; 2 financials; 3 basic
materials, energy, industrials, agriculture, manufacturing, mining; 4 consumer goods/services,
transportation, administrative; 5 technology, telecommunications; 6 health care, utilities,
professional/technical; 7 other sector; 8 qualified indices [MAR 50.63]."""
SA_CVA_CCS_TENORS: Final[tuple[str, ...]] = ("0.5Y", "1Y", "3Y", "5Y", "10Y")
"""CAR Ch.8 s.8.3.7 -- tenors 0.5, 1, 3, 5 and 10 years [MAR 50.65]."""
SA_CVA_CCS_RW: Final[dict[str, tuple[float, float]]] = {
    # bucket: (IG, HY and NR)
    "1a": (0.005, 0.020), "1b": (0.010, 0.040), "2": (0.050, 0.120), "3": (0.030, 0.070),
    "4": (0.030, 0.085), "5": (0.020, 0.055), "6": (0.015, 0.050), "7": (0.050, 0.120),
    "8": (0.015, 0.050),
}
"""CAR Ch.8 s.8.3.7 Table 7 "Risk weights for counterparty credit spread delta risk" [MAR 50.65]."""
SA_CVA_CCS_GAMMA: Final[dict[tuple[str, str], float]] = {
    ("1", "2"): 0.10, ("1", "3"): 0.20, ("1", "4"): 0.25, ("1", "5"): 0.20, ("1", "6"): 0.15,
    ("1", "7"): 0.0, ("1", "8"): 0.45,
    ("2", "3"): 0.05, ("2", "4"): 0.15, ("2", "5"): 0.20, ("2", "6"): 0.05, ("2", "7"): 0.0,
    ("2", "8"): 0.45,
    ("3", "4"): 0.20, ("3", "5"): 0.25, ("3", "6"): 0.05, ("3", "7"): 0.0, ("3", "8"): 0.45,
    ("4", "5"): 0.25, ("4", "6"): 0.05, ("4", "7"): 0.0, ("4", "8"): 0.45,
    ("5", "6"): 0.05, ("5", "7"): 0.0, ("5", "8"): 0.45,
    ("6", "7"): 0.0, ("6", "8"): 0.45,
    ("7", "8"): 0.0,
}
"""CAR Ch.8 s.8.3.7 Table 6 "Cross-bucket correlations for counterparty credit spread delta risk"
(upper triangle; bucket 1 covers 1a and 1b) [MAR 50.64]."""
SA_CVA_CCS_RHO_TENOR_DIFF: Final[float] = 0.90
SA_CVA_CCS_RHO_NAME_LEGAL: Final[float] = 0.90
SA_CVA_CCS_RHO_NAME_OTHER: Final[float] = 0.50
SA_CVA_CCS_RHO_QUALITY_DIFF: Final[float] = 0.80
"""CAR Ch.8 s.8.3.7 -- buckets 1-7: rho_tenor 100%/90%; rho_name 100% same, 90% distinct but
legally related, 50% otherwise; rho_quality 100%/80% [MAR 50.65]."""
SA_CVA_CCS_IDX_RHO_NAME_SERIES: Final[float] = 0.90
SA_CVA_CCS_IDX_RHO_NAME_OTHER: Final[float] = 0.80
"""CAR Ch.8 s.8.3.7 -- bucket 8: rho_name 100% same index and series, 90% same index distinct
series, 80% otherwise (rho_tenor and rho_quality as buckets 1-7) [MAR 50.65]."""

# --- Reference credit spread (s.8.3.8) ---------------------------------------------------------
SA_CVA_RCS_RW: Final[dict[int, float]] = {
    1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015,
    8: 0.020, 9: 0.040, 10: 0.120, 11: 0.070, 12: 0.085, 13: 0.055, 14: 0.050,
    15: 0.120, 16: 0.015, 17: 0.050,
}
"""CAR Ch.8 s.8.3.8 Table 10 "Risk weights for reference credit spread delta risk" [MAR 50.68].
Table 8 buckets: 1-7 IG sectors, 8-14 HY/NR sectors (same order), 15 other sector, 16 IG qualified
indices, 17 HY qualified indices. (The flattened Table 10 labels rows 8-9 "IG" and 16-17 "HY/NR";
the bucket numbers and values follow Table 8 and MAR 50.68.)"""
SA_CVA_RCS_GAMMA: Final[dict[tuple[str, str], float]] = {
    ("1", "2"): 0.75, ("1", "3"): 0.10, ("1", "4"): 0.20, ("1", "5"): 0.25, ("1", "6"): 0.20,
    ("1", "7"): 0.15, ("1", "15"): 0.0, ("1", "16"): 0.45, ("1", "17"): 0.45,
    ("2", "3"): 0.05, ("2", "4"): 0.15, ("2", "5"): 0.20, ("2", "6"): 0.15, ("2", "7"): 0.10,
    ("2", "15"): 0.0, ("2", "16"): 0.45, ("2", "17"): 0.45,
    ("3", "4"): 0.05, ("3", "5"): 0.15, ("3", "6"): 0.20, ("3", "7"): 0.05, ("3", "15"): 0.0,
    ("3", "16"): 0.45, ("3", "17"): 0.45,
    ("4", "5"): 0.20, ("4", "6"): 0.25, ("4", "7"): 0.05, ("4", "15"): 0.0, ("4", "16"): 0.45,
    ("4", "17"): 0.45,
    ("5", "6"): 0.25, ("5", "7"): 0.05, ("5", "15"): 0.0, ("5", "16"): 0.45, ("5", "17"): 0.45,
    ("6", "7"): 0.05, ("6", "15"): 0.0, ("6", "16"): 0.45, ("6", "17"): 0.45,
    ("7", "15"): 0.0, ("7", "16"): 0.45, ("7", "17"): 0.45,
    ("15", "16"): 0.0, ("15", "17"): 0.0,
    ("16", "17"): 0.75,
}
"""CAR Ch.8 s.8.3.8 Table 9 "Cross-bucket correlations for reference credit spread risk", keyed by
sector rows "1/8".."7/14" (as "1".."7"), 15, 16, 17 (upper triangle). Between buckets 1-14 of
different credit quality the value is divided by 2 [MAR 50.67]."""
SA_CVA_RCS_DIFF_QUALITY_DIVISOR: Final[float] = 2.0
"""CAR Ch.8 s.8.3.8 -- "the correlations ... are divided by 2" [MAR 50.67(2)]."""
SA_CVA_RCS_VEGA_RW: Final[float] = 1.00
"""CAR Ch.8 s.8.3.8 -- reference credit spread volatility RW 100% [MAR 50.69]."""

# --- Equity (s.8.3.9) ------------------------------------------------------------
SA_CVA_EQ_LARGE_CAP_THRESHOLD_CAD_M: Final[float] = 2_500.0
"""CAR Ch.8 s.8.3.9 -- "'Large market cap' is defined as a market capitalization equal to or greater
than $2.5 billion" (CAD, footnote 4). Basel MAR 50.70: USD 2 billion."""
SA_CVA_EQ_DELTA_RW: Final[dict[int, float]] = {
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50, 9: 0.70, 10: 0.50,
    11: 0.70, 12: 0.15, 13: 0.25,
}
"""CAR Ch.8 s.8.3.9 Table 12 "Risk weights for equity delta risk" [MAR 50.72]."""
SA_CVA_EQ_LARGE_CAP_BUCKETS: Final[frozenset[int]] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 12})
"""CAR Ch.8 s.8.3.9 Table 11 -- buckets with Size "Large" (1-8) or "Large cap" (12)."""
SA_CVA_EQ_VEGA_RW_LARGE: Final[float] = 0.78
SA_CVA_EQ_VEGA_RW_OTHER: Final[float] = 1.00
"""CAR Ch.8 s.8.3.9 -- equity volatility RW 78% for large market capitalization buckets, 100% for
the other buckets [MAR 50.73]."""
SA_CVA_EQ_GAMMA_1_10: Final[float] = 0.15
SA_CVA_EQ_GAMMA_12_13: Final[float] = 0.75
SA_CVA_EQ_GAMMA_IDX_VS_1_10: Final[float] = 0.45
SA_CVA_EQ_GAMMA_BUCKET_11: Final[float] = 0.0
"""CAR Ch.8 s.8.3.9 -- 15% within 1-10; 75% between 12 and 13; 45% between 12/13 and 1-10; 0% with
bucket 11 [MAR 50.71]."""

# --- Commodity (s.8.3.10) ------------------------------------------------------------
SA_CVA_COM_DELTA_RW: Final[dict[int, float]] = {
    1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45, 7: 0.20, 8: 0.35, 9: 0.25, 10: 0.35,
    11: 0.50,
}
"""CAR Ch.8 s.8.3.10 Table 14 "Risk weights for commodity delta risk" [MAR 50.76]."""
SA_CVA_COM_VEGA_RW: Final[float] = 1.00
"""CAR Ch.8 s.8.3.10 -- commodity volatility RW 100% [MAR 50.77]."""
SA_CVA_COM_GAMMA_1_10: Final[float] = 0.20
SA_CVA_COM_GAMMA_BUCKET_11: Final[float] = 0.0
"""CAR Ch.8 s.8.3.10 -- 20% within buckets 1-10; 0% with bucket 11 [MAR 50.75]."""

# =========================================================================
#  Leverage Requirements Guideline (2023)
# =========================================================================

LR_MINIMUM: Final[float] = 0.03
"""LR s.IV (paragraph 17) -- "Institutions are expected to maintain a leverage ratio that meets or
exceeds 3% at all times" [LEV 20.7]. Confirms CAR Ch.4 s.4.1.4."""
LR_DSIB_BUFFER_SHARE_OF_HLA: Final[float] = 0.50
"""LR s.IV -- "The leverage ratio buffer will be set at 50% of a D-SIB's higher-loss absorbency
risk-weighted requirements. For example, a D-SIB subject to a 1% higher-loss absorbency
requirement would be subject to a 0.5% leverage ratio buffer requirement. This means that DSIBs
are expected to maintain a leverage ratio that meets or exceeds 3.5% at all times." [LEV 40.2]."""
LR_DSIB_CONSERVATION_BANDS: Final[tuple[tuple[float, float, float], ...]] = (
    (0.05375, 0.03125, 1.00), (0.0625, 0.0325, 0.80), (0.07125, 0.03375, 0.60),
    (0.080, 0.035, 0.40),
)
"""LR s.IV Table 1 -- (CET1 upper bound, Tier 1 leverage upper bound, minimum conservation ratio)
for a D-SIB in the first HLA bucket; above 8.0% / 3.50% -> 0% [LEV 40.5]. Identical to CAR Ch.1
Table 7."""
LR_DERIVATIVE_ALPHA: Final[float] = 1.4
"""LR s.VI(b)(i) (paragraph 37, per LR's "paragraphs 37 to 49") -- derivative exposure = alpha 1.4
x (RC + PFE) "as described in section 7.1.7 of the CAR Guideline" [LEV 30.14]. No leverage-specific
SA-CCR modification (the Basel LEV30.15-30.24 fixed multiplier of one and cash-VM-only RC are not
in the OSFI text)."""
LR_CCF: Final[dict[str, float]] = {
    "UNCONDITIONALLY_CANCELLABLE": 0.10,   # [LEV 30.54]; excludes paragraph 72 (cards)
    "CREDIT_CARD_UNDRAWN": 0.25,           # paragraph 72 (OSFI-specific, no Basel ref)
    "COMMITMENT_OTHER": 0.40,              # [LEV 30.52] "regardless of the maturity"
    "SHORT_TERM_TRADE_LC": 0.20,           # [LEV 30.53] issuing and confirming institutions
    "TRANSACTION_RELATED_CONTINGENT": 0.50,  # [LEV 30.51]
    "NIF_RUF": 0.50,                       # [LEV 30.50]
    "DIRECT_CREDIT_SUBSTITUTE": 1.00,      # [LEV 30.49] guarantees, acceptances
    "FORWARD_ASSET_PURCHASE": 1.00,        # [LEV 30.49] incl. forward deposits, partly paid
    "UNSETTLED_PURCHASE": 1.00,            # [LEV 30.49] settlement-date accounting
    "OTHER_CREDIT_SUBSTITUTE": 1.00,       # [LEV 30.49] residual credit substitutes
}
"""LR s.VI(d) (paragraphs 61-75) -- off-balance-sheet credit conversion factors. "Undrawn balances
of credit card and charge card exposures will receive a CCF of 25%" has no Basel counterpart.
LR paragraph numbers are cited only where the guideline's own cross-references fix them."""
LR_PERMITTED_CCFS: Final[frozenset[float]] = frozenset(LR_CCF.values())

# =========================================================================
#  Guideline B-2 Large Exposure Limits (2028) -- consultation draft
# =========================================================================

# TODO: VERIFY -- every B-2 value below is taken from the May 21, 2026 consultation draft
# (consultation closed August 19, 2026); confirm against the final guideline when published.
LE_REPORTING_THRESHOLD: Final[float] = 0.10
"""B-2 s.III -- large exposure: >= 10% of Tier 1 capital [LEX 10.8, 20.2]."""
LE_LIMIT_GENERAL: Final[float] = 0.25
"""B-2 s.IV -- "otherwise, 25% of the institution's Tier 1 capital"; Category I/II SMSBs 25%
[LEX 20.1]."""
LE_LIMIT_GSIB_TO_GSIB: Final[float] = 0.15
"""B-2 s.IV -- Canadian G-SIB: 15% where the counterparty is (or the group includes) a G-SIB
[LEX 40.1]."""
LE_LIMIT_DSIB_INTERCONNECTED: Final[float] = 0.20
"""B-2 s.IV -- Canadian G-SIB: 20% where the counterparty is (or the group includes) a Canadian
D-SIB that is not a G-SIB; Canadian D-SIB (non-G-SIB): 20% where the counterparty is (or the group
includes) a Canadian D-SIB or a G-SIB. OSFI-specific (no Basel counterpart)."""
LE_NEW_GSIB_TRANSITION_MONTHS: Final[int] = 12
"""B-2 footnote 12 -- 15% limit for newly designated G-SIBs within 12 months of the FSB list."""
LE_OBS_CCF_FLOOR: Final[float] = 0.10
"""B-2 s.VI -- off-balance sheet CCFs per CAR s.4.1.18 "subject to a minimum value of 10%"
[LEX 30.6]."""
LE_STRUCTURE_LOOKTHROUGH_THRESHOLD: Final[float] = 0.0025
LE_SMSB_STRUCTURE_THRESHOLD_FLOOR_CAD_M: Final[float] = 1.5
"""B-2 s.VI (paragraph 48) -- structured vehicles: 0.25% of Tier 1; Category I/II SMSB applicable
threshold max(0.25% of Tier 1, $1.5 million) [LEX 30.42]."""
LE_ECONOMIC_INTERDEPENDENCE_REVIEW: Final[float] = 0.05
"""B-2 s.VII -- thorough interdependence investigation where an exposure exceeds 5% of Tier 1
[LEX 10.18]."""
LE_QUALIFYING_COVERED_BOND_FACTOR: Final[float] = 0.25
LE_NON_QUALIFYING_COVERED_BOND_FACTOR: Final[float] = 1.00
"""B-2 s.VI (paragraph 27) -- qualifying covered bonds: exposure value no less than 25% of nominal;
non-qualifying 100% [LEX 20.21, 30.38]."""
LE_COVERED_BOND_OVERCOLLATERALISATION: Final[float] = 0.05
LE_COVERED_BOND_RRE_MAX_RW: Final[float] = 0.35
LE_COVERED_BOND_RRE_MAX_LTV: Final[float] = 0.80
LE_COVERED_BOND_CRE_MAX_RW: Final[float] = 1.00
LE_COVERED_BOND_CRE_MAX_LTV: Final[float] = 0.60
"""B-2 s.VI (paragraph 28) -- cover pool RRE (RW <= 35%, LTV <= 80%), CRE (RW <= 100%,
LTV <= 60%); over-collateralization >= 5% [LEX 30.39]."""

# =========================================================================
#  Chapter 7 s.7.1.8 -- central counterparties
# =========================================================================

QCCP_CLEARING_MEMBER_RW: Final[float] = 0.02
"""CAR Ch.7 s.7.1.8.1 A(i) -- 2% on clearing member trade exposures to a QCCP [CRE 54.7]."""
QCCP_CLIENT_RW: Final[float] = 0.02
"""CAR Ch.7 s.7.1.8.1 A(iii) -- client exposures meeting the two conditions: clearing member
treatment (2%) [CRE 54.14-54.15]."""
QCCP_CLIENT_NOT_PROTECTED_JOINT_DEFAULT_RW: Final[float] = 0.04
"""CAR Ch.7 s.7.1.8.1 A(iii) -- 4% where the client is not protected against the joint default of
the clearing member and another client (OSFI prints "[Basel Framework, CRE 53.16]"; CRE 54.16)."""
QCCP_POSTED_COLLATERAL_BANKRUPTCY_REMOTE_RW: Final[float] = 0.0
"""CAR Ch.7 s.7.1.8.1 A(iv) -- collateral held by a custodian and bankruptcy remote from the CCP:
no CCR capital requirement [CRE 54.21]."""
KCCP_RISK_WEIGHT: Final[float] = 0.20
"""CAR Ch.7 s.7.1.8.1 B -- K_CCP = sum EAD_i x RW x capital ratio, "RW is a risk weight of 20%"
(footnote 47: a minimum; OSFI may increase it) [CRE 54.29]."""
KCCP_CAPITAL_RATIO: Final[float] = 0.08
"""CAR Ch.7 s.7.1.8.1 B -- "Capital ratio means 8%" [CRE 54.29]."""
KCM_FLOOR_RW: Final[float] = 0.02
KCM_FLOOR_CAPITAL_RATIO: Final[float] = 0.08
"""CAR Ch.7 s.7.1.8.1 B -- K_CM_i = max(K_CCP x DF_i / (DF_CCP + DF_CM); 8% x 2% x DF_i)
[CRE 54.36]."""
KCCP_MPOR_DAYS: Final[int] = 10
"""CAR Ch.7 s.7.1.8.1 B (footnote 48) -- MPOR of 10 days for the CCP's PFE to its clearing members
[CRE 54.33]."""
CCP_CLIENT_MPOR_FLOOR_DAYS: Final[int] = 5
"""CAR Ch.7 s.7.1.8.1 A(ii) -- clearing member exposures to clients: MPOR of at least five days
[CRE 54.12]."""
CCP_TRADE_MPOR_FLOOR_DAYS: Final[int] = 10
"""CAR Ch.7 s.7.1.8.1 A(i) -- minimum MPOR of 10 days for OTC derivative trade exposures to CCPs
[CRE 54.8]."""
FORMER_QCCP_GRACE_MONTHS: Final[int] = 3
"""CAR Ch.7 s.7.1.8 -- trades with a former QCCP may be treated as QCCP trades for three months
[CRE 54.6]."""
NON_QCCP_DF_DEDUCTION_RW_EQUIVALENT: Final[float] = CAPITAL_TO_RWA
"""CAR Ch.7 s.7.1.8.2 -- default fund contributions to a non-qualifying CCP are deducted from CET1
[CRE 54.42]; expressed here as the RWA equivalent 12.5 x amount."""
