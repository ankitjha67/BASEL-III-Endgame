"""G-SIB surcharge parameters: 12 CFR 217 Subpart H and the March 2026 G-SIB NPR.

Two rule versions are carried side by side so that the current requirement
and the proposal can be computed on the same data:

``GSIBRuleVersion.CURRENT_RULE``
    12 CFR 217.400-406 as in effect (eCFR, 1 January 2025; Reg. Q,
    80 FR 49105, Aug. 14, 2015, as amended at 81 FR 90954, Dec. 16, 2016).

``GSIBRuleVersion.PROPOSAL_2026``
    Board NPR "Regulatory Capital Rule (Regulation Q): Risk-Based Capital
    Surcharges for Global Systemically Important Bank Holding Companies;
    Systemic Risk Report (FR Y-15)", Docket No. 1889, RIN 7100-AH22,
    91 FR 14908-14949 (Mar. 27, 2026), FR Doc. 2026-05961. The proposal:

    * adds two substitutability indicators (trading volume -- fixed income;
      trading volume -- equity and other) and re-weights underwriting
      (revised Table 1 to § 217.404; preamble § II.E.ii.a);
    * divides the fixed method 2 coefficients by 1.2 (one-time adjustment,
      preamble § II.A.i) and indexes them annually by a GDP growth
      adjustment (revised § 217.405(c); definition in § 217.401);
    * removes § 217.406 -- weighted short-term wholesale funding becomes a
      method 2 systemic indicator scored as $bn x coefficient 23.003
      without the average-RWA denominator (preamble § II.B);
    * replaces method 2 Table 2 with 20bp score bands / 0.1% surcharge
      increments (revised § 217.403(c); preamble § II.D), while leaving
      the method 1 bands unchanged ("The proposal would not amend the
      score band ranges for method 1", preamble § II.D).

Method 1 aggregate global indicator amounts: Board notice "2025 aggregate
global indicator amounts", Docket No. OP-1875, 90 FR 58245-58246
(Dec. 16, 2025), FR Doc. 2025-22964 (year-end 2024 BCBS amounts x 1.0389
EUR/USD).

Units: indicator inputs are in USD millions ($M). § 217.405(b)(1) expresses
method 2 indicators "in billions of dollars"; coefficient values are
published in percent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional

# =========================================================================
#  Enumerations
# =========================================================================


class GSIBRuleVersion(Enum):
    """Which version of 12 CFR 217 Subpart H to apply."""

    CURRENT_RULE = "CURRENT_RULE"
    """12 CFR 217.400-406 as in effect (eCFR 2025-01-01)."""
    PROPOSAL_2026 = "PROPOSAL_2026"
    """FR Doc. 2026-05961, 91 FR 14908 (Mar. 27, 2026)."""


class GSIBCategory(Enum):
    """Prudential category of the reporting bank holding company (12 CFR 252.5)."""

    CATEGORY_I = "CATEGORY_I"
    CATEGORY_II = "CATEGORY_II"
    CATEGORY_III = "CATEGORY_III"
    CATEGORY_IV = "CATEGORY_IV"


class GSIBMethod(Enum):
    """Surcharge methods under 12 CFR 217.403(a)."""

    METHOD_1 = "METHOD_1"
    METHOD_2 = "METHOD_2"


class GSIBIndicatorCategory(Enum):
    """Systemic-indicator categories (Table 1 to § 217.404; Table 1 to § 217.405)."""

    SIZE = "SIZE"
    INTERCONNECTEDNESS = "INTERCONNECTEDNESS"
    SUBSTITUTABILITY = "SUBSTITUTABILITY"
    COMPLEXITY = "COMPLEXITY"
    CROSS_JURISDICTIONAL = "CROSS_JURISDICTIONAL"
    SHORT_TERM_WHOLESALE_FUNDING = "SHORT_TERM_WHOLESALE_FUNDING"


# =========================================================================
#  Indicator specifications
# =========================================================================


@dataclass(frozen=True)
class IndicatorSpec:
    """One systemic indicator with its method 1 weight.

    Attributes:
        name: Field name on :class:`GSIBIndicatorData`.
        category: Systemic category.
        weight: Method 1 indicator weight as a decimal (Table 1 to § 217.404).
        fr_y15_line: FR Y-15 schedule reference (§ 217.401 definitions).
        description: Indicator description as defined in § 217.401.
    """

    name: str
    category: GSIBIndicatorCategory
    weight: float
    fr_y15_line: str
    description: str


_S = GSIBIndicatorCategory

# Table 1 to § 217.404 -- Systemic Indicator Weights (current rule).
# "Total exposures 20 percent ... Intra-financial system assets 6.67 percent
#  ... Cross-jurisdictional claims 10 percent ..."
METHOD_1_INDICATORS_CURRENT: Final[tuple[IndicatorSpec, ...]] = (
    IndicatorSpec("total_exposures", _S.SIZE, 0.20, "Schedule A", "Total exposures"),
    IndicatorSpec(
        "intra_financial_system_assets",
        _S.INTERCONNECTEDNESS,
        0.0667,
        "Schedule B",
        "Intra-financial system assets",
    ),
    IndicatorSpec(
        "intra_financial_system_liabilities",
        _S.INTERCONNECTEDNESS,
        0.0667,
        "Schedule B",
        "Intra-financial system liabilities",
    ),
    IndicatorSpec(
        "securities_outstanding",
        _S.INTERCONNECTEDNESS,
        0.0667,
        "Schedule B",
        "Securities outstanding",
    ),
    IndicatorSpec(
        "payments_activity", _S.SUBSTITUTABILITY, 0.0667, "Schedule C", "Payments activity"
    ),
    IndicatorSpec(
        "assets_under_custody", _S.SUBSTITUTABILITY, 0.0667, "Schedule C", "Assets under custody"
    ),
    IndicatorSpec(
        "underwriting_activity",
        _S.SUBSTITUTABILITY,
        0.0667,
        "Schedule C",
        "Underwritten transactions in debt and equity markets",
    ),
    IndicatorSpec(
        "otc_derivatives_notional",
        _S.COMPLEXITY,
        0.0667,
        "Schedule D",
        "Notional amount of over-the-counter (OTC) derivatives",
    ),
    IndicatorSpec(
        "trading_and_afs_securities",
        _S.COMPLEXITY,
        0.0667,
        "Schedule D",
        "Trading and available-for-sale (AFS) securities",
    ),
    IndicatorSpec("level_3_assets", _S.COMPLEXITY, 0.0667, "Schedule D", "Level 3 assets"),
    IndicatorSpec(
        "cross_jurisdictional_claims",
        _S.CROSS_JURISDICTIONAL,
        0.10,
        "Schedule E",
        "Cross-jurisdictional claims",
    ),
    IndicatorSpec(
        "cross_jurisdictional_liabilities",
        _S.CROSS_JURISDICTIONAL,
        0.10,
        "Schedule E",
        "Cross-jurisdictional liabilities",
    ),
)

# Revised Table 1 to § 217.404 (FR Doc. 2026-05961, amendatory instruction 5,
# 91 FR 14948-14949): underwriting 3.33%, trading volume -- fixed income 1.67%,
# trading volume -- equity and other 1.67%; other weights unchanged.
METHOD_1_INDICATORS_PROPOSAL: Final[tuple[IndicatorSpec, ...]] = (
    IndicatorSpec("total_exposures", _S.SIZE, 0.20, "Schedule A", "Total exposures"),
    IndicatorSpec(
        "intra_financial_system_assets",
        _S.INTERCONNECTEDNESS,
        0.0667,
        "Schedule B",
        "Intra-financial system assets",
    ),
    IndicatorSpec(
        "intra_financial_system_liabilities",
        _S.INTERCONNECTEDNESS,
        0.0667,
        "Schedule B",
        "Intra-financial system liabilities",
    ),
    IndicatorSpec(
        "securities_outstanding",
        _S.INTERCONNECTEDNESS,
        0.0667,
        "Schedule B",
        "Securities outstanding",
    ),
    IndicatorSpec(
        "payments_activity", _S.SUBSTITUTABILITY, 0.0667, "Schedule C", "Payments activity"
    ),
    IndicatorSpec(
        "assets_under_custody", _S.SUBSTITUTABILITY, 0.0667, "Schedule C", "Assets under custody"
    ),
    IndicatorSpec(
        "underwriting_activity",
        _S.SUBSTITUTABILITY,
        0.0333,
        "Schedule C",
        "Underwritten transactions in debt and equity markets",
    ),
    IndicatorSpec(
        "trading_volume_fixed_income",
        _S.SUBSTITUTABILITY,
        0.0167,
        "Schedule C",
        "Trading volume -- fixed income",
    ),
    IndicatorSpec(
        "trading_volume_equity_other",
        _S.SUBSTITUTABILITY,
        0.0167,
        "Schedule C",
        "Trading volume -- equity and other",
    ),
    IndicatorSpec(
        "otc_derivatives_notional",
        _S.COMPLEXITY,
        0.0667,
        "Schedule D",
        "Notional amount of over-the-counter (OTC) derivatives",
    ),
    IndicatorSpec(
        "trading_and_afs_securities",
        _S.COMPLEXITY,
        0.0667,
        "Schedule D",
        "Trading and available-for-sale (AFS) securities",
    ),
    IndicatorSpec("level_3_assets", _S.COMPLEXITY, 0.0667, "Schedule D", "Level 3 assets"),
    IndicatorSpec(
        "cross_jurisdictional_claims",
        _S.CROSS_JURISDICTIONAL,
        0.10,
        "Schedule E",
        "Cross-jurisdictional claims",
    ),
    IndicatorSpec(
        "cross_jurisdictional_liabilities",
        _S.CROSS_JURISDICTIONAL,
        0.10,
        "Schedule E",
        "Cross-jurisdictional liabilities",
    ),
)


def method1_indicators(version: GSIBRuleVersion) -> tuple[IndicatorSpec, ...]:
    """Method 1 indicator set for a rule version (Table 1 to § 217.404)."""
    if version == GSIBRuleVersion.PROPOSAL_2026:
        return METHOD_1_INDICATORS_PROPOSAL
    return METHOD_1_INDICATORS_CURRENT


METHOD_1_SCALING_FACTOR: Final[float] = 10_000.0
"""§ 217.404(b)(1)(ii): the indicator ratio is "Multiplied by 10,000"."""

SUBSTITUTABILITY_CAP_BPS: Final[float] = 100.0
"""§ 217.404(b)(2): "The sum of the systemic indicator scores for the indicators
in the substitutability category ... will not exceed 100 basis points." The
proposal does not amend § 217.404(b)(2)."""

GSIB_IDENTIFICATION_THRESHOLD_BPS: Final[float] = 130.0
"""A bank holding company is identified as a GSIB if its method 1 score equals
or exceeds 130 basis points (§ 217.402; 2026 NPR fn. 53)."""


# =========================================================================
#  Method 1 aggregate global indicator amounts (denominators)
# =========================================================================


@dataclass(frozen=True)
class DenominationFactors:
    """Aggregate global indicator amounts in $M (§ 217.401, § 217.404(b)(1)(i)(B)).

    ``trading_volume_*`` are None when the Board has not published them; they
    are required only for the proposal's method 1 trading-volume indicators.
    """

    total_exposures: float
    intra_financial_system_assets: float
    intra_financial_system_liabilities: float
    securities_outstanding: float
    payments_activity: float
    assets_under_custody: float
    underwriting_activity: float
    otc_derivatives_notional: float
    trading_and_afs_securities: float
    level_3_assets: float
    cross_jurisdictional_claims: float
    cross_jurisdictional_liabilities: float
    trading_volume_fixed_income: Optional[float] = None
    trading_volume_equity_other: Optional[float] = None
    source: str = ""

    def get(self, name: str) -> Optional[float]:
        """Return the denominator for an indicator name."""
        return getattr(self, name)


_USD_TO_MILLIONS: Final[float] = 1e-6

# FR Doc. 2025-22964, 90 FR 58246, "Aggregate Global Indicator Amounts in U.S.
# Dollars (USD) for 2025" (values transcribed in USD, converted to $M).
AGGREGATE_GLOBAL_INDICATORS_2025: Final[DenominationFactors] = DenominationFactors(
    total_exposures=115_610_567_459_028 * _USD_TO_MILLIONS,
    intra_financial_system_assets=11_744_530_471_538 * _USD_TO_MILLIONS,
    intra_financial_system_liabilities=11_549_951_568_929 * _USD_TO_MILLIONS,
    securities_outstanding=20_989_667_733_564 * _USD_TO_MILLIONS,
    payments_activity=3_583_068_096_731_293 * _USD_TO_MILLIONS,
    assets_under_custody=236_728_086_197_216 * _USD_TO_MILLIONS,
    underwriting_activity=9_458_987_280_583 * _USD_TO_MILLIONS,
    otc_derivatives_notional=743_719_670_668_380 * _USD_TO_MILLIONS,
    trading_and_afs_securities=4_617_580_286_026 * _USD_TO_MILLIONS,
    level_3_assets=785_843_290_915 * _USD_TO_MILLIONS,
    cross_jurisdictional_claims=27_556_319_815_579 * _USD_TO_MILLIONS,
    cross_jurisdictional_liabilities=22_625_378_519_775 * _USD_TO_MILLIONS,
    # TODO: VERIFY -- the 2025 notice publishes only the twelve current-rule
    # indicators; trading-volume aggregates (needed under the proposal) must be
    # supplied from the BCBS denominators (bis.org/bcbs/gsib/denominators.htm).
    trading_volume_fixed_income=None,
    trading_volume_equity_other=None,
    source="FR Doc. 2025-22964, 90 FR 58246 (Dec. 16, 2025); EUR/USD 1.0389 at 31 Dec 2024",
)

AGGREGATE_GLOBAL_INDICATORS_EURUSD_2024: Final[float] = 1.0389
"""Euro to US dollar spot rate used for the 2025 amounts (90 FR 58246)."""

DEFAULT_DENOMINATION_FACTORS: Final[DenominationFactors] = AGGREGATE_GLOBAL_INDICATORS_2025


# =========================================================================
#  Method 1 surcharge -- Table 1 to § 217.403 (unchanged by the proposal)
# =========================================================================


@dataclass(frozen=True)
class SurchargeBand:
    """A score band [lower, upper) mapped to a surcharge in percent."""

    lower_bps: float
    upper_bps: float
    surcharge_pct: float


# Table 1 to § 217.403 -- Method 1 Surcharge: "Below 130 0.0 percent; 130-229
# 1.0; 230-329 1.5; 330-429 2.0; 430-529 2.5; 530-629 3.5". Integer score
# ranges are applied as half-open intervals [130, 230), [230, 330), ...
METHOD_1_SURCHARGE_BANDS: Final[tuple[SurchargeBand, ...]] = (
    SurchargeBand(float("-inf"), 130.0, 0.0),
    SurchargeBand(130.0, 230.0, 1.0),
    SurchargeBand(230.0, 330.0, 1.5),
    SurchargeBand(330.0, 430.0, 2.0),
    SurchargeBand(430.0, 530.0, 2.5),
    SurchargeBand(530.0, 630.0, 3.5),
)
METHOD_1_HIGHER_THRESHOLD_BPS: Final[float] = 630.0
"""§ 217.403(b)(2): scores that equal or exceed 630 basis points."""
METHOD_1_HIGHER_BASE_PCT: Final[float] = 4.5
"""§ 217.403(b)(2)(i): 4.5 percent."""
METHOD_1_HIGHER_STEP_BPS: Final[float] = 100.0
METHOD_1_HIGHER_STEP_PCT: Final[float] = 1.0
"""§ 217.403(b)(2)(ii): "An additional 1.0 percent for each 100 basis points
that the ... score exceeds 630 basis points"."""


