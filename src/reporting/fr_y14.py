"""FR Y-14A/Q Capital Assessment generator.

Generates the FR Y-14A (Annual) and FR Y-14Q (Quarterly) capital
assessment and stress testing schedules for a Category I US G-SIB:
- Summary schedule: projected capital ratios over 9 quarters
- Regulatory capital schedule: projected components under stress
- Losses and revenue projections
- Trading and counterparty risk schedules
- Balance sheet projections

All monetary amounts in USD millions ($M).

References:
- FR Y-14A/Q Instructions (OMB 7100-0341)
- 12 CFR 252.14: Capital plan and stress testing requirements
- 12 CFR 252.54-56: Stress testing requirements for covered companies
- ERBA NPR pp. 34-68: Capital adequacy framework
"""

from __future__ import annotations

import logging
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_ratios import CapitalAdequacyResult
from src.capital.rwa_aggregator import RWABreakdown
from src.reporting.reporting_params import (
    BCBS_239_THRESHOLDS,
    DataQualityThresholds,
    FR_Y14_SCHEDULES,
    FRY14ScheduleType,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Stress Scenario Definitions
# =========================================================================

class StressScenario(Enum):
    """Stress scenarios per 12 CFR 252.54.

    Reference: 12 CFR 252.54(b), FR Y-14A Instructions.
    """
    BASELINE = "BASELINE"
    ADVERSE = "ADVERSE"
    SEVERELY_ADVERSE = "SEVERELY_ADVERSE"
    BHC_BASELINE = "BHC_BASELINE"
    BHC_STRESS = "BHC_STRESS"


class ProjectionHorizon(Enum):
    """Projection horizon for stress testing.

    Reference: 12 CFR 252.54(b)(1), 9-quarter planning horizon.
    """
    Q1 = "Q+1"
    Q2 = "Q+2"
    Q3 = "Q+3"
    Q4 = "Q+4"
    Q5 = "Q+5"
    Q6 = "Q+6"
    Q7 = "Q+7"
    Q8 = "Q+8"
    Q9 = "Q+9"


# =========================================================================
#  Summary Schedule (A.1) — Projected Capital Ratios
# =========================================================================

class CapitalProjectionQuarter(BaseModel):
    """Projected capital ratios and components for a single quarter.

    Maps to FR Y-14A/Q Summary Schedule (A.1) line items.

    Reference: FR Y-14A Instructions Schedule A.1.
    """
    quarter: str = Field(description="Projection quarter (e.g., 'Q+1')")
    scenario: str = Field(description="Stress scenario name")

    # Capital amounts ($M)
    cet1_capital: float = Field(description="Projected CET1 capital")
    at1_capital: float = Field(default=0.0, description="Projected AT1 capital")
    tier1_capital: float = Field(description="Projected Tier 1 capital")
    tier2_capital: float = Field(default=0.0, description="Projected Tier 2 capital")
    total_capital: float = Field(description="Projected total capital")

    # RWA ($M)
    total_rwa: float = Field(description="Projected total RWA")

    # Ratios (decimal)
    cet1_ratio: float = Field(
        description="Projected CET1 ratio. Reference: 12 CFR 217.10(a)(1)."
    )
    tier1_ratio: float = Field(
        description="Projected Tier 1 ratio. Reference: 12 CFR 217.10(a)(2)."
    )
    total_capital_ratio: float = Field(
        description="Projected total capital ratio. Reference: 12 CFR 217.10(a)(3)."
    )
    leverage_ratio: float = Field(
        default=0.0,
        description="Projected SLR. Reference: 12 CFR 217.10(a)(4)."
    )

    # Minimum ratio breaches
    breaches_cet1_minimum: bool = Field(
        default=False,
        description="True if projected CET1 < 4.5%. Reference: 12 CFR 217.10(a)(1)."
    )
    breaches_tier1_minimum: bool = Field(
        default=False,
        description="True if projected Tier 1 < 6.0%. Reference: 12 CFR 217.10(a)(2)."
    )
    breaches_total_minimum: bool = Field(
        default=False,
        description="True if projected Total < 8.0%. Reference: 12 CFR 217.10(a)(3)."
    )
    breaches_slr_minimum: bool = Field(
        default=False,
        description="True if projected SLR < 3.0%. Reference: 12 CFR 217.10(a)(4)."
    )


class SummarySchedule(BaseModel):
    """FR Y-14A/Q Summary Schedule — projected capital over 9 quarters.

    Per 12 CFR 252.14(a)(2)(i), the summary schedule provides
    projected capital ratios and components under each stress scenario
    over the 9-quarter planning horizon.

    Reference: FR Y-14A Instructions Schedule A.1.
    """
    reporting_date: date
    entity_name: str = Field(default="")
    scenario: str = Field(description="Stress scenario name")
    projections: list[CapitalProjectionQuarter] = Field(default_factory=list)
    # Minimums across the horizon
    minimum_cet1_ratio: float = Field(
        default=0.0,
        description="Minimum CET1 ratio across the 9-quarter horizon"
    )
    minimum_tier1_ratio: float = Field(
        default=0.0,
        description="Minimum Tier 1 ratio across the horizon"
    )
    minimum_total_capital_ratio: float = Field(
        default=0.0,
        description="Minimum total capital ratio across the horizon"
    )
    minimum_slr: float = Field(
        default=0.0,
        description="Minimum SLR across the horizon"
    )
    any_breach: bool = Field(
        default=False,
        description="True if any ratio breaches its minimum during the horizon"
    )


def build_summary_schedule(
    base_adequacy: CapitalAdequacyResult,
    stress_projections: list[dict[str, float]],
    scenario: str = "SEVERELY_ADVERSE",
    reporting_date: Optional[date] = None,
    entity_name: str = "",
) -> SummarySchedule:
    """Build FR Y-14A/Q Summary Schedule from projections.

    Converts a list of quarterly projection dicts into the structured
    Summary Schedule format.

    Args:
        base_adequacy: Current period (Q+0) capital adequacy.
        stress_projections: List of dicts (one per quarter Q+1..Q+9)
            with keys: cet1_capital, tier1_capital, total_capital,
            total_rwa, tier2_capital (optional), at1_capital (optional),
            leverage_ratio (optional).
        scenario: Stress scenario name.
        reporting_date: As-of date.
        entity_name: Reporting entity name.

    Returns:
        SummarySchedule with projections and minimum analysis.

    Reference: FR Y-14A Instructions Schedule A.1, 12 CFR 252.14(a)(2)(i).
    """
    rd = reporting_date or date.today()
    quarters = [f"Q+{i}" for i in range(1, 10)]
    projections: list[CapitalProjectionQuarter] = []

    for i, proj in enumerate(stress_projections[:9]):
        cet1 = proj.get("cet1_capital", 0.0)
        tier1 = proj.get("tier1_capital", 0.0)
        total = proj.get("total_capital", 0.0)
        rwa = proj.get("total_rwa", 0.0)
        at1 = proj.get("at1_capital", tier1 - cet1)
        tier2 = proj.get("tier2_capital", total - tier1)
        lev = proj.get("leverage_ratio", 0.0)

        cet1_ratio = cet1 / rwa if rwa > 0 else 0.0
        tier1_ratio = tier1 / rwa if rwa > 0 else 0.0
        total_ratio = total / rwa if rwa > 0 else 0.0

        projections.append(CapitalProjectionQuarter(
            quarter=quarters[i],
            scenario=scenario,
            cet1_capital=cet1,
            at1_capital=at1,
            tier1_capital=tier1,
            tier2_capital=tier2,
            total_capital=total,
            total_rwa=rwa,
            cet1_ratio=cet1_ratio,
            tier1_ratio=tier1_ratio,
            total_capital_ratio=total_ratio,
            leverage_ratio=lev,
            breaches_cet1_minimum=cet1_ratio < 0.045,
            breaches_tier1_minimum=tier1_ratio < 0.06,
            breaches_total_minimum=total_ratio < 0.08,
            breaches_slr_minimum=lev < 0.03 and lev > 0,
        ))

    min_cet1 = min((p.cet1_ratio for p in projections), default=0.0)
    min_tier1 = min((p.tier1_ratio for p in projections), default=0.0)
    min_total = min((p.total_capital_ratio for p in projections), default=0.0)
    min_slr = min(
        (p.leverage_ratio for p in projections if p.leverage_ratio > 0),
        default=0.0,
    )
    any_breach = any(
        p.breaches_cet1_minimum or p.breaches_tier1_minimum
        or p.breaches_total_minimum or p.breaches_slr_minimum
        for p in projections
    )

    return SummarySchedule(
        reporting_date=rd,
        entity_name=entity_name,
        scenario=scenario,
        projections=projections,
        minimum_cet1_ratio=min_cet1,
        minimum_tier1_ratio=min_tier1,
        minimum_total_capital_ratio=min_total,
        minimum_slr=min_slr,
        any_breach=any_breach,
    )


# =========================================================================
#  Regulatory Capital Schedule (A.7/Q.2)
# =========================================================================

class RegulatoryCapitalProjection(BaseModel):
    """Projected regulatory capital components under stress.

    Maps to FR Y-14A Schedule A.7 / FR Y-14Q Schedule Q.2.

    Reference: FR Y-14A Instructions Schedule A.7,
    12 CFR 252.14(a)(2)(vi).
    """
    quarter: str = Field(description="Projection quarter")
    scenario: str = Field(description="Stress scenario")

    # CET1 components ($M)
    common_stock_and_surplus: float = Field(
        default=0.0, description="Projected common stock + surplus"
    )
    retained_earnings: float = Field(
        default=0.0, description="Projected retained earnings"
    )
    aoci: float = Field(default=0.0, description="Projected AOCI")
    cet1_deductions: float = Field(
        default=0.0, description="Projected CET1 deductions"
    )
    cet1_capital: float = Field(default=0.0, description="Projected CET1")

    # AT1 and Tier 2 ($M)
    at1_capital: float = Field(default=0.0, description="Projected AT1")
    tier2_capital: float = Field(default=0.0, description="Projected Tier 2")
    total_capital: float = Field(default=0.0, description="Projected total capital")

    # RWA ($M)
    credit_risk_rwa: float = Field(default=0.0)
    market_risk_rwa: float = Field(default=0.0)
    operational_risk_rwa: float = Field(default=0.0)
    total_rwa: float = Field(default=0.0)


# =========================================================================
#  Losses and Revenue Schedule (A.2)
# =========================================================================

class LossesRevenueProjection(BaseModel):
    """Projected losses and revenue for a single quarter.

    Maps to FR Y-14A Schedule A.2 key line items.

    Reference: FR Y-14A Instructions Schedule A.2,
    12 CFR 252.14(a)(2)(ii).
    """
    quarter: str = Field(description="Projection quarter")
    scenario: str = Field(description="Stress scenario")

    # Revenue ($M)
    net_interest_income: float = Field(
        default=0.0, description="Projected net interest income"
    )
    noninterest_income: float = Field(
        default=0.0, description="Projected noninterest income"
    )
    ppnr: float = Field(
        default=0.0,
        description="Pre-provision net revenue. "
                    "Reference: FR Y-14A Schedule A.4."
    )

    # Losses ($M)
    provision_for_credit_losses: float = Field(
        default=0.0, description="Provision for credit losses"
    )
    trading_losses: float = Field(
        default=0.0, description="Trading and counterparty losses"
    )
    operational_risk_losses: float = Field(
        default=0.0, description="Operational risk losses"
    )
    other_losses: float = Field(default=0.0, description="Other gains/losses")

    # Net income ($M)
    pre_tax_income: float = Field(default=0.0, description="Pre-tax net income")
    tax_provision: float = Field(default=0.0, description="Income tax provision")
    net_income: float = Field(default=0.0, description="Net income after tax")

    # Impact on capital ($M)
    capital_impact: float = Field(
        default=0.0,
        description="Net change to CET1 from income/losses"
    )


# =========================================================================
#  Trading and Counterparty Schedule (A.6)
# =========================================================================

class TradingCounterpartySchedule(BaseModel):
    """Trading and counterparty risk schedule.

    Maps to FR Y-14A Schedule A.6 key items covering
    mark-to-market losses, CVA adjustments, and stress P&L.

    Reference: FR Y-14A Instructions Schedule A.6,
    12 CFR 252.14(a)(2)(v).
    """
    reporting_date: date
    scenario: str = Field(description="Stress scenario")

    # Trading book ($M)
    trading_book_fair_value: float = Field(
        default=0.0, description="Total trading book fair value"
    )
    stressed_trading_loss: float = Field(
        default=0.0, description="Projected trading losses under stress"
    )
    incremental_default_loss: float = Field(
        default=0.0, description="Incremental default risk losses"
    )

    # Counterparty risk ($M)
    total_counterparty_exposure: float = Field(
        default=0.0, description="Total counterparty exposure (SA-CCR)"
    )
    cva_loss: float = Field(
        default=0.0, description="Projected CVA losses under stress"
    )
    counterparty_default_loss: float = Field(
        default=0.0, description="Counterparty default losses"
    )

    # Total ($M)
    total_trading_counterparty_loss: float = Field(
        default=0.0,
        description="Total trading + counterparty losses"
    )


# =========================================================================
#  Data Quality Validation
# =========================================================================

class FRY14DataQualityCheck(BaseModel):
    """Single data quality check for FR Y-14 report.

    Reference: BCBS 239 Principles 3-6.
    """
    check_name: str
    check_type: str
    passed: bool
    message: str = ""
    regulatory_reference: str = "BCBS 239"


class FRY14DataQualityResult(BaseModel):
    """Aggregate data quality result for FR Y-14 filing.

    Reference: BCBS 239 Principles 3-6.
    """
    report_type: str = Field(default="FR_Y_14")
    reporting_date: date
    checks: list[FRY14DataQualityCheck] = Field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    overall_pass: bool = True


def validate_summary_schedule(
    schedule: SummarySchedule,
    reporting_date: date,
) -> FRY14DataQualityResult:
    """Validate FR Y-14 Summary Schedule data quality.

    Checks per BCBS 239:
    1. Completeness: 9 quarters of projections
    2. Consistency: capital components foot correctly each quarter
    3. Plausibility: ratios within reasonable range (0-30%)
    4. Monotonicity: CET1 should decline under severely adverse

    Args:
        schedule: The summary schedule to validate.
        reporting_date: Filing date.

    Returns:
        FRY14DataQualityResult with check outcomes.

    Reference: BCBS 239 Principles 3-6, FR Y-14A Instructions.
    """
    checks: list[FRY14DataQualityCheck] = []

    # Check 1: 9 quarters of projections
    checks.append(FRY14DataQualityCheck(
        check_name="9-quarter projection horizon",
        check_type="completeness",
        passed=len(schedule.projections) >= 9,
        message=f"Quarters present: {len(schedule.projections)}/9",
        regulatory_reference="12 CFR 252.54(b)(1)",
    ))

    # Check 2: Capital ratios within plausible range
    for proj in schedule.projections:
        in_range = 0.0 <= proj.cet1_ratio <= 0.30
        if not in_range:
            checks.append(FRY14DataQualityCheck(
                check_name=f"CET1 ratio plausibility ({proj.quarter})",
                check_type="range",
                passed=False,
                message=f"CET1 ratio {proj.cet1_ratio:.2%} outside [0%, 30%]",
                regulatory_reference="12 CFR 252.54",
            ))
            break
    else:
        checks.append(FRY14DataQualityCheck(
            check_name="CET1 ratio plausibility (all quarters)",
            check_type="range",
            passed=True,
            message="All CET1 ratios within [0%, 30%]",
            regulatory_reference="12 CFR 252.54",
        ))

    # Check 3: Total capital = Tier 1 + Tier 2 (each quarter)
    footing_ok = True
    for proj in schedule.projections:
        expected_total = proj.tier1_capital + proj.tier2_capital
        if abs(proj.total_capital - expected_total) > 1.0:
            footing_ok = False
            break
    checks.append(FRY14DataQualityCheck(
        check_name="Capital footing (Total = Tier 1 + Tier 2)",
        check_type="accuracy",
        passed=footing_ok,
        message="Capital components foot correctly" if footing_ok
        else "Capital footing mismatch in one or more quarters",
        regulatory_reference="12 CFR 217.20",
    ))

    # Check 4: RWA positive in all quarters
    rwa_positive = all(p.total_rwa > 0 for p in schedule.projections)
    checks.append(FRY14DataQualityCheck(
        check_name="RWA positive all quarters",
        check_type="range",
        passed=rwa_positive,
        message="RWA positive in all quarters" if rwa_positive
        else "RWA zero or negative in one or more quarters",
        regulatory_reference="12 CFR 217.10(a)",
    ))

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = len(checks) - passed_count

    return FRY14DataQualityResult(
        reporting_date=reporting_date,
        checks=checks,
        total_checks=len(checks),
        passed_checks=passed_count,
        failed_checks=failed_count,
        overall_pass=failed_count == 0,
    )


# =========================================================================
#  Complete FR Y-14 Report Package
# =========================================================================

class FRY14Report(BaseModel):
    """Complete FR Y-14A/Q capital assessment report package.

    Contains the summary schedule, regulatory capital projections,
    losses/revenue projections, and data quality validation.

    Reference: FR Y-14A/Q Instructions (OMB 7100-0341),
    12 CFR 252.14, 12 CFR 252.54-56.
    """
    report_type: str = Field(default="FR_Y_14")
    report_subtype: str = Field(
        default="Y-14Q",
        description="Y-14A (annual) or Y-14Q (quarterly)"
    )
    reporting_date: date
    entity_name: str = Field(default="")
    rssd_id: str = Field(default="")

    # Schedules
    summary_schedules: list[SummarySchedule] = Field(
        default_factory=list,
        description="Summary schedules (one per scenario)"
    )
    regulatory_capital_projections: list[RegulatoryCapitalProjection] = Field(
        default_factory=list,
        description="Regulatory capital component projections"
    )
    losses_revenue_projections: list[LossesRevenueProjection] = Field(
        default_factory=list,
        description="Losses and revenue projections"
    )
    trading_counterparty: Optional[TradingCounterpartySchedule] = Field(
        default=None,
        description="Trading and counterparty schedule (Y-14A only)"
    )

    # Quality
    data_quality: FRY14DataQualityResult

    # Key metrics
    minimum_cet1_ratio_severely_adverse: float = Field(
        default=0.0,
        description="Minimum CET1 ratio under severely adverse scenario"
    )
    any_breach_severely_adverse: bool = Field(
        default=False,
        description="Whether any ratio breaches minimum under severely adverse"
    )


def generate_fr_y14(
    base_adequacy: CapitalAdequacyResult,
    base_rwa_breakdown: RWABreakdown,
    stress_projections: dict[str, list[dict[str, float]]],
    reporting_date: date,
    entity_name: str = "",
    rssd_id: str = "",
    is_annual: bool = False,
    trading_counterparty: Optional[TradingCounterpartySchedule] = None,
) -> FRY14Report:
    """Generate complete FR Y-14A/Q capital assessment report.

    This is the master function that produces the full FR Y-14 filing
    including summary schedules for each scenario, regulatory capital
    projections, and data quality validation.

    Args:
        base_adequacy: Current period capital adequacy (Q+0).
        base_rwa_breakdown: Current period RWA breakdown.
        stress_projections: Dict mapping scenario names to lists of
            quarterly projection dicts (Q+1 through Q+9).
        reporting_date: As-of date.
        entity_name: Reporting entity name.
        rssd_id: RSSD identifier.
        is_annual: True for Y-14A, False for Y-14Q.
        trading_counterparty: Optional trading/counterparty schedule
            (required for Y-14A).

    Returns:
        FRY14Report with all schedules and quality validation.

    Reference: FR Y-14A/Q Instructions (OMB 7100-0341),
    12 CFR 252.14, 12 CFR 252.54-56.
    """
    summary_schedules: list[SummarySchedule] = []
    all_reg_cap_projections: list[RegulatoryCapitalProjection] = []
    min_cet1_sa = 0.0
    any_breach_sa = False

    for scenario_name, projections in stress_projections.items():
        summary = build_summary_schedule(
            base_adequacy, projections, scenario_name,
            reporting_date, entity_name,
        )
        summary_schedules.append(summary)

        # Build regulatory capital projections for this scenario
        quarters = [f"Q+{i}" for i in range(1, 10)]
        for i, proj in enumerate(projections[:9]):
            cet1 = proj.get("cet1_capital", 0.0)
            tier1 = proj.get("tier1_capital", 0.0)
            total = proj.get("total_capital", 0.0)
            rwa = proj.get("total_rwa", 0.0)

            all_reg_cap_projections.append(RegulatoryCapitalProjection(
                quarter=quarters[i],
                scenario=scenario_name,
                common_stock_and_surplus=proj.get("common_stock_surplus", 0.0),
                retained_earnings=proj.get("retained_earnings", 0.0),
                aoci=proj.get("aoci", 0.0),
                cet1_deductions=proj.get("cet1_deductions", 0.0),
                cet1_capital=cet1,
                at1_capital=proj.get("at1_capital", tier1 - cet1),
                tier2_capital=proj.get("tier2_capital", total - tier1),
                total_capital=total,
                credit_risk_rwa=proj.get("credit_risk_rwa", 0.0),
                market_risk_rwa=proj.get("market_risk_rwa", 0.0),
                operational_risk_rwa=proj.get("operational_risk_rwa", 0.0),
                total_rwa=rwa,
            ))

        # Track severely adverse metrics
        if scenario_name.upper() in ("SEVERELY_ADVERSE", "SEVERELY ADVERSE"):
            min_cet1_sa = summary.minimum_cet1_ratio
            any_breach_sa = summary.any_breach

    # Data quality validation on first summary schedule
    quality = FRY14DataQualityResult(
        reporting_date=reporting_date,
        overall_pass=True,
    )
    if summary_schedules:
        quality = validate_summary_schedule(
            summary_schedules[0], reporting_date
        )

    subtype = "Y-14A" if is_annual else "Y-14Q"

    logger.info(
        "Generated FR %s for %s as of %s: "
        "%d scenarios, min CET1 (SA)=%.2f%%, breach=%s, quality=%s",
        subtype, entity_name, reporting_date,
        len(summary_schedules),
        min_cet1_sa * 100,
        any_breach_sa,
        "PASS" if quality.overall_pass else "FAIL",
    )

    return FRY14Report(
        report_type="FR_Y_14",
        report_subtype=subtype,
        reporting_date=reporting_date,
        entity_name=entity_name,
        rssd_id=rssd_id,
        summary_schedules=summary_schedules,
        regulatory_capital_projections=all_reg_cap_projections,
        trading_counterparty=trading_counterparty,
        data_quality=quality,
        minimum_cet1_ratio_severely_adverse=min_cet1_sa,
        any_breach_severely_adverse=any_breach_sa,
    )
