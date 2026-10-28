"""Default risk capital requirement parameters -- ERBA NPR §__.210 (p.901-913).

All loss-given-default rates, Table 1 risk weights, maturity scaling rules,
bucket definitions and the securitization risk-weight conversion for the
FRTB default risk capital requirement under the March 2026 US ERBA NPR.

BCBS d457 MAR22 paragraph numbers are given as cross-references only; the
US text governs wherever the two differ (credit quality categories instead
of external ratings, four non-securitization buckets, SEC-SA x 8% for
securitization risk weights, and the CTP 0.5 factor on negative bucket
amounts).

Monetary inputs are in USD millions ($M) unless stated otherwise.
"""

from __future__ import annotations

import math

from src.core.enums import (
    DRCCreditQuality,
    DRCExposureType,
    DRCRatingCategory,
    DRCSecRating,
    DRCSecSeniority,
    DRCSeniority,
)
from src.core.exceptions import ValidationError
from src.securitization.sec_params import (
    MAX_RISK_WEIGHT as SEC_MAX_RISK_WEIGHT,
)
from src.securitization.sec_params import (
    MIN_RISK_WEIGHT_NON_RESEC as SEC_MIN_RISK_WEIGHT_NON_RESEC,
)
from src.securitization.sec_params import (
    MIN_RISK_WEIGHT_RESEC as SEC_MIN_RISK_WEIGHT_RESEC,
)
from src.securitization.sec_params import (
    P_NON_RESECURITIZATION as SEC_P_NON_RESEC,
)
from src.securitization.sec_params import (
    P_RESECURITIZATION as SEC_P_RESEC,
)
from src.securitization.sec_params import (
    RW_PER_UNIT_CAPITAL as SEC_RW_PER_UNIT_CAPITAL,
)

# ---------------------------------------------------------------------------
#  LGD by seniority / issuer type -- §__.210(b)(1)(iv) (p.903); MAR22.12
# ---------------------------------------------------------------------------

LGD_VALUES: dict[DRCSeniority, float] = {
    DRCSeniority.EQUITY: 1.00,                  # 100% equity
    DRCSeniority.SUBORDINATED: 1.00,            # 100% non-senior debt
    DRCSeniority.SENIOR_UNSECURED: 0.75,        # 75% senior debt
    DRCSeniority.GSE_UNGUARANTEED: 0.75,        # 75% GSE debt issued, not guaranteed
    DRCSeniority.US_PSE: 0.50,                  # 50% positions in a US PSE
    DRCSeniority.GSE_GUARANTEED: 0.25,          # 25% GSE debt guaranteed by the GSE
    DRCSeniority.COVERED_BOND: 0.25,            # 25% covered bonds
    DRCSeniority.NOT_LINKED_TO_RECOVERY: 0.00,  # 0% value not linked to recovery rate
}

DEFAULTED_POSITION_LGD: float = 1.00
"""§__.210(b)(1)(iv): defaulted positions receive a 100% LGD irrespective of seniority."""


# ---------------------------------------------------------------------------
#  Seniority ordering for same-obligor offsetting -- §__.210(b)(1)(v) (p.904)
#
#  A short position may offset a long position in the same obligor only if
#  the short has the SAME or LOWER seniority than the long.  Higher rank =
#  more senior.  The NPR only distinguishes senior / non-senior / equity;
#  the relative ordering of the issuer-type LGD classes below is inferred
#  from their LGD (lower LGD = higher recovery = more senior).
# TODO: VERIFY -- relative ranking of GSE_GUARANTEED / COVERED_BOND (25%),
#   US_PSE (50%) and senior debt (75%) for cross-class offsetting is not
#   spelled out in §__.210(b)(1)(v); conservative LGD-based ordering used.
# ---------------------------------------------------------------------------

