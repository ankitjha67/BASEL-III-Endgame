"""Equity risk regulatory parameters -- US ERBA NPR (March 2026) §__.208-§__.209.

All risk weights, correlations, and regulatory constants for the Equity
risk class under the FRTB Sensitivities-Based Method, as written in the
March 2026 Federal Reserve re-proposal, 12 CFR 217 Subpart F:

* §__.208(b)    -- Equity risk factors: spot price and repo rate per issuer;
                   vega by option maturity; curvature on spot only.
* §__.209(b)(5) -- Table 8 bucket definitions, spot and repo delta risk
                   weights, intra-bucket correlations and inter-bucket
                   correlations.
* §__.209 Table 11 / curvature paragraph -- vega risk weights (77.78% for
  large-cap and index buckets, 100% otherwise); curvature risk weight =
  delta risk weight; curvature correlations = delta correlations squared.

Bucket taxonomy (Table 8).  The US rule distinguishes "emerging market
economy" and "liquid market economy" issuers (not "advanced economy" as in
BCBS MAR21.72), and large market capitalisation means >= $2 billion:

    1  EM, large cap -- consumer goods & services, transportation & storage,
       administrative & support services, health care, utilities
    2  EM, large cap -- telecommunications, industrials
    3  EM, large cap -- basic materials, energy, agriculture, manufacturing,
       mining & quarrying
    4  EM, large cap -- financials (incl. government-backed), real estate,
       technology
    5  Liquid market, large cap -- as bucket 1 sectors
    6  Liquid market, large cap -- as bucket 2 sectors
    7  Liquid market, large cap -- as bucket 3 sectors
    8  Liquid market, large cap -- as bucket 4 sectors
    9  EM, small cap -- all sectors
    10 Liquid market, small cap -- all sectors
    11 Other sector
    12 Large-cap, liquid-market equity indices
    13 Other equity indices
"""
from __future__ import annotations

from src.core.enums import CorrelationScenario

# ---------------------------------------------------------------------------
# Large market capitalisation threshold -- ERBA NPR §__.209(b)(5)
# "large market capitalization" = market capitalisation >= $2 billion.
# Expressed in USD millions per project convention.
# ---------------------------------------------------------------------------
EQUITY_LARGE_CAP_THRESHOLD_USD_M: float = 2_000.0

# ---------------------------------------------------------------------------
# Spot delta risk weights per bucket -- ERBA NPR §__.209(b)(5) Table 8
# ---------------------------------------------------------------------------
EQUITY_DELTA_RW: dict[int, float] = {
    1: 0.55,   # EM large cap - consumer, transport, admin, health care, utilities
    2: 0.60,   # EM large cap - telecommunications, industrials
    3: 0.45,   # EM large cap - basic materials, energy, agriculture, manufacturing, mining
    4: 0.55,   # EM large cap - financials, real estate, technology
    5: 0.30,   # Liquid market large cap - consumer, transport, admin, health care, utilities
    6: 0.35,   # Liquid market large cap - telecommunications, industrials
    7: 0.40,   # Liquid market large cap - basic materials, energy, agri, manufacturing, mining
    8: 0.50,   # Liquid market large cap - financials, real estate, technology
    9: 0.70,   # EM small cap - all sectors
    10: 0.50,  # Liquid market small cap - all sectors
    11: 0.70,  # Other sector
    12: 0.15,  # Large-cap, liquid-market equity indices
    13: 0.25,  # Other equity indices
}

# ---------------------------------------------------------------------------
# Equity repo-rate delta risk weights -- ERBA NPR §__.209(b)(5) Table 8
# Repo RW = spot RW / 100 (e.g. bucket 8: 0.50% ; bucket 1: 0.55%).
# ---------------------------------------------------------------------------
EQUITY_REPO_RW_SCALE: float = 0.01
EQUITY_REPO_RW: dict[int, float] = {
    bucket: rw * EQUITY_REPO_RW_SCALE for bucket, rw in EQUITY_DELTA_RW.items()
}

