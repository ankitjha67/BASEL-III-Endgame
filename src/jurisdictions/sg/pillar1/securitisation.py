"""Securitisation framework under MAS Notice 637 Part VII Division 6.

Hierarchy (paras 7.6.13-7.6.19, 7.6.80-7.6.81, p. 7-126 to 7-143):

1. SEC-IRBA for an IRB pool (or a mixed pool with K_IRB on >= 95% of the pool), unless the
   bank cannot (7.6.14), MAS prohibits it (7.6.15), or the pool is an NPL securitisation whose
   K_IRB uses the F-IRBA (7.6.87);
2. otherwise SEC-ERBA where an eligible external (or inferred) assessment exists (7.6.16);
3. otherwise SEC-IAA for an unrated exposure to an ABCP programme, with MAS approval (7.6.17);
4. otherwise SEC-SA (7.6.18);
5. otherwise 1250% (7.6.19), also where the 7.6.8 due-diligence requirements are not met.

Resecuritisation exposures always use the SEC-SA with p = 1.5 and a 100% floor (7.6.82).
STC exposures (traditional, Annex 7AE / 7AF criteria) use p x 0.5 (SEC-IRBA), Tables 7-32 /
7-33 (SEC-ERBA / SEC-IAA), p = 0.5 (SEC-SA) and floors of 10% senior / 15% non-senior
(7.6.97-7.6.104). NPL securitisations (W >= 90%) have a 100% floor under SEC-IRBA, SEC-SA and
the look-through cap, and a 100% senior risk weight where NRPPD >= 50% (7.6.84-7.6.92). The
senior look-through cap (7.1.15-7.1.17) and the maximum capital requirement P x K_P x 12.5
(7.1.18-7.1.22) are applied where the caller supplies the inputs.

Flags read from :attr:`SecTrancheInput.flags` (all default False unless stated):

``use_sec_irba``            the bank has IRBA approval for the pool and can compute K_IRB.
``sec_irba_prohibited``     MAS prohibits SEC-IRBA for the pool (7.6.15).
``kirb_foundation_irba``    K_IRB of an NPL pool uses the F-IRBA (7.6.87).
``erba_eligible``           the external / inferred assessment meets Annex 7AD (default True
                            when a rating is supplied).
``abcp_programme``          exposure to an ABCP programme (SEC-IAA scope, 7.6.17).
``iaa_approved``            MAS approval to use the SEC-IAA (7.6.55).
``requirements_7_6_8_not_met``  due-diligence requirements of 7.6.8 not met -> 1250%.
``delinquency_unknown_over_5pct``  W unknown for > 5% of the pool -> 1250% (7.6.74).
``npl_traditional_nrppd_50pct``   traditional NPL securitisation with NRPPD >= 50% of the pool
                            (7.6.89) -> 100% senior risk weight under SEC-IRBA / SEC-SA.
``stc_abcp_criteria_met``   Short-term STC criteria of Annex 7AF met (ABCP; 7.6.93(b)(ii)-(iii)).

``is_stc`` on the input is read as "meets the STC Criteria of Annex 7AE" (7.6.93(b)(i)).

References:
    - MAS Notice 637 paras 7.1.14-7.1.23 (pp. 7-7 to 7-10), 7.6.1-7.6.104 (pp. 7-124 to
      7-150), Annex 7M Tables 7M-3 / 7M-4 (p. 7-272), Annex 7V Section 6 (pp. 7-317, 7-318)
    - Basel Framework CRE40-CRE45 (comparison)
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import SecApproachUsed, SecResultRow, SecTrancheInput
from src.jurisdictions.sg.pillar1 import params as p

# =========================================================================
#  Inputs: ratings and tranche maturity
# =========================================================================


def long_term_grade(rating: str) -> int:
    """Credit quality grade 1-18 of a long-term (or inferred) securitisation assessment.

    Reference: MAS Notice 637 Annex 7M Table 7M-3 (p. 7-272). Accepts Fitch / S&P notation
    ("AA-") and Moody's notation ("Aa3"); any assessment below CCC- / Caa3 is grade 18.
    """
    key = rating.strip().upper().replace(" ", "")
    if key in p.SEC_LONG_TERM_GRADE:
        return p.SEC_LONG_TERM_GRADE[key]
    if key in p.SEC_BELOW_CCC_RATINGS:
        return p.SEC_BELOW_CCC_GRADE
    raise ValueError(f"unrecognised long-term securitisation rating {rating!r}")


def short_term_grade(rating: str) -> str:
    """Short-term credit quality grade I-IV (IV = "Others").

    Reference: MAS Notice 637 Annex 7M Table 7M-4 (p. 7-272) and Table 7M-2 para 1.1.
    """
    return p.SEC_SHORT_TERM_GRADE.get(rating.strip().upper().replace(" ", ""), "IV")


def tranche_maturity_from_cash_flows(cash_flows: list[tuple[float, float]]) -> float:
    """M_T = sum(t x CF_t) / sum(CF_t), floored at 1 and capped at 5 years.

    Reference: MAS Notice 637 Annex 7V paras 6.1(a) and 6.3 (pp. 7-317, 7-318). ``cash_flows``
    holds (t in years, contractual cash flow) pairs.
    """
    total = sum(cf for _, cf in cash_flows)
    if total <= 0.0:
        raise ValueError("contractual cash flows must sum to a positive amount")
    mt = sum(t * cf for t, cf in cash_flows) / total
    return min(max(mt, p.TRANCHE_MATURITY_FLOOR), p.TRANCHE_MATURITY_CAP)


def tranche_maturity_from_legal(final_legal_maturity_years: float) -> float:
    """M_T = 1 + (M_L - 1) x 80%, floored at 1 and capped at 5 years.

    Reference: MAS Notice 637 Annex 7V paras 6.1(b), 6.2 and 6.3 (pp. 7-317, 7-318).
    """
    mt = 1.0 + (final_legal_maturity_years - 1.0) * p.TRANCHE_MATURITY_LEGAL_FACTOR
    return min(max(mt, p.TRANCHE_MATURITY_FLOOR), p.TRANCHE_MATURITY_CAP)


def _clamp_mt(mt: float) -> float:
    """Apply the 1-year floor and 5-year cap on M_T (Annex 7V para 6.3, p. 7-318)."""
    return min(max(mt, p.TRANCHE_MATURITY_FLOOR), p.TRANCHE_MATURITY_CAP)


# =========================================================================
#  SSFA building blocks
# =========================================================================


def k_ssfa(k: float, a_point: float, d_point: float, p_param: float) -> float:
    """K_SSFA = (e^{a u} - e^{a l}) / (a (u - l)), a = -1/(p K), u = D - K, l = max(A - K, 0).

    Reference: MAS Notice 637 paras 7.6.45 (SEC-IRBA, pp. 7-132, 7-133) and 7.6.75 (SEC-SA,
    p. 7-142). Requires A >= K (the caller blends the part below K at 1250%).
    """
    if k <= 0.0:
        # a -> -infinity: K_SSFA -> 0 for A > 0. Return 0; the 15% / STC floors then apply.
        return 0.0
    a = -1.0 / (p_param * k)
    u = d_point - k
    lo = max(a_point - k, 0.0)
    if u <= lo:
        return 1.0
    return (math.exp(a * u) - math.exp(a * lo)) / (a * (u - lo))


def ssfa_risk_weight(k: float, a_point: float, d_point: float, p_param: float) -> float:
    """SSFA risk weight before floors (1250% / K_SSFA x 12.5 / blended).

    Reference: MAS Notice 637 paras 7.6.46(a)-(c) (p. 7-133) and 7.6.77(a)-(c), 7.6.104
    (pp. 7-142, 7-143, 7-150).
    """
    if d_point <= a_point:
        raise ValueError("detachment point must exceed attachment point")
    if d_point <= k:
        return p.SEC_RW_1250
    if a_point >= k:
        return k_ssfa(k, a_point, d_point, p_param) * p.SSFA_SCALAR
    kss = k_ssfa(k, k, d_point, p_param)
    return ((k - a_point) / (d_point - a_point)) * p.SSFA_SCALAR + (
        (d_point - k) / (d_point - a_point)
    ) * p.SSFA_SCALAR * kss


def k_a(k_sa: float, w: float) -> float:
    """K_A = (1 - W) x K_SA + W x 0.5.

    Reference: MAS Notice 637 para 7.6.73 (p. 7-142).
    """
    return (1.0 - w) * k_sa + w * p.SEC_SA_W_PARAMETER


def k_a_with_unknown_w(
    k_sa_known: float, w_known: float, e_known: float, e_unknown: float
) -> float:
    """K_A where delinquency status is unknown for part of the pool (<= 5% by E).

    Reference: MAS Notice 637 para 7.6.74 (p. 7-142):
    K_A = (E_known / E_total) x K_A^known + E_unknown / E_total. Raises if the unknown share
    exceeds 5% -- the exposure must then be risk-weighted at 1250%.
    """
    total = e_known + e_unknown
    if total <= 0.0:
        raise ValueError("pool exposure must be positive")
    if e_unknown / total > p.SEC_SA_UNKNOWN_W_MAX_SHARE + 1e-12:
        raise ValueError("delinquency status unknown for > 5% of the pool: 1250% (para 7.6.74)")
    return (e_known / total) * k_a(k_sa_known, w_known) + e_unknown / total


def k_sa_from_pool(sa_rwa: float, sa_exposure: float) -> float:
    """K_SA = (SA(CR) RWA + CCR-SA RWA) / (SA(CR) exposure + CCR exposure) x 8%.

    Reference: MAS Notice 637 paras 7.6.63-7.6.64 (p. 7-140).
    """
    if sa_exposure <= 0.0:
        raise ValueError("underlying exposure must be positive")
    return sa_rwa / sa_exposure * p.CAPITAL_RATIO_8PCT


def mixed_pool_k(k_irb: float, k_sa: float, d_share: float) -> float:
    """Pool capital for SEC-IRBA on a mixed pool: d x K_IRB + (1 - d) x K_SA.

    Reference: MAS Notice 637 para 7.6.80 (p. 7-143); only where d >= 95%.
    """
    if d_share < p.MIXED_POOL_IRB_SHARE - 1e-12:
        raise ValueError("SEC-IRBA on a mixed pool needs K_IRB on >= 95% of the pool (7.6.81)")
    return d_share * k_irb + (1.0 - d_share) * k_sa


def effective_n_simplified(c1: float, cm: float | None = None, m: int | None = None) -> float:
    """Simplified effective number of exposures N.

    Reference: MAS Notice 637 paras 7.6.40-7.6.41 (p. 7-131):
    N = (C1 Cm + ((Cm - C1)/(m - 1)) x max(1 - m C1, 0))^-1, or N = 1/C1 if only C1 is known;
    only where the largest exposure is no more than 3% of the pool (LGD_avg = 0.5).
    """
    if c1 > p.IRBA_SIMPLIFIED_MAX_C1 + 1e-12:
        raise ValueError("simplified method requires C1 <= 3% (paras 7.6.40-7.6.41)")
    if cm is None or m is None:
        return 1.0 / c1
    return 1.0 / (c1 * cm + ((cm - c1) / (m - 1)) * max(1.0 - m * c1, 0.0))


def irba_p_key(is_retail: bool, is_senior: bool, n_eff: float) -> str:
    """Row of Table 7-28 / 7-31 for the supervisory parameter.

    Reference: MAS Notice 637 Table 7-28 (p. 7-132): granular means N >= 25.
    """
    if is_retail:
        return "RETAIL_SENIOR" if is_senior else "RETAIL_NON_SENIOR"
    seniority = "SENIOR" if is_senior else "NON_SENIOR"
    gran = "GRANULAR" if n_eff >= p.IRBA_GRANULARITY_N else "NON_GRANULAR"
    return f"WHOLESALE_{seniority}_{gran}"


def irba_p(
    k_irb: float,
    n_eff: float,
    lgd: float,
    mt: float,
    is_retail: bool,
    is_senior: bool,
    stc: bool = False,
) -> float:
    """Supervisory parameter p = max[0.3, (x 0.5 for STC) (A + B/N + C K_IRB + D LGD + E M_T)].

    Reference: MAS Notice 637 paras 7.6.42 (p. 7-132) and 7.6.99 (STC, p. 7-147), Tables 7-28
    and 7-31.
    """
    table = p.IRBA_P_PARAMS_STC if stc else p.IRBA_P_PARAMS
    a, b, c, d, e = table[irba_p_key(is_retail, is_senior, n_eff)]
    raw = a + b / n_eff + c * k_irb + d * lgd + e * _clamp_mt(mt)
    if stc:
        raw *= p.IRBA_STC_P_SCALAR
    return max(p.IRBA_P_FLOOR, raw)


def erba_long_term_rw(
    grade: int, is_senior: bool, mt: float, thickness: float, stc: bool = False
) -> float:
    """SEC-ERBA long-term risk weight with maturity interpolation and thickness adjustment.

    Reference: MAS Notice 637 paras 7.6.49-7.6.52 (pp. 7-134, 7-135), Table 7-30 (non-STC) or
    Table 7-33 (STC, para 7.6.101). Floors are applied by the caller.
    """
    table = p.ERBA_LONG_TERM_RW_STC if stc else p.ERBA_LONG_TERM_RW
    s1, s5, n1, n5 = table[grade]
    rw1, rw5 = (s1, s5) if is_senior else (n1, n5)
    m = _clamp_mt(mt)
    span = p.ERBA_MATURITY_HIGH - p.ERBA_MATURITY_LOW
    rw = rw1 + (rw5 - rw1) * (m - p.ERBA_MATURITY_LOW) / span
    if not is_senior:
        rw *= 1.0 - min(thickness, p.ERBA_THICKNESS_CAP)
    return rw


def erba_short_term_rw(grade: str, stc: bool = False) -> float:
    """SEC-ERBA short-term risk weight.

    Reference: MAS Notice 637 para 7.6.48 / Table 7-29 (p. 7-133) or para 7.6.100 / Table 7-32
    (STC, p. 7-148).
    """
    return (p.ERBA_SHORT_TERM_RW_STC if stc else p.ERBA_SHORT_TERM_RW)[grade]


def floor_for(is_senior: bool, stc: bool) -> float:
    """Applicable risk-weight floor (15%, or 10% senior / 15% non-senior for STC).

    Reference: MAS Notice 637 paras 7.6.46, 7.6.48, 7.6.49, 7.6.77 and 7.6.98.
    """
    if stc:
        return p.STC_SENIOR_RW_FLOOR if is_senior else p.STC_NON_SENIOR_RW_FLOOR
    return p.SEC_RW_FLOOR


def max_capital_rwa(p_share: float, k_pool: float) -> float:
    """Maximum aggregate credit RWE for one securitisation per unit of pool: P x K_P x 12.5.

    Reference: MAS Notice 637 paras 7.1.18-7.1.22 (pp. 7-9, 7-10). The result is multiplied
    by the pool exposure amount by the caller (K_P is per unit of pool exposure). Not available
    for resecuritisation exposures (7.1.22). Investors may cap only where they use the SEC-IRBA
    (7.1.18); originators may cap under any approach (7.1.19); NPL see 7.6.91.
    """
    return p_share * k_pool * p.SSFA_SCALAR


# =========================================================================
#  Calculator
# =========================================================================

_CITE = "MAS Notice 637 Part VII Division 6"


def _flag(t: SecTrancheInput, key: str, default: bool = False) -> bool:
    """Read a boolean flag (see module docstring for the documented keys)."""
    return bool(t.flags.get(key, default))


def _row(
    t: SecTrancheInput, approach: SecApproachUsed, rw: float, cite: str, notes: list[str]
) -> SecResultRow:
    """Assemble a result row (RWA = E x RW, para 7.1.14(b))."""
    return SecResultRow(
        tranche_id=t.tranche_id,
        jurisdiction=Jurisdiction.SG,
        approach=approach,
        risk_weight=rw,
        rwa=t.exposure_amount * rw,
        citation=cite,
        notes=notes,
    )


def _stc_applies(t: SecTrancheInput) -> bool:
    """STC treatment applies only to traditional, non-resecuritisation exposures meeting the
    Annex 7AE (or Annex 7AF for ABCP) criteria.

    Reference: MAS Notice 637 paras 7.6.93 (p. 7-145) and 7.6.82 (resecuritisation uses p = 1.5).
    """
    if t.is_synthetic or t.is_resecuritisation:
        return False
    return t.is_stc or _flag(t, "stc_abcp_criteria_met")


def securitisation_risk_weight(
    t: SecTrancheInput,
    *,
    look_through_rw: float | None = None,
    more_senior_rw: float | None = None,
    mixed_pool_irb_share: float | None = None,
) -> SecResultRow:
    """Risk weight and RWA for one securitisation position under the MAS hierarchy.

    Reference: MAS Notice 637 paras 7.1.14-7.1.17, 7.6.8, 7.6.13-7.6.19, 7.6.42-7.6.104.

    Args:
        t: the position.
        look_through_rw: exposure-weighted average risk weight of the underlying pool (incl.
            EL x 12.5 for IRB pools) for the senior look-through cap of 7.1.15; ignored for
            non-senior and resecuritisation exposures (7.1.17).
        more_senior_rw: risk weight of the immediately preceding more senior rated exposure
            (floor of 7.6.54 under SEC-ERBA and 7.6.79 under SEC-SA for unrated non-senior).
        mixed_pool_irb_share: d of 7.6.80 when both ``k_irb`` and ``k_sa`` are supplied.
    """
    notes: list[str] = []
    stc = _stc_applies(t)
    if t.is_stc and not stc:
        notes.append("STC treatment not available (synthetic or resecuritisation, 7.6.93)")
    if t.detachment <= t.attachment:
        raise ValueError("detachment point must exceed attachment point")

    if _flag(t, "requirements_7_6_8_not_met"):
        return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_1250, f"{_CITE}, paras 7.1.14(b)(iii)(E),"
                    " 7.6.8", ["7.6.8 due-diligence requirements not met"])

    # ---- Resecuritisation: SEC-SA with p = 1.5 and 100% floor (7.6.82-7.6.83) ----
    if t.is_resecuritisation:
        if t.k_sa is None:
            return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_1250, f"{_CITE}, para 7.6.19",
                        ["resecuritisation without K_SA: 1250%"])
        ka = k_a(t.k_sa, t.w)
        rw_resec = max(ssfa_risk_weight(ka, t.attachment, t.detachment, p.SEC_SA_P_RESEC),
                       p.RESEC_RW_FLOOR)
        notes.append("resecuritisation: p = 1.5, floor 100%, no senior cap (7.1.17)")
        return _row(t, SecApproachUsed.SEC_SA, rw_resec, f"{_CITE}, paras 7.6.82-7.6.83", notes)

    npl = t.is_npl_securitisation
    approach: SecApproachUsed | None = None
    rw: float | None = None
    cite = _CITE

    # ---- 1. SEC-IRBA (7.6.13-7.6.15, 7.6.80, 7.6.87) ----
    k_pool: float | None = None
    if _flag(t, "use_sec_irba") and t.k_irb is not None and not _flag(t, "sec_irba_prohibited"):
        if npl and _flag(t, "kirb_foundation_irba"):
            notes.append("NPL pool with F-IRBA K_IRB: SEC-IRBA not permitted (7.6.87)")
        elif t.k_sa is not None and mixed_pool_irb_share is not None:
            if mixed_pool_irb_share >= p.MIXED_POOL_IRB_SHARE - 1e-12:
                k_pool = mixed_pool_k(t.k_irb, t.k_sa, mixed_pool_irb_share)
                notes.append(f"mixed pool d = {mixed_pool_irb_share:.4f} (7.6.80)")
            else:
                notes.append("K_IRB on < 95% of the pool: SA-pool hierarchy (7.6.81)")
        else:
            k_pool = t.k_irb
    if k_pool is not None:
        assert t.k_irb is not None
        n_eff = t.n_effective
        lgd = t.lgd_pool
        if n_eff is None and not t.is_retail_pool:
            n_eff = 1.0
            notes.append("N not supplied: N = 1 used (conservative; B/N maximal)")
        if lgd is None:
            lgd = 1.0
            notes.append("LGD_avg not supplied: 100% used (conservative)")
        pp = irba_p(t.k_irb, n_eff or 1.0, lgd, t.maturity_years, t.is_retail_pool,
                    t.is_senior, stc=stc)
        rw = max(ssfa_risk_weight(k_pool, t.attachment, t.detachment, pp),
                 floor_for(t.is_senior, stc))
        approach = SecApproachUsed.SEC_IRBA
        cite = f"{_CITE} Sub-division 4, paras 7.6.42-7.6.46" + (", 7.6.99 (STC)" if stc else "")
        notes.append(f"p = {pp:.6f}")

    # ---- 2. SEC-ERBA (7.6.16, 7.6.48-7.6.54; STC 7.6.100-7.6.101) ----
    if approach is None and (t.external_rating or t.short_term_rating) and _flag(
        t, "erba_eligible", True
    ):
        if t.short_term_rating:
            rw = erba_short_term_rw(short_term_grade(t.short_term_rating), stc)
            para = "7.6.100, Table 7-32" if stc else "7.6.48, Table 7-29"
            cite = f"{_CITE} Sub-division 5, para {para}"
        else:
            assert t.external_rating is not None
            grade = long_term_grade(t.external_rating)
            rw = erba_long_term_rw(grade, t.is_senior, t.maturity_years,
                                   t.detachment - t.attachment, stc)
            cite = f"{_CITE} Sub-division 5, paras 7.6.49-7.6.52, " + (
                "7.6.101, Table 7-33" if stc else "Table 7-30")
            notes.append(f"credit quality grade {grade} (Table 7M-3)")
        rw = max(rw, floor_for(t.is_senior, stc))
        if more_senior_rw is not None and not t.is_senior:
            rw = max(rw, more_senior_rw)
            notes.append("not below the immediately more senior exposure (7.6.54)")
        approach = SecApproachUsed.SEC_ERBA

    # ---- 3. SEC-IAA (7.6.17, 7.6.55-7.6.61; STC 7.6.102) ----
    if (approach is None and t.internal_assessment_rating and _flag(t, "abcp_programme")
            and _flag(t, "iaa_approved")):
        ia = t.internal_assessment_rating.strip()
        st = short_term_grade(ia)
        if st != "IV":
            rw = (erba_short_term_rw(st, stc) if st in p.IAA_ELIGIBLE_SHORT_TERM_GRADES
                  else p.SEC_RW_1250)
        else:
            grade = long_term_grade(ia)
            rw = (erba_long_term_rw(grade, t.is_senior, t.maturity_years,
                                    t.detachment - t.attachment, stc)
                  if grade <= p.IAA_MAX_LONG_TERM_GRADE else p.SEC_RW_1250)
        rw = max(rw, floor_for(t.is_senior, stc))
        approach = SecApproachUsed.SEC_IAA
        cite = f"{_CITE} Sub-division 6, para {'7.6.102' if stc else '7.6.61'}"

    # ---- 4. SEC-SA (7.6.18, 7.6.62-7.6.79; STC 7.6.103-7.6.104) ----
    if approach is None and t.k_sa is not None:
        if _flag(t, "delinquency_unknown_over_5pct"):
            return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_1250, f"{_CITE}, para 7.6.74",
                        ["delinquency status unknown for > 5% of the pool"])
        ka = k_a(t.k_sa, t.w)
        pp = p.SEC_SA_P_STC if stc else p.SEC_SA_P
        rw = max(ssfa_risk_weight(ka, t.attachment, t.detachment, pp),
                 floor_for(t.is_senior, stc))
        if more_senior_rw is not None and not t.is_senior:
            rw = max(rw, more_senior_rw)
            notes.append("not below the immediately more senior rated exposure (7.6.79)")
        approach = SecApproachUsed.SEC_SA
        cite = f"{_CITE} Sub-division 7, paras 7.6.73-7.6.77" + (
            ", 7.6.103-7.6.104 (STC)" if stc else "")
        notes.append(f"K_A = {ka:.6f}, p = {pp}")

    # ---- 5. 1250% (7.6.19) ----
    if approach is None or rw is None:
        return _row(t, SecApproachUsed.RW_1250, p.SEC_RW_1250, f"{_CITE}, para 7.6.19",
                    [*notes, "no approach can be applied"])

    # ---- NPL securitisations (7.6.84-7.6.92) ----
    if npl and approach in (SecApproachUsed.SEC_IRBA, SecApproachUsed.SEC_SA):
        if t.is_senior and _flag(t, "npl_traditional_nrppd_50pct") and not t.is_synthetic:
            rw = p.NPL_SENIOR_RW
            notes.append("NPL senior, traditional, NRPPD >= 50%: 100% (7.6.89)")
        else:
            rw = max(rw, p.NPL_RW_FLOOR)
            notes.append("NPL securitisation floor 100% (7.6.88)")
        cite += ", 7.6.88-7.6.89"

    # ---- Senior look-through cap (7.1.15-7.1.17) ----
    if look_through_rw is not None and t.is_senior and look_through_rw < rw:
        capped = max(look_through_rw, p.NPL_RW_FLOOR) if npl else look_through_rw
        if capped < rw:
            rw = capped
            notes.append("senior look-through cap applied (7.1.15-7.1.16; may be below 15%)")
            approach = SecApproachUsed.LOOK_THROUGH
            cite += ", para 7.1.15"
    return _row(t, approach, rw, cite, notes)


def capped_securitisation_rwa(
    rows: list[SecResultRow], p_share: float, k_pool: float, pool_exposure: float
) -> float:
    """Aggregate RWA for positions in one securitisation, capped at P x K_P x 12.5 x pool.

    Reference: MAS Notice 637 paras 7.1.14(c), 7.1.18-7.1.22 (pp. 7-7 to 7-10). The caller
    decides eligibility (originator, or investor using SEC-IRBA; never resecuritisation).
    """
    total = sum(r.rwa for r in rows)
    return min(total, max_capital_rwa(p_share, k_pool) * pool_exposure)
