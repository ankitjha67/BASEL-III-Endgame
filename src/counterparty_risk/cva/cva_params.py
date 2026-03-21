"""CVA Risk parameters and regulatory constants.

Defines supervisory credit spreads, risk weights, correlation parameters,
and bucket mappings for both BA-CVA and SA-CVA approaches under the
Basel III Endgame framework.

References:
    - BCBS d457 MAR50 (Basic Approach CVA)
    - BCBS d457 MAR51 (Standardized Approach CVA)
    - US Federal Reserve Basel III Endgame Final Rule, Subpart E
"""

from __future__ import annotations

from enum import Enum
from typing import Final

import numpy as np


# =========================================================================
#  CVA Enums
# =========================================================================

class CVAApproach(Enum):
    """CVA calculation approach per MAR50/MAR51."""
    BA_CVA = "BA-CVA"
    SA_CVA = "SA-CVA"


class CVARating(Enum):
    """Credit rating categories for CVA risk per MAR50.3."""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    UNRATED_IG = "UNRATED_IG"
    UNRATED_OTHER = "UNRATED_OTHER"
    UNRATED = "UNRATED"


class CVASector(Enum):
    """Counterparty sector classification for CVA per MAR50.4 / MAR51.6."""
    SOVEREIGN = "SOVEREIGN"
    FINANCIAL = "FINANCIAL"
    CORPORATE = "CORPORATE"
    PUBLIC_SECTOR = "PUBLIC_SECTOR"
    OTHER = "OTHER"


class CVAHedgeType(Enum):
    """Types of eligible CVA hedges per MAR50.7."""
    SINGLE_NAME_CDS = "SINGLE_NAME_CDS"
    INDEX_CDS = "INDEX_CDS"
    CONTINGENT_CDS = "CONTINGENT_CDS"


class SACVARiskFactor(Enum):
    """Risk factor types for SA-CVA per MAR51.2."""
    CREDIT_SPREAD = "CREDIT_SPREAD"
    INTEREST_RATE = "INTEREST_RATE"
    FX = "FX"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"


# =========================================================================
#  BA-CVA Parameters (MAR50)
# =========================================================================

# Supervisory credit spreads by rating in basis points (MAR50.3, Table 1)
CVA_SPREADS_BPS: Final[dict[str, int]] = {
    "AAA": 50,
    "AA": 60,
    "A": 80,
    "BBB": 100,
    "BB": 200,
    "B": 400,
    "CCC": 700,
    "UNRATED_IG": 80,
    "UNRATED_OTHER": 200,
}

# Supervisory correlation parameter (rho) per MAR50.5
BA_CVA_RHO: Final[float] = 0.50

# Hedging proportion parameter (beta) per MAR50.6
# Controls the mix between hedged and unhedged CVA capital
BA_CVA_BETA: Final[float] = 0.25

# Minimum effective maturity floor (1 year per MAR50.4)
MIN_EFFECTIVE_MATURITY: Final[float] = 1.0

# Maximum effective maturity cap (5 years per MAR50.4)
MAX_EFFECTIVE_MATURITY: Final[float] = 5.0

# Discount factor for maturity adjustment per MAR50.4
MATURITY_DISCOUNT_RATE: Final[float] = 0.05

# Supervisory discount factor for EAD conversion
# d_c = (1 - exp(-0.05 * M_c)) / (0.05 * M_c) per MAR50.4
def supervisory_discount_factor(maturity: float) -> float:
    """Compute supervisory discount factor per MAR50.4.

    Args:
        maturity: Effective maturity in years, clipped to [1, 5].

    Returns:
        Discount factor d_c.
    """
    m = np.clip(maturity, MIN_EFFECTIVE_MATURITY, MAX_EFFECTIVE_MATURITY)
    if m <= 0:
        return 1.0
    return float((1.0 - np.exp(-MATURITY_DISCOUNT_RATE * m))
                 / (MATURITY_DISCOUNT_RATE * m))


# =========================================================================
#  SA-CVA Parameters (MAR51)
# =========================================================================

# Supervisory risk weights for SA-CVA counterparty credit spread delta
# per MAR51.5, Table 2
CVA_RISK_WEIGHTS: Final[dict[str, float]] = {
    "AAA": 0.007,
    "AA": 0.007,
    "A": 0.008,
    "BBB": 0.01,
    "BB": 0.02,
    "B": 0.03,
    "CCC": 0.10,
    "UNRATED": 0.015,
}

# Sector risk weight multipliers per MAR51.6
CVA_SECTOR_MULTIPLIERS: Final[dict[str, float]] = {
    "SOVEREIGN": 0.5,
    "FINANCIAL": 1.0,
    "CORPORATE": 1.0,
    "PUBLIC_SECTOR": 0.8,
    "OTHER": 1.0,
}

# Inter-bucket correlation for SA-CVA per MAR51.8
SA_CVA_INTER_BUCKET_CORRELATION: Final[float] = 0.50

# Intra-bucket counterparty correlation for SA-CVA per MAR51.7
SA_CVA_INTRA_BUCKET_CORRELATION: Final[float] = 0.35

# Vega risk weight multiplier per MAR51.10
SA_CVA_VEGA_RISK_WEIGHT: Final[float] = 0.55

