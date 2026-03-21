"""Operational Risk Calculator — Standardized Measurement Approach (SMA).

Implements the operational risk capital charge per BCBS d424 Section 5
and the US Basel III Endgame March 2026 Re-Proposal.

OpRisk_Capital = BIC * ILM

Where:
- BIC = Business Indicator Component (marginal coefficients: 12% / 15% / 18%)
- ILM = Internal Loss Multiplier (1.0 per US proposal — not applied)
- BI = ILDC + SC + FC (Business Indicator)

Components:
- ILDC = Interest, Lease, and Dividend Component (BCBS d424 §5.3)
  = min(|Interest income - Interest expense|, 2.25% * IEA) + Dividends
- SC = Services Component (BCBS d424 §5.4)
  = max(Fee income, Fee expense) + max(Other op income, Other op expense)
- FC = Financial Component (BCBS d424 §5.5)
  = |Net P&L trading book| + |Net P&L banking book|
- NIC = Net Interest Component (ERBA NPR Section VI)
  = Net basis with 0.7x for investment management

Reference: BCBS d424 Section 5, US Fed Basel III Endgame March 2026 Re-Proposal.
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.operational_risk.or_params import (
    BI_AVERAGING_YEARS,
    BIC_BUCKETS,
    BIC_COEFFICIENTS,
    ILDC_INTEREST_CAP_RATE,
    ILM,
    LC_BI_THRESHOLD,
    LC_MULTIPLIER,
    LOSS_DATA_MIN_YEARS,
    LOSS_DATA_YEARS,
    LOSS_THRESHOLD_USD,
    NIC_INVESTMENT_MANAGEMENT_FACTOR,
    RWA_CONVERSION_FACTOR,
    LossEventType,
    compute_bic,
    compute_ilm,
    compute_loss_component,
)


# =========================================================================
#  Input Models
# =========================================================================

class FinancialStatementData(BaseModel):
    """Financial statement inputs for BI calculation per BCBS d424 §5.2.

    All monetary values in USD. Should be 3-year averages where applicable
    per BCBS d424 §5.6.

    Reference:
        BCBS d424 §5.2-5.6; ERBA NPR Section VI.
    """
    interest_income: float = Field(
        description="Gross interest income (BCBS d424 §5.3)"
    )
    interest_expense: float = Field(
        description="Gross interest expense (BCBS d424 §5.3)"
    )
    interest_earning_assets: float = Field(
        description="Total interest-earning assets for ILDC cap (BCBS d424 §5.3)"
    )
    dividend_income: float = Field(
        default=0.0,
        description="Dividend income, included in ILDC (BCBS d424 §5.3)"
    )
    lease_income: float = Field(
        default=0.0,
        description="Lease income, included in ILDC (BCBS d424 §5.3)"
    )
    lease_expense: float = Field(
        default=0.0,
        description="Lease expense, included in ILDC (BCBS d424 §5.3)"
    )
    fee_income: float = Field(
        description="Fee and commission income (BCBS d424 §5.4)"
    )
    fee_expense: float = Field(
        description="Fee and commission expense (BCBS d424 §5.4)"
    )
    other_operating_income: float = Field(
        default=0.0,
        description="Other operating income (BCBS d424 §5.4)"
    )
    other_operating_expense: float = Field(
        default=0.0,
        description="Other operating expense (BCBS d424 §5.4)"
    )
    net_trading_income: float = Field(
        default=0.0,
        description="Net P&L on trading book positions (BCBS d424 §5.5)"
    )
    banking_book_gains_losses: float = Field(
        default=0.0,
        description="Net gains/losses on banking book positions (BCBS d424 §5.5)"
    )
    period_years: int = Field(
        default=3,
        description="Number of years averaged (BCBS d424 §5.6)"
    )

    @field_validator("interest_earning_assets")
    @classmethod
    def iea_must_be_positive(cls, v: float) -> float:
        """Interest-earning assets must be non-negative per BCBS d424 §5.3."""
        if v < 0:
            raise ValueError("Interest-earning assets cannot be negative")
        return v


class InvestmentManagementData(BaseModel):
    """Investment management-specific data for NIC calculation.

    NIC for investment management uses NET basis with 0.7x factor
    per ERBA NPR Section VI, reflecting the lower operational risk
    profile of fee-based investment management activities.

    Reference:
        ERBA NPR Section VI; BCBS d424 §5.3 (modified for US).
    """
    net_interest_income: float = Field(
        description="Net interest income from investment management activities"
    )
    investment_management_revenue: float = Field(
        default=0.0,
        description="Total investment management fee revenue"
    )
    is_investment_management_entity: bool = Field(
        default=False,
        description="Whether entity is primarily an investment manager"
    )


class LossComponentData(BaseModel):
    """Internal loss data for Loss Component (LC) calculation.

    While the US 2026 proposal sets ILM = 1.0 (making LC irrelevant
    for capital computation), loss data is still required for:
    - Pillar 3 disclosure (OR1 template)
    - BCBS 239 data lineage
    - SR 11-7 model governance
    - Potential future ILM activation

    Reference:
        BCBS d424 §5.10; ERBA NPR Section VI.
    """
    annual_losses: list[float] = Field(
        default_factory=list,
        description="Annual operational losses for each year (USD)"
    )
    loss_years: int = Field(
        default=0,
        description="Number of years of loss data available"
    )
    losses_by_event_type: dict[str, float] = Field(
        default_factory=dict,
        description="Aggregate losses by Basel event type (USD)"
    )
    total_loss_events: int = Field(
        default=0,
        description="Total number of loss events above threshold"
    )
    largest_single_loss: float = Field(
        default=0.0,
        description="Largest single operational loss event (USD)"
    )

    @field_validator("annual_losses")
    @classmethod
    def losses_must_be_non_negative(cls, v: list[float]) -> list[float]:
        """All annual loss amounts must be non-negative per BCBS d424 §5.10."""
        for i, loss in enumerate(v):
            if loss < 0:
                raise ValueError(f"Annual loss for year {i} cannot be negative: {loss}")
        return v


# =========================================================================
#  Output Models
# =========================================================================

class BIComponentBreakdown(BaseModel):
    """Detailed breakdown of Business Indicator components.

    Reference:
        BCBS d424 §5.3-5.5.
    """
    interest_component_gross: float = Field(
        description="|Interest income - Interest expense| (BCBS d424 §5.3)"
    )
    interest_component_capped: float = Field(
        description="min(gross, 2.25% * IEA) per BCBS d424 §5.3"
    )
    ildc_cap_applied: bool = Field(
        description="Whether ILDC interest cap was binding"
    )
    dividend_component: float = Field(
        description="Dividend income added to ILDC (BCBS d424 §5.3)"
    )
    lease_component: float = Field(
        description="Net lease income added to ILDC (BCBS d424 §5.3)"
    )
    fee_component: float = Field(
        description="max(fee_income, fee_expense) (BCBS d424 §5.4)"
    )
    other_operating_component: float = Field(
        description="max(other_op_income, other_op_expense) (BCBS d424 §5.4)"
    )
    trading_book_component: float = Field(
        description="|Net P&L trading book| (BCBS d424 §5.5)"
    )
    banking_book_component: float = Field(
        description="|Net P&L banking book| (BCBS d424 §5.5)"
    )


class OpRiskResult(BaseModel):
    """Result of operational risk capital calculation.

    Reference:
        BCBS d424 §5.7; ERBA NPR Section VI.
    """
    business_indicator: float = Field(
        description="BI = ILDC + SC + FC (BCBS d424 §5.2)"
    )
    ildc: float = Field(
        description="Interest, Lease, and Dividend Component (BCBS d424 §5.3)"
    )
    sc: float = Field(
        description="Services Component (BCBS d424 §5.4)"
    )
    fc: float = Field(
        description="Financial Component (BCBS d424 §5.5)"
    )
    bic: float = Field(
        description="Business Indicator Component after marginal rates (BCBS d424 §5.7)"
    )
    ilm: float = Field(
        description="Internal Loss Multiplier (1.0 per US 2026 proposal)"
    )
    capital_charge: float = Field(
        description="BIC * ILM = operational risk capital (BCBS d424 §5.8)"
    )
    rwa: float = Field(
        default=0.0,
        description="OpRisk RWA = capital * 12.5"
    )
    capital_charge_by_bucket: dict[str, float] = Field(
        default_factory=dict,
        description="Capital contribution by BI bucket for reporting"
    )
    bi_component_breakdown: Optional[BIComponentBreakdown] = Field(
        default=None,
        description="Detailed BI component breakdown"
    )
    loss_component: float = Field(
        default=0.0,
        description="Loss Component (LC) — not used for US capital but reported"
    )
    ilm_computed: float = Field(
        default=1.0,
        description="Computed ILM (for reference; US always uses 1.0)"
    )
    nic_adjustment: float = Field(
        default=0.0,
        description="NIC investment management adjustment amount"
    )
    bi_bucket: str = Field(
        default="",
        description="Which BI bucket the bank falls into"
    )


# =========================================================================
#  NIC Calculator
# =========================================================================

class NICCalculator:
    """Net Interest Component calculator for investment management entities.

    NIC for investment management activities uses NET basis (interest income
    minus interest expense) with a 0.7x reduction factor, reflecting the
    lower operational risk profile of fee-based activities.

    Reference:
        ERBA NPR Section VI; BCBS d424 §5.3 (US modification).
    """

    @staticmethod
    def compute_nic(
        interest_income: float,
        interest_expense: float,
        interest_earning_assets: float,
        investment_mgmt_data: Optional[InvestmentManagementData] = None,
    ) -> tuple[float, float]:
        """Compute Net Interest Component with investment management adjustment.

        For investment management entities, NIC is computed on a NET basis
        with a 0.7x factor per ERBA NPR Section VI.

        Args:
            interest_income: Gross interest income in USD.
            interest_expense: Gross interest expense in USD.
            interest_earning_assets: Total interest-earning assets in USD.
            investment_mgmt_data: Optional investment management data.

        Returns:
            Tuple of (adjusted_interest_component, nic_adjustment_amount).

        Reference:
            ERBA NPR Section VI; BCBS d424 §5.3.
        """
        # Standard ILDC interest component: absolute value, capped
        gross_interest = abs(interest_income - interest_expense)
        cap = ILDC_INTEREST_CAP_RATE * interest_earning_assets
        standard_component = min(gross_interest, cap)

        nic_adjustment = 0.0

        if (
            investment_mgmt_data is not None
            and investment_mgmt_data.is_investment_management_entity
        ):
            # NIC on NET basis with 0.7x factor
            net_interest = investment_mgmt_data.net_interest_income
            net_component = abs(net_interest) * NIC_INVESTMENT_MANAGEMENT_FACTOR
            nic_adjustment = standard_component - net_component
            return net_component, nic_adjustment

        return standard_component, nic_adjustment

    @staticmethod
    def compute_nic_for_mixed_entity(
        total_interest_income: float,
        total_interest_expense: float,
        interest_earning_assets: float,
        im_interest_income: float,
        im_interest_expense: float,
        im_proportion: float,
    ) -> tuple[float, float]:
        """Compute NIC for a mixed entity with both banking and investment management.

        For entities that have both traditional banking and investment management
        activities, the NIC adjustment is applied proportionally.

        Args:
            total_interest_income: Total gross interest income in USD.
            total_interest_expense: Total gross interest expense in USD.
            interest_earning_assets: Total interest-earning assets in USD.
            im_interest_income: Investment management interest income in USD.
            im_interest_expense: Investment management interest expense in USD.
            im_proportion: Proportion of revenue from investment management (0 to 1).

        Returns:
            Tuple of (blended_interest_component, nic_adjustment_amount).

        Reference:
            ERBA NPR Section VI; BCBS d424 §5.3 (US modification).
        """
        # Standard component for banking portion
        gross_interest = abs(total_interest_income - total_interest_expense)
        cap = ILDC_INTEREST_CAP_RATE * interest_earning_assets
        standard_component = min(gross_interest, cap)

        # Investment management portion on NET basis with 0.7x
        im_net = abs(im_interest_income - im_interest_expense)
        im_component = im_net * NIC_INVESTMENT_MANAGEMENT_FACTOR

        # Banking portion (standard treatment)
        banking_proportion = 1.0 - im_proportion
        banking_component = standard_component * banking_proportion

        blended = banking_component + im_component * im_proportion
        adjustment = standard_component - blended

        return blended, adjustment


# =========================================================================
#  Main Calculator
# =========================================================================

class OpRiskCalculator:
    """Operational Risk calculator using the Standardized Measurement Approach.

    Implements the full SMA calculation per BCBS d424 Section 5 and
    the US Basel III Endgame March 2026 Re-Proposal.

    The calculation flow:
    1. Compute Business Indicator (BI) = ILDC + SC + FC
    2. Apply marginal BIC coefficients (12% / 15% / 18%)
    3. Multiply by ILM (= 1.0 per US proposal)
    4. RWA = capital * 12.5

    Usage::

        calc = OpRiskCalculator()
        result = calc.calculate(financials)
        print(f"OpRisk capital: {result.capital_charge:,.0f}")
        print(f"OpRisk RWA: {result.rwa:,.0f}")

    Reference:
        BCBS d424 §5.1-5.12; ERBA NPR Section VI.
    """

    def __init__(
        self,
        investment_mgmt_data: Optional[InvestmentManagementData] = None,
        loss_data: Optional[LossComponentData] = None,
    ) -> None:
        """Initialize the calculator with optional investment management and loss data.

        Args:
            investment_mgmt_data: Optional data for NIC investment management adjustment.
            loss_data: Optional internal loss data for LC computation (reference only).
        """
        self._investment_mgmt_data = investment_mgmt_data
        self._loss_data = loss_data
        self._nic_calculator = NICCalculator()

    def calculate(
        self,
        financials: FinancialStatementData,
        investment_mgmt_data: Optional[InvestmentManagementData] = None,
        loss_data: Optional[LossComponentData] = None,
    ) -> OpRiskResult:
        """Calculate operational risk capital charge per SMA.

        Steps per BCBS d424 §5.1-5.8:
        1. Compute ILDC (Interest, Lease, and Dividend Component)
        2. Compute SC (Services Component)
        3. Compute FC (Financial Component)
        4. BI = ILDC + SC + FC
        5. Apply marginal BIC coefficients (12% / 15% / 18%)
        6. Capital = BIC * ILM (ILM = 1.0 per US proposal)
        7. RWA = Capital * 12.5

        Args:
            financials: Financial statement data.
            investment_mgmt_data: Override for investment management data.
            loss_data: Override for internal loss data.

        Returns:
            OpRiskResult with full breakdown.

        Reference:
            BCBS d424 §5.1-5.8; ERBA NPR Section VI.
        """
        im_data = investment_mgmt_data or self._investment_mgmt_data
        lc_data = loss_data or self._loss_data

        # 1. ILDC — Interest, Lease, and Dividend Component (BCBS d424 §5.3)
        ildc, nic_adj, bi_breakdown = self._compute_ildc(financials, im_data)

        # 2. SC — Services Component (BCBS d424 §5.4)
        sc = self._compute_sc(financials)

        # 3. FC — Financial Component (BCBS d424 §5.5)
        fc = self._compute_fc(financials)

        # 4. Business Indicator (BCBS d424 §5.2)
        bi = ildc + sc + fc

        # 5. BIC via marginal coefficients (BCBS d424 §5.7)
        bic = compute_bic(bi)

        # 6. Loss Component (reference only, not used for US capital)
        lc = self._compute_loss_component(lc_data, bi)

        # 7. ILM (always 1.0 under US rules, computed for reference)
        ilm_value = ILM
        ilm_computed = compute_ilm(lc, bic) if bic > 0 else 1.0

        # 8. Capital charge = BIC * ILM (BCBS d424 §5.8)
        capital = bic * ilm_value

        # 9. RWA = Capital * 12.5
        rwa = capital * RWA_CONVERSION_FACTOR

        # Bucket breakdown for reporting
        bucket_breakdown = self._bucket_breakdown(bi)

        # Determine BI bucket
        bi_bucket = self._determine_bi_bucket(bi)

        return OpRiskResult(
            business_indicator=bi,
            ildc=ildc,
            sc=sc,
            fc=fc,
            bic=bic,
            ilm=ilm_value,
            capital_charge=capital,
            rwa=rwa,
            capital_charge_by_bucket=bucket_breakdown,
            bi_component_breakdown=bi_breakdown,
            loss_component=lc,
            ilm_computed=ilm_computed,
            nic_adjustment=nic_adj,
            bi_bucket=bi_bucket,
        )

    def calculate_rwa(self, financials: FinancialStatementData) -> float:
        """Convenience method returning only the RWA amount.

        Args:
            financials: Financial statement data.

        Returns:
            Operational risk RWA in USD (= BIC * ILM * 12.5).

        Reference:
            BCBS d424 §5.8; standard 12.5x conversion.
        """
        result = self.calculate(financials)
        return result.rwa

    def _compute_ildc(
        self,
        financials: FinancialStatementData,
        im_data: Optional[InvestmentManagementData],
    ) -> tuple[float, float, BIComponentBreakdown]:
        """Compute ILDC — Interest, Lease, and Dividend Component.

        ILDC = min(|Interest income - Interest expense|, 2.25% * IEA)
               + Dividend income + |Lease income - Lease expense|

        The interest component is capped at 2.25% of interest-earning assets
        to prevent distortion from maturity transformation activities.

        For investment management entities, NIC adjustment applies:
        NIC = NET basis with 0.7x factor per ERBA NPR Section VI.

        Args:
            financials: Financial statement data.
            im_data: Optional investment management data.

        Returns:
            Tuple of (ildc_value, nic_adjustment, component_breakdown).

        Reference:
            BCBS d424 §5.3; ERBA NPR Section VI.
        """
        # Gross interest component
        gross_interest = abs(financials.interest_income - financials.interest_expense)
        cap = ILDC_INTEREST_CAP_RATE * financials.interest_earning_assets
        capped_interest = min(gross_interest, cap)
        cap_applied = gross_interest > cap

        # NIC adjustment for investment management
        nic_adjustment = 0.0
        interest_component = capped_interest

        if im_data is not None:
            interest_component, nic_adjustment = self._nic_calculator.compute_nic(
                financials.interest_income,
                financials.interest_expense,
                financials.interest_earning_assets,
                im_data,
            )

        # Lease component
        lease_component = abs(financials.lease_income - financials.lease_expense)

        # Dividend component
        dividend_component = financials.dividend_income

        # Total ILDC
        ildc = interest_component + dividend_component + lease_component

        breakdown = BIComponentBreakdown(
            interest_component_gross=gross_interest,
            interest_component_capped=capped_interest,
            ildc_cap_applied=cap_applied,
            dividend_component=dividend_component,
            lease_component=lease_component,
            fee_component=max(financials.fee_income, financials.fee_expense),
            other_operating_component=max(
                financials.other_operating_income,
                financials.other_operating_expense,
            ),
            trading_book_component=abs(financials.net_trading_income),
            banking_book_component=abs(financials.banking_book_gains_losses),
        )

        return ildc, nic_adjustment, breakdown

    @staticmethod
    def _compute_sc(financials: FinancialStatementData) -> float:
        """Compute SC — Services Component per BCBS d424 §5.4.

        SC = max(Fee income, Fee expense)
           + max(Other operating income, Other operating expense)

        Uses the maximum of income vs expense for each sub-component
        to capture the larger of the two directions of activity.

        Args:
            financials: Financial statement data.

        Returns:
            Services Component value in USD.

        Reference:
            BCBS d424 §5.4.
        """
        fee_component = max(financials.fee_income, financials.fee_expense)
        other_component = max(
            financials.other_operating_income,
            financials.other_operating_expense,
        )
        return fee_component + other_component

    @staticmethod
    def _compute_fc(financials: FinancialStatementData) -> float:
        """Compute FC — Financial Component per BCBS d424 §5.5.

        FC = |Net P&L trading book| + |Net P&L banking book|

        Uses absolute values of net gains/losses to capture the
        scale of financial activity regardless of direction.

        Args:
            financials: Financial statement data.

        Returns:
            Financial Component value in USD.

        Reference:
            BCBS d424 §5.5.
        """
        trading_component = abs(financials.net_trading_income)
        banking_component = abs(financials.banking_book_gains_losses)
        return trading_component + banking_component

    @staticmethod
    def _compute_loss_component(
        loss_data: Optional[LossComponentData],
        business_indicator: float,
    ) -> float:
        """Compute Loss Component (LC) per BCBS d424 §5.10.

        LC = 15x * average annual operational losses.
        Only applicable for banks with BI > $1B.
        Under US 2026 proposal, LC is computed for reference only
        (ILM = 1.0, so LC does not affect capital).

        Args:
            loss_data: Internal loss data.
            business_indicator: Total BI in USD.

        Returns:
            Loss Component in USD.

        Reference:
            BCBS d424 §5.10; ERBA NPR Section VI.
        """
        if loss_data is None or not loss_data.annual_losses:
            return 0.0

        avg_annual = sum(loss_data.annual_losses) / len(loss_data.annual_losses)
        return compute_loss_component(avg_annual, business_indicator)

    @staticmethod
    def _bucket_breakdown(bi: float) -> dict[str, float]:
        """Break down BIC by marginal bucket for reporting.

        Args:
            bi: Business Indicator in USD.

        Returns:
            Dictionary mapping bucket name to capital contribution.

        Reference:
            BCBS d424 §5.7, Table 1.
        """
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

    @staticmethod
    def _determine_bi_bucket(bi: float) -> str:
        """Determine which BI bucket the bank falls into.

        Args:
            bi: Business Indicator in USD.

        Returns:
            Human-readable bucket label.

        Reference:
            BCBS d424 §5.7, Table 1.
        """
        for bucket in BIC_BUCKETS:
            if bi <= bucket.ceiling_usd:
                return bucket.bucket_label
        return BIC_BUCKETS[-1].bucket_label

    @staticmethod
    def validate_financial_data(financials: FinancialStatementData) -> list[str]:
        """Validate financial statement data for completeness and consistency.

        Performs data quality checks per BCBS 239 requirements:
        - Non-negative asset values
        - Reasonable ranges for income/expense ratios
        - Consistency between related fields

        Args:
            financials: Financial statement data to validate.

        Returns:
            List of warning messages (empty if all checks pass).

        Reference:
            BCBS 239; SR 11-7 model governance.
        """
        warnings: list[str] = []

        if financials.interest_earning_assets <= 0:
            warnings.append(
                "Interest-earning assets is zero or negative — "
                "ILDC cap cannot be properly applied"
            )

        if financials.interest_income < 0:
            warnings.append("Interest income is negative — verify data")

        if financials.interest_expense < 0:
            warnings.append("Interest expense is negative — verify data")

        # Check if interest spread is unreasonably large
        if financials.interest_earning_assets > 0:
            nim = (
                (financials.interest_income - financials.interest_expense)
                / financials.interest_earning_assets
            )
            if abs(nim) > 0.10:  # NIM > 10% is unusual
                warnings.append(
                    f"Net interest margin ({nim:.2%}) exceeds 10% — verify data"
                )

        # Check for zero BI components (may indicate missing data)
        if financials.fee_income == 0 and financials.fee_expense == 0:
            warnings.append(
                "Both fee income and fee expense are zero — "
                "verify SC data completeness"
            )

        if (
            financials.net_trading_income == 0
            and financials.banking_book_gains_losses == 0
        ):
            warnings.append(
                "Both trading and banking book P&L are zero — "
                "verify FC data completeness"
            )

        return warnings
