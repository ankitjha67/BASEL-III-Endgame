"""OSFI CAR 2026 regime calculator implementing :class:`RegimeCalculator`.

Delegates to the Chapter 4 credit module, Chapter 3 operational risk, the Chapter 1 capital
floor and buffer stack, Chapter 7 SA-CCR and Chapter 8 BA-CVA.

References:
    - OSFI Capital Adequacy Requirements (CAR) Guideline 2026, Chapters 1, 3, 4, 7, 8
"""

from __future__ import annotations

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
from src.jurisdictions.ca import (
    capital_stack,
    credit_risk,
    cva,
    operational_risk,
    output_floor,
    saccr,
)
from src.jurisdictions.ca.operational_risk import OpRiskApproach


class CARegime:
    """Canada -- OSFI CAR Guideline 2026.

    Args:
        is_dsib: institution is one of the six OSFI-designated D-SIBs (CAR Ch.1 s.1.8).
        domestic_stability_buffer: current DSB level (0-4%); not stated in CAR (s.1.9), so it is
            an input. ``None`` -> 0 with a flagged citation.
        op_risk_approach: SA (D-SIBs; SMSBs with AGI > $1.5B) or SSA (CAR Ch.3 s.3.2).
        loss_data_standards_met: CAR Ch.3 s.3.4.2 loss-data standards met (else ILM >= 1).
        uses_internal_models: subject to the capital floor (CAR Ch.1 s.1.5).
        institution_floor_factor: institution-specific floor factor (e.g. 0.90, s.1.4).
    """

    jurisdiction: Jurisdiction = Jurisdiction.CA
    regime_name: str = "OSFI Capital Adequacy Requirements (CAR) 2026"
    legal_basis: str = ("OSFI Capital Adequacy Requirements (CAR) Guideline, effective fiscal 2026 "
                        "(Bank Act ss. 485, 949; Trust and Loan Companies Act s. 473)")

    def __init__(
        self,
        is_dsib: bool = True,
        domestic_stability_buffer: float | None = None,
        op_risk_approach: OpRiskApproach = OpRiskApproach.SA,
        loss_data_standards_met: bool = True,
        uses_internal_models: bool = True,
        institution_floor_factor: float | None = None,
    ) -> None:
        """Configure institution-level choices (see class docstring; CAR Ch.1, Ch.3)."""
        self.is_dsib = is_dsib
        self.domestic_stability_buffer = domestic_stability_buffer
        self.op_risk_approach = op_risk_approach
        self.loss_data_standards_met = loss_data_standards_met
        self.uses_internal_models = uses_internal_models
        self.institution_floor_factor = institution_floor_factor

    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CCF and RWA for one exposure (CAR Ch.4 s.4.1, 4.3)."""
        return credit_risk.risk_weight_result(exposure)

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """Portfolio SA credit RWA aggregated by OSFI exposure class (CAR Ch.4)."""
        lines = [self.risk_weight(e) for e in exposures]
        rwa_by: dict[str, float] = {}
        exp_by: dict[str, float] = {}
        for e, r in zip(exposures, lines, strict=True):
            key = e.asset_class.value
            rwa_by[key] = rwa_by.get(key, 0.0) + r.rwa
            exp_by[key] = exp_by.get(key, 0.0) + r.exposure_amount
        return CreditRWAResult(
            jurisdiction=Jurisdiction.CA,
            total_exposure=sum(r.exposure_amount for r in lines),
            total_rwa=sum(r.rwa for r in lines),
            rwa_by_class=rwa_by, exposure_by_class=exp_by, line_items=lines,
        )

    def ccf(self, exposure: SAExposure) -> float:
        """CCF for the off-balance part (CAR Ch.4 s.4.1.18)."""
        return credit_risk.ccf_for(exposure)

    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """Operational-risk capital (CAR Ch.3: SA = BIC x ILM, or SSA)."""
        return operational_risk.operational_risk_capital(
            inputs, self.op_risk_approach, self.loss_data_standards_met)

    def output_floor(self, pre_floor_rwa: float, standardised_rwa: float, year: int
                     ) -> OutputFloorResult:
        """Capital floor at 67.5% (CAR Ch.1 s.1.5)."""
        return output_floor.apply_capital_floor(
            pre_floor_rwa, standardised_rwa, year,
            uses_internal_models=self.uses_internal_models,
            institution_factor=self.institution_floor_factor)

    def capital_requirements(
        self,
        systemic_bucket_or_rate: float = 0.0,
        countercyclical_rate: float = 0.0,
        stress_buffer: float = 0.0,
    ) -> CapitalRequirements:
        """Minimums and buffers (CAR Ch.1). ``stress_buffer`` > 0 is taken as the DSB."""
        dsb = stress_buffer if stress_buffer > 0 else self.domestic_stability_buffer
        return capital_stack.capital_requirements(
            self.is_dsib, systemic_bucket_or_rate, countercyclical_rate, dsb)

    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """SA-CCR EAD (CAR Ch.7 s.7.1.7, alpha 1.4)."""
        return saccr.saccr_ead(netting_set)

    def ba_cva_capital(
        self,
        counterparties: list[dict[str, float | str | bool]],
        hedged: bool = False,
    ) -> dict[str, float]:
        """BA-CVA reduced / full (CAR Ch.8 s.8.2)."""
        return cva.ba_cva(counterparties, hedged)
