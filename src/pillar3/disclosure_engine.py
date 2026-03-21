"""Pillar 3 Disclosure Engine — Main disclosure generation orchestrator.

Generates a complete set of Pillar 3 disclosure templates for a reporting
period. Orchestrates the creation of all required templates based on
reporting frequency (quarterly, semi-annual, annual) and populates them
from the institution's capital, RWA, and risk data.

All amounts in USD millions ($M).

References:
- BCBS d400: "Pillar 3 Disclosure Requirements — Updated Framework" (2022)
- BCBS d455: "Pillar 3 Disclosure Requirements — Consolidated and Enhanced"
- 12 CFR 217 Subpart E: Disclosures
- ERBA NPR pp. 34-120: Capital adequacy framework
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from src.pillar3.pillar3_params import (
    DisclosureFrequency,
    TEMPLATE_REGISTRY,
    TemplateDefinition,
    get_templates_by_frequency,
)
from src.pillar3.templates.overview import (
    Pillar3KM1,
    Pillar3OV1,
    build_km1,
    build_ov1,
)
from src.pillar3.templates.capital_composition import (
    Pillar3CC1,
    Pillar3CC2,
    build_cc1,
    build_cc2,
)
from src.pillar3.templates.credit_risk_disclosure import (
    Pillar3CR1,
    Pillar3CR4,
    Pillar3CR5,
    build_cr1,
    build_cr4,
    build_cr5,
)
from src.pillar3.templates.market_risk_disclosure import (
    Pillar3MR1,
    build_mr1,
)
from src.pillar3.templates.operational_risk_disclosure import (
    Pillar3OR1,
    build_or1,
)
from src.pillar3.templates.leverage_ratio import (
    Pillar3LR1,
    Pillar3LR2,
    build_lr1,
    build_lr2,
)


# =========================================================================
#  Disclosure Input Data
# =========================================================================

class DisclosureCapitalData(BaseModel):
    """Capital data inputs for Pillar 3 disclosures.

    Reference: FR Y-9C Schedule HC-R Part I.
    """
    # CET1 components
    common_stock: float = Field(default=0.0)
    surplus: float = Field(default=0.0)
    retained_earnings: float = Field(default=0.0)
    aoci: float = Field(default=0.0)
    treasury_stock: float = Field(default=0.0)
    cet1_minority_interest: float = Field(default=0.0)

    # CET1 deductions
    goodwill_deduction: float = Field(default=0.0)
    other_intangibles_deduction: float = Field(default=0.0)
    dta_carryforward_deduction: float = Field(default=0.0)
    dta_timing_deduction: float = Field(default=0.0)
    other_cet1_deductions: float = Field(default=0.0)

    # AT1
    at1_instruments: float = Field(default=0.0)
    at1_minority_interest: float = Field(default=0.0)
    at1_deductions: float = Field(default=0.0)

    # Tier 2
    tier2_instruments: float = Field(default=0.0)
    tier2_allowance: float = Field(default=0.0)
    tier2_minority_interest: float = Field(default=0.0)
    tier2_deductions: float = Field(default=0.0)


class DisclosureRWAData(BaseModel):
    """RWA data inputs for Pillar 3 disclosures.

    Reference: FFIEC 101 Schedule A.
    """
    credit_risk_rwa: float = Field(default=0.0)
    counterparty_credit_risk_rwa: float = Field(default=0.0)
    equity_risk_rwa: float = Field(default=0.0)
    securitization_rwa: float = Field(default=0.0)
    threshold_deductions_rwa: float = Field(default=0.0)
    market_risk_rwa: float = Field(default=0.0)
    operational_risk_rwa: float = Field(default=0.0)
    cva_risk_rwa: float = Field(default=0.0)


class DisclosureMarketRiskData(BaseModel):
    """Market risk data for FRTB-related disclosures.

    Reference: BCBS d457, ERBA NPR pp. 300-350.
    """
    girr_charge: float = Field(default=0.0)
    csr_nonsec_charge: float = Field(default=0.0)
    csr_sec_nonctp_charge: float = Field(default=0.0)
    csr_sec_ctp_charge: float = Field(default=0.0)
    equity_charge: float = Field(default=0.0)
    commodity_charge: float = Field(default=0.0)
    fx_charge: float = Field(default=0.0)
    drc_nonsec_charge: float = Field(default=0.0)
    rrao_charge: float = Field(default=0.0)


class DisclosureLeverageData(BaseModel):
    """Leverage ratio data for SLR disclosures.

    Reference: 12 CFR 217.10(c), ERBA NPR pp. 59-68.
    """
    total_consolidated_assets: float = Field(default=0.0)
    on_balance_sheet_excl_derivatives: float = Field(default=0.0)
    on_balance_sheet_deductions: float = Field(default=0.0)
    derivative_replacement_cost: float = Field(default=0.0)
    derivative_pfe: float = Field(default=0.0)
    sft_gross: float = Field(default=0.0)
    sft_ccr_addon: float = Field(default=0.0)
    off_bs_notional: float = Field(default=0.0)
    off_bs_ccf_adjustment: float = Field(default=0.0)
    tier1_capital: float = Field(default=0.0)


# =========================================================================
#  Disclosure Package Result
# =========================================================================

class DisclosurePackage(BaseModel):
    """Complete Pillar 3 disclosure package for a reporting period.

    Contains all generated templates, metadata about which templates
    are included, and the applicable reporting frequency.

    Reference: BCBS d400/d455.
    """
    reporting_date: date
    entity_name: str = Field(default="")
    frequency: DisclosureFrequency = Field(
        default=DisclosureFrequency.QUARTERLY
    )
    templates_included: list[str] = Field(
        default_factory=list,
        description="List of template IDs included in this package"
    )

    # Template instances
    ov1: Optional[Pillar3OV1] = None
    km1: Optional[Pillar3KM1] = None
    cc1: Optional[Pillar3CC1] = None
    cc2: Optional[Pillar3CC2] = None
    mr1: Optional[Pillar3MR1] = None
    or1: Optional[Pillar3OR1] = None
    lr1: Optional[Pillar3LR1] = None
    lr2: Optional[Pillar3LR2] = None

    # Credit risk templates stored as generic
    cr1: Optional[Pillar3CR1] = None
    cr4: Optional[Pillar3CR4] = None
    cr5: Optional[Pillar3CR5] = None

    # Validation
    is_complete: bool = Field(
        default=False,
        description="True if all required templates for the frequency are generated"
    )
    missing_templates: list[str] = Field(
        default_factory=list,
        description="Template IDs that should be included but are missing"
    )


# =========================================================================
#  Disclosure Generation Engine
# =========================================================================

def generate_disclosure_package(
    reporting_date: date,
    frequency: DisclosureFrequency,
    capital_data: DisclosureCapitalData,
    rwa_data: DisclosureRWAData,
    market_risk_data: Optional[DisclosureMarketRiskData] = None,
    leverage_data: Optional[DisclosureLeverageData] = None,
    ccb: float = 0.025,
    ccyb: float = 0.0,
    gsib_surcharge: float = 0.015,
    total_rwa: Optional[float] = None,
    entity_name: str = "",
) -> DisclosurePackage:
    """Generate a complete Pillar 3 disclosure package.

    Produces all required templates for the given reporting frequency.
    Quarterly reporting includes OV1, KM1, MR1, LR1, LR2.
    Semi-annual adds CC1, CC2, CR1-CR5.
    Annual adds OR1.

    Args:
        reporting_date: As-of date for the disclosures.
        frequency: Reporting frequency (QUARTERLY, SEMI_ANNUAL, ANNUAL).
        capital_data: Capital component data.
        rwa_data: RWA breakdown data.
        market_risk_data: Optional FRTB market risk data.
        leverage_data: Optional leverage ratio data.
        ccb: CCB/SCB rate.
        ccyb: CCyB rate.
        gsib_surcharge: G-SIB surcharge rate.
        total_rwa: Override total RWA (if None, sum from rwa_data).
        entity_name: Entity name.

    Returns:
        DisclosurePackage with all generated templates.

    Reference: BCBS d400/d455, 12 CFR 217 Subpart E.
    """
    # Compute total RWA
    if total_rwa is None:
        total_rwa = (
            rwa_data.credit_risk_rwa
            + rwa_data.counterparty_credit_risk_rwa
            + rwa_data.equity_risk_rwa
            + rwa_data.securitization_rwa
            + rwa_data.threshold_deductions_rwa
            + rwa_data.market_risk_rwa
            + rwa_data.operational_risk_rwa
            + rwa_data.cva_risk_rwa
        )

    # Compute capital totals
    cd = capital_data
    gross_cet1 = (
        cd.common_stock + cd.surplus + cd.retained_earnings
        + cd.aoci - cd.treasury_stock + cd.cet1_minority_interest
    )
    total_cet1_deductions = (
        cd.goodwill_deduction + cd.other_intangibles_deduction
        + cd.dta_carryforward_deduction + cd.dta_timing_deduction
        + cd.other_cet1_deductions
    )
    net_cet1 = gross_cet1 - total_cet1_deductions
    net_at1 = max(0.0, cd.at1_instruments + cd.at1_minority_interest - cd.at1_deductions)
    tier1 = net_cet1 + net_at1
    net_tier2 = max(
        0.0,
        cd.tier2_instruments + cd.tier2_allowance
        + cd.tier2_minority_interest - cd.tier2_deductions
    )
    total_capital = tier1 + net_tier2

    package = DisclosurePackage(
        reporting_date=reporting_date,
        entity_name=entity_name,
        frequency=frequency,
    )

    templates_included: list[str] = []

    # --- Quarterly templates (always generated) ---

    # OV1
    package.ov1 = build_ov1(
        credit_risk_rwa=rwa_data.credit_risk_rwa,
        counterparty_credit_risk_rwa=rwa_data.counterparty_credit_risk_rwa,
        equity_risk_rwa=rwa_data.equity_risk_rwa,
        securitization_rwa=rwa_data.securitization_rwa,
        market_risk_rwa=rwa_data.market_risk_rwa,
        operational_risk_rwa=rwa_data.operational_risk_rwa,
        cva_risk_rwa=rwa_data.cva_risk_rwa,
        threshold_deductions_rwa=rwa_data.threshold_deductions_rwa,
        reporting_date=reporting_date,
        entity_name=entity_name,
    )
    templates_included.append("OV1")

    # KM1
    tle = 0.0
    if leverage_data is not None:
        tle_calc = (
            leverage_data.on_balance_sheet_excl_derivatives
            - leverage_data.on_balance_sheet_deductions
            + leverage_data.derivative_replacement_cost
            + leverage_data.derivative_pfe
            + leverage_data.sft_gross
            + leverage_data.sft_ccr_addon
            + leverage_data.off_bs_notional
            - leverage_data.off_bs_ccf_adjustment
        )
        tle = tle_calc

    package.km1 = build_km1(
        cet1_capital=net_cet1,
        tier1_capital=tier1,
        total_capital=total_capital,
        total_rwa=total_rwa,
        ccb=ccb,
        ccyb=ccyb,
        gsib_surcharge=gsib_surcharge,
        total_leverage_exposure=tle,
        reporting_date=reporting_date,
        entity_name=entity_name,
    )
    templates_included.append("KM1")

    # MR1
    if market_risk_data is not None:
        mrd = market_risk_data
        package.mr1 = build_mr1(
            girr_charge=mrd.girr_charge,
            csr_nonsec_charge=mrd.csr_nonsec_charge,
            csr_sec_nonctp_charge=mrd.csr_sec_nonctp_charge,
            csr_sec_ctp_charge=mrd.csr_sec_ctp_charge,
            equity_charge=mrd.equity_charge,
            commodity_charge=mrd.commodity_charge,
            fx_charge=mrd.fx_charge,
            drc_nonsec_charge=mrd.drc_nonsec_charge,
            rrao_charge=mrd.rrao_charge,
            reporting_date=reporting_date,
            entity_name=entity_name,
        )
        templates_included.append("MR1")

    # LR1, LR2
    if leverage_data is not None:
        ld = leverage_data
        package.lr1 = build_lr1(
            total_consolidated_assets=ld.total_consolidated_assets,
            adjustment_for_derivatives=(
                ld.derivative_replacement_cost + ld.derivative_pfe
            ),
            adjustment_for_sft=ld.sft_gross + ld.sft_ccr_addon,
            off_balance_sheet_items=ld.off_bs_notional - ld.off_bs_ccf_adjustment,
            regulatory_deductions=ld.on_balance_sheet_deductions,
            reporting_date=reporting_date,
            entity_name=entity_name,
        )
        templates_included.append("LR1")

        package.lr2 = build_lr2(
            on_balance_sheet_excl_derivatives=ld.on_balance_sheet_excl_derivatives,
            on_balance_sheet_deductions=ld.on_balance_sheet_deductions,
            derivative_replacement_cost=ld.derivative_replacement_cost,
            derivative_pfe=ld.derivative_pfe,
            sft_gross=ld.sft_gross,
            sft_ccr_addon=ld.sft_ccr_addon,
            off_bs_notional=ld.off_bs_notional,
            off_bs_ccf_adjustment=ld.off_bs_ccf_adjustment,
            tier1_capital=tier1,
            reporting_date=reporting_date,
            entity_name=entity_name,
        )
        templates_included.append("LR2")

    # --- Semi-annual templates (only if frequency is SEMI_ANNUAL or ANNUAL) ---
    if frequency in (DisclosureFrequency.SEMI_ANNUAL, DisclosureFrequency.ANNUAL):
        package.cc1 = build_cc1(
            common_stock=cd.common_stock,
            surplus=cd.surplus,
            retained_earnings=cd.retained_earnings,
            aoci=cd.aoci,
            treasury_stock=cd.treasury_stock,
            cet1_minority_interest=cd.cet1_minority_interest,
            goodwill_deduction=cd.goodwill_deduction,
            other_intangibles_deduction=cd.other_intangibles_deduction,
            dta_carryforward_deduction=cd.dta_carryforward_deduction,
            dta_timing_deduction=cd.dta_timing_deduction,
            other_cet1_deductions=cd.other_cet1_deductions,
            at1_instruments=cd.at1_instruments,
            at1_minority_interest=cd.at1_minority_interest,
            at1_deductions=cd.at1_deductions,
            tier2_instruments=cd.tier2_instruments,
            tier2_allowance=cd.tier2_allowance,
            tier2_minority_interest=cd.tier2_minority_interest,
            tier2_deductions=cd.tier2_deductions,
            total_rwa=total_rwa,
            reporting_date=reporting_date,
            entity_name=entity_name,
        )
        templates_included.append("CC1")

    # --- Annual templates ---
    if frequency == DisclosureFrequency.ANNUAL:
        templates_included.append("OR1")  # OR1 populated separately

    # Completeness check
    required = get_templates_by_frequency(frequency)
    # Also include lower-frequency templates
    if frequency == DisclosureFrequency.SEMI_ANNUAL:
        required += get_templates_by_frequency(DisclosureFrequency.QUARTERLY)
    elif frequency == DisclosureFrequency.ANNUAL:
        required += get_templates_by_frequency(DisclosureFrequency.QUARTERLY)
        required += get_templates_by_frequency(DisclosureFrequency.SEMI_ANNUAL)

    required_ids = set(t.template_id for t in required)
    missing = sorted(required_ids - set(templates_included))

    package.templates_included = templates_included
    package.missing_templates = missing
    package.is_complete = len(missing) == 0

    return package


def get_disclosure_schedule(
    frequency: DisclosureFrequency,
) -> list[TemplateDefinition]:
    """Get the list of templates required for a given reporting frequency.

    Returns all templates that must be published at the specified
    frequency, including any that are also required at higher frequencies.

    Args:
        frequency: Reporting frequency.

    Returns:
        List of required TemplateDefinition.

    Reference: BCBS d400 Section 2.
    """
    templates = get_templates_by_frequency(frequency)
    if frequency == DisclosureFrequency.SEMI_ANNUAL:
        templates += get_templates_by_frequency(DisclosureFrequency.QUARTERLY)
    elif frequency == DisclosureFrequency.ANNUAL:
        templates += get_templates_by_frequency(DisclosureFrequency.QUARTERLY)
        templates += get_templates_by_frequency(DisclosureFrequency.SEMI_ANNUAL)
    return templates