# =========================================================================
#  Method 2 surcharge
# =========================================================================

# Current rule: Table 2 to § 217.403 -- Method 2 Surcharge.
METHOD_2_SURCHARGE_BANDS_CURRENT: Final[tuple[SurchargeBand, ...]] = (
    SurchargeBand(float("-inf"), 130.0, 0.0),
    SurchargeBand(130.0, 230.0, 1.0),
    SurchargeBand(230.0, 330.0, 1.5),
    SurchargeBand(330.0, 430.0, 2.0),
    SurchargeBand(430.0, 530.0, 2.5),
    SurchargeBand(530.0, 630.0, 3.0),
    SurchargeBand(630.0, 730.0, 3.5),
    SurchargeBand(730.0, 830.0, 4.0),
    SurchargeBand(830.0, 930.0, 4.5),
    SurchargeBand(930.0, 1030.0, 5.0),
    SurchargeBand(1030.0, 1130.0, 5.5),
)
METHOD_2_HIGHER_THRESHOLD_BPS_CURRENT: Final[float] = 1130.0
"""§ 217.403(c)(2): scores that equal or exceed 1130 basis points."""
METHOD_2_HIGHER_BASE_PCT_CURRENT: Final[float] = 6.5
"""§ 217.403(c)(2)(i): 6.5 percent."""
METHOD_2_HIGHER_STEP_BPS_CURRENT: Final[float] = 100.0
METHOD_2_HIGHER_STEP_PCT_CURRENT: Final[float] = 0.5
"""§ 217.403(c)(2)(ii): "An additional 0.5 percent for each 100 basis points"."""

