"""Tests for Credit Risk Standardized Approach (SA-CR).

Validates risk weight assignments, calculator logic, exposure classification,
and CRM integration per 12 CFR 217 Subpart E and BCBS CRE20-22.
"""

from __future__ import annotations

import pytest


# =========================================================================
#  Import Tests
# =========================================================================

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


# =========================================================================
#  Sovereign Risk Weight Constants
# =========================================================================

class TestSovereignRiskWeights:
    """Per 12 CFR 217, Subpart E — Sovereign risk weights by CRC."""

    def test_crc_0_zero_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[0] == 0.0

    def test_crc_1_zero_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[1] == 0.0

    def test_crc_2_twenty_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[2] == 0.20

    def test_crc_3_fifty_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[3] == 0.50

    def test_crc_4_hundred_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[4] == 1.00

    def test_crc_5_hundred_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[5] == 1.00

    def test_crc_6_one_fifty_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[6] == 1.50

    def test_crc_7_one_fifty_pct(self):
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[7] == 1.50


# =========================================================================
#  Corporate Risk Weight Constants
# =========================================================================

class TestCorporateRiskWeights:
    """Per Dodd-Frank §939A and 12 CFR 217 — no external ratings."""

    def test_ig_self_assessed_65_pct(self):
        """Corporate IG = 65% per 2026 re-proposal (self-assessed)."""
        from src.credit_risk.sa.risk_weights import CORPORATE_IG_RW
        assert CORPORATE_IG_RW == 0.65

    def test_standard_100_pct(self):
        from src.credit_risk.sa.risk_weights import CORPORATE_STANDARD_RW
        assert CORPORATE_STANDARD_RW == 1.00

    def test_sme_85_pct(self):
        from src.credit_risk.sa.risk_weights import CORPORATE_SME_RW
        assert CORPORATE_SME_RW == 0.85


# =========================================================================
#  Retail Risk Weight Constants
# =========================================================================

class TestRetailRiskWeights:
    """Per 12 CFR 217 — retail exposure risk weights."""

    def test_standard_retail_75_pct(self):
        from src.credit_risk.sa.risk_weights import RETAIL_RW
        assert RETAIL_RW == 0.75

    def test_transactor_45_pct(self):
        """Retail transactor = 45% per 2026 re-proposal (NOT 55%)."""
        from src.credit_risk.sa.risk_weights import RETAIL_TRANSACTOR_RW
        assert RETAIL_TRANSACTOR_RW == 0.45


# =========================================================================
#  Real Estate Risk Weight Constants (actual LTV bucket keys)
# =========================================================================

