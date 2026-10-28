"""Basic approach for CVA risk (BA-CVA) — ERBA NPR §__.222.

Implements the BA-CVA capital requirement of the March 2026 US re-proposal
(ERBA NPR §__.222, rule text pp. 950–988; preamble §V.B.3, pp. 455–468).

Formulas (all citations to ERBA NPR §__.222 unless noted):

    K_basic     = 0.65 · ( β · K_unhedged + (1 − β) · K_hedged ),   β = 0.25
    K_unhedged  = sqrt( (ρ · Σ_c SCVA_c)² + (1 − ρ²) · Σ_c SCVA_c² ),   ρ = 0.50
    SCVA_c      = (1/α) · RW_c · Σ_NS ( M_NS · EAD_NS · DF_NS )
    DF_NS       = (1 − e^(−0.05·M_NS)) / (0.05·M_NS)
    K_hedged    = sqrt( (ρ · Σ_c (SCVA_c − SNH_c) − IH)²
                        + (1 − ρ²) · Σ_c (SCVA_c − SNH_c)²
                        + Σ_c HMA_c )
    SNH_c       = Σ_{h∈c} r_hc · RW_h · M_h · B_h · DF_h
    HMA_c       = Σ_{h∈c} (1 − r_hc²) · (RW_h · M_h · B_h · DF_h)²
    IH          = Σ_i RW_i · M_i · B_i · DF_i,   RW_i = 0.7 × Table 1 weight
    RWA_CVA     = 12.5 · K_basic

When a banking organization has no eligible CVA hedges, K_hedged equals
K_unhedged and K_basic = 0.65 · K_unhedged (the *reduced* BA-CVA,
preamble p. 457).

α = 1.4, except 1.0 for commercial end-user counterparties whose exposure
amount is calculated under §__.114(e)(4). EAD_NS is the SA-CCR exposure
amount of the netting set (§__.113–§__.114). M_NS is the notional-weighted
average remaining maturity of the netting set with no floor or cap.

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator, model_validator

from src.cva_risk.cva_params import (
    BA_CVA_BETA,
    BA_CVA_DISCOUNT_SCALAR,
    BA_CVA_HEDGE_CORRELATION,
    BA_CVA_INDEX_HEDGE_FACTOR,
    BA_CVA_RHO,
    RWA_MULTIPLIER,
    BACVAHedgeRelationship,
    CVAApproach,
    CVACreditQuality,
    CVAHedgeType,
    CVASector,
    credit_quality_from_grade,
    get_ba_cva_alpha,
    get_ba_cva_risk_weight,
    netting_set_effective_maturity,
    normalize_sector,
    supervisory_discount_factor,
)

# =========================================================================
#  Data models
# =========================================================================

class BACVAPosition(BaseModel):
    """A CVA risk covered position inside a netting set.

    Used only to derive M_NS per ERBA NPR §__.222(b): the notional-weighted
    average remaining maturity of the netting set.
    """
    notional: float = Field(description="Notional amount in $M")
    remaining_maturity: float = Field(
        description="Remaining contractual maturity in years (whole or fractional)"
    )

    @field_validator("notional")
    @classmethod
    def _positive_notional(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Position notional must be non-negative, got {v}")
        return v


class BACVANettingSet(BaseModel):
    """A netting set NS of a counterparty for SCVA_c per ERBA NPR §__.222(b).

    Supply either ``effective_maturity`` directly or the ``positions`` from
    which M_NS is derived as the notional-weighted average remaining
    maturity (no floor, no cap).
    """
    netting_set_id: str = Field(default="", description="Netting set identifier")
    ead: float = Field(
        description="EAD_NS: SA-CCR exposure amount of the netting set in $M "
                    "(ERBA NPR §__.113–§__.114)"
    )
    effective_maturity: float | None = Field(
        default=None,
        description="M_NS in years; derived from positions if omitted",
    )
    positions: list[BACVAPosition] = Field(
        default_factory=list,
        description="CVA risk covered positions used to derive M_NS",
    )

    @field_validator("ead")
    @classmethod
    def _non_negative_ead(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"EAD must be non-negative, got {v}")
        return v

    @model_validator(mode="after")
    def _resolve_maturity(self) -> BACVANettingSet:
        if self.effective_maturity is None:
            if not self.positions:
                raise ValueError(
                    "Netting set requires effective_maturity or positions"
                )
            self.effective_maturity = netting_set_effective_maturity(
                [(p.notional, p.remaining_maturity) for p in self.positions]
            )
        elif self.effective_maturity < 0:
            raise ValueError("effective_maturity must be non-negative")
        return self

    @property
    def maturity(self) -> float:
        """M_NS in years (always resolved after validation)."""
        assert self.effective_maturity is not None
        return self.effective_maturity

    @property
    def discount_factor(self) -> float:
        """DF_NS per ERBA NPR §__.222(b)."""
        return supervisory_discount_factor(self.maturity)


class BACVACounterparty(BaseModel):
    """A counterparty c for BA-CVA per ERBA NPR §__.222(b).

    Risk weight RW_c is taken from Table 1 to §__.222 by sector and the
    banking organization's own credit quality assessment. Either
    ``credit_quality`` or the convenience ``rating`` label must be given.

    For a single-netting-set counterparty the shorthand ``ead`` and
    ``effective_maturity`` fields may be used instead of ``netting_sets``.
    """
    counterparty_id: str = Field(description="Unique counterparty identifier")
    sector: CVASector = Field(
        default=CVASector.OTHER_SECTOR,
        description="One of the eight sectors of Table 1 to ERBA NPR §__.222",
    )
    credit_quality: CVACreditQuality | None = Field(
        default=None,
        description="Bank-internal credit quality category (IG / speculative / "
                    "sub-speculative) per ERBA NPR §__.2",
    )
    rating: str | None = Field(
        default=None,
        description="Convenience internal grade label mapped to credit_quality "
                    "(e.g. 'BBB' → IG); not an external rating",
    )
    is_commercial_end_user: bool = Field(
        default=False,
        description="True if exposure amount is computed under §__.114(e)(4) "
                    "(alpha = 1.0 instead of 1.4)",
    )
    region: str = Field(
        default="",
        description="Country or territorial entity (hedge matching, Table 2)",
    )
    netting_sets: list[BACVANettingSet] = Field(
        default_factory=list,
        description="Netting sets NS with EAD_NS and M_NS",
    )
    ead: float | None = Field(
        default=None,
        description="Shorthand: EAD of a single netting set in $M",
    )
    effective_maturity: float | None = Field(
        default=None,
        description="Shorthand: M of the single netting set in years",
    )

    @field_validator("sector", mode="before")
    @classmethod
    def _coerce_sector(cls, v: object) -> CVASector:
        if isinstance(v, CVASector):
            return v
        return normalize_sector(str(v))

    @model_validator(mode="after")
    def _resolve(self) -> BACVACounterparty:
        if self.credit_quality is None:
            if self.rating is None:
                raise ValueError(
                    "Provide credit_quality (or a rating label) for the counterparty"
                )
            self.credit_quality = credit_quality_from_grade(self.rating)
        if not self.netting_sets:
            if self.ead is None:
                raise ValueError("Provide netting_sets or ead/effective_maturity")
            if self.effective_maturity is None:
                raise ValueError("effective_maturity is required with ead")
            self.netting_sets = [BACVANettingSet(
                netting_set_id=f"{self.counterparty_id}-NS1",
                ead=self.ead,
                effective_maturity=self.effective_maturity,
            )]
        if self.ead is None:
            self.ead = sum(ns.ead for ns in self.netting_sets)
        if self.effective_maturity is None:
            total = sum(ns.ead for ns in self.netting_sets)
            self.effective_maturity = (
                sum(ns.ead * ns.maturity for ns in self.netting_sets) / total
                if total > 0 else self.netting_sets[0].maturity
            )
        return self

    @property
    def quality(self) -> CVACreditQuality:
        """Resolved credit quality category."""
        assert self.credit_quality is not None
        return self.credit_quality

    @property
    def risk_weight(self) -> float:
        """RW_c per Table 1 to ERBA NPR §__.222."""
        return get_ba_cva_risk_weight(self.sector, self.quality)

    @property
    def alpha(self) -> float:
        """α per ERBA NPR §__.222(b): 1.4, or 1.0 for commercial end-users."""
        return get_ba_cva_alpha(self.is_commercial_end_user)


class BACVAIndexConstituent(BaseModel):
    """A constituent of an index hedge for RW_i per ERBA NPR §__.222(c).

    For indices spanning multiple sectors or credit qualities RW_i is the
    notional-weighted average of the constituents' Table 1 weights × 0.7.
    """
    weight: float = Field(description="Notional weight of the constituent (any positive scale)")
    sector: CVASector
    credit_quality: CVACreditQuality

    @field_validator("sector", mode="before")
    @classmethod
    def _coerce_sector(cls, v: object) -> CVASector:
        return v if isinstance(v, CVASector) else normalize_sector(str(v))

    @field_validator("credit_quality", mode="before")
    @classmethod
    def _coerce_quality(cls, v: object) -> CVACreditQuality:
        return v if isinstance(v, CVACreditQuality) else credit_quality_from_grade(str(v))


class BACVAHedge(BaseModel):
    """An eligible BA-CVA hedge per ERBA NPR §__.222(c).

    Eligible instruments are single-name CDS, single-name contingent CDS
    and index CDS. For a single-name contingent CDS the notional B_h is the
    current market value of the reference portfolio or instrument
    (preamble fn. 500). A whole transaction must be designated; fractions
    are not recognized.
    """
    hedge_id: str = Field(description="Unique hedge identifier")
    hedge_type: CVAHedgeType = Field(description="SINGLE_NAME_CDS, CONTINGENT_CDS or INDEX_CDS")
    notional: float = Field(description="B_h: notional in $M")
    maturity: float = Field(description="M_h: remaining maturity in years")
    counterparty_id: str = Field(
        default="",
        description="Counterparty c the single-name hedge is assigned to",
    )
    relationship: BACVAHedgeRelationship = Field(
        default=BACVAHedgeRelationship.DIRECT,
        description="Relationship of the reference name to counterparty c "
                    "(Table 2 to ERBA NPR §__.222)",
    )
    reference_sector: CVASector | None = Field(
        default=None,
        description="Sector of the reference name (single-name) or of all "
                    "constituents (single-sector index)",
    )
    reference_credit_quality: CVACreditQuality | None = Field(
        default=None,
        description="Credit quality of the reference name / index constituents",
    )
    rating: str | None = Field(
        default=None,
        description="Convenience grade label for reference_credit_quality",
    )
    constituents: list[BACVAIndexConstituent] = Field(
        default_factory=list,
        description="Index constituents (multi-sector / mixed-quality indices)",
    )

    @field_validator("hedge_type", mode="before")
    @classmethod
    def _coerce_type(cls, v: object) -> CVAHedgeType:
        return v if isinstance(v, CVAHedgeType) else CVAHedgeType(str(v))

    @field_validator("relationship", mode="before")
    @classmethod
    def _coerce_relationship(cls, v: object) -> BACVAHedgeRelationship:
        return v if isinstance(v, BACVAHedgeRelationship) else BACVAHedgeRelationship(str(v))

    @field_validator("reference_sector", mode="before")
    @classmethod
    def _coerce_sector(cls, v: object) -> CVASector | None:
        if v is None or isinstance(v, CVASector):
            return v
        return normalize_sector(str(v))

    @field_validator("notional", "maturity")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Hedge notional and maturity must be non-negative, got {v}")
        return v

    @model_validator(mode="after")
    def _resolve(self) -> BACVAHedge:
        if self.reference_credit_quality is None and self.rating is not None:
            self.reference_credit_quality = credit_quality_from_grade(self.rating)
        if self.is_index:
            if not self.constituents and (
                self.reference_sector is None or self.reference_credit_quality is None
            ):
                raise ValueError(
                    "Index hedge requires constituents or a single reference_sector "
                    "and reference_credit_quality"
                )
        else:
            if not self.counterparty_id:
                raise ValueError("Single-name hedge must name the counterparty it hedges")
            if self.reference_sector is None or self.reference_credit_quality is None:
                raise ValueError(
                    "Single-name hedge requires reference_sector and reference_credit_quality"
                )
        return self

    @property
    def is_index(self) -> bool:
        """True for index CDS hedges (contribute to IH)."""
        return self.hedge_type is CVAHedgeType.INDEX_CDS

    @property
    def correlation(self) -> float:
        """r_hc per Table 2 to ERBA NPR §__.222 (single-name hedges only)."""
        return BA_CVA_HEDGE_CORRELATION[self.relationship]

    @property
    def risk_weight(self) -> float:
        """RW_h (single-name) or RW_i (index) per ERBA NPR §__.222(c).

        Single-name: Table 1 weight of the reference name. Index: Table 1
        weight × 0.7 for a single-sector, single-quality index; otherwise
        the notional-weighted average of constituent weights × 0.7.
        """
        if not self.is_index:
            assert self.reference_sector is not None and self.reference_credit_quality is not None
            return get_ba_cva_risk_weight(self.reference_sector, self.reference_credit_quality)
        if self.constituents:
            total_w = sum(c.weight for c in self.constituents)
            if total_w <= 0:
                raise ValueError("Index constituent weights must sum to a positive value")
            avg = sum(
                c.weight * get_ba_cva_risk_weight(c.sector, c.credit_quality)
                for c in self.constituents
            ) / total_w
            return BA_CVA_INDEX_HEDGE_FACTOR * avg
        assert self.reference_sector is not None and self.reference_credit_quality is not None
        return BA_CVA_INDEX_HEDGE_FACTOR * get_ba_cva_risk_weight(
            self.reference_sector, self.reference_credit_quality
        )

    @property
    def discount_factor(self) -> float:
        """DF_h / DF_i per ERBA NPR §__.222(c)."""
        return supervisory_discount_factor(self.maturity)

    @property
    def weighted_amount(self) -> float:
        """RW · M · B · DF of the hedge in $M (before r_hc)."""
        return self.risk_weight * self.maturity * self.notional * self.discount_factor


class BACVAHedgeResult(BaseModel):
    """Per-hedge decomposition for audit (ERBA NPR §__.222(c))."""
    hedge_id: str
    hedge_type: CVAHedgeType
    counterparty_id: str = ""
    risk_weight: float
    maturity: float
    notional: float
    discount_factor: float
    correlation: float = Field(description="r_hc (1.0 for index hedges)")
    weighted_amount: float = Field(description="RW·M·B·DF in $M")
    snh_contribution: float = Field(default=0.0, description="r_hc·RW·M·B·DF in $M")
    hma_contribution: float = Field(default=0.0, description="(1−r_hc²)·(RW·M·B·DF)² in $M²")
    ih_contribution: float = Field(default=0.0, description="RW_i·M_i·B_i·DF_i in $M")


class BACVACounterpartyResult(BaseModel):
    """Per-counterparty decomposition of SCVA_c per ERBA NPR §__.222(b)."""
    counterparty_id: str
    sector: CVASector
    credit_quality: CVACreditQuality
    ead: float = Field(description="Σ_NS EAD_NS in $M")
    effective_maturity: float = Field(description="EAD-weighted M_NS (reporting only)")
    risk_weight: float = Field(description="RW_c from Table 1 to §__.222")
    alpha: float = Field(description="α divisor (1.4 or 1.0)")
    maturity_weighted_ead: float = Field(description="Σ_NS M_NS·EAD_NS·DF_NS in $M")
    scva: float = Field(description="SCVA_c in $M")
    snh: float = Field(default=0.0, description="SNH_c in $M")
    hma: float = Field(default=0.0, description="HMA_c in $M²")

    @property
    def net_scva(self) -> float:
        """SCVA_c − SNH_c in $M (may be negative when over-hedged)."""
        return self.scva - self.snh


class BACVAResult(BaseModel):
    """BA-CVA capital requirement per ERBA NPR §__.222(a)."""
    approach: CVAApproach = Field(
        description="BA_CVA_REDUCED (no hedges) or BA_CVA_FULL (hedges recognized)"
    )
    k_unhedged: float = Field(description="K_unhedged in $M")
    k_hedged: float = Field(description="K_hedged in $M (= K_unhedged without hedges)")
    k_basic: float = Field(description="K_basic = 0.65·(β·K_unhedged + (1−β)·K_hedged) in $M")
    rwa: float = Field(description="RWA_CVA = 12.5 · K_basic in $M")
    total_scva: float = Field(default=0.0, description="Σ_c SCVA_c in $M")
    index_hedge_amount: float = Field(default=0.0, description="IH in $M")
    systematic_component: float = Field(
        default=0.0, description="(ρ·Σ(SCVA_c − SNH_c) − IH)² in $M² (hedged form)"
    )
    idiosyncratic_component: float = Field(
        default=0.0, description="(1 − ρ²)·Σ(SCVA_c − SNH_c)² in $M² (hedged form)"
    )
    hedge_mismatch_component: float = Field(default=0.0, description="Σ_c HMA_c in $M²")
    counterparty_results: list[BACVACounterpartyResult] = Field(default_factory=list)
    hedge_results: list[BACVAHedgeResult] = Field(default_factory=list)
    hedge_count: int = Field(default=0)
    total_hedge_notional: float = Field(default=0.0, description="Σ B_h in $M")

    @property
    def k_ba_cva(self) -> float:
        """Alias of ``k_basic`` (BA-CVA capital requirement in $M)."""
        return self.k_basic


# =========================================================================
#  Component calculations
# =========================================================================

def compute_scva(counterparty: BACVACounterparty) -> BACVACounterpartyResult:
    """Standalone CVA capital SCVA_c per ERBA NPR §__.222(b).

    SCVA_c = (1/α) · RW_c · Σ_NS ( M_NS · EAD_NS · DF_NS ).

    Args:
        counterparty: Counterparty with its netting sets.

    Returns:
        Per-counterparty result holding SCVA_c and its components.
    """
    weighted = sum(
        ns.maturity * ns.ead * ns.discount_factor for ns in counterparty.netting_sets
    )
    rw = counterparty.risk_weight
    alpha = counterparty.alpha
    scva = (1.0 / alpha) * rw * weighted
    assert counterparty.ead is not None and counterparty.effective_maturity is not None
    return BACVACounterpartyResult(
        counterparty_id=counterparty.counterparty_id,
        sector=counterparty.sector,
        credit_quality=counterparty.quality,
        ead=counterparty.ead,
        effective_maturity=counterparty.effective_maturity,
        risk_weight=rw,
        alpha=alpha,
        maturity_weighted_ead=weighted,
        scva=scva,
    )


def compute_k_unhedged(scva_values: list[float], rho: float = BA_CVA_RHO) -> float:
    """K_unhedged per ERBA NPR §__.222(b).

    K_unhedged = sqrt( (ρ · Σ_c SCVA_c)² + (1 − ρ²) · Σ_c SCVA_c² ).

    Args:
        scva_values: SCVA_c for every counterparty, $M.
        rho: Supervisory correlation (0.50).

    Returns:
        K_unhedged in $M.
    """
    total = sum(scva_values)
    sum_sq = sum(s * s for s in scva_values)
    return math.sqrt((rho * total) ** 2 + (1.0 - rho ** 2) * sum_sq)


def compute_k_hedged(
    net_scva_values: list[float],
    hma_values: list[float],
    index_hedge_amount: float,
    rho: float = BA_CVA_RHO,
) -> tuple[float, float, float, float]:
    """K_hedged per ERBA NPR §__.222(c).

    K_hedged = sqrt( (ρ · Σ_c (SCVA_c − SNH_c) − IH)²
                     + (1 − ρ²) · Σ_c (SCVA_c − SNH_c)²
                     + Σ_c HMA_c ).

    Args:
        net_scva_values: SCVA_c − SNH_c per counterparty, $M (no floor).
        hma_values: HMA_c per counterparty, $M².
        index_hedge_amount: IH in $M.
        rho: Supervisory correlation (0.50).

    Returns:
        (K_hedged, systematic term, idiosyncratic term, Σ HMA_c).
    """
    total_net = sum(net_scva_values)
    systematic = (rho * total_net - index_hedge_amount) ** 2
    idiosyncratic = (1.0 - rho ** 2) * sum(v * v for v in net_scva_values)
    hma_total = sum(hma_values)
    return math.sqrt(systematic + idiosyncratic + hma_total), systematic, idiosyncratic, hma_total


def compute_k_basic(
    k_unhedged: float,
    k_hedged: float,
    beta: float = BA_CVA_BETA,
    scalar: float = BA_CVA_DISCOUNT_SCALAR,
) -> float:
    """K_basic per ERBA NPR §__.222(a).

    K_basic = 0.65 · ( β · K_unhedged + (1 − β) · K_hedged ), β = 0.25.

    Args:
        k_unhedged: K_unhedged in $M.
        k_hedged: K_hedged in $M.
        beta: β (0.25).
        scalar: Calibration factor (0.65).

    Returns:
        K_basic in $M.
    """
    return scalar * (beta * k_unhedged + (1.0 - beta) * k_hedged)


# =========================================================================
#  Calculator
# =========================================================================

class BACVACalculator:
    """BA-CVA calculator per ERBA NPR §__.222.

    Usage::

        calc = BACVACalculator()
        result = calc.calculate(counterparties, hedges)
        print(result.k_basic, result.rwa)
    """

    def calculate(
        self,
        counterparties: list[BACVACounterparty],
        hedges: list[BACVAHedge] | None = None,
    ) -> BACVAResult:
        """Compute K_basic and RWA per ERBA NPR §__.222(a)–(c).

        Without eligible hedges K_hedged = K_unhedged (reduced BA-CVA). With
        hedges, single-name hedges reduce SCVA_c through SNH_c and add
        HMA_c, and index hedges reduce the systematic term through IH.

        Args:
            counterparties: Counterparties with netting sets.
            hedges: Eligible CVA hedges (single-name, contingent, index CDS).

        Returns:
            BACVAResult with K_unhedged, K_hedged, K_basic and RWA.

        Raises:
            ValueError: If a single-name hedge is assigned to an unknown
                counterparty.
        """
        hedges = hedges or []
        if not counterparties:
            return BACVAResult(
                approach=CVAApproach.BA_CVA_FULL if hedges else CVAApproach.BA_CVA_REDUCED,
                k_unhedged=0.0, k_hedged=0.0, k_basic=0.0, rwa=0.0,
                hedge_count=len(hedges),
                total_hedge_notional=sum(h.notional for h in hedges),
            )

        cp_results = [compute_scva(cp) for cp in counterparties]
        by_id = {r.counterparty_id: r for r in cp_results}
        k_unhedged = compute_k_unhedged([r.scva for r in cp_results])
        total_scva = sum(r.scva for r in cp_results)

        if not hedges:
            k_basic = compute_k_basic(k_unhedged, k_unhedged)
            return BACVAResult(
                approach=CVAApproach.BA_CVA_REDUCED,
                k_unhedged=k_unhedged,
                k_hedged=k_unhedged,
                k_basic=k_basic,
                rwa=k_basic * RWA_MULTIPLIER,
                total_scva=total_scva,
                systematic_component=(BA_CVA_RHO * total_scva) ** 2,
                idiosyncratic_component=(1.0 - BA_CVA_RHO ** 2) * sum(r.scva ** 2 for r in cp_results),
                counterparty_results=cp_results,
            )

        hedge_results: list[BACVAHedgeResult] = []
        index_hedge_amount = 0.0
        for h in hedges:
            amount = h.weighted_amount
            hr = BACVAHedgeResult(
                hedge_id=h.hedge_id,
                hedge_type=h.hedge_type,
                counterparty_id=h.counterparty_id,
                risk_weight=h.risk_weight,
                maturity=h.maturity,
                notional=h.notional,
                discount_factor=h.discount_factor,
                correlation=1.0 if h.is_index else h.correlation,
                weighted_amount=amount,
            )
            if h.is_index:
                hr.ih_contribution = amount
                index_hedge_amount += amount
            else:
                if h.counterparty_id not in by_id:
                    raise ValueError(
                        f"Hedge {h.hedge_id!r} references unknown counterparty "
                        f"{h.counterparty_id!r}"
                    )
                r_hc = h.correlation
                hr.snh_contribution = r_hc * amount
                hr.hma_contribution = (1.0 - r_hc ** 2) * amount ** 2
                cp = by_id[h.counterparty_id]
                cp.snh += hr.snh_contribution
                cp.hma += hr.hma_contribution
            hedge_results.append(hr)

        k_hedged, systematic, idiosyncratic, hma_total = compute_k_hedged(
            [r.net_scva for r in cp_results],
            [r.hma for r in cp_results],
            index_hedge_amount,
        )
        k_basic = compute_k_basic(k_unhedged, k_hedged)

        return BACVAResult(
            approach=CVAApproach.BA_CVA_FULL,
            k_unhedged=k_unhedged,
            k_hedged=k_hedged,
            k_basic=k_basic,
            rwa=k_basic * RWA_MULTIPLIER,
            total_scva=total_scva,
            index_hedge_amount=index_hedge_amount,
            systematic_component=systematic,
            idiosyncratic_component=idiosyncratic,
            hedge_mismatch_component=hma_total,
            counterparty_results=cp_results,
            hedge_results=hedge_results,
            hedge_count=len(hedges),
            total_hedge_notional=sum(h.notional for h in hedges),
        )

    def calculate_reduced(self, counterparties: list[BACVACounterparty]) -> BACVAResult:
        """Reduced BA-CVA (no hedges): K_basic = 0.65 · K_unhedged (preamble p. 457)."""
        return self.calculate(counterparties, None)

    def calculate_full(
        self,
        counterparties: list[BACVACounterparty],
        hedges: list[BACVAHedge],
    ) -> BACVAResult:
        """Full BA-CVA recognizing eligible hedges per ERBA NPR §__.222(c)."""
        return self.calculate(counterparties, hedges)


def compute_ba_cva_rwa(
    counterparties: list[BACVACounterparty],
    hedges: list[BACVAHedge] | None = None,
) -> float:
    """Convenience: RWA_CVA = 12.5 · K_basic per ERBA NPR §__.221/§__.222.

    Args:
        counterparties: Counterparties.
        hedges: Optional eligible hedges.

    Returns:
        CVA RWA in $M.
    """
    return BACVACalculator().calculate(counterparties, hedges).rwa


def compute_scva_summary(counterparties: list[BACVACounterparty]) -> dict[str, float]:
    """SCVA_c by counterparty per ERBA NPR §__.222(b).

    Args:
        counterparties: Counterparties.

    Returns:
        Mapping counterparty_id → SCVA_c in $M.
    """
    return {cp.counterparty_id: compute_scva(cp).scva for cp in counterparties}
