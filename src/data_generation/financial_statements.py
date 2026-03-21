"""Financial Statement Generator — Synthetic income/balance sheet for OpRisk.

Generates realistic financial statements for a $3.2T Category I G-SIB
with 3-year historical data for Business Indicator calculation.

All amounts in USD millions ($M).

References:
    - FR Y-9C Schedule HI: Consolidated Income Statement
    - FR Y-9C Schedule HC: Consolidated Balance Sheet
    - BCBS d424 Section 5: Operational risk — Business Indicator
    - ERBA NPR pp. 250-270: Operational risk framework
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class IncomeStatement:
    """Annual income statement for a G-SIB.

    Maps to FR Y-9C Schedule HI.
    All amounts in $M.

    Reference: FR Y-9C Schedule HI.
    """
    year: int
    # Interest income/expense
    interest_income: float = 0.0
    interest_expense: float = 0.0
    net_interest_income: float = 0.0  # NII = II - IE
    # Non-interest income
    fee_income: float = 0.0
    fee_expense: float = 0.0
    trading_revenue: float = 0.0
    other_operating_income: float = 0.0
    total_non_interest_income: float = 0.0
    # Non-interest expense
    total_non_interest_expense: float = 0.0
    # Provisions
    provision_for_credit_losses: float = 0.0
    # P&L
    pre_tax_income: float = 0.0
    tax_expense: float = 0.0
    net_income: float = 0.0
    # Trading book P&L (for FC component)
    trading_book_pl: float = 0.0
    banking_book_pl: float = 0.0


@dataclass
class BalanceSheet:
    """Annual balance sheet for a G-SIB.

    Maps to FR Y-9C Schedule HC.
    All amounts in $M.

    Reference: FR Y-9C Schedule HC.
    """
    year: int
    # Assets
    cash_and_due_from: float = 0.0
    fed_funds_sold: float = 0.0
    securities_afs: float = 0.0
    securities_htm: float = 0.0
    total_loans: float = 0.0
    allowance_for_credit_losses: float = 0.0
    net_loans: float = 0.0
    trading_assets: float = 0.0
    premises_and_equipment: float = 0.0
    goodwill: float = 0.0
    other_intangibles: float = 0.0
    other_assets: float = 0.0
    total_assets: float = 0.0
    # Liabilities
    total_deposits: float = 0.0
    fed_funds_purchased: float = 0.0
    trading_liabilities: float = 0.0
    subordinated_debt: float = 0.0
    other_liabilities: float = 0.0
    total_liabilities: float = 0.0
    # Equity
    common_stock: float = 0.0
    surplus: float = 0.0
    retained_earnings: float = 0.0
    aoci: float = 0.0
    treasury_stock: float = 0.0
    total_equity: float = 0.0


@dataclass
class BusinessIndicatorData:
    """Business Indicator components for Operational Risk.

    BI = ILDC + SC + FC, computed from 3-year average.

    Reference: BCBS d424 Section 5, ERBA NPR pp. 250-260.
    """
    year: int
    # Interest, Lease, and Dividend Component (ILDC)
    interest_income: float = 0.0
    interest_expense: float = 0.0
    lease_income: float = 0.0
    dividend_income: float = 0.0
    ildc: float = 0.0  # = abs(II - IE) + lease + dividend
    # Services Component (SC)
    fee_income: float = 0.0
    fee_expense: float = 0.0
    other_operating_income: float = 0.0
    other_operating_expense: float = 0.0
    sc: float = 0.0  # = max(fee_inc, fee_exp) + max(other_inc, other_exp)
    # Financial Component (FC)
    net_pl_trading: float = 0.0
    net_pl_banking: float = 0.0
    fc: float = 0.0  # = abs(net_pl_trading) + abs(net_pl_banking)
    # Total
    business_indicator: float = 0.0  # = ILDC + SC + FC
    # NIC adjustment
    is_investment_management: bool = False
    nic_factor: float = 1.0  # 0.7 for investment management per CLAUDE.md


# =========================================================================
#  Financial Statement Generator
# =========================================================================

class FinancialStatementGenerator:
    """Generate realistic financial statements for a $3.2T G-SIB.

    Produces 3 years of income statements, balance sheets, and
    Business Indicator data for operational risk calculation.

    Balance sheet: $3.2T total assets
    - Loans: $1.0T, Securities: $800B, Trading: $500B, Cash: $600B
    - Deposits: $2.0T, Equity: $250B

    Reference: FR Y-9C, BCBS d424 Section 5.
    """

    def __init__(self, seed: int = 42) -> None:
        """Initialize with fixed random seed.

        Args:
            seed: Random seed.
        """
        self.rng = np.random.default_rng(seed)

    def generate_income_statements(
        self, years: list[int] = [2023, 2024, 2025]
    ) -> list[IncomeStatement]:
        """Generate 3 years of income statements.

        Typical G-SIB metrics:
        - NII: ~$60-70B (2% of avg assets)
        - Non-interest income: ~$25-30B
        - Non-interest expense: ~$55-60B
        - Net income: ~$25-35B

        Args:
            years: Years to generate.

        Returns:
            List of IncomeStatement.

        Reference: FR Y-9C Schedule HI.
        """
        statements: list[IncomeStatement] = []
        base_ii = 100_000.0  # $100B interest income
        base_ie = 35_000.0   # $35B interest expense

        for i, year in enumerate(years):
            growth = 1.0 + 0.03 * i + self.rng.random() * 0.02
            ii = base_ii * growth
            ie = base_ie * growth * (1.0 + self.rng.random() * 0.05)
            nii = ii - ie

            fee_inc = 18_000.0 * growth * (1.0 + self.rng.random() * 0.03)
            fee_exp = 5_000.0 * growth
            trading = 8_000.0 * (0.7 + self.rng.random() * 0.6)
            other_inc = 4_000.0 * growth

            total_nonint_inc = fee_inc - fee_exp + trading + other_inc
            total_nonint_exp = 58_000.0 * growth * (1.0 + self.rng.random() * 0.02)

            provision = 8_000.0 * (0.5 + self.rng.random())
            pre_tax = nii + total_nonint_inc - total_nonint_exp - provision
            tax = max(0.0, pre_tax * 0.21)

            trading_pl = trading * (0.8 + self.rng.random() * 0.4)
            banking_pl = 2_000.0 * (self.rng.random() - 0.3)

            statements.append(IncomeStatement(
                year=year,
                interest_income=ii,
                interest_expense=ie,
                net_interest_income=nii,
                fee_income=fee_inc,
                fee_expense=fee_exp,
                trading_revenue=trading,
                other_operating_income=other_inc,
                total_non_interest_income=total_nonint_inc,
                total_non_interest_expense=total_nonint_exp,
                provision_for_credit_losses=provision,
                pre_tax_income=pre_tax,
                tax_expense=tax,
                net_income=pre_tax - tax,
                trading_book_pl=trading_pl,
                banking_book_pl=banking_pl,
            ))

        return statements

    def generate_balance_sheets(
        self, years: list[int] = [2023, 2024, 2025]
    ) -> list[BalanceSheet]:
        """Generate 3 years of balance sheets.

        Total assets: ~$3.2T, growing ~3% per year.

        Args:
            years: Years to generate.

        Returns:
            List of BalanceSheet.

        Reference: FR Y-9C Schedule HC.
        """
        sheets: list[BalanceSheet] = []
        base_assets = 3_200_000.0

        for i, year in enumerate(years):
            growth = 1.0 + 0.03 * i
            ta = base_assets * growth

            loans = 1_000_000.0 * growth
            acl = loans * 0.015
            securities = 800_000.0 * growth
            trading = 500_000.0 * (growth + self.rng.random() * 0.02)
            cash = ta - loans - securities - trading - 100_000.0
            goodwill = 30_000.0
            intangibles = 5_000.0
            other = 100_000.0 - goodwill - intangibles

            deposits = 2_000_000.0 * growth
            sub_debt = 50_000.0
            equity = 250_000.0 * growth
            other_liab = ta - deposits - sub_debt - equity

            sheets.append(BalanceSheet(
                year=year,
                cash_and_due_from=cash,
                securities_afs=securities * 0.6,
                securities_htm=securities * 0.4,
                total_loans=loans,
                allowance_for_credit_losses=acl,
                net_loans=loans - acl,
                trading_assets=trading,
                goodwill=goodwill,
                other_intangibles=intangibles,
                other_assets=other,
                total_assets=ta,
                total_deposits=deposits,
                subordinated_debt=sub_debt,
                other_liabilities=other_liab,
                total_liabilities=ta - equity,
                common_stock=25_000.0,
                surplus=85_000.0,
                retained_earnings=95_000.0 * growth,
                aoci=-3_000.0 * (1.0 + self.rng.random()),
                treasury_stock=5_000.0,
                total_equity=equity,
            ))

        return sheets

    def generate_business_indicator_data(
        self,
        income_statements: Optional[list[IncomeStatement]] = None,
        years: list[int] = [2023, 2024, 2025],
    ) -> list[BusinessIndicatorData]:
        """Generate Business Indicator data for Operational Risk.

        BI = ILDC + SC + FC per BCBS d424 Section 5.
        NIC uses NET basis with 0.7x factor for investment management per CLAUDE.md.

        Args:
            income_statements: Income statements to derive BI from.
            years: Years.

        Returns:
            List of BusinessIndicatorData.

        Reference: BCBS d424 Section 5, ERBA NPR pp. 250-260.
        """
        if income_statements is None:
            income_statements = self.generate_income_statements(years)

        bi_data: list[BusinessIndicatorData] = []

        for stmt in income_statements:
            lease_inc = 500.0 + self.rng.random() * 200.0
            div_inc = 1_000.0 + self.rng.random() * 500.0

            # ILDC = abs(II - IE) + lease + dividend
            ildc = abs(stmt.interest_income - stmt.interest_expense) + lease_inc + div_inc

            # SC = max(fee_income, fee_expense) + max(other_operating_income, other_operating_expense)
            other_exp = stmt.total_non_interest_expense * 0.1
            sc = max(stmt.fee_income, stmt.fee_expense) + max(stmt.other_operating_income, other_exp)

            # FC = abs(net_pl_trading) + abs(net_pl_banking)
            fc = abs(stmt.trading_book_pl) + abs(stmt.banking_book_pl)

            bi = ildc + sc + fc

            bi_data.append(BusinessIndicatorData(
                year=stmt.year,
                interest_income=stmt.interest_income,
                interest_expense=stmt.interest_expense,
                lease_income=lease_inc,
                dividend_income=div_inc,
                ildc=ildc,
                fee_income=stmt.fee_income,
                fee_expense=stmt.fee_expense,
                other_operating_income=stmt.other_operating_income,
                other_operating_expense=other_exp,
                sc=sc,
                net_pl_trading=stmt.trading_book_pl,
                net_pl_banking=stmt.banking_book_pl,
                fc=fc,
                business_indicator=bi,
                nic_factor=1.0,  # Not investment management
            ))

        return bi_data

    def generate_all(self, years: list[int] = [2023, 2024, 2025]) -> dict[str, object]:
        """Generate all financial data.

        Returns:
            Dictionary with income statements, balance sheets, and BI data.
        """
        income = self.generate_income_statements(years)
        balance = self.generate_balance_sheets(years)
        bi = self.generate_business_indicator_data(income, years)
        return {
            "income_statements": income,
            "balance_sheets": balance,
            "business_indicator_data": bi,
        }
