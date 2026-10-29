"""Sensitivities-based method (Basel Framework MAR21).

Implements, for each of the seven risk classes:

    - delta and vega (MAR21.4): net sensitivities per risk factor, WS_k = RW_k s_k,
      K_b = sqrt(max(0, sum_k WS_k^2 + sum_k sum_{l != k} rho_kl WS_k WS_l)),
      across buckets sqrt(sum_b K_b^2 + sum_b sum_{c != b} gamma_bc S_b S_c) with
      S_b = sum_k WS_k and the alternative S_b = max(min(sum_k WS_k, K_b), -K_b) when the
      sum under the root is negative (MAR21.4(5)(b), formulas read from p. 570-571);
    - curvature (MAR21.5): CVR+ / CVR- inputs, K_b+ and K_b- with the psi function,
      selection of the upward / downward scenario (including the tie rule), across-bucket
      aggregation with psi(S_b, S_c) and no alternative specification (pp. 572-573);
    - "other sector" buckets aggregated by simple sum (MAR21.56, 21.69, 21.79) and the
      non-CTP securitisation bucket 25 added outside the root (MAR21.71);
    - the three correlation scenarios (MAR21.6): medium = prescribed, high = min(1.25 x, 1),
      low = max(2x - 1, 0.75x), applied to rho and gamma (to the squared parameters for
      curvature, MAR21.100-21.101); the SBM requirement is the largest scenario total
      across all risk classes (MAR21.7).

All amounts are in the reporting currency (millions). Inputs follow
:mod:`src.jurisdictions.frtb_base` (delta s_k, vega = vega x implied vol, CVR+/-).

Documented ``flags`` keys on :class:`FRTBSensitivity`:
    - ``fx_curvature_scalar_1_5``: the FX option does not reference the reporting currency;
      CVR+ and CVR- are divided by 1.5 (MAR21.98).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from src.jurisdictions.bcbs.frtb import buckets as bk
from src.jurisdictions.bcbs.frtb import params as p
from src.jurisdictions.frtb_base import (
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
    SBMClassResult,
)

FX_CURVATURE_FLAG = "fx_curvature_scalar_1_5"
"""Flag on an FX curvature sensitivity: divide CVR+/- by 1.5 (MAR21.98)."""

RISK_CLASS_ORDER: tuple[FRTBRiskClass, ...] = (
    FRTBRiskClass.GIRR,
    FRTBRiskClass.CSR_NONSEC,
    FRTBRiskClass.CSR_SEC_NONCTP,
    FRTBRiskClass.CSR_SEC_CTP,
    FRTBRiskClass.EQUITY,
    FRTBRiskClass.COMMODITY,
    FRTBRiskClass.FX,
)
"""MAR21.1(1): the seven risk classes."""


# =========================================================================
#  Scenario transforms (MAR21.6)
# =========================================================================


def scenario_correlation(value: float, scenario: str) -> float:
    """Apply a MAR21.6 correlation scenario to one rho or gamma.

    MEDIUM: as prescribed. HIGH: x 1.25, capped at 100%. LOW:
    max(2 x value - 100%; 75% x value) (formula read from p. 574).
    """
    if scenario == "MEDIUM":
        return value
    if scenario == "HIGH":
        return min(p.HIGH_CORRELATION_MULTIPLIER * value, p.CORRELATION_CAP)
    if scenario == "LOW":
        return max(p.LOW_CORRELATION_SLOPE * value - p.LOW_CORRELATION_INTERCEPT,
                   p.LOW_CORRELATION_FLOOR_FACTOR * value)
    raise ValueError(f"unknown correlation scenario {scenario!r}")


# =========================================================================
#  Risk factors
# =========================================================================


@dataclass
class _Factor:
    """A netted risk factor within a bucket (MAR21.4(2))."""

    key: tuple[object, ...]
    rep: FRTBSensitivity
    """Representative sensitivity (carries the descriptors for correlations)."""
    ws: float = 0.0
    cvr_up: float = 0.0
    cvr_down: float = 0.0


@dataclass
class _Bucket:
    """Factors of one bucket for one risk class and measure."""

    name: str
    factors: list[_Factor] = field(default_factory=list)


def _name(s: FRTBSensitivity) -> str:
    """Issuer / name key: ``issuer`` then ``label``."""
    return s.issuer or s.label


def _tranche(s: FRTBSensitivity) -> str:
    """Tranche key for non-CTP securitisations (MAR21.68): ``tranche_id`` then ``label``."""
    return s.tranche_id or s.label


def _commodity(s: FRTBSensitivity) -> str:
    """Commodity key (MAR21.83(1)): ``commodity_name`` then ``label``."""
    return s.commodity_name or s.label


def _xccy_curve(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> str:
    """Cross-currency basis curve key; MAR21.45 simple-sum option merges onshore/offshore."""
    return "" if options.xccy_onshore_offshore_simple_sum else s.curve_name


def delta_factor_key(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> tuple[object, ...]:
    """Delta risk factor identity (MAR21.8-21.14); equal keys are netted (MAR21.4(2))."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is GIRRCurve.INFLATION:
            return ("INFLATION", s.curve_name)
        if s.girr_curve is GIRRCurve.XCCY_BASIS:
            return ("XCCY", _xccy_curve(s, options))
        return ("RF", s.curve_name, bk.snap_tenor(s.tenor_years, p.GIRR_TENORS, "GIRR"))
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return (_name(s), bk.snap_tenor(s.tenor_years, p.CSR_TENORS, "CSR"), s.is_cds)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return (_tranche(s), bk.snap_tenor(s.tenor_years, p.CSR_TENORS, "CSR sec"), s.is_cds)
    if rc is FRTBRiskClass.EQUITY:
        return (_name(s), s.equity_risk_factor.value)
    if rc is FRTBRiskClass.COMMODITY:
        return (_commodity(s), bk.snap_tenor(s.tenor_years, p.COMMODITY_TENORS, "commodity"),
                s.delivery_location)
    return (bk.fx_bucket(s),)


