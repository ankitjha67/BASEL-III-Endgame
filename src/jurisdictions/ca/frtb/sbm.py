"""OSFI CAR 2026 Chapter 9 -- Sensitivities-based method (SBM).

Implements CAR 9.5.2.3 ¶115-119 [MAR21.4-21.7]:

* delta / vega: WS_k = RW_k · s_k; within bucket K_b = sqrt(max(0, Σ WS_k² + ΣΣ_{k≠l} ρ_kl WS_k
  WS_l)); across buckets Δ = sqrt(Σ K_b² + ΣΣ_{c≠b} γ_bc S_b S_c) with S_b = Σ WS_k, and the
  alternative S_b = max[min(Σ WS_k, K_b), −K_b] when the sum under the root is negative (¶116);
* curvature (¶117): K_b± = sqrt(max(0, Σ max(CVR_k±, 0)² + ΣΣ_{k≠l} ρ_kl CVR_k± CVR_l±
  ψ(CVR_k±, CVR_l±))), K_b = max(K_b+, K_b−) with the tie rule, S_b = Σ CVR of the selected
  scenario, total = sqrt(max(0, Σ K_b² + ΣΣ γ_bc S_b S_c ψ(S_b, S_c)));
* "other" buckets (CSR 16, securitisation non-CTP 25, equity 11): K_b = Σ|WS_k| and, for
  curvature, max(Σ max(CVR+, 0), Σ max(CVR−, 0)) (¶168, ¶181, ¶191);
* three correlation scenarios (¶118): medium = as specified, high = min(1.25ρ, 100%), low =
  max(2ρ − 100%, 75%ρ), applied to ρ_kl and γ_bc (curvature: to the squared values, ¶212-213);
  per scenario the delta, vega and curvature requirements of all risk classes are summed and the
  largest scenario total is the SBM requirement (¶119 [MAR21.7]).

Reporting currency defaults to CAD (CAR 9.5.2.4 ¶127 [MAR21.15]: "Sensitivities ... must be
expressed in the reporting currency of the institution").
"""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

from src.jurisdictions.ca.frtb import buckets as bk
from src.jurisdictions.ca.frtb import params as p
from src.jurisdictions.frtb_base import (
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
)

Key = tuple[Hashable, ...]
CorrFn = Callable[[str, Key, Key], float]
GammaFn = Callable[[str, str], float]

_CSR_CLASSES = (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP)


# =========================================================================
#  Correlation scenarios
# =========================================================================


def scenario_correlation(rho: float, scenario: str) -> float:
    """Apply a CAR ¶118 correlation scenario to a medium correlation [MAR21.6].

    HIGH: min(1.25·ρ, 100%); LOW: max(2·ρ − 100%, 75%·ρ); MEDIUM: ρ.
    """
    if scenario == "HIGH":
        return min(p.HIGH_CORRELATION_MULTIPLIER * rho, p.CORRELATION_CAP)
    if scenario == "LOW":
        return max(
            p.LOW_CORRELATION_SLOPE * rho - p.LOW_CORRELATION_INTERCEPT,
            p.LOW_CORRELATION_FLOOR_FACTOR * rho,
        )
    return rho


def _maturity_corr(t_k: float, t_l: float) -> float:
    """e^(−α·|Tk − Tl| / min{Tk; Tl}), α = 1% (CAR ¶205 [MAR21.93])."""
    lo = min(t_k, t_l)
    if lo <= 0.0:
        return 1.0 if t_k == t_l else 0.0
    return math.exp(-p.VEGA_ALPHA * abs(t_k - t_l) / lo)


# =========================================================================
#  Risk-factor keys (what nets with what)
# =========================================================================


@dataclass
class _Factor:
    """A netted risk factor within a bucket."""

    key: Key
    amount: float = 0.0  # net sensitivity s_k (delta/vega) -- WS computed with rw
    rw: float = 0.0
    cvr_up: float = 0.0
    cvr_down: float = 0.0

    @property
    def ws(self) -> float:
        return self.rw * self.amount


@dataclass
class _Bucket:
    bucket: str
    factors: dict[Key, _Factor] = field(default_factory=dict)


def _name_key(s: FRTBSensitivity) -> str:
    """Issuer / tranche / commodity / curve identity used by the ρ(name) tests."""
    if s.risk_class == FRTBRiskClass.CSR_SEC_NONCTP:
        return s.tranche_id or s.issuer or s.label
    if s.risk_class == FRTBRiskClass.COMMODITY:
        return s.commodity_name or s.label
    return s.issuer or s.label


