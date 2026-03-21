"""FR Y-15 systemic risk indicators for G-SIB score calculation.

Implements the 12 systemic risk indicators required for FR Y-15 reporting
and G-SIB score computation under both Method 1 and Method 2.

Regulatory References:
- G-SIB NPR Section II.B (pp.15-22): Indicator definitions
- G-SIB NPR Section II.D (pp.30-35): STWF component for Method 2
- FR Y-15 Instructions (OMB 7100-0352): Reporting requirements
- BCBS d445: Global Systemically Important Banks assessment methodology
- 12 CFR 217.404-406: US regulatory implementation

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.capital.gsib.gsib_params import (
    CATEGORY_WEIGHT,
    DEFAULT_DENOMINATION_FACTORS,
    DEFAULT_VALIDATION_BOUNDS,
    DenominationFactors,
    GSIBIndicatorCategory,
    INDICATOR_LOOKUP,
    INDICATORS_PER_CATEGORY,
    METHOD_1_INDICATORS,
    METHOD_1_SCALING_FACTOR,
    METHOD_2_ADJUSTED_COEFFICIENT,
    METHOD_2_CATEGORY_WEIGHT,
    STWF_MATURITY_BUCKETS,
    SUBSTITUTABILITY_CAP_BPS,
    IndicatorSpec,
    STWFBucketSpec,
    ValidationBounds,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Data Classes for Indicator Values
# =========================================================================

@dataclass
class IndicatorValue:
    """A single indicator's raw and scored values.

    Per G-SIB NPR p.24 / BCBS d445 Section 3.2:
    score_i = (bank_value_i / global_aggregate_i) * indicator_weight * 10,000

    Attributes:
        indicator_name: Name matching IndicatorSpec.name
        raw_value: Bank's raw indicator value in $M
        denomination_factor: Global aggregate for this indicator in $M
        weighted_score_bps: Weighted contribution to G-SIB score in basis points
        fr_y15_line: FR Y-15 schedule/line reference
    """
    indicator_name: str
    raw_value: float
    denomination_factor: float
    weighted_score_bps: float = 0.0
    fr_y15_line: str = ""


@dataclass
class CategoryScore:
    """Aggregated score for one of the five systemic importance categories.

    Per G-SIB NPR p.15: Each category receives 20% weight.
    The category score is the sum of its constituent indicator scores.

    Attributes:
        category: Which systemic category
        indicators: Individual indicator scores within this category
        raw_score_bps: Sum of indicator scores before any caps
        capped_score_bps: Score after applying caps (e.g., substitutability cap)
        cap_applied: Whether a cap was applied to this category
    """
    category: GSIBIndicatorCategory
    indicators: list[IndicatorValue] = field(default_factory=list)
    raw_score_bps: float = 0.0
    capped_score_bps: float = 0.0
    cap_applied: bool = False


@dataclass
class STWFBucketValue:
    """Short-Term Wholesale Funding value for a single maturity bucket.

    Per G-SIB NPR p.32 / 12 CFR 217.406(b):
    Wholesale funding is allocated to maturity buckets and weighted.

    Attributes:
        bucket: The maturity bucket specification
        amount: Total wholesale funding in this bucket ($M)
        weighted_amount: amount * bucket.weight ($M)
    """
    bucket: STWFBucketSpec
    amount: float = 0.0
    weighted_amount: float = 0.0


@dataclass
class STWFScore:
    """Short-Term Wholesale Funding score for Method 2.

    Per G-SIB NPR pp.30-35 / 12 CFR 217.406:
    STWF score = (weighted_stwf_amount / avg_total_assets) * adjusted_coefficient * 10,000

    Attributes:
        buckets: Breakdown by maturity bucket
        total_wholesale_funding: Sum of all bucket amounts ($M)
        total_weighted_funding: Sum of all weighted amounts ($M)
        avg_total_assets: Average total consolidated assets ($M)
        stwf_ratio: weighted_funding / avg_total_assets
        stwf_score_bps: Final STWF contribution to Method 2 score
    """
    buckets: list[STWFBucketValue] = field(default_factory=list)
    total_wholesale_funding: float = 0.0
    total_weighted_funding: float = 0.0
    avg_total_assets: float = 0.0
    stwf_ratio: float = 0.0
    stwf_score_bps: float = 0.0


# =========================================================================
#  Indicator Data Input
# =========================================================================

@dataclass
class GSIBIndicatorData:
    """Complete set of indicator values for G-SIB score calculation.

    Contains all 12 systemic indicators required for Method 1 (FR Y-15
    Schedules A-E) plus the STWF data for Method 2 (Schedule G).

    All monetary values in USD millions ($M).
    Per FR Y-15 Instructions / G-SIB NPR Section II.B.
    """
    # Reporting metadata
    reporting_entity: str = ""
    reporting_date: Optional[date] = None
    assessment_year: Optional[int] = None

    # ---- Category 1: Size (Schedule A) ----
    # Per G-SIB NPR p.16: Total exposures as defined by leverage ratio
    total_exposures: float = 0.0  # Schedule A, Line 1

    # ---- Category 2: Interconnectedness (Schedule B) ----
    # Per G-SIB NPR pp.16-17
    intra_financial_system_assets: float = 0.0  # Schedule B, Line 1
    intra_financial_system_liabilities: float = 0.0  # Schedule B, Line 2
    securities_outstanding: float = 0.0  # Schedule B, Line 3

    # ---- Category 3: Substitutability (Schedule C) ----
    # Per G-SIB NPR pp.17-19
    payments_activity: float = 0.0  # Schedule C, Line 1
    assets_under_custody: float = 0.0  # Schedule C, Line 2
    underwriting_activity: float = 0.0  # Schedule C, Line 3

    # ---- Category 4: Complexity (Schedule D) ----
    # Per G-SIB NPR pp.19-20
    otc_derivatives_notional: float = 0.0  # Schedule D, Line 1
    trading_and_afs_securities: float = 0.0  # Schedule D, Line 2
    level_3_assets: float = 0.0  # Schedule D, Line 3

    # ---- Category 5: Cross-Jurisdictional (Schedule E) ----
    # Per G-SIB NPR pp.20-22
    cross_jurisdictional_claims: float = 0.0  # Schedule E, Line 1
    cross_jurisdictional_liabilities: float = 0.0  # Schedule E, Line 2

    # ---- STWF Data for Method 2 (Schedule G) ----
    # Per G-SIB NPR pp.30-35
    stwf_0_30_days: float = 0.0  # Wholesale funding maturing in 0-30 days
    stwf_31_90_days: float = 0.0  # Wholesale funding maturing in 31-90 days
    stwf_91_180_days: float = 0.0  # Wholesale funding maturing in 91-180 days
    stwf_181_365_days: float = 0.0  # Wholesale funding maturing in 181-365 days
    avg_total_assets: float = 0.0  # Average total consolidated assets

    def get_indicator_value(self, indicator_name: str) -> float:
        """Get the raw value for a named indicator.

        Per FR Y-15 Instructions, each indicator maps to a specific
        schedule and line item.

        Args:
            indicator_name: One of the 12 indicator names from METHOD_1_INDICATORS

        Returns:
            Raw indicator value in $M

        Raises:
            ValueError: If indicator_name is not recognized
        """
        indicator_map: dict[str, float] = {
            "total_exposures": self.total_exposures,
            "intra_financial_system_assets": self.intra_financial_system_assets,
            "intra_financial_system_liabilities": self.intra_financial_system_liabilities,
            "securities_outstanding": self.securities_outstanding,
            "payments_activity": self.payments_activity,
            "assets_under_custody": self.assets_under_custody,
            "underwriting_activity": self.underwriting_activity,
            "otc_derivatives_notional": self.otc_derivatives_notional,
            "trading_and_afs_securities": self.trading_and_afs_securities,
            "level_3_assets": self.level_3_assets,
            "cross_jurisdictional_claims": self.cross_jurisdictional_claims,
            "cross_jurisdictional_liabilities": self.cross_jurisdictional_liabilities,
        }
        if indicator_name not in indicator_map:
            raise ValueError(
                f"Unknown indicator '{indicator_name}'. "
                f"Valid indicators: {list(indicator_map.keys())}"
            )
        return indicator_map[indicator_name]

    def get_stwf_amounts(self) -> list[float]:
        """Get STWF amounts by maturity bucket.

        Per G-SIB NPR p.32, wholesale funding is allocated to
        four maturity buckets.

        Returns:
            List of 4 amounts corresponding to STWF_MATURITY_BUCKETS
        """
        return [
            self.stwf_0_30_days,
            self.stwf_31_90_days,
            self.stwf_91_180_days,
            self.stwf_181_365_days,
        ]


# =========================================================================
#  Score Calculation Functions
# =========================================================================

def calculate_indicator_score(
    raw_value: float,
    denomination_factor: float,
    indicator_weight: float,
    scaling_factor: float = METHOD_1_SCALING_FACTOR,
) -> float:
    """Calculate a single indicator's contribution to the G-SIB score.

    Per BCBS d445 Section 3.2 / G-SIB NPR p.24:
    score_i = (bank_value_i / global_aggregate_i) * weight_i * 10,000

    Args:
        raw_value: Bank's indicator value in $M
        denomination_factor: Global aggregate for this indicator in $M
        indicator_weight: Weight of this indicator (e.g., 0.20 for size)
        scaling_factor: Multiplier to convert to basis points (10,000)

    Returns:
        Indicator score contribution in basis points
    """
    if denomination_factor <= 0:
        logger.warning(
            "Denomination factor is non-positive (%.2f). "
            "Returning 0 for this indicator.",
            denomination_factor,
        )
        return 0.0

    if raw_value < 0:
        logger.warning(
            "Negative indicator value (%.2f). Per BCBS d445, "
            "negative values are floored at 0.",
            raw_value,
        )
        raw_value = 0.0

    return (raw_value / denomination_factor) * indicator_weight * scaling_factor


def calculate_category_scores(
    indicator_data: GSIBIndicatorData,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
) -> list[CategoryScore]:
    """Calculate Method 1 category scores for all five categories.

    Per G-SIB NPR Section II.B / BCBS d445:
    1. For each indicator, calculate score = (bank / global) * weight * 10,000
    2. Sum indicators within each category
    3. Apply substitutability cap of 500bp

    Args:
        indicator_data: Bank's indicator values
        denomination_factors: Global aggregates for normalization

    Returns:
        List of 5 CategoryScore objects, one per systemic category
    """
    # Build denomination factor lookup
    denom_lookup: dict[str, float] = {
        "total_exposures": denomination_factors.total_exposures,
        "intra_financial_system_assets": denomination_factors.intra_financial_system_assets,
        "intra_financial_system_liabilities": denomination_factors.intra_financial_system_liabilities,
        "securities_outstanding": denomination_factors.securities_outstanding,
        "payments_activity": denomination_factors.payments_activity,
        "assets_under_custody": denomination_factors.assets_under_custody,
        "underwriting_activity": denomination_factors.underwriting_activity,
        "otc_derivatives_notional": denomination_factors.otc_derivatives_notional,
        "trading_and_afs_securities": denomination_factors.trading_and_afs_securities,
        "level_3_assets": denomination_factors.level_3_assets,
        "cross_jurisdictional_claims": denomination_factors.cross_jurisdictional_claims,
        "cross_jurisdictional_liabilities": denomination_factors.cross_jurisdictional_liabilities,
    }

    # Group indicators by category
    category_indicators: dict[GSIBIndicatorCategory, list[IndicatorSpec]] = {}
    for ind in METHOD_1_INDICATORS:
        category_indicators.setdefault(ind.category, []).append(ind)

    results: list[CategoryScore] = []

    for category in GSIBIndicatorCategory:
        indicators = category_indicators.get(category, [])
        indicator_values: list[IndicatorValue] = []
        category_raw_score = 0.0

        for ind_spec in indicators:
            raw_value = indicator_data.get_indicator_value(ind_spec.name)
            denom = denom_lookup[ind_spec.name]

            score = calculate_indicator_score(
                raw_value=raw_value,
                denomination_factor=denom,
                indicator_weight=ind_spec.weight,
            )

            iv = IndicatorValue(
                indicator_name=ind_spec.name,
                raw_value=raw_value,
                denomination_factor=denom,
                weighted_score_bps=score,
                fr_y15_line=ind_spec.fr_y15_line,
            )
            indicator_values.append(iv)
            category_raw_score += score

        # Apply substitutability cap per G-SIB NPR p.18
        cap_applied = False
        capped_score = category_raw_score
        if category == GSIBIndicatorCategory.SUBSTITUTABILITY:
            if category_raw_score > SUBSTITUTABILITY_CAP_BPS:
                capped_score = SUBSTITUTABILITY_CAP_BPS
                cap_applied = True
                logger.info(
                    "Substitutability cap applied: raw=%.2f bps, capped=%.2f bps",
                    category_raw_score, capped_score,
                )

        results.append(CategoryScore(
            category=category,
            indicators=indicator_values,
            raw_score_bps=category_raw_score,
            capped_score_bps=capped_score,
            cap_applied=cap_applied,
        ))

    return results


def calculate_method1_score(
    indicator_data: GSIBIndicatorData,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
) -> tuple[float, list[CategoryScore]]:
    """Calculate Method 1 G-SIB score.

    Per G-SIB NPR Section II.B / 12 CFR 217.404:
    Method 1 score = sum of all 5 category scores (with substitutability cap)

    Args:
        indicator_data: Bank's indicator values
        denomination_factors: Global aggregates for normalization

    Returns:
        Tuple of (total_score_bps, list_of_category_scores)
    """
    category_scores = calculate_category_scores(indicator_data, denomination_factors)
    total_score = sum(cs.capped_score_bps for cs in category_scores)

    logger.info("Method 1 G-SIB score: %.2f bps", total_score)
    for cs in category_scores:
        logger.debug(
            "  %s: raw=%.2f bps, capped=%.2f bps",
            cs.category.value, cs.raw_score_bps, cs.capped_score_bps,
        )

    return total_score, category_scores


def calculate_stwf_score(
    indicator_data: GSIBIndicatorData,
) -> STWFScore:
    """Calculate the Short-Term Wholesale Funding (STWF) score for Method 2.

    Per G-SIB NPR pp.30-35 / 12 CFR 217.406(b)-(c):
    1. Allocate wholesale funding to maturity buckets
    2. Apply maturity-based weights
    3. Calculate STWF ratio = weighted_funding / avg_total_assets
    4. STWF score = ratio * adjusted_coefficient * 10,000

    The adjusted coefficient applies the 1.2x downward factor per
    the 2026 Re-Proposal / CLAUDE.md.

    Args:
        indicator_data: Bank's indicator values including STWF data

    Returns:
        STWFScore with full breakdown
    """
    stwf_amounts = indicator_data.get_stwf_amounts()

    if len(stwf_amounts) != len(STWF_MATURITY_BUCKETS):
        raise ValueError(
            f"Expected {len(STWF_MATURITY_BUCKETS)} STWF bucket amounts, "
            f"got {len(stwf_amounts)}"
        )

    bucket_values: list[STWFBucketValue] = []
    total_wholesale = 0.0
    total_weighted = 0.0

    for bucket_spec, amount in zip(STWF_MATURITY_BUCKETS, stwf_amounts):
        weighted = amount * bucket_spec.weight
        bucket_values.append(STWFBucketValue(
            bucket=bucket_spec,
            amount=amount,
            weighted_amount=weighted,
        ))
        total_wholesale += amount
        total_weighted += weighted

    # Calculate STWF ratio
    avg_assets = indicator_data.avg_total_assets
    if avg_assets <= 0:
        logger.warning(
            "Average total assets is non-positive (%.2f). "
            "Cannot calculate STWF ratio.",
            avg_assets,
        )
        return STWFScore(
            buckets=bucket_values,
            total_wholesale_funding=total_wholesale,
            total_weighted_funding=total_weighted,
            avg_total_assets=avg_assets,
        )

    stwf_ratio = total_weighted / avg_assets

    # Calculate STWF score using adjusted coefficient
    # Per CLAUDE.md: Method 2 coefficients adjusted by 1.2x downward factor
    stwf_score = stwf_ratio * METHOD_2_ADJUSTED_COEFFICIENT * METHOD_1_SCALING_FACTOR

    logger.info(
        "STWF score: ratio=%.6f, adjusted_coeff=%.3f, score=%.2f bps",
        stwf_ratio, METHOD_2_ADJUSTED_COEFFICIENT, stwf_score,
    )

    return STWFScore(
        buckets=bucket_values,
        total_wholesale_funding=total_wholesale,
        total_weighted_funding=total_weighted,
        avg_total_assets=avg_assets,
        stwf_ratio=stwf_ratio,
        stwf_score_bps=stwf_score,
    )


def calculate_method2_score(
    indicator_data: GSIBIndicatorData,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
) -> tuple[float, list[CategoryScore], STWFScore]:
    """Calculate Method 2 G-SIB score.

    Per G-SIB NPR Section II.D / 12 CFR 217.406:
    Method 2 uses the same 4 systemic categories as Method 1
    (size, interconnectedness, complexity, cross-jurisdictional)
    but replaces the substitutability category with the STWF component.

    Each of the 5 components receives 20% weight.

    Args:
        indicator_data: Bank's indicator values
        denomination_factors: Global aggregates for normalization

    Returns:
        Tuple of (total_score_bps, category_scores, stwf_score)
        Note: category_scores excludes substitutability (replaced by STWF)
    """
    # Calculate the standard 4 categories (exclude substitutability)
    all_category_scores = calculate_category_scores(indicator_data, denomination_factors)

    # Filter to the 4 categories used in Method 2
    method2_categories = {
        GSIBIndicatorCategory.SIZE,
        GSIBIndicatorCategory.INTERCONNECTEDNESS,
        GSIBIndicatorCategory.COMPLEXITY,
        GSIBIndicatorCategory.CROSS_JURISDICTIONAL,
    }
    m2_category_scores = [
        cs for cs in all_category_scores
        if cs.category in method2_categories
    ]

    # Calculate STWF component
    stwf_score = calculate_stwf_score(indicator_data)

    # Method 2 total = sum of 4 categories + STWF score
    total_from_categories = sum(cs.capped_score_bps for cs in m2_category_scores)
    total_score = total_from_categories + stwf_score.stwf_score_bps

    logger.info(
        "Method 2 G-SIB score: %.2f bps (categories=%.2f + STWF=%.2f)",
        total_score, total_from_categories, stwf_score.stwf_score_bps,
    )

    return total_score, m2_category_scores, stwf_score


# =========================================================================
#  Validation Functions
# =========================================================================

def validate_indicator_data(
    indicator_data: GSIBIndicatorData,
    bounds: ValidationBounds = DEFAULT_VALIDATION_BOUNDS,
) -> list[str]:
    """Validate G-SIB indicator data for plausibility.

    Per SR 11-7 / BCBS 239 data quality requirements:
    - Range checks on all indicator values
    - Non-negativity checks
    - Cross-field consistency checks
    - Completeness checks

    Args:
        indicator_data: Data to validate
        bounds: Plausibility bounds for validation

    Returns:
        List of validation warning messages (empty if all checks pass)
    """
    warnings: list[str] = []

    # 1. Total exposures range check
    if indicator_data.total_exposures < bounds.min_total_exposures:
        warnings.append(
            f"Total exposures ({indicator_data.total_exposures:,.0f} $M) "
            f"below minimum threshold ({bounds.min_total_exposures:,.0f} $M) "
            f"for a Category I G-SIB."
        )
    if indicator_data.total_exposures > bounds.max_total_exposures:
        warnings.append(
            f"Total exposures ({indicator_data.total_exposures:,.0f} $M) "
            f"above maximum threshold ({bounds.max_total_exposures:,.0f} $M). "
            f"Verify data accuracy."
        )

    # 2. Non-negativity checks for all indicators
    all_indicators = {
        "total_exposures": indicator_data.total_exposures,
        "intra_financial_system_assets": indicator_data.intra_financial_system_assets,
        "intra_financial_system_liabilities": indicator_data.intra_financial_system_liabilities,
        "securities_outstanding": indicator_data.securities_outstanding,
        "payments_activity": indicator_data.payments_activity,
        "assets_under_custody": indicator_data.assets_under_custody,
        "underwriting_activity": indicator_data.underwriting_activity,
        "otc_derivatives_notional": indicator_data.otc_derivatives_notional,
        "trading_and_afs_securities": indicator_data.trading_and_afs_securities,
        "level_3_assets": indicator_data.level_3_assets,
        "cross_jurisdictional_claims": indicator_data.cross_jurisdictional_claims,
        "cross_jurisdictional_liabilities": indicator_data.cross_jurisdictional_liabilities,
    }

    for name, value in all_indicators.items():
        if value < 0:
            warnings.append(
                f"Indicator '{name}' has negative value ({value:,.0f} $M). "
                f"Per BCBS d445, negative values are not expected."
            )

    # 3. STWF validation
    stwf_amounts = indicator_data.get_stwf_amounts()
    for i, amount in enumerate(stwf_amounts):
        if amount < 0:
            warnings.append(
                f"STWF bucket {i} has negative value ({amount:,.0f} $M)."
            )

    if indicator_data.avg_total_assets <= 0 and any(a > 0 for a in stwf_amounts):
        warnings.append(
            "STWF data provided but avg_total_assets is non-positive. "
            "Cannot compute STWF ratio."
        )

    # 4. STWF ratio plausibility
    if indicator_data.avg_total_assets > 0:
        total_stwf = sum(stwf_amounts)
        stwf_ratio = total_stwf / indicator_data.avg_total_assets
        if stwf_ratio > bounds.max_stwf_ratio:
            warnings.append(
                f"STWF ratio ({stwf_ratio:.2%}) exceeds "
                f"maximum plausible ratio ({bounds.max_stwf_ratio:.2%})."
            )

    # 5. Cross-field consistency: total exposures should be roughly
    # in line with avg_total_assets (leverage ratio basis is typically
    # larger than total assets due to off-balance-sheet items)
    if (indicator_data.avg_total_assets > 0
            and indicator_data.total_exposures > 0):
        ratio = indicator_data.total_exposures / indicator_data.avg_total_assets
        if ratio < 0.8:
            warnings.append(
                f"Total exposures / avg total assets ratio ({ratio:.2f}) "
                f"is unusually low. Leverage ratio exposure should typically "
                f"exceed or be close to total assets."
            )
        if ratio > 3.0:
            warnings.append(
                f"Total exposures / avg total assets ratio ({ratio:.2f}) "
                f"is unusually high. Verify off-balance-sheet calculations."
            )

    # 6. Completeness check: at least total_exposures must be non-zero
    if indicator_data.total_exposures == 0:
        warnings.append(
            "Total exposures is zero. This is a required field "
            "for G-SIB score calculation."
        )

    return warnings


def calculate_reporting_period(
    assessment_year: int,
) -> tuple[date, date]:
    """Determine the reporting period for a G-SIB assessment year.

    Per FR Y-15 Instructions / G-SIB NPR p.23:
    The annual G-SIB score is based on data as of December 31
    of the assessment year. The reporting period covers the
    full calendar year.

    Args:
        assessment_year: The year for which G-SIB scores are being calculated

    Returns:
        Tuple of (period_start, period_end) dates
    """
    period_start = date(assessment_year, 1, 1)
    period_end = date(assessment_year, 12, 31)
    return period_start, period_end
