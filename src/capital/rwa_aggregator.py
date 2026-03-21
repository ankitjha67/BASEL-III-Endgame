"""RWA Aggregation Engine — Risk-Weighted Assets across all risk types.

Aggregates RWA from credit risk, market risk (FRTB), operational risk,
and CVA risk into total RWA. Computes the output floor for reference
(NOT applied per US 2026 re-proposal) and provides FFIEC 101 Schedule A
line-item mapping.

All amounts in USD millions ($M).

References:
- ERBA NPR pp. 95-98: Output floor (72.5%)
- ERBA NPR pp. 100-120: RWA aggregation
- FFIEC 101 Schedule A: RWA by exposure type
- 12 CFR 217.10(a): Risk-based capital ratios
- BCBS d424 para 60: Output floor
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_params import (
    OUTPUT_FLOOR_APPLIED,
    OUTPUT_FLOOR_RATE,
)


# =========================================================================
#  Enumerations
# =========================================================================

class CreditRiskExposureType(Enum):
    """Credit risk exposure types per FFIEC 101 Schedule A.

    Reference: FFIEC 101 Schedule A lines 1a-8.
    """
    SOVEREIGN = "SOVEREIGN"
    PUBLIC_SECTOR_ENTITY = "PUBLIC_SECTOR_ENTITY"
    DEPOSITORY_INSTITUTION = "DEPOSITORY_INSTITUTION"
    CORPORATE = "CORPORATE"
    CORPORATE_IG = "CORPORATE_IG"
    RETAIL_RESIDENTIAL = "RETAIL_RESIDENTIAL"
    RETAIL_QUALIFYING_REVOLVING = "RETAIL_QUALIFYING_REVOLVING"
    RETAIL_OTHER = "RETAIL_OTHER"
    RETAIL_TRANSACTOR = "RETAIL_TRANSACTOR"
    EQUITY = "EQUITY"
    SECURITIZATION = "SECURITIZATION"
    CLEARED_TRANSACTIONS = "CLEARED_TRANSACTIONS"
    DEFAULT_FUND_CONTRIBUTIONS = "DEFAULT_FUND_CONTRIBUTIONS"
    UNSETTLED_TRANSACTIONS = "UNSETTLED_TRANSACTIONS"
    OTHER_ASSETS = "OTHER_ASSETS"
    THRESHOLD_DEDUCTIONS_250RW = "THRESHOLD_DEDUCTIONS_250RW"


class MarketRiskChargeType(Enum):
    """Market risk capital charge types per FRTB framework.

    Reference: BCBS d457, ERBA NPR pp. 300-350.
    """
    SBM_GIRR = "SBM_GIRR"
    SBM_CSR_NONSEC = "SBM_CSR_NONSEC"
    SBM_CSR_SEC_NONCTP = "SBM_CSR_SEC_NONCTP"
    SBM_CSR_SEC_CTP = "SBM_CSR_SEC_CTP"
    SBM_EQUITY = "SBM_EQUITY"
    SBM_COMMODITY = "SBM_COMMODITY"
    SBM_FX = "SBM_FX"
    DRC_NONSEC = "DRC_NONSEC"
    DRC_SEC_NONCTP = "DRC_SEC_NONCTP"
    DRC_SEC_CTP = "DRC_SEC_CTP"
    RRAO = "RRAO"


# =========================================================================
#  Input Models
# =========================================================================

class CreditRiskRWAItem(BaseModel):
    """A single credit risk RWA line item.

    Maps to FFIEC 101 Schedule A line items.
    Reference: ERBA NPR pp. 100-115.
    """
    exposure_type: CreditRiskExposureType
    exposure_amount: float = Field(
        description="Exposure amount after CRM, in $M"
    )
    risk_weight: float = Field(
        description="Applicable risk weight (as decimal, e.g. 1.0 = 100%)"
    )
    rwa: float = Field(description="RWA = exposure * risk_weight, in $M")
    ffiec_101_line: str = Field(
        default="",
        description="FFIEC 101 Schedule A line reference"
    )
    description: str = Field(default="")


class CreditRiskRWAInput(BaseModel):
    """Aggregated credit risk RWA input.

    Reference: FFIEC 101 Schedule A lines 1a-8.
    """
    items: list[CreditRiskRWAItem] = Field(default_factory=list)
    total_exposure: float = Field(
        default=0.0,
        description="Total credit risk exposure in $M"
    )
    total_rwa: float = Field(
        default=0.0,
        description="Total credit risk RWA in $M"
    )
    # 250% RW items from threshold deductions
    threshold_250rw_rwa: float = Field(
        default=0.0,
        description="RWA from 250% risk-weighted threshold items (MSA, DTA, etc.)"
    )


class MarketRiskRWAInput(BaseModel):
    """Market risk RWA input from FRTB calculation.

    Market risk RWA = Capital charge * 12.5 (reciprocal of 8% minimum).
    Reference: 12 CFR 217.10(a)(3), ERBA NPR p. 310.
    """
    sbm_charge: float = Field(
        default=0.0,
        description="Total SBM capital charge in $M"
    )
    drc_charge: float = Field(
        default=0.0,
        description="Total DRC capital charge in $M"
    )
    rrao_charge: float = Field(
        default=0.0,
        description="RRAO capital charge in $M"
    )
    total_capital_charge: float = Field(
        default=0.0,
        description="Total FRTB capital charge in $M"
    )

    # Breakdown by risk class (for reporting)
    girr_charge: float = Field(default=0.0)
    csr_nonsec_charge: float = Field(default=0.0)
    csr_sec_nonctp_charge: float = Field(default=0.0)
    csr_sec_ctp_charge: float = Field(default=0.0)
    equity_charge: float = Field(default=0.0)
    commodity_charge: float = Field(default=0.0)
    fx_charge: float = Field(default=0.0)

    @property
    def market_risk_rwa(self) -> float:
        """Convert capital charge to RWA equivalent.

        RWA = Capital_charge * 12.5 (= 1 / 0.08)
        Reference: 12 CFR 217.10(a)(3).
        """
        return self.total_capital_charge * 12.5


class OperationalRiskRWAInput(BaseModel):
    """Operational risk RWA input from SMA calculation.

    OpRisk RWA = BIC * ILM * 12.5
    Reference: BCBS d424 Section 5, ERBA NPR pp. 250-270.
    """
    business_indicator: float = Field(
        default=0.0,
        description="Business Indicator (BI) in $M"
    )
    bic: float = Field(
        default=0.0,
        description="Business Indicator Component in $M"
    )
    ilm: float = Field(
        default=1.0,
        description="Internal Loss Multiplier (1.0 per US proposal)"
    )
    capital_charge: float = Field(
        default=0.0,
        description="OpRisk capital charge = BIC * ILM, in $M"
    )

    @property
    def operational_risk_rwa(self) -> float:
        """Convert capital charge to RWA equivalent.

        RWA = Capital_charge * 12.5
        Reference: BCBS d424 para 7.
        """
        return self.capital_charge * 12.5


class CVARiskRWAInput(BaseModel):
    """CVA risk RWA input.

    CVA RWA = CVA capital charge * 12.5
    Reference: ERBA NPR pp. 280-295.
    """
    sa_cva_charge: float = Field(
        default=0.0,
        description="SA-CVA capital charge in $M"
    )
    ba_cva_charge: float = Field(
        default=0.0,
        description="BA-CVA capital charge in $M"
    )
    total_cva_charge: float = Field(
        default=0.0,
        description="Total CVA capital charge in $M"
    )

    @property
    def cva_risk_rwa(self) -> float:
        """Convert CVA capital charge to RWA equivalent.

        RWA = Capital_charge * 12.5
        Reference: ERBA NPR p. 285.
        """
        return self.total_cva_charge * 12.5


# =========================================================================
#  RWA Result Models
# =========================================================================

class RWABreakdown(BaseModel):
    """Detailed RWA breakdown by risk type.

    Maps to FFIEC 101 Schedule A summary lines.
    Reference: FFIEC 101 Schedule A.
    """
    # Credit Risk RWA
    credit_risk_rwa: float = Field(
        default=0.0,
        description="FFIEC 101 line 9: Total credit risk RWA"
    )
    credit_risk_exposure: float = Field(
        default=0.0,
        description="Total credit risk exposure"
    )
    threshold_250rw_rwa: float = Field(
        default=0.0,
        description="RWA from 250% risk-weighted threshold items"
    )

    # Market Risk RWA
    market_risk_rwa: float = Field(
        default=0.0,
        description="FFIEC 101 line 10: Market risk equivalent RWA"
    )
    market_risk_capital_charge: float = Field(
        default=0.0,
        description="Market risk capital charge (before 12.5x)"
    )

    # Operational Risk RWA
    operational_risk_rwa: float = Field(
        default=0.0,
        description="FFIEC 101 line 11: Operational risk equivalent RWA"
    )
    operational_risk_capital_charge: float = Field(
        default=0.0,
        description="OpRisk capital charge (before 12.5x)"
    )

    # CVA Risk RWA
    cva_risk_rwa: float = Field(
        default=0.0,
        description="FFIEC 101 line 12: CVA risk equivalent RWA"
    )
    cva_risk_capital_charge: float = Field(
        default=0.0,
        description="CVA capital charge (before 12.5x)"
    )

    # Totals
    total_rwa: float = Field(
        default=0.0,
        description="FFIEC 101 line 13: Total RWA"
    )

    # Output floor (reference only)
    standardized_total_rwa: float = Field(
        default=0.0,
        description="Total standardized RWA (for output floor reference)"
    )
    output_floor_rwa: float = Field(
        default=0.0,
        description="72.5% of standardized RWA (NOT applied per US proposal)"
    )
    output_floor_applied: bool = Field(
        default=False,
        description="Whether output floor is binding"
    )
    output_floor_surplus: float = Field(
        default=0.0,
        description="Surplus above output floor (positive = above floor)"
    )


class FFIEC101ScheduleA(BaseModel):
    """FFIEC 101 Schedule A: RWA by exposure type.

    Reference: FFIEC 101 reporting instructions.
    """
    # Credit risk by exposure type
    line_1a_sovereign: float = Field(
        default=0.0, description="Line 1a: Sovereign exposures"
    )
    line_1b_public_sector: float = Field(
        default=0.0, description="Line 1b: Public sector entity exposures"
    )
    line_2_depository: float = Field(
        default=0.0, description="Line 2: Depository institution exposures"
    )
    line_3a_corporate: float = Field(
        default=0.0, description="Line 3a: Corporate exposures"
    )
    line_3b_corporate_ig: float = Field(
        default=0.0, description="Line 3b: Investment grade corporate (65% RW)"
    )
    line_4a_retail_residential: float = Field(
        default=0.0, description="Line 4a: Residential mortgage exposures"
    )
    line_4b_retail_revolving: float = Field(
        default=0.0, description="Line 4b: Qualifying revolving exposures"
    )
    line_4c_retail_other: float = Field(
        default=0.0, description="Line 4c: Other retail exposures"
    )
    line_4d_retail_transactor: float = Field(
        default=0.0, description="Line 4d: Retail transactor (45% RW)"
    )
    line_5_equity: float = Field(
        default=0.0, description="Line 5: Equity exposures"
    )
    line_6_securitization: float = Field(
        default=0.0, description="Line 6: Securitization exposures"
    )
    line_7_cleared_transactions: float = Field(
        default=0.0, description="Line 7: Cleared transaction exposures"
    )
    line_8_default_fund: float = Field(
        default=0.0, description="Line 8: Default fund contributions"
    )
    line_8a_unsettled: float = Field(
        default=0.0, description="Line 8a: Unsettled transactions"
    )
    line_8b_other_assets: float = Field(
        default=0.0, description="Line 8b: Other assets"
    )
    line_8c_threshold_250rw: float = Field(
        default=0.0, description="Line 8c: Threshold items at 250% RW"
    )

    # Subtotals
    line_9_total_credit_risk_rwa: float = Field(
        default=0.0, description="Line 9: Total credit risk RWA"
    )
    line_10_market_risk_rwa: float = Field(
        default=0.0, description="Line 10: Market risk equivalent RWA"
    )
    line_11_operational_risk_rwa: float = Field(
        default=0.0, description="Line 11: Operational risk equivalent RWA"
    )
    line_12_cva_risk_rwa: float = Field(
        default=0.0, description="Line 12: CVA risk equivalent RWA"
    )

    # Grand total
    line_13_total_rwa: float = Field(
        default=0.0, description="Line 13: Total risk-weighted assets"
    )


# =========================================================================
#  Aggregation Functions
# =========================================================================

def aggregate_credit_risk_rwa(
    items: list[CreditRiskRWAItem],
    threshold_250rw_rwa: float = 0.0,
) -> CreditRiskRWAInput:
    """Aggregate credit risk RWA across all exposure types.

    Sums RWA from all credit risk exposure categories and adds the
    250% risk-weighted threshold items (MSA, DTA, significant investments).

    Args:
        items: Individual credit risk RWA line items.
        threshold_250rw_rwa: RWA from 250% risk-weighted threshold items.

    Returns:
        CreditRiskRWAInput with aggregated totals.

    Reference: FFIEC 101 Schedule A lines 1a-9.
    """
    total_exposure = sum(item.exposure_amount for item in items)
    total_rwa = sum(item.rwa for item in items) + threshold_250rw_rwa

    return CreditRiskRWAInput(
        items=items,
        total_exposure=total_exposure,
        total_rwa=total_rwa,
        threshold_250rw_rwa=threshold_250rw_rwa,
    )


def convert_capital_charge_to_rwa(capital_charge: float) -> float:
    """Convert a capital charge to RWA-equivalent amount.

    RWA = Capital_charge * 12.5 (reciprocal of 8% minimum capital ratio).

    Args:
        capital_charge: Capital charge in $M.

    Returns:
        RWA-equivalent amount in $M.

    Reference: 12 CFR 217.10(a)(3).
    """
    return capital_charge * 12.5


def compute_output_floor(
    standardized_rwa: float,
    floor_rate: float = OUTPUT_FLOOR_RATE,
) -> float:
    """Compute the output floor RWA.

    Output floor = 72.5% of total standardized RWA.
    NOTE: NOT applied per US 2026 re-proposal. Computed for reference only.

    Args:
        standardized_rwa: Total RWA under the standardized approach.
        floor_rate: Floor rate (72.5% default).

    Returns:
        Output floor RWA in $M.

    Reference: BCBS d424 para 60, ERBA NPR p. 95.
    """
    return standardized_rwa * floor_rate


def aggregate_rwa(
    credit_risk: Optional[CreditRiskRWAInput] = None,
    market_risk: Optional[MarketRiskRWAInput] = None,
    operational_risk: Optional[OperationalRiskRWAInput] = None,
    cva_risk: Optional[CVARiskRWAInput] = None,
    apply_output_floor: bool = OUTPUT_FLOOR_APPLIED,
) -> RWABreakdown:
    """Aggregate RWA across all risk types.

    Total RWA = Credit Risk RWA + Market Risk RWA + OpRisk RWA + CVA RWA

    The output floor (72.5%) is calculated for reference but NOT applied
    per the US 2026 re-proposal. If apply_output_floor is True (not default),
    total RWA = max(calculated RWA, 72.5% of standardized RWA).

    Args:
        credit_risk: Credit risk RWA input.
        market_risk: Market risk RWA input (FRTB).
        operational_risk: Operational risk RWA input (SMA).
        cva_risk: CVA risk RWA input.
        apply_output_floor: Whether to apply the 72.5% output floor
                           (False per US proposal).

    Returns:
        RWABreakdown with all components and totals.

    Reference: 12 CFR 217.10(a), FFIEC 101 Schedule A.
    """
    # Credit Risk
    cr_rwa = 0.0
    cr_exposure = 0.0
    cr_250rw = 0.0
    if credit_risk is not None:
        cr_rwa = credit_risk.total_rwa
        cr_exposure = credit_risk.total_exposure
        cr_250rw = credit_risk.threshold_250rw_rwa

    # Market Risk
    mr_rwa = 0.0
    mr_charge = 0.0
    if market_risk is not None:
        mr_charge = market_risk.total_capital_charge
        mr_rwa = market_risk.market_risk_rwa

    # Operational Risk
    or_rwa = 0.0
    or_charge = 0.0
    if operational_risk is not None:
        or_charge = operational_risk.capital_charge
        or_rwa = operational_risk.operational_risk_rwa

    # CVA Risk
    cva_rwa = 0.0
    cva_charge = 0.0
    if cva_risk is not None:
        cva_charge = cva_risk.total_cva_charge
        cva_rwa = cva_risk.cva_risk_rwa

    # Total
    total_rwa = cr_rwa + mr_rwa + or_rwa + cva_rwa

    # Output floor (reference calculation)
    # Use total_rwa as standardized proxy since US approach is SA-only
    standardized_rwa = total_rwa
    floor_rwa = compute_output_floor(standardized_rwa)
    floor_binding = apply_output_floor and floor_rwa > total_rwa
    floor_surplus = total_rwa - floor_rwa

    # Apply floor if configured (NOT default per US proposal)
    if floor_binding:
        total_rwa = floor_rwa

    return RWABreakdown(
        credit_risk_rwa=cr_rwa,
        credit_risk_exposure=cr_exposure,
        threshold_250rw_rwa=cr_250rw,
        market_risk_rwa=mr_rwa,
        market_risk_capital_charge=mr_charge,
        operational_risk_rwa=or_rwa,
        operational_risk_capital_charge=or_charge,
        cva_risk_rwa=cva_rwa,
        cva_risk_capital_charge=cva_charge,
        total_rwa=total_rwa,
        standardized_total_rwa=standardized_rwa,
        output_floor_rwa=floor_rwa,
        output_floor_applied=floor_binding,
        output_floor_surplus=floor_surplus,
    )


def build_ffiec_101_schedule_a(
    credit_risk_items: list[CreditRiskRWAItem],
    rwa_breakdown: RWABreakdown,
) -> FFIEC101ScheduleA:
    """Build FFIEC 101 Schedule A from RWA components.

    Maps each credit risk exposure type to the corresponding Schedule A
    line item and adds market, operational, and CVA risk subtotals.

    Args:
        credit_risk_items: Individual credit risk RWA items.
        rwa_breakdown: Aggregated RWA breakdown.

    Returns:
        FFIEC101ScheduleA with all line items populated.

    Reference: FFIEC 101 Schedule A reporting instructions.
    """
    # Map exposure types to line items
    line_map: dict[CreditRiskExposureType, str] = {
        CreditRiskExposureType.SOVEREIGN: "line_1a_sovereign",
        CreditRiskExposureType.PUBLIC_SECTOR_ENTITY: "line_1b_public_sector",
        CreditRiskExposureType.DEPOSITORY_INSTITUTION: "line_2_depository",
        CreditRiskExposureType.CORPORATE: "line_3a_corporate",
        CreditRiskExposureType.CORPORATE_IG: "line_3b_corporate_ig",
        CreditRiskExposureType.RETAIL_RESIDENTIAL: "line_4a_retail_residential",
        CreditRiskExposureType.RETAIL_QUALIFYING_REVOLVING: "line_4b_retail_revolving",
        CreditRiskExposureType.RETAIL_OTHER: "line_4c_retail_other",
        CreditRiskExposureType.RETAIL_TRANSACTOR: "line_4d_retail_transactor",
        CreditRiskExposureType.EQUITY: "line_5_equity",
        CreditRiskExposureType.SECURITIZATION: "line_6_securitization",
        CreditRiskExposureType.CLEARED_TRANSACTIONS: "line_7_cleared_transactions",
        CreditRiskExposureType.DEFAULT_FUND_CONTRIBUTIONS: "line_8_default_fund",
        CreditRiskExposureType.UNSETTLED_TRANSACTIONS: "line_8a_unsettled",
        CreditRiskExposureType.OTHER_ASSETS: "line_8b_other_assets",
        CreditRiskExposureType.THRESHOLD_DEDUCTIONS_250RW: "line_8c_threshold_250rw",
    }

    line_values: dict[str, float] = {}
    for item in credit_risk_items:
        field_name = line_map.get(item.exposure_type)
        if field_name:
            line_values[field_name] = line_values.get(field_name, 0.0) + item.rwa

    # Add 250% RW threshold items
    line_values["line_8c_threshold_250rw"] = (
        line_values.get("line_8c_threshold_250rw", 0.0)
        + rwa_breakdown.threshold_250rw_rwa
    )

    total_credit_rwa = sum(line_values.values())

    return FFIEC101ScheduleA(
        **line_values,
        line_9_total_credit_risk_rwa=rwa_breakdown.credit_risk_rwa,
        line_10_market_risk_rwa=rwa_breakdown.market_risk_rwa,
        line_11_operational_risk_rwa=rwa_breakdown.operational_risk_rwa,
        line_12_cva_risk_rwa=rwa_breakdown.cva_risk_rwa,
        line_13_total_rwa=rwa_breakdown.total_rwa,
    )