DRC_SENIORITY_RANK: dict[DRCSeniority, int] = {
    DRCSeniority.EQUITY: 0,
    DRCSeniority.SUBORDINATED: 1,
    DRCSeniority.SENIOR_UNSECURED: 2,
    DRCSeniority.GSE_UNGUARANTEED: 2,
    DRCSeniority.NOT_LINKED_TO_RECOVERY: 2,
    DRCSeniority.US_PSE: 3,
    DRCSeniority.GSE_GUARANTEED: 4,
    DRCSeniority.COVERED_BOND: 4,
}


# ---------------------------------------------------------------------------
#  Table 1 to §__.210 -- default risk weights by bucket and credit quality
#  (p.906).  MAR22.14 Table 2 (external ratings) is NOT used (Dodd-Frank
#  §939A).
# ---------------------------------------------------------------------------

DRC_RISK_WEIGHTS: dict[DRCExposureType, dict[DRCCreditQuality, float]] = {
    DRCExposureType.NON_US_SOVEREIGN: {
        DRCCreditQuality.INVESTMENT_GRADE: 0.006,       # 0.6%
        DRCCreditQuality.SPECULATIVE_GRADE: 0.220,      # 22.0%
        DRCCreditQuality.SUB_SPECULATIVE_GRADE: 0.500,  # 50.0%
    },
    DRCExposureType.PSE_GSE: {
        DRCCreditQuality.INVESTMENT_GRADE: 0.021,       # 2.1%
        DRCCreditQuality.SPECULATIVE_GRADE: 0.220,      # 22.0%
        DRCCreditQuality.SUB_SPECULATIVE_GRADE: 0.500,  # 50.0%
    },
    DRCExposureType.CORPORATE: {
        DRCCreditQuality.INVESTMENT_GRADE: 0.041,       # 4.1%
        DRCCreditQuality.SPECULATIVE_GRADE: 0.220,      # 22.0%
        DRCCreditQuality.SUB_SPECULATIVE_GRADE: 0.500,  # 50.0%
    },
}

DRC_DEFAULTED_RISK_WEIGHT: float = 1.00
"""Table 1 to §__.210: defaulted positions 100%."""


# ---------------------------------------------------------------------------
#  Rating -> credit quality convenience mapping
# ---------------------------------------------------------------------------

RATING_TO_CREDIT_QUALITY: dict[DRCRatingCategory, DRCCreditQuality] = {
    DRCRatingCategory.AAA: DRCCreditQuality.INVESTMENT_GRADE,
    DRCRatingCategory.AA: DRCCreditQuality.INVESTMENT_GRADE,
    DRCRatingCategory.A: DRCCreditQuality.INVESTMENT_GRADE,
    DRCRatingCategory.BBB: DRCCreditQuality.INVESTMENT_GRADE,
    DRCRatingCategory.BB: DRCCreditQuality.SPECULATIVE_GRADE,
    DRCRatingCategory.B: DRCCreditQuality.SPECULATIVE_GRADE,
    DRCRatingCategory.CCC: DRCCreditQuality.SUB_SPECULATIVE_GRADE,
    DRCRatingCategory.DEFAULTED: DRCCreditQuality.DEFAULTED,
    # TODO: VERIFY -- the NPR has no "unrated" concept: the banking
    #   organization must assign an investment / speculative /
    #   sub-speculative grade internally (§__.2 definitions).  Speculative
    #   grade is used here as a conservative placeholder.
    DRCRatingCategory.UNRATED: DRCCreditQuality.SPECULATIVE_GRADE,
}


# ---------------------------------------------------------------------------
#  Maturity scaling -- §__.210(b)(1)(iii) (p.903); MAR22.13
# ---------------------------------------------------------------------------

MATURITY_CAP_YEARS: float = 1.0
"""Positions with maturity >= 1 year carry a weight of 1 (no scaling)."""

MATURITY_FLOOR_FRACTION: float = 0.25
"""Positions shorter than 3 months are floored at a 3-month (0.25 year) weight."""

