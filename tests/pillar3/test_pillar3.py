"""Tests for Pillar 3 — Disclosure Templates and Disclosure Engine.

Validates:
- OV1 (Overview of RWA) template generation
- KM1 (Key Metrics) template generation
- CC1 (Capital Composition) template generation
- CC2 (Reconciliation) template generation
- CR1 (Credit Quality) template generation
- CR4 (SA Exposure and CRM) template generation
- CR5 (SA Exposure by Risk Weight) template generation
- MR1 (Market Risk SA) template generation
- MR2 (RWA Flow) template generation
- OR1 (Operational Risk) template generation
- LR1/LR2 (Leverage Ratio) template generation
- Disclosure engine package generation
- Template registry and frequency filters

All amounts in USD millions ($M).

References:
- BCBS d400/d455: Pillar 3 disclosure requirements
- 12 CFR 217 Subpart E: Disclosures
"""

from datetime import date

import pytest

from src.pillar3.pillar3_params import (
    DisclosureFrequency,
    TEMPLATE_REGISTRY,
    get_templates_by_category,
    get_templates_by_frequency,
)
from src.pillar3.templates.overview import (
    Pillar3KM1,
    Pillar3OV1,
    build_km1,
    build_ov1,
)
from src.pillar3.templates.capital_composition import (
    Pillar3CC1,
    Pillar3CC2,
    build_cc1,
    build_cc2,
)
from src.pillar3.templates.credit_risk_disclosure import (
    Pillar3CR1,
    Pillar3CR2,
    Pillar3CR4,
    Pillar3CR5,
    build_cr1,
    build_cr2,
    build_cr4,
    build_cr5,
)
from src.pillar3.templates.market_risk_disclosure import (
    Pillar3MR1,
    Pillar3MR2,
    build_mr1,
    build_mr2,
)
from src.pillar3.templates.operational_risk_disclosure import (
    Pillar3OR1,
    build_or1,
)
from src.pillar3.templates.leverage_ratio import (
    Pillar3LR1,
    Pillar3LR2,
    build_lr1,
    build_lr2,
)
from src.pillar3.disclosure_engine import (
    DisclosureCapitalData,
    DisclosureLeverageData,
    DisclosureMarketRiskData,
    DisclosurePackage,
    DisclosureRWAData,
    generate_disclosure_package,
    get_disclosure_schedule,
)


# =========================================================================
#  Test Template Registry
# =========================================================================

class TestTemplateRegistry:
    """Tests for Pillar 3 template registry and metadata."""

    def test_registry_has_all_templates(self) -> None:
        """Registry contains all 16 expected templates."""
        expected = {
            "OV1", "KM1", "CC1", "CC2",
            "CR1", "CR2", "CR3", "CR4", "CR5",
            "MR1", "MR2", "MR3", "MR4",
            "OR1", "LR1", "LR2",
        }
        assert set(TEMPLATE_REGISTRY.keys()) == expected

    def test_quarterly_templates(self) -> None:
        """Quarterly templates include OV1, KM1, MR1-MR4, LR1, LR2."""
        quarterly = get_templates_by_frequency(DisclosureFrequency.QUARTERLY)
        quarterly_ids = {t.template_id for t in quarterly}
        assert "OV1" in quarterly_ids
        assert "KM1" in quarterly_ids
        assert "MR1" in quarterly_ids
        assert "LR1" in quarterly_ids

    def test_semi_annual_templates(self) -> None:
        """Semi-annual templates include CC1, CC2, CR1-CR5."""
        semi = get_templates_by_frequency(DisclosureFrequency.SEMI_ANNUAL)
        semi_ids = {t.template_id for t in semi}
        assert "CC1" in semi_ids
        assert "CC2" in semi_ids
        assert "CR1" in semi_ids

    def test_annual_templates(self) -> None:
        """Annual templates include OR1."""
        annual = get_templates_by_frequency(DisclosureFrequency.ANNUAL)
        annual_ids = {t.template_id for t in annual}
        assert "OR1" in annual_ids

    def test_templates_by_category(self) -> None:
        """Filter templates by category."""
        credit = get_templates_by_category("credit_risk")
        credit_ids = {t.template_id for t in credit}
        assert "CR1" in credit_ids
        assert "CR5" in credit_ids
        assert "MR1" not in credit_ids


