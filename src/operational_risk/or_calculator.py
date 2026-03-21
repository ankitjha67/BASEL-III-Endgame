"""Operational Risk Calculator — Standardized Measurement Approach (SMA).

Implements the operational risk capital charge per BCBS d424
and the US Basel III Endgame Final Rule.

OpRisk_Capital = BIC * ILM

Where:
- BIC = Business Indicator Component (marginal coefficients: 12% / 15% / 18%)
- ILM = Internal Loss Multiplier (1.0 per US proposal — not applied)
- BI = ILDC + SC + FC (Business Indicator)

Reference: BCBS d424 Section 5, US Fed Basel III Endgame Final Rule.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.operational_risk.or_params import (
    BIC_COEFFICIENTS,
    ILDC_INTEREST_CAP_RATE,
    ILM,
    NIC_INVESTMENT_MANAGEMENT_FACTOR,
    compute_bic,
)


# =========================================================================
#  Models
# =========================================================================

class FinancialStatementData(BaseModel):
    """Financial statement inputs for BI calculation.

    All values in USD. Should be 3-year averages where applicable.
    """
    interest_income: float = Field(description="Gross interest income")
    interest_expense: float = Field(description="Gross interest expense")
    interest_earning_assets: float = Field(description="Total interest-earning assets")
    dividend_income: float = Field(default=0.0, description="Dividend income")
    fee_income: float = Field(description="Fee and commission income")
    fee_expense: float = Field(description="Fee and commission expense")
    other_operating_income: float = Field(default=0.0, description="Other operating income")
    other_operating_expense: float = Field(default=0.0, description="Other operating expense")
    net_trading_income: float = Field(default=0.0, description="Net P&L on trading book")
    banking_book_gains_losses: float = Field(
        default=0.0, description="Net gains/losses on banking book positions"
    )
    period_years: int = Field(default=3, description="Number of years averaged")


class OpRiskResult(BaseModel):
    """Result of operational risk capital calculation."""
    business_indicator: float = Field(description="BI = ILDC + SC + FC")
    ildc: float = Field(description="Interest, Lease, and Dividend Component")
    sc: float = Field(description="Services Component")
    fc: float = Field(description="Financial Component")
    bic: float = Field(description="Business Indicator Component (after marginal rates)")
    ilm: float = Field(description="Internal Loss Multiplier (1.0 per US proposal)")
    capital_charge: float = Field(description="BIC * ILM")
    capital_charge_by_bucket: dict[str, float] = Field(
        default_factory=dict, description="Capital by BI bucket"
    )


# =========================================================================
#  Calculator
# =========================================================================

class OpRiskCalculator:
    """Operational Risk calculator using the Standardized Measurement Approach.

    Usage::

        calc = OpRiskCalculator()
        result = calc.calculate(financials)
        print(f"OpRisk capital: {result.capital_charge:,.0f}")
    """

    def calculate(self, financials: FinancialStatementData) -> OpRiskResult:
        """Calculate operational risk capital charge.

        Steps:
        1. Compute Business Indicator (BI) = ILDC + SC + FC
        2. Apply marginal BIC coefficients (12% / 15% / 18%)
        3. Multiply by ILM (= 1.0 per US proposal)

        Args:
            financials: Financial statement data.

        Returns:
            OpRiskResult with full breakdown.
        """
        # 1. ILDC — Interest, Lease, and Dividend Component (BCBS d424 §5.3)
        interest_component = min(
            abs(financials.interest_income - financials.interest_expense),
            ILDC_INTEREST_CAP_RATE * financials.interest_earning_assets,
        )
        ildc = interest_component + financials.dividend_income

        # 2. SC — Services Component (BCBS d424 §5.4)
        sc = (
            max(financials.fee_income, financials.fee_expense)
            + max(financials.other_operating_income, financials.other_operating_expense)
        )

        # 3. FC — Financial Component (BCBS d424 §5.5)
        fc = (
            abs(financials.net_trading_income)
            + abs(financials.banking_book_gains_losses)
        )

        # 4. Business Indicator
        bi = ildc + sc + fc

        # 5. BIC via marginal coefficients
        bic = compute_bic(bi)

        # 6. Capital charge = BIC * ILM
        capital = bic * ILM

        # Bucket breakdown for reporting
        bucket_breakdown = self._bucket_breakdown(bi)

        return OpRiskResult(
            business_indicator=bi,
            ildc=ildc,
            sc=sc,
            fc=fc,
            bic=bic,
            ilm=ILM,
            capital_charge=capital,
            capital_charge_by_bucket=bucket_breakdown,
        )

    @staticmethod
    def _bucket_breakdown(bi: float) -> dict[str, float]:
        """Break down BIC by marginal bucket."""
        breakdown: dict[str, float] = {}
        remaining = bi
        prev_ceiling = 0.0

        bucket_names = ["bucket_1_to_1B", "bucket_1B_to_30B", "bucket_above_30B"]

        for i, (ceiling, coefficient) in enumerate(BIC_COEFFICIENTS):
            bucket_size = min(remaining, ceiling - prev_ceiling)
            if bucket_size <= 0:
                break
            name = bucket_names[i] if i < len(bucket_names) else f"bucket_{i}"
            breakdown[name] = bucket_size * coefficient
            remaining -= bucket_size
            prev_ceiling = ceiling

        return breakdown
