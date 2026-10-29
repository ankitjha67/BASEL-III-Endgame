"""Tests for the US regime adapter (March 2026 ERBA NPR)."""

from __future__ import annotations

import pytest

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    OBSCategory,
    OpRiskInputs,
    PFPhase,
    RatingBucket,
    RegimeCalculator,
    SACCRNettingSetInput,
    SAExposure,
    SCRAGrade,
)
from src.jurisdictions.us import USRegime

US = USRegime()


def _e(ac: AssetClass, **kw: object) -> SAExposure:
    return SAExposure(exposure_id="X", asset_class=ac, on_balance_amount=100.0, **kw)


def test_protocol() -> None:
    assert isinstance(US, RegimeCalculator)


@pytest.mark.parametrize(
    "ltv,rw", [(0.45, 0.20), (0.55, 0.25), (0.75, 0.30), (0.85, 0.40), (0.95, 0.50), (1.10, 0.70)]
)
def test_residential_table_5(ltv: float, rw: float) -> None:
    """Table 5 to § __.111."""
    assert US.risk_weight(_e(AssetClass.RESIDENTIAL_RE, ltv=ltv)).risk_weight == pytest.approx(rw)


@pytest.mark.parametrize("ltv,rw", [(0.45, 0.30), (0.75, 0.45), (1.10, 1.05)])
def test_residential_table_6_cash_flow_dependent(ltv: float, rw: float) -> None:
    r = US.risk_weight(_e(AssetClass.RESIDENTIAL_RE, ltv=ltv, is_cash_flow_dependent=True))
    assert r.risk_weight == pytest.approx(rw)


@pytest.mark.parametrize(
    "grade,enhanced,rw",
    [
        (SCRAGrade.A, True, 0.30),
        (SCRAGrade.A, False, 0.40),
        (SCRAGrade.B, False, 0.75),
        (SCRAGrade.C, False, 1.50),
    ],
)
def test_bank_table_2(grade: SCRAGrade, enhanced: bool, rw: float) -> None:
    r = US.risk_weight(_e(AssetClass.BANK, scra_grade=grade, scra_grade_a_enhanced=enhanced))
    assert r.risk_weight == pytest.approx(rw)


def test_ratings_ignored_939a() -> None:
    """Dodd-Frank s.939A: an AAA rating does not lower a US corporate weight."""
    rated = US.risk_weight(_e(AssetClass.CORPORATE, rating=RatingBucket.AAA_TO_AA_MINUS))
    assert rated.risk_weight == pytest.approx(1.00)
    ig = US.risk_weight(_e(AssetClass.CORPORATE, is_investment_grade=True))
    assert ig.risk_weight == pytest.approx(0.65)


def test_project_finance() -> None:
    assert US.risk_weight(
        _e(AssetClass.SPECIALISED_LENDING_PF, pf_phase=PFPhase.PRE_OPERATIONAL)
    ).risk_weight == pytest.approx(1.30)
    assert US.risk_weight(
        _e(AssetClass.SPECIALISED_LENDING_PF, pf_phase=PFPhase.OPERATIONAL)
    ).risk_weight == pytest.approx(1.00)


@pytest.mark.parametrize("et,rw", [(EquityType.PUBLICLY_TRADED, 3.0), (EquityType.NON_PUBLIC, 4.0)])
def test_equity(et: EquityType, rw: float) -> None:
    assert US.risk_weight(_e(AssetClass.EQUITY, equity_type=et)).risk_weight == pytest.approx(rw)


def test_retail() -> None:
    assert US.risk_weight(_e(AssetClass.RETAIL_TRANSACTOR)).risk_weight == pytest.approx(0.45)
    assert US.risk_weight(_e(AssetClass.RETAIL_REGULATORY)).risk_weight == pytest.approx(0.75)
    assert US.risk_weight(_e(AssetClass.RETAIL_OTHER)).risk_weight == pytest.approx(1.00)


