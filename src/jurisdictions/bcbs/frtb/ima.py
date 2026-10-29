"""Internal models approach aggregation helpers (Basel Framework MAR32-MAR33).

Formula sources (images in the Framework, read from the rendered PDF pages):
    - Liquidity-adjusted ES (MAR33.4, p. 670): the scaling formula is an image not reproduced
      here (the cascade over LH_j is described in the text); see ``liquidity_adjusted_es``.
    - ES = ES_R,S x max(ES_F,C / ES_R,C, 1) (MAR33.6, text "ratio is floored at 1")
    - IMCC = rho x IMCC(C) + (1 - rho) x sum_i IMCC(C_i), rho = 0.5 (MAR33.15, p. 676)
    - SES = sqrt(sum ISES_i^2) + sqrt(sum ISES_j^2)
            + sqrt((rho sum SES_k)^2 + (1 - rho^2) sum SES_k^2), rho = 0.6 (MAR33.17, p. 678)
    - C_A = max(IMCC_{t-1} + SES_{t-1}; m_c x IMCC_avg + SES_avg) (MAR33.41, p. 685)
    - ACR_total = min(IMA_G,A + surcharge + C_U; SA_all desks) + max(0; IMA_G,A - SA_G,A)
      (MAR33.43, p. 685)
    - surcharge = k x max(0, SA_G,A - IMA_G,A), k = 0.5 x sum_amber SA_i / sum_{G,A} SA_i
      (MAR33.45, p. 686)
"""

from __future__ import annotations

import math

from src.jurisdictions.bcbs.frtb import params as p


def backtesting_multiplier(exceptions: int, qualitative_addon: float = 0.0) -> float:
    """m_c from MAR32.9 Table 1 (exceptions in 250 days) plus a qualitative add-on (MAR33.42)."""
    if exceptions < 0:
        raise ValueError("exceptions must be non-negative")
    return p.IMA_BACKTESTING_MULTIPLIER[min(exceptions, 10)] + qualitative_addon


def backtesting_zone(exceptions: int) -> str:
    """MAR32.9 Table 1: GREEN (0-4), AMBER (5-9), RED (10 or more)."""
    if exceptions <= 4:
        return "GREEN"
    return "AMBER" if exceptions <= 9 else "RED"


def pla_zone(spearman: float, ks: float) -> str:
    """MAR32.42 Table 2: green if rho > 0.80 and KS < 0.09; red if rho < 0.70 or KS > 0.12."""
    amber_rho, red_rho = p.IMA_PLA_SPEARMAN
    amber_ks, red_ks = p.IMA_PLA_KS
    if spearman > amber_rho and ks < amber_ks:
        return "GREEN"
    if spearman < red_rho or ks > red_ks:
        return "RED"
    return "AMBER"


def liquidity_adjusted_es(es_by_horizon: list[float]) -> float:
    """MAR33.4 cascade over liquidity horizons.

    ES = sqrt(ES_T(P)^2 + sum_{j>=2} (ES_T(P, j) x sqrt((LH_j - LH_{j-1}) / T))^2).

    ``es_by_horizon[0]`` is ES_T(P) (all risk factors); ``es_by_horizon[j-1]`` for j = 2..5 is
    ES_T(P, j) over risk factors with LH >= LH_j. The formula is an image in the Framework
    (p. 670); it is reconstructed from the definitions in MAR33.4(1)-(8) and Table 1.
    # TODO: VERIFY -- MAR33.4 equation image not legible in the extracted text or PDF render.
    """
    if not es_by_horizon:
        return 0.0
    t = p.IMA_BASE_HORIZON_DAYS
    total = es_by_horizon[0] ** 2
    for j in range(1, min(len(es_by_horizon), len(p.IMA_LH_BUCKETS))):
        scale = math.sqrt((p.IMA_LH_BUCKETS[j] - p.IMA_LH_BUCKETS[j - 1]) / t)
        total += (es_by_horizon[j] * scale) ** 2
    return math.sqrt(total)


def stressed_es(es_rs: float, es_fc: float, es_rc: float) -> float:
    """MAR33.6: ES = ES_R,S x max(ES_F,C / ES_R,C, 1)."""
    ratio = es_fc / es_rc if es_rc > 0 else 1.0
    return es_rs * max(ratio, 1.0)


def imcc(unconstrained: float, constrained_by_class: list[float]) -> float:
    """MAR33.15: rho x IMCC(C) + (1 - rho) x sum IMCC(C_i), rho = 0.5."""
    rho = p.IMA_IMCC_RHO
    return rho * unconstrained + (1.0 - rho) * sum(constrained_by_class)


def ses(ises_credit: list[float], ises_equity: list[float], ses_other: list[float]) -> float:
    """MAR33.17 aggregate NMRF capital, rho = 0.6."""
    rho = p.IMA_SES_RHO
    a = math.sqrt(sum(x * x for x in ises_credit))
    b = math.sqrt(sum(x * x for x in ises_equity))
    c = math.sqrt((rho * sum(ses_other)) ** 2 + (1.0 - rho * rho) * sum(x * x for x in ses_other))
    return a + b + c


def capital_eligible_desks(imcc_last: float, ses_last: float, imcc_avg: float, ses_avg: float,
                           multiplier: float = p.IMA_MULTIPLIER_BASE) -> float:
    """MAR33.41: C_A = max(IMCC_{t-1} + SES_{t-1}; m_c x IMCC_avg + SES_avg)."""
    return max(imcc_last + ses_last, multiplier * imcc_avg + ses_avg)


def pla_surcharge(sa_by_desk: dict[str, float], amber_desks: set[str], ima_ga: float) -> float:
    """MAR33.45: k x max(0, SA_G,A - IMA_G,A), k = 0.5 x sum_amber SA_i / sum_{G,A} SA_i."""
    sa_ga = sum(sa_by_desk.values())
    if sa_ga <= 0:
        return 0.0
    k = p.IMA_PLA_SURCHARGE_K * sum(v for d, v in sa_by_desk.items() if d in amber_desks) / sa_ga
    return k * max(0.0, sa_ga - ima_ga)


def aggregate_capital(ima_ga: float, surcharge: float, c_u: float, sa_all_desks: float,
                      sa_ga: float) -> float:
    """MAR33.43: min(IMA_G,A + surcharge + C_U; SA_all desks) + max(0; IMA_G,A - SA_G,A)."""
    return min(ima_ga + surcharge + c_u, sa_all_desks) + max(0.0, ima_ga - sa_ga)


__all__ = [
    "aggregate_capital",
    "backtesting_multiplier",
    "backtesting_zone",
    "capital_eligible_desks",
    "imcc",
    "liquidity_adjusted_es",
    "pla_surcharge",
    "pla_zone",
    "ses",
    "stressed_es",
]
