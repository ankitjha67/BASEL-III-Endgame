"""EU securitisation framework -- CRR Articles 242-270a (consolidated 09.07.2024).

CRR3 did not amend the securitisation chapter (only the RW* definition of
Article 252(b), point (145)) apart from the output-floor p factor of Article
465(13). Formulas below were read from the rendered consolidated PDF (cons.
pp.318-325, 331-332).

Hierarchy (Article 254):

1. Re-securitisation -> SEC-SA with p = 1,5, W = 0 for tranche underlyings and a
   100 % floor (254(6), 269); no Subsection 4 caps (269(3)).
2. Internal Assessment Approach for unrated ABCP positions within an IAA
   permission (254(5), 265-266): derived rating -> Article 263/264 tables.
3. SEC-IRBA where Article 258 is met (254(1)(a), 259-260).
4. SEC-SA (254(1)(b), 261-262), except that rated / inferred-rated positions
   use the SEC-ERBA instead where (254(2)): (a) STS and SEC-SA RW > 25 %;
   (b) non-STS and SEC-SA RW > 25 % or SEC-ERBA RW > 75 %; (c) auto loans,
   auto leases and equipment leases; or (254(3)) the institution elected the
   SEC-ERBA for all rated positions.
5. SEC-ERBA where the SEC-SA may not be used (254(1)(c), 263-264).
6. 1 250 % in all other cases (254(7)).

Then: senior look-through cap (267), NPE floors (269a), maximum capital
requirement (268), additional risk weight for due-diligence breaches (270a).

Key formulas:

* SSFA (259(1)/261(1)): RW = 1 250 % if D <= K; 12,5 K_SSFA(K) if A >= K;
  [(K - A)/(D - A)] 12,5 + [(D - K)/(D - A)] 12,5 K_SSFA(K) if A < K < D;
  K_SSFA = (e^{a u} - e^{a l}) / (a (u - l)), a = -1/(p K), u = D - K, l = max(A - K; 0).
* SEC-IRBA p (259(1)): max[0,3; A + B/N + C K_IRB + D LGD + E M_T]; STS (260):
  max[0,3; 0,5 (...)]; floors 15 % (10 % STS senior).
* SEC-SA (261(2)): K_A = (1 - W) K_SA + 0,5 W; p = 1 (0,5 STS, 262); floors 15 % (10 % STS senior).
* SEC-ERBA (263(3)-(6)): Table 2 (Table 4 STS) by CQS 1-17, senior / non-senior,
  linear interpolation in M_T between 1 and 5 years; non-senior x [1 - min(T; 50 %)],
  T = D - A; non-senior floor 15 % and not below the senior RW of the same rating/maturity.

Flags read from :attr:`SecTrancheInput.flags` (all default ``False``):

* ``eu_iaa_permitted`` -- Article 265(2) permission covers this unrated ABCP position.
* ``eu_sec_irba_precluded`` -- competent authority precluded the SEC-IRBA (258(2)).
* ``eu_irb_without_own_lgd`` -- IRB pool without own LGD estimates (bars SEC-IRBA for NPE, 269a(4)).
* ``eu_sec_sa_prohibited`` -- Article 254(4) prohibition of the SEC-SA.
* ``eu_delinquency_unknown_over_5pct`` -- Article 261(2): status unknown for > 5 % -> 1 250 %.
* ``eu_254_2_c_auto`` -- auto loans / auto leases / equipment leases (254(2)(c)).
* ``eu_254_3_erba_election`` -- institution notified the SEC-ERBA election (254(3)).
* ``eu_243_criteria_not_met`` -- STS position failing Article 243 (no 260/262/264 treatment).
* ``eu_originator`` / ``eu_sponsor`` -- role of the institution (Articles 268(1), 270).
* ``eu_267_look_through`` -- composition known at all times (Article 267(1)).
* ``eu_268_max_capital`` -- apply the Article 268 maximum capital requirement.
* ``eu_269a_qualifying_traditional`` -- qualifying traditional NPE securitisation (269a(1)(b)).
* ``eu_270a_breach`` -- Article 270a additional risk weight (supervisory minimum applied).
* ``eu_resec_mixed_pool`` -- re-securitisation pool mixing tranches and other assets: the
  caller's nominal-weighted W is used (269(4)); otherwise W = 0 (269(1)(a)).

Amounts are in the reporting currency, millions.

References:
    - Regulation (EU) No 575/2013, Articles 242-270a (consolidated 09.07.2024)
    - Regulation (EU) 2024/1623, Article 1 point (237) (Article 465(13))
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.eu.pillar1 import params as prm
from src.jurisdictions.pillar1_base import SecApproachUsed, SecResultRow, SecTrancheInput

# =========================================================================
#  Common parameters -- Articles 256, 257
# =========================================================================


def tranche_maturity(maturity_years: float) -> float:
    """M_T bounded to [1, 5] years -- Article 257(2)."""
    return min(max(maturity_years, prm.SEC_MT_FLOOR_YEARS), prm.SEC_MT_CAP_YEARS)


def tranche_maturity_from_legal(final_legal_maturity_years: float) -> float:
    """M_T = 1 + (M_L - 1) x 80 %, bounded to [1, 5] -- Article 257(1)(b), (2)."""
    raw = 1.0 + (final_legal_maturity_years - 1.0) * prm.SEC_MT_LEGAL_MATURITY_FACTOR
    return tranche_maturity(raw)


# =========================================================================
#  SSFA -- Articles 259(1), 261(1)
# =========================================================================


def k_ssfa(k: float, attachment: float, detachment: float, p: float) -> float:
    """K_SSFA(K) = (e^{a u} - e^{a l}) / (a (u - l)) -- Articles 259(1) and 261(1).

    a = -1/(p K), u = D - K, l = max(A - K; 0). Returns 1 when K = 0 is not
    meaningful (the caller handles D <= K separately).
    """
    if k <= 0.0 or p <= 0.0:
        raise ValueError("K and p must be positive for the SSFA")
    a = -1.0 / (p * k)
    u = detachment - k
    lo = max(attachment - k, 0.0)
    if u <= lo:
        return 1.0
    return (math.exp(a * u) - math.exp(a * lo)) / (a * (u - lo))


def ssfa_risk_weight(k: float, attachment: float, detachment: float, p: float) -> float:
    """Unfloored SSFA risk weight (Articles 259(1) / 261(1) three-branch formula).

    The A < K < D branch is the blended ('straddle') treatment.
    """
    if detachment <= attachment:
        raise ValueError("detachment point must exceed attachment point")
    if detachment <= k:
        return prm.SEC_RW_MAX
    ks = k_ssfa(k, attachment, detachment, p)
    if attachment >= k:
        return prm.SEC_CAPITAL_TO_RW * ks
    w_below = (k - attachment) / (detachment - attachment)
    w_above = (detachment - k) / (detachment - attachment)
    return w_below * prm.SEC_CAPITAL_TO_RW + w_above * prm.SEC_CAPITAL_TO_RW * ks


# =========================================================================
#  SEC-IRBA -- Articles 258-260
# =========================================================================


def irba_p(
    k_irb: float,
    lgd: float,
    n_effective: float,
    maturity: float,
    senior: bool,
    retail: bool,
    sts: bool = False,
) -> float:
    """Supervisory parameter p -- Article 259(1) look-up table; STS per Article 260."""
    if retail:
        key = ("RETAIL", "SENIOR" if senior else "NON_SENIOR")
    else:
        granular = n_effective >= prm.SEC_IRBA_GRANULAR_N
        seniority = "SENIOR" if senior else "NON_SENIOR"
        key = ("NON_RETAIL", f"{seniority}_{'GRANULAR' if granular else 'NON_GRANULAR'}")
    a, b, c, d, e = prm.SEC_IRBA_P_TABLE[key]
    raw = a + b * (1.0 / n_effective) + c * k_irb + d * lgd + e * tranche_maturity(maturity)
    if sts:
        raw *= prm.SEC_IRBA_STS_SCALAR
    return max(prm.SEC_IRBA_P_FLOOR, raw)


def effective_number(eads: list[float]) -> float:
    """N = (sum EAD_i)^2 / sum EAD_i^2 -- Article 259(4)."""
    num = sum(eads) ** 2
    den = sum(x * x for x in eads)
    if den <= 0:
        raise ValueError("at least one positive exposure is required")
    return num / den


def exposure_weighted_lgd(lgds: list[float], eads: list[float]) -> float:
    """LGD = sum LGD_i EAD_i / sum EAD_i -- Article 259(5)."""
    tot = sum(eads)
    if tot <= 0:
        raise ValueError("at least one positive exposure is required")
    return sum(lg * e for lg, e in zip(lgds, eads, strict=True)) / tot


def simplified_n(c1: float, cm: float | None = None, m: int | None = None) -> float:
    """Simplified N where C1 <= 3 % -- Article 259(6) (LGD is then 0,50).

    N = (C1 Cm + ((Cm - C1)/(m - 1)) max{1 - m C1; 0})^-1, or 1/C1 if only C1 is known.
    """
    if c1 > 0.03:
        raise ValueError("Article 259(6) requires C1 <= 3 %")
    if cm is None or m is None or m <= 1:
        return 1.0 / c1
    return 1.0 / (c1 * cm + ((cm - c1) / (m - 1)) * max(1.0 - m * c1, 0.0))


def mixed_pool_capital(k_irb: float, k_sa: float, d_share: float) -> float:
    """Capital charge of a mixed pool d K_IRB + (1 - d) K_SA -- Article 259(7) (d >= 95 %)."""
    if d_share < prm.SEC_IRBA_MIXED_POOL_MIN_SHARE:
        raise ValueError("SEC-IRBA requires K_IRB on at least 95 % of the pool (Art. 258(1)(a))")
    return d_share * k_irb + (1.0 - d_share) * k_sa


def sec_irba_rw(t: SecTrancheInput, sts: bool) -> float:
    """SEC-IRBA risk weight with the 15 % (10 % STS senior) floor -- Articles 259, 260."""
    if t.k_irb is None or t.n_effective is None or t.lgd_pool is None:
        raise ValueError("SEC-IRBA needs k_irb, n_effective and lgd_pool")
    p = irba_p(t.k_irb, t.lgd_pool, t.n_effective, t.maturity_years, t.is_senior,
               t.is_retail_pool, sts)  # fmt: skip
    rw = ssfa_risk_weight(t.k_irb, t.attachment, t.detachment, p)
    floor = prm.SEC_RW_FLOOR_STS_SENIOR if (sts and t.is_senior) else prm.SEC_RW_FLOOR
    return max(rw, floor)


# =========================================================================
#  SEC-SA -- Articles 261, 262, 269
# =========================================================================


def k_a(k_sa: float, w: float) -> float:
    """K_A = (1 - W) K_SA + W x 0,5 -- Article 261(2)."""
    return (1.0 - w) * k_sa + w * prm.SEC_SA_W_LGD


def k_a_with_unknown_delinquency(k_a_known: float, share_unknown: float) -> float:
    """K_A where delinquency status is unknown for <= 5 % of the pool -- Article 261(2).

    K_A = (EAD_known / EAD_total) x K_A^known + EAD_unknown / EAD_total; above 5 % the
    position is risk-weighted at 1 250 % (returns 1.0, i.e. K_A = 100 %).
    """
    if share_unknown > prm.SEC_SA_UNKNOWN_DELINQUENCY_MAX:
        return 1.0
    return (1.0 - share_unknown) * k_a_known + share_unknown


def sec_sa_rw(
    t: SecTrancheInput, sts: bool, p_override: float | None = None
) -> tuple[float, float]:
    """SEC-SA risk weight and the p used -- Articles 261, 262 and 269 (re-securitisation).

    ``p_override`` carries the Article 465(13) S-TREA factor.
    """
    if t.k_sa is None:
        raise ValueError("SEC-SA needs k_sa")
    if t.flags.get("eu_delinquency_unknown_over_5pct", False):
        return prm.SEC_RW_MAX, prm.SEC_SA_P
    if t.is_resecuritisation:
        # Article 269(1)(a): W = 0 for securitisation tranches in the pool; a pool mixing
        # tranches and other assets (269(4)) passes its nominal-weighted W with the
        # ``eu_resec_mixed_pool`` flag.
        p = prm.SEC_SA_P_RESEC
        w = t.w if t.flags.get("eu_resec_mixed_pool", False) else 0.0
        ka = k_a(t.k_sa, w)
        rw = ssfa_risk_weight(ka, t.attachment, t.detachment, p) if ka > 0 else prm.SEC_RW_FLOOR
        return max(rw, prm.SEC_RW_FLOOR_RESEC), p
    p = p_override if p_override is not None else (prm.SEC_SA_P_STS if sts else prm.SEC_SA_P)
    ka = k_a(t.k_sa, t.w)
    rw = ssfa_risk_weight(ka, t.attachment, t.detachment, p) if ka > 0 else prm.SEC_RW_FLOOR
    floor = prm.SEC_RW_FLOOR_STS_SENIOR if (sts and t.is_senior) else prm.SEC_RW_FLOOR
    return max(rw, floor), p


# =========================================================================
#  SEC-ERBA / IAA -- Articles 263, 264, 266
# =========================================================================


def long_term_cqs(rating: str | None) -> int | None:
    """Securitisation CQS (1-17) of a long-term rating; ``None`` = 'all other ratings'.

    Accepts ``'CQS<n>'`` / ``'<n>'`` directly, else an S&P-style notch mapped per the
    ``# TODO: VERIFY`` table in :mod:`.params` (Implementing Regulation (EU) 2016/1801).
    """
    if rating is None:
        return None
    r = rating.strip().upper()
    if r.startswith("CQS"):
        r = r[3:]
    if r.isdigit():
        n = int(r)
        return n if 1 <= n <= 17 else None
    return prm.SEC_LONG_TERM_NOTCH_TO_CQS.get(r)


def short_term_cqs(rating: str | None) -> int | None:
    """Securitisation CQS (1-3) of a short-term rating; ``None`` = 'all other ratings'."""
    if rating is None:
        return None
    r = rating.strip().upper()
    if r.startswith("CQS") and r[3:].isdigit():
        n = int(r[3:])
        return n if 1 <= n <= 3 else None
    return prm.SEC_SHORT_TERM_NOTCH_TO_CQS.get(r)


def _interp(rw1: float, rw5: float, maturity: float) -> float:
    """Linear interpolation between 1 and 5 years -- Article 263(4)."""
    m = tranche_maturity(maturity)
    return rw1 + (rw5 - rw1) * (m - 1.0) / 4.0


def erba_rw(
    long_term: str | None,
    short_term: str | None,
    senior: bool,
    maturity: float,
    thickness: float,
    sts: bool,
) -> float:
    """SEC-ERBA risk weight -- Article 263 (Tables 1-2) / Article 264 (Tables 3-4, STS).

    A short-term assessment uses Table 1/3; otherwise the long-term Table 2/4 with
    maturity interpolation (263(4)), the thickness adjustment for non-senior
    tranches (263(5)), the 15 % floor and the senior-tranche floor (263(6)).
    """
    if short_term is not None:
        cqs = short_term_cqs(short_term)
        table_st = prm.SEC_ERBA_SHORT_TERM_STS if sts else prm.SEC_ERBA_SHORT_TERM
        return table_st.get(cqs, prm.SEC_RW_MAX) if cqs is not None else prm.SEC_RW_MAX
    cqs = long_term_cqs(long_term)
    if cqs is None:
        return prm.SEC_RW_MAX
    table = prm.SEC_ERBA_LONG_TERM_STS if sts else prm.SEC_ERBA_LONG_TERM
    s1, s5, n1, n5 = table[cqs]
    senior_rw = _interp(s1, s5, maturity)
    if senior:
        return senior_rw
    rw = _interp(n1, n5, maturity) * (1.0 - min(thickness, prm.SEC_ERBA_THICKNESS_CAP))
    return max(rw, prm.SEC_RW_FLOOR, senior_rw)


def _erba_for(t: SecTrancheInput, sts: bool, rating: str | None = None) -> float:
    """SEC-ERBA on the tranche's own (or the given derived) rating."""
    lt = rating if rating is not None else t.external_rating
    st = None if rating is not None else t.short_term_rating
    return erba_rw(lt, st, t.is_senior, t.maturity_years, t.detachment - t.attachment, sts)


