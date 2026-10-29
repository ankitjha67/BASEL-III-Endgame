"""UK PRA Pillar 1 parameters -- securitisation, SA-CVA, leverage, large exposures, CCPs.

Every constant used by :mod:`src.jurisdictions.uk.pillar1` is defined here with
the PRA Rulebook provision it is transcribed from. Sources (PRA Rulebook as in
force on 1 January 2027):

* Securitisation (CRR) Part -- Articles 242-270F ("Sec Part").
* Credit Valuation Adjustment Risk Part, Chapter 5 (SA-CVA) -- PS1/26 Appendix 1
  (PRA2026/1) Annex K, rules 5.14-5.30, p. 408-422 ("CVA Part").
* Leverage Ratio (CRR) Part -- Articles 429-429g ("LR Part").
* Large Exposures (CRR) Part -- rule 1.2, Articles 390-403 ("LE Part").
* Counterparty Credit Risk (CRR) Part, Section 9 -- Articles 300-311 ("CCR Part").
* Credit Risk: General Provisions (CRR) Part Article 107(2) (PS1/26 Appendix 1).

Formulas printed as images on the Rulebook web pages (CCR Part Art 308(2);
LR Part Art 429e(2)-(3)) are taken from the identical formula of Regulation (EU)
No 575/2013 (consolidated 9 July 2024), which the Rulebook note says each rule
"corresponds to"; both are cited.

GBP amounts are carried in GBP millions. Anything the supplied text does not
settle carries ``# TODO: VERIFY`` and a conservative placeholder.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

SEC: Final[str] = "PRA Rulebook Securitisation (CRR) Part"
CVA: Final[str] = "PRA Rulebook Credit Valuation Adjustment Risk Part"
LR: Final[str] = "PRA Rulebook Leverage Ratio (CRR) Part"
LE: Final[str] = "PRA Rulebook Large Exposures (CRR) Part"
CCR: Final[str] = "PRA Rulebook Counterparty Credit Risk (CRR) Part"
CRR_EU: Final[str] = "Regulation (EU) No 575/2013 (consolidated 09.07.2024)"

# =========================================================================
#  Securitisation (CRR) Part
# =========================================================================

SEC_RW_MAX: Final[float] = 12.50
"""Art 254(7): 'a risk weight of 1250% shall be assigned'; Art 259(1) / 261(1) 'RW = 1250%'
when D <= K_POOL / K_A."""

SEC_IRBA_RW_FLOOR: Final[float] = 0.15
"""Art 259(1): '... in all cases subject to a floor of 15%'."""
SEC_SA_RW_FLOOR: Final[float] = 0.15
"""Art 261(1): '... in all cases subject to a floor of 15%'."""
STS_SENIOR_RW_FLOOR: Final[float] = 0.10
"""Art 260 (SEC-IRBA) and Art 262 (SEC-SA): 'risk-weight floor for senior securitisation
positions = 10%'."""
ERBA_NON_SENIOR_RW_FLOOR: Final[float] = 0.15
"""Art 263(6): non-senior tranche risk weights 'subject to a floor of 15%'."""

SEC_K_SCALAR: Final[float] = 12.5
"""Arts 259(1) / 261(1): 'RW = 12.5 * K_SSFA' (and 12.5 * e^(au), 12.5 * (K - A)/(D - A))."""

IRBA_P_FLOOR: Final[float] = 0.3
"""Art 259(1): p = max[0.3, (A + B*(1/N) + C*K_IRB + D*LGD + E*M_T)]."""
IRBA_STS_P_SCALAR: Final[float] = 0.5
"""Art 260: p = max[0.3, 0.5 * (A + B*(1/N) + C*K_IRB + D*LGD + E*M_T)]."""

SEC_SA_P_DEFAULT: Final[float] = 1.0
"""Art 261(1): 'an institution may for each securitisation either apply a value of 1 or
calculate p' by the formula."""
SEC_SA_P_MIN: Final[float] = 0.5
SEC_SA_P_MAX: Final[float] = 1.0
"""Art 261(1): p = min[1, max[0.5, (A + B*(1/N) + C*K_A + D*LGD + E*M_T)]]."""
SEC_SA_STS_P_DEFAULT: Final[float] = 0.5
"""Art 262: 'for the value of p, an institution may for each STS securitisation either apply a
value of 0.5 or calculate p' by the formula."""
SEC_SA_STS_P_MIN: Final[float] = 0.3
SEC_SA_STS_P_MAX: Final[float] = 0.5
SEC_SA_STS_P_SCALAR: Final[float] = 0.5
"""Art 262: p = min[0.5, max[0.3, 0.5 * (A + B*(1/N) + C*K_A + D*LGD + E*M_T)]]."""

