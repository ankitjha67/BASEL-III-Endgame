"""Enumerations for Basel III Endgame engine.

Defines all enums used across risk modules for type safety and consistency.
"""

from enum import Enum, auto


class RiskClass(Enum):
    """FRTB risk classes per MAR21.1."""
    GIRR = "GIRR"
    CSR_NON_SEC = "CSR_NON_SEC"
    CSR_SEC_NON_CTP = "CSR_SEC_NON_CTP"
    CSR_SEC_CTP = "CSR_SEC_CTP"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FX = "FX"


class RiskMeasure(Enum):
    """Risk measure types within SBM per MAR21.4."""
    DELTA = "DELTA"
    VEGA = "VEGA"
    CURVATURE = "CURVATURE"


class CorrelationScenario(Enum):
    """Three correlation scenarios per MAR21.6.

    The capital requirement is the maximum across these three scenarios.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GIRRTenor(Enum):
    """Standard GIRR tenors per MAR21.8.

    Vertices for the risk-free yield curve.
    Values represent years as floats.
    """
    Y0_25 = 0.25
    Y0_5 = 0.5
    Y1 = 1.0
    Y2 = 2.0
    Y3 = 3.0
    Y5 = 5.0
    Y7 = 7.0
    Y10 = 10.0
    Y15 = 15.0
    Y20 = 20.0
    Y25 = 25.0
    Y30 = 30.0


class CurrencyCategory(Enum):
    """Currency categories for GIRR risk weight determination per MAR21.8.

    LOW_VOLATILITY: Major currencies (USD, EUR, GBP, AUD, CAD, JPY, SEK, CHF)
    HIGH_VOLATILITY: All other currencies
    SPECIFIED: Currencies with specific regulatory treatment
    """
    LOW_VOLATILITY = "LOW_VOLATILITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    SPECIFIED = "SPECIFIED"


class GIRRRiskFactorType(Enum):
    """Types of GIRR risk factors per MAR21.8-21.9.

    YIELD_CURVE: Risk-free yield curve sensitivities (delta by tenor)
    INFLATION: Inflation rate sensitivity (single sensitivity per currency)
    CROSS_CURRENCY_BASIS: Cross-currency basis risk (single sensitivity per currency)
    """
    YIELD_CURVE = "YIELD_CURVE"
    INFLATION = "INFLATION"
    CROSS_CURRENCY_BASIS = "CROSS_CURRENCY_BASIS"


class SensitivityType(Enum):
    """Type of sensitivity provided."""
    DELTA = auto()
    VEGA = auto()
    CURVATURE = auto()
