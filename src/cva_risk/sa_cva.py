"""Standardized Approach CVA (SA-CVA) capital calculation.

Implements the full SA-CVA framework per BCBS d424 Section 5.2 and
the US Federal Reserve Basel III Endgame Re-Proposal (ERBA NPR pp. 284-295).

SA-CVA uses a sensitivity-based approach analogous to FRTB SBM, computing
delta and vega risk charges for counterparty credit spread and interest rate
risk factors. The key formula is:

    K_CVA = sqrt(K_spread^2 + K_IR^2 + 2 * rho_type * K_spread * K_IR)

Where:
    K_spread = inter-bucket aggregation of credit spread delta + vega
    K_IR     = interest rate component (delta + vega)
    rho_type = 0.30 (cross-risk-type correlation)

All monetary amounts in USD millions ($M).

References:
    - BCBS d424, Section 5.2: Standardized Approach for CVA risk
    - BCBS d457 MAR51: SA-CVA detailed specifications
    - ERBA NPR pp. 284-295: US implementation of SA-CVA
    - ERBA NPR p. 287: Intra-bucket and inter-bucket correlation
    - ERBA NPR p. 288: Cross-risk-type aggregation
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator

from src.cva_risk.cva_params import (
    BA_CVA_RISK_WEIGHTS,
    ELIGIBLE_CVA_HEDGE_TYPES,
    MAX_EFFECTIVE_MATURITY,
    MIN_EFFECTIVE_MATURITY,
    RATING_TO_CVA_RATING,
    SA_CVA_BUCKETS,
    SA_CVA_INTRA_BUCKET_CORRELATION,
    SA_CVA_INTER_BUCKET_CORRELATION,
    SA_CVA_INTER_BUCKET_CORRELATION_MATRIX,
    SA_CVA_IR_TENOR_VERTICES,
    SA_CVA_RISK_TYPE_CORRELATION,
    SA_CVA_TENOR_CORRELATION_BASE,
    SA_CVA_TENOR_VERTICES,
    SA_CVA_VEGA_RISK_WEIGHT,
    SACVARiskFactorType,
    get_sa_cva_bucket,
    get_sa_cva_risk_weight,
    hedge_maturity_adjustment,
    is_investment_grade,
    supervisory_discount_factor,
    tenor_correlation,
)


# =========================================================================
#  Data Models
# =========================================================================

class SACVACounterparty(BaseModel):
    """A counterparty for SA-CVA calculation.

    Per ERBA NPR p. 284: Each counterparty is characterized by its sector,
    credit quality, exposure at default, and effective maturity.
    """
    counterparty_id: str = Field(description="Unique counterparty identifier")
    sector: str = Field(
        default="CORPORATE",
        description="Sector: SOVEREIGN, FINANCIAL, CORPORATE, PUBLIC_SECTOR, OTHER"
    )
    rating: str = Field(
        default="BBB",
        description="Credit rating or internal grade equivalent"
    )
    ead: float = Field(description="Exposure at Default in $M")
    effective_maturity: float = Field(
        default=2.5,
        description="Effective maturity in years, clipped to [1, 5]"
    )
    is_financial: bool = Field(
        default=False,
        description="True if financial institution (affects SA-CCR alpha)"
    )
    netting_set_id: str = Field(
        default="",
        description="Netting set this counterparty belongs to"
    )

    @field_validator("effective_maturity")
    @classmethod
    def clip_maturity(cls, v: float) -> float:
        """Clip effective maturity to [1, 5] per ERBA NPR p. 283."""
        return max(MIN_EFFECTIVE_MATURITY, min(v, MAX_EFFECTIVE_MATURITY))

    @property
    def credit_quality(self) -> str:
        """Determine IG vs HY/NR classification per ERBA NPR p. 282."""
        return "IG" if is_investment_grade(self.rating) else "HY"


class SACVASensitivity(BaseModel):
    """A single CVA sensitivity for SA-CVA delta or vega calculation.

    Per ERBA NPR p. 285: Sensitivities represent the change in CVA
    for a unit shift in the underlying risk factor.
    """
    counterparty_id: str = Field(description="Counterparty this sensitivity belongs to")
    risk_factor_type: SACVARiskFactorType = Field(
        description="Type of risk factor (credit spread, IR, FX, etc.)"
    )
    tenor: float = Field(
        description="Tenor vertex in years (e.g., 0.5, 1.0, 3.0, 5.0, 10.0)"
    )
    value: float = Field(description="Sensitivity value in $M")
    bucket: int = Field(
        default=0,
        description="SA-CVA bucket number (auto-assigned if 0)"
    )
    is_vega: bool = Field(
        default=False,
        description="True if this is a vega sensitivity, False for delta"
    )
    currency: str = Field(
        default="USD",
        description="Currency of the sensitivity"
    )


class SACVAHedge(BaseModel):
    """An eligible CVA hedge position for SA-CVA.

    Per ERBA NPR p. 288: Only single-name CDS, index CDS, and contingent
    CDS are eligible for CVA hedging.
    """
    hedge_id: str = Field(description="Unique hedge identifier")
    counterparty_id: str = Field(
        default="",
        description="Counterparty being hedged (for single-name CDS)"
    )
    hedge_type: str = Field(
        description="SINGLE_NAME_CDS, INDEX_CDS, or CONTINGENT_CDS"
    )
    notional: float = Field(description="Hedge notional in $M")
    maturity: float = Field(description="Remaining hedge maturity in years")
    rating: str = Field(
        default="BBB",
        description="Reference entity rating for CDS"
    )
    sector: str = Field(
        default="CORPORATE",
        description="Reference entity sector"
    )
    tenor: float = Field(
        default=5.0,
        description="CDS tenor vertex for sensitivity mapping"
    )
    bucket: int = Field(
        default=0,
        description="SA-CVA bucket number (auto-assigned if 0)"
    )

    @field_validator("hedge_type")
    @classmethod
    def validate_hedge_type(cls, v: str) -> str:
        """Ensure hedge type is eligible per ERBA NPR p. 288."""
        if v not in ELIGIBLE_CVA_HEDGE_TYPES:
            raise ValueError(
                f"Hedge type {v!r} not eligible. Must be one of: "
                f"{sorted(ELIGIBLE_CVA_HEDGE_TYPES)}"
            )
        return v


class SACVABucketResult(BaseModel):
    """Result of SA-CVA intra-bucket aggregation for a single bucket.

    Per ERBA NPR p. 287: Intra-bucket aggregation uses counterparty
    correlation rho = 0.35 for different counterparties within the
    same sector bucket.
    """
    bucket: int = Field(description="SA-CVA bucket number (1-10)")
    bucket_name: str = Field(default="", description="Descriptive bucket name")
    capital_charge: float = Field(
        description="K_b: intra-bucket capital charge in $M"
    )
    net_weighted_sensitivity: float = Field(
        description="S_b = sum of weighted sensitivities in $M"
    )
    counterparty_count: int = Field(
        default=0,
        description="Number of counterparties in this bucket"
    )
    gross_exposure: float = Field(
        default=0.0,
        description="Gross weighted sensitivity before netting in $M"
    )
    hedge_benefit: float = Field(
        default=0.0,
        description="Reduction due to hedges in $M"
    )


class SACVAResult(BaseModel):
    """Complete SA-CVA capital charge result.

    Per ERBA NPR p. 288: K_CVA = sqrt(K_spread^2 + K_IR^2 + 2*rho*K_spread*K_IR)
    """
    k_spread: float = Field(
        description="Credit spread component capital charge in $M"
    )
    k_ir: float = Field(
        default=0.0,
        description="Interest rate component capital charge in $M"
    )
    k_cva: float = Field(
        description="Total SA-CVA capital charge in $M"
    )
    rwa: float = Field(
        description="CVA RWA = K_CVA * 12.5 in $M"
    )
    approach: str = Field(default="SA-CVA")
    bucket_results: list[SACVABucketResult] = Field(default_factory=list)
    counterparty_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Capital contribution by counterparty ID"
    )
    delta_charge: float = Field(
        default=0.0,
        description="Delta component of the spread charge in $M"
    )
    vega_charge: float = Field(
        default=0.0,
        description="Vega component of the spread charge in $M"
    )
    hedge_benefit_total: float = Field(
        default=0.0,
        description="Total hedge benefit across all buckets in $M"
    )


# =========================================================================
#  SA-CVA Sensitivity Generation
# =========================================================================

def compute_counterparty_cs_sensitivity(
    counterparty: SACVACounterparty,
    tenor: float = 5.0,
) -> float:
    """Compute the credit spread delta sensitivity for a counterparty.

    Per ERBA NPR p. 285: The CVA sensitivity to a 1bp shift in the
    counterparty's credit spread, approximated as:
        s_c,t = EAD_c * d_c * M_c * RW_c

    Where d_c is the supervisory discount factor and RW_c is the
    sector/quality risk weight.

    Args:
        counterparty: The counterparty to compute sensitivity for.
        tenor: Tenor vertex to assign the sensitivity.

    Returns:
        Credit spread sensitivity in $M.
    """
    d_c = supervisory_discount_factor(counterparty.effective_maturity)
    rw = get_sa_cva_risk_weight(counterparty.sector, counterparty.credit_quality)
    return counterparty.ead * d_c * counterparty.effective_maturity * rw


def generate_counterparty_sensitivities(
    counterparty: SACVACounterparty,
    tenors: Optional[list[float]] = None,
) -> list[SACVASensitivity]:
    """Generate SA-CVA credit spread sensitivities for a counterparty.

    Per ERBA NPR p. 285: Sensitivities are allocated across the standard
    tenor vertices. If no explicit tenors are provided, all exposure is
    assigned to the 5Y vertex (most common for derivatives).

    Args:
        counterparty: The counterparty.
        tenors: Optional list of tenor vertices. Defaults to [5.0].

    Returns:
        List of SACVASensitivity objects.
    """
    if tenors is None:
        tenors = [5.0]

    bucket = get_sa_cva_bucket(counterparty.sector, counterparty.credit_quality)
    total_sens = compute_counterparty_cs_sensitivity(counterparty)

    # Distribute sensitivity across tenors (equal allocation if multiple)
    per_tenor = total_sens / len(tenors) if tenors else total_sens

    sensitivities = []
    for t in tenors:
        sensitivities.append(SACVASensitivity(
            counterparty_id=counterparty.counterparty_id,
            risk_factor_type=SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD,
            tenor=t,
            value=per_tenor,
            bucket=bucket,
            is_vega=False,
        ))

    return sensitivities


# =========================================================================
#  Hedge Sensitivity Computation
# =========================================================================

def compute_hedge_sensitivity(
    hedge: SACVAHedge,
    exposure_maturity: float = 5.0,
) -> SACVASensitivity:
    """Compute the credit spread sensitivity for a CVA hedge.

    Per ERBA NPR p. 289: Hedge sensitivities are computed from the
    CDS notional, adjusted for maturity mismatch.

    Args:
        hedge: The hedge position.
        exposure_maturity: Maturity of the hedged exposure.

    Returns:
        SACVASensitivity representing the hedge (negative sensitivity).
    """
    quality = "IG" if is_investment_grade(hedge.rating) else "HY"
    bucket = hedge.bucket if hedge.bucket > 0 else get_sa_cva_bucket(
        hedge.sector, quality,
    )
    rw = get_sa_cva_risk_weight(hedge.sector, quality)

    # Maturity mismatch adjustment per ERBA NPR p. 289
    mat_adj = hedge_maturity_adjustment(hedge.maturity, exposure_maturity)

    # Hedge sensitivity is negative (offsets exposure)
    # Per ERBA NPR p. 289: hedge_sens = -notional * rw * mat_adj
    hedge_value = -hedge.notional * rw * mat_adj * min(hedge.maturity, 5.0)

    return SACVASensitivity(
        counterparty_id=hedge.counterparty_id,
        risk_factor_type=SACVARiskFactorType.REFERENCE_CREDIT_SPREAD,
        tenor=hedge.tenor,
        value=hedge_value,
        bucket=bucket,
        is_vega=False,
    )


# =========================================================================
#  Intra-Bucket Aggregation
# =========================================================================

def _intra_bucket_aggregate(
    weighted_sensitivities: list[float],
    counterparty_ids: list[str],
    rho_same: float = SA_CVA_INTRA_BUCKET_CORRELATION,
) -> tuple[float, float]:
    """Perform intra-bucket aggregation for SA-CVA per ERBA NPR p. 287.

    Within a bucket, sensitivities from the same counterparty have
    correlation 1.0; sensitivities from different counterparties have
    correlation rho (default 0.35).

    Formula:
        K_b = sqrt(sum_k sum_l rho_kl * WS_k * WS_l)
    where rho_kl = 1.0 if same counterparty, rho otherwise.

    Args:
        weighted_sensitivities: List of weighted sensitivity values (WS_k).
        counterparty_ids: Corresponding counterparty IDs for correlation.
        rho_same: Correlation for different counterparties in same bucket.

    Returns:
        Tuple of (K_b, S_b) where K_b is the bucket charge and S_b is
        the net weighted sensitivity.
    """
    n = len(weighted_sensitivities)
    if n == 0:
        return 0.0, 0.0

    ws = np.array(weighted_sensitivities, dtype=np.float64)
    s_b = float(np.sum(ws))

    # Build correlation matrix
    corr = np.full((n, n), rho_same)
    for i in range(n):
        for j in range(n):
            if counterparty_ids[i] == counterparty_ids[j]:
                corr[i, j] = 1.0

    # K_b = sqrt(max(WS' * Corr * WS, 0))
    ws_col = ws.reshape(-1, 1)
    variance_sum = float(np.sum(corr * (ws_col @ ws_col.T)))

    if variance_sum >= 0:
        k_b = math.sqrt(variance_sum)
    else:
        # Fallback: sum of squares
        k_b = math.sqrt(float(np.sum(ws ** 2)))

    return k_b, s_b


def _inter_bucket_aggregate(
    bucket_charges: dict[int, float],
    bucket_net_sensitivities: dict[int, float],
) -> float:
    """Perform inter-bucket aggregation for SA-CVA per ERBA NPR p. 288.

    Formula:
        K = sqrt(sum_b K_b^2 + sum_{b!=c} gamma_bc * S_b * S_c)

    Where gamma_bc comes from the inter-bucket correlation matrix and
    S_b = max(min(net_WS_b, K_b), -K_b).

    Args:
        bucket_charges: Dict of bucket_id -> K_b.
        bucket_net_sensitivities: Dict of bucket_id -> raw S_b.

    Returns:
        Inter-bucket aggregated capital charge in $M.
    """
    if not bucket_charges:
        return 0.0

    buckets = sorted(bucket_charges.keys())

    # Cap S_b per MAR21.4(4) / ERBA NPR p. 288
    capped_s: dict[int, float] = {}
    for b in buckets:
        k_b = bucket_charges[b]
        raw_s = bucket_net_sensitivities.get(b, 0.0)
        capped_s[b] = max(min(raw_s, k_b), -k_b)

    # Sum of K_b^2
    sum_kb_sq = sum(k ** 2 for k in bucket_charges.values())

    # Cross-bucket terms
    cross_sum = 0.0
    for i, b in enumerate(buckets):
        for j, c in enumerate(buckets):
            if b < c:
                # Buckets are 1-indexed, matrix is 0-indexed
                gamma = float(
                    SA_CVA_INTER_BUCKET_CORRELATION_MATRIX[b - 1, c - 1]
                )
                cross_sum += gamma * capped_s[b] * capped_s[c]
    cross_sum *= 2  # Symmetric

    total = sum_kb_sq + cross_sum

    if total >= 0:
        return math.sqrt(total)
    else:
        return sum(abs(k) for k in bucket_charges.values())


# =========================================================================
#  SA-CVA Calculator
# =========================================================================

class SACVACalculator:
    """Standardized Approach CVA (SA-CVA) capital calculator.

    Implements the full SA-CVA framework per BCBS d424 Section 5.2 and
    ERBA NPR pp. 284-295.

    The calculation flow:
    1. Map counterparties to SA-CVA buckets by sector/quality
    2. Compute credit spread delta sensitivities per counterparty
    3. Apply risk weights to produce weighted sensitivities
    4. Intra-bucket aggregation (rho = 0.35 across counterparties)
    5. Inter-bucket aggregation (gamma from correlation matrix)
    6. Optionally compute vega and IR components
    7. Final aggregation: K_CVA = sqrt(K_spread^2 + K_IR^2 + 2*rho*K_spread*K_IR)

    Usage::

        calculator = SACVACalculator()
        result = calculator.calculate(counterparties, hedges=hedges)
        print(f"SA-CVA charge: ${result.k_cva:,.2f}M")
        print(f"CVA RWA: ${result.rwa:,.2f}M")
    """

    def calculate(
        self,
        counterparties: list[SACVACounterparty],
        hedges: Optional[list[SACVAHedge]] = None,
        sensitivities: Optional[list[SACVASensitivity]] = None,
        include_vega: bool = True,
        include_ir: bool = False,
    ) -> SACVAResult:
        """Calculate the full SA-CVA capital charge.

        Per ERBA NPR p. 284: The SA-CVA charge is computed from counterparty
        credit spread sensitivities, with optional IR component.

        Args:
            counterparties: List of counterparties with EAD and maturity.
            hedges: Optional list of eligible CVA hedges.
            sensitivities: Optional pre-computed sensitivities. If not
                provided, sensitivities are generated from counterparty data.
            include_vega: Whether to include vega component (default True).
            include_ir: Whether to include IR component (default False,
                as most banks only have material credit spread CVA risk).

        Returns:
            SACVAResult with full charge breakdown.
        """
        if not counterparties:
            return SACVAResult(
                k_spread=0.0, k_ir=0.0, k_cva=0.0, rwa=0.0,
            )

        # Step 1: Generate or use provided sensitivities
        if sensitivities is None:
            sensitivities = self._generate_all_sensitivities(counterparties)

        # Step 2: Compute hedge sensitivities
        hedge_sensitivities: list[SACVASensitivity] = []
        if hedges:
            # Map counterparty maturities for hedge adjustment
            cp_maturities = {
                cp.counterparty_id: cp.effective_maturity
                for cp in counterparties
            }
            for h in hedges:
                exp_mat = cp_maturities.get(h.counterparty_id, 5.0)
                hedge_sensitivities.append(
                    compute_hedge_sensitivity(h, exp_mat)
                )

        # Step 3: Compute delta spread charge
        delta_result = self._compute_spread_charge(
            sensitivities=[s for s in sensitivities if not s.is_vega],
            hedge_sensitivities=[s for s in hedge_sensitivities if not s.is_vega],
            counterparties=counterparties,
        )

        delta_charge = delta_result["charge"]
        bucket_results = delta_result["bucket_results"]
        cp_breakdown = delta_result["counterparty_breakdown"]
        total_hedge_benefit = delta_result["hedge_benefit"]

        # Step 4: Compute vega charge (if enabled)
        vega_charge = 0.0
        if include_vega:
            vega_charge = self._compute_vega_charge(counterparties)

        # Step 5: K_spread = delta + vega
        k_spread = delta_charge + vega_charge

        # Step 6: Compute IR charge (if enabled)
        k_ir = 0.0
        if include_ir:
            k_ir = self._compute_ir_charge(counterparties)

        # Step 7: Final aggregation per ERBA NPR p. 288
        # K_CVA = sqrt(K_spread^2 + K_IR^2 + 2 * rho * K_spread * K_IR)
        rho = SA_CVA_RISK_TYPE_CORRELATION
        k_cva = math.sqrt(
            k_spread ** 2
            + k_ir ** 2
            + 2.0 * rho * k_spread * k_ir
        )

        return SACVAResult(
            k_spread=k_spread,
            k_ir=k_ir,
            k_cva=k_cva,
            rwa=k_cva * 12.5,
            bucket_results=bucket_results,
            counterparty_breakdown=cp_breakdown,
            delta_charge=delta_charge,
            vega_charge=vega_charge,
            hedge_benefit_total=total_hedge_benefit,
        )

    def _generate_all_sensitivities(
        self,
        counterparties: list[SACVACounterparty],
    ) -> list[SACVASensitivity]:
        """Generate credit spread sensitivities for all counterparties.

        Per ERBA NPR p. 285: Each counterparty generates a set of
        sensitivities across the standard tenor vertices.

        Args:
            counterparties: List of counterparties.

        Returns:
            List of SACVASensitivity objects.
        """
        all_sens: list[SACVASensitivity] = []
        for cp in counterparties:
            all_sens.extend(generate_counterparty_sensitivities(cp))
        return all_sens

    def _compute_spread_charge(
        self,
        sensitivities: list[SACVASensitivity],
        hedge_sensitivities: list[SACVASensitivity],
        counterparties: list[SACVACounterparty],
    ) -> dict:
        """Compute the credit spread delta charge with bucket aggregation.

        Per ERBA NPR pp. 285-288:
        1. Assign sensitivities to buckets
        2. Intra-bucket aggregation with rho = 0.35
        3. Inter-bucket aggregation with gamma from correlation matrix

        Args:
            sensitivities: Counterparty credit spread sensitivities.
            hedge_sensitivities: Hedge credit spread sensitivities.
            counterparties: Counterparty list for metadata.

        Returns:
            Dict with 'charge', 'bucket_results', 'counterparty_breakdown',
            'hedge_benefit'.
        """
        # Group sensitivities by bucket
        bucket_sens: dict[int, list[tuple[str, float]]] = {}
        cp_contributions: dict[str, float] = {}

        for s in sensitivities:
            bucket_id = s.bucket
            if bucket_id not in bucket_sens:
                bucket_sens[bucket_id] = []
            bucket_sens[bucket_id].append((s.counterparty_id, s.value))
            cp_contributions[s.counterparty_id] = (
                cp_contributions.get(s.counterparty_id, 0.0) + s.value
            )

        # Add hedge sensitivities (negative values reduce exposure)
        total_hedge_benefit = 0.0
        for hs in hedge_sensitivities:
            bucket_id = hs.bucket
            if bucket_id not in bucket_sens:
                bucket_sens[bucket_id] = []
            bucket_sens[bucket_id].append((hs.counterparty_id, hs.value))
            total_hedge_benefit += abs(hs.value)

        # Intra-bucket aggregation
        bucket_charges: dict[int, float] = {}
        bucket_net_sens: dict[int, float] = {}
        bucket_results: list[SACVABucketResult] = []

        for bucket_id in sorted(bucket_sens.keys()):
            entries = bucket_sens[bucket_id]
            ws_values = [e[1] for e in entries]
            cp_ids = [e[0] for e in entries]

            k_b, s_b = _intra_bucket_aggregate(ws_values, cp_ids)

            bucket_charges[bucket_id] = k_b
            bucket_net_sens[bucket_id] = s_b

            bucket_info = SA_CVA_BUCKETS.get(bucket_id, {})
            bucket_results.append(SACVABucketResult(
                bucket=bucket_id,
                bucket_name=str(bucket_info.get("name", f"Bucket {bucket_id}")),
                capital_charge=k_b,
                net_weighted_sensitivity=s_b,
                counterparty_count=len(set(cp_ids)),
                gross_exposure=sum(abs(v) for v in ws_values if v > 0),
                hedge_benefit=sum(abs(v) for v in ws_values if v < 0),
            ))

        # Inter-bucket aggregation
        charge = _inter_bucket_aggregate(bucket_charges, bucket_net_sens)

        return {
            "charge": charge,
            "bucket_results": bucket_results,
            "counterparty_breakdown": cp_contributions,
            "hedge_benefit": total_hedge_benefit,
        }

    def _compute_vega_charge(
        self,
        counterparties: list[SACVACounterparty],
    ) -> float:
        """Compute SA-CVA vega charge per ERBA NPR p. 289.

        The vega charge captures the risk from changes in implied volatility
        of credit spreads. For counterparties with option-like CVA exposure,
        the vega charge is a fraction of the delta charge.

        Per MAR51.10: vega_RW = 0.55

        Args:
            counterparties: List of counterparties.

        Returns:
            Vega capital charge in $M.
        """
        # Vega is approximated as a fraction of the delta sensitivity
        # per ERBA NPR p. 289: vega contribution = RW_vega * delta_sens
        vega_ws: list[float] = []
        cp_ids: list[str] = []

        for cp in counterparties:
            delta_sens = compute_counterparty_cs_sensitivity(cp)
            vega_sens = delta_sens * SA_CVA_VEGA_RISK_WEIGHT
            vega_ws.append(vega_sens)
            cp_ids.append(cp.counterparty_id)

        if not vega_ws:
            return 0.0

        # Single-bucket aggregation (simplified for vega)
        k_vega, _ = _intra_bucket_aggregate(
            vega_ws, cp_ids, rho_same=SA_CVA_INTRA_BUCKET_CORRELATION,
        )
        return k_vega

    def _compute_ir_charge(
        self,
        counterparties: list[SACVACounterparty],
    ) -> float:
        """Compute SA-CVA interest rate component per ERBA NPR p. 290.

        The IR component captures the sensitivity of CVA to changes in
        risk-free interest rates. For most derivatives portfolios, this
        is secondary to credit spread risk.

        Per ERBA NPR p. 290: IR sensitivities are computed from the
        derivative portfolio's exposure to rate changes, weighted by
        supervisory IR risk weights.

        Args:
            counterparties: List of counterparties.

        Returns:
            IR capital charge in $M.
        """
        # IR risk weights by tenor per ERBA NPR p. 290
        ir_risk_weights = {
            1.0: 0.017,
            2.0: 0.016,
            5.0: 0.013,
            10.0: 0.012,
            30.0: 0.013,
        }

        # For each counterparty, compute approximate IR sensitivity
        # IR sensitivity ~ EAD * d_c * duration_proxy * IR_RW
        ir_ws: list[float] = []
        cp_ids: list[str] = []

        for cp in counterparties:
            d_c = supervisory_discount_factor(cp.effective_maturity)
            # Map effective maturity to closest IR tenor
            closest_tenor = min(
                SA_CVA_IR_TENOR_VERTICES,
                key=lambda t: abs(t - cp.effective_maturity),
            )
            ir_rw = ir_risk_weights.get(closest_tenor, 0.013)

            ir_sens = cp.ead * d_c * cp.effective_maturity * ir_rw
            ir_ws.append(ir_sens)
            cp_ids.append(cp.counterparty_id)

        if not ir_ws:
            return 0.0

        k_ir, _ = _intra_bucket_aggregate(
            ir_ws, cp_ids, rho_same=SA_CVA_INTRA_BUCKET_CORRELATION,
        )
        return k_ir

    def calculate_with_sensitivities(
        self,
        sensitivities: list[SACVASensitivity],
        hedge_sensitivities: Optional[list[SACVASensitivity]] = None,
    ) -> SACVAResult:
        """Calculate SA-CVA from pre-computed sensitivities.

        This method is for advanced users who have their own CVA sensitivity
        engine and want to use the SA-CVA aggregation framework.

        Per ERBA NPR p. 285: When banks compute their own CVA sensitivities,
        those sensitivities feed directly into the aggregation.

        Args:
            sensitivities: Pre-computed CVA sensitivities.
            hedge_sensitivities: Pre-computed hedge sensitivities.

        Returns:
            SACVAResult with charge breakdown.
        """
        if not sensitivities:
            return SACVAResult(k_spread=0.0, k_ir=0.0, k_cva=0.0, rwa=0.0)

        hedge_sens = hedge_sensitivities or []

        # Separate by risk factor type
        cs_delta = [s for s in sensitivities
                    if s.risk_factor_type in (
                        SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD,
                        SACVARiskFactorType.REFERENCE_CREDIT_SPREAD,
                    ) and not s.is_vega]
        cs_vega = [s for s in sensitivities
                   if s.risk_factor_type in (
                       SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD,
                       SACVARiskFactorType.REFERENCE_CREDIT_SPREAD,
                   ) and s.is_vega]
        ir_delta = [s for s in sensitivities
                    if s.risk_factor_type == SACVARiskFactorType.INTEREST_RATE
                    and not s.is_vega]

        # Credit spread delta
        delta_charge = self._aggregate_sensitivities(cs_delta + hedge_sens)

        # Credit spread vega
        vega_charge = self._aggregate_sensitivities(cs_vega)

        k_spread = delta_charge + vega_charge

        # IR delta
        k_ir = self._aggregate_sensitivities(ir_delta)

        # Final aggregation
        rho = SA_CVA_RISK_TYPE_CORRELATION
        k_cva = math.sqrt(
            k_spread ** 2 + k_ir ** 2 + 2.0 * rho * k_spread * k_ir
        )

        return SACVAResult(
            k_spread=k_spread,
            k_ir=k_ir,
            k_cva=k_cva,
            rwa=k_cva * 12.5,
            delta_charge=delta_charge,
            vega_charge=vega_charge,
        )

    def _aggregate_sensitivities(
        self,
        sensitivities: list[SACVASensitivity],
    ) -> float:
        """Aggregate a list of sensitivities using SA-CVA bucket framework.

        Per ERBA NPR pp. 287-288: Two-level aggregation (intra then inter).

        Args:
            sensitivities: Sensitivities to aggregate.

        Returns:
            Aggregated capital charge in $M.
        """
        if not sensitivities:
            return 0.0

        # Group by bucket
        bucket_data: dict[int, list[tuple[str, float]]] = {}
        for s in sensitivities:
            b = s.bucket
            if b not in bucket_data:
                bucket_data[b] = []
            bucket_data[b].append((s.counterparty_id, s.value))

        # Intra-bucket
        bucket_charges: dict[int, float] = {}
        bucket_net_sens: dict[int, float] = {}

        for b, entries in bucket_data.items():
            ws = [e[1] for e in entries]
            ids = [e[0] for e in entries]
            k_b, s_b = _intra_bucket_aggregate(ws, ids)
            bucket_charges[b] = k_b
            bucket_net_sens[b] = s_b

        # Inter-bucket
        return _inter_bucket_aggregate(bucket_charges, bucket_net_sens)
