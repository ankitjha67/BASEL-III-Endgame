"""Pillar 3 — Disclosure template definitions and frequency requirements.

Defines all Pillar 3 disclosure templates, their publication frequency,
content requirements, and mapping to regulatory sources.

References:
- BCBS d309: "Pillar 2 (Supervisory Review Process)"
- BCBS d400: "Pillar 3 Disclosure Requirements — Updated Framework" (2022)
- BCBS d455: "Pillar 3 Disclosure Requirements — Consolidated and Enhanced"
- ERBA NPR pp. 34-120: Capital adequacy framework
- 12 CFR 217 Subpart E: Disclosures

All monetary amounts in USD millions ($M) unless otherwise stated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =========================================================================
#  Disclosure Frequency
#  Reference: BCBS d400, Section 2; BCBS d455 para 5-8
# =========================================================================

class DisclosureFrequency(Enum):
    """Publication frequency for Pillar 3 templates.

    Reference: BCBS d400, Section 2.
    """
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"


class DisclosureType(Enum):
    """Type of disclosure: fixed/quantitative format or flexible/qualitative.

    Reference: BCBS d400, Section 2.
    """
    FIXED_FORMAT = "FIXED_FORMAT"       # Standardized template (quantitative)
    FLEXIBLE_FORMAT = "FLEXIBLE_FORMAT"  # Flexible qualitative disclosure


# =========================================================================
#  Template Registry
#  Reference: BCBS d400/d455 — Complete list of Pillar 3 templates
# =========================================================================

@dataclass(frozen=True)
class TemplateDefinition:
    """Definition of a single Pillar 3 disclosure template.

    Reference: BCBS d400/d455.
    """
    template_id: str
    name: str
    description: str
    frequency: DisclosureFrequency
    disclosure_type: DisclosureType
    regulatory_reference: str
    category: str
    row_count: int = 0
    column_count: int = 0


# Overview and Key Metrics
TEMPLATE_OV1 = TemplateDefinition(
    template_id="OV1",
    name="Overview of RWA",
    description="Overview of risk-weighted assets and minimum capital requirements "
                "by risk type (credit, market, operational, CVA).",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table OV1",
    category="overview",
    row_count=12,
    column_count=3,
)

TEMPLATE_KM1 = TemplateDefinition(
    template_id="KM1",
    name="Key Metrics",
    description="Key capital, leverage, and liquidity metrics. Provides "
                "a snapshot of the institution's regulatory position.",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table KM1",
    category="overview",
    row_count=13,
    column_count=5,
)

# Capital Composition
TEMPLATE_CC1 = TemplateDefinition(
    template_id="CC1",
    name="Composition of Regulatory Capital",
    description="Detailed breakdown of CET1, AT1, and Tier 2 capital components "
                "including all regulatory adjustments and deductions.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CC1",
    category="capital_composition",
    row_count=60,
    column_count=2,
)

TEMPLATE_CC2 = TemplateDefinition(
    template_id="CC2",
    name="Reconciliation of Regulatory Capital to Balance Sheet",
    description="Reconciliation of accounting balance sheet to regulatory capital "
                "items, showing how financial statements map to capital components.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CC2",
    category="capital_composition",
    row_count=20,
    column_count=3,
)

# Credit Risk Templates
TEMPLATE_CR1 = TemplateDefinition(
    template_id="CR1",
    name="Credit Quality of Assets",
    description="Gross carrying amounts, allowances, and net values of performing "
                "and non-performing loans and debt securities.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CR1",
    category="credit_risk",
    row_count=10,
    column_count=7,
)

TEMPLATE_CR2 = TemplateDefinition(
    template_id="CR2",
    name="Changes in Stock of Defaulted Loans and Debt Securities",
    description="Movements in defaulted exposures during the reporting period.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CR2",
    category="credit_risk",
    row_count=8,
    column_count=2,
)

TEMPLATE_CR3 = TemplateDefinition(
    template_id="CR3",
    name="Credit Risk Mitigation Techniques — Overview",
    description="Overview of CRM techniques: collateral, guarantees, "
                "credit derivatives by exposure class.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CR3",
    category="credit_risk",
    row_count=12,
    column_count=6,
)

TEMPLATE_CR4 = TemplateDefinition(
    template_id="CR4",
    name="Standardised Approach — Credit Risk Exposure and CRM Effects",
    description="Exposures pre- and post-CRM, RWA and average risk weights "
                "under the standardised approach by asset class.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CR4",
    category="credit_risk",
    row_count=16,
    column_count=6,
)

TEMPLATE_CR5 = TemplateDefinition(
    template_id="CR5",
    name="Standardised Approach — Exposures by Asset Class and Risk Weight",
    description="Breakdown of credit exposures by asset class and applicable "
                "risk weight under the standardised approach.",
    frequency=DisclosureFrequency.SEMI_ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table CR5",
    category="credit_risk",
    row_count=16,
    column_count=12,
)

# Market Risk Templates
TEMPLATE_MR1 = TemplateDefinition(
    template_id="MR1",
    name="Market Risk Under Standardised Approach",
    description="Capital requirements under the FRTB standardised approach "
                "by risk class (GIRR, CSR, Equity, Commodity, FX).",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table MR1",
    category="market_risk",
    row_count=15,
    column_count=2,
)

TEMPLATE_MR2 = TemplateDefinition(
    template_id="MR2",
    name="RWA Flow Statements of Market Risk Exposures Under SA",
    description="Movements in market risk RWA during the reporting period.",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table MR2",
    category="market_risk",
    row_count=8,
    column_count=2,
)

TEMPLATE_MR3 = TemplateDefinition(
    template_id="MR3",
    name="Market Risk Under IMA (where applicable)",
    description="VaR, stressed VaR, and incremental risk charge under IMA.",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table MR3",
    category="market_risk",
    row_count=10,
    column_count=2,
)

TEMPLATE_MR4 = TemplateDefinition(
    template_id="MR4",
    name="Comparison of VaR Estimates with Gains/Losses",
    description="Backtesting results: VaR estimates vs actual P&L.",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table MR4",
    category="market_risk",
    row_count=5,
    column_count=2,
)

# Operational Risk
TEMPLATE_OR1 = TemplateDefinition(
    template_id="OR1",
    name="Operational Risk",
    description="Operational risk capital requirement: Business Indicator, BIC, "
                "ILM, and total operational risk capital charge.",
    frequency=DisclosureFrequency.ANNUAL,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table OR1",
    category="operational_risk",
    row_count=8,
    column_count=3,
)

# Leverage Ratio
TEMPLATE_LR1 = TemplateDefinition(
    template_id="LR1",
    name="Summary Comparison of Accounting Assets vs Leverage Ratio Exposure",
    description="Reconciliation of total assets to leverage ratio exposure.",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table LR1",
    category="leverage_ratio",
    row_count=8,
    column_count=2,
)

TEMPLATE_LR2 = TemplateDefinition(
    template_id="LR2",
    name="Leverage Ratio Common Disclosure",
    description="Detailed leverage ratio calculation with all components "
                "of the leverage exposure denominator.",
    frequency=DisclosureFrequency.QUARTERLY,
    disclosure_type=DisclosureType.FIXED_FORMAT,
    regulatory_reference="BCBS d455 Table LR2",
    category="leverage_ratio",
    row_count=22,
    column_count=2,
)


# =========================================================================
#  Template Registry
# =========================================================================

TEMPLATE_REGISTRY: dict[str, TemplateDefinition] = {
    "OV1": TEMPLATE_OV1,
    "KM1": TEMPLATE_KM1,
    "CC1": TEMPLATE_CC1,
    "CC2": TEMPLATE_CC2,
    "CR1": TEMPLATE_CR1,
    "CR2": TEMPLATE_CR2,
    "CR3": TEMPLATE_CR3,
    "CR4": TEMPLATE_CR4,
    "CR5": TEMPLATE_CR5,
    "MR1": TEMPLATE_MR1,
    "MR2": TEMPLATE_MR2,
    "MR3": TEMPLATE_MR3,
    "MR4": TEMPLATE_MR4,
    "OR1": TEMPLATE_OR1,
    "LR1": TEMPLATE_LR1,
    "LR2": TEMPLATE_LR2,
}
"""Complete registry of all Pillar 3 disclosure templates.
Reference: BCBS d400/d455."""


def get_templates_by_frequency(
    frequency: DisclosureFrequency,
) -> list[TemplateDefinition]:
    """Get all templates that must be published at the given frequency.

    Args:
        frequency: Publication frequency to filter by.

    Returns:
        List of TemplateDefinition matching the frequency.

    Reference: BCBS d400, Section 2.
    """
    return [
        t for t in TEMPLATE_REGISTRY.values()
        if t.frequency == frequency
    ]


def get_templates_by_category(
    category: str,
) -> list[TemplateDefinition]:
    """Get all templates belonging to a specific category.

    Args:
        category: Category name (e.g., "credit_risk", "market_risk").

    Returns:
        List of TemplateDefinition in the category.

    Reference: BCBS d400/d455.
    """
    return [
        t for t in TEMPLATE_REGISTRY.values()
        if t.category == category
    ]