GRANULARITY_THRESHOLD_N: Final[float] = 25.0
"""Art 259(1) / 261(1) look-up tables: granular 'N >= 25', non-granular 'N < 25'."""

P_PARAMETER_TABLE: Final[Mapping[str, tuple[float, float, float, float, float]]] = (
    MappingProxyType(
        {
            "NON_RETAIL_SENIOR_GRANULAR": (0.0, 3.56, -1.85, 0.55, 0.07),
            "NON_RETAIL_SENIOR_NON_GRANULAR": (0.11, 2.61, -2.91, 0.68, 0.07),
            "NON_RETAIL_NON_SENIOR_GRANULAR": (0.16, 2.87, -1.03, 0.21, 0.07),
            "NON_RETAIL_NON_SENIOR_NON_GRANULAR": (0.22, 2.35, -2.46, 0.48, 0.07),
            "RETAIL_SENIOR": (0.0, 0.0, -7.48, 0.71, 0.24),
            "RETAIL_NON_SENIOR": (0.0, 0.0, -5.78, 0.55, 0.27),
        }
    )
)
"""Art 259(1) look-up table (SEC-IRBA), repeated verbatim in Art 261(1) (SEC-SA): parameters
(A, B, C, D, E)."""

SEC_SA_LGD_TABLE: Final[Mapping[str, float]] = MappingProxyType(
    {
        "REGULATORY_RRE_LTV_LE_100": 0.20,
        "OTHER_IMMOVABLE_PROPERTY_LTV_LE_100": 0.30,
        "SENIOR_PURCHASED_CORPORATE_RECEIVABLES": 0.50,
        "OTHER_SENIOR_NON_FINANCIAL_CORPORATE": 0.40,
        "OTHER_SENIOR_NON_RETAIL": 0.45,
        "SUBORDINATED_PURCHASED_CORPORATE_RECEIVABLES": 1.00,
        "OTHER_SUBORDINATED_NON_RETAIL": 0.75,
        "OTHER": 1.00,
    }
)
"""Art 261(1)(a) table: exposure-type LGDs for the SEC-SA p formula."""

SIMPLIFIED_N_MAX_C1: Final[float] = 0.03
"""Arts 259(6) / 261(1)(d): simplified N / LGD where C_1 'is no more than 3%'."""
SIMPLIFIED_LGD: Final[float] = 0.50
"""Arts 259(6) / 261(1)(d): 'exposure-weighted average LGD = 0.50'."""

MIXED_POOL_MIN_KIRB_SHARE: Final[float] = 0.95
"""Art 258(1)(a) / 259(7): K_IRB on 'a minimum of 95% of the underlying exposure amount'."""

K_A_DEFAULTED_WEIGHT: Final[float] = 0.5
"""Art 261(2): K_A = (1 - W) * K_SA + W * 0.5 (or K_SAE in place of K_SA)."""
UNKNOWN_DELINQUENCY_MAX_SHARE: Final[float] = 0.05
"""Art 261(2): delinquency status unknown for 5% or less -> adjusted K_A; for more than 5% the
position 'must be risk-weighted at 1250%'."""

TRANCHE_MATURITY_FLOOR_YEARS: Final[float] = 1.0
TRANCHE_MATURITY_CAP_YEARS: Final[float] = 5.0
"""Art 257(2): 'a floor of one year and a cap of five years'."""
TRANCHE_MATURITY_LEGAL_SCALAR: Final[float] = 0.80
"""Art 257(1)(b): M_T = 1 + (M_L - 1) * 80%."""

SEC_SA_OVERRIDE_RW_STS: Final[float] = 0.25
"""Art 254(2)(a): SEC-ERBA instead of SEC-SA where SEC-SA 'would result in a risk weight higher
than 25%' for STS positions."""
SEC_SA_OVERRIDE_RW_NON_STS: Final[float] = 0.25
SEC_ERBA_OVERRIDE_RW_NON_STS: Final[float] = 0.75
"""Art 254(2)(b): for non-STS positions where SEC-SA 'would result in a risk weight higher than
25% or the application of the SEC-ERBA would result in a risk weight higher than 75%'."""

RESEC_P: Final[float] = 1.5
"""Art 269(1)(b): p = 1.5."""
RESEC_RW_FLOOR: Final[float] = 1.00
"""Art 269(1)(c): 'subject to a risk-weight floor of 100%'."""
RESEC_W: Final[float] = 0.0
"""Art 269(1)(a): W = 0 for any exposure to a securitisation tranche within the pool."""

