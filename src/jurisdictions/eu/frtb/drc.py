"""EU own funds requirement for default risk (ASA) -- CRR Articles 325v-325ad as amended by CRR3.

Three components summed without diversification (Article 325v(2), 325ab(1)):

* non-securitisations (Arts 325w-325y): JTD_long = max(LGD x V_notional + P&L_long; 0),
  JTD_short = min(LGD x V_notional + P&L_short; 0) with V_notional negative for shorts
  (Art 325w(1)-(2), (5)); LGD 100 % non-senior / 75 % senior / 25 % covered bonds / 100 % equity
  (325w(3), (6)); offsetting within an obligor only where the short is of the same or lower
  seniority (325x(1)); maturity ratio to one year (325x(2)-(3)); default risk weights of Table 2
  (325y(1)), 0 % for 0 %-SA-RW exposures (325y(2)); three buckets (325y(3));
  DRC_b = max{Sum_long RW x netJTD - WtS x Sum_short RW x |netJTD|; 0} with
  WtS = Sum netJTD_long / (Sum netJTD_long + Sum |netJTD_short|) (325y(4)).
* securitisations not in the ACTP (Arts 325z-325aa): JTD = market value; offsetting only within
  the same pool and tranche; RW = 8 % x non-trading-book RW; cash exposures capped at fair value;
  1 corporate bucket + 11 asset classes x 4 regions (325aa(4)).
* ACTP (Arts 325ab-325ad): JTD = market value; offsetting only between otherwise-identical
  exposures; RW per Article 325ad(1) as replaced by CRR3 point (169)(a) (non-tranched: Table 2;
  tranched: 325aa(1)); per-index buckets; DRC_b without zero floor (CRR3 point (169)(b));
  DRC_ACTP = max{Sum_b (max(DRC_b, 0) + 0,5 min(DRC_b, 0)); 0} (325ad(4)).

Documented position ``flags`` (default False):

* ``zero_sa_risk_weight`` -- exposure would receive 0 % under the SA for credit risk (325y(2)).
* ``cash_equity`` -- cash equity: maturity set by the calculator's Article 325x(4) election.
* ``hedged_derivative_closeout`` -- derivative hedged with its cash underlying that can be closed
  out at the first-to-mature expiry with no default exposure: net JTD of the combined position is
  zero (Article 325x(5), CRR3 point (166)). Set on both legs.
* ``cash_securitisation`` -- cap risk-weighted JTD at the fair value (Article 325aa(3)).
* ``sec_corporate`` -- securitisation assigned to the common corporate bucket (325aa(4)(a)).
* ``sec_abcp`` / ``sec_cdo_squared`` / ``sec_sme`` / ``sec_other_retail`` -- asset classes of
  Article 325aa(4) not carried by :class:`~src.jurisdictions.frtb_base.SecAssetClass`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from src.jurisdictions.eu.frtb import params as p
from src.jurisdictions.frtb_base import (
    CreditSector,
    DRCKind,
    DRCPositionInput,
    DRCSeniority,
    SecAssetClass,
)


@dataclass
class DRCComponentResult:
    """One DRC component with its bucket detail."""

    total: float = 0.0
    buckets: dict[str, float] = field(default_factory=dict)
    hbr: dict[str, float] = field(default_factory=dict)
    net_jtd: dict[str, float] = field(default_factory=dict)
    """Signed net JTD per position id (after maturity scaling and offsetting)."""
    notes: list[str] = field(default_factory=list)


def _flag(pos: DRCPositionInput, key: str) -> bool:
    return bool(pos.flags.get(key, False))


# =========================================================================
#  Gross JTD and maturity -- Articles 325w, 325x, 325z, 325ac
# =========================================================================


def lgd(seniority: DRCSeniority) -> float:
    """LGD -- Article 325w(3) (debt) and 325w(6) (equity)."""
    return p.DRC_LGD[seniority.value]


def gross_jtd(pos: DRCPositionInput) -> float:
    """Signed gross JTD (long > 0, short < 0).

    Non-securitisation: Article 325w(1), (2), (5); the 'Adjustment' term of 325w(1)-(2) cannot be
    passed through the contract and is taken as zero. Securitisation / ACTP: market value
    (Articles 325z(1), 325ac(2)).
    """
    if _flag(pos, "hedged_derivative_closeout"):
        return 0.0
    if pos.kind != DRCKind.NON_SECURITISATION:
        mv = abs(pos.market_value)
        return mv if pos.is_long else -mv
    loss_rate = lgd(pos.seniority)
    if pos.is_long:
        return max(loss_rate * pos.notional + pos.pnl, 0.0)
    return min(loss_rate * (-pos.notional) + pos.pnl, 0.0)


def maturity_years(pos: DRCPositionInput, cash_equity_maturity: float) -> float:
    """Maturity used in the Article 325x ratio (derivative maturity, 325x(4))."""
    if _flag(pos, "cash_equity"):
        return cash_equity_maturity
    return pos.maturity_years


def maturity_scale(m: float, offsetting: bool) -> float:
    """Ratio of maturity to one year (Article 325x(2)(b) and (3)).

    The three-month floor is stated only in 325x(3) (no offsetting possible); 325x(2)(b) (partial
    offsetting) applies the plain ratio. Exposures of one year or more are not scaled.
    """
    ratio = min(m / p.DRC_MATURITY_ONE_YEAR, 1.0)
    if offsetting:
        return ratio
    return max(ratio, p.DRC_MATURITY_FLOOR)


# =========================================================================
#  Default risk weights -- Article 325y Table 2
# =========================================================================


def default_risk_weight(pos: DRCPositionInput) -> float:
    """Default RW by credit quality step (Article 325y(1)-(2), (6))."""
    if pos.is_defaulted:
        return p.DRC_RW_DEFAULTED
    if _flag(pos, "zero_sa_risk_weight"):
        return p.DRC_RW_ZERO_SA
    cqs = p.CQS_OF_RATING.get(pos.rating)
    if cqs is None:
        return p.DRC_RW_UNRATED
    return p.DRC_RW_BY_CQS[cqs]


def nonsec_bucket(pos: DRCPositionInput) -> str:
    """Bucket of Article 325y(3): corporates, sovereigns, local governments / municipalities."""
    if pos.credit_sector == CreditSector.SOVEREIGN:
        return "SOVEREIGNS"
    if pos.credit_sector == CreditSector.LOCAL_GOVERNMENT:
        return "LOCAL_GOVERNMENTS_MUNICIPALITIES"
    return "CORPORATES"


# =========================================================================
#  Offsetting
# =========================================================================


@dataclass
class _Leg:
    pos: DRCPositionInput
    jtd: float  # signed, maturity-scaled
    rank: int
    rw: float


def _offset_group(legs: list[_Leg], seniority_rule: bool) -> list[_Leg]:
    """Offset longs against shorts within one obligor / tranche group.

    With ``seniority_rule`` (Article 325x(1)) a short may only offset longs of the same or higher
    seniority; shorts are applied from the most senior down, each consuming the most senior
    eligible longs first.
    """
    longs = sorted([lg for lg in legs if lg.jtd > 0], key=lambda lg: -lg.rank)
    shorts = sorted([lg for lg in legs if lg.jtd < 0], key=lambda lg: -lg.rank)
    for sh in shorts:
        for lo in longs:
            if sh.jtd >= 0:
                break
            if lo.jtd <= 0 or (seniority_rule and lo.rank < sh.rank):
                continue
            used = min(lo.jtd, -sh.jtd)
            lo.jtd -= used
            sh.jtd += used
    return legs


def _scaled_legs(
    group: list[DRCPositionInput],
    rw_of: dict[str, float],
    cash_equity_maturity: float,
    seniority_rule: bool,
) -> list[_Leg]:
    """Gross JTDs scaled for maturity (Article 325x(2)-(3)), then offset."""
    gross = [(pos, gross_jtd(pos)) for pos in group]
    rank = {pos.position_id: p.DRC_SENIORITY_RANK[pos.seniority.value] for pos in group}

    def can_offset(pos: DRCPositionInput, g: float) -> bool:
        for other, og in gross:
            if other is pos or og == 0.0 or g == 0.0 or (og > 0) == (g > 0):
                continue
            if not seniority_rule:
                return True
            long_rank = rank[pos.position_id] if g > 0 else rank[other.position_id]
            short_rank = rank[other.position_id] if g > 0 else rank[pos.position_id]
            if short_rank <= long_rank:
                return True
        return False

    legs: list[_Leg] = []
    for pos, g in gross:
        m = maturity_years(pos, cash_equity_maturity)
        scaled = g * maturity_scale(m, can_offset(pos, g))
        legs.append(_Leg(pos=pos, jtd=scaled, rank=rank[pos.position_id],
                         rw=rw_of[pos.position_id]))
    return _offset_group(legs, seniority_rule)


def _bucket_drc(legs: list[_Leg], floor: bool, wts: float | None = None) -> tuple[float, float]:
    """DRC_b and WtS (Article 325y(4); 325ad(3) for the ACTP)."""
    long_sum = sum(lg.jtd for lg in legs if lg.jtd > 0)
    short_sum = sum(-lg.jtd for lg in legs if lg.jtd < 0)
    if wts is None:
        denom = long_sum + short_sum
        wts = long_sum / denom if denom > 0 else 0.0
    rw_long = sum(lg.rw * lg.jtd for lg in legs if lg.jtd > 0)
    rw_short = sum(lg.rw * -lg.jtd for lg in legs if lg.jtd < 0)
    drc = rw_long - wts * rw_short
    return (max(drc, 0.0) if floor else drc), wts


# =========================================================================
#  Components
# =========================================================================


def drc_nonsec(
    positions: list[DRCPositionInput], cash_equity_maturity: float = 1.0
) -> DRCComponentResult:
    """Non-securitisation DRC -- Articles 325w-325y."""
    res = DRCComponentResult()
    by_obligor: dict[str, list[DRCPositionInput]] = defaultdict(list)
    for pos in positions:
        by_obligor[pos.obligor].append(pos)
    by_bucket: dict[str, list[_Leg]] = defaultdict(list)
    for group in by_obligor.values():
        rw_of = {pos.position_id: default_risk_weight(pos) for pos in group}
        for leg in _scaled_legs(group, rw_of, cash_equity_maturity, seniority_rule=True):
            res.net_jtd[leg.pos.position_id] = leg.jtd
            by_bucket[nonsec_bucket(leg.pos)].append(leg)
    for b, legs in by_bucket.items():
        res.buckets[b], res.hbr[b] = _bucket_drc(legs, floor=True)
    res.total = sum(res.buckets.values())  # Article 325y(5)
    return res


_SEC_CLASS: dict[SecAssetClass, str] = {
    SecAssetClass.RMBS_PRIME: "RMBS",
    SecAssetClass.RMBS_MIDPRIME: "RMBS",
    SecAssetClass.RMBS_SUBPRIME: "RMBS",
    SecAssetClass.CMBS: "CMBS",
    SecAssetClass.ABS_STUDENT_LOANS: "STUDENT_LOANS",
    SecAssetClass.ABS_CREDIT_CARDS: "CREDIT_CARDS",
    SecAssetClass.ABS_AUTO: "AUTO_LOANS_LEASES",
    SecAssetClass.CLO_NON_CTP: "CLO",
}
_REGIONS: dict[str, str] = {
    "ASIA": "ASIA",
    "EUROPE": "EUROPE",
    "EU": "EUROPE",
    "NORTH_AMERICA": "NORTH_AMERICA",
    "NORTH AMERICA": "NORTH_AMERICA",
    "NA": "NORTH_AMERICA",
}


def sec_bucket(pos: DRCPositionInput) -> str:
    """Bucket of Article 325aa(4)-(5): corporates, or asset class x region."""
    if _flag(pos, "sec_corporate"):
        return p.DRC_SEC_CORPORATE_BUCKET
    if _flag(pos, "sec_abcp"):
        asset = "ABCP"
    elif _flag(pos, "sec_cdo_squared"):
        asset = "CDO_SQUARED"
    elif _flag(pos, "sec_sme"):
        asset = "SME"
    elif pos.sec_asset_class in _SEC_CLASS:
        asset = _SEC_CLASS[pos.sec_asset_class]
    else:
        asset = "OTHER_RETAIL" if _flag(pos, "sec_other_retail") else "OTHER_WHOLESALE"
    region = _REGIONS.get(pos.region.strip().upper(), "REST_OF_WORLD")
    return f"{asset}|{region}"


def sec_risk_weight(pos: DRCPositionInput, notes: list[str]) -> float:
    """8 % x non-trading-book securitisation RW (Article 325aa(1))."""
    bb = pos.banking_book_risk_weight
    if bb is None:
        # TODO: VERIFY -- no banking-book RW supplied; conservative 1 250 % (Article 263 cap).
        notes.append(f"{pos.position_id}: banking_book_risk_weight missing; 1 250 % assumed")
        bb = p.SEC_RW_FALLBACK
    return p.DRC_SEC_RW_FACTOR * bb


def drc_sec_nonctp(
    positions: list[DRCPositionInput], cash_equity_maturity: float = 1.0
) -> DRCComponentResult:
    """Securitisation (non-ACTP) DRC -- Articles 325z-325aa."""
    res = DRCComponentResult()
    groups: dict[tuple[str, str], list[DRCPositionInput]] = defaultdict(list)
    for pos in positions:
        groups[(pos.pool_id or pos.obligor, pos.tranche_id)].append(pos)
    by_bucket: dict[str, list[_Leg]] = defaultdict(list)
    for group in groups.values():
        rw_of = {pos.position_id: sec_risk_weight(pos, res.notes) for pos in group}
        for leg in _scaled_legs(group, rw_of, cash_equity_maturity, seniority_rule=False):
            if _flag(leg.pos, "cash_securitisation") and leg.jtd != 0.0:
                cap = abs(leg.pos.market_value)
                weighted = abs(leg.jtd) * leg.rw
                if weighted > cap:
                    leg.rw = cap / abs(leg.jtd)  # Article 325aa(3)
            res.net_jtd[leg.pos.position_id] = leg.jtd
            by_bucket[sec_bucket(leg.pos)].append(leg)
    for b, legs in by_bucket.items():
        res.buckets[b], res.hbr[b] = _bucket_drc(legs, floor=True)  # Article 325aa(6)
    res.total = sum(res.buckets.values())  # Article 325aa(7)
    return res


def ctp_risk_weight(pos: DRCPositionInput, notes: list[str]) -> float:
    """Article 325ad(1) as replaced by CRR3 point (169)(a).

    Non-tranched products: Article 325y(1)-(2) default RWs; tranched products: 8 % of the
    banking-book RW (Article 325aa(1)). A position is treated as tranched when it carries a
    ``banking_book_risk_weight`` or a ``tranche_id``.
    """
    if pos.banking_book_risk_weight is not None or pos.tranche_id:
        return sec_risk_weight(pos, notes)
    return default_risk_weight(pos)


def drc_ctp(
    positions: list[DRCPositionInput], cash_equity_maturity: float = 1.0
) -> DRCComponentResult:
    """ACTP DRC -- Articles 325ac-325ad (CRR3 point (169))."""
    res = DRCComponentResult()
    groups: dict[tuple[str, str], list[DRCPositionInput]] = defaultdict(list)
    for pos in positions:
        # Article 325ac(4): offsetting within the same index family/series and tranche; single
        # names (non-tranched hedges) offset by obligor.
        groups[(pos.pool_id or pos.obligor, pos.tranche_id)].append(pos)
    all_legs: list[_Leg] = []
    by_bucket: dict[str, list[_Leg]] = defaultdict(list)
    for (pool, _tranche), group in groups.items():
        rw_of = {pos.position_id: ctp_risk_weight(pos, res.notes) for pos in group}
        for leg in _scaled_legs(group, rw_of, cash_equity_maturity, seniority_rule=False):
            res.net_jtd[leg.pos.position_id] = leg.jtd
            by_bucket[pool or leg.pos.obligor].append(leg)
            all_legs.append(leg)
    long_sum = sum(lg.jtd for lg in all_legs if lg.jtd > 0)
    short_sum = sum(-lg.jtd for lg in all_legs if lg.jtd < 0)
    wts_actp = long_sum / (long_sum + short_sum) if (long_sum + short_sum) > 0 else 0.0
    for b, legs in by_bucket.items():
        res.buckets[b], res.hbr[b] = _bucket_drc(legs, floor=False, wts=wts_actp)
    agg = sum(
        max(v, 0.0) + p.DRC_CTP_NEGATIVE_BUCKET_FACTOR * min(v, 0.0) for v in res.buckets.values()
    )
    res.total = max(agg, 0.0)
    return res


def drc_all(
    positions: list[DRCPositionInput], cash_equity_maturity: float = 1.0
) -> dict[str, DRCComponentResult]:
    """All three DRC components (Article 325v(2))."""
    nonsec = [x for x in positions if x.kind == DRCKind.NON_SECURITISATION]
    sec = [x for x in positions if x.kind == DRCKind.SEC_NON_CTP]
    ctp = [x for x in positions if x.kind == DRCKind.CTP]
    return {
        "nonsec": drc_nonsec(nonsec, cash_equity_maturity),
        "sec_nonctp": drc_sec_nonctp(sec, cash_equity_maturity),
        "ctp": drc_ctp(ctp, cash_equity_maturity),
    }


__all__ = [
    "DRCComponentResult",
    "ctp_risk_weight",
    "default_risk_weight",
    "drc_all",
    "drc_ctp",
    "drc_nonsec",
    "drc_sec_nonctp",
    "gross_jtd",
    "lgd",
    "maturity_scale",
    "nonsec_bucket",
    "sec_bucket",
]
