"""CSR Non-Securitization regulatory parameters -- ERBA NPR §__.208(c), §__.209(b)(2).

All risk weights, correlations and regulatory constants for the Credit Spread
Risk -- Non-Securitization (CSR non-sec) risk class under the FRTB
Sensitivities-Based Method as re-proposed by the US agencies in March 2026
(ERBA NPR, "Regulatory Capital Rule: Category I and II Banking
Organizations").

Where the US text deliberately deviates from BCBS d457 MAR21 (three
internally-assessed credit-quality categories instead of external ratings,
20 buckets instead of 18, fixed 65 % tenor correlation instead of the
exponential GIRR decay, Table 4 sector correlations), the US text governs.

Citations in this module:

* §__.208(c)(1)  -- CSR non-sec delta risk factors and tenor vertices
* §__.208(c)(2)  -- CSR non-sec vega risk factors (option maturities)
* §__.209(b)(2)  -- Table 3 (buckets / delta RWs), intra-bucket rho,
                    Table 4 (gamma_sector) and gamma_rating
* §__.209(c)     -- Vega risk weights (Table 11) and vega correlations
* §__.209(d)     -- Curvature risk weights and correlations
* §__.206        -- Correlation scenarios (low / medium / high)
"""
from __future__ import annotations

import math

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    CreditQuality,
    CSRSector,
)

# ---------------------------------------------------------------------------
# Standard tenor vertices (years) -- ERBA NPR §__.208(c)(1)
# CSR non-sec delta risk factors are defined at five tenor vertices.
# ---------------------------------------------------------------------------
TENORS: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]

# ---------------------------------------------------------------------------
# Bucket taxonomy -- ERBA NPR §__.209(b)(2) Table 3
#
# Each bucket maps to (sector, set of credit-quality categories).  Buckets
# 12-16 explicitly cover BOTH speculative and sub-speculative grade; bucket
# 18 ("other sector") takes any credit quality; buckets 19-20 are indices.
#
# TODO: VERIFY -- Table 3 labels buckets 9-11 "Speculative grade" and gives
#   no separate sub-speculative-grade bucket for PSEs (bucket 10) or
#   financials (bucket 11); only sovereigns receive a dedicated
#   sub-speculative bucket (17).  Pending agency clarification, this engine
#   maps sub-speculative-grade PSEs to bucket 10 and sub-speculative-grade
#   financials to bucket 11 (the highest-RW bucket of that sector), which is
#   the conservative reading of the table's grouping.
# ---------------------------------------------------------------------------
_IG: frozenset[CreditQuality] = frozenset({CreditQuality.INVESTMENT_GRADE})
_SPEC: frozenset[CreditQuality] = frozenset({CreditQuality.SPECULATIVE_GRADE})
_SPEC_AND_SUBSPEC: frozenset[CreditQuality] = frozenset(
    {CreditQuality.SPECULATIVE_GRADE, CreditQuality.SUB_SPECULATIVE_GRADE}
)
_SUBSPEC: frozenset[CreditQuality] = frozenset({CreditQuality.SUB_SPECULATIVE_GRADE})
_ANY: frozenset[CreditQuality] = frozenset(CreditQuality)

BUCKET_SECTOR_QUALITY: dict[int, tuple[CSRSector, frozenset[CreditQuality]]] = {
    # Investment grade
    1:  (CSRSector.SOVEREIGN,            _IG),
    2:  (CSRSector.PSE,                  _IG),
    3:  (CSRSector.FINANCIALS,           _IG),
    4:  (CSRSector.BASIC_MATERIALS,      _IG),
    5:  (CSRSector.CONSUMER,             _IG),
    6:  (CSRSector.TECH_TELECOM,         _IG),
    7:  (CSRSector.HEALTHCARE_UTILITIES, _IG),
    8:  (CSRSector.COVERED_BOND,         _IG),
    # Speculative grade (see TODO: VERIFY above for sub-speculative PSE / fin)
    9:  (CSRSector.SOVEREIGN,            _SPEC),
    10: (CSRSector.PSE,                  _SPEC_AND_SUBSPEC),
    11: (CSRSector.FINANCIALS,           _SPEC_AND_SUBSPEC),
    # Speculative AND sub-speculative grade
    12: (CSRSector.BASIC_MATERIALS,      _SPEC_AND_SUBSPEC),
    13: (CSRSector.CONSUMER,             _SPEC_AND_SUBSPEC),
    14: (CSRSector.TECH_TELECOM,         _SPEC_AND_SUBSPEC),
    15: (CSRSector.HEALTHCARE_UTILITIES, _SPEC_AND_SUBSPEC),
    16: (CSRSector.COVERED_BOND,         _SPEC_AND_SUBSPEC),
    # Sub-speculative grade
    17: (CSRSector.SOVEREIGN,            _SUBSPEC),
    # Other sector / indices
    18: (CSRSector.OTHER,                _ANY),
    19: (CSRSector.INDEX,                _IG),
    20: (CSRSector.INDEX,                _SPEC_AND_SUBSPEC),
}