ERBA_THICKNESS_CAP: Final[float] = 0.50
"""Art 263(5): RW x [1 - min(T, 50%)], T = D - A."""
ERBA_MATURITY_POINTS: Final[tuple[float, float]] = (1.0, 5.0)
"""Art 263(3)-(4) Table 2 columns '1 year' / '5 years'; linear interpolation in between."""

ERBA_CQS_ALL_OTHER: Final[int] = 18
"""Key used here for the 'All other' row of Tables 2 and 4 (Art 263(3), 264(3))."""
ERBA_ST_ALL_OTHER: Final[int] = 4
"""Key used here for the 'All other ratings' column of Tables 1 and 3 (Art 263(2), 264(2))."""


def _erba_rows(
    rows: tuple[tuple[float, float, float, float], ...],
) -> Mapping[int, tuple[float, float, float, float]]:
    """Freeze an ERBA table keyed by CQS 1-17 plus 18 = 'All other' (helper; no content)."""
    table = {i + 1: r for i, r in enumerate(rows)}
    table[ERBA_CQS_ALL_OTHER] = (12.5, 12.5, 12.5, 12.5)
    return MappingProxyType(table)


ERBA_TABLE_2: Final[Mapping[int, tuple[float, float, float, float]]] = _erba_rows(
    (
        (0.15, 0.20, 0.15, 0.70),
        (0.15, 0.30, 0.15, 0.90),
        (0.25, 0.40, 0.30, 1.20),
        (0.30, 0.45, 0.40, 1.40),
        (0.40, 0.50, 0.60, 1.60),
        (0.50, 0.65, 0.80, 1.80),
        (0.60, 0.70, 1.20, 2.10),
        (0.75, 0.90, 1.70, 2.60),
        (0.90, 1.05, 2.20, 3.10),
        (1.20, 1.40, 3.30, 4.20),
        (1.40, 1.60, 4.70, 5.80),
        (1.60, 1.80, 6.20, 7.60),
        (2.00, 2.25, 7.50, 8.60),
        (2.50, 2.80, 9.00, 9.50),
        (3.10, 3.40, 10.50, 10.50),
        (3.80, 4.20, 11.30, 11.30),
        (4.60, 5.05, 12.50, 12.50),
    )
)
"""Art 263(3) Table 2: CQS -> (senior 1y, senior 5y, non-senior 1y, non-senior 5y)."""

ERBA_TABLE_4_STS: Final[Mapping[int, tuple[float, float, float, float]]] = _erba_rows(
    (
        (0.10, 0.10, 0.15, 0.40),
        (0.10, 0.15, 0.15, 0.55),
        (0.15, 0.20, 0.15, 0.70),
        (0.15, 0.25, 0.25, 0.80),
        (0.20, 0.30, 0.35, 0.95),
        (0.30, 0.40, 0.60, 1.35),
        (0.35, 0.45, 0.95, 1.70),
        (0.45, 0.55, 1.50, 2.25),
        (0.55, 0.65, 1.80, 2.55),
        (0.70, 0.85, 2.70, 3.45),
        (1.20, 1.35, 4.05, 5.00),
        (1.35, 1.55, 5.35, 6.55),
        (1.70, 1.95, 6.45, 7.40),
        (2.25, 2.50, 8.10, 8.55),
        (2.80, 3.05, 9.45, 9.45),
        (3.40, 3.80, 10.15, 10.15),
        (4.15, 4.55, 12.50, 12.50),
    )
)
"""Art 264(3) Table 4 (STS): CQS -> (senior 1y, senior 5y, non-senior 1y, non-senior 5y)."""

ERBA_TABLE_1_SHORT_TERM: Final[Mapping[int, float]] = MappingProxyType(
    {1: 0.15, 2: 0.50, 3: 1.00, ERBA_ST_ALL_OTHER: 12.50}
)
"""Art 263(2) Table 1: short-term CQS 1 / 2 / 3 / all other ratings."""
ERBA_TABLE_3_SHORT_TERM_STS: Final[Mapping[int, float]] = MappingProxyType(
    {1: 0.10, 2: 0.30, 3: 0.60, ERBA_ST_ALL_OTHER: 12.50}
)
"""Art 264(2) Table 3 (STS): short-term CQS 1 / 2 / 3 / all other ratings."""

