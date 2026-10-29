"""UK SA-CCR exposure value -- Counterparty Credit Risk (CRR) Part Arts 274-280f.

PS1/26 Appendix 1 Annex R amends Article 274(2) and inserts 274(2A)-(2B) (p. 455-456);
the remaining provisions are taken from the PRA Rulebook CCR (CRR) Part web text in
force on 1 January 2027:

    Exposure value = alpha * (RC + PFE)                                  (Art 274(2))
    alpha = 1.4, or 1 where the counterparty is a non-financial counterparty, a
    pension scheme arrangement, or an entity established to compensate members
    of a pension scheme arrangement on default.
    RC = max{CMV - NICA, 0} (unmargined)                                (Art 275(1))
    RC = max{CMV - VM - NICA, TH + MTA - NICA, 0} (margined)            (Art 275(2))
    PFE = multiplier * AggAddOn, Floor_m = 5%, y = 2 (1 - Floor_m) AggAddOn  (Art 278)

The Art 278(3) multiplier and z, Art 275(3) multi-netting-set RC and Art 279c
maturity factor are images on the Rulebook page; their form is transcribed from
the corresponding CRR articles (Regulation (EU) No 575/2013, consolidated
09.07.2024), which carry the same Floor_m, y, NICA_i, VM_MA and MPOR definitions.
Supervisory factors, volatilities, correlations and hedging-set coefficients
(Arts 279a, 280-280f) are in :mod:`params`.

Transitional 'alpha add-on' (Art 274(2A)): for transactions entered into before
1 January 2027 with a counterparty in CVA Part 7.1(1)(a) or (b) (non-financial
counterparties below the clearing threshold, pension scheme arrangements), add
60% (2027), 40% (2028), 20% (2029) of [EV at alpha 1.4 - EV at alpha 1] as at
1 January 2027, unless the firm ceases to apply CVA Part 7.1(1)/(2)
(Art 274(2A)(2)). Not applied for the leverage ratio (Art 274(2B)).

References:
    - PRA Rulebook Counterparty Credit Risk (CRR) Part Arts 274-280f and 1.2 definitions
    - Regulation (EU) No 575/2013 Arts 275(3), 278(3), 279c (formula layout only)
"""

from __future__ import annotations

import math
from typing import Final

from src.jurisdictions.base import Jurisdiction, SACCRNettingSetInput, SACCRResult
from src.jurisdictions.uk import params as p

CCR_PART: Final[str] = "PRA Rulebook Counterparty Credit Risk (CRR) Part"


def alpha_for(netting_set: SACCRNettingSetInput) -> tuple[float, str]:
    """Alpha -- Art 274(2) (p. 456) with the 1.2 definitions of 'non-financial
    counterparty' and 'pension scheme arrangement' (p. 455)."""
    if (
        netting_set.counterparty_is_nonfinancial
        or netting_set.counterparty_is_pension_scheme
        or netting_set.flags.get("pension_compensation_entity", False)
    ):
        return (
            p.SACCR_ALPHA_NFC_PENSION,
            f"{CCR_PART} Art 274(2) (alpha = 1: NFC / pension scheme arrangement)",
        )
    return p.SACCR_ALPHA, f"{CCR_PART} Art 274(2) (alpha = 1.4)"


def multiplier(mtm: float, net_collateral: float, aggregate_addon: float) -> float:
    """PFE multiplier -- CCR Part Art 278(3): 1 if z >= 0, otherwise
    min{1; Floor_m + (1 - Floor_m) exp(z / y)}, Floor_m = 5%, y = 2 (1 - Floor_m) AggAddOn.

    ``mtm`` - ``net_collateral`` is z: CMV - NICA (Art 275(1) netting sets) or
    CMV - VM - NICA (Art 275(2)). The formula image is not extractable from the Rulebook
    page; its form follows CRR Art 278(3), which the rule corresponds to.
    """
    if aggregate_addon <= 0.0:
        return 1.0
    floor = p.SACCR_MULTIPLIER_FLOOR
    x = (mtm - net_collateral) / (2.0 * (1.0 - floor) * aggregate_addon)
    # exp(x) >= 1 for x >= 0, so the min{1; .} binds; clamp to avoid overflow.
    return min(1.0, floor + (1.0 - floor) * math.exp(min(x, 0.0)))


def replacement_cost_unmargined(cmv: float, nica: float) -> float:
    """RC = max{CMV - NICA, 0} -- CCR Part Art 275(1) (also one-way margin where the firm
    posts but does not receive VM, with VM included in NICA)."""
    return max(cmv - nica, 0.0)


def replacement_cost_margined(
    cmv: float, vm: float, nica: float, threshold: float, mta: float
) -> float:
    """RC = max{CMV - VM - NICA, TH + MTA - NICA, 0} -- CCR Part Art 275(2)."""
    return max(cmv - vm - nica, threshold + mta - nica, 0.0)


