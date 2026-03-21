"""SA-CR — Standardized Approach to Credit Risk.

Implements the US Basel III Endgame / Federal Reserve re-proposal for
credit risk capital requirements under the Standardized Approach.

Key divergences from the Basel Committee international standard:
  - No external credit ratings (Dodd-Frank Act Section 939A)
  - CRC-based risk weights for sovereign and bank exposures
  - Self-assessed investment-grade for 65% corporate risk weight
  - Transactor treatment (45%) for qualifying retail credit cards
  - MSA 250% risk weight (deduction threshold removed in 2026)

Modules:
    exposure_classes: Exposure classification taxonomy and logic
    risk_weights: Risk weight tables and lookup functions
    calculator: RWA calculation engine and result models

References:
    - Federal Reserve Basel III Endgame NPR (July 2023, re-proposed Sept 2025)
    - 12 CFR Part 217, Subpart E
    - Basel Committee CRE20-CRE22
"""

from src.credit_risk.sa.exposure_classes import (
    CRESubType,
    EquitySubType,
    ExposureClass,
    ExposureClassificationCriteria,
    PSEObligationType,
    QUALIFYING_MDBS,
    classify_exposure,
    get_cre_ltv_bucket,
    get_resi_mortgage_ltv_bucket,
    is_qualifying_mdb,
)
from src.credit_risk.sa.risk_weights import (
    RiskWeightInput,
    RiskWeightSchedule,
    get_risk_weight,
    get_sovereign_risk_weight,
    get_bank_risk_weight,
    get_corporate_risk_weight,
    get_residential_mortgage_risk_weight,
    get_cre_risk_weight,
    get_equity_risk_weight,
    get_pse_risk_weight,
    get_mdb_risk_weight,
)
from src.credit_risk.sa.calculator import (
    CreditExposure,
    ExposureClassResult,
    ExposureResult,
    SACRCalculator,
    SACRResult,
    build_exposure,
    calculate_sacr_rwa,
)

__all__ = [
    # Enums
    "CRESubType",
    "EquitySubType",
    "ExposureClass",
    "PSEObligationType",
    # Classification
    "ExposureClassificationCriteria",
    "QUALIFYING_MDBS",
    "classify_exposure",
    "get_cre_ltv_bucket",
    "get_resi_mortgage_ltv_bucket",
    "is_qualifying_mdb",
    # Risk weights
    "RiskWeightInput",
    "RiskWeightSchedule",
    "get_risk_weight",
    "get_sovereign_risk_weight",
    "get_bank_risk_weight",
    "get_corporate_risk_weight",
    "get_residential_mortgage_risk_weight",
    "get_cre_risk_weight",
    "get_equity_risk_weight",
    "get_pse_risk_weight",
    "get_mdb_risk_weight",
    # Calculator
    "CreditExposure",
    "ExposureClassResult",
    "ExposureResult",
    "SACRCalculator",
    "SACRResult",
    "build_exposure",
    "calculate_sacr_rwa",
]
