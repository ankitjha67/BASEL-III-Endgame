"""Pillar 3 Template — OR1: Operational Risk.

OR1: Operational risk capital requirement under the standardised approach,
showing the Business Indicator (BI), Business Indicator Component (BIC),
Internal Loss Multiplier (ILM), and total operational risk capital.

All amounts in USD millions ($M).

References:
- BCBS d455 Table OR1
- BCBS d400 Section 8: Operational risk
- BCBS d424 Section 5: Standardised approach for operational risk
- ERBA NPR pp. 250-270: Operational risk framework
- ILM = 1.0 per US 2026 re-proposal (CLAUDE.md)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# =========================================================================
#  OR1: Operational Risk
#  Reference: BCBS d455 Table OR1
# =========================================================================

class OR1Row(BaseModel):
    """A single row in the OR1 disclosure template.

    Reference: BCBS d455 Table OR1.
    """
    row_number: int = Field(description="Row number")
    description: str = Field(description="Operational risk component")
    current_period: float = Field(default=0.0, description="Current period value in $M")
    prior_period: float = Field(default=0.0, description="Prior period value in $M")
    regulatory_reference: str = Field(default="")


class Pillar3OR1(BaseModel):
    """Pillar 3 Template OR1: Operational Risk.

    Shows the calculation of operational risk capital under the
    Basel III standardised approach (SMA).

    Key components:
    - BI Sub-components: ILDC, SC, FC
    - Business Indicator (BI) = ILDC + SC + FC
    - BIC: marginal coefficients (12%/15%/18%) at thresholds ($1B/$30B)
    - ILM: 1.0 per US 2026 re-proposal
    - OpRisk capital = BIC * ILM
    - OpRisk RWA = capital * 12.5

    Reference: BCBS d455 Table OR1.
    """
    template_id: str = Field(default="OR1")
    reporting_date: date
    entity_name: str = Field(default="")
    rows: list[OR1Row] = Field(default_factory=list)

    # Key metrics
    business_indicator: float = Field(
        default=0.0, description="Business Indicator (BI) in $M"
    )
    bic: float = Field(
        default=0.0, description="Business Indicator Component (BIC) in $M"
    )
    ilm: float = Field(
        default=1.0,
        description="Internal Loss Multiplier (1.0 per US 2026 proposal)"
    )
    capital_charge: float = Field(
        default=0.0, description="Operational risk capital = BIC * ILM in $M"
    )
    rwa: float = Field(
        default=0.0, description="Operational risk RWA = capital * 12.5 in $M"
    )


def build_or1(
    interest_lease_dividend_component: float = 0.0,
    services_component: float = 0.0,
    financial_component: float = 0.0,
    business_indicator: Optional[float] = None,
    bic: float = 0.0,
    ilm: float = 1.0,
    internal_losses_10y: float = 0.0,
    prior_bi: float = 0.0,
    prior_bic: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3OR1:
    """Build Pillar 3 OR1: Operational Risk.

    Creates the OR1 disclosure template showing the operational risk
    capital calculation under the Basel III standardised approach.

    Note: ILM = 1.0 per the US 2026 re-proposal. The Internal Loss
    Multiplier is NOT applied. Reference: CLAUDE.md.

    BIC marginal coefficients:
    - BI <= $1B: 12%
    - $1B < BI <= $30B: 15%
    - BI > $30B: 18%
    Reference: BCBS d424 para 8, ERBA NPR p. 255.

    Args:
        interest_lease_dividend_component: ILDC sub-component in $M.
        services_component: Services sub-component in $M.
        financial_component: Financial sub-component in $M.
        business_indicator: BI override (if None, sum of components).
        bic: Business Indicator Component in $M.
        ilm: Internal Loss Multiplier (1.0 per US proposal).
        internal_losses_10y: 10-year average annual internal losses in $M.
        prior_bi: Prior period BI for comparison in $M.
        prior_bic: Prior period BIC for comparison in $M.
        reporting_date: As-of date.
        entity_name: Entity name.

    Returns:
        Pillar3OR1 disclosure template.

    Reference: BCBS d455 Table OR1, BCBS d424 Section 5.
    """
    # Compute BI if not provided
    bi = business_indicator
    if bi is None:
        bi = (
            interest_lease_dividend_component
            + services_component
            + financial_component
        )

    # Capital charge = BIC * ILM
    capital = bic * ilm
    rwa = capital * 12.5

    rows: list[OR1Row] = [
        OR1Row(
            row_number=1,
            description="Interest, Lease and Dividend Component (ILDC)",
            current_period=interest_lease_dividend_component,
            regulatory_reference="BCBS d424 para 6(a)",
        ),
        OR1Row(
            row_number=2,
            description="Services Component (SC)",
            current_period=services_component,
            regulatory_reference="BCBS d424 para 6(b)",
        ),
        OR1Row(
            row_number=3,
            description="Financial Component (FC)",
            current_period=financial_component,
            regulatory_reference="BCBS d424 para 6(c)",
        ),
        OR1Row(
            row_number=4,
            description="Business Indicator (BI) = ILDC + SC + FC",
            current_period=bi,
            prior_period=prior_bi,
            regulatory_reference="BCBS d424 para 7",
        ),
        OR1Row(
            row_number=5,
            description="Business Indicator Component (BIC)",
            current_period=bic,
            prior_period=prior_bic,
            regulatory_reference="BCBS d424 para 8",
        ),
        OR1Row(
            row_number=6,
            description="Internal Loss Multiplier (ILM)",
            current_period=ilm,
            regulatory_reference="US 2026: ILM = 1.0 (not applied)",
        ),
        OR1Row(
            row_number=7,
            description="Operational risk capital requirement = BIC x ILM",
            current_period=capital,
            regulatory_reference="BCBS d424 para 9",
        ),
        OR1Row(
            row_number=8,
            description="Operational risk RWA = capital x 12.5",
            current_period=rwa,
            regulatory_reference="12 CFR 217.10(a)(3)",
        ),
    ]

    return Pillar3OR1(
        reporting_date=reporting_date,
        entity_name=entity_name,
        rows=rows,
        business_indicator=bi,
        bic=bic,
        ilm=ilm,
        capital_charge=capital,
        rwa=rwa,
    )