def vega_factor_key(s: FRTBSensitivity) -> tuple[object, ...]:
    """Vega risk factor identity (MAR21.8(4), 21.9(2)-21.14(2))."""
    opt = bk.snap_tenor(s.option_maturity_years, p.VEGA_TENORS, "vega option maturity")
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is not GIRRCurve.RISK_FREE:
            # MAR21.8 FAQ4: inflation / xccy vega along option maturity only.
            return (s.girr_curve.value, s.curve_name, opt, None)
        und = bk.snap_tenor(s.underlying_maturity_years, p.VEGA_TENORS, "vega underlying")
        return ("RF", "", opt, und)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP, FRTBRiskClass.EQUITY):
        return (_name(s), opt)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return (_tranche(s), opt)
    if rc is FRTBRiskClass.COMMODITY:
        return (_commodity(s), opt)
    return (bk.fx_bucket(s), opt)


def curvature_factor_key(s: FRTBSensitivity) -> tuple[object, ...]:
    """Curvature risk factor identity (MAR21.8(5), 21.9(3)-21.14(3)).

    GIRR: the whole risk-free curve set of the currency (one factor per bucket);
    no curvature for inflation or cross-currency basis (MAR21.8(5)(b)).
    """
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is not GIRRCurve.RISK_FREE:
            raise ValueError("no GIRR curvature for inflation / cross-currency basis "
                             "(MAR21.8(5)(b))")
        return (bk.girr_bucket(s),)
    if rc is FRTBRiskClass.EQUITY:
        if s.equity_risk_factor is EquityRiskFactor.REPO:
            raise ValueError("no curvature for equity repo rates (MAR21.12(3)(b))")
        return (_name(s),)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return (_name(s),)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return (_tranche(s),)
    if rc is FRTBRiskClass.COMMODITY:
        return (_commodity(s),)
    return (bk.fx_bucket(s),)


# =========================================================================
#  Prescribed (medium) correlations
# =========================================================================


def girr_tenor_rho(t1: float, t2: float) -> float:
    """MAR21.46 Table 2 lookup."""
    i, j = p.GIRR_TENORS.index(t1), p.GIRR_TENORS.index(t2)
    return p.GIRR_TENOR_CORRELATION[i][j]


