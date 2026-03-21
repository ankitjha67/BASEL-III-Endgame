"""LGD Models — Loss Given Default calculators for ECL.

Implements collateral recovery, workout LGD, downturn LGD, and cure rate
models used in the ECL engine.

All amounts in USD millions ($M). LGD expressed as decimal (0.45 = 45%).

References:
    - BCBS d350 §5.1-5.3: LGD estimation for ECL
    - BCBS d424 CRE32.14-32.16: Supervisory LGD values
    - IFRS 9 §B5.5.28-B5.5.34: LGD measurement
    - ASC 326-20-30-5: Loss rate estimation for CECL
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from src.ecl.lgd_models.lgd_params import (
    COLLATERAL_HAIRCUTS,
    DEFAULT_CURE_RATES,
    DOWNTURN_LGD_ADD_ON,
    LGD_CAP,
    LGD_FLOOR,
    SUPERVISORY_LGD,
    WORKOUT_DISCOUNT_RATE,
    AVERAGE_WORKOUT_PERIODS,
)


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class LGDResult:
    """Result of LGD estimation.

    Reference: BCBS d350 §5.1.
    """
    base_lgd: float
    downturn_lgd: float
    effective_lgd: float
    cure_rate: float = 0.0
    collateral_recovery: float = 0.0
    workout_lgd: Optional[float] = None
    asset_class: str = "corporate"
    collateral_type: Optional[str] = None
    is_downturn: bool = False


# =========================================================================
#  Collateral Recovery Model
# =========================================================================

class CollateralRecoveryModel:
    """Collateral recovery estimation using supervisory haircuts.

    Computes the expected recovery from collateral, net of liquidation
    costs and haircuts, to reduce LGD for secured exposures.

    Reference: BCBS d424 CRE22.48-72, BCBS d350 §5.1.2.
    """

    def __init__(
        self,
        haircuts: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize with collateral haircut schedule.

        Args:
            haircuts: Collateral type to haircut mapping.

        Reference: BCBS d424 CRE22.48.
        """
        self.haircuts = haircuts or COLLATERAL_HAIRCUTS

    def compute_recovery(
        self,
        collateral_value: float,
        collateral_type: str,
        ead: float,
        liquidation_cost_pct: float = 0.05,
    ) -> float:
        """Compute expected recovery from collateral.

        Recovery = max(0, Collateral * (1 - haircut) * (1 - liquidation_cost))
        Recovery rate = min(1.0, Recovery / EAD)

        Args:
            collateral_value: Market value of collateral ($M).
            collateral_type: Type for haircut lookup.
            ead: Exposure at default ($M).
            liquidation_cost_pct: Liquidation cost as fraction.

        Returns:
            Recovery rate (0 to 1).

        Reference: BCBS d424 CRE22.48-72.
        """
        if ead <= 0 or collateral_value <= 0:
            return 0.0

        haircut = self.haircuts.get(collateral_type, 0.40)
        net_collateral = collateral_value * (1.0 - haircut) * (1.0 - liquidation_cost_pct)
        recovery_rate = min(1.0, max(0.0, net_collateral / ead))
        return recovery_rate


