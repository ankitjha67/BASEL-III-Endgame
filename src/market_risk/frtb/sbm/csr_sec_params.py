"""CSR Securitization regulatory parameters -- ERBA NPR §__.208(d)-(e), §__.209(b)(3)-(4).

All risk weights, correlations and regulatory constants for the two Credit
Spread Risk -- Securitization risk classes under the FRTB
Sensitivities-Based Method as re-proposed by the US agencies in March 2026
(ERBA NPR, "Regulatory Capital Rule: Category I and II Banking
Organizations"):

* CSR securitization **correlation trading portfolio (CTP)** --
  §__.209(b)(3), Table 5 (16 buckets), Table 6 (gamma_sector);
* CSR securitization **non-CTP** -- §__.209(b)(4), Table 7 (25 buckets),
  gamma_bc = 0 %.

Citations in this module:

* §__.208(d)-(e) -- CSR sec (CTP / non-CTP) delta risk factors (tenor
                    vertices 0.5, 1, 3, 5, 10) and vega risk factors
* §__.209(b)(3)  -- Table 5 CTP buckets / delta RWs, intra-bucket rho,
                    gamma_rating and Table 6 gamma_sector
* §__.209(b)(4)  -- Table 7 non-CTP buckets / delta RWs, intra-bucket rho
                    (tranche x tenor x basis), gamma_bc = 0 %
* §__.209(c)     -- Vega risk weights (Table 11: 100 %) and correlations
* §__.209(d)     -- Curvature risk weights and correlations
* §__.206        -- Correlation scenarios (low / medium / high)
"""
from __future__ import annotations

import math

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    CreditQuality,
    CSRSecAssetType,
    CSRSecSeniority,
    CSRSector,
)

# ---------------------------------------------------------------------------
# Standard tenor vertices (years) -- ERBA NPR §__.208(d)(1), (e)(1)
# ---------------------------------------------------------------------------
TENORS: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]

_IG: frozenset[CreditQuality] = frozenset({CreditQuality.INVESTMENT_GRADE})
_SPEC: frozenset[CreditQuality] = frozenset({CreditQuality.SPECULATIVE_GRADE})
_SPEC_AND_SUBSPEC: frozenset[CreditQuality] = frozenset(
    {CreditQuality.SPECULATIVE_GRADE, CreditQuality.SUB_SPECULATIVE_GRADE}
)
_SUBSPEC: frozenset[CreditQuality] = frozenset({CreditQuality.SUB_SPECULATIVE_GRADE})
_ANY: frozenset[CreditQuality] = frozenset(CreditQuality)


# ===========================================================================
#  NON-CTP PARAMETERS -- ERBA NPR §__.209(b)(4)
# ===========================================================================

# Asset-type order within each seniority / quality group of Table 7.
_NON_CTP_ASSET_ORDER: tuple[CSRSecAssetType, ...] = (
    CSRSecAssetType.RMBS_PRIME,
    CSRSecAssetType.RMBS_MIDPRIME,
    CSRSecAssetType.RMBS_SUBPRIME,
    CSRSecAssetType.CMBS,
    CSRSecAssetType.ABS_STUDENT_LOANS,
    CSRSecAssetType.ABS_CREDIT_CARDS_PERSONAL,
    CSRSecAssetType.ABS_AUTO_FLOORPLAN,
    CSRSecAssetType.CLO_NON_CTP,
)

# Bucket -> (seniority or None for "any", credit qualities, asset type)
NON_CTP_BUCKET_DEFINITIONS: dict[
    int, tuple[CSRSecSeniority | None, frozenset[CreditQuality], CSRSecAssetType]
] = {
    # Senior, investment grade (1-8)
    **{
        i + 1: (CSRSecSeniority.SENIOR, _IG, asset)
        for i, asset in enumerate(_NON_CTP_ASSET_ORDER)
    },
    # Non-senior, investment grade (9-16)
    **{
        i + 9: (CSRSecSeniority.NON_SENIOR, _IG, asset)
        for i, asset in enumerate(_NON_CTP_ASSET_ORDER)
    },
    # Speculative & sub-speculative grade, any seniority (17-24)
    **{
        i + 17: (None, _SPEC_AND_SUBSPEC, asset)
        for i, asset in enumerate(_NON_CTP_ASSET_ORDER)
    },
    # Other sector (25)
    25: (None, _ANY, CSRSecAssetType.OTHER),
}

