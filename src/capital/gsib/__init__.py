"""G-SIB Surcharge Module — Basel III Endgame 2026.

Implements the G-SIB capital surcharge calculation per:
- G-SIB NPR (128 pages): "Risk-Based Capital Surcharges for GSIBs"
- 12 CFR 217 Subpart H: G-SIB Surcharge
- FR Y-15: Banking Organization Systemic Risk Report

Key features:
- Method 1: BCBS substitutability-based (12 indicators, 5 categories)
- Method 2: US-specific STWF-based (1.2x downward adjustment)
- Higher-of Method 1 vs Method 2 determination
- Surcharge bands: 20bp score ranges / 0.1% increments
- FR Y-15 report generation
- Sensitivity and what-if analysis

Per CLAUDE.md:
- G-SIB Method 2 coefficients adjusted by 1.2x downward factor
- G-SIB surcharge bands: 20bp score ranges / 0.1% increments (NOT 100bp/0.5%)
"""

from src.capital.gsib.gsib_calculator import (
    GSIBCalculator,
    GSIBSurchargeResult,
    MethodResult,
    calculate_gsib_surcharge,
    create_indicator_data_from_dict,
    get_surcharge_for_score,
    score_to_method1_surcharge,
    score_to_method2_surcharge,
)
from src.capital.gsib.gsib_indicators import (
    CategoryScore,
    GSIBIndicatorData,
    IndicatorValue,
    STWFBucketValue,
    STWFScore,
    calculate_category_scores,
    calculate_indicator_score,
    calculate_method1_score,
    calculate_method2_score,
    calculate_stwf_score,
    validate_indicator_data,
)
from src.capital.gsib.gsib_params import (
    CATEGORY_WEIGHT,
    DEFAULT_DENOMINATION_FACTORS,
    DenominationFactors,
    GSIBCategory,
    GSIBIndicatorCategory,
    GSIBMethod,
    INDICATOR_LOOKUP,
    METHOD_1_BAND_WIDTH_BPS,
    METHOD_1_INDICATORS,
    METHOD_1_INITIAL_THRESHOLD_BPS,
    METHOD_1_MIN_SURCHARGE_PCT,
    METHOD_1_SURCHARGE_INCREMENT_PCT,
    METHOD_2_ADJUSTED_COEFFICIENT,
    METHOD_2_BASE_COEFFICIENT,
    METHOD_2_DOWNWARD_FACTOR,
    SUBSTITUTABILITY_CAP_BPS,
    IndicatorSpec,
)
from src.capital.gsib.gsib_reporting import (
    FRY15Report,
    FRY15Schedule,
    FRY15ScheduleLineItem,
    MethodComparisonReport,
    SurchargeBucketReport,
    format_fr_y15_text,
    format_method_comparison_text,
    format_surcharge_bucket_text,
    fr_y15_report_to_dict,
    generate_fr_y15_report,
    generate_method_comparison,
    generate_surcharge_bucket_report,
    surcharge_result_to_dict,
)

__all__ = [
    # Calculator
    "GSIBCalculator",
    "GSIBSurchargeResult",
    "MethodResult",
    "calculate_gsib_surcharge",
    "create_indicator_data_from_dict",
    "get_surcharge_for_score",
    "score_to_method1_surcharge",
    "score_to_method2_surcharge",
    # Indicators
    "CategoryScore",
    "GSIBIndicatorData",
    "IndicatorValue",
    "STWFBucketValue",
    "STWFScore",
    "calculate_category_scores",
    "calculate_indicator_score",
    "calculate_method1_score",
    "calculate_method2_score",
    "calculate_stwf_score",
    "validate_indicator_data",
    # Params
    "CATEGORY_WEIGHT",
    "DEFAULT_DENOMINATION_FACTORS",
    "DenominationFactors",
    "GSIBCategory",
    "GSIBIndicatorCategory",
    "GSIBMethod",
    "INDICATOR_LOOKUP",
    "IndicatorSpec",
    "METHOD_1_BAND_WIDTH_BPS",
    "METHOD_1_INDICATORS",
    "METHOD_1_INITIAL_THRESHOLD_BPS",
    "METHOD_1_MIN_SURCHARGE_PCT",
    "METHOD_1_SURCHARGE_INCREMENT_PCT",
    "METHOD_2_ADJUSTED_COEFFICIENT",
    "METHOD_2_BASE_COEFFICIENT",
    "METHOD_2_DOWNWARD_FACTOR",
    "SUBSTITUTABILITY_CAP_BPS",
    # Reporting
    "FRY15Report",
    "FRY15Schedule",
    "FRY15ScheduleLineItem",
    "MethodComparisonReport",
    "SurchargeBucketReport",
    "format_fr_y15_text",
    "format_method_comparison_text",
    "format_surcharge_bucket_text",
    "fr_y15_report_to_dict",
    "generate_fr_y15_report",
    "generate_method_comparison",
    "generate_surcharge_bucket_report",
    "surcharge_result_to_dict",
]