def _delta_entries(s: FRTBSensitivity) -> list[tuple[Key, float, float | None]]:
    """(key, share of s_k, vertex) for a delta sensitivity, after linear vertex allocation."""
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        if s.girr_curve == GIRRCurve.INFLATION:
            return [(("INF", s.curve_name), 1.0, None)]
        if s.girr_curve == GIRRCurve.XCCY_BASIS:
            return [(("XCCY", s.curve_name), 1.0, None)]
        if s.tenor_years is None:
            raise ValueError("GIRR delta requires tenor_years (CAR ¶120(1))")
        return [
            (("RF", s.curve_name, t), w, t)
            for t, w in bk.allocate_to_vertices(s.tenor_years, p.GIRR_TENORS)
        ]
    if rc in (*_CSR_CLASSES, FRTBRiskClass.CSR_SEC_NONCTP):
        if s.tenor_years is None:
            raise ValueError("CSR delta requires tenor_years (CAR ¶121-123)")
        return [
            ((_name_key(s), s.is_cds, t), w, t)
            for t, w in bk.allocate_to_vertices(s.tenor_years, p.CSR_TENORS)
        ]
    if rc == FRTBRiskClass.EQUITY:
        return [((_name_key(s), s.equity_risk_factor.value), 1.0, None)]
    if rc == FRTBRiskClass.COMMODITY:
        tenor = 0.0 if s.tenor_years is None else s.tenor_years  # spot -> first tenor, ¶125
        return [
            ((_name_key(s), s.delivery_location, t), w, t)
            for t, w in bk.allocate_to_vertices(tenor, p.COMMODITY_TENORS)
        ]
    return [(("FX",), 1.0, None)]


def _vega_entries(s: FRTBSensitivity) -> list[tuple[Key, float]]:
    """(key, share) for a vega sensitivity; maturities allocated to 0.5/1/3/5/10 years.

    CAR ¶138(1),(4): options without a maturity go to the longest prescribed tenor (10 years);
    the underlying residual maturity defaults likewise.
    """
    longest = p.VEGA_TENORS[-1]
    t_opt = longest if s.option_maturity_years is None else s.option_maturity_years
    opt_alloc = bk.allocate_to_vertices(t_opt, p.VEGA_TENORS)
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        if s.girr_curve != GIRRCurve.RISK_FREE:
            # ¶120(1)(c)/(d): inflation and cross-currency basis vega along option maturity only.
            return [((s.girr_curve.value, s.curve_name, t, None), w) for t, w in opt_alloc]
        t_u = longest if s.underlying_maturity_years is None else s.underlying_maturity_years
        und_alloc = bk.allocate_to_vertices(t_u, p.VEGA_TENORS)
        return [
            ((GIRRCurve.RISK_FREE.value, s.curve_name, t, u), w * v)
            for t, w in opt_alloc for u, v in und_alloc
        ]
    return [((_name_key(s), t), w) for t, w in opt_alloc]


def _curvature_key(s: FRTBSensitivity) -> Key | None:
    """Curvature risk factor (CAR ¶120(3), ¶121(3), ¶122(4), ¶123(4), ¶124(3), ¶125(3), ¶126(3)).

    GIRR: one constructed risk-free curve per currency (none for inflation / cross-currency basis,
    ¶120(3)(b)); CSR: issuer curve (bond and CDS a single curve); securitisation: tranche;
    equity: spot price (none for repo, ¶124(3)(b)); commodity: constructed curve per commodity;
    FX: the exchange rate.
    """
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        return None if s.girr_curve != GIRRCurve.RISK_FREE else ("GIRR",)
    if rc == FRTBRiskClass.EQUITY and s.equity_risk_factor == EquityRiskFactor.REPO:
        return None
    if rc == FRTBRiskClass.FX:
        return ("FX",)
    return (_name_key(s),)


# =========================================================================
#  Medium (specified) correlations by risk class
# =========================================================================


