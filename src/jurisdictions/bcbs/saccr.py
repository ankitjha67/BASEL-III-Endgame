"""BCBS standardised approach for counterparty credit risk (CRE52).

    EAD        = alpha x (RC + PFE),  alpha = 1.4                  (CRE52.1)
    PFE        = multiplier x AddOn_aggregate                      (CRE52.20)
    multiplier = min{1; Floor + (1 - Floor) x
                     exp[(V - C) / (2 x (1 - Floor) x AddOn_aggregate)]},  Floor = 5%  (CRE52.23)
    MF (unmargined) = sqrt(min(M, 1 year) / 1 year), M >= 10 business days  (CRE52.48)
    MF (margined)   = 3/2 x sqrt(MPOR / 1 year)                    (CRE52.52)

The Basel Framework applies alpha = 1.4 to every netting set: unlike the
EU (CRR Art. 274(2), non-financial / pension 1.0) and US (commercial end
user 1.0) implementations there is no alpha exemption, so the
``counterparty_is_nonfinancial`` and ``counterparty_is_pension_scheme``
inputs do not change the BCBS result.

The CRE52.1, CRE52.23, CRE52.48 and CRE52.52 equations are images in the
Framework text. EAD = 1.4 x (RC + PFE) is confirmed by the CRE99.125 worked
example; the "3/2 multiplier" of CRE52.52 is named in CRE52.2 FAQ1; the
multiplier equation is cross-checked against CRR Article 278(3).

References:
    - Basel Framework CRE52.1-52.76 (pp. 434-462), CRE99.125 (p. 545)
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction, SACCRNettingSetInput, SACCRResult
from src.jurisdictions.bcbs import params as p


def pfe_multiplier(v: float, c: float, addon_aggregate: float) -> float:
    """CRE52.23 multiplier with the 5% floor (1 where AddOn is zero)."""
    if addon_aggregate <= 0:
        return 1.0
    floor = p.SACCR_MULTIPLIER_FLOOR
    expo = (v - c) / (2.0 * (1.0 - floor) * addon_aggregate)
    if expo >= 0:
        return 1.0
    return min(1.0, floor + (1.0 - floor) * math.exp(expo))


def maturity_factor_unmargined(maturity_years: float) -> float:
    """CRE52.48-52.49: sqrt(min(M, 1) / 1), M floored at 10 business days (10/250 years)."""
    floor_years = p.SACCR_MIN_MATURITY_BUSINESS_DAYS / p.SACCR_BUSINESS_DAYS_PER_YEAR
    m = max(maturity_years, floor_years)
    return math.sqrt(min(m, 1.0))


def maturity_factor_margined(mpor_business_days: float) -> float:
    """CRE52.52-52.53: 3/2 x sqrt(MPOR / 250 business days)."""
    return p.SACCR_MARGINED_MF_SCALAR * math.sqrt(
        mpor_business_days / p.SACCR_BUSINESS_DAYS_PER_YEAR)


def mpor_floor(daily_margin: bool = True, remargin_days: int = 1,
               large_or_illiquid: bool = False, disputes: bool = False) -> int:
    """MPOR floor in business days (CRE52.50-52.51), non-centrally-cleared.

    10 days with daily margining, otherwise 9 + the remargining period;
    20 days for > 5,000 trades or illiquid collateral / hard-to-replace
    derivatives; doubled after more than two lengthy margin disputes.
    """
    base = p.SACCR_MPOR_FLOOR_DAILY_DAYS if daily_margin else (
        p.SACCR_MPOR_FLOOR_DAILY_DAYS - 1 + remargin_days)
    if large_or_illiquid:
        base = max(base, p.SACCR_MPOR_FLOOR_LARGE_DAYS)
    return base * 2 if disputes else base


def supervisory_factor(subclass: str, basis: bool = False, volatility: bool = False) -> float:
    """Supervisory factor from CRE52.72 Table 2, adjusted per CRE52.73.

    Basis-transaction hedging sets x 0.5; volatility-transaction hedging sets x 5.
    """
    sf = p.SACCR_SUPERVISORY_PARAMS[subclass][0]
    if basis:
        sf *= p.SACCR_BASIS_SF_SCALAR
    if volatility:
        sf *= p.SACCR_VOLATILITY_SF_SCALAR
    return sf


def saccr_ead(netting_set: SACCRNettingSetInput) -> SACCRResult:
    """EAD = 1.4 x (RC + multiplier x AddOn_aggregate) for one netting set (CRE52.1)."""
    mult = pfe_multiplier(netting_set.mtm, netting_set.net_collateral,
                          netting_set.aggregate_addon)
    pfe = mult * netting_set.aggregate_addon
    ead = p.SACCR_ALPHA * (netting_set.replacement_cost + pfe)
    return SACCRResult(
        jurisdiction=Jurisdiction.BCBS,
        netting_set_id=netting_set.netting_set_id,
        alpha=p.SACCR_ALPHA,
        multiplier=mult,
        pfe=pfe,
        ead=ead,
        citation="CRE52.1 / CRE52.20-52.23 (alpha 1.4, no exemptions)",
    )
