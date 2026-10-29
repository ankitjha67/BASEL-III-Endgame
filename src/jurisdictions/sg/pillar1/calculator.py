"""Singapore Pillar 1 calculator -- securitisation, SA-CVA, leverage, large exposures, CCPs.

:class:`SGPillar1` implements the five protocols of :mod:`src.jurisdictions.pillar1_base`
(:class:`SecuritisationCalculator`, :class:`SACVACalculator`, :class:`LeverageCalculator`,
:class:`LargeExposuresCalculator`, :class:`CCPCalculator`) for banks incorporated in Singapore.

References:
    - MAS Notice 637 (version effective 1 January 2026): Part IV Division 2, Annexes 4C / 4D,
      Part VII Divisions 6 and 7, Part VIII Division 5 Sub-division 3
    - MAS Notice 656 (last revised 22 May 2026, effective 1 July 2026)
"""

from __future__ import annotations

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
from src.jurisdictions.sg.pillar1 import ccp, large_exposures, leverage, sa_cva, securitisation
from src.jurisdictions.sg.pillar1 import params as p


class SGPillar1:
    """MAS Notice 637 / 656 Pillar 1 sections (Singapore-incorporated banks).

    Args:
        m_cva: SA-CVA multiplier (para 8.5.32(e)(i): 1, or higher if MAS so requires).
    """

    jurisdiction: Jurisdiction = Jurisdiction.SG
    legal_basis: str = (
        "MAS Notice 637 (Risk Based Capital Adequacy Requirements, version effective "
        "1 January 2026); MAS Notice 656 (Exposures to Single Counterparty Groups, last revised "
        "22 May 2026, effective 1 July 2026)"
    )

    def __init__(self, m_cva: float = p.SA_CVA_M_CVA) -> None:
        """Configure the calculator (MAS Notice 637 para 8.5.32(e)(i) for ``m_cva``)."""
        self.m_cva = m_cva

    def securitisation(
        self,
        tranche: SecTrancheInput,
        *,
        look_through_rw: float | None = None,
        more_senior_rw: float | None = None,
        mixed_pool_irb_share: float | None = None,
    ) -> SecResultRow:
        """Risk weight via the MAS hierarchy (MAS Notice 637 paras 7.1.14-7.1.17, 7.6.13-7.6.104).

        The optional keyword inputs are not in the protocol: the senior look-through cap
        (7.1.15), the more-senior floor (7.6.54 / 7.6.79) and the mixed-pool share d (7.6.80).
        """
        return securitisation.securitisation_risk_weight(
            tranche,
            look_through_rw=look_through_rw,
            more_senior_rw=more_senior_rw,
            mixed_pool_irb_share=mixed_pool_irb_share,
        )

    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """K_SA-CVA and CVA RWA (MAS Notice 637 paras 8.5.1, 8.5.29-8.5.73)."""
        return sa_cva.sa_cva(sensitivities, self.m_cva)

    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Total exposure measure (MAS Notice 637 Annex 4C, Annex 4D)."""
        return leverage.leverage_exposure(inputs)

    def large_exposures(
        self,
        exposures: list[LargeExposureInput],
        tier1_capital: float,
        reporting_bank_is_gsib: bool,
    ) -> list[LargeExposureRow]:
        """Limit test and reporting threshold (MAS Notice 656 paras 4, 7-11, 28, Annex A)."""
        return large_exposures.large_exposures(exposures, tier1_capital, reporting_bank_is_gsib)

    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """Trade-exposure and default-fund RWA (MAS Notice 637 paras 7.7.1-7.7.45)."""
        return ccp.ccp_exposure(exposure)
