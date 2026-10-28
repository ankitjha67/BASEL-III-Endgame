"""Commodity risk regulatory parameters -- US ERBA NPR (March 2026) §__.208-§__.209.

All risk weights, correlations, and regulatory constants for the Commodity
risk class under the FRTB Sensitivities-Based Method, as written in the
March 2026 Federal Reserve re-proposal, 12 CFR 217 Subpart F:

* §__.208(b)    -- Commodity risk factors: spot price per commodity, by
                   delivery location and contract maturity on the grid
                   {0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30} years.
* §__.209(b)(6) -- Table 9 bucket definitions and delta risk weights;
                   Table 10 intra-bucket commodity correlations; the tenor
                   (99%) and delivery-location (99.9%) correlations; the
                   inter-bucket correlation (20%, 0% for bucket 11).
* §__.209 Table 11 / curvature paragraph -- vega risk weight 100%;
  curvature risk weight = highest delta risk weight in the bucket; curvature
  correlations = delta correlations squared.

Buckets (Table 9):
   1  Energy -- solid combustibles
   2  Energy -- liquid combustibles
   3  Energy -- electricity and carbon trading  (US text: carbon trading)
   4  Freight
   5  Metals -- non-precious
   6  Gaseous combustibles and electricity
   7  Precious metals (including gold)
   8  Grains and oilseed
   9  Livestock and dairy
   10 Softs and other agriculturals (forestry and other agriculturals)
   11 Other commodity
   12 Commodity indices
(BCBS d457 MAR21.82-21.86 given as cross-reference only; the US rule adds
the index bucket 12 and uses a flat 99% tenor correlation.)
"""
from __future__ import annotations

from src.core.enums import CorrelationScenario

# ---------------------------------------------------------------------------
# Delta maturity vertices (years) -- ERBA NPR §__.208(b)(6)
# Spot (0) plus the ten GIRR vertices.
# ---------------------------------------------------------------------------
COMMODITY_DELTA_MATURITIES: list[float] = [
    0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0,
]

# ---------------------------------------------------------------------------
# Delta risk weights per bucket -- ERBA NPR §__.209(b)(6) Table 9
# ---------------------------------------------------------------------------
COMMODITY_DELTA_RW: dict[int, float] = {
    1: 0.30,   # Energy - solid combustibles
    2: 0.35,   # Energy - liquid combustibles
    3: 0.60,   # Energy - carbon trading
    4: 0.80,   # Freight
    5: 0.40,   # Metals - non-precious
    6: 0.45,   # Gaseous combustibles and electricity
    7: 0.20,   # Precious metals (including gold)
    8: 0.35,   # Grains and oilseed
    9: 0.25,   # Livestock and dairy
    10: 0.35,  # Forestry and other agriculturals
    11: 0.50,  # Other commodity
    12: 0.30,  # Commodity indices
}

# ---------------------------------------------------------------------------
# Intra-bucket commodity correlations rho_cty -- ERBA NPR §__.209(b)(6) Table 10
# Between two DIFFERENT commodities in the same bucket.  The full
# intra-bucket correlation is  rho_kl = rho_cty * rho_tenor * rho_basis.
# ---------------------------------------------------------------------------
COMMODITY_INTRA_CORR: dict[int, float] = {
    1: 0.55,   # Energy - solid combustibles
    2: 0.95,   # Energy - liquid combustibles
    3: 0.40,   # Energy - carbon trading
    4: 0.80,   # Freight
    5: 0.60,   # Metals - non-precious
    6: 0.65,   # Gaseous combustibles and electricity
    7: 0.55,   # Precious metals
    8: 0.45,   # Grains and oilseed
    9: 0.15,   # Livestock and dairy
    10: 0.40,  # Forestry and other agriculturals
    11: 0.15,  # Other commodity
    12: 0.50,  # Commodity indices
}

# ---------------------------------------------------------------------------
# Tenor correlation -- ERBA NPR §__.209(b)(6)
# rho_tenor = 100% if the two maturities are identical, else 99%.
# (The US text prescribes a flat 99%, not the exp(-alpha ...) decay.)
# ---------------------------------------------------------------------------
COMMODITY_RHO_TENOR: float = 0.99

# ---------------------------------------------------------------------------
# Basis (delivery location) correlation -- ERBA NPR §__.209(b)(6)
# rho_basis = 100% if same delivery location, else 99.9%.
# ---------------------------------------------------------------------------
COMMODITY_RHO_BASIS: float = 0.999

# ---------------------------------------------------------------------------
# Inter-bucket correlation -- ERBA NPR §__.209(b)(6)
# gamma_bc = 20% among buckets 1-10 and 12; 0% if either bucket is 11.
# ---------------------------------------------------------------------------
COMMODITY_INTER_BUCKET_BASE: float = 0.20
COMMODITY_INTER_BUCKET_OTHER: float = 0.0
COMMODITY_OTHER_BUCKET: int = 11

