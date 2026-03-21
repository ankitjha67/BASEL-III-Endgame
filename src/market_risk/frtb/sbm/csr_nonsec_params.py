"""CSR Non-Securitization regulatory parameters per MAR21.12-21.13 Basel III Endgame.

All risk weights, correlations, and regulatory constants for the Credit Spread
Risk -- Non-Securitization class under FRTB Sensitivities-Based Method.

Reference: BCBS d457 MAR21.12-21.13, US Federal Reserve Basel III Endgame Final Rule.
"""
from __future__ import annotations

import math
from typing import Optional

from src.core.enums import (
    CorrelationScenario,
    CreditQuality,
    CSRBucket,
    CSRSector,
)

# ---------------------------------------------------------------------------
# Standard tenor vertices (years) -- same 12 as GIRR (MAR21.12)
# ---------------------------------------------------------------------------
TENORS: list[float] = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 25.0, 30.0]

# ---------------------------------------------------------------------------
# Bucket definitions -- MAR21.12 Table 4
# ---------------------------------------------------------------------------
BUCKET_SECTOR_QUALITY: dict[int, tuple[CSRSector, CreditQuality]] = {
    1:  (CSRSector.SOVEREIGN,           CreditQuality.INVESTMENT_GRADE),
    2:  (CSRSector.SOVEREIGN,           CreditQuality.HIGH_YIELD),
    3:  (CSRSector.FINANCIALS,          CreditQuality.INVESTMENT_GRADE),
    4:  (CSRSector.FINANCIALS,          CreditQuality.HIGH_YIELD),
    5:  (CSRSector.BASIC_MATERIALS,     CreditQuality.INVESTMENT_GRADE),
    6:  (CSRSector.BASIC_MATERIALS,     CreditQuality.HIGH_YIELD),
    7:  (CSRSector.CONSUMER,            CreditQuality.INVESTMENT_GRADE),
    8:  (CSRSector.CONSUMER,            CreditQuality.HIGH_YIELD),
    9:  (CSRSector.TMT,                 CreditQuality.INVESTMENT_GRADE),
    10: (CSRSector.TMT,                 CreditQuality.HIGH_YIELD),
    11: (CSRSector.HEALTHCARE_UTILITIES, CreditQuality.INVESTMENT_GRADE),
    12: (CSRSector.HEALTHCARE_UTILITIES, CreditQuality.HIGH_YIELD),
    13: (CSRSector.COVERED_BOND,        CreditQuality.INVESTMENT_GRADE),
    14: (CSRSector.COVERED_BOND,        CreditQuality.HIGH_YIELD),
    15: (CSRSector.REAL_ESTATE,         CreditQuality.INVESTMENT_GRADE),
    16: (CSRSector.REAL_ESTATE,         CreditQuality.HIGH_YIELD),
    17: (CSRSector.OTHER,               CreditQuality.INVESTMENT_GRADE),
    18: (CSRSector.OTHER,               CreditQuality.HIGH_YIELD),
}

# ---------------------------------------------------------------------------
# Delta risk weights as decimal percentages -- MAR21.12 Table 4
# ---------------------------------------------------------------------------
DELTA_RISK_WEIGHTS: dict[int, float] = {
    1:  0.005,   # 0.5% - Sovereigns IG
    2:  0.01,    # 1.0% - Sovereigns HY/NR
    3:  0.01,    # 1.0% - Financials IG
    4:  0.02,    # 2.0% - Financials HY/NR
    5:  0.01,    # 1.0% - Basic materials/energy/industrials IG
    6:  0.02,    # 2.0% - Basic materials/energy/industrials HY/NR
    7:  0.01,    # 1.0% - Consumer goods/services/transport IG
    8:  0.02,    # 2.0% - Consumer goods/services/transport HY/NR
    9:  0.01,    # 1.0% - Technology/telecommunications IG
    10: 0.02,    # 2.0% - Technology/telecommunications HY/NR
    11: 0.01,    # 1.0% - Healthcare/utilities/gov-backed IG
    12: 0.02,    # 2.0% - Healthcare/utilities/gov-backed HY/NR
    13: 0.01,    # 1.0% - Covered bonds IG
    14: 0.02,    # 2.0% - Covered bonds HY/NR
    15: 0.01,    # 1.0% - Real estate IG
    16: 0.035,   # 3.5% - Real estate HY/NR
    17: 0.005,   # 0.5% - Other IG
    18: 0.035,   # 3.5% - Other HY/NR
}

