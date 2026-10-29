"""UK default risk charge (DRC) -- PRA Market Risk: Advanced Standardised Approach Part, Section 5.

Implements Articles 325v-325ad (p. 335-343):

* non-securitisations (Art 325w-325y): gross JTD = V_A - V_D with V_D the value after default
  with recovery (1 - LGD) on the face value (LGD 100% non-senior / 75% senior / 25% covered
  bonds; equity full loss); maturity scaling min(max(M, 3 months), 1 year)/1 year; offsetting
  within an obligor only where the short is of the same or lower seniority than the long;
  default risk weights by credit quality (Table 2, 0% where the SA weight is 0%); three buckets;
  DRC_b = max{sum RW*JTD_long - WtS * sum RW*|JTD_short|; 0}, WtS = sum long / (sum long +
  sum |short|); simple sum over buckets;
* securitisations not in the ACTP (Art 325z-325aa): gross JTD = market value; offsetting only
  within the same pool and tranche; RW = 8% x banking-book RW; cap at fair value for cash
  securitisations; one corporate bucket + 11 asset classes x 4 regions;
* ACTP (Art 325ab-325ad): RW = Table 2 (non-tranched) or 8% x banking-book RW (tranched);
  buckets = indices; WtS_ACTP over the whole ACTP; DRC_ACTP = max{sum [max(DRC_b, 0) +
  0.5 min(DRC_b, 0)]; 0}.

Input convention (contract :class:`DRCPositionInput`): ``notional`` is the face value and
``market_value`` the current (unsigned) value of the instrument or of its reference obligation;
the direction comes from ``is_long``. ``pnl`` is not used: the UK rule is expressed through V_A
and V_D, and V_A - V_D = market_value - (1 - LGD) x notional (= LGD x notional + (market_value -
notional), the MAR22.13 form).

Flags read (``DRCPositionInput.flags``): ``sa_zero_risk_weight`` (Art 325y(2)), ``rating_aaa``
(Table 2 AAA row; the contract merges AAA with AA), ``unwind_without_default_exposure``
(Art 325w(7)), ``default_reflected_in_value`` (Art 325w(6)), ``rw_art_259_263`` (Art 325aa(2)
one-year maturity), ``cash_securitisation`` (Art 325aa(3) cap), ``sec_corporate_bucket``,
``abcp``, ``cdo_squared``, ``sme``, ``other_retail`` (Art 325aa(4)-(5) bucket mapping).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.frtb_base import (
    CreditSector,
    DRCKind,
    DRCPositionInput,
    DRCSeniority,
    SecAssetClass,
)
from src.jurisdictions.uk.frtb import params as p

SENIORITY_RANK: dict[DRCSeniority, int] = {
    DRCSeniority.COVERED_BOND: 0,
    DRCSeniority.SENIOR: 1,
    DRCSeniority.NON_SENIOR: 2,
    DRCSeniority.EQUITY: 3,
}
"""Seniority order for Art 325x(1) (higher = more junior)."""


@dataclass(frozen=True)
class NetJTD:
    """A net (maturity-scaled) JTD amount with its default risk weight and bucket."""

    obligor: str
    amount: float
    """Positive = long, negative = short."""
    risk_weight: float
    bucket: str
    cap: float | None = None
    """Fair-value cap on |RW x JTD| (Art 325aa(3)); None = uncapped."""


# =========================================================================
#  Common helpers
# =========================================================================


def lgd(pos: DRCPositionInput) -> float:
    """LGD by seniority (Art 325w(3), p. 337; equity full loss, Art 325w(4))."""
    return {
        DRCSeniority.NON_SENIOR: p.DRC_LGD_NON_SENIOR,
        DRCSeniority.SENIOR: p.DRC_LGD_SENIOR,
        DRCSeniority.COVERED_BOND: p.DRC_LGD_COVERED_BOND,
        DRCSeniority.EQUITY: p.DRC_LGD_EQUITY,
    }[pos.seniority]


def maturity_factor(maturity_years: float) -> float:
    """min(max(M, 3 months), 1 year) / 1 year (Art 325x(2)(b) and (3), p. 337-338)."""
    return min(max(maturity_years, p.DRC_MATURITY_FLOOR_YEARS), p.DRC_MATURITY_CAP_YEARS) / (
        p.DRC_MATURITY_CAP_YEARS
    )


def gross_jtd(pos: DRCPositionInput) -> float:
    """Signed gross JTD of a non-securitisation position (Art 325w(1)-(7), p. 336-337).

    Long: max{V_A - V_D; 0}; short: min{V_A - V_D; 0} with the short's V_A and V_D negative.
    """
    if pos.flags.get("unwind_without_default_exposure"):
        return 0.0  # Art 325w(7)
    if pos.is_defaulted and pos.flags.get("default_reflected_in_value"):
        return 0.0  # Art 325w(6)
    if pos.seniority is DRCSeniority.EQUITY:
        loss = pos.market_value  # V_D = 0: 'a full loss in value' (Art 325w(4))
    else:
        loss = pos.market_value - (1.0 - lgd(pos)) * pos.notional  # V_A - V_D (Art 325w(1))
    return max(loss, 0.0) if pos.is_long else min(-loss, 0.0)


def default_risk_weight(pos: DRCPositionInput) -> float:
    """Default risk weight (Art 325y(1) Table 2 and (2), p. 338-339)."""
    if pos.flags.get("sa_zero_risk_weight"):
        return p.DRC_SA_ZERO_RW
    if pos.is_defaulted:
        return p.DRC_RW_BY_RATING["DEFAULTED"]
    if pos.rating is RatingBucket.AAA_TO_AA_MINUS and pos.flags.get("rating_aaa"):
        return p.DRC_RW_BY_RATING["AAA"]
    return p.DRC_RW_BY_RATING_BUCKET[pos.rating]


def nonsec_bucket(pos: DRCPositionInput) -> str:
    """Corporates, sovereigns, local governments/municipalities (Art 325y(3), p. 339)."""
    if pos.credit_sector is CreditSector.SOVEREIGN:
        return p.DRC_BUCKETS[1]
    if pos.credit_sector is CreditSector.LOCAL_GOVERNMENT:
        return p.DRC_BUCKETS[2]
    return p.DRC_BUCKETS[0]


def hedge_benefit_ratio(longs: float, shorts_abs: float) -> float:
    """WtS = sum net JTD long / (sum net JTD long + sum |net JTD short|) (Art 325y(4), p. 339)."""
    denom = longs + shorts_abs
    return longs / denom if denom > 0.0 else 0.0


def bucket_drc(items: list[NetJTD], wts: float, floor: bool = True) -> float:
    """DRC_b = max{sum RW*JTD_long - WtS * sum RW*|JTD_short|; 0} (Art 325y(4), 325ad(3))."""

    def weighted(n: NetJTD) -> float:
        w = n.risk_weight * abs(n.amount)
        return min(w, n.cap) if n.cap is not None else w

    long_rw = sum(weighted(n) for n in items if n.amount > 0.0)
    short_rw = sum(weighted(n) for n in items if n.amount < 0.0)
    val = long_rw - wts * short_rw
    return max(val, 0.0) if floor else val


# =========================================================================
#  Non-securitisations
# =========================================================================


@dataclass
class _Leg:
    """Mutable remaining JTD of one position during offsetting."""

    amount: float
    pos: DRCPositionInput

    @property
    def rank(self) -> int:
        """Seniority rank of the position (higher = more junior)."""
        return SENIORITY_RANK[self.pos.seniority]


def net_obligor(positions: list[DRCPositionInput]) -> list[NetJTD]:
    """Net JTD for one obligor (Art 325x(1)-(3), p. 337-338).

    JTDs are maturity-scaled, then shorts offset longs only where the short has the same or
    lower seniority than the long. Shorts are processed from the most senior (most constrained)
    and offset the most junior eligible long first, which maximises recognised offsetting under
    the nested eligibility sets.
    """
    longs: list[_Leg] = []
    shorts: list[_Leg] = []
    for pos in positions:
        j = gross_jtd(pos) * maturity_factor(pos.maturity_years)
        if j > 0.0:
            longs.append(_Leg(j, pos))
        elif j < 0.0:
            shorts.append(_Leg(-j, pos))
    shorts.sort(key=lambda e: e.rank)
    for s in shorts:
        eligible = sorted(
            (lg for lg in longs if lg.rank <= s.rank and lg.amount > 0.0),
            key=lambda e: -e.rank,
        )
        for lg in eligible:
            m = min(lg.amount, s.amount)
            lg.amount -= m
            s.amount -= m
            if s.amount <= 0.0:
                break
    out: list[NetJTD] = []
    for leg, sign in [(lg, 1.0) for lg in longs] + [(sh, -1.0) for sh in shorts]:
        if leg.amount > 0.0:
            out.append(
                NetJTD(
                    leg.pos.obligor,
                    sign * leg.amount,
                    default_risk_weight(leg.pos),
                    nonsec_bucket(leg.pos),
                )
            )
    return out


def nonsec_net_jtds(positions: list[DRCPositionInput]) -> list[NetJTD]:
    """Net JTD amounts for all non-securitisation positions, grouped by obligor."""
    by_obligor: dict[str, list[DRCPositionInput]] = defaultdict(list)
    for pos in positions:
        by_obligor[pos.obligor].append(pos)
    out: list[NetJTD] = []
    for group in by_obligor.values():
        out.extend(net_obligor(group))
    return out


def drc_nonsec_by_bucket(positions: list[DRCPositionInput]) -> dict[str, float]:
    """Bucket-level DRC for non-securitisations (Art 325y(3)-(4), p. 339)."""
    nets = nonsec_net_jtds(positions)
    by_bucket: dict[str, list[NetJTD]] = defaultdict(list)
    for n in nets:
        by_bucket[n.bucket].append(n)
    out: dict[str, float] = {}
    for b, items in by_bucket.items():
        longs = sum(n.amount for n in items if n.amount > 0.0)
        shorts = sum(-n.amount for n in items if n.amount < 0.0)
        out[b] = bucket_drc(items, hedge_benefit_ratio(longs, shorts))
    return out


def drc_nonsec(positions: list[DRCPositionInput]) -> float:
    """Non-securitisation DRC = simple sum of bucket requirements (Art 325y(5), p. 339)."""
    return sum(drc_nonsec_by_bucket(positions).values())


# =========================================================================
#  Securitisations not in the ACTP
# =========================================================================

_REGION: dict[str, str] = {
    "ASIA": p.DRC_SEC_REGIONS[0],
    "EUROPE": p.DRC_SEC_REGIONS[1],
    "NORTH AMERICA": p.DRC_SEC_REGIONS[2],
    "NORTH_AMERICA": p.DRC_SEC_REGIONS[2],
}

_ASSET: dict[SecAssetClass, str] = {
    SecAssetClass.ABS_AUTO: p.DRC_SEC_ASSET_CLASSES[1],
    SecAssetClass.RMBS_PRIME: p.DRC_SEC_ASSET_CLASSES[2],
    SecAssetClass.RMBS_MIDPRIME: p.DRC_SEC_ASSET_CLASSES[2],
    SecAssetClass.RMBS_SUBPRIME: p.DRC_SEC_ASSET_CLASSES[2],
    SecAssetClass.ABS_CREDIT_CARDS: p.DRC_SEC_ASSET_CLASSES[3],
    SecAssetClass.CMBS: p.DRC_SEC_ASSET_CLASSES[4],
    SecAssetClass.CLO_NON_CTP: p.DRC_SEC_ASSET_CLASSES[5],
    SecAssetClass.ABS_STUDENT_LOANS: p.DRC_SEC_ASSET_CLASSES[8],
}


def sec_bucket(pos: DRCPositionInput) -> str:
    """Securitisation DRC bucket (Art 325aa(4)-(5), p. 340-341): the common corporate bucket, or
    asset class x region; unassignable asset classes go to 'other retail' / 'other wholesale'
    and unassignable regions to 'rest of the world'."""
    if pos.flags.get("sec_corporate_bucket"):
        return p.DRC_SEC_CORPORATE_BUCKET
    if pos.flags.get("abcp"):
        asset = p.DRC_SEC_ASSET_CLASSES[0]
    elif pos.flags.get("cdo_squared"):
        asset = p.DRC_SEC_ASSET_CLASSES[6]
    elif pos.flags.get("sme"):
        asset = p.DRC_SEC_ASSET_CLASSES[7]
    elif pos.sec_asset_class in _ASSET:
        asset = _ASSET[pos.sec_asset_class]
    elif pos.flags.get("other_retail"):
        asset = p.DRC_SEC_ASSET_CLASSES[9]
    else:
        asset = p.DRC_SEC_ASSET_CLASSES[10]
    region = _REGION.get(pos.region.strip().upper(), p.DRC_SEC_REGIONS[3])
    return f"{asset} | {region}"


def sec_risk_weight(pos: DRCPositionInput) -> float:
    """8% of the non-trading-book securitisation RW (Art 325aa(1), p. 340)."""
    rw = pos.banking_book_risk_weight
    if rw is None:
        rw = p.DRC_SEC_DEFAULT_BANKING_BOOK_RW  # TODO: VERIFY -- see params
    return p.DRC_SEC_RW_SCALAR * rw


def _sec_maturity(pos: DRCPositionInput) -> float:
    """Tranche maturity; one year where the RW comes from CRR Art 259 or 263 (Art 325aa(2))."""
    return p.DRC_MATURITY_CAP_YEARS if pos.flags.get("rw_art_259_263") else pos.maturity_years


def _sec_net(positions: list[DRCPositionInput]) -> list[NetJTD]:
    """Net securitisation JTDs: gross JTD = market value (Art 325z(1), 325ac(2)); offsetting only
    within the same pool and tranche (Art 325z(2)) / index family, series and tranche
    (Art 325ac(4)); maturity scaling per Art 325x (Art 325z(5), 325ac(4)(a))."""
    groups: dict[tuple[str, str], list[DRCPositionInput]] = defaultdict(list)
    for pos in positions:
        groups[(pos.pool_id or pos.obligor, pos.tranche_id)].append(pos)
    out: list[NetJTD] = []
    for (pool, _tranche), group in groups.items():
        amt = 0.0
        fair_value = 0.0
        for pos in group:
            sign = 1.0 if pos.is_long else -1.0
            amt += sign * abs(pos.market_value) * maturity_factor(_sec_maturity(pos))
            fair_value += sign * abs(pos.market_value)
        if amt == 0.0:
            continue
        rep = group[0]
        cap = abs(fair_value) if all(g.flags.get("cash_securitisation") for g in group) else None
        if rep.kind is DRCKind.CTP:
            if rep.banking_book_risk_weight is not None:
                rw = sec_risk_weight(rep)  # tranched (Art 325ad(1)(b))
            else:
                rw = default_risk_weight(rep)  # non-tranched (Art 325ad(1)(a))
            bucket = pool  # buckets correspond to an index (Art 325ad(2))
        else:
            rw = sec_risk_weight(rep)
            bucket = sec_bucket(rep)
        out.append(NetJTD(pool, amt, rw, bucket, cap))
    return out


def drc_sec_nonctp_by_bucket(positions: list[DRCPositionInput]) -> dict[str, float]:
    """Bucket-level DRC for non-ACTP securitisations (Art 325aa(6), p. 341)."""
    by_bucket: dict[str, list[NetJTD]] = defaultdict(list)
    for n in _sec_net(positions):
        by_bucket[n.bucket].append(n)
    out: dict[str, float] = {}
    for b, items in by_bucket.items():
        longs = sum(n.amount for n in items if n.amount > 0.0)
        shorts = sum(-n.amount for n in items if n.amount < 0.0)
        out[b] = bucket_drc(items, hedge_benefit_ratio(longs, shorts))
    return out


def drc_sec_nonctp(positions: list[DRCPositionInput]) -> float:
    """Simple sum over buckets (Art 325aa(7), p. 341)."""
    return sum(drc_sec_nonctp_by_bucket(positions).values())


# =========================================================================
#  ACTP
# =========================================================================


def drc_ctp_by_bucket(
    positions: list[DRCPositionInput], floor_bucket: bool = p.DRC_CTP_BUCKET_FLOOR_AT_ZERO
) -> dict[str, float]:
    """Bucket-level ACTP DRC with WtS_ACTP over the entire ACTP (Art 325ad(2)-(3), p. 343)."""
    nets = _sec_net(positions)
    longs = sum(n.amount for n in nets if n.amount > 0.0)
    shorts = sum(-n.amount for n in nets if n.amount < 0.0)
    wts = hedge_benefit_ratio(longs, shorts)
    by_bucket: dict[str, list[NetJTD]] = defaultdict(list)
    for n in nets:
        by_bucket[n.bucket].append(n)
    return {b: bucket_drc(items, wts, floor_bucket) for b, items in by_bucket.items()}


def drc_ctp(
    positions: list[DRCPositionInput], floor_bucket: bool = p.DRC_CTP_BUCKET_FLOOR_AT_ZERO
) -> float:
    """DRC_ACTP = max{sum_b [max(DRC_b, 0) + 0.5 min(DRC_b, 0)]; 0} (Art 325ad(4), p. 343)."""
    total = 0.0
    for v in drc_ctp_by_bucket(positions, floor_bucket).values():
        total += max(v, 0.0) + p.DRC_CTP_NEGATIVE_BUCKET_WEIGHT * min(v, 0.0)
    return max(total, 0.0)


def drc_capital(
    positions: list[DRCPositionInput], ctp_floor_bucket: bool = p.DRC_CTP_BUCKET_FLOOR_AT_ZERO
) -> dict[str, float]:
    """DRC by component and total = sum of the three (no diversification, Art 325v(2) and
    325ab(1), p. 335 and 341)."""
    nonsec = drc_nonsec([q for q in positions if q.kind is DRCKind.NON_SECURITISATION])
    sec = drc_sec_nonctp([q for q in positions if q.kind is DRCKind.SEC_NON_CTP])
    ctp = drc_ctp([q for q in positions if q.kind is DRCKind.CTP], ctp_floor_bucket)
    return {"nonsec": nonsec, "sec_nonctp": sec, "ctp": ctp, "total": nonsec + sec + ctp}
