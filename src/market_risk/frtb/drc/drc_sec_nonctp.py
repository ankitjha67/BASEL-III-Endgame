"""Default risk capital requirement, securitization non-CTP -- ERBA NPR §__.210(c) (p.907-910).

Implements the standardized default risk capital requirement for
securitization positions outside the correlation trading portfolio under
the March 2026 US ERBA NPR (BCBS d457 MAR22.24-22.34 cross-reference).

Pipeline:

1. Gross default exposure = market value (§__.210(c)(1); no LGD).
2. Maturity scaling as for non-securitization (§__.210(c)(2)).
3. Offsetting only for the same underlying pool AND same tranche (or via
   decomposition into replicating tranches supplied by the caller)
   (§__.210(c)(2)).
4. Buckets (§__.210(c)(3)(i)): corporate positions, plus asset class
   {ABCP, auto, RMBS, credit cards, CMBS, CLO, CDO-squared, SME, student
   loans, other retail, other wholesale} x region {Asia, Europe, North
   America, other}.
5. Risk weight (§__.210(c)(3)(ii)) = banking-book securitization risk
   weight (§__.132 / §__.133 SEC-SA) x 8%.
6. Bucket charge (§__.210(c)(3)(iii)) with the same HBR formula as
   non-securitization:
   DRC_b = max( sum_long RW x NDE - HBR_b x sum_short RW x |NDE|, 0 ).
7. Total = simple sum across buckets.

Monetary inputs are in USD millions ($M) unless stated otherwise.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.enums import (
    DRCSecBucket,
    DRCSecRating,
    DRCSecRegion,
    DRCSecSeniority,
)
from src.core.exceptions import ValidationError
from src.market_risk.frtb.drc.drc_params import (
    compute_hedge_benefit_ratio,
    compute_maturity_weight,
    compute_sec_sa_risk_weight,
    get_legacy_sec_risk_weight,
    get_sec_drc_risk_weight,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Shared risk-weight resolution (also used by the CTP calculator)
# =========================================================================


def resolve_sec_drc_risk_weight(
    *,
    banking_book_risk_weight: float | None,
    attachment_point: float | None,
    detachment_point: float | None,
    k_g: float | None,
    w: float | None,
    is_resecuritization: bool,
    legacy_rating_table: bool = False,
    rating: DRCSecRating | None = None,
    seniority: DRCSecSeniority | None = None,
    label: str = "",
) -> float:
    """Resolve the DRC risk weight of a tranched position per §__.210(c)(3)(ii).

    Precedence:

    1. ``banking_book_risk_weight`` (the §__.132 / §__.133 risk weight the
       banking organization already computed) x 8%.
    2. Otherwise the SEC-SA risk weight recomputed from the SSFA inputs
       (attachment, detachment, K_G, W) per §__.133, x 8%.
    3. Otherwise, ONLY when ``legacy_rating_table=True`` is passed
       explicitly, the legacy rating x seniority table
       (``# TODO: VERIFY`` -- not the NPR rule).
    4. Otherwise a :class:`ValidationError` is raised; the invented table is
       never a silent default.

    Args:
        banking_book_risk_weight: Decimal banking-book RW (0.15 = 15%).
        attachment_point: SSFA attachment A.
        detachment_point: SSFA detachment D.
        k_g: Pool capital requirement K_G.
        w: Pool delinquency ratio W (defaults to 0 when SSFA inputs given).
        is_resecuritization: SSFA p = 1.5 / 100% floor.
        legacy_rating_table: Explicit opt-in to the legacy table.
        rating: Legacy rating (required with ``legacy_rating_table``).
        seniority: Legacy seniority (required with ``legacy_rating_table``).
        label: Identifier for error messages.

    Returns:
        DRC risk weight as a decimal.

    Raises:
        ValidationError: If no admissible risk-weight source is available.
    """
    if banking_book_risk_weight is not None:
        return get_sec_drc_risk_weight(banking_book_risk_weight)

    if attachment_point is not None and detachment_point is not None and k_g is not None:
        bb_rw = compute_sec_sa_risk_weight(
            attachment_point=attachment_point,
            detachment_point=detachment_point,
            k_g=k_g,
            w=w if w is not None else 0.0,
            is_resecuritization=is_resecuritization,
        )
        return get_sec_drc_risk_weight(bb_rw)

    if legacy_rating_table:
        if rating is None or seniority is None:
            raise ValidationError(
                f"Position {label!r}: legacy_rating_table=True requires rating and seniority."
            )
        return get_legacy_sec_risk_weight(rating, seniority)

    raise ValidationError(
        f"Position {label!r}: no securitization risk weight available.  Supply "
        "banking_book_risk_weight (§__.132/§__.133 RW) or the SSFA inputs "
        "attachment_point / detachment_point / k_g (and optionally w) per "
        "§__.210(c)(3)(ii)."
    )


# =========================================================================
#  Data models
# =========================================================================


class DRCSecNonCTPPosition(BaseModel):
    """A securitization non-CTP default risk position per §__.210(c) (ERBA NPR p.907).

    Attributes:
        tranche_id: Tranche identifier (offsetting key with ``pool_id``).
        pool_id: Underlying pool / deal identifier (``deal_name`` accepted
            as an input alias).
        asset_class: Underlying asset class (``bucket`` accepted as alias);
            CORPORATE forms its own bucket without a region.
        region: Region of the underlying exposures (required unless
            ``asset_class`` is CORPORATE).
        market_value: Fair value of the position ($M, positive magnitude;
            direction given by ``is_long``).  This IS the gross default
            exposure (§__.210(c)(1)).
        maturity_years: Remaining maturity in years (>= 0).
        is_long: True for a long credit exposure, False for short.
        banking_book_risk_weight: §__.132 / §__.133 risk weight as a decimal
            (0.15 for 15%).  Preferred input for §__.210(c)(3)(ii).
        attachment_point / detachment_point / k_g / w: SSFA inputs used to
            recompute the §__.133 risk weight when the banking-book RW is
            not supplied.
        is_resecuritization: Resecuritization flag for the SSFA fallback.
        is_cash_position: Cash (non-derivative) securitization; the DRC of
            an individual cash position may be capped at its fair value.
        rating / seniority: Legacy inputs, used only with
            ``legacy_rating_table=True``.
        notional: Optional face value for reporting (not used in the charge).
    """

    tranche_id: str
    pool_id: str
    asset_class: DRCSecBucket
    region: DRCSecRegion | None = None
    market_value: float
    maturity_years: float
    is_long: bool
    banking_book_risk_weight: float | None = Field(default=None, ge=0.0)
    attachment_point: float | None = Field(default=None, ge=0.0, le=1.0)
    detachment_point: float | None = Field(default=None, ge=0.0, le=1.0)
    k_g: float | None = Field(default=None, gt=0.0, le=1.0)
    w: float | None = Field(default=None, ge=0.0, le=1.0)
    is_resecuritization: bool = False
    is_cash_position: bool = True
    rating: DRCSecRating | None = None
    seniority: DRCSecSeniority | None = None
    notional: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="before")
    @classmethod
    def _accept_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "pool_id" not in data and "deal_name" in data:
                data["pool_id"] = data.pop("deal_name")
            if "asset_class" not in data and "bucket" in data:
                data["asset_class"] = data.pop("bucket")
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
    def _region_required(self) -> DRCSecNonCTPPosition:
        if self.asset_class != DRCSecBucket.CORPORATE and self.region is None:
            raise ValueError(
                "region is required for non-corporate securitization positions "
                "(§__.210(c)(3)(i) buckets are asset class x region)"
            )
        return self

    @property
    def bucket_label(self) -> str:
        """§__.210(c)(3)(i) bucket key: CORPORATE or ``<asset_class>_<region>``."""
        if self.asset_class == DRCSecBucket.CORPORATE:
            return DRCSecBucket.CORPORATE.value
        assert self.region is not None
        return f"{self.asset_class.value}_{self.region.value}"


class DRCSecBucketDetail(BaseModel):
    """Per-bucket diagnostics for §__.210(c)(3)(iii)."""

    bucket: str
    rw_long: float
    rw_short: float
    hbr: float
    charge: float


class DRCSecNonCTPResult(BaseModel):
    """Result of the securitization non-CTP default risk capital requirement.

    Attributes:
        total_charge: Sum of bucket charges ($M).
        bucket_charges: Charge by bucket label.
        bucket_details: Per-bucket HBR and risk-weighted sums.
        gross_jtd_long / gross_jtd_short: Maturity-scaled gross default
            exposures before offsetting.
        net_jtd_long / net_jtd_short: Net default exposures after same
            pool / same tranche offsetting.
        position_count: Number of positions processed.
    """

    total_charge: float
    bucket_charges: dict[str, float]
    bucket_details: list[DRCSecBucketDetail] = []
    gross_jtd_long: float
    gross_jtd_short: float
    net_jtd_long: float = 0.0
    net_jtd_short: float = 0.0
    position_count: int


# =========================================================================
#  Calculator
# =========================================================================


class DRCSecNonCTPCalculator:
    """Securitization non-CTP default risk capital calculator per §__.210(c).

    Args:
        legacy_rating_table: Explicit opt-in to the pre-NPR rating x
            seniority table when no banking-book / SSFA inputs are present
            (``# TODO: VERIFY`` -- never a silent default).
        cap_cash_positions_at_fair_value: Cap each cash position's DRC
            contribution at its fair value (§__.210(c)(3)(ii)).

    Usage::

        calculator = DRCSecNonCTPCalculator()
        result = calculator.calculate(positions)
    """

    def __init__(
        self,
        legacy_rating_table: bool = False,
        cap_cash_positions_at_fair_value: bool = True,
    ) -> None:
        """Initialise the calculator."""
        self._legacy = legacy_rating_table
        self._cap_at_fair_value = cap_cash_positions_at_fair_value

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(self, positions: list[DRCSecNonCTPPosition]) -> DRCSecNonCTPResult:
        """Calculate the securitization non-CTP default risk capital requirement.

        Args:
            positions: Securitization non-CTP positions.

        Returns:
            :class:`DRCSecNonCTPResult`.

        Raises:
            ValidationError: If a position has no admissible risk weight.
        """
        if not positions:
            return self._empty_result()
        self._validate_positions(positions)

        # Steps 1-2: gross DE = market value, maturity scaled --------------
        gross = [self._maturity_scaled_jtd(p) for p in positions]
        gross_long = sum(j for j in gross if j > 0)
        gross_short = sum(j for j in gross if j < 0)

        # Step 3: same pool + same tranche offsetting ---------------------
        netted = self._net_same_tranche(positions, gross)
        net_long = sum(v for _, _, v in netted if v > 0)
        net_short = sum(v for _, _, v in netted if v < 0)

        # Steps 4-6: bucket charges with HBR -------------------------------
        details = self._compute_bucket_charges(netted)
        bucket_charges = {d.bucket: d.charge for d in details}
        total = sum(bucket_charges.values())

        logger.info(
            "DRC sec non-CTP: total=%.4f buckets=%d gross_long=%.4f gross_short=%.4f "
            "positions=%d",
            total, len(bucket_charges), gross_long, gross_short, len(positions),
        )

        return DRCSecNonCTPResult(
            total_charge=total,
            bucket_charges=bucket_charges,
            bucket_details=details,
            gross_jtd_long=gross_long,
            gross_jtd_short=gross_short,
            net_jtd_long=net_long,
            net_jtd_short=net_short,
            position_count=len(positions),
        )

    # ------------------------------------------------------------------ #
    #  Steps 1-2                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_gross_jtd(position: DRCSecNonCTPPosition) -> float:
        """Gross default exposure per §__.210(c)(1) (ERBA NPR p.908).

        For securitization positions the gross default exposure is the
        market value of the position (no LGD assumption): positive for a
        long, negative for a short.

        Args:
            position: Securitization non-CTP position.

        Returns:
            Signed gross default exposure, unscaled.
        """
        return position.market_value if position.is_long else -position.market_value

    def _maturity_scaled_jtd(self, position: DRCSecNonCTPPosition) -> float:
        """Apply §__.210(c)(2) maturity scaling (same rule as §__.210(b)(1)(iii))."""
        return self.compute_gross_jtd(position) * compute_maturity_weight(position.maturity_years)

    # ------------------------------------------------------------------ #
    #  Step 3: offsetting -- §__.210(c)(2)                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _net_same_tranche(
        positions: list[DRCSecNonCTPPosition], gross: list[float]
    ) -> list[tuple[str, DRCSecNonCTPPosition, float]]:
        """Offset exposures sharing the same pool AND the same tranche.

        §__.210(c)(2) (ERBA NPR p.908): offsetting is permitted only between
        positions in the same tranche of the same underlying pool (a
        position decomposed into replicating tranches must be supplied as
        those tranches).  Positions in different tranches, or different
        pools, are never offset here; the HBR gives the partial benefit.

        Args:
            positions: Positions.
            gross: Aligned maturity-scaled gross default exposures.

        Returns:
            ``(bucket_label, representative_position, net_jtd)`` per
            (pool, tranche, bucket) group with non-zero net exposure.
        """
        groups: dict[tuple[str, str, str], float] = defaultdict(float)
        rep: dict[tuple[str, str, str], DRCSecNonCTPPosition] = {}
        for pos, jtd in zip(positions, gross, strict=True):
            key = (pos.pool_id, pos.tranche_id, pos.bucket_label)
            groups[key] += jtd
            rep.setdefault(key, pos)
        return [
            (key[2], rep[key], v) for key, v in groups.items() if abs(v) > 0.0
        ]

    # ------------------------------------------------------------------ #
    #  Steps 4-6: bucket charges -- §__.210(c)(3)                         #
    # ------------------------------------------------------------------ #

    def _risk_weight(self, position: DRCSecNonCTPPosition) -> float:
        """DRC risk weight = banking-book RW x 8% (§__.210(c)(3)(ii))."""
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
            label=position.tranche_id,
        )

    def _weighted_exposure(self, position: DRCSecNonCTPPosition, net_jtd: float) -> float:
        """RW x |NDE|, with the optional fair-value cap for cash positions."""
        weighted = self._risk_weight(position) * abs(net_jtd)
        if self._cap_at_fair_value and position.is_cash_position:
            weighted = min(weighted, abs(net_jtd))
        return weighted

    def _compute_bucket_charges(
        self, netted: list[tuple[str, DRCSecNonCTPPosition, float]]
    ) -> list[DRCSecBucketDetail]:
        """Bucket charge per §__.210(c)(3)(iii) (ERBA NPR p.909).

        .. math::

            DRC_b = \\max\\Big( \\sum_{long} RW_i NDE_i
                                - HBR_b \\sum_{short} RW_j |NDE_j|,\\; 0 \\Big)

        with HBR_b computed within the bucket exactly as for
        non-securitization positions.

        Args:
            netted: ``(bucket_label, position, net_jtd)`` tuples.

        Returns:
            Per-bucket details.
        """
        buckets: dict[str, list[tuple[DRCSecNonCTPPosition, float]]] = defaultdict(list)
        for label, pos, v in netted:
            buckets[label].append((pos, v))

        details: list[DRCSecBucketDetail] = []
        for label, items in buckets.items():
            longs = [(p, v) for p, v in items if v > 0]
            shorts = [(p, v) for p, v in items if v < 0]
            rw_long = sum(self._weighted_exposure(p, v) for p, v in longs)
            rw_short = sum(self._weighted_exposure(p, v) for p, v in shorts)
            hbr = compute_hedge_benefit_ratio(
                sum(v for _, v in longs), sum(v for _, v in shorts)
            )
            charge = max(rw_long - hbr * rw_short, 0.0)
            logger.debug(
                "DRC sec non-CTP bucket=%s rw_long=%.4f rw_short=%.4f hbr=%.4f charge=%.4f",
                label, rw_long, rw_short, hbr, charge,
            )
            details.append(
                DRCSecBucketDetail(bucket=label, rw_long=rw_long, rw_short=rw_short,
                                   hbr=hbr, charge=charge)
            )
        return details

    # ------------------------------------------------------------------ #
    #  Validation / empty                                                 #
    # ------------------------------------------------------------------ #

    def _validate_positions(self, positions: list[DRCSecNonCTPPosition]) -> None:
        """Portfolio-level validation: every position must have a resolvable RW."""
        if not positions:
            raise ValidationError("No positions provided for DRC sec non-CTP calculation.")
        for pos in positions:
            self._risk_weight(pos)  # raises ValidationError if unresolvable

    @staticmethod
    def _empty_result() -> DRCSecNonCTPResult:
        """Zero result for an empty portfolio."""
        return DRCSecNonCTPResult(
            total_charge=0.0,
            bucket_charges={},
            bucket_details=[],
            gross_jtd_long=0.0,
            gross_jtd_short=0.0,
            net_jtd_long=0.0,
            net_jtd_short=0.0,
            position_count=0,
        )
