"""EU simplified standardised approach -- CRR Article 325(2) (CRR3 point (156)) with Arts 326-361.

    OFR_SSA = 1,3 x (general + specific risk of debt, excl. securitisation)   [325(2)(a)(i)]
            + 3,5 x (general + specific risk of equity)                       [325(2)(a)(ii)]
            + 1,2 x foreign-exchange risk (Chapter 3)                         [325(2)(b)]
            + 1,9 x commodity risk (Chapter 4)                                [325(2)(c)]
            +       securitisation instruments (Article 337 / 338)            [325(2)(d)]

Eligibility (Article 325a(1), introductory wording replaced by CRR3 point (157)(b)): on- and
off-balance-sheet business subject to market risk <= 10 % of total assets and <= EUR 500
million, assessed monthly.

Input models are specific to the SSA (the SBM ``FRTBSensitivity`` contract does not carry
cash-flow positions):

* :class:`SSADebtPosition` -- net position per issue (Article 327) with the Table 1 category of
  Article 336 and the maturity / coupon / modified duration needed by Article 339 or 340;
* :class:`SSAEquityPosition` -- net position per issue with its market (Article 341);
* :class:`SSAFXPosition` -- net open position per currency or gold (Article 352);
* :class:`SSACommodityPosition` -- position per commodity at spot (Articles 357-361).
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from pydantic import BaseModel, Field

from src.jurisdictions.eu.frtb import params as p


class SSASpecificCategory(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Article 336(1) Table 1 categories (and the 10 % covered bonds of Article 336(3))."""

    ZERO_RW = "ZERO_RW"
    QUALIFYING = "QUALIFYING"  # 20 % / 50 % SA RW and other qualifying items (336(4))
    RW_100 = "RW_100"
    RW_150 = "RW_150"
    COVERED_BOND_10PCT = "COVERED_BOND_10PCT"


class SSADebtPosition(BaseModel):
    """Net position in one debt issue (Articles 327, 334, 336, 339, 340)."""

    position_id: str
    currency: str = "EUR"
    is_long: bool = True
    amount: float = Field(ge=0.0, description="Market value of the net position (reporting ccy)")
    category: SSASpecificCategory = SSASpecificCategory.RW_100
    residual_maturity_years: float = Field(default=1.0, ge=0.0)
    coupon: float = Field(default=0.03, description="Coupon rate, decimal (Art 339(2))")
    modified_duration: float | None = Field(default=None, ge=0.0, description="Art 340(3)")
    is_securitisation: bool = False
    banking_book_risk_weight: float | None = None
    """Securitisation RW in the non-trading book (Article 337(1)), decimal."""
    in_correlation_trading_portfolio: bool = False
    """Article 338 (CRR3 point (191)): larger of net-long and net-short specific risk."""


class SSAEquityPosition(BaseModel):
    """Net position in one equity issue or CIU (Articles 341-343, 348)."""

    position_id: str
    issuer: str
    market: str = "EU"
    is_long: bool = True
    amount: float = Field(ge=0.0)
    is_ciu: bool = False
    ciu_includes_fx: bool = False
    """Article 348(1) second sentence: 40 % covering position and FX risk."""


class SSAFXPosition(BaseModel):
    """Net open position in a currency or gold, in the reporting currency (Article 352)."""

    currency: str
    net_position: float = Field(description="Signed: long > 0, short < 0")
    is_gold: bool = False


class SSACommodityPosition(BaseModel):
    """Commodity position valued at spot in the reporting currency (Articles 357-359)."""

    commodity: str
    is_long: bool = True
    amount: float = Field(ge=0.0, description="Quantity x spot price")
    maturity_years: float = Field(default=0.0, ge=0.0)
    commodity_type: str = Field(
        default="OTHER",
        description="PRECIOUS_METALS / BASE_METALS / AGRICULTURAL / OTHER (Art 361)",
    )


class SSAInputs(BaseModel):
    """Simplified-standardised-approach portfolio."""

    debt: list[SSADebtPosition] = Field(default_factory=list)
    equity: list[SSAEquityPosition] = Field(default_factory=list)
    fx: list[SSAFXPosition] = Field(default_factory=list)
    commodity: list[SSACommodityPosition] = Field(default_factory=list)
    total_own_funds: float = Field(default=0.0, ge=0.0, description="For Article 351 de minimis")
    reporting_currency: str = "EUR"
    general_risk_method: str = Field(
        default="MATURITY", description="MATURITY (339) / DURATION (340)"
    )
    commodity_method: str = Field(
        default="MATURITY_LADDER",
        description="MATURITY_LADDER (359) / SIMPLIFIED (360) / EXTENDED (361)",
    )


