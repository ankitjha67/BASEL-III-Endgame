"""IRRBB parameters — Interest Rate Risk in the Banking Book.

Defines the six prescribed shock scenarios, currency-specific shock sizes,
time bucket midpoints, and all regulatory parameters for EVE and NII
calculations per BCBS d368.

References:
- BCBS d368: "Interest Rate Risk in the Banking Book" (April 2016)
- BCBS d368 Annex 1: Prescribed interest rate shock scenarios
- BCBS d368 Annex 2: Currency-specific shock parameters
- BCBS d368 Section 3: Standardised framework for IRRBB
- 12 CFR 217.11: Capital buffer implications
- SR 10-1: Interagency Advisory on IRRBB

All monetary amounts in USD millions ($M) unless otherwise stated.
All rates in basis points (bp) or decimals as noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =========================================================================
#  Scenario Definitions
#  Reference: BCBS d368 Section 3, Table 1
# =========================================================================

class IRRBBScenario(Enum):
    """Six prescribed IRRBB shock scenarios per BCBS d368.

    Each scenario represents a different interest rate movement pattern
    applied to the yield curve.

    Reference: BCBS d368 Section 3.2, paras 109-115.
    """
    PARALLEL_UP = "PARALLEL_UP"
    """Uniform upward shift across all maturities."""

    PARALLEL_DOWN = "PARALLEL_DOWN"
    """Uniform downward shift across all maturities."""

    STEEPENER = "STEEPENER"
    """Short rates down, long rates up (curve steepening)."""

    FLATTENER = "FLATTENER"
    """Short rates up, long rates down (curve flattening)."""

    SHORT_RATE_UP = "SHORT_RATE_UP"
    """Short-end rates increase; long-end largely unchanged."""

    SHORT_RATE_DOWN = "SHORT_RATE_DOWN"
    """Short-end rates decrease; long-end largely unchanged."""


IRRBB_SCENARIO_NAMES: dict[IRRBBScenario, str] = {
    IRRBBScenario.PARALLEL_UP: "Parallel Up",
    IRRBBScenario.PARALLEL_DOWN: "Parallel Down",
    IRRBBScenario.STEEPENER: "Steepener (Short Down, Long Up)",
    IRRBBScenario.FLATTENER: "Flattener (Short Up, Long Down)",
    IRRBBScenario.SHORT_RATE_UP: "Short Rate Shock Up",
    IRRBBScenario.SHORT_RATE_DOWN: "Short Rate Shock Down",
}
"""Human-readable scenario names. Reference: BCBS d368 Table 1."""


# =========================================================================
#  Currency-Specific Shock Parameters
#  Reference: BCBS d368 Annex 2, Table 7
# =========================================================================

@dataclass(frozen=True)
class IRRBBShockParams:
    """Currency-specific interest rate shock parameters.

    Defines the size of parallel, short-rate, and long-rate shocks
    for a specific currency.

    Reference: BCBS d368 Annex 2, Table 7.

    Attributes:
        currency: ISO 4217 currency code.
        parallel_shock_bp: Parallel shift size in basis points.
        short_rate_shock_bp: Short-rate shock size in basis points.
        long_rate_shock_bp: Long-rate shock size in basis points.
    """
    currency: str
    parallel_shock_bp: int
    short_rate_shock_bp: int
    long_rate_shock_bp: int


# USD shocks per BCBS d368 Annex 2
DEFAULT_USD_SHOCKS = IRRBBShockParams(
    currency="USD",
    parallel_shock_bp=200,
    short_rate_shock_bp=300,
    long_rate_shock_bp=150,
)
"""USD interest rate shocks. Reference: BCBS d368 Annex 2, Table 7."""


# Currency-specific shocks per BCBS d368 Annex 2, Table 7
CURRENCY_SPECIFIC_SHOCKS: dict[str, IRRBBShockParams] = {
    "USD": DEFAULT_USD_SHOCKS,
    "EUR": IRRBBShockParams(
        currency="EUR",
        parallel_shock_bp=200,
        short_rate_shock_bp=300,
        long_rate_shock_bp=150,
    ),
    "GBP": IRRBBShockParams(
        currency="GBP",
        parallel_shock_bp=250,
        short_rate_shock_bp=300,
        long_rate_shock_bp=150,
    ),
    "JPY": IRRBBShockParams(
        currency="JPY",
        parallel_shock_bp=100,
        short_rate_shock_bp=100,
        long_rate_shock_bp=100,
    ),
    "CHF": IRRBBShockParams(
        currency="CHF",
        parallel_shock_bp=100,
        short_rate_shock_bp=150,
        long_rate_shock_bp=100,
    ),
    "AUD": IRRBBShockParams(
        currency="AUD",
        parallel_shock_bp=300,
        short_rate_shock_bp=400,
        long_rate_shock_bp=200,
    ),
    "CAD": IRRBBShockParams(
        currency="CAD",
        parallel_shock_bp=200,
        short_rate_shock_bp=300,
        long_rate_shock_bp=150,
    ),
    "SEK": IRRBBShockParams(
        currency="SEK",
        parallel_shock_bp=200,
        short_rate_shock_bp=300,
        long_rate_shock_bp=150,
    ),
    "SGD": IRRBBShockParams(
        currency="SGD",
        parallel_shock_bp=150,
        short_rate_shock_bp=200,
        long_rate_shock_bp=100,
    ),
    "HKD": IRRBBShockParams(
        currency="HKD",
        parallel_shock_bp=200,
        short_rate_shock_bp=300,
        long_rate_shock_bp=150,
    ),
    "CNY": IRRBBShockParams(
        currency="CNY",
        parallel_shock_bp=250,
        short_rate_shock_bp=300,
        long_rate_shock_bp=150,
    ),
}
"""Currency-specific shock calibration. Reference: BCBS d368 Annex 2."""


def get_shock_params(currency: str) -> IRRBBShockParams:
    """Get shock parameters for a given currency.

    Falls back to USD parameters for currencies not in the lookup table.

    Args:
        currency: ISO 4217 currency code.

    Returns:
        IRRBBShockParams for the currency.

    Reference: BCBS d368 Annex 2, Table 7.
    """
    return CURRENCY_SPECIFIC_SHOCKS.get(currency.upper(), DEFAULT_USD_SHOCKS)


# =========================================================================
#  Time Bucket Definitions
#  Reference: BCBS d368 Section 3.3, Table 2
# =========================================================================

TIME_BUCKETS_MIDPOINTS: list[float] = [
    0.0028,   # Overnight (1 day / 365)
    0.0417,   # 1 month midpoint (0.5M)
    0.125,    # 3 month midpoint (1.5M)
    0.25,     # 6 month midpoint (3M)
    0.5,      # 9 month midpoint (6M)
    0.75,     # 1 year midpoint (9M)
    1.5,      # 2 year midpoint
    2.5,      # 3 year midpoint
    3.5,      # 4 year midpoint
    4.5,      # 5 year midpoint
    5.5,      # 6 year midpoint
    6.5,      # 7 year midpoint
    7.5,      # 8 year midpoint
    8.5,      # 9 year midpoint
    9.5,      # 10 year midpoint
    12.5,     # 15 year midpoint
    17.5,     # 20 year midpoint
    22.5,     # 25 year midpoint
    25.0,     # 25+ year bucket
]
"""Midpoints of standard time buckets for EVE calculation (in years).
Reference: BCBS d368 Section 3.3, Table 2."""

TIME_BUCKET_LABELS: list[str] = [
    "O/N",
    "1M",
    "3M",
    "6M",
    "9M",
    "1Y",
    "2Y",
    "3Y",
    "4Y",
    "5Y",
    "6Y",
    "7Y",
    "8Y",
    "9Y",
    "10Y",
    "15Y",
    "20Y",
    "25Y",
    "25Y+",
]
"""Labels for time buckets. Reference: BCBS d368 Section 3.3."""


# =========================================================================
#  Scenario Shock Functions
#  Reference: BCBS d368 Section 3.2, paras 109-115
# =========================================================================

def compute_scenario_shocks(
    scenario: IRRBBScenario,
    shock_params: IRRBBShockParams,
    time_buckets: Optional[list[float]] = None,
) -> list[float]:
    """Compute rate shocks for each time bucket under a given scenario.

    Implements the six prescribed scenarios from BCBS d368:
    - Parallel: uniform shift of +/- parallel_shock_bp
    - Steepener: short down by -0.65*short_shock, long up by +0.9*long_shock
    - Flattener: short up by +0.8*short_shock, long down by -0.6*long_shock
    - Short up/down: shock concentrated on short end, decaying with tenor

    Args:
        scenario: One of the six prescribed scenarios.
        shock_params: Currency-specific shock magnitudes.
        time_buckets: Time bucket midpoints in years. Uses default if None.

    Returns:
        List of rate shocks in decimal (e.g., 0.02 = 200bp) for each bucket.

    Reference: BCBS d368 Section 3.2, paras 109-115, Annex 1.
    """
    buckets = time_buckets or TIME_BUCKETS_MIDPOINTS

    parallel_bp = shock_params.parallel_shock_bp
    short_bp = shock_params.short_rate_shock_bp
    long_bp = shock_params.long_rate_shock_bp

    shocks: list[float] = []
    max_tenor = max(buckets) if buckets else 25.0

    for t in buckets:
        # Scalar function S(t) for short-rate interpolation
        # S(t) = exp(-t/4) per BCBS d368 Annex 1
        import math
        s_t = math.exp(-t / 4.0)
        # Long-rate weight: L(t) = 1 - S(t)
        l_t = 1.0 - s_t

        if scenario == IRRBBScenario.PARALLEL_UP:
            shock_bp = parallel_bp
        elif scenario == IRRBBScenario.PARALLEL_DOWN:
            shock_bp = -parallel_bp
        elif scenario == IRRBBScenario.STEEPENER:
            # Short rates down, long rates up
            # per BCBS d368 Annex 1: -0.65*Rshort*S(t) + 0.9*Rlong*L(t)
            shock_bp = -0.65 * short_bp * s_t + 0.9 * long_bp * l_t
        elif scenario == IRRBBScenario.FLATTENER:
            # Short rates up, long rates down
            # per BCBS d368 Annex 1: +0.8*Rshort*S(t) - 0.6*Rlong*L(t)
            shock_bp = 0.8 * short_bp * s_t - 0.6 * long_bp * l_t
        elif scenario == IRRBBScenario.SHORT_RATE_UP:
            # Short rates up with decay
            shock_bp = short_bp * s_t
        elif scenario == IRRBBScenario.SHORT_RATE_DOWN:
            # Short rates down with decay
            shock_bp = -short_bp * s_t
        else:
            shock_bp = 0.0

        shocks.append(shock_bp / 10000.0)  # Convert bp to decimal

    return shocks


# =========================================================================
#  Floor / Cap Parameters
#  Reference: BCBS d368 Section 3.2, para 116
# =========================================================================

AUTOMATIC_CAP_FLOOR: bool = True
"""Apply automatic interest rate floor per BCBS d368.
Shocked rates cannot fall below the floor rate.
Reference: BCBS d368 Section 3.2, para 116."""

EVE_FLOOR_RATE: float = -0.01
"""Floor rate for EVE calculation: -100bp (-1.0%).
Post-shock interest rates cannot be below this floor.
Reference: BCBS d368 Section 3.2, para 116."""


# =========================================================================
#  NII Parameters
#  Reference: BCBS d368 Section 3.4
# =========================================================================

NII_HORIZON_YEARS: float = 1.0
"""NII calculation horizon: 1 year.
Reference: BCBS d368 Section 3.4, para 120."""

NII_CONSTANT_BALANCE_SHEET: bool = True
"""Constant balance sheet assumption for NII.
Assets and liabilities maturing within the horizon are replaced with
instruments of similar characteristics.
Reference: BCBS d368 Section 3.4, para 121."""


# =========================================================================
#  Outlier / Materiality Thresholds
#  Reference: BCBS d368 Principles 5, 7
# =========================================================================

EVE_OUTLIER_THRESHOLD_PCT: float = 0.15
"""EVE outlier threshold: 15% of Tier 1 capital.
Triggers supervisory review if the maximum EVE decline exceeds this.
Reference: BCBS d368 Principle 7."""

NII_MATERIALITY_THRESHOLD_PCT: float = 0.05
"""NII materiality threshold: 5% of Tier 1 capital.
Reference: BCBS d368 Principle 5."""
