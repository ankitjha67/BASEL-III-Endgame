"""United Kingdom -- PRA Rulebook securitisation, SA-CVA, leverage exposure, large exposures
and CCP exposures.

Exports :class:`UKPillar1`, implementing the five protocols of
:mod:`src.jurisdictions.pillar1_base`.
"""

from src.jurisdictions.uk.pillar1.calculator import UKPillar1

__all__ = ["UKPillar1"]
