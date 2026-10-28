"""SA-CCR supervisory parameters and calibration tables.

Contains all regulatory constants, asset-class parameters, and supervisory
factor tables required by the Standardized Approach for Counterparty Credit
Risk (SA-CCR) as written in the March 2026 US ERBA NPR, common rule text
§ __.114 (12 CFR 217.114; ERBA NPR pp. 705-726).  The US text uses
investment-grade / speculative-grade / sub-speculative-grade credit
quality categories (Dodd-Frank § 939A) instead of external ratings.

References
----------
- ERBA NPR § __.114(e): exposure amount, alpha (1.4; 1.0 for commercial
  end-users under § __.114(e)(4))
- ERBA NPR § __.114(f)-(g): replacement cost and PFE multiplier
- ERBA NPR § __.114(h)-(i): hedging-set amounts, adjusted notional,
  supervisory duration, supervisory delta, maturity factor
- ERBA NPR Table 2 to § __.114: supervisory option volatility,
  correlation parameters and supervisory factors
- BCBS d424 CRE52 (international standard, where aligned)
"""

from __future__ import annotations

import math
from enum import Enum
from typing import NamedTuple

# ============================================================================
#  Alpha constants
# ============================================================================

ALPHA_FINANCIAL: float = 1.4
"""Alpha multiplier: exposure amount = 1.4 x (RC + PFE) per ERBA NPR
§ __.114(e)(1)."""

ALPHA_NON_FINANCIAL: float = 1.0
"""Netting sets with a commercial end-user counterparty: exposure amount =
RC + PFE (no 1.4 multiplier) per ERBA NPR § __.114(e)(4)."""

# ============================================================================
#  PFE multiplier floor
# ============================================================================

PFE_FLOOR: float = 0.05
"""Floor for the PFE multiplier per ERBA NPR § __.114(g)(1):
multiplier = min(1; 0.05 + 0.95 * exp((V - C) / (1.9 * A)))."""

PFE_MULTIPLIER_DENOMINATOR_FACTOR: float = 1.9
"""The 1.9 = 2 x (1 - 0.05) factor in the PFE multiplier exponent."""

SUPERVISORY_DURATION_FLOOR: float = 0.04
"""Floor on the supervisory duration (ten business days / 250) per ERBA NPR
§ __.114(i)(2)(i)(A)."""

SUPERVISORY_DISCOUNT_RATE: float = 0.05
"""Discount rate in the supervisory duration formula (§ __.114(i)(2)(i)(A))."""

BUSINESS_DAYS_PER_YEAR: int = 250
"""Business-day convention used throughout § __.114."""

BASIS_HEDGING_SET_SF_MULTIPLIER: float = 0.5
"""Supervisory factor for basis derivative hedging sets = 0.5 x Table 2
(footnote 1 to Table 2 to § __.114)."""

VOLATILITY_HEDGING_SET_SF_MULTIPLIER: float = 5.0
"""Supervisory factor for volatility derivative hedging sets = 5 x Table 2
(footnote 1 to Table 2 to § __.114)."""

CLIENT_FACING_HAIRCUT_SCALING: float = math.sqrt(0.5)
"""Clearing members may scale standard supervisory haircuts on NICA / VM for
client-facing transactions by sqrt(1/2) = 0.707107 (§ __.114(e)(7))."""

# ============================================================================
#  Margin period of risk defaults (business days)
# ============================================================================

MPOR_DEFAULT_DAYS: int = 10
"""MPOR floor for a margined derivative that is not a client-facing
transaction: ten business days plus (re-margining periodicity - 1)
per ERBA NPR § __.114(i)(4)(i)(B)(1)."""

MPOR_CENTRALLY_CLEARED_DAYS: int = 5
"""MPOR floor for client-facing derivative transactions: five business days
plus (re-margining periodicity - 1) per § __.114(i)(4)(i)(B)(2)."""

MPOR_DISPUTE_DAYS: int = 20
"""MPOR floor of twenty business days for netting sets with more than 5,000
non-cleared derivative contracts, illiquid collateral or hard-to-replace
derivatives per § __.114(i)(4)(i)(B)(3)."""

MPOR_LARGE_NETTING_SET_TRADE_COUNT: int = 5_000
"""Trade-count trigger for the twenty-business-day MPOR floor."""

MPOR_DISPUTE_MULTIPLIER: float = 2.0
"""Floors are doubled for netting sets with more than two margin disputes
lasting longer than the MPOR over the previous two quarters
(§ __.114(i)(4)(i)(B)(4))."""

UNMARGINED_MATURITY_FLOOR_DAYS: int = 10
"""Unmargined maturity factor uses M = max(10 business days, remaining
maturity) per § __.114(i)(4)(ii)."""

# ============================================================================
#  Asset class enumeration
# ============================================================================


