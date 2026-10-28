"""Operational risk reporting — Pillar 3 OR1, FFIEC 101 and FR Y-9C HC-R.

Generates regulatory disclosure views of the ERBA NPR §__.150 operational
risk calculation:

- Pillar 3 OR1: business indicator, BIC and RWA by marginal tier
- FFIEC 101 Schedule A: operational risk line items (BI inputs are to be
  publicly reported on FFIEC 101 — preamble p. 200)
- FR Y-9C Schedule HC-R: operational risk RWA component
- Loss event data summary for Pillar 3 / FR Y-14Q

All monetary amounts in USD millions ($M), consistent with the calculator.
The ILM column retained in some templates is populated with 1.0 because
§__.150(a) has no multiplier (preamble p. 197 fn. 216).

References:
    - ERBA NPR §__.150 (12 CFR 217.150, Subpart E); §__.162 disclosures
    - FFIEC 101 Schedule A; FR Y-9C Schedule HC-R; FR Y-14Q Schedule E
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.operational_risk.or_calculator import (
    OperationalLossData,
    OpRiskCalculator,
    OpRiskResult,
)
from src.operational_risk.or_params import (
    BI_AVERAGING_PERIODS,
    BIC_THRESHOLD_1_USD_M,
    BIC_THRESHOLD_2_USD_M,
    ILM,
    LOSS_COLLECTION_THRESHOLD_USD,
    LOSS_DATA_YEARS,
    RWA_CONVERSION_FACTOR,
    SERVICES_NET_INCOME_FACTOR,
    LossEventType,
)

# =========================================================================
#  Pillar 3 OR1 template models
# =========================================================================

class OR1Row(BaseModel):
    """One marginal tier row of the Pillar 3 OR1 disclosure ($M).

    Reference:
        ERBA NPR §__.150(b); §__.162 Table (operational risk).
    """
    row_number: int = Field(description="OR1 template row number")
    row_label: str = Field(description="Row description")
    bi_amount_usd_m: float = Field(description="BI falling in this tier ($M)")
    bic_amount_usd_m: float = Field(description="BIC contribution ($M)")
    ilm: float = Field(default=ILM, description="No multiplier; shown as 1.0")
    capital_usd_m: float = Field(description="Capital contribution ($M)")
    rwa_usd_m: float = Field(description="RWA contribution ($M)")


class OR1Report(BaseModel):
    """Complete Pillar 3 OR1 disclosure ($M).

    Reference:
        ERBA NPR §__.150; §__.162.
    """
    reporting_date: str = Field(description="Reporting date (YYYY-MM-DD)")
    entity_name: str = Field(description="Reporting entity name")
    rows: list[OR1Row] = Field(default_factory=list, description="Tier rows")
    total_bi_usd_m: float = Field(default=0.0, description="Business Indicator")
    total_bic_usd_m: float = Field(default=0.0, description="BIC")
    total_capital_usd_m: float = Field(default=0.0, description="Capital = BIC")
    total_rwa_usd_m: float = Field(default=0.0, description="RWA = 12.5 x BIC")
    ildc_usd_m: float = Field(
        default=0.0, description="Interest, lease and dividend component"
    )
    noninterest_component_usd_m: float = Field(
        default=0.0, description="Noninterest component"
    )
    services_adjustment_usd_m: float = Field(
        default=0.0, description="0.7 x net service-line income subtracted"
    )
    avg_total_operational_losses_usd_m: float = Field(
        default=0.0, description="Avg3y(total operational losses) added"
    )
    ilm_applied: float = Field(default=ILM, description="Always 1.0")
    notes: list[str] = Field(default_factory=list, description="Disclosure notes")


# =========================================================================
#  FFIEC 101 Schedule A models
# =========================================================================

class FFIEC101OpRiskLine(BaseModel):
    """FFIEC 101 Schedule A operational risk line item ($M)."""
    line_number: str = Field(description="FFIEC 101 line reference")
    line_description: str = Field(description="Line item description")
    amount_usd_m: float = Field(description="Amount in $M")


class FFIEC101OpRiskReport(BaseModel):
    """FFIEC 101 Schedule A operational risk section ($M)."""
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    lines: list[FFIEC101OpRiskLine] = Field(default_factory=list)
    total_oprisk_rwa_usd_m: float = Field(
        default=0.0, description="Total operational risk RWA ($M)"
    )


# =========================================================================
#  FR Y-9C Schedule HC-R models
# =========================================================================

class HCROpRiskSection(BaseModel):
    """FR Y-9C Schedule HC-R operational risk component ($M)."""
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    oprisk_capital_usd_m: float = Field(description="Capital requirement = BIC")
    oprisk_rwa_usd_m: float = Field(description="Operational risk RWA")
    bi_usd_m: float = Field(description="Business Indicator")
    bic_usd_m: float = Field(description="Business Indicator Component")
    ilm: float = Field(default=ILM, description="No multiplier; shown as 1.0")


# =========================================================================
#  Loss data report models
# =========================================================================

class LossDataSummary(BaseModel):
    """Operational loss event data summary for Pillar 3 / FR Y-14Q.

    Reference:
        ERBA NPR §__.150 (loss event data requirements); §__.101 event
        types; §__.162 operational risk table.
    """
    data_years: int = Field(description="Years of loss data held")
    required_years: int = Field(
        default=LOSS_DATA_YEARS, description="Years required by §__.150"
    )
    meets_ten_year_requirement: bool = Field(
        description="Whether the ten-year history requirement is met"
    )
    includes_acquired_entities: bool = Field(
        description="Acquired/merged entity history included"
    )
    total_losses_usd_m: float = Field(description="Total losses over the period")
    average_annual_loss_usd_m: float = Field(description="Average annual loss")
    three_year_average_loss_usd_m: float = Field(
        description="Avg3y(total operational losses) feeding the BI, if derivable"
    )
    event_count: int = Field(description="Loss events at or above threshold")
    largest_loss_usd_m: float = Field(description="Largest single loss event")
    losses_by_event_type: dict[str, float] = Field(
        default_factory=dict, description="Losses by §__.101 event type ($M)"
    )
    loss_threshold_usd: float = Field(
        default=LOSS_COLLECTION_THRESHOLD_USD,
        description="Regulatory per-event collection threshold (absolute USD)",
    )
    collection_threshold_applied_usd: float = Field(
        default=LOSS_COLLECTION_THRESHOLD_USD,
        description="Threshold actually applied by the bank (absolute USD)",
    )


# =========================================================================
#  Report generator
# =========================================================================

class OpRiskReportGenerator:
    """Generates operational risk regulatory reports from an OpRiskResult.

    Usage::

        calc = OpRiskCalculator()
        result = calc.calculate(inputs)
        gen = OpRiskReportGenerator("Bank Name")
        or1 = gen.generate_or1(result, "2026-03-31")

    Reference:
        ERBA NPR §__.150, §__.162; FFIEC 101; FR Y-9C HC-R.
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
        loss_data: OperationalLossData | None = None,
    ) -> OR1Report:
        """Generate the Pillar 3 OR1 disclosure.

        Args:
            result: OpRiskResult from the calculator ($M).
            reporting_date: Reporting date string (YYYY-MM-DD).
            loss_data: Optional loss data for supplementary notes.

        Returns:
            Complete OR1 report.

        Reference:
            ERBA NPR §__.150(b); §__.162.
        """
        bi = result.business_indicator
        buckets = result.capital_charge_by_bucket

        tier_specs = [
            (1, "bucket_1_to_1B", "Tier 1 (BI <= $1B): 12% marginal coefficient",
             min(bi, BIC_THRESHOLD_1_USD_M)),
            (2, "bucket_1B_to_30B", "Tier 2 ($1B < BI <= $30B): 15% marginal coefficient",
             max(0.0, min(bi, BIC_THRESHOLD_2_USD_M) - BIC_THRESHOLD_1_USD_M)),
            (3, "bucket_above_30B", "Tier 3 (BI > $30B): 18% marginal coefficient",
             max(0.0, bi - BIC_THRESHOLD_2_USD_M)),
        ]

        rows: list[OR1Row] = []
        for number, key, label, tier_bi in tier_specs:
            tier_bic = buckets.get(key, 0.0)
            rows.append(OR1Row(
                row_number=number,
                row_label=label,
                bi_amount_usd_m=tier_bi,
                bic_amount_usd_m=tier_bic,
                ilm=result.ilm,
                capital_usd_m=tier_bic,
                rwa_usd_m=tier_bic * RWA_CONVERSION_FACTOR,
            ))

        breakdown = result.bi_component_breakdown
        avg_losses = breakdown.avg_total_operational_losses if breakdown else 0.0

        notes = [
            "RWA = 12.5 x BIC per ERBA NPR §__.150(a); no internal loss "
            "multiplier applies.",
            f"BI inputs averaged over the {BI_AVERAGING_PERIODS} most recent "
            "four-calendar-quarter periods (§__.150(c)).",
            "BIC marginal coefficients 12% / 15% / 18% at $1B / $30B "
            "(§__.150(b); thresholds indexed under §__.4).",
            f"Net income from investment management, investment services and "
            f"non-lending treasury services reduced by "
            f"{SERVICES_NET_INCOME_FACTOR:.0%} (§__.150(c)(1)(ii)): "
            f"${result.services_adjustment:,.1f}M subtracted.",
        ]
        if breakdown is not None and breakdown.ildc_cap_applied:
            notes.append(
                "Interest component capped at 2.25% of average interest-earning "
                "assets (§__.150(c)(1)(i))."
            )
        if loss_data is not None:
            notes.append(
                f"Loss event data: {loss_data.data_years} years held "
                f"({LOSS_DATA_YEARS} required), threshold "
                f"${loss_data.collection_threshold_usd:,.0f}."
            )

        return OR1Report(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            rows=rows,
            total_bi_usd_m=bi,
            total_bic_usd_m=result.bic,
            total_capital_usd_m=result.capital_charge,
            total_rwa_usd_m=result.rwa,
            ildc_usd_m=result.ildc,
            noninterest_component_usd_m=result.noninterest_component,
            services_adjustment_usd_m=result.services_adjustment,
            avg_total_operational_losses_usd_m=avg_losses,
            ilm_applied=result.ilm,
            notes=notes,
        )

    def generate_ffiec101(
        self,
        result: OpRiskResult,
        reporting_date: str,
    ) -> FFIEC101OpRiskReport:
        """Generate the FFIEC 101 Schedule A operational risk section.

        Args:
            result: OpRiskResult from the calculator ($M).
            reporting_date: Reporting date string (YYYY-MM-DD).

        Returns:
            FFIEC 101 operational risk report section.

        Reference:
            FFIEC 101 Schedule A; ERBA NPR §__.150 (preamble p. 200).
        """
        breakdown = result.bi_component_breakdown
        avg_losses = breakdown.avg_total_operational_losses if breakdown else 0.0

        lines: list[FFIEC101OpRiskLine] = [
            FFIEC101OpRiskLine(
                line_number="14a",
                line_description="Business Indicator (BI) — §__.150(c)(1)",
                amount_usd_m=result.business_indicator,
            ),
            FFIEC101OpRiskLine(
                line_number="14b",
                line_description="Interest, lease and dividend component — §__.150(c)(1)(i)",
                amount_usd_m=result.ildc,
            ),
            FFIEC101OpRiskLine(
                line_number="14c",
                line_description="Noninterest component — §__.150(c)(1)(ii)",
                amount_usd_m=result.noninterest_component,
            ),
            FFIEC101OpRiskLine(
                line_number="14d",
                line_description="  of which: 0.7 x net service-line income (subtracted)",
                amount_usd_m=result.services_adjustment,
            ),
            FFIEC101OpRiskLine(
                line_number="14e",
                line_description="  of which: Avg3y total operational losses (added)",
                amount_usd_m=avg_losses,
            ),
            FFIEC101OpRiskLine(
                line_number="14f",
                line_description="Business Indicator Component (BIC) — §__.150(b)",
                amount_usd_m=result.bic,
            ),
            FFIEC101OpRiskLine(
                line_number="14g",
                line_description="Operational risk capital requirement (= BIC)",
                amount_usd_m=result.capital_charge,
            ),
            FFIEC101OpRiskLine(
                line_number="14h",
                line_description="Operational risk RWA (12.5 x BIC) — §__.150(a)",
                amount_usd_m=result.rwa,
            ),
        ]

        return FFIEC101OpRiskReport(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            lines=lines,
            total_oprisk_rwa_usd_m=result.rwa,
        )

    def generate_hcr_section(
        self,
        result: OpRiskResult,
        reporting_date: str,
    ) -> HCROpRiskSection:
        """Generate the FR Y-9C Schedule HC-R operational risk component.

        Args:
            result: OpRiskResult from the calculator ($M).
            reporting_date: Reporting date string (YYYY-MM-DD).

        Returns:
            HC-R operational risk section.

        Reference:
            FR Y-9C Schedule HC-R; ERBA NPR §__.150(a).
        """
        return HCROpRiskSection(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            oprisk_capital_usd_m=result.capital_charge,
            oprisk_rwa_usd_m=result.rwa,
            bi_usd_m=result.business_indicator,
            bic_usd_m=result.bic,
            ilm=result.ilm,
        )

    def generate_loss_data_summary(
        self,
        loss_data: OperationalLossData,
    ) -> LossDataSummary:
        """Summarize operational loss event data for disclosure.

        Args:
            loss_data: Operational loss event data ($M).

        Returns:
            Loss data summary.

        Reference:
            ERBA NPR §__.150 (loss event data requirements); §__.101
            event types; §__.162.
        """
        annual = loss_data.annual_losses
        total = sum(annual)
        n_years = len(annual)
        avg_annual = total / n_years if n_years > 0 else 0.0
        three_year_avg = (
            sum(loss_data.most_recent_period_losses()) / BI_AVERAGING_PERIODS
            if n_years >= BI_AVERAGING_PERIODS
            else 0.0
        )

        by_type: dict[str, float] = {
            (k.value if isinstance(k, LossEventType) else str(k)): v
            for k, v in loss_data.losses_by_event_type.items()
        }

        return LossDataSummary(
            data_years=n_years,
            meets_ten_year_requirement=loss_data.meets_ten_year_requirement,
            includes_acquired_entities=loss_data.includes_acquired_entities,
            total_losses_usd_m=total,
            average_annual_loss_usd_m=avg_annual,
            three_year_average_loss_usd_m=three_year_avg,
            event_count=loss_data.total_loss_events,
            largest_loss_usd_m=loss_data.largest_single_loss,
            losses_by_event_type=by_type,
            collection_threshold_applied_usd=loss_data.collection_threshold_usd,
        )


__all__ = [
    "FFIEC101OpRiskLine",
    "FFIEC101OpRiskReport",
    "HCROpRiskSection",
    "LossDataSummary",
    "OR1Report",
    "OR1Row",
    "OpRiskCalculator",
    "OpRiskReportGenerator",
]