_LT_SCALE_SP: tuple[str, ...] = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-",
)
_LT_SCALE_MOODYS: tuple[str, ...] = (
    "AAA", "AA1", "AA2", "AA3", "A1", "A2", "A3", "BAA1", "BAA2", "BAA3",
    "BA1", "BA2", "BA3", "B1", "B2", "B3",
)
SEC_LONG_TERM_CQS: Final[Mapping[str, int]] = MappingProxyType(
    {
        **{r: i + 1 for i, r in enumerate(_LT_SCALE_SP)},
        **{r: i + 1 for i, r in enumerate(_LT_SCALE_MOODYS)},
        "CCC+": 17, "CCC": 17, "CCC-": 17,
        "CAA1": 17, "CAA2": 17, "CAA3": 17,
    }
)
"""Art 270F(1) mapping table, S&P Global Ratings UK / Fitch Ratings / Moody's Investors Service
rows: AAA (sf) -> CQS 1 ... B- (sf) -> CQS 16; CCC+/CCC/CCC- (sf) -> CQS 17 (Fitch 'CCC SF' and
Moody's 'Caa1-Caa3 (sf)' -> 17); anything below -> 'All other'. Keys are upper-cased with the
'(sf)'/'SF' suffix removed."""

SEC_SHORT_TERM_CQS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "A-1+": 1, "A-1": 1, "A-2": 2, "A-3": 3,
        "P-1": 1, "P-2": 2, "P-3": 3,
        "F1+": 1, "F-1+": 1, "F1": 1, "F2": 2, "F3": 3,
    }
)
"""Art 270F(1) short-term rows: S&P A-1+/A-1 -> 1, A-2 -> 2, A-3 -> 3; Moody's P-1/P-2/P-3;
Fitch F-1+/F1, F2, F3; below -> 'All other ratings'. The repo's 'A-1/P-1' style input is split
on '/'."""

QUALIFYING_SEC_SA_RW_LOW: Final[float] = 0.20
QUALIFYING_SEC_SA_RW_HIGH: Final[float] = 0.75
QUALIFYING_SEC_SA_PROPERTY_SHARE: Final[float] = 0.55
"""Art 262A(2): 20% when A >= X; 75% when D <= X; blended otherwise;
X = 1 - (0.55 * property value / exposure value)."""

NPE_RW_FLOOR: Final[float] = 1.00
"""# TODO: VERIFY -- Art 269A(1) subjects NPE securitisations to the Non-Performing Exposures
Securitisation (CRR) Part, which was not supplied. Placeholder = BCBS CRE45.4 ('floored at
100%')."""
NPE_SENIOR_RW: Final[float] = 1.00
NPE_SENIOR_MIN_NRPPD: Final[float] = 0.50
"""# TODO: VERIFY -- placeholder = BCBS CRE45.5: senior tranche of a traditional NPL
securitisation 100% where NRPPD >= 50% of the outstanding pool balance (UK NPE Part not
supplied)."""

SME_SENIOR_MIN_SME_SHARE: Final[float] = 0.70
"""Art 270(c): at least 70% of the pool (portfolio balance) qualifies as SMEs."""
SRT_CLEAN_UP_CALL_MAX: Final[float] = 0.10
"""Art 244(4)(g)(ii) / 245(4)(f)(ii): clean-up call only when '10% or less of the original value'
remains unamortised."""
SRT_MEZZANINE_MAX_SHARE: Final[float] = 0.50
SRT_FIRST_LOSS_MAX_SHARE: Final[float] = 0.20
"""Art 244(2)(a)-(b) / 245(2)(a)-(b): mezzanine RWEA held <= 50%; first-loss held <= 20%."""
STS_SINGLE_OBLIGOR_MAX: Final[float] = 0.02
"""Art 243(1)(b) / 243(2)(a): single-obligor concentration <= 2%."""
LIQUIDITY_FACILITY_CANCELLABLE_CCF: Final[float] = 0.10
SEC_OBS_CCF: Final[float] = 1.00
"""Art 248(1)(b): conversion factor 100%, except 10% for the undrawn portion of an
unconditionally cancellable cash advance facility (liquidity facility) meeting the seniority
condition."""

# =========================================================================
#  Credit Valuation Adjustment Risk Part, Chapter 5 -- SA-CVA (p. 408-422)
# =========================================================================

SA_CVA_M: Final[float] = 1.0
"""Rule 5.24(2): 'mCVA = multiplier factor equal to 1' (p. 410)."""
SA_CVA_R: Final[float] = 0.01
"""Rule 5.24(1): 'R = the hedging disallowance parameter set at 0.01' (p. 410)."""

