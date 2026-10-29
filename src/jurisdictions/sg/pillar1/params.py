"""Singapore Pillar 1 parameters -- securitisation, SA-CVA, leverage, large exposures, CCPs.

Every constant below is transcribed from the text of:

- MAS Notice 637, "Notice on Risk Based Capital Adequacy Requirements for Banks Incorporated
  in Singapore" (version effective 1 January 2026): Part IV Division 2 and Annexes 4C / 4D
  (leverage ratio), Part VII Division 1 Sub-division 7 and Division 6 (securitisation),
  Annex 7C (securitisation CCFs), Annex 7M Tables 7M-3 / 7M-4 (securitisation credit quality
  grades), Annex 7V Section 6 (tranche maturity), Part VII Division 7 (CCPs) and Part VIII
  Division 5 Sub-division 3 (SA-CVA);
- MAS Notice 656, "Exposures to Single Counterparty Groups for Banks Incorporated in
  Singapore" (last revised 22 May 2026, effective 1 July 2026): paragraphs 4, 7-11, 16, 28 and
  Annexes A and C (large exposures).

Page numbers are the Notices' own page footers (e.g. "p. 7-130"). The verbatim transcription
is ``docs/jurisdictions/SG_pillar1_reference.md``. Amounts are in SGD millions.
"""

from __future__ import annotations

from typing import Final

# =========================================================================
#  Securitisation -- MAS 637 Part VII Division 1 Sub-division 7 and Division 6
# =========================================================================

SEC_RW_1250: Final[float] = 12.50
"""Paras 7.1.14(b)(iii)(E), 7.6.19 (pp. 7-7, 7-127): 1250% where no approach can be applied."""
SEC_RW_FLOOR: Final[float] = 0.15
"""Paras 7.6.46, 7.6.48, 7.6.49, 7.6.77 (pp. 7-133 to 7-142): 15% risk-weight floor."""
STC_SENIOR_RW_FLOOR: Final[float] = 0.10
"""Para 7.6.98 (p. 7-147): STC minimum risk weight 10% for senior tranches."""
STC_NON_SENIOR_RW_FLOOR: Final[float] = 0.15
"""Para 7.6.98: STC minimum risk weight 15% for non-senior tranches."""
RESEC_RW_FLOOR: Final[float] = 1.00
"""Para 7.6.82 (p. 7-143): resecuritisation risk weight floor 100%."""
NPL_RW_FLOOR: Final[float] = 1.00
"""Para 7.6.88 (p. 7-144): 100% floor for NPL securitisation exposures (SEC-IRBA, SEC-SA,
look-through)."""
NPL_SENIOR_RW: Final[float] = 1.00
"""Para 7.6.89 (pp. 7-144, 7-145): 100% for a senior exposure to a traditional NPL
securitisation where non-refundable purchase price discounts >= 50% of the pool."""
NPL_NRPPD_THRESHOLD: Final[float] = 0.50
"""Para 7.6.89(b): NRPPD equal to or higher than 50% of the outstanding amount of the pool."""
NPL_W_THRESHOLD: Final[float] = 0.90
"""Para 7.6.85(a) (p. 7-144): an NPL securitisation has W >= 90%."""

SSFA_SCALAR: Final[float] = 12.5
"""Paras 7.6.46(b)-(c), 7.6.77(b)-(c): risk weight = K_SSFA x 12.5."""
CAPITAL_RATIO_8PCT: Final[float] = 0.08
"""Paras 7.6.63-7.6.64 (p. 7-140): K_SA = SA(CR) RWA / exposure x 8%."""

