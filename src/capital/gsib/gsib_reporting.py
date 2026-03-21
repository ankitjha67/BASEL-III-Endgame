"""FR Y-15 report generation and G-SIB surcharge reporting.

Generates structured reports for FR Y-15 filing, Method 1 vs Method 2
comparison, surcharge bucket assignment, and regulatory submission.

Regulatory References:
- FR Y-15 Instructions (OMB 7100-0352): Report format and content
- G-SIB NPR Section II.E: Disclosure and reporting requirements
- 12 CFR 217.403: Surcharge determination and notification
- BCBS d445: Assessment methodology disclosure

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from src.capital.gsib.gsib_calculator import (
    GSIBCalculator,
    GSIBSurchargeResult,
    MethodResult,
)
from src.capital.gsib.gsib_indicators import (
    CategoryScore,
    GSIBIndicatorData,
    IndicatorValue,
    STWFScore,
    validate_indicator_data,
)
from src.capital.gsib.gsib_params import (
    DEFAULT_DENOMINATION_FACTORS,
    DenominationFactors,
    FR_Y15_OMB_NUMBER,
    FR_Y15_REPORT_NAME,
    FR_Y15_REPORT_TITLE,
    FR_Y15_SCHEDULES,
    GSIBCategory,
    GSIBIndicatorCategory,
    GSIBMethod,
    INDICATOR_LOOKUP,
    METHOD_1_BAND_WIDTH_BPS,
    METHOD_1_INDICATORS,
    METHOD_1_INITIAL_THRESHOLD_BPS,
    METHOD_1_MIN_SURCHARGE_PCT,
    METHOD_1_SURCHARGE_INCREMENT_PCT,
    METHOD_2_ADJUSTED_COEFFICIENT,
    METHOD_2_BASE_COEFFICIENT,
    METHOD_2_DOWNWARD_FACTOR,
    SUBSTITUTABILITY_CAP_BPS,
    ValidationBounds,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Report Data Structures
# =========================================================================

@dataclass
class FRY15ScheduleLineItem:
    """A single line item in an FR Y-15 schedule.

    Per FR Y-15 Instructions:
    Each schedule contains specific line items with standardized
    descriptions and reporting codes.

    Attributes:
        line_number: Line reference (e.g., "1", "2a")
        description: Official line item description
        value: Reported value in $M
        memo_items: Any memo/supplemental items
    """
    line_number: str
    description: str
    value: float = 0.0
    memo_items: dict[str, float] = field(default_factory=dict)


@dataclass
class FRY15Schedule:
    """A complete FR Y-15 schedule.

    Per FR Y-15 Instructions:
    The FR Y-15 consists of multiple schedules (A through H),
    each covering a specific systemic importance category.

    Attributes:
        schedule_id: Schedule letter (A-H)
        schedule_name: Official schedule title
        line_items: Individual line items within the schedule
        schedule_total: Sum of relevant line items
    """
    schedule_id: str
    schedule_name: str
    line_items: list[FRY15ScheduleLineItem] = field(default_factory=list)
    schedule_total: float = 0.0


@dataclass
class FRY15Report:
    """Complete FR Y-15 Banking Organization Systemic Risk Report.

    Per FR Y-15 Instructions (OMB 7100-0352):
    This is the primary regulatory report for G-SIB score calculation
    and surcharge determination.

    Attributes:
        report_name: Official report name
        omb_number: OMB control number
        reporting_entity: Name of the bank
        reporting_date: As-of date for the report
        schedules: All FR Y-15 schedules
        method1_score_bps: Calculated Method 1 score
        method2_score_bps: Calculated Method 2 score
        method1_surcharge_pct: Method 1 surcharge
        method2_surcharge_pct: Method 2 surcharge
        final_surcharge_pct: Binding surcharge (higher of M1/M2)
        binding_method: Which method produces the higher surcharge
        generation_timestamp: When the report was generated
    """
    report_name: str = FR_Y15_REPORT_NAME
    omb_number: str = FR_Y15_OMB_NUMBER
    reporting_entity: str = ""
    reporting_date: Optional[date] = None
    schedules: list[FRY15Schedule] = field(default_factory=list)
    method1_score_bps: float = 0.0
    method2_score_bps: float = 0.0
    method1_surcharge_pct: float = 0.0
    method2_surcharge_pct: float = 0.0
    final_surcharge_pct: float = 0.0
    binding_method: GSIBMethod = GSIBMethod.METHOD_1
    generation_timestamp: Optional[datetime] = None
    validation_warnings: list[str] = field(default_factory=list)


@dataclass
class MethodComparisonReport:
    """Method 1 vs Method 2 comparison report.

    Per G-SIB NPR Section II.E:
    Banks must analyze and disclose the impact of both methods.

    Attributes:
        method1_result: Full Method 1 breakdown
        method2_result: Full Method 2 breakdown
        score_differential_bps: Method 2 - Method 1 score
        surcharge_differential_pct: Method 2 - Method 1 surcharge
        binding_method: Which method is binding
        category_comparison: Side-by-side category scores
        stwf_impact_bps: Impact of STWF vs substitutability
    """
    method1_result: MethodResult
    method2_result: MethodResult
    score_differential_bps: float = 0.0
    surcharge_differential_pct: float = 0.0
    binding_method: GSIBMethod = GSIBMethod.METHOD_1
    category_comparison: list[dict[str, Any]] = field(default_factory=list)
    stwf_impact_bps: float = 0.0


@dataclass
class SurchargeBucketReport:
    """Surcharge bucket assignment report.

    Per G-SIB NPR pp.25-26:
    Details the score-to-surcharge band mapping and proximity
    to band boundaries.

    Attributes:
        method: Which method this is for
        score_bps: The G-SIB score
        assigned_bucket: Which band (1-based)
        surcharge_pct: Assigned surcharge
        band_lower_bps: Lower bound of assigned band
        band_upper_bps: Upper bound of assigned band
        distance_to_next_band_bps: How far from the next band boundary
        distance_to_prior_band_bps: How far above the prior band boundary
        next_band_surcharge_pct: What surcharge would be in the next band
    """
    method: GSIBMethod
    score_bps: float = 0.0
    assigned_bucket: int = 0
    surcharge_pct: float = 0.0
    band_lower_bps: float = 0.0
    band_upper_bps: float = 0.0
    distance_to_next_band_bps: float = 0.0
    distance_to_prior_band_bps: float = 0.0
    next_band_surcharge_pct: float = 0.0


# =========================================================================
#  Report Generation Functions
# =========================================================================

def generate_fr_y15_report(
    indicator_data: GSIBIndicatorData,
    surcharge_result: GSIBSurchargeResult,
) -> FRY15Report:
    """Generate a complete FR Y-15 report.

    Per FR Y-15 Instructions (OMB 7100-0352):
    Produces the full systemic risk report with all schedules
    populated from the indicator data and calculation results.

    Args:
        indicator_data: Bank's indicator values
        surcharge_result: Calculated surcharge result

    Returns:
        FRY15Report with all schedules populated
    """
    schedules: list[FRY15Schedule] = []

    # Schedule A: Size Indicators
    # Per FR Y-15 Instructions, Schedule A
    schedule_a = FRY15Schedule(
        schedule_id="A",
        schedule_name=FR_Y15_SCHEDULES["A"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="Total exposures (leverage ratio exposure measure)",
                value=indicator_data.total_exposures,
            ),
        ],
        schedule_total=indicator_data.total_exposures,
    )
    schedules.append(schedule_a)

    # Schedule B: Interconnectedness Indicators
    # Per FR Y-15 Instructions, Schedule B
    schedule_b = FRY15Schedule(
        schedule_id="B",
        schedule_name=FR_Y15_SCHEDULES["B"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="Intra-financial system assets",
                value=indicator_data.intra_financial_system_assets,
            ),
            FRY15ScheduleLineItem(
                line_number="2",
                description="Intra-financial system liabilities",
                value=indicator_data.intra_financial_system_liabilities,
            ),
            FRY15ScheduleLineItem(
                line_number="3",
                description="Securities outstanding",
                value=indicator_data.securities_outstanding,
            ),
        ],
        schedule_total=(
            indicator_data.intra_financial_system_assets
            + indicator_data.intra_financial_system_liabilities
            + indicator_data.securities_outstanding
        ),
    )
    schedules.append(schedule_b)

    # Schedule C: Substitutability Indicators
    # Per FR Y-15 Instructions, Schedule C
    schedule_c = FRY15Schedule(
        schedule_id="C",
        schedule_name=FR_Y15_SCHEDULES["C"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="Payments activity",
                value=indicator_data.payments_activity,
            ),
            FRY15ScheduleLineItem(
                line_number="2",
                description="Assets under custody",
                value=indicator_data.assets_under_custody,
            ),
            FRY15ScheduleLineItem(
                line_number="3",
                description="Underwriting activity",
                value=indicator_data.underwriting_activity,
            ),
        ],
        schedule_total=(
            indicator_data.payments_activity
            + indicator_data.assets_under_custody
            + indicator_data.underwriting_activity
        ),
    )
    schedules.append(schedule_c)

    # Schedule D: Complexity Indicators
    # Per FR Y-15 Instructions, Schedule D
    schedule_d = FRY15Schedule(
        schedule_id="D",
        schedule_name=FR_Y15_SCHEDULES["D"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="OTC derivatives notional amount",
                value=indicator_data.otc_derivatives_notional,
            ),
            FRY15ScheduleLineItem(
                line_number="2",
                description="Trading and AFS securities",
                value=indicator_data.trading_and_afs_securities,
            ),
            FRY15ScheduleLineItem(
                line_number="3",
                description="Level 3 assets",
                value=indicator_data.level_3_assets,
            ),
        ],
        schedule_total=(
            indicator_data.otc_derivatives_notional
            + indicator_data.trading_and_afs_securities
            + indicator_data.level_3_assets
        ),
    )
    schedules.append(schedule_d)

    # Schedule E: Cross-Jurisdictional Activity Indicators
    # Per FR Y-15 Instructions, Schedule E
    schedule_e = FRY15Schedule(
        schedule_id="E",
        schedule_name=FR_Y15_SCHEDULES["E"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="Cross-jurisdictional claims",
                value=indicator_data.cross_jurisdictional_claims,
            ),
            FRY15ScheduleLineItem(
                line_number="2",
                description="Cross-jurisdictional liabilities",
                value=indicator_data.cross_jurisdictional_liabilities,
            ),
        ],
        schedule_total=(
            indicator_data.cross_jurisdictional_claims
            + indicator_data.cross_jurisdictional_liabilities
        ),
    )
    schedules.append(schedule_e)

    # Schedule G: Short-Term Wholesale Funding
    # Per FR Y-15 Instructions, Schedule G
    schedule_g = FRY15Schedule(
        schedule_id="G",
        schedule_name=FR_Y15_SCHEDULES["G"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="STWF: 0-30 days residual maturity",
                value=indicator_data.stwf_0_30_days,
            ),
            FRY15ScheduleLineItem(
                line_number="2",
                description="STWF: 31-90 days residual maturity",
                value=indicator_data.stwf_31_90_days,
            ),
            FRY15ScheduleLineItem(
                line_number="3",
                description="STWF: 91-180 days residual maturity",
                value=indicator_data.stwf_91_180_days,
            ),
            FRY15ScheduleLineItem(
                line_number="4",
                description="STWF: 181-365 days residual maturity",
                value=indicator_data.stwf_181_365_days,
            ),
            FRY15ScheduleLineItem(
                line_number="5",
                description="Average total consolidated assets",
                value=indicator_data.avg_total_assets,
            ),
        ],
        schedule_total=(
            indicator_data.stwf_0_30_days
            + indicator_data.stwf_31_90_days
            + indicator_data.stwf_91_180_days
            + indicator_data.stwf_181_365_days
        ),
    )
    schedules.append(schedule_g)

    # Schedule H: G-SIB Surcharge Calculation
    # Per FR Y-15 Instructions, Schedule H
    schedule_h = FRY15Schedule(
        schedule_id="H",
        schedule_name=FR_Y15_SCHEDULES["H"],
        line_items=[
            FRY15ScheduleLineItem(
                line_number="1",
                description="Method 1 systemic score (basis points)",
                value=surcharge_result.method1_score_bps,
            ),
            FRY15ScheduleLineItem(
                line_number="2",
                description="Method 1 surcharge (%)",
                value=surcharge_result.method1_surcharge_pct,
            ),
            FRY15ScheduleLineItem(
                line_number="3",
                description="Method 2 systemic score (basis points)",
                value=surcharge_result.method2_score_bps,
            ),
            FRY15ScheduleLineItem(
                line_number="4",
                description="Method 2 surcharge (%)",
                value=surcharge_result.method2_surcharge_pct,
            ),
            FRY15ScheduleLineItem(
                line_number="5",
                description="Final G-SIB surcharge (higher of M1/M2) (%)",
                value=surcharge_result.final_surcharge_pct,
            ),
            FRY15ScheduleLineItem(
                line_number="6",
                description="Binding method",
                value=1.0 if surcharge_result.binding_method == GSIBMethod.METHOD_1 else 2.0,
            ),
        ],
    )
    schedules.append(schedule_h)

    # Validation warnings
    validation_warnings = validate_indicator_data(indicator_data)

    return FRY15Report(
        reporting_entity=indicator_data.reporting_entity,
        reporting_date=indicator_data.reporting_date,
        schedules=schedules,
        method1_score_bps=surcharge_result.method1_score_bps,
        method2_score_bps=surcharge_result.method2_score_bps,
        method1_surcharge_pct=surcharge_result.method1_surcharge_pct,
        method2_surcharge_pct=surcharge_result.method2_surcharge_pct,
        final_surcharge_pct=surcharge_result.final_surcharge_pct,
        binding_method=surcharge_result.binding_method,
        generation_timestamp=datetime.now(),
        validation_warnings=validation_warnings,
    )


def generate_method_comparison(
    surcharge_result: GSIBSurchargeResult,
) -> MethodComparisonReport:
    """Generate a Method 1 vs Method 2 comparison report.

    Per G-SIB NPR Section II.E:
    Provides a side-by-side comparison of both methods including
    category-level breakdowns and the impact of STWF vs substitutability.

    Args:
        surcharge_result: Complete surcharge calculation result

    Returns:
        MethodComparisonReport with detailed comparison
    """
    m1 = surcharge_result.method1_result
    m2 = surcharge_result.method2_result

    # Build category comparison
    # Method 1 has all 5 categories; Method 2 has 4 + STWF
    category_comparison: list[dict[str, Any]] = []

    # Get Method 1 category scores indexed by category
    m1_by_category: dict[GSIBIndicatorCategory, float] = {}
    for cs in m1.category_scores:
        m1_by_category[cs.category] = cs.capped_score_bps

    # Get Method 2 category scores indexed by category
    m2_by_category: dict[GSIBIndicatorCategory, float] = {}
    for cs in m2.category_scores:
        m2_by_category[cs.category] = cs.capped_score_bps

    # Common categories
    for cat in [
        GSIBIndicatorCategory.SIZE,
        GSIBIndicatorCategory.INTERCONNECTEDNESS,
        GSIBIndicatorCategory.COMPLEXITY,
        GSIBIndicatorCategory.CROSS_JURISDICTIONAL,
    ]:
        m1_score = m1_by_category.get(cat, 0.0)
        m2_score = m2_by_category.get(cat, 0.0)
        category_comparison.append({
            "category": cat.value,
            "method1_score_bps": m1_score,
            "method2_score_bps": m2_score,
            "differential_bps": m2_score - m1_score,
            "note": "Same calculation in both methods",
        })

    # Substitutability (Method 1 only)
    sub_score = m1_by_category.get(GSIBIndicatorCategory.SUBSTITUTABILITY, 0.0)
    category_comparison.append({
        "category": "SUBSTITUTABILITY (Method 1 only)",
        "method1_score_bps": sub_score,
        "method2_score_bps": 0.0,
        "differential_bps": -sub_score,
        "note": f"Capped at {SUBSTITUTABILITY_CAP_BPS}bp in Method 1",
    })

    # STWF (Method 2 only)
    stwf_score = m2.stwf_score.stwf_score_bps if m2.stwf_score else 0.0
    category_comparison.append({
        "category": "STWF (Method 2 only)",
        "method1_score_bps": 0.0,
        "method2_score_bps": stwf_score,
        "differential_bps": stwf_score,
        "note": f"Coefficient adjusted by {METHOD_2_DOWNWARD_FACTOR}x downward factor",
    })

    # STWF impact: difference between Method 2's STWF and Method 1's substitutability
    stwf_impact = stwf_score - sub_score

    return MethodComparisonReport(
        method1_result=m1,
        method2_result=m2,
        score_differential_bps=surcharge_result.score_differential_bps,
        surcharge_differential_pct=surcharge_result.surcharge_differential_pct,
        binding_method=surcharge_result.binding_method,
        category_comparison=category_comparison,
        stwf_impact_bps=stwf_impact,
    )


def generate_surcharge_bucket_report(
    method_result: MethodResult,
) -> SurchargeBucketReport:
    """Generate a surcharge bucket assignment report.

    Per G-SIB NPR pp.25-26 / CLAUDE.md:
    Shows the detailed band mapping with 20bp ranges and 0.1% increments.
    Includes proximity analysis to neighboring bands.

    Args:
        method_result: Result from one method (Method 1 or Method 2)

    Returns:
        SurchargeBucketReport with band analysis
    """
    score = method_result.score_bps
    bucket = method_result.surcharge_bucket
    surcharge = method_result.surcharge_pct
    band_lower = method_result.band_lower_bps
    band_upper = method_result.band_upper_bps

    # Distance to next band
    distance_to_next = band_upper - score
    # Distance above prior band boundary
    distance_from_prior = score - band_lower

    # Next band surcharge
    next_surcharge = surcharge + METHOD_1_SURCHARGE_INCREMENT_PCT

    return SurchargeBucketReport(
        method=method_result.method,
        score_bps=score,
        assigned_bucket=bucket,
        surcharge_pct=surcharge,
        band_lower_bps=band_lower,
        band_upper_bps=band_upper,
        distance_to_next_band_bps=distance_to_next,
        distance_to_prior_band_bps=distance_from_prior,
        next_band_surcharge_pct=next_surcharge,
    )


# =========================================================================
#  Text Report Formatting
# =========================================================================

def format_fr_y15_text(report: FRY15Report) -> str:
    """Format FR Y-15 report as human-readable text.

    Per FR Y-15 Instructions:
    Produces a formatted text representation of the FR Y-15 report
    suitable for review and audit trail purposes.

    Args:
        report: Complete FR Y-15 report

    Returns:
        Formatted text string
    """
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"  {report.report_name} — {FR_Y15_REPORT_TITLE}")
    lines.append(f"  OMB No. {report.omb_number}")
    lines.append("=" * 80)
    lines.append(f"  Reporting Entity:  {report.reporting_entity}")
    lines.append(f"  Reporting Date:    {report.reporting_date}")
    if report.generation_timestamp:
        lines.append(f"  Generated:         {report.generation_timestamp:%Y-%m-%d %H:%M:%S}")
    lines.append("-" * 80)

    for schedule in report.schedules:
        lines.append("")
        lines.append(f"  Schedule {schedule.schedule_id}: {schedule.schedule_name}")
        lines.append("  " + "-" * 60)
        for item in schedule.line_items:
            lines.append(
                f"    Line {item.line_number:>4s}  {item.description:<50s}  "
                f"${item.value:>15,.0f}M"
            )
        if schedule.schedule_total > 0:
            lines.append(
                f"    {'':>4s}  {'Schedule Total':<50s}  "
                f"${schedule.schedule_total:>15,.0f}M"
            )

    lines.append("")
    lines.append("=" * 80)
    lines.append("  G-SIB SURCHARGE DETERMINATION")
    lines.append("=" * 80)
    lines.append(f"  Method 1 Score:      {report.method1_score_bps:>10.2f} bps")
    lines.append(f"  Method 1 Surcharge:  {report.method1_surcharge_pct:>10.1f}%")
    lines.append(f"  Method 2 Score:      {report.method2_score_bps:>10.2f} bps")
    lines.append(f"  Method 2 Surcharge:  {report.method2_surcharge_pct:>10.1f}%")
    lines.append("-" * 80)
    lines.append(
        f"  BINDING METHOD:      {report.binding_method.value}"
    )
    lines.append(
        f"  FINAL SURCHARGE:     {report.final_surcharge_pct:>10.1f}%"
    )
    lines.append("=" * 80)

    if report.validation_warnings:
        lines.append("")
        lines.append("  VALIDATION WARNINGS:")
        for i, warning in enumerate(report.validation_warnings, 1):
            lines.append(f"    {i}. {warning}")
        lines.append("")

    return "\n".join(lines)


def format_method_comparison_text(report: MethodComparisonReport) -> str:
    """Format Method 1 vs Method 2 comparison as text.

    Per G-SIB NPR Section II.E:
    Produces a formatted comparison of both methods for
    regulatory analysis and disclosure purposes.

    Args:
        report: Method comparison report

    Returns:
        Formatted text string
    """
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("  G-SIB METHOD 1 vs METHOD 2 COMPARISON")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"  {'Category':<40s}  {'Method 1':>10s}  {'Method 2':>10s}  {'Diff':>10s}")
    lines.append("  " + "-" * 74)

    for comp in report.category_comparison:
        cat_name = comp["category"]
        m1_val = comp["method1_score_bps"]
        m2_val = comp["method2_score_bps"]
        diff = comp["differential_bps"]
        lines.append(
            f"  {cat_name:<40s}  {m1_val:>10.2f}  {m2_val:>10.2f}  {diff:>+10.2f}"
        )

    lines.append("  " + "-" * 74)
    lines.append(
        f"  {'TOTAL SCORE (bps)':<40s}  "
        f"{report.method1_result.score_bps:>10.2f}  "
        f"{report.method2_result.score_bps:>10.2f}  "
        f"{report.score_differential_bps:>+10.2f}"
    )
    lines.append(
        f"  {'SURCHARGE (%)':<40s}  "
        f"{report.method1_result.surcharge_pct:>10.1f}  "
        f"{report.method2_result.surcharge_pct:>10.1f}  "
        f"{report.surcharge_differential_pct:>+10.1f}"
    )
    lines.append("")
    lines.append(f"  Binding Method: {report.binding_method.value}")
    lines.append(f"  STWF vs Substitutability Impact: {report.stwf_impact_bps:+.2f} bps")
    lines.append("")

    # STWF detail if available
    stwf = report.method2_result.stwf_score
    if stwf:
        lines.append("  SHORT-TERM WHOLESALE FUNDING DETAIL:")
        lines.append("  " + "-" * 50)
        for bv in stwf.buckets:
            lines.append(
                f"    {bv.bucket.description:<30s}  "
                f"Amount: ${bv.amount:>12,.0f}M  "
                f"Weighted: ${bv.weighted_amount:>12,.0f}M"
            )
        lines.append(f"    {'Total Wholesale Funding':<30s}  ${stwf.total_wholesale_funding:>12,.0f}M")
        lines.append(f"    {'Total Weighted Funding':<30s}  ${stwf.total_weighted_funding:>12,.0f}M")
        lines.append(f"    {'Avg Total Assets':<30s}  ${stwf.avg_total_assets:>12,.0f}M")
        lines.append(f"    {'STWF Ratio':<30s}  {stwf.stwf_ratio:>12.6f}")
        lines.append(
            f"    {'Adjusted Coefficient':<30s}  {METHOD_2_ADJUSTED_COEFFICIENT:>12.3f} "
            f"(base {METHOD_2_BASE_COEFFICIENT:.0f} / {METHOD_2_DOWNWARD_FACTOR}x)"
        )
        lines.append(f"    {'STWF Score':<30s}  {stwf.stwf_score_bps:>12.2f} bps")

    lines.append("=" * 80)
    return "\n".join(lines)


def format_surcharge_bucket_text(report: SurchargeBucketReport) -> str:
    """Format surcharge bucket assignment as text.

    Per G-SIB NPR pp.25-26 / CLAUDE.md:
    Shows the band assignment with 20bp/0.1% granularity.

    Args:
        report: Surcharge bucket report

    Returns:
        Formatted text string
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"  SURCHARGE BUCKET ASSIGNMENT — {report.method.value}")
    lines.append("=" * 60)
    lines.append(f"  Score:                 {report.score_bps:>10.2f} bps")
    lines.append(f"  Assigned Bucket:       {report.assigned_bucket:>10d}")
    lines.append(f"  Band Range:            [{report.band_lower_bps:.0f}, {report.band_upper_bps:.0f}) bps")
    lines.append(f"  Surcharge:             {report.surcharge_pct:>10.1f}%")
    lines.append("-" * 60)
    lines.append(f"  Distance to Next Band: {report.distance_to_next_band_bps:>10.2f} bps")
    lines.append(f"  Above Prior Boundary:  {report.distance_to_prior_band_bps:>10.2f} bps")
    lines.append(f"  Next Band Surcharge:   {report.next_band_surcharge_pct:>10.1f}%")
    lines.append("=" * 60)
    return "\n".join(lines)


