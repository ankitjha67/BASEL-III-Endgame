"""Descriptor -> Basel Framework bucket and risk weight, for every SBM risk class.

The jurisdiction-neutral :class:`FRTBSensitivity` carries descriptors
(currency, tenor, sector, credit quality, market cap, ...). This module maps
them to the MAR21 bucket numbering and risk weights:

    - GIRR: one bucket per currency (MAR21.41); Table 1 risk weights (MAR21.42-21.44)
    - CSR non-securitisation: Table 3 buckets 1-18 (MAR21.51-21.52), Table 4 RWs (MAR21.53)
    - CSR securitisation CTP: Table 3 buckets 1-16 (MAR21.58), Table 6 RWs (MAR21.59)
    - CSR securitisation non-CTP: Table 7 buckets 1-25 (MAR21.62-21.63), MAR21.64-21.67 RWs
    - Equity: Table 9 buckets 1-13 (MAR21.72-21.76), Table 10 RWs (MAR21.77)
    - Commodity: Table 11 buckets 1-11 and RWs (MAR21.82)
    - FX: one bucket per currency (MAR21.86), 15% (/ sqrt 2) (MAR21.87-21.88)
    - Vega: same buckets (MAR21.91); Table 13 RWs (MAR21.92)

``bucket_hint`` (a MAR21-numbered bucket) overrides descriptor mapping for the
numbered risk classes, since the hint is already in MAR21 numbering.
"""

from __future__ import annotations

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.bcbs.frtb import params as p
from src.jurisdictions.frtb_base import (
    CreditSector,
    EquityRiskFactor,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
)

_IG_RATINGS: frozenset[RatingBucket] = frozenset({
    RatingBucket.AAA_TO_AA_MINUS,
    RatingBucket.A_PLUS_TO_A_MINUS,
    RatingBucket.BBB_PLUS_TO_BBB_MINUS,
})
_TENOR_TOL = 1e-9


def is_investment_grade(explicit: bool | None, rating: RatingBucket) -> bool:
    """Credit-quality split of MAR21.51 Table 3 (IG vs HY & NR).

    ``explicit`` (the bank's IG determination, e.g. an internal rating mapped per
    the MAR21.51 FAQ1) wins; otherwise BBB- or better is IG and unrated is "NR"
    (grouped with HY in Table 3).
    """
    if explicit is not None:
        return explicit
    return rating in _IG_RATINGS


def snap_tenor(value: float | None, grid: tuple[float, ...], what: str) -> float:
    """Return the prescribed vertex equal to ``value``.

    MAR21.8 FAQ2: risk factors "must be assigned to the prescribed tenors" (by
    linear interpolation, footnote 274, done by the bank before input). Raises
    ``ValueError`` when the input is not on the grid.
    """
    if value is None:
        raise ValueError(f"{what}: tenor is required")
    for t in grid:
        if abs(t - value) <= _TENOR_TOL:
            return t
    raise ValueError(f"{what}: tenor {value} is not a prescribed vertex {grid} (MAR21.8 FAQ2)")


def _hint_int(s: FRTBSensitivity, valid: range) -> int | None:
    """Parse ``bucket_hint`` as a MAR21 bucket number within ``valid``."""
    if s.bucket_hint is None:
        return None
    try:
        b = int(s.bucket_hint)
    except ValueError as exc:
        raise ValueError(f"bucket_hint {s.bucket_hint!r} is not a MAR21 bucket number") from exc
    if b not in valid:
        raise ValueError(f"bucket_hint {b} outside {valid.start}-{valid.stop - 1}")
    return b


# -------------------------------------------------------------------------
#  Bucket assignment
# -------------------------------------------------------------------------


def girr_bucket(s: FRTBSensitivity) -> str:
    """MAR21.41: each currency is a separate GIRR bucket."""
    if not s.currency:
        raise ValueError("GIRR sensitivity requires a currency (MAR21.41)")
    return s.currency.upper()


