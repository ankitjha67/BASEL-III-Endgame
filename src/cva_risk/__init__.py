"""CVA risk module — ERBA NPR §__.220–§__.225 (March 2026 US re-proposal).

Implements the credit valuation adjustment risk capital framework:
    - BA-CVA (§__.222): K_basic = 0.65·(β·K_unhedged + (1−β)·K_hedged),
      supervisory risk weights from Table 1 to §__.222 by sector and
      bank-internal credit quality, alpha 1.4 / 1.0, single-name and index
      hedge recognition with Table 2 correlations.
    - SA-CVA (§__.224–§__.225): sensitivities-based delta and vega capital
      requirements across six risk classes with Tables 1–9 risk weights
      and correlations, R = 0.01 hedging disallowance, m_CVA multiplier.

Usage::

    from src.cva_risk import CVACalculator, CVACounterparty

    calc = CVACalculator()
    result = calc.calculate([
        CVACounterparty(counterparty_id="CP1", sector="FINANCIALS",
                        credit_quality="IG", ead=500.0, effective_maturity=3.0),
    ])
    print(f"CVA RWA: ${result.rwa:,.0f}M")

All monetary amounts in USD millions ($M).
"""

from src.cva_risk.ba_cva import (
    BACVACalculator,
    BACVACounterparty,
    BACVACounterpartyResult,
    BACVAHedge,
    BACVAHedgeResult,
    BACVAIndexConstituent,
    BACVANettingSet,
    BACVAPosition,
    BACVAResult,
    compute_ba_cva_rwa,
    compute_k_basic,
    compute_k_hedged,
    compute_k_unhedged,
    compute_scva,
    compute_scva_summary,
)
from src.cva_risk.cva_calculator import (
    CVACalculator,
    CVACapitalResult,
    CVACounterparty,
    CVAEligibility,
    CVAHedge,
    CVAScopeDetermination,
    determine_cva_scope,
    determine_eligibility,
    is_cva_risk_covered_position,
)
from src.cva_risk.cva_params import (
    BA_CVA_ALPHA_COMMERCIAL_END_USER,
    BA_CVA_ALPHA_DEFAULT,
    BA_CVA_BETA,
    BA_CVA_DISCOUNT_RATE,
    BA_CVA_DISCOUNT_SCALAR,
    BA_CVA_HEDGE_CORRELATION,
    BA_CVA_INDEX_HEDGE_FACTOR,
    BA_CVA_RHO,
    BA_CVA_RISK_WEIGHT_TABLE,
    BA_CVA_RISK_WEIGHTS,
    CVA_SCOPE_OTC_NOTIONAL_THRESHOLD,
    RWA_MULTIPLIER,
    SA_CVA_CCS_GAMMA,
    SA_CVA_HEDGING_DISALLOWANCE_R,
    SA_CVA_MULTIPLIER_DEFAULT,
    SA_CVA_RCS_GAMMA,
    SACCR_ALPHA_COMMERCIAL,
    SACCR_ALPHA_FINANCIAL,
    BACVAHedgeRelationship,
    CVAApproach,
    CVACreditQuality,
    CVAHedgeType,
    CVASector,
    SACVARiskClass,
    SACVARiskFactorType,
    credit_quality_from_grade,
    get_ba_cva_alpha,
    get_ba_cva_risk_weight,
    get_saccr_alpha,
    netting_set_effective_maturity,
    normalize_sector,
    supervisory_discount_factor,
)
from src.cva_risk.sa_cva import (
    SACVABucketResult,
    SACVACalculator,
    SACVAFactorResult,
    SACVAResult,
    SACVARiskClassResult,
    SACVASensitivity,
)

__all__ = [
    # Main calculator
    "CVACalculator",
    "CVACapitalResult",
    "CVACounterparty",
    "CVAEligibility",
    "CVAHedge",
    "CVAScopeDetermination",
    "determine_cva_scope",
    "determine_eligibility",
    "is_cva_risk_covered_position",
    # BA-CVA
    "BACVACalculator",
    "BACVACounterparty",
    "BACVACounterpartyResult",
    "BACVAHedge",
    "BACVAHedgeResult",
    "BACVAIndexConstituent",
    "BACVANettingSet",
    "BACVAPosition",
    "BACVAResult",
    "compute_ba_cva_rwa",
    "compute_k_basic",
    "compute_k_hedged",
    "compute_k_unhedged",
    "compute_scva",
    "compute_scva_summary",
    # SA-CVA
    "SACVABucketResult",
    "SACVACalculator",
    "SACVAFactorResult",
    "SACVAResult",
    "SACVARiskClassResult",
    "SACVASensitivity",
    # Enums and parameters
    "BACVAHedgeRelationship",
    "CVAApproach",
    "CVACreditQuality",
    "CVAHedgeType",
    "CVASector",
    "SACVARiskClass",
    "SACVARiskFactorType",
    "BA_CVA_ALPHA_COMMERCIAL_END_USER",
    "BA_CVA_ALPHA_DEFAULT",
    "BA_CVA_BETA",
    "BA_CVA_DISCOUNT_RATE",
    "BA_CVA_DISCOUNT_SCALAR",
    "BA_CVA_HEDGE_CORRELATION",
    "BA_CVA_INDEX_HEDGE_FACTOR",
    "BA_CVA_RHO",
    "BA_CVA_RISK_WEIGHT_TABLE",
    "BA_CVA_RISK_WEIGHTS",
    "CVA_SCOPE_OTC_NOTIONAL_THRESHOLD",
    "RWA_MULTIPLIER",
    "SA_CVA_CCS_GAMMA",
    "SA_CVA_HEDGING_DISALLOWANCE_R",
    "SA_CVA_MULTIPLIER_DEFAULT",
    "SA_CVA_RCS_GAMMA",
    "SACCR_ALPHA_COMMERCIAL",
    "SACCR_ALPHA_FINANCIAL",
    "credit_quality_from_grade",
    "get_ba_cva_alpha",
    "get_ba_cva_risk_weight",
    "get_saccr_alpha",
    "netting_set_effective_maturity",
    "normalize_sector",
    "supervisory_discount_factor",
]
