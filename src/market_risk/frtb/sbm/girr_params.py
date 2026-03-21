"""GIRR regulatory parameters per MAR21 Basel III Endgame.

All risk weights, correlations, and regulatory constants for the
General Interest Rate Risk class under FRTB Sensitivities-Based Method.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.core.enums import CorrelationScenario, GIRRTenor, CurrencyCategory

# ---------------------------------------------------------------------------
# Standard tenor vertices (years) -- MAR21.8
# ---------------------------------------------------------------------------
TENORS: list[float] = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 25.0, 30.0]

# ---------------------------------------------------------------------------
# Delta risk weights as decimal percentages (MAR21.9 Table 1)
# These are for LOW volatility currencies (USD, EUR, GBP, etc.)
# ---------------------------------------------------------------------------
DELTA_RISK_WEIGHTS: dict[float, float] = {
    0.25: 0.017,  # 1.7%
    0.5:  0.017,  # 1.7%
    1.0:  0.016,  # 1.6%
    2.0:  0.013,  # 1.3%
    3.0:  0.012,  # 1.2%
    5.0:  0.011,  # 1.1%
    7.0:  0.011,  # 1.1%
    10.0: 0.011,  # 1.1%
    15.0: 0.011,  # 1.1%
    20.0: 0.011,  # 1.1%
    25.0: 0.011,  # 1.1%
    30.0: 0.011,  # 1.1%
}

HIGH_VOLATILITY_MULTIPLIER: float = math.sqrt(2)  # ~1.4142

# ---------------------------------------------------------------------------
# Inflation and cross-currency basis risk weights -- MAR21.9
# ---------------------------------------------------------------------------
RW_INFLATION: float = 0.016  # 1.6%
RW_XCCY_BASIS: float = 0.016  # 1.6%

# ---------------------------------------------------------------------------
# Low volatility currencies -- MAR21.9
# ---------------------------------------------------------------------------
LOW_VOLATILITY_CURRENCIES: set[str] = {
    "USD", "EUR", "GBP", "AUD", "CAD", "JPY", "SEK", "CHF",
}

# ---------------------------------------------------------------------------
# Intra-bucket correlation parameters (MAR21.9)
# ---------------------------------------------------------------------------
THETA: float = 0.03  # Correlation decay parameter
CORRELATION_FLOOR: float = 0.40  # Minimum intra-bucket correlation

# ---------------------------------------------------------------------------
# Cross-curve correlations within same bucket -- MAR21.9
# ---------------------------------------------------------------------------
RHO_CROSS_CURVE: float = 0.999  # Between different yield curves in same currency
RHO_INFLATION: float = 0.40  # Between inflation and yield curve
RHO_XCCY_BASIS: float = 0.00  # Between XCCY basis and everything else
RHO_INFLATION_XCCY: float = 0.00  # Between inflation and XCCY basis

# ---------------------------------------------------------------------------
# Inter-bucket correlation -- MAR21.9
# ---------------------------------------------------------------------------
GAMMA_GIRR: float = 0.50  # Between all currency pairs

# ---------------------------------------------------------------------------
# Vega parameters (MAR21.44-47)
# ---------------------------------------------------------------------------
VEGA_RISK_WEIGHT: float = 1.0  # 100% (min(sqrt(60/10), 1.0) = min(2.449, 1.0))
VEGA_LIQUIDITY_HORIZON: int = 60  # Business days
VEGA_OPTION_MATURITIES: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_UNDERLYING_TENORS: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_ALPHA: float = 0.01  # Correlation decay for vega


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_currency_category(currency: str) -> CurrencyCategory:
    """Determine currency category for risk weight lookup.

    Args:
        currency: ISO 4217 currency code (e.g. ``"USD"``).

    Returns:
        ``CurrencyCategory.LOW_VOLATILITY`` for the eight major currencies
        defined in MAR21.9, otherwise ``CurrencyCategory.HIGH_VOLATILITY``.
    """
    if currency.upper() in LOW_VOLATILITY_CURRENCIES:
        return CurrencyCategory.LOW_VOLATILITY
    return CurrencyCategory.HIGH_VOLATILITY


def get_delta_risk_weight(tenor: float, currency: str) -> float:
    """Get delta risk weight for a tenor and currency.

    For high-volatility currencies, the base risk weight is multiplied
    by ``sqrt(2)`` per MAR21.9.

    Args:
        tenor: Tenor vertex in years (must be one of :data:`TENORS`).
        currency: ISO 4217 currency code.

    Returns:
        Risk weight as a decimal (e.g. 0.017 for 1.7%).

    Raises:
        KeyError: If *tenor* is not a standard GIRR vertex.
    """
    base_rw = DELTA_RISK_WEIGHTS[tenor]
    if get_currency_category(currency) == CurrencyCategory.HIGH_VOLATILITY:
        return base_rw * HIGH_VOLATILITY_MULTIPLIER
    return base_rw


def compute_tenor_correlation(tenor_k: float, tenor_l: float) -> float:
    """Compute intra-bucket same-curve tenor correlation per MAR21.9(2).

    .. math::

        \\rho(k, l) = \\max\\!\\bigl(
            e^{-\\theta \\,|T_k - T_l| / \\min(T_k, T_l)},\\;
            40\\%
        \\bigr)

    Args:
        tenor_k: First tenor vertex in years.
        tenor_l: Second tenor vertex in years.

    Returns:
        Correlation between the two tenor vertices, floored at
        :data:`CORRELATION_FLOOR`.
    """
    if tenor_k == tenor_l:
        return 1.0
    ratio = abs(tenor_k - tenor_l) / min(tenor_k, tenor_l)
    raw = math.exp(-THETA * ratio)
    return max(raw, CORRELATION_FLOOR)


def apply_correlation_scenario(
    rho: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply correlation scenario adjustment per MAR21.6.

    +---------+--------------------------------------+
    | Scenario| Adjusted correlation                 |
    +=========+======================================+
    | LOW     | ``max(2*rho - 1, 0.75*rho)``         |
    +---------+--------------------------------------+
    | MEDIUM  | ``rho`` (no change)                  |
    +---------+--------------------------------------+
    | HIGH    | ``min(1.0, 1.25*rho)``               |
    +---------+--------------------------------------+

    Args:
        rho: Base correlation value.
        scenario: One of LOW / MEDIUM / HIGH.
        is_inter_bucket: Whether this is an inter-bucket correlation
            (reserved for future use with differentiated scaling).

    Returns:
        Scenario-adjusted correlation.
    """
    if scenario == CorrelationScenario.MEDIUM:
        return rho
    elif scenario == CorrelationScenario.HIGH:
        return min(1.0, 1.25 * rho)
    else:  # LOW
        return max(2 * rho - 1, 0.75 * rho)


