"""EU ASA bucket and risk-weight assignment (CRR Arts 325l-325q, 325ae-325ax, as amended).

Maps the jurisdiction-neutral :class:`~src.jurisdictions.frtb_base.FRTBSensitivity`
descriptors onto the EU bucket taxonomies:

* GIRR -- one bucket per currency (Article 325l(1), (4));
* CSR non-securitisation -- 20 buckets of Article 325ah Table 4 (M12; CRR3 point (171));
* CSR securitisation ACTP -- 18 buckets of Article 325ak Table 6 (M12; CRR3 point (174));
* CSR securitisation non-ACTP -- 25 buckets of Article 325am Table 7 (M12; CRR3 point (175));
* Equity -- 13 buckets of Article 325ap Table 8 (M12);
* Commodity -- 11 buckets plus 3a / 3b of Article 325as Table 9 (CRR3 point (176));
* FX -- one bucket per currency pair against the reporting (or base) currency (Art 325q(1)).

``bucket_hint`` (MAR21 numbering) is ignored except for commodity sensitivities with no
``commodity_group`` -- the EU numbering of the other risk classes differs from MAR21.

Documented ``flags`` keys read here (all optional, default False):

* ``eu_member_state`` -- sovereign issuer is a Member State central government / central bank
  (CSR bucket 1, Art 325ah Table 4); covered-bond issuer established in a Member State (bucket 9).
* ``issuer_cqs_1_to_3`` -- unrated covered bond whose issuing institution has CQS 1-3 (Art
  325ah(3) / 325ak, CRR3 points (171)(b), (174)(b): bucket 4).
* ``eu_most_liquid_currency`` -- GIRR currency in the most-liquid sub-category (Art 325bd(7)(b)).
* ``erm2_currency`` -- GIRR currency of a Member State in ERM II (Art 325bd(5a), CRR3 point (181)).
* ``erm2_pair`` / ``eu_constant_pair`` -- FX pair treatments of Art 325av(2)(a) / 325av(5).
* ``eu_ets_carbon`` / ``non_eu_ets_carbon`` -- commodity buckets 3a / 3b (CRR3 point (176)).
"""

from __future__ import annotations

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.eu.frtb import params as p
from src.jurisdictions.frtb_base import (
    CommodityGroup,
    CreditSector,
    EquityRiskFactor,
    EquitySector,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
    SecAssetClass,
    SecTrancheClass,
)

# -------------------------------------------------------------------------
#  Helpers
# -------------------------------------------------------------------------


def credit_quality_step(rating: RatingBucket) -> int | None:
    """Credit quality step 1-6 of a rating bucket; ``None`` for unrated (Article 136).

    Article 325y(6) and Article 325ah(1) second subparagraph (CRR3 points (167), (171)): the
    credit quality category is the one assigned under the SA for credit risk.
    """
    return p.CQS_OF_RATING.get(rating)


def is_cqs_1_to_3(rating: RatingBucket) -> bool:
    """True for credit quality steps 1 to 3 (Article 325ah Table 4 upper block)."""
    cqs = credit_quality_step(rating)
    return cqs is not None and cqs <= p.IG_CQS_MAX


def flag(s: FRTBSensitivity, key: str) -> bool:
    """Read a documented boolean flag (default False)."""
    return bool(s.flags.get(key, False))


def snap(value: float, grid: tuple[float, ...]) -> float:
    """Nearest prescribed vertex (Article 325l(1) allows linear interpolation or the
    pricing-consistent method; the engine expects inputs already at vertices and snaps)."""
    return min(grid, key=lambda g: (abs(g - value), g))


# -------------------------------------------------------------------------
#  GIRR -- Articles 325l, 325ae
# -------------------------------------------------------------------------


def girr_bucket(s: FRTBSensitivity) -> str:
    """One bucket per currency (Article 325l(1) and (4))."""
    if not s.currency:
        raise ValueError("GIRR sensitivity requires a currency (Article 325l(1))")
    return s.currency.upper()