def replacement_cost_multi_netting_sets(
    cmvs: list[float], vm_ma: float, nica_ma: float
) -> float:
    """RC for netting sets under one margin agreement -- CCR Part Art 275(3):
    max{sum max{CMV_i, 0} - max{VM_MA + NICA_MA, 0}, 0}
    + max{sum min{CMV_i, 0} - min{VM_MA + NICA_MA, 0}, 0}
    (image on the Rulebook page; form transcribed from CRR Art 275(3))."""
    coll = vm_ma + nica_ma
    pos = sum(max(c, 0.0) for c in cmvs) - max(coll, 0.0)
    neg = sum(min(c, 0.0) for c in cmvs) - min(coll, 0.0)
    return max(pos, 0.0) + max(neg, 0.0)


def maturity_factor_unmargined(
    remaining_maturity_years: float, one_business_year: int = p.SACCR_BUSINESS_DAYS_PER_YEAR
) -> float:
    """MF = sqrt(min{max{M; 10 / OneBusinessYear}; 1}) -- CCR Part Art 279c(1)(a)."""
    floor = p.SACCR_MF_UNMARGINED_MIN_DAYS / one_business_year
    return math.sqrt(min(max(remaining_maturity_years, floor), 1.0))


def maturity_factor_margined(
    mpor_days: float, one_business_year: int = p.SACCR_BUSINESS_DAYS_PER_YEAR
) -> float:
    """MF = 1.5 * sqrt(MPOR / OneBusinessYear) -- CCR Part Art 279c(1)(b)."""
    return p.SACCR_MF_MARGINED_SCALAR * math.sqrt(mpor_days / one_business_year)


def credit_supervisory_factor(
    cqs: int | None = None, *, index_ig: bool | None = None, high_risk: bool = False
) -> float:
    """Credit supervisory factor -- CCR Part Art 280c(5).

    Single name: Table 3 by CQS 1-6; unrated issuer for an SA firm 0.54%, or 1.6% where
    Art 128 applies (280c(5)(a)(ii)). Quoted index (``index_ig`` given): Table 4,
    investment grade 0.38%, non-investment grade 1.06%.
    """
    if index_ig is not None:
        return p.SACCR_SF_CREDIT_INDEX["IG" if index_ig else "NON_IG"]
    if cqs is None:
        return p.SACCR_SF_CREDIT_UNRATED_HIGH_RISK if high_risk else p.SACCR_SF_CREDIT_UNRATED_SA
    return p.SACCR_SF_CREDIT_SINGLE_NAME[cqs]


def alpha_addon_share(year: int) -> float:
    """Share of the alpha add-on by year -- Art 274(2A)(1)(a)-(c) (p. 456)."""
    return p.SACCR_ALPHA_ADDON_TRANSITIONAL.get(year, 0.0)


def saccr_exposure(
    netting_set: SACCRNettingSetInput, year: int = 2027, alpha_addon: float | None = None
) -> SACCRResult:
    """SA-CCR exposure value for one netting set under the UK rules.

    ``alpha_addon`` is the Art 1.2 'alpha add-on' measured at 1 January 2027; if
    not given it is approximated by (1.4 - 1) x (RC + PFE) on current inputs.
    It is added only when ``flags['legacy_pre_2027_trades']`` is set for an
    alpha = 1 counterparty and ``flags['cva_transitional_applied']`` is not
    False (Art 274(2A)(1)-(2)).
    """
    alpha, cite = alpha_for(netting_set)
    m = multiplier(netting_set.mtm, netting_set.net_collateral, netting_set.aggregate_addon)
    pfe = m * netting_set.aggregate_addon
    base = netting_set.replacement_cost + pfe
    ead = alpha * base
    legacy = netting_set.flags.get("legacy_pre_2027_trades", False)
    cva_tr = netting_set.flags.get("cva_transitional_applied", True)
    if alpha == p.SACCR_ALPHA_NFC_PENSION and legacy and cva_tr:
        share = alpha_addon_share(year)
        if share:
            addon = (
                alpha_addon
                if alpha_addon is not None
                else (p.SACCR_ALPHA - p.SACCR_ALPHA_NFC_PENSION) * base
            )
            ead += share * addon
            cite += f"; Art 274(2A)(1) alpha add-on {share:.0%} ({year})"
    return SACCRResult(
        jurisdiction=Jurisdiction.UK,
        netting_set_id=netting_set.netting_set_id,
        alpha=alpha,
        multiplier=m,
        pfe=pfe,
        ead=ead,
        citation=cite + "; Art 275 RC, Art 278 multiplier (Floor_m 5%)",
    )
