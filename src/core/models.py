"""Data models for Basel III Endgame engine.

Uses Pydantic for validation and serialization of trade and sensitivity data.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.core.enums import (
    CorrelationScenario,
    GIRRRiskFactorType,
    GIRRTenor,
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