SEC_SA_P: Final[float] = 1.0
"""Para 7.6.76 (p. 7-142): supervisory parameter p = 1 under the SEC-SA (non-resecuritisation)."""
SEC_SA_P_RESEC: Final[float] = 1.5
"""Para 7.6.82(c) (p. 7-143): p = 1.5 for resecuritisation exposures."""
SEC_SA_P_STC: Final[float] = 0.5
"""Para 7.6.103 (p. 7-150): p = 0.5 under the SEC-SA for STC securitisation exposures."""
SEC_SA_W_PARAMETER: Final[float] = 0.5
"""Para 7.6.73 (p. 7-142): K_A = (1 - W) x K_SA + W x 0.5."""
SEC_SA_UNKNOWN_W_MAX_SHARE: Final[float] = 0.05
"""Para 7.6.74 (p. 7-142): delinquency status unknown for no more than 5% of the pool (by E);
above 5% the exposure is risk-weighted at 1250%."""

IRBA_P_FLOOR: Final[float] = 0.3
"""Paras 7.6.42(a), 7.6.99(a) (pp. 7-132, 7-147): floor of the supervisory parameter p."""
IRBA_STC_P_SCALAR: Final[float] = 0.5
"""Para 7.6.99 (p. 7-147): STC p = max[0.3, 0.5 x (A + B/N + C K_IRB + D LGD + E M_T)]."""
IRBA_GRANULARITY_N: Final[float] = 25.0
"""Table 7-28 / Table 7-31: granular N >= 25, non-granular N < 25."""
IRBA_SIMPLIFIED_MAX_C1: Final[float] = 0.03
"""Paras 7.6.40-7.6.41 (p. 7-131): simplified N / LGD where the largest exposure <= 3%."""
IRBA_SIMPLIFIED_LGD: Final[float] = 0.5
"""Paras 7.6.40-7.6.41: LGD_avg = 0.5 under the simplified method."""
MIXED_POOL_IRB_SHARE: Final[float] = 0.95
"""Paras 7.6.80-7.6.81 (p. 7-143): SEC-IRBA for a mixed pool only if K_IRB is available for at
least 95% of the underlying exposure amounts."""

IRBA_P_PARAMS: Final[dict[str, tuple[float, float, float, float, float]]] = {
    # key: (A, B, C, D, E) -- Table 7-28 (p. 7-132); Table 7-31 (STC, p. 7-147) is identical.
    "WHOLESALE_SENIOR_GRANULAR": (0.0, 3.56, -1.85, 0.55, 0.07),
    "WHOLESALE_SENIOR_NON_GRANULAR": (0.11, 2.61, -2.91, 0.68, 0.07),
    "WHOLESALE_NON_SENIOR_GRANULAR": (0.16, 2.87, -1.03, 0.21, 0.07),
    "WHOLESALE_NON_SENIOR_NON_GRANULAR": (0.22, 2.35, -2.46, 0.48, 0.07),
    "RETAIL_SENIOR": (0.0, 0.0, -7.48, 0.71, 0.24),
    "RETAIL_NON_SENIOR": (0.0, 0.0, -5.78, 0.55, 0.27),
}
"""Table 7-28 -- Parameters for Calculation of Supervisory Parameter under SEC-IRBA."""
IRBA_P_PARAMS_STC: Final[dict[str, tuple[float, float, float, float, float]]] = dict(
    IRBA_P_PARAMS
)
"""Table 7-31 -- Parameters for STC Securitisations under SEC-IRBA (same cells as Table 7-28)."""

