"""Descriptor -> MAS Notice 637 SA(MR) bucket and risk weight, for every SBM risk class.

Maps the jurisdiction-neutral :class:`FRTBSensitivity` descriptors to MAS 637 Part VIII
Division 2 buckets and weights:

    - GIRR: one bucket per currency (para 8.2.91); Table 8-1 weights, divided by sqrt(2) for
      EUR, USD, GBP, AUD, JPY, SEK, CAD, SGD -- including the 1.6% inflation / cross-currency
      basis weight (para 8.2.92)
    - CSR non-securitisation: Table 8-3 buckets 1-18 (paras 8.2.100-8.2.104), Table 8-4 weights
      (para 8.2.106), covered bonds CQG "1" 1.5% (para 8.2.107)
    - CSR securitisation CTP: Table 8-3 buckets 1-16 (paras 8.2.114-8.2.114A), Table 8-6
    - CSR securitisation non-CTP: Table 8-7 buckets 1-25 (paras 8.2.119-8.2.121), Table 8-8
    - Equity: Table 8-9 buckets 1-13 (paras 8.2.126-8.2.129), Table 8-10 weights
    - Commodity: Table 8-11 buckets and weights (para 8.2.134)
    - FX: one bucket per currency against the reporting currency (para 8.2.138), 15% (para
      8.2.139), 15% / sqrt(2) for the para 8.2.140 pairs and their first-order crosses
    - Vega: same buckets (para 8.2.142); Table 8-13 weights (para 8.2.144)

Credit quality: "CQG 3 or better" (Table 7M-1) is the upper block of Tables 8-3 and 8-7;
"CQG 4 or worse or not rated" the lower. ``is_investment_grade`` on the sensitivity, when set,
is read as the bank's CQG-3-or-better determination (e.g. an IRBA internal rating mapped with
MAS approval, para 8.2.104(b)(i)); otherwise the rating decides and unrated is "not rated".

``bucket_hint`` (a MAR21/MAS-numbered bucket -- the numbering is identical) overrides the
descriptor mapping for the numbered risk classes.
"""

from __future__ import annotations

import math

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.bcbs.frtb.buckets import snap_tenor
from src.jurisdictions.frtb_base import (
    CreditSector,
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
)
from src.jurisdictions.sg.frtb import params as p

_CQG_1_TO_3: frozenset[RatingBucket] = frozenset({
    RatingBucket.AAA_TO_AA_MINUS,
    RatingBucket.A_PLUS_TO_A_MINUS,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS,
})
"""Table 7M-1 credit quality grades 1-3 (AAA to BBB-)."""


def is_cqg3_or_better(explicit: bool | None, rating: RatingBucket) -> bool:
    """CQG "3" or better per Table 7M-1 (paras 8.2.104, 8.2.112, Table 8-3).

    ``explicit`` (the bank's determination, para 8.2.104(b)(i)) wins; otherwise BBB- or
    better is CQG 1-3 and an unrated name is "not rated" (lower block, para 8.2.104(b)(ii)).
    """
    if explicit is not None:
        return explicit
    return rating in _CQG_1_TO_3


def _hint_int(s: FRTBSensitivity, valid: range) -> int | None:
    """Parse ``bucket_hint`` as a Table 8-3 / 8-7 / 8-9 / 8-11 bucket number within ``valid``."""
    if s.bucket_hint is None:
        return None
    try:
        b = int(s.bucket_hint)
    except ValueError as exc:
        raise ValueError(f"bucket_hint {s.bucket_hint!r} is not a MAS 637 bucket number") from exc
    if b not in valid:
        raise ValueError(f"bucket_hint {b} outside {valid.start}-{valid.stop - 1}")
    return b


# -------------------------------------------------------------------------
#  Bucket assignment
# -------------------------------------------------------------------------


def girr_bucket(s: FRTBSensitivity) -> str:
    """Para 8.2.91: each currency is a separate GIRR delta (and vega / curvature) bucket."""
    if not s.currency:
        raise ValueError("GIRR sensitivity requires a currency (MAS 637 para 8.2.91)")
    return s.currency.upper()


