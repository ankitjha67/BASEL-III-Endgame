"""EU market-risk (FRTB) parameters -- CRR Part Three, Title IV, as amended by CRR3.

Every constant below is transcribed from one of two texts, with its article,
paragraph and table:

* **CRR3** -- Regulation (EU) 2024/1623 (OJ L, 19.6.2024), Article 1 points
  (156)-(195) and (236), (242) (Article 495h), (245) and Article 2. CRR3 is the
  authority wherever it replaces or amends an article ("p." = OJ page of the
  189-page act). Formulas printed as images in the text extraction were read
  from the rendered PDF pages (pp. 120, 121, 125).
* **Consolidated CRR** 02013R0575 -- EN -- 09.07.2024 (the consolidation
  already carries Commission Delegated Regulation (EU) 2021/424, marker
  ``M12``, which recalibrated Tables 3-11 of Chapter 1a). It is used for every
  provision CRR3 left unchanged. Image formulas were read from the rendered
  consolidated PDF (pp. 426-430, 457, 477).

The verbatim tables are reproduced in ``docs/jurisdictions/EU_frtb_reference.md``.

Approaches (Article 325(1) as replaced by CRR3 point (156)):
    (a) alternative standardised approach (ASA) -- Chapter 1a, Arts 325c-325ay;
    (b) alternative internal model approach (AIMA) -- Chapter 1b, Arts 325az-325bp;
    (c) simplified standardised approach (SSA) -- Article 325(2) with Chapters 2-4
        (Arts 326-361), subject to the Article 325a thresholds.

Where neither text settles a value the constant carries ``# TODO: VERIFY``.
Monetary thresholds stated in EUR by the Regulation are kept in EUR millions.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Final

from src.jurisdictions.base import RatingBucket

# =========================================================================
#  General -- Articles 325, 325a, 325h, 92(6)
# =========================================================================

RWA_MULTIPLIER: Final[float] = 12.5
"""Article 92(6)(b) (CRR3 point (28), p.27): own funds requirements for market risk x 12,5."""

SCENARIO_HIGH_MULTIPLIER: Final[float] = 1.25
"""Article 325h(2)(b): high-correlations scenario, rho and gamma x 1,25, capped at 100 %."""
SCENARIO_CORRELATION_CAP: Final[float] = 1.0
"""Article 325h(2)(b): cap at 100 %."""
SCENARIO_LOW_SLOPE: Final[float] = 2.0
SCENARIO_LOW_INTERCEPT: Final[float] = 1.0
SCENARIO_LOW_FLOOR_FACTOR: Final[float] = 0.75
"""Article 325h(2)(c) (M12, rendered p.430): rho_low = max(2*rho - 100 %; 75 % * rho), same
for gamma."""

SCENARIOS: Final[tuple[str, ...]] = ("LOW", "MEDIUM", "HIGH")
"""Article 325h(2)(a)-(c); Article 325h(4): the SBM requirement is the highest of the three."""

# --- Simplified standardised approach -- Article 325(2) (CRR3 point (156)(a), p.115)
SSA_MULTIPLIER_DEBT: Final[float] = 1.3
"""Article 325(2)(a)(i): general and specific risk of debt instruments (excl. securitisation)."""
SSA_MULTIPLIER_EQUITY: Final[float] = 3.5
"""Article 325(2)(a)(ii): general and specific risk of equity instruments."""
SSA_MULTIPLIER_FX: Final[float] = 1.2
"""Article 325(2)(b): foreign exchange risk (Chapter 3)."""
SSA_MULTIPLIER_COMMODITY: Final[float] = 1.9
"""Article 325(2)(c): commodity risk (Chapter 4)."""
SSA_MULTIPLIER_SECURITISATION: Final[float] = 1.0
"""Article 325(2)(d): securitisation instruments (Article 337) enter without a multiplier."""
SSA_MULTIPLIER_CIU: Final[float] = 3.5
"""CIU position risk (Article 348) is not named in Article 325(2)(a)(i)/(ii).
# TODO: VERIFY -- Article 325(2)(a) does not say which multiplier applies to the Article 348
CIU charge; the equity multiplier (3,5, the higher) is used as a conservative placeholder."""

SSA_THRESHOLD_SHARE_OF_TOTAL_ASSETS: Final[float] = 0.10
"""Article 325a(1)(a) (wording kept by CRR3 point (157)(b)): <= 10 % of total assets."""
SSA_THRESHOLD_EUR_M: Final[float] = 500.0
"""Article 325a(1)(b): <= EUR 500 million (EUR millions)."""
SSA_EXIT_CONSECUTIVE_MONTHS: Final[int] = 3
SSA_EXIT_MONTHS_IN_LAST_12: Final[int] = 6
"""Article 325a(5)(a)-(b): cease within three months if breached for three consecutive months or
for more than 6 of the last 12 months."""

AIMA_MIN_SHARE_OF_TOTAL: Final[float] = 0.10
"""Article 325(4) (CRR3): ASA + AIMA combined only if AIMA >= 10 % of total market-risk OFR."""

# =========================================================================
#  Index look-through -- Article 325i(3) (M12)
# =========================================================================

INDEX_MIN_CONSTITUENTS: Final[int] = 20
"""Article 325i(3)(b)."""
INDEX_MAX_SINGLE_WEIGHT: Final[float] = 0.25
"""Article 325i(3)(c)."""
INDEX_TOP_DECILE_MAX_WEIGHT: Final[float] = 0.60
"""Article 325i(3)(d): top tenth of constituents <= 60 % of market capitalisation."""
INDEX_MIN_MARKET_CAP_EUR_M: Final[float] = 40_000.0
"""Article 325i(3)(e): >= EUR 40 billion (EUR millions)."""
INDEX_BUCKET_CONCENTRATION: Final[float] = 0.75
"""Article 325i(1)(c)(i) / (2)(a): more than 75 % of constituents mapped to one bucket."""
CIU_TRACKING_DIFFERENCE: Final[float] = 0.01
"""Article 325j(2) (M12): annualised return difference below 1 % -> treat as the index."""

# =========================================================================
#  Underwriting -- Article 325k Table 1 (ASA) and Article 345 Table 4 (SSA)
# =========================================================================

UNDERWRITING_FACTORS_ASA: Final[dict[int, float]] = {
    0: 0.00,
    1: 0.10,
    2: 0.25,
    3: 0.25,
    4: 0.50,
    5: 0.75,
}
"""Article 325k(2) Table 1: multiplying factor by business day (after day 5: 100 %)."""
UNDERWRITING_FACTOR_ASA_AFTER_DAY_5: Final[float] = 1.00

UNDERWRITING_REDUCTION_SSA: Final[dict[int, float]] = {
    0: 1.00,
    1: 0.90,
    2: 0.75,
    3: 0.75,
    4: 0.50,
    5: 0.25,
}
"""Article 345(1) Table 4: reduction factor by working day (after working day 5: 0 %)."""
UNDERWRITING_REDUCTION_SSA_AFTER_DAY_5: Final[float] = 0.00

# =========================================================================
#  GIRR -- Articles 325l, 325ae (M12 Table 3; CRR3 point (170)), 325af, 325ag
# =========================================================================

GIRR_TENORS: Final[tuple[float, ...]] = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)
"""Article 325l(1): delta risk-free rate vertices."""

GIRR_RW_BY_TENOR: Final[dict[float, float]] = {
    0.25: 0.017,
    0.5: 0.017,
    1.0: 0.016,
    2.0: 0.013,
    3.0: 0.012,
    5.0: 0.011,
    10.0: 0.011,
    15.0: 0.011,
    20.0: 0.011,
    30.0: 0.011,
}
"""Article 325ae(1) Table 3 (M12): currencies not in the most liquid sub-category."""
GIRR_RW_INFLATION_XCCY: Final[float] = 0.016
"""Article 325ae(2) (M12): inflation and cross-currency basis risk factors."""
GIRR_LIQUID_DIVISOR: Final[float] = math.sqrt(2.0)
"""Article 325ae(3) as replaced by CRR3 point (170) (p.121, rendered): most liquid currencies
(Art 325bd(7)(b)) and the domestic currency -- risk-free RWs AND inflation / cross-currency
basis RWs divided by sqrt(2)."""

GIRR_DEFAULT_DOMESTIC_CURRENCY: Final[str] = "EUR"
"""Domestic currency of the institution for Article 325ae(3) (configurable per calculator)."""
GIRR_MOST_LIQUID_CURRENCIES: Final[frozenset[str]] = frozenset()
"""Article 325bd(7)(b): the most liquid currencies are specified in an EBA RTS that is not in the
supplied texts.
# TODO: VERIFY -- list of most liquid currencies (RTS under Art 325bd(7)(b)); conservative
placeholder = empty set (only the domestic currency, ERM II currencies per Art 325bd(5a) and
sensitivities flagged ``eu_most_liquid_currency`` receive the sqrt(2) reduction)."""

GIRR_RHO_DIFFERENT_CURVE: Final[float] = 0.999
"""Article 325af(1): same vertex, different curves."""
GIRR_THETA: Final[float] = 0.03
"""Article 325af(2): theta = 3 %."""
GIRR_RHO_TENOR_FLOOR: Final[float] = 0.40
"""Article 325af(2): max(exp(-theta*|Tk-Tl|/min(Tk,Tl)); 40 %)."""
GIRR_RHO_INFLATION: Final[float] = 0.40
"""Article 325af(4): GIRR risk factor vs inflation risk factor."""
GIRR_RHO_XCCY: Final[float] = 0.0
"""Article 325af(5): cross-currency basis vs any GIRR factor (incl. another xccy factor)."""
GIRR_GAMMA: Final[float] = 0.50
"""Article 325ag(1)."""
GIRR_GAMMA_ERM2_EUR: Final[float] = 0.80
"""Article 325ag(2): currency of Article 325av(3) (ERM II, narrower band) vs the euro."""

GIRR_VEGA_MATURITIES: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Article 325l(7): GIRR vega maturities (also CSR 325m(2)/325n, equity 325o(3), commodity
325p(3), FX 325q(2) as replaced by CRR3 point (161))."""
CSR_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Articles 325m(1), 325n(3)(a), 325n(5)(a)."""
COMMODITY_TENORS: Final[tuple[float, ...]] = GIRR_TENORS
"""Article 325p(2): 0,25 ... 30 years."""

# =========================================================================
#  CSR non-securitisation -- Article 325ah Table 4 (M12; CRR3 point (171)),
#  325ai (CRR3 point (172)), 325aj Table 5 (M12; CRR3 point (173))
# =========================================================================

CSR_NONSEC_RW: Final[dict[int, float]] = {
    1: 0.005,
    2: 0.005,
    3: 0.010,
    4: 0.050,
    5: 0.030,
    6: 0.030,
    7: 0.020,
    8: 0.015,
    9: 0.010,
    10: 0.025,  # CQS 2 to 3; CQS 1 -> CSR_NONSEC_RW_BUCKET10_CQS1
    11: 0.020,
    12: 0.040,
    13: 0.120,
    14: 0.070,
    15: 0.085,
    16: 0.055,
    17: 0.050,
    18: 0.120,
    19: 0.015,
    20: 0.050,
}
"""Article 325ah(1) Table 4 (M12)."""
CSR_NONSEC_RW_BUCKET10_CQS1: Final[float] = 0.015
"""Article 325ah(1) Table 4 bucket 10: third-country covered bonds, credit quality step 1."""

CSR_NONSEC_BUCKET_DESCRIPTIONS: Final[dict[int, str]] = {
    1: "All -- central government incl. central banks of Member States",
    2: "CQS 1-3 -- third-country central government/central banks, MDBs, Art 117(2)/118 IOs",
    3: "CQS 1-3 -- regional or local authority and public sector entities",
    4: "CQS 1-3 -- financial sector entities incl. government-established credit institutions "
    "and promotional lenders",
    5: "CQS 1-3 -- basic materials, energy, industrials, agriculture, manufacturing, mining",
    6: "CQS 1-3 -- consumer goods/services, transportation and storage, admin and support",
    7: "CQS 1-3 -- technology, telecommunications",
    8: "CQS 1-3 -- health care, utilities, professional and technical activities",
    9: "CQS 1-3 -- covered bonds issued by credit institutions established in Member States",
    10: "CQS 1 (1,5 %) / CQS 2-3 (2,5 %) -- covered bonds issued by credit institutions in "
    "third countries",
    11: "CQS 4-6 and unrated -- third-country central government, MDBs, IOs",
    12: "CQS 4-6 and unrated -- regional or local authority and PSEs",
    13: "CQS 4-6 and unrated -- financial sector entities ... promotional lenders and covered "
    "bonds (CRR3 point (171)(a)(i))",
    14: "CQS 4-6 and unrated -- basic materials, energy, industrials, ...",
    15: "CQS 4-6 and unrated -- consumer goods and services, ...",
    16: "CQS 4-6 and unrated -- technology, telecommunications",
    17: "CQS 4-6 and unrated -- health care, utilities, professional and technical activities",
    18: "Other sector",
    19: "Listed credit indices, majority of constituents investment grade",
    20: "Listed credit indices, majority of constituents non-investment grade or unrated",
}
"""Article 325ah(1) Table 4 (M12), bucket 13 sector as replaced by CRR3 point (171)(a)(i)."""

CSR_NONSEC_OTHER_BUCKET: Final[int] = 18
"""Article 325ah(2): unassignable issuers -> bucket 18; Article 325ai(2): sum of |WS_k|."""
CSR_NONSEC_IG_BUCKETS: Final[frozenset[int]] = frozenset(range(1, 11))
"""Buckets with credit quality step 1 to 3 (bucket 1 counted with them, Art 325aj as replaced
by CRR3 point (173)(a))."""
CSR_NONSEC_HY_BUCKETS: Final[frozenset[int]] = frozenset(range(11, 18))
"""Buckets with credit quality step 4 to 6 and unrated."""

CSR_RHO_NAME_DIFFERENT_1_18: Final[float] = 0.35
CSR_RHO_NAME_DIFFERENT_OTHER: Final[float] = 0.80
"""Article 325ai(1) rho_kl(name) as replaced by CRR3 point (172): 35 % for different names in
buckets 1-18 of Table 4, otherwise (index buckets 19-20) 80 %."""
CSR_RHO_TENOR_DIFFERENT: Final[float] = 0.65
"""Article 325ai(1): rho_kl(tenor)."""
CSR_RHO_BASIS_DIFFERENT: Final[float] = 0.999
"""Article 325ai(1): rho_kl(basis) (bond curve vs CDS curve)."""
CSR_GAMMA_RATING_DIFFERENT: Final[float] = 0.50
"""Article 325aj gamma_bc(rating) as replaced by CRR3 point (173)."""

CSR_SECTOR_GROUP: Final[dict[int, str]] = {
    1: "SOV",
    2: "SOV",
    11: "SOV",
    3: "RGLA",
    12: "RGLA",
    4: "FIN",
    13: "FIN",
    5: "BASIC",
    14: "BASIC",
    6: "CONS",
    15: "CONS",
    7: "TECH",
    16: "TECH",
    8: "HEALTH",
    17: "HEALTH",
    9: "COVERED",
    10: "COVERED",
    18: "OTHER",
    19: "IDX_IG",
    20: "IDX_HY",
}
"""Article 325aj Table 5 (M12) column groups: '1, 2 and 11', '3 and 12', ..., '9 and 10', 18, 19,
20. Buckets in the same group belong to the same sector (gamma_bc(sector) = 1)."""

_SECTOR_GAMMA_ROWS: Final[dict[str, dict[str, float]]] = {
    "SOV": {"RGLA": 0.75, "FIN": 0.10, "BASIC": 0.20, "CONS": 0.25, "TECH": 0.20,
            "HEALTH": 0.15, "COVERED": 0.10, "OTHER": 0.0, "IDX_IG": 0.45, "IDX_HY": 0.45},
    "RGLA": {"FIN": 0.05, "BASIC": 0.15, "CONS": 0.20, "TECH": 0.15, "HEALTH": 0.10,
             "COVERED": 0.10, "OTHER": 0.0, "IDX_IG": 0.45, "IDX_HY": 0.45},
    "FIN": {"BASIC": 0.05, "CONS": 0.15, "TECH": 0.20, "HEALTH": 0.05, "COVERED": 0.20,
            "OTHER": 0.0, "IDX_IG": 0.45, "IDX_HY": 0.45},
    "BASIC": {"CONS": 0.20, "TECH": 0.25, "HEALTH": 0.05, "COVERED": 0.05, "OTHER": 0.0,
              "IDX_IG": 0.45, "IDX_HY": 0.45},
    "CONS": {"TECH": 0.25, "HEALTH": 0.05, "COVERED": 0.15, "OTHER": 0.0, "IDX_IG": 0.45,
             "IDX_HY": 0.45},
    "TECH": {"HEALTH": 0.05, "COVERED": 0.20, "OTHER": 0.0, "IDX_IG": 0.45, "IDX_HY": 0.45},
    "HEALTH": {"COVERED": 0.05, "OTHER": 0.0, "IDX_IG": 0.45, "IDX_HY": 0.45},
    "COVERED": {"OTHER": 0.0, "IDX_IG": 0.45, "IDX_HY": 0.45},
    "OTHER": {"IDX_IG": 0.0, "IDX_HY": 0.0},
    "IDX_IG": {"IDX_HY": 0.75},
}


def _symmetric(rows: dict[str, dict[str, float]]) -> dict[tuple[str, str], float]:
    """Expand an upper-triangular table into a symmetric pair lookup."""
    out: dict[tuple[str, str], float] = {}
    for a, row in rows.items():
        for b, v in row.items():
            out[(a, b)] = v
            out[(b, a)] = v
    return out


CSR_SECTOR_GAMMA: Final[dict[tuple[str, str], float]] = _symmetric(_SECTOR_GAMMA_ROWS)
"""Article 325aj Table 5 (M12): gamma_bc(sector) between different sector groups."""

# --- ACTP -- Article 325ak Table 6 (M12; CRR3 point (174)), 325al --------------------------
CSR_CTP_RW: Final[dict[int, float]] = {
    1: 0.04,
    2: 0.04,
    3: 0.04,
    4: 0.08,
    5: 0.05,
    6: 0.04,
    7: 0.03,
    8: 0.02,
    9: 0.03,
    10: 0.06,
    11: 0.13,
    12: 0.13,
    13: 0.16,
    14: 0.10,
    15: 0.12,
    16: 0.12,
    17: 0.12,
    18: 0.13,
}
"""Article 325ak Table 6 (M12). CRR3 point (174)(a)(i) relabels the credit-quality column
'Credit quality step 1 to 10' (buckets 2-10) and 'Credit quality step 11 to 17' (buckets 11-17);
point (174)(a)(ii) adds covered bonds to bucket 13."""
CSR_CTP_OTHER_BUCKET: Final[int] = 18
CSR_CTP_RHO_BASIS_DIFFERENT: Final[float] = 0.99
"""Article 325al(1): rho_kl(basis) = 99,00 % for the ACTP (otherwise as Article 325ai)."""

# --- Securitisation non-ACTP -- Article 325am Table 7 (M12; CRR3 point (175)), 325an, 325ao -----
CSR_SEC_NONCTP_RW: Final[dict[int, float]] = {
    1: 0.009,
    2: 0.015,
    3: 0.020,
    4: 0.020,
    5: 0.008,
    6: 0.012,
    7: 0.012,
    8: 0.014,
    9: 0.01125,
    10: 0.01875,
    11: 0.025,
    12: 0.025,
    13: 0.010,
    14: 0.015,
    15: 0.015,
    16: 0.0175,
    17: 0.01575,
    18: 0.02625,
    19: 0.035,
    20: 0.035,
    21: 0.014,
    22: 0.021,
    23: 0.021,
    24: 0.0245,
    25: 0.035,
}
"""Article 325am(1) Table 7 (M12): 1-8 senior & CQS 1-10, 9-16 non-senior & CQS 1-10, 17-24
CQS 11-17 & unrated (labels as replaced by CRR3 point (175)(a)), 25 other sector."""
CSR_SEC_NONCTP_OTHER_BUCKET: Final[int] = 25
CSR_SEC_RHO_TRANCHE_DIFFERENT: Final[float] = 0.40
CSR_SEC_RHO_TENOR_DIFFERENT: Final[float] = 0.80
CSR_SEC_RHO_BASIS_DIFFERENT: Final[float] = 0.999
"""Article 325an(1): rho = rho(tranche) x rho(tenor) x rho(basis)."""
CSR_SEC_TRANCHE_OVERLAP: Final[float] = 0.80
"""Article 325an(1): same tranche = more than 80 % overlap in notional terms."""
CSR_SEC_GAMMA: Final[float] = 0.0
"""Article 325ao(1); Article 325ao(2): bucket 25 is added with no diversification."""

# =========================================================================
#  Equity -- Article 325ap Table 8 (M12), 325aq (M12), 325ar (M12)
# =========================================================================

EQUITY_RW_SPOT: Final[dict[int, float]] = {
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
"""Article 325ap(1) Table 8 (M12): risk weight for equity spot price."""
EQUITY_RW_REPO: Final[dict[int, float]] = {
    1: 0.0055,
    2: 0.0060,
    3: 0.0045,
    4: 0.0055,
    5: 0.0030,
    6: 0.0035,
    7: 0.0040,
    8: 0.0050,
    9: 0.0070,
    10: 0.0050,
    11: 0.0070,
    12: 0.0015,
    13: 0.0025,
}
"""Article 325ap(1) Table 8 (M12): risk weight for equity repo rate."""
EQUITY_OTHER_BUCKET: Final[int] = 11
EQUITY_RHO_SPOT: Final[dict[int, float]] = {
    1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15,
    5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25,
    9: 0.075,
    10: 0.125,
    12: 0.80, 13: 0.80,
}
"""Article 325aq(2)(a)-(e) (M12): spot-spot correlation within a bucket."""
EQUITY_RHO_REPO_INDEX_BUCKETS: Final[float] = 0.80
"""Article 325aq(3) (M12) refers only to points (a)-(d) of paragraph 2 for repo-repo correlations,
leaving the index buckets 12-13 unspecified.
# TODO: VERIFY -- repo/repo correlation in index buckets 12-13; placeholder = the spot 80 %."""
EQUITY_RHO_SPOT_REPO_SAME_NAME: Final[float] = 0.999
"""Article 325aq(1) (M12)."""
EQUITY_RHO_SPOT_REPO_DIFF_NAME_FACTOR: Final[float] = 0.999
"""Article 325aq(4): paragraph-2 correlation x 99,90 %."""
EQUITY_GAMMA_1_10: Final[float] = 0.15
EQUITY_GAMMA_OTHER_BUCKET: Final[float] = 0.0
EQUITY_GAMMA_INDICES: Final[float] = 0.75
EQUITY_GAMMA_OTHERWISE: Final[float] = 0.45
"""Article 325ar(a)-(d) (M12)."""