ERBA_LONG_TERM_RW: Final[dict[int, tuple[float, float, float, float]]] = {
    # grade: (senior M_T=1, senior M_T=5, non-senior M_T=1, non-senior M_T=5) -- Table 7-30
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
    18: (12.50, 12.50, 12.50, 12.50),
}
"""Table 7-30 -- SEC-ERBA Risk Weights for Long-Term External Credit Assessment (p. 7-134)."""
ERBA_LONG_TERM_RW_STC: Final[dict[int, tuple[float, float, float, float]]] = {
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
    18: (12.50, 12.50, 12.50, 12.50),
}
"""Table 7-33 -- SEC-ERBA Risk Weights for STC Securitisations, Long-Term (p. 7-149)."""
ERBA_SHORT_TERM_RW: Final[dict[str, float]] = {"I": 0.15, "II": 0.50, "III": 1.00, "IV": 12.50}
"""Table 7-29 -- SEC-ERBA Risk Weights for Short-Term External Credit Assessment (p. 7-133);
"IV" = "All other credit assessments"."""
ERBA_SHORT_TERM_RW_STC: Final[dict[str, float]] = {"I": 0.10, "II": 0.30, "III": 0.60, "IV": 12.50}
"""Table 7-32 -- SEC-ERBA Risk Weights for STC Short-Term External Credit Assessments
(p. 7-148)."""
ERBA_THICKNESS_CAP: Final[float] = 0.5
"""Para 7.6.52 (p. 7-135): RW = RW_M adj. x [1 - min(T, 0.5)] for non-senior tranches."""
ERBA_MATURITY_LOW: Final[float] = 1.0
"""Para 7.6.50: interpolation between the one-year column ..."""
ERBA_MATURITY_HIGH: Final[float] = 5.0
"""... and the 5-year column of Table 7-30 / 7-33."""
IAA_MAX_LONG_TERM_GRADE: Final[int] = 10
"""Paras 7.6.59(c)(i), 7.6.61(b), 7.6.102(b) (pp. 7-137, 7-139, 7-149): an internal assessment
must map to grade "10" or better, otherwise 1250%."""
IAA_MAX_SHORT_TERM_GRADE: Final[str] = "III"
"""Paras 7.6.61(b), 7.6.102(b): short-term internal assessment must map to "III" or better."""
IAA_ELIGIBLE_SHORT_TERM_GRADES: Final[frozenset[str]] = frozenset({"I", "II", "III"})
"""Short-term grades "III" or better (Table 7M-4) eligible under paras 7.6.61(b) / 7.6.102(b)."""

SEC_LONG_TERM_GRADE: Final[dict[str, int]] = {
    # Table 7M-3 (Annex 7M, p. 7-272): Fitch / S&P notation and Moody's notation.
    "AAA": 1, "AA+": 2, "AA": 3, "AA-": 4, "A+": 5, "A": 6, "A-": 7,
    "BBB+": 8, "BBB": 9, "BBB-": 10, "BB+": 11, "BB": 12, "BB-": 13,
    "B+": 14, "B": 15, "B-": 16, "CCC+": 17, "CCC": 17, "CCC-": 17,
    "AA1": 2, "AA2": 3, "AA3": 4, "A1": 5, "A2": 6, "A3": 7,
    "BAA1": 8, "BAA2": 9, "BAA3": 10, "BA1": 11, "BA2": 12, "BA3": 13,
    "B1": 14, "B2": 15, "B3": 16, "CAA1": 17, "CAA2": 17, "CAA3": 17,
}  # fmt: skip
"""Table 7M-3 -- Credit Quality Grades for SEC-ERBA Exposures and SEC-IAA Exposures. Grade 18 =
"Below CCC-" / "Below Caa3" (any other assessment, e.g. CC, C, D, Ca, C)."""
SEC_BELOW_CCC_GRADE: Final[int] = 18
"""Table 7M-3 grade 18: below CCC- (Fitch / S&P) or below Caa3 (Moody's)."""
SEC_BELOW_CCC_RATINGS: Final[frozenset[str]] = frozenset({"CC", "C", "D", "SD", "RD", "CA"})
"""Assessments below CCC- / Caa3 recognised as grade 18 of Table 7M-3."""
SEC_SHORT_TERM_GRADE: Final[dict[str, str]] = {
    # Table 7M-4 (p. 7-272); Table 7M-2 para 1.1(a): A-1 includes A-1+ and A-1-.
    "F1": "I", "F-1": "I", "P-1": "I", "P1": "I", "A-1": "I", "A-1+": "I",
    "A-1-": "I", "A-1/P-1": "I",
    "F2": "II", "F-2": "II", "P-2": "II", "P2": "II", "A-2": "II", "A-2/P-2": "II",
    "F3": "III", "F-3": "III", "P-3": "III", "P3": "III", "A-3": "III", "A-3/P-3": "III",
}  # fmt: skip
"""Table 7M-4 -- Credit Quality Grades for Short-term SEC-ERBA / SEC-IAA Exposures; any other
assessment is grade "IV" ("Others")."""