class SSAResult(BaseModel):
    """SSA own funds requirements by component (before and after Article 325(2) multipliers)."""

    debt_specific: float = 0.0
    debt_general: float = 0.0
    equity_specific: float = 0.0
    equity_general: float = 0.0
    ciu: float = 0.0
    fx: float = 0.0
    commodity: float = 0.0
    securitisation: float = 0.0
    total: float = 0.0
    rwa: float = 0.0
    citations: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


# =========================================================================
#  Eligibility -- Article 325a
# =========================================================================


def ssa_eligible(market_risk_business: float, total_assets: float,
                 eur_per_reporting_unit: float = 1.0) -> bool:
    """Article 325a(1): business subject to market risk <= 10 % of total assets and
    <= EUR 500 million (``eur_per_reporting_unit`` converts the reporting currency to EUR)."""
    in_eur = market_risk_business * eur_per_reporting_unit
    return (
        market_risk_business <= p.SSA_THRESHOLD_SHARE_OF_TOTAL_ASSETS * total_assets
        and in_eur <= p.SSA_THRESHOLD_EUR_M
    )


# =========================================================================
#  Debt -- Articles 336, 337, 338, 339, 340
# =========================================================================


def specific_risk_rate(pos: SSADebtPosition) -> float:
    """Article 336(1) Table 1 and 336(3)."""
    cat = pos.category
    if cat == SSASpecificCategory.ZERO_RW:
        return p.SSA_SPECIFIC_RISK_ZERO
    if cat == SSASpecificCategory.RW_100:
        return p.SSA_SPECIFIC_RISK_100
    if cat == SSASpecificCategory.RW_150:
        return p.SSA_SPECIFIC_RISK_150
    rate = p.SSA_SPECIFIC_RISK_QUALIFYING_LONG
    for upper, r in p.SSA_SPECIFIC_RISK_QUALIFYING:
        if pos.residual_maturity_years <= upper:
            rate = r
            break
    if cat == SSASpecificCategory.COVERED_BOND_10PCT:
        return rate * p.SSA_COVERED_BOND_10PCT_FACTOR
    return rate


def maturity_band(maturity: float, coupon: float) -> int:
    """Row index of Article 339(4) Table 2 for a maturity and coupon (Article 339(2))."""
    high = coupon >= p.SSA_COUPON_THRESHOLD
    for i, (_zone, up_hi, up_lo, _w, _dr) in enumerate(p.SSA_MATURITY_BANDS):
        if maturity <= (up_hi if high else up_lo):
            return i
    return len(p.SSA_MATURITY_BANDS) - 1


def _inter_zone(residual: dict[int, float]) -> tuple[float, float, float, float]:
    """Article 339(5)-(8): matched 1-2, 2-3, 1-3 and the residual unmatched position."""
    r = dict(residual)

    def match(a: int, b: int) -> float:
        if r[a] * r[b] >= 0:
            return 0.0
        m = min(abs(r[a]), abs(r[b]))
        r[a] += m if r[a] < 0 else -m
        r[b] += m if r[b] < 0 else -m
        return m

    m12 = match(1, 2)
    m23 = match(2, 3)
    m13 = match(1, 3)
    return m12, m23, m13, abs(r[1]) + abs(r[2]) + abs(r[3])


def general_risk_maturity(positions: list[SSADebtPosition]) -> float:
    """Maturity-based general risk for one currency (Article 339(2)-(9))."""
    long_w: dict[int, float] = defaultdict(float)
    short_w: dict[int, float] = defaultdict(float)
    for pos in positions:
        i = maturity_band(pos.residual_maturity_years, pos.coupon)
        w = pos.amount * p.SSA_MATURITY_BANDS[i][3]
        (long_w if pos.is_long else short_w)[i] += w
    matched_bands = 0.0
    zone_long: dict[int, float] = defaultdict(float)
    zone_short: dict[int, float] = defaultdict(float)
    for i in set(long_w) | set(short_w):
        lo, sh = long_w[i], short_w[i]
        matched_bands += min(lo, sh)
        zone = p.SSA_MATURITY_BANDS[i][0]
        if lo > sh:
            zone_long[zone] += lo - sh
        else:
            zone_short[zone] += sh - lo
    req = p.SSA_GR_MATCHED_BAND * matched_bands
    residual: dict[int, float] = {}
    for z in (1, 2, 3):
        req += p.SSA_GR_MATCHED_ZONE[z] * min(zone_long[z], zone_short[z])
        residual[z] = zone_long[z] - zone_short[z]
    m12, m23, m13, res = _inter_zone(residual)
    req += p.SSA_GR_MATCHED_ADJACENT_ZONES * (m12 + m23)
    req += p.SSA_GR_MATCHED_ZONES_1_3 * m13
    req += p.SSA_GR_RESIDUAL * res
    return req


