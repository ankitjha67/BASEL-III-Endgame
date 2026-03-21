"""IRRBB Calculator — Economic Value of Equity and Net Interest Income.

Implements the standardised measurement framework for Interest Rate Risk
in the Banking Book (IRRBB) per BCBS d368:
- EVE (Economic Value of Equity) shock calculations
- NII (Net Interest Income) shock calculations
- Six prescribed shock scenarios
- Aggregation across currencies
- Outlier test assessment

All amounts in USD millions ($M). Rates as decimals.

References:
- BCBS d368: "Interest Rate Risk in the Banking Book" (April 2016)
- BCBS d368 Section 3: Standardised framework
- BCBS d368 Annex 1: Prescribed interest rate shock scenarios
- BCBS d368 Principle 5: Supervisory outlier test
- BCBS d368 Principle 7: EVE outlier threshold (15% of Tier 1)
- SR 10-1: Interagency Advisory on IRRBB
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, Field

from src.pillar2.irrbb.irrbb_params import (
    AUTOMATIC_CAP_FLOOR,
    CURRENCY_SPECIFIC_SHOCKS,
    DEFAULT_USD_SHOCKS,
    EVE_FLOOR_RATE,
    EVE_OUTLIER_THRESHOLD_PCT,
    IRRBB_SCENARIO_NAMES,
    IRRBBScenario,
    IRRBBShockParams,
    NII_HORIZON_YEARS,
    NII_MATERIALITY_THRESHOLD_PCT,
    TIME_BUCKETS_MIDPOINTS,
    compute_scenario_shocks,
    get_shock_params,
)


# =========================================================================
#  Data Models
# =========================================================================

class CashFlowBucket(BaseModel):
    """A single time bucket of cash flows for IRRBB calculation.

    Represents repricing cash flows in a specific time bucket for
    a single currency.

    Reference: BCBS d368 Section 3.3, Table 2.
    """
    bucket_index: int = Field(description="Index into the time bucket array")
    midpoint_years: float = Field(description="Midpoint of the time bucket in years")
    label: str = Field(default="", description="Human-readable bucket label")

    # Cash flows in $M
    asset_cash_flows: float = Field(
        default=0.0,
        description="Net asset repricing cash flows in $M"
    )
    liability_cash_flows: float = Field(
        default=0.0,
        description="Net liability repricing cash flows in $M (positive = outflow)"
    )
    net_cash_flows: float = Field(
        default=0.0,
        description="Net position = assets - liabilities in $M"
    )

    # Base rate
    base_rate: float = Field(
        default=0.0,
        description="Base (current) interest rate for this bucket (decimal)"
    )

    # Notional repricing amounts
    asset_notional: float = Field(
        default=0.0,
        description="Asset notional repricing in this bucket in $M"
    )
    liability_notional: float = Field(
        default=0.0,
        description="Liability notional repricing in this bucket in $M"
    )


class CurrencyCashFlows(BaseModel):
    """Cash flows for a single currency across all time buckets.

    Reference: BCBS d368 Section 3.3.
    """
    currency: str = Field(description="ISO 4217 currency code")
    buckets: list[CashFlowBucket] = Field(default_factory=list)
    total_assets: float = Field(default=0.0, description="Total asset CFs in $M")
    total_liabilities: float = Field(default=0.0, description="Total liability CFs in $M")


class EVEScenarioResult(BaseModel):
    """EVE change result for a single scenario and currency.

    Reference: BCBS d368 Section 3.3.
    """
    scenario: IRRBBScenario
    currency: str = Field(default="USD")
    scenario_name: str = Field(default="")

    # EVE values
    base_eve: float = Field(description="EVE under base rates in $M")
    shocked_eve: float = Field(description="EVE under shocked rates in $M")
    eve_change: float = Field(description="Change in EVE in $M (negative = decline)")
    eve_change_pct: float = Field(
        default=0.0,
        description="EVE change as % of base EVE"
    )

    # Shocks applied
    shocks_applied: list[float] = Field(
        default_factory=list,
        description="Rate shocks in decimal for each time bucket"
    )


class EVEResult(BaseModel):
    """Aggregated EVE results across all scenarios and currencies.

    The worst-case EVE decline determines the IRRBB capital add-on.

    Reference: BCBS d368 Section 3.3, Principle 7.
    """
    # Per-scenario results
    scenario_results: list[EVEScenarioResult] = Field(default_factory=list)

    # Worst case
    worst_scenario: IRRBBScenario = Field(
        default=IRRBBScenario.PARALLEL_UP,
        description="Scenario with the largest EVE decline"
    )
    worst_eve_change: float = Field(
        default=0.0,
        description="Largest EVE decline in $M"
    )
    worst_eve_change_pct_tier1: float = Field(
        default=0.0,
        description="Worst EVE change as % of Tier 1 capital"
    )

    # Outlier assessment
    tier1_capital: float = Field(default=0.0, description="Tier 1 capital in $M")
    outlier_threshold: float = Field(
        default=EVE_OUTLIER_THRESHOLD_PCT,
        description="Outlier threshold (15% of Tier 1)"
    )
    is_outlier: bool = Field(
        default=False,
        description="True if worst EVE decline > 15% of Tier 1"
    )


class NIIScenarioResult(BaseModel):
    """NII change result for a single scenario.

    Reference: BCBS d368 Section 3.4.
    """
    scenario: IRRBBScenario
    currency: str = Field(default="USD")
    scenario_name: str = Field(default="")

    # NII values
    base_nii: float = Field(description="NII under base rates in $M")
    shocked_nii: float = Field(description="NII under shocked rates in $M")
    nii_change: float = Field(description="Change in NII in $M")
    nii_change_pct: float = Field(
        default=0.0,
        description="NII change as % of base NII"
    )


class NIIResult(BaseModel):
    """Aggregated NII results across all scenarios.

    Reference: BCBS d368 Section 3.4.
    """
    scenario_results: list[NIIScenarioResult] = Field(default_factory=list)

    worst_scenario: IRRBBScenario = Field(
        default=IRRBBScenario.PARALLEL_UP,
        description="Scenario with the largest NII decline"
    )
    worst_nii_change: float = Field(
        default=0.0,
        description="Largest NII decline in $M"
    )
    worst_nii_change_pct_tier1: float = Field(
        default=0.0,
        description="Worst NII change as % of Tier 1 capital"
    )
    tier1_capital: float = Field(default=0.0)
    is_material: bool = Field(
        default=False,
        description="True if worst NII decline > 5% of Tier 1"
    )


class IRRBBResult(BaseModel):
    """Complete IRRBB assessment combining EVE and NII analysis.

    Reference: BCBS d368 Section 3.
    """
    eve_result: EVEResult
    nii_result: NIIResult

    # Capital implications
    irrbb_capital_addon: float = Field(
        default=0.0,
        description="Pillar 2A capital add-on for IRRBB in $M"
    )
    irrbb_addon_pct_rwa: float = Field(
        default=0.0,
        description="IRRBB add-on as % of RWA"
    )

    # Summary flags
    requires_supervisory_action: bool = Field(
        default=False,
        description="True if outlier test is triggered"
    )
    currencies_analyzed: list[str] = Field(default_factory=list)


# =========================================================================
#  Core Calculation Functions
# =========================================================================

def discount_factor(rate: float, maturity: float) -> float:
    """Compute continuous-compounding discount factor.

    DF(t) = exp(-r * t)

    Args:
        rate: Interest rate (decimal).
        maturity: Time to maturity in years.

    Returns:
        Discount factor.

    Reference: BCBS d368 Section 3.3, para 118.
    """
    return math.exp(-rate * maturity)


def compute_eve_base(
    buckets: list[CashFlowBucket],
) -> float:
    """Compute base EVE (Economic Value of Equity) from cash flows.

    EVE = sum of discounted net cash flows across all time buckets.
    EVE = sum_t [ CF_net(t) * DF(r_base, t) ]

    Args:
        buckets: Cash flow buckets with base rates.

    Returns:
        Base EVE in $M.

    Reference: BCBS d368 Section 3.3, para 117.
    """
    eve = 0.0
    for b in buckets:
        df = discount_factor(b.base_rate, b.midpoint_years)
        eve += b.net_cash_flows * df
    return eve


def compute_eve_shocked(
    buckets: list[CashFlowBucket],
    shocks: list[float],
    apply_floor: bool = AUTOMATIC_CAP_FLOOR,
    floor_rate: float = EVE_FLOOR_RATE,
) -> float:
    """Compute shocked EVE under a specific rate scenario.

    EVE_shocked = sum_t [ CF_net(t) * DF(r_shocked, t) ]
    where r_shocked = max(r_base + shock, floor_rate)

    Args:
        buckets: Cash flow buckets with base rates.
        shocks: Rate shocks for each time bucket (decimal).
        apply_floor: Whether to apply the interest rate floor.
        floor_rate: Minimum post-shock rate.

    Returns:
        Shocked EVE in $M.

    Reference: BCBS d368 Section 3.3, paras 116-118.
    """
    if len(shocks) != len(buckets):
        raise ValueError(
            f"Number of shocks ({len(shocks)}) must match number of buckets "
            f"({len(buckets)}). Reference: BCBS d368 Section 3.3."
        )

    eve = 0.0
    for b, shock in zip(buckets, shocks):
        shocked_rate = b.base_rate + shock
        if apply_floor:
            shocked_rate = max(shocked_rate, floor_rate)
        df = discount_factor(shocked_rate, b.midpoint_years)
        eve += b.net_cash_flows * df
    return eve


def calculate_eve_change(
    buckets: list[CashFlowBucket],
    scenario: IRRBBScenario,
    shock_params: IRRBBShockParams = DEFAULT_USD_SHOCKS,
    currency: str = "USD",
    apply_floor: bool = AUTOMATIC_CAP_FLOOR,
    floor_rate: float = EVE_FLOOR_RATE,
) -> EVEScenarioResult:
    """Calculate EVE change for a single scenario and currency.

    Computes:
    1. Base EVE from current rates
    2. Shocked EVE under the prescribed scenario
    3. EVE change = Shocked - Base

    A negative EVE change indicates a decline in economic value.

    Args:
        buckets: Cash flow buckets for the currency.
        scenario: One of the six prescribed scenarios.
        shock_params: Currency-specific shock magnitudes.
        currency: ISO 4217 currency code.
        apply_floor: Whether to apply the interest rate floor.
        floor_rate: Minimum post-shock rate.

    Returns:
        EVEScenarioResult with base, shocked, and change values.

    Reference: BCBS d368 Section 3.3.
    """
    # Compute shocks for this scenario
    bucket_midpoints = [b.midpoint_years for b in buckets]
    shocks = compute_scenario_shocks(scenario, shock_params, bucket_midpoints)

    # Base EVE
    base_eve = compute_eve_base(buckets)

    # Shocked EVE
    shocked_eve = compute_eve_shocked(buckets, shocks, apply_floor, floor_rate)

    # Change
    eve_change = shocked_eve - base_eve
    eve_change_pct = (eve_change / base_eve * 100.0) if base_eve != 0 else 0.0

    return EVEScenarioResult(
        scenario=scenario,
        currency=currency,
        scenario_name=IRRBB_SCENARIO_NAMES.get(scenario, scenario.value),
        base_eve=base_eve,
        shocked_eve=shocked_eve,
        eve_change=eve_change,
        eve_change_pct=eve_change_pct,
        shocks_applied=shocks,
    )


def calculate_nii_change(
    buckets: list[CashFlowBucket],
    scenario: IRRBBScenario,
    shock_params: IRRBBShockParams = DEFAULT_USD_SHOCKS,
    currency: str = "USD",
    nii_horizon: float = NII_HORIZON_YEARS,
    apply_floor: bool = AUTOMATIC_CAP_FLOOR,
    floor_rate: float = EVE_FLOOR_RATE,
) -> NIIScenarioResult:
    """Calculate NII change for a single scenario and currency.

    NII measures the impact of rate changes on interest income over a
    specified horizon (typically 1 year). Only cash flows within the
    NII horizon are considered.

    NII_change = sum_t [ notional_gap(t) * shock(t) * min(t, horizon) / horizon ]

    For each bucket within the horizon:
    - Asset repricing: higher rates increase NII (for variable rate)
    - Liability repricing: higher rates decrease NII

    Args:
        buckets: Cash flow buckets for the currency.
        scenario: One of the six prescribed scenarios.
        shock_params: Currency-specific shock magnitudes.
        currency: ISO 4217 currency code.
        nii_horizon: NII calculation horizon in years.
        apply_floor: Whether to apply the interest rate floor.
        floor_rate: Minimum post-shock rate.

    Returns:
        NIIScenarioResult with base, shocked, and change values.

    Reference: BCBS d368 Section 3.4, paras 120-122.
    """
    # Compute shocks
    bucket_midpoints = [b.midpoint_years for b in buckets]
    shocks = compute_scenario_shocks(scenario, shock_params, bucket_midpoints)

    # Base NII: sum of net interest income from current rates
    base_nii = 0.0
    shocked_nii = 0.0

    for i, b in enumerate(buckets):
        if b.midpoint_years > nii_horizon:
            # Only buckets within the NII horizon contribute
            break

        # Time fraction within horizon
        time_in_horizon = min(b.midpoint_years, nii_horizon)
        weight = time_in_horizon / nii_horizon if nii_horizon > 0 else 0.0

        # Net interest from base rates
        # NII contribution = net_position * rate * time_weight
        net_position = b.asset_notional - b.liability_notional
        base_contribution = net_position * b.base_rate * weight
        base_nii += base_contribution

        # Shocked NII
        shocked_rate = b.base_rate + shocks[i]
        if apply_floor:
            shocked_rate = max(shocked_rate, floor_rate)
        shocked_contribution = net_position * shocked_rate * weight
        shocked_nii += shocked_contribution

    nii_change = shocked_nii - base_nii
    nii_change_pct = (nii_change / base_nii * 100.0) if base_nii != 0 else 0.0

    return NIIScenarioResult(
        scenario=scenario,
        currency=currency,
        scenario_name=IRRBB_SCENARIO_NAMES.get(scenario, scenario.value),
        base_nii=base_nii,
        shocked_nii=shocked_nii,
        nii_change=nii_change,
        nii_change_pct=nii_change_pct,
    )


# =========================================================================
#  Multi-Scenario / Multi-Currency Aggregation
# =========================================================================

def compute_eve_all_scenarios(
    currency_cash_flows: list[CurrencyCashFlows],
    tier1_capital: float,
) -> EVEResult:
    """Compute EVE changes across all six scenarios and all currencies.

    For each scenario, EVE changes are aggregated across currencies
    (sum of negative changes only, per BCBS d368 para 119).

    The worst-case EVE decline is then compared against the 15%
    Tier 1 outlier threshold.

    Args:
        currency_cash_flows: Cash flows by currency.
        tier1_capital: Tier 1 capital in $M.

    Returns:
        EVEResult with per-scenario results and outlier assessment.

    Reference: BCBS d368 Section 3.3, Principle 7.
    """
    all_results: list[EVEScenarioResult] = []
    scenario_totals: dict[IRRBBScenario, float] = {}

    for scenario in IRRBBScenario:
        total_change = 0.0

        for ccf in currency_cash_flows:
            shock_params = get_shock_params(ccf.currency)
            result = calculate_eve_change(
                buckets=ccf.buckets,
                scenario=scenario,
                shock_params=shock_params,
                currency=ccf.currency,
            )
            all_results.append(result)
            # Aggregate: sum negative changes across currencies
            # Reference: BCBS d368 para 119
            total_change += result.eve_change

        scenario_totals[scenario] = total_change

    # Worst case (largest decline = most negative change)
    worst_scenario = min(scenario_totals, key=scenario_totals.get)  # type: ignore[arg-type]
    worst_change = scenario_totals[worst_scenario]

    # Outlier test
    worst_pct_tier1 = 0.0
    is_outlier = False
    if tier1_capital > 0:
        worst_pct_tier1 = abs(worst_change) / tier1_capital
        is_outlier = worst_pct_tier1 > EVE_OUTLIER_THRESHOLD_PCT

    return EVEResult(
        scenario_results=all_results,
        worst_scenario=worst_scenario,
        worst_eve_change=worst_change,
        worst_eve_change_pct_tier1=worst_pct_tier1,
        tier1_capital=tier1_capital,
        outlier_threshold=EVE_OUTLIER_THRESHOLD_PCT,
        is_outlier=is_outlier,
    )


def compute_nii_all_scenarios(
    currency_cash_flows: list[CurrencyCashFlows],
    tier1_capital: float,
) -> NIIResult:
    """Compute NII changes across all six scenarios and all currencies.

    For each scenario, NII changes are summed across currencies.
    The worst-case NII decline is compared against the 5% Tier 1
    materiality threshold.

    Args:
        currency_cash_flows: Cash flows by currency.
        tier1_capital: Tier 1 capital in $M.

    Returns:
        NIIResult with per-scenario results and materiality assessment.

    Reference: BCBS d368 Section 3.4, Principle 5.
    """
    all_results: list[NIIScenarioResult] = []
    scenario_totals: dict[IRRBBScenario, float] = {}

    for scenario in IRRBBScenario:
        total_change = 0.0

        for ccf in currency_cash_flows:
            shock_params = get_shock_params(ccf.currency)
            result = calculate_nii_change(
                buckets=ccf.buckets,
                scenario=scenario,
                shock_params=shock_params,
                currency=ccf.currency,
            )
            all_results.append(result)
            total_change += result.nii_change

        scenario_totals[scenario] = total_change

    # Worst case (largest decline)
    worst_scenario = min(scenario_totals, key=scenario_totals.get)  # type: ignore[arg-type]
    worst_change = scenario_totals[worst_scenario]

    # Materiality test
    worst_pct_tier1 = 0.0
    is_material = False
    if tier1_capital > 0:
        worst_pct_tier1 = abs(worst_change) / tier1_capital
        is_material = worst_pct_tier1 > NII_MATERIALITY_THRESHOLD_PCT

    return NIIResult(
        scenario_results=all_results,
        worst_scenario=worst_scenario,
        worst_nii_change=worst_change,
        worst_nii_change_pct_tier1=worst_pct_tier1,
        tier1_capital=tier1_capital,
        is_material=is_material,
    )


# =========================================================================
#  Master IRRBB Calculator
# =========================================================================

def compute_irrbb(
    currency_cash_flows: list[CurrencyCashFlows],
    tier1_capital: float,
    total_rwa: float,
    irrbb_addon_multiplier: float = 1.0,
) -> IRRBBResult:
    """Compute complete IRRBB assessment.

    This is the master function that:
    1. Runs EVE analysis across all scenarios and currencies
    2. Runs NII analysis across all scenarios and currencies
    3. Determines worst-case impacts
    4. Assesses outlier test
    5. Calculates the Pillar 2A capital add-on

    The IRRBB capital add-on is based on the worst-case EVE decline:
    Add-on = |worst EVE change| * multiplier

    Args:
        currency_cash_flows: Cash flows by currency.
        tier1_capital: Tier 1 capital in $M.
        total_rwa: Total RWA in $M.
        irrbb_addon_multiplier: Multiplier for EVE-based add-on (default 1.0).

    Returns:
        IRRBBResult with complete EVE, NII, and capital add-on analysis.

    Reference: BCBS d368 Section 3.
    """
    # EVE analysis
    eve_result = compute_eve_all_scenarios(currency_cash_flows, tier1_capital)

    # NII analysis
    nii_result = compute_nii_all_scenarios(currency_cash_flows, tier1_capital)

    # Capital add-on based on worst EVE decline
    addon = abs(eve_result.worst_eve_change) * irrbb_addon_multiplier
    addon_pct_rwa = addon / total_rwa if total_rwa > 0 else 0.0

    # Supervisory action required if outlier test triggered
    requires_action = eve_result.is_outlier

    currencies = list(set(ccf.currency for ccf in currency_cash_flows))

    return IRRBBResult(
        eve_result=eve_result,
        nii_result=nii_result,
        irrbb_capital_addon=addon,
        irrbb_addon_pct_rwa=addon_pct_rwa,
        requires_supervisory_action=requires_action,
        currencies_analyzed=currencies,
    )
