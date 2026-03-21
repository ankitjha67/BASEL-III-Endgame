"""Credit Risk module — SA-CR and IRB approaches (Phase 4).

Includes:
    - SA-CR: Standardized Approach to Credit Risk
    - OBS/CCF: Off-Balance Sheet Credit Conversion Factors (12 CFR 217.33)
    - Large Exposures: Single-Counterparty Credit Limits (12 CFR 252 Subpart J)
"""

from src.credit_risk.sa.obs_ccf import (
    OBSCategory,
    OBSCCFCalculator,
    OBSExposure,
    OBSResult,
)
from src.credit_risk.large_exposures import (
    LargeExposureCalculator,
    LargeExposureSummary,
    LargeExposureResult,
    CounterpartyExposure as LECounterpartyExposure,
    CounterpartyGroup,
)