def girr_is_liquid(
    s: FRTBSensitivity,
    domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
    most_liquid: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
) -> bool:
    """Most liquid currency or domestic currency (Article 325ae(3), CRR3 point (170)).

    Article 325bd(5a) (CRR3 point (181)) adds ERM II currencies to the most liquid sub-category.
    """
    ccy = girr_bucket(s)
    return (
        ccy == domestic_currency.upper()
        or ccy in most_liquid
        or flag(s, "eu_most_liquid_currency")
        or flag(s, "erm2_currency")
    )


def girr_delta_rw(
    s: FRTBSensitivity,
    domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
    most_liquid: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
) -> float:
    """GIRR delta risk weight -- Article 325ae(1) Table 3, (2), and (3) as replaced by CRR3.

    CRR3 point (170): for the most liquid currencies and the domestic currency both the
    risk-free-rate weights and the inflation / cross-currency-basis weight are divided by
    sqrt(2).
    """
    if s.girr_curve == GIRRCurve.RISK_FREE:
        if s.tenor_years is None:
            raise ValueError("GIRR risk-free sensitivity requires tenor_years (Article 325l(1))")
        rw = p.GIRR_RW_BY_TENOR[snap(s.tenor_years, p.GIRR_TENORS)]
    else:
        rw = p.GIRR_RW_INFLATION_XCCY
    if girr_is_liquid(s, domestic_currency, most_liquid):
        rw /= p.GIRR_LIQUID_DIVISOR
    return rw


# -------------------------------------------------------------------------
#  CSR non-securitisation -- Article 325ah Table 4
# -------------------------------------------------------------------------

_NONSEC_SECTOR_BUCKETS: dict[CreditSector, tuple[int, int]] = {
    CreditSector.SOVEREIGN: (2, 11),
    CreditSector.LOCAL_GOVERNMENT: (3, 12),
    CreditSector.FINANCIAL: (4, 13),
    CreditSector.BASIC_MATERIALS: (5, 14),
    CreditSector.CONSUMER: (6, 15),
    CreditSector.TECHNOLOGY: (7, 16),
    CreditSector.HEALTH_CARE: (8, 17),
}
"""Sector -> (CQS 1-3 bucket, CQS 4-6 / unrated bucket) per Article 325ah Table 4."""


def csr_nonsec_bucket(s: FRTBSensitivity) -> int:
    """Bucket of Article 325ah(1) Table 4 (M12; CRR3 point (171)).

    * Member-State sovereign (flag ``eu_member_state``) -> 1 regardless of credit quality.
    * Covered bonds: Member-State issuer -> 9, third-country -> 10 (CQS 1-3); with CQS 4-6 they
      fall in bucket 13 ('... promotional lenders and covered bonds', CRR3); unrated covered
      bonds go to 13 unless the issuer has CQS 1-3 (flag ``issuer_cqs_1_to_3``), in which case
      Article 325ah(3) allows bucket 4.
    * Indices -> 19 (majority IG) / 20 (otherwise); ``is_investment_grade`` decides, else the
      rating.
    * Unassignable sector -> 18 (Article 325ah(2)).
    """
    sector = s.credit_sector or CreditSector.OTHER
    ig = is_cqs_1_to_3(s.rating)
    if sector == CreditSector.SOVEREIGN and flag(s, "eu_member_state"):
        return 1
    if sector == CreditSector.INDEX:
        idx_ig = s.is_investment_grade if s.is_investment_grade is not None else ig
        return 19 if idx_ig else 20
    if sector == CreditSector.COVERED_BOND:
        if ig:
            return 9 if flag(s, "eu_member_state") else 10
        if s.rating == RatingBucket.UNRATED and flag(s, "issuer_cqs_1_to_3"):
            return 4
        return 13
    if sector in _NONSEC_SECTOR_BUCKETS:
        hi, lo = _NONSEC_SECTOR_BUCKETS[sector]
        return hi if ig else lo
    return p.CSR_NONSEC_OTHER_BUCKET


def csr_nonsec_rw(s: FRTBSensitivity, bucket: int) -> float:
    """Delta RW of Article 325ah(1) Table 4; bucket 10 splits CQS 1 (1,5 %) / CQS 2-3 (2,5 %)."""
    if bucket == 10 and credit_quality_step(s.rating) == 1:
        return p.CSR_NONSEC_RW_BUCKET10_CQS1
    return p.CSR_NONSEC_RW[bucket]


