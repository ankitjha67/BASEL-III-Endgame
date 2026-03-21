"""Tests for Operational Risk SMA calculator."""

from __future__ import annotations

import pytest


class TestOpRiskImports:
    def test_calculator_import(self):
        from src.operational_risk.or_calculator import OpRiskCalculator
        calc = OpRiskCalculator()
        assert calc is not None


class TestOpRiskCalculator:
    @pytest.fixture
    def calc(self):
        from src.operational_risk.or_calculator import OpRiskCalculator
        return OpRiskCalculator()

    def test_small_bank(self, calc):
        from src.operational_risk.or_calculator import FinancialStatementData
        f = FinancialStatementData(
            interest_income=500e6, interest_expense=200e6,
            interest_earning_assets=20e9, dividend_income=10e6,
            fee_income=100e6, fee_expense=50e6,
            other_operating_income=30e6, other_operating_expense=20e6,
            net_trading_income=50e6, banking_book_gains_losses=10e6,
        )
        result = calc.calculate(f)
        assert result.capital_charge > 0
        assert result.ilm == 1.0  # US proposal

    def test_bic_marginal_coefficients(self, calc):
        """BIC uses 12% / 15% / 18% marginal rates at $1B / $30B."""
        from src.operational_risk.or_calculator import FinancialStatementData
        # Small BI (< $1B)
        small = FinancialStatementData(
            interest_income=100e6, interest_expense=50e6,
            interest_earning_assets=5e9, dividend_income=5e6,
            fee_income=30e6, fee_expense=10e6,
            other_operating_income=10e6, other_operating_expense=5e6,
            net_trading_income=10e6, banking_book_gains_losses=5e6,
        )
        result = calc.calculate(small)
        assert result.business_indicator > 0
        assert result.bic > 0
        assert result.capital_charge > 0

    def test_large_bank_higher_bic(self, calc):
        """Larger BI should produce higher BIC."""
        from src.operational_risk.or_calculator import FinancialStatementData
        small = FinancialStatementData(
            interest_income=100e6, interest_expense=50e6,
            interest_earning_assets=5e9, dividend_income=5e6,
            fee_income=30e6, fee_expense=10e6,
            other_operating_income=10e6, other_operating_expense=5e6,
            net_trading_income=10e6, banking_book_gains_losses=5e6,
        )
        large = FinancialStatementData(
            interest_income=10e9, interest_expense=5e9,
            interest_earning_assets=500e9, dividend_income=500e6,
            fee_income=3e9, fee_expense=1e9,
            other_operating_income=1e9, other_operating_expense=500e6,
            net_trading_income=2e9, banking_book_gains_losses=500e6,
        )
        small_result = calc.calculate(small)
        large_result = calc.calculate(large)
        assert large_result.capital_charge > small_result.capital_charge
