"""Standardized approach for CVA risk (SA-CVA) — ERBA NPR §__.224–§__.225.

Implements the SA-CVA aggregation of the March 2026 US re-proposal. The
SA-CVA is a sensitivities-based method: the banking organization supplies
sensitivities of aggregate regulatory CVA (s^CVA) and of the market value
of eligible CVA hedges (s^Hdg) to each risk factor; this module applies the
regulatory risk weights and correlations of §__.225 and aggregates.

Risk classes (§__.224(b)): delta for interest rate, FX, counterparty
credit spread, reference credit spread, equity and commodity; vega for
the five exposure-related classes (no counterparty credit spread vega).

Formulas (§__.225(a)):

    WS_k  = RW_k · s_k^CVA − RW_k · s_k^Hdg          (net weighted sensitivity)
    WS_k^Hdg = RW_k · s_k^Hdg
    K_b   = sqrt( Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l + R · Σ_k (WS_k^Hdg)² ),  R = 0.01
    S_b   = max( min( Σ_k WS_k , K_b ), −K_b )         (always applied)
    K     = m_CVA · sqrt( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c ),  m_CVA = 1 (default)
    K_SA-CVA = Σ_{risk classes} ( K_delta + K_vega )   (simple sum, no diversification)
    RWA_CVA  = 12.5 · K_SA-CVA

Sensitivity conventions (§__.224(e)): interest rate and credit spread
delta per 0.0001 absolute shift divided by 0.0001; FX, equity and
commodity delta per 1% relative shift divided by 0.01; vega per 1%
relative shift of volatilities divided by 0.01. Regulatory CVA must be
computed with the inputs of §__.224(d), including a margin period of risk
of at least 9 + N business days.

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Hashable

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from src.cva_risk.cva_params import (
    RWA_MULTIPLIER,
    SA_CVA_CCS_INDEX_BUCKET,
    SA_CVA_CCS_RHO_INDEX_DIFF,
    SA_CVA_CCS_RHO_INDEX_SAME_INDEX,
    SA_CVA_CCS_RHO_INDEX_SAME_SERIES,
    SA_CVA_CCS_RHO_NAME_AFFILIATE,
    SA_CVA_CCS_RHO_NAME_DIFF,
    SA_CVA_CCS_RHO_NAME_SAME,
    SA_CVA_CCS_RHO_QUALITY_DIFF,
    SA_CVA_CCS_RHO_QUALITY_SAME,
    SA_CVA_CCS_RHO_TENOR_DIFF,
    SA_CVA_CCS_RHO_TENOR_SAME,
    SA_CVA_CCS_TENORS,
    SA_CVA_COMMODITY_DELTA_RW,
    SA_CVA_COMMODITY_VEGA_RW,
    SA_CVA_EQUITY_DELTA_RW,
    SA_CVA_FX_DELTA_RW,
    SA_CVA_FX_GAMMA,
    SA_CVA_FX_VEGA_RW,
    SA_CVA_HEDGING_DISALLOWANCE_R,
    SA_CVA_IR_GAMMA,
    SA_CVA_IR_INFLATION_KEY,
    SA_CVA_IR_PARALLEL_KEY,
    SA_CVA_IR_SPECIFIED_CURRENCIES,
    SA_CVA_IR_TENORS,
    SA_CVA_IR_VEGA_INFLATION_KEY,
    SA_CVA_IR_VEGA_RATE_KEY,
    SA_CVA_IR_VEGA_RHO,
    SA_CVA_IR_VEGA_RW,
    SA_CVA_MULTIPLIER_DEFAULT,
    SA_CVA_RCS_RISK_WEIGHTS,
    SA_CVA_RCS_VEGA_RW,
    SA_CVA_VEGA_RISK_CLASSES,
    CVACreditQuality,
    CVASector,
    SACVARiskFactorType,
    ccs_gamma,
    ccs_quality_category,
    commodity_gamma,
    credit_quality_from_grade,
    equity_gamma,
    equity_vega_risk_weight,
    get_ccs_bucket,
    get_ccs_risk_weight,
    ir_delta_correlation,
    ir_delta_risk_weight,
    normalize_sector,
    rcs_gamma,
)

# =========================================================================
#  Input model
# =========================================================================

class SACVASensitivity(BaseModel):
    """One SA-CVA sensitivity record per ERBA NPR §__.224(e) / §__.225(b).

    ``cva_sensitivity`` is the sensitivity of aggregate regulatory CVA to
    the risk factor (s_k^CVA) and ``hedge_sensitivity`` the sensitivity of
    the market value of all eligible CVA hedges (s_k^Hdg), both in $M per
    unit shift using the §__.224(e) conventions. Records sharing the same
    risk factor are summed before weighting.

    Risk factor identification by risk class:
        - Interest rate delta: ``currency`` plus ``tenor`` (1, 2, 5, 10, 30
          for specified currencies) or ``is_inflation``; for non-specified
          currencies any tenor sensitivity is pooled into the single
          parallel-shift factor.
        - Interest rate vega: ``currency`` plus ``is_inflation`` (inflation
          volatility) or not (rate volatility).
        - FX delta/vega: ``currency`` (the non-reporting currency).
        - Counterparty credit spread delta: ``entity_id``, ``tenor`` (0.5, 1,
          3, 5, 10), ``credit_quality``, and ``sector`` /
          ``government_backed_financial`` / ``is_index`` (+ ``index_series``)
          to place the entity in a Table 3 bucket; ``affiliate_group`` marks
          legal entities under common control.
        - Reference credit spread delta/vega: ``bucket`` 1–17 (Table 5);
          ``credit_quality`` selects the bucket 8 weight.
        - Equity delta/vega: ``bucket`` 1–13 (Table 8).
        - Commodity delta/vega: ``bucket`` 1–12 (Table 9).
    """
    risk_class: SACVARiskFactorType
    is_vega: bool = False
    cva_sensitivity: float = Field(description="s_k^CVA in $M per unit shift")
    hedge_sensitivity: float = Field(default=0.0, description="s_k^Hdg in $M per unit shift")
    currency: str = Field(default="", description="Currency bucket (IR, FX)")
    bucket: int = Field(default=0, description="Bucket number (CCS, RCS, equity, commodity)")
    tenor: float | None = Field(default=None, description="Tenor in years (IR, CCS)")
    is_inflation: bool = Field(default=False, description="IR inflation (vol) factor")
    entity_id: str = Field(default="", description="Counterparty / reference name / index id (CCS)")
    affiliate_group: str = Field(default="", description="Common-control group id (CCS)")
    index_series: str = Field(default="", description="Index series (CCS bucket 8)")
    is_index: bool = Field(default=False, description="Credit index under optional treatment (CCS)")
    sector: CVASector | None = Field(default=None, description="Sector (CCS bucket assignment)")
    credit_quality: CVACreditQuality | None = Field(default=None)
    government_backed_financial: bool = Field(default=False, description="CCS bucket 1(c)")

    @field_validator("sector", mode="before")
    @classmethod
    def _coerce_sector(cls, v: object) -> CVASector | None:
        if v is None or isinstance(v, CVASector):
            return v
        return normalize_sector(str(v))

    @field_validator("credit_quality", mode="before")
    @classmethod
    def _coerce_quality(cls, v: object) -> CVACreditQuality | None:
        if v is None or isinstance(v, CVACreditQuality):
            return v
        return credit_quality_from_grade(str(v))

    @field_validator("currency")
    @classmethod
    def _upper_ccy(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def _validate_by_class(self) -> SACVASensitivity:
        rc = self.risk_class
        if self.is_vega and rc not in SA_CVA_VEGA_RISK_CLASSES:
            raise ValueError(
                "No vega capital requirement is computed for the counterparty "
                "credit spread risk class (ERBA NPR §__.224(b)(2))"
            )
        if rc in (SACVARiskFactorType.INTEREST_RATE, SACVARiskFactorType.FX):
            if not self.currency:
                raise ValueError(f"{rc.value} sensitivity requires a currency")
        if rc is SACVARiskFactorType.INTEREST_RATE and not self.is_vega:
            specified = self.currency in SA_CVA_IR_SPECIFIED_CURRENCIES
            if specified and not self.is_inflation:
                if self.tenor is None or float(self.tenor) not in SA_CVA_IR_TENORS:
                    raise ValueError(
                        f"IR delta tenor for specified currency must be one of "
                        f"{SA_CVA_IR_TENORS}, got {self.tenor}"
                    )
        if rc is SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD:
            if self.tenor is None or float(self.tenor) not in SA_CVA_CCS_TENORS:
                raise ValueError(
                    f"Counterparty credit spread tenor must be one of {SA_CVA_CCS_TENORS}"
                )
            if not self.entity_id:
                raise ValueError("Counterparty credit spread sensitivity requires entity_id")
            if self.credit_quality is None:
                raise ValueError("Counterparty credit spread sensitivity requires credit_quality")
            if self.bucket == 0:
                if not self.is_index and self.sector is None:
                    raise ValueError("Provide sector, is_index or an explicit bucket (Table 3)")
                self.bucket = get_ccs_bucket(
                    self.sector or CVASector.OTHER_SECTOR,
                    self.government_backed_financial,
                    self.is_index,
                )
            elif self.bucket == SA_CVA_CCS_INDEX_BUCKET:
                self.is_index = True
            if not 1 <= self.bucket <= 8:
                raise ValueError("Counterparty credit spread bucket must be 1–8")
        if rc is SACVARiskFactorType.REFERENCE_CREDIT_SPREAD:
            if not 1 <= self.bucket <= 17:
                raise ValueError("Reference credit spread bucket must be 1–17 (Table 5)")
            if self.bucket == 8 and self.credit_quality is None:
                raise ValueError(
                    "Reference credit spread bucket 8 requires credit_quality "
                    "(speculative 3.0% / sub-speculative 7.0%)"
                )
        if rc is SACVARiskFactorType.EQUITY and not 1 <= self.bucket <= 13:
            raise ValueError("Equity bucket must be 1–13 (Table 8)")
        if rc is SACVARiskFactorType.COMMODITY and not 1 <= self.bucket <= 12:
            raise ValueError("Commodity bucket must be 1–12 (Table 9)")
        return self

    # ---- derived classification ------------------------------------------

    @property
    def bucket_key(self) -> Hashable:
        """Bucket identifier: currency for IR/FX, bucket number otherwise."""
        if self.risk_class in (SACVARiskFactorType.INTEREST_RATE, SACVARiskFactorType.FX):
            return self.currency
        return self.bucket

    @property
    def factor_key(self) -> Hashable:
        """Risk factor identifier within the bucket (records sharing a key are summed)."""
        rc = self.risk_class
        if rc is SACVARiskFactorType.INTEREST_RATE:
            if self.is_vega:
                return SA_CVA_IR_VEGA_INFLATION_KEY if self.is_inflation else SA_CVA_IR_VEGA_RATE_KEY
            if self.is_inflation:
                return SA_CVA_IR_INFLATION_KEY
            if self.currency in SA_CVA_IR_SPECIFIED_CURRENCIES:
                return float(self.tenor)  # type: ignore[arg-type]
            return SA_CVA_IR_PARALLEL_KEY
        if rc is SACVARiskFactorType.FX:
            return self.currency
        if rc is SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD:
            return (self.entity_id, self.index_series, float(self.tenor))  # type: ignore[arg-type]
        # Reference credit spread, equity, commodity: one factor per bucket.
        return self.bucket

    @property
    def risk_weight(self) -> float:
        """RW_k per ERBA NPR §__.225 Tables 1, 3, 5, 8, 9 and §__.225(b)."""
        rc = self.risk_class
        if rc is SACVARiskFactorType.INTEREST_RATE:
            if self.is_vega:
                return SA_CVA_IR_VEGA_RW
            specified = self.currency in SA_CVA_IR_SPECIFIED_CURRENCIES
            return ir_delta_risk_weight(self.factor_key, specified)  # type: ignore[arg-type]
        if rc is SACVARiskFactorType.FX:
            return SA_CVA_FX_VEGA_RW if self.is_vega else SA_CVA_FX_DELTA_RW
        if rc is SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD:
            assert self.credit_quality is not None
            return get_ccs_risk_weight(
                self.sector or CVASector.OTHER_SECTOR,
                self.credit_quality,
                self.government_backed_financial,
                self.is_index,
            )
        if rc is SACVARiskFactorType.REFERENCE_CREDIT_SPREAD:
            if self.is_vega:
                return SA_CVA_RCS_VEGA_RW
            q = self.credit_quality or CVACreditQuality.INVESTMENT_GRADE
            return SA_CVA_RCS_RISK_WEIGHTS[self.bucket][q]
        if rc is SACVARiskFactorType.EQUITY:
            if self.is_vega:
                return equity_vega_risk_weight(self.bucket)
            return SA_CVA_EQUITY_DELTA_RW[self.bucket]
        if self.is_vega:
            return SA_CVA_COMMODITY_VEGA_RW
        return SA_CVA_COMMODITY_DELTA_RW[self.bucket]


# =========================================================================
#  Result models
# =========================================================================

class SACVAFactorResult(BaseModel):
    """Aggregated risk factor k within a bucket (ERBA NPR §__.225(a))."""
    factor: str
    cva_sensitivity: float = Field(description="Σ s_k^CVA in $M")
    hedge_sensitivity: float = Field(description="Σ s_k^Hdg in $M")
    weighted_sensitivity: float = Field(description="WS_k = RW·(s^CVA − s^Hdg) in $M")
    hedge_weighted_sensitivity: float = Field(description="WS_k^Hdg = RW·s^Hdg in $M")


class SACVABucketResult(BaseModel):
    """Intra-bucket aggregation result (ERBA NPR §__.225(a))."""
    bucket: str
    capital_charge: float = Field(description="K_b in $M")
    sum_weighted_sensitivity: float = Field(description="Σ_k WS_k in $M")
    s_b: float = Field(description="max(min(ΣWS_k, K_b), −K_b) in $M")
    hedge_disallowance_term: float = Field(description="R·Σ_k (WS_k^Hdg)² in $M²")
    factors: list[SACVAFactorResult] = Field(default_factory=list)


class SACVARiskClassResult(BaseModel):
    """Risk-class level result for delta or vega (ERBA NPR §__.225(a))."""
    risk_class: SACVARiskFactorType
    is_vega: bool
    capital_charge: float = Field(description="K = m_CVA·sqrt(ΣK_b² + ΣΣγ S_b S_c) in $M")
    capital_charge_unscaled: float = Field(description="K before m_CVA in $M")
    bucket_results: list[SACVABucketResult] = Field(default_factory=list)


class SACVAResult(BaseModel):
    """SA-CVA capital requirement per ERBA NPR §__.224–§__.225."""
    approach: str = Field(default="SA-CVA")
    k_cva: float = Field(description="Σ risk classes (K_delta + K_vega) in $M")
    rwa: float = Field(description="12.5 · K_SA-CVA in $M")
    m_cva: float = Field(default=SA_CVA_MULTIPLIER_DEFAULT)
    delta_charge: float = Field(default=0.0, description="Σ delta K across risk classes in $M")
    vega_charge: float = Field(default=0.0, description="Σ vega K across risk classes in $M")
    risk_class_results: list[SACVARiskClassResult] = Field(default_factory=list)

    @property
    def k_by_risk_class(self) -> dict[str, float]:
        """K per (risk class, delta|vega) label, $M."""
        return {
            f"{r.risk_class.value}:{'VEGA' if r.is_vega else 'DELTA'}": r.capital_charge
            for r in self.risk_class_results
        }


# =========================================================================
#  Correlation helpers
# =========================================================================

class _Factor:
    """Internal accumulator for one risk factor within a bucket."""

    __slots__ = ("key", "cva", "hdg", "ws", "ws_hdg", "meta")

    def __init__(self, key: Hashable, meta: SACVASensitivity) -> None:
        self.key = key
        self.cva = 0.0
        self.hdg = 0.0
        self.ws = 0.0
        self.ws_hdg = 0.0
        self.meta = meta


def _ccs_rho(a: SACVASensitivity, b: SACVASensitivity) -> float:
    """Intra-bucket counterparty credit spread correlation per ERBA NPR §__.225(b)(3).

    ρ_kl = ρ_tenor × ρ_name × ρ_quality with ρ_tenor 100%/90%, ρ_name
    100% (same entity) / 90% (affiliates) / 50%, ρ_quality 100% (same
    category; speculative and sub-speculative are one category) / 80%. In
    the index bucket ρ_name is 100% (same index and series) / 90% (same
    index, different series) / 80%.
    """
    rho_tenor = SA_CVA_CCS_RHO_TENOR_SAME if a.tenor == b.tenor else SA_CVA_CCS_RHO_TENOR_DIFF
    if a.bucket == SA_CVA_CCS_INDEX_BUCKET:
        if a.entity_id == b.entity_id and a.index_series == b.index_series:
            rho_name = SA_CVA_CCS_RHO_INDEX_SAME_SERIES
        elif a.entity_id == b.entity_id:
            rho_name = SA_CVA_CCS_RHO_INDEX_SAME_INDEX
        else:
            rho_name = SA_CVA_CCS_RHO_INDEX_DIFF
    else:
        if a.entity_id == b.entity_id:
            rho_name = SA_CVA_CCS_RHO_NAME_SAME
        elif a.affiliate_group and a.affiliate_group == b.affiliate_group:
            rho_name = SA_CVA_CCS_RHO_NAME_AFFILIATE
        else:
            rho_name = SA_CVA_CCS_RHO_NAME_DIFF
    assert a.credit_quality is not None and b.credit_quality is not None
    same_q = ccs_quality_category(a.credit_quality) == ccs_quality_category(b.credit_quality)
    rho_quality = SA_CVA_CCS_RHO_QUALITY_SAME if same_q else SA_CVA_CCS_RHO_QUALITY_DIFF
    return rho_tenor * rho_name * rho_quality


def intra_bucket_correlation(
    risk_class: SACVARiskFactorType,
    is_vega: bool,
    f_k: _Factor,
    f_l: _Factor,
) -> float:
    """ρ_kl between two risk factors of the same bucket per ERBA NPR §__.225(b).

    Interest rate delta: Table 2 (specified currencies) or 40% (parallel vs
    inflation, other currencies); interest rate vega: 40% between rate and
    inflation volatility; counterparty credit spread: product of tenor,
    name and quality factors. FX, reference credit spread, equity and
    commodity buckets contain a single risk factor.
    """
    if f_k.key == f_l.key:
        return 1.0
    if risk_class is SACVARiskFactorType.INTEREST_RATE:
        if is_vega:
            return SA_CVA_IR_VEGA_RHO
        specified = f_k.meta.currency in SA_CVA_IR_SPECIFIED_CURRENCIES
        return ir_delta_correlation(f_k.key, f_l.key, specified)  # type: ignore[arg-type]
    if risk_class is SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD:
        return _ccs_rho(f_k.meta, f_l.meta)
    # Single-factor buckets never reach here with distinct keys.
    return 1.0


def cross_bucket_correlation(
    risk_class: SACVARiskFactorType,
    bucket_b: Hashable,
    bucket_c: Hashable,
) -> float:
    """γ_bc per ERBA NPR §__.225(b): IR 50%, FX 60%, CCS Table 4, RCS Tables
    6–7, equity and commodity per §__.225(b)(5)–(6). Identical for delta and
    vega within a risk class."""
    if bucket_b == bucket_c:
        return 1.0
    if risk_class is SACVARiskFactorType.INTEREST_RATE:
        return SA_CVA_IR_GAMMA
    if risk_class is SACVARiskFactorType.FX:
        return SA_CVA_FX_GAMMA
    b, c = int(str(bucket_b)), int(str(bucket_c))
    if risk_class is SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD:
        return ccs_gamma(b, c)
    if risk_class is SACVARiskFactorType.REFERENCE_CREDIT_SPREAD:
        return rcs_gamma(b, c)
    if risk_class is SACVARiskFactorType.EQUITY:
        return equity_gamma(b, c)
    return commodity_gamma(b, c)


# =========================================================================
#  Aggregation
# =========================================================================

def aggregate_bucket(
    risk_class: SACVARiskFactorType,
    is_vega: bool,
    factors: list[_Factor],
    hedging_disallowance: float = SA_CVA_HEDGING_DISALLOWANCE_R,
) -> tuple[float, float, float]:
    """Intra-bucket aggregation per ERBA NPR §__.225(a).

    K_b = sqrt( Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l + R · Σ_k (WS_k^Hdg)² ).

    Args:
        risk_class: Risk class of the bucket.
        is_vega: True for vega factors.
        factors: Aggregated risk factors of the bucket.
        hedging_disallowance: R (0.01).

    Returns:
        (K_b, Σ_k WS_k, R·Σ_k (WS_k^Hdg)²).
    """
    n = len(factors)
    ws = np.array([f.ws for f in factors], dtype=np.float64)
    ws_hdg = np.array([f.ws_hdg for f in factors], dtype=np.float64)
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            rho = intra_bucket_correlation(risk_class, is_vega, factors[i], factors[j])
            corr[i, j] = rho
            corr[j, i] = rho
    quad = float(ws @ corr @ ws)
    hedge_term = hedging_disallowance * float(np.sum(ws_hdg ** 2))
    k_b = math.sqrt(max(quad + hedge_term, 0.0))
    return k_b, float(np.sum(ws)), hedge_term


def aggregate_risk_class(
    risk_class: SACVARiskFactorType,
    bucket_charges: OrderedDict[Hashable, float],
    bucket_sums: OrderedDict[Hashable, float],
    m_cva: float = SA_CVA_MULTIPLIER_DEFAULT,
) -> tuple[float, float, dict[Hashable, float]]:
    """Inter-bucket aggregation per ERBA NPR §__.225(a).

    K = m_CVA · sqrt( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c ) with
    S_b = max(min(Σ_k WS_k, K_b), −K_b) applied unconditionally
    (preamble fn. 510).

    Args:
        risk_class: Risk class.
        bucket_charges: K_b by bucket.
        bucket_sums: Σ_k WS_k by bucket.
        m_cva: Multiplier m_CVA.

    Returns:
        (K scaled by m_CVA, K unscaled, S_b by bucket).
    """
    buckets = list(bucket_charges.keys())
    s_b: dict[Hashable, float] = {
        b: max(min(bucket_sums[b], bucket_charges[b]), -bucket_charges[b]) for b in buckets
    }
    total = sum(k * k for k in bucket_charges.values())
    for i, b in enumerate(buckets):
        for c in buckets[i + 1:]:
            total += 2.0 * cross_bucket_correlation(risk_class, b, c) * s_b[b] * s_b[c]
    k_unscaled = math.sqrt(max(total, 0.0))
    return m_cva * k_unscaled, k_unscaled, s_b


# =========================================================================
#  Calculator
# =========================================================================

class SACVACalculator:
    """SA-CVA calculator per ERBA NPR §__.224–§__.225.

    Usage::

        calc = SACVACalculator()
        result = calc.calculate(sensitivities)        # m_CVA = 1
        result = calc.calculate(sensitivities, m_cva=1.5)

    Args:
        m_cva: Default multiplier m_CVA (1.0 unless the primary Federal
            supervisor requires a higher value in writing, §__.225(a)).
    """

    def __init__(self, m_cva: float = SA_CVA_MULTIPLIER_DEFAULT) -> None:
        if m_cva < SA_CVA_MULTIPLIER_DEFAULT:
            raise ValueError("m_CVA may not be below its default value of 1.0 (§__.225(a))")
        self.m_cva = m_cva

    def calculate(
        self,
        sensitivities: list[SACVASensitivity],
        m_cva: float | None = None,
    ) -> SACVAResult:
        """Compute K_SA-CVA and RWA per ERBA NPR §__.224(b) / §__.225(a).

        For each risk class the delta and (where applicable) vega capital
        requirements are computed separately and summed across risk
        classes with no diversification benefit.

        Args:
            sensitivities: Regulatory CVA and hedge sensitivities.
            m_cva: Override of the multiplier for this calculation.

        Returns:
            SACVAResult with the total, delta/vega split and per-class detail.
        """
        mult = self.m_cva if m_cva is None else m_cva
        if mult < SA_CVA_MULTIPLIER_DEFAULT:
            raise ValueError("m_CVA may not be below its default value of 1.0 (§__.225(a))")

        groups: OrderedDict[tuple[SACVARiskFactorType, bool], list[SACVASensitivity]] = OrderedDict()
        for s in sensitivities:
            groups.setdefault((s.risk_class, s.is_vega), []).append(s)

        class_results: list[SACVARiskClassResult] = []
        delta_total = 0.0
        vega_total = 0.0
        for rc in SACVARiskFactorType:
            for is_vega in (False, True):
                recs = groups.get((rc, is_vega))
                if not recs:
                    continue
                res = self.calculate_risk_class(recs, rc, is_vega, mult)
                class_results.append(res)
                if is_vega:
                    vega_total += res.capital_charge
                else:
                    delta_total += res.capital_charge

        k_total = delta_total + vega_total
        return SACVAResult(
            k_cva=k_total,
            rwa=k_total * RWA_MULTIPLIER,
            m_cva=mult,
            delta_charge=delta_total,
            vega_charge=vega_total,
            risk_class_results=class_results,
        )

    def calculate_risk_class(
        self,
        sensitivities: list[SACVASensitivity],
        risk_class: SACVARiskFactorType,
        is_vega: bool,
        m_cva: float = SA_CVA_MULTIPLIER_DEFAULT,
    ) -> SACVARiskClassResult:
        """Delta or vega capital requirement for one risk class (§__.225(a)).

        Args:
            sensitivities: Records of this risk class and delta/vega type.
            risk_class: Risk class.
            is_vega: True for vega.
            m_cva: Multiplier m_CVA.

        Returns:
            SACVARiskClassResult with bucket detail.
        """
        buckets: OrderedDict[Hashable, OrderedDict[Hashable, _Factor]] = OrderedDict()
        for s in sensitivities:
            if s.risk_class is not risk_class or s.is_vega != is_vega:
                raise ValueError("Sensitivity does not belong to this risk class / type")
            factors = buckets.setdefault(s.bucket_key, OrderedDict())
            f = factors.get(s.factor_key)
            if f is None:
                f = _Factor(s.factor_key, s)
                factors[s.factor_key] = f
            rw = s.risk_weight
            f.cva += s.cva_sensitivity
            f.hdg += s.hedge_sensitivity
            f.ws += rw * s.cva_sensitivity - rw * s.hedge_sensitivity
            f.ws_hdg += rw * s.hedge_sensitivity

        bucket_charges: OrderedDict[Hashable, float] = OrderedDict()
        bucket_sums: OrderedDict[Hashable, float] = OrderedDict()
        bucket_detail: dict[Hashable, tuple[float, list[SACVAFactorResult]]] = {}
        for b, factors in buckets.items():
            flist = list(factors.values())
            k_b, sum_ws, hedge_term = aggregate_bucket(risk_class, is_vega, flist)
            bucket_charges[b] = k_b
            bucket_sums[b] = sum_ws
            bucket_detail[b] = (hedge_term, [
                SACVAFactorResult(
                    factor=str(f.key),
                    cva_sensitivity=f.cva,
                    hedge_sensitivity=f.hdg,
                    weighted_sensitivity=f.ws,
                    hedge_weighted_sensitivity=f.ws_hdg,
                ) for f in flist
            ])

        k_scaled, k_unscaled, s_b = aggregate_risk_class(
            risk_class, bucket_charges, bucket_sums, m_cva,
        )
        return SACVARiskClassResult(
            risk_class=risk_class,
            is_vega=is_vega,
            capital_charge=k_scaled,
            capital_charge_unscaled=k_unscaled,
            bucket_results=[
                SACVABucketResult(
                    bucket=str(b),
                    capital_charge=bucket_charges[b],
                    sum_weighted_sensitivity=bucket_sums[b],
                    s_b=s_b[b],
                    hedge_disallowance_term=bucket_detail[b][0],
                    factors=bucket_detail[b][1],
                ) for b in bucket_charges
            ],
        )
