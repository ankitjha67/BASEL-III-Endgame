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

    def test_crc_6_hundred_pct(self):
        """Table 1 to § __.111: CRC 4-6 -> 100% (only CRC 7 is 150%)."""
        from src.credit_risk.sa.risk_weights import SOVEREIGN_RW
        assert SOVEREIGN_RW[6] == 1.00

    def test_sovereign_no_crc_oecd_vs_non_oecd(self):
        """§ __.111(a)(4)-(5): OECD member without CRC 0%, non-OECD 100%."""
        from src.credit_risk.sa.risk_weights import get_sovereign_risk_weight
        assert get_sovereign_risk_weight(None, is_oecd_member=True) == 0.0
        assert get_sovereign_risk_weight(None, is_oecd_member=False) == 1.0

    def test_sovereign_default_150(self):
        """§ __.111(a)(6): sovereign default within five years -> 150%."""
        from src.credit_risk.sa.risk_weights import get_sovereign_risk_weight
        assert get_sovereign_risk_weight(0, is_sovereign_default=True) == 1.50

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

    def test_sme_no_preferential_weight(self):
        """ERBA NPR § __.111(h) has no SME preferential weight: 100%."""
        from src.credit_risk.sa.risk_weights import CORPORATE_SME_RW
        assert CORPORATE_SME_RW == 1.00

    def test_project_finance_130_and_100(self):
        """§ __.111(h)(3): pre-operational 130%, operational phase 100%."""
        from src.credit_risk.sa.risk_weights import get_corporate_risk_weight
        assert get_corporate_risk_weight(is_project_finance=True) == 1.30
        assert get_corporate_risk_weight(
            is_project_finance=True, is_project_finance_operational=True
        ) == 1.00

    def test_subordinated_corporate_150(self):
        """§ __.111(h)(5): subordinated corporate exposure 150% even if IG."""
        from src.credit_risk.sa.risk_weights import get_corporate_risk_weight
        assert get_corporate_risk_weight(is_investment_grade=True, is_subordinated=True) == 1.50


# =========================================================================
#  Bank Risk Weight Constants (Table 2 to § __.111)
# =========================================================================

