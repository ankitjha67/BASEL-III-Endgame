"""Stress Test Results — Aggregation, analysis, and buffer assessment.

Combines scenario results and capital projections into a comprehensive
stress test assessment with buffer adequacy evaluation.

All amounts in USD millions ($M). Ratios as decimals.

References:
    - SR 12-7 §V: Stress test results and reporting
    - 12 CFR 252.17: Stress test results disclosure
    - FR Y-14A/Q: Capital assessment and stress testing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.stress_testing.stress_params import (
    SCB_FLOOR,
    ScenarioType,
)
from src.stress_testing.capital_projector import CapitalProjectionResult


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class BufferAdequacy:
    """Capital buffer adequacy assessment under stress.

    Reference: 12 CFR 217.11, SR 12-7 §V.
    """
    # Minimum requirements
    cet1_minimum: float = 0.045
    tier1_minimum: float = 0.06
    total_capital_minimum: float = 0.08
    slr_minimum: float = 0.03

    # Buffer requirements
    ccb: float = 0.025
    ccyb: float = 0.0
    gsib_surcharge: float = 0.0
    scb: float = 0.025

    # Effective minimums (minimum + buffer)
    effective_cet1_minimum: float = 0.0
    effective_tier1_minimum: float = 0.0

    # Surplus/deficit under stress
    cet1_surplus_stress: float = 0.0
    tier1_surplus_stress: float = 0.0
    total_surplus_stress: float = 0.0
    slr_surplus_stress: float = 0.0

    # Assessment
    meets_minimums_under_stress: bool = True
    meets_buffers_under_stress: bool = True
    binding_constraint: str = ""


@dataclass
class ScenarioComparison:
    """Comparison of results across scenarios.

    Reference: SR 12-7 §V.
    """
    baseline_min_cet1: float = 0.0
    adverse_min_cet1: float = 0.0
    severe_min_cet1: float = 0.0
    baseline_total_losses: float = 0.0
    adverse_total_losses: float = 0.0
    severe_total_losses: float = 0.0
    severe_peak_to_trough: float = 0.0
    scb: float = 0.025


@dataclass
class StressTestResults:
    """Complete stress test results package.

    Contains projections for all scenarios, buffer assessment,
    and cross-scenario comparison.

    Reference: SR 12-7, 12 CFR 252.17.
    """
    # Individual scenario results
    baseline_result: Optional[CapitalProjectionResult] = None
    adverse_result: Optional[CapitalProjectionResult] = None
    severely_adverse_result: Optional[CapitalProjectionResult] = None

    # Buffer assessment (based on severely adverse)
    buffer_adequacy: Optional[BufferAdequacy] = None

    # Cross-scenario comparison
    comparison: Optional[ScenarioComparison] = None

    # Summary
    stress_capital_buffer: float = 0.025
    binding_scenario: ScenarioType = ScenarioType.SEVERELY_ADVERSE
    overall_pass: bool = True
    capital_shortfall: float = 0.0  # $M, 0 if no shortfall


# =========================================================================
#  Results Aggregation
# =========================================================================

def compute_stress_test_results(
    baseline: Optional[CapitalProjectionResult] = None,
    adverse: Optional[CapitalProjectionResult] = None,
    severely_adverse: Optional[CapitalProjectionResult] = None,
    gsib_surcharge: float = 0.0,
    ccyb: float = 0.0,
    total_rwa: float = 0.0,
) -> StressTestResults:
    """Aggregate stress test results across all scenarios.

    Computes buffer adequacy, cross-scenario comparison, SCB,
    and overall pass/fail determination.

    Args:
        baseline: Baseline scenario capital projection.
        adverse: Adverse scenario capital projection.
        severely_adverse: Severely adverse scenario capital projection.
        gsib_surcharge: G-SIB surcharge rate.
        ccyb: Countercyclical capital buffer rate.
        total_rwa: Starting total RWA ($M).

    Returns:
        StressTestResults with full assessment.

    Reference: SR 12-7, 12 CFR 252.17.
    """
    # SCB from severely adverse
    scb = SCB_FLOOR
    if severely_adverse is not None:
        scb = severely_adverse.stress_capital_buffer

    # Buffer adequacy
    buffer = BufferAdequacy(
        ccb=max(scb, SCB_FLOOR),
        ccyb=ccyb,
        gsib_surcharge=gsib_surcharge,
        scb=scb,
    )
    buffer.effective_cet1_minimum = (
        buffer.cet1_minimum + buffer.ccb + buffer.ccyb + buffer.gsib_surcharge
    )
    buffer.effective_tier1_minimum = (
        buffer.tier1_minimum + buffer.ccb + buffer.ccyb + buffer.gsib_surcharge
    )

    # Check minimums under stress
    if severely_adverse is not None:
        buffer.cet1_surplus_stress = (
            severely_adverse.min_cet1_ratio - buffer.cet1_minimum
        )
        buffer.tier1_surplus_stress = (
            severely_adverse.min_tier1_ratio - buffer.tier1_minimum
        )
        buffer.total_surplus_stress = (
            severely_adverse.min_total_ratio - buffer.total_capital_minimum
        )
        buffer.slr_surplus_stress = (
            severely_adverse.min_slr - buffer.slr_minimum
        )
        buffer.meets_minimums_under_stress = all([
            buffer.cet1_surplus_stress >= 0,
            buffer.tier1_surplus_stress >= 0,
            buffer.total_surplus_stress >= 0,
            buffer.slr_surplus_stress >= 0,
        ])
        buffer.meets_buffers_under_stress = (
            severely_adverse.min_cet1_ratio >= buffer.effective_cet1_minimum
        )

        # Identify binding constraint
        surpluses = {
            "CET1": buffer.cet1_surplus_stress,
            "Tier1": buffer.tier1_surplus_stress,
            "Total": buffer.total_surplus_stress,
            "SLR": buffer.slr_surplus_stress,
        }
        buffer.binding_constraint = min(surpluses, key=surpluses.get)

    # Scenario comparison
    comparison = ScenarioComparison(
        baseline_min_cet1=baseline.min_cet1_ratio if baseline else 0.0,
        adverse_min_cet1=adverse.min_cet1_ratio if adverse else 0.0,
        severe_min_cet1=severely_adverse.min_cet1_ratio if severely_adverse else 0.0,
        baseline_total_losses=baseline.total_provisions if baseline else 0.0,
        adverse_total_losses=adverse.total_provisions if adverse else 0.0,
        severe_total_losses=(
            severely_adverse.total_provisions + severely_adverse.total_losses
            if severely_adverse else 0.0
        ),
        severe_peak_to_trough=(
            severely_adverse.peak_to_trough_cet1 if severely_adverse else 0.0
        ),
        scb=scb,
    )

    # Overall pass/fail
    overall_pass = buffer.meets_minimums_under_stress

    # Capital shortfall
    shortfall = 0.0
    if not overall_pass and total_rwa > 0 and severely_adverse is not None:
        shortfall = max(0.0, (
            buffer.cet1_minimum - severely_adverse.min_cet1_ratio
        ) * total_rwa)

    return StressTestResults(
        baseline_result=baseline,
        adverse_result=adverse,
        severely_adverse_result=severely_adverse,
        buffer_adequacy=buffer,
        comparison=comparison,
        stress_capital_buffer=scb,
        binding_scenario=ScenarioType.SEVERELY_ADVERSE,
        overall_pass=overall_pass,
        capital_shortfall=shortfall,
    )
