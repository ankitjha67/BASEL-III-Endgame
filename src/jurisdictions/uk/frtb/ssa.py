"""UK simplified standardised approach (SSA) for market risk.

The PRA keeps the legacy CRR standardised rules as the 'simplified standardised approach' for
firms with small market-risk business (Market Risk: General Provisions (CRR) Part Art 325(1)(b),
p. 226; eligibility Art 325a, p. 231), scaled by the Art 325(2) multipliers (p. 226-227):

* debt instruments, Articles 334-340 (Annex J, p. 369-374): specific risk by Table 1 / 8% of
  the securitisation RW, general risk by the maturity ladder (Table 2) or duration (Table 3)
  method -- x 1.3;
* equities, Articles 341-344 (p. 375-376): 8% of the overall gross position (specific) plus 8%
  of the overall net position per market (general) -- x 3.5;
* CIUs, Article 348 (p. 378): 32% (position risk) or 40% (with FX risk) -- x 3.5;
* foreign exchange, Articles 351-354 (p. 380-388): 8% of the overall net FX position plus the
  net gold position where it exceeds 2% of total own funds; 4% on closely correlated matched
  positions -- x 1.2;
* commodities, Articles 355-361 (p. 388-392): maturity ladder, simplified or extended maturity
  ladder approach -- x 1.9;
* non-delta risk of options, Article 352a (p. 382-387): simplified approach or delta-plus gamma
  and vega charges.

Underwriting positions may be reduced by the Art 345 Table 4 factors (p. 376). Each input model
below documents the provisions it carries. Amounts are in the reporting currency (GBP millions).
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from pydantic import BaseModel, Field

from src.jurisdictions.uk.frtb import params as p


class SSARiskType(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Risk category of an option's underlying (for the Art 325(2) multiplier)."""

    DEBT = "DEBT"
    EQUITY = "EQUITY"
    FX = "FX"
    COMMODITY = "COMMODITY"


class GeneralRiskMethod(str, Enum):  # noqa: UP042
    """General interest-rate risk method for debt (Art 339 / Art 340)."""

    MATURITY = "MATURITY"
    DURATION = "DURATION"


class CommodityMethod(str, Enum):  # noqa: UP042
    """Commodity method (Art 355: Articles 359, 360 or 361)."""

    MATURITY_LADDER = "MATURITY_LADDER"
    SIMPLIFIED = "SIMPLIFIED"
    EXTENDED_LADDER = "EXTENDED_LADDER"


class SSADebtPosition(BaseModel):
    """A debt position (Art 326-340). ``amount`` is the signed market value (long > 0) after the
    decomposition of derivatives into long/short legs (Art 328-332); legs that are notional
    borrowings or government-bond legs carry ``sa_risk_weight = 0`` (Table 1 first category)."""

    position_id: str
    issue_id: str = Field(default="", description="Netting key (Art 327(1)); default position_id")
    currency: str = "GBP"
    amount: float
    residual_maturity_years: float = Field(ge=0.0)
    next_reset_years: float | None = Field(
        default=None, description="Floating rate: period until the next fixing (Art 339(2))"
    )
    coupon: float = Field(default=0.0, description="Coupon rate, decimal (Art 339(2))")
    sa_risk_weight: float | None = Field(
        default=None,
        description="Credit Risk SA weight the security would receive (Art 336(1)); None -> 12%",
    )
    qualifying_covered_bond: bool = False
    """Qualifies for a 10% RW under Art 129(4)-(6): half of the second category (Art 336(3))."""
    is_securitisation: bool = False
    banking_book_risk_weight: float | None = None
    """Non-trading-book securitisation RW (decimal) for Art 337(1)."""
    modified_duration: float | None = Field(default=None, ge=0.0)
    """For the duration method (Art 340(3)); computed from cash flows by the caller."""
    max_default_loss: float | None = Field(default=None, ge=0.0)
    """Optional Art 335 cap on the specific-risk requirement of the net position."""
    underwriting_day: int | None = Field(default=None, ge=0)
    """Working day of an underwriting position for the Art 345 Table 4 reduction."""


