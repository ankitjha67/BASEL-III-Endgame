"""Canada Pillar 1 calculator: securitization, SA-CVA, leverage, large exposures and CCPs.

Implements the five protocols of :mod:`src.jurisdictions.pillar1_base` for OSFI:

- ``securitisation``: CAR 2026 Chapter 6.
- ``sa_cva``: CAR 2026 Chapter 8 s.8.3.
- ``leverage_exposure``: Leverage Requirements Guideline (2023).
- ``large_exposures``: Guideline B-2 Large Exposure Limits (2028), consultation draft (D-SIBs and
  Category I/II SMSBs).
- ``ccp_exposure``: CAR 2026 Chapter 7 s.7.1.8.

References:
    - OSFI CAR 2026 Chapters 6, 7, 8; OSFI LR (2023); OSFI B-2 (2028 draft)
    - Basel Framework CRE40-45, CRE54, MAR50, LEV, LEX
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.ca.pillar1 import (
    ccp,
    large_exposures,
    leverage,
    sa_cva,
    securitisation,
)
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


class CAPillar1:
    """Canada -- OSFI Pillar 1 sections beyond the core credit/op-risk engine.

    Args:
        is_dsib: reporting institution is an OSFI-designated D-SIB (B-2 limits; LR buffer).
            ``False`` means a Category I/II SMSB for B-2 purposes.
        reporting_currency: SA-CVA reporting currency (IR specified-currency and FX buckets).
        m_cva: SA-CVA multiplier (CAR s.8.3.3; 1 unless OSFI requires more).
    """

    jurisdiction: Jurisdiction = Jurisdiction.CA
    regime_name: str = "OSFI CAR 2026 Ch.6-8, Leverage Requirements (2023), B-2 (2028 draft)"

    def __init__(self, is_dsib: bool = True, reporting_currency: str = "CAD",
                 m_cva: float | None = None) -> None:
        """Configure institution-level choices (CAR s.8.3.3; B-2 s.II)."""
        self.is_dsib = is_dsib
        self.reporting_currency = reporting_currency
        self.m_cva = m_cva

    def securitisation(self, tranche: SecTrancheInput) -> SecResultRow:
        """Risk weight via the CAR Ch.6 hierarchy (s.6.5.2) with STC, NPL, resec and caps."""
        return securitisation.securitisation_rw(tranche)

    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """K_SA-CVA = sum over classes of m_CVA x sqrt(...) (CAR s.8.3.4 [MAR 50.53])."""
        return sa_cva.sa_cva(sensitivities, self.reporting_currency, self.m_cva)

    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Leverage ratio exposure measure (OSFI LR s.VI [LEV 30])."""
        return leverage.leverage_exposure(inputs)

    def large_exposures(
        self,
        exposures: list[LargeExposureInput],
        tier1_capital: float,
        reporting_bank_is_gsib: bool,
    ) -> list[LargeExposureRow]:
        """10% reporting threshold and 15/20/25% limits (B-2 s.III-V [LEX 20, 40])."""
        return large_exposures.large_exposures(exposures, tier1_capital, reporting_bank_is_gsib,
                                               self.is_dsib)

    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """QCCP / non-QCCP trade and default-fund RWA (CAR s.7.1.8 [CRE 54])."""
        return ccp.ccp_exposure(exposure)

    def leverage_requirement(self, hla: float = 0.0,
                             authorized_ratio: float | None = None) -> float:
        """3% + 50% x HLA for D-SIBs, or the authorized leverage ratio if higher (LR s.IV)."""
        return leverage.leverage_requirement(self.is_dsib, hla, authorized_ratio)
