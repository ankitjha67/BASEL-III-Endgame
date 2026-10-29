"""UK SA-CCR exposure value -- Counterparty Credit Risk (CRR) Part Article 274.

PS1/26 Appendix 1 Annex R amends only Article 274(2) and inserts 274(2A)-(2B)
of the PRA Counterparty Credit Risk (CRR) Part (p. 455-456):

    Exposure value = alpha * (RC + PFE)                                  (Art 274(2))
    alpha = 1.4, or 1 where the counterparty is a non-financial counterparty, a
    pension scheme arrangement, or an entity established to compensate members
    of a pension scheme arrangement on default.

Transitional 'alpha add-on' (Art 274(2A)): for transactions entered into before
1 January 2027 with a counterparty in CVA Part 7.1(1)(a) or (b) (non-financial
counterparties below the clearing threshold, pension scheme arrangements), add
60% (2027), 40% (2028), 20% (2029) of [EV at alpha 1.4 - EV at alpha 1] as at
1 January 2027, unless the firm ceases to apply CVA Part 7.1(1)/(2)
(Art 274(2A)(2)). Not applied for the leverage ratio (Art 274(2B)).

The remaining SA-CCR provisions (Art 275 RC, Art 278 PFE and multiplier, the
supervisory factors of Art 280a-280e) are not reproduced in the instrument
(Annex R shows '...' for unamended text). The multiplier below follows the BCBS
CRE52.23 form with its stated 5% floor and is flagged ``TODO: VERIFY``.

References:
    - PRA Rulebook Counterparty Credit Risk (CRR) Part Art 274(2)-(2B) and 1.2 definitions
    - BCBS Basel Framework CRE52.23 (multiplier; comparison source only)
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
    """PFE multiplier = min{1; F + (1 - F) exp((V - C) / (2 (1 - F) AddOn))}, F = 5%.

    # TODO: VERIFY -- Art 278 of the PRA Counterparty Credit Risk (CRR) Part is not
    in the instrument; formula and 5% floor follow BCBS CRE52.23 (floor stated in
    CRE52.23(2)).
    """
    if aggregate_addon <= 0.0:
        return 1.0
    floor = p.SACCR_MULTIPLIER_FLOOR
    x = (mtm - net_collateral) / (2.0 * (1.0 - floor) * aggregate_addon)
    # exp(x) >= 1 for x >= 0, so the min{1; .} binds; clamp to avoid overflow.
    return min(1.0, floor + (1.0 - floor) * math.exp(min(x, 0.0)))


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
        citation=cite + "; multiplier per BCBS CRE52.23 (TODO: VERIFY Art 278)",
    )
