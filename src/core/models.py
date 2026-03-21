"""Data models for Basel III Endgame engine.

Uses Pydantic for validation and serialization of trade and sensitivity data.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.core.enums import (
    CorrelationScenario,
    DRCExposureType,
    DRCRatingCategory,
    DRCSeniority,
    GIRRRiskFactorType,
    GIRRTenor,
    RRAOCategory,
    RiskClass,
    RiskMeasure,
)


class Sensitivity(BaseModel):
    """A single risk sensitivity for SBM calculation.

    Represents s_k in MAR21 notation — the sensitivity of a position
    to a specific risk factor.
    """
    risk_class: RiskClass
    risk_measure: RiskMeasure
    bucket: str = Field(description="Bucket identifier (currency for GIRR)")
    risk_factor_type: GIRRRiskFactorType = GIRRRiskFactorType.YIELD_CURVE
    tenor: Optional[GIRRTenor] = Field(
        default=None,
        description="Tenor vertex for yield curve sensitivities"
    )
    label: str = Field(
        default="",
        description="Curve label (e.g., 'OIS', 'LIBOR3M') for same-curve correlation"
    )
    value: float = Field(description="Sensitivity value in reporting currency")
    option_maturity: Optional[float] = Field(
        default=None,
        description="Option maturity in years (for vega/curvature)"
    )

    @field_validator("tenor")
    @classmethod
    def validate_tenor_for_yield_curve(
        cls, v: Optional[GIRRTenor], info: object
    ) -> Optional[GIRRTenor]:
        """Yield curve sensitivities must have a tenor."""
        return v


class WeightedSensitivity(BaseModel):
    """Weighted sensitivity WS_k = RW_k × s_k per MAR21.4."""
    sensitivity: Sensitivity
    risk_weight: float
    weighted_value: float = Field(description="WS_k = RW_k * s_k")


class BucketResult(BaseModel):
    """Result of intra-bucket aggregation for a single bucket."""
    bucket: str
    capital_charge: float = Field(description="K_b: intra-bucket capital charge")
    net_weighted_sensitivity: float = Field(description="S_b = sum(WS_k)")
    weighted_sensitivities: list[WeightedSensitivity] = []


class RiskChargeResult(BaseModel):
    """Final risk charge result for a risk class and measure."""
    risk_class: RiskClass
    risk_measure: RiskMeasure
    scenario: CorrelationScenario
    capital_charge: float
    bucket_results: list[BucketResult] = []


class GIRRResult(BaseModel):
    """Complete GIRR result across all three correlation scenarios.

    Per MAR21.6, the capital requirement is max across scenarios.
    """
    delta_low: RiskChargeResult
    delta_medium: RiskChargeResult
    delta_high: RiskChargeResult
    vega_low: RiskChargeResult
    vega_medium: RiskChargeResult
    vega_high: RiskChargeResult
    curvature_low: RiskChargeResult
    curvature_medium: RiskChargeResult
    curvature_high: RiskChargeResult

    @property
    def delta_charge(self) -> float:
        """Maximum delta charge across scenarios."""
        return max(
            self.delta_low.capital_charge,
            self.delta_medium.capital_charge,
            self.delta_high.capital_charge,
        )

    @property
    def vega_charge(self) -> float:
        """Maximum vega charge across scenarios."""
        return max(
            self.vega_low.capital_charge,
            self.vega_medium.capital_charge,
            self.vega_high.capital_charge,
        )

    @property
    def curvature_charge(self) -> float:
        """Maximum curvature charge across scenarios."""
        return max(
            self.curvature_low.capital_charge,
            self.curvature_medium.capital_charge,
            self.curvature_high.capital_charge,
        )

    @property
    def total_charge(self) -> float:
        """Total GIRR capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge


# =========================================================================
#  Generic SBM Result (reusable for CSR, Equity, Commodity, FX)
# =========================================================================