def _is_rated(t: SecTrancheInput) -> bool:
    """Rated or inferred-rated position (Articles 242(5), 263(7))."""
    return t.external_rating is not None or t.short_term_rating is not None


# =========================================================================
#  STS eligibility -- Articles 243, 270
# =========================================================================


def sts_treatment_applies(t: SecTrancheInput) -> tuple[bool, str | None]:
    """Whether Articles 260/262/264 apply to the position.

    Traditional (incl. ABCP) STS positions qualify where Article 243(1)/(2) is met.
    Synthetic (on-balance-sheet) STS positions qualify only for the originator's
    senior position (Article 270(1)).
    """
    if not t.is_stc:
        return False, None
    if t.flags.get("eu_243_criteria_not_met", False):
        return False, "STS but Article 243 criteria not met: non-STS treatment"
    if t.is_synthetic and not (t.is_senior and t.flags.get("eu_originator", False)):
        return False, "synthetic STS: Article 270(1) limited to the originator's senior position"
    return True, None


# =========================================================================
#  Caps -- Articles 267, 268; NPE 269a; additional RW 270a
# =========================================================================


def look_through_rw(pool_capital_k: float) -> float:
    """Exposure-weighted average RW of the pool = 12,5 x K -- Articles 255(2)/(6), 267(1)-(3).

    K_SA = RWEA x 8 % / EV and K_IRB includes EL (255(3)), so the pool's average
    risk weight (including EL x 12,5 for IRB pools, 267(3)) is 12,5 K.
    """
    return prm.SEC_CAPITAL_TO_RW * pool_capital_k