# ---------------------------------------------------------------------------
# Intra-bucket correlation parameters (MAR21.12)
# ---------------------------------------------------------------------------
THETA: float = 0.03  # Tenor correlation decay parameter
CORRELATION_FLOOR: float = 0.40  # Minimum tenor correlation

# ---------------------------------------------------------------------------
# Name correlations by bucket (rho_name for different issuers) -- MAR21.12
# Same issuer always gets rho_name = 1.0
# ---------------------------------------------------------------------------
NAME_CORRELATIONS: dict[int, float] = {
    1:  0.80,   2:  0.80,   # Sovereigns
    3:  0.65,   4:  0.65,   # Financials
    5:  0.55,   6:  0.55,   # Basic materials
    7:  0.55,   8:  0.55,   # Consumer
    9:  0.55,   10: 0.55,   # TMT
    11: 0.55,   12: 0.55,   # Healthcare/utilities
    13: 0.80,   14: 0.80,   # Covered bonds
    15: 0.55,   16: 0.55,   # Real estate
    17: 0.50,   18: 0.50,   # Other
}

# ---------------------------------------------------------------------------
# Cross-curve basis correlation -- MAR21.12
# ---------------------------------------------------------------------------
RHO_BASIS_SAME_CURVE: float = 1.0    # Same credit spread curve
RHO_BASIS_DIFF_CURVE: float = 0.999  # Different credit spread curves

# ---------------------------------------------------------------------------
# Inter-bucket correlation matrix (18x18) -- MAR21.13
# ---------------------------------------------------------------------------
# Sector groupings for inter-bucket correlation logic:
#   Sovereign: 1, 2        Financials: 3, 4
#   Basic materials: 5, 6  Consumer: 7, 8
#   TMT: 9, 10             Healthcare: 11, 12
#   Covered bonds: 13, 14  Real estate: 15, 16
#   Other: 17, 18

def _same_sector(b1: int, b2: int) -> bool:
    """Check whether two buckets belong to the same sector."""
    return (b1 - 1) // 2 == (b2 - 1) // 2


def _is_ig(bucket: int) -> bool:
    """Check whether a bucket is investment grade (odd bucket number)."""
    return bucket % 2 == 1


def _sector_index(bucket: int) -> int:
    """Return the 0-based sector index (0-8) for a bucket."""
    return (bucket - 1) // 2


# Pre-computed inter-bucket correlation matrix
def _build_inter_bucket_matrix() -> dict[tuple[int, int], float]:
    """Build the full 18x18 inter-bucket correlation matrix per MAR21.13.

    Correlation rules:
    - Same sector IG/HY pair: 0.75
    - Sovereign-Financial: 0.50
    - Sovereign-Corporate: 0.45
    - Financial-Corporate: 0.40
    - Corporate-Corporate same quality: 0.50
    - Corporate-Corporate cross quality: 0.40
    - Covered bond-Financial: 0.60
    - Other-any: 0.25

    Returns:
        Dictionary mapping ``(bucket_i, bucket_j)`` to the inter-bucket
        correlation gamma_bc.
    """
    # Sector indices for classification
    SOV = 0        # sector index for sovereign (buckets 1-2)
    FIN = 1        # sector index for financials (buckets 3-4)
    COVERED = 6    # sector index for covered bonds (buckets 13-14)
    OTHER = 8      # sector index for other (buckets 17-18)

    # Corporate sectors: basic materials, consumer, TMT, healthcare, real estate
    CORPORATE_SECTORS = {2, 3, 4, 5, 7}  # sector indices

    matrix: dict[tuple[int, int], float] = {}

    for bi in range(1, 19):
        for bj in range(1, 19):
            if bi == bj:
                matrix[(bi, bj)] = 1.0
                continue

            si = _sector_index(bi)
            sj = _sector_index(bj)

            if _same_sector(bi, bj):
                # Same sector, different quality (IG vs HY)
                gamma = 0.75
            elif si == OTHER or sj == OTHER:
                # Other sector with anything
                gamma = 0.25
            elif si == SOV and sj == FIN or si == FIN and sj == SOV:
                # Sovereign-Financial
                gamma = 0.50
            elif si == SOV and sj in CORPORATE_SECTORS or sj == SOV and si in CORPORATE_SECTORS:
                # Sovereign-Corporate
                gamma = 0.45
            elif si == COVERED and sj == FIN or si == FIN and sj == COVERED:
                # Covered bond-Financial
                gamma = 0.60
            elif si == SOV and sj == COVERED or sj == SOV and si == COVERED:
                # Sovereign-Covered bond
                gamma = 0.45
            elif si == COVERED and sj in CORPORATE_SECTORS or sj == COVERED and si in CORPORATE_SECTORS:
                # Covered bond-Corporate
                gamma = 0.40
            elif si == FIN and sj in CORPORATE_SECTORS or sj == FIN and si in CORPORATE_SECTORS:
                # Financial-Corporate
                gamma = 0.40
            elif si in CORPORATE_SECTORS and sj in CORPORATE_SECTORS:
                # Corporate-Corporate
                bi_ig = _is_ig(bi)
                bj_ig = _is_ig(bj)
                if bi_ig == bj_ig:
                    # Same quality
                    gamma = 0.50
                else:
                    # Cross quality
                    gamma = 0.40
            else:
                gamma = 0.25

            matrix[(bi, bj)] = gamma

    return matrix