def _girr_delta_rho(_b: str, k: Key, l: Key) -> float:  # noqa: E741
    """GIRR delta ρ_kl (CAR ¶157-161 [MAR21.45-21.49])."""
    tk, tl = k[0], l[0]
    if tk == "XCCY" or tl == "XCCY":
        return p.GIRR_XCCY_CORRELATION
    if tk == "INF" and tl == "INF":
        return 1.0 if k[1] == l[1] else p.GIRR_DIFFERENT_CURVE_CORRELATION
    if tk == "INF" or tl == "INF":
        return p.GIRR_INFLATION_YIELD_CORRELATION
    tenor_rho = p.GIRR_TENOR_CORRELATION[(float(k[2]), float(l[2]))]  # type: ignore[arg-type]
    if k[1] == l[1]:
        return tenor_rho
    return tenor_rho * p.GIRR_DIFFERENT_CURVE_CORRELATION


def _csr_delta_rho_factory(ctp: bool) -> CorrFn:
    def rho(b: str, k: Key, l: Key) -> float:  # noqa: E741
        """CSR ρ = ρ(name)·ρ(tenor)·ρ(basis) (CAR ¶166-167, ¶172 [MAR21.54-21.55, 21.60])."""
        index_bucket = (not ctp) and int(b) in p.CSR_INDEX_BUCKETS
        name_other = p.CSR_INDEX_NAME_CORRELATION if index_bucket else p.CSR_NAME_CORRELATION
        r_name = 1.0 if k[0] == l[0] else name_other
        r_tenor = 1.0 if k[2] == l[2] else p.CSR_TENOR_CORRELATION
        basis_other = p.CSR_CTP_BASIS_CORRELATION if ctp else p.CSR_BASIS_CORRELATION
        r_basis = 1.0 if k[1] == l[1] else basis_other
        return r_name * r_tenor * r_basis

    return rho


def _sec_delta_rho(_b: str, k: Key, l: Key) -> float:  # noqa: E741
    """Securitisation non-CTP ρ = ρ(tranche)·ρ(tenor)·ρ(basis) (CAR ¶180 [MAR21.68])."""
    r_tr = 1.0 if k[0] == l[0] else p.SEC_NONCTP_TRANCHE_CORRELATION
    r_tenor = 1.0 if k[2] == l[2] else p.SEC_NONCTP_TENOR_CORRELATION
    r_basis = 1.0 if k[1] == l[1] else p.SEC_NONCTP_BASIS_CORRELATION
    return r_tr * r_tenor * r_basis


def _equity_delta_rho(b: str, k: Key, l: Key) -> float:  # noqa: E741
    """Equity ρ_kl (CAR ¶190 [MAR21.78])."""
    same_name = k[0] == l[0]
    same_type = k[1] == l[1]
    if same_name:
        return 1.0 if same_type else p.EQUITY_SPOT_REPO_SAME_NAME_CORRELATION
    base = p.EQUITY_INTRA_BUCKET_CORRELATION[int(b)]
    return base if same_type else base * p.EQUITY_SPOT_REPO_SAME_NAME_CORRELATION


def _commodity_delta_rho(b: str, k: Key, l: Key) -> float:  # noqa: E741
    """Commodity ρ = ρ(cty)·ρ(tenor)·ρ(basis) (CAR ¶195 Table 12 [MAR21.83])."""
    r_cty = 1.0 if k[0] == l[0] else p.COMMODITY_CTY_CORRELATION[int(b)]
    r_tenor = 1.0 if k[2] == l[2] else p.COMMODITY_TENOR_CORRELATION
    r_basis = 1.0 if k[1] == l[1] else p.COMMODITY_BASIS_CORRELATION
    return r_cty * r_tenor * r_basis


def _fx_rho(_b: str, _k: Key, _l: Key) -> float:
    """FX: one risk factor per bucket (CAR ¶198 [MAR21.86])."""
    return 1.0


def delta_rho_fn(rc: FRTBRiskClass) -> CorrFn:
    """Medium delta ρ_kl function for a risk class."""
    return {
        FRTBRiskClass.GIRR: _girr_delta_rho,
        FRTBRiskClass.CSR_NONSEC: _csr_delta_rho_factory(ctp=False),
        FRTBRiskClass.CSR_SEC_CTP: _csr_delta_rho_factory(ctp=True),
        FRTBRiskClass.CSR_SEC_NONCTP: _sec_delta_rho,
        FRTBRiskClass.EQUITY: _equity_delta_rho,
        FRTBRiskClass.COMMODITY: _commodity_delta_rho,
        FRTBRiskClass.FX: _fx_rho,
    }[rc]