def girr_delta_rho(a: _Factor, b: _Factor) -> float:
    """MAR21.45-21.49 within-bucket GIRR delta correlation."""
    ka, kb = a.key, b.key
    if ka[0] == "XCCY" or kb[0] == "XCCY":
        return p.GIRR_XCCY_RHO  # MAR21.49
    if ka[0] == "INFLATION" and kb[0] == "INFLATION":
        return p.GIRR_DIFF_CURVE_FACTOR  # MAR21.47 FAQ1
    if ka[0] == "INFLATION" or kb[0] == "INFLATION":
        return p.GIRR_INFLATION_VS_YIELD_RHO  # MAR21.48
    _, c1, t1 = ka
    _, c2, t2 = kb
    assert isinstance(t1, float) and isinstance(t2, float)
    if c1 == c2:
        return girr_tenor_rho(t1, t2)  # MAR21.46
    if t1 == t2:
        return p.GIRR_SAME_TENOR_DIFF_CURVE_RHO  # MAR21.45
    return girr_tenor_rho(t1, t2) * p.GIRR_DIFF_CURVE_FACTOR  # MAR21.47


def _maturity_rho(t1: float | None, t2: float | None) -> float:
    """exp(-alpha |T_k - T_l| / min(T_k, T_l)), alpha = 1% (MAR21.93, p. 615)."""
    if t1 is None or t2 is None:
        return 1.0
    return math.exp(-p.VEGA_ALPHA * abs(t1 - t2) / min(t1, t2))


def csr_rho_components(bucket: int, ctp: bool) -> tuple[float, float, float]:
    """(rho_name, rho_tenor, rho_basis) when name / tenor / curve differ.

    MAR21.54-21.55 (non-sec, index buckets), MAR21.60 (CTP basis 99%).
    """
    if not ctp and bucket in (p.CSR_IG_INDEX_BUCKET, p.CSR_HY_INDEX_BUCKET):
        return (p.CSR_INDEX_RHO_NAME_DIFF, p.CSR_INDEX_RHO_TENOR_DIFF, p.CSR_INDEX_RHO_BASIS_DIFF)
    basis = p.CSR_CTP_RHO_BASIS_DIFF if ctp else p.CSR_RHO_BASIS_DIFF
    return (p.CSR_RHO_NAME_DIFF, p.CSR_RHO_TENOR_DIFF, basis)


def equity_spot_rho(bucket: int) -> float:
    """MAR21.78(2)(a)-(e)."""
    return p.EQUITY_INTRA_RHO[bucket]


def equity_delta_rho(a: _Factor, b: _Factor, bucket: int) -> float:
    """MAR21.78(1)-(4)."""
    n1, f1 = a.key
    n2, f2 = b.key
    if n1 == n2:
        return p.EQUITY_SPOT_REPO_SAME_NAME_RHO  # different factor type, same issuer
    base = equity_spot_rho(bucket)
    return base if f1 == f2 else base * p.EQUITY_SPOT_REPO_DIFF_NAME_FACTOR


def commodity_delta_rho(a: _Factor, b: _Factor, bucket: int) -> float:
    """MAR21.83: rho_cty x rho_tenor x rho_basis."""
    c1, t1, l1 = a.key
    c2, t2, l2 = b.key
    r_cty = 1.0 if c1 == c2 else p.COMMODITY_RHO_CTY[bucket]
    r_t = 1.0 if t1 == t2 else p.COMMODITY_RHO_TENOR_DIFF
    r_b = 1.0 if l1 == l2 else p.COMMODITY_RHO_BASIS_DIFF
    return r_cty * r_t * r_b


def delta_rho(rc: FRTBRiskClass, bucket: str, a: _Factor, b: _Factor) -> float:
    """Medium-scenario within-bucket delta correlation (MAR21.45-21.83)."""
    if rc is FRTBRiskClass.GIRR:
        return girr_delta_rho(a, b)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        rn, rt, rb = csr_rho_components(int(bucket), rc is FRTBRiskClass.CSR_SEC_CTP)
        n1, t1, c1 = a.key
        n2, t2, c2 = b.key
        return (1.0 if n1 == n2 else rn) * (1.0 if t1 == t2 else rt) * (1.0 if c1 == c2 else rb)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        n1, t1, c1 = a.key
        n2, t2, c2 = b.key
        return ((1.0 if n1 == n2 else p.SEC_RHO_TRANCHE_DIFF)
                * (1.0 if t1 == t2 else p.SEC_RHO_TENOR_DIFF)
                * (1.0 if c1 == c2 else p.SEC_RHO_BASIS_DIFF))
    if rc is FRTBRiskClass.EQUITY:
        return equity_delta_rho(a, b, int(bucket))
    if rc is FRTBRiskClass.COMMODITY:
        return commodity_delta_rho(a, b, int(bucket))
    return 1.0  # FX: one risk factor per bucket