class TestBankRiskWeights:
    """Table 2 to § __.111 (ERBA NPR p. 688): Grade A/B/C bank exposures."""

    def test_grade_a_otherwise_40(self):
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        assert get_bank_risk_weight(BankGrade.GRADE_A) == 0.40

    def test_grade_a_enhanced_30(self):
        """§ __.111(d)(2): CET1 >= 14% and leverage >= 5% -> 30%."""
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        assert get_bank_risk_weight(BankGrade.GRADE_A, meets_enhanced_criteria=True) == 0.30

    def test_grade_b_75_and_grade_c_150(self):
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        assert get_bank_risk_weight(BankGrade.GRADE_B) == 0.75
        assert get_bank_risk_weight(BankGrade.GRADE_C) == 1.50

    def test_short_term_trade_related_row(self):
        """Foreign bank trade-related contingent item <= 3m: 20/50/150."""
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        kw = dict(is_short_term_trade_related=True, maturity_years=0.25, is_us_entity=False)
        assert get_bank_risk_weight(BankGrade.GRADE_A, **kw) == 0.20
        assert get_bank_risk_weight(BankGrade.GRADE_B, **kw) == 0.50
        assert get_bank_risk_weight(BankGrade.GRADE_C, **kw) == 1.50

    def test_no_general_short_term_preference(self):
        """The ERBA NPR has no general <= 3 month preferential bank RW."""
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        assert get_bank_risk_weight(BankGrade.GRADE_B, maturity_years=0.1) == 0.75

    def test_foreign_bank_sovereign_floor(self):
        """§ __.111(d)(3): foreign bank RW floored at home-sovereign RW."""
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        assert get_bank_risk_weight(
            BankGrade.GRADE_A, is_us_entity=False, home_sovereign_risk_weight=1.0
        ) == 1.0
        assert get_bank_risk_weight(
            BankGrade.GRADE_A, is_us_entity=False, home_sovereign_risk_weight=1.0,
            is_local_currency=True,
        ) == 0.40

    def test_subordinated_bank_150(self):
        from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight
        assert get_bank_risk_weight(BankGrade.GRADE_A, is_subordinated=True) == 1.50


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

    # Table 5 to § __.111 (ERBA NPR p. 692): 20/25/30/40/50/70
    def test_resi_ltv_0_50(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["0-50"] == 0.20

    def test_resi_ltv_50_60(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["50-60"] == 0.25

    def test_resi_ltv_60_80(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["60-80"] == 0.30

    def test_resi_ltv_80_90(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["80-90"] == 0.40

    def test_resi_ltv_90_100(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["90-100"] == 0.50

    def test_resi_ltv_above_100(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert RESI_MORTGAGE_RW["100+"] == 0.70

    def test_resi_has_six_bands(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_RW
        assert list(RESI_MORTGAGE_RW) == ["0-50", "50-60", "60-80", "80-90", "90-100", "100+"]

    # Table 6 to § __.111 (p. 693): dependent on cash flows 30/35/45/60/75/105
    def test_resi_cf_dependent_table_6(self):
        from src.credit_risk.sa.risk_weights import RESI_MORTGAGE_CF_DEPENDENT_RW
        assert list(RESI_MORTGAGE_CF_DEPENDENT_RW.values()) == [0.30, 0.35, 0.45, 0.60, 0.75, 1.05]

    def test_resi_cf_dependent_lookup(self):
        from src.credit_risk.sa.risk_weights import get_residential_mortgage_risk_weight
        assert get_residential_mortgage_risk_weight(0.75, is_dependent_on_cash_flows=True) == 0.45
        assert get_residential_mortgage_risk_weight(0.75) == 0.30

    def test_resi_non_regulatory_and_past_due(self):
        """§ __.111(f)(7)-(8): 100% if not dependent on cash flows, else 150%."""
        from src.credit_risk.sa.risk_weights import get_residential_mortgage_risk_weight
        assert get_residential_mortgage_risk_weight(0.5, is_regulatory_real_estate=False) == 1.00
        assert get_residential_mortgage_risk_weight(0.5, is_past_due=True) == 1.00
        assert get_residential_mortgage_risk_weight(
            0.5, is_past_due=True, is_dependent_on_cash_flows=True
        ) == 1.50

    def test_cre_ltv_0_60(self):
        from src.credit_risk.sa.risk_weights import CRE_INCOME_PRODUCING_RW
        assert CRE_INCOME_PRODUCING_RW["0-60"] == 0.70

    def test_cre_ltv_60_80(self):
        from src.credit_risk.sa.risk_weights import CRE_INCOME_PRODUCING_RW
        assert CRE_INCOME_PRODUCING_RW["60-80"] == 0.90

    def test_cre_ltv_above_80(self):
        from src.credit_risk.sa.risk_weights import CRE_INCOME_PRODUCING_RW
        assert CRE_INCOME_PRODUCING_RW["80+"] == 1.10

    def test_cre_not_dependent_table_7(self):
        """Table 7 to § __.111: LTV <= 60% -> min(60%, borrower RW); else borrower RW."""
        from src.credit_risk.sa.exposure_classes import CRESubType
        from src.credit_risk.sa.risk_weights import get_cre_risk_weight
        kw = dict(cre_sub_type=CRESubType.REGULATORY_CRE, is_dependent_on_cash_flows=False)
        assert get_cre_risk_weight(ltv_ratio=0.55, borrower_risk_weight=1.00, **kw) == 0.60
        assert get_cre_risk_weight(ltv_ratio=0.55, borrower_risk_weight=0.65, **kw) == 0.60
        assert get_cre_risk_weight(ltv_ratio=0.55, borrower_risk_weight=0.20, **kw) == 0.20
        assert get_cre_risk_weight(ltv_ratio=0.70, borrower_risk_weight=0.65, **kw) == 0.65
        assert get_cre_risk_weight(ltv_ratio=0.70, **kw) == 1.00  # borrower RW unknown

    def test_cre_special_categories(self):
        """§ __.111(f)(1)-(4),(7): multifamily 50, pre-sold 50/100, ADC 100, HVCRE 150, other 150."""
        from src.credit_risk.sa.exposure_classes import CRESubType
        from src.credit_risk.sa.risk_weights import get_cre_risk_weight
        assert get_cre_risk_weight(CRESubType.STATUTORY_MULTIFAMILY) == 0.50
        assert get_cre_risk_weight(CRESubType.PRESOLD_CONSTRUCTION) == 0.50
        assert get_cre_risk_weight(
            CRESubType.PRESOLD_CONSTRUCTION, is_purchase_contract_cancelled=True
        ) == 1.00
        assert get_cre_risk_weight(CRESubType.ADC) == 1.00
        assert get_cre_risk_weight(CRESubType.LAND) == 1.00
        assert get_cre_risk_weight(CRESubType.HVCRE) == 1.50
        assert get_cre_risk_weight(CRESubType.OTHER_REAL_ESTATE) == 1.50


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

    def test_adc_100_pct(self):
        """§ __.111(f)(4): ADC that is not HVCRE -> 100%."""
        from src.credit_risk.sa.risk_weights import CRE_ADC_RW
        assert CRE_ADC_RW == 1.00

    def test_hvcre_150_pct(self):
        from src.credit_risk.sa.risk_weights import HVCRE_RW
        assert HVCRE_RW == 1.50

    def test_cash_zero_pct(self):
        from src.credit_risk.sa.risk_weights import CASH_RW
        assert CASH_RW == 0.0

    def test_equity_public_300_pct(self):
        """§ __.141(b)(5): publicly traded equity 300%."""
        from src.credit_risk.sa.risk_weights import EQUITY_PUBLIC_TRADED_RW
        assert EQUITY_PUBLIC_TRADED_RW == 3.00

    def test_equity_speculative_400_pct(self):
        from src.credit_risk.sa.risk_weights import EQUITY_SPECULATIVE_RW
        assert EQUITY_SPECULATIVE_RW == 4.00

    def test_equity_srwa_full_ladder(self):
        """§ __.141(b)(1)-(7): 0 / 20 / 100 / 250 / 300 / 400 / 600 percent."""
        from src.credit_risk.sa.exposure_classes import EquitySubType
        from src.credit_risk.sa.risk_weights import get_equity_risk_weight
        assert get_equity_risk_weight(EquitySubType.SOVEREIGN_MDB) == 0.0
        assert get_equity_risk_weight(EquitySubType.FEDERAL_RESERVE_STOCK) == 0.0
        assert get_equity_risk_weight(EquitySubType.PSE_FHLB_FARMER_MAC) == 0.20
        assert get_equity_risk_weight(EquitySubType.COMMUNITY_DEVELOPMENT) == 1.00
        assert get_equity_risk_weight(EquitySubType.NON_SIGNIFICANT) == 1.00
        assert get_equity_risk_weight(EquitySubType.SIGNIFICANT_FI_NOT_DEDUCTED) == 2.50
        assert get_equity_risk_weight(EquitySubType.PUBLIC_TRADED) == 3.00
        assert get_equity_risk_weight(EquitySubType.VENTURE_CAPITAL) == 4.00
        assert get_equity_risk_weight(EquitySubType.INVESTMENT_FIRM_LEVERAGED) == 6.00

    def test_gse_risk_weights(self):
        """§ __.111(c): GSE 20%; subordinated 150%; FHLB/Farmer Mac subordinated 20%."""
        from src.credit_risk.sa.risk_weights import get_gse_risk_weight
        assert get_gse_risk_weight() == 0.20
        assert get_gse_risk_weight(is_subordinated=True) == 1.50
        assert get_gse_risk_weight(is_subordinated=True, is_fhlb_or_farmer_mac=True) == 0.20

    def test_foreign_pse_tables_3_and_4(self):
        """Tables 3-4 to § __.111: foreign PSE by home-country CRC."""
        from src.credit_risk.sa.exposure_classes import PSEObligationType
        from src.credit_risk.sa.risk_weights import get_pse_risk_weight
        go = PSEObligationType.GENERAL_OBLIGATION
        rev = PSEObligationType.REVENUE_OBLIGATION
        assert get_pse_risk_weight(go, is_us_entity=False, country_risk_class=1) == 0.20
        assert get_pse_risk_weight(go, is_us_entity=False, country_risk_class=2) == 0.50
        assert get_pse_risk_weight(go, is_us_entity=False, country_risk_class=3) == 1.00
        assert get_pse_risk_weight(rev, is_us_entity=False, country_risk_class=1) == 0.50
        assert get_pse_risk_weight(rev, is_us_entity=False, country_risk_class=3) == 1.00
        assert get_pse_risk_weight(rev, is_us_entity=False, country_risk_class=5) == 1.50

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
        """LTV 55% → bucket '50-60' → 25% RW (Table 5 to § __.111)."""
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        rw_input = RiskWeightInput(
            exposure_class=ExposureClass.RESIDENTIAL_MORTGAGE,
            ltv_ratio=0.55,
        )
        assert get_risk_weight(rw_input) == pytest.approx(0.25)

    def test_bank_via_lookup_defaults_grade_a_40(self):
        from src.credit_risk.sa.risk_weights import RiskWeightInput, get_risk_weight
        from src.credit_risk.sa.exposure_classes import ExposureClass
        assert get_risk_weight(RiskWeightInput(exposure_class=ExposureClass.BANK)) == 0.40

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

    def test_sme_corporate_100_pct(self, calc):
        """SME corporate: RWA = EAD × 100% (no SME preference in ERBA NPR)."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.CORPORATE_SME,
            counterparty="SME", ead=20e6, is_sme=True,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(20e6, rel=0.01)

    def test_residential_mortgage_low_ltv(self, calc):
        """Residential mortgage with LTV 45% → 0-50 bucket → 20% RW."""
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.RESIDENTIAL_MORTGAGE,
            counterparty="M1", ead=1e6, ltv_ratio=0.45,
        )
        result = calc.calculate([exp])
        assert result.total_rwa == pytest.approx(0.2e6, rel=0.01)

    def test_bank_grade_b_via_calculator(self, calc):
        from src.credit_risk.sa.calculator import CreditExposure
        from src.credit_risk.sa.exposure_classes import ExposureClass
        from src.credit_risk.sa.risk_weights import BankGrade
        exp = CreditExposure(
            exposure_id="1", exposure_class=ExposureClass.BANK,
            counterparty="B1", ead=10e6, bank_grade=BankGrade.GRADE_B,
        )
        assert calc.calculate([exp]).total_rwa == pytest.approx(7.5e6)


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
