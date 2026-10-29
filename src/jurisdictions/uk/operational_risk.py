"""UK PRA Basel 3.1 operational risk -- the Operational Risk Part standardised approach.

The PRA Rulebook Operational Risk Part (PS1/26 Appendix 1, Annex L, p. 426-438)
replaces the CRR operational-risk approaches (Annex T deletes the Operational
Risk (CRR) Part). The own funds requirement is BIC x ILM (rule 4.1), with the
Internal Loss Multiplier fixed at one (rule 5.9), so internal losses do not
affect Pillar 1 capital (loss data must still be collected under Chapter 7).

    BI   = ILDC + SC + FC                                         (rule 5.2-5.3)
    ILDC = min(avg|II - IE|, 2.25% x avg IEA) + avg DI
    SC   = max(avg OOI, avg OOE) + max(avg FI, avg FE)
    FC   = avg|Net P&L TB| + avg|Net P&L BB|
    BIC  = sum of marginal 12% / 15% / 18% over GBP 0.88bn / 26bn  (rule 5.7-5.8)
    ORC  = BIC x ILM, ILM = 1                                    (rules 4.1, 5.9)
    RWA  = 12.5 x ORC              (Required Level of Own Funds (CRR) Part Art 92(4)(b))

References:
    - PRA Rulebook Operational Risk Part, rules 4.1, 5.1-5.9, 7.1 and Annex 1 Tables A-D
    - Required Level of Own Funds (CRR) Part Article 92(3)(e), 92(4)(b)

Inputs are in millions of the reporting currency; the bucket thresholds are the
GBP amounts of rule 5.8 expressed in GBP millions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from src.jurisdictions.base import Jurisdiction, OpRiskInputs, OpRiskResult
from src.jurisdictions.uk import params as p

OR_PART: Final[str] = "PRA Rulebook Operational Risk Part"


def _avg(values: Sequence[float]) -> float:
    """Three-year average per rule 5.4(1) (bar over a term) (p. 429)."""
    return sum(values) / len(values)


def _avg_abs(values: Sequence[float]) -> float:
    """Average of absolute values computed year by year first, rule 5.4(2) (p. 429)."""
    return sum(abs(v) for v in values) / len(values)


def interest_leases_dividend_component(inputs: OpRiskInputs) -> float:
    """ILDC = Min[avg Abs(II - IE); 2.25% x avg IEA] + avg DI -- rule 5.3 table (p. 429)."""
    net_interest = [
        ii - ie for ii, ie in zip(inputs.interest_income, inputs.interest_expense, strict=True)
    ]
    capped = min(_avg_abs(net_interest), p.ILDC_IEA_CAP * _avg(inputs.interest_earning_assets))
    return capped + _avg(inputs.dividend_income)


def services_component(inputs: OpRiskInputs) -> float:
    """SC = Max[avg OOI; avg OOE] + Max[avg FI; avg FE] -- rule 5.3 table (p. 429)."""
    return max(_avg(inputs.other_operating_income), _avg(inputs.other_operating_expense)) + max(
        _avg(inputs.fee_income), _avg(inputs.fee_expense)
    )


def financial_component(inputs: OpRiskInputs) -> float:
    """FC = avg Abs(Net P&L trading book) + avg Abs(Net P&L banking book) -- rule 5.3 (p. 429)."""
    return _avg_abs(inputs.net_pnl_trading_book) + _avg_abs(inputs.net_pnl_banking_book)


def business_indicator(inputs: OpRiskInputs) -> tuple[float, dict[str, float]]:
    """Business Indicator = ILDC + SC + FC -- rule 5.2 (p. 428)."""
    comps = {
        "ILDC": interest_leases_dividend_component(inputs),
        "SC": services_component(inputs),
        "FC": financial_component(inputs),
    }
    return comps["ILDC"] + comps["SC"] + comps["FC"], comps


def business_indicator_component(bi: float) -> float:
    """BIC = BI x marginal coefficients of the rule 5.8 table (p. 430).

    Buckets: BI <= GBP 0.88bn at 12%; 0.88bn < BI <= 26bn at 15%; > 26bn at 18%.
    """
    bic = 0.0
    lower = 0.0
    for upper, coefficient in p.BIC_BUCKETS_GBP_M:
        if bi <= lower:
            break
        bic += (min(bi, upper) - lower) * coefficient
        lower = upper
    return bic


def operational_risk_capital(inputs: OpRiskInputs) -> OpRiskResult:
    """Own funds requirement and RWA for operational risk -- rules 4.1, 5.9; Art 92(4)(b).

    The loss component is not part of the UK calculation (ILM = 1 by rule 5.9),
    so ``loss_component`` is ``None``; the ten-year loss average above the GBP
    20,000 threshold (rule 7.1(2), (4)) is reported in ``components`` for
    information only.
    """
    bi, comps = business_indicator(inputs)
    bic = business_indicator_component(bi)
    capital = bic * p.ILM
    losses = [x for x in inputs.annual_operational_losses]
    comps = dict(comps)
    comps["BI"] = bi
    if losses:
        comps["avg_annual_loss_info_only"] = _avg(losses[-p.OPRISK_LOSS_OBSERVATION_YEARS :])
    return OpRiskResult(
        jurisdiction=Jurisdiction.UK,
        business_indicator=bi,
        bic=bic,
        loss_component=None,
        ilm=p.ILM,
        capital=capital,
        rwa=capital * p.OWN_FUNDS_TO_RWA_MULTIPLIER,
        citation=(
            f"{OR_PART} rules 4.1, 5.2-5.9 (ILM = 1, rule 5.9); "
            "Required Level of Own Funds (CRR) Part Art 92(3)(e), 92(4)(b)"
        ),
        components=comps,
    )