TRANCHE_MATURITY_FLOOR: Final[float] = 1.0
"""Annex 7V para 6.3 (p. 7-318): M_T floor of one year."""
TRANCHE_MATURITY_CAP: Final[float] = 5.0
"""Annex 7V para 6.3: M_T cap of 5 years."""
TRANCHE_MATURITY_LEGAL_FACTOR: Final[float] = 0.80
"""Annex 7V para 6.1(b) (p. 7-317): M_T = 1 + (M_L - 1) x 80%."""

SEC_OBS_CCF: Final[dict[str, float]] = {
    "SERVICER_ADVANCE_UNCONDITIONALLY_CANCELLABLE": 0.10,  # item (a)
    "SERVICER_ADVANCE_OTHER": 1.00,  # item (b)
    "OTHER_FACILITY": 1.00,  # item (c) other facilities which are not credit risk mitigants
}
"""Annex 7C -- CCF for Off-balance Sheet Securitisation Exposures (p. 7-181); also applied to
off-balance sheet securitisation items in the leverage ratio (Annex 4C para 2.51(b))."""

# =========================================================================
#  SA-CVA -- MAS 637 Part VIII Division 5 Sub-division 3 (pp. 8-188 to 8-227)
# =========================================================================

SA_CVA_M_CVA: Final[float] = 1.0
"""Para 8.5.32(e)(i) (p. 8-197): m_CVA = 1 (the Authority may require a higher value)."""
SA_CVA_R: Final[float] = 0.01
"""Para 8.5.32(d)(ii) (p. 8-196): hedging disallowance parameter R = 0.01."""
CVA_RWA_MULTIPLIER: Final[float] = 12.5
"""Para 8.5.1 (p. 8-178): CVA RWA = 12.5 x (BA-CVA + SA-CVA capital)."""
REPORTING_CURRENCY: Final[str] = "SGD"
# TODO: VERIFY -- paras 8.5.36 / 8.5.40 key the IR tenor structure and the FX buckets to "the
# Reporting Bank's reporting currency", which the Notice does not fix; SGD assumed.
"""Paras 8.5.36 / 8.5.40: the Reporting Bank's reporting currency (Singapore dollar assumed)."""

IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"USD", "EUR", "GBP", "AUD", "CAD", "SEK", "JPY"}
)
"""Para 8.5.36 (p. 8-199): currencies (plus the reporting currency) with the tenor structure."""
IR_DELTA_RW_SPECIFIED: Final[dict[str, float]] = {
    "1Y": 0.0111,
    "2Y": 0.0093,
    "5Y": 0.0074,
    "10Y": 0.0074,
    "30Y": 0.0074,
    "INFLATION": 0.0111,
}
"""Table 8-28 -- Risk weights for interest rate risk class (reporting currency, USD, EUR, GBP,
AUD, CAD, SEK, JPY) (p. 8-200)."""
IR_DELTA_CORR_SPECIFIED: Final[dict[tuple[str, str], float]] = {
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
    ("1Y", "INFLATION"): 0.40,
    ("2Y", "INFLATION"): 0.40,
    ("5Y", "INFLATION"): 0.40,
    ("10Y", "INFLATION"): 0.40,
    ("30Y", "INFLATION"): 0.40,
}
"""Table 8-29 -- Correlations for interest rate risk factors (p. 8-200)."""
IR_DELTA_RW_OTHER: Final[float] = 0.0158
"""Para 8.5.37(c) (p. 8-201): 1.58% for the risk-free curve and inflation (other currencies)."""
IR_DELTA_CORR_OTHER: Final[float] = 0.40
"""Para 8.5.37(d): 40% between the risk-free yield curve and the inflation rate."""
IR_VEGA_RW: Final[float] = 1.00
"""Para 8.5.38(c) (p. 8-202): 100% for rate and inflation volatilities."""
IR_VEGA_CORR: Final[float] = 0.40
"""Para 8.5.38(d) (p. 8-203): 40% between rate volatility and inflation volatility."""
IR_GAMMA: Final[float] = 0.5
"""Para 8.5.39 (p. 8-203): cross-bucket gamma 0.5 for all currency pairs."""

