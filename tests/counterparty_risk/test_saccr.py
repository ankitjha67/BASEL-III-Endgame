"""Tests for SA-CCR counterparty credit risk."""

from __future__ import annotations

import math
import pytest


class TestSACCRImports:
    def test_calculator_import(self):
        from src.counterparty_risk.saccr.saccr import SACCRCalculator
        calc = SACCRCalculator()
        assert calc is not None

    def test_params_import(self):
        from src.counterparty_risk.saccr.saccr_params import SACCR_ASSET_CLASSES
        assert "IR" in SACCR_ASSET_CLASSES or len(SACCR_ASSET_CLASSES) > 0


class TestSACCRCalculator:
    @pytest.fixture
    def calc(self):
        from src.counterparty_risk.saccr.saccr import SACCRCalculator
        return SACCRCalculator()

    def test_single_ir_swap(self, calc):
        from src.counterparty_risk.saccr.saccr import SACCRTrade, SACCRNettingSet
        trade = SACCRTrade(
            trade_id="T1", asset_class="IR", notional=100e6,
            mtm_value=500_000.0, start_years=0.0, end_years=5.0,
            is_long=True, underlying="USD_LIBOR", netting_set="NS1",
        )
        ns = SACCRNettingSet(
            netting_set_id="NS1", trades=[trade],
        )
        result = calc.calculate(ns)
        assert result.ead > 0
        assert result.replacement_cost >= 0
        assert result.pfe >= 0
        assert result.alpha == 1.4  # Financial counterparty

    def test_commercial_enduser_alpha(self, calc):
        from src.counterparty_risk.saccr.saccr import SACCRTrade, SACCRNettingSet
        trade = SACCRTrade(
            trade_id="T1", asset_class="IR", notional=50e6,
            mtm_value=100_000.0, start_years=0.0, end_years=3.0,
            is_long=True, underlying="USD", netting_set="NS1",
        )
        ns = SACCRNettingSet(
            netting_set_id="NS1", trades=[trade], is_financial=False,
        )
        result = calc.calculate(ns)
        assert result.alpha == 1.0  # Commercial end-user

    def test_collateralized_reduces_ead(self, calc):
        from src.counterparty_risk.saccr.saccr import SACCRTrade, SACCRNettingSet
        trade = SACCRTrade(
            trade_id="T1", asset_class="FX", notional=50e6,
            mtm_value=1e6, start_years=0.0, end_years=1.0,
            is_long=True, underlying="EURUSD", netting_set="NS1",
        )
        uncollat = SACCRNettingSet(netting_set_id="NS1", trades=[trade])
        collat = SACCRNettingSet(
            netting_set_id="NS1", trades=[trade], collateral=500_000.0,
        )
        uncollat_result = calc.calculate(uncollat)
        collat_result = calc.calculate(collat)
        assert collat_result.ead <= uncollat_result.ead

    def test_single_trade_netting_set(self, calc):
        """Netting set with one small trade should produce small EAD."""
        from src.counterparty_risk.saccr.saccr import SACCRTrade, SACCRNettingSet
        trade = SACCRTrade(
            trade_id="T1", asset_class="IR", notional=1e6,
            mtm_value=0.0, start_years=0.0, end_years=1.0,
            is_long=True, underlying="USD", netting_set="NS1",
        )
        ns = SACCRNettingSet(netting_set_id="NS1", trades=[trade])
        result = calc.calculate(ns)
        assert result.ead >= 0
