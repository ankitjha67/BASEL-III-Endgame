"""DRC (Default Risk Charge) module -- FRTB MAR22.

Provides calculators for the Default Risk Charge across:

- **Non-securitization** (``drc_nonsec``): Bonds, loans, CDS, equity.
- **Securitization** (``drc_sec``): *Planned -- not yet implemented.*

Regulatory parameters (LGD tables, risk weights, maturity weighting)
are centralised in ``drc_params``.
"""

from src.market_risk.frtb.drc.drc_nonsec import (
    DRCCalculator,
    DRCPosition,
    DRCResult,
)
from src.market_risk.frtb.drc.drc_params import (
    DRC_RISK_WEIGHTS,
    LGD_VALUES,
    compute_maturity_weight,
    get_lgd,
    get_risk_weight,
)

__all__ = [
    "DRCCalculator",
    "DRCPosition",
    "DRCResult",
    "DRC_RISK_WEIGHTS",
    "LGD_VALUES",
    "compute_maturity_weight",
    "get_lgd",
    "get_risk_weight",
]