# Proposal: revised § 217.403(c) (91 FR 14948).
METHOD_2_PROPOSAL_FLOOR_PCT: Final[float] = 1.0
"""Revised § 217.403(c)(1): 1.0 percent if the score is 189 basis points or less."""
METHOD_2_PROPOSAL_FLOOR_MAX_SCORE_BPS: Final[float] = 189.0
METHOD_2_PROPOSAL_START_BPS: Final[float] = 190.0
"""Revised § 217.403(c)(2): scores that equal or exceed 190 basis points."""
METHOD_2_PROPOSAL_START_PCT: Final[float] = 1.1
"""Revised § 217.403(c)(2)(i): 1.1 percent."""
METHOD_2_PROPOSAL_BAND_WIDTH_BPS: Final[float] = 20.0
METHOD_2_PROPOSAL_INCREMENT_PCT: Final[float] = 0.1
"""Revised § 217.403(c)(2)(ii): "An additional 0.1 percent for each 20 basis
points that the ... score exceeds 190 basis points"."""


# =========================================================================
#  Method 2 coefficients -- Table 1 to § 217.405
# =========================================================================

# Current rule Table 1 to § 217.405 -- Coefficients for Systemic Indicators
# (coefficient value, %; applied to the indicator in billions of dollars).
METHOD_2_COEFFICIENTS_CURRENT_PCT: Final[dict[str, float]] = {
    "total_exposures": 4.423,
    "intra_financial_system_assets": 12.007,
    "intra_financial_system_liabilities": 12.490,
    "securities_outstanding": 9.056,
    "otc_derivatives_notional": 0.155,
    "trading_and_afs_securities": 30.169,
    "level_3_assets": 161.177,
    "cross_jurisdictional_claims": 9.277,
    "cross_jurisdictional_liabilities": 9.926,
}