BUCKET_NAMES: dict[int, str] = {
    1:  "IG - Sovereigns, central banks, MDBs, supranationals",
    2:  "IG - PSEs, gov-backed non-financials, GSE debt, education, public administration",
    3:  "IG - Financials incl. gov-backed financials and real estate activities",
    4:  "IG - Basic materials, energy, industrials, agriculture, manufacturing, mining",
    5:  "IG - Consumer goods & services, transport & storage, administrative & support",
    6:  "IG - Technology, telecommunications",
    7:  "IG - Health care, utilities, professional & technical activities",
    8:  "IG - Covered bonds",
    9:  "Speculative - Sovereigns, central banks, MDBs, supranationals",
    10: "Speculative - PSEs, gov-backed non-financials, education, public administration",
    11: "Speculative - Financials incl. gov-backed financials and real estate activities",
    12: "Spec & sub-spec - Basic materials, energy, industrials, agriculture, manufacturing, "
        "mining",
    13: "Spec & sub-spec - Consumer goods & services, transport & storage, administrative & "
        "support",
    14: "Spec & sub-spec - Technology, telecommunications",
    15: "Spec & sub-spec - Health care, utilities, professional & technical activities",
    16: "Spec & sub-spec - Covered bonds",
    17: "Sub-speculative - Sovereigns, central banks, MDBs, supranationals",
    18: "Other sector",
    19: "Investment-grade indices",
    20: "Speculative & sub-speculative grade indices",
}

OTHER_SECTOR_BUCKET: int = 18
INDEX_BUCKETS: frozenset[int] = frozenset({19, 20})
SINGLE_NAME_BUCKETS: frozenset[int] = frozenset(range(1, 18))
ALL_BUCKETS: tuple[int, ...] = tuple(range(1, 21))

# ---------------------------------------------------------------------------
# Delta risk weights -- ERBA NPR §__.209(b)(2) Table 3 (uniform across tenors)
# ---------------------------------------------------------------------------
DELTA_RISK_WEIGHTS: dict[int, float] = {
    1:  0.005,   # 0.5%  IG sovereigns / MDBs / supranationals
    2:  0.010,   # 1.0%  IG PSEs, gov-backed non-financials, GSE debt, education, public admin
    3:  0.050,   # 5.0%  IG financials incl. gov-backed financials, real estate activities
    4:  0.030,   # 3.0%  IG basic materials, energy, industrials, agriculture, manufacturing, mining
    5:  0.030,   # 3.0%  IG consumer goods & services, transport & storage, admin & support
    6:  0.020,   # 2.0%  IG technology, telecommunications
    7:  0.015,   # 1.5%  IG health care, utilities, professional & technical
    8:  0.015,   # 1.5%  IG covered bonds
    9:  0.030,   # 3.0%  Speculative sovereigns
    10: 0.040,   # 4.0%  Speculative PSEs / gov-backed non-financials / education / public admin
    11: 0.120,   # 12.0% Speculative financials
    12: 0.070,   # 7.0%  Spec & sub-spec basic materials ...
    13: 0.085,   # 8.5%  Spec & sub-spec consumer ...
    14: 0.055,   # 5.5%  Spec & sub-spec technology, telecommunications
    15: 0.050,   # 5.0%  Spec & sub-spec health care, utilities, professional
    16: 0.025,   # 2.5%  Spec & sub-spec covered bonds
    17: 0.070,   # 7.0%  Sub-speculative sovereigns
    18: 0.120,   # 12.0% Other sector
    19: 0.015,   # 1.5%  Investment-grade indices
    20: 0.050,   # 5.0%  Speculative & sub-speculative indices
}

