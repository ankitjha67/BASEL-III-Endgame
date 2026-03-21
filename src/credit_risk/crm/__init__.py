"""Credit Risk Mitigation (CRM) module.

Implements the Comprehensive Approach (haircuts) and Substitution Approach
(guarantees/credit derivatives) per MAR22 / CRE22.
"""

from src.credit_risk.crm.crm import (
    CollateralType,
    CRMCollateral,
    CRMExposure,
    CRMGuarantee,
    CRMResult,
    CRMCalculator,
    SUPERVISORY_HAIRCUTS,
    CURRENCY_MISMATCH_HAIRCUT,
)

__all__ = [
    "CollateralType",
    "CRMCollateral",
    "CRMExposure",
    "CRMGuarantee",
    "CRMResult",
    "CRMCalculator",
    "SUPERVISORY_HAIRCUTS",
    "CURRENCY_MISMATCH_HAIRCUT",
]
