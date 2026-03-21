"""Pillar 2 — ICAAP and Supervisory Review Process.

Implements the Internal Capital Adequacy Assessment Process (ICAAP),
capital buffer stack calculation, MDA triggers, and IRRBB analysis
per BCBS d309, BCBS d368, and US supervisory guidance.

References:
- BCBS d309: Pillar 2 (Supervisory Review Process)
- BCBS d368: Interest Rate Risk in the Banking Book
- SR 15-18: Federal Reserve Supervisory Assessment of Capital Planning
- 12 CFR 217.11: Capital buffer requirements
- 12 CFR 252.153-155: Enhanced prudential standards — capital planning
"""

from src.pillar2.pillar2_params import (
    BufferType,
    CCB_RATE,
    CCYB_DEFAULT,
    CET1_MINIMUM,
    DEFAULT_PILLAR_2A_RATES,
    DEFAULT_PILLAR_TWO_THRESHOLDS,
    ESLR_TOTAL,
    GSIB_SURCHARGE_DEFAULT,
    MDA_QUARTILE_PAYOUTS,
    MDARestrictionQuartile,
    MANAGEMENT_BUFFER_DEFAULT,
    Pillar2AAddOnRates,
    Pillar2RiskCategory,
    PillarTwoThresholds,
    SCB_FLOOR,
    SLR_MINIMUM,
    StressScenarioType,
)

from src.pillar2.buffer_calculator import (
    BufferComponent,
    BufferStackResult,
    DistributionConstraint,
    MDAAnalysis,
    compute_buffer_distance,
    compute_buffer_stack,
    compute_mda_analysis,
    determine_mda_quartile,
    evaluate_distribution,
)

from src.pillar2.icaap_engine import (
    CapitalPlan,
    CapitalPlanProjection,
    ConcentrationRiskAssessment,
    ICAAPresult,
    ModelRiskAssessment,
    PensionRiskAssessment,
    Pillar2ARiskAssessment,
    StressScenarioResult,
    assess_pillar2a_risks,
    build_capital_plan,
    compute_icaap,
    compute_scb_from_stress,
    compute_stress_scenario,
)

__all__ = [
    # Parameters
    "BufferType",
    "CCB_RATE",
    "CCYB_DEFAULT",
    "CET1_MINIMUM",
    "DEFAULT_PILLAR_2A_RATES",
    "DEFAULT_PILLAR_TWO_THRESHOLDS",
    "ESLR_TOTAL",
    "GSIB_SURCHARGE_DEFAULT",
    "MDA_QUARTILE_PAYOUTS",
    "MDARestrictionQuartile",
    "MANAGEMENT_BUFFER_DEFAULT",
    "Pillar2AAddOnRates",
    "Pillar2RiskCategory",
    "PillarTwoThresholds",
    "SCB_FLOOR",
    "SLR_MINIMUM",
    "StressScenarioType",
    # Buffer calculator
    "BufferComponent",
    "BufferStackResult",
    "DistributionConstraint",
    "MDAAnalysis",
    "compute_buffer_distance",
    "compute_buffer_stack",
    "compute_mda_analysis",
    "determine_mda_quartile",
    "evaluate_distribution",
    # ICAAP
    "CapitalPlan",
    "CapitalPlanProjection",
    "ConcentrationRiskAssessment",
    "ICAAPresult",
    "ModelRiskAssessment",
    "PensionRiskAssessment",
    "Pillar2ARiskAssessment",
    "StressScenarioResult",
    "assess_pillar2a_risks",
    "build_capital_plan",
    "compute_icaap",
    "compute_scb_from_stress",
    "compute_stress_scenario",
]