FX_DELTA_RW: Final[float] = 0.11
"""Para 8.5.41(c) (p. 8-204): 11% for all exchange rates against the reporting currency."""
FX_VEGA_RW: Final[float] = 1.00
"""Para 8.5.43(c) (p. 8-204): 100% for FX volatilities."""
FX_GAMMA: Final[float] = 0.6
"""Para 8.5.45 (p. 8-205): cross-bucket gamma 0.6 for all currency pairs."""

CCS_RW: Final[dict[str, tuple[float, float]]] = {
    # bucket: (grade "3" or better, grade "4" or worse / not rated) -- Table 8-31
    "1a": (0.005, 0.020),  # sovereigns, central banks, BIS, IMF, ECB, EU, ESM, EFSF, MDBs
    "1b": (0.010, 0.040),  # PSEs, education
    "2": (0.050, 0.120),  # financial institutions
    "3": (0.030, 0.070),  # basic materials, energy, industrials, agriculture, manufacturing, mining
    "4": (0.030, 0.085),  # consumer goods/services, transportation/storage, admin & support
    "5": (0.020, 0.055),  # technology, telecommunications
    "6": (0.015, 0.050),  # health care, utilities, professional and technical activities
    "7": (0.050, 0.120),  # other sector
    "8": (0.015, 0.050),  # qualified indices
}
"""Table 8-31 -- Risk weights for counterparty credit spread delta risk (p. 8-209); buckets per
Table 8-30 (p. 8-206)."""
CCS_TENORS: Final[tuple[str, ...]] = ("0.5Y", "1Y", "3Y", "5Y", "10Y")
"""Para 8.5.50(a) (p. 8-206): tenors 0.5, 1, 3, 5 and 10 years."""
CCS_RHO_TENOR_DIFF: Final[float] = 0.90
"""Para 8.5.50(d)(i)(A)/(ii)(A): 90% if tenors differ (100% if the same)."""
CCS_RHO_NAME_RELATED: Final[float] = 0.90
"""Para 8.5.50(d)(i)(B)(II): 90% for parent/subsidiary or common-parent entities."""
CCS_RHO_NAME_UNRELATED: Final[float] = 0.50
"""Para 8.5.50(d)(i)(B)(III): 50% otherwise (buckets 1-7)."""
CCS_RHO_INDEX_SERIES_DIFF: Final[float] = 0.90
"""Para 8.5.50(d)(ii)(B)(II): same index, distinct series -- 90% (bucket 8)."""
CCS_RHO_INDEX_DIFF: Final[float] = 0.80
"""Para 8.5.50(d)(ii)(B)(III): different indices -- 80% (bucket 8)."""
CCS_RHO_QUALITY_DIFF: Final[float] = 0.80
"""Para 8.5.50(d)(i)(C)/(ii)(C) (p. 8-210): 80% if credit quality differs (8.5.51)."""
CCS_GAMMA: Final[dict[tuple[str, str], float]] = {
    ("1", "2"): 0.10, ("1", "3"): 0.20, ("1", "4"): 0.25, ("1", "5"): 0.20, ("1", "6"): 0.15,
    ("1", "7"): 0.0, ("1", "8"): 0.45,
    ("2", "3"): 0.05, ("2", "4"): 0.15, ("2", "5"): 0.20, ("2", "6"): 0.05, ("2", "7"): 0.0,
    ("2", "8"): 0.45,
    ("3", "4"): 0.20, ("3", "5"): 0.25, ("3", "6"): 0.05, ("3", "7"): 0.0, ("3", "8"): 0.45,
    ("4", "5"): 0.25, ("4", "6"): 0.05, ("4", "7"): 0.0, ("4", "8"): 0.45,
    ("5", "6"): 0.05, ("5", "7"): 0.0, ("5", "8"): 0.45,
    ("6", "7"): 0.0, ("6", "8"): 0.45,
    ("7", "8"): 0.0,
}  # fmt: skip
"""Table 8-32 -- Cross-bucket correlation for counterparty credit spread delta risk (p. 8-211)."""

