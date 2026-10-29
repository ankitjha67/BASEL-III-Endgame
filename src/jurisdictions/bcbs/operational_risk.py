"""BCBS standardised approach for operational risk (OPE25).

ORC = BIC x ILM; RWA = 12.5 x ORC (OPE25.2).

    BI   = ILDC + SC + FC                                       (OPE25.4)
    ILDC = min(avg|II - IE|, 2.25% x avg IEA) + avg DI          (OPE25.5)
    SC   = max(avg OOI, avg OOE) + max(avg FI, avg FE)          (OPE25.5)
    FC   = avg|Net P&L TB| + avg|Net P&L BB|                    (OPE25.5)
    BIC  = sum of alpha_i over BI buckets 12% / 15% / 18%       (OPE25.7 Table 1)
    LC   = 15 x average annual net losses (10 years)            (OPE25.8)
    ILM  = ln(exp(1) - 1 + (LC / BIC)^0.8)                      (OPE25.8)

The OPE25.4/25.5/25.8 equations are images in the Basel Framework text; they
are transcribed from BCBS d424 (Operational risk, paras 6 and 9), which the
Framework text describes identically. Absolute values of net items are taken
year by year before averaging (OPE25.5 footnote 362).

BI bucket thresholds are stated in EUR (EUR 1bn / EUR 30bn); inputs are read
in the same unit (millions). National discretions (OPE25.11): ILM = 1 for all
banks; inclusion of loss data for bucket-1 banks.

References:
    - Basel Framework OPE25.1-25.18 (pp. 769-776)
    - BCBS d424, Operational risk paras 4-11
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction, OpRiskInputs, OpRiskResult
from src.jurisdictions.bcbs import params as p
from src.jurisdictions.bcbs.params import BCBSOptions


def _avg(values: list[float]) -> float:
    """Three-year average (OPE25.5: average over t, t-1 and t-2)."""
    return sum(values) / len(values)


def business_indicator_components(inputs: OpRiskInputs) -> dict[str, float]:
    """ILDC, SC and FC per OPE25.5 (footnote 362: absolute values year by year)."""
    net_interest = _avg([abs(i - e) for i, e in zip(inputs.interest_income,
                                                    inputs.interest_expense, strict=True)])
    ildc = (min(net_interest, p.OPE_ILDC_IEA_CAP * _avg(inputs.interest_earning_assets))
            + _avg(inputs.dividend_income))
    sc = (max(_avg(inputs.other_operating_income), _avg(inputs.other_operating_expense))
          + max(_avg(inputs.fee_income), _avg(inputs.fee_expense)))
    fc = (_avg([abs(x) for x in inputs.net_pnl_trading_book])
          + _avg([abs(x) for x in inputs.net_pnl_banking_book]))
    return {"ILDC": ildc, "SC": sc, "FC": fc}


def business_indicator(inputs: OpRiskInputs) -> float:
    """BI = ILDC + SC + FC (OPE25.4)."""
    return sum(business_indicator_components(inputs).values())


def bi_bucket(bi: float) -> int:
    """BI bucket 1-3 (OPE25.7 Table 1: <= 1bn, 1bn < BI <= 30bn, > 30bn; EUR)."""
    for idx, (upper, _alpha) in enumerate(p.OPE_BI_BUCKETS_EUR_M, start=1):
        if bi <= upper:
            return idx
    return len(p.OPE_BI_BUCKETS_EUR_M)


def business_indicator_component(bi: float) -> float:
    """BIC with marginal coefficients 12% / 15% / 18% (OPE25.7 Table 1, footnote 363)."""
    bic = 0.0
    lower = 0.0
    for upper, alpha in p.OPE_BI_BUCKETS_EUR_M:
        if bi <= lower:
            break
        bic += (min(bi, upper) - lower) * alpha
        lower = upper
    return bic


def loss_component(annual_losses: list[float]) -> float | None:
    """LC = 15 x average annual net losses over the latest 10 years (OPE25.8, OPE25.10).

    Uses at most the most recent 10 observations (oldest first in the input);
    returns None where fewer than five years are available (OPE25.10: capital
    is then based solely on the BIC).
    """
    window = annual_losses[-p.OPE_LOSS_YEARS:]
    if len(window) < p.OPE_MIN_LOSS_YEARS:
        return None
    return p.OPE_LC_MULTIPLE * (sum(window) / len(window))


def internal_loss_multiplier(lc: float, bic: float) -> float:
    """ILM = ln(exp(1) - 1 + (LC / BIC)^0.8) (OPE25.8; d424 OpRisk para 9)."""
    if bic <= 0:
        return 1.0
    return math.log(math.e - 1.0 + (lc / bic) ** p.OPE_ILM_EXPONENT)


def operational_risk(inputs: OpRiskInputs, opts: BCBSOptions) -> OpRiskResult:
    """Operational-risk capital and RWA under OPE25 (ORC = BIC x ILM; RWA = 12.5 x ORC)."""
    comps = business_indicator_components(inputs)
    bi = sum(comps.values())
    bic = business_indicator_component(bi)
    bucket = bi_bucket(bi)
    lc = loss_component(inputs.annual_operational_losses)
    citation = "OPE25.2 / OPE25.4-25.8"
    if opts.ilm_equal_one:
        ilm = 1.0
        citation += " / OPE25.11 (ILM = 1 national discretion)"
    elif bucket == 1 and not opts.include_loss_data_bucket1:
        ilm = 1.0
        citation += " / OPE25.11 (bucket 1: ILM = 1)"
    elif lc is None:
        ilm = 1.0
        citation += " / OPE25.10 (< 5 years of loss data: BIC only)"
    else:
        ilm = internal_loss_multiplier(lc, bic)
    orc = bic * ilm
    return OpRiskResult(
        jurisdiction=Jurisdiction.BCBS,
        business_indicator=bi,
        bic=bic,
        loss_component=lc,
        ilm=ilm,
        capital=orc,
        rwa=p.OPE_RWA_MULTIPLIER * orc,
        citation=citation,
        components={**comps, "bucket": float(bucket)},
    )
