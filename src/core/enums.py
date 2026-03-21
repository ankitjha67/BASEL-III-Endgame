"""Enumerations for Basel III Endgame engine.

Defines all enums used across risk modules for type safety and consistency.
Covers FRTB SBM (all 7 risk classes), DRC, and RRAO.
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
    DRC = "DRC"
    RRAO = "RRAO"


class CorrelationScenario(Enum):
    """Three correlation scenarios per MAR21.6."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GIRRTenor(Enum):
    """Standard GIRR tenors per MAR21.8. Values in years."""
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
    """Currency categories for GIRR risk weight determination per MAR21.8."""
    LOW_VOLATILITY = "LOW_VOLATILITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    SPECIFIED = "SPECIFIED"


class GIRRRiskFactorType(Enum):
    """Types of GIRR risk factors per MAR21.8-21.9."""
    YIELD_CURVE = "YIELD_CURVE"
    INFLATION = "INFLATION"
    CROSS_CURRENCY_BASIS = "CROSS_CURRENCY_BASIS"


class SensitivityType(Enum):
    """Type of sensitivity provided."""
    DELTA = auto()
    VEGA = auto()
    CURVATURE = auto()


# =========================================================================
#  CSR Enums
# =========================================================================

class CSRBucket(Enum):
    """CSR Non-Securitization buckets per MAR21.12 Table 4.

    18 buckets organized by sector and credit quality.
    """
    # Investment Grade (IG)
    B1_SOVEREIGN_IG = 1        # Sovereigns including central banks, multilateral development banks - IG
    B2_SOVEREIGN_HY = 2        # Sovereigns including central banks, multilateral development banks - HY/NR
    B3_FINANCIALS_IG = 3       # Financials including government-backed financials - IG
    B4_FINANCIALS_HY = 4       # Financials including government-backed financials - HY/NR
    B5_BASIC_MATERIALS_IG = 5  # Basic materials, energy, industrials, agriculture - IG
    B6_BASIC_MATERIALS_HY = 6  # Basic materials, energy, industrials, agriculture - HY/NR
    B7_CONSUMER_IG = 7         # Consumer goods and services, transport, storage - IG
    B8_CONSUMER_HY = 8         # Consumer goods and services, transport, storage - HY/NR
    B9_TMT_IG = 9              # Technology, telecommunications - IG
    B10_TMT_HY = 10            # Technology, telecommunications - HY/NR
    B11_HEALTHCARE_IG = 11     # Health care, utilities, local government, government-backed non-financials - IG
    B12_HEALTHCARE_HY = 12     # Health care, utilities, local government, government-backed non-financials - HY/NR
    B13_COVERED_BOND_IG = 13   # Covered bonds - IG
    B14_COVERED_BOND_HY = 14   # Covered bonds - HY/NR
    B15_REALESTATE_IG = 15     # Real estate - IG
    B16_REALESTATE_HY = 16     # Real estate - HY/NR
    B17_OTHER_IG = 17          # Other sector - IG
    B18_OTHER_HY = 18          # Other sector - HY/NR


class CSRSecBucket(Enum):
    """CSR Securitization Non-CTP buckets per MAR21.14."""
    B1_RMBS_PRIME = 1
    B2_RMBS_MIDPRIME = 2
    B3_RMBS_SUBPRIME = 3
    B4_CMBS = 4
    B5_ABS_CONSUMER = 5    # Auto loans, credit cards, student loans
    B6_CLO = 6             # CLO non-CTP
    B7_ABS_OTHER = 7       # Other ABS
    B8_OTHER = 8           # Other securitizations


class CSRSecCTPBucket(Enum):
    """CSR Securitization CTP buckets per MAR21.15."""
    B1_CTP_IG = 1
    B2_CTP_HY = 2
    B3_CTP_INDEX_IG = 3
    B4_CTP_INDEX_HY = 4
    B5_CTP_OTHER = 5


class CreditQuality(Enum):
    """Credit quality categories for CSR bucket assignment."""
    INVESTMENT_GRADE = "IG"
    HIGH_YIELD = "HY"
    NOT_RATED = "NR"


class CSRSector(Enum):
    """CSR sector classifications per MAR21.12."""
    SOVEREIGN = "SOVEREIGN"
    FINANCIALS = "FINANCIALS"
    BASIC_MATERIALS = "BASIC_MATERIALS"
    CONSUMER = "CONSUMER"
    TMT = "TMT"
    HEALTHCARE_UTILITIES = "HEALTHCARE_UTILITIES"
    COVERED_BOND = "COVERED_BOND"
    REAL_ESTATE = "REAL_ESTATE"
    OTHER = "OTHER"


