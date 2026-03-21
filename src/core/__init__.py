"""Core module — base classes, enums, data models, and exceptions."""

from src.core.enums import (
    CorrelationScenario,
    CurrencyCategory,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
    SensitivityType,
)
from src.core.exceptions import (
    BaselEngineError,
    CalculationError,
    ConfigurationError,
    DataError,
    ValidationError,
)
from src.core.models import (
    BucketResult,
    GIRRResult,
    RiskChargeResult,
    Sensitivity,
    WeightedSensitivity,
)

__all__ = [
    "CorrelationScenario",
    "CurrencyCategory",
    "GIRRRiskFactorType",
    "GIRRTenor",
    "RiskClass",
    "RiskMeasure",
    "SensitivityType",
    "BaselEngineError",
    "CalculationError",
    "ConfigurationError",
    "DataError",
    "ValidationError",
    "BucketResult",
    "GIRRResult",
    "RiskChargeResult",
    "Sensitivity",
    "WeightedSensitivity",
]
