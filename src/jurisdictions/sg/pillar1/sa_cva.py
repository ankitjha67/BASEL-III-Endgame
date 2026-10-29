"""SA-CVA under MAS Notice 637 Part VIII Division 5 Sub-division 3.

K_SA-CVA = sum over risk classes of K_delta + K_vega (para 8.5.29), each computed by
(para 8.5.32, pp. 8-195 to 8-197):

    WS_k = RW_k s_k^CVA - RW_k s_k^Hdg
    K_b  = sqrt( (sum_k WS_k^2 + sum_k sum_{l != k} rho_kl WS_k WS_l) + R sum_k (WS_k^Hdg)^2 )
    K    = m_CVA sqrt( sum_b K_b^2 + sum_b sum_{c != b} gamma_bc S_b S_c ),
    S_b  = max(-K_b, min(sum_k WS_k, K_b)),

with R = 0.01 and m_CVA = 1. CVA RWA = 12.5 x K (para 8.5.1). Counterparty credit spread has
no vega (para 8.5.30).

Input conventions (:class:`CVASensitivityInput`):

- INTEREST_RATE: ``bucket`` = ISO currency. Delta ``risk_factor`` in 1Y / 2Y / 5Y / 10Y / 30Y /
  INFLATION for the reporting currency (SGD) and USD, EUR, GBP, AUD, CAD, SEK, JPY (8.5.36);
  CURVE / INFLATION for any other currency (8.5.37). Vega ``risk_factor`` RATE_VOL or
  INFLATION_VOL (8.5.38).
- FX: ``bucket`` = ISO currency other than the reporting currency (8.5.40).
- COUNTERPARTY_CREDIT_SPREAD: ``bucket`` in 1a, 1b, 2-8 (Tables 8-30 / 8-31; 1a and 1b form
  bucket 1 for aggregation, Table 8-32); ``risk_factor`` = tenor 0.5Y / 1Y / 3Y / 5Y / 10Y;
  ``name`` = entity (bucket 8: index) written ``"GROUP|ENTITY"`` -- the same prefix before
  ``|`` marks parent / subsidiary / common-parent entities (rho_name 90%) or, in bucket 8, the
  same index of a different series (90%); ``is_investment_grade`` True = grade "3" or better
  (None = not rated).
- REFERENCE_CREDIT_SPREAD: ``bucket`` 1-17 (Table 8-33); one risk factor per bucket.
- EQUITY: ``bucket`` 1-13 (Table 8-36); one risk factor per bucket.
- COMMODITY: ``bucket`` 1-11 (Table 8-38); one risk factor per bucket.

References:
    - MAS Notice 637 paras 8.5.1, 8.5.29-8.5.73, Tables 8-28 to 8-39 (pp. 8-178, 8-194 to
      8-227)
    - Basel Framework MAR50.42-50.77 (comparison)
"""

from __future__ import annotations

import math
from collections.abc import Callable

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import CVARiskClass, CVASensitivityInput, SACVAResult
from src.jurisdictions.sg.pillar1 import params as p

DELTA = "DELTA"
VEGA = "VEGA"

# A risk-factor position after netting: (key, WS_k, WS_k^Hdg, attributes)
_Pos = tuple[tuple[str, ...], float, float]


# =========================================================================
#  Aggregation (para 8.5.32)
# =========================================================================


def bucket_capital(
    positions: list[_Pos],
    rho: Callable[[tuple[str, ...], tuple[str, ...]], float],
    r: float = p.SA_CVA_R,
) -> tuple[float, float]:
    """(K_b, sum WS_k) for one bucket.

    Reference: MAS Notice 637 para 8.5.32(d) (p. 8-196); the hedging-disallowance term
    R x sum (WS_k^Hdg)^2 sits inside the square root.
    """
    total = 0.0
    for i, (ki, wi, _) in enumerate(positions):
        total += wi * wi
        for j, (kj, wj, _) in enumerate(positions):
            if i != j:
                total += rho(ki, kj) * wi * wj
    hedge = sum(h * h for _, _, h in positions)
    kb = math.sqrt(max(total + r * hedge, 0.0))
    return kb, sum(w for _, w, _ in positions)


