"""Basel Framework market-risk (FRTB) parameters -- the international baseline.

Every constant is transcribed from the consolidated Basel Framework (BIS,
generated 29/10/2026) and carries its paragraph reference. Page numbers are
the "n / 1429" footers. Equations printed as images were read from the
rendered PDF page (the page is cited); where neither the text nor the
rendered page settles a value the constant carries a ``TODO: VERIFY`` marker.

Chapters:
    - MAR20 (pp. 563-566): structure of the standardised approach, CTP definition
    - MAR21 (pp. 566-618): sensitivities-based method (Tables 1-13)
    - MAR22 (pp. 618-633): default risk capital (Tables 1-2)
    - MAR23 (pp. 633-637): residual risk add-on
    - MAR32 (pp. 655-668): backtesting (Table 1) and PLA (Table 2)
    - MAR33 (pp. 668-686): ES, liquidity horizons (Tables 1-2), IMCC, SES, aggregation
    - MAR40 (pp. 686-720): simplified standardised approach (Tables 1, 4, 5, 10, 11)

The verbatim transcription is ``docs/jurisdictions/BCBS_frtb_reference.md``.

Table numbering note: the Framework numbers the MAR21 tables 1-13 in its own
sequence (e.g. equity buckets are Table 9, equity risk weights Table 10,
commodity Table 11, commodity intra-bucket correlations Table 12, vega
liquidity horizons Table 13). Citations below use the Framework's numbering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.frtb_base import (
    CommodityGroup,
    CreditSector,
    DRCSeniority,
    EquitySector,
    SecAssetClass,
    SecTrancheClass,
)

R = RatingBucket

# =========================================================================
#  Discretions (bank / national) -- BCBS defaults
# =========================================================================


@dataclass(frozen=True)
class BCBSFRTBOptions:
    """Bank and national discretions in MAR21-MAR23, with engine defaults.

    Each field cites the paragraph granting the discretion.
    """

    reporting_currency: str = "USD"
    """MAR21.15: sensitivities are expressed in the reporting currency; it is also a
    "specified currency" for MAR21.44 (footnote 283) and the FX bucket anchor (MAR21.86)."""

    girr_specified_currency_sqrt2: bool = True
    """MAR21.44: specified-currency GIRR risk weights "may, at the discretion of the bank,
    be divided by the square root of 2". Engine default: exercised."""

    fx_liquid_pair_sqrt2: bool = True
    """MAR21.88: FX risk weight for specified pairs and first-order crosses "may at the
    discretion of the bank be divided by the square root of 2". Engine default: exercised."""

    covered_bond_aa_reduction: bool = True
    """MAR21.53 footnote 288: covered bonds rated AA- or higher "may at the discretion of
    the bank be 1.5%". Engine default: exercised."""

    xccy_onshore_offshore_simple_sum: bool = False
    """MAR21.45: a bank "may choose" to aggregate onshore/offshore cross-currency basis
    of a currency by simple sum. Engine default: not exercised (0% correlation, MAR21.49)."""

    drc_sovereign_zero_rw: bool = False
    """MAR22.7: claims on sovereigns, PSEs and MDBs may, at national discretion, be subject
    to a zero default risk weight. Engine default: not exercised."""


DEFAULT_FRTB_OPTIONS: Final[BCBSFRTBOptions] = BCBSFRTBOptions()

# =========================================================================
#  MAR20 / MAR21 -- structure and correlation scenarios
# =========================================================================

RWA_MULTIPLIER: Final[float] = 12.5
"""MAR20.1 (p. 564): RWA = 12.5 x capital requirement (also MAR33.46, MAR40.1)."""

HIGH_CORRELATION_MULTIPLIER: Final[float] = 1.25
"""MAR21.6(2) (p. 574): rho and gamma "uniformly multiplied by 1.25 ... subject to a cap at
100%"."""

CORRELATION_CAP: Final[float] = 1.0
"""MAR21.6(2): cap at 100%."""

LOW_CORRELATION_SLOPE: Final[float] = 2.0
LOW_CORRELATION_INTERCEPT: Final[float] = 1.0
LOW_CORRELATION_FLOOR_FACTOR: Final[float] = 0.75
"""MAR21.6(3) (p. 574, formula rendered from PDF): rho_low = max(2 x rho - 100%; 75% x rho),
gamma_low = max(2 x gamma - 100%; 75% x gamma)."""

SCENARIOS: Final[tuple[str, str, str]] = ("LOW", "MEDIUM", "HIGH")
"""MAR21.6: low / medium / high correlations; MAR21.7(2): SBM = largest of the three."""

# =========================================================================
#  MAR21.8 / 21.41-21.50 -- GIRR
# =========================================================================

GIRR_TENORS: Final[tuple[float, ...]] = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)
"""MAR21.8(1) (p. 574): ten delta GIRR tenors."""

GIRR_DELTA_RW: Final[dict[float, float]] = {
    0.25: 0.017, 0.5: 0.017, 1.0: 0.016, 2.0: 0.013, 3.0: 0.012,
    5.0: 0.011, 10.0: 0.011, 15.0: 0.011, 20.0: 0.011, 30.0: 0.011,
}
"""MAR21.42 Table 1 (p. 592): delta GIRR risk weights by tenor."""

GIRR_INFLATION_RW: Final[float] = 0.016
GIRR_XCCY_BASIS_RW: Final[float] = 0.016
"""MAR21.43 (p. 592): inflation and cross-currency basis risk weights 1.6%."""

GIRR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"EUR", "USD", "GBP", "AUD", "JPY", "SEK", "CAD"}
)
"""MAR21.44 footnote 283 (p. 593): EUR, USD, GBP, AUD, JPY, SEK, CAD "as well as the
domestic reporting currency of a bank"."""

SQRT2: Final[float] = math.sqrt(2.0)
"""MAR21.44 / MAR21.88: divisor "square root of 2"."""

GIRR_SQRT2_APPLIES_TO_INFLATION_XCCY: Final[bool] = False
# TODO: VERIFY -- MAR21.44 says "the above risk weights" after both MAR21.42 (Table 1) and
# MAR21.43 (inflation / xccy 1.6%); it is not settled whether the sqrt(2) reduction extends to
# the inflation and cross-currency basis weights. Conservative placeholder: Table 1 only.