# =========================================================================
#  Test OV1: Overview of RWA
# =========================================================================

class TestOV1:
    """Tests for OV1 template generation."""

    def test_ov1_basic(self) -> None:
        """OV1 with all risk types produces correct total."""
        result = build_ov1(
            credit_risk_rwa=800_000.0,
            market_risk_rwa=120_000.0,
            operational_risk_rwa=150_000.0,
            cva_risk_rwa=30_000.0,
        )
        assert result.total_rwa == pytest.approx(1_100_000.0)
        assert result.total_minimum_capital == pytest.approx(
            1_100_000.0 * 0.08
        )

    def test_ov1_rows(self) -> None:
        """OV1 has correct number of rows."""
        result = build_ov1(credit_risk_rwa=800_000.0)
        # 8 risk type rows + 1 total row
        assert len(result.rows) == 9

    def test_ov1_minimum_capital(self) -> None:
        """Minimum capital = 8% of RWA for each row."""
        result = build_ov1(credit_risk_rwa=100_000.0)
        cr_row = result.rows[0]
        assert cr_row.minimum_capital == pytest.approx(8_000.0)


# =========================================================================
#  Test KM1: Key Metrics
# =========================================================================

class TestKM1:
    """Tests for KM1 template generation."""

    def test_km1_ratios(self) -> None:
        """KM1 computes correct ratios."""
        result = build_km1(
            cet1_capital=180_000.0,
            tier1_capital=200_000.0,
            total_capital=230_000.0,
            total_rwa=1_500_000.0,
            total_leverage_exposure=4_000_000.0,
        )
        assert result.cet1_ratio == pytest.approx(0.12)
        assert result.tier1_ratio == pytest.approx(200_000.0 / 1_500_000.0)
        assert result.leverage_ratio == pytest.approx(200_000.0 / 4_000_000.0)

    def test_km1_rows(self) -> None:
        """KM1 has 13 rows."""
        result = build_km1(
            cet1_capital=180_000.0,
            tier1_capital=200_000.0,
            total_capital=230_000.0,
            total_rwa=1_500_000.0,
        )
        assert len(result.rows) == 13

    def test_km1_buffer_metrics(self) -> None:
        """KM1 includes buffer requirements."""
        result = build_km1(
            cet1_capital=180_000.0,
            tier1_capital=200_000.0,
            total_capital=230_000.0,
            total_rwa=1_500_000.0,
            ccb=0.03,
            gsib_surcharge=0.02,
        )
        assert result.ccb == 0.03
        assert result.gsib_surcharge == 0.02
        # CET1 available = 12% - 4.5% = 7.5%
        assert result.cet1_available_for_buffers == pytest.approx(0.075)


# =========================================================================
#  Test CC1: Capital Composition
# =========================================================================

class TestCC1:
    """Tests for CC1 template generation."""

    def test_cc1_capital_computation(self) -> None:
        """CC1 computes correct CET1, Tier 1, Total Capital."""
        result = build_cc1(
            common_stock=5_000.0,
            surplus=50_000.0,
            retained_earnings=140_000.0,
            aoci=-2_000.0,
            goodwill_deduction=15_000.0,
            at1_instruments=20_000.0,
            tier2_instruments=15_000.0,
            tier2_allowance=5_000.0,
            total_rwa=1_500_000.0,
        )
        expected_cet1 = 5_000 + 50_000 + 140_000 - 2_000 - 15_000
        assert result.cet1_capital == pytest.approx(expected_cet1)
        assert result.tier1_capital == pytest.approx(expected_cet1 + 20_000)
        assert result.total_capital == pytest.approx(
            expected_cet1 + 20_000 + 15_000 + 5_000
        )

    def test_cc1_rows(self) -> None:
        """CC1 has expected number of rows."""
        result = build_cc1(
            common_stock=5_000.0,
            surplus=50_000.0,
            retained_earnings=140_000.0,
            aoci=0.0,
            total_rwa=1_000_000.0,
        )
        assert len(result.rows) > 20  # At least 20 standardized rows


