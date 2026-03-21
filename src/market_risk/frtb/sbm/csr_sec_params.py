"""CSR Securitization regulatory parameters per MAR21.14-21.15 Basel III Endgame.

All risk weights, correlations, and regulatory constants for the Credit Spread
Risk -- Securitization class (both Non-CTP and CTP) under FRTB Sensitivities-Based Method.

Reference: BCBS d457 MAR21.14-21.15, US Federal Reserve Basel III Endgame Final Rule.
"""
from __future__ import annotations

import math
from typing import Optional

from src.core.enums import (
    CorrelationScenario,
    CSRSecBucket,
    CSRSecCTPBucket,
)

# ---------------------------------------------------------------------------
# Standard tenor vertices (years) -- same 12 as GIRR/CSR (MAR21.14)
# ---------------------------------------------------------------------------
TENORS: list[float] = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 25.0, 30.0]

# ===========================================================================
#  NON-CTP PARAMETERS (MAR21.14)
# ===========================================================================

# ---------------------------------------------------------------------------
# Non-CTP delta risk weights -- MAR21.14 Table 6
# ---------------------------------------------------------------------------
CSR_SEC_NON_CTP_RW: dict[int, float] = {
    1: 0.009,   # 0.9% - RMBS Prime
    2: 0.015,   # 1.5% - RMBS Mid-prime
    3: 0.021,   # 2.1% - RMBS Sub-prime
    4: 0.025,   # 2.5% - CMBS
    5: 0.010,   # 1.0% - ABS Consumer (auto, credit cards, student)
    6: 0.012,   # 1.2% - CLO non-CTP
    7: 0.020,   # 2.0% - ABS Other
    8: 0.035,   # 3.5% - Other securitization
}

# ---------------------------------------------------------------------------
# Non-CTP intra-bucket correlations -- MAR21.14
# ---------------------------------------------------------------------------
CSR_SEC_NON_CTP_CORR: dict[int, float] = {
    1: 0.70,
    2: 0.60,
    3: 0.50,
    4: 0.65,
    5: 0.60,
    6: 0.55,
    7: 0.50,
    8: 0.40,
}

# ---------------------------------------------------------------------------
# Non-CTP inter-bucket correlation -- MAR21.14
# ---------------------------------------------------------------------------
GAMMA_NON_CTP: float = 0.25

# ---------------------------------------------------------------------------
# Non-CTP tenor correlation parameters -- MAR21.14
# Tenor correlation uses same formula as CSR Non-Sec:
#   rho_tenor = max(exp(-theta * |Tk - Tl| / min(Tk, Tl)), floor)
# ---------------------------------------------------------------------------
THETA_NON_CTP: float = 0.03
CORRELATION_FLOOR_NON_CTP: float = 0.40

# ---------------------------------------------------------------------------
# Non-CTP basis correlation -- MAR21.14
# ---------------------------------------------------------------------------
RHO_BASIS_SAME_TRANCHE: float = 1.0
RHO_BASIS_DIFF_TRANCHE: float = 0.999

# ---------------------------------------------------------------------------
# Non-CTP bucket descriptions
# ---------------------------------------------------------------------------
NON_CTP_BUCKET_NAMES: dict[int, str] = {
    1: "RMBS Prime",
    2: "RMBS Mid-prime",
    3: "RMBS Sub-prime",
    4: "CMBS",
    5: "ABS Consumer (auto, credit cards, student)",
    6: "CLO non-CTP",
    7: "ABS Other",
    8: "Other Securitization",
}


# ===========================================================================
#  CTP PARAMETERS (MAR21.15)
# ===========================================================================

# ---------------------------------------------------------------------------
# CTP delta risk weights -- MAR21.15 Table 7
# ---------------------------------------------------------------------------
CSR_SEC_CTP_RW: dict[int, float] = {
    1: 0.04,    # 4.0% - CTP IG
    2: 0.08,    # 8.0% - CTP HY
    3: 0.025,   # 2.5% - CTP Index IG
    4: 0.05,    # 5.0% - CTP Index HY
    5: 0.12,    # 12.0% - CTP Other
}

