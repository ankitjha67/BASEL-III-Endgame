"""OSFI CAR 2026 Chapter 9 (Market Risk) -- FRTB regulatory parameters.

Every constant below is transcribed from the text of the OSFI Capital Adequacy Requirements
(CAR) Guideline 2026, Chapter 9 -- Market Risk ("valid until the end of the reporting period on
January 31, 2027"). Citations take the form ``CAR 9.x.y [¶n] [Basel Framework MARxx.yy]``:

* ``9.x.y`` is the CAR section heading;
* ``¶n`` is the OSFI paragraph number. The flattened web text does not print paragraph numbers,
  so they are *derived* from the text's own cross-references, which pin a one-to-one mapping
  within section 9.5: ¶(107+n) = MAR20.n, ¶(112+n) = MAR21.n, ¶(213+n) = MAR22.n and
  ¶(258+n) = MAR23.n (checked against 20 internal cross-references, e.g. "paragraph 163" =
  CSR Table 3 = MAR21.51, "Table 15 in paragraph 237" = MAR22.24, "paragraph 266" = RRAO
  calculation = MAR23.8). For section 9.6 (IMA) the mapping is not consistent, so only the
  section and Basel reference are cited there;
* ``[Basel Framework MARxx.yy]`` is the cross-reference OSFI prints in square brackets at the end
  of each paragraph.

The verbatim transcription of every table is in ``docs/jurisdictions/CA_frtb_reference.md``.

Currency: CAR Ch.1 footnote 6 -- "All dollar values in this guideline are in Canadian dollars".
Thresholds below (large-cap equity, index market cap) are stated in CAD exactly as printed.

Scope: CAR Ch.9 eligibility -- "These requirements apply only to internationally active
institutions"; all D-SIBs "shall meet the requirements of this chapter". CAR 9.1.2.2 [MAR11.7]
offers only the standardized approach (section 9.5) and the IMA (section 9.6); CAR Ch.1
s.1.3.2 [RBC20.9] likewise lists only those two. The Basel simplified standardised approach
(MAR40) is **not** adopted by OSFI -- the MAR40 parameters at the end of this module are
transcribed from the Basel Framework for comparison only (see ``ssa.py``).
"""

from __future__ import annotations

import math
from typing import Final

from src.jurisdictions.frtb_base import CommodityGroup, EquitySector, SecAssetClass, SecTrancheClass

SQRT2: Final[float] = math.sqrt(2.0)

# =========================================================================
#  9.5.1 / 9.5.2.3 -- general structure and correlation scenarios
# =========================================================================

RWA_MULTIPLIER: Final[float] = 12.5
"""CAR 9.5.1.1 ¶108 -- "risk-weighted assets for market risk under the standardized approach are
determined by multiplying the capital requirements ... by 12.5" [MAR20.1]."""

HIGH_CORRELATION_MULTIPLIER: Final[float] = 1.25
"""CAR 9.5.2.3 ¶118(2) -- high scenario: "ρkl and ϒbc ... uniformly multiplied by 1.25, with ρkl
and ϒbc subject to a cap at 100%" [MAR21.6]."""
CORRELATION_CAP: Final[float] = 1.0
"""CAR 9.5.2.3 ¶118(2) -- cap at 100% [MAR21.6]."""
LOW_CORRELATION_SLOPE: Final[float] = 2.0
LOW_CORRELATION_INTERCEPT: Final[float] = 1.0
LOW_CORRELATION_FLOOR_FACTOR: Final[float] = 0.75
"""CAR 9.5.2.3 ¶118(3) -- low scenario: ρ_low = max(2 × ρ − 100%; 75% × ρ) (same for ϒbc)
[MAR21.6]."""

SCENARIOS: Final[tuple[str, ...]] = ("LOW", "MEDIUM", "HIGH")
"""CAR 9.5.2.3 ¶118-119 -- three correlation scenarios; "The sensitivities-based method capital
requirement is the largest capital requirement from the three scenarios" [MAR21.6-21.7]."""

# =========================================================================
#  9.5.2.5 -- Delta GIRR (¶153-162, Tables 1-2)
# =========================================================================

GIRR_TENORS: Final[tuple[float, ...]] = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)
"""CAR 9.5.2.4 ¶120(1) -- GIRR delta tenors "0.25 years, 0.5 years, 1 year, 2 years, 3 years,
5 years, 10 years, 15 years, 20 years and 30 years" [MAR21.8]."""

GIRR_RISK_WEIGHTS: Final[dict[float, float]] = {
    0.25: 0.017, 0.5: 0.017, 1.0: 0.016, 2.0: 0.013, 3.0: 0.012,
    5.0: 0.011, 10.0: 0.011, 15.0: 0.011, 20.0: 0.011, 30.0: 0.011,
}
"""CAR 9.5.2.5 ¶154 Table 1 -- Delta GIRR buckets and risk weights [MAR21.42]."""

GIRR_INFLATION_RW: Final[float] = 0.016
GIRR_XCCY_BASIS_RW: Final[float] = 0.016
"""CAR 9.5.2.5 ¶155 -- "The risk weight for the inflation risk factor and the cross-currency basis
risk factors, respectively, is set at 1.6%" [MAR21.43]."""

GIRR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"EUR", "USD", "GBP", "AUD", "JPY", "SEK", "CAD"}
)
"""CAR 9.5.2.5 ¶156 -- "For EUR, USD, GBP, AUD, JPY, SEK, CAD as well as the domestic reporting
currency of an institution, the above risk weights may, at the discretion of the institution, be
divided by the square root of 2" [MAR21.44]. The reporting currency is added at run time."""
# TODO: VERIFY -- CAR ¶156 says "the above risk weights" directly after ¶155 (inflation and
# cross-currency basis 1.6%); it does not settle whether the sqrt(2) reduction also extends to
# those two risk factors. Conservatively applied to the Table 1 tenor risk weights only.

GIRR_DIFFERENT_CURVE_CORRELATION: Final[float] = 0.999
"""CAR 9.5.2.5 ¶157 -- same bucket, same tenor, different curves: 99.90% [MAR21.45]; ¶159 --
different tenor and different curves: Table 2 value × 99.90%; the 99.90% "also applies to
different inflation curves in the same currency" [MAR21.47]."""

