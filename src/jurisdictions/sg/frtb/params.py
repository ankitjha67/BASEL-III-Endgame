"""MAS Notice 637 market-risk (FRTB) parameters -- Singapore.

Every constant is transcribed from MAS Notice 637 (version effective 1 January 2026), Part VIII:

    - Division 1 (paras 8.1.1-8.1.42): market RWA = 12.5 x capital, method choice,
      SSA(MR) eligibility (8.1.18)
    - Division 2 (paras 8.2.1-8.2.218): SA(MR) -- SBM (Tables 8-1 to 8-13),
      DRC (Tables 8-14, 8-15), RRAO
    - Division 3 (paras 8.3.1-8.3.245A): IMA (Tables 8-22 to 8-25)
    - Division 4 (paras 8.4.1-8.4.85) and Annex 8E:
      SSA(MR) (Tables 8E-1 to 8E-4)

Citations are by paragraph / table number (page numbers are omitted). MAS Part VIII
Division 2 is a near-verbatim transposition of Basel Framework MAR20-MAR23; where a MAS
value equals the Basel value the corresponding MAR paragraph is cited in square brackets.
Every MAS deviation from MAR is listed in ``MAS_DEVIATIONS_FROM_MAR`` at the end of this module
and in
``docs/jurisdictions/SG_frtb_reference.md``. Where the text does not settle a value the constant
carries a ``TODO: VERIFY`` marker.

Credit quality: MAS defines credit quality by the Table 7M-1 credit quality grades (CQG "1" =
AAA..AA-, "2" = A+..A-, "3" = BBB+..BBB-, "4" = BB+..BB-, "5" = B+..B-, "6" = CCC+ and below,
Annex 7M p. 7-271). "CQG 3 or better" is the MAR21 "IG" split.

Currency: MAS expresses sensitivities in the reporting currency (para 8.2.55); a Singapore-
incorporated bank reports in SGD. All amounts are in reporting-currency millions.
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
#  Options (bank discretions, Authority approvals) -- engine defaults
# =========================================================================


@dataclass(frozen=True)
class SGFRTBOptions:
    """Bank discretions and Authority approvals in MAS 637 Part VIII Division 2.

    Unlike MAR21.44 / MAR21.88, MAS makes the sqrt(2) GIRR and FX reductions mandatory
    ("must", paras 8.2.92 and 8.2.140), so they are not options here.
    """

    reporting_currency: str = "SGD"
    """Para 8.2.55: sensitivities in the reporting currency; para 8.2.138: FX buckets are
    currency pairs against the reporting (or approved base) currency."""

    covered_bond_cqg1_reduction: bool = True
    """Para 8.2.107 [MAR21.53 fn 288]: covered bonds with CQG "1" "may" take 1.5%. Engine default:
    exercised."""

    xccy_onshore_offshore_simple_sum: bool = False
    """Para 8.2.96 [MAR21.45]: onshore/offshore cross-currency basis curves over the same base
    "may" be aggregated by simple sum. Engine default: not exercised (99.90%, para 8.2.95)."""

    fx_curvature_all_div_1_5: bool = False
    """Para 8.2.152(b) (Authority's written approval): divide CVR+/- by 1.5 for ALL FX curvature
    instruments when all currencies (incl. the reporting currency) are shocked. Default: no
    approval; para 8.2.152(a) applies per instrument via the ``fx_curvature_scalar_1_5`` flag."""


DEFAULT_FRTB_OPTIONS: Final[SGFRTBOptions] = SGFRTBOptions()

# =========================================================================
#  Structure, RWA, correlation scenarios (paras 8.1.1, 8.2.1, 8.2.8, 8.2.14)
# =========================================================================

RWA_MULTIPLIER: Final[float] = 12.5
"""Para 8.1.1(a) [MAR20.1]: market RWA = 12.5 x market risk capital requirement
(SA(MR), IMA aggregation of para 8.3.243, or SSA(MR))."""

HIGH_CORRELATION_MULTIPLIER: Final[float] = 1.25
CORRELATION_CAP: Final[float] = 1.0
"""Para 8.2.14(b) [MAR21.6(2)]: rho and gamma x 1.25, "subject to a cap at 100%"."""

LOW_CORRELATION_SLOPE: Final[float] = 2.0
LOW_CORRELATION_INTERCEPT: Final[float] = 1.0
LOW_CORRELATION_FLOOR_FACTOR: Final[float] = 0.75
"""Para 8.2.14(c) [MAR21.6(3)]: rho_low = max(2 x rho - 100%; 75% x rho), same for
gamma."""

SCENARIOS: Final[tuple[str, str, str]] = ("LOW", "MEDIUM", "HIGH")
"""Para 8.2.14(a)-(c); para 8.2.8(f) [MAR21.7]: SBM = largest of the 3 scenario aggregates, each
the sum of delta, vega and curvature over all risk classes."""

# =========================================================================
#  GIRR (paras 8.2.16-8.2.29, 8.2.91-8.2.99; Tables 8-1, 8-2)
# =========================================================================

GIRR_TENORS: Final[tuple[float, ...]] = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)
"""Para 8.2.16(a) [MAR21.8(1)]: ten risk-free yield tenors."""

GIRR_DELTA_RW: Final[dict[float, float]] = {
    0.25: 0.017, 0.5: 0.017, 1.0: 0.016, 2.0: 0.013, 3.0: 0.012,
    5.0: 0.011, 10.0: 0.011, 15.0: 0.011, 20.0: 0.011, 30.0: 0.011,
}
"""Table 8-1 [MAR21.42 Table 1]: GIRR delta risk weights by tenor."""

GIRR_INFLATION_XCCY_RW: Final[float] = 0.016
"""Para 8.2.92(c)-(d) [MAR21.43]: 1.6% for inflation and cross-currency basis."""

GIRR_SQRT2_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"EUR", "USD", "GBP", "AUD", "JPY", "SEK", "CAD", "SGD"}
)
"""Para 8.2.92(a) and (c): the risk weights "must" be divided by sqrt(2) for EUR, USD,
GBP, AUD, JPY, SEK, CAD and SGD. MAS deviation: a fixed list (SGD named) instead of MAR21.44
footnote 283's "domestic reporting currency of a bank"; mandatory rather than "may"."""

GIRR_SQRT2_APPLIES_TO_INFLATION_XCCY: Final[bool] = True
"""Para 8.2.92(c): the 1.6% inflation / cross-currency basis weight is also divided
by sqrt(2) for the listed currencies (settles the MAR21.44 ambiguity)."""

SQRT2: Final[float] = math.sqrt(2.0)
"""Paras 8.2.92 and 8.2.140: divisor "the square root of 2"."""

GIRR_SAME_TENOR_DIFF_CURVE_RHO: Final[float] = 0.999
"""Para 8.2.93(a) [MAR21.45]: same tenor, different curves: 99.90%."""

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
"""Table 8-2 [MAR21.46 Table 2]: same bucket, different tenor, same curve; rows /
columns in ``GIRR_TENORS`` order."""

GIRR_TENOR_THETA: Final[float] = 0.03
GIRR_TENOR_RHO_FLOOR: Final[float] = 0.40
"""Para 8.2.93 footnote 657: Table 8-2 = max(exp(-theta |T_k - T_l| / min(T_k, T_l));
40%) with theta = 3% (worked example 1y vs 5y = 88.69%). Used in tests to re-derive Table 8-2."""

GIRR_DIFF_CURVE_FACTOR: Final[float] = 0.999
"""Para 8.2.93(c) [MAR21.47]: different tenor and curve: Table 8-2 x 99.90%."""

GIRR_INFLATION_DIFF_CURVE_RHO: Final[float] = 0.999
"""Para 8.2.94(b) [MAR21.47 FAQ]: different inflation curves, same currency: 99.90%.
Para 8.2.94(a): same inflation curve -> simple sum (rho = 1)."""

GIRR_XCCY_DIFF_CURVE_RHO: Final[float] = 0.999
"""Para 8.2.95: cross-currency bases over USD or EUR in the same bucket, different
curves: 99.90%. MAS deviation: MAR21.49 sets 0% between two cross-currency basis curves; MAS
para 8.2.98(c) also says 0% vs "another cross-currency basis". The engine reads 8.2.95 as the
specific rule for two bases of the same currency on different curves (onshore / offshore, over
USD vs over EUR) and 8.2.98(c) as the residual rule."""
# TODO: VERIFY -- paras 8.2.95 (99.90% between different xccy curves) and 8.2.98(c) (0% between a
# cross-currency basis and "another cross-currency basis") overlap; the engine applies 99.90%
# (8.2.95, the more conservative for same-sign exposures) to every pair of distinct xccy curves.

GIRR_INFLATION_VS_YIELD_RHO: Final[float] = 0.40
"""Para 8.2.97 [MAR21.48]: inflation vs a risk-free tenor: 40%."""

GIRR_XCCY_VS_OTHER_RHO: Final[float] = 0.0
"""Para 8.2.98(a)-(b) [MAR21.49]: cross-currency basis vs yield / inflation: 0%."""

GIRR_GAMMA: Final[float] = 0.50
"""Para 8.2.99 [MAR21.50]: across GIRR buckets: 50%."""

# =========================================================================
#  CSR non-securitisation (paras 8.2.30-8.2.32, 8.2.100-8.2.112; Tables 8-3 to 8-5)
# =========================================================================

CSR_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Paras 8.2.30(b), 8.2.33(b), 8.2.36(b) [MAR21.9-21.11]: CSR tenors."""

VEGA_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Paras 8.2.23-8.2.25, 8.2.31, 8.2.34, 8.2.37, 8.2.40, 8.2.45, 8.2.51: option-maturity (and
GIRR underlying residual-maturity) tenors."""

VEGA_NO_MATURITY_TENOR: Final[float] = 10.0
"""Para 8.2.70 [MAR21.25 FAQ]: options without a maturity -> 10-year tenor."""

COMMODITY_TENORS: Final[tuple[float, ...]] = (
    0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0
)
"""Para 8.2.42(b) [MAR21.13(1)(b)]: commodity delta tenors."""

CSR_NONSEC_BUCKETS: Final[dict[int, str]] = {
    1: "CQG 3 or better: Sovereigns (central governments, central banks, BIS, IMF, ECB, EU, ESM, "
       "EFSF) and MDBs",
    2: "CQG 3 or better: PSEs, education",
    3: "CQG 3 or better: Financial Institutions",
    4: "CQG 3 or better: Basic materials, energy, industrials, agriculture, manufacturing, mining "
       "and quarrying",
    5: "CQG 3 or better: Consumer goods and services, transportation and storage, administrative "
       "and support service activities",
    6: "CQG 3 or better: Technology, telecommunications",
    7: "CQG 3 or better: Health care, utilities, professional and technical activities",
    8: "CQG 3 or better: Covered bonds",
    9: "CQG 4 or worse or not rated: Sovereigns ... and MDBs",
    10: "CQG 4 or worse or not rated: PSEs, education",
    11: "CQG 4 or worse or not rated: Financial Institutions",
    12: "CQG 4 or worse or not rated: Basic materials, energy, industrials, agriculture, "
        "manufacturing, mining and quarrying",
    13: "CQG 4 or worse or not rated: Consumer goods and services, transportation and storage, "
        "administrative and support service activities",
    14: "CQG 4 or worse or not rated: Technology, telecommunications",
    15: "CQG 4 or worse or not rated: Health care, utilities, professional and technical "
        "activities",
    16: "Other sector",
    17: "Qualified indices with CQG 3 or better",
    18: "Qualified indices with CQG 4 or worse or not rated",
}
"""Table 8-3 [MAR21.51 Table 3]. MAS wording differences: bucket 2 is "PSEs,
education" (MAR: local government, government-backed non-financials, education, public
administration); credit quality is the Table 7M-1 grade."""

CSR_SECTOR_TO_CQG3_BUCKET: Final[dict[CreditSector, int]] = {
    CreditSector.SOVEREIGN: 1,
    CreditSector.LOCAL_GOVERNMENT: 2,   # MAS "PSEs, education"
    CreditSector.FINANCIAL: 3,
    CreditSector.BASIC_MATERIALS: 4,
    CreditSector.CONSUMER: 5,
    CreditSector.TECHNOLOGY: 6,
    CreditSector.HEALTH_CARE: 7,
    CreditSector.COVERED_BOND: 8,
}
"""Table 8-3: CQG-3-or-better sector buckets 1-8; CQG 4 or worse / not rated = +8 (9-15)."""

CSR_LOW_QUALITY_OFFSET: Final[int] = 8
"""Table 8-3: bucket 9-15 = bucket 1-7 + 8."""

CSR_OTHER_BUCKET: Final[int] = 16
CSR_HIGH_QUALITY_INDEX_BUCKET: Final[int] = 17
CSR_LOW_QUALITY_INDEX_BUCKET: Final[int] = 18
"""Table 8-3; paras 8.2.100 (other sector -> 16), 8.2.102(b) and 8.2.104(c) (indices 17 / 18)."""

INDEX_LOOK_THROUGH_SHARE: Final[float] = 0.75
"""Paras 8.2.102, 8.2.104(c), 8.2.114A, 8.2.128 [MAR21.33]: index sector /
quality / market-cap tests at "more than 75%" (sector) and "75% or more" (quality, size,
economy) of constituent weights. Applied upstream; used through the descriptors."""

CSR_NONSEC_RW: Final[dict[int, float]] = {
    1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015, 8: 0.025,
    9: 0.020, 10: 0.040, 11: 0.120, 12: 0.070, 13: 0.085, 14: 0.055, 15: 0.050,
    16: 0.120, 17: 0.015, 18: 0.050,
}
"""Table 8-4 [MAR21.53 Table 4]: CSR non-sec delta risk weights (all tenors)."""

CSR_COVERED_BOND_CQG1_RW: Final[float] = 0.015
"""Para 8.2.107 [MAR21.53 fn 288]: rated covered bonds with CQG "1": 1.5% (may)."""

CSR_RHO_NAME_DIFF: Final[float] = 0.35
CSR_RHO_TENOR_DIFF: Final[float] = 0.65
CSR_RHO_BASIS_DIFF: Final[float] = 0.999
"""Para 8.2.108 [MAR21.54]: buckets 1-15: 35% / 65% / 99.90%."""

CSR_INDEX_RHO_NAME_DIFF: Final[float] = 0.80
CSR_INDEX_RHO_TENOR_DIFF: Final[float] = 0.65
CSR_INDEX_RHO_BASIS_DIFF: Final[float] = 0.999
"""Para 8.2.109 [MAR21.55]: buckets 17-18: 80% / 65% / 99.90%."""

CSR_GAMMA_RATING_DIFF: Final[float] = 0.50
"""Para 8.2.111(a) [MAR21.57(1)]: 50% when both buckets are in 1-15 with different
credit quality (para 8.2.112: CQG 4-or-worse and unrated count as the same quality)."""

_CSR_SECTOR_GROUPS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8, 16, 17, 18)
_CSR_TABLE85_UPPER: Final[dict[int, tuple[float, ...]]] = {
    #     2/10  3/11  4/12  5/13  6/14  7/15   8    16    17    18
    1: (0.75, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.00, 0.45, 0.45),
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


def _build_table85() -> dict[tuple[int, int], float]:
    """Expand the upper triangle of Table 8-5 into a symmetric lookup."""
    out: dict[tuple[int, int], float] = {}
    for i, g in enumerate(_CSR_SECTOR_GROUPS):
        row = _CSR_TABLE85_UPPER.get(g, ())
        for j, h in enumerate(_CSR_SECTOR_GROUPS[i + 1:]):
            out[(g, h)] = row[j]
            out[(h, g)] = row[j]
    return out


CSR_GAMMA_SECTOR: Final[dict[tuple[int, int], float]] = _build_table85()
"""Table 8-5 [MAR21.57 Table 5]: gamma_sector between sector groups 1/9, ..., 7/15, 8,
16, 17, 18 (symmetric)."""

# =========================================================================
#  CSR securitisation CTP (paras 8.2.36-8.2.38, 8.2.113-8.2.118; Table 8-6)
# =========================================================================

CSR_CTP_RW: Final[dict[int, float]] = {
    1: 0.04, 2: 0.04, 3: 0.08, 4: 0.05, 5: 0.04, 6: 0.03, 7: 0.02, 8: 0.06,
    9: 0.13, 10: 0.13, 11: 0.16, 12: 0.10, 13: 0.12, 14: 0.12, 15: 0.12, 16: 0.13,
}
"""Table 8-6 [MAR21.59 Table 6]: CTP risk weights, buckets 1-16 (no 17-18,
para 8.2.114)."""

CSR_CTP_RHO_BASIS_DIFF: Final[float] = 0.99
"""Para 8.2.116(c)(ii) [MAR21.60]: bond vs CDS basis 99.00% for the CTP; name 35% and
tenor 65% as non-sec (para 8.2.116(a)-(b))."""

# =========================================================================
#  CSR securitisation non-CTP (paras 8.2.33-8.2.35, 8.2.119-8.2.125; Tables 8-7, 8-8)
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
"""Table 8-7 [MAR21.62 Table 7]: sector order within each seniority/quality block."""

SEC_TRANCHE_OFFSET: Final[dict[SecTrancheClass, int]] = {
    SecTrancheClass.SENIOR_IG: 0,       # buckets 1-8: senior, CQG 3 or better
    SecTrancheClass.NON_SENIOR_IG: 8,   # buckets 9-16: subordinated, CQG 3 or better
    SecTrancheClass.HY_NR: 16,          # buckets 17-24: CQG 4 or worse or not rated
}
"""Table 8-7: seniority / credit-quality blocks."""

SEC_OTHER_BUCKET: Final[int] = 25
"""Table 8-7 / para 8.2.121(b): other sector, bucket 25."""

CSR_SEC_NONCTP_RW: Final[dict[int, float]] = {
    1: 0.009, 2: 0.015, 3: 0.020, 4: 0.020, 5: 0.008, 6: 0.012, 7: 0.012, 8: 0.014,
    9: 0.01125, 10: 0.01875, 11: 0.025, 12: 0.025, 13: 0.010, 14: 0.015, 15: 0.015, 16: 0.0175,
    17: 0.01575, 18: 0.02625, 19: 0.035, 20: 0.035, 21: 0.014, 22: 0.021, 23: 0.021,
    24: 0.0245, 25: 0.035,
}
"""Table 8-8: all 25 risk weights printed explicitly. They equal MAR21.64-21.67
(buckets 1-8 x 1.25 for 9-16, x 1.75 for 17-24, 3.5% for 25)."""

SEC_RHO_TRANCHE_DIFF: Final[float] = 0.40
SEC_RHO_TENOR_DIFF: Final[float] = 0.80
SEC_RHO_BASIS_DIFF: Final[float] = 0.999
"""Para 8.2.123 [MAR21.68]: tranche 40% (same tranche = > 80% notional
overlap), tenor 80%, basis 99.90%."""

SEC_GAMMA: Final[float] = 0.0
"""Para 8.2.125(a) [MAR21.70]: gamma = 0% across buckets 1-24; para 8.2.125(b)
[MAR21.71]: bucket 25 added by simple sum."""

# =========================================================================
#  Equity (paras 8.2.39-8.2.41, 8.2.126-8.2.133; Tables 8-9, 8-10)
# =========================================================================

EQUITY_BUCKETS: Final[dict[int, str]] = {
    1: "Large, EME: consumer goods/services, transportation/storage, admin/support, healthcare, "
       "utilities",
    2: "Large, EME: telecommunications, industrials",
    3: "Large, EME: basic materials, energy, agriculture, manufacturing, mining/quarrying",
    4: "Large, EME: financial institutions, real estate activities, technology",
    5: "Large, AE: consumer goods/services, transportation/storage, admin/support, healthcare, "
       "utilities",
    6: "Large, AE: telecommunications, industrials",
    7: "Large, AE: basic materials, energy, agriculture, manufacturing, mining/quarrying",
    8: "Large, AE: financial institutions, real estate activities, technology",
    9: "Small, EME: all sectors of buckets 1-4",
    10: "Small, AE: all sectors of buckets 5-8",
    11: "Other sector",
    12: "Large market cap, advanced economy equity indices (non-sector specific)",
    13: "Other equity indices (non-sector specific)",
}
"""Table 8-9 [MAR21.72 Table 9]."""

EQUITY_SECTOR_TO_EME_BUCKET: Final[dict[EquitySector, int]] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 1,
    EquitySector.TELECOM_INDUSTRIALS: 2,
    EquitySector.MATERIALS_ENERGY: 3,
    EquitySector.FINANCIALS_REALESTATE_TECH: 4,
}
"""Table 8-9: large-cap EME buckets 1-4; advanced economy adds 4 (5-8)."""

