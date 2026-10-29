"""EU standardised approach for CVA risk -- CRR Articles 383-383z (CRR3 points (200)-(201)).

Aggregation (Article 383b(5)-(8), OJ pp.137-138, printed as images):

* WS_k^CVA = RW_k S_k^CVA;  WS_k^hedges = RW_k S_k^hedges;  WS_k = WS_k^CVA - WS_k^hedges
* K_b = sqrt( sum_k WS_k^2 + sum_k sum_{l != k} rho_kl WS_k WS_l + R sum_k (WS_k^hedges)^2 ),
  R = 0,01
* K (risk class, delta or vega) = m_CVA sqrt( sum_b K_b^2 + sum_b sum_{c != b} gamma_bc S_b S_c ),
  S_b = max{-K_b; min(sum_k WS_k; K_b)}, m_CVA = 1
* Own funds requirement = sum over the six risk classes of the delta and vega
  requirements (Article 383(3)); RWEA = 12,5 x own funds (Article 92(6)(b)).

Input conventions for :class:`~src.jurisdictions.pillar1_base.CVASensitivityInput`:

* ``measure``: ``"DELTA"`` or ``"VEGA"``; counterparty credit spread has no vega (383e(2)).
* INTEREST_RATE: ``bucket`` = ISO currency; ``risk_factor`` = tenor ``1Y/2Y/5Y/10Y/30Y`` for
  the risk-free curve, ``INFLATION_<tenor>`` for inflation (specified currencies, 383c(1));
  for other currencies ``PARALLEL`` and ``INFLATION`` (383c(3)); for vega any factor
  containing ``INFL`` is the inflation volatility, otherwise the rate volatility (383c(6)).
  Specified currencies (383c(2)): EUR, SEK, AUD, CAD, GBP, JPY, USD, the reporting currency,
  and ERM II currencies (flag ``eu_erm2_currency`` or constructor list).
* FX: ``bucket`` = currency (versus the reporting currency); flag ``eu_erm2_currency``
  applies the 11 %/3 weight of 383n(2)(a).
* COUNTERPARTY_CREDIT_SPREAD: ``bucket`` = Table 1 bucket number 1-21 (383p); ``risk_factor``
  = tenor ``0.5Y/1Y/3Y/5Y/10Y``; ``name`` = counterparty or index name; flags
  ``group:<id>`` mark legally related names, ``series:<id>`` the index series,
  ``eu_cqs1`` selects the CQS 1 weight in bucket 10.
* REFERENCE_CREDIT_SPREAD: ``bucket`` = 383s Table 1 bucket 1-20 (one net sensitivity per
  bucket, 383f); ``eu_cqs1`` for bucket 10.
* EQUITY: ``bucket`` = 383v Table 1 bucket 1-13 (one net sensitivity per bucket, 383g).
* COMMODITY: ``bucket`` = 383x Table 1 bucket 1-13 (one net sensitivity per bucket, 383h).

References:
    - Regulation (EU) 2024/1623, Article 1 points (199)-(201) (Articles 382a-383z)
    - Regulation (EU) No 575/2013, Article 92(6)(b) as replaced by CRR3
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.eu.pillar1 import params as prm
from src.jurisdictions.pillar1_base import CVARiskClass, CVASensitivityInput, SACVAResult

RC = CVARiskClass

_CITE_RW: dict[CVARiskClass, str] = {
    RC.INTEREST_RATE: "CRR Art. 383k; correlations 383l, 383m",
    RC.FX: "CRR Art. 383n; correlations 383o",
    RC.COUNTERPARTY_CREDIT_SPREAD: "CRR Art. 383p; correlations 383q, 383r",
    RC.REFERENCE_CREDIT_SPREAD: "CRR Art. 383s; correlations 383t, 383u",
    RC.EQUITY: "CRR Art. 383v; correlations 383w",
    RC.COMMODITY: "CRR Art. 383x; correlations 383z",
}


# =========================================================================
#  Risk-factor keys
# =========================================================================


def _bucket_no(s: CVASensitivityInput, lo: int, hi: int) -> int:
    """Integer bucket number, validated against the table range."""
    try:
        b = int(str(s.bucket).strip())
    except ValueError as exc:
        raise ValueError(f"{s.risk_class.value} bucket must be a number, got {s.bucket!r}") from exc
    if not lo <= b <= hi:
        raise ValueError(f"{s.risk_class.value} bucket must be {lo}-{hi}, got {b}")
    return b


def _ir_factor(rf: str, specified: bool, vega: bool) -> tuple[str, str]:
    """(type, tenor) of an interest-rate factor: type 'RFR' or 'INF' -- Article 383c."""
    u = rf.strip().upper()
    kind = "INF" if "INFL" in u else "RFR"
    if vega or not specified:
        return kind, "ALL"
    tenor = u.replace("INFLATION", "").replace("INFL", "").strip("_ ") or ""
    if tenor not in prm.SACVA_IR_TENORS:
        raise ValueError(f"interest-rate tenor must be one of {prm.SACVA_IR_TENORS}, got {rf!r}")
    return kind, tenor


def _tenor_corr(t1: str, t2: str) -> float:
    """Article 383l(1) Table 1."""
    if t1 == t2:
        return 1.0
    return prm.SACVA_IR_TENOR_CORR.get((t1, t2)) or prm.SACVA_IR_TENOR_CORR[(t2, t1)]


def _flag_values(s: CVASensitivityInput, prefix: str) -> set[str]:
    """Values of ``prefix:<value>`` flags set to True."""
    return {k.split(":", 1)[1] for k, v in s.flags.items() if v and k.startswith(prefix + ":")}


# =========================================================================
#  Risk weights
# =========================================================================


class _Ctx:
    """Regime context: reporting currency and ERM II currencies (Article 383c(2))."""

    def __init__(self, reporting_currency: str, erm2_currencies: Iterable[str]) -> None:
        """Store the reporting currency and the ERM II currency list."""
        self.reporting = reporting_currency.upper()
        self.erm2 = {c.upper() for c in erm2_currencies}

    def ir_specified(self, s: CVASensitivityInput) -> bool:
        """Currency gets the tenor risk factors of Article 383c(1)-(2)."""
        ccy =str(s.bucket).upper()
        return (
            ccy in prm.SACVA_IR_SPECIFIED_CURRENCIES
            or ccy == self.reporting
            or ccy in self.erm2
            or s.flags.get("eu_erm2_currency", False)
        )


def risk_weight(s: CVASensitivityInput, ctx: _Ctx) -> float:
    """RW_k of a sensitivity -- Articles 383k, 383n, 383p, 383s, 383v, 383x."""
    vega = s.measure.upper() == "VEGA"
    rc = s.risk_class
    if rc is RC.INTEREST_RATE:
        if vega:
            return prm.SACVA_IR_VEGA_RW
        spec = ctx.ir_specified(s)
        kind, tenor = _ir_factor(s.risk_factor, spec, vega)
        if kind == "INF":
            return prm.SACVA_INFLATION_RW_SPECIFIED if spec else prm.SACVA_INFLATION_RW_OTHER
        return prm.SACVA_IR_RW_SPECIFIED[tenor] if spec else prm.SACVA_IR_RW_OTHER
    if rc is RC.FX:
        if vega:
            return prm.SACVA_FX_VEGA_RW
        erm2 = str(s.bucket).upper() in ctx.erm2 or s.flags.get("eu_erm2_currency", False)
        return prm.SACVA_FX_RW / prm.SACVA_FX_ERM2_DIVISOR if erm2 else prm.SACVA_FX_RW
    if rc is RC.COUNTERPARTY_CREDIT_SPREAD:
        if vega:
            raise ValueError("counterparty credit spread has no vega requirement (Art. 383e(2))")
        b = _bucket_no(s, 1, 21)
        if b == 10:
            return prm.SACVA_CCS_RW_BUCKET_10["CQS1" if s.flags.get("eu_cqs1") else "CQS2_3"]
        return prm.SACVA_CCS_RW[b]
    if rc is RC.REFERENCE_CREDIT_SPREAD:
        b = _bucket_no(s, 1, 20)
        if vega:
            return prm.SACVA_RCS_VEGA_RW
        if b == 10:
            return prm.SACVA_CCS_RW_BUCKET_10["CQS1" if s.flags.get("eu_cqs1") else "CQS2_3"]
        return prm.SACVA_RCS_RW[b]
    if rc is RC.EQUITY:
        b = _bucket_no(s, 1, 13)
        if vega:
            return (
                prm.SACVA_EQ_VEGA_RW_LARGE
                if b in prm.SACVA_EQ_VEGA_LARGE_BUCKETS
                else prm.SACVA_EQ_VEGA_RW_OTHER
            )
        return prm.SACVA_EQ_RW[b]
    b = _bucket_no(s, 1, 13)  # COMMODITY
    return prm.SACVA_COM_VEGA_RW if vega else prm.SACVA_COM_RW[b]


# =========================================================================
#  Correlations
# =========================================================================


def intra_bucket_corr(
    s1: CVASensitivityInput, s2: CVASensitivityInput, ctx: _Ctx
) -> float:
    """rho_kl within a bucket -- Articles 383l, 383q, 383t.

    Risk classes with a single net sensitivity per bucket (FX, reference credit
    spread, equity, commodity) never reach this function.
    """
    rc = s1.risk_class
    vega = s1.measure.upper() == "VEGA"
    if rc is RC.INTEREST_RATE:
        spec = ctx.ir_specified(s1)
        k1, t1 = _ir_factor(s1.risk_factor, spec, vega)
        k2, t2 = _ir_factor(s2.risk_factor, spec, vega)
        if k1 != k2:
            return prm.SACVA_IR_INFLATION_CORR  # 383l(2) delta / 383l(3) vega
        if not spec or vega:
            return 1.0
        # TODO: VERIFY -- Article 383l gives no correlation between inflation tenors; the
        # risk-free tenor correlations of Table 1 are applied to inflation tenors too.
        return _tenor_corr(t1, t2)
    if rc is RC.COUNTERPARTY_CREDIT_SPREAD:
        b1, b2 = _bucket_no(s1, 1, 21), _bucket_no(s2, 1, 21)
        rho_tenor = (
            1.0 if s1.risk_factor.strip().upper() == s2.risk_factor.strip().upper()
            else prm.SACVA_CS_RHO_TENOR_DIFF
        )  # fmt: skip
        if b1 in prm.SACVA_CCS_INDEX_BUCKETS:
            if s1.name == s2.name:
                same_series = _flag_values(s1, "series") == _flag_values(s2, "series")
                rho_name = 1.0 if same_series else prm.SACVA_CS_RHO_INDEX_SERIES
            else:
                rho_name = prm.SACVA_CS_RHO_INDEX_OTHER
            rho_quality = 1.0 if b1 == b2 else prm.SACVA_CS_RHO_QUALITY_DIFF
        else:
            if s1.name == s2.name:
                rho_name = 1.0
            elif _flag_values(s1, "group") & _flag_values(s2, "group"):
                rho_name = prm.SACVA_CS_RHO_NAME_RELATED
            else:
                rho_name = prm.SACVA_CS_RHO_NAME_UNRELATED
            same_q = any(b1 in g and b2 in g for g in prm.SACVA_CCS_QUALITY_GROUPS)
            rho_quality = 1.0 if same_q else prm.SACVA_CS_RHO_QUALITY_DIFF
        return rho_tenor * rho_name * rho_quality
    return 1.0


def cross_bucket_corr(rc: CVARiskClass, b: str, c: str) -> float:
    """gamma_bc -- Articles 383m, 383o, 383r, 383u, 383w, 383z."""
    if rc is RC.INTEREST_RATE:
        return prm.SACVA_IR_CROSS_BUCKET
    if rc is RC.FX:
        return prm.SACVA_FX_CROSS_BUCKET
    bi, ci = int(b), int(c)
    if rc is RC.COUNTERPARTY_CREDIT_SPREAD:
        g1, g2 = prm.SACVA_CCS_CROSS_GROUPS[bi], prm.SACVA_CCS_CROSS_GROUPS[ci]
        return prm.SACVA_CCS_CROSS_CORR[(g1, g2)]
    if rc is RC.REFERENCE_CREDIT_SPREAD:
        g1, g2 = prm.SACVA_RCS_CROSS_GROUPS[bi], prm.SACVA_RCS_CROSS_GROUPS[ci]
        gamma = prm.SACVA_RCS_CROSS_CORR[(g1, g2)]
        ig, hy = prm.SACVA_RCS_IG_BUCKETS, prm.SACVA_RCS_HY_BUCKETS
        if (bi in ig and ci in hy) or (bi in hy and ci in ig):
            gamma /= prm.SACVA_RCS_IG_HY_DIVISOR  # 383u(2)
        return gamma
    if rc is RC.EQUITY:
        if 11 in (bi, ci):
            return prm.SACVA_EQ_CROSS_OTHER
        idx = {12, 13}
        if bi in idx and ci in idx:
            return prm.SACVA_EQ_CROSS_12_13
        if bi in idx or ci in idx:
            return prm.SACVA_EQ_CROSS_INDEX_SECTOR
        return prm.SACVA_EQ_CROSS_1_10
    if 13 in (bi, ci):  # COMMODITY
        return prm.SACVA_COM_CROSS_OTHER
    return prm.SACVA_COM_CROSS


# =========================================================================
#  Aggregation -- Article 383b(5)-(8)
# =========================================================================

_SINGLE_NET = {RC.FX, RC.REFERENCE_CREDIT_SPREAD, RC.EQUITY, RC.COMMODITY}


def _factor_key(s: CVASensitivityInput, ctx: _Ctx) -> tuple[str, ...]:
    """Key under which sensitivities are netted (one net sensitivity per risk factor)."""
    if s.risk_class in _SINGLE_NET:
        return ("NET",)
    vega = s.measure.upper() == "VEGA"
    if s.risk_class is RC.INTEREST_RATE:
        return _ir_factor(s.risk_factor, ctx.ir_specified(s), vega)
    series = ",".join(sorted(_flag_values(s, "series")))
    return (s.name, s.risk_factor.strip().upper(), series)


def bucket_capital(
    ws: list[float], ws_hedge: list[float], rho: list[list[float]], r: float = prm.SACVA_R
) -> tuple[float, float]:
    """(K_b, S_b) -- Article 383b(7)-(8)."""
    n = len(ws)
    total = sum(w * w for w in ws)
    for i in range(n):
        for j in range(n):
            if i != j:
                total += rho[i][j] * ws[i] * ws[j]
    total += r * sum(h * h for h in ws_hedge)
    kb = math.sqrt(max(total, 0.0))
    sb = max(-kb, min(sum(ws), kb))
    return kb, sb


def class_capital(
    sens: list[CVASensitivityInput], ctx: _Ctx, m_cva: float = prm.SACVA_M_CVA
) -> float:
    """Risk-class own funds requirement for delta or vega -- Article 383b(8)."""
    if not sens:
        return 0.0
    rc = sens[0].risk_class
    by_bucket: dict[str, dict[tuple[str, ...], list[CVASensitivityInput]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for s in sens:
        by_bucket[str(s.bucket).strip().upper()][_factor_key(s, ctx)].append(s)
    kb: dict[str, float] = {}
    sb: dict[str, float] = {}
    for b, factors in by_bucket.items():
        reps: list[CVASensitivityInput] = []
        ws: list[float] = []
        wsh: list[float] = []
        for group in factors.values():
            rw = risk_weight(group[0], ctx)
            s_cva = sum(x.s_cva for x in group)
            s_hedge = sum(x.s_hedge for x in group)
            reps.append(group[0])
            ws.append(rw * s_cva - rw * s_hedge)  # 383b(5)-(6)
            wsh.append(rw * s_hedge)
        rho = [[intra_bucket_corr(a, c, ctx) if i != j else 1.0 for j, c in enumerate(reps)]
               for i, a in enumerate(reps)]  # fmt: skip
        kb[b], sb[b] = bucket_capital(ws, wsh, rho)
    total = sum(v * v for v in kb.values())
    keys = list(kb)
    for b in keys:
        for c in keys:
            if b != c:
                total += cross_bucket_corr(rc, b, c) * sb[b] * sb[c]
    return m_cva * math.sqrt(max(total, 0.0))


def sa_cva(
    sensitivities: list[CVASensitivityInput],
    reporting_currency: str = "EUR",
    erm2_currencies: Iterable[str] = (),
    m_cva: float = prm.SACVA_M_CVA,
) -> SACVAResult:
    """SA-CVA own funds requirement and RWEA -- Articles 383(3), 383b, 92(6)(b).

    ``m_cva`` defaults to 1 (383b(8)); a competent authority may set it higher.
    """
    if m_cva < prm.SACVA_M_CVA:
        raise ValueError("m_CVA may only be increased above 1 (Art. 383b(8))")
    ctx = _Ctx(reporting_currency, erm2_currencies)
    groups: dict[tuple[CVARiskClass, str], list[CVASensitivityInput]] = defaultdict(list)
    for s in sensitivities:
        m = s.measure.strip().upper()
        if m not in ("DELTA", "VEGA"):
            raise ValueError(f"measure must be DELTA or VEGA, got {s.measure!r}")
        if s.risk_class is RC.COUNTERPARTY_CREDIT_SPREAD and m == "VEGA":
            raise ValueError("counterparty credit spread has no vega requirement (Art. 383e(2))")
        groups[(s.risk_class, m)].append(s)
    k_by: dict[str, float] = {}
    cites: dict[str, str] = {
        "aggregation": "CRR Art. 383b(5)-(8): R = 0,01, m_CVA = 1",
        "total": "CRR Art. 383(3): sum of delta and vega requirements",
        "rwa": "CRR Art. 92(6)(b): x 12,5",
    }
    for (rc, m), lst in sorted(groups.items(), key=lambda kv: (kv[0][0].value, kv[0][1])):
        key = f"{rc.value}_{m}"
        k_by[key] = class_capital(lst, ctx, m_cva)
        cites[key] = _CITE_RW[rc]
    k_total = sum(k_by.values())
    return SACVAResult(
        jurisdiction=Jurisdiction.EU,
        k_by_class=k_by,
        k_total=k_total,
        rwa=prm.SACVA_OWN_FUNDS_TO_RWA * k_total,
        m_cva=m_cva,
        r_hedging_disallowance=prm.SACVA_R,
        citations=cites,
    )
