"""DRC Securitization Non-CTP Calculator -- FRTB Default Risk Charge.

Implements the Default Risk Charge (DRC) for securitization non-CTP
exposures per MAR22.24-22.34 of the Basel III Endgame framework (BCBS d457).

DRC Securitization Non-CTP applies to all securitization positions that are
NOT part of the Correlation Trading Portfolio, including RMBS, CMBS, ABS,
CLO tranches, and other structured products.

Key characteristics:
1. LGD = 100% for all securitization positions (no recovery assumption).
2. Risk weights depend on rating AND tranche seniority (senior vs non-senior).
3. NO netting or offsetting between long and short positions.
4. Maturity scaling: positions with residual maturity < 1 year are scaled
   by max(maturity, 3 months) / 1 year.
5. Bucket charge = sum of risk-weighted absolute JTDs (no hedge benefit).
6. Total charge = sum across buckets (no diversification).

Reference: BCBS d457 MAR22.24-22.34, US Federal Reserve Basel III Endgame
Final Rule.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Sequence

from pydantic import BaseModel, Field, field_validator

from src.core.enums import (
    DRCSecBucket,
    DRCSecRating,
    DRCSecSeniority,
)
from src.core.exceptions import CalculationError, ValidationError
from src.market_risk.frtb.drc.drc_params import (
    CTP_HEDGE_BENEFIT_RATIO,
    DRC_SEC_LGD,
    DRC_SEC_RISK_WEIGHTS_NON_SENIOR,
    DRC_SEC_RISK_WEIGHTS_SENIOR,
    compute_maturity_weight,
    get_sec_risk_weight,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Data models
# =========================================================================


class DRCSecNonCTPPosition(BaseModel):
    """A single securitization non-CTP position for DRC calculation.

    Represents a tranche of a securitization that is NOT part of the
    Correlation Trading Portfolio.  Each position carries the tranche
    identity, rating, seniority, and economic terms needed to compute
    the jump-to-default amount.

    Per MAR22.24, this covers RMBS, CMBS, ABS, CLO, and other
    non-CTP securitization exposures.

    Attributes:
        tranche_id: Unique identifier for the securitization tranche.
        deal_name: Name or identifier of the securitization deal/SPV.
        bucket: Underlying asset class bucket classification.
        rating: External credit rating category of the tranche.
        seniority: Whether the tranche is senior or non-senior.
        notional: Face value / tranche notional amount.
        market_value: Current mark-to-market value of the position.
        maturity_years: Remaining maturity in years (must be >= 0).
        is_long: ``True`` for a long credit exposure, ``False`` for short.
    """

    tranche_id: str
    deal_name: str
    bucket: DRCSecBucket
    rating: DRCSecRating
    seniority: DRCSecSeniority
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


class DRCSecNonCTPResult(BaseModel):
    """Result of a DRC securitization non-CTP calculation.

    Contains the aggregate capital charge, per-bucket breakdown, and
    diagnostic JTD statistics useful for risk reporting and reconciliation.

    Attributes:
        total_charge: Aggregate DRC capital charge (sum of all buckets).
        bucket_charges: Capital charge broken down by bucket label.
        gross_jtd_long: Sum of all positive (long) gross JTDs.
        gross_jtd_short: Sum of all negative (short) gross JTDs.
        position_count: Number of positions processed.
    """

    total_charge: float
    bucket_charges: dict[str, float]
    gross_jtd_long: float
    gross_jtd_short: float
    position_count: int


# =========================================================================
#  Calculator
# =========================================================================


class DRCSecNonCTPCalculator:
    """Default Risk Charge calculator for securitization non-CTP exposures.

    Implements the DRC pipeline for securitization non-CTP per MAR22.24-22.34:

    1. **JTD computation** -- Translate each position into a gross
       jump-to-default amount using LGD=100%, tranche notional, and P&L.
    2. **Maturity weighting** -- Scale each JTD by a maturity factor
       (linear in maturity, 1-year cap, 3-month floor).
    3. **No netting** -- Per MAR22.27, no offsetting between long and
       short positions is allowed for non-CTP securitizations.
    4. **Risk weighting** -- Apply risk weights by rating and seniority.
    5. **Bucket aggregation** -- Sum risk-weighted absolute JTDs per bucket.
    6. **Total DRC** -- Simple sum across buckets (no diversification).

    Usage::

        calculator = DRCSecNonCTPCalculator()
        result = calculator.calculate(positions)
        print(result.total_charge)
    """

    # ------------------------------------------------------------------ #
    #  Initialization                                                     #
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        """Initialize the DRC Sec Non-CTP calculator.

        No mutable configuration state is kept; all regulatory parameters
        are sourced from :mod:`drc_params`.
        """
        pass

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(
        self, positions: list[DRCSecNonCTPPosition]
    ) -> DRCSecNonCTPResult:
        """Calculate the DRC securitization non-CTP capital charge.

        This is the main entry point.  Processes all positions through the
        JTD computation, maturity weighting, risk weighting, and bucket
        aggregation pipeline.

        Per MAR22.27, no netting or offsetting is permitted between long
        and short securitization non-CTP positions.

        Args:
            positions: List of :class:`DRCSecNonCTPPosition` objects
                representing the securitization non-CTP portfolio.

        Returns:
            :class:`DRCSecNonCTPResult` containing the total charge,
            per-bucket charges, and JTD statistics.
        """
        if not positions:
            return self._empty_result()

        self._validate_positions(positions)

        # Step 1-2: Compute maturity-weighted JTDs for each position ----
        jtds: list[tuple[DRCSecNonCTPPosition, float]] = []
        for pos in positions:
            raw_jtd = self._compute_jtd(pos)
            scaled_jtd = self._apply_maturity_weight(raw_jtd, pos.maturity_years)
            jtds.append((pos, scaled_jtd))

        # Gross JTD statistics ------------------------------------------
        gross_jtd_long = sum(j for _, j in jtds if j > 0)
        gross_jtd_short = sum(j for _, j in jtds if j < 0)

        # Step 3-5: Bucket-level charges (no netting per MAR22.27) ------
        bucket_charges = self._compute_bucket_charges(jtds)

        # Step 6: Total DRC (simple sum, no diversification) ------------
        total_charge = sum(bucket_charges.values())

        logger.info(
            "DRC sec non-CTP: total_charge=%.2f, buckets=%d, "
            "gross_long=%.2f, gross_short=%.2f, positions=%d",
            total_charge,
            len(bucket_charges),
            gross_jtd_long,
            gross_jtd_short,
            len(positions),
        )

        return DRCSecNonCTPResult(
            total_charge=total_charge,
            bucket_charges=bucket_charges,
            gross_jtd_long=gross_jtd_long,
            gross_jtd_short=gross_jtd_short,
            position_count=len(positions),
        )

    # ------------------------------------------------------------------ #
    #  Step 1: JTD computation -- MAR22.26                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_jtd(position: DRCSecNonCTPPosition) -> float:
        """Compute the raw jump-to-default amount for a securitization position.

        Per MAR22.26, the JTD for securitization positions uses the same
        formula as non-securitization but with LGD = 100%:

        .. math::

            \\mathrm{JTD}_{\\mathrm{long}}
                = \\max(\\mathrm{LGD} \\times \\mathrm{notional}
                        + \\mathrm{P\\&L},\\; 0)

            \\mathrm{JTD}_{\\mathrm{short}}
                = \\min(\\mathrm{LGD} \\times \\mathrm{notional}
                        + \\mathrm{P\\&L},\\; 0)

        where LGD = 100% for all securitization positions.

        Args:
            position: A single :class:`DRCSecNonCTPPosition`.

        Returns:
            Gross JTD amount (positive for longs, negative for shorts).
        """
        lgd = DRC_SEC_LGD  # 100% per MAR22.26
        pnl = position.market_value - position.notional

        raw = lgd * position.notional + pnl

        if position.is_long:
            return max(raw, 0.0)
        else:
            return min(-abs(raw), 0.0) if raw != 0.0 else 0.0

    # ------------------------------------------------------------------ #
    #  Step 2: Maturity weighting -- MAR22.28                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_maturity_weight(jtd: float, maturity_years: float) -> float:
        """Scale a JTD amount by the regulatory maturity weight.

        Per MAR22.28, if the residual maturity is less than 1 year,
        the JTD is scaled by max(maturity, 3 months) / 1 year.
        This reuses the same maturity weight function as non-sec DRC.

        Args:
            jtd: Raw JTD amount (positive or negative).
            maturity_years: Remaining maturity in years.

        Returns:
            Maturity-weighted JTD.
        """
        weight = compute_maturity_weight(maturity_years)
        return jtd * weight

    # ------------------------------------------------------------------ #
    #  Step 3-5: Bucket aggregation (no netting) -- MAR22.27             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_bucket_charges(
        jtds: list[tuple[DRCSecNonCTPPosition, float]],
    ) -> dict[str, float]:
        """Compute the DRC capital charge for each bucket.

        Per MAR22.27, no offsetting between long and short positions is
        permitted for non-CTP securitizations.  The bucket charge is
        simply the sum of risk-weighted absolute JTDs:

        .. math::

            \\mathrm{DRC}_b = \\sum_i \\mathrm{RW}_i \\times |\\mathrm{JTD}_i|

        Args:
            jtds: List of (position, maturity-weighted JTD) tuples.

        Returns:
            Dictionary mapping bucket label to its DRC charge.
        """
        # Group by bucket -----------------------------------------------
        buckets: dict[str, float] = defaultdict(float)

        for pos, jtd in jtds:
            rw = get_sec_risk_weight(pos.rating, pos.seniority)
            weighted = rw * abs(jtd)
            bucket_label = pos.bucket.value
            buckets[bucket_label] += weighted

            logger.debug(
                "DRC sec non-CTP: tranche=%s, bucket=%s, rating=%s, "
                "seniority=%s, jtd=%.2f, rw=%.4f, weighted=%.2f",
                pos.tranche_id,
                bucket_label,
                pos.rating.value,
                pos.seniority.value,
                jtd,
                rw,
                weighted,
            )

        return dict(buckets)

    # ------------------------------------------------------------------ #
    #  Validation                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_positions(positions: list[DRCSecNonCTPPosition]) -> None:
        """Validate the input position list.

        Checks that all positions have valid data.  Pydantic field
        validators handle individual field validation; this method
        performs cross-field and portfolio-level checks.

        Args:
            positions: Input positions.

        Raises:
            ValidationError: If any position fails validation.
        """
        if not positions:
            raise ValidationError(
                "No positions provided for DRC sec non-CTP calculation."
            )

        for idx, pos in enumerate(positions):
            if pos.market_value < 0 and pos.is_long:
                logger.warning(
                    "Position %d (tranche=%s) is long with negative "
                    "market value (%.2f) -- verify data quality.",
                    idx,
                    pos.tranche_id,
                    pos.market_value,
                )

    # ------------------------------------------------------------------ #
    #  Helper: empty result                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _empty_result() -> DRCSecNonCTPResult:
        """Return a zero-charge result for an empty portfolio.

        Returns:
            :class:`DRCSecNonCTPResult` with all fields set to zero / empty.
        """
        return DRCSecNonCTPResult(
            total_charge=0.0,
            bucket_charges={},
            gross_jtd_long=0.0,
            gross_jtd_short=0.0,
            position_count=0,
        )
