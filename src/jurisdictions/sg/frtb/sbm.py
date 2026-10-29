"""Sensitivities-based method under MAS Notice 637 Part VIII Division 2 (paras 8.2.2-8.2.157).

For each of the seven risk classes (para 8.2.8):

    - delta and vega (paras 8.2.10-8.2.11): net sensitivity per risk factor, WS_k = RW_k s_k,
      K_b = sqrt(max(0, sum_k WS_k^2 + sum_k sum_{l != k} rho_kl WS_k WS_l)), across buckets
      sqrt(sum_b K_b^2 + sum_b sum_{c != b} gamma_bc S_b S_c) with S_b = sum_k WS_k, and the
      alternative S_b = max[min(sum_k WS_k, K_b), -K_b] when the sum under the root is
      negative (paras 8.2.10(g), 8.2.11(g));
    - curvature (para 8.2.12): K_b+/- with the psi function, K_b = max(K_b+, K_b-) and the
      tie rule of para 8.2.12(d)(i), S_b = sum of the selected CVRs, across buckets
      sqrt(max(0, sum K_b^2 + sum gamma_bc S_b S_c psi(S_b, S_c))) (para 8.2.12(e));
    - "Other sector" buckets: sum of |WS| (paras 8.2.110, 8.2.117, 8.2.124, 8.2.132, 8.2.148)
      and max(sum max(CVR+, 0), sum max(CVR-, 0)) for curvature (para 8.2.156); CSR
      securitisation non-CTP bucket 25 added outside the root (paras 8.2.125(b), 8.2.149(b));
    - correlation scenarios (para 8.2.14): medium as specified, high min(1.25 x, 100%), low
      max(2 x - 100%, 75% x), applied to rho and gamma (curvature: to the squared values,
      paras 8.2.154-8.2.157); SBM = largest scenario aggregate over all risk classes (para
      8.2.8(f)).

The aggregation algebra (within-bucket K_b, across-bucket with the alternative S_b, curvature
psi / tie rule) is the MAR21.4-21.5 algebra that MAS transposes verbatim, so it is imported from
the BCBS engine (:mod:`src.jurisdictions.bcbs.frtb.sbm`); every correlation, gamma, bucket and
risk weight comes from :mod:`src.jurisdictions.sg.frtb.params`.

Documented ``flags`` keys on :class:`FRTBSensitivity`:
    - ``fx_curvature_scalar_1_5``: FX curvature instrument that does not reference the reporting
      currency; CVR+ and CVR- are divided by 1.5 (para 8.2.152(a)).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from src.jurisdictions.bcbs.frtb.sbm import (
    SBMScenarioResult,
    across_buckets,
    binding_scenario,
    curvature_across,
    curvature_bucket,
    curvature_other_bucket,
    within_bucket_k,
)
from src.jurisdictions.frtb_base import (
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
    SBMClassResult,
)
from src.jurisdictions.sg.frtb import buckets as bk
from src.jurisdictions.sg.frtb import params as p

FX_CURVATURE_FLAG = "fx_curvature_scalar_1_5"
"""Flag on an FX curvature sensitivity: divide CVR+/- by 1.5 (para 8.2.152(a))."""

RISK_CLASS_ORDER: tuple[FRTBRiskClass, ...] = (
    FRTBRiskClass.GIRR,
    FRTBRiskClass.CSR_NONSEC,
    FRTBRiskClass.CSR_SEC_NONCTP,
    FRTBRiskClass.CSR_SEC_CTP,
    FRTBRiskClass.EQUITY,
    FRTBRiskClass.COMMODITY,
    FRTBRiskClass.FX,
)
"""The seven SBM risk classes (para 8.2.8; MAS 637 Part II "risk class")."""

Key = tuple[object, ...]


# =========================================================================
#  Scenarios (para 8.2.14)
# =========================================================================


def scenario_correlation(value: float, scenario: str) -> float:
    """Apply a para 8.2.14 correlation scenario to one rho or gamma.

    MEDIUM: as specified (a). HIGH: x 1.25 capped at 100% (b). LOW: max(2 x value - 100%;
    75% x value) (c).
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
#  Risk factors (Sub-division 3, paras 8.2.15-8.2.54)
# =========================================================================


@dataclass
class _Factor:
    """A netted risk factor within a bucket (paras 8.2.10(b), 8.2.11(b))."""

    key: Key
    ws: float = 0.0
    cvr_up: float = 0.0
    cvr_down: float = 0.0