def vega_rho_fn(rc: FRTBRiskClass) -> CorrFn:
    """Medium vega ρ_kl (CAR ¶205-206 [MAR21.93-21.94]).

    GIRR: min[ρ(option maturity)·ρ(underlying maturity); 1]. Inflation / cross-currency basis vega
    against other GIRR vega factors use the delta correlation between the corresponding delta
    factors (40% / 0%) times ρ(option maturity) -- ¶205 does not address mixed curve types.
    Non-GIRR: min[ρ(DELTA)·ρ(option maturity); 1], where ρ(DELTA) uses only the dimensions shared
    by delta and vega factors (¶206): name (CSR, CTP), tranche (non-CTP), commodity (commodity),
    issuer (equity spot), none (FX).
    """
    if rc == FRTBRiskClass.GIRR:
        def girr(_b: str, k: Key, l: Key) -> float:  # noqa: E741
            r_opt = _maturity_corr(float(k[2]), float(l[2]))  # type: ignore[arg-type]
            if k[0] != l[0]:
                kinds = {k[0], l[0]}
                if GIRRCurve.XCCY_BASIS.value in kinds:
                    return p.GIRR_XCCY_CORRELATION
                return min(p.GIRR_INFLATION_YIELD_CORRELATION * r_opt, 1.0)
            if k[3] is None or l[3] is None:
                same_curve = k[1] == l[1]
                base = 1.0 if same_curve else p.GIRR_DIFFERENT_CURVE_CORRELATION
                return min(base * r_opt, 1.0)
            r_und = _maturity_corr(float(k[3]), float(l[3]))  # type: ignore[arg-type]
            return min(r_opt * r_und, 1.0)

        return girr

    def other(b: str, k: Key, l: Key) -> float:  # noqa: E741
        r_opt = _maturity_corr(float(k[1]), float(l[1]))  # type: ignore[arg-type]
        same = k[0] == l[0]
        if rc in _CSR_CLASSES:
            index_bucket = rc == FRTBRiskClass.CSR_NONSEC and int(b) in p.CSR_INDEX_BUCKETS
            other_name = p.CSR_INDEX_NAME_CORRELATION if index_bucket else p.CSR_NAME_CORRELATION
            r_delta = 1.0 if same else other_name
        elif rc == FRTBRiskClass.CSR_SEC_NONCTP:
            r_delta = 1.0 if same else p.SEC_NONCTP_TRANCHE_CORRELATION
        elif rc == FRTBRiskClass.COMMODITY:
            r_delta = 1.0 if same else p.COMMODITY_CTY_CORRELATION[int(b)]
        elif rc == FRTBRiskClass.EQUITY:
            r_delta = 1.0 if same else p.EQUITY_INTRA_BUCKET_CORRELATION[int(b)]
        else:
            r_delta = 1.0
        return min(r_delta * r_opt, 1.0)

    return other


def curvature_rho_fn(rc: FRTBRiskClass) -> CorrFn:
    """Medium curvature ρ_kl = (delta ρ_kl)² on the curvature dimensions (CAR ¶212 [MAR21.100]).

    CSR / CTP / securitisation: only the name (tranche) correlation, squared; commodity: ρ(cty)²;
    equity: spot-spot correlation²; GIRR and FX: a single factor per bucket.
    """
    def rho(b: str, k: Key, l: Key) -> float:  # noqa: E741
        if k == l:
            return 1.0
        if rc in _CSR_CLASSES:
            index_bucket = rc == FRTBRiskClass.CSR_NONSEC and int(b) in p.CSR_INDEX_BUCKETS
            base = p.CSR_INDEX_NAME_CORRELATION if index_bucket else p.CSR_NAME_CORRELATION
        elif rc == FRTBRiskClass.CSR_SEC_NONCTP:
            base = p.SEC_NONCTP_TRANCHE_CORRELATION
        elif rc == FRTBRiskClass.COMMODITY:
            base = p.COMMODITY_CTY_CORRELATION[int(b)]
        elif rc == FRTBRiskClass.EQUITY:
            base = p.EQUITY_INTRA_BUCKET_CORRELATION[int(b)]
        else:
            base = 1.0
        return base ** p.CURVATURE_CORRELATION_POWER

    return rho


# =========================================================================
#  Across-bucket γ (medium)
# =========================================================================


