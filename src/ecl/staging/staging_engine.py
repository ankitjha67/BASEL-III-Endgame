"""Staging Engine — IFRS 9 stage allocation and SICR assessment.

Implements the three-stage impairment model:
- Stage 1: 12-month ECL (performing, no SICR)
- Stage 2: Lifetime ECL (performing, SICR detected)
- Stage 3: Lifetime ECL (credit-impaired / defaulted)

References:
    - IFRS 9 §5.5.1-5.5.20: Impairment staging criteria
    - IFRS 9 §B5.5.1-B5.5.24: Application guidance for staging
    - ASC 326-20-35: CECL subsequent measurement
    - BCBS d350 §3.1-3.3: Stage allocation requirements
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =========================================================================
#  Enumerations
# =========================================================================

class Stage(Enum):
    """IFRS 9 impairment stages.

    Reference: IFRS 9 §5.5.3-5.5.5.
    """
    STAGE_1 = 1   # 12-month ECL — performing, no SICR
    STAGE_2 = 2   # Lifetime ECL — performing, SICR detected
    STAGE_3 = 3   # Lifetime ECL — credit-impaired (defaulted)


class SICRIndicator(Enum):
    """Significant Increase in Credit Risk (SICR) trigger types.

    Reference: IFRS 9 §5.5.9-5.5.11, §B5.5.15-B5.5.24.
    """
    PD_INCREASE = "PD_INCREASE"
    RATING_DOWNGRADE = "RATING_DOWNGRADE"
    DAYS_PAST_DUE = "DAYS_PAST_DUE"
    WATCHLIST = "WATCHLIST"
    FORBEARANCE = "FORBEARANCE"
    QUALITATIVE = "QUALITATIVE"
    BACKSTOP_30DPD = "BACKSTOP_30DPD"
    EXTERNAL_RATING_DOWNGRADE = "EXTERNAL_RATING_DOWNGRADE"


# =========================================================================
#  SICR Thresholds
#  Reference: IFRS 9 §B5.5.15-B5.5.24, Internal Model Doc §6
# =========================================================================

PD_RELATIVE_THRESHOLD: float = 2.0
"""Relative PD increase threshold: current PD / origination PD >= 2.0x.
Reference: IFRS 9 §B5.5.15, commonly used 2x or 3x threshold."""

PD_ABSOLUTE_THRESHOLD: float = 0.005
"""Absolute PD increase threshold: current PD - origination PD >= 50bps.
Reference: IFRS 9 §B5.5.15."""

RATING_DOWNGRADE_NOTCHES: int = 3
"""Number of notch downgrades to trigger SICR.
Reference: Internal Model Doc §6.2."""

DPD_BACKSTOP: int = 30
"""30 days past due rebuttable presumption for SICR per IFRS 9 §5.5.11."""

DPD_DEFAULT: int = 90
"""90 days past due = default / Stage 3 per IFRS 9 §B5.5.37."""


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class SICRAssessment:
    """Result of SICR (Significant Increase in Credit Risk) assessment.

    Reference: IFRS 9 §5.5.9.
    """
    has_sicr: bool
    triggered_indicators: list[SICRIndicator] = field(default_factory=list)
    pd_at_origination: float = 0.0
    pd_current: float = 0.0
    pd_relative_change: float = 0.0
    pd_absolute_change: float = 0.0
    days_past_due: int = 0
    rating_at_origination: str = ""
    rating_current: str = ""
    rating_notch_change: int = 0
    is_on_watchlist: bool = False
    has_forbearance: bool = False
    notes: str = ""


@dataclass
class StageAssignment:
    """Final stage assignment for an exposure.

    Reference: IFRS 9 §5.5.3-5.5.5.
    """
    stage: Stage
    sicr_assessment: SICRAssessment
    is_credit_impaired: bool = False
    is_defaulted: bool = False
    ecl_horizon: str = ""  # "12_month" or "lifetime"
    assignment_reason: str = ""

    def __post_init__(self) -> None:
        """Set ECL horizon based on stage."""
        if self.stage == Stage.STAGE_1:
            self.ecl_horizon = "12_month"
        else:
            self.ecl_horizon = "lifetime"


# =========================================================================
#  Staging Engine
# =========================================================================

class StagingEngine:
    """IFRS 9 staging engine for ECL stage allocation.

    Implements the three-stage model with SICR assessment using
    quantitative (PD-based) and qualitative indicators.

    Reference: IFRS 9 §5.5.1-5.5.20, BCBS d350 §3.1-3.3.
    """

    def __init__(
        self,
        pd_relative_threshold: float = PD_RELATIVE_THRESHOLD,
        pd_absolute_threshold: float = PD_ABSOLUTE_THRESHOLD,
        rating_downgrade_notches: int = RATING_DOWNGRADE_NOTCHES,
        dpd_backstop: int = DPD_BACKSTOP,
        dpd_default: int = DPD_DEFAULT,
    ) -> None:
        """Initialize staging engine with SICR thresholds.

        Args:
            pd_relative_threshold: Relative PD change for SICR.
            pd_absolute_threshold: Absolute PD change for SICR.
            rating_downgrade_notches: Notch downgrades for SICR.
            dpd_backstop: DPD backstop for SICR.
            dpd_default: DPD threshold for default/Stage 3.

        Reference: IFRS 9 §5.5.9-5.5.11.
        """
        self.pd_relative_threshold = pd_relative_threshold
        self.pd_absolute_threshold = pd_absolute_threshold
        self.rating_downgrade_notches = rating_downgrade_notches
        self.dpd_backstop = dpd_backstop
        self.dpd_default = dpd_default

    def assess_sicr(
        self,
        pd_at_origination: float,
        pd_current: float,
        days_past_due: int = 0,
        rating_at_origination: str = "",
        rating_current: str = "",
        is_on_watchlist: bool = False,
        has_forbearance: bool = False,
    ) -> SICRAssessment:
        """Assess whether SICR has occurred.

        Tests multiple indicators per IFRS 9 §5.5.9:
        1. PD relative increase (current/origination >= threshold)
        2. PD absolute increase (current - origination >= threshold)
        3. Rating downgrade (notches >= threshold)
        4. Days past due backstop (>= 30 DPD)
        5. Watchlist/forbearance (qualitative)

        Args:
            pd_at_origination: PD at initial recognition.
            pd_current: Current PD.
            days_past_due: Days past due.
            rating_at_origination: Rating at origination.
            rating_current: Current rating.
            is_on_watchlist: Whether exposure is on watchlist.
            has_forbearance: Whether forbearance measures applied.

        Returns:
            SICRAssessment with all indicator results.

        Reference: IFRS 9 §5.5.9-5.5.11, §B5.5.15-B5.5.24.
        """
        triggered: list[SICRIndicator] = []

        # PD-based assessment
        pd_relative = pd_current / pd_at_origination if pd_at_origination > 0 else 0.0
        pd_absolute = pd_current - pd_at_origination

        if (pd_relative >= self.pd_relative_threshold
                and pd_absolute >= self.pd_absolute_threshold):
            triggered.append(SICRIndicator.PD_INCREASE)

        # Rating-based assessment
        notch_change = self._compute_notch_change(
            rating_at_origination, rating_current
        )
        if notch_change >= self.rating_downgrade_notches:
            triggered.append(SICRIndicator.RATING_DOWNGRADE)

        # DPD backstop per IFRS 9 §5.5.11
        if days_past_due >= self.dpd_backstop:
            triggered.append(SICRIndicator.BACKSTOP_30DPD)

        # Qualitative indicators
        if is_on_watchlist:
            triggered.append(SICRIndicator.WATCHLIST)
        if has_forbearance:
            triggered.append(SICRIndicator.FORBEARANCE)

        return SICRAssessment(
            has_sicr=len(triggered) > 0,
            triggered_indicators=triggered,
            pd_at_origination=pd_at_origination,
            pd_current=pd_current,
            pd_relative_change=pd_relative,
            pd_absolute_change=pd_absolute,
            days_past_due=days_past_due,
            rating_at_origination=rating_at_origination,
            rating_current=rating_current,
            rating_notch_change=notch_change,
            is_on_watchlist=is_on_watchlist,
            has_forbearance=has_forbearance,
        )

    def assign_stage(
        self,
        pd_at_origination: float,
        pd_current: float,
        days_past_due: int = 0,
        is_defaulted: bool = False,
        rating_at_origination: str = "",
        rating_current: str = "",
        is_on_watchlist: bool = False,
        has_forbearance: bool = False,
    ) -> StageAssignment:
        """Assign IFRS 9 stage to an exposure.

        Stage hierarchy:
        1. Stage 3 if defaulted or >= 90 DPD (credit-impaired)
        2. Stage 2 if SICR detected (lifetime ECL)
        3. Stage 1 otherwise (12-month ECL)

        Args:
            pd_at_origination: PD at initial recognition.
            pd_current: Current PD.
            days_past_due: Days past due.
            is_defaulted: Whether exposure has defaulted.
            rating_at_origination: Rating at origination.
            rating_current: Current rating.
            is_on_watchlist: Watchlist flag.
            has_forbearance: Forbearance flag.

        Returns:
            StageAssignment with stage, SICR assessment, and reason.

        Reference: IFRS 9 §5.5.3-5.5.5.
        """
        # Stage 3: Credit-impaired / defaulted
        if is_defaulted or days_past_due >= self.dpd_default:
            sicr = SICRAssessment(
                has_sicr=True,
                pd_at_origination=pd_at_origination,
                pd_current=pd_current,
                days_past_due=days_past_due,
            )
            reason = "Defaulted" if is_defaulted else f"{days_past_due} DPD >= {self.dpd_default}"
            return StageAssignment(
                stage=Stage.STAGE_3,
                sicr_assessment=sicr,
                is_credit_impaired=True,
                is_defaulted=is_defaulted,
                assignment_reason=reason,
            )

        # SICR assessment for Stage 1 vs Stage 2
        sicr = self.assess_sicr(
            pd_at_origination=pd_at_origination,
            pd_current=pd_current,
            days_past_due=days_past_due,
            rating_at_origination=rating_at_origination,
            rating_current=rating_current,
            is_on_watchlist=is_on_watchlist,
            has_forbearance=has_forbearance,
        )

        if sicr.has_sicr:
            indicators_str = ", ".join(i.value for i in sicr.triggered_indicators)
            return StageAssignment(
                stage=Stage.STAGE_2,
                sicr_assessment=sicr,
                assignment_reason=f"SICR: {indicators_str}",
            )

        return StageAssignment(
            stage=Stage.STAGE_1,
            sicr_assessment=sicr,
            assignment_reason="No SICR — performing",
        )

    def _compute_notch_change(
        self,
        rating_origin: str,
        rating_current: str,
    ) -> int:
        """Compute number of notches between two ratings.

        Uses the 22-grade master scale ordering where lower index = better.

        Args:
            rating_origin: Rating at origination.
            rating_current: Current rating.

        Returns:
            Number of notch downgrades (negative if upgraded).

        Reference: Internal Model Doc §6.2.
        """
        scale = [
            "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
            "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
            "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
        ]
        if rating_origin not in scale or rating_current not in scale:
            return 0
        return scale.index(rating_current) - scale.index(rating_origin)