def max_capital_rw(pool_capital_k: float, attachment: float, detachment: float) -> float:
    """Article 268 cap expressed as a risk weight on a single-tranche holding.

    Maximum capital = K x pool x V with V = held nominal / tranche nominal (268(3)(a));
    since the tranche nominal is (D - A) x pool, the RWEA cap on the position is
    12,5 x K x exposure / (D - A).
    """
    return prm.SEC_CAPITAL_TO_RW * pool_capital_k / (detachment - attachment)


def npe_max_capital(
    rwea_irb: float,
    el_irb: float,
    nrppd: float,
    ev_irb: float,
    ev_pool: float,
    scra_irb: float,
    rwea_sa: float,
) -> float:
    """CR_max of a qualifying traditional NPE securitisation -- Article 269a(5) (cons. p.331).

    CR_max = RWEA_IRB x 8 % + max[EL_IRB - NRPPD x EV_IRB/EV_Pool - SCRA_IRB; 0] + RWEA_SA x 8 %.
    """
    adj = max(el_irb - nrppd * ev_irb / ev_pool - scra_irb, 0.0)
    return rwea_irb * prm.SEC_OWN_FUNDS_RATIO + adj + rwea_sa * prm.SEC_OWN_FUNDS_RATIO


def npe_senior_look_through_rw(
    rwea_irb: float,
    rwea_sa: float,
    el_irb: float,
    nrppd: float,
    ev_irb: float,
    ev_pool: float,
    ev_sa: float,
    scra_irb: float,
) -> float:
    """RW_max of the senior position in a qualifying traditional NPE -- Article 269a(6) (p.332).

    RW_max = (RWEA_IRB + max[12,5 (EL_IRB - NRPPD EV_IRB/EV_Pool - SCRA_IRB); 0] + RWEA_SA)
             / (max[EV_IRB - NRPPD EV_IRB/EV_Pool - SCRA_IRB; 0] + EV_SA),
    before the 50 % floor.
    """
    share = nrppd * ev_irb / ev_pool
    num = rwea_irb + max(prm.SEC_CAPITAL_TO_RW * (el_irb - share - scra_irb), 0.0) + rwea_sa
    den = max(ev_irb - share - scra_irb, 0.0) + ev_sa
    if den <= 0:
        raise ValueError("denominator of Article 269a(6) RW_max must be positive")
    return num / den


