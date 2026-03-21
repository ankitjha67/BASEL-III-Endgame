"""Capital buffer stack calculator — CET1 buffers, MDA triggers, distributions.

Implements the full capital buffer stack calculation for a Category I US G-SIB
under the Basel III Endgame 2026 framework:
- CET1 minimum (4.5%)
- Capital Conservation Buffer / Stress Capital Buffer (2.5% floor)
- Countercyclical Capital Buffer (0-2.5%)
- G-SIB surcharge (1.0-4.5%)
- Combined buffer requirement
- Maximum Distributable Amount (MDA) triggers
- Distribution constraints by buffer zone quartile

All amounts in USD millions ($M). Ratios as decimals (e.g., 0.12 = 12%).

References:
- 12 CFR 217.10: Minimum capital ratios
- 12 CFR 217.11: Capital buffer requirements
- 12 CFR 217.11(a)(4)(iv): MDA restrictions
- ERBA NPR pp. 43-58: Capital buffers
- G-SIB NPR pp. 12-28: G-SIB surcharge
- BCBS d309: Pillar 2 supervisory review
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.pillar2.pillar2_params import (
    CCB_RATE,
    CCYB_DEFAULT,
    CCYB_MAXIMUM,
    CCYB_MINIMUM,
    CET1_MINIMUM,
    ESLR_TOTAL,
    GSIB_SURCHARGE_DEFAULT,
    GSIB_SURCHARGE_MAXIMUM,
    GSIB_SURCHARGE_MINIMUM,
    MANAGEMENT_BUFFER_DEFAULT,
    CAPITAL_PLANNING_BUFFER_DEFAULT,
    MDA_QUARTILE_PAYOUTS,
    MDARestrictionQuartile,
    SCB_DEFAULT,
    SCB_FLOOR,
    SLR_MINIMUM,
    TIER1_MINIMUM,
    TOTAL_CAPITAL_MINIMUM,
    BufferType,
)


# =========================================================================
#  Data Models
# =========================================================================

class BufferComponent(BaseModel):
    """A single component of the capital buffer stack.

    Reference: 12 CFR 217.11, ERBA NPR pp. 43-58.
    """
    buffer_type: BufferType
    rate: float = Field(description="Buffer rate as decimal (e.g., 0.025 = 2.5%)")
    amount: float = Field(
        default=0.0,
        description="Buffer amount in $M = rate * RWA"
    )
    description: str = Field(default="")
    regulatory_reference: str = Field(default="")
    is_cet1_only: bool = Field(
        default=True,
        description="True if buffer must be met with CET1 capital only"
    )


class BufferStackResult(BaseModel):
    """Complete capital buffer stack calculation result.

    Reference: 12 CFR 217.11, ERBA NPR pp. 43-58.
    """
    # Individual buffer components
    components: list[BufferComponent] = Field(default_factory=list)

    # Combined regulatory buffer
    ccb_or_scb_rate: float = Field(
        description="Effective CCB/SCB rate = max(CCB, SCB)"
    )
    ccyb_rate: float = Field(description="Countercyclical buffer rate")
    gsib_surcharge_rate: float = Field(description="G-SIB surcharge rate")
    combined_buffer_rate: float = Field(
        description="Combined buffer = CCB/SCB + CCyB + G-SIB"
    )
    combined_buffer_amount: float = Field(
        description="Combined buffer in $M = rate * RWA"
    )

    # Effective minimums (including buffers)
    effective_cet1_minimum: float = Field(
        description="CET1 min + combined buffer"
    )
    effective_tier1_minimum: float = Field(
        description="Tier 1 min + combined buffer"
    )
    effective_total_capital_minimum: float = Field(
        description="Total capital min + combined buffer"
    )

    # Internal targets (including Pillar 2A + management buffers)
    internal_cet1_target: float = Field(
        default=0.0,
        description="Internal CET1 target including P2A and management buffer"
    )
    internal_tier1_target: float = Field(
        default=0.0,
        description="Internal Tier 1 target"
    )
    internal_total_capital_target: float = Field(
        default=0.0,
        description="Internal total capital target"
    )

    # SLR requirements
    slr_minimum: float = Field(default=SLR_MINIMUM)
    eslr_requirement: float = Field(default=ESLR_TOTAL)


class MDAAnalysis(BaseModel):
    """Maximum Distributable Amount analysis.

    Determines capital distribution restrictions based on CET1 ratio
    position relative to the combined buffer requirement.

    Reference: 12 CFR 217.11(a)(4)(iv).
    """
    # Current position
    cet1_ratio: float = Field(description="Current CET1 ratio")
    cet1_minimum: float = Field(description="CET1 minimum (4.5%)")
    combined_buffer: float = Field(description="Combined buffer requirement")

    # Buffer utilization
    buffer_available: float = Field(
        description="CET1 ratio above minimum (available for buffers)"
    )
    buffer_utilization_pct: float = Field(
        description="Buffer utilization (0-100%): available / required"
    )

    # MDA determination
    quartile: MDARestrictionQuartile = Field(
        description="Buffer zone quartile"
    )
    maximum_payout_ratio: float = Field(
        description="Maximum payout ratio (0.0-1.0)"
    )

    # Dollar amounts
    total_rwa: float = Field(description="Total RWA in $M")
    cet1_capital: float = Field(description="CET1 capital in $M")
    mda_amount: float = Field(
        description="Maximum distributable amount in $M"
    )
    distributable_earnings: float = Field(
        default=0.0,
        description="Eligible distributable earnings in $M"
    )

    # Breach flags
    breaches_minimum: bool = Field(
        description="True if CET1 ratio < 4.5%"
    )
    breaches_buffer: bool = Field(
        description="True if CET1 ratio < effective minimum"
    )
    distributions_restricted: bool = Field(
        description="True if any distribution restrictions apply"
    )


class DistributionConstraint(BaseModel):
    """Capital distribution constraint analysis.

    Determines whether specific capital actions (dividends, buybacks,
    discretionary bonuses) are permitted under current buffer position.

    Reference: 12 CFR 217.11(a)(4), BCBS d309 Principle 7.
    """
    action_type: str = Field(description="Type of distribution action")
    proposed_amount: float = Field(description="Proposed distribution in $M")
    is_permitted: bool = Field(description="Whether the action is permitted")
    remaining_mda: float = Field(
        description="Remaining MDA after proposed action in $M"
    )
    post_action_cet1_ratio: float = Field(
        description="CET1 ratio after proposed action"
    )
    post_action_quartile: MDARestrictionQuartile = Field(
        description="Buffer zone after proposed action"
    )
    warning: str = Field(default="")


# =========================================================================
#  Calculation Functions
# =========================================================================

def compute_buffer_stack(
    total_rwa: float,
    gsib_surcharge: float = GSIB_SURCHARGE_DEFAULT,
    ccyb_rate: float = CCYB_DEFAULT,
    scb_rate: Optional[float] = None,
    pillar_2a_addon: float = 0.0,
    management_buffer: float = MANAGEMENT_BUFFER_DEFAULT,
    planning_buffer: float = CAPITAL_PLANNING_BUFFER_DEFAULT,
) -> BufferStackResult:
    """Compute the complete capital buffer stack.

    Buffer stack (CET1):
    1. CET1 minimum: 4.5%
    2. CCB or SCB: max(2.5%, SCB) — SCB replaces CCB for Cat I-IV
    3. CCyB: 0-2.5% (currently 0%)
    4. G-SIB surcharge: 1.0-4.5%
    5. Pillar 2A add-ons (institution-specific)
    6. Management buffer (internal)
    7. Capital planning buffer (internal)

    Args:
        total_rwa: Total risk-weighted assets in $M.
        gsib_surcharge: G-SIB surcharge rate (decimal).
        ccyb_rate: Countercyclical buffer rate (decimal).
        scb_rate: Stress Capital Buffer rate. If None, uses CCB 2.5%.
        pillar_2a_addon: Pillar 2A supervisory add-on rate.
        management_buffer: Internal management buffer rate.
        planning_buffer: Capital planning buffer rate.

    Returns:
        BufferStackResult with all buffer components and effective minimums.

    Raises:
        ValueError: If total_rwa is not positive or buffer rates are invalid.

    Reference: 12 CFR 217.10-11, ERBA NPR pp. 43-58.
    """
    if total_rwa <= 0:
        raise ValueError(
            f"Total RWA must be positive, got {total_rwa}. "
            "Reference: 12 CFR 217.10(a)."
        )

    if ccyb_rate < CCYB_MINIMUM or ccyb_rate > CCYB_MAXIMUM:
        raise ValueError(
            f"CCyB rate must be between {CCYB_MINIMUM} and {CCYB_MAXIMUM}, "
            f"got {ccyb_rate}. Reference: 12 CFR 217.11(b)."
        )

    # Effective CCB/SCB
    if scb_rate is not None:
        effective_ccb = max(scb_rate, SCB_FLOOR)
    else:
        effective_ccb = CCB_RATE

    # Combined regulatory buffer
    combined_buffer = effective_ccb + ccyb_rate + gsib_surcharge

    # Build component list
    components: list[BufferComponent] = [
        BufferComponent(
            buffer_type=BufferType.CET1_MINIMUM,
            rate=CET1_MINIMUM,
            amount=CET1_MINIMUM * total_rwa,
            description="CET1 minimum requirement",
            regulatory_reference="12 CFR 217.10(a)(1)",
        ),
        BufferComponent(
            buffer_type=BufferType.SCB if scb_rate is not None else BufferType.CCB,
            rate=effective_ccb,
            amount=effective_ccb * total_rwa,
            description=(
                f"Stress Capital Buffer (SCB floor {SCB_FLOOR*100:.1f}%)"
                if scb_rate is not None
                else "Capital Conservation Buffer"
            ),
            regulatory_reference=(
                "12 CFR 217.11(a)(2)(iv)"
                if scb_rate is not None
                else "12 CFR 217.11(a)(4)"
            ),
        ),
        BufferComponent(
            buffer_type=BufferType.CCYB,
            rate=ccyb_rate,
            amount=ccyb_rate * total_rwa,
            description="Countercyclical Capital Buffer",
            regulatory_reference="12 CFR 217.11(b)",
        ),
        BufferComponent(
            buffer_type=BufferType.GSIB_SURCHARGE,
            rate=gsib_surcharge,
            amount=gsib_surcharge * total_rwa,
            description="G-SIB capital surcharge",
            regulatory_reference="12 CFR 217.403",
        ),
    ]

    if pillar_2a_addon > 0:
        components.append(BufferComponent(
            buffer_type=BufferType.PILLAR_2A,
            rate=pillar_2a_addon,
            amount=pillar_2a_addon * total_rwa,
            description="Pillar 2A supervisory add-on",
            regulatory_reference="BCBS d309 Principle 1",
        ))

    if management_buffer > 0:
        components.append(BufferComponent(
            buffer_type=BufferType.MANAGEMENT_BUFFER,
            rate=management_buffer,
            amount=management_buffer * total_rwa,
            description="Internal management buffer",
            regulatory_reference="BCBS d309 Principle 7",
        ))

    if planning_buffer > 0:
        components.append(BufferComponent(
            buffer_type=BufferType.CAPITAL_PLANNING_BUFFER,
            rate=planning_buffer,
            amount=planning_buffer * total_rwa,
            description="Capital planning buffer",
            regulatory_reference="12 CFR 252.153",
        ))

    # Effective minimums
    effective_cet1 = CET1_MINIMUM + combined_buffer
    effective_tier1 = TIER1_MINIMUM + combined_buffer
    effective_total = TOTAL_CAPITAL_MINIMUM + combined_buffer

    # Internal targets
    internal_cet1 = effective_cet1 + pillar_2a_addon + management_buffer + planning_buffer
    internal_tier1 = effective_tier1 + pillar_2a_addon + management_buffer + planning_buffer
    internal_total = effective_total + pillar_2a_addon + management_buffer + planning_buffer

    return BufferStackResult(
        components=components,
        ccb_or_scb_rate=effective_ccb,
        ccyb_rate=ccyb_rate,
        gsib_surcharge_rate=gsib_surcharge,
        combined_buffer_rate=combined_buffer,
        combined_buffer_amount=combined_buffer * total_rwa,
        effective_cet1_minimum=effective_cet1,
        effective_tier1_minimum=effective_tier1,
        effective_total_capital_minimum=effective_total,
        internal_cet1_target=internal_cet1,
        internal_tier1_target=internal_tier1,
        internal_total_capital_target=internal_total,
        slr_minimum=SLR_MINIMUM,
        eslr_requirement=ESLR_TOTAL,
    )


def determine_mda_quartile(
    cet1_ratio: float,
    cet1_minimum: float = CET1_MINIMUM,
    combined_buffer: float = 0.0,
) -> tuple[MDARestrictionQuartile, float]:
    """Determine the MDA restriction quartile and maximum payout ratio.

    The combined buffer is divided into four quartiles. The CET1 ratio
    position within the buffer determines the maximum payout:

    - Above buffer (CET1 >= min + buffer): No restrictions (100%)
    - Q4 (75-100% of buffer): Max 60% payout
    - Q3 (50-75% of buffer): Max 40% payout
    - Q2 (25-50% of buffer): Max 20% payout
    - Q1 (0-25% of buffer): Max 0% payout
    - Below minimum (CET1 < 4.5%): Distributions prohibited

    Args:
        cet1_ratio: Current CET1 capital ratio.
        cet1_minimum: CET1 minimum ratio (4.5%).
        combined_buffer: Combined buffer requirement.

    Returns:
        Tuple of (MDARestrictionQuartile, maximum_payout_ratio).

    Reference: 12 CFR 217.11(a)(4)(iv), Table 1.
    """
    if cet1_ratio < cet1_minimum:
        return MDARestrictionQuartile.BELOW_MINIMUM, 0.0

    buffer_available = cet1_ratio - cet1_minimum

    if combined_buffer <= 0:
        return MDARestrictionQuartile.ABOVE_BUFFER, 1.0

    utilization = buffer_available / combined_buffer

    if utilization >= 1.0:
        return MDARestrictionQuartile.ABOVE_BUFFER, 1.0
    elif utilization >= 0.75:
        return MDARestrictionQuartile.QUARTILE_4, 0.6
    elif utilization >= 0.50:
        return MDARestrictionQuartile.QUARTILE_3, 0.4
    elif utilization >= 0.25:
        return MDARestrictionQuartile.QUARTILE_2, 0.2
    else:
        return MDARestrictionQuartile.QUARTILE_1, 0.0


def compute_mda_analysis(
    cet1_ratio: float,
    cet1_capital: float,
    total_rwa: float,
    combined_buffer: float,
    distributable_earnings: float = 0.0,
    cet1_minimum: float = CET1_MINIMUM,
) -> MDAAnalysis:
    """Compute Maximum Distributable Amount analysis.

    Determines distribution restrictions based on the CET1 ratio position
    relative to the combined buffer requirement.

    MDA = max_payout_ratio * eligible_distributable_earnings

    Args:
        cet1_ratio: Current CET1 ratio.
        cet1_capital: Current CET1 capital in $M.
        total_rwa: Total RWA in $M.
        combined_buffer: Combined buffer requirement (decimal).
        distributable_earnings: Eligible distributable earnings in $M.
        cet1_minimum: CET1 minimum ratio.

    Returns:
        MDAAnalysis with quartile, payout ratio, and dollar amounts.

    Reference: 12 CFR 217.11(a)(4)(iv).
    """
    quartile, max_payout = determine_mda_quartile(
        cet1_ratio, cet1_minimum, combined_buffer
    )

    buffer_available = max(0.0, cet1_ratio - cet1_minimum)
    buffer_utilization = 0.0
    if combined_buffer > 0:
        buffer_utilization = min(1.0, buffer_available / combined_buffer) * 100.0

    mda = max_payout * distributable_earnings
    effective_minimum = cet1_minimum + combined_buffer
    breaches_min = cet1_ratio < cet1_minimum
    breaches_buf = cet1_ratio < effective_minimum
    restricted = quartile != MDARestrictionQuartile.ABOVE_BUFFER

    return MDAAnalysis(
        cet1_ratio=cet1_ratio,
        cet1_minimum=cet1_minimum,
        combined_buffer=combined_buffer,
        buffer_available=buffer_available,
        buffer_utilization_pct=buffer_utilization,
        quartile=quartile,
        maximum_payout_ratio=max_payout,
        total_rwa=total_rwa,
        cet1_capital=cet1_capital,
        mda_amount=mda,
        distributable_earnings=distributable_earnings,
        breaches_minimum=breaches_min,
        breaches_buffer=breaches_buf,
        distributions_restricted=restricted,
    )


def evaluate_distribution(
    proposed_amount: float,
    action_type: str,
    cet1_capital: float,
    total_rwa: float,
    combined_buffer: float,
    distributable_earnings: float = 0.0,
    cet1_minimum: float = CET1_MINIMUM,
) -> DistributionConstraint:
    """Evaluate whether a proposed capital distribution is permitted.

    Checks the proposed action against MDA restrictions and determines
    whether it can proceed, and what the post-action capital position
    would be.

    Args:
        proposed_amount: Proposed distribution amount in $M.
        action_type: Type of distribution (e.g., "dividend", "buyback").
        cet1_capital: Current CET1 capital in $M.
        total_rwa: Total RWA in $M.
        combined_buffer: Combined buffer requirement (decimal).
        distributable_earnings: Eligible distributable earnings in $M.
        cet1_minimum: CET1 minimum ratio.

    Returns:
        DistributionConstraint with permit decision and post-action analysis.

    Reference: 12 CFR 217.11(a)(4), SR 15-18 Section IV.
    """
    if total_rwa <= 0:
        raise ValueError("Total RWA must be positive for distribution evaluation.")

    current_ratio = cet1_capital / total_rwa
    post_cet1 = cet1_capital - proposed_amount
    post_ratio = post_cet1 / total_rwa

    # Current MDA
    mda_analysis = compute_mda_analysis(
        cet1_ratio=current_ratio,
        cet1_capital=cet1_capital,
        total_rwa=total_rwa,
        combined_buffer=combined_buffer,
        distributable_earnings=distributable_earnings,
        cet1_minimum=cet1_minimum,
    )

    # Check permission
    is_permitted = (
        proposed_amount <= mda_analysis.mda_amount
        and post_ratio >= cet1_minimum
    )

    # Post-action quartile
    post_quartile, _ = determine_mda_quartile(
        post_ratio, cet1_minimum, combined_buffer
    )

    remaining_mda = max(0.0, mda_analysis.mda_amount - proposed_amount)

    warning = ""
    if not is_permitted:
        if proposed_amount > mda_analysis.mda_amount:
            warning = (
                f"Proposed {action_type} of ${proposed_amount:.1f}M exceeds "
                f"MDA of ${mda_analysis.mda_amount:.1f}M. "
                f"Current quartile: {mda_analysis.quartile.value}."
            )
        if post_ratio < cet1_minimum:
            warning += (
                f" Post-action CET1 ratio {post_ratio*100:.2f}% would breach "
                f"minimum {cet1_minimum*100:.1f}%."
            )
    elif post_quartile != mda_analysis.quartile:
        warning = (
            f"Distribution would move buffer zone from "
            f"{mda_analysis.quartile.value} to {post_quartile.value}."
        )

    return DistributionConstraint(
        action_type=action_type,
        proposed_amount=proposed_amount,
        is_permitted=is_permitted,
        remaining_mda=remaining_mda,
        post_action_cet1_ratio=post_ratio,
        post_action_quartile=post_quartile,
        warning=warning,
    )


def compute_buffer_distance(
    cet1_ratio: float,
    tier1_ratio: float,
    total_capital_ratio: float,
    leverage_ratio: float,
    buffer_stack: BufferStackResult,
) -> dict[str, float]:
    """Compute the distance (surplus/deficit) to each buffer threshold.

    Positive values indicate surplus above the threshold.
    Negative values indicate breach of the threshold.

    Args:
        cet1_ratio: Current CET1 ratio.
        tier1_ratio: Current Tier 1 ratio.
        total_capital_ratio: Current Total Capital ratio.
        leverage_ratio: Current SLR.
        buffer_stack: Computed buffer stack.

    Returns:
        Dictionary with distance to each threshold (in ratio terms).

    Reference: 12 CFR 217.10-11.
    """
    return {
        "cet1_vs_minimum": cet1_ratio - CET1_MINIMUM,
        "cet1_vs_buffer": cet1_ratio - buffer_stack.effective_cet1_minimum,
        "cet1_vs_internal_target": cet1_ratio - buffer_stack.internal_cet1_target,
        "tier1_vs_minimum": tier1_ratio - TIER1_MINIMUM,
        "tier1_vs_buffer": tier1_ratio - buffer_stack.effective_tier1_minimum,
        "total_vs_minimum": total_capital_ratio - TOTAL_CAPITAL_MINIMUM,
        "total_vs_buffer": total_capital_ratio - buffer_stack.effective_total_capital_minimum,
        "slr_vs_minimum": leverage_ratio - buffer_stack.slr_minimum,
        "eslr_vs_requirement": leverage_ratio - buffer_stack.eslr_requirement,
    }