class TestRealEstateRiskWeights:
    """Per 12 CFR 217, Subpart E — LTV-based risk weights."""

    def test_resi_ltv_0_50(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["0-50"] == 0.40

    def test_resi_ltv_50_60(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["50-60"] == 0.45

    def test_resi_ltv_60_70(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["60-70"] == 0.50

    def test_resi_ltv_70_80(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["70-80"] == 0.60

    def test_resi_ltv_80_90(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["80-90"] == 0.70

    def test_resi_ltv_90_100(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["90-100"] == 0.80

    def test_resi_ltv_above_100(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["100+"] == 0.90

    def test_cre_ltv_0_60(self):
        from src.credit_risk.sa.risk_weights import CRE_INCOME_PRODUCING_RW
        assert CRE_INCOME_PRODUCING_RW["0-60"] == 0.70

    def test_cre_ltv_60_80(self):
        from src.credit_risk.sa.risk_weights import CRE_INCOME_PRODUCING_RW
        assert CRE_INCOME_PRODUCING_RW["60-80"] == 0.90

    def test_cre_ltv_above_80(self):
        from src.credit_risk.sa.risk_weights import CRE_INCOME_PRODUCING_RW
        assert CRE_INCOME_PRODUCING_RW["80+"] == 1.10


# =========================================================================
#  Special Exposure Risk Weight Constants
# =========================================================================

class TestSpecialExposureRiskWeights:
    """Per 12 CFR 217 — special exposure class risk weights."""

    def test_defaulted_150_pct(self):
        from src.credit_risk.sa.risk_weights import DEFAULTED_RW
        assert DEFAULTED_RW == 1.50

    def test_msa_250_pct(self):
        """MSA = 250% RW (deduction removed per 2026 re-proposal)."""
        from src.credit_risk.sa.risk_weights import MSA_RW
        assert MSA_RW == 2.50

    def test_adc_150_pct(self):
        from src.credit_risk.sa.risk_weights import CRE_ADC_RW
        assert CRE_ADC_RW == 1.50

    def test_hvcre_150_pct(self):
        from src.credit_risk.sa.risk_weights import HVCRE_RW
        assert HVCRE_RW == 1.50

    def test_cash_zero_pct(self):
        from src.credit_risk.sa.risk_weights import CASH_RW
        assert CASH_RW == 0.0

    def test_equity_public_250_pct(self):
        from src.credit_risk.sa.risk_weights import EQUITY_PUBLIC_TRADED_RW
        assert EQUITY_PUBLIC_TRADED_RW == 2.50

    def test_equity_speculative_400_pct(self):
        from src.credit_risk.sa.risk_weights import EQUITY_SPECULATIVE_RW
        assert EQUITY_SPECULATIVE_RW == 4.00

    def test_subordinated_debt_150_pct(self):
        from src.credit_risk.sa.risk_weights import SUBORDINATED_DEBT_RW
        assert SUBORDINATED_DEBT_RW == 1.50


# =========================================================================
#  Risk Weight Lookup Function
# =========================================================================

class TestGetRiskWeight:
    """Test the unified get_risk_weight() dispatcher."""

    def test_sovereign_us(self):
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.SOVEREIGN,
            country_risk_class=0,
            is_us_sovereign=True,
        )
        assert get_risk_weight(rw_input) == pytest.approx(0.0)

    def test_corporate_ig_via_lookup(self):
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.CORPORATE,
            is_investment_grade=True,
        )
        assert get_risk_weight(rw_input) == pytest.approx(0.65)

    def test_corporate_standard_via_lookup(self):
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.CORPORATE,
            is_investment_grade=False,
        )
        assert get_risk_weight(rw_input) == pytest.approx(1.00)

    def test_retail_transactor_via_lookup(self):
        """Retail transactor uses ExposureClass.RETAIL_TRANSACTOR."""
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.RETAIL_TRANSACTOR,
        )
        assert get_risk_weight(rw_input) == pytest.approx(0.45)

    def test_residential_mortgage_ltv_55(self):
        """LTV 55% → bucket '50-60' → 45% RW."""
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.RESIDENTIAL_MORTGAGE,
            ltv_ratio=0.55,
        )
        assert get_risk_weight(rw_input) == pytest.approx(0.45)

    def test_defaulted_via_lookup(self):
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.DEFAULTED,
        )
        assert get_risk_weight(rw_input) == pytest.approx(1.50)


# =========================================================================
#  Calculator Tests
# =========================================================================

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

    def test_ig_corporate_65_pct_rwa(self, calc):
        """IG corporate: RWA = EAD × 65%."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE,
            counterparty="A", ead=100e6, is_investment_grade=True,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(65e6, rel=0.01)

    def test_retail_standard(self, calc):
        """Retail exposure gets 75% RW."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.RETAIL,
            counterparty="RETAIL_A", ead=1_000_000.0,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(1_000_000.0 * 0.75, rel=0.05)

    def test_retail_transactor_45_pct(self, calc):
        """Retail transactor uses ExposureClass.RETAIL_TRANSACTOR → 45% RW."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.RETAIL_TRANSACTOR,
            counterparty="T1", ead=10e6, is_transactor=True,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(4.5e6, rel=0.05)

    def test_sovereign_zero_rw(self, calc):
        """US sovereign: RWA = 0."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.SOVEREIGN,
            counterparty="US_TREASURY", ead=500e6,
            country_risk_class=0, is_us_sovereign=True,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(0.0, abs=1.0)

    def test_defaulted_150_pct(self, calc):
        """Defaulted exposure: RWA = EAD × 150%."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.DEFAULTED,
            counterparty="DFLT", ead=10e6,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(15e6, rel=0.01)

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

    def test_rwa_density(self, calc):
        """RWA density = total_rwa / total_ead."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE,
            counterparty="A", ead=100e6, is_investment_grade=True,
        )
        result = calc.calculate([exp])
        density = result.total_rwa / result.total_ead
        assert density == pytest.approx(0.65, rel=0.01)

    def test_capital_requirement_8_pct(self, calc):
        """Capital requirement = RWA × 8%."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE,
            counterparty="A", ead=100e6,
        )
        result = calc.calculate([exp])
        cap_req = result.total_rwa * 0.08
        assert cap_req == pytest.approx(8e6, rel=0.01)

    def test_sme_corporate_85_pct(self, calc):
        """SME corporate: RWA = EAD × 85%."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE_SME,
            counterparty="SME", ead=20e6, is_sme=True,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(17e6, rel=0.05)

    def test_residential_mortgage_low_ltv(self, calc):
        """Residential mortgage with LTV 45% → 0-50 bucket → 40% RW."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.RESIDENTIAL_MORTGAGE,
            counterparty="M1", ead=1e6, ltv_ratio=0.45,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(0.4e6, rel=0.05)


# =========================================================================
#  Exposure Classification
# =========================================================================

class TestExposureClassification:
    def test_all_exposure_classes_exist(self):
        from src.credit_risk.sa.exposure_classes import ExposureClass
        required = [
            "SOVEREIGN", "BANK", "CORPORATE", "CORPORATE_SME",
            "RETAIL", "RETAIL_TRANSACTOR", "RESIDENTIAL_MORTGAGE",
            "COMMERCIAL_REAL_ESTATE", "DEFAULTED", "EQUITY",
        ]
        class_names = [e.name for e in ExposureClass]
        for name in required:
            assert name in class_names, f"Missing ExposureClass: {name}"

    def test_exposure_class_enum_values(self):
        from src.credit_risk.sa.exposure_classes import ExposureClass
        assert ExposureClass.CORPORATE.value == "CORPORATE"
        assert ExposureClass.RETAIL.value == "RETAIL"

    def test_retail_transactor_is_separate_class(self):
        """Retail transactor is its own ExposureClass, not a flag."""
        from src.credit_risk.sa.exposure_classes import ExposureClass
        assert hasattr(ExposureClass, "RETAIL_TRANSACTOR")
        assert ExposureClass.RETAIL_TRANSACTOR.value == "RETAIL_TRANSACTOR"
