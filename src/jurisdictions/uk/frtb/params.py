"""UK PRA market-risk (FRTB) parameters -- PS1/26 Appendix 1.

Every constant used by :mod:`src.jurisdictions.uk.frtb` is defined here, transcribed from
the PRA Rulebook: CRR Firms: (CRR) Instrument 2026 (PRA2026/1, in force 1 January 2027)
with the Part, article and page ("p. N" = page N of 492) of that instrument:

* Market Risk: General Provisions (CRR) Part (Annex G) -- Article 325 (approaches, ACTP,
  simplified-standardised-approach multipliers), Article 325a (eligibility thresholds).
* Market Risk: Internal Model Approach (CRR) Part (Annex H) -- Articles 325ba-325bn (IMA
  scalars), Article 325bd (liquidity horizons, most liquid currencies / currency pairs,
  large-cap threshold -- also used by the advanced standardised approach).
* Market Risk: Advanced Standardised Approach (CRR) Part (Annex I) -- Articles 325c-325ay
  (sensitivities-based method, residual risk add-on, default risk charge).
* Market Risk: Simplified Standardised Approach (CRR) Part (Annex J) -- Articles 326-361
  (the legacy CRR standardised rules, scaled by the Article 325(2) multipliers).

The verbatim transcription is ``docs/jurisdictions/UK_frtb_reference.md``. Anything the
instrument does not settle carries ``# TODO: VERIFY`` with the location where the value would
be found, and a conservative placeholder. Amounts stated in GBP in the rules are carried in GBP
millions (the engine is currency-agnostic; UK inputs are taken in GBP millions).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.uk.params import OWN_FUNDS_TO_RWA_MULTIPLIER

RWA_MULTIPLIER: Final[float] = OWN_FUNDS_TO_RWA_MULTIPLIER
"""Required Level of Own Funds (CRR) Part Art 92(4)(b): own funds requirements for market risk
multiplied by 12.5 (p. 15); taken from :mod:`src.jurisdictions.uk.params`."""


def _frozen(d: dict) -> Mapping:  # type: ignore[type-arg]
    """Freeze a table (helper; no regulatory content)."""
    return MappingProxyType(d)


SQRT2: Final[float] = math.sqrt(2.0)
"""The divisor sqrt(2) of Art 325ae(3) (p. 344) and Art 325av(4) (p. 359)."""

REPORTING_CURRENCY: Final[str] = "GBP"
"""Default reporting / domestic currency of a UK institution (Art 325ae(3) 'domestic currency of
the institution', p. 344; Art 325q(1)(b) 'reporting currency', p. 327). Overridable on the
calculator."""

# =========================================================================
#  Market Risk: General Provisions (CRR) Part -- Article 325 / 325a (Annex G)
# =========================================================================
SSA_MULTIPLIER_DEBT: Final[float] = 1.3
"""Art 325(2)(a)(i): x1.3 for general and specific risk of debt instruments, Articles 334-340
(p. 226)."""
SSA_MULTIPLIER_EQUITY: Final[float] = 3.5
"""Art 325(2)(a)(ii): x3.5 for general and specific risk of equity, Articles 341-344, 346, 347
(p. 226)."""
SSA_MULTIPLIER_CIU: Final[float] = 3.5
"""Art 325(2)(a)(iii): x3.5 for CIUs under Article 348 (p. 226)."""
SSA_MULTIPLIER_FX: Final[float] = 1.2
"""Art 325(2)(b): x1.2 for foreign exchange risk, Articles 351-354 (p. 227)."""
SSA_MULTIPLIER_COMMODITY: Final[float] = 1.9
"""Art 325(2)(c): x1.9 for commodity risk, Articles 355-361 (p. 227)."""

SSA_ELIGIBILITY_TOTAL_ASSETS_SHARE: Final[float] = 0.10
"""Art 325a(1)(a): market-risk business <= 10% of total assets (p. 231)."""
SSA_ELIGIBILITY_ABSOLUTE_GBP_M: Final[float] = 440.0
"""Art 325a(1)(b): market-risk business <= GBP 440 million (p. 231)."""
SSA_INELIGIBLE_CONSECUTIVE_MONTHS: Final[int] = 3
"""Art 325a(5)(a): breach for three consecutive months (p. 231)."""
SSA_INELIGIBLE_MONTHS_IN_12: Final[int] = 6
"""Art 325a(5)(b): breach during more than 6 of the last 12 months (p. 231)."""

# =========================================================================
#  SBM -- Article 325h scenarios (p. 318)
# =========================================================================
SCENARIO_HIGH_MULTIPLIER: Final[float] = 1.25
"""Art 325h(2)(b): rho and gamma 'uniformly multiplied by 1.25' (p. 318)."""
SCENARIO_HIGH_CAP: Final[float] = 1.0
"""Art 325h(2)(b): 'subject to a cap at 100%' (p. 318)."""
SCENARIO_LOW_SLOPE: Final[float] = 2.0
"""Art 325h(2)(c): rho_low = max(2*rho - 100%, 75%*rho) (p. 318)."""
SCENARIO_LOW_FLOOR_FACTOR: Final[float] = 0.75
"""Art 325h(2)(c): the 75% term of the low scenario (p. 318)."""
SCENARIOS: Final[tuple[str, ...]] = ("MEDIUM", "HIGH", "LOW")
"""Art 325h(2)(a)-(c): the three correlation scenarios (p. 318)."""

CURVATURE_FX_SCALAR: Final[float] = 1.5
"""Art 325q(5)/(6): CVR+ and CVR- for FX risk factors may be divided by 1.5 (p. 328)."""

# =========================================================================
#  Article 325i -- listed index conditions (p. 319-320)
# =========================================================================
INDEX_LOOK_THROUGH_SAME_BUCKET_SHARE: Final[float] = 0.75
"""Art 325i(1)(c)(i)/(2)(a): 'more than 75% of constituents' mapped to one bucket (p. 319)."""
LISTED_INDEX_MIN_CONSTITUENTS: Final[int] = 20
"""Art 325i(3)(b): at least 20 constituents (p. 319)."""
LISTED_INDEX_MAX_SINGLE_WEIGHT: Final[float] = 0.25
"""Art 325i(3)(c): no single constituent more than 25% (p. 319)."""
LISTED_INDEX_TOP_DECILE_MAX_WEIGHT: Final[float] = 0.60
"""Art 325i(3)(d): one tenth of constituents (rounded up) not more than 60% (p. 319)."""
LISTED_INDEX_MIN_MARKET_CAP_GBP_M: Final[float] = 32_000.0
"""Art 325i(3)(e): total market capitalisation no less than GBP 32 billion (p. 320)."""

# =========================================================================
#  GIRR -- Articles 325l, 325ae-325ag
# =========================================================================
GIRR_VERTICES: Final[tuple[float, ...]] = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)
"""Art 325l(1): 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years (p. 323)."""
GIRR_RW: Final[Mapping[float, float]] = _frozen(
    {0.25: 0.017, 0.5: 0.017, 1.0: 0.016, 2.0: 0.013, 3.0: 0.012,
     5.0: 0.011, 10.0: 0.011, 15.0: 0.011, 20.0: 0.011, 30.0: 0.011}
)
"""Art 325ae(1) Table 3 (p. 344)."""
GIRR_INFLATION_XCCY_RW: Final[float] = 0.016
"""Art 325ae(2): 1.6% for inflation and cross-currency basis risk factors (p. 344)."""
GIRR_MOST_LIQUID_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"AUD", "CAD", "EUR", "GBP", "JPY", "SEK", "USD"}
)
"""IMA Part Art 325bd(8)(a): AUD, CAD, EUR, GBP, JPY, SEK, USD (p. 251); used by Art 325ae(3)
together with 'the domestic currency of the institution' (p. 344)."""
GIRR_THETA: Final[float] = 0.03
"""Art 325af(2): theta = 3% (p. 344)."""
GIRR_TENOR_CORR_FLOOR: Final[float] = 0.40
"""Art 325af(2): max[exp(-theta*|Tk-Tl|/min{Tk;Tl}); 40%] (p. 344)."""
GIRR_DIFFERENT_CURVE_CORR: Final[float] = 0.999
"""Art 325af(1)/(3): 99.90% for the same maturity on different curves (p. 344-345)."""
GIRR_INFLATION_CORR: Final[float] = 0.40
"""Art 325af(4): GIRR factor vs inflation factor 40% (p. 345)."""
GIRR_XCCY_CORR: Final[float] = 0.0
"""Art 325af(5): cross-currency basis vs any GIRR factor 0% (p. 345)."""
GIRR_INFLATION_INFLATION_CORR: Final[float] = 0.999
"""Art 325af(6): two different inflation factors in the same currency 99.90% (p. 345)."""
GIRR_GAMMA: Final[float] = 0.50
"""Art 325ag(1): gamma_bc = 50% (p. 345)."""

# =========================================================================
#  CSR vertices -- Articles 325m, 325n (p. 324-325)
# =========================================================================
CSR_VERTICES: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Art 325m(1), 325n(3)(a), 325n(5)(a): 0.5, 1, 3, 5, 10 years (p. 324-325)."""
VEGA_OPTION_MATURITIES: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Art 325l(7)(a), 325m(2), 325n, 325o(3), 325p(3), 325q(2): 0.5, 1, 3, 5, 10 years
(p. 323-328)."""
GIRR_VEGA_UNDERLYING_MATURITIES: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Art 325l(7)(b): residual maturity of the underlying, 0.5, 1, 3, 5, 10 years (p. 323)."""
COMMODITY_VERTICES: Final[tuple[float, ...]] = (
    0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0
)
"""Art 325p(2): 0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years (p. 327)."""

# =========================================================================
#  CSR non-securitisation -- Articles 325ah-325aj (p. 345-349)
# =========================================================================
CSR_NONSEC_RW: Final[Mapping[str, float]] = _frozen(
    {"1": 0.005, "2": 0.010, "3": 0.050, "4": 0.030, "5": 0.030, "6": 0.020, "7": 0.015,
     "8": 0.025, "9": 0.020, "10": 0.040, "11": 0.120, "12": 0.070, "13": 0.085,
     "14": 0.055, "15": 0.050, "16": 0.120, "17": 0.015, "18": 0.050}
)
"""Art 325ah(1) Table 4 (p. 345-347). Bucket 1 = the central government of the UK and the Bank
of England (all credit quality) and IG third-country central governments / MDBs / Art 117(2)
and 118 organisations, both 0.5%. Bucket 8 = 'Investment grade (Other)' covered bonds 2.5%."""
CSR_NONSEC_COVERED_AA_RW: Final[float] = 0.015
"""Art 325ah(1) Table 4 bucket 8: covered bonds 'Investment grade (AA- or higher (or equivalently
rated by ECAIs))' 1.5% (p. 346)."""
CSR_NONSEC_IG_BUCKETS: Final[frozenset[str]] = frozenset(
    {"1", "2", "3", "4", "5", "6", "7", "8", "17"}
)
"""Table 4 credit-quality column: buckets 1-8 investment grade; bucket 17 = listed credit
indices with a majority of IG constituents (p. 345-347)."""
CSR_NONSEC_HY_BUCKETS: Final[frozenset[str]] = frozenset(
    {"9", "10", "11", "12", "13", "14", "15", "18"}
)
"""Table 4: buckets 9-15 'Non-Investment grade and unrated'; bucket 18 = listed credit indices
with a majority non-IG or unrated (p. 346-347)."""
CSR_NONSEC_OTHER_BUCKET: Final[str] = "16"
"""Art 325ah(2) / 325ai(2): bucket 16 'Other Sector'; K_b = sum |WS_k| (p. 347-348)."""
CSR_NONSEC_INDEX_BUCKETS: Final[frozenset[str]] = frozenset({"17", "18"})
"""Table 4 buckets 17-18: listed credit indices (p. 347)."""
CSR_NONSEC_GSE_BUCKET: Final[str] = "2"
"""Art 325ah(4): non-tranched GSE mortgage-backed securities to bucket 2 (p. 347)."""

CSR_NAME_CORR_SECTOR: Final[float] = 0.35
"""Art 325ai(1): rho(name) 35% for different names in buckets 1 to 15 (p. 347)."""
CSR_NAME_CORR_INDEX: Final[float] = 0.80
"""Art 325ai(1): rho(name) 80% for different names in buckets 17 to 18 (p. 348)."""
CSR_TENOR_CORR: Final[float] = 0.65
"""Art 325ai(1): rho(tenor) 65% for different vertices (p. 348)."""
CSR_BASIS_CORR: Final[float] = 0.999
"""Art 325ai(1): rho(basis) 99.90% for different curves (bond vs CDS) (p. 348)."""
CSR_RATING_GAMMA: Final[float] = 0.50
"""Art 325aj: gamma(rating) 50% where the rating categories differ (p. 348)."""

# Art 325aj Table 5 (p. 348-349): gamma(sector) between sector groups, where group keys are the
# column labels of the table ('1/9', '2/10', ..., '7/15', '8', '16', '17', '18').
CSR_SECTOR_GROUP: Final[Mapping[str, str]] = _frozen(
    {"1": "1/9", "9": "1/9", "2": "2/10", "10": "2/10", "3": "3/11", "11": "3/11",
     "4": "4/12", "12": "4/12", "5": "5/13", "13": "5/13", "6": "6/14", "14": "6/14",
     "7": "7/15", "15": "7/15", "8": "8", "16": "16", "17": "17", "18": "18"}
)
"""Table 5 header grouping 'Bucket 1 and 9, 2 and 10, ..., 7 and 15, 8, 16, 17, 18' (p. 348)."""
_T5_COLS: Final[tuple[str, ...]] = (
    "1/9", "2/10", "3/11", "4/12", "5/13", "6/14", "7/15", "8", "16", "17", "18"
)
_T5_UPPER: Final[dict[str, tuple[float, ...]]] = {
    # row: values for the columns to the right of the diagonal, in _T5_COLS order
    "1/9": (0.75, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.0, 0.45, 0.45),
    "2/10": (0.05, 0.15, 0.20, 0.15, 0.10, 0.10, 0.0, 0.45, 0.45),
    "3/11": (0.05, 0.15, 0.20, 0.05, 0.20, 0.0, 0.45, 0.45),
    "4/12": (0.20, 0.25, 0.05, 0.05, 0.0, 0.45, 0.45),
    "5/13": (0.25, 0.05, 0.15, 0.0, 0.45, 0.45),
    "6/14": (0.05, 0.20, 0.0, 0.45, 0.45),
    "7/15": (0.05, 0.0, 0.45, 0.45),
    "8": (0.0, 0.45, 0.45),
    "16": (0.0, 0.0),
    "17": (0.75,),
}


def _symmetric_table_5() -> Mapping[tuple[str, str], float]:
    """Expand the upper triangle of Table 5 into a symmetric lookup (helper)."""
    out: dict[tuple[str, str], float] = {}
    for i, row in enumerate(_T5_COLS[:-1]):
        for j, val in enumerate(_T5_UPPER[row]):
            col = _T5_COLS[i + 1 + j]
            out[(row, col)] = val
            out[(col, row)] = val
    return MappingProxyType(out)


CSR_SECTOR_GAMMA: Final[Mapping[tuple[str, str], float]] = _symmetric_table_5()
"""Art 325aj Table 5: gamma(sector) for buckets of different sector groups (p. 348-349);
gamma(sector) = 1 for the same sector."""

# =========================================================================
#  CSR securitisation in the ACTP -- Articles 325ak-325al (p. 349-351)
# =========================================================================
CSR_CTP_RW: Final[Mapping[str, float]] = _frozen(
    {"1": 0.04, "2": 0.04, "3": 0.08, "4": 0.05, "5": 0.04, "6": 0.03, "7": 0.02, "8": 0.06,
     "9": 0.13, "10": 0.13, "11": 0.16, "12": 0.10, "13": 0.12, "14": 0.12, "15": 0.12,
     "16": 0.13}
)
"""Art 325ak(1) Table 6 (p. 349-351)."""
CSR_CTP_BASIS_CORR: Final[float] = 0.99
"""Art 325al(1): rho(basis) 99.00% for the ACTP (p. 351)."""
CSR_CTP_OTHER_BUCKET: Final[str] = "16"
"""Table 6 bucket 16 'Other Sector' (p. 351); Art 325g(5) curvature special case (p. 317)."""

# =========================================================================
#  CSR securitisation not in the ACTP -- Articles 325am-325ao (p. 351-353)
# =========================================================================
CSR_SEC_NONCTP_RW: Final[Mapping[str, float]] = _frozen(
    {"1": 0.009, "2": 0.015, "3": 0.020, "4": 0.020, "5": 0.008, "6": 0.012, "7": 0.012,
     "8": 0.014, "9": 0.01125, "10": 0.01875, "11": 0.025, "12": 0.025, "13": 0.010,
     "14": 0.015, "15": 0.015, "16": 0.0175, "17": 0.01575, "18": 0.02625, "19": 0.035,
     "20": 0.035, "21": 0.014, "22": 0.021, "23": 0.021, "24": 0.0245, "25": 0.035}
)
"""Art 325am(1) Table 7 (p. 351-352)."""
CSR_SEC_NONCTP_OTHER_BUCKET: Final[str] = "25"
"""Art 325am(2), 325an(2), 325ao(2): bucket 25 'Other sector' (p. 352-353)."""
CSR_SEC_TRANCHE_CORR: Final[float] = 0.40
"""Art 325an(1): rho(tranche) 40% for different tranches (p. 353)."""
CSR_SEC_TENOR_CORR: Final[float] = 0.80
"""Art 325an(1): rho(tenor) 80% (p. 353)."""
CSR_SEC_BASIS_CORR: Final[float] = 0.999
"""Art 325an(1): rho(basis) 99.90% (p. 353)."""
CSR_SEC_GAMMA: Final[float] = 0.0
"""Art 325ao(1): gamma_bc = 0% (p. 353)."""

# =========================================================================
#  Equity -- Articles 325ap-325ar (p. 353-356)
# =========================================================================
EQUITY_SPOT_RW: Final[Mapping[str, float]] = _frozen(
    {"1": 0.55, "2": 0.60, "3": 0.45, "4": 0.55, "5": 0.30, "6": 0.35, "7": 0.40, "8": 0.50,
     "9": 0.70, "10": 0.50, "11": 0.70, "12": 0.15, "13": 0.25}
)
"""Art 325ap(1) Table 8, 'risk weight for equity spot price' (p. 354)."""
EQUITY_REPO_RW: Final[Mapping[str, float]] = _frozen(
    {"1": 0.0055, "2": 0.0060, "3": 0.0045, "4": 0.0055, "5": 0.0030, "6": 0.0035,
     "7": 0.0040, "8": 0.0050, "9": 0.0070, "10": 0.0050, "11": 0.0070, "12": 0.0015,
     "13": 0.0025}
)
"""Art 325ap(1) Table 8, 'risk weight for equity repo rate' (p. 354)."""
EQUITY_LARGE_CAP_THRESHOLD_GBP_M: Final[float] = 1_600.0
"""IMA Part Art 325bd(9): large capitalisation 'greater than GBP 1.60 billion' (p. 251), applied
to the standardised approach by Art 325ap(2) (p. 355)."""
EQUITY_ADVANCED_ECONOMIES: Final[tuple[str, ...]] = (
    "Australia", "Canada", "euro-area member states", "Denmark", "Hong Kong SAR", "Japan",
    "Mexico", "New Zealand", "Norway", "Singapore", "Sweden", "Switzerland",
    "United Kingdom", "United States",
)
"""Art 325ap(3)(a)-(n): advanced economies; all other countries are emerging markets (p. 355)."""
EQUITY_OTHER_BUCKET: Final[str] = "11"
"""Art 325ap(4), 325aq(5): bucket 11 'Other sector'; K_b = sum |WS_k| (p. 355-356)."""
EQUITY_INDEX_BUCKETS: Final[frozenset[str]] = frozenset({"12", "13"})
"""Table 8 buckets 12-13: equity indices (p. 354)."""
EQUITY_SPOT_REPO_SAME_NAME_CORR: Final[float] = 0.999
"""Art 325aq(1): spot vs repo of the same issuer 99.90% (p. 355)."""
EQUITY_CORR: Final[Mapping[str, float]] = _frozen(
    {"1": 0.15, "2": 0.15, "3": 0.15, "4": 0.15, "5": 0.25, "6": 0.25, "7": 0.25, "8": 0.25,
     "9": 0.075, "10": 0.125, "12": 0.80, "13": 0.80}
)
"""Art 325aq(2)(a)-(e): 15% (1-4), 25% (5-8), 7.5% (9), 12.5% (10), 80% (12, 13) (p. 356)."""
EQUITY_SPOT_REPO_DIFF_NAME_FACTOR: Final[float] = 0.999
"""Art 325aq(4): spot vs repo of different issuers = paragraph-2 value x 99.90% (p. 356)."""
EQUITY_GAMMA_SECTOR: Final[float] = 0.15
"""Art 325ar(a): 15% where both buckets are within 1 to 10 (p. 356)."""
EQUITY_GAMMA_OTHER: Final[float] = 0.0
"""Art 325ar(b): 0% where either bucket is 11 (p. 356)."""
EQUITY_GAMMA_INDICES: Final[float] = 0.75
"""Art 325ar(c): 75% where the two buckets are 12 and 13 (p. 356)."""
EQUITY_GAMMA_ELSE: Final[float] = 0.45
"""Art 325ar(d): 45% otherwise (index vs sector bucket) (p. 356)."""

# =========================================================================
#  Commodity -- Articles 325as-325au (p. 356-359)
# =========================================================================
COMMODITY_RW: Final[Mapping[str, float]] = _frozen(
    {"1": 0.30, "2": 0.35, "3a": 0.60, "3b": 0.60, "4": 0.80, "5": 0.40, "6": 0.45,
     "7": 0.20, "8": 0.35, "9": 0.25, "10": 0.35, "11": 0.50}
)
"""Art 325as Table 9 (p. 357). Electricity (3a) and carbon trading (3b) are separate buckets."""
COMMODITY_CORR: Final[Mapping[str, float]] = _frozen(
    {"1": 0.55, "2": 0.95, "3a": 0.40, "3b": 0.40, "4": 0.80, "5": 0.60, "6": 0.65,
     "7": 0.55, "8": 0.45, "9": 0.15, "10": 0.40, "11": 0.15}
)
"""Art 325at(3) Table 10: rho(commodity) for distinct commodities in a bucket (p. 358)."""
COMMODITY_TENOR_CORR: Final[float] = 0.99
"""Art 325at(2)/(2A): rho(tenor) 99% (p. 357-358)."""
COMMODITY_BASIS_CORR: Final[float] = 0.999
"""Art 325at(2)/(2A): rho(basis) 99.90% for different delivery locations (p. 357-358)."""
COMMODITY_GAMMA: Final[float] = 0.20
"""Art 325au(1)(a): 20% where both buckets are within 1 to 10 (p. 359)."""
COMMODITY_GAMMA_OTHER: Final[float] = 0.0
"""Art 325au(1)(b): 0% where either bucket is 11 (p. 359)."""
COMMODITY_OTHER_BUCKET: Final[str] = "11"
"""Table 9 bucket 11 'Other commodities' (p. 357)."""

# =========================================================================
#  FX -- Articles 325q, 325av-325aw (p. 327-328, 359)
# =========================================================================
FX_RW: Final[float] = 0.15
"""Art 325av(1): 15% for all FX sensitivities (p. 359)."""
FX_MOST_LIQUID_PAIR_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"AUD", "BRL", "CAD", "CHF", "CNY", "EUR", "GBP", "HKD", "INR", "JPY", "KRW", "MXN",
     "NOK", "NZD", "RUB", "SEK", "SGD", "TRY", "USD", "ZAR"}
)
"""IMA Part Art 325bd(8)(b): any pair formed from two of these 20 currencies (p. 251); used by
Art 325av(4) (RW / sqrt(2), p. 359). The text prints 'Brazilian lire' and 'Swiss kroner (SEK)';
the ISO codes as printed (BRL, SEK) are used."""
FX_GAMMA: Final[float] = 0.60
"""Art 325aw(1): uniform gamma_bc = 60% (p. 359)."""