def csr_nonsec_bucket(s: FRTBSensitivity) -> int:
    """MAR21.51 Table 3 / MAR21.52 / MAR21.33(2)(b).

    Sector groups map to buckets 1-8 (IG) or 9-15 (HY & NR); issuers without a
    sector go to bucket 16 (MAR21.52(2)); qualified indices go to 17 (IG) or 18 (HY).
    A covered bond that is not IG has no Table 3 bucket and is placed in the
    "other sector" bucket 16 (MAR21.52(2)).
    """
    hint = _hint_int(s, range(1, 19))
    if hint is not None:
        return hint
    ig = is_investment_grade(s.is_investment_grade, s.rating)
    sector = s.credit_sector
    if sector is CreditSector.INDEX:
        return p.CSR_IG_INDEX_BUCKET if ig else p.CSR_HY_INDEX_BUCKET
    if sector is None or sector is CreditSector.OTHER:
        return p.CSR_OTHER_BUCKET
    base = p.CSR_SECTOR_TO_IG_BUCKET[sector]
    if sector is CreditSector.COVERED_BOND:
        return base if ig else p.CSR_OTHER_BUCKET
    return base if ig else base + 8


def csr_ctp_bucket(s: FRTBSensitivity) -> int:
    """MAR21.58(1): Table 3 structure without index buckets 17-18.

    MAR21.34 FAQ / MAR21.58 FAQ1: an index CTP instrument goes to the sector bucket
    of >= 75% of its constituents, otherwise to bucket 16 ("other sector").
    """
    hint = _hint_int(s, range(1, 17))
    if hint is not None:
        return hint
    if s.credit_sector is CreditSector.INDEX:
        return p.CSR_OTHER_BUCKET
    b = csr_nonsec_bucket(s.model_copy(update={"bucket_hint": None}))
    return b if b <= p.CSR_OTHER_BUCKET else p.CSR_OTHER_BUCKET


def csr_sec_nonctp_bucket(s: FRTBSensitivity) -> int:
    """MAR21.62 Table 7 / MAR21.63: credit quality block x sector; else bucket 25."""
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
    """MAR21.72 Table 9, MAR21.33(2)(a), MAR21.74-21.76.

    Indices: bucket 12 when (>= 75% of constituents) large cap and advanced
    economy, else 13. Single names: large cap by economy and sector (1-8), small
    cap by economy (9-10); missing descriptors or OTHER sector -> bucket 11
    (MAR21.76(2)).
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
    return base + 4 if s.is_advanced_economy else base


def commodity_bucket(s: FRTBSensitivity) -> int:
    """MAR21.82 Table 11; unknown group -> bucket 11 (other commodity)."""
    hint = _hint_int(s, range(1, 12))
    if hint is not None:
        return hint
    if s.commodity_group is None:
        return p.COMMODITY_OTHER_BUCKET
    return p.COMMODITY_GROUP_TO_BUCKET[s.commodity_group]


def fx_bucket(s: FRTBSensitivity) -> str:
    """MAR21.86: one bucket per currency against the reporting currency."""
    ccy = s.fx_currency or s.currency
    if not ccy:
        raise ValueError("FX sensitivity requires fx_currency (MAR21.86)")
    return ccy.upper()


def assign_bucket(s: FRTBSensitivity) -> str:
    """Regime bucket key (string) for any sensitivity (MAR21.41-21.91)."""
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


def girr_is_specified(currency: str, options: p.BCBSFRTBOptions) -> bool:
    """MAR21.44 footnote 283: specified currencies plus the domestic reporting currency."""
    ccy = currency.upper()
    return ccy in p.GIRR_SPECIFIED_CURRENCIES or ccy == options.reporting_currency.upper()


def girr_delta_rw(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> float:
    """MAR21.42 Table 1, MAR21.43 (inflation / xccy 1.6%), MAR21.44 (sqrt 2)."""
    specified = options.girr_specified_currency_sqrt2 and girr_is_specified(
        girr_bucket(s), options)
    if s.girr_curve is GIRRCurve.INFLATION:
        rw = p.GIRR_INFLATION_RW
        return rw / p.SQRT2 if specified and p.GIRR_SQRT2_APPLIES_TO_INFLATION_XCCY else rw
    if s.girr_curve is GIRRCurve.XCCY_BASIS:
        rw = p.GIRR_XCCY_BASIS_RW
        return rw / p.SQRT2 if specified and p.GIRR_SQRT2_APPLIES_TO_INFLATION_XCCY else rw
    tenor = snap_tenor(s.tenor_years, p.GIRR_TENORS, "GIRR delta")
    rw = p.GIRR_DELTA_RW[tenor]
    return rw / p.SQRT2 if specified else rw


def csr_nonsec_rw(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> float:
    """MAR21.53 Table 4 and footnote 288 (covered bonds rated AA- or better: 1.5%)."""
    b = csr_nonsec_bucket(s)
    if (b == p.CSR_SECTOR_TO_IG_BUCKET[CreditSector.COVERED_BOND]
            and options.covered_bond_aa_reduction
            and s.rating is RatingBucket.AAA_TO_AA_MINUS):
        return p.CSR_COVERED_BOND_AA_RW
    return p.CSR_NONSEC_RW[b]


def fx_is_liquid(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> bool:
    """MAR21.88 footnotes 293-294: specified pair or a first-order cross of two specified pairs.

    ``fx_pair_is_liquid`` on the sensitivity wins when set; otherwise both the
    reporting currency and the bucket currency must appear in the specified pairs.
    """
    if s.fx_pair_is_liquid is not None:
        return s.fx_pair_is_liquid
    a, b = options.reporting_currency.upper(), fx_bucket(s)
    return a in p.FX_SPECIFIED_CURRENCIES and b in p.FX_SPECIFIED_CURRENCIES and a != b


def fx_delta_rw(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> float:
    """MAR21.87-21.88: 15%, divided by sqrt(2) for liquid pairs at the bank's discretion."""
    if options.fx_liquid_pair_sqrt2 and fx_is_liquid(s, options):
        return p.FX_RW / p.SQRT2
    return p.FX_RW


