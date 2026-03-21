"""Operational Risk regulatory parameters per BCBS d424 / US Basel III Endgame.

Defines the Business Indicator Component (BIC) marginal coefficients
and ILM settings for the Standardized Measurement Approach (SMA).
"""

from __future__ import annotations

# BIC Marginal Coefficients per US Basel III Endgame
# (bucket_ceiling_usd, marginal_coefficient)
BIC_COEFFICIENTS: list[tuple[float, float]] = [
    (1_000_000_000, 0.12),      # 12% for BI <= $1B
    (30_000_000_000, 0.15),     # 15% for $1B < BI <= $30B
    (float("inf"), 0.18),       # 18% for BI > $30B
]

# Internal Loss Multiplier — NOT applied per US 2026 proposal
ILM: float = 1.0

# ILDC cap: interest component capped at 2.25% of interest-earning assets
ILDC_INTEREST_CAP_RATE: float = 0.0225

# NIC adjustment for investment management
NIC_INVESTMENT_MANAGEMENT_FACTOR: float = 0.7


def compute_bic(business_indicator: float) -> float:
    """Compute Business Indicator Component using marginal coefficients.

    The BIC is computed by applying marginal rates to each BI bucket:
    - 12% on the first $1B
    - 15% on the next $29B ($1B to $30B)
    - 18% on anything above $30B

    Args:
        business_indicator: Total Business Indicator in USD.

    Returns:
        BIC value in USD.
    """
    bic = 0.0
    remaining = business_indicator
    prev_ceiling = 0.0

    for ceiling, coefficient in BIC_COEFFICIENTS:
        bucket_size = min(remaining, ceiling - prev_ceiling)
        if bucket_size <= 0:
            break
        bic += bucket_size * coefficient
        remaining -= bucket_size
        prev_ceiling = ceiling

    return bic
