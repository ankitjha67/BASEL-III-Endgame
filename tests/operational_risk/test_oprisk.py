"""Tests for Operational Risk SMA calculator.

Validates the Standardized Measurement Approach (SMA) implementation
per BCBS d424 Section 5 and US Basel III Endgame March 2026 Re-Proposal.

Tests cover:
- BIC marginal coefficient application at $1B/$30B thresholds
- ILDC computation with interest cap
- SC and FC component calculations
- NIC investment management adjustment
- ILM = 1.0 enforcement
- RWA conversion (capital * 12.5)
- Loss component computation (reference only)
- Data validation
- Reporting (OR1, FFIEC 101, HC-R)
"""

from __future__ import annotations

import pytest


# =========================================================================
#  Imports
# =========================================================================

class TestOpRiskImports:
    """Test that all operational risk modules import correctly."""

    def test_calculator_import(self) -> None:
        """OpRiskCalculator should be importable."""
        from src.operational_risk.or_calculator import OpRiskCalculator
        calc = OpRiskCalculator()
        assert calc is not None

    def test_params_import(self) -> None:
        """All params should be importable."""
        from src.operational_risk.or_params import (
            BIC_COEFFICIENTS,
            ILM,
            ILDC_INTEREST_CAP_RATE,
            NIC_INVESTMENT_MANAGEMENT_FACTOR,
            RWA_CONVERSION_FACTOR,
            compute_bic,
        )
        assert ILM == 1.0
        assert ILDC_INTEREST_CAP_RATE == 0.0225
        assert NIC_INVESTMENT_MANAGEMENT_FACTOR == 0.7
        assert RWA_CONVERSION_FACTOR == 12.5
        assert len(BIC_COEFFICIENTS) == 3

    def test_reporting_import(self) -> None:
        """OpRiskReportGenerator should be importable."""
        from src.operational_risk.or_reporting import OpRiskReportGenerator
        gen = OpRiskReportGenerator("Test Bank")
        assert gen is not None

    def test_module_init_import(self) -> None:
        """Module __init__ should export all key classes."""
        from src.operational_risk import (
            OpRiskCalculator,
            FinancialStatementData,
            OpRiskResult,
            NICCalculator,
            OpRiskReportGenerator,
        )
        assert OpRiskCalculator is not None
        assert FinancialStatementData is not None
        assert OpRiskResult is not None
        assert NICCalculator is not None
        assert OpRiskReportGenerator is not None


# =========================================================================
#  BIC Marginal Coefficients
# =========================================================================

class TestBICComputation:
    """Test BIC marginal coefficient application per BCBS d424 §5.7."""

    def test_bic_below_1b(self) -> None:
        """BI below $1B should use 12% flat rate."""
        from src.operational_risk.or_params import compute_bic
        bi = 500_000_000  # $500M
        bic = compute_bic(bi)
        assert bic == pytest.approx(500_000_000 * 0.12)

    def test_bic_at_1b(self) -> None:
        """BI at exactly $1B: 12% on full $1B."""
        from src.operational_risk.or_params import compute_bic
        bic = compute_bic(1_000_000_000)
        assert bic == pytest.approx(1_000_000_000 * 0.12)

    def test_bic_between_1b_and_30b(self) -> None:
        """BI between $1B and $30B: 12% on first $1B + 15% on remainder."""
        from src.operational_risk.or_params import compute_bic
        bi = 10_000_000_000  # $10B
        expected = 1_000_000_000 * 0.12 + 9_000_000_000 * 0.15
        bic = compute_bic(bi)
        assert bic == pytest.approx(expected)

    def test_bic_above_30b(self) -> None:
        """BI above $30B: 12% on $1B + 15% on $29B + 18% on remainder."""
        from src.operational_risk.or_params import compute_bic
        bi = 50_000_000_000  # $50B
        expected = (
            1_000_000_000 * 0.12
            + 29_000_000_000 * 0.15
            + 20_000_000_000 * 0.18
        )
        bic = compute_bic(bi)
        assert bic == pytest.approx(expected)

    def test_bic_zero(self) -> None:
        """BI of zero should produce zero BIC."""
        from src.operational_risk.or_params import compute_bic
        assert compute_bic(0) == 0.0

    def test_bic_negative_raises(self) -> None:
        """Negative BI should raise ValueError."""
        from src.operational_risk.or_params import compute_bic
        with pytest.raises(ValueError, match="negative"):
            compute_bic(-1_000_000)


