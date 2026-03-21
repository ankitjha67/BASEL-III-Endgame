"""Tests for CVA Risk calculator."""

from __future__ import annotations

import pytest


class TestCVAImports:
    def test_calculator_import(self):
        from src.counterparty_risk.cva.cva import CVACalculator
        calc = CVACalculator()
        assert calc is not None

    def test_params_import(self):
        from src.counterparty_risk.cva.cva_params import CVA_RISK_WEIGHTS
        assert len(CVA_RISK_WEIGHTS) > 0


class TestCVACalculator:
    @pytest.fixture
    def calc(self):
        from src.counterparty_risk.cva.cva import CVACalculator
        return CVACalculator()

    def test_single_counterparty_ba_cva(self, calc):
        from src.counterparty_risk.cva.cva import CVACounterparty
        cp = CVACounterparty(
            counterparty_id="CP1", rating="BBB", sector="CORPORATE",
            ead=100e6, effective_maturity=3.0,
        )
        result = calc.calculate_ba_cva([cp])
        assert result.total_cva_charge > 0

    def test_higher_rating_lower_charge(self, calc):
        from src.counterparty_risk.cva.cva import CVACounterparty
        aaa = CVACounterparty(
            counterparty_id="AAA", rating="AAA", sector="CORPORATE",
            ead=100e6, effective_maturity=3.0,
        )
        ccc = CVACounterparty(
            counterparty_id="CCC", rating="CCC", sector="CORPORATE",
            ead=100e6, effective_maturity=3.0,
        )
        aaa_result = calc.calculate_ba_cva([aaa])
        ccc_result = calc.calculate_ba_cva([ccc])
        assert aaa_result.total_cva_charge < ccc_result.total_cva_charge

    def test_empty_counterparties(self, calc):
        result = calc.calculate_ba_cva([])
        assert result.total_cva_charge == 0.0

    def test_multiple_counterparties(self, calc):
        from src.counterparty_risk.cva.cva import CVACounterparty
        cps = [
            CVACounterparty(counterparty_id="A", rating="A", sector="FINANCIAL",
                           ead=50e6, effective_maturity=2.0),
            CVACounterparty(counterparty_id="B", rating="BBB", sector="CORPORATE",
                           ead=80e6, effective_maturity=5.0),
        ]
        result = calc.calculate_ba_cva(cps)
        assert result.total_cva_charge > 0