# ---------------------------------------------------------------------------
# Non-CTP delta risk weights -- ERBA NPR §__.209(b)(4) Table 7
# ---------------------------------------------------------------------------
CSR_SEC_NON_CTP_RW: dict[int, float] = {
    # Senior IG
    1:  0.0090,  # 0.90% prime RMBS
    2:  0.0150,  # 1.50% mid-prime RMBS
    3:  0.0200,  # 2.00% sub-prime RMBS
    4:  0.0200,  # 2.00% CMBS
    5:  0.0080,  # 0.80% ABS student loans
    6:  0.0120,  # 1.20% ABS credit cards & personal loans
    7:  0.0120,  # 1.20% ABS auto & dealer floorplan
    8:  0.0140,  # 1.40% CLO non-CTP
    # Non-senior IG
    9:  0.0113,  # 1.13% prime RMBS
    10: 0.0188,  # 1.88% mid-prime RMBS
    11: 0.0250,  # 2.50% sub-prime RMBS
    12: 0.0250,  # 2.50% CMBS
    13: 0.0100,  # 1.00% ABS student loans
    14: 0.0150,  # 1.50% ABS credit cards & personal loans
    15: 0.0150,  # 1.50% ABS auto & dealer floorplan
    16: 0.0175,  # 1.75% CLO non-CTP
    # Speculative & sub-speculative grade
    17: 0.0158,  # 1.58% prime RMBS
    18: 0.0263,  # 2.63% mid-prime RMBS
    19: 0.0350,  # 3.50% sub-prime RMBS
    20: 0.0350,  # 3.50% CMBS
    21: 0.0140,  # 1.40% ABS student loans
    22: 0.0210,  # 2.10% ABS credit cards & personal loans
    23: 0.0210,  # 2.10% ABS auto & dealer floorplan
    24: 0.0245,  # 2.45% CLO non-CTP
    # Other
    25: 0.0350,  # 3.50% other sector
}

_ASSET_LABEL: dict[CSRSecAssetType, str] = {
    CSRSecAssetType.RMBS_PRIME: "prime RMBS",
    CSRSecAssetType.RMBS_MIDPRIME: "mid-prime RMBS",
    CSRSecAssetType.RMBS_SUBPRIME: "sub-prime RMBS",
    CSRSecAssetType.CMBS: "CMBS",
    CSRSecAssetType.ABS_STUDENT_LOANS: "ABS student loans",
    CSRSecAssetType.ABS_CREDIT_CARDS_PERSONAL: "ABS credit cards & personal loans",
    CSRSecAssetType.ABS_AUTO_FLOORPLAN: "ABS auto & dealer floorplan",
    CSRSecAssetType.CLO_NON_CTP: "CLO non-CTP",
    CSRSecAssetType.OTHER: "Other sector",
}

NON_CTP_BUCKET_NAMES: dict[int, str] = {
    **{i + 1: f"Senior IG - {_ASSET_LABEL[a]}" for i, a in enumerate(_NON_CTP_ASSET_ORDER)},
    **{i + 9: f"Non-senior IG - {_ASSET_LABEL[a]}" for i, a in enumerate(_NON_CTP_ASSET_ORDER)},
    **{i + 17: f"Spec & sub-spec - {_ASSET_LABEL[a]}" for i, a in enumerate(_NON_CTP_ASSET_ORDER)},
    25: "Other sector",
}

OTHER_SECTOR_BUCKET_NON_CTP: int = 25
NON_CTP_BUCKETS: tuple[int, ...] = tuple(range(1, 26))

# ---------------------------------------------------------------------------
# Non-CTP intra-bucket correlation -- ERBA NPR §__.209(b)(4)
#   rho_kl = rho_tranche x rho_tenor x rho_basis   (buckets 1-24)
#   bucket 25: K_b = sum |WS_k|
# ---------------------------------------------------------------------------
RHO_TRANCHE_SAME: float = 1.0        # same bucket AND same tranche (>80 % notional overlap)
RHO_TRANCHE_DIFF: float = 0.40       # otherwise
TRANCHE_NOTIONAL_OVERLAP_THRESHOLD: float = 0.80  # "same tranche" notional-overlap test
RHO_TENOR_SAME_NON_CTP: float = 1.0
RHO_TENOR_DIFF_NON_CTP: float = 0.80
RHO_BASIS_SAME_CURVE_NON_CTP: float = 1.0
RHO_BASIS_DIFF_CURVE_NON_CTP: float = 0.999

# ---------------------------------------------------------------------------
# Non-CTP inter-bucket correlation -- ERBA NPR §__.209(b)(4): gamma_bc = 0 %
# ---------------------------------------------------------------------------
GAMMA_NON_CTP: float = 0.0


# ===========================================================================
#  CTP PARAMETERS -- ERBA NPR §__.209(b)(3)
# ===========================================================================