MATURITY_FLOOR_THRESHOLD_YEARS: float = 0.25
"""Threshold below which the 3-month floor applies."""

UNHEDGED_CASH_EQUITY_MATURITY_OPTIONS: tuple[float, float] = (0.25, 1.0)
"""§__.210(b)(1)(iii): unhedged cash equity may be assigned 3 months or 1 year."""

UNHEDGED_CASH_EQUITY_MATURITY_DEFAULT: float = 1.0
"""Default maturity assumption for unhedged cash equity (bank's choice; 1 year used)."""


# ---------------------------------------------------------------------------
#  Bucket definitions -- §__.210(b)(2) (p.905)
# ---------------------------------------------------------------------------

DRC_BUCKETS: dict[DRCExposureType, str] = {
    DRCExposureType.NON_US_SOVEREIGN: "NON_US_SOVEREIGN",
    DRCExposureType.PSE_GSE: "PSE_GSE",
    DRCExposureType.CORPORATE: "CORPORATE",
    DRCExposureType.DEFAULTED: "DEFAULTED",
}

DRC_BUCKET_LABELS: list[str] = [
    "NON_US_SOVEREIGN",
    "PSE_GSE",
    "CORPORATE",
    "DEFAULTED",
]

DRC_EXCLUDED_EXPOSURE_TYPES: frozenset[DRCExposureType] = frozenset(
    {DRCExposureType.US_SOVEREIGN_MDB}
)
"""§__.210(a): US sovereign exposures, specified supranationals and MDBs are
not default risk positions (gross default exposure 0)."""


# ---------------------------------------------------------------------------
#  Securitization -- §__.210(c)(3)(ii) and §__.210(d)(3) (p.909-912)
# ---------------------------------------------------------------------------

DRC_SEC_CAPITAL_CONVERSION: float = 0.08
"""§__.210(c)(3)(ii): DRC risk weight for a securitization position = the
banking-book securitization risk weight under §__.132 / §__.133 multiplied
by 8 percent (i.e. risk weight -> capital requirement)."""

CTP_NEGATIVE_BUCKET_FACTOR: float = 0.5
"""§__.210(d)(4): DRC_CTP = max( sum_b [ max(DRC_b, 0) + 0.5 * min(DRC_b, 0) ], 0 ).
The 0.5 factor applies to NEGATIVE bucket-level amounts in the cross-bucket
sum -- not to short positions within a bucket."""

SEC_SA_P_NON_RESEC: float = SEC_P_NON_RESEC
"""§__.133 SSFA supervisory parameter p = 0.5 for non-resecuritization."""

SEC_SA_P_RESEC: float = SEC_P_RESEC
"""§__.133 SSFA supervisory parameter p = 1.5 for resecuritization."""


# ---------------------------------------------------------------------------
#  LEGACY rating x seniority securitization table (BCBS-style, NOT the NPR)
#
# TODO: VERIFY -- this table does not derive from §__.210(c)(3)(ii), which
#   sets the DRC risk weight equal to the banking-book securitization risk
#   weight x 8%.  It is retained ONLY behind the explicit
#   ``legacy_rating_table=True`` switch for back-comparison and is never a
#   silent default.
# ---------------------------------------------------------------------------

LEGACY_DRC_SEC_RISK_WEIGHTS_SENIOR: dict[DRCSecRating, float] = {
    DRCSecRating.AAA: 0.004,
    DRCSecRating.AA: 0.008,
    DRCSecRating.A: 0.016,
    DRCSecRating.BBB: 0.048,
    DRCSecRating.BB: 0.08,
    DRCSecRating.B: 0.16,
    DRCSecRating.CCC: 0.32,
    DRCSecRating.UNRATED: 1.0,
    DRCSecRating.DEFAULTED: 1.0,
}

