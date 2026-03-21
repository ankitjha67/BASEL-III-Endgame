"""SA-CCR supervisory parameters and calibration tables.

Contains all regulatory constants, asset-class parameters, and supervisory
factor tables required by the Standardized Approach for Counterparty Credit
Risk (SA-CCR) per CRE52.

References
----------
- CRE52.40-52.72: Add-on calculation and supervisory parameters
- CRE52.30: Alpha multiplier
- CRE52.33-52.36: Replacement cost formulas
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

# ============================================================================
#  Alpha constants
# ============================================================================

ALPHA_FINANCIAL: float = 1.4
"""Alpha multiplier for financial counterparties per CRE52.30."""

ALPHA_NON_FINANCIAL: float = 1.0
"""Alpha multiplier for commercial end-users (2026 rule)."""

# ============================================================================
#  PFE multiplier floor
# ============================================================================

PFE_FLOOR: float = 0.05
"""Floor for the PFE multiplier per CRE52.41."""

# ============================================================================
#  Margin period of risk defaults (business days)
# ============================================================================

MPOR_DEFAULT_DAYS: int = 10
"""Default margin period of risk for bilateral margined netting sets."""

MPOR_CENTRALLY_CLEARED_DAYS: int = 5
"""MPOR for centrally cleared transactions."""

MPOR_DISPUTE_DAYS: int = 20
"""MPOR where disputes exceed threshold per CRE52.36."""

# ============================================================================
#  Asset class enumeration
# ============================================================================


class SACCRAssetClass(str, Enum):
    """SA-CCR asset classes per CRE52.40."""

    IR = "IR"
    FX = "FX"
    CREDIT_IG = "CREDIT_IG"
    CREDIT_SPEC = "CREDIT_SPEC"
    EQUITY_SINGLE = "EQUITY_SINGLE"
    EQUITY_INDEX = "EQUITY_INDEX"
    COMMODITY_ELEC = "COMMODITY_ELEC"
    COMMODITY_OTHER = "COMMODITY_OTHER"


# ============================================================================
#  Supervisory parameters per asset class
# ============================================================================


class AssetClassParams(NamedTuple):
    """Supervisory parameters for one SA-CCR asset class.

    Attributes
    ----------
    supervisory_factor : float
        SF_i — scales the effective notional to produce the add-on.
    correlation : float
        rho_i — within-hedging-set correlation used to separate the
        systematic and idiosyncratic components.
    """

    supervisory_factor: float
    correlation: float


SACCR_ASSET_CLASS_PARAMS: dict[SACCRAssetClass, AssetClassParams] = {
    SACCRAssetClass.IR: AssetClassParams(
        supervisory_factor=0.005, correlation=1.0
    ),
    SACCRAssetClass.FX: AssetClassParams(
        supervisory_factor=0.04, correlation=1.0
    ),
    SACCRAssetClass.CREDIT_IG: AssetClassParams(
        supervisory_factor=0.0038, correlation=0.8
    ),
    SACCRAssetClass.CREDIT_SPEC: AssetClassParams(
        supervisory_factor=0.0054, correlation=0.8
    ),
    SACCRAssetClass.EQUITY_SINGLE: AssetClassParams(
        supervisory_factor=0.32, correlation=0.5
    ),
    SACCRAssetClass.EQUITY_INDEX: AssetClassParams(
        supervisory_factor=0.20, correlation=0.8
    ),
    SACCRAssetClass.COMMODITY_ELEC: AssetClassParams(
        supervisory_factor=0.40, correlation=0.4
    ),
    SACCRAssetClass.COMMODITY_OTHER: AssetClassParams(
        supervisory_factor=0.18, correlation=0.4
    ),
}

# Convenience dict matching the spec format
SACCR_ASSET_CLASSES: dict[str, dict[str, float]] = {
    ac.value: {
        "supervisory_factor": p.supervisory_factor,
        "correlation": p.correlation,
    }
    for ac, p in SACCR_ASSET_CLASS_PARAMS.items()
}

# ============================================================================
#  Interest-rate maturity buckets for hedging sets
# ============================================================================


class IRMaturityBucket(str, Enum):
    """IR hedging-set maturity buckets per CRE52.48."""

    BUCKET_1 = "<=1Y"
    BUCKET_2 = "1Y-5Y"
    BUCKET_3 = ">5Y"


def ir_maturity_bucket(end_years: float) -> IRMaturityBucket:
    """Assign an IR trade to its maturity bucket.

    Parameters
    ----------
    end_years : float
        End date of the trade in years from today.

    Returns
    -------
    IRMaturityBucket
    """
    if end_years <= 1.0:
        return IRMaturityBucket.BUCKET_1
    if end_years <= 5.0:
        return IRMaturityBucket.BUCKET_2
    return IRMaturityBucket.BUCKET_3


# ============================================================================
#  Supervisory option volatilities (for option delta)
# ============================================================================

SUPERVISORY_OPTION_VOLATILITY: dict[SACCRAssetClass, float] = {
    SACCRAssetClass.IR: 0.50,
    SACCRAssetClass.FX: 0.15,
    SACCRAssetClass.CREDIT_IG: 1.00,
    SACCRAssetClass.CREDIT_SPEC: 1.00,
    SACCRAssetClass.EQUITY_SINGLE: 1.20,
    SACCRAssetClass.EQUITY_INDEX: 0.75,
    SACCRAssetClass.COMMODITY_ELEC: 1.50,
    SACCRAssetClass.COMMODITY_OTHER: 0.70,
}

# ============================================================================
#  MPOR scaling factor for margined netting sets
# ============================================================================


def mpor_scaling_factor(mpor_days: int) -> float:
    """Compute the MPOR scaling factor applied to supervisory duration.

    The factor is sqrt(MPOR / 250) normalised against a 1-year reference.
    Per CRE52.52, the factor is:
        1.5 * sqrt(MPOR / 250)

    Parameters
    ----------
    mpor_days : int
        Margin period of risk in business days.

    Returns
    -------
    float
        Scaling factor.
    """
    import numpy as np

    return float(1.5 * np.sqrt(mpor_days / 250.0))


# ============================================================================
#  Netting set categories
# ============================================================================


class NettingSetCategory(str, Enum):
    """Margining status of a netting set."""

    UNMARGINED = "unmargined"
    MARGINED = "margined"


# ============================================================================
#  Commodity sub-class hedging set types
# ============================================================================


class CommodityHedgingSet(str, Enum):
    """Commodity hedging-set types per CRE52.56."""

    ENERGY = "energy"
    METALS = "metals"
    AGRICULTURAL = "agricultural"
    OTHER = "other"
    ELECTRICITY = "electricity"


def commodity_hedging_set(asset_class: SACCRAssetClass) -> CommodityHedgingSet:
    """Map asset class to commodity hedging set.

    Parameters
    ----------
    asset_class : SACCRAssetClass

    Returns
    -------
    CommodityHedgingSet
    """
    if asset_class == SACCRAssetClass.COMMODITY_ELEC:
        return CommodityHedgingSet.ELECTRICITY
    return CommodityHedgingSet.OTHER