# ---------------------------------------------------------------------------
# CTP bucket taxonomy -- ERBA NPR §__.209(b)(3) Table 5
#
# TODO: VERIFY -- Table 5 labels buckets 8-9 "Speculative grade" and gives no
#   dedicated sub-speculative-grade bucket for PSEs; only sovereigns receive
#   one (bucket 15).  Pending agency clarification, sub-speculative-grade
#   PSEs are mapped to bucket 9 (the highest-RW bucket of that sector).
# ---------------------------------------------------------------------------
CTP_BUCKET_SECTOR_QUALITY: dict[int, tuple[CSRSector, frozenset[CreditQuality]]] = {
    # Investment grade
    1:  (CSRSector.SOVEREIGN,            _IG),
    2:  (CSRSector.PSE,                  _IG),
    3:  (CSRSector.FINANCIALS,           _IG),
    4:  (CSRSector.BASIC_MATERIALS,      _IG),
    5:  (CSRSector.CONSUMER,             _IG),
    6:  (CSRSector.TECH_TELECOM,         _IG),
    7:  (CSRSector.HEALTHCARE_UTILITIES, _IG),
    # Speculative grade (see TODO: VERIFY above for sub-speculative PSEs)
    8:  (CSRSector.SOVEREIGN,            _SPEC),
    9:  (CSRSector.PSE,                  _SPEC_AND_SUBSPEC),
    # Speculative & sub-speculative grade
    10: (CSRSector.FINANCIALS,           _SPEC_AND_SUBSPEC),
    11: (CSRSector.BASIC_MATERIALS,      _SPEC_AND_SUBSPEC),
    12: (CSRSector.CONSUMER,             _SPEC_AND_SUBSPEC),
    13: (CSRSector.TECH_TELECOM,         _SPEC_AND_SUBSPEC),
    14: (CSRSector.HEALTHCARE_UTILITIES, _SPEC_AND_SUBSPEC),
    # Sub-speculative grade
    15: (CSRSector.SOVEREIGN,            _SUBSPEC),
    # Other sector
    16: (CSRSector.OTHER,                _ANY),
}

# ---------------------------------------------------------------------------
# CTP delta risk weights -- ERBA NPR §__.209(b)(3) Table 5
# ---------------------------------------------------------------------------
CSR_SEC_CTP_RW: dict[int, float] = {
    1:  0.04,   # 4.0%  IG sovereigns / MDBs / supranationals
    2:  0.04,   # 4.0%  IG PSEs, gov-backed non-financials, GSE debt, education, public admin
    3:  0.08,   # 8.0%  IG financials incl. gov-backed financials
    4:  0.05,   # 5.0%  IG basic materials, energy, industrials, ...
    5:  0.04,   # 4.0%  IG consumer goods & services, transport, ...
    6:  0.03,   # 3.0%  IG technology, telecommunications
    7:  0.02,   # 2.0%  IG health care, utilities, professional
    8:  0.13,   # 13.0% Speculative sovereigns
    9:  0.13,   # 13.0% Speculative PSEs ...
    10: 0.16,   # 16.0% Spec & sub-spec financials
    11: 0.10,   # 10.0% Spec & sub-spec basic materials ...
    12: 0.12,   # 12.0% Spec & sub-spec consumer ...
    13: 0.12,   # 12.0% Spec & sub-spec technology, telecommunications
    14: 0.12,   # 12.0% Spec & sub-spec health care, utilities, professional
    15: 0.16,   # 16.0% Sub-speculative sovereigns
    16: 0.13,   # 13.0% Other sector
}

CTP_BUCKET_NAMES: dict[int, str] = {
    1:  "IG - Sovereigns, central banks, MDBs, supranationals",
    2:  "IG - PSEs, gov-backed non-financials, GSE debt, education, public administration",
    3:  "IG - Financials incl. gov-backed financials",
    4:  "IG - Basic materials, energy, industrials, agriculture, manufacturing, mining",
    5:  "IG - Consumer goods & services, transport & storage, administrative & support",
    6:  "IG - Technology, telecommunications",
    7:  "IG - Health care, utilities, professional & technical activities",
    8:  "Speculative - Sovereigns, central banks, MDBs, supranationals",
    9:  "Speculative - PSEs, gov-backed non-financials, education, public administration",
    10: "Spec & sub-spec - Financials incl. gov-backed financials",
    11: "Spec & sub-spec - Basic materials, energy, industrials, agriculture, manufacturing, "
        "mining",
    12: "Spec & sub-spec - Consumer goods & services, transport & storage, administrative & "
        "support",
    13: "Spec & sub-spec - Technology, telecommunications",
    14: "Spec & sub-spec - Health care, utilities, professional & technical activities",
    15: "Sub-speculative - Sovereigns, central banks, MDBs, supranationals",
    16: "Other sector",
}

OTHER_SECTOR_BUCKET_CTP: int = 16
CTP_BUCKETS: tuple[int, ...] = tuple(range(1, 17))
CTP_SINGLE_NAME_BUCKETS: frozenset[int] = frozenset(range(1, 16))

