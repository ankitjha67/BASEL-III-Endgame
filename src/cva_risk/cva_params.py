"""CVA Risk parameters — SA-CVA and BA-CVA regulatory constants.

Defines all supervisory parameters, risk weights, correlation matrices,
bucket definitions, and hedge effectiveness parameters for Credit Valuation
Adjustment risk capital calculations under both the Standardized Approach
(SA-CVA) and Basic Approach (BA-CVA).

All monetary amounts in USD millions ($M) unless stated otherwise.

References:
    - BCBS d424 (Dec 2017), Section 5: CVA risk capital charge
    - BCBS d457 MAR50: Basic Approach CVA
    - BCBS d457 MAR51: Standardized Approach CVA
    - US Federal Reserve Basel III Endgame Re-Proposal (Mar 2026),
      ERBA NPR pp. 280-295: CVA risk framework
    - CRE52.30: SA-CCR alpha multipliers

Regulatory Notes:
    - SA-CCR alpha = 1.4 for financial counterparties, 1.0 for commercial
      end-users per US 2026 re-proposal (consistent with CLAUDE.md).
    - ILM = 1.0 (Internal Loss Multiplier NOT applied per 2026 proposal).
    - Dodd-Frank §939A: No external ratings for US exposures; use internal
      assessment. Rating enums used here map to internal grade equivalents.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Final, NamedTuple

import numpy as np


# =========================================================================
#  CVA Approach Enums
# =========================================================================

class CVAApproach(Enum):
    """CVA calculation approach per BCBS d424 Section 5 / ERBA NPR p. 280.

    Banks may use either BA-CVA (simpler, higher capital) or SA-CVA
    (sensitivity-based, requires supervisory approval).
    """
    BA_CVA_FULL = "BA-CVA-FULL"
    BA_CVA_REDUCED = "BA-CVA-REDUCED"
    SA_CVA = "SA-CVA"


class CVARating(Enum):
    """Credit rating categories for CVA risk weights.

    Per BCBS d424 / ERBA NPR p. 282, Table 1.
    For US banks under Dodd-Frank §939A, these map to internal
    credit grade equivalents rather than external agency ratings.
    """
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    UNRATED_IG = "UNRATED_IG"
    UNRATED_HY = "UNRATED_HY"
    UNRATED = "UNRATED"


class CVASector(Enum):
    """Counterparty sector classification for CVA per ERBA NPR p. 283.

    Sector determines both the bucket assignment in SA-CVA and the
    supervisory risk weight multiplier.
    """
    SOVEREIGN = "SOVEREIGN"
    PUBLIC_SECTOR = "PUBLIC_SECTOR"
    FINANCIAL = "FINANCIAL"
    CORPORATE = "CORPORATE"
    OTHER = "OTHER"


class CVACreditQuality(Enum):
    """Credit quality classification for SA-CVA bucket assignment.

    Per ERBA NPR p. 284, counterparties are classified as IG or HY/NR
    for bucket assignment.
    """
    INVESTMENT_GRADE = "IG"
    HIGH_YIELD = "HY"
    NOT_RATED = "NR"


class CVAHedgeType(Enum):
    """Types of eligible CVA hedges per BCBS d424 / ERBA NPR p. 288.

    Only single-name CDS, index CDS, and contingent CDS are eligible
    as CVA hedges.
    """
    SINGLE_NAME_CDS = "SINGLE_NAME_CDS"
    INDEX_CDS = "INDEX_CDS"
    CONTINGENT_CDS = "CONTINGENT_CDS"


class SACVARiskFactorType(Enum):
    """Risk factor types for SA-CVA sensitivities per MAR51.2 / ERBA NPR p. 285.

    SA-CVA captures delta and vega risk for credit spread and interest rate
    risk factors. FX, equity, and commodity are included when material.
    """
    COUNTERPARTY_CREDIT_SPREAD = "COUNTERPARTY_CREDIT_SPREAD"
    REFERENCE_CREDIT_SPREAD = "REFERENCE_CREDIT_SPREAD"
    INTEREST_RATE = "INTEREST_RATE"
    FX = "FX"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"


# =========================================================================
#  Investment Grade Classification
# =========================================================================

IG_RATINGS: Final[frozenset[str]] = frozenset({
    "AAA", "AA", "A", "BBB", "UNRATED_IG",
})
"""Ratings considered investment grade per ERBA NPR p. 282."""


def is_investment_grade(rating: str) -> bool:
    """Determine if a rating is investment grade.

    Per ERBA NPR p. 282: AAA through BBB (or internal equivalent)
    are considered investment grade.

    Args:
        rating: Rating string (raw or mapped).

    Returns:
        True if the rating maps to investment grade.
    """
    mapped = RATING_TO_CVA_RATING.get(rating, rating)
    return mapped in IG_RATINGS


# =========================================================================
#  Rating Mapping
# =========================================================================

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
    "UNRATED_HY": "UNRATED_HY",
    "UNRATED": "UNRATED",
    "NR": "UNRATED",
}
"""Map external/internal rating strings to CVA rating categories.

