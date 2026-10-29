"""Basel MAR40 simplified standardised approach -- comparison method for the CA package.

**OSFI has not adopted MAR40.** CAR 2026 Ch.9 s.9.1.2.2 [MAR11.7] offers "two broad
methodologies: the standardized approach and internal models approach (IMA)", and CAR Ch.1
s.1.3.2 [RBC20.9] lists only "The standardized approach, as described in section 9.5; or The
internal models approach set out in section 9.6" (the Basel RBC20.9 option of MAR40 is omitted).
Chapter 9 applies only to internationally active institutions and D-SIBs; other institutions are
outside the market-risk framework altogether unless OSFI applies it case by case.

This module therefore transcribes the Basel Framework text (MAR40, version effective 1 January
2023) so the multi-jurisdiction comparison can show what a MAR40 bank would hold. Every result
carries ``permitted_under_car = False``. All values cite MAR40 paragraphs; see params.py.

Implemented: MAR40.2 scaling; interest-rate specific risk (MAR40.5-40.14, 40.16-40.20 via
caller-netted issues) and general market risk by the maturity method (MAR40.23-40.28); equity
specific / general and the 2% index add-on (MAR40.41-40.52); FX shorthand method (MAR40.53-
40.61); commodities simplified approach and maturity ladder (MAR40.63-40.73); options simplified
approach (MAR40.76) and delta-plus gamma / vega (MAR40.77-40.80). Not implemented: duration
method (MAR40.29), nth-to-default and CTP specific-risk rules (MAR40.21-40.22), the scenario
approach (MAR40.81-40.85) -- callers may pass those amounts through ``other_option_capital``.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from pydantic import BaseModel, Field

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.ca.frtb import params as p


class SSAIssuerCategory(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """MAR40.6 Table 1 issuer categories (plus securitisation, MAR40.14)."""

    GOVERNMENT = "GOVERNMENT"
    QUALIFYING = "QUALIFYING"
    OTHER = "OTHER"
    SECURITISATION = "SECURITISATION"
    NONE = "NONE"
    """Interest-rate derivatives with no issuer (no specific risk)."""


class SSAInterestRatePosition(BaseModel):
    """A debt / interest-rate position for MAR40.3-40.40 (market values in reporting ccy)."""

    issue_id: str
    currency: str
    is_long: bool
    market_value: float = Field(ge=0.0)
    residual_maturity_years: float = Field(ge=0.0)
    """Residual maturity (fixed rate) or time to next repricing (floating), MAR40.25."""
    coupon: float = 0.05
    issuer_category: SSAIssuerCategory = SSAIssuerCategory.OTHER
    rating: RatingBucket = RatingBucket.UNRATED
    securitisation_banking_book_rw: float | None = None


class SSAEquityPosition(BaseModel):
    """An equity position for MAR40.41-40.52."""

    issue_id: str
    national_market: str
    is_long: bool
    market_value: float = Field(ge=0.0)
    is_diversified_index: bool = False


class SSACommodityPosition(BaseModel):
    """A commodity position (spot-valued) for MAR40.63-40.73."""

    commodity: str
    is_long: bool
    market_value: float = Field(ge=0.0)
    maturity_years: float = Field(default=0.0, ge=0.0)


class SSAOptionSimplified(BaseModel):
    """A purchased-option trade under the MAR40.76 Table 11 simplified approach."""

    risk_class: str = Field(description="IRR / EQ / FX / COMM")
    hedged_with_underlying: bool
    """True: long cash + long put or short cash + long call; False: naked long call / put."""
    underlying_market_value: float = Field(ge=0.0)
    option_market_value: float = Field(default=0.0, ge=0.0)
    in_the_money_amount: float = Field(default=0.0, ge=0.0)
    charge_rate: float | None = None
    """Specific + general charge of the underlying (EQ 16%, FX 8%, COMM 15% by default)."""


class SSAOptionGreeks(BaseModel):
    """Delta-plus inputs for one option (MAR40.80)."""

    risk_class: str = Field(description="IRR / EQ / FX / COMM")
    underlying_id: str
    gamma: float = 0.0
    underlying_value: float = 0.0
    vu_rate: float | None = None
    """MAR40.80(2): EQ 8%, FX 8%, COMM 15%; IRR = the MAR40.26 band risk weight (required)."""
    vega: float = 0.0
    """Change in value per 1.00 (100 vol points) change in implied volatility."""
    implied_vol: float = 0.0


class SSAResult(BaseModel):
    """MAR40 capital (reporting currency)."""

    interest_rate: float = 0.0
    equity: float = 0.0
    fx: float = 0.0
    commodity: float = 0.0
    scaled_total: float = 0.0
    rwa: float = 0.0
    permitted_under_car: bool = p.SSA_PERMITTED_UNDER_CAR
    detail: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


_DEFAULT_OPTION_RATE: dict[str, float] = {
    "EQ": p.SSA_EQUITY_SPECIFIC + p.SSA_EQUITY_GENERAL,
    "FX": p.SSA_FX_CHARGE,
    "COMM": p.SSA_COMMODITY_DIRECTIONAL,
}
"""MAR40.76 footnote 344 -- currency options 8%, commodities 15%; equities 8% + 8%."""


# =========================================================================
#  Interest rate risk
# =========================================================================

_IG = frozenset({
    RatingBucket.AAA_TO_AA_MINUS, RatingBucket.A_PLUS_TO_A_MINUS,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS,
})


def _qualifying_rate(maturity: float) -> float:
    for upper, rate in p.SSA_SPECIFIC_RISK_QUALIFYING:
        if maturity <= upper:
            return rate
    return p.SSA_SPECIFIC_RISK_QUALIFYING[-1][1]


def specific_risk_rate(pos: SSAInterestRatePosition) -> float:
    """MAR40.6 Table 1 specific-risk charge (MAR40.9: IG-rated securities are qualifying)."""
    cat, r = pos.issuer_category, pos.rating
    if cat == SSAIssuerCategory.NONE:
        return 0.0
    if cat == SSAIssuerCategory.SECURITISATION:
        rw = p.DRC_SEC_MISSING_BB_RW if pos.securitisation_banking_book_rw is None else (
            pos.securitisation_banking_book_rw
        )
        return rw / p.RWA_MULTIPLIER  # MAR40.14: banking-book RW divided by 12.5
    if cat == SSAIssuerCategory.GOVERNMENT:
        if r == RatingBucket.AAA_TO_AA_MINUS:
            return p.SSA_SPECIFIC_RISK_GOV_AAA_AA
        if r in (RatingBucket.A_PLUS_TO_A_MINUS, RatingBucket.BBB_PLUS_TO_BBB_MINUS):
            return _qualifying_rate(pos.residual_maturity_years)
        if r == RatingBucket.BELOW_B_MINUS:
            return p.SSA_SPECIFIC_RISK_12PCT
        return p.SSA_SPECIFIC_RISK_8PCT  # BB+ to B-, unrated
    if cat == SSAIssuerCategory.QUALIFYING or r in _IG:
        return _qualifying_rate(pos.residual_maturity_years)
    if r in (RatingBucket.B_PLUS_TO_B_MINUS, RatingBucket.BELOW_B_MINUS):
        return p.SSA_SPECIFIC_RISK_12PCT  # "Below BB-"
    return p.SSA_SPECIFIC_RISK_8PCT  # BB+ to BB-, unrated


def ir_specific_risk(positions: list[SSAInterestRatePosition]) -> float:
    """Σ rate × |net position per identical issue| (MAR40.5: offsetting only within an issue)."""
    net: dict[str, float] = defaultdict(float)
    rate: dict[str, float] = {}
    for pos in positions:
        net[pos.issue_id] += pos.market_value if pos.is_long else -pos.market_value
        rate[pos.issue_id] = specific_risk_rate(pos)
    return sum(rate[i] * abs(v) for i, v in net.items())


def maturity_band(maturity: float, coupon: float) -> int:
    """Row index 0..14 in MAR40.26 Table 4 (rows 13-14 only for coupons below 3%)."""
    low = coupon < p.SSA_LOW_COUPON_THRESHOLD
    for i, (hi_normal, hi_low, _rw, _dy, _z) in enumerate(p.SSA_MATURITY_BANDS[:-1]):
        if maturity <= (hi_low if low else hi_normal):
            return i
    if not low:
        return len(p.SSA_MATURITY_BANDS) - 1
    if maturity <= p.SSA_MATURITY_BANDS[-1][1]:
        return len(p.SSA_MATURITY_BANDS) - 1
    for k, (hi, _rw, _dy, _z) in enumerate(p.SSA_LOW_COUPON_EXTRA_BANDS):
        if maturity <= hi:
            return len(p.SSA_MATURITY_BANDS) + k
    return len(p.SSA_MATURITY_BANDS) + len(p.SSA_LOW_COUPON_EXTRA_BANDS) - 1


def band_weight_and_zone(row: int) -> tuple[float, int]:
    """(risk weight, zone) of a Table 4 row (MAR40.26, MAR40.28)."""
    n = len(p.SSA_MATURITY_BANDS)
    if row < n:
        _a, _b, rw, _dy, zone = p.SSA_MATURITY_BANDS[row]
        return rw, zone
    _hi, rw, _dy, zone = p.SSA_LOW_COUPON_EXTRA_BANDS[row - n]
    return rw, zone


def ladder_general_market_risk(rows: dict[int, tuple[float, float]]) -> dict[str, float]:
    """General market risk of one currency ladder (MAR40.23, MAR40.27-40.28).

    ``rows`` maps Table 4 row -> (weighted long, weighted short) (both >= 0). Horizontal offsetting
    order: zone 1 vs zone 2, then zone 2 vs zone 3 (adjacent, 40%), then zone 1 vs zone 3 (100%).
    """
    # TODO: VERIFY -- MAR40.28 does not prescribe the order of the cross-zone offsets; the
    # adjacent-zone offsets are done first (1-2, then 2-3), then 1-3.
    vertical = 0.0
    zone_long: dict[int, float] = defaultdict(float)
    zone_short: dict[int, float] = defaultdict(float)
    for row, (lng, sht) in rows.items():
        vertical += p.SSA_VERTICAL_DISALLOWANCE * min(lng, sht)
        _rw, zone = band_weight_and_zone(row)
        net = lng - sht
        if net > 0:
            zone_long[zone] += net
        else:
            zone_short[zone] += -net
    within = 0.0
    zone_net: dict[int, float] = {}
    for z in (1, 2, 3):
        within += p.SSA_HORIZONTAL_WITHIN_ZONE[z] * min(zone_long[z], zone_short[z])
        zone_net[z] = zone_long[z] - zone_short[z]
    across = 0.0
    for a, b, rate in (
        (1, 2, p.SSA_HORIZONTAL_ADJACENT),
        (2, 3, p.SSA_HORIZONTAL_ADJACENT),
        (1, 3, p.SSA_HORIZONTAL_ZONE1_ZONE3),
    ):
        if zone_net[a] * zone_net[b] < 0.0:
            m = min(abs(zone_net[a]), abs(zone_net[b]))
            across += rate * m
            zone_net[a] -= m if zone_net[a] > 0 else -m
            zone_net[b] -= m if zone_net[b] > 0 else -m
    net_position = p.SSA_NET_POSITION_CHARGE * abs(sum(zone_net.values()))
    return {
        "vertical": vertical, "horizontal_within": within, "horizontal_across": across,
        "net_position": net_position,
        "total": vertical + within + across + net_position,
    }


def ir_general_market_risk(positions: list[SSAInterestRatePosition]) -> float:
    """Maturity method, a separate ladder per currency, summed (MAR40.24-40.28)."""
    ladders: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0.0])
    )
    for pos in positions:
        row = maturity_band(pos.residual_maturity_years, pos.coupon)
        rw, _zone = band_weight_and_zone(row)
        cell = ladders[pos.currency.upper()][row]
        cell[0 if pos.is_long else 1] += rw * pos.market_value
    return sum(
        ladder_general_market_risk({r: (c[0], c[1]) for r, c in rows.items()})["total"]
        for rows in ladders.values()
    )


# =========================================================================
#  Equity, FX, commodities
# =========================================================================


def equity_capital(positions: list[SSAEquityPosition]) -> float:
    """MAR40.42-40.47: per national market, specific 8% of gross (2% for diversified indices,
    Table 8) plus general 8% of |net|; the 2% index add-on on the net index position."""
    total = 0.0
    markets: dict[str, list[SSAEquityPosition]] = defaultdict(list)
    for pos in positions:
        markets[pos.national_market].append(pos)
    for plist in markets.values():
        net_issue: dict[str, float] = defaultdict(float)
        is_index: dict[str, bool] = {}
        for pos in plist:
            net_issue[pos.issue_id] += pos.market_value if pos.is_long else -pos.market_value
            is_index[pos.issue_id] = pos.is_diversified_index
        specific = sum(
            (p.SSA_EQUITY_INDEX_ADDON if is_index[i] else p.SSA_EQUITY_SPECIFIC) * abs(v)
            for i, v in net_issue.items()
        )
        general = p.SSA_EQUITY_GENERAL * abs(sum(net_issue.values()))
        total += specific + general
    return total


def fx_capital(net_by_currency: dict[str, float], gold_net: float = 0.0) -> float:
    """Shorthand method: 8% × (max(Σ net long, Σ |net short|) + |gold|) (MAR40.60-40.61)."""
    longs = sum(v for v in net_by_currency.values() if v > 0)
    shorts = sum(-v for v in net_by_currency.values() if v < 0)
    return p.SSA_FX_CHARGE * (max(longs, shorts) + abs(gold_net))


def commodity_simplified(positions: list[SSACommodityPosition]) -> float:
    """15% of |net| + 3% of gross per commodity (MAR40.72-40.73)."""
    net: dict[str, float] = defaultdict(float)
    gross: dict[str, float] = defaultdict(float)
    for pos in positions:
        net[pos.commodity] += pos.market_value if pos.is_long else -pos.market_value
        gross[pos.commodity] += pos.market_value
    return sum(
        p.SSA_COMMODITY_DIRECTIONAL * abs(net[c]) + p.SSA_COMMODITY_GROSS * gross[c] for c in net
    )


def _commodity_band(maturity: float) -> int:
    for i, hi in enumerate(p.SSA_COMMODITY_LADDER_BANDS):
        if maturity <= hi:
            return i
    return len(p.SSA_COMMODITY_LADDER_BANDS) - 1


def commodity_ladder_one(positions: list[SSACommodityPosition]) -> float:
    """Maturity ladder for one commodity (MAR40.69-40.70).

    In each band 1.5% of (matched long + matched short); the residual net is carried forward to the
    next band holding an opposite position, with 0.6% of the carried amount per band moved and
    1.5% on the newly matched amounts; the final open position is charged 15%.
    """
    # TODO: VERIFY -- MAR40.70 does not say whether a residual with no opposite position further
    # out is still "carried forward"; here it is carried only towards an offsetting band.
    n = len(p.SSA_COMMODITY_LADDER_BANDS)
    longs, shorts = [0.0] * n, [0.0] * n
    for pos in positions:
        b = _commodity_band(pos.maturity_years)
        if pos.is_long:
            longs[b] += pos.market_value
        else:
            shorts[b] += pos.market_value
    charge = 0.0
    nets: list[float] = []
    for b in range(n):
        matched = min(longs[b], shorts[b])
        charge += p.SSA_COMMODITY_SPREAD_RATE * 2.0 * matched
        nets.append(longs[b] - shorts[b])
    carry = 0.0
    for b in range(n):
        if carry * nets[b] < 0.0:
            m = min(abs(carry), abs(nets[b]))
            charge += p.SSA_COMMODITY_SPREAD_RATE * 2.0 * m
        carry += nets[b]
        if carry != 0.0 and any(carry * nets[j] < 0.0 for j in range(b + 1, n)):
            charge += p.SSA_COMMODITY_CARRY_RATE * abs(carry)  # carried one band further
    return charge + p.SSA_COMMODITY_DIRECTIONAL * abs(carry)


def commodity_ladder(positions: list[SSACommodityPosition]) -> float:
    """Sum of the per-commodity maturity ladders (MAR40.67-40.71)."""
    per: dict[str, list[SSACommodityPosition]] = defaultdict(list)
    for pos in positions:
        per[pos.commodity].append(pos)
    return sum(commodity_ladder_one(v) for v in per.values())


# =========================================================================
#  Options
# =========================================================================


def option_simplified_capital(opt: SSAOptionSimplified) -> float:
    """MAR40.76 Table 11."""
    rate = opt.charge_rate if opt.charge_rate is not None else _DEFAULT_OPTION_RATE.get(
        opt.risk_class.upper()
    )
    if rate is None:
        raise ValueError("MAR40.76: interest-rate options need charge_rate (specific + general)")
    base = opt.underlying_market_value * rate
    if opt.hedged_with_underlying:
        return max(base - opt.in_the_money_amount, 0.0)
    return min(base, opt.option_market_value)


def delta_plus_gamma_vega(options: list[SSAOptionGreeks]) -> dict[str, dict[str, float]]:
    """Gamma and vega capital by risk class (MAR40.80).

    Gamma impact = ½·Γ·VU², VU = underlying value × rate; netted per underlying, only net
    negative impacts count. Vega = |Σ vega × 25% × σ| per underlying, summed.
    """
    gamma_net: dict[tuple[str, str], float] = defaultdict(float)
    vega_net: dict[tuple[str, str], float] = defaultdict(float)
    for o in options:
        rc = o.risk_class.upper()
        rate = o.vu_rate if o.vu_rate is not None else p.SSA_OPTION_VU.get(rc)
        if rate is None:
            raise ValueError("MAR40.80(2)(a): IRR options need vu_rate (MAR40.26 weight)")
        vu = o.underlying_value * rate
        gamma_net[(rc, o.underlying_id)] += p.SSA_OPTION_GAMMA_HALF * o.gamma * vu * vu
        vega_net[(rc, o.underlying_id)] += o.vega * p.SSA_OPTION_VOL_SHIFT * o.implied_vol
    out: dict[str, dict[str, float]] = defaultdict(lambda: {"gamma": 0.0, "vega": 0.0})
    for (rc, _u), g in gamma_net.items():
        if g < 0.0:
            out[rc]["gamma"] += abs(g)
    for (rc, _u), v in vega_net.items():
        out[rc]["vega"] += abs(v)
    return dict(out)


# =========================================================================
#  Aggregation
# =========================================================================


def ssa_capital(
    ir_positions: list[SSAInterestRatePosition] | None = None,
    equity_positions: list[SSAEquityPosition] | None = None,
    fx_net_by_currency: dict[str, float] | None = None,
    gold_net: float = 0.0,
    commodity_positions: list[SSACommodityPosition] | None = None,
    commodity_use_ladder: bool = False,
    simplified_options: list[SSAOptionSimplified] | None = None,
    option_greeks: list[SSAOptionGreeks] | None = None,
    other_option_capital: dict[str, float] | None = None,
) -> SSAResult:
    """Capital = CR_IRR·1.30 + CR_EQ·3.50 + CR_FX·1.20 + CR_COMM·1.90 (MAR40.2); RWA = 12.5×."""
    ir_positions = ir_positions or []
    equity_positions = equity_positions or []
    commodity_positions = commodity_positions or []
    detail: dict[str, float] = {
        "ir_specific": ir_specific_risk(ir_positions),
        "ir_general": ir_general_market_risk(ir_positions),
        "equity": equity_capital(equity_positions),
        "fx": fx_capital(fx_net_by_currency or {}, gold_net),
        "commodity": (
            commodity_ladder(commodity_positions) if commodity_use_ladder
            else commodity_simplified(commodity_positions)
        ),
    }
    opt: dict[str, float] = defaultdict(float)
    for o in simplified_options or []:
        opt[o.risk_class.upper()] += option_simplified_capital(o)
    for rc, gv in delta_plus_gamma_vega(option_greeks or []).items():
        opt[rc] += gv["gamma"] + gv["vega"]
    for rc, v in (other_option_capital or {}).items():
        opt[rc.upper()] += v
    for rc, v in opt.items():
        detail[f"options_{rc}"] = v
    ir = detail["ir_specific"] + detail["ir_general"] + opt.get("IRR", 0.0)
    eq = detail["equity"] + opt.get("EQ", 0.0)
    fx = detail["fx"] + opt.get("FX", 0.0)
    comm = detail["commodity"] + opt.get("COMM", 0.0)
    sf = p.SSA_SCALING_FACTORS
    scaled = ir * sf["IRR"] + eq * sf["EQ"] + fx * sf["FX"] + comm * sf["COMM"]
    return SSAResult(
        interest_rate=ir, equity=eq, fx=fx, commodity=comm, scaled_total=scaled,
        rwa=scaled * p.RWA_MULTIPLIER, detail=detail,
        notes=[
            "Basel MAR40 simplified standardised approach -- NOT available under OSFI CAR 2026 "
            "(CAR 9.1.2.2 [MAR11.7]; Ch.1 s.1.3.2 [RBC20.9]); comparison only.",
        ],
    )