class SSAEquityPosition(BaseModel):
    """An equity position (Art 341-344). ``amount`` signed (long > 0)."""

    position_id: str
    issuer: str
    market: str = Field(description="National market (Art 341(3))")
    amount: float
    diversified_index_future: bool = False
    """Exchange-traded future on an appropriately diversified index (Art 344(1), (4)): no
    specific risk."""
    underwriting_day: int | None = Field(default=None, ge=0)


class SSACIUPosition(BaseModel):
    """A CIU position under the Art 348(1) fixed percentages."""

    position_id: str
    value: float = Field(ge=0.0)
    include_fx: bool = False
    """True -> 40% (position and FX risk); False -> 32% (position risk)."""


class SSAFXPosition(BaseModel):
    """Net open position in one currency or in gold (Art 352(1)), in the reporting currency,
    signed (long > 0)."""

    currency: str
    net_position: float
    is_gold: bool = False


class SSACommodityPosition(BaseModel):
    """A commodity position (Art 357-358), in standard units (signed, long > 0)."""

    commodity: str
    units: float
    spot_price: float = Field(ge=0.0)
    maturity_years: float = Field(default=0.0, ge=0.0)
    """Physical stocks go to the first band (Art 359(1)); derivatives use expiry (Art 358(1))."""
    category: str = "OTHER"
    """For the extended ladder: PRECIOUS_METALS, BASE_METALS, AGRICULTURAL, OTHER (Art 361)."""


class SSAOptionNonDelta(BaseModel):
    """Non-delta risk of an option (Art 352a).

    Simplified approach (Art 352a(5)): give ``gross_amount`` and ``rw_delta_equivalent``.
    Delta-plus (Art 352a(6)-(8)): give ``gamma`` and ``vu`` (Art 352a(7)(b)) and/or ``vega`` and
    ``implied_vol``; ``underlying_type`` is the distinct underlying type of Art 352a(7)(c).
    """

    position_id: str
    risk_type: SSARiskType
    underlying_type: str = ""
    gross_amount: float | None = None
    rw_delta_equivalent: float | None = None
    gamma: float | None = None
    vu: float | None = None
    vega: float | None = None
    implied_vol: float | None = None


class SSAInputs(BaseModel):
    """All simplified-standardised-approach inputs."""

    debt: list[SSADebtPosition] = Field(default_factory=list)
    general_risk_method: GeneralRiskMethod = GeneralRiskMethod.MATURITY
    reverse_zone_order: bool = False
    """Art 339(6): match zones two and three before one and two."""
    equities: list[SSAEquityPosition] = Field(default_factory=list)
    cius: list[SSACIUPosition] = Field(default_factory=list)
    fx: list[SSAFXPosition] = Field(default_factory=list)
    reporting_currency: str = p.REPORTING_CURRENCY
    total_own_funds: float | None = Field(
        default=None, description="For the Art 351 2% de minimis; None -> always charge"
    )
    closely_correlated_matched: float = Field(default=0.0, ge=0.0)
    """Matched positions in closely correlated currencies (Art 354(1)), already removed from the
    currency nets (Art 354(3)(c))."""
    commodities: list[SSACommodityPosition] = Field(default_factory=list)
    commodity_method: CommodityMethod = CommodityMethod.MATURITY_LADDER
    options: list[SSAOptionNonDelta] = Field(default_factory=list)


class SSAResult(BaseModel):
    """SSA own funds requirements (before and after the Art 325(2) multipliers) and RWA."""

    debt_specific: float = 0.0
    debt_general: float = 0.0
    equity_specific: float = 0.0
    equity_general: float = 0.0
    ciu: float = 0.0
    fx: float = 0.0
    commodity: float = 0.0
    options_non_delta: dict[str, float] = Field(default_factory=dict)
    scaled: dict[str, float] = Field(default_factory=dict)
    total: float = 0.0
    rwa: float = 0.0
    citations: dict[str, str] = Field(default_factory=dict)


# =========================================================================
#  Underwriting (Art 345)
# =========================================================================


