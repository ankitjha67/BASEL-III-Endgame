"""Securitization Framework — SEC-SA and SEC-ERBA per CRE40 / BCBS d424.

Implements risk weight calculations for securitization exposures using:
- SEC-SA: Simplified Supervisory Formula Approach (SSFA)
- SEC-ERBA: External Ratings-Based Approach (where ratings available)

The hierarchy is: SEC-IRBA > SEC-ERBA > SEC-SA.
US Basel III Endgame primarily uses SEC-SA with limited ERBA.

Reference: BCBS d424 CRE40, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, Field

from src.securitization.sec_params import (
    P_NON_RESECURITIZATION as P_NON_RESEC,
    P_RESECURITIZATION as P_RESEC,
    SEC_ERBA_RW,
)

# Regulatory constants
MAX_RW: float = 12.50   # 1250% cap
MIN_RW_RESEC: float = 1.00  # 100% floor for resecuritization


def get_erba_risk_weight(
    rating: str, is_senior: bool, maturity_years: float
) -> float | None:
    """Look up SEC-ERBA risk weight from the regulatory table.

    Args:
        rating: External rating (AAA, AA, A, BBB, BB, B).
        is_senior: Whether the tranche is senior.
        maturity_years: Remaining maturity in years.

    Returns:
        Risk weight as decimal, or None if rating not in table.
    """
    seniority = "SENIOR" if is_senior else "NON_SENIOR"
    mat_bucket = "SHORT" if maturity_years <= 1.0 else "LONG"
    key = (rating.upper(), seniority, mat_bucket)
    return SEC_ERBA_RW.get(key)


# =========================================================================
#  Models
# =========================================================================

class SecuritizationPool(BaseModel):
    """Underlying securitization pool characteristics."""
    pool_id: str
    total_ead: float = Field(description="Total EAD of underlying pool")
    pool_rwa: float = Field(description="RWA of pool if held directly (for K_g)")
    delinquency_ratio: float = Field(default=0.0, description="W parameter: delinquency ratio")
    asset_type: str = Field(default="CORPORATE", description="RMBS, CMBS, CLO, ABS, CORPORATE")


class SecuritizationTranche(BaseModel):
    """A single securitization tranche/position."""
    tranche_id: str
    pool_id: str
    attachment_point: float = Field(description="A: lower attachment (0.0 to 1.0)")
    detachment_point: float = Field(description="D: upper detachment (0.0 to 1.0)")
    notional: float = Field(description="Notional exposure amount")
    is_senior: bool = False
    is_resecuritization: bool = False
    external_rating: Optional[str] = None
    maturity_years: float = 5.0


class SecResult(BaseModel):
    """Result of securitization RWA calculation."""
    total_rwa: float = 0.0
    rwa_by_tranche: dict[str, float] = {}
    rw_by_tranche: dict[str, float] = {}
    approach_used: dict[str, str] = {}
    k_g: float = 0.0


# =========================================================================
#  Calculator
# =========================================================================

class SecuritizationCalculator:
    """Securitization risk weight calculator using SEC-SA (SSFA) and SEC-ERBA.

    Usage::

        calc = SecuritizationCalculator()
        result = calc.calculate(tranches, pool)
        print(f"Sec RWA: {result.total_rwa:,.0f}")
    """

    def calculate(
        self,
        tranches: list[SecuritizationTranche],
        pool: SecuritizationPool,
    ) -> SecResult:
        """Calculate RWA for all tranches.

        Args:
            tranches: List of securitization tranches.
            pool: Underlying pool characteristics.

        Returns:
            SecResult with RWA and risk weights per tranche.
        """
        if not tranches:
            return SecResult(total_rwa=0.0)

        # Pool capital ratio K_g
        k_g = pool.pool_rwa / pool.total_ead if pool.total_ead > 0 else 0.08

        total_rwa = 0.0
        rwa_by_tranche: dict[str, float] = {}
        rw_by_tranche: dict[str, float] = {}
        approach_by_tranche: dict[str, str] = {}

        for tranche in tranches:
            # Determine approach
            if tranche.external_rating:
                erba_rw = get_erba_risk_weight(
                    tranche.external_rating,
                    tranche.is_senior,
                    tranche.maturity_years,
                )
                sa_rw = self._ssfa_risk_weight(tranche, k_g, pool)
                # Use lower of ERBA and SA
                if erba_rw is not None:
                    rw = min(erba_rw, sa_rw)
                    approach = "SEC-ERBA" if erba_rw <= sa_rw else "SEC-SA"
                else:
                    rw = sa_rw
                    approach = "SEC-SA"
            else:
                rw = self._ssfa_risk_weight(tranche, k_g, pool)
                approach = "SEC-SA"

            # Apply caps and floors
            rw = min(rw, MAX_RW)
            if tranche.is_resecuritization:
                rw = max(rw, MIN_RW_RESEC)

            tranche_rwa = tranche.notional * rw
            total_rwa += tranche_rwa
            rwa_by_tranche[tranche.tranche_id] = tranche_rwa
            rw_by_tranche[tranche.tranche_id] = rw
            approach_by_tranche[tranche.tranche_id] = approach

        return SecResult(
            total_rwa=total_rwa,
            rwa_by_tranche=rwa_by_tranche,
            rw_by_tranche=rw_by_tranche,
            approach_used=approach_by_tranche,
            k_g=k_g,
        )

    def _ssfa_risk_weight(
        self,
        tranche: SecuritizationTranche,
        k_g: float,
        pool: SecuritizationPool,
    ) -> float:
        """Compute SEC-SA risk weight using SSFA per CRE40.4.

        SSFA formula:
            K_SSFA(a, d) = (e^(alpha*u) - e^(alpha*l)) / (alpha * (u - l))

        Where:
            alpha = -(1 / (p * K_g))
            u = D - K_g
            l = max(A - K_g, 0)
            p = 0.5 (non-resec) or 1.5 (resec)

        Args:
            tranche: The tranche to evaluate.
            k_g: Pool capital ratio.
            pool: Pool characteristics.

        Returns:
            Risk weight as a decimal (e.g., 0.15 for 15%).
        """
        a = tranche.attachment_point
        d = tranche.detachment_point
        p = P_RESEC if tranche.is_resecuritization else P_NON_RESEC

        # Adjust K_g for delinquency
        k_a = k_g + pool.delinquency_ratio * (1 - k_g)

        # SSFA parameters
        u = d - k_a
        l_val = max(a - k_a, 0.0)

        if d <= k_a:
            # Entire tranche below K_a → 1250% RW
            return MAX_RW

        if a >= d:
            return MAX_RW

        if k_a <= 0:
            k_a = 0.0001  # Avoid division by zero

        alpha = -(1.0 / (p * k_a))

        if u <= l_val or u <= 0:
            return MAX_RW

        # SSFA formula
        try:
            numerator = math.exp(alpha * u) - math.exp(alpha * l_val)
            denominator = alpha * (u - l_val)

            if abs(denominator) < 1e-12:
                return MAX_RW

            rw = numerator / denominator
        except (OverflowError, ValueError):
            rw = MAX_RW

        return min(max(rw, 0.0), MAX_RW)
