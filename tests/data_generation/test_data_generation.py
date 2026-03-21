"""Unit tests for data generation module — portfolio and financial statement generators.

Tests cover:
- Credit portfolio: ~$1.8T total EAD, ~565 exposures, correct risk weights
- Trading portfolio: ~$500B notional, 130 positions, all 5 risk classes
- Counterparty portfolio: 500 counterparties, alpha=1.4/1.0 split
- Financial statements: 3 years, $3.2T balance sheet, NII ~$60-70B
- Business Indicator data: ILDC + SC + FC calculation

References:
    - FR Y-9C: Consolidated financial statements
    - FR Y-14A: Capital assessment data
    - FFIEC 101 Schedule A: RWA by exposure type
    - BCBS d424 Section 5: Operational risk BI
"""

import pytest
import numpy as np

from src.data_generation.portfolio_generator import (
    PortfolioGenerator,
    CreditPortfolio,
    TradingBookPortfolio,
    CounterpartyPortfolio,
)
from src.data_generation.financial_statements import (
    FinancialStatementGenerator,
    BusinessIndicatorData,
)


# =========================================================================
#  Credit Portfolio Tests
# =========================================================================


class TestCreditPortfolio:
    """Tests for credit portfolio generation."""

    @pytest.fixture(scope="class")
    def credit_portfolio(self) -> CreditPortfolio:
        """Generate credit portfolio with seed=42 for reproducibility."""
        gen = PortfolioGenerator(seed=42)
        return gen.generate_credit_portfolio()

    def test_exposure_count(self, credit_portfolio: CreditPortfolio) -> None:
        """Credit portfolio should have ~565 exposures (sum of config n_exposures)."""
        # Config: 20+15+50+60+30+20+100+200+40+30 = 565
        assert credit_portfolio.count == 565

    def test_total_ead_around_1_8t(self, credit_portfolio: CreditPortfolio) -> None:
        """Total EAD should be approximately $1.8T ($1,800,000M).

        Each exposure's EAD = avg_ead * (0.5 + random), so on average 1.0*avg_ead.
        Total target: 500+300+200+200+60+40+250+80+100+70 = $1,800B.
        """
        assert credit_portfolio.total_ead == pytest.approx(1_800_000.0, rel=0.15)

    def test_has_all_exposure_types(self, credit_portfolio: CreditPortfolio) -> None:
        """Portfolio includes all major exposure classes."""
        types = {e.exposure_type for e in credit_portfolio.exposures}
        expected = {"SOVEREIGN", "AGENCY_MBS", "CORPORATE_IG", "CORPORATE_HY",
                    "RETAIL_MORTGAGE", "RETAIL_REVOLVING", "CRE", "OTHER"}
        assert expected.issubset(types)

    def test_sovereign_zero_rw(self, credit_portfolio: CreditPortfolio) -> None:
        """US Treasuries at 0% risk weight."""
        sovereigns = [e for e in credit_portfolio.exposures if e.exposure_type == "SOVEREIGN"]
        for s in sovereigns:
            if not s.is_defaulted:
                assert s.risk_weight == pytest.approx(0.0)

    def test_corporate_ig_65_rw(self, credit_portfolio: CreditPortfolio) -> None:
        """Corporate IG at 65% risk weight per CLAUDE.md."""
        ig = [e for e in credit_portfolio.exposures
              if e.exposure_type == "CORPORATE_IG" and not e.is_defaulted]
        for e in ig:
            assert e.risk_weight == pytest.approx(0.65)

    def test_summary_by_type(self, credit_portfolio: CreditPortfolio) -> None:
        """Summary dictionary has correct keys and positive values."""
        summary = credit_portfolio.summary_by_type()
        assert "SOVEREIGN" in summary
        assert summary["SOVEREIGN"]["ead"] > 0
        assert summary["SOVEREIGN"]["count"] > 0

    def test_rwa_equals_ead_times_rw(self, credit_portfolio: CreditPortfolio) -> None:
        """RWA = EAD * RW for each exposure."""
        for e in credit_portfolio.exposures[:20]:
            assert e.rwa == pytest.approx(e.ead * e.risk_weight, rel=1e-6)


