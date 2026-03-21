"""Commodity risk regulatory parameters per MAR21.19-21.20 Basel III Endgame.

All risk weights, correlations, and regulatory constants for the
Commodity risk class under FRTB Sensitivities-Based Method.

Buckets:
  B1: Coal and crude oil
  B2: Light ends (gasoline, naphtha)
  B3: Middle distillates (jet fuel, diesel, heating oil)
  B4: Heavy distillates and residual fuel oil
  B5: Natural gas
  B6: Electricity and carbon trading
  B7: Precious metals (gold, silver, platinum)
  B8: Base metals (copper, aluminium, zinc, nickel)
  B9: Grains and oilseed (wheat, corn, soybeans)
  B10: Softs and other agriculturals (sugar, cotton, cocoa)
  B11: Other commodities (freight, emissions, exotic)
"""
from __future__ import annotations

import math

from src.core.enums import CorrelationScenario

# ---------------------------------------------------------------------------
# Delta risk weights per bucket (MAR21.19 Table 10) -- decimal fractions
# ---------------------------------------------------------------------------
COMMODITY_DELTA_RW: dict[int, float] = {
    1: 0.30,   # Coal and crude oil
    2: 0.35,   # Light ends
    3: 0.30,   # Middle distillates
    4: 0.35,   # Heavy distillates
    5: 0.40,   # Natural gas
    6: 0.60,   # Electricity and carbon trading
    7: 0.20,   # Precious metals
    8: 0.35,   # Base metals
    9: 0.25,   # Grains and oilseed
    10: 0.35,  # Softs and other agriculturals
    11: 0.50,  # Other commodities
}

# ---------------------------------------------------------------------------
# Intra-bucket correlations per bucket (MAR21.20 Table 11)
#
# Full commodity intra-bucket correlation:
#   rho_kl = rho_commodity * rho_tenor * rho_basis
# where rho_tenor and rho_basis are applied separately.
# The values below represent the base rho_commodity per bucket.
# ---------------------------------------------------------------------------
COMMODITY_INTRA_CORR: dict[int, float] = {
    1: 0.55,   # Coal and crude oil
    2: 0.95,   # Light ends
    3: 0.95,   # Middle distillates
    4: 0.80,   # Heavy distillates
    5: 0.80,   # Natural gas
    6: 0.30,   # Electricity and carbon trading
    7: 0.55,   # Precious metals
    8: 0.40,   # Base metals
    9: 0.45,   # Grains and oilseed
    10: 0.45,  # Softs and other agriculturals
    11: 0.15,  # Other commodities
}

# ---------------------------------------------------------------------------
# Tenor correlation parameter for delivery tenors
# rho_tenor = exp(-alpha * |T_k - T_l| / min(T_k, T_l))
# ---------------------------------------------------------------------------
COMMODITY_TENOR_ALPHA: float = 0.01

# ---------------------------------------------------------------------------
# Basis correlation (different delivery locations)
# ---------------------------------------------------------------------------
COMMODITY_RHO_BASIS: float = 0.999

# ---------------------------------------------------------------------------
# Inter-bucket correlation (MAR21.20)
# Base gamma = 0.20 for all pairs
# Energy group (buckets 1-6): gamma = 0.40
# ---------------------------------------------------------------------------
COMMODITY_INTER_BUCKET_BASE: float = 0.20
COMMODITY_INTER_BUCKET_ENERGY: float = 0.40

# Energy group bucket IDs
COMMODITY_ENERGY_BUCKETS: set[int] = {1, 2, 3, 4, 5, 6}

# ---------------------------------------------------------------------------
# Vega parameters (MAR21.44-47)
# Commodity liquidity horizon = 120 days
# RW_vega = min(sqrt(RWsigma * LH / T), 1.0) -> capped at 100%
# ---------------------------------------------------------------------------
COMMODITY_VEGA_RW: float = 1.0  # 100%
COMMODITY_VEGA_LIQUIDITY_HORIZON: int = 120  # Business days
COMMODITY_VEGA_ALPHA: float = 0.01  # Correlation decay for vega

