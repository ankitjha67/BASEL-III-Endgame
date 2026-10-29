"""EU large exposures -- CRR Part Four, Articles 387-403 (CRR3 points (203)-(206)).

* Definition (Article 392): exposure >= 10 % of Tier 1 capital.
* Reporting (Article 394(1)): every large exposure, including exempted ones; plus
  exposures >= EUR 300 million but < 10 % of Tier 1 (third subparagraph).
* Limits (Article 395(1)), after CRM per Articles 399-403:
  - 25 % of Tier 1 capital;
  - client that is (or group including) an institution or investment firm: the higher of
    25 % of Tier 1 and EUR 150 million (a competent authority may set a lower amount);
    where EUR 150 million exceeds 25 % of Tier 1, an institution-set reasonable limit of
    at most 100 % of Tier 1 also applies;
  - G-SII to another G-SII or non-EU G-SII: 15 % of Tier 1.
* Exemptions: Article 400(1)(a)-(n) (automatic) and 400(2)(a)-(l) (competent authority,
  subject to 400(3)); no two exemptions on the same exposure (400(4)).
* Trading-book excess (Articles 395(5), 397): factors 200 %-900 % on the specific-risk
  requirement of the excess.

Inputs and flags (``LargeExposureInput``):

* ``exposure_value`` is the value after CRM and exemptions not yet applied.
* ``is_exempt`` or any ``eu_400_1_<x>`` / ``eu_400_2_<x>`` flag -> exempt from 395(1).
* Counterparty treated as an institution where ``counterparty_asset_class`` is ``BANK`` or
  flag ``eu_institution_or_investment_firm`` / ``eu_group_includes_institution`` is set.
* ``counterparty_is_gsib`` -> G-SII or non-EU G-SII (Article 395(1) fourth subparagraph).

Monetary thresholds stated in EUR are converted with ``reporting_ccy_per_eur``.

References:
    - Regulation (EU) No 575/2013, Articles 387-403 (consolidated 09.07.2024)
    - Regulation (EU) 2024/1623, Article 1 points (203)-(206)
"""

from __future__ import annotations

from src.jurisdictions.base import AssetClass
from src.jurisdictions.eu.pillar1 import params as prm
from src.jurisdictions.pillar1_base import LargeExposureInput, LargeExposureRow


def exemption(e: LargeExposureInput) -> str | None:
    """Citation of the Article 400 exemption applied, if any (Article 400(4): only one)."""
    if e.is_exempt:
        return "CRR Art. 400 (exemption provided by caller)"
    for key, cite in {**prm.LE_400_1_EXEMPTION_KEYS, **prm.LE_400_2_EXEMPTION_KEYS}.items():
        if e.flags.get(key, False):
            return cite
    return None


def is_institution(e: LargeExposureInput) -> bool:
    """Client is, or the group includes, an institution or investment firm (Art. 395(1))."""
    return (
        e.counterparty_asset_class is AssetClass.BANK
        or e.flags.get("eu_institution_or_investment_firm", False)
        or e.flags.get("eu_group_includes_institution", False)
    )


def limit_for(
    e: LargeExposureInput,
    tier1_capital: float,
    reporting_bank_is_gsib: bool,
    reporting_ccy_per_eur: float = 1.0,
    institution_floor_eur_m: float = prm.LE_INSTITUTION_FLOOR_EUR_M,
    institution_set_limit_pct_t1: float = prm.LE_INSTITUTION_ABSOLUTE_CEILING_PCT_T1,
) -> tuple[float, str]:
    """Article 395(1) limit (amount) and its citation."""
    if reporting_bank_is_gsib and e.counterparty_is_gsib:
        return prm.LE_GSII_TO_GSII_PCT_T1 * tier1_capital, "CRR Art. 395(1) 4th subpara.: 15 %"
    general = prm.LE_LIMIT_PCT_T1 * tier1_capital
    if not is_institution(e):
        return general, "CRR Art. 395(1): 25 % of Tier 1"
    floor_amt = min(institution_floor_eur_m, prm.LE_INSTITUTION_FLOOR_EUR_M) * reporting_ccy_per_eur
    if floor_amt <= general:
        return general, "CRR Art. 395(1): institution, 25 % of Tier 1 (>= EUR 150m)"
    inst_pct = min(institution_set_limit_pct_t1, prm.LE_INSTITUTION_ABSOLUTE_CEILING_PCT_T1)
    return (
        min(floor_amt, inst_pct * tier1_capital),
        "CRR Art. 395(1): institution, EUR 150m bounded by the institution-set limit (<= 100 % T1)",
    )