# =========================================================================
#  Vega and curvature -- Articles 325ax-325ay (p. 359-361)
# =========================================================================
VEGA_RW: Final[Mapping[str, float]] = _frozen(
    {"GIRR": 1.0, "CSR_NONSEC": 1.0, "CSR_SEC_CTP": 1.0, "CSR_SEC_NONCTP": 1.0,
     "EQUITY_LARGE_INDEX": 0.7778, "EQUITY_SMALL_OTHER": 1.0, "COMMODITY": 1.0, "FX": 1.0}
)
"""Art 325ax(2) Table 11 (p. 359-360)."""
VEGA_ALPHA: Final[float] = 0.01
"""Art 325ay(1): alpha = 1% in rho(option maturity) and rho(underlying maturity) (p. 360)."""
CURVATURE_CORR_POWER: Final[int] = 2
"""Art 325ay(5): curvature correlations are the square of the delta rho and gamma (p. 361)."""

# =========================================================================
#  Residual risk add-on -- Article 325u (p. 333-335)
# =========================================================================
RRAO_EXOTIC_RW: Final[float] = 0.01
"""Art 325u(3)(a): 1% of gross notional for exotic underlyings (p. 333)."""
RRAO_OTHER_RW: Final[float] = 0.001
"""Art 325u(3)(b): 0.1% of gross notional for other residual risks (p. 333)."""
RRAO_EXOTIC_UNDERLYINGS: Final[tuple[str, ...]] = (
    "longevity", "weather", "natural disasters", "future realised volatility"
)
"""Art 325u(5)(a)-(d) (p. 334)."""

