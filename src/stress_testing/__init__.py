"""Stress Testing Module — CCAR/DFAST capital stress testing.

Implements the Fed's Comprehensive Capital Analysis and Review (CCAR)
and Dodd-Frank Act Stress Testing (DFAST) framework for Category I G-SIBs.

References:
    - SR 12-7: Supervisory Guidance on Stress Testing
    - Dodd-Frank Act §165(i): Stress testing requirements
    - FR Y-14A/Q: Capital assessment and stress testing
"""

from src.stress_testing.stress_params import (
    ScenarioType,
    MacroVariableType,
    MacroVariable,
    ScenarioDefinition,
    build_scenario,
    QUARTERS,
    SCB_FLOOR,
)
from src.stress_testing.scenario_engine import (
    ScenarioEngine,
    ScenarioResult,
    PortfolioImpact,
)
from src.stress_testing.capital_projector import (
    CapitalProjector,
    CapitalProjectionResult,
    QuarterlyCapitalState,
)
from src.stress_testing.stress_results import (
    StressTestResults,
    BufferAdequacy,
    ScenarioComparison,
    compute_stress_test_results,
)

__all__ = [
    "ScenarioType",
    "MacroVariableType",
    "MacroVariable",
    "ScenarioDefinition",
    "build_scenario",
    "QUARTERS",
    "SCB_FLOOR",
    "ScenarioEngine",
    "ScenarioResult",
    "PortfolioImpact",
    "CapitalProjector",
    "CapitalProjectionResult",
    "QuarterlyCapitalState",
    "StressTestResults",
    "BufferAdequacy",
    "ScenarioComparison",
    "compute_stress_test_results",
]
