"""Equity risk regulatory parameters per MAR21.17-21.18 Basel III Endgame.

All risk weights, correlations, and regulatory constants for the
Equity risk class under FRTB Sensitivities-Based Method.

Buckets 1-5: Emerging Markets large cap (Consumer/Telecom/BasicMaterials/Financials/Tech)
Buckets 6-10: Advanced Economies large cap (same sectors)
Bucket 11: All small cap
Bucket 12: Large cap developed market indices
Bucket 13: Other equity indices
"""
from __future__ import annotations

import math

from src.core.enums import CorrelationScenario

# ---------------------------------------------------------------------------
# Delta risk weights per bucket (MAR21.17 Table 8) -- decimal fractions
# ---------------------------------------------------------------------------
EQUITY_DELTA_RW: dict[int, float] = {
    1: 0.55,   # EM large cap - Consumer, utilities
    2: 0.60,   # EM large cap - Telecom, industrials
    3: 0.45,   # EM large cap - Basic materials, energy
    4: 0.55,   # EM large cap - Financials
    5: 0.30,   # EM large cap - Technology, health care
    6: 0.25,   # AE large cap - Consumer, utilities
    7: 0.25,   # AE large cap - Telecom, industrials
    8: 0.30,   # AE large cap - Basic materials, energy
    9: 0.20,   # AE large cap - Financials
    10: 0.25,  # AE large cap - Technology, health care
    11: 0.70,  # All small cap
    12: 0.15,  # Large cap developed market indices
    13: 0.25,  # Other equity indices
}

# ---------------------------------------------------------------------------
# Intra-bucket correlations per bucket (MAR21.18 Table 9)
# ---------------------------------------------------------------------------
EQUITY_INTRA_CORR: dict[int, float] = {
    1: 0.15,   # EM large cap
    2: 0.15,
    3: 0.15,
    4: 0.15,
    5: 0.15,
    6: 0.25,   # AE large cap
    7: 0.25,
    8: 0.25,
    9: 0.25,
    10: 0.25,
    11: 0.075,  # Small cap
    12: 0.80,   # Index buckets
    13: 0.80,
}

# ---------------------------------------------------------------------------
# Inter-bucket correlation (MAR21.18)
# All pairs: gamma = 0.15, except buckets 12-13 which is 0.75
# ---------------------------------------------------------------------------
EQUITY_INTER_BUCKET_BASE: float = 0.15
EQUITY_INTER_BUCKET_INDEX: float = 0.75  # Between bucket 12 and 13

# ---------------------------------------------------------------------------
# Vega parameters (MAR21.44-47)
# Equity liquidity horizon = 20 days
# RW_vega = 0.55 for equity risk class
# ---------------------------------------------------------------------------
EQUITY_VEGA_RW: float = 0.55
EQUITY_VEGA_LIQUIDITY_HORIZON: int = 20  # Business days
EQUITY_VEGA_ALPHA: float = 0.01  # Correlation decay for vega

# ---------------------------------------------------------------------------
# All valid bucket IDs
# ---------------------------------------------------------------------------
EQUITY_BUCKETS: list[int] = list(range(1, 14))

# ---------------------------------------------------------------------------
# Energy bucket group (buckets sharing higher inter-bucket correlation)
# For equity there is no energy group; this constant tracks index buckets
# ---------------------------------------------------------------------------
EQUITY_INDEX_BUCKETS: set[int] = {12, 13}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_equity_delta_rw(bucket: int) -> float:
    """Get delta risk weight for an equity bucket.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        Risk weight as a decimal (e.g. 0.55 for 55%).

    Raises:
        KeyError: If *bucket* is not a valid equity bucket.
    """
    return EQUITY_DELTA_RW[bucket]


def get_equity_intra_corr(bucket: int) -> float:
    """Get base intra-bucket correlation for an equity bucket.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        Intra-bucket correlation (e.g. 0.15 for EM large cap).

    Raises:
        KeyError: If *bucket* is not a valid equity bucket.
    """
    return EQUITY_INTRA_CORR[bucket]


def get_equity_inter_bucket_corr(bucket_b: int, bucket_c: int) -> float:
    """Get inter-bucket correlation for a pair of equity buckets.

    All pairs use gamma = 0.15, except buckets 12 and 13 which use 0.75.

    Args:
        bucket_b: First bucket number.
        bucket_c: Second bucket number.

    Returns:
        Inter-bucket correlation.
    """
    pair = frozenset({bucket_b, bucket_c})
    if pair == frozenset({12, 13}):
        return EQUITY_INTER_BUCKET_INDEX
    return EQUITY_INTER_BUCKET_BASE


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


def build_equity_intra_bucket_corr_matrix(
    n: int,
    bucket: int,
    scenario: CorrelationScenario,
) -> "numpy.ndarray":
    """Build the intra-bucket correlation matrix for an equity bucket.

    All pairs within the same bucket share the same correlation value
    from Table 9, adjusted by the scenario multiplier.

    Args:
        n: Number of sensitivities in the bucket.
        bucket: Bucket number (1-13).
        scenario: Correlation scenario (LOW / MEDIUM / HIGH).

    Returns:
        numpy ndarray of shape (n, n).
    """
    import numpy as np

    base_rho = get_equity_intra_corr(bucket)
    rho = apply_correlation_scenario(base_rho, scenario)

    corr = np.full((n, n), rho, dtype=np.float64)
    np.fill_diagonal(corr, 1.0)
    return corr