# =========================================================================
#  Trading Portfolio Tests
# =========================================================================


class TestTradingPortfolio:
    """Tests for trading book portfolio generation."""

    @pytest.fixture(scope="class")
    def trading_portfolio(self) -> TradingBookPortfolio:
        """Generate trading portfolio with seed=42."""
        gen = PortfolioGenerator(seed=42)
        return gen.generate_trading_portfolio()

    def test_position_count(self, trading_portfolio: TradingBookPortfolio) -> None:
        """Trading book should have 130 positions (40+30+25+15+20)."""
        assert len(trading_portfolio.positions) == 130

    def test_total_notional_around_500b(self, trading_portfolio: TradingBookPortfolio) -> None:
        """Total notional approximately $500B."""
        assert trading_portfolio.total_notional == pytest.approx(500_000.0, rel=0.15)

    def test_all_5_risk_classes(self, trading_portfolio: TradingBookPortfolio) -> None:
        """All 5 FRTB risk classes represented."""
        classes = {p.risk_class for p in trading_portfolio.positions}
        expected = {"GIRR", "CSR_NONSEC", "EQUITY", "COMMODITY", "FX"}
        assert expected == classes

    def test_summary_by_risk_class(self, trading_portfolio: TradingBookPortfolio) -> None:
        """Summary has all 5 risk classes with positive notional."""
        summary = trading_portfolio.summary_by_risk_class()
        for rc in ["GIRR", "CSR_NONSEC", "EQUITY", "COMMODITY", "FX"]:
            assert summary[rc] > 0

    def test_sensitivities_populated(self, trading_portfolio: TradingBookPortfolio) -> None:
        """Positions have delta, vega, and curvature sensitivities."""
        pos = trading_portfolio.positions[0]
        # All sensitivities are computed from notional, so should be non-zero in general
        assert isinstance(pos.delta_sensitivity, float)
        assert isinstance(pos.vega_sensitivity, float)
        assert isinstance(pos.curvature_sensitivity, float)


# =========================================================================
#  Counterparty Portfolio Tests
# =========================================================================


class TestCounterpartyPortfolio:
    """Tests for counterparty exposure portfolio generation."""

    @pytest.fixture(scope="class")
    def cpty_portfolio(self) -> CounterpartyPortfolio:
        """Generate counterparty portfolio with seed=42."""
        gen = PortfolioGenerator(seed=42)
        return gen.generate_counterparty_portfolio()

    def test_500_counterparties(self, cpty_portfolio: CounterpartyPortfolio) -> None:
        """500 counterparties generated (300 financial + 200 commercial)."""
        assert len(cpty_portfolio.exposures) == 500

    def test_financial_alpha_14(self, cpty_portfolio: CounterpartyPortfolio) -> None:
        """Financial counterparties have alpha = 1.4."""
        fin = [e for e in cpty_portfolio.exposures if e.counterparty_id.startswith("FIN")]
        assert len(fin) == 300
        for e in fin:
            assert e.alpha == pytest.approx(1.4)

    def test_commercial_alpha_10(self, cpty_portfolio: CounterpartyPortfolio) -> None:
        """Commercial counterparties have alpha = 1.0."""
        com = [e for e in cpty_portfolio.exposures if e.counterparty_id.startswith("COM")]
        assert len(com) == 200
        for e in com:
            assert e.alpha == pytest.approx(1.0)

    def test_total_ead_positive(self, cpty_portfolio: CounterpartyPortfolio) -> None:
        """Total EAD is positive and in a reasonable range."""
        assert cpty_portfolio.total_ead > 0
        # Expected ~$200B range for derivatives portfolio
        assert cpty_portfolio.total_ead > 50_000.0

    def test_rwa_consistent(self, cpty_portfolio: CounterpartyPortfolio) -> None:
        """RWA = EAD * RW for each counterparty exposure."""
        for e in cpty_portfolio.exposures[:20]:
            assert e.rwa == pytest.approx(e.ead * e.risk_weight, rel=1e-6)


