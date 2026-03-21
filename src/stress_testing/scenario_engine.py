"""Scenario Engine — Macroeconomic scenario generation and application.

Generates baseline, adverse, and severely adverse scenarios and translates
macro variables to portfolio-level credit, market, and revenue impacts.

References:
    - SR 12-7 §III: Scenario design and application
    - FR Y-14A Schedule A: Macro scenario projections
    - Dodd-Frank Act §165(i): Stress testing requirements
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.stress_testing.stress_params import (
    PROVISION_RATE_ADVERSE,
    PROVISION_RATE_BASELINE,
    PROVISION_RATE_SEVERE,
    RWA_MIGRATION_ADVERSE,
    RWA_MIGRATION_SEVERE,
    ScenarioDefinition,
    ScenarioType,
    MacroVariable,
    MacroVariableType,
    QUARTERS,
    build_scenario,
)


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class PortfolioImpact:
    """Quarterly portfolio-level impact from a stress scenario.

    Reference: FR Y-14A Schedule A.
    """
    quarter: int
    credit_loss_rate: float = 0.0
    rwa_migration_pct: float = 0.0
    market_risk_pl: float = 0.0
    nii_impact_pct: float = 0.0
    trading_pl: float = 0.0


@dataclass
class ScenarioResult:
    """Complete scenario application result.

    Reference: SR 12-7 §III.
    """
    scenario_type: ScenarioType
    scenario_name: str
    quarterly_impacts: list[PortfolioImpact] = field(default_factory=list)
    cumulative_credit_losses: float = 0.0
    peak_unemployment: float = 0.0
    trough_hpi_change: float = 0.0
    peak_to_trough_equity: float = 0.0
    total_rwa_increase_pct: float = 0.0


# =========================================================================
#  Scenario Engine
# =========================================================================

class ScenarioEngine:
    """Macroeconomic scenario generation and portfolio impact engine.

    Generates CCAR-compliant scenarios and translates macro variables
    to credit losses, RWA migration, NII impact, and market risk P&L.

    Reference: SR 12-7, FR Y-14A, Dodd-Frank §165(i).
    """

    def __init__(self, quarters: int = QUARTERS) -> None:
        """Initialize scenario engine.

        Args:
            quarters: Projection horizon (13 per CCAR).

        Reference: SR 12-7 §III.
        """
        self.quarters = quarters

    def generate_scenario(
        self, scenario_type: ScenarioType
    ) -> ScenarioDefinition:
        """Generate a complete macro scenario.

        Args:
            scenario_type: BASELINE, ADVERSE, or SEVERELY_ADVERSE.

        Returns:
            ScenarioDefinition with all macro variables.

        Reference: Federal Reserve CCAR scenario publications.
        """
        return build_scenario(scenario_type)

    def apply_scenario_to_portfolio(
        self,
        scenario: ScenarioDefinition,
        total_loans: float,
        total_rwa: float,
        trading_book_size: float = 0.0,
        avg_assets: float = 0.0,
    ) -> ScenarioResult:
        """Translate macro scenario to portfolio-level impacts.

        Produces quarterly credit loss rates, RWA migration, NII impact,
        and market risk P&L based on the macro variable paths.

        Args:
            scenario: Macro scenario definition.
            total_loans: Total loan portfolio ($M).
            total_rwa: Starting total RWA ($M).
            trading_book_size: Trading book notional ($M).
            avg_assets: Average total assets ($M).

        Returns:
            ScenarioResult with quarterly impacts.

        Reference: SR 12-7 §III.2, FR Y-14A.
        """
        # Extract key macro paths
        unemployment = self._get_variable_path(
            scenario, MacroVariableType.UNEMPLOYMENT_RATE
        )
        hpi = self._get_variable_path(
            scenario, MacroVariableType.HPI_CHANGE
        )
        equity = self._get_variable_path(
            scenario, MacroVariableType.EQUITY_INDEX_CHANGE
        )
        rates_10y = self._get_variable_path(
            scenario, MacroVariableType.TREASURY_10Y
        )
        bbb_spread = self._get_variable_path(
            scenario, MacroVariableType.BBB_SPREAD
        )

        # Determine provision rate based on scenario type
        if scenario.scenario_type == ScenarioType.SEVERELY_ADVERSE:
            base_provision_rate = PROVISION_RATE_SEVERE
            rwa_migration = RWA_MIGRATION_SEVERE
        elif scenario.scenario_type == ScenarioType.ADVERSE:
            base_provision_rate = PROVISION_RATE_ADVERSE
            rwa_migration = RWA_MIGRATION_ADVERSE
        else:
            base_provision_rate = PROVISION_RATE_BASELINE
            rwa_migration = 0.0

        quarterly_impacts: list[PortfolioImpact] = []
        cumulative_losses = 0.0

        for q in range(self.quarters):
            # Credit loss rate driven by unemployment and HPI
            # Unemployment sensitivity: marginal increase above baseline (4%)
            # drives incremental losses, but capped to avoid runaway compounding.
            # Reference: SR 12-7 §III.2 — loss rate sensitivity to macro drivers.
            unemp_baseline = 0.04
            unemp_delta = max(0.0, (unemployment[q] if unemployment else unemp_baseline) - unemp_baseline)
            unemp_factor = 1.0 + 2.0 * unemp_delta  # e.g., 10% unemp -> 1.12x (not 2.5x)

            # HPI: negative changes increase losses modestly
            hpi_val = hpi[q] if hpi else 0.0
            hpi_factor = 1.0 - 1.0 * min(hpi_val, 0.0)  # only negative HPI increases losses

            credit_loss_rate = base_provision_rate * unemp_factor * hpi_factor / 4.0  # quarterly

            # RWA migration (gradual increase, peaks mid-horizon)
            rwa_pct = rwa_migration * self._bell_curve(q, self.quarters) / 4.0

            # NII impact from rate compression
            # Reference: SR 12-7 §III.2 — NII sensitivity to rate changes.
            # Pass-through is limited (hedged balance sheets, repricing lags).
            nii_pct = 0.0
            if rates_10y:
                rate_change = rates_10y[q] - (rates_10y[0] if rates_10y else 0.04)
                nii_pct = rate_change * 0.15  # 15% pass-through (hedged)

            # Trading P&L from equity and spread moves
            trading_pl = 0.0
            if trading_book_size > 0:
                equity_impact = (equity[q] if equity else 0.0) * trading_book_size * 0.10
                spread_impact = -(bbb_spread[q] - 0.012 if bbb_spread else 0.0) * trading_book_size * 0.05
                trading_pl = equity_impact + spread_impact

            impact = PortfolioImpact(
                quarter=q + 1,
                credit_loss_rate=credit_loss_rate,
                rwa_migration_pct=rwa_pct,
                market_risk_pl=trading_pl,
                nii_impact_pct=nii_pct,
                trading_pl=trading_pl,
            )
            quarterly_impacts.append(impact)
            cumulative_losses += credit_loss_rate * total_loans

        # Summary statistics
        peak_unemp = max(unemployment) if unemployment else 0.0
        trough_hpi = min(hpi) if hpi else 0.0

        cum_equity = 1.0
        min_equity = 1.0
        for eq in (equity or []):
            cum_equity *= (1.0 + eq)
            min_equity = min(min_equity, cum_equity)
        peak_to_trough = 1.0 - min_equity

        return ScenarioResult(
            scenario_type=scenario.scenario_type,
            scenario_name=scenario.name,
            quarterly_impacts=quarterly_impacts,
            cumulative_credit_losses=cumulative_losses,
            peak_unemployment=peak_unemp,
            trough_hpi_change=trough_hpi,
            peak_to_trough_equity=peak_to_trough,
            total_rwa_increase_pct=rwa_migration,
        )

    def _get_variable_path(
        self,
        scenario: ScenarioDefinition,
        var_type: MacroVariableType,
    ) -> list[float]:
        """Extract a variable's quarterly path from scenario.

        Args:
            scenario: Scenario definition.
            var_type: Variable type to extract.

        Returns:
            List of quarterly values.
        """
        for var in scenario.variables:
            if var.variable_type == var_type:
                return list(var.quarterly_values)
        return [0.0] * self.quarters

    @staticmethod
    def _bell_curve(quarter: int, total_quarters: int) -> float:
        """Generate a bell-curve weighting peaking mid-horizon.

        Used for RWA migration timing — rating downgrades peak
        in the middle of the stress period.

        Args:
            quarter: Current quarter (0-indexed).
            total_quarters: Total quarters.

        Returns:
            Weight between 0 and 1.
        """
        import math
        mid = total_quarters / 2.0
        sigma = total_quarters / 4.0
        return math.exp(-0.5 * ((quarter - mid) / sigma) ** 2)

    def interpolate_quarterly_path(
        self,
        values: list[float],
        target_quarters: int,
    ) -> list[float]:
        """Interpolate a variable path to a different number of quarters.

        Uses linear interpolation between available data points.

        Args:
            values: Source quarterly values.
            target_quarters: Target number of quarters.

        Returns:
            Interpolated quarterly path.

        Reference: SR 12-7 §III — scenario interpolation.
        """
        if not values:
            return [0.0] * target_quarters

        if len(values) == target_quarters:
            return values.copy()

        result: list[float] = []
        for t in range(target_quarters):
            source_idx = t * (len(values) - 1) / max(target_quarters - 1, 1)
            lower = int(source_idx)
            upper = min(lower + 1, len(values) - 1)
            frac = source_idx - lower
            result.append(values[lower] * (1 - frac) + values[upper] * frac)

        return result