class SACCRAssetClass(str, Enum):
    """SA-CCR asset classes / categories per Table 2 to § __.114.

    Credit categories follow the US credit-quality taxonomy (investment
    grade, speculative grade, sub-speculative grade) for single names and
    (investment grade, speculative grade) for indices.
    """

    IR = "IR"
    FX = "FX"
    CREDIT_IG = "CREDIT_IG"                  # single-name, investment grade
    CREDIT_SPEC = "CREDIT_SPEC"              # single-name, speculative grade
    CREDIT_SUBSPEC = "CREDIT_SUBSPEC"        # single-name, sub-speculative grade
    CREDIT_INDEX_IG = "CREDIT_INDEX_IG"      # index, investment grade
    CREDIT_INDEX_SPEC = "CREDIT_INDEX_SPEC"  # index, speculative grade
    EQUITY_SINGLE = "EQUITY_SINGLE"
    EQUITY_INDEX = "EQUITY_INDEX"
    COMMODITY_ELEC = "COMMODITY_ELEC"
    COMMODITY_OTHER = "COMMODITY_OTHER"


CREDIT_ASSET_CLASSES: frozenset["SACCRAssetClass"] = frozenset({
    SACCRAssetClass.CREDIT_IG,
    SACCRAssetClass.CREDIT_SPEC,
    SACCRAssetClass.CREDIT_SUBSPEC,
    SACCRAssetClass.CREDIT_INDEX_IG,
    SACCRAssetClass.CREDIT_INDEX_SPEC,
})
"""All credit derivative categories; they form ONE hedging set per netting
set (§ __.114(b) hedging set definition (iii))."""


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
    # Table 2 to § __.114 (ERBA NPR p. 726): credit single-name IG 0.46%,
    # speculative 1.3%, sub-speculative 6.0% (rho 50%); credit index IG
    # 0.38%, speculative 1.06% (rho 80%).
    SACCRAssetClass.CREDIT_IG: AssetClassParams(
        supervisory_factor=0.0046, correlation=0.5
    ),
    SACCRAssetClass.CREDIT_SPEC: AssetClassParams(
        supervisory_factor=0.013, correlation=0.5
    ),
    SACCRAssetClass.CREDIT_SUBSPEC: AssetClassParams(
        supervisory_factor=0.060, correlation=0.5
    ),
    SACCRAssetClass.CREDIT_INDEX_IG: AssetClassParams(
        supervisory_factor=0.0038, correlation=0.8
    ),
    SACCRAssetClass.CREDIT_INDEX_SPEC: AssetClassParams(
        supervisory_factor=0.0106, correlation=0.8
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
    # Table 2 to § __.114 -- supervisory option volatility
    SACCRAssetClass.IR: 0.50,
    SACCRAssetClass.FX: 0.15,
    SACCRAssetClass.CREDIT_IG: 1.00,
    SACCRAssetClass.CREDIT_SPEC: 1.00,
    SACCRAssetClass.CREDIT_SUBSPEC: 1.00,
    SACCRAssetClass.CREDIT_INDEX_IG: 0.80,
    SACCRAssetClass.CREDIT_INDEX_SPEC: 0.80,
    SACCRAssetClass.EQUITY_SINGLE: 1.20,
    SACCRAssetClass.EQUITY_INDEX: 0.75,
    SACCRAssetClass.COMMODITY_ELEC: 1.50,
    SACCRAssetClass.COMMODITY_OTHER: 0.70,
}

# ============================================================================
#  MPOR scaling factor for margined netting sets
# ============================================================================


def mpor_scaling_factor(mpor_days: int) -> float:
    """Maturity factor for a margined derivative per ERBA NPR § __.114(i)(4)(i).

    .. math::

        MF = \\sqrt{\\tfrac{3}{2} \\cdot \\tfrac{MPOR}{250}}

    (The previous implementation used ``1.5 * sqrt(MPOR/250)``, which
    overstates the factor by sqrt(1.5).)

    Parameters
    ----------
    mpor_days : int
        Margin period of risk in business days (after applying the floors
        in § __.114(i)(4)(i)(B)).

    Returns
    -------
    float
        Margined maturity factor.
    """
    return math.sqrt(1.5 * mpor_days / BUSINESS_DAYS_PER_YEAR)


def margined_maturity_factor(mpor_days: int) -> float:
    """Alias of :func:`mpor_scaling_factor` with the NPR's terminology."""
    return mpor_scaling_factor(mpor_days)


def unmargined_maturity_factor(remaining_maturity_years: float) -> float:
    """Maturity factor for an unmargined derivative per § __.114(i)(4)(ii).

    .. math::

        MF = \\sqrt{\\tfrac{\\min(M, 250)}{250}},\\quad
        M = \\max(10\\text{ bd}, \\text{remaining maturity in bd})

    Parameters
    ----------
    remaining_maturity_years : float
        Remaining maturity of the contract in years.

    Returns
    -------
    float
        Unmargined maturity factor in (0, 1].
    """
    maturity_days = max(
        float(UNMARGINED_MATURITY_FLOOR_DAYS),
        remaining_maturity_years * BUSINESS_DAYS_PER_YEAR,
    )
    return math.sqrt(min(maturity_days, BUSINESS_DAYS_PER_YEAR) / BUSINESS_DAYS_PER_YEAR)


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