class TestCC2:
    """Tests for CC2 template generation."""

    def test_cc2_reconciliation(self) -> None:
        """CC2 reconciles balance sheet to regulatory capital."""
        result = build_cc2(
            total_assets=3_500_000.0,
            total_liabilities=3_250_000.0,
            shareholders_equity=250_000.0,
            goodwill_intangibles=15_000.0,
            dta_disallowed=3_000.0,
            total_regulatory_capital=232_000.0,
        )
        assert result.total_assets_bs == pytest.approx(3_500_000.0)
        assert result.shareholders_equity_bs == pytest.approx(250_000.0)
        assert len(result.rows) == 10


# =========================================================================
#  Test Credit Risk Disclosures
# =========================================================================

class TestCR1:
    """Tests for CR1 template generation."""

    def test_cr1_basic(self) -> None:
        """CR1 produces correct totals."""
        asset_classes = [
            {"name": "Corporate", "defaulted_gross": 500.0,
             "non_defaulted_gross": 800_000.0,
             "allowances_specific": 400.0, "allowances_general": 200.0},
            {"name": "Retail", "defaulted_gross": 1_000.0,
             "non_defaulted_gross": 400_000.0,
             "allowances_specific": 800.0, "allowances_general": 500.0},
        ]
        result = build_cr1(asset_classes)
        assert result.total_defaulted == pytest.approx(1_500.0)
        assert result.total_non_defaulted == pytest.approx(1_200_000.0)
        assert len(result.rows) == 3  # 2 classes + total


class TestCR2:
    """Tests for CR2 template generation."""

    def test_cr2_closing_balance(self) -> None:
        """CR2 computes correct closing balance."""
        result = build_cr2(
            opening_balance=5_000.0,
            new_defaults=1_000.0,
            returned_to_performing=200.0,
            write_offs=800.0,
        )
        assert result.closing_balance == pytest.approx(5_000.0)
        assert len(result.rows) == 6


class TestCR4:
    """Tests for CR4 template generation."""

    def test_cr4_rwa_density(self) -> None:
        """CR4 computes correct RWA density."""
        exposures = [
            {"name": "Sovereign", "exposure_pre": 500_000.0,
             "exposure_post": 480_000.0, "rwa": 0.0},
            {"name": "Corporate", "exposure_pre": 300_000.0,
             "exposure_post": 280_000.0, "rwa": 280_000.0},
        ]
        result = build_cr4(exposures)
        corp_row = result.rows[1]
        assert corp_row.rwa_density == pytest.approx(1.0)
        assert result.total_rwa == pytest.approx(280_000.0)


class TestCR5:
    """Tests for CR5 template generation."""

    def test_cr5_risk_weight_breakdown(self) -> None:
        """CR5 captures risk weight distribution."""
        exposures = [
            {
                "name": "Sovereign",
                "risk_weight_exposures": {"0%": 400_000.0, "20%": 50_000.0},
                "total_credit_exposure": 450_000.0,
            },
        ]
        result = build_cr5(exposures)
        assert result.total_exposure == pytest.approx(450_000.0)
        assert result.rows[0].risk_weight_exposures["0%"] == pytest.approx(
            400_000.0
        )


# =========================================================================
#  Test Market Risk Disclosures
# =========================================================================

class TestMR1:
    """Tests for MR1 template generation."""

    def test_mr1_total_charge(self) -> None:
        """MR1 computes correct total capital charge."""
        result = build_mr1(
            girr_charge=50.0,
            csr_nonsec_charge=80.0,
            equity_charge=30.0,
            commodity_charge=20.0,
            fx_charge=15.0,
            drc_nonsec_charge=40.0,
            rrao_charge=5.0,
        )
        expected_sbm = 50 + 80 + 30 + 20 + 15
        expected_total = expected_sbm + 40 + 5
        assert result.total_sbm_charge == pytest.approx(expected_sbm)
        assert result.total_capital_charge == pytest.approx(expected_total)
        assert result.total_rwa == pytest.approx(expected_total * 12.5)

    def test_mr1_rows(self) -> None:
        """MR1 has 14 rows."""
        result = build_mr1(girr_charge=50.0)
        assert len(result.rows) == 14


