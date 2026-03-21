"""Capital components calculator — CET1, AT1, Tier 2 per Basel III Endgame.

Implements the full regulatory capital stack for a Category I US G-SIB:
- Common Equity Tier 1 (CET1): common stock, retained earnings, AOCI,
  regulatory deductions (goodwill, DTA, threshold deductions)
- Additional Tier 1 (AT1): qualifying non-cumulative perpetual preferred,
  trust preferred (grandfathered), minority interests
- Tier 2: subordinated debt, general allowances (capped at 1.25% SA-RWA),
  minority interests, amortizing instruments

All amounts in USD millions ($M).

References:
- 12 CFR 217.20-22: Capital components and deductions
- ERBA NPR pp. 34-92: Regulatory capital framework
- FR Y-9C Schedule HC-R Part I: Regulatory capital components
- BCBS d424 paras 49-53: Definition of capital
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_params import (
    AT1_MINORITY_INTEREST_INCLUSION_LIMIT,
    DTA_AGGREGATE_THRESHOLD,
    DTA_BELOW_THRESHOLD_RW,
    DTA_THRESHOLD_PERCENT,
    GOODWILL_DEDUCTION_RATE,
    MSA_INDIVIDUAL_THRESHOLD,
    MSA_RISK_WEIGHT,
    SIGNIFICANT_INVESTMENT_BELOW_THRESHOLD_RW,
    SIGNIFICANT_INVESTMENT_THRESHOLD,
    TIER2_ALLOWANCE_CAP_SA,
    TIER2_AMORTIZATION_SCHEDULE_YEARS,
)


# =========================================================================
#  Enumerations
# =========================================================================

class CapitalTier(Enum):
    """Capital quality tiers per 12 CFR 217.20.

    Reference: ERBA NPR pp. 34-36.
    """
    CET1 = "CET1"
    AT1 = "AT1"
    TIER2 = "TIER2"


class DeductionCategory(Enum):
    """Categories of regulatory capital deductions per 12 CFR 217.22.

    Reference: ERBA NPR pp. 70-85.
    """
    GOODWILL = "GOODWILL"
    OTHER_INTANGIBLES = "OTHER_INTANGIBLES"
    DTA_CARRYFORWARD = "DTA_CARRYFORWARD"
    DTA_TIMING = "DTA_TIMING"
    DEFINED_BENEFIT_PENSION = "DEFINED_BENEFIT_PENSION"
    GAIN_ON_SALE_SECURITIZATION = "GAIN_ON_SALE_SECURITIZATION"
    INVESTMENTS_OWN_SHARES = "INVESTMENTS_OWN_SHARES"
    RECIPROCAL_CROSS_HOLDINGS = "RECIPROCAL_CROSS_HOLDINGS"
    SIGNIFICANT_INVESTMENTS_CET1 = "SIGNIFICANT_INVESTMENTS_CET1"
    SIGNIFICANT_INVESTMENTS_AT1 = "SIGNIFICANT_INVESTMENTS_AT1"
    SIGNIFICANT_INVESTMENTS_TIER2 = "SIGNIFICANT_INVESTMENTS_TIER2"
    NON_SIGNIFICANT_INVESTMENTS = "NON_SIGNIFICANT_INVESTMENTS"
    MSA = "MSA"  # 250% RW, NOT deducted per US 2026
    THRESHOLD_DEDUCTION = "THRESHOLD_DEDUCTION"
    OTHER = "OTHER"


class InstrumentType(Enum):
    """Types of capital instruments per 12 CFR 217.20.

    Reference: ERBA NPR pp. 86-92.
    """
    COMMON_STOCK = "COMMON_STOCK"
    RETAINED_EARNINGS = "RETAINED_EARNINGS"
    AOCI = "AOCI"
    SURPLUS = "SURPLUS"
    PREFERRED_NONCUMULATIVE = "PREFERRED_NONCUMULATIVE"
    PREFERRED_CUMULATIVE = "PREFERRED_CUMULATIVE"
    TRUST_PREFERRED = "TRUST_PREFERRED"
    SUBORDINATED_DEBT = "SUBORDINATED_DEBT"
    GENERAL_ALLOWANCE = "GENERAL_ALLOWANCE"
    MINORITY_INTEREST = "MINORITY_INTEREST"
    QUALIFYING_AT1 = "QUALIFYING_AT1"
    QUALIFYING_TIER2 = "QUALIFYING_TIER2"


# =========================================================================
#  Input Data Models
# =========================================================================

class CommonEquityInputs(BaseModel):
    """Common equity inputs for CET1 calculation.

    Maps to FR Y-9C Schedule HC-R Part I, Items 1-3.
    All amounts in $M.

    Reference: 12 CFR 217.20(b), ERBA NPR pp. 34-40.
    """
    common_stock: float = Field(
        description="Par value of common stock issued. HC-R Item 1."
    )
    surplus: float = Field(
        description="Additional paid-in capital (surplus). HC-R Item 2."
    )
    retained_earnings: float = Field(
        description="Retained earnings. HC-R Item 3."
    )
    aoci: float = Field(
        default=0.0,
        description="Accumulated other comprehensive income. HC-R Item 4. "
                    "Negative = unrealized losses (reduce CET1)."
    )
    treasury_stock: float = Field(
        default=0.0,
        description="Treasury stock (at cost). Reduces CET1. HC-R Item 5."
    )
    minority_interest_cet1: float = Field(
        default=0.0,
        description="Qualifying minority interest in CET1 of consolidated "
                    "subsidiaries. HC-R Item 6."
    )


class DeductionItem(BaseModel):
    """A single regulatory capital deduction.

    Reference: 12 CFR 217.22, ERBA NPR pp. 70-85.
    """
    category: DeductionCategory
    amount: float = Field(description="Deduction amount in $M")
    tier: CapitalTier = Field(
        default=CapitalTier.CET1,
        description="Capital tier from which deduction is taken"
    )
    description: str = Field(default="")
    regulatory_reference: str = Field(
        default="",
        description="Specific CFR/NPR citation"
    )


class AT1Instrument(BaseModel):
    """An Additional Tier 1 capital instrument.

    Reference: 12 CFR 217.20(c), ERBA NPR pp. 86-89.
    """
    instrument_type: InstrumentType
    amount: float = Field(description="Qualifying amount in $M")
    issuer: str = Field(default="")
    maturity: Optional[date] = Field(
        default=None,
        description="Maturity date (None for perpetual instruments)"
    )
    coupon_rate: float = Field(default=0.0)
    is_grandfathered: bool = Field(
        default=False,
        description="True for pre-2014 trust preferred securities"
    )


class Tier2Instrument(BaseModel):
    """A Tier 2 capital instrument.

    Reference: 12 CFR 217.20(d), ERBA NPR pp. 90-92.
    """
    instrument_type: InstrumentType
    face_amount: float = Field(description="Original face amount in $M")
    current_amount: float = Field(
        description="Current qualifying amount after amortization, in $M"
    )
    issuer: str = Field(default="")
    maturity_date: Optional[date] = Field(
        default=None,
        description="Maturity date for amortization calculation"
    )
    remaining_maturity_years: float = Field(
        default=10.0,
        description="Remaining maturity in years"
    )
    is_subordinated: bool = Field(default=True)


class ThresholdDeductionInputs(BaseModel):
    """Inputs for threshold-based deductions per 12 CFR 217.22(d).

    Items subject to the 10% individual / 15% aggregate thresholds:
    1. Significant investments in unconsolidated financial institutions
    2. MSAs (250% RW per US 2026 — NOT deducted below threshold)
    3. DTAs arising from timing differences

    Reference: 12 CFR 217.22(d), ERBA NPR pp. 74-80.
    """
    significant_investments_cet1: float = Field(
        default=0.0,
        description="CET1 instruments of unconsolidated FIs. "
                    "Subject to 10% individual threshold."
    )
    mortgage_servicing_assets: float = Field(
        default=0.0,
        description="Mortgage servicing assets (net of deferred tax liability). "
                    "Per US 2026: 250% RW, NOT deducted below threshold. "
                    "Reference: ERBA NPR p. 78."
    )
    dta_timing_differences: float = Field(
        default=0.0,
        description="DTAs from temporary timing differences. "
                    "Subject to 10% individual threshold."
    )


# =========================================================================
#  Result Models
# =========================================================================

class CET1Result(BaseModel):
    """CET1 capital calculation result.

    Maps to FR Y-9C Schedule HC-R Part I, Items 1-12.
    Reference: 12 CFR 217.20(b), 12 CFR 217.22.
    """
    # Gross components (before deductions)
    common_stock: float = Field(description="HC-R Item 1: Common stock")
    surplus: float = Field(description="HC-R Item 2: Surplus")
    retained_earnings: float = Field(description="HC-R Item 3: Retained earnings")
    aoci: float = Field(description="HC-R Item 4: AOCI")
    treasury_stock: float = Field(description="HC-R Item 5: Treasury stock")
    minority_interest: float = Field(
        description="HC-R Item 6: Qualifying CET1 minority interest"
    )

    # Gross CET1 before deductions
    gross_cet1: float = Field(description="HC-R Item 7: Gross CET1")

    # Deductions
    goodwill_deduction: float = Field(
        description="HC-R Item 8: Goodwill (net of associated DTL)"
    )
    other_intangibles_deduction: float = Field(
        default=0.0,
        description="HC-R Item 9: Other intangibles (net of associated DTL)"
    )
    dta_carryforward_deduction: float = Field(
        default=0.0,
        description="HC-R Item 10: DTAs from NOL/tax credit carryforwards"
    )
    defined_benefit_pension_deduction: float = Field(
        default=0.0,
        description="HC-R Item 10a: Defined benefit pension fund net assets"
    )
    gain_on_sale_deduction: float = Field(
        default=0.0,
        description="Gain-on-sale associated with securitization exposures"
    )
    investments_own_shares_deduction: float = Field(
        default=0.0,
        description="Investments in own shares (including indirect)"
    )
    reciprocal_cross_holdings_deduction: float = Field(
        default=0.0,
        description="Reciprocal cross-holdings in CET1 instruments"
    )

    # Threshold deductions
    significant_investments_deduction: float = Field(
        default=0.0,
        description="Significant investments exceeding 10% individual threshold"
    )
    msa_deduction: float = Field(
        default=0.0,
        description="MSA exceeding 10% threshold. NOTE: Per US 2026, "
                    "MSA below threshold receives 250% RW, NOT deducted."
    )
    dta_timing_deduction: float = Field(
        default=0.0,
        description="DTAs from timing differences exceeding 10% threshold"
    )
    aggregate_threshold_deduction: float = Field(
        default=0.0,
        description="Additional deduction for amounts exceeding 15% aggregate "
                    "threshold (significant investments + MSA + DTA timing)"
    )
    other_deductions: float = Field(
        default=0.0,
        description="All other CET1 deductions"
    )

    # Totals
    total_deductions: float = Field(description="HC-R Item 11: Total deductions")
    net_cet1: float = Field(description="HC-R Item 12: CET1 capital (net)")

    # 250% RW items (below threshold)
    msa_below_threshold_250rw: float = Field(
        default=0.0,
        description="MSA below threshold receiving 250% risk weight. "
                    "Reference: ERBA NPR p. 78."
    )
    dta_below_threshold_250rw: float = Field(
        default=0.0,
        description="DTA below threshold receiving 250% risk weight"
    )
    significant_inv_below_threshold_250rw: float = Field(
        default=0.0,
        description="Significant investments below threshold, 250% RW"
    )
    total_250rw_rwa: float = Field(
        default=0.0,
        description="Total RWA from 250% risk-weighted items"
    )


class AT1Result(BaseModel):
    """AT1 capital calculation result.

    Maps to FR Y-9C Schedule HC-R Part I, Items 13-15.
    Reference: 12 CFR 217.20(c).
    """
    qualifying_instruments: float = Field(
        description="HC-R Item 13: Qualifying AT1 instruments"
    )
    minority_interest_at1: float = Field(
        default=0.0,
        description="HC-R Item 14: Qualifying AT1 minority interest"
    )
    at1_deductions: float = Field(
        default=0.0,
        description="HC-R Item 14a: AT1 regulatory deductions"
    )
    gross_at1: float = Field(description="Gross AT1 before deductions")
    net_at1: float = Field(description="HC-R Item 15: AT1 capital (net)")


class Tier2Result(BaseModel):
    """Tier 2 capital calculation result.

    Maps to FR Y-9C Schedule HC-R Part I, Items 16-17.
    Reference: 12 CFR 217.20(d).
    """
    qualifying_instruments: float = Field(
        description="HC-R Item 16a: Qualifying Tier 2 instruments"
    )
    general_allowance: float = Field(
        default=0.0,
        description="HC-R Item 16b: Eligible portion of ALLL/ACL "
                    "(capped at 1.25% of SA RWA)"
    )
    minority_interest_tier2: float = Field(
        default=0.0,
        description="HC-R Item 16c: Qualifying Tier 2 minority interest"
    )
    tier2_deductions: float = Field(
        default=0.0,
        description="HC-R Item 16d: Tier 2 regulatory deductions"
    )
    gross_tier2: float = Field(description="Gross Tier 2 before deductions")
    net_tier2: float = Field(description="HC-R Item 17: Tier 2 capital (net)")


class TotalCapitalResult(BaseModel):
    """Total regulatory capital stack.

    Maps to FR Y-9C Schedule HC-R Part I.
    Reference: 12 CFR 217.20.
    """
    cet1: CET1Result
    at1: AT1Result
    tier2: Tier2Result
    tier1_capital: float = Field(description="Tier 1 = CET1 + AT1")
    total_capital: float = Field(description="Total Capital = Tier 1 + Tier 2")


# =========================================================================
#  Calculation Functions
# =========================================================================

def compute_threshold_deductions(
    cet1_before_threshold: float,
    threshold_inputs: ThresholdDeductionInputs,
) -> dict[str, float]:
    """Compute threshold-based deductions per 12 CFR 217.22(d).

    Applies the two-step threshold test:
    1. Individual 10% threshold: each item (significant investments, MSA,
       DTA timing) is tested against 10% of CET1.
    2. Aggregate 15% threshold: combined below-threshold amounts tested
       against 15% of CET1.

    For MSA: per US 2026 re-proposal, amounts below the 10% threshold
    receive 250% risk weight instead of deduction (ERBA NPR p. 78).

    Args:
        cet1_before_threshold: CET1 before threshold deductions, in $M.
        threshold_inputs: Amounts subject to threshold tests.

    Returns:
        Dictionary with deduction amounts and 250% RW items.

    Reference: 12 CFR 217.22(d)(1)-(4), ERBA NPR pp. 74-80.
    """
    individual_threshold = cet1_before_threshold * DTA_THRESHOLD_PERCENT
    aggregate_threshold = cet1_before_threshold * DTA_AGGREGATE_THRESHOLD

    # Step 1: Individual 10% test
    sig_inv = threshold_inputs.significant_investments_cet1
    msa = threshold_inputs.mortgage_servicing_assets
    dta = threshold_inputs.dta_timing_differences

    sig_inv_deduction = max(0.0, sig_inv - individual_threshold)
    sig_inv_below = min(sig_inv, individual_threshold)

    msa_deduction = max(0.0, msa - individual_threshold)
    msa_below = min(msa, individual_threshold)

    dta_deduction = max(0.0, dta - individual_threshold)
    dta_below = min(dta, individual_threshold)

    # Step 2: Aggregate 15% test on below-threshold amounts
    total_below = sig_inv_below + msa_below + dta_below
    aggregate_excess = max(0.0, total_below - aggregate_threshold)

    # Proportional allocation of aggregate excess
    if total_below > 0 and aggregate_excess > 0:
        sig_inv_agg_deduction = aggregate_excess * (sig_inv_below / total_below)
        msa_agg_deduction = aggregate_excess * (msa_below / total_below)
        dta_agg_deduction = aggregate_excess * (dta_below / total_below)
    else:
        sig_inv_agg_deduction = 0.0
        msa_agg_deduction = 0.0
        dta_agg_deduction = 0.0

    # Final below-threshold amounts (after aggregate test)
    sig_inv_final_below = sig_inv_below - sig_inv_agg_deduction
    msa_final_below = msa_below - msa_agg_deduction
    dta_final_below = dta_below - dta_agg_deduction

    return {
        # Individual threshold deductions
        "significant_investments_deduction": sig_inv_deduction,
        "msa_deduction": msa_deduction,
        "dta_timing_deduction": dta_deduction,
        # Aggregate threshold deduction
        "aggregate_threshold_deduction": aggregate_excess,
        "aggregate_sig_inv_deduction": sig_inv_agg_deduction,
        "aggregate_msa_deduction": msa_agg_deduction,
        "aggregate_dta_deduction": dta_agg_deduction,
        # Below-threshold items receiving 250% RW
        "sig_inv_below_threshold": sig_inv_final_below,
        "msa_below_threshold": msa_final_below,
        "dta_below_threshold": dta_final_below,
        # 250% RW amounts
        "sig_inv_250rw_rwa": sig_inv_final_below * SIGNIFICANT_INVESTMENT_BELOW_THRESHOLD_RW,
        "msa_250rw_rwa": msa_final_below * MSA_RISK_WEIGHT,
        "dta_250rw_rwa": dta_final_below * DTA_BELOW_THRESHOLD_RW,
    }


def compute_cet1(
    equity_inputs: CommonEquityInputs,
    deductions: list[DeductionItem],
    threshold_inputs: Optional[ThresholdDeductionInputs] = None,
) -> CET1Result:
    """Compute Common Equity Tier 1 capital per 12 CFR 217.20(b).

    CET1 = Common stock + Surplus + Retained earnings + AOCI
           - Treasury stock + Minority interests - Regulatory deductions

    Deductions applied per 12 CFR 217.22:
    - Goodwill (full deduction)
    - Other intangibles (full deduction, net of associated DTL)
    - DTA from carryforwards (full deduction)
    - Defined benefit pension fund net assets
    - Gain-on-sale from securitizations
    - Investments in own shares
    - Reciprocal cross-holdings
    - Threshold items (10%/15% threshold test)

    Args:
        equity_inputs: Common equity components.
        deductions: List of regulatory deductions.
        threshold_inputs: Optional threshold deduction inputs.

    Returns:
        CET1Result with all components and deductions itemized.

    Reference: FR Y-9C Schedule HC-R Part I Items 1-12.
    """
    # Gross CET1 before deductions
    gross_cet1 = (
        equity_inputs.common_stock
        + equity_inputs.surplus
        + equity_inputs.retained_earnings
        + equity_inputs.aoci
        - equity_inputs.treasury_stock
        + equity_inputs.minority_interest_cet1
    )

    # Categorize deductions
    goodwill = 0.0
    other_intangibles = 0.0
    dta_carryforward = 0.0
    defined_benefit_pension = 0.0
    gain_on_sale = 0.0
    own_shares = 0.0
    reciprocal = 0.0
    other = 0.0

    for d in deductions:
        if d.tier != CapitalTier.CET1:
            continue
        if d.category == DeductionCategory.GOODWILL:
            goodwill += d.amount
        elif d.category == DeductionCategory.OTHER_INTANGIBLES:
            other_intangibles += d.amount
        elif d.category == DeductionCategory.DTA_CARRYFORWARD:
            dta_carryforward += d.amount
        elif d.category == DeductionCategory.DEFINED_BENEFIT_PENSION:
            defined_benefit_pension += d.amount
        elif d.category == DeductionCategory.GAIN_ON_SALE_SECURITIZATION:
            gain_on_sale += d.amount
        elif d.category == DeductionCategory.INVESTMENTS_OWN_SHARES:
            own_shares += d.amount
        elif d.category == DeductionCategory.RECIPROCAL_CROSS_HOLDINGS:
            reciprocal += d.amount
        elif d.category == DeductionCategory.OTHER:
            other += d.amount

    # Non-threshold deductions
    non_threshold_deductions = (
        goodwill + other_intangibles + dta_carryforward
        + defined_benefit_pension + gain_on_sale
        + own_shares + reciprocal + other
    )

    # CET1 before threshold deductions (used as base for 10%/15% tests)
    cet1_before_threshold = gross_cet1 - non_threshold_deductions

    # Threshold deductions
    sig_inv_deduction = 0.0
    msa_deduction = 0.0
    dta_timing_deduction = 0.0
    aggregate_deduction = 0.0
    msa_below_threshold = 0.0
    dta_below_threshold = 0.0
    sig_inv_below_threshold = 0.0
    total_250rw_rwa = 0.0

    if threshold_inputs is not None:
        td = compute_threshold_deductions(cet1_before_threshold, threshold_inputs)
        sig_inv_deduction = (
            td["significant_investments_deduction"]
            + td["aggregate_sig_inv_deduction"]
        )
        msa_deduction = td["msa_deduction"] + td["aggregate_msa_deduction"]
        dta_timing_deduction = (
            td["dta_timing_deduction"] + td["aggregate_dta_deduction"]
        )
        aggregate_deduction = td["aggregate_threshold_deduction"]

        msa_below_threshold = td["msa_below_threshold"]
        dta_below_threshold = td["dta_below_threshold"]
        sig_inv_below_threshold = td["sig_inv_below_threshold"]
        total_250rw_rwa = (
            td["sig_inv_250rw_rwa"]
            + td["msa_250rw_rwa"]
            + td["dta_250rw_rwa"]
        )

    total_threshold_deductions = (
        sig_inv_deduction + msa_deduction + dta_timing_deduction
    )

    total_deductions = non_threshold_deductions + total_threshold_deductions

    net_cet1 = gross_cet1 - total_deductions

    return CET1Result(
        common_stock=equity_inputs.common_stock,
        surplus=equity_inputs.surplus,
        retained_earnings=equity_inputs.retained_earnings,
        aoci=equity_inputs.aoci,
        treasury_stock=equity_inputs.treasury_stock,
        minority_interest=equity_inputs.minority_interest_cet1,
        gross_cet1=gross_cet1,
        goodwill_deduction=goodwill,
        other_intangibles_deduction=other_intangibles,
        dta_carryforward_deduction=dta_carryforward,
        defined_benefit_pension_deduction=defined_benefit_pension,
        gain_on_sale_deduction=gain_on_sale,
        investments_own_shares_deduction=own_shares,
        reciprocal_cross_holdings_deduction=reciprocal,
        significant_investments_deduction=sig_inv_deduction,
        msa_deduction=msa_deduction,
        dta_timing_deduction=dta_timing_deduction,
        aggregate_threshold_deduction=aggregate_deduction,
        other_deductions=other,
        total_deductions=total_deductions,
        net_cet1=net_cet1,
        msa_below_threshold_250rw=msa_below_threshold,
        dta_below_threshold_250rw=dta_below_threshold,
        significant_inv_below_threshold_250rw=sig_inv_below_threshold,
        total_250rw_rwa=total_250rw_rwa,
    )


def compute_tier2_amortization(
    face_amount: float,
    remaining_maturity_years: float,
    amortization_years: int = TIER2_AMORTIZATION_SCHEDULE_YEARS,
) -> float:
    """Compute Tier 2 qualifying amount after straight-line amortization.

    Tier 2 instruments are amortized over the final 5 years to maturity
    at 20% per year. Instruments with > 5 years remaining maturity
    qualify at full face value.

    Args:
        face_amount: Original face amount in $M.
        remaining_maturity_years: Years to maturity.
        amortization_years: Amortization period (5 years default).

    Returns:
        Qualifying amount in $M after amortization.

    Reference: 12 CFR 217.20(d)(1)(iv), ERBA NPR p. 91.
    """
    if remaining_maturity_years >= amortization_years:
        return face_amount

    if remaining_maturity_years <= 0:
        return 0.0

    # Straight-line amortization: 20% per year for 5 years
    fraction_remaining = remaining_maturity_years / amortization_years
    return face_amount * fraction_remaining


def compute_at1(
    instruments: list[AT1Instrument],
    deductions: list[DeductionItem],
) -> AT1Result:
    """Compute Additional Tier 1 capital per 12 CFR 217.20(c).

    AT1 = Qualifying AT1 instruments + AT1 minority interests - AT1 deductions

    Qualifying instruments include:
    - Non-cumulative perpetual preferred stock
    - Qualifying AT1 capital instruments
    - Grandfathered trust preferred securities (subject to phase-out)

    Args:
        instruments: List of AT1 instruments.
        deductions: List of regulatory deductions applicable to AT1.

    Returns:
        AT1Result with components itemized.

    Reference: FR Y-9C Schedule HC-R Part I Items 13-15.
    """
    qualifying_total = 0.0
    minority_interest = 0.0

    for inst in instruments:
        if inst.instrument_type == InstrumentType.MINORITY_INTEREST:
            minority_interest += inst.amount
        else:
            qualifying_total += inst.amount

    # AT1 deductions
    at1_deductions = sum(
        d.amount for d in deductions if d.tier == CapitalTier.AT1
    )

    gross_at1 = qualifying_total + minority_interest
    net_at1 = max(0.0, gross_at1 - at1_deductions)

    return AT1Result(
        qualifying_instruments=qualifying_total,
        minority_interest_at1=minority_interest,
        at1_deductions=at1_deductions,
        gross_at1=gross_at1,
        net_at1=net_at1,
    )


def compute_tier2(
    instruments: list[Tier2Instrument],
    deductions: list[DeductionItem],
    total_allowance: float = 0.0,
    sa_rwa: float = 0.0,
    minority_interest: float = 0.0,
    valuation_date: Optional[date] = None,
) -> Tier2Result:
    """Compute Tier 2 capital per 12 CFR 217.20(d).

    Tier 2 = Qualifying subordinated debt (after amortization)
             + Eligible general allowances (capped at 1.25% SA RWA)
             + Tier 2 minority interests
             - Tier 2 deductions

    Args:
        instruments: List of Tier 2 instruments.
        deductions: List of regulatory deductions applicable to Tier 2.
        total_allowance: Total allowance for credit losses (ALLL/ACL) in $M.
        sa_rwa: Standardized approach RWA in $M (for allowance cap).
        minority_interest: Qualifying Tier 2 minority interest in $M.
        valuation_date: Date for amortization calculation.

    Returns:
        Tier2Result with components itemized.

    Reference: FR Y-9C Schedule HC-R Part I Items 16-17.
    """
    # Qualifying instruments after amortization
    qualifying_total = 0.0
    for inst in instruments:
        if inst.instrument_type == InstrumentType.GENERAL_ALLOWANCE:
            continue  # Handled separately
        qualifying_total += inst.current_amount

    # General allowance capped at 1.25% of SA RWA
    allowance_cap = sa_rwa * TIER2_ALLOWANCE_CAP_SA
    eligible_allowance = min(total_allowance, allowance_cap) if sa_rwa > 0 else 0.0

    # Tier 2 deductions
    tier2_deductions = sum(
        d.amount for d in deductions if d.tier == CapitalTier.TIER2
    )

    gross_tier2 = qualifying_total + eligible_allowance + minority_interest
    net_tier2 = max(0.0, gross_tier2 - tier2_deductions)

    return Tier2Result(
        qualifying_instruments=qualifying_total,
        general_allowance=eligible_allowance,
        minority_interest_tier2=minority_interest,
        tier2_deductions=tier2_deductions,
        gross_tier2=gross_tier2,
        net_tier2=net_tier2,
    )


def compute_total_capital(
    equity_inputs: CommonEquityInputs,
    deductions: list[DeductionItem],
    at1_instruments: list[AT1Instrument],
    tier2_instruments: list[Tier2Instrument],
    threshold_inputs: Optional[ThresholdDeductionInputs] = None,
    total_allowance: float = 0.0,
    sa_rwa: float = 0.0,
    tier2_minority_interest: float = 0.0,
) -> TotalCapitalResult:
    """Compute the full regulatory capital stack per 12 CFR 217.20.

    Total Capital = CET1 + AT1 + Tier 2

    This is the master capital components calculation that produces
    all line items for FR Y-9C Schedule HC-R Part I.

    Args:
        equity_inputs: CET1 equity components.
        deductions: All regulatory deductions across tiers.
        at1_instruments: AT1 capital instruments.
        tier2_instruments: Tier 2 capital instruments.
        threshold_inputs: Threshold deduction inputs (sig inv, MSA, DTA).
        total_allowance: Total allowance for credit losses in $M.
        sa_rwa: Standardized approach RWA for allowance cap.
        tier2_minority_interest: Qualifying Tier 2 minority interest.

    Returns:
        TotalCapitalResult with all three tiers and totals.

    Reference: FR Y-9C Schedule HC-R Part I, 12 CFR 217.20.
    """
    cet1 = compute_cet1(equity_inputs, deductions, threshold_inputs)
    at1 = compute_at1(at1_instruments, deductions)
    tier2 = compute_tier2(
        tier2_instruments,
        deductions,
        total_allowance=total_allowance,
        sa_rwa=sa_rwa,
        minority_interest=tier2_minority_interest,
    )

    tier1_capital = cet1.net_cet1 + at1.net_at1
    total_capital = tier1_capital + tier2.net_tier2

    return TotalCapitalResult(
        cet1=cet1,
        at1=at1,
        tier2=tier2,
        tier1_capital=tier1_capital,
        total_capital=total_capital,
    )


# =========================================================================
#  Leverage Exposure Calculation
# =========================================================================

class LeverageExposureInputs(BaseModel):
    """Inputs for Supplementary Leverage Ratio denominator.

    Total Leverage Exposure = On-balance-sheet assets
                             + Derivative exposures (SA-CCR)
                             + SFT exposures
                             + Off-balance-sheet items (CCF-adjusted)

    All amounts in $M.
    Reference: 12 CFR 217.10(c), ERBA NPR pp. 62-65.
    """
    total_on_balance_sheet: float = Field(
        description="Total on-balance-sheet assets (less deductions)"
    )
    derivative_exposures: float = Field(
        default=0.0,
        description="Derivative exposures per SA-CCR methodology"
    )
    sft_exposures: float = Field(
        default=0.0,
        description="Securities financing transaction exposures"
    )
    off_balance_sheet_items: float = Field(
        default=0.0,
        description="Off-balance-sheet items after credit conversion factors"
    )
    cet1_deductions: float = Field(
        default=0.0,
        description="CET1 deductions subtracted from on-balance-sheet"
    )


def compute_total_leverage_exposure(
    inputs: LeverageExposureInputs,
) -> float:
    """Compute Total Leverage Exposure for SLR denominator.

    TLE = On-balance-sheet assets (net of CET1 deductions)
          + Derivative exposures
          + SFT exposures
          + Off-balance-sheet items

    Args:
        inputs: Leverage exposure components.

    Returns:
        Total leverage exposure in $M.

    Reference: 12 CFR 217.10(c)(4), ERBA NPR pp. 62-65.
    """
    on_bs_net = inputs.total_on_balance_sheet - inputs.cet1_deductions
    return (
        on_bs_net
        + inputs.derivative_exposures
        + inputs.sft_exposures
        + inputs.off_balance_sheet_items
    )