# =========================================================================
#  Commodity -- Article 325as Table 9 (CRR3 point (176)), 325at Table 10, 325au
# =========================================================================

COMMODITY_RW: Final[dict[str, float]] = {
    "1": 0.30,
    "2": 0.35,
    "3": 0.60,
    "3a": 0.40,
    "3b": 0.60,
    "4": 0.80,
    "5": 0.40,
    "6": 0.45,
    "7": 0.20,
    "8": 0.35,
    "9": 0.25,
    "10": 0.35,
    "11": 0.50,
}
"""Article 325as Table 9; CRR3 point (176): bucket 3 renamed 'Energy -- electricity', new
buckets 3a 'Energy -- EU ETS carbon trading' 40 % and 3b 'Energy -- non-EU ETS carbon trading'
60 %."""
COMMODITY_BUCKET_NAMES: Final[dict[str, str]] = {
    "1": "Energy -- solid combustibles",
    "2": "Energy -- liquid combustibles",
    "3": "Energy -- electricity",
    "3a": "Energy -- EU ETS carbon trading",
    "3b": "Energy -- non-EU ETS carbon trading",
    "4": "Freight",
    "5": "Metals -- non-precious",
    "6": "Gaseous combustibles",
    "7": "Precious metals (including gold)",
    "8": "Grains and oilseed",
    "9": "Livestock and dairy",
    "10": "Softs and other agricultural commodities",
    "11": "Other commodities",
}
COMMODITY_RHO: Final[dict[str, float]] = {
    "1": 0.55,
    "2": 0.95,
    "3": 0.40,
    "3a": 0.40,
    "3b": 0.40,
    "4": 0.80,
    "5": 0.60,
    "6": 0.65,
    "7": 0.55,
    "8": 0.45,
    "9": 0.15,
    "10": 0.40,
    "11": 0.15,
}
"""Article 325at(3) Table 10 (not amended by CRR3).
# TODO: VERIFY -- CRR3 inserted buckets 3a/3b in Table 9 only; Table 10 still lists bucket 3
'electricity and carbon trading' at 40 %. Placeholder: 3a and 3b use the bucket-3 40 %."""
COMMODITY_RHO_TENOR_DIFFERENT: Final[float] = 0.99
COMMODITY_RHO_BASIS_DIFFERENT: Final[float] = 0.999
"""Article 325at(2): rho(tenor) 99 %, rho(basis) (delivery location) 99,90 %."""
COMMODITY_OTHER_BUCKET: Final[str] = "11"
COMMODITY_GAMMA_1_10: Final[float] = 0.20
COMMODITY_GAMMA_OTHER: Final[float] = 0.0
"""Article 325au(a)-(b).
# TODO: VERIFY -- Article 325au(a) says 'bucket numbers 1 to 10'; buckets 3a/3b (CRR3) are
treated as within 1-10 (20 %)."""