def underwriting_factor(day: int | None) -> float:
    """Art 345(1) Table 4 reduction factor (p. 376): day 0 100%, 1 90%, 2-3 75%, 4 50%, 5 25%,
    after working day 5 0%."""
    if day is None:
        return 1.0
    return p.SSA_UNDERWRITING_REDUCTION.get(day, 0.0)


# =========================================================================
#  Debt -- specific risk (Art 335-337)
# =========================================================================


def debt_specific_rate(pos: SSADebtPosition) -> float:
    """Art 336(1) Table 1 (p. 370) with the Art 336(3) half rate for 10% covered bonds; Art
    337(1) 8% of the banking-book RW for securitisations (p. 371)."""
    if pos.is_securitisation:
        rw = pos.banking_book_risk_weight
        if rw is None:
            rw = p.DRC_SEC_DEFAULT_BANKING_BOOK_RW  # TODO: VERIFY -- conservative 1,250%
        return p.SSA_SEC_SPECIFIC_SCALAR * rw
    rw = pos.sa_risk_weight
    m = pos.residual_maturity_years
    if pos.qualifying_covered_bond:
        return p.SSA_COVERED_BOND_FACTOR * _row2(m)
    if rw is None:
        return p.SSA_DEBT_SPECIFIC_ROW4  # unknown weight: highest category (conservative)
    if rw <= 0.0:
        return p.SSA_DEBT_SPECIFIC_ZERO
    if rw <= p.SSA_DEBT_SPECIFIC_LOW_RW_CAP:
        return _row2(m)
    if rw <= p.SSA_DEBT_SPECIFIC_MID_RW_CAP:
        return p.SSA_DEBT_SPECIFIC_ROW3
    return p.SSA_DEBT_SPECIFIC_ROW4


def _row2(m: float) -> float:
    """Table 1 second category by residual term (p. 370)."""
    for upper, rate in p.SSA_DEBT_SPECIFIC_ROW2:
        if m <= upper:
            return rate
    return p.SSA_DEBT_SPECIFIC_ROW2_LONG


def _net_debt(positions: list[SSADebtPosition]) -> list[tuple[SSADebtPosition, float]]:
    """Net positions per issue (Art 327(1), p. 365) after the Art 345 underwriting reduction."""
    acc: dict[tuple[str, str], float] = defaultdict(float)
    rep: dict[tuple[str, str], SSADebtPosition] = {}
    for q in positions:
        key = (q.currency, q.issue_id or q.position_id)
        acc[key] += q.amount * underwriting_factor(q.underwriting_day)
        rep.setdefault(key, q)
    return [(rep[k], v) for k, v in acc.items() if v != 0.0]


def debt_specific_risk(positions: list[SSADebtPosition]) -> float:
    """Sum of weighted net positions regardless of sign (Art 336(1), 337(4)), each capped at the
    maximum possible default-related loss where given (Art 335)."""
    total = 0.0
    for pos, net in _net_debt(positions):
        charge = abs(net) * debt_specific_rate(pos)
        if pos.max_default_loss is not None:
            charge = min(charge, pos.max_default_loss)
        total += charge
    return total


# =========================================================================
#  Debt -- general risk (Art 339-340)
# =========================================================================


def ladder_band(maturity_years: float, coupon: float) -> int:
    """Index of the Art 339(4) Table 2 band (p. 372-373)."""
    high = coupon >= p.SSA_COUPON_THRESHOLD
    for i, (_zone, up_hi, up_lo, _w, _chg) in enumerate(p.SSA_MATURITY_LADDER):
        upper = up_hi if high else up_lo
        if upper is None or maturity_years <= upper:
            return i
    return len(p.SSA_MATURITY_LADDER) - 1  # pragma: no cover


def _match(a: float, b: float) -> tuple[float, float, float]:
    """Match two signed unmatched positions; returns (matched, a', b')."""
    if a * b >= 0.0:
        return 0.0, a, b
    m = min(abs(a), abs(b))
    return m, a - m * (1.0 if a > 0 else -1.0), b - m * (1.0 if b > 0 else -1.0)