GIRR_SAME_TENOR_DIFF_CURVE_RHO: Final[float] = 0.999
"""MAR21.45 (p. 593): same bucket, same tenor, different curves: 99.90%."""

GIRR_TENOR_CORRELATION: Final[tuple[tuple[float, ...], ...]] = (
    (1.000, 0.970, 0.914, 0.811, 0.719, 0.566, 0.400, 0.400, 0.400, 0.400),
    (0.970, 1.000, 0.970, 0.914, 0.861, 0.763, 0.566, 0.419, 0.400, 0.400),
    (0.914, 0.970, 1.000, 0.970, 0.942, 0.887, 0.763, 0.657, 0.566, 0.419),
    (0.811, 0.914, 0.970, 1.000, 0.985, 0.956, 0.887, 0.823, 0.763, 0.657),
    (0.719, 0.861, 0.942, 0.985, 1.000, 0.980, 0.932, 0.887, 0.844, 0.763),
    (0.566, 0.763, 0.887, 0.956, 0.980, 1.000, 0.970, 0.942, 0.914, 0.861),
    (0.400, 0.566, 0.763, 0.887, 0.932, 0.970, 1.000, 0.985, 0.970, 0.942),
    (0.400, 0.419, 0.657, 0.823, 0.887, 0.942, 0.985, 1.000, 0.990, 0.970),
    (0.400, 0.400, 0.566, 0.763, 0.844, 0.914, 0.970, 0.990, 1.000, 0.985),
    (0.400, 0.400, 0.419, 0.657, 0.763, 0.861, 0.942, 0.970, 0.985, 1.000),
)
"""MAR21.46 Table 2 (p. 593): delta GIRR correlations, same bucket, different tenor, same
curve; rows / columns in ``GIRR_TENORS`` order. (Footnote 284 gives the generating formula,
an image lost in extraction and in the PDF render; the printed table is used.)"""

GIRR_DIFF_CURVE_FACTOR: Final[float] = 0.999
"""MAR21.47 (p. 594): different tenor and different curves -> Table 2 x 99.90%; the FAQ
applies 99.90% between different inflation curves in the same currency."""

GIRR_INFLATION_VS_YIELD_RHO: Final[float] = 0.40
"""MAR21.48 (p. 594): inflation vs a tenor of the yield curve: 40%."""

GIRR_XCCY_RHO: Final[float] = 0.0
"""MAR21.49 (p. 594): cross-currency basis vs yield curve / inflation / other xccy: 0%."""

GIRR_GAMMA: Final[float] = 0.50
"""MAR21.50 (p. 594): across GIRR buckets (currencies): 50%."""

# =========================================================================
#  MAR21.9 / 21.51-21.57 -- CSR non-securitisation
# =========================================================================

CSR_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""MAR21.9(1), 21.10(2), 21.11(2) (pp. 577-579): CSR tenors (also the vega option maturities,
MAR21.8(4), 21.9(2), 21.12(2), 21.13(2), 21.14(2))."""

VEGA_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""MAR21.8(4) and MAR21.9(2)-21.14(2): vega option-maturity (and GIRR underlying) tenors."""

COMMODITY_TENORS: Final[tuple[float, ...]] = (
    0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0
)
"""MAR21.13(1)(b) (p. 580): commodity delta tenors."""

CSR_NONSEC_BUCKETS: Final[dict[int, str]] = {
    1: "IG: Sovereigns including central banks, multilateral development banks",
    2: "IG: Local government, government-backed non-financials, education, public administration",
    3: "IG: Financials including government-backed financials",
    4: "IG: Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying",
    5: "IG: Consumer goods and services, transportation and storage, administrative and support "
       "service activities",
    6: "IG: Technology, telecommunications",
    7: "IG: Health care, utilities, professional and technical activities",
    8: "IG: Covered bonds",
    9: "HY & NR: Sovereigns including central banks, multilateral development banks",
    10: "HY & NR: Local government, government-backed non-financials, education, public "
        "administration",
    11: "HY & NR: Financials including government-backed financials",
    12: "HY & NR: Basic materials, energy, industrials, agriculture, manufacturing, mining and "
        "quarrying",
    13: "HY & NR: Consumer goods and services, transportation and storage, administrative and "
        "support service activities",
    14: "HY & NR: Technology, telecommunications",
    15: "HY & NR: Health care, utilities, professional and technical activities",
    16: "Other sector",
    17: "IG indices",
    18: "HY indices",
}
"""MAR21.51 Table 3 (pp. 594-595)."""

CSR_SECTOR_TO_IG_BUCKET: Final[dict[CreditSector, int]] = {
    CreditSector.SOVEREIGN: 1,
    CreditSector.LOCAL_GOVERNMENT: 2,
    CreditSector.FINANCIAL: 3,
    CreditSector.BASIC_MATERIALS: 4,
    CreditSector.CONSUMER: 5,
    CreditSector.TECHNOLOGY: 6,
    CreditSector.HEALTH_CARE: 7,
    CreditSector.COVERED_BOND: 8,
}
"""MAR21.51 Table 3: IG sector buckets 1-8; HY/NR = IG bucket + 8 (buckets 9-15). Covered bonds
appear only in the IG block."""

CSR_OTHER_BUCKET: Final[int] = 16
"""MAR21.51 Table 3 / MAR21.52(2): issuers not assignable to a sector -> bucket 16."""

CSR_IG_INDEX_BUCKET: Final[int] = 17
CSR_HY_INDEX_BUCKET: Final[int] = 18
"""MAR21.51 Table 3, MAR21.33(2)(b): IG indices 17 (>= 75% IG constituents), else 18."""

CSR_NONSEC_RW: Final[dict[int, float]] = {
    1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015, 8: 0.025,
    9: 0.020, 10: 0.040, 11: 0.120, 12: 0.070, 13: 0.085, 14: 0.055, 15: 0.050,
    16: 0.120, 17: 0.015, 18: 0.050,
}
"""MAR21.53 Table 4 (p. 597): delta CSR non-securitisation risk weights (all tenors)."""

CSR_COVERED_BOND_AA_RW: Final[float] = 0.015
"""MAR21.53 footnote 288: covered bonds rated AA- or higher: 1.5% at the bank's discretion."""

