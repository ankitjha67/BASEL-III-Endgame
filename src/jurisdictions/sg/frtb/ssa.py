"""SSA(MR) -- MAS Notice 637 Part VIII Division 4 (paras 8.4.1-8.4.85, Annex 8E).

Capital = (CR_IRR x 1.3) + (CR_EQ x 3.5) + (CR_FX x 1.2) + (CR_COMM x 1.9) (para 8.4.2);
market RWA = 12.5 x capital (para 8.1.1(a)(iii)). Use requires the Authority's approval for a
"small and simple" portfolio; para 8.1.18(a) screens market RWA against S$200 million and 2% of
total RWA (:func:`ssa_eligibility_screen`).

The building blocks equal MAR40 and are reused from the BCBS engine
(:mod:`src.jurisdictions.bcbs.frtb.ssa`): the maturity ladder (Table 8E-2 = MAR40 Table 4,
Table 8E-4 = MAR40 Table 5), FX (8%), commodities (simplified 15% / 3%, ladder 1.5% / 0.6% /
15%) and the simplified option approach. The tests assert that the SG transcriptions of these
tables equal the BCBS constants the reused functions read. MAS-specific pieces implemented here:

    - specific risk by Table 8E-1 credit quality grade, plus the Annex 8E para 1.4 0% charge
      (Singapore Government / MAS paper in SGD funded in SGD; domestic-currency CQG <= 3
      sovereigns; 0% PSEs) via :class:`SGSSADebtPosition.zero_specific_risk`;
    - equity specific risk 0% for qualifying equity indices (para 8.4.36(b)(i)), 8% otherwise,
      general 8% per country portfolio (para 8.4.37), +2% on qualifying indices (para 8.4.38);
    - the FX de minimis exemption test of para 8.4.42.

Not implemented (pass upstream results as ``other_*_capital``): duration method (para 8.4.24),
securitisation / CTP specific risk (para 8.4.18(a), (c)), credit-derivative offsets (para
8.4.15), delta-plus and scenario approaches (paras 8.4.69-8.4.85).
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.bcbs.frtb.ssa import (
    SSACommodityPosition,
    SSADebtPosition,
    SSAEquityPosition,
    SSAInputs,
    SSAIssuerCategory,
    SSAOptionPosition,
    commodity_ladder,
    commodity_simplified,
    fx_capital,
    ir_general_market_risk,
    option_capital,
)
from src.jurisdictions.sg.frtb import params as p

R = RatingBucket


class SGSSADebtPosition(SSADebtPosition):
    """Interest-rate position with the Annex 8E para 1.4 zero-specific-risk marker."""

    zero_specific_risk: bool = Field(
        default=False,
        description="Annex 8E para 1.4: SGD Singapore Government / MAS paper funded in SGD, "
                    "domestic-currency CQG<=3 sovereign funded in that currency, or 0% PSE")


class SGSSAInputs(SSAInputs):
    """Portfolio for SSA(MR); ``equities[i].is_diversified_index`` marks a qualifying equity
    index (Annex 8H)."""

    debt: list[SGSSADebtPosition] = Field(default_factory=list)  # type: ignore[assignment]


def _maturity_key(m: float) -> str:
    """Table 8E-1 residual-term bands."""
    if m <= p.SSA_MATURITY_SHORT_YEARS:
        return "LE_6M"
    return "6M_TO_24M" if m <= p.SSA_MATURITY_MEDIUM_YEARS else "GT_24M"


def specific_risk_rate(pos: SGSSADebtPosition) -> float:
    """Table 8E-1 and Annex 8E para 1.4 (para 8.4.18(d))."""
    if pos.general_market_risk_only or pos.zero_specific_risk:
        return p.SSA_ZERO_SPECIFIC_RISK
    if pos.category is SSAIssuerCategory.GOVERNMENT:
        if pos.rating is R.AAA_TO_AA_MINUS:
            return p.SSA_GOVT_SPECIFIC["CQG1"]
        if pos.rating in (R.A_PLUS_TO_A_MINUS, R.BBB_PLUS_TO_BBB_MINUS):
            return p.SSA_GOVT_SPECIFIC["CQG2_3_" + _maturity_key(pos.residual_maturity_years)]
        if pos.rating in (R.BB_PLUS_TO_BB_MINUS, R.B_PLUS_TO_B_MINUS):
            return p.SSA_GOVT_SPECIFIC["CQG4_5"]
        if pos.rating is R.BELOW_B_MINUS:
            return p.SSA_GOVT_SPECIFIC["CQG6"]
        return p.SSA_GOVT_SPECIFIC["UNRATED"]
    if pos.category is SSAIssuerCategory.QUALIFYING:
        return p.SSA_QUALIFYING_SPECIFIC[_maturity_key(pos.residual_maturity_years)]
    if pos.rating is R.BB_PLUS_TO_BB_MINUS:
        return p.SSA_OTHER_SPECIFIC["CQG4"]
    if pos.rating in (R.B_PLUS_TO_B_MINUS, R.BELOW_B_MINUS):
        return p.SSA_OTHER_SPECIFIC["CQG5_6"]
    return p.SSA_OTHER_SPECIFIC["UNRATED"]


def ir_specific_risk(debt: list[SGSSADebtPosition]) -> float:
    """Para 8.4.18(d): charge on the absolute net position per identical issue (para 8.4.11)."""
    by_issue: dict[str, list[SGSSADebtPosition]] = defaultdict(list)
    for d in debt:
        by_issue[d.issue_id].append(d)
    return sum(abs(sum(i.amount for i in items)) * specific_risk_rate(items[0])
               for items in by_issue.values())


def equity_capital(eqs: list[SSAEquityPosition]) -> float:
    """Paras 8.4.36-8.4.38: specific (0% qualifying index / 8% other) on net positions per
    issue, 8% general on the net position per country portfolio, +2% on qualifying indices."""
    by_issue: dict[tuple[str, str], float] = defaultdict(float)
    index_issue: set[tuple[str, str]] = set()
    for e in eqs:
        by_issue[(e.market, e.issue_id)] += e.amount
        if e.is_diversified_index:
            index_issue.add((e.market, e.issue_id))
    specific = sum(abs(v) * (p.SSA_EQUITY_QUALIFYING_INDEX_SPECIFIC if k in index_issue
                             else p.SSA_EQUITY_SPECIFIC) for k, v in by_issue.items())
    by_market: dict[str, float] = defaultdict(float)
    for (mkt, _), v in by_issue.items():
        by_market[mkt] += v
    general = p.SSA_EQUITY_GENERAL * sum(abs(v) for v in by_market.values())
    addon = p.SSA_EQUITY_INDEX_ADDON * sum(abs(by_issue[k]) for k in index_issue)
    return specific + general + addon


def fx_exemption_eligible(foreign_currency_business: float, overall_net_open_position: float,
                          eligible_total_capital: float) -> bool:
    """Para 8.4.42 (with prior approval): business <= 100% and NOP <= 2% of Eligible Total
    Capital."""
    return (foreign_currency_business <= p.SSA_FX_EXEMPT_BUSINESS_SHARE * eligible_total_capital
            and overall_net_open_position <= p.SSA_FX_EXEMPT_NOP_SHARE * eligible_total_capital)


def ssa_eligibility_screen(market_rwa_sgd_mn: float, total_rwa_sgd_mn: float) -> bool:
    """Para 8.1.18(a): True when SSA(MR) market RWA exceeds neither S$200m nor 2% of total RWA.

    The Authority also weighs complexity, G-SIB status, IMA use and CTP holdings
    (para 8.1.18(b)-(e)); this screen is necessary, not sufficient.
    """
    return (market_rwa_sgd_mn <= p.SSA_ELIGIBILITY_RWA_SGD_MN
            and market_rwa_sgd_mn <= p.SSA_ELIGIBILITY_RWA_SHARE * total_rwa_sgd_mn)


def ssa_capital(inputs: SGSSAInputs) -> dict[str, float]:
    """Para 8.4.2 scaled capital by risk class, total, and RWA (para 8.1.1(a)(iii))."""
    opt: dict[str, float] = defaultdict(float)
    for o in inputs.options:
        opt[o.risk_class.upper()] += option_capital(o)
    cr_irr = (ir_specific_risk(inputs.debt) + ir_general_market_risk(list(inputs.debt))
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
    "SGSSADebtPosition",
    "SGSSAInputs",
    "SSACommodityPosition",
    "SSAEquityPosition",
    "SSAIssuerCategory",
    "SSAOptionPosition",
    "equity_capital",
    "fx_exemption_eligible",
    "ir_specific_risk",
    "specific_risk_rate",
    "ssa_capital",
    "ssa_eligibility_screen",
]
