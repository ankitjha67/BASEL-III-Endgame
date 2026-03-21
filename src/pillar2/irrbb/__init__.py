"""IRRBB — Interest Rate Risk in the Banking Book.

Implements EVE and NII shock calculations per BCBS d368.
"""

from src.pillar2.irrbb.irrbb_params import (
    IRRBB_SCENARIO_NAMES,
    IRRBBScenario,
    IRRBBShockParams,
    DEFAULT_USD_SHOCKS,
    CURRENCY_SPECIFIC_SHOCKS,
    AUTOMATIC_CAP_FLOOR,
    EVE_FLOOR_RATE,
    NII_HORIZON_YEARS,
    TIME_BUCKETS_MIDPOINTS,
)
from src.pillar2.irrbb.irrbb_calculator import (
    CashFlowBucket,
    EVEResult,
    IRRBBResult,
    NIIResult,
    calculate_eve_change,
    calculate_nii_change,
    compute_irrbb,
)

__all__ = [
    "IRRBB_SCENARIO_NAMES",
    "IRRBBScenario",
    "IRRBBShockParams",
    "DEFAULT_USD_SHOCKS",
    "CURRENCY_SPECIFIC_SHOCKS",
    "AUTOMATIC_CAP_FLOOR",
    "EVE_FLOOR_RATE",
    "NII_HORIZON_YEARS",
    "TIME_BUCKETS_MIDPOINTS",
    "CashFlowBucket",
    "EVEResult",
    "IRRBBResult",
    "NIIResult",
    "calculate_eve_change",
    "calculate_nii_change",
    "compute_irrbb",
]
