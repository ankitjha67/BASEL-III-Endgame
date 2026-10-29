"""UK large exposures -- PRA Rulebook Large Exposures (CRR) Part.

* Large exposure: value >= 10% of Tier 1 (rule 1.2); also reportable on a
  consolidated basis where >= GBP 260 million (Art 394(1)).
* Limit: 25% of Tier 1 after CRM (Art 395(1)); for relevant exposures to Article
  119 institutions, the higher of 25% of Tier 1 and GBP 130 million, and where
  GBP 130 million exceeds 25% a firm-set limit not above 100% of Tier 1; a G-SII's
  exposure to another G-SII or non-UK G-SII is limited to 15%.
* Exemptions: Art 400(1) (automatic) and 400(2) (with PRA permission); exempt
  large exposures are still reported (Art 394(1)).

``LargeExposureInput.flags`` keys read here: the Art 400 keys of
:data:`params.LE_EXEMPTION_KEYS`; ``gsii_compliance_period`` (Art 395(1): within
12 months of identification the 15% limit is not yet binding);
``connected_non_institutions_over_25pct`` (Art 395(1) proviso to the GBP 130m
floor). The firm-set 'reasonable limit' of Art 395(1) second subparagraph cannot be
passed through the contract, so its 100%-of-Tier-1 ceiling is used. Amounts are
GBP millions.
"""

from __future__ import annotations

from src.jurisdictions.base import AssetClass
from src.jurisdictions.pillar1_base import LargeExposureInput, LargeExposureRow
from src.jurisdictions.uk.pillar1 import params as p


def exemption(e: LargeExposureInput) -> str | None:
    """Art 400 exemption that applies, if any (caller-asserted via ``is_exempt`` or flags)."""
    for key, label in p.LE_EXEMPTION_KEYS.items():
        if e.flags.get(key, False):
            return label
    if e.is_exempt:
        return "Art 400 exemption (caller-asserted)"
    return None


def limit_for(
    e: LargeExposureInput, tier1: float, reporting_bank_is_gsii: bool
) -> tuple[float, str]:
    """Applicable limit (GBP m) and citation -- Art 395(1)."""
    general = p.LE_LIMIT * tier1
    if (reporting_bank_is_gsii and e.counterparty_is_gsib
            and not e.flags.get("gsii_compliance_period", False)):
        return p.LE_GSII_LIMIT * tier1, f"{p.LE} Art 395(1) third subparagraph (G-SII 15%)"
    if (e.counterparty_asset_class is AssetClass.BANK
            and not e.flags.get("connected_non_institutions_over_25pct", False)):
        if general < p.LE_INSTITUTION_FLOOR_GBP_M:
            limit = min(p.LE_INSTITUTION_FLOOR_GBP_M, p.LE_INSTITUTION_ABS_CAP * tier1)
            return limit, (
                f"{p.LE} Art 395(1) (institution: GBP 130m > 25% of Tier 1; firm-set limit "
                "capped at 100% of Tier 1)"
            )
        return general, f"{p.LE} Art 395(1) (institution: max(25% Tier 1, GBP 130m))"
    return general, f"{p.LE} Art 395(1) (25% of Tier 1)"


def large_exposure_rows(
    exposures: list[LargeExposureInput], tier1_capital: float, reporting_bank_is_gsib: bool
) -> list[LargeExposureRow]:
    """Reporting test (rule 1.2, Art 394(1)) and limit test (Art 395(1), Art 400)."""
    if tier1_capital <= 0.0:
        raise ValueError("Tier 1 capital must be positive")
    rows: list[LargeExposureRow] = []
    for e in exposures:
        limit, cite = limit_for(e, tier1_capital, reporting_bank_is_gsib)
        reportable = (e.exposure_value >= p.LE_REPORTING_THRESHOLD * tier1_capital
                      or e.exposure_value >= p.LE_REPORTING_ABS_GBP_M)
        exempt = exemption(e)
        breach = exempt is None and e.exposure_value > limit
        if exempt is not None:
            cite += f"; exempt: {exempt}; still reported (Art 394(1))"
        cite += f"; reporting: {p.LE} rule 1.2 (10% of Tier 1), Art 394(1) (GBP 260m)"
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


def trading_book_excess_factor(excess_pct_of_tier1: float, days: int) -> float:
    """Additional own funds factor on trading-book excess -- Art 397(2)-(3).

    200% while the excess has persisted 10 days or less; thereafter Table 1 by the
    excess as a share of Tier 1 (applied to the components in ascending order of
    specific-risk requirement; this returns the factor for the given band).
    """
    if days <= p.LE_TB_EXCESS_DAYS:
        return p.LE_TB_EXCESS_FACTOR_FIRST_10D
    for upper, factor in p.LE_TB_EXCESS_TABLE_1:
        if excess_pct_of_tier1 <= upper:
            return factor
    return p.LE_TB_EXCESS_TABLE_1[-1][1]


def trading_book_excess_permitted(
    trading_book_exposure: float, non_trading_exposure: float, tier1: float, days: int,
    aggregate_persistent_excess: float = 0.0,
) -> bool:
    """Art 395(5)(a), (c)-(d): non-trading part within the limit; within 10 days the
    trading-book exposure <= 500% of Tier 1; persistent excesses in aggregate <= 600%."""
    if non_trading_exposure > p.LE_LIMIT * tier1:
        return False
    if days <= p.LE_TB_EXCESS_DAYS:
        return trading_book_exposure <= p.LE_TB_EXCESS_10D_MAX * tier1
    return aggregate_persistent_excess <= p.LE_TB_EXCESS_PERSISTENT_MAX * tier1