# ---------------------------------------------------------------------------
# CTP intra-bucket correlation -- ERBA NPR §__.209(b)(3)
#   rho_kl = rho_name x rho_tenor x rho_basis   (buckets 1-15)
#   bucket 16: K_b = sum |WS_k|
# ---------------------------------------------------------------------------
RHO_CTP_NAME_SAME: float = 1.0
RHO_CTP_NAME_DIFF: float = 0.35
RHO_CTP_TENOR_SAME: float = 1.0
RHO_CTP_TENOR_DIFF: float = 0.65
RHO_CTP_BASIS_SAME_CURVE: float = 1.0
RHO_CTP_BASIS_DIFF_CURVE: float = 0.99   # NB: 99 %, not 99.9 % as in non-sec / non-CTP

# ---------------------------------------------------------------------------
# CTP inter-bucket correlation -- ERBA NPR §__.209(b)(3)
#   gamma_bc = gamma_rating x gamma_sector (Table 6)
# ---------------------------------------------------------------------------
GAMMA_CTP_RATING_DIFFERENT_QUALITY: float = 0.50
GAMMA_CTP_RATING_SAME_QUALITY: float = 1.0
GAMMA_CTP_SECTOR_SAME: float = 1.0

CTP_SECTOR_GROUPS: tuple[frozenset[int], ...] = (
    frozenset({1, 8, 15}),   # 0: sovereigns / MDBs / supranationals
    frozenset({2, 9}),       # 1: PSEs ...
    frozenset({3, 10}),      # 2: financials
    frozenset({4, 11}),      # 3: basic materials ...
    frozenset({5, 12}),      # 4: consumer ...
    frozenset({6, 13}),      # 5: technology, telecommunications
    frozenset({7, 14}),      # 6: health care, utilities, professional
    frozenset({16}),         # 7: other sector
)