# ---- interest rate (rule 5.25, p. 411-412) ------------------------------
IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"USD", "EUR", "GBP", "AUD", "CAD", "SEK", "JPY"}
)
"""Rule 5.25(3)(a): currencies with five tenors plus inflation."""
IR_TENORS: Final[tuple[str, ...]] = ("1Y", "2Y", "5Y", "10Y", "30Y", "INFLATION")
IR_DELTA_RW: Final[Mapping[str, float]] = MappingProxyType(
    {"1Y": 0.0111, "2Y": 0.0093, "5Y": 0.0074, "10Y": 0.0074, "30Y": 0.0074, "INFLATION": 0.0111}
)
"""Rule 5.25(5) table: 1.11% / 0.93% / 0.74% / 0.74% / 0.74% / inflation 1.11%."""
_IR_CORR_UPPER: dict[tuple[str, str], float] = {
    ("1Y", "2Y"): 0.91, ("1Y", "5Y"): 0.72, ("1Y", "10Y"): 0.55, ("1Y", "30Y"): 0.31,
    ("2Y", "5Y"): 0.87, ("2Y", "10Y"): 0.72, ("2Y", "30Y"): 0.45,
    ("5Y", "10Y"): 0.91, ("5Y", "30Y"): 0.68,
    ("10Y", "30Y"): 0.83,
    ("1Y", "INFLATION"): 0.40, ("2Y", "INFLATION"): 0.40, ("5Y", "INFLATION"): 0.40,
    ("10Y", "INFLATION"): 0.40, ("30Y", "INFLATION"): 0.40,
}
IR_DELTA_CORRELATION: Final[Mapping[tuple[str, str], float]] = MappingProxyType(
    {**_IR_CORR_UPPER, **{(b, a): v for (a, b), v in _IR_CORR_UPPER.items()}}
)
"""Rule 5.25(6) correlation table (p. 412), symmetric."""
IR_OTHER_CCY_RW: Final[float] = 0.0158
"""Rule 5.25(8): other currencies, curve and inflation risk weights 1.58%."""
IR_OTHER_CCY_CORRELATION: Final[float] = 0.40
"""Rule 5.25(9): curve vs inflation correlation 40% (other currencies)."""
IR_VEGA_RW: Final[float] = 1.00
"""Rule 5.25(12): IR and inflation volatility risk weights 100%."""
IR_VEGA_CORRELATION: Final[float] = 0.40
"""Rule 5.25(13): IR volatility vs inflation volatility 40%."""
IR_CROSS_BUCKET: Final[float] = 0.5
"""Rule 5.25(2): gamma_bc = 0.5 for all currency pairs."""

# ---- foreign exchange (rule 5.26, p. 413) -------------------------------
FX_DELTA_RW: Final[float] = 0.11
"""Rule 5.26(5): 11%."""
FX_VEGA_RW: Final[float] = 1.00
"""Rule 5.26(8): 100%."""
FX_CROSS_BUCKET: Final[float] = 0.6
"""Rule 5.26(2): gamma_bc = 0.6."""