class TestMR2:
    """Tests for MR2 template generation."""

    def test_mr2_closing_rwa(self) -> None:
        """MR2 computes correct closing RWA."""
        result = build_mr2(
            opening_rwa=1_500.0,
            movement_levels=200.0,
            movement_fx=-50.0,
        )
        assert result.closing_rwa == pytest.approx(1_650.0)
        assert len(result.rows) == 8


# =========================================================================
#  Test Operational Risk Disclosure
# =========================================================================

class TestOR1:
    """Tests for OR1 template generation."""

    def test_or1_ilm_one(self) -> None:
        """OR1 uses ILM = 1.0 per US 2026 re-proposal."""
        result = build_or1(
            interest_lease_dividend_component=5_000.0,
            services_component=3_000.0,
            financial_component=2_000.0,
            bic=1_200.0,
            ilm=1.0,
        )
        assert result.ilm == 1.0
        assert result.capital_charge == pytest.approx(1_200.0)
        assert result.rwa == pytest.approx(1_200.0 * 12.5)
        assert result.business_indicator == pytest.approx(10_000.0)

    def test_or1_rows(self) -> None:
        """OR1 has 8 rows."""
        result = build_or1(bic=1_000.0)
        assert len(result.rows) == 8


# =========================================================================
#  Test Leverage Ratio Disclosures
# =========================================================================

class TestLR1:
    """Tests for LR1 template generation."""

    def test_lr1_reconciliation(self) -> None:
        """LR1 reconciles assets to leverage exposure."""
        result = build_lr1(
            total_consolidated_assets=3_500_000.0,
            adjustment_for_derivatives=50_000.0,
            adjustment_for_sft=80_000.0,
            off_balance_sheet_items=200_000.0,
            regulatory_deductions=30_000.0,
        )
        expected = 3_500_000.0 + 50_000.0 + 80_000.0 + 200_000.0 - 30_000.0
        assert result.total_leverage_exposure == pytest.approx(expected)
        assert len(result.rows) == 8


class TestLR2:
    """Tests for LR2 template generation."""

    def test_lr2_leverage_ratio(self) -> None:
        """LR2 computes correct leverage ratio."""
        result = build_lr2(
            on_balance_sheet_excl_derivatives=3_000_000.0,
            on_balance_sheet_deductions=50_000.0,
            derivative_replacement_cost=30_000.0,
            derivative_pfe=20_000.0,
            sft_gross=400_000.0,
            sft_ccr_addon=10_000.0,
            off_bs_notional=800_000.0,
            off_bs_ccf_adjustment=400_000.0,
            tier1_capital=200_000.0,
        )
        # TLE = (3M - 50K) + (30K + 20K) + (400K + 10K) + (800K - 400K)
        # = 2,950K + 50K + 410K + 400K = 3,810K
        expected_tle = 2_950_000.0 + 50_000.0 + 410_000.0 + 400_000.0
        assert result.total_leverage_exposure == pytest.approx(expected_tle)
        assert result.leverage_ratio == pytest.approx(
            200_000.0 / expected_tle
        )
        assert len(result.rows) == 22

    def test_lr2_slr_surplus(self) -> None:
        """LR2 computes SLR surplus correctly."""
        result = build_lr2(
            on_balance_sheet_excl_derivatives=3_000_000.0,
            tier1_capital=200_000.0,
        )
        expected_lr = 200_000.0 / 3_000_000.0
        assert result.slr_surplus == pytest.approx(expected_lr - 0.03)
        assert result.eslr_surplus == pytest.approx(expected_lr - 0.05)


# =========================================================================
#  Test Disclosure Engine
# =========================================================================

