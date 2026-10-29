"""OSFI CAR 2026 Chapter 8 s.8.3 -- standardized approach for CVA risk (SA-CVA).

K = sum over risk classes and measures of m_CVA x sqrt(sum_b K_b^2 + sum_b sum_{c != b}
gamma_bc S_b S_c), with K_b = sqrt((sum WS_k^2 + sum sum rho_kl WS_k WS_l) + R sum (WS_k^Hdg)^2),
WS_k = RW_k s_k^CVA - RW_k s_k^Hdg and S_b = max(-K_b, min(sum WS_k, K_b)) (s.8.3.4). The square
roots are lost in the flattened CAR text and are taken from the identical Basel MAR 50.53 formula.
m_CVA = 1, R = 0.01. Counterparty credit spread has no vega requirement (s.8.3.4).

Input conventions (``CVASensitivityInput``):

- INTEREST_RATE: ``bucket`` = currency; delta ``risk_factor`` in {1Y, 2Y, 5Y, 10Y, 30Y,
  INFLATION} for specified currencies (USD, EUR, GBP, AUD, CAD, SEK, JPY and the reporting
  currency) or {CURVE, INFLATION} otherwise; vega ``risk_factor`` in {IR_VOL, INFLATION_VOL}.
- FX: ``bucket`` = currency (not the reporting currency); one risk factor per bucket.
- COUNTERPARTY_CREDIT_SPREAD: ``bucket`` in {1a, 1b, 2, ..., 8}; ``risk_factor`` = tenor in
  {0.5Y, 1Y, 3Y, 5Y, 10Y}; ``name`` = entity (or "INDEX::SERIES" in bucket 8); names sharing the
  prefix before "::" are "distinct but legally related"; ``is_investment_grade`` selects the IG /
  HY-NR risk weight and rho_quality.
- REFERENCE_CREDIT_SPREAD: ``bucket`` in 1..17 (Table 8); single risk factor per bucket.
- EQUITY: ``bucket`` in 1..13 (Table 11); single risk factor per bucket.
- COMMODITY: ``bucket`` in 1..11 (Table 13); single risk factor per bucket.

Sensitivities sharing (class, measure, bucket, risk factor, name) are summed first.

References:
    - OSFI CAR 2026 Ch.8 s.8.3.3-8.3.10, Tables 3-14
    - Basel Framework MAR50.40-50.77
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.ca.pillar1 import params as p
from src.jurisdictions.pillar1_base import CVARiskClass, CVASensitivityInput, SACVAResult

C = CVARiskClass


@dataclass(frozen=True)
class _Factor:
    """One netted risk factor within a bucket."""

    bucket: str
    risk_factor: str
    name: str
    ig: bool | None
    ws_cva: float
    ws_hdg: float

    @property
    def ws(self) -> float:
        """Net weighted sensitivity WS_k = WS_k^CVA - WS_k^Hdg (CAR s.8.3.4 [MAR 50.52])."""
        return self.ws_cva - self.ws_hdg


# -------------------------------------------------------------------------
#  Risk weights
# -------------------------------------------------------------------------

def _ccs_rw_key(bucket: str) -> str:
    b = bucket.strip().lower()
    if b == "1":
        return "1b"  # conservative: higher of the 1a / 1b weights
    if b not in p.SA_CVA_CCS_RW:
        raise ValueError(f"unknown counterparty credit spread bucket {bucket!r}")
    return b


def risk_weight(s: CVASensitivityInput, reporting_currency: str) -> float:
    """RW_k for one sensitivity (CAR Ch.8 s.8.3.5-8.3.10 [MAR 50.56-50.77])."""
    measure = s.measure.upper()
    rf = s.risk_factor.upper()
    if s.risk_class == C.INTEREST_RATE:
        if measure == "VEGA":
            if rf not in ("IR_VOL", "INFLATION_VOL"):
                raise ValueError(f"IR vega risk factor must be IR_VOL/INFLATION_VOL, got {rf!r}")
            return p.SA_CVA_IR_VEGA_RW
        if _ir_specified(s.bucket, reporting_currency):
            if rf not in p.SA_CVA_IR_DELTA_RW_SPECIFIED:
                raise ValueError(f"unknown IR tenor {s.risk_factor!r} for {s.bucket}")
            return p.SA_CVA_IR_DELTA_RW_SPECIFIED[rf]
        if rf not in ("CURVE", "INFLATION"):
            raise ValueError(f"other-currency IR risk factor must be CURVE/INFLATION, got {rf!r}")
        return p.SA_CVA_IR_DELTA_RW_OTHER
    if s.risk_class == C.FX:
        if s.bucket.upper() == reporting_currency.upper():
            raise ValueError("FX buckets exclude the reporting currency (CAR s.8.3.6)")
        return p.SA_CVA_FX_VEGA_RW if measure == "VEGA" else p.SA_CVA_FX_DELTA_RW
    if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        if measure == "VEGA":
            raise ValueError("counterparty credit spread has no vega requirement (CAR s.8.3.4)")
        if rf not in p.SA_CVA_CCS_TENORS:
            raise ValueError(f"unknown counterparty credit spread tenor {s.risk_factor!r}")
        ig, hy = p.SA_CVA_CCS_RW[_ccs_rw_key(s.bucket)]
        if s.is_investment_grade is None:
            return hy
        return ig if s.is_investment_grade else hy
    if s.risk_class == C.REFERENCE_CREDIT_SPREAD:
        b = int(s.bucket)
        if b not in p.SA_CVA_RCS_RW:
            raise ValueError(f"unknown reference credit spread bucket {s.bucket!r}")
        return p.SA_CVA_RCS_VEGA_RW if measure == "VEGA" else p.SA_CVA_RCS_RW[b]
    if s.risk_class == C.EQUITY:
        b = int(s.bucket)
        if b not in p.SA_CVA_EQ_DELTA_RW:
            raise ValueError(f"unknown equity bucket {s.bucket!r}")
        if measure == "VEGA":
            return (p.SA_CVA_EQ_VEGA_RW_LARGE if b in p.SA_CVA_EQ_LARGE_CAP_BUCKETS
                    else p.SA_CVA_EQ_VEGA_RW_OTHER)
        return p.SA_CVA_EQ_DELTA_RW[b]
    b = int(s.bucket)
    if b not in p.SA_CVA_COM_DELTA_RW:
        raise ValueError(f"unknown commodity bucket {s.bucket!r}")
    return p.SA_CVA_COM_VEGA_RW if measure == "VEGA" else p.SA_CVA_COM_DELTA_RW[b]


def _ir_specified(currency: str, reporting_currency: str) -> bool:
    c = currency.upper()
    return c in p.SA_CVA_IR_SPECIFIED_CURRENCIES or c == reporting_currency.upper()


# -------------------------------------------------------------------------
#  Correlations
# -------------------------------------------------------------------------

def _sym(table: dict[tuple[str, str], float], a: str, b: str) -> float:
    if a == b:
        return 1.0
    return table.get((a, b), table.get((b, a), 0.0))


def _name_root(name: str) -> str:
    return name.split("::", 1)[0]


def rho(risk_class: CVARiskClass, measure: str, k: _Factor, l_: _Factor,
        specified: bool = True) -> float:
    """Within-bucket correlation rho_kl (CAR Ch.8 s.8.3.5-8.3.10 [MAR 50.56-50.77])."""
    if risk_class == C.INTEREST_RATE:
        if measure == "VEGA":
            return p.SA_CVA_IR_VEGA_CORR
        if specified:
            return _sym(p.SA_CVA_IR_DELTA_CORR_SPECIFIED, k.risk_factor, l_.risk_factor)
        return p.SA_CVA_IR_DELTA_CORR_OTHER
    if risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        r_tenor = 1.0 if k.risk_factor == l_.risk_factor else p.SA_CVA_CCS_RHO_TENOR_DIFF
        same_q = (k.ig is True) == (l_.ig is True)
        r_quality = 1.0 if same_q else p.SA_CVA_CCS_RHO_QUALITY_DIFF
        if k.bucket == "8":
            if k.name == l_.name:
                r_name = 1.0
            elif _name_root(k.name) == _name_root(l_.name):
                r_name = p.SA_CVA_CCS_IDX_RHO_NAME_SERIES
            else:
                r_name = p.SA_CVA_CCS_IDX_RHO_NAME_OTHER
        elif k.name == l_.name:
            r_name = 1.0
        elif _name_root(k.name) == _name_root(l_.name):
            r_name = p.SA_CVA_CCS_RHO_NAME_LEGAL
        else:
            r_name = p.SA_CVA_CCS_RHO_NAME_OTHER
        return r_tenor * r_name * r_quality
    # FX, RCS, equity, commodity: one risk factor per bucket
    return 1.0


def _ccs_gamma_key(bucket: str) -> str:
    return "1" if bucket.lower() in ("1a", "1b", "1") else bucket


def _rcs_sector(b: int) -> str:
    return str(b - 7) if 8 <= b <= 14 else str(b)


def gamma(risk_class: CVARiskClass, b: str, c: str) -> float:
    """Cross-bucket correlation gamma_bc (CAR Ch.8 s.8.3.5-8.3.10 [MAR 50.55-50.75])."""
    if risk_class == C.INTEREST_RATE:
        return p.SA_CVA_IR_GAMMA
    if risk_class == C.FX:
        return p.SA_CVA_FX_GAMMA
    if risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        return _sym(p.SA_CVA_CCS_GAMMA, _ccs_gamma_key(b), _ccs_gamma_key(c))
    ib, ic = int(b), int(c)
    if risk_class == C.REFERENCE_CREDIT_SPREAD:
        g = _sym(p.SA_CVA_RCS_GAMMA, _rcs_sector(ib), _rcs_sector(ic))
        if ib <= 14 and ic <= 14 and (ib <= 7) != (ic <= 7):
            g /= p.SA_CVA_RCS_DIFF_QUALITY_DIVISOR
        return g
    if risk_class == C.EQUITY:
        if 11 in (ib, ic):
            return p.SA_CVA_EQ_GAMMA_BUCKET_11
        idx = {12, 13}
        if ib in idx and ic in idx:
            return p.SA_CVA_EQ_GAMMA_12_13
        if ib in idx or ic in idx:
            return p.SA_CVA_EQ_GAMMA_IDX_VS_1_10
        return p.SA_CVA_EQ_GAMMA_1_10
    if 11 in (ib, ic):
        return p.SA_CVA_COM_GAMMA_BUCKET_11
    return p.SA_CVA_COM_GAMMA_1_10


# -------------------------------------------------------------------------
#  Aggregation
# -------------------------------------------------------------------------

def _bucket_key(s: CVASensitivityInput) -> str:
    if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        return _ccs_gamma_key(s.bucket)
    if s.risk_class in (C.INTEREST_RATE, C.FX):
        return s.bucket.upper()
    return str(int(s.bucket))


def _factor_key(s: CVASensitivityInput) -> tuple[str, str]:
    """Risk factor identity within a bucket (CAR s.8.3.5-8.3.10)."""
    if s.risk_class == C.INTEREST_RATE:
        return s.risk_factor.upper(), ""
    if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD:
        return s.risk_factor.upper(), s.name
    return "SINGLE", ""


def bucket_capital(risk_class: CVARiskClass, measure: str, factors: list[_Factor],
                   r: float, specified: bool = True) -> float:
    """K_b = sqrt((sum WS_k^2 + sum_{k != l} rho_kl WS_k WS_l) + R sum (WS_k^Hdg)^2).

    CAR Ch.8 s.8.3.4 [MAR 50.53(1)].
    """
    total = 0.0
    for i, k in enumerate(factors):
        for j, l_ in enumerate(factors):
            if i == j:
                total += k.ws * k.ws
            else:
                total += rho(risk_class, measure, k, l_, specified) * k.ws * l_.ws
    total += r * sum(f.ws_hdg * f.ws_hdg for f in factors)
    return math.sqrt(max(total, 0.0))


def class_capital(risk_class: CVARiskClass, measure: str, sens: list[CVASensitivityInput],
                  reporting_currency: str, m_cva: float, r: float) -> float:
    """K for one risk class and measure (CAR Ch.8 s.8.3.4 [MAR 50.53(2)-(3)])."""
    netted: dict[tuple[str, str, str, bool | None], list[float]] = defaultdict(
        lambda: [0.0, 0.0])
    for s in sens:
        rw = risk_weight(s, reporting_currency)
        rf, name = _factor_key(s)
        ig = s.is_investment_grade if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD else None
        acc = netted[(_bucket_key(s), rf, name, ig)]
        acc[0] += rw * s.s_cva
        acc[1] += rw * s.s_hedge
    buckets: dict[str, list[_Factor]] = defaultdict(list)
    for (b, rf, name, ig), (wc, wh) in netted.items():
        buckets[b].append(_Factor(bucket=b, risk_factor=rf, name=name, ig=ig,
                                  ws_cva=wc, ws_hdg=wh))
    kb: dict[str, float] = {}
    sb: dict[str, float] = {}
    for b, factors in buckets.items():
        spec = (risk_class != C.INTEREST_RATE) or _ir_specified(b, reporting_currency)
        k_b = bucket_capital(risk_class, measure, factors, r, spec)
        kb[b] = k_b
        sb[b] = max(-k_b, min(sum(f.ws for f in factors), k_b))
    total = sum(v * v for v in kb.values())
    names = list(kb)
    for i, b in enumerate(names):
        for j, c in enumerate(names):
            if i != j:
                total += gamma(risk_class, b, c) * sb[b] * sb[c]
    return m_cva * math.sqrt(max(total, 0.0))


def sa_cva(sensitivities: list[CVASensitivityInput], reporting_currency: str = "CAD",
           m_cva: float | None = None) -> SACVAResult:
    """SA-CVA capital (CAR Ch.8 s.8.3.4: simple sum of delta and vega capital by risk class).

    ``m_cva`` defaults to 1 (s.8.3.3); OSFI may require a higher value.
    """
    m = p.SA_CVA_M_CVA if m_cva is None else m_cva
    if m < p.SA_CVA_M_CVA:
        raise ValueError("m_CVA cannot be set below 1 (CAR s.8.3.3)")
    groups: dict[tuple[CVARiskClass, str], list[CVASensitivityInput]] = defaultdict(list)
    for s in sensitivities:
        measure = s.measure.upper()
        if measure not in ("DELTA", "VEGA"):
            raise ValueError(f"measure must be DELTA or VEGA, got {s.measure!r}")
        if s.risk_class == C.COUNTERPARTY_CREDIT_SPREAD and measure == "VEGA":
            raise ValueError("counterparty credit spread has no vega requirement (CAR s.8.3.4)")
        groups[(s.risk_class, measure)].append(s)
    k_by: dict[str, float] = {}
    for (rc, measure), sens in groups.items():
        k_by[f"{rc.value}_{measure}"] = class_capital(rc, measure, sens, reporting_currency, m,
                                                      p.SA_CVA_R)
    k_total = sum(k_by.values())
    return SACVAResult(
        jurisdiction=Jurisdiction.CA, k_by_class=k_by, k_total=k_total,
        rwa=p.CVA_RWA_MULTIPLIER * k_total, m_cva=m, r_hedging_disallowance=p.SA_CVA_R,
        citations={
            "aggregation": "CAR Ch.8 s.8.3.4 [MAR 50.42-50.53] (sqrt per MAR 50.53 formula)",
            "m_cva": "CAR Ch.8 s.8.3.3 (m_CVA = 1) [MAR 50.41]",
            "R": "CAR Ch.8 s.8.3.4 (R = 0.01) [MAR 50.53]",
            "interest_rate": "CAR Ch.8 s.8.3.5 Tables 3-4 [MAR 50.54-50.58]",
            "fx": "CAR Ch.8 s.8.3.6 (11% / 100%, gamma 0.6) [MAR 50.59-50.62]",
            "counterparty_credit_spread": "CAR Ch.8 s.8.3.7 Tables 5-7 [MAR 50.63-50.65]",
            "reference_credit_spread": "CAR Ch.8 s.8.3.8 Tables 8-10 [MAR 50.66-50.69]",
            "equity": "CAR Ch.8 s.8.3.9 Tables 11-12 (large cap >= CAD 2.5bn) [MAR 50.70-50.73]",
            "commodity": "CAR Ch.8 s.8.3.10 Tables 13-14 [MAR 50.74-50.77]",
            "rwa": "CAR Ch.8 s.8.1 (12.5 x capital) [MAR 50.1]",
        },
    )