# ---- counterparty credit spread (rule 5.27, p. 413-416) -----------------
CCS_TENORS: Final[tuple[str, ...]] = ("0.5Y", "1Y", "3Y", "5Y", "10Y")
"""Rule 5.27(3): 0.5, 1, 3, 5 and 10 years."""
CCS_RW: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "1A": (0.005, 0.020),
        "1B": (0.010, 0.040),
        "2A": (0.050, 0.120),
        "2B": (0.035, 0.085),
        "3": (0.030, 0.070),
        "4": (0.030, 0.085),
        "5": (0.020, 0.055),
        "6": (0.015, 0.050),
        "7": (0.050, 0.120),
        "8": (0.015, 0.050),
    }
)
"""Rule 5.27(5) table: bucket -> (investment grade, high yield and not rated). Buckets 1(a)
sovereigns/central banks/MDBs, 1(b) local government etc., 2(a) financials excl. pension funds,
2(b) pension funds, 3-7 sectors, 8 qualified indices (rule 5.27(1))."""
_CCS_GAMMA_UPPER: dict[tuple[int, int], float] = {
    (1, 2): 0.10, (1, 3): 0.20, (1, 4): 0.25, (1, 5): 0.20, (1, 6): 0.15, (1, 7): 0.0, (1, 8): 0.45,
    (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.05, (2, 7): 0.0, (2, 8): 0.45,
    (3, 4): 0.20, (3, 5): 0.25, (3, 6): 0.05, (3, 7): 0.0, (3, 8): 0.45,
    (4, 5): 0.25, (4, 6): 0.05, (4, 7): 0.0, (4, 8): 0.45,
    (5, 6): 0.05, (5, 7): 0.0, (5, 8): 0.45,
    (6, 7): 0.0, (6, 8): 0.45,
    (7, 8): 0.0,
}
CCS_CROSS_BUCKET: Final[Mapping[tuple[int, int], float]] = MappingProxyType(
    {**_CCS_GAMMA_UPPER, **{(b, a): v for (a, b), v in _CCS_GAMMA_UPPER.items()}}
)
"""Rule 5.27(2) table (p. 414), symmetric; keyed by bucket number 1-8."""
CCS_RHO_TENOR_DIFFERENT: Final[float] = 0.90
CCS_RHO_NAME_LEGALLY_RELATED: Final[float] = 0.90
CCS_RHO_NAME_DIFFERENT: Final[float] = 0.50
CCS_RHO_QUALITY_DIFFERENT: Final[float] = 0.80
"""Rule 5.27(6): rho_tenor 90% if tenors differ; rho_name 90% legally related, 50% otherwise;
rho_quality 80% if credit quality differs."""
CCS_INDEX_RHO_NAME_DIFFERENT_SERIES: Final[float] = 0.90
CCS_INDEX_RHO_NAME_DIFFERENT: Final[float] = 0.80
"""Rule 5.27(7) (bucket 8): rho_name 90% same index distinct series, 80% otherwise."""

# ---- reference credit spread (rule 5.28, p. 416-418) --------------------
RCS_RW: Final[Mapping[int, float]] = MappingProxyType(
    {
        1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015,
        8: 0.020, 9: 0.040, 10: 0.120, 11: 0.070, 12: 0.085, 13: 0.055, 14: 0.050,
        15: 0.120, 16: 0.015, 17: 0.050,
    }
)
"""Rule 5.28(5) tables (p. 417-418), by bucket number. The printed tables head buckets 1-9
'Investment grade bucket' and 10-17 'High yield/Not rated' while the bucket table of rule
5.28(1) defines 1-7 as investment grade and 8-14 as high yield and not rated; the risk weights
are transcribed by bucket number, which is unambiguous."""
RCS_IG_BUCKETS: Final[frozenset[int]] = frozenset(range(1, 8))
RCS_HY_BUCKETS: Final[frozenset[int]] = frozenset(range(8, 15))
"""Rule 5.28(1): buckets 1-7 investment grade, 8-14 high yield and not rated, 15 other sector,
16 IG qualified index, 17 HY qualified index."""
_RCS_GAMMA_UPPER: dict[tuple[str, str], float] = {
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
RCS_CROSS_BUCKET_SAME_QUALITY: Final[Mapping[tuple[str, str], float]] = MappingProxyType(
    {**_RCS_GAMMA_UPPER, **{(b, a): v for (a, b), v in _RCS_GAMMA_UPPER.items()}}
)
"""Rule 5.28(2)(a) table (p. 417), symmetric. Keys are the column labels with '1' = '1/8',
..., '7' = '7/14' (same sector, either credit quality), '15', '16', '17'. Diagonal 1/8-1/8
etc. = 100% (same sector, same quality = same bucket)."""
RCS_DIFFERENT_QUALITY_DIVISOR: Final[float] = 2.0
"""Rule 5.28(2)(b): between buckets 1 to 14 of different credit quality, divide by 2."""
RCS_VEGA_RW: Final[float] = 1.00
"""Rule 5.28(8): 100%."""

# ---- equity (rule 5.29, p. 418-420) -------------------------------------
EQ_DELTA_RW: Final[Mapping[int, float]] = MappingProxyType(
    {1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50, 9: 0.70,
     10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25}
)
"""Rule 5.29(6) table."""
EQ_LARGE_CAP_BUCKETS: Final[frozenset[int]] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 12})
"""Rule 5.29(1): buckets 1-8 'Large market capitalisation'; bucket 12 'Large capitalisation,
advanced economies Qualified index'."""
EQ_VEGA_RW_LARGE: Final[float] = 0.78
EQ_VEGA_RW_OTHER: Final[float] = 1.00
"""Rule 5.29(9): 78% for large market capitalisation buckets and 100% for the other buckets.
Treating index bucket 12 as a 'large market capitalisation bucket' follows its label in the
5.29(1) table."""
EQ_LARGE_CAP_THRESHOLD_GBP_M: Final[float] = 1_600.0
"""Rule 5.29(1): large market capitalisation >= GBP 1.6 billion."""
EQ_ADVANCED_ECONOMIES: Final[tuple[str, ...]] = (
    "UK", "Canada", "United States", "Mexico", "euro area", "Norway", "Sweden", "Denmark",
    "Switzerland", "Japan", "Australia", "New Zealand", "Singapore", "Hong Kong SAR",
)
"""Rule 5.29(1) 'advanced economies'."""
EQ_GAMMA_WITHIN_1_10: Final[float] = 0.15
EQ_GAMMA_12_13: Final[float] = 0.75
EQ_GAMMA_INDEX_VS_1_10: Final[float] = 0.45
EQ_GAMMA_BUCKET_11: Final[float] = 0.0
"""Rule 5.29(4)(a)-(d)."""