def _zones_charge(
    unmatched: dict[int, float], reverse: bool
) -> tuple[float, float, float, float]:
    """Cross-zone matching (Art 339(5)-(8), p. 373): returns (m12, m23, m13, residual)."""
    u1, u2, u3 = unmatched.get(1, 0.0), unmatched.get(2, 0.0), unmatched.get(3, 0.0)
    if reverse:
        m23, u2, u3 = _match(u2, u3)
        m12, u1, u2 = _match(u1, u2)
    else:
        m12, u1, u2 = _match(u1, u2)
        m23, u2, u3 = _match(u2, u3)
    m13, u1, u3 = _match(u1, u3)
    return m12, m23, m13, abs(u1) + abs(u2) + abs(u3)


def maturity_ladder_charge(
    items: list[tuple[float, float, float]], reverse: bool = False
) -> float:
    """Art 339 general-risk requirement for one currency (p. 371-373).

    ``items`` = (signed net position, maturity or time to reset in years, coupon).
    """
    band_long: dict[int, float] = defaultdict(float)
    band_short: dict[int, float] = defaultdict(float)
    for amount, maturity, coupon in items:
        i = ladder_band(maturity, coupon)
        weighted = amount * p.SSA_MATURITY_LADDER[i][3] / 100.0
        if weighted > 0:
            band_long[i] += weighted
        else:
            band_short[i] += -weighted
    matched_bands = 0.0
    zone_long: dict[int, float] = defaultdict(float)
    zone_short: dict[int, float] = defaultdict(float)
    for i in set(band_long) | set(band_short):
        lo, sh = band_long[i], band_short[i]
        matched_bands += min(lo, sh)
        zone = p.SSA_MATURITY_LADDER[i][0]
        if lo > sh:
            zone_long[zone] += lo - sh
        else:
            zone_short[zone] += sh - lo
    charge = p.SSA_LADDER_BAND_MATCHED * matched_bands
    unmatched: dict[int, float] = {}
    for z in (1, 2, 3):
        charge += p.SSA_LADDER_ZONE_MATCHED[z] * min(zone_long[z], zone_short[z])
        unmatched[z] = zone_long[z] - zone_short[z]
    m12, m23, m13, residual = _zones_charge(unmatched, reverse)
    return (
        charge
        + p.SSA_LADDER_ADJACENT_ZONES * (m12 + m23)
        + p.SSA_LADDER_ZONES_1_3 * m13
        + p.SSA_LADDER_RESIDUAL * residual
    )


def duration_zone(modified_duration: float) -> tuple[int, float]:
    """Art 340(4) Table 3 zone and assumed interest change in % (p. 374)."""
    for zone, upper, change in p.SSA_DURATION_ZONES:
        if upper is None or modified_duration <= upper:
            return zone, change
    raise AssertionError("unreachable")  # pragma: no cover


def modified_duration(cash_flows: list[tuple[float, float]], ytm: float) -> float:
    """Modified duration D / (1 + R) with D = sum t C_t (1+R)^-t / sum C_t (1+R)^-t
    (Art 340(3), p. 373-374).

    # TODO: VERIFY -- the PRA text prints (1 - R)^t in the duration formula (p. 374); CRR
    # Art 340(3) and the Basel text use (1 + R)^t, which is implemented here.
    """
    disc = 1.0 + ytm
    pv = sum(c / disc**t for t, c in cash_flows)
    d = sum(t * c / disc**t for t, c in cash_flows) / pv
    return float(d / disc)


def duration_charge(items: list[tuple[float, float]], reverse: bool = False) -> float:
    """Art 340(5)-(7) general-risk requirement for one currency (p. 374).

    ``items`` = (signed market value, modified duration).
    """
    zl: dict[int, float] = defaultdict(float)
    zs: dict[int, float] = defaultdict(float)
    for mv, md in items:
        zone, change = duration_zone(md)
        dw = mv * md * change / 100.0
        if dw > 0:
            zl[zone] += dw
        else:
            zs[zone] += -dw
    charge = 0.0
    unmatched: dict[int, float] = {}
    for z in (1, 2, 3):
        charge += p.SSA_DURATION_ZONE_MATCHED * min(zl[z], zs[z])
        unmatched[z] = zl[z] - zs[z]
    m12, m23, m13, residual = _zones_charge(unmatched, reverse)
    return (
        charge
        + p.SSA_LADDER_ADJACENT_ZONES * (m12 + m23)
        + p.SSA_LADDER_ZONES_1_3 * m13
        + p.SSA_LADDER_RESIDUAL * residual
    )


