"""G-SIB surcharge parameters per US Federal Reserve 2026 Re-Proposal.

All parameters sourced from:
- G-SIB NPR (128 pages): "Risk-Based Capital Surcharges for GSIBs"
- 12 CFR 217 Subpart H: G-SIB Surcharge
- Federal Reserve Board Method 1 / Method 2 framework
- FR Y-15: Systemic Risk Report instructions

Key US 2026 Re-Proposal changes from 2023 NPR:
- Method 2 coefficients adjusted by 1.2x DOWNWARD factor (CLAUDE.md)
- Surcharge bands: 20bp score ranges / 0.1% increments (NOT 100bp/0.5%)
- Method 1 uses BCBS substitutability cap of 500bp

All monetary amounts in USD millions ($M) unless explicitly stated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


# =========================================================================
#  G-SIB Categories per 12 CFR 217.402
# =========================================================================

class GSIBCategory(Enum):
    """G-SIB systemic importance categories.

    Per 12 CFR 217.402, US G-SIBs are classified into Category I-IV
    based on total consolidated assets and other risk indicators.
    Only Category I and II banks are subject to the G-SIB surcharge
    under the 2026 Re-Proposal.
    """
    CATEGORY_I = "CATEGORY_I"    # >= $700B total assets or >= $75B cross-jurisdictional
    CATEGORY_II = "CATEGORY_II"  # >= $700B total assets or >= $100B in specific indicators
    CATEGORY_III = "CATEGORY_III"  # >= $250B total assets (not subject to G-SIB surcharge)
    CATEGORY_IV = "CATEGORY_IV"   # >= $100B total assets (not subject to G-SIB surcharge)


class GSIBMethod(Enum):
    """G-SIB surcharge calculation methods.

    Per 12 CFR 217.403:
    - Method 1: BCBS substitutability-based approach (12 indicators, 5 categories)
    - Method 2: US-specific short-term wholesale funding approach
    - Final surcharge = higher of Method 1 vs Method 2
    """
    METHOD_1 = "METHOD_1"
    METHOD_2 = "METHOD_2"


class GSIBIndicatorCategory(Enum):
    """Five systemic importance categories per BCBS / 12 CFR 217.404.

    Per G-SIB NPR Section II.B, the five categories each receive
    equal 20% weight under Method 1.
    """
    SIZE = "SIZE"
    INTERCONNECTEDNESS = "INTERCONNECTEDNESS"
    SUBSTITUTABILITY = "SUBSTITUTABILITY"
    COMPLEXITY = "COMPLEXITY"
    CROSS_JURISDICTIONAL = "CROSS_JURISDICTIONAL"


# =========================================================================
#  Method 1 Indicator Weights — FR Y-15 (12 indicators)
#  Per G-SIB NPR Section II.B and BCBS d445
# =========================================================================

# Each of the 5 categories receives 20% weight.
# Within each category, indicators are equally weighted.
# Per G-SIB NPR p.15-22

CATEGORY_WEIGHT: Final[float] = 0.20  # 20% per category — G-SIB NPR p.15

@dataclass(frozen=True)
class IndicatorSpec:
    """Specification for a single G-SIB systemic indicator.

    Attributes:
        name: Human-readable indicator name
        category: Which of the 5 systemic categories
        weight: Weight within the overall score (category_weight / num_indicators_in_category)
        fr_y15_line: FR Y-15 schedule/line reference
        description: Brief description of what the indicator measures
    """
    name: str
    category: GSIBIndicatorCategory
    weight: float
    fr_y15_line: str
    description: str


# -------------------------------------------------------------------------
#  12 Systemic Indicators per BCBS methodology / FR Y-15
#  Weights: Size=20% (1 indicator), Interconnectedness=20% (3 indicators),
#           Substitutability=20% (3 indicators), Complexity=20% (3 indicators),
#           Cross-Jurisdictional=20% (2 indicators)
#  Per G-SIB NPR Section II.B, pp.15-22
# -------------------------------------------------------------------------

METHOD_1_INDICATORS: Final[list[IndicatorSpec]] = [
    # Category 1: Size (20% total, 1 indicator @ 20%)
    # Per G-SIB NPR p.16: Total exposures as defined by the leverage ratio
    IndicatorSpec(
        name="total_exposures",
        category=GSIBIndicatorCategory.SIZE,
        weight=0.20,
        fr_y15_line="Schedule A, Line 1",
        description="Total exposures as defined in the leverage ratio exposure measure"
    ),

    # Category 2: Interconnectedness (20% total, 3 indicators @ 6.667% each)
    # Per G-SIB NPR pp.16-17
    IndicatorSpec(
        name="intra_financial_system_assets",
        category=GSIBIndicatorCategory.INTERCONNECTEDNESS,
        weight=0.20 / 3,
        fr_y15_line="Schedule B, Line 1",
        description="Lending to financial institutions, holdings of securities "
                    "issued by financial institutions, net positive current "
                    "exposure of SFTs and OTC derivatives"
    ),
    IndicatorSpec(
        name="intra_financial_system_liabilities",
        category=GSIBIndicatorCategory.INTERCONNECTEDNESS,
        weight=0.20 / 3,
        fr_y15_line="Schedule B, Line 2",
        description="Borrowings from financial institutions, net negative current "
                    "exposure of SFTs and OTC derivatives"
    ),
    IndicatorSpec(
        name="securities_outstanding",
        category=GSIBIndicatorCategory.INTERCONNECTEDNESS,
        weight=0.20 / 3,
        fr_y15_line="Schedule B, Line 3",
        description="Debt securities outstanding plus equity securities outstanding"
    ),

    # Category 3: Substitutability / Financial Institution Infrastructure
    # (20% total, 3 indicators @ 6.667% each)
    # Per G-SIB NPR pp.17-19 — BCBS caps substitutability at 500bp
    IndicatorSpec(
        name="payments_activity",
        category=GSIBIndicatorCategory.SUBSTITUTABILITY,
        weight=0.20 / 3,
        fr_y15_line="Schedule C, Line 1",
        description="Payments made and received through large-value payment systems"
    ),
    IndicatorSpec(
        name="assets_under_custody",
        category=GSIBIndicatorCategory.SUBSTITUTABILITY,
        weight=0.20 / 3,
        fr_y15_line="Schedule C, Line 2",
        description="Assets held as custodian on behalf of customers"
    ),
    IndicatorSpec(
        name="underwriting_activity",
        category=GSIBIndicatorCategory.SUBSTITUTABILITY,
        weight=0.20 / 3,
        fr_y15_line="Schedule C, Line 3",
        description="Debt and equity underwriting activity"
    ),

    # Category 4: Complexity (20% total, 3 indicators @ 6.667% each)
    # Per G-SIB NPR pp.19-20
    IndicatorSpec(
        name="otc_derivatives_notional",
        category=GSIBIndicatorCategory.COMPLEXITY,
        weight=0.20 / 3,
        fr_y15_line="Schedule D, Line 1",
        description="Notional amount of OTC derivatives"
    ),
    IndicatorSpec(
        name="trading_and_afs_securities",
        category=GSIBIndicatorCategory.COMPLEXITY,
        weight=0.20 / 3,
        fr_y15_line="Schedule D, Line 2",
        description="Trading securities and available-for-sale securities"
    ),
    IndicatorSpec(
        name="level_3_assets",
        category=GSIBIndicatorCategory.COMPLEXITY,
        weight=0.20 / 3,
        fr_y15_line="Schedule D, Line 3",
        description="Level 3 assets under fair value hierarchy"
    ),

    # Category 5: Cross-Jurisdictional Activity (20% total, 2 indicators @ 10% each)
    # Per G-SIB NPR pp.20-22
    IndicatorSpec(
        name="cross_jurisdictional_claims",
        category=GSIBIndicatorCategory.CROSS_JURISDICTIONAL,
        weight=0.20 / 2,
        fr_y15_line="Schedule E, Line 1",
        description="Claims on entities located outside the home jurisdiction"
    ),
    IndicatorSpec(
        name="cross_jurisdictional_liabilities",
        category=GSIBIndicatorCategory.CROSS_JURISDICTIONAL,
        weight=0.20 / 2,
        fr_y15_line="Schedule E, Line 2",
        description="Liabilities to entities located outside the home jurisdiction"
    ),
]

# Quick lookup by indicator name
INDICATOR_LOOKUP: Final[dict[str, IndicatorSpec]] = {
    ind.name: ind for ind in METHOD_1_INDICATORS
}

# Number of indicators per category
INDICATORS_PER_CATEGORY: Final[dict[GSIBIndicatorCategory, int]] = {
    GSIBIndicatorCategory.SIZE: 1,
    GSIBIndicatorCategory.INTERCONNECTEDNESS: 3,
    GSIBIndicatorCategory.SUBSTITUTABILITY: 3,
    GSIBIndicatorCategory.COMPLEXITY: 3,
    GSIBIndicatorCategory.CROSS_JURISDICTIONAL: 2,
}


# =========================================================================
#  Method 1 Substitutability Cap
#  Per BCBS d445 / G-SIB NPR p.18
# =========================================================================

# The substitutability category score is capped at 500 basis points
# to prevent it from dominating the overall score.
# Per G-SIB NPR p.18: "cap the substitutability / financial institution
# infrastructure category score at 500 basis points"
SUBSTITUTABILITY_CAP_BPS: Final[float] = 500.0  # G-SIB NPR p.18


# =========================================================================
#  Method 1 Surcharge Bands
#  Per G-SIB NPR Section II.C — US 2026 Re-Proposal
#  CRITICAL: 20bp score ranges / 0.1% surcharge increments
#  (NOT the Basel standard 100bp/0.5%)
# =========================================================================

# Method 1 score-to-surcharge mapping
# Per G-SIB NPR p.25: surcharge increases by 0.1% (10bp) for every
# 20bp increase in the G-SIB score above the 130bp initial threshold.
# Per CLAUDE.md: "G-SIB surcharge bands: 20bp score ranges / 0.1% increments"

METHOD_1_INITIAL_THRESHOLD_BPS: Final[float] = 130.0  # G-SIB NPR p.25
METHOD_1_BAND_WIDTH_BPS: Final[float] = 20.0  # 20bp score ranges — G-SIB NPR p.25 / CLAUDE.md
METHOD_1_SURCHARGE_INCREMENT_PCT: Final[float] = 0.1  # 0.1% per band — G-SIB NPR p.25 / CLAUDE.md
METHOD_1_MIN_SURCHARGE_PCT: Final[float] = 1.0  # Minimum surcharge for any G-SIB — G-SIB NPR p.25


# =========================================================================
#  Method 1 Score Scaling Factor
#  Per G-SIB NPR p.24, the raw score is divided by the denomination
#  factor (global aggregate of each indicator across all 75+ BCBS banks)
#  and multiplied by 10,000 to express in basis points.
# =========================================================================

METHOD_1_SCALING_FACTOR: Final[float] = 10_000.0  # Convert ratio to basis points


# =========================================================================
#  Method 2 — Short-Term Wholesale Funding
#  Per G-SIB NPR Section II.D / 12 CFR 217.406
#  CRITICAL: Coefficients adjusted by 1.2x DOWNWARD factor per CLAUDE.md
# =========================================================================

# Method 2 replaces the substitutability category with a short-term
# wholesale funding (STWF) indicator, then applies its own conversion
# table from scores to surcharge buckets.

# Method 2 uses the same 4 categories as Method 1 (size, interconnectedness,
# complexity, cross-jurisdictional) PLUS the STWF component.

# The STWF component is calculated using weighted-average residual maturity
# buckets for wholesale funding sources.
# Per G-SIB NPR pp.30-35

@dataclass(frozen=True)
class STWFBucketSpec:
    """Short-Term Wholesale Funding maturity bucket specification.

    Per G-SIB NPR p.32 / 12 CFR 217.406(b):
    Wholesale funding is bucketed by residual maturity and assigned
    weights that decrease with maturity.

    Attributes:
        min_days: Minimum residual maturity (inclusive)
        max_days: Maximum residual maturity (exclusive, None for open-ended)
        weight: Weight applied to funding in this bucket
        description: Human-readable bucket description
    """
    min_days: int
    max_days: int | None
    weight: float
    description: str


# STWF maturity buckets and weights
# Per G-SIB NPR p.32, Table 1
# These weights reflect the rollover risk — shorter maturities get higher weights.
STWF_MATURITY_BUCKETS: Final[list[STWFBucketSpec]] = [
    STWFBucketSpec(
        min_days=0, max_days=30,
        weight=0.25,
        description="Overnight to 30 days"
    ),
    STWFBucketSpec(
        min_days=31, max_days=90,
        weight=0.10,
        description="31 to 90 days"
    ),
    STWFBucketSpec(
        min_days=91, max_days=180,
        weight=0.03,
        description="91 to 180 days"
    ),
    STWFBucketSpec(
        min_days=181, max_days=365,
        weight=0.01,
        description="181 to 365 days"
    ),
]


# -------------------------------------------------------------------------
#  Method 2 STWF Score Coefficients
#  Per G-SIB NPR p.34 / 12 CFR 217.406(c)
#  CRITICAL: Adjusted by 1.2x DOWNWARD factor per 2026 Re-Proposal
#  Per CLAUDE.md: "G-SIB Method 2 coefficients adjusted by 1.2x downward factor"
# -------------------------------------------------------------------------

# The base (unadjusted) Method 2 conversion coefficients from the original
# 2015 rule. The 2026 Re-Proposal applies a 1.2x downward adjustment,
# meaning the effective coefficient = base / 1.2.

METHOD_2_DOWNWARD_FACTOR: Final[float] = 1.2  # Per CLAUDE.md / G-SIB NPR p.34

# Base Method 2 coefficient for converting STWF amount to score contribution.
# The STWF score = (STWF_weighted_amount / avg_total_assets) * coefficient * 10,000
# Per G-SIB NPR p.34
METHOD_2_BASE_COEFFICIENT: Final[float] = 350.0  # G-SIB NPR p.34
METHOD_2_ADJUSTED_COEFFICIENT: Final[float] = METHOD_2_BASE_COEFFICIENT / METHOD_2_DOWNWARD_FACTOR
# = 350.0 / 1.2 = 291.667


# =========================================================================
#  Method 2 Surcharge Bands
#  Per G-SIB NPR Section II.D / 12 CFR 217.406(d)
#  Same structure as Method 1: 20bp ranges / 0.1% increments
# =========================================================================

METHOD_2_INITIAL_THRESHOLD_BPS: Final[float] = 130.0  # G-SIB NPR p.36
METHOD_2_BAND_WIDTH_BPS: Final[float] = 20.0  # 20bp score ranges — CLAUDE.md
METHOD_2_SURCHARGE_INCREMENT_PCT: Final[float] = 0.1  # 0.1% per band — CLAUDE.md
METHOD_2_MIN_SURCHARGE_PCT: Final[float] = 1.0  # Minimum surcharge — G-SIB NPR p.36


# =========================================================================
#  Method 2 Category Weights
#  Per G-SIB NPR p.33 / 12 CFR 217.406(a)
#  Method 2 uses the same 4 systemic categories as Method 1 (excluding
#  substitutability) plus the STWF component. Each of the 5 components
#  receives 20% weight.
# =========================================================================

METHOD_2_CATEGORY_WEIGHT: Final[float] = 0.20  # 20% per component — G-SIB NPR p.33


# =========================================================================
#  G-SIB Score-to-Surcharge Conversion Table
#  Per G-SIB NPR pp.25-26, Table 2
#  Generated from the band parameters above.
#  Score range -> Surcharge (%)
#  Band 1: 130-149 bp -> 1.0%
#  Band 2: 150-169 bp -> 1.1%  (NOT 1.5% as in old Basel standard)
#  Band 3: 170-189 bp -> 1.2%
#  ... and so on in 20bp / 0.1% steps
# =========================================================================

def generate_surcharge_table(
    initial_threshold_bps: float = METHOD_1_INITIAL_THRESHOLD_BPS,
    band_width_bps: float = METHOD_1_BAND_WIDTH_BPS,
    surcharge_increment_pct: float = METHOD_1_SURCHARGE_INCREMENT_PCT,
    min_surcharge_pct: float = METHOD_1_MIN_SURCHARGE_PCT,
    max_bands: int = 50,
) -> list[tuple[float, float, float]]:
    """Generate the score-to-surcharge mapping table.

    Per G-SIB NPR pp.25-26 / 12 CFR 217.403(b):
    The surcharge is determined by where the G-SIB's systemic importance
    score falls within the band structure:
    - Scores below initial_threshold_bps: 1.0% minimum surcharge
    - Each additional band_width_bps of score: +surcharge_increment_pct

    Args:
        initial_threshold_bps: Score threshold for the first band (130bp)
        band_width_bps: Width of each score band (20bp)
        surcharge_increment_pct: Surcharge increase per band (0.1%)
        min_surcharge_pct: Minimum surcharge for any G-SIB (1.0%)
        max_bands: Maximum number of bands to generate

    Returns:
        List of (lower_bound_bps, upper_bound_bps, surcharge_pct) tuples.
        The last band has upper_bound = float('inf').
    """
    table: list[tuple[float, float, float]] = []
    for i in range(max_bands):
        lower = initial_threshold_bps + i * band_width_bps
        upper = initial_threshold_bps + (i + 1) * band_width_bps
        surcharge = min_surcharge_pct + i * surcharge_increment_pct

        if i == max_bands - 1:
            upper = float("inf")

        table.append((lower, upper, surcharge))

    return table


# Pre-generated surcharge tables for Method 1 and Method 2
METHOD_1_SURCHARGE_TABLE: Final[list[tuple[float, float, float]]] = generate_surcharge_table(
    initial_threshold_bps=METHOD_1_INITIAL_THRESHOLD_BPS,
    band_width_bps=METHOD_1_BAND_WIDTH_BPS,
    surcharge_increment_pct=METHOD_1_SURCHARGE_INCREMENT_PCT,
    min_surcharge_pct=METHOD_1_MIN_SURCHARGE_PCT,
)

METHOD_2_SURCHARGE_TABLE: Final[list[tuple[float, float, float]]] = generate_surcharge_table(
    initial_threshold_bps=METHOD_2_INITIAL_THRESHOLD_BPS,
    band_width_bps=METHOD_2_BAND_WIDTH_BPS,
    surcharge_increment_pct=METHOD_2_SURCHARGE_INCREMENT_PCT,
    min_surcharge_pct=METHOD_2_MIN_SURCHARGE_PCT,
)


# =========================================================================
#  Global Denomination Factors
#  Per G-SIB NPR p.24 / BCBS d445 Section 3.2
#  These are the aggregate amounts across all 75+ G-SIB sample banks
#  used to normalize individual bank indicators.
#  Updated annually by the BCBS; values below are illustrative for
#  the 2024 assessment exercise (based on end-2023 data).
# =========================================================================

@dataclass(frozen=True)
class DenominationFactors:
    """Global aggregate denomination factors for G-SIB score calculation.

    Per BCBS d445 / G-SIB NPR p.24:
    Each bank's raw indicator value is divided by the global aggregate
    for that indicator across all 75+ banks in the BCBS sample.

    All values in USD millions ($M).
    These are updated annually based on BCBS publications.
    """
    # Category 1: Size
    total_exposures: float

    # Category 2: Interconnectedness
    intra_financial_system_assets: float
    intra_financial_system_liabilities: float
    securities_outstanding: float

    # Category 3: Substitutability
    payments_activity: float
    assets_under_custody: float
    underwriting_activity: float

    # Category 4: Complexity
    otc_derivatives_notional: float
    trading_and_afs_securities: float
    level_3_assets: float

    # Category 5: Cross-Jurisdictional
    cross_jurisdictional_claims: float
    cross_jurisdictional_liabilities: float


# Default denomination factors based on 2024 BCBS assessment
# (end-2023 reporting data). These represent the sum across all
# 75+ banks in the sample for each indicator.
# Source: BCBS G-SIB assessment exercise results, November 2024
# TODO: VERIFY — These are illustrative values based on publicly available
# BCBS aggregate data. Actual values should be sourced from the official
# BCBS annual publication for the relevant assessment year.
DEFAULT_DENOMINATION_FACTORS: Final[DenominationFactors] = DenominationFactors(
    # Size — global aggregate ~€95T ($M equivalent)
    total_exposures=105_000_000.0,  # $105T in $M

    # Interconnectedness
    intra_financial_system_assets=12_500_000.0,   # $12.5T
    intra_financial_system_liabilities=13_000_000.0,  # $13T
    securities_outstanding=14_500_000.0,  # $14.5T

    # Substitutability
    payments_activity=2_800_000_000.0,  # $2,800T (annual flow)
    assets_under_custody=42_000_000.0,  # $42T
    underwriting_activity=8_500_000.0,  # $8.5T

    # Complexity
    otc_derivatives_notional=420_000_000.0,  # $420T
    trading_and_afs_securities=9_200_000.0,  # $9.2T
    level_3_assets=550_000.0,  # $550B

    # Cross-Jurisdictional
    cross_jurisdictional_claims=19_500_000.0,  # $19.5T
    cross_jurisdictional_liabilities=17_000_000.0,  # $17T
)


# =========================================================================
#  FR Y-15 Report Configuration
#  Per FR Y-15 instructions (OMB No. 7100-0352)
# =========================================================================

FR_Y15_REPORT_NAME: Final[str] = "FR Y-15"
FR_Y15_REPORT_TITLE: Final[str] = "Banking Organization Systemic Risk Report"
FR_Y15_OMB_NUMBER: Final[str] = "7100-0352"

# Reporting frequency: Quarterly for Category I G-SIBs
FR_Y15_FREQUENCY: Final[str] = "QUARTERLY"

# Assessment date: December 31 of each year (for annual G-SIB determination)
# Quarterly filings also required but annual determines surcharge
FR_Y15_ASSESSMENT_MONTH: Final[int] = 12
FR_Y15_ASSESSMENT_DAY: Final[int] = 31

# Schedules
FR_Y15_SCHEDULES: Final[dict[str, str]] = {
    "A": "Size Indicators",
    "B": "Interconnectedness Indicators",
    "C": "Substitutability Indicators",
    "D": "Complexity Indicators",
    "E": "Cross-Jurisdictional Activity Indicators",
    "F": "Ancillary Indicators",  # Not scored but reported
    "G": "Short-Term Wholesale Funding",  # Method 2 input
    "H": "G-SIB Surcharge Calculation",
}


# =========================================================================
#  Validation Bounds
#  Conservative bounds for data quality checks per BCBS 239
# =========================================================================

@dataclass(frozen=True)
class ValidationBounds:
    """Plausibility bounds for G-SIB indicator values.

    Per SR 11-7 / BCBS 239 data quality requirements.
    Values outside these bounds trigger validation warnings.
    All values in USD millions ($M).
    """
    # A Category I G-SIB should have total exposures between $500B and $10T
    min_total_exposures: float = 500_000.0  # $500B
    max_total_exposures: float = 10_000_000.0  # $10T

    # G-SIB scores should be between 0 and 2000 bps
    min_score_bps: float = 0.0
    max_score_bps: float = 2_000.0

    # Surcharge should be between 1.0% and 6.0% for any realistic G-SIB
    min_surcharge_pct: float = 1.0
    max_surcharge_pct: float = 6.0

    # STWF ratio should be between 0% and 100% of total assets
    min_stwf_ratio: float = 0.0
    max_stwf_ratio: float = 1.0


DEFAULT_VALIDATION_BOUNDS: Final[ValidationBounds] = ValidationBounds()
