"""Capital adequacy regulatory parameters per US Basel III Endgame 2026.

Defines minimum capital ratios, buffer requirements, G-SIB surcharge
parameters, leverage ratio thresholds, and all related regulatory
constants used in the capital aggregation engine.

References:
- ERBA NPR pp. 34-42: Minimum capital requirements
- ERBA NPR pp. 43-58: Capital buffers (CCB, CCyB, G-SIB)
- ERBA NPR pp. 59-68: Supplementary Leverage Ratio
- G-SIB NPR pp. 12-28: G-SIB surcharge methodology
- 12 CFR 217 Subpart H: Enhanced prudential standards
- FR Y-9C Schedule HC-R: Regulatory capital line items

All monetary amounts in USD millions ($M) unless otherwise stated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =========================================================================
#  Minimum Capital Ratios
#  Reference: 12 CFR 217.10, ERBA NPR p. 34
# =========================================================================

# Risk-based capital ratios (as fraction of RWA)
CET1_MINIMUM_RATIO: float = 0.045
"""CET1 minimum: 4.5% of RWA per 12 CFR 217.10(a)(1)."""

TIER1_MINIMUM_RATIO: float = 0.06
"""Tier 1 minimum: 6.0% of RWA per 12 CFR 217.10(a)(2)."""

TOTAL_CAPITAL_MINIMUM_RATIO: float = 0.08
"""Total capital minimum: 8.0% of RWA per 12 CFR 217.10(a)(3)."""


# =========================================================================
#  Capital Conservation Buffer (CCB)
#  Reference: 12 CFR 217.11(a)(4), ERBA NPR pp. 43-45
# =========================================================================

CCB_RATE: float = 0.025
"""Capital conservation buffer: 2.5% of RWA, composed of CET1.
Per 12 CFR 217.11(a)(4), fully phased-in since January 1, 2019."""


# =========================================================================
#  Countercyclical Capital Buffer (CCyB)
#  Reference: 12 CFR 217.11(b), ERBA NPR pp. 46-48
# =========================================================================

CCYB_DEFAULT_RATE: float = 0.0
"""Default CCyB rate: 0% when not activated.
Per 12 CFR 217.11(b), the CCyB can range from 0% to 2.5%
and is activated by the Fed based on macro-financial conditions.
As of March 2026, the US CCyB is 0%."""

CCYB_MAXIMUM_RATE: float = 0.025
"""Maximum CCyB rate: 2.5% of RWA per 12 CFR 217.11(b)(2)."""


# =========================================================================
#  G-SIB Surcharge
#  Reference: G-SIB NPR pp. 12-28, 12 CFR 217.403-404
#  US 2026 re-proposal: 20bp score ranges / 0.1% surcharge increments
#  (NOT 100bp/0.5% from original Basel standard)
# =========================================================================

class GSIBMethod(Enum):
    """G-SIB surcharge calculation methods per 12 CFR 217.403."""
    METHOD_1 = "METHOD_1"  # Coefficient-based (BCBS methodology)
    METHOD_2 = "METHOD_2"  # Short-term wholesale funding substitution


# G-SIB surcharge bands per US 2026 re-proposal
# Score range: 20bp increments; surcharge: 0.1% increments
# Reference: G-SIB NPR pp. 18-22
GSIB_SCORE_INCREMENT: float = 0.0020
"""G-SIB score band width: 20bp (0.20%) per US 2026 re-proposal.
Note: Original Basel uses 100bp bands."""

GSIB_SURCHARGE_INCREMENT: float = 0.001
"""G-SIB surcharge increment: 0.1% per band per US 2026 re-proposal.
Note: Original Basel uses 0.5% increments."""

GSIB_BASE_SCORE_THRESHOLD: float = 0.0130
"""Score threshold above which G-SIB surcharge applies: 130bp.
Reference: 12 CFR 217.403(b)."""

GSIB_METHOD2_DOWNWARD_FACTOR: float = 1.0 / 1.2
"""Method 2 coefficients adjusted by 1.2x downward factor per US 2026
re-proposal. Effective multiplier = 1/1.2 = 0.8333.
Reference: G-SIB NPR p. 24."""


@dataclass(frozen=True)
class GSIBSurchargeBand:
    """A single G-SIB surcharge band.

    Attributes:
        score_lower: Lower bound of score band (inclusive).
        score_upper: Upper bound of score band (exclusive).
        surcharge: Applicable surcharge rate.
    """
    score_lower: float
    score_upper: float
    surcharge: float


def build_gsib_surcharge_schedule(
    num_bands: int = 50,
    base_threshold: float = GSIB_BASE_SCORE_THRESHOLD,
    score_increment: float = GSIB_SCORE_INCREMENT,
    surcharge_increment: float = GSIB_SURCHARGE_INCREMENT,
) -> list[GSIBSurchargeBand]:
    """Build the G-SIB surcharge lookup table.

    Generates surcharge bands using 20bp score ranges and 0.1% surcharge
    increments per the US 2026 re-proposal (G-SIB NPR pp. 18-22).

    Args:
        num_bands: Number of surcharge bands to generate.
        base_threshold: Score threshold for first band.
        score_increment: Width of each score band (20bp default).
        surcharge_increment: Surcharge step per band (0.1% default).

    Returns:
        List of GSIBSurchargeBand from lowest to highest.

    Example:
        Band 1: score 130-150bp -> 1.0% surcharge
        Band 2: score 150-170bp -> 1.1% surcharge
        ...
    """
    bands: list[GSIBSurchargeBand] = []
    for i in range(num_bands):
        lower = base_threshold + i * score_increment
        upper = lower + score_increment
        surcharge = 0.010 + i * surcharge_increment  # Start at 1.0%
        bands.append(GSIBSurchargeBand(
            score_lower=lower,
            score_upper=upper,
            surcharge=surcharge,
        ))
    return bands


def lookup_gsib_surcharge(
    score: float,
    schedule: Optional[list[GSIBSurchargeBand]] = None,
) -> float:
    """Look up G-SIB surcharge for a given systemic importance score.

    Per 12 CFR 217.403, the surcharge is determined by the band in which
    the institution's G-SIB score falls. Scores below the base threshold
    receive no surcharge.

    Args:
        score: G-SIB systemic importance score (as decimal, e.g. 0.0200 = 200bp).
        schedule: Optional pre-built schedule; built if None.

    Returns:
        G-SIB surcharge rate (as decimal, e.g. 0.015 = 1.5%).
    """
    if score < GSIB_BASE_SCORE_THRESHOLD:
        return 0.0

    if schedule is None:
        schedule = build_gsib_surcharge_schedule()

    # Find applicable band
    for band in reversed(schedule):
        if score >= band.score_lower:
            return band.surcharge

    return 0.0


# =========================================================================
#  G-SIB Method 1 Indicator Categories
#  Reference: FR Y-15, 12 CFR 217.404
# =========================================================================

GSIB_METHOD1_CATEGORIES: dict[str, float] = {
    "size": 0.20,
    "interconnectedness": 0.20,
    "substitutability": 0.20,
    "complexity": 0.20,
    "cross_jurisdictional_activity": 0.20,
}
"""Method 1 category weights — equal 20% each per BCBS methodology.
Reference: 12 CFR 217.404(b)."""


# =========================================================================
#  Supplementary Leverage Ratio (SLR)
#  Reference: 12 CFR 217.10(a)(4)-(5), ERBA NPR pp. 59-68
# =========================================================================

SLR_MINIMUM: float = 0.03
"""SLR minimum: 3.0% for all banking organizations.
Reference: 12 CFR 217.10(a)(4)."""

SLR_ENHANCED_BUFFER: float = 0.02
"""Enhanced SLR buffer: 2.0% for Category I G-SIBs.
Total eSLR = 3% + 2% = 5%. Reference: 12 CFR 217.11(d)(4).
Note: Buffer = 50% of the highest applicable G-SIB surcharge.
For a G-SIB with 4.0% surcharge, eSLR buffer = 2.0%."""

ESLR_TOTAL_CATEGORY_I: float = SLR_MINIMUM + SLR_ENHANCED_BUFFER
"""Total enhanced SLR for Category I G-SIBs: 5.0%.
Reference: 12 CFR 217.11(d)(4)."""


# =========================================================================
#  Leverage Ratio Denominator Components
#  Reference: 12 CFR 217.10(c), ERBA NPR pp. 62-65
# =========================================================================

SACCR_ALPHA_FINANCIAL: float = 1.4
"""SA-CCR alpha factor for financial counterparties.
Reference: ERBA NPR p. 287, 12 CFR 217.132(c)(5)(i)."""

SACCR_ALPHA_COMMERCIAL: float = 1.0
"""SA-CCR alpha factor for commercial end-users.
Reference: ERBA NPR p. 287, 12 CFR 217.132(c)(5)(ii)."""


# =========================================================================
#  Capital Deductions and Thresholds
#  Reference: 12 CFR 217.22, ERBA NPR pp. 70-85
# =========================================================================

# Goodwill deduction — full deduction from CET1
# Reference: 12 CFR 217.22(a)(1)
GOODWILL_DEDUCTION_RATE: float = 1.0
"""Goodwill is fully deducted from CET1 per 12 CFR 217.22(a)(1)."""

# DTA deduction thresholds
# Reference: 12 CFR 217.22(a)(3)-(4)
DTA_THRESHOLD_PERCENT: float = 0.10
"""DTAs from timing differences that exceed 10% of CET1 are deducted.
Reference: 12 CFR 217.22(d)(1)(ii)."""

DTA_AGGREGATE_THRESHOLD: float = 0.15
"""Aggregate 15% threshold for combined significant investments + DTAs.
Items exceeding 15% of CET1 are deducted. Reference: 12 CFR 217.22(d)(2)."""

# Risk weight for items below thresholds
DTA_BELOW_THRESHOLD_RW: float = 2.50
"""DTAs below the threshold receive 250% risk weight.
Reference: 12 CFR 217.22(d)(4)."""

# MSA — NOT deducted under US 2026 re-proposal
# Instead receives 250% risk weight
# Reference: ERBA NPR p. 78
MSA_RISK_WEIGHT: float = 2.50
"""Mortgage Servicing Assets: 250% risk weight (NOT deducted).
US 2026 re-proposal REMOVED the MSA deduction — applies 250% RW instead.
Reference: ERBA NPR p. 78, 12 CFR 217.22(d)(1)(iii)."""

MSA_INDIVIDUAL_THRESHOLD: float = 0.10
"""MSA individual threshold: 10% of CET1.
Amounts exceeding this threshold are deducted from CET1.
Reference: 12 CFR 217.22(d)(1)(iii)."""

# Significant investments in unconsolidated financial institutions
SIGNIFICANT_INVESTMENT_THRESHOLD: float = 0.10
"""Significant investments threshold: 10% of CET1.
Reference: 12 CFR 217.22(d)(1)(i)."""

SIGNIFICANT_INVESTMENT_BELOW_THRESHOLD_RW: float = 2.50
"""Significant investments below threshold: 250% risk weight.
Reference: 12 CFR 217.22(d)(4)."""


# =========================================================================
#  AT1 and Tier 2 Parameters
#  Reference: 12 CFR 217.20-21, ERBA NPR pp. 86-92
# =========================================================================

AT1_MINORITY_INTEREST_INCLUSION_LIMIT: float = 0.10
"""Minority interest in AT1 capped at 10% of parent AT1.
Reference: 12 CFR 217.21(b)."""

TIER2_AMORTIZATION_SCHEDULE_YEARS: int = 5
"""Tier 2 instruments amortize over last 5 years of maturity.
20% per year straight-line amortization.
Reference: 12 CFR 217.20(d)(1)(iv)."""

TIER2_ALLOWANCE_CAP_SA: float = 0.0125
"""General allowance for credit losses capped at 1.25% of SA RWA.
Reference: 12 CFR 217.20(d)(3)."""


# =========================================================================
#  Output Floor
#  Reference: ERBA NPR pp. 95-98
#  NOTE: NOT applied per US 2026 re-proposal
# =========================================================================

OUTPUT_FLOOR_RATE: float = 0.725
"""Output floor: 72.5% of standardized RWA.
IMPORTANT: This is NOT applied in the US 2026 re-proposal.
Calculated for reference/comparison only.
Reference: BCBS d424 para 60, ERBA NPR p. 95."""

OUTPUT_FLOOR_APPLIED: bool = False
"""Flag indicating output floor is NOT applied per US proposal.
Reference: ERBA NPR p. 95."""


# =========================================================================
#  FRTB Threshold
#  Reference: ERBA NPR p. 312
# =========================================================================

FRTB_TRADING_THRESHOLD: float = 5_000.0
"""FRTB threshold: $5B (expressed as $5,000M) trading activity.
4-quarter average. NOT $1B from the 2023 NPR.
Reference: ERBA NPR p. 312."""


# =========================================================================
#  Stress Capital Buffer (SCB)
#  Reference: 12 CFR 217.11(a)(2)(iv)
# =========================================================================

SCB_FLOOR: float = 0.025
"""Stress Capital Buffer floor: 2.5% of RWA.
The SCB replaces the CCB for Category I-IV firms.
Reference: 12 CFR 217.11(a)(2)(iv)."""


# =========================================================================
#  Well-Capitalized Thresholds (PCA)
#  Reference: 12 CFR 6.4 (OCC), 12 CFR 208.43 (Fed)
# =========================================================================

@dataclass(frozen=True)
class PCAThresholds:
    """Prompt Corrective Action thresholds per 12 CFR 6.4.

    Used to classify banking organizations into PCA categories:
    well-capitalized, adequately capitalized, undercapitalized, etc.
    """
    cet1_ratio: float
    tier1_ratio: float
    total_capital_ratio: float
    leverage_ratio: float


PCA_WELL_CAPITALIZED = PCAThresholds(
    cet1_ratio=0.065,
    tier1_ratio=0.08,
    total_capital_ratio=0.10,
    leverage_ratio=0.05,
)
"""Well-capitalized thresholds per 12 CFR 6.4(b)(1)."""

PCA_ADEQUATELY_CAPITALIZED = PCAThresholds(
    cet1_ratio=0.045,
    tier1_ratio=0.06,
    total_capital_ratio=0.08,
    leverage_ratio=0.04,
)
"""Adequately capitalized thresholds per 12 CFR 6.4(b)(2)."""

PCA_UNDERCAPITALIZED = PCAThresholds(
    cet1_ratio=0.045,
    tier1_ratio=0.06,
    total_capital_ratio=0.08,
    leverage_ratio=0.04,
)
"""Undercapitalized: fails to meet any adequately-capitalized threshold.
Reference: 12 CFR 6.4(b)(3)."""


# =========================================================================
#  Capital Quality Limits
#  Reference: 12 CFR 217.20, ERBA NPR p. 87
# =========================================================================

AT1_CET1_COMPOSITION: float = 1.5 / 6.0
"""AT1 can comprise at most 1.5% out of the 6% Tier 1 minimum.
The remainder (4.5%) must be CET1. Reference: 12 CFR 217.10(a)."""

TIER2_TOTAL_COMPOSITION: float = 2.0 / 8.0
"""Tier 2 can comprise at most 2% out of the 8% Total Capital minimum.
The remainder (6%) must be Tier 1. Reference: 12 CFR 217.10(a)."""


# =========================================================================
#  Typical G-SIB Reference Values (for validation)
#  These are NOT regulatory parameters — used for integration test bounds
# =========================================================================

TYPICAL_GSIB_CET1_RATIO_RANGE: tuple[float, float] = (0.10, 0.15)
"""Expected CET1 ratio range for a large Category I G-SIB: 10-15%."""

TYPICAL_GSIB_SLR_RANGE: tuple[float, float] = (0.05, 0.07)
"""Expected SLR range for a large Category I G-SIB: 5-7%."""

TYPICAL_GSIB_TOTAL_CAPITAL_RANGE: tuple[float, float] = (0.13, 0.18)
"""Expected Total Capital ratio range for a large Category I G-SIB: 13-18%."""