EQUITY_AE_OFFSET: Final[int] = 4
EQUITY_SMALL_EME_BUCKET: Final[int] = 9
EQUITY_SMALL_AE_BUCKET: Final[int] = 10
EQUITY_OTHER_BUCKET: Final[int] = 11
EQUITY_LARGE_AE_INDEX_BUCKET: Final[int] = 12
EQUITY_OTHER_INDEX_BUCKET: Final[int] = 13
EQUITY_LAST_SECTOR_BUCKET: Final[int] = 10
EQUITY_LAST_LARGE_BUCKET: Final[int] = 8

EQUITY_LARGE_CAP_THRESHOLD_USD_BN: Final[float] = 2.0
"""Para 8.2.129(a) [MAR21.74]: large >= USD 2 billion (issuer plus listed subsidiaries;
related corporations that are not subsidiaries excluded, para 8.2.129(a)(ii))."""

ADVANCED_ECONOMIES: Final[tuple[str, ...]] = (
    "Canada", "United States", "Mexico", "euro area", "United Kingdom", "Norway", "Sweden",
    "Denmark", "Switzerland", "Japan", "Australia", "New Zealand", "Singapore",
    "Hong Kong SAR",
)
"""Para 8.2.129(b) [MAR21.75]."""

EQUITY_SPOT_RW: Final[dict[int, float]] = {
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,
    9: 0.70, 10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25,
}
"""Table 8-10 [MAR21.77 Table 10]: equity spot price risk weights."""

