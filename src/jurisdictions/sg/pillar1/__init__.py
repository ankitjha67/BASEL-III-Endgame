"""Singapore Pillar 1 package -- securitisation, SA-CVA, leverage, large exposures, CCPs.

Exports :class:`SGPillar1`. Sources: MAS Notice 637 (version effective 1 January 2026) and
MAS Notice 656 (last revised 22 May 2026, effective 1 July 2026). Parameters are in
:mod:`src.jurisdictions.sg.pillar1.params`; the verbatim transcription is
``docs/jurisdictions/SG_pillar1_reference.md``.
"""

from src.jurisdictions.sg.pillar1.calculator import SGPillar1

__all__ = ["SGPillar1"]