# =========================================================================
#  FX -- Article 325av (M12; para 1), 325aw
# =========================================================================

FX_RW: Final[float] = 0.15
"""Article 325av(1) (M12)."""
FX_ERM2_DIVISOR: Final[float] = 3.0
"""Article 325av(2)(a): EUR / ERM II currency pair -> RW / 3 (or a narrower agreed band, (2)(b)
and (3), which must be supplied by the caller -- see ``fx_narrow_band_rw``)."""
FX_LIQUID_DIVISOR: Final[float] = math.sqrt(2.0)
"""Article 325av(4): most liquid currency pairs (Art 325bd(7)(c)) -> RW / sqrt(2)."""
FX_CONSTANT_PAIR_DIVISOR: Final[float] = 2.0
"""Article 325av(5): constant EUR / Member-State currency pair, zero bid/ask, with permission."""
FX_GAMMA: Final[float] = 0.60
"""Article 325aw."""
FX_CURVATURE_CROSS_DIVISOR: Final[float] = 1.5
"""Article 325q(5)-(6) (M12): CVR components may be divided by 1,5."""

# =========================================================================
#  Vega and curvature -- Article 325ax (CRR3 point (177)), 325ay
# =========================================================================

VEGA_RW: Final[dict[str, float]] = {
    "GIRR": 1.00,
    "CSR_NONSEC": 1.00,
    "CSR_SEC_CTP": 1.00,
    "CSR_SEC_NONCTP": 1.00,
    "EQUITY_LARGE_INDEX": 0.7778,
    "EQUITY_SMALL_OTHER": 1.00,
    "COMMODITY": 1.00,
    "FX": 1.00,
}
"""Article 325ax(2) Table 1 as replaced by CRR3 point (177)(a); paragraph 3 (LH formula)
deleted by CRR3 point (177)(b)."""
VEGA_ALPHA: Final[float] = 0.01
"""Article 325ay(1): alpha = 1 % in rho(option maturity) and rho(underlying maturity)."""

