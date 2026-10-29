"""Default risk capital under MAS Notice 637 Part VIII Division 2 Sub-division 9
(paras 8.2.158-8.2.209).

Non-securitisations (paras 8.2.168-8.2.187):
    JTD(long) = max(LGD x notional + P&L, 0), JTD(short) = min(LGD x notional + P&L, 0)
    (para 8.2.170), notional signed +long / -short and P&L loss negative (para 8.2.172);
    LGD 100% equity / subordinated, 75% senior, 25% covered bonds (para 8.2.171); maturity
    weight min(max(M, 3 months), 1 year) on gross JTD (paras 8.2.176-8.2.179); offsetting per
    reference entity where the short has the same or lower seniority (para 8.2.180); buckets
    companies / central governments, central banks and MDBs / PSEs (para 8.2.183);
    DRC_b = max(sum RW x net long - HBR x sum RW x |net short|; 0), HBR over the bucket
    (para 8.2.184); Table 8-14 weights with a mandatory 0% for sovereign, PSE and MDB names at
    0% under SA(CR) (para 8.2.184(b)(ii)); simple sum across buckets (para 8.2.187).

Securitisations non-CTP (paras 8.2.188-8.2.197): JTD = market value; offsetting only within the
same tranche of the same pool (paras 8.2.191-8.2.192); Table 8-15 buckets; RW = banking-book RW
/ 12.5 (one-year maturity) with the DRC of a non-derivative exposure capped at its fair value
(para 8.2.196(b)); same floored bucket formula; simple sum (para 8.2.197).

CTP (paras 8.2.198-8.2.209): JTD = market value; one bucket per index (paras 8.2.205-8.2.206);
securitisation RW per para 8.2.196(b), hedging non-securitisations per para 8.2.184(b) (para
8.2.207); HBR_CTP across all buckets, DRC_b not floored (para 8.2.208); DRC_CTP =
max(sum_b [max(DRC_b, 0) + 0.5 min(DRC_b, 0)]; 0) (para 8.2.209).

The pure offsetting / HBR / bucket algebra is identical to MAR22 and is imported from the BCBS
engine (:mod:`src.jurisdictions.bcbs.frtb.drc`); all parameters come from the SG params.

Documented ``flags`` keys on :class:`DRCPositionInput`:
    - ``drc_aaa``: obligor rated AAA (Table 8-14 0.5%; the AAA..AA- band otherwise -> AA 2%)
    - ``sa_cr_zero_rw``: True/False overrides whether the name attracts 0% under SA(CR)
      (para 8.2.184(b)(ii)); absent -> 0% for a SOVEREIGN rated AAA..AA- (Table 7-1 CQG "1")
    - ``singapore_government_sgd``: exposure to the Singapore Government / MAS in SGD funded in
      SGD (para 7.3.43 -> 0%)
    - ``zero_rw_international_org``: BIS, IMF, ECB, EU, ESM, EFSF (para 7.3.46 -> 0%)
    - ``qualifying_mdb``: qualifying MDB (para 7.3.51 -> 0%)
    - ``pse_zero_rw``: PSE risk-weighted 0% under Table 7-3 (para 7.3.48)
    - ``fund_unrated_equity``: fund treated as unrated equity (para 8.2.165) -> 15%, LGD 100%
    - ``fund_hy_mandate``: such a fund with a high-yield / distressed mandate (para 8.2.166)
    - ``lgd_not_linked_to_recovery``: no LGD multiplication (para 8.2.174(a))
    - ``unwind_without_default_exposure``: JTD = 0 (para 8.2.174(b))
    - ``cash_equity``: non-derivative equity; maturity must be 0.25 or >= 1 year (8.2.179(b))
    - ``sec_derivative``: securitisation exposure is a derivative (no fair-value cap)
    - ``sec_asset_abcp`` / ``sec_asset_cdo_squared`` / ``sec_asset_small_business`` /
      ``sec_asset_other_retail`` / ``sec_asset_other_wholesale`` / ``sec_asset_companies``:
      Table 8-15 asset classes not in :class:`SecAssetClass`
    - ``ctp_tranched``: CTP position is a securitisation exposure (else inferred from
      ``banking_book_risk_weight``)
"""

from __future__ import annotations

from collections import defaultdict

from src.jurisdictions.bcbs.frtb.drc import (
    _Net,
    bucket_drc,
    hedge_benefit_ratio,
    offset_identical,
    offset_obligor,
)
from src.jurisdictions.frtb_base import CreditSector, DRCKind, DRCPositionInput, DRCSeniority
from src.jurisdictions.sg.frtb import params as p