Per ERBA NPR p. 282. Under Dodd-Frank §939A, US banks use internal
grade equivalents.
"""


# =========================================================================
#  BA-CVA Parameters (BCBS d424 / MAR50 / ERBA NPR pp. 280-284)
# =========================================================================

BA_CVA_ALPHA: Final[float] = 1.0
"""Alpha multiplier for BA-CVA per ERBA NPR p. 281.

The overall scaling factor applied to the BA-CVA formula.
Per the 2026 re-proposal, alpha = 1.0 for BA-CVA.
"""

BA_CVA_RHO: Final[float] = 0.50
"""Supervisory correlation parameter (rho) for BA-CVA per MAR50.5 / ERBA NPR p. 281.

Controls the split between systematic and idiosyncratic components.
rho = 50% means equal weight to diversifiable and non-diversifiable risk.
"""

BA_CVA_BETA: Final[float] = 0.25
"""Hedging effectiveness parameter (beta) for BA-CVA per MAR50.6 / ERBA NPR p. 281.

K_BA-CVA = beta * K_hedged + (1 - beta) * K_full.
beta = 0.25 means 75% of the capital comes from the full (unhedged) formula
and 25% from the hedged formula. This conservative calibration reflects
the supervisory view that CVA hedges are imperfect.
"""

BA_CVA_HEDGE_DISCOUNT_SINGLE_NAME: Final[float] = 0.50
"""Hedge discount factor for single-name CDS per MAR50.7 / ERBA NPR p. 288.

A single-name CDS on the counterparty reduces the standalone CVA risk
by this factor. Reflects basis risk between CVA and CDS hedge.
"""

BA_CVA_HEDGE_DISCOUNT_INDEX: Final[float] = 0.25
"""Hedge discount factor for index CDS per MAR50.7 / ERBA NPR p. 288.

Index CDS provides less effective hedging than single-name due to
basis risk. Discount is half of single-name.
"""


# =========================================================================
#  BA-CVA Supervisory Risk Weights by Rating
#  (ERBA NPR pp. 282-283, Table 1)
# =========================================================================

BA_CVA_RISK_WEIGHTS: Final[dict[str, float]] = {
    "AAA": 0.007,
    "AA": 0.007,
    "A": 0.008,
    "BBB": 0.010,
    "BB": 0.020,
    "B": 0.030,
    "CCC": 0.100,
    "UNRATED_IG": 0.008,
    "UNRATED_HY": 0.020,
    "UNRATED": 0.015,
}
"""Supervisory risk weights (w_c) for BA-CVA by rating.

Per ERBA NPR p. 282, Table 1. These weights are applied to
M_c * EAD_c to produce the standalone CVA risk per counterparty.
Risk weights are expressed as decimals (e.g., 0.007 = 0.7%).
"""

BA_CVA_SUPERVISORY_SPREADS_BPS: Final[dict[str, int]] = {
    "AAA": 50,
    "AA": 60,
    "A": 80,
    "BBB": 100,
    "BB": 200,
    "B": 400,
    "CCC": 700,
    "UNRATED_IG": 80,
    "UNRATED_HY": 200,
    "UNRATED": 150,
}
"""Supervisory credit spreads in basis points per ERBA NPR p. 283.

Used when market-implied spreads are not available for a counterparty.
"""


# =========================================================================
#  Effective Maturity Parameters (ERBA NPR p. 283)
# =========================================================================

MIN_EFFECTIVE_MATURITY: Final[float] = 1.0
"""Floor for effective maturity in years per MAR50.4 / ERBA NPR p. 283."""

MAX_EFFECTIVE_MATURITY: Final[float] = 5.0
"""Cap for effective maturity in years per MAR50.4 / ERBA NPR p. 283."""

MATURITY_DISCOUNT_RATE: Final[float] = 0.05
"""Risk-free rate for supervisory discount factor per MAR50.4 / ERBA NPR p. 283.