# ---------------------------------------------------------------------------
# Intra-bucket correlations between DIFFERENT issuers -- ERBA NPR §__.209(b)(5)
# Bucket 11 ("other sector") has no correlation parameter: K_b = sum|WS_k|
# (and, for curvature, max(sum max(CVR+,0), sum max(CVR-,0))).  Its entry
# below is a placeholder that must not be used for aggregation.
# ---------------------------------------------------------------------------
EQUITY_INTRA_CORR: dict[int, float] = {
    1: 0.15,    # EM large cap
    2: 0.15,
    3: 0.15,
    4: 0.15,
    5: 0.25,    # Liquid market large cap
    6: 0.25,
    7: 0.25,
    8: 0.25,
    9: 0.075,   # EM small cap
    10: 0.125,  # Liquid market small cap
    11: 0.0,    # Other sector: NOT a correlation -- see EQUITY_OTHER_SECTOR_BUCKET
    12: 0.80,   # Index buckets
    13: 0.80,
}

EQUITY_OTHER_SECTOR_BUCKET: int = 11

# Spot vs repo-rate correlations -- ERBA NPR §__.209(b)(5)
#   same issuer:      99.9%
#   different issuer: bucket rho x 99.9%
EQUITY_RHO_SPOT_REPO_SAME_ISSUER: float = 0.999
EQUITY_RHO_SPOT_REPO_CROSS_FACTOR: float = 0.999

# ---------------------------------------------------------------------------
# Inter-bucket correlations -- ERBA NPR §__.209(b)(5)
#   15% between any two of buckets 1-10
#    0% if either bucket is 11 (other sector)
#   75% between buckets 12 and 13
#   45% otherwise (an index bucket vs a sector bucket 1-10)
# ---------------------------------------------------------------------------
EQUITY_GAMMA_SECTOR: float = 0.15
EQUITY_GAMMA_OTHER_SECTOR: float = 0.0
EQUITY_GAMMA_INDEX_INDEX: float = 0.75
EQUITY_GAMMA_INDEX_SECTOR: float = 0.45

# ---------------------------------------------------------------------------
# Vega risk weights -- ERBA NPR §__.209 Table 11
#   77.78% for large-cap buckets (1-8) and index buckets (12-13)
#   100%   for small-cap and other-sector buckets (9-11)
# ---------------------------------------------------------------------------
EQUITY_VEGA_RW_LARGE_CAP_AND_INDEX: float = 0.7778
EQUITY_VEGA_RW_SMALL_CAP_AND_OTHER: float = 1.0
EQUITY_VEGA_RW: dict[int, float] = {
    **{b: EQUITY_VEGA_RW_LARGE_CAP_AND_INDEX for b in (1, 2, 3, 4, 5, 6, 7, 8, 12, 13)},
    **{b: EQUITY_VEGA_RW_SMALL_CAP_AND_OTHER for b in (9, 10, 11)},
}
EQUITY_VEGA_LIQUIDITY_HORIZON: int = 20  # Business days (informational)
EQUITY_VEGA_ALPHA: float = 0.01  # alpha = 1% in exp(-alpha * |T_k - T_l| / min(T_k, T_l))

# ---------------------------------------------------------------------------
# Bucket groupings
# ---------------------------------------------------------------------------
EQUITY_BUCKETS: list[int] = list(range(1, 14))
EQUITY_EM_BUCKETS: set[int] = {1, 2, 3, 4, 9}
EQUITY_LIQUID_MARKET_BUCKETS: set[int] = {5, 6, 7, 8, 10}
EQUITY_LARGE_CAP_BUCKETS: set[int] = {1, 2, 3, 4, 5, 6, 7, 8}
EQUITY_SMALL_CAP_BUCKETS: set[int] = {9, 10}
EQUITY_SECTOR_BUCKETS: set[int] = set(range(1, 11))
EQUITY_INDEX_BUCKETS: set[int] = {12, 13}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_other_sector_bucket(bucket: int) -> bool:
    """Return whether *bucket* is the equity "other sector" bucket (11).

    ERBA NPR §__.209(b)(5): bucket 11 aggregates as ``sum |WS_k|`` with no
    diversification and carries 0% inter-bucket correlation.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        ``True`` for bucket 11.
    """
    return bucket == EQUITY_OTHER_SECTOR_BUCKET


