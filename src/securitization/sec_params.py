"""Securitization framework parameters per BCBS d424 / CRE40.

Defines regulatory constants, risk weight lookup tables, and parameter
enumerations for the SEC-SA, SEC-ERBA, and SEC-IRBA approaches under
the Basel III Endgame framework.

References:
    - BCBS d424 (December 2017), CRE40: Securitisation framework
    - US Basel III Endgame NPR (July 2023, re-proposed Sept 2025)
    - 12 CFR Part 217, Subpart E
    - Dodd-Frank Act Section 939A (constraints on external ratings usage)
"""

from __future__ import annotations

from enum import Enum


# =========================================================================
#  Enumerations
# =========================================================================

class SecApproach(Enum):
    """Securitization capital calculation approaches per CRE40.3-40.5.

    Applied in hierarchical order: SEC-IRBA > SEC-ERBA > SEC-SA.
    US Basel III Endgame primarily uses SEC-SA and SEC-ERBA.
    """
    SEC_IRBA = "SEC-IRBA"
    SEC_ERBA = "SEC-ERBA"
    SEC_SA = "SEC-SA"


class TrancheSeniority(Enum):
    """Tranche seniority classification per CRE40.42."""
    SENIOR = "SENIOR"
    NON_SENIOR = "NON_SENIOR"


class MaturityBucket(Enum):
    """Maturity buckets for SEC-ERBA risk weight lookup per CRE40.43.

    SHORT: residual maturity <= 1 year
    LONG:  residual maturity > 1 year (or up to 5 years, interpolated)
    """
    SHORT = "SHORT"
    LONG = "LONG"


class ExternalRating(Enum):
    """External credit rating categories for SEC-ERBA per CRE40.42."""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    BELOW_CCC = "BELOW_CCC"
    UNRATED = "UNRATED"


class SecPoolAssetType(Enum):
    """Underlying pool asset types for securitization positions."""
    RMBS = "RMBS"
    CMBS = "CMBS"
    CLO = "CLO"
    ABS_AUTO = "ABS_AUTO"
    ABS_CREDIT_CARD = "ABS_CREDIT_CARD"
    ABS_STUDENT_LOAN = "ABS_STUDENT_LOAN"
    ABS_OTHER = "ABS_OTHER"
    CORPORATE = "CORPORATE"
    SOVEREIGN = "SOVEREIGN"
    MIXED = "MIXED"


# =========================================================================
#  SSFA Parameters
# =========================================================================

# Supervisory parameter 'p' for the SSFA formula per CRE40.50
P_NON_RESECURITIZATION: float = 0.5
P_RESECURITIZATION: float = 1.5

# Maximum risk weight (1250% = full deduction) per CRE40.46
MAX_RISK_WEIGHT: float = 12.50

# Minimum risk weight floor per CRE40.44
MIN_RISK_WEIGHT_NON_RESEC: float = 0.15  # 15%
MIN_RISK_WEIGHT_RESEC: float = 1.00  # 100%

# Risk weight floor for senior tranches per CRE40.44
SENIOR_TRANCHE_FLOOR: float = 0.15  # 15%


# =========================================================================
#  SEC-ERBA Risk Weight Tables (CRE40.42, Table CRE40-1)
# =========================================================================

# Mapping: (ExternalRating, TrancheSeniority, MaturityBucket) -> risk_weight
# Risk weights expressed as decimals (e.g., 0.15 = 15%)

SEC_ERBA_RW: dict[tuple[str, str, str], float] = {
    # --- Senior tranches ---
    # AAA
    ("AAA", "SENIOR", "SHORT"): 0.15,
    ("AAA", "SENIOR", "LONG"): 0.20,
    # AA
    ("AA", "SENIOR", "SHORT"): 0.15,
    ("AA", "SENIOR", "LONG"): 0.30,
    # A
    ("A", "SENIOR", "SHORT"): 0.25,
    ("A", "SENIOR", "LONG"): 0.40,
    # BBB
    ("BBB", "SENIOR", "SHORT"): 0.35,
    ("BBB", "SENIOR", "LONG"): 0.60,
    # BB
    ("BB", "SENIOR", "SHORT"): 0.60,
    ("BB", "SENIOR", "LONG"): 0.85,
    # B
    ("B", "SENIOR", "SHORT"): 1.00,
    ("B", "SENIOR", "LONG"): 1.00,
    # CCC
    ("CCC", "SENIOR", "SHORT"): 3.25,
    ("CCC", "SENIOR", "LONG"): 3.25,
    # Below CCC
    ("BELOW_CCC", "SENIOR", "SHORT"): 12.50,
    ("BELOW_CCC", "SENIOR", "LONG"): 12.50,

    # --- Non-senior tranches ---
    # AAA
    ("AAA", "NON_SENIOR", "SHORT"): 0.15,
    ("AAA", "NON_SENIOR", "LONG"): 0.25,
    # AA
    ("AA", "NON_SENIOR", "SHORT"): 0.25,
    ("AA", "NON_SENIOR", "LONG"): 0.40,
    # A
    ("A", "NON_SENIOR", "SHORT"): 0.35,
    ("A", "NON_SENIOR", "LONG"): 0.55,
    # BBB
    ("BBB", "NON_SENIOR", "SHORT"): 0.45,
    ("BBB", "NON_SENIOR", "LONG"): 0.75,
    # BB
    ("BB", "NON_SENIOR", "SHORT"): 0.75,
    ("BB", "NON_SENIOR", "LONG"): 1.20,
    # B
    ("B", "NON_SENIOR", "SHORT"): 1.25,
    ("B", "NON_SENIOR", "LONG"): 1.60,
    # CCC
    ("CCC", "NON_SENIOR", "SHORT"): 3.50,
    ("CCC", "NON_SENIOR", "LONG"): 5.00,
    # Below CCC
    ("BELOW_CCC", "NON_SENIOR", "SHORT"): 12.50,
    ("BELOW_CCC", "NON_SENIOR", "LONG"): 12.50,
}


# =========================================================================
#  SEC-ERBA Maturity Interpolation Anchors
# =========================================================================

# Short-term maturity anchor (years) for interpolation
ERBA_SHORT_MATURITY: float = 1.0

# Long-term maturity anchor (years) for interpolation
ERBA_LONG_MATURITY: float = 5.0


# =========================================================================
#  SEC-IRBA Parameters (for reference / future use)
# =========================================================================

# SEC-IRBA supervisory parameters per CRE40.37
# tau parameter for maturity adjustment
SEC_IRBA_TAU: float = 1000.0

# omega parameter for granularity adjustment
SEC_IRBA_OMEGA: float = 20.0


# =========================================================================
#  Pool-Level Delinquency Thresholds
# =========================================================================

# W parameter (delinquency ratio) thresholds for K_A calculation per CRE40.54
W_THRESHOLD_LOW: float = 0.0
W_THRESHOLD_HIGH: float = 1.0


# =========================================================================
#  Resecuritization Risk Weight Multipliers
# =========================================================================

# ERBA resecuritization multipliers per CRE40.63
RESEC_RW_MULTIPLIER: float = 2.0  # Applied to base ERBA risk weights

# Resecuritization risk weight floor
RESEC_RW_FLOOR: float = 1.00  # 100%


# =========================================================================
#  Concentration Ratio Thresholds
# =========================================================================

# Maximum number of effective obligors below which concentration add-on applies
CONCENTRATION_N_THRESHOLD: int = 6

# Concentration ratio risk weight add-on per CRE40.56
CONCENTRATION_RW_ADDON: float = 0.06  # 6 percentage points per unit
