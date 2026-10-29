"""EU standardised approach for counterparty credit risk -- Articles 274-280f CRR.

* Exposure value = alpha x (RC + PFE), alpha = 1,4 (Article 274(2), consolidated;
  not amended by CRR3). Unlike the US NPR, the CRR has no alpha of 1 for
  non-financial or pension counterparties; the only alpha = 1 case is the
  output-floor transitional of Article 465(4) (S-TREA, IMM users, until 2029).
* PFE = multiplier x sum AddOn(a) (Article 278(1)).
* multiplier = 1 if z >= 0, else min{1; Floor_m + (1 - Floor_m) exp(z / y)}
  with Floor_m = 5 %, y = 2 (1 - Floor_m) sum AddOn(a), z = CMV - NICA
  (unmargined) or CMV - VM - NICA (margined) (Article 278(3)).
* Article 274(5): netting sets of sold options with negative CMV, premium received
  upfront and no margin agreement may be set to zero (flag ``eu_sold_options_274_5``).

Supervisory factors and add-ons (Articles 280a-280f) are inputs
(``SACCRNettingSetInput.aggregate_addon``); CRR3 did not change the
supervisory-factor table.

References:
    - Regulation (EU) No 575/2013 Articles 274, 278 (consolidated 09.07.2024)
    - Regulation (EU) 2024/1623 Article 1 point (149) (Article 274(4) and (6)) and
      point (237) (Article 465(4))
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction, SACCRNettingSetInput, SACCRResult
from src.jurisdictions.eu import params as prm
from src.jurisdictions.eu.output_floor import saccr_alpha_for_s_trea


def pfe_multiplier(z: float, aggregate_addon: float) -> float:
    """Article 278(3) multiplier with Floor_m = 5 % and y = 2 (1 - Floor_m) sum AddOn."""
    if z >= 0:
        return 1.0
    floor_m = prm.SACCR_MULTIPLIER_FLOOR
    y = 2.0 * (1.0 - floor_m) * aggregate_addon
    if y <= 0:
        return floor_m
    return min(1.0, floor_m + (1.0 - floor_m) * math.exp(z / y))


def saccr_ead(
    ns: SACCRNettingSetInput, year: int = 2026, for_output_floor: bool = False
) -> SACCRResult:
    """Exposure value of a netting set -- Article 274(2) with Article 278 PFE.

    ``z`` is taken as ``mtm - net_collateral`` (CMV less VM and NICA held, Article
    278(3)). With ``for_output_floor`` and flag ``eu_u_trea_uses_imm`` the Article
    465(4) alpha of 1 applies until 2029.
    """
    if ns.flags.get("eu_sold_options_274_5", False):
        return SACCRResult(
            jurisdiction=Jurisdiction.EU,
            netting_set_id=ns.netting_set_id,
            alpha=prm.SACCR_ALPHA,
            multiplier=0.0,
            pfe=0.0,
            ead=0.0,
            citation="CRR Art. 274(5)",
        )
    alpha = prm.SACCR_ALPHA
    cite = "CRR Art. 274(2) alpha 1,4; Art. 278 PFE"
    if for_output_floor:
        alpha = saccr_alpha_for_s_trea(year, ns.flags.get("eu_u_trea_uses_imm", False))
        if alpha != prm.SACCR_ALPHA:
            cite = "CRR Art. 465(4) alpha 1 (S-TREA); Art. 278 PFE"
    z = ns.mtm - ns.net_collateral
    mult = pfe_multiplier(z, ns.aggregate_addon)
    pfe = mult * ns.aggregate_addon
    ead = alpha * (ns.replacement_cost + pfe)
    return SACCRResult(
        jurisdiction=Jurisdiction.EU,
        netting_set_id=ns.netting_set_id,
        alpha=alpha,
        multiplier=mult,
        pfe=pfe,
        ead=ead,
        citation=cite,
    )
