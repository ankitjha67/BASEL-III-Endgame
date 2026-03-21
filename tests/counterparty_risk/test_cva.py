"""Tests for CVA Risk calculator.

Updated to import from src.cva_risk (canonical location) instead of
the deprecated src.counterparty_risk.cva stub.
"""

from __future__ import annotations

import pytest


class TestCVAImports:
    def test_calculator_import(self):
        from src.cva_risk import CVACalculator
        calc = CVACalculator()
        assert calc is not None

    def test_params_import(self):
        from src.cva_risk import BA_CVA_RISK_WEIGHTS
        assert len(BA_CVA_RISK_WEIGHTS) > 0


class TestCVACalculator:
    @pytest.fixture
    def calc(self):
        from src.cva_risk import BACVACalculator
        return BACVACalculator()

    def test_single_counterparty_ba_cva(self, calc):
        from src.cva_risk import BACVACounterparty
        cp = BACVACounterparty(
            counterparty_id="CP1", rating="BBB", sector="CORPORATE",
            ead=100e6, effective_maturity=3.0,
        )
        result = calc.calculate([cp])
        assert result.k_ba_cva > 0

    def test_higher_rating_lower_charge(self, calc):
        from src.cva_risk import BACVACounterparty
        aaa = BACVACounterparty(
            counterparty_id="AAA", rating="AAA", sector="CORPORATE",
            ead=100e6, effective_maturity=3.0,
        )
        ccc = BACVACounterparty(
            counterparty_id="CCC", rating="CCC", sector="CORPORATE",
            ead=100e6, effective_maturity=3.0,
        )
        aaa_result = calc.calculate([aaa])
        ccc_result = calc.calculate([ccc])
        assert aaa_result.k_ba_cva < ccc_result.k_ba_cva

    def test_empty_counterparties(self, calc):
        result = calc.calculate([])
        assert result.k_ba_cva == 0.0

    def test_multiple_counterparties(self, calc):
        from src.cva_risk import BACVACounterparty
        cps = [
            BACVACounterparty(counterparty_id="A", rating="A", sector="FINANCIAL",
                              ead=50e6, effective_maturity=2.0),
            BACVACounterparty(counterparty_id="B", rating="BBB", sector="CORPORATE",
                              ead=80e6, effective_maturity=5.0),
        ]
        result = calc.calculate(cps)
        assert result.k_ba_cva > 0
