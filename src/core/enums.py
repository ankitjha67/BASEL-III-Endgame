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
    """The ten GIRR delta tenor vertices per ERBA NPR §__.208(b)(1). Values in years.

    (BCBS d457 MAR21.8(1) cross-reference.)  Sensitivities at other
    maturities must be allocated to these vertices before aggregation.
    """
    Y0_25 = 0.25
    Y0_5 = 0.5
    Y1 = 1.0
    Y2 = 2.0
    Y3 = 3.0
    Y5 = 5.0
    Y10 = 10.0
    Y15 = 15.0
    Y20 = 20.0
    Y30 = 30.0


class CurrencyCategory(Enum):
    """Currency categories for GIRR delta risk weights per ERBA NPR §__.209(b)(1).

    SPECIFIED currencies (USD, AUD, CAD, EUR, JPY, SEK, GBP and any the
    agency specifies) may divide the Table 1 risk weights by sqrt(2);
    OTHER currencies use Table 1 unchanged.
    """
    SPECIFIED = "SPECIFIED"
    OTHER = "OTHER"


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
    """CSR Non-Securitization buckets per ERBA NPR §__.209(b)(2) Table 3.

    20 buckets organised by credit-quality category (investment grade,
    speculative grade, sub-speculative grade -- assessed internally, no
    external ratings per Dodd-Frank §939A) and sector.  Buckets 12-16 cover
    speculative AND sub-speculative grade; bucket 18 is "other sector";
    buckets 19-20 are index buckets.
    """
    # Investment grade (IG)
    B1_SOVEREIGN_IG = 1              # Sovereigns incl. central banks, MDBs, supranationals
    B2_PSE_IG = 2                    # PSEs, gov-backed non-financials, GSE debt, education, public admin
    B3_FINANCIALS_IG = 3             # Financials incl. gov-backed financials and real estate activities
    B4_BASIC_MATERIALS_IG = 4        # Basic materials, energy, industrials, agriculture, manufacturing, mining
    B5_CONSUMER_IG = 5               # Consumer goods & services, transport & storage, admin & support
    B6_TECH_TELECOM_IG = 6           # Technology, telecommunications
    B7_HEALTHCARE_UTILITIES_IG = 7   # Health care, utilities, professional & technical activities
    B8_COVERED_BOND_IG = 8           # Covered bonds
    # Speculative grade
    B9_SOVEREIGN_SPEC = 9            # Sovereigns incl. central banks, MDBs, supranationals
    B10_PSE_SPEC = 10                # PSEs, gov-backed non-financials, education, public admin
    B11_FINANCIALS_SPEC = 11         # Financials incl. gov-backed financials and real estate activities
    # Speculative grade AND sub-speculative grade
    B12_BASIC_MATERIALS_SPEC_SUBSPEC = 12
    B13_CONSUMER_SPEC_SUBSPEC = 13
    B14_TECH_TELECOM_SPEC_SUBSPEC = 14
    B15_HEALTHCARE_UTILITIES_SPEC_SUBSPEC = 15
    B16_COVERED_BOND_SPEC_SUBSPEC = 16
    # Sub-speculative grade
    B17_SOVEREIGN_SUBSPEC = 17       # Sovereigns incl. central banks, MDBs, supranationals
    # Residual / index buckets
    B18_OTHER_SECTOR = 18            # Other sector (any credit quality)
    B19_INDEX_IG = 19                # Investment-grade indices
    B20_INDEX_SPEC_SUBSPEC = 20      # Speculative & sub-speculative grade indices


