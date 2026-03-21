"""FX risk regulatory parameters per MAR21.21-21.22 Basel III Endgame.

All risk weights, correlations, and regulatory constants for the
FX risk class under FRTB Sensitivities-Based Method.

FX has NO bucket structure -- all currency pair sensitivities are
aggregated in a single correlation matrix with uniform rho = 0.60.
"""
from __future__ import annotations

import math

from src.core.enums import CorrelationScenario

# ---------------------------------------------------------------------------
# Delta risk weight (MAR21.21) -- decimal fraction
# 15% for all currency pairs
# ---------------------------------------------------------------------------
FX_DELTA_RW: float = 0.15

# ---------------------------------------------------------------------------
# Specified (well-traded) currency pairs -- MAR21.21
# These may receive a reduced risk weight in some jurisdictions.
# For the base implementation, all pairs use 15%.
# ---------------------------------------------------------------------------
FX_SPECIFIED_PAIRS: set[frozenset[str]] = {
    frozenset({"USD", "EUR"}),
    frozenset({"USD", "JPY"}),
    frozenset({"USD", "GBP"}),
    frozenset({"USD", "AUD"}),
    frozenset({"USD", "CAD"}),
    frozenset({"USD", "CHF"}),
    frozenset({"USD", "MXN"}),
    frozenset({"USD", "CNY"}),
    frozenset({"USD", "NZD"}),
    frozenset({"USD", "RUB"}),
    frozenset({"USD", "HKD"}),
    frozenset({"USD", "SGD"}),
    frozenset({"USD", "TRY"}),
    frozenset({"USD", "KRW"}),
    frozenset({"USD", "SEK"}),
    frozenset({"USD", "ZAR"}),
    frozenset({"USD", "INR"}),
    frozenset({"USD", "NOK"}),
    frozenset({"USD", "BRL"}),
    frozenset({"EUR", "GBP"}),
    frozenset({"EUR", "JPY"}),
    frozenset({"EUR", "CHF"}),
}

# ---------------------------------------------------------------------------
# Intra-bucket correlation (MAR21.22)
# FX has a single "bucket" -- all pairs correlated at rho = 0.60
# ---------------------------------------------------------------------------
FX_INTRA_CORR: float = 0.60

# ---------------------------------------------------------------------------
# Vega parameters (MAR21.44-47)
# FX liquidity horizon = 40 days
# RW_vega = min(sqrt(RWsigma * LH / T), 1.0) -> capped at 100%
# ---------------------------------------------------------------------------
FX_VEGA_RW: float = 1.0  # 100%
FX_VEGA_LIQUIDITY_HORIZON: int = 40  # Business days
FX_VEGA_ALPHA: float = 0.01  # Correlation decay for vega


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_fx_delta_rw(currency_pair: str | None = None) -> float:
    """Get delta risk weight for an FX sensitivity.

    All FX pairs use 15% risk weight. The currency_pair argument is
    accepted for interface consistency but does not affect the result.

    Args:
        currency_pair: Optional currency pair identifier (e.g. "EUR/USD").

    Returns:
        Risk weight as a decimal (0.15 for 15%).
    """
    return FX_DELTA_RW


def apply_correlation_scenario(
    rho: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply correlation scenario adjustment per MAR21.6.

    +---------+--------------------------------------+
    | Scenario| Adjusted correlation                 |
    +=========+======================================+
    | LOW     | max(2*rho - 1, 0.75*rho)             |
    +---------+--------------------------------------+
    | MEDIUM  | rho (no change)                      |
    +---------+--------------------------------------+
    | HIGH    | min(1.0, 1.25*rho)                   |
    +---------+--------------------------------------+

    Args:
        rho: Base correlation value.
        scenario: One of LOW / MEDIUM / HIGH.
        is_inter_bucket: Whether this is an inter-bucket correlation.

    Returns:
        Scenario-adjusted correlation.
    """
    if scenario == CorrelationScenario.MEDIUM:
        return rho
    elif scenario == CorrelationScenario.HIGH:
        return min(1.0, 1.25 * rho)
    else:  # LOW
        return max(2 * rho - 1, 0.75 * rho)


def build_fx_correlation_matrix(
    n: int,
    scenario: CorrelationScenario,
) -> "numpy.ndarray":
    """Build the correlation matrix for FX sensitivities.

    FX uses a single-bucket structure with uniform correlation rho = 0.60
    between all currency pairs, adjusted by the scenario multiplier.

    Args:
        n: Number of FX sensitivities.
        scenario: Correlation scenario (LOW / MEDIUM / HIGH).

    Returns:
        numpy ndarray of shape (n, n).
    """
    import numpy as np

    rho = apply_correlation_scenario(FX_INTRA_CORR, scenario)

    corr = np.full((n, n), rho, dtype=np.float64)
    np.fill_diagonal(corr, 1.0)
    return corr