def csr_nonsec_bucket(s: FRTBSensitivity) -> int:
    """Table 8-3 (paras 8.2.100-8.2.104).

    Sector groups map to buckets 1-8 (CQG 3 or better) or 9-15 (CQG 4 or worse / not rated);
    names without a sector go to 16 (para 8.2.100); index risk factors that fail the > 75%
    sector test go to 17 (constituents >= 75% CQG 3 or better) or 18 (para 8.2.104(c)).
    Covered bonds exist only in bucket 8; a covered bond that is not CQG 3 or better has no
    Table 8-3 bucket and is placed in "Other sector" 16 (para 8.2.100).
    """
    hint = _hint_int(s, range(1, 19))
    if hint is not None:
        return hint
    good = is_cqg3_or_better(s.is_investment_grade, s.rating)
    sector = s.credit_sector
    if sector is CreditSector.INDEX:
        return p.CSR_HIGH_QUALITY_INDEX_BUCKET if good else p.CSR_LOW_QUALITY_INDEX_BUCKET
    if sector is None or sector is CreditSector.OTHER:
        return p.CSR_OTHER_BUCKET
    base = p.CSR_SECTOR_TO_CQG3_BUCKET[sector]
    if sector is CreditSector.COVERED_BOND:
        return base if good else p.CSR_OTHER_BUCKET
    return base if good else base + p.CSR_LOW_QUALITY_OFFSET


def csr_ctp_bucket(s: FRTBSensitivity) -> int:
    """Paras 8.2.114-8.2.114A: Table 8-3 without buckets 17-18.

    An index risk factor that fails the > 75% sector test goes to bucket 16 (para
    8.2.114A(b)).
    """
    hint = _hint_int(s, range(1, 17))
    if hint is not None:
        return hint
    if s.credit_sector is CreditSector.INDEX:
        return p.CSR_OTHER_BUCKET
    b = csr_nonsec_bucket(s.model_copy(update={"bucket_hint": None}))
    return min(b, p.CSR_OTHER_BUCKET)


def csr_sec_nonctp_bucket(s: FRTBSensitivity) -> int:
    """Table 8-7 (paras 8.2.119-8.2.121): seniority / quality block x sector, else 25."""
    hint = _hint_int(s, range(1, 26))
    if hint is not None:
        return hint
    if s.sec_tranche_class is None or s.sec_asset_class is None:
        return p.SEC_OTHER_BUCKET
    if s.sec_asset_class not in p.SEC_ASSET_ORDER:
        return p.SEC_OTHER_BUCKET
    return p.SEC_TRANCHE_OFFSET[s.sec_tranche_class] + p.SEC_ASSET_ORDER.index(
        s.sec_asset_class) + 1


def equity_bucket(s: FRTBSensitivity) -> int:
    """Table 8-9 (paras 8.2.126-8.2.129).

    Index risk factors (that fail the > 75% sector test, para 8.2.128(a)): 12 if >= 75% of
    constituents are large cap and advanced economy, else 13 (para 8.2.128(c)). Single names:
    large cap by economy and sector (1-8), small cap by economy (9-10); missing descriptors or
    an OTHER sector -> 11 (para 8.2.129(d)(iii)).
    """
    hint = _hint_int(s, range(1, 14))
    if hint is not None:
        return hint
    if s.is_equity_index:
        if s.is_large_cap and s.is_advanced_economy:
            return p.EQUITY_LARGE_AE_INDEX_BUCKET
        return p.EQUITY_OTHER_INDEX_BUCKET
    if s.is_large_cap is None or s.is_advanced_economy is None:
        return p.EQUITY_OTHER_BUCKET
    if s.equity_sector is None or s.equity_sector not in p.EQUITY_SECTOR_TO_EME_BUCKET:
        return p.EQUITY_OTHER_BUCKET
    if not s.is_large_cap:
        return p.EQUITY_SMALL_AE_BUCKET if s.is_advanced_economy else p.EQUITY_SMALL_EME_BUCKET
    base = p.EQUITY_SECTOR_TO_EME_BUCKET[s.equity_sector]
    return base + p.EQUITY_AE_OFFSET if s.is_advanced_economy else base


def commodity_bucket(s: FRTBSensitivity) -> int:
    """Table 8-11 (para 8.2.134); no group -> bucket 11 (other commodity)."""
    hint = _hint_int(s, range(1, 12))
    if hint is not None:
        return hint
    if s.commodity_group is None:
        return p.COMMODITY_OTHER_BUCKET
    return p.COMMODITY_GROUP_TO_BUCKET[s.commodity_group]


def fx_bucket(s: FRTBSensitivity) -> str:
    """Para 8.2.138: a currency pair of each currency against the reporting currency.

    The bucket key is the non-reporting currency (``fx_currency``, falling back to
    ``currency``); onshore/offshore and deliverable/NDF variants are one factor (para 8.2.54).
    """
    ccy = s.fx_currency or s.currency
    if not ccy:
        raise ValueError("FX sensitivity requires fx_currency (MAS 637 para 8.2.138)")
    return ccy.upper()


