"""Default risk capital requirement -- ERBA NPR §__.210 (BCBS d457 MAR22 cross-reference).

Provides calculators for:

- **Non-securitization** (``drc_nonsec``): bonds, loans, CDS, equity
  (§__.210(b)).
- **Securitization non-CTP** (``drc_sec_nonctp``): ABS, RMBS, CMBS, CLO
  tranches (§__.210(c)).
- **Correlation trading portfolio** (``drc_sec_ctp``): index tranches,
  nth-to-default, bespokes and their non-securitization hedges (§__.210(d)).

Regulatory parameters (LGD, Table 1 risk weights, maturity scaling,
SEC-SA x 8% conversion, CTP aggregation factor) live in ``drc_params``.
"""

from src.market_risk.frtb.drc.drc_nonsec import (
    DRCBucketDetail,
    DRCCalculator,
    DRCPosition,
    DRCResult,
)
from src.market_risk.frtb.drc.drc_params import (
    CTP_NEGATIVE_BUCKET_FACTOR,
    DRC_DEFAULTED_RISK_WEIGHT,
    DRC_RISK_WEIGHTS,
    DRC_SEC_CAPITAL_CONVERSION,
    DRC_SENIORITY_RANK,
    LEGACY_DRC_SEC_RISK_WEIGHTS_NON_SENIOR,
    LEGACY_DRC_SEC_RISK_WEIGHTS_SENIOR,
    LGD_VALUES,
    RATING_TO_CREDIT_QUALITY,
    compute_hedge_benefit_ratio,
    compute_maturity_weight,
    compute_sec_sa_risk_weight,
    get_bucket,
    get_bucket_label,
    get_legacy_sec_risk_weight,
    get_lgd,
    get_risk_weight,
    get_sec_drc_risk_weight,
    get_seniority_rank,
    rating_to_credit_quality,
)
from src.market_risk.frtb.drc.drc_sec_ctp import (
    DRCSecCTPBucketDetail,
    DRCSecCTPCalculator,
    DRCSecCTPPosition,
    DRCSecCTPResult,
)
from src.market_risk.frtb.drc.drc_sec_nonctp import (
    DRCSecBucketDetail,
    DRCSecNonCTPCalculator,
    DRCSecNonCTPPosition,
    DRCSecNonCTPResult,
    resolve_sec_drc_risk_weight,
)

__all__ = [
    # Non-securitization
    "DRCBucketDetail",
    "DRCCalculator",
    "DRCPosition",
    "DRCResult",
    # Securitization Non-CTP
    "DRCSecBucketDetail",
    "DRCSecNonCTPCalculator",
    "DRCSecNonCTPPosition",
    "DRCSecNonCTPResult",
    "resolve_sec_drc_risk_weight",
    # Securitization CTP
    "DRCSecCTPBucketDetail",
    "DRCSecCTPCalculator",
    "DRCSecCTPPosition",
    "DRCSecCTPResult",
    # Parameters
    "CTP_NEGATIVE_BUCKET_FACTOR",
    "DRC_DEFAULTED_RISK_WEIGHT",
    "DRC_RISK_WEIGHTS",
    "DRC_SEC_CAPITAL_CONVERSION",
    "DRC_SENIORITY_RANK",
    "LEGACY_DRC_SEC_RISK_WEIGHTS_NON_SENIOR",
    "LEGACY_DRC_SEC_RISK_WEIGHTS_SENIOR",
    "LGD_VALUES",
    "RATING_TO_CREDIT_QUALITY",
    "compute_hedge_benefit_ratio",
    "compute_maturity_weight",
    "compute_sec_sa_risk_weight",
    "get_bucket",
    "get_bucket_label",
    "get_legacy_sec_risk_weight",
    "get_lgd",
    "get_risk_weight",
    "get_sec_drc_risk_weight",
    "get_seniority_rank",
    "rating_to_credit_quality",
]
