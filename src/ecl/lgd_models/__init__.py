"""LGD Models — Loss Given Default estimation for ECL calculation.

Provides downturn LGD, workout LGD, collateral recovery, and cure rate
models per BCBS d350 and ASC 326 / IFRS 9 requirements.

References:
    - BCBS d350 §5.1-5.3: LGD estimation requirements
    - BCBS d424 CRE32.14-32.16: IRB supervisory LGD values
    - ASC 326-20-30-5: Loss rate estimation for CECL
    - IFRS 9 §B5.5.28-B5.5.34: LGD measurement
"""

from src.ecl.lgd_models.lgd_models import (
    LGDModel,
    CollateralRecoveryModel,
    WorkoutLGDModel,
    DownturnLGDModel,
    LGDResult,
    CureRateModel,
)

__all__ = [
    "LGDModel",
    "CollateralRecoveryModel",
    "WorkoutLGDModel",
    "DownturnLGDModel",
    "LGDResult",
    "CureRateModel",
]
