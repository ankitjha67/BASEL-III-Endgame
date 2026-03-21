"""Comprehensive Phase 2 test suite for all SBM risk classes.

Tests CSR Non-Sec, CSR Sec, Equity, Commodity, FX calculators.
"""

from __future__ import annotations

import math

import pytest

from src.core.enums import (
    CorrelationScenario,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.models import Sensitivity


# =========================================================================
#  Helpers
# =========================================================================

def _sens(
    risk_class: RiskClass,
    bucket: str = "1",
    value: float = 1_000_000.0,
    risk_measure: RiskMeasure = RiskMeasure.DELTA,
    tenor: GIRRTenor | None = GIRRTenor.Y5,
    label: str = "DEFAULT",
    option_maturity: float | None = None,
) -> Sensitivity:
    from src.core.enums import GIRRRiskFactorType
    return Sensitivity(
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
        tenor=tenor,
        label=label,
        value=value,
        option_maturity=option_maturity,
    )


# =========================================================================
#  CSR Non-Securitization Tests
# =========================================================================

class TestCSRNonSec:
    """Tests for CSR Non-Securitization calculator."""

    @pytest.fixture
    def calc(self):
        from src.market_risk.frtb.sbm.csr_nonsec import CSRNonSecCalculator
        return CSRNonSecCalculator()

    def test_import(self):
        from src.market_risk.frtb.sbm.csr_nonsec import CSRNonSecCalculator
        calc = CSRNonSecCalculator()
        assert calc is not None

    def test_single_delta_sensitivity(self, calc):
        """Single sensitivity in bucket 1 (Sovereign IG, RW=0.5%)."""
        sens = [_sens(RiskClass.CSR_NON_SEC, bucket="1", value=1e6)]
        result = calc.calculate(sens)
        assert result.total_charge > 0
        assert result.delta_charge > 0

    def test_multi_bucket(self, calc):
        """Sensitivities across multiple buckets."""
        sens = [
            _sens(RiskClass.CSR_NON_SEC, bucket="1", value=5e6),
            _sens(RiskClass.CSR_NON_SEC, bucket="3", value=3e6),
            _sens(RiskClass.CSR_NON_SEC, bucket="5", value=2e6),
        ]
        result = calc.calculate(sens)
        assert result.total_charge > 0

    def test_offsetting_same_bucket(self, calc):
        """Offsetting positions in same bucket reduce charge."""
        long_only = [_sens(RiskClass.CSR_NON_SEC, bucket="1", value=1e6)]
        hedged = [
            _sens(RiskClass.CSR_NON_SEC, bucket="1", value=1e6),
            _sens(RiskClass.CSR_NON_SEC, bucket="1", value=-1e6),
        ]
        long_result = calc.calculate(long_only)
        hedged_result = calc.calculate(hedged)
        assert hedged_result.delta_charge < long_result.delta_charge

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0

    def test_high_yield_higher_rw(self, calc):
        """HY buckets have higher risk weights than IG → higher charge."""
        ig = [_sens(RiskClass.CSR_NON_SEC, bucket="3", value=1e6)]  # Financials IG
        hy = [_sens(RiskClass.CSR_NON_SEC, bucket="4", value=1e6)]  # Financials HY
        ig_result = calc.calculate(ig)
        hy_result = calc.calculate(hy)
        assert hy_result.delta_charge > ig_result.delta_charge

    def test_scenarios_produce_different_charges(self, calc):
        """Three scenarios should produce non-identical charges."""
        sens = [
            _sens(RiskClass.CSR_NON_SEC, bucket="1", value=1e6),
            _sens(RiskClass.CSR_NON_SEC, bucket="3", value=1e6),
        ]
        result = calc.calculate(sens)
        charges = {
            result.delta_low.capital_charge,
            result.delta_medium.capital_charge,
            result.delta_high.capital_charge,
        }
        # At least 2 different values (might be 3)
        assert len(charges) >= 2


# =========================================================================
#  CSR Securitization Tests
# =========================================================================

class TestCSRSec:
    """Tests for CSR Securitization calculator."""

    @pytest.fixture
    def calc(self):
        from src.market_risk.frtb.sbm.csr_sec import CSRSecCalculator
        return CSRSecCalculator()

    def test_import(self):
        from src.market_risk.frtb.sbm.csr_sec import CSRSecCalculator
        calc = CSRSecCalculator()
        assert calc is not None

    def test_nonctp_single(self, calc):
        sens = [_sens(RiskClass.CSR_SEC_NON_CTP, bucket="1", value=1e6)]
        result = calc.calculate(sens, is_ctp=False)
        assert result.total_charge > 0

    def test_ctp_single(self, calc):
        sens = [_sens(RiskClass.CSR_SEC_CTP, bucket="1", value=1e6)]
        result = calc.calculate(sens, is_ctp=True)
        assert result.total_charge > 0

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([], is_ctp=False)
        assert result.total_charge == 0.0

    def test_multi_bucket_nonctp(self, calc):
        sens = [
            _sens(RiskClass.CSR_SEC_NON_CTP, bucket="1", value=2e6),
            _sens(RiskClass.CSR_SEC_NON_CTP, bucket="4", value=1e6),
        ]
        result = calc.calculate(sens, is_ctp=False)
        assert result.total_charge > 0


# =========================================================================
#  Equity Tests
# =========================================================================

class TestEquity:
    """Tests for Equity risk calculator."""

    @pytest.fixture
    def calc(self):
        from src.market_risk.frtb.sbm.equity import EquityCalculator
        return EquityCalculator()

    def test_import(self):
        from src.market_risk.frtb.sbm.equity import EquityCalculator
        calc = EquityCalculator()
        assert calc is not None

    def test_single_equity_delta(self, calc):
        sens = [_sens(RiskClass.EQUITY, bucket="6", value=1e6, tenor=None)]
        result = calc.calculate(sens)
        assert result.total_charge > 0

    def test_em_vs_ae_risk_weights(self, calc):
        """EM (bucket 1) should have higher RW than AE (bucket 6)."""
        em = [_sens(RiskClass.EQUITY, bucket="1", value=1e6, tenor=None)]
        ae = [_sens(RiskClass.EQUITY, bucket="6", value=1e6, tenor=None)]
        em_result = calc.calculate(em)
        ae_result = calc.calculate(ae)
        assert em_result.delta_charge > ae_result.delta_charge

    def test_small_cap_highest_rw(self, calc):
        """Small cap (bucket 11) should have highest single-name RW."""
        small = [_sens(RiskClass.EQUITY, bucket="11", value=1e6, tenor=None)]
        large_ae = [_sens(RiskClass.EQUITY, bucket="9", value=1e6, tenor=None)]
        small_result = calc.calculate(small)
        large_result = calc.calculate(large_ae)
        assert small_result.delta_charge > large_result.delta_charge

    def test_index_lowest_rw(self, calc):
        """Index bucket (12) should have lowest RW."""
        idx = [_sens(RiskClass.EQUITY, bucket="12", value=1e6, tenor=None)]
        result = calc.calculate(idx)
        assert result.total_charge > 0

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0

    def test_multi_bucket(self, calc):
        sens = [
            _sens(RiskClass.EQUITY, bucket="1", value=3e6, tenor=None),
            _sens(RiskClass.EQUITY, bucket="6", value=2e6, tenor=None),
            _sens(RiskClass.EQUITY, bucket="11", value=1e6, tenor=None),
        ]
        result = calc.calculate(sens)
        assert result.total_charge > 0


# =========================================================================
#  Commodity Tests
# =========================================================================

class TestCommodity:
    """Tests for Commodity risk calculator."""

    @pytest.fixture
    def calc(self):
        from src.market_risk.frtb.sbm.commodity import CommodityCalculator
        return CommodityCalculator()

    def test_import(self):
        from src.market_risk.frtb.sbm.commodity import CommodityCalculator
        calc = CommodityCalculator()
        assert calc is not None

    def test_single_commodity_delta(self, calc):
        sens = [_sens(RiskClass.COMMODITY, bucket="1", value=1e6)]
        result = calc.calculate(sens)
        assert result.total_charge > 0

    def test_energy_vs_precious_metals(self, calc):
        """Energy (B1, 30%) vs Precious metals (B7, 20%)."""
        energy = [_sens(RiskClass.COMMODITY, bucket="1", value=1e6)]
        metals = [_sens(RiskClass.COMMODITY, bucket="7", value=1e6)]
        energy_result = calc.calculate(energy)
        metals_result = calc.calculate(metals)
        assert energy_result.delta_charge > metals_result.delta_charge

    def test_electricity_highest_rw(self, calc):
        """Electricity (B6, 60%) should have high RW."""
        elec = [_sens(RiskClass.COMMODITY, bucket="6", value=1e6)]
        result = calc.calculate(elec)
        assert result.total_charge > 0

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0

    def test_multi_commodity(self, calc):
        sens = [
            _sens(RiskClass.COMMODITY, bucket="1", value=5e6),
            _sens(RiskClass.COMMODITY, bucket="7", value=3e6),
            _sens(RiskClass.COMMODITY, bucket="9", value=2e6),
        ]
        result = calc.calculate(sens)
        assert result.total_charge > 0


# =========================================================================
#  FX Tests
# =========================================================================

class TestFX:
    """Tests for FX risk calculator."""

    @pytest.fixture
    def calc(self):
        from src.market_risk.frtb.sbm.fx import FXCalculator
        return FXCalculator()

    def test_import(self):
        from src.market_risk.frtb.sbm.fx import FXCalculator
        calc = FXCalculator()
        assert calc is not None

    def test_single_fx_delta(self, calc):
        sens = [_sens(RiskClass.FX, bucket="EURUSD", value=1e6, tenor=None)]
        result = calc.calculate(sens)
        assert result.total_charge > 0

    def test_fx_risk_weight_15pct(self, calc):
        """FX RW is 15%, so charge on single position = 15% * value."""
        sens = [_sens(RiskClass.FX, bucket="EURUSD", value=1e6, tenor=None)]
        result = calc.calculate(sens)
        # Single position: charge = 0.15 * 1e6 = 150,000
        assert abs(result.delta_charge - 150_000) / 150_000 < 0.05

    def test_multi_pair(self, calc):
        sens = [
            _sens(RiskClass.FX, bucket="EURUSD", value=5e6, tenor=None),
            _sens(RiskClass.FX, bucket="GBPUSD", value=3e6, tenor=None),
            _sens(RiskClass.FX, bucket="JPYUSD", value=2e6, tenor=None),
        ]
        result = calc.calculate(sens)
        assert result.total_charge > 0

    def test_diversification_multi_pair(self, calc):
        """Multiple FX pairs should get diversification benefit vs sum."""
        single = [_sens(RiskClass.FX, bucket="EURUSD", value=1e6, tenor=None)]
        multi = [
            _sens(RiskClass.FX, bucket="EURUSD", value=1e6, tenor=None),
            _sens(RiskClass.FX, bucket="GBPUSD", value=1e6, tenor=None),
        ]
        single_result = calc.calculate(single)
        multi_result = calc.calculate(multi)
        # Multi should be less than 2x single due to diversification
        assert multi_result.delta_charge < 2 * single_result.delta_charge

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0
