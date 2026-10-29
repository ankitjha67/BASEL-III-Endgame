"""European Union -- CRR3 (Regulation (EU) 2024/1623 amending Regulation (EU) No 575/2013).

Exports :class:`EURegime`, the :class:`~src.jurisdictions.base.RegimeCalculator`
implementation for the EU. Parameters and citations live in
:mod:`src.jurisdictions.eu.params`; the verbatim transcription is
``docs/jurisdictions/EU_parameter_reference.md``.
"""

from src.jurisdictions.eu.calculator import EURegime

__all__ = ["EURegime"]
