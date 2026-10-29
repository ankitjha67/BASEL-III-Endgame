"""BCBS Pillar 1 calculator: securitisation, SA-CVA, leverage exposure, large exposures, CCP.

:class:`BCBSPillar1` implements the five protocols of
:mod:`src.jurisdictions.pillar1_base` for the Basel Framework baseline
(``Jurisdiction.BCBS``). National discretions are set through
:class:`~src.jurisdictions.bcbs.pillar1.params.BCBSPillar1Options`.

References:
    - Basel Framework CRE40-CRE45, CRE54, MAR50.27-50.77, LEV30, LEX10-LEX40
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.bcbs.pillar1 import ccp as ccp_module
from src.jurisdictions.bcbs.pillar1 import large_exposures as lex
from src.jurisdictions.bcbs.pillar1 import leverage as lev
from src.jurisdictions.bcbs.pillar1 import sa_cva as sacva
from src.jurisdictions.bcbs.pillar1 import securitisation as sec
from src.jurisdictions.bcbs.pillar1.params import DEFAULT_PILLAR1_OPTIONS, BCBSPillar1Options
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


class BCBSPillar1:
    """Basel Framework securitisation, SA-CVA, leverage, large-exposure and CCP rules."""

    jurisdiction: Jurisdiction = Jurisdiction.BCBS
    legal_basis: str = ("BCBS Basel Framework: CRE40-CRE45, CRE54, MAR50.27-50.77, LEV30, "
                        "LEX10-LEX40")

    def __init__(self, options: BCBSPillar1Options | None = None) -> None:
        """Create the calculator with discretion settings (BCBS defaults if None)."""
        self.options: BCBSPillar1Options = options or DEFAULT_PILLAR1_OPTIONS

    def securitisation(self, tranche: SecTrancheInput) -> SecResultRow:
        """Risk weight via the CRE40.41-40.48 hierarchy with CRE40.50 / CRE45 adjustments."""
        return sec.securitisation(tranche, self.options.sec_erba_permitted)

    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """K_SA-CVA and RWA (MAR50.42-50.53, MAR50.1)."""
        return sacva.sa_cva(sensitivities, self.options.reporting_currency, self.options.m_cva)

    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Leverage ratio exposure measure (LEV30)."""
        return lev.leverage_exposure(inputs, self.options.central_bank_reserves_exemption)

    def large_exposures(self, exposures: list[LargeExposureInput], tier1_capital: float,
                        reporting_bank_is_gsib: bool) -> list[LargeExposureRow]:
        """Large-exposure reporting and limit test (LEX10.8, LEX20.1-20.4, LEX40.1)."""
        return lex.large_exposures(exposures, tier1_capital, reporting_bank_is_gsib)

    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """Trade-exposure and default-fund RWA (CRE54)."""
        return ccp_module.ccp_exposure(exposure)