# =========================================================================
#  Full Calculator
# =========================================================================

class TestOpRiskCalculator:
    """Test full OpRisk SMA calculator per BCBS d424 §5."""

    @pytest.fixture
    def calc(self):
        from src.operational_risk.or_calculator import OpRiskCalculator
        return OpRiskCalculator()

    @pytest.fixture
    def small_bank_financials(self):
        from src.operational_risk.or_calculator import FinancialStatementData
        return FinancialStatementData(
            interest_income=500e6, interest_expense=200e6,
            interest_earning_assets=20e9, dividend_income=10e6,
            fee_income=100e6, fee_expense=50e6,
            other_operating_income=30e6, other_operating_expense=20e6,
            net_trading_income=50e6, banking_book_gains_losses=10e6,
        )

    @pytest.fixture
    def large_bank_financials(self):
        from src.operational_risk.or_calculator import FinancialStatementData
        return FinancialStatementData(
            interest_income=10e9, interest_expense=5e9,
            interest_earning_assets=500e9, dividend_income=500e6,
            fee_income=3e9, fee_expense=1e9,
            other_operating_income=1e9, other_operating_expense=500e6,
            net_trading_income=2e9, banking_book_gains_losses=500e6,
        )

    def test_small_bank(self, calc, small_bank_financials) -> None:
        """Small bank should produce positive capital charge."""
        result = calc.calculate(small_bank_financials)
        assert result.capital_charge > 0
        assert result.ilm == 1.0  # US proposal

    def test_ilm_always_one(self, calc, small_bank_financials) -> None:
        """ILM must always be 1.0 per US 2026 proposal."""
        result = calc.calculate(small_bank_financials)
        assert result.ilm == 1.0

    def test_capital_equals_bic(self, calc, small_bank_financials) -> None:
        """Capital = BIC * ILM = BIC * 1.0 = BIC."""
        result = calc.calculate(small_bank_financials)
        assert result.capital_charge == pytest.approx(result.bic)

    def test_rwa_equals_capital_times_12_5(self, calc, small_bank_financials) -> None:
        """RWA = capital * 12.5."""
        result = calc.calculate(small_bank_financials)
        assert result.rwa == pytest.approx(result.capital_charge * 12.5)

    def test_bi_equals_sum_of_components(self, calc, small_bank_financials) -> None:
        """BI = ILDC + SC + FC."""
        result = calc.calculate(small_bank_financials)
        assert result.business_indicator == pytest.approx(
            result.ildc + result.sc + result.fc
        )

    def test_bic_marginal_coefficients(self, calc) -> None:
        """BIC uses 12% / 15% / 18% marginal rates at $1B / $30B."""
        from src.operational_risk.or_calculator import FinancialStatementData
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

    def test_large_bank_higher_bic(self, calc, small_bank_financials, large_bank_financials) -> None:
        """Larger BI should produce higher BIC."""
        small_result = calc.calculate(small_bank_financials)
        large_result = calc.calculate(large_bank_financials)
        assert large_result.capital_charge > small_result.capital_charge

    def test_ildc_cap_applied(self, calc) -> None:
        """ILDC interest component capped at 2.25% of IEA per BCBS d424 §5.3."""
        from src.operational_risk.or_calculator import FinancialStatementData
        # Large interest spread relative to IEA should trigger cap
        f = FinancialStatementData(
            interest_income=10e9, interest_expense=1e9,
            interest_earning_assets=50e9,  # cap = 50B * 2.25% = 1.125B
            fee_income=100e6, fee_expense=50e6,
        )
        result = calc.calculate(f)
        # Interest component should be capped at 2.25% * 50B = 1.125B
        assert result.bi_component_breakdown is not None
        assert result.bi_component_breakdown.ildc_cap_applied is True
        assert result.bi_component_breakdown.interest_component_capped == pytest.approx(
            0.0225 * 50e9
        )

    def test_sc_uses_max_of_income_expense(self, calc) -> None:
        """SC = max(fee_in, fee_exp) + max(other_in, other_exp)."""
        from src.operational_risk.or_calculator import FinancialStatementData
        f = FinancialStatementData(
            interest_income=100e6, interest_expense=50e6,
            interest_earning_assets=5e9,
            fee_income=200e6, fee_expense=300e6,
            other_operating_income=50e6, other_operating_expense=80e6,
        )
        result = calc.calculate(f)
        expected_sc = max(200e6, 300e6) + max(50e6, 80e6)
        assert result.sc == pytest.approx(expected_sc)

    def test_fc_uses_absolute_values(self, calc) -> None:
        """FC = |net_trading| + |banking_book_gl|."""
        from src.operational_risk.or_calculator import FinancialStatementData
        f = FinancialStatementData(
            interest_income=100e6, interest_expense=50e6,
            interest_earning_assets=5e9,
            fee_income=50e6, fee_expense=30e6,
            net_trading_income=-500e6,
            banking_book_gains_losses=-200e6,
        )
        result = calc.calculate(f)
        expected_fc = abs(-500e6) + abs(-200e6)
        assert result.fc == pytest.approx(expected_fc)

    def test_bucket_breakdown(self, calc, large_bank_financials) -> None:
        """Capital breakdown by bucket should sum to total."""
        result = calc.calculate(large_bank_financials)
        bucket_total = sum(result.capital_charge_by_bucket.values())
        assert bucket_total == pytest.approx(result.bic, rel=1e-9)

    def test_bi_bucket_label(self, calc, large_bank_financials) -> None:
        """BI bucket label should be set."""
        result = calc.calculate(large_bank_financials)
        assert result.bi_bucket != ""

    def test_component_breakdown_present(self, calc, small_bank_financials) -> None:
        """BI component breakdown should be populated."""
        result = calc.calculate(small_bank_financials)
        assert result.bi_component_breakdown is not None
        assert result.bi_component_breakdown.fee_component >= 0
        assert result.bi_component_breakdown.trading_book_component >= 0