RCS_DELTA_RW: Final[dict[int, float]] = {
    1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015,
    8: 0.020, 9: 0.040, 10: 0.120, 11: 0.070, 12: 0.085, 13: 0.055, 14: 0.050,
    15: 0.120, 16: 0.015, 17: 0.050,
}  # fmt: skip
"""Table 8-34 -- Risk weights for reference credit spread delta risk (p. 8-216); buckets per
Table 8-33 (p. 8-214): 1-7 grade "3" or better; 8-14 grade "4" or worse / not rated;
15 other sector; 16 / 17 qualified indices IG / non-IG."""
RCS_VEGA_RW: Final[float] = 1.00
"""Para 8.5.59(c) (p. 8-217): 100% for reference credit spread volatilities."""
RCS_GAMMA_SECTOR: Final[dict[tuple[int, int], float]] = {
    # sector index 1-7 (bucket b or b+7) -- Table 8-35 (p. 8-217)
    (1, 1): 1.00, (1, 2): 0.75, (1, 3): 0.10, (1, 4): 0.20, (1, 5): 0.25, (1, 6): 0.20,
    (1, 7): 0.15,
    (2, 2): 1.00, (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.15, (2, 7): 0.10,
    (3, 3): 1.00, (3, 4): 0.05, (3, 5): 0.15, (3, 6): 0.20, (3, 7): 0.05,
    (4, 4): 1.00, (4, 5): 0.20, (4, 6): 0.25, (4, 7): 0.05,
    (5, 5): 1.00, (5, 6): 0.25, (5, 7): 0.05,
    (6, 6): 1.00, (6, 7): 0.05,
    (7, 7): 1.00,
}  # fmt: skip
"""Table 8-35 cells for pairs of buckets 1-14 (by sector, "1 or 8" ... "7 or 14")."""
RCS_GAMMA_OTHER_BUCKET: Final[float] = 0.0
"""Table 8-35: bucket 15 against any bucket -- 0%."""
RCS_GAMMA_INDEX_VS_SECTOR: Final[float] = 0.45
"""Table 8-35: buckets 16 / 17 against buckets 1-14 -- 45%."""
RCS_GAMMA_INDEX_VS_INDEX: Final[float] = 0.75
"""Table 8-35: bucket 16 against bucket 17 -- 75%."""
RCS_DIFF_QUALITY_DIVISOR: Final[float] = 2.0
"""Para 8.5.60(a) (p. 8-217): Table 8-35 value divided by 2 for buckets 1-14 of different
credit quality."""

EQ_DELTA_RW: Final[dict[int, float]] = {
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,
    9: 0.70, 10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25,
}  # fmt: skip
"""Table 8-37 -- Risk weights for equity delta risk (p. 8-223); buckets per Table 8-36
(p. 8-221)."""
EQ_VEGA_RW_LARGE: Final[float] = 0.78
"""Para 8.5.68(c) (p. 8-224): 78% for a bucket corresponding to large market capitalisation."""
EQ_VEGA_RW_OTHER: Final[float] = 1.00
"""Para 8.5.68(c): 100% in all other cases."""
EQ_LARGE_CAP_BUCKETS: Final[frozenset[int]] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 12})
"""Table 8-36 (p. 8-221): buckets 1-8 are large market capitalisation; bucket 12 is "Large Market
Capitalisation and Advanced Economy" qualified indices."""
EQ_LARGE_CAP_USD_BN: Final[float] = 2.0
"""Para 8.5.66(a) (p. 8-219): large market capitalisation >= USD 2 billion."""
EQ_GAMMA_SECTOR: Final[float] = 0.15
"""Para 8.5.69(a) (p. 8-224): 15% between buckets 1-10."""
EQ_GAMMA_INDEX: Final[float] = 0.75
"""Para 8.5.69(b): 75% between buckets 12 and 13."""
EQ_GAMMA_INDEX_SECTOR: Final[float] = 0.45
"""Para 8.5.69(c): 45% between bucket 12/13 and buckets 1-10."""
EQ_GAMMA_OTHER: Final[float] = 0.0
"""Para 8.5.69(d): 0% where one bucket is bucket 11."""

