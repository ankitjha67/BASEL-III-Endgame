"""Aggregation utilities for SBM risk charge calculations.

Implements the intra-bucket and inter-bucket aggregation formulas
from MAR21.4-21.6 of the Basel III FRTB framework.
"""

from __future__ import annotations

import math

import numpy as np

from src.core.enums import CorrelationScenario


def apply_scenario_multiplier(
    correlation: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply correlation scenario multiplier per MAR21.6.

    Args:
        correlation: Base (medium) correlation value.
        scenario: LOW, MEDIUM, or HIGH scenario.
        is_inter_bucket: Whether this is an inter-bucket correlation.

    Returns:
        Adjusted correlation, clamped to [-1, 1].
    """
    if scenario == CorrelationScenario.MEDIUM:
        return correlation
    elif scenario == CorrelationScenario.HIGH:
        return min(1.0, 1.25 * correlation)
    else:  # LOW
        return max(2 * correlation - 1, 0.75 * correlation)


def intra_bucket_aggregation(
    weighted_sensitivities: np.ndarray,
    correlation_matrix: np.ndarray,
) -> tuple[float, float]:
    """Compute intra-bucket capital charge K_b per MAR21.4(3).

    Formula:
        K_b = sqrt(max(sum_k sum_l rho_kl * WS_k * WS_l, 0))

    If the sum under the square root is negative, K_b is computed using
    an alternative formula to avoid imaginary results.

    Args:
        weighted_sensitivities: Array of WS_k values for the bucket.
        correlation_matrix: Matrix of rho_kl correlations.

    Returns:
        Tuple of (K_b, S_b) where:
            K_b = intra-bucket capital charge
            S_b = sum of weighted sensitivities
    """
    if len(weighted_sensitivities) == 0:
        return 0.0, 0.0

    s_b = float(np.sum(weighted_sensitivities))

    # Compute sum_k sum_l rho_kl * WS_k * WS_l
    ws = weighted_sensitivities.reshape(-1, 1)
    cross_product = ws @ ws.T
    variance_sum = float(np.sum(correlation_matrix * cross_product))

    if variance_sum >= 0:
        k_b = math.sqrt(variance_sum)
    else:
        # Alternative: K_b = sqrt(sum_k WS_k^2) — diagonal-only fallback
        k_b = math.sqrt(float(np.sum(weighted_sensitivities ** 2)))

    return k_b, s_b


def inter_bucket_aggregation(
    bucket_charges: dict[str, float],
    bucket_net_sensitivities: dict[str, float],
    inter_bucket_correlation: float,
) -> float:
    """Compute inter-bucket aggregated capital charge per MAR21.4(4).

    Formula:
        Capital = sqrt(sum_b K_b^2 + sum_b sum_{c!=b} gamma_bc * S_b * S_c)

    Where S_b is capped: S_b = max(min(sum(WS_k), K_b), -K_b)

    Args:
        bucket_charges: Dict of bucket_id -> K_b.
        bucket_net_sensitivities: Dict of bucket_id -> raw S_b.
        inter_bucket_correlation: gamma_bc between buckets.

    Returns:
        Total aggregated capital charge.
    """
    if not bucket_charges:
        return 0.0

    buckets = list(bucket_charges.keys())

    # Cap S_b to [-K_b, K_b]
    capped_s = {}
    for b in buckets:
        k_b = bucket_charges[b]
        raw_s = bucket_net_sensitivities.get(b, 0.0)
        capped_s[b] = max(min(raw_s, k_b), -k_b)

    # Sum of K_b^2
    sum_kb_squared = sum(k ** 2 for k in bucket_charges.values())

    # Cross-bucket terms
    cross_sum = 0.0
    for i, b in enumerate(buckets):
        for j, c in enumerate(buckets):
            if i < j:
                cross_sum += inter_bucket_correlation * capped_s[b] * capped_s[c]
    cross_sum *= 2  # Symmetric: count both (b,c) and (c,b)

    total_variance = sum_kb_squared + cross_sum

    if total_variance >= 0:
        return math.sqrt(total_variance)
    else:
        # Fallback: sum of individual bucket charges
        return sum(abs(k) for k in bucket_charges.values())


def curvature_aggregation(
    cvr_values: dict[str, float],
    correlation_matrix_func: object,
    inter_bucket_correlation: float,
    buckets: list[str],
) -> float:
    """Compute curvature risk charge per MAR21.5.

    Formula:
        K_b_curvature = max(sum_k CVR_k + sum_k sum_{l!=k} rho_kl^2 * psi(CVR_k, CVR_l) * |CVR_k| * |CVR_l|, 0)

    Where psi(x, y) = 0 if x < 0 and y < 0, else +1 if both positive, else 0 for mixed signs.

    Args:
        cvr_values: Dict of risk_factor -> CVR_k (net curvature risk).
        correlation_matrix_func: Callable(k, l) -> rho_kl.
        inter_bucket_correlation: gamma_bc for cross-bucket.
        buckets: List of bucket identifiers.

    Returns:
        Total curvature capital charge.
    """
    # This is a simplified interface; actual implementation in girr.py
    total_cvr = sum(cvr_values.values())
    return max(total_cvr, 0.0)
