"""OSFI CAR 2026 Chapter 9 -- regime bucket and risk-weight assignment for SBM sensitivities.

Maps the jurisdiction-neutral descriptors of :class:`FRTBSensitivity` onto the CAR 9.5.2.5 bucket
tables (which keep the Basel MAR21 numbering) and returns the delta / vega risk weight.

Descriptor rules (documented defaults where a descriptor is missing):

* credit quality: ``is_investment_grade`` if given, else rating AAA..BBB- = IG (CAR footnote 52:
  "Baa3 or better by Moody's; a rating of BBB- or better by S&P"); unrated = "HY & NR"
  (CAR ¶163 Table 3);
* equity: ``is_large_cap`` must be set by the caller against the CAR ¶186 threshold of
  CAD 2.5 billion; ``None`` -> small cap. ``is_advanced_economy`` ``None`` -> emerging market.
  Missing sector -> bucket 11 "other sector" (CAR ¶188(3)). These defaults are the conservative
  (higher risk-weight) branches;
* ``flags`` keys read here: ``canadian_province_or_agent`` (treated as the Government of Canada,
  CAR ¶163), ``gse_non_tranched_mbs`` (CSR bucket 2 at 1.0%, CAR ¶163),
  ``covered_bond_aa_discretion`` (1.5% for covered bonds rated AA- or higher, footnote 42 --
  opt-in), ``no_sqrt2_discretion`` (opt out of the CAR ¶156 / ¶200 sqrt(2) reductions),
  ``ctp_index`` (CTP sensitivity to an index that cannot be assigned to a sector -> bucket 16,
  footnote 35), ``girr_inflation`` / ``girr_xccy_basis`` are expressed by ``girr_curve``.

References:
    - OSFI CAR 2026 Ch.9 s.9.5.2.4-9.5.2.6, ¶120-207 [Basel Framework MAR21.8-MAR21.95]
"""

from __future__ import annotations

import math

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.ca.frtb import params as p
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

_CSR_SECTOR_IG_BUCKET: dict[CreditSector, int] = {
    CreditSector.SOVEREIGN: 1,
    CreditSector.LOCAL_GOVERNMENT: 2,
    CreditSector.FINANCIAL: 3,
    CreditSector.BASIC_MATERIALS: 4,
    CreditSector.CONSUMER: 5,
    CreditSector.TECHNOLOGY: 6,
    CreditSector.HEALTH_CARE: 7,
}
"""CAR ¶163 Table 3 -- IG sector buckets 1-7; HY&NR = +8 (buckets 9-15) [MAR21.51]."""
_CSR_HY_OFFSET: int = 8
_COVERED_BOND_BUCKET: int = 8
_CSR_INDEX_IG_BUCKET: int = 17
_CSR_INDEX_HY_BUCKET: int = 18


def is_investment_grade(rating: RatingBucket, explicit: bool | None) -> bool:
    """IG test used by CSR and DRC (CAR ¶163; footnotes 49 and 52).

    CAR footnote 52: "Investment grade refers to a rating of Baa3 or better by Moody's; a rating of
    BBB- or better by S&P". An explicit flag (e.g. an OSFI-approved internal-rating mapping under
    CAR ¶163, "map the internal rating to an external rating") overrides the rating bucket.
    """
    if explicit is not None:
        return explicit
    return rating in _IG_RATINGS


def _hint(s: FRTBSensitivity, valid: range) -> int | None:
    """Return a valid numeric ``bucket_hint`` (CAR keeps the MAR21 bucket numbering)."""
    if s.bucket_hint is None:
        return None
    try:
        b = int(s.bucket_hint)
    except ValueError:
        return None
    return b if b in valid else None


def csr_nonsec_bucket(s: FRTBSensitivity) -> int:
    """CSR non-securitisation bucket (CAR 9.5.2.5 ¶163-164 Table 3 [MAR21.51-21.52]).

    Provincial / territorial governments and their agents are treated as the Government of Canada
    (¶163, consistent with CAR Ch.4 s.4.1) -> bucket 1. Non-tranched GSE MBS -> bucket 2 (¶163).
    Indices -> 17 (IG) / 18 (HY) per the 75% rule in ¶145(4). Covered bonds -> 8 when IG; a
    non-IG covered bond has no Table 3 sector and goes to "other sector" 16 (¶164(3)).
    """
    hinted = _hint(s, range(1, 19))
    if hinted is not None:
        return hinted
    if s.flags.get("canadian_province_or_agent", False):
        return 1
    if s.flags.get("gse_non_tranched_mbs", False):
        return p.CSR_GSE_MBS_BUCKET
    ig = is_investment_grade(s.rating, s.is_investment_grade)
    sector = s.credit_sector
    if sector is None or sector == CreditSector.OTHER:
        return p.CSR_OTHER_BUCKET
    if sector == CreditSector.INDEX:
        return _CSR_INDEX_IG_BUCKET if ig else _CSR_INDEX_HY_BUCKET
    if sector == CreditSector.COVERED_BOND:
        return _COVERED_BOND_BUCKET if ig else p.CSR_OTHER_BUCKET
    base = _CSR_SECTOR_IG_BUCKET[sector]
    return base if ig else base + _CSR_HY_OFFSET


