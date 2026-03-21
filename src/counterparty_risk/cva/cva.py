"""CVA Risk Calculator — Basic Approach (BA-CVA) per MAR50.

Implements the Credit Valuation Adjustment capital charge using
the Basic Approach (BA-CVA) as specified in BCBS d457 MAR50
and the US Basel III Endgame Final Rule.

The BA-CVA formula:
    K = beta * K_hedged + (1 - beta) * K_full

Where:
    K_full = sqrt(rho^2 * (sum S_c*M_c*EAD_c)^2 + (1-rho^2) * sum (S_c*M_c*EAD_c)^2)
    beta = 0.25
    rho = 0.50
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, Field

from src.counterparty_risk.cva.cva_params import (
    BA_CVA_BETA as BETA,
    BA_CVA_RHO as RHO,
    CVA_RISK_WEIGHTS,
    get_sa_cva_risk_weight as get_cva_risk_weight,
)


# =========================================================================
#  Models
# =========================================================================

class CVACounterparty(BaseModel):
    """A counterparty for CVA calculation."""
    counterparty_id: str
    rating: str = Field(description="Credit rating: AAA, AA, A, BBB, BB, B, CCC, UNRATED")
    sector: str = Field(default="CORPORATE", description="FINANCIAL, SOVEREIGN, CORPORATE")
    ead: float = Field(description="Exposure at Default for this counterparty")
    effective_maturity: float = Field(default=2.5, description="Effective maturity in years")
    is_financial: bool = False
    netting_set_count: int = 1


class CVAHedge(BaseModel):
    """A CVA hedge position (CDS or eligible hedge)."""
    hedge_id: str
    counterparty_id: str = Field(description="Counterparty being hedged")
    notional: float
    maturity: float
    rating: str = "BBB"


class CVAResult(BaseModel):
    """Result of CVA capital calculation."""
    total_cva_charge: float
    k_full: float = 0.0
    k_hedged: float = 0.0
    k_spread: float = 0.0
    k_counterparty: float = 0.0
    approach: str = "BA-CVA"
    counterparty_charges: dict[str, float] = {}


# =========================================================================
#  Calculator
# =========================================================================

class CVACalculator:
    """CVA Risk calculator implementing BA-CVA and SA-CVA.

    Usage::

        calc = CVACalculator()
        result = calc.calculate_ba_cva(counterparties)
        print(f"CVA charge: {result.total_cva_charge:,.0f}")
    """

    def calculate_ba_cva(
        self,
        counterparties: list[CVACounterparty],
        hedges: Optional[list[CVAHedge]] = None,
    ) -> CVAResult:
        """Calculate BA-CVA capital charge per MAR50.

        Formula:
            K_full = sqrt(rho^2 * (sum_c SCR_c)^2 + (1 - rho^2) * sum_c SCR_c^2)
            K = beta * K_hedged + (1 - beta) * K_full

        Where SCR_c = S_c * M_c * EAD_c (Standalone CVA Risk per counterparty).

        Args:
            counterparties: List of CVA counterparties.
            hedges: Optional list of CVA hedges.

        Returns:
            CVAResult with total charge and breakdown.
        """
        if not counterparties:
            return CVAResult(total_cva_charge=0.0, approach="BA-CVA")

        # Compute standalone CVA risk per counterparty
        scr_by_cp: dict[str, float] = {}
        for cp in counterparties:
            s_c = get_cva_risk_weight(cp.rating)
            m_c = min(cp.effective_maturity, 5.0)  # Cap at 5 years
            scr_c = s_c * m_c * cp.ead
            scr_by_cp[cp.counterparty_id] = scr_c

        # K_full (unhedged) per MAR50.4
        sum_scr = sum(scr_by_cp.values())
        sum_scr_sq = sum(s ** 2 for s in scr_by_cp.values())

        systematic = RHO ** 2 * sum_scr ** 2
        idiosyncratic = (1 - RHO ** 2) * sum_scr_sq
        k_full = math.sqrt(systematic + idiosyncratic)

        # K_hedged (with hedge benefit) per MAR50.5
        k_hedged = k_full  # Default: no hedges
        if hedges:
            # Apply hedge benefit: reduce SCR for hedged counterparties
            hedge_by_cp: dict[str, float] = {}
            for h in hedges:
                s_h = get_cva_risk_weight(h.rating)
                hedge_scr = s_h * min(h.maturity, 5.0) * h.notional
                hedge_by_cp[h.counterparty_id] = (
                    hedge_by_cp.get(h.counterparty_id, 0.0) + hedge_scr
                )

            net_scr: dict[str, float] = {}
            for cp_id, scr in scr_by_cp.items():
                hedge_amt = hedge_by_cp.get(cp_id, 0.0)
                net_scr[cp_id] = max(scr - hedge_amt, 0.0)

            net_sum = sum(net_scr.values())
            net_sum_sq = sum(s ** 2 for s in net_scr.values())
            k_hedged = math.sqrt(
                RHO ** 2 * net_sum ** 2
                + (1 - RHO ** 2) * net_sum_sq
            )

        # Combined charge per MAR50.3
        total = BETA * k_hedged + (1 - BETA) * k_full

        return CVAResult(
            total_cva_charge=total,
            k_full=k_full,
            k_hedged=k_hedged,
            approach="BA-CVA",
            counterparty_charges=scr_by_cp,
        )

    def calculate_sa_cva(
        self,
        counterparties: list[CVACounterparty],
        sensitivities: Optional[list] = None,
    ) -> CVAResult:
        """Calculate SA-CVA capital charge per MAR51.

        SA-CVA uses a delta+vega framework similar to FRTB SBM.
        For simplicity, this implementation uses the BA-CVA as a proxy
        with a reduced charge (SA-CVA typically produces lower capital).

        Args:
            counterparties: List of counterparties.
            sensitivities: Optional spread sensitivities.

        Returns:
            CVAResult with SA-CVA charge.
        """
        # SA-CVA typically gives ~15-25% reduction vs BA-CVA
        ba_result = self.calculate_ba_cva(counterparties)
        sa_factor = 0.80  # Approximate SA-CVA / BA-CVA ratio

        return CVAResult(
            total_cva_charge=ba_result.k_full * sa_factor,
            k_full=ba_result.k_full,
            k_spread=ba_result.k_full * sa_factor * 0.6,
            k_counterparty=ba_result.k_full * sa_factor * 0.4,
            approach="SA-CVA",
            counterparty_charges=ba_result.counterparty_charges,
        )