EQUITY_REPO_RW: Final[dict[int, float]] = {
    1: 0.0055, 2: 0.0060, 3: 0.0045, 4: 0.0055, 5: 0.0030, 6: 0.0035, 7: 0.0040, 8: 0.0050,
    9: 0.0070, 10: 0.0050, 11: 0.0070, 12: 0.0015, 13: 0.0025,
}
"""Table 8-10 [MAR21.77 Table 10]: equity repo rate risk weights."""

EQUITY_SPOT_REPO_SAME_NAME_RHO: Final[float] = 0.999
"""Para 8.2.131(a) [MAR21.78(1)]: spot vs repo, same issuer: 99.90%."""

EQUITY_INTRA_RHO: Final[dict[int, float]] = {
    1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15,
    5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25,
    9: 0.075, 10: 0.125, 12: 0.80, 13: 0.80,
}
"""Para 8.2.131(b)(i)-(v) [MAR21.78(2)]; para 8.2.131(c): same for repo-repo."""

EQUITY_SPOT_REPO_DIFF_NAME_FACTOR: Final[float] = 0.999
"""Para 8.2.131(d) [MAR21.78(4)]: spot vs repo, different issuers: (b) value x
99.90%."""

EQUITY_GAMMA_1_10: Final[float] = 0.15
EQUITY_GAMMA_OTHER_BUCKET: Final[float] = 0.0
EQUITY_GAMMA_INDEX_PAIR: Final[float] = 0.75
EQUITY_GAMMA_DEFAULT: Final[float] = 0.45
"""Para 8.2.133(a)-(d) [MAR21.80]."""