# ---------------------------------------------------------------------------
# All valid bucket IDs
# ---------------------------------------------------------------------------
COMMODITY_BUCKETS: list[int] = list(range(1, 12))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_commodity_delta_rw(bucket: int) -> float:
    """Get delta risk weight for a commodity bucket.

    Args:
        bucket: Bucket number (1-11).

    Returns:
        Risk weight as a decimal (e.g. 0.30 for 30%).

    Raises:
        KeyError: If *bucket* is not a valid commodity bucket.
    """
    return COMMODITY_DELTA_RW[bucket]


def get_commodity_intra_corr(bucket: int) -> float:
    """Get base intra-bucket correlation for a commodity bucket.

    Args:
        bucket: Bucket number (1-11).

    Returns:
        Base intra-bucket correlation.

    Raises:
        KeyError: If *bucket* is not a valid commodity bucket.
    """
    return COMMODITY_INTRA_CORR[bucket]


def get_commodity_inter_bucket_corr(bucket_b: int, bucket_c: int) -> float:
    """Get inter-bucket correlation for a pair of commodity buckets.

    Within the energy group (buckets 1-6): gamma = 0.40.
    All other pairs: gamma = 0.20.

    Args:
        bucket_b: First bucket number.
        bucket_c: Second bucket number.

    Returns:
        Inter-bucket correlation.
    """
    if bucket_b in COMMODITY_ENERGY_BUCKETS and bucket_c in COMMODITY_ENERGY_BUCKETS:
        return COMMODITY_INTER_BUCKET_ENERGY
    return COMMODITY_INTER_BUCKET_BASE


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


def compute_commodity_tenor_correlation(tenor_k: float, tenor_l: float) -> float:
    """Compute tenor correlation for commodity delivery dates.

    rho_tenor = exp(-alpha * |T_k - T_l| / min(T_k, T_l))

    Args:
        tenor_k: First delivery tenor in years.
        tenor_l: Second delivery tenor in years.

    Returns:
        Tenor correlation.
    """
    if tenor_k == tenor_l:
        return 1.0
    ratio = abs(tenor_k - tenor_l) / min(tenor_k, tenor_l)
    return math.exp(-COMMODITY_TENOR_ALPHA * ratio)


def build_commodity_intra_bucket_corr_matrix(
    n: int,
    bucket: int,
    tenors: list[float] | None = None,
    basis_flags: list[str] | None = None,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> "numpy.ndarray":
    """Build the intra-bucket correlation matrix for a commodity bucket.

    Full correlation structure:
        rho_kl = rho_commodity * rho_tenor * rho_basis

    where:
    - rho_commodity is the base intra-bucket correlation from Table 11
    - rho_tenor = exp(-alpha * |T_k - T_l| / min(T_k, T_l))
    - rho_basis = 0.999 if different delivery locations, else 1.0

    If tenors or basis_flags are not provided, the simplified uniform
    correlation (rho_commodity only) is used.

    Args:
        n: Number of sensitivities in the bucket.
        bucket: Bucket number (1-11).
        tenors: Optional list of delivery tenors in years.
        basis_flags: Optional list of delivery location identifiers.
        scenario: Correlation scenario (LOW / MEDIUM / HIGH).

    Returns:
        numpy ndarray of shape (n, n).
    """
    import numpy as np

    base_rho = get_commodity_intra_corr(bucket)

    corr = np.eye(n, dtype=np.float64)

    for i in range(n):
        for j in range(i + 1, n):
            rho = base_rho

            # Apply tenor correlation if available
            if tenors is not None and len(tenors) == n:
                rho *= compute_commodity_tenor_correlation(tenors[i], tenors[j])

            # Apply basis correlation if different locations
            if basis_flags is not None and len(basis_flags) == n:
                if basis_flags[i] != basis_flags[j]:
                    rho *= COMMODITY_RHO_BASIS

            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho

    return corr
