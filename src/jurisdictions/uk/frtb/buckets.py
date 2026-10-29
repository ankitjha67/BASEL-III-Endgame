"""UK FRTB-SA bucket and risk-weight assignment from regime-neutral descriptors.

Maps an :class:`~src.jurisdictions.frtb_base.FRTBSensitivity` to the bucket and risk weight of
the PRA Market Risk: Advanced Standardised Approach (CRR) Part (PS1/26 Appendix 1, Annex I),
Section 6 (Articles 325ae-325ax, p. 343-360). Bucket identifiers are strings: GIRR and FX
buckets are currency codes (Art 325l(4), 325q(1)); CSR, equity and commodity buckets are the
table numbers ("1".."18", "3a", "3b", ...).

Descriptor flags read here (``FRTBSensitivity.flags``), documented as contract extensions:

* ``uk_central_government`` -- issuer is the UK central government or the Bank of England:
  CSR bucket 1 for every credit quality (Table 4 'All', p. 345).
* ``gse_mbs`` -- non-tranched mortgage-backed security of a government-sponsored enterprise:
  CSR bucket 2 (Art 325ah(4), p. 347).
* ``carbon_trading`` -- commodity in 'Energy - carbon trading' (bucket 3b) rather than
  'Energy - electricity' (bucket 3a) (Table 9, p. 357).
* ``fx_curvature_div_1_5`` -- FX option whose underlying refers to neither the reporting nor the
  base currency: CVR+/- may be divided by 1.5 (Art 325q(5), p. 328).
"""

from __future__ import annotations

from src.jurisdictions.base import RatingBucket
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
from src.jurisdictions.uk.frtb import params as p

INVESTMENT_GRADE_RATINGS: frozenset[RatingBucket] = frozenset(
    {
        RatingBucket.AAA_TO_AA_MINUS,
        RatingBucket.A_PLUS_TO_A_MINUS,
        RatingBucket.BBB_PLUS_TO_BBB_MINUS,
    }
)
"""ECAI investment grade (Art 325ah(3), p. 347): BBB- or better; unrated is grouped with
non-investment grade ('Non-Investment grade and unrated', Table 4, p. 346)."""

_CSR_SECTOR_IG: dict[CreditSector, str] = {
    CreditSector.SOVEREIGN: "1",
    CreditSector.LOCAL_GOVERNMENT: "2",
    CreditSector.FINANCIAL: "3",
    CreditSector.BASIC_MATERIALS: "4",
    CreditSector.CONSUMER: "5",
    CreditSector.TECHNOLOGY: "6",
    CreditSector.HEALTH_CARE: "7",
    CreditSector.COVERED_BOND: "8",
}
"""Table 4 (p. 345-347) investment-grade sector buckets; Table 6 (p. 349-350) uses the same."""

_CSR_SECTOR_HY: dict[CreditSector, str] = {
    CreditSector.SOVEREIGN: "9",
    CreditSector.LOCAL_GOVERNMENT: "10",
    CreditSector.FINANCIAL: "11",
    CreditSector.BASIC_MATERIALS: "12",
    CreditSector.CONSUMER: "13",
    CreditSector.TECHNOLOGY: "14",
    CreditSector.HEALTH_CARE: "15",
}
"""Table 4 (p. 346-347) non-investment-grade and unrated sector buckets; Table 6 the same."""

_SEC_ASSET_OFFSET: dict[SecAssetClass, int] = {
    SecAssetClass.RMBS_PRIME: 1,
    SecAssetClass.RMBS_MIDPRIME: 2,
    SecAssetClass.RMBS_SUBPRIME: 3,
    SecAssetClass.CMBS: 4,
    SecAssetClass.ABS_STUDENT_LOANS: 5,
    SecAssetClass.ABS_CREDIT_CARDS: 6,
    SecAssetClass.ABS_AUTO: 7,
    SecAssetClass.CLO_NON_CTP: 8,
}
"""Table 7 (p. 351-352): sector position within each credit-quality block of eight."""

_SEC_TRANCHE_BLOCK: dict[SecTrancheClass, int] = {
    SecTrancheClass.SENIOR_IG: 0,
    SecTrancheClass.NON_SENIOR_IG: 8,
    SecTrancheClass.HY_NR: 16,
}
"""Table 7: senior IG buckets 1-8, non-senior IG 9-16, non-IG and unrated 17-24 (p. 351-352)."""

_EQUITY_SECTOR_OFFSET: dict[EquitySector, int] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 1,
    EquitySector.TELECOM_INDUSTRIALS: 2,
    EquitySector.MATERIALS_ENERGY: 3,
    EquitySector.FINANCIALS_REALESTATE_TECH: 4,
}
"""Table 8 (p. 354): large-cap emerging-market buckets 1-4; advanced-economy buckets 5-8."""

