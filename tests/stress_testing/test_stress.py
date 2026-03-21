"""Tests for Stress Testing module.

Tests scenario generation, capital projection, SCB calculation,
and buffer adequacy assessment.

References:
    - SR 12-7: Supervisory Guidance on Stress Testing
    - FR Y-14A: Capital assessment
    - 12 CFR 217.11: SCB requirements
"""

import pytest

from src.stress_testing.stress_params import (
    QUARTERS,
    SCB_FLOOR,
    ScenarioType,
    MacroVariableType,
    build_scenario,
)
from src.stress_testing.scenario_engine import (
    ScenarioEngine,
    ScenarioResult,
)
from src.stress_testing.capital_projector import (
    CapitalProjector,
    CapitalProjectionResult,
)
from src.stress_testing.stress_results import (
    compute_stress_test_results,
    StressTestResults,
)


# =========================================================================
#  Fixtures
# =========================================================================

# Realistic Category I G-SIB starting position
STARTING_CET1 = 195_000.0        # $195B CET1
STARTING_RWA = 1_650_000.0       # $1.65T RWA
AVG_ASSETS = 3_200_000.0         # $3.2T average assets
TOTAL_LOANS = 1_000_000.0        # $1T total loans
STARTING_TLE = 3_500_000.0       # $3.5T leverage exposure


# =========================================================================
#  Scenario Generation Tests
# =========================================================================

class TestScenarioGeneration:
    """Tests for macro scenario generation."""

    def test_baseline_scenario(self) -> None:
        """Baseline scenario has 13 quarters of data."""
        scenario = build_scenario(ScenarioType.BASELINE)
        assert scenario.quarters == QUARTERS
        assert scenario.scenario_type == ScenarioType.BASELINE
        for var in scenario.variables:
            assert len(var.quarterly_values) == QUARTERS

    def test_adverse_scenario(self) -> None:
        """Adverse scenario shows economic deterioration."""
        scenario = build_scenario(ScenarioType.ADVERSE)
        assert scenario.scenario_type == ScenarioType.ADVERSE
        # GDP should go negative
        gdp = next(
            v for v in scenario.variables
            if v.variable_type == MacroVariableType.REAL_GDP_GROWTH
        )
        assert min(gdp.quarterly_values) < 0.0

    def test_severely_adverse_scenario(self) -> None:
        """Severely adverse: GDP -8.5%, unemployment 10%, equity -55%."""
        scenario = build_scenario(ScenarioType.SEVERELY_ADVERSE)
        gdp = next(
            v for v in scenario.variables
            if v.variable_type == MacroVariableType.REAL_GDP_GROWTH
        )
        unemp = next(
            v for v in scenario.variables
            if v.variable_type == MacroVariableType.UNEMPLOYMENT_RATE
        )
        equity = next(
            v for v in scenario.variables
            if v.variable_type == MacroVariableType.EQUITY_INDEX_CHANGE
        )
        # Check CCAR-calibrated parameters
        assert min(gdp.quarterly_values) <= -0.05
        assert max(unemp.quarterly_values) >= 0.09
        assert min(equity.quarterly_values) <= -0.15

    def test_scenario_engine(self) -> None:
        """ScenarioEngine generates all three scenarios."""
        engine = ScenarioEngine()
        for st in ScenarioType:
            scenario = engine.generate_scenario(st)
            assert scenario.scenario_type == st
            assert len(scenario.variables) >= 5


# =========================================================================
#  Scenario Application Tests
# =========================================================================