def class_capital(
    buckets: dict[str, tuple[float, float]],
    gamma: Callable[[str, str], float],
    m_cva: float = p.SA_CVA_M_CVA,
) -> float:
    """K = m_CVA sqrt(sum K_b^2 + sum_{b != c} gamma_bc S_b S_c), S_b capped / floored at K_b.

    Reference: MAS Notice 637 para 8.5.32(e) (p. 8-197).
    """
    s = {b: max(-kb, min(ws, kb)) for b, (kb, ws) in buckets.items()}
    total = sum(kb * kb for kb, _ in buckets.values())
    for b in buckets:
        for c in buckets:
            if b != c:
                total += gamma(b, c) * s[b] * s[c]
    return m_cva * math.sqrt(max(total, 0.0))


# =========================================================================
#  Risk weights and correlations per risk class
# =========================================================================


def _ir_specified(ccy: str) -> bool:
    """Reporting currency or a currency listed in para 8.5.36 (p. 8-199)."""
    return ccy == p.REPORTING_CURRENCY or ccy in p.IR_SPECIFIED_CURRENCIES


def ir_delta_rw(ccy: str, factor: str) -> float:
    """Interest rate delta risk weight.

    Reference: MAS Notice 637 para 8.5.36(c) / Table 8-28 (p. 8-200) and para 8.5.37(c)
    (p. 8-201).
    """
    if _ir_specified(ccy):
        if factor not in p.IR_DELTA_RW_SPECIFIED:
            raise ValueError(f"IR delta risk factor {factor!r} not in Table 8-28 for {ccy}")
        return p.IR_DELTA_RW_SPECIFIED[factor]
    if factor not in ("CURVE", "INFLATION"):
        raise ValueError(f"IR delta risk factor for {ccy} must be CURVE or INFLATION (8.5.37)")
    return p.IR_DELTA_RW_OTHER


def ir_delta_rho(ccy: str, f1: str, f2: str) -> float:
    """Correlation between interest rate delta risk factors in one currency.

    Reference: MAS Notice 637 Table 8-29 (p. 8-200); para 8.5.37(d) (p. 8-201).
    """
    if f1 == f2:
        return 1.0
    if not _ir_specified(ccy):
        return p.IR_DELTA_CORR_OTHER
    return p.IR_DELTA_CORR_SPECIFIED.get(
        (f1, f2), p.IR_DELTA_CORR_SPECIFIED.get((f2, f1), 1.0)
    )


def ccs_rw(bucket: str, investment_grade: bool | None) -> float:
    """Counterparty credit spread delta risk weight.

    Reference: MAS Notice 637 para 8.5.50(c), Table 8-31 (p. 8-209); not rated uses the
    grade "4" or worse column.
    """
    ig, hy = p.CCS_RW[bucket]
    return ig if investment_grade else hy


def _ccs_agg_bucket(bucket: str) -> str:
    """Buckets 1a / 1b aggregate as bucket 1 (Table 8-30, Table 8-32)."""
    return "1" if bucket in ("1a", "1b") else bucket


def ccs_rho(key1: tuple[str, ...], key2: tuple[str, ...]) -> float:
    """rho_kl = rho_tenor x rho_name x rho_quality for counterparty credit spread.

    Reference: MAS Notice 637 paras 8.5.50(d) and 8.5.51 (pp. 8-209, 8-210). ``key`` =
    (aggregation bucket, tenor, name, quality, sub-bucket).
    """
    b, t1, n1, q1, _ = key1
    _, t2, n2, q2, _ = key2
    rho_t = 1.0 if t1 == t2 else p.CCS_RHO_TENOR_DIFF
    g1, g2 = n1.split("|")[0], n2.split("|")[0]
    if n1 == n2:
        rho_n = 1.0
    elif "|" in n1 and "|" in n2 and g1 == g2:
        rho_n = p.CCS_RHO_INDEX_SERIES_DIFF if b == "8" else p.CCS_RHO_NAME_RELATED
    else:
        rho_n = p.CCS_RHO_INDEX_DIFF if b == "8" else p.CCS_RHO_NAME_UNRELATED
    rho_q = 1.0 if q1 == q2 else p.CCS_RHO_QUALITY_DIFF
    return rho_t * rho_n * rho_q


