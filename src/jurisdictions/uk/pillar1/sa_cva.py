"""UK SA-CVA -- PRA Rulebook Credit Valuation Adjustment Risk Part, Chapter 5.

Rules 5.14-5.30 of PS1/26 Appendix 1 Annex K (p. 408-422):

* WS_k = RW_k s_k^CVA - RW_k s_k^Hdg                                (rules 5.22-5.23)
* K_b = sqrt( (sum WS_k^2 + sum_{k != l} rho_kl WS_k WS_l) + R sum (WS_k^Hdg)^2 ),
  R = 0.01                                                         (rule 5.24(1))
* K = m_CVA sqrt( sum K_b^2 + sum_{b != c} gamma_bc S_b S_c ),
  S_b = max{-K_b; min(sum WS_k; K_b)}, m_CVA = 1                    (rule 5.24(2))
* own funds requirement = sum over risk classes of delta K (six classes, rule 5.15)
  plus vega K (five classes -- no counterparty credit spread vega, rule 5.17).

Input conventions (``CVASensitivityInput``):

* ``measure``: 'DELTA' or 'VEGA'.
* Interest rate: ``bucket`` = currency; ``risk_factor`` = '1Y', '2Y', '5Y', '10Y',
  '30Y', 'INFLATION' (USD/EUR/GBP/AUD/CAD/SEK/JPY) or 'CURVE', 'INFLATION' (other
  currencies); vega 'IR_VOL' / 'INFLATION_VOL'.
* FX: ``bucket`` = currency (one risk factor per bucket).
* Counterparty credit spread: ``bucket`` = '1a', '1b', '2a', '2b', '3' ... '8';
  ``risk_factor`` = tenor ('0.5Y', '1Y', '3Y', '5Y', '10Y'); ``name`` = counterparty,
  reference name or index; ``is_investment_grade`` (None = not rated). Names written
  'GROUP/ENTITY' are 'distinct, but legally related' when the GROUP parts match; for
  bucket 8 'INDEX/SERIES' is 'the same, but of distinct series'.
* Reference credit spread, equity, commodity: ``bucket`` = bucket number; one risk
  factor per bucket (rules 5.28(3), 5.29(3), 5.30(3)-(4)), so sensitivities within a
  bucket are netted.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Final

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import CVARiskClass, CVASensitivityInput, SACVAResult
from src.jurisdictions.uk import params as uk
from src.jurisdictions.uk.pillar1 import params as p

DELTA: Final[str] = "DELTA"
VEGA: Final[str] = "VEGA"

# A risk factor within a bucket: (risk_factor, name, is_investment_grade)
FactorKey = tuple[str, str, bool | None]


class _Factor:
    """Net weighted sensitivities of one risk factor (rules 5.22-5.23)."""

    __slots__ = ("key", "ws", "ws_hedge")

    def __init__(self, key: FactorKey) -> None:
        self.key = key
        self.ws = 0.0
        self.ws_hedge = 0.0


# =========================================================================
#  Risk weights -- rules 5.25-5.30
# =========================================================================


def _int_bucket(bucket: str, valid: range) -> int:
    """Parse a numeric bucket label."""
    try:
        b = int(bucket)
    except ValueError as exc:
        raise ValueError(f"bucket must be a number, got {bucket!r}") from exc
    if b not in valid:
        raise ValueError(f"bucket {b} outside {valid.start}-{valid.stop - 1}")
    return b


def risk_weight(s: CVASensitivityInput) -> float:
    """RW_k for one sensitivity -- rules 5.25(5),(8),(12); 5.26(5),(8); 5.27(5);
    5.28(5),(8); 5.29(6),(9); 5.30(6),(8)."""
    m = s.measure.upper()
    rc = s.risk_class
    if rc is CVARiskClass.INTEREST_RATE:
        if m == VEGA:
            return p.IR_VEGA_RW
        if s.bucket.upper() in p.IR_SPECIFIED_CURRENCIES:
            return p.IR_DELTA_RW[s.risk_factor.upper()]
        return p.IR_OTHER_CCY_RW
    if rc is CVARiskClass.FX:
        return p.FX_VEGA_RW if m == VEGA else p.FX_DELTA_RW
    if rc is CVARiskClass.COUNTERPARTY_CREDIT_SPREAD:
        if m == VEGA:
            raise ValueError("no counterparty credit spread vega risk class (rule 5.17)")
        ig, hy = p.CCS_RW[s.bucket.upper()]
        return ig if s.is_investment_grade else hy
    if rc is CVARiskClass.REFERENCE_CREDIT_SPREAD:
        b = _int_bucket(s.bucket, range(1, 18))
        return p.RCS_VEGA_RW if m == VEGA else p.RCS_RW[b]
    if rc is CVARiskClass.EQUITY:
        b = _int_bucket(s.bucket, range(1, 14))
        if m == VEGA:
            return p.EQ_VEGA_RW_LARGE if b in p.EQ_LARGE_CAP_BUCKETS else p.EQ_VEGA_RW_OTHER
        return p.EQ_DELTA_RW[b]
    b = _int_bucket(s.bucket, range(1, 12))
    return p.COM_VEGA_RW if m == VEGA else p.COM_DELTA_RW[b]


# =========================================================================
#  Intra-bucket correlations
# =========================================================================


def _split(name: str) -> tuple[str, str]:
    """'GROUP/ENTITY' -> (GROUP, ENTITY); a plain name is its own group."""
    if "/" in name:
        g, e = name.split("/", 1)
        return g.strip().upper(), e.strip().upper()
    return name.strip().upper(), ""


def ccs_rho(k: FactorKey, l_: FactorKey, index_bucket: bool) -> float:
    """rho_kl = rho_tenor * rho_name * rho_quality -- rule 5.27(6) (buckets 1-7) and
    5.27(7) (bucket 8, qualified indices)."""
    rho_tenor = 1.0 if k[0] == l_[0] else p.CCS_RHO_TENOR_DIFFERENT
    gk, ek = _split(k[1])
    gl, el = _split(l_[1])
    if (gk, ek) == (gl, el):
        rho_name = 1.0
    elif gk == gl:
        rho_name = (p.CCS_INDEX_RHO_NAME_DIFFERENT_SERIES if index_bucket
                    else p.CCS_RHO_NAME_LEGALLY_RELATED)
    else:
        rho_name = p.CCS_INDEX_RHO_NAME_DIFFERENT if index_bucket else p.CCS_RHO_NAME_DIFFERENT
    rho_quality = 1.0 if bool(k[2]) == bool(l_[2]) else p.CCS_RHO_QUALITY_DIFFERENT
    return rho_tenor * rho_name * rho_quality


def ir_rho(k: FactorKey, l_: FactorKey, measure: str, currency: str) -> float:
    """IR intra-bucket correlation -- rule 5.25(6) table, (9) other currencies 40%,
    (13) vega 40%."""
    a, b = k[0].upper(), l_[0].upper()
    if a == b:
        return 1.0
    if measure == VEGA:
        return p.IR_VEGA_CORRELATION
    if currency.upper() in p.IR_SPECIFIED_CURRENCIES:
        return p.IR_DELTA_CORRELATION[(a, b)]
    return p.IR_OTHER_CCY_CORRELATION


# =========================================================================
#  Cross-bucket correlations
# =========================================================================


def _ccs_bucket_number(bucket: str) -> int:
    """'1a' -> 1, '2b' -> 2, '3' -> 3 (rule 5.27(2) table is by bucket number)."""
    return int(bucket.strip().upper().rstrip("AB"))


def _rcs_column(b: int) -> str:
    """Rule 5.28(2)(a) column label: '1/8' -> '1', ..., '7/14' -> '7'; 15-17 as is."""
    return str(b - 7) if 8 <= b <= 14 else str(b)


def rcs_gamma(b: int, c: int) -> float:
    """Reference credit spread gamma_bc -- rule 5.28(2)(a) table; (b) divided by 2 between
    buckets 1-14 of different credit quality."""
    cb, cc = _rcs_column(b), _rcs_column(c)
    g = 1.0 if cb == cc else p.RCS_CROSS_BUCKET_SAME_QUALITY[(cb, cc)]
    both_1_14 = b <= 14 and c <= 14
    different_quality = (b in p.RCS_IG_BUCKETS) != (c in p.RCS_IG_BUCKETS)
    if both_1_14 and different_quality:
        g /= p.RCS_DIFFERENT_QUALITY_DIVISOR
    return g


def equity_gamma(b: int, c: int) -> float:
    """Equity gamma_bc -- rule 5.29(4)(a)-(d)."""
    if 11 in (b, c):
        return p.EQ_GAMMA_BUCKET_11
    idx = {12, 13}
    if b in idx and c in idx:
        return p.EQ_GAMMA_12_13
    if b in idx or c in idx:
        return p.EQ_GAMMA_INDEX_VS_1_10
    return p.EQ_GAMMA_WITHIN_1_10


def commodity_gamma(b: int, c: int) -> float:
    """Commodity gamma_bc -- rule 5.30(2)(a)-(b)."""
    return p.COM_GAMMA_BUCKET_11 if 11 in (b, c) else p.COM_GAMMA_WITHIN_1_10


def gamma(risk_class: CVARiskClass, b: str, c: str) -> float:
    """Cross-bucket correlation for a risk class (rules 5.25(2)-5.30(2))."""
    if risk_class is CVARiskClass.INTEREST_RATE:
        return p.IR_CROSS_BUCKET
    if risk_class is CVARiskClass.FX:
        return p.FX_CROSS_BUCKET
    if risk_class is CVARiskClass.COUNTERPARTY_CREDIT_SPREAD:
        nb, nc = _ccs_bucket_number(b), _ccs_bucket_number(c)
        return 1.0 if nb == nc else p.CCS_CROSS_BUCKET[(nb, nc)]
    if risk_class is CVARiskClass.REFERENCE_CREDIT_SPREAD:
        return rcs_gamma(int(b), int(c))
    if risk_class is CVARiskClass.EQUITY:
        return equity_gamma(int(b), int(c))
    return commodity_gamma(int(b), int(c))


# =========================================================================
#  Aggregation -- rule 5.24
# =========================================================================


def _factor_key(s: CVASensitivityInput) -> FactorKey:
    """Risk-factor identity within a bucket (single-factor classes collapse to one key)."""
    rc = s.risk_class
    if rc is CVARiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return (s.risk_factor.upper(), s.name, s.is_investment_grade)
    if rc is CVARiskClass.INTEREST_RATE:
        return (s.risk_factor.upper(), "", None)
    return ("BUCKET", "", None)


def bucket_capital(
    factors: Sequence[_Factor], rho: Callable[[FactorKey, FactorKey], float]
) -> tuple[float, float]:
    """K_b and sum WS_k for one bucket -- rule 5.24(1)."""
    sq = sum(f.ws * f.ws for f in factors)
    cross = 0.0
    for i, fk in enumerate(factors):
        for j, fl in enumerate(factors):
            if i != j:
                cross += rho(fk.key, fl.key) * fk.ws * fl.ws
    hedge = p.SA_CVA_R * sum(f.ws_hedge * f.ws_hedge for f in factors)
    return math.sqrt(max(sq + cross + hedge, 0.0)), sum(f.ws for f in factors)


def _rho_for(
    risk_class: CVARiskClass, measure: str, bucket: str
) -> Callable[[FactorKey, FactorKey], float]:
    """Intra-bucket correlation function for one bucket (rules 5.25(6),(9),(13), 5.27(6)-(7));
    the other classes have a single risk factor per bucket."""
    if risk_class is CVARiskClass.COUNTERPARTY_CREDIT_SPREAD:
        index_bucket = _ccs_bucket_number(bucket) == 8
        return lambda k, l_: ccs_rho(k, l_, index_bucket)
    if risk_class is CVARiskClass.INTEREST_RATE:
        return lambda k, l_: ir_rho(k, l_, measure, bucket)
    return lambda k, l_: 1.0


def class_capital(
    risk_class: CVARiskClass, measure: str, sens: Sequence[CVASensitivityInput]
) -> float:
    """K for one risk class and measure -- rule 5.24(2) with m_CVA = 1."""
    buckets: dict[str, dict[FactorKey, _Factor]] = defaultdict(dict)
    for s in sens:
        bkey = s.bucket.strip().upper()
        fk = _factor_key(s)
        f = buckets[bkey].setdefault(fk, _Factor(fk))
        rw = risk_weight(s)
        f.ws += rw * s.s_cva - rw * s.s_hedge
        f.ws_hedge += rw * s.s_hedge
    kb: dict[str, float] = {}
    sb: dict[str, float] = {}
    for bkey, fmap in buckets.items():
        k_b, ws_sum = bucket_capital(list(fmap.values()), _rho_for(risk_class, measure, bkey))
        kb[bkey] = k_b
        sb[bkey] = max(-k_b, min(ws_sum, k_b))
    total = sum(v * v for v in kb.values())
    keys = list(kb)
    for b in keys:
        for c in keys:
            if b != c:
                total += gamma(risk_class, b, c) * sb[b] * sb[c]
    return p.SA_CVA_M * math.sqrt(max(total, 0.0))


def sa_cva_capital(sensitivities: list[CVASensitivityInput]) -> SACVAResult:
    """SA-CVA own funds requirement and RWEA -- rules 5.14-5.24; RWEA = 12.5 x K
    (Required Level of Own Funds (CRR) Part Art 92(4)(b))."""
    groups: dict[tuple[CVARiskClass, str], list[CVASensitivityInput]] = defaultdict(list)
    for s in sensitivities:
        m = s.measure.upper()
        if m not in (DELTA, VEGA):
            raise ValueError(f"measure must be DELTA or VEGA, got {s.measure!r}")
        if m == VEGA and s.risk_class is CVARiskClass.COUNTERPARTY_CREDIT_SPREAD:
            raise ValueError("no counterparty credit spread vega risk class (rule 5.17)")
        groups[(s.risk_class, m)].append(s)
    k_by_class: dict[str, float] = {}
    for (rc, m), sens in groups.items():
        k_by_class[f"{rc.value}_{m}"] = class_capital(rc, m, sens)
    k_total = sum(k_by_class.values())
    return SACVAResult(
        jurisdiction=Jurisdiction.UK,
        k_by_class=k_by_class,
        k_total=k_total,
        rwa=uk.OWN_FUNDS_TO_RWA_MULTIPLIER * k_total,
        m_cva=p.SA_CVA_M,
        r_hedging_disallowance=p.SA_CVA_R,
        citations={
            "structure": f"{p.CVA} rules 5.14-5.17 (delta: six risk classes; vega: five)",
            "weighted_sensitivity": f"{p.CVA} rules 5.22-5.23",
            "aggregation": f"{p.CVA} rule 5.24(1)-(2) (R = 0.01, m_CVA = 1)",
            "INTEREST_RATE": f"{p.CVA} rule 5.25",
            "FX": f"{p.CVA} rule 5.26",
            "COUNTERPARTY_CREDIT_SPREAD": f"{p.CVA} rule 5.27",
            "REFERENCE_CREDIT_SPREAD": f"{p.CVA} rule 5.28",
            "EQUITY": f"{p.CVA} rule 5.29",
            "COMMODITY": f"{p.CVA} rule 5.30",
            "rwa": "Required Level of Own Funds (CRR) Part Art 92(4)(b) (x 12.5)",
        },
    )
