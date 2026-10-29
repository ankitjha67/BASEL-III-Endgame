"""OSFI CAR 2026 Chapter 3 -- operational risk.

Two methodologies (CAR Ch.3 s.3.2):

- **Standardized Approach (SA)** -- mandatory for D-SIBs and for Category I SMSBs with annual
  Adjusted Gross Income above $1.5 billion: ORC = BIC x ILM (s.3.4, [OPE 25.2]). OSFI does *not*
  exercise the Basel national discretion to set ILM = 1: the ILM is computed from 10 years of
  high-quality loss data, and is floored at 1 where an institution lacks 10 years of data or
  fails the loss-data standards (s.3.4.1-3.4.2, [OPE 25.10, 25.13]).
- **Simplified Standardized Approach (SSA)** -- other SMSBs: ORC = 15% x average annual
  Adjusted Gross Income over the previous 12 fiscal quarters (s.3.3; OSFI-specific).

RWA = 12.5 x ORC. BIC thresholds are $1.5B and $45B (CAD) with 12% / +3% / +3% increments.

References:
    - OSFI CAR 2026 Ch.3 s.3.2-3.4.7, Annex 3-1
    - Basel Framework OPE10, OPE25
"""

from __future__ import annotations

import math
from enum import StrEnum

from src.jurisdictions.base import Jurisdiction, OpRiskInputs, OpRiskResult
from src.jurisdictions.ca import params as p


class OpRiskApproach(StrEnum):
    """CAR Ch.3 s.3.2 methodologies."""

    SA = "SA"
    SSA = "SSA"


def _avg(values: list[float]) -> float:
    """Arithmetic mean of the three annual observations (CAR Ch.3 s.3.4.1 footnote 7)."""
    return sum(values) / len(values)


def business_indicator(inputs: OpRiskInputs) -> dict[str, float]:
    """BI = ILDC + SC + FC (CAR Ch.3 s.3.4.1, [OPE 25.4-25.5]).

    ILDC = Min[avg Abs(II - IE); 2.25% x avg IEA] + avg dividends, with the absolute value of the
    net item taken year by year before averaging (footnote 7); SC = Max[avg fee income; avg fee
    expense] + Max[avg other operating income; avg other operating expense];
    FC = avg Abs(net P&L trading book) + avg Abs(net P&L banking book).
    """
    pairs = zip(inputs.interest_income, inputs.interest_expense, strict=True)
    nii = _avg([abs(i - x) for i, x in pairs])
    iea = _avg(inputs.interest_earning_assets)
    ildc = min(nii, p.ILDC_IEA_CAP * iea) + _avg(inputs.dividend_income)
    sc = (max(_avg(inputs.fee_income), _avg(inputs.fee_expense))
          + max(_avg(inputs.other_operating_income), _avg(inputs.other_operating_expense)))
    fc = (_avg([abs(v) for v in inputs.net_pnl_trading_book])
          + _avg([abs(v) for v in inputs.net_pnl_banking_book]))
    return {"ILDC": ildc, "SC": sc, "FC": fc, "BI": ildc + sc + fc}


def business_indicator_component(bi: float) -> float:
    """BIC = 12% BI + 3% (BI - $1.5B)+ + 3% (BI - $45B)+ (CAR Ch.3 s.3.4.1, [OPE 25.7]).

    Amounts in $M (thresholds 1,500 and 45,000 CAD millions). Footnote 8: BI $50B -> $7.605B.
    """
    return (p.BIC_BASE_COEFFICIENT * bi
            + p.BIC_INCREMENT_1 * max(0.0, bi - p.BIC_THRESHOLD_1_CAD_M)
            + p.BIC_INCREMENT_2 * max(0.0, bi - p.BIC_THRESHOLD_2_CAD_M))


def loss_component(annual_losses: list[float]) -> float:
    """LC = 15 x average annual net operational losses (CAR Ch.3 s.3.4.1, [OPE 25.8])."""
    if not annual_losses:
        return 0.0
    return p.LOSS_COMPONENT_MULTIPLIER * _avg(annual_losses)


def internal_loss_multiplier(lc: float, bic: float) -> float:
    """ILM = ln(exp(1) - 1 + (LC/BIC)^0.8) (CAR Ch.3 s.3.4.1, [OPE 25.8-25.9])."""
    if bic <= 0:
        return 1.0
    return math.log(math.e - 1.0 + (lc / bic) ** p.ILM_EXPONENT)


def adjusted_gross_income(inputs: OpRiskInputs) -> list[float]:
    """Annual Adjusted Gross Income for the SSA (CAR Ch.3 s.3.3).

    AGI = min(|net interest income|, 2.25% x IEA) + dividends + |fee and commission income| +
    |other income| + |net P&L trading book| + |net P&L banking book|.
    """
    out = []
    for k in range(3):
        nii = abs(inputs.interest_income[k] - inputs.interest_expense[k])
        out.append(min(nii, p.SSA_NII_CAP_PCT_IEA * inputs.interest_earning_assets[k])
                   + inputs.dividend_income[k] + abs(inputs.fee_income[k])
                   + abs(inputs.other_operating_income[k]) + abs(inputs.net_pnl_trading_book[k])
                   + abs(inputs.net_pnl_banking_book[k]))
    return out


def operational_risk_capital(
    inputs: OpRiskInputs,
    approach: OpRiskApproach = OpRiskApproach.SA,
    loss_data_standards_met: bool = True,
) -> OpRiskResult:
    """Operational-risk capital and RWA under OSFI CAR Chapter 3.

    SA (s.3.4): ORC = BIC x ILM. The ILM uses the supplied loss history; with fewer than 10
    years of loss data, or where the loss-data standards are not met, ILM is floored at 1
    (s.3.4.1 [OPE 25.10], s.3.4.2 [OPE 25.13]); with no loss data ILM = 1.
    SSA (s.3.3): ORC = 15% x average annual AGI. RWA = 12.5 x ORC.
    """
    if approach == OpRiskApproach.SSA:
        agi = adjusted_gross_income(inputs)
        orc = p.SSA_AGI_COEFFICIENT * _avg(agi)
        return OpRiskResult(
            jurisdiction=Jurisdiction.CA, business_indicator=_avg(agi), bic=orc,
            loss_component=None, ilm=1.0, capital=orc, rwa=p.OPRISK_RWA_MULTIPLIER * orc,
            citation="CAR Ch.3 s.3.3 (Simplified Standardized Approach: 15% x average AGI)",
            components={"AGI_avg": _avg(agi), "AGI_y1": agi[0], "AGI_y2": agi[1], "AGI_y3": agi[2]},
        )
    comps = business_indicator(inputs)
    bic = business_indicator_component(comps["BI"])
    losses = inputs.annual_operational_losses
    if not losses:
        lc: float | None = None
        ilm = 1.0
    else:
        lc = loss_component(losses)
        ilm = internal_loss_multiplier(lc, bic)
        if len(losses) < p.LOSS_DATA_YEARS or not loss_data_standards_met:
            ilm = max(1.0, ilm)
    orc = bic * ilm
    return OpRiskResult(
        jurisdiction=Jurisdiction.CA, business_indicator=comps["BI"], bic=bic,
        loss_component=lc, ilm=ilm, capital=orc, rwa=p.OPRISK_RWA_MULTIPLIER * orc,
        citation=("CAR Ch.3 s.3.4 (ORC = BIC x ILM; BIC 12%/+3% > $1.5B/+3% > $45B; "
                  "ILM floored at 1 without 10 years of qualifying loss data) "
                  "[Basel Framework, OPE 25.2-25.13]"),
        components=comps,
    )