COM_DELTA_RW: Final[dict[int, float]] = {
    1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45, 7: 0.20, 8: 0.35,
    9: 0.25, 10: 0.35, 11: 0.50,
}  # fmt: skip
"""Table 8-39 -- Risk weights for commodity delta risk (p. 8-226); buckets per Table 8-38."""
COM_VEGA_RW: Final[float] = 1.00
"""Para 8.5.72(c) (p. 8-227): 100% for commodity volatilities."""
COM_GAMMA: Final[float] = 0.20
"""Para 8.5.73(a) (p. 8-227): 20% between buckets 1-10."""
COM_GAMMA_OTHER: Final[float] = 0.0
"""Para 8.5.73(b): 0% where one bucket is bucket 11."""

# =========================================================================
#  Leverage ratio -- MAS 637 Part IV Division 2, Annexes 4C and 4D
# =========================================================================

LEVERAGE_MINIMUM: Final[float] = 0.03
"""Para 4.2.2 (p. 4-12): minimum leverage ratio of 3% at Solo and Group levels."""
LEVERAGE_ALPHA: Final[float] = 1.4
"""Annex 4C paras 2.13(a) / 2.14(a) (pp. 4-21, 4-22): alpha = 1.4."""
LEVERAGE_PFE_MULTIPLIER: Final[float] = 1.0
"""Annex 4C paras 2.13(c) / 2.14(c) / 2.17(b): the SA-CCR multiplier is fixed at one."""
LEVERAGE_CCF: Final[dict[str, float]] = {
    "DIRECT_CREDIT_SUBSTITUTE": 1.00,  # (a)
    "REPO_ASSET_SALE_WITH_RECOURSE": 1.00,  # (b)
    "CERTAIN_DRAWDOWN_COMMITMENT": 1.00,  # (c) forward purchases, forward deposits, partly paid
    "OTHER_CREDIT_SUBSTITUTE": 1.00,  # (d)
    "UNSETTLED_PURCHASE_COMMITMENT": 1.00,  # (e) settlement-date accounting
    "NIF_RUF": 0.50,  # (f)
    "TRANSACTION_RELATED_CONTINGENT": 0.50,  # (g)
    "OTHER_COMMITMENT": 0.40,  # (h) regardless of maturity
    "SHORT_TERM_TRADE_CONTINGENT": 0.20,  # (i) original maturity below one year
    "UNCONDITIONALLY_CANCELLABLE": 0.10,  # (j)
}
"""Table 4D-1 -- CCF for off-balance sheet items (Annex 4D, pp. 4-37, 4-38)."""
LEVERAGE_ALLOWED_CCFS: Final[frozenset[float]] = frozenset(
    set(LEVERAGE_CCF.values()) | set(SEC_OBS_CCF.values())
)
"""CCF values that Annex 4D (Table 4D-1) and Annex 7C can produce (10/20/40/50/100%)."""

# =========================================================================
#  Large exposures -- MAS Notice 656
# =========================================================================