# =========================================================================
#  Commodity (paras 8.2.42-8.2.47, 8.2.134-8.2.137; Tables 8-11, 8-12)
# =========================================================================

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
"""Table 8-11 [MAR21.82 Table 11] bucket numbering."""

COMMODITY_RW: Final[dict[int, float]] = {
    1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45,
    7: 0.20, 8: 0.35, 9: 0.25, 10: 0.35, 11: 0.50,
}
"""Table 8-11 [MAR21.82 Table 11]: commodity delta risk weights."""

COMMODITY_RHO_CTY: Final[dict[int, float]] = {
    1: 0.55, 2: 0.95, 3: 0.40, 4: 0.80, 5: 0.60, 6: 0.65,
    7: 0.55, 8: 0.45, 9: 0.15, 10: 0.40, 11: 0.15,
}
"""Table 8-12 [MAR21.83(1) Table 12]: rho_cty for non-identical commodities."""

COMMODITY_RHO_TENOR_DIFF: Final[float] = 0.99
COMMODITY_RHO_BASIS_DIFF: Final[float] = 0.999
"""Para 8.2.135(b)-(c) [MAR21.83(2)-(3)]: 99% tenor, 99.90% location."""

COMMODITY_OTHER_BUCKET: Final[int] = 11
COMMODITY_GAMMA_1_10: Final[float] = 0.20
COMMODITY_GAMMA_OTHER: Final[float] = 0.0
"""Para 8.2.137 [MAR21.85]: 20% within 1-10; 0% if either is bucket 11."""

# =========================================================================
#  FX (paras 8.2.48-8.2.54, 8.2.138-8.2.141)
# =========================================================================