# =========================================================================
#  Default risk -- Articles 325v-325ad (p. 335-343)
# =========================================================================
DRC_LGD_NON_SENIOR: Final[float] = 1.00
"""Art 325w(3)(a): non-senior debt LGD 100% (p. 337)."""
DRC_LGD_SENIOR: Final[float] = 0.75
"""Art 325w(3)(b): senior debt LGD 75% (p. 337)."""
DRC_LGD_COVERED_BOND: Final[float] = 0.25
"""Art 325w(3)(c): covered bonds LGD 25% (p. 337)."""
DRC_LGD_EQUITY: Final[float] = 1.00
"""Art 325w(4): equity V_D assumes 'a full loss in value' (p. 337)."""
DRC_MATURITY_CAP_YEARS: Final[float] = 1.0
"""Art 325x(2)-(3): maturity ratio relative to one year (p. 337-338)."""
DRC_MATURITY_FLOOR_YEARS: Final[float] = 0.25
"""Art 325x(2)(b)/(3): 'with a floor of three months' (p. 338)."""
DRC_RW_BY_RATING: Final[Mapping[str, float]] = _frozen(
    {"AAA": 0.005, "AA": 0.02, "A": 0.03, "BBB": 0.06, "BB": 0.15, "B": 0.30, "CCC": 0.50,
     "UNRATED": 0.15, "DEFAULTED": 1.00}
)
"""Art 325y(1) Table 2 (p. 338-339): AAA 0.5%, AA+ to AA- 2%, A 3%, BBB 6%, BB 15%, B 30%,
CCC+ and below 50%, unrated 15%, defaulted 100%."""
DRC_RW_BY_RATING_BUCKET: Final[Mapping[RatingBucket, float]] = _frozen(
    {RatingBucket.AAA_TO_AA_MINUS: 0.02,  # AAA (0.5%) only via flag 'rating_aaa'
     RatingBucket.A_PLUS_TO_A_MINUS: 0.03,
     RatingBucket.BBB_PLUS_TO_BBB_MINUS: 0.06,
     RatingBucket.BB_PLUS_TO_BB_MINUS: 0.15,
     RatingBucket.B_PLUS_TO_B_MINUS: 0.30,
     RatingBucket.BELOW_B_MINUS: 0.50,
     RatingBucket.UNRATED: 0.15}
)
"""Table 2 mapped onto the contract's RatingBucket. The contract merges AAA with AA+..AA-; the
conservative AA weight (2%) applies unless the position carries flags['rating_aaa'] (contract gap,
see report)."""
DRC_SA_ZERO_RW: Final[float] = 0.0
"""Art 325y(2): exposures that would receive 0% under the SA receive a 0% default RW (p. 339)."""
DRC_BUCKETS: Final[tuple[str, ...]] = (
    "corporates", "sovereigns", "local governments/municipalities"
)
"""Art 325y(3) (p. 339)."""
DRC_SEC_RW_SCALAR: Final[float] = 0.08
"""Art 325aa(1): 8% of the non-trading-book securitisation risk weight (p. 340); also used for
tranched ACTP products by Art 325ad(1)(b) (p. 343)."""
DRC_SEC_DEFAULT_BANKING_BOOK_RW: Final[float] = 12.50
"""Placeholder where no banking-book RW is supplied. # TODO: VERIFY -- the rule (Art 325aa(1),
p. 340) requires the Securitisation Part hierarchy RW; 1,250% (the maximum) is used as a
conservative placeholder."""
DRC_SEC_ASSET_CLASSES: Final[tuple[str, ...]] = (
    "asset-backed commercial paper", "auto loans/leases", "residential mortgage-backed securities",
    "credit cards", "commercial mortgage-backed securities", "collateralised loan obligations",
    "collateralised debt obligations squared", "small and medium-sized enterprises",
    "student loans", "other retail", "other wholesale",
)
"""Art 325aa(4)(i)-(xi): the 11 asset classes (p. 340-341)."""
DRC_SEC_REGIONS: Final[tuple[str, ...]] = ("Asia", "Europe", "North America", "rest of the world")
"""Art 325aa(4)(A)-(D): the four regions (p. 341)."""
DRC_SEC_CORPORATE_BUCKET: Final[str] = "corporates"
"""Art 325aa(4)(a): one common bucket for all corporates, regardless of region (p. 340)."""
DRC_CTP_NEGATIVE_BUCKET_WEIGHT: Final[float] = 0.5
"""Art 325ad(4): DRC_ACTP = max{sum_b [max(DRC_b,0) + 0.5*min(DRC_b,0)]; 0} (p. 343)."""
DRC_CTP_BUCKET_FLOOR_AT_ZERO: Final[bool] = True
"""Art 325ad(3) as printed floors DRC_b at zero ('max{...; 0}', p. 343), which leaves the 0.5*min
term of paragraph 4 inert. BCBS MAR22.44(2) states 'no floor at zero applies at the bucket level'.
# TODO: VERIFY -- literal PRA text applied by default; the calculator can switch it off."""