def csr_ctp_bucket(s: FRTBSensitivity) -> int:
    """CSR CTP bucket: Table 3 buckets 1-16 without the index buckets (CAR ¶170(1) [MAR21.58]).

    Footnote 35: an index CTP instrument goes to the sector bucket of at least 75% of its
    constituents (pass ``bucket_hint``), otherwise to bucket 16.
    """
    hinted = _hint(s, range(1, 17))
    if hinted is not None:
        return hinted
    if s.credit_sector == CreditSector.INDEX or s.flags.get("ctp_index", False):
        return p.CSR_OTHER_BUCKET
    b = csr_nonsec_bucket(s.model_copy(update={"bucket_hint": None}))
    return b if b <= p.CSR_OTHER_BUCKET else p.CSR_OTHER_BUCKET


def sec_nonctp_bucket(s: FRTBSensitivity) -> int:
    """CSR securitisation non-CTP bucket (CAR 9.5.2.5 ¶174-175 Table 7 [MAR21.62-21.63])."""
    hinted = _hint(s, range(1, 26))
    if hinted is not None:
        return hinted
    if (
        s.sec_asset_class is None
        or s.sec_asset_class not in p.SEC_NONCTP_SECTOR_ORDER
        or s.sec_tranche_class is None
    ):
        return p.SEC_NONCTP_OTHER_BUCKET
    sector_index = p.SEC_NONCTP_SECTOR_ORDER.index(s.sec_asset_class) + 1
    return p.SEC_NONCTP_TRANCHE_OFFSET[s.sec_tranche_class] + sector_index


def equity_bucket(s: FRTBSensitivity) -> int:
    """Equity bucket (CAR 9.5.2.5 ¶184-188 Table 9 [MAR21.72-21.76]).

    Index: bucket 12 if large cap and advanced economy (¶145(3): at least 75% of constituents),
    else 13. Large cap (>= CAD 2.5bn, ¶186) by sector 1-4 (EM) / 5-8 (AE); small cap 9 (EM) /
    10 (AE); unassignable sector -> 11.
    """
    hinted = _hint(s, range(1, 14))
    if hinted is not None:
        return hinted
    large = bool(s.is_large_cap)
    advanced = bool(s.is_advanced_economy)
    if s.is_equity_index:
        return (
            p.EQUITY_INDEX_LARGE_AE_BUCKET if (large and advanced)
            else p.EQUITY_INDEX_OTHER_BUCKET
        )
    if s.equity_sector is None or s.equity_sector not in p.EQUITY_SECTOR_OFFSET:
        return p.EQUITY_OTHER_BUCKET
    if not large:
        return p.EQUITY_SMALL_CAP_AE_BUCKET if advanced else p.EQUITY_SMALL_CAP_EM_BUCKET
    offset = p.EQUITY_SECTOR_OFFSET[s.equity_sector]
    return offset + 4 if advanced else offset


def commodity_bucket(s: FRTBSensitivity) -> int:
    """Commodity bucket (CAR 9.5.2.5 ¶194 Table 11 [MAR21.82]); missing group -> 11 (other)."""
    hinted = _hint(s, range(1, 12))
    if hinted is not None:
        return hinted
    if s.commodity_group is None:
        return p.COMMODITY_OTHER_BUCKET
    return p.COMMODITY_BUCKET_OF[s.commodity_group]