LEGACY_DRC_SEC_RISK_WEIGHTS_NON_SENIOR: dict[DRCSecRating, float] = {
    DRCSecRating.AAA: 0.01,
    DRCSecRating.AA: 0.02,
    DRCSecRating.A: 0.04,
    DRCSecRating.BBB: 0.08,
    DRCSecRating.BB: 0.16,
    DRCSecRating.B: 0.32,
    DRCSecRating.CCC: 0.64,
    DRCSecRating.UNRATED: 1.0,
    DRCSecRating.DEFAULTED: 1.0,
}


# =========================================================================
#  Helper functions -- non-securitization
# =========================================================================


def get_lgd(
    seniority: DRCSeniority,
    credit_quality: DRCCreditQuality | None = None,
) -> float:
    """Return the LGD fraction per §__.210(b)(1)(iv) (ERBA NPR p.903).

    Args:
        seniority: Capital-structure / issuer-type LGD class.
        credit_quality: Optional credit quality; a DEFAULTED position
            receives 100% LGD regardless of seniority.

    Returns:
        LGD as a decimal (e.g. 0.75 for 75%).

    Raises:
        KeyError: If the seniority is not recognised.
    """
    if credit_quality == DRCCreditQuality.DEFAULTED:
        return DEFAULTED_POSITION_LGD
    return LGD_VALUES[seniority]


def get_seniority_rank(seniority: DRCSeniority) -> int:
    """Return the offsetting rank of a seniority class (higher = more senior).

    Used for the §__.210(b)(1)(v) rule that a short may offset a long of the
    same obligor only when the short's seniority is the same or lower.

    Args:
        seniority: LGD / seniority class.

    Returns:
        Integer rank; higher is more senior.
    """
    return DRC_SENIORITY_RANK[seniority]


def rating_to_credit_quality(rating: DRCRatingCategory) -> DRCCreditQuality:
    """Map a rating-style convenience input to an NPR credit quality category.

    AAA..BBB -> investment grade; BB, B -> speculative grade; CCC ->
    sub-speculative grade; DEFAULTED -> defaulted; UNRATED -> speculative
    grade (``# TODO: VERIFY`` -- see :data:`RATING_TO_CREDIT_QUALITY`).

    Args:
        rating: Rating category.

    Returns:
        The corresponding :class:`DRCCreditQuality`.
    """
    return RATING_TO_CREDIT_QUALITY[rating]


def get_bucket(
    exposure_type: DRCExposureType,
    credit_quality: DRCCreditQuality,
) -> DRCExposureType:
    """Return the §__.210(b)(2) bucket for a position (ERBA NPR p.905).

    Defaulted positions are assigned to the DEFAULTED bucket regardless of
    sector; otherwise the bucket is the position's exposure type.

    Args:
        exposure_type: Non-US sovereign, PSE/GSE or corporate.
        credit_quality: Credit quality category.

    Returns:
        One of NON_US_SOVEREIGN, PSE_GSE, CORPORATE, DEFAULTED.

    Raises:
        KeyError: If the exposure type is not a DRC non-securitization bucket.
    """
    if credit_quality == DRCCreditQuality.DEFAULTED:
        return DRCExposureType.DEFAULTED
    if exposure_type not in DRC_BUCKETS:
        raise KeyError(exposure_type)
    return exposure_type


def get_bucket_label(
    exposure_type: DRCExposureType,
    credit_quality: DRCCreditQuality = DRCCreditQuality.INVESTMENT_GRADE,
) -> str:
    """Map an exposure type (and credit quality) to its DRC bucket label.

    Args:
        exposure_type: Exposure classification.
        credit_quality: Credit quality; DEFAULTED routes to the defaulted bucket.

    Returns:
        Bucket label string per §__.210(b)(2).

    Raises:
        KeyError: If the exposure type has no DRC bucket (e.g. SECURITIZATION
            or the excluded US_SOVEREIGN_MDB type).
    """
    return DRC_BUCKETS[get_bucket(exposure_type, credit_quality)]


