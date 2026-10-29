"""EU sensitivities-based method -- CRR Articles 325e-325h, 325ae-325ay (as amended by CRR3).

Aggregation (Article 325f(5)-(8), M8/C7):

    WS_k = RW_k * s_k
    K_b  = sqrt(max(0, Sum_k WS_k^2 + Sum_k Sum_{l!=k} rho_kl WS_k WS_l))
    K    = sqrt(Sum_b K_b^2 + Sum_b Sum_{c!=b} gamma_bc S_b S_c),   S_b = Sum_k WS_k
           (if the sum under the root is negative, S_b = max(min(Sum_k WS_k, K_b), -K_b))

Curvature (Article 325g, M12, rendered consolidated pp.426-429):

    CVR_k^+/- = -Sum_i CVR_ik^+/-  (the engine takes CVR^+/- inputs already signed this way)
    K_b^+/-   = sqrt(max(0, Sum_k max(CVR_k^+/-, 0)^2
                         + Sum_k Sum_{l!=k} rho_kl CVR_k CVR_l psi(CVR_k, CVR_l)))
    K_b       = max(K_b^+, K_b^-); ties -> K_b^+ if Sum CVR^+ > Sum CVR^-, else K_b^-
    'other' buckets (325g(5)): K_b = max(Sum_k max(CVR_k^+,0), Sum_k max(CVR_k^-,0))
    RCCR      = sqrt(max(0, Sum_b K_b^2 + Sum_b Sum_{c!=b} gamma_bc S_b S_c psi(S_b, S_c)))
    psi(x, y) = 0 if x < 0 and y < 0, else 1

Curvature correlations are the squares of the delta correlations (Article 325ay(5)). Vega
correlations follow Article 325ay(1)-(3); delta and vega are summed without diversification
(Article 325ay(4)).

Scenarios (Article 325h): medium (as specified), high (x 1,25, cap 100 %), low
(max(2 rho - 100 %; 75 % rho)); the scenario-specific requirements are summed across all risk
classes and measures and the highest total is the SBM requirement (Article 325h(3)-(4)).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.jurisdictions.eu.frtb import buckets as bk
from src.jurisdictions.eu.frtb import params as p
from src.jurisdictions.frtb_base import (
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
)

Attrs = dict[str, Any]
RhoFn = Callable[[str, Attrs, Attrs], float]
GammaFn = Callable[[str, str], float]


# =========================================================================
#  Scenario transforms -- Article 325h(2)
# =========================================================================


def scenario_correlation(value: float, scenario: str) -> float:
    """Apply the Article 325h(2) scenario to a correlation parameter.

    * MEDIUM: unchanged (325h(2)(a));
    * HIGH: min(1,25 x value, 100 %) (325h(2)(b));
    * LOW: max(2 x value - 100 %; 75 % x value) (325h(2)(c), M12).
    """
    if scenario == "HIGH":
        return min(p.SCENARIO_HIGH_MULTIPLIER * value, p.SCENARIO_CORRELATION_CAP)
    if scenario == "LOW":
        return max(
            p.SCENARIO_LOW_SLOPE * value - p.SCENARIO_LOW_INTERCEPT,
            p.SCENARIO_LOW_FLOOR_FACTOR * value,
        )
    return value


def psi(x: float, y: float) -> float:
    """psi(x, y) = 0 where x < 0 and y < 0, otherwise 1 (Article 325g(4), (6))."""
    return 0.0 if (x < 0.0 and y < 0.0) else 1.0


# =========================================================================
#  Delta intra-bucket correlations (medium scenario)
# =========================================================================


def girr_tenor_correlation(t_k: float, t_l: float) -> float:
    """max(exp(-theta |Tk - Tl| / min(Tk, Tl)); 40 %), theta = 3 % (Article 325af(2))."""
    if t_k == t_l:
        return 1.0
    val = math.exp(-p.GIRR_THETA * abs(t_k - t_l) / min(t_k, t_l))
    return max(val, p.GIRR_RHO_TENOR_FLOOR)


def rho_girr_delta(a: Attrs, b: Attrs) -> float:
    """GIRR delta rho within a currency bucket (Article 325af(1)-(5))."""
    if a["kind"] == "XCCY" or b["kind"] == "XCCY":
        return p.GIRR_RHO_XCCY
    if a["kind"] != b["kind"]:
        return p.GIRR_RHO_INFLATION
    if a["kind"] == "INF":
        return 1.0
    same_curve = a["curve"] == b["curve"]
    if a["tenor"] == b["tenor"]:
        return 1.0 if same_curve else p.GIRR_RHO_DIFFERENT_CURVE
    tenor_rho = girr_tenor_correlation(a["tenor"], b["tenor"])
    return tenor_rho if same_curve else tenor_rho * p.GIRR_RHO_DIFFERENT_CURVE


def rho_csr_nonsec(bucket: str, a: Attrs, b: Attrs) -> float:
    """rho = rho(name) x rho(tenor) x rho(basis) -- Article 325ai(1) (CRR3 point (172))."""
    if a["name"] == b["name"]:
        name = 1.0
    elif int(bucket) <= p.CSR_NONSEC_OTHER_BUCKET:
        name = p.CSR_RHO_NAME_DIFFERENT_1_18
    else:
        name = p.CSR_RHO_NAME_DIFFERENT_OTHER
    tenor = 1.0 if a["tenor"] == b["tenor"] else p.CSR_RHO_TENOR_DIFFERENT
    basis = 1.0 if a["basis"] == b["basis"] else p.CSR_RHO_BASIS_DIFFERENT
    return name * tenor * basis


def rho_csr_ctp(bucket: str, a: Attrs, b: Attrs) -> float:
    """Article 325al(1): as Article 325ai but rho(basis) = 99,00 %."""
    name = 1.0 if a["name"] == b["name"] else p.CSR_RHO_NAME_DIFFERENT_1_18
    tenor = 1.0 if a["tenor"] == b["tenor"] else p.CSR_RHO_TENOR_DIFFERENT
    basis = 1.0 if a["basis"] == b["basis"] else p.CSR_CTP_RHO_BASIS_DIFFERENT
    return name * tenor * basis


def rho_csr_sec(bucket: str, a: Attrs, b: Attrs) -> float:
    """rho = rho(tranche) x rho(tenor) x rho(basis) -- Article 325an(1)."""
    tranche = 1.0 if a["name"] == b["name"] else p.CSR_SEC_RHO_TRANCHE_DIFFERENT
    tenor = 1.0 if a["tenor"] == b["tenor"] else p.CSR_SEC_RHO_TENOR_DIFFERENT
    basis = 1.0 if a["basis"] == b["basis"] else p.CSR_SEC_RHO_BASIS_DIFFERENT
    return tranche * tenor * basis


def rho_equity(bucket: str, a: Attrs, b: Attrs) -> float:
    """Equity delta rho -- Article 325aq(1)-(4) (M12)."""
    bnum = int(bucket)
    same_name = a["name"] == b["name"]
    if same_name:
        return 1.0 if a["factor"] == b["factor"] else p.EQUITY_RHO_SPOT_REPO_SAME_NAME
    base = p.EQUITY_RHO_SPOT[bnum]
    if a["factor"] == b["factor"] == EquityRiskFactor.REPO.value and bnum in (12, 13):
        base = p.EQUITY_RHO_REPO_INDEX_BUCKETS
    if a["factor"] != b["factor"]:
        return base * p.EQUITY_RHO_SPOT_REPO_DIFF_NAME_FACTOR
    return base


def rho_commodity(bucket: str, a: Attrs, b: Attrs) -> float:
    """rho = rho(commodity) x rho(tenor) x rho(basis) -- Article 325at(2)-(3)."""
    commodity = 1.0 if a["name"] == b["name"] else p.COMMODITY_RHO[bucket]
    tenor = 1.0 if a["tenor"] == b["tenor"] else p.COMMODITY_RHO_TENOR_DIFFERENT
    basis = 1.0 if a["basis"] == b["basis"] else p.COMMODITY_RHO_BASIS_DIFFERENT
    return commodity * tenor * basis


def delta_rho(rc: FRTBRiskClass, bucket: str, a: Attrs, b: Attrs) -> float:
    """Medium-scenario delta rho for any risk class."""
    if rc == FRTBRiskClass.GIRR:
        return rho_girr_delta(a, b)
    if rc == FRTBRiskClass.CSR_NONSEC:
        return rho_csr_nonsec(bucket, a, b)
    if rc == FRTBRiskClass.CSR_SEC_CTP:
        return rho_csr_ctp(bucket, a, b)
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return rho_csr_sec(bucket, a, b)
    if rc == FRTBRiskClass.EQUITY:
        return rho_equity(bucket, a, b)
    if rc == FRTBRiskClass.COMMODITY:
        return rho_commodity(bucket, a, b)
    return 1.0  # FX: one risk factor per bucket (Article 325q(1))


def option_maturity_correlation(t_k: float, t_l: float) -> float:
    """exp(-alpha |Tk - Tl| / min(Tk, Tl)), alpha = 1 % (Article 325ay(1))."""
    if t_k == t_l:
        return 1.0
    return math.exp(-p.VEGA_ALPHA * abs(t_k - t_l) / min(t_k, t_l))


def vega_rho(rc: FRTBRiskClass, bucket: str, a: Attrs, b: Attrs) -> float:
    """Vega rho -- Article 325ay(1) (GIRR) and (2) (other classes).

    GIRR: min(rho(option maturity) x rho(underlying maturity), 1). Other classes:
    min(rho(DELTA) x rho(option maturity), 1), where rho(DELTA) is the delta correlation of the
    bucket evaluated with equal tenors (the option-maturity dimension replaces the tenor).
    """
    rho_opt = option_maturity_correlation(a["opt"], b["opt"])
    if rc == FRTBRiskClass.GIRR:
        rho_und = option_maturity_correlation(a["und"], b["und"])
        return min(rho_opt * rho_und, 1.0)
    da = {**a, "tenor": None}
    db = {**b, "tenor": None}
    return min(delta_rho(rc, bucket, da, db) * rho_opt, 1.0)


def curvature_rho(rc: FRTBRiskClass, bucket: str, a: Attrs, b: Attrs) -> float:
    """Curvature rho = (delta rho at curve level)^2 -- Article 325ay(5).

    Curvature risk factors are whole curves / names (Arts 325l(8)-(9), 325m(3)-(4), 325n(4),
    325o(4), 325p(4), 325q(3)), so tenor and basis components are 1.
    """
    da = {**a, "tenor": None, "basis": None, "factor": EquityRiskFactor.SPOT.value}
    db = {**b, "tenor": None, "basis": None, "factor": EquityRiskFactor.SPOT.value}
    return delta_rho(rc, bucket, da, db) ** 2


# =========================================================================
#  Inter-bucket correlations (medium scenario)
# =========================================================================


def _csr_rating_category(bucket: int) -> str:
    """Credit-quality category of a CSR bucket for gamma_bc(rating) (CRR3 point (173))."""
    if bucket in p.CSR_NONSEC_IG_BUCKETS or bucket == 19:
        return "IG"
    if bucket in p.CSR_NONSEC_HY_BUCKETS or bucket == 20:
        return "HY"
    return "OTHER"


def gamma_csr_rating(b: int, c: int) -> float:
    """gamma_bc(rating) -- Article 325aj as replaced by CRR3 point (173)(a)-(d).

    Bucket 1 counts as CQS 1-3. For points (c)/(d) the 'other bucket' credit quality is read from
    its bucket block (2-10, 19: CQS 1-3; 11-17, 20: CQS 4-6).
    # TODO: VERIFY -- points (c)/(d) do not say how bucket 1 is classed; it is treated as CQS 1-3.
    """
    if p.CSR_NONSEC_OTHER_BUCKET in (b, c):
        return 1.0  # point (b)
    if 19 in (b, c):
        other = c if b == 19 else b
        return 1.0 if _csr_rating_category(other) == "IG" else p.CSR_GAMMA_RATING_DIFFERENT
    if 20 in (b, c):
        other = c if b == 20 else b
        return 1.0 if _csr_rating_category(other) == "HY" else p.CSR_GAMMA_RATING_DIFFERENT
    same = _csr_rating_category(b) == _csr_rating_category(c)
    return 1.0 if same else p.CSR_GAMMA_RATING_DIFFERENT  # point (a)


def gamma_csr_sector(b: int, c: int) -> float:
    """gamma_bc(sector) -- Article 325aj Table 5 (M12)."""
    gb, gc = p.CSR_SECTOR_GROUP[b], p.CSR_SECTOR_GROUP[c]
    if gb == gc:
        return 1.0
    return p.CSR_SECTOR_GAMMA[(gb, gc)]


def gamma_csr_nonsec(b: int, c: int) -> float:
    """gamma_bc = gamma_bc(rating) x gamma_bc(sector) -- Article 325aj."""
    return gamma_csr_rating(b, c) * gamma_csr_sector(b, c)


def gamma_csr_ctp(b: int, c: int) -> float:
    """Article 325al(2): gamma as Article 325aj, on Table 6 buckets 1-18 (no index buckets)."""
    return gamma_csr_nonsec(b, c)


def gamma_equity(b: int, c: int) -> float:
    """Article 325ar (M12)."""
    if p.EQUITY_OTHER_BUCKET in (b, c):
        return p.EQUITY_GAMMA_OTHER_BUCKET
    if b <= 10 and c <= 10:
        return p.EQUITY_GAMMA_1_10
    if {b, c} == {12, 13}:
        return p.EQUITY_GAMMA_INDICES
    return p.EQUITY_GAMMA_OTHERWISE


def gamma_commodity(b: str, c: str) -> float:
    """Article 325au (buckets 3a/3b treated as within '1 to 10')."""
    if p.COMMODITY_OTHER_BUCKET in (b, c):
        return p.COMMODITY_GAMMA_OTHER
    return p.COMMODITY_GAMMA_1_10


# =========================================================================
#  Engine
# =========================================================================


@dataclass
class _Factor:
    bucket: str
    key: tuple[Any, ...]
    attrs: Attrs
    rw: float
    s: float = 0.0
    cvr_up: float = 0.0
    cvr_down: float = 0.0

    @property
    def ws(self) -> float:
        return self.rw * self.s


@dataclass
class SBMOutcome:
    """Per-scenario, per-class, per-measure SBM requirements."""

    by_scenario: dict[str, dict[FRTBRiskClass, dict[FRTBMeasure, float]]] = field(
        default_factory=dict
    )
    totals: dict[str, float] = field(default_factory=dict)
    binding_scenario: str = "MEDIUM"
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        """Highest scenario total (Article 325h(4))."""
        return self.totals.get(self.binding_scenario, 0.0)


_OTHER_BUCKETS: dict[FRTBRiskClass, str] = {
    FRTBRiskClass.CSR_NONSEC: str(p.CSR_NONSEC_OTHER_BUCKET),
    FRTBRiskClass.CSR_SEC_CTP: str(p.CSR_CTP_OTHER_BUCKET),
    FRTBRiskClass.CSR_SEC_NONCTP: str(p.CSR_SEC_NONCTP_OTHER_BUCKET),
    FRTBRiskClass.EQUITY: str(p.EQUITY_OTHER_BUCKET),
}
"""Buckets aggregated as Sum |WS_k| (Arts 325ai(2), 325an(2), 325aq(5)) and with the
curvature formula of Article 325g(5)."""


class EUSBMEngine:
    """EU ASA sensitivities-based method.

    Args:
        domestic_currency: institution's domestic currency (Article 325ae(3)).
        most_liquid_currencies: currencies in the Article 325bd(7)(b) sub-category.
        fx_curvature_divide_all: Article 325q(6) permission to divide all FX CVRs by 1,5.
    """

    def __init__(
        self,
        domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
        most_liquid_currencies: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
        fx_curvature_divide_all: bool = False,
    ) -> None:
        """Store the EU-specific configuration."""
        self.domestic_currency = domestic_currency.upper()
        self.most_liquid = frozenset(c.upper() for c in most_liquid_currencies)
        self.fx_curvature_divide_all = fx_curvature_divide_all

    # ------------------------------------------------------------------
    #  Factor construction
    # ------------------------------------------------------------------

    def _delta_attrs(self, s: FRTBSensitivity) -> tuple[tuple[Any, ...], Attrs]:
        """Risk-factor key and correlation attributes of a delta sensitivity."""
        rc = s.risk_class
        if rc == FRTBRiskClass.GIRR:
            if s.girr_curve == GIRRCurve.INFLATION:
                return ("INF",), {"kind": "INF", "curve": "", "tenor": None}
            if s.girr_curve == GIRRCurve.XCCY_BASIS:
                return ("XCCY", s.curve_name), {"kind": "XCCY", "curve": s.curve_name,
                                                "tenor": None}
            tenor = bk.snap(s.tenor_years or 0.0, p.GIRR_TENORS)
            return ("RF", s.curve_name, tenor), {"kind": "RF", "curve": s.curve_name,
                                                  "tenor": tenor}
        if rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
            tenor = bk.snap(s.tenor_years or 0.5, p.CSR_TENORS)
            name = s.issuer or s.label
            return (name, tenor, s.is_cds), {"name": name, "tenor": tenor, "basis": s.is_cds}
        if rc == FRTBRiskClass.CSR_SEC_NONCTP:
            tenor = bk.snap(s.tenor_years or 0.5, p.CSR_TENORS)
            name = s.tranche_id or s.label
            return (name, tenor, s.is_cds), {"name": name, "tenor": tenor, "basis": s.is_cds}
        if rc == FRTBRiskClass.EQUITY:
            name = s.issuer or s.label
            fac = s.equity_risk_factor.value
            return (name, fac), {"name": name, "factor": fac}
        if rc == FRTBRiskClass.COMMODITY:
            tenor = bk.snap(s.tenor_years or 0.25, p.COMMODITY_TENORS)
            name = s.commodity_name or s.label
            return (name, tenor, s.delivery_location), {
                "name": name, "tenor": tenor, "basis": s.delivery_location}
        return ("FX",), {}

    def _build(
        self, sens: list[FRTBSensitivity], notes: list[str]
    ) -> dict[tuple[FRTBRiskClass, FRTBMeasure], dict[str, dict[tuple[Any, ...], _Factor]]]:
        """Net sensitivities per (class, measure, bucket, risk factor) (Article 325f(5))."""
        out: dict[
            tuple[FRTBRiskClass, FRTBMeasure], dict[str, dict[tuple[Any, ...], _Factor]]
        ] = defaultdict(lambda: defaultdict(dict))
        for s in sens:
            rc, m = s.risk_class, s.measure
            bucket = bk.assign_bucket(s)
            key, attrs = self._delta_attrs(s)
            if m == FRTBMeasure.VEGA:
                if rc == FRTBRiskClass.EQUITY and s.equity_risk_factor == EquityRiskFactor.REPO:
                    notes.append(f"{s.label}: no vega for equity repo rates (Art 325o(3)); skipped")
                    continue
                opt = bk.snap(s.option_maturity_years or p.GIRR_VEGA_MATURITIES[-1],
                              p.GIRR_VEGA_MATURITIES)
                attrs = {**attrs, "opt": opt}
                if rc == FRTBRiskClass.GIRR:
                    und_raw = (
                        (s.underlying_maturity_years - (s.option_maturity_years or 0.0))
                        if s.underlying_maturity_years is not None
                        else opt
                    )
                    und = bk.snap(max(und_raw, 0.0), p.GIRR_VEGA_MATURITIES)
                    attrs = {"opt": opt, "und": und}
                    key = ("VEGA", opt, und)
                else:
                    if rc == FRTBRiskClass.COMMODITY:
                        # Article 325p(3): same commodity type and maturity = one risk factor
                        attrs = {**attrs, "basis": None}
                    key = (attrs.get("name", ""), attrs.get("basis"), attrs.get("factor"), opt)
                rw = bk.vega_risk_weight(s)
            elif m == FRTBMeasure.CURVATURE:
                if rc == FRTBRiskClass.GIRR and s.girr_curve != GIRRCurve.RISK_FREE:
                    notes.append(f"{s.label}: no curvature for inflation / xccy basis "
                                 "(Art 325l(9)); skipped")
                    continue
                if rc == FRTBRiskClass.EQUITY and s.equity_risk_factor == EquityRiskFactor.REPO:
                    notes.append(f"{s.label}: no curvature for equity repo (Art 325o(4)); "
                                 "skipped")
                    continue
                if rc == FRTBRiskClass.GIRR:
                    key = ("CURVE",)
                elif rc == FRTBRiskClass.FX:
                    key = ("FX",)
                else:
                    key = (attrs.get("name", ""),)
                rw = 0.0
            else:
                rw = bk.delta_risk_weight(s, self.domestic_currency, self.most_liquid)
            factors = out[(rc, m)][bucket]
            f = factors.get(key)
            if f is None:
                f = _Factor(bucket=bucket, key=key, attrs=attrs, rw=rw)
                factors[key] = f
            if m == FRTBMeasure.CURVATURE:
                up, dn = s.cvr_up or 0.0, s.cvr_down or 0.0
                if rc == FRTBRiskClass.FX and (
                    self.fx_curvature_divide_all or bk.flag(s, "fx_curvature_cross_pair")
                ):
                    up /= p.FX_CURVATURE_CROSS_DIVISOR
                    dn /= p.FX_CURVATURE_CROSS_DIVISOR
                f.cvr_up += up
                f.cvr_down += dn
            else:
                f.s += s.value
        return out

    # ------------------------------------------------------------------
    #  Gamma per class
    # ------------------------------------------------------------------

    def _gamma_fn(
        self, rc: FRTBRiskClass, bucket_flags: dict[str, set[str]]
    ) -> GammaFn:
        """Medium-scenario gamma_bc for a risk class."""
        if rc == FRTBRiskClass.GIRR:
            def g_girr(b: str, c: str) -> float:
                pair = {b, c}
                if "EUR" in pair:
                    other = c if b == "EUR" else b
                    if "erm2_narrow_band" in bucket_flags.get(other, set()):
                        return p.GIRR_GAMMA_ERM2_EUR
                return p.GIRR_GAMMA
            return g_girr
        if rc == FRTBRiskClass.CSR_NONSEC:
            return lambda b, c: gamma_csr_nonsec(int(b), int(c))
        if rc == FRTBRiskClass.CSR_SEC_CTP:
            return lambda b, c: gamma_csr_ctp(int(b), int(c))
        if rc == FRTBRiskClass.CSR_SEC_NONCTP:
            return lambda b, c: p.CSR_SEC_GAMMA
        if rc == FRTBRiskClass.EQUITY:
            return lambda b, c: gamma_equity(int(b), int(c))
        if rc == FRTBRiskClass.COMMODITY:
            return gamma_commodity
        return lambda b, c: p.FX_GAMMA

    # ------------------------------------------------------------------
    #  Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _bucket_k(fs: list[_Factor], rho: Callable[[Attrs, Attrs], float], other: bool) -> float:
        """K_b (Article 325f(7)); Sum |WS_k| for 'other' buckets."""
        if other:
            return sum(abs(f.ws) for f in fs)
        tot = sum(f.ws ** 2 for f in fs)
        for i, fk in enumerate(fs):
            for j, fl in enumerate(fs):
                if i != j:
                    tot += rho(fk.attrs, fl.attrs) * fk.ws * fl.ws
        return math.sqrt(max(tot, 0.0))

    @staticmethod
    def _across(
        kb: dict[str, float],
        sb: dict[str, float],
        gamma: GammaFn,
        linear: set[str],
    ) -> float:
        """Risk-class requirement (Article 325f(8)) with the alternative S_b specification.

        Buckets in ``linear`` (Article 325ao(2): bucket 25) are added outside the root.
        """
        inner = [b for b in kb if b not in linear]
        lin = sum(kb[b] for b in kb if b in linear)

        def total(s: dict[str, float]) -> float:
            t = sum(kb[b] ** 2 for b in inner)
            for b in inner:
                for c in inner:
                    if b != c:
                        t += gamma(b, c) * s[b] * s[c]
            return t

        t = total(sb)
        if t < 0.0:
            alt = {b: max(min(sb[b], kb[b]), -kb[b]) for b in inner}
            t = total(alt)
        return math.sqrt(max(t, 0.0)) + lin

    def _delta_vega(
        self,
        rc: FRTBRiskClass,
        m: FRTBMeasure,
        buckets: dict[str, dict[tuple[Any, ...], _Factor]],
        scenario: str,
        bucket_flags: dict[str, set[str]],
    ) -> float:
        """Delta or vega requirement of a class under a scenario (Articles 325f, 325h)."""
        other = _OTHER_BUCKETS.get(rc)
        g_med = self._gamma_fn(rc, bucket_flags)
        kb: dict[str, float] = {}
        sb: dict[str, float] = {}
        for b, facs in buckets.items():
            fs = list(facs.values())
            if m == FRTBMeasure.VEGA:
                def rho(x: Attrs, y: Attrs, _b: str = b) -> float:
                    return scenario_correlation(vega_rho(rc, _b, x, y), scenario)
            else:
                def rho(x: Attrs, y: Attrs, _b: str = b) -> float:
                    return scenario_correlation(delta_rho(rc, _b, x, y), scenario)
            kb[b] = self._bucket_k(fs, rho, other == b)
            sb[b] = sum(f.ws for f in fs)

        def gamma(b: str, c: str) -> float:
            return scenario_correlation(g_med(b, c), scenario)

        linear = {other} if (rc == FRTBRiskClass.CSR_SEC_NONCTP and other) else set()
        return self._across(kb, sb, gamma, linear)

    def _curvature(
        self,
        rc: FRTBRiskClass,
        buckets: dict[str, dict[tuple[Any, ...], _Factor]],
        scenario: str,
        bucket_flags: dict[str, set[str]],
    ) -> float:
        """Curvature requirement of a class under a scenario (Article 325g(4)-(6), 325ay(5))."""
        other = _OTHER_BUCKETS.get(rc)
        g_med = self._gamma_fn(rc, bucket_flags)
        kb: dict[str, float] = {}
        sb: dict[str, float] = {}
        for b, facs in buckets.items():
            fs = list(facs.values())
            sum_up = sum(f.cvr_up for f in fs)
            sum_dn = sum(f.cvr_down for f in fs)
            if other == b:
                kp = sum(max(f.cvr_up, 0.0) for f in fs)
                km = sum(max(f.cvr_down, 0.0) for f in fs)
            else:
                kp = self._k_curv(rc, b, fs, scenario, up=True)
                km = self._k_curv(rc, b, fs, scenario, up=False)
            if kp > km or (kp == km and sum_up > sum_dn):
                kb[b], sb[b] = kp, sum_up
            else:
                kb[b], sb[b] = km, sum_dn
        linear = {other} if (rc == FRTBRiskClass.CSR_SEC_NONCTP and other) else set()
        inner = [b for b in kb if b not in linear]
        tot = sum(kb[b] ** 2 for b in inner)
        for b in inner:
            for c in inner:
                if b != c:
                    gam = scenario_correlation(g_med(b, c) ** 2, scenario)
                    tot += gam * sb[b] * sb[c] * psi(sb[b], sb[c])
        return math.sqrt(max(tot, 0.0)) + sum(kb[b] for b in kb if b in linear)

    @staticmethod
    def _k_curv(
        rc: FRTBRiskClass, bucket: str, fs: list[_Factor], scenario: str, up: bool
    ) -> float:
        """K_b^+ or K_b^- (Article 325g(4))."""
        vals = [f.cvr_up if up else f.cvr_down for f in fs]
        tot = sum(max(v, 0.0) ** 2 for v in vals)
        for i, fk in enumerate(fs):
            for j, fl in enumerate(fs):
                if i != j:
                    rho = scenario_correlation(curvature_rho(rc, bucket, fk.attrs, fl.attrs),
                                               scenario)
                    tot += rho * vals[i] * vals[j] * psi(vals[i], vals[j])
        return math.sqrt(max(tot, 0.0))

    # ------------------------------------------------------------------
    #  Public
    # ------------------------------------------------------------------

    def compute(self, sensitivities: list[FRTBSensitivity]) -> SBMOutcome:
        """Run all classes, measures and the three scenarios (Article 325h)."""
        outcome = SBMOutcome()
        built = self._build(sensitivities, outcome.notes)
        bucket_flags: dict[FRTBRiskClass, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        for s in sensitivities:
            on = {k for k, v in s.flags.items() if v}
            if on:
                bucket_flags[s.risk_class][bk.assign_bucket(s)] |= on
        for scen in p.SCENARIOS:
            res: dict[FRTBRiskClass, dict[FRTBMeasure, float]] = defaultdict(dict)
            for (rc, m), buckets in built.items():
                if m == FRTBMeasure.CURVATURE:
                    val = self._curvature(rc, buckets, scen, bucket_flags[rc])
                else:
                    val = self._delta_vega(rc, m, buckets, scen, bucket_flags[rc])
                res[rc][m] = val
            outcome.by_scenario[scen] = dict(res)
            outcome.totals[scen] = sum(sum(v.values()) for v in res.values())
        if outcome.totals:
            outcome.binding_scenario = max(
                p.SCENARIOS, key=lambda sc: (outcome.totals[sc], sc == "MEDIUM")
            )
        return outcome