def csr_gamma(b: str, c: str) -> float:
    """CSR non-sec / CTP γ_bc = γ(rating)·γ(sector) (CAR ¶169 Table 5, ¶173 [MAR21.57, 21.61])."""
    bi, ci = int(b), int(c)
    g_rating = 1.0
    if bi <= 15 and ci <= 15 and ((bi <= 8) != (ci <= 8)):
        g_rating = p.CSR_RATING_GAMMA
    sb, sc = p.CSR_SECTOR_GROUP[bi], p.CSR_SECTOR_GROUP[ci]
    g_sector = 1.0 if sb == sc else p.CSR_SECTOR_GAMMA[(sb, sc)]
    return g_rating * g_sector


def equity_gamma(b: str, c: str) -> float:
    """Equity γ_bc (CAR ¶192 [MAR21.80])."""
    bi, ci = int(b), int(c)
    if p.EQUITY_OTHER_BUCKET in (bi, ci):
        return p.EQUITY_GAMMA_OTHER_BUCKET
    if bi <= 10 and ci <= 10:
        return p.EQUITY_GAMMA_SECTOR
    if {bi, ci} == {p.EQUITY_INDEX_LARGE_AE_BUCKET, p.EQUITY_INDEX_OTHER_BUCKET}:
        return p.EQUITY_GAMMA_INDICES
    return p.EQUITY_GAMMA_OTHERWISE


def commodity_gamma(b: str, c: str) -> float:
    """Commodity γ_bc (CAR ¶197 [MAR21.85])."""
    if p.COMMODITY_OTHER_BUCKET in (int(b), int(c)):
        return p.COMMODITY_GAMMA_OTHER
    return p.COMMODITY_GAMMA


def gamma_fn(rc: FRTBRiskClass) -> GammaFn:
    """Medium γ_bc for a risk class (vega uses the same, ¶207 [MAR21.95])."""
    if rc == FRTBRiskClass.GIRR:
        return lambda _b, _c: p.GIRR_GAMMA
    if rc in _CSR_CLASSES:
        return csr_gamma
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return lambda _b, _c: p.SEC_NONCTP_GAMMA
    if rc == FRTBRiskClass.EQUITY:
        return equity_gamma
    if rc == FRTBRiskClass.COMMODITY:
        return commodity_gamma
    return lambda _b, _c: p.FX_GAMMA


def is_other_bucket(rc: FRTBRiskClass, bucket: str) -> bool:
    """"Other sector" buckets aggregated by simple sum (CAR ¶168, ¶181, ¶191)."""
    if rc in _CSR_CLASSES:
        return int(bucket) == p.CSR_OTHER_BUCKET
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return int(bucket) == p.SEC_NONCTP_OTHER_BUCKET
    if rc == FRTBRiskClass.EQUITY:
        return int(bucket) == p.EQUITY_OTHER_BUCKET
    return False


# =========================================================================
#  Aggregation primitives
# =========================================================================


def bucket_k_linear(
    ws: list[float], keys: list[Key], bucket: str, rho: CorrFn, scenario: str,
) -> float:
    """K_b = sqrt(max(0, Σ WS_k² + ΣΣ_{k≠l} ρ_kl WS_k WS_l)) (CAR ¶116 [MAR21.4])."""
    total = 0.0
    n = len(ws)
    for i in range(n):
        total += ws[i] * ws[i]
        for j in range(n):
            if i != j:
                r = scenario_correlation(rho(bucket, keys[i], keys[j]), scenario)
                total += r * ws[i] * ws[j]
    return math.sqrt(max(0.0, total))


def across_buckets_linear(
    k_b: dict[str, float], s_b: dict[str, float], gamma: GammaFn, scenario: str,
) -> float:
    """Δ = sqrt(Σ K_b² + ΣΣ_{c≠b} γ_bc S_b S_c), with the ¶116 alternative S_b [MAR21.4]."""
    names = list(k_b)

    def total(sv: dict[str, float]) -> float:
        acc = sum(k_b[b] ** 2 for b in names)
        for b in names:
            for c in names:
                if b != c:
                    acc += scenario_correlation(gamma(b, c), scenario) * sv[b] * sv[c]
        return acc

    t = total(s_b)
    if t < 0.0:
        alt = {b: max(min(s_b[b], k_b[b]), -k_b[b]) for b in names}
        t = total(alt)
    return math.sqrt(max(0.0, t))


def _psi(a: float, b: float) -> float:
    """ψ = 0 if both arguments are negative, else 1 (CAR ¶117(3)(a)(iv), (4)(b))."""
    return 0.0 if (a < 0.0 and b < 0.0) else 1.0


