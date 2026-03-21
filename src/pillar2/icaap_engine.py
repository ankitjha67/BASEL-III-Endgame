"""ICAAP Engine — Internal Capital Adequacy Assessment Process.

Implements the full ICAAP framework for a Category I US G-SIB under
Basel III Endgame 2026. The ICAAP evaluates whether the institution
holds sufficient capital above Pillar 1 minimums to cover all material
risks, including:

1. Pillar 1+ risk add-ons:
   - Concentration risk (single-name, sector, geographic)
   - Interest Rate Risk in the Banking Book (IRRBB)
   - Pension risk (defined benefit pension obligations)
   - Model risk (estimation and implementation errors)
   - Strategic, reputation, country, and residual risks

2. Capital planning buffer:
   - Forward-looking capital projections
   - Planned capital actions (dividends, buybacks, issuance)
   - Organic capital generation vs. growth requirements

3. Management buffer:
   - Operational flexibility for unexpected shocks
   - Internal target above regulatory minimums

4. Stress testing overlay:
   - Capital adequacy under stress scenarios
   - Stress Capital Buffer (SCB) determination

All amounts in USD millions ($M). Ratios as decimals.

References:
- BCBS d309: "Pillar 2 (Supervisory Review Process)" (2006, updated 2019)
- BCBS d309 Principles 1-4: ICAAP requirements
- BCBS d368: "Interest Rate Risk in the Banking Book" (April 2016)
- SR 15-18: Federal Reserve Supervisory Assessment of Capital Planning
- SR 15-19: Heightened Standards for Large Financial Institutions
- SR 11-7: Guidance on Model Risk Management
- 12 CFR 252.153-155: Capital planning requirements
- ERBA NPR pp. 34-58: Capital adequacy framework
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.pillar2.pillar2_params import (
    CAPITAL_PLANNING_BUFFER_DEFAULT,
    CAPITAL_PLANNING_HORIZON_YEARS,
    DEFAULT_PILLAR_2A_RATES,
    MANAGEMENT_BUFFER_DEFAULT,
    Pillar2AAddOnRates,
    Pillar2RiskCategory,
    StressScenarioType,
)
from src.pillar2.buffer_calculator import (
    BufferStackResult,
    MDAAnalysis,
    compute_buffer_stack,
    compute_mda_analysis,
)


# =========================================================================
#  Pillar 2A Risk Add-On Models
# =========================================================================

class Pillar2ARiskAssessment(BaseModel):
    """Assessment of a single Pillar 2A risk category.

    Captures the quantitative add-on and qualitative assessment for
    each risk category not fully covered by Pillar 1.

    Reference: BCBS d309 Principle 1, SR 15-18 Section III.
    """
    category: Pillar2RiskCategory
    description: str = Field(
        default="",
        description="Description of the risk and its drivers"
    )

    # Quantitative
    addon_rate: float = Field(
        description="Capital add-on as fraction of RWA (e.g., 0.005 = 50bp)"
    )
    addon_amount: float = Field(
        default=0.0,
        description="Capital add-on in $M = addon_rate * total_rwa"
    )

    # Qualitative assessment
    risk_rating: str = Field(
        default="MEDIUM",
        description="Qualitative risk rating: LOW / MEDIUM / HIGH / CRITICAL"
    )
    trend: str = Field(
        default="STABLE",
        description="Risk trend: IMPROVING / STABLE / DETERIORATING"
    )
    mitigants: list[str] = Field(
        default_factory=list,
        description="List of risk mitigants in place"
    )

    # Regulatory reference
    regulatory_reference: str = Field(default="")


class ConcentrationRiskAssessment(BaseModel):
    """Detailed assessment of concentration risk for Pillar 2A.

    Covers single-name, sector, and geographic concentration risk
    not captured by Pillar 1 risk weights.

    Reference: BCBS d309 Principle 1(d), SR 15-18 Section III.A.
    """
    # Single-name concentration
    top_10_exposures_pct_cet1: float = Field(
        default=0.0,
        description="Top 10 single-name exposures as % of CET1"
    )
    largest_single_exposure_pct_cet1: float = Field(
        default=0.0,
        description="Largest single counterparty as % of CET1"
    )
    single_name_addon: float = Field(
        default=0.0,
        description="Single-name concentration add-on (rate)"
    )

    # Sector concentration
    largest_sector_pct_portfolio: float = Field(
        default=0.0,
        description="Largest sector as % of total portfolio"
    )
    herfindahl_index_sector: float = Field(
        default=0.0,
        description="Herfindahl-Hirschman Index for sector concentration"
    )
    sector_addon: float = Field(
        default=0.0,
        description="Sector concentration add-on (rate)"
    )

    # Geographic concentration
    largest_country_pct_portfolio: float = Field(
        default=0.0,
        description="Largest country exposure as % of portfolio"
    )
    geographic_addon: float = Field(
        default=0.0,
        description="Geographic concentration add-on (rate)"
    )

    @property
    def total_addon(self) -> float:
        """Total concentration risk add-on.
        Reference: BCBS d309 Principle 1(d)."""
        return self.single_name_addon + self.sector_addon + self.geographic_addon


class PensionRiskAssessment(BaseModel):
    """Assessment of defined benefit pension obligation risk.

    Reference: SR 15-18 Section III.B.
    """
    gross_pension_obligation: float = Field(
        default=0.0,
        description="Gross pension obligation in $M"
    )
    plan_assets: float = Field(
        default=0.0,
        description="Fair value of plan assets in $M"
    )
    funded_status: float = Field(
        default=0.0,
        description="Funded status = assets - obligation in $M"
    )
    funding_ratio: float = Field(
        default=1.0,
        description="Funding ratio = assets / obligation"
    )
    pension_addon_rate: float = Field(
        default=0.0,
        description="Capital add-on rate for pension risk"
    )

    @property
    def is_underfunded(self) -> bool:
        """Whether the pension plan is underfunded.
        Reference: SR 15-18 Section III.B."""
        return self.funded_status < 0


class ModelRiskAssessment(BaseModel):
    """Assessment of model risk for Pillar 2A.

    Reference: SR 11-7, SR 15-18 Section III.C.
    """
    total_models_in_inventory: int = Field(
        default=0,
        description="Total models in the model inventory"
    )
    high_risk_models: int = Field(
        default=0,
        description="Number of models rated as high risk"
    )
    models_past_validation_due: int = Field(
        default=0,
        description="Models past their validation due date"
    )
    model_risk_addon_rate: float = Field(
        default=0.0,
        description="Capital add-on rate for model risk"
    )
    qualitative_assessment: str = Field(
        default="MEDIUM",
        description="Overall model risk rating: LOW / MEDIUM / HIGH"
    )


# =========================================================================
#  Capital Planning Models
# =========================================================================

class CapitalPlanProjection(BaseModel):
    """Capital planning projection for a single quarter.

    Reference: 12 CFR 252.153(e), SR 15-18 Section II.
    """
    quarter: str = Field(description="Quarter label (e.g., 'Q1 2026')")
    quarter_index: int = Field(description="Quarter index from start of plan")

    # Starting position
    starting_cet1: float = Field(description="Beginning CET1 capital in $M")
    starting_rwa: float = Field(description="Beginning RWA in $M")

    # Capital generation
    net_income: float = Field(default=0.0, description="Net income in $M")
    other_comprehensive_income: float = Field(
        default=0.0, description="OCI in $M"
    )

    # Capital actions
    dividends: float = Field(default=0.0, description="Dividends in $M")
    share_buybacks: float = Field(default=0.0, description="Share buybacks in $M")
    at1_issuance: float = Field(
        default=0.0, description="AT1 issuance (net) in $M"
    )
    tier2_issuance: float = Field(
        default=0.0, description="Tier 2 issuance (net) in $M"
    )

    # RWA changes
    rwa_growth: float = Field(default=0.0, description="RWA growth in $M")

    # Ending position
    ending_cet1: float = Field(default=0.0, description="Ending CET1 capital in $M")
    ending_rwa: float = Field(default=0.0, description="Ending RWA in $M")
    ending_cet1_ratio: float = Field(default=0.0, description="Ending CET1 ratio")


class CapitalPlan(BaseModel):
    """Multi-quarter capital plan.

    Reference: 12 CFR 252.153(e), SR 15-18 Section II.
    """
    plan_start_date: date = Field(description="Capital plan start date")
    horizon_quarters: int = Field(
        default=CAPITAL_PLANNING_HORIZON_YEARS * 4,
        description="Planning horizon in quarters"
    )
    projections: list[CapitalPlanProjection] = Field(default_factory=list)

    # Summary metrics
    minimum_cet1_ratio: float = Field(
        default=0.0,
        description="Minimum projected CET1 ratio over the horizon"
    )
    minimum_cet1_quarter: str = Field(
        default="",
        description="Quarter in which minimum CET1 ratio occurs"
    )
    total_capital_distributions: float = Field(
        default=0.0,
        description="Total planned distributions over the horizon in $M"
    )
    ending_cet1_ratio: float = Field(
        default=0.0,
        description="CET1 ratio at end of planning horizon"
    )


# =========================================================================
#  Stress Testing Overlay
# =========================================================================

class StressScenarioResult(BaseModel):
    """Result of capital adequacy under a single stress scenario.

    Reference: 12 CFR 252.54-56, SR 12-7.
    """
    scenario_type: StressScenarioType
    scenario_name: str = Field(default="")

    # Pre-stress
    pre_stress_cet1: float = Field(description="Pre-stress CET1 in $M")
    pre_stress_rwa: float = Field(description="Pre-stress RWA in $M")
    pre_stress_cet1_ratio: float = Field(description="Pre-stress CET1 ratio")

    # Post-stress
    post_stress_cet1: float = Field(description="Post-stress CET1 in $M")
    post_stress_rwa: float = Field(description="Post-stress RWA in $M")
    post_stress_cet1_ratio: float = Field(description="Post-stress CET1 ratio")

    # Impact
    cet1_depletion: float = Field(description="CET1 depletion in $M")
    cet1_ratio_change: float = Field(description="Change in CET1 ratio")

    # Stress losses by category
    credit_losses: float = Field(default=0.0, description="Credit losses in $M")
    market_losses: float = Field(default=0.0, description="Market risk losses in $M")
    operational_losses: float = Field(
        default=0.0, description="Operational losses in $M"
    )
    ppnr: float = Field(
        default=0.0, description="Pre-provision net revenue in $M"
    )

    # Minimum ratios through horizon
    minimum_cet1_ratio: float = Field(
        default=0.0,
        description="Minimum CET1 ratio through 9-quarter horizon"
    )
    breaches_minimum: bool = Field(
        default=False,
        description="Whether post-stress ratio breaches 4.5% CET1 minimum"
    )


# =========================================================================
#  ICAAP Result Model
# =========================================================================

class ICAAPresult(BaseModel):
    """Complete ICAAP assessment result.

    Combines Pillar 1 adequacy, Pillar 2A add-ons, buffer stack,
    capital planning, and stress testing into a comprehensive internal
    capital adequacy assessment.

    Reference: BCBS d309 Principles 1-4, SR 15-18.
    """
    assessment_date: date = Field(description="ICAAP assessment date")
    entity_name: str = Field(default="", description="Entity name")

    # Pillar 1 position
    cet1_capital: float = Field(description="Current CET1 capital in $M")
    tier1_capital: float = Field(description="Current Tier 1 capital in $M")
    total_capital: float = Field(description="Current Total capital in $M")
    total_rwa: float = Field(description="Current total RWA in $M")
    cet1_ratio: float = Field(description="Current CET1 ratio")
    tier1_ratio: float = Field(description="Current Tier 1 ratio")
    total_capital_ratio: float = Field(description="Current Total Capital ratio")
    leverage_ratio: float = Field(default=0.0, description="Current SLR")

    # Pillar 2A risk assessments
    risk_assessments: list[Pillar2ARiskAssessment] = Field(default_factory=list)
    total_pillar_2a_addon_rate: float = Field(
        default=0.0,
        description="Total Pillar 2A add-on as fraction of RWA"
    )
    total_pillar_2a_addon_amount: float = Field(
        default=0.0,
        description="Total Pillar 2A add-on in $M"
    )

    # Detailed risk assessments
    concentration_risk: Optional[ConcentrationRiskAssessment] = None
    pension_risk: Optional[PensionRiskAssessment] = None
    model_risk: Optional[ModelRiskAssessment] = None

    # Buffer stack
    buffer_stack: Optional[BufferStackResult] = None
    mda_analysis: Optional[MDAAnalysis] = None

    # Capital planning
    capital_plan: Optional[CapitalPlan] = None

    # Stress testing
    stress_results: list[StressScenarioResult] = Field(default_factory=list)
    scb_implied: float = Field(
        default=0.025,
        description="Implied SCB from stress testing"
    )

    # Overall assessment
    total_internal_capital_requirement: float = Field(
        default=0.0,
        description="Total internal capital requirement (P1 + P2A + buffers) as rate"
    )
    total_internal_capital_amount: float = Field(
        default=0.0,
        description="Total internal capital requirement in $M"
    )
    capital_surplus_over_internal_target: float = Field(
        default=0.0,
        description="Surplus above internal target in $M"
    )
    capital_surplus_rate: float = Field(
        default=0.0,
        description="Surplus above internal target as rate"
    )

    # Adequacy flags
    meets_pillar1_minimums: bool = Field(default=True)
    meets_buffer_requirements: bool = Field(default=True)
    meets_internal_targets: bool = Field(default=True)
    passes_stress_tests: bool = Field(default=True)
    overall_adequate: bool = Field(
        default=True,
        description="True if capital is adequate across all dimensions"
    )


# =========================================================================
#  ICAAP Computation Functions
# =========================================================================

def assess_pillar2a_risks(
    total_rwa: float,
    addon_rates: Pillar2AAddOnRates = DEFAULT_PILLAR_2A_RATES,
    concentration_risk: Optional[ConcentrationRiskAssessment] = None,
    pension_risk: Optional[PensionRiskAssessment] = None,
    model_risk: Optional[ModelRiskAssessment] = None,
) -> list[Pillar2ARiskAssessment]:
    """Assess all Pillar 2A risks and compute add-ons.

    Evaluates each risk category that is not fully captured by Pillar 1
    and determines the appropriate capital add-on.

    Args:
        total_rwa: Total RWA in $M.
        addon_rates: Pillar 2A add-on rates by category.
        concentration_risk: Optional detailed concentration risk assessment.
        pension_risk: Optional detailed pension risk assessment.
        model_risk: Optional detailed model risk assessment.

    Returns:
        List of Pillar2ARiskAssessment for each risk category.

    Reference: BCBS d309 Principle 1, SR 15-18 Section III.
    """
    assessments: list[Pillar2ARiskAssessment] = []

    # Concentration risk
    conc_rate = addon_rates.concentration_risk
    if concentration_risk is not None:
        conc_rate = concentration_risk.total_addon
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.CONCENTRATION_RISK,
        description="Single-name, sector, and geographic concentration risk",
        addon_rate=conc_rate,
        addon_amount=conc_rate * total_rwa,
        regulatory_reference="BCBS d309 Principle 1(d)",
    ))

    # IRRBB
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.IRRBB,
        description="Interest rate risk in the banking book per BCBS d368",
        addon_rate=addon_rates.irrbb,
        addon_amount=addon_rates.irrbb * total_rwa,
        regulatory_reference="BCBS d368 Section 3",
    ))

    # Pension risk
    pension_rate = addon_rates.pension_risk
    if pension_risk is not None:
        pension_rate = pension_risk.pension_addon_rate
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.PENSION_RISK,
        description="Defined benefit pension obligation shortfall risk",
        addon_rate=pension_rate,
        addon_amount=pension_rate * total_rwa,
        regulatory_reference="SR 15-18 Section III.B",
    ))

    # Model risk
    model_rate = addon_rates.model_risk
    if model_risk is not None:
        model_rate = model_risk.model_risk_addon_rate
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.MODEL_RISK,
        description="Model estimation and implementation error risk",
        addon_rate=model_rate,
        addon_amount=model_rate * total_rwa,
        regulatory_reference="SR 11-7, SR 15-18 Section III.C",
    ))

    # Strategic risk
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.STRATEGIC_RISK,
        description="Adverse business decisions or poor strategy execution",
        addon_rate=addon_rates.strategic_risk,
        addon_amount=addon_rates.strategic_risk * total_rwa,
        regulatory_reference="SR 15-19",
    ))

    # Reputation risk
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.REPUTATION_RISK,
        description="Reputational damage leading to revenue decline",
        addon_rate=addon_rates.reputation_risk,
        addon_amount=addon_rates.reputation_risk * total_rwa,
        regulatory_reference="SR 15-19",
    ))

    # Country risk
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.COUNTRY_RISK,
        description="Cross-border transfer and sovereign risk",
        addon_rate=addon_rates.country_risk,
        addon_amount=addon_rates.country_risk * total_rwa,
        regulatory_reference="BCBS d309 Principle 1(e)",
    ))

    # Residual risk
    assessments.append(Pillar2ARiskAssessment(
        category=Pillar2RiskCategory.RESIDUAL_RISK,
        description="Residual risks not covered by other categories",
        addon_rate=addon_rates.residual_risk,
        addon_amount=addon_rates.residual_risk * total_rwa,
        regulatory_reference="BCBS d309 Principle 1(f)",
    ))

    return assessments


def build_capital_plan(
    starting_cet1: float,
    starting_rwa: float,
    quarterly_net_income: float,
    quarterly_dividends: float,
    quarterly_buybacks: float = 0.0,
    quarterly_rwa_growth: float = 0.0,
    quarterly_oci: float = 0.0,
    horizon_quarters: int = CAPITAL_PLANNING_HORIZON_YEARS * 4,
    plan_start_date: date = date(2026, 3, 31),
) -> CapitalPlan:
    """Build a multi-quarter capital plan projection.

    Projects CET1 capital and ratios forward based on assumed income,
    distributions, and RWA growth. Uses a constant balance sheet approach
    for the base case.

    Args:
        starting_cet1: Starting CET1 capital in $M.
        starting_rwa: Starting total RWA in $M.
        quarterly_net_income: Projected quarterly net income in $M.
        quarterly_dividends: Projected quarterly dividends in $M.
        quarterly_buybacks: Projected quarterly share buybacks in $M.
        quarterly_rwa_growth: Projected quarterly RWA growth in $M.
        quarterly_oci: Projected quarterly OCI in $M.
        horizon_quarters: Number of quarters to project.
        plan_start_date: Start date for the capital plan.

    Returns:
        CapitalPlan with quarterly projections and summary metrics.

    Reference: 12 CFR 252.153(e), SR 15-18 Section II.
    """
    projections: list[CapitalPlanProjection] = []
    current_cet1 = starting_cet1
    current_rwa = starting_rwa
    min_ratio = float('inf')
    min_quarter = ""
    total_distributions = 0.0

    for q in range(horizon_quarters):
        year_offset = q // 4
        quarter_in_year = (q % 4) + 1
        start_year = plan_start_date.year
        quarter_label = f"Q{quarter_in_year} {start_year + year_offset}"

        starting_q_cet1 = current_cet1
        starting_q_rwa = current_rwa

        # Capital generation
        ending_cet1 = (
            current_cet1
            + quarterly_net_income
            + quarterly_oci
            - quarterly_dividends
            - quarterly_buybacks
        )

        # RWA change
        ending_rwa = current_rwa + quarterly_rwa_growth

        # Ratio
        ratio = ending_cet1 / ending_rwa if ending_rwa > 0 else 0.0

        proj = CapitalPlanProjection(
            quarter=quarter_label,
            quarter_index=q + 1,
            starting_cet1=starting_q_cet1,
            starting_rwa=starting_q_rwa,
            net_income=quarterly_net_income,
            other_comprehensive_income=quarterly_oci,
            dividends=quarterly_dividends,
            share_buybacks=quarterly_buybacks,
            rwa_growth=quarterly_rwa_growth,
            ending_cet1=ending_cet1,
            ending_rwa=ending_rwa,
            ending_cet1_ratio=ratio,
        )
        projections.append(proj)

        total_distributions += quarterly_dividends + quarterly_buybacks

        if ratio < min_ratio:
            min_ratio = ratio
            min_quarter = quarter_label

        current_cet1 = ending_cet1
        current_rwa = ending_rwa

    final_ratio = projections[-1].ending_cet1_ratio if projections else 0.0

    return CapitalPlan(
        plan_start_date=plan_start_date,
        horizon_quarters=horizon_quarters,
        projections=projections,
        minimum_cet1_ratio=min_ratio,
        minimum_cet1_quarter=min_quarter,
        total_capital_distributions=total_distributions,
        ending_cet1_ratio=final_ratio,
    )


def compute_stress_scenario(
    pre_stress_cet1: float,
    pre_stress_rwa: float,
    credit_losses: float,
    market_losses: float,
    operational_losses: float,
    ppnr: float,
    rwa_inflation: float = 0.0,
    scenario_type: StressScenarioType = StressScenarioType.SEVERELY_ADVERSE,
    scenario_name: str = "Severely Adverse",
) -> StressScenarioResult:
    """Compute capital impact of a single stress scenario.

    Post-stress CET1 = Pre-stress CET1 - losses + PPNR
    Post-stress RWA = Pre-stress RWA + RWA inflation

    Args:
        pre_stress_cet1: Pre-stress CET1 capital in $M.
        pre_stress_rwa: Pre-stress RWA in $M.
        credit_losses: Projected credit losses in $M.
        market_losses: Projected market risk losses in $M.
        operational_losses: Projected operational losses in $M.
        ppnr: Pre-provision net revenue (cushion against losses) in $M.
        rwa_inflation: RWA increase under stress in $M.
        scenario_type: Type of stress scenario.
        scenario_name: Human-readable scenario name.

    Returns:
        StressScenarioResult with pre/post stress positions.

    Reference: 12 CFR 252.54-56, SR 12-7.
    """
    total_losses = credit_losses + market_losses + operational_losses
    cet1_depletion = total_losses - ppnr  # Net impact (positive = depletion)

    post_cet1 = pre_stress_cet1 - cet1_depletion
    post_rwa = pre_stress_rwa + rwa_inflation

    pre_ratio = pre_stress_cet1 / pre_stress_rwa if pre_stress_rwa > 0 else 0.0
    post_ratio = post_cet1 / post_rwa if post_rwa > 0 else 0.0

    return StressScenarioResult(
        scenario_type=scenario_type,
        scenario_name=scenario_name,
        pre_stress_cet1=pre_stress_cet1,
        pre_stress_rwa=pre_stress_rwa,
        pre_stress_cet1_ratio=pre_ratio,
        post_stress_cet1=post_cet1,
        post_stress_rwa=post_rwa,
        post_stress_cet1_ratio=post_ratio,
        cet1_depletion=cet1_depletion,
        cet1_ratio_change=post_ratio - pre_ratio,
        credit_losses=credit_losses,
        market_losses=market_losses,
        operational_losses=operational_losses,
        ppnr=ppnr,
        minimum_cet1_ratio=post_ratio,  # Simplified — single quarter
        breaches_minimum=post_ratio < 0.045,
    )


def compute_scb_from_stress(
    stress_results: list[StressScenarioResult],
    planned_dividends_4q: float,
    pre_stress_cet1_ratio: float,
    scb_floor: float = 0.025,
) -> float:
    """Compute the Stress Capital Buffer from stress test results.

    SCB = max(SCB_floor, pre-stress CET1 ratio - post-stress minimum CET1 ratio
              + planned common stock dividends as % of RWA for 4 quarters)

    The SCB is determined from the severely adverse scenario.

    Args:
        stress_results: List of stress scenario results.
        planned_dividends_4q: Planned dividends for next 4 quarters as % of RWA.
        pre_stress_cet1_ratio: Pre-stress CET1 ratio.
        scb_floor: Minimum SCB (2.5%).

    Returns:
        Stress Capital Buffer rate (decimal).

    Reference: 12 CFR 217.11(a)(2)(iv).
    """
    # Find severely adverse result
    sa_result = None
    for sr in stress_results:
        if sr.scenario_type == StressScenarioType.SEVERELY_ADVERSE:
            sa_result = sr
            break

    if sa_result is None:
        return scb_floor

    # SCB = ratio depletion + dividends
    ratio_depletion = pre_stress_cet1_ratio - sa_result.minimum_cet1_ratio
    scb = ratio_depletion + planned_dividends_4q

    return max(scb, scb_floor)


# =========================================================================
#  Master ICAAP Function
# =========================================================================

def compute_icaap(
    cet1_capital: float,
    tier1_capital: float,
    total_capital: float,
    total_rwa: float,
    leverage_ratio: float = 0.0,
    gsib_surcharge: float = 0.015,
    ccyb_rate: float = 0.0,
    scb_rate: Optional[float] = None,
    addon_rates: Pillar2AAddOnRates = DEFAULT_PILLAR_2A_RATES,
    management_buffer: float = MANAGEMENT_BUFFER_DEFAULT,
    planning_buffer: float = CAPITAL_PLANNING_BUFFER_DEFAULT,
    concentration_risk: Optional[ConcentrationRiskAssessment] = None,
    pension_risk: Optional[PensionRiskAssessment] = None,
    model_risk: Optional[ModelRiskAssessment] = None,
    stress_results: Optional[list[StressScenarioResult]] = None,
    capital_plan: Optional[CapitalPlan] = None,
    distributable_earnings: float = 0.0,
    assessment_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> ICAAPresult:
    """Compute the complete Internal Capital Adequacy Assessment.

    This is the master ICAAP function that combines:
    1. Current capital position (Pillar 1)
    2. Pillar 2A risk add-ons
    3. Buffer stack calculation
    4. MDA analysis
    5. Capital planning projections
    6. Stress testing overlay
    7. Overall adequacy determination

    Args:
        cet1_capital: Current CET1 capital in $M.
        tier1_capital: Current Tier 1 capital in $M.
        total_capital: Current Total capital in $M.
        total_rwa: Current total RWA in $M.
        leverage_ratio: Current SLR (decimal).
        gsib_surcharge: G-SIB surcharge rate (decimal).
        ccyb_rate: Countercyclical buffer rate (decimal).
        scb_rate: Stress Capital Buffer rate (None = use CCB).
        addon_rates: Pillar 2A add-on rates by category.
        management_buffer: Internal management buffer rate.
        planning_buffer: Capital planning buffer rate.
        concentration_risk: Optional concentration risk assessment.
        pension_risk: Optional pension risk assessment.
        model_risk: Optional model risk assessment.
        stress_results: Optional stress test results.
        capital_plan: Optional capital plan.
        distributable_earnings: Eligible distributable earnings in $M.
        assessment_date: Assessment date.
        entity_name: Entity name.

    Returns:
        ICAAPresult with comprehensive capital adequacy assessment.

    Reference: BCBS d309 Principles 1-4, SR 15-18.
    """
    if total_rwa <= 0:
        raise ValueError(
            f"Total RWA must be positive, got {total_rwa}. "
            "Reference: BCBS d309 Principle 1."
        )

    # Current ratios
    cet1_ratio = cet1_capital / total_rwa
    tier1_ratio = tier1_capital / total_rwa
    total_capital_ratio = total_capital / total_rwa

    # Pillar 2A risk assessments
    risk_assessments = assess_pillar2a_risks(
        total_rwa=total_rwa,
        addon_rates=addon_rates,
        concentration_risk=concentration_risk,
        pension_risk=pension_risk,
        model_risk=model_risk,
    )
    total_p2a_rate = sum(ra.addon_rate for ra in risk_assessments)
    total_p2a_amount = total_p2a_rate * total_rwa

    # Buffer stack
    buffer_stack = compute_buffer_stack(
        total_rwa=total_rwa,
        gsib_surcharge=gsib_surcharge,
        ccyb_rate=ccyb_rate,
        scb_rate=scb_rate,
        pillar_2a_addon=total_p2a_rate,
        management_buffer=management_buffer,
        planning_buffer=planning_buffer,
    )

    # MDA analysis
    mda = compute_mda_analysis(
        cet1_ratio=cet1_ratio,
        cet1_capital=cet1_capital,
        total_rwa=total_rwa,
        combined_buffer=buffer_stack.combined_buffer_rate,
        distributable_earnings=distributable_earnings,
    )

    # SCB from stress testing
    scb_implied = 0.025
    if stress_results:
        scb_implied = compute_scb_from_stress(
            stress_results=stress_results,
            planned_dividends_4q=0.0,  # Simplified
            pre_stress_cet1_ratio=cet1_ratio,
        )

    # Total internal capital requirement
    total_req_rate = buffer_stack.internal_cet1_target
    total_req_amount = total_req_rate * total_rwa

    # Surplus
    surplus_amount = cet1_capital - total_req_amount
    surplus_rate = cet1_ratio - total_req_rate

    # Adequacy flags
    meets_p1 = (
        cet1_ratio >= 0.045
        and tier1_ratio >= 0.06
        and total_capital_ratio >= 0.08
    )
    meets_buffers = cet1_ratio >= buffer_stack.effective_cet1_minimum
    meets_internal = surplus_amount >= 0
    passes_stress = all(
        not sr.breaches_minimum for sr in (stress_results or [])
    )
    overall = meets_p1 and meets_buffers and meets_internal and passes_stress

    return ICAAPresult(
        assessment_date=assessment_date,
        entity_name=entity_name,
        cet1_capital=cet1_capital,
        tier1_capital=tier1_capital,
        total_capital=total_capital,
        total_rwa=total_rwa,
        cet1_ratio=cet1_ratio,
        tier1_ratio=tier1_ratio,
        total_capital_ratio=total_capital_ratio,
        leverage_ratio=leverage_ratio,
        risk_assessments=risk_assessments,
        total_pillar_2a_addon_rate=total_p2a_rate,
        total_pillar_2a_addon_amount=total_p2a_amount,
        concentration_risk=concentration_risk,
        pension_risk=pension_risk,
        model_risk=model_risk,
        buffer_stack=buffer_stack,
        mda_analysis=mda,
        capital_plan=capital_plan,
        stress_results=stress_results or [],
        scb_implied=scb_implied,
        total_internal_capital_requirement=total_req_rate,
        total_internal_capital_amount=total_req_amount,
        capital_surplus_over_internal_target=surplus_amount,
        capital_surplus_rate=surplus_rate,
        meets_pillar1_minimums=meets_p1,
        meets_buffer_requirements=meets_buffers,
        meets_internal_targets=meets_internal,
        passes_stress_tests=passes_stress,
        overall_adequate=overall,
    )