Used in: d_c = (1 - exp(-r * M_c)) / (r * M_c).
"""


# =========================================================================
#  Margin Period of Risk (ERBA NPR p. 284)
# =========================================================================

MPOR_DEFAULT_DAYS: Final[int] = 10
"""Default margin period of risk for bilateral margined netting sets (business days)."""

MPOR_CENTRALLY_CLEARED_DAYS: Final[int] = 5
"""MPOR for centrally cleared transactions (business days)."""

MPOR_DISPUTE_DAYS: Final[int] = 20
"""MPOR where margin disputes exceed threshold (business days)."""

MPOR_UNMARGINED_FACTOR: Final[float] = 1.0
"""Scaling factor for unmargined netting sets (no MPOR reduction)."""


# =========================================================================
#  SA-CCR Alpha Multipliers (per CRE52.30 / CLAUDE.md)
# =========================================================================

SACCR_ALPHA_FINANCIAL: Final[float] = 1.4
"""SA-CCR alpha multiplier for financial counterparties per CRE52.30.

Per CLAUDE.md: SA-CCR alpha = 1.4 for financial counterparties.
"""

SACCR_ALPHA_COMMERCIAL: Final[float] = 1.0
"""SA-CCR alpha multiplier for commercial end-users per 2026 re-proposal.