_ZERO_RW_FLAGS: tuple[str, ...] = (
    "singapore_government_sgd",   # para 7.3.43
    "zero_rw_international_org",  # para 7.3.46
    "qualifying_mdb",             # para 7.3.51
    "pse_zero_rw",                # para 7.3.48 / Table 7-3
)

# =========================================================================
#  Common helpers
# =========================================================================


def maturity_weight(maturity_years: float) -> float:
    """min(max(M, 3 months), 1 year) / 1 year (paras 8.2.176-8.2.179)."""
    m = min(max(maturity_years, p.DRC_MATURITY_FLOOR_YEARS), p.DRC_CAPITAL_HORIZON_YEARS)
    return m / p.DRC_CAPITAL_HORIZON_YEARS


def _check_cash_equity(pos: DRCPositionInput) -> None:
    """Para 8.2.179(b): non-derivative equities are 3 months or more than one year."""
    lo, hi = p.DRC_CASH_EQUITY_MATURITIES
    if pos.flags.get("cash_equity", False) and lo < pos.maturity_years < hi:
        raise ValueError(f"{pos.position_id}: cash equity maturity must be 0.25 or >= 1 year "
                         "(MAS 637 para 8.2.179(b))")


def lgd(pos: DRCPositionInput) -> float:
    """Para 8.2.171 (and fn 683: unrated-equity funds 100%); para 8.2.174(a)."""
    if pos.flags.get("lgd_not_linked_to_recovery", False):
        return p.DRC_LGD_NOT_LINKED_TO_RECOVERY
    if pos.flags.get("fund_unrated_equity", False):
        return p.DRC_LGD[DRCSeniority.EQUITY]
    return p.DRC_LGD[pos.seniority]


def gross_jtd(pos: DRCPositionInput) -> float:
    """Unweighted gross JTD for a non-securitisation (paras 8.2.170-8.2.174)."""
    if pos.flags.get("unwind_without_default_exposure", False):
        return 0.0
    signed = pos.notional if pos.is_long else -pos.notional
    value = lgd(pos) * signed + pos.pnl
    return max(value, 0.0) if pos.is_long else min(value, 0.0)


def sec_gross_jtd(pos: DRCPositionInput) -> float:
    """Securitisation (non-CTP / CTP) gross JTD = market value (paras 8.2.189, 8.2.199)."""
    if pos.flags.get("unwind_without_default_exposure", False):
        return 0.0
    mv = abs(pos.market_value)
    return mv if pos.is_long else -mv


def attracts_zero_sa_cr_rw(pos: DRCPositionInput) -> bool:
    """Para 8.2.184(b)(ii): does the reference entity attract 0% under SA(CR)?

    Explicit ``sa_cr_zero_rw`` wins; otherwise the para 7.3.43 / 7.3.46 / 7.3.48 / 7.3.51
    flags; otherwise a central government / central bank with CQG "1" (Table 7-1).
    """
    if "sa_cr_zero_rw" in pos.flags:
        return pos.flags["sa_cr_zero_rw"]
    if any(pos.flags.get(f, False) for f in _ZERO_RW_FLAGS):
        return True
    return (pos.credit_sector is CreditSector.SOVEREIGN
            and pos.rating in p.SA_CR_ZERO_RW_SOVEREIGN_RATINGS)


def default_rw(pos: DRCPositionInput) -> float:
    """Para 8.2.184(b) and 8.2.185: Table 8-14 weight, 0% names, fund treatments."""
    if pos.is_defaulted:
        return p.DRC_RW_TABLE814["DEFAULTED"]  # 8.2.185(a)
    if attracts_zero_sa_cr_rw(pos):
        return p.DRC_ZERO_RW  # 8.2.184(b)(ii)
    if pos.flags.get("fund_unrated_equity", False):
        if pos.flags.get("fund_hy_mandate", False):
            return p.DRC_FUND_HY_MANDATE_RW  # 8.2.184(b)(iv), TODO: VERIFY placeholder
        return p.DRC_FUND_UNRATED_EQUITY_RW  # 8.2.184(b)(iii)
    cat = p.DRC_RATING_TO_CATEGORY[pos.rating]
    if cat == "AA" and pos.flags.get(p.DRC_AAA_FLAG, False):
        cat = "AAA"
    return p.DRC_RW_TABLE814[cat]