# =========================================================================
#  Financial Statement Tests
# =========================================================================


class TestFinancialStatements:
    """Tests for financial statement generation."""

    @pytest.fixture(scope="class")
    def fin_gen(self) -> FinancialStatementGenerator:
        """Create generator with seed=42."""
        return FinancialStatementGenerator(seed=42)

    def test_three_years_income_statements(self, fin_gen: FinancialStatementGenerator) -> None:
        """3 years of income statements generated."""
        stmts = fin_gen.generate_income_statements([2023, 2024, 2025])
        assert len(stmts) == 3
        assert stmts[0].year == 2023
        assert stmts[2].year == 2025

    def test_nii_in_expected_range(self, fin_gen: FinancialStatementGenerator) -> None:
        """NII should be approximately $60-70B per typical G-SIB.

        Base: II=$100B - IE=$35B = NII=$65B, with growth and noise.
        """
        stmts = fin_gen.generate_income_statements([2023, 2024, 2025])
        for stmt in stmts:
            assert stmt.net_interest_income > 50_000.0, f"NII too low: {stmt.net_interest_income}"
            assert stmt.net_interest_income < 90_000.0, f"NII too high: {stmt.net_interest_income}"

    def test_balance_sheet_total_assets(self, fin_gen: FinancialStatementGenerator) -> None:
        """Balance sheet total assets approximately $3.2T."""
        sheets = fin_gen.generate_balance_sheets([2023, 2024, 2025])
        assert len(sheets) == 3
        # First year should be close to $3.2T
        assert sheets[0].total_assets == pytest.approx(3_200_000.0, rel=0.05)

    def test_balance_sheet_grows(self, fin_gen: FinancialStatementGenerator) -> None:
        """Balance sheet grows ~3% per year."""
        sheets = fin_gen.generate_balance_sheets([2023, 2024, 2025])
        assert sheets[1].total_assets > sheets[0].total_assets
        assert sheets[2].total_assets > sheets[1].total_assets

    def test_business_indicator_components(self, fin_gen: FinancialStatementGenerator) -> None:
        """BI = ILDC + SC + FC, all components positive."""
        bi_data = fin_gen.generate_business_indicator_data(years=[2023, 2024, 2025])
        assert len(bi_data) == 3
        for bi in bi_data:
            assert bi.ildc > 0
            assert bi.sc > 0
            assert bi.fc >= 0
            assert bi.business_indicator == pytest.approx(bi.ildc + bi.sc + bi.fc)

    def test_nic_factor_default(self, fin_gen: FinancialStatementGenerator) -> None:
        """NIC factor defaults to 1.0 (not investment management)."""
        bi_data = fin_gen.generate_business_indicator_data(years=[2025])
        assert bi_data[0].nic_factor == pytest.approx(1.0)

    def test_generate_all(self, fin_gen: FinancialStatementGenerator) -> None:
        """generate_all returns all three components."""
        result = fin_gen.generate_all([2023, 2024, 2025])
        assert "income_statements" in result
        assert "balance_sheets" in result
        assert "business_indicator_data" in result


class TestPortfolioGeneratorAll:
    """Tests for PortfolioGenerator.generate_all."""

    def test_generate_all_keys(self) -> None:
        """generate_all returns all 4 portfolio types."""
        gen = PortfolioGenerator(seed=42)
        result = gen.generate_all()
        assert "credit" in result
        assert "trading" in result
        assert "counterparty" in result
        assert "securitization" in result

    def test_reproducibility(self) -> None:
        """Same seed produces identical portfolios."""
        gen1 = PortfolioGenerator(seed=42)
        gen2 = PortfolioGenerator(seed=42)
        p1 = gen1.generate_credit_portfolio()
        p2 = gen2.generate_credit_portfolio()
        assert p1.total_ead == pytest.approx(p2.total_ead)
        assert p1.count == p2.count