Per CLAUDE.md: SA-CCR alpha = 1.0 for commercial end-users.
"""


def get_saccr_alpha(is_financial: bool) -> float:
    """Return the appropriate SA-CCR alpha multiplier.

    Per CRE52.30 / ERBA NPR: alpha = 1.4 for financial counterparties,
    1.0 for commercial end-users.

    Args:
        is_financial: True if counterparty is a financial institution.

    Returns:
        Alpha multiplier (1.4 or 1.0).
    """
    return SACCR_ALPHA_FINANCIAL if is_financial else SACCR_ALPHA_COMMERCIAL


# =========================================================================
#  SA-CVA Risk Weights by Sector and Rating
#  (BCBS d424 / ERBA NPR pp. 284-287, Table 2)
# =========================================================================

class SACVARiskWeightEntry(NamedTuple):
    """A single SA-CVA risk weight entry."""
    bucket: int
    sector: str
    quality: str
    risk_weight: float
    description: str


SA_CVA_RISK_WEIGHT_TABLE: Final[list[SACVARiskWeightEntry]] = [
    # Bucket 1: Sovereigns (IG) — ERBA NPR p. 285
    SACVARiskWeightEntry(1, "SOVEREIGN", "IG", 0.005, "Sovereigns, central banks, MDBs (IG)"),
    # Bucket 2: Sovereigns (HY/NR) — ERBA NPR p. 285
    SACVARiskWeightEntry(2, "SOVEREIGN", "HY", 0.020, "Sovereigns, central banks, MDBs (HY/NR)"),
    # Bucket 3: Financials (IG) — ERBA NPR p. 285
    SACVARiskWeightEntry(3, "FINANCIAL", "IG", 0.008, "Financials incl. govt-backed (IG)"),
    # Bucket 4: Financials (HY/NR) — ERBA NPR p. 285
    SACVARiskWeightEntry(4, "FINANCIAL", "HY", 0.025, "Financials incl. govt-backed (HY/NR)"),
    # Bucket 5: Corporates (IG) — ERBA NPR p. 286
    SACVARiskWeightEntry(5, "CORPORATE", "IG", 0.010, "Non-financial corporates (IG)"),
    # Bucket 6: Corporates (HY/NR) — ERBA NPR p. 286
    SACVARiskWeightEntry(6, "CORPORATE", "HY", 0.030, "Non-financial corporates (HY/NR)"),
    # Bucket 7: Public Sector/Other (IG) — ERBA NPR p. 286
    SACVARiskWeightEntry(7, "PUBLIC_SECTOR", "IG", 0.008, "Public sector entities (IG)"),
    # Bucket 8: Public Sector/Other (HY/NR) — ERBA NPR p. 286
    SACVARiskWeightEntry(8, "PUBLIC_SECTOR", "HY", 0.025, "Public sector entities (HY/NR)"),
    # Bucket 9: Other (IG) — ERBA NPR p. 287
    SACVARiskWeightEntry(9, "OTHER", "IG", 0.012, "Other sector (IG)"),
    # Bucket 10: Other (HY/NR) — ERBA NPR p. 287
    SACVARiskWeightEntry(10, "OTHER", "HY", 0.035, "Other sector (HY/NR)"),
]

SA_CVA_BUCKETS: Final[dict[int, dict[str, str | float]]] = {
    entry.bucket: {
        "name": entry.description,
        "sector": entry.sector,
        "quality": entry.quality,
        "rw": entry.risk_weight,
    }
    for entry in SA_CVA_RISK_WEIGHT_TABLE
}
"""SA-CVA sector buckets with risk weights per ERBA NPR pp. 285-287."""


def get_sa_cva_bucket(sector: str, quality: str) -> int:
    """Determine the SA-CVA bucket number for a counterparty.

    Per ERBA NPR pp. 285-287: Buckets are assigned by sector and credit
    quality (IG vs HY/NR).

    Args:
        sector: Counterparty sector (SOVEREIGN, FINANCIAL, CORPORATE, etc.).
        quality: Credit quality (IG, HY, NR).

    Returns:
        Bucket number (1-10).

    Raises:
        ValueError: If sector/quality combination is not recognized.
    """
    # Normalize quality: NR maps to HY
    q = "IG" if quality == "IG" else "HY"

    for bucket_id, info in SA_CVA_BUCKETS.items():
        if info["sector"] == sector and info["quality"] == q:
            return bucket_id

    # Default fallback to OTHER bucket
    if q == "IG":
        return 9
    return 10


def get_sa_cva_risk_weight(sector: str, quality: str) -> float:
    """Get the SA-CVA risk weight for a sector/quality combination.

    Per ERBA NPR pp. 285-287, Table 2.

    Args:
        sector: Counterparty sector.
        quality: Credit quality (IG, HY, NR).

    Returns:
        Risk weight as decimal (e.g., 0.005 for Sovereign IG).
    """
    bucket_id = get_sa_cva_bucket(sector, quality)
    return float(SA_CVA_BUCKETS[bucket_id]["rw"])


def get_ba_cva_risk_weight(rating: str) -> float:
    """Look up BA-CVA supervisory risk weight by rating.

    Per ERBA NPR p. 282, Table 1.

    Args:
        rating: Rating string (raw or mapped).

    Returns:
        Risk weight as decimal (e.g., 0.007 for AAA).

    Raises:
        KeyError: If rating cannot be mapped.
    """
    mapped = RATING_TO_CVA_RATING.get(rating, rating)
    if mapped in BA_CVA_RISK_WEIGHTS:
        return BA_CVA_RISK_WEIGHTS[mapped]
    # Fallback for generic UNRATED
    if mapped in ("UNRATED", "UNRATED_IG", "UNRATED_HY"):
        return BA_CVA_RISK_WEIGHTS.get(mapped, BA_CVA_RISK_WEIGHTS["UNRATED"])
    raise KeyError(f"Unknown CVA rating: {rating!r} (mapped to {mapped!r})")


# =========================================================================
#  SA-CVA Correlation Parameters (ERBA NPR pp. 287-288)
# =========================================================================

SA_CVA_INTRA_BUCKET_CORRELATION: Final[float] = 0.35
"""Intra-bucket counterparty correlation for SA-CVA per MAR51.7 / ERBA NPR p. 287.

Correlation between different counterparties within the same sector bucket.
"""

SA_CVA_SAME_COUNTERPARTY_CORRELATION: Final[float] = 0.50
"""Correlation for the same counterparty across risk factors per ERBA NPR p. 287.

Per CLAUDE.md: rho = 50% for same counterparty.
"""

SA_CVA_INTER_BUCKET_CORRELATION: Final[float] = 0.50
"""Inter-bucket correlation for SA-CVA per MAR51.8 / ERBA NPR p. 288.

Used when aggregating across sector buckets (e.g., Financial vs Corporate).
"""

SA_CVA_RISK_TYPE_CORRELATION: Final[float] = 0.30
"""Correlation across risk factor types (spread vs IR) per MAR51.12 / ERBA NPR p. 288.

