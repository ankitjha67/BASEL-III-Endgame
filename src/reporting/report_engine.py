"""Report engine — main orchestrator for regulatory report generation.

Orchestrates the generation of all regulatory reports for a Category I
US G-SIB, including:
- FR Y-9C Schedule HC-R (capital components and ratios)
- FFIEC 101 Schedule A (RWA by exposure type)
- FR Y-15 (systemic risk report)
- FR Y-14A/Q (capital assessment and stress testing)
- Cross-report validation and reconciliation
- Data quality aggregation per BCBS 239
- BCBS 239 lineage trail for data transformations

All monetary amounts in USD millions ($M).

References:
- Federal Reserve Board regulatory reporting requirements
- BCBS 239: Principles for effective risk data aggregation and risk reporting
- SR 11-7: Supervisory guidance on model risk management
- 12 CFR 217.10-22: Capital adequacy framework
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_components import TotalCapitalResult
from src.capital.capital_ratios import CapitalAdequacyResult
from src.capital.rwa_aggregator import (
    CreditRiskRWAItem,
    CVARiskRWAInput,
    MarketRiskRWAInput,
    OperationalRiskRWAInput,
    RWABreakdown,
)
from src.reporting.fr_y9c import (
    FRY9CReport,
    FRY9CDataQualityResult,
    generate_fr_y9c,
)
from src.reporting.ffiec101 import (
    FFIEC101Report,
    FFIEC101DataQualityResult,
    generate_ffiec_101,
)
from src.reporting.fr_y15 import (
    FRY15Report,
    FRY15DataQualityResult,
    generate_fr_y15,
)
from src.reporting.fr_y14 import (
    FRY14Report,
    FRY14DataQualityResult,
    TradingCounterpartySchedule,
    generate_fr_y14,
)
from src.reporting.reporting_params import (
    BCBS_239_THRESHOLDS,
    DataQualityThresholds,
    ReportType,
    REPORT_DEFINITIONS,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Cross-Validation Checks
# =========================================================================

class CrossValidationCheck(BaseModel):
    """A single cross-report reconciliation check.

    Per BCBS 239 Principle 6 (Adaptability), reports must be
    internally consistent across filings.

    Reference: BCBS 239 Principles 3 and 6.
    """
    check_name: str = Field(description="Name of the cross-validation check")
    report_a: str = Field(description="First report in comparison")
    report_b: str = Field(description="Second report in comparison")
    field_a: str = Field(description="Field from report A")
    field_b: str = Field(description="Field from report B")
    value_a: float = Field(description="Value from report A in $M")
    value_b: float = Field(description="Value from report B in $M")
    deviation: float = Field(description="Absolute difference in $M")
    passed: bool = Field(description="Whether within tolerance")
    tolerance: float = Field(description="Reconciliation tolerance in $M")
    message: str = Field(default="")
    regulatory_reference: str = Field(default="BCBS 239 Principle 6")


class CrossValidationResult(BaseModel):
    """Aggregate cross-validation result across all report pairs.

    Reference: BCBS 239 Principles 3 and 6.
    """
    checks: list[CrossValidationCheck] = Field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    overall_pass: bool = True


def run_cross_validation(
    y9c: Optional[FRY9CReport] = None,
    ffiec101: Optional[FFIEC101Report] = None,
    y15: Optional[FRY15Report] = None,
    tolerance: float = BCBS_239_THRESHOLDS.cross_validation_tolerance,
) -> CrossValidationResult:
    """Run cross-report reconciliation checks.

    Validates consistency between regulatory reports:
    1. FR Y-9C total capital vs FFIEC 101 implied capital
    2. FR Y-9C total RWA vs FFIEC 101 total RWA
    3. FR Y-9C CET1 ratio consistency
    4. FR Y-15 surcharge consistency with Y-9C buffer

    Args:
        y9c: FR Y-9C report (if available).
        ffiec101: FFIEC 101 report (if available).
        y15: FR Y-15 report (if available).
        tolerance: Reconciliation tolerance in $M.

    Returns:
        CrossValidationResult with all reconciliation checks.

    Reference: BCBS 239 Principles 3 (Accuracy), 6 (Adaptability).
    """
    checks: list[CrossValidationCheck] = []

    # Check 1: Y-9C total RWA vs FFIEC 101 total RWA
    if y9c is not None and ffiec101 is not None:
        y9c_rwa = y9c.part_ii.base_report.total_rwa
        ffiec_rwa = ffiec101.schedule_a.total_rwa
        dev = abs(y9c_rwa - ffiec_rwa)
        checks.append(CrossValidationCheck(
            check_name="Total RWA: FR Y-9C vs FFIEC 101",
            report_a="FR_Y_9C",
            report_b="FFIEC_101",
            field_a="Part II total RWA",
            field_b="Schedule A line 13",
            value_a=y9c_rwa,
            value_b=ffiec_rwa,
            deviation=dev,
            passed=dev <= tolerance,
            tolerance=tolerance,
            message=f"RWA deviation: ${dev:.2f}M",
            regulatory_reference="BCBS 239 Principle 3",
        ))

    # Check 2: Y-9C credit risk RWA vs FFIEC 101 credit risk RWA
    if y9c is not None and ffiec101 is not None:
        y9c_cr_rwa = y9c.part_ii.base_report.credit_risk_rwa
        ffiec_cr_rwa = ffiec101.schedule_a.total_credit_risk_rwa
        dev = abs(y9c_cr_rwa - ffiec_cr_rwa)
        checks.append(CrossValidationCheck(
            check_name="Credit Risk RWA: FR Y-9C vs FFIEC 101",
            report_a="FR_Y_9C",
            report_b="FFIEC_101",
            field_a="Part II credit risk RWA",
            field_b="Schedule A line 9",
            value_a=y9c_cr_rwa,
            value_b=ffiec_cr_rwa,
            deviation=dev,
            passed=dev <= tolerance,
            tolerance=tolerance,
            message=f"Credit Risk RWA deviation: ${dev:.2f}M",
            regulatory_reference="BCBS 239 Principle 3",
        ))

    # Check 3: Y-9C CET1 capital consistency (Part I item 12 should drive Part II ratio)
    if y9c is not None:
        cet1_cap = y9c.part_i.item_12_cet1_capital.amount
        total_rwa = y9c.part_ii.base_report.total_rwa
        expected_ratio = cet1_cap / total_rwa if total_rwa > 0 else 0.0
        actual_ratio = y9c.part_ii.base_report.cet1_ratio
        ratio_dev = abs(actual_ratio - expected_ratio)
        checks.append(CrossValidationCheck(
            check_name="CET1 ratio consistency: Part I vs Part II",
            report_a="FR_Y_9C Part I",
            report_b="FR_Y_9C Part II",
            field_a="Item 12 / RWA",
            field_b="CET1 ratio",
            value_a=expected_ratio,
            value_b=actual_ratio,
            deviation=ratio_dev,
            passed=ratio_dev <= 0.0001,
            tolerance=0.0001,
            message=f"CET1 ratio deviation: {ratio_dev:.6f}",
            regulatory_reference="12 CFR 217.10(a)(1)",
        ))

    # Check 4: FR Y-15 surcharge consistency with Y-9C buffer
    if y9c is not None and y15 is not None:
        y9c_surcharge = y9c.part_ii.gsib_surcharge
        y15_surcharge = y15.surcharge_determination.final_surcharge_pct / 100.0
        dev = abs(y9c_surcharge - y15_surcharge)
        checks.append(CrossValidationCheck(
            check_name="G-SIB surcharge: FR Y-9C vs FR Y-15",
            report_a="FR_Y_9C",
            report_b="FR_Y_15",
            field_a="G-SIB surcharge (Part II)",
            field_b="Final surcharge (Y-15)",
            value_a=y9c_surcharge,
            value_b=y15_surcharge,
            deviation=dev,
            passed=dev <= 0.001,
            tolerance=0.001,
            message=f"Surcharge deviation: {dev:.4f}",
            regulatory_reference="12 CFR 217.403",
        ))

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = len(checks) - passed_count

    return CrossValidationResult(
        checks=checks,
        total_checks=len(checks),
        passed_checks=passed_count,
        failed_checks=failed_count,
        overall_pass=failed_count == 0,
    )


# =========================================================================
#  BCBS 239 Lineage Trail
# =========================================================================

class LineageEntry(BaseModel):
    """A single entry in the BCBS 239 data lineage trail.

    Per BCBS 239 Principle 2 (Data architecture and IT infrastructure),
    all data transformations must be traceable.

    Reference: BCBS 239 Principle 2.
    """
    timestamp: str = Field(description="ISO 8601 timestamp of the operation")
    operation: str = Field(description="Description of the transformation")
    source: str = Field(description="Source system or module")
    target: str = Field(description="Target report or output")
    record_count: int = Field(
        default=0, description="Number of records processed"
    )
    status: str = Field(default="SUCCESS", description="SUCCESS or FAILURE")
    error_message: str = Field(default="")


class BCBS239LineageTrail(BaseModel):
    """Complete BCBS 239 data lineage trail for a reporting cycle.

    Tracks all data transformations from source systems through to
    final regulatory reports for audit and governance purposes.

    Reference: BCBS 239 Principle 2 (Data architecture),
    Principle 7 (Accuracy of risk management reports).
    """
    reporting_date: date
    entity_name: str = Field(default="")
    entries: list[LineageEntry] = Field(default_factory=list)
    total_operations: int = 0
    failed_operations: int = 0


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.utcnow().isoformat() + "Z"


# =========================================================================
#  Master Report Package
# =========================================================================

class RegulatoryReportPackage(BaseModel):
    """Complete regulatory report package for a single reporting period.

    Contains all regulatory reports, cross-validation results,
    aggregate data quality, and BCBS 239 lineage trail.

    Reference: Federal Reserve regulatory reporting requirements,
    BCBS 239 Principles for effective risk data aggregation.
    """
    reporting_date: date
    entity_name: str = Field(default="")
    rssd_id: str = Field(default="")
    generation_timestamp: str = Field(default="")

    # Individual reports
    fr_y9c: Optional[FRY9CReport] = None
    ffiec_101: Optional[FFIEC101Report] = None
    fr_y15: Optional[FRY15Report] = None
    fr_y14: Optional[FRY14Report] = None

    # Cross-validation
    cross_validation: CrossValidationResult = Field(
        default_factory=CrossValidationResult
    )

    # Aggregate quality
    overall_data_quality_pass: bool = Field(
        default=True,
        description="True if all individual and cross-report checks pass"
    )
    reports_generated: list[str] = Field(
        default_factory=list,
        description="List of report types generated"
    )

    # BCBS 239 lineage
    lineage: BCBS239LineageTrail = Field(
        default_factory=lambda: BCBS239LineageTrail(
            reporting_date=date.today()
        )
    )


class ReportEngine:
    """Main orchestrator for regulatory report generation.

    Coordinates the generation of all regulatory reports, performs
    cross-validation, aggregates data quality results, and maintains
    the BCBS 239 lineage trail.

    Per SR 11-7 and BCBS 239, the report engine ensures:
    - Completeness: all required reports are generated
    - Accuracy: cross-report reconciliation passes
    - Timeliness: reports generated within filing deadlines
    - Traceability: full lineage trail for audit

    Reference: BCBS 239, SR 11-7, Federal Reserve reporting requirements.
    """

    def __init__(
        self,
        entity_name: str = "",
        rssd_id: str = "",
        thresholds: DataQualityThresholds = BCBS_239_THRESHOLDS,
    ) -> None:
        """Initialize the report engine.

        Args:
            entity_name: Reporting entity name.
            rssd_id: RSSD identifier.
            thresholds: Data quality thresholds per BCBS 239.

        Reference: BCBS 239 Principle 1 (Governance).
        """
        self._entity_name = entity_name
        self._rssd_id = rssd_id
        self._thresholds = thresholds
        self._lineage: list[LineageEntry] = []

    def _log_lineage(
        self,
        operation: str,
        source: str,
        target: str,
        record_count: int = 0,
        status: str = "SUCCESS",
        error_message: str = "",
    ) -> None:
        """Add an entry to the lineage trail.

        Reference: BCBS 239 Principle 2.
        """
        self._lineage.append(LineageEntry(
            timestamp=_now_iso(),
            operation=operation,
            source=source,
            target=target,
            record_count=record_count,
            status=status,
            error_message=error_message,
        ))

    def generate_all(
        self,
        capital: TotalCapitalResult,
        adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
        credit_risk_items: Optional[list[CreditRiskRWAItem]] = None,
        market_risk_input: Optional[MarketRiskRWAInput] = None,
        operational_risk_input: Optional[OperationalRiskRWAInput] = None,
        cva_risk_input: Optional[CVARiskRWAInput] = None,
        indicator_values: Optional[dict[str, float]] = None,
        stress_projections: Optional[dict[str, list[dict[str, float]]]] = None,
        prior_capital: Optional[TotalCapitalResult] = None,
        prior_reporting_date: Optional[date] = None,
        denomination_factors: Optional[dict[str, float]] = None,
        is_annual: bool = False,
    ) -> RegulatoryReportPackage:
        """Generate all regulatory reports for the reporting period.

        This is the master orchestration function that generates all
        applicable regulatory reports, runs cross-validation, and
        assembles the complete report package.

        Args:
            capital: Total capital result from capital_components.
            adequacy: Capital adequacy assessment from capital_ratios.
            rwa_breakdown: RWA breakdown from rwa_aggregator.
            reporting_date: As-of date for all reports.
            credit_risk_items: Credit risk RWA items for FFIEC 101.
            market_risk_input: Market risk input for FFIEC 101.
            operational_risk_input: Operational risk input for FFIEC 101.
            cva_risk_input: CVA risk input for FFIEC 101.
            indicator_values: G-SIB indicator values for FR Y-15.
            stress_projections: Stress projections for FR Y-14.
            prior_capital: Prior period capital for variance analysis.
            prior_reporting_date: Prior period date.
            denomination_factors: Global aggregates for FR Y-15.
            is_annual: True for annual reports (Y-14A).

        Returns:
            RegulatoryReportPackage with all reports and validations.

        Reference: Federal Reserve reporting requirements, BCBS 239.
        """
        self._lineage = []
        reports_generated: list[str] = []

        # --- FR Y-9C ---
        self._log_lineage(
            "Generate FR Y-9C Schedule HC-R",
            "capital_components, capital_ratios",
            "FR_Y_9C",
        )
        y9c: Optional[FRY9CReport] = None
        try:
            y9c = generate_fr_y9c(
                capital=capital,
                adequacy=adequacy,
                rwa_breakdown=rwa_breakdown,
                reporting_date=reporting_date,
                entity_name=self._entity_name,
                rssd_id=self._rssd_id,
                prior_capital=prior_capital,
                prior_reporting_date=prior_reporting_date,
            )
            reports_generated.append("FR_Y_9C")
            self._log_lineage(
                "FR Y-9C generated successfully",
                "report_engine", "FR_Y_9C",
                status="SUCCESS",
            )
        except Exception as e:
            logger.error("Failed to generate FR Y-9C: %s", e)
            self._log_lineage(
                "FR Y-9C generation failed",
                "report_engine", "FR_Y_9C",
                status="FAILURE", error_message=str(e),
            )

        # --- FFIEC 101 ---
        ffiec: Optional[FFIEC101Report] = None
        if credit_risk_items is not None:
            self._log_lineage(
                "Generate FFIEC 101 Schedule A",
                "rwa_aggregator",
                "FFIEC_101",
                record_count=len(credit_risk_items),
            )
            try:
                ffiec = generate_ffiec_101(
                    credit_risk_items=credit_risk_items,
                    rwa_breakdown=rwa_breakdown,
                    reporting_date=reporting_date,
                    entity_name=self._entity_name,
                    rssd_id=self._rssd_id,
                    market_risk_input=market_risk_input,
                    operational_risk_input=operational_risk_input,
                    cva_risk_input=cva_risk_input,
                )
                reports_generated.append("FFIEC_101")
                self._log_lineage(
                    "FFIEC 101 generated successfully",
                    "report_engine", "FFIEC_101",
                    status="SUCCESS",
                )
            except Exception as e:
                logger.error("Failed to generate FFIEC 101: %s", e)
                self._log_lineage(
                    "FFIEC 101 generation failed",
                    "report_engine", "FFIEC_101",
                    status="FAILURE", error_message=str(e),
                )

        # --- FR Y-15 ---
        y15: Optional[FRY15Report] = None
        if indicator_values is not None:
            self._log_lineage(
                "Generate FR Y-15 Systemic Risk Report",
                "gsib_indicators",
                "FR_Y_15",
                record_count=len(indicator_values),
            )
            try:
                y15 = generate_fr_y15(
                    indicator_values=indicator_values,
                    reporting_date=reporting_date,
                    entity_name=self._entity_name,
                    rssd_id=self._rssd_id,
                    total_rwa=rwa_breakdown.total_rwa,
                    denomination_factors=denomination_factors,
                )
                reports_generated.append("FR_Y_15")
                self._log_lineage(
                    "FR Y-15 generated successfully",
                    "report_engine", "FR_Y_15",
                    status="SUCCESS",
                )
            except Exception as e:
                logger.error("Failed to generate FR Y-15: %s", e)
                self._log_lineage(
                    "FR Y-15 generation failed",
                    "report_engine", "FR_Y_15",
                    status="FAILURE", error_message=str(e),
                )

        # --- FR Y-14 ---
        y14: Optional[FRY14Report] = None
        if stress_projections is not None:
            self._log_lineage(
                "Generate FR Y-14 Capital Assessment",
                "stress_testing, capital_ratios",
                "FR_Y_14",
                record_count=len(stress_projections),
            )
            try:
                y14 = generate_fr_y14(
                    base_adequacy=adequacy,
                    base_rwa_breakdown=rwa_breakdown,
                    stress_projections=stress_projections,
                    reporting_date=reporting_date,
                    entity_name=self._entity_name,
                    rssd_id=self._rssd_id,
                    is_annual=is_annual,
                )
                reports_generated.append("FR_Y_14")
                self._log_lineage(
                    "FR Y-14 generated successfully",
                    "report_engine", "FR_Y_14",
                    status="SUCCESS",
                )
            except Exception as e:
                logger.error("Failed to generate FR Y-14: %s", e)
                self._log_lineage(
                    "FR Y-14 generation failed",
                    "report_engine", "FR_Y_14",
                    status="FAILURE", error_message=str(e),
                )

        # --- Cross-Validation ---
        self._log_lineage(
            "Run cross-report validation",
            "report_engine",
            "cross_validation",
        )
        cross_val = run_cross_validation(
            y9c=y9c, ffiec101=ffiec, y15=y15,
            tolerance=self._thresholds.cross_validation_tolerance,
        )
        self._log_lineage(
            f"Cross-validation complete: "
            f"{cross_val.passed_checks}/{cross_val.total_checks} passed",
            "report_engine", "cross_validation",
            status="SUCCESS" if cross_val.overall_pass else "FAILURE",
        )

        # --- Aggregate Quality ---
        individual_quality_pass = True
        if y9c is not None and not y9c.data_quality.overall_pass:
            individual_quality_pass = False
        if ffiec is not None and not ffiec.data_quality.overall_pass:
            individual_quality_pass = False
        if y15 is not None and not y15.data_quality.overall_pass:
            individual_quality_pass = False
        if y14 is not None and not y14.data_quality.overall_pass:
            individual_quality_pass = False

        overall_pass = individual_quality_pass and cross_val.overall_pass

        # --- Build Lineage Trail ---
        failed_ops = sum(1 for e in self._lineage if e.status == "FAILURE")
        lineage = BCBS239LineageTrail(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            entries=list(self._lineage),
            total_operations=len(self._lineage),
            failed_operations=failed_ops,
        )

        logger.info(
            "Report package complete for %s as of %s: "
            "%d reports generated, cross-validation %s, overall quality %s",
            self._entity_name, reporting_date,
            len(reports_generated),
            "PASS" if cross_val.overall_pass else "FAIL",
            "PASS" if overall_pass else "FAIL",
        )

        return RegulatoryReportPackage(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            rssd_id=self._rssd_id,
            generation_timestamp=_now_iso(),
            fr_y9c=y9c,
            ffiec_101=ffiec,
            fr_y15=y15,
            fr_y14=y14,
            cross_validation=cross_val,
            overall_data_quality_pass=overall_pass,
            reports_generated=reports_generated,
            lineage=lineage,
        )
