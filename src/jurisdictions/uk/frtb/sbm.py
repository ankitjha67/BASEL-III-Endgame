"""UK sensitivities-based method (SBM) -- PRA Market Risk: Advanced Standardised Approach Part.

Implements Articles 325e-325h (p. 314-318) with the risk factors of Articles 325l-325q
(p. 322-328) and the risk weights / correlations of Section 6 (Articles 325ae-325ay,
p. 343-361):

* delta and vega (Art 325f, p. 315-316): WS_k = RW_k * s_k;
  K_b = sqrt(max(0, sum WS_k^2 + sum_k sum_{l!=k} rho_kl WS_k WS_l));
  risk-class charge = sqrt(sum K_b^2 + sum_b sum_{c!=b} gamma_bc S_b S_c) with S_b = sum WS_k,
  and the alternative S_b = max[min(sum WS_k, K_b), -K_b] where the sum under the root is
  negative;
* curvature (Art 325g, p. 316-318): K_b^+/- with the psi function, K_b = max(K_b+, K_b-) with
  the tie rule, special 'other' buckets, and RCCR = sqrt(max(0, sum K_b^2 + sum sum gamma_bc S_b
  S_c psi(S_b, S_c))); curvature correlations are the squares of the delta ones (Art 325ay(5));
* three correlation scenarios (Art 325h, p. 318): medium, high (x1.25 capped at 100%), low
  (max(2 rho - 100%, 75% rho)); the SBM requirement is the highest of the three scenario totals
  (the scenario is selected on the sum over all risk classes, Art 325h(3)-(4)).

Sensitivities on tenors between the prescribed vertices are split by linear interpolation onto
the two adjacent vertices (Art 325l(1), p. 323).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from src.jurisdictions.frtb_base import (
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
    SBMClassResult,
)
from src.jurisdictions.uk.frtb import buckets as bk
from src.jurisdictions.uk.frtb import params as p

RISK_CLASS_ORDER: tuple[FRTBRiskClass, ...] = tuple(FRTBRiskClass)


# =========================================================================
#  Scenario transforms -- Art 325h(2) (p. 318)
# =========================================================================


def scenario_correlation(rho: float, scenario: str) -> float:
    """Apply a correlation scenario to a prescribed rho or gamma (Art 325h(2), p. 318)."""
    if scenario == "MEDIUM":
        return rho
    if scenario == "HIGH":
        return min(rho * p.SCENARIO_HIGH_MULTIPLIER, p.SCENARIO_HIGH_CAP)
    if scenario == "LOW":
        return max(p.SCENARIO_LOW_SLOPE * rho - 1.0, p.SCENARIO_LOW_FLOOR_FACTOR * rho)
    raise ValueError(f"unknown correlation scenario {scenario!r}")


# =========================================================================
#  Vertex allocation (linear interpolation, Art 325l(1), p. 323)
# =========================================================================


def allocate_to_vertices(t: float, vertices: tuple[float, ...]) -> list[tuple[float, float]]:
    """Split a tenor onto the adjacent prescribed vertices by linear interpolation.

    Returns ``[(vertex, weight)]`` with weights summing to one; tenors outside the grid go to
    the nearest end vertex (Art 325l(1) 'by linear interpolation', p. 323).
    """
    if t <= vertices[0]:
        return [(vertices[0], 1.0)]
    if t >= vertices[-1]:
        return [(vertices[-1], 1.0)]
    for lo, hi in zip(vertices[:-1], vertices[1:], strict=True):
        if lo <= t <= hi:
            if t == lo:
                return [(lo, 1.0)]
            if t == hi:
                return [(hi, 1.0)]
            w = (hi - t) / (hi - lo)
            return [(lo, w), (hi, 1.0 - w)]
    raise AssertionError("unreachable")  # pragma: no cover


# =========================================================================
#  Risk factors
# =========================================================================


@dataclass(frozen=True)
class Factor:
    """A netting-level risk factor (Art 325f(5): sensitivities to the same risk factor net)."""

    risk_class: FRTBRiskClass
    bucket: str
    name: str = ""
    """Issuer / tranche / equity / commodity name, or GIRR curve name."""
    tenor: float | None = None
    sub: str = ""
    """GIRR curve type; CSR 'BOND'/'CDS' basis; equity 'SPOT'/'REPO'."""
    location: str = ""
    """Commodity delivery location (Art 325p(2), 325at(2))."""
    opt_mat: float | None = None
    und_mat: float | None = None


_WSMap = dict[FRTBRiskClass, dict[str, dict[Factor, float]]]
"""Weighted sensitivities by risk class, bucket and risk factor."""


def _name(s: FRTBSensitivity) -> str:
    """Name key: issuer, else tranche id / commodity name / label."""
    return s.issuer or s.tranche_id or s.commodity_name or s.label


def _delta_factors(
    s: FRTBSensitivity, bucket: str
) -> list[tuple[Factor, float]]:
    """Delta risk factors and allocation weights for a sensitivity (Art 325l-325q)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is GIRRCurve.RISK_FREE:
            if s.tenor_years is None:
                raise ValueError("GIRR risk-free delta requires tenor_years (Art 325l(1))")
            return [
                (Factor(rc, bucket, s.curve_name, v, GIRRCurve.RISK_FREE.value), w)
                for v, w in allocate_to_vertices(s.tenor_years, p.GIRR_VERTICES)
            ]
        # Inflation: one risk factor per inflation curve; cross-currency basis: basis over USD
        # or EUR (curve_name) -- Art 325l(5)-(6), p. 323-324.
        return [(Factor(rc, bucket, s.curve_name, None, s.girr_curve.value), 1.0)]
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP, FRTBRiskClass.CSR_SEC_NONCTP):
        if s.tenor_years is None:
            raise ValueError("CSR delta requires tenor_years (Art 325m(1), 325n)")
        key = (s.tranche_id or s.label) if rc is FRTBRiskClass.CSR_SEC_NONCTP else _name(s)
        basis = "CDS" if s.is_cds else "BOND"
        return [
            (Factor(rc, bucket, key, v, basis), w)
            for v, w in allocate_to_vertices(s.tenor_years, p.CSR_VERTICES)
        ]
    if rc is FRTBRiskClass.EQUITY:
        return [(Factor(rc, bucket, _name(s), None, s.equity_risk_factor.value), 1.0)]
    if rc is FRTBRiskClass.COMMODITY:
        t = s.tenor_years if s.tenor_years is not None else 0.0
        name = s.commodity_name or s.label
        return [
            (Factor(rc, bucket, name, v, "", s.delivery_location), w)
            for v, w in allocate_to_vertices(t, p.COMMODITY_VERTICES)
        ]
    return [(Factor(rc, bucket, bucket), 1.0)]