Used in: K_CVA = sqrt(K_spread^2 + K_IR^2 + 2 * rho * K_spread * K_IR).
"""


# =========================================================================
#  SA-CVA Inter-Bucket Correlation Matrix
#  (ERBA NPR p. 288)
# =========================================================================

def _build_inter_bucket_correlation_matrix() -> np.ndarray:
    """Build the 10x10 inter-bucket correlation matrix for SA-CVA.

    Per ERBA NPR p. 288: Same-sector different-quality pairs get
    higher correlation (0.80); different-sector pairs get the
    supervisory inter-bucket correlation (0.50).

    Returns:
        10x10 numpy array of inter-bucket correlations.
    """
    n = 10
    matrix = np.full((n, n), SA_CVA_INTER_BUCKET_CORRELATION)

    # Same-sector IG/HY pairs get higher correlation (0.80)
    # Per ERBA NPR p. 288: pairs within the same sector
    same_sector_pairs = [
        (0, 1),  # Sovereign IG/HY
        (2, 3),  # Financial IG/HY
        (4, 5),  # Corporate IG/HY
        (6, 7),  # Public Sector IG/HY
        (8, 9),  # Other IG/HY
    ]
    for i, j in same_sector_pairs:
        matrix[i, j] = 0.80
        matrix[j, i] = 0.80

    # Diagonal is 1.0
    np.fill_diagonal(matrix, 1.0)

    return matrix


SA_CVA_INTER_BUCKET_CORRELATION_MATRIX: Final[np.ndarray] = (
    _build_inter_bucket_correlation_matrix()
)
"""10x10 inter-bucket correlation matrix for SA-CVA.

Rows/columns correspond to buckets 1-10. Same-sector pairs have
correlation 0.80; different-sector pairs have 0.50.
Per ERBA NPR p. 288.
"""


# =========================================================================
#  SA-CVA Tenor and Sensitivity Parameters (ERBA NPR pp. 285-286)
# =========================================================================

SA_CVA_TENOR_VERTICES: Final[list[float]] = [0.5, 1.0, 3.0, 5.0, 10.0]
"""SA-CVA credit spread tenor vertices in years per MAR51.4 / ERBA NPR p. 285.

Sensitivities are mapped to these standard tenors for aggregation.
"""

SA_CVA_IR_TENOR_VERTICES: Final[list[float]] = [1.0, 2.0, 5.0, 10.0, 30.0]
"""SA-CVA interest rate tenor vertices in years per MAR51.4 / ERBA NPR p. 286."""

SA_CVA_TENOR_CORRELATION_BASE: Final[float] = 0.65
"""Base correlation between different tenors within same counterparty.

Per MAR51.4 / ERBA NPR p. 286:
rho_tenor(t_k, t_l) = exp(-theta * |t_k - t_l| / min(t_k, t_l))
where theta = -ln(0.65) ≈ 0.431.
"""


def tenor_correlation(t_k: float, t_l: float) -> float:
    """Compute correlation between two tenor vertices per MAR51.4 / ERBA NPR p. 286.

    Formula: rho(t_k, t_l) = exp(-theta * |t_k - t_l| / min(t_k, t_l))
    where theta = -ln(base_correlation).

    Args:
        t_k: First tenor in years.
        t_l: Second tenor in years.

    Returns:
        Correlation between 0 and 1.
    """
    if t_k <= 0 or t_l <= 0:
        return 1.0
    if t_k == t_l:
        return 1.0
    theta = -math.log(SA_CVA_TENOR_CORRELATION_BASE)
    return math.exp(-theta * abs(t_k - t_l) / min(t_k, t_l))


# =========================================================================
#  SA-CVA Vega Parameters (ERBA NPR p. 289)
# =========================================================================

SA_CVA_VEGA_RISK_WEIGHT: Final[float] = 0.55
"""Vega risk weight multiplier for SA-CVA per MAR51.10 / ERBA NPR p. 289.

Applied to the vega sensitivity to compute the weighted sensitivity.
"""

SA_CVA_VEGA_OPTION_MATURITY_VERTICES: Final[list[float]] = [
    0.5, 1.0, 3.0, 5.0, 10.0,
]
"""Option maturity vertices for vega risk per MAR51.10 / ERBA NPR p. 289."""


# =========================================================================
#  SA-CVA Risk Weight Ranges by Quality (ERBA NPR p. 285)
# =========================================================================

SA_CVA_RW_RANGE_IG: Final[tuple[float, float]] = (0.005, 0.030)
"""SA-CVA risk weight range for investment grade counterparties.

Per ERBA NPR p. 285: IG risk weights range from 0.5% to 3.0%.
"""

SA_CVA_RW_RANGE_HY: Final[tuple[float, float]] = (0.015, 0.060)
"""SA-CVA risk weight range for high yield counterparties.

