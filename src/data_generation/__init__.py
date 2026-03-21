"""Data Generation Module — Synthetic portfolio and financial statement generators.

Generates realistic synthetic data for a $3.2T Category I US G-SIB.

References:
    - FR Y-9C: Consolidated Financial Statements
    - FR Y-14A/Q: Capital Assessment data templates
"""

from src.data_generation.portfolio_generator import (
    PortfolioGenerator,
    CreditPortfolio,
    TradingBookPortfolio,
    CounterpartyPortfolio,
    SecuritizationPortfolio,
)
from src.data_generation.financial_statements import (
    FinancialStatementGenerator,
    IncomeStatement,
    BalanceSheet,
    BusinessIndicatorData,
)

__all__ = [
    "PortfolioGenerator",
    "CreditPortfolio",
    "TradingBookPortfolio",
    "CounterpartyPortfolio",
    "SecuritizationPortfolio",
    "FinancialStatementGenerator",
    "IncomeStatement",
    "BalanceSheet",
    "BusinessIndicatorData",
]
