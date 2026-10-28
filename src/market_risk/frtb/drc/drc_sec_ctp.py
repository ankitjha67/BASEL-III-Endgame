"""Default risk capital requirement, CTP -- ERBA NPR §__.210(d) (p.910-913).

Implements the standardized default risk capital requirement for the
correlation trading portfolio (CTP) under the March 2026 US ERBA NPR
(BCBS d457 MAR22.35-22.46 cross-reference).

Pipeline:

1. Gross default exposure = market value for tranched positions
   (§__.210(d)(1)); nth-to-default products are treated as tranches with
   attachment (N-1)/total names and detachment N/total names.  Non-
   securitization hedges inside the CTP use the non-securitization LGD /
   risk weight (§__.210(d)(2)).
2. Maturity scaling as for non-securitization.
3. Offsetting for the same index AND same tranche (§__.210(d)(2)).
4. Buckets (§__.210(d)(3)): each index is its own bucket; a bespoke
   tranche substantially similar to an index goes into that index's
   bucket; non-securitization hedges go into the bucket of the CTP
   position they hedge.
5. Risk weight for tranched positions = banking-book securitization risk
   weight x 8% (§__.210(d)(3)); Table 1 to §__.210 for non-sec hedges.
6. HBR_CTP computed ONCE across all CTP net default exposures
   (§__.210(d)(4)); per bucket (NOT floored):
   DRC_b = sum_long RW x NDE - HBR_CTP x sum_short RW x |NDE|.
7. Total: DRC_CTP = max( sum_b [ max(DRC_b, 0) + 0.5 x min(DRC_b, 0) ], 0 ).

Monetary inputs are in USD millions ($M) unless stated otherwise.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.enums import (
    DRCCreditQuality,
    DRCExposureType,
    DRCRatingCategory,
    DRCSecCTPBucket,
    DRCSecRating,
    DRCSecSeniority,
    DRCSeniority,
)
from src.core.exceptions import ValidationError
from src.market_risk.frtb.drc.drc_params import (
    CTP_NEGATIVE_BUCKET_FACTOR,
    compute_hedge_benefit_ratio,
    compute_maturity_weight,
    get_bucket,
    get_lgd,
    get_risk_weight,
    rating_to_credit_quality,
)
from src.market_risk.frtb.drc.drc_sec_nonctp import resolve_sec_drc_risk_weight

logger = logging.getLogger(__name__)


# =========================================================================
#  Data models
# =========================================================================


class DRCSecCTPPosition(BaseModel):
    """A CTP default risk position per §__.210(d) (ERBA NPR p.910).

    Attributes:
        tranche_id: Tranche identifier (offsetting key with ``index_name``).
            For a non-securitization hedge use the obligor identifier.
        index_name: Index (bucket) the position belongs to.  Bespoke
            tranches carry the name of the substantially similar index;
            non-securitization hedges carry the index of the CTP position
            they hedge.
        position_type: INDEX_TRANCHE, BESPOKE, NTD or NON_SEC_HEDGE
            (``bucket`` accepted as an input alias).
        market_value: Fair value ($M, positive magnitude) -- the gross
            default exposure for tranched positions.
        maturity_years: Remaining maturity in years (>= 0).
        is_long: True for a long credit exposure, False for short.
        banking_book_risk_weight: §__.132 / §__.133 risk weight (decimal).
        attachment_point / detachment_point / k_g / w: SSFA inputs for the
            §__.133 fallback.  For NTD positions attachment and detachment
            are derived from ``nth`` and ``total_names`` when absent.
        nth / total_names: nth-to-default parameters: A = (N-1)/total,
            D = N/total.
        is_resecuritization: SSFA p = 1.5 / 100% floor.
        rating / seniority: Legacy inputs for ``legacy_rating_table=True``.
        notional / nonsec_seniority / nonsec_exposure_type /
        nonsec_credit_quality / nonsec_rating: Required for NON_SEC_HEDGE
            positions (§__.210(d)(2): non-securitization LGD and Table 1 RW).
    """

    tranche_id: str
    index_name: str
    position_type: DRCSecCTPBucket = DRCSecCTPBucket.INDEX_TRANCHE
    market_value: float
    maturity_years: float
    is_long: bool
    banking_book_risk_weight: float | None = Field(default=None, ge=0.0)
    attachment_point: float | None = Field(default=None, ge=0.0, le=1.0)
    detachment_point: float | None = Field(default=None, ge=0.0, le=1.0)
    k_g: float | None = Field(default=None, gt=0.0, le=1.0)
    w: float | None = Field(default=None, ge=0.0, le=1.0)
    nth: int | None = Field(default=None, ge=1)
    total_names: int | None = Field(default=None, ge=1)
    is_resecuritization: bool = False
    rating: DRCSecRating | None = None
    seniority: DRCSecSeniority | None = None
    # Non-securitization hedge attributes -----------------------------------
    notional: float | None = Field(default=None, gt=0.0)
    nonsec_seniority: DRCSeniority | None = None
    nonsec_exposure_type: DRCExposureType | None = None
    nonsec_credit_quality: DRCCreditQuality | None = None
    nonsec_rating: DRCRatingCategory | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_aliases(cls, data: object) -> object:
        if isinstance(data, dict):
            data = dict(data)
            if "position_type" not in data and "bucket" in data:
                data["position_type"] = data.pop("bucket")
        return data

    @field_validator("market_value")
    @classmethod
    def _market_value_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(
                "market_value must be a non-negative magnitude; use is_long for direction"
            )
        return v

    @field_validator("maturity_years")
    @classmethod
    def _maturity_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("maturity_years must be non-negative")
        return v

    @model_validator(mode="after")
    def _derive_ntd_and_check_hedge(self) -> DRCSecCTPPosition:
        if self.position_type == DRCSecCTPBucket.NTD and self.nth is not None:
            if self.total_names is None or self.nth > self.total_names:
                raise ValueError("NTD requires total_names >= nth")
            if self.attachment_point is None:
                self.attachment_point = (self.nth - 1) / self.total_names
            if self.detachment_point is None:
                self.detachment_point = self.nth / self.total_names
        if self.position_type == DRCSecCTPBucket.NON_SEC_HEDGE:
            if self.notional is None or self.nonsec_seniority is None:
                raise ValueError(
                    "NON_SEC_HEDGE positions require notional and nonsec_seniority "
                    "(§__.210(d)(2))"
                )
            if self.nonsec_exposure_type is None:
                self.nonsec_exposure_type = DRCExposureType.CORPORATE
            if self.nonsec_credit_quality is None:
                if self.nonsec_rating is None:
                    raise ValueError(
                        "NON_SEC_HEDGE positions require nonsec_credit_quality or nonsec_rating"
                    )
                self.nonsec_credit_quality = rating_to_credit_quality(self.nonsec_rating)
        return self

    @property
    def is_nonsec_hedge(self) -> bool:
        """True for a non-securitization hedge inside the CTP."""
        return self.position_type == DRCSecCTPBucket.NON_SEC_HEDGE


class DRCSecCTPBucketDetail(BaseModel):
    """Per-index diagnostics for §__.210(d)(4).

    ``charge`` is the UNFLOORED bucket amount; negative amounts enter the
    total with the 0.5 factor.
    """

    bucket: str
    rw_long: float
    rw_short: float
    charge: float


class DRCSecCTPResult(BaseModel):
    """Result of the CTP default risk capital requirement.

    Attributes:
        total_charge: DRC_CTP per §__.210(d)(4) ($M).
        bucket_charges: Unfloored DRC_b by index.
        bucket_details: Per-index risk-weighted sums.
        hbr_ctp: Single hedge benefit ratio across all CTP positions.
        gross_jtd_long / gross_jtd_short: Maturity-scaled gross exposures.
        net_jtd_long / net_jtd_short: Net exposures after same-tranche offsetting.
        position_count: Number of positions processed.
    """

    total_charge: float
    bucket_charges: dict[str, float]
    bucket_details: list[DRCSecCTPBucketDetail] = []
    hbr_ctp: float = 0.0
    gross_jtd_long: float
    gross_jtd_short: float
    net_jtd_long: float
    net_jtd_short: float
    position_count: int


# =========================================================================
#  Calculator
# =========================================================================


class DRCSecCTPCalculator:
    """CTP default risk capital calculator per §__.210(d).

    Args:
        legacy_rating_table: Explicit opt-in to the pre-NPR rating x
            seniority table for tranched positions lacking banking-book /
            SSFA inputs (``# TODO: VERIFY`` -- never a silent default).

    Usage::

        calculator = DRCSecCTPCalculator()
        result = calculator.calculate(positions)
    """

    def __init__(self, legacy_rating_table: bool = False) -> None:
        """Initialise the calculator."""
        self._legacy = legacy_rating_table

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(self, positions: list[DRCSecCTPPosition]) -> DRCSecCTPResult:
        """Calculate the CTP default risk capital requirement.

        Args:
            positions: CTP positions (tranches, NTDs, bespokes, non-sec hedges).

        Returns:
            :class:`DRCSecCTPResult`.

        Raises:
            ValidationError: If a tranched position has no admissible risk weight.
        """
        if not positions:
            return self._empty_result()
        self._validate_positions(positions)

        # Steps 1-2 -----------------------------------------------------------
        gross = [self._maturity_scaled_jtd(p) for p in positions]
        gross_long = sum(j for j in gross if j > 0)
        gross_short = sum(j for j in gross if j < 0)

        # Step 3: same index + same tranche offsetting ------------------------
        netted = self._net_same_tranche(positions, gross)
        net_long = sum(v for _, v in netted if v > 0)
        net_short = sum(v for _, v in netted if v < 0)

        # Step 6: single HBR across the whole CTP -----------------------------
        hbr_ctp = compute_hedge_benefit_ratio(net_long, net_short)

        # Per-index unfloored amounts -----------------------------------------
        details = self._compute_bucket_amounts(netted, hbr_ctp)
        bucket_charges = {d.bucket: d.charge for d in details}

        # Step 7: cross-bucket aggregation -------------------------------------
        total = self.aggregate_buckets(bucket_charges)

        logger.info(
            "DRC sec CTP: total=%.4f buckets=%d hbr=%.4f gross_long=%.4f gross_short=%.4f "
            "positions=%d",
            total, len(bucket_charges), hbr_ctp, gross_long, gross_short, len(positions),
        )

        return DRCSecCTPResult(
            total_charge=total,
            bucket_charges=bucket_charges,
            bucket_details=details,
            hbr_ctp=hbr_ctp,
            gross_jtd_long=gross_long,
            gross_jtd_short=gross_short,
            net_jtd_long=net_long,
            net_jtd_short=net_short,
            position_count=len(positions),
        )

    # ------------------------------------------------------------------ #
    #  Steps 1-2: gross default exposure                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_gross_jtd(position: DRCSecCTPPosition) -> float:
        """Gross default exposure per §__.210(d)(1)-(2) (ERBA NPR p.911).

        Tranched products: the market value (signed by direction).
        Non-securitization hedges: ``max/min(LGD x notional + P&L, 0)`` with
        the non-securitization LGD of §__.210(b)(1)(iv).

        Args:
            position: CTP position.

        Returns:
            Signed gross default exposure, unscaled.
        """
        if position.is_nonsec_hedge:
            assert position.notional is not None and position.nonsec_seniority is not None
            lgd = get_lgd(position.nonsec_seniority, position.nonsec_credit_quality)
            pnl = position.market_value - position.notional
            raw = lgd * position.notional + pnl
            return max(raw, 0.0) if position.is_long else min(-raw, 0.0)
        return position.market_value if position.is_long else -position.market_value

    def _maturity_scaled_jtd(self, position: DRCSecCTPPosition) -> float:
        """Apply the §__.210(b)(1)(iii) maturity scaling."""
        return self.compute_gross_jtd(position) * compute_maturity_weight(position.maturity_years)

    # ------------------------------------------------------------------ #
    #  Step 3: offsetting -- §__.210(d)(2)                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _net_same_tranche(
        positions: list[DRCSecCTPPosition], gross: list[float]
    ) -> list[tuple[DRCSecCTPPosition, float]]:
        """Offset exposures in the same tranche of the same index.

        §__.210(d)(2) (ERBA NPR p.911): long and short positions in the same
        index AND the same tranche (same attachment / detachment) may be
        offset.  Non-securitization hedges offset only with the same obligor
        key within the same index bucket.

        Args:
            positions: Positions.
            gross: Aligned maturity-scaled gross default exposures.

        Returns:
            ``(representative_position, net_jtd)`` per group.
        """
        groups: dict[tuple[str, str, bool], float] = defaultdict(float)
        rep: dict[tuple[str, str, bool], DRCSecCTPPosition] = {}
        for pos, jtd in zip(positions, gross, strict=True):
            key = (pos.index_name, pos.tranche_id, pos.is_nonsec_hedge)
            groups[key] += jtd
            rep.setdefault(key, pos)
        return [(rep[k], v) for k, v in groups.items() if abs(v) > 0.0]

    # ------------------------------------------------------------------ #
    #  Steps 5-6: risk weights and per-index amounts                      #
    # ------------------------------------------------------------------ #

    def _risk_weight(self, position: DRCSecCTPPosition) -> float:
        """Risk weight per §__.210(d)(3): SEC RW x 8%, or Table 1 for non-sec hedges."""
        if position.is_nonsec_hedge:
            assert position.nonsec_exposure_type is not None
            assert position.nonsec_credit_quality is not None
            bucket = get_bucket(position.nonsec_exposure_type, position.nonsec_credit_quality)
            return get_risk_weight(position.nonsec_credit_quality, bucket)
        return resolve_sec_drc_risk_weight(
            banking_book_risk_weight=position.banking_book_risk_weight,
            attachment_point=position.attachment_point,
            detachment_point=position.detachment_point,
            k_g=position.k_g,
            w=position.w,
            is_resecuritization=position.is_resecuritization,
            legacy_rating_table=self._legacy,
            rating=position.rating,
            seniority=position.seniority,
            label=f"{position.index_name}/{position.tranche_id}",
        )

    def _compute_bucket_amounts(
        self, netted: list[tuple[DRCSecCTPPosition, float]], hbr_ctp: float
    ) -> list[DRCSecCTPBucketDetail]:
        """Unfloored per-index amounts per §__.210(d)(4) (ERBA NPR p.912).

        .. math::

            DRC_b = \\sum_{long} RW_i NDE_i - HBR_{CTP} \\sum_{short} RW_j |NDE_j|

        where HBR_CTP is the single ratio computed across all CTP net
        default exposures.  DRC_b is NOT floored at zero here.

        Args:
            netted: ``(position, net_jtd)`` pairs.
            hbr_ctp: Portfolio-wide hedge benefit ratio.

        Returns:
            Per-index details with the unfloored amount.
        """
        buckets: dict[str, list[tuple[DRCSecCTPPosition, float]]] = defaultdict(list)
        for pos, v in netted:
            buckets[pos.index_name].append((pos, v))

        details: list[DRCSecCTPBucketDetail] = []
        for label, items in buckets.items():
            rw_long = sum(self._risk_weight(p) * v for p, v in items if v > 0)
            rw_short = sum(self._risk_weight(p) * abs(v) for p, v in items if v < 0)
            amount = rw_long - hbr_ctp * rw_short
            logger.debug(
                "DRC CTP bucket=%s rw_long=%.4f rw_short=%.4f hbr=%.4f amount=%.4f",
                label, rw_long, rw_short, hbr_ctp, amount,
            )
            details.append(
                DRCSecCTPBucketDetail(bucket=label, rw_long=rw_long, rw_short=rw_short,
                                      charge=amount)
            )
        return details

    # ------------------------------------------------------------------ #
    #  Step 7: cross-bucket aggregation -- §__.210(d)(4)                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def aggregate_buckets(bucket_amounts: dict[str, float]) -> float:
        """Aggregate unfloored per-index amounts per §__.210(d)(4) (ERBA NPR p.912).

        .. math::

            DRC_{CTP} = \\max\\Big( \\sum_b \\big[ \\max(DRC_b, 0)
                        + 0.5 \\cdot \\min(DRC_b, 0) \\big],\\; 0 \\Big)

        Negative index-level amounts receive 50% recognition against positive
        ones; the total is floored at zero.

        Args:
            bucket_amounts: Unfloored DRC_b by index.

        Returns:
            DRC_CTP.
        """
        total = sum(
            max(v, 0.0) + CTP_NEGATIVE_BUCKET_FACTOR * min(v, 0.0)
            for v in bucket_amounts.values()
        )
        return max(total, 0.0)

    # ------------------------------------------------------------------ #
    #  Validation / empty                                                 #
    # ------------------------------------------------------------------ #

    def _validate_positions(self, positions: list[DRCSecCTPPosition]) -> None:
        """Portfolio-level validation: every position must have a resolvable RW."""
        if not positions:
            raise ValidationError("No positions provided for DRC sec CTP calculation.")
        for pos in positions:
            self._risk_weight(pos)

    @staticmethod
    def _empty_result() -> DRCSecCTPResult:
        """Zero result for an empty portfolio."""
        return DRCSecCTPResult(
            total_charge=0.0,
            bucket_charges={},
            bucket_details=[],
            hbr_ctp=0.0,
            gross_jtd_long=0.0,
            gross_jtd_short=0.0,
            net_jtd_long=0.0,
            net_jtd_short=0.0,
            position_count=0,
        )