def curvature_bucket(
    cvr_up: list[float], cvr_down: list[float], keys: list[Key], bucket: str, rho: CorrFn,
    scenario: str, other: bool = False,
) -> tuple[float, float]:
    """(K_b, S_b) for curvature (CAR ¶117(3), ¶168(3) [MAR21.5, MAR21.56]).

    Tie rule: when K_b+ = K_b−, upward is selected if Σ CVR+ > Σ CVR−, else downward.
    """
    up_sum, down_sum = sum(cvr_up), sum(cvr_down)
    if other:
        k_up = sum(max(c, 0.0) for c in cvr_up)
        k_down = sum(max(c, 0.0) for c in cvr_down)
    else:
        def k_of(cv: list[float]) -> float:
            acc = sum(max(c, 0.0) ** 2 for c in cv)
            n = len(cv)
            for i in range(n):
                for j in range(n):
                    if i != j:
                        r = scenario_correlation(rho(bucket, keys[i], keys[j]), scenario)
                        acc += r * cv[i] * cv[j] * _psi(cv[i], cv[j])
            return math.sqrt(max(0.0, acc))

        k_up, k_down = k_of(cvr_up), k_of(cvr_down)
    if k_up > k_down or (k_up == k_down and up_sum > down_sum):
        return k_up, up_sum
    return k_down, down_sum


def curvature_across(
    k_b: dict[str, float], s_b: dict[str, float], gamma: GammaFn, scenario: str,
) -> float:
    """sqrt(max(0, Σ K_b² + ΣΣ γ_bc² S_b S_c ψ(S_b, S_c))) (CAR ¶117(4), ¶213 [MAR21.5])."""
    names = list(k_b)
    acc = sum(k_b[b] ** 2 for b in names)
    for b in names:
        for c in names:
            if b != c:
                g = scenario_correlation(gamma(b, c) ** p.CURVATURE_CORRELATION_POWER, scenario)
                acc += g * s_b[b] * s_b[c] * _psi(s_b[b], s_b[c])
    return math.sqrt(max(0.0, acc))


# =========================================================================
#  Risk-class engine
# =========================================================================


@dataclass
class ClassScenarioResult:
    """Delta, vega and curvature of one risk class under one scenario."""

    delta: float = 0.0
    vega: float = 0.0
    curvature: float = 0.0

    @property
    def total(self) -> float:
        return self.delta + self.vega + self.curvature


def _group(
    sens: list[FRTBSensitivity], reporting_currency: str,
) -> dict[FRTBMeasure, dict[str, _Bucket]]:
    """Net sensitivities per (measure, bucket, risk factor) (CAR ¶116(2) [MAR21.4])."""
    out: dict[FRTBMeasure, dict[str, _Bucket]] = {m: {} for m in FRTBMeasure}
    for s in sens:
        b = bk.assign_bucket(s, reporting_currency)
        bucket = out[s.measure].setdefault(b, _Bucket(b))
        if s.measure == FRTBMeasure.DELTA:
            for key, share, tenor in _delta_entries(s):
                f = bucket.factors.setdefault(key, _Factor(key))
                f.rw = bk.delta_risk_weight(s, b, tenor, reporting_currency)
                f.amount += share * s.value
        elif s.measure == FRTBMeasure.VEGA:
            if s.risk_class == FRTBRiskClass.EQUITY and (
                s.equity_risk_factor == EquityRiskFactor.REPO
            ):
                continue  # ¶124(1)(b): no vega for equity repo rates
            for key, share in _vega_entries(s):
                f = bucket.factors.setdefault(key, _Factor(key))
                f.rw = bk.vega_risk_weight(s, b)
                f.amount += share * s.value
        else:
            key_c = _curvature_key(s)
            if key_c is None:
                continue
            scale = 1.0
            if s.risk_class == FRTBRiskClass.FX and s.flags.get(
                "fx_curvature_no_reporting_ccy", False
            ):
                scale = 1.0 / p.FX_CURVATURE_SCALAR  # ¶210 [MAR21.98]
            f = bucket.factors.setdefault(key_c, _Factor(key_c))
            f.cvr_up += scale * (s.cvr_up or 0.0)
            f.cvr_down += scale * (s.cvr_down or 0.0)
    return out


