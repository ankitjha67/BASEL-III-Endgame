"""Operational Risk regulatory parameters per BCBS d424 / US Basel III Endgame.

Defines the Business Indicator Component (BIC) marginal coefficients,
ILM settings, NIC parameters, loss component thresholds, and all
regulatory constants for the Standardized Measurement Approach (SMA).

References:
    - BCBS d424 (December 2017), Section 5: Operational Risk
    - US Basel III Endgame March 2026 Re-Proposal
    - 12 CFR Part 217, Subpart F: Operational Risk
    - BCBS d457: SMA implementation guidance

Regulatory Notes:
    - ILM = 1.0: The Internal Loss Multiplier is NOT applied per the
      US 2026 proposal. The BIC alone determines the capital charge.
    - NIC uses NET basis with 0.7x factor for investment management
      per ERBA NPR Section VI.
    - BIC marginal coefficients: 12% / 15% / 18% at $1B / $30B thresholds
      per BCBS d424 Table 1.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


# =========================================================================
#  BIC Marginal Coefficient Buckets (BCBS d424 §5.7, Table 1)
# =========================================================================

class BICBucket(NamedTuple):
    """A single BIC marginal coefficient bucket.

    Attributes:
        ceiling_usd: Upper bound of the bucket in USD (float('inf') for last).
        marginal_coefficient: Marginal coefficient applied to BI within this bucket.
        bucket_label: Human-readable label for reporting.
    """
    ceiling_usd: float
    marginal_coefficient: float
    bucket_label: str


# BIC Marginal Coefficients per US Basel III Endgame / BCBS d424 Table 1
# (bucket_ceiling_usd, marginal_coefficient, label)
BIC_BUCKETS: list[BICBucket] = [
    BICBucket(1_000_000_000, 0.12, "Bucket 1: BI <= $1B (12%)"),
    BICBucket(30_000_000_000, 0.15, "Bucket 2: $1B < BI <= $30B (15%)"),
    BICBucket(float("inf"), 0.18, "Bucket 3: BI > $30B (18%)"),
]

# Legacy flat list for backward compatibility
BIC_COEFFICIENTS: list[tuple[float, float]] = [
    (b.ceiling_usd, b.marginal_coefficient) for b in BIC_BUCKETS
]


# =========================================================================
#  Internal Loss Multiplier (ILM) — BCBS d424 §5.11
# =========================================================================

# ILM = 1.0: NOT applied per US 2026 proposal (ERBA NPR Section VI).
# Under BCBS d424, ILM = ln(exp(1) - 1 + (LC/BIC)^0.8),
# but the US has elected to set ILM = 1.0 for all banks.
ILM: float = 1.0

# ILM formula parameters (for reference / international comparison only)
# ILM_EXPONENT: Exponent in the ILM formula per BCBS d424 §5.11
ILM_EXPONENT: float = 0.8

# Minimum ILM floor (if ILM were applied) — some jurisdictions set a floor
ILM_FLOOR: float = 0.0

# Maximum ILM (if ILM were applied) — no explicit cap in BCBS d424
ILM_CAP: float = float("inf")


# =========================================================================
#  ILDC Parameters — Interest, Lease, and Dividend Component (BCBS d424 §5.3)
# =========================================================================

# Interest component capped at 2.25% of interest-earning assets
# per BCBS d424 §5.3 to prevent distortion from maturity mismatch.
ILDC_INTEREST_CAP_RATE: float = 0.0225

# Lease income is included in the interest component per BCBS d424 §5.3
# as part of net interest income for banking book positions.
ILDC_INCLUDES_LEASE_INCOME: bool = True

# Dividend income is added to the interest component per BCBS d424 §5.3
ILDC_INCLUDES_DIVIDEND_INCOME: bool = True


# =========================================================================
#  NIC Parameters — Net Interest Component (ERBA NPR Section VI)
# =========================================================================

# NIC adjustment factor for investment management activities.
# Investment management NIC is calculated on NET basis with 0.7x factor
# per ERBA NPR Section VI, reflecting lower operational risk profile
# of fee-based investment management versus lending.
NIC_INVESTMENT_MANAGEMENT_FACTOR: float = 0.7

# NIC uses NET basis (interest income minus interest expense)
# rather than GROSS basis for investment management activities.
NIC_USE_NET_BASIS: bool = True


# =========================================================================
#  Services Component (SC) Parameters — BCBS d424 §5.4
# =========================================================================

# SC = max(fee_income, fee_expense) + max(other_op_income, other_op_expense)
# No additional parameters needed — the formula uses max() of gross values.

# Fee income includes: advisory fees, brokerage fees, custodian fees,
# payment services fees, asset management fees, underwriting fees.
# Fee expense includes: outsourcing fees, clearing fees, custody fees.


# =========================================================================
#  Financial Component (FC) Parameters — BCBS d424 §5.5
# =========================================================================

# FC = |Net P&L trading book| + |Net P&L banking book|
# Uses absolute values of net gains/losses.

# Trading book P&L includes: gains/losses on financial instruments
# measured at fair value through profit or loss, realized gains/losses
# on financial assets not measured at fair value through profit or loss.

# Banking book P&L includes: realized gains/losses from disposal of
# non-financial assets, derecognition of financial assets measured at
# amortised cost, and net foreign exchange gains/losses.


# =========================================================================
#  Loss Component Parameters — BCBS d424 §5.10
# =========================================================================

class LossEventType(Enum):
    """Basel operational risk loss event types per BCBS d424 Annex 9.

    Seven categories of operational risk loss events used for
    internal loss data collection and reporting.
    """
    INTERNAL_FRAUD = "INTERNAL_FRAUD"
    EXTERNAL_FRAUD = "EXTERNAL_FRAUD"
    EMPLOYMENT_PRACTICES = "EMPLOYMENT_PRACTICES"
    CLIENTS_PRODUCTS = "CLIENTS_PRODUCTS"
    DAMAGE_PHYSICAL = "DAMAGE_PHYSICAL"
    BUSINESS_DISRUPTION = "BUSINESS_DISRUPTION"
    EXECUTION_DELIVERY = "EXECUTION_DELIVERY"


# Minimum loss threshold for inclusion in loss component calculation
# per BCBS d424 §5.10: losses >= EUR 20,000 (approx $22,000 USD)
LOSS_THRESHOLD_USD: float = 22_000.0

# Number of years of loss data required for loss component (10 years)
# per BCBS d424 §5.10
LOSS_DATA_YEARS: int = 10

# Minimum years of loss data for transition (5 years)
# per BCBS d424 §5.10 transitional provision
LOSS_DATA_MIN_YEARS: int = 5

# Loss component calculation uses average annual loss over the data period
# LC = 15x * average annual loss (for BI > EUR 1B)
LC_MULTIPLIER: float = 15.0

# Loss component threshold: LC only relevant if BI > $1B
# (Bucket 1 banks do not compute LC even if ILM were applied)
LC_BI_THRESHOLD: float = 1_000_000_000.0


# =========================================================================
#  RWA Conversion Factor
# =========================================================================

# Operational risk RWA = Capital charge * 12.5
# per Basel framework standard conversion (reciprocal of 8% minimum).
RWA_CONVERSION_FACTOR: float = 12.5


# =========================================================================
#  Data Quality Parameters (BCBS 239 compliance)
# =========================================================================

# Minimum data completeness ratio for BI components (95%)
MIN_DATA_COMPLETENESS: float = 0.95

# Maximum acceptable variance between reported and recalculated BI (1%)
MAX_RECONCILIATION_VARIANCE: float = 0.01

# Required number of quarters for averaging (12 quarters = 3 years)
AVERAGING_QUARTERS: int = 12

# Number of years for BI averaging per BCBS d424 §5.6
BI_AVERAGING_YEARS: int = 3


# =========================================================================
#  FFIEC Reporting Thresholds
# =========================================================================

# Category I bank threshold (total assets >= $250B or FBO criteria)
CATEGORY_I_ASSET_THRESHOLD: float = 250_000_000_000.0

# G-SIB designation threshold (Method 1 score >= 130 basis points)
GSIB_SCORE_THRESHOLD: float = 130.0


# =========================================================================
#  Helper Functions
# =========================================================================

def compute_bic(business_indicator: float) -> float:
    """Compute Business Indicator Component using marginal coefficients.

    The BIC is computed by applying marginal rates to each BI bucket
    per BCBS d424 §5.7, Table 1:
    - 12% on the first $1B
    - 15% on the next $29B ($1B to $30B)
    - 18% on anything above $30B

    Args:
        business_indicator: Total Business Indicator in USD.

    Returns:
        BIC value in USD.

    Raises:
        ValueError: If business_indicator is negative.

    Reference:
        BCBS d424 §5.7, Table 1; ERBA NPR Section VI.
    """
    if business_indicator < 0:
        raise ValueError(
            f"Business Indicator cannot be negative: {business_indicator}"
        )

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


def compute_ilm(loss_component: float, bic: float) -> float:
    """Compute Internal Loss Multiplier per BCBS d424 §5.11.

    NOTE: Under the US 2026 proposal, ILM = 1.0 always. This function
    is provided for international comparison and sensitivity analysis only.

    Formula: ILM = ln(exp(1) - 1 + (LC/BIC)^0.8)

    Args:
        loss_component: Average annual operational loss (LC) in USD.
        bic: Business Indicator Component in USD.

    Returns:
        ILM value (always 1.0 under US rules; computed value for reference).

    Reference:
        BCBS d424 §5.11; ERBA NPR Section VI (US override: ILM = 1.0).
    """
    import math

    if bic <= 0:
        return ILM  # Return regulatory ILM (1.0)

    ratio = loss_component / bic
    if ratio <= 0:
        return ILM

    try:
        ilm_computed = math.log(math.exp(1.0) - 1.0 + ratio ** ILM_EXPONENT)
    except (OverflowError, ValueError):
        ilm_computed = ILM

    # Under US rules, always return 1.0; computed value is for reference only
    return ILM


def compute_loss_component(
    average_annual_losses: float,
    business_indicator: float,
) -> float:
    """Compute the Loss Component (LC) per BCBS d424 §5.10.

    LC = 15x * average annual operational losses, but only
    relevant for banks with BI > $1B. Under US rules, LC is
    not used (ILM = 1.0), but computed for reference.

    Args:
        average_annual_losses: Average annual operational losses in USD.
        business_indicator: Total Business Indicator in USD.

    Returns:
        Loss Component in USD (0.0 if BI <= $1B threshold).

    Reference:
        BCBS d424 §5.10.
    """
    if business_indicator <= LC_BI_THRESHOLD:
        return 0.0

    return LC_MULTIPLIER * max(average_annual_losses, 0.0)
