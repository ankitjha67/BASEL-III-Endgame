"""SA-CCR — Standardized Approach for Counterparty Credit Risk.

Implements the full SA-CCR methodology per CRE52 for computing
Exposure at Default (EAD) for OTC derivative netting sets.
"""

from src.counterparty_risk.saccr.saccr import (
    SACCRCalculator,
    SACCRNettingSet,
    SACCRResult,
    SACCRTrade,
    adjusted_notional,
    supervisory_duration,
    trade_level_addon,
)
from src.counterparty_risk.saccr.saccr_params import (
    ALPHA_FINANCIAL,
    ALPHA_NON_FINANCIAL,
    PFE_FLOOR,
    SACCR_ASSET_CLASS_PARAMS,
    SACCR_ASSET_CLASSES,
    SACCRAssetClass,
    AssetClassParams,
    IRMaturityBucket,
    ir_maturity_bucket,
)

__all__ = [
    # Calculator & models
    "SACCRCalculator",
    "SACCRNettingSet",
    "SACCRResult",
    "SACCRTrade",
    # Functions
    "adjusted_notional",
    "supervisory_duration",
    "trade_level_addon",
    # Parameters
    "ALPHA_FINANCIAL",
    "ALPHA_NON_FINANCIAL",
    "PFE_FLOOR",
    "SACCR_ASSET_CLASS_PARAMS",
    "SACCR_ASSET_CLASSES",
    "SACCRAssetClass",
    "AssetClassParams",
    "IRMaturityBucket",
    "ir_maturity_bucket",
]