CSR_RHO_NAME_DIFF: Final[float] = 0.35
CSR_RHO_TENOR_DIFF: Final[float] = 0.65
CSR_RHO_BASIS_DIFF: Final[float] = 0.999
"""MAR21.54 (p. 598): buckets 1-15, rho = rho_name x rho_tenor x rho_basis with
35% / 65% / 99.90% when name / tenor / curve differ (1 otherwise)."""

CSR_INDEX_RHO_NAME_DIFF: Final[float] = 0.80
CSR_INDEX_RHO_TENOR_DIFF: Final[float] = 0.65
CSR_INDEX_RHO_BASIS_DIFF: Final[float] = 0.999
"""MAR21.55 (p. 598): buckets 17-18, 80% / 65% / 99.90%."""

CSR_GAMMA_RATING_DIFF: Final[float] = 0.50
"""MAR21.57(1) (p. 599): 50% when both buckets are in 1-15 with different rating category."""

# MAR21.57 Table 5 (p. 599): gamma_sector between sector groups; keys are sector groups
# 1 (=1/9), 2 (=2/10), ..., 7 (=7/15), 8, 16, 17, 18.
_CSR_SECTOR_GROUPS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8, 16, 17, 18)
_CSR_TABLE5_UPPER: Final[dict[int, tuple[float, ...]]] = {
    #     2     3     4     5     6     7     8    16    17    18
    1: (0.75, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.00, 0.45, 0.45),
    #           3     4     5     6     7     8    16    17    18
    2: (0.05, 0.15, 0.20, 0.15, 0.10, 0.10, 0.00, 0.45, 0.45),
    3: (0.05, 0.15, 0.20, 0.05, 0.20, 0.00, 0.45, 0.45),
    4: (0.20, 0.25, 0.05, 0.05, 0.00, 0.45, 0.45),
    5: (0.25, 0.05, 0.15, 0.00, 0.45, 0.45),
    6: (0.05, 0.20, 0.00, 0.45, 0.45),
    7: (0.05, 0.00, 0.45, 0.45),
    8: (0.00, 0.45, 0.45),
    16: (0.00, 0.00),
    17: (0.75,),
}


def _build_table5() -> dict[tuple[int, int], float]:
    """Expand the upper triangle of MAR21.57 Table 5 into a symmetric lookup."""
    out: dict[tuple[int, int], float] = {}
    for i, g in enumerate(_CSR_SECTOR_GROUPS):
        row = _CSR_TABLE5_UPPER.get(g, ())
        for j, h in enumerate(_CSR_SECTOR_GROUPS[i + 1:]):
            out[(g, h)] = row[j]
            out[(h, g)] = row[j]
    return out


CSR_GAMMA_SECTOR: Final[dict[tuple[int, int], float]] = _build_table5()
"""MAR21.57 Table 5 (p. 599): gamma_sector for different sector groups (symmetric)."""

# =========================================================================
#  MAR21.58-21.61 -- CSR securitisation (CTP)
# =========================================================================

CSR_CTP_RW: Final[dict[int, float]] = {
    1: 0.04, 2: 0.04, 3: 0.08, 4: 0.05, 5: 0.04, 6: 0.03, 7: 0.02, 8: 0.06,
    9: 0.13, 10: 0.13, 11: 0.16, 12: 0.10, 13: 0.12, 14: 0.12, 15: 0.12, 16: 0.13,
}
"""MAR21.59 Table 6 (pp. 600-601): CTP risk weights, buckets 1-16 (no index buckets,
MAR21.58(1))."""

CSR_CTP_RHO_BASIS_DIFF: Final[float] = 0.99
"""MAR21.60(1) (p. 601): rho_basis 99.00% for the CTP; name and tenor as MAR21.54/21.55."""

# =========================================================================
#  MAR21.62-21.71 -- CSR securitisation (non-CTP)
# =========================================================================

SEC_ASSET_ORDER: Final[tuple[SecAssetClass, ...]] = (
    SecAssetClass.RMBS_PRIME,
    SecAssetClass.RMBS_MIDPRIME,
    SecAssetClass.RMBS_SUBPRIME,
    SecAssetClass.CMBS,
    SecAssetClass.ABS_STUDENT_LOANS,
    SecAssetClass.ABS_CREDIT_CARDS,
    SecAssetClass.ABS_AUTO,
    SecAssetClass.CLO_NON_CTP,
)
"""MAR21.62 Table 7 (pp. 602-603): sector order within each credit-quality block."""

SEC_TRANCHE_OFFSET: Final[dict[SecTrancheClass, int]] = {
    SecTrancheClass.SENIOR_IG: 0,       # buckets 1-8
    SecTrancheClass.NON_SENIOR_IG: 8,   # buckets 9-16
    SecTrancheClass.HY_NR: 16,          # buckets 17-24
}
"""MAR21.62 Table 7: senior IG 1-8, non-senior IG 9-16, HY & NR 17-24."""

SEC_OTHER_BUCKET: Final[int] = 25
"""MAR21.62 Table 7 / MAR21.63(2): other sector, bucket 25."""

SEC_SENIOR_IG_RW: Final[dict[int, float]] = {
    1: 0.009, 2: 0.015, 3: 0.020, 4: 0.020, 5: 0.008, 6: 0.012, 7: 0.012, 8: 0.014,
}
"""MAR21.64 Table 8 (pp. 603-604): buckets 1-8."""

SEC_NON_SENIOR_IG_SCALAR: Final[float] = 1.25
"""MAR21.65 (p. 604): buckets 9-16 = buckets 1-8 x 1.25 (e.g. 1.25 x 0.9% = 1.125%)."""

SEC_HY_NR_SCALAR: Final[float] = 1.75
"""MAR21.66 (p. 604): buckets 17-24 = buckets 1-8 x 1.75 (e.g. 1.75 x 0.9% = 1.575%)."""

SEC_OTHER_RW: Final[float] = 0.035
"""MAR21.67 (p. 604): bucket 25 = 3.5%."""