GIRR_TENOR_CORRELATION: Final[dict[tuple[float, float], float]] = {}
"""CAR 9.5.2.5 ¶158 Table 2 -- Delta GIRR correlations within the same bucket, different tenor
and same curve [MAR21.46]. Populated below from the printed matrix (row-major)."""
_GIRR_TABLE2: Final[tuple[tuple[float, ...], ...]] = (
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
for _i, _ti in enumerate(GIRR_TENORS):
    for _j, _tj in enumerate(GIRR_TENORS):
        GIRR_TENOR_CORRELATION[(_ti, _tj)] = _GIRR_TABLE2[_i][_j]

GIRR_TABLE2_THETA: Final[float] = 0.03
GIRR_TABLE2_FLOOR: Final[float] = 0.40
"""CAR 9.5.2.5 footnote 38 -- Table 2 is max[e^(−θ·|Tk−Tl|/min{Tk;Tl}); 40%] with θ = 3%."""

GIRR_INFLATION_YIELD_CORRELATION: Final[float] = 0.40
"""CAR 9.5.2.5 ¶160 -- inflation curve vs a tenor of the yield curve: 40% [MAR21.48]."""
GIRR_XCCY_CORRELATION: Final[float] = 0.0
"""CAR 9.5.2.5 ¶161 -- cross-currency basis curve vs a tenor of the yield curve, the inflation
curve, or another cross-currency basis curve: 0% [MAR21.49]."""
GIRR_GAMMA: Final[float] = 0.50
"""CAR 9.5.2.5 ¶162 -- across GIRR buckets (currencies) ϒbc = 50% [MAR21.50]."""

# =========================================================================
#  9.5.2.5 -- Delta CSR non-securitisation (¶163-169, Tables 3-5)
# =========================================================================

CSR_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""CAR 9.5.2.4 ¶121(1)(b), ¶122, ¶123 -- CSR delta tenors 0.5, 1, 3, 5, 10 years
[MAR21.9-21.11]."""

CSR_NONSEC_BUCKETS: Final[dict[int, tuple[str, str]]] = {
    1: ("IG", "Sovereigns including central banks, multilateral development institutions"),
    2: ("IG", "Local government, government-backed non-financials, education, public "
              "administration"),
    3: ("IG", "Financials including government-backed financials"),
    4: ("IG", "Basic materials, energy, industrials, agriculture, manufacturing, mining and "
              "quarrying"),
    5: ("IG", "Consumer goods and services, transportation and storage, administrative and "
              "support service activities"),
    6: ("IG", "Technology, telecommunications"),
    7: ("IG", "Health care, utilities, professional and technical activities"),
    8: ("IG", "Covered bonds"),
    9: ("HY&NR", "Sovereigns including central banks, multilateral development institutions"),
    10: ("HY&NR", "Local government, government-backed non-financials, education, public "
                  "administration"),
    11: ("HY&NR", "Financials including government-backed financials"),
    12: ("HY&NR", "Basic materials, energy, industrials, agriculture, manufacturing, mining and "
                  "quarrying"),
    13: ("HY&NR", "Consumer goods and services, transportation and storage, administrative and "
                  "support service activities"),
    14: ("HY&NR", "Technology, telecommunications"),
    15: ("HY&NR", "Health care, utilities, professional and technical activities"),
    16: ("N/A", "Other sector"),
    17: ("IG", "Qualified Indices"),
    18: ("HY", "Qualified Indices"),
}
"""CAR 9.5.2.5 ¶163 Table 3 -- Buckets for delta CSR non-securitizations [MAR21.51]."""

CSR_NONSEC_RW: Final[dict[int, float]] = {
    1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015, 8: 0.025,
    9: 0.020, 10: 0.040, 11: 0.120, 12: 0.070, 13: 0.085, 14: 0.055, 15: 0.050, 16: 0.120,
    17: 0.015, 18: 0.050,
}
"""CAR 9.5.2.5 ¶165 Table 4 -- Risk weights for delta CSR non-securitizations [MAR21.53]."""

CSR_COVERED_BOND_AA_RW: Final[float] = 0.015
"""CAR 9.5.2.5 Table 4 footnote 42 -- "For covered bonds that are rated AA- or higher, the
applicable risk weight may at the discretion of the institution be 1.5%"."""

CSR_GSE_MBS_BUCKET: Final[int] = 2
CSR_GSE_MBS_RW: Final[float] = 0.010
"""CAR 9.5.2.5 ¶163 -- "Non-tranched MBS issued by government sponsored-entities (GSEs), such as
Fannie and Freddie, are assigned to bucket 2 ... for CSR with a risk weight of 1.0%"
[MAR21.51]."""

CSR_OTHER_BUCKET: Final[int] = 16
"""CAR 9.5.2.5 ¶164(3) -- issuers not assignable to a sector go to bucket 16 [MAR21.52]."""
CSR_INDEX_BUCKETS: Final[frozenset[int]] = frozenset({17, 18})

CSR_NAME_CORRELATION: Final[float] = 0.35
CSR_TENOR_CORRELATION: Final[float] = 0.65
CSR_BASIS_CORRELATION: Final[float] = 0.999
"""CAR 9.5.2.5 ¶166 -- buckets 1-15: ρ(name) 35%, ρ(tenor) 65%, ρ(basis) 99.90%;
ρkl = ρ(name)·ρ(tenor)·ρ(basis) [MAR21.54]."""
CSR_INDEX_NAME_CORRELATION: Final[float] = 0.80
"""CAR 9.5.2.5 ¶167 -- buckets 17-18: ρ(name) 80% (tenor 65%, basis 99.90%) [MAR21.55]."""

CSR_RATING_GAMMA: Final[float] = 0.50
"""CAR 9.5.2.5 ¶169 -- ϒbc(rating) = 50% where both buckets are in 1-15 with a different rating
category (IG vs HY/NR), else 1; ϒbc = ϒbc(rating)·ϒbc(sector) [MAR21.57]."""

CSR_SECTOR_GROUP: Final[dict[int, str]] = {
    1: "1/9", 9: "1/9", 2: "2/10", 10: "2/10", 3: "3/11", 11: "3/11", 4: "4/12", 12: "4/12",
    5: "5/13", 13: "5/13", 6: "6/14", 14: "6/14", 7: "7/15", 15: "7/15", 8: "8", 16: "16",
    17: "17", 18: "18",
}
"""CAR 9.5.2.5 ¶169 Table 5 -- sector groups (row/column headings)."""

_CSR_TABLE5_ORDER: Final[tuple[str, ...]] = (
    "1/9", "2/10", "3/11", "4/12", "5/13", "6/14", "7/15", "8", "16", "17", "18",
)
_CSR_TABLE5_UPPER: Final[tuple[tuple[float, ...], ...]] = (
    (0.75, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.00, 0.45, 0.45),  # 1/9 vs 2/10 .. 18
    (0.05, 0.15, 0.20, 0.15, 0.10, 0.10, 0.00, 0.45, 0.45),        # 2/10 vs 3/11 .. 18
    (0.05, 0.15, 0.20, 0.05, 0.20, 0.00, 0.45, 0.45),              # 3/11
    (0.20, 0.25, 0.05, 0.05, 0.00, 0.45, 0.45),                    # 4/12
    (0.25, 0.05, 0.15, 0.00, 0.45, 0.45),                          # 5/13
    (0.05, 0.20, 0.00, 0.45, 0.45),                                # 6/14
    (0.05, 0.00, 0.45, 0.45),                                      # 7/15
    (0.00, 0.45, 0.45),                                            # 8
    (0.00, 0.00),                                                  # 16
    (0.75,),                                                       # 17 vs 18
)
CSR_SECTOR_GAMMA: Final[dict[tuple[str, str], float]] = {}
"""CAR 9.5.2.5 ¶169 Table 5 -- ϒbc(sector) where buckets do not belong to the same sector
[MAR21.57]; 1 for the same sector. Symmetric dict built from the printed upper triangle."""
for _r, _row in enumerate(_CSR_TABLE5_UPPER):
    for _c, _val in enumerate(_row):
        _a, _b = _CSR_TABLE5_ORDER[_r], _CSR_TABLE5_ORDER[_r + 1 + _c]
        CSR_SECTOR_GAMMA[(_a, _b)] = _val
        CSR_SECTOR_GAMMA[(_b, _a)] = _val

# =========================================================================
#  9.5.2.5 -- Delta CSR securitisation CTP (¶170-173, Table 6)
# =========================================================================

CSR_CTP_RW: Final[dict[int, float]] = {
    1: 0.04, 2: 0.04, 3: 0.08, 4: 0.05, 5: 0.04, 6: 0.03, 7: 0.02, 8: 0.06,
    9: 0.13, 10: 0.13, 11: 0.16, 12: 0.10, 13: 0.12, 14: 0.12, 15: 0.12, 16: 0.13,
}
"""CAR 9.5.2.5 ¶171 Table 6 -- Risk weights for sensitivities to CSR arising from the CTP
(buckets 1-16; the index buckets 17-18 do not apply, ¶170(1)) [MAR21.58-21.59]."""
CSR_CTP_BASIS_CORRELATION: Final[float] = 0.990
"""CAR 9.5.2.5 ¶172 -- CTP ρ(basis) "equal to 1 if the two sensitivities are related to same
curves, and 99.00% otherwise"; ρ(name), ρ(tenor) as for non-sec [MAR21.60]. ¶173 -- ϒbc
identical to CSR non-securitization [MAR21.61]."""

# =========================================================================
#  9.5.2.5 -- Delta CSR securitisation non-CTP (¶174-183, Tables 7-8)
# =========================================================================

SEC_NONCTP_SECTOR_ORDER: Final[tuple[SecAssetClass, ...]] = (
    SecAssetClass.RMBS_PRIME, SecAssetClass.RMBS_MIDPRIME, SecAssetClass.RMBS_SUBPRIME,
    SecAssetClass.CMBS, SecAssetClass.ABS_STUDENT_LOANS, SecAssetClass.ABS_CREDIT_CARDS,
    SecAssetClass.ABS_AUTO, SecAssetClass.CLO_NON_CTP,
)
"""CAR 9.5.2.5 ¶174 Table 7 -- sector order within each credit-quality block [MAR21.62]."""
SEC_NONCTP_TRANCHE_OFFSET: Final[dict[SecTrancheClass, int]] = {
    SecTrancheClass.SENIOR_IG: 0, SecTrancheClass.NON_SENIOR_IG: 8, SecTrancheClass.HY_NR: 16,
}
"""CAR ¶174 Table 7 -- buckets 1-8 senior IG, 9-16 non-senior IG, 17-24 high yield & non-rated,
25 other sector [MAR21.62]."""
SEC_NONCTP_OTHER_BUCKET: Final[int] = 25

SEC_NONCTP_SENIOR_IG_RW: Final[dict[int, float]] = {
    1: 0.009, 2: 0.015, 3: 0.020, 4: 0.020, 5: 0.008, 6: 0.012, 7: 0.012, 8: 0.014,
}
"""CAR 9.5.2.5 ¶176 Table 8 -- risk weights for buckets 1 to 8 (senior IG) [MAR21.64]."""
SEC_NONCTP_NON_SENIOR_IG_SCALAR: Final[float] = 1.25
"""CAR ¶177 -- buckets 9-16 = buckets 1-8 × 1.25 [MAR21.65]."""
SEC_NONCTP_HY_NR_SCALAR: Final[float] = 1.75
"""CAR ¶178 -- buckets 17-24 = buckets 1-8 × 1.75 [MAR21.66]."""
SEC_NONCTP_OTHER_RW: Final[float] = 0.035
"""CAR ¶179 -- "The risk weight for bucket 25 is set at 3.5%" [MAR21.67]."""


def _sec_nonctp_rw_table() -> dict[int, float]:
    """Build buckets 1-25 from CAR ¶176-179 [MAR21.64-21.67]."""
    table: dict[int, float] = dict(SEC_NONCTP_SENIOR_IG_RW)
    for b, rw in SEC_NONCTP_SENIOR_IG_RW.items():
        table[b + 8] = rw * SEC_NONCTP_NON_SENIOR_IG_SCALAR
        table[b + 16] = rw * SEC_NONCTP_HY_NR_SCALAR
    table[SEC_NONCTP_OTHER_BUCKET] = SEC_NONCTP_OTHER_RW
    return table


SEC_NONCTP_RW: Final[dict[int, float]] = _sec_nonctp_rw_table()
"""CAR ¶176-179 Table 8 and scalars -- all 25 non-CTP risk weights [MAR21.64-21.67]."""

SEC_NONCTP_TRANCHE_CORRELATION: Final[float] = 0.40
SEC_NONCTP_TENOR_CORRELATION: Final[float] = 0.80
SEC_NONCTP_BASIS_CORRELATION: Final[float] = 0.999
"""CAR 9.5.2.5 ¶180 -- ρ(tranche) 1 for the same tranche (more than 80% overlap in notional
terms) else 40%; ρ(tenor) 80%; ρ(basis) 99.90% [MAR21.68]."""
SEC_NONCTP_GAMMA: Final[float] = 0.0
"""CAR 9.5.2.5 ¶182 -- ϒbc = 0% across buckets 1-24 [MAR21.70]; ¶183 -- bucket 25 is added to
the aggregate of buckets 1-24 with no diversification [MAR21.71]."""

# =========================================================================
#  9.5.2.5 -- Delta equity (¶184-192, Tables 9-10)
# =========================================================================

EQUITY_LARGE_CAP_THRESHOLD_CAD: Final[float] = 2.5e9
"""CAR 9.5.2.5 ¶186 -- "Large market cap is defined as a market capitalization equal to or
greater than CAD 2.5 billion" [MAR21.74 -- USD 2 billion in the Basel text]."""
EQUITY_INDEX_MIN_MARKET_CAP_CAD: Final[float] = 50e9
"""CAR 9.5.2.4 ¶143(5) -- no-look-through equity index: "total market capitalization of all the
constituents of the index is no less than CAD $50 billion" [MAR21.31 -- USD 40 billion]."""
INDEX_MIN_CONSTITUENTS: Final[int] = 20
INDEX_MAX_SINGLE_WEIGHT: Final[float] = 0.25
INDEX_TOP_DECILE_MAX_WEIGHT: Final[float] = 0.60
"""CAR ¶143(2)-(4) -- at least 20 constituents; no constituent > 25%; largest 10% of
constituents < 60% [MAR21.31]."""
INDEX_SECTOR_CONCENTRATION: Final[float] = 0.75
"""CAR ¶145 -- more than 75% of constituents in one sector bucket -> that sector bucket; equity
index -> bucket 12 if at least 75% large cap and advanced economy; credit index -> bucket 17 if
at least 75% IG [MAR21.33]."""

ADVANCED_ECONOMIES: Final[str] = (
    "Canada, the United States, Mexico, the euro area, the non-euro area western European "
    "countries (the United Kingdom, Norway, Sweden, Denmark and Switzerland), Japan, Oceania "
    "(Australia and New Zealand), Singapore and Hong Kong SAR"
)
"""CAR 9.5.2.5 ¶187 -- the advanced economies [MAR21.75]."""

EQUITY_SECTOR_OFFSET: Final[dict[EquitySector, int]] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 1,
    EquitySector.TELECOM_INDUSTRIALS: 2,
    EquitySector.MATERIALS_ENERGY: 3,
    EquitySector.FINANCIALS_REALESTATE_TECH: 4,
}
"""CAR 9.5.2.5 ¶184 Table 9 -- sector order 1-4 (EM large cap) / 5-8 (AE large cap)
[MAR21.72]."""
EQUITY_SMALL_CAP_EM_BUCKET: Final[int] = 9
EQUITY_SMALL_CAP_AE_BUCKET: Final[int] = 10
EQUITY_OTHER_BUCKET: Final[int] = 11
EQUITY_INDEX_LARGE_AE_BUCKET: Final[int] = 12
EQUITY_INDEX_OTHER_BUCKET: Final[int] = 13
"""CAR ¶184 Table 9 -- 9 small/EM, 10 small/AE, 11 other sector, 12 large-cap advanced-economy
indices, 13 other equity indices [MAR21.72]."""