def non_refundable_purchase_price_discount(
    outstanding_at_transfer: float,
    sale_price_sold_tranches: float,
    originator_retained_outstanding: float,
    realised_losses: float = 0.0,
) -> float:
    """NRPPD -- Article 269a(7): (a) - (b), reduced by realised losses, floor zero."""
    nrppd = outstanding_at_transfer - (sale_price_sold_tranches + originator_retained_outstanding)
    return max(nrppd - realised_losses, 0.0)


def synthetic_maturity_mismatch_rwea(
    rw_sp: float, rwa_ss: float, t_protection: float, t_underlying: float
) -> float:
    """RW* = RW_SP (t - t*)/(T - t*) + RWA_ss (T - t)/(T - t*) -- Article 252(b), t* = 0,25.

    T is capped at 5 years (252(a)); arguments are risk-weighted exposure amounts.
    """
    t_star = prm.SEC_SYNTHETIC_MATURITY_MISMATCH_T_STAR
    big_t = min(t_underlying, prm.SEC_SYNTHETIC_UNDERLYING_MATURITY_CAP)
    t = min(max(t_protection, t_star), big_t)
    if big_t <= t_star:
        return rw_sp
    return rw_sp * (t - t_star) / (big_t - t_star) + rwa_ss * (big_t - t) / (big_t - t_star)


