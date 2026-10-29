"""Default risk capital requirement (Basel Framework MAR22).

Non-securitisations (MAR22.9-22.26):
    gross JTD(long) = max(LGD x notional + P&L, 0), JTD(short) = min(LGD x notional + P&L, 0)
    (MAR22.11, formulas read from p. 622), notional signed +long / -short (MAR22.13); maturity
    weighting min(max(M, 0.25), 1) applied to gross JTD (MAR22.15, 22.18, footnote 296);
    offsetting within an obligor where the short is of the same or lower seniority
    (MAR22.19); three buckets (MAR22.22); HBR = sum net long / (sum net long + sum |net short|)
    (MAR22.23); DRC_b = max(sum RW x net long - HBR x sum RW x |net short|, 0) (MAR22.25, p. 628);
    simple sum across buckets (MAR22.26).

Securitisations non-CTP (MAR22.27-22.35): JTD = market value (no LGD); offsetting only within
the same tranche of the same pool (MAR22.29-22.30); buckets corporates / asset class x region /
other (MAR22.31-22.32); RW from the banking-book securitisation RW (MAR22.34); same HBR and
floored bucket formula; simple sum (MAR22.35).

CTP (MAR22.36-22.45): JTD = market value; one bucket per index (MAR22.40-22.41);
non-tranched RW from Table 2, tranched from the banking-book treatment (MAR22.43); HBR_ctp over
the whole CTP (MAR22.44(1)); bucket DRC not floored (MAR22.44(2));
DRC_CTP = max(sum_b [max(DRC_b, 0) + 0.5 min(DRC_b, 0)], 0) (MAR22.45, p. 633).

Documented ``flags`` keys on :class:`DRCPositionInput`:
    - ``drc_aaa``: obligor rated AAA (Table 2 0.5%; the engine AAA..AA- band otherwise -> AA 2%)
    - ``lgd_not_linked_to_recovery``: no LGD multiplication (MAR22.12(4))
    - ``unwind_without_default_exposure``: JTD = 0 (MAR22.13, MAR22.18 FAQ1)
    - ``cash_equity``: cash equity; maturity must be 0.25 or >= 1 year (MAR22.16)
    - ``sec_asset_abcp`` / ``sec_asset_cdo_squared`` / ``sec_asset_sme`` /
      ``sec_asset_other_retail`` / ``sec_asset_other_wholesale``: MAR22.31(2)(a) asset classes
      not in :class:`SecAssetClass`
    - ``sec_asset_corporate``: corporates (excl. SME) bucket, all regions (MAR22.31(1))
    - ``ctp_tranched``: CTP position is a tranche (else inferred from ``banking_book_risk_weight``)
Non-sec / CTP offsetting uses ``obligor``; non-CTP offsetting uses (``pool_id``, ``tranche_id``);
the CTP bucket (index) is ``pool_id`` (falling back to ``obligor``).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.jurisdictions.bcbs.frtb import params as p
from src.jurisdictions.frtb_base import CreditSector, DRCKind, DRCPositionInput


@dataclass
class _Net:
    """A residual (net) JTD amount after offsetting, with its risk weight."""

    amount: float
    """Positive = net long, negative = net short."""
    rw: float


# =========================================================================
#  Common helpers
# =========================================================================


def maturity_weight(maturity_years: float) -> float:
    """min(max(M, 3 months), 1 year) / 1 year (MAR22.15, MAR22.18)."""
    return min(max(maturity_years, p.DRC_MATURITY_FLOOR_YEARS), p.DRC_CAPITAL_HORIZON_YEARS) \
        / p.DRC_CAPITAL_HORIZON_YEARS


def _check_cash_equity(pos: DRCPositionInput) -> None:
    """MAR22.16 and FAQ: cash equities are 3 months or more than one year, nothing in between."""
    lo, hi = p.DRC_CASH_EQUITY_MATURITIES
    if pos.flags.get("cash_equity", False) and lo < pos.maturity_years < hi:
        raise ValueError(f"{pos.position_id}: cash equity maturity must be 0.25 or >= 1 year "
                         "(MAR22.16)")


def lgd(pos: DRCPositionInput) -> float:
    """MAR22.12."""
    if pos.flags.get("lgd_not_linked_to_recovery", False):
        return p.DRC_LGD_NOT_LINKED_TO_RECOVERY
    return p.DRC_LGD[pos.seniority]


def gross_jtd(pos: DRCPositionInput) -> float:
    """Unscaled gross JTD for a non-securitisation (MAR22.11-22.14).

    ``notional`` is the bond-equivalent notional (>= 0) signed by ``is_long``
    (MAR22.13); ``pnl`` is the cumulative mark-to-market P&L (loss negative).
    """
    if pos.flags.get("unwind_without_default_exposure", False):
        return 0.0
    signed = pos.notional if pos.is_long else -pos.notional
    value = lgd(pos) * signed + pos.pnl
    return max(value, 0.0) if pos.is_long else min(value, 0.0)


def sec_gross_jtd(pos: DRCPositionInput) -> float:
    """Securitisation (non-CTP and CTP) gross JTD = market value, no LGD (MAR22.27, 22.36-22.37).

    Signed by direction: long positive, short negative (MAR22.10, 22.13).
    """
    if pos.flags.get("unwind_without_default_exposure", False):
        return 0.0
    mv = abs(pos.market_value)
    return mv if pos.is_long else -mv


def default_rw(pos: DRCPositionInput, options: p.BCBSFRTBOptions) -> float:
    """MAR22.24 Table 2 (and MAR22.7 sovereign discretion)."""
    if pos.is_defaulted:
        return p.DRC_RW_TABLE2["DEFAULTED"]
    if options.drc_sovereign_zero_rw and pos.credit_sector is CreditSector.SOVEREIGN:
        return 0.0
    cat = p.DRC_RATING_TO_CATEGORY[pos.rating]
    if cat == "AA" and pos.flags.get(p.DRC_AAA_FLAG, False):
        cat = "AAA"
    return p.DRC_RW_TABLE2[cat]


def nonsec_bucket(pos: DRCPositionInput) -> str:
    """MAR22.22: sovereigns, local governments and municipalities, else corporates."""
    if pos.credit_sector is CreditSector.SOVEREIGN:
        return "SOVEREIGNS"
    if pos.credit_sector is CreditSector.LOCAL_GOVERNMENT:
        return "LOCAL_GOVERNMENTS"
    return "CORPORATES"


def hedge_benefit_ratio(nets: list[_Net]) -> float:
    """HBR = sum net long / (sum net long + sum |net short|) (MAR22.23, p. 627); 0 if empty."""
    longs = sum(n.amount for n in nets if n.amount > 0)
    shorts = sum(-n.amount for n in nets if n.amount < 0)
    denom = longs + shorts
    return longs / denom if denom > 0 else 0.0


def bucket_drc(nets: list[_Net], hbr: float, floor: bool = True) -> float:
    """DRC_b = [max]( sum RW x net long - HBR x sum RW x |net short| [, 0]) (MAR22.25, 22.44)."""
    lw = sum(n.rw * n.amount for n in nets if n.amount > 0)
    sw = sum(n.rw * -n.amount for n in nets if n.amount < 0)
    value = lw - hbr * sw
    return max(value, 0.0) if floor else value


# =========================================================================
#  Offsetting
# =========================================================================


def offset_obligor(entries: list[tuple[float, int, float]]) -> list[_Net]:
    """Offset scaled gross JTDs of one obligor (MAR22.19-22.21).

    ``entries`` are (scaled JTD, seniority rank, RW). A short may offset a long
    only where the short has the same or lower seniority (MAR22.19(1)). Shorts are
    processed from most senior to most junior; each consumes eligible longs from the
    most senior down. Because the eligible sets are nested this maximises the
    permitted offsetting. Residuals keep their own risk weights.
    """
    longs = sorted(([amt, rank, rw] for amt, rank, rw in entries if amt > 0),
                   key=lambda x: -x[1])
    shorts = sorted(([-amt, rank, rw] for amt, rank, rw in entries if amt < 0),
                    key=lambda x: -x[1])
    for sh in shorts:
        for lg in longs:
            if sh[0] <= 0:
                break
            if lg[0] <= 0 or lg[1] < sh[1]:
                continue
            m = min(lg[0], sh[0])
            lg[0] -= m
            sh[0] -= m
    out = [_Net(amount=a, rw=w) for a, _, w in longs if a > 0]
    out += [_Net(amount=-a, rw=w) for a, _, w in shorts if a > 0]
    return out


def offset_identical(entries: list[tuple[float, float]]) -> list[_Net]:
    """Full offsetting of identical exposures (same tranche / index series) (MAR22.30, 22.39).

    ``entries`` are (scaled JTD, RW); the net amount carries the RW of the larger side
    (RWs are equal for identical exposures).
    """
    net = sum(a for a, _ in entries)
    if net == 0:
        return []
    side = [e for e in entries if (e[0] > 0) == (net > 0)]
    rw = max(w for _, w in side) if side else entries[0][1]
    return [_Net(amount=net, rw=rw)]


# =========================================================================
#  Non-securitisation
# =========================================================================


def nonsec_drc(positions: list[DRCPositionInput], options: p.BCBSFRTBOptions) -> float:
    """DRC for non-securitisations (MAR22.9-22.26)."""
    by_bucket_obligor: dict[str, dict[str, list[tuple[float, int, float]]]] = defaultdict(
        lambda: defaultdict(list))
    for pos in positions:
        _check_cash_equity(pos)
        jtd = gross_jtd(pos) * maturity_weight(pos.maturity_years)
        if jtd == 0.0:
            continue
        rank = p.DRC_SENIORITY_RANK[pos.seniority]
        by_bucket_obligor[nonsec_bucket(pos)][pos.obligor].append(
            (jtd, rank, default_rw(pos, options)))
    total = 0.0
    for obligors in by_bucket_obligor.values():
        nets: list[_Net] = []
        for entries in obligors.values():
            nets.extend(offset_obligor(entries))
        total += bucket_drc(nets, hedge_benefit_ratio(nets))
    return total


# =========================================================================
#  Securitisation non-CTP
# =========================================================================


_SEC_FLAG_ASSETS: tuple[tuple[str, str], ...] = (
    ("sec_asset_abcp", "ABCP"),
    ("sec_asset_cdo_squared", "CDO_SQUARED"),
    ("sec_asset_sme", "SME"),
    ("sec_asset_other_retail", "OTHER_RETAIL"),
    ("sec_asset_other_wholesale", "OTHER_WHOLESALE"),
)


def sec_nonctp_bucket(pos: DRCPositionInput) -> str:
    """MAR22.31-22.32: corporates (all regions), asset class x region, or "other bucket"."""
    if pos.flags.get("sec_asset_corporate", False):
        return p.DRC_SEC_CORPORATE_BUCKET
    asset: str | None = None
    for flag, name in _SEC_FLAG_ASSETS:
        if pos.flags.get(flag, False):
            asset = name
            break
    if asset is None and pos.sec_asset_class is not None:
        asset = p.DRC_SEC_ASSET_FROM_ENUM.get(pos.sec_asset_class)
    region = pos.region.upper().replace(" ", "_") if pos.region else ""
    if asset is None or not region:
        return p.DRC_SEC_OTHER_BUCKET
    if region not in p.DRC_SEC_NONCTP_REGIONS:
        region = "OTHER"  # "all other" region (MAR22.31(2)(b))
    return f"{asset}|{region}"


def sec_rw(pos: DRCPositionInput) -> float:
    """Banking-book securitisation RW x 8% (MAR22.34(1), MAR22.42; conversion flagged TODO)."""
    if pos.banking_book_risk_weight is None:
        raise ValueError(f"{pos.position_id}: banking_book_risk_weight is required for a "
                         "securitisation tranche (MAR22.34 / MAR22.42)")
    return pos.banking_book_risk_weight * p.DRC_SEC_BANKING_BOOK_TO_DRC_FACTOR


def sec_nonctp_drc(positions: list[DRCPositionInput]) -> float:
    """DRC for securitisations not in the CTP (MAR22.27-22.35)."""
    by_bucket: dict[str, dict[tuple[str, str], list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list))
    for pos in positions:
        jtd = sec_gross_jtd(pos) * maturity_weight(pos.maturity_years)
        if jtd == 0.0:
            continue
        key = (pos.pool_id, pos.tranche_id or pos.position_id)
        by_bucket[sec_nonctp_bucket(pos)][key].append((jtd, sec_rw(pos)))
    total = 0.0
    for tranches in by_bucket.values():
        nets: list[_Net] = []
        for entries in tranches.values():
            nets.extend(offset_identical(entries))
        total += bucket_drc(nets, hedge_benefit_ratio(nets))
    return total


# =========================================================================
#  CTP
# =========================================================================


def ctp_is_tranched(pos: DRCPositionInput) -> bool:
    """Tranched CTP product (``ctp_tranched`` flag, else a banking-book RW is supplied)."""
    if "ctp_tranched" in pos.flags:
        return pos.flags["ctp_tranched"]
    return pos.banking_book_risk_weight is not None


def ctp_rw(pos: DRCPositionInput, options: p.BCBSFRTBOptions) -> float:
    """MAR22.43: non-tranched -> Table 2; tranched -> banking-book treatment (MAR22.42)."""
    return sec_rw(pos) if ctp_is_tranched(pos) else default_rw(pos, options)


def ctp_drc(positions: list[DRCPositionInput], options: p.BCBSFRTBOptions) -> float:
    """DRC for the correlation trading portfolio (MAR22.36-22.45)."""
    by_index: dict[str, dict[tuple[str, str], list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list))
    for pos in positions:
        jtd = sec_gross_jtd(pos) * maturity_weight(pos.maturity_years)
        if jtd == 0.0:
            continue
        index = pos.pool_id or pos.obligor
        key = (pos.tranche_id, pos.obligor) if ctp_is_tranched(pos) else ("", pos.obligor)
        by_index[index][key].append((jtd, ctp_rw(pos, options)))
    nets_by_index: dict[str, list[_Net]] = {}
    for index, groups in by_index.items():
        nets: list[_Net] = []
        for entries in groups.values():
            nets.extend(offset_identical(entries))
        nets_by_index[index] = nets
    hbr_ctp = hedge_benefit_ratio([n for ns in nets_by_index.values() for n in ns])
    total = 0.0
    for nets in nets_by_index.values():
        d = bucket_drc(nets, hbr_ctp, floor=False)
        total += max(d, 0.0) + p.DRC_CTP_NEGATIVE_BUCKET_WEIGHT * min(d, 0.0)
    return max(total, 0.0)


def drc_capital(positions: list[DRCPositionInput], options: p.BCBSFRTBOptions) -> dict[str, float]:
    """DRC by component, no diversification between them (MAR22.4)."""
    nonsec = nonsec_drc([x for x in positions if x.kind is DRCKind.NON_SECURITISATION], options)
    sec = sec_nonctp_drc([x for x in positions if x.kind is DRCKind.SEC_NON_CTP])
    ctp = ctp_drc([x for x in positions if x.kind is DRCKind.CTP], options)
    return {"nonsec": nonsec, "sec_nonctp": sec, "ctp": ctp, "total": nonsec + sec + ctp}


__all__ = [
    "bucket_drc",
    "ctp_drc",
    "default_rw",
    "drc_capital",
    "gross_jtd",
    "hedge_benefit_ratio",
    "lgd",
    "maturity_weight",
    "nonsec_bucket",
    "nonsec_drc",
    "offset_identical",
    "offset_obligor",
    "sec_gross_jtd",
    "sec_nonctp_bucket",
    "sec_nonctp_drc",
    "sec_rw",
]