def debt_general_risk(
    positions: list[SSADebtPosition],
    method: GeneralRiskMethod = GeneralRiskMethod.MATURITY,
    reverse: bool = False,
) -> float:
    """General risk per currency, summed (Art 334, p. 369; Art 339 or 340)."""
    by_ccy: dict[str, list[tuple[SSADebtPosition, float]]] = defaultdict(list)
    for pos, net in _net_debt(positions):
        by_ccy[pos.currency].append((pos, net))
    total = 0.0
    for items in by_ccy.values():
        if method is GeneralRiskMethod.DURATION:
            dur: list[tuple[float, float]] = []
            for pos, net in items:
                if pos.modified_duration is None:
                    raise ValueError("duration method requires modified_duration (Art 340(3))")
                dur.append((net, pos.modified_duration))
            total += duration_charge(dur, reverse)
        else:
            lad = [
                (
                    net,
                    pos.next_reset_years
                    if pos.next_reset_years is not None
                    else pos.residual_maturity_years,
                    pos.coupon,
                )
                for pos, net in items
            ]
            total += maturity_ladder_charge(lad, reverse)
    return total


# =========================================================================
#  Equities (Art 341-344) and CIUs (Art 348)
# =========================================================================


def equity_charges(positions: list[SSAEquityPosition]) -> tuple[float, float]:
    """(specific, general): 8% of the overall gross position excluding diversified index
    futures (Art 341(1), 342, 344(4)) and 8% of the overall net position, netted per market
    (Art 341(2)-(3), 343) (p. 375-376)."""
    net_issue: dict[tuple[str, str, bool], float] = defaultdict(float)
    for q in positions:
        net_issue[(q.market, q.issuer, q.diversified_index_future)] += q.amount * (
            underwriting_factor(q.underwriting_day)
        )
    gross = sum(abs(v) for (_m, _i, div), v in net_issue.items() if not div)
    per_market: dict[str, float] = defaultdict(float)
    for (market, _i, _d), v in net_issue.items():
        per_market[market] += v
    net = sum(abs(v) for v in per_market.values())
    return p.SSA_EQUITY_SPECIFIC * gross, p.SSA_EQUITY_GENERAL * net


def ciu_charge(positions: list[SSACIUPosition]) -> float:
    """Art 348(1): 32% (position risk) or 40% (position and FX risk) (p. 378)."""
    return sum(
        q.value * (p.SSA_CIU_POSITION_AND_FX if q.include_fx else p.SSA_CIU_POSITION)
        for q in positions
    )


# =========================================================================
#  Foreign exchange (Art 351-354)
# =========================================================================


def fx_charge(
    positions: list[SSAFXPosition],
    reporting_currency: str = p.REPORTING_CURRENCY,
    total_own_funds: float | None = None,
    closely_correlated_matched: float = 0.0,
) -> float:
    """Art 351-352, 354 (p. 380-388): overall net FX position = max(total net long, total net
    short) over currencies other than the reporting currency (Art 352(4)); plus the net gold
    position; 8% if their sum exceeds 2% of total own funds (Art 351(1)); plus 4% of matched
    closely-correlated positions (Art 354(1))."""
    nets: dict[str, float] = defaultdict(float)
    gold = 0.0
    for q in positions:
        if q.is_gold:
            gold += q.net_position
        elif q.currency.upper() != reporting_currency.upper():
            nets[q.currency.upper()] += q.net_position
    longs = sum(v for v in nets.values() if v > 0)
    shorts = sum(-v for v in nets.values() if v < 0)
    base = max(longs, shorts) + abs(gold)
    charge = p.SSA_FX_CLOSELY_CORRELATED_RATE * closely_correlated_matched
    if total_own_funds is not None and base <= p.SSA_FX_DE_MINIMIS * total_own_funds:
        return 0.0
    return charge + p.SSA_FX_RATE * base


# =========================================================================
#  Commodities (Art 357-361)
# =========================================================================