# ---- commodity (rule 5.30, p. 420-422) ----------------------------------
COM_DELTA_RW: Final[Mapping[int, float]] = MappingProxyType(
    {1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45, 7: 0.20, 8: 0.35, 9: 0.25,
     10: 0.35, 11: 0.50}
)
"""Rule 5.30(6) table."""
COM_VEGA_RW: Final[float] = 1.00
"""Rule 5.30(8)."""
COM_GAMMA_WITHIN_1_10: Final[float] = 0.20
COM_GAMMA_BUCKET_11: Final[float] = 0.0
"""Rule 5.30(2)(a)-(b)."""

# =========================================================================
#  Leverage Ratio (CRR) Part
# =========================================================================

LEV_SACCR_MULTIPLIER: Final[float] = 1.0
"""Art 429c(5): the PFE multiplier of CCR Part Art 278(1) is set to one (except client
derivatives cleared through a QCCP)."""
LEV_SACCR_ALPHA: Final[float] = 1.4
LEV_SACCR_ALPHA_NFC_PENSION: Final[float] = 1.0
"""Art 429c(1): exposure value per the standardised approach for CCR, i.e. CCR Part Art 274(2)
alpha = 1.4, or 1 for a non-financial counterparty / pension scheme arrangement; Art 274(2B):
the 274(2A) alpha add-on transitional does not apply to the leverage ratio."""
LEV_LOW_RISK_OBS_CCF: Final[float] = 0.10
"""Art 429f(3): 'a conversion factor of 10% to low-risk off-balance-sheet items referred to in
point (d) of Article 111(1)'."""
LEV_SFT_RW_FLOOR_SIMPLE_METHOD: Final[float] = 0.20
"""Art 429e(5): Article 222 method 'subject to a 20% floor for the applicable risk weight'."""
LEV_SDDT_ALPHA: Final[float] = 1.4
"""Art 429c(6)(b): SDDTs, exposure value = alpha * max{CMV, 0}, alpha = 1.4."""

LEVERAGE_RATIO_MINIMUM_PLACEHOLDER: Final[float] = 0.0325
"""# TODO: VERIFY -- the minimum leverage ratio is set in the Leverage Ratio - Capital
Requirements and Buffers Part, which was not supplied (the Leverage Ratio (CRR) Part only
defines the measure, Art 429(2)-(4)). Not used by the exposure-measure calculation."""

# =========================================================================
#  Large Exposures (CRR) Part
# =========================================================================

LE_REPORTING_THRESHOLD: Final[float] = 0.10
"""Rule 1.2 'large exposure': value 'equal to or exceeds 10% of its Tier 1 capital'."""
LE_REPORTING_ABS_GBP_M: Final[float] = 260.0
"""Art 394(1) third subparagraph: report exposures >= GBP 260 million but < 10% of Tier 1
(consolidated basis)."""
LE_LIMIT: Final[float] = 0.25
"""Art 395(1): 25% of Tier 1 capital."""
LE_INSTITUTION_FLOOR_GBP_M: Final[float] = 130.0
"""Art 395(1): relevant exposures to Article 119 institutions -- 25% of Tier 1 or GBP 130
million, whichever is higher."""
LE_INSTITUTION_ABS_CAP: Final[float] = 1.00
"""Art 395(1) second subparagraph: where GBP 130 million > 25% of Tier 1, a firm-set reasonable
limit that 'must not exceed 100% of the firm's Tier 1 capital'."""
LE_GSII_LIMIT: Final[float] = 0.15
"""Art 395(1) third subparagraph: G-SII to another G-SII or non-UK G-SII, 15% of Tier 1."""
LE_GSII_COMPLIANCE_MONTHS: Final[int] = 12
"""Art 395(1): comply 'no later than 12 months' after identification."""
LE_TB_EXCESS_10D_MAX: Final[float] = 5.00
LE_TB_EXCESS_PERSISTENT_MAX: Final[float] = 6.00
"""Art 395(5)(c)-(d): trading-book excess <= 500% of Tier 1 within 10 days; persistent
excesses in aggregate <= 600%."""
LE_TB_EXCESS_DAYS: Final[int] = 10
LE_TB_EXCESS_FACTOR_FIRST_10D: Final[float] = 2.00
"""Art 397(2): 200% of the specific-risk requirements where the excess has not persisted
more than 10 days."""
LE_TB_EXCESS_TABLE_1: Final[tuple[tuple[float, float], ...]] = (
    (0.40, 2.00),
    (0.60, 3.00),
    (0.80, 4.00),
    (1.00, 5.00),
    (2.50, 6.00),
    (float("inf"), 9.00),
)
"""Art 397(3) Table 1: excess over the limits (% of Tier 1) -> factor: up to 40% 200%;
40-60% 300%; 60-80% 400%; 80-100% 500%; 100-250% 600%; over 250% 900%."""
LE_UNKNOWN_CLIENT_THRESHOLD: Final[float] = 0.0025
"""LE Part Chapter 5 Art 6(2)-(3): 0.25% of Tier 1 for transactions with underlying assets."""
LE_FX_SETTLEMENT_DAYS: Final[int] = 2
LE_SECURITIES_SETTLEMENT_DAYS: Final[int] = 5
"""Art 390(6)(a)-(b): settlement exclusions (two / five business days)."""

