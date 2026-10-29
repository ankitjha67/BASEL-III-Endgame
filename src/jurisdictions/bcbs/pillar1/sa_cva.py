"""BCBS standardised approach for CVA risk, SA-CVA (Basel Framework MAR50.27-50.77).

    WS_k^CVA = RW_k s_k^CVA,  WS_k^Hdg = RW_k s_k^Hdg                     (MAR50.51)
    WS_k     = WS_k^CVA - WS_k^Hdg                                       (MAR50.52)
    K_b      = sqrt[(sum_k WS_k^2 + sum_k sum_{l!=k} rho_kl WS_k WS_l)
                    + R sum_k (WS_k^Hdg)^2]                              (MAR50.53(1))
    K        = m_CVA sqrt[sum_b K_b^2 + sum_b sum_{c!=b} gamma_bc S_b S_c] (MAR50.53(2))
    S_b      = max{-K_b; min(sum_k WS_k; K_b)}                           (MAR50.53(3))
    K_SA-CVA = sum of delta K over six risk classes + vega K over five    (MAR50.42-50.45)
    RWA      = 12.5 x K_SA-CVA                                           (MAR50.1)

The aggregation formulas are images in the Framework (rendered p. 738); R = 0.01
(MAR50.53(1)), m_CVA = 1 (MAR50.41).

Input conventions (``CVASensitivityInput``):

- ``risk_class``; ``measure`` "DELTA" or "VEGA"; ``s_cva`` / ``s_hedge`` are the
  sensitivities of aggregate CVA and of the eligible hedges (MAR50.47). Several
  rows with the same (bucket, risk factor[, name]) are summed before weighting.
- INTEREST_RATE: ``bucket`` = currency; ``risk_factor`` = "1Y", "2Y", "5Y", "10Y",
  "30Y", "INFLATION" (specified currencies, MAR50.56) or "CURVE", "INFLATION" (other
  currencies, MAR50.57); vega: "IR_VOL", "INFLATION_VOL" (MAR50.58).
- FX: ``bucket`` = currency other than the reporting currency; ``risk_factor`` ignored.
- COUNTERPARTY_CREDIT_SPREAD (delta only): ``bucket`` "1a", "1b", "2"..."8";
  ``risk_factor`` = tenor "0.5Y", "1Y", "3Y", "5Y", "10Y"; ``name`` = entity, or for
  bucket 8 "INDEX:SERIES"; ``is_investment_grade`` (None = not rated -> HY/NR column);
  ``flags["legally_related:<other name>"]`` marks distinct but legally related names.
- REFERENCE_CREDIT_SPREAD: ``bucket`` "1".."17".
- EQUITY: ``bucket`` "1".."13". COMMODITY: ``bucket`` "1".."11".

References:
    - Basel Framework MAR50.27-50.77 (pp. 730-750)
    - BCBS d424, CVA section C (cross-check only; superseded July 2020 revisions)
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.bcbs.pillar1 import params as p
from src.jurisdictions.pillar1_base import CVARiskClass, CVASensitivityInput, SACVAResult

C = CVARiskClass


class _Factor:
    """A netted risk factor within a bucket."""

    __slots__ = ("key", "s_cva", "s_hedge", "rw", "meta")

    def __init__(self, key: tuple[str, ...], rw: float, meta: CVASensitivityInput) -> None:
        self.key = key
        self.s_cva = 0.0
        self.s_hedge = 0.0
        self.rw = rw
        self.meta = meta

    @property
    def ws_cva(self) -> float:
        return self.rw * self.s_cva

    @property
    def ws_hedge(self) -> float:
        return self.rw * self.s_hedge

    @property
    def ws(self) -> float:
        """MAR50.52: WS_k = WS_k^CVA - WS_k^Hdg."""
        return self.ws_cva - self.ws_hedge


# =========================================================================
#  Risk weights per risk class (MAR50.54-50.77)
# =========================================================================


def _is_specified_currency(ccy: str, reporting_ccy: str) -> bool:
    """MAR50.56: reporting currency and USD, EUR, GBP, AUD, CAD, SEK, JPY."""
    c = ccy.upper()
    return c in p.IR_SPECIFIED_CURRENCIES or c == reporting_ccy.upper()


def risk_weight(s: CVASensitivityInput, reporting_ccy: str = "USD") -> float:
    """RW_k for one sensitivity (MAR50.56-50.77)."""
    meas = s.measure.upper()
    if meas not in ("DELTA", "VEGA"):
        raise ValueError(f"measure must be DELTA or VEGA: {s.measure}")
    vega = meas == "VEGA"
    rc = s.risk_class
    if rc == C.INTEREST_RATE:
        if vega:
            if s.risk_factor.upper() not in p.IR_VEGA_FACTORS:
                raise ValueError(f"IR vega risk factor must be one of {p.IR_VEGA_FACTORS}")
            return p.IR_VEGA_RW
        rf = s.risk_factor.upper()
        if _is_specified_currency(s.bucket, reporting_ccy):
            if rf not in p.IR_DELTA_RW_SPECIFIED:
                raise ValueError(f"MAR50.56 tenor must be one of {p.IR_TENORS}: {rf}")
            return p.IR_DELTA_RW_SPECIFIED[rf]
        if rf not in p.IR_OTHER_FACTORS:
            raise ValueError(f"MAR50.57 risk factor must be one of {p.IR_OTHER_FACTORS}")
        return p.IR_DELTA_RW_OTHER
    if rc == C.FX:
        if s.bucket.upper() == reporting_ccy.upper():
            raise ValueError("MAR50.59: no FX bucket for the reporting currency")
        return p.FX_VEGA_RW if vega else p.FX_DELTA_RW
    if rc == C.COUNTERPARTY_CREDIT_SPREAD:
        if vega:
            raise ValueError("MAR50.45 / MAR50.63: no vega for counterparty credit spread")
        b = s.bucket.lower()
        if b not in p.CCS_DELTA_RW:
            raise ValueError(f"MAR50.63 Table 5 bucket unknown: {s.bucket}")
        if s.risk_factor.upper() not in p.CCS_TENORS:
            raise ValueError(f"MAR50.65(1) tenor must be one of {p.CCS_TENORS}")
        ig, hy = p.CCS_DELTA_RW[b]
        return ig if s.is_investment_grade else hy
    if rc == C.REFERENCE_CREDIT_SPREAD:
        nb = int(s.bucket)
        if nb not in p.RCS_DELTA_RW:
            raise ValueError(f"MAR50.66 Table 8 bucket unknown: {s.bucket}")
        return p.RCS_VEGA_RW if vega else p.RCS_DELTA_RW[nb]
    if rc == C.EQUITY:
        nb = int(s.bucket)
        if nb not in p.EQ_DELTA_RW:
            raise ValueError(f"MAR50.70 Table 11 bucket unknown: {s.bucket}")
        if vega:
            return p.EQ_VEGA_RW_LARGE_CAP if nb in p.EQ_LARGE_CAP_BUCKETS else p.EQ_VEGA_RW_OTHER
        return p.EQ_DELTA_RW[nb]
    if rc == C.COMMODITY:
        nb = int(s.bucket)
        if nb not in p.COM_DELTA_RW:
            raise ValueError(f"MAR50.74 Table 13 bucket unknown: {s.bucket}")
        return p.COM_VEGA_RW if vega else p.COM_DELTA_RW[nb]
    raise ValueError(f"unknown risk class {rc}")


# =========================================================================
#  Bucket keys and intra-bucket correlations
# =========================================================================


def aggregation_bucket(s: CVASensitivityInput) -> str:
    """Bucket used for aggregation (CCS 1a/1b share bucket 1, MAR50.63 Table 5)."""
    if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        return "1" if s.bucket.lower() in ("1a", "1b") else s.bucket
    if s.risk_class in (C.INTEREST_RATE, C.FX):
        return s.bucket.upper()
    return str(int(s.bucket))


def _factor_key(s: CVASensitivityInput) -> tuple[str, ...]:
    """Risk-factor identity within a bucket (single-factor buckets collapse to one key)."""
    if s.risk_class == C.INTEREST_RATE:
        return (s.risk_factor.upper(),)
    if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        return (s.name, s.risk_factor.upper(), s.bucket.lower(),
                "IG" if s.is_investment_grade else "HY_NR")
    return ("SINGLE",)


def _ir_rho(k: _Factor, l_: _Factor, specified: bool, vega: bool) -> float:
    """MAR50.56(4) Table 4, MAR50.57(4), MAR50.58(4)."""
    a, b = k.key[0], l_.key[0]
    if a == b:
        return 1.0
    if vega:
        return p.IR_VEGA_CORR
    if not specified:
        return p.IR_DELTA_CORR_OTHER
    return p.IR_DELTA_CORR_SPECIFIED.get((a, b), p.IR_DELTA_CORR_SPECIFIED.get((b, a), 0.0))


def _legally_related(a: CVASensitivityInput, b: CVASensitivityInput) -> bool:
    """MAR50.65(4)(2): distinct but legally related names (flag on either side)."""
    return bool(a.flags.get(f"legally_related:{b.name}")
                or b.flags.get(f"legally_related:{a.name}"))


def ccs_rho(k: CVASensitivityInput, l_: CVASensitivityInput, index_bucket: bool) -> float:
    """MAR50.65(4)-(5): rho_kl = rho_tenor x rho_name x rho_quality (image, p. 743)."""
    same_tenor = k.risk_factor.upper() == l_.risk_factor.upper()
    rho_tenor = 1.0 if same_tenor else p.CCS_RHO_TENOR_DIFFERENT
    if index_bucket:
        ik, _, sk = k.name.partition(":")
        il, _, sl = l_.name.partition(":")
        if ik == il and sk == sl:
            rho_name = 1.0
        elif ik == il:
            rho_name = p.CCS_RHO_INDEX_DISTINCT_SERIES
        else:
            rho_name = p.CCS_RHO_INDEX_OTHER
    elif k.name == l_.name:
        rho_name = 1.0
    elif _legally_related(k, l_):
        rho_name = p.CCS_RHO_NAME_RELATED
    else:
        rho_name = p.CCS_RHO_NAME_UNRELATED
    same_q = bool(k.is_investment_grade) == bool(l_.is_investment_grade)
    rho_quality = 1.0 if same_q else p.CCS_RHO_QUALITY_DIFFERENT
    return rho_tenor * rho_name * rho_quality


# =========================================================================
#  Cross-bucket correlations
# =========================================================================


def _rcs_key(b: int) -> str:
    return f"S{(b - 1) % 7 + 1}" if b <= 14 else str(b)


def rcs_gamma(b: int, c: int) -> float:
    """MAR50.67 Table 9 with the IG/HY halving of MAR50.67(2)."""
    kb, kc = _rcs_key(b), _rcs_key(c)
    if kb == kc:
        g = 1.0
    else:
        g = p.RCS_CROSS_BUCKET_GAMMA.get((kb, kc), p.RCS_CROSS_BUCKET_GAMMA.get((kc, kb), 0.0))
    if b <= 14 and c <= 14 and (b <= 7) != (c <= 7):
        g /= p.RCS_DIFFERENT_QUALITY_DIVISOR
    return g


def ccs_gamma(b: str, c: str) -> float:
    """MAR50.64 Table 6."""
    return p.CCS_CROSS_BUCKET_GAMMA.get((b, c), p.CCS_CROSS_BUCKET_GAMMA.get((c, b), 0.0))


def equity_gamma(b: int, c: int) -> float:
    """MAR50.71."""
    if 11 in (b, c):
        return p.EQ_GAMMA_OTHER_BUCKET
    if {b, c} == {12, 13}:
        return p.EQ_GAMMA_12_13
    if b in (12, 13) or c in (12, 13):
        return p.EQ_GAMMA_INDEX_VS_1_TO_10
    return p.EQ_GAMMA_1_TO_10


def commodity_gamma(b: int, c: int) -> float:
    """MAR50.75."""
    return p.COM_GAMMA_OTHER_BUCKET if 11 in (b, c) else p.COM_GAMMA_1_TO_10


def cross_bucket_gamma(rc: CVARiskClass) -> Callable[[str, str], float]:
    """gamma_bc for the risk class (MAR50.55, 50.60, 50.64, 50.67, 50.71, 50.75)."""
    if rc == C.INTEREST_RATE:
        return lambda _b, _c: p.IR_CROSS_BUCKET_GAMMA
    if rc == C.FX:
        return lambda _b, _c: p.FX_CROSS_BUCKET_GAMMA
    if rc == C.COUNTERPARTY_CREDIT_SPREAD:
        return ccs_gamma
    if rc == C.REFERENCE_CREDIT_SPREAD:
        return lambda b, c: rcs_gamma(int(b), int(c))
    if rc == C.EQUITY:
        return lambda b, c: equity_gamma(int(b), int(c))
    return lambda b, c: commodity_gamma(int(b), int(c))


# =========================================================================
#  Aggregation (MAR50.53)
# =========================================================================


def bucket_capital(factors: list[_Factor], rho: Callable[[_Factor, _Factor], float],
                   r: float = p.R_HEDGING_DISALLOWANCE) -> float:
    """MAR50.53(1): K_b."""
    total = sum(f.ws ** 2 for f in factors)
    for i, fk in enumerate(factors):
        for j, fl in enumerate(factors):
            if i != j:
                total += rho(fk, fl) * fk.ws * fl.ws
    total += r * sum(f.ws_hedge ** 2 for f in factors)
    return math.sqrt(max(total, 0.0))


def class_capital(kb: dict[str, float], sb_raw: dict[str, float],
                  gamma: Callable[[str, str], float], m_cva: float = p.M_CVA) -> float:
    """MAR50.53(2)-(3): K = m_CVA sqrt[sum K_b^2 + sum_{b!=c} gamma_bc S_b S_c].

    S_b = max(-K_b, min(sum_k WS_k, K_b)). The radicand is floored at zero.
    """
    s = {b: max(-kb[b], min(sb_raw[b], kb[b])) for b in kb}
    total = sum(v * v for v in kb.values())
    keys = list(kb)
    for b in keys:
        for c in keys:
            if b != c:
                total += gamma(b, c) * s[b] * s[c]
    return m_cva * math.sqrt(max(total, 0.0))


def _intra_rho(rc: CVARiskClass, bucket: str, reporting_ccy: str,
               vega: bool) -> Callable[[_Factor, _Factor], float]:
    """rho_kl within a bucket (MAR50.56-50.58, MAR50.65); single-factor buckets -> 1."""
    if rc == C.INTEREST_RATE:
        spec = _is_specified_currency(bucket, reporting_ccy)
        return lambda x, y: _ir_rho(x, y, spec, vega)
    if rc == C.COUNTERPARTY_CREDIT_SPREAD:
        idx = bucket == p.CCS_INDEX_BUCKET
        return lambda x, y: ccs_rho(x.meta, y.meta, idx)
    return lambda _x, _y: 1.0


def risk_class_capital(sens: list[CVASensitivityInput], rc: CVARiskClass, vega: bool,
                       reporting_ccy: str = "USD", m_cva: float = p.M_CVA) -> float:
    """Delta or vega capital for one risk class (MAR50.46-50.53)."""
    buckets: dict[str, dict[tuple[str, ...], _Factor]] = defaultdict(dict)
    for s in sens:
        b = aggregation_bucket(s)
        key = _factor_key(s)
        f = buckets[b].get(key)
        if f is None:
            f = _Factor(key, risk_weight(s, reporting_ccy), s)
            buckets[b][key] = f
        f.s_cva += s.s_cva
        f.s_hedge += s.s_hedge
    kb: dict[str, float] = {}
    sb: dict[str, float] = {}
    for b, fmap in buckets.items():
        factors = list(fmap.values())
        kb[b] = bucket_capital(factors, _intra_rho(rc, b, reporting_ccy, vega))
        sb[b] = sum(f.ws for f in factors)
    if not kb:
        return 0.0
    return class_capital(kb, sb, cross_bucket_gamma(rc), m_cva)


def sa_cva(sensitivities: list[CVASensitivityInput], reporting_ccy: str = "USD",
           m_cva: float = p.M_CVA) -> SACVAResult:
    """K_SA-CVA = sum of delta and vega capital by risk class (MAR50.42-50.53); RWA x 12.5."""
    groups: dict[tuple[CVARiskClass, bool], list[CVASensitivityInput]] = defaultdict(list)
    for s in sensitivities:
        groups[(s.risk_class, s.measure.upper() == "VEGA")].append(s)
    k_by: dict[str, float] = {}
    for (rc, vega), sens in groups.items():
        k_by[f"{rc.value}_{'VEGA' if vega else 'DELTA'}"] = risk_class_capital(
            sens, rc, vega, reporting_ccy, m_cva)
    k_total = sum(k_by.values())
    return SACVAResult(
        jurisdiction=Jurisdiction.BCBS,
        k_by_class=k_by,
        k_total=k_total,
        rwa=p.CVA_RWA_MULTIPLIER * k_total,
        m_cva=m_cva,
        r_hedging_disallowance=p.R_HEDGING_DISALLOWANCE,
        citations={
            "aggregation": "MAR50.51-50.53 (R = 0.01, m_CVA per MAR50.41)",
            "interest_rate": "MAR50.54-50.58 (Tables 3-4)",
            "fx": "MAR50.59-50.62",
            "counterparty_credit_spread": "MAR50.63-50.65 (Tables 5-7)",
            "reference_credit_spread": "MAR50.66-50.69 (Tables 8-10)",
            "equity": "MAR50.70-50.73 (Tables 11-12)",
            "commodity": "MAR50.74-50.77 (Tables 13-14)",
            "rwa": "MAR50.1",
        },
    )