_COMMODITY_BUCKET: dict[CommodityGroup, str] = {
    CommodityGroup.ENERGY_SOLID: "1",
    CommodityGroup.ENERGY_LIQUID: "2",
    CommodityGroup.ENERGY_ELECTRICITY_CARBON: "3a",
    CommodityGroup.FREIGHT: "4",
    CommodityGroup.METALS_NON_PRECIOUS: "5",
    CommodityGroup.GASEOUS_ENERGY: "6",
    CommodityGroup.PRECIOUS_METALS: "7",
    CommodityGroup.GRAINS_OILSEED: "8",
    CommodityGroup.LIVESTOCK_DAIRY: "9",
    CommodityGroup.SOFTS_OTHER_AGRI: "10",
    CommodityGroup.OTHER: "11",
}
"""Table 9 (p. 357)."""

_VALID_BUCKETS: dict[FRTBRiskClass, frozenset[str]] = {
    FRTBRiskClass.CSR_NONSEC: frozenset(p.CSR_NONSEC_RW),
    FRTBRiskClass.CSR_SEC_CTP: frozenset(p.CSR_CTP_RW),
    FRTBRiskClass.CSR_SEC_NONCTP: frozenset(p.CSR_SEC_NONCTP_RW),
    FRTBRiskClass.EQUITY: frozenset(p.EQUITY_SPOT_RW),
    FRTBRiskClass.COMMODITY: frozenset(p.COMMODITY_RW),
}


def is_investment_grade(rating: RatingBucket, explicit: bool | None = None) -> bool:
    """Investment grade per nominated-ECAI assessment (Art 325ah(3), p. 347; 325am(3), p. 352).

    ``explicit`` (an internal-rating mapping, Art 325ah(3) second sentence) overrides the rating.
    """
    if explicit is not None:
        return explicit
    return rating in INVESTMENT_GRADE_RATINGS


def _hint(s: FRTBSensitivity) -> str | None:
    """A valid UK bucket pinned by ``bucket_hint`` (UK numbering equals the hint's), else None."""
    valid = _VALID_BUCKETS.get(s.risk_class)
    if s.bucket_hint is not None and valid is not None and s.bucket_hint in valid:
        return s.bucket_hint
    return None


def girr_bucket(s: FRTBSensitivity) -> str:
    """GIRR bucket = currency (Art 325l(1) and (4), p. 322-323)."""
    if not s.currency:
        raise ValueError("GIRR sensitivity requires a currency (Art 325l(4))")
    return s.currency.upper()


def csr_nonsec_bucket(s: FRTBSensitivity) -> str:
    """CSR non-securitisation bucket (Art 325ah(1)-(4), Table 4, p. 345-347).

    UK central government / Bank of England -> 1 for all credit quality; GSE MBS -> 2 (Art
    325ah(4)); IG sector -> 1-8; non-IG and unrated -> 9-15; listed credit indices -> 17 (IG
    majority) / 18; unassignable sector -> 16 (Art 325ah(2)).
    """
    hint = _hint(s)
    if hint is not None:
        return hint
    if s.flags.get("uk_central_government"):
        return "1"
    if s.flags.get("gse_mbs"):
        return p.CSR_NONSEC_GSE_BUCKET
    ig = is_investment_grade(s.rating, s.is_investment_grade)
    sector = s.credit_sector
    if sector is CreditSector.INDEX:
        return "17" if ig else "18"
    if sector is None or sector is CreditSector.OTHER:
        return p.CSR_NONSEC_OTHER_BUCKET
    if ig:
        return _CSR_SECTOR_IG[sector]
    if sector is CreditSector.COVERED_BOND:
        # TODO: VERIFY -- Table 4 (p. 346) has no non-investment-grade covered-bond bucket;
        # Art 325ah(2) sends unassignable exposures to bucket 16 (12%, no diversification),
        # used as the conservative placement.
        return p.CSR_NONSEC_OTHER_BUCKET
    return _CSR_SECTOR_HY[sector]


def csr_ctp_bucket(s: FRTBSensitivity) -> str:
    """ACTP CSR bucket: same sector buckets as non-securitisations (Art 325n(2), p. 325; Table 6,
    p. 349-351). Table 6 has no index buckets."""
    hint = _hint(s)
    if hint is not None:
        return hint
    if s.flags.get("uk_central_government"):
        return "1"
    ig = is_investment_grade(s.rating, s.is_investment_grade)
    sector = s.credit_sector
    if sector is None or sector in (CreditSector.OTHER, CreditSector.INDEX):
        # TODO: VERIFY -- ACTP index positions use one sensitivity to the index (Art 325i(1)(a),
        # p. 319) but Table 6 has no index bucket; bucket 16 (13%) is used conservatively.
        return p.CSR_CTP_OTHER_BUCKET
    if ig:
        return _CSR_SECTOR_IG[sector]
    if sector is CreditSector.COVERED_BOND:
        return p.CSR_CTP_OTHER_BUCKET  # TODO: VERIFY -- no non-IG covered bucket in Table 6
    return _CSR_SECTOR_HY[sector]