class CSRSecBucket(Enum):
    """CSR Securitization (non-CTP) buckets per ERBA NPR §__.209(b)(4) Table 7.

    25 buckets: seniority x credit quality x asset type, plus "other sector".
    Buckets 1-8 senior IG, 9-16 non-senior IG, 17-24 speculative &
    sub-speculative grade (any seniority), 25 other sector.  Within each
    group the asset-type order is: prime RMBS, mid-prime RMBS, sub-prime
    RMBS, CMBS, ABS student loans, ABS credit cards & personal loans, ABS
    auto & dealer floorplan, CLO non-CTP.
    """
    # Senior, investment grade
    B1_SENIOR_IG_RMBS_PRIME = 1
    B2_SENIOR_IG_RMBS_MIDPRIME = 2
    B3_SENIOR_IG_RMBS_SUBPRIME = 3
    B4_SENIOR_IG_CMBS = 4
    B5_SENIOR_IG_ABS_STUDENT = 5
    B6_SENIOR_IG_ABS_CARDS_PERSONAL = 6
    B7_SENIOR_IG_ABS_AUTO_FLOORPLAN = 7
    B8_SENIOR_IG_CLO = 8
    # Non-senior, investment grade
    B9_NONSENIOR_IG_RMBS_PRIME = 9
    B10_NONSENIOR_IG_RMBS_MIDPRIME = 10
    B11_NONSENIOR_IG_RMBS_SUBPRIME = 11
    B12_NONSENIOR_IG_CMBS = 12
    B13_NONSENIOR_IG_ABS_STUDENT = 13
    B14_NONSENIOR_IG_ABS_CARDS_PERSONAL = 14
    B15_NONSENIOR_IG_ABS_AUTO_FLOORPLAN = 15
    B16_NONSENIOR_IG_CLO = 16
    # Speculative & sub-speculative grade (any seniority)
    B17_SPEC_RMBS_PRIME = 17
    B18_SPEC_RMBS_MIDPRIME = 18
    B19_SPEC_RMBS_SUBPRIME = 19
    B20_SPEC_CMBS = 20
    B21_SPEC_ABS_STUDENT = 21
    B22_SPEC_ABS_CARDS_PERSONAL = 22
    B23_SPEC_ABS_AUTO_FLOORPLAN = 23
    B24_SPEC_CLO = 24
    # Residual
    B25_OTHER_SECTOR = 25


class CSRSecCTPBucket(Enum):
    """CSR Securitization CTP buckets per ERBA NPR §__.209(b)(3) Table 5.

    16 buckets: the CSR non-sec sector taxonomy without covered-bond and
    index buckets.  Buckets 1-7 IG, 8-9 speculative grade, 10-14
    speculative & sub-speculative grade, 15 sub-speculative sovereigns,
    16 other sector.
    """
    # Investment grade
    B1_SOVEREIGN_IG = 1
    B2_PSE_IG = 2
    B3_FINANCIALS_IG = 3
    B4_BASIC_MATERIALS_IG = 4
    B5_CONSUMER_IG = 5
    B6_TECH_TELECOM_IG = 6
    B7_HEALTHCARE_UTILITIES_IG = 7
    # Speculative grade
    B8_SOVEREIGN_SPEC = 8
    B9_PSE_SPEC = 9
    # Speculative & sub-speculative grade
    B10_FINANCIALS_SPEC_SUBSPEC = 10
    B11_BASIC_MATERIALS_SPEC_SUBSPEC = 11
    B12_CONSUMER_SPEC_SUBSPEC = 12
    B13_TECH_TELECOM_SPEC_SUBSPEC = 13
    B14_HEALTHCARE_UTILITIES_SPEC_SUBSPEC = 14
    # Sub-speculative grade
    B15_SOVEREIGN_SUBSPEC = 15
    # Residual
    B16_OTHER_SECTOR = 16


class CreditQuality(Enum):
    """Credit-quality categories for CSR bucket assignment.

    ERBA NPR §__.209(b)(2)-(4) uses three internally-assessed categories
    (no external ratings per Dodd-Frank §939A): investment grade,
    speculative grade and sub-speculative grade.  For the inter-bucket
    rating factor gamma_rating, speculative and sub-speculative grade count
    as ONE category.
    """
    INVESTMENT_GRADE = "IG"
    SPECULATIVE_GRADE = "SG"
    SUB_SPECULATIVE_GRADE = "SSG"


class CSRSector(Enum):
    """CSR sector classifications per ERBA NPR §__.209(b)(2) Table 3.

    Real estate activities are classified under FINANCIALS (bucket 3/11);
    GSE debt, education and public administration under PSE (bucket 2/10).
    """
    SOVEREIGN = "SOVEREIGN"                    # Sovereigns, central banks, MDBs, supranationals
    PSE = "PSE"                                # PSEs, gov-backed non-financials, GSE debt, education, public admin
    FINANCIALS = "FINANCIALS"                  # Financials incl. gov-backed financials, real estate activities
    BASIC_MATERIALS = "BASIC_MATERIALS"        # Basic materials, energy, industrials, agriculture, manufacturing, mining
    CONSUMER = "CONSUMER"                      # Consumer goods & services, transport & storage, admin & support
    TECH_TELECOM = "TECH_TELECOM"              # Technology, telecommunications
    HEALTHCARE_UTILITIES = "HEALTHCARE_UTILITIES"  # Health care, utilities, professional & technical activities
    COVERED_BOND = "COVERED_BOND"              # Covered bonds
    OTHER = "OTHER"                            # Other sector
    INDEX = "INDEX"                            # Credit indices (buckets 19-20)