def _vega_delta_component(rc: FRTBRiskClass, bucket: str, n1: object, n2: object) -> float:
    """rho_DELTA restricted to the vega dimensions (MAR21.94 and its FAQ1)."""
    if n1 == n2:
        return 1.0
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return csr_rho_components(int(bucket), rc is FRTBRiskClass.CSR_SEC_CTP)[0]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.SEC_RHO_TRANCHE_DIFF
    if rc is FRTBRiskClass.EQUITY:
        return equity_spot_rho(int(bucket))
    if rc is FRTBRiskClass.COMMODITY:
        return p.COMMODITY_RHO_CTY[int(bucket)]
    return 1.0


def vega_rho(rc: FRTBRiskClass, bucket: str, a: _Factor, b: _Factor) -> float:
    """MAR21.93 (GIRR) and MAR21.94 (other classes), medium scenario."""
    if rc is FRTBRiskClass.GIRR:
        # key = (type, curve, option maturity, underlying maturity or None); inflation and
        # xccy vega have no underlying dimension (MAR21.8 FAQ4) -> rho_underlying = 1.
        r_opt = _maturity_rho(a.key[2], b.key[2])  # type: ignore[arg-type]
        r_und = _maturity_rho(a.key[3], b.key[3])  # type: ignore[arg-type]
        return min(r_opt * r_und, 1.0)
    n1, o1 = a.key
    n2, o2 = b.key
    r_delta = _vega_delta_component(rc, bucket, n1, n2)
    return min(r_delta * _maturity_rho(o1, o2), 1.0)  # type: ignore[arg-type]


def curvature_rho(rc: FRTBRiskClass, bucket: str, a: _Factor, b: _Factor) -> float:
    """MAR21.100: square of the delta correlation on the curvature dimensions only."""
    if rc in (FRTBRiskClass.GIRR, FRTBRiskClass.FX):
        return 1.0  # one curvature risk factor per bucket
    base = _vega_delta_component(rc, bucket, a.key[0], b.key[0])
    return base ** p.CURVATURE_CORRELATION_POWER


def gamma(rc: FRTBRiskClass, b: str, c: str) -> float:
    """Medium-scenario across-bucket gamma_bc.

    MAR21.50, 21.57, 21.61, 21.70, 21.80, 21.85, 21.89.
    """
    if rc is FRTBRiskClass.GIRR:
        return p.GIRR_GAMMA
    if rc is FRTBRiskClass.FX:
        return p.FX_GAMMA
    bi, ci = int(b), int(c)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return csr_gamma(bi, ci)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.SEC_GAMMA
    if rc is FRTBRiskClass.EQUITY:
        return equity_gamma(bi, ci)
    if p.COMMODITY_OTHER_BUCKET in (bi, ci):
        return p.COMMODITY_GAMMA_OTHER
    return p.COMMODITY_GAMMA_1_10


def _csr_sector_group(bucket: int) -> int:
    """Table 5 sector group: 1/9 -> 1, ..., 7/15 -> 7; 8, 16, 17, 18 unchanged."""
    return bucket - 8 if 9 <= bucket <= 15 else bucket


def csr_gamma(b: int, c: int) -> float:
    """MAR21.57: gamma = gamma_rating x gamma_sector (Table 5)."""
    rating = 1.0
    if b <= 15 and c <= 15 and ((b <= 8) != (c <= 8)):
        rating = p.CSR_GAMMA_RATING_DIFF
    gb, gc = _csr_sector_group(b), _csr_sector_group(c)
    sector = 1.0 if gb == gc else p.CSR_GAMMA_SECTOR[(gb, gc)]
    return rating * sector