class WorkoutLGDModel:
    """Workout-based LGD estimation from historical recovery data.

    Computes LGD from observed workout recoveries, discounted at the
    original effective interest rate.

    Reference: BCBS d350 §5.1.3, IFRS 9 §B5.5.28.
    """

    def __init__(
        self,
        discount_rate: float = WORKOUT_DISCOUNT_RATE,
        workout_periods: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize workout LGD model.

        Args:
            discount_rate: Discount rate for recovery cash flows.
            workout_periods: Asset class to average workout period mapping.

        Reference: IFRS 9 §B5.5.28.
        """
        self.discount_rate = discount_rate
        self.workout_periods = workout_periods or AVERAGE_WORKOUT_PERIODS

    def compute_workout_lgd(
        self,
        recovery_rate: float,
        asset_class: str = "corporate",
        direct_costs_pct: float = 0.03,
        indirect_costs_pct: float = 0.02,
    ) -> float:
        """Compute workout LGD from recovery rate.

        Workout LGD = 1 - PV(recovery) + costs
        PV(recovery) = recovery_rate / (1 + r)^T

        Args:
            recovery_rate: Gross recovery rate (0 to 1).
            asset_class: For workout period lookup.
            direct_costs_pct: Direct workout costs (legal, admin).
            indirect_costs_pct: Indirect costs (opportunity, management).

        Returns:
            Workout LGD (decimal).

        Reference: BCBS d350 §5.1.3.
        """
        workout_years = self.workout_periods.get(asset_class, 2.0)
        discount_factor = (1.0 + self.discount_rate) ** workout_years
        pv_recovery = recovery_rate / discount_factor
        total_costs = direct_costs_pct + indirect_costs_pct
        lgd = 1.0 - pv_recovery + total_costs
        return min(max(lgd, LGD_FLOOR), LGD_CAP)


class DownturnLGDModel:
    """Downturn LGD model applying stress add-ons to base LGD.

    Computes LGD under adverse economic conditions by adding a
    calibrated stress component to the normal-period LGD.

    Reference: BCBS d350 §5.2, EBA GL/2019/03.
    """

    def __init__(
        self,
        add_ons: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize downturn LGD model.

        Args:
            add_ons: Asset class to downturn add-on mapping.

        Reference: BCBS d350 §5.2.
        """
        self.add_ons = add_ons or DOWNTURN_LGD_ADD_ON

    def compute_downturn_lgd(
        self,
        base_lgd: float,
        asset_class: str = "senior_unsecured",
    ) -> float:
        """Compute downturn LGD.

        Downturn LGD = base LGD + downturn add-on, capped at LGD_CAP.

        Args:
            base_lgd: Normal-period LGD (decimal).
            asset_class: For add-on lookup.

        Returns:
            Downturn LGD (decimal).

        Reference: BCBS d350 §5.2.
        """
        add_on = self.add_ons.get(asset_class, 0.08)
        return min(base_lgd + add_on, LGD_CAP)


class CureRateModel:
    """Cure rate model for defaulted exposures.

    Estimates the probability that a defaulted exposure returns to
    performing status, reducing the effective LGD.

    Reference: BCBS d350 §5.3, Internal Model Doc §4.3.
    """

    def __init__(
        self,
        cure_rates: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize cure rate model.

        Args:
            cure_rates: Asset class to cure rate mapping.

        Reference: BCBS d350 §5.3.
        """
        self.cure_rates = cure_rates or DEFAULT_CURE_RATES

    def get_cure_rate(self, asset_class: str) -> float:
        """Look up cure rate for an asset class.

        Args:
            asset_class: Borrower/exposure asset class.

        Returns:
            Cure rate probability (0 to 1).

        Reference: BCBS d350 §5.3.
        """
        return self.cure_rates.get(asset_class, 0.10)

    def adjust_lgd_for_cure(
        self,
        lgd: float,
        asset_class: str,
    ) -> float:
        """Adjust LGD downward for cure probability.

        Effective LGD = (1 - cure_rate) * LGD

        Args:
            lgd: Pre-cure LGD (decimal).
            asset_class: For cure rate lookup.

        Returns:
            Cure-adjusted LGD (decimal).

        Reference: BCBS d350 §5.3.
        """
        cure_rate = self.get_cure_rate(asset_class)
        return max(lgd * (1.0 - cure_rate), LGD_FLOOR)


class LGDModel:
    """Main LGD model orchestrating all sub-models.

    Combines collateral recovery, workout, downturn adjustment, and
    cure rate into a single LGD estimation pipeline.

    Reference: BCBS d350 §5.1-5.3.
    """

    def __init__(
        self,
        collateral_model: Optional[CollateralRecoveryModel] = None,
        workout_model: Optional[WorkoutLGDModel] = None,
        downturn_model: Optional[DownturnLGDModel] = None,
        cure_model: Optional[CureRateModel] = None,
    ) -> None:
        """Initialize LGD model with sub-models.

        Reference: SR 11-7 §III.
        """
        self.collateral_model = collateral_model or CollateralRecoveryModel()
        self.workout_model = workout_model or WorkoutLGDModel()
        self.downturn_model = downturn_model or DownturnLGDModel()
        self.cure_model = cure_model or CureRateModel()

    def compute_lgd(
        self,
        asset_class: str = "corporate",
        seniority: str = "senior_unsecured",
        collateral_value: float = 0.0,
        collateral_type: Optional[str] = None,
        ead: float = 100.0,
        use_downturn: bool = True,
        apply_cure: bool = True,
    ) -> LGDResult:
        """Compute LGD through the full model pipeline.

        Pipeline:
        1. Start with supervisory LGD for seniority
        2. Adjust for collateral recovery
        3. Apply downturn add-on if applicable
        4. Apply cure rate adjustment

        Args:
            asset_class: Borrower asset class.
            seniority: Debt seniority for base LGD lookup.
            collateral_value: Market value of collateral ($M).
            collateral_type: Collateral type for haircut.
            ead: Exposure at default ($M).
            use_downturn: Apply downturn LGD.
            apply_cure: Apply cure rate adjustment.

        Returns:
            LGDResult with all components.

        Reference: BCBS d350 §5.1-5.3.
        """
        # Step 1: Base LGD from supervisory values
        base_lgd = SUPERVISORY_LGD.get(seniority, 0.45)

        # Step 2: Collateral recovery
        collateral_recovery = 0.0
        if collateral_value > 0 and collateral_type:
            collateral_recovery = self.collateral_model.compute_recovery(
                collateral_value, collateral_type, ead
            )
            base_lgd = max(base_lgd * (1.0 - collateral_recovery), LGD_FLOOR)

        # Step 3: Downturn adjustment
        downturn_lgd = self.downturn_model.compute_downturn_lgd(
            base_lgd, seniority
        ) if use_downturn else base_lgd

        # Step 4: Cure rate
        effective_lgd = downturn_lgd
        cure_rate = 0.0
        if apply_cure:
            cure_rate = self.cure_model.get_cure_rate(asset_class)
            effective_lgd = self.cure_model.adjust_lgd_for_cure(
                downturn_lgd, asset_class
            )

        workout_lgd = self.workout_model.compute_workout_lgd(
            1.0 - base_lgd, asset_class
        )

        return LGDResult(
            base_lgd=base_lgd,
            downturn_lgd=downturn_lgd,
            effective_lgd=effective_lgd,
            cure_rate=cure_rate,
            collateral_recovery=collateral_recovery,
            workout_lgd=workout_lgd,
            asset_class=asset_class,
            collateral_type=collateral_type,
            is_downturn=use_downturn,
        )