class CSRSecSeniority(Enum):
    """Tranche seniority for CSR securitization (non-CTP) bucketing per ERBA NPR §__.209(b)(4) Table 7."""
    SENIOR = "SENIOR"
    NON_SENIOR = "NON_SENIOR"


class CSRSecAssetType(Enum):
    """Underlying asset type for CSR securitization (non-CTP) bucketing per ERBA NPR §__.209(b)(4) Table 7."""
    RMBS_PRIME = "RMBS_PRIME"
    RMBS_MIDPRIME = "RMBS_MIDPRIME"
    RMBS_SUBPRIME = "RMBS_SUBPRIME"
    CMBS = "CMBS"
    ABS_STUDENT_LOANS = "ABS_STUDENT_LOANS"
    ABS_CREDIT_CARDS_PERSONAL = "ABS_CREDIT_CARDS_PERSONAL"
    ABS_AUTO_FLOORPLAN = "ABS_AUTO_FLOORPLAN"
    CLO_NON_CTP = "CLO_NON_CTP"
    OTHER = "OTHER"


# =========================================================================
#  Equity Enums
# =========================================================================

class EquityBucket(Enum):
    """Equity risk buckets per ERBA NPR §__.209(b)(5) Table 8.

    13 buckets: 4 EM large cap + 4 liquid-market large cap + EM small cap
    + liquid-market small cap + other sector + 2 index buckets.  Large
    market capitalisation = >= $2 billion.  (BCBS MAR21.72 cross-reference;
    the US rule uses "liquid market economy" rather than "advanced economy".)
    """
    B1_EM_LARGE_CONSUMER = 1              # EM large cap - consumer, transport, admin, health care, utilities
    B2_EM_LARGE_TELECOM_INDUSTRIALS = 2   # EM large cap - telecommunications, industrials
    B3_EM_LARGE_BASIC_MATERIALS = 3       # EM large cap - basic materials, energy, agri, manufacturing, mining
    B4_EM_LARGE_FINANCIALS_TECH = 4       # EM large cap - financials, real estate, technology
    B5_LIQUID_LARGE_CONSUMER = 5          # Liquid market large cap - consumer, transport, admin, health, utilities
    B6_LIQUID_LARGE_TELECOM_INDUSTRIALS = 6  # Liquid market large cap - telecommunications, industrials
    B7_LIQUID_LARGE_BASIC_MATERIALS = 7   # Liquid market large cap - basic materials, energy, agri, mfg, mining
    B8_LIQUID_LARGE_FINANCIALS_TECH = 8   # Liquid market large cap - financials, real estate, technology
    B9_EM_SMALL_CAP = 9                   # EM small cap - all sectors
    B10_LIQUID_SMALL_CAP = 10             # Liquid market small cap - all sectors
    B11_OTHER_SECTOR = 11                 # Other sector
    B12_LARGE_CAP_LIQUID_INDEX = 12       # Large-cap, liquid-market equity indices
    B13_OTHER_INDEX = 13                  # Other equity indices


class EquityMarket(Enum):
    """Equity market classification per ERBA NPR §__.209(b)(5).

    The US rule distinguishes "emerging market economy" and "liquid market
    economy" issuers.
    """
    EMERGING = "EM"
    LIQUID_MARKET = "LIQUID"


class EquitySize(Enum):
    """Equity size classification."""
    LARGE_CAP = "LARGE"
    SMALL_CAP = "SMALL"


# =========================================================================
#  Commodity Enums
# =========================================================================

