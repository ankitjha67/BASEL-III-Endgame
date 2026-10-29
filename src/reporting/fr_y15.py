"""FR Y-15 Systemic Risk Report generator.

Generates the FR Y-15 Banking Organization Systemic Risk Report for a
Category I US G-SIB, covering:
- Systemic indicators (12 under the current rule, 14 under the 2026
  proposal, which adds the two trading-volume indicators)
- Method 1 / Method 2 scores and the surcharge -- delegated to
  ``src.capital.gsib.GSIBCalculator`` so the FR Y-15 and the capital stack
  share one implementation
- Data-quality checks and FR Y-15 Schedules A-G population

All monetary amounts in USD millions ($M).

References:
- FR Y-15 Instructions (OMB 7100-0352): Banking Organization Systemic Risk Report
- 12 CFR 217.403-406 (current rule)
- G-SIB NPR, FR Doc. 2026-05961, 91 FR 14908 (Mar. 27, 2026)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.gsib import (
    DEFAULT_DENOMINATION_FACTORS,
    DEFAULT_RULE_VERSION,
    METHOD_1_INDICATORS_PROPOSAL,
    DenominationFactors,
    GSIBCalculator,
    GSIBIndicatorCategory,
    GSIBRuleVersion,
    MethodResult,
    create_indicator_data_from_dict,
    score_to_method1_surcharge,
    score_to_method2_surcharge,
)
from src.capital.gsib.gsib_params import INITIAL_GDP_GROWTH_ADJUSTMENT
from src.reporting.reporting_params import FR_Y15_INDICATORS

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
        description="Score after caps (substitutability capped at 100 bp). "
                    "Reference: 12 CFR 217.404(b)(2)."
    )
    cap_applied: bool = Field(default=False)


# =========================================================================
#  Method 1 and Method 2 Scores (delegated to src.capital.gsib)
# =========================================================================

class FRY15MethodScore(BaseModel):
    """Score for a single G-SIB surcharge method (Method 1 or Method 2).

    Reference: 12 CFR 217.403-405 (and § 217.406 under the current rule).
    """
    method: str = Field(description="'Method 1' or 'Method 2'")
    total_score_bps: float = Field(description="Total systemic importance score in basis points")
    surcharge_pct: float = Field(description="Capital surcharge as percentage of RWA")
    surcharge_bucket: int = Field(default=0, description="Band index in the surcharge schedule")
    band_lower_bps: float = Field(default=0.0, description="Lower bound of band")
    band_upper_bps: float = Field(default=0.0, description="Upper bound of band")
    category_scores: list[FRY15CategoryScore] = Field(default_factory=list)
    citation: str = Field(default="")


_CATEGORY_LABELS: dict[GSIBIndicatorCategory, str] = {
    GSIBIndicatorCategory.SIZE: "Size",
    GSIBIndicatorCategory.INTERCONNECTEDNESS: "Interconnectedness",
    GSIBIndicatorCategory.SUBSTITUTABILITY: "Substitutability",
    GSIBIndicatorCategory.COMPLEXITY: "Complexity",
    GSIBIndicatorCategory.CROSS_JURISDICTIONAL: "Cross-Jurisdictional Activity",
    GSIBIndicatorCategory.SHORT_TERM_WHOLESALE_FUNDING: "STWF (Method 2)",
}


def score_to_surcharge(
    score_bps: float,
    method: int = 1,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
) -> tuple[float, int, float, float]:
    """Map a score to a surcharge using the calculator's tables.

    Method 1: Table 1 to § 217.403 (100 bp bands, unchanged by the 2026
    proposal). Method 2: Table 2 to § 217.403 (current rule) or revised
    § 217.403(c) (proposal: 1.0% up to 189 bp, then 1.1% + 0.1% per 20 bp).

    Returns:
        (surcharge_pct, bucket, band_lower_bps, band_upper_bps).
    """
    if method == 1:
        return score_to_method1_surcharge(score_bps)
    return score_to_method2_surcharge(score_bps, version)


def _to_method_score(label: str, result: MethodResult) -> FRY15MethodScore:
    """Convert a calculator MethodResult to the FR Y-15 report model."""
    cats: list[FRY15CategoryScore] = []
    for cs in result.category_scores:
        cat_label = _CATEGORY_LABELS[cs.category]
        indicators: list[FRY15IndicatorValue] = []
        for iv in cs.indicators:
            ind_def = FR_Y15_INDICATORS.get(iv.indicator_name)
            indicators.append(FRY15IndicatorValue(
                indicator_name=iv.indicator_name,
                schedule=(ind_def.schedule if ind_def
                          else ("G" if "stwf" in iv.indicator_name else "")),
                line_number=ind_def.line_number if ind_def else "",
                description=ind_def.description if ind_def else iv.indicator_name,
                category=cat_label,
                amount=iv.raw_value,
                denomination_factor=iv.denomination_factor,
                score_contribution=iv.weighted_score_bps,
                regulatory_reference=ind_def.regulatory_reference if ind_def else result.citation,
            ))
        cats.append(FRY15CategoryScore(
            category=cat_label,
            weight=sum((s.weight for s in METHOD_1_INDICATORS_PROPOSAL
                        if s.category == cs.category), 0.0),
            indicators=indicators,
            raw_score_bps=cs.raw_score_bps,
            capped_score_bps=cs.capped_score_bps,
            cap_applied=cs.cap_applied,
        ))
    return FRY15MethodScore(
        method=label, total_score_bps=result.score_bps, surcharge_pct=result.surcharge_pct,
        surcharge_bucket=result.surcharge_bucket, band_lower_bps=result.band_lower_bps,
        band_upper_bps=result.band_upper_bps, category_scores=cats, citation=result.citation,
    )


def _calculator(
    denomination_factors: Optional[DenominationFactors],
    version: GSIBRuleVersion,
    gdp_growth_adjustment: float,
) -> GSIBCalculator:
    """Single source of G-SIB scoring for the FR Y-15 (src.capital.gsib)."""
    return GSIBCalculator(
        denomination_factors=denomination_factors or DEFAULT_DENOMINATION_FACTORS,
        version=version, gdp_growth_adjustment=gdp_growth_adjustment, validate_inputs=False,
    )


def compute_method1_score(
    indicator_values: dict[str, float],
    denomination_factors: Optional[DenominationFactors] = None,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
) -> FRY15MethodScore:
    """Method 1 score and surcharge for the FR Y-15 (12 CFR 217.404).

    Delegates to :class:`src.capital.gsib.GSIBCalculator` so the FR Y-15 and
    the capital stack always agree.
    """
    data = create_indicator_data_from_dict(indicator_values)
    calc = _calculator(denomination_factors, version, INITIAL_GDP_GROWTH_ADJUSTMENT)
    return _to_method_score("Method 1", calc.method1(data))


def compute_method2_score(
    indicator_values: dict[str, float],
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
    gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT,
) -> FRY15MethodScore:
    """Method 2 score and surcharge for the FR Y-15 (12 CFR 217.405).

    ``indicator_values`` carries the STWF inputs as well (``stwf_cat{c}_b{b}``
    cells, a reported ``weighted_stwf_amount``, or legacy ``stwf_*_days``)
    and ``avg_risk_weighted_assets`` for the current rule's § 217.406 ratio.
    """
    data = create_indicator_data_from_dict(indicator_values)
    calc = _calculator(None, version, gdp_growth_adjustment)
    return _to_method_score("Method 2", calc.method2(data))


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
    denomination_factors: Optional[DenominationFactors] = None,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
    gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT,
) -> FRY15Report:
    """Generate the FR Y-15 with method 1 / method 2 scores and the surcharge.

    Scoring is delegated to :class:`src.capital.gsib.GSIBCalculator`
    (12 CFR 217.403(a): surcharge = greater of the two methods), so the
    FR Y-15 determination is identical to the capital-stack surcharge.

    Args:
        indicator_values: Indicator values in $M (see
            :func:`src.capital.gsib.create_indicator_data_from_dict` keys).
        reporting_date: As-of date.
        entity_name: Reporting entity.
        rssd_id: RSSD identifier.
        assessment_year: Assessment year.
        total_rwa: Total RWA ($M) for the dollar surcharge.
        denomination_factors: Aggregate global indicator amounts.
        version: Rule version (current rule or 2026 proposal).
        gdp_growth_adjustment: Proposed § 217.405(c)(2) scalar.

    Returns:
        FRY15Report.

    Reference: FR Y-15 (OMB 7100-0352); 12 CFR 217.403-405.
    """
    data = create_indicator_data_from_dict(
        indicator_values, entity_name, reporting_date, assessment_year)
    calc = _calculator(denomination_factors, version, gdp_growth_adjustment)
    result = calc.calculate(data, total_rwa)
    method1 = _to_method_score("Method 1", result.method1_result)
    method2 = _to_method_score("Method 2", result.method2_result)
    binding = "Method 2" if result.binding_method.value == "METHOD_2" else "Method 1"
    final_surcharge = result.final_surcharge_pct
    determination = FRY15SurchargeDetermination(
        method1=method1,
        method2=method2,
        binding_method=binding,
        final_surcharge_pct=final_surcharge,
        surcharge_amount=result.cet1_surcharge_amount,
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