# ---------------------------------------------------------------------------
# CTP intra-bucket correlations -- MAR21.15
# ---------------------------------------------------------------------------
CSR_SEC_CTP_CORR: dict[int, float] = {
    1: 0.60,
    2: 0.55,
    3: 0.80,
    4: 0.75,
    5: 0.40,
}

# ---------------------------------------------------------------------------
# CTP inter-bucket correlation -- MAR21.15
# ---------------------------------------------------------------------------
GAMMA_CTP: float = 0.20

# ---------------------------------------------------------------------------
# CTP tenor correlation parameters -- MAR21.15
# ---------------------------------------------------------------------------
THETA_CTP: float = 0.03
CORRELATION_FLOOR_CTP: float = 0.40

# ---------------------------------------------------------------------------
# CTP basis correlation -- MAR21.15
# ---------------------------------------------------------------------------
RHO_CTP_BASIS_SAME_TRANCHE: float = 1.0
RHO_CTP_BASIS_DIFF_TRANCHE: float = 0.999

# ---------------------------------------------------------------------------
# CTP bucket descriptions
# ---------------------------------------------------------------------------
CTP_BUCKET_NAMES: dict[int, str] = {
    1: "CTP Investment Grade",
    2: "CTP High Yield",
    3: "CTP Index Investment Grade",
    4: "CTP Index High Yield",
    5: "CTP Other",
}


# ===========================================================================
#  VEGA PARAMETERS (MAR21.44-47)
# ===========================================================================
VEGA_RISK_WEIGHT: float = 1.0  # min(sqrt(120/10), 1.0) = 1.0
VEGA_LIQUIDITY_HORIZON_NON_CTP: int = 120  # Business days
VEGA_LIQUIDITY_HORIZON_CTP: int = 120      # Business days
VEGA_OPTION_MATURITIES: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_UNDERLYING_TENORS: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_ALPHA: float = 0.01  # Correlation decay for vega


# ===========================================================================
#  HELPER FUNCTIONS
# ===========================================================================

def get_non_ctp_risk_weight(bucket: int) -> float:
    """Get delta risk weight for a CSR Sec Non-CTP bucket.

    Args:
        bucket: Bucket number (1-8).

    Returns:
        Risk weight as a decimal (e.g. 0.009 for 0.9%).

    Raises:
        KeyError: If *bucket* is not a valid Non-CTP bucket.
    """
    return CSR_SEC_NON_CTP_RW[bucket]


def get_ctp_risk_weight(bucket: int) -> float:
    """Get delta risk weight for a CSR Sec CTP bucket.

    Args:
        bucket: Bucket number (1-5).

    Returns:
        Risk weight as a decimal (e.g. 0.04 for 4.0%).

    Raises:
        KeyError: If *bucket* is not a valid CTP bucket.
    """
    return CSR_SEC_CTP_RW[bucket]


def compute_tenor_correlation(
    tenor_k: float,
    tenor_l: float,
    is_ctp: bool = False,
) -> float:
    """Compute tenor correlation per MAR21.14/21.15.

    .. math::

        \\rho_{\\mathrm{tenor}}(k, l) = \\max\\!\\bigl(
            e^{-\\theta \\,|T_k - T_l| / \\min(T_k, T_l)},\\;
            \\mathrm{floor}
        \\bigr)

    Args:
        tenor_k: First tenor vertex in years.
        tenor_l: Second tenor vertex in years.
        is_ctp: Whether to use CTP parameters.

    Returns:
        Correlation between the two tenor vertices.
    """
    if tenor_k == tenor_l:
        return 1.0
    theta = THETA_CTP if is_ctp else THETA_NON_CTP
    floor = CORRELATION_FLOOR_CTP if is_ctp else CORRELATION_FLOOR_NON_CTP
    ratio = abs(tenor_k - tenor_l) / min(tenor_k, tenor_l)
    raw = math.exp(-theta * ratio)
    return max(raw, floor)