# =========================================================================
#  Internal model approach scalars (Annex H)
# =========================================================================
IMA_ES_CONFIDENCE: Final[float] = 0.975
"""Art 325bc(1)(b): 97.5th percentile, one tailed (p. 245)."""
IMA_BASE_HORIZON_DAYS: Final[int] = 10
"""Art 325bc(1)(c): T = 10 days (p. 245)."""
IMA_LIQUIDITY_HORIZON_TABLE_1: Final[Mapping[int, int]] = _frozen(
    {1: 10, 2: 20, 3: 40, 4: 60, 5: 120}
)
"""Art 325bc(1) Table 1: liquidity horizons j = 1..5 of 10, 20, 40, 60, 120 days (p. 245-246).
(The '20' of row 2 sits on the watermark column of the extracted text; read from the PDF.)"""
IMA_LIQUIDITY_HORIZONS: Final[Mapping[str, int]] = _frozen(
    {"IR_MOST_LIQUID_AND_DOMESTIC": 10, "IR_OTHER_CURRENCIES": 20, "IR_VOLATILITY": 60,
     "IR_OTHER": 60, "CS_SOVEREIGN_IG": 20, "CS_SOVEREIGN_HY": 40, "CS_CORPORATE_IG": 40,
     "CS_CORPORATE_HY": 60, "CS_VOLATILITY": 120, "CS_OTHER": 120, "EQ_LARGE_CAP": 10,
     "EQ_SMALL_CAP": 20, "EQ_VOL_LARGE_CAP": 20, "EQ_VOL_SMALL_CAP": 60, "EQ_OTHER": 60,
     "FX_MOST_LIQUID_PAIRS": 10, "FX_OTHER_PAIRS": 20, "FX_VOLATILITY": 40, "FX_OTHER": 40,
     "COM_ENERGY_CARBON": 20, "COM_PRECIOUS_NONFERROUS": 20, "COM_OTHER_PRICES": 60,
     "COM_VOL_ENERGY_CARBON": 60, "COM_VOL_PRECIOUS_NONFERROUS": 60, "COM_OTHER_VOL": 120,
     "COM_OTHER": 120}
)
"""Art 325bd(7) Table 2 (p. 249-251)."""
IMA_ES_RHO: Final[float] = 0.50
"""Art 325bb(1): rho = 50% across broad risk-factor categories (p. 244)."""
IMA_MULTIPLIER_BASE: Final[float] = 1.5
"""Art 325bf(6): mc = 1.5 + add-on between 0 and 0.5 (p. 261)."""
IMA_BACKTESTING_ADDON: Final[Mapping[int, float]] = _frozen(
    {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.20, 6: 0.26, 7: 0.33, 8: 0.38, 9: 0.42,
     10: 0.50}
)
"""Art 325bf(6) Table 3: fewer than 5 -> 0.00; 5 -> 0.20; 6 -> 0.26; 7 -> 0.33; 8 -> 0.38;
9 -> 0.42; more than 9 -> 0.50 (p. 262). Key 10 stands for 'more than 9'."""
IMA_DESK_BACKTEST_LIMIT_99: Final[int] = 12
"""Art 325bf(3)(a)/(b): 12 overshootings at 99% over 250 days (p. 260)."""
IMA_DESK_BACKTEST_LIMIT_975: Final[int] = 30
"""Art 325bf(3)(c)/(d): 30 overshootings at 97.5% over 250 days (p. 260)."""
IMA_PLA_SPEARMAN: Final[tuple[float, float]] = (0.80, 0.70)
"""Art 325bg(7): green if Spearman > 0.8; red if < 0.7 (p. 269)."""
IMA_PLA_KS: Final[tuple[float, float]] = (0.09, 0.12)
"""Art 325bg(7): green if KS < 0.09; red if > 0.12 (p. 269)."""
IMA_SES_RHO: Final[float] = 0.6
"""Art 325bk(13): rho = 0.6 in the SS_total aggregation (p. 283)."""
IMA_SES_MIN_HORIZON_DAYS: Final[int] = 20
"""Art 325bk(3)(e): scaled to max(20, LH_j) days (p. 278)."""
IMA_YELLOW_SURCHARGE_K: Final[float] = 0.5
"""Art 325ba(5): k = 0.5 x sum_y SA_i / sum_g&y SA_i (p. 242)."""
IMA_DRC_CONFIDENCE: Final[float] = 0.999
"""Art 325bn(1)(a): 99.9% over a one-year horizon (p. 284)."""
IMA_DRC_AVERAGING_WEEKS: Final[int] = 12
"""Art 325ba(2)(b): average over the preceding 12 weeks (p. 241)."""
IMA_AVERAGING_DAYS: Final[int] = 60
"""Art 325ba(1)(b): averages over the preceding 60 business days (p. 241)."""
IMA_TRANSITIONAL_PERIOD: Final[tuple[str, str]] = ("2027-01-01", "2027-12-31")
"""Glossary 'IMA transitional period': 1 January 2027 to 31 December 2027 (p. 5); IMA Part rule
4.1: for one year after it every IMA desk is treated as a green desk (p. 238)."""

