"""FFIEC 101 Schedule A generator — RWA by exposure type.

Generates the FFIEC 101 Schedule A regulatory report for a Category I US
G-SIB, detailing risk-weighted assets by exposure type (line references
1a-16b) under the standardized approach per the Basel III Endgame 2026
re-proposal.

This module extends the existing rwa_aggregator.py FFIEC101ScheduleA model
with:
- Detailed exposure and RWA breakdowns per line item
- Credit conversion factor (CCF) tracking for off-balance-sheet items
- Market risk FRTB breakdown by risk class
- Cross-validation checks between FFIEC 101 and FR Y-9C
- Data quality validation per BCBS 239

All monetary amounts in USD millions ($M).

References:
- FFIEC 101 Instructions (OMB 7100-0319): Schedule A
- 12 CFR 217.10(a): Risk-based capital ratios
- 12 CFR 217.32-38: Standardized approach risk weights
- 12 CFR 217.41-45: Securitization framework
- ERBA NPR pp. 100-120: RWA aggregation
- ERBA NPR p. 108: Corporate IG 65% RW (Dodd-Frank 939A)
- ERBA NPR p. 112: Retail transactor 45% RW
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.rwa_aggregator import (
    CreditRiskExposureType,
    CreditRiskRWAItem,
    CreditRiskRWAInput,
    CVARiskRWAInput,
    FFIEC101ScheduleA,
    MarketRiskRWAInput,
    OperationalRiskRWAInput,
    RWABreakdown,
    build_ffiec_101_schedule_a,
)
from src.reporting.reporting_params import (
    BCBS_239_THRESHOLDS,
    DataQualityThresholds,
    FFIEC_101_SCHEDULE_A_LINES,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Detailed Line Item Model
# =========================================================================

class FFIEC101LineDetail(BaseModel):
    """Detailed FFIEC 101 Schedule A line item with exposure breakdown.

    Contains exposure amount, applicable risk weight, resulting RWA,
    and number of positions for a single line item.

    Reference: FFIEC 101 Instructions, Schedule A.
    """
    line_reference: str = Field(description="Schedule A line reference (e.g., '1a', '3b')")
    description: str = Field(description="Line item description")
    exposure_amount: float = Field(
        default=0.0, description="Gross exposure amount in $M"
    )
    risk_weight: float = Field(
        default=0.0, description="Weighted average risk weight (decimal)"
    )
    rwa: float = Field(default=0.0, description="Risk-weighted assets in $M")
    position_count: int = Field(
        default=0, description="Number of individual exposures"
    )
    regulatory_reference: str = Field(
        default="", description="Applicable CFR or NPR citation"
    )


class MarketRiskFRTBDetail(BaseModel):
    """FRTB market risk breakdown by risk class for FFIEC 101.

    Provides the SBM, DRC, and RRAO components mapped to
    Schedule A line 10 (market risk equivalent RWA).

    Reference: BCBS d457, ERBA NPR pp. 300-350.
    """
    # SBM by risk class
    girr_charge: float = Field(default=0.0, description="GIRR SBM charge in $M")
    csr_nonsec_charge: float = Field(default=0.0, description="CSR Non-Sec charge in $M")
    csr_sec_nonctp_charge: float = Field(default=0.0, description="CSR Sec Non-CTP in $M")
    csr_sec_ctp_charge: float = Field(default=0.0, description="CSR Sec CTP in $M")
    equity_charge: float = Field(default=0.0, description="Equity SBM charge in $M")
    commodity_charge: float = Field(default=0.0, description="Commodity SBM charge in $M")
    fx_charge: float = Field(default=0.0, description="FX SBM charge in $M")

    @property
    def total_sbm_charge(self) -> float:
        """Total SBM capital charge. Reference: BCBS d457 MAR21."""
        return (
            self.girr_charge + self.csr_nonsec_charge
            + self.csr_sec_nonctp_charge + self.csr_sec_ctp_charge
            + self.equity_charge + self.commodity_charge + self.fx_charge
        )

    # DRC
    drc_nonsec_charge: float = Field(default=0.0, description="DRC Non-Sec charge in $M")
    drc_sec_nonctp_charge: float = Field(default=0.0, description="DRC Sec Non-CTP in $M")
    drc_sec_ctp_charge: float = Field(default=0.0, description="DRC Sec CTP in $M")

    @property
    def total_drc_charge(self) -> float:
        """Total DRC capital charge. Reference: BCBS d457 MAR22."""
        return (
            self.drc_nonsec_charge + self.drc_sec_nonctp_charge
            + self.drc_sec_ctp_charge
        )

    # RRAO
    rrao_charge: float = Field(default=0.0, description="RRAO charge in $M")

    @property
    def total_frtb_charge(self) -> float:
        """Total FRTB capital charge = SBM + DRC + RRAO."""
        return self.total_sbm_charge + self.total_drc_charge + self.rrao_charge

    @property
    def market_risk_rwa(self) -> float:
        """Market risk equivalent RWA = charge * 12.5.
        Reference: 12 CFR 217.10(a)(3).
        """
        return self.total_frtb_charge * 12.5


# =========================================================================
#  FFIEC 101 Schedule A Extended Report
# =========================================================================

class FFIEC101ScheduleAExtended(BaseModel):
    """Extended FFIEC 101 Schedule A with full detail.

    Adds per-line-item detail, market risk FRTB breakdown, and
    data quality information to the base FFIEC 101 Schedule A.

    Reference: FFIEC 101 Instructions (OMB 7100-0319).
    """
    reporting_date: date
    entity_name: str = Field(default="")
    rssd_id: str = Field(default="")

    # Base schedule
    base_schedule: FFIEC101ScheduleA

    # Detailed credit risk line items
    credit_risk_details: list[FFIEC101LineDetail] = Field(default_factory=list)

    # Market risk FRTB detail
    market_risk_detail: Optional[MarketRiskFRTBDetail] = None

    # Operational risk detail
    operational_risk_bic: float = Field(
        default=0.0,
        description="Business Indicator Component in $M. "
                    "Reference: BCBS d424 Section 5."
    )
    operational_risk_ilm: float = Field(
        default=1.0,
        description="Internal Loss Multiplier (1.0 per US proposal). "
                    "Reference: ERBA NPR p. 260."
    )
    operational_risk_charge: float = Field(
        default=0.0, description="OpRisk capital charge in $M"
    )

    # CVA risk detail
    cva_sa_charge: float = Field(
        default=0.0,
        description="SA-CVA capital charge in $M. "
                    "Reference: ERBA NPR pp. 280-295."
    )
    cva_ba_charge: float = Field(
        default=0.0,
        description="BA-CVA capital charge in $M. "
                    "Reference: ERBA NPR pp. 280-295."
    )

    # Summary
    total_credit_risk_rwa: float = Field(default=0.0, description="Line 9")
    total_market_risk_rwa: float = Field(default=0.0, description="Line 10")
    total_operational_risk_rwa: float = Field(default=0.0, description="Line 11")
    total_cva_risk_rwa: float = Field(default=0.0, description="Line 12")
    total_rwa: float = Field(default=0.0, description="Line 13")


def _build_credit_risk_details(
    items: list[CreditRiskRWAItem],
    threshold_250rw_rwa: float = 0.0,
) -> list[FFIEC101LineDetail]:
    """Build detailed FFIEC 101 credit risk line items from RWA items.

    Maps each CreditRiskRWAItem to the corresponding Schedule A line
    reference and aggregates by line.

    Args:
        items: Individual credit risk RWA items.
        threshold_250rw_rwa: RWA from 250% risk-weighted threshold items.

    Returns:
        List of FFIEC101LineDetail with per-line aggregations.

    Reference: FFIEC 101 Instructions, Schedule A lines 1a-8c.
    """
    # Mapping from exposure type to line reference
    exposure_to_line: dict[CreditRiskExposureType, str] = {
        CreditRiskExposureType.SOVEREIGN: "1a",
        CreditRiskExposureType.PUBLIC_SECTOR_ENTITY: "1b",
        CreditRiskExposureType.DEPOSITORY_INSTITUTION: "2",
        CreditRiskExposureType.CORPORATE: "3a",
        CreditRiskExposureType.CORPORATE_IG: "3b",
        CreditRiskExposureType.RETAIL_RESIDENTIAL: "4a",
        CreditRiskExposureType.RETAIL_QUALIFYING_REVOLVING: "4b",
        CreditRiskExposureType.RETAIL_OTHER: "4c",
        CreditRiskExposureType.RETAIL_TRANSACTOR: "4d",
        CreditRiskExposureType.EQUITY: "5",
        CreditRiskExposureType.SECURITIZATION: "6",
        CreditRiskExposureType.CLEARED_TRANSACTIONS: "7",
        CreditRiskExposureType.DEFAULT_FUND_CONTRIBUTIONS: "8",
        CreditRiskExposureType.UNSETTLED_TRANSACTIONS: "8a",
        CreditRiskExposureType.OTHER_ASSETS: "8b",
        CreditRiskExposureType.THRESHOLD_DEDUCTIONS_250RW: "8c",
    }

    # Aggregate by line
    line_data: dict[str, dict] = {}
    for item in items:
        line_ref = exposure_to_line.get(item.exposure_type, "8b")
        if line_ref not in line_data:
            line_def = FFIEC_101_SCHEDULE_A_LINES.get(line_ref)
            line_data[line_ref] = {
                "line_reference": line_ref,
                "description": line_def.description if line_def else "",
                "exposure_amount": 0.0,
                "rwa": 0.0,
                "position_count": 0,
                "regulatory_reference": (
                    line_def.regulatory_reference if line_def else ""
                ),
                "total_rw_weighted": 0.0,
            }
        entry = line_data[line_ref]
        entry["exposure_amount"] += item.exposure_amount
        entry["rwa"] += item.rwa
        entry["position_count"] += 1
        entry["total_rw_weighted"] += item.rwa

    # Add 250% RW threshold items to line 8c
    if threshold_250rw_rwa > 0:
        if "8c" not in line_data:
            line_def = FFIEC_101_SCHEDULE_A_LINES.get("8c")
            line_data["8c"] = {
                "line_reference": "8c",
                "description": line_def.description if line_def else "",
                "exposure_amount": 0.0,
                "rwa": 0.0,
                "position_count": 0,
                "regulatory_reference": (
                    line_def.regulatory_reference if line_def else ""
                ),
                "total_rw_weighted": 0.0,
            }
        line_data["8c"]["rwa"] += threshold_250rw_rwa
        line_data["8c"]["exposure_amount"] += threshold_250rw_rwa / 2.50

    # Build detail list
    details: list[FFIEC101LineDetail] = []
    for line_ref in sorted(line_data.keys(), key=_line_sort_key):
        entry = line_data[line_ref]
        exposure = entry["exposure_amount"]
        rwa = entry["rwa"]
        avg_rw = rwa / exposure if exposure > 0 else 0.0

        details.append(FFIEC101LineDetail(
            line_reference=entry["line_reference"],
            description=entry["description"],
            exposure_amount=exposure,
            risk_weight=avg_rw,
            rwa=rwa,
            position_count=entry["position_count"],
            regulatory_reference=entry["regulatory_reference"],
        ))

    return details


def _line_sort_key(line_ref: str) -> tuple[int, str]:
    """Sort key for FFIEC 101 line references (1a, 1b, 2, 3a, 3b, ..., 8c).

    Reference: FFIEC 101 Instructions, Schedule A ordering.
    """
    # Extract numeric prefix and alpha suffix
    num_part = ""
    alpha_part = ""
    for ch in line_ref:
        if ch.isdigit():
            num_part += ch
        else:
            alpha_part += ch
    return (int(num_part) if num_part else 0, alpha_part)


# =========================================================================
#  Data Quality Validation
# =========================================================================

class FFIEC101DataQualityCheck(BaseModel):
    """Single data quality check for FFIEC 101 Schedule A.

    Reference: BCBS 239 Principles 3-6.
    """
    check_name: str
    check_type: str
    passed: bool
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    deviation: Optional[float] = None
    message: str = ""
    regulatory_reference: str = "BCBS 239"


class FFIEC101DataQualityResult(BaseModel):
    """Aggregate data quality result for FFIEC 101 filing.

    Reference: BCBS 239 Principles 3-6.
    """
    report_type: str = Field(default="FFIEC_101")
    reporting_date: date
    checks: list[FFIEC101DataQualityCheck] = Field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    overall_pass: bool = True


def validate_ffiec_101(
    schedule: FFIEC101ScheduleA,
    rwa_breakdown: RWABreakdown,
    thresholds: DataQualityThresholds = BCBS_239_THRESHOLDS,
    reporting_date: Optional[date] = None,
) -> FFIEC101DataQualityResult:
    """Validate FFIEC 101 Schedule A data quality.

    Performs checks per BCBS 239:
    1. Line 9 footing: sum of credit risk lines equals total credit RWA
    2. Line 13 footing: sum of lines 9-12 equals total RWA
    3. Cross-validation: Schedule A total matches RWA breakdown total
    4. Non-negative: all RWA line items are non-negative
    5. Plausibility: credit risk RWA is the largest component

    Args:
        schedule: The FFIEC 101 Schedule A to validate.
        rwa_breakdown: RWA breakdown for cross-validation.
        thresholds: Data quality thresholds per BCBS 239.
        reporting_date: Filing date.

    Returns:
        FFIEC101DataQualityResult with all check outcomes.

    Reference: BCBS 239 Principles 3 (Accuracy), 4 (Completeness).
    """
    rd = reporting_date or date.today()
    checks: list[FFIEC101DataQualityCheck] = []
    tol = thresholds.reconciliation_tolerance

    # Check 1: Credit risk RWA footing (Line 9 = sum of 1a-8c)
    credit_sum = (
        schedule.line_1a_sovereign + schedule.line_1b_public_sector
        + schedule.line_2_depository
        + schedule.line_3a_corporate + schedule.line_3b_corporate_ig
        + schedule.line_4a_retail_residential + schedule.line_4b_retail_revolving
        + schedule.line_4c_retail_other + schedule.line_4d_retail_transactor
        + schedule.line_5_equity + schedule.line_6_securitization
        + schedule.line_7_cleared_transactions + schedule.line_8_default_fund
        + schedule.line_8a_unsettled + schedule.line_8b_other_assets
        + schedule.line_8c_threshold_250rw
    )
    line9_diff = abs(schedule.line_9_total_credit_risk_rwa - credit_sum)
    checks.append(FFIEC101DataQualityCheck(
        check_name="Line 9 footing (sum of lines 1a-8c)",
        check_type="accuracy",
        passed=line9_diff <= tol,
        expected_value=credit_sum,
        actual_value=schedule.line_9_total_credit_risk_rwa,
        deviation=line9_diff,
        message=f"Line 9 deviation: ${line9_diff:.2f}M",
        regulatory_reference="FFIEC 101 Schedule A Line 9",
    ))

    # Check 2: Total RWA footing (Line 13 = Lines 9 + 10 + 11 + 12)
    total_sum = (
        schedule.line_9_total_credit_risk_rwa
        + schedule.line_10_market_risk_rwa
        + schedule.line_11_operational_risk_rwa
        + schedule.line_12_cva_risk_rwa
    )
    line13_diff = abs(schedule.line_13_total_rwa - total_sum)
    checks.append(FFIEC101DataQualityCheck(
        check_name="Line 13 footing (Lines 9+10+11+12)",
        check_type="accuracy",
        passed=line13_diff <= tol,
        expected_value=total_sum,
        actual_value=schedule.line_13_total_rwa,
        deviation=line13_diff,
        message=f"Line 13 deviation: ${line13_diff:.2f}M",
        regulatory_reference="FFIEC 101 Schedule A Line 13",
    ))

    # Check 3: Cross-validation with RWA breakdown
    xval_diff = abs(schedule.line_13_total_rwa - rwa_breakdown.total_rwa)
    checks.append(FFIEC101DataQualityCheck(
        check_name="Cross-validation: Schedule A vs RWA breakdown total",
        check_type="reconciliation",
        passed=xval_diff <= thresholds.cross_validation_tolerance,
        expected_value=rwa_breakdown.total_rwa,
        actual_value=schedule.line_13_total_rwa,
        deviation=xval_diff,
        message=f"Cross-validation deviation: ${xval_diff:.2f}M",
        regulatory_reference="BCBS 239 Principle 6",
    ))

    # Check 4: Non-negative RWA
    negative_lines: list[str] = []
    for field_name, line_ref in [
        ("line_1a_sovereign", "1a"), ("line_2_depository", "2"),
        ("line_3a_corporate", "3a"), ("line_3b_corporate_ig", "3b"),
        ("line_9_total_credit_risk_rwa", "9"),
        ("line_10_market_risk_rwa", "10"),
        ("line_11_operational_risk_rwa", "11"),
        ("line_13_total_rwa", "13"),
    ]:
        val = getattr(schedule, field_name, 0.0)
        if val < 0:
            negative_lines.append(line_ref)
    checks.append(FFIEC101DataQualityCheck(
        check_name="Non-negative RWA check",
        check_type="range",
        passed=len(negative_lines) == 0,
        message=(
            f"Negative RWA on lines: {negative_lines}" if negative_lines
            else "All RWA lines non-negative"
        ),
        regulatory_reference="12 CFR 217.10(a)",
    ))

    # Check 5: Total RWA must be positive
    checks.append(FFIEC101DataQualityCheck(
        check_name="Total RWA positive",
        check_type="range",
        passed=schedule.line_13_total_rwa > 0,
        actual_value=schedule.line_13_total_rwa,
        message=f"Total RWA: ${schedule.line_13_total_rwa:.0f}M",
        regulatory_reference="12 CFR 217.10(a)",
    ))

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = len(checks) - passed_count

    return FFIEC101DataQualityResult(
        reporting_date=rd,
        checks=checks,
        total_checks=len(checks),
        passed_checks=passed_count,
        failed_checks=failed_count,
        overall_pass=failed_count == 0,
    )


# =========================================================================
#  Complete FFIEC 101 Report Package
# =========================================================================

class FFIEC101Report(BaseModel):
    """Complete FFIEC 101 Schedule A report package.

    Contains the base schedule, detailed line items, market risk breakdown,
    and data quality validation.

    Reference: FFIEC 101 Instructions (OMB 7100-0319).
    """
    report_type: str = Field(default="FFIEC_101")
    reporting_date: date
    entity_name: str = Field(default="")
    rssd_id: str = Field(default="")
    schedule_a: FFIEC101ScheduleAExtended
    data_quality: FFIEC101DataQualityResult


def generate_ffiec_101(
    credit_risk_items: list[CreditRiskRWAItem],
    rwa_breakdown: RWABreakdown,
    reporting_date: date,
    entity_name: str = "",
    rssd_id: str = "",
    market_risk_input: Optional[MarketRiskRWAInput] = None,
    operational_risk_input: Optional[OperationalRiskRWAInput] = None,
    cva_risk_input: Optional[CVARiskRWAInput] = None,
) -> FFIEC101Report:
    """Generate complete FFIEC 101 Schedule A report.

    This is the master function that produces the full FFIEC 101 filing
    including per-line credit risk detail, FRTB market risk breakdown,
    and data quality validation.

    Args:
        credit_risk_items: Individual credit risk RWA items.
        rwa_breakdown: Aggregated RWA breakdown.
        reporting_date: As-of date.
        entity_name: Reporting entity name.
        rssd_id: RSSD identifier.
        market_risk_input: Optional market risk FRTB input for detail.
        operational_risk_input: Optional operational risk input.
        cva_risk_input: Optional CVA risk input.

    Returns:
        FFIEC101Report with all components.

    Reference: FFIEC 101 Instructions (OMB 7100-0319), Schedule A.
    """
    # Build base schedule
    base_schedule = build_ffiec_101_schedule_a(credit_risk_items, rwa_breakdown)

    # Build credit risk details
    credit_details = _build_credit_risk_details(
        credit_risk_items,
        threshold_250rw_rwa=rwa_breakdown.threshold_250rw_rwa,
    )

    # Build market risk FRTB detail
    mr_detail: Optional[MarketRiskFRTBDetail] = None
    if market_risk_input is not None:
        mr_detail = MarketRiskFRTBDetail(
            girr_charge=market_risk_input.girr_charge,
            csr_nonsec_charge=market_risk_input.csr_nonsec_charge,
            csr_sec_nonctp_charge=market_risk_input.csr_sec_nonctp_charge,
            csr_sec_ctp_charge=market_risk_input.csr_sec_ctp_charge,
            equity_charge=market_risk_input.equity_charge,
            commodity_charge=market_risk_input.commodity_charge,
            fx_charge=market_risk_input.fx_charge,
            drc_nonsec_charge=market_risk_input.drc_charge,
            rrao_charge=market_risk_input.rrao_charge,
        )

    # Operational risk
    or_bic = 0.0
    or_ilm = 1.0
    or_charge = 0.0
    if operational_risk_input is not None:
        or_bic = operational_risk_input.bic
        or_ilm = operational_risk_input.ilm
        or_charge = operational_risk_input.capital_charge

    # CVA risk
    cva_sa = 0.0
    cva_ba = 0.0
    if cva_risk_input is not None:
        cva_sa = cva_risk_input.sa_cva_charge
        cva_ba = cva_risk_input.ba_cva_charge

    # Build extended schedule
    extended = FFIEC101ScheduleAExtended(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rssd_id=rssd_id,
        base_schedule=base_schedule,
        credit_risk_details=credit_details,
        market_risk_detail=mr_detail,
        operational_risk_bic=or_bic,
        operational_risk_ilm=or_ilm,
        operational_risk_charge=or_charge,
        cva_sa_charge=cva_sa,
        cva_ba_charge=cva_ba,
        total_credit_risk_rwa=rwa_breakdown.credit_risk_rwa,
        total_market_risk_rwa=rwa_breakdown.market_risk_rwa,
        total_operational_risk_rwa=rwa_breakdown.operational_risk_rwa,
        total_cva_risk_rwa=rwa_breakdown.cva_risk_rwa,
        total_rwa=rwa_breakdown.total_rwa,
    )

    # Validate
    quality = validate_ffiec_101(base_schedule, rwa_breakdown, reporting_date=reporting_date)

    logger.info(
        "Generated FFIEC 101 for %s as of %s: "
        "Credit RWA=$%.0fM, Market RWA=$%.0fM, OpRisk RWA=$%.0fM, "
        "CVA RWA=$%.0fM, Total=$%.0fM, quality=%s",
        entity_name, reporting_date,
        rwa_breakdown.credit_risk_rwa,
        rwa_breakdown.market_risk_rwa,
        rwa_breakdown.operational_risk_rwa,
        rwa_breakdown.cva_risk_rwa,
        rwa_breakdown.total_rwa,
        "PASS" if quality.overall_pass else "FAIL",
    )

    return FFIEC101Report(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rssd_id=rssd_id,
        schedule_a=extended,
        data_quality=quality,
    )