def csr_sec_nonctp_bucket(s: FRTBSensitivity) -> str:
    """Non-ACTP securitisation bucket (Art 325am(1)-(3), Table 7, p. 351-352).

    Tranches whose sector or credit-quality block is unknown go to bucket 25 (Art 325am(2)).
    """
    hint = _hint(s)
    if hint is not None:
        return hint
    tranche = s.sec_tranche_class
    asset = s.sec_asset_class
    if tranche is None or asset is None or asset not in _SEC_ASSET_OFFSET:
        return p.CSR_SEC_NONCTP_OTHER_BUCKET
    return str(_SEC_TRANCHE_BLOCK[tranche] + _SEC_ASSET_OFFSET[asset])


def equity_bucket(s: FRTBSensitivity) -> str:
    """Equity bucket (Art 325ap(1)-(4), Table 8, p. 354-355).

    Unknown market capitalisation is treated as small and unknown economy as emerging market
    (both carry the higher risk weights); issuers without a sector go to bucket 11.
    """
    hint = _hint(s)
    if hint is not None:
        return hint
    large = bool(s.is_large_cap)
    advanced = bool(s.is_advanced_economy)
    if s.is_equity_index:
        return "12" if (large and advanced) else "13"
    sector = s.equity_sector
    if sector is None or sector is EquitySector.OTHER:
        return p.EQUITY_OTHER_BUCKET
    if not large:
        return "10" if advanced else "9"
    return str(_EQUITY_SECTOR_OFFSET[sector] + (4 if advanced else 0))


def commodity_bucket(s: FRTBSensitivity) -> str:
    """Commodity bucket (Art 325as Table 9, p. 357); carbon trading -> 3b via flag."""
    hint = _hint(s)
    if hint is not None:
        return hint
    group = s.commodity_group or CommodityGroup.OTHER
    bucket = _COMMODITY_BUCKET[group]
    if bucket == "3a" and s.flags.get("carbon_trading"):
        return "3b"
    return bucket


def fx_bucket(s: FRTBSensitivity) -> str:
    """FX bucket = currency pair against the reporting currency (Art 325q(1)-(2), p. 327)."""
    ccy = s.fx_currency or s.currency
    if not ccy:
        raise ValueError("FX sensitivity requires fx_currency (Art 325q(1))")
    return ccy.upper()


