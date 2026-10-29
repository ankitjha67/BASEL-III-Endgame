"""United Kingdom -- PRA market risk (FRTB) under PS1/26 Appendix 1.

Exports :class:`UKMarketRisk`, the :class:`~src.jurisdictions.frtb_base.MarketRiskCalculator`
implementation for the UK (advanced standardised approach, simplified standardised approach,
IMA scalars). Parameters and citations are in :mod:`src.jurisdictions.uk.frtb.params`; the
verbatim transcription is ``docs/jurisdictions/UK_frtb_reference.md``.
"""

from src.jurisdictions.uk.frtb.calculator import UKMarketRisk

__all__ = ["UKMarketRisk"]