def ccs_gamma(b: str, c: str) -> float:
    """Cross-bucket correlation for counterparty credit spread.

    Reference: MAS Notice 637 para 8.5.52, Table 8-32 (p. 8-211).
    """
    return p.CCS_GAMMA.get((b, c), p.CCS_GAMMA.get((c, b), 0.0))


def rcs_rw(bucket: int, measure: str) -> float:
    """Reference credit spread risk weight.

    Reference: MAS Notice 637 Table 8-34 (p. 8-216); para 8.5.59(c) vega 100% (p. 8-217).
    """
    if bucket not in p.RCS_DELTA_RW:
        raise ValueError(f"reference credit spread bucket {bucket} not in Table 8-33")
    return p.RCS_VEGA_RW if measure == VEGA else p.RCS_DELTA_RW[bucket]


def rcs_gamma(b: int, c: int) -> float:
    """Cross-bucket correlation for reference credit spread.

    Reference: MAS Notice 637 paras 8.5.60-8.5.61, Table 8-35 (p. 8-217): halved for buckets
    1-14 of different credit quality.
    """
    if b == 15 or c == 15:
        return p.RCS_GAMMA_OTHER_BUCKET
    b_idx, c_idx = b >= 16, c >= 16
    if b_idx and c_idx:
        return p.RCS_GAMMA_INDEX_VS_INDEX
    if b_idx or c_idx:
        return p.RCS_GAMMA_INDEX_VS_SECTOR
    sb, sc = (b - 1) % 7 + 1, (c - 1) % 7 + 1
    base = p.RCS_GAMMA_SECTOR[(min(sb, sc), max(sb, sc))]
    same_quality = (b <= 7) == (c <= 7)
    return base if same_quality else base / p.RCS_DIFF_QUALITY_DIVISOR


def eq_rw(bucket: int, measure: str) -> float:
    """Equity risk weight.

    Reference: MAS Notice 637 Table 8-37 (p. 8-223); para 8.5.68(c) vega 78% large cap /
    100% otherwise (p. 8-224).
    """
    if bucket not in p.EQ_DELTA_RW:
        raise ValueError(f"equity bucket {bucket} not in Table 8-36")
    if measure == VEGA:
        return p.EQ_VEGA_RW_LARGE if bucket in p.EQ_LARGE_CAP_BUCKETS else p.EQ_VEGA_RW_OTHER
    return p.EQ_DELTA_RW[bucket]


def eq_gamma(b: int, c: int) -> float:
    """Cross-bucket correlation for equity.

    Reference: MAS Notice 637 para 8.5.69 (p. 8-224).
    """
    if b == 11 or c == 11:
        return p.EQ_GAMMA_OTHER
    b_idx, c_idx = b >= 12, c >= 12
    if b_idx and c_idx:
        return p.EQ_GAMMA_INDEX
    if b_idx or c_idx:
        return p.EQ_GAMMA_INDEX_SECTOR
    return p.EQ_GAMMA_SECTOR


def com_rw(bucket: int, measure: str) -> float:
    """Commodity risk weight.

    Reference: MAS Notice 637 Table 8-39 (p. 8-226); para 8.5.72(c) vega 100% (p. 8-227).
    """
    if bucket not in p.COM_DELTA_RW:
        raise ValueError(f"commodity bucket {bucket} not in Table 8-38")
    return p.COM_VEGA_RW if measure == VEGA else p.COM_DELTA_RW[bucket]


def com_gamma(b: int, c: int) -> float:
    """Cross-bucket correlation for commodity.

    Reference: MAS Notice 637 para 8.5.73 (p. 8-227).
    """
    if b == 11 or c == 11:
        return p.COM_GAMMA_OTHER
    return p.COM_GAMMA


# =========================================================================
#  Per-class computation
# =========================================================================