LIQUIDITY_HORIZON_VEGA_FORMER: Final[dict[str, int]] = {
    "GIRR": 60,
    "CSR_NONSEC": 120,
    "CSR_SEC_CTP": 120,
    "CSR_SEC_NONCTP": 120,
    "EQUITY_LARGE_INDEX": 20,
    "EQUITY_SMALL_OTHER": 60,
    "COMMODITY": 120,
    "FX": 40,
}
"""Article 325ax(3) Table 11 (M12) -- LH_risk class, superseded by CRR3 point (177) (kept for
reference: RW_sigma 55 % x sqrt(LH/10) capped at 100 % reproduces the CRR3 Table 1 weights)."""
VEGA_RW_SIGMA_FORMER: Final[float] = 0.55
"""Article 325ax(3) (M12, deleted by CRR3): RW_sigma = 55 %."""

# =========================================================================
#  Default risk charge -- Articles 325v-325ad
# =========================================================================

DRC_RW_BY_CQS: Final[dict[int, float]] = {
    1: 0.005,
    2: 0.03,
    3: 0.06,
    4: 0.15,
    5: 0.30,
    6: 0.50,
}
"""Article 325y(1) Table 2; credit quality step per the SA for credit risk (Article 325y(6),
CRR3 point (167))."""
DRC_RW_UNRATED: Final[float] = 0.15
DRC_RW_DEFAULTED: Final[float] = 1.00
"""Article 325y(1) Table 2."""
DRC_RW_ZERO_SA: Final[float] = 0.0
"""Article 325y(2): exposures with a 0 % SA credit-risk weight receive a 0 % default risk weight."""