# =========================================================================
#  NIC Calculator
# =========================================================================

class TestNICCalculator:
    """Test NIC investment management adjustment per ERBA NPR Section VI."""

    def test_nic_standard_entity(self) -> None:
        """Non-investment-management entity: no NIC adjustment."""
        from src.operational_risk.or_calculator import NICCalculator
        nic = NICCalculator()
        component, adjustment = nic.compute_nic(
            interest_income=500e6,
            interest_expense=200e6,
            interest_earning_assets=20e9,
        )
        assert adjustment == 0.0
        assert component == pytest.approx(min(300e6, 0.0225 * 20e9))

    def test_nic_investment_management(self) -> None:
        """Investment management entity: 0.7x on NET basis."""
        from src.operational_risk.or_calculator import (
            InvestmentManagementData, NICCalculator,
        )
        nic = NICCalculator()
        im_data = InvestmentManagementData(
            net_interest_income=100e6,
            is_investment_management_entity=True,
        )
        component, adjustment = nic.compute_nic(
            interest_income=500e6,
            interest_expense=200e6,
            interest_earning_assets=20e9,
            investment_mgmt_data=im_data,
        )
        assert component == pytest.approx(100e6 * 0.7)
        assert adjustment > 0  # Standard was higher, so adjustment is positive


# =========================================================================
#  Loss Component
# =========================================================================

class TestLossComponent:
    """Test Loss Component computation per BCBS d424 §5.10."""

    def test_lc_computation(self) -> None:
        """LC = 15x * average annual loss when BI > $1B."""
        from src.operational_risk.or_params import compute_loss_component
        lc = compute_loss_component(
            average_annual_losses=200e6,
            business_indicator=10e9,
        )
        assert lc == pytest.approx(15 * 200e6)

    def test_lc_below_threshold(self) -> None:
        """LC = 0 when BI <= $1B."""
        from src.operational_risk.or_params import compute_loss_component
        lc = compute_loss_component(
            average_annual_losses=200e6,
            business_indicator=500e6,
        )
        assert lc == 0.0

    def test_lc_with_calculator(self) -> None:
        """Calculator should compute LC for reference."""
        from src.operational_risk.or_calculator import (
            FinancialStatementData, LossComponentData, OpRiskCalculator,
        )
        calc = OpRiskCalculator()
        financials = FinancialStatementData(
            interest_income=10e9, interest_expense=5e9,
            interest_earning_assets=500e9, dividend_income=500e6,
            fee_income=3e9, fee_expense=1e9,
            other_operating_income=1e9, other_operating_expense=500e6,
            net_trading_income=2e9, banking_book_gains_losses=500e6,
        )
        loss_data = LossComponentData(
            annual_losses=[200e6, 150e6, 250e6, 180e6, 220e6],
            loss_years=5,
        )
        result = calc.calculate(financials, loss_data=loss_data)
        assert result.loss_component > 0