def general_risk_duration(positions: list[SSADebtPosition]) -> float:
    """Duration-based general risk for one currency (Article 340(2)-(7))."""
    zone_long: dict[int, float] = defaultdict(float)
    zone_short: dict[int, float] = defaultdict(float)
    for pos in positions:
        md = pos.modified_duration if pos.modified_duration is not None else (
            pos.residual_maturity_years)
        for zone, upper, dr in p.SSA_DURATION_ZONES:
            if md <= upper:
                w = pos.amount * md * dr
                (zone_long if pos.is_long else zone_short)[zone] += w
                break
    req = 0.0
    residual: dict[int, float] = {}
    for z in (1, 2, 3):
        req += p.SSA_DURATION_MATCHED_ZONE * min(zone_long[z], zone_short[z])
        residual[z] = zone_long[z] - zone_short[z]
    m12, m23, m13, res = _inter_zone(residual)
    req += p.SSA_GR_MATCHED_ADJACENT_ZONES * (m12 + m23)
    req += p.SSA_GR_MATCHED_ZONES_1_3 * m13
    req += p.SSA_GR_RESIDUAL * res
    return req


def securitisation_specific(positions: list[SSADebtPosition]) -> float:
    """Articles 337 (8 % x banking-book RW, longs and shorts summed) and 338 (CRR3: the larger of
    the net-long and net-short requirement for the correlation trading portfolio)."""
    non_ctp = 0.0
    ctp_long = 0.0
    ctp_short = 0.0
    for pos in positions:
        bb = pos.banking_book_risk_weight
        rw = bb if bb is not None else p.SEC_RW_FALLBACK
        charge = pos.amount * p.SSA_SECURITISATION_RW_FACTOR * rw
        if pos.in_correlation_trading_portfolio:
            if pos.is_long:
                ctp_long += charge
            else:
                ctp_short += charge
        else:
            non_ctp += charge
    return non_ctp + max(ctp_long, ctp_short)


# =========================================================================
#  Equity -- Articles 341-343, 348
# =========================================================================


def equity_requirements(positions: list[SSAEquityPosition]) -> tuple[float, float, float]:
    """(specific, general, CIU): Article 342 (8 % gross), 343 (8 % net per market), 348."""
    net_issue: dict[tuple[str, str], float] = defaultdict(float)
    ciu = 0.0
    for pos in positions:
        if pos.is_ciu:
            rate = p.SSA_CIU_POSITION_AND_FX if pos.ciu_includes_fx else p.SSA_CIU_POSITION_RISK
            ciu += pos.amount * rate
            continue
        net_issue[(pos.market, pos.issuer)] += pos.amount if pos.is_long else -pos.amount
    gross = sum(abs(v) for v in net_issue.values())  # Article 341(1)
    per_market: dict[str, float] = defaultdict(float)
    for (market, _issuer), v in net_issue.items():
        per_market[market] += v
    net = sum(abs(v) for v in per_market.values())  # Article 341(2)
    return p.SSA_EQUITY_SPECIFIC * gross, p.SSA_EQUITY_GENERAL * net, ciu


# =========================================================================
#  FX -- Articles 351-352 (CRR3 point (193))
# =========================================================================


def fx_requirement(positions: list[SSAFXPosition], reporting_currency: str,
                   total_own_funds: float) -> float:
    """Article 352(4): overall net FX position = higher of total net long and total net short;
    Article 351: if net FX + net gold > 2 % of total own funds, OFR = (net FX + net gold) x 8 %."""
    longs = shorts = gold = 0.0
    for pos in positions:
        if pos.is_gold:
            gold += pos.net_position
            continue
        if pos.currency.upper() == reporting_currency.upper():
            continue
        if pos.net_position > 0:
            longs += pos.net_position
        else:
            shorts += -pos.net_position
    overall = max(longs, shorts) + abs(gold)
    if overall <= p.SSA_FX_DE_MINIMIS * total_own_funds:
        return 0.0
    return p.SSA_FX_RATE * overall


# =========================================================================
#  Commodities -- Articles 359-361
# =========================================================================


def _commodity_band(m: float) -> int:
    for i, upper in enumerate(p.SSA_COMMODITY_BANDS):
        if m <= upper:
            return i
    return len(p.SSA_COMMODITY_BANDS) - 1


def commodity_ladder(positions: list[SSACommodityPosition], spread: float, carry: float,
                     outright: float) -> float:
    """Maturity ladder for one commodity (Article 359(1)-(5); Article 361 rates if extended).

    (a) matched long + short in each band x spread; (b) inter-band matched positions x carry for
    each band they are carried forward; (c) residual unmatched x outright. Positions carried
    forward are matched against the nearest earlier band first.
    """
    lo: dict[int, float] = defaultdict(float)
    sh: dict[int, float] = defaultdict(float)
    for pos in positions:
        (lo if pos.is_long else sh)[_commodity_band(pos.maturity_years)] += pos.amount
    req = 0.0
    open_pos: list[list[float]] = []  # [signed amount, band index]
    for i in range(len(p.SSA_COMMODITY_BANDS)):
        matched = min(lo[i], sh[i])
        req += 2.0 * matched * spread
        u = lo[i] - sh[i]
        for item in reversed(open_pos):
            if u == 0.0:
                break
            if item[0] * u >= 0:
                continue
            m = min(abs(item[0]), abs(u))
            req += m * carry * (i - int(item[1]))
            item[0] += m if item[0] < 0 else -m
            u += m if u < 0 else -m
        open_pos = [it for it in open_pos if it[0] != 0.0]
        if u != 0.0:
            open_pos.append([u, float(i)])
    req += outright * sum(abs(it[0]) for it in open_pos)
    return req


