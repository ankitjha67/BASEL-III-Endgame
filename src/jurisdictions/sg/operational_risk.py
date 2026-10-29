"""Operational risk under MAS Notice 637 Part IX -- SA(OR).

K_ORC = BIC x ILM (para 9.1.2) with:

- BI = ILDC + SC + FC (para 9.1.3, Annex 9A), three-year averages;
- BIC = 12% x BI + 3% x (BI - S$1.5bn)+ + 3% x (BI - S$45bn)+ (para 9.1.2(a)),
  i.e. marginal coefficients 12% / 15% / 18%;
- ILM = ln(e - 1 + (LC/BIC)^0.8), LC = 15 x average annual net losses over
  10 years (para 9.1.2(b)). MAS does NOT exercise the BCBS discretion to set
  ILM = 1 for all banks: ILM is computed for banks with BI > S$1.5bn
  (para 9.1.8(b)); it is 1 for BI <= S$1.5bn unless MAS approves loss-data
  use (9.1.8(a)), where loss-data criteria are failed (9.1.10), or where fewer
  than 5 years of qualifying loss data exist (9.1.15).
- Operational RWA = 12.5 x K_ORC (para 9.1.1).

Inputs are expected in SGD millions (thresholds are stated in S$).

References:
    - MAS Notice 637 paras 9.1.1-9.1.21 (pp. 9-1 to 9-7), Annex 9A (pp. 9-14 to 9-17)
    - Basel Framework OPE25.1-25.11 (comparison)
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction, OpRiskInputs, OpRiskResult
from src.jurisdictions.sg import params as p


def _avg(values: list[float]) -> float:
    """Three-year average (para 9.1.3(i))."""
    return sum(values) / len(values)


def business_indicator_components(inputs: OpRiskInputs) -> dict[str, float]:
    """ILDC, SC and FC per MAS Notice 637 para 9.1.3 (p. 9-2).

    ILDC = min(avg|II - IE|, 2.25% x avg IEA) + avg dividend income;
    SC = max(avg fee income, avg fee expense) + max(avg other op. income, avg other op. expense);
    FC = avg|net P&L trading book| + avg|net P&L banking book|. Absolute values of net items
    are taken year by year before averaging (para 9.1.3(iii)).
    """
    nii = _avg(
        [abs(i - e) for i, e in zip(inputs.interest_income, inputs.interest_expense, strict=True)]
    )
    iea = _avg(inputs.interest_earning_assets)
    ildc = min(nii, p.ILDC_IEA_CAP * iea) + _avg(inputs.dividend_income)
    sc = max(_avg(inputs.fee_income), _avg(inputs.fee_expense)) + max(
        _avg(inputs.other_operating_income), _avg(inputs.other_operating_expense)
    )
    fc = _avg([abs(x) for x in inputs.net_pnl_trading_book]) + _avg(
        [abs(x) for x in inputs.net_pnl_banking_book]
    )
    return {"ILDC": ildc, "SC": sc, "FC": fc, "BI": ildc + sc + fc}


def business_indicator_component(bi: float) -> float:
    """BIC per MAS Notice 637 para 9.1.2(a) (p. 9-1); thresholds S$1.5bn and S$45bn.

    Worked example (footnote 901): BI = S$50bn -> BIC = S$7.605bn.
    """
    return (
        p.BIC_BASE_COEFFICIENT * bi
        + p.BIC_TIER2_INCREMENT * max(0.0, bi - p.BIC_TIER2_THRESHOLD_SGD_M)
        + p.BIC_TIER3_INCREMENT * max(0.0, bi - p.BIC_TIER3_THRESHOLD_SGD_M)
    )


def internal_loss_multiplier(lc: float, bic: float) -> float:
    """ILM = ln(exp(1) - 1 + (LC/BIC)^0.8) per MAS Notice 637 para 9.1.2(b) (p. 9-1)."""
    if bic <= 0.0:
        return 1.0
    return math.log(math.e - 1.0 + (lc / bic) ** p.ILM_EXPONENT)


def loss_component(annual_losses: list[float]) -> float:
    """LC = 15 x average annual net losses over the most recent 10 years (para 9.1.2(b)(i)).

    Where 5-9 years of qualifying data exist (para 9.1.14) all available years are used.
    """
    window = annual_losses[-p.LOSS_YEARS_STANDARD :]
    return p.LC_MULTIPLE * (sum(window) / len(window)) if window else 0.0


def operational_risk(
    inputs: OpRiskInputs,
    *,
    loss_data_criteria_met: bool = True,
    small_bank_ilm_approved: bool = False,
) -> OpRiskResult:
    """Operational risk capital and RWA under MAS Notice 637 SA(OR).

    Reference: MAS Notice 637 paras 9.1.1, 9.1.2, 9.1.3, 9.1.8, 9.1.10, 9.1.14, 9.1.15
    (pp. 9-1 to 9-7).

    Args:
        inputs: three-year BI inputs and up to 10 years of net annual losses (SGD millions).
        loss_data_criteria_met: the bank meets paras 9.1.16-9.1.41; if False ILM = 1 (9.1.10).
        small_bank_ilm_approved: MAS approval for a BI <= S$1.5bn bank to use the ILM (9.1.8(a)).
    """
    comps = business_indicator_components(inputs)
    bi = comps["BI"]
    bic = business_indicator_component(bi)
    losses = inputs.annual_operational_losses
    lc: float | None = None
    ilm = 1.0
    reason = "ILM computed (para 9.1.8(b))"
    uses_losses = bi > p.ILM_ONE_BI_THRESHOLD_SGD_M or small_bank_ilm_approved
    if not uses_losses:
        reason = "ILM = 1: BI <= S$1.5bn (para 9.1.8(a))"
    elif not loss_data_criteria_met:
        reason = "ILM = 1: loss-data criteria not met (para 9.1.10)"
    elif len(losses) < p.LOSS_YEARS_MINIMUM:
        reason = "ILM = 1: fewer than 5 years of loss data (para 9.1.15)"
    else:
        lc = loss_component(losses)
        ilm = internal_loss_multiplier(lc, bic)
    capital = bic * ilm
    comps.update({"BIC": bic, "ILM": ilm})
    return OpRiskResult(
        jurisdiction=Jurisdiction.SG,
        business_indicator=bi,
        bic=bic,
        loss_component=lc,
        ilm=ilm,
        capital=capital,
        rwa=p.OPRISK_RWA_MULTIPLIER * capital,
        citation=f"MAS 637 paras 9.1.1-9.1.3; {reason}",
        components=comps,
    )