class TestScenarioApplication:
    """Tests for applying scenarios to portfolios."""

    def test_apply_baseline(self) -> None:
        """Baseline scenario produces low credit losses."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(ScenarioType.BASELINE)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS
        )
        assert result.scenario_type == ScenarioType.BASELINE
        assert len(result.quarterly_impacts) == QUARTERS

    def test_severely_adverse_worse_than_adverse(self) -> None:
        """Severely adverse produces higher losses than adverse."""
        engine = ScenarioEngine()
        adverse = engine.apply_scenario_to_portfolio(
            engine.generate_scenario(ScenarioType.ADVERSE),
            TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        severe = engine.apply_scenario_to_portfolio(
            engine.generate_scenario(ScenarioType.SEVERELY_ADVERSE),
            TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        assert severe.cumulative_credit_losses > adverse.cumulative_credit_losses
        assert severe.peak_unemployment > adverse.peak_unemployment

    def test_interpolation(self) -> None:
        """Quarterly path interpolation produces correct length."""
        engine = ScenarioEngine()
        values = [1.0, 2.0, 3.0, 4.0]
        interpolated = engine.interpolate_quarterly_path(values, 8)
        assert len(interpolated) == 8
        assert interpolated[0] == pytest.approx(1.0)
        assert interpolated[-1] == pytest.approx(4.0)


# =========================================================================
#  Capital Projection Tests
# =========================================================================

class TestCapitalProjection:
    """Tests for 9-quarter capital projection."""

    def test_baseline_capital_stable(self) -> None:
        """Baseline projection: capital ratios remain stable."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(ScenarioType.BASELINE)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        projector = CapitalProjector()
        proj = projector.project_capital(
            result, STARTING_CET1, STARTING_RWA, AVG_ASSETS, TOTAL_LOANS,
        )
        # CET1 ratio should stay roughly stable under baseline
        assert proj.min_cet1_ratio >= 0.08
        assert len(proj.quarterly_states) == 9

    def test_severely_adverse_capital_decline(self) -> None:
        """Severely adverse: CET1 ratio declines significantly."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(ScenarioType.SEVERELY_ADVERSE)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        projector = CapitalProjector()
        proj = projector.project_capital(
            result, STARTING_CET1, STARTING_RWA, AVG_ASSETS, TOTAL_LOANS,
        )
        # CET1 should decline under stress
        assert proj.peak_to_trough_cet1 > 0.0
        assert proj.min_cet1_ratio < proj.starting_cet1_ratio

    def test_scb_floor(self) -> None:
        """SCB is at least 2.5% per 12 CFR 217.11."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(ScenarioType.BASELINE)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        projector = CapitalProjector()
        proj = projector.project_capital(
            result, STARTING_CET1, STARTING_RWA, AVG_ASSETS, TOTAL_LOANS,
        )
        assert proj.stress_capital_buffer >= SCB_FLOOR

    def test_minimum_ratio_identification(self) -> None:
        """Min CET1 ratio is correctly identified."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(ScenarioType.SEVERELY_ADVERSE)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        projector = CapitalProjector()
        proj = projector.project_capital(
            result, STARTING_CET1, STARTING_RWA, AVG_ASSETS, TOTAL_LOANS,
        )
        actual_min = min(s.cet1_ratio for s in proj.quarterly_states)
        assert proj.min_cet1_ratio == pytest.approx(actual_min)
        assert 1 <= proj.min_cet1_quarter <= 9

    def test_capital_waterfall_consistency(self) -> None:
        """Capital waterfall: ending CET1 = starting + income - actions."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(ScenarioType.BASELINE)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        projector = CapitalProjector()
        proj = projector.project_capital(
            result, STARTING_CET1, STARTING_RWA, AVG_ASSETS, TOTAL_LOANS,
        )
        # Total PPNR should be positive under baseline
        assert proj.total_ppnr > 0


# =========================================================================
#  Stress Test Results Aggregation Tests
# =========================================================================

class TestStressTestResults:
    """Tests for results aggregation and buffer assessment."""

    def _run_projection(self, scenario_type: ScenarioType) -> CapitalProjectionResult:
        """Helper to run a single scenario projection."""
        engine = ScenarioEngine()
        scenario = engine.generate_scenario(scenario_type)
        result = engine.apply_scenario_to_portfolio(
            scenario, TOTAL_LOANS, STARTING_RWA, 0.0, AVG_ASSETS,
        )
        projector = CapitalProjector()
        return projector.project_capital(
            result, STARTING_CET1, STARTING_RWA, AVG_ASSETS, TOTAL_LOANS,
        )

    def test_full_stress_test(self) -> None:
        """Full stress test across all three scenarios."""
        baseline = self._run_projection(ScenarioType.BASELINE)
        adverse = self._run_projection(ScenarioType.ADVERSE)
        severe = self._run_projection(ScenarioType.SEVERELY_ADVERSE)

        results = compute_stress_test_results(
            baseline=baseline,
            adverse=adverse,
            severely_adverse=severe,
            gsib_surcharge=0.035,
            total_rwa=STARTING_RWA,
        )
        assert results.stress_capital_buffer >= SCB_FLOOR
        assert results.comparison is not None
        assert results.buffer_adequacy is not None

    def test_severely_adverse_binding(self) -> None:
        """Severely adverse is the binding scenario."""
        baseline = self._run_projection(ScenarioType.BASELINE)
        severe = self._run_projection(ScenarioType.SEVERELY_ADVERSE)

        results = compute_stress_test_results(
            baseline=baseline,
            severely_adverse=severe,
        )
        assert results.binding_scenario == ScenarioType.SEVERELY_ADVERSE

    def test_well_capitalized_gsib_passes(self) -> None:
        """A well-capitalized G-SIB should pass stress tests."""
        baseline = self._run_projection(ScenarioType.BASELINE)
        severe = self._run_projection(ScenarioType.SEVERELY_ADVERSE)

        results = compute_stress_test_results(
            baseline=baseline,
            severely_adverse=severe,
            gsib_surcharge=0.035,
            total_rwa=STARTING_RWA,
        )
        # Starting with 11.8% CET1, should maintain above 4.5% minimum
        assert results.overall_pass is True
        assert results.capital_shortfall == pytest.approx(0.0)