# -------------------------------------------------------------------------
#  CSR securitisation ACTP -- Article 325ak Table 6
# -------------------------------------------------------------------------


def csr_ctp_bucket(s: FRTBSensitivity) -> int:
    """Bucket of Article 325ak Table 6 (M12; CRR3 point (174)).

    Credit quality column relabelled by CRR3 to 'credit quality step 1 to 10' / '11 to 17'; the
    engine maps the six SA rating buckets onto it (AAA..BBB- -> 1-10).
    # TODO: VERIFY -- Table 6 cites CQS 1-10 / 11-17 while Article 325ak (CRR3) says the SA
    credit-quality category applies; mapping of SA CQS 1-3 onto 'CQS 1-10' is an interpretation.
    Table 6 has no index buckets: an index sensitivity is placed in bucket 18 (other sector).
    """
    sector = s.credit_sector or CreditSector.OTHER
    ig = is_cqs_1_to_3(s.rating)
    if sector == CreditSector.SOVEREIGN and flag(s, "eu_member_state"):
        return 1
    if sector == CreditSector.COVERED_BOND:
        if ig:
            return 9 if flag(s, "eu_member_state") else 10
        if s.rating == RatingBucket.UNRATED and flag(s, "issuer_cqs_1_to_3"):
            return 4
        return 13
    if sector in _NONSEC_SECTOR_BUCKETS:
        hi, lo = _NONSEC_SECTOR_BUCKETS[sector]
        return hi if ig else lo
    return p.CSR_CTP_OTHER_BUCKET


# -------------------------------------------------------------------------
#  CSR securitisation non-ACTP -- Article 325am Table 7
# -------------------------------------------------------------------------

_SEC_ASSET_OFFSET: dict[SecAssetClass, int] = {
    SecAssetClass.RMBS_PRIME: 0,
    SecAssetClass.RMBS_MIDPRIME: 1,
    SecAssetClass.RMBS_SUBPRIME: 2,
    SecAssetClass.CMBS: 3,
    SecAssetClass.ABS_STUDENT_LOANS: 4,
    SecAssetClass.ABS_CREDIT_CARDS: 5,
    SecAssetClass.ABS_AUTO: 6,
    SecAssetClass.CLO_NON_CTP: 7,
}
_SEC_TRANCHE_BASE: dict[SecTrancheClass, int] = {
    SecTrancheClass.SENIOR_IG: 1,
    SecTrancheClass.NON_SENIOR_IG: 9,
    SecTrancheClass.HY_NR: 17,
}


def csr_sec_nonctp_bucket(s: FRTBSensitivity) -> int:
    """Bucket of Article 325am(1) Table 7 (M12; CRR3 point (175)).

    1-8 senior & CQS 1-10, 9-16 non-senior & CQS 1-10, 17-24 CQS 11-17 & unrated; tranches that
    cannot be assigned to a sector go to bucket 25 (Article 325am(2)). Credit quality follows the
    External Ratings Based Approach (Article 325am(3), CRR3) and is carried by
    ``sec_tranche_class``.
    """
    if s.sec_asset_class is None or s.sec_asset_class not in _SEC_ASSET_OFFSET:
        return p.CSR_SEC_NONCTP_OTHER_BUCKET
    tranche = s.sec_tranche_class or SecTrancheClass.HY_NR
    return _SEC_TRANCHE_BASE[tranche] + _SEC_ASSET_OFFSET[s.sec_asset_class]


# -------------------------------------------------------------------------
#  Equity -- Article 325ap Table 8
# -------------------------------------------------------------------------

_EQ_LARGE_EMERGING: dict[EquitySector, int] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 1,
    EquitySector.TELECOM_INDUSTRIALS: 2,
    EquitySector.MATERIALS_ENERGY: 3,
    EquitySector.FINANCIALS_REALESTATE_TECH: 4,
}
_EQ_LARGE_ADVANCED: dict[EquitySector, int] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 5,
    EquitySector.TELECOM_INDUSTRIALS: 6,
    EquitySector.MATERIALS_ENERGY: 7,
    EquitySector.FINANCIALS_REALESTATE_TECH: 8,
}


