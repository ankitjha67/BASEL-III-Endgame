"""Tests for the cross-jurisdiction comparison engine."""

from __future__ import annotations

import pytest

from src.data_generation.portfolio_generator import PortfolioGenerator
from src.jurisdictions.base import AssetClass, Jurisdiction, OpRiskInputs, SAExposure
from src.jurisdictions.comparison import (
    ECB_EUR_REFERENCE_RATES_20241231,
    build_reference_book,
    floor_sensitivity,
    run_comparison,
    scale_exposure,
    scale_op_inputs,
    usd_to_local,
)

OP = OpRiskInputs(
    interest_income=[95_000.0, 102_000.0, 115_000.0],
    interest_expense=[45_000.0, 52_000.0, 67_000.0],
    interest_earning_assets=[2_300_000.0, 2_500_000.0, 2_700_000.0],
    dividend_income=[2_100.0] * 3,
    fee_income=[40_000.0] * 3,
    fee_expense=[15_000.0] * 3,
    other_operating_income=[8_000.0] * 3,
    other_operating_expense=[11_000.0] * 3,
    net_pnl_trading_book=[10_000.0] * 3,
    net_pnl_banking_book=[500.0] * 3,
    annual_operational_losses=[3_000.0] * 10,
)

SACCR_ROWS = [
    {
        "netting_set_id": "N1",
        "rc": 100.0,
        "pfe": 200.0,
        "multiplier": 1.0,
        "mtm": 100.0,
        "collateral": 0.0,
        "counterparty_type": "BANK",
        "commercial_end_user": False,
        "maturity": 3.0,
        "margined": True,
    },
    {
        "netting_set_id": "N2",
        "rc": 50.0,
        "pfe": 80.0,
        "multiplier": 0.8,
        "mtm": 50.0,
        "collateral": 0.0,
        "counterparty_type": "CORPORATE",
        "commercial_end_user": True,
        "maturity": 4.0,
    },
]


@pytest.fixture(scope="module")
def result():  # type: ignore[no-untyped-def]
    credit = PortfolioGenerator(seed=11).generate_credit_portfolio().exposures[:150]
    book = build_reference_book(credit, SACCR_ROWS, OP, seed=11)
    return run_comparison(
        book,
        2027,
        market_rwa_usd=100_000.0,
        securitisation_rwa_usd=20_000.0,
        capital_usd={"cet1": 150_000.0, "tier1": 170_000.0, "total": 200_000.0},
        leverage_exposure_usd=3_000_000.0,
        gsib_method1_score_bps=388.0,
        us_gsib_rate=0.034,
        us_scb=0.055,
    )


def test_fx_from_ecb_reference_rates() -> None:
    assert usd_to_local("USD") == 1.0
    assert usd_to_local("EUR") == pytest.approx(1 / 1.0389)
    assert usd_to_local("GBP") == pytest.approx(0.82918 / 1.0389)
    assert usd_to_local("SGD") == pytest.approx(1.4164 / 1.0389)
    assert ECB_EUR_REFERENCE_RATES_20241231["CAD"] == 1.4948


def test_scaling_is_monetary_only() -> None:
    e = SAExposure(
        exposure_id="x",
        asset_class=AssetClass.RESIDENTIAL_RE,
        on_balance_amount=100.0,
        property_value=200.0,
        ltv=0.5,
    )
    s = scale_exposure(e, 2.0)
    assert s.on_balance_amount == 200.0 and s.property_value == 400.0 and s.ltv == 0.5
    assert scale_op_inputs(OP, 0.5).fee_income[0] == pytest.approx(20_000.0)


def test_all_regimes(result) -> None:  # type: ignore[no-untyped-def]
    assert {r.jurisdiction for r in result.regimes} == set(Jurisdiction)


def test_us_no_floor_and_scb(result) -> None:  # type: ignore[no-untyped-def]
    us = next(r for r in result.regimes if r.jurisdiction == Jurisdiction.US)
    assert not us.floor_applies
    assert us.cet1_requirement == pytest.approx(0.045 + 0.055 + 0.034)


def test_sa_bank_floor_never_binds(result) -> None:  # type: ignore[no-untyped-def]
    for r in result.regimes:
        assert r.total_rwa == pytest.approx(r.standardised_rwa)


def test_common_components_identical(result) -> None:  # type: ignore[no-untyped-def]
    assert len({r.market_rwa for r in result.regimes}) == 1
    assert len({r.securitisation_rwa for r in result.regimes}) == 1


def test_alpha_one_for_end_users_in_us_and_uk(result) -> None:  # type: ignore[no-untyped-def]
    by = {r.jurisdiction: r for r in result.regimes}
    # N2 is a commercial end-user: alpha 1.0 (US § __.114(e)(4); UK Art 274(2)); 1.4 under BCBS
    assert by[Jurisdiction.US].ccr_ead < by[Jurisdiction.BCBS].ccr_ead
    assert by[Jurisdiction.UK].ccr_ead < by[Jurisdiction.BCBS].ccr_ead


def test_floor_sensitivity(result) -> None:  # type: ignore[no-untyped-def]
    rows = floor_sensitivity(result, (2027, 2030), (0.5,))
    bcbs27 = next(x for x in rows if x.jurisdiction == Jurisdiction.BCBS and x.year == 2027)
    assert bcbs27.floor_factor == pytest.approx(0.70)  # RBC90.1
    assert bcbs27.add_on == pytest.approx((0.70 - 0.5) * bcbs27.standardised_rwa)
    eu30 = next(x for x in rows if x.jurisdiction == Jurisdiction.EU and x.year == 2030)
    assert eu30.floor_factor == pytest.approx(0.725)  # CRR Art. 92(3), 465(1)
    us = [x for x in rows if x.jurisdiction == Jurisdiction.US]
    assert all(x.add_on == 0 for x in us)