class CommodityBucket(Enum):
    """Commodity risk buckets per ERBA NPR §__.209(b)(6) Table 9.

    12 buckets covering energy, freight, metals, agriculturals, other and
    commodity indices.  (BCBS MAR21.82 cross-reference.)
    """
    B1_ENERGY_SOLID_COMBUSTIBLES = 1       # Energy - solid combustibles (coal, charcoal, ...)
    B2_ENERGY_LIQUID_COMBUSTIBLES = 2      # Energy - liquid combustibles (crude, light ends, distillates, ...)
    B3_ENERGY_CARBON_TRADING = 3           # Energy - carbon trading
    B4_FREIGHT = 4                         # Freight (dry bulk, tanker)
    B5_METALS_NON_PRECIOUS = 5             # Metals - non-precious (base metals, steel, ...)
    B6_GASEOUS_COMBUSTIBLES_ELECTRICITY = 6  # Gaseous combustibles (natural gas, LNG) and electricity
    B7_PRECIOUS_METALS = 7                 # Precious metals including gold
    B8_GRAINS_OILSEED = 8                  # Grains and oilseed
    B9_LIVESTOCK_DAIRY = 9                 # Livestock and dairy
    B10_FORESTRY_OTHER_AGRICULTURALS = 10  # Softs, forestry and other agriculturals
    B11_OTHER_COMMODITY = 11               # Other commodity
    B12_COMMODITY_INDEX = 12               # Commodity indices


# =========================================================================
#  DRC Enums
# =========================================================================

class DRCSeniority(Enum):
    """LGD classes for DRC non-securitization positions per ERBA NPR §__.210(b)(1)(iv) (p.903).

    (BCBS d457 MAR22.12 cross-reference.)  The NPR assigns LGD by the
    instrument's place in the capital structure and by issuer type:

    - EQUITY, SUBORDINATED (non-senior debt): 100%
    - SENIOR_UNSECURED (senior debt): 75%
    - GSE_UNGUARANTEED (debt issued but not guaranteed by a GSE): 75%
    - US_PSE (positions in a US public sector entity): 50%
    - GSE_GUARANTEED (GSE debt guaranteed by the GSE): 25%
    - COVERED_BOND: 25%
    - NOT_LINKED_TO_RECOVERY (value not linked to the recovery rate): 0%

    ``SENIOR_SECURED`` is retained as a deprecated alias of ``COVERED_BOND``:
    the NPR has no generic "senior secured = 25%" category.
    """
    EQUITY = "EQUITY"
    SUBORDINATED = "SUBORDINATED"
    SENIOR_UNSECURED = "SENIOR_UNSECURED"
    GSE_UNGUARANTEED = "GSE_UNGUARANTEED"
    US_PSE = "US_PSE"
    GSE_GUARANTEED = "GSE_GUARANTEED"
    COVERED_BOND = "COVERED_BOND"
    NOT_LINKED_TO_RECOVERY = "NOT_LINKED_TO_RECOVERY"
    SENIOR_SECURED = "COVERED_BOND"  # deprecated alias of COVERED_BOND


class DRCCreditQuality(Enum):
    """Credit quality categories for DRC risk weights per ERBA NPR §__.210(b)(2) Table 1 (p.906).

    The US rule assigns default risk weights by internally assessed credit
    quality category (investment grade / speculative grade / sub-speculative
    grade / defaulted) -- NOT by external rating (Dodd-Frank §939A).
    """
    INVESTMENT_GRADE = "INVESTMENT_GRADE"
    SPECULATIVE_GRADE = "SPECULATIVE_GRADE"
    SUB_SPECULATIVE_GRADE = "SUB_SPECULATIVE_GRADE"
    DEFAULTED = "DEFAULTED"


