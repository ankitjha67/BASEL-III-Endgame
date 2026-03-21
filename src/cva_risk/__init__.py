"""CVA Risk module — SA-CVA and BA-CVA approaches.

Implements the Credit Valuation Adjustment risk capital framework
per BCBS d424, BCBS d457 MAR50/MAR51, and the US Federal Reserve
Basel III Endgame Re-Proposal (ERBA NPR pp. 280-295).

Provides two approaches:
    - SA-CVA: Standardized Approach using sensitivity-based delta/vega framework
    - BA-CVA: Basic Approach using formula-based supervisory risk weights

Usage::

    from src.cva_risk import CVACalculator, CVACounterparty

    calculator = CVACalculator()
    result = calculator.calculate([
        CVACounterparty(counterparty_id="CP1", rating="A", ead=500.0),
    ])
    print(f"CVA RWA: ${result.rwa:,.0f}M")
"""

from src.cva_risk.ba_cva import (
    BACVACalculator,
    BACVACounterparty,
    BACVAHedge,
    BACVAResult,
)
from src.cva_risk.cva_calculator import (
    CVACalculator,
    CVACapitalResult,
    CVACounterparty,
    CVAEligibility,
    CVAHedge,
    determine_eligibility,
)
from src.cva_risk.cva_params import (
    BA_CVA_ALPHA,
    BA_CVA_BETA,
    BA_CVA_RHO,
    BA_CVA_RISK_WEIGHTS,
    CVAApproach,
    CVACreditQuality,
    CVAHedgeType,
    CVARating,
    CVASector,
    RWA_MULTIPLIER,
    SA_CVA_BUCKETS,
    SA_CVA_INTER_BUCKET_CORRELATION,
    SA_CVA_INTRA_BUCKET_CORRELATION,
    SA_CVA_RISK_TYPE_CORRELATION,
    SACCR_ALPHA_COMMERCIAL,
    SACCR_ALPHA_FINANCIAL,
    SACVARiskFactorType,
)
from src.cva_risk.sa_cva import (
    SACVACalculator,
    SACVACounterparty,
    SACVAHedge,
    SACVAResult,
)

__all__ = [
    # Main calculator
    "CVACalculator",
    "CVACapitalResult",
    "CVACounterparty",
    "CVAEligibility",
    "CVAHedge",
    "determine_eligibility",
    # BA-CVA
    "BACVACalculator",
    "BACVACounterparty",
    "BACVAHedge",
    "BACVAResult",
    # SA-CVA
    "SACVACalculator",
    "SACVACounterparty",
    "SACVAHedge",
    "SACVAResult",
    # Enums and params
    "CVAApproach",
    "CVACreditQuality",
    "CVAHedgeType",
    "CVARating",
    "CVASector",
    "SACVARiskFactorType",
    "BA_CVA_ALPHA",
    "BA_CVA_BETA",
    "BA_CVA_RHO",
    "BA_CVA_RISK_WEIGHTS",
    "RWA_MULTIPLIER",
    "SA_CVA_BUCKETS",
    "SA_CVA_INTER_BUCKET_CORRELATION",
    "SA_CVA_INTRA_BUCKET_CORRELATION",
    "SA_CVA_RISK_TYPE_CORRELATION",
    "SACCR_ALPHA_COMMERCIAL",
    "SACCR_ALPHA_FINANCIAL",
]
