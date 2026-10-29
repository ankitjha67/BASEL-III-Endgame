"""OSFI CAR 2026 Chapter 9 s.9.6 -- internal models approach (IMA) aggregation helpers.

These functions reproduce the closed-form aggregation steps of CAR 9.6.3-9.6.4; the ES / SES
model outputs themselves are inputs. The square-root signs lost in the flattened CAR text are
restored from the identical Basel formulas (MAR33.4 rendered from the Basel Framework PDF p.670;
MAR33.17 from p.678).

References:
    - CAR 9.6.3.1 Table 17 [MAR32.9]; 9.6.3.2 Table 18 [MAR32.42]
    - CAR 9.6.4.1 Table 19 [MAR33.4], [MAR33.6]; 9.6.4.2 [MAR33.15]; 9.6.4.3 [MAR33.17]
    - CAR 9.6.4.6 [MAR33.41-33.45]
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from src.jurisdictions.ca.frtb import params as p


def liquidity_adjusted_es(es_full: float, es_subsets: Sequence[float]) -> float:
    """ES = sqrt(ES_T(P)² + Σ_{j≥2} (ES_T(P, j)·sqrt((LH_j − LH_{j−1}) / T))²).

    CAR 9.6.4.1 Table 19 [MAR33.4]: T = 10 days, LH = 10/20/40/60/120. ``es_subsets`` holds
    ES_T(P, j) for j = 2..5 (at most four values).
    """
    ladder = p.IMA_LIQUIDITY_HORIZON_LADDER
    if len(es_subsets) > len(ladder) - 1:
        raise ValueError("at most four ES_T(P, j) values (j = 2..5), CAR Table 19")
    acc = es_full ** 2
    for j, es_j in enumerate(es_subsets, start=1):
        acc += (es_j * math.sqrt((ladder[j] - ladder[j - 1]) / p.IMA_BASE_HORIZON_DAYS)) ** 2
    return math.sqrt(acc)


def stressed_es(es_rs: float, es_fc: float, es_rc: float) -> float:
    """ES = ES_R,S × ES_F,C / ES_R,C with the ratio floored at 1 (CAR 9.6.4.1 [MAR33.6])."""
    ratio = es_fc / es_rc if es_rc > 0.0 else 1.0
    return es_rs * max(ratio, 1.0)


def imcc(imcc_unconstrained: float, imcc_constrained_by_class: Sequence[float]) -> float:
    """IMCC = ρ·IMCC(C) + (1 − ρ)·Σ IMCC(C_i), ρ = 0.5 (CAR 9.6.4.2 [MAR33.15])."""
    rho = p.IMA_IMCC_RHO
    return rho * imcc_unconstrained + (1.0 - rho) * sum(imcc_constrained_by_class)


def ses(
    ises_credit: Sequence[float], ises_equity: Sequence[float], ses_other: Sequence[float],
) -> float:
    """SES aggregation (CAR 9.6.4.3 [MAR33.17]), ρ = 0.6.

    SES = sqrt(Σ ISES_i²) + sqrt(Σ ISES_j²) + sqrt((ρ·Σ SES_k)² + (1 − ρ²)·Σ SES_k²).
    """
    rho = p.IMA_SES_RHO
    term_k = (rho * sum(ses_other)) ** 2 + (1.0 - rho ** 2) * sum(x * x for x in ses_other)
    return (
        math.sqrt(sum(x * x for x in ises_credit))
        + math.sqrt(sum(x * x for x in ises_equity))
        + math.sqrt(term_k)
    )


def backtesting_zone(exceptions: int) -> str:
    """GREEN (0-4) / AMBER (5-9) / RED (10+) (CAR 9.6.3.1 Table 17 [MAR32.9])."""
    if exceptions >= p.IMA_BACKTESTING_RED_START:
        return "RED"
    if exceptions >= p.IMA_BACKTESTING_AMBER_START:
        return "AMBER"
    return "GREEN"


def multiplication_factor(exceptions: int, qualitative_addon: float = 0.0) -> float:
    """m_c = Table 17 backtesting-dependent multiplier + qualitative add-on (CAR 9.6.4.6
    [MAR33.42]); exceptions are the maximum of the APL and HPL counts."""
    capped = min(max(exceptions, 0), p.IMA_BACKTESTING_RED_START)
    return p.IMA_BACKTESTING_MULTIPLIER[capped] + qualitative_addon


def pla_zone(spearman: float, ks: float) -> str:
    """PLA test zone (CAR 9.6.3.2 Table 18 [MAR32.42]).

    Green: Spearman > 0.80 and KS < 0.09; red: Spearman < 0.70 or KS > 0.12; amber otherwise.
    """
    if spearman < p.IMA_PLA_SPEARMAN_RED or ks > p.IMA_PLA_KS_RED:
        return "RED"
    if spearman > p.IMA_PLA_SPEARMAN_GREEN and ks < p.IMA_PLA_KS_GREEN:
        return "GREEN"
    return "AMBER"


def desk_fails_backtesting(exceptions_99: int, exceptions_975: int) -> bool:
    """More than 12 exceptions at 99% or 30 at 97.5% -> SA for the desk (CAR 9.6.3.1 [MAR32.19])."""
    return (
        exceptions_99 > p.IMA_DESK_MAX_EXCEPTIONS_99
        or exceptions_975 > p.IMA_DESK_MAX_EXCEPTIONS_975
    )


def capital_ca(
    imcc_prev: float, ses_prev: float, imcc_avg60: float, ses_avg60: float, m_c: float,
) -> float:
    """C_A = max{IMCC_t−1 + SES_t−1; m_c·IMCC_avg + SES_avg} (CAR 9.6.4.6 [MAR33.41])."""
    return max(imcc_prev + ses_prev, m_c * imcc_avg60 + ses_avg60)


def pla_surcharge(
    sa_amber: float, sa_green_amber: float, sa_ga: float, ima_ga: float,
) -> float:
    """k·max{0, SA_G,A − IMA_G,A}, k = 0.5·Σ SA_amber / Σ SA_G,A (CAR 9.6.4.6 [MAR33.45])."""
    if sa_green_amber <= 0.0:
        return 0.0
    k = p.IMA_PLA_SURCHARGE_K * sa_amber / sa_green_amber
    return k * max(0.0, sa_ga - ima_ga)


def aggregate_capital(
    ima_ga: float, surcharge: float, c_u: float, sa_all_desks: float, sa_ga: float,
) -> float:
    """ACR_total = min{IMA_G,A + surcharge + C_U; SA_all desks} + max{0; IMA_G,A − SA_G,A}.

    CAR 9.6.4.6 [MAR33.43]; IMA_G,A = C_A + DRC.
    """
    return min(ima_ga + surcharge + c_u, sa_all_desks) + max(0.0, ima_ga - sa_ga)