# ---------------------------------------------------------------------------
# Intra-bucket correlation components -- ERBA NPR §__.209(b)(2)
#   rho_kl = rho_name x rho_tenor x rho_basis   (buckets 1-17, 19, 20)
#   bucket 18: K_b = sum |WS_k|  (no intra-bucket correlation)
# ---------------------------------------------------------------------------
RHO_NAME_SAME: float = 1.0          # same name
RHO_NAME_DIFF: float = 0.35         # different names, buckets 1-17
RHO_NAME_DIFF_INDEX: float = 0.80   # different indices, buckets 19-20
RHO_TENOR_SAME: float = 1.0         # same tenor vertex
RHO_TENOR_DIFF: float = 0.65        # different tenor vertices (fixed, NOT exp-decay)
RHO_BASIS_SAME_CURVE: float = 1.0   # same credit spread curve (e.g. bond-bond)
RHO_BASIS_DIFF_CURVE: float = 0.999  # different curves (e.g. bond vs CDS)

# ---------------------------------------------------------------------------
# Inter-bucket correlation -- ERBA NPR §__.209(b)(2)
#   gamma_bc = gamma_rating x gamma_sector
#   gamma_rating = 50 % if buckets b and c (both within 1-17) fall in
#                  different credit-quality categories, where speculative
#                  and sub-speculative grade count as ONE category;
#                  100 % otherwise (incl. any pair involving 18, 19, 20).
#   gamma_sector = 100 % if same sector, else Table 4.
# ---------------------------------------------------------------------------
GAMMA_RATING_DIFFERENT_QUALITY: float = 0.50
GAMMA_RATING_SAME_QUALITY: float = 1.0
GAMMA_SECTOR_SAME: float = 1.0

# Sector groups (rows / columns of Table 4), in table order.
SECTOR_GROUPS: tuple[frozenset[int], ...] = (
    frozenset({1, 9, 17}),   # 0: sovereigns / MDBs / supranationals
    frozenset({2, 10}),      # 1: PSEs, gov-backed non-financials, GSE, education, public admin
    frozenset({3, 11}),      # 2: financials
    frozenset({4, 12}),      # 3: basic materials, energy, industrials, ...
    frozenset({5, 13}),      # 4: consumer goods & services, transport, ...
    frozenset({6, 14}),      # 5: technology, telecommunications
    frozenset({7, 15}),      # 6: health care, utilities, professional
    frozenset({8, 16}),      # 7: covered bonds
    frozenset({18}),         # 8: other sector
    frozenset({19}),         # 9: IG indices
    frozenset({20}),         # 10: spec & sub-spec indices
)