def _rf_upper(s: CVASensitivityInput) -> str:
    """Normalised risk-factor label."""
    return s.risk_factor.strip().upper()


def _net(
    items: dict[tuple[str, ...], list[float]], rw_of: Callable[[tuple[str, ...]], float]
) -> list[_Pos]:
    """Turn summed sensitivities into (key, WS_k, WS_k^Hdg) (para 8.5.32(b)-(c))."""
    out: list[_Pos] = []
    for key, (s_cva, s_hdg) in items.items():
        rw = rw_of(key)
        out.append((key, rw * s_cva - rw * s_hdg, rw * s_hdg))
    return out


def _accumulate(
    acc: dict[str, dict[tuple[str, ...], list[float]]],
    bucket: str,
    key: tuple[str, ...],
    s: CVASensitivityInput,
) -> None:
    """Sum s^CVA and s^Hdg for the same risk factor (para 8.5.32(a))."""
    slot = acc.setdefault(bucket, {}).setdefault(key, [0.0, 0.0])
    slot[0] += s.s_cva
    slot[1] += s.s_hedge


def risk_class_capital(
    risk_class: CVARiskClass,
    measure: str,
    sens: list[CVASensitivityInput],
    m_cva: float = p.SA_CVA_M_CVA,
) -> float:
    """K_delta or K_vega for one risk class.

    Reference: MAS Notice 637 paras 8.5.29-8.5.73 (pp. 8-194 to 8-227).
    """
    if not sens:
        return 0.0
    acc: dict[str, dict[tuple[str, ...], list[float]]] = {}
    rc = CVARiskClass
    rw_of: Callable[[tuple[str, ...]], float]
    rho: Callable[[tuple[str, ...], tuple[str, ...]], float]
    gamma: Callable[[str, str], float]

    if risk_class == rc.INTEREST_RATE:
        for s in sens:
            ccy = s.bucket.strip().upper()
            f = _rf_upper(s)
            if measure == VEGA:
                f = "INFLATION_VOL" if "INFLATION" in f else "RATE_VOL"
            _accumulate(acc, ccy, (ccy, f), s)

        def rw_of(k: tuple[str, ...]) -> float:
            return p.IR_VEGA_RW if measure == VEGA else ir_delta_rw(k[0], k[1])

        def rho(k1: tuple[str, ...], k2: tuple[str, ...]) -> float:
            if measure == VEGA:
                return 1.0 if k1[1] == k2[1] else p.IR_VEGA_CORR
            return ir_delta_rho(k1[0], k1[1], k2[1])

        def gamma(b: str, c: str) -> float:
            return p.IR_GAMMA

    elif risk_class == rc.FX:
        for s in sens:
            ccy = s.bucket.strip().upper()
            if ccy == p.REPORTING_CURRENCY:
                raise ValueError("no FX bucket for the reporting currency (para 8.5.40)")
            _accumulate(acc, ccy, (ccy,), s)

        def rw_of(k: tuple[str, ...]) -> float:
            return p.FX_VEGA_RW if measure == VEGA else p.FX_DELTA_RW

        def rho(k1: tuple[str, ...], k2: tuple[str, ...]) -> float:
            return 1.0

        def gamma(b: str, c: str) -> float:
            return p.FX_GAMMA

    elif risk_class == rc.COUNTERPARTY_CREDIT_SPREAD:
        if measure == VEGA:
            raise ValueError("no vega for counterparty credit spread (para 8.5.30)")
        for s in sens:
            sub = s.bucket.strip().lower()
            if sub not in p.CCS_RW:
                raise ValueError(f"counterparty credit spread bucket {s.bucket!r} not in "
                                 "Table 8-30")
            tenor = _rf_upper(s)
            if tenor not in p.CCS_TENORS:
                raise ValueError(f"tenor {tenor!r} not in para 8.5.50(a)")
            quality = "IG" if s.is_investment_grade else "NIG"
            agg = _ccs_agg_bucket(sub)
            _accumulate(acc, agg, (agg, tenor, s.name, quality, sub), s)

        def rw_of(k: tuple[str, ...]) -> float:
            return ccs_rw(k[4], k[3] == "IG")

        rho = ccs_rho
        gamma = ccs_gamma

    elif risk_class in (rc.REFERENCE_CREDIT_SPREAD, rc.EQUITY, rc.COMMODITY):
        rw_fn = {rc.REFERENCE_CREDIT_SPREAD: rcs_rw, rc.EQUITY: eq_rw, rc.COMMODITY: com_rw}[
            risk_class
        ]
        g_fn = {rc.REFERENCE_CREDIT_SPREAD: rcs_gamma, rc.EQUITY: eq_gamma,
                rc.COMMODITY: com_gamma}[risk_class]
        for s in sens:
            b = str(int(s.bucket))
            rw_fn(int(b), measure)  # validates the bucket
            _accumulate(acc, b, (b,), s)

        def rw_of(k: tuple[str, ...]) -> float:
            return rw_fn(int(k[0]), measure)

        def rho(k1: tuple[str, ...], k2: tuple[str, ...]) -> float:
            return 1.0

        def gamma(b: str, c: str) -> float:
            return g_fn(int(b), int(c))

    else:  # pragma: no cover - exhaustive enum
        raise ValueError(f"unknown risk class {risk_class}")

    buckets = {b: bucket_capital(_net(items, rw_of), rho) for b, items in acc.items()}
    return class_capital(buckets, gamma, m_cva)


