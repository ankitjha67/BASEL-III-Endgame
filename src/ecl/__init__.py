"""Expected Credit Loss (ECL) Module — CECL and IFRS 9 Implementation.

Implements the Current Expected Credit Losses (CECL) methodology per
ASC 326 (Financial Instruments — Credit Losses) for US banking organizations,
with parallel support for IFRS 9 (International Financial Reporting Standard 9)
staging and measurement for international subsidiaries.

For a Category I US G-SIB, the CECL model is the primary accounting standard
for credit loss provisioning. The ECL module provides:

  - PD Models: Through-the-cycle (TTC) and point-in-time (PIT) probability
    of default, PD term structures, migration matrices, and calibration
  - LGD Models: Downturn LGD, workout LGD, collateral recovery, cure rates
  - EAD Models: Credit conversion factors (CCF), undrawn commitments,
    off-balance sheet exposures
  - ECL Calculator: Stage 1 (12-month), Stage 2 (lifetime), Stage 3
    (credit-impaired) ECL computation with forward-looking scenarios
  - Staging Engine: IFRS 9 / CECL stage assignment, SICR assessment,
    backstop indicators, and transfer criteria

References:
    - ASC 326: Financial Instruments — Credit Losses (CECL)
    - IFRS 9: Financial Instruments (July 2014)
    - BCBS d350: Guidance on Credit Risk and Accounting for ECL (Dec 2015)
    - SR 11-7: Supervisory Guidance on Model Risk Management
    - FASB ASU 2016-13: Measurement of Credit Losses on Financial Instruments
    - Federal Reserve SR 20-15: Interagency Policy Statement on Allowances
    - OCC Bulletin 2020-49: CECL Implementation Guidance
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
from src.ecl.lgd_models import (
    LGDModel,
    CollateralRecoveryModel,
    WorkoutLGDModel,
    DownturnLGDModel,
    LGDResult,
    CureRateModel,
)
from src.ecl.ead_models import (
    EADModel,
    CCFModel,
    UndrawnCommitmentModel,
    OffBalanceSheetModel,
    EADResult,
)
from src.ecl.staging import (
    StagingEngine,
    StageAssignment,
    SICRAssessment,
    SICRIndicator,
    Stage,
)
from src.ecl.ecl_calculator import (
    ECLCalculator,
    ECLResult,
    ECLExposure,
    MacroeconomicScenario,
    ScenarioWeight,
    ECLPortfolioResult,
)

__all__ = [
    # PD parameters
    "MASTER_SCALE_PD",
    "RATING_TO_PD",
    "SECTOR_CORRELATION_FACTORS",
    "TTC_TO_PIT_SCALARS",
    "MIGRATION_MATRIX_IG",
    "MIGRATION_MATRIX_HY",
    "PD_FLOOR",
    "PD_CAP",
    "ASSET_CORRELATION_PARAMS",
    # PD models
    "PDModel",
    "PDTermStructure",
    "MigrationMatrix",
    "TTCCalibrator",
    "PITPDModel",
    "PDModelResult",
    # LGD models
    "LGDModel",
    "CollateralRecoveryModel",
    "WorkoutLGDModel",
    "DownturnLGDModel",
    "LGDResult",
    "CureRateModel",
    # EAD models
    "EADModel",
    "CCFModel",
    "UndrawnCommitmentModel",
    "OffBalanceSheetModel",
    "EADResult",
    # Staging
    "StagingEngine",
    "StageAssignment",
    "SICRAssessment",
    "SICRIndicator",
    "Stage",
    # ECL calculator
    "ECLCalculator",
    "ECLResult",
    "ECLExposure",
    "MacroeconomicScenario",
    "ScenarioWeight",
    "ECLPortfolioResult",
]