def equity_gamma(b: int, c: int) -> float:
    """MAR21.80."""
    if p.EQUITY_OTHER_BUCKET in (b, c):
        return p.EQUITY_GAMMA_OTHER_BUCKET
    if b <= 10 and c <= 10:
        return p.EQUITY_GAMMA_1_10
    if {b, c} == {p.EQUITY_LARGE_AE_INDEX_BUCKET, p.EQUITY_OTHER_INDEX_BUCKET}:
        return p.EQUITY_GAMMA_INDEX_PAIR
    return p.EQUITY_GAMMA_DEFAULT


# =========================================================================
#  Aggregation
# =========================================================================

_RhoFn = Callable[[FRTBRiskClass, str, _Factor, _Factor], float]


def within_bucket_k(ws: list[float], rho: Callable[[int, int], float]) -> float:
    """K_b = sqrt(max(0, sum WS_k^2 + sum_k sum_{l != k} rho_kl WS_k WS_l)) (MAR21.4(4))."""
    total = sum(w * w for w in ws)
    n = len(ws)
    for i in range(n):
        for j in range(n):
            if i != j:
                total += rho(i, j) * ws[i] * ws[j]
    return math.sqrt(max(0.0, total))


def across_buckets(k: list[float], s: list[float], gam: Callable[[int, int], float]) -> float:
    """Delta / vega across buckets with the MAR21.4(5)(b) alternative specification.

    The result is floored at zero under the root (a negative sum can remain after
    the alternative specification with more than two buckets; the text gives no
    further fallback).
    """
    def total(sb: list[float]) -> float:
        out = sum(x * x for x in k)
        for i in range(len(k)):
            for j in range(len(k)):
                if i != j:
                    out += gam(i, j) * sb[i] * sb[j]
        return out

    t = total(s)
    if t < 0.0:
        alt = [max(min(s_b, k_b), -k_b) for s_b, k_b in zip(s, k, strict=True)]
        t = total(alt)
    return math.sqrt(max(0.0, t))


def _psi(x: float, y: float) -> float:
    """psi = 0 if both arguments are negative, 1 otherwise (MAR21.5(3)(b), 21.5(4)(b))."""
    return 0.0 if (x < 0.0 and y < 0.0) else 1.0


def curvature_bucket(cvr_up: list[float], cvr_down: list[float],
                     rho: Callable[[int, int], float]) -> tuple[float, float, bool]:
    """(K_b, S_b, upward_selected) per MAR21.5(3)-(4) (formulas from pp. 572-573).

    K_b+/- = sqrt(max(0, sum_k max(CVR_k, 0)^2 + sum_{l != k} rho CVR_k CVR_l psi(CVR_k, CVR_l))).
    K_b = max(K_b+, K_b-); on a tie the upward scenario is selected when
    sum CVR+ > sum CVR-, otherwise the downward one. S_b = sum of the selected CVRs.
    """
    def k_of(cvr: list[float]) -> float:
        t = sum(max(c, 0.0) ** 2 for c in cvr)
        n = len(cvr)
        for i in range(n):
            for j in range(n):
                if i != j:
                    t += rho(i, j) * cvr[i] * cvr[j] * _psi(cvr[i], cvr[j])
        return math.sqrt(max(0.0, t))

    kp, km = k_of(cvr_up), k_of(cvr_down)
    sp, sm = sum(cvr_up), sum(cvr_down)
    up = kp > km or (kp == km and sp > sm)
    return (kp if up else km), (sp if up else sm), up


def curvature_other_bucket(cvr_up: list[float], cvr_down: list[float]) -> tuple[float, float]:
    """Other-sector buckets: K_b = max(sum max(CVR+, 0), sum max(CVR-, 0)) (MAR21.56(2) etc.).

    Returns (K_b, S_b) with S_b the sum of the selected scenario's CVRs.
    """
    kp = sum(max(c, 0.0) for c in cvr_up)
    km = sum(max(c, 0.0) for c in cvr_down)
    sp, sm = sum(cvr_up), sum(cvr_down)
    up = kp > km or (kp == km and sp > sm)
    return (kp if up else km), (sp if up else sm)


