"""Simplified standardised approach (Basel Framework MAR40) -- extra method.

Capital = 1.30 x CR_IRR + 3.50 x CR_EQ + 1.20 x CR_FX + 1.90 x CR_COMM (MAR40.2, p. 688);
RWA = 12.5 x capital (MAR40.1).

Implemented:
    - Interest rate specific risk, MAR40.6 Table 1 (government / qualifying / other)
    - Interest rate general market risk, maturity method MAR40.23-40.28 (Table 4 weights,
      10% vertical disallowance, Table 5 horizontal disallowances, net position), one ladder
      per currency summed without offsetting (MAR40.24)
    - Equity, MAR40.42-40.47 (8% specific on gross, 8% general on net per market, 2% index add-on)
    - FX shorthand method, MAR40.59-40.61 (8% of max(sum net long, sum |net short|) + |gold|)
    - Commodities: simplified approach MAR40.72-40.73 (15% net + 3% gross) and maturity-ladder
      approach MAR40.68-40.70 (1.5% spread rate, 0.6% carry, 15% residual)
    - Options, simplified approach MAR40.76 Table 11

Not implemented (outside the scope of the input models below): the duration method (MAR40.29),
securitisation specific risk (MAR40.12-40.21), credit-derivative offsetting (MAR40.16-40.18),
the delta-plus and scenario methods for options (MAR40.77-40.86). Inputs to these must be
computed upstream and passed as ``other_irr_capital`` etc. on :class:`SSAInputs`.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from pydantic import BaseModel, Field

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.bcbs.frtb import params as p

R = RatingBucket


class SSAIssuerCategory(str, Enum):  # noqa: UP042 -- repo convention
    """MAR40.6 Table 1 categories (MAR40.7-40.11)."""

    GOVERNMENT = "GOVERNMENT"
    QUALIFYING = "QUALIFYING"
    OTHER = "OTHER"


class SSADebtPosition(BaseModel):
    """A debt / interest-rate position for MAR40.3-40.28 (market value, signed long +/short -)."""

    position_id: str
    issue_id: str = Field(description="Identical issue key for specific-risk offsetting (MAR40.5)")
    currency: str
    amount: float = Field(description="Market value; long positive, short negative")
    residual_maturity_years: float = Field(ge=0.0)
    coupon: float = Field(default=0.05, description="Annual coupon rate (low coupon < 3%)")
    category: SSAIssuerCategory = SSAIssuerCategory.OTHER
    rating: RatingBucket = RatingBucket.UNRATED
    general_market_risk_only: bool = False
    """True for derivatives legs without issuer risk (e.g. swaps, FRAs): no specific risk."""


class SSAEquityPosition(BaseModel):
    """An equity position (MAR40.41-40.47)."""

    position_id: str
    issue_id: str
    market: str = Field(description="National market (MAR40.42)")
    amount: float = Field(description="Market value; long positive, short negative")
    is_diversified_index: bool = False
    """Diversified index contract: 2% add-on on its net position (MAR40.47)."""


class SSACommodityPosition(BaseModel):
    """A commodity position at spot value (MAR40.68, 40.73)."""

    position_id: str
    commodity: str
    amount: float = Field(description="Spot-valued position; long positive, short negative")
    maturity_years: float = Field(default=0.0, ge=0.0)


class SSAOptionPosition(BaseModel):
    """A purchased option for the MAR40.76 simplified approach."""

    position_id: str
    structure: str = Field(description="'HEDGED' (long cash + long put / short cash + long call) "
                                       "or 'NAKED' (long call / long put)")
    underlying_value: float = Field(ge=0.0)
    charge_rate: float = Field(ge=0.0, description="Specific + general charge of the underlying "
                                                  "(e.g. 0.16 equity, 0.08 FX, 0.15 commodity)")
    in_the_money: float = Field(default=0.0, ge=0.0)
    option_value: float = Field(default=0.0, ge=0.0)
    risk_class: str = Field(description="IRR / EQ / FX / COMM")


class SSAInputs(BaseModel):
    """Portfolio for the simplified standardised approach."""

    debt: list[SSADebtPosition] = Field(default_factory=list)
    equities: list[SSAEquityPosition] = Field(default_factory=list)
    fx_net_positions: dict[str, float] = Field(
        default_factory=dict, description="Net position per foreign currency (reporting ccy)")
    gold_net_position: float = 0.0
    commodities: list[SSACommodityPosition] = Field(default_factory=list)
    commodity_method: str = Field(default="SIMPLIFIED", description="SIMPLIFIED or LADDER")
    options: list[SSAOptionPosition] = Field(default_factory=list)
    other_irr_capital: float = 0.0
    other_eq_capital: float = 0.0
    other_fx_capital: float = 0.0
    other_comm_capital: float = 0.0


# -------------------------------------------------------------------------
#  Interest rate
# -------------------------------------------------------------------------


def _maturity_key(m: float) -> str:
    """MAR40.6 Table 1 residual-maturity bands."""
    if m <= p.SSA_MATURITY_SHORT_YEARS:
        return "LE_6M"
    return "6M_TO_24M" if m <= p.SSA_MATURITY_MEDIUM_YEARS else "GT_24M"


def specific_risk_rate(pos: SSADebtPosition) -> float:
    """MAR40.6 Table 1."""
    if pos.general_market_risk_only:
        return 0.0
    if pos.category is SSAIssuerCategory.GOVERNMENT:
        if pos.rating is R.AAA_TO_AA_MINUS:
            return p.SSA_GOVT_SPECIFIC["AAA_TO_AA-"]
        if pos.rating in (R.A_PLUS_TO_A_MINUS, R.BBB_PLUS_TO_BBB_MINUS):
            return p.SSA_GOVT_SPECIFIC["A+_TO_BBB-_" + _maturity_key(pos.residual_maturity_years)]
        if pos.rating in (R.BB_PLUS_TO_BB_MINUS, R.B_PLUS_TO_B_MINUS):
            return p.SSA_GOVT_SPECIFIC["BB+_TO_B-"]
        if pos.rating is R.BELOW_B_MINUS:
            return p.SSA_GOVT_SPECIFIC["BELOW_B-"]
        return p.SSA_GOVT_SPECIFIC["UNRATED"]
    if pos.category is SSAIssuerCategory.QUALIFYING:
        return p.SSA_QUALIFYING_SPECIFIC[_maturity_key(pos.residual_maturity_years)]
    if pos.rating is R.BB_PLUS_TO_BB_MINUS:
        return p.SSA_OTHER_SPECIFIC["BB+_TO_BB-"]
    if pos.rating in (R.B_PLUS_TO_B_MINUS, R.BELOW_B_MINUS):
        return p.SSA_OTHER_SPECIFIC["BELOW_BB-"]
    return p.SSA_OTHER_SPECIFIC["UNRATED"]


def ir_specific_risk(debt: list[SSADebtPosition]) -> float:
    """MAR40.5-40.6: net per identical issue, charge on the absolute net position."""
    by_issue: dict[str, list[SSADebtPosition]] = defaultdict(list)
    for d in debt:
        by_issue[d.issue_id].append(d)
    total = 0.0
    for items in by_issue.values():
        net = sum(i.amount for i in items)
        total += abs(net) * specific_risk_rate(items[0])
    return total


def maturity_band(m: float, coupon: float) -> int:
    """Index (0-based) of the MAR40.26 Table 4 time band."""
    low = coupon < p.SSA_LOW_COUPON_THRESHOLD
    for i, (hi_normal, hi_low, _, _) in enumerate(p.SSA_MATURITY_BANDS):
        if m <= (hi_low if low else hi_normal):
            return i
    if low:
        for j, (hi, _, _) in enumerate(p.SSA_LOW_COUPON_EXTRA_BANDS):
            if m <= hi:
                return len(p.SSA_MATURITY_BANDS) + j
    return len(p.SSA_MATURITY_BANDS) - 1


def band_weight(idx: int) -> float:
    """MAR40.26 Table 4 risk weight of band ``idx``."""
    if idx < len(p.SSA_MATURITY_BANDS):
        return p.SSA_MATURITY_BANDS[idx][2]
    return p.SSA_LOW_COUPON_EXTRA_BANDS[idx - len(p.SSA_MATURITY_BANDS)][1]


def ladder_capital(weighted: list[tuple[float, float]]) -> float:
    """General market risk for one currency ladder (MAR40.23, 40.27-40.28).

    ``weighted`` holds (weighted long, weighted short) per band (15 bands; shorts positive).
    Capital = 10% vertical + horizontal (Table 5) + |overall net position|.
    """
    vertical = 0.0
    net_band: list[float] = []
    for lg, sh in weighted:
        vertical += p.SSA_VERTICAL_DISALLOWANCE * min(lg, sh)
        net_band.append(lg - sh)
    horizontal = 0.0
    zone_net: dict[int, float] = {}
    for z in (1, 2, 3):
        vals = [n for n, zz in zip(net_band, p.SSA_ZONE_OF_BAND, strict=False) if zz == z]
        lz = sum(v for v in vals if v > 0)
        sz = -sum(v for v in vals if v < 0)
        horizontal += p.SSA_HORIZONTAL_WITHIN_ZONE[z] * min(lz, sz)
        zone_net[z] = lz - sz

    def offset(a: int, b: int, rate: float) -> float:
        x, y = zone_net[a], zone_net[b]
        if x * y >= 0:
            return 0.0
        m = min(abs(x), abs(y))
        zone_net[a] = x - m if x > 0 else x + m
        zone_net[b] = y - m if y > 0 else y + m
        return rate * m

    horizontal += offset(1, 2, p.SSA_HORIZONTAL_ADJACENT)
    horizontal += offset(2, 3, p.SSA_HORIZONTAL_ADJACENT)
    horizontal += offset(1, 3, p.SSA_HORIZONTAL_ZONE1_ZONE3)
    net = abs(sum(net_band))
    return net + vertical + horizontal


def ir_general_market_risk(debt: list[SSADebtPosition]) -> float:
    """MAR40.24-40.28: one maturity ladder per currency, summed without offsetting."""
    n_bands = len(p.SSA_MATURITY_BANDS) + len(p.SSA_LOW_COUPON_EXTRA_BANDS)
    ladders: dict[str, list[list[float]]] = defaultdict(lambda: [[0.0, 0.0] for _ in
                                                                 range(n_bands)])
    for d in debt:
        idx = maturity_band(d.residual_maturity_years, d.coupon)
        w = band_weight(idx) * d.amount
        cell = ladders[d.currency][idx]
        if w >= 0:
            cell[0] += w
        else:
            cell[1] += -w
    return sum(ladder_capital([(c[0], c[1]) for c in lad]) for lad in ladders.values())


# -------------------------------------------------------------------------
#  Equity, FX, commodities, options
# -------------------------------------------------------------------------


def equity_capital(eqs: list[SSAEquityPosition]) -> float:
    """MAR40.42-40.47: 8% gross specific + 8% net general per market + 2% index net."""
    by_issue: dict[tuple[str, str], float] = defaultdict(float)
    index_net: dict[tuple[str, str], float] = defaultdict(float)
    for e in eqs:
        by_issue[(e.market, e.issue_id)] += e.amount  # MAR40.46 matched positions offset
        if e.is_diversified_index:
            index_net[(e.market, e.issue_id)] += e.amount
    specific = p.SSA_EQUITY_SPECIFIC * sum(abs(v) for v in by_issue.values())
    by_market: dict[str, float] = defaultdict(float)
    for (mkt, _), v in by_issue.items():
        by_market[mkt] += v
    general = p.SSA_EQUITY_GENERAL * sum(abs(v) for v in by_market.values())
    index_addon = p.SSA_EQUITY_INDEX_ADDON * sum(abs(v) for v in index_net.values())
    return specific + general + index_addon


def fx_capital(net_positions: dict[str, float], gold: float) -> float:
    """MAR40.60-40.61: 8% x (max(sum net long, sum |net short|) + |gold|)."""
    longs = sum(v for v in net_positions.values() if v > 0)
    shorts = -sum(v for v in net_positions.values() if v < 0)
    return p.SSA_FX_CHARGE * (max(longs, shorts) + abs(gold))


def commodity_simplified(cs: list[SSACommodityPosition]) -> float:
    """MAR40.72-40.73: per commodity 15% x |net| + 3% x (long + short)."""
    by_c: dict[str, list[float]] = defaultdict(list)
    for c in cs:
        by_c[c.commodity].append(c.amount)
    total = 0.0
    for amts in by_c.values():
        total += p.SSA_COMMODITY_SIMPLIFIED_NET * abs(sum(amts))
        total += p.SSA_COMMODITY_SIMPLIFIED_GROSS * sum(abs(a) for a in amts)
    return total


def commodity_ladder_one(positions: list[SSACommodityPosition]) -> float:
    """MAR40.68-40.70 for one commodity (spot-valued positions).

    In each band, matched long/short x 1.5% x 2 (the "sum of short and long positions that are
    matched", MAR40.69); residual net carried forward with 0.6% per band carried (MAR40.70) and
    matched against later bands; the final residual attracts 15%.
    """
    nb = len(p.SSA_COMMODITY_BANDS)
    longs = [0.0] * nb
    shorts = [0.0] * nb
    for c in positions:
        idx = next(i for i, hi in enumerate(p.SSA_COMMODITY_BANDS) if c.maturity_years <= hi)
        if c.amount >= 0:
            longs[idx] += c.amount
        else:
            shorts[idx] += -c.amount
    capital = 0.0
    carry = 0.0  # signed residual carried forward
    outright = 0.0  # residuals no longer carried (no opposite exposure further out)
    for i in range(nb):
        lg, sh = longs[i] + max(carry, 0.0), shorts[i] + max(-carry, 0.0)
        matched = min(lg, sh)
        capital += p.SSA_COMMODITY_SPREAD_RATE * 2.0 * matched
        net = lg - sh
        later = shorts[i + 1:] if net > 0 else longs[i + 1:]
        if net != 0 and any(x > 0 for x in later):
            capital += p.SSA_COMMODITY_CARRY_RATE * abs(net)  # one band carried forward
            carry = net
        else:
            outright += abs(net)
            carry = 0.0
    capital += p.SSA_COMMODITY_OUTRIGHT * outright
    return capital


def commodity_ladder(cs: list[SSACommodityPosition]) -> float:
    """MAR40.69: a separate ladder per commodity."""
    by_c: dict[str, list[SSACommodityPosition]] = defaultdict(list)
    for c in cs:
        by_c[c.commodity].append(c)
    return sum(commodity_ladder_one(v) for v in by_c.values())


def option_capital(o: SSAOptionPosition) -> float:
    """MAR40.76 Table 11."""
    gross = o.underlying_value * o.charge_rate
    if o.structure.upper() == "HEDGED":
        return max(gross - o.in_the_money, 0.0)
    return min(gross, o.option_value)


def ssa_capital(inputs: SSAInputs) -> dict[str, float]:
    """MAR40.2 scaled capital by risk class, total and RWA (MAR40.1)."""
    opt: dict[str, float] = defaultdict(float)
    for o in inputs.options:
        opt[o.risk_class.upper()] += option_capital(o)
    cr_irr = (ir_specific_risk(inputs.debt) + ir_general_market_risk(inputs.debt)
              + opt["IRR"] + inputs.other_irr_capital)
    cr_eq = equity_capital(inputs.equities) + opt["EQ"] + inputs.other_eq_capital
    cr_fx = (fx_capital(inputs.fx_net_positions, inputs.gold_net_position) + opt["FX"]
             + inputs.other_fx_capital)
    comm = (commodity_ladder(inputs.commodities) if inputs.commodity_method.upper() == "LADDER"
            else commodity_simplified(inputs.commodities))
    cr_comm = comm + opt["COMM"] + inputs.other_comm_capital
    sf = p.SSA_SCALING
    total = cr_irr * sf["IRR"] + cr_eq * sf["EQ"] + cr_fx * sf["FX"] + cr_comm * sf["COMM"]
    return {"irr": cr_irr, "eq": cr_eq, "fx": cr_fx, "comm": cr_comm, "total": total,
            "rwa": total * p.RWA_MULTIPLIER}


__all__ = [
    "SSACommodityPosition",
    "SSADebtPosition",
    "SSAEquityPosition",
    "SSAInputs",
    "SSAIssuerCategory",
    "SSAOptionPosition",
    "commodity_ladder",
    "commodity_simplified",
    "equity_capital",
    "fx_capital",
    "ir_general_market_risk",
    "ir_specific_risk",
    "ladder_capital",
    "maturity_band",
    "option_capital",
    "specific_risk_rate",
    "ssa_capital",
]