def assign_bucket(s: FRTBSensitivity) -> str:
    """MAS 637 bucket key (string) for any sensitivity (paras 8.2.91-8.2.150)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        return girr_bucket(s)
    if rc is FRTBRiskClass.FX:
        return fx_bucket(s)
    if rc is FRTBRiskClass.CSR_NONSEC:
        return str(csr_nonsec_bucket(s))
    if rc is FRTBRiskClass.CSR_SEC_CTP:
        return str(csr_ctp_bucket(s))
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return str(csr_sec_nonctp_bucket(s))
    if rc is FRTBRiskClass.EQUITY:
        return str(equity_bucket(s))
    return str(commodity_bucket(s))


# -------------------------------------------------------------------------
#  Risk weights
# -------------------------------------------------------------------------


def girr_is_sqrt2_currency(currency: str) -> bool:
    """Para 8.2.92(a)/(c): EUR, USD, GBP, AUD, JPY, SEK, CAD and SGD (a fixed list)."""
    return currency.upper() in p.GIRR_SQRT2_CURRENCIES


def girr_delta_rw(s: FRTBSensitivity) -> float:
    """Para 8.2.92 and Table 8-1: tenor weight or 1.6%, / sqrt(2) for the listed currencies."""
    reduce = girr_is_sqrt2_currency(girr_bucket(s))
    if s.girr_curve in (GIRRCurve.INFLATION, GIRRCurve.XCCY_BASIS):
        rw = p.GIRR_INFLATION_XCCY_RW
        return rw / p.SQRT2 if reduce and p.GIRR_SQRT2_APPLIES_TO_INFLATION_XCCY else rw
    tenor = snap_tenor(s.tenor_years, p.GIRR_TENORS, "GIRR delta")
    rw = p.GIRR_DELTA_RW[tenor]
    return rw / p.SQRT2 if reduce else rw


def csr_nonsec_rw(s: FRTBSensitivity, options: p.SGFRTBOptions) -> float:
    """Table 8-4 (para 8.2.106) and para 8.2.107 (covered bonds with CQG "1": 1.5%)."""
    b = csr_nonsec_bucket(s)
    if (b == p.CSR_SECTOR_TO_CQG3_BUCKET[CreditSector.COVERED_BOND]
            and options.covered_bond_cqg1_reduction
            and s.rating is RatingBucket.AAA_TO_AA_MINUS):
        return p.CSR_COVERED_BOND_CQG1_RW
    return p.CSR_NONSEC_RW[b]


def fx_is_specified_pair(s: FRTBSensitivity, options: p.SGFRTBOptions) -> bool:
    """Para 8.2.140: one of the 19 USD pairs or a first-order cross of two of them.

    ``fx_pair_is_liquid`` on the sensitivity wins when set; otherwise both the reporting
    currency and the bucket currency must be members of the para 8.2.140(a) pairs (e.g. with
    SGD reporting: USD/SGD is listed, EUR/SGD is a first-order cross of USD/EUR and USD/SGD).
    """
    if s.fx_pair_is_liquid is not None:
        return s.fx_pair_is_liquid
    a, b = options.reporting_currency.upper(), fx_bucket(s)
    return a in p.FX_SPECIFIED_CURRENCIES and b in p.FX_SPECIFIED_CURRENCIES and a != b


def fx_delta_rw(s: FRTBSensitivity, options: p.SGFRTBOptions) -> float:
    """Paras 8.2.139-8.2.140: 15%, divided by sqrt(2) for specified pairs (mandatory)."""
    return p.FX_RW / p.SQRT2 if fx_is_specified_pair(s, options) else p.FX_RW


def delta_risk_weight(s: FRTBSensitivity, options: p.SGFRTBOptions) -> float:
    """Delta risk weight for any risk class (paras 8.2.92-8.2.140)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        return girr_delta_rw(s)
    if rc is FRTBRiskClass.CSR_NONSEC:
        return csr_nonsec_rw(s, options)
    if rc is FRTBRiskClass.CSR_SEC_CTP:
        return p.CSR_CTP_RW[csr_ctp_bucket(s)]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.CSR_SEC_NONCTP_RW[csr_sec_nonctp_bucket(s)]
    if rc is FRTBRiskClass.EQUITY:
        b = equity_bucket(s)
        if s.equity_risk_factor is EquityRiskFactor.REPO:
            return p.EQUITY_REPO_RW[b]
        return p.EQUITY_SPOT_RW[b]
    if rc is FRTBRiskClass.COMMODITY:
        return p.COMMODITY_RW[commodity_bucket(s)]
    return fx_delta_rw(s, options)


