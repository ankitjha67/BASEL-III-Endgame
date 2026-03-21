"""CVA Risk Calculator — main entry point for CVA capital computation.

Orchestrates both SA-CVA and BA-CVA calculations, determines approach
eligibility, converts capital charges to RWA, and produces reporting
breakdowns by counterparty.

All monetary amounts in USD millions ($M).

References:
    - BCBS d424, Section 5: CVA risk capital charge
    - BCBS d457 MAR50/MAR51: BA-CVA and SA-CVA specifications
    - ERBA NPR pp. 280-295: US implementation of CVA risk framework
    - ERBA NPR p. 280: Approach eligibility criteria
    - ERBA NPR p. 280: RWA conversion (K * 12.5)
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from src.cva_risk.ba_cva import (
    BACVACalculator,
    BACVACounterparty,
    BACVAHedge,
    BACVAResult,
)
from src.cva_risk.cva_params import (
    CVAApproach,
    RWA_MULTIPLIER,
    SACCR_ALPHA_COMMERCIAL,
    SACCR_ALPHA_FINANCIAL,
    get_saccr_alpha,
)
from src.cva_risk.sa_cva import (
    SACVACalculator,
    SACVACounterparty,
    SACVAHedge,
    SACVAResult,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Unified Counterparty Model
# =========================================================================

class CVACounterparty(BaseModel):
    """Unified counterparty model for CVA risk calculation.

    This model is used by the main CVA calculator and automatically
    converts to the approach-specific models (BACVACounterparty or
    SACVACounterparty) as needed.

    Per ERBA NPR p. 281: Each counterparty requires identification,
    credit quality, exposure, and maturity information.
    """
    counterparty_id: str = Field(description="Unique counterparty identifier")
    name: str = Field(default="", description="Counterparty name")
    rating: str = Field(
        default="BBB",
        description="Credit rating or internal grade equivalent"
    )
    sector: str = Field(
        default="CORPORATE",
        description="SOVEREIGN, FINANCIAL, CORPORATE, PUBLIC_SECTOR, OTHER"
    )
    ead: float = Field(
        description="Exposure at Default in $M (SA-CCR or other method)"
    )
    effective_maturity: float = Field(
        default=2.5,
        description="Effective maturity in years"
    )
    is_financial: bool = Field(
        default=False,
        description="True if financial institution"
    )
    netting_set_id: str = Field(default="", description="Netting set identifier")
    margin_agreement: bool = Field(
        default=False,
        description="True if a margin agreement is in place"
    )

    def to_ba_cva(self) -> BACVACounterparty:
        """Convert to BA-CVA counterparty model.

        Per ERBA NPR p. 281: BA-CVA uses rating-based risk weights.

        Returns:
            BACVACounterparty instance.
        """
        return BACVACounterparty(
            counterparty_id=self.counterparty_id,
            rating=self.rating,
            sector=self.sector,
            ead=self.ead,
            effective_maturity=self.effective_maturity,
            is_financial=self.is_financial,
            netting_set_id=self.netting_set_id,
            margin_agreement=self.margin_agreement,
        )

    def to_sa_cva(self) -> SACVACounterparty:
        """Convert to SA-CVA counterparty model.

        Per ERBA NPR p. 284: SA-CVA uses sector/quality-based risk weights.

        Returns:
            SACVACounterparty instance.
        """
        return SACVACounterparty(
            counterparty_id=self.counterparty_id,
            sector=self.sector,
            rating=self.rating,
            ead=self.ead,
            effective_maturity=self.effective_maturity,
            is_financial=self.is_financial,
            netting_set_id=self.netting_set_id,
        )


class CVAHedge(BaseModel):
    """Unified hedge model for CVA risk calculation.

    Per ERBA NPR p. 288: Only CDS and contingent CDS are eligible
    as CVA hedges.
    """
    hedge_id: str = Field(description="Unique hedge identifier")
    hedge_type: str = Field(
        description="SINGLE_NAME_CDS, INDEX_CDS, or CONTINGENT_CDS"
    )
    counterparty_id: str = Field(
        default="",
        description="Counterparty being hedged (for single-name CDS)"
    )
    notional: float = Field(description="Hedge notional in $M")
    maturity: float = Field(description="Remaining maturity in years")
    rating: str = Field(default="BBB", description="Reference entity rating")
    sector: str = Field(default="CORPORATE", description="Reference entity sector")

    def to_ba_cva(self) -> BACVAHedge:
        """Convert to BA-CVA hedge model.

        Returns:
            BACVAHedge instance.
        """
        return BACVAHedge(
            hedge_id=self.hedge_id,
            hedge_type=self.hedge_type,
            counterparty_id=self.counterparty_id,
            notional=self.notional,
            maturity=self.maturity,
            rating=self.rating,
        )

    def to_sa_cva(self) -> SACVAHedge:
        """Convert to SA-CVA hedge model.

        Returns:
            SACVAHedge instance.
        """
        return SACVAHedge(
            hedge_id=self.hedge_id,
            counterparty_id=self.counterparty_id,
            hedge_type=self.hedge_type,
            notional=self.notional,
            maturity=self.maturity,
            rating=self.rating,
            sector=self.sector,
        )


# =========================================================================
#  CVA Eligibility
# =========================================================================

class CVAEligibility(BaseModel):
    """CVA approach eligibility determination.

    Per ERBA NPR p. 280: Banks must meet specific criteria to use SA-CVA.
    Banks that do not meet criteria must use BA-CVA.
    """
    sa_cva_eligible: bool = Field(
        default=False,
        description="True if bank is eligible for SA-CVA"
    )
    ba_cva_full_eligible: bool = Field(
        default=True,
        description="True if bank is eligible for BA-CVA Full (always True)"
    )
    ba_cva_reduced_eligible: bool = Field(
        default=False,
        description="True if bank has eligible hedges for BA-CVA Reduced"
    )
    recommended_approach: CVAApproach = Field(
        default=CVAApproach.BA_CVA_FULL,
        description="Recommended approach based on eligibility"
    )
    reason: str = Field(
        default="",
        description="Reason for the recommendation"
    )


def determine_eligibility(
    has_cva_desk: bool = False,
    has_cva_sensitivities: bool = False,
    has_eligible_hedges: bool = False,
    supervisory_approval: bool = False,
) -> CVAEligibility:
    """Determine CVA approach eligibility per ERBA NPR p. 280.

    Per ERBA NPR p. 280:
    - SA-CVA requires: CVA desk, ability to compute CVA sensitivities,
      and supervisory approval.
    - BA-CVA Reduced requires: eligible CVA hedges.
    - BA-CVA Full: available to all banks (default).

    Args:
        has_cva_desk: True if bank has a dedicated CVA desk.
        has_cva_sensitivities: True if bank can compute CVA sensitivities.
        has_eligible_hedges: True if bank holds eligible CVA hedges.
        supervisory_approval: True if bank has supervisory approval for SA-CVA.

    Returns:
        CVAEligibility with recommended approach.
    """
    sa_eligible = (
        has_cva_desk
        and has_cva_sensitivities
        and supervisory_approval
    )

    ba_reduced = has_eligible_hedges

    if sa_eligible:
        return CVAEligibility(
            sa_cva_eligible=True,
            ba_cva_reduced_eligible=ba_reduced,
            recommended_approach=CVAApproach.SA_CVA,
            reason="Bank meets all SA-CVA criteria: CVA desk, sensitivities, approval",
        )
    elif ba_reduced:
        return CVAEligibility(
            sa_cva_eligible=False,
            ba_cva_reduced_eligible=True,
            recommended_approach=CVAApproach.BA_CVA_REDUCED,
            reason="Bank has eligible hedges; using BA-CVA Reduced",
        )
    else:
        return CVAEligibility(
            sa_cva_eligible=False,
            ba_cva_reduced_eligible=False,
            recommended_approach=CVAApproach.BA_CVA_FULL,
            reason="Default: BA-CVA Full (no hedges or SA-CVA capability)",
        )


# =========================================================================
#  Unified CVA Result
# =========================================================================

class CVACapitalResult(BaseModel):
    """Complete CVA capital charge result with reporting breakdown.

    Per ERBA NPR p. 280: The CVA capital charge converts to RWA via
    K_CVA * 12.5 for inclusion in total risk-weighted assets.
    """
    approach: CVAApproach = Field(
        description="CVA approach used for calculation"
    )
    k_cva: float = Field(
        description="Total CVA capital charge in $M"
    )
    rwa: float = Field(
        description="CVA RWA = K_CVA * 12.5 in $M"
    )

    # Component breakdown
    k_spread: float = Field(
        default=0.0,
        description="Credit spread component (SA-CVA) or full charge (BA-CVA) in $M"
    )
    k_ir: float = Field(
        default=0.0,
        description="Interest rate component (SA-CVA only) in $M"
    )
    k_full: float = Field(
        default=0.0,
        description="Unhedged charge (BA-CVA) in $M"
    )
    k_hedged: float = Field(
        default=0.0,
        description="Hedged charge (BA-CVA Reduced) in $M"
    )

    # Reporting
    counterparty_rwa: dict[str, float] = Field(
        default_factory=dict,
        description="RWA contribution by counterparty in $M"
    )
    sector_rwa: dict[str, float] = Field(
        default_factory=dict,
        description="RWA contribution by sector in $M"
    )
    total_ead: float = Field(
        default=0.0,
        description="Total EAD across all counterparties in $M"
    )
    counterparty_count: int = Field(
        default=0,
        description="Number of counterparties"
    )
    hedge_count: int = Field(
        default=0,
        description="Number of eligible hedges"
    )
    hedge_benefit_pct: float = Field(
        default=0.0,
        description="Percentage reduction from hedging"
    )

    # Eligibility
    eligibility: Optional[CVAEligibility] = Field(
        default=None,
        description="Approach eligibility determination"
    )

    # Raw results
    ba_cva_result: Optional[BACVAResult] = Field(
        default=None,
        description="Detailed BA-CVA result (if BA-CVA was used)"
    )
    sa_cva_result: Optional[SACVAResult] = Field(
        default=None,
        description="Detailed SA-CVA result (if SA-CVA was used)"
    )


# =========================================================================
#  Main CVA Calculator
# =========================================================================

class CVACalculator:
    """Main CVA Risk calculator — orchestrates SA-CVA and BA-CVA.

    This is the primary entry point for CVA capital computation.
    It determines approach eligibility, runs the appropriate calculation,
    converts to RWA, and produces reporting breakdowns.

    Per ERBA NPR p. 280: Banks must calculate CVA capital for all
    OTC derivatives (except those cleared through a qualifying CCP)
    and securities financing transactions.

    Usage::

        calculator = CVACalculator()

        # Auto-select approach
        result = calculator.calculate(
            counterparties=counterparties,
            hedges=hedges,
        )
        print(f"CVA RWA: ${result.rwa:,.0f}M")
        print(f"Approach: {result.approach.value}")

        # Force specific approach
        result = calculator.calculate(
            counterparties=counterparties,
            approach=CVAApproach.SA_CVA,
        )

    Attributes:
        ba_cva_calculator: BA-CVA calculation engine.
        sa_cva_calculator: SA-CVA calculation engine.
    """

    def __init__(self) -> None:
        """Initialize CVA calculators."""
        self.ba_cva_calculator = BACVACalculator()
        self.sa_cva_calculator = SACVACalculator()

    def calculate(
        self,
        counterparties: list[CVACounterparty],
        hedges: Optional[list[CVAHedge]] = None,
        approach: Optional[CVAApproach] = None,
        has_cva_desk: bool = False,
        has_cva_sensitivities: bool = False,
        supervisory_approval: bool = False,
    ) -> CVACapitalResult:
        """Calculate CVA capital charge using the appropriate approach.

        Per ERBA NPR p. 280: The CVA capital charge is computed based
        on the bank's eligibility for SA-CVA or BA-CVA. If no approach
        is specified, the calculator auto-selects based on eligibility.

        Args:
            counterparties: List of counterparties with EAD and maturity.
            hedges: Optional list of eligible CVA hedges.
            approach: Force a specific approach (overrides auto-selection).
            has_cva_desk: True if bank has a CVA desk (for SA-CVA eligibility).
            has_cva_sensitivities: True if bank can compute CVA sensitivities.
            supervisory_approval: True if bank has SA-CVA approval.

        Returns:
            CVACapitalResult with charge, RWA, and reporting breakdown.
        """
        if not counterparties:
            return CVACapitalResult(
                approach=approach or CVAApproach.BA_CVA_FULL,
                k_cva=0.0,
                rwa=0.0,
            )

        has_hedges = bool(hedges and len(hedges) > 0)

        # Determine eligibility
        eligibility = determine_eligibility(
            has_cva_desk=has_cva_desk,
            has_cva_sensitivities=has_cva_sensitivities,
            has_eligible_hedges=has_hedges,
            supervisory_approval=supervisory_approval,
        )

        # Select approach
        selected_approach = approach or eligibility.recommended_approach

        logger.info(
            "CVA calculation: approach=%s, counterparties=%d, hedges=%d",
            selected_approach.value,
            len(counterparties),
            len(hedges) if hedges else 0,
        )

        # Execute calculation
        if selected_approach == CVAApproach.SA_CVA:
            return self._run_sa_cva(
                counterparties, hedges, eligibility,
            )
        elif selected_approach == CVAApproach.BA_CVA_REDUCED:
            return self._run_ba_cva_reduced(
                counterparties, hedges or [], eligibility,
            )
        else:
            return self._run_ba_cva_full(
                counterparties, eligibility,
            )

    def _run_ba_cva_full(
        self,
        counterparties: list[CVACounterparty],
        eligibility: CVAEligibility,
    ) -> CVACapitalResult:
        """Execute BA-CVA Full calculation per ERBA NPR p. 281.

        Args:
            counterparties: Counterparties.
            eligibility: Eligibility determination.

        Returns:
            CVACapitalResult.
        """
        ba_cps = [cp.to_ba_cva() for cp in counterparties]
        result = self.ba_cva_calculator.calculate_full(ba_cps)

        # Build reporting breakdown
        cp_rwa, sector_rwa = self._build_reporting_breakdown(
            counterparties, result.counterparty_results,
        )

        return CVACapitalResult(
            approach=CVAApproach.BA_CVA_FULL,
            k_cva=result.k_ba_cva,
            rwa=result.rwa,
            k_spread=result.k_full,
            k_full=result.k_full,
            k_hedged=result.k_hedged,
            counterparty_rwa=cp_rwa,
            sector_rwa=sector_rwa,
            total_ead=sum(cp.ead for cp in counterparties),
            counterparty_count=len(counterparties),
            eligibility=eligibility,
            ba_cva_result=result,
        )

    def _run_ba_cva_reduced(
        self,
        counterparties: list[CVACounterparty],
        hedges: list[CVAHedge],
        eligibility: CVAEligibility,
    ) -> CVACapitalResult:
        """Execute BA-CVA Reduced calculation per ERBA NPR pp. 281-284.

        Args:
            counterparties: Counterparties.
            hedges: Eligible hedges.
            eligibility: Eligibility determination.

        Returns:
            CVACapitalResult.
        """
        ba_cps = [cp.to_ba_cva() for cp in counterparties]
        ba_hedges = [h.to_ba_cva() for h in hedges]
        result = self.ba_cva_calculator.calculate_reduced(ba_cps, ba_hedges)

        cp_rwa, sector_rwa = self._build_reporting_breakdown(
            counterparties, result.counterparty_results,
        )

        # Compute hedge benefit percentage
        hedge_benefit_pct = 0.0
        if result.k_full > 0:
            hedge_benefit_pct = (
                (result.k_full - result.k_ba_cva) / result.k_full * 100.0
            )

        return CVACapitalResult(
            approach=CVAApproach.BA_CVA_REDUCED,
            k_cva=result.k_ba_cva,
            rwa=result.rwa,
            k_spread=result.k_full,
            k_full=result.k_full,
            k_hedged=result.k_hedged,
            counterparty_rwa=cp_rwa,
            sector_rwa=sector_rwa,
            total_ead=sum(cp.ead for cp in counterparties),
            counterparty_count=len(counterparties),
            hedge_count=len(hedges),
            hedge_benefit_pct=hedge_benefit_pct,
            eligibility=eligibility,
            ba_cva_result=result,
        )

    def _run_sa_cva(
        self,
        counterparties: list[CVACounterparty],
        hedges: Optional[list[CVAHedge]],
        eligibility: CVAEligibility,
    ) -> CVACapitalResult:
        """Execute SA-CVA calculation per ERBA NPR pp. 284-295.

        Args:
            counterparties: Counterparties.
            hedges: Optional hedges.
            eligibility: Eligibility determination.

        Returns:
            CVACapitalResult.
        """
        sa_cps = [cp.to_sa_cva() for cp in counterparties]
        sa_hedges = [h.to_sa_cva() for h in hedges] if hedges else None

        result = self.sa_cva_calculator.calculate(
            sa_cps, hedges=sa_hedges,
        )

        # Build reporting from SA-CVA counterparty breakdown
        cp_rwa: dict[str, float] = {}
        total_charge = result.k_cva if result.k_cva > 0 else 1.0
        for cp_id, contribution in result.counterparty_breakdown.items():
            # Allocate RWA proportionally to sensitivity contribution
            share = abs(contribution) / max(
                sum(abs(v) for v in result.counterparty_breakdown.values()), 1.0
            )
            cp_rwa[cp_id] = result.rwa * share

        # Build sector RWA
        sector_rwa: dict[str, float] = {}
        for cp in counterparties:
            sector = cp.sector
            cp_contribution = cp_rwa.get(cp.counterparty_id, 0.0)
            sector_rwa[sector] = sector_rwa.get(sector, 0.0) + cp_contribution

        hedge_benefit_pct = 0.0
        if result.hedge_benefit_total > 0 and result.k_spread > 0:
            # Rough estimate of hedge benefit
            hedge_benefit_pct = min(
                result.hedge_benefit_total / (result.k_spread + result.hedge_benefit_total) * 100.0,
                100.0,
            )

        return CVACapitalResult(
            approach=CVAApproach.SA_CVA,
            k_cva=result.k_cva,
            rwa=result.rwa,
            k_spread=result.k_spread,
            k_ir=result.k_ir,
            counterparty_rwa=cp_rwa,
            sector_rwa=sector_rwa,
            total_ead=sum(cp.ead for cp in counterparties),
            counterparty_count=len(counterparties),
            hedge_count=len(hedges) if hedges else 0,
            hedge_benefit_pct=hedge_benefit_pct,
            eligibility=eligibility,
            sa_cva_result=result,
        )

    def _build_reporting_breakdown(
        self,
        counterparties: list[CVACounterparty],
        cp_results: list,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Build counterparty and sector RWA breakdowns for reporting.

        Per FR Y-9C Schedule HC-R / FFIEC 101: RWA must be reportable
        by counterparty and sector.

        Args:
            counterparties: Original counterparty list.
            cp_results: Per-counterparty results from BA-CVA.

        Returns:
            Tuple of (counterparty_rwa, sector_rwa) dicts.
        """
        # Build a map from cp_id to sector
        cp_sector_map = {cp.counterparty_id: cp.sector for cp in counterparties}

        cp_rwa: dict[str, float] = {}
        sector_rwa: dict[str, float] = {}

        total_scr = sum(getattr(r, "scr", 0.0) for r in cp_results)
        if total_scr <= 0:
            return cp_rwa, sector_rwa

        # Compute total RWA from the sum of results
        # Each counterparty's RWA is proportional to its SCR
        total_rwa = total_scr * RWA_MULTIPLIER  # Approximate

        for r in cp_results:
            cp_id = r.counterparty_id
            share = r.scr / total_scr if total_scr > 0 else 0.0
            allocated_rwa = total_rwa * share

            cp_rwa[cp_id] = allocated_rwa

            sector = cp_sector_map.get(cp_id, "OTHER")
            sector_rwa[sector] = sector_rwa.get(sector, 0.0) + allocated_rwa

        return cp_rwa, sector_rwa

    def compute_rwa(
        self,
        counterparties: list[CVACounterparty],
        hedges: Optional[list[CVAHedge]] = None,
        approach: Optional[CVAApproach] = None,
    ) -> float:
        """Convenience method to compute CVA RWA directly.

        Per ERBA NPR p. 280: RWA_CVA = K_CVA * 12.5

        Args:
            counterparties: Counterparties.
            hedges: Optional hedges.
            approach: Force a specific approach.

        Returns:
            CVA RWA in $M.
        """
        result = self.calculate(counterparties, hedges, approach=approach)
        return result.rwa