def get_equity_delta_rw(bucket: int, is_repo: bool = False) -> float:
    """Get the delta risk weight for an equity bucket.

    ERBA NPR §__.209(b)(5) Table 8: spot risk weight, or the repo-rate risk
    weight (= spot / 100) when *is_repo* is set.

    Args:
        bucket: Bucket number (1-13).
        is_repo: ``True`` for an equity repo-rate sensitivity.

    Returns:
        Risk weight as a decimal (e.g. 0.50 for bucket 8 spot, 0.005 repo).

    Raises:
        KeyError: If *bucket* is not a valid equity bucket.
    """
    if is_repo:
        return EQUITY_REPO_RW[bucket]
    return EQUITY_DELTA_RW[bucket]


def get_equity_repo_rw(bucket: int) -> float:
    """Get the equity repo-rate delta risk weight per §__.209(b)(5) Table 8.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        Repo-rate risk weight as a decimal (spot RW / 100).
    """
    return EQUITY_REPO_RW[bucket]


def get_equity_curvature_rw(bucket: int) -> float:
    """Get the equity curvature shock (relative spot shift) for a bucket.

    ERBA NPR §__.209 (curvature): for equity the curvature risk weight
    equals the Table 8 spot delta risk weight; curvature applies to spot
    only (§__.208(b)), not to repo rates.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        Curvature shock as a decimal.
    """
    return EQUITY_DELTA_RW[bucket]


def get_equity_vega_rw(bucket: int) -> float:
    """Get the equity vega risk weight for a bucket per §__.209 Table 11.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        0.7778 for buckets 1-8 and 12-13; 1.0 for buckets 9-11.

    Raises:
        KeyError: If *bucket* is not a valid equity bucket.
    """
    return EQUITY_VEGA_RW[bucket]


def get_equity_intra_corr(bucket: int) -> float:
    """Get the intra-bucket correlation between different issuers.

    ERBA NPR §__.209(b)(5): 15% (buckets 1-4), 25% (5-8), 7.5% (9),
    12.5% (10), 80% (12-13).  Bucket 11 has no correlation parameter and
    returns the 0.0 placeholder; callers must aggregate it as ``sum |WS|``.

    Args:
        bucket: Bucket number (1-13).

    Returns:
        Intra-bucket correlation as a decimal.

    Raises:
        KeyError: If *bucket* is not a valid equity bucket.
    """
    return EQUITY_INTRA_CORR[bucket]


def get_equity_inter_bucket_corr(bucket_b: int, bucket_c: int) -> float:
    """Get the inter-bucket correlation gamma_bc for two equity buckets.

    ERBA NPR §__.209(b)(5):

    * 0%  if either bucket is 11 (other sector);
    * 75% between buckets 12 and 13;
    * 15% between any two of buckets 1-10;
    * 45% otherwise (index bucket 12 or 13 vs a sector bucket 1-10).

    Args:
        bucket_b: First bucket number.
        bucket_c: Second bucket number.

    Returns:
        Inter-bucket correlation as a decimal.
    """
    if bucket_b == bucket_c:
        return 1.0
    if is_other_sector_bucket(bucket_b) or is_other_sector_bucket(bucket_c):
        return EQUITY_GAMMA_OTHER_SECTOR
    if bucket_b in EQUITY_INDEX_BUCKETS and bucket_c in EQUITY_INDEX_BUCKETS:
        return EQUITY_GAMMA_INDEX_INDEX
    if bucket_b in EQUITY_SECTOR_BUCKETS and bucket_c in EQUITY_SECTOR_BUCKETS:
        return EQUITY_GAMMA_SECTOR
    return EQUITY_GAMMA_INDEX_SECTOR


