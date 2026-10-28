"""Default risk capital requirement, non-securitization -- ERBA NPR §__.210(b) (p.901-907).

Implements the standardized default risk capital requirement for
non-securitization debt and equity positions under the March 2026 US ERBA
NPR (BCBS d457 MAR22.1-22.23 cross-reference).

Pipeline:

1. Exclude US sovereign / specified supranational / MDB positions
   (§__.210(a): not default risk positions).
2. Gross default exposure (§__.210(b)(1)(i)-(ii)):
   long = max(LGD x notional + P&L, 0); short = min(LGD x notional + P&L, 0).
3. Maturity scaling (§__.210(b)(1)(iii)): < 1 year scaled by the fraction
   of a year, floored at 3 months; cash equity options.
4. Net default exposure (§__.210(b)(1)(v)): same obligor offsetting where
   the short's seniority is the same or lower than the long's.
5. Buckets (§__.210(b)(2)): non-US sovereign, PSE & GSE, corporate, defaulted.
6. Bucket charge (§__.210(b)(3)):
   DRC_b = max( sum_long RW x NDE - HBR_b x sum_short RW x |NDE|, 0 ).
7. Total = simple sum across buckets (no diversification).

Monetary inputs are in USD millions ($M) unless stated otherwise.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.enums import (
    DRCCreditQuality,
    DRCExposureType,
    DRCRatingCategory,
    DRCSeniority,
)
from src.core.exceptions import ValidationError
from src.market_risk.frtb.drc.drc_params import (
    DRC_EXCLUDED_EXPOSURE_TYPES,
    UNHEDGED_CASH_EQUITY_MATURITY_DEFAULT,
    UNHEDGED_CASH_EQUITY_MATURITY_OPTIONS,
    compute_hedge_benefit_ratio,
    compute_maturity_weight,
    get_bucket,
    get_bucket_label,
    get_lgd,
    get_risk_weight,
    get_seniority_rank,
    rating_to_credit_quality,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Data models
# =========================================================================


class DRCPosition(BaseModel):
    """A non-securitization default risk position per §__.210(b) (ERBA NPR p.901).

    Attributes:
        issuer: Obligor identifier.  Positions sharing an obligor (or an
            explicit ``offset_group``) are eligible for §__.210(b)(1)(v)
            offsetting.
        seniority: LGD / seniority class (§__.210(b)(1)(iv)).
        exposure_type: Bucket classification (§__.210(b)(2)); US_SOVEREIGN_MDB
            positions are excluded from the charge.
        credit_quality: Credit quality category (Table 1 to §__.210).  May be
            omitted when ``rating`` is supplied; it is then derived via
            ``drc_params.RATING_TO_CREDIT_QUALITY``.
        rating: Optional rating-style convenience input (not used by the NPR
            directly).
        notional: Face value ($M, positive; direction given by ``is_long``).
        market_value: Current market value ($M, same sign convention).
        maturity_years: Remaining maturity in years (>= 0).
        is_long: True for a long credit exposure, False for short.
        is_us_sovereign_or_mdb: Flag marking US sovereign / supranational /
            MDB exposure; excluded per §__.210(a).
        is_cash_equity: Cash equity position (maturity option applies).
        hedged_derivative_maturity_years: For cash equity hedging a
            derivative, the derivative's maturity may be used
            (§__.210(b)(1)(iii)).
        offset_group: Optional obligor-override key.  GSEs are separate
            obligors, but UMBS issued by different GSEs may fully offset:
            give those positions the same ``offset_group``.
    """

    issuer: str
    seniority: DRCSeniority
    exposure_type: DRCExposureType = DRCExposureType.CORPORATE
    credit_quality: DRCCreditQuality | None = None
    rating: DRCRatingCategory | None = None
    notional: float
    market_value: float
    maturity_years: float
    is_long: bool
    is_us_sovereign_or_mdb: bool = False
    is_cash_equity: bool = False
    hedged_derivative_maturity_years: float | None = Field(default=None, ge=0.0)
    offset_group: str | None = None

    @field_validator("notional")
    @classmethod
    def _notional_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("notional must be positive")
        return v

    @field_validator("maturity_years")
    @classmethod
    def _maturity_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("maturity_years must be non-negative")
        return v

    @field_validator("exposure_type")
    @classmethod
    def _no_securitization(cls, v: DRCExposureType) -> DRCExposureType:
        if v == DRCExposureType.SECURITIZATION:
            raise ValueError(
                "Securitization exposures must use the DRC-Sec calculators, "
                "not the non-securitization DRC."
            )
        return v

    @model_validator(mode="after")
    def _resolve_credit_quality(self) -> DRCPosition:
        if self.credit_quality is None:
            if self.rating is None:
                raise ValueError(
                    "Either credit_quality (ERBA NPR Table 1 to §__.210) or the "
                    "rating convenience input must be supplied."
                )
            self.credit_quality = rating_to_credit_quality(self.rating)
        if self.exposure_type == DRCExposureType.DEFAULTED:
            self.credit_quality = DRCCreditQuality.DEFAULTED
        return self

    @property
    def is_excluded(self) -> bool:
        """True when the position is not a default risk position (§__.210(a))."""
        return (
            self.is_us_sovereign_or_mdb
            or self.exposure_type in DRC_EXCLUDED_EXPOSURE_TYPES
        )

    @property
    def obligor_key(self) -> str:
        """Obligor identity used for offsetting (``offset_group`` overrides issuer)."""
        return self.offset_group if self.offset_group is not None else self.issuer


class DRCBucketDetail(BaseModel):
    """Per-bucket diagnostics for §__.210(b)(3).

    Attributes:
        bucket: Bucket label.
        rw_long: sum_long RW x NDE.
        rw_short: sum_short RW x |NDE|.
        hbr: Hedge benefit ratio for the bucket.
        charge: max(rw_long - hbr x rw_short, 0).
    """

    bucket: str
    rw_long: float
    rw_short: float
    hbr: float
    charge: float


class DRCResult(BaseModel):
    """Result of the non-securitization default risk capital requirement.

    Attributes:
        total_charge: Sum of bucket charges ($M).
        bucket_charges: Charge by bucket label.
        bucket_details: Per-bucket HBR and risk-weighted long / short sums.
        gross_jtd_long: Sum of positive gross default exposures (maturity scaled).
        gross_jtd_short: Sum of negative gross default exposures (maturity scaled).
        net_jtd_long: Sum of positive net default exposures.
        net_jtd_short: Sum of negative net default exposures.
        excluded_positions: Count of US sovereign / MDB positions excluded.
    """

    total_charge: float
    bucket_charges: dict[str, float]
    bucket_details: list[DRCBucketDetail] = []
    gross_jtd_long: float
    gross_jtd_short: float
    net_jtd_long: float
    net_jtd_short: float
    excluded_positions: int = 0


# =========================================================================
#  Internal intermediate types
# =========================================================================


class _NetDefaultExposure(BaseModel):
    """A net default exposure after same-obligor offsetting.

    Carries the attributes needed for the Table 1 risk-weight lookup and
    bucket assignment.
    """

    obligor: str
    seniority: DRCSeniority
    exposure_type: DRCExposureType
    credit_quality: DRCCreditQuality
    net_jtd: float  # positive = net long, negative = net short

    @property
    def bucket(self) -> DRCExposureType:
        """§__.210(b)(2) bucket (defaulted positions -> DEFAULTED)."""
        return get_bucket(self.exposure_type, self.credit_quality)

    @property
    def risk_weight(self) -> float:
        """Table 1 to §__.210 risk weight."""
        return get_risk_weight(self.credit_quality, self.bucket)


# =========================================================================
#  Calculator
# =========================================================================


class DRCCalculator:
    """Non-securitization default risk capital calculator per §__.210(b).

    Args:
        unhedged_cash_equity_maturity_years: Maturity assigned to unhedged
            cash equity positions; §__.210(b)(1)(iii) permits 3 months
            (0.25) or 1 year (1.0).  Default 1 year.

    Usage::

        calculator = DRCCalculator()
        result = calculator.calculate(positions)
        print(result.total_charge)
    """

    def __init__(
        self,
        unhedged_cash_equity_maturity_years: float = UNHEDGED_CASH_EQUITY_MATURITY_DEFAULT,
    ) -> None:
        """Initialise the calculator and validate the cash equity option."""
        if unhedged_cash_equity_maturity_years not in UNHEDGED_CASH_EQUITY_MATURITY_OPTIONS:
            raise ValidationError(
                "unhedged_cash_equity_maturity_years must be one of "
                f"{UNHEDGED_CASH_EQUITY_MATURITY_OPTIONS} per §__.210(b)(1)(iii); "
                f"got {unhedged_cash_equity_maturity_years}"
            )
        self._cash_equity_maturity = unhedged_cash_equity_maturity_years
        self._positions: list[DRCPosition] = []

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(self, positions: Sequence[Any]) -> DRCResult:
        """Calculate the non-securitization default risk capital requirement.

        Args:
            positions: :class:`DRCPosition` objects (or duck-typed models
                such as ``src.core.models.DRCPosition``; they are coerced).

        Returns:
            :class:`DRCResult` with total, per-bucket charges and diagnostics.

        Raises:
            ValidationError: If the position list contains invalid data.
        """
        if not positions:
            return self._empty_result()

        coerced = self._coerce_positions(positions)
        self._validate_positions(coerced)

        included = [p for p in coerced if not p.is_excluded]
        excluded_count = len(coerced) - len(included)
        self._positions = included

        if not included:
            result = self._empty_result()
            result.excluded_positions = excluded_count
            return result

        # Steps 2-3: gross default exposure with maturity scaling ---------
        gross = [self._maturity_scaled_jtd(p) for p in included]
        gross_long = sum(j for j in gross if j > 0)
        gross_short = sum(j for j in gross if j < 0)

        # Step 4: same-obligor offsetting ---------------------------------
        netted = self._net_same_obligor(included, gross)
        net_long = sum(n.net_jtd for n in netted if n.net_jtd > 0)
        net_short = sum(n.net_jtd for n in netted if n.net_jtd < 0)

        # Steps 5-6: bucket charges ---------------------------------------
        details = self._compute_bucket_charges(netted)
        bucket_charges = {d.bucket: d.charge for d in details}

        # Step 7: total -----------------------------------------------------
        total = sum(bucket_charges.values())

        logger.info(
            "DRC non-sec: total=%.4f buckets=%d gross_long=%.4f gross_short=%.4f "
            "net_long=%.4f net_short=%.4f excluded=%d",
            total, len(bucket_charges), gross_long, gross_short,
            net_long, net_short, excluded_count,
        )

        return DRCResult(
            total_charge=total,
            bucket_charges=bucket_charges,
            bucket_details=details,
            gross_jtd_long=gross_long,
            gross_jtd_short=gross_short,
            net_jtd_long=net_long,
            net_jtd_short=net_short,
            excluded_positions=excluded_count,
        )

    # ------------------------------------------------------------------ #
    #  Gross default exposure -- §__.210(b)(1)(i)-(iii)                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_gross_jtd(position: DRCPosition) -> float:
        """Compute the gross default exposure per §__.210(b)(1)(i)-(ii) (p.902).

        .. math::

            GDE_{long} = \\max(LGD \\times notional + P\\&L, 0), \\quad
            GDE_{short} = \\min(LGD \\times notional + P\\&L, 0)

        with ``P&L = market_value - notional`` on the signed position.  For a
        short the signed notional and market value are negative, so the
        amount is the negative of the long-side expression.  Credit
        derivatives use the LGD of the reference exposure (the position's
        ``seniority`` must be that of the reference obligation).

        Args:
            position: Non-securitization position.

        Returns:
            Gross default exposure (positive long, negative short), unscaled.
        """
        lgd = get_lgd(position.seniority, position.credit_quality)
        pnl = position.market_value - position.notional
        raw = lgd * position.notional + pnl
        if position.is_long:
            return max(raw, 0.0)
        return min(-raw, 0.0)

    def effective_maturity(self, position: DRCPosition) -> float:
        """Return the maturity used for scaling per §__.210(b)(1)(iii) (p.903).

        - Cash equity hedging a derivative may take the derivative's maturity.
        - Unhedged cash equity takes the calculator option (3 months or 1 year).
        - Otherwise the instrument's own remaining maturity.

        Args:
            position: Non-securitization position.

        Returns:
            Maturity in years.
        """
        if position.is_cash_equity:
            if position.hedged_derivative_maturity_years is not None:
                return position.hedged_derivative_maturity_years
            return self._cash_equity_maturity
        return position.maturity_years

    def _maturity_scaled_jtd(self, position: DRCPosition) -> float:
        """Gross default exposure after §__.210(b)(1)(iii) maturity scaling."""
        weight = compute_maturity_weight(self.effective_maturity(position))
        return self.compute_gross_jtd(position) * weight

    # ------------------------------------------------------------------ #
    #  Net default exposure -- §__.210(b)(1)(v)                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _net_same_obligor(
        positions: list[DRCPosition], gross: list[float]
    ) -> list[_NetDefaultExposure]:
        """Offset long and short gross default exposures of the same obligor.

        §__.210(b)(1)(v) (ERBA NPR p.904): a short position may offset a
        long position in the same obligor only if the short has the same or
        lower seniority than the long (a short in subordinated debt may
        offset a long in senior debt; a short in senior debt may NOT offset
        a long in subordinated debt).  Different obligors never offset here
        (the HBR provides the partial cross-obligor benefit).  GSEs are
        separate obligors unless the caller sets a shared ``offset_group``
        (UMBS).

        Algorithm per obligor: aggregate exposures by (seniority,
        exposure_type, credit_quality); process shorts from most to least
        senior, each consuming eligible longs (rank >= short rank) from most
        senior downward.  Residuals are returned as net default exposures.

        Args:
            positions: Included positions.
            gross: Maturity-scaled gross default exposures, aligned.

        Returns:
            Net default exposures (positive or negative), one per residual
            (obligor, seniority, exposure_type, credit_quality) cell.
        """
        by_obligor: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        for pos, jtd in zip(positions, gross, strict=True):
            if jtd == 0.0:
                continue
            cell = (pos.seniority, pos.exposure_type, pos.credit_quality)
            by_obligor[pos.obligor_key][cell] += jtd

        result: list[_NetDefaultExposure] = []
        for obligor, cells in by_obligor.items():
            longs = {c: v for c, v in cells.items() if v > 0}
            shorts = {c: v for c, v in cells.items() if v < 0}

            short_order = sorted(shorts, key=lambda c: get_seniority_rank(c[0]), reverse=True)
            for s_cell in short_order:
                remaining_short = -shorts[s_cell]  # positive magnitude
                s_rank = get_seniority_rank(s_cell[0])
                eligible = sorted(
                    (c for c in longs if longs[c] > 0 and get_seniority_rank(c[0]) >= s_rank),
                    key=lambda c: get_seniority_rank(c[0]),
                    reverse=True,
                )
                for l_cell in eligible:
                    if remaining_short <= 0.0:
                        break
                    used = min(longs[l_cell], remaining_short)
                    longs[l_cell] -= used
                    remaining_short -= used
                shorts[s_cell] = -remaining_short

            for cell, v in list(longs.items()) + list(shorts.items()):
                if abs(v) > 0.0:
                    result.append(
                        _NetDefaultExposure(
                            obligor=obligor,
                            seniority=cell[0],
                            exposure_type=cell[1],
                            credit_quality=cell[2],
                            net_jtd=v,
                        )
                    )
        return result

    # ------------------------------------------------------------------ #
    #  Bucket charges -- §__.210(b)(2)-(3)                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_bucket_charges(
        netted: list[_NetDefaultExposure],
    ) -> list[DRCBucketDetail]:
        """Compute the bucket-level default risk capital per §__.210(b)(3) (p.906).

        .. math::

            HBR_b = \\frac{\\sum NDE_{long}}{\\sum NDE_{long} + \\sum |NDE_{short}|}

            DRC_b = \\max\\Big( \\sum_{long} RW_i NDE_i
                                - HBR_b \\sum_{short} RW_j |NDE_j|,\\; 0 \\Big)

        Args:
            netted: Net default exposures.

        Returns:
            Per-bucket details including HBR and the floored charge.
        """
        buckets: dict[str, list[_NetDefaultExposure]] = defaultdict(list)
        for n in netted:
            buckets[get_bucket_label(n.exposure_type, n.credit_quality)].append(n)

        details: list[DRCBucketDetail] = []
        for label, items in buckets.items():
            longs = [n for n in items if n.net_jtd > 0]
            shorts = [n for n in items if n.net_jtd < 0]
            rw_long = sum(n.risk_weight * n.net_jtd for n in longs)
            rw_short = sum(n.risk_weight * abs(n.net_jtd) for n in shorts)
            hbr = compute_hedge_benefit_ratio(
                sum(n.net_jtd for n in longs), sum(n.net_jtd for n in shorts)
            )
            charge = max(rw_long - hbr * rw_short, 0.0)
            logger.debug(
                "DRC bucket=%s rw_long=%.4f rw_short=%.4f hbr=%.4f charge=%.4f",
                label, rw_long, rw_short, hbr, charge,
            )
            details.append(
                DRCBucketDetail(bucket=label, rw_long=rw_long, rw_short=rw_short,
                                hbr=hbr, charge=charge)
            )
        return details

    # ------------------------------------------------------------------ #
    #  Validation / coercion                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _coerce_positions(positions: Sequence[Any]) -> list[DRCPosition]:
        """Coerce duck-typed position models into :class:`DRCPosition`.

        Accepts :class:`DRCPosition` instances directly and any pydantic
        model exposing the same field names (e.g. the lightweight
        ``src.core.models.DRCPosition``).
        """
        out: list[DRCPosition] = []
        for idx, p in enumerate(positions):
            if isinstance(p, DRCPosition):
                out.append(p)
                continue
            try:
                data = p.model_dump() if hasattr(p, "model_dump") else dict(p)
                out.append(DRCPosition.model_validate(data))
            except Exception as exc:  # noqa: BLE001
                raise ValidationError(
                    f"Position {idx} could not be interpreted as a DRCPosition: {exc}"
                ) from exc
        return out

    @staticmethod
    def _validate_positions(positions: list[DRCPosition]) -> None:
        """Portfolio-level validation (securitization routed elsewhere)."""
        if not positions:
            raise ValidationError("No positions provided for DRC non-sec calculation.")
        for idx, pos in enumerate(positions):
            if pos.exposure_type == DRCExposureType.SECURITIZATION:
                raise ValidationError(
                    f"Position {idx} (issuer={pos.issuer!r}) has exposure_type "
                    "SECURITIZATION.  Use the DRC-Sec calculators instead."
                )

    @staticmethod
    def _empty_result() -> DRCResult:
        """Zero result for an empty (or fully excluded) portfolio."""
        return DRCResult(
            total_charge=0.0,
            bucket_charges={},
            bucket_details=[],
            gross_jtd_long=0.0,
            gross_jtd_short=0.0,
            net_jtd_long=0.0,
            net_jtd_short=0.0,
            excluded_positions=0,
        )