# =========================================================================
#  Equity Enums
# =========================================================================

class EquityBucket(Enum):
    """Equity risk buckets per MAR21.17 Table 8.

    13 buckets: 5 EM + 5 AE + small cap + 2 index.
    """
    B1_EM_LARGE_CONSUMER = 1         # Large cap EM - Consumer, utilities
    B2_EM_LARGE_TELECOM = 2          # Large cap EM - Telecom, industrials
    B3_EM_LARGE_BASIC_MATERIALS = 3  # Large cap EM - Basic materials, energy
    B4_EM_LARGE_FINANCIALS = 4       # Large cap EM - Financials
    B5_EM_LARGE_TECH = 5             # Large cap EM - Technology, health care
    B6_AE_LARGE_CONSUMER = 6         # Large cap AE - Consumer, utilities
    B7_AE_LARGE_TELECOM = 7          # Large cap AE - Telecom, industrials
    B8_AE_LARGE_BASIC_MATERIALS = 8  # Large cap AE - Basic materials, energy
    B9_AE_LARGE_FINANCIALS = 9       # Large cap AE - Financials
    B10_AE_LARGE_TECH = 10           # Large cap AE - Technology, health care
    B11_ALL_SMALL_CAP = 11           # All regions - Small cap
    B12_LARGE_CAP_INDEX = 12         # Large cap developed market indices
    B13_OTHER_INDEX = 13             # Other equity indices


class EquityMarket(Enum):
    """Equity market classification."""
    EMERGING = "EM"
    ADVANCED = "AE"


class EquitySize(Enum):
    """Equity size classification."""
    LARGE_CAP = "LARGE"
    SMALL_CAP = "SMALL"


# =========================================================================
#  Commodity Enums
# =========================================================================

class CommodityBucket(Enum):
    """Commodity risk buckets per MAR21.19 Table 10.

    11 buckets covering energy, metals, agricultural, and other.
    """
    B1_ENERGY_CRUDE = 1     # Coal and crude oil
    B2_ENERGY_LIGHT = 2     # Light ends (gasoline, naphtha)
    B3_ENERGY_MIDDLE = 3    # Middle distillates (jet fuel, diesel, heating oil)
    B4_ENERGY_HEAVY = 4     # Heavy distillates and residual fuel oil
    B5_ENERGY_NAT_GAS = 5   # Natural gas
    B6_ENERGY_POWER = 6     # Electricity and carbon trading
    B7_METALS_PRECIOUS = 7  # Precious metals (gold, silver, platinum)
    B8_METALS_BASE = 8      # Base metals (copper, aluminium, zinc, nickel)
    B9_AGRI_GRAINS = 9      # Grains and oilseed (wheat, corn, soybeans)
    B10_AGRI_SOFTS = 10     # Softs and other agriculturals (sugar, cotton, cocoa)
    B11_OTHER = 11          # Other commodities (freight, emissions, exotic)


# =========================================================================
#  DRC Enums
# =========================================================================

class DRCSeniority(Enum):
    """Seniority levels for DRC LGD determination per MAR22.12."""
    SENIOR_SECURED = "SENIOR_SECURED"
    SENIOR_UNSECURED = "SENIOR_UNSECURED"
    SUBORDINATED = "SUBORDINATED"
    EQUITY = "EQUITY"


class DRCRatingCategory(Enum):
    """Rating categories for DRC risk weights per MAR22.14."""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    UNRATED = "UNRATED"
    DEFAULTED = "DEFAULTED"


class DRCExposureType(Enum):
    """DRC exposure types for hedge benefit ratio calculation."""
    CORPORATE = "CORPORATE"
    SOVEREIGN = "SOVEREIGN"
    LOCAL_GOVERNMENT = "LOCAL_GOVERNMENT"
    SECURITIZATION = "SECURITIZATION"


# =========================================================================
#  RRAO Enums
# =========================================================================

class RRAOCategory(Enum):
    """RRAO instrument categories per MAR23."""
    EXOTIC = "EXOTIC"        # 1.0% risk weight
    OTHER = "OTHER"          # 0.1% risk weight
    EXEMPT = "EXEMPT"        # No RRAO charge
