"""PD (Probability of Default) Models sub-package.

Provides TTC PD, PIT PD, PD term structures, migration matrices,
and through-the-cycle calibration for ECL calculations.

References:
    - BCBS d350 §4.1-4.3: PD estimation requirements
    - ASC 326-20-30: CECL measurement — PD/LGD approach
    - IFRS 9 §5.5.9-5.5.11: PD estimation for ECL
"""

from src.ecl.pd_models.pd_params import (
    MASTER_SCALE_PD,
    RATING_TO_PD,
    SECTOR_CORRELATION_FACTORS,
    TTC_TO_PIT_SCALARS,
    MIGRATION_MATRIX_IG,
    MIGRATION_MATRIX_HY,
    PD_FLOOR,
    PD_CAP,
    ASSET_CORRELATION_PARAMS,
)
from src.ecl.pd_models.pd_models import (
    PDModel,
    PDTermStructure,
    MigrationMatrix,
    TTCCalibrator,
    PITPDModel,
    PDModelResult,
)

__all__ = [
    "MASTER_SCALE_PD",
    "RATING_TO_PD",
    "SECTOR_CORRELATION_FACTORS",
    "TTC_TO_PIT_SCALARS",
    "MIGRATION_MATRIX_IG",
    "MIGRATION_MATRIX_HY",
    "PD_FLOOR",
    "PD_CAP",
    "ASSET_CORRELATION_PARAMS",
    "PDModel",
    "PDTermStructure",
    "MigrationMatrix",
    "TTCCalibrator",
    "PITPDModel",
    "PDModelResult",
]
