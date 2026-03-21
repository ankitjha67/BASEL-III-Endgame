"""Tests for Securitization framework."""

from __future__ import annotations

import pytest


class TestSecuritizationImports:
    def test_calculator_import(self):
        from src.securitization.sec_framework import SecuritizationCalculator
        calc = SecuritizationCalculator()
        assert calc is not None


class TestSecuritizationCalculator:
    @pytest.fixture
    def calc(self):
        from src.securitization.sec_framework import SecuritizationCalculator
        return SecuritizationCalculator()

    def test_senior_tranche_lower_rw(self, calc):
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=500e6,
        )
        senior = SecuritizationTranche(
            tranche_id="T_SR", pool_id="P1",
            attachment_point=0.10, detachment_point=1.0,
            notional=100e6, is_senior=True,
        )
        junior = SecuritizationTranche(
            tranche_id="T_JR", pool_id="P1",
            attachment_point=0.0, detachment_point=0.05,
            notional=50e6, is_senior=False,
        )
        sr_result = calc.calculate([senior], pool)
        jr_result = calc.calculate([junior], pool)
        # Senior tranche should have lower RW than junior
        sr_avg_rw = sr_result.total_rwa / 100e6 if sr_result.total_rwa > 0 else 0
        jr_avg_rw = jr_result.total_rwa / 50e6 if jr_result.total_rwa > 0 else 0
        assert sr_avg_rw < jr_avg_rw or jr_avg_rw >= 12.50

    def test_max_rw_1250(self, calc):
        """Risk weight capped at 1250%."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(
            pool_id="P1", total_ead=1e9, pool_rwa=900e6,
        )
        thin = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.0, detachment_point=0.01,
            notional=10e6,
        )
        result = calc.calculate([thin], pool)
        rw = result.rw_by_tranche.get("T1", 0)
        assert rw <= 12.50  # 1250% cap

    def test_empty_tranches(self, calc):
        from src.securitization.sec_framework import SecuritizationPool
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=100e6)
        result = calc.calculate([], pool)
        assert result.total_rwa == 0.0

    def test_resecuritization_higher_rw(self, calc):
        """Resecuritization should get higher RW (p=1.5 vs p=0.5)."""
        from src.securitization.sec_framework import (
            SecuritizationPool, SecuritizationTranche,
        )
        pool = SecuritizationPool(pool_id="P1", total_ead=1e9, pool_rwa=400e6)
        normal = SecuritizationTranche(
            tranche_id="T1", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6,
        )
        resec = SecuritizationTranche(
            tranche_id="T2", pool_id="P1",
            attachment_point=0.05, detachment_point=0.15,
            notional=100e6, is_resecuritization=True,
        )
        normal_result = calc.calculate([normal], pool)
        resec_result = calc.calculate([resec], pool)
        assert resec_result.total_rwa >= normal_result.total_rwa
