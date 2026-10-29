"""EU market risk (FRTB) -- CRR Part Three Title IV as amended by CRR3 (Reg. (EU) 2024/1623).

Exports :class:`EUMarketRisk`, the
:class:`~src.jurisdictions.frtb_base.MarketRiskCalculator` implementation for the EU
(alternative standardised approach, plus the simplified standardised approach and the
alternative-internal-model scalars as extra methods). Parameters and citations live in
:mod:`src.jurisdictions.eu.frtb.params`; the verbatim transcription is
``docs/jurisdictions/EU_frtb_reference.md``.
"""

from src.jurisdictions.eu.frtb.calculator import EUMarketRisk

__all__ = ["EUMarketRisk"]