def commodity_band(maturity_years: float) -> int:
    """Art 359(1) Table 1 band index (p. 390-391)."""
    for i, upper in enumerate(p.SSA_COMMODITY_LADDER_BANDS):
        if upper is None or maturity_years <= upper:
            return i
    return len(p.SSA_COMMODITY_LADDER_BANDS) - 1  # pragma: no cover


def ladder_commodity(
    items: list[tuple[float, float]], spread: float, carry: float, outright: float
) -> float:
    """Maturity ladder for one commodity (Art 359(3)-(5), p. 391); ``items`` = (signed value =
    units x spot price, maturity years).

    (a) matched long + matched short in each band x spread rate; (b) positions matched between
    bands x carry rate for each band the unmatched position is carried forward; (c) residual x
    outright rate.
    """
    longs: dict[int, float] = defaultdict(float)
    shorts: dict[int, float] = defaultdict(float)
    for value, maturity in items:
        i = commodity_band(maturity)
        if value > 0:
            longs[i] += value
        else:
            shorts[i] += -value
    charge = 0.0
    carried: list[list[float]] = []  # [signed amount, origin band]
    for i in range(len(p.SSA_COMMODITY_LADDER_BANDS)):
        lo, sh = longs[i], shorts[i]
        matched = min(lo, sh)
        charge += 2.0 * matched * spread  # 'the sum of the matched long and short positions'
        u = lo - sh
        while u != 0.0 and carried and carried[0][0] * u < 0.0:
            chunk = carried[0]
            m = min(abs(chunk[0]), abs(u))
            charge += m * carry * (i - chunk[1])
            chunk[0] -= m if chunk[0] > 0 else -m
            u -= m if u > 0 else -m
            if chunk[0] == 0.0:
                carried.pop(0)
        if u != 0.0:
            carried.append([u, float(i)])
    residual = sum(abs(c[0]) for c in carried)
    return charge + outright * residual


def commodity_charge(
    positions: list[SSACommodityPosition],
    method: CommodityMethod = CommodityMethod.MATURITY_LADDER,
) -> float:
    """Sum over commodities (Art 359(6), 360(2), p. 391)."""
    by_c: dict[str, list[SSACommodityPosition]] = defaultdict(list)
    for q in positions:
        by_c[q.commodity].append(q)
    total = 0.0
    for group in by_c.values():
        if method is CommodityMethod.SIMPLIFIED:
            net = sum(q.units * q.spot_price for q in group)
            gross = sum(abs(q.units) * q.spot_price for q in group)
            total += p.SSA_COMMODITY_SIMPLE_NET * abs(net) + p.SSA_COMMODITY_SIMPLE_GROSS * gross
            continue
        items = [(q.units * q.spot_price, q.maturity_years) for q in group]
        if method is CommodityMethod.EXTENDED_LADDER:
            spread, carry, outright = p.SSA_COMMODITY_EXTENDED.get(
                group[0].category, p.SSA_COMMODITY_EXTENDED["OTHER"]
            )
        else:
            spread, carry, outright = (
                p.SSA_COMMODITY_SPREAD, p.SSA_COMMODITY_CARRY, p.SSA_COMMODITY_OUTRIGHT
            )
        total += ladder_commodity(items, spread, carry, outright)
    return total


# =========================================================================
#  Options -- non-delta risk (Art 352a)
# =========================================================================