def curvature_across(k: list[float], s: list[float], gam: Callable[[int, int], float]) -> float:
    """sqrt(max(0, sum K_b^2 + sum_{c != b} gamma_bc S_b S_c psi(S_b, S_c))) (MAR21.5(4))."""
    t = sum(x * x for x in k)
    for i in range(len(k)):
        for j in range(len(k)):
            if i != j:
                t += gam(i, j) * s[i] * s[j] * _psi(s[i], s[j])
    return math.sqrt(max(0.0, t))


# =========================================================================
#  Grouping
# =========================================================================


def _group(sens: Iterable[FRTBSensitivity], measure: FRTBMeasure,
           options: p.BCBSFRTBOptions) -> dict[str, dict[tuple[object, ...], _Factor]]:
    """Bucket -> netted factors for one risk class and measure."""
    out: dict[str, dict[tuple[object, ...], _Factor]] = {}
    for s in sens:
        bucket = bk.assign_bucket(s)
        if measure is FRTBMeasure.DELTA:
            key = delta_factor_key(s, options)
        elif measure is FRTBMeasure.VEGA:
            key = vega_factor_key(s)
        else:
            key = curvature_factor_key(s)
        f = out.setdefault(bucket, {}).setdefault(key, _Factor(key=key, rep=s))
        if measure is FRTBMeasure.CURVATURE:
            up = s.cvr_up or 0.0
            dn = s.cvr_down or 0.0
            if s.risk_class is FRTBRiskClass.FX and s.flags.get(FX_CURVATURE_FLAG, False):
                up /= p.FX_CURVATURE_NON_REPORTING_SCALAR
                dn /= p.FX_CURVATURE_NON_REPORTING_SCALAR
            f.cvr_up += up
            f.cvr_down += dn
        else:
            f.ws += bk.weighted_sensitivity(s, options)
    return out


def _sort_buckets(rc: FRTBRiskClass, names: Iterable[str]) -> list[str]:
    """Deterministic bucket order (numeric where MAR21 numbers the buckets)."""
    if rc in (FRTBRiskClass.GIRR, FRTBRiskClass.FX):
        return sorted(names)
    return sorted(names, key=int)


def _split_sec25(rc: FRTBRiskClass, names: list[str]) -> tuple[list[str], list[str]]:
    """MAR21.71: bucket 25 is summed outside the root for non-CTP securitisations."""
    if rc is not FRTBRiskClass.CSR_SEC_NONCTP:
        return names, []
    other = str(p.SEC_OTHER_BUCKET)
    return [n for n in names if n != other], [n for n in names if n == other]


def delta_vega_capital(rc: FRTBRiskClass, groups: dict[str, dict[tuple[object, ...], _Factor]],
                       measure: FRTBMeasure, scenario: str) -> float:
    """Delta or vega capital for one risk class under one scenario (MAR21.4, MAR21.6)."""
    rho_fn: _RhoFn = delta_rho if measure is FRTBMeasure.DELTA else vega_rho
    names = _sort_buckets(rc, groups)
    inner, outer = _split_sec25(rc, names)
    k_list: list[float] = []
    s_list: list[float] = []
    for b in inner:
        facs = list(groups[b].values())
        ws = [f.ws for f in facs]
        if bk.is_other_bucket(rc, b):
            k_b = sum(abs(w) for w in ws)  # MAR21.56(1) / 21.69(1) / 21.79(1)
        else:
            def rho(i: int, j: int, _f: list[_Factor] = facs, _b: str = b) -> float:
                return scenario_correlation(rho_fn(rc, _b, _f[i], _f[j]), scenario)
            k_b = within_bucket_k(ws, rho)
        k_list.append(k_b)
        s_list.append(sum(ws))

    def gam(i: int, j: int) -> float:
        return scenario_correlation(gamma(rc, inner[i], inner[j]), scenario)

    total = across_buckets(k_list, s_list, gam) if k_list else 0.0
    for b in outer:
        total += sum(abs(f.ws) for f in groups[b].values())  # MAR21.69(1), 21.71
    return total