def _build_sec_rw() -> dict[int, float]:
    """MAR21.64-21.67: all 25 sec non-CTP risk weights."""
    out: dict[int, float] = {}
    for b, w in SEC_SENIOR_IG_RW.items():
        out[b] = w
        out[b + 8] = w * SEC_NON_SENIOR_IG_SCALAR
        out[b + 16] = w * SEC_HY_NR_SCALAR
    out[SEC_OTHER_BUCKET] = SEC_OTHER_RW
    return out


CSR_SEC_NONCTP_RW: Final[dict[int, float]] = _build_sec_rw()
"""MAR21.64-21.67: delta CSR securitisation (non-CTP) risk weights, buckets 1-25."""

SEC_RHO_TRANCHE_DIFF: Final[float] = 0.40
SEC_RHO_TENOR_DIFF: Final[float] = 0.80
SEC_RHO_BASIS_DIFF: Final[float] = 0.999
"""MAR21.68 (p. 604): rho_tranche 40%, rho_tenor 80%, rho_basis 99.90%."""

SEC_GAMMA: Final[float] = 0.0
"""MAR21.70 (p. 605): across buckets 1-24, gamma = 0%. MAR21.71: bucket 25 added by simple sum."""

# =========================================================================
#  MAR21.72-21.80 -- Equity
# =========================================================================

EQUITY_BUCKETS: Final[dict[int, str]] = {
    1: "Large, EME: consumer goods/services, transportation/storage, admin/support, "
       "healthcare, utilities",
    2: "Large, EME: telecommunications, industrials",
    3: "Large, EME: basic materials, energy, agriculture, manufacturing, mining/quarrying",
    4: "Large, EME: financials incl. government-backed, real estate activities, technology",
    5: "Large, AE: consumer goods/services, transportation/storage, admin/support, "
       "healthcare, utilities",
    6: "Large, AE: telecommunications, industrials",
    7: "Large, AE: basic materials, energy, agriculture, manufacturing, mining/quarrying",
    8: "Large, AE: financials incl. government-backed, real estate activities, technology",
    9: "Small, EME: all sectors of buckets 1-4",
    10: "Small, AE: all sectors of buckets 5-8",
    11: "Other sector",
    12: "Large market cap, advanced economy equity indices (non-sector specific)",
    13: "Other equity indices (non-sector specific)",
}
"""MAR21.72 Table 9 (pp. 605-606)."""

EQUITY_SECTOR_TO_EME_BUCKET: Final[dict[EquitySector, int]] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 1,
    EquitySector.TELECOM_INDUSTRIALS: 2,
    EquitySector.MATERIALS_ENERGY: 3,
    EquitySector.FINANCIALS_REALESTATE_TECH: 4,
}
"""MAR21.72 Table 9: large-cap EME buckets 1-4; advanced economy = +4 (buckets 5-8)."""

EQUITY_SMALL_EME_BUCKET: Final[int] = 9
EQUITY_SMALL_AE_BUCKET: Final[int] = 10
EQUITY_OTHER_BUCKET: Final[int] = 11
EQUITY_LARGE_AE_INDEX_BUCKET: Final[int] = 12
EQUITY_OTHER_INDEX_BUCKET: Final[int] = 13

EQUITY_LARGE_CAP_THRESHOLD_USD_BN: Final[float] = 2.0
"""MAR21.74 (p. 607): large market cap >= USD 2 billion; small < USD 2 billion."""

ADVANCED_ECONOMIES: Final[tuple[str, ...]] = (
    "Canada", "United States", "Mexico", "euro area", "United Kingdom", "Norway", "Sweden",
    "Denmark", "Switzerland", "Japan", "Australia", "New Zealand", "Singapore",
    "Hong Kong SAR",
)
"""MAR21.75 (p. 607)."""

EQUITY_SPOT_RW: Final[dict[int, float]] = {
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,
    9: 0.70, 10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25,
}
"""MAR21.77 Table 10 (pp. 607-608): equity spot price risk weights."""

EQUITY_REPO_RW: Final[dict[int, float]] = {
    1: 0.0055, 2: 0.0060, 3: 0.0045, 4: 0.0055, 5: 0.0030, 6: 0.0035, 7: 0.0040, 8: 0.0050,
    9: 0.0070, 10: 0.0050, 11: 0.0070, 12: 0.0015, 13: 0.0025,
}
"""MAR21.77 Table 10 (pp. 607-608): equity repo rate risk weights."""

EQUITY_SPOT_REPO_SAME_NAME_RHO: Final[float] = 0.999
"""MAR21.78(1) (p. 608): spot vs repo of the same issuer: 99.90%."""

EQUITY_INTRA_RHO: Final[dict[int, float]] = {
    1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15,
    5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25,
    9: 0.075, 10: 0.125, 12: 0.80, 13: 0.80,
}
"""MAR21.78(2)(a)-(e) (p. 608): 15% large EME, 25% large AE, 7.5% small EME, 12.5% small AE,
80% index buckets; MAR21.78(3): same for repo-repo."""

EQUITY_SPOT_REPO_DIFF_NAME_FACTOR: Final[float] = 0.999
"""MAR21.78(4) (p. 608): spot vs repo, different issuers: MAR21.78(2) parameter x 99.90%."""

EQUITY_GAMMA_1_10: Final[float] = 0.15
EQUITY_GAMMA_OTHER_BUCKET: Final[float] = 0.0
EQUITY_GAMMA_INDEX_PAIR: Final[float] = 0.75
EQUITY_GAMMA_DEFAULT: Final[float] = 0.45
"""MAR21.80 (p. 609): 15% within 1-10; 0% if either is 11; 75% between 12 and 13; 45% otherwise."""

# =========================================================================
#  MAR21.81-21.85 -- Commodity
# =========================================================================

COMMODITY_BUCKETS: Final[dict[int, str]] = {
    1: "Energy - solid combustibles",
    2: "Energy - liquid combustibles",
    3: "Energy - electricity and carbon trading",
    4: "Freight",
    5: "Metals - non-precious",
    6: "Gaseous combustibles",
    7: "Precious metals (including gold)",
    8: "Grains and oilseed",
    9: "Livestock and dairy",
    10: "Softs and other agriculturals",
    11: "Other commodity",
}
"""MAR21.82 Table 11 (pp. 609-611)."""

