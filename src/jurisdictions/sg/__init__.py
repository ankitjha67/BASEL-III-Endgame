"""Singapore -- MAS Notice 637 (version effective 1 January 2026).

Exports :class:`SGRegime`, the :class:`src.jurisdictions.base.RegimeCalculator`
implementation for banks incorporated in Singapore. Parameters and their
citations are in :mod:`src.jurisdictions.sg.params`; the verbatim
transcription is ``docs/jurisdictions/SG_parameter_reference.md``.
"""

from src.jurisdictions.sg.calculator import SGRegime

__all__ = ["SGRegime"]
