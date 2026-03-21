"""DRC Non-Securitization Calculator -- FRTB Default Risk Charge.

Implements the Default Risk Charge (DRC) for non-securitization exposures
per MAR22 of the Basel III Endgame framework (BCBS d457).

DRC captures jump-to-default (JTD) risk at a 99.9% confidence level over
a 1-year capital horizon.  It applies to all instruments subject to
issuer default risk, including bonds, loans, CDS, and equity.

Key steps:

1. Compute gross JTD for each position (long and short).
2. Apply maturity weighting (1-year cap, 3-month floor).
3. Net same-obligor / same-seniority JTDs.
4. Compute Hedge Benefit Ratio (HBR) per bucket.
5. Apply risk weights by rating to produce the bucket-level DRC.
6. Aggregate across buckets (simple sum -- no diversification).

Reference: BCBS d457 MAR22, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Sequence

from pydantic import BaseModel, Field, field_validator

from src.core.enums import (
    DRCExposureType,
    DRCRatingCategory,
    DRCSeniority,
)
from src.core.exceptions import CalculationError, ValidationError
from src.market_risk.frtb.drc.drc_params import (
    DRC_RISK_WEIGHTS,
    LGD_VALUES,
    compute_maturity_weight,
    get_bucket_label,
    get_lgd,
    get_risk_weight,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Data models
# =========================================================================


class DRCPosition(BaseModel):
    """A single position for the DRC non-securitization calculation.

    Represents an instrument subject to issuer default risk.  Each position
    carries the obligor identity, capital-structure seniority, credit rating,
    and economic terms (notional, market value, maturity, direction) needed
    to compute the jump-to-default amount.

    Attributes:
        issuer: Name or identifier of the obligor / issuer.
        seniority: Seniority of the instrument in the capital structure.
        rating: External credit rating category.
        exposure_type: Sector bucket classification (Corporate, Sovereign, etc.).
        notional: Face value / par amount of the position.
        market_value: Current mark-to-market value of the position.
        maturity_years: Remaining maturity in years (must be >= 0).
        is_long: ``True`` for a long credit exposure, ``False`` for short.
    """

    issuer: str
    seniority: DRCSeniority
    rating: DRCRatingCategory
    exposure_type: DRCExposureType
    notional: float
    market_value: float
    maturity_years: float
    is_long: bool

    # ------------------------------------------------------------------ #
    #  Validators                                                         #
    # ------------------------------------------------------------------ #

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
                "Securitization exposures must use the DRC-Sec calculator, "
                "not the non-securitization DRC."
            )
        return v


class DRCResult(BaseModel):
    """Result of a DRC non-securitization calculation.

    Contains the aggregate capital charge, per-bucket breakdown, and
    diagnostic JTD statistics useful for risk reporting and reconciliation.

    Attributes:
        total_charge: Aggregate DRC capital charge (sum of all buckets).
        bucket_charges: Capital charge broken down by bucket label.
        gross_jtd_long: Sum of all positive (long) gross JTDs before netting.
        gross_jtd_short: Sum of all negative (short) gross JTDs before netting.
        net_jtd_long: Sum of positive net JTDs after same-obligor netting.
        net_jtd_short: Sum of negative net JTDs after same-obligor netting.
    """

    total_charge: float
    bucket_charges: dict[str, float]
    gross_jtd_long: float
    gross_jtd_short: float
    net_jtd_long: float
    net_jtd_short: float


# =========================================================================
#  Internal intermediate types
# =========================================================================


class _NettingKey(BaseModel):
    """Composite key for same-obligor / same-seniority netting.

    JTDs are netted across long and short positions that share the
    same issuer **and** the same seniority per MAR22.15.  The exposure
    type and rating are carried through for downstream risk-weight lookup.
    """

    issuer: str
    seniority: DRCSeniority
    exposure_type: DRCExposureType
    rating: DRCRatingCategory

    model_config = {"frozen": True}

    def __hash__(self) -> int:  # noqa: D105
        return hash(
            (self.issuer, self.seniority, self.exposure_type, self.rating)
        )

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, _NettingKey):
            return NotImplemented
        return (
            self.issuer == other.issuer
            and self.seniority == other.seniority
            and self.exposure_type == other.exposure_type
            and self.rating == other.rating
        )


class _NettedJTD(BaseModel):
    """Result of netting JTDs for a single obligor/seniority group.

    After same-obligor netting, each group collapses to a single net JTD
    that is either long (positive) or short (negative).
    """

    issuer: str
    seniority: DRCSeniority
    exposure_type: DRCExposureType
    rating: DRCRatingCategory
    net_jtd: float  # positive = net long, negative = net short


# =========================================================================
#  Calculator
# =========================================================================


class DRCCalculator:
    """Default Risk Charge calculator for non-securitization exposures.

    Implements the full DRC pipeline per MAR22:

    1. **JTD computation** -- Translate each position into a gross
       jump-to-default amount using LGD, notional, and cumulative P&L.
    2. **Maturity weighting** -- Scale each JTD by a maturity factor
       (linear in maturity, 1-year cap, 3-month floor).
    3. **Same-obligor netting** -- Net long and short JTDs that share
       the same issuer and seniority.
    4. **Bucket aggregation** -- Group net JTDs by exposure type
       (Corporate, Sovereign, Local Government).
    5. **Hedge Benefit Ratio (HBR)** -- Compute the per-bucket ratio
       that limits the offset of shorts against longs.
    6. **Risk-weighted DRC** -- Apply risk weights by rating and
       compute the final charge per bucket.
    7. **Total DRC** -- Simple sum across buckets (no diversification).

    Usage::

        calculator = DRCCalculator()
        result = calculator.calculate(positions)
        print(result.total_charge)
    """

    # ------------------------------------------------------------------ #
    #  Initialization                                                     #
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        """Initialize the DRC calculator.

        No mutable configuration state is kept; all regulatory parameters
        are sourced from :mod:`drc_params`.
        """
        self._positions: list[DRCPosition] = []

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(self, positions: list[DRCPosition]) -> DRCResult:
        """Calculate the DRC non-securitization capital charge.

        This is the main entry point.  Caches the positions internally
        so that the netting step can look up position attributes by
        index.

        Args:
            positions: List of :class:`DRCPosition` objects representing
                the portfolio of instruments subject to default risk.

        Returns:
            :class:`DRCResult` containing the total charge, per-bucket
            charges, and gross/net JTD statistics.

        Raises:
            ValidationError: If the position list contains invalid data.
        """
        if not positions:
            return self._empty_result()

        self._validate_positions(positions)

        # Cache positions for use in netting step -------------------------
        self._positions = positions

        # Step 1-2: Compute gross JTDs with maturity weighting ------------
        gross_jtds = self._compute_all_jtds(positions)

        # Gross JTD statistics --------------------------------------------
        gross_jtd_long = sum(j for j in gross_jtds.values() if j > 0)
        gross_jtd_short = sum(j for j in gross_jtds.values() if j < 0)

        # Step 3: Same-obligor netting ------------------------------------
        netted = self._net_same_obligor(gross_jtds)

        # Net JTD statistics ----------------------------------------------
        net_jtd_long = sum(n.net_jtd for n in netted if n.net_jtd > 0)
        net_jtd_short = sum(n.net_jtd for n in netted if n.net_jtd < 0)

        # Step 4-6: Bucket-level charges ----------------------------------
        bucket_charges = self._compute_bucket_charges(netted)

        # Step 7: Total DRC (simple sum, no diversification) --------------
        total_charge = sum(bucket_charges.values())

        logger.info(
            "DRC non-sec: total_charge=%.2f, buckets=%d, "
            "gross_long=%.2f, gross_short=%.2f, "
            "net_long=%.2f, net_short=%.2f",
            total_charge,
            len(bucket_charges),
            gross_jtd_long,
            gross_jtd_short,
            net_jtd_long,
            net_jtd_short,
        )

        return DRCResult(
            total_charge=total_charge,
            bucket_charges=bucket_charges,
            gross_jtd_long=gross_jtd_long,
            gross_jtd_short=gross_jtd_short,
            net_jtd_long=net_jtd_long,
            net_jtd_short=net_jtd_short,
        )

    # ------------------------------------------------------------------ #
    #  Step 1-2: JTD computation & maturity weighting                    #
    # ------------------------------------------------------------------ #

    def _compute_all_jtds(
        self, positions: list[DRCPosition]
    ) -> dict[int, float]:
        """Compute maturity-weighted gross JTD for every position.

        Iterates over all positions, computes the raw JTD via
        :meth:`_compute_jtd`, then scales by the maturity weight.

        Args:
            positions: Input position list.

        Returns:
            Dictionary mapping position index to its gross JTD (scaled
            by maturity weight).
        """
        result: dict[int, float] = {}
        for idx, pos in enumerate(positions):
            raw_jtd = self._compute_jtd(pos)
            scaled = self._apply_maturity_weight(raw_jtd, pos.maturity_years)
            result[idx] = scaled
        return result

    @staticmethod
    def _compute_jtd(position: DRCPosition) -> float:
        """Compute the raw jump-to-default amount for a single position.

        Per MAR22.11-22.12:

        .. math::

            \\mathrm{JTD}_{\\mathrm{long}}
                = \\max(\\mathrm{LGD} \\times \\mathrm{notional}
                        + \\mathrm{P\\&L},\\; 0)

            \\mathrm{JTD}_{\\mathrm{short}}
                = \\min(\\mathrm{LGD} \\times \\mathrm{notional}
                        + \\mathrm{P\\&L},\\; 0)

        where ``P&L = market_value - notional`` is the cumulative
        profit-or-loss on the position.

        For **long** positions the JTD is floored at zero (you cannot
        gain from your own default).  For **short** positions the JTD
        is capped at zero (the loss in case of default is a gain for
        the short).

        Args:
            position: A single :class:`DRCPosition`.

        Returns:
            Gross JTD amount (positive for longs, negative for shorts).
        """
        lgd = get_lgd(position.seniority)
        pnl = position.market_value - position.notional

        raw = lgd * position.notional + pnl

        if position.is_long:
            # Long: exposure to default -- JTD is the loss upon default
            return max(raw, 0.0)
        else:
            # Short: benefit from default -- JTD is negative
            return min(-abs(raw), 0.0) if raw != 0.0 else 0.0

    @staticmethod
    def _apply_maturity_weight(jtd: float, maturity_years: float) -> float:
        """Scale a JTD amount by the regulatory maturity weight.

        Per MAR22.13 the maturity weight is:

        .. math::

            w = \\min\\!\\left(\\frac{M}{1},\\; 1\\right)

        with a floor of 0.25 for maturities shorter than 3 months.

        Args:
            jtd: Raw JTD amount (positive or negative).
            maturity_years: Remaining maturity in years.

        Returns:
            Maturity-weighted JTD.
        """
        weight = compute_maturity_weight(maturity_years)
        return jtd * weight

    # ------------------------------------------------------------------ #
    #  Step 3: Same-obligor netting -- MAR22.15                          #
    # ------------------------------------------------------------------ #

    def _net_same_obligor(
        self, gross_jtds: dict[int, float]
    ) -> list[_NettedJTD]:
        """Net JTDs across positions with the same issuer and seniority.

        Per MAR22.15, long and short JTDs for the same obligor **and**
        same seniority can be fully offset against each other.  Positions
        with different seniority levels are not netted here; the HBR
        mechanism in the bucket aggregation step provides partial offset.

        This method groups positions by ``(issuer, seniority, exposure_type,
        rating)`` and sums JTDs within each group to produce a single net
        JTD per group.

        Args:
            gross_jtds: Mapping of position index to gross JTD.

        Returns:
            List of :class:`_NettedJTD` objects, one per netting group.
        """
        netting_groups: dict[_NettingKey, float] = defaultdict(float)

        for idx, jtd in gross_jtds.items():
            pos = self._positions[idx]
            key = _NettingKey(
                issuer=pos.issuer,
                seniority=pos.seniority,
                exposure_type=pos.exposure_type,
                rating=pos.rating,
            )
            netting_groups[key] += jtd

        result: list[_NettedJTD] = []
        for key, net_jtd in netting_groups.items():
            result.append(
                _NettedJTD(
                    issuer=key.issuer,
                    seniority=key.seniority,
                    exposure_type=key.exposure_type,
                    rating=key.rating,
                    net_jtd=net_jtd,
                )
            )

        return result

    # ------------------------------------------------------------------ #
    #  Step 4-6: Bucket aggregation, HBR, risk-weighted DRC              #
    # ------------------------------------------------------------------ #

    def _compute_bucket_charges(
        self, netted: list[_NettedJTD]
    ) -> dict[str, float]:
        """Compute the DRC capital charge for each bucket.

        Steps per MAR22.16-22.17:

        1. Group net JTDs by bucket (exposure type).
        2. Separate net longs and net shorts within each bucket.
        3. Compute the Hedge Benefit Ratio (HBR).
        4. Apply risk weights and compute the bucket charge:

        .. math::

            \\mathrm{DRC}_b = \\max\\!\\Bigl(
                \\sum_i \\mathrm{RW}_i \\times \\mathrm{netJTD}^{+}_i
                \\;-\\; \\mathrm{HBR}_b \\times
                \\sum_j \\mathrm{RW}_j \\times |\\mathrm{netJTD}^{-}_j|
            ,\\;0\\Bigr)

        Args:
            netted: List of netted JTDs from step 3.

        Returns:
            Dictionary mapping bucket label to its DRC charge.
        """
        # Group by bucket (exposure type) ---------------------------------
        buckets: dict[str, list[_NettedJTD]] = defaultdict(list)
        for n in netted:
            label = get_bucket_label(n.exposure_type)
            buckets[label].append(n)

        charges: dict[str, float] = {}

        for bucket_label, bucket_positions in buckets.items():
            # Separate longs and shorts -----------------------------------
            longs = [n for n in bucket_positions if n.net_jtd > 0]
            shorts = [n for n in bucket_positions if n.net_jtd < 0]

            # Risk-weighted long charge -----------------------------------
            rw_long = sum(
                get_risk_weight(n.rating, n.exposure_type) * n.net_jtd
                for n in longs
            )

            # Risk-weighted short charge (absolute values) ----------------
            rw_short = sum(
                get_risk_weight(n.rating, n.exposure_type) * abs(n.net_jtd)
                for n in shorts
            )

            # Sum of long and short JTDs in this bucket -------------------
            sum_long_jtd = sum(n.net_jtd for n in longs)
            sum_short_jtd = sum(n.net_jtd for n in shorts)  # negative

            # HBR per MAR22.17 -------------------------------------------
            hbr = self._compute_hbr(sum_long_jtd, sum_short_jtd)

            # Bucket charge per MAR22.16 ----------------------------------
            bucket_charge = max(rw_long - hbr * rw_short, 0.0)

            logger.debug(
                "DRC bucket=%s: rw_long=%.2f, rw_short=%.2f, "
                "hbr=%.4f, charge=%.2f",
                bucket_label,
                rw_long,
                rw_short,
                hbr,
                bucket_charge,
            )

            charges[bucket_label] = bucket_charge

        return charges

    @staticmethod
    def _compute_hbr(sum_long_jtd: float, sum_short_jtd: float) -> float:
        """Compute the Hedge Benefit Ratio (HBR) for a single bucket.

        Per MAR22.17:

        .. math::

            \\mathrm{HBR}_b = \\frac{
                \\max(\\sum \\mathrm{JTD}^{+} + \\sum \\mathrm{JTD}^{-},\\; 0)
            }{
                \\sum \\mathrm{JTD}^{+}
            }

        where ``JTD+`` are net-long JTDs and ``JTD-`` are net-short JTDs
        (negative values).

        The ratio is bounded in [0, 1]:

        - HBR = 1 when there are no shorts (full long exposure).
        - HBR approaches 0 as shorts grow relative to longs.

        Args:
            sum_long_jtd: Sum of positive (net long) JTDs in the bucket.
            sum_short_jtd: Sum of negative (net short) JTDs in the bucket.

        Returns:
            HBR as a decimal in [0, 1].
        """
        if sum_long_jtd <= 0.0:
            # No long exposure -- no charge possible
            return 0.0

        numerator = max(sum_long_jtd + sum_short_jtd, 0.0)
        return numerator / sum_long_jtd

    # ------------------------------------------------------------------ #
    #  Validation                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_positions(positions: list[DRCPosition]) -> None:
        """Validate the input position list.

        Checks:

        - The list is non-empty.
        - No securitization exposures (those are handled by DRC-Sec).

        Args:
            positions: Input positions.

        Raises:
            ValidationError: If any position fails validation.
        """
        if not positions:
            raise ValidationError(
                "No positions provided for DRC non-sec calculation."
            )

        for idx, pos in enumerate(positions):
            if pos.exposure_type == DRCExposureType.SECURITIZATION:
                raise ValidationError(
                    f"Position {idx} (issuer={pos.issuer!r}) has exposure_type "
                    f"SECURITIZATION.  Use the DRC-Sec calculator instead."
                )

    # ------------------------------------------------------------------ #
    #  Helper: empty result                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _empty_result() -> DRCResult:
        """Return a zero-charge result for an empty portfolio.

        Returns:
            :class:`DRCResult` with all fields set to zero / empty.
        """
        return DRCResult(
            total_charge=0.0,
            bucket_charges={},
            gross_jtd_long=0.0,
            gross_jtd_short=0.0,
            net_jtd_long=0.0,
            net_jtd_short=0.0,
        )