FX_RW: Final[float] = 0.15
"""Para 8.2.139 [MAR21.87]: 15%."""

FX_SPECIFIED_PAIRS: Final[frozenset[str]] = frozenset({
    "USD/EUR", "USD/JPY", "USD/GBP", "USD/AUD", "USD/CAD", "USD/CHF", "USD/MXN", "USD/CNY",
    "USD/NZD", "USD/RUB", "USD/HKD", "USD/SGD", "USD/TRY", "USD/KRW", "USD/SEK", "USD/ZAR",
    "USD/INR", "USD/NOK", "USD/BRL",
})
"""Para 8.2.140(a) [MAR21.88 fn 293]: the 19 specified pairs; (b) first-order crosses
(fn 668: EUR/AUD). The 15% weight "must" be divided by sqrt(2) (MAR21.88: "may")."""

FX_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"USD"} | {pair.split("/")[1] for pair in FX_SPECIFIED_PAIRS}
)
"""Currencies of the para 8.2.140 pairs; two distinct members form a specified pair or a
first-order cross."""

FX_GAMMA: Final[float] = 0.60
"""Para 8.2.141 [MAR21.89]: 60%."""

# =========================================================================
#  Vega (paras 8.2.142-8.2.149; Table 8-13)
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
"""Table 8-13 [MAR21.92 Table 13]: LH_risk class (days)."""

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
"""Table 8-13 [MAR21.92 Table 13]: 77.78% for equity vega buckets 1-8, 12-13 (fn 670);
100% otherwise (incl. equity 9-11, fn 671)."""

VEGA_RW_SIGMA: Final[float] = 0.55
VEGA_BASE_HORIZON_DAYS: Final[float] = 10.0
VEGA_RW_CAP: Final[float] = 1.0
"""Para 8.2.144 footnote 669: RW_k = min(RW_sigma x sqrt(LH_risk class) / sqrt(10);
100%), RW_sigma = 55%. Table 8-13 prints the rounded results (77.78% for LH 20)."""

VEGA_ALPHA: Final[float] = 0.01
"""Para 8.2.145(a)(i) and (b)(i) [MAR21.93]: alpha = 1% in
rho = exp(-alpha |T_k - T_l| / min(T_k, T_l)) (option maturity and underlying residual
maturity); GIRR rho = min(rho_opt x rho_und; 1). Para 8.2.146 [MAR21.94]: other classes
rho = min(rho_delta x rho_opt; 1), with para 8.2.147 restricting rho_delta to name / tranche /
commodity."""

# =========================================================================
#  Curvature (paras 8.2.150-8.2.157)
# =========================================================================

FX_CURVATURE_NON_REPORTING_SCALAR: Final[float] = 1.5
"""Para 8.2.152 [MAR21.98]: 1.5 scalar for FX instruments not referencing the
reporting (or base) currency (a); or for all instruments with Authority approval (b)."""

CURVATURE_CORRELATION_POWER: Final[int] = 2
"""Paras 8.2.154-8.2.155 [MAR21.100]: rho_curv = rho_delta^2 (CSR: rho_name only; sec
non-CTP: rho_tranche only; commodity: rho_cty only); para 8.2.157 [MAR21.101]: gamma squared."""

# =========================================================================
#  DRC (paras 8.2.158-8.2.209; Tables 8-14, 8-15)
# =========================================================================

DRC_LGD: Final[dict[DRCSeniority, float]] = {
    DRCSeniority.EQUITY: 1.00,
    DRCSeniority.NON_SENIOR: 1.00,
    DRCSeniority.SENIOR: 0.75,
    DRCSeniority.COVERED_BOND: 0.25,
}
"""Para 8.2.171 [MAR22.12]: equity and subordinated debt 100%; senior 75%; covered
bonds 25%. Para 8.2.174(a): no LGD multiplication where value is not linked to recovery."""

DRC_LGD_NOT_LINKED_TO_RECOVERY: Final[float] = 1.0
"""Para 8.2.174(a) [MAR22.12(4)]: notional not multiplied by LGD."""

DRC_SENIORITY_RANK: Final[dict[DRCSeniority, int]] = {
    DRCSeniority.EQUITY: 0,
    DRCSeniority.NON_SENIOR: 1,
    DRCSeniority.SENIOR: 2,
    DRCSeniority.COVERED_BOND: 3,
}
"""Para 8.2.180 [MAR22.19]: a short offsets a long only if it has the same or lower
seniority (fn 691: long bond vs short equity allowed, not the reverse)."""

DRC_CAPITAL_HORIZON_YEARS: Final[float] = 1.0
DRC_MATURITY_FLOOR_YEARS: Final[float] = 0.25
"""Paras 8.2.176-8.2.179 [MAR22.15-22.18]: weight = residual maturity / 1 year
for maturities < 1 year, floored at one-fourth (3 months); no weighting at >= 1 year."""

DRC_CASH_EQUITY_MATURITIES: Final[tuple[float, float]] = (0.25, 1.0)
"""Para 8.2.179(b) [MAR22.16]: non-derivative equities: 3 months or more than one
year."""

DRC_BUCKET_COMPANIES: Final[str] = "COMPANIES"
DRC_BUCKET_SOVEREIGNS: Final[str] = "CENTRAL_GOVERNMENTS_CENTRAL_BANKS_MDBS"
DRC_BUCKET_PSES: Final[str] = "PSES"
DRC_BUCKETS: Final[tuple[str, str, str]] = (
    DRC_BUCKET_COMPANIES, DRC_BUCKET_SOVEREIGNS, DRC_BUCKET_PSES,
)
"""Para 8.2.183: companies; central governments, central banks and MDBs; PSEs.
MAS deviation: MAR22.22 has "sovereigns" (MDBs not named) and "local governments and
municipalities"."""