def nonsec_bucket(pos: DRCPositionInput) -> str:
    """Para 8.2.183: central governments, central banks and MDBs; PSEs; else companies."""
    if pos.credit_sector is CreditSector.SOVEREIGN or pos.flags.get("qualifying_mdb", False):
        return p.DRC_BUCKET_SOVEREIGNS
    if pos.credit_sector is CreditSector.LOCAL_GOVERNMENT:
        return p.DRC_BUCKET_PSES
    return p.DRC_BUCKET_COMPANIES


# =========================================================================
#  Non-securitisations
# =========================================================================


def nonsec_by_bucket(positions: list[DRCPositionInput]) -> dict[str, float]:
    """Bucket-level DRC for non-securitisations (para 8.2.184)."""
    grouped: dict[str, dict[str, list[tuple[float, int, float]]]] = defaultdict(
        lambda: defaultdict(list))
    for pos in positions:
        _check_cash_equity(pos)
        jtd = gross_jtd(pos) * maturity_weight(pos.maturity_years)
        if jtd == 0.0:
            continue
        grouped[nonsec_bucket(pos)][pos.obligor].append(
            (jtd, p.DRC_SENIORITY_RANK[pos.seniority], default_rw(pos)))
    out: dict[str, float] = {}
    for bucket, obligors in grouped.items():
        nets: list[_Net] = []
        for entries in obligors.values():
            nets.extend(offset_obligor(entries))
        out[bucket] = bucket_drc(nets, hedge_benefit_ratio(nets))
    return out


def nonsec_drc(positions: list[DRCPositionInput]) -> float:
    """Para 8.2.187: sum of bucket-level DRC (no diversification across buckets)."""
    return sum(nonsec_by_bucket(positions).values())


# =========================================================================
#  Securitisations non-CTP
# =========================================================================

_SEC_FLAG_ASSETS: tuple[tuple[str, str], ...] = (
    ("sec_asset_abcp", "ABCP"),
    ("sec_asset_cdo_squared", "CDO_SQUARED"),
    ("sec_asset_small_business", "SMALL_BUSINESSES"),
    ("sec_asset_other_retail", "OTHER_RETAIL"),
    ("sec_asset_other_wholesale", "OTHER_WHOLESALE"),
)


def sec_nonctp_bucket(pos: DRCPositionInput) -> str:
    """Table 8-15 (paras 8.2.194-8.2.195): companies (all regions), asset class x region, or
    "Others" (bucket 46)."""
    if pos.flags.get("sec_asset_companies", False):
        return p.DRC_SEC_COMPANIES_BUCKET
    asset: str | None = None
    for flag, name in _SEC_FLAG_ASSETS:
        if pos.flags.get(flag, False):
            asset = name
            break
    if asset is None and pos.sec_asset_class is not None:
        asset = p.DRC_SEC_ASSET_FROM_ENUM.get(pos.sec_asset_class)
    region = pos.region.upper().replace(" ", "_") if pos.region else ""
    if asset is None or not region:
        return p.DRC_SEC_OTHERS_BUCKET
    if region not in p.DRC_SEC_NONCTP_REGIONS:
        region = "OTHER"  # "All other" region
    return f"{asset}|{region}"


def sec_rw(pos: DRCPositionInput) -> float:
    """Para 8.2.196(b)(i): banking-book RW (one-year tranche maturity) divided by 12.5."""
    if pos.banking_book_risk_weight is None:
        raise ValueError(f"{pos.position_id}: banking_book_risk_weight is required for a "
                         "securitisation exposure (MAS 637 para 8.2.196(b)(i))")
    return pos.banking_book_risk_weight / p.DRC_SEC_BANKING_BOOK_DIVISOR


def sec_capped_rw(pos: DRCPositionInput, jtd: float) -> float:
    """Para 8.2.196(b)(ii): RW x |JTD| of a non-derivative exposure capped at its fair value."""
    rw = sec_rw(pos)
    if not p.DRC_SEC_FAIR_VALUE_CAP or pos.flags.get("sec_derivative", False) or jtd == 0.0:
        return rw
    return min(rw, abs(pos.market_value) / abs(jtd))