@pytest.mark.parametrize(
    "cat,ccf",
    [
        (OBSCategory.UNCONDITIONALLY_CANCELLABLE, 0.10),
        (OBSCategory.COMMITMENT_OTHER, 0.40),
        (OBSCategory.SHORT_TERM_TRADE_LC, 0.20),
        (OBSCategory.TRANSACTION_RELATED_CONTINGENT, 0.50),
        (OBSCategory.DIRECT_CREDIT_SUBSTITUTE, 1.00),
    ],
)
def test_ccf_112(cat: OBSCategory, ccf: float) -> None:
    e = SAExposure(
        exposure_id="O",
        asset_class=AssetClass.CORPORATE,
        off_balance_notional=100.0,
        obs_category=cat,
    )
    r = US.risk_weight(e)
    assert r.ccf == pytest.approx(ccf)
    assert r.exposure_amount == pytest.approx(100.0 * ccf)


def test_collateral_reduces_exposure() -> None:
    e = _e(AssetClass.CORPORATE, financial_collateral_value=50.0, collateral_haircut_class="cash")
    r = US.risk_weight(e)
    assert r.exposure_amount == pytest.approx(50.0)


def test_guarantee_substitution() -> None:
    e = _e(AssetClass.CORPORATE, guarantee_amount=60.0, guarantor_asset_class=AssetClass.SOVEREIGN)
    r = US.risk_weight(e)
    assert r.rwa == pytest.approx(40.0 * 1.00)


def test_no_output_floor() -> None:
    f = US.output_floor(1_000.0, 2_000.0, 2028)
    assert not f.applies and f.floored_rwa == 1_000.0


def test_capital_requirements() -> None:
    c = US.capital_requirements(systemic_bucket_or_rate=0.034, stress_buffer=0.055)
    assert c.cet1_minimum == 0.045 and c.conservation_buffer == 0.0
    assert c.cet1_requirement == pytest.approx(0.045 + 0.055 + 0.034)
    assert US.capital_requirements(stress_buffer=0.01).stress_buffer == 0.025


def test_saccr_alpha() -> None:
    ns = SACCRNettingSetInput(netting_set_id="N", replacement_cost=10.0, aggregate_addon=20.0)
    assert US.saccr_ead(ns).ead == pytest.approx(1.4 * 30.0)
    cu = ns.model_copy(update={"counterparty_is_nonfinancial": True})
    assert US.saccr_ead(cu).ead == pytest.approx(30.0)


def test_op_risk_no_ilm() -> None:
    three = [1.0, 1.0, 1.0]
    r = US.operational_risk(
        OpRiskInputs(
            interest_income=[95_000.0, 102_000.0, 115_000.0],
            interest_expense=[45_000.0, 52_000.0, 67_000.0],
            interest_earning_assets=[2_300_000.0, 2_500_000.0, 2_700_000.0],
            dividend_income=[2_100.0] * 3,
            fee_income=[40_000.0] * 3,
            fee_expense=[15_000.0] * 3,
            other_operating_income=[8_000.0] * 3,
            other_operating_expense=[6_000.0] * 3,
            net_pnl_trading_book=[10_000.0] * 3,
            net_pnl_banking_book=three,
            annual_operational_losses=[3_200.0, 4_100.0, 3_500.0],
        )
    )
    assert r.ilm == 1.0
    assert r.rwa == pytest.approx(12.5 * r.bic)


def test_op_risk_requires_losses() -> None:
    """§ __.150(c)(1)(ii) adds operational losses back into the noninterest component."""
    three = [1.0, 1.0, 1.0]
    with pytest.raises(ValueError, match="operational_losses"):
        US.operational_risk(
            OpRiskInputs(
                interest_income=three,
                interest_expense=three,
                interest_earning_assets=[100.0] * 3,
                dividend_income=three,
                fee_income=three,
                fee_expense=three,
                other_operating_income=three,
                other_operating_expense=three,
                net_pnl_trading_book=three,
                net_pnl_banking_book=three,
            )
        )
