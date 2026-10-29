"""Singapore market risk -- MAS Notice 637 Part VIII: SA(MR), IMA scalars, SSA(MR).

References: MAS Notice 637 (effective 1 January 2026) Part VIII Divisions 1-4, Annex 8E;
docs/jurisdictions/SG_frtb_reference.md.
"""

from src.jurisdictions.sg.frtb.calculator import SGMarketRisk
from src.jurisdictions.sg.frtb.params import DEFAULT_FRTB_OPTIONS, SGFRTBOptions

__all__ = ["DEFAULT_FRTB_OPTIONS", "SGFRTBOptions", "SGMarketRisk"]