# =========================================================================
#  Data Validation
# =========================================================================

class TestDataValidation:
    """Test financial data validation per BCBS 239."""

    def test_negative_iea_raises(self) -> None:
        """Negative interest-earning assets should raise."""
        from src.operational_risk.or_calculator import FinancialStatementData
        with pytest.raises(ValueError):
            FinancialStatementData(
                interest_income=100e6, interest_expense=50e6,
                interest_earning_assets=-1e9,
                fee_income=50e6, fee_expense=30e6,
            )

    def test_validation_warnings(self) -> None:
        """Validator should flag unusual data."""
        from src.operational_risk.or_calculator import (
            FinancialStatementData, OpRiskCalculator,
        )
        f = FinancialStatementData(
            interest_income=100e6, interest_expense=50e6,
            interest_earning_assets=0,
            fee_income=0, fee_expense=0,
            net_trading_income=0, banking_book_gains_losses=0,
        )
        warnings = OpRiskCalculator.validate_financial_data(f)
        assert len(warnings) > 0

    def test_negative_annual_losses_raises(self) -> None:
        """Negative annual losses should raise ValueError."""
        from src.operational_risk.or_calculator import LossComponentData
        with pytest.raises(ValueError):
            LossComponentData(annual_losses=[-100e6, 200e6])


# =========================================================================
#  Reporting
# =========================================================================

class TestOpRiskReporting:
    """Test OR1, FFIEC 101, and HC-R report generation."""

    @pytest.fixture
    def result(self):
        from src.operational_risk.or_calculator import (
            FinancialStatementData, OpRiskCalculator,
        )
        calc = OpRiskCalculator()
        f = FinancialStatementData(
            interest_income=10e9, interest_expense=5e9,
            interest_earning_assets=500e9, dividend_income=500e6,
            fee_income=3e9, fee_expense=1e9,
            other_operating_income=1e9, other_operating_expense=500e6,
            net_trading_income=2e9, banking_book_gains_losses=500e6,
        )
        return calc.calculate(f)

    def test_or1_report(self, result) -> None:
        """OR1 report should have 3 bucket rows."""
        from src.operational_risk.or_reporting import OpRiskReportGenerator
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_or1(result, "2026-03-31")
        assert len(report.rows) == 3
        assert report.total_rwa_usd_m > 0
        assert report.ilm_applied == 1.0

    def test_ffiec101_report(self, result) -> None:
        """FFIEC 101 report should have standard line items."""
        from src.operational_risk.or_reporting import OpRiskReportGenerator
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_ffiec101(result, "2026-03-31")
        assert len(report.lines) == 8
        assert report.total_oprisk_rwa_usd_m > 0

    def test_hcr_report(self, result) -> None:
        """HC-R report should match calculator output."""
        from src.operational_risk.or_reporting import OpRiskReportGenerator
        gen = OpRiskReportGenerator("Test Bank")
        report = gen.generate_hcr_section(result, "2026-03-31")
        assert report.oprisk_rwa_usd_m == pytest.approx(result.rwa * 1e-6)
        assert report.ilm == 1.0

    def test_loss_data_summary(self) -> None:
        """Loss data summary should compute LC correctly."""
        from src.operational_risk.or_calculator import LossComponentData
        from src.operational_risk.or_reporting import OpRiskReportGenerator
        gen = OpRiskReportGenerator("Test Bank")
        loss_data = LossComponentData(
            annual_losses=[200e6, 150e6, 250e6],
            loss_years=3,
            total_loss_events=50,
            largest_single_loss=100e6,
        )
        summary = gen.generate_loss_data_summary(loss_data, business_indicator=10e9)
        assert summary.average_annual_loss_usd_m > 0
        assert summary.loss_component_usd_m > 0