def delta_risk_weight(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> float:
    """Delta risk weight for any risk class (MAR21.42-21.88)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.GIRR:
        return girr_delta_rw(s, options)
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


def vega_risk_weight(s: FRTBSensitivity) -> float:
    """MAR21.92 Table 13 and its FAQ (equity buckets 1-8, 12, 13 -> 77.78%)."""
    rc = s.risk_class
    if rc is FRTBRiskClass.EQUITY:
        b = equity_bucket(s)
        large = b <= 8 or b in (p.EQUITY_LARGE_AE_INDEX_BUCKET, p.EQUITY_OTHER_INDEX_BUCKET)
        return p.VEGA_RW["EQUITY_LARGE_CAP_INDEX" if large else "EQUITY_SMALL_CAP_OTHER"]
    return p.VEGA_RW[rc.value]


def curvature_risk_weight(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> float:
    """Curvature shock size (MAR21.98-21.99), informational (CVR inputs are pre-computed).

    FX and equity: relative shift equal to the delta RW (MAR21.98). GIRR, CSR and
    commodity: parallel shift equal to the highest delta RW of the bucket (MAR21.99;
    for GIRR the 0.25-year weight, MAR21.99 example).
    """
    rc = s.risk_class
    if rc in (FRTBRiskClass.FX, FRTBRiskClass.EQUITY):
        return delta_risk_weight(s.model_copy(update={"measure": FRTBMeasure.DELTA}), options)
    if rc is FRTBRiskClass.GIRR:
        top = max(p.GIRR_DELTA_RW.values())
        spec = options.girr_specified_currency_sqrt2 and girr_is_specified(girr_bucket(s), options)
        return top / p.SQRT2 if spec else top
    if rc is FRTBRiskClass.CSR_NONSEC:
        return csr_nonsec_rw(s, options)
    if rc is FRTBRiskClass.CSR_SEC_CTP:
        return p.CSR_CTP_RW[csr_ctp_bucket(s)]
    if rc is FRTBRiskClass.CSR_SEC_NONCTP:
        return p.CSR_SEC_NONCTP_RW[csr_sec_nonctp_bucket(s)]
    return p.COMMODITY_RW[commodity_bucket(s)]


def is_other_bucket(risk_class: FRTBRiskClass, bucket: str) -> bool:
    """Buckets aggregated by simple sum of |WS| (MAR21.56, 21.69, 21.79)."""
    if risk_class in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
        return bucket == str(p.CSR_OTHER_BUCKET)
    if risk_class is FRTBRiskClass.CSR_SEC_NONCTP:
        return bucket == str(p.SEC_OTHER_BUCKET)
    if risk_class is FRTBRiskClass.EQUITY:
        return bucket == str(p.EQUITY_OTHER_BUCKET)
    return False


def weighted_sensitivity(s: FRTBSensitivity, options: p.BCBSFRTBOptions) -> float:
    """WS_k = RW_k x s_k (MAR21.4(3)) for delta or vega."""
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
    "fx_is_liquid",
    "girr_bucket",
    "girr_delta_rw",
    "girr_is_specified",
    "is_investment_grade",
    "is_other_bucket",
    "snap_tenor",
    "vega_risk_weight",
    "weighted_sensitivity",
]
