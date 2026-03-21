"""Pillar 3 Templates — MR1-MR4: Market Risk Disclosures.

MR1: Market risk capital requirements under FRTB standardised approach.
MR2: RWA flow statements of market risk exposures under SA.
MR3: Market risk under IMA (if applicable — placeholder).
MR4: Comparison of VaR estimates with gains/losses (backtesting).

All amounts in USD millions ($M).

References:
- BCBS d455 Tables MR1-MR4
- BCBS d400 Section 7: Market risk
- BCBS d457: "Minimum Capital Requirements for Market Risk" (Jan 2019)
- ERBA NPR pp. 300-350: FRTB framework
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# =========================================================================
#  MR1: Market Risk Under Standardised Approach
#  Reference: BCBS d455 Table MR1
# =========================================================================

class MR1Row(BaseModel):
    """A single row in the MR1 disclosure template.

    Reference: BCBS d455 Table MR1.
    """
    row_number: int = Field(description="Row number")
    description: str = Field(description="Risk class / component")
    rwa: float = Field(default=0.0, description="RWA equivalent in $M")
    capital_charge: float = Field(
        default=0.0, description="Capital charge in $M"
    )


class Pillar3MR1(BaseModel):
    """Pillar 3 Template MR1: Market Risk Under SA (FRTB).

    Breakdown of market risk capital requirements by risk class
    (GIRR, CSR, Equity, Commodity, FX) and by component
    (SBM delta/vega/curvature, DRC, RRAO).

    Reference: BCBS d455 Table MR1.
    """
    template_id: str = Field(default="MR1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[MR1Row] = Field(default_factory=list)

    # Summary
    total_sbm_charge: float = Field(default=0.0)
    total_drc_charge: float = Field(default=0.0)
    total_rrao_charge: float = Field(default=0.0)
    total_capital_charge: float = Field(default=0.0)
    total_rwa: float = Field(default=0.0)


def build_mr1(
    girr_charge: float = 0.0,
    csr_nonsec_charge: float = 0.0,
    csr_sec_nonctp_charge: float = 0.0,
    csr_sec_ctp_charge: float = 0.0,
    equity_charge: float = 0.0,
    commodity_charge: float = 0.0,
    fx_charge: float = 0.0,
    drc_nonsec_charge: float = 0.0,
    drc_sec_nonctp_charge: float = 0.0,
    drc_sec_ctp_charge: float = 0.0,
    rrao_charge: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3MR1:
    """Build Pillar 3 MR1: Market Risk Under SA.

    Creates the MR1 disclosure template with FRTB capital charges
    broken down by risk class and component.

    RWA = capital_charge * 12.5 per 12 CFR 217.10(a)(3).

    Args:
        girr_charge: GIRR capital charge in $M.
        csr_nonsec_charge: CSR Non-Sec capital charge in $M.
        csr_sec_nonctp_charge: CSR Sec Non-CTP charge in $M.
        csr_sec_ctp_charge: CSR Sec CTP charge in $M.
        equity_charge: Equity risk charge in $M.
        commodity_charge: Commodity risk charge in $M.
        fx_charge: FX risk charge in $M.
        drc_nonsec_charge: DRC Non-Sec charge in $M.
        drc_sec_nonctp_charge: DRC Sec Non-CTP charge in $M.
        drc_sec_ctp_charge: DRC Sec CTP charge in $M.
        rrao_charge: RRAO charge in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3MR1 disclosure template.

    Reference: BCBS d455 Table MR1.
    """
    rwa_mult = 12.5  # RWA = charge * 12.5

    # SBM by risk class
    sbm_total = (
        girr_charge + csr_nonsec_charge + csr_sec_nonctp_charge
        + csr_sec_ctp_charge + equity_charge + commodity_charge + fx_charge
    )
    drc_total = drc_nonsec_charge + drc_sec_nonctp_charge + drc_sec_ctp_charge
    total_charge = sbm_total + drc_total + rrao_charge

    rows: list[MR1Row] = [
        # SBM components
        MR1Row(row_number=1, description="GIRR (General Interest Rate Risk)",
               capital_charge=girr_charge, rwa=girr_charge * rwa_mult),
        MR1Row(row_number=2, description="CSR Non-Securitisation",
               capital_charge=csr_nonsec_charge, rwa=csr_nonsec_charge * rwa_mult),
        MR1Row(row_number=3, description="CSR Securitisation (Non-CTP)",
               capital_charge=csr_sec_nonctp_charge,
               rwa=csr_sec_nonctp_charge * rwa_mult),
        MR1Row(row_number=4, description="CSR Securitisation (CTP)",
               capital_charge=csr_sec_ctp_charge,
               rwa=csr_sec_ctp_charge * rwa_mult),
        MR1Row(row_number=5, description="Equity Risk",
               capital_charge=equity_charge, rwa=equity_charge * rwa_mult),
        MR1Row(row_number=6, description="Commodity Risk",
               capital_charge=commodity_charge, rwa=commodity_charge * rwa_mult),
        MR1Row(row_number=7, description="FX Risk",
               capital_charge=fx_charge, rwa=fx_charge * rwa_mult),
        MR1Row(row_number=8, description="Total SBM",
               capital_charge=sbm_total, rwa=sbm_total * rwa_mult),
        # DRC components
        MR1Row(row_number=9, description="DRC Non-Securitisation",
               capital_charge=drc_nonsec_charge, rwa=drc_nonsec_charge * rwa_mult),
        MR1Row(row_number=10, description="DRC Securitisation (Non-CTP)",
               capital_charge=drc_sec_nonctp_charge,
               rwa=drc_sec_nonctp_charge * rwa_mult),
        MR1Row(row_number=11, description="DRC Securitisation (CTP)",
               capital_charge=drc_sec_ctp_charge,
               rwa=drc_sec_ctp_charge * rwa_mult),
        MR1Row(row_number=12, description="Total DRC",
               capital_charge=drc_total, rwa=drc_total * rwa_mult),
        # RRAO
        MR1Row(row_number=13, description="Residual Risk Add-On (RRAO)",
               capital_charge=rrao_charge, rwa=rrao_charge * rwa_mult),
        # Grand total
        MR1Row(row_number=14, description="Total Market Risk (SA)",
               capital_charge=total_charge, rwa=total_charge * rwa_mult),
    ]

    return Pillar3MR1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_sbm_charge=sbm_total,
        total_drc_charge=drc_total,
        total_rrao_charge=rrao_charge,
        total_capital_charge=total_charge,
        total_rwa=total_charge * rwa_mult,
    )


# =========================================================================
#  MR2: RWA Flow Statements
#  Reference: BCBS d455 Table MR2
# =========================================================================

class MR2Row(BaseModel):
    """A single row in the MR2 disclosure template.

    Reference: BCBS d455 Table MR2.
    """
    row_number: int = Field(description="Row number")
    description: str = Field(description="Movement description")
    rwa_change: float = Field(default=0.0, description="RWA change in $M")
    capital_charge_change: float = Field(
        default=0.0, description="Capital charge change in $M"
    )


class Pillar3MR2(BaseModel):
    """Pillar 3 Template MR2: RWA Flow Statements.

    Shows movements in market risk RWA during the reporting period.

    Reference: BCBS d455 Table MR2.
    """
    template_id: str = Field(default="MR2")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[MR2Row] = Field(default_factory=list)
    opening_rwa: float = Field(default=0.0)
    closing_rwa: float = Field(default=0.0)


def build_mr2(
    opening_rwa: float,
    movement_levels: float = 0.0,
    movement_model_updates: float = 0.0,
    movement_methodology: float = 0.0,
    movement_acquisitions: float = 0.0,
    movement_fx: float = 0.0,
    movement_other: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3MR2:
    """Build Pillar 3 MR2: RWA Flow Statements.

    Args:
        opening_rwa: Opening market risk RWA in $M.
        movement_levels: RWA change from risk levels in $M.
        movement_model_updates: RWA change from model updates in $M.
        movement_methodology: RWA change from methodology changes in $M.
        movement_acquisitions: RWA change from acquisitions/disposals in $M.
        movement_fx: RWA change from FX movements in $M.
        movement_other: Other RWA changes in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3MR2 disclosure template.

    Reference: BCBS d455 Table MR2.
    """
    total_change = (
        movement_levels + movement_model_updates + movement_methodology
        + movement_acquisitions + movement_fx + movement_other
    )
    closing = opening_rwa + total_change
    charge_divisor = 12.5  # capital charge = RWA / 12.5

    rows: list[MR2Row] = [
        MR2Row(row_number=1, description="RWA at previous quarter end",
               rwa_change=opening_rwa,
               capital_charge_change=opening_rwa / charge_divisor),
        MR2Row(row_number=2, description="Movement in risk levels",
               rwa_change=movement_levels,
               capital_charge_change=movement_levels / charge_divisor),
        MR2Row(row_number=3, description="Model updates/changes",
               rwa_change=movement_model_updates,
               capital_charge_change=movement_model_updates / charge_divisor),
        MR2Row(row_number=4, description="Methodology and policy changes",
               rwa_change=movement_methodology,
               capital_charge_change=movement_methodology / charge_divisor),
        MR2Row(row_number=5, description="Acquisitions and disposals",
               rwa_change=movement_acquisitions,
               capital_charge_change=movement_acquisitions / charge_divisor),
        MR2Row(row_number=6, description="Foreign exchange movements",
               rwa_change=movement_fx,
               capital_charge_change=movement_fx / charge_divisor),
        MR2Row(row_number=7, description="Other",
               rwa_change=movement_other,
               capital_charge_change=movement_other / charge_divisor),
        MR2Row(row_number=8, description="RWA at end of reporting period",
               rwa_change=closing,
               capital_charge_change=closing / charge_divisor),
    ]

    return Pillar3MR2(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        opening_rwa=opening_rwa,
        closing_rwa=closing,
    )