DRC_LGD: Final[dict[str, float]] = {
    "NON_SENIOR": 1.00,
    "SENIOR": 0.75,
    "COVERED_BOND": 0.25,
    "EQUITY": 1.00,
}
"""Article 325w(3)(a)-(c) (debt) and 325w(6) (equity)."""
DRC_SENIORITY_RANK: Final[dict[str, int]] = {
    "COVERED_BOND": 3,
    "SENIOR": 2,
    "NON_SENIOR": 1,
    "EQUITY": 0,
}
"""Article 325x(1): a short may offset a long of the same obligor only where the short has the
same or lower seniority. Higher rank = more senior."""
DRC_MATURITY_ONE_YEAR: Final[float] = 1.0
DRC_MATURITY_FLOOR: Final[float] = 0.25
"""Article 325x(2)-(3): ratio of maturity to one year; the three-month floor is stated only for
exposures with no offsetting (para 3). Para 2(b) (partial offsetting) states no floor."""
DRC_CASH_EQUITY_MATURITY_OPTIONS: Final[tuple[float, float]] = (1.0, 0.25)
"""Article 325x(4): cash equity -- one year or three months at the institution's discretion."""
DRC_BUCKETS_NONSEC: Final[tuple[str, ...]] = (
    "CORPORATES",
    "SOVEREIGNS",
    "LOCAL_GOVERNMENTS_MUNICIPALITIES",
)
"""Article 325y(3)."""