# Table 4 gamma_sector (upper triangle, keyed by sector-group index pair).
GAMMA_SECTOR_TABLE4: dict[tuple[int, int], float] = {
    # {1,9,17} row
    (0, 1): 0.75, (0, 2): 0.10, (0, 3): 0.20, (0, 4): 0.25, (0, 5): 0.20,
    (0, 6): 0.15, (0, 7): 0.10, (0, 8): 0.00, (0, 9): 0.45, (0, 10): 0.45,
    # {2,10} row
    (1, 2): 0.05, (1, 3): 0.15, (1, 4): 0.20, (1, 5): 0.15, (1, 6): 0.10,
    (1, 7): 0.10, (1, 8): 0.00, (1, 9): 0.45, (1, 10): 0.45,
    # {3,11} row
    (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.05, (2, 7): 0.20,
    (2, 8): 0.00, (2, 9): 0.45, (2, 10): 0.45,
    # {4,12} row
    (3, 4): 0.20, (3, 5): 0.25, (3, 6): 0.05, (3, 7): 0.05,
    (3, 8): 0.00, (3, 9): 0.45, (3, 10): 0.45,
    # {5,13} row
    (4, 5): 0.25, (4, 6): 0.05, (4, 7): 0.15,
    (4, 8): 0.00, (4, 9): 0.45, (4, 10): 0.45,
    # {6,14} row
    (5, 6): 0.05, (5, 7): 0.20,
    (5, 8): 0.00, (5, 9): 0.45, (5, 10): 0.45,
    # {7,15} row
    (6, 7): 0.05,
    (6, 8): 0.00, (6, 9): 0.45, (6, 10): 0.45,
    # {8,16} row
    (7, 8): 0.00, (7, 9): 0.45, (7, 10): 0.45,
    # 18 row
    (8, 9): 0.00, (8, 10): 0.00,
    # 19 row
    (9, 10): 0.75,
}

# ---------------------------------------------------------------------------
# Vega parameters -- ERBA NPR §__.208(c)(2), §__.209(c) Table 11
# ---------------------------------------------------------------------------
VEGA_RISK_WEIGHT: float = 1.0  # 100 % for CSR non-sec (Table 11)
VEGA_OPTION_MATURITIES: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_ALPHA: float = 0.01  # alpha in exp(-alpha |Tk - Tl| / min(Tk, Tl))


# ===========================================================================
#  Helper functions
# ===========================================================================

def _sector_group_index(bucket: int) -> int:
    """Return the Table 4 sector-group index (0-10) for a bucket.

    ERBA NPR §__.209(b)(2) Table 4 groups buckets of the same sector
    ({1,9,17}, {2,10}, ..., {8,16}) plus singleton rows for 18, 19, 20.

    Args:
        bucket: Bucket number (1-20).

    Returns:
        0-based index into :data:`SECTOR_GROUPS`.

    Raises:
        KeyError: If *bucket* is not a valid CSR non-sec bucket.
    """
    for idx, group in enumerate(SECTOR_GROUPS):
        if bucket in group:
            return idx
    raise KeyError(f"Bucket {bucket} is not a valid CSR non-sec bucket (1-20)")


def get_credit_quality_category(bucket: int) -> str | None:
    """Return the gamma_rating credit-quality category of a bucket.

    Per ERBA NPR §__.209(b)(2) the rating factor distinguishes only two
    categories among buckets 1-17: investment grade (1-8) versus
    speculative / sub-speculative grade (9-17), the latter two counting as
    ONE category.  Buckets 18-20 are outside the rating factor.

    Args:
        bucket: Bucket number (1-20).

    Returns:
        ``"IG"``, ``"NON_IG"`` or ``None`` for buckets 18-20.
    """
    if bucket not in DELTA_RISK_WEIGHTS:
        raise KeyError(f"Bucket {bucket} is not a valid CSR non-sec bucket (1-20)")
    if bucket not in SINGLE_NAME_BUCKETS:
        return None
    qualities = BUCKET_SECTOR_QUALITY[bucket][1]
    return "IG" if qualities == _IG else "NON_IG"


def get_bucket_for_sector_quality(
    sector: CSRSector,
    quality: CreditQuality,
) -> int:
    """Determine the CSR non-sec bucket for a sector / credit-quality pair.

    Implements the Table 3 assignment of ERBA NPR §__.209(b)(2).  The
    ``OTHER`` sector maps to bucket 18 regardless of credit quality; the
    ``INDEX`` sector maps to bucket 19 (IG) or 20 (speculative /
    sub-speculative).  Sub-speculative-grade PSEs and financials map to
    buckets 10 and 11 respectively (see ``TODO: VERIFY`` at the table).

    Args:
        sector: The issuer's sector classification.
        quality: The issuer's internally-assessed credit quality.

    Returns:
        Bucket number (1-20).

    Raises:
        ValueError: If the sector / quality combination is unrecognised.
    """
    for bucket_num, (s, qualities) in BUCKET_SECTOR_QUALITY.items():
        if s == sector and quality in qualities:
            return bucket_num
    raise ValueError(
        f"No CSR non-sec bucket for sector={sector.value}, quality={quality.value}"
    )


def get_delta_risk_weight(bucket: int) -> float:
    """Get the delta risk weight for a CSR non-sec bucket.

    ERBA NPR §__.209(b)(2) Table 3.  The risk weight is uniform across the
    five tenor vertices within a bucket.

    Args:
        bucket: Bucket number (1-20).

    Returns:
        Risk weight as a decimal (e.g. ``0.05`` for 5.0 %).

    Raises:
        KeyError: If *bucket* is not a valid CSR non-sec bucket.
    """
    return DELTA_RISK_WEIGHTS[bucket]


def get_curvature_risk_weight(bucket: int) -> float:
    """Get the curvature risk weight for a CSR non-sec bucket.

    ERBA NPR §__.209(d): the curvature shock is a parallel shift of all
    tenors by the HIGHEST delta risk weight in the bucket.  CSR non-sec
    delta risk weights are tenor-uniform, so this equals the bucket's delta
    risk weight.

    Args:
        bucket: Bucket number (1-20).

    Returns:
        Curvature risk weight as a decimal.
    """
    return DELTA_RISK_WEIGHTS[bucket]


def compute_name_correlation(bucket: int, same_issuer: bool) -> float:
    """Compute rho_name per ERBA NPR §__.209(b)(2).

    * 100 % where the two names are identical;
    * 35 % otherwise for buckets 1-17;
    * 80 % otherwise for the index buckets 19-20.

    Bucket 18 has no intra-bucket correlation (``K_b = sum |WS_k|``); for
    completeness the function returns the single-name value.

    Args:
        bucket: Bucket number (1-20).
        same_issuer: True if the two risk factors reference the same name.

    Returns:
        Name correlation component.
    """
    if bucket not in DELTA_RISK_WEIGHTS:
        raise KeyError(f"Bucket {bucket} is not a valid CSR non-sec bucket (1-20)")
    if same_issuer:
        return RHO_NAME_SAME
    if bucket in INDEX_BUCKETS:
        return RHO_NAME_DIFF_INDEX
    return RHO_NAME_DIFF


def compute_tenor_correlation(tenor_k: float, tenor_l: float) -> float:
    """Compute rho_tenor per ERBA NPR §__.209(b)(2).

    100 % where the two sensitivities are to the same tenor vertex, 65 %
    otherwise.  (The US text uses a fixed value, NOT the GIRR
    ``exp(-theta |Tk-Tl| / min)`` decay.)

    Args:
        tenor_k: Tenor vertex of risk factor *k* in years.
        tenor_l: Tenor vertex of risk factor *l* in years.

    Returns:
        Tenor correlation component.
    """
    return RHO_TENOR_SAME if tenor_k == tenor_l else RHO_TENOR_DIFF


def compute_basis_correlation(same_curve: bool) -> float:
    """Compute rho_basis per ERBA NPR §__.209(b)(2).

    100 % where both sensitivities are to the same credit spread curve,
    99.9 % otherwise (e.g. bond spread vs CDS spread of the same name).

    Args:
        same_curve: True if both risk factors reference the same curve.

    Returns:
        Basis correlation component.
    """
    return RHO_BASIS_SAME_CURVE if same_curve else RHO_BASIS_DIFF_CURVE


def compute_intra_bucket_correlation(
    bucket: int,
    tenor_k: float,
    tenor_l: float,
    same_issuer: bool,
    same_curve: bool,
) -> float:
    """Compute the delta intra-bucket correlation rho_kl per ERBA NPR §__.209(b)(2).

    .. math::

        \\rho_{kl} = \\rho_{\\mathrm{name}} \\times
                     \\rho_{\\mathrm{tenor}} \\times
                     \\rho_{\\mathrm{basis}}

    Not applicable to bucket 18 (other sector), whose intra-bucket charge
    is ``sum |WS_k|``; callers must special-case that bucket.

    Args:
        bucket: Bucket number (1-20).
        tenor_k: Tenor of risk factor *k* in years.
        tenor_l: Tenor of risk factor *l* in years.
        same_issuer: Whether both risk factors reference the same name.
        same_curve: Whether both risk factors reference the same curve.

    Returns:
        Combined intra-bucket correlation.
    """
    return (
        compute_name_correlation(bucket, same_issuer)
        * compute_tenor_correlation(tenor_k, tenor_l)
        * compute_basis_correlation(same_curve)
    )


def compute_curvature_correlation(
    bucket: int,
    same_issuer: bool,
    same_curve: bool,
) -> float:
    """Compute the curvature intra-bucket correlation per ERBA NPR §__.209(d).

    Curvature risk factors are parallel shifts of a name's whole curve, so
    the tenor dimension collapses and the delta correlation reduces to
    ``rho_name x rho_basis``; the curvature correlation is its square.

    Args:
        bucket: Bucket number (1-20).
        same_issuer: Whether both risk factors reference the same name.
        same_curve: Whether both risk factors reference the same curve.

    Returns:
        Squared delta correlation (before scenario adjustment).
    """
    rho = compute_name_correlation(bucket, same_issuer) * compute_basis_correlation(same_curve)
    return rho ** 2


def compute_vega_correlation(
    bucket: int,
    option_maturity_k: float,
    option_maturity_l: float,
    same_issuer: bool,
) -> float:
    """Compute the vega intra-bucket correlation per ERBA NPR §__.209(c).

    For CSR risk classes:

    .. math::

        \\rho_{kl} = \\min\\bigl(\\rho^{\\mathrm{delta}}_{kl}
            \\times e^{-\\alpha |T_k - T_l| / \\min(T_k, T_l)},\\; 1\\bigr)

    where ``rho_delta`` is the delta correlation between the underlying
    names (``rho_name``), ``T`` is the option maturity and ``alpha = 1 %``.

    Args:
        bucket: Bucket number (1-20).
        option_maturity_k: Option maturity of vega factor *k* in years.
        option_maturity_l: Option maturity of vega factor *l* in years.
        same_issuer: Whether both vega factors reference the same name.

    Returns:
        Vega correlation (capped at 100 %).
    """
    rho_delta = compute_name_correlation(bucket, same_issuer)
    if option_maturity_k == option_maturity_l:
        rho_opt = 1.0
    else:
        rho_opt = math.exp(
            -VEGA_ALPHA
            * abs(option_maturity_k - option_maturity_l)
            / min(option_maturity_k, option_maturity_l)
        )
    return min(rho_delta * rho_opt, 1.0)


def compute_gamma_rating(bucket_b: int, bucket_c: int) -> float:
    """Compute gamma_rating per ERBA NPR §__.209(b)(2).

    50 % where buckets *b* and *c* are both within 1-17 and fall in
    different credit-quality categories (speculative and sub-speculative
    grade count as one category); 100 % otherwise.

    Args:
        bucket_b: First bucket (1-20).
        bucket_c: Second bucket (1-20).

    Returns:
        Rating component of the inter-bucket correlation.
    """
    cat_b = get_credit_quality_category(bucket_b)
    cat_c = get_credit_quality_category(bucket_c)
    if cat_b is None or cat_c is None or cat_b == cat_c:
        return GAMMA_RATING_SAME_QUALITY
    return GAMMA_RATING_DIFFERENT_QUALITY


def compute_gamma_sector(bucket_b: int, bucket_c: int) -> float:
    """Compute gamma_sector per ERBA NPR §__.209(b)(2) Table 4.

    100 % where the two buckets belong to the same sector group, otherwise
    the Table 4 entry for the pair of sector groups.

    Args:
        bucket_b: First bucket (1-20).
        bucket_c: Second bucket (1-20).

    Returns:
        Sector component of the inter-bucket correlation.
    """
    gi = _sector_group_index(bucket_b)
    gj = _sector_group_index(bucket_c)
    if gi == gj:
        return GAMMA_SECTOR_SAME
    key = (gi, gj) if gi < gj else (gj, gi)
    return GAMMA_SECTOR_TABLE4[key]


def _build_inter_bucket_matrix() -> dict[tuple[int, int], float]:
    """Build the 20x20 inter-bucket correlation matrix per ERBA NPR §__.209(b)(2).

    ``gamma_bc = gamma_rating(b, c) x gamma_sector(b, c)`` for ``b != c``;
    the diagonal is 1.0.

    Returns:
        Dictionary mapping ``(bucket_b, bucket_c)`` to gamma_bc.
    """
    matrix: dict[tuple[int, int], float] = {}
    for b in ALL_BUCKETS:
        for c in ALL_BUCKETS:
            if b == c:
                matrix[(b, c)] = 1.0
            else:
                matrix[(b, c)] = compute_gamma_rating(b, c) * compute_gamma_sector(b, c)
    return matrix


INTER_BUCKET_CORRELATIONS: dict[tuple[int, int], float] = _build_inter_bucket_matrix()


def get_inter_bucket_correlation(bucket_b: int, bucket_c: int) -> float:
    """Look up gamma_bc between two CSR non-sec buckets.

    ERBA NPR §__.209(b)(2): ``gamma_bc = gamma_rating x gamma_sector``.

    Args:
        bucket_b: First bucket number (1-20).
        bucket_c: Second bucket number (1-20).

    Returns:
        Inter-bucket correlation gamma_bc (medium scenario).
    """
    return INTER_BUCKET_CORRELATIONS[(bucket_b, bucket_c)]


def apply_correlation_scenario(
    rho: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply the correlation scenario adjustment per ERBA NPR §__.206.

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
        rho: Base (medium) correlation value.
        scenario: One of LOW / MEDIUM / HIGH.
        is_inter_bucket: Whether this is an inter-bucket correlation
            (the same scaling applies; kept for API symmetry).

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
) -> np.ndarray:
    """Build the delta intra-bucket correlation matrix for a CSR non-sec bucket.

    Each entry corresponds to a sensitivity identified by its
    (issuer, tenor, curve) triple; the correlation between entries *i* and
    *j* is ``rho_name x rho_tenor x rho_basis`` per ERBA NPR §__.209(b)(2),
    scenario-adjusted per §__.206.

    Args:
        bucket: Bucket number (1-20).
        issuers: Issuer name / ID for each sensitivity (length *n*).
        tenors: Tenor in years for each sensitivity (length *n*).
        curves: Curve label for each sensitivity (length *n*).
        scenario: Correlation scenario to apply.

    Returns:
        Symmetric ``numpy.ndarray`` of shape ``(n, n)``.
    """
    n = len(issuers)
    corr = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_intra_bucket_correlation(
                bucket=bucket,
                tenor_k=tenors[i],
                tenor_l=tenors[j],
                same_issuer=(issuers[i] == issuers[j]),
                same_curve=(curves[i] == curves[j]),
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho
    return corr


def build_csr_nonsec_curvature_correlation_matrix(
    bucket: int,
    issuers: list[str],
    curves: list[str],
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> np.ndarray:
    """Build the curvature intra-bucket correlation matrix (rho squared).

    Per ERBA NPR §__.209(d) the curvature correlation is the square of the
    delta correlation; per §__.206 the scenario scaling is applied to the
    delta correlation BEFORE squaring.

    Args:
        bucket: Bucket number (1-20).
        issuers: Issuer name / ID for each curvature factor.
        curves: Curve label for each curvature factor.
        scenario: Correlation scenario to apply.

    Returns:
        Symmetric ``numpy.ndarray`` of shape ``(n, n)`` holding rho_kl^2.
    """
    n = len(issuers)
    corr = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_name_correlation(bucket, issuers[i] == issuers[j]) * (
                compute_basis_correlation(curves[i] == curves[j])
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho ** 2
            corr[j, i] = rho ** 2
    return corr


def build_csr_nonsec_vega_correlation_matrix(
    bucket: int,
    issuers: list[str],
    option_maturities: list[float],
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> np.ndarray:
    """Build the vega intra-bucket correlation matrix per ERBA NPR §__.209(c).

    Args:
        bucket: Bucket number (1-20).
        issuers: Underlying name for each vega factor.
        option_maturities: Option maturity in years for each vega factor.
        scenario: Correlation scenario to apply.

    Returns:
        Symmetric ``numpy.ndarray`` of shape ``(n, n)``.
    """
    n = len(issuers)
    corr = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_vega_correlation(
                bucket=bucket,
                option_maturity_k=option_maturities[i],
                option_maturity_l=option_maturities[j],
                same_issuer=(issuers[i] == issuers[j]),
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho
    return corr
