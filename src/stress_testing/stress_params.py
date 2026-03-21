"""Stress Testing Parameters — CCAR scenario definitions and macro variables.

Defines Fed CCAR/DFAST scenario parameters including severely adverse,
adverse, and baseline macro projections over a 13-quarter horizon.

All monetary amounts in USD millions ($M) unless stated otherwise.
Growth rates and ratios as decimals.

References:
    - SR 12-7: Supervisory Guidance on Stress Testing for Banking Organizations
    - Dodd-Frank Act §165(i): Stress testing requirements
    - FR Y-14A/Q: Capital assessment and stress testing templates
    - Federal Reserve CCAR 2026 Scenarios (published Q1 2026)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final


# =========================================================================
#  Scenario Types
# =========================================================================

class ScenarioType(Enum):
    """CCAR/DFAST stress test scenario types.

    Reference: 12 CFR 252.14(b), SR 12-7 §III.
    """
    BASELINE = "BASELINE"
    ADVERSE = "ADVERSE"
    SEVERELY_ADVERSE = "SEVERELY_ADVERSE"


# =========================================================================
#  Macro Variable Definitions
# =========================================================================

class MacroVariableType(Enum):
    """Types of macroeconomic variables used in stress scenarios.

    Reference: FR Y-14A Schedule A, CCAR scenario design.
    """
    REAL_GDP_GROWTH = "REAL_GDP_GROWTH"
    UNEMPLOYMENT_RATE = "UNEMPLOYMENT_RATE"
    CPI_INFLATION = "CPI_INFLATION"
    HPI_CHANGE = "HPI_CHANGE"           # House Price Index
    CRE_PRICE_CHANGE = "CRE_PRICE_CHANGE"  # Commercial RE
    EQUITY_INDEX_CHANGE = "EQUITY_INDEX_CHANGE"  # S&P 500
    BBB_SPREAD = "BBB_SPREAD"            # BBB corporate spread (bps)
    TREASURY_10Y = "TREASURY_10Y"        # 10-year Treasury rate
    TREASURY_3M = "TREASURY_3M"          # 3-month Treasury rate
    VIX = "VIX"                          # Volatility index


@dataclass(frozen=True)
class MacroVariable:
    """A single macroeconomic variable with quarterly projections.

    Reference: FR Y-14A Schedule A.
    """
    variable_type: MacroVariableType
    name: str
    quarterly_values: tuple[float, ...]
    unit: str = "decimal"
    description: str = ""


# =========================================================================
#  CCAR Scenario Definitions — 13 quarters (Q1 2026 through Q1 2029)
#  Reference: Federal Reserve CCAR 2026 Scenarios
# =========================================================================

QUARTERS: Final[int] = 13  # 13-quarter projection horizon per CCAR

# --- Baseline Scenario ---
# Consensus forecast: moderate growth, stable employment
BASELINE_GDP: Final[tuple[float, ...]] = (
    0.020, 0.021, 0.022, 0.022, 0.023,  # Q1-Q5
    0.023, 0.022, 0.022, 0.021, 0.021,  # Q6-Q10
    0.020, 0.020, 0.020,                 # Q11-Q13
)
BASELINE_UNEMPLOYMENT: Final[tuple[float, ...]] = (
    0.042, 0.041, 0.040, 0.040, 0.039,
    0.039, 0.039, 0.039, 0.039, 0.040,
    0.040, 0.040, 0.040,
)
BASELINE_HPI: Final[tuple[float, ...]] = (
    0.030, 0.028, 0.025, 0.023, 0.020,
    0.020, 0.020, 0.020, 0.020, 0.020,
    0.020, 0.020, 0.020,
)
BASELINE_EQUITY: Final[tuple[float, ...]] = (
    0.020, 0.025, 0.020, 0.020, 0.020,
    0.015, 0.015, 0.015, 0.015, 0.015,
    0.015, 0.015, 0.015,
)
BASELINE_10Y: Final[tuple[float, ...]] = (
    0.042, 0.042, 0.041, 0.040, 0.040,
    0.039, 0.039, 0.038, 0.038, 0.038,
    0.038, 0.038, 0.038,
)
BASELINE_BBB_SPREAD: Final[tuple[float, ...]] = (
    0.0120, 0.0115, 0.0110, 0.0110, 0.0110,
    0.0110, 0.0110, 0.0110, 0.0110, 0.0110,
    0.0110, 0.0110, 0.0110,
)

# --- Adverse Scenario ---
# Moderate recession: GDP -3%, unemployment to 7%, HPI -10%
ADVERSE_GDP: Final[tuple[float, ...]] = (
    -0.010, -0.025, -0.030, -0.020, -0.010,
    0.005, 0.010, 0.015, 0.018, 0.020,
    0.020, 0.020, 0.020,
)
ADVERSE_UNEMPLOYMENT: Final[tuple[float, ...]] = (
    0.045, 0.050, 0.055, 0.060, 0.065,
    0.070, 0.068, 0.065, 0.062, 0.060,
    0.058, 0.056, 0.054,
)
ADVERSE_HPI: Final[tuple[float, ...]] = (
    -0.020, -0.030, -0.030, -0.020, -0.010,
    -0.005, 0.000, 0.005, 0.010, 0.015,
    0.015, 0.015, 0.015,
)
ADVERSE_EQUITY: Final[tuple[float, ...]] = (
    -0.100, -0.150, -0.050, 0.000, 0.020,
    0.030, 0.040, 0.030, 0.020, 0.020,
    0.020, 0.020, 0.020,
)
ADVERSE_10Y: Final[tuple[float, ...]] = (
    0.035, 0.030, 0.025, 0.020, 0.018,
    0.018, 0.020, 0.022, 0.025, 0.028,
    0.030, 0.032, 0.035,
)
ADVERSE_BBB_SPREAD: Final[tuple[float, ...]] = (
    0.0200, 0.0280, 0.0320, 0.0300, 0.0260,
    0.0220, 0.0200, 0.0180, 0.0160, 0.0150,
    0.0140, 0.0130, 0.0120,
)

# --- Severely Adverse Scenario ---
# Deep recession: GDP -8.5%, unemployment to 10%, HPI -25%, equity -55%
SEVERE_GDP: Final[tuple[float, ...]] = (
    -0.030, -0.060, -0.085, -0.060, -0.030,
    -0.010, 0.010, 0.020, 0.025, 0.030,
    0.025, 0.020, 0.020,
)
SEVERE_UNEMPLOYMENT: Final[tuple[float, ...]] = (
    0.050, 0.060, 0.070, 0.080, 0.090,
    0.100, 0.098, 0.095, 0.090, 0.085,
    0.080, 0.075, 0.070,
)
SEVERE_HPI: Final[tuple[float, ...]] = (
    -0.050, -0.080, -0.080, -0.060, -0.040,
    -0.020, -0.010, 0.000, 0.010, 0.015,
    0.020, 0.020, 0.020,
)
SEVERE_EQUITY: Final[tuple[float, ...]] = (
    -0.200, -0.300, -0.150, -0.050, 0.000,
    0.050, 0.080, 0.060, 0.040, 0.030,
    0.025, 0.020, 0.020,
)
SEVERE_10Y: Final[tuple[float, ...]] = (
    0.025, 0.015, 0.010, 0.005, 0.005,
    0.008, 0.010, 0.015, 0.020, 0.025,
    0.030, 0.032, 0.035,
)
SEVERE_BBB_SPREAD: Final[tuple[float, ...]] = (
    0.0300, 0.0450, 0.0550, 0.0500, 0.0400,
    0.0320, 0.0260, 0.0220, 0.0190, 0.0170,
    0.0150, 0.0140, 0.0130,
)


# =========================================================================
#  Scenario Definitions
# =========================================================================

@dataclass(frozen=True)
class ScenarioDefinition:
    """Complete scenario definition with all macro variables.

    Reference: FR Y-14A Schedule A, SR 12-7 §III.
    """
    scenario_type: ScenarioType
    name: str
    variables: tuple[MacroVariable, ...]
    description: str = ""
    quarters: int = QUARTERS


def build_scenario(scenario_type: ScenarioType) -> ScenarioDefinition:
    """Build a complete scenario definition.

    Args:
        scenario_type: BASELINE, ADVERSE, or SEVERELY_ADVERSE.

    Returns:
        ScenarioDefinition with all macro variables.

    Reference: Federal Reserve CCAR 2026 Scenarios.
    """
    if scenario_type == ScenarioType.BASELINE:
        return ScenarioDefinition(
            scenario_type=ScenarioType.BASELINE,
            name="Baseline",
            description="Consensus economic forecast — moderate growth",
            variables=(
                MacroVariable(MacroVariableType.REAL_GDP_GROWTH, "Real GDP Growth", BASELINE_GDP, "annualized_qoq"),
                MacroVariable(MacroVariableType.UNEMPLOYMENT_RATE, "Unemployment Rate", BASELINE_UNEMPLOYMENT, "rate"),
                MacroVariable(MacroVariableType.HPI_CHANGE, "HPI Change", BASELINE_HPI, "qoq"),
                MacroVariable(MacroVariableType.EQUITY_INDEX_CHANGE, "Equity Index Change", BASELINE_EQUITY, "qoq"),
                MacroVariable(MacroVariableType.TREASURY_10Y, "10Y Treasury", BASELINE_10Y, "rate"),
                MacroVariable(MacroVariableType.BBB_SPREAD, "BBB Spread", BASELINE_BBB_SPREAD, "spread"),
            ),
        )
    elif scenario_type == ScenarioType.ADVERSE:
        return ScenarioDefinition(
            scenario_type=ScenarioType.ADVERSE,
            name="Adverse",
            description="Moderate recession — GDP -3%, unemployment 7%",
            variables=(
                MacroVariable(MacroVariableType.REAL_GDP_GROWTH, "Real GDP Growth", ADVERSE_GDP, "annualized_qoq"),
                MacroVariable(MacroVariableType.UNEMPLOYMENT_RATE, "Unemployment Rate", ADVERSE_UNEMPLOYMENT, "rate"),
                MacroVariable(MacroVariableType.HPI_CHANGE, "HPI Change", ADVERSE_HPI, "qoq"),
                MacroVariable(MacroVariableType.EQUITY_INDEX_CHANGE, "Equity Index Change", ADVERSE_EQUITY, "qoq"),
                MacroVariable(MacroVariableType.TREASURY_10Y, "10Y Treasury", ADVERSE_10Y, "rate"),
                MacroVariable(MacroVariableType.BBB_SPREAD, "BBB Spread", ADVERSE_BBB_SPREAD, "spread"),
            ),
        )
    else:
        return ScenarioDefinition(
            scenario_type=ScenarioType.SEVERELY_ADVERSE,
            name="Severely Adverse",
            description="Deep recession — GDP -8.5%, unemployment 10%, HPI -25%, equity -55%",
            variables=(
                MacroVariable(MacroVariableType.REAL_GDP_GROWTH, "Real GDP Growth", SEVERE_GDP, "annualized_qoq"),
                MacroVariable(MacroVariableType.UNEMPLOYMENT_RATE, "Unemployment Rate", SEVERE_UNEMPLOYMENT, "rate"),
                MacroVariable(MacroVariableType.HPI_CHANGE, "HPI Change", SEVERE_HPI, "qoq"),
                MacroVariable(MacroVariableType.EQUITY_INDEX_CHANGE, "Equity Index Change", SEVERE_EQUITY, "qoq"),
                MacroVariable(MacroVariableType.TREASURY_10Y, "10Y Treasury", SEVERE_10Y, "rate"),
                MacroVariable(MacroVariableType.BBB_SPREAD, "BBB Spread", SEVERE_BBB_SPREAD, "spread"),
            ),
        )


# =========================================================================
#  Capital Projection Parameters
#  Reference: FR Y-14A Schedule A, CCAR instructions
# =========================================================================

# PPNR component rates (as fraction of average assets)
PPNR_NII_RATE_BASELINE: Final[float] = 0.020
"""Net interest income as % of avg assets — baseline. FR Y-14A."""

PPNR_NII_RATE_STRESS: Final[float] = 0.015
"""NII rate under stress (compressed margins). FR Y-14A."""

PPNR_NONINT_INCOME_RATE: Final[float] = 0.008
"""Non-interest income as % of avg assets. FR Y-14A."""

PPNR_NONINT_EXPENSE_RATE: Final[float] = 0.018
"""Non-interest expense as % of avg assets. FR Y-14A."""

# Provision rates (as fraction of loans)
PROVISION_RATE_BASELINE: Final[float] = 0.003
"""Provision expense as % of total loans — baseline."""

PROVISION_RATE_ADVERSE: Final[float] = 0.010
"""Provision rate — adverse scenario. Reference: CCAR 2024 results."""

PROVISION_RATE_SEVERE: Final[float] = 0.020
"""Provision rate — severely adverse scenario. Reference: CCAR 2024 results, GFC-era ~2-2.5%."""

# Capital action assumptions per CCAR
DIVIDEND_PAYOUT_RATIO: Final[float] = 0.30
"""Common dividend payout ratio (% of projected net income). CCAR assumption."""

SHARE_BUYBACK_SUSPENSION: Final[bool] = True
"""Share buybacks assumed suspended under stress per CCAR rules."""

# DTA realization limits under stress
DTA_REALIZATION_RATE_STRESS: Final[float] = 0.05
"""Maximum DTA realization per quarter under stress (% of DTA balance)."""

# Stress Capital Buffer
SCB_FLOOR: Final[float] = 0.025
"""SCB floor: 2.5% per 12 CFR 217.11(a)(4)(iv)."""

# RWA migration under stress
RWA_MIGRATION_ADVERSE: Final[float] = 0.05
"""RWA increase under adverse scenario (5% due to rating downgrades)."""

RWA_MIGRATION_SEVERE: Final[float] = 0.12
"""RWA increase under severely adverse scenario (12%)."""
