"""Pillar 3 Templates — CR1-CR5: Credit Risk Disclosures.

CR1: Credit quality of assets (performing vs non-performing).
CR2: Changes in stock of defaulted loans and debt securities.
CR3: Credit risk mitigation techniques overview (not implemented here).
CR4: SA credit risk exposure and CRM effects by asset class.
CR5: SA exposures by asset class and risk weight.

All amounts in USD millions ($M).

References:
- BCBS d455 Tables CR1-CR5
- BCBS d400 Section 5: Credit risk
- 12 CFR 217 Subpart D: Standardised approach for credit risk
- ERBA NPR pp. 100-200: Credit risk framework
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# =========================================================================
#  CR1: Credit Quality of Assets
#  Reference: BCBS d455 Table CR1
# =========================================================================

class CR1Row(BaseModel):
    """A single row in the CR1 disclosure template.

    Reference: BCBS d455 Table CR1.
    """
    row_number: int = Field(description="Row number")
    asset_class: str = Field(description="Asset class / exposure type")
    defaulted_gross: float = Field(
        default=0.0, description="Defaulted exposures — gross carrying amount in $M"
    )
    non_defaulted_gross: float = Field(
        default=0.0, description="Non-defaulted exposures — gross carrying amount in $M"
    )
    allowances_specific: float = Field(
        default=0.0, description="Specific allowances / provisions in $M"
    )
    allowances_general: float = Field(
        default=0.0, description="General allowances / provisions in $M"
    )
    write_offs: float = Field(
        default=0.0, description="Accumulated write-offs in period in $M"
    )
    net_values: float = Field(
        default=0.0, description="Net values (gross - allowances) in $M"
    )


class Pillar3CR1(BaseModel):
    """Pillar 3 Template CR1: Credit Quality of Assets.

    Reference: BCBS d455 Table CR1.
    """
    template_id: str = Field(default="CR1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[CR1Row] = Field(default_factory=list)

    total_defaulted: float = Field(default=0.0)
    total_non_defaulted: float = Field(default=0.0)
    total_allowances: float = Field(default=0.0)
    total_net: float = Field(default=0.0)


def build_cr1(
    asset_classes: list[dict[str, float]],
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3CR1:
    """Build Pillar 3 CR1: Credit Quality of Assets.

    Args:
        asset_classes: List of dicts with keys: name, defaulted_gross,
            non_defaulted_gross, allowances_specific, allowances_general,
            write_offs.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3CR1 disclosure template.

    Reference: BCBS d455 Table CR1.
    """
    rows: list[CR1Row] = []
    total_def = 0.0
    total_nondef = 0.0
    total_allow = 0.0
    total_net = 0.0

    for i, ac in enumerate(asset_classes, 1):
        defaulted = ac.get("defaulted_gross", 0.0)
        non_defaulted = ac.get("non_defaulted_gross", 0.0)
        spec_allow = ac.get("allowances_specific", 0.0)
        gen_allow = ac.get("allowances_general", 0.0)
        write_offs = ac.get("write_offs", 0.0)
        total_allowance = spec_allow + gen_allow
        net = defaulted + non_defaulted - total_allowance

        rows.append(CR1Row(
            row_number=i,
            asset_class=ac.get("name", f"Asset Class {i}"),
            defaulted_gross=defaulted,
            non_defaulted_gross=non_defaulted,
            allowances_specific=spec_allow,
            allowances_general=gen_allow,
            write_offs=write_offs,
            net_values=net,
        ))

        total_def += defaulted
        total_nondef += non_defaulted
        total_allow += total_allowance
        total_net += net

    # Total row
    rows.append(CR1Row(
        row_number=len(asset_classes) + 1,
        asset_class="Total",
        defaulted_gross=total_def,
        non_defaulted_gross=total_nondef,
        allowances_specific=sum(ac.get("allowances_specific", 0.0) for ac in asset_classes),
        allowances_general=sum(ac.get("allowances_general", 0.0) for ac in asset_classes),
        write_offs=sum(ac.get("write_offs", 0.0) for ac in asset_classes),
        net_values=total_net,
    ))

    return Pillar3CR1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_defaulted=total_def,
        total_non_defaulted=total_nondef,
        total_allowances=total_allow,
        total_net=total_net,
    )


# =========================================================================
#  CR2: Changes in Stock of Defaulted Loans and Debt Securities
#  Reference: BCBS d455 Table CR2
# =========================================================================

class CR2Row(BaseModel):
    """A single row in the CR2 disclosure template.

    Reference: BCBS d455 Table CR2.
    """
    row_number: int = Field(description="Row number")
    description: str = Field(description="Movement description")
    amount: float = Field(description="Amount in $M")


class Pillar3CR2(BaseModel):
    """Pillar 3 Template CR2: Changes in Defaulted Exposures.

    Reference: BCBS d455 Table CR2.
    """
    template_id: str = Field(default="CR2")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[CR2Row] = Field(default_factory=list)
    closing_balance: float = Field(default=0.0)


def build_cr2(
    opening_balance: float,
    new_defaults: float = 0.0,
    returned_to_performing: float = 0.0,
    write_offs: float = 0.0,
    other_changes: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3CR2:
    """Build Pillar 3 CR2: Changes in Defaulted Exposures.

    Args:
        opening_balance: Opening defaulted balance in $M.
        new_defaults: Loans/securities newly defaulted in $M.
        returned_to_performing: Amounts returned to performing in $M.
        write_offs: Amounts written off in $M.
        other_changes: Other changes in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3CR2 disclosure template.

    Reference: BCBS d455 Table CR2.
    """
    closing = (
        opening_balance + new_defaults
        - returned_to_performing - write_offs + other_changes
    )

    rows: list[CR2Row] = [
        CR2Row(row_number=1, description="Defaulted loans and debt securities at beginning of period",
               amount=opening_balance),
        CR2Row(row_number=2, description="Loans and debt securities that have defaulted since last period",
               amount=new_defaults),
        CR2Row(row_number=3, description="Returned to non-defaulted status",
               amount=-returned_to_performing),
        CR2Row(row_number=4, description="Amounts written off",
               amount=-write_offs),
        CR2Row(row_number=5, description="Other changes",
               amount=other_changes),
        CR2Row(row_number=6, description="Defaulted loans and debt securities at end of period",
               amount=closing),
    ]

    return Pillar3CR2(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        closing_balance=closing,
    )


# =========================================================================
#  CR4: SA — Credit Risk Exposure and CRM Effects
#  Reference: BCBS d455 Table CR4
# =========================================================================

class CR4Row(BaseModel):
    """A single row in the CR4 disclosure template.

    Reference: BCBS d455 Table CR4.
    """
    row_number: int = Field(description="Row number")
    asset_class: str = Field(description="Asset class")
    exposure_pre_ccf_pre_crm: float = Field(
        default=0.0, description="Exposure pre-CCF and pre-CRM in $M"
    )
    exposure_post_ccf_post_crm: float = Field(
        default=0.0, description="Exposure post-CCF and post-CRM in $M"
    )
    rwa: float = Field(default=0.0, description="RWA in $M")
    rwa_density: float = Field(
        default=0.0, description="RWA density = RWA / exposure_post"
    )


class Pillar3CR4(BaseModel):
    """Pillar 3 Template CR4: SA Credit Exposure and CRM Effects.

    Reference: BCBS d455 Table CR4.
    """
    template_id: str = Field(default="CR4")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[CR4Row] = Field(default_factory=list)
    total_exposure_pre: float = Field(default=0.0)
    total_exposure_post: float = Field(default=0.0)
    total_rwa: float = Field(default=0.0)


def build_cr4(
    exposures: list[dict[str, float]],
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3CR4:
    """Build Pillar 3 CR4: SA Credit Exposure and CRM Effects.

    Args:
        exposures: List of dicts with keys: name, exposure_pre, exposure_post, rwa.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3CR4 disclosure template.

    Reference: BCBS d455 Table CR4.
    """
    rows: list[CR4Row] = []
    total_pre = 0.0
    total_post = 0.0
    total_rwa = 0.0

    for i, exp in enumerate(exposures, 1):
        pre = exp.get("exposure_pre", 0.0)
        post = exp.get("exposure_post", 0.0)
        rwa = exp.get("rwa", 0.0)
        density = rwa / post if post > 0 else 0.0

        rows.append(CR4Row(
            row_number=i,
            asset_class=exp.get("name", f"Asset Class {i}"),
            exposure_pre_ccf_pre_crm=pre,
            exposure_post_ccf_post_crm=post,
            rwa=rwa,
            rwa_density=density,
        ))

        total_pre += pre
        total_post += post
        total_rwa += rwa

    # Total row
    total_density = total_rwa / total_post if total_post > 0 else 0.0
    rows.append(CR4Row(
        row_number=len(exposures) + 1,
        asset_class="Total",
        exposure_pre_ccf_pre_crm=total_pre,
        exposure_post_ccf_post_crm=total_post,
        rwa=total_rwa,
        rwa_density=total_density,
    ))

    return Pillar3CR4(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_exposure_pre=total_pre,
        total_exposure_post=total_post,
        total_rwa=total_rwa,
    )


# =========================================================================
#  CR5: SA — Exposures by Asset Class and Risk Weight
#  Reference: BCBS d455 Table CR5
# =========================================================================

# Standard risk weight columns per Basel III SA
STANDARD_RISK_WEIGHTS: list[str] = [
    "0%", "10%", "20%", "35%", "45%", "50%", "65%",
    "75%", "100%", "150%", "250%", "Others",
]
"""Standard risk weight bands for CR5 template.
Reference: BCBS d455 Table CR5, 12 CFR 217 Subpart D."""


class CR5Row(BaseModel):
    """A single row in the CR5 disclosure template.

    Reference: BCBS d455 Table CR5.
    """
    row_number: int = Field(description="Row number")
    asset_class: str = Field(description="Asset class")
    risk_weight_exposures: dict[str, float] = Field(
        default_factory=dict,
        description="Exposure by risk weight band in $M"
    )
    total_credit_exposure: float = Field(
        default=0.0, description="Total credit exposure for this asset class in $M"
    )


class Pillar3CR5(BaseModel):
    """Pillar 3 Template CR5: SA Exposures by Risk Weight.

    Reference: BCBS d455 Table CR5.
    """
    template_id: str = Field(default="CR5")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[CR5Row] = Field(default_factory=list)
    risk_weight_columns: list[str] = Field(
        default_factory=lambda: list(STANDARD_RISK_WEIGHTS)
    )
    total_exposure: float = Field(default=0.0)


def build_cr5(
    exposures: list[dict[str, object]],
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3CR5:
    """Build Pillar 3 CR5: SA Exposures by Risk Weight.

    Args:
        exposures: List of dicts with keys: name, risk_weight_exposures (dict),
            total_credit_exposure.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3CR5 disclosure template.

    Reference: BCBS d455 Table CR5.
    """
    rows: list[CR5Row] = []
    total_exp = 0.0

    for i, exp in enumerate(exposures, 1):
        rw_exp = exp.get("risk_weight_exposures", {})
        if not isinstance(rw_exp, dict):
            rw_exp = {}
        total_class = float(exp.get("total_credit_exposure", sum(
            float(v) for v in rw_exp.values()
        )))

        rows.append(CR5Row(
            row_number=i,
            asset_class=str(exp.get("name", f"Asset Class {i}")),
            risk_weight_exposures={str(k): float(v) for k, v in rw_exp.items()},
            total_credit_exposure=total_class,
        ))
        total_exp += total_class

    return Pillar3CR5(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_exposure=total_exp,
    )
