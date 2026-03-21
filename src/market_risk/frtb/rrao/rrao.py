"""Residual Risk Add-On (RRAO) Calculator -- FRTB MAR23.

Implements the Residual Risk Add-On charge per MAR23 of the Basel III
Endgame framework (BCBS d457).

RRAO is a simple notional-based capital add-on for instruments bearing
residual risks that are not adequately captured by the Sensitivities-Based
Method (SBM) or the Default Risk Charge (DRC).  Two categories of residual
risk are recognised, each carrying a distinct risk weight applied to the
gross notional of the instrument:

- **Exotic underlyings** (1.0%): Longevity risk, weather derivatives,
  natural disasters, correlation trading positions not in the CTP.
- **Other residual risks** (0.1%): Gap risk, correlation risk from
  non-CTP positions, behavioural risk (e.g. prepayment).

Certain instruments are **exempt** from RRAO:

- Listed / exchange-traded vanilla options.
- Callable or puttable bonds where the only exotic feature is the
  call/put provision.
- Securitization tranches already captured by the CSR-Sec framework.
- Plain-vanilla structured products without exotic payoff features.

Reference: BCBS d457 MAR23, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import logging
from typing import Sequence

from pydantic import BaseModel, Field, field_validator

from src.core.enums import RRAOCategory
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# =========================================================================
#  Data models
# =========================================================================


class RRAOPosition(BaseModel):
    """A single instrument position for the RRAO calculation.

    Each position carries a gross notional and a category that determines
    whether an RRAO charge applies and at what risk weight.

    Attributes:
        instrument_id: Unique identifier for the instrument.
        notional: Gross notional amount of the instrument.  Must be
            non-negative.
        category: RRAO classification -- ``EXOTIC``, ``OTHER``, or
            ``EXEMPT``.
        description: Optional free-text description of the instrument
            or the nature of its residual risk.
    """

    instrument_id: str
    notional: float
    category: RRAOCategory
    description: str = ""

    @field_validator("notional")
    @classmethod
    def _notional_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("notional must be non-negative")
        return v


class RRAOResult(BaseModel):
    """Result of an RRAO calculation.

    Provides the total RRAO charge as well as the contribution from each
    category, plus the notional of exempt instruments for reporting.

    Attributes:
        total_charge: Total RRAO capital charge (exotic + other).
        exotic_charge: Charge from instruments with exotic underlyings.
        other_charge: Charge from instruments with other residual risks.
        exempt_notional: Aggregate notional of exempt instruments (for
            reporting / audit purposes only -- not charged).
    """

    total_charge: float
    exotic_charge: float
    other_charge: float
    exempt_notional: float


# =========================================================================
#  Calculator
# =========================================================================


class RRAOCalculator:
    """Residual Risk Add-On calculator per MAR23.

    Applies a simple notional-based risk weight to instruments with
    residual risks not captured by SBM or DRC.

    Risk weights per MAR23.4:

    - Exotic underlyings: 1.0% of gross notional.
    - Other residual risks: 0.1% of gross notional.
    - Exempt instruments: no charge.

    Usage::

        calculator = RRAOCalculator()
        result = calculator.calculate(positions)
        print(result.total_charge)
    """

    # Regulatory risk weights per MAR23.4 ---------------------------------
    EXOTIC_RW: float = 0.01    # 1.0%
    OTHER_RW: float = 0.001    # 0.1%

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(self, positions: list[RRAOPosition]) -> RRAOResult:
        """Calculate the RRAO capital charge.

        Iterates over all positions, applies the appropriate risk weight
        based on the RRAO category, and sums the charges.

        Args:
            positions: List of :class:`RRAOPosition` objects.

        Returns:
            :class:`RRAOResult` with the total charge and per-category
            breakdown.

        Raises:
            ValidationError: If any position has invalid data.
        """
        if not positions:
            return self._empty_result()

        self._validate_positions(positions)

        # Compute charges by category -------------------------------------
        exotic_charge = 0.0
        other_charge = 0.0
        exempt_notional = 0.0

        for pos in positions:
            if pos.category == RRAOCategory.EXOTIC:
                exotic_charge += pos.notional * self.EXOTIC_RW
            elif pos.category == RRAOCategory.OTHER:
                other_charge += pos.notional * self.OTHER_RW
            elif pos.category == RRAOCategory.EXEMPT:
                exempt_notional += pos.notional

        total_charge = exotic_charge + other_charge

        logger.info(
            "RRAO: total_charge=%.2f, exotic=%.2f, other=%.2f, "
            "exempt_notional=%.2f, positions=%d",
            total_charge,
            exotic_charge,
            other_charge,
            exempt_notional,
            len(positions),
        )

        return RRAOResult(
            total_charge=total_charge,
            exotic_charge=exotic_charge,
            other_charge=other_charge,
            exempt_notional=exempt_notional,
        )

    # ------------------------------------------------------------------ #
    #  Validation                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_positions(positions: list[RRAOPosition]) -> None:
        """Validate the input position list.

        Checks that all positions have non-negative notionals and valid
        categories.

        Args:
            positions: Input RRAO positions.

        Raises:
            ValidationError: If any position fails validation.
        """
        if not positions:
            raise ValidationError(
                "No positions provided for RRAO calculation."
            )

        for idx, pos in enumerate(positions):
            if pos.notional < 0:
                raise ValidationError(
                    f"Position {idx} (instrument_id={pos.instrument_id!r}) "
                    f"has negative notional: {pos.notional}"
                )

    # ------------------------------------------------------------------ #
    #  Helper: empty result                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _empty_result() -> RRAOResult:
        """Return a zero-charge result for an empty portfolio.

        Returns:
            :class:`RRAOResult` with all fields set to zero.
        """
        return RRAOResult(
            total_charge=0.0,
            exotic_charge=0.0,
            other_charge=0.0,
            exempt_notional=0.0,
        )
