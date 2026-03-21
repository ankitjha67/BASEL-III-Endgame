"""Capital ratio calculator — CET1, Tier 1, Total Capital, SLR, and buffers.

Computes all key regulatory capital adequacy ratios and buffer requirements
for a Category I US G-SIB under the Basel III Endgame 2026 framework.

Ratios computed:
- CET1 ratio = CET1 / Total RWA
- Tier 1 ratio = Tier 1 / Total RWA
- Total capital ratio = Total Capital / Total RWA
- Supplementary Leverage Ratio (SLR) = Tier 1 / Total Leverage Exposure
- Capital Conservation Buffer (CCB) distance
- Countercyclical Capital Buffer (CCyB)
- G-SIB surcharge
- Combined buffer requirement
- Surplus/deficit analysis vs. all regulatory thresholds
- Prompt Corrective Action (PCA) classification

All amounts in USD millions ($M). Ratios as decimals (e.g., 0.12 = 12%).

References:
- 12 CFR 217.10: Minimum capital ratios
- 12 CFR 217.11: Capital buffers
- 12 CFR 6.4: Prompt Corrective Action thresholds
- ERBA NPR pp. 34-68: Capital adequacy framework
- FR Y-9C Schedule HC-R Part II: Capital adequacy
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.capital.capital_params import (
    CCB_RATE,
    CCYB_DEFAULT_RATE,
    CET1_MINIMUM_RATIO,
    ESLR_TOTAL_CATEGORY_I,
    GSIB_BASE_SCORE_THRESHOLD,
    PCA_ADEQUATELY_CAPITALIZED,
    PCA_WELL_CAPITALIZED,
    SCB_FLOOR,
    SLR_ENHANCED_BUFFER,
    SLR_MINIMUM,
    TIER1_MINIMUM_RATIO,
    TOTAL_CAPITAL_MINIMUM_RATIO,
    TYPICAL_GSIB_CET1_RATIO_RANGE,
    TYPICAL_GSIB_SLR_RANGE,
    TYPICAL_GSIB_TOTAL_CAPITAL_RANGE,
    lookup_gsib_surcharge,
)
from src.capital.capital_components import TotalCapitalResult, LeverageExposureInputs
from src.capital.rwa_aggregator import RWABreakdown


# =========================================================================
#  Enumerations
# =========================================================================

class PCACategory(Enum):
    """Prompt Corrective Action categories per 12 CFR 6.4.

    Reference: 12 CFR 6.4(b), ERBA NPR p. 38.
    """
    WELL_CAPITALIZED = "WELL_CAPITALIZED"
    ADEQUATELY_CAPITALIZED = "ADEQUATELY_CAPITALIZED"
    UNDERCAPITALIZED = "UNDERCAPITALIZED"
    SIGNIFICANTLY_UNDERCAPITALIZED = "SIGNIFICANTLY_UNDERCAPITALIZED"
    CRITICALLY_UNDERCAPITALIZED = "CRITICALLY_UNDERCAPITALIZED"


class BufferZone(Enum):
    """Capital buffer zone classification.

    Determines dividend/distribution restrictions.
    Reference: 12 CFR 217.11(a)(4)(iv).
    """
    ABOVE_BUFFER = "ABOVE_BUFFER"
    QUARTILE_4 = "QUARTILE_4"  # 75-100% of buffer, max 60% payout
    QUARTILE_3 = "QUARTILE_3"  # 50-75% of buffer, max 40% payout
    QUARTILE_2 = "QUARTILE_2"  # 25-50% of buffer, max 20% payout
    QUARTILE_1 = "QUARTILE_1"  # 0-25% of buffer, max 0% payout
    BELOW_MINIMUM = "BELOW_MINIMUM"


# =========================================================================
#  Result Models
# =========================================================================

class CapitalRatios(BaseModel):
    """Core capital adequacy ratios.

    Reference: FR Y-9C Schedule HC-R Part II.
    """
    cet1_ratio: float = Field(
        description="CET1 / Total RWA. Minimum: 4.5%."
    )
    tier1_ratio: float = Field(
        description="Tier 1 / Total RWA. Minimum: 6.0%."
    )
    total_capital_ratio: float = Field(
        description="Total Capital / Total RWA. Minimum: 8.0%."
    )
    leverage_ratio: float = Field(
        default=0.0,
        description="Tier 1 / Total Leverage Exposure (SLR). Minimum: 3%."
    )


class BufferRequirements(BaseModel):
    """Capital buffer requirements and surplus/deficit analysis.

    Reference: 12 CFR 217.11, ERBA NPR pp. 43-58.
    """
    # Buffer components
    capital_conservation_buffer: float = Field(
        description="CCB: 2.5% (or SCB if applicable, floor 2.5%)"
    )
    countercyclical_buffer: float = Field(
        description="CCyB: 0-2.5%, currently 0%"
    )
    gsib_surcharge: float = Field(
        description="G-SIB surcharge based on systemic importance score"
    )
    stress_capital_buffer: float = Field(
        default=0.025,
        description="SCB: replaces CCB for Category I-IV firms (floor 2.5%)"
    )

    # Combined buffer
    combined_buffer_requirement: float = Field(
        description="CCB (or SCB) + CCyB + G-SIB surcharge"
    )

    # Effective minimums (minimum + buffers)
    effective_cet1_minimum: float = Field(
        description="CET1 minimum + combined buffer requirement"
    )
    effective_tier1_minimum: float = Field(
        description="Tier 1 minimum + combined buffer requirement * (T1_min / CET1_min)"
    )
    effective_total_capital_minimum: float = Field(
        description="Total capital minimum + combined buffer requirement"
    )


class CapitalSurplusDeficit(BaseModel):
    """Capital surplus/deficit analysis against all regulatory thresholds.

    Positive values indicate surplus (capital above requirement).
    Negative values indicate deficit (capital shortfall).

    All amounts in $M.
    Reference: 12 CFR 217.10-11.
    """
    # Surplus above minimums (in $M)
    cet1_surplus_over_minimum: float = Field(
        description="CET1 - (4.5% * RWA)"
    )
    tier1_surplus_over_minimum: float = Field(
        description="Tier 1 - (6.0% * RWA)"
    )
    total_capital_surplus_over_minimum: float = Field(
        description="Total Capital - (8.0% * RWA)"
    )
    slr_surplus_over_minimum: float = Field(
        default=0.0,
        description="Tier 1 - (3% * TLE)"
    )

    # Surplus above minimums + buffers (in $M)
    cet1_surplus_over_buffer: float = Field(
        description="CET1 - (effective CET1 minimum * RWA)"
    )

    # Surplus in ratio terms
    cet1_ratio_surplus: float = Field(
        description="Actual CET1 ratio - effective minimum ratio"
    )
    tier1_ratio_surplus: float = Field(
        description="Actual Tier 1 ratio - minimum ratio"
    )
    total_capital_ratio_surplus: float = Field(
        description="Actual Total Capital ratio - minimum ratio"
    )
    slr_surplus: float = Field(
        default=0.0,
        description="Actual SLR - minimum SLR"
    )

    # Enhanced SLR (for Category I G-SIBs)
    eslr_surplus: float = Field(
        default=0.0,
        description="Actual SLR - 5% eSLR requirement"
    )

    # Distribution restrictions
    buffer_zone: BufferZone = Field(
        description="Current buffer zone for distribution restrictions"
    )
    maximum_payout_ratio: float = Field(
        description="Maximum capital distribution payout ratio (0.0-1.0)"
    )


class PCAClassification(BaseModel):
    """Prompt Corrective Action classification.

    Reference: 12 CFR 6.4.
    """
    category: PCACategory
    binding_ratio: str = Field(
        description="The ratio that determines the PCA category"
    )
    binding_value: float = Field(
        description="Value of the binding ratio"
    )
    description: str = Field(default="")


class CapitalAdequacyResult(BaseModel):
    """Complete capital adequacy assessment.

    Combines ratios, buffers, surplus/deficit, PCA classification,
    and the enhanced SLR for a Category I G-SIB.

    Reference: FR Y-9C Schedule HC-R Part II.
    """
    # Core ratios
    ratios: CapitalRatios

    # Buffer requirements
    buffers: BufferRequirements

    # Surplus/deficit
    surplus_deficit: CapitalSurplusDeficit

    # PCA classification
    pca: PCAClassification

    # Input amounts for reference
    cet1_capital: float = Field(description="CET1 capital in $M")
    tier1_capital: float = Field(description="Tier 1 capital in $M")
    total_capital: float = Field(description="Total capital in $M")
    total_rwa: float = Field(description="Total RWA in $M")
    total_leverage_exposure: float = Field(
        default=0.0, description="Total leverage exposure in $M"
    )

    # Validation flags
    meets_minimum_requirements: bool = Field(
        description="True if all minimum ratios are met"
    )
    meets_buffer_requirements: bool = Field(
        description="True if all buffer requirements are met"
    )
    is_well_capitalized: bool = Field(
        description="True if meets PCA well-capitalized thresholds"
    )


# =========================================================================
#  Calculation Functions
# =========================================================================

def compute_capital_ratios(
    cet1_capital: float,
    tier1_capital: float,
    total_capital: float,
    total_rwa: float,
    total_leverage_exposure: float = 0.0,
) -> CapitalRatios:
    """Compute core capital adequacy ratios.

    CET1 ratio = CET1 / RWA
    Tier 1 ratio = Tier 1 / RWA
    Total capital ratio = Total Capital / RWA
    Leverage ratio (SLR) = Tier 1 / Total Leverage Exposure

    Args:
        cet1_capital: CET1 capital in $M.
        tier1_capital: Tier 1 capital in $M.
        total_capital: Total capital in $M.
        total_rwa: Total risk-weighted assets in $M.
        total_leverage_exposure: Total leverage exposure in $M (for SLR).

    Returns:
        CapitalRatios with all core ratios.

    Raises:
        ValueError: If total_rwa is zero or negative.

    Reference: 12 CFR 217.10(a), FR Y-9C Schedule HC-R Part II.
    """
    if total_rwa <= 0:
        raise ValueError(
            f"Total RWA must be positive, got {total_rwa}. "
            "Reference: 12 CFR 217.10(a)."
        )

    cet1_ratio = cet1_capital / total_rwa
    tier1_ratio = tier1_capital / total_rwa
    total_ratio = total_capital / total_rwa

    leverage_ratio = 0.0
    if total_leverage_exposure > 0:
        leverage_ratio = tier1_capital / total_leverage_exposure

    return CapitalRatios(
        cet1_ratio=cet1_ratio,
        tier1_ratio=tier1_ratio,
        total_capital_ratio=total_ratio,
        leverage_ratio=leverage_ratio,
    )


def compute_buffer_requirements(
    gsib_score: float = 0.0,
    ccyb_rate: float = CCYB_DEFAULT_RATE,
    scb_rate: Optional[float] = None,
) -> BufferRequirements:
    """Compute capital buffer requirements.

    Combined buffer = max(CCB, SCB) + CCyB + G-SIB surcharge

    For Category I-IV firms, the Stress Capital Buffer (SCB) replaces
    the static CCB. The SCB has a floor of 2.5%.

    Args:
        gsib_score: G-SIB systemic importance score (decimal).
        ccyb_rate: Countercyclical buffer rate (0-2.5%).
        scb_rate: Stress Capital Buffer rate. If None, uses CCB (2.5%).

    Returns:
        BufferRequirements with all components.

    Reference: 12 CFR 217.11(a), ERBA NPR pp. 43-58.
    """
    # G-SIB surcharge
    gsib_surcharge = lookup_gsib_surcharge(gsib_score)

    # Capital Conservation Buffer / Stress Capital Buffer
    if scb_rate is not None:
        effective_ccb = max(scb_rate, SCB_FLOOR)
    else:
        effective_ccb = CCB_RATE

    # Combined buffer
    combined = effective_ccb + ccyb_rate + gsib_surcharge

    # Effective minimums
    effective_cet1 = CET1_MINIMUM_RATIO + combined
    effective_tier1 = TIER1_MINIMUM_RATIO + combined
    effective_total = TOTAL_CAPITAL_MINIMUM_RATIO + combined

    return BufferRequirements(
        capital_conservation_buffer=effective_ccb,
        countercyclical_buffer=ccyb_rate,
        gsib_surcharge=gsib_surcharge,
        stress_capital_buffer=effective_ccb,
        combined_buffer_requirement=combined,
        effective_cet1_minimum=effective_cet1,
        effective_tier1_minimum=effective_tier1,
        effective_total_capital_minimum=effective_total,
    )


def classify_buffer_zone(
    cet1_ratio: float,
    cet1_minimum: float,
    combined_buffer: float,
) -> tuple[BufferZone, float]:
    """Classify the buffer zone and determine maximum payout ratio.

    The buffer framework divides the buffer into quartiles, each with
    different maximum payout ratios for capital distributions:
    - Above buffer: No restrictions
    - Q4 (75-100%): Max 60% payout
    - Q3 (50-75%): Max 40% payout
    - Q2 (25-50%): Max 20% payout
    - Q1 (0-25%): Max 0% payout
    - Below minimum: Capital distributions prohibited

    Args:
        cet1_ratio: Actual CET1 ratio.
        cet1_minimum: CET1 minimum ratio (4.5%).
        combined_buffer: Combined buffer requirement.

    Returns:
        Tuple of (BufferZone, maximum_payout_ratio).

    Reference: 12 CFR 217.11(a)(4)(iv), Table 1.
    """
    if cet1_ratio < cet1_minimum:
        return BufferZone.BELOW_MINIMUM, 0.0

    buffer_available = cet1_ratio - cet1_minimum

    if combined_buffer <= 0:
        return BufferZone.ABOVE_BUFFER, 1.0

    buffer_utilization = buffer_available / combined_buffer

    if buffer_utilization >= 1.0:
        return BufferZone.ABOVE_BUFFER, 1.0
    elif buffer_utilization >= 0.75:
        return BufferZone.QUARTILE_4, 0.6
    elif buffer_utilization >= 0.50:
        return BufferZone.QUARTILE_3, 0.4
    elif buffer_utilization >= 0.25:
        return BufferZone.QUARTILE_2, 0.2
    else:
        return BufferZone.QUARTILE_1, 0.0


def compute_surplus_deficit(
    ratios: CapitalRatios,
    buffers: BufferRequirements,
    cet1_capital: float,
    tier1_capital: float,
    total_capital: float,
    total_rwa: float,
    total_leverage_exposure: float = 0.0,
) -> CapitalSurplusDeficit:
    """Compute capital surplus/deficit against all regulatory thresholds.

    Calculates how much capital exceeds (surplus) or falls short of
    (deficit) each regulatory requirement, both in dollar terms and
    ratio terms.

    Args:
        ratios: Computed capital ratios.
        buffers: Buffer requirements.
        cet1_capital: CET1 capital in $M.
        tier1_capital: Tier 1 capital in $M.
        total_capital: Total capital in $M.
        total_rwa: Total RWA in $M.
        total_leverage_exposure: Total leverage exposure in $M.

    Returns:
        CapitalSurplusDeficit with all surplus/deficit amounts.

    Reference: 12 CFR 217.10-11.
    """
    # Dollar surplus over minimums
    cet1_surplus_min = cet1_capital - (CET1_MINIMUM_RATIO * total_rwa)
    tier1_surplus_min = tier1_capital - (TIER1_MINIMUM_RATIO * total_rwa)
    total_surplus_min = total_capital - (TOTAL_CAPITAL_MINIMUM_RATIO * total_rwa)

    # SLR surplus
    slr_surplus_min = 0.0
    slr_ratio_surplus = 0.0
    eslr_surplus = 0.0
    if total_leverage_exposure > 0:
        slr_surplus_min = tier1_capital - (SLR_MINIMUM * total_leverage_exposure)
        slr_ratio_surplus = ratios.leverage_ratio - SLR_MINIMUM
        eslr_surplus = ratios.leverage_ratio - ESLR_TOTAL_CATEGORY_I

    # Dollar surplus over effective minimums (including buffers)
    cet1_surplus_buffer = cet1_capital - (
        buffers.effective_cet1_minimum * total_rwa
    )

    # Ratio surplus
    cet1_ratio_surplus = ratios.cet1_ratio - buffers.effective_cet1_minimum
    tier1_ratio_surplus = ratios.tier1_ratio - TIER1_MINIMUM_RATIO
    total_ratio_surplus = ratios.total_capital_ratio - TOTAL_CAPITAL_MINIMUM_RATIO

    # Buffer zone classification
    buffer_zone, max_payout = classify_buffer_zone(
        ratios.cet1_ratio,
        CET1_MINIMUM_RATIO,
        buffers.combined_buffer_requirement,
    )

    return CapitalSurplusDeficit(
        cet1_surplus_over_minimum=cet1_surplus_min,
        tier1_surplus_over_minimum=tier1_surplus_min,
        total_capital_surplus_over_minimum=total_surplus_min,
        slr_surplus_over_minimum=slr_surplus_min,
        cet1_surplus_over_buffer=cet1_surplus_buffer,
        cet1_ratio_surplus=cet1_ratio_surplus,
        tier1_ratio_surplus=tier1_ratio_surplus,
        total_capital_ratio_surplus=total_ratio_surplus,
        slr_surplus=slr_ratio_surplus,
        eslr_surplus=eslr_surplus,
        buffer_zone=buffer_zone,
        maximum_payout_ratio=max_payout,
    )


def classify_pca(
    ratios: CapitalRatios,
) -> PCAClassification:
    """Classify bank under Prompt Corrective Action framework.

    PCA categories (12 CFR 6.4):
    - Well-capitalized: CET1 >= 6.5%, T1 >= 8%, Total >= 10%, Leverage >= 5%
    - Adequately capitalized: CET1 >= 4.5%, T1 >= 6%, Total >= 8%, Lev >= 4%
    - Undercapitalized: fails any adequately-capitalized threshold
    - Significantly undercapitalized: CET1 < 3%, T1 < 4%, Total < 6%
    - Critically undercapitalized: tangible equity / total assets < 2%

    Args:
        ratios: Computed capital ratios.

    Returns:
        PCAClassification with category and binding ratio.

    Reference: 12 CFR 6.4(b).
    """
    wc = PCA_WELL_CAPITALIZED
    ac = PCA_ADEQUATELY_CAPITALIZED

    # Check well-capitalized
    meets_wc = (
        ratios.cet1_ratio >= wc.cet1_ratio
        and ratios.tier1_ratio >= wc.tier1_ratio
        and ratios.total_capital_ratio >= wc.total_capital_ratio
        and (ratios.leverage_ratio >= wc.leverage_ratio or ratios.leverage_ratio == 0)
    )

    if meets_wc:
        # Find the tightest ratio for binding constraint
        margins = {
            "CET1": ratios.cet1_ratio - wc.cet1_ratio,
            "Tier 1": ratios.tier1_ratio - wc.tier1_ratio,
            "Total Capital": ratios.total_capital_ratio - wc.total_capital_ratio,
        }
        if ratios.leverage_ratio > 0:
            margins["SLR"] = ratios.leverage_ratio - wc.leverage_ratio

        binding = min(margins, key=margins.get)  # type: ignore[arg-type]
        binding_value = {
            "CET1": ratios.cet1_ratio,
            "Tier 1": ratios.tier1_ratio,
            "Total Capital": ratios.total_capital_ratio,
            "SLR": ratios.leverage_ratio,
        }.get(binding, ratios.cet1_ratio)

        return PCAClassification(
            category=PCACategory.WELL_CAPITALIZED,
            binding_ratio=binding,
            binding_value=binding_value,
            description=f"Well-capitalized: all ratios above PCA thresholds. "
                        f"Binding constraint: {binding}.",
        )

    # Check adequately capitalized
    meets_ac = (
        ratios.cet1_ratio >= ac.cet1_ratio
        and ratios.tier1_ratio >= ac.tier1_ratio
        and ratios.total_capital_ratio >= ac.total_capital_ratio
    )

    if meets_ac:
        return PCAClassification(
            category=PCACategory.ADEQUATELY_CAPITALIZED,
            binding_ratio="Multiple",
            binding_value=min(ratios.cet1_ratio, ratios.tier1_ratio),
            description="Adequately capitalized but not well-capitalized.",
        )

    # Significantly undercapitalized thresholds
    sig_under = (
        ratios.cet1_ratio < 0.03
        or ratios.tier1_ratio < 0.04
        or ratios.total_capital_ratio < 0.06
    )

    if sig_under:
        return PCAClassification(
            category=PCACategory.SIGNIFICANTLY_UNDERCAPITALIZED,
            binding_ratio="Multiple",
            binding_value=min(
                ratios.cet1_ratio, ratios.tier1_ratio, ratios.total_capital_ratio
            ),
            description="Significantly undercapitalized: capital ratios "
                        "critically below regulatory minimums.",
        )

    return PCAClassification(
        category=PCACategory.UNDERCAPITALIZED,
        binding_ratio="Multiple",
        binding_value=min(
            ratios.cet1_ratio, ratios.tier1_ratio, ratios.total_capital_ratio
        ),
        description="Undercapitalized: fails to meet one or more "
                    "adequately-capitalized thresholds.",
    )


def compute_capital_adequacy(
    capital_result: TotalCapitalResult,
    rwa_breakdown: RWABreakdown,
    leverage_inputs: Optional[LeverageExposureInputs] = None,
    gsib_score: float = 0.0,
    ccyb_rate: float = CCYB_DEFAULT_RATE,
    scb_rate: Optional[float] = None,
) -> CapitalAdequacyResult:
    """Compute complete capital adequacy assessment.

    This is the master function that brings together capital components,
    RWA, and regulatory requirements to produce a comprehensive capital
    adequacy assessment including ratios, buffers, surplus/deficit, and
    PCA classification.

    Args:
        capital_result: Total capital from capital_components module.
        rwa_breakdown: Aggregated RWA from rwa_aggregator module.
        leverage_inputs: Optional leverage exposure for SLR computation.
        gsib_score: G-SIB systemic importance score (decimal).
        ccyb_rate: Countercyclical buffer rate.
        scb_rate: Stress Capital Buffer rate (None = use CCB 2.5%).

    Returns:
        CapitalAdequacyResult with complete assessment.

    Reference: FR Y-9C Schedule HC-R, 12 CFR 217.10-11.
    """
    from src.capital.capital_components import compute_total_leverage_exposure

    cet1 = capital_result.cet1.net_cet1
    tier1 = capital_result.tier1_capital
    total = capital_result.total_capital
    total_rwa = rwa_breakdown.total_rwa

    # Leverage exposure
    tle = 0.0
    if leverage_inputs is not None:
        tle = compute_total_leverage_exposure(leverage_inputs)

    # Ratios
    ratios = compute_capital_ratios(cet1, tier1, total, total_rwa, tle)

    # Buffers
    buffers = compute_buffer_requirements(gsib_score, ccyb_rate, scb_rate)

    # Surplus/deficit
    surplus_deficit = compute_surplus_deficit(
        ratios, buffers, cet1, tier1, total, total_rwa, tle
    )

    # PCA classification
    pca = classify_pca(ratios)

    # Validation flags
    meets_minimums = (
        ratios.cet1_ratio >= CET1_MINIMUM_RATIO
        and ratios.tier1_ratio >= TIER1_MINIMUM_RATIO
        and ratios.total_capital_ratio >= TOTAL_CAPITAL_MINIMUM_RATIO
    )
    if tle > 0:
        meets_minimums = meets_minimums and ratios.leverage_ratio >= SLR_MINIMUM

    meets_buffers = surplus_deficit.cet1_surplus_over_buffer >= 0

    is_well_capitalized = pca.category == PCACategory.WELL_CAPITALIZED

    return CapitalAdequacyResult(
        ratios=ratios,
        buffers=buffers,
        surplus_deficit=surplus_deficit,
        pca=pca,
        cet1_capital=cet1,
        tier1_capital=tier1,
        total_capital=total,
        total_rwa=total_rwa,
        total_leverage_exposure=tle,
        meets_minimum_requirements=meets_minimums,
        meets_buffer_requirements=meets_buffers,
        is_well_capitalized=is_well_capitalized,
    )


# =========================================================================
#  Stress Testing Support
# =========================================================================

class StressScenarioImpact(BaseModel):
    """Impact of a stress scenario on capital ratios.

    Used for FR Y-14A/Q stress testing.
    Reference: 12 CFR 252.54-56.
    """
    scenario_name: str = Field(description="Stress scenario name")
    pre_stress_cet1_ratio: float = Field(description="CET1 ratio before stress")
    post_stress_cet1_ratio: float = Field(description="CET1 ratio after stress")
    cet1_ratio_change: float = Field(description="Change in CET1 ratio")
    pre_stress_tier1_ratio: float = Field(description="Tier 1 ratio before stress")
    post_stress_tier1_ratio: float = Field(description="Tier 1 ratio after stress")
    tier1_ratio_change: float = Field(description="Change in Tier 1 ratio")
    pre_stress_total_ratio: float = Field(description="Total ratio before stress")
    post_stress_total_ratio: float = Field(description="Total ratio after stress")
    total_ratio_change: float = Field(description="Change in Total ratio")
    pre_stress_slr: float = Field(
        default=0.0, description="SLR before stress"
    )
    post_stress_slr: float = Field(
        default=0.0, description="SLR after stress"
    )
    slr_change: float = Field(default=0.0, description="Change in SLR")
    breaches_minimum: bool = Field(
        description="Whether any post-stress ratio breaches minimum"
    )
    breaches_buffer: bool = Field(
        description="Whether post-stress CET1 breaches buffer requirement"
    )


def compute_stress_impact(
    base_adequacy: CapitalAdequacyResult,
    stressed_adequacy: CapitalAdequacyResult,
    scenario_name: str = "Severely Adverse",
) -> StressScenarioImpact:
    """Compute the impact of a stress scenario on capital ratios.

    Compares pre-stress and post-stress capital adequacy results
    to determine ratio changes and minimum/buffer breaches.

    Args:
        base_adequacy: Pre-stress capital adequacy.
        stressed_adequacy: Post-stress capital adequacy.
        scenario_name: Name of the stress scenario.

    Returns:
        StressScenarioImpact with ratio changes and breach flags.

    Reference: FR Y-14A/Q, 12 CFR 252.54-56.
    """
    br = base_adequacy.ratios
    sr = stressed_adequacy.ratios

    return StressScenarioImpact(
        scenario_name=scenario_name,
        pre_stress_cet1_ratio=br.cet1_ratio,
        post_stress_cet1_ratio=sr.cet1_ratio,
        cet1_ratio_change=sr.cet1_ratio - br.cet1_ratio,
        pre_stress_tier1_ratio=br.tier1_ratio,
        post_stress_tier1_ratio=sr.tier1_ratio,
        tier1_ratio_change=sr.tier1_ratio - br.tier1_ratio,
        pre_stress_total_ratio=br.total_capital_ratio,
        post_stress_total_ratio=sr.total_capital_ratio,
        total_ratio_change=sr.total_capital_ratio - br.total_capital_ratio,
        pre_stress_slr=br.leverage_ratio,
        post_stress_slr=sr.leverage_ratio,
        slr_change=sr.leverage_ratio - br.leverage_ratio,
        breaches_minimum=not stressed_adequacy.meets_minimum_requirements,
        breaches_buffer=not stressed_adequacy.meets_buffer_requirements,
    )
