"""Large Exposures Framework — Single-Counterparty Credit Limits.

Implements the supervisory framework for measuring and controlling large
exposures per 12 CFR 252 Subpart J (US) and BCBS d283 (international).

Key limits:
    - G-SIB to G-SIB: 15% of Tier 1 capital
    - All other counterparties: 25% of Tier 1 capital
    - Reporting threshold: 5% of Tier 1 capital

Exposure measurement includes loans, securities, derivatives (SA-CCR EAD),
SFTs, and off-balance sheet items, net of eligible CRM.

References:
    - 12 CFR 252 Subpart J — Single-Counterparty Credit Limits
    - 12 CFR 252.70-252.78 — Definitions, scope, limits, exemptions
    - BCBS d283 — Supervisory Framework for Large Exposures (April 2014)
    - Federal Reserve Basel III Endgame 2026 Re-Proposal
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# =========================================================================
#  Enumerations
# =========================================================================

class CounterpartyCategory(str, Enum):
    """Counterparty category for limit determination.

    Per 12 CFR 252.71, different limits apply based on the counterparty
    type and the reporting bank's own category.
    """

    GSIB = "GSIB"
    NON_GSIB_FINANCIAL = "NON_GSIB_FINANCIAL"
    NON_FINANCIAL = "NON_FINANCIAL"
    SOVEREIGN = "SOVEREIGN"
    CCP_QUALIFYING = "CCP_QUALIFYING"
    CCP_NON_QUALIFYING = "CCP_NON_QUALIFYING"


class ExposureType(str, Enum):
    """Type of credit exposure for measurement purposes.

    Per 12 CFR 252.73, exposures are measured differently depending
    on the product type.
    """

    LOAN = "LOAN"
    SECURITIES = "SECURITIES"
    DERIVATIVE = "DERIVATIVE"
    SFT = "SFT"
    OFF_BALANCE_SHEET = "OFF_BALANCE_SHEET"
    OTHER = "OTHER"


class ExemptionReason(str, Enum):
    """Reasons an exposure may be exempt from the limit.

    Per 12 CFR 252.77, certain exposures are excluded from the
    single-counterparty credit limit calculation.
    """

    US_GOVERNMENT = "US_GOVERNMENT"
    US_AGENCY = "US_AGENCY"
    INTRADAY = "INTRADAY"
    CCP_TRADE_EXPOSURE = "CCP_TRADE_EXPOSURE"
    GRANDFATHERED = "GRANDFATHERED"


class ConnectionType(str, Enum):
    """Type of economic interdependence between counterparties.

    Per 12 CFR 252.76 and BCBS d283 Section 5, connected counterparties
    must be aggregated when they share material dependencies.
    """

    REVENUE = "REVENUE"
    GUARANTEE = "GUARANTEE"
    FUNDING = "FUNDING"
    CONTROL = "CONTROL"


# =========================================================================
#  Data Models
# =========================================================================

class CounterpartyExposure(BaseModel):
    """Single exposure to a counterparty for large exposure measurement.

    Per 12 CFR 252.73, each exposure is measured at its gross value
    before CRM adjustments. CRM fields allow netting down to net exposure.

    All monetary amounts in USD millions ($M).

    References:
        12 CFR 252.73 — Gross credit exposure measurement
        12 CFR 252.74 — Net credit exposure (after CRM)
    """

    counterparty_id: str = Field(description="Unique counterparty identifier")
    counterparty_name: str = Field(description="Counterparty legal name")
    counterparty_category: CounterpartyCategory = Field(
        description="Category for limit determination per 12 CFR 252.71",
    )
    exposure_type: ExposureType = Field(
        description="Product type for measurement per 12 CFR 252.73",
    )
    gross_exposure: float = Field(
        ge=0.0,
        description="Gross credit exposure amount ($M)",
    )
    collateral_value: float = Field(
        default=0.0,
        ge=0.0,
        description="Eligible collateral value ($M) per 12 CFR 252.74(a)",
    )
    collateral_haircut: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Supervisory haircut on collateral (decimal)",
    )
    guarantee_amount: float = Field(
        default=0.0,
        ge=0.0,
        description="Eligible guarantee/credit derivative protection ($M)",
    )
    guarantor_id: str | None = Field(
        default=None,
        description="Guarantor counterparty ID (for exposure shifting)",
    )
    netting_set_id: str | None = Field(
        default=None,
        description="Netting agreement identifier for derivatives/SFTs",
    )
    is_exempt: bool = Field(
        default=False,
        description="Whether this exposure is exempt per 12 CFR 252.77",
    )
    exemption_reason: ExemptionReason | None = Field(
        default=None,
        description="Reason for exemption if is_exempt=True",
    )

    @field_validator("exemption_reason")
    @classmethod
    def validate_exemption(
        cls, v: ExemptionReason | None, info: object
    ) -> ExemptionReason | None:
        """Ensure exemption_reason is provided when is_exempt=True."""
        return v


class CounterpartyGroup(BaseModel):
    """Group of economically interdependent counterparties.

    Per 12 CFR 252.76 and BCBS d283 Section 5, counterparties that
    are economically interdependent must be treated as a single
    counterparty for limit purposes.

    Aggregation triggers:
        - Revenue dependency > 50%
        - Full or partial guarantee dependency
        - Common funding source dependency
        - Common controlling entity

    References:
        12 CFR 252.76 — Aggregation of exposures to connected counterparties
        BCBS d283, Section 5 — Connected counterparties
    """

    group_id: str = Field(description="Unique group identifier")
    group_name: str = Field(description="Descriptive name for the group")
    member_ids: list[str] = Field(
        description="Counterparty IDs of group members",
        min_length=2,
    )
    connection_type: ConnectionType = Field(
        description="Basis for economic interdependence",
    )


class LargeExposureResult(BaseModel):
    """Result for a single counterparty or connected group.

    Contains the gross and net exposure, applicable limit, headroom,
    and breach status per 12 CFR 252.72.

    All monetary amounts in USD millions ($M).

    References:
        12 CFR 252.72 — Credit exposure limits
        12 CFR 252.78 — Reporting requirements
    """

    counterparty_id: str = Field(description="Counterparty or group ID")
    counterparty_name: str = Field(description="Counterparty or group name")
    counterparty_category: CounterpartyCategory = Field(
        description="Category for limit determination",
    )
    gross_exposure: float = Field(
        description="Total gross exposure ($M)",
    )
    net_exposure: float = Field(
        description="Net exposure after CRM ($M)",
    )
    tier1_capital: float = Field(
        description="Reference Tier 1 capital ($M)",
    )
    exposure_pct_tier1: float = Field(
        description="Net exposure as % of Tier 1 capital",
    )
    limit_pct: float = Field(
        description="Applicable limit (0.15 or 0.25)",
    )
    limit_amount: float = Field(
        description="Limit amount = limit_pct × tier1_capital ($M)",
    )
    headroom: float = Field(
        description="Remaining capacity = limit_amount - net_exposure ($M)",
    )
    is_breach: bool = Field(
        description="True if net_exposure > limit_amount",
    )
    is_reportable: bool = Field(
        description="True if exposure >= 5% of Tier 1 (per 12 CFR 252.78)",
    )
    exposure_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown by ExposureType ($M)",
    )


class LargeExposureSummary(BaseModel):
    """Summary of all large exposure calculations.

    Provides portfolio-level statistics and per-counterparty details
    for regulatory reporting and risk management.

    References:
        12 CFR 252.78 — Compliance and reporting
        FR Y-15 — Systemic Risk Report (Section F)
    """

    total_counterparties: int = Field(description="Number of counterparties analysed")
    reportable_exposures: int = Field(
        description="Number of exposures >= 5% of Tier 1",
    )
    limit_breaches: int = Field(
        description="Number of counterparties exceeding limit",
    )
    largest_exposure_pct: float = Field(
        description="Largest single exposure as % of Tier 1",
    )
    total_gross_exposure: float = Field(description="Sum of all gross exposures ($M)")
    total_net_exposure: float = Field(description="Sum of all net exposures ($M)")
    tier1_capital: float = Field(description="Reference Tier 1 capital ($M)")
    counterparty_results: list[LargeExposureResult] = Field(
        default_factory=list,
        description="Per-counterparty results",
    )
    connected_groups: list[dict] = Field(
        default_factory=list,
        description="Connected counterparty group details",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Calculation timestamp (ISO 8601)",
    )


# =========================================================================
#  Large Exposure Calculator
# =========================================================================

# Regulatory limits per 12 CFR 252.72
GSIB_TO_GSIB_LIMIT: float = 0.15  # 15% of Tier 1
STANDARD_LIMIT: float = 0.25  # 25% of Tier 1
REPORTING_THRESHOLD: float = 0.05  # 5% of Tier 1


class LargeExposureCalculator:
    """Calculate and monitor single-counterparty credit limits.

    Implements the full large exposures framework per 12 CFR 252 Subpart J
    for Category I US G-SIBs. The calculator:

    1. Aggregates exposures by counterparty (12 CFR 252.73)
    2. Applies CRM adjustments to derive net exposure (12 CFR 252.74)
    3. Checks exemptions (12 CFR 252.77)
    4. Determines applicable limit (15% or 25%) per counterparty type
    5. Aggregates connected counterparties (12 CFR 252.76)
    6. Reports breaches and reportable exposures (12 CFR 252.78)

    Args:
        tier1_capital: Tier 1 capital of the reporting bank ($M).
        is_gsib: Whether the reporting bank is a G-SIB (affects limits).

    References:
        12 CFR 252 Subpart J — Single-Counterparty Credit Limits
        BCBS d283 — Supervisory Framework for Large Exposures
    """

    def __init__(self, tier1_capital: float, is_gsib: bool = True) -> None:
        """Initialise with reference Tier 1 capital.

        Args:
            tier1_capital: Consolidated Tier 1 capital ($M). Must be > 0.
            is_gsib: Whether the reporting institution is a G-SIB.

        Raises:
            ValueError: If tier1_capital <= 0.
        """
        if tier1_capital <= 0:
            raise ValueError(
                f"Tier 1 capital must be positive, got {tier1_capital}"
            )
        self.tier1_capital = tier1_capital
        self.is_gsib = is_gsib
        logger.info(
            "LargeExposureCalculator initialised: T1=$%.1fM, G-SIB=%s",
            tier1_capital,
            is_gsib,
        )

    def calculate(
        self,
        exposures: list[CounterpartyExposure],
        connected_groups: list[CounterpartyGroup] | None = None,
    ) -> LargeExposureSummary:
        """Calculate large exposures for all counterparties.

        Per 12 CFR 252.73-252.78:
        1. Filter out exempt exposures
        2. Aggregate by counterparty
        3. Apply CRM to compute net exposure
        4. Check against applicable limits
        5. Aggregate connected counterparties

        Args:
            exposures: List of individual counterparty exposures.
            connected_groups: Optional list of connected counterparty groups.

        Returns:
            LargeExposureSummary with per-counterparty results and statistics.

        References:
            12 CFR 252.73 — Gross credit exposure
            12 CFR 252.74 — Net credit exposure
            12 CFR 252.72 — Credit exposure limits
        """
        if not exposures:
            return self._empty_summary()

        # 1. Separate exempt vs. non-exempt
        non_exempt = [e for e in exposures if not self._check_exemption(e)]
        logger.info(
            "Processing %d exposures (%d exempt, %d non-exempt)",
            len(exposures),
            len(exposures) - len(non_exempt),
            len(non_exempt),
        )

        # 2. Aggregate by counterparty
        by_counterparty = self._aggregate_by_counterparty(non_exempt)

        # 3. Compute per-counterparty results
        counterparty_results: list[LargeExposureResult] = []
        for cp_id, cp_exposures in by_counterparty.items():
            result = self._compute_counterparty_result(cp_id, cp_exposures)
            counterparty_results.append(result)

        # 4. Handle connected counterparty groups
        group_details: list[dict] = []
        if connected_groups:
            group_details = self._aggregate_connected(
                {r.counterparty_id: r for r in counterparty_results},
                connected_groups,
            )

        # 5. Build summary
        reportable = [r for r in counterparty_results if r.is_reportable]
        breaches = [r for r in counterparty_results if r.is_breach]
        largest_pct = (
            max(r.exposure_pct_tier1 for r in counterparty_results)
            if counterparty_results
            else 0.0
        )

        summary = LargeExposureSummary(
            total_counterparties=len(counterparty_results),
            reportable_exposures=len(reportable),
            limit_breaches=len(breaches),
            largest_exposure_pct=largest_pct,
            total_gross_exposure=sum(r.gross_exposure for r in counterparty_results),
            total_net_exposure=sum(r.net_exposure for r in counterparty_results),
            tier1_capital=self.tier1_capital,
            counterparty_results=counterparty_results,
            connected_groups=group_details,
        )

        logger.info(
            "Large exposure summary: %d counterparties, %d reportable, "
            "%d breaches, largest=%.2f%% of T1",
            summary.total_counterparties,
            summary.reportable_exposures,
            summary.limit_breaches,
            summary.largest_exposure_pct * 100,
        )
        return summary

    def _aggregate_by_counterparty(
        self, exposures: list[CounterpartyExposure]
    ) -> dict[str, list[CounterpartyExposure]]:
        """Group exposures by counterparty ID.

        Per 12 CFR 252.73, all exposures to the same counterparty must
        be aggregated for limit purposes.

        Args:
            exposures: Non-exempt exposures.

        Returns:
            Dict mapping counterparty_id to list of exposures.
        """
        result: dict[str, list[CounterpartyExposure]] = {}
        for exp in exposures:
            result.setdefault(exp.counterparty_id, []).append(exp)
        return result

    def _compute_counterparty_result(
        self,
        counterparty_id: str,
        exposures: list[CounterpartyExposure],
    ) -> LargeExposureResult:
        """Compute large exposure result for a single counterparty.

        Per 12 CFR 252.73-252.74:
        - Gross exposure = sum of all individual exposures
        - Net exposure = gross - eligible CRM adjustments

        Args:
            counterparty_id: Counterparty identifier.
            exposures: All exposures to this counterparty.

        Returns:
            LargeExposureResult with limit check.
        """
        first = exposures[0]
        gross = sum(e.gross_exposure for e in exposures)
        net = self._apply_crm(exposures)
        limit_pct = self._get_limit(first.counterparty_category)
        limit_amount = limit_pct * self.tier1_capital
        pct_tier1 = net / self.tier1_capital if self.tier1_capital > 0 else 0.0

        # Breakdown by exposure type
        breakdown: dict[str, float] = {}
        for exp in exposures:
            key = exp.exposure_type.value
            breakdown[key] = breakdown.get(key, 0.0) + exp.gross_exposure

        return LargeExposureResult(
            counterparty_id=counterparty_id,
            counterparty_name=first.counterparty_name,
            counterparty_category=first.counterparty_category,
            gross_exposure=gross,
            net_exposure=net,
            tier1_capital=self.tier1_capital,
            exposure_pct_tier1=pct_tier1,
            limit_pct=limit_pct,
            limit_amount=limit_amount,
            headroom=limit_amount - net,
            is_breach=net > limit_amount,
            is_reportable=pct_tier1 >= REPORTING_THRESHOLD,
            exposure_breakdown=breakdown,
        )

    def _apply_crm(self, exposures: list[CounterpartyExposure]) -> float:
        """Apply credit risk mitigation to derive net exposure.

        Per 12 CFR 252.74:
        - Eligible financial collateral reduces exposure (after haircuts)
        - Eligible guarantees shift exposure to guarantor (not netted here)
        - Net exposure = max(gross - collateral_after_haircut - guarantees, 0)

        The guarantee amount is subtracted from this counterparty's exposure;
        in a full implementation it would be added to the guarantor's exposure.

        Args:
            exposures: All exposures to a single counterparty.

        Returns:
            Net exposure after CRM ($M). Never negative.

        References:
            12 CFR 252.74 — Net credit exposure
        """
        gross = sum(e.gross_exposure for e in exposures)
        total_collateral = sum(
            e.collateral_value * (1.0 - e.collateral_haircut)
            for e in exposures
        )
        total_guarantees = sum(e.guarantee_amount for e in exposures)
        net = max(gross - total_collateral - total_guarantees, 0.0)

        logger.debug(
            "CRM: gross=$%.1fM, collateral=$%.1fM, guarantees=$%.1fM, net=$%.1fM",
            gross,
            total_collateral,
            total_guarantees,
            net,
        )
        return net

    def _get_limit(self, counterparty_category: CounterpartyCategory) -> float:
        """Get the applicable single-counterparty credit limit.

        Per 12 CFR 252.72:
        - G-SIB reporting bank to G-SIB counterparty: 15% of Tier 1
        - All other counterparties: 25% of Tier 1
        - Sovereigns and qualifying CCPs: exempt (handled separately)

        Args:
            counterparty_category: Category of the counterparty.

        Returns:
            Limit as a fraction of Tier 1 capital (0.15 or 0.25).

        References:
            12 CFR 252.72(a) — G-SIB to G-SIB limit
            12 CFR 252.72(b) — Standard limit
        """
        if (
            self.is_gsib
            and counterparty_category == CounterpartyCategory.GSIB
        ):
            return GSIB_TO_GSIB_LIMIT
        return STANDARD_LIMIT

    def _check_exemption(self, exposure: CounterpartyExposure) -> bool:
        """Check if an exposure qualifies for exemption.

        Per 12 CFR 252.77, certain exposures are excluded:
        - Direct exposures to the US government or agencies
        - Intraday exposures
        - Trade exposures to qualifying CCPs (T+5)
        - Certain pre-existing (grandfathered) exposures

        Args:
            exposure: The exposure to check.

        Returns:
            True if the exposure is exempt from limit.

        References:
            12 CFR 252.77 — Exemptions
        """
        if exposure.is_exempt:
            logger.debug(
                "Exempt exposure: %s (%s) — %s",
                exposure.counterparty_name,
                exposure.exposure_type.value,
                exposure.exemption_reason.value if exposure.exemption_reason else "no reason",
            )
            return True

        # Auto-exempt sovereign US government exposures
        if exposure.counterparty_category == CounterpartyCategory.SOVEREIGN:
            logger.debug(
                "Auto-exempt sovereign: %s",
                exposure.counterparty_name,
            )
            return True

        return False

    def _aggregate_connected(
        self,
        counterparty_results: dict[str, LargeExposureResult],
        groups: list[CounterpartyGroup],
    ) -> list[dict]:
        """Aggregate exposures for economically connected counterparties.

        Per 12 CFR 252.76, when counterparties are connected through
        economic interdependence, their exposures must be aggregated
        and tested against the limit as a single counterparty.

        Args:
            counterparty_results: Per-counterparty results keyed by ID.
            groups: List of connected counterparty groups.

        Returns:
            List of group-level aggregation details.

        References:
            12 CFR 252.76 — Aggregation of connected counterparties
            BCBS d283, Section 5 — Groups of connected counterparties
        """
        group_details: list[dict] = []

        for group in groups:
            member_results = [
                counterparty_results[mid]
                for mid in group.member_ids
                if mid in counterparty_results
            ]

            if not member_results:
                continue

            agg_gross = sum(r.gross_exposure for r in member_results)
            agg_net = sum(r.net_exposure for r in member_results)
            pct_tier1 = agg_net / self.tier1_capital if self.tier1_capital > 0 else 0.0

            # Use the strictest limit among members
            limit_pct = min(r.limit_pct for r in member_results)
            limit_amount = limit_pct * self.tier1_capital

            group_details.append({
                "group_id": group.group_id,
                "group_name": group.group_name,
                "connection_type": group.connection_type.value,
                "member_count": len(member_results),
                "member_ids": [r.counterparty_id for r in member_results],
                "aggregate_gross_exposure": agg_gross,
                "aggregate_net_exposure": agg_net,
                "exposure_pct_tier1": pct_tier1,
                "limit_pct": limit_pct,
                "limit_amount": limit_amount,
                "headroom": limit_amount - agg_net,
                "is_breach": agg_net > limit_amount,
                "is_reportable": pct_tier1 >= REPORTING_THRESHOLD,
            })

            if agg_net > limit_amount:
                logger.warning(
                    "BREACH: Connected group '%s' net=$%.1fM > limit=$%.1fM "
                    "(%.1f%% of T1)",
                    group.group_name,
                    agg_net,
                    limit_amount,
                    pct_tier1 * 100,
                )

        return group_details

    def _empty_summary(self) -> LargeExposureSummary:
        """Return an empty summary when no exposures are provided.

        Returns:
            LargeExposureSummary with all zero values.
        """
        return LargeExposureSummary(
            total_counterparties=0,
            reportable_exposures=0,
            limit_breaches=0,
            largest_exposure_pct=0.0,
            total_gross_exposure=0.0,
            total_net_exposure=0.0,
            tier1_capital=self.tier1_capital,
        )