DRC_SEC_RW_FACTOR: Final[float] = 0.08
"""Article 325aa(1): 8 % of the non-trading-book securitisation risk weight (incl. STS)."""
SEC_RW_FALLBACK: Final[float] = 12.5
"""# TODO: VERIFY -- fallback banking-book securitisation RW when none is supplied: 1 250 %, the
highest securitisation risk weight of Title II Chapter 5 (conservative placeholder)."""
DRC_SEC_SEC_IRBA_ERBA_MATURITY: Final[float] = 1.0
"""Article 325aa(2): one-year maturity for SEC-IRBA / SEC-ERBA tranche risk weights."""
DRC_SEC_ASSET_CLASSES: Final[tuple[str, ...]] = (
    "ABCP",
    "AUTO_LOANS_LEASES",
    "RMBS",
    "CREDIT_CARDS",
    "CMBS",
    "CLO",
    "CDO_SQUARED",
    "SME",
    "STUDENT_LOANS",
    "OTHER_RETAIL",
    "OTHER_WHOLESALE",
)
"""Article 325aa(4), second subparagraph: the 11 asset classes."""
DRC_SEC_REGIONS: Final[tuple[str, ...]] = ("ASIA", "EUROPE", "NORTH_AMERICA", "REST_OF_WORLD")
"""Article 325aa(4): the four regions; Article 325aa(5): unassignable -> 'rest of the world'."""
DRC_SEC_CORPORATE_BUCKET: Final[str] = "CORPORATES"
"""Article 325aa(4)(a): one common bucket for all corporates regardless of region."""
DRC_CTP_NEGATIVE_BUCKET_FACTOR: Final[float] = 0.5
"""Article 325ad(4) (C7, rendered p.457): DRC_ACTP = max{Sum_b(max(DRC_b,0) + 0,5 min(DRC_b,0)); 0}.
Article 325ad(3) as replaced by CRR3 point (169)(b) removes the per-bucket zero floor."""

# =========================================================================
#  RRAO -- Article 325u (CRR3 point (164))
# =========================================================================

RRAO_RW_EXOTIC: Final[float] = 0.010
"""Article 325u(3)(a): exotic underlyings 1,0 %."""
RRAO_RW_OTHER: Final[float] = 0.001
"""Article 325u(3)(b): other residual risks 0,1 %."""
RRAO_HEDGE_DEROGATION_END: Final[date] = date(2032, 12, 31)
"""Article 325u(4a) (CRR3 point (164)(a)): hedges of RRAO positions exempt until 31 December 2032
(with competent-authority permission)."""

# =========================================================================
#  Alternative internal model approach -- Articles 325ba-325bp
# =========================================================================