def equity_bucket(s: FRTBSensitivity) -> int:
    """Bucket of Article 325ap(1) Table 8 (M12).

    Index sensitivities: 12 (large market cap, advanced economy indices) or 13 (other indices).
    Issuers that cannot be assigned (missing size / economy / sector, or sector OTHER) go to
    bucket 11 (Article 325ap(4)).
    """
    if s.is_equity_index:
        return 12 if (s.is_large_cap and s.is_advanced_economy) else 13
    if (
        s.equity_sector is None
        or s.equity_sector == EquitySector.OTHER
        or s.is_large_cap is None
        or s.is_advanced_economy is None
    ):
        return p.EQUITY_OTHER_BUCKET
    if s.is_large_cap:
        table = _EQ_LARGE_ADVANCED if s.is_advanced_economy else _EQ_LARGE_EMERGING
        return table[s.equity_sector]
    return 10 if s.is_advanced_economy else 9


def equity_delta_rw(s: FRTBSensitivity, bucket: int) -> float:
    """Spot or repo-rate RW of Article 325ap(1) Table 8 (M12)."""
    if s.equity_risk_factor == EquityRiskFactor.REPO:
        return p.EQUITY_RW_REPO[bucket]
    return p.EQUITY_RW_SPOT[bucket]


# -------------------------------------------------------------------------
#  Commodity -- Article 325as Table 9
# -------------------------------------------------------------------------

_COMMODITY_BUCKET: dict[CommodityGroup, str] = {
    CommodityGroup.ENERGY_SOLID: "1",
    CommodityGroup.ENERGY_LIQUID: "2",
    CommodityGroup.ENERGY_ELECTRICITY_CARBON: "3",
    CommodityGroup.FREIGHT: "4",
    CommodityGroup.METALS_NON_PRECIOUS: "5",
    CommodityGroup.GASEOUS_ENERGY: "6",
    CommodityGroup.PRECIOUS_METALS: "7",
    CommodityGroup.GRAINS_OILSEED: "8",
    CommodityGroup.LIVESTOCK_DAIRY: "9",
    CommodityGroup.SOFTS_OTHER_AGRI: "10",
    CommodityGroup.OTHER: "11",
}


def commodity_bucket(s: FRTBSensitivity) -> str:
    """Bucket of Article 325as Table 9 as amended by CRR3 point (176).

    ``ENERGY_ELECTRICITY_CARBON`` maps to bucket 3 (electricity) unless flagged
    ``eu_ets_carbon`` (3a) or ``non_eu_ets_carbon`` (3b).
    """
    if s.commodity_group is None:
        if s.bucket_hint and s.bucket_hint in p.COMMODITY_RW:
            return s.bucket_hint
        return p.COMMODITY_OTHER_BUCKET
    bucket = _COMMODITY_BUCKET[s.commodity_group]
    if bucket == "3":
        if flag(s, "eu_ets_carbon"):
            return "3a"
        if flag(s, "non_eu_ets_carbon"):
            return "3b"
    return bucket


# -------------------------------------------------------------------------
#  FX -- Articles 325q, 325av
# -------------------------------------------------------------------------


def fx_bucket(s: FRTBSensitivity) -> str:
    """One bucket per currency pair with the reporting / base currency (Article 325q(1))."""
    ccy = s.fx_currency or s.currency
    if not ccy:
        raise ValueError("FX sensitivity requires fx_currency (Article 325q(1))")
    return ccy.upper()


def fx_delta_rw(s: FRTBSensitivity) -> float:
    """FX RW -- Article 325av(1) 15 %; (2)(a) ERM II pair / 3; (4) most liquid pair / sqrt(2);
    (5) constant pair / 2 with permission. The most favourable applicable divisor is used.

    A narrower agreed ERM II band (Art 325av(2)(b), (3)) is a numeric input that the bool-only
    ``flags`` cannot carry -- see the contract-change requests.
    """
    rw = p.FX_RW
    candidates = [rw]
    if flag(s, "erm2_pair"):
        candidates.append(rw / p.FX_ERM2_DIVISOR)
    if s.fx_pair_is_liquid:
        candidates.append(rw / p.FX_LIQUID_DIVISOR)
    if flag(s, "eu_constant_pair"):
        candidates.append(rw / p.FX_CONSTANT_PAIR_DIVISOR)
    return min(candidates)