# SA-CVA aggregation: correlation across risk types per MAR51.12
SA_CVA_RISK_TYPE_CORRELATION: Final[float] = 0.30

# SA-CVA spread tenor vertices (years) per MAR51.4
SA_CVA_TENOR_VERTICES: Final[list[float]] = [0.5, 1.0, 3.0, 5.0, 10.0]

# SA-CVA tenor correlation parameter per MAR51.4
SA_CVA_TENOR_CORRELATION_BASE: Final[float] = 0.65


# =========================================================================
#  Bucket Definitions for SA-CVA (MAR51.6)
# =========================================================================

# SA-CVA sector buckets and their constituent sectors
SA_CVA_BUCKETS: Final[dict[int, dict[str, str | float]]] = {
    1: {"name": "Sovereigns (IG)", "sector": "SOVEREIGN", "quality": "IG", "rw": 0.005},
    2: {"name": "Sovereigns (HY/NR)", "sector": "SOVEREIGN", "quality": "HY", "rw": 0.02},
    3: {"name": "Financials (IG)", "sector": "FINANCIAL", "quality": "IG", "rw": 0.008},
    4: {"name": "Financials (HY/NR)", "sector": "FINANCIAL", "quality": "HY", "rw": 0.025},
    5: {"name": "Corporates (IG)", "sector": "CORPORATE", "quality": "IG", "rw": 0.01},
    6: {"name": "Corporates (HY/NR)", "sector": "CORPORATE", "quality": "HY", "rw": 0.03},
    7: {"name": "Other (IG)", "sector": "OTHER", "quality": "IG", "rw": 0.012},
    8: {"name": "Other (HY/NR)", "sector": "OTHER", "quality": "HY", "rw": 0.035},
}


# =========================================================================
#  Hedge Eligibility (MAR50.7)
# =========================================================================

# Eligible hedge instruments for BA-CVA
ELIGIBLE_BA_CVA_HEDGES: Final[set[str]] = {
    "SINGLE_NAME_CDS",
    "INDEX_CDS",
    "CONTINGENT_CDS",
}

# Hedge mismatch adjustments per MAR50.8
HEDGE_MATURITY_MISMATCH_FLOOR: Final[float] = 0.0
HEDGE_MATURITY_MISMATCH_CAP: Final[float] = 1.0

# Hedge notional supervisory factor per MAR50.9
HEDGE_SUPERVISORY_FACTOR: Final[float] = 1.0


# =========================================================================
#  Rating Mapping Utilities
# =========================================================================

# Map from generic rating strings to CVA rating categories
RATING_TO_CVA_RATING: Final[dict[str, str]] = {
    "AAA": "AAA",
    "AA+": "AA", "AA": "AA", "AA-": "AA",
    "A+": "A", "A": "A", "A-": "A",
    "BBB+": "BBB", "BBB": "BBB", "BBB-": "BBB",
    "BB+": "BB", "BB": "BB", "BB-": "BB",
    "B+": "B", "B": "B", "B-": "B",
    "CCC+": "CCC", "CCC": "CCC", "CCC-": "CCC",
    "CC": "CCC", "C": "CCC", "D": "CCC",
    "UNRATED_IG": "UNRATED_IG",
    "UNRATED_OTHER": "UNRATED_OTHER",
    "UNRATED": "UNRATED",
    "NR": "UNRATED",
}

# Investment grade ratings
IG_RATINGS: Final[frozenset[str]] = frozenset({"AAA", "AA", "A", "BBB"})


def is_investment_grade(rating: str) -> bool:
    """Check if a rating is investment grade.

    Args:
        rating: Rating string (raw or mapped).

    Returns:
        True if the rating is IG (AAA through BBB).
    """
    mapped = RATING_TO_CVA_RATING.get(rating, rating)
    return mapped in IG_RATINGS


def get_supervisory_spread_bps(rating: str) -> int:
    """Look up supervisory credit spread in basis points per MAR50.3.

    Args:
        rating: Rating string (raw or mapped).

    Returns:
        Supervisory spread in basis points.

    Raises:
        KeyError: If the rating cannot be mapped.
    """
    mapped = RATING_TO_CVA_RATING.get(rating, rating)
    if mapped in CVA_SPREADS_BPS:
        return CVA_SPREADS_BPS[mapped]
    # Fallback for generic UNRATED
    if mapped == "UNRATED":
        return CVA_SPREADS_BPS["UNRATED_OTHER"]
    raise KeyError(f"Unknown CVA rating: {rating!r} (mapped to {mapped!r})")


def get_sa_cva_risk_weight(rating: str) -> float:
    """Look up SA-CVA risk weight per MAR51.5.

    Args:
        rating: Rating string (raw or mapped).

    Returns:
        Risk weight as a decimal (e.g., 0.007 for AAA).

    Raises:
        KeyError: If the rating cannot be mapped.
    """
    mapped = RATING_TO_CVA_RATING.get(rating, rating)
    if mapped in CVA_RISK_WEIGHTS:
        return CVA_RISK_WEIGHTS[mapped]
    # All unrated variants use the UNRATED weight
    if mapped in ("UNRATED_IG", "UNRATED_OTHER", "UNRATED"):
        return CVA_RISK_WEIGHTS["UNRATED"]
    raise KeyError(f"Unknown CVA rating for SA-CVA: {rating!r} (mapped to {mapped!r})")