def curvature_capital(rc: FRTBRiskClass, groups: dict[str, dict[tuple[object, ...], _Factor]],
                      scenario: str) -> float:
    """Curvature capital for one risk class under one scenario (MAR21.5, 21.100-21.101)."""
    names = _sort_buckets(rc, groups)
    inner, outer = _split_sec25(rc, names)
    k_list: list[float] = []
    s_list: list[float] = []
    for b in inner:
        facs = list(groups[b].values())
        up = [f.cvr_up for f in facs]
        dn = [f.cvr_down for f in facs]
        if bk.is_other_bucket(rc, b):
            k_b, s_b = curvature_other_bucket(up, dn)
        else:
            def rho(i: int, j: int, _f: list[_Factor] = facs, _b: str = b) -> float:
                return scenario_correlation(curvature_rho(rc, _b, _f[i], _f[j]), scenario)
            k_b, s_b, _ = curvature_bucket(up, dn, rho)
        k_list.append(k_b)
        s_list.append(s_b)

    def gam(i: int, j: int) -> float:
        g = gamma(rc, inner[i], inner[j]) ** p.CURVATURE_CORRELATION_POWER
        return scenario_correlation(g, scenario)

    total = curvature_across(k_list, s_list, gam) if k_list else 0.0
    for b in outer:
        facs = list(groups[b].values())
        total += curvature_other_bucket([f.cvr_up for f in facs], [f.cvr_down for f in facs])[0]
    return total


@dataclass
class SBMScenarioResult:
    """Per-scenario, per-class capital (delta, vega, curvature)."""

    scenario: str
    by_class: dict[FRTBRiskClass, tuple[float, float, float]]

    @property
    def total(self) -> float:
        """MAR21.7(1): simple sum across measures and risk classes."""
        return sum(d + v + c for d, v, c in self.by_class.values())


def sbm_scenarios(sensitivities: list[FRTBSensitivity],
                  options: p.BCBSFRTBOptions) -> list[SBMScenarioResult]:
    """Delta, vega and curvature for every risk class under the three scenarios (MAR21.6)."""
    classes = [rc for rc in RISK_CLASS_ORDER
               if any(s.risk_class is rc for s in sensitivities)]
    grouped: dict[tuple[FRTBRiskClass, FRTBMeasure], dict[str, dict[tuple[object, ...],
                                                                    _Factor]]] = {}
    for rc in classes:
        for m in FRTBMeasure:
            sel = [s for s in sensitivities if s.risk_class is rc and s.measure is m]
            grouped[(rc, m)] = _group(sel, m, options) if sel else {}
    results: list[SBMScenarioResult] = []
    for sc in p.SCENARIOS:
        by_class: dict[FRTBRiskClass, tuple[float, float, float]] = {}
        for rc in classes:
            d = delta_vega_capital(rc, grouped[(rc, FRTBMeasure.DELTA)], FRTBMeasure.DELTA, sc)
            v = delta_vega_capital(rc, grouped[(rc, FRTBMeasure.VEGA)], FRTBMeasure.VEGA, sc)
            c = curvature_capital(rc, grouped[(rc, FRTBMeasure.CURVATURE)], sc)
            by_class[rc] = (d, v, c)
        results.append(SBMScenarioResult(scenario=sc, by_class=by_class))
    return results


def binding_scenario(results: list[SBMScenarioResult]) -> SBMScenarioResult:
    """MAR21.7(2): the largest of the three scenario totals (ties: first in LOW, MEDIUM, HIGH)."""
    return max(results, key=lambda r: r.total)


def sbm_capital(sensitivities: list[FRTBSensitivity],
                options: p.BCBSFRTBOptions) -> list[SBMClassResult]:
    """SBM by risk class under the binding (portfolio-level) scenario (MAR21.7)."""
    if not sensitivities:
        return []
    best = binding_scenario(sbm_scenarios(sensitivities, options))
    return [SBMClassResult(risk_class=rc, delta=d, vega=v, curvature=c, total=d + v + c,
                           scenario=best.scenario)
            for rc, (d, v, c) in best.by_class.items()]


__all__ = [
    "SBMScenarioResult",
    "across_buckets",
    "binding_scenario",
    "csr_gamma",
    "curvature_across",
    "curvature_bucket",
    "curvature_other_bucket",
    "delta_factor_key",
    "equity_gamma",
    "gamma",
    "girr_tenor_rho",
    "sbm_capital",
    "sbm_scenarios",
    "scenario_correlation",
    "within_bucket_k",
]
