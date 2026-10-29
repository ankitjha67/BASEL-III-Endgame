"""EU CRR3 Pillar 1 package: securitisation, SA-CVA, leverage, large exposures, CCPs.

Exports :class:`EUPillar1`. Parameters and citations live in
:mod:`src.jurisdictions.eu.pillar1.params`; the verbatim transcription is
``docs/jurisdictions/EU_pillar1_reference.md``.
"""

from src.jurisdictions.eu.pillar1.calculator import EUPillar1

__all__ = ["EUPillar1"]
