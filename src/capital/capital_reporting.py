"""Capital reporting — FR Y-9C Schedule HC-R and FFIEC 101 Schedule A.

Generates regulatory reports for capital adequacy, mapping internal
calculation results to the specific line items required by:
- FR Y-9C Schedule HC-R Part I: Regulatory capital components (17 items)
- FR Y-9C Schedule HC-R Part II: Risk-weighted assets
- FFIEC 101 Schedule A: RWA by exposure type
- Pillar 3 disclosures: KM1, OV1, CC1, CC2

All amounts in USD millions ($M).

References:
- FR Y-9C reporting instructions (Schedule HC-R)
- FFIEC 101 reporting instructions (Schedule A)
- BCBS Pillar 3 disclosure requirements (d400/d455)
- ERBA NPR pp. 34-120: Capital adequacy framework
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_components import TotalCapitalResult, LeverageExposureInputs
from src.capital.capital_ratios import (
    CapitalAdequacyResult,
    CapitalRatios,
    BufferRequirements,
    PCACategory,
)
from src.capital.rwa_aggregator import RWABreakdown, FFIEC101ScheduleA


# =========================================================================
#  FR Y-9C Schedule HC-R Part I: Regulatory Capital Components
# =========================================================================

class HCRPartILineItem(BaseModel):
    """A single FR Y-9C Schedule HC-R Part I line item.

    Reference: FR Y-9C reporting instructions, Schedule HC-R.
    """
    line_number: str = Field(description="Line item number (e.g., '1', '2', '8a')")
    description: str = Field(description="Official line item description")
    amount: float = Field(description="Amount in $M (thousands on actual form)")
    regulatory_reference: str = Field(
        default="",
        description="12 CFR citation"
    )


class FRY9C_HCR_PartI(BaseModel):
    """FR Y-9C Schedule HC-R Part I: Regulatory Capital Components.

    Contains all 17 key line items for the regulatory capital components
    section of Schedule HC-R.

    Reference: FR Y-9C reporting instructions.
    """
    reporting_date: date = Field(description="As-of date for the report")
    entity_name: str = Field(default="", description="Reporting entity name")
    rssd_id: str = Field(default="", description="RSSD ID")

    # CET1 Components (Items 1-12)
    item_1_common_stock: HCRPartILineItem
    item_2_surplus: HCRPartILineItem
    item_3_retained_earnings: HCRPartILineItem
    item_4_aoci: HCRPartILineItem
    item_5_treasury_stock: HCRPartILineItem
    item_6_minority_interest_cet1: HCRPartILineItem
    item_7_gross_cet1: HCRPartILineItem
    item_8_goodwill: HCRPartILineItem
    item_9_other_intangibles: HCRPartILineItem
    item_10_dta_carryforward: HCRPartILineItem
    item_10a_other_deductions: HCRPartILineItem
    item_11_total_deductions: HCRPartILineItem
    item_12_cet1_capital: HCRPartILineItem

    # AT1 Components (Items 13-15)
    item_13_at1_instruments: HCRPartILineItem
    item_14_at1_minority_interest: HCRPartILineItem
    item_14a_at1_deductions: HCRPartILineItem
    item_15_at1_capital: HCRPartILineItem

    # Tier 1 (Item 15a)
    item_15a_tier1_capital: HCRPartILineItem

    # Tier 2 Components (Items 16-17)
    item_16a_tier2_instruments: HCRPartILineItem
    item_16b_general_allowance: HCRPartILineItem
    item_16c_tier2_minority_interest: HCRPartILineItem
    item_16d_tier2_deductions: HCRPartILineItem
    item_17_tier2_capital: HCRPartILineItem

    # Total Capital (Item 18)
    item_18_total_capital: HCRPartILineItem


class FRY9C_HCR_PartII(BaseModel):
    """FR Y-9C Schedule HC-R Part II: Risk-Weighted Assets.

    Reference: FR Y-9C reporting instructions.
    """
    reporting_date: date = Field(description="As-of date for the report")

    # RWA summary
    total_rwa: float = Field(description="Total risk-weighted assets")
    credit_risk_rwa: float = Field(description="Credit risk RWA")
    market_risk_rwa: float = Field(description="Market risk equivalent RWA")
    operational_risk_rwa: float = Field(description="Operational risk equivalent RWA")
    cva_risk_rwa: float = Field(description="CVA risk equivalent RWA")

    # Capital ratios
    cet1_ratio: float = Field(description="CET1 capital ratio")
    tier1_ratio: float = Field(description="Tier 1 capital ratio")
    total_capital_ratio: float = Field(description="Total capital ratio")
    leverage_ratio: float = Field(description="Supplementary Leverage Ratio")


# =========================================================================
#  Pillar 3 Disclosure Templates
# =========================================================================

class Pillar3_KM1(BaseModel):
    """Pillar 3 Template KM1: Key metrics.

    Presents key capital, leverage, and liquidity metrics at a glance.
    Reference: BCBS d455, Table KM1.
    """
    reporting_date: date

    # Available capital
    cet1_capital: float = Field(description="Row 1: CET1 capital")
    tier1_capital: float = Field(description="Row 2: Tier 1 capital")
    total_capital: float = Field(description="Row 3: Total capital")

    # RWA
    total_rwa: float = Field(description="Row 4: Total RWA")

    # Risk-based capital ratios
    cet1_ratio: float = Field(description="Row 5: CET1 ratio (%)")
    tier1_ratio: float = Field(description="Row 6: Tier 1 ratio (%)")
    total_capital_ratio: float = Field(description="Row 7: Total capital ratio (%)")

    # Additional CET1 buffers
    ccb: float = Field(description="Row 8: CCB requirement (%)")
    ccyb: float = Field(description="Row 9: CCyB requirement (%)")
    gsib_surcharge: float = Field(description="Row 10: G-SIB surcharge (%)")

    # CET1 available after meeting minimum requirements
    cet1_available_for_buffers: float = Field(
        description="Row 11: CET1 available to meet buffers (%)"
    )

    # Leverage ratio
    total_leverage_exposure: float = Field(
        default=0.0, description="Row 12: Total leverage exposure"
    )
    leverage_ratio: float = Field(
        default=0.0, description="Row 13: Leverage ratio (%)"
    )


class Pillar3_OV1(BaseModel):
    """Pillar 3 Template OV1: Overview of RWA.

    Provides a summary view of total RWA and minimum capital requirements.
    Reference: BCBS d455, Table OV1.
    """
    reporting_date: date

    # RWA and minimum capital
    credit_risk_rwa: float = Field(
        description="Row 1: Credit risk (SA)"
    )
    credit_risk_min_capital: float = Field(
        description="Row 1: Minimum capital for credit risk"
    )
    market_risk_rwa: float = Field(
        description="Row 6: Market risk (SA)"
    )
    market_risk_min_capital: float = Field(
        description="Row 6: Minimum capital for market risk"
    )
    operational_risk_rwa: float = Field(
        description="Row 10: Operational risk"
    )
    operational_risk_min_capital: float = Field(
        description="Row 10: Minimum capital for operational risk"
    )
    cva_risk_rwa: float = Field(
        description="Row 11: CVA risk"
    )
    cva_risk_min_capital: float = Field(
        description="Row 11: Minimum capital for CVA risk"
    )
    total_rwa: float = Field(
        description="Row 12: Total RWA"
    )
    total_min_capital: float = Field(
        description="Row 12: Total minimum capital"
    )


class Pillar3_CC1(BaseModel):
    """Pillar 3 Template CC1: Composition of regulatory capital.

    Detailed breakdown of CET1, AT1, and Tier 2 components.
    Reference: BCBS d455, Table CC1.
    """
    reporting_date: date

    # CET1
    common_stock_and_surplus: float = Field(
        description="Row 1: Common stock + surplus"
    )
    retained_earnings: float = Field(
        description="Row 2: Retained earnings"
    )
    aoci: float = Field(description="Row 3: AOCI")
    cet1_minority_interest: float = Field(
        description="Row 5: CET1 minority interest"
    )
    cet1_before_adjustments: float = Field(
        description="Row 6: CET1 before regulatory adjustments"
    )
    goodwill_deduction: float = Field(
        description="Row 8: Goodwill deduction"
    )
    other_intangibles_deduction: float = Field(
        description="Row 9: Other intangibles deduction"
    )
    dta_deduction: float = Field(
        description="Row 10: DTA deduction"
    )
    other_cet1_deductions: float = Field(
        description="Row 26: Other CET1 deductions"
    )
    total_cet1_deductions: float = Field(
        description="Row 28: Total CET1 regulatory adjustments"
    )
    cet1_capital: float = Field(
        description="Row 29: CET1 capital"
    )

    # AT1
    at1_instruments: float = Field(
        description="Row 30: AT1 instruments"
    )
    at1_minority_interest: float = Field(
        description="Row 34: AT1 minority interest"
    )
    at1_deductions: float = Field(
        description="Row 36: AT1 deductions"
    )
    at1_capital: float = Field(
        description="Row 44: AT1 capital"
    )
    tier1_capital: float = Field(
        description="Row 45: Tier 1 capital (CET1 + AT1)"
    )

    # Tier 2
    tier2_instruments: float = Field(
        description="Row 46: Tier 2 instruments"
    )
    tier2_allowance: float = Field(
        description="Row 50: General allowance"
    )
    tier2_minority_interest: float = Field(
        description="Row 48: Tier 2 minority interest"
    )
    tier2_deductions: float = Field(
        description="Row 52: Tier 2 deductions"
    )
    tier2_capital: float = Field(
        description="Row 58: Tier 2 capital"
    )
    total_capital: float = Field(
        description="Row 59: Total capital (Tier 1 + Tier 2)"
    )
    total_rwa: float = Field(
        description="Row 60: Total RWA"
    )


# =========================================================================
#  Capital Adequacy Summary
# =========================================================================

class CapitalAdequacySummary(BaseModel):
    """Executive summary of capital adequacy position.

    Provides a concise overview suitable for board reporting, regulatory
    submissions, and investor relations.

    Reference: Pillar 3 KM1, FR Y-9C Schedule HC-R.
    """
    reporting_date: date
    entity_name: str = Field(default="")

    # Capital amounts ($M)
    cet1_capital: float
    at1_capital: float
    tier1_capital: float
    tier2_capital: float
    total_capital: float

    # RWA ($M)
    total_rwa: float
    credit_risk_rwa: float
    market_risk_rwa: float
    operational_risk_rwa: float
    cva_risk_rwa: float

    # Ratios (%)
    cet1_ratio_pct: float = Field(description="CET1 ratio as percentage")
    tier1_ratio_pct: float = Field(description="Tier 1 ratio as percentage")
    total_capital_ratio_pct: float = Field(description="Total capital ratio as %")
    slr_pct: float = Field(default=0.0, description="SLR as percentage")

    # Buffer analysis
    combined_buffer_pct: float = Field(description="Combined buffer requirement %")
    cet1_surplus_over_buffer_pct: float = Field(
        description="CET1 surplus over effective minimum %"
    )

    # PCA
    pca_category: str = Field(description="PCA classification")
    is_well_capitalized: bool

    # G-SIB
    gsib_surcharge_pct: float = Field(default=0.0)

    # Key flags
    meets_all_minimums: bool
    meets_all_buffers: bool
    distribution_restricted: bool = Field(
        description="True if capital distributions are restricted"
    )


# =========================================================================
#  Report Generation Functions
# =========================================================================

def build_hcr_part_i(
    capital: TotalCapitalResult,
    reporting_date: date,
    entity_name: str = "",
    rssd_id: str = "",
) -> FRY9C_HCR_PartI:
    """Build FR Y-9C Schedule HC-R Part I from capital components.

    Maps internal capital calculation results to the 17+ line items
    required by Schedule HC-R Part I of the FR Y-9C.

    Args:
        capital: Total capital result from capital_components module.
        reporting_date: As-of date for the report.
        entity_name: Reporting entity name.
        rssd_id: RSSD identifier.

    Returns:
        FRY9C_HCR_PartI with all line items populated.

    Reference: FR Y-9C reporting instructions, Schedule HC-R.
    """
    cet1 = capital.cet1
    at1 = capital.at1
    tier2 = capital.tier2

    return FRY9C_HCR_PartI(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rssd_id=rssd_id,
        item_1_common_stock=HCRPartILineItem(
            line_number="1",
            description="Common stock",
            amount=cet1.common_stock,
            regulatory_reference="12 CFR 217.20(b)(1)",
        ),
        item_2_surplus=HCRPartILineItem(
            line_number="2",
            description="Surplus (related to common stock)",
            amount=cet1.surplus,
            regulatory_reference="12 CFR 217.20(b)(1)",
        ),
        item_3_retained_earnings=HCRPartILineItem(
            line_number="3",
            description="Retained earnings",
            amount=cet1.retained_earnings,
            regulatory_reference="12 CFR 217.20(b)(1)",
        ),
        item_4_aoci=HCRPartILineItem(
            line_number="4",
            description="Accumulated other comprehensive income (AOCI)",
            amount=cet1.aoci,
            regulatory_reference="12 CFR 217.20(b)(2)",
        ),
        item_5_treasury_stock=HCRPartILineItem(
            line_number="5",
            description="Treasury stock",
            amount=cet1.treasury_stock,
            regulatory_reference="12 CFR 217.20(b)",
        ),
        item_6_minority_interest_cet1=HCRPartILineItem(
            line_number="6",
            description="Qualifying minority interest in CET1",
            amount=cet1.minority_interest,
            regulatory_reference="12 CFR 217.21(a)",
        ),
        item_7_gross_cet1=HCRPartILineItem(
            line_number="7",
            description="CET1 capital before deductions",
            amount=cet1.gross_cet1,
            regulatory_reference="12 CFR 217.20(b)",
        ),
        item_8_goodwill=HCRPartILineItem(
            line_number="8",
            description="Goodwill, net of associated DTL",
            amount=cet1.goodwill_deduction,
            regulatory_reference="12 CFR 217.22(a)(1)",
        ),
        item_9_other_intangibles=HCRPartILineItem(
            line_number="9",
            description="Other intangible assets, net of associated DTL",
            amount=cet1.other_intangibles_deduction,
            regulatory_reference="12 CFR 217.22(a)(2)",
        ),
        item_10_dta_carryforward=HCRPartILineItem(
            line_number="10",
            description="DTAs from NOL/tax credit carryforwards",
            amount=cet1.dta_carryforward_deduction,
            regulatory_reference="12 CFR 217.22(a)(3)",
        ),
        item_10a_other_deductions=HCRPartILineItem(
            line_number="10a",
            description="Other CET1 deductions (pension, gain-on-sale, "
                        "own shares, cross-holdings, threshold items)",
            amount=(
                cet1.defined_benefit_pension_deduction
                + cet1.gain_on_sale_deduction
                + cet1.investments_own_shares_deduction
                + cet1.reciprocal_cross_holdings_deduction
                + cet1.significant_investments_deduction
                + cet1.msa_deduction
                + cet1.dta_timing_deduction
                + cet1.aggregate_threshold_deduction
                + cet1.other_deductions
            ),
            regulatory_reference="12 CFR 217.22(a)-(d)",
        ),
        item_11_total_deductions=HCRPartILineItem(
            line_number="11",
            description="Total CET1 deductions",
            amount=cet1.total_deductions,
            regulatory_reference="12 CFR 217.22",
        ),
        item_12_cet1_capital=HCRPartILineItem(
            line_number="12",
            description="CET1 capital",
            amount=cet1.net_cet1,
            regulatory_reference="12 CFR 217.20(b)",
        ),
        item_13_at1_instruments=HCRPartILineItem(
            line_number="13",
            description="Qualifying AT1 instruments",
            amount=at1.qualifying_instruments,
            regulatory_reference="12 CFR 217.20(c)",
        ),
        item_14_at1_minority_interest=HCRPartILineItem(
            line_number="14",
            description="Qualifying AT1 minority interest",
            amount=at1.minority_interest_at1,
            regulatory_reference="12 CFR 217.21(b)",
        ),
        item_14a_at1_deductions=HCRPartILineItem(
            line_number="14a",
            description="AT1 regulatory deductions",
            amount=at1.at1_deductions,
            regulatory_reference="12 CFR 217.22(b)",
        ),
        item_15_at1_capital=HCRPartILineItem(
            line_number="15",
            description="Additional Tier 1 capital",
            amount=at1.net_at1,
            regulatory_reference="12 CFR 217.20(c)",
        ),
        item_15a_tier1_capital=HCRPartILineItem(
            line_number="15a",
            description="Tier 1 capital (CET1 + AT1)",
            amount=capital.tier1_capital,
            regulatory_reference="12 CFR 217.20",
        ),
        item_16a_tier2_instruments=HCRPartILineItem(
            line_number="16a",
            description="Qualifying Tier 2 instruments",
            amount=tier2.qualifying_instruments,
            regulatory_reference="12 CFR 217.20(d)",
        ),
        item_16b_general_allowance=HCRPartILineItem(
            line_number="16b",
            description="Eligible portion of ALLL/ACL (capped at 1.25% SA-RWA)",
            amount=tier2.general_allowance,
            regulatory_reference="12 CFR 217.20(d)(3)",
        ),
        item_16c_tier2_minority_interest=HCRPartILineItem(
            line_number="16c",
            description="Qualifying Tier 2 minority interest",
            amount=tier2.minority_interest_tier2,
            regulatory_reference="12 CFR 217.21(c)",
        ),
        item_16d_tier2_deductions=HCRPartILineItem(
            line_number="16d",
            description="Tier 2 regulatory deductions",
            amount=tier2.tier2_deductions,
            regulatory_reference="12 CFR 217.22(c)",
        ),
        item_17_tier2_capital=HCRPartILineItem(
            line_number="17",
            description="Tier 2 capital",
            amount=tier2.net_tier2,
            regulatory_reference="12 CFR 217.20(d)",
        ),
        item_18_total_capital=HCRPartILineItem(
            line_number="18",
            description="Total capital (Tier 1 + Tier 2)",
            amount=capital.total_capital,
            regulatory_reference="12 CFR 217.20",
        ),
    )


def build_hcr_part_ii(
    adequacy: CapitalAdequacyResult,
    reporting_date: date,
) -> FRY9C_HCR_PartII:
    """Build FR Y-9C Schedule HC-R Part II from capital adequacy result.

    Args:
        adequacy: Capital adequacy result from capital_ratios module.
        reporting_date: As-of date for the report.

    Returns:
        FRY9C_HCR_PartII with RWA and ratio line items.

    Reference: FR Y-9C reporting instructions, Schedule HC-R Part II.
    """
    return FRY9C_HCR_PartII(
        reporting_date=reporting_date,
        total_rwa=adequacy.total_rwa,
        credit_risk_rwa=adequacy.ratios.cet1_ratio * adequacy.total_rwa
        if adequacy.total_rwa > 0 else 0.0,  # Placeholder — use breakdown
        market_risk_rwa=0.0,  # From RWA breakdown
        operational_risk_rwa=0.0,
        cva_risk_rwa=0.0,
        cet1_ratio=adequacy.ratios.cet1_ratio,
        tier1_ratio=adequacy.ratios.tier1_ratio,
        total_capital_ratio=adequacy.ratios.total_capital_ratio,
        leverage_ratio=adequacy.ratios.leverage_ratio,
    )


def build_hcr_part_ii_from_breakdown(
    adequacy: CapitalAdequacyResult,
    rwa_breakdown: RWABreakdown,
    reporting_date: date,
) -> FRY9C_HCR_PartII:
    """Build FR Y-9C Schedule HC-R Part II with full RWA breakdown.

    Args:
        adequacy: Capital adequacy result.
        rwa_breakdown: Detailed RWA breakdown by risk type.
        reporting_date: As-of date.

    Returns:
        FRY9C_HCR_PartII with all RWA components and ratios.

    Reference: FR Y-9C reporting instructions, Schedule HC-R Part II.
    """
    return FRY9C_HCR_PartII(
        reporting_date=reporting_date,
        total_rwa=rwa_breakdown.total_rwa,
        credit_risk_rwa=rwa_breakdown.credit_risk_rwa,
        market_risk_rwa=rwa_breakdown.market_risk_rwa,
        operational_risk_rwa=rwa_breakdown.operational_risk_rwa,
        cva_risk_rwa=rwa_breakdown.cva_risk_rwa,
        cet1_ratio=adequacy.ratios.cet1_ratio,
        tier1_ratio=adequacy.ratios.tier1_ratio,
        total_capital_ratio=adequacy.ratios.total_capital_ratio,
        leverage_ratio=adequacy.ratios.leverage_ratio,
    )


def build_pillar3_km1(
    adequacy: CapitalAdequacyResult,
    reporting_date: date,
) -> Pillar3_KM1:
    """Build Pillar 3 Template KM1: Key Metrics.

    Args:
        adequacy: Capital adequacy result.
        reporting_date: As-of date.

    Returns:
        Pillar3_KM1 with key capital, leverage, and ratio metrics.

    Reference: BCBS d455, Table KM1.
    """
    # CET1 available for buffers = CET1 ratio - max(CET1 min, T1 min - AT1, TC min - AT1 - T2)
    # Simplified: CET1 ratio - 4.5%
    cet1_available = max(0.0, adequacy.ratios.cet1_ratio - 0.045)

    return Pillar3_KM1(
        reporting_date=reporting_date,
        cet1_capital=adequacy.cet1_capital,
        tier1_capital=adequacy.tier1_capital,
        total_capital=adequacy.total_capital,
        total_rwa=adequacy.total_rwa,
        cet1_ratio=adequacy.ratios.cet1_ratio,
        tier1_ratio=adequacy.ratios.tier1_ratio,
        total_capital_ratio=adequacy.ratios.total_capital_ratio,
        ccb=adequacy.buffers.capital_conservation_buffer,
        ccyb=adequacy.buffers.countercyclical_buffer,
        gsib_surcharge=adequacy.buffers.gsib_surcharge,
        cet1_available_for_buffers=cet1_available,
        total_leverage_exposure=adequacy.total_leverage_exposure,
        leverage_ratio=adequacy.ratios.leverage_ratio,
    )


def build_pillar3_ov1(
    rwa_breakdown: RWABreakdown,
    reporting_date: date,
) -> Pillar3_OV1:
    """Build Pillar 3 Template OV1: Overview of RWA.

    Minimum capital = 8% of RWA for each risk type.

    Args:
        rwa_breakdown: Aggregated RWA breakdown.
        reporting_date: As-of date.

    Returns:
        Pillar3_OV1 with RWA and minimum capital by risk type.

    Reference: BCBS d455, Table OV1.
    """
    min_cap_rate = 0.08  # 8% minimum capital ratio

    return Pillar3_OV1(
        reporting_date=reporting_date,
        credit_risk_rwa=rwa_breakdown.credit_risk_rwa,
        credit_risk_min_capital=rwa_breakdown.credit_risk_rwa * min_cap_rate,
        market_risk_rwa=rwa_breakdown.market_risk_rwa,
        market_risk_min_capital=rwa_breakdown.market_risk_rwa * min_cap_rate,
        operational_risk_rwa=rwa_breakdown.operational_risk_rwa,
        operational_risk_min_capital=rwa_breakdown.operational_risk_rwa * min_cap_rate,
        cva_risk_rwa=rwa_breakdown.cva_risk_rwa,
        cva_risk_min_capital=rwa_breakdown.cva_risk_rwa * min_cap_rate,
        total_rwa=rwa_breakdown.total_rwa,
        total_min_capital=rwa_breakdown.total_rwa * min_cap_rate,
    )


def build_pillar3_cc1(
    capital: TotalCapitalResult,
    total_rwa: float,
    reporting_date: date,
) -> Pillar3_CC1:
    """Build Pillar 3 Template CC1: Composition of Regulatory Capital.

    Args:
        capital: Total capital result.
        total_rwa: Total risk-weighted assets.
        reporting_date: As-of date.

    Returns:
        Pillar3_CC1 with detailed capital composition.

    Reference: BCBS d455, Table CC1.
    """
    cet1 = capital.cet1
    at1 = capital.at1
    tier2 = capital.tier2

    return Pillar3_CC1(
        reporting_date=reporting_date,
        common_stock_and_surplus=cet1.common_stock + cet1.surplus,
        retained_earnings=cet1.retained_earnings,
        aoci=cet1.aoci,
        cet1_minority_interest=cet1.minority_interest,
        cet1_before_adjustments=cet1.gross_cet1,
        goodwill_deduction=cet1.goodwill_deduction,
        other_intangibles_deduction=cet1.other_intangibles_deduction,
        dta_deduction=cet1.dta_carryforward_deduction + cet1.dta_timing_deduction,
        other_cet1_deductions=(
            cet1.defined_benefit_pension_deduction
            + cet1.gain_on_sale_deduction
            + cet1.investments_own_shares_deduction
            + cet1.reciprocal_cross_holdings_deduction
            + cet1.significant_investments_deduction
            + cet1.msa_deduction
            + cet1.aggregate_threshold_deduction
            + cet1.other_deductions
        ),
        total_cet1_deductions=cet1.total_deductions,
        cet1_capital=cet1.net_cet1,
        at1_instruments=at1.qualifying_instruments,
        at1_minority_interest=at1.minority_interest_at1,
        at1_deductions=at1.at1_deductions,
        at1_capital=at1.net_at1,
        tier1_capital=capital.tier1_capital,
        tier2_instruments=tier2.qualifying_instruments,
        tier2_allowance=tier2.general_allowance,
        tier2_minority_interest=tier2.minority_interest_tier2,
        tier2_deductions=tier2.tier2_deductions,
        tier2_capital=tier2.net_tier2,
        total_capital=capital.total_capital,
        total_rwa=total_rwa,
    )


def build_capital_adequacy_summary(
    adequacy: CapitalAdequacyResult,
    rwa_breakdown: RWABreakdown,
    reporting_date: date,
    entity_name: str = "",
) -> CapitalAdequacySummary:
    """Build executive capital adequacy summary.

    Generates a concise summary suitable for board reporting,
    regulatory submissions, and investor relations.

    Args:
        adequacy: Complete capital adequacy assessment.
        rwa_breakdown: Detailed RWA breakdown.
        reporting_date: As-of date.
        entity_name: Reporting entity name.

    Returns:
        CapitalAdequacySummary with key metrics.

    Reference: Pillar 3 KM1, FR Y-9C Schedule HC-R.
    """
    sd = adequacy.surplus_deficit

    return CapitalAdequacySummary(
        reporting_date=reporting_date,
        entity_name=entity_name,
        cet1_capital=adequacy.cet1_capital,
        at1_capital=adequacy.tier1_capital - adequacy.cet1_capital,
        tier1_capital=adequacy.tier1_capital,
        tier2_capital=adequacy.total_capital - adequacy.tier1_capital,
        total_capital=adequacy.total_capital,
        total_rwa=adequacy.total_rwa,
        credit_risk_rwa=rwa_breakdown.credit_risk_rwa,
        market_risk_rwa=rwa_breakdown.market_risk_rwa,
        operational_risk_rwa=rwa_breakdown.operational_risk_rwa,
        cva_risk_rwa=rwa_breakdown.cva_risk_rwa,
        cet1_ratio_pct=adequacy.ratios.cet1_ratio * 100,
        tier1_ratio_pct=adequacy.ratios.tier1_ratio * 100,
        total_capital_ratio_pct=adequacy.ratios.total_capital_ratio * 100,
        slr_pct=adequacy.ratios.leverage_ratio * 100,
        combined_buffer_pct=adequacy.buffers.combined_buffer_requirement * 100,
        cet1_surplus_over_buffer_pct=sd.cet1_ratio_surplus * 100,
        pca_category=adequacy.pca.category.value,
        is_well_capitalized=adequacy.is_well_capitalized,
        gsib_surcharge_pct=adequacy.buffers.gsib_surcharge * 100,
        meets_all_minimums=adequacy.meets_minimum_requirements,
        meets_all_buffers=adequacy.meets_buffer_requirements,
        distribution_restricted=(
            sd.buffer_zone not in {
                "ABOVE_BUFFER",
            }
            and sd.buffer_zone.value != "ABOVE_BUFFER"
            if hasattr(sd.buffer_zone, 'value')
            else True
        ),
    )
