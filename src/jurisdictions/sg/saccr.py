"""SA-CCR under MAS Notice 637 Annex 7D.

EAD = alpha x (RC + PFE), alpha = 1.4 (Annex 7D para 1.1). MAS applies alpha
= 1.4 to every counterparty: the Notice contains no reduced alpha for
non-financial (commercial end-user) or pension-scheme counterparties.
PFE = multiplier x AddOn_aggregate with
multiplier = min{1; Floor + (1 - Floor) exp((V - C) / (2 (1 - Floor) AddOn))},
Floor = 5% (para 3.1). Also provided: the Table 7D-1 supervisory parameters,
the maturity factors (para 3.36) and the supervisory-duration factor
(para 3.28(a)).

References:
    - MAS Notice 637 Annex 7D paras 1.1-1.4, 2.1-2.5, 3.1-3.3, 3.28, 3.36, 3.40-3.43
      (pp. 7-182 to 7-200)
    - Basel Framework CRE52 (comparison)
"""

from __future__ import annotations

import math

from src.jurisdictions.base import Jurisdiction, RatingBucket, SACCRNettingSetInput, SACCRResult
from src.jurisdictions.sg import params as p


def pfe_multiplier(v_minus_c: float, aggregate_addon: float) -> float:
    """PFE multiplier per MAS Notice 637 Annex 7D para 3.1(b) (p. 7-184).

    With a zero add-on the multiplier is 1 (no PFE to scale).
    """
    if aggregate_addon <= 0.0:
        return 1.0
    floor = p.SACCR_MULTIPLIER_FLOOR
    return min(
        1.0, floor + (1.0 - floor) * math.exp(v_minus_c / (2.0 * (1.0 - floor) * aggregate_addon))
    )


def maturity_factor_unmargined(remaining_maturity_years: float) -> float:
    """MF = sqrt(min(M, 1 year) / 1 year), M floored at 10 business days.

    Reference: MAS Notice 637 Annex 7D para 3.36(a) and footnote 361 (pp. 7-197, 7-198).
    """
    m = max(remaining_maturity_years, p.SACCR_MIN_MATURITY_YEARS)
    return math.sqrt(min(m, 1.0))


def maturity_factor_margined(mpor_business_days: float) -> float:
    """MF = 3/2 x sqrt(MPOR / 1 year), 1 year = 250 business days.

    Reference: MAS Notice 637 Annex 7D para 3.36(b) and footnote 361(b) (p. 7-198).
    """
    return p.SACCR_MARGINED_MF_SCALAR * math.sqrt(
        mpor_business_days / p.SACCR_BUSINESS_DAYS_PER_YEAR
    )


def supervisory_duration(start_years: float, end_years: float) -> float:
    """SD = (exp(-0.05 S) - exp(-0.05 E)) / 0.05.

    Reference: MAS Notice 637 Annex 7D para 3.28(a) (p. 7-194); S is set to zero where the
    start date has occurred.
    """
    r = p.SACCR_SD_RATE
    s = max(start_years, 0.0)
    return (math.exp(-r * s) - math.exp(-r * end_years)) / r


def credit_supervisory_factor(rating: RatingBucket, index: bool = False) -> float:
    """Credit supervisory factor by reference-entity credit quality grade.

    Reference: MAS Notice 637 Annex 7D para 3.42 and Table 7D-1 (pp. 7-199, 7-200). Unrated
    single names (without an IRBA mapping) take 1.06%.
    """
    grade = p.CQS_BY_RATING[rating]
    if index:
        key = "CREDIT_INDEX_CQS1_3" if grade is not None and grade <= 3 else "CREDIT_INDEX_CQS4_6"
        return p.SACCR_SUPERVISORY_PARAMS[key][0]
    if grade is None:
        return p.SACCR_UNRATED_CREDIT_SF
    return p.SACCR_SUPERVISORY_PARAMS[f"CREDIT_SN_CQS{grade}"][0]


def adjusted_supervisory_factor(
    base_sf: float, basis: bool = False, volatility: bool = False
) -> float:
    """Basis (x0.5) and volatility (x5) hedging-set adjustments.

    Reference: MAS Notice 637 Annex 7D para 3.41 (p. 7-199).
    """
    sf = base_sf
    if basis:
        sf *= p.SACCR_BASIS_SF_SCALAR
    if volatility:
        sf *= p.SACCR_VOLATILITY_SF_SCALAR
    return sf


def saccr_ead(netting_set: SACCRNettingSetInput) -> SACCRResult:
    """SA-CCR EAD for a netting set.

    Reference: MAS Notice 637 Annex 7D paras 1.1 and 3.1 (pp. 7-182, 7-184). V - C is taken as
    ``mtm - net_collateral``. The margined-set cap of para 1.4 (EAD of a margined set capped at
    its unmargined EAD) needs the unmargined RC, which the input does not carry; it is not
    applied here.
    """
    multiplier = pfe_multiplier(
        netting_set.mtm - netting_set.net_collateral, netting_set.aggregate_addon
    )
    pfe = multiplier * netting_set.aggregate_addon
    ead = p.SACCR_ALPHA * (netting_set.replacement_cost + pfe)
    return SACCRResult(
        jurisdiction=Jurisdiction.SG,
        netting_set_id=netting_set.netting_set_id,
        alpha=p.SACCR_ALPHA,
        multiplier=multiplier,
        pfe=pfe,
        ead=ead,
        citation="MAS 637 Annex 7D paras 1.1 (alpha = 1.4, all counterparties), 3.1 (Floor 5%)",
    )