def apply_correlation_scenario(
    rho: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply the correlation scenario adjustment per ERBA NPR §__.206(c).

    +---------+--------------------------------------+
    | Scenario| Adjusted correlation                 |
    +=========+======================================+
    | LOW     | max(2*rho - 1, 0.75*rho)             |
    +---------+--------------------------------------+
    | MEDIUM  | rho (no change)                      |
    +---------+--------------------------------------+
    | HIGH    | min(1.0, 1.25*rho)                   |
    +---------+--------------------------------------+

    (BCBS MAR21.6.)

    Args:
        rho: Base correlation value.
        scenario: One of LOW / MEDIUM / HIGH.
        is_inter_bucket: Whether this is an inter-bucket correlation.

    Returns:
        Scenario-adjusted correlation.
    """
    if scenario == CorrelationScenario.MEDIUM:
        return rho
    elif scenario == CorrelationScenario.HIGH:
        return min(1.0, 1.25 * rho)
    else:  # LOW
        return max(2 * rho - 1, 0.75 * rho)


def compute_equity_pair_correlation(
    bucket: int,
    same_issuer: bool,
    is_repo_k: bool,
    is_repo_l: bool,
) -> float:
    """Base (medium-scenario) correlation between two equity delta factors.

    ERBA NPR §__.209(b)(5):

    * same issuer, both spot or both repo  -> 100% (same risk factor);
    * same issuer, spot vs repo            -> 99.9%;
    * different issuers, same factor type  -> bucket rho;
    * different issuers, spot vs repo      -> bucket rho x 99.9%.

    Args:
        bucket: Bucket number (1-13, not 11).
        same_issuer: Whether both sensitivities reference the same issuer.
        is_repo_k: Whether the first factor is a repo-rate sensitivity.
        is_repo_l: Whether the second factor is a repo-rate sensitivity.

    Returns:
        Correlation as a decimal.
    """
    cross_type = is_repo_k != is_repo_l
    if same_issuer:
        return EQUITY_RHO_SPOT_REPO_SAME_ISSUER if cross_type else 1.0
    rho = get_equity_intra_corr(bucket)
    if cross_type:
        rho *= EQUITY_RHO_SPOT_REPO_CROSS_FACTOR
    return rho


def build_equity_intra_bucket_corr_matrix(
    n: int,
    bucket: int,
    scenario: CorrelationScenario,
    issuers: list[str | None] | None = None,
    is_repo: list[bool] | None = None,
) -> "numpy.ndarray":
    """Build the intra-bucket delta correlation matrix for an equity bucket.

    Implements the ERBA NPR §__.209(b)(5) correlation rules (see
    :func:`compute_equity_pair_correlation`).  When *issuers* is omitted
    every sensitivity is treated as a distinct issuer; when *is_repo* is
    omitted every sensitivity is treated as a spot sensitivity.

    Bucket 11 (other sector) has no correlation structure and must be
    aggregated as ``sum |WS_k|`` by the caller; this function returns the
    identity matrix for it.

    Args:
        n: Number of sensitivities in the bucket.
        bucket: Bucket number (1-13).
        scenario: Correlation scenario (LOW / MEDIUM / HIGH).
        issuers: Optional issuer identifier per sensitivity (``None`` =
            unknown, treated as a distinct issuer).
        is_repo: Optional repo-rate flag per sensitivity.

    Returns:
        numpy ndarray of shape (n, n).
    """
    import numpy as np

    corr = np.eye(n, dtype=np.float64)
    if is_other_sector_bucket(bucket):
        return corr

    for i in range(n):
        for j in range(i + 1, n):
            iss_i = issuers[i] if issuers is not None else None
            iss_j = issuers[j] if issuers is not None else None
            same_issuer = iss_i is not None and iss_i == iss_j
            repo_i = bool(is_repo[i]) if is_repo is not None else False
            repo_j = bool(is_repo[j]) if is_repo is not None else False
            base = compute_equity_pair_correlation(bucket, same_issuer, repo_i, repo_j)
            rho = apply_correlation_scenario(base, scenario)
            corr[i, j] = rho
            corr[j, i] = rho
    return corr