def vega_rw_from_formula(liquidity_horizon_days: int) -> float:
    """Para 8.2.144 fn 669: RW = min(55% x sqrt(LH) / sqrt(10); 100%)."""
    return min(p.VEGA_RW_SIGMA * math.sqrt(liquidity_horizon_days / p.VEGA_BASE_HORIZON_DAYS),
               p.VEGA_RW_CAP)


def vega_risk_weight(s: FRTBSensitivity) -> float:
    """Table 8-13 (para 8.2.144): equity vega buckets 1-8, 12, 13 -> 77.78%; else 100%."""
    rc = s.risk_class
    if rc is FRTBRiskClass.EQUITY:
        b = equity_bucket(s)
        large = b <= p.EQUITY_LAST_LARGE_BUCKET or b in (
            p.EQUITY_LARGE_AE_INDEX_BUCKET, p.EQUITY_OTHER_INDEX_BUCKET)
        return p.VEGA_RW["EQUITY_LARGE_CAP_INDEX" if large else "EQUITY_SMALL_CAP_OTHER"]
    return p.VEGA_RW[rc.value]


def curvature_risk_weight(s: FRTBSensitivity, options: p.SGFRTBOptions) -> float:
    """Curvature shock size (informational; CVR inputs are pre-computed).

    FX and equity: the delta risk weight (para 8.2.151). GIRR, CSR, commodity: the highest
    prescribed delta weight of the bucket (para 8.2.153; GIRR: the 0.25-year weight, fn 674,
    divided by sqrt(2) for the para 8.2.92 currencies).
    """
    rc = s.risk_class
    if rc in (FRTBRiskClass.FX, FRTBRiskClass.EQUITY):
        return delta_risk_weight(s.model_copy(update={"measure": FRTBMeasure.DELTA}), options)
    if rc is FRTBRiskClass.GIRR:
        top = max(p.GIRR_DELTA_RW.values())
        return top / p.SQRT2 if girr_is_sqrt2_currency(girr_bucket(s)) else top
    if rc is FRTBRiskClass.CSR_NONSEC:
        return csr_nonsec_rw(s, options)
    if rc is FRTBRiskClass.CSR_SEC_CTP:
        return p.CSR_CTP_RW[csr_ctp_bucket(s)]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.CSR_SEC_NONCTP_RW[csr_sec_nonctp_bucket(s)]
    return p.COMMODITY_RW[commodity_bucket(s)]


def is_other_bucket(risk_class: FRTBRiskClass, bucket: str) -> bool:
    """"Other sector" buckets aggregated by sum of |WS| (paras 8.2.110, 8.2.117, 8.2.124,
    8.2.132, 8.2.148) and, for curvature, by para 8.2.156."""
    if risk_class in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return bucket == str(p.CSR_OTHER_BUCKET)
    if risk_class is FRTBRiskClass.CSR_SEC_NONCTP:
        return bucket == str(p.SEC_OTHER_BUCKET)
    if risk_class is FRTBRiskClass.EQUITY:
        return bucket == str(p.EQUITY_OTHER_BUCKET)
    return False


def weighted_sensitivity(s: FRTBSensitivity, options: p.SGFRTBOptions) -> float:
    """WS_k = RW_k x s_k (paras 8.2.10(d), 8.2.11(d))."""
    if s.measure is FRTBMeasure.VEGA:
        return vega_risk_weight(s) * s.value
    return delta_risk_weight(s, options) * s.value


__all__ = [
    "assign_bucket",
    "commodity_bucket",
    "csr_ctp_bucket",
    "csr_nonsec_bucket",
    "csr_nonsec_rw",
    "csr_sec_nonctp_bucket",
    "curvature_risk_weight",
    "delta_risk_weight",
    "equity_bucket",
    "fx_bucket",
    "fx_delta_rw",
    "fx_is_specified_pair",
    "girr_bucket",
    "girr_delta_rw",
    "girr_is_sqrt2_currency",
    "is_cqg3_or_better",
    "is_other_bucket",
    "snap_tenor",
    "vega_risk_weight",
    "vega_rw_from_formula",
    "weighted_sensitivity",
]
