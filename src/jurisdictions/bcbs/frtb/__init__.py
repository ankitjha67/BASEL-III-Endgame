"""BCBS (Basel Framework) market risk -- FRTB standardised approach, IMA scalars, MAR40 SSA.

References: Basel Framework MAR20-MAR23, MAR30-MAR33, MAR40.
"""

from src.jurisdictions.bcbs.frtb.calculator import BCBSMarketRisk
from src.jurisdictions.bcbs.frtb.params import DEFAULT_FRTB_OPTIONS, BCBSFRTBOptions

__all__ = ["BCBSMarketRisk", "BCBSFRTBOptions", "DEFAULT_FRTB_OPTIONS"]