# Proposed Table 1 to § 217.405 -- Coefficients for Systemic Indicators as of
# December 31, 202[X] (91 FR 14949). The size / interconnectedness /
# complexity / cross-jurisdictional values equal the current coefficients
# divided by the one-time factor of 1.2 (preamble § II.A.i).
METHOD_2_COEFFICIENTS_PROPOSAL_PCT: Final[dict[str, float]] = {
    "total_exposures": 3.686,
    "intra_financial_system_assets": 10.006,
    "intra_financial_system_liabilities": 10.408,
    "securities_outstanding": 7.547,
    "otc_derivatives_notional": 0.129,
    "trading_and_afs_securities": 25.141,
    "level_3_assets": 134.314,
    "cross_jurisdictional_claims": 7.731,
    "cross_jurisdictional_liabilities": 8.272,
    "weighted_stwf_amount": 23.003,
}

METHOD_2_ONE_TIME_DOWNWARD_FACTOR: Final[float] = 1.2
"""Preamble § II.A.i: "a one-time downward adjustment of the method 2
coefficients by a factor of 1.2" (already reflected in the proposed table)."""

METHOD_2_INDICATOR_CATEGORY: Final[dict[str, GSIBIndicatorCategory]] = {
    "total_exposures": _S.SIZE,
    "intra_financial_system_assets": _S.INTERCONNECTEDNESS,
    "intra_financial_system_liabilities": _S.INTERCONNECTEDNESS,
    "securities_outstanding": _S.INTERCONNECTEDNESS,
    "otc_derivatives_notional": _S.COMPLEXITY,
    "trading_and_afs_securities": _S.COMPLEXITY,
    "level_3_assets": _S.COMPLEXITY,
    "cross_jurisdictional_claims": _S.CROSS_JURISDICTIONAL,
    "cross_jurisdictional_liabilities": _S.CROSS_JURISDICTIONAL,
    "weighted_stwf_amount": _S.SHORT_TERM_WHOLESALE_FUNDING,
}

