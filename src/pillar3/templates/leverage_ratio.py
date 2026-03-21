"""Pillar 3 Templates — LR1 and LR2: Leverage Ratio Disclosures.

LR1: Summary comparison of accounting assets vs leverage ratio exposure.
LR2: Leverage ratio common disclosure with detailed components.

All amounts in USD millions ($M). Ratios as decimals.

References:
- BCBS d455 Tables LR1, LR2
- BCBS d400 Section 6: Leverage ratio
- 12 CFR 217.10(a)(4)-(5): SLR requirements
- 12 CFR 217.10(c): Total leverage exposure calculation
- ERBA NPR pp. 59-68: Supplementary Leverage Ratio
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# =========================================================================
#  LR1: Summary Comparison — Accounting Assets vs Leverage Exposure
#  Reference: BCBS d455 Table LR1
# =========================================================================

class LR1Row(BaseModel):
    """A single row in the LR1 disclosure template.

    Reference: BCBS d455 Table LR1.
    """
    row_number: int = Field(description="Row number")
    description: str = Field(description="Item description")
    amount: float = Field(default=0.0, description="Amount in $M")


class Pillar3LR1(BaseModel):
    """Pillar 3 Template LR1: Accounting Assets vs Leverage Exposure.

    Shows the reconciliation from total consolidated assets per the
    published financial statements to the total leverage exposure
    measure used in the SLR calculation.

    Reference: BCBS d455 Table LR1.
    """
    template_id: str = Field(default="LR1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[LR1Row] = Field(default_factory=list)

    total_consolidated_assets: float = Field(
        description="Total consolidated assets per financial statements in $M"
    )
    total_leverage_exposure: float = Field(
        description="Total leverage ratio exposure measure in $M"
    )


def build_lr1(
    total_consolidated_assets: float,
    adjustment_for_investments: float = 0.0,
    adjustment_for_derivatives: float = 0.0,
    adjustment_for_sft: float = 0.0,
    off_balance_sheet_items: float = 0.0,
    other_adjustments: float = 0.0,
    regulatory_deductions: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3LR1:
    """Build Pillar 3 LR1: Accounting Assets vs Leverage Exposure.

    Reconciles total consolidated assets to the leverage ratio
    exposure measure by adding/subtracting adjustments for derivatives,
    SFTs, off-balance-sheet items, and regulatory deductions.

    Args:
        total_consolidated_assets: Total consolidated assets in $M.
        adjustment_for_investments: Adjustment for investments in
            consolidated entities (deducted from assets) in $M.
        adjustment_for_derivatives: Adjustment for derivative
            financial instruments (SA-CCR vs accounting) in $M.
        adjustment_for_sft: Adjustment for securities financing
            transactions (repo/reverse repo) in $M.
        off_balance_sheet_items: Off-balance-sheet items after CCF in $M.
        other_adjustments: Other adjustments in $M.
        regulatory_deductions: CET1 deductions (reduces exposure) in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3LR1 disclosure template.

    Reference: BCBS d455 Table LR1, 12 CFR 217.10(c).
    """
    tle = (
        total_consolidated_assets
        - adjustment_for_investments
        + adjustment_for_derivatives
        + adjustment_for_sft
        + off_balance_sheet_items
        + other_adjustments
        - regulatory_deductions
    )

    rows: list[LR1Row] = [
        LR1Row(
            row_number=1,
            description="Total consolidated assets per published financial statements",
            amount=total_consolidated_assets,
        ),
        LR1Row(
            row_number=2,
            description="Adjustment for investments in banking, financial, "
                        "insurance or commercial entities that are consolidated "
                        "for accounting but outside regulatory consolidation",
            amount=-adjustment_for_investments,
        ),
        LR1Row(
            row_number=3,
            description="Adjustment for derivative financial instruments (SA-CCR)",
            amount=adjustment_for_derivatives,
        ),
        LR1Row(
            row_number=4,
            description="Adjustment for securities financing transactions (SFTs)",
            amount=adjustment_for_sft,
        ),
        LR1Row(
            row_number=5,
            description="Off-balance-sheet items (CCF-adjusted)",
            amount=off_balance_sheet_items,
        ),
        LR1Row(
            row_number=6,
            description="Other adjustments",
            amount=other_adjustments,
        ),
        LR1Row(
            row_number=7,
            description="Regulatory deductions from Tier 1 capital",
            amount=-regulatory_deductions,
        ),
        LR1Row(
            row_number=8,
            description="Total leverage ratio exposure measure",
            amount=tle,
        ),
    ]

    return Pillar3LR1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_consolidated_assets=total_consolidated_assets,
        total_leverage_exposure=tle,
    )


# =========================================================================
#  LR2: Leverage Ratio Common Disclosure
#  Reference: BCBS d455 Table LR2
# =========================================================================

class LR2Row(BaseModel):
    """A single row in the LR2 disclosure template.

    Reference: BCBS d455 Table LR2.
    """
    row_number: int = Field(description="Row number")
    description: str = Field(description="Item description")
    amount: float = Field(default=0.0, description="Amount in $M")


class Pillar3LR2(BaseModel):
    """Pillar 3 Template LR2: Leverage Ratio Common Disclosure.

    Detailed leverage ratio disclosure showing all components of the
    exposure measure and the resulting leverage ratio.

    Reference: BCBS d455 Table LR2.
    """
    template_id: str = Field(default="LR2")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[LR2Row] = Field(default_factory=list)

    # Key metrics
    on_balance_sheet_exposures: float = Field(default=0.0)
    derivative_exposures: float = Field(default=0.0)
    sft_exposures: float = Field(default=0.0)
    off_balance_sheet_exposures: float = Field(default=0.0)
    tier1_capital: float = Field(default=0.0)
    total_leverage_exposure: float = Field(default=0.0)
    leverage_ratio: float = Field(default=0.0)

    # SLR requirements
    slr_minimum: float = Field(default=0.03, description="SLR minimum: 3%")
    eslr_requirement: float = Field(
        default=0.05,
        description="Enhanced SLR for Category I G-SIBs: 5%"
    )
    slr_surplus: float = Field(
        default=0.0,
        description="Surplus above SLR minimum"
    )
    eslr_surplus: float = Field(
        default=0.0,
        description="Surplus above eSLR requirement"
    )


def build_lr2(
    on_balance_sheet_excl_derivatives: float,
    on_balance_sheet_deductions: float = 0.0,
    derivative_replacement_cost: float = 0.0,
    derivative_pfe: float = 0.0,
    derivative_deductions: float = 0.0,
    ccp_derivative_exposure: float = 0.0,
    sft_gross: float = 0.0,
    sft_ccr_addon: float = 0.0,
    sft_agent_exemption: float = 0.0,
    off_bs_notional: float = 0.0,
    off_bs_ccf_adjustment: float = 0.0,
    tier1_capital: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3LR2:
    """Build Pillar 3 LR2: Leverage Ratio Common Disclosure.

    Creates the detailed LR2 disclosure template showing all components
    of the total leverage exposure measure and the resulting SLR.

    SLR = Tier 1 capital / Total leverage exposure
    Reference: 12 CFR 217.10(a)(4).

    Enhanced SLR for Category I G-SIBs = 5%
    (SLR 3% + 2% buffer)
    Reference: 12 CFR 217.11(d)(4).

    Args:
        on_balance_sheet_excl_derivatives: On-BS assets excluding
            derivative and SFT exposures in $M.
        on_balance_sheet_deductions: Asset amounts deducted from
            Tier 1 capital in $M.
        derivative_replacement_cost: Current replacement cost of
            derivative contracts in $M.
        derivative_pfe: Potential future exposure add-on for
            derivatives (SA-CCR) in $M.
        derivative_deductions: Deductions for derivative
            receivables in $M.
        ccp_derivative_exposure: Trade exposure to CCPs in $M.
        sft_gross: Gross SFT assets in $M.
        sft_ccr_addon: SFT counterparty credit risk add-on in $M.
        sft_agent_exemption: Exempted SFT exposures (agent basis) in $M.
        off_bs_notional: Off-balance-sheet notional before CCF in $M.
        off_bs_ccf_adjustment: CCF adjustment to OBS items in $M.
        tier1_capital: Tier 1 capital in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3LR2 disclosure template.

    Reference: BCBS d455 Table LR2, 12 CFR 217.10(c).
    """
    # On-balance-sheet
    on_bs = on_balance_sheet_excl_derivatives - on_balance_sheet_deductions

    # Derivatives
    total_derivatives = (
        derivative_replacement_cost + derivative_pfe
        - derivative_deductions + ccp_derivative_exposure
    )

    # SFTs
    total_sft = sft_gross + sft_ccr_addon - sft_agent_exemption

    # Off-balance-sheet
    off_bs = off_bs_notional - off_bs_ccf_adjustment

    # Total leverage exposure
    tle = on_bs + total_derivatives + total_sft + off_bs

    # Leverage ratio
    lr = tier1_capital / tle if tle > 0 else 0.0

    slr_min = 0.03
    eslr_req = 0.05
    slr_surplus = lr - slr_min
    eslr_surplus = lr - eslr_req

    rows: list[LR2Row] = [
        # On-balance-sheet
        LR2Row(row_number=1,
               description="On-balance-sheet items (excluding derivatives and SFTs)",
               amount=on_balance_sheet_excl_derivatives),
        LR2Row(row_number=2,
               description="Asset amounts deducted in determining Tier 1 capital",
               amount=-on_balance_sheet_deductions),
        LR2Row(row_number=3,
               description="Total on-balance-sheet exposures",
               amount=on_bs),
        # Derivatives
        LR2Row(row_number=4,
               description="Replacement cost (SA-CCR methodology)",
               amount=derivative_replacement_cost),
        LR2Row(row_number=5,
               description="PFE add-on (SA-CCR methodology)",
               amount=derivative_pfe),
        LR2Row(row_number=6,
               description="Deductions for derivative receivables",
               amount=-derivative_deductions),
        LR2Row(row_number=7,
               description="CCP trade exposures",
               amount=ccp_derivative_exposure),
        LR2Row(row_number=8,
               description="Total derivative exposures",
               amount=total_derivatives),
        # SFTs
        LR2Row(row_number=9,
               description="Gross SFT assets",
               amount=sft_gross),
        LR2Row(row_number=10,
               description="SFT counterparty credit risk add-on",
               amount=sft_ccr_addon),
        LR2Row(row_number=11,
               description="Agent transaction exemptions",
               amount=-sft_agent_exemption),
        LR2Row(row_number=12,
               description="Total SFT exposures",
               amount=total_sft),
        # Off-balance-sheet
        LR2Row(row_number=13,
               description="Off-balance-sheet exposures (gross notional)",
               amount=off_bs_notional),
        LR2Row(row_number=14,
               description="Adjustments for credit conversion factors",
               amount=-off_bs_ccf_adjustment),
        LR2Row(row_number=15,
               description="Total off-balance-sheet exposures",
               amount=off_bs),
        # Totals
        LR2Row(row_number=16,
               description="Tier 1 capital",
               amount=tier1_capital),
        LR2Row(row_number=17,
               description="Total leverage ratio exposure measure",
               amount=tle),
        LR2Row(row_number=18,
               description="Leverage ratio (%)",
               amount=lr * 100),  # Display as percentage
        # Requirements
        LR2Row(row_number=19,
               description="SLR minimum requirement (%)",
               amount=slr_min * 100),
        LR2Row(row_number=20,
               description="Enhanced SLR requirement — Category I G-SIB (%)",
               amount=eslr_req * 100),
        LR2Row(row_number=21,
               description="SLR surplus / (deficit) (%)",
               amount=slr_surplus * 100),
        LR2Row(row_number=22,
               description="eSLR surplus / (deficit) (%)",
               amount=eslr_surplus * 100),
    ]

    return Pillar3LR2(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        on_balance_sheet_exposures=on_bs,
        derivative_exposures=total_derivatives,
        sft_exposures=total_sft,
        off_balance_sheet_exposures=off_bs,
        tier1_capital=tier1_capital,
        total_leverage_exposure=tle,
        leverage_ratio=lr,
        slr_minimum=slr_min,
        eslr_requirement=eslr_req,
        slr_surplus=slr_surplus,
        eslr_surplus=eslr_surplus,
    )