# =========================================================================
#  Simplified standardised approach (Annex J)
# =========================================================================
SSA_DEBT_SPECIFIC_ZERO: Final[float] = 0.0
"""Art 336(1) Table 1 row 1: debt securities with a 0% SA RW -> 0% (p. 370)."""
SSA_DEBT_SPECIFIC_LOW_RW_CAP: Final[float] = 0.50
"""Table 1 row 2: SA RW > 0% and <= 50% (p. 370)."""
SSA_DEBT_SPECIFIC_MID_RW_CAP: Final[float] = 1.00
"""Table 1 row 3: SA RW > 50% and <= 100% (p. 370)."""
SSA_DEBT_SPECIFIC_ROW2: Final[tuple[tuple[float, float], ...]] = ((0.5, 0.0025), (2.0, 0.01))
"""Table 1 row 2: 0.25% (residual term <= 6 months); 1.00% (> 6 and <= 24 months) (p. 370)."""
SSA_DEBT_SPECIFIC_ROW2_LONG: Final[float] = 0.016
"""Table 1 row 2: 1.60% (residual term exceeding 24 months) (p. 370)."""
SSA_DEBT_SPECIFIC_ROW3: Final[float] = 0.08
"""Table 1 row 3: 8% (p. 370)."""
SSA_DEBT_SPECIFIC_ROW4: Final[float] = 0.12
"""Table 1 row 4: SA RW > 100% -> 12% (p. 370)."""
SSA_COVERED_BOND_FACTOR: Final[float] = 0.5
"""Art 336(3): bonds qualifying for a 10% RW (Art 129(4)-(6)) at half of the second category
(p. 370)."""
SSA_SEC_SPECIFIC_SCALAR: Final[float] = 0.08
"""Art 337(1): 8% of the non-trading-book RW (p. 371)."""

