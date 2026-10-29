"""OSFI CAR 2026 Chapter 9 -- Default risk capital (DRC) requirement, standardized approach.

CAR 9.5.3 ¶214-258 [Basel Framework MAR22]:

* non-securitisations (¶222-239): gross JTD(long) = max(LGD × notional + P&L, 0), JTD(short) =
  min(LGD × notional + P&L, 0) (¶224); LGD by seniority (¶225); maturity scaling of the gross
  JTD by min(max(M, 3 months), 1 year) / 1 year (¶228-231, footnote 50); offsetting within an
  obligor where the short is of the same or lower seniority (¶232); three buckets (¶235); HBR =
  Σ net long / (Σ net long + Σ |net short|) (¶236); DRC_b = max[Σ RW·long − HBR·Σ RW·|short|; 0]
  (¶238); total = simple sum (¶239). Canadian / US sovereign, central bank and 0%-RW PSE and MDB
  exposures take 0%, other IG sovereigns with local presence and local funding 0.5% (¶220);
  provincial / territorial governments are treated as the Government of Canada (¶237);
* securitisation non-CTP (¶240-248): JTD = market value (no LGD); offsetting only within the
  same tranche of the same pool; buckets by asset class × region with a single corporates bucket;
  default RW from the Chapter 6 banking-book RW (× 8%), capped at fair value; simple sum;
* CTP (¶249-258): index buckets; HBR_ctp across all CTP positions; DRC_b may be negative;
  DRC_CTP = max[Σ_b (max[DRC_b, 0] + 0.5 × min[DRC_b, 0]), 0].

Input conventions (``DRCPositionInput``):

* ``notional`` is the bond-equivalent notional (>= 0); direction from ``is_long``;
* P&L: if ``pnl`` is non-zero it is used as the signed P&L of ¶226 (loss negative); otherwise it
  is derived as market value − notional for longs and notional − |market value| for shorts
  (¶224(2), ¶226 sign convention);
* ``flags`` keys: ``price_not_linked_to_recovery`` (LGD not applied, ¶225(4)),
  ``gse_non_tranched_mbs`` (LGD 75% unless ``covered_bond_qualifying``),
  ``canadian_sovereign_zero_rw`` / ``us_sovereign_zero_rw`` / ``mdb_zero_rw`` (0%, ¶220),
  ``other_ig_sovereign_local_funded`` (0.5%, ¶220), ``canadian_province_or_agent`` (treated as
  the Government of Canada -> sovereign bucket, 0%), ``rating_aaa`` (separates AAA from AA in
  Table 15 -- the shared ``RatingBucket`` merges AAA..AA-), ``rating_ccc_or_below`` (CCC, else
  BELOW_B- maps to CCC anyway), ``sec_corporate`` / ``sec_abcp`` / ``sec_cdo_squared`` /
  ``sec_sme`` / ``sec_other_retail`` / ``sec_other_wholesale`` (non-CTP asset classes absent
  from ``SecAssetClass``), ``ctp_non_tranched`` (CTP single-name / index hedge -> Table 15 RW).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.ca.frtb import params as p
from src.jurisdictions.ca.frtb.buckets import is_investment_grade
from src.jurisdictions.frtb_base import (
    CreditSector,
    DRCKind,
    DRCPositionInput,
    DRCSeniority,
    SecAssetClass,
)

_SENIORITY_RANK: dict[DRCSeniority, int] = {
    DRCSeniority.EQUITY: 0,
    DRCSeniority.NON_SENIOR: 1,
    DRCSeniority.SENIOR: 2,
    DRCSeniority.COVERED_BOND: 3,
}
"""Higher = more senior (CAR ¶232(1): a short may offset a long of the same or higher
seniority; e.g. "a short exposure in an equity may offset a long exposure in a bond")."""

_RATING_CATEGORY: dict[RatingBucket, str] = {
    RatingBucket.AAA_TO_AA_MINUS: "AA",
    RatingBucket.A_PLUS_TO_A_MINUS: "A",
    RatingBucket.BBB_PLUS_TO_BBB_MINUS: "BBB",
    RatingBucket.BB_PLUS_TO_BB_MINUS: "BB",
    RatingBucket.B_PLUS_TO_B_MINUS: "B",
    RatingBucket.BELOW_B_MINUS: "CCC",
    RatingBucket.UNRATED: "Unrated",
}
"""RatingBucket -> Table 15 credit quality category (CAR ¶237). AAA..AA- maps to AA (2%) unless
``flags['rating_aaa']`` -- conservative, as the shared enum does not separate AAA."""

_SEC_ASSET_CLASS_NAME: dict[SecAssetClass, str] = {
    SecAssetClass.RMBS_PRIME: "residential MBS",
    SecAssetClass.RMBS_MIDPRIME: "residential MBS",
    SecAssetClass.RMBS_SUBPRIME: "residential MBS",
    SecAssetClass.CMBS: "commercial MBS",
    SecAssetClass.ABS_STUDENT_LOANS: "student loans",
    SecAssetClass.ABS_CREDIT_CARDS: "credit cards",
    SecAssetClass.ABS_AUTO: "auto loans/leases",
    SecAssetClass.CLO_NON_CTP: "collateralized loan obligations",
}
_SEC_FLAG_ASSET_CLASS: dict[str, str] = {
    "sec_abcp": "asset-backed commercial paper",
    "sec_cdo_squared": "CDO-squared",
    "sec_sme": "small and medium enterprises",
    "sec_other_retail": "other retail",
    "sec_other_wholesale": "other wholesale",
}
_REGION_ALIASES: dict[str, str] = {
    "asia": "Asia", "europe": "Europe", "north america": "North America",
    "northamerica": "North America", "na": "North America", "us": "North America",
    "ca": "North America", "all other": "all other", "other": "all other",
}


# =========================================================================
#  Gross JTD
# =========================================================================


def lgd(pos: DRCPositionInput) -> float:
    """LGD for the gross JTD (CAR 9.5.3.4 ¶225 [MAR22.12]).

    Equity and non-senior debt 100%; senior debt 75%; covered bonds 25%; 1.0 (no LGD
    multiplication) where the price is not linked to the recovery rate; non-tranched GSE MBS 75%
    unless they qualify as covered bonds (footnote 40 to ¶163).
    """
    if pos.flags.get("price_not_linked_to_recovery", False):
        return 1.0
    if pos.flags.get("gse_non_tranched_mbs", False):
        if pos.flags.get("covered_bond_qualifying", False):
            return p.DRC_LGD_COVERED_BOND
        return p.DRC_LGD_SENIOR
    return {
        DRCSeniority.EQUITY: p.DRC_LGD_EQUITY,
        DRCSeniority.NON_SENIOR: p.DRC_LGD_NON_SENIOR,
        DRCSeniority.SENIOR: p.DRC_LGD_SENIOR,
        DRCSeniority.COVERED_BOND: p.DRC_LGD_COVERED_BOND,
    }[pos.seniority]


def signed_pnl(pos: DRCPositionInput) -> float:
    """Signed cumulative P&L of ¶224(2)/¶226 (loss negative, gain positive)."""
    if pos.pnl != 0.0:
        return pos.pnl
    if pos.is_long:
        return pos.market_value - pos.notional
    return pos.notional - abs(pos.market_value)


def gross_jtd_nonsec(pos: DRCPositionInput) -> float:
    """Gross JTD (CAR ¶224 [MAR22.11]): long max(LGD·N + P&L, 0); short min(LGD·N + P&L, 0).

    The notional of a short is recorded as negative (¶226 [MAR22.13]).
    """
    n = pos.notional if pos.is_long else -pos.notional
    raw = lgd(pos) * n + signed_pnl(pos)
    return max(raw, 0.0) if pos.is_long else min(raw, 0.0)


def gross_jtd_sec(pos: DRCPositionInput) -> float:
    """Securitisation gross JTD = market value, no LGD (CAR ¶240, ¶249-250 [MAR22.27, 22.36-37])."""
    mv = abs(pos.market_value)
    return mv if pos.is_long else -mv


def maturity_weight(maturity_years: float) -> float:
    """min(max(M, 0.25), 1) / 1 (CAR ¶228, ¶231 [MAR22.15, MAR22.18])."""
    m = min(max(maturity_years, p.DRC_MATURITY_FLOOR_YEARS), p.DRC_CAPITAL_HORIZON_YEARS)
    return m / p.DRC_CAPITAL_HORIZON_YEARS


# =========================================================================
#  Risk weights and buckets (non-securitisation)
# =========================================================================


def _is_zero_rw_sovereign(pos: DRCPositionInput) -> bool:
    f = pos.flags
    return any(
        f.get(k, False)
        for k in ("canadian_sovereign_zero_rw", "us_sovereign_zero_rw", "mdb_zero_rw",
                  "canadian_province_or_agent")
    )


def credit_quality_category(pos: DRCPositionInput) -> str:
    """Table 15 credit quality category (CAR ¶237 [MAR22.24])."""
    if pos.is_defaulted:
        return "Defaulted"
    if pos.flags.get("rating_aaa", False) and pos.rating == RatingBucket.AAA_TO_AA_MINUS:
        return "AAA"
    return _RATING_CATEGORY[pos.rating]


def default_risk_weight_nonsec(pos: DRCPositionInput) -> float:
    """Default risk weight (CAR ¶220, ¶237 Table 15 [MAR22.7, MAR22.24])."""
    if pos.is_defaulted:
        return p.DRC_RW_BY_CATEGORY["Defaulted"]
    if _is_zero_rw_sovereign(pos):
        return p.DRC_RW_CANADA_US_MDB_ZERO
    if pos.flags.get("other_ig_sovereign_local_funded", False) and is_investment_grade(
        pos.rating, pos.is_investment_grade
    ):
        return p.DRC_RW_OTHER_IG_SOVEREIGN_LOCAL
    return p.DRC_RW_BY_CATEGORY[credit_quality_category(pos)]


def nonsec_bucket(pos: DRCPositionInput) -> str:
    """Non-securitisation DRC bucket (CAR ¶235 [MAR22.22])."""
    if pos.flags.get("canadian_province_or_agent", False):
        return "sovereigns"
    if pos.credit_sector == CreditSector.SOVEREIGN:
        return "sovereigns"
    if pos.credit_sector == CreditSector.LOCAL_GOVERNMENT:
        return "local governments and municipalities"
    return "corporates"


# =========================================================================
#  Offsetting
# =========================================================================


@dataclass
class NetJTD:
    """A net JTD position after offsetting (sign = direction)."""

    amount: float
    risk_weight: float
    bucket: str


def _offset_obligor(
    longs: list[tuple[int, float, float]], shorts: list[tuple[int, float, float]],
) -> tuple[list[tuple[int, float, float]], list[tuple[int, float, float]]]:
    """Offset (rank, |JTD|, RW) lists within an obligor (CAR ¶232 [MAR22.19]).

    A short of rank r offsets longs of rank >= r. Shorts are processed from the most senior (most
    restrictive) down; each consumes eligible longs from the lowest eligible rank upward, which
    maximises the recognised offset for nested eligibility sets.
    """
    lg_left = [[float(r), a, w] for r, a, w in sorted(longs, key=lambda x: x[0])]
    sh_left = [[float(r), a, w] for r, a, w in sorted(shorts, key=lambda x: -x[0])]
    for sh in sh_left:
        for lg in lg_left:
            if sh[1] <= 0.0:
                break
            if lg[0] >= sh[0] and lg[1] > 0.0:
                m = min(sh[1], lg[1])
                sh[1] -= m
                lg[1] -= m
    return (
        [(int(x[0]), x[1], x[2]) for x in lg_left if x[1] > 0.0],
        [(int(x[0]), x[1], x[2]) for x in sh_left if x[1] > 0.0],
    )


def net_jtd_nonsec(positions: list[DRCPositionInput]) -> list[NetJTD]:
    """Gross JTD × maturity weight, then offset per obligor (CAR ¶224-234 [MAR22.9-22.21])."""
    by_obligor: dict[str, tuple[list[tuple[int, float, float]], list[tuple[int, float, float]]]]
    by_obligor = defaultdict(lambda: ([], []))
    bucket_of: dict[str, str] = {}
    for pos in positions:
        jtd = gross_jtd_nonsec(pos) * maturity_weight(pos.maturity_years)
        rank = _SENIORITY_RANK[pos.seniority]
        rw = default_risk_weight_nonsec(pos)
        bucket_of.setdefault(pos.obligor, nonsec_bucket(pos))
        if jtd > 0.0:
            by_obligor[pos.obligor][0].append((rank, jtd, rw))
        elif jtd < 0.0:
            by_obligor[pos.obligor][1].append((rank, -jtd, rw))
    out: list[NetJTD] = []
    for obligor, (longs, shorts) in by_obligor.items():
        rl, rs = _offset_obligor(longs, shorts)
        b = bucket_of[obligor]
        out.extend(NetJTD(a, rw, b) for _, a, rw in rl)
        out.extend(NetJTD(-a, rw, b) for _, a, rw in rs)
    return out


def hbr(net: list[NetJTD]) -> float:
    """HBR = Σ net long / (Σ net long + Σ |net short|) (CAR ¶236 [MAR22.23]); 0 if empty."""
    long_sum = sum(n.amount for n in net if n.amount > 0.0)
    short_sum = sum(-n.amount for n in net if n.amount < 0.0)
    denom = long_sum + short_sum
    return long_sum / denom if denom > 0.0 else 0.0


def bucket_drc(net: list[NetJTD], ratio: float, floor_at_zero: bool = True) -> float:
    """DRC_b = [Σ RW·long − HBR·Σ RW·|short|], floored at 0 except for the CTP (¶238, ¶256)."""
    long_rw = sum(n.risk_weight * n.amount for n in net if n.amount > 0.0)
    short_rw = sum(n.risk_weight * -n.amount for n in net if n.amount < 0.0)
    val = long_rw - ratio * short_rw
    return max(val, 0.0) if floor_at_zero else val


def drc_nonsec(positions: list[DRCPositionInput]) -> tuple[float, dict[str, float]]:
    """Non-securitisation DRC: per-bucket HBR and simple sum (CAR ¶235-239 [MAR22.22-22.26])."""
    net = net_jtd_nonsec(positions)
    by_bucket: dict[str, list[NetJTD]] = defaultdict(list)
    for n in net:
        by_bucket[n.bucket].append(n)
    detail = {b: bucket_drc(lst, hbr(lst)) for b, lst in by_bucket.items()}
    return sum(detail.values()), detail


# =========================================================================
#  Securitisation non-CTP and CTP
# =========================================================================


def sec_default_risk_weight(pos: DRCPositionInput) -> float:
    """Banking-book securitisation RW × 8%, capped at fair value (CAR ¶247 [MAR22.34]).

    Missing RW -> conservative 1,250% placeholder.
    """
    bb = pos.banking_book_risk_weight
    rw = (p.DRC_SEC_MISSING_BB_RW if bb is None else bb) * p.DRC_SEC_RW_CONVERSION
    return min(rw, p.DRC_SEC_FAIR_VALUE_CAP)


def sec_nonctp_bucket(pos: DRCPositionInput) -> str:
    """Non-CTP bucket: corporates (all regions) or asset class × region (CAR ¶244-245)."""
    if pos.flags.get("sec_corporate", False):
        return "corporates"
    asset: str | None = None
    for flag, name in _SEC_FLAG_ASSET_CLASS.items():
        if pos.flags.get(flag, False):
            asset = name
            break
    if asset is None and pos.sec_asset_class is not None:
        asset = _SEC_ASSET_CLASS_NAME.get(pos.sec_asset_class)
    region = _REGION_ALIASES.get(pos.region.strip().lower()) if pos.region else None
    if asset is None or region is None:
        return "other bucket"
    return f"{asset} | {region}"


def _net_by_tranche(
    positions: list[DRCPositionInput],
    rw_fn: Callable[[DRCPositionInput], float],
    bucket_fn: Callable[[DRCPositionInput], str],
) -> list[NetJTD]:
    """Offset only identical exposures (CAR ¶242-243 [MAR22.29-22.30], ¶252 [MAR22.39]).

    Positions net when they share pool (underlying portfolio / index series) and tranche, across
    maturities after maturity scaling; different tranches or pools never offset. Decomposition /
    replication offsets (¶243(1)-(2), ¶252(3)-(4)) must be applied by the caller before input.
    """
    sums: dict[tuple[str, str], float] = defaultdict(float)
    rw_of: dict[tuple[str, str], float] = {}
    bucket_of: dict[tuple[str, str], str] = {}
    for pos in positions:
        key = (pos.pool_id, pos.tranche_id or pos.position_id)
        sums[key] += gross_jtd_sec(pos) * maturity_weight(pos.maturity_years)
        rw_of[key] = rw_fn(pos)
        bucket_of[key] = bucket_fn(pos)
    return [
        NetJTD(amount, rw_of[key], bucket_of[key]) for key, amount in sums.items() if amount != 0.0
    ]


def drc_sec_nonctp(positions: list[DRCPositionInput]) -> tuple[float, dict[str, float]]:
    """Securitisation non-CTP DRC (CAR ¶240-248 [MAR22.27-22.35])."""
    net = _net_by_tranche(positions, sec_default_risk_weight, sec_nonctp_bucket)
    by_bucket: dict[str, list[NetJTD]] = defaultdict(list)
    for n in net:
        by_bucket[n.bucket].append(n)
    detail = {b: bucket_drc(lst, hbr(lst)) for b, lst in by_bucket.items()}
    return sum(detail.values()), detail


def ctp_risk_weight(pos: DRCPositionInput) -> float:
    """CTP RW: Table 15 for non-tranched products, banking-book RW for tranches (CAR ¶256)."""
    if pos.flags.get("ctp_non_tranched", False):
        return default_risk_weight_nonsec(pos)
    return sec_default_risk_weight(pos)


def _ctp_bucket(pos: DRCPositionInput) -> str:
    """Each index is its own bucket; bespokes go to their index (CAR ¶253-254 [MAR22.40-41])."""
    return pos.pool_id or pos.obligor


def drc_ctp(positions: list[DRCPositionInput]) -> tuple[float, dict[str, float]]:
    """CTP DRC (CAR ¶249-258 [MAR22.36-22.45]).

    HBR_ctp from all CTP positions; DRC_b not floored; total = max[Σ(max[DRC_b,0] +
    0.5·min[DRC_b,0]), 0].
    """
    net = _net_by_tranche(positions, ctp_risk_weight, _ctp_bucket)
    ratio = hbr(net)
    by_bucket: dict[str, list[NetJTD]] = defaultdict(list)
    for n in net:
        by_bucket[n.bucket].append(n)
    detail = {b: bucket_drc(lst, ratio, floor_at_zero=False) for b, lst in by_bucket.items()}
    total = sum(
        max(v, 0.0) + p.DRC_CTP_NEGATIVE_BUCKET_WEIGHT * min(v, 0.0) for v in detail.values()
    )
    return max(total, 0.0), detail


def drc_capital(positions: list[DRCPositionInput]) -> dict[str, float]:
    """DRC by component, no diversification between them (CAR ¶217 [MAR22.4])."""
    nonsec, _ = drc_nonsec([x for x in positions if x.kind == DRCKind.NON_SECURITISATION])
    sec, _ = drc_sec_nonctp([x for x in positions if x.kind == DRCKind.SEC_NON_CTP])
    ctp, _ = drc_ctp([x for x in positions if x.kind == DRCKind.CTP])
    return {"nonsec": nonsec, "sec_nonctp": sec, "ctp": ctp, "total": nonsec + sec + ctp}