EQUITY_SPOT_RW: Final[dict[int, float]] = {
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55, 5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,
    9: 0.70, 10: 0.50, 11: 0.70, 12: 0.15, 13: 0.25,
}
EQUITY_REPO_RW: Final[dict[int, float]] = {
    1: 0.0055, 2: 0.0060, 3: 0.0045, 4: 0.0055, 5: 0.0030, 6: 0.0035, 7: 0.0040, 8: 0.0050,
    9: 0.0070, 10: 0.0050, 11: 0.0070, 12: 0.0015, 13: 0.0025,
}
"""CAR 9.5.2.5 ¶189 Table 10 -- Risk weights for equity spot price and equity repo rate
[MAR21.77]."""

EQUITY_SPOT_REPO_SAME_NAME_CORRELATION: Final[float] = 0.999
"""CAR ¶190(1) -- spot vs repo of the same issuer: 99.90%; ¶190(4) -- spot vs repo of different
issuers: the (2)(a)-(e) value × 99.90% [MAR21.78]."""
EQUITY_INTRA_BUCKET_CORRELATION: Final[dict[int, float]] = {
    1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15,
    5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25,
    9: 0.075, 10: 0.125, 12: 0.80, 13: 0.80,
}
"""CAR 9.5.2.5 ¶190(2)(a)-(e) -- 15% large/EM (1-4), 25% large/AE (5-8), 7.5% small/EM (9),
12.5% small/AE (10), 80% index buckets (12, 13); ¶190(3) same for repo-repo [MAR21.78]."""

