"""Operational Risk Reporting — Pillar 3 OR1 and FFIEC Templates.

Generates regulatory disclosure reports for operational risk under
the Basel III Endgame framework, including:

- Pillar 3 OR1: Operational risk own funds requirements and RWA
- FFIEC 101 Schedule A: RWA by exposure type (operational risk lines)
- FR Y-9C Schedule HC-R: Regulatory capital (operational risk component)

All monetary amounts in USD millions ($M) unless otherwise stated.

References:
    - BCBS d424 Section 5: Operational Risk
    - Pillar 3 disclosure requirements: OR1 template
    - FFIEC 101 Schedule A: Risk-weighted assets
    - FR Y-9C Schedule HC-R: Regulatory capital components
    - US Basel III Endgame March 2026 Re-Proposal, Section VI
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from src.operational_risk.or_calculator import (
    FinancialStatementData,
    LossComponentData,
    OpRiskCalculator,
    OpRiskResult,
)
from src.operational_risk.or_params import (
    BI_AVERAGING_YEARS,
    BIC_BUCKETS,
    ILM,
    LC_MULTIPLIER,
    LOSS_DATA_YEARS,
    LOSS_THRESHOLD_USD,
    RWA_CONVERSION_FACTOR,
    LossEventType,
)


# =========================================================================
#  Pillar 3 OR1 Template Models
# =========================================================================

class OR1Row(BaseModel):
    """Single row in the Pillar 3 OR1 disclosure template.

    Each row represents a BI bucket with its components and capital.

    Reference:
        Pillar 3 OR1 template; BCBS d424 §5.7.
    """
    row_number: int = Field(description="OR1 template row number")
    row_label: str = Field(description="Row description")
    bi_amount_usd_m: float = Field(
        description="Business Indicator amount in $M"
    )
    bic_amount_usd_m: float = Field(
        description="Business Indicator Component in $M"
    )
    ilm: float = Field(
        description="Internal Loss Multiplier (1.0 per US proposal)"
    )
    capital_usd_m: float = Field(
        description="Operational risk capital in $M"
    )
    rwa_usd_m: float = Field(
        description="Operational risk RWA in $M"
    )


class OR1Report(BaseModel):
    """Complete Pillar 3 OR1 disclosure report.

    Reference:
        Pillar 3 disclosure requirements; BCBS d424 §5.
    """
    reporting_date: str = Field(description="Reporting date (YYYY-MM-DD)")
    entity_name: str = Field(description="Reporting entity name")
    rows: list[OR1Row] = Field(
        default_factory=list, description="OR1 template rows"
    )
    total_bi_usd_m: float = Field(
        default=0.0, description="Total Business Indicator in $M"
    )
    total_bic_usd_m: float = Field(
        default=0.0, description="Total BIC in $M"
    )
    total_capital_usd_m: float = Field(
        default=0.0, description="Total operational risk capital in $M"
    )
    total_rwa_usd_m: float = Field(
        default=0.0, description="Total operational risk RWA in $M"
    )
    ildc_usd_m: float = Field(
        default=0.0, description="ILDC component in $M"
    )
    sc_usd_m: float = Field(
        default=0.0, description="SC component in $M"
    )
    fc_usd_m: float = Field(
        default=0.0, description="FC component in $M"
    )
    loss_component_usd_m: float = Field(
        default=0.0, description="Loss Component in $M (for reference)"
    )
    ilm_applied: float = Field(
        default=1.0, description="ILM value applied"
    )
    notes: list[str] = Field(
        default_factory=list, description="Disclosure notes"
    )


# =========================================================================
#  FFIEC 101 Schedule A Models
# =========================================================================

class FFIEC101OpRiskLine(BaseModel):
    """FFIEC 101 Schedule A operational risk line items.

    Reference:
        FFIEC 101 Schedule A: Risk-weighted assets by exposure type.
    """
    line_number: str = Field(description="FFIEC 101 line reference")
    line_description: str = Field(description="Line item description")
    amount_usd_m: float = Field(description="Amount in $M")


class FFIEC101OpRiskReport(BaseModel):
    """FFIEC 101 Schedule A operational risk section.

    Reference:
        FFIEC 101 Schedule A.
    """
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    lines: list[FFIEC101OpRiskLine] = Field(default_factory=list)
    total_oprisk_rwa_usd_m: float = Field(
        default=0.0, description="Total operational risk RWA in $M"
    )


# =========================================================================
#  FR Y-9C Schedule HC-R Models
# =========================================================================

class HCROpRiskSection(BaseModel):
    """FR Y-9C Schedule HC-R operational risk component.

    Reference:
        FR Y-9C Schedule HC-R: Regulatory capital components.
    """
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    oprisk_capital_usd_m: float = Field(
        description="Operational risk capital charge in $M"
    )
    oprisk_rwa_usd_m: float = Field(
        description="Operational risk RWA in $M"
    )
    bi_usd_m: float = Field(
        description="Business Indicator in $M"
    )
    bic_usd_m: float = Field(
        description="Business Indicator Component in $M"
    )
    ilm: float = Field(
        description="Internal Loss Multiplier applied"
    )


# =========================================================================
#  Loss Data Report Models
# =========================================================================

class LossDataSummary(BaseModel):
    """Summary of internal loss data for Pillar 3 disclosure.

    While the US 2026 proposal does not use loss data for capital,
    disclosure of loss experience is required per Pillar 3.

    Reference:
        Pillar 3 OR1 template; BCBS d424 §5.10.
    """
    data_years: int = Field(description="Years of loss data available")
    total_losses_usd_m: float = Field(
        description="Total losses over the data period in $M"
    )
    average_annual_loss_usd_m: float = Field(
        description="Average annual loss in $M"
    )
    loss_component_usd_m: float = Field(
        description="Loss Component (15x * avg annual loss) in $M"
    )
    event_count: int = Field(
        description="Total loss events above threshold"
    )
    largest_loss_usd_m: float = Field(
        description="Largest single loss event in $M"
    )
    losses_by_event_type: dict[str, float] = Field(
        default_factory=dict,
        description="Losses by Basel event type in $M"
    )
    loss_threshold_usd: float = Field(
        default=LOSS_THRESHOLD_USD,
        description="Minimum loss threshold for inclusion"
    )


# =========================================================================
#  Report Generator
# =========================================================================

class OpRiskReportGenerator:
    """Generates operational risk regulatory reports.

    Produces Pillar 3 OR1 disclosures, FFIEC 101 Schedule A entries,
    and FR Y-9C Schedule HC-R operational risk components.

    Usage::

        calc = OpRiskCalculator()
        result = calc.calculate(financials)
        gen = OpRiskReportGenerator("Bank Name")
        or1 = gen.generate_or1(result, "2026-03-31")
        ffiec = gen.generate_ffiec101(result, "2026-03-31")

    Reference:
        Pillar 3 OR1; FFIEC 101 Schedule A; FR Y-9C Schedule HC-R.
    """

    def __init__(self, entity_name: str) -> None:
        """Initialize the report generator.

        Args:
            entity_name: Name of the reporting entity.
        """
        self._entity_name = entity_name

    def generate_or1(
        self,
        result: OpRiskResult,
        reporting_date: str,
        loss_data: Optional[LossComponentData] = None,
    ) -> OR1Report:
        """Generate Pillar 3 OR1 disclosure report.

        The OR1 template discloses the Business Indicator, BIC, ILM,
        and operational risk capital by BI bucket.

        Args:
            result: OpRiskResult from the calculator.
            reporting_date: Reporting date string (YYYY-MM-DD).
            loss_data: Optional loss data for supplementary disclosure.

        Returns:
            Complete OR1 report.

        Reference:
            Pillar 3 OR1 template; BCBS d424 §5.
        """
        to_m = 1e-6  # Convert USD to $M

        rows: list[OR1Row] = []
        bucket_capitals = result.capital_charge_by_bucket

        # Row 1: BI Bucket 1 (up to $1B)
        b1_capital = bucket_capitals.get("bucket_1_to_1B", 0.0)
        b1_bi = min(result.business_indicator, 1_000_000_000)
        rows.append(OR1Row(
            row_number=1,
            row_label="BI Bucket 1 (BI <= $1B): 12% marginal coefficient",
            bi_amount_usd_m=b1_bi * to_m,
            bic_amount_usd_m=b1_capital * to_m,
            ilm=result.ilm,
            capital_usd_m=b1_capital * to_m,
            rwa_usd_m=b1_capital * RWA_CONVERSION_FACTOR * to_m,
        ))

        # Row 2: BI Bucket 2 ($1B to $30B)
        b2_capital = bucket_capitals.get("bucket_1B_to_30B", 0.0)
        b2_bi = max(0, min(result.business_indicator, 30_000_000_000) - 1_000_000_000)
        rows.append(OR1Row(
            row_number=2,
            row_label="BI Bucket 2 ($1B < BI <= $30B): 15% marginal coefficient",
            bi_amount_usd_m=b2_bi * to_m,
            bic_amount_usd_m=b2_capital * to_m,
            ilm=result.ilm,
            capital_usd_m=b2_capital * to_m,
            rwa_usd_m=b2_capital * RWA_CONVERSION_FACTOR * to_m,
        ))

        # Row 3: BI Bucket 3 (above $30B)
        b3_capital = bucket_capitals.get("bucket_above_30B", 0.0)
        b3_bi = max(0, result.business_indicator - 30_000_000_000)
        rows.append(OR1Row(
            row_number=3,
            row_label="BI Bucket 3 (BI > $30B): 18% marginal coefficient",
            bi_amount_usd_m=b3_bi * to_m,
            bic_amount_usd_m=b3_capital * to_m,
            ilm=result.ilm,
            capital_usd_m=b3_capital * to_m,
            rwa_usd_m=b3_capital * RWA_CONVERSION_FACTOR * to_m,
        ))

        # Notes
        notes = [
            f"ILM = {result.ilm:.1f} per US 2026 proposal (not applied).",
            f"BI averaging period: {BI_AVERAGING_YEARS} years.",
            "BIC marginal coefficients: 12% / 15% / 18% at $1B / $30B thresholds.",
        ]
        if result.nic_adjustment != 0:
            notes.append(
                f"NIC investment management adjustment: "
                f"${result.nic_adjustment * to_m:,.1f}M"
            )

        return OR1Report(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            rows=rows,
            total_bi_usd_m=result.business_indicator * to_m,
            total_bic_usd_m=result.bic * to_m,
            total_capital_usd_m=result.capital_charge * to_m,
            total_rwa_usd_m=result.rwa * to_m,
            ildc_usd_m=result.ildc * to_m,
            sc_usd_m=result.sc * to_m,
            fc_usd_m=result.fc * to_m,
            loss_component_usd_m=result.loss_component * to_m,
            ilm_applied=result.ilm,
            notes=notes,
        )

    def generate_ffiec101(
        self,
        result: OpRiskResult,
        reporting_date: str,
    ) -> FFIEC101OpRiskReport:
        """Generate FFIEC 101 Schedule A operational risk section.

        Produces the operational risk line items for the FFIEC 101
        regulatory report filed by advanced approaches banking organizations.

        Args:
            result: OpRiskResult from the calculator.
            reporting_date: Reporting date string (YYYY-MM-DD).

        Returns:
            FFIEC 101 operational risk report section.

        Reference:
            FFIEC 101 Schedule A: Risk-weighted assets by exposure type.
        """
        to_m = 1e-6

        lines: list[FFIEC101OpRiskLine] = [
            FFIEC101OpRiskLine(
                line_number="14a",
                line_description="Business Indicator (BI)",
                amount_usd_m=result.business_indicator * to_m,
            ),
            FFIEC101OpRiskLine(
                line_number="14b",
                line_description="ILDC — Interest, Lease, and Dividend Component",
                amount_usd_m=result.ildc * to_m,
            ),
            FFIEC101OpRiskLine(
                line_number="14c",
                line_description="SC — Services Component",
                amount_usd_m=result.sc * to_m,
            ),
            FFIEC101OpRiskLine(
                line_number="14d",
                line_description="FC — Financial Component",
                amount_usd_m=result.fc * to_m,
            ),
            FFIEC101OpRiskLine(
                line_number="14e",
                line_description="Business Indicator Component (BIC)",
                amount_usd_m=result.bic * to_m,
            ),
            FFIEC101OpRiskLine(
                line_number="14f",
                line_description="Internal Loss Multiplier (ILM)",
                amount_usd_m=result.ilm,
            ),
            FFIEC101OpRiskLine(
                line_number="14g",
                line_description="Operational Risk Capital Charge",
                amount_usd_m=result.capital_charge * to_m,
            ),
            FFIEC101OpRiskLine(
                line_number="14h",
                line_description="Operational Risk RWA",
                amount_usd_m=result.rwa * to_m,
            ),
        ]

        return FFIEC101OpRiskReport(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            lines=lines,
            total_oprisk_rwa_usd_m=result.rwa * to_m,
        )

    def generate_hcr_section(
        self,
        result: OpRiskResult,
        reporting_date: str,
    ) -> HCROpRiskSection:
        """Generate FR Y-9C Schedule HC-R operational risk component.

        Produces the operational risk section for the FR Y-9C
        Schedule HC-R regulatory capital report.

        Args:
            result: OpRiskResult from the calculator.
            reporting_date: Reporting date string (YYYY-MM-DD).

        Returns:
            HC-R operational risk section.

        Reference:
            FR Y-9C Schedule HC-R: Regulatory capital components.
        """
        to_m = 1e-6

        return HCROpRiskSection(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            oprisk_capital_usd_m=result.capital_charge * to_m,
            oprisk_rwa_usd_m=result.rwa * to_m,
            bi_usd_m=result.business_indicator * to_m,
            bic_usd_m=result.bic * to_m,
            ilm=result.ilm,
        )

    def generate_loss_data_summary(
        self,
        loss_data: LossComponentData,
        business_indicator: float,
    ) -> LossDataSummary:
        """Generate loss data summary for Pillar 3 disclosure.

        While the US 2026 proposal sets ILM = 1.0, banks must still
        disclose their loss experience per Pillar 3 requirements.

        Args:
            loss_data: Internal loss data.
            business_indicator: Total BI in USD for LC calculation.

        Returns:
            Loss data summary.

        Reference:
            Pillar 3 OR1 template; BCBS d424 §5.10.
        """
        to_m = 1e-6

        total_losses = sum(loss_data.annual_losses) if loss_data.annual_losses else 0.0
        n_years = len(loss_data.annual_losses) if loss_data.annual_losses else 0
        avg_annual = total_losses / n_years if n_years > 0 else 0.0
        lc = LC_MULTIPLIER * avg_annual if business_indicator > 1e9 else 0.0

        losses_by_type_m = {
            k: v * to_m for k, v in loss_data.losses_by_event_type.items()
        }

        return LossDataSummary(
            data_years=n_years,
            total_losses_usd_m=total_losses * to_m,
            average_annual_loss_usd_m=avg_annual * to_m,
            loss_component_usd_m=lc * to_m,
            event_count=loss_data.total_loss_events,
            largest_loss_usd_m=loss_data.largest_single_loss * to_m,
            losses_by_event_type=losses_by_type_m,
        )