# Table 6 gamma_sector (upper triangle keyed by sector-group index pair).
GAMMA_SECTOR_TABLE6: dict[tuple[int, int], float] = {
    # {1,8,15} row
    (0, 1): 0.75, (0, 2): 0.10, (0, 3): 0.20, (0, 4): 0.25, (0, 5): 0.20, (0, 6): 0.15,
    (0, 7): 0.00,
    # {2,9} row
    (1, 2): 0.05, (1, 3): 0.15, (1, 4): 0.20, (1, 5): 0.15, (1, 6): 0.10, (1, 7): 0.00,
    # {3,10} row
    (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.05, (2, 7): 0.00,
    # {4,11} row
    (3, 4): 0.20, (3, 5): 0.25, (3, 6): 0.05, (3, 7): 0.00,
    # {5,12} row
    (4, 5): 0.25, (4, 6): 0.05, (4, 7): 0.00,
    # {6,13} row
    (5, 6): 0.05, (5, 7): 0.00,
    # {7,14} row
    (6, 7): 0.00,
}


# ===========================================================================
#  VEGA PARAMETERS -- ERBA NPR §__.208(d)(2), (e)(2), §__.209(c) Table 11
# ===========================================================================
VEGA_RISK_WEIGHT: float = 1.0  # 100 % for CSR CTP and CSR sec non-CTP
VEGA_OPTION_MATURITIES: list[float] = [0.5, 1.0, 3.0, 5.0, 10.0]
VEGA_ALPHA: float = 0.01  # alpha in exp(-alpha |Tk - Tl| / min(Tk, Tl))


# ===========================================================================
#  HELPER FUNCTIONS -- bucket lookup
# ===========================================================================

def get_non_ctp_bucket(
    seniority: CSRSecSeniority,
    quality: CreditQuality,
    asset_type: CSRSecAssetType,
) -> int:
    """Look up the CSR sec non-CTP bucket per ERBA NPR §__.209(b)(4) Table 7.

    Senior IG tranches map to 1-8, non-senior IG to 9-16, speculative and
    sub-speculative grade (any seniority) to 17-24; ``OTHER`` asset type
    maps to bucket 25 irrespective of seniority / quality.

    Args:
        seniority: Tranche seniority.
        quality: Internally-assessed credit quality of the tranche.
        asset_type: Underlying asset type.

    Returns:
        Bucket number (1-25).

    Raises:
        ValueError: If no Table 7 bucket matches.
    """
    if asset_type == CSRSecAssetType.OTHER:
        return OTHER_SECTOR_BUCKET_NON_CTP
    for bucket, (sen, qualities, asset) in NON_CTP_BUCKET_DEFINITIONS.items():
        if asset != asset_type or quality not in qualities:
            continue
        if sen is None or sen == seniority:
            return bucket
    raise ValueError(
        f"No CSR sec non-CTP bucket for seniority={seniority.value}, "
        f"quality={quality.value}, asset_type={asset_type.value}"
    )


def get_ctp_bucket_for_sector_quality(
    sector: CSRSector,
    quality: CreditQuality,
) -> int:
    """Look up the CSR CTP bucket per ERBA NPR §__.209(b)(3) Table 5.

    Args:
        sector: Sector of the reference name(s).
        quality: Internally-assessed credit quality.

    Returns:
        Bucket number (1-16).

    Raises:
        ValueError: If no Table 5 bucket matches (e.g. covered bonds and
            index sectors do not exist in the CTP taxonomy).
    """
    for bucket, (s, qualities) in CTP_BUCKET_SECTOR_QUALITY.items():
        if s == sector and quality in qualities:
            return bucket
    raise ValueError(
        f"No CSR CTP bucket for sector={sector.value}, quality={quality.value}"
    )


def get_non_ctp_risk_weight(bucket: int) -> float:
    """Get the delta risk weight for a CSR sec non-CTP bucket (Table 7).

    ERBA NPR §__.209(b)(4).  Uniform across the five tenor vertices.

    Args:
        bucket: Bucket number (1-25).

    Returns:
        Risk weight as a decimal (e.g. ``0.009`` for 0.90 %).

    Raises:
        KeyError: If *bucket* is not a valid non-CTP bucket.
    """
    return CSR_SEC_NON_CTP_RW[bucket]


def get_ctp_risk_weight(bucket: int) -> float:
    """Get the delta risk weight for a CSR CTP bucket (Table 5).

    ERBA NPR §__.209(b)(3).  Uniform across the five tenor vertices.

    Args:
        bucket: Bucket number (1-16).

    Returns:
        Risk weight as a decimal (e.g. ``0.16`` for 16.0 %).

    Raises:
        KeyError: If *bucket* is not a valid CTP bucket.
    """
    return CSR_SEC_CTP_RW[bucket]


def get_curvature_risk_weight(bucket: int, is_ctp: bool = False) -> float:
    """Get the curvature risk weight per ERBA NPR §__.209(d).

    The curvature shock is a parallel shift by the HIGHEST delta risk
    weight in the bucket; CSR sec delta RWs are tenor-uniform so this is
    the bucket's delta RW.

    Args:
        bucket: Bucket number.
        is_ctp: Whether the bucket is a CTP bucket.

    Returns:
        Curvature risk weight as a decimal.
    """
    return get_ctp_risk_weight(bucket) if is_ctp else get_non_ctp_risk_weight(bucket)


def is_other_sector_bucket(bucket: int, is_ctp: bool = False) -> bool:
    """Whether *bucket* is the residual "other sector" bucket.

    ERBA NPR §__.209(b)(3) (bucket 16) and §__.209(b)(4) (bucket 25):
    the intra-bucket charge of these buckets is ``sum |WS_k|``.

    Args:
        bucket: Bucket number.
        is_ctp: Whether the bucket is a CTP bucket.

    Returns:
        True for the other-sector bucket of the given sub-class.
    """
    return bucket == (OTHER_SECTOR_BUCKET_CTP if is_ctp else OTHER_SECTOR_BUCKET_NON_CTP)


# ===========================================================================
#  HELPER FUNCTIONS -- intra-bucket correlation components
# ===========================================================================

def compute_tenor_correlation(
    tenor_k: float,
    tenor_l: float,
    is_ctp: bool = False,
) -> float:
    """Compute rho_tenor per ERBA NPR §__.209(b)(3) / (b)(4).

    100 % for the same tenor vertex; otherwise 65 % (CTP) or 80 % (non-CTP).

    Args:
        tenor_k: Tenor vertex of risk factor *k* in years.
        tenor_l: Tenor vertex of risk factor *l* in years.
        is_ctp: Whether to use CTP parameters.

    Returns:
        Tenor correlation component.
    """
    if tenor_k == tenor_l:
        return RHO_CTP_TENOR_SAME if is_ctp else RHO_TENOR_SAME_NON_CTP
    return RHO_CTP_TENOR_DIFF if is_ctp else RHO_TENOR_DIFF_NON_CTP


def compute_tranche_correlation(
    same_tranche: bool,
    is_ctp: bool = False,
) -> float:
    """Compute rho_tranche (non-CTP) or rho_name (CTP).

    * Non-CTP, ERBA NPR §__.209(b)(4): 100 % where both sensitivities are
      to the same bucket and the same tranche (more than 80 % notional
      overlap); 40 % otherwise.
    * CTP, §__.209(b)(3): 100 % where the two names are identical; 35 %
      otherwise.

    Args:
        same_tranche: True if both risk factors reference the same tranche
            (non-CTP) or the same name (CTP).
        is_ctp: Whether to use CTP parameters.

    Returns:
        Tranche / name correlation component.
    """
    if is_ctp:
        return RHO_CTP_NAME_SAME if same_tranche else RHO_CTP_NAME_DIFF
    return RHO_TRANCHE_SAME if same_tranche else RHO_TRANCHE_DIFF


def compute_basis_correlation(same_curve: bool, is_ctp: bool = False) -> float:
    """Compute rho_basis per ERBA NPR §__.209(b)(3) / (b)(4).

    100 % where both sensitivities are to the same credit spread curve;
    otherwise 99 % (CTP) or 99.9 % (non-CTP).

    Args:
        same_curve: True if both risk factors reference the same curve.
        is_ctp: Whether to use CTP parameters.

    Returns:
        Basis correlation component.
    """
    if same_curve:
        return RHO_CTP_BASIS_SAME_CURVE if is_ctp else RHO_BASIS_SAME_CURVE_NON_CTP
    return RHO_CTP_BASIS_DIFF_CURVE if is_ctp else RHO_BASIS_DIFF_CURVE_NON_CTP


def compute_intra_bucket_correlation(
    bucket: int,
    tenor_k: float,
    tenor_l: float,
    same_tranche: bool,
    is_ctp: bool = False,
    same_curve: bool = True,
) -> float:
    """Compute the delta intra-bucket correlation rho_kl for CSR securitization.

    .. math::

        \\rho_{kl} = \\rho_{\\mathrm{tranche|name}} \\times
                     \\rho_{\\mathrm{tenor}} \\times
                     \\rho_{\\mathrm{basis}}

    per ERBA NPR §__.209(b)(4) (non-CTP) or §__.209(b)(3) (CTP).  Not
    applicable to the other-sector buckets (25 / 16) whose charge is
    ``sum |WS_k|``; callers must special-case those.

    Args:
        bucket: Bucket number (1-25 non-CTP, 1-16 CTP).
        tenor_k: Tenor of risk factor *k* in years.
        tenor_l: Tenor of risk factor *l* in years.
        same_tranche: Whether both factors reference the same tranche
            (non-CTP) or the same name (CTP).
        is_ctp: Whether to use CTP parameters.
        same_curve: Whether both factors reference the same curve.

    Returns:
        Combined intra-bucket correlation.

    Raises:
        KeyError: If *bucket* is not valid for the sub-class.
    """
    rw_table = CSR_SEC_CTP_RW if is_ctp else CSR_SEC_NON_CTP_RW
    if bucket not in rw_table:
        raise KeyError(
            f"Bucket {bucket} is not a valid CSR sec {'CTP' if is_ctp else 'non-CTP'} bucket"
        )
    return (
        compute_tranche_correlation(same_tranche, is_ctp=is_ctp)
        * compute_tenor_correlation(tenor_k, tenor_l, is_ctp=is_ctp)
        * compute_basis_correlation(same_curve, is_ctp=is_ctp)
    )


def compute_curvature_correlation(
    same_tranche: bool,
    is_ctp: bool = False,
    same_curve: bool = True,
) -> float:
    """Compute the curvature intra-bucket correlation per ERBA NPR §__.209(d).

    Curvature risk factors are parallel shifts of a tranche's / name's whole
    curve, so the tenor dimension collapses: the delta correlation reduces
    to ``rho_tranche|name x rho_basis`` and the curvature correlation is its
    square.

    Args:
        same_tranche: Whether both factors reference the same tranche / name.
        is_ctp: Whether to use CTP parameters.
        same_curve: Whether both factors reference the same curve.

    Returns:
        Squared delta correlation (before scenario adjustment).
    """
    rho = compute_tranche_correlation(same_tranche, is_ctp=is_ctp) * (
        compute_basis_correlation(same_curve, is_ctp=is_ctp)
    )
    return rho ** 2


def compute_vega_correlation(
    option_maturity_k: float,
    option_maturity_l: float,
    same_tranche: bool,
    is_ctp: bool = False,
) -> float:
    """Compute the vega intra-bucket correlation per ERBA NPR §__.209(c).

    .. math::

        \\rho_{kl} = \\min\\bigl(\\rho^{\\mathrm{delta}}_{kl}
            \\times e^{-\\alpha |T_k - T_l| / \\min(T_k, T_l)},\\; 1\\bigr)

    where ``rho_delta`` is the tranche (non-CTP) / name (CTP) correlation of
    the underlyings, ``T`` the option maturity and ``alpha = 1 %``.

    Args:
        option_maturity_k: Option maturity of vega factor *k* in years.
        option_maturity_l: Option maturity of vega factor *l* in years.
        same_tranche: Whether both factors reference the same tranche / name.
        is_ctp: Whether to use CTP parameters.

    Returns:
        Vega correlation (capped at 100 %).
    """
    rho_delta = compute_tranche_correlation(same_tranche, is_ctp=is_ctp)
    if option_maturity_k == option_maturity_l:
        rho_opt = 1.0
    else:
        rho_opt = math.exp(
            -VEGA_ALPHA
            * abs(option_maturity_k - option_maturity_l)
            / min(option_maturity_k, option_maturity_l)
        )
    return min(rho_delta * rho_opt, 1.0)


# ===========================================================================
#  HELPER FUNCTIONS -- inter-bucket correlation
# ===========================================================================

def _ctp_sector_group_index(bucket: int) -> int:
    """Return the Table 6 sector-group index (0-7) for a CTP bucket.

    ERBA NPR §__.209(b)(3) Table 6.

    Args:
        bucket: CTP bucket number (1-16).

    Returns:
        0-based index into :data:`CTP_SECTOR_GROUPS`.

    Raises:
        KeyError: If *bucket* is not a valid CTP bucket.
    """
    for idx, group in enumerate(CTP_SECTOR_GROUPS):
        if bucket in group:
            return idx
    raise KeyError(f"Bucket {bucket} is not a valid CSR CTP bucket (1-16)")


def get_ctp_credit_quality_category(bucket: int) -> str | None:
    """Return the gamma_rating credit-quality category of a CTP bucket.

    ERBA NPR §__.209(b)(3): investment grade (1-7) versus speculative /
    sub-speculative grade (8-15), the latter two counting as ONE category.
    Bucket 16 is outside the rating factor.

    Args:
        bucket: CTP bucket number (1-16).

    Returns:
        ``"IG"``, ``"NON_IG"`` or ``None`` for bucket 16.
    """
    if bucket not in CSR_SEC_CTP_RW:
        raise KeyError(f"Bucket {bucket} is not a valid CSR CTP bucket (1-16)")
    if bucket == OTHER_SECTOR_BUCKET_CTP:
        return None
    return "IG" if CTP_BUCKET_SECTOR_QUALITY[bucket][1] == _IG else "NON_IG"


def compute_ctp_gamma_rating(bucket_b: int, bucket_c: int) -> float:
    """Compute gamma_rating for CTP per ERBA NPR §__.209(b)(3).

    50 % where buckets *b* and *c* (both within 1-15) fall in different
    credit-quality categories (speculative and sub-speculative grade count
    as one category); 100 % otherwise.

    Args:
        bucket_b: First CTP bucket (1-16).
        bucket_c: Second CTP bucket (1-16).

    Returns:
        Rating component of gamma_bc.
    """
    cat_b = get_ctp_credit_quality_category(bucket_b)
    cat_c = get_ctp_credit_quality_category(bucket_c)
    if cat_b is None or cat_c is None or cat_b == cat_c:
        return GAMMA_CTP_RATING_SAME_QUALITY
    return GAMMA_CTP_RATING_DIFFERENT_QUALITY


def compute_ctp_gamma_sector(bucket_b: int, bucket_c: int) -> float:
    """Compute gamma_sector for CTP per ERBA NPR §__.209(b)(3) Table 6.

    100 % where the two buckets belong to the same sector group, otherwise
    the Table 6 entry.

    Args:
        bucket_b: First CTP bucket (1-16).
        bucket_c: Second CTP bucket (1-16).

    Returns:
        Sector component of gamma_bc.
    """
    gi = _ctp_sector_group_index(bucket_b)
    gj = _ctp_sector_group_index(bucket_c)
    if gi == gj:
        return GAMMA_CTP_SECTOR_SAME
    key = (gi, gj) if gi < gj else (gj, gi)
    return GAMMA_SECTOR_TABLE6[key]


def _build_ctp_inter_bucket_matrix() -> dict[tuple[int, int], float]:
    """Build the 16x16 CTP inter-bucket correlation matrix per ERBA NPR §__.209(b)(3).

    Returns:
        Dictionary mapping ``(bucket_b, bucket_c)`` to gamma_bc.
    """
    matrix: dict[tuple[int, int], float] = {}
    for b in CTP_BUCKETS:
        for c in CTP_BUCKETS:
            if b == c:
                matrix[(b, c)] = 1.0
            else:
                matrix[(b, c)] = compute_ctp_gamma_rating(b, c) * compute_ctp_gamma_sector(b, c)
    return matrix


CTP_INTER_BUCKET_CORRELATIONS: dict[tuple[int, int], float] = _build_ctp_inter_bucket_matrix()


def get_ctp_inter_bucket_correlation(bucket_b: int, bucket_c: int) -> float:
    """Look up gamma_bc between two CTP buckets per ERBA NPR §__.209(b)(3).

    Args:
        bucket_b: First CTP bucket (1-16).
        bucket_c: Second CTP bucket (1-16).

    Returns:
        Inter-bucket correlation (medium scenario).
    """
    return CTP_INTER_BUCKET_CORRELATIONS[(bucket_b, bucket_c)]


def get_inter_bucket_correlation(
    bucket_b: int,
    bucket_c: int,
    is_ctp: bool = False,
) -> float:
    """Get the inter-bucket correlation gamma_bc for CSR securitization.

    * Non-CTP, ERBA NPR §__.209(b)(4): 0 % between any two buckets.
    * CTP, ERBA NPR §__.209(b)(3): ``gamma_rating x gamma_sector`` (Table 6).

    Args:
        bucket_b: First bucket number.
        bucket_c: Second bucket number.
        is_ctp: Whether to use CTP inter-bucket correlation.

    Returns:
        Inter-bucket correlation (medium scenario).
    """
    if is_ctp:
        return get_ctp_inter_bucket_correlation(bucket_b, bucket_c)
    if bucket_b not in CSR_SEC_NON_CTP_RW or bucket_c not in CSR_SEC_NON_CTP_RW:
        raise KeyError(
            f"Buckets ({bucket_b}, {bucket_c}) are not valid CSR sec non-CTP buckets (1-25)"
        )
    return GAMMA_NON_CTP


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


# ===========================================================================
#  HELPER FUNCTIONS -- correlation matrices
# ===========================================================================

def build_csr_sec_correlation_matrix(
    bucket: int,
    tranches: list[str],
    tenors: list[float],
    is_ctp: bool = False,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
    curves: list[str] | None = None,
) -> np.ndarray:
    """Build the delta intra-bucket correlation matrix for a CSR sec bucket.

    Each entry corresponds to a sensitivity identified by its
    (tranche|name, tenor, curve) triple; the correlation between entries
    *i* and *j* is ``rho_tranche|name x rho_tenor x rho_basis`` per ERBA NPR
    §__.209(b)(3)/(4), scenario-adjusted per §__.206.

    Args:
        bucket: Bucket number (1-25 non-CTP, 1-16 CTP).
        tranches: Tranche (non-CTP) or name (CTP) identifier per sensitivity.
        tenors: Tenor in years per sensitivity.
        is_ctp: Whether this is a CTP bucket.
        scenario: Correlation scenario to apply.
        curves: Optional curve label per sensitivity; all-same when omitted.

    Returns:
        Symmetric ``numpy.ndarray`` of shape ``(n, n)``.
    """
    n = len(tranches)
    if curves is None:
        curves = ["DEFAULT"] * n
    corr = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_intra_bucket_correlation(
                bucket=bucket,
                tenor_k=tenors[i],
                tenor_l=tenors[j],
                same_tranche=(tranches[i] == tranches[j]),
                is_ctp=is_ctp,
                same_curve=(curves[i] == curves[j]),
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho
    return corr


def build_csr_sec_curvature_correlation_matrix(
    tranches: list[str],
    is_ctp: bool = False,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
    curves: list[str] | None = None,
) -> np.ndarray:
    """Build the curvature intra-bucket correlation matrix (rho squared).

    Per ERBA NPR §__.209(d) the curvature correlation is the square of the
    delta correlation; per §__.206 the scenario scaling is applied to the
    delta correlation BEFORE squaring.

    Args:
        tranches: Tranche (non-CTP) or name (CTP) identifier per factor.
        is_ctp: Whether this is a CTP bucket.
        scenario: Correlation scenario to apply.
        curves: Optional curve label per factor; all-same when omitted.

    Returns:
        Symmetric ``numpy.ndarray`` of shape ``(n, n)`` holding rho_kl^2.
    """
    n = len(tranches)
    if curves is None:
        curves = ["DEFAULT"] * n
    corr = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_tranche_correlation(tranches[i] == tranches[j], is_ctp=is_ctp) * (
                compute_basis_correlation(curves[i] == curves[j], is_ctp=is_ctp)
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho ** 2
            corr[j, i] = rho ** 2
    return corr


def build_csr_sec_vega_correlation_matrix(
    tranches: list[str],
    option_maturities: list[float],
    is_ctp: bool = False,
    scenario: CorrelationScenario = CorrelationScenario.MEDIUM,
) -> np.ndarray:
    """Build the vega intra-bucket correlation matrix per ERBA NPR §__.209(c).

    Args:
        tranches: Tranche (non-CTP) or name (CTP) identifier per vega factor.
        option_maturities: Option maturity in years per vega factor.
        is_ctp: Whether this is a CTP bucket.
        scenario: Correlation scenario to apply.

    Returns:
        Symmetric ``numpy.ndarray`` of shape ``(n, n)``.
    """
    n = len(tranches)
    corr = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            rho = compute_vega_correlation(
                option_maturity_k=option_maturities[i],
                option_maturity_l=option_maturities[j],
                same_tranche=(tranches[i] == tranches[j]),
                is_ctp=is_ctp,
            )
            rho = apply_correlation_scenario(rho, scenario)
            corr[i, j] = rho
            corr[j, i] = rho
    return corr