def commodity_requirement(positions: list[SSACommodityPosition], method: str) -> float:
    """Sum over commodities (Articles 359(6), 360(2))."""
    by_commodity: dict[str, list[SSACommodityPosition]] = defaultdict(list)
    for pos in positions:
        by_commodity[pos.commodity].append(pos)
    total = 0.0
    for group in by_commodity.values():
        if method == "SIMPLIFIED":
            net = sum(x.amount if x.is_long else -x.amount for x in group)
            gross = sum(x.amount for x in group)
            total += p.SSA_COMMODITY_SIMPLE_NET * abs(net) + p.SSA_COMMODITY_SIMPLE_GROSS * gross
        elif method == "EXTENDED":
            sp, ca, out = p.SSA_COMMODITY_EXTENDED.get(
                group[0].commodity_type, p.SSA_COMMODITY_EXTENDED["OTHER"])
            total += commodity_ladder(group, sp, ca, out)
        else:
            total += commodity_ladder(group, p.SSA_COMMODITY_SPREAD, p.SSA_COMMODITY_CARRY,
                                      p.SSA_COMMODITY_OUTRIGHT)
    return total


# =========================================================================
#  Total -- Article 325(2)
# =========================================================================


def ssa_capital(inputs: SSAInputs) -> SSAResult:
    """Own funds requirement under the simplified standardised approach (Article 325(2))."""
    res = SSAResult()
    plain = [d for d in inputs.debt if not d.is_securitisation]
    sec = [d for d in inputs.debt if d.is_securitisation]
    res.debt_specific = sum(d.amount * specific_risk_rate(d) for d in plain)
    by_ccy: dict[str, list[SSADebtPosition]] = defaultdict(list)
    for d in inputs.debt:
        # Article 326: securitisation positions are treated as debt instruments; their general
        # risk is kept in the ladder.
        # TODO: VERIFY -- Article 325(2)(a)(i) excludes securitisation instruments from the 1,3
        # multiplier and 325(2)(d) covers only Article 337 (specific risk); the general risk of
        # securitisation positions is conservatively kept in the 1,3-multiplied debt ladder.
        by_ccy[d.currency.upper()].append(d)
    gr = general_risk_duration if inputs.general_risk_method == "DURATION" else (
        general_risk_maturity)
    res.debt_general = sum(gr(group) for group in by_ccy.values())  # Article 334
    res.securitisation = securitisation_specific(sec)
    res.equity_specific, res.equity_general, res.ciu = equity_requirements(inputs.equity)
    res.fx = fx_requirement(inputs.fx, inputs.reporting_currency, inputs.total_own_funds)
    res.commodity = commodity_requirement(inputs.commodity, inputs.commodity_method)
    res.total = (
        p.SSA_MULTIPLIER_DEBT * (res.debt_specific + res.debt_general)
        + p.SSA_MULTIPLIER_EQUITY * (res.equity_specific + res.equity_general)
        + p.SSA_MULTIPLIER_CIU * res.ciu
        + p.SSA_MULTIPLIER_FX * res.fx
        + p.SSA_MULTIPLIER_COMMODITY * res.commodity
        + p.SSA_MULTIPLIER_SECURITISATION * res.securitisation
    )
    res.rwa = p.RWA_MULTIPLIER * res.total
    res.citations = {
        "multipliers": "CRR Art 325(2) as replaced by CRR3 Art 1 point (156)(a)",
        "debt_specific": "CRR Art 336 Table 1",
        "debt_general": "CRR Art 339 (maturity) / Art 340 (duration)",
        "securitisation": "CRR Art 337 (CRR3 point (190)), Art 338 (CRR3 point (191))",
        "equity": "CRR Arts 341-343",
        "ciu": "CRR Art 348(1) (CRR3 point (192))",
        "fx": "CRR Art 351 (CRR3 point (193)), Art 352",
        "commodity": "CRR Arts 359-361",
        "rwa": "CRR Art 92(6)(b) (CRR3 point (28))",
    }
    if res.ciu:
        res.notes.append("CIU multiplier 3,5 is a conservative placeholder (TODO: VERIFY)")
    return res
