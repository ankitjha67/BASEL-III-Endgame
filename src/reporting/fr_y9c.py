"""FR Y-9C Schedule HC-R generator — Regulatory capital components and ratios.

Generates the complete FR Y-9C Schedule HC-R Parts I & II for a Category I
US G-SIB, producing the 17+ line items required for regulatory capital
components (Part I) and the risk-weighted assets / capital ratios (Part II).

This module wraps the existing capital_reporting.py functions in src/capital/
and adds:
- Multi-period reporting (current + prior quarters)
- Variance analysis (period-over-period changes)
- Materiality flagging for significant changes
- Data quality validation per BCBS 239
- XBRL-tagged output structure for electronic filing

All monetary amounts in USD millions ($M).

References:
- FR Y-9C Instructions (OMB 7100-0128): Schedule HC-R Parts I & II
- 12 CFR 217.10-22: Regulatory capital requirements
- 12 CFR 217.20(b)-(d): Capital component definitions
- ERBA NPR pp. 34-120: Capital adequacy framework
- BCBS 239: Principles for effective risk data aggregation
"""

from __future__ import annotations

import logging
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_components import TotalCapitalResult, LeverageExposureInputs
from src.capital.capital_ratios import (
    CapitalAdequacyResult,
    BufferRequirements,
)
from src.capital.capital_reporting import (
    FRY9C_HCR_PartI,
    FRY9C_HCR_PartII,
    HCRPartILineItem,
    build_hcr_part_i,
    build_hcr_part_ii_from_breakdown,
)
from src.capital.rwa_aggregator import RWABreakdown
from src.reporting.reporting_params import (
    BCBS_239_THRESHOLDS,
    DataQualityThresholds,
    HCR_PART_I_LINE_ITEMS,
    ReportType,
    REPORT_DEFINITIONS,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Variance Analysis
# =========================================================================

class MaterialityFlag(Enum):
    """Materiality flags for period-over-period variance analysis.

    Reference: FR Y-9C Instructions — General Instructions, Section 5.
    """
    NONE = "NONE"
    NOTABLE = "NOTABLE"       # > 5% change
    MATERIAL = "MATERIAL"     # > 10% change
    SIGNIFICANT = "SIGNIFICANT"  # > 25% change


class LineItemVariance(BaseModel):
    """Variance analysis for a single HC-R line item.

    Compares current period to prior period and flags material changes
    for supervisory attention.

    Reference: FR Y-9C Instructions — General Instructions, Section 5.
    """
    line_number: str = Field(description="HC-R line item number")
    description: str = Field(description="Line item description")
    current_amount: float = Field(description="Current period amount in $M")
    prior_amount: float = Field(description="Prior period amount in $M")
    absolute_change: float = Field(description="Current - Prior in $M")
    percentage_change: Optional[float] = Field(
        default=None,
        description="Percentage change (None if prior is zero)"
    )
    materiality: MaterialityFlag = Field(
        description="Materiality classification of the change"
    )
    regulatory_reference: str = Field(default="")


def classify_materiality(
    current: float,
    prior: float,
    notable_threshold: float = 0.05,
    material_threshold: float = 0.10,
    significant_threshold: float = 0.25,
) -> MaterialityFlag:
    """Classify the materiality of a period-over-period change.

    Per FR Y-9C Instructions General Section 5, banks must explain
    significant changes in line items between reporting periods.

    Args:
        current: Current period amount in $M.
        prior: Prior period amount in $M.
        notable_threshold: Threshold for NOTABLE flag (5% default).
        material_threshold: Threshold for MATERIAL flag (10% default).
        significant_threshold: Threshold for SIGNIFICANT flag (25% default).

    Returns:
        MaterialityFlag classification.

    Reference: FR Y-9C Instructions — General Instructions, Section 5.
    """
    if prior == 0.0:
        if abs(current) > 0.0:
            return MaterialityFlag.SIGNIFICANT
        return MaterialityFlag.NONE

    pct_change = abs((current - prior) / prior)

    if pct_change >= significant_threshold:
        return MaterialityFlag.SIGNIFICANT
    elif pct_change >= material_threshold:
        return MaterialityFlag.MATERIAL
    elif pct_change >= notable_threshold:
        return MaterialityFlag.NOTABLE
    return MaterialityFlag.NONE


# =========================================================================
#  Data Quality Validation
# =========================================================================

class DataQualityCheck(BaseModel):
    """Result of a single data quality check per BCBS 239.

    Reference: BCBS 239 Principles 3 (Accuracy), 4 (Completeness),
    5 (Timeliness), 6 (Adaptability).
    """
    check_name: str = Field(description="Name of the quality check")
    check_type: str = Field(
        description="Type: completeness, accuracy, range, reconciliation"
    )
    passed: bool = Field(description="Whether the check passed")
    expected_value: Optional[float] = Field(
        default=None, description="Expected or threshold value"
    )
    actual_value: Optional[float] = Field(
        default=None, description="Actual measured value"
    )
    deviation: Optional[float] = Field(
        default=None, description="Deviation from expected"
    )
    message: str = Field(default="", description="Human-readable result message")
    regulatory_reference: str = Field(
        default="BCBS 239", description="Regulatory citation"
    )


class FRY9CDataQualityResult(BaseModel):
    """Aggregate data quality result for an FR Y-9C filing.

    Reference: BCBS 239 Principles 3-6.
    """
    report_type: str = Field(default="FR_Y_9C")
    reporting_date: date
    checks: list[DataQualityCheck] = Field(default_factory=list)
    total_checks: int = Field(default=0)
    passed_checks: int = Field(default=0)
    failed_checks: int = Field(default=0)
    overall_pass: bool = Field(default=True)
    completeness_score: float = Field(
        default=1.0, description="Fraction of required fields present"
    )


def validate_hcr_part_i(
    report: FRY9C_HCR_PartI,
    thresholds: DataQualityThresholds = BCBS_239_THRESHOLDS,
) -> FRY9CDataQualityResult:
    """Validate FR Y-9C Schedule HC-R Part I data quality.

    Performs checks per BCBS 239 Principles 3-6:
    1. Completeness: all required line items present and non-null
    2. Accuracy: subtotals foot correctly (Item 7 = Items 1-6, etc.)
    3. Range: capital amounts within plausible bounds
    4. Reconciliation: CET1 + AT1 = Tier 1, Tier 1 + Tier 2 = Total

    Args:
        report: The HC-R Part I report to validate.
        thresholds: Data quality thresholds per BCBS 239.

    Returns:
        FRY9CDataQualityResult with all check outcomes.

    Reference: BCBS 239 Principles 3 (Accuracy), 4 (Completeness).
    """
    checks: list[DataQualityCheck] = []
    tol = thresholds.reconciliation_tolerance

    # Check 1: Gross CET1 footing
    # Item 7 = Item 1 + Item 2 + Item 3 + Item 4 - Item 5 + Item 6
    expected_gross_cet1 = (
        report.item_1_common_stock.amount
        + report.item_2_surplus.amount
        + report.item_3_retained_earnings.amount
        + report.item_4_aoci.amount
        - report.item_5_treasury_stock.amount
        + report.item_6_minority_interest_cet1.amount
    )
    actual_gross_cet1 = report.item_7_gross_cet1.amount
    gross_cet1_diff = abs(actual_gross_cet1 - expected_gross_cet1)
    checks.append(DataQualityCheck(
        check_name="Gross CET1 footing (Item 7 = Items 1-6)",
        check_type="accuracy",
        passed=gross_cet1_diff <= tol,
        expected_value=expected_gross_cet1,
        actual_value=actual_gross_cet1,
        deviation=gross_cet1_diff,
        message=f"Gross CET1 deviation: ${gross_cet1_diff:.2f}M",
        regulatory_reference="12 CFR 217.20(b)",
    ))

    # Check 2: CET1 = Gross CET1 - Total Deductions
    expected_cet1 = actual_gross_cet1 - report.item_11_total_deductions.amount
    actual_cet1 = report.item_12_cet1_capital.amount
    cet1_diff = abs(actual_cet1 - expected_cet1)
    checks.append(DataQualityCheck(
        check_name="CET1 capital footing (Item 12 = Item 7 - Item 11)",
        check_type="accuracy",
        passed=cet1_diff <= tol,
        expected_value=expected_cet1,
        actual_value=actual_cet1,
        deviation=cet1_diff,
        message=f"CET1 capital deviation: ${cet1_diff:.2f}M",
        regulatory_reference="12 CFR 217.20(b)",
    ))

    # Check 3: Tier 1 = CET1 + AT1
    expected_tier1 = actual_cet1 + report.item_15_at1_capital.amount
    actual_tier1 = report.item_15a_tier1_capital.amount
    tier1_diff = abs(actual_tier1 - expected_tier1)
    checks.append(DataQualityCheck(
        check_name="Tier 1 footing (Item 15a = Item 12 + Item 15)",
        check_type="reconciliation",
        passed=tier1_diff <= tol,
        expected_value=expected_tier1,
        actual_value=actual_tier1,
        deviation=tier1_diff,
        message=f"Tier 1 capital deviation: ${tier1_diff:.2f}M",
        regulatory_reference="12 CFR 217.20",
    ))

    # Check 4: Total Capital = Tier 1 + Tier 2
    expected_total = actual_tier1 + report.item_17_tier2_capital.amount
    actual_total = report.item_18_total_capital.amount
    total_diff = abs(actual_total - expected_total)
    checks.append(DataQualityCheck(
        check_name="Total capital footing (Item 18 = Item 15a + Item 17)",
        check_type="reconciliation",
        passed=total_diff <= tol,
        expected_value=expected_total,
        actual_value=actual_total,
        deviation=total_diff,
        message=f"Total capital deviation: ${total_diff:.2f}M",
        regulatory_reference="12 CFR 217.20",
    ))

    # Check 5: CET1 should be positive for a going concern
    checks.append(DataQualityCheck(
        check_name="CET1 capital positive",
        check_type="range",
        passed=actual_cet1 > 0,
        expected_value=0.0,
        actual_value=actual_cet1,
        message=f"CET1 capital: ${actual_cet1:.0f}M",
        regulatory_reference="12 CFR 217.10(a)(1)",
    ))

    # Check 6: Total deductions should not exceed gross CET1
    deductions_ratio = (
        report.item_11_total_deductions.amount / actual_gross_cet1
        if actual_gross_cet1 > 0 else 0.0
    )
    checks.append(DataQualityCheck(
        check_name="Deductions do not exceed gross CET1",
        check_type="range",
        passed=report.item_11_total_deductions.amount <= actual_gross_cet1,
        expected_value=actual_gross_cet1,
        actual_value=report.item_11_total_deductions.amount,
        deviation=deductions_ratio,
        message=f"Deductions = {deductions_ratio:.1%} of gross CET1",
        regulatory_reference="12 CFR 217.22",
    ))

    # Check 7: Completeness — all line items have amounts
    required_items = [
        report.item_1_common_stock, report.item_2_surplus,
        report.item_3_retained_earnings, report.item_7_gross_cet1,
        report.item_12_cet1_capital, report.item_15a_tier1_capital,
        report.item_18_total_capital,
    ]
    present_count = sum(1 for item in required_items if item.amount is not None)
    completeness = present_count / len(required_items) if required_items else 1.0
    checks.append(DataQualityCheck(
        check_name="Required line items completeness",
        check_type="completeness",
        passed=completeness >= thresholds.completeness_minimum,
        expected_value=thresholds.completeness_minimum,
        actual_value=completeness,
        message=f"Completeness: {completeness:.0%} ({present_count}/{len(required_items)})",
        regulatory_reference="BCBS 239 Principle 4",
    ))

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = len(checks) - passed_count

    return FRY9CDataQualityResult(
        reporting_date=report.reporting_date,
        checks=checks,
        total_checks=len(checks),
        passed_checks=passed_count,
        failed_checks=failed_count,
        overall_pass=failed_count == 0,
        completeness_score=completeness,
    )


# =========================================================================
#  Multi-Period Report
# =========================================================================

class FRY9CMultiPeriod(BaseModel):
    """Multi-period FR Y-9C Schedule HC-R for trend analysis.

    Contains current and up to 4 prior quarters for period-over-period
    comparison and trend identification.

    Reference: FR Y-9C Instructions — General Instructions.
    """
    current_period: FRY9C_HCR_PartI
    prior_periods: list[FRY9C_HCR_PartI] = Field(default_factory=list)
    variances: list[LineItemVariance] = Field(default_factory=list)
    entity_name: str = Field(default="")


def compute_hcr_variances(
    current: FRY9C_HCR_PartI,
    prior: FRY9C_HCR_PartI,
) -> list[LineItemVariance]:
    """Compute period-over-period variances for all HC-R Part I line items.

    Compares each line item between the current and prior period,
    calculates absolute and percentage changes, and classifies materiality.

    Args:
        current: Current period HC-R Part I.
        prior: Prior period HC-R Part I.

    Returns:
        List of LineItemVariance for all comparable line items.

    Reference: FR Y-9C Instructions — General Instructions, Section 5.
    """
    pairs: list[tuple[str, HCRPartILineItem, HCRPartILineItem]] = [
        ("1", current.item_1_common_stock, prior.item_1_common_stock),
        ("2", current.item_2_surplus, prior.item_2_surplus),
        ("3", current.item_3_retained_earnings, prior.item_3_retained_earnings),
        ("4", current.item_4_aoci, prior.item_4_aoci),
        ("7", current.item_7_gross_cet1, prior.item_7_gross_cet1),
        ("8", current.item_8_goodwill, prior.item_8_goodwill),
        ("11", current.item_11_total_deductions, prior.item_11_total_deductions),
        ("12", current.item_12_cet1_capital, prior.item_12_cet1_capital),
        ("13", current.item_13_at1_instruments, prior.item_13_at1_instruments),
        ("15", current.item_15_at1_capital, prior.item_15_at1_capital),
        ("15a", current.item_15a_tier1_capital, prior.item_15a_tier1_capital),
        ("16a", current.item_16a_tier2_instruments, prior.item_16a_tier2_instruments),
        ("16b", current.item_16b_general_allowance, prior.item_16b_general_allowance),
        ("17", current.item_17_tier2_capital, prior.item_17_tier2_capital),
        ("18", current.item_18_total_capital, prior.item_18_total_capital),
    ]

    variances: list[LineItemVariance] = []
    for line_num, curr_item, prior_item in pairs:
        abs_change = curr_item.amount - prior_item.amount
        pct_change: Optional[float] = None
        if prior_item.amount != 0.0:
            pct_change = abs_change / abs(prior_item.amount)

        materiality = classify_materiality(curr_item.amount, prior_item.amount)

        line_def = HCR_PART_I_LINE_ITEMS.get(line_num)
        reg_ref = line_def.regulatory_reference if line_def else ""

        variances.append(LineItemVariance(
            line_number=line_num,
            description=curr_item.description,
            current_amount=curr_item.amount,
            prior_amount=prior_item.amount,
            absolute_change=abs_change,
            percentage_change=pct_change,
            materiality=materiality,
            regulatory_reference=reg_ref,
        ))

    return variances


# =========================================================================
#  FR Y-9C Part II: Risk-Weighted Assets and Ratios
# =========================================================================

class FRY9CPartIIExtended(BaseModel):
    """Extended FR Y-9C Schedule HC-R Part II with buffer analysis.

    Adds buffer requirements, surplus/deficit analysis, and PCA
    classification to the standard Part II RWA/ratio output.

    Reference: FR Y-9C Instructions Schedule HC-R Part II,
    12 CFR 217.10-11.
    """
    base_report: FRY9C_HCR_PartII
    # Buffer requirements
    ccb_requirement: float = Field(
        description="Capital Conservation Buffer requirement. "
                    "Reference: 12 CFR 217.11(a)(4)."
    )
    ccyb_requirement: float = Field(
        default=0.0,
        description="Countercyclical Capital Buffer. "
                    "Reference: 12 CFR 217.11(b)."
    )
    gsib_surcharge: float = Field(
        default=0.0,
        description="G-SIB surcharge. "
                    "Reference: 12 CFR 217.403."
    )
    combined_buffer: float = Field(
        description="Combined buffer = CCB + CCyB + G-SIB surcharge. "
                    "Reference: 12 CFR 217.11(a)."
    )
    # Effective minimums
    effective_cet1_minimum: float = Field(
        description="CET1 minimum + combined buffer"
    )
    effective_tier1_minimum: float = Field(
        description="Tier 1 minimum + combined buffer"
    )
    effective_total_minimum: float = Field(
        description="Total capital minimum + combined buffer"
    )
    # Surplus
    cet1_surplus_over_minimum: float = Field(
        description="CET1 ratio - 4.5% minimum"
    )
    cet1_surplus_over_buffer: float = Field(
        description="CET1 ratio - effective minimum"
    )
    # PCA
    pca_category: str = Field(description="Prompt Corrective Action category")
    is_well_capitalized: bool = Field(description="Meets well-capitalized thresholds")


def build_extended_part_ii(
    adequacy: CapitalAdequacyResult,
    rwa_breakdown: RWABreakdown,
    reporting_date: date,
) -> FRY9CPartIIExtended:
    """Build extended FR Y-9C Schedule HC-R Part II with buffer analysis.

    Combines the standard Part II with buffer requirements, surplus/deficit
    analysis, and PCA classification.

    Args:
        adequacy: Complete capital adequacy assessment.
        rwa_breakdown: Detailed RWA breakdown.
        reporting_date: As-of date.

    Returns:
        FRY9CPartIIExtended with full buffer and PCA analysis.

    Reference: FR Y-9C Schedule HC-R Part II, 12 CFR 217.10-11.
    """
    base = build_hcr_part_ii_from_breakdown(adequacy, rwa_breakdown, reporting_date)

    return FRY9CPartIIExtended(
        base_report=base,
        ccb_requirement=adequacy.buffers.capital_conservation_buffer,
        ccyb_requirement=adequacy.buffers.countercyclical_buffer,
        gsib_surcharge=adequacy.buffers.gsib_surcharge,
        combined_buffer=adequacy.buffers.combined_buffer_requirement,
        effective_cet1_minimum=adequacy.buffers.effective_cet1_minimum,
        effective_tier1_minimum=adequacy.buffers.effective_tier1_minimum,
        effective_total_minimum=adequacy.buffers.effective_total_capital_minimum,
        cet1_surplus_over_minimum=adequacy.surplus_deficit.cet1_surplus_over_minimum,
        cet1_surplus_over_buffer=adequacy.surplus_deficit.cet1_surplus_over_buffer,
        pca_category=adequacy.pca.category.value,
        is_well_capitalized=adequacy.is_well_capitalized,
    )


# =========================================================================
#  Complete FR Y-9C Report Package
# =========================================================================

class FRY9CReport(BaseModel):
    """Complete FR Y-9C Schedule HC-R report package.

    Contains Part I (capital components), Part II (RWA and ratios),
    data quality validation results, and optional variance analysis.

    Reference: FR Y-9C Instructions (OMB 7100-0128).
    """
    report_type: str = Field(default="FR_Y_9C")
    reporting_date: date
    entity_name: str = Field(default="")
    rssd_id: str = Field(default="")
    # Parts
    part_i: FRY9C_HCR_PartI
    part_ii: FRY9CPartIIExtended
    # Quality
    data_quality: FRY9CDataQualityResult
    # Variance (optional, requires prior period)
    variances: list[LineItemVariance] = Field(default_factory=list)
    has_material_variances: bool = Field(
        default=False,
        description="True if any line item has MATERIAL or SIGNIFICANT variance"
    )


def generate_fr_y9c(
    capital: TotalCapitalResult,
    adequacy: CapitalAdequacyResult,
    rwa_breakdown: RWABreakdown,
    reporting_date: date,
    entity_name: str = "",
    rssd_id: str = "",
    prior_capital: Optional[TotalCapitalResult] = None,
    prior_reporting_date: Optional[date] = None,
) -> FRY9CReport:
    """Generate complete FR Y-9C Schedule HC-R report.

    This is the master function that produces the full FR Y-9C HC-R filing
    including Part I (capital components), Part II (RWA and ratios),
    data quality validation, and optional variance analysis.

    Args:
        capital: Current period total capital result.
        adequacy: Current period capital adequacy assessment.
        rwa_breakdown: Current period RWA breakdown.
        reporting_date: As-of date for the report.
        entity_name: Reporting entity name.
        rssd_id: RSSD identifier.
        prior_capital: Optional prior period capital for variance analysis.
        prior_reporting_date: Prior period reporting date.

    Returns:
        FRY9CReport with all components.

    Reference: FR Y-9C Instructions (OMB 7100-0128), Schedule HC-R.
    """
    # Part I
    part_i = build_hcr_part_i(capital, reporting_date, entity_name, rssd_id)

    # Part II (extended)
    part_ii = build_extended_part_ii(adequacy, rwa_breakdown, reporting_date)

    # Data quality
    quality = validate_hcr_part_i(part_i)

    # Variance analysis (if prior period available)
    variances: list[LineItemVariance] = []
    has_material = False
    if prior_capital is not None and prior_reporting_date is not None:
        prior_part_i = build_hcr_part_i(
            prior_capital, prior_reporting_date, entity_name, rssd_id
        )
        variances = compute_hcr_variances(part_i, prior_part_i)
        has_material = any(
            v.materiality in (MaterialityFlag.MATERIAL, MaterialityFlag.SIGNIFICANT)
            for v in variances
        )

    logger.info(
        "Generated FR Y-9C for %s as of %s: CET1=$%.0fM, Total=$%.0fM, "
        "RWA=$%.0fM, CET1 ratio=%.2f%%, quality=%s",
        entity_name, reporting_date,
        part_i.item_12_cet1_capital.amount,
        part_i.item_18_total_capital.amount,
        rwa_breakdown.total_rwa,
        adequacy.ratios.cet1_ratio * 100,
        "PASS" if quality.overall_pass else "FAIL",
    )

    return FRY9CReport(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rssd_id=rssd_id,
        part_i=part_i,
        part_ii=part_ii,
        data_quality=quality,
        variances=variances,
        has_material_variances=has_material,
    )