class DRCRatingCategory(Enum):
    """Optional rating-style convenience input for DRC (BCBS d457 MAR22.14 scale).

    The US ERBA NPR §__.210(b)(2) does NOT use external ratings.  This enum is
    kept only as a convenience that maps onto :class:`DRCCreditQuality`
    (AAA..BBB -> investment grade; BB, B -> speculative grade; CCC ->
    sub-speculative grade; DEFAULTED -> defaulted; UNRATED -> speculative
    grade, see ``drc_params.RATING_TO_CREDIT_QUALITY``).
    """
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
    """DRC non-securitization bucket / exposure types per ERBA NPR §__.210(b)(2) (p.905).

    The four DRC buckets are NON_US_SOVEREIGN, PSE_GSE, CORPORATE and
    DEFAULTED (defaulted positions go to the defaulted bucket regardless of
    sector).  US_SOVEREIGN_MDB marks US sovereign exposures, specified
    supranationals and MDBs, which are excluded from the default risk
    capital requirement (§__.210(a)).  SECURITIZATION is routed to the
    securitization calculators.  ``SOVEREIGN`` and ``LOCAL_GOVERNMENT`` are
    deprecated aliases of NON_US_SOVEREIGN and PSE_GSE.
    """
    NON_US_SOVEREIGN = "NON_US_SOVEREIGN"
    PSE_GSE = "PSE_GSE"
    CORPORATE = "CORPORATE"
    DEFAULTED = "DEFAULTED"
    US_SOVEREIGN_MDB = "US_SOVEREIGN_MDB"
    SECURITIZATION = "SECURITIZATION"
    SOVEREIGN = "NON_US_SOVEREIGN"      # deprecated alias
    LOCAL_GOVERNMENT = "PSE_GSE"        # deprecated alias


class DRCSecBucket(Enum):
    """DRC securitization non-CTP asset classes per ERBA NPR §__.210(c)(3)(i) (p.909).

    Buckets are CORPORATE plus each asset class crossed with a
    :class:`DRCSecRegion`.  ``ABS_AUTO``, ``ABS_CARDS`` and ``ABS_STUDENT``
    are deprecated aliases.
    """
    CORPORATE = "CORPORATE"
    ABCP = "ABCP"
    AUTO = "AUTO"
    RMBS = "RMBS"
    CREDIT_CARDS = "CREDIT_CARDS"
    CMBS = "CMBS"
    CLO = "CLO"
    CDO_SQUARED = "CDO_SQUARED"
    SME = "SME"
    STUDENT_LOANS = "STUDENT_LOANS"
    OTHER_RETAIL = "OTHER_RETAIL"
    OTHER_WHOLESALE = "OTHER_WHOLESALE"
    ABS_AUTO = "AUTO"                  # deprecated alias
    ABS_CARDS = "CREDIT_CARDS"         # deprecated alias
    ABS_STUDENT = "STUDENT_LOANS"      # deprecated alias


class DRCSecRegion(Enum):
    """DRC securitization non-CTP regions per ERBA NPR §__.210(c)(3)(i) (p.909)."""
    ASIA = "ASIA"
    EUROPE = "EUROPE"
    NORTH_AMERICA = "NORTH_AMERICA"
    OTHER = "OTHER"


class DRCSecCTPBucket(Enum):
    """CTP position types per ERBA NPR §__.210(d) (p.911).

    Under the NPR each index is its own bucket (the bucket key is the index
    name), so this enum classifies the *kind* of CTP position rather than
    the bucket: INDEX_TRANCHE (tranched index product), BESPOKE (bespoke
    tranche mapped to the substantially similar index), NTD (nth-to-default),
    NON_SEC_HEDGE (non-securitization hedge placed in the bucket of the CTP
    position it hedges).  ``INDEX_CDS`` is a deprecated alias.
    """
    INDEX_TRANCHE = "INDEX_TRANCHE"
    BESPOKE = "BESPOKE"
    NTD = "NTD"
    NON_SEC_HEDGE = "NON_SEC_HEDGE"
    INDEX_CDS = "INDEX_TRANCHE"        # deprecated alias


class DRCSecRating(Enum):
    """Legacy rating scale for the pre-NPR securitization DRC table (BCBS d457 MAR22.25).

    Not used by the US ERBA NPR §__.210(c)(3)(ii), where the DRC risk weight
    is the banking-book securitization risk weight (§__.133 SEC-SA) x 8%.
    Kept only for the explicit ``legacy_rating_table=True`` switch.
    """
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    UNRATED = "UNRATED"
    DEFAULTED = "DEFAULTED"


class DRCSecSeniority(Enum):
    """Tranche seniority for the legacy securitization DRC table (BCBS d457 MAR22.25)."""
    SENIOR = "SENIOR"
    NON_SENIOR = "NON_SENIOR"


# =========================================================================
#  RRAO Enums
# =========================================================================

class RRAOCategory(Enum):
    """RRAO instrument categories per MAR23."""
    EXOTIC = "EXOTIC"        # 1.0% risk weight
    OTHER = "OTHER"          # 0.1% risk weight
    EXEMPT = "EXEMPT"        # No RRAO charge
