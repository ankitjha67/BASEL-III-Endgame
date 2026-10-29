"""UK securitisation framework -- PRA Rulebook Securitisation (CRR) Part, Arts 242-270F.

Hierarchy (Art 254(1)): SEC-IRBA where the Art 258 conditions are met; otherwise
SEC-SA; otherwise SEC-ERBA for rated positions (or positions with an inferred
rating); otherwise 1250% (Art 254(7)). This is the CRR ordering (SEC-SA ahead of
SEC-ERBA), not the BCBS CRE40.41-40.45 ordering. Overrides:

* Art 254(2): a rated (or inferred-rated) position uses SEC-ERBA instead of
  SEC-SA where SEC-SA gives > 25% (STS), or SEC-SA > 25% or SEC-ERBA > 75%
  (non-STS), or the pool is auto loans / auto leases / equipment leases.
* Art 254(5) / 265 / 266: the Internal Assessment Approach for unrated ABCP
  positions with 138BA permission -- internal grade mapped to an ECAI-equivalent
  credit quality step and risk-weighted under Art 263 / 264.
* Art 254(6) / 269: resecuritisations use SEC-SA with W = 0, p = 1.5 and a 100%
  floor; the Art 267-268 caps do not apply.
* Art 269A: NPE securitisations -- the governing Non-Performing Exposures
  Securitisation (CRR) Part was not supplied; BCBS CRE45.4-45.5 placeholders.

``SecTrancheInput.flags`` keys read here (all default False unless noted):

``sec_irba_precluded`` (Art 258(2)), ``sec_sa_precluded`` (Art 254(4)),
``iaa_permission`` and ``abcp`` (Art 254(5), 265(1)), ``iaa_ig_at_first_assignment``
(Art 266(2), default True), ``auto_or_equipment_lease_pool`` (Art 254(2)(c)),
``sec_sa_calculate_p`` (Art 261(1) / 262 optional p formula), ``k_sa_excludes_defaults``
(K_SAE variant of Art 261(2)), ``delinquency_unknown_over_5pct`` (Art 261(2)),
``look_through`` (Art 267, senior only), ``art270_sme_senior`` (Art 270),
``npe_traditional_nrppd_ge_50pct`` (CRE45.5 placeholder).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import SecApproachUsed, SecResultRow, SecTrancheInput
from src.jurisdictions.uk.pillar1 import params as p

# =========================================================================
#  Common parameters -- Arts 255-257
# =========================================================================


def tranche_maturity_from_legal(final_legal_maturity_years: float) -> float:
    """M_T from final legal maturity -- Art 257(1)(b), (2): 1 + (M_L - 1) * 80%, in [1, 5]."""
    mt = 1.0 + (final_legal_maturity_years - 1.0) * p.TRANCHE_MATURITY_LEGAL_SCALAR
    return clamp_maturity(mt)


def tranche_maturity_from_cash_flows(cash_flows: Sequence[tuple[float, float]]) -> float:
    """M_T = sum(t * CF_t) / sum(CF_t), floored at 1 and capped at 5 -- Art 257(1)(a), (2)."""
    total = sum(cf for _, cf in cash_flows)
    if total <= 0.0:
        raise ValueError("cash flows must sum to a positive amount")
    return clamp_maturity(sum(t * cf for t, cf in cash_flows) / total)


def clamp_maturity(m_t: float) -> float:
    """Art 257(2): floor of one year and cap of five years."""
    return min(max(m_t, p.TRANCHE_MATURITY_FLOOR_YEARS), p.TRANCHE_MATURITY_CAP_YEARS)


def effective_number(eads: Sequence[float]) -> float:
    """N = (sum EAD_i)^2 / sum EAD_i^2 -- Art 259(4) / 261(1)(c)."""
    s = sum(eads)
    s2 = sum(e * e for e in eads)
    if s2 <= 0.0:
        raise ValueError("pool must contain a positive exposure")
    return s * s / s2


def simplified_n(c1: float, cm: float | None = None, m: int | None = None) -> float:
    """Simplified N -- Art 259(6) / 261(1)(d), permitted only where C_1 <= 3%.

    N = (C_1 * C_m + (C_m - C_1)/(m - 1) * max{1 - m * C_1, 0})^-1, or N = 1/C_1 where only
    C_1 is available.
    """
    if c1 > p.SIMPLIFIED_N_MAX_C1:
        raise ValueError("simplified method requires C_1 <= 3%")
    if cm is None or m is None:
        return 1.0 / c1
    if m < 2:
        raise ValueError("m must be at least 2")
    return 1.0 / (c1 * cm + (cm - c1) / (m - 1) * max(1.0 - m * c1, 0.0))


def weighted_lgd(pairs: Sequence[tuple[float, float]]) -> float:
    """Exposure-weighted LGD = sum LGD_i * EAD_i / sum EAD_i -- Art 259(5) / 261(1)(b)."""
    total = sum(e for _, e in pairs)
    if total <= 0.0:
        raise ValueError("pool must contain a positive exposure")
    return sum(lgd * e for lgd, e in pairs) / total


def sec_sa_pool_lgd(exposures: Sequence[tuple[str, float]]) -> float:
    """SEC-SA pool LGD from the Art 261(1)(a) exposure-type table (keys of
    :data:`params.SEC_SA_LGD_TABLE`), weighted by EAD per Art 261(1)(b)."""
    return weighted_lgd([(p.SEC_SA_LGD_TABLE[t], e) for t, e in exposures])


def k_a(k_sa: float, w: float) -> float:
    """K_A = (1 - W) * K_SA + W * 0.5 -- Art 261(2) (K_SAE in place of K_SA under (i))."""
    return (1.0 - w) * k_sa + w * p.K_A_DEFAULTED_WEIGHT


def k_a_partially_unknown(ead_known: float, k_known: float, ead_unknown: float) -> float:
    """K_A where delinquency status is unknown for <= 5% of the pool -- Art 261(2):
    K_A = (EAD_known * K_known + EAD_unknown) / EAD_total."""
    total = ead_known + ead_unknown
    if total <= 0.0:
        raise ValueError("pool must contain a positive exposure")
    if ead_unknown / total > p.UNKNOWN_DELINQUENCY_MAX_SHARE:
        raise ValueError("delinquency unknown for more than 5%: Art 261(2) requires 1250%")
    return (ead_known * k_known + ead_unknown) / total


def k_pool(d_share: float, k_irb: float, k_a_value: float) -> float:
    """K_POOL = d * K_IRB + (1 - d) * K_A for a mixed pool -- Art 259(7); requires
    d >= 95% (Art 258(1)(a)). For an IRB pool, K_POOL = K_IRB."""
    if d_share < p.MIXED_POOL_MIN_KIRB_SHARE:
        raise ValueError("SEC-IRBA requires K_IRB on at least 95% of the pool (Art 258(1)(a))")
    return d_share * k_irb + (1.0 - d_share) * k_a_value


# =========================================================================
#  Supervisory parameter p and K_SSFA -- Arts 259-262
# =========================================================================


def p_parameter_row(
    is_retail: bool, is_senior: bool, n: float
) -> tuple[str, tuple[float, float, float, float, float]]:
    """Look-up of (A, B, C, D, E) -- Art 259(1) / 261(1) table."""
    if is_retail:
        key = "RETAIL_SENIOR" if is_senior else "RETAIL_NON_SENIOR"
    else:
        seniority = "SENIOR" if is_senior else "NON_SENIOR"
        granular = "GRANULAR" if n >= p.GRANULARITY_THRESHOLD_N else "NON_GRANULAR"
        key = f"NON_RETAIL_{seniority}_{granular}"
    return key, p.P_PARAMETER_TABLE[key]


def _p_linear(
    is_retail: bool, is_senior: bool, n: float, k: float, lgd: float, m_t: float
) -> float:
    """A + B * (1/N) + C * K + D * LGD + E * M_T (Art 259(1) / 261(1))."""
    _, (a_, b_, c_, d_, e_) = p_parameter_row(is_retail, is_senior, n)
    return a_ + b_ / n + c_ * k + d_ * lgd + e_ * clamp_maturity(m_t)


def p_irba(
    is_retail: bool, is_senior: bool, n: float, k_irb: float, lgd: float, m_t: float,
    sts: bool = False,
) -> float:
    """SEC-IRBA p -- Art 259(1): max[0.3, (...)]; Art 260 (STS): max[0.3, 0.5 * (...)]."""
    lin = _p_linear(is_retail, is_senior, n, k_irb, lgd, m_t)
    scalar = p.IRBA_STS_P_SCALAR if sts else 1.0
    return max(p.IRBA_P_FLOOR, scalar * lin)


def p_sec_sa(
    is_retail: bool, is_senior: bool, n: float, k_a_value: float, lgd: float, m_t: float,
    sts: bool = False,
) -> float:
    """SEC-SA p by formula -- Art 261(1): min[1, max[0.5, (...)]];
    Art 262 (STS): min[0.5, max[0.3, 0.5 * (...)]]."""
    lin = _p_linear(is_retail, is_senior, n, k_a_value, lgd, m_t)
    if sts:
        return min(p.SEC_SA_STS_P_MAX, max(p.SEC_SA_STS_P_MIN, p.SEC_SA_STS_P_SCALAR * lin))
    return min(p.SEC_SA_P_MAX, max(p.SEC_SA_P_MIN, lin))


def k_ssfa(k: float, a: float, d: float, p_value: float) -> float:
    """K_SSFA = (e^(a u) - e^(a l)) / (a (u - l)), a = -1/(p K), u = D - K, l = max(A - K, 0)
    -- Art 259(1) (K_POOL) / Art 261(1) (K_A)."""
    if k <= 0.0:
        return 0.0
    a_ = -1.0 / (p_value * k)
    u = d - k
    l_ = max(a - k, 0.0)
    if u <= l_:
        return math.exp(a_ * u)
    return (math.exp(a_ * u) - math.exp(a_ * l_)) / (a_ * (u - l_))


def ssfa_risk_weight(k: float, a: float, d: float, p_value: float) -> float:
    """Piecewise SSFA risk weight before floors -- Art 259(1) / 261(1).

    1250% when D <= K; 12.5 * K_SSFA when D > A >= K; blended
    [12.5 (K - A)/(D - A)] + [12.5 K_SSFA (D - K)/(D - A)] when A < K < D;
    12.5 e^(a u) when K < A = D.
    """
    if d <= k:
        return p.SEC_RW_MAX
    if d == a:
        return p.SEC_K_SCALAR * k_ssfa(k, a, d, p_value)
    ks = k_ssfa(k, a, d, p_value)
    if a >= k:
        return p.SEC_K_SCALAR * ks
    return p.SEC_K_SCALAR * (k - a) / (d - a) + p.SEC_K_SCALAR * ks * (d - k) / (d - a)


# =========================================================================
#  Approaches
# =========================================================================


def _senior_floor(t: SecTrancheInput, sts: bool, floor: float) -> float:
    """15% floor; 10% for senior STS positions (Arts 259(1), 260, 261(1), 262)."""
    return p.STS_SENIOR_RW_FLOOR if (sts and t.is_senior) else floor


def sec_irba_rw(t: SecTrancheInput, sts: bool) -> tuple[float, str, list[str]]:
    """SEC-IRBA risk weight -- Art 259 (Art 260 for STS). ``k_irb`` is K_POOL (pass
    :func:`k_pool` for a mixed pool)."""
    if t.k_irb is None or t.n_effective is None or t.lgd_pool is None:
        raise ValueError("SEC-IRBA requires k_irb, n_effective and lgd_pool")
    pv = p_irba(t.is_retail_pool, t.is_senior, t.n_effective, t.k_irb, t.lgd_pool,
                t.maturity_years, sts=sts)
    rw = ssfa_risk_weight(t.k_irb, t.attachment, t.detachment, pv)
    floor = _senior_floor(t, sts, p.SEC_IRBA_RW_FLOOR)
    cite = f"{p.SEC} Art 259(1)" + ("; Art 260 (STS)" if sts else "")
    return max(rw, floor), cite, [f"K_POOL={t.k_irb:.4f}, p={pv:.4f}, floor={floor:.0%}"]


def sec_sa_rw(t: SecTrancheInput, sts: bool, resec: bool = False) -> tuple[float, str, list[str]]:
    """SEC-SA risk weight -- Art 261 (Art 262 for STS; Art 269 for resecuritisations)."""
    if t.k_sa is None:
        raise ValueError("SEC-SA requires k_sa")
    notes: list[str] = []
    w = p.RESEC_W if resec else t.w
    ka = k_a(t.k_sa, w)
    if resec:
        pv = p.RESEC_P
        cite = f"{p.SEC} Art 261(1), Art 269(1)(a)-(c) (resecuritisation: W=0, p=1.5, floor 100%)"
    elif t.flags.get("sec_sa_calculate_p", False):
        if t.n_effective is None or t.lgd_pool is None:
            raise ValueError("SEC-SA p formula requires n_effective and lgd_pool")
        pv = p_sec_sa(t.is_retail_pool, t.is_senior, t.n_effective, ka, t.lgd_pool,
                      t.maturity_years, sts=sts)
        cite = f"{p.SEC} Art 261(1) (p by formula)" + ("; Art 262 (STS)" if sts else "")
    else:
        pv = p.SEC_SA_STS_P_DEFAULT if sts else p.SEC_SA_P_DEFAULT
        cite = f"{p.SEC} Art 261(1) (p = {pv})" + ("; Art 262 (STS)" if sts else "")
    rw = ssfa_risk_weight(ka, t.attachment, t.detachment, pv)
    floor = p.RESEC_RW_FLOOR if resec else _senior_floor(t, sts, p.SEC_SA_RW_FLOOR)
    notes.append(f"K_A={ka:.4f} (W={w:.2%}), p={pv:.4f}, floor={floor:.0%}")
    return max(rw, floor), cite, notes


def normalise_rating(rating: str) -> str:
    """Upper-case and strip the '(sf)' / 'SF' structured-finance suffix (Art 270F labels)."""
    r = rating.upper().replace("(SF)", "").replace(" SF", "").strip()
    return r.replace(" ", "")


def long_term_cqs(rating: str) -> int:
    """Long-term securitisation CQS 1-17, or 18 for 'All other' -- Art 270F(1)."""
    return p.SEC_LONG_TERM_CQS.get(normalise_rating(rating), p.ERBA_CQS_ALL_OTHER)


def short_term_cqs(rating: str) -> int:
    """Short-term securitisation CQS 1-3, or 4 for 'All other ratings' -- Art 270F(1).

    A composite label such as 'A-1/P-1' is split on '/' and the first scale is used.
    """
    first = normalise_rating(rating).split("/")[0]
    return p.SEC_SHORT_TERM_CQS.get(first, p.ERBA_ST_ALL_OTHER)


def erba_long_term_rw(
    cqs: int, senior: bool, maturity: float, thickness: float, sts: bool
) -> float:
    """SEC-ERBA long-term risk weight -- Art 263(3)-(6) (Table 2), Art 264(3) (Table 4, STS).

    Linear interpolation between 1 and 5 years (Art 263(4)); non-senior thickness
    adjustment RW x [1 - min(T, 50%)] (Art 263(5)); non-senior floor 15% and not
    lower than the hypothetical senior tranche of the same rating and maturity
    (Art 263(6)).
    """
    table = p.ERBA_TABLE_4_STS if sts else p.ERBA_TABLE_2
    s1, s5, n1, n5 = table[cqs]
    m = clamp_maturity(maturity)
    w = (m - p.ERBA_MATURITY_POINTS[0]) / (p.ERBA_MATURITY_POINTS[1] - p.ERBA_MATURITY_POINTS[0])
    senior_rw = s1 + w * (s5 - s1)
    if senior or cqs == p.ERBA_CQS_ALL_OTHER:
        return senior_rw
    rw = (n1 + w * (n5 - n1)) * (1.0 - min(thickness, p.ERBA_THICKNESS_CAP))
    return max(rw, p.ERBA_NON_SENIOR_RW_FLOOR, senior_rw)


def sec_erba_rw(t: SecTrancheInput, sts: bool) -> tuple[float, str, list[str]]:
    """SEC-ERBA risk weight -- Art 263 (Art 264 for STS), ratings mapped per Art 270F."""
    if t.short_term_rating is not None and t.external_rating is None:
        cqs = short_term_cqs(t.short_term_rating)
        table = p.ERBA_TABLE_3_SHORT_TERM_STS if sts else p.ERBA_TABLE_1_SHORT_TERM
        cite = f"{p.SEC} Art 264(2) Table 3" if sts else f"{p.SEC} Art 263(2) Table 1"
        return table[cqs], cite, [f"short-term CQS {cqs}"]
    if t.external_rating is None:
        raise ValueError("SEC-ERBA requires a rating")
    cqs = long_term_cqs(t.external_rating)
    rw = erba_long_term_rw(cqs, t.is_senior, t.maturity_years,
                           t.detachment - t.attachment, sts)
    cite = (f"{p.SEC} Art 264(3) Table 4" if sts else f"{p.SEC} Art 263(3) Table 2") + (
        ", Art 263(4)-(6)"
    )
    return rw, cite, [f"long-term CQS {cqs}, M_T={clamp_maturity(t.maturity_years):.2f}"]


def iaa_rw(t: SecTrancheInput, sts: bool) -> tuple[float, str, list[str]]:
    """Internal Assessment Approach -- Arts 265-266: the internal grade's ECAI-equivalent
    rating is an eligible credit assessment for Art 263 / 264 (Art 266(2))."""
    if t.internal_assessment_rating is None:
        raise ValueError("IAA requires internal_assessment_rating")
    proxy = t.model_copy(update={"external_rating": t.internal_assessment_rating,
                                 "short_term_rating": None})
    rw, cite, notes = sec_erba_rw(proxy, sts)
    return rw, f"{p.SEC} Art 254(5), 265(1), 266(1)-(2) -> {cite}", notes


def _is_rated(t: SecTrancheInput) -> bool:
    """Rated position or inferred rating available (Art 254(1)(c), 263(7))."""
    return t.external_rating is not None or t.short_term_rating is not None


def look_through_cap(t: SecTrancheInput, approach: SecApproachUsed) -> float | None:
    """Senior look-through maximum risk weight -- Art 267(1)-(3).

    Uses the pool capital the tranche already carries: average RW = 12.5 * K_IRB
    (IRB RW plus 12.5 * EL / EV, Art 267(3), consistent with K_IRB of Art 255(2)-(3)) for
    SEC-IRBA; 12.5 * K_SA (Standardised Approach average, Art 267(2)(b)) for SEC-SA,
    SEC-ERBA and IAA.
    """
    if not (t.is_senior and t.flags.get("look_through", False)):
        return None
    if approach is SecApproachUsed.SEC_IRBA and t.k_irb is not None:
        return p.SEC_K_SCALAR * t.k_irb
    if t.k_sa is not None:
        return p.SEC_K_SCALAR * t.k_sa
    return None


def _row(
    t: SecTrancheInput, approach: SecApproachUsed, rw: float, cite: str, notes: list[str]
) -> SecResultRow:
    """Build the result row; RWEA = exposure value x total risk weight (Art 247(5)-(6))."""
    return SecResultRow(
        tranche_id=t.tranche_id,
        jurisdiction=Jurisdiction.UK,
        approach=approach,
        risk_weight=rw,
        rwa=t.exposure_amount * rw,
        citation=cite,
        notes=notes,
    )


def _apply_caps_and_npe(
    t: SecTrancheInput, approach: SecApproachUsed, rw: float, cite: str, notes: list[str]
) -> tuple[float, str, list[str]]:
    """Art 267 look-through cap (overrides floors, Art 267(4)); Art 269A NPE placeholder."""
    if t.is_npl_securitisation:
        # TODO: VERIFY -- UK Non-Performing Exposures Securitisation (CRR) Part not supplied.
        if (t.is_senior and not t.is_synthetic
                and t.flags.get("npe_traditional_nrppd_ge_50pct", False)
                and approach in (SecApproachUsed.SEC_IRBA, SecApproachUsed.SEC_SA)):
            rw = p.NPE_SENIOR_RW
            notes.append("NPE senior 100% (TODO: VERIFY -- BCBS CRE45.5 placeholder)")
        else:
            rw = max(rw, p.NPE_RW_FLOOR)
            notes.append("NPE floor 100% (TODO: VERIFY -- BCBS CRE45.4 placeholder)")
        cite += "; Art 269A (NPE Part not supplied: BCBS CRE45 placeholder, TODO: VERIFY)"
        return rw, cite, notes
    cap = look_through_cap(t, approach)
    if cap is not None and cap < rw:
        notes.append(f"look-through cap {cap:.2%} applied (Art 267(4) overrides floors)")
        return cap, cite + f"; {p.SEC} Art 267", notes
    return rw, cite, notes


def securitisation_risk_weight(t: SecTrancheInput) -> SecResultRow:
    """Risk weight and RWEA through the Art 254 hierarchy, with caps and floors."""
    if t.detachment < t.attachment:
        raise ValueError("detachment must be >= attachment")
    sts = t.is_stc or t.flags.get("art270_sme_senior", False) and t.is_senior
    notes: list[str] = []
    if sts and t.flags.get("art270_sme_senior", False) and not t.is_stc:
        notes.append("Art 270 senior SME position: Arts 260/262/264 STS treatment")

    # Art 254(6) / Art 269 -- resecuritisation: SEC-SA only, no Art 267-268 caps.
    if t.is_resecuritisation:
        if t.k_sa is None:
            return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX,
                        f"{p.SEC} Art 254(6)-(7) (resecuritisation without K_SA)", notes)
        rw, cite, n2 = sec_sa_rw(t, sts=False, resec=True)
        return _row(t, SecApproachUsed.SEC_SA, rw, f"{p.SEC} Art 254(6); {cite}", notes + n2)

    # Art 254(5) / 265 -- IAA for unrated ABCP positions with permission.
    if (t.flags.get("iaa_permission", False) and t.flags.get("abcp", False)
            and not _is_rated(t) and t.internal_assessment_rating is not None):
        if not t.flags.get("iaa_ig_at_first_assignment", True):
            return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX,
                        f"{p.SEC} Art 266(2) (derived rating not investment grade); "
                        f"Art 254(7)", notes)
        rw, cite, n2 = iaa_rw(t, sts)
        rw, cite, n2 = _apply_caps_and_npe(t, SecApproachUsed.SEC_IAA, rw, cite, n2)
        return _row(t, SecApproachUsed.SEC_IAA, rw, cite, notes + n2)

    # Art 254(1)(a) -- SEC-IRBA where Art 258 conditions are met.
    if (t.k_irb is not None and t.n_effective is not None and t.lgd_pool is not None
            and not t.flags.get("sec_irba_precluded", False)):
        rw, cite, n2 = sec_irba_rw(t, sts)
        rw, cite, n2 = _apply_caps_and_npe(t, SecApproachUsed.SEC_IRBA, rw, cite, n2)
        return _row(t, SecApproachUsed.SEC_IRBA, rw, f"{p.SEC} Art 254(1)(a); {cite}",
                    notes + n2)

    # Art 254(1)(b) -- SEC-SA, subject to the Art 254(2) ERBA overrides.
    sa_available = t.k_sa is not None and not t.flags.get("sec_sa_precluded", False)
    if sa_available and t.flags.get("delinquency_unknown_over_5pct", False):
        return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX,
                    f"{p.SEC} Art 261(2) (delinquency status unknown for > 5% of the pool)",
                    notes)
    if sa_available:
        rw_sa, cite_sa, n_sa = sec_sa_rw(t, sts)
        if _is_rated(t):
            rw_erba, cite_erba, n_erba = sec_erba_rw(t, sts)
            override = (
                t.flags.get("auto_or_equipment_lease_pool", False)
                or (sts and rw_sa > p.SEC_SA_OVERRIDE_RW_STS)
                or (not sts and (rw_sa > p.SEC_SA_OVERRIDE_RW_NON_STS
                                 or rw_erba > p.SEC_ERBA_OVERRIDE_RW_NON_STS))
            )
            if override:
                rw, cite, n2 = _apply_caps_and_npe(
                    t, SecApproachUsed.SEC_ERBA, rw_erba, cite_erba, n_erba)
                n2.append(f"SEC-SA would give {rw_sa:.2%}")
                return _row(t, SecApproachUsed.SEC_ERBA, rw,
                            f"{p.SEC} Art 254(2) (SEC-ERBA instead of SEC-SA); {cite}",
                            notes + n2)
        rw, cite, n2 = _apply_caps_and_npe(t, SecApproachUsed.SEC_SA, rw_sa, cite_sa, n_sa)
        return _row(t, SecApproachUsed.SEC_SA, rw, f"{p.SEC} Art 254(1)(b); {cite}", notes + n2)

    # Art 254(1)(c) -- SEC-ERBA for rated / inferred-rated positions.
    if _is_rated(t):
        rw, cite, n2 = sec_erba_rw(t, sts)
        rw, cite, n2 = _apply_caps_and_npe(t, SecApproachUsed.SEC_ERBA, rw, cite, n2)
        return _row(t, SecApproachUsed.SEC_ERBA, rw, f"{p.SEC} Art 254(1)(c); {cite}",
                    notes + n2)

    # Art 254(7) -- all other cases.
    return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX, f"{p.SEC} Art 254(7)", notes)


# =========================================================================
#  Stand-alone provisions not reachable through the tranche contract
# =========================================================================


def qualifying_securitisation_sec_sa_rw(
    attachment: float, detachment: float, property_value: float, exposure_value: float
) -> float:
    """Qualifying (single-RRE synthetic) securitisation under SEC-SA -- Art 262A(2).

    X = 1 - 0.55 * property value / exposure value; 20% when A >= X; 75% when D <= X;
    20% (D - X)/(D - A) + 75% (X - A)/(D - A) when D > X > A.
    """
    if exposure_value <= 0.0:
        raise ValueError("exposure value must be positive")
    x = 1.0 - p.QUALIFYING_SEC_SA_PROPERTY_SHARE * property_value / exposure_value
    if attachment >= x:
        return p.QUALIFYING_SEC_SA_RW_LOW
    if detachment <= x:
        return p.QUALIFYING_SEC_SA_RW_HIGH
    span = detachment - attachment
    return (p.QUALIFYING_SEC_SA_RW_LOW * (detachment - x) / span
            + p.QUALIFYING_SEC_SA_RW_HIGH * (x - attachment) / span)


def maximum_capital_requirement(
    u: float, y: float, tranches: Sequence[tuple[float, float]]
) -> float:
    """Maximum capital requirement -- Art 268(1A): U * Y + sum_i max(0, V_i - U) * Z_i.

    ``tranches`` holds (V_i, Z_i): the share held in tranche i and that tranche's
    capital requirement under this Part. Not applicable to resecuritisations
    (Art 269(3)).
    """
    if not 0.0 <= u <= 1.0:
        raise ValueError("U must be between 0 and 1")
    return u * y + sum(max(0.0, v - u) * z for v, z in tranches)


def synthetic_maturity_mismatch_rwa(
    rw_sp: float, rw_ass: float, t_protection: float, t_underlying: float
) -> float:
    """RW* = RW_SP (t - t*)/(T - t*) + RW_Ass (T - t)/(T - t*), t* = 0.25 -- Art 252(1)(b);
    T is capped at five years (Art 252(1)(a))."""
    t_star: Final[float] = 0.25
    big_t = min(t_underlying, p.TRANCHE_MATURITY_CAP_YEARS)
    if big_t <= t_star:
        raise ValueError("maturity of the underlying exposures must exceed t* = 0.25")
    t = min(max(t_protection, t_star), big_t)
    return rw_sp * (t - t_star) / (big_t - t_star) + rw_ass * (big_t - t) / (big_t - t_star)
