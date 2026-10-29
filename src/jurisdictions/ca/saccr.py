"""OSFI CAR 2026 Chapter 7 s.7.1.7 -- standardized approach for counterparty credit risk.

EAD = alpha x (RC + PFE) with alpha = 1.4 for every netting set: CAR prints no alpha exemption
for commercial end-users, non-financial or pension-fund counterparties (contrast the US
1.0 commercial end-user alpha). PFE = multiplier x AddOn_aggregate with
multiplier = min{1; 0.05 + 0.95 x exp((V - C) / (2 x 0.95 x AddOn))}. Maturity factors and the
Table 2 supervisory parameters follow CRE52 unchanged.

References:
    - OSFI CAR 2026 Ch.7 s.7.1.7-7.1.7.13, Table 2
    - Basel Framework CRE52
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction, SACCRNettingSetInput, SACCRResult
from src.jurisdictions.ca import params as p


def pfe_multiplier(v_minus_c: float, aggregate_addon: float) -> float:
    """multiplier = min{1; F + (1 - F) exp((V - C) / (2 (1 - F) AddOn))}, F = 5%.

    CAR Ch.7 s.7.1.7.3 [CRE 52.23]. With no add-on the multiplier is 1.
    """
    if aggregate_addon <= 0:
        return 1.0
    f = p.SACCR_MULTIPLIER_FLOOR
    return min(1.0, f + (1.0 - f) * math.exp(v_minus_c / (2.0 * (1.0 - f) * aggregate_addon)))


def maturity_factor_unmargined(maturity_years: float) -> float:
    """MF = sqrt(min(M, 1 year) / 1 year), M floored at 10 business days.

    CAR Ch.7 s.7.1.7.12 [CRE 52.48-52.49].
    """
    floor = p.SACCR_MATURITY_FLOOR_BD / p.SACCR_BUSINESS_DAYS_PER_YEAR
    m = max(maturity_years, floor)
    return math.sqrt(min(m, 1.0))


def mpor_floor_business_days(remargin_period_bd: int = 1, n_trades: int = 0,
                             illiquid_or_hard_to_replace: bool = False) -> int:
    """Supervisory MPOR floor (CAR Ch.7 s.7.1.7.12 [CRE 52.50-52.51]).

    10 business days for daily-margined non-cleared netting sets; 9 + N for remargining every N
    days; 20 business days for netting sets above 5,000 trades or with illiquid collateral /
    hard-to-replace OTC derivatives.
    """
    floor = (p.SACCR_MPOR_FLOOR_DAILY_BD if remargin_period_bd <= 1
             else p.SACCR_MPOR_FLOOR_DAILY_BD - 1 + remargin_period_bd)
    if n_trades > p.SACCR_MPOR_LARGE_NETTING_SET_TRADES or illiquid_or_hard_to_replace:
        floor = max(floor, p.SACCR_MPOR_FLOOR_LARGE_NETTING_SET_BD)
    return floor


def maturity_factor_margined(mpor_business_days: float) -> float:
    """MF = 1.5 x sqrt(MPOR / 1 year) (CAR Ch.7 s.7.1.7.12 [CRE 52.52-52.53])."""
    return p.SACCR_MARGINED_MF_SCALAR * math.sqrt(mpor_business_days
                                                  / p.SACCR_BUSINESS_DAYS_PER_YEAR)


def supervisory_parameters(key: str) -> tuple[float, float | None, float]:
    """(SF, correlation, option volatility) from CAR Ch.7 Table 2 [CRE 52.72]."""
    return p.SACCR_SUPERVISORY_PARAMETERS[key]


def saccr_ead(ns: SACCRNettingSetInput) -> SACCRResult:
    """EAD = 1.4 x (RC + PFE) for one netting set (CAR Ch.7 s.7.1.7 [CRE 52.1, 52.20-52.23]).

    ``replacement_cost`` and ``aggregate_addon`` are inputs; V - C = ``mtm - net_collateral``.
    ``counterparty_is_nonfinancial`` / ``counterparty_is_pension_scheme`` do not change alpha
    under CAR. The margined-vs-unmargined EAD cap (CRE 52.2) needs the unmargined EAD and is
    applied by the caller via :func:`cap_margined_ead`.
    """
    mult = pfe_multiplier(ns.mtm - ns.net_collateral, ns.aggregate_addon)
    pfe = mult * ns.aggregate_addon
    ead = p.SACCR_ALPHA * (ns.replacement_cost + pfe)
    return SACCRResult(
        jurisdiction=Jurisdiction.CA, netting_set_id=ns.netting_set_id, alpha=p.SACCR_ALPHA,
        multiplier=mult, pfe=pfe, ead=ead,
        citation=("CAR Ch.7 s.7.1.7 (alpha = 1.4, no end-user/pension exemption) and s.7.1.7.3 "
                  "(multiplier floor 5%) [Basel Framework, CRE 52.1, 52.23]"),
    )


def cap_margined_ead(ead_margined: float, ead_unmargined: float) -> float:
    """Margined EAD capped at the unmargined EAD (CAR Ch.7 s.7.1.7 [CRE 52.2])."""
    return min(ead_margined, ead_unmargined)
