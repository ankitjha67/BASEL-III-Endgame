"""Pillar 2 — ICAAP and Supervisory Review regulatory parameters.

Defines all parameters for the Internal Capital Adequacy Assessment Process
(ICAAP), capital buffer stack, stress capital buffer, management buffer,
and Pillar 1+ add-on risk categories.

References:
- BCBS d309: "Pillar 2 (Supervisory Review Process)" (2006, updated 2019)
- BCBS d368: "Interest Rate Risk in the Banking Book" (April 2016)
- BCBS d400: "Pillar 3 Disclosure Requirements — Updated Framework" (2022)
- 12 CFR 217.11: Capital buffer requirements
- 12 CFR 252.153-155: Enhanced prudential standards — capital planning
- SR 15-18: Federal Reserve Supervisory Assessment of Capital Planning
- SR 15-19: Heightened Standards for Large Financial Institutions
- ERBA NPR pp. 34-58: Capital buffers and requirements

All monetary amounts in USD millions ($M) unless otherwise stated.
All ratios expressed as decimals (e.g., 0.025 = 2.5%).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =========================================================================
#  Capital Buffer Components
#  Reference: 12 CFR 217.11, ERBA NPR pp. 43-58
# =========================================================================

CET1_MINIMUM: float = 0.045
"""CET1 minimum: 4.5% of RWA per 12 CFR 217.10(a)(1)."""

TIER1_MINIMUM: float = 0.06
"""Tier 1 minimum: 6.0% of RWA per 12 CFR 217.10(a)(2)."""

TOTAL_CAPITAL_MINIMUM: float = 0.08
"""Total capital minimum: 8.0% of RWA per 12 CFR 217.10(a)(3)."""

CCB_RATE: float = 0.025
"""Capital Conservation Buffer: 2.5% of RWA, composed of CET1.
Reference: 12 CFR 217.11(a)(4)."""

CCYB_MINIMUM: float = 0.0
"""Countercyclical Capital Buffer minimum: 0%.
Reference: 12 CFR 217.11(b)."""

CCYB_MAXIMUM: float = 0.025
"""Countercyclical Capital Buffer maximum: 2.5%.
Reference: 12 CFR 217.11(b)(2)."""

CCYB_DEFAULT: float = 0.0
"""Current CCyB rate: 0% (as of March 2026, US CCyB not activated).
Reference: 12 CFR 217.11(b)."""

SCB_FLOOR: float = 0.025
"""Stress Capital Buffer floor: 2.5% of RWA.
The SCB replaces the static CCB for Category I-IV firms.
Reference: 12 CFR 217.11(a)(2)(iv)."""

SCB_DEFAULT: float = 0.025
"""Default SCB if no stress testing result: equals the CCB floor of 2.5%.
Reference: 12 CFR 217.11(a)(2)(iv)."""


# =========================================================================
#  G-SIB Surcharge Parameters (copied from capital_params for Pillar 2 use)
#  Reference: G-SIB NPR pp. 12-28, 12 CFR 217.403-404
# =========================================================================

GSIB_SURCHARGE_DEFAULT: float = 0.015
"""Default G-SIB surcharge for a typical large Category I G-SIB: 1.5%.
This is a placeholder — actual surcharge determined by G-SIB score.
Reference: 12 CFR 217.403."""

GSIB_SURCHARGE_MINIMUM: float = 0.010
"""Minimum G-SIB surcharge for banks designated as G-SIBs: 1.0%.
Reference: G-SIB NPR p. 18."""

GSIB_SURCHARGE_MAXIMUM: float = 0.045
"""Maximum observed G-SIB surcharge for US G-SIBs: 4.5%.
Reference: G-SIB NPR p. 22."""


# =========================================================================
#  Supplementary Leverage Ratio (SLR)
#  Reference: 12 CFR 217.10(a)(4)-(5), ERBA NPR pp. 59-68
# =========================================================================

SLR_MINIMUM: float = 0.03
"""SLR minimum: 3.0% for all banking organizations.
Reference: 12 CFR 217.10(a)(4)."""

SLR_ENHANCED_BUFFER: float = 0.02
"""Enhanced SLR buffer: 2.0% for Category I G-SIBs.
Reference: 12 CFR 217.11(d)(4)."""

ESLR_TOTAL: float = SLR_MINIMUM + SLR_ENHANCED_BUFFER
"""Total enhanced SLR: 5.0% for Category I G-SIBs.
Reference: 12 CFR 217.11(d)(4)."""


# =========================================================================
#  Pillar 1+ Risk Add-On Categories
#  Reference: BCBS d309, SR 15-18, SR 15-19
# =========================================================================

class Pillar2RiskCategory(Enum):
    """Pillar 2 risk categories requiring additional capital beyond Pillar 1.

    These are risks not fully captured by the Pillar 1 standardized framework.
    Reference: BCBS d309 Principle 1, SR 15-18 Section III.
    """
    CONCENTRATION_RISK = "CONCENTRATION_RISK"
    IRRBB = "IRRBB"
    PENSION_RISK = "PENSION_RISK"
    MODEL_RISK = "MODEL_RISK"
    STRATEGIC_RISK = "STRATEGIC_RISK"
    REPUTATION_RISK = "REPUTATION_RISK"
    LIQUIDITY_RISK = "LIQUIDITY_RISK"
    COUNTRY_RISK = "COUNTRY_RISK"
    RESIDUAL_RISK = "RESIDUAL_RISK"
    OTHER = "OTHER"


class BufferType(Enum):
    """Types of capital buffers in the buffer stack.

    Reference: 12 CFR 217.11, BCBS d309 Principle 7.
    """
    CET1_MINIMUM = "CET1_MINIMUM"
    CCB = "CCB"
    CCYB = "CCYB"
    GSIB_SURCHARGE = "GSIB_SURCHARGE"
    SCB = "SCB"
    PILLAR_2A = "PILLAR_2A"
    MANAGEMENT_BUFFER = "MANAGEMENT_BUFFER"
    CAPITAL_PLANNING_BUFFER = "CAPITAL_PLANNING_BUFFER"


class MDARestrictionQuartile(Enum):
    """Maximum Distributable Amount (MDA) restriction quartiles.

    Determines capital distribution restrictions based on buffer utilization.
    Reference: 12 CFR 217.11(a)(4)(iv), BCBS d309 para 145.
    """
    ABOVE_BUFFER = "ABOVE_BUFFER"       # No restrictions
    QUARTILE_4 = "QUARTILE_4"           # Max 60% payout
    QUARTILE_3 = "QUARTILE_3"           # Max 40% payout
    QUARTILE_2 = "QUARTILE_2"           # Max 20% payout
    QUARTILE_1 = "QUARTILE_1"           # Max 0% payout
    BELOW_MINIMUM = "BELOW_MINIMUM"     # Distributions prohibited


# =========================================================================
#  Pillar 2A Add-On Default Rates
#  Reference: BCBS d309 Principle 1, SR 15-18
# =========================================================================

@dataclass(frozen=True)
class Pillar2AAddOnRates:
    """Default add-on rates for Pillar 2A risk categories.

    These are expressed as percentages of RWA and represent typical
    supervisory add-ons for risks not captured by Pillar 1.

    Note: Actual add-ons are institution-specific and determined through
    the SREP (Supervisory Review and Evaluation Process). These defaults
    are calibrated for a large Category I G-SIB.

    Reference: BCBS d309 Principle 1, SR 15-18.
    """
    concentration_risk: float = 0.005
    """Concentration risk add-on: 50bp default.
    Single-name, sector, and geographic concentration.
    Reference: BCBS d309 Principle 1(d)."""

    irrbb: float = 0.01
    """IRRBB add-on: 100bp default.
    Interest rate risk in the banking book per BCBS d368.
    Reference: BCBS d368 Section 3."""

    pension_risk: float = 0.003
    """Pension risk add-on: 30bp default.
    Defined benefit pension obligation shortfall risk.
    Reference: SR 15-18 Section III.B."""

    model_risk: float = 0.005
    """Model risk add-on: 50bp default.
    Risk from model estimation and implementation errors.
    Reference: SR 11-7, SR 15-18 Section III.C."""

    strategic_risk: float = 0.002
    """Strategic risk add-on: 20bp default.
    Risk from adverse business decisions or poor strategy execution.
    Reference: SR 15-19."""

    reputation_risk: float = 0.002
    """Reputation risk add-on: 20bp default.
    Reputational damage leading to revenue decline.
    Reference: SR 15-19."""

    country_risk: float = 0.003
    """Country/transfer risk add-on: 30bp default.
    Cross-border exposure risk.
    Reference: BCBS d309 Principle 1(e)."""

    residual_risk: float = 0.002
    """Residual risk add-on: 20bp default.
    Risks not covered by other categories.
    Reference: BCBS d309 Principle 1(f)."""

    @property
    def total_add_on(self) -> float:
        """Total Pillar 2A add-on as percentage of RWA.

        Reference: BCBS d309 Principle 1.
        """
        return (
            self.concentration_risk
            + self.irrbb
            + self.pension_risk
            + self.model_risk
            + self.strategic_risk
            + self.reputation_risk
            + self.country_risk
            + self.residual_risk
        )


DEFAULT_PILLAR_2A_RATES = Pillar2AAddOnRates()
"""Default Pillar 2A add-on rates for a Category I G-SIB.
Total default add-on: ~3.2% of RWA."""


# =========================================================================
#  Management and Capital Planning Buffers
#  Reference: SR 15-18, BCBS d309 Principle 7
# =========================================================================

MANAGEMENT_BUFFER_DEFAULT: float = 0.01
"""Management buffer: 100bp default.
Internal buffer maintained above regulatory minimums for operational
flexibility and unexpected shocks.
Reference: BCBS d309 Principle 7, SR 15-18 Section IV."""

CAPITAL_PLANNING_BUFFER_DEFAULT: float = 0.005
"""Capital planning buffer: 50bp default.
Buffer for planned capital actions (dividends, buybacks, growth).
Reference: SR 15-18 Section IV, 12 CFR 252.153."""

CAPITAL_PLANNING_HORIZON_YEARS: int = 3
"""Capital planning horizon: 3 years.
Reference: 12 CFR 252.153(e)(2), SR 15-18 Section II."""


# =========================================================================
#  MDA Restriction Schedule
#  Reference: 12 CFR 217.11(a)(4)(iv)
# =========================================================================

MDA_QUARTILE_PAYOUTS: dict[MDARestrictionQuartile, float] = {
    MDARestrictionQuartile.ABOVE_BUFFER: 1.0,
    MDARestrictionQuartile.QUARTILE_4: 0.6,
    MDARestrictionQuartile.QUARTILE_3: 0.4,
    MDARestrictionQuartile.QUARTILE_2: 0.2,
    MDARestrictionQuartile.QUARTILE_1: 0.0,
    MDARestrictionQuartile.BELOW_MINIMUM: 0.0,
}
"""Maximum payout ratios by buffer zone quartile.
Reference: 12 CFR 217.11(a)(4)(iv), Table 1."""


# =========================================================================
#  IRRBB Parameters (High-Level — detailed params in irrbb_params.py)
#  Reference: BCBS d368
# =========================================================================

IRRBB_MATERIALITY_THRESHOLD: float = 0.15
"""IRRBB materiality: EVE decline > 15% of Tier 1 triggers supervisory concern.
Reference: BCBS d368 Principle 5."""

IRRBB_NII_MATERIALITY_THRESHOLD: float = 0.05
"""NII materiality: NII decline > 5% of Tier 1 triggers supervisory concern.
Reference: BCBS d368 Principle 5."""

IRRBB_OUTLIER_THRESHOLD_EVE: float = 0.15
"""Outlier test: EVE change > 15% of Tier 1 capital.
Reference: BCBS d368 Principle 7 (outlier test)."""


# =========================================================================
#  Stress Testing Parameters
#  Reference: 12 CFR 252.54-56, SR 12-7
# =========================================================================

class StressScenarioType(Enum):
    """Stress scenario types for CCAR/DFAST.

    Reference: 12 CFR 252.54, SR 12-7.
    """
    BASELINE = "BASELINE"
    ADVERSE = "ADVERSE"
    SEVERELY_ADVERSE = "SEVERELY_ADVERSE"
    EXPLORATORY = "EXPLORATORY"


@dataclass(frozen=True)
class StressTestParameters:
    """Parameters for stress testing capital adequacy.

    Reference: 12 CFR 252.54-56.
    """
    planning_horizon_quarters: int = 9
    """DFAST/CCAR planning horizon: 9 quarters.
    Reference: 12 CFR 252.54(b)(1)."""

    pre_provision_net_revenue_floor_pct: float = 0.0
    """PPNR floor: 0% (can be negative under stress).
    Reference: 12 CFR 252.56(b)."""

    cet1_minimum_throughout: float = 0.045
    """CET1 must stay above 4.5% throughout the planning horizon.
    Reference: 12 CFR 252.56(b)(1)."""

    tier1_minimum_throughout: float = 0.06
    """Tier 1 must stay above 6.0% throughout the planning horizon.
    Reference: 12 CFR 252.56(b)(2)."""

    total_capital_minimum_throughout: float = 0.08
    """Total capital must stay above 8.0% throughout the planning horizon.
    Reference: 12 CFR 252.56(b)(3)."""

    slr_minimum_throughout: float = 0.03
    """SLR must stay above 3.0% throughout the planning horizon.
    Reference: 12 CFR 252.56(b)(4)."""


DEFAULT_STRESS_TEST_PARAMS = StressTestParameters()
"""Default stress test parameters per 12 CFR 252.54-56."""


# =========================================================================
#  Well-Capitalized & PCA Thresholds (for Pillar 2 reference)
#  Reference: 12 CFR 6.4, 12 CFR 208.43
# =========================================================================

@dataclass(frozen=True)
class PillarTwoThresholds:
    """Aggregate capital thresholds including Pillar 2 requirements.

    Combines Pillar 1 minimums, buffer stack, and Pillar 2A add-ons
    to derive total internal capital targets.

    Reference: BCBS d309, 12 CFR 217.10-11.
    """
    cet1_pillar1: float = CET1_MINIMUM
    tier1_pillar1: float = TIER1_MINIMUM
    total_capital_pillar1: float = TOTAL_CAPITAL_MINIMUM
    ccb: float = CCB_RATE
    ccyb: float = CCYB_DEFAULT
    gsib_surcharge: float = GSIB_SURCHARGE_DEFAULT
    scb: float = SCB_DEFAULT
    pillar_2a_addon: float = DEFAULT_PILLAR_2A_RATES.total_add_on
    management_buffer: float = MANAGEMENT_BUFFER_DEFAULT
    planning_buffer: float = CAPITAL_PLANNING_BUFFER_DEFAULT

    @property
    def effective_ccb(self) -> float:
        """Effective conservation buffer = max(CCB, SCB).
        Reference: 12 CFR 217.11(a)(2)(iv)."""
        return max(self.ccb, self.scb)

    @property
    def combined_buffer_requirement(self) -> float:
        """Combined buffer = effective CCB + CCyB + G-SIB surcharge.
        Reference: 12 CFR 217.11(a)(4)."""
        return self.effective_ccb + self.ccyb + self.gsib_surcharge

    @property
    def total_cet1_requirement(self) -> float:
        """Total CET1 requirement = Pillar 1 + buffers.
        Reference: 12 CFR 217.10-11."""
        return self.cet1_pillar1 + self.combined_buffer_requirement

    @property
    def total_cet1_target(self) -> float:
        """Total CET1 target = requirement + P2A + management + planning.
        Reference: BCBS d309 Principle 7, SR 15-18."""
        return (
            self.total_cet1_requirement
            + self.pillar_2a_addon
            + self.management_buffer
            + self.planning_buffer
        )


DEFAULT_PILLAR_TWO_THRESHOLDS = PillarTwoThresholds()
"""Default Pillar 2 thresholds for a Category I G-SIB."""
