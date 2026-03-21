"""Securitization framework parameters per BCBS d424 / CRE40.

Defines regulatory constants, risk weight lookup tables, and parameter
enumerations for the SEC-SA, SEC-ERBA, and SEC-IRBA approaches under
the Basel III Endgame framework.

References:
    - BCBS d424 (December 2017), CRE40: Securitisation framework
    - US Basel III Endgame NPR (July 2023, re-proposed March 2026)
    - 12 CFR Part 217, Subpart E
    - Dodd-Frank Act Section 939A (constraints on external ratings usage)
    - ERBA NPR Tables 2-5: SEC-ERBA risk weights
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


# =========================================================================
#  Enumerations
# =========================================================================

class SecApproach(Enum):
    """Securitization capital calculation approaches per CRE40.3-40.5.

    Applied in hierarchical order: SEC-IRBA > SEC-ERBA > SEC-SA.
    US Basel III Endgame primarily uses SEC-SA and SEC-ERBA.
    Dodd-Frank §939A limits use of external ratings for SEC-ERBA.

    Reference:
        CRE40.3-40.5; 12 CFR Part 217, Subpart E.
    """
    SEC_IRBA = "SEC-IRBA"
    SEC_ERBA = "SEC-ERBA"
    SEC_SA = "SEC-SA"


class TrancheSeniority(Enum):
    """Tranche seniority classification per CRE40.42.

    Seniority affects risk weight lookup in the SEC-ERBA table.
    Senior tranches receive lower risk weights.

    Reference:
        CRE40.42; ERBA NPR Tables 2-3.
    """
    SENIOR = "SENIOR"
    NON_SENIOR = "NON_SENIOR"


class MaturityBucket(Enum):
    """Maturity buckets for SEC-ERBA risk weight lookup per CRE40.43.

    SHORT: residual maturity <= 1 year
    LONG:  residual maturity > 1 year (or up to 5 years, interpolated)

    Reference:
        CRE40.43; ERBA NPR Tables 2-3.
    """
    SHORT = "SHORT"
    LONG = "LONG"


class ExternalRating(Enum):
    """External credit rating categories for SEC-ERBA per CRE40.42.

    Maps to S&P/Fitch/Moody's rating scales.
    UNRATED positions fall through to SEC-SA.

    Reference:
        CRE40.42; ERBA NPR Tables 2-5.
    """
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
    """Underlying pool asset types for securitization positions.

    Determines K_SA (pool capital ratio) and STC eligibility.

    Reference:
        CRE40.4; 12 CFR Part 217, Subpart E.
    """
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


class STCEligibility(Enum):
    """STC (Simple, Transparent, Comparable) eligibility status.

    STC-compliant securitizations receive preferential risk weight
    treatment under the SEC-SA framework.

    Reference:
        CRE40.70-40.80; BCBS d424 STC criteria.
    """
    STC_COMPLIANT = "STC_COMPLIANT"
    NON_STC = "NON_STC"
    PENDING_REVIEW = "PENDING_REVIEW"


# =========================================================================
#  SSFA Parameters (SEC-SA)
# =========================================================================

# Supervisory parameter 'p' for the SSFA formula per CRE40.50
# p determines the steepness of the risk weight curve.
# Non-resecuritization: p = 0.5
# Resecuritization: p = 1.5 (more conservative)
P_NON_RESECURITIZATION: float = 0.5
P_RESECURITIZATION: float = 1.5

# STC-compliant securitizations use lower p values per CRE40.72
P_STC_NON_RESEC: float = 0.3
P_STC_RESEC: float = 1.5  # No reduction for resecuritization STC

# Maximum risk weight (1250% = full deduction) per CRE40.46
MAX_RISK_WEIGHT: float = 12.50

# Minimum risk weight floor per CRE40.44
# Non-resecuritization: 15% floor
# Resecuritization: 100% floor
MIN_RISK_WEIGHT_NON_RESEC: float = 0.15  # 15%
MIN_RISK_WEIGHT_RESEC: float = 1.00  # 100%

# Risk weight floor for senior tranches per CRE40.44
SENIOR_TRANCHE_FLOOR: float = 0.15  # 15%

# STC risk weight floor (lower than standard) per CRE40.73
STC_RISK_WEIGHT_FLOOR: float = 0.10  # 10%


# =========================================================================
#  SEC-ERBA Risk Weight Tables (CRE40.42, ERBA NPR Tables 2-5)
# =========================================================================

# Mapping: (ExternalRating, TrancheSeniority, MaturityBucket) -> risk_weight
# Risk weights expressed as decimals (e.g., 0.15 = 15%)
#
# These tables correspond to Tables 2-5 in the ERBA NPR:
# Table 2: Senior tranches, short-term maturity
# Table 3: Senior tranches, long-term maturity
# Table 4: Non-senior tranches, short-term maturity
# Table 5: Non-senior tranches, long-term maturity

SEC_ERBA_RW: dict[tuple[str, str, str], float] = {
    # --- Senior tranches (Tables 2-3) ---
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

    # --- Non-senior tranches (Tables 4-5) ---
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
#  SEC-ERBA STC Adjusted Risk Weight Tables (CRE40.74)
# =========================================================================

# STC-compliant securitizations receive a 0.5x multiplier on
# SEC-ERBA risk weights, subject to the STC floor.
STC_ERBA_MULTIPLIER: float = 0.5


# =========================================================================
#  SEC-ERBA Maturity Interpolation Anchors
# =========================================================================

# Short-term maturity anchor (years) for interpolation per CRE40.43
ERBA_SHORT_MATURITY: float = 1.0

# Long-term maturity anchor (years) for interpolation per CRE40.43
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
#  Pool-Level Parameters
# =========================================================================

# W parameter (delinquency ratio) thresholds for K_A calculation per CRE40.54
# W represents the proportion of underlying exposures that are delinquent
W_THRESHOLD_LOW: float = 0.0
W_THRESHOLD_HIGH: float = 1.0

# Default K_g (pool capital ratio) when pool RWA data is unavailable
# per CRE40.48 — conservative assumption of 8%
DEFAULT_POOL_CAPITAL_RATIO: float = 0.08

# K_g cap: pool capital ratio cannot exceed 100% per CRE40.49
MAX_POOL_CAPITAL_RATIO: float = 1.00


# =========================================================================
#  Tranche Parameters
# =========================================================================

class TrancheThickness(NamedTuple):
    """Tranche thickness classification thresholds.

    Thin tranches (small D - A) receive higher risk weights
    due to concentrated credit risk.

    Reference:
        CRE40.52; ERBA NPR Section IV.
    """
    thin_threshold: float  # Below this thickness → thin tranche
    thick_threshold: float  # Above this → thick tranche


# Tranche thickness thresholds per CRE40.52
TRANCHE_THICKNESS: TrancheThickness = TrancheThickness(
    thin_threshold=0.03,   # 3% thickness considered thin
    thick_threshold=0.10,  # 10% thickness considered thick
)

# Minimum detachment point for senior tranche status per CRE40.42
# A tranche is senior if it is the most senior in the waterfall structure
# and D >= this threshold
SENIOR_DETACHMENT_THRESHOLD: float = 0.50


# =========================================================================
#  Resecuritization Risk Weight Multipliers
# =========================================================================

# ERBA resecuritization multipliers per CRE40.63
# Resecuritization positions receive a 2x multiplier on base risk weights
RESEC_RW_MULTIPLIER: float = 2.0

# Resecuritization risk weight floor per CRE40.63
RESEC_RW_FLOOR: float = 1.00  # 100%


# =========================================================================
#  Concentration Ratio Thresholds
# =========================================================================

# Maximum number of effective obligors below which concentration add-on applies
# per CRE40.56
CONCENTRATION_N_THRESHOLD: int = 6

# Concentration ratio risk weight add-on per CRE40.56
CONCENTRATION_RW_ADDON: float = 0.06  # 6 percentage points per unit


# =========================================================================
#  CTP (Correlation Trading Portfolio) Parameters
# =========================================================================

# CTP eligibility: nth-to-default credit derivatives or securitizations
# where the underlying is a portfolio of single-name credit instruments
# per CRE40.65

# CTP risk weight cap (lower than standard 1250% for qualifying CTP)
CTP_RW_CAP: float = 12.50

# CTP floor for long positions per CRE40.66
CTP_LONG_FLOOR: float = 0.08  # 8%

# CTP floor for short positions per CRE40.66
CTP_SHORT_FLOOR: float = 0.02  # 2%

# CTP comprehensive risk measure (CRM) cap per CRE40.67
# Banks may use internal models subject to this multiplier on SA charges
CTP_CRM_MULTIPLIER: float = 0.08

# CTP maturity mismatch adjustment per CRE40.68
CTP_MATURITY_MISMATCH_FLOOR: float = 0.0


# =========================================================================
#  STC Criteria Parameters
# =========================================================================

# STC (Simple, Transparent, Comparable) criteria per CRE40.70-40.80
# Securitizations meeting all STC criteria receive preferential treatment.

# Maximum tranche maturity for STC eligibility per CRE40.75
STC_MAX_MATURITY_YEARS: float = 5.0

# Minimum number of underlying exposures per CRE40.76
STC_MIN_EXPOSURES: int = 100

# Maximum single obligor concentration per CRE40.77
STC_MAX_SINGLE_OBLIGOR: float = 0.02  # 2% of pool

# STC eligible asset types per CRE40.78
STC_ELIGIBLE_ASSET_TYPES: set[str] = {
    "RMBS", "ABS_AUTO", "ABS_CREDIT_CARD", "ABS_STUDENT_LOAN",
    "CMBS", "CLO", "CORPORATE",
}

# STC requires granularity: effective number of obligors >= this threshold
STC_MIN_EFFECTIVE_OBLIGORS: int = 20


# =========================================================================
#  Reporting Parameters
# =========================================================================

# SEC1-SEC4 Pillar 3 template identifiers
PILLAR3_SEC_TEMPLATES: dict[str, str] = {
    "SEC1": "Securitisation exposures in the banking book",
    "SEC2": "Securitisation exposures in the trading book",
    "SEC3": "Securitisation exposures in the banking book: by approach",
    "SEC4": "Securitisation exposures in the banking book: by risk weight band",
}

# Risk weight bands for SEC4 reporting per Pillar 3
SEC4_RW_BANDS: list[tuple[float, float, str]] = [
    (0.00, 0.15, "0% to 15%"),
    (0.15, 0.25, ">15% to 25%"),
    (0.25, 0.50, ">25% to 50%"),
    (0.50, 1.00, ">50% to 100%"),
    (1.00, 2.50, ">100% to 250%"),
    (2.50, 12.50, ">250% to <1250%"),
    (12.50, 12.50, "1250% (deduction)"),
]


# =========================================================================
#  Helper Functions
# =========================================================================

def get_sec_erba_rw(
    rating: str,
    seniority: str,
    maturity_bucket: str,
) -> float | None:
    """Look up SEC-ERBA risk weight from the regulatory table.

    Args:
        rating: External rating string (AAA, AA, A, BBB, BB, B, CCC, BELOW_CCC).
        seniority: SENIOR or NON_SENIOR.
        maturity_bucket: SHORT or LONG.

    Returns:
        Risk weight as decimal, or None if key not found.

    Reference:
        CRE40.42; ERBA NPR Tables 2-5.
    """
    key = (rating.upper(), seniority.upper(), maturity_bucket.upper())
    return SEC_ERBA_RW.get(key)


def interpolate_erba_rw(
    rating: str,
    seniority: str,
    maturity_years: float,
) -> float | None:
    """Interpolate SEC-ERBA risk weight for intermediate maturities.

    For maturities between 1 and 5 years, linearly interpolate
    between SHORT and LONG risk weights per CRE40.43.

    Args:
        rating: External rating string.
        seniority: SENIOR or NON_SENIOR.
        maturity_years: Remaining maturity in years.

    Returns:
        Interpolated risk weight, or None if rating not in table.

    Reference:
        CRE40.43; ERBA NPR Tables 2-5.
    """
    rw_short = get_sec_erba_rw(rating, seniority, "SHORT")
    rw_long = get_sec_erba_rw(rating, seniority, "LONG")

    if rw_short is None or rw_long is None:
        return None

    if maturity_years <= ERBA_SHORT_MATURITY:
        return rw_short
    if maturity_years >= ERBA_LONG_MATURITY:
        return rw_long

    # Linear interpolation between short and long anchors
    fraction = (maturity_years - ERBA_SHORT_MATURITY) / (
        ERBA_LONG_MATURITY - ERBA_SHORT_MATURITY
    )
    return rw_short + fraction * (rw_long - rw_short)