def large_exposures(
    exposures: list[LargeExposureInput],
    tier1_capital: float,
    reporting_bank_is_gsib: bool,
    reporting_ccy_per_eur: float = 1.0,
    institution_floor_eur_m: float = prm.LE_INSTITUTION_FLOOR_EUR_M,
    institution_set_limit_pct_t1: float = prm.LE_INSTITUTION_ABSOLUTE_CEILING_PCT_T1,
) -> list[LargeExposureRow]:
    """Definition (392), reporting (394(1)) and limit test (395(1)) per counterparty."""
    if tier1_capital <= 0:
        raise ValueError("Tier 1 capital must be positive")
    reporting_amt = prm.LE_REPORTING_EUR_M * reporting_ccy_per_eur
    rows: list[LargeExposureRow] = []
    for e in exposures:
        limit, cite = limit_for(
            e,
            tier1_capital,
            reporting_bank_is_gsib,
            reporting_ccy_per_eur,
            institution_floor_eur_m,
            institution_set_limit_pct_t1,
        )
        is_large = e.exposure_value >= prm.LE_DEFINITION_PCT_T1 * tier1_capital
        reportable = is_large or e.exposure_value >= reporting_amt
        exempt = exemption(e)
        breach = exempt is None and e.exposure_value > limit
        if exempt is not None:
            cite = f"{exempt}; limit not applied"
        if reportable:
            cite += "; reportable (Art. 392 / 394(1))"
        rows.append(
            LargeExposureRow(
                counterparty_id=e.counterparty_id,
                exposure_value=e.exposure_value,
                limit=limit,
                limit_pct_of_tier1=limit / tier1_capital,
                reportable=reportable,
                breach=breach,
                citation=cite,
            )
        )
    return rows


def mortgage_reduction(
    exposure: float, pledged_amount: float, property_value: float, residential: bool,
    authority_rw: float,
) -> float:
    """Exposure value after the Article 402(1)/(2) reduction (CRR3 point (206)).

    The reduction is the pledged amount, at most 55 % of the property value, and only
    where the competent authority has not raised the weight above 20 % (RRE) / 60 % (CRE).
    """  # fmt: skip
    cap_rw = prm.LE_MORTGAGE_RRE_MAX_RW if residential else prm.LE_MORTGAGE_CRE_MAX_RW
    if authority_rw > cap_rw:
        return exposure
    reduction = min(pledged_amount, prm.LE_MORTGAGE_REDUCTION_MAX_SHARE * property_value)
    return max(exposure - reduction, 0.0)


def partial_exemption_400_2_i(amount: float, kind: str) -> float:
    """Exposure remaining after the Article 400(2)(i) partial exemption (50 % or 80 %)."""
    return amount * (1.0 - prm.LE_400_2_I_SHARE[kind])


def trading_book_excess_factor(excess_pct_t1: float, persisted_over_10_days: bool) -> float:
    """Article 397 factor on the specific-risk requirement of the excess.

    200 % within 10 days (397(2)); thereafter Table 1 by the excess as % of Tier 1 (397(3)).
    """
    if not persisted_over_10_days:
        return prm.LE_TB_EXCESS_SHORT_FACTOR
    for upper, factor in prm.LE_TB_EXCESS_FACTORS:
        if excess_pct_t1 <= upper:
            return factor
    return prm.LE_TB_EXCESS_FACTORS[-1][1]


def trading_book_excess_permitted(
    trading_book_exposure_pct_t1: float,
    persisting_excess_aggregate_pct_t1: float,
    within_10_days: bool,
) -> bool:
    """Article 395(5)(c)-(d): <= 500 % within 10 days; persisting excesses <= 600 % in aggregate."""
    if within_10_days:
        return trading_book_exposure_pct_t1 <= prm.LE_TB_EXCESS_10_DAYS_MAX_PCT_T1
    return persisting_excess_aggregate_pct_t1 <= prm.LE_TB_EXCESS_PERSISTING_MAX_PCT_T1
