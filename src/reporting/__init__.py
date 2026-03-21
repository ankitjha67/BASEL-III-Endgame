"""Reporting module — regulatory report generation for Basel III Endgame.

Generates all Federal Reserve regulatory reports for a Category I US G-SIB:
- FR Y-9C Schedule HC-R: Regulatory capital components and ratios
- FFIEC 101 Schedule A: RWA by exposure type
- FR Y-15: Systemic risk report (G-SIB scoring)
- FR Y-14A/Q: Capital assessment and stress testing
- Cross-report validation and reconciliation per BCBS 239
- BCBS 239 data lineage trail

References:
- FR Y-9C Instructions (OMB 7100-0128)
- FFIEC 101 Instructions (OMB 7100-0319)
- FR Y-15 Instructions (OMB 7100-0352)
- FR Y-14A/Q Instructions (OMB 7100-0341)
- BCBS 239: Principles for effective risk data aggregation
"""

from src.reporting.reporting_params import (
    BCBS_239_THRESHOLDS,
    DataQualityThresholds,
    FFIEC_101_SCHEDULE_A_LINES,
    FilingFrequency,
    FR_Y14_SCHEDULES,
    FR_Y15_INDICATORS,
    FR_Y15_STWF_INDICATORS,
    FRY14ScheduleType,
    HCR_PART_I_LINE_ITEMS,
    Pillar3Template,
    ReportType,
    REPORT_DEFINITIONS,
)

from src.reporting.fr_y9c import (
    FRY9CReport,
    FRY9CDataQualityResult,
    FRY9CMultiPeriod,
    FRY9CPartIIExtended,
    LineItemVariance,
    MaterialityFlag,
    generate_fr_y9c,
    validate_hcr_part_i,
)

from src.reporting.ffiec101 import (
    FFIEC101Report,
    FFIEC101DataQualityResult,
    FFIEC101LineDetail,
    FFIEC101ScheduleAExtended,
    MarketRiskFRTBDetail,
    generate_ffiec_101,
    validate_ffiec_101,
)

from src.reporting.fr_y15 import (
    FRY15Report,
    FRY15DataQualityResult,
    FRY15CategoryScore,
    FRY15IndicatorValue,
    FRY15MethodScore,
    FRY15SurchargeDetermination,
    generate_fr_y15,
    validate_fr_y15,
)

from src.reporting.fr_y14 import (
    FRY14Report,
    FRY14DataQualityResult,
    CapitalProjectionQuarter,
    LossesRevenueProjection,
    RegulatoryCapitalProjection,
    StressScenario,
    SummarySchedule,
    TradingCounterpartySchedule,
    generate_fr_y14,
    validate_summary_schedule,
)

from src.reporting.report_engine import (
    BCBS239LineageTrail,
    CrossValidationCheck,
    CrossValidationResult,
    LineageEntry,
    RegulatoryReportPackage,
    ReportEngine,
    run_cross_validation,
)

__all__ = [
    # Parameters
    "BCBS_239_THRESHOLDS",
    "DataQualityThresholds",
    "FFIEC_101_SCHEDULE_A_LINES",
    "FilingFrequency",
    "FR_Y14_SCHEDULES",
    "FR_Y15_INDICATORS",
    "FR_Y15_STWF_INDICATORS",
    "FRY14ScheduleType",
    "HCR_PART_I_LINE_ITEMS",
    "Pillar3Template",
    "ReportType",
    "REPORT_DEFINITIONS",
    # FR Y-9C
    "FRY9CReport",
    "FRY9CDataQualityResult",
    "FRY9CMultiPeriod",
    "FRY9CPartIIExtended",
    "LineItemVariance",
    "MaterialityFlag",
    "generate_fr_y9c",
    "validate_hcr_part_i",
    # FFIEC 101
    "FFIEC101Report",
    "FFIEC101DataQualityResult",
    "FFIEC101LineDetail",
    "FFIEC101ScheduleAExtended",
    "MarketRiskFRTBDetail",
    "generate_ffiec_101",
    "validate_ffiec_101",
    # FR Y-15
    "FRY15Report",
    "FRY15DataQualityResult",
    "FRY15CategoryScore",
    "FRY15IndicatorValue",
    "FRY15MethodScore",
    "FRY15SurchargeDetermination",
    "generate_fr_y15",
    "validate_fr_y15",
    # FR Y-14
    "FRY14Report",
    "FRY14DataQualityResult",
    "CapitalProjectionQuarter",
    "LossesRevenueProjection",
    "RegulatoryCapitalProjection",
    "StressScenario",
    "SummarySchedule",
    "TradingCounterpartySchedule",
    "generate_fr_y14",
    "validate_summary_schedule",
    # Report Engine
    "BCBS239LineageTrail",
    "CrossValidationCheck",
    "CrossValidationResult",
    "LineageEntry",
    "RegulatoryReportPackage",
    "ReportEngine",
    "run_cross_validation",
]