def compute_tranche_correlation(
    same_tranche: bool,
    is_ctp: bool = False,
) -> float:
    """Compute the tranche (basis) correlation component.

    Args:
        same_tranche: True if both risk factors reference the same tranche.
        is_ctp: Whether to use CTP parameters.

    Returns:
        1.0 for same tranche, 0.999 for different tranches.
    """
    if is_ctp:
        return RHO_CTP_BASIS_SAME_TRANCHE if same_tranche else RHO_CTP_BASIS_DIFF_TRANCHE
    return RHO_BASIS_SAME_TRANCHE if same_tranche else RHO_BASIS_DIFF_TRANCHE


def compute_intra_bucket_correlation(
    bucket: int,
    tenor_k: float,
    tenor_l: float,
    same_tranche: bool,
    is_ctp: bool = False,
) -> float:
    """Compute the full intra-bucket correlation for CSR Securitization.

    The correlation decomposes into:

    .. math::

        \\rho_{kl} = \\rho_{\\mathrm{bucket}} \\times
                     \\rho_{\\mathrm{tenor}} \\times
                     \\rho_{\\mathrm{tranche}}

    Args:
        bucket: Bucket number (1-8 for Non-CTP, 1-5 for CTP).
        tenor_k: Tenor of risk factor *k* in years.
        tenor_l: Tenor of risk factor *l* in years.
        same_tranche: Whether both risk factors reference the same tranche.
        is_ctp: Whether to use CTP parameters.

    Returns:
        Combined intra-bucket correlation.
    """
    if is_ctp:
        rho_bucket = CSR_SEC_CTP_CORR[bucket]
    else:
        rho_bucket = CSR_SEC_NON_CTP_CORR[bucket]

    rho_tenor = compute_tenor_correlation(tenor_k, tenor_l, is_ctp=is_ctp)
    rho_tranche = compute_tranche_correlation(same_tranche, is_ctp=is_ctp)

    return rho_bucket * rho_tenor * rho_tranche


def get_inter_bucket_correlation(is_ctp: bool = False) -> float:
    """Get the inter-bucket correlation for CSR Securitization.

    Args:
        is_ctp: Whether to use CTP inter-bucket correlation.

    Returns:
        Inter-bucket correlation (0.25 for Non-CTP, 0.20 for CTP).
    """
    return GAMMA_CTP if is_ctp else GAMMA_NON_CTP


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


def build_csr_sec_correlation_matrix(
    bucket: int,
    tranches: list[str],
    tenors: list[float],
    is_ctp: bool = False,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> "numpy.ndarray":
    """Build the full intra-bucket correlation matrix for a CSR Sec bucket.

    Each entry in the matrix corresponds to a sensitivity identified by its
    (tranche, tenor) pair. The correlation between entries *i* and *j* is:

    .. math::

        \\rho_{ij} = \\rho_{\\mathrm{bucket}} \\times
                     \\rho_{\\mathrm{tenor}} \\times
                     \\rho_{\\mathrm{tranche}}

    with scenario adjustments applied per MAR21.6.

    Args:
        bucket: Bucket number (1-8 for Non-CTP, 1-5 for CTP).
        tranches: Tranche identifier for each sensitivity (length *n*).
        tenors: Tenor in years for each sensitivity (length *n*).
        is_ctp: Whether this is a CTP bucket.
        scenario: Correlation scenario to apply.

    Returns:
        A symmetric ``numpy.ndarray`` of shape ``(n, n)`` with the
        scenario-adjusted intra-bucket correlation matrix.
    """
    import numpy as np

    n = len(tranches)
    corr = np.eye(n, dtype=np.float64)

    for i in range(n):
        for j in range(i + 1, n):
            same_tranche = (tranches[i] == tranches[j])
            rho = compute_intra_bucket_correlation(
                bucket=bucket,
                tenor_k=tenors[i],
                tenor_l=tenors[j],
                same_tranche=same_tranche,
                is_ctp=is_ctp,
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho

    return corr