def sec_nonctp_by_bucket(positions: list[DRCPositionInput]) -> dict[str, float]:
    """Bucket-level DRC for securitisations non-CTP (para 8.2.196)."""
    grouped: dict[str, dict[tuple[str, str], list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list))
    for pos in positions:
        jtd = sec_gross_jtd(pos) * maturity_weight(pos.maturity_years)
        if jtd == 0.0:
            continue
        key = (pos.pool_id, pos.tranche_id or pos.position_id)  # 8.2.191-8.2.192(a)
        grouped[sec_nonctp_bucket(pos)][key].append((jtd, sec_capped_rw(pos, jtd)))
    out: dict[str, float] = {}
    for bucket, tranches in grouped.items():
        nets: list[_Net] = []
        for entries in tranches.values():
            nets.extend(offset_identical(entries))
        out[bucket] = bucket_drc(nets, hedge_benefit_ratio(nets))
    return out


def sec_nonctp_drc(positions: list[DRCPositionInput]) -> float:
    """Para 8.2.197: sum of bucket-level DRC."""
    return sum(sec_nonctp_by_bucket(positions).values())


# =========================================================================
#  CTP
# =========================================================================


def ctp_is_tranched(pos: DRCPositionInput) -> bool:
    """Securitisation exposure in the CTP (``ctp_tranched``, else a banking-book RW given)."""
    if "ctp_tranched" in pos.flags:
        return pos.flags["ctp_tranched"]
    return pos.banking_book_risk_weight is not None


def ctp_rw(pos: DRCPositionInput, jtd: float) -> float:
    """Para 8.2.207: securitisation -> para 8.2.196(b); hedging non-sec -> para 8.2.184(b)."""
    return sec_capped_rw(pos, jtd) if ctp_is_tranched(pos) else default_rw(pos)


def ctp_bucket_drc(positions: list[DRCPositionInput]) -> dict[str, float]:
    """Unfloored DRC_b per index with HBR_CTP over all buckets (para 8.2.208)."""
    by_index: dict[str, dict[tuple[str, str], list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list))
    for pos in positions:
        jtd = sec_gross_jtd(pos) * maturity_weight(pos.maturity_years)
        if jtd == 0.0:
            continue
        index = pos.pool_id or pos.obligor  # 8.2.205-8.2.206
        key = (pos.tranche_id, pos.obligor) if ctp_is_tranched(pos) else ("", pos.obligor)
        by_index[index][key].append((jtd, ctp_rw(pos, jtd)))
    nets_by_index: dict[str, list[_Net]] = {}
    for index, groups in by_index.items():
        nets: list[_Net] = []
        for entries in groups.values():
            nets.extend(offset_identical(entries))  # 8.2.202(a)
        nets_by_index[index] = nets
    hbr_ctp = hedge_benefit_ratio([n for ns in nets_by_index.values() for n in ns])
    return {ix: bucket_drc(nets, hbr_ctp, floor=False) for ix, nets in nets_by_index.items()}


def ctp_aggregate(bucket_values: list[float]) -> float:
    """Para 8.2.209: max(sum_b [max(DRC_b, 0) + 0.5 min(DRC_b, 0)]; 0)."""
    total = sum(max(d, 0.0) + p.DRC_CTP_NEGATIVE_BUCKET_WEIGHT * min(d, 0.0)
                for d in bucket_values)
    return max(total, 0.0)


def ctp_drc(positions: list[DRCPositionInput]) -> float:
    """DRC for securitisations (CTP) (paras 8.2.198-8.2.209)."""
    return ctp_aggregate(list(ctp_bucket_drc(positions).values()))


def drc_capital(positions: list[DRCPositionInput]) -> dict[str, float]:
    """DRC by component, summed without diversification (para 8.2.162, fn 679)."""
    nonsec = nonsec_drc([x for x in positions if x.kind is DRCKind.NON_SECURITISATION])
    sec = sec_nonctp_drc([x for x in positions if x.kind is DRCKind.SEC_NON_CTP])
    ctp = ctp_drc([x for x in positions if x.kind is DRCKind.CTP])
    return {"nonsec": nonsec, "sec_nonctp": sec, "ctp": ctp, "total": nonsec + sec + ctp}


__all__ = [
    "attracts_zero_sa_cr_rw",
    "ctp_aggregate",
    "ctp_bucket_drc",
    "ctp_drc",
    "default_rw",
    "drc_capital",
    "gross_jtd",
    "lgd",
    "maturity_weight",
    "nonsec_bucket",
    "nonsec_by_bucket",
    "nonsec_drc",
    "sec_capped_rw",
    "sec_gross_jtd",
    "sec_nonctp_bucket",
    "sec_nonctp_by_bucket",
    "sec_nonctp_drc",
    "sec_rw",
]