COMMODITY_GROUP_TO_BUCKET: Final[dict[CommodityGroup, int]] = {
    CommodityGroup.ENERGY_SOLID: 1,
    CommodityGroup.ENERGY_LIQUID: 2,
    CommodityGroup.ENERGY_ELECTRICITY_CARBON: 3,
    CommodityGroup.FREIGHT: 4,
    CommodityGroup.METALS_NON_PRECIOUS: 5,
    CommodityGroup.GASEOUS_ENERGY: 6,
    CommodityGroup.PRECIOUS_METALS: 7,
    CommodityGroup.GRAINS_OILSEED: 8,
    CommodityGroup.LIVESTOCK_DAIRY: 9,
    CommodityGroup.SOFTS_OTHER_AGRI: 10,
    CommodityGroup.OTHER: 11,
}
"""MAR21.82 Table 11 bucket numbering."""

COMMODITY_RW: Final[dict[int, float]] = {
    1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45,
    7: 0.20, 8: 0.35, 9: 0.25, 10: 0.35, 11: 0.50,
}
"""MAR21.82 Table 11 (pp. 609-611): commodity delta risk weights."""

COMMODITY_RHO_CTY: Final[dict[int, float]] = {
    1: 0.55, 2: 0.95, 3: 0.40, 4: 0.80, 5: 0.60, 6: 0.65,
    7: 0.55, 8: 0.45, 9: 0.15, 10: 0.40, 11: 0.15,
}
"""MAR21.83(1) Table 12 (pp. 611-612): rho_cty for distinct commodities."""

COMMODITY_RHO_TENOR_DIFF: Final[float] = 0.99
COMMODITY_RHO_BASIS_DIFF: Final[float] = 0.999
"""MAR21.83(2)-(3) (p. 611): 99.00% different tenor; 99.90% different delivery location."""

COMMODITY_OTHER_BUCKET: Final[int] = 11
COMMODITY_GAMMA_1_10: Final[float] = 0.20
COMMODITY_GAMMA_OTHER: Final[float] = 0.0
"""MAR21.85 (p. 613): 20% within buckets 1-10; 0% if either bucket is 11."""

# =========================================================================
#  MAR21.86-21.89 -- FX
# =========================================================================

FX_RW: Final[float] = 0.15
"""MAR21.87 (p. 613): unique relative risk weight 15%."""

FX_SPECIFIED_PAIRS: Final[frozenset[str]] = frozenset({
    "USD/EUR", "USD/JPY", "USD/GBP", "USD/AUD", "USD/CAD", "USD/CHF", "USD/MXN", "USD/CNY",
    "USD/NZD", "USD/RUB", "USD/HKD", "USD/SGD", "USD/TRY", "USD/KRW", "USD/SEK", "USD/ZAR",
    "USD/INR", "USD/NOK", "USD/BRL",
})
"""MAR21.88 footnote 293 (p. 613): specified currency pairs."""

FX_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"USD"} | {pair.split("/")[1] for pair in FX_SPECIFIED_PAIRS}
)
"""Currencies appearing in the MAR21.88 specified pairs; a pair of two of them is either a
specified pair (one leg USD) or a first-order cross (footnote 294, e.g. EUR/AUD)."""

FX_GAMMA: Final[float] = 0.60
"""MAR21.89 (p. 613): across FX buckets, 60%."""

# =========================================================================
#  MAR21.90-21.95 -- Vega
# =========================================================================

VEGA_LIQUIDITY_HORIZON: Final[dict[str, int]] = {
    "GIRR": 60,
    "CSR_NONSEC": 120,
    "CSR_SEC_CTP": 120,
    "CSR_SEC_NONCTP": 120,
    "EQUITY_LARGE_CAP_INDEX": 20,
    "EQUITY_SMALL_CAP_OTHER": 60,
    "COMMODITY": 120,
    "FX": 40,
}
"""MAR21.92 Table 13 (p. 614): regulatory liquidity horizon LH_risk class (days)."""

VEGA_RW: Final[dict[str, float]] = {
    "GIRR": 1.00,
    "CSR_NONSEC": 1.00,
    "CSR_SEC_CTP": 1.00,
    "CSR_SEC_NONCTP": 1.00,
    "EQUITY_LARGE_CAP_INDEX": 0.7778,
    "EQUITY_SMALL_CAP_OTHER": 1.00,
    "COMMODITY": 1.00,
    "FX": 1.00,
}
"""MAR21.92 Table 13 (p. 614): vega risk weights. Footnote 295 states RW_k is determined from
RW_sigma = 55% and LH_risk class (the formula itself is an image lost in extraction and in the
PDF render); the printed Table 13 values are used. FAQ: 77.78% for equity buckets 1-8, 12, 13;
100% for buckets 9-11."""

VEGA_RW_SIGMA: Final[float] = 0.55
"""MAR21.92 footnote 295: RW_sigma = 55% (informational)."""

VEGA_ALPHA: Final[float] = 0.01
"""MAR21.93(1)(a) and (2)(a) (p. 615): alpha = 1% in
rho_option maturity = exp(-alpha |T_k - T_l| / min(T_k, T_l)) and the same for the underlying
residual maturity; GIRR rho = min(rho_opt x rho_und; 1). MAR21.94: non-GIRR
rho = min(rho_delta x rho_opt; 1)."""

# =========================================================================
#  MAR21.96-21.101 -- Curvature
# =========================================================================

FX_CURVATURE_NON_REPORTING_SCALAR: Final[float] = 1.5
"""MAR21.98 (p. 616): for FX options not referencing the reporting (or base) currency, CVR+
and CVR- may be divided by 1.5."""

CURVATURE_CORRELATION_POWER: Final[int] = 2
"""MAR21.100-21.101 (p. 617): curvature rho and gamma are the squares of the delta parameters;
for CSR (non-sec, CTP) only rho_name applies; for sec non-CTP only rho_tranche; for commodity
only rho_cty (MAR21.100: dimensions not defined for the curvature risk factor are ignored)."""

# =========================================================================
#  MAR22 -- Default risk capital
# =========================================================================

DRC_LGD: Final[dict[DRCSeniority, float]] = {
    DRCSeniority.EQUITY: 1.00,
    DRCSeniority.NON_SENIOR: 1.00,
    DRCSeniority.SENIOR: 0.75,
    DRCSeniority.COVERED_BOND: 0.25,
}
"""MAR22.12 (p. 622): equity and non-senior 100%; senior 75%; covered bonds 25%.
MAR22.12(4): where the price is not linked to recovery, no LGD multiplication (factor 1)."""