def additional_rw_270a(rw: float) -> float:
    """Article 270a(1): RW plus an additional RW of at least 250 % of it, capped at 1 250 %."""
    return min(rw * (1.0 + prm.SEC_270A_ADDITIONAL_RW_MIN_MULTIPLE), prm.SEC_RW_MAX)


# =========================================================================
#  Hierarchy -- Article 254
# =========================================================================


def securitisation(
    t: SecTrancheInput,
    year: int = 2026,
    for_output_floor: bool = False,
) -> SecResultRow:
    """Risk weight and RWEA of one securitisation position -- Article 254 hierarchy.

    ``for_output_floor`` computes the S-TREA view (Article 92(5)): SEC-IRBA and the
    IAA are not available and, until 31 December 2032, positions that U-TREA
    risk-weights with the SEC-IRBA or the IAA use p = 0,25 (STS) / 0,5 in the
    SEC-SA (Article 465(13)).
    """
    if t.detachment <= t.attachment:
        raise ValueError("detachment point must exceed attachment point (Article 256)")
    notes: list[str] = []
    f = t.flags
    sts, sts_note = sts_treatment_applies(t)
    if sts_note:
        notes.append(sts_note)
    sts_cite = " (STS)" if sts else ""

    irba_ok = (
        t.k_irb is not None
        and t.n_effective is not None
        and t.lgd_pool is not None
        and not f.get("eu_sec_irba_precluded", False)
        and not (t.is_npl_securitisation and f.get("eu_irb_without_own_lgd", False))
        and not t.is_resecuritisation
    )
    iaa_ok = (
        f.get("eu_iaa_permitted", False)
        and t.internal_assessment_rating is not None
        and not _is_rated(t)
        and not t.is_resecuritisation
    )
    p_override: float | None = None
    if for_output_floor:
        if (irba_ok or iaa_ok) and year <= prm.SEC_OUTPUT_FLOOR_P_END_YEAR:
            p_override = prm.SEC_OUTPUT_FLOOR_P["ARTICLE_262" if sts else "ARTICLE_261"]
            notes.append(f"S-TREA: Art. 465(13) p = {p_override}")
        irba_ok = iaa_ok = False

    approach: SecApproachUsed
    pool_k: float | None = None
    if t.is_resecuritisation:
        if t.k_sa is None:
            approach, rw, cite = SecApproachUsed.RW_1250, prm.SEC_RW_MAX, "CRR Art. 254(7)"
            notes.append("re-securitisation without K_SA")
        else:
            rw, _ = sec_sa_rw(t, sts=False)
            approach, cite = SecApproachUsed.SEC_SA, "CRR Art. 254(6), 269(1): p = 1,5, floor 100 %"
    elif iaa_ok:
        rw = _erba_for(t, sts, rating=t.internal_assessment_rating)
        approach = SecApproachUsed.SEC_IAA
        cite = f"CRR Art. 254(5), 266 -> Art. {264 if sts else 263}"
    elif irba_ok:
        rw = sec_irba_rw(t, sts)
        pool_k = t.k_irb
        approach = SecApproachUsed.SEC_IRBA
        cite = f"CRR Art. 254(1)(a), {260 if sts else 259}{sts_cite}"
    else:
        sa_ok = t.k_sa is not None and not f.get("eu_sec_sa_prohibited", False)
        rated = _is_rated(t)
        erba = _erba_for(t, sts) if rated else None
        if sa_ok:
            sa_rw, p_used = sec_sa_rw(t, sts, p_override)
            use_erba = False
            if rated and erba is not None:
                if f.get("eu_254_2_c_auto", False):
                    use_erba, why = True, "254(2)(c) auto loans/leases"
                elif sts and sa_rw > prm.SEC_254_2_SA_RW_THRESHOLD:
                    use_erba, why = True, "254(2)(a) STS with SEC-SA RW > 25 %"
                elif not sts and (
                    sa_rw > prm.SEC_254_2_SA_RW_THRESHOLD
                    or erba > prm.SEC_254_2_ERBA_RW_THRESHOLD
                ):
                    use_erba, why = True, "254(2)(b) SEC-SA RW > 25 % or SEC-ERBA RW > 75 %"
                elif f.get("eu_254_3_erba_election", False):
                    use_erba, why = True, "254(3) SEC-ERBA election"
            if use_erba and erba is not None:
                rw, approach = erba, SecApproachUsed.SEC_ERBA
                cite = f"CRR Art. {why}; Art. {264 if sts else 263}"
            else:
                rw, approach = sa_rw, SecApproachUsed.SEC_SA
                cite = f"CRR Art. 254(1)(b), {262 if sts else 261}{sts_cite}"
                if p_override is not None:
                    cite += f"; Art. 465(13) p = {p_used}"
                if f.get("eu_delinquency_unknown_over_5pct", False):
                    notes.append("Art. 261(2): delinquency unknown for > 5 % of the pool")
            pool_k = t.k_sa
        elif rated and erba is not None:
            rw, approach = erba, SecApproachUsed.SEC_ERBA
            cite = f"CRR Art. 254(1)(c), {264 if sts else 263}"
            pool_k = t.k_sa
        else:
            rw, approach, cite = prm.SEC_RW_MAX, SecApproachUsed.RW_1250, "CRR Art. 254(7)"

    # Article 267: senior look-through cap (not for re-securitisations, 269(3))
    if (
        t.is_senior
        and not t.is_resecuritisation
        and f.get("eu_267_look_through", False)
        and pool_k is not None
    ):
        lt = look_through_rw(pool_k)
        if lt < rw:
            rw, approach = lt, SecApproachUsed.LOOK_THROUGH
            cite += "; Art. 267 look-through cap (may be below floors, 267(4))"

    # Article 269a: NPE securitisations
    if t.is_npl_securitisation and approach is not SecApproachUsed.SEC_ERBA:
        if t.is_senior and f.get("eu_269a_qualifying_traditional", False):
            rw_npe = prm.SEC_RW_NPE_QUALIFYING_SENIOR
            if f.get("eu_267_look_through", False) and pool_k is not None:
                lt = look_through_rw(pool_k)
                if lt < prm.SEC_RW_NPE_QUALIFYING_SENIOR:
                    rw_npe = max(lt, prm.SEC_RW_NPE_LOOK_THROUGH_FLOOR)
                    cite += "; Art. 269a(6) look-through, 50 % floor"
            rw = rw_npe
            cite += "; Art. 269a(3) qualifying traditional NPE senior"
        elif rw < prm.SEC_RW_FLOOR_NPE:
            rw = prm.SEC_RW_FLOOR_NPE
            cite += "; Art. 269a(2) NPE floor 100 %"

    # Article 268: maximum capital requirement (not for re-securitisations)
    role_ok = approach is SecApproachUsed.SEC_IRBA or f.get("eu_originator", False) or f.get(
        "eu_sponsor", False
    )
    if (
        f.get("eu_268_max_capital", False)
        and role_ok
        and not t.is_resecuritisation
        and pool_k is not None
    ):
        cap = max_capital_rw(pool_k, t.attachment, t.detachment)
        if cap < rw:
            rw = cap
            cite += "; Art. 268 maximum capital requirement"
            notes.append("Art. 268(4): gain on sale / CEIO strips must be deducted from CET1")

    # Article 270a: additional risk weight
    if f.get("eu_270a_breach", False):
        rw = additional_rw_270a(rw)
        cite += "; Art. 270a additional RW (supervisory minimum)"

    return SecResultRow(
        tranche_id=t.tranche_id,
        jurisdiction=Jurisdiction.EU,
        approach=approach,
        risk_weight=rw,
        rwa=rw * t.exposure_amount,
        citation=cite,
        notes=notes,
    )
