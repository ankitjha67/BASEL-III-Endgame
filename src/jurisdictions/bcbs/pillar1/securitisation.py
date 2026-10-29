"""BCBS securitisation framework (Basel Framework CRE40-CRE45).

Hierarchy (CRE40.41-40.48):

1. due diligence not performed -> 1250% (CRE40.31)
2. resecuritisation -> SEC-SA with p = 1.5, floor 100%, no caps (CRE40.48, CRE41.16-41.19)
3. IRB pool -> SEC-IRBA (CRE40.42, CRE44)
4. external or inferred rating, jurisdiction permits ERBA -> SEC-ERBA (CRE40.43, CRE42)
5. unrated ABCP exposure with an internal assessment -> SEC-IAA (CRE40.44, CRE43)
6. K_SA available -> SEC-SA (CRE40.45, CRE41)
7. otherwise 1250% (CRE40.41)

Supervisory formula (CRE41.11 / CRE44.23, images pp. 395 and 414)::

    a = -1 / (p K),  u = D - K,  l = max(A - K, 0)
    K_SSFA = (e^{a u} - e^{a l}) / (a (u - l))
    RW = 1250%                                    if D <= K
       = 12.5 K_SSFA                              if A >= K
       = 12.5 (K - A)/(D - A) + 12.5 K_SSFA (D - K)/(D - A)   otherwise

SEC-SA: K = K_A = (1 - W) K_SA + 0.5 W (CRE41.8); p = 1 (0.5 STC, 1.5 resec).
SEC-IRBA: K = K_IRB; p = max[0.3; A + B/N + C K_IRB + D LGD + E M_T] (CRE44.17),
STC: max[0.3; 0.5 (...)] (CRE44.28).

Keys read from ``SecTrancheInput.flags``:

- ``due_diligence_failed``: CRE40.31 -> 1250%.
- ``irba_not_permitted``: supervisor prohibits treating the pool as IRB (CRE40.15/40.42).
- ``kirb_foundation_approach``: K_IRB of an NPL pool computed with F-IRB (CRE45.3 bars SEC-IRBA).
- ``delinquency_unknown_over_5pct``: CRE41.10 -> SEC-SA gives 1250%.
- ``senior_look_through_cap``: apply the CRE40.50 cap (bank knows the pool composition).
- ``npl_nrppd_at_least_50pct``: CRE45.5 NRPPD >= 50% of the pool balance.
- ``is_abcp_exposure``: CRE40.44 SEC-IAA scope (unrated exposure to an ABCP programme).

References:
    - Basel Framework CRE40 (pp. 348-391), CRE41 (pp. 392-396), CRE42 (pp. 397-403),
      CRE43 (pp. 404-407), CRE44 (pp. 408-416), CRE45 (pp. 417-419)
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.bcbs.pillar1 import params as p
from src.jurisdictions.pillar1_base import SecApproachUsed, SecResultRow, SecTrancheInput

# =========================================================================
#  Tranche maturity (CRE40.22-40.23)
# =========================================================================


def clamp_tranche_maturity(m_t: float) -> float:
    """CRE40.22: M_T has a floor of one year and a cap of five years."""
    return min(max(m_t, p.TRANCHE_MATURITY_FLOOR_YEARS), p.TRANCHE_MATURITY_CAP_YEARS)


def tranche_maturity_from_cash_flows(cash_flows: Sequence[tuple[float, float]]) -> float:
    """CRE40.22(1): M_T = sum_t t CF_t / sum_t CF_t over (t in years, CF_t) pairs, clamped."""
    total = sum(cf for _, cf in cash_flows)
    if total <= 0:
        raise ValueError("cash flows must sum to a positive amount")
    return clamp_tranche_maturity(sum(t * cf for t, cf in cash_flows) / total)


def tranche_maturity_from_legal(final_legal_maturity: float) -> float:
    """CRE40.22(2): M_T = 1 + 80% x (M_L - 1), clamped to [1, 5]."""
    return clamp_tranche_maturity(
        1.0 + p.TRANCHE_MATURITY_LEGAL_FACTOR * (final_legal_maturity - 1.0)
    )


# =========================================================================
#  Pool parameters
# =========================================================================


def k_a(k_sa: float, w: float) -> float:
    """CRE41.8: K_A = (1 - W) x K_SA + 0.5 x W."""
    return (1.0 - w) * k_sa + p.SEC_SA_DELINQUENT_LGD * w


def k_a_partially_unknown_w(ead_known: float, k_a_known: float, ead_unknown: float) -> float | None:
    """CRE41.9: K_A = (EAD_known/EAD_total) K_A^known + EAD_unknown/EAD_total.

    Returns None where the unknown share exceeds 5% (CRE41.10: 1250% applies).
    """
    total = ead_known + ead_unknown
    if total <= 0:
        raise ValueError("pool exposure must be positive")
    if ead_unknown / total > p.SEC_SA_MAX_UNKNOWN_DELINQUENCY_SHARE:
        return None
    return ead_known / total * k_a_known + ead_unknown / total


def mixed_pool_capital(d: float, k_irb: float, k_sa: float) -> float:
    """CRE40.46: capital charge for a mixed pool = d x K_IRB + (1 - d) x K_SA (d >= 95%)."""
    if d < p.MIXED_POOL_IRBA_MIN_SHARE:
        raise ValueError("CRE40.47: below 95% K_IRB coverage the SA-pool hierarchy applies")
    return d * k_irb + (1.0 - d) * k_sa


def effective_number(eads: Sequence[float]) -> float:
    """CRE44.20: N = (sum_i EAD_i)^2 / sum_i EAD_i^2 (obligor-consolidated EADs)."""
    s2 = sum(e * e for e in eads)
    if s2 <= 0:
        raise ValueError("EADs must be positive")
    return sum(eads) ** 2 / s2


def weighted_lgd(lgds: Sequence[float], eads: Sequence[float]) -> float:
    """CRE44.21: LGD = sum_i LGD_i EAD_i / sum_i EAD_i."""
    tot = sum(eads)
    if tot <= 0:
        raise ValueError("EADs must be positive")
    return sum(lg * e for lg, e in zip(lgds, eads, strict=True)) / tot


def simplified_n(c1: float, c_m: float | None = None, m: int | None = None) -> float:
    """CRE44.22: simplified N (with LGD = 0.50) where C1 <= 0.03.

    (1) N = (C1 C_m + (C_m - C1) max(1 - m C1, 0) / (m - 1))^-1; (2) only C1: N = 1/C1.
    """
    if c1 > p.IRBA_SIMPLIFIED_MAX_C1:
        raise ValueError("CRE44.22: simplified method requires C1 <= 0.03")
    if c_m is None or m is None:
        return 1.0 / c1
    if m < 2:
        raise ValueError("m must be at least 2")
    return 1.0 / (c1 * c_m + (c_m - c1) * max(1.0 - m * c1, 0.0) / (m - 1))


def irba_p_row(is_retail: bool, is_senior: bool, n: float | None) -> str:
    """CRE44.17 Table 1 row key."""
    if is_retail:
        return "RETAIL_SENIOR" if is_senior else "RETAIL_NON_SENIOR"
    if n is None:
        raise ValueError("CRE44.17: N is required for a wholesale pool")
    gran = "GRANULAR" if n >= p.IRBA_GRANULAR_N else "NON_GRANULAR"
    return f"WHOLESALE_{'SENIOR' if is_senior else 'NON_SENIOR'}_{gran}"


def irba_p(k_irb: float, lgd: float, m_t: float, is_senior: bool, is_retail: bool,
           n: float | None, stc: bool = False) -> float:
    """CRE44.17 (CRE44.28 for STC): supervisory parameter p.

    p = max[0.3; A + B/N + C K_IRB + D LGD + E M_T]; STC: max[0.3; 0.5 (...)].
    For retail rows B = 0, so N does not enter.
    """
    a_, b_, c_, d_, e_ = p.IRBA_P_TABLE[irba_p_row(is_retail, is_senior, n)]
    b_term = b_ / n if (b_ != 0.0 and n is not None) else 0.0
    core = a_ + b_term + c_ * k_irb + d_ * lgd + e_ * clamp_tranche_maturity(m_t)
    if stc:
        core *= p.IRBA_STC_P_SCALAR
    return max(p.IRBA_P_FLOOR, core)


# =========================================================================
#  Supervisory formula (CRE41.11-41.13, CRE44.23-44.24)
# =========================================================================


def k_ssfa(k: float, attachment: float, detachment: float, p_param: float) -> float:
    """CRE41.11 / CRE44.23: K_SSFA = (e^{au} - e^{al}) / (a (u - l)).

    a = -1/(p K), u = D - K, l = max(A - K, 0). The K -> 0 limit is 0.
    """
    if detachment <= attachment:
        raise ValueError("detachment must exceed attachment")
    if k <= 0.0:
        return 0.0
    a = -1.0 / (p_param * k)
    u = detachment - k
    lo = max(attachment - k, 0.0)
    if u <= lo:
        raise ValueError("u must exceed l (D must exceed max(A, K))")
    return (math.exp(a * u) - math.exp(a * lo)) / (a * (u - lo))


def ssfa_risk_weight(k: float, attachment: float, detachment: float, p_param: float) -> float:
    """CRE41.13 / CRE44.24: risk weight (decimal) before floors."""
    if detachment <= k:
        return p.SEC_RW_MAX
    if attachment >= k:
        return p.SEC_RW_PER_UNIT_K * k_ssfa(k, attachment, detachment, p_param)
    width = detachment - attachment
    return (p.SEC_RW_PER_UNIT_K * (k - attachment) / width
            + p.SEC_RW_PER_UNIT_K * k_ssfa(k, attachment, detachment, p_param)
            * (detachment - k) / width)


def stc_floor(is_senior: bool) -> float:
    """CRE41.22 / CRE42.14 / CRE44.29: 10% senior, 15% non-senior."""
    return p.SEC_STC_FLOOR_SENIOR if is_senior else p.SEC_STC_FLOOR_NON_SENIOR


def sec_sa_risk_weight(k_sa: float, w: float, attachment: float, detachment: float,
                       is_senior: bool = False, stc: bool = False,
                       resecuritisation: bool = False) -> float:
    """SEC-SA risk weight with floors (CRE41.8-41.22)."""
    if resecuritisation:
        rw = ssfa_risk_weight(k_a(k_sa, w), attachment, detachment, p.SEC_SA_P_RESEC)
        return max(rw, p.SEC_SA_FLOOR_RESEC)
    p_param = p.SEC_SA_P_STC if stc else p.SEC_SA_P
    rw = ssfa_risk_weight(k_a(k_sa, w), attachment, detachment, p_param)
    return max(rw, stc_floor(is_senior) if stc else p.SEC_SA_FLOOR)


def sec_irba_risk_weight(k_irb: float, attachment: float, detachment: float, p_param: float,
                         is_senior: bool = False, stc: bool = False) -> float:
    """SEC-IRBA risk weight with floors (CRE44.24, CRE44.26, CRE44.29)."""
    rw = ssfa_risk_weight(k_irb, attachment, detachment, p_param)
    return max(rw, stc_floor(is_senior) if stc else p.IRBA_FLOOR)


# =========================================================================
#  SEC-ERBA (CRE42)
# =========================================================================

_CCC_ALIASES = frozenset({"CCC+", "CCC", "CCC-", "CCC+/CCC/CCC-"})


def normalise_long_term_rating(rating: str) -> str:
    """Map a notch to a CRE42 Table 2 / Table 4 row (anything below CCC- -> 'Below CCC-')."""
    r = rating.strip().upper().replace(" ", "")
    if r in _CCC_ALIASES:
        return "CCC+/CCC/CCC-"
    for grade in p.ERBA_LONG_TERM_GRADES:
        if r == grade.upper():
            return grade
    if r in {"BELOWCCC-", "CC", "C", "D", "SD", "RD"}:
        return "Below CCC-"
    raise ValueError(f"unrecognised long-term rating: {rating}")


def erba_short_term_risk_weight(rating: str, stc: bool = False) -> float:
    """CRE42.2 Table 1 (CRE42.12 Table 3 for STC); all other ratings 1250%."""
    table = p.ERBA_STC_SHORT_TERM_RW if stc else p.ERBA_SHORT_TERM_RW
    key = rating.strip().upper().replace(" ", "")
    for k, v in table.items():
        if key == k.upper():
            return v
    return p.SEC_RW_MAX


def _interpolate(rw_1y: float, rw_5y: float, m_t: float) -> float:
    """CRE42.5(1): linear interpolation between the 1-year and 5-year risk weights."""
    m = clamp_tranche_maturity(m_t)
    return rw_1y + (rw_5y - rw_1y) * (m - 1.0) / 4.0


def erba_long_term_risk_weight(rating: str, is_senior: bool, m_t: float,
                               thickness: float, stc: bool = False) -> float:
    """SEC-ERBA risk weight for a long-term rating (CRE42.3-42.7, CRE42.13-42.14).

    Senior: interpolated senior column. Non-senior: interpolated non-senior
    column x (1 - min(T, 50%)) (CRE42.5(2)), then floored at 15% and, for
    non-STC only, at the senior risk weight of the same rating and maturity
    (CRE42.7; CRE42.11 substitutes CRE42.14 for CRE42.7 under STC).
    """
    table = p.ERBA_STC_LONG_TERM_RW if stc else p.ERBA_LONG_TERM_RW
    s1, s5, n1, n5 = table[normalise_long_term_rating(rating)]
    senior_rw = _interpolate(s1, s5, m_t)
    if is_senior:
        rw = senior_rw
    else:
        rw = _interpolate(n1, n5, m_t) * (1.0 - min(thickness, p.ERBA_THICKNESS_CAP))
    if stc:
        return max(rw, stc_floor(is_senior))
    rw = max(rw, p.ERBA_FLOOR)
    if not is_senior:
        rw = max(rw, senior_rw)
    return rw


# =========================================================================
#  Caps (CRE40.50-40.55)
# =========================================================================


def max_capital_requirement(k_p: float, share_p: float, pool_exposure: float) -> float:
    """CRE40.54: maximum aggregated capital for a bank's exposures in one transaction.

    The text states "K_P * P"; K_P is a ratio to the pool exposure amount, so the
    amount is K_P x P x pool exposure.
    TODO: VERIFY -- the scaling by the pool exposure amount is the engine's reading of
    "K_P * P" (CRE40.54 defines K_P as a decimal and P as a proportion).
    """
    return k_p * share_p * pool_exposure


def apply_transaction_cap(rows: Sequence[SecResultRow], k_p: float, share_p: float,
                          pool_exposure: float) -> list[SecResultRow]:
    """CRE40.52-40.54: scale RWAs of one transaction so total capital <= K_P x P x pool."""
    cap_rwa = p.SEC_RW_PER_UNIT_K * max_capital_requirement(k_p, share_p, pool_exposure)
    total = sum(r.rwa for r in rows)
    if total <= cap_rwa or total <= 0:
        return list(rows)
    scale = cap_rwa / total
    out: list[SecResultRow] = []
    for r in rows:
        out.append(r.model_copy(update={
            "rwa": r.rwa * scale,
            "risk_weight": r.risk_weight * scale,
            "notes": [*r.notes, "CRE40.54 maximum capital requirement applied"],
        }))
    return out


# =========================================================================
#  Hierarchy (CRE40.41-40.48)
# =========================================================================


def _row(t: SecTrancheInput, approach: SecApproachUsed, rw: float, citation: str,
         notes: list[str]) -> SecResultRow:
    return SecResultRow(tranche_id=t.tranche_id, jurisdiction=Jurisdiction.BCBS,
                        approach=approach, risk_weight=rw, rwa=rw * t.exposure_amount,
                        citation=citation, notes=notes)


def _look_through(t: SecTrancheInput, rw: float, approach: SecApproachUsed, notes: list[str],
                  k_pool: float | None) -> tuple[float, SecApproachUsed]:
    """CRE40.50-40.51 senior look-through cap (not for resecuritisations, CRE41.19)."""
    if not (t.is_senior and t.flags.get("senior_look_through_cap", False)):
        return rw, approach
    if k_pool is None:
        notes.append("CRE40.50 cap requested but pool capital (K_SA/K_IRB) not supplied")
        return rw, approach
    cap = p.SEC_RW_PER_UNIT_K * k_pool
    if t.is_npl_securitisation:
        cap = max(cap, p.NPL_RW_FLOOR)  # CRE45.4
    if cap < rw:
        notes.append(f"CRE40.50 senior look-through cap {cap:.4f} applied "
                     "(CRE40.51: may be below the 15% floor)")
        return cap, SecApproachUsed.LOOK_THROUGH
    return rw, approach


def securitisation(t: SecTrancheInput, erba_permitted: bool = True) -> SecResultRow:
    """Risk weight and RWA of one position under the CRE40.41-40.48 hierarchy."""
    notes: list[str] = []
    if t.detachment <= t.attachment:
        raise ValueError("detachment must exceed attachment")
    if t.flags.get("due_diligence_failed", False):
        return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX, "CRE40.31", notes)

    stc = t.is_stc
    if stc and t.is_synthetic:
        notes.append("CRE40.66: only traditional securitisations are in STC scope; STC ignored")
        stc = False
    if stc and t.is_resecuritisation:
        notes.append("CRE40.48: resecuritisations use SEC-SA (p = 1.5); STC ignored")
        stc = False
    npl = t.is_npl_securitisation

    # Resecuritisation: SEC-SA only (CRE40.48, CRE41.16-41.19)
    if t.is_resecuritisation:
        if t.k_sa is None:
            return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX, "CRE40.41 (no K_SA)", notes)
        rw = sec_sa_risk_weight(t.k_sa, t.w, t.attachment, t.detachment,
                                resecuritisation=True)
        notes.append("CRE41.19: caps of CRE40.50-40.55 not applicable")
        return _row(t, SecApproachUsed.SEC_SA, rw, "CRE41.16-41.18 (p = 1.5, floor 100%)", notes)

    # 1. SEC-IRBA (CRE40.42)
    irba_barred = t.flags.get("irba_not_permitted", False) or (
        npl and t.flags.get("kirb_foundation_approach", False))
    if t.k_irb is not None and not irba_barred:
        if t.lgd_pool is None or (t.n_effective is None and not t.is_retail_pool):
            raise ValueError("CRE44.17: SEC-IRBA needs LGD and (wholesale) N")
        p_param = irba_p(t.k_irb, t.lgd_pool, t.maturity_years, t.is_senior,
                         t.is_retail_pool, t.n_effective, stc)
        rw = sec_irba_risk_weight(t.k_irb, t.attachment, t.detachment, p_param,
                                  t.is_senior, stc)
        notes.append(f"p = {p_param:.6f}")
        cite = "CRE44.17-44.26" if not stc else "CRE44.27-44.29 (STC)"
        return _finish_irba_or_sa(t, rw, SecApproachUsed.SEC_IRBA, cite, notes, t.k_irb)
    if t.k_irb is not None and irba_barred:
        notes.append("SEC-IRBA not permitted (CRE40.42 / CRE45.3)")

    # 2. SEC-ERBA (CRE40.43)
    if erba_permitted and (t.external_rating or t.short_term_rating):
        if t.short_term_rating:
            rw = erba_short_term_risk_weight(t.short_term_rating, stc)
            cite = "CRE42.12 Table 3" if stc else "CRE42.2 Table 1"
            rw = max(rw, stc_floor(t.is_senior) if stc else p.ERBA_FLOOR)
        else:
            assert t.external_rating is not None
            rw = erba_long_term_risk_weight(t.external_rating, t.is_senior, t.maturity_years,
                                            t.detachment - t.attachment, stc)
            cite = "CRE42.13 Table 4, CRE42.14" if stc else "CRE42.4 Table 2, CRE42.5-42.7"
        rw, approach = _look_through(t, rw, SecApproachUsed.SEC_ERBA, notes, t.k_sa)
        return _row(t, approach, rw, cite, notes)

    # 3. SEC-IAA (CRE40.44, CRE43.3)
    if (erba_permitted and t.internal_assessment_rating
            and t.flags.get("is_abcp_exposure", True)):
        rw = erba_long_term_risk_weight(t.internal_assessment_rating, t.is_senior,
                                        t.maturity_years, t.detachment - t.attachment, stc)
        rw, approach = _look_through(t, rw, SecApproachUsed.SEC_IAA, notes, t.k_sa)
        return _row(t, approach, rw, "CRE43.1-43.3 (mapped to the SEC-ERBA table)", notes)

    # 4. SEC-SA (CRE40.45)
    if t.k_sa is not None:
        if t.flags.get("delinquency_unknown_over_5pct", False):
            return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX, "CRE41.10", notes)
        rw = sec_sa_risk_weight(t.k_sa, t.w, t.attachment, t.detachment, t.is_senior, stc)
        notes.append(f"K_A = {k_a(t.k_sa, t.w):.6f}")
        cite = "CRE41.8-41.15" if not stc else "CRE41.20-41.22 (STC)"
        return _finish_irba_or_sa(t, rw, SecApproachUsed.SEC_SA, cite, notes, t.k_sa)

    # 5. 1250% (CRE40.41)
    return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_MAX, "CRE40.41", notes)


def _finish_irba_or_sa(t: SecTrancheInput, rw: float, approach: SecApproachUsed, cite: str,
                       notes: list[str], k_pool: float) -> SecResultRow:
    """NPL floor / senior treatment (CRE45.4-45.5) and the look-through cap (CRE40.50)."""
    if t.is_npl_securitisation:
        if (t.is_senior and not t.is_synthetic
                and t.flags.get("npl_nrppd_at_least_50pct", False)):
            notes.append("CRE45.5: senior tranche of traditional NPL securitisation, "
                         "NRPPD >= 50% -> 100%")
            return _row(t, approach, p.NPL_SENIOR_RW, f"{cite}; CRE45.5", notes)
        rw = max(rw, p.NPL_RW_FLOOR)
        cite = f"{cite}; CRE45.4 floor 100%"
    rw, approach = _look_through(t, rw, approach, notes, k_pool)
    return _row(t, approach, rw, cite, notes)