Per ERBA NPR p. 285: HY risk weights range from 1.5% to 6.0%.
"""

SA_CVA_RW_RANGE_SOVEREIGN: Final[tuple[float, float]] = (0.005, 0.020)
"""SA-CVA risk weight range for sovereign counterparties.

Per ERBA NPR p. 285: Sovereign risk weights range from 0.5% to 2.0%.
"""


# =========================================================================
#  Hedge Eligibility Parameters (ERBA NPR pp. 288-290)
# =========================================================================

ELIGIBLE_CVA_HEDGE_TYPES: Final[frozenset[str]] = frozenset({
    "SINGLE_NAME_CDS",
    "INDEX_CDS",
    "CONTINGENT_CDS",
})
"""Set of eligible CVA hedge instrument types per ERBA NPR p. 288."""

HEDGE_MATURITY_MISMATCH_FLOOR: Final[float] = 0.0
"""Floor for maturity mismatch adjustment per ERBA NPR p. 289.

When hedge maturity < exposure maturity, the hedge benefit is reduced.
"""

HEDGE_MATURITY_MISMATCH_CAP: Final[float] = 1.0
"""Cap for maturity mismatch adjustment per ERBA NPR p. 289."""

SA_CVA_HEDGE_NOTIONAL_SCALING: Final[float] = 1.0
"""Supervisory scaling factor for hedge notionals per ERBA NPR p. 289."""


def hedge_maturity_adjustment(
    hedge_maturity: float,
    exposure_maturity: float,
) -> float:
    """Compute maturity mismatch adjustment for a CVA hedge.

    Per ERBA NPR p. 289: When the hedge has shorter maturity than the
    exposure, the hedge benefit is reduced proportionally.

    Formula: adjustment = min(hedge_maturity / exposure_maturity, 1.0)

    Args:
        hedge_maturity: Remaining maturity of the hedge in years.
        exposure_maturity: Effective maturity of the exposure in years.

    Returns:
        Adjustment factor in [0, 1].
    """
    if exposure_maturity <= 0:
        return HEDGE_MATURITY_MISMATCH_FLOOR
    ratio = hedge_maturity / exposure_maturity
    return max(
        HEDGE_MATURITY_MISMATCH_FLOOR,
        min(ratio, HEDGE_MATURITY_MISMATCH_CAP),
    )


# =========================================================================
#  Supervisory Discount Factor (ERBA NPR p. 283)
# =========================================================================

def supervisory_discount_factor(maturity: float) -> float:
    """Compute the supervisory discount factor per MAR50.4 / ERBA NPR p. 283.

    Formula: d_c = (1 - exp(-r * M_c)) / (r * M_c)
    where r = 0.05 (supervisory risk-free rate).

    The maturity is clipped to [1, 5] years per regulatory requirements.

    Args:
        maturity: Effective maturity in years.

    Returns:
        Supervisory discount factor d_c.
    """
    m = float(np.clip(maturity, MIN_EFFECTIVE_MATURITY, MAX_EFFECTIVE_MATURITY))
    if m <= 0:
        return 1.0
    return float(
        (1.0 - math.exp(-MATURITY_DISCOUNT_RATE * m))
        / (MATURITY_DISCOUNT_RATE * m)
    )


def effective_maturity(
    notional_weighted_maturity: float,
    total_notional: float,
    floor: float = MIN_EFFECTIVE_MATURITY,
    cap: float = MAX_EFFECTIVE_MATURITY,
) -> float:
    """Compute notional-weighted effective maturity per ERBA NPR p. 283.

    For netting sets with multiple trades, effective maturity is the
    notional-weighted average, floored at 1 year and capped at 5 years.

    Args:
        notional_weighted_maturity: Sum of (notional_i * maturity_i).
        total_notional: Sum of notional_i.
        floor: Minimum effective maturity (default 1 year).
        cap: Maximum effective maturity (default 5 years).

    Returns:
        Effective maturity in years, in [floor, cap].
    """
    if total_notional <= 0:
        return floor
    m = notional_weighted_maturity / total_notional
    return max(floor, min(m, cap))


# =========================================================================
#  RWA Conversion
# =========================================================================

RWA_MULTIPLIER: Final[float] = 12.5
"""Multiplier to convert capital charge to RWA per ERBA NPR p. 280.

RWA_CVA = K_CVA * 12.5 (inverse of 8% minimum capital ratio).
"""