EQUITY_GAMMA_SECTOR: Final[float] = 0.15
EQUITY_GAMMA_OTHER_BUCKET: Final[float] = 0.0
EQUITY_GAMMA_INDICES: Final[float] = 0.75
EQUITY_GAMMA_OTHERWISE: Final[float] = 0.45
"""CAR 9.5.2.5 ¶192 -- ϒbc 15% if both in 1-10; 0% if either is 11; 75% for 12 vs 13; 45%
otherwise [MAR21.80]."""

# =========================================================================
#  9.5.2.5 -- Delta commodity (¶193-197, Tables 11-12)
# =========================================================================

COMMODITY_TENORS: Final[tuple[float, ...]] = (
    0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0,
)
"""CAR 9.5.2.4 ¶125(1)(b) -- commodity delta tenors 0 to 30 years [MAR21.13]."""

COMMODITY_BUCKET_OF: Final[dict[CommodityGroup, int]] = {
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
"""CAR 9.5.2.5 ¶194 Table 11 -- delta commodity buckets [MAR21.82]."""
COMMODITY_OTHER_BUCKET: Final[int] = 11

COMMODITY_RW: Final[dict[int, float]] = {
    1: 0.30, 2: 0.35, 3: 0.60, 4: 0.80, 5: 0.40, 6: 0.45, 7: 0.20, 8: 0.35, 9: 0.25,
    10: 0.35, 11: 0.50,
}
"""CAR 9.5.2.5 ¶194 Table 11 -- delta commodity risk weights [MAR21.82]."""

COMMODITY_CTY_CORRELATION: Final[dict[int, float]] = {
    1: 0.55, 2: 0.95, 3: 0.40, 4: 0.80, 5: 0.60, 6: 0.65, 7: 0.55, 8: 0.45, 9: 0.15,
    10: 0.40, 11: 0.15,
}
"""CAR 9.5.2.5 ¶195 Table 12 -- ρkl(cty) intra-bucket correlations [MAR21.83]."""
COMMODITY_TENOR_CORRELATION: Final[float] = 0.99
COMMODITY_BASIS_CORRELATION: Final[float] = 0.999
"""CAR ¶195 -- ρ(tenor) 99.00%; ρ(basis) (delivery location) 99.90%;
ρkl = ρ(cty)·ρ(tenor)·ρ(basis) [MAR21.83]."""
COMMODITY_GAMMA: Final[float] = 0.20
COMMODITY_GAMMA_OTHER: Final[float] = 0.0
"""CAR 9.5.2.5 ¶197 -- ϒbc 20% within buckets 1-10; 0% if either bucket is 11 [MAR21.85]."""

# =========================================================================
#  9.5.2.5 -- Delta FX (¶198-201)
# =========================================================================

FX_RW: Final[float] = 0.15
"""CAR 9.5.2.5 ¶199 -- "A unique relative risk weight equal to 15% applies to all the FX
sensitivities" [MAR21.87]."""
FX_SPECIFIED_PAIR_CURRENCIES: Final[frozenset[str]] = frozenset({
    "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "MXN", "CNY", "NZD", "RUB", "HKD", "SGD",
    "TRY", "KRW", "SEK", "ZAR", "INR", "NOK", "BRL",
})
"""CAR 9.5.2.5 ¶200 -- specified pairs USD/EUR, USD/JPY, USD/GBP, USD/AUD, USD/CAD, USD/CHF,
USD/MXN, USD/CNY, USD/NZD, USD/RUB, USD/HKD, USD/SGD, USD/TRY, USD/KRW, USD/SEK, USD/ZAR,
USD/INR, USD/NOK, USD/BRL "and for currency pairs forming first-order crosses across these
specified currency pairs" -> RW may be divided by sqrt(2) [MAR21.88]."""
FX_GAMMA: Final[float] = 0.60
"""CAR 9.5.2.5 ¶201 -- ϒbc uniformly 60% [MAR21.89]."""
FX_CURVATURE_SCALAR: Final[float] = 1.5
"""CAR 9.5.2.7 ¶210 -- for FX options not referencing the reporting (or base) currency, CVR+
and CVR− may be divided by 1.5 [MAR21.98]."""

# =========================================================================
#  9.5.2.6 -- Vega (¶202-207, Table 13, footnote 47)
# =========================================================================

VEGA_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""CAR 9.5.2.4 ¶120(2), 121(2), 122(3), 123(3), 124(2), 125(2), 126(2) -- vega option-maturity
tenors (and GIRR underlying residual maturities) 0.5, 1, 3, 5, 10 years [MAR21.8-21.14]."""

VEGA_RW_SIGMA: Final[float] = 0.55
"""CAR 9.5.2.6 footnote 47 -- RWk = min[RWσ·sqrt(LH_risk class / 10); 100%], RWσ = 55%."""
VEGA_LIQUIDITY_HORIZON: Final[dict[str, int]] = {
    "GIRR": 60, "CSR_NONSEC": 120, "CSR_SEC_CTP": 120, "CSR_SEC_NONCTP": 120,
    "EQUITY_LARGE_CAP_AND_INDICES": 20, "EQUITY_SMALL_CAP_AND_OTHER": 60,
    "COMMODITY": 120, "FX": 40,
}
"""CAR 9.5.2.6 ¶204 Table 13 -- regulatory liquidity horizon LH_risk class [MAR21.92]."""
VEGA_RW: Final[dict[str, float]] = {
    "GIRR": 1.0, "CSR_NONSEC": 1.0, "CSR_SEC_CTP": 1.0, "CSR_SEC_NONCTP": 1.0,
    "EQUITY_LARGE_CAP_AND_INDICES": 0.7778, "EQUITY_SMALL_CAP_AND_OTHER": 1.0,
    "COMMODITY": 1.0, "FX": 1.0,
}
"""CAR 9.5.2.6 ¶204 Table 13 -- vega risk weights as printed (77.78% = 55%·sqrt(2) rounded)
[MAR21.92]. Large-cap = equity buckets 1-8 and indices 12-13; small cap / other = 9, 10, 11."""

VEGA_ALPHA: Final[float] = 0.01
"""CAR 9.5.2.6 ¶205 -- ρ(option maturity) = e^(−α·|Tk−Tl|/min{Tk;Tl}), α = 1%; same for the
underlying maturity (GIRR); ρkl = min[ρ(option maturity)·ρ(underlying maturity); 1]
[MAR21.93]; ¶206 -- non-GIRR: min[ρ(DELTA)·ρ(option maturity); 1] [MAR21.94]."""

# =========================================================================
#  9.5.2.7 -- Curvature (¶208-213)
# =========================================================================

CURVATURE_CORRELATION_POWER: Final[int] = 2
"""CAR 9.5.2.7 ¶212-213 -- curvature ρkl and ϒbc are the squares of the delta parameters
(e.g. GIRR 50%² = 25%); high/low scenarios apply to the squared values [MAR21.100-21.101]."""

# =========================================================================
#  9.5.3 -- Default risk capital (¶214-258, Tables 14-15)
# =========================================================================

DRC_LGD_EQUITY: Final[float] = 1.00
DRC_LGD_NON_SENIOR: Final[float] = 1.00
DRC_LGD_SENIOR: Final[float] = 0.75
DRC_LGD_COVERED_BOND: Final[float] = 0.25
"""CAR 9.5.3.4 ¶225 -- equity and non-senior debt 100%; senior debt 75%; covered bonds 25%;
no LGD multiplication where the price is not linked to the recovery rate; non-tranched GSE MBS
75% unless they qualify as covered bonds [MAR22.12]."""

DRC_CAPITAL_HORIZON_YEARS: Final[float] = 1.0
DRC_MATURITY_FLOOR_YEARS: Final[float] = 0.25
"""CAR 9.5.3.4 ¶228 -- JTD of exposures under one year scaled by a fraction of a year, none at
one year or more [MAR22.15]; ¶231 -- weighting floored at one-fourth (three months)
[MAR22.18]; ¶229 -- cash equities assigned either more than one year or three months
[MAR22.16]."""
DRC_TRS_HEDGE_MISMATCH_CAP_DAYS: Final[int] = 40
"""CAR 9.5.3.4 ¶233 -- IG bond or large-cap equity (CAD 6.25 billion, footnote 53) hedging a TRS,
or a bond forward hedging a Level 1 HQLA: "the mismatch applied between long and short position
mismatches is capped at 40 days" (OSFI addition to MAR22.20). Not applied automatically -- see
``drc.py``."""
DRC_TRS_LARGE_CAP_THRESHOLD_CAD: Final[float] = 6.25e9
"""CAR 9.5.3.4 footnote 53 -- "Large cap refers to the shares of a company with a market
capitalization higher than CAD $6.25 billion"."""

DRC_NONSEC_BUCKETS: Final[tuple[str, ...]] = (
    "corporates", "sovereigns", "local governments and municipalities",
)
"""CAR 9.5.3.4 ¶235 -- three non-securitisation buckets [MAR22.22]."""

DRC_RW_BY_CATEGORY: Final[dict[str, float]] = {
    "AAA": 0.005, "AA": 0.02, "A": 0.03, "BBB": 0.06, "BB": 0.15, "B": 0.30, "CCC": 0.50,
    "Unrated": 0.15, "Defaulted": 1.00,
}
"""CAR 9.5.3.4 ¶237 Table 15 -- Default risk weights for non-securitizations by credit quality
category [MAR22.24]."""

DRC_RW_CANADA_US_MDB_ZERO: Final[float] = 0.0
"""CAR 9.5.3.3 ¶220 -- Canadian sovereign, central bank and Canadian PSEs subject to a 0% RW in
CAR Chapter 4; US sovereign, central bank and US PSEs assigned 0% by US regulators; MDBs at 0%
in CAR Chapter 4 -> default risk weight 0% [MAR22.7 national discretion]. ¶237 -- provincial
and territorial governments and their agents are treated as the Government of Canada."""
DRC_RW_OTHER_IG_SOVEREIGN_LOCAL: Final[float] = 0.005
"""CAR 9.5.3.3 ¶220 -- other IG sovereigns assigned 0% by their national authority: 0.5%,
"provided the institution has a local presence (subsidiary or branch) in the country of the
sovereign exposure and has funded the exposure in the local currency" [MAR22.7]."""

DRC_SEC_RW_CONVERSION: Final[float] = 0.08
"""Banking-book securitisation RW (Chapter 6, one-year maturity) -> DRC default risk weight.
CAR 9.5.3.5 ¶247(1) says the DRC risk weights "are based on the corresponding risk weights for
banking book instruments"; the 8% factor is the RWA-to-capital conversion (the inverse of the
12.5 in ¶108 / CAR Ch.1)."""
# TODO: VERIFY -- the 8% conversion is not printed in CAR ¶247 / ¶255 (nor in MAR22.34/22.42);
# it is inferred from RWA = 12.5 × capital. Same treatment as the US ERBA engine (CLAUDE.md).
DRC_SEC_MISSING_BB_RW: Final[float] = 12.5
"""Conservative placeholder when no banking-book securitisation RW is supplied: 1,250%
(-> 100% DRC weight after the 8% conversion)."""
DRC_SEC_FAIR_VALUE_CAP: Final[float] = 1.0
"""CAR 9.5.3.5 ¶247(3) -- capital for an individual cash securitisation position "can be capped at
the fair value of the transaction" (JTD = market value, so the effective weight is capped at
100%) [MAR22.34]."""

DRC_SEC_NONCTP_ASSET_CLASSES: Final[tuple[str, ...]] = (
    "asset-backed commercial paper", "auto loans/leases", "residential MBS", "credit cards",
    "commercial MBS", "collateralized loan obligations", "CDO-squared",
    "small and medium enterprises", "student loans", "other retail", "other wholesale",
)
DRC_SEC_NONCTP_REGIONS: Final[tuple[str, ...]] = ("Asia", "Europe", "North America", "all other")
"""CAR 9.5.3.5 ¶244 -- buckets: corporates (all regions); other buckets by 11 asset classes × 4
regions [MAR22.31]; ¶245 -- unassignable exposures go to the "other bucket" [MAR22.32]."""

DRC_CTP_NEGATIVE_BUCKET_WEIGHT: Final[float] = 0.5
"""CAR 9.5.3.6 ¶258 -- DRC_CTP = max[Σb(max[DRCb, 0] + 0.5 × min[DRCb, 0]), 0] [MAR22.45]."""

# =========================================================================
#  9.5.4 -- Residual risk add-on (¶259-266)
# =========================================================================

RRAO_EXOTIC_RW: Final[float] = 0.010
RRAO_OTHER_RW: Final[float] = 0.001
"""CAR 9.5.4.3 ¶266 -- "The risk weight for instruments with an exotic underlying ... is 1.0%"; "The
risk weight for instruments bearing other residual risks ... is 0.1%" [MAR23.8]."""

# =========================================================================
#  9.6 -- Internal models approach (scalars)
# =========================================================================

IMA_ES_CONFIDENCE: Final[float] = 0.975
"""CAR 9.6.4.1 -- "an institution must use a 97.5th percentile, one-tailed confidence level"
[MAR33.3]."""
IMA_BASE_HORIZON_DAYS: Final[int] = 10
IMA_LIQUIDITY_HORIZON_LADDER: Final[tuple[int, ...]] = (10, 20, 40, 60, 120)
"""CAR 9.6.4.1 Table 19 -- LHj, j = 1..5: 10, 20, 40, 60, 120 days; base horizon T = 10 days;
ES = sqrt(ES_T(P)² + Σ_{j≥2}(ES_T(P,j)·sqrt((LHj − LHj−1)/T))²) [MAR33.4]."""
IMA_REDUCED_SET_MIN_EXPLANATION: Final[float] = 0.75
"""CAR 9.6.4.1 -- reduced set must explain at least 75% of the full ES model [MAR33.5]."""

IMA_LIQUIDITY_HORIZONS: Final[dict[str, int]] = {
    "Interest rate: specified currencies (EUR, USD, GBP, AUD, JPY, SEK, CAD, domestic)": 10,
    "Interest rate: unspecified currencies": 20,
    "Interest rate: volatility": 60,
    "Interest rate: other types": 60,
    "Credit spread: sovereign (IG)": 20,
    "Credit spread: sovereign (HY)": 40,
    "Credit spread: corporate (IG)": 40,
    "Credit spread: corporate (HY)": 60,
    "Credit spread: volatility": 120,
    "Credit spread: other types": 120,
    "Equity price (large cap)": 10,
    "Equity price (small cap)": 20,
    "Equity price (large cap): volatility": 20,
    "Equity price (small cap): volatility": 60,
    "Equity: other types": 60,
    "FX rate: specified currency pairs": 10,
    "FX rate: currency pairs": 20,
    "FX: volatility": 40,
    "FX: other types": 40,
    "Energy and carbon emissions trading price": 20,
    "Precious metals and non-ferrous metals price": 20,
    "Other commodities price": 60,
    "Energy and carbon emissions trading price: volatility": 60,
    "Precious metals and non-ferrous metals price: volatility": 60,
    "Other commodities price: volatility": 120,
    "Commodity: other types": 120,
}
"""CAR 9.6.4.1 Table 20 -- Liquidity horizon n by risk factor category [MAR33.12]; equity
large-cap repo/dividend 20 days, other equity repo/dividend 60 days."""

IMA_MULTIPLIER_BASE: Final[float] = 1.5
"""CAR 9.6.4.6 -- "The multiplication factor mc is fixed at 1.5 unless it is set at a higher level
by OSFI" [MAR33.42]; C_A = max{IMCC_t−1 + SES_t−1; mc·IMCC_avg + SES_avg} [MAR33.41]."""
IMA_BACKTESTING_MULTIPLIER: Final[dict[int, float]] = {
    0: 1.50, 1: 1.50, 2: 1.50, 3: 1.50, 4: 1.50, 5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88,
    9: 1.92, 10: 2.00,
}
"""CAR 9.6.3.1 Table 17 -- backtesting-dependent multiplier by number of exceptions (10 or more
-> 2.00; green 0-4, amber 5-9, red 10+) [MAR32.9]."""
IMA_BACKTESTING_ADDONS: Final[dict[int, float]] = {
    k: round(v - IMA_MULTIPLIER_BASE, 2) for k, v in IMA_BACKTESTING_MULTIPLIER.items()
}
"""Plus factor = Table 17 multiplier − 1.5 (0 to 0.5, CAR 9.6.4.6 [MAR33.42])."""
IMA_BACKTESTING_AMBER_START: Final[int] = 5
IMA_BACKTESTING_RED_START: Final[int] = 10
"""CAR 9.6.3.1 Table 17 and 9.6.5.2 Table 22 -- amber from 5, red from 10 exceptions (250
observations) [MAR32.9, MAR99.16]."""
IMA_DESK_MAX_EXCEPTIONS_99: Final[int] = 12
IMA_DESK_MAX_EXCEPTIONS_975: Final[int] = 30
"""CAR 9.6.3.1 -- desk falls back to the SA with "more than 12 exceptions at the 99th percentile
or 30 exceptions at the 97.5th percentile" [MAR32.19]."""

IMA_PLA_SPEARMAN_GREEN: Final[float] = 0.80
IMA_PLA_SPEARMAN_RED: Final[float] = 0.70
IMA_PLA_KS_GREEN: Final[float] = 0.09
IMA_PLA_KS_RED: Final[float] = 0.12
"""CAR 9.6.3.2 Table 18 -- PLA green: Spearman > 0.80 and KS < 0.09 (p = 0.264); red: Spearman
< 0.70 or KS > 0.12 (p = 0.055); amber otherwise [MAR32.42]."""

IMA_IMCC_RHO: Final[float] = 0.5
"""CAR 9.6.4.2 -- "Rho (ρ) is the relative weight assigned to the institution's internal model. The
value of ρ is 0.5"; IMCC = ρ·IMCC(C) + (1 − ρ)·Σ IMCC(Ci) [MAR33.15]."""
IMA_SES_RHO: Final[float] = 0.6
"""CAR 9.6.4.3 -- "Rho (ρ) is equal to 0.6" in the SES aggregation [MAR33.17]."""
IMA_NMRF_MIN_LIQUIDITY_HORIZON: Final[int] = 20
"""CAR 9.6.4.3 -- NMRF stress-scenario LH = max(Table 20 LH, 20 days) [MAR33.16]."""
IMA_PLA_SURCHARGE_K: Final[float] = 0.5
"""CAR 9.6.4.6 -- k = 0.5 × Σ_{i∈A} SA_i / Σ_{i∈G,A} SA_i; capital surcharge =
k·max{0, SA_G,A − IMA_G,A} [MAR33.45]."""

# =========================================================================
#  Basel MAR40 simplified standardised approach -- NOT ADOPTED BY OSFI (comparison only)
# =========================================================================

SSA_PERMITTED_UNDER_CAR: Final[bool] = False
"""CAR 9.1.2.2 [MAR11.7] and Ch.1 s.1.3.2 [RBC20.9]: only the standardized approach (9.5) and
the IMA (9.6). The MAR40 values below are Basel Framework text, not OSFI text."""

SSA_SCALING_FACTORS: Final[dict[str, float]] = {
    "IRR": 1.30, "EQ": 3.50, "COMM": 1.90, "FX": 1.20,
}
"""Basel Framework MAR40.2 -- SF_IRR 1.30, SF_EQ 3.50, SF_COMM 1.90, SF_FX 1.20; capital =
CR_IRR·SF_IRR + CR_EQ·SF_EQ + CR_FX·SF_FX + CR_COMM·SF_COMM (formula rendered from the PDF,
p.688; the extracted text loses the symbols)."""

SSA_SPECIFIC_RISK_QUALIFYING: Final[tuple[tuple[float, float], ...]] = (
    (0.5, 0.0025), (2.0, 0.0100), (math.inf, 0.0160),
)
"""Basel MAR40.6 Table 1 -- government A+ to BBB− and qualifying: 0.25% (residual maturity
<= 6 months), 1.00% (> 6 and <= 24 months), 1.60% (> 24 months)."""
SSA_SPECIFIC_RISK_GOV_AAA_AA: Final[float] = 0.0
SSA_SPECIFIC_RISK_8PCT: Final[float] = 0.08
SSA_SPECIFIC_RISK_12PCT: Final[float] = 0.12
"""Basel MAR40.6 Table 1 -- government AAA to AA− 0%; government BB+ to B− 8%, below B− 12%,
unrated 8%; other BB+ to BB− 8%, below BB− 12%, unrated 8%."""

SSA_MATURITY_BANDS: Final[tuple[tuple[float, float, float, float, int], ...]] = (
    # (upper bound coupon >= 3%, upper bound coupon < 3%, risk weight, assumed yield change, zone)
    (1 / 12, 1 / 12, 0.0000, 1.00, 1),
    (0.25, 0.25, 0.0020, 1.00, 1),
    (0.5, 0.5, 0.0040, 1.00, 1),
    (1.0, 1.0, 0.0070, 1.00, 1),
    (2.0, 1.9, 0.0125, 0.90, 2),
    (3.0, 2.8, 0.0175, 0.80, 2),
    (4.0, 3.6, 0.0225, 0.75, 2),
    (5.0, 4.3, 0.0275, 0.75, 3),
    (7.0, 5.7, 0.0325, 0.70, 3),
    (10.0, 7.3, 0.0375, 0.65, 3),
    (15.0, 9.3, 0.0450, 0.60, 3),
    (20.0, 10.6, 0.0525, 0.60, 3),
    (math.inf, 12.0, 0.0600, 0.60, 3),
)
"""Basel MAR40.26 Table 4 -- maturity method time bands and weights (13 bands for coupon >= 3%);
zones per MAR40.28(1) and Table 5."""
SSA_LOW_COUPON_EXTRA_BANDS: Final[tuple[tuple[float, float, float, int], ...]] = (
    (20.0, 0.0800, 0.60, 3),
    (math.inf, 0.1250, 0.60, 3),
)
"""Basel MAR40.26 Table 4 -- coupon < 3% bands "12 to 20 years" 8.00% and "Over 20 years"
12.50% (15 bands in total for low-coupon instruments)."""
SSA_LOW_COUPON_THRESHOLD: Final[float] = 0.03
SSA_VERTICAL_DISALLOWANCE: Final[float] = 0.10
"""Basel MAR40.27 -- 10% on the smaller of the offsetting weighted positions in a band."""
SSA_HORIZONTAL_WITHIN_ZONE: Final[dict[int, float]] = {1: 0.40, 2: 0.30, 3: 0.30}
SSA_HORIZONTAL_ADJACENT: Final[float] = 0.40
SSA_HORIZONTAL_ZONE1_ZONE3: Final[float] = 1.00
"""Basel MAR40.28 Table 5 -- horizontal disallowances: within zone 1 40%, zones 2 and 3 30%;
between adjacent zones 40%; between zones 1 and 3 100%."""
SSA_NET_POSITION_CHARGE: Final[float] = 1.00
"""Basel MAR40.23(1) -- "the net short or long position in the whole trading book"."""

SSA_EQUITY_SPECIFIC: Final[float] = 0.08
SSA_EQUITY_GENERAL: Final[float] = 0.08
"""Basel MAR40.43 -- "The capital requirement for specific risk and for general market risk will
each be 8%"."""
SSA_EQUITY_INDEX_ADDON: Final[float] = 0.02
"""Basel MAR40.47 -- further 2% on the net position in a diversified index contract."""

SSA_FX_CHARGE: Final[float] = 0.08
"""Basel MAR40.61 -- 8% of the overall net open position (greater of net long / net short sum,
plus the gold position regardless of sign, MAR40.60)."""

SSA_COMMODITY_DIRECTIONAL: Final[float] = 0.15
SSA_COMMODITY_GROSS: Final[float] = 0.03
"""Basel MAR40.72-40.73 -- simplified approach: 15% of the net position plus 3% of the gross
(long plus short) position in each commodity."""
SSA_COMMODITY_LADDER_BANDS: Final[tuple[float, ...]] = (
    1 / 12, 0.25, 0.5, 1.0, 2.0, 3.0, math.inf,
)
SSA_COMMODITY_SPREAD_RATE: Final[float] = 0.015
SSA_COMMODITY_CARRY_RATE: Final[float] = 0.006
"""Basel MAR40.69 Table 10 -- seven bands, spread rate 1.5% on the matched long + short;
MAR40.70 -- 0.6% of the net position carried forward per band; residual at 15%."""

SSA_OPTION_VOL_SHIFT: Final[float] = 0.25
SSA_OPTION_GAMMA_HALF: Final[float] = 0.5
"""Basel MAR40.80 -- gamma impact = ½·Γ·VU² (Taylor expansion); vega: ±25% proportional shift in
volatility. VU: equity 8%, FX/gold 8%, commodity 15%, interest rate: MAR40.26 weights."""
SSA_OPTION_VU: Final[dict[str, float]] = {"EQ": 0.08, "FX": 0.08, "COMM": 0.15}
