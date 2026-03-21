"""Reference data module — counterparty, instrument, and regulatory lookups.

Provides the foundational reference data layer for the Basel III Endgame
capital engine. No dependencies on other calculation modules.

Reference: ERBA NPR pp. 100-160, BCBS d457, 12 CFR 217.32.
"""

from src.reference_data.counterparty_reference import (
    CounterpartyRecord,
    CounterpartyRegistry,
    CounterpartyType,
    DomicileRegion,
    IndustryClassification,
    NettingSet,
    SovereignRiskCategory,
    classify_counterparty_type,
    get_sa_ccr_alpha,
)
from src.reference_data.instrument_reference import (
    BookClassification,
    CollateralType,
    InstrumentRecord,
    InstrumentType,
    SACCRAssetClass,
    SecuritizationType,
    classify_book,
    get_saccr_asset_class,
    is_derivative,
    is_securitization,
    is_sft,
)
from src.reference_data.regulatory_lookups import (
    CRE_RW_BY_LTV,
    RESIDENTIAL_MORTGAGE_RW_BY_LTV,
    SA_CR_RISK_WEIGHTS,
    SOVEREIGN_RISK_WEIGHTS,
    get_risk_weight,
)

__all__ = [
    # Counterparty reference
    "CounterpartyRecord",
    "CounterpartyRegistry",
    "CounterpartyType",
    "DomicileRegion",
    "IndustryClassification",
    "NettingSet",
    "SovereignRiskCategory",
    "classify_counterparty_type",
    "get_sa_ccr_alpha",
    # Instrument reference
    "BookClassification",
    "CollateralType",
    "InstrumentRecord",
    "InstrumentType",
    "SACCRAssetClass",
    "SecuritizationType",
    "classify_book",
    "get_saccr_asset_class",
    "is_derivative",
    "is_securitization",
    "is_sft",
    # Regulatory lookups
    "CRE_RW_BY_LTV",
    "RESIDENTIAL_MORTGAGE_RW_BY_LTV",
    "SA_CR_RISK_WEIGHTS",
    "SOVEREIGN_RISK_WEIGHTS",
    "get_risk_weight",
]
