"""DRC Non-Securitization regulatory parameters per MAR22, BCBS d457.

All risk weights, LGD values, maturity weighting rules, and sector definitions
for the Default Risk Charge under the FRTB framework.

Reference: BCBS d457 MAR22, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

from src.core.enums import (
    DRCExposureType,
    DRCRatingCategory,
    DRCSecRating,
    DRCSecSeniority,
    DRCSeniority,
)


# ---------------------------------------------------------------------------
#  LGD (Loss Given Default) by seniority -- MAR22.12
# ---------------------------------------------------------------------------

LGD_VALUES: dict[DRCSeniority, float] = {
    DRCSeniority.SENIOR_SECURED: 0.25,    # 25%
    DRCSeniority.SENIOR_UNSECURED: 0.75,  # 75%
    DRCSeniority.SUBORDINATED: 0.75,      # 75%
    DRCSeniority.EQUITY: 1.00,            # 100%
}


# ---------------------------------------------------------------------------
#  DRC risk weights by rating -- MAR22.14 Table 2
# ---------------------------------------------------------------------------

DRC_RISK_WEIGHTS: dict[DRCRatingCategory, float] = {
    DRCRatingCategory.AAA: 0.005,       # 0.5%
    DRCRatingCategory.AA: 0.02,         # 2%
    DRCRatingCategory.A: 0.03,          # 3%
    DRCRatingCategory.BBB: 0.06,        # 6%
    DRCRatingCategory.BB: 0.15,         # 15%
    DRCRatingCategory.B: 0.30,          # 30%
    DRCRatingCategory.CCC: 0.50,        # 50%
    DRCRatingCategory.UNRATED: 0.15,    # 15% (same as BB)
    DRCRatingCategory.DEFAULTED: 1.00,  # 100%
}


# ---------------------------------------------------------------------------
#  Maturity weighting constants -- MAR22.13
# ---------------------------------------------------------------------------

MATURITY_CAP_YEARS: float = 1.0
"""Maximum maturity weight is capped at 1.0 (1-year horizon)."""

MATURITY_FLOOR_FRACTION: float = 0.25
"""Maturities below 3 months receive a floor weight of 0.25 (3-month floor)."""

MATURITY_FLOOR_THRESHOLD_YEARS: float = 0.25
"""Threshold below which the maturity floor applies (3 months = 0.25 years)."""


# ---------------------------------------------------------------------------
#  Sector / bucket definitions for DRC non-securitization -- MAR22.15
# ---------------------------------------------------------------------------

DRC_BUCKETS: dict[DRCExposureType, str] = {
    DRCExposureType.CORPORATE: "CORPORATE",
    DRCExposureType.SOVEREIGN: "SOVEREIGN",
    DRCExposureType.LOCAL_GOVERNMENT: "LOCAL_GOVERNMENT",
}

DRC_BUCKET_LABELS: list[str] = [
    "CORPORATE",
    "SOVEREIGN",
    "LOCAL_GOVERNMENT",
]


# ---------------------------------------------------------------------------
#  Sovereign risk weight overrides -- MAR22.14
#
#  Sovereigns rated AA- or higher receive reduced risk weights relative
#  to corporates.  The values below reflect the MAR22 Table 2 sovereign
#  adjustments.
# ---------------------------------------------------------------------------

SOVEREIGN_RISK_WEIGHT_OVERRIDES: dict[DRCRatingCategory, float] = {
    DRCRatingCategory.AAA: 0.005,    # 0.5%  (no change)
    DRCRatingCategory.AA: 0.02,      # 2%    (no change)
    DRCRatingCategory.A: 0.03,       # 3%
    DRCRatingCategory.BBB: 0.06,     # 6%
    DRCRatingCategory.BB: 0.15,      # 15%
    DRCRatingCategory.B: 0.30,       # 30%
    DRCRatingCategory.CCC: 0.50,     # 50%
    DRCRatingCategory.UNRATED: 0.15, # 15%
    DRCRatingCategory.DEFAULTED: 1.00,
}


# =========================================================================
#  Helper functions
# =========================================================================


def get_lgd(seniority: DRCSeniority) -> float:
    """Return the LGD fraction for a given seniority level.

    Args:
        seniority: Bond/instrument seniority classification.

    Returns:
        LGD as a decimal (e.g. 0.75 for 75%).

    Raises:
        KeyError: If the seniority is not recognised.
    """
    return LGD_VALUES[seniority]


def get_risk_weight(
    rating: DRCRatingCategory,
    exposure_type: DRCExposureType = DRCExposureType.CORPORATE,
) -> float:
    """Return the DRC risk weight for a given rating and exposure type.

    For sovereigns the regulatory framework specifies the same table as
    corporates in the base calibration; if future recalibrations diverge,
    :data:`SOVEREIGN_RISK_WEIGHT_OVERRIDES` will hold the sovereign-specific
    values.

    Args:
        rating: External rating category.
        exposure_type: Type of exposure (corporate, sovereign, etc.).

    Returns:
        Risk weight as a decimal (e.g. 0.03 for 3%).

    Raises:
        KeyError: If the rating is not recognised.
    """
    if exposure_type == DRCExposureType.SOVEREIGN:
        return SOVEREIGN_RISK_WEIGHT_OVERRIDES[rating]
    return DRC_RISK_WEIGHTS[rating]


def compute_maturity_weight(maturity_years: float) -> float:
    """Compute the maturity-based scaling factor for a JTD amount.

    Per MAR22.13 the maturity weight scales linearly from 0 to 1 over
    a 1-year horizon:

    .. math::

        w = \\min\\!\\left(\\frac{M}{1},\\; 1\\right)

    with a floor of 0.25 for maturities shorter than 3 months.

    Args:
        maturity_years: Remaining maturity of the instrument in years.
            Must be non-negative.

    Returns:
        Maturity weight in the range [0.25, 1.0].
    """
    if maturity_years <= 0.0:
        return MATURITY_FLOOR_FRACTION

    raw = min(maturity_years / MATURITY_CAP_YEARS, 1.0)

    # Apply 3-month floor
    return max(raw, MATURITY_FLOOR_FRACTION)


def get_bucket_label(exposure_type: DRCExposureType) -> str:
    """Map an exposure type to its DRC bucket label.

    Args:
        exposure_type: The exposure classification.

    Returns:
        Human-readable bucket label string.

    Raises:
        KeyError: If the exposure type has no DRC bucket mapping
            (e.g. ``SECURITIZATION`` which is handled separately).
    """
    return DRC_BUCKETS[exposure_type]


# =========================================================================
#  DRC Securitization Parameters -- MAR22.24-22.46
# =========================================================================

# ---------------------------------------------------------------------------
#  DRC Securitization risk weights by rating and seniority -- MAR22.25 Table 5
# ---------------------------------------------------------------------------

DRC_SEC_RISK_WEIGHTS_SENIOR: dict[DRCSecRating, float] = {
    DRCSecRating.AAA: 0.004,        # 0.4%
    DRCSecRating.AA: 0.008,         # 0.8%
    DRCSecRating.A: 0.016,          # 1.6%
    DRCSecRating.BBB: 0.048,        # 4.8%
    DRCSecRating.BB: 0.08,          # 8.0%
    DRCSecRating.B: 0.16,           # 16.0%
    DRCSecRating.CCC: 0.32,         # 32.0%
    DRCSecRating.UNRATED: 1.0,      # 100%
    DRCSecRating.DEFAULTED: 1.0,    # 100%
}

DRC_SEC_RISK_WEIGHTS_NON_SENIOR: dict[DRCSecRating, float] = {
    DRCSecRating.AAA: 0.01,         # 1.0%
    DRCSecRating.AA: 0.02,          # 2.0%
    DRCSecRating.A: 0.04,           # 4.0%
    DRCSecRating.BBB: 0.08,         # 8.0%
    DRCSecRating.BB: 0.16,          # 16.0%
    DRCSecRating.B: 0.32,           # 32.0%
    DRCSecRating.CCC: 0.64,         # 64.0%
    DRCSecRating.UNRATED: 1.0,      # 100%
    DRCSecRating.DEFAULTED: 1.0,    # 100%
}


# ---------------------------------------------------------------------------
#  DRC Securitization LGD -- MAR22.26
#
#  LGD = 100% for all securitization positions (no recovery assumption).
# ---------------------------------------------------------------------------

DRC_SEC_LGD: float = 1.0
"""LGD for securitization positions is 100% per MAR22.26."""


# ---------------------------------------------------------------------------
#  CTP hedge benefit ratio -- MAR22.41
# ---------------------------------------------------------------------------

CTP_HEDGE_BENEFIT_RATIO: float = 0.5
"""50% recognition of hedges within CTP buckets per MAR22.41."""


def get_sec_risk_weight(
    rating: DRCSecRating,
    seniority: DRCSecSeniority,
) -> float:
    """Return the DRC securitization risk weight for a given rating and seniority.

    Per MAR22.25 Table 5, risk weights depend on both the external rating
    category and whether the tranche is senior or non-senior.

    Args:
        rating: External rating category of the securitization tranche.
        seniority: Whether the tranche is senior or non-senior.

    Returns:
        Risk weight as a decimal (e.g. 0.004 for 0.4%).

    Raises:
        KeyError: If the rating is not recognised.
    """
    if seniority == DRCSecSeniority.SENIOR:
        return DRC_SEC_RISK_WEIGHTS_SENIOR[rating]
    return DRC_SEC_RISK_WEIGHTS_NON_SENIOR[rating]
