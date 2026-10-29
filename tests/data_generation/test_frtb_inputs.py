"""Tests for the synthetic trading-book -> FRTB-SA input mapper and DRC-sec wiring."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.enums import RiskClass, RiskMeasure
from src.data_generation.frtb_inputs import (
    DEFAULT_NET_FRACTION,
    PV01_SHOCK,
    RELATIVE_SHOCK,
    trading_positions_to_frtb_inputs,
)
from src.data_generation.portfolio_generator import PortfolioGenerator
from src.market_risk.frtb.calculator import FRTBCalculator


@pytest.fixture(scope="module")
def positions() -> list[object]:
    return list(PortfolioGenerator(seed=7).generate_trading_portfolio().positions)


def test_sensitivity_units(positions: list[object]) -> None:
    """§ __.207(b): GIRR/CSR delta = PV01 / 0.0001; equity/commodity/FX = P&L(1%) / 0.01."""
    sens, _ = trading_positions_to_frtb_inputs(positions, np.random.default_rng(1), net_fraction=1.0)
    girr_pos = next(p for p in positions if p.risk_class == "GIRR")
    girr = next(s for s in sens if s.risk_class == RiskClass.GIRR)
    assert girr.value == pytest.approx(girr_pos.delta_sensitivity / PV01_SHOCK)
    fx_pos = next(p for p in positions if p.risk_class == "FX")
    fx = next(s for s in sens if s.risk_class == RiskClass.FX and s.risk_measure == RiskMeasure.DELTA)
    assert fx.value == pytest.approx(fx_pos.delta_sensitivity / RELATIVE_SHOCK)


def test_net_fraction_scales_linearly(positions: list[object]) -> None:
    full, _ = trading_positions_to_frtb_inputs(positions, np.random.default_rng(1), net_fraction=1.0)
    net, _ = trading_positions_to_frtb_inputs(positions, np.random.default_rng(1))
    assert net[0].value == pytest.approx(full[0].value * DEFAULT_NET_FRACTION)


def test_drc_position_per_csr_position(positions: list[object]) -> None:
    _, drc = trading_positions_to_frtb_inputs(positions, np.random.default_rng(1))
    assert len(drc) == sum(1 for p in positions if p.risk_class == "CSR_NONSEC")


def test_master_calculator_sums_drc_components(positions: list[object]) -> None:
    """DRC total = non-sec + sec non-CTP + CTP, no diversification (§ __.210)."""
    from src.market_risk.frtb.drc.drc_sec_nonctp import DRCSecNonCTPPosition
    sens, drc = trading_positions_to_frtb_inputs(positions, np.random.default_rng(1))
    base = FRTBCalculator().calculate(sensitivities=sens, drc_positions=drc)
    sec = DRCSecNonCTPPosition(tranche_id="T1", pool_id="P1", asset_class="CORPORATE",
                               market_value=500.0, maturity_years=3.0, is_long=True,
                               banking_book_risk_weight=1.0)
    withsec = FRTBCalculator().calculate(sensitivities=sens, drc_positions=drc + [sec])
    assert withsec.drc_sec_nonctp > 0
    assert withsec.drc_nonsec == pytest.approx(base.drc_nonsec)
    assert withsec.drc_total == pytest.approx(base.drc_nonsec + withsec.drc_sec_nonctp)