IMA_ES_CONFIDENCE: Final[float] = 0.975
"""Article 325bc(1)(b): 97,5th percentile, one-tailed."""
IMA_BASE_HORIZON_DAYS: Final[int] = 10
"""Article 325bc(1)(c): T = 10 days."""
IMA_LIQUIDITY_HORIZONS: Final[tuple[int, ...]] = (10, 20, 40, 60, 120)
"""Article 325bc(1) Table 1."""
IMA_LH_BY_SUBCATEGORY: Final[dict[str, int]] = {
    "IR_MOST_LIQUID_AND_DOMESTIC": 10,
    "IR_OTHER_CURRENCIES": 20,
    "IR_VOLATILITY": 60,
    "IR_OTHER": 60,
    "CS_CENTRAL_GOVERNMENT_MEMBER_STATES": 20,
    "CS_COVERED_BONDS_MEMBER_STATES_IG": 20,
    "CS_SOVEREIGN_IG": 20,
    "CS_SOVEREIGN_HY": 40,
    "CS_CORPORATE_IG": 40,
    "CS_CORPORATE_HY": 60,
    "CS_VOLATILITY": 120,
    "CS_OTHER": 120,
    "EQ_PRICE_LARGE_CAP": 10,
    "EQ_PRICE_SMALL_CAP": 20,
    "EQ_VOL_LARGE_CAP": 20,
    "EQ_VOL_SMALL_CAP": 60,
    "EQ_OTHER": 60,
    "FX_MOST_LIQUID_PAIRS": 10,
    "FX_OTHER_PAIRS": 20,
    "FX_VOLATILITY": 40,
    "FX_OTHER": 40,
    "CO_ENERGY_AND_CARBON_PRICE": 20,
    "CO_PRECIOUS_AND_NON_FERROUS_PRICE": 20,
    "CO_OTHER_PRICE": 60,
    "CO_ENERGY_AND_CARBON_VOL": 60,
    "CO_PRECIOUS_AND_NON_FERROUS_VOL": 60,
    "CO_OTHER_VOL": 120,
    "CO_OTHER": 120,
}
"""Article 325bd(1) Table 2 (CRR3 point (181) adds ERM II currencies to 'most liquid')."""
IMA_RHO: Final[float] = 0.50
"""Article 325bb(1): rho = 50 % between UES_t and the sum of UES_t^i."""
IMA_MULTIPLIER_BASE: Final[float] = 1.5
"""Article 325bf(6) as amended by CRR3 point (183)(a)(i): m_c at least 1,5 + add-on (Table 3)."""
IMA_BACKTESTING_ADDON: Final[dict[int, float]] = {
    0: 0.00,
    1: 0.00,
    2: 0.00,
    3: 0.00,
    4: 0.00,
    5: 0.20,
    6: 0.26,
    7: 0.33,
    8: 0.38,
    9: 0.42,
    10: 0.50,
}
"""Article 325bf(6) Table 3: fewer than 5 -> 0,00; 5 -> 0,20; 6 -> 0,26; 7 -> 0,33; 8 -> 0,38;
9 -> 0,42; more than 9 -> 0,50 (key 10 = 'more than 9')."""
IMA_BACKTEST_LIMIT_99: Final[int] = 12
IMA_BACKTEST_LIMIT_975: Final[int] = 30
"""Article 325bf(3): desk eligibility -- at most 12 overshootings at 99 % and 30 at 97,5 % (both
hypothetical and actual) over 250 business days."""
IMA_BACKTEST_WINDOW_DAYS: Final[int] = 250
IMA_RS_RC_FC_RATIO_MIN: Final[float] = 0.75
"""Article 325bc(2)(a): reduced set must explain >= 75 % (60-day average of PES_RC / PES_FC)."""
IMA_AVERAGING_DAYS: Final[int] = 60
"""Article 325ba(1)(b): 60-business-day averages."""
IMA_DRC_CONFIDENCE: Final[float] = 0.999
"""Article 325bn(1)(a): 99,9 % one-year VaR."""
IMA_DRC_AVERAGING_WEEKS: Final[int] = 12
"""Article 325ba(2)(b)."""
IMA_DRC_PD_FLOOR: Final[float] = 0.0003
IMA_DRC_PD_FLOOR_ZERO_RW: Final[float] = 0.0001
"""Article 325bp(5)(a) as replaced by CRR3 point (188)(a)(i): 0,01 % for 0 % RW sovereign-type
exposures (Arts 114-118) and 10 %-RW covered bonds (Art 129); otherwise 0,03 %."""
IMA_DRC_LGD_FLOOR: Final[float] = 0.0
"""Article 325bp(6)(a)."""
IMA_SES_RHO: Final[float | None] = None
"""Article 325bk(3)(d): aggregation of stress scenario risk measures is left to an EBA RTS.
# TODO: VERIFY -- SES aggregation correlation not in the supplied texts."""
IMA_PLA_SPEARMAN: Final[tuple[float, float] | None] = None
IMA_PLA_KS: Final[tuple[float, float] | None] = None
"""Article 325bg(4)(a) (CRR3 point (184)): 'close' / 'sufficiently close' criteria are left to an
EBA RTS. # TODO: VERIFY -- PLA thresholds not in the supplied texts."""
AIMA_PLA_DEROGATION_END: Final[date] = date(2026, 1, 1)
"""Article 495h (CRR3 point (242)): AIMA may be used until 1 January 2026 for desks not meeting
Article 325bg."""

# =========================================================================
#  SSA -- position risk in debt instruments, Articles 336, 339, 340 (C2)
# =========================================================================

SSA_SPECIFIC_RISK_ZERO: Final[float] = 0.0
"""Article 336(1) Table 1: debt with a 0 % SA risk weight."""
SSA_SPECIFIC_RISK_QUALIFYING: Final[tuple[tuple[float, float], ...]] = (
    (0.5, 0.0025),
    (2.0, 0.0100),
)
"""Article 336(1) Table 1: 20 %/50 % SA RW and other qualifying items -- 0,25 % (residual term
<= 6 months), 1,00 % (> 6 and <= 24 months)."""
SSA_SPECIFIC_RISK_QUALIFYING_LONG: Final[float] = 0.0160
"""Article 336(1) Table 1: 1,60 % (residual term > 24 months)."""
SSA_SPECIFIC_RISK_100: Final[float] = 0.08
"""Article 336(1) Table 1: debt with a 100 % SA risk weight."""
SSA_SPECIFIC_RISK_150: Final[float] = 0.12
"""Article 336(1) Table 1: debt with a 150 % SA risk weight."""
SSA_COVERED_BOND_10PCT_FACTOR: Final[float] = 0.5
"""Article 336(3): 10 %-RW covered bonds -- half of the second-category requirement."""
SSA_SECURITISATION_RW_FACTOR: Final[float] = 0.08
"""Article 337(1): 8 % of the non-trading-book securitisation risk weight."""

