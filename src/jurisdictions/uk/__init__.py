"""United Kingdom -- PRA Basel 3.1 (PS1/26, PRA Rulebook: CRR Firms: (CRR) Instrument 2026).

Exports :class:`UKRegime`, the :class:`~src.jurisdictions.base.RegimeCalculator`
implementation for the UK. Parameters and their citations are in
:mod:`src.jurisdictions.uk.params`; the verbatim transcription is in
``docs/jurisdictions/UK_parameter_reference.md``.
"""

from src.jurisdictions.uk.calculator import UKRegime

__all__ = ["UKRegime"]
