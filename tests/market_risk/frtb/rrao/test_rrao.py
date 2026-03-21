"""Tests for Residual Risk Add-On (RRAO) calculator."""

from __future__ import annotations

import pytest

from src.core.enums import RRAOCategory
from src.core.models import RRAOPosition
from src.market_risk.frtb.rrao.rrao import RRAOCalculator


def _rrao_pos(
    notional: float = 1_000_000.0,
    category: RRAOCategory = RRAOCategory.OTHER,
) -> RRAOPosition:
    return RRAOPosition(
        instrument_id="INST_1",
        notional=notional,
        category=category,
    )


class TestRRAO:
    """Tests for RRAO calculator."""

    @pytest.fixture
    def calc(self):
        return RRAOCalculator()

    def test_import(self):
        calc = RRAOCalculator()
        assert calc is not None

    def test_exotic_1pct(self, calc):
        """Exotic underlyings get 1.0% charge."""
        positions = [_rrao_pos(notional=10e6, category=RRAOCategory.EXOTIC)]
        result = calc.calculate(positions)
        assert abs(result.exotic_charge - 100_000) < 1.0
        assert abs(result.total_charge - 100_000) < 1.0

    def test_other_01pct(self, calc):
        """Other residual risks get 0.1% charge."""
        positions = [_rrao_pos(notional=10e6, category=RRAOCategory.OTHER)]
        result = calc.calculate(positions)
        assert abs(result.other_charge - 10_000) < 1.0
        assert abs(result.total_charge - 10_000) < 1.0

    def test_exempt_no_charge(self, calc):
        """Exempt positions get no charge."""
        positions = [_rrao_pos(notional=10e6, category=RRAOCategory.EXEMPT)]
        result = calc.calculate(positions)
        assert result.total_charge == 0.0
        assert result.exempt_notional == 10e6

    def test_mixed_portfolio(self, calc):
        """Mix of exotic, other, and exempt."""
        positions = [
            _rrao_pos(notional=5e6, category=RRAOCategory.EXOTIC),
            _rrao_pos(notional=10e6, category=RRAOCategory.OTHER),
            _rrao_pos(notional=20e6, category=RRAOCategory.EXEMPT),
        ]
        result = calc.calculate(positions)
        assert abs(result.exotic_charge - 50_000) < 1.0
        assert abs(result.other_charge - 10_000) < 1.0
        assert abs(result.total_charge - 60_000) < 1.0
        assert result.exempt_notional == 20e6

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0
