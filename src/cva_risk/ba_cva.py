"""Basic Approach CVA (BA-CVA) capital calculation.

Implements the BA-CVA framework per BCBS d424 Section 5.1, BCBS d457 MAR50,
and the US Federal Reserve Basel III Endgame Re-Proposal (ERBA NPR pp. 280-284).

BA-CVA is a simplified approach for banks with limited CVA hedging activity.
It does not require CVA sensitivity computation and instead uses a formula-based
approach with supervisory risk weights.

Two versions are available:
    - BA-CVA Full: For banks without eligible CVA hedges
    - BA-CVA Reduced: For banks with eligible hedges (CDS, contingent CDS)

Key formulas:
    K_full = sqrt(rho^2 * (sum_c SCR_c)^2 + (1 - rho^2) * sum_c SCR_c^2)

    K_hedged = sqrt(rho^2 * (sum_c SCR_c - sum_h SNH_h - IH)^2
               + (1 - rho^2) * sum_c (SCR_c - SN_c)^2 + sum_h SNH_h^2)

    K_BA-CVA = beta * K_hedged + (1 - beta) * K_full

Where:
    SCR_c   = w_c * M_c * EAD_c  (standalone CVA risk per counterparty)
    SNH_h   = single-name hedge contribution
    IH      = index hedge contribution
    rho     = 0.50  (supervisory correlation)
    beta    = 0.25  (hedging effectiveness parameter)

All monetary amounts in USD millions ($M).

References:
    - BCBS d424, Section 5.1: Basic approach for CVA risk
    - BCBS d457 MAR50: BA-CVA specifications
    - ERBA NPR pp. 280-284: US implementation of BA-CVA
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator

from src.cva_risk.cva_params import (
    BA_CVA_ALPHA,
    BA_CVA_BETA,
    BA_CVA_HEDGE_DISCOUNT_INDEX,
    BA_CVA_HEDGE_DISCOUNT_SINGLE_NAME,
    BA_CVA_RHO,
    BA_CVA_RISK_WEIGHTS,
    ELIGIBLE_CVA_HEDGE_TYPES,
    MAX_EFFECTIVE_MATURITY,
    MIN_EFFECTIVE_MATURITY,
    RATING_TO_CVA_RATING,
    RWA_MULTIPLIER,
    get_ba_cva_risk_weight,
    hedge_maturity_adjustment,
    supervisory_discount_factor,
)


# =========================================================================
#  Data Models
# =========================================================================

class BACVACounterparty(BaseModel):
    """A counterparty for BA-CVA calculation.

    Per ERBA NPR p. 281: Each counterparty is characterized by its
    credit rating, sector, exposure at default, and effective maturity.
    """
    counterparty_id: str = Field(description="Unique counterparty identifier")
    rating: str = Field(
        default="BBB",
        description="Credit rating or internal grade equivalent per ERBA NPR p. 282"
    )
    sector: str = Field(
        default="CORPORATE",
        description="Counterparty sector: SOVEREIGN, FINANCIAL, CORPORATE, OTHER"
    )
    ead: float = Field(
        description="Exposure at Default in $M per ERBA NPR p. 281"
    )
    effective_maturity: float = Field(
        default=2.5,
        description="Effective maturity in years, clipped to [1, 5] per ERBA NPR p. 283"
    )
    is_financial: bool = Field(
        default=False,
        description="True if financial institution (affects SA-CCR alpha)"
    )
    netting_set_id: str = Field(
        default="",
        description="Netting set this counterparty belongs to"
    )
    margin_agreement: bool = Field(
        default=False,
        description="True if counterparty has a margin agreement"
    )

    @field_validator("effective_maturity")
    @classmethod
    def clip_maturity(cls, v: float) -> float:
        """Clip effective maturity to [1, 5] per MAR50.4 / ERBA NPR p. 283."""
        return max(MIN_EFFECTIVE_MATURITY, min(v, MAX_EFFECTIVE_MATURITY))

    @field_validator("ead")
    @classmethod
    def validate_ead(cls, v: float) -> float:
        """EAD must be non-negative per ERBA NPR p. 281."""
        if v < 0:
            raise ValueError(f"EAD must be non-negative, got {v}")
        return v


class BACVAHedge(BaseModel):
    """A CVA hedge position for BA-CVA.

    Per ERBA NPR p. 288: Only single-name CDS, index CDS, and
    contingent CDS are eligible CVA hedges.
    """
    hedge_id: str = Field(description="Unique hedge identifier")
    hedge_type: str = Field(
        description="SINGLE_NAME_CDS, INDEX_CDS, or CONTINGENT_CDS"
    )
    counterparty_id: str = Field(
        default="",
        description="Counterparty being hedged (for single-name/contingent CDS)"
    )
    notional: float = Field(
        description="Hedge notional in $M per ERBA NPR p. 288"
    )
    maturity: float = Field(
        description="Remaining hedge maturity in years"
    )
    rating: str = Field(
        default="BBB",
        description="Reference entity rating for the CDS"
    )

    @field_validator("hedge_type")
    @classmethod
    def validate_hedge_type(cls, v: str) -> str:
        """Ensure hedge type is eligible per ERBA NPR p. 288."""
        if v not in ELIGIBLE_CVA_HEDGE_TYPES:
            raise ValueError(
                f"Hedge type {v!r} not eligible for BA-CVA. "
                f"Must be one of: {sorted(ELIGIBLE_CVA_HEDGE_TYPES)}"
            )
        return v

    @field_validator("notional")
    @classmethod
    def validate_notional(cls, v: float) -> float:
        """Notional must be positive per ERBA NPR p. 288."""
        if v < 0:
            raise ValueError(f"Hedge notional must be non-negative, got {v}")
        return v


class BACVACounterpartyResult(BaseModel):
    """Per-counterparty breakdown of BA-CVA calculation.

    Per ERBA NPR p. 281: Each counterparty contributes SCR_c = w_c * M_c * EAD_c
    to the overall BA-CVA charge.
    """
    counterparty_id: str
    rating: str
    sector: str
    ead: float = Field(description="Exposure at Default in $M")
    effective_maturity: float
    risk_weight: float = Field(description="Supervisory risk weight w_c")
    discount_factor: float = Field(description="Supervisory discount factor d_c")
    scr: float = Field(description="Standalone CVA risk = w_c * M_c * EAD_c in $M")
    hedged_scr: float = Field(
        default=0.0,
        description="SCR after hedge reduction in $M"
    )


class BACVAResult(BaseModel):
    """Complete BA-CVA capital charge result.

    Per ERBA NPR p. 281:
    K = beta * K_hedged + (1 - beta) * K_full
    """
    approach: str = Field(
        default="BA-CVA-FULL",
        description="BA-CVA-FULL or BA-CVA-REDUCED"
    )
    k_full: float = Field(
        description="Unhedged BA-CVA charge in $M per ERBA NPR p. 281"
    )
    k_hedged: float = Field(
        default=0.0,
        description="Hedged BA-CVA charge in $M per ERBA NPR p. 281"
    )
    k_ba_cva: float = Field(
        description="Combined BA-CVA charge in $M: beta * K_hedged + (1-beta) * K_full"
    )
    rwa: float = Field(
        description="CVA RWA = K_BA-CVA * 12.5 in $M"
    )
    total_scr: float = Field(
        default=0.0,
        description="Sum of standalone CVA risks across counterparties in $M"
    )
    systematic_component: float = Field(
        default=0.0,
        description="rho^2 * (sum SCR_c)^2 — undiversifiable risk in $M^2"
    )
    idiosyncratic_component: float = Field(
        default=0.0,
        description="(1 - rho^2) * sum SCR_c^2 — diversifiable risk in $M^2"
    )
    counterparty_results: list[BACVACounterpartyResult] = Field(
        default_factory=list
    )
    hedge_count: int = Field(default=0, description="Number of eligible hedges applied")
    total_hedge_notional: float = Field(
        default=0.0,
        description="Sum of hedge notionals in $M"
    )
    index_hedge_contribution: float = Field(
        default=0.0,
        description="Total index hedge contribution to K_hedged in $M"
    )


# =========================================================================
#  Standalone CVA Risk Computation
# =========================================================================

def compute_standalone_cva_risk(
    counterparty: BACVACounterparty,
) -> tuple[float, float, float]:
    """Compute standalone CVA risk (SCR_c) for a single counterparty.

    Per ERBA NPR p. 281 / MAR50.4:
        SCR_c = w_c * M_c * EAD_c

    Where:
        w_c = supervisory risk weight based on rating
        M_c = effective maturity, clipped to [1, 5]
        EAD_c = exposure at default

    Note: The supervisory discount factor d_c is embedded in the
    risk weight calibration per the ERBA framework.

    Args:
        counterparty: The counterparty data.

    Returns:
        Tuple of (SCR_c, risk_weight, discount_factor).
    """
    w_c = get_ba_cva_risk_weight(counterparty.rating)
    m_c = counterparty.effective_maturity  # Already clipped by validator
    d_c = supervisory_discount_factor(m_c)

    scr_c = w_c * m_c * counterparty.ead
    return scr_c, w_c, d_c


# =========================================================================
#  BA-CVA Calculator
# =========================================================================

class BACVACalculator:
    """Basic Approach CVA (BA-CVA) capital calculator.

    Implements both the full (unhedged) and reduced (hedged) versions
    of BA-CVA per BCBS d424 Section 5.1 / ERBA NPR pp. 280-284.

    The BA-CVA formula decomposes CVA risk into:
    - Systematic component: rho^2 * (sum SCR_c)^2
      Captures market-wide credit spread movements.
    - Idiosyncratic component: (1 - rho^2) * sum SCR_c^2
      Captures counterparty-specific credit spread risk.

    Usage::

        calculator = BACVACalculator()

        # Full BA-CVA (no hedges)
        result = calculator.calculate_full(counterparties)
        print(f"BA-CVA charge: ${result.k_ba_cva:,.2f}M")

        # Reduced BA-CVA (with hedges)
        result = calculator.calculate_reduced(counterparties, hedges)
        print(f"BA-CVA charge: ${result.k_ba_cva:,.2f}M")
        print(f"CVA RWA: ${result.rwa:,.2f}M")
    """

    def calculate_full(
        self,
        counterparties: list[BACVACounterparty],
    ) -> BACVAResult:
        """Calculate BA-CVA Full (unhedged) per ERBA NPR p. 281.

        Formula:
            K_full = sqrt(rho^2 * (sum_c SCR_c)^2 + (1 - rho^2) * sum_c SCR_c^2)
            K_BA-CVA = K_full  (no hedging benefit)

        This version is used by banks without eligible CVA hedges.

        Args:
            counterparties: List of counterparties with EAD and maturity.

        Returns:
            BACVAResult with full charge breakdown.
        """
        if not counterparties:
            return BACVAResult(
                k_full=0.0, k_ba_cva=0.0, rwa=0.0,
                approach="BA-CVA-FULL",
            )

        # Compute standalone CVA risk per counterparty
        cp_results: list[BACVACounterpartyResult] = []
        scr_values: list[float] = []

        for cp in counterparties:
            scr_c, w_c, d_c = compute_standalone_cva_risk(cp)
            scr_values.append(scr_c)
            cp_results.append(BACVACounterpartyResult(
                counterparty_id=cp.counterparty_id,
                rating=cp.rating,
                sector=cp.sector,
                ead=cp.ead,
                effective_maturity=cp.effective_maturity,
                risk_weight=w_c,
                discount_factor=d_c,
                scr=scr_c,
                hedged_scr=scr_c,
            ))

        # Aggregation per MAR50.4 / ERBA NPR p. 281
        sum_scr = sum(scr_values)
        sum_scr_sq = sum(s ** 2 for s in scr_values)

        rho = BA_CVA_RHO
        systematic = rho ** 2 * sum_scr ** 2
        idiosyncratic = (1.0 - rho ** 2) * sum_scr_sq

        k_full = math.sqrt(systematic + idiosyncratic)

        # For full BA-CVA, K = K_full (no hedge reduction)
        k_ba_cva = BA_CVA_ALPHA * k_full

        return BACVAResult(
            approach="BA-CVA-FULL",
            k_full=k_full,
            k_hedged=k_full,
            k_ba_cva=k_ba_cva,
            rwa=k_ba_cva * RWA_MULTIPLIER,
            total_scr=sum_scr,
            systematic_component=systematic,
            idiosyncratic_component=idiosyncratic,
            counterparty_results=cp_results,
        )

    def calculate_reduced(
        self,
        counterparties: list[BACVACounterparty],
        hedges: list[BACVAHedge],
    ) -> BACVAResult:
        """Calculate BA-CVA Reduced (with hedges) per ERBA NPR pp. 281-284.

        Formula:
            K_hedged = sqrt(
                rho^2 * (sum_c SCR_c - sum_h SNH_h - IH)^2
                + (1 - rho^2) * sum_c (SCR_c - SN_c)^2
                + sum_h SNH_h^2
            )
            K_BA-CVA = beta * K_hedged + (1 - beta) * K_full

        Where:
            SN_c = single-name hedge allocated to counterparty c
            SNH_h = single-name hedge h contribution
            IH = index hedge contribution (sum of index hedge SCRs)

        Args:
            counterparties: List of counterparties.
            hedges: List of eligible CVA hedges.

        Returns:
            BACVAResult with hedged and unhedged breakdown.
        """
        if not counterparties:
            return BACVAResult(
                k_full=0.0, k_ba_cva=0.0, rwa=0.0,
                approach="BA-CVA-REDUCED",
            )

        # Step 1: Compute full (unhedged) charge
        full_result = self.calculate_full(counterparties)
        k_full = full_result.k_full

        if not hedges:
            # No hedges: reduced = full
            return BACVAResult(
                approach="BA-CVA-REDUCED",
                k_full=k_full,
                k_hedged=k_full,
                k_ba_cva=k_full,
                rwa=k_full * RWA_MULTIPLIER,
                total_scr=full_result.total_scr,
                systematic_component=full_result.systematic_component,
                idiosyncratic_component=full_result.idiosyncratic_component,
                counterparty_results=full_result.counterparty_results,
            )

        # Step 2: Build counterparty SCR map
        scr_by_cp: dict[str, float] = {
            r.counterparty_id: r.scr for r in full_result.counterparty_results
        }
        cp_maturities: dict[str, float] = {
            cp.counterparty_id: cp.effective_maturity for cp in counterparties
        }

        # Step 3: Process hedges per ERBA NPR pp. 282-284
        sn_hedge_by_cp: dict[str, float] = {}  # Single-name hedge per counterparty
        sn_hedge_contributions: list[float] = []  # SNH_h values
        index_hedge_total: float = 0.0

        for h in hedges:
            h_rw = get_ba_cva_risk_weight(h.rating)
            h_maturity = min(h.maturity, MAX_EFFECTIVE_MATURITY)

            if h.hedge_type in ("SINGLE_NAME_CDS", "CONTINGENT_CDS"):
                # Single-name hedge: allocated to specific counterparty
                # Per ERBA NPR p. 282: SNH_h = w_h * M_h * B_h * mat_adj
                exp_mat = cp_maturities.get(h.counterparty_id, 5.0)
                mat_adj = hedge_maturity_adjustment(h.maturity, exp_mat)

                snh = h_rw * h_maturity * h.notional * mat_adj
                sn_hedge_contributions.append(snh)

                # Allocate to counterparty for idiosyncratic component
                cp_id = h.counterparty_id
                sn_hedge_by_cp[cp_id] = sn_hedge_by_cp.get(cp_id, 0.0) + snh

            elif h.hedge_type == "INDEX_CDS":
                # Index hedge: reduces systematic component
                # Per ERBA NPR p. 283: IH = sum of index hedge contributions
                ih = h_rw * h_maturity * h.notional * BA_CVA_HEDGE_DISCOUNT_INDEX
                index_hedge_total += ih

        # Step 4: Compute K_hedged per ERBA NPR p. 282
        rho = BA_CVA_RHO

        # Systematic component: rho^2 * (sum SCR_c - sum SNH_h - IH)^2
        sum_scr = full_result.total_scr
        sum_snh = sum(sn_hedge_contributions)
        systematic_net = sum_scr - sum_snh - index_hedge_total
        systematic_hedged = rho ** 2 * systematic_net ** 2

        # Idiosyncratic component: (1 - rho^2) * sum_c (SCR_c - SN_c)^2
        idiosyncratic_hedged = 0.0
        hedged_cp_results: list[BACVACounterpartyResult] = []

        for cp_result in full_result.counterparty_results:
            cp_id = cp_result.counterparty_id
            sn_c = sn_hedge_by_cp.get(cp_id, 0.0)
            net_scr = max(cp_result.scr - sn_c, 0.0)  # Floor at 0
            idiosyncratic_hedged += net_scr ** 2

            hedged_cp_results.append(BACVACounterpartyResult(
                counterparty_id=cp_id,
                rating=cp_result.rating,
                sector=cp_result.sector,
                ead=cp_result.ead,
                effective_maturity=cp_result.effective_maturity,
                risk_weight=cp_result.risk_weight,
                discount_factor=cp_result.discount_factor,
                scr=cp_result.scr,
                hedged_scr=net_scr,
            ))

        idiosyncratic_hedged *= (1.0 - rho ** 2)

        # Hedge residual risk: sum_h SNH_h^2
        # Per ERBA NPR p. 282: This term captures hedge basis risk
        hedge_residual = sum(snh ** 2 for snh in sn_hedge_contributions)

        k_hedged = math.sqrt(
            max(systematic_hedged + idiosyncratic_hedged + hedge_residual, 0.0)
        )

        # Step 5: Combine per ERBA NPR p. 281
        beta = BA_CVA_BETA
        k_ba_cva = BA_CVA_ALPHA * (beta * k_hedged + (1.0 - beta) * k_full)

        return BACVAResult(
            approach="BA-CVA-REDUCED",
            k_full=k_full,
            k_hedged=k_hedged,
            k_ba_cva=k_ba_cva,
            rwa=k_ba_cva * RWA_MULTIPLIER,
            total_scr=sum_scr,
            systematic_component=systematic_hedged,
            idiosyncratic_component=idiosyncratic_hedged,
            counterparty_results=hedged_cp_results,
            hedge_count=len(hedges),
            total_hedge_notional=sum(h.notional for h in hedges),
            index_hedge_contribution=index_hedge_total,
        )

    def calculate(
        self,
        counterparties: list[BACVACounterparty],
        hedges: Optional[list[BACVAHedge]] = None,
    ) -> BACVAResult:
        """Calculate BA-CVA, automatically selecting full or reduced.

        Per ERBA NPR p. 280: Banks without eligible hedges use BA-CVA Full;
        banks with eligible hedges use BA-CVA Reduced.

        Args:
            counterparties: List of counterparties.
            hedges: Optional list of eligible hedges.

        Returns:
            BACVAResult with appropriate approach.
        """
        if hedges and len(hedges) > 0:
            return self.calculate_reduced(counterparties, hedges)
        return self.calculate_full(counterparties)


# =========================================================================
#  Utility Functions
# =========================================================================

def compute_ba_cva_rwa(
    counterparties: list[BACVACounterparty],
    hedges: Optional[list[BACVAHedge]] = None,
) -> float:
    """Convenience function to compute BA-CVA RWA directly.

    Per ERBA NPR p. 280: RWA_CVA = K_CVA * 12.5

    Args:
        counterparties: List of counterparties.
        hedges: Optional list of hedges.

    Returns:
        CVA RWA in $M.
    """
    calculator = BACVACalculator()
    result = calculator.calculate(counterparties, hedges)
    return result.rwa


def compute_scr_summary(
    counterparties: list[BACVACounterparty],
) -> dict[str, float]:
    """Compute standalone CVA risk summary by counterparty.

    Per ERBA NPR p. 281: SCR_c = w_c * M_c * EAD_c for each counterparty.

    Args:
        counterparties: List of counterparties.

    Returns:
        Dict mapping counterparty_id to SCR_c in $M.
    """
    summary: dict[str, float] = {}
    for cp in counterparties:
        scr_c, _, _ = compute_standalone_cva_risk(cp)
        summary[cp.counterparty_id] = scr_c
    return summary
