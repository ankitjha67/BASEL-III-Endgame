"""UK PRA Pillar 1 calculator -- securitisation, SA-CVA, leverage, large exposures, CCPs.

Implements the five protocols of :mod:`src.jurisdictions.pillar1_base`:

* :class:`SecuritisationCalculator` -- Securitisation (CRR) Part (:mod:`.securitisation`)
* :class:`SACVACalculator`          -- CVA Risk Part Chapter 5 (:mod:`.sa_cva`)
* :class:`LeverageCalculator`       -- Leverage Ratio (CRR) Part (:mod:`.leverage`)
* :class:`LargeExposuresCalculator` -- Large Exposures (CRR) Part (:mod:`.large_exposures`)
* :class:`CCPCalculator`            -- CCR (CRR) Part Section 9 (:mod:`.ccp`)

Amounts are GBP millions. Parameters and citations: :mod:`.params`; verbatim
transcription: ``docs/jurisdictions/UK_pillar1_reference.md``.
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import (
    CCPExposureInput,
    CCPResult,
    CVASensitivityInput,
    LargeExposureInput,
    LargeExposureRow,
    LeverageInputs,
    LeverageResult,
    SACVAResult,
    SecResultRow,
    SecTrancheInput,
)
from src.jurisdictions.uk.pillar1 import ccp, large_exposures, leverage, sa_cva, securitisation

LEGAL_BASIS: Final[str] = (
    "PRA Rulebook (as at 1 January 2027): Securitisation (CRR) Part Arts 242-270F; Credit "
    "Valuation Adjustment Risk Part Chapter 5 (PS1/26 Appendix 1, PRA2026/1); Leverage Ratio "
    "(CRR) Part Arts 429-429g; Large Exposures (CRR) Part; Counterparty Credit Risk (CRR) Part "
    "Arts 300-311"
)


class UKPillar1:
    """United Kingdom -- remaining Pillar 1 sections under the PRA Rulebook."""

    jurisdiction: Jurisdiction = Jurisdiction.UK
    legal_basis: str = LEGAL_BASIS

    def securitisation(self, tranche: SecTrancheInput) -> SecResultRow:
        """Risk weight via the Art 254 hierarchy with Arts 259-269A floors and caps."""
        return securitisation.securitisation_risk_weight(tranche)

    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """SA-CVA -- CVA Risk Part rules 5.14-5.30 (m_CVA = 1, R = 0.01)."""
        return sa_cva.sa_cva_capital(sensitivities)

    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Total exposure measure -- Leverage Ratio (CRR) Part Art 429(4), 429a-429g."""
        return leverage.leverage_exposure_measure(inputs)

    def large_exposures(
        self,
        exposures: list[LargeExposureInput],
        tier1_capital: float,
        reporting_bank_is_gsib: bool,
    ) -> list[LargeExposureRow]:
        """Reporting (rule 1.2, Art 394) and limits (Art 395(1), Art 400)."""
        return large_exposures.large_exposure_rows(
            exposures, tier1_capital, reporting_bank_is_gsib
        )

    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """Trade-exposure and default-fund RWEA -- CCR (CRR) Part Arts 303-311."""
        return ccp.ccp_exposure_rwa(exposure)