class SBMRiskClassResult(BaseModel):
    """Generic SBM result for any risk class across three correlation scenarios.

    Follows the same pattern as GIRRResult but is parameterized for reuse.
    """
    risk_class: RiskClass
    delta_low: RiskChargeResult
    delta_medium: RiskChargeResult
    delta_high: RiskChargeResult
    vega_low: RiskChargeResult
    vega_medium: RiskChargeResult
    vega_high: RiskChargeResult
    curvature_low: RiskChargeResult
    curvature_medium: RiskChargeResult
    curvature_high: RiskChargeResult

    @property
    def delta_charge(self) -> float:
        return max(
            self.delta_low.capital_charge,
            self.delta_medium.capital_charge,
            self.delta_high.capital_charge,
        )

    @property
    def vega_charge(self) -> float:
        return max(
            self.vega_low.capital_charge,
            self.vega_medium.capital_charge,
            self.vega_high.capital_charge,
        )

    @property
    def curvature_charge(self) -> float:
        return max(
            self.curvature_low.capital_charge,
            self.curvature_medium.capital_charge,
            self.curvature_high.capital_charge,
        )

    @property
    def total_charge(self) -> float:
        return self.delta_charge + self.vega_charge + self.curvature_charge


# =========================================================================
#  DRC Models
# =========================================================================

class DRCPosition(BaseModel):
    """A single position for Default Risk Charge calculation per MAR22."""
    issuer: str = Field(description="Issuer/obligor identifier")
    seniority: DRCSeniority
    rating: DRCRatingCategory
    exposure_type: DRCExposureType = DRCExposureType.CORPORATE
    notional: float = Field(description="Face value / notional amount")
    market_value: float = Field(description="Current market value")
    maturity_years: float = Field(description="Remaining maturity in years")
    is_long: bool = Field(description="True for long, False for short")


class DRCBucketResult(BaseModel):
    """Result for a single DRC bucket."""
    bucket: str
    capital_charge: float
    gross_jtd_long: float
    gross_jtd_short: float
    net_jtd_long: float
    net_jtd_short: float
    hedge_benefit_ratio: float


class DRCResult(BaseModel):
    """Complete DRC result."""
    total_charge: float
    bucket_results: list[DRCBucketResult] = []
    gross_jtd_long: float = 0.0
    gross_jtd_short: float = 0.0


# =========================================================================
#  RRAO Models
# =========================================================================

class RRAOPosition(BaseModel):
    """A single position for RRAO calculation per MAR23."""
    instrument_id: str
    notional: float = Field(description="Gross notional amount")
    category: RRAOCategory
    description: str = ""


class RRAOResult(BaseModel):
    """Complete RRAO result."""
    total_charge: float
    exotic_charge: float = 0.0
    other_charge: float = 0.0
    exempt_notional: float = 0.0


# =========================================================================
#  Master FRTB Result
# =========================================================================

class FRTBResult(BaseModel):
    """Complete FRTB capital charge result."""
    # SBM by risk class
    girr_charge: float = 0.0
    csr_nonsec_charge: float = 0.0
    csr_sec_nonctp_charge: float = 0.0
    csr_sec_ctp_charge: float = 0.0
    equity_charge: float = 0.0
    commodity_charge: float = 0.0
    fx_charge: float = 0.0

    # SBM subtotals
    sbm_delta: float = 0.0
    sbm_vega: float = 0.0
    sbm_curvature: float = 0.0

    @property
    def sbm_total(self) -> float:
        return (
            self.girr_charge + self.csr_nonsec_charge
            + self.csr_sec_nonctp_charge + self.csr_sec_ctp_charge
            + self.equity_charge + self.commodity_charge + self.fx_charge
        )

    # DRC
    drc_nonsec: float = 0.0
    drc_sec_nonctp: float = 0.0
    drc_sec_ctp: float = 0.0

    @property
    def drc_total(self) -> float:
        return self.drc_nonsec + self.drc_sec_nonctp + self.drc_sec_ctp

    # RRAO
    rrao_total: float = 0.0

    @property
    def total_capital_charge(self) -> float:
        """Total FRTB capital charge = SBM + DRC + RRAO."""
        return self.sbm_total + self.drc_total + self.rrao_total
