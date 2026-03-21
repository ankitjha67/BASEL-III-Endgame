"""DRC (Default Risk Charge) module -- FRTB MAR22.

Provides calculators for the Default Risk Charge across:

- **Non-securitization** (``drc_nonsec``): Bonds, loans, CDS, equity.
- **Securitization Non-CTP** (``drc_sec_nonctp``): RMBS, CMBS, ABS, CLO.
- **Securitization CTP** (``drc_sec_ctp``): Index tranches, nth-to-default, bespoke CDOs.

Regulatory parameters (LGD tables, risk weights, maturity weighting)
are centralised in ``drc_params``.
"""

from src.market_risk.frtb.drc.drc_nonsec import (
    DRCCalculator,
    DRCPosition,
    DRCResult,
)
from src.market_risk.frtb.drc.drc_params import (
    CTP_HEDGE_BENEFIT_RATIO,
    DRC_RISK_WEIGHTS,
    DRC_SEC_LGD,
    DRC_SEC_RISK_WEIGHTS_NON_SENIOR,
    DRC_SEC_RISK_WEIGHTS_SENIOR,
    LGD_VALUES,
    compute_maturity_weight,
    get_lgd,
    get_risk_weight,
    get_sec_risk_weight,
)
from src.market_risk.frtb.drc.drc_sec_ctp import (
    DRCSecCTPCalculator,
    DRCSecCTPPosition,
    DRCSecCTPResult,
)
from src.market_risk.frtb.drc.drc_sec_nonctp import (
    DRCSecNonCTPCalculator,
    DRCSecNonCTPPosition,
    DRCSecNonCTPResult,
)

__all__ = [
    # Non-securitization
    "DRCCalculator",
    "DRCPosition",
    "DRCResult",
    # Securitization Non-CTP
    "DRCSecNonCTPCalculator",
    "DRCSecNonCTPPosition",
    "DRCSecNonCTPResult",
    # Securitization CTP
    "DRCSecCTPCalculator",
    "DRCSecCTPPosition",
    "DRCSecCTPResult",
    # Parameters
    "CTP_HEDGE_BENEFIT_RATIO",
    "DRC_RISK_WEIGHTS",
    "DRC_SEC_LGD",
    "DRC_SEC_RISK_WEIGHTS_NON_SENIOR",
    "DRC_SEC_RISK_WEIGHTS_SENIOR",
    "LGD_VALUES",
    "compute_maturity_weight",
    "get_lgd",
    "get_risk_weight",
    "get_sec_risk_weight",
]