def _vega_factors(s: FRTBSensitivity, bucket: str) -> list[tuple[Factor, float]]:
    """Vega risk factors: option maturity (and underlying residual maturity for GIRR) mapped to
    0.5/1/3/5/10 years (Art 325l(7), 325m(2), 325n(3)(b)/(5)(b), 325o(3), 325p(3), 325q(2)).

    Options without a maturity map to the longest maturity (Art 325s(2), p. 331)."""
    rc = s.risk_class
    t = s.option_maturity_years
    opt = allocate_to_vertices(t if t is not None else p.VEGA_OPTION_MATURITIES[-1],
                               p.VEGA_OPTION_MATURITIES)
    if rc is FRTBRiskClass.GIRR:
        u = s.underlying_maturity_years
        und = allocate_to_vertices(
            u if u is not None else p.GIRR_VEGA_UNDERLYING_MATURITIES[-1],
            p.GIRR_VEGA_UNDERLYING_MATURITIES,
        )
        return [
            (Factor(rc, bucket, "", None, "", "", vo, vu), wo * wu)
            for vo, wo in opt
            for vu, wu in und
        ]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        name = s.tranche_id or s.label
    elif rc is FRTBRiskClass.COMMODITY:
        name = s.commodity_name or s.label
    elif rc is FRTBRiskClass.FX:
        name = bucket
    else:
        name = _name(s)
    basis = "CDS" if s.is_cds else "BOND"
    sub = basis if rc in (
        FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP, FRTBRiskClass.CSR_SEC_NONCTP
    ) else ""
    return [(Factor(rc, bucket, name, None, sub, "", vo), wo) for vo, wo in opt]