def _name(s: FRTBSensitivity) -> str:
    """Issuer / name key: ``issuer`` then ``label``."""
    return s.issuer or s.label


def _tranche(s: FRTBSensitivity) -> str:
    """Securitisation tranche key (para 8.2.123(a)): ``tranche_id`` then ``label``."""
    return s.tranche_id or s.label


def _commodity(s: FRTBSensitivity) -> str:
    """Commodity key (para 8.2.135(a)): ``commodity_name`` then ``label``."""
    return s.commodity_name or s.label


def delta_factor_key(s: FRTBSensitivity, options: p.SGFRTBOptions) -> Key:
    """Delta risk-factor identity (paras 8.2.16, 8.2.30, 8.2.33, 8.2.36, 8.2.39, 8.2.42,
    8.2.48); equal keys are netted (para 8.2.10(b))."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is GIRRCurve.INFLATION:
            return ("INFLATION", s.curve_name)  # flat curve, para 8.2.16(b)
        if s.girr_curve is GIRRCurve.XCCY_BASIS:
            curve = "" if options.xccy_onshore_offshore_simple_sum else s.curve_name
            return ("XCCY", curve)  # flat curve, para 8.2.16(c); 8.2.96 simple-sum option
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


def _vega_option_tenor(s: FRTBSensitivity) -> float:
    """Option maturity on the vega grid; options without a maturity -> 10 years (para 8.2.70)."""
    t = s.option_maturity_years
    return bk.snap_tenor(p.VEGA_NO_MATURITY_TENOR if t is None else t, p.VEGA_TENORS,
                         "vega option maturity")


def vega_factor_key(s: FRTBSensitivity) -> Key:
    """Vega risk-factor identity (paras 8.2.23-8.2.25, 8.2.31, 8.2.34, 8.2.37, 8.2.40, 8.2.45,
    8.2.51)."""
    opt = _vega_option_tenor(s)
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is not GIRRCurve.RISK_FREE:
            # paras 8.2.24-8.2.25: inflation / xccy vega along option maturity only
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


def curvature_factor_key(s: FRTBSensitivity) -> Key:
    """Curvature risk-factor identity (paras 8.2.27, 8.2.29, 8.2.32, 8.2.35, 8.2.38, 8.2.41,
    8.2.46, 8.2.52).

    GIRR: all risk-free curves of a currency are one factor (para 8.2.27); no curvature for
    inflation or cross-currency basis (para 8.2.29); no equity repo curvature (para 8.2.41).
    """
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        if s.girr_curve is not GIRRCurve.RISK_FREE:
            raise ValueError("no GIRR curvature for inflation / cross-currency basis "
                             "(MAS 637 para 8.2.29)")
        return (bk.girr_bucket(s),)
    if rc is FRTBRiskClass.EQUITY:
        if s.equity_risk_factor is EquityRiskFactor.REPO:
            raise ValueError("no curvature for equity repo rates (MAS 637 para 8.2.41)")
        return (_name(s),)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return (_name(s),)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return (_tranche(s),)
    if rc is FRTBRiskClass.COMMODITY:
        return (_commodity(s),)
    return (bk.fx_bucket(s),)


# =========================================================================
#  Medium-scenario correlations
# =========================================================================


def girr_tenor_rho(t1: float, t2: float) -> float:
    """Table 8-2 lookup."""
    return p.GIRR_TENOR_CORRELATION[p.GIRR_TENORS.index(t1)][p.GIRR_TENORS.index(t2)]


def girr_tenor_rho_formula(t1: float, t2: float) -> float:
    """Para 8.2.93 fn 657: max(exp(-theta |T_k - T_l| / min(T_k, T_l)); 40%), theta = 3%."""
    return max(math.exp(-p.GIRR_TENOR_THETA * abs(t1 - t2) / min(t1, t2)),
               p.GIRR_TENOR_RHO_FLOOR)


def girr_delta_rho(ka: Key, kb: Key) -> float:
    """Paras 8.2.93-8.2.98: within-bucket GIRR delta correlation."""
    xa, xb = ka[0] == "XCCY", kb[0] == "XCCY"
    if xa and xb:
        return p.GIRR_XCCY_DIFF_CURVE_RHO  # 8.2.95 (TODO: VERIFY vs 8.2.98(c))
    if xa or xb:
        return p.GIRR_XCCY_VS_OTHER_RHO  # 8.2.98(a)-(b)
    ia, ib = ka[0] == "INFLATION", kb[0] == "INFLATION"
    if ia and ib:
        return p.GIRR_INFLATION_DIFF_CURVE_RHO  # 8.2.94(b)
    if ia or ib:
        return p.GIRR_INFLATION_VS_YIELD_RHO  # 8.2.97
    _, c1, t1 = ka
    _, c2, t2 = kb
    assert isinstance(t1, float) and isinstance(t2, float)
    if c1 == c2:
        return girr_tenor_rho(t1, t2)  # 8.2.93(b)
    if t1 == t2:
        return p.GIRR_SAME_TENOR_DIFF_CURVE_RHO  # 8.2.93(a)
    return girr_tenor_rho(t1, t2) * p.GIRR_DIFF_CURVE_FACTOR  # 8.2.93(c)


def csr_rho_components(bucket: int, ctp: bool) -> tuple[float, float, float]:
    """(rho_name, rho_tenor, rho_basis) for differing name / tenor / curve.

    Paras 8.2.108 (buckets 1-15), 8.2.109 (17-18), 8.2.116 (CTP, basis 99.00%).
    """
    if not ctp and bucket in (p.CSR_HIGH_QUALITY_INDEX_BUCKET, p.CSR_LOW_QUALITY_INDEX_BUCKET):
        return (p.CSR_INDEX_RHO_NAME_DIFF, p.CSR_INDEX_RHO_TENOR_DIFF, p.CSR_INDEX_RHO_BASIS_DIFF)
    basis = p.CSR_CTP_RHO_BASIS_DIFF if ctp else p.CSR_RHO_BASIS_DIFF
    return (p.CSR_RHO_NAME_DIFF, p.CSR_RHO_TENOR_DIFF, basis)


def _prod3(ka: Key, kb: Key, diff: tuple[float, float, float]) -> float:
    """rho = rho_1 x rho_2 x rho_3 with each factor 1 when the dimension agrees."""
    out = 1.0
    for x, y, r in zip(ka, kb, diff, strict=True):
        out *= 1.0 if x == y else r
    return out


def delta_rho(rc: FRTBRiskClass, bucket: str, ka: Key, kb: Key) -> float:
    """Medium-scenario within-bucket delta correlation (paras 8.2.93-8.2.135)."""
    if rc is FRTBRiskClass.GIRR:
        return girr_delta_rho(ka, kb)
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return _prod3(ka, kb, csr_rho_components(int(bucket), rc is FRTBRiskClass.CSR_SEC_CTP))
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return _prod3(ka, kb, (p.SEC_RHO_TRANCHE_DIFF, p.SEC_RHO_TENOR_DIFF,
                               p.SEC_RHO_BASIS_DIFF))  # 8.2.123
    if rc is FRTBRiskClass.EQUITY:
        (n1, f1), (n2, f2) = ka, kb
        if n1 == n2:
            return p.EQUITY_SPOT_REPO_SAME_NAME_RHO  # 8.2.131(a)
        base = p.EQUITY_INTRA_RHO[int(bucket)]  # 8.2.131(b)-(c)
        return base if f1 == f2 else base * p.EQUITY_SPOT_REPO_DIFF_NAME_FACTOR  # (d)
    if rc is FRTBRiskClass.COMMODITY:
        return _prod3(ka, kb, (p.COMMODITY_RHO_CTY[int(bucket)], p.COMMODITY_RHO_TENOR_DIFF,
                               p.COMMODITY_RHO_BASIS_DIFF))  # 8.2.135
    return 1.0  # FX: one risk factor per bucket


def shared_dimension_rho(rc: FRTBRiskClass, bucket: str, n1: object, n2: object) -> float:
    """rho restricted to the dimension shared by delta and vega / curvature factors.

    Para 8.2.147 (vega) and para 8.2.155 (curvature): CSR -> rho_name, sec non-CTP ->
    rho_tranche, commodity -> rho_cty; equity -> the para 8.2.131(b) spot correlation.
    """
    if n1 == n2:
        return 1.0
    if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return csr_rho_components(int(bucket), rc is FRTBRiskClass.CSR_SEC_CTP)[0]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.SEC_RHO_TRANCHE_DIFF
    if rc is FRTBRiskClass.EQUITY:
        return p.EQUITY_INTRA_RHO[int(bucket)]
    if rc is FRTBRiskClass.COMMODITY:
        return p.COMMODITY_RHO_CTY[int(bucket)]
    return 1.0


def _maturity_rho(t1: float | None, t2: float | None) -> float:
    """exp(-alpha |T_k - T_l| / min(T_k, T_l)), alpha = 1% (para 8.2.145)."""
    if t1 is None or t2 is None:
        return 1.0
    return math.exp(-p.VEGA_ALPHA * abs(t1 - t2) / min(t1, t2))


def vega_rho(rc: FRTBRiskClass, bucket: str, ka: Key, kb: Key) -> float:
    """Para 8.2.145 (GIRR) and para 8.2.146 (other classes), medium scenario."""
    if rc is FRTBRiskClass.GIRR:
        r_opt = _maturity_rho(ka[2], kb[2])  # type: ignore[arg-type]
        r_und = _maturity_rho(ka[3], kb[3])  # type: ignore[arg-type]
        return min(r_opt * r_und, 1.0)
    (n1, o1), (n2, o2) = ka, kb
    r_delta = shared_dimension_rho(rc, bucket, n1, n2)
    return min(r_delta * _maturity_rho(o1, o2), 1.0)  # type: ignore[arg-type]


def curvature_rho(rc: FRTBRiskClass, bucket: str, ka: Key, kb: Key) -> float:
    """Paras 8.2.154-8.2.155: square of the delta correlation on the shared dimension."""
    if rc in (FRTBRiskClass.GIRR, FRTBRiskClass.FX):
        return 1.0  # one curvature factor per bucket
    return shared_dimension_rho(rc, bucket, ka[0], kb[0]) ** p.CURVATURE_CORRELATION_POWER


def _csr_sector_group(bucket: int) -> int:
    """Table 8-5 grouping: 1/9 -> 1, ..., 7/15 -> 7; 8, 16, 17, 18 unchanged."""
    lo = p.CSR_LOW_QUALITY_OFFSET
    return bucket - lo if lo < bucket <= lo + 7 else bucket


def csr_gamma(b: int, c: int) -> float:
    """Para 8.2.111: gamma = gamma_rating x gamma_sector (Table 8-5); para 8.2.112."""
    rating = 1.0
    last = p.CSR_OTHER_BUCKET - 1
    if b <= last and c <= last and ((b <= p.CSR_LOW_QUALITY_OFFSET)
                                    != (c <= p.CSR_LOW_QUALITY_OFFSET)):
        rating = p.CSR_GAMMA_RATING_DIFF
    gb, gc = _csr_sector_group(b), _csr_sector_group(c)
    return rating * (1.0 if gb == gc else p.CSR_GAMMA_SECTOR[(gb, gc)])


def equity_gamma(b: int, c: int) -> float:
    """Para 8.2.133(a)-(d)."""
    if p.EQUITY_OTHER_BUCKET in (b, c):
        return p.EQUITY_GAMMA_OTHER_BUCKET
    if b <= p.EQUITY_LAST_SECTOR_BUCKET and c <= p.EQUITY_LAST_SECTOR_BUCKET:
        return p.EQUITY_GAMMA_1_10
    if {b, c} == {p.EQUITY_LARGE_AE_INDEX_BUCKET, p.EQUITY_OTHER_INDEX_BUCKET}:
        return p.EQUITY_GAMMA_INDEX_PAIR
    return p.EQUITY_GAMMA_DEFAULT


def gamma(rc: FRTBRiskClass, b: str, c: str) -> float:
    """Medium-scenario gamma_bc (paras 8.2.99, 8.2.111, 8.2.118, 8.2.125(a), 8.2.133, 8.2.137,
    8.2.141; vega: para 8.2.149(a))."""
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


# =========================================================================
#  Grouping and aggregation
# =========================================================================

Groups = dict[str, dict[Key, _Factor]]
_RhoFn = Callable[[FRTBRiskClass, str, Key, Key], float]


def _group(sens: Iterable[FRTBSensitivity], measure: FRTBMeasure,
           options: p.SGFRTBOptions) -> Groups:
    """Bucket -> netted factors for one risk class and measure."""
    out: Groups = {}
    for s in sens:
        bucket = bk.assign_bucket(s)
        if measure is FRTBMeasure.DELTA:
            key = delta_factor_key(s, options)
        elif measure is FRTBMeasure.VEGA:
            key = vega_factor_key(s)
        else:
            key = curvature_factor_key(s)
        f = out.setdefault(bucket, {}).setdefault(key, _Factor(key=key))
        if measure is FRTBMeasure.CURVATURE:
            up, dn = s.cvr_up or 0.0, s.cvr_down or 0.0
            if s.risk_class is FRTBRiskClass.FX and (
                    options.fx_curvature_all_div_1_5 or s.flags.get(FX_CURVATURE_FLAG, False)):
                up /= p.FX_CURVATURE_NON_REPORTING_SCALAR
                dn /= p.FX_CURVATURE_NON_REPORTING_SCALAR
            f.cvr_up += up
            f.cvr_down += dn
        else:
            f.ws += bk.weighted_sensitivity(s, options)
    return out


def _sorted_split(rc: FRTBRiskClass, names: Iterable[str]) -> tuple[list[str], list[str]]:
    """Deterministic bucket order; split off sec non-CTP bucket 25 (para 8.2.125(b))."""
    ordered = sorted(names) if rc in (FRTBRiskClass.GIRR, FRTBRiskClass.FX) else sorted(
        names, key=int)
    if rc is not FRTBRiskClass.CSR_SEC_NONCTP:
        return ordered, []
    other = str(p.SEC_OTHER_BUCKET)
    return [n for n in ordered if n != other], [n for n in ordered if n == other]


def delta_vega_capital(rc: FRTBRiskClass, groups: Groups, measure: FRTBMeasure,
                       scenario: str) -> float:
    """Delta (para 8.2.10) or vega (para 8.2.11) capital for one class under one scenario."""
    rho_fn: _RhoFn = delta_rho if measure is FRTBMeasure.DELTA else vega_rho
    inner, outer = _sorted_split(rc, groups)
    k_list: list[float] = []
    s_list: list[float] = []
    for b in inner:
        facs = list(groups[b].values())
        ws = [f.ws for f in facs]
        if bk.is_other_bucket(rc, b):
            k_b = sum(abs(w) for w in ws)
        else:
            def rho(i: int, j: int, _f: list[_Factor] = facs, _b: str = b) -> float:
                return scenario_correlation(rho_fn(rc, _b, _f[i].key, _f[j].key), scenario)
            k_b = within_bucket_k(ws, rho)
        k_list.append(k_b)
        s_list.append(sum(ws))

    def gam(i: int, j: int) -> float:
        return scenario_correlation(gamma(rc, inner[i], inner[j]), scenario)

    total = across_buckets(k_list, s_list, gam) if k_list else 0.0
    for b in outer:
        total += sum(abs(f.ws) for f in groups[b].values())
    return total


def curvature_capital(rc: FRTBRiskClass, groups: Groups, scenario: str) -> float:
    """Curvature capital for one class under one scenario (paras 8.2.12, 8.2.154-8.2.157)."""
    inner, outer = _sorted_split(rc, groups)
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
                return scenario_correlation(curvature_rho(rc, _b, _f[i].key, _f[j].key),
                                            scenario)
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


def sbm_scenarios(sensitivities: list[FRTBSensitivity],
                  options: p.SGFRTBOptions) -> list[SBMScenarioResult]:
    """Delta, vega and curvature for every risk class under the 3 scenarios (para 8.2.14)."""
    classes = [rc for rc in RISK_CLASS_ORDER if any(s.risk_class is rc for s in sensitivities)]
    grouped: dict[tuple[FRTBRiskClass, FRTBMeasure], Groups] = {}
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


def sbm_capital(sensitivities: list[FRTBSensitivity],
                options: p.SGFRTBOptions) -> list[SBMClassResult]:
    """SBM by risk class under the binding scenario (para 8.2.8(f): largest aggregate)."""
    if not sensitivities:
        return []
    best = binding_scenario(sbm_scenarios(sensitivities, options))
    return [SBMClassResult(risk_class=rc, delta=d, vega=v, curvature=c, total=d + v + c,
                           scenario=best.scenario)
            for rc, (d, v, c) in best.by_class.items()]


__all__ = [
    "FX_CURVATURE_FLAG",
    "SBMScenarioResult",
    "binding_scenario",
    "csr_gamma",
    "curvature_capital",
    "curvature_rho",
    "delta_factor_key",
    "delta_rho",
    "delta_vega_capital",
    "equity_gamma",
    "gamma",
    "girr_delta_rho",
    "girr_tenor_rho",
    "girr_tenor_rho_formula",
    "sbm_capital",
    "sbm_scenarios",
    "scenario_correlation",
    "vega_rho",
]
