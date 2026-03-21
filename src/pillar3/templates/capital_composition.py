"""Pillar 3 Templates — CC1 (Capital Composition) and CC2 (Reconciliation).

CC1: Detailed breakdown of CET1, AT1, and Tier 2 capital components
including all regulatory adjustments and deductions.

CC2: Reconciliation of accounting balance sheet to regulatory capital,
showing how financial statement items map to regulatory capital components.

All amounts in USD millions ($M).

References:
- BCBS d455 Tables CC1, CC2
- BCBS d400 Section 4: Composition of capital
- 12 CFR 217.20-22: Capital components and deductions
- FR Y-9C Schedule HC-R Part I
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# =========================================================================
#  CC1: Composition of Regulatory Capital
#  Reference: BCBS d455 Table CC1
# =========================================================================

class CC1Row(BaseModel):
    """A single row in the CC1 disclosure template.

    Reference: BCBS d455 Table CC1.
    """
    row_number: int = Field(description="Row number in CC1 template")
    description: str = Field(description="Capital component description")
    amount: float = Field(description="Amount in $M")
    regulatory_reference: str = Field(
        default="",
        description="Regulatory reference (12 CFR citation)"
    )


class Pillar3CC1(BaseModel):
    """Pillar 3 Template CC1: Composition of Regulatory Capital.

    Detailed 60-row breakdown of CET1, AT1, Tier 2 components,
    regulatory adjustments, and limits.

    Reference: BCBS d455 Table CC1.
    """
    template_id: str = Field(default="CC1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[CC1Row] = Field(default_factory=list)

    # Summary totals (direct access)
    cet1_capital: float = Field(description="CET1 capital in $M")
    at1_capital: float = Field(description="AT1 capital in $M")
    tier1_capital: float = Field(description="Tier 1 capital in $M")
    tier2_capital: float = Field(description="Tier 2 capital in $M")
    total_capital: float = Field(description="Total capital in $M")
    total_rwa: float = Field(description="Total RWA in $M")

    # CET1 ratio check
    cet1_ratio: float = Field(default=0.0)
    tier1_ratio: float = Field(default=0.0)
    total_capital_ratio: float = Field(default=0.0)


def build_cc1(
    common_stock: float,
    surplus: float,
    retained_earnings: float,
    aoci: float,
    treasury_stock: float = 0.0,
    cet1_minority_interest: float = 0.0,
    goodwill_deduction: float = 0.0,
    other_intangibles_deduction: float = 0.0,
    dta_carryforward_deduction: float = 0.0,
    dta_timing_deduction: float = 0.0,
    pension_deduction: float = 0.0,
    gain_on_sale_deduction: float = 0.0,
    own_shares_deduction: float = 0.0,
    cross_holdings_deduction: float = 0.0,
    significant_inv_deduction: float = 0.0,
    msa_deduction: float = 0.0,
    aggregate_threshold_deduction: float = 0.0,
    other_cet1_deductions: float = 0.0,
    at1_instruments: float = 0.0,
    at1_minority_interest: float = 0.0,
    at1_deductions: float = 0.0,
    tier2_instruments: float = 0.0,
    tier2_allowance: float = 0.0,
    tier2_minority_interest: float = 0.0,
    tier2_deductions: float = 0.0,
    total_rwa: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3CC1:
    """Build Pillar 3 CC1: Composition of Regulatory Capital.

    Creates the CC1 disclosure template with all capital components,
    regulatory adjustments, and deductions itemized per BCBS d455.

    Args:
        common_stock: Par value of common stock in $M.
        surplus: Additional paid-in capital in $M.
        retained_earnings: Retained earnings in $M.
        aoci: Accumulated other comprehensive income in $M.
        treasury_stock: Treasury stock (at cost) in $M.
        cet1_minority_interest: Qualifying CET1 minority interest in $M.
        goodwill_deduction: Goodwill deduction in $M.
        other_intangibles_deduction: Other intangibles deduction in $M.
        dta_carryforward_deduction: DTA carryforward deduction in $M.
        dta_timing_deduction: DTA timing difference deduction in $M.
        pension_deduction: Defined benefit pension deduction in $M.
        gain_on_sale_deduction: Gain-on-sale securitization deduction in $M.
        own_shares_deduction: Investments in own shares deduction in $M.
        cross_holdings_deduction: Reciprocal cross-holdings deduction in $M.
        significant_inv_deduction: Significant investments deduction in $M.
        msa_deduction: MSA deduction in $M.
        aggregate_threshold_deduction: Aggregate threshold deduction in $M.
        other_cet1_deductions: Other CET1 deductions in $M.
        at1_instruments: AT1 qualifying instruments in $M.
        at1_minority_interest: AT1 minority interest in $M.
        at1_deductions: AT1 deductions in $M.
        tier2_instruments: Tier 2 qualifying instruments in $M.
        tier2_allowance: Eligible general allowance in $M.
        tier2_minority_interest: Tier 2 minority interest in $M.
        tier2_deductions: Tier 2 deductions in $M.
        total_rwa: Total RWA in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3CC1 disclosure template.

    Reference: BCBS d455 Table CC1.
    """
    # CET1 computation
    gross_cet1 = (
        common_stock + surplus + retained_earnings + aoci
        - treasury_stock + cet1_minority_interest
    )
    total_dta_deduction = dta_carryforward_deduction + dta_timing_deduction
    total_cet1_deductions = (
        goodwill_deduction + other_intangibles_deduction
        + total_dta_deduction + pension_deduction
        + gain_on_sale_deduction + own_shares_deduction
        + cross_holdings_deduction + significant_inv_deduction
        + msa_deduction + aggregate_threshold_deduction
        + other_cet1_deductions
    )
    net_cet1 = gross_cet1 - total_cet1_deductions

    # AT1 computation
    gross_at1 = at1_instruments + at1_minority_interest
    net_at1 = max(0.0, gross_at1 - at1_deductions)

    # Tier 1
    tier1 = net_cet1 + net_at1

    # Tier 2 computation
    gross_tier2 = tier2_instruments + tier2_allowance + tier2_minority_interest
    net_tier2 = max(0.0, gross_tier2 - tier2_deductions)

    # Total capital
    total_capital = tier1 + net_tier2

    # Ratios
    cet1_r = net_cet1 / total_rwa if total_rwa > 0 else 0.0
    tier1_r = tier1 / total_rwa if total_rwa > 0 else 0.0
    total_r = total_capital / total_rwa if total_rwa > 0 else 0.0

    # Build rows
    rows: list[CC1Row] = [
        # CET1 components
        CC1Row(row_number=1, description="Common stock plus surplus",
               amount=common_stock + surplus,
               regulatory_reference="12 CFR 217.20(b)(1)"),
        CC1Row(row_number=2, description="Retained earnings",
               amount=retained_earnings,
               regulatory_reference="12 CFR 217.20(b)(1)"),
        CC1Row(row_number=3, description="AOCI",
               amount=aoci,
               regulatory_reference="12 CFR 217.20(b)(2)"),
        CC1Row(row_number=4, description="Treasury stock",
               amount=-treasury_stock,
               regulatory_reference="12 CFR 217.20(b)"),
        CC1Row(row_number=5, description="CET1 minority interest",
               amount=cet1_minority_interest,
               regulatory_reference="12 CFR 217.21(a)"),
        CC1Row(row_number=6, description="CET1 before regulatory adjustments",
               amount=gross_cet1,
               regulatory_reference="12 CFR 217.20(b)"),
        # CET1 deductions
        CC1Row(row_number=8, description="Goodwill (net of associated DTL)",
               amount=-goodwill_deduction,
               regulatory_reference="12 CFR 217.22(a)(1)"),
        CC1Row(row_number=9, description="Other intangibles (net of DTL)",
               amount=-other_intangibles_deduction,
               regulatory_reference="12 CFR 217.22(a)(2)"),
        CC1Row(row_number=10, description="DTA (carryforwards + timing)",
               amount=-total_dta_deduction,
               regulatory_reference="12 CFR 217.22(a)(3)-(4)"),
        CC1Row(row_number=16, description="Defined benefit pension fund net assets",
               amount=-pension_deduction,
               regulatory_reference="12 CFR 217.22(a)(5)"),
        CC1Row(row_number=17, description="Gain-on-sale (securitization)",
               amount=-gain_on_sale_deduction,
               regulatory_reference="12 CFR 217.22(a)(6)"),
        CC1Row(row_number=18, description="Investments in own shares",
               amount=-own_shares_deduction,
               regulatory_reference="12 CFR 217.22(a)(7)"),
        CC1Row(row_number=19, description="Reciprocal cross-holdings",
               amount=-cross_holdings_deduction,
               regulatory_reference="12 CFR 217.22(b)"),
        CC1Row(row_number=20,
               description="Significant investments in unconsolidated FIs",
               amount=-significant_inv_deduction,
               regulatory_reference="12 CFR 217.22(d)(1)(i)"),
        CC1Row(row_number=21, description="Mortgage servicing assets",
               amount=-msa_deduction,
               regulatory_reference="12 CFR 217.22(d)(1)(iii)"),
        CC1Row(row_number=25, description="Aggregate 15% threshold deduction",
               amount=-aggregate_threshold_deduction,
               regulatory_reference="12 CFR 217.22(d)(2)"),
        CC1Row(row_number=26, description="Other CET1 deductions",
               amount=-other_cet1_deductions,
               regulatory_reference="12 CFR 217.22"),
        CC1Row(row_number=28, description="Total CET1 regulatory adjustments",
               amount=-total_cet1_deductions,
               regulatory_reference="12 CFR 217.22"),
        CC1Row(row_number=29, description="CET1 capital",
               amount=net_cet1,
               regulatory_reference="12 CFR 217.20(b)"),
        # AT1
        CC1Row(row_number=30, description="AT1 instruments",
               amount=at1_instruments,
               regulatory_reference="12 CFR 217.20(c)"),
        CC1Row(row_number=34, description="AT1 minority interest",
               amount=at1_minority_interest,
               regulatory_reference="12 CFR 217.21(b)"),
        CC1Row(row_number=36, description="AT1 regulatory deductions",
               amount=-at1_deductions,
               regulatory_reference="12 CFR 217.22(b)"),
        CC1Row(row_number=44, description="AT1 capital",
               amount=net_at1,
               regulatory_reference="12 CFR 217.20(c)"),
        CC1Row(row_number=45, description="Tier 1 capital (CET1 + AT1)",
               amount=tier1,
               regulatory_reference="12 CFR 217.20"),
        # Tier 2
        CC1Row(row_number=46, description="Tier 2 instruments",
               amount=tier2_instruments,
               regulatory_reference="12 CFR 217.20(d)"),
        CC1Row(row_number=48, description="Tier 2 minority interest",
               amount=tier2_minority_interest,
               regulatory_reference="12 CFR 217.21(c)"),
        CC1Row(row_number=50, description="General allowance (capped at 1.25% SA-RWA)",
               amount=tier2_allowance,
               regulatory_reference="12 CFR 217.20(d)(3)"),
        CC1Row(row_number=52, description="Tier 2 regulatory deductions",
               amount=-tier2_deductions,
               regulatory_reference="12 CFR 217.22(c)"),
        CC1Row(row_number=58, description="Tier 2 capital",
               amount=net_tier2,
               regulatory_reference="12 CFR 217.20(d)"),
        CC1Row(row_number=59, description="Total capital (Tier 1 + Tier 2)",
               amount=total_capital,
               regulatory_reference="12 CFR 217.20"),
        CC1Row(row_number=60, description="Total risk-weighted assets",
               amount=total_rwa,
               regulatory_reference="12 CFR 217.10"),
    ]

    return Pillar3CC1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        cet1_capital=net_cet1,
        at1_capital=net_at1,
        tier1_capital=tier1,
        tier2_capital=net_tier2,
        total_capital=total_capital,
        total_rwa=total_rwa,
        cet1_ratio=cet1_r,
        tier1_ratio=tier1_r,
        total_capital_ratio=total_r,
    )


# =========================================================================
#  CC2: Reconciliation of Regulatory Capital to Balance Sheet
#  Reference: BCBS d455 Table CC2
# =========================================================================

class CC2Row(BaseModel):
    """A single row in the CC2 disclosure template.

    Reference: BCBS d455 Table CC2.
    """
    row_number: int = Field(description="Row number in CC2 template")
    description: str = Field(description="Balance sheet / capital item")
    balance_sheet_amount: float = Field(
        description="Amount per published financial statements in $M"
    )
    regulatory_capital_amount: float = Field(
        default=0.0,
        description="Amount recognized in regulatory capital in $M"
    )
    difference: float = Field(
        default=0.0,
        description="Difference between BS and regulatory amounts in $M"
    )


class Pillar3CC2(BaseModel):
    """Pillar 3 Template CC2: Reconciliation to Balance Sheet.

    Shows how accounting balance sheet items map to regulatory capital,
    highlighting differences caused by regulatory adjustments.

    Reference: BCBS d455 Table CC2.
    """
    template_id: str = Field(default="CC2")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[CC2Row] = Field(default_factory=list)

    total_assets_bs: float = Field(description="Total assets per BS in $M")
    total_liabilities_bs: float = Field(description="Total liabilities per BS in $M")
    shareholders_equity_bs: float = Field(
        description="Shareholders' equity per BS in $M"
    )
    regulatory_capital: float = Field(description="Total regulatory capital in $M")


def build_cc2(
    total_assets: float,
    total_liabilities: float,
    shareholders_equity: float,
    goodwill_intangibles: float = 0.0,
    dta_disallowed: float = 0.0,
    other_adjustments: float = 0.0,
    at1_instruments_bs: float = 0.0,
    tier2_instruments_bs: float = 0.0,
    total_regulatory_capital: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3CC2:
    """Build Pillar 3 CC2: Reconciliation to Balance Sheet.

    Args:
        total_assets: Total assets per balance sheet in $M.
        total_liabilities: Total liabilities per balance sheet in $M.
        shareholders_equity: Shareholders' equity per balance sheet in $M.
        goodwill_intangibles: Goodwill and intangibles deducted in $M.
        dta_disallowed: DTA amounts disallowed for reg cap in $M.
        other_adjustments: Other regulatory adjustments in $M.
        at1_instruments_bs: AT1 instruments per balance sheet in $M.
        tier2_instruments_bs: Tier 2 instruments per balance sheet in $M.
        total_regulatory_capital: Total regulatory capital in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3CC2 disclosure template.

    Reference: BCBS d455 Table CC2.
    """
    cet1_reg = shareholders_equity - goodwill_intangibles - dta_disallowed - other_adjustments

    rows: list[CC2Row] = [
        CC2Row(
            row_number=1,
            description="Total assets per published financial statements",
            balance_sheet_amount=total_assets,
            regulatory_capital_amount=0.0,
            difference=total_assets,
        ),
        CC2Row(
            row_number=2,
            description="Total liabilities per published financial statements",
            balance_sheet_amount=total_liabilities,
            regulatory_capital_amount=0.0,
            difference=total_liabilities,
        ),
        CC2Row(
            row_number=3,
            description="Shareholders' equity per published financial statements",
            balance_sheet_amount=shareholders_equity,
            regulatory_capital_amount=cet1_reg,
            difference=shareholders_equity - cet1_reg,
        ),
        CC2Row(
            row_number=4,
            description="Goodwill and other intangibles (deducted)",
            balance_sheet_amount=goodwill_intangibles,
            regulatory_capital_amount=0.0,
            difference=-goodwill_intangibles,
        ),
        CC2Row(
            row_number=5,
            description="Deferred tax assets (disallowed portion)",
            balance_sheet_amount=dta_disallowed,
            regulatory_capital_amount=0.0,
            difference=-dta_disallowed,
        ),
        CC2Row(
            row_number=6,
            description="Other regulatory adjustments",
            balance_sheet_amount=0.0,
            regulatory_capital_amount=-other_adjustments,
            difference=-other_adjustments,
        ),
        CC2Row(
            row_number=7,
            description="CET1 capital",
            balance_sheet_amount=shareholders_equity,
            regulatory_capital_amount=cet1_reg,
            difference=shareholders_equity - cet1_reg,
        ),
        CC2Row(
            row_number=8,
            description="Additional Tier 1 instruments",
            balance_sheet_amount=at1_instruments_bs,
            regulatory_capital_amount=at1_instruments_bs,
            difference=0.0,
        ),
        CC2Row(
            row_number=9,
            description="Tier 2 instruments",
            balance_sheet_amount=tier2_instruments_bs,
            regulatory_capital_amount=tier2_instruments_bs,
            difference=0.0,
        ),
        CC2Row(
            row_number=10,
            description="Total regulatory capital",
            balance_sheet_amount=shareholders_equity + at1_instruments_bs + tier2_instruments_bs,
            regulatory_capital_amount=total_regulatory_capital,
            difference=(
                shareholders_equity + at1_instruments_bs + tier2_instruments_bs
                - total_regulatory_capital
            ),
        ),
    ]

    return Pillar3CC2(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_assets_bs=total_assets,
        total_liabilities_bs=total_liabilities,
        shareholders_equity_bs=shareholders_equity,
        regulatory_capital=total_regulatory_capital,
    )