class TestDisclosureEngine:
    """Tests for the disclosure package generation engine."""

    @pytest.fixture
    def sample_capital_data(self) -> DisclosureCapitalData:
        """Sample capital data for a G-SIB."""
        return DisclosureCapitalData(
            common_stock=5_000.0,
            surplus=50_000.0,
            retained_earnings=140_000.0,
            aoci=-2_000.0,
            goodwill_deduction=15_000.0,
            at1_instruments=20_000.0,
            tier2_instruments=15_000.0,
            tier2_allowance=5_000.0,
        )

    @pytest.fixture
    def sample_rwa_data(self) -> DisclosureRWAData:
        """Sample RWA data."""
        return DisclosureRWAData(
            credit_risk_rwa=800_000.0,
            market_risk_rwa=120_000.0,
            operational_risk_rwa=150_000.0,
            cva_risk_rwa=30_000.0,
        )

    def test_quarterly_package(
        self,
        sample_capital_data: DisclosureCapitalData,
        sample_rwa_data: DisclosureRWAData,
    ) -> None:
        """Quarterly package generates OV1 and KM1."""
        package = generate_disclosure_package(
            reporting_date=date(2026, 3, 31),
            frequency=DisclosureFrequency.QUARTERLY,
            capital_data=sample_capital_data,
            rwa_data=sample_rwa_data,
        )
        assert "OV1" in package.templates_included
        assert "KM1" in package.templates_included
        assert package.ov1 is not None
        assert package.km1 is not None
        assert package.ov1.total_rwa == pytest.approx(1_100_000.0)

    def test_semi_annual_package(
        self,
        sample_capital_data: DisclosureCapitalData,
        sample_rwa_data: DisclosureRWAData,
    ) -> None:
        """Semi-annual package includes CC1."""
        package = generate_disclosure_package(
            reporting_date=date(2026, 6, 30),
            frequency=DisclosureFrequency.SEMI_ANNUAL,
            capital_data=sample_capital_data,
            rwa_data=sample_rwa_data,
        )
        assert "CC1" in package.templates_included
        assert package.cc1 is not None

    def test_package_with_market_risk(
        self,
        sample_capital_data: DisclosureCapitalData,
        sample_rwa_data: DisclosureRWAData,
    ) -> None:
        """Package with market risk data generates MR1."""
        mrd = DisclosureMarketRiskData(
            girr_charge=50.0,
            equity_charge=30.0,
        )
        package = generate_disclosure_package(
            reporting_date=date(2026, 3, 31),
            frequency=DisclosureFrequency.QUARTERLY,
            capital_data=sample_capital_data,
            rwa_data=sample_rwa_data,
            market_risk_data=mrd,
        )
        assert "MR1" in package.templates_included
        assert package.mr1 is not None
        assert package.mr1.total_capital_charge == pytest.approx(80.0)

    def test_package_with_leverage_data(
        self,
        sample_capital_data: DisclosureCapitalData,
        sample_rwa_data: DisclosureRWAData,
    ) -> None:
        """Package with leverage data generates LR1 and LR2."""
        ld = DisclosureLeverageData(
            total_consolidated_assets=3_500_000.0,
            on_balance_sheet_excl_derivatives=3_000_000.0,
            tier1_capital=200_000.0,
        )
        package = generate_disclosure_package(
            reporting_date=date(2026, 3, 31),
            frequency=DisclosureFrequency.QUARTERLY,
            capital_data=sample_capital_data,
            rwa_data=sample_rwa_data,
            leverage_data=ld,
        )
        assert "LR1" in package.templates_included
        assert "LR2" in package.templates_included
        assert package.lr2 is not None
        assert package.lr2.leverage_ratio > 0

    def test_disclosure_schedule(self) -> None:
        """Disclosure schedule returns correct templates per frequency."""
        quarterly = get_disclosure_schedule(DisclosureFrequency.QUARTERLY)
        quarterly_ids = {t.template_id for t in quarterly}
        assert "OV1" in quarterly_ids
        assert "KM1" in quarterly_ids

        annual = get_disclosure_schedule(DisclosureFrequency.ANNUAL)
        annual_ids = {t.template_id for t in annual}
        # Annual includes all quarterly and semi-annual too
        assert "OV1" in annual_ids
        assert "CC1" in annual_ids
        assert "OR1" in annual_ids