INTER_BUCKET_CORRELATIONS: dict[tuple[int, int], float] = _build_inter_bucket_matrix()


# ---------------------------------------------------------------------------
# Vega parameters (MAR21.44-47)
# ---------------------------------------------------------------------------
VEGA_RISK_WEIGHT: float = 1.0  # min(sqrt(120/10), 1.0) = min(3.464, 1.0) = 1.0
VEGA_LIQUIDITY_HORIZON: int = 120  # Business days for CSR Non-Sec
VEGA_OPTION_MATURITIES: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_UNDERLYING_TENORS: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_ALPHA: float = 0.01  # Correlation decay for vega


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_bucket_for_sector_quality(
    sector: CSRSector,
    quality: CreditQuality,
) -> int:
    """Determine the CSR Non-Sec bucket number for a sector and credit quality.

    Maps a sector and credit quality combination to the corresponding
    bucket number (1-18) per MAR21.12 Table 4.

    Not-rated (NR) issuers are assigned to the HY/NR bucket for their sector.

    Args:
        sector: The issuer's sector classification.
        quality: The issuer's credit quality.

    Returns:
        Bucket number (1-18).

    Raises:
        ValueError: If the sector/quality combination is unrecognised.
    """
    # NOT_RATED maps to the same bucket as HIGH_YIELD
    effective_quality = (
        CreditQuality.HIGH_YIELD
        if quality == CreditQuality.NOT_RATED
        else quality
    )

    for bucket_num, (s, q) in BUCKET_SECTOR_QUALITY.items():
        if s == sector and q == effective_quality:
            return bucket_num

    raise ValueError(
        f"No CSR Non-Sec bucket for sector={sector.value}, "
        f"quality={quality.value}"
    )


def get_delta_risk_weight(bucket: int) -> float:
    """Get delta risk weight for a CSR Non-Sec bucket.

    The risk weight is uniform across all tenors within a bucket,
    unlike GIRR where it varies by tenor.

    Args:
        bucket: Bucket number (1-18).

    Returns:
        Risk weight as a decimal (e.g. 0.01 for 1.0%).

    Raises:
        KeyError: If *bucket* is not a valid CSR Non-Sec bucket.
    """
    return DELTA_RISK_WEIGHTS[bucket]


def compute_tenor_correlation(tenor_k: float, tenor_l: float) -> float:
    """Compute tenor correlation per MAR21.12.

    .. math::

        \\rho_{\\mathrm{tenor}}(k, l) = \\max\\!\\bigl(
            e^{-\\theta \\,|T_k - T_l| / \\min(T_k, T_l)},\\;
            40\\%
        \\bigr)

    Args:
        tenor_k: First tenor vertex in years.
        tenor_l: Second tenor vertex in years.

    Returns:
        Correlation between the two tenor vertices, floored at
        :data:`CORRELATION_FLOOR`.
    """
    if tenor_k == tenor_l:
        return 1.0
    ratio = abs(tenor_k - tenor_l) / min(tenor_k, tenor_l)
    raw = math.exp(-THETA * ratio)
    return max(raw, CORRELATION_FLOOR)


def compute_name_correlation(
    bucket: int,
    same_issuer: bool,
) -> float:
    """Compute the name correlation component per MAR21.12.

    Args:
        bucket: Bucket number (1-18).
        same_issuer: True if the two risk factors reference the same
            issuer / obligor.

    Returns:
        Name correlation: 1.0 for same issuer, otherwise the regulatory
        value from :data:`NAME_CORRELATIONS`.
    """
    if same_issuer:
        return 1.0
    return NAME_CORRELATIONS[bucket]


