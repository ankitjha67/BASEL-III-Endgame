"""EU CRR3 Pillar 1 calculator -- implements the five protocols of
:mod:`src.jurisdictions.pillar1_base`.

* :class:`~src.jurisdictions.pillar1_base.SecuritisationCalculator` -- Articles 242-270a
* :class:`~src.jurisdictions.pillar1_base.SACVACalculator` -- Articles 383-383z
* :class:`~src.jurisdictions.pillar1_base.LeverageCalculator` -- Articles 429-429g
* :class:`~src.jurisdictions.pillar1_base.LargeExposuresCalculator` -- Articles 387-403
* :class:`~src.jurisdictions.pillar1_base.CCPCalculator` -- Articles 300-311

References:
    - Regulation (EU) No 575/2013 as amended by Regulation (EU) 2024/1623
"""

from __future__ import annotations

from collections.abc import Iterable

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.eu.pillar1 import (
    ccp,
    large_exposures,
    leverage,
    sa_cva,
    securitisation,
)
from src.jurisdictions.eu.pillar1 import params as prm
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


class EUPillar1:
    """EU securitisation, SA-CVA, leverage exposure, large exposures and CCP treatment.

    Args:
        year: reporting year (drives the Article 465(13) S-TREA p factor).
        for_output_floor: compute securitisation risk weights for S-TREA (Article 92(5)).
        reporting_currency: ISO code of the reporting currency (SA-CVA Article 383c(2), 383n).
        erm2_currencies: currencies participating in ERM II (Articles 383c(2), 383n(2)).
        m_cva: SA-CVA multiplier (1, may be raised by the competent authority, 383b(8)).
        reporting_ccy_per_eur: converts the EUR 150m / EUR 300m large-exposure amounts.
        le_institution_floor_eur_m: lower EUR amount set by the competent authority (395(1)).
        le_institution_set_limit_pct_t1: institution-set limit where EUR 150m > 25 % T1
            (at most 100 %, 395(1) second subparagraph).
    """

    jurisdiction: Jurisdiction = Jurisdiction.EU

    def __init__(
        self,
        year: int = 2026,
        for_output_floor: bool = False,
        reporting_currency: str = "EUR",
        erm2_currencies: Iterable[str] = (),
        m_cva: float = prm.SACVA_M_CVA,
        reporting_ccy_per_eur: float = 1.0,
        le_institution_floor_eur_m: float = prm.LE_INSTITUTION_FLOOR_EUR_M,
        le_institution_set_limit_pct_t1: float = prm.LE_INSTITUTION_ABSOLUTE_CEILING_PCT_T1,
    ) -> None:
        """Store the regime options (see class docstring)."""
        self.year = year
        self.for_output_floor = for_output_floor
        self.reporting_currency = reporting_currency
        self.erm2_currencies = tuple(erm2_currencies)
        self.m_cva = m_cva
        self.reporting_ccy_per_eur = reporting_ccy_per_eur
        self.le_institution_floor_eur_m = le_institution_floor_eur_m
        self.le_institution_set_limit_pct_t1 = le_institution_set_limit_pct_t1

    def securitisation(self, tranche: SecTrancheInput) -> SecResultRow:
        """Risk weight via the Article 254 hierarchy with Articles 267-270a."""
        return securitisation.securitisation(tranche, self.year, self.for_output_floor)

    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """SA-CVA own funds requirement -- Articles 383, 383b."""
        return sa_cva.sa_cva(
            sensitivities, self.reporting_currency, self.erm2_currencies, self.m_cva
        )

    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Total exposure measure -- Articles 429(4), 429a-429g."""
        return leverage.leverage_exposure(inputs)

    def large_exposures(
        self,
        exposures: list[LargeExposureInput],
        tier1_capital: float,
        reporting_bank_is_gsib: bool,
    ) -> list[LargeExposureRow]:
        """Articles 392, 394(1), 395(1), 400."""
        return large_exposures.large_exposures(
            exposures,
            tier1_capital,
            reporting_bank_is_gsib,
            self.reporting_ccy_per_eur,
            self.le_institution_floor_eur_m,
            self.le_institution_set_limit_pct_t1,
        )

    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """Trade-exposure and default-fund RWEA -- Articles 303-311."""
        return ccp.ccp_exposure(exposure)