def assign_bucket(s: FRTBSensitivity, reporting_currency: str = "CAD") -> str:
    """Regime bucket for a sensitivity (CAR 9.5.2.5-9.5.2.7 ¶153-213 [MAR21.39-21.101]).

    GIRR: each currency is a bucket (¶153 [MAR21.41]). FX: each exchange rate against the
    reporting currency is a bucket (¶198 [MAR21.86]). Vega and curvature reuse the delta buckets
    (¶203, ¶209 [MAR21.91, MAR21.97]).
    """
    rc = s.risk_class
    if rc == FRTBRiskClass.GIRR:
        if not s.currency:
            raise ValueError("GIRR sensitivity requires a currency (CAR ¶153)")
        return s.currency.upper()
    if rc == FRTBRiskClass.FX:
        ccy = s.fx_currency or s.currency
        if not ccy:
            raise ValueError("FX sensitivity requires fx_currency (CAR ¶198)")
        return f"{ccy.upper()}/{reporting_currency.upper()}"
    if rc == FRTBRiskClass.CSR_NONSEC:
        return str(csr_nonsec_bucket(s))
    if rc == FRTBRiskClass.CSR_SEC_CTP:
        return str(csr_ctp_bucket(s))
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return str(sec_nonctp_bucket(s))
    if rc == FRTBRiskClass.EQUITY:
        return str(equity_bucket(s))
    return str(commodity_bucket(s))


def girr_reduced_rw_currencies(reporting_currency: str) -> frozenset[str]:
    """Currencies eligible for the sqrt(2) GIRR reduction (CAR ¶156 [MAR21.44]).

    "EUR, USD, GBP, AUD, JPY, SEK, CAD as well as the domestic reporting currency".
    """
    return p.GIRR_SPECIFIED_CURRENCIES | {reporting_currency.upper()}


def fx_pair_is_specified(ccy: str, reporting_currency: str) -> bool:
    """Specified FX pair or first-order cross (CAR ¶200 [MAR21.88]).

    The specified pairs are all USD/x for x in the list; a first-order cross is x/y with both x and
    y in the list. Hence a pair qualifies iff both currencies are in the specified set.
    """
    a, b = ccy.upper(), reporting_currency.upper()
    return a in p.FX_SPECIFIED_PAIR_CURRENCIES and b in p.FX_SPECIFIED_PAIR_CURRENCIES


def delta_risk_weight(
    s: FRTBSensitivity, bucket: str, tenor: float | None, reporting_currency: str = "CAD",
) -> float:
    """Delta risk weight for a sensitivity already assigned to ``bucket``.

    ``tenor`` is the prescribed vertex the sensitivity has been allocated to (GIRR only).

    * GIRR: Table 1 (¶154); inflation / cross-currency basis 1.6% (¶155); Table 1 weights / sqrt(2)
      for the ¶156 currencies unless ``no_sqrt2_discretion``.
    * CSR non-sec: Table 4 (¶165); GSE MBS 1.0% (¶163); covered bonds AA- or better 1.5% on opt-in
      (footnote 42).
    * CSR CTP: Table 6 (¶171). Sec non-CTP: Table 8 and ¶177-179.
    * Equity: Table 10 spot / repo (¶189). Commodity: Table 11 (¶194).
    * FX: 15% (¶199), / sqrt(2) for specified pairs and first-order crosses (¶200).
    """
    rc = s.risk_class
    no_sqrt2 = s.flags.get("no_sqrt2_discretion", False)
    if rc == FRTBRiskClass.GIRR:
        if s.girr_curve == GIRRCurve.INFLATION:
            return p.GIRR_INFLATION_RW
        if s.girr_curve == GIRRCurve.XCCY_BASIS:
            return p.GIRR_XCCY_BASIS_RW
        if tenor is None:
            raise ValueError("GIRR delta requires a tenor (CAR ¶120)")
        rw = p.GIRR_RISK_WEIGHTS[tenor]
        if not no_sqrt2 and bucket in girr_reduced_rw_currencies(reporting_currency):
            rw /= p.SQRT2
        return rw
    if rc == FRTBRiskClass.CSR_NONSEC:
        b = int(bucket)
        if s.flags.get("gse_non_tranched_mbs", False) and b == p.CSR_GSE_MBS_BUCKET:
            return p.CSR_GSE_MBS_RW
        if (
            b == _COVERED_BOND_BUCKET
            and s.flags.get("covered_bond_aa_discretion", False)
            and s.rating == RatingBucket.AAA_TO_AA_MINUS
        ):
            return p.CSR_COVERED_BOND_AA_RW
        return p.CSR_NONSEC_RW[b]
    if rc == FRTBRiskClass.CSR_SEC_CTP:
        return p.CSR_CTP_RW[int(bucket)]
    if rc == FRTBRiskClass.CSR_SEC_NONCTP:
        return p.SEC_NONCTP_RW[int(bucket)]
    if rc == FRTBRiskClass.EQUITY:
        b = int(bucket)
        if s.equity_risk_factor == EquityRiskFactor.REPO:
            return p.EQUITY_REPO_RW[b]
        return p.EQUITY_SPOT_RW[b]
    if rc == FRTBRiskClass.COMMODITY:
        return p.COMMODITY_RW[int(bucket)]
    # FX
    ccy = (s.fx_currency or s.currency or "").upper()
    liquid = s.fx_pair_is_liquid
    if liquid is None:
        liquid = fx_pair_is_specified(ccy, reporting_currency)
    if liquid and not no_sqrt2:
        return p.FX_RW / p.SQRT2
    return p.FX_RW