SSA_MATURITY_BANDS: Final[tuple[tuple[int, float, float, float, float], ...]] = (
    # (zone, upper bound coupon >= 3 % (years), upper bound coupon < 3 % (years), weight, dr)
    (1, 1 / 12, 1 / 12, 0.0000, 0.0),
    (1, 3 / 12, 3 / 12, 0.0020, 1.00),
    (1, 6 / 12, 6 / 12, 0.0040, 1.00),
    (1, 1.0, 1.0, 0.0070, 1.00),
    (2, 2.0, 1.9, 0.0125, 0.90),
    (2, 3.0, 2.8, 0.0175, 0.80),
    (2, 4.0, 3.6, 0.0225, 0.75),
    (3, 5.0, 4.3, 0.0275, 0.75),
    (3, 7.0, 5.7, 0.0325, 0.70),
    (3, 10.0, 7.3, 0.0375, 0.65),
    (3, 15.0, 9.3, 0.0450, 0.60),
    (3, 20.0, 10.6, 0.0525, 0.60),
    (3, math.inf, 12.0, 0.0600, 0.60),
    (3, math.inf, 20.0, 0.0800, 0.60),
    (3, math.inf, math.inf, 0.1250, 0.60),
)
"""Article 339(4) Table 2: maturity bands (coupon >= 3 % / < 3 %), weighting (in %), assumed
interest-rate change (in %). The last two rows exist only for coupons below 3 % (the coupon
>= 3 % column ends at '> 20 years' = 6,00 %)."""
SSA_COUPON_THRESHOLD: Final[float] = 0.03
"""Article 339(2): coupon of 3 % or more vs less than 3 %."""
SSA_GR_MATCHED_BAND: Final[float] = 0.10
SSA_GR_MATCHED_ZONE: Final[dict[int, float]] = {1: 0.40, 2: 0.30, 3: 0.30}
SSA_GR_MATCHED_ADJACENT_ZONES: Final[float] = 0.40
SSA_GR_MATCHED_ZONES_1_3: Final[float] = 1.50
SSA_GR_RESIDUAL: Final[float] = 1.00
"""Article 339(9)(a)-(g)."""
SSA_DURATION_ZONES: Final[tuple[tuple[int, float, float], ...]] = (
    (1, 1.0, 0.010),
    (2, 3.6, 0.0085),
    (3, math.inf, 0.007),
)
"""Article 340(4) Table 3: zone, modified duration upper bound (years), assumed rate change."""
SSA_DURATION_MATCHED_ZONE: Final[float] = 0.02
"""Article 340(7)(a): 2 % of the matched duration-weighted position for each zone ((b)-(d) as
Article 339)."""

# --- Equity, CIU, FX, commodity (SSA) -----------------------------------
SSA_EQUITY_SPECIFIC: Final[float] = 0.08
"""Article 342: overall gross position x 8 %."""
SSA_EQUITY_GENERAL: Final[float] = 0.08
"""Article 343: overall net position x 8 %."""
SSA_CIU_POSITION_RISK: Final[float] = 0.32
SSA_CIU_POSITION_AND_FX: Final[float] = 0.40
"""Article 348(1) as replaced by CRR3 point (192): 32 % (position risk); 40 % (position + FX)."""
SSA_FX_RATE: Final[float] = 0.08
SSA_FX_DE_MINIMIS: Final[float] = 0.02
"""Article 351 as replaced by CRR3 point (193): if net FX + net gold > 2 % of total own funds,
OFR = (overall net FX position + net gold position) x 8 %."""
SSA_FX_CLOSELY_CORRELATED: Final[float] = 0.04
"""Article 354(1): matched positions in closely correlated currencies x 4 %."""
SSA_FX_ERM2_MATCHED: Final[float] = 0.016
"""Article 354(4): matched positions in ERM II currencies x 1,6 %."""
SSA_COMMODITY_SPREAD: Final[float] = 0.015
SSA_COMMODITY_CARRY: Final[float] = 0.006
SSA_COMMODITY_OUTRIGHT: Final[float] = 0.15
"""Article 359(1) Table 1 (spread 1,50 % in every band) and 359(5)(b)-(c) (carry 0,6 %, outright
15 %)."""
SSA_COMMODITY_BANDS: Final[tuple[float, ...]] = (1 / 12, 3 / 12, 6 / 12, 1.0, 2.0, 3.0, math.inf)
"""Article 359(1) Table 1 maturity bands (upper bounds in years)."""
SSA_COMMODITY_SIMPLE_NET: Final[float] = 0.15
SSA_COMMODITY_SIMPLE_GROSS: Final[float] = 0.03
"""Article 360(1)(a)-(b)."""
SSA_COMMODITY_EXTENDED: Final[dict[str, tuple[float, float, float]]] = {
    "PRECIOUS_METALS": (0.010, 0.003, 0.08),
    "BASE_METALS": (0.012, 0.005, 0.10),
    "AGRICULTURAL": (0.015, 0.006, 0.12),
    "OTHER": (0.015, 0.006, 0.15),
}
"""Article 361 Table 2 (spread, carry, outright): precious metals (except gold), base metals,
agricultural products (softs), other incl. energy."""

# =========================================================================
#  Application dates and transitional provisions
# =========================================================================

CRR3_APPLICATION_DATE: Final[date] = date(2025, 1, 1)
"""CRR3 Article 2 second paragraph: applies from 1 January 2025 (points (156)(b), (159)(c),
(160)(c), (164)(b), (178)(e), (180), (182)(d), (183)(c), (184)(b)(iii) apply from 9 July 2024)."""
CRR3_EARLY_POINTS_DATE: Final[date] = date(2024, 7, 9)
MARKET_RISK_MAX_POSTPONEMENT_YEARS: Final[int] = 2
"""Article 461a(2)(b) (CRR3 point (236)): the Commission may postpone the market-risk own funds
requirements by up to two years by delegated act. The delegated acts themselves are not in the
supplied texts. # TODO: VERIFY -- actual EU application date of the FRTB own funds requirements
(postponement delegated acts are outside the supplied texts)."""
MARKET_RISK_TARGETED_MULTIPLIER_RANGE: Final[tuple[float, float]] = (0.0, 1.0)
"""Article 461a(2)(a): targeted multipliers >= 0 and < 1 for specific risk classes / risk
factors, for up to three years absent a legislative act."""

CQS_OF_RATING: Final[dict[RatingBucket, int]] = {
    RatingBucket.AAA_TO_AA_MINUS: 1,
    RatingBucket.A_PLUS_TO_A_MINUS: 2,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS: 3,
    RatingBucket.BB_PLUS_TO_BB_MINUS: 4,
    RatingBucket.B_PLUS_TO_B_MINUS: 5,
    RatingBucket.BELOW_B_MINUS: 6,
}
"""Article 136 credit quality steps (same mapping as ``src.jurisdictions.eu.params``); used for
Article 325y(6) and Article 325ah(1) (CRR3 points (167), (171))."""
IG_CQS_MAX: Final[int] = 3
"""Credit quality steps 1 to 3 = Table 4 investment-grade block."""