DRC_LGD_NOT_LINKED_TO_RECOVERY: Final[float] = 1.0
"""MAR22.12(4): no multiplication of the notional by the LGD."""

DRC_SENIORITY_RANK: Final[dict[DRCSeniority, int]] = {
    DRCSeniority.EQUITY: 0,
    DRCSeniority.NON_SENIOR: 1,
    DRCSeniority.SENIOR: 2,
    DRCSeniority.COVERED_BOND: 3,
}
"""MAR22.19(1) (p. 626): a short may offset a long of the same obligor only where the short has
the same or lower seniority. Ranking (higher = more senior) by LGD ordering of MAR22.12."""

DRC_CAPITAL_HORIZON_YEARS: Final[float] = 1.0
"""MAR22.15 (p. 624): one-year capital horizon; no scaling at maturity >= 1 year."""

DRC_MATURITY_FLOOR_YEARS: Final[float] = 0.25
"""MAR22.18 (p. 626): maturity weighting floored at one-fourth (three months)."""

DRC_CASH_EQUITY_MATURITIES: Final[tuple[float, float]] = (0.25, 1.0)
"""MAR22.16 (p. 625): cash equities assigned either three months or more than one year."""

DRC_BUCKETS: Final[tuple[str, str, str]] = ("CORPORATES", "SOVEREIGNS", "LOCAL_GOVERNMENTS")
"""MAR22.22 (p. 627): corporates; sovereigns; local governments and municipalities."""

DRC_RW_TABLE2: Final[dict[str, float]] = {
    "AAA": 0.005,
    "AA": 0.02,
    "A": 0.03,
    "BBB": 0.06,
    "BB": 0.15,
    "B": 0.30,
    "CCC": 0.50,
    "UNRATED": 0.15,
    "DEFAULTED": 1.00,
}
"""MAR22.24 Table 2 (pp. 627-628): default risk weights by credit quality category."""

DRC_RATING_TO_CATEGORY: Final[dict[RatingBucket, str]] = {
    R.AAA_TO_AA_MINUS: "AA",
    R.A_PLUS_TO_A_MINUS: "A",
    R.BBB_PLUS_TO_BBB_MINUS: "BBB",
    R.BB_PLUS_TO_BB_MINUS: "BB",
    R.B_PLUS_TO_B_MINUS: "B",
    R.BELOW_B_MINUS: "CCC",
    R.UNRATED: "UNRATED",
}
"""Map of the engine's six-band :class:`RatingBucket` to MAR22.24 Table 2. The engine bucket
AAA..AA- spans two Table 2 categories (AAA 0.5%, AA 2%); the conservative AA (2%) is used unless
``flags['drc_aaa']`` marks an AAA obligor. BELOW_B- maps to CCC."""

DRC_AAA_FLAG: Final[str] = "drc_aaa"

DRC_SEC_BANKING_BOOK_TO_DRC_FACTOR: Final[float] = 0.08
# TODO: VERIFY -- MAR22.34(1) and MAR22.42 say only that securitisation default risk weights are
# "based on the corresponding risk weights for banking book instruments" (CRE40-CRE44, one-year
# maturity). The conversion of a banking-book RWA weight (e.g. 1,250%) into a DRC weight applied
# to JTD is not written in MAR22. 8% (= 1/12.5, RBC20 / MAR20.1) is used, which caps a 1,250% RW
# at 100% of JTD (consistent with the MAR22.34(3) cap at fair value).

DRC_SEC_NONCTP_REGIONS: Final[tuple[str, ...]] = ("ASIA", "EUROPE", "NORTH_AMERICA", "OTHER")
"""MAR22.31(2)(b) (p. 630): Asia, Europe, North America and all other."""

DRC_SEC_NONCTP_ASSET_CLASSES: Final[tuple[str, ...]] = (
    "ABCP", "AUTO_LOANS_LEASES", "RMBS", "CREDIT_CARDS", "CMBS", "CLO", "CDO_SQUARED",
    "SME", "STUDENT_LOANS", "OTHER_RETAIL", "OTHER_WHOLESALE",
)
"""MAR22.31(2)(a) (p. 630): the 11 asset classes."""

DRC_SEC_CORPORATE_BUCKET: Final[str] = "CORPORATES"
"""MAR22.31(1): corporates (excluding SMEs), all regions."""

DRC_SEC_OTHER_BUCKET: Final[str] = "OTHER"
"""MAR22.32(2): exposures not assignable by type or region -> "other bucket"."""

DRC_SEC_ASSET_FROM_ENUM: Final[dict[SecAssetClass, str]] = {
    SecAssetClass.RMBS_PRIME: "RMBS",
    SecAssetClass.RMBS_MIDPRIME: "RMBS",
    SecAssetClass.RMBS_SUBPRIME: "RMBS",
    SecAssetClass.CMBS: "CMBS",
    SecAssetClass.ABS_STUDENT_LOANS: "STUDENT_LOANS",
    SecAssetClass.ABS_CREDIT_CARDS: "CREDIT_CARDS",
    SecAssetClass.ABS_AUTO: "AUTO_LOANS_LEASES",
    SecAssetClass.CLO_NON_CTP: "CLO",
}
"""Engine :class:`SecAssetClass` to MAR22.31 asset classes; the remaining classes (ABCP,
CDO-squared, SME, other retail, other wholesale, corporates) are read from flags
``sec_asset_<name lower-case>`` / ``sec_asset_corporate``."""

DRC_CTP_NEGATIVE_BUCKET_WEIGHT: Final[float] = 0.5
"""MAR22.45 (p. 633): DRC_CTP = max(sum_b [max(DRC_b, 0) + 0.5 x min(DRC_b, 0)], 0)."""

# =========================================================================
#  MAR23 -- Residual risk add-on
# =========================================================================

RRAO_EXOTIC_RW: Final[float] = 0.01
"""MAR23.8(2)(a) (p. 637): exotic underlying 1.0%."""

RRAO_OTHER_RW: Final[float] = 0.001
"""MAR23.8(2)(b) (p. 637): other residual risks 0.1%."""