def vega_risk_weight(s: FRTBSensitivity, bucket: str) -> float:
    """Vega risk weight (CAR 9.5.2.6 ¶204 Table 13 and footnote 47 [MAR21.92]).

    Equity: 77.78% (20-day LH) for buckets 1-8 and 12-13; 100% (60-day LH) for 9, 10, 11.
    """
    rc = s.risk_class
    if rc == FRTBRiskClass.EQUITY:
        b = int(bucket)
        if b in (p.EQUITY_SMALL_CAP_EM_BUCKET, p.EQUITY_SMALL_CAP_AE_BUCKET,
                 p.EQUITY_OTHER_BUCKET):
            return p.VEGA_RW["EQUITY_SMALL_CAP_AND_OTHER"]
        return p.VEGA_RW["EQUITY_LARGE_CAP_AND_INDICES"]
    return p.VEGA_RW[rc.value]


def vega_rw_from_formula(liquidity_horizon_days: int) -> float:
    """Footnote 47 formula RWk = min[RWσ·sqrt(LH/10); 100%] with RWσ = 55% (CAR ¶204)."""
    return min(p.VEGA_RW_SIGMA * math.sqrt(liquidity_horizon_days / 10.0), 1.0)


def curvature_risk_weight(
    s: FRTBSensitivity, bucket: str, reporting_currency: str = "CAD",
) -> float:
    """Curvature shock size (CAR 9.5.2.7 ¶210-211 [MAR21.98-21.99]) -- informational.

    FX and equity: the delta risk weight (relative shift). GIRR, CSR, commodity: the highest
    prescribed delta risk weight of the bucket applied as a parallel shift (e.g. GIRR 0.25-year
    weight). The engine takes CVR+/CVR- as inputs; this is exposed for callers computing them.
    """
    rc = s.risk_class
    if rc in (FRTBRiskClass.FX, FRTBRiskClass.EQUITY):
        return delta_risk_weight(s, bucket, None, reporting_currency)
    if rc == FRTBRiskClass.GIRR:
        rf = s.model_copy(update={"girr_curve": GIRRCurve.RISK_FREE})
        return max(delta_risk_weight(rf, bucket, t, reporting_currency) for t in p.GIRR_TENORS)
    return delta_risk_weight(s, bucket, None, reporting_currency)


def measure_tenors(s: FRTBSensitivity) -> tuple[float, ...]:
    """Prescribed vertex grid for a sensitivity's measure and risk class (CAR ¶120-126)."""
    if s.measure == FRTBMeasure.VEGA:
        return p.VEGA_TENORS
    if s.risk_class == FRTBRiskClass.GIRR:
        return p.GIRR_TENORS
    if s.risk_class == FRTBRiskClass.COMMODITY:
        return p.COMMODITY_TENORS
    if s.risk_class in (
        FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP, FRTBRiskClass.CSR_SEC_NONCTP,
    ):
        return p.CSR_TENORS
    return ()


def allocate_to_vertices(t: float, grid: tuple[float, ...]) -> list[tuple[float, float]]:
    """Linear-interpolation split of a sensitivity at ``t`` onto the prescribed vertices.

    CAR 9.5.2.4 ¶120 footnote 28 / ¶127: "the assignment of risk factors and sensitivities to the
    specified tenors should be performed by linear interpolation". Outside the grid the whole
    amount goes to the nearest end vertex. Returns (vertex, weight) pairs summing to 1.
    """
    if not grid:
        return [(t, 1.0)]
    if t <= grid[0]:
        return [(grid[0], 1.0)]
    if t >= grid[-1]:
        return [(grid[-1], 1.0)]
    for lo, hi in zip(grid, grid[1:], strict=False):
        if t == lo:
            return [(lo, 1.0)]
        if lo < t < hi:
            w_hi = (t - lo) / (hi - lo)
            return [(lo, 1.0 - w_hi), (hi, w_hi)]
    return [(grid[-1], 1.0)]