LE_EXEMPTION_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "art400_1_a": "Art 400(1)(a) 0% RW central governments, central banks, PSEs",
        "art400_1_b": "Art 400(1)(b) 0% RW international organisations / MDBs",
        "art400_1_c": "Art 400(1)(c) explicit guarantee of a 0% RW sovereign/IO/MDB/PSE",
        "art400_1_d": "Art 400(1)(d) other exposures attributable to/guaranteed by 0% RW entities",
        "art400_1_e": "Art 400(1)(e) 0% RW UK regional governments / local authorities",
        "art400_1_f": "Art 400(1)(f) Art 113(6)/(7) counterparties at 0% RW",
        "art400_1_g": "Art 400(1)(g) secured by cash deposits with the lender or group institution",
        "art400_1_h": "Art 400(1)(h) secured by CDs issued by the lender or group institution",
        "art400_1_i": "Art 400(1)(i) low-risk undrawn facilities drawable only within the limit",
        "art400_1_j": "Art 400(1)(j) clearing members' trade exposures and DF to QCCPs",
        "art400_1_l": "Art 400(1)(l) clients' trade exposures under CCR Part Art 305(2)/(3)",
        "art400_2_c": "Art 400(2)(c) intragroup exposures (PRA permission)",
        "art400_2_g": "Art 400(2)(g) required minimum reserves at central banks (permission)",
        "art400_2_h": "Art 400(2)(h) statutory liquidity holdings of IG sovereign securities "
        "(permission)",
    }
)
"""Art 400(1) and (2) exemptions, keyed for ``LargeExposureInput.flags``; Art 400(4): no more
than one exemption to the same exposure."""

# =========================================================================
#  Counterparty Credit Risk (CRR) Part, Section 9 -- CCPs
# =========================================================================

QCCP_TRADE_RW: Final[float] = 0.02
"""Art 306(1)(a): 2% for trade exposures with QCCPs."""
QCCP_CLIENT_NOT_PROTECTED_JOINT_DEFAULT_RW: Final[float] = 0.04
"""Art 305(3): 4% in place of 2% where the client is not protected against the joint default
of the clearing member and another client."""
QCCP_DF_FLOOR_RW: Final[float] = 0.02
QCCP_DF_FLOOR_CAPITAL_RATIO: Final[float] = 0.08
"""Art 308(2): K_i = max{K_CCP * DF_i / (DF_CCP + DF_CM); 8% * 2% * DF_i} (the formula is an
image on the Rulebook page; transcribed from CRR Art 308(2), which the rule corresponds to)."""
DF_RWA_MULTIPLIER: Final[float] = 12.5
"""Art 308(3) / 309(2): risk-weighted exposure amount = own funds requirement x 12.5."""
QCCP_UNFUNDED_DF_RW: Final[float] = 0.0
"""Art 310: 0% risk weight on unfunded contributions to a QCCP default fund."""
CASH_TRANSACTION_DF_RW: Final[float] = 0.0
"""Art 301(1): 0% for default fund contributions covering only cash transactions."""
CM_CLIENT_MPOR_MIN_DAYS: Final[int] = 5
CM_CCP_MPOR_MIN_DAYS: Final[int] = 10
"""Art 304(3)(a)-(b): MPOR at least five business days to a client, 10 to a CCP."""
CM_CLIENT_MATURITY_FACTOR: Final[float] = 0.21
"""Art 304(4)-(5): maturity factor 0.21 for client exposures under Sections 4 / 5."""
CCP_CEASING_TRANSITION_MONTHS: Final[int] = 3
"""Art 311(2): treatment applies within three months of becoming aware."""