_CLASS_CITES: dict[CVARiskClass, str] = {
    CVARiskClass.INTEREST_RATE: "MAS 637 paras 8.5.35-8.5.39, Tables 8-28 and 8-29",
    CVARiskClass.FX: "MAS 637 paras 8.5.40-8.5.45",
    CVARiskClass.COUNTERPARTY_CREDIT_SPREAD: "MAS 637 paras 8.5.46-8.5.52, Tables 8-30 to 8-32",
    CVARiskClass.REFERENCE_CREDIT_SPREAD: "MAS 637 paras 8.5.53-8.5.61, Tables 8-33 to 8-35",
    CVARiskClass.EQUITY: "MAS 637 paras 8.5.62-8.5.69, Tables 8-36 and 8-37",
    CVARiskClass.COMMODITY: "MAS 637 paras 8.5.70-8.5.73, Tables 8-38 and 8-39",
}


def sa_cva(
    sensitivities: list[CVASensitivityInput], m_cva: float = p.SA_CVA_M_CVA
) -> SACVAResult:
    """SA-CVA capital: sum of delta and vega capital over the six risk classes.

    Reference: MAS Notice 637 paras 8.5.1, 8.5.29-8.5.32 (pp. 8-178, 8-194 to 8-197).
    ``k_by_class`` keys are ``<RISK_CLASS>_<DELTA|VEGA>``.
    """
    if m_cva < p.SA_CVA_M_CVA:
        raise ValueError("m_CVA may not be set below 1 (para 8.5.32(e)(i))")
    grouped: dict[tuple[CVARiskClass, str], list[CVASensitivityInput]] = {}
    for s in sensitivities:
        measure = s.measure.strip().upper()
        if measure not in (DELTA, VEGA):
            raise ValueError(f"measure must be DELTA or VEGA, got {s.measure!r}")
        grouped.setdefault((s.risk_class, measure), []).append(s)
    k_by: dict[str, float] = {}
    for (rc, measure), items in grouped.items():
        k_by[f"{rc.value}_{measure}"] = risk_class_capital(rc, measure, items, m_cva)
    k_total = sum(k_by.values())
    cites = {f"{rc.value}": c for rc, c in _CLASS_CITES.items()}
    cites["aggregation"] = "MAS 637 para 8.5.32 (R = 0.01, m_CVA = 1)"
    cites["rwa"] = "MAS 637 para 8.5.1 (CVA RWA = 12.5 x capital)"
    return SACVAResult(
        jurisdiction=Jurisdiction.SG,
        k_by_class=k_by,
        k_total=k_total,
        rwa=p.CVA_RWA_MULTIPLIER * k_total,
        m_cva=m_cva,
        r_hedging_disallowance=p.SA_CVA_R,
        citations=cites,
    )