def get_risk_weight(
    credit_quality: DRCCreditQuality,
    exposure_type: DRCExposureType = DRCExposureType.CORPORATE,
) -> float:
    """Return the Table 1 to §__.210 default risk weight (ERBA NPR p.906).

    Args:
        credit_quality: Investment / speculative / sub-speculative / defaulted.
        exposure_type: Bucket (non-US sovereign, PSE/GSE, corporate).

    Returns:
        Risk weight as a decimal (e.g. 0.041 for 4.1%).

    Raises:
        KeyError: If the exposure type is not a risk-weighted DRC bucket.
    """
    if credit_quality == DRCCreditQuality.DEFAULTED:
        return DRC_DEFAULTED_RISK_WEIGHT
    if exposure_type == DRCExposureType.DEFAULTED:
        return DRC_DEFAULTED_RISK_WEIGHT
    return DRC_RISK_WEIGHTS[exposure_type][credit_quality]


def compute_maturity_weight(maturity_years: float) -> float:
    """Compute the maturity scaling factor per §__.210(b)(1)(iii) (ERBA NPR p.903).

    .. math::

        w = \\min(M / 1\\text{yr}, 1), \\quad w \\ge 0.25

    Positions with less than one year to maturity are scaled by the fraction
    of a year, floored at three months; positions of one year or more take
    a weight of one.  (MAR22.13 cross-reference.)

    Args:
        maturity_years: Remaining maturity in years (non-negative).

    Returns:
        Maturity weight in [0.25, 1.0].
    """
    if maturity_years <= 0.0:
        return MATURITY_FLOOR_FRACTION
    raw = min(maturity_years / MATURITY_CAP_YEARS, 1.0)
    return max(raw, MATURITY_FLOOR_FRACTION)


# =========================================================================
#  Helper functions -- securitization
# =========================================================================


def get_sec_drc_risk_weight(banking_book_risk_weight: float) -> float:
    """Convert a banking-book securitization risk weight to a DRC risk weight.

    §__.210(c)(3)(ii) / §__.210(d)(3): RW_DRC = RW_{§__.132/§__.133} x 8%.
    A 15% SEC-SA floor position therefore carries 1.2%; a 1,250% position
    carries 100%.

    Args:
        banking_book_risk_weight: Risk weight as a decimal (0.15 for 15%,
            12.5 for 1,250%).

    Returns:
        DRC risk weight as a decimal.

    Raises:
        ValidationError: If the risk weight is negative or above 1,250%.
    """
    if banking_book_risk_weight < 0.0 or banking_book_risk_weight > SEC_MAX_RISK_WEIGHT:
        raise ValidationError(
            f"banking_book_risk_weight must be in [0, {SEC_MAX_RISK_WEIGHT}], "
            f"got {banking_book_risk_weight}"
        )
    return banking_book_risk_weight * DRC_SEC_CAPITAL_CONVERSION


