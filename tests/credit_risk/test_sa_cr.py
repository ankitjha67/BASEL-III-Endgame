"""Tests for Credit Risk Standardized Approach (SA-CR)."""

from __future__ import annotations

import pytest


class TestSACRImports:
    def test_exposure_classes_import(self):
        from src.credit_risk.sa.exposure_classes import ExposureClass
        assert ExposureClass is not None

    def test_risk_weights_import(self):
        from src.credit_risk.sa.risk_weights import get_risk_weight
        assert get_risk_weight is not None

    def test_calculator_import(self):
        from src.credit_risk.sa.calculator import SACRCalculator
        calc = SACRCalculator()
        assert calc is not None


class TestSACRRiskWeights:
    def test_sovereign_us_zero(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[0] == 0.0  # CRC 0 = 0%

    def test_corporate_ig(self):
        from src.credit_risk.sa.risk_weights import CORPORATE_IG_RW
        assert CORPORATE_IG_RW == 0.65

    def test_retail_transactor(self):
        from src.credit_risk.sa.risk_weights import RETAIL_TRANSACTOR_RW
        assert RETAIL_TRANSACTOR_RW == 0.45

    def test_defaulted(self):
        from src.credit_risk.sa.risk_weights import DEFAULTED_RW
        assert DEFAULTED_RW == 1.50


class TestSACRCalculator:
    @pytest.fixture
    def calc(self):
        from src.credit_risk.sa.calculator import SACRCalculator
        return SACRCalculator()

    def test_single_corporate_exposure(self, calc):
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE,
            counterparty="CORP_A", ead=10_000_000.0,
        )
        result = calc.calculate([exp])
        assert result.total_rwa > 0
        assert result.total_rwa == pytest.approx(10_000_000.0 * 1.00, rel=0.01)

    def test_ig_corporate_lower_rw(self, calc):
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        standard = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE,
            counterparty="A", ead=10e6,
        )
        ig = CreditExposure(
            exposure_id="2", exposure_class=ExposureClass.CORPORATE,
            counterparty="B", ead=10e6, is_investment_grade=True,
        )
        std_result = calc.calculate([standard])
        ig_result = calc.calculate([ig])
        assert ig_result.total_rwa < std_result.total_rwa

    def test_retail_standard(self, calc):
        """Retail exposure gets 75% RW."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.RETAIL,
            counterparty="RETAIL_A", ead=1_000_000.0,
        )
        result = calc.calculate([exp])
        # Standard retail: 75% RW
        assert result.total_rwa == pytest.approx(1_000_000.0 * 0.75, rel=0.05)

    def test_empty_portfolio(self, calc):
        result = calc.calculate([])
        assert result.total_rwa == 0.0

    def test_multi_class_portfolio(self, calc):
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exposures = [
            CreditExposure(exposure_id="1", exposure_class=ExposureClass.CORPORATE,
                          counterparty="A", ead=50e6),
            CreditExposure(exposure_id="2", exposure_class=ExposureClass.RETAIL,
                          counterparty="B", ead=10e6),
            CreditExposure(exposure_id="3", exposure_class=ExposureClass.RESIDENTIAL_MORTGAGE,
                          counterparty="C", ead=5e6, ltv_ratio=0.60),
        ]
        result = calc.calculate(exposures)
        assert result.total_rwa > 0
        assert result.total_ead == pytest.approx(65e6, rel=0.01)