def assign_bucket(s: FRTBSensitivity) -> str:
    """UK bucket for any sensitivity (dispatch over Art 325l-325q / Section 6)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        return girr_bucket(s)
    if rc is FRTBRiskClass.CSR_NONSEC:
        return csr_nonsec_bucket(s)
    if rc is FRTBRiskClass.CSR_SEC_CTP:
        return csr_ctp_bucket(s)
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return csr_sec_nonctp_bucket(s)
    if rc is FRTBRiskClass.EQUITY:
        return equity_bucket(s)
    if rc is FRTBRiskClass.COMMODITY:
        return commodity_bucket(s)
    return fx_bucket(s)


# =========================================================================
#  Risk weights
# =========================================================================


def girr_is_most_liquid(currency: str, domestic_currency: str = p.REPORTING_CURRENCY) -> bool:
    """Most liquid currency or the institution's domestic currency (Art 325ae(3), p. 344;
    Art 325bd(8)(a), p. 251)."""
    ccy = currency.upper()
    return ccy in p.GIRR_MOST_LIQUID_CURRENCIES or ccy == domestic_currency.upper()


def girr_delta_rw(
    s: FRTBSensitivity, vertex: float | None, domestic_currency: str = p.REPORTING_CURRENCY
) -> float:
    """GIRR delta risk weight (Art 325ae(1)-(3), Table 3, p. 344).

    Risk-free rates use the Table 3 weight of the vertex; inflation and cross-currency basis use
    1.6%; both are divided by sqrt(2) for the most liquid currencies and the domestic currency.
    """
    if s.girr_curve is GIRRCurve.RISK_FREE:
        if vertex is None:
            raise ValueError("GIRR risk-free delta requires a vertex (Art 325l(1))")
        rw = p.GIRR_RW[vertex]
    else:
        rw = p.GIRR_INFLATION_XCCY_RW
    if girr_is_most_liquid(girr_bucket(s), domestic_currency):
        rw /= p.SQRT2
    return rw


def csr_nonsec_rw(s: FRTBSensitivity, bucket: str) -> float:
    """CSR non-securitisation RW (Art 325ah(1) Table 4, p. 345-347); covered bonds rated AA- or
    better 1.5%, other IG covered bonds 2.5%."""
    if bucket == "8" and s.rating is RatingBucket.AAA_TO_AA_MINUS:
        return p.CSR_NONSEC_COVERED_AA_RW
    return p.CSR_NONSEC_RW[bucket]


def equity_rw(s: FRTBSensitivity, bucket: str) -> float:
    """Equity spot or repo RW (Art 325ap(1) Table 8, p. 354)."""
    if s.equity_risk_factor is EquityRiskFactor.REPO:
        return p.EQUITY_REPO_RW[bucket]
    return p.EQUITY_SPOT_RW[bucket]


def fx_is_liquid(s: FRTBSensitivity, reporting_currency: str = p.REPORTING_CURRENCY) -> bool:
    """Most liquid currency pair (Art 325av(4), p. 359; Art 325bd(8)(b), p. 251).

    ``fx_pair_is_liquid`` overrides; otherwise both currencies of the pair (the risk-factor
    currency and the reporting currency) must be in the list of 20.
    """
    if s.fx_pair_is_liquid is not None:
        return s.fx_pair_is_liquid
    return (
        fx_bucket(s) in p.FX_MOST_LIQUID_PAIR_CURRENCIES
        and reporting_currency.upper() in p.FX_MOST_LIQUID_PAIR_CURRENCIES
    )


def fx_rw(s: FRTBSensitivity, reporting_currency: str = p.REPORTING_CURRENCY) -> float:
    """FX delta RW: 15%, divided by sqrt(2) for most liquid pairs (Art 325av(1),(4), p. 359)."""
    return p.FX_RW / p.SQRT2 if fx_is_liquid(s, reporting_currency) else p.FX_RW


def delta_rw(
    s: FRTBSensitivity,
    bucket: str,
    vertex: float | None = None,
    domestic_currency: str = p.REPORTING_CURRENCY,
) -> float:
    """Delta risk weight for any risk class (Section 6 Sub-section 1, p. 343-359)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        return girr_delta_rw(s, vertex, domestic_currency)
    if rc is FRTBRiskClass.CSR_NONSEC:
        return csr_nonsec_rw(s, bucket)
    if rc is FRTBRiskClass.CSR_SEC_CTP:
        return p.CSR_CTP_RW[bucket]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.CSR_SEC_NONCTP_RW[bucket]
    if rc is FRTBRiskClass.EQUITY:
        return equity_rw(s, bucket)
    if rc is FRTBRiskClass.COMMODITY:
        return p.COMMODITY_RW[bucket]
    return fx_rw(s, domestic_currency)


def vega_rw(s: FRTBSensitivity, bucket: str) -> float:
    """Vega RW (Art 325ax(2) Table 11, p. 359-360): 100% except equity large cap and indices
    (buckets 1-8, 12, 13) at 77.78%."""
    rc = s.risk_class
    if rc is FRTBRiskClass.EQUITY:
        if bucket in {"9", "10", p.EQUITY_OTHER_BUCKET}:
            return p.VEGA_RW["EQUITY_SMALL_OTHER"]
        return p.VEGA_RW["EQUITY_LARGE_INDEX"]
    return p.VEGA_RW[rc.value]


def curvature_rw(
    s: FRTBSensitivity, bucket: str, domestic_currency: str = p.REPORTING_CURRENCY
) -> float:
    """Curvature RW (Art 325ax(4)-(5), p. 360): FX and equity = the delta RW (relative shift);
    GIRR, CSR and commodity = the highest delta RW of the bucket (parallel shift).

    For information: the SBM consumes CVR+/CVR- computed by the caller with this shift.
    """
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        top = max(p.GIRR_RW.values())
        return top / p.SQRT2 if girr_is_most_liquid(bucket, domestic_currency) else top
    if rc is FRTBRiskClass.CSR_NONSEC:
        return max(p.CSR_NONSEC_RW[bucket], p.CSR_NONSEC_COVERED_AA_RW if bucket == "8" else 0.0)
    if rc is FRTBRiskClass.EQUITY:
        return p.EQUITY_SPOT_RW[bucket]
    return delta_rw(s, bucket, None, domestic_currency)


def risk_weight(
    s: FRTBSensitivity,
    bucket: str,
    vertex: float | None = None,
    domestic_currency: str = p.REPORTING_CURRENCY,
) -> float:
    """Risk weight for the sensitivity's measure (delta, vega or curvature)."""
    if s.measure is FRTBMeasure.VEGA:
        return vega_rw(s, bucket)
    if s.measure is FRTBMeasure.CURVATURE:
        return curvature_rw(s, bucket, domestic_currency)
    return delta_rw(s, bucket, vertex, domestic_currency)