MILLIONS_PER_BILLION: Final[float] = 1_000.0
"""§ 217.405(b)(1): indicator "expressed in billions of dollars"; inputs are $M."""
PERCENT: Final[float] = 100.0
"""Coefficient values in Table 1 to § 217.405 are stated in percent."""


def method2_coefficients_pct(version: GSIBRuleVersion) -> dict[str, float]:
    """Method 2 coefficient table (in %) for a rule version (Table 1 to § 217.405)."""
    if version == GSIBRuleVersion.PROPOSAL_2026:
        return dict(METHOD_2_COEFFICIENTS_PROPOSAL_PCT)
    return dict(METHOD_2_COEFFICIENTS_CURRENT_PCT)


def gdp_growth_adjustment(
    avg_nominal_gdp_three_years_prior_to_publication: float,
    avg_nominal_gdp_three_years_prior_to_effective_date: float,
    prior_year_adjustment: Optional[float] = None,
) -> float:
    """GDP growth adjustment scalar (proposed § 217.401 definition).

    "GDP growth adjustment means the most recent annual scalar published by
    the Board equal to the greater of: (1) The ratio of: (i) The average of
    nominal United States gross domestic product in the three calendar years
    prior to publication of the scalar ...; to (ii) The average of nominal
    United States gross domestic product in the three calendar years prior to
    [the effective date of a final rule] ...; or (2) The GDP growth adjustment
    published by the Board the prior calendar year."

    Args:
        avg_nominal_gdp_three_years_prior_to_publication: Numerator average.
        avg_nominal_gdp_three_years_prior_to_effective_date: Base average.
        prior_year_adjustment: Scalar published the prior year (None in the
            first year).

    Returns:
        The scalar; proposed § 217.405(c)(2) divides each coefficient by it.
    """
    if avg_nominal_gdp_three_years_prior_to_effective_date <= 0:
        raise ValueError("base-period average nominal GDP must be positive")
    ratio = (
        avg_nominal_gdp_three_years_prior_to_publication
        / avg_nominal_gdp_three_years_prior_to_effective_date
    )
    if prior_year_adjustment is None:
        return ratio
    return max(ratio, prior_year_adjustment)


