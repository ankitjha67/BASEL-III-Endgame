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


# ---------------------------------------------------------------------------
#  Per-regime market risk, securitisation, CCP, leverage and large exposures
# ---------------------------------------------------------------------------

SEC_DEALS = [("RMBS", 10_000.0, 0.035, 0.02), ("CLO", 8_000.0, 0.080, 0.03)]
SEC_TRANCHES = [
    ("SNR", 0.20, 1.00, True, "AAA"),
    ("MEZ", 0.08, 0.20, False, "A"),
    ("JNR", 0.03, 0.08, False, "BB"),
]


@pytest.fixture(scope="module")
def full_result():  # type: ignore[no-untyped-def]
    import numpy as np

    from src.data_generation.frtb_inputs import trading_positions_to_neutral_frtb
    from src.jurisdictions.comparison import (
        banking_book_large_exposures,
        reference_securitisations,
    )
    from src.jurisdictions.frtb_base import RRAOCategory, RRAOPositionInput
    from src.jurisdictions.pillar1_base import CCPExposureInput, LeverageInputs

    gen = PortfolioGenerator(seed=11)
    credit = gen.generate_credit_portfolio().exposures[:150]
    book = build_reference_book(credit, SACCR_ROWS, OP, seed=11)
    sens, drc = trading_positions_to_neutral_frtb(
        gen.generate_trading_portfolio().positions, np.random.default_rng(11)
    )
    book.frtb_sensitivities, book.drc_positions = sens, drc  # type: ignore[assignment]
    book.rrao_positions = [
        RRAOPositionInput(position_id="X", gross_notional=1_000.0, category=RRAOCategory.EXOTIC)
    ]
    book.sec_tranches = reference_securitisations(SEC_DEALS, SEC_TRANCHES, 500.0, 5.0)
    book.ccp_exposures = [
        CCPExposureInput(
            ccp_id="Q",
            trade_exposure=10_000.0,
            default_fund_contribution=500.0,
            k_ccp=2_000.0,
            total_default_fund=10_000.0,
        )
    ]
    book.leverage = LeverageInputs(
        on_balance_sheet_assets=2_500_000.0,
        derivative_rc=20_000.0,
        derivative_pfe_addon=40_000.0,
        sft_gross_assets=200_000.0,
        obs_notional_by_ccf={0.1: 100_000.0, 0.4: 200_000.0},
        central_bank_reserves=250_000.0,
    )
    book.large_exposures = banking_book_large_exposures(book.exposures)
    return run_comparison(
        book,
        2027,
        capital_usd={"cet1": 150_000.0, "tier1": 170_000.0, "total": 200_000.0},
        gsib_method1_score_bps=388.0,
        us_gsib_rate=0.034,
        us_scb=0.055,
        market_rwa_usd=MARKET_FALLBACK,
    )


MARKET_FALLBACK = 123_456.0
"""Used only for a regime without its own FRTB calculator."""


def test_nothing_held_common_but_capital(full_result) -> None:  # type: ignore[no-untyped-def]
    import importlib.util

    common = full_result.common_components
    assert common[0] == "capital resources (CET1, Tier 1, total capital)"
    if importlib.util.find_spec("src.jurisdictions.sg.frtb") is not None:
        assert common == common[:1]
    else:
        assert common[1:] == ["market risk RWA for SG (caller-supplied; no calculator)"]


def test_market_risk_per_regime(full_result) -> None:  # type: ignore[no-untyped-def]
    own = [r for r in full_result.regimes if r.market_rwa != MARKET_FALLBACK]
    assert len(own) >= 5
    for r in own:
        assert r.market_rwa == pytest.approx(12.5 * (r.market_sbm + r.market_drc + r.market_rrao))
        assert r.market_binding_scenario in ("LOW", "MEDIUM", "HIGH")
        assert r.market_rrao == pytest.approx(10.0)  # 1.0% of 1,000 exotic (MAR23.8)


def test_us_securitisation_sec_sa_only(full_result) -> None:  # type: ignore[no-untyped-def]
    by = {r.jurisdiction: r for r in full_result.regimes}
    us = by[Jurisdiction.US].securitisation_rows
    assert {x["approach"] for x in us} <= {"SEC_SA", "RW_1250"}
    bcbs = by[Jurisdiction.BCBS].securitisation_rows
    assert any(x["approach"] == "SEC_ERBA" for x in bcbs)
    assert len(us) == len(bcbs) == 6


def test_sec_senior_tranche_floor(full_result) -> None:  # type: ignore[no-untyped-def]
    for r in full_result.regimes:
        for x in r.securitisation_rows:
            assert (
                float(x["risk_weight"]) >= 0.15 - 1e-12
            )  # 15% RW floor (US § __.133; BCBS SEC-SA / SEC-ERBA floor)


def test_ccp_rwa_included(full_result) -> None:  # type: ignore[no-untyped-def]
    for r in full_result.regimes:
        assert r.ccp_rwa > 0
        assert r.standardised_rwa == pytest.approx(
            r.credit_rwa
            + r.ccr_rwa
            + r.cva_rwa
            + r.op_rwa
            + r.market_rwa
            + r.securitisation_rwa
            + r.ccp_rwa
        )


def test_leverage_per_regime(full_result) -> None:  # type: ignore[no-untyped-def]
    by = {r.jurisdiction: r for r in full_result.regimes}
    assert by[Jurisdiction.UK].leverage_exclusions == pytest.approx(250_000.0)
    assert by[Jurisdiction.UK].leverage_exposure < by[Jurisdiction.BCBS].leverage_exposure
    for r in full_result.regimes:
        assert r.leverage_ratio == pytest.approx(170_000.0 / r.leverage_exposure)


def test_large_exposures_evaluated(full_result) -> None:  # type: ignore[no-untyped-def]
    for r in full_result.regimes:
        assert 0.0 <= r.large_exposure_max_pct_tier1 < 1.0


def test_table_flat(full_result) -> None:  # type: ignore[no-untyped-def]
    row = full_result.table()[0]
    assert "securitisation_rows" not in row and "market_by_class" not in row
    assert "market_sbm" in row and "leverage_exposure" in row