# ---------------------------------------------------------------------------
# Vega parameters -- ERBA NPR §__.209 Table 11
# ---------------------------------------------------------------------------
COMMODITY_VEGA_RW: float = 1.0  # 100%
COMMODITY_VEGA_LIQUIDITY_HORIZON: int = 120  # Business days (informational)
COMMODITY_VEGA_ALPHA: float = 0.01  # alpha = 1% in exp(-alpha * |T_k - T_l| / min(T_k, T_l))

# ---------------------------------------------------------------------------
# All valid bucket IDs
# ---------------------------------------------------------------------------
COMMODITY_BUCKETS: list[int] = list(range(1, 13))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_commodity_delta_rw(bucket: int) -> float:
    """Get the delta risk weight for a commodity bucket per §__.209(b)(6) Table 9.

    Args:
        bucket: Bucket number (1-12).

    Returns:
        Risk weight as a decimal (e.g. 0.80 for bucket 4, freight).

    Raises:
        KeyError: If *bucket* is not a valid commodity bucket.
    """
    return COMMODITY_DELTA_RW[bucket]


def get_commodity_curvature_rw(bucket: int) -> float:
    """Get the commodity curvature shock (relative price shift) for a bucket.

    ERBA NPR §__.209 (curvature): the curvature risk weight is the highest
    delta risk weight of the bucket applied as a parallel shift.  Table 9
    assigns a single risk weight per bucket, so this equals the delta RW.

    Args:
        bucket: Bucket number (1-12).

    Returns:
        Curvature shock as a decimal.
    """
    return COMMODITY_DELTA_RW[bucket]


def get_commodity_intra_corr(bucket: int) -> float:
    """Get rho_cty for a commodity bucket per §__.209(b)(6) Table 10.

    Args:
        bucket: Bucket number (1-12).

    Returns:
        Correlation between different commodities in the bucket.

    Raises:
        KeyError: If *bucket* is not a valid commodity bucket.
    """
    return COMMODITY_INTRA_CORR[bucket]


def get_commodity_inter_bucket_corr(bucket_b: int, bucket_c: int) -> float:
    """Get the inter-bucket correlation gamma_bc for two commodity buckets.

    ERBA NPR §__.209(b)(6): 20% among buckets 1-10 and 12; 0% whenever
    either bucket is 11 (other commodity).

    Args:
        bucket_b: First bucket number.
        bucket_c: Second bucket number.

    Returns:
        Inter-bucket correlation as a decimal.
    """
    if bucket_b == bucket_c:
        return 1.0
    if bucket_b == COMMODITY_OTHER_BUCKET or bucket_c == COMMODITY_OTHER_BUCKET:
        return COMMODITY_INTER_BUCKET_OTHER
    return COMMODITY_INTER_BUCKET_BASE


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


def compute_commodity_tenor_correlation(tenor_k: float, tenor_l: float) -> float:
    """Tenor correlation between two commodity contract maturities.

    ERBA NPR §__.209(b)(6): 100% for identical maturities, otherwise a
    flat 99%.

    Args:
        tenor_k: First contract maturity in years.
        tenor_l: Second contract maturity in years.

    Returns:
        Tenor correlation (1.0 or 0.99).
    """
    if tenor_k == tenor_l:
        return 1.0
    return COMMODITY_RHO_TENOR


def build_commodity_intra_bucket_corr_matrix(
    n: int,
    bucket: int,
    tenors: list[float] | None = None,
    basis_flags: list[str] | None = None,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
    commodities: list[str | None] | None = None,
) -> "numpy.ndarray":
    """Build the intra-bucket delta correlation matrix for a commodity bucket.

    ERBA NPR §__.209(b)(6)::

        rho_kl = rho_cty * rho_tenor * rho_basis

    * ``rho_cty``   = Table 10 value for different commodities, 100% for the
      same commodity (when *commodities* is supplied);
    * ``rho_tenor`` = 100% same maturity, else 99%;
    * ``rho_basis`` = 100% same delivery location, else 99.9%.

    If *tenors* or *basis_flags* are not provided the corresponding factor
    is taken as 100%.  If *commodities* is not provided every sensitivity is
    treated as a different commodity.

    Args:
        n: Number of sensitivities in the bucket.
        bucket: Bucket number (1-12).
        tenors: Optional list of contract maturities in years.
        basis_flags: Optional list of delivery-location identifiers.
        scenario: Correlation scenario (LOW / MEDIUM / HIGH).
        commodities: Optional commodity identifier per sensitivity
            (``None`` = unknown, treated as a distinct commodity).

    Returns:
        numpy ndarray of shape (n, n).
    """
    import numpy as np

    base_rho = get_commodity_intra_corr(bucket)

    corr = np.eye(n, dtype=np.float64)

    for i in range(n):
        for j in range(i + 1, n):
            same_commodity = (
                commodities is not None
                and commodities[i] is not None
                and commodities[i] == commodities[j]
            )
            rho = 1.0 if same_commodity else base_rho

            if tenors is not None and len(tenors) == n:
                rho *= compute_commodity_tenor_correlation(tenors[i], tenors[j])

            if basis_flags is not None and len(basis_flags) == n:
                if basis_flags[i] != basis_flags[j]:
                    rho *= COMMODITY_RHO_BASIS

            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho

    return corr