def compute_sec_sa_risk_weight(
    attachment_point: float,
    detachment_point: float,
    k_g: float,
    w: float = 0.0,
    is_resecuritization: bool = False,
) -> float:
    """Compute the SEC-SA (SSFA) banking-book risk weight per §__.133.

    .. math::

        K_A = K_G + W (1 - K_G), \\quad a = -1/(p K_A), \\quad
        u = D - K_A, \\quad l = \\max(A - K_A, 0)

        K_{SSFA} = \\frac{e^{a u} - e^{a l}}{a (u - l)}

    - If D <= K_A the risk weight is 1,250%.
    - If A >= K_A the risk weight is 12.5 x K_SSFA.
    - Otherwise (straddle) RW = 12.5 x [(K_A - A)/(D - A)] +
      12.5 x [(D - K_A)/(D - A)] x K_SSFA(K_A, D).

    The result is floored at 15% (100% for resecuritizations) and capped at
    1,250% per §__.133(d).  Supervisory p = 0.5 (1.5 resecuritization).

    Args:
        attachment_point: Tranche attachment A as a decimal in [0, 1).
        detachment_point: Tranche detachment D as a decimal in (A, 1].
        k_g: Weighted-average capital requirement of the underlying pool
            (RWA x 8% / EAD), as a decimal.
        w: Delinquency ratio W of the underlying pool, decimal in [0, 1].
        is_resecuritization: Use p = 1.5 and the 100% floor.

    Returns:
        Banking-book risk weight as a decimal (e.g. 0.15 for 15%).

    Raises:
        ValidationError: If the inputs are outside their admissible ranges.
    """
    if not 0.0 <= attachment_point < detachment_point <= 1.0:
        raise ValidationError(
            f"Require 0 <= A < D <= 1; got A={attachment_point}, D={detachment_point}"
        )
    if not 0.0 < k_g <= 1.0:
        raise ValidationError(f"k_g must be in (0, 1]; got {k_g}")
    if not 0.0 <= w <= 1.0:
        raise ValidationError(f"w must be in [0, 1]; got {w}")

    p = SEC_SA_P_RESEC if is_resecuritization else SEC_SA_P_NON_RESEC
    floor = SEC_MIN_RISK_WEIGHT_RESEC if is_resecuritization else SEC_MIN_RISK_WEIGHT_NON_RESEC

    k_a = k_g + w * (1.0 - k_g)
    a, d = attachment_point, detachment_point

    if d <= k_a:
        return SEC_MAX_RISK_WEIGHT

    alpha = -1.0 / (p * k_a)
    u = d - k_a
    l_val = max(a - k_a, 0.0)
    try:
        k_ssfa = (math.exp(alpha * u) - math.exp(alpha * l_val)) / (alpha * (u - l_val))
    except (OverflowError, ZeroDivisionError, ValueError):
        return SEC_MAX_RISK_WEIGHT

    if a >= k_a:
        rw = SEC_RW_PER_UNIT_CAPITAL * k_ssfa
    else:
        thickness = d - a
        below = (k_a - a) / thickness
        above = (d - k_a) / thickness
        rw = SEC_RW_PER_UNIT_CAPITAL * (below + above * k_ssfa)

    return min(max(rw, floor), SEC_MAX_RISK_WEIGHT)


def get_legacy_sec_risk_weight(
    rating: DRCSecRating,
    seniority: DRCSecSeniority,
) -> float:
    """Return the LEGACY rating x seniority securitization DRC risk weight.

    # TODO: VERIFY -- not the §__.210(c)(3)(ii) rule (banking-book RW x 8%).
    Only reachable through ``legacy_rating_table=True``.

    Args:
        rating: Legacy rating category.
        seniority: Senior / non-senior.

    Returns:
        Risk weight as a decimal.
    """
    if seniority == DRCSecSeniority.SENIOR:
        return LEGACY_DRC_SEC_RISK_WEIGHTS_SENIOR[rating]
    return LEGACY_DRC_SEC_RISK_WEIGHTS_NON_SENIOR[rating]


def compute_hedge_benefit_ratio(sum_net_long: float, sum_net_short: float) -> float:
    """Compute the hedge benefit ratio per §__.210(b)(3)(ii) (ERBA NPR p.906).

    .. math::

        HBR = \\frac{\\sum NDE_{long}}{\\sum NDE_{long} + \\sum |NDE_{short}|}

    The same ratio is used within each securitization non-CTP bucket
    (§__.210(c)(3)(iii)) and once across all CTP positions (§__.210(d)(4)).

    Args:
        sum_net_long: Sum of positive net default exposures.
        sum_net_short: Sum of negative net default exposures (sign-agnostic).

    Returns:
        HBR in [0, 1]; 0 when there is no net long exposure.
    """
    if sum_net_long <= 0.0:
        return 0.0
    denominator = sum_net_long + abs(sum_net_short)
    return sum_net_long / denominator if denominator > 0.0 else 0.0