def build_girr_correlation_matrix(
    currency: str,
    num_yield_curve_sensitivities: int,
    curve_labels: list[str],
    tenors: list[float],
    include_inflation: bool = False,
    include_xccy_basis: bool = False,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> "numpy.ndarray":
    """Build the full intra-bucket correlation matrix for a GIRR bucket.

    Matrix dimensions::

        n_yield_curve + (1 if inflation) + (1 if xccy_basis)

    Correlation rules applied:

    * **Yield curve to yield curve (same curve):** ``rho_tenor(k, l)``
    * **Yield curve to yield curve (different curve):**
      ``rho_tenor(k, l) * RHO_CROSS_CURVE`` (0.999)
    * **Yield curve to inflation:** ``RHO_INFLATION`` (0.40)
    * **Yield curve to XCCY basis:** ``RHO_XCCY_BASIS`` (0.00)
    * **Inflation to XCCY basis:** ``RHO_INFLATION_XCCY`` (0.00)

    Args:
        currency: ISO 4217 currency code for the bucket.
        num_yield_curve_sensitivities: Number of yield-curve risk factor
            entries (curve x tenor combinations).
        curve_labels: Label for each yield-curve sensitivity indicating
            which curve it belongs to (length must equal
            *num_yield_curve_sensitivities*).
        tenors: Tenor (in years) for each yield-curve sensitivity (length
            must equal *num_yield_curve_sensitivities*).
        include_inflation: Whether to add an inflation sensitivity row/column.
        include_xccy_basis: Whether to add a cross-currency basis
            sensitivity row/column.
        scenario: Correlation scenario to apply (LOW / MEDIUM / HIGH).

    Returns:
        A symmetric ``numpy.ndarray`` of shape ``(total, total)`` containing
        the scenario-adjusted correlation matrix.
    """
    import numpy as np  # noqa: WPS433 (local import to keep module lightweight)

    n = num_yield_curve_sensitivities
    extra = (1 if include_inflation else 0) + (1 if include_xccy_basis else 0)
    total = n + extra

    corr = np.eye(total)

    # --- Yield curve correlations -------------------------------------------
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_tenor_correlation(tenors[i], tenors[j])
            # Apply cross-curve factor if different curves
            if curve_labels[i] != curve_labels[j]:
                rho *= RHO_CROSS_CURVE
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho

    # --- Inflation correlations ---------------------------------------------
    if include_inflation:
        infl_idx = n
        for i in range(n):
            rho = apply_correlation_scenario(RHO_INFLATION, scenario)
            corr[i, infl_idx] = rho
            corr[infl_idx, i] = rho

    # --- XCCY basis correlations (0 with everything) ------------------------
    if include_xccy_basis:
        # All correlations with XCCY basis are 0; already set by np.eye
        pass

    return corr