# =========================================================================
#  Report-to-Dict Conversion (for JSON/DataFrame export)
# =========================================================================

def fr_y15_report_to_dict(report: FRY15Report) -> dict[str, Any]:
    """Convert FR Y-15 report to a dictionary for serialization.

    Per BCBS 239 data lineage requirements:
    All reports must be serializable for audit trail and storage.

    Args:
        report: FR Y-15 report

    Returns:
        Dictionary representation suitable for JSON serialization
    """
    return {
        "report_name": report.report_name,
        "omb_number": report.omb_number,
        "reporting_entity": report.reporting_entity,
        "reporting_date": report.reporting_date.isoformat() if report.reporting_date else None,
        "generation_timestamp": (
            report.generation_timestamp.isoformat()
            if report.generation_timestamp else None
        ),
        "method1_score_bps": report.method1_score_bps,
        "method2_score_bps": report.method2_score_bps,
        "method1_surcharge_pct": report.method1_surcharge_pct,
        "method2_surcharge_pct": report.method2_surcharge_pct,
        "final_surcharge_pct": report.final_surcharge_pct,
        "binding_method": report.binding_method.value,
        "schedules": [
            {
                "schedule_id": s.schedule_id,
                "schedule_name": s.schedule_name,
                "schedule_total": s.schedule_total,
                "line_items": [
                    {
                        "line_number": li.line_number,
                        "description": li.description,
                        "value": li.value,
                    }
                    for li in s.line_items
                ],
            }
            for s in report.schedules
        ],
        "validation_warnings": report.validation_warnings,
    }


