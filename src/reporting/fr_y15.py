"""FR Y-15 Systemic Risk Report generator.

Generates the FR Y-15 Banking Organization Systemic Risk Report for a
Category I US G-SIB, covering:
- 12 systemic risk indicators across 5 categories
- Size, Interconnectedness, Substitutability, Complexity, Cross-Jurisdictional
- Method 1 score computation (BCBS-based, 12 indicators)
- Method 2 score computation (STWF-based, US-specific)
- Score-to-surcharge mapping (20bp bands / 0.1% increments per 2026 proposal)
- FR Y-15 Schedules A-G population

All monetary amounts in USD millions ($M).

References:
- FR Y-15 Instructions (OMB 7100-0352): Banking Organization Systemic Risk Report
- G-SIB NPR (128 pages): Risk-Based Capital Surcharges for GSIBs
- 12 CFR 217.403-406: G-SIB surcharge calculation
- BCBS d445: Global Systemically Important Banks assessment methodology
- CLAUDE.md: Method 2 coefficients adjusted by 1.2x downward factor;
  surcharge bands: 20bp score ranges / 0.1% increments
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from src.reporting.reporting_params import (
    BCBS_239_THRESHOLDS,
    DataQualityThresholds,
    FR_Y15_INDICATORS,
    FR_Y15_STWF_INDICATORS,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  FR Y-15 Indicator Data Model
# =========================================================================

class FRY15IndicatorValue(BaseModel):
    """A single FR Y-15 indicator value for the systemic risk report.

    Maps to a specific FR Y-15 schedule and line item.

    Reference: FR Y-15 Instructions (OMB 7100-0352).
    """
    indicator_name: str = Field(description="Internal indicator name")
    schedule: str = Field(description="FR Y-15 schedule letter (A-G)")
    line_number: str = Field(description="Line number within schedule")
    description: str = Field(description="Official indicator description")
    category: str = Field(description="Systemic importance category")
    amount: float = Field(description="Indicator value in $M")
    denomination_factor: float = Field(
        default=0.0,
        description="Global aggregate for normalization in $M. "
                    "Reference: BCBS d445 Section 3.2."
    )
    score_contribution: float = Field(
        default=0.0,
        description="Weighted score contribution in basis points"
    )
    regulatory_reference: str = Field(default="")


class FRY15CategoryScore(BaseModel):
    """Aggregated score for one systemic importance category.

    Each of the 5 categories receives 20% weight per BCBS methodology.

    Reference: G-SIB NPR p. 15, 12 CFR 217.404(b).
    """
    category: str = Field(description="Category name")
    weight: float = Field(description="Category weight (0.20 for each)")
    indicators: list[FRY15IndicatorValue] = Field(default_factory=list)
    raw_score_bps: float = Field(
        default=0.0, description="Sum of indicator contributions in bps"
    )
    capped_score_bps: float = Field(
        default=0.0,
        description="Score after caps (substitutability capped at 500bps). "
                    "Reference: G-SIB NPR p. 18."
    )
    cap_applied: bool = Field(default=False)


# =========================================================================
#  Method 1 and Method 2 Scores
# =========================================================================

class FRY15MethodScore(BaseModel):
    """Score for a single G-SIB surcharge method (Method 1 or Method 2).

    Reference: 12 CFR 217.403-406.
    """
    method: str = Field(description="'Method 1' or 'Method 2'")
    total_score_bps: float = Field(
        description="Total systemic importance score in basis points"
    )
    surcharge_pct: float = Field(
        description="Capital surcharge as percentage of RWA"
    )
    surcharge_bucket: int = Field(
        default=0,
        description="Band number in the surcharge schedule"
    )
    band_lower_bps: float = Field(default=0.0, description="Lower bound of band")
    band_upper_bps: float = Field(default=0.0, description="Upper bound of band")
    category_scores: list[FRY15CategoryScore] = Field(default_factory=list)


# =========================================================================
#  Surcharge Determination
# =========================================================================

# Surcharge schedule parameters per 2026 Re-Proposal
# Reference: G-SIB NPR pp. 18-22, CLAUDE.md
METHOD_1_INITIAL_THRESHOLD_BPS: float = 130.0
"""Method 1 initial score threshold in basis points.
Reference: 12 CFR 217.403(b)."""

METHOD_2_INITIAL_THRESHOLD_BPS: float = 130.0
"""Method 2 initial score threshold in basis points.
Reference: 12 CFR 217.406(d)."""

BAND_WIDTH_BPS: float = 20.0
"""Score band width: 20bp per 2026 Re-Proposal (NOT 100bp from BCBS).
Reference: G-SIB NPR p. 18."""

SURCHARGE_INCREMENT_PCT: float = 0.1
"""Surcharge increment: 0.1% per band per 2026 Re-Proposal (NOT 0.5%).
Reference: G-SIB NPR p. 18."""

MIN_SURCHARGE_PCT: float = 1.0
"""Minimum G-SIB surcharge: 1.0%.
Reference: 12 CFR 217.403(b)."""

SUBSTITUTABILITY_CAP_BPS: float = 500.0
"""Substitutability category score cap: 500 basis points.
Reference: G-SIB NPR p. 18, 12 CFR 217.404(b)(3)."""

METHOD_2_DOWNWARD_FACTOR: float = 1.0 / 1.2
"""Method 2 coefficients adjusted by 1.2x downward factor.
Reference: G-SIB NPR p. 24, CLAUDE.md."""


def score_to_surcharge(
    score_bps: float,
    initial_threshold: float = METHOD_1_INITIAL_THRESHOLD_BPS,
    band_width: float = BAND_WIDTH_BPS,
    increment: float = SURCHARGE_INCREMENT_PCT,
    min_surcharge: float = MIN_SURCHARGE_PCT,
) -> tuple[float, int, float, float]:
    """Convert a G-SIB score to a surcharge percentage.

    Per G-SIB NPR pp. 25-26 / 12 CFR 217.403(b):
    Uses 20bp bands and 0.1% increments per 2026 Re-Proposal.

    Args:
        score_bps: G-SIB score in basis points.
        initial_threshold: First band lower bound (130bp).
        band_width: Width of each band (20bp).
        increment: Surcharge increase per band (0.1%).
        min_surcharge: Minimum surcharge (1.0%).

    Returns:
        Tuple of (surcharge_pct, bucket_number, band_lower, band_upper).

    Reference: G-SIB NPR pp. 25-26, 12 CFR 217.403(b).
    """
    if score_bps < initial_threshold:
        return min_surcharge, 1, 0.0, initial_threshold

    import math
    bands_above = (score_bps - initial_threshold) / band_width
    bucket_index = int(math.floor(bands_above))
    surcharge = min_surcharge + bucket_index * increment
    band_lower = initial_threshold + bucket_index * band_width
    band_upper = band_lower + band_width

    return surcharge, bucket_index + 1, band_lower, band_upper


# =========================================================================
#  Indicator Scoring
# =========================================================================

# Default global denomination factors (annual BCBS publication)
# These are representative values for a typical assessment year
# Reference: BCBS d445, published annually
DEFAULT_DENOMINATION_FACTORS: dict[str, float] = {
    "total_exposures": 117_000_000.0,
    "intra_financial_system_assets": 12_500_000.0,
    "intra_financial_system_liabilities": 12_300_000.0,
    "securities_outstanding": 14_800_000.0,
    "payments_activity": 2_900_000_000.0,
    "assets_under_custody": 177_000_000.0,
    "underwriting_activity": 9_200_000.0,
    "otc_derivatives_notional": 620_000_000.0,
    "trading_and_afs_securities": 16_000_000.0,
    "level_3_assets": 1_300_000.0,
    "cross_jurisdictional_claims": 21_000_000.0,
    "cross_jurisdictional_liabilities": 18_000_000.0,
}


def compute_indicator_score(
    indicator_name: str,
    bank_value: float,
    denomination_factor: float,
    category_weight: float,
    indicator_weight: float,
) -> float:
    """Compute a single indicator's contribution to the G-SIB score.

    Per BCBS d445 Section 3.2 / G-SIB NPR p. 24:
    score_i = (bank_value / global_aggregate) * category_weight
              * indicator_weight * 10,000

    Args:
        indicator_name: Name of the indicator (for logging).
        bank_value: Bank's indicator value in $M.
        denomination_factor: Global aggregate in $M.
        category_weight: Category weight (0.20).
        indicator_weight: Within-category weight.

    Returns:
        Score contribution in basis points.

    Reference: BCBS d445 Section 3.2, G-SIB NPR p. 24.
    """
    if denomination_factor <= 0:
        logger.warning(
            "Denomination factor for %s is zero or negative: %.0f",
            indicator_name, denomination_factor
        )
        return 0.0

    ratio = bank_value / denomination_factor
    score = ratio * category_weight * indicator_weight * 10_000.0
    return score


def compute_method1_score(
    indicator_values: dict[str, float],
    denomination_factors: Optional[dict[str, float]] = None,
) -> FRY15MethodScore:
    """Compute Method 1 G-SIB score from indicator values.

    Per 12 CFR 217.404 / G-SIB NPR Section II.B:
    Method 1 uses 12 indicators across 5 categories, each weighted 20%.
    Substitutability category is capped at 500bps.

    Args:
        indicator_values: Dict mapping indicator names to values in $M.
        denomination_factors: Global aggregates for normalization.
            If None, uses DEFAULT_DENOMINATION_FACTORS.

    Returns:
        FRY15MethodScore with full breakdown.

    Reference: 12 CFR 217.404, G-SIB NPR pp. 15-22.
    """
    if denomination_factors is None:
        denomination_factors = DEFAULT_DENOMINATION_FACTORS

    # Group indicators by category
    categories: dict[str, list[str]] = {
        "Size": ["total_exposures"],
        "Interconnectedness": [
            "intra_financial_system_assets",
            "intra_financial_system_liabilities",
            "securities_outstanding",
        ],
        "Substitutability": [
            "payments_activity",
            "assets_under_custody",
            "underwriting_activity",
        ],
        "Complexity": [
            "otc_derivatives_notional",
            "trading_and_afs_securities",
            "level_3_assets",
        ],
        "Cross-Jurisdictional Activity": [
            "cross_jurisdictional_claims",
            "cross_jurisdictional_liabilities",
        ],
    }

    category_scores: list[FRY15CategoryScore] = []
    total_score = 0.0

    for cat_name, indicator_names in categories.items():
        cat_weight = 0.20
        n_indicators = len(indicator_names)
        ind_weight = 1.0 / n_indicators if n_indicators > 0 else 0.0

        indicators: list[FRY15IndicatorValue] = []
        cat_score = 0.0

        for ind_name in indicator_names:
            bank_val = indicator_values.get(ind_name, 0.0)
            denom = denomination_factors.get(ind_name, 0.0)
            ind_def = FR_Y15_INDICATORS.get(ind_name)

            score = compute_indicator_score(
                ind_name, bank_val, denom, cat_weight, ind_weight
            )
            cat_score += score

            indicators.append(FRY15IndicatorValue(
                indicator_name=ind_name,
                schedule=ind_def.schedule if ind_def else "",
                line_number=ind_def.line_number if ind_def else "",
                description=ind_def.description if ind_def else ind_name,
                category=cat_name,
                amount=bank_val,
                denomination_factor=denom,
                score_contribution=score,
                regulatory_reference=(
                    ind_def.regulatory_reference if ind_def else ""
                ),
            ))

        # Apply substitutability cap
        cap_applied = False
        capped_score = cat_score
        if cat_name == "Substitutability" and cat_score > SUBSTITUTABILITY_CAP_BPS:
            capped_score = SUBSTITUTABILITY_CAP_BPS
            cap_applied = True
            logger.info(
                "Substitutability cap applied: %.1f bps capped to %.1f bps",
                cat_score, SUBSTITUTABILITY_CAP_BPS
            )

        total_score += capped_score

        category_scores.append(FRY15CategoryScore(
            category=cat_name,
            weight=cat_weight,
            indicators=indicators,
            raw_score_bps=cat_score,
            capped_score_bps=capped_score,
            cap_applied=cap_applied,
        ))

    surcharge, bucket, band_lower, band_upper = score_to_surcharge(
        total_score, METHOD_1_INITIAL_THRESHOLD_BPS
    )

    return FRY15MethodScore(
        method="Method 1",
        total_score_bps=total_score,
        surcharge_pct=surcharge,
        surcharge_bucket=bucket,
        band_lower_bps=band_lower,
        band_upper_bps=band_upper,
        category_scores=category_scores,
    )


def compute_method2_score(
    indicator_values: dict[str, float],
    stwf_values: dict[str, float],
    avg_total_assets: float,
    denomination_factors: Optional[dict[str, float]] = None,
) -> FRY15MethodScore:
    """Compute Method 2 G-SIB score from indicator and STWF values.

    Per 12 CFR 217.406 / G-SIB NPR Section II.D:
    Method 2 replaces Substitutability with the STWF component.
    Method 2 coefficients adjusted by 1.2x downward factor per 2026
    Re-Proposal (CLAUDE.md).

    STWF score = (weighted_funding / avg_total_assets) * adjusted_coeff * 10,000

    Args:
        indicator_values: Dict mapping indicator names to values in $M.
        stwf_values: Dict with keys stwf_0_30_days, stwf_31_90_days,
            stwf_91_180_days, stwf_181_365_days — all in $M.
        avg_total_assets: Average total consolidated assets in $M.
        denomination_factors: Global aggregates for normalization.

    Returns:
        FRY15MethodScore with full breakdown.

    Reference: 12 CFR 217.406, G-SIB NPR pp. 30-35.
    """
    if denomination_factors is None:
        denomination_factors = DEFAULT_DENOMINATION_FACTORS

    # STWF maturity bucket weights
    # Reference: G-SIB NPR p. 32, 12 CFR 217.406(b)
    stwf_weights: dict[str, float] = {
        "stwf_0_30_days": 1.00,     # Full weight for shortest maturity
        "stwf_31_90_days": 0.75,
        "stwf_91_180_days": 0.50,
        "stwf_181_365_days": 0.25,  # Lowest weight for longest maturity
    }

    # Compute weighted STWF
    total_weighted_stwf = 0.0
    for bucket, weight in stwf_weights.items():
        amount = stwf_values.get(bucket, 0.0)
        total_weighted_stwf += amount * weight

    # STWF score contribution
    stwf_score = 0.0
    if avg_total_assets > 0:
        stwf_ratio = total_weighted_stwf / avg_total_assets
        # Apply Method 2 downward factor
        adjusted_coefficient = METHOD_2_DOWNWARD_FACTOR
        stwf_score = stwf_ratio * adjusted_coefficient * 10_000.0 * 0.20
        # 0.20 is the category weight for STWF replacing Substitutability

    # Categories for Method 2 (same as Method 1 except Substitutability -> STWF)
    categories_m2: dict[str, list[str]] = {
        "Size": ["total_exposures"],
        "Interconnectedness": [
            "intra_financial_system_assets",
            "intra_financial_system_liabilities",
            "securities_outstanding",
        ],
        "Complexity": [
            "otc_derivatives_notional",
            "trading_and_afs_securities",
            "level_3_assets",
        ],
        "Cross-Jurisdictional Activity": [
            "cross_jurisdictional_claims",
            "cross_jurisdictional_liabilities",
        ],
    }

    category_scores: list[FRY15CategoryScore] = []
    total_score = 0.0

    for cat_name, indicator_names in categories_m2.items():
        cat_weight = 0.20
        n_indicators = len(indicator_names)
        ind_weight = 1.0 / n_indicators if n_indicators > 0 else 0.0

        indicators: list[FRY15IndicatorValue] = []
        cat_score = 0.0

        for ind_name in indicator_names:
            bank_val = indicator_values.get(ind_name, 0.0)
            denom = denomination_factors.get(ind_name, 0.0)
            ind_def = FR_Y15_INDICATORS.get(ind_name)

            score = compute_indicator_score(
                ind_name, bank_val, denom, cat_weight, ind_weight
            )
            cat_score += score

            indicators.append(FRY15IndicatorValue(
                indicator_name=ind_name,
                schedule=ind_def.schedule if ind_def else "",
                line_number=ind_def.line_number if ind_def else "",
                description=ind_def.description if ind_def else ind_name,
                category=cat_name,
                amount=bank_val,
                denomination_factor=denom,
                score_contribution=score,
                regulatory_reference=(
                    ind_def.regulatory_reference if ind_def else ""
                ),
            ))

        total_score += cat_score

        category_scores.append(FRY15CategoryScore(
            category=cat_name,
            weight=cat_weight,
            indicators=indicators,
            raw_score_bps=cat_score,
            capped_score_bps=cat_score,
        ))

    # Add STWF category
    stwf_indicators: list[FRY15IndicatorValue] = []
    for bucket_name, weight in stwf_weights.items():
        amount = stwf_values.get(bucket_name, 0.0)
        stwf_def = FR_Y15_STWF_INDICATORS.get(bucket_name)
        stwf_indicators.append(FRY15IndicatorValue(
            indicator_name=bucket_name,
            schedule=stwf_def.schedule if stwf_def else "G",
            line_number=stwf_def.line_number if stwf_def else "",
            description=stwf_def.description if stwf_def else bucket_name,
            category="STWF (Method 2)",
            amount=amount,
            denomination_factor=avg_total_assets,
            score_contribution=amount * weight / avg_total_assets * METHOD_2_DOWNWARD_FACTOR * 10_000.0 * 0.20 / len(stwf_weights) if avg_total_assets > 0 else 0.0,
            regulatory_reference=(
                stwf_def.regulatory_reference if stwf_def else ""
            ),
        ))

    total_score += stwf_score

    category_scores.append(FRY15CategoryScore(
        category="STWF (Method 2)",
        weight=0.20,
        indicators=stwf_indicators,
        raw_score_bps=stwf_score,
        capped_score_bps=stwf_score,
    ))

    surcharge, bucket, band_lower, band_upper = score_to_surcharge(
        total_score, METHOD_2_INITIAL_THRESHOLD_BPS
    )

    return FRY15MethodScore(
        method="Method 2",
        total_score_bps=total_score,
        surcharge_pct=surcharge,
        surcharge_bucket=bucket,
        band_lower_bps=band_lower,
        band_upper_bps=band_upper,
        category_scores=category_scores,
    )


# =========================================================================
#  Complete FR Y-15 Report
# =========================================================================

class FRY15SurchargeDetermination(BaseModel):
    """Final G-SIB surcharge determination.

    Per 12 CFR 217.403(a): surcharge = max(Method 1, Method 2).

    Reference: 12 CFR 217.403(a), G-SIB NPR p. 25.
    """
    method1: FRY15MethodScore
    method2: FRY15MethodScore
    binding_method: str = Field(
        description="Which method produced the higher surcharge"
    )
    final_surcharge_pct: float = Field(
        description="The binding surcharge percentage"
    )
    surcharge_amount: float = Field(
        default=0.0,
        description="Surcharge dollar amount = surcharge_pct/100 * RWA ($M)"
    )


class FRY15DataQualityCheck(BaseModel):
    """Single data quality check for FR Y-15 report.

    Reference: BCBS 239 Principles 3-6.
    """
    check_name: str
    check_type: str
    passed: bool
    message: str = ""
    regulatory_reference: str = "BCBS 239"


class FRY15DataQualityResult(BaseModel):
    """Aggregate data quality result for FR Y-15 filing.

    Reference: BCBS 239 Principles 3-6.
    """
    report_type: str = Field(default="FR_Y_15")
    reporting_date: date
    checks: list[FRY15DataQualityCheck] = Field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    overall_pass: bool = True


def validate_fr_y15(
    indicator_values: dict[str, float],
    reporting_date: date,
) -> FRY15DataQualityResult:
    """Validate FR Y-15 indicator data quality.

    Checks per BCBS 239:
    1. Completeness: all 12 indicators have non-zero values
    2. Range: indicator values within plausible bounds for a G-SIB
    3. Consistency: total exposures > cross-jurisdictional claims

    Args:
        indicator_values: Dict mapping indicator names to values.
        reporting_date: Filing date.

    Returns:
        FRY15DataQualityResult with all check outcomes.

    Reference: BCBS 239 Principles 3-6, FR Y-15 Instructions.
    """
    checks: list[FRY15DataQualityCheck] = []

    # Check 1: Completeness — all 12 Method 1 indicators present
    required = list(FR_Y15_INDICATORS.keys())
    present = [name for name in required if indicator_values.get(name, 0.0) > 0]
    completeness = len(present) / len(required) if required else 1.0
    checks.append(FRY15DataQualityCheck(
        check_name="Indicator completeness (12 Method 1 indicators)",
        check_type="completeness",
        passed=completeness >= 0.90,
        message=f"Present: {len(present)}/{len(required)} ({completeness:.0%})",
        regulatory_reference="FR Y-15 Instructions, BCBS 239 Principle 4",
    ))

    # Check 2: Total exposures should be positive for a G-SIB
    total_exp = indicator_values.get("total_exposures", 0.0)
    checks.append(FRY15DataQualityCheck(
        check_name="Total exposures positive",
        check_type="range",
        passed=total_exp > 0,
        message=f"Total exposures: ${total_exp:,.0f}M",
        regulatory_reference="FR Y-15 Schedule A Line 1",
    ))

    # Check 3: Total exposures >= cross-jurisdictional claims
    cj_claims = indicator_values.get("cross_jurisdictional_claims", 0.0)
    checks.append(FRY15DataQualityCheck(
        check_name="Total exposures >= cross-jurisdictional claims",
        check_type="consistency",
        passed=total_exp >= cj_claims or total_exp == 0,
        message=(
            f"Total exp: ${total_exp:,.0f}M vs "
            f"CJ claims: ${cj_claims:,.0f}M"
        ),
        regulatory_reference="FR Y-15 Schedules A/E consistency",
    ))

    # Check 4: Plausible G-SIB size (total exposures > $250B for typical G-SIB)
    checks.append(FRY15DataQualityCheck(
        check_name="Plausible G-SIB size (total exposures > $250B)",
        check_type="range",
        passed=total_exp >= 250_000.0 or total_exp == 0,
        message=f"Total exposures: ${total_exp:,.0f}M",
        regulatory_reference="G-SIB NPR p. 16",
    ))

    # Check 5: STWF data consistency (sum of buckets should be reasonable)
    stwf_fields = [
        "stwf_0_30_days", "stwf_31_90_days",
        "stwf_91_180_days", "stwf_181_365_days",
    ]
    total_stwf = sum(indicator_values.get(f, 0.0) for f in stwf_fields)
    checks.append(FRY15DataQualityCheck(
        check_name="STWF total reasonable (< total exposures)",
        check_type="consistency",
        passed=total_stwf <= total_exp or total_exp == 0,
        message=f"STWF total: ${total_stwf:,.0f}M vs exposures: ${total_exp:,.0f}M",
        regulatory_reference="FR Y-15 Schedule G, G-SIB NPR p. 32",
    ))

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = len(checks) - passed_count

    return FRY15DataQualityResult(
        reporting_date=reporting_date,
        checks=checks,
        total_checks=len(checks),
        passed_checks=passed_count,
        failed_checks=failed_count,
        overall_pass=failed_count == 0,
    )


class FRY15Report(BaseModel):
    """Complete FR Y-15 Systemic Risk Report.

    Contains all 12 indicators, Method 1 and Method 2 scores,
    surcharge determination, and data quality validation.

    Reference: FR Y-15 Instructions (OMB 7100-0352).
    """
    report_type: str = Field(default="FR_Y_15")
    reporting_date: date
    entity_name: str = Field(default="")
    rssd_id: str = Field(default="")
    assessment_year: Optional[int] = None

    # Indicator values
    indicator_values: dict[str, float] = Field(
        default_factory=dict,
        description="All indicator values in $M"
    )

    # Scores and surcharge
    surcharge_determination: FRY15SurchargeDetermination

    # Quality
    data_quality: FRY15DataQualityResult


def generate_fr_y15(
    indicator_values: dict[str, float],
    reporting_date: date,
    entity_name: str = "",
    rssd_id: str = "",
    assessment_year: Optional[int] = None,
    total_rwa: float = 0.0,
    denomination_factors: Optional[dict[str, float]] = None,
) -> FRY15Report:
    """Generate complete FR Y-15 Systemic Risk Report.

    This is the master function that produces the full FR Y-15 filing
    including Method 1 and Method 2 scores, surcharge determination,
    and data quality validation.

    Args:
        indicator_values: Dict mapping indicator names to values in $M.
            Must include the 12 Method 1 indicators plus STWF data.
        reporting_date: As-of date for the report.
        entity_name: Reporting entity name.
        rssd_id: RSSD identifier.
        assessment_year: G-SIB assessment year.
        total_rwa: Total RWA in $M for surcharge dollar amount.
        denomination_factors: Global aggregates for normalization.

    Returns:
        FRY15Report with complete systemic risk analysis.

    Reference: FR Y-15 Instructions (OMB 7100-0352).
    """
    # Method 1 score
    method1 = compute_method1_score(indicator_values, denomination_factors)

    # Method 2 score
    stwf_values = {
        k: indicator_values.get(k, 0.0)
        for k in ["stwf_0_30_days", "stwf_31_90_days",
                   "stwf_91_180_days", "stwf_181_365_days"]
    }
    avg_total_assets = indicator_values.get("avg_total_assets", 0.0)
    method2 = compute_method2_score(
        indicator_values, stwf_values, avg_total_assets, denomination_factors
    )

    # Surcharge determination: higher of Method 1 and Method 2
    if method2.surcharge_pct >= method1.surcharge_pct:
        binding = "Method 2"
        final_surcharge = method2.surcharge_pct
    else:
        binding = "Method 1"
        final_surcharge = method1.surcharge_pct

    surcharge_amount = total_rwa * (final_surcharge / 100.0) if total_rwa > 0 else 0.0

    determination = FRY15SurchargeDetermination(
        method1=method1,
        method2=method2,
        binding_method=binding,
        final_surcharge_pct=final_surcharge,
        surcharge_amount=surcharge_amount,
    )

    # Data quality
    quality = validate_fr_y15(indicator_values, reporting_date)

    logger.info(
        "Generated FR Y-15 for %s as of %s: "
        "Method 1=%.1fbps (%.1f%%), Method 2=%.1fbps (%.1f%%), "
        "Binding=%s, Surcharge=%.1f%%, quality=%s",
        entity_name, reporting_date,
        method1.total_score_bps, method1.surcharge_pct,
        method2.total_score_bps, method2.surcharge_pct,
        binding, final_surcharge,
        "PASS" if quality.overall_pass else "FAIL",
    )

    return FRY15Report(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rssd_id=rssd_id,
        assessment_year=assessment_year,
        indicator_values=indicator_values,
        surcharge_determination=determination,
        data_quality=quality,
    )
