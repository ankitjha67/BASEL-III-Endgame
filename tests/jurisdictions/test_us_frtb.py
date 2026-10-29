"""Tests for the US market-risk adapter (ERBA NPR Subpart F)."""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import RatingBucket
from src.jurisdictions.frtb_base import (
    CommodityGroup,
    CreditSector,
    DRCPositionInput,
    DRCSeniority,
    EquitySector,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    MarketRiskCalculator,
    RRAOCategory,
    RRAOPositionInput,
)
from src.jurisdictions.us.frtb import USMarketRisk

M = USMarketRisk()


def _s(rc: FRTBRiskClass, **kw: object) -> FRTBSensitivity:
    return FRTBSensitivity(risk_class=rc, measure=FRTBMeasure.DELTA, **kw)


def test_protocol() -> None:
    assert isinstance(M, MarketRiskCalculator)


@pytest.mark.parametrize(
    "sector,ig,rating,bucket",
    [
        (CreditSector.SOVEREIGN, True, RatingBucket.UNRATED, "1"),
        (CreditSector.CONSUMER, True, RatingBucket.UNRATED, "5"),
        (CreditSector.SOVEREIGN, False, RatingBucket.BB_PLUS_TO_BB_MINUS, "9"),
        (CreditSector.SOVEREIGN, False, RatingBucket.BELOW_B_MINUS, "17"),
        (CreditSector.CONSUMER, False, RatingBucket.B_PLUS_TO_B_MINUS, "13"),
        (CreditSector.OTHER, False, RatingBucket.UNRATED, "18"),
        (CreditSector.INDEX, True, RatingBucket.UNRATED, "19"),
    ],
)
def test_csr_buckets_table3(
    sector: CreditSector, ig: bool, rating: RatingBucket, bucket: str
) -> None:
    s = _s(
        FRTBRiskClass.CSR_NONSEC,
        credit_sector=sector,
        is_investment_grade=ig,
        rating=rating,
        tenor_years=5.0,
        issuer="X",
        value=1.0,
    )
    assert M.assign_bucket(s) == bucket


@pytest.mark.parametrize(
    "large,adv,sector,index,bucket",
    [
        (True, False, EquitySector.CONSUMER_HEALTH_UTILITIES, False, "1"),
        (True, True, EquitySector.FINANCIALS_REALESTATE_TECH, False, "8"),
        (False, False, EquitySector.MATERIALS_ENERGY, False, "9"),
        (False, True, EquitySector.MATERIALS_ENERGY, False, "10"),
        (True, True, EquitySector.OTHER, False, "11"),
        (True, True, None, True, "12"),
        (False, True, None, True, "13"),
    ],
)
def test_equity_buckets_table8(
    large: bool, adv: bool, sector: EquitySector | None, index: bool, bucket: str
) -> None:
    s = _s(
        FRTBRiskClass.EQUITY,
        is_large_cap=large,
        is_advanced_economy=adv,
        equity_sector=sector,
        is_equity_index=index,
        issuer="E",
        value=1.0,
    )
    assert M.assign_bucket(s) == bucket


def test_delta_risk_weights() -> None:
    """Table 1 (USD 5y 1.1%/sqrt 2), Table 3 (bucket 5 3%), Table 8 (bucket 7 40%),
    Table 9 (gold 20%), FX 15%/sqrt 2 for USD/EUR."""
    res = M.sbm_capital(
        [
            _s(FRTBRiskClass.GIRR, currency="USD", tenor_years=5.0, value=1000.0),
            _s(
                FRTBRiskClass.CSR_NONSEC,
                issuer="A",
                credit_sector=CreditSector.CONSUMER,
                is_investment_grade=True,
                tenor_years=5.0,
                value=500.0,
            ),
            _s(
                FRTBRiskClass.EQUITY,
                issuer="E",
                is_large_cap=True,
                is_advanced_economy=True,
                equity_sector=EquitySector.MATERIALS_ENERGY,
                value=100.0,
            ),
            _s(
                FRTBRiskClass.COMMODITY,
                commodity_group=CommodityGroup.PRECIOUS_METALS,
                commodity_name="GOLD",
                value=100.0,
            ),
            _s(FRTBRiskClass.FX, fx_currency="EUR", value=100.0),
        ]
    )
    by = {r.risk_class: r.total for r in res}
    assert by[FRTBRiskClass.GIRR] == pytest.approx(1000 * 0.011 / math.sqrt(2))
    assert by[FRTBRiskClass.CSR_NONSEC] == pytest.approx(15.0)
    assert by[FRTBRiskClass.EQUITY] == pytest.approx(40.0)
    assert by[FRTBRiskClass.COMMODITY] == pytest.approx(20.0)
    assert by[FRTBRiskClass.FX] == pytest.approx(15.0 / math.sqrt(2))


def test_drc_ig_corporate() -> None:
    """§ __.210 Table 1 corporate IG 4.1% x senior LGD 75%."""
    d = M.drc_capital(
        [
            DRCPositionInput(
                position_id="d",
                obligor="A",
                is_long=True,
                notional=100.0,
                market_value=100.0,
                is_investment_grade=True,
                seniority=DRCSeniority.SENIOR,
            )
        ]
    )
    assert d["nonsec"] == pytest.approx(100 * 0.75 * 0.041)


def test_rrao() -> None:
    r = M.rrao_capital(
        [
            RRAOPositionInput(position_id="a", gross_notional=1000.0, category=RRAOCategory.EXOTIC),
            RRAOPositionInput(
                position_id="b", gross_notional=1000.0, category=RRAOCategory.OTHER_RESIDUAL
            ),
        ]
    )
    assert r == pytest.approx(10.0 + 1.0)


def test_non_vertex_tenor_rejected() -> None:
    with pytest.raises(ValueError):
        M.sbm_capital([_s(FRTBRiskClass.GIRR, currency="USD", tenor_years=7.0, value=1.0)])


def test_ima_parameters() -> None:
    p = M.ima_parameters()
    assert (
        p.es_confidence == 0.975
        and p.backtesting_addons[5] == 1.70
        and p.backtesting_addons[10] == 2.0
    )
    assert p.pla_ks_thresholds == (0.09, 0.12)
