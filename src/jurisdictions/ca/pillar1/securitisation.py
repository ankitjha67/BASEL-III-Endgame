"""OSFI CAR 2026 Chapter 6 -- securitization framework.

Hierarchy (s.6.5.2): SEC-IRBA for IRB pools (or mixed pools with K_IRB for >= 95% of the pool);
otherwise SEC-ERBA (external or inferred rating) or SEC-IAA (unrated ABCP exposures, OSFI
agreement and IRB approval required); otherwise SEC-SA; otherwise 1,250%. Resecuritizations use
SEC-SA with p = 1.5 and a 100% floor (s.6.7). STC-compliant traditional securitizations use the
alternative parameters of s.6.10.3. NPL securitizations follow s.6.12. Under the capital floor
(s.6.11) SEC-IRBA and SEC-IAA are ineligible.

Regime-specific flags read from ``SecTrancheInput.flags`` (all default False):

- ``ca_capital_floor_calculation``: run the s.6.11 capital-floor hierarchy (ERBA / SA / 1250%).
- ``ca_irb_pool_excess_spread_as_sa``: investor/sponsor exposure to an IRB pool that materially
  benefits from excess spread, externally rated, treated as an SA pool (s.6.5.2.1).
- ``ca_iaa_approved``: OSFI agreement to use the SEC-IAA (requires IRB approval) (s.6.5.2.2).
- ``ca_kirb_foundation_irb``: K_IRB computed with F-IRB (precludes SEC-IRBA for NPL, s.6.12).
- ``ca_delinquency_unknown_over_5pct``: W unknown for > 5% of the pool -> 1,250% (s.6.6.4).
- ``ca_npl_nrppd_at_least_50pct``: NRPPD >= 50% of the pool balance (s.6.12 senior 100%).
- ``ca_senior_look_through``: apply the s.6.6.5.1 senior look-through cap (composition known).
- ``ca_apply_max_capital_cap``: apply the s.6.6.5.2 maximum capital requirement.
- ``ca_is_originator``: the institution is the originator (needed for the ERBA/SA cap).

References:
    - OSFI CAR 2026 Ch.6 s.6.2.1.11-6.2.1.16, 6.5-6.7, 6.10-6.12
    - Basel Framework CRE40-CRE45
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.ca.pillar1 import params as p
from src.jurisdictions.pillar1_base import SecApproachUsed, SecResultRow, SecTrancheInput

_CCC_ALIASES = {"CCC+", "CCC", "CCC-", "CCC+/CCC/CCC-"}
_BELOW_ALIASES = {"BELOW_CCC-", "BELOW CCC-", "CC", "C", "D", "SD", "RD"}
_SHORT_ALIASES = {
    "A-1/P-1": "A-1/P-1", "A-1": "A-1/P-1", "P-1": "A-1/P-1", "A-1+": "A-1/P-1",
    "A-2/P-2": "A-2/P-2", "A-2": "A-2/P-2", "P-2": "A-2/P-2",
    "A-3/P-3": "A-3/P-3", "A-3": "A-3/P-3", "P-3": "A-3/P-3",
}


# -------------------------------------------------------------------------
#  Building blocks
# -------------------------------------------------------------------------

def tranche_maturity_from_legal(legal_maturity_years: float) -> float:
    """M_T = 1 + (M_L - 1) x 80%, floored at 1 and capped at 5 years.

    CAR Ch.6 s.6.2.1.16 (paragraph 26(b)) [CRE 40.22].
    """
    mt = 1.0 + (legal_maturity_years - 1.0) * p.LEGAL_MATURITY_FACTOR
    return clamp_tranche_maturity(mt)


def tranche_maturity_from_cash_flows(cash_flows: list[tuple[float, float]]) -> float:
    """M_T = sum(t x CF_t) / sum(CF_t), floored at 1 and capped at 5 years.

    ``cash_flows`` holds (t in years, contractual cash flow) pairs.
    CAR Ch.6 s.6.2.1.16 (paragraph 26(a)) [CRE 40.22].
    """
    total = sum(cf for _, cf in cash_flows)
    if total <= 0:
        raise ValueError("cash flows must sum to a positive amount")
    return clamp_tranche_maturity(sum(t * cf for t, cf in cash_flows) / total)


def clamp_tranche_maturity(mt: float) -> float:
    """Apply the 1-year floor and 5-year cap to M_T (CAR Ch.6 s.6.2.1.16 [CRE 40.22])."""
    return min(max(mt, p.TRANCHE_MATURITY_FLOOR_YEARS), p.TRANCHE_MATURITY_CAP_YEARS)


def k_ssfa(k: float, a_point: float, d_point: float, p_param: float) -> float:
    """K_SSFA = (e^{a u} - e^{a l}) / (a (u - l)), a = -1/(p K), u = D - K, l = max(A - K, 0).

    CAR Ch.6 s.6.6.1.10 (SEC-IRBA, K = K_IRB) and s.6.6.4 (SEC-SA, K = K_A) [CRE 44.23, 41.11].
    With K = 0 the limit is 0.
    """
    if k <= 0:
        return 0.0
    a = -1.0 / (p_param * k)
    u = d_point - k
    lo = max(a_point - k, 0.0)
    if u <= lo:
        return 1.0
    return (math.exp(a * u) - math.exp(a * lo)) / (a * (u - lo))


def ssfa_risk_weight(k: float, a_point: float, d_point: float, p_param: float) -> float:
    """Unfloored SSFA risk weight (CAR Ch.6 s.6.6.1.10 / s.6.6.4 [CRE 44.25, 41.14]).

    D <= K: 1,250%; A >= K: 12.5 x K_SSFA; A < K < D: 12.5 x (K - A)/(D - A)
    + 12.5 x K_SSFA x (D - K)/(D - A).
    """
    if d_point <= a_point:
        raise ValueError("detachment point D must exceed attachment point A")
    if d_point <= k:
        return p.RW_1250
    ks = k_ssfa(k, a_point, d_point, p_param)
    if a_point >= k:
        return p.CAPITAL_TO_RW * ks
    width = d_point - a_point
    return (p.CAPITAL_TO_RW * (k - a_point) / width
            + p.CAPITAL_TO_RW * ks * (d_point - k) / width)


def irba_p(k_irb: float, n: float, lgd: float, mt: float, senior: bool, retail: bool,
           stc: bool = False) -> float:
    """Supervisory parameter p for SEC-IRBA.

    p = max[0.3; A + B/N + C K_IRB + D LGD + E M_T] (CAR Ch.6 s.6.6.1.6 [CRE 44.17]); for STC
    p = max[0.3; 0.5 x (...)] (s.6.10.3.1 [CRE 44.28]). Granular means N >= 25.
    """
    key = ("RETAIL" if retail else "WHOLESALE", senior, n >= p.GRANULAR_N_THRESHOLD)
    a_, b_, c_, d_, e_ = p.IRBA_P_TABLE[key]
    raw = a_ + b_ / n + c_ * k_irb + d_ * lgd + e_ * clamp_tranche_maturity(mt)
    if stc:
        raw *= p.STC_IRBA_P_SCALAR
    return max(p.IRBA_P_FLOOR, raw)


def effective_number(eads: list[float]) -> float:
    """N = (sum EAD_i)^2 / sum EAD_i^2 (CAR Ch.6 s.6.6.1.7 [CRE 44.20])."""
    s2 = sum(e * e for e in eads)
    if s2 <= 0:
        raise ValueError("EADs must be positive")
    return sum(eads) ** 2 / s2


def weighted_lgd(lgds: list[float], eads: list[float]) -> float:
    """LGD = sum LGD_i EAD_i / sum EAD_i (CAR Ch.6 s.6.6.1.8 [CRE 44.21])."""
    return sum(lg * e for lg, e in zip(lgds, eads, strict=True)) / sum(eads)


def simplified_n(c1: float, cm: float | None = None, m: int | None = None) -> tuple[float, float]:
    """Simplified (N, LGD) where C1 <= 3% (CAR Ch.6 s.6.6.1.9 [CRE 44.22]).

    N = (C1 Cm + (Cm - C1) max(1 - m C1, 0) / (m - 1))^-1, or 1/C1 if only C1 is known;
    LGD = 0.50.
    """
    if c1 > p.SIMPLIFIED_C1_MAX:
        raise ValueError("simplified method requires C1 <= 3%")
    if cm is None or m is None or m <= 1:
        return 1.0 / c1, p.SIMPLIFIED_LGD
    n = 1.0 / (c1 * cm + (cm - c1) * max(1.0 - m * c1, 0.0) / (m - 1))
    return n, p.SIMPLIFIED_LGD


def k_a(k_sa: float, w: float) -> float:
    """K_A = (1 - W) K_SA + 0.5 W (CAR Ch.6 s.6.6.4 [CRE 41.8])."""
    return (1.0 - w) * k_sa + p.DELINQUENT_CAPITAL_FACTOR * w


def k_a_partial_unknown(k_a_known: float, share_unknown: float) -> float:
    """K_A where W is unknown for <= 5% of the pool (CAR Ch.6 s.6.6.4 [CRE 41.9]).

    K_A = (EAD_known / EAD_total) x K_A,known + EAD_unknown / EAD_total.
    """
    if share_unknown > p.W_UNKNOWN_MAX_SHARE:
        raise ValueError("delinquency unknown for more than 5%: 1,250% applies")
    return (1.0 - share_unknown) * k_a_known + share_unknown


def mixed_pool_k(k_irb: float, k_sa: float, d: float) -> float:
    """K = d K_IRB + (1 - d) K_SA for mixed pools with d >= 95% (CAR Ch.6 s.6.5.2.3 [CRE 40.46])."""
    if d < p.MIXED_POOL_KIRB_SHARE:
        raise ValueError("K_IRB available for less than 95%: use the SA-pool hierarchy")
    return d * k_irb + (1.0 - d) * k_sa


def normalise_rating(rating: str) -> str:
    """Map an S&P-style notch to a CAR Table 2 row ("CCC+/CCC/CCC-" -> "CCC")."""
    r = rating.strip().upper().replace("−", "-").replace("–", "-")
    if r in _CCC_ALIASES:
        return "CCC"
    if r in _BELOW_ALIASES:
        return "BELOW_CCC-"
    if r not in p.ERBA_LONG_TERM_RW:
        raise ValueError(f"unrecognised long-term rating {rating!r}")
    return r


def normalise_short_rating(rating: str) -> str:
    """Map a short-term rating to a CAR Table 1 column ("All other ratings" -> OTHER)."""
    r = rating.strip().upper().replace("−", "-").replace("–", "-")
    return _SHORT_ALIASES.get(r, "OTHER")


def erba_long_term_rw(rating: str, senior: bool, mt: float, thickness: float,
                      stc: bool = False) -> float:
    """SEC-ERBA long-term RW before floors (CAR Ch.6 s.6.6.2.2 Tables 2 / 2' [CRE 42.4-42.5]).

    Linear interpolation in M_T between 1 and 5 years; non-senior tranches x [1 - min(T, 50%)]
    and never below the senior RW of the same rating and maturity (s.6.6.2.2 [CRE 42.7]).
    """
    table = p.STC_ERBA_LONG_TERM_RW if stc else p.ERBA_LONG_TERM_RW
    s1, s5, n1, n5 = table[normalise_rating(rating)]
    mt_c = clamp_tranche_maturity(mt)
    frac = (mt_c - p.ERBA_MATURITY_SHORT_YEARS) / (
        p.ERBA_MATURITY_LONG_YEARS - p.ERBA_MATURITY_SHORT_YEARS)
    senior_rw = s1 + (s5 - s1) * frac
    if senior:
        return senior_rw
    non_senior = (n1 + (n5 - n1) * frac) * (1.0 - min(thickness, p.ERBA_THICKNESS_CAP))
    return max(non_senior, senior_rw)


def erba_short_term_rw(rating: str, stc: bool = False) -> float:
    """SEC-ERBA short-term RW (CAR Ch.6 s.6.6.2.1 Table 1 / s.6.10.3.2 Table 1') [CRE 42.2]."""
    table = p.STC_ERBA_SHORT_TERM_RW if stc else p.ERBA_SHORT_TERM_RW
    return table[normalise_short_rating(rating)]


def rw_floor(senior: bool, stc: bool) -> float:
    """Approach floor: 15%, or 10% senior / 15% non-senior for STC (CAR Ch.6 s.6.10.3)."""
    if stc:
        return p.STC_SENIOR_RW_FLOOR if senior else p.STC_NON_SENIOR_RW_FLOOR
    return p.SEC_RW_FLOOR


# -------------------------------------------------------------------------
#  Hierarchy
# -------------------------------------------------------------------------

def _row(t: SecTrancheInput, approach: SecApproachUsed, rw: float, citation: str,
         notes: list[str]) -> SecResultRow:
    rw = min(rw, p.RW_1250)
    return SecResultRow(tranche_id=t.tranche_id, jurisdiction=Jurisdiction.CA, approach=approach,
                        risk_weight=rw, rwa=rw * t.exposure_amount, citation=citation,
                        notes=notes)


def _caps(t: SecTrancheInput, approach: SecApproachUsed, rw: float, k_pool: float | None,
          notes: list[str]) -> tuple[float, SecApproachUsed]:
    """Senior look-through cap and maximum capital requirement (CAR Ch.6 s.6.6.5)."""
    if k_pool is None or t.is_resecuritisation:
        return rw, approach
    flags = t.flags
    if flags.get("ca_senior_look_through", False) and t.is_senior:
        # TODO: VERIFY -- s.6.6.5.1 caps at the exposure-weighted average RW of the underlying
        # exposures, which SecTrancheInput does not carry; 12.5 x K is used (exact for IRB pools,
        # where K_IRB includes EL; for SA pools K_SA excludes defaulted exposures).
        cap = p.CAPITAL_TO_RW * k_pool
        if cap < rw:
            notes.append(f"s.6.6.5.1 senior look-through cap {cap:.2%} (may be below the "
                         "15% floor, s.6.6.5.1 [CRE 40.51]); K x 12.5 used as the underlying "
                         "exposure-weighted RW (K_SA excludes defaulted exposures)")
            rw, approach = cap, SecApproachUsed.LOOK_THROUGH
            if t.is_npl_securitisation:
                rw = max(rw, p.NPL_RW_FLOOR)
    if flags.get("ca_apply_max_capital_cap", False):
        eligible = (approach == SecApproachUsed.SEC_IRBA
                    or flags.get("ca_is_originator", False))
        if eligible:
            # K_P x P with P = held share of a single tranche of thickness D - A and exposure =
            # P x (D - A) x pool, i.e. RW_max = 12.5 K / (D - A) (s.6.6.5.2 [CRE 40.54]).
            cap = p.CAPITAL_TO_RW * k_pool / (t.detachment - t.attachment)
            if cap < rw:
                notes.append(f"s.6.6.5.2 maximum capital requirement: K_P x P for a single "
                             f"tranche holding = RW {cap:.2%}")
                rw = cap
        else:
            notes.append("s.6.6.5.2 cap not applied: SEC-ERBA/SEC-SA cap is for originators")
    return rw, approach


def securitisation_rw(t: SecTrancheInput) -> SecResultRow:
    """Risk weight and RWA via the CAR Chapter 6 hierarchy (s.6.5.2, 6.7, 6.10-6.12)."""
    flags = t.flags
    notes: list[str] = []
    if t.detachment <= t.attachment:
        raise ValueError("detachment point D must exceed attachment point A")
    floor_calc = flags.get("ca_capital_floor_calculation", False)
    stc = t.is_stc and not t.is_resecuritisation
    if stc and t.is_synthetic:
        stc = False
        notes.append("STC treatment limited to traditional securitizations (s.6.10.1)")
    mt = clamp_tranche_maturity(t.maturity_years)
    floor = rw_floor(t.is_senior, stc)

    # Resecuritization: SEC-SA only (s.6.7)
    if t.is_resecuritisation:
        if t.k_sa is None:
            return _row(t, SecApproachUsed.RW_1250, p.RW_1250,
                        "CAR Ch.6 s.6.7 and s.6.5.2 (no K_SA) [CRE 41.16, 40.41]", notes)
        ka = k_a(t.k_sa, t.w)
        rw = max(ssfa_risk_weight(ka, t.attachment, t.detachment, p.RESEC_P), p.RESEC_RW_FLOOR)
        notes.append("resecuritization: p = 1.5, W = 0 for securitization tranches (caller), "
                     "100% floor, no caps (s.6.7)")
        return _row(t, SecApproachUsed.SEC_SA, rw,
                    "CAR Ch.6 s.6.7 [CRE 41.16-41.19]", notes)

    # SEC-IRBA (s.6.5.2.1)
    irb_ok = (t.k_irb is not None and not floor_calc
              and not flags.get("ca_irb_pool_excess_spread_as_sa", False))
    if irb_ok and t.is_npl_securitisation and flags.get("ca_kirb_foundation_irb", False):
        irb_ok = False
        notes.append("SEC-IRBA precluded for NPL securitization with F-IRB K_IRB (s.6.12)")
    if irb_ok and t.k_irb is not None:
        if t.lgd_pool is None or (not t.is_retail_pool and t.n_effective is None):
            raise ValueError("SEC-IRBA requires lgd_pool and (wholesale) n_effective")
        n = t.n_effective if t.n_effective is not None else 1.0
        pp = irba_p(t.k_irb, n, t.lgd_pool, mt, t.is_senior, t.is_retail_pool, stc)
        rw = max(ssfa_risk_weight(t.k_irb, t.attachment, t.detachment, pp), floor)
        notes.append(f"p = {pp:.4f}")
        rw = _npl_adjust(t, rw, notes)
        rw, approach = _caps(t, SecApproachUsed.SEC_IRBA, rw, t.k_irb, notes)
        cite = ("CAR Ch.6 s.6.6.1 [CRE 44]" if not stc
                else "CAR Ch.6 s.6.6.1 with s.6.10.3.1 (STC) [CRE 44.27-44.29]")
        return _row(t, approach, rw, cite, notes)

    # SEC-ERBA (s.6.5.2.2)
    if t.external_rating is not None or t.short_term_rating is not None:
        if t.short_term_rating is not None and t.external_rating is None:
            rw = erba_short_term_rw(t.short_term_rating, stc)
            cite = "CAR Ch.6 s.6.6.2.1 Table 1" + (" / s.6.10.3.2 Table 1'" if stc else "")
        else:
            assert t.external_rating is not None
            rw = erba_long_term_rw(t.external_rating, t.is_senior, mt,
                                   t.detachment - t.attachment, stc)
            cite = "CAR Ch.6 s.6.6.2.2 Table 2" + (" / s.6.10.3.2 Table 2'" if stc else "")
        rw = max(rw, floor)
        rw, approach = _caps(t, SecApproachUsed.SEC_ERBA, rw, t.k_sa, notes)
        return _row(t, approach, rw, cite + " [CRE 42]", notes)

    # SEC-IAA (s.6.5.2.2, 6.6.3)
    if (t.internal_assessment_rating is not None and flags.get("ca_iaa_approved", False)
            and not floor_calc):
        rating = t.internal_assessment_rating
        if normalise_short_rating(rating) != "OTHER":
            rw = erba_short_term_rw(rating, stc)
        else:
            rw = erba_long_term_rw(rating, t.is_senior, mt, t.detachment - t.attachment, stc)
        rw = max(rw, floor)
        rw, approach = _caps(t, SecApproachUsed.SEC_IAA, rw, t.k_sa, notes)
        return _row(t, approach, rw,
                    "CAR Ch.6 s.6.6.3 (internal assessment mapped to SEC-ERBA tables) [CRE 43]",
                    notes)

    # SEC-SA (s.6.5.2.2, 6.6.4)
    if t.k_sa is not None:
        if flags.get("ca_delinquency_unknown_over_5pct", False):
            return _row(t, SecApproachUsed.RW_1250, p.RW_1250,
                        "CAR Ch.6 s.6.6.4 (W unknown for > 5% of the pool) [CRE 41.10]", notes)
        ka = k_a(t.k_sa, t.w)
        pp = p.STC_SEC_SA_P if stc else p.SEC_SA_P
        rw = max(ssfa_risk_weight(ka, t.attachment, t.detachment, pp), floor)
        notes.append(f"K_A = {ka:.4f}, p = {pp}")
        rw = _npl_adjust(t, rw, notes)
        rw, approach = _caps(t, SecApproachUsed.SEC_SA, rw, t.k_sa, notes)
        cite = ("CAR Ch.6 s.6.6.4 [CRE 41]" if not stc
                else "CAR Ch.6 s.6.6.4 with s.6.10.3.3 (STC, p = 0.5) [CRE 41.20-41.22]")
        return _row(t, approach, rw, cite, notes)

    return _row(t, SecApproachUsed.RW_1250, p.RW_1250,
                "CAR Ch.6 s.6.5.2 (no approach applicable) [CRE 40.41]", notes)


def _npl_adjust(t: SecTrancheInput, rw: float, notes: list[str]) -> float:
    """NPL floor of 100% and optional senior 100% RW (CAR Ch.6 s.6.12 [CRE 45.4-45.5])."""
    if not t.is_npl_securitisation:
        return rw
    if (t.is_senior and not t.is_synthetic
            and t.flags.get("ca_npl_nrppd_at_least_50pct", False)):
        notes.append("NPL senior tranche, NRPPD >= 50%: 100% (s.6.12)")
        return p.NPL_SENIOR_RW
    notes.append("NPL securitization: 100% floor (s.6.12)")
    return max(rw, p.NPL_RW_FLOOR)
