"""Pillar 3 Templates — OV1 (Overview of RWA) and KM1 (Key Metrics).

OV1: Provides a summary view of total RWA and minimum capital requirements
by risk type (credit, market, operational, CVA).

KM1: Presents key capital, leverage, and liquidity metrics at a glance.

All amounts in USD millions ($M). Ratios as decimals.

References:
- BCBS d400: "Pillar 3 Disclosure Requirements — Updated Framework"
- BCBS d455: "Pillar 3 Disclosure Requirements — Consolidated and Enhanced"
- BCBS d455 Tables OV1, KM1
- 12 CFR 217 Subpart E: Disclosures
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# =========================================================================
#  OV1: Overview of Risk-Weighted Assets
#  Reference: BCBS d455 Table OV1
# =========================================================================

class OV1Row(BaseModel):
    """A single row in the OV1 disclosure template.

    Reference: BCBS d455 Table OV1.
    """
    row_number: int = Field(description="Row number in OV1 template")
    description: str = Field(description="Risk category description")
    rwa: float = Field(description="Risk-weighted assets in $M")
    minimum_capital: float = Field(
        description="Minimum capital requirement (8% of RWA) in $M"
    )
    rwa_prior_period: float = Field(
        default=0.0,
        description="RWA from prior reporting period in $M"
    )


class Pillar3OV1(BaseModel):
    """Pillar 3 Template OV1: Overview of Risk-Weighted Assets.

    Provides a high-level summary of RWA and minimum capital
    requirements across all risk types.

    Reference: BCBS d455 Table OV1.
    """
    template_id: str = Field(default="OV1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[OV1Row] = Field(default_factory=list)

    # Summary totals
    total_rwa: float = Field(description="Total risk-weighted assets in $M")
    total_minimum_capital: float = Field(
        description="Total minimum capital (8% of total RWA) in $M"
    )

    # Component breakdown
    credit_risk_rwa: float = Field(default=0.0)
    credit_risk_sa_rwa: float = Field(default=0.0)
    counterparty_credit_risk_rwa: float = Field(default=0.0)
    equity_risk_rwa: float = Field(default=0.0)
    securitization_rwa: float = Field(default=0.0)
    market_risk_rwa: float = Field(default=0.0)
    operational_risk_rwa: float = Field(default=0.0)
    cva_risk_rwa: float = Field(default=0.0)
    threshold_deductions_rwa: float = Field(default=0.0)


def build_ov1(
    credit_risk_rwa: float = 0.0,
    counterparty_credit_risk_rwa: float = 0.0,
    equity_risk_rwa: float = 0.0,
    securitization_rwa: float = 0.0,
    market_risk_rwa: float = 0.0,
    operational_risk_rwa: float = 0.0,
    cva_risk_rwa: float = 0.0,
    threshold_deductions_rwa: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
    prior_credit_risk_rwa: float = 0.0,
    prior_market_risk_rwa: float = 0.0,
    prior_operational_risk_rwa: float = 0.0,
    prior_cva_risk_rwa: float = 0.0,
) -> Pillar3OV1:
    """Build Pillar 3 OV1: Overview of RWA.

    Creates the OV1 disclosure template with RWA and minimum capital
    requirements broken down by risk type.

    Minimum capital = 8% of RWA per 12 CFR 217.10(a)(3).

    Args:
        credit_risk_rwa: Credit risk SA RWA in $M.
        counterparty_credit_risk_rwa: CCR (SA-CCR) RWA in $M.
        equity_risk_rwa: Equity exposure RWA in $M.
        securitization_rwa: Securitization RWA in $M.
        market_risk_rwa: Market risk (FRTB) RWA in $M.
        operational_risk_rwa: Operational risk RWA in $M.
        cva_risk_rwa: CVA risk RWA in $M.
        threshold_deductions_rwa: RWA from 250% threshold items.
        reporting_date: As-of date.
        entity_name: Entity name.
        prior_*: Prior period RWA for comparison.

    Returns:
        Pillar3OV1 disclosure template.

    Reference: BCBS d455 Table OV1.
    """
    min_rate = 0.08  # 8% minimum capital ratio

    rows: list[OV1Row] = [
        OV1Row(
            row_number=1,
            description="Credit risk (standardised approach)",
            rwa=credit_risk_rwa,
            minimum_capital=credit_risk_rwa * min_rate,
            rwa_prior_period=prior_credit_risk_rwa,
        ),
        OV1Row(
            row_number=2,
            description="Counterparty credit risk (SA-CCR)",
            rwa=counterparty_credit_risk_rwa,
            minimum_capital=counterparty_credit_risk_rwa * min_rate,
        ),
        OV1Row(
            row_number=3,
            description="Equity exposures under simple risk weight approach",
            rwa=equity_risk_rwa,
            minimum_capital=equity_risk_rwa * min_rate,
        ),
        OV1Row(
            row_number=4,
            description="Securitisation exposures",
            rwa=securitization_rwa,
            minimum_capital=securitization_rwa * min_rate,
        ),
        OV1Row(
            row_number=5,
            description="Amounts below thresholds (250% risk weight)",
            rwa=threshold_deductions_rwa,
            minimum_capital=threshold_deductions_rwa * min_rate,
        ),
        OV1Row(
            row_number=6,
            description="Market risk (standardised approach — FRTB)",
            rwa=market_risk_rwa,
            minimum_capital=market_risk_rwa * min_rate,
            rwa_prior_period=prior_market_risk_rwa,
        ),
        OV1Row(
            row_number=7,
            description="Operational risk",
            rwa=operational_risk_rwa,
            minimum_capital=operational_risk_rwa * min_rate,
            rwa_prior_period=prior_operational_risk_rwa,
        ),
        OV1Row(
            row_number=8,
            description="CVA risk",
            rwa=cva_risk_rwa,
            minimum_capital=cva_risk_rwa * min_rate,
            rwa_prior_period=prior_cva_risk_rwa,
        ),
    ]

    total_rwa = (
        credit_risk_rwa + counterparty_credit_risk_rwa + equity_risk_rwa
        + securitization_rwa + threshold_deductions_rwa
        + market_risk_rwa + operational_risk_rwa + cva_risk_rwa
    )

    rows.append(OV1Row(
        row_number=9,
        description="Total",
        rwa=total_rwa,
        minimum_capital=total_rwa * min_rate,
    ))

    return Pillar3OV1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        total_rwa=total_rwa,
        total_minimum_capital=total_rwa * min_rate,
        credit_risk_rwa=credit_risk_rwa,
        credit_risk_sa_rwa=credit_risk_rwa,
        counterparty_credit_risk_rwa=counterparty_credit_risk_rwa,
        equity_risk_rwa=equity_risk_rwa,
        securitization_rwa=securitization_rwa,
        market_risk_rwa=market_risk_rwa,
        operational_risk_rwa=operational_risk_rwa,
        cva_risk_rwa=cva_risk_rwa,
        threshold_deductions_rwa=threshold_deductions_rwa,
    )


# =========================================================================
#  KM1: Key Metrics
#  Reference: BCBS d455 Table KM1
# =========================================================================

class KM1Row(BaseModel):
    """A single row in the KM1 disclosure template.

    Reference: BCBS d455 Table KM1.
    """
    row_number: int = Field(description="Row number in KM1 template")
    description: str = Field(description="Metric description")
    current_value: float = Field(description="Current period value")
    prior_q1: float = Field(default=0.0, description="Prior quarter (T-1)")
    prior_q2: float = Field(default=0.0, description="Two quarters ago (T-2)")
    prior_q3: float = Field(default=0.0, description="Three quarters ago (T-3)")
    prior_q4: float = Field(default=0.0, description="Four quarters ago (T-4)")
    unit: str = Field(default="$M", description="Unit of measurement")


class Pillar3KM1(BaseModel):
    """Pillar 3 Template KM1: Key Metrics.

    Provides a snapshot of the institution's regulatory capital,
    leverage, and liquidity position.

    Reference: BCBS d455 Table KM1.
    """
    template_id: str = Field(default="KM1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[KM1Row] = Field(default_factory=list)

    # Key metrics (direct access)
    cet1_capital: float = Field(description="CET1 capital in $M")
    tier1_capital: float = Field(description="Tier 1 capital in $M")
    total_capital: float = Field(description="Total capital in $M")
    total_rwa: float = Field(description="Total RWA in $M")
    cet1_ratio: float = Field(description="CET1 ratio")
    tier1_ratio: float = Field(description="Tier 1 ratio")
    total_capital_ratio: float = Field(description="Total capital ratio")
    ccb: float = Field(default=0.025, description="CCB/SCB rate")
    ccyb: float = Field(default=0.0, description="CCyB rate")
    gsib_surcharge: float = Field(default=0.015, description="G-SIB surcharge rate")
    cet1_available_for_buffers: float = Field(
        default=0.0, description="CET1 available to meet buffer requirements"
    )
    total_leverage_exposure: float = Field(default=0.0)
    leverage_ratio: float = Field(default=0.0)


def build_km1(
    cet1_capital: float,
    tier1_capital: float,
    total_capital: float,
    total_rwa: float,
    ccb: float = 0.025,
    ccyb: float = 0.0,
    gsib_surcharge: float = 0.015,
    total_leverage_exposure: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3KM1:
    """Build Pillar 3 KM1: Key Metrics.

    Creates the KM1 disclosure template with key capital, leverage,
    and liquidity metrics.

    Args:
        cet1_capital: CET1 capital in $M.
        tier1_capital: Tier 1 capital in $M.
        total_capital: Total capital in $M.
        total_rwa: Total RWA in $M.
        ccb: CCB/SCB rate (decimal).
        ccyb: CCyB rate (decimal).
        gsib_surcharge: G-SIB surcharge (decimal).
        total_leverage_exposure: Total leverage exposure in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3KM1 disclosure template.

    Reference: BCBS d455 Table KM1.
    """
    cet1_ratio = cet1_capital / total_rwa if total_rwa > 0 else 0.0
    tier1_ratio = tier1_capital / total_rwa if total_rwa > 0 else 0.0
    total_ratio = total_capital / total_rwa if total_rwa > 0 else 0.0
    leverage_ratio = (
        tier1_capital / total_leverage_exposure
        if total_leverage_exposure > 0 else 0.0
    )
    cet1_available = max(0.0, cet1_ratio - 0.045)

    rows: list[KM1Row] = [
        KM1Row(row_number=1, description="Common Equity Tier 1 (CET1)",
               current_value=cet1_capital),
        KM1Row(row_number=2, description="Tier 1",
               current_value=tier1_capital),
        KM1Row(row_number=3, description="Total capital",
               current_value=total_capital),
        KM1Row(row_number=4, description="Total risk-weighted assets (RWA)",
               current_value=total_rwa),
        KM1Row(row_number=5, description="CET1 ratio (%)",
               current_value=cet1_ratio * 100, unit="%"),
        KM1Row(row_number=6, description="Tier 1 ratio (%)",
               current_value=tier1_ratio * 100, unit="%"),
        KM1Row(row_number=7, description="Total capital ratio (%)",
               current_value=total_ratio * 100, unit="%"),
        KM1Row(row_number=8, description="Capital conservation buffer (%)",
               current_value=ccb * 100, unit="%"),
        KM1Row(row_number=9, description="Countercyclical buffer (%)",
               current_value=ccyb * 100, unit="%"),
        KM1Row(row_number=10, description="G-SIB surcharge (%)",
               current_value=gsib_surcharge * 100, unit="%"),
        KM1Row(row_number=11,
               description="CET1 available to meet buffers (%)",
               current_value=cet1_available * 100, unit="%"),
        KM1Row(row_number=12, description="Total leverage exposure",
               current_value=total_leverage_exposure),
        KM1Row(row_number=13, description="Leverage ratio (%)",
               current_value=leverage_ratio * 100, unit="%"),
    ]

    return Pillar3KM1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        cet1_capital=cet1_capital,
        tier1_capital=tier1_capital,
        total_capital=total_capital,
        total_rwa=total_rwa,
        cet1_ratio=cet1_ratio,
        tier1_ratio=tier1_ratio,
        total_capital_ratio=total_ratio,
        ccb=ccb,
        ccyb=ccyb,
        gsib_surcharge=gsib_surcharge,
        cet1_available_for_buffers=cet1_available,
        total_leverage_exposure=total_leverage_exposure,
        leverage_ratio=leverage_ratio,
    )