def _curvature_factor(s: FRTBSensitivity, bucket: str) -> Factor | None:
    """Curvature risk factor (Art 325l(8)-(9), 325m(3)-(4), 325n(3)(c)/(4)/(5)(c), 325o(4),
    325p(4), 325q(3)). GIRR: one per currency; CSR: one per issuer curve (bond and CDS curves
    are the same factor); equity: spot only; commodity: one per commodity type regardless of
    delivery location. Inflation, cross-currency basis and equity repo have no curvature
    (returns None)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is not GIRRCurve.RISK_FREE:
            return None
        return Factor(rc, bucket, bucket)
    if rc is FRTBRiskClass.EQUITY:
        if s.equity_risk_factor is EquityRiskFactor.REPO:
            return None
        return Factor(rc, bucket, _name(s))
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return Factor(rc, bucket, s.tranche_id or s.label)
    if rc is FRTBRiskClass.COMMODITY:
        return Factor(rc, bucket, s.commodity_name or s.label)
    if rc is FRTBRiskClass.FX:
        return Factor(rc, bucket, bucket)
    return Factor(rc, bucket, _name(s))


# =========================================================================
#  Correlations (medium scenario) -- Section 6
# =========================================================================


def _girr_delta_rho(k: Factor, j: Factor) -> float:
    """GIRR intra-bucket delta correlation (Art 325af(1)-(6), p. 344-345)."""
    rf = GIRRCurve.RISK_FREE.value
    xc = GIRRCurve.XCCY_BASIS.value
    if k.sub == xc or j.sub == xc:
        return p.GIRR_XCCY_CORR
    if k.sub != rf and j.sub != rf:
        return p.GIRR_INFLATION_INFLATION_CORR  # two different inflation curves, same currency
    if k.sub != rf or j.sub != rf:
        return p.GIRR_INFLATION_CORR
    assert k.tenor is not None and j.tenor is not None
    if k.tenor == j.tenor:
        tenor_rho = 1.0
    else:
        tenor_rho = max(
            math.exp(-p.GIRR_THETA * abs(k.tenor - j.tenor) / min(k.tenor, j.tenor)),
            p.GIRR_TENOR_CORR_FLOOR,
        )
    curve_rho = 1.0 if k.name == j.name else p.GIRR_DIFFERENT_CURVE_CORR
    return tenor_rho * curve_rho


def _csr_name_rho(k: Factor, j: Factor) -> float:
    """rho(name) for CSR non-securitisation and ACTP (Art 325ai(1), p. 347-348)."""
    if k.name == j.name:
        return 1.0
    if k.bucket in p.CSR_NONSEC_INDEX_BUCKETS and k.risk_class is FRTBRiskClass.CSR_NONSEC:
        return p.CSR_NAME_CORR_INDEX
    return p.CSR_NAME_CORR_SECTOR


def _csr_basis(rc: FRTBRiskClass) -> float:
    """rho(basis): 99.90% (Art 325ai(1), 325an(1)); 99.00% for the ACTP (Art 325al(1))."""
    return p.CSR_CTP_BASIS_CORR if rc is FRTBRiskClass.CSR_SEC_CTP else p.CSR_BASIS_CORR


def _delta_rho(k: Factor, j: Factor, *, with_tenor: bool = True) -> float:
    """Medium-scenario intra-bucket delta correlation for any risk class (Section 6).

    ``with_tenor=False`` drops the tenor component (used for the rho(DELTA) part of the vega
    correlation, whose maturity dimension is the option maturity, Art 325ay(2))."""
    rc = k.risk_class
    if rc is FRTBRiskClass.GIRR:
        return _girr_delta_rho(k, j)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        tenor = 1.0 if (not with_tenor or k.tenor == j.tenor) else p.CSR_TENOR_CORR
        basis = 1.0 if k.sub == j.sub else _csr_basis(rc)
        return _csr_name_rho(k, j) * tenor * basis
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        tranche = 1.0 if k.name == j.name else p.CSR_SEC_TRANCHE_CORR
        tenor = 1.0 if (not with_tenor or k.tenor == j.tenor) else p.CSR_SEC_TENOR_CORR
        basis = 1.0 if k.sub == j.sub else p.CSR_SEC_BASIS_CORR
        return tranche * tenor * basis
    if rc is FRTBRiskClass.EQUITY:
        spot = EquityRiskFactor.SPOT.value
        if k.name == j.name:
            # same issuer: spot vs repo 99.90% (Art 325aq(1)); same issuer and type (vega at
            # different option maturities) -> 1
            return 1.0 if k.sub == j.sub else p.EQUITY_SPOT_REPO_SAME_NAME_CORR
        base = p.EQUITY_CORR[k.bucket]
        if (k.sub == spot) != (j.sub == spot):
            return base * p.EQUITY_SPOT_REPO_DIFF_NAME_FACTOR  # Art 325aq(4)
        return base  # Art 325aq(2)-(3)
    if rc is FRTBRiskClass.COMMODITY:
        commodity = 1.0 if k.name == j.name else p.COMMODITY_CORR[k.bucket]
        tenor = 1.0 if (not with_tenor or k.tenor == j.tenor) else p.COMMODITY_TENOR_CORR
        basis = 1.0 if k.location == j.location else p.COMMODITY_BASIS_CORR
        return commodity * tenor * basis
    return 1.0  # FX: a single risk factor per bucket (Art 325q(1))


def _vega_rho(k: Factor, j: Factor) -> float:
    """Medium-scenario vega correlation (Art 325ay(1)-(2), p. 360)."""
    assert k.opt_mat is not None and j.opt_mat is not None
    rho_opt = math.exp(-p.VEGA_ALPHA * abs(k.opt_mat - j.opt_mat) / min(k.opt_mat, j.opt_mat))
    if k.risk_class is FRTBRiskClass.GIRR:
        assert k.und_mat is not None and j.und_mat is not None
        rho_und = math.exp(
            -p.VEGA_ALPHA * abs(k.und_mat - j.und_mat) / min(k.und_mat, j.und_mat)
        )
        return min(rho_opt * rho_und, 1.0)
    return min(_delta_rho(k, j, with_tenor=False) * rho_opt, 1.0)


def _curvature_rho(k: Factor, j: Factor) -> float:
    """Curvature correlation = square of the delta correlation (Art 325ay(5), p. 361); the
    curvature risk factor is curve-level, so tenor and basis components are one."""
    return _delta_rho(k, j, with_tenor=False) ** p.CURVATURE_CORR_POWER


def _csr_rating_category(rc: FRTBRiskClass, bucket: str) -> str:
    """Rating category of a CSR bucket for gamma(rating) (Art 325aj, p. 348)."""
    if bucket in p.CSR_NONSEC_IG_BUCKETS and not (
        rc is FRTBRiskClass.CSR_SEC_CTP and bucket == "17"
    ):
        return "IG"
    if bucket in p.CSR_NONSEC_HY_BUCKETS:
        return "HY_NR"
    return "OTHER"


def gamma(rc: FRTBRiskClass, b: str, c: str) -> float:
    """Medium-scenario cross-bucket correlation gamma_bc (Section 6).

    GIRR 50% (Art 325ag); CSR non-sec / ACTP gamma(rating) x gamma(sector) (Art 325aj, 325al(2));
    non-ACTP 0% (Art 325ao); equity (Art 325ar); commodity (Art 325au); FX 60% (Art 325aw).
    """
    if rc is FRTBRiskClass.GIRR:
        return p.GIRR_GAMMA
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        g_sector_b, g_sector_c = p.CSR_SECTOR_GROUP[b], p.CSR_SECTOR_GROUP[c]
        sector = 1.0 if g_sector_b == g_sector_c else p.CSR_SECTOR_GAMMA[(g_sector_b, g_sector_c)]
        same_rating = _csr_rating_category(rc, b) == _csr_rating_category(rc, c)
        # TODO: VERIFY -- Art 325aj (p. 348) applies gamma(rating) = 50% to any two buckets of
        # different rating category (literal text, used here, incl. buckets 17 vs 18); BCBS
        # MAR21.57 restricts it to buckets 1 to 15.
        return sector * (1.0 if same_rating else p.CSR_RATING_GAMMA)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.CSR_SEC_GAMMA
    if rc is FRTBRiskClass.EQUITY:
        if p.EQUITY_OTHER_BUCKET in (b, c):
            return p.EQUITY_GAMMA_OTHER
        idx_b, idx_c = b in p.EQUITY_INDEX_BUCKETS, c in p.EQUITY_INDEX_BUCKETS
        if idx_b and idx_c:
            return p.EQUITY_GAMMA_INDICES
        if not idx_b and not idx_c:
            return p.EQUITY_GAMMA_SECTOR
        return p.EQUITY_GAMMA_ELSE
    if rc is FRTBRiskClass.COMMODITY:
        if p.COMMODITY_OTHER_BUCKET in (b, c):
            return p.COMMODITY_GAMMA_OTHER
        return p.COMMODITY_GAMMA
    return p.FX_GAMMA


def is_abs_sum_bucket(rc: FRTBRiskClass, bucket: str) -> bool:
    """'Other sector' buckets aggregated without diversification (K_b = sum |WS_k|):
    CSR non-sec 16 (Art 325ai(2)), non-ACTP 25 (Art 325an(2)), equity 11 (Art 325aq(5)); ACTP
    16 by analogy (Art 325al(1) derives rho per Art 325ai; Art 325g(5) lists Table 6 bucket 16
    for curvature)."""
    return (
        (rc is FRTBRiskClass.CSR_NONSEC and bucket == p.CSR_NONSEC_OTHER_BUCKET)
        or (rc is FRTBRiskClass.CSR_SEC_CTP and bucket == p.CSR_CTP_OTHER_BUCKET)
        or (rc is FRTBRiskClass.CSR_SEC_NONCTP and bucket == p.CSR_SEC_NONCTP_OTHER_BUCKET)
        or (rc is FRTBRiskClass.EQUITY and bucket == p.EQUITY_OTHER_BUCKET)
    )


def _added_outside(rc: FRTBRiskClass, bucket: str) -> bool:
    """Non-ACTP bucket 25 is added to the risk-class charge with no diversification
    (Art 325ao(2), p. 353)."""
    return rc is FRTBRiskClass.CSR_SEC_NONCTP and bucket == p.CSR_SEC_NONCTP_OTHER_BUCKET


# =========================================================================
#  Aggregation
# =========================================================================


def bucket_capital(
    ws: dict[Factor, float],
    rho: Callable[[Factor, Factor], float],
    abs_sum: bool,
) -> float:
    """K_b (Art 325f(7), p. 315): sqrt(max(0, sum WS^2 + sum sum rho WS WS)); 'other' buckets
    sum |WS_k| (Art 325ai(2), 325an(2), 325aq(5))."""
    if abs_sum:
        return sum(abs(v) for v in ws.values())
    items = list(ws.items())
    total = 0.0
    for i, (fk, wk) in enumerate(items):
        total += wk * wk
        for fl, wl in items[i + 1:]:
            total += 2.0 * rho(fk, fl) * wk * wl
    return math.sqrt(max(total, 0.0))


def aggregate_buckets(
    rc: FRTBRiskClass,
    k_b: dict[str, float],
    s_b: dict[str, float],
    gamma_fn: Callable[[str, str], float],
) -> float:
    """Risk-class delta/vega charge (Art 325f(8), p. 315-316), with the alternative S_b where the
    sum under the root is negative, and non-ACTP bucket 25 added outside (Art 325ao(2))."""
    inner = [b for b in k_b if not _added_outside(rc, b)]
    outside = sum(k_b[b] for b in k_b if _added_outside(rc, b))

    def quad(s: dict[str, float]) -> float:
        tot = sum(k_b[b] ** 2 for b in inner)
        for i, b in enumerate(inner):
            for c in inner[i + 1:]:
                tot += 2.0 * gamma_fn(b, c) * s[b] * s[c]
        return tot

    q = quad(s_b)
    if q < 0.0:
        alt = {b: max(min(s_b[b], k_b[b]), -k_b[b]) for b in inner}
        q = quad(alt)
    return math.sqrt(max(q, 0.0)) + outside


def _psi(x: float, y: float) -> float:
    """psi(x, y) = 0 where x < 0 and y < 0; 1 otherwise (Art 325g(4), (6), p. 317)."""
    return 0.0 if (x < 0.0 and y < 0.0) else 1.0


def curvature_bucket(
    cvr: dict[Factor, tuple[float, float]],
    rho: Callable[[Factor, Factor], float],
    special: bool,
) -> tuple[float, float]:
    """Bucket curvature (Art 325g(4)-(5), p. 317): returns (K_b, S_b).

    K_b^+/- = sqrt(max(0, sum max(CVR,0)^2 + sum sum rho CVR_k CVR_l psi(CVR_k, CVR_l)));
    K_b = max(K_b+, K_b-), or where equal K_b+ if sum CVR+ > sum CVR-, else K_b-.
    'Other' buckets: K_b = max(sum max(CVR+,0), sum max(CVR-,0)).
    """
    ups = [(f, v[0]) for f, v in cvr.items()]
    downs = [(f, v[1]) for f, v in cvr.items()]
    sum_up = sum(v for _, v in ups)
    sum_down = sum(v for _, v in downs)

    if special:
        k_up = sum(max(v, 0.0) for _, v in ups)
        k_down = sum(max(v, 0.0) for _, v in downs)
    else:

        def k(side: list[tuple[Factor, float]]) -> float:
            tot = sum(max(v, 0.0) ** 2 for _, v in side)
            for i, (fk, vk) in enumerate(side):
                for fl, vl in side[i + 1:]:
                    tot += 2.0 * rho(fk, fl) * vk * vl * _psi(vk, vl)
            return math.sqrt(max(tot, 0.0))

        k_up, k_down = k(ups), k(downs)

    if k_up > k_down or (k_up == k_down and sum_up > sum_down):
        return k_up, sum_up
    return k_down, sum_down


def aggregate_curvature(
    rc: FRTBRiskClass,
    k_b: dict[str, float],
    s_b: dict[str, float],
    gamma_fn: Callable[[str, str], float],
) -> float:
    """RCCR = sqrt(max(0, sum K_b^2 + sum sum gamma_bc S_b S_c psi(S_b, S_c))) (Art 325g(6),
    p. 317), non-ACTP bucket 25 added outside (Art 325ao(2))."""
    inner = [b for b in k_b if not _added_outside(rc, b)]
    outside = sum(k_b[b] for b in k_b if _added_outside(rc, b))
    tot = sum(k_b[b] ** 2 for b in inner)
    for i, b in enumerate(inner):
        for c in inner[i + 1:]:
            tot += 2.0 * gamma_fn(b, c) * s_b[b] * s_b[c] * _psi(s_b[b], s_b[c])
    return math.sqrt(max(tot, 0.0)) + outside


# =========================================================================
#  Engine
# =========================================================================


@dataclass
class SBMEngine:
    """UK SBM calculator (Articles 325e-325h).

    ``domestic_currency`` drives the GIRR sqrt(2) reduction (Art 325ae(3)) and is the reporting
    currency of the FX risk factors (Art 325q(1)); ``fx_curvature_permission`` applies the 1.5
    divisor to all FX curvature positions (Art 325q(6), PRA permission).
    """

    domestic_currency: str = p.REPORTING_CURRENCY
    fx_curvature_permission: bool = False

    # ---- weighted sensitivities --------------------------------------
    def weighted_delta(
        self, sens: Iterable[FRTBSensitivity]
    ) -> _WSMap:
        """Net sensitivities per risk factor within each bucket and weight them
        (Art 325f(4)-(6), p. 315)."""
        out: _WSMap = defaultdict(lambda: defaultdict(dict))
        rws: dict[Factor, float] = {}
        net: dict[Factor, float] = defaultdict(float)
        for s in sens:
            bucket = bk.assign_bucket(s)
            for f, w in _delta_factors(s, bucket):
                net[f] += s.value * w
                rws[f] = bk.delta_rw(s, bucket, f.tenor, self.domestic_currency)
        for f, v in net.items():
            out[f.risk_class][f.bucket][f] = rws[f] * v
        return out

    def weighted_vega(
        self, sens: Iterable[FRTBSensitivity]
    ) -> _WSMap:
        """Vega weighted sensitivities (Art 325f with Table 11 risk weights, p. 359-360)."""
        out: _WSMap = defaultdict(lambda: defaultdict(dict))
        rws: dict[Factor, float] = {}
        net: dict[Factor, float] = defaultdict(float)
        for s in sens:
            bucket = bk.assign_bucket(s)
            for f, w in _vega_factors(s, bucket):
                net[f] += s.value * w
                rws[f] = bk.vega_rw(s, bucket)
        for f, v in net.items():
            out[f.risk_class][f.bucket][f] = rws[f] * v
        return out

    def curvature_positions(
        self, sens: Iterable[FRTBSensitivity]
    ) -> dict[FRTBRiskClass, dict[str, dict[Factor, tuple[float, float]]]]:
        """Net CVR+ / CVR- per curvature risk factor (Art 325g(1)-(3), p. 316-317), with the
        optional FX division by 1.5 (Art 325q(5)-(6), p. 328)."""
        acc: dict[Factor, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for s in sens:
            bucket = bk.assign_bucket(s)
            f = _curvature_factor(s, bucket)
            if f is None:
                continue
            up, down = s.cvr_up or 0.0, s.cvr_down or 0.0
            if s.risk_class is FRTBRiskClass.FX and (
                self.fx_curvature_permission or s.flags.get("fx_curvature_div_1_5")
            ):
                up, down = up / p.CURVATURE_FX_SCALAR, down / p.CURVATURE_FX_SCALAR
            acc[f][0] += up
            acc[f][1] += down
        out: dict[FRTBRiskClass, dict[str, dict[Factor, tuple[float, float]]]] = defaultdict(
            dict
        )
        for f, (u, d) in acc.items():
            out[f.risk_class].setdefault(f.bucket, {})[f] = (u, d)
        return out

    # ---- risk-class charges per scenario -------------------------------
    @staticmethod
    def _linear_charge(
        rc: FRTBRiskClass,
        buckets: dict[str, dict[Factor, float]],
        base_rho: Callable[[Factor, Factor], float],
        scenario: str,
    ) -> float:
        """Delta or vega charge of one risk class under one scenario (Art 325f, 325h)."""

        def rho(k: Factor, j: Factor) -> float:
            return scenario_correlation(base_rho(k, j), scenario)

        k_b = {b: bucket_capital(ws, rho, is_abs_sum_bucket(rc, b)) for b, ws in buckets.items()}
        s_b = {b: sum(ws.values()) for b, ws in buckets.items()}
        return aggregate_buckets(
            rc, k_b, s_b, lambda b, c: scenario_correlation(gamma(rc, b, c), scenario)
        )

    @staticmethod
    def _curvature_charge(
        rc: FRTBRiskClass,
        buckets: dict[str, dict[Factor, tuple[float, float]]],
        scenario: str,
    ) -> float:
        """Curvature charge of one risk class under one scenario (Art 325g, 325h, 325ay(5))."""

        def rho(k: Factor, j: Factor) -> float:
            return scenario_correlation(_curvature_rho(k, j), scenario)

        k_b: dict[str, float] = {}
        s_b: dict[str, float] = {}
        for b, cvr in buckets.items():
            k_b[b], s_b[b] = curvature_bucket(cvr, rho, is_abs_sum_bucket(rc, b))
        return aggregate_curvature(
            rc,
            k_b,
            s_b,
            lambda b, c: scenario_correlation(
                gamma(rc, b, c) ** p.CURVATURE_CORR_POWER, scenario
            ),
        )

    def by_scenario(
        self, sensitivities: list[FRTBSensitivity]
    ) -> dict[str, list[SBMClassResult]]:
        """Risk-class delta / vega / curvature charges under each of the three scenarios."""
        delta = self.weighted_delta(s for s in sensitivities if s.measure is FRTBMeasure.DELTA)
        vega = self.weighted_vega(s for s in sensitivities if s.measure is FRTBMeasure.VEGA)
        curv = self.curvature_positions(
            s for s in sensitivities if s.measure is FRTBMeasure.CURVATURE
        )
        classes = [rc for rc in RISK_CLASS_ORDER if rc in delta or rc in vega or rc in curv]
        out: dict[str, list[SBMClassResult]] = {}
        for sc in p.SCENARIOS:
            rows: list[SBMClassResult] = []
            for rc in classes:
                d = self._linear_charge(rc, delta.get(rc, {}), _delta_rho, sc)
                v = self._linear_charge(rc, vega.get(rc, {}), _vega_rho, sc)
                c = self._curvature_charge(rc, curv.get(rc, {}), sc)
                rows.append(
                    SBMClassResult(
                        risk_class=rc, delta=d, vega=v, curvature=c, total=d + v + c, scenario=sc
                    )
                )
            out[sc] = rows
        return out

    def capital(self, sensitivities: list[FRTBSensitivity]) -> tuple[list[SBMClassResult], str]:
        """SBM requirement: the highest of the three scenario-specific sums (Art 325h(3)-(4),
        p. 318). Returns the risk-class rows of the binding scenario and its name."""
        per = self.by_scenario(sensitivities)
        totals = {sc: sum(r.total for r in rows) for sc, rows in per.items()}
        binding = max(p.SCENARIOS, key=lambda sc: totals[sc])
        return per[binding], binding
