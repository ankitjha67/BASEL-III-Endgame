"""Credit Risk module — SA-CR and IRB approaches (Phase 4).

Includes:
    - SA-CR: Standardized Approach to Credit Risk
    - OBS/CCF: Off-Balance Sheet Credit Conversion Factors (12 CFR 217.33)
"""

from src.credit_risk.sa.obs_ccf import (
    OBSCategory,
    OBSCCFCalculator,
    OBSExposure,
    OBSResult,
)
