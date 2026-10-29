"""UK PRA Basel 3.1 regime calculator -- implements :class:`RegimeCalculator`.

Delegates to the UK modules:

* :mod:`.credit_risk`       -- Credit Risk: Standardised Approach (CRR) Part, CRM (CRR) Part
* :mod:`.operational_risk`  -- Operational Risk Part
* :mod:`.output_floor`      -- Required Level of Own Funds (CRR) Part Art 92
* :mod:`.capital_stack`     -- Art 92(1) minima; buffers (placeholders, see module)
* :mod:`.saccr`             -- Counterparty Credit Risk (CRR) Part Art 274
* :mod:`.cva`               -- Credit Valuation Adjustment Risk Part

References:
    - PRA PS1/26 Appendix 1: PRA Rulebook: CRR Firms: (CRR) Instrument 2026 (PRA2026/1),
      in force 1 January 2027
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

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
from src.jurisdictions.uk import (
    capital_stack,
    credit_risk,
    cva,
    operational_risk,
    output_floor,
    saccr,
)
from src.jurisdictions.uk.credit_risk import UKCreditConfig

LEGAL_BASIS: Final[str] = (
    "PRA PS1/26 (January 2026), Appendix 1: PRA Rulebook: CRR Firms: (CRR) Instrument 2026 "
    "(PRA2026/1) -- Required Level of Own Funds (CRR), Credit Risk: General Provisions (CRR), "
    "Credit Risk: Standardised Approach (CRR), Credit Risk Mitigation (CRR), Credit Valuation "
    "Adjustment Risk, Operational Risk and Counterparty Credit Risk (CRR) Parts; "
    "in force 1 January 2027"
)


class UKRegime:
    """United Kingdom -- PRA Basel 3.1 (PS1/26).

    Args:
        year: reporting year; drives the equity (GP Part rules 4.2-4.3), SA-CCR
            alpha add-on (Art 274(2A)) and CVA (rule 7.2) transitionals.
            ``output_floor`` takes its own ``year`` argument per the protocol.
        irb_firm: firm had IRB permission on 31 December 2026 (GP Part rule 4.1/4.4).
        corporate_ig_permission: firm holds the Art 122(6) permission (65% / 135%).
        equity_transitional_opt_out: GP Part rule 4.9 election (IRB firms).
        output_floor_in_scope: False for entities Art 92(2A)(b)-(d) leave on U-TREA.
        output_floor_use_transitional: apply the optional Art 92(5) factors.
    """

    jurisdiction: Jurisdiction = Jurisdiction.UK
    regime_name: str = "UK PRA Basel 3.1 (PS1/26)"
    legal_basis: str = LEGAL_BASIS

    def __init__(
        self,
        year: int = 2027,
        irb_firm: bool = False,
        corporate_ig_permission: bool = False,
        equity_transitional_opt_out: bool = False,
        output_floor_in_scope: bool = True,
        output_floor_use_transitional: bool = True,
    ) -> None:
        """Configure the regime (see class docstring for the provisions behind each option)."""
        self.year = year
        self.config = UKCreditConfig(
            year=year,
            irb_firm=irb_firm,
            corporate_ig_permission=corporate_ig_permission,
            equity_transitional_opt_out=equity_transitional_opt_out,
        )
        self.output_floor_in_scope = output_floor_in_scope
        self.output_floor_use_transitional = output_floor_use_transitional

    # ---- credit risk ---------------------------------------------------------
    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CF and RWEA -- SA Part Arts 111-134; CRM Part Arts 223-239."""
        return credit_risk.assign_risk_weight(exposure, self.config)

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """SA credit RWEA for a portfolio -- Art 92(3)(a); SA Part Art 113."""
        return credit_risk.portfolio_rwa(exposures, self.config)

    def ccf(self, exposure: SAExposure) -> float:
        """Conversion factor -- SA Part Art 111(1)(b)-(c) Table A1."""
        return credit_risk.conversion_factor(exposure)[0]

    # ---- operational risk ----------------------------------------------------
    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """Operational risk -- Operational Risk Part rules 4.1, 5.2-5.9 (ILM = 1)."""
        return operational_risk.operational_risk_capital(inputs)

    # ---- output floor ---------------------------------------------------------
    def output_floor(
        self, pre_floor_rwa: float, standardised_rwa: float, year: int
    ) -> OutputFloorResult:
        """Output floor -- Required Level of Own Funds (CRR) Part Art 92(2A), (5) (OF-ADJ = 0)."""
        return output_floor.apply_output_floor(
            pre_floor_rwa,
            standardised_rwa,
            year,
            in_scope=self.output_floor_in_scope,
            use_transitional=self.output_floor_use_transitional,
        )

    def output_floor_with_adjustments(
        self,
        pre_floor_rwa: float,
        standardised_rwa: float,
        year: int,
        *,
        irb_t2: float = 0.0,
        irb_cet1: float = 0.0,
        gcra: float = 0.0,
        sa_t2: float = 0.0,
        s_trea_credit_rwea: float | None = None,
    ) -> OutputFloorResult:
        """Output floor with OF-ADJ = 12.5 (IRB T2 - IRB CET1 - GCRA + SA T2) -- Art 92(2A)(a)."""
        adj = output_floor.of_adj(irb_t2, irb_cet1, gcra, sa_t2, s_trea_credit_rwea)
        return output_floor.apply_output_floor(
            pre_floor_rwa,
            standardised_rwa,
            year,
            in_scope=self.output_floor_in_scope,
            use_transitional=self.output_floor_use_transitional,
            adjustment=adj,
        )

    # ---- capital stack --------------------------------------------------------
    def capital_requirements(
        self,
        systemic_bucket_or_rate: float = 0.0,
        countercyclical_rate: float = 0.0,
        stress_buffer: float = 0.0,
    ) -> CapitalRequirements:
        """Art 92(1) minima and the buffer stack; ``systemic_bucket_or_rate`` is the
        G-SII/O-SII rate as a decimal; ``stress_buffer`` is the PRA buffer (see capital_stack)."""
        return capital_stack.capital_requirements(
            systemic_bucket_or_rate, countercyclical_rate, stress_buffer
        )

    # ---- counterparty and CVA -------------------------------------------------
    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """SA-CCR exposure value -- CCR Part Art 274(2)-(2A)."""
        return saccr.saccr_exposure(netting_set, year=self.year)

    def ba_cva_capital(
        self,
        counterparties: list[dict[str, float | str | bool]],
        hedged: bool = False,
    ) -> dict[str, float]:
        """BA-CVA (reduced / full) -- CVA Risk Part rules 4.2-4.10."""
        return cva.ba_cva(counterparties, hedged=hedged)

    def ba_cva_capital_with_index_hedges(
        self,
        counterparties: list[dict[str, float | str | bool]],
        index_hedges: Sequence[cva.IndexHedge],
    ) -> dict[str, float]:
        """Full BA-CVA including index hedges -- CVA Risk Part rules 4.5-4.8."""
        return cva.ba_cva(counterparties, hedged=True, index_hedges=index_hedges)
