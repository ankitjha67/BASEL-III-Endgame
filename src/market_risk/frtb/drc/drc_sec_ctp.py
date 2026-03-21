"""DRC Securitization CTP Calculator -- FRTB Default Risk Charge.

Implements the Default Risk Charge (DRC) for Correlation Trading Portfolio
(CTP) exposures per MAR22.35-22.46 of the Basel III Endgame framework
(BCBS d457).

DRC Securitization CTP applies to nth-to-default credit derivatives,
tranched index products (e.g. CDX/iTraxx tranches), and bespoke CDO
tranches.

Key characteristics:
1. LGD = 100% for all securitization positions (no recovery assumption).
2. Risk weights depend on rating AND tranche seniority (same table as
   Non-CTP securitization per MAR22.37).
3. Hedging recognition within same tranche/index (MAR22.38-22.40):
   - Can offset long/short positions in SAME tranche of SAME index.
   - Net JTD = JTD_long + JTD_short within same tranche/index.
4. Bucket charge with hedge benefit (MAR22.41-22.42):
   - WtS = sum of RW * net_JTD for net long positions in bucket.
   - WtB = sum of RW * |net_JTD| for net short positions in bucket.
   - DRC_b = max(WtS - hedge_benefit * WtB, 0).
   - hedge_benefit = 0.5 (50% recognition).
5. Total charge = sum across buckets (no diversification).

Reference: BCBS d457 MAR22.35-22.46, US Federal Reserve Basel III Endgame
Final Rule.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from pydantic import BaseModel, Field, field_validator

from src.core.enums import (
    DRCSecCTPBucket,
    DRCSecRating,
    DRCSecSeniority,
)
from src.core.exceptions import CalculationError, ValidationError
from src.market_risk.frtb.drc.drc_params import (
    CTP_HEDGE_BENEFIT_RATIO,
    DRC_SEC_LGD,
    compute_maturity_weight,
    get_sec_risk_weight,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Data models
# =========================================================================


class DRCSecCTPPosition(BaseModel):
    """A single CTP position for DRC securitization calculation.

    Represents a tranched credit product that is part of the Correlation
    Trading Portfolio, including nth-to-default credit derivatives,
    tranched index products, and bespoke CDO tranches.

    Per MAR22.35, CTP positions are those where the underlying names are
    single-name credit instruments and the product references a specific
    tranche of the capital structure of the securitization.

    Attributes:
        tranche_id: Unique identifier for the tranche.
        index_name: Name of the underlying index or reference portfolio
            (e.g. "CDX.NA.IG.42", "iTraxx Europe 41").
        bucket: CTP bucket classification.
        rating: External credit rating category of the tranche.
        seniority: Whether the tranche is senior or non-senior.
        notional: Face value / tranche notional amount.
        market_value: Current mark-to-market value of the position.
        maturity_years: Remaining maturity in years (must be >= 0).
        is_long: ``True`` for a long credit exposure, ``False`` for short.
    """

    tranche_id: str
    index_name: str
    bucket: DRCSecCTPBucket
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


class DRCSecCTPResult(BaseModel):
    """Result of a DRC securitization CTP calculation.

    Contains the aggregate capital charge, per-bucket breakdown, and
    diagnostic JTD statistics useful for risk reporting and reconciliation.

    Attributes:
        total_charge: Aggregate DRC CTP capital charge (sum of all buckets).
        bucket_charges: Capital charge broken down by bucket label.
        gross_jtd_long: Sum of all positive (long) gross JTDs before netting.
        gross_jtd_short: Sum of all negative (short) gross JTDs before netting.
        net_jtd_long: Sum of positive net JTDs after same-tranche netting.
        net_jtd_short: Sum of negative net JTDs after same-tranche netting.
        position_count: Number of positions processed.
    """

    total_charge: float
    bucket_charges: dict[str, float]
    gross_jtd_long: float
    gross_jtd_short: float
    net_jtd_long: float
    net_jtd_short: float
    position_count: int


# =========================================================================
#  Internal intermediate types
# =========================================================================


class _CTPNettingKey(BaseModel):
    """Composite key for same-tranche / same-index netting in CTP.

    Per MAR22.38, JTDs can be offset for positions in the SAME tranche
    of the SAME index.  The netting key combines index_name and tranche_id
    to identify positions eligible for netting.
    """

    index_name: str
    tranche_id: str
    bucket: DRCSecCTPBucket
    rating: DRCSecRating
    seniority: DRCSecSeniority

    model_config = {"frozen": True}

    def __hash__(self) -> int:  # noqa: D105
        return hash(
            (self.index_name, self.tranche_id, self.bucket,
             self.rating, self.seniority)
        )

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, _CTPNettingKey):
            return NotImplemented
        return (
            self.index_name == other.index_name
            and self.tranche_id == other.tranche_id
            and self.bucket == other.bucket
            and self.rating == other.rating
            and self.seniority == other.seniority
        )


class _CTPNettedJTD(BaseModel):
    """Result of netting JTDs for a single tranche/index group in CTP.

    After same-tranche netting, each group collapses to a single net JTD
    that is either long (positive) or short (negative).
    """

    index_name: str
    tranche_id: str
    bucket: DRCSecCTPBucket
    rating: DRCSecRating
    seniority: DRCSecSeniority
    net_jtd: float  # positive = net long, negative = net short


# =========================================================================
#  Calculator
# =========================================================================


class DRCSecCTPCalculator:
    """Default Risk Charge calculator for CTP securitization exposures.

    Implements the DRC pipeline for CTP per MAR22.35-22.46:

    1. **JTD computation** -- Translate each position into a gross JTD
       using LGD=100%, tranche notional, and P&L.
    2. **Maturity weighting** -- Scale each JTD by a maturity factor.
    3. **Same-tranche netting** -- Net long and short JTDs that share
       the same index AND same tranche (MAR22.38).
    4. **Bucket aggregation** -- Group net JTDs by CTP bucket.
    5. **Hedge benefit** -- Apply 50% hedge benefit ratio to shorts
       within each bucket (MAR22.41).
    6. **Total DRC** -- Simple sum across buckets (no diversification).

    Usage::

        calculator = DRCSecCTPCalculator()
        result = calculator.calculate(positions)
        print(result.total_charge)
    """

    # ------------------------------------------------------------------ #
    #  Initialization                                                     #
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        """Initialize the DRC Sec CTP calculator.

        No mutable configuration state is kept; all regulatory parameters
        are sourced from :mod:`drc_params`.
        """
        self._positions: list[DRCSecCTPPosition] = []

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def calculate(
        self, positions: list[DRCSecCTPPosition]
    ) -> DRCSecCTPResult:
        """Calculate the DRC securitization CTP capital charge.

        This is the main entry point.  Processes all positions through
        the JTD computation, maturity weighting, same-tranche netting,
        and bucket aggregation pipeline with hedge benefit recognition.

        Args:
            positions: List of :class:`DRCSecCTPPosition` objects
                representing the CTP portfolio.

        Returns:
            :class:`DRCSecCTPResult` containing the total charge,
            per-bucket charges, and JTD statistics.
        """
        if not positions:
            return self._empty_result()

        self._validate_positions(positions)

        # Cache positions for netting step ----------------------------------
        self._positions = positions

        # Step 1-2: Compute gross JTDs with maturity weighting --------------
        gross_jtds = self._compute_all_jtds(positions)

        # Gross JTD statistics ----------------------------------------------
        gross_jtd_long = sum(j for j in gross_jtds.values() if j > 0)
        gross_jtd_short = sum(j for j in gross_jtds.values() if j < 0)

        # Step 3: Same-tranche netting per MAR22.38 -------------------------
        netted = self._net_same_tranche(gross_jtds)

        # Net JTD statistics ------------------------------------------------
        net_jtd_long = sum(n.net_jtd for n in netted if n.net_jtd > 0)
        net_jtd_short = sum(n.net_jtd for n in netted if n.net_jtd < 0)

        # Step 4-6: Bucket-level charges with hedge benefit -----------------
        bucket_charges = self._compute_bucket_charges(netted)

        # Total DRC (simple sum, no diversification) ------------------------
        total_charge = sum(bucket_charges.values())

        logger.info(
            "DRC sec CTP: total_charge=%.2f, buckets=%d, "
            "gross_long=%.2f, gross_short=%.2f, "
            "net_long=%.2f, net_short=%.2f, positions=%d",
            total_charge,
            len(bucket_charges),
            gross_jtd_long,
            gross_jtd_short,
            net_jtd_long,
            net_jtd_short,
            len(positions),
        )

        return DRCSecCTPResult(
            total_charge=total_charge,
            bucket_charges=bucket_charges,
            gross_jtd_long=gross_jtd_long,
            gross_jtd_short=gross_jtd_short,
            net_jtd_long=net_jtd_long,
            net_jtd_short=net_jtd_short,
            position_count=len(positions),
        )

    # ------------------------------------------------------------------ #
    #  Step 1-2: JTD computation & maturity weighting                    #
    # ------------------------------------------------------------------ #

    def _compute_all_jtds(
        self, positions: list[DRCSecCTPPosition]
    ) -> dict[int, float]:
        """Compute maturity-weighted gross JTD for every CTP position.

        Per MAR22.37, the JTD calculation for CTP uses the same formula
        as securitization non-CTP with LGD = 100%.

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
    def _compute_jtd(position: DRCSecCTPPosition) -> float:
        """Compute the raw jump-to-default amount for a CTP position.

        Per MAR22.37, same JTD formula as securitization non-CTP:

        .. math::

            \\mathrm{JTD}_{\\mathrm{long}}
                = \\max(\\mathrm{LGD} \\times \\mathrm{notional}
                        + \\mathrm{P\\&L},\\; 0)

            \\mathrm{JTD}_{\\mathrm{short}}
                = \\min(\\mathrm{LGD} \\times \\mathrm{notional}
                        + \\mathrm{P\\&L},\\; 0)

        where LGD = 100%.

        Args:
            position: A single :class:`DRCSecCTPPosition`.

        Returns:
            Gross JTD amount (positive for longs, negative for shorts).
        """
        lgd = DRC_SEC_LGD  # 100% per MAR22.37
        pnl = position.market_value - position.notional

        raw = lgd * position.notional + pnl

        if position.is_long:
            return max(raw, 0.0)
        else:
            return min(-abs(raw), 0.0) if raw != 0.0 else 0.0

    @staticmethod
    def _apply_maturity_weight(jtd: float, maturity_years: float) -> float:
        """Scale a JTD amount by the regulatory maturity weight.

        Per MAR22.28 (applicable to CTP as well), the maturity weight
        scales linearly with a 1-year cap and 3-month floor.

        Args:
            jtd: Raw JTD amount (positive or negative).
            maturity_years: Remaining maturity in years.

        Returns:
            Maturity-weighted JTD.
        """
        weight = compute_maturity_weight(maturity_years)
        return jtd * weight

    # ------------------------------------------------------------------ #
    #  Step 3: Same-tranche netting -- MAR22.38                          #
    # ------------------------------------------------------------------ #

    def _net_same_tranche(
        self, gross_jtds: dict[int, float]
    ) -> list[_CTPNettedJTD]:
        """Net JTDs across positions in the same tranche of the same index.

        Per MAR22.38, long and short JTDs can be offset for positions
        that share the same index name AND the same tranche identifier.
        This is a more restrictive netting set than the non-sec DRC
        (which nets by issuer/seniority).

        Args:
            gross_jtds: Mapping of position index to gross JTD.

        Returns:
            List of :class:`_CTPNettedJTD` objects, one per netting group.
        """
        netting_groups: dict[_CTPNettingKey, float] = defaultdict(float)

        for idx, jtd in gross_jtds.items():
            pos = self._positions[idx]
            key = _CTPNettingKey(
                index_name=pos.index_name,
                tranche_id=pos.tranche_id,
                bucket=pos.bucket,
                rating=pos.rating,
                seniority=pos.seniority,
            )
            netting_groups[key] += jtd

        result: list[_CTPNettedJTD] = []
        for key, net_jtd in netting_groups.items():
            result.append(
                _CTPNettedJTD(
                    index_name=key.index_name,
                    tranche_id=key.tranche_id,
                    bucket=key.bucket,
                    rating=key.rating,
                    seniority=key.seniority,
                    net_jtd=net_jtd,
                )
            )

        return result

    # ------------------------------------------------------------------ #
    #  Step 4-6: Bucket aggregation with hedge benefit -- MAR22.41-22.42 #
    # ------------------------------------------------------------------ #

    def _compute_bucket_charges(
        self, netted: list[_CTPNettedJTD]
    ) -> dict[str, float]:
        """Compute the DRC CTP capital charge for each bucket.

        Per MAR22.41-22.42:

        1. Group net JTDs by CTP bucket.
        2. Separate net longs and net shorts within each bucket.
        3. Compute weighted long (WtS) and weighted short (WtB).
        4. Apply hedge benefit ratio (50%) to shorts:

        .. math::

            \\mathrm{DRC}_b = \\max\\!\\Bigl(
                \\mathrm{WtS} - 0.5 \\times \\mathrm{WtB}
            ,\\;0\\Bigr)

        Args:
            netted: List of netted JTDs from step 3.

        Returns:
            Dictionary mapping bucket label to its DRC charge.
        """
        # Group by bucket ---------------------------------------------------
        buckets: dict[str, list[_CTPNettedJTD]] = defaultdict(list)
        for n in netted:
            label = n.bucket.value
            buckets[label].append(n)

        charges: dict[str, float] = {}

        for bucket_label, bucket_positions in buckets.items():
            # Separate longs and shorts -------------------------------------
            longs = [n for n in bucket_positions if n.net_jtd > 0]
            shorts = [n for n in bucket_positions if n.net_jtd < 0]

            # WtS: risk-weighted long charge per MAR22.41 -------------------
            wts = sum(
                get_sec_risk_weight(n.rating, n.seniority) * n.net_jtd
                for n in longs
            )

            # WtB: risk-weighted short charge (absolute) per MAR22.41 ------
            wtb = sum(
                get_sec_risk_weight(n.rating, n.seniority) * abs(n.net_jtd)
                for n in shorts
            )

            # Bucket charge with 50% hedge benefit per MAR22.42 ------------
            bucket_charge = max(wts - CTP_HEDGE_BENEFIT_RATIO * wtb, 0.0)

            logger.debug(
                "DRC sec CTP bucket=%s: wts=%.2f, wtb=%.2f, "
                "hedge_benefit=%.2f, charge=%.2f",
                bucket_label,
                wts,
                wtb,
                CTP_HEDGE_BENEFIT_RATIO,
                bucket_charge,
            )

            charges[bucket_label] = bucket_charge

        return charges

    # ------------------------------------------------------------------ #
    #  Validation                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_positions(positions: list[DRCSecCTPPosition]) -> None:
        """Validate the input CTP position list.

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
                "No positions provided for DRC sec CTP calculation."
            )

        for idx, pos in enumerate(positions):
            if pos.market_value < 0 and pos.is_long:
                logger.warning(
                    "CTP position %d (tranche=%s) is long with negative "
                    "market value (%.2f) -- verify data quality.",
                    idx,
                    pos.tranche_id,
                    pos.market_value,
                )

    # ------------------------------------------------------------------ #
    #  Helper: empty result                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _empty_result() -> DRCSecCTPResult:
        """Return a zero-charge result for an empty portfolio.

        Returns:
            :class:`DRCSecCTPResult` with all fields set to zero / empty.
        """
        return DRCSecCTPResult(
            total_charge=0.0,
            bucket_charges={},
            gross_jtd_long=0.0,
            gross_jtd_short=0.0,
            net_jtd_long=0.0,
            net_jtd_short=0.0,
            position_count=0,
        )
