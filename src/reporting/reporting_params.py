"""Reporting parameters — report definitions, line item mappings, filing frequencies.

Defines the regulatory reporting framework for a Category I US G-SIB under
the Basel III Endgame 2026 re-proposal, including:
- FR Y-9C Schedule HC-R line item definitions (17 capital items + RWA)
- FFIEC 101 Schedule A line references (1a-16b)
- FR Y-15 Systemic Risk Report schedule structure (12 indicators)
- FR Y-14A/Q capital assessment schedule layout
- Filing frequencies and deadlines
- Data quality validation thresholds per BCBS 239

All monetary amounts in USD millions ($M).

References:
- FR Y-9C Instructions: Schedule HC-R Parts I & II
- FFIEC 101 Instructions: Schedule A — Risk-Weighted Assets
- FR Y-15 Instructions (OMB 7100-0352): Systemic Risk Report
- FR Y-14A/Q Instructions: Capital Assessment and Stress Testing
- BCBS 239: Principles for effective risk data aggregation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =========================================================================
#  Filing Frequencies and Deadlines
#  Reference: Federal Reserve reporting requirements
# =========================================================================

class FilingFrequency(Enum):
    """Regulatory report filing frequencies.

    Reference: Federal Reserve Board reporting calendar.
    """
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"
    MONTHLY = "MONTHLY"
    AD_HOC = "AD_HOC"


class ReportType(Enum):
    """Federal Reserve regulatory report types.

    Reference: Federal Reserve Board reporting forms index.
    """
    FR_Y_9C = "FR_Y_9C"
    FFIEC_101 = "FFIEC_101"
    FR_Y_15 = "FR_Y_15"
    FR_Y_14A = "FR_Y_14A"
    FR_Y_14Q = "FR_Y_14Q"
    PILLAR_3 = "PILLAR_3"


@dataclass(frozen=True)
class ReportDefinition:
    """Definition of a regulatory report.

    Attributes:
        report_type: Enumerated report type.
        full_name: Official report name.
        description: Brief description of report content.
        frequency: Filing frequency.
        omb_number: OMB control number.
        filing_deadline_days: Days after quarter-end for filing.
        applicable_to: Bank categories for which report is required.
        regulatory_citation: Primary regulatory citation.
    """
    report_type: ReportType
    full_name: str
    description: str
    frequency: FilingFrequency
    omb_number: str
    filing_deadline_days: int
    applicable_to: str
    regulatory_citation: str


# Report definitions
# Reference: Federal Reserve reporting forms index

REPORT_DEFINITIONS: dict[ReportType, ReportDefinition] = {
    ReportType.FR_Y_9C: ReportDefinition(
        report_type=ReportType.FR_Y_9C,
        full_name="Consolidated Financial Statements for Holding Companies",
        description="Schedule HC-R: Regulatory capital components and ratios",
        frequency=FilingFrequency.QUARTERLY,
        omb_number="7100-0128",
        filing_deadline_days=40,
        applicable_to="All BHCs with total consolidated assets >= $500M",
        regulatory_citation="12 CFR 225.5(b), 12 CFR 217.10-22",
    ),
    ReportType.FFIEC_101: ReportDefinition(
        report_type=ReportType.FFIEC_101,
        full_name="Regulatory Capital Reporting for Institutions Subject to the Advanced Capital Adequacy Framework",
        description="Schedule A: Risk-weighted assets by exposure type",
        frequency=FilingFrequency.QUARTERLY,
        omb_number="7100-0319",
        filing_deadline_days=60,
        applicable_to="Category I-III banking organizations",
        regulatory_citation="12 CFR 217.100-173",
    ),
    ReportType.FR_Y_15: ReportDefinition(
        report_type=ReportType.FR_Y_15,
        full_name="Banking Organization Systemic Risk Report",
        description="12 systemic risk indicators for G-SIB scoring",
        frequency=FilingFrequency.QUARTERLY,
        omb_number="7100-0352",
        filing_deadline_days=45,
        applicable_to="US G-SIBs and large BHCs (total assets >= $100B)",
        regulatory_citation="12 CFR 217.403-406, BCBS d445",
    ),
    ReportType.FR_Y_14A: ReportDefinition(
        report_type=ReportType.FR_Y_14A,
        full_name="Capital Assessments and Stress Testing — Annual",
        description="Summary, losses, PPNR, loan-level, trading/counterparty schedules",
        frequency=FilingFrequency.ANNUAL,
        omb_number="7100-0341",
        filing_deadline_days=5,
        applicable_to="Category I-IV BHCs (total assets >= $100B)",
        regulatory_citation="12 CFR 252.14, 12 CFR 252.54-56",
    ),
    ReportType.FR_Y_14Q: ReportDefinition(
        report_type=ReportType.FR_Y_14Q,
        full_name="Capital Assessments and Stress Testing — Quarterly",
        description="Quarterly updates of capital assessment schedules",
        frequency=FilingFrequency.QUARTERLY,
        omb_number="7100-0341",
        filing_deadline_days=15,
        applicable_to="Category I-IV BHCs (total assets >= $100B)",
        regulatory_citation="12 CFR 252.14, 12 CFR 252.54-56",
    ),
}


# =========================================================================
#  FR Y-9C Schedule HC-R Line Items
#  Reference: FR Y-9C Instructions — Schedule HC-R Parts I & II
# =========================================================================

@dataclass(frozen=True)
class HCRLineItemDef:
    """Definition of a FR Y-9C Schedule HC-R line item.

    Attributes:
        line_number: Official line number (e.g., '1', '8a', '15a').
        part: HC-R part (I = capital components, II = RWA/ratios).
        description: Official line item description.
        regulatory_reference: CFR citation.
        sign: +1 for additive items, -1 for deductions.
        is_subtotal: True if this is a calculated subtotal line.
    """
    line_number: str
    part: int
    description: str
    regulatory_reference: str
    sign: int = 1
    is_subtotal: bool = False


# HC-R Part I: Regulatory Capital Components (17 key line items)
# Reference: FR Y-9C Instructions Schedule HC-R Part I
HCR_PART_I_LINE_ITEMS: dict[str, HCRLineItemDef] = {
    "1": HCRLineItemDef(
        "1", 1, "Common stock (par value)", "12 CFR 217.20(b)(1)", 1),
    "2": HCRLineItemDef(
        "2", 1, "Surplus (related to common stock)", "12 CFR 217.20(b)(1)", 1),
    "3": HCRLineItemDef(
        "3", 1, "Retained earnings", "12 CFR 217.20(b)(1)", 1),
    "4": HCRLineItemDef(
        "4", 1, "Accumulated other comprehensive income (AOCI)",
        "12 CFR 217.20(b)(2)", 1),
    "5": HCRLineItemDef(
        "5", 1, "Treasury stock, at cost", "12 CFR 217.20(b)", -1),
    "6": HCRLineItemDef(
        "6", 1, "Qualifying CET1 minority interest", "12 CFR 217.21(a)", 1),
    "7": HCRLineItemDef(
        "7", 1, "CET1 capital before deductions", "12 CFR 217.20(b)", 1, True),
    "8": HCRLineItemDef(
        "8", 1, "Goodwill, net of associated DTL",
        "12 CFR 217.22(a)(1)", -1),
    "9": HCRLineItemDef(
        "9", 1, "Other intangible assets, net of associated DTL",
        "12 CFR 217.22(a)(2)", -1),
    "10": HCRLineItemDef(
        "10", 1, "DTAs from NOL/tax credit carryforwards",
        "12 CFR 217.22(a)(3)", -1),
    "10a": HCRLineItemDef(
        "10a", 1, "Other CET1 deductions (pension, gain-on-sale, threshold items)",
        "12 CFR 217.22(a)-(d)", -1),
    "11": HCRLineItemDef(
        "11", 1, "Total CET1 deductions", "12 CFR 217.22", -1, True),
    "12": HCRLineItemDef(
        "12", 1, "CET1 capital", "12 CFR 217.20(b)", 1, True),
    "13": HCRLineItemDef(
        "13", 1, "Qualifying AT1 capital instruments",
        "12 CFR 217.20(c)", 1),
    "14": HCRLineItemDef(
        "14", 1, "Qualifying AT1 minority interest", "12 CFR 217.21(b)", 1),
    "14a": HCRLineItemDef(
        "14a", 1, "AT1 regulatory deductions", "12 CFR 217.22(b)", -1),
    "15": HCRLineItemDef(
        "15", 1, "Additional Tier 1 capital", "12 CFR 217.20(c)", 1, True),
    "15a": HCRLineItemDef(
        "15a", 1, "Tier 1 capital (CET1 + AT1)", "12 CFR 217.20", 1, True),
    "16a": HCRLineItemDef(
        "16a", 1, "Qualifying Tier 2 capital instruments",
        "12 CFR 217.20(d)", 1),
    "16b": HCRLineItemDef(
        "16b", 1, "Eligible ALLL/ACL (capped at 1.25% SA-RWA)",
        "12 CFR 217.20(d)(3)", 1),
    "16c": HCRLineItemDef(
        "16c", 1, "Qualifying Tier 2 minority interest", "12 CFR 217.21(c)", 1),
    "16d": HCRLineItemDef(
        "16d", 1, "Tier 2 regulatory deductions", "12 CFR 217.22(c)", -1),
    "17": HCRLineItemDef(
        "17", 1, "Tier 2 capital", "12 CFR 217.20(d)", 1, True),
    "18": HCRLineItemDef(
        "18", 1, "Total capital (Tier 1 + Tier 2)", "12 CFR 217.20", 1, True),
}


# =========================================================================
#  FFIEC 101 Schedule A Line Items
#  Reference: FFIEC 101 Instructions — Schedule A
# =========================================================================

@dataclass(frozen=True)
class FFIEC101LineItemDef:
    """Definition of an FFIEC 101 Schedule A line item.

    Attributes:
        line_reference: Official line reference (e.g., '1a', '3b', '16b').
        description: Official line item description.
        exposure_category: Broad exposure category for grouping.
        risk_weight_note: Applicable risk weight(s) or calculation method.
        regulatory_reference: Regulatory citation.
    """
    line_reference: str
    description: str
    exposure_category: str
    risk_weight_note: str
    regulatory_reference: str


FFIEC_101_SCHEDULE_A_LINES: dict[str, FFIEC101LineItemDef] = {
    "1a": FFIEC101LineItemDef(
        "1a", "Sovereign exposures", "Credit Risk",
        "0%/20%/50%/100%/150%", "12 CFR 217.32"),
    "1b": FFIEC101LineItemDef(
        "1b", "Public sector entity exposures", "Credit Risk",
        "20%/50%/100%", "12 CFR 217.32"),
    "2": FFIEC101LineItemDef(
        "2", "Depository institution exposures", "Credit Risk",
        "20%/50%/100%/150%", "12 CFR 217.32"),
    "3a": FFIEC101LineItemDef(
        "3a", "Corporate exposures", "Credit Risk",
        "100%", "12 CFR 217.32"),
    "3b": FFIEC101LineItemDef(
        "3b", "Investment grade corporate exposures (self-assessed)",
        "Credit Risk", "65%", "ERBA NPR p. 108 (Dodd-Frank 939A)"),
    "4a": FFIEC101LineItemDef(
        "4a", "Residential mortgage exposures", "Credit Risk",
        "50%/100%", "12 CFR 217.32"),
    "4b": FFIEC101LineItemDef(
        "4b", "Qualifying revolving exposures", "Credit Risk",
        "75%", "12 CFR 217.32"),
    "4c": FFIEC101LineItemDef(
        "4c", "Other retail exposures", "Credit Risk",
        "75%/100%", "12 CFR 217.32"),
    "4d": FFIEC101LineItemDef(
        "4d", "Retail transactor exposures", "Credit Risk",
        "45%", "ERBA NPR p. 112 (not 55% from 2023 NPR)"),
    "5": FFIEC101LineItemDef(
        "5", "Equity exposures", "Credit Risk",
        "100%/250%/300%/400%", "12 CFR 217.52"),
    "6": FFIEC101LineItemDef(
        "6", "Securitization exposures", "Credit Risk",
        "ERBA/SA-SEC", "12 CFR 217.41-45"),
    "7": FFIEC101LineItemDef(
        "7", "Cleared transaction exposures", "Credit Risk",
        "2%/4%", "12 CFR 217.35"),
    "8": FFIEC101LineItemDef(
        "8", "Default fund contribution exposures", "Credit Risk",
        "Various", "12 CFR 217.35"),
    "8a": FFIEC101LineItemDef(
        "8a", "Unsettled transaction exposures", "Credit Risk",
        "100%-1250%", "12 CFR 217.38"),
    "8b": FFIEC101LineItemDef(
        "8b", "Other assets", "Credit Risk",
        "100%", "12 CFR 217.32"),
    "8c": FFIEC101LineItemDef(
        "8c", "Threshold items at 250% risk weight", "Credit Risk",
        "250% (MSA, DTA, significant investments)", "12 CFR 217.22(d)"),
    "9": FFIEC101LineItemDef(
        "9", "Total credit risk RWA", "Subtotal",
        "Sum of lines 1a-8c", "12 CFR 217.10(a)(1)"),
    "10": FFIEC101LineItemDef(
        "10", "Market risk equivalent RWA", "Market Risk",
        "FRTB capital charge * 12.5", "12 CFR 217.10(a)(3)"),
    "11": FFIEC101LineItemDef(
        "11", "Operational risk equivalent RWA", "Operational Risk",
        "BIC * ILM * 12.5 (ILM=1.0)", "BCBS d424 Section 5"),
    "12": FFIEC101LineItemDef(
        "12", "CVA risk equivalent RWA", "CVA Risk",
        "SA-CVA/BA-CVA charge * 12.5", "ERBA NPR pp. 280-295"),
    "13": FFIEC101LineItemDef(
        "13", "Total risk-weighted assets", "Grand Total",
        "Sum of lines 9-12", "12 CFR 217.10(a)"),
}


# =========================================================================
#  FR Y-15 Schedule Definitions
#  Reference: FR Y-15 Instructions (OMB 7100-0352)
# =========================================================================

@dataclass(frozen=True)
class FRY15IndicatorDef:
    """Definition of an FR Y-15 systemic risk indicator.

    Attributes:
        indicator_id: Indicator identifier.
        schedule: FR Y-15 schedule letter (A-G).
        line_number: Line number within schedule.
        description: Official indicator description.
        category: Systemic importance category.
        category_weight: Weight of the category (20% each).
        indicator_weight: Weight within category (equal split).
        regulatory_reference: G-SIB NPR page reference.
    """
    indicator_id: str
    schedule: str
    line_number: str
    description: str
    category: str
    category_weight: float
    indicator_weight: float
    regulatory_reference: str


FR_Y15_INDICATORS: dict[str, FRY15IndicatorDef] = {
    # Category 1: Size (20% weight, 1 indicator)
    "total_exposures": FRY15IndicatorDef(
        "SIZE_1", "A", "1",
        "Total exposures (leverage ratio exposure measure)",
        "Size", 0.20, 1.0,
        "G-SIB NPR p. 16, 12 CFR 217.404(b)(1)"),

    # Category 2: Interconnectedness (20% weight, 3 indicators = 6.67% each)
    "intra_financial_system_assets": FRY15IndicatorDef(
        "INTER_1", "B", "1",
        "Intra-financial system assets",
        "Interconnectedness", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 17, 12 CFR 217.404(b)(2)"),
    "intra_financial_system_liabilities": FRY15IndicatorDef(
        "INTER_2", "B", "2",
        "Intra-financial system liabilities",
        "Interconnectedness", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 17, 12 CFR 217.404(b)(2)"),
    "securities_outstanding": FRY15IndicatorDef(
        "INTER_3", "B", "3",
        "Securities outstanding",
        "Interconnectedness", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 17, 12 CFR 217.404(b)(2)"),

    # Category 3: Substitutability (20% weight, 3 indicators = 6.67% each)
    "payments_activity": FRY15IndicatorDef(
        "SUB_1", "C", "1",
        "Payments activity",
        "Substitutability", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 18, 12 CFR 217.404(b)(3)"),
    "assets_under_custody": FRY15IndicatorDef(
        "SUB_2", "C", "2",
        "Assets under custody",
        "Substitutability", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 18, 12 CFR 217.404(b)(3)"),
    "underwriting_activity": FRY15IndicatorDef(
        "SUB_3", "C", "3",
        "Underwriting activity",
        "Substitutability", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 18, 12 CFR 217.404(b)(3)"),

    # Category 4: Complexity (20% weight, 3 indicators = 6.67% each)
    "otc_derivatives_notional": FRY15IndicatorDef(
        "COMP_1", "D", "1",
        "OTC derivatives notional amount",
        "Complexity", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 19, 12 CFR 217.404(b)(4)"),
    "trading_and_afs_securities": FRY15IndicatorDef(
        "COMP_2", "D", "2",
        "Trading and AFS securities",
        "Complexity", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 20, 12 CFR 217.404(b)(4)"),
    "level_3_assets": FRY15IndicatorDef(
        "COMP_3", "D", "3",
        "Level 3 assets",
        "Complexity", 0.20, 1.0 / 3.0,
        "G-SIB NPR p. 20, 12 CFR 217.404(b)(4)"),

    # Category 5: Cross-Jurisdictional Activity (20% weight, 2 indicators = 10% each)
    "cross_jurisdictional_claims": FRY15IndicatorDef(
        "CJ_1", "E", "1",
        "Cross-jurisdictional claims",
        "Cross-Jurisdictional Activity", 0.20, 0.50,
        "G-SIB NPR p. 21, 12 CFR 217.404(b)(5)"),
    "cross_jurisdictional_liabilities": FRY15IndicatorDef(
        "CJ_2", "E", "2",
        "Cross-jurisdictional liabilities",
        "Cross-Jurisdictional Activity", 0.20, 0.50,
        "G-SIB NPR p. 21, 12 CFR 217.404(b)(5)"),
}


# Method 2 additional indicator: Short-Term Wholesale Funding
# Reference: G-SIB NPR pp. 30-35, 12 CFR 217.406
FR_Y15_STWF_INDICATORS: dict[str, FRY15IndicatorDef] = {
    "stwf_0_30_days": FRY15IndicatorDef(
        "STWF_1", "G", "1",
        "Wholesale funding maturing in 0-30 days",
        "STWF (Method 2)", 0.20, 0.25,
        "G-SIB NPR p. 32, 12 CFR 217.406(b)"),
    "stwf_31_90_days": FRY15IndicatorDef(
        "STWF_2", "G", "2",
        "Wholesale funding maturing in 31-90 days",
        "STWF (Method 2)", 0.20, 0.25,
        "G-SIB NPR p. 32, 12 CFR 217.406(b)"),
    "stwf_91_180_days": FRY15IndicatorDef(
        "STWF_3", "G", "3",
        "Wholesale funding maturing in 91-180 days",
        "STWF (Method 2)", 0.20, 0.25,
        "G-SIB NPR p. 32, 12 CFR 217.406(b)"),
    "stwf_181_365_days": FRY15IndicatorDef(
        "STWF_4", "G", "4",
        "Wholesale funding maturing in 181-365 days",
        "STWF (Method 2)", 0.20, 0.25,
        "G-SIB NPR p. 32, 12 CFR 217.406(b)"),
}


# =========================================================================
#  FR Y-14A/Q Schedule Definitions
#  Reference: FR Y-14A/Q Instructions (OMB 7100-0341)
# =========================================================================

class FRY14ScheduleType(Enum):
    """FR Y-14A/Q schedule types.

    Reference: FR Y-14A/Q Instructions.
    """
    SUMMARY = "SUMMARY"
    LOSSES_REVENUE = "LOSSES_REVENUE"
    PPNR = "PPNR"
    LOAN_LEVEL = "LOAN_LEVEL"
    TRADING_COUNTERPARTY = "TRADING_COUNTERPARTY"
    REGULATORY_CAPITAL = "REGULATORY_CAPITAL"
    BALANCE_SHEET = "BALANCE_SHEET"
    AFS_HTM_SECURITIES = "AFS_HTM_SECURITIES"
    OPERATIONAL_RISK = "OPERATIONAL_RISK"


@dataclass(frozen=True)
class FRY14ScheduleDef:
    """Definition of an FR Y-14A/Q schedule.

    Attributes:
        schedule_type: Schedule type enum.
        schedule_code: Schedule letter/code.
        description: Schedule description.
        frequency: Filing frequency (A=annual, Q=quarterly).
        key_line_items: Number of key line items.
        regulatory_reference: Regulatory citation.
    """
    schedule_type: FRY14ScheduleType
    schedule_code: str
    description: str
    frequency: str
    key_line_items: int
    regulatory_reference: str


FR_Y14_SCHEDULES: dict[FRY14ScheduleType, FRY14ScheduleDef] = {
    FRY14ScheduleType.SUMMARY: FRY14ScheduleDef(
        FRY14ScheduleType.SUMMARY, "A.1",
        "Summary: Projected capital ratios and components over 9 quarters",
        "Q", 25,
        "12 CFR 252.14(a)(2)(i)"),
    FRY14ScheduleType.LOSSES_REVENUE: FRY14ScheduleDef(
        FRY14ScheduleType.LOSSES_REVENUE, "A.2",
        "Losses and Revenue: Projected loan losses, PPNR, other gains/losses",
        "Q", 40,
        "12 CFR 252.14(a)(2)(ii)"),
    FRY14ScheduleType.PPNR: FRY14ScheduleDef(
        FRY14ScheduleType.PPNR, "A.4",
        "Pre-provision net revenue projections",
        "Q", 30,
        "12 CFR 252.14(a)(2)(iii)"),
    FRY14ScheduleType.LOAN_LEVEL: FRY14ScheduleDef(
        FRY14ScheduleType.LOAN_LEVEL, "A.5/Q.1",
        "Loan-level data: CRE, C&I, consumer, mortgage",
        "A/Q", 200,
        "12 CFR 252.14(a)(2)(iv)"),
    FRY14ScheduleType.TRADING_COUNTERPARTY: FRY14ScheduleDef(
        FRY14ScheduleType.TRADING_COUNTERPARTY, "A.6",
        "Trading and counterparty: Mark-to-market, CVA, stress P&L",
        "A", 50,
        "12 CFR 252.14(a)(2)(v)"),
    FRY14ScheduleType.REGULATORY_CAPITAL: FRY14ScheduleDef(
        FRY14ScheduleType.REGULATORY_CAPITAL, "A.7/Q.2",
        "Regulatory capital: Projected capital components under stress",
        "A/Q", 35,
        "12 CFR 252.14(a)(2)(vi)"),
    FRY14ScheduleType.BALANCE_SHEET: FRY14ScheduleDef(
        FRY14ScheduleType.BALANCE_SHEET, "Q.3",
        "Balance sheet: Projected assets, liabilities, equity",
        "Q", 50,
        "12 CFR 252.14(a)(2)(vii)"),
    FRY14ScheduleType.AFS_HTM_SECURITIES: FRY14ScheduleDef(
        FRY14ScheduleType.AFS_HTM_SECURITIES, "Q.4",
        "AFS/HTM securities: Fair value and OCI projections",
        "Q", 20,
        "12 CFR 252.14(a)(2)(viii)"),
    FRY14ScheduleType.OPERATIONAL_RISK: FRY14ScheduleDef(
        FRY14ScheduleType.OPERATIONAL_RISK, "A.9",
        "Operational risk: Internal loss data, scenario analysis",
        "A", 15,
        "12 CFR 252.14(a)(2)(ix)"),
}


# =========================================================================
#  BCBS 239 Data Quality Thresholds
#  Reference: BCBS 239 — Principles for effective risk data aggregation
# =========================================================================

@dataclass(frozen=True)
class DataQualityThresholds:
    """Data quality thresholds for regulatory reporting per BCBS 239.

    Attributes:
        completeness_minimum: Min fraction of non-null required fields (0-1).
        accuracy_tolerance: Max acceptable deviation from expected values.
        timeliness_max_days: Max days data can lag behind reporting date.
        reconciliation_tolerance: Max acceptable reconciliation difference ($M).
        cross_validation_tolerance: Max acceptable cross-report variance ($M).
    """
    completeness_minimum: float = 0.95
    accuracy_tolerance: float = 0.01
    timeliness_max_days: int = 5
    reconciliation_tolerance: float = 1.0
    cross_validation_tolerance: float = 0.5


BCBS_239_THRESHOLDS = DataQualityThresholds(
    completeness_minimum=0.95,
    accuracy_tolerance=0.01,
    timeliness_max_days=5,
    reconciliation_tolerance=1.0,
    cross_validation_tolerance=0.5,
)
"""Default BCBS 239 data quality thresholds.
Reference: BCBS 239 Principles 3 (Accuracy) and 4 (Completeness)."""


# =========================================================================
#  Pillar 3 Template Definitions
#  Reference: BCBS d455 — Pillar 3 disclosure requirements
# =========================================================================

class Pillar3Template(Enum):
    """Pillar 3 disclosure template identifiers.

    Reference: BCBS d455, ERBA NPR pp. 1100-1150.
    """
    OV1 = "OV1"    # Overview of RWA
    KM1 = "KM1"    # Key metrics
    CC1 = "CC1"    # Composition of regulatory capital
    CC2 = "CC2"    # Reconciliation of regulatory capital
    CR1 = "CR1"    # Credit quality of assets
    CR2 = "CR2"    # Changes in stock of defaulted exposures
    CR3 = "CR3"    # CRM techniques overview
    CR4 = "CR4"    # Standardized approach — credit risk
    CR5 = "CR5"    # Standardized approach — exposures by asset class
    SEC1 = "SEC1"  # Securitization exposures in banking book
    SEC2 = "SEC2"  # Securitization exposures in trading book
    SEC3 = "SEC3"  # Securitization exposures in banking book — risk weight
    SEC4 = "SEC4"  # Securitization exposures in banking book — approach
    MR1 = "MR1"    # Market risk under SA
    MR2 = "MR2"    # RWA flow statements for market risk
    MR3 = "MR3"    # IMA values for trading portfolios
    MR4 = "MR4"    # Comparison of VaR estimates with gains/losses
    OR1 = "OR1"    # Operational risk
    LR1 = "LR1"    # Summary comparison of accounting assets vs leverage ratio
    LR2 = "LR2"    # Leverage ratio common disclosure


PILLAR_3_FILING_FREQUENCY: dict[Pillar3Template, FilingFrequency] = {
    Pillar3Template.OV1: FilingFrequency.QUARTERLY,
    Pillar3Template.KM1: FilingFrequency.QUARTERLY,
    Pillar3Template.CC1: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.CC2: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.CR1: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.CR2: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.CR3: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.CR4: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.CR5: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.SEC1: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.SEC2: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.SEC3: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.SEC4: FilingFrequency.SEMI_ANNUAL,
    Pillar3Template.MR1: FilingFrequency.QUARTERLY,
    Pillar3Template.MR2: FilingFrequency.QUARTERLY,
    Pillar3Template.MR3: FilingFrequency.QUARTERLY,
    Pillar3Template.MR4: FilingFrequency.QUARTERLY,
    Pillar3Template.OR1: FilingFrequency.ANNUAL,
    Pillar3Template.LR1: FilingFrequency.QUARTERLY,
    Pillar3Template.LR2: FilingFrequency.QUARTERLY,
}