RRAO_FLAG_BACK_TO_BACK: Final[str] = "back_to_back"
"""MAR23.7 (p. 636): back-to-back transactions excluded (both legs)."""

RRAO_FLAG_LISTED_OR_CCP: Final[str] = "listed_or_ccp_eligible"
"""MAR23.7: listed and/or CCP-eligible instruments excluded from the *other residual risk*
RRAO; listed/CCP-eligible instruments with an exotic underlying remain in scope."""

# =========================================================================
#  MAR31-MAR33 -- Internal models approach scalars
# =========================================================================

IMA_ES_CONFIDENCE: Final[float] = 0.975
"""MAR33.3 (p. 670): 97.5th percentile, one-tailed."""

IMA_BASE_HORIZON_DAYS: Final[int] = 10
"""MAR33.4 (p. 670): base liquidity horizon T = 10 days."""

IMA_LH_BUCKETS: Final[tuple[int, ...]] = (10, 20, 40, 60, 120)
"""MAR33.4 Table 1 (p. 671): LH_j for j = 1..5."""

IMA_LIQUIDITY_HORIZONS: Final[dict[str, int]] = {
    "IR_SPECIFIED_CURRENCIES": 10,
    "IR_UNSPECIFIED_CURRENCIES": 20,
    "IR_VOLATILITY": 60,
    "IR_OTHER": 60,
    "CS_SOVEREIGN_IG": 20,
    "CS_SOVEREIGN_HY": 40,
    "CS_CORPORATE_IG": 40,
    "CS_CORPORATE_HY": 60,
    "CS_VOLATILITY": 120,
    "CS_OTHER": 120,
    "EQ_LARGE_CAP": 10,
    "EQ_SMALL_CAP": 20,
    "EQ_LARGE_CAP_VOLATILITY": 20,
    "EQ_SMALL_CAP_VOLATILITY": 60,
    "EQ_OTHER": 60,
    "FX_SPECIFIED_PAIRS": 10,
    "FX_PAIRS": 20,
    "FX_VOLATILITY": 40,
    "FX_OTHER": 40,
    "CMDTY_ENERGY_CARBON": 20,
    "CMDTY_PRECIOUS_NONFERROUS": 20,
    "CMDTY_OTHER": 60,
    "CMDTY_ENERGY_CARBON_VOLATILITY": 60,
    "CMDTY_PRECIOUS_NONFERROUS_VOLATILITY": 60,
    "CMDTY_OTHER_VOLATILITY": 120,
    "CMDTY_OTHER_TYPES": 120,
}
"""MAR33.12 Table 2 (p. 674, read from the rendered page): liquidity horizon n by risk factor
category (days). The IR "specified currencies" are EUR, USD, GBP, AUD, JPY, SEK, CAD and the
domestic currency."""

IMA_FX_SPECIFIED_PAIRS: Final[frozenset[str]] = FX_SPECIFIED_PAIRS | frozenset(
    {"EUR/JPY", "EUR/GBP", "EUR/CHF", "JPY/AUD"}
)
"""MAR33.12 footnote 309 (p. 675): the MAR21.88 pairs plus EUR/JPY, EUR/GBP, EUR/CHF and
JPY/AUD (and their first-order crosses)."""

IMA_NMRF_MIN_LH_DAYS: Final[int] = 20
"""MAR33.16(1) (p. 677): NMRF stress-scenario LH = max(MAR33.12 LH, 20 days)."""

IMA_REDUCED_SET_MIN_EXPLANATORY: Final[float] = 0.75
"""MAR33.5(2)(b) (p. 671): reduced set must explain >= 75% of the full ES."""

IMA_IMCC_RHO: Final[float] = 0.5
"""MAR33.15(2) (p. 676): IMCC = rho x IMCC(C) + (1 - rho) x sum_i IMCC(C_i), rho = 0.5."""

IMA_SES_RHO: Final[float] = 0.6
"""MAR33.17(4) (p. 678): SES correlation rho = 0.6."""

IMA_MULTIPLIER_BASE: Final[float] = 1.5
"""MAR33.42 (p. 685): m_c fixed at 1.5 plus add-ons."""

IMA_BACKTESTING_ADDON_MAX: Final[float] = 0.5
"""MAR33.42(2): the backtesting plus ranges from 0 to 0.5."""

IMA_BACKTESTING_MULTIPLIER: Final[dict[int, float]] = {
    0: 1.50, 1: 1.50, 2: 1.50, 3: 1.50, 4: 1.50,
    5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92,
    10: 2.00,
}
"""MAR32.9 Table 1 (p. 660): backtesting-dependent multiplier by number of exceptions in 250
observations (green 0-4, amber 5-9, red 10 or more -> 2.00)."""

IMA_BACKTESTING_ADDON: Final[dict[int, float]] = {
    n: round(m - IMA_MULTIPLIER_BASE, 10) for n, m in IMA_BACKTESTING_MULTIPLIER.items()
}
"""Plus factor = MAR32.9 Table 1 multiplier - 1.5 (MAR33.42); key 10 = "10 or more"."""

IMA_DESK_BACKTEST_MAX_EXCEPTIONS_99: Final[int] = 12
IMA_DESK_BACKTEST_MAX_EXCEPTIONS_975: Final[int] = 30
"""MAR32.19 (p. 662): desk moves to SA with more than 12 exceptions at 99% or 30 at 97.5%."""

IMA_PLA_SPEARMAN: Final[tuple[float, float]] = (0.80, 0.70)
IMA_PLA_KS: Final[tuple[float, float]] = (0.09, 0.12)
"""MAR32.42 Table 2 (p. 667): (amber threshold, red threshold) for Spearman and KS."""

IMA_PLA_SURCHARGE_K: Final[float] = 0.5
"""MAR33.45 (p. 686): k = 0.5 x sum_{amber} SA_i / sum_{green, amber} SA_i."""

# =========================================================================
#  MAR40 -- Simplified standardised approach
# =========================================================================

SSA_SCALING: Final[dict[str, float]] = {"IRR": 1.30, "EQ": 3.50, "COMM": 1.90, "FX": 1.20}
"""MAR40.2 (p. 688, formula rendered from the PDF): capital = CR_IRR x 1.30 + CR_EQ x 3.50 +
CR_FX x 1.20 + CR_COMM x 1.90."""