def _linear_measure(
    rc: FRTBRiskClass, buckets: dict[str, _Bucket], rho: CorrFn, scenario: str,
) -> float:
    """Delta or vega requirement of a risk class under one scenario."""
    if not buckets:
        return 0.0
    k_b: dict[str, float] = {}
    s_b: dict[str, float] = {}
    for name, bucket in buckets.items():
        factors = list(bucket.factors.values())
        ws = [f.ws for f in factors]
        if is_other_bucket(rc, name):
            k_b[name] = sum(abs(w) for w in ws)
        else:
            k_b[name] = bucket_k_linear(ws, [f.key for f in factors], name, rho, scenario)
        s_b[name] = sum(ws)
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return _sec_nonctp_combine(k_b, s_b, scenario, curvature=False)
    return across_buckets_linear(k_b, s_b, gamma_fn(rc), scenario)


def _sec_nonctp_combine(
    k_b: dict[str, float], s_b: dict[str, float], scenario: str, curvature: bool,
) -> float:
    """Buckets 1-24 with γ = 0 plus bucket 25 by simple sum (CAR ¶182-183 [MAR21.70-21.71])."""
    other = str(p.SEC_NONCTP_OTHER_BUCKET)
    main_k = {b: v for b, v in k_b.items() if b != other}
    main_s = {b: v for b, v in s_b.items() if b != other}
    gamma = gamma_fn(FRTBRiskClass.CSR_SEC_NONCTP)
    if curvature:
        core = curvature_across(main_k, main_s, gamma, scenario) if main_k else 0.0
    else:
        core = across_buckets_linear(main_k, main_s, gamma, scenario) if main_k else 0.0
    return core + k_b.get(other, 0.0)


def _curvature_measure(
    rc: FRTBRiskClass, buckets: dict[str, _Bucket], scenario: str,
) -> float:
    """Curvature requirement of a risk class under one scenario (CAR ¶117 [MAR21.5])."""
    if not buckets:
        return 0.0
    rho = curvature_rho_fn(rc)
    k_b: dict[str, float] = {}
    s_b: dict[str, float] = {}
    for name, bucket in buckets.items():
        factors = list(bucket.factors.values())
        k, sv = curvature_bucket(
            [f.cvr_up for f in factors], [f.cvr_down for f in factors],
            [f.key for f in factors], name, rho, scenario, other=is_other_bucket(rc, name),
        )
        k_b[name], s_b[name] = k, sv
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return _sec_nonctp_combine(k_b, s_b, scenario, curvature=True)
    return curvature_across(k_b, s_b, gamma_fn(rc), scenario)


def risk_class_by_scenario(
    rc: FRTBRiskClass, sens: list[FRTBSensitivity], reporting_currency: str = "CAD",
) -> dict[str, ClassScenarioResult]:
    """Delta / vega / curvature of one risk class under each of the three scenarios."""
    grouped = _group([s for s in sens if s.risk_class == rc], reporting_currency)
    out: dict[str, ClassScenarioResult] = {}
    for sc in p.SCENARIOS:
        out[sc] = ClassScenarioResult(
            delta=_linear_measure(rc, grouped[FRTBMeasure.DELTA], delta_rho_fn(rc), sc),
            vega=_linear_measure(rc, grouped[FRTBMeasure.VEGA], vega_rho_fn(rc), sc),
            curvature=_curvature_measure(rc, grouped[FRTBMeasure.CURVATURE], sc),
        )
    return out


def sbm_by_scenario(
    sens: list[FRTBSensitivity], reporting_currency: str = "CAD",
) -> dict[str, dict[FRTBRiskClass, ClassScenarioResult]]:
    """All risk classes under each scenario (CAR ¶118-119 [MAR21.6-21.7])."""
    per_class = {
        rc: risk_class_by_scenario(rc, sens, reporting_currency)
        for rc in FRTBRiskClass
        if any(s.risk_class == rc for s in sens)
    }
    return {sc: {rc: per_class[rc][sc] for rc in per_class} for sc in p.SCENARIOS}


def binding_scenario(by_scenario: dict[str, dict[FRTBRiskClass, ClassScenarioResult]]) -> str:
    """Scenario with the largest summed requirement (CAR ¶119(2) [MAR21.7]); ties -> MEDIUM."""
    best, best_val = "MEDIUM", -1.0
    for sc in ("MEDIUM", "HIGH", "LOW"):
        val = sum(r.total for r in by_scenario.get(sc, {}).values())
        if val > best_val + 1e-12:
            best, best_val = sc, val
    return best