def option_non_delta(options: list[SSAOptionNonDelta]) -> dict[str, float]:
    """Non-delta requirement per risk type (Art 352a, p. 382-387).

    Simplified approach: max(0, gross amount - risk-weighted delta equivalent) (Art 352a(5)(a)).
    Delta-plus gamma: per distinct underlying type sum 1/2 x Gamma x VU^2; requirement = |sum of
    the negative sums| (Art 352a(7)). Delta-plus vega: per underlying type sum vega x 25% x
    implied vol; requirement = sum of absolute values (Art 352a(8)).
    """
    out: dict[str, float] = defaultdict(float)
    gamma: dict[tuple[str, str], float] = defaultdict(float)
    vega: dict[tuple[str, str], float] = defaultdict(float)
    for o in options:
        rt = o.risk_type.value
        if o.gross_amount is not None and o.rw_delta_equivalent is not None:
            out[rt] += max(0.0, o.gross_amount - o.rw_delta_equivalent)
        if o.gamma is not None and o.vu is not None:
            gamma[(rt, o.underlying_type)] += p.SSA_GAMMA_FACTOR * o.gamma * o.vu**2
        if o.vega is not None and o.implied_vol is not None:
            vega[(rt, o.underlying_type)] += o.vega * p.SSA_OPTION_VOL_SHIFT * o.implied_vol
    for (rt, _u), g in gamma.items():
        if g < 0.0:
            out[rt] += -g
    for (rt, _u), v in vega.items():
        out[rt] += abs(v)
    return dict(out)


_OPTION_MULTIPLIER: dict[str, float] = {
    SSARiskType.DEBT.value: p.SSA_MULTIPLIER_DEBT,
    SSARiskType.EQUITY.value: p.SSA_MULTIPLIER_EQUITY,
    SSARiskType.FX.value: p.SSA_MULTIPLIER_FX,
    SSARiskType.COMMODITY.value: p.SSA_MULTIPLIER_COMMODITY,
}
"""# TODO: VERIFY -- Art 325(2) (p. 226-227) does not list Art 352a separately; the non-delta
option charge is scaled with the multiplier of the underlying's risk category."""


def simplified_standardised(inputs: SSAInputs) -> SSAResult:
    """Total SSA requirement = sum of the Art 325(2) scaled components (p. 226-227); RWA =
    12.5 x requirement (Art 92(4)(b), p. 15)."""
    d_spec = debt_specific_risk(inputs.debt)
    d_gen = debt_general_risk(inputs.debt, inputs.general_risk_method, inputs.reverse_zone_order)
    e_spec, e_gen = equity_charges(inputs.equities)
    ciu = ciu_charge(inputs.cius)
    fx = fx_charge(
        inputs.fx,
        inputs.reporting_currency,
        inputs.total_own_funds,
        inputs.closely_correlated_matched,
    )
    com = commodity_charge(inputs.commodities, inputs.commodity_method)
    opts = option_non_delta(inputs.options)
    scaled = {
        "debt": p.SSA_MULTIPLIER_DEBT * (d_spec + d_gen),
        "equity": p.SSA_MULTIPLIER_EQUITY * (e_spec + e_gen),
        "ciu": p.SSA_MULTIPLIER_CIU * ciu,
        "fx": p.SSA_MULTIPLIER_FX * fx,
        "commodity": p.SSA_MULTIPLIER_COMMODITY * com,
    }
    for rt, v in opts.items():
        scaled[f"options_{rt.lower()}"] = _OPTION_MULTIPLIER[rt] * v
    total = sum(scaled.values())
    return SSAResult(
        debt_specific=d_spec,
        debt_general=d_gen,
        equity_specific=e_spec,
        equity_general=e_gen,
        ciu=ciu,
        fx=fx,
        commodity=com,
        options_non_delta=opts,
        scaled=scaled,
        total=total,
        rwa=p.RWA_MULTIPLIER * total,
        citations={
            "multipliers": "Market Risk: General Provisions (CRR) Part Art 325(2) (p. 226-227)",
            "debt": "Market Risk: Simplified Standardised Approach (CRR) Part Art 334-340",
            "equity": "Art 341-344",
            "ciu": "Art 348",
            "fx": "Art 351-354",
            "commodity": "Art 355-361",
            "options": "Art 352a",
            "rwa": "Required Level of Own Funds (CRR) Part Art 92(4)(b) (p. 15)",
        },
    )


def ssa_eligible(business_size: float, total_assets: float) -> bool:
    """Art 325a(1) (p. 231): on- and off-balance-sheet market-risk business (Art 325a(2):
    |long| + |short| at market value) <= 10% of total assets and <= GBP 440 million."""
    return (
        business_size <= p.SSA_ELIGIBILITY_TOTAL_ASSETS_SHARE * total_assets
        and business_size <= p.SSA_ELIGIBILITY_ABSOLUTE_GBP_M
    )
