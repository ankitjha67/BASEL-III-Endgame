"""Mathematical helper functions for regulatory capital calculations.

Provides common mathematical operations used across the capital engine:
- Vasicek model utilities
- Risk weight interpolation
- Maturity-related calculations
- Statistical functions for backtesting

All monetary amounts in USD millions ($M).

References:
    - BCBS d424: Basel III framework mathematical foundations
    - BCBS d457: Market risk framework (SBM aggregation)
    - SR 11-7: Model risk management — quantitative methods
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from scipy.stats import norm  # type: ignore[import-untyped]


# =========================================================================
#  Vasicek Model Utilities
# =========================================================================

def vasicek_conditional_pd(
    pd: float,
    correlation: float,
    confidence_level: float = 0.999,
) -> float:
    """Compute conditional PD under the Vasicek single-factor model.

    Formula: N((N^{-1}(PD) + sqrt(R) * N^{-1}(confidence)) / sqrt(1-R))

    Used as the core building block for IRB risk weight functions.

    Args:
        pd: Probability of default (annual, decimal).
        correlation: Asset correlation R.
        confidence_level: Confidence level (0.999 = 99.9%).

    Returns:
        Conditional PD at the given confidence level.

    Reference: BCBS d424 CRE31.6, para 44.
    """
    if pd <= 0.0 or pd >= 1.0:
        return pd

    g_pd = norm.ppf(pd)
    g_conf = norm.ppf(confidence_level)

    conditional = norm.cdf(
        (g_pd + math.sqrt(correlation) * g_conf) / math.sqrt(1.0 - correlation)
    )
    return float(conditional)


def merton_distance_to_default(
    asset_value: float,
    debt_value: float,
    asset_volatility: float,
    time_horizon: float = 1.0,
    risk_free_rate: float = 0.04,
) -> float:
    """Compute Merton model distance to default.

    DD = (ln(V/D) + (r - 0.5 * sigma^2) * T) / (sigma * sqrt(T))

    Args:
        asset_value: Firm asset value ($M).
        debt_value: Firm debt (default barrier) ($M).
        asset_volatility: Annual asset return volatility.
        time_horizon: Time horizon in years.
        risk_free_rate: Risk-free rate.

    Returns:
        Distance to default (number of std devs).

    Reference: Merton (1974), used in PD calibration per BCBS d350 §4.1.
    """
    if asset_value <= 0 or debt_value <= 0 or asset_volatility <= 0:
        return 0.0

    numerator = (
        math.log(asset_value / debt_value)
        + (risk_free_rate - 0.5 * asset_volatility**2) * time_horizon
    )
    denominator = asset_volatility * math.sqrt(time_horizon)
    return numerator / denominator if denominator > 0 else 0.0


def pd_from_distance_to_default(dd: float) -> float:
    """Convert distance to default to PD.

    PD = N(-DD)

    Args:
        dd: Distance to default.

    Returns:
        Probability of default.

    Reference: Merton (1974).
    """
    return float(norm.cdf(-dd))


# =========================================================================
#  Risk Weight Interpolation
# =========================================================================

def interpolate_risk_weight(
    ltv: float,
    ltv_breakpoints: list[float],
    rw_values: list[float],
) -> float:
    """Interpolate risk weight based on LTV ratio.

    Used for residential mortgage risk weights under SA-CR where
    risk weights vary by LTV band.

    Args:
        ltv: Loan-to-value ratio (decimal, e.g., 0.80 = 80%).
        ltv_breakpoints: LTV breakpoints (sorted ascending).
        rw_values: Risk weights corresponding to each band.

    Returns:
        Interpolated risk weight.

    Reference: ERBA NPR Table 3 — Residential mortgage risk weights.
    """
    if not ltv_breakpoints or not rw_values:
        return 1.0

    if ltv <= ltv_breakpoints[0]:
        return rw_values[0]

    for i in range(len(ltv_breakpoints) - 1):
        if ltv_breakpoints[i] <= ltv <= ltv_breakpoints[i + 1]:
            frac = (ltv - ltv_breakpoints[i]) / (
                ltv_breakpoints[i + 1] - ltv_breakpoints[i]
            )
            return rw_values[i] + frac * (rw_values[i + 1] - rw_values[i])

    return rw_values[-1]


def effective_maturity(
    cash_flows: list[tuple[float, float]],
    min_maturity: float = 1.0,
    max_maturity: float = 5.0,
) -> float:
    """Compute effective maturity from cash flow schedule.

    M = max(1, min(5, sum(t_i * CF_i) / sum(CF_i)))

    Args:
        cash_flows: List of (time_in_years, cash_flow_amount) pairs.
        min_maturity: Floor (1 year per BCBS d424 CRE32.17).
        max_maturity: Cap (5 years per BCBS d424 CRE32.17).

    Returns:
        Effective maturity in years.

    Reference: BCBS d424 CRE32.17.
    """
    if not cash_flows:
        return 2.5  # Default per F-IRB

    weighted_sum = sum(t * cf for t, cf in cash_flows if cf > 0)
    total_cf = sum(cf for _, cf in cash_flows if cf > 0)

    if total_cf <= 0:
        return 2.5

    m = weighted_sum / total_cf
    return max(min_maturity, min(m, max_maturity))


# =========================================================================
#  Statistical Helpers
# =========================================================================

def portfolio_variance(
    exposures: np.ndarray,
    correlation_matrix: np.ndarray,
    loss_rates: np.ndarray,
) -> float:
    """Compute portfolio loss variance for concentration risk.

    Var = sum_i sum_j EAD_i * EAD_j * LR_i * LR_j * rho_ij

    Args:
        exposures: EAD vector ($M).
        correlation_matrix: Pairwise asset correlations.
        loss_rates: Expected loss rate per exposure.

    Returns:
        Portfolio loss variance.

    Reference: Pillar 2 concentration risk assessment.
    """
    weighted = exposures * loss_rates
    return float(weighted @ correlation_matrix @ weighted)


def herfindahl_index(exposures: np.ndarray) -> float:
    """Compute Herfindahl-Hirschman Index for concentration.

    HHI = sum((EAD_i / sum(EAD))^2)

    Args:
        exposures: Exposure amounts ($M).

    Returns:
        HHI (0 to 1, where 1 = fully concentrated).

    Reference: Used in Pillar 2 concentration risk, FR Y-15.
    """
    total = exposures.sum()
    if total <= 0:
        return 0.0
    shares = exposures / total
    return float((shares**2).sum())


def kupiec_test(
    exceptions: int,
    total_observations: int,
    confidence_level: float = 0.99,
) -> tuple[float, bool]:
    """Kupiec proportion of failures test for VaR backtesting.

    Tests whether the number of VaR exceptions is consistent
    with the confidence level.

    Args:
        exceptions: Number of VaR breaches.
        total_observations: Total trading days.
        confidence_level: VaR confidence level.

    Returns:
        Tuple of (test_statistic, pass_flag).

    Reference: BCBS d457 MAR99 — backtesting requirements.
    """
    if total_observations <= 0:
        return 0.0, True

    p = 1.0 - confidence_level
    n = total_observations
    x = exceptions

    if x == 0:
        return 0.0, True

    # Likelihood ratio test statistic
    p_hat = x / n
    if p_hat <= 0 or p_hat >= 1:
        return 0.0, x <= n * p * 3

    lr = -2.0 * (
        x * math.log(p / p_hat)
        + (n - x) * math.log((1 - p) / (1 - p_hat))
    )

    # Chi-square critical value at 95% with 1 df = 3.841
    passed = lr < 3.841
    return lr, passed


# =========================================================================
#  Discount Factor Utilities
# =========================================================================

def discount_factor(
    rate: float,
    time_years: float,
    compounding: str = "continuous",
) -> float:
    """Compute discount factor.

    Args:
        rate: Discount rate (annual, decimal).
        time_years: Time in years.
        compounding: "continuous" or "annual".

    Returns:
        Discount factor (0 to 1).

    Reference: Used across CVA, ECL, and market risk modules.
    """
    if compounding == "continuous":
        return math.exp(-rate * time_years)
    else:
        return 1.0 / (1.0 + rate) ** time_years


def present_value(
    cash_flows: list[tuple[float, float]],
    discount_rate: float,
    compounding: str = "continuous",
) -> float:
    """Compute present value of cash flows.

    Args:
        cash_flows: List of (time_years, amount) pairs.
        discount_rate: Discount rate.
        compounding: Compounding convention.

    Returns:
        Present value ($M).
    """
    return sum(
        amount * discount_factor(discount_rate, t, compounding)
        for t, amount in cash_flows
    )