# -------------------------------------------------------------------------
#  Dispatch
# -------------------------------------------------------------------------


def assign_bucket(s: FRTBSensitivity) -> str:
    """EU bucket label for any sensitivity (vega and curvature use the delta buckets,
    Article 325ax(1) as replaced by CRR3 and 325ax(4))."""
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        return girr_bucket(s)
    if rc == FRTBRiskClass.CSR_NONSEC:
        return str(csr_nonsec_bucket(s))
    if rc == FRTBRiskClass.CSR_SEC_CTP:
        return str(csr_ctp_bucket(s))
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return str(csr_sec_nonctp_bucket(s))
    if rc == FRTBRiskClass.EQUITY:
        return str(equity_bucket(s))
    if rc == FRTBRiskClass.COMMODITY:
        return commodity_bucket(s)
    return fx_bucket(s)


def delta_risk_weight(
    s: FRTBSensitivity,
    domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
    most_liquid: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
) -> float:
    """Delta RW for a sensitivity (Articles 325ae-325av)."""
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        return girr_delta_rw(s, domestic_currency, most_liquid)
    if rc == FRTBRiskClass.CSR_NONSEC:
        return csr_nonsec_rw(s, csr_nonsec_bucket(s))
    if rc == FRTBRiskClass.CSR_SEC_CTP:
        return p.CSR_CTP_RW[csr_ctp_bucket(s)]
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return p.CSR_SEC_NONCTP_RW[csr_sec_nonctp_bucket(s)]
    if rc == FRTBRiskClass.EQUITY:
        return equity_delta_rw(s, equity_bucket(s))
    if rc == FRTBRiskClass.COMMODITY:
        return p.COMMODITY_RW[commodity_bucket(s)]
    return fx_delta_rw(s)


def vega_risk_weight(s: FRTBSensitivity) -> float:
    """Vega RW -- Article 325ax(2) Table 1 as replaced by CRR3 point (177)(a)."""
    rc = s.risk_class
    if rc == FRTBRiskClass.EQUITY:
        b = equity_bucket(s)
        large = b in (1, 2, 3, 4, 5, 6, 7, 8, 12, 13)
        return p.VEGA_RW["EQUITY_LARGE_INDEX" if large else "EQUITY_SMALL_OTHER"]
    return p.VEGA_RW[rc.value]


def curvature_risk_weight(
    s: FRTBSensitivity,
    domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
    most_liquid: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
) -> float:
    """Curvature shift size RW_k^curvature (informational: CVR inputs embed it).

    Article 325ax(5): FX and equity -- relative shift equal to the delta RW. Article 325ax(6) as
    replaced by CRR3 point (177)(c): GIRR, CSR and commodity -- parallel shift of the curve by the
    highest prescribed delta RW for the relevant risk bucket.
    """
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        rw = max(p.GIRR_RW_BY_TENOR.values())
        if girr_is_liquid(s, domestic_currency, most_liquid):
            rw /= p.GIRR_LIQUID_DIVISOR
        return rw
    if rc == FRTBRiskClass.CSR_NONSEC:
        b = csr_nonsec_bucket(s)
        return (
            max(p.CSR_NONSEC_RW[b], p.CSR_NONSEC_RW_BUCKET10_CQS1) if b == 10
            else p.CSR_NONSEC_RW[b]
        )
    if rc == FRTBRiskClass.EQUITY:
        return p.EQUITY_RW_SPOT[equity_bucket(s)]
    return delta_risk_weight(s, domestic_currency, most_liquid)


def risk_weight(
    s: FRTBSensitivity,
    domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
    most_liquid: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
) -> float:
    """Risk weight for the sensitivity's measure (delta / vega / curvature)."""
    if s.measure == FRTBMeasure.VEGA:
        return vega_risk_weight(s)
    if s.measure == FRTBMeasure.CURVATURE:
        return curvature_risk_weight(s, domestic_currency, most_liquid)
    return delta_risk_weight(s, domestic_currency, most_liquid)