# Art 339(4) Table 2 (p. 372-373): (zone, upper bound coupon >= 3%, upper bound coupon < 3%,
# weighting %, assumed interest rate change %). Upper bounds in years; None = open-ended.
_LadderRow = tuple[int, float | None, float | None, float, float | None]
SSA_MATURITY_LADDER: Final[tuple[_LadderRow, ...]] = (
    (1, 1 / 12, 1 / 12, 0.00, None),
    (1, 3 / 12, 3 / 12, 0.20, 1.00),
    (1, 6 / 12, 6 / 12, 0.40, 1.00),
    (1, 1.0, 1.0, 0.70, 1.00),
    (2, 2.0, 1.9, 1.25, 0.90),
    (2, 3.0, 2.8, 1.75, 0.80),
    (2, 4.0, 3.6, 2.25, 0.75),
    (3, 5.0, 4.3, 2.75, 0.75),
    (3, 7.0, 5.7, 3.25, 0.70),
    (3, 10.0, 7.3, 3.75, 0.65),
    (3, 15.0, 9.3, 4.50, 0.60),
    (3, 20.0, 10.6, 5.25, 0.60),
    (3, None, 12.0, 6.00, 0.60),
    (3, None, 20.0, 8.00, 0.60),
    (3, None, None, 12.50, 0.60),
)
"""Art 339(4) Table 2 (p. 372-373). The coupon >= 3% column has 13 bands (the 13th, '> 20 years',
shares the 6.00% weighting row with '> 10.6 <= 12.0 years' of the low-coupon column); the
coupon < 3% column has 15 bands."""
SSA_COUPON_THRESHOLD: Final[float] = 0.03
"""Art 339(2): coupon of 3% or more vs less than 3% (p. 372)."""
SSA_LADDER_BAND_MATCHED: Final[float] = 0.10
"""Art 339(9)(a): 10% of matched weighted positions in all bands (p. 373)."""
SSA_LADDER_ZONE_MATCHED: Final[Mapping[int, float]] = _frozen({1: 0.40, 2: 0.30, 3: 0.30})
"""Art 339(9)(b)-(d): 40% zone one, 30% zone two, 30% zone three (p. 373)."""
SSA_LADDER_ADJACENT_ZONES: Final[float] = 0.40
"""Art 339(9)(e): 40% between zones one and two and between two and three (p. 373)."""
SSA_LADDER_ZONES_1_3: Final[float] = 1.50
"""Art 339(9)(f): 150% between zones one and three (p. 373)."""
SSA_LADDER_RESIDUAL: Final[float] = 1.00
"""Art 339(9)(g): 100% of residual unmatched weighted positions (p. 373)."""
SSA_DURATION_ZONES: Final[tuple[tuple[int, float | None, float], ...]] = (
    (1, 1.0, 1.0), (2, 3.6, 0.85), (3, None, 0.7)
)
"""Art 340(4) Table 3: (zone, upper modified duration, assumed interest change %) (p. 374)."""
SSA_DURATION_ZONE_MATCHED: Final[float] = 0.02
"""Art 340(7)(a): 2% of matched duration-weighted position for each zone (p. 374)."""
SSA_EQUITY_SPECIFIC: Final[float] = 0.08
"""Art 342(1): 8% of overall gross position (p. 375)."""
SSA_EQUITY_GENERAL: Final[float] = 0.08
"""Art 343(1): 8% of overall net position (p. 375)."""
SSA_UNDERWRITING_REDUCTION: Final[Mapping[int, float]] = _frozen(
    {0: 1.00, 1: 0.90, 2: 0.75, 3: 0.75, 4: 0.50, 5: 0.25}
)
"""Art 345(1) Table 4: working day 0 100%, 1 90%, 2-3 75%, 4 50%, 5 25%, after 5 0% (p. 376)."""
SSA_CIU_POSITION: Final[float] = 0.32
"""Art 348(1): 32% for position risk (specific and general) (p. 378)."""
SSA_CIU_POSITION_AND_FX: Final[float] = 0.40
"""Art 348(1): 40% for position risk and foreign-exchange risk (p. 378)."""
SSA_FX_DE_MINIMIS: Final[float] = 0.02
"""Art 351(1): requirement only if net FX + net gold exceeds 2% of total own funds (p. 380)."""
SSA_FX_RATE: Final[float] = 0.08
"""Art 351(1): multiplied by 8% (p. 380)."""
SSA_FX_CLOSELY_CORRELATED_RATE: Final[float] = 0.04
"""Art 354(1): 4% of the matched position in two closely correlated currencies (p. 388)."""
SSA_OPTION_VOL_SHIFT: Final[float] = 0.25
"""Art 352a(8)(b): +/-25% shift in implied volatility (p. 385)."""
SSA_GAMMA_FACTOR: Final[float] = 0.5
"""Art 352a(7)(b): gamma impact = 1/2 x Gamma x VU^2 (p. 384)."""
SSA_COMMODITY_LADDER_BANDS: Final[tuple[float | None, ...]] = (
    1 / 12, 3 / 12, 6 / 12, 1.0, 2.0, 3.0, None
)
"""Art 359(1) Table 1 maturity bands: 0<=1m, >1<=3m, >3<=6m, >6<=12m, >1<=2y, >2<=3y, >3y
(p. 390-391)."""
SSA_COMMODITY_SPREAD: Final[float] = 0.015
"""Art 359(1) Table 1: spread rate 1.50% in every band (p. 390-391)."""
SSA_COMMODITY_CARRY: Final[float] = 0.006
"""Art 359(5)(b): carry rate 0.6% (p. 391)."""
SSA_COMMODITY_OUTRIGHT: Final[float] = 0.15
"""Art 359(5)(c): outright rate 15% (p. 391)."""
SSA_COMMODITY_SIMPLE_NET: Final[float] = 0.15
"""Art 360(1)(a): 15% of the net position (p. 391)."""
SSA_COMMODITY_SIMPLE_GROSS: Final[float] = 0.03
"""Art 360(1)(b): 3% of the gross position (p. 391)."""
SSA_COMMODITY_EXTENDED: Final[Mapping[str, tuple[float, float, float]]] = _frozen(
    {"PRECIOUS_METALS": (0.010, 0.003, 0.08), "BASE_METALS": (0.012, 0.005, 0.10),
     "AGRICULTURAL": (0.015, 0.006, 0.12), "OTHER": (0.015, 0.006, 0.15)}
)
"""Art 361(1) Table 2 (spread, carry, outright): precious metals (except gold) 1.0/0.3/8; base
metals 1.2/0.5/10; agricultural products (softs) 1.5/0.6/12; other, including energy
1.5/0.6/15 (p. 392)."""