INITIAL_GDP_GROWTH_ADJUSTMENT: Final[float] = 1.0
"""Before the first annual publication the coefficients apply as tabulated
(ratio of the base-period average to itself)."""


# =========================================================================
#  Short-term wholesale funding -- Table 1 to § 217.406
# =========================================================================


class STWFMaturityBucket(Enum):
    """Remaining-maturity columns of Table 1 to § 217.406.

    The proposal (preamble § II.E.iv.a) re-labels the last two columns
    91-179 and 180-364 days to align with FR 2052a; the weights are unchanged
    and move to the FR Y-15 Schedule G instructions (§ II.E.iv.b).
    """

    UP_TO_30_DAYS = "30 days or less or no maturity"
    DAYS_31_TO_90 = "31 to 90 days"
    DAYS_91_TO_180 = "91 to 180 days (proposal: 91 to 179)"
    DAYS_181_TO_365 = "181 to 365 days (proposal: 180 to 364)"


STWF_MATURITY_BUCKETS: Final[tuple[STWFMaturityBucket, ...]] = tuple(STWFMaturityBucket)

STWF_BUCKET_BOUNDS_DAYS_CURRENT: Final[dict[STWFMaturityBucket, tuple[int, int]]] = {
    STWFMaturityBucket.UP_TO_30_DAYS: (0, 30),
    STWFMaturityBucket.DAYS_31_TO_90: (31, 90),
    STWFMaturityBucket.DAYS_91_TO_180: (91, 180),
    STWFMaturityBucket.DAYS_181_TO_365: (181, 365),
}
STWF_BUCKET_BOUNDS_DAYS_PROPOSAL: Final[dict[STWFMaturityBucket, tuple[int, int]]] = {
    STWFMaturityBucket.UP_TO_30_DAYS: (0, 30),
    STWFMaturityBucket.DAYS_31_TO_90: (31, 90),
    STWFMaturityBucket.DAYS_91_TO_180: (91, 179),
    STWFMaturityBucket.DAYS_181_TO_365: (180, 364),
}