SSA_GOVT_SPECIFIC: Final[dict[str, float]] = {
    "AAA_TO_AA-": 0.0,
    "A+_TO_BBB-_LE_6M": 0.0025,
    "A+_TO_BBB-_6M_TO_24M": 0.01,
    "A+_TO_BBB-_GT_24M": 0.016,
    "BB+_TO_B-": 0.08,
    "BELOW_B-": 0.12,
    "UNRATED": 0.08,
}
"""MAR40.6 Table 1 (pp. 690-691): government category specific risk charges."""

SSA_QUALIFYING_SPECIFIC: Final[dict[str, float]] = {
    "LE_6M": 0.0025, "6M_TO_24M": 0.01, "GT_24M": 0.016,
}
"""MAR40.6 Table 1: qualifying category (MAR40.9-40.11) by residual maturity."""

SSA_OTHER_SPECIFIC: Final[dict[str, float]] = {
    "BB+_TO_BB-": 0.08, "BELOW_BB-": 0.12, "UNRATED": 0.08,
}
"""MAR40.6 Table 1: "other" category."""

SSA_MATURITY_SHORT_YEARS: Final[float] = 0.5
SSA_MATURITY_MEDIUM_YEARS: Final[float] = 2.0
"""MAR40.6 Table 1: 6 months or less; > 6 and up to and including 24 months; > 24 months."""

SSA_MATURITY_BANDS: Final[tuple[tuple[float, float, float, float], ...]] = (
    # (upper bound coupon >= 3% [years], upper bound coupon < 3% [years], RW, yield change)
    (1 / 12, 1 / 12, 0.0000, 1.00),
    (3 / 12, 3 / 12, 0.0020, 1.00),
    (6 / 12, 6 / 12, 0.0040, 1.00),
    (1.0, 1.0, 0.0070, 1.00),
    (2.0, 1.9, 0.0125, 0.90),
    (3.0, 2.8, 0.0175, 0.80),
    (4.0, 3.6, 0.0225, 0.75),
    (5.0, 4.3, 0.0275, 0.75),
    (7.0, 5.7, 0.0325, 0.70),
    (10.0, 7.3, 0.0375, 0.65),
    (15.0, 9.3, 0.0450, 0.60),
    (20.0, 10.6, 0.0525, 0.60),
    (math.inf, 12.0, 0.0600, 0.60),
)
"""MAR40.26 Table 4 (p. 699): maturity-method time bands, risk weights and assumed yield changes
(13 bands for coupon >= 3%). Low-coupon bands 14-15 follow."""

SSA_LOW_COUPON_EXTRA_BANDS: Final[tuple[tuple[float, float, float], ...]] = (
    (20.0, 0.0800, 0.60),
    (math.inf, 0.1250, 0.60),
)
"""MAR40.26 Table 4: low-coupon bands "12 to 20 years" 8.00% and "Over 20 years" 12.50%."""

SSA_LOW_COUPON_THRESHOLD: Final[float] = 0.03
"""MAR40.26: deep-discount bonds are those with a coupon of less than 3%."""

SSA_VERTICAL_DISALLOWANCE: Final[float] = 0.10
"""MAR40.27 (p. 699): 10% of the smaller of the offsetting weighted positions in a band."""

SSA_DURATION_VERTICAL_DISALLOWANCE: Final[float] = 0.05
"""MAR40.29(3) (p. 702): duration method, 5% vertical disallowance."""

SSA_ZONE_OF_BAND: Final[tuple[int, ...]] = (1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3)
"""MAR40.28(1) and Table 5 (pp. 700-701): zone 1 = 0-1 year (bands 1-4), zone 2 = 1-4 years
(bands 5-7; 1-3.6 years for low coupon), zone 3 = over 4 years (bands 8-15)."""

SSA_HORIZONTAL_WITHIN_ZONE: Final[dict[int, float]] = {1: 0.40, 2: 0.30, 3: 0.30}
SSA_HORIZONTAL_ADJACENT: Final[float] = 0.40
SSA_HORIZONTAL_ZONE1_ZONE3: Final[float] = 1.00
"""MAR40.28 Table 5 (p. 701): within zone 40% / 30% / 30%; adjacent zones 40%; zones 1-3 100%."""

SSA_EQUITY_SPECIFIC: Final[float] = 0.08
SSA_EQUITY_GENERAL: Final[float] = 0.08
"""MAR40.43 (p. 706): specific and general market risk each 8%."""

SSA_EQUITY_INDEX_ADDON: Final[float] = 0.02
"""MAR40.47 (p. 707): further 2% on the net position in a diversified index contract."""

SSA_EQUITY_ARBITRAGE: Final[float] = 0.02
"""MAR40.50 (p. 707): 2% of the gross value on each side of a qualifying index arbitrage."""

SSA_FX_CHARGE: Final[float] = 0.08
"""MAR40.61 (p. 711): 8% of the overall net open position (incl. gold, regardless of sign)."""

SSA_COMMODITY_SPREAD_RATE: Final[float] = 0.015
SSA_COMMODITY_CARRY_RATE: Final[float] = 0.006
SSA_COMMODITY_OUTRIGHT: Final[float] = 0.15
"""MAR40.69-40.70 Table 10 (pp. 714-715): 1.5% spread rate on matched positions per band,
0.6% per band carried forward, 15% on the residual net position."""

SSA_COMMODITY_BANDS: Final[tuple[float, ...]] = (1 / 12, 3 / 12, 6 / 12, 1.0, 2.0, 3.0, math.inf)
"""MAR40.69 Table 10: 0-1m, 1-3m, 3-6m, 6-12m, 1-2y, 2-3y, over 3y (upper bounds, years)."""

SSA_COMMODITY_SIMPLIFIED_NET: Final[float] = 0.15
SSA_COMMODITY_SIMPLIFIED_GROSS: Final[float] = 0.03
"""MAR40.72-40.73 (p. 715): 15% of the net position plus 3% of gross (long + short)."""

SSA_OPTION_FX_CHARGE: Final[float] = 0.08
SSA_OPTION_COMMODITY_CHARGE: Final[float] = 0.15
"""MAR40.76 Table 11 footnote 344 (p. 717): currency options 8%, commodity options 15%."""