def compute_basis_correlation(same_curve: bool) -> float:
    """Compute the basis (curve) correlation component per MAR21.12.

    Args:
        same_curve: True if both risk factors reference the same credit
            spread curve.

    Returns:
        1.0 for same curve, 0.999 for different curves.
    """
    return RHO_BASIS_SAME_CURVE if same_curve else RHO_BASIS_DIFF_CURVE


def compute_intra_bucket_correlation(
    bucket: int,
    tenor_k: float,
    tenor_l: float,
    same_issuer: bool,
    same_curve: bool,
) -> float:
    """Compute the full intra-bucket correlation for CSR Non-Sec per MAR21.12.

    The correlation decomposes into three multiplicative factors:

    .. math::

        \\rho_{kl} = \\rho_{\\mathrm{name}} \\times
                     \\rho_{\\mathrm{tenor}} \\times
                     \\rho_{\\mathrm{basis}}

    Args:
        bucket: Bucket number (1-18).
        tenor_k: Tenor of risk factor *k* in years.
        tenor_l: Tenor of risk factor *l* in years.
        same_issuer: Whether both risk factors reference the same obligor.
        same_curve: Whether both risk factors reference the same curve.

    Returns:
        Combined intra-bucket correlation.
    """
    rho_name = compute_name_correlation(bucket, same_issuer)
    rho_tenor = compute_tenor_correlation(tenor_k, tenor_l)
    rho_basis = compute_basis_correlation(same_curve)
    return rho_name * rho_tenor * rho_basis


def get_inter_bucket_correlation(bucket_b: int, bucket_c: int) -> float:
    """Look up the inter-bucket correlation between two CSR Non-Sec buckets.

    Args:
        bucket_b: First bucket number (1-18).
        bucket_c: Second bucket number (1-18).

    Returns:
        Inter-bucket correlation gamma_bc per MAR21.13.
    """
    return INTER_BUCKET_CORRELATIONS[(bucket_b, bucket_c)]


def apply_correlation_scenario(
    rho: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply correlation scenario adjustment per MAR21.6.

    +---------+--------------------------------------+
    | Scenario| Adjusted correlation                 |
    +=========+======================================+
    | LOW     | ``max(2*rho - 1, 0.75*rho)``         |
    +---------+--------------------------------------+
    | MEDIUM  | ``rho`` (no change)                  |
    +---------+--------------------------------------+
    | HIGH    | ``min(1.0, 1.25*rho)``               |
    +---------+--------------------------------------+

    Args:
        rho: Base correlation value.
        scenario: One of LOW / MEDIUM / HIGH.
        is_inter_bucket: Whether this is an inter-bucket correlation
            (reserved for future use with differentiated scaling).

    Returns:
        Scenario-adjusted correlation.
    """
    if scenario == CorrelationScenario.MEDIUM:
        return rho
    elif scenario == CorrelationScenario.HIGH:
        return min(1.0, 1.25 * rho)
    else:  # LOW
        return max(2 * rho - 1, 0.75 * rho)


def build_csr_nonsec_correlation_matrix(
    bucket: int,
    issuers: list[str],
    tenors: list[float],
    curves: list[str],
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> "numpy.ndarray":
    """Build the full intra-bucket correlation matrix for a CSR Non-Sec bucket.

    Each entry in the matrix corresponds to a sensitivity identified by its
    (issuer, tenor, curve) triple.  The correlation between entries *i* and
    *j* is:

    .. math::

        \\rho_{ij} = \\rho_{\\mathrm{name}} \\times
                     \\rho_{\\mathrm{tenor}} \\times
                     \\rho_{\\mathrm{basis}}

    with scenario adjustments applied per MAR21.6.

    Args:
        bucket: Bucket number (1-18).
        issuers: Issuer name/ID for each sensitivity (length *n*).
        tenors: Tenor in years for each sensitivity (length *n*).
        curves: Curve label for each sensitivity (length *n*).
        scenario: Correlation scenario to apply.

    Returns:
        A symmetric ``numpy.ndarray`` of shape ``(n, n)`` with the
        scenario-adjusted intra-bucket correlation matrix.
    """
    import numpy as np  # noqa: WPS433 (local import to keep module lightweight)

    n = len(issuers)
    corr = np.eye(n, dtype=np.float64)

    for i in range(n):
        for j in range(i + 1, n):
            same_issuer = (issuers[i] == issuers[j])
            same_curve = (curves[i] == curves[j])

            rho = compute_intra_bucket_correlation(
                bucket=bucket,
                tenor_k=tenors[i],
                tenor_l=tenors[j],
                same_issuer=same_issuer,
                same_curve=same_curve,
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho

    return corr