DRC_RW_TABLE814: Final[dict[str, float]] = {
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
"""Table 8-14 [MAR22.24 Table 2]: default risk weights by credit quality category."""

DRC_RATING_TO_CATEGORY: Final[dict[RatingBucket, str]] = {
    R.AAA_TO_AA_MINUS: "AA",
    R.A_PLUS_TO_A_MINUS: "A",
    R.BBB_PLUS_TO_BBB_MINUS: "BBB",
    R.BB_PLUS_TO_BB_MINUS: "BB",
    R.B_PLUS_TO_B_MINUS: "B",
    R.BELOW_B_MINUS: "CCC",
    R.UNRATED: "UNRATED",
}
"""Engine :class:`RatingBucket` -> Table 8-14 category. AAA..AA- spans two categories (AAA 0.5%,
AA 2%); the conservative AA is used unless ``flags['drc_aaa']``. CQG 6 (CCC+ and below) -> CCC."""

DRC_AAA_FLAG: Final[str] = "drc_aaa"

DRC_ZERO_RW: Final[float] = 0.0
"""Para 8.2.184(b)(ii): 0% for central governments, central banks, the para 7.3.46
entities (BIS, IMF, ECB, EU, ESM, EFSF), PSEs or MDBs "that attract a 0% risk weight under the
SA(CR)" (paras 7.3.42-7.3.51). MAS deviation: mandatory; MAR22.7 makes it a national
discretion (the BCBS engine leaves it unexercised)."""

SA_CR_ZERO_RW_SOVEREIGN_RATINGS: Final[frozenset[RatingBucket]] = frozenset({R.AAA_TO_AA_MINUS})
"""Table 7-1 (para 7.3.42): central government / central bank CQG "1" -> 0%."""

DRC_FUND_UNRATED_EQUITY_RW: Final[float] = 0.15
"""Para 8.2.184(b)(iii): equity investment in a fund treated as unrated equity
(para 8.2.165): 15%; LGD 100% (fn 683)."""

DRC_FUND_HY_MANDATE_RW: Final[float] = 1.00
# TODO: VERIFY -- para 8.2.166 / 8.2.184(b)(iv): a fund whose mandate allows primarily high-yield
# or distressed investments takes the effective average RW from filling the mandate from the
# highest Table 8-14 category downward. The mandate limits are not an engine input; the
# conservative placeholder is the highest Table 8-14 weight (Defaulted, 100%).

DRC_SEC_BANKING_BOOK_DIVISOR: Final[float] = 12.5
"""Para 8.2.196(b)(i): securitisation (non-CTP) RW = banking-book RW (paras 7.6.13-
7.6.19 hierarchy, one-year tranche maturity) "divided by 12.5". Settles the BCBS engine's
TODO (MAR22.34 only says "based on"); numerically identical to x 8%."""

DRC_SEC_FAIR_VALUE_CAP: Final[bool] = True
"""Para 8.2.196(b)(ii) [MAR22.34(3)]: DRC of an individual non-derivative
securitisation exposure capped at its fair value."""

DRC_SEC_NONCTP_REGIONS: Final[tuple[str, ...]] = ("ASIA", "EUROPE", "NORTH_AMERICA", "OTHER")
"""Table 8-15 [MAR22.31(2)(b)]: Asia, Europe, North America, all other."""

DRC_SEC_NONCTP_ASSET_CLASSES: Final[tuple[str, ...]] = (
    "ABCP", "AUTO_LOANS_LEASES", "RMBS", "CREDIT_CARDS", "CMBS", "CLO", "CDO_SQUARED",
    "SMALL_BUSINESSES", "STUDENT_LOANS", "OTHER_RETAIL", "OTHER_WHOLESALE",
)
"""Table 8-15 [MAR22.31(2)(a)]: the 11 asset classes per region, in table order."""


def _build_table815() -> dict[str, int]:
    """Table 8-15 bucket numbers: 1 companies, 2-45 = region x asset class, 46 others."""
    out: dict[str, int] = {"COMPANIES": 1}
    n = 2
    for region in DRC_SEC_NONCTP_REGIONS:
        for asset in DRC_SEC_NONCTP_ASSET_CLASSES:
            out[f"{asset}|{region}"] = n
            n += 1
    out["OTHERS"] = n
    return out


DRC_SEC_NONCTP_BUCKET_NUMBER: Final[dict[str, int]] = _build_table815()
"""Table 8-15: 46 buckets -- 1 "Companies (excluding small businesses)", all regions;
2-12 Asia, 13-23 Europe, 24-34 North America, 35-45 all other; 46 "Others" (para 8.2.195(b))."""

DRC_SEC_COMPANIES_BUCKET: Final[str] = "COMPANIES"
DRC_SEC_OTHERS_BUCKET: Final[str] = "OTHERS"

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
"""Engine :class:`SecAssetClass` -> Table 8-15 asset classes; ABCP, CDO-squared, small
businesses, other retail, other wholesale and companies come from flags."""

DRC_CTP_NEGATIVE_BUCKET_WEIGHT: Final[float] = 0.5
"""Para 8.2.209 [MAR22.45]: contribution_b = max(DRC_b, 0) + 0.5 x min(DRC_b, 0);
DRC_CTP = max(sum_b contribution_b, 0) (fn 705 example: 100 - 0.5 x 100 = 50)."""

# =========================================================================
#  RRAO (paras 8.2.210-8.2.218)
# =========================================================================

RRAO_EXOTIC_RW: Final[float] = 0.01
"""Para 8.2.217(a) [MAR23.8(2)(a)]: exotic underlying 1.0%."""

RRAO_OTHER_RW: Final[float] = 0.001
"""Para 8.2.217(b) [MAR23.8(2)(b)]: instruments in para 8.2.210(b)-(f): 0.1%."""

RRAO_FLAG_BACK_TO_BACK: Final[str] = "back_to_back"
"""Para 8.2.214 [MAR23.7]: back-to-back transactions excluded."""

RRAO_FLAG_LISTED_OR_CCP: Final[str] = "listed_or_ccp_eligible"
"""Para 8.2.215 [MAR23.7]: listed / CCP-eligible instruments excluded "despite
paragraph 8.2.210(b)"; exotic-underlying instruments stay in scope."""

RRAO_FLAG_210_C_TO_F: Final[str] = "rrao_8_2_210_c_to_f"
"""Marks an OTHER_RESIDUAL position that is in scope only under para 8.2.210(c)-(f) (behavioural
prepayment, no maturity, no strike/barrier, multiple strikes/barriers). The para 8.2.215
listed/CCP exclusion refers to para 8.2.210(b) only, so such positions are not excluded by it.
MAS deviation: MAR23.4 folds these into "other residual risks"."""

# =========================================================================
#  IMA (Part VIII Division 3)
# =========================================================================

IMA_ES_CONFIDENCE: Final[float] = 0.975
"""Para 8.3.182 [MAR33.3]: 97.5th percentile, one-tailed."""

IMA_BASE_HORIZON_DAYS: Final[int] = 10
"""Para 8.3.184(b) [MAR33.4]: T = 10 days."""

IMA_LH_BUCKETS: Final[tuple[int, ...]] = (10, 20, 40, 60, 120)
"""Table 8-24 [MAR33.4 Table 1]: LH_j for j = 1..5."""

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
    "EQ_REPO_LARGE_CAP": 20,
    "EQ_REPO_SMALL_CAP": 60,
    "EQ_DIVIDENDS_LARGE_CAP": 20,
    "EQ_DIVIDENDS_SMALL_CAP": 60,
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
"""Table 8-25 [MAR33.12 Table 2]. MAS deviations: IR specified currencies are EUR,
USD, GBP, AUD, JPY, SEK, CAD and SGD (fn 772-773, incl. cross-currency basis); equity repo and
dividend rows are listed explicitly (large cap 20, small cap 60)."""

IMA_IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = GIRR_SQRT2_CURRENCIES
"""Table 8-25 row 1: EUR, USD, GBP, AUD, JPY, SEK, CAD and SGD."""

IMA_FX_SPECIFIED_PAIRS: Final[frozenset[str]] = FX_SPECIFIED_PAIRS | frozenset(
    {"EUR/JPY", "EUR/GBP", "EUR/CHF", "JPY/AUD"}
)
"""Table 8-25 [MAR33.12 fn 309]: the para 8.2.140 pairs plus EUR/JPY, EUR/GBP,
EUR/CHF, JPY/AUD and first-order crosses."""

IMA_NMRF_MIN_LH_DAYS: Final[int] = 20
"""Para 8.3.206 [MAR33.16]: NMRF LH = max(Table 8-25 LH, 20 days)."""

IMA_REDUCED_SET_MIN_EXPLANATORY: Final[float] = 0.75
"""Para 8.3.186(e) [MAR33.5(2)(b)]: reduced-set ES >= 75% of full-set ES."""

IMA_IMCC_RHO: Final[float] = 0.5
"""Para 8.3.200(b) [MAR33.15]: IMCC = rho IMCC(C) + (1 - rho) sum IMCC(C_i)."""

IMA_SES_RHO: Final[float] = 0.6
"""Para 8.3.212(d) [MAR33.17]: SES rho = 0.6."""

IMA_MULTIPLIER_BASE: Final[float] = 1.5
"""Para 8.3.242(e) [MAR33.42]: m_c = 1.5 + m_b + m_q."""

IMA_BACKTESTING_ADDON: Final[dict[int, float]] = {
    0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0,
    5: 0.20, 6: 0.26, 7: 0.33, 8: 0.38, 9: 0.42,
    10: 0.50,
}
"""Table 8-22 [MAR32.9 Table 1]: backtesting add-on m_b by exceptions (green 0-4,
amber 5-9, red "10 or more" -> key 10). MAS prints the add-on directly (MAR prints 1.5 + add-on)."""

IMA_GREEN_MAX_EXCEPTIONS: Final[int] = 4
IMA_AMBER_MAX_EXCEPTIONS: Final[int] = 9
"""Table 8-22: green 0-4, amber 5-9, red 10 or more."""

IMA_DESK_BACKTEST_MAX_EXCEPTIONS_99: Final[int] = 12
IMA_DESK_BACKTEST_MAX_EXCEPTIONS_975: Final[int] = 30
"""Para 8.3.164 [MAR32.19]: desk out of IMA with > 12 (99%) or > 30 (97.5%)."""

IMA_PLA_SPEARMAN: Final[tuple[float, float]] = (0.80, 0.70)
IMA_PLA_KS: Final[tuple[float, float]] = (0.09, 0.12)
"""Para 8.3.175 and Table 8-23 [MAR32.42 Table 2]: (amber, red) thresholds."""

IMA_PLA_SURCHARGE_K: Final[float] = 0.5
"""Para 8.3.244(a) [MAR33.45]: k = 0.5 x sum_amber SA_i / sum_{G,A} SA_i."""

# =========================================================================
#  SSA(MR) (Part VIII Division 4, Annex 8E)
# =========================================================================

SSA_SCALING: Final[dict[str, float]] = {"IRR": 1.3, "EQ": 3.5, "COMM": 1.9, "FX": 1.2}
"""Para 8.4.2 [MAR40.2]: (CR_IRR x 1.3) + (CR_EQ x 3.5) + (CR_FX x 1.2) +
(CR_COMM x 1.9)."""

SSA_ELIGIBILITY_RWA_SGD_MN: Final[float] = 200.0
SSA_ELIGIBILITY_RWA_SHARE: Final[float] = 0.02
"""Para 8.1.18(a): the Authority considers whether SSA(MR) market RWA (excl. CVA)
exceeds S$200 million or 2% of total RWA (also (c) G-SIB, (d) IMA use, (e) CTP). MAS deviation:
MAR40.1 sets no numeric screen."""

SSA_GOVT_SPECIFIC: Final[dict[str, float]] = {
    "CQG1": 0.0,
    "CQG2_3_LE_6M": 0.0025,
    "CQG2_3_6M_TO_24M": 0.01,
    "CQG2_3_GT_24M": 0.016,
    "CQG4_5": 0.08,
    "CQG6": 0.12,
    "UNRATED": 0.08,
}
"""Table 8E-1 (Annex 8E) [MAR40.6 Table 1]: "Government" category."""

SSA_QUALIFYING_SPECIFIC: Final[dict[str, float]] = {
    "LE_6M": 0.0025, "6M_TO_24M": 0.01, "GT_24M": 0.016,
}
"""Table 8E-1: "Qualifying" category by residual term to final maturity."""

SSA_OTHER_SPECIFIC: Final[dict[str, float]] = {"CQG4": 0.08, "CQG5_6": 0.12, "UNRATED": 0.08}
"""Table 8E-1: "Others" category."""

SSA_ZERO_SPECIFIC_RISK: Final[float] = 0.0
"""Annex 8E para 1.4: 0% for (a) Singapore Government / MAS securities in SGD funded in
SGD, (b) other CQG <= 3 central governments in domestic currency funded in that currency, (c)
PSEs at 0% under SA(CR) Table 7-3. MAS national treatment (no MAR40 counterpart)."""

SSA_MATURITY_SHORT_YEARS: Final[float] = 0.5
SSA_MATURITY_MEDIUM_YEARS: Final[float] = 2.0
"""Table 8E-1: "6 months or less", "more than 6 and up to and including 24 months"."""

SSA_MATURITY_BANDS: Final[tuple[tuple[float, float, float, float], ...]] = (
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
"""Table 8E-2 [MAR40.26 Table 4]: (upper bound coupon >= 3%, upper bound coupon < 3%,
general risk charge, assumed change in yield), bands 1-13."""

SSA_LOW_COUPON_EXTRA_BANDS: Final[tuple[tuple[float, float, float], ...]] = (
    (20.0, 0.0800, 0.60),
    (math.inf, 0.1250, 0.60),
)
"""Table 8E-2 bands 14-15 (coupon < 3% only): 12-20 years 8.00%, over 20 years 12.50%."""

SSA_LOW_COUPON_THRESHOLD: Final[float] = 0.03
"""Table 8E-2 column headings: "Coupon 3% or more" / "Coupon less than 3%"."""

SSA_VERTICAL_DISALLOWANCE: Final[float] = 0.10
SSA_DURATION_VERTICAL_DISALLOWANCE: Final[float] = 0.05
SSA_HORIZONTAL_WITHIN_ZONE: Final[dict[int, float]] = {1: 0.40, 2: 0.30, 3: 0.30}
SSA_HORIZONTAL_ADJACENT: Final[float] = 0.40
SSA_HORIZONTAL_ZONE1_ZONE3: Final[float] = 1.00
"""Table 8E-4 [MAR40.27-40.28 Table 5]: maturity-band matching 10% (duration 5%);
zone 40% / 30% / 30%; adjacent 40%; non-adjacent 100%."""

SSA_EQUITY_SPECIFIC: Final[float] = 0.08
SSA_EQUITY_QUALIFYING_INDEX_SPECIFIC: Final[float] = 0.0
"""Para 8.4.36(b): specific risk 0% for a qualifying equity index (Annex 8H), 8% for
any other equity, basket or index. MAS deviation: MAR40.43 applies 8% specific risk to all."""

SSA_EQUITY_GENERAL: Final[float] = 0.08
"""Para 8.4.37(c) [MAR40.44]: 8% on the net position per country portfolio."""

SSA_EQUITY_INDEX_ADDON: Final[float] = 0.02
"""Para 8.4.38 [MAR40.47]: +2% on the net position in a qualifying equity index."""

SSA_EQUITY_ARBITRAGE: Final[float] = 0.02
"""Paras 8.4.39-8.4.40 [MAR40.48-40.50]: 2% per side."""

SSA_FX_CHARGE: Final[float] = 0.08
"""Para 8.4.41(e) [MAR40.61]: 8% of the overall net open position."""

SSA_FX_EXEMPT_BUSINESS_SHARE: Final[float] = 1.00
SSA_FX_EXEMPT_NOP_SHARE: Final[float] = 0.02
"""Para 8.4.42 [MAR40.62]: exemption (with approval) if foreign currency business
<= 100% and overall net open position <= 2% of Eligible Total Capital."""

SSA_COMMODITY_SIMPLIFIED_NET: Final[float] = 0.15
SSA_COMMODITY_SIMPLIFIED_GROSS: Final[float] = 0.03
"""Para 8.4.59 [MAR40.72-40.73]: 15% of the net position + 3% of gross."""

SSA_COMMODITY_SPREAD_RATE: Final[float] = 0.015
SSA_COMMODITY_CARRY_RATE: Final[float] = 0.006
SSA_COMMODITY_OUTRIGHT: Final[float] = 0.15
"""Para 8.4.60 [MAR40.69-40.70]: spread 1.5%, carry 0.6%, outright 15%."""

SSA_OPTION_EQUITY_FX_CHARGE: Final[float] = 0.08
SSA_OPTION_COMMODITY_CHARGE: Final[float] = 0.15
"""Para 8.4.67(c)(iii)-(iv) [MAR40.76 fn 344]: currency (and gold) options 8%, commodity options
15%."""

# =========================================================================
#  Deviations from Basel MAR (for documentation and tests)
# =========================================================================

MAS_DEVIATIONS_FROM_MAR: Final[dict[str, str]] = {
    "girr_sqrt2_list": "8.2.92(a)/(c): sqrt(2) reduction mandatory for a fixed list incl. SGD; "
                       "MAR21.44 is a bank discretion for the list plus the domestic reporting "
                       "currency",
    "girr_sqrt2_inflation_xccy": "8.2.92(c): sqrt(2) also applies to the 1.6% inflation and "
                                 "cross-currency basis weights (MAR21.44 ambiguous)",
    "girr_xccy_99_9": "8.2.95: 99.90% between cross-currency basis curves of the same bucket "
                      "(MAR21.49: 0%)",
    "fx_sqrt2_mandatory": "8.2.140: FX sqrt(2) mandatory (MAR21.88: may)",
    "csr_bucket2": "Table 8-3 bucket 2/10 'PSEs, education' (MAR21.51: local government, "
                   "government-backed non-financials, education, public administration)",
    "drc_zero_rw": "8.2.184(b)(ii): 0% DRC RW mandatory for sovereigns/PSEs/MDBs at 0% under "
                   "SA(CR) (MAR22.7: national discretion)",
    "drc_buckets": "8.2.183: companies / central governments, central banks and MDBs / PSEs "
                   "(MAR22.22: corporates / sovereigns / local governments and municipalities)",
    "drc_sec_divisor": "8.2.196(b)(i): sec DRC RW = banking-book RW / 12.5 written into the rule "
                       "(MAR22.34: 'based on')",
    "drc_funds": "8.2.165-8.2.166, 8.2.184(b)(iii)-(iv): funds treated as unrated equity 15%, "
                 "HY/distressed mandates by mandate fill (MAR22: no fund-specific rule)",
    "rrao_listed_scope": "8.2.215: listed/CCP exclusion only for 8.2.210(b) instruments; "
                         "8.2.210(c)-(f) items remain in scope",
    "ima_lh_sgd": "Table 8-25: SGD is an IR specified currency (10 days); equity repo/dividend "
                  "rows listed",
    "ssa_threshold": "8.1.18(a): SSA(MR) eligibility screen S$200m market RWA or 2% of total RWA",
    "ssa_equity_index": "8.4.36(b)(i): 0% specific risk on qualifying equity indices",
    "ssa_zero_specific": "Annex 8E para 1.4: 0% specific risk for SGD Singapore Government / MAS "
                         "paper funded in SGD, domestic-currency CQG<=3 sovereigns, 0% PSEs",
}
"""Material MAS 637 deviations from Basel MAR20-MAR23 / MAR33 / MAR40 (paragraph references)."""