# Table 1 to § 217.406 -- Short-Term Wholesale Funding Components and Weights.
STWF_WEIGHTS: Final[dict[int, tuple[float, float, float, float]]] = {
    # Category 1: secured funding by a level 1 liquid asset; unsecured wholesale
    # funding from non-financial-sector entities; brokered deposits from retail
    # customers; short positions where the borrowed asset is not level 1/2A.
    1: (0.25, 0.10, 0.00, 0.00),
    # Category 2: secured funding by a level 2A liquid asset; covered asset
    # exchanges of level 1 for level 2A.
    2: (0.50, 0.25, 0.10, 0.00),
    # Category 3: secured funding by a level 2B liquid asset; other covered asset
    # exchanges; unsecured wholesale funding other than Category 1.
    3: (0.75, 0.50, 0.25, 0.10),
    # Category 4: any other component of short-term wholesale funding.
    4: (1.00, 0.75, 0.50, 0.25),
}

STWF_CATEGORY_DESCRIPTIONS: Final[dict[int, str]] = {
    1: (
        "Secured funding by level 1 liquid asset; unsecured wholesale funding from a "
        "non-financial-sector counterparty; retail brokered deposits; short positions in "
        "non-level-1/2A assets"
    ),
    2: "Secured funding by level 2A liquid asset; level 1 for level 2A covered asset exchanges",
    3: (
        "Secured funding by level 2B liquid asset; other covered asset exchanges; unsecured "
        "wholesale funding (other than Category 1)"
    ),
    4: "Any other component of short-term wholesale funding",
}

STWF_FIXED_FACTOR_CURRENT: Final[float] = 350.0
"""§ 217.406(a)(3): "Multiplied by a fixed factor of 350" (ratio of the average
weighted STWF amount to average risk-weighted assets)."""

LEGACY_STWF_CATEGORY: Final[int] = 4
"""Category assumed for STWF amounts supplied without a funding category: the
Category 4 weights are the highest in every maturity column (conservative)."""


# =========================================================================
#  Effective-date mechanics -- § 217.403(d)
# =========================================================================


def effective_surcharge_pct(
    calculated_prior_year_pct: float,
    calculated_two_years_prior_pct: Optional[float] = None,
) -> float:
    """GSIB surcharge in effect for a calendar year (proposed § 217.403(d)).

    "As of January 1 of a calendar year, the GSIB surcharge in effect ... is
    the GSIB surcharge calculated ... in the immediately prior calendar year,
    unless the GSIB surcharge calculated ... in the calendar year two years
    prior was lower, in which case the GSIB surcharge calculated in the
    calendar year two years prior shall be in effect." The preamble (§ II.F)
    states this restates current § 217.403(d)(1)-(2) without changing its
    substance.
    """
    if calculated_two_years_prior_pct is None:
        return calculated_prior_year_pct
    return min(calculated_prior_year_pct, calculated_two_years_prior_pct)


# =========================================================================
#  FR Y-15 metadata and validation bounds
# =========================================================================

FR_Y15_REPORT_NAME: Final[str] = "FR Y-15"
FR_Y15_REPORT_TITLE: Final[str] = "Systemic Risk Report"
FR_Y15_OMB_NUMBER: Final[str] = "7100-0352"
FR_Y15_FREQUENCY: Final[str] = "QUARTERLY"
FR_Y15_ASSESSMENT_MONTH: Final[int] = 12
FR_Y15_ASSESSMENT_DAY: Final[int] = 31

FR_Y15_SCHEDULES: Final[dict[str, str]] = {
    "A": "Size Indicators",
    "B": "Interconnectedness Indicators",
    "C": "Substitutability Indicators",
    "D": "Complexity Indicators",
    "E": "Cross-Jurisdictional Activity Indicators",
    "F": "Ancillary Indicators",
    "G": "Short-Term Wholesale Funding Indicator",
}


@dataclass(frozen=True)
class ValidationBounds:
    """Plausibility bounds for data-quality checks (BCBS 239 / SR 11-7).

    These are model-governance tolerances, not regulatory parameters.
    """

    min_total_exposures: float = 500_000.0
    max_total_exposures: float = 10_000_000.0
    min_score_bps: float = 0.0
    max_score_bps: float = 2_000.0
    min_surcharge_pct: float = 0.0
    max_surcharge_pct: float = 10.0
    max_stwf_to_total_exposures: float = 1.0


DEFAULT_VALIDATION_BOUNDS: Final[ValidationBounds] = ValidationBounds()

DEFAULT_RULE_VERSION: Final[GSIBRuleVersion] = GSIBRuleVersion.PROPOSAL_2026
"""The engine's basis is the March 2026 re-proposal (CLAUDE.md)."""