def surcharge_result_to_dict(result: GSIBSurchargeResult) -> dict[str, Any]:
    """Convert GSIBSurchargeResult to a dictionary.

    Per BCBS 239:
    Serializable format for data lineage and audit purposes.

    Args:
        result: G-SIB surcharge calculation result

    Returns:
        Dictionary representation
    """
    m2_stwf: dict[str, Any] | None = None
    if result.method2_result.stwf_score:
        stwf = result.method2_result.stwf_score
        m2_stwf = {
            "total_wholesale_funding": stwf.total_wholesale_funding,
            "total_weighted_funding": stwf.total_weighted_funding,
            "avg_total_assets": stwf.avg_total_assets,
            "stwf_ratio": stwf.stwf_ratio,
            "stwf_score_bps": stwf.stwf_score_bps,
            "buckets": [
                {
                    "description": bv.bucket.description,
                    "amount": bv.amount,
                    "weight": bv.bucket.weight,
                    "weighted_amount": bv.weighted_amount,
                }
                for bv in stwf.buckets
            ],
        }

    return {
        "reporting_entity": result.reporting_entity,
        "reporting_date": (
            result.reporting_date.isoformat() if result.reporting_date else None
        ),
        "assessment_year": result.assessment_year,
        "gsib_category": result.gsib_category.value,
        "method1": {
            "score_bps": result.method1_score_bps,
            "surcharge_pct": result.method1_surcharge_pct,
            "bucket": result.method1_result.surcharge_bucket,
            "band_lower_bps": result.method1_result.band_lower_bps,
            "band_upper_bps": result.method1_result.band_upper_bps,
            "category_scores": {
                cs.category.value: {
                    "raw_score_bps": cs.raw_score_bps,
                    "capped_score_bps": cs.capped_score_bps,
                    "cap_applied": cs.cap_applied,
                }
                for cs in result.method1_result.category_scores
            },
        },
        "method2": {
            "score_bps": result.method2_score_bps,
            "surcharge_pct": result.method2_surcharge_pct,
            "bucket": result.method2_result.surcharge_bucket,
            "band_lower_bps": result.method2_result.band_lower_bps,
            "band_upper_bps": result.method2_result.band_upper_bps,
            "category_scores": {
                cs.category.value: {
                    "raw_score_bps": cs.raw_score_bps,
                    "capped_score_bps": cs.capped_score_bps,
                }
                for cs in result.method2_result.category_scores
            },
            "stwf": m2_stwf,
        },
        "binding_method": result.binding_method.value,
        "final_surcharge_pct": result.final_surcharge_pct,
        "cet1_surcharge_amount": result.cet1_surcharge_amount,
        "total_rwa": result.total_rwa,
    }
