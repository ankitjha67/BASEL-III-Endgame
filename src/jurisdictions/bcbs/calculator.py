"""BCBS regime calculator: the Basel Framework international baseline.

:class:`BCBSRegime` implements :class:`~src.jurisdictions.base.RegimeCalculator`
by delegating to the CRE20-22, OPE25, RBC20/RBC90, RBC30/RBC40/LEV, CRE52 and
MAR50 modules of this package. National discretions are set through
:class:`~src.jurisdictions.bcbs.params.BCBSOptions` (defaults = BCBS base rules).

References:
    - Basel Framework (BIS consolidated standards, generated 29/10/2026)
    - BCBS d424, Basel III: Finalising post-crisis reforms (Dec 2017)
"""

from __future__ import annotations

from collections import defaultdict

from src.jurisdictions.base import (
    CapitalRequirements,
    CreditRWAResult,
    Jurisdiction,
    OpRiskInputs,
    OpRiskResult,
    OutputFloorResult,
    RiskWeightResult,
    SACCRNettingSetInput,
    SACCRResult,
    SAExposure,
)
from src.jurisdictions.bcbs import capital_stack, credit_risk, cva, operational_risk, output_floor
from src.jurisdictions.bcbs import saccr as saccr_module
from src.jurisdictions.bcbs.params import DEFAULT_OPTIONS, BCBSOptions


class BCBSRegime:
    """Basel Committee standards (Basel Framework) as a :class:`RegimeCalculator`."""

    jurisdiction: Jurisdiction = Jurisdiction.BCBS
    regime_name: str = "Basel Framework (BCBS consolidated standards)"
    legal_basis: str = ("BCBS Basel Framework: CRE20-CRE22, CRE52, CRE90, MAR50, OPE25, "
                        "RBC20, RBC30, RBC40, RBC90, LEV20, LEV40, SCO40; BCBS d424 (Dec 2017)")

    def __init__(self, options: BCBSOptions | None = None) -> None:
        """Create the regime with national-discretion options (BCBS defaults if None)."""
        self.options: BCBSOptions = options or DEFAULT_OPTIONS

    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CCF, CRM and RWA for one exposure (CRE20-CRE22)."""
        return credit_risk.risk_weight_exposure(exposure, self.options)

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """Aggregate SA credit RWA (RBC20.6(1)(a), CRE20-CRE22)."""
        items = [self.risk_weight(e) for e in exposures]
        rwa_by: dict[str, float] = defaultdict(float)
        ead_by: dict[str, float] = defaultdict(float)
        for e, r in zip(exposures, items, strict=True):
            rwa_by[e.asset_class.value] += r.rwa
            ead_by[e.asset_class.value] += r.exposure_amount
        return CreditRWAResult(
            jurisdiction=Jurisdiction.BCBS,
            total_exposure=sum(r.exposure_amount for r in items),
            total_rwa=sum(r.rwa for r in items),
            rwa_by_class=dict(rwa_by),
            exposure_by_class=dict(ead_by),
            line_items=items,
        )

    def ccf(self, exposure: SAExposure) -> float:
        """Credit conversion factor (CRE20.94-20.101)."""
        return credit_risk.ccf(exposure)

    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """Operational-risk capital and RWA (OPE25)."""
        return operational_risk.operational_risk(inputs, self.options)

    def output_floor(self, pre_floor_rwa: float, standardised_rwa: float,
                     year: int) -> OutputFloorResult:
        """Output floor with the RBC90 phase-in (RBC20.4(2), RBC90.1-90.2)."""
        return output_floor.output_floor(pre_floor_rwa, standardised_rwa, year, self.options)

    def capital_requirements(self, systemic_bucket_or_rate: float = 0.0,
                             countercyclical_rate: float = 0.0,
                             stress_buffer: float = 0.0) -> CapitalRequirements:
        """Minimums and buffers (RBC20.1, RBC30, RBC40, LEV20.7, LEV40.2)."""
        return capital_stack.capital_requirements(systemic_bucket_or_rate,
                                                  countercyclical_rate, stress_buffer)

    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """SA-CCR EAD for one netting set (CRE52)."""
        return saccr_module.saccr_ead(netting_set)

    def ba_cva_capital(self, counterparties: list[dict[str, float | str | bool]],
                       hedged: bool = False) -> dict[str, float]:
        """Reduced / full BA-CVA capital (MAR50.12-50.26)."""
        return cva.ba_cva_capital(counterparties, hedged)