LE_GENERAL_LIMIT: Final[float] = 0.25
"""MAS 656 paras 7 and 8(b) (pp. 10, 11): 25% of Tier 1 capital (Solo and Group)."""
LE_GSIB_TO_GSIB_LIMIT: Final[float] = 0.15
"""MAS 656 para 9 (p. 11): 15% of Tier 1 for a Singapore-headquartered G-SIB's exposures to any
other G-SIB (or a connected counterparty group including the G-SIB)."""
LE_GSIB_TRANSITION_MONTHS: Final[int] = 12
"""MAS 656 paras 10-11 (p. 11): the 15% limit applies within 12 months of becoming a G-SIB (or of
the counterparty becoming a G-SIB) on or after 1 July 2021."""
LE_REPORTING_THRESHOLD: Final[float] = 0.10
"""MAS 656 para 4 ("large exposure") and para 28(a)-(b) (pp. 6, 15): equal to or above 10% of
Tier 1 capital."""
LE_DUE_DILIGENCE_THRESHOLD: Final[float] = 0.05
"""MAS 656 para 16 (p. 12): economic-dependence due diligence where exposure > 5% of Tier 1."""
LE_OBS_CCF_FLOOR: Final[float] = 0.10
"""MAS 656 Annex C para 2.5 (p. 26): off-balance sheet CCF from Table 7B-1 with a floor of 10%."""
LE_LTA_THRESHOLD: Final[float] = 0.0025
"""MAS 656 Annex C paras 4.8-4.11 (pp. 33, 34): 0.25% of Tier 1 look-through threshold."""
LE_QUALIFYING_COVERED_BOND_FACTOR: Final[float] = 0.25
"""MAS 656 Annex C para 4.2 (p. 31): at least 25% of the nominal value of a qualifying covered
bond."""
LE_LARGEST_REPORTED: Final[int] = 20
"""MAS 656 para 28(c) (p. 15): the 20 largest exposures are reported."""

# =========================================================================
#  CCP exposures -- MAS 637 Part VII Division 7 (pp. 7-153 to 7-165)
# =========================================================================

QCCP_TRADE_RW: Final[float] = 0.02
"""Paras 7.7.15, 7.7.26, 7.7.28(a) (pp. 7-156 to 7-160): 2% of E / EAD."""
QCCP_CLIENT_RW_NO_JOINT_DEFAULT_PROTECTION: Final[float] = 0.04
"""Paras 7.7.23, 7.7.28(b) (pp. 7-159, 7-160): 4% where all 7.7.20 conditions except
7.7.20(b)(i)(C) are met."""
SEGREGATED_COLLATERAL_RW: Final[float] = 0.0
"""Paras 7.7.25, 7.7.27 (pp. 7-159, 7-160): no CCR capital for bankruptcy-remote collateral."""
KCCP_RISK_WEIGHT: Final[float] = 0.20
"""Para 7.7.41 (p. 7-163): K_CCP = sum EAD_i x 20% x 8%; the Authority may specify a higher
risk weight (7.7.42(e))."""
KCCP_CAPITAL_RATIO: Final[float] = 0.08
"""Para 7.7.41: 8% in K_CCP."""
DF_RW_FLOOR: Final[float] = 0.02
"""Para 7.7.44 (p. 7-166): 2% risk-weight floor on the default fund exposure
(K_CM >= 8% x 2% x DF_CM(Bank))."""
DF_CAPITAL_RATIO: Final[float] = 0.08
"""Para 7.7.44: 8% in the K_CM floor."""
NON_QCCP_DF_RW: Final[float] = 12.50
"""Para 7.7.6(b) (p. 7-155): 1250% of default fund exposures (funded and unfunded) to a
non-qualifying CCP."""
SETTLEMENT_ONLY_DF_RW: Final[float] = 0.0
"""Paras 7.7.4(b) / 7.7.6(b): 0% for contributions to pre-funded default funds covering
settlement-risk-only products."""
CCP_RWA_MULTIPLIER: Final[float] = 12.5
"""Para 7.7.4(b): default fund RWA = capital requirement x 12.5."""
QCCP_MIN_MPOR_DAYS: Final[int] = 10
"""Para 7.7.18(b) (p. 7-157): minimum MPOR of 10 business days for OTC derivative CCP trade
exposures."""
CLIENT_MIN_MPOR_DAYS: Final[int] = 5
"""Para 7.7.34 (p. 7-161): clearing member exposures to clients may use an MPOR of at least
5 business days."""
QCCP_LOSS_TRANSITION_MONTHS: Final[int] = 3
"""Para 7.7.10 (p. 7-155): QCCP treatment continues for 3 months after the CCP ceases to qualify."""
