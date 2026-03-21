"""Capital Projector — 9-quarter capital projection under stress.

Projects regulatory capital ratios over the CCAR horizon under each
scenario, computing PPNR, provisions, capital actions, and the
Stress Capital Buffer (SCB).

All amounts in USD millions ($M). Ratios as decimals.

References:
    - SR 12-7 §IV: Capital planning under stress
    - FR Y-14A Schedule A: 9-quarter capital projection
    - 12 CFR 217.11(a)(4)(iv): Stress Capital Buffer (SCB)
    - Dodd-Frank Act §165(i): Stress testing requirements
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.stress_testing.stress_params import (
    DIVIDEND_PAYOUT_RATIO,
    DTA_REALIZATION_RATE_STRESS,
    PPNR_NII_RATE_BASELINE,
    PPNR_NII_RATE_STRESS,
    PPNR_NONINT_EXPENSE_RATE,
    PPNR_NONINT_INCOME_RATE,
    SCB_FLOOR,
    SHARE_BUYBACK_SUSPENSION,
    ScenarioType,
)
from src.stress_testing.scenario_engine import ScenarioResult


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class QuarterlyCapitalState:
    """Capital state at the end of a quarter.

    Reference: FR Y-14A Schedule A, Capital Projection.
    """
    quarter: int
    # PPNR components
    net_interest_income: float = 0.0
    non_interest_income: float = 0.0
    non_interest_expense: float = 0.0
    ppnr: float = 0.0
    # Provisions and losses
    provision_expense: float = 0.0
    trading_losses: float = 0.0
    other_losses: float = 0.0
    # Pre-tax income
    pre_tax_income: float = 0.0
    tax_expense: float = 0.0
    net_income: float = 0.0
    # Capital actions
    common_dividends: float = 0.0
    preferred_dividends: float = 0.0
    share_buybacks: float = 0.0
    total_capital_actions: float = 0.0
    # OCI
    aoci_change: float = 0.0
    # Capital levels
    cet1_capital: float = 0.0
    tier1_capital: float = 0.0
    total_capital: float = 0.0
    total_rwa: float = 0.0
    total_leverage_exposure: float = 0.0
    # Ratios
    cet1_ratio: float = 0.0
    tier1_ratio: float = 0.0
    total_capital_ratio: float = 0.0
    slr: float = 0.0


@dataclass
class CapitalProjectionResult:
    """Complete capital projection over the CCAR horizon.

    Reference: SR 12-7 §IV, FR Y-14A.
    """
    scenario_type: ScenarioType
    quarterly_states: list[QuarterlyCapitalState] = field(default_factory=list)
    # Minimum ratios across the projection
    min_cet1_ratio: float = 1.0
    min_cet1_quarter: int = 0
    min_tier1_ratio: float = 1.0
    min_total_ratio: float = 1.0
    min_slr: float = 1.0
    # Peak-to-trough
    starting_cet1_ratio: float = 0.0
    ending_cet1_ratio: float = 0.0
    peak_to_trough_cet1: float = 0.0
    # SCB
    stress_capital_buffer: float = 0.0
    # Totals
    total_ppnr: float = 0.0
    total_provisions: float = 0.0
    total_losses: float = 0.0
    total_capital_actions: float = 0.0


# =========================================================================
#  Capital Projector
# =========================================================================

class CapitalProjector:
    """9-quarter capital projection engine under stress.

    Projects the capital waterfall:
    Beginning CET1 + PPNR - Provisions - Losses - Capital Actions + AOCI = Ending CET1

    Reference: SR 12-7 §IV, FR Y-14A.
    """

    def __init__(
        self,
        tax_rate: float = 0.21,
        preferred_dividend_quarterly: float = 0.0,
        at1_capital_ratio: float = 0.015,
        tier2_capital_ratio: float = 0.02,
    ) -> None:
        """Initialize capital projector.

        Args:
            tax_rate: Corporate tax rate (21% US federal).
            preferred_dividend_quarterly: Quarterly preferred dividends ($M).
            at1_capital_ratio: AT1 as ratio of CET1 (for tier1 projection).
            tier2_capital_ratio: Tier2 as ratio of CET1.

        Reference: FR Y-14A instructions.
        """
        self.tax_rate = tax_rate
        self.preferred_dividend_quarterly = preferred_dividend_quarterly
        self.at1_capital_ratio = at1_capital_ratio
        self.tier2_capital_ratio = tier2_capital_ratio

    def project_capital(
        self,
        scenario_result: ScenarioResult,
        starting_cet1: float,
        starting_rwa: float,
        avg_assets: float,
        total_loans: float,
        starting_tle: float = 0.0,
        projection_quarters: int = 9,
    ) -> CapitalProjectionResult:
        """Run 9-quarter capital projection.

        Args:
            scenario_result: Portfolio impact from scenario application.
            starting_cet1: Starting CET1 capital ($M).
            starting_rwa: Starting RWA ($M).
            avg_assets: Average total assets ($M).
            total_loans: Total loan portfolio ($M).
            starting_tle: Starting total leverage exposure ($M).
            projection_quarters: Number of quarters (9 per CCAR).

        Returns:
            CapitalProjectionResult with full quarterly projection.

        Reference: SR 12-7 §IV, FR Y-14A Schedule A.
        """
        is_stress = scenario_result.scenario_type != ScenarioType.BASELINE

        quarterly_states: list[QuarterlyCapitalState] = []
        cet1 = starting_cet1
        rwa = starting_rwa
        tle = starting_tle if starting_tle > 0 else avg_assets * 1.1

        total_ppnr = 0.0
        total_provisions = 0.0
        total_losses = 0.0
        total_actions = 0.0

        for q in range(projection_quarters):
            impact = (
                scenario_result.quarterly_impacts[q]
                if q < len(scenario_result.quarterly_impacts)
                else scenario_result.quarterly_impacts[-1]
            )

            # PPNR
            nii_rate = PPNR_NII_RATE_STRESS if is_stress else PPNR_NII_RATE_BASELINE
            nii = avg_assets * (nii_rate + impact.nii_impact_pct) / 4.0
            nonint_income = avg_assets * PPNR_NONINT_INCOME_RATE / 4.0
            nonint_expense = avg_assets * PPNR_NONINT_EXPENSE_RATE / 4.0
            ppnr = nii + nonint_income - nonint_expense

            # Provisions
            provision = impact.credit_loss_rate * total_loans

            # Trading losses
            trading_losses = max(0.0, -impact.trading_pl) if is_stress else 0.0

            # Pre-tax income
            pre_tax = ppnr - provision - trading_losses
            tax = max(0.0, pre_tax * self.tax_rate)
            net_income = pre_tax - tax

            # Capital actions
            common_div = max(0.0, net_income * DIVIDEND_PAYOUT_RATIO) if net_income > 0 else 0.0
            buybacks = 0.0  # Suspended under stress per CCAR
            pref_div = self.preferred_dividend_quarterly
            cap_actions = common_div + pref_div + buybacks

            # AOCI change (rates-driven)
            aoci_change = 0.0
            if is_stress:
                # Approximate AOCI impact from rate changes on AFS portfolio
                aoci_change = impact.nii_impact_pct * avg_assets * 0.01

            # Capital waterfall
            cet1 = cet1 + net_income - cap_actions + aoci_change

            # RWA migration
            rwa = rwa * (1.0 + impact.rwa_migration_pct)

            # Ratios
            tier1 = cet1 * (1.0 + self.at1_capital_ratio)
            total_cap = tier1 + cet1 * self.tier2_capital_ratio
            cet1_ratio = cet1 / rwa if rwa > 0 else 0.0
            tier1_ratio = tier1 / rwa if rwa > 0 else 0.0
            total_ratio = total_cap / rwa if rwa > 0 else 0.0
            slr = tier1 / tle if tle > 0 else 0.0

            state = QuarterlyCapitalState(
                quarter=q + 1,
                net_interest_income=nii,
                non_interest_income=nonint_income,
                non_interest_expense=nonint_expense,
                ppnr=ppnr,
                provision_expense=provision,
                trading_losses=trading_losses,
                pre_tax_income=pre_tax,
                tax_expense=tax,
                net_income=net_income,
                common_dividends=common_div,
                preferred_dividends=pref_div,
                share_buybacks=buybacks,
                total_capital_actions=cap_actions,
                aoci_change=aoci_change,
                cet1_capital=cet1,
                tier1_capital=tier1,
                total_capital=total_cap,
                total_rwa=rwa,
                total_leverage_exposure=tle,
                cet1_ratio=cet1_ratio,
                tier1_ratio=tier1_ratio,
                total_capital_ratio=total_ratio,
                slr=slr,
            )
            quarterly_states.append(state)

            total_ppnr += ppnr
            total_provisions += provision
            total_losses += trading_losses
            total_actions += cap_actions

        # Summary statistics
        starting_ratio = starting_cet1 / starting_rwa if starting_rwa > 0 else 0.0
        cet1_ratios = [s.cet1_ratio for s in quarterly_states]
        min_cet1 = min(cet1_ratios)
        min_cet1_q = cet1_ratios.index(min_cet1) + 1
        peak_to_trough = starting_ratio - min_cet1

        # SCB = max(2.5%, peak-to-trough CET1 decline + 4 quarters dividends)
        four_q_dividends = sum(
            s.common_dividends for s in quarterly_states[:4]
        )
        four_q_div_ratio = four_q_dividends / starting_rwa if starting_rwa > 0 else 0.0
        scb = max(SCB_FLOOR, peak_to_trough + four_q_div_ratio)

        return CapitalProjectionResult(
            scenario_type=scenario_result.scenario_type,
            quarterly_states=quarterly_states,
            min_cet1_ratio=min_cet1,
            min_cet1_quarter=min_cet1_q,
            min_tier1_ratio=min(s.tier1_ratio for s in quarterly_states),
            min_total_ratio=min(s.total_capital_ratio for s in quarterly_states),
            min_slr=min(s.slr for s in quarterly_states),
            starting_cet1_ratio=starting_ratio,
            ending_cet1_ratio=quarterly_states[-1].cet1_ratio if quarterly_states else 0.0,
            peak_to_trough_cet1=peak_to_trough,
            stress_capital_buffer=scb,
            total_ppnr=total_ppnr,
            total_provisions=total_provisions,
            total_losses=total_losses,
            total_capital_actions=total_actions,
        )
