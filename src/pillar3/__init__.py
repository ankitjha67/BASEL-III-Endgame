"""Pillar 3 — Disclosure Requirements.

Implements Pillar 3 disclosure templates per BCBS d400/d455:
- OV1: Overview of RWA
- KM1: Key Metrics
- CC1: Composition of Regulatory Capital
- CC2: Reconciliation to Balance Sheet
- CR1-CR5: Credit Risk Disclosures
- MR1-MR4: Market Risk Disclosures
- OR1: Operational Risk
- LR1-LR2: Leverage Ratio

References:
- BCBS d400: Pillar 3 Disclosure Requirements — Updated Framework
- BCBS d455: Pillar 3 Disclosure Requirements — Consolidated and Enhanced
- 12 CFR 217 Subpart E: Disclosures
"""

from src.pillar3.pillar3_params import (
    DisclosureFrequency,
    DisclosureType,
    TEMPLATE_REGISTRY,
    TemplateDefinition,
    get_templates_by_category,
    get_templates_by_frequency,
)

from src.pillar3.disclosure_engine import (
    DisclosureCapitalData,
    DisclosureLeverageData,
    DisclosureMarketRiskData,
    DisclosurePackage,
    DisclosureRWAData,
    generate_disclosure_package,
    get_disclosure_schedule,
)

from src.pillar3.templates import (
    # Overview
    OV1Row, KM1Row, Pillar3OV1, Pillar3KM1,
    build_ov1, build_km1,
    # Capital composition
    CC1Row, CC2Row, Pillar3CC1, Pillar3CC2,
    build_cc1, build_cc2,
    # Credit risk
    CR1Row, CR4Row, CR5Row,
    Pillar3CR1, Pillar3CR4, Pillar3CR5,
    build_cr1, build_cr4, build_cr5,
    # Market risk
    MR1Row, MR2Row, Pillar3MR1, Pillar3MR2,
    build_mr1, build_mr2,
    # Operational risk
    OR1Row, Pillar3OR1, build_or1,
    # Leverage ratio
    LR1Row, LR2Row, Pillar3LR1, Pillar3LR2,
    build_lr1, build_lr2,
)

__all__ = [
    # Params
    "DisclosureFrequency",
    "DisclosureType",
    "TEMPLATE_REGISTRY",
    "TemplateDefinition",
    "get_templates_by_category",
    "get_templates_by_frequency",
    # Disclosure engine
    "DisclosureCapitalData",
    "DisclosureLeverageData",
    "DisclosureMarketRiskData",
    "DisclosurePackage",
    "DisclosureRWAData",
    "generate_disclosure_package",
    "get_disclosure_schedule",
    # Templates
    "OV1Row", "KM1Row", "Pillar3OV1", "Pillar3KM1",
    "build_ov1", "build_km1",
    "CC1Row", "CC2Row", "Pillar3CC1", "Pillar3CC2",
    "build_cc1", "build_cc2",
    "CR1Row", "CR4Row", "CR5Row",
    "Pillar3CR1", "Pillar3CR4", "Pillar3CR5",
    "build_cr1", "build_cr4", "build_cr5",
    "MR1Row", "MR2Row", "Pillar3MR1", "Pillar3MR2",
    "build_mr1", "build_mr2",
    "OR1Row", "Pillar3OR1", "build_or1",
    "LR1Row", "LR2Row", "Pillar3LR1", "Pillar3LR2",
    "build_lr1", "build_lr2",
]
