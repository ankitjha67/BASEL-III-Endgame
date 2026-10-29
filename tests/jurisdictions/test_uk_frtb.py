"""Tests for the UK PRA market-risk (FRTB) package (PS1/26 Appendix 1, Annexes G-J).

Every transcribed table cell is asserted (parametrised); hand-worked examples cover single- and
two-bucket delta aggregation, the alternative S_b, vega, curvature (psi, tie rule, 'other'
buckets, FX 1.5 divisor), scenario selection, DRC netting / seniority / maturity scaling /
buckets / securitisations / ACTP, RRAO exemptions and the simplified standardised approach.
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.frtb_base import (
    CommodityGroup,
    CreditSector,
    DRCKind,
    DRCPositionInput,
    DRCSeniority,
    EquityRiskFactor,
    EquitySector,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    GIRRCurve,
    MarketRiskCalculator,
    RRAOCategory,
    RRAOPositionInput,
    SecAssetClass,
    SecTrancheClass,
)
from src.jurisdictions.uk.frtb import UKMarketRisk, drc, rrao, sbm, ssa
from src.jurisdictions.uk.frtb import buckets as bk
from src.jurisdictions.uk.frtb import params as p

R = UKMarketRisk()
S2 = math.sqrt(2.0)
GIRR, CSR, CTP, SEC = (
    FRTBRiskClass.GIRR,
    FRTBRiskClass.CSR_NONSEC,
    FRTBRiskClass.CSR_SEC_CTP,
    FRTBRiskClass.CSR_SEC_NONCTP,
)
EQ, COM, FX = FRTBRiskClass.EQUITY, FRTBRiskClass.COMMODITY, FRTBRiskClass.FX
D, V, C = FRTBMeasure.DELTA, FRTBMeasure.VEGA, FRTBMeasure.CURVATURE


def sens(rc: FRTBRiskClass, measure: FRTBMeasure = D, value: float = 0.0, **kw: object) -> (
    FRTBSensitivity
):
    """Build a sensitivity."""
    return FRTBSensitivity(risk_class=rc, measure=measure, value=value, **kw)


def drc_pos(
    pid: str,
    obligor: str,
    is_long: bool,
    notional: float,
    mv: float,
    **kw: object,
) -> DRCPositionInput:
    """Build a DRC position."""
    return DRCPositionInput(
        position_id=pid, obligor=obligor, is_long=is_long, notional=notional, market_value=mv, **kw
    )


def class_row(rows: list, rc: FRTBRiskClass):  # type: ignore[no-untyped-def,type-arg]
    """Row of a risk class."""
    return next(r for r in rows if r.risk_class is rc)


# =========================================================================
#  Protocol conformance
# =========================================================================


def test_protocol_conformance() -> None:
    assert isinstance(R, MarketRiskCalculator)
    assert R.jurisdiction is Jurisdiction.UK
    assert "PS1/26" in R.legal_basis


def test_empty_portfolio() -> None:
    res = R.market_risk([], [], [])
    assert res.total_capital == 0.0 and res.rwa == 0.0 and res.sbm_by_class == []


# =========================================================================
#  Table cells -- GIRR (Art 325ae Table 3, 325af, 325ag)
# =========================================================================


@pytest.mark.parametrize(
    ("vertex", "rw"),
    [(0.25, 0.017), (0.5, 0.017), (1.0, 0.016), (2.0, 0.013), (3.0, 0.012), (5.0, 0.011),
     (10.0, 0.011), (15.0, 0.011), (20.0, 0.011), (30.0, 0.011)],
)
def test_girr_table_3(vertex: float, rw: float) -> None:
    assert p.GIRR_RW[vertex] == rw
    s = sens(GIRR, currency="PLN", tenor_years=vertex)
    assert bk.girr_delta_rw(s, vertex) == pytest.approx(rw)
    s_usd = sens(GIRR, currency="USD", tenor_years=vertex)
    assert bk.girr_delta_rw(s_usd, vertex) == pytest.approx(rw / S2)


def test_girr_scalars() -> None:
    assert p.GIRR_VERTICES == (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)
    assert p.GIRR_INFLATION_XCCY_RW == 0.016
    assert p.GIRR_THETA == 0.03 and p.GIRR_TENOR_CORR_FLOOR == 0.40
    assert p.GIRR_DIFFERENT_CURVE_CORR == 0.999 and p.GIRR_INFLATION_CORR == 0.40
    assert p.GIRR_XCCY_CORR == 0.0 and p.GIRR_INFLATION_INFLATION_CORR == 0.999
    assert p.GIRR_GAMMA == 0.50


@pytest.mark.parametrize("ccy", ["AUD", "CAD", "EUR", "GBP", "JPY", "SEK", "USD"])
def test_girr_most_liquid(ccy: str) -> None:
    assert bk.girr_is_most_liquid(ccy)


@pytest.mark.parametrize("ccy", ["CHF", "NOK", "PLN", "INR"])
def test_girr_not_liquid_unless_domestic(ccy: str) -> None:
    assert not bk.girr_is_most_liquid(ccy)
    assert bk.girr_is_most_liquid(ccy, domestic_currency=ccy)


def test_girr_inflation_rw_liquid() -> None:
    s = sens(GIRR, currency="GBP", girr_curve=GIRRCurve.INFLATION)
    assert bk.girr_delta_rw(s, None) == pytest.approx(0.016 / S2)


# =========================================================================
#  Table cells -- CSR (Tables 4-7, Table 5 gammas)
# =========================================================================

TABLE_4 = {"1": 0.005, "2": 0.01, "3": 0.05, "4": 0.03, "5": 0.03, "6": 0.02, "7": 0.015,
           "8": 0.025, "9": 0.02, "10": 0.04, "11": 0.12, "12": 0.07, "13": 0.085, "14": 0.055,
           "15": 0.05, "16": 0.12, "17": 0.015, "18": 0.05}


@pytest.mark.parametrize(("bucket", "rw"), sorted(TABLE_4.items()))
def test_csr_table_4(bucket: str, rw: float) -> None:
    assert p.CSR_NONSEC_RW[bucket] == rw


def test_csr_covered_bond_aa() -> None:
    assert p.CSR_NONSEC_COVERED_AA_RW == 0.015
    aa = sens(CSR, credit_sector=CreditSector.COVERED_BOND, rating=RatingBucket.AAA_TO_AA_MINUS)
    a = sens(CSR, credit_sector=CreditSector.COVERED_BOND, rating=RatingBucket.A_PLUS_TO_A_MINUS)
    assert bk.csr_nonsec_bucket(aa) == "8" and bk.csr_nonsec_rw(aa, "8") == 0.015
    assert bk.csr_nonsec_rw(a, "8") == 0.025


TABLE_6 = {"1": 0.04, "2": 0.04, "3": 0.08, "4": 0.05, "5": 0.04, "6": 0.03, "7": 0.02,
           "8": 0.06, "9": 0.13, "10": 0.13, "11": 0.16, "12": 0.10, "13": 0.12, "14": 0.12,
           "15": 0.12, "16": 0.13}


@pytest.mark.parametrize(("bucket", "rw"), sorted(TABLE_6.items()))
def test_csr_ctp_table_6(bucket: str, rw: float) -> None:
    assert p.CSR_CTP_RW[bucket] == rw


TABLE_7 = {"1": 0.009, "2": 0.015, "3": 0.02, "4": 0.02, "5": 0.008, "6": 0.012, "7": 0.012,
           "8": 0.014, "9": 0.01125, "10": 0.01875, "11": 0.025, "12": 0.025, "13": 0.01,
           "14": 0.015, "15": 0.015, "16": 0.0175, "17": 0.01575, "18": 0.02625, "19": 0.035,
           "20": 0.035, "21": 0.014, "22": 0.021, "23": 0.021, "24": 0.0245, "25": 0.035}


@pytest.mark.parametrize(("bucket", "rw"), sorted(TABLE_7.items()))
def test_csr_sec_table_7(bucket: str, rw: float) -> None:
    assert p.CSR_SEC_NONCTP_RW[bucket] == rw


TABLE_5 = [
    ("1/9", "2/10", 0.75), ("1/9", "3/11", 0.10), ("1/9", "4/12", 0.20), ("1/9", "5/13", 0.25),
    ("1/9", "6/14", 0.20), ("1/9", "7/15", 0.15), ("1/9", "8", 0.10), ("1/9", "16", 0.0),
    ("1/9", "17", 0.45), ("1/9", "18", 0.45),
    ("2/10", "3/11", 0.05), ("2/10", "4/12", 0.15), ("2/10", "5/13", 0.20),
    ("2/10", "6/14", 0.15), ("2/10", "7/15", 0.10), ("2/10", "8", 0.10), ("2/10", "16", 0.0),
    ("2/10", "17", 0.45), ("2/10", "18", 0.45),
    ("3/11", "4/12", 0.05), ("3/11", "5/13", 0.15), ("3/11", "6/14", 0.20),
    ("3/11", "7/15", 0.05), ("3/11", "8", 0.20), ("3/11", "16", 0.0), ("3/11", "17", 0.45),
    ("3/11", "18", 0.45),
    ("4/12", "5/13", 0.20), ("4/12", "6/14", 0.25), ("4/12", "7/15", 0.05), ("4/12", "8", 0.05),
    ("4/12", "16", 0.0), ("4/12", "17", 0.45), ("4/12", "18", 0.45),
    ("5/13", "6/14", 0.25), ("5/13", "7/15", 0.05), ("5/13", "8", 0.15), ("5/13", "16", 0.0),
    ("5/13", "17", 0.45), ("5/13", "18", 0.45),
    ("6/14", "7/15", 0.05), ("6/14", "8", 0.20), ("6/14", "16", 0.0), ("6/14", "17", 0.45),
    ("6/14", "18", 0.45),
    ("7/15", "8", 0.05), ("7/15", "16", 0.0), ("7/15", "17", 0.45), ("7/15", "18", 0.45),
    ("8", "16", 0.0), ("8", "17", 0.45), ("8", "18", 0.45),
    ("16", "17", 0.0), ("16", "18", 0.0), ("17", "18", 0.75),
]


@pytest.mark.parametrize(("a", "b", "g"), TABLE_5)
def test_csr_table_5(a: str, b: str, g: float) -> None:
    assert p.CSR_SECTOR_GAMMA[(a, b)] == g
    assert p.CSR_SECTOR_GAMMA[(b, a)] == g


def test_csr_correlation_scalars() -> None:
    assert p.CSR_NAME_CORR_SECTOR == 0.35 and p.CSR_NAME_CORR_INDEX == 0.80
    assert p.CSR_TENOR_CORR == 0.65 and p.CSR_BASIS_CORR == 0.999
    assert p.CSR_RATING_GAMMA == 0.50 and p.CSR_CTP_BASIS_CORR == 0.99
    assert p.CSR_SEC_TRANCHE_CORR == 0.40 and p.CSR_SEC_TENOR_CORR == 0.80
    assert p.CSR_SEC_BASIS_CORR == 0.999 and p.CSR_SEC_GAMMA == 0.0
    assert p.CSR_VERTICES == (0.5, 1.0, 3.0, 5.0, 10.0)


@pytest.mark.parametrize(
    ("b", "c", "expected"),
    [("1", "9", 0.5), ("3", "12", 0.05 * 0.5), ("3", "4", 0.05), ("17", "18", 0.75 * 0.5),
     ("8", "17", 0.45), ("8", "18", 0.45 * 0.5), ("16", "3", 0.0), ("2", "10", 0.5)],
)
def test_csr_gamma(b: str, c: str, expected: float) -> None:
    assert sbm.gamma(CSR, b, c) == pytest.approx(expected)


# =========================================================================
#  Table cells -- equity, commodity, FX, vega
# =========================================================================

TABLE_8 = {"1": (0.55, 0.0055), "2": (0.60, 0.0060), "3": (0.45, 0.0045), "4": (0.55, 0.0055),
           "5": (0.30, 0.0030), "6": (0.35, 0.0035), "7": (0.40, 0.0040), "8": (0.50, 0.0050),
           "9": (0.70, 0.0070), "10": (0.50, 0.0050), "11": (0.70, 0.0070),
           "12": (0.15, 0.0015), "13": (0.25, 0.0025)}


@pytest.mark.parametrize(("bucket", "rws"), sorted(TABLE_8.items()))
def test_equity_table_8(bucket: str, rws: tuple[float, float]) -> None:
    assert p.EQUITY_SPOT_RW[bucket] == rws[0]
    assert p.EQUITY_REPO_RW[bucket] == pytest.approx(rws[1])


@pytest.mark.parametrize(
    ("bucket", "rho"),
    [("1", 0.15), ("2", 0.15), ("3", 0.15), ("4", 0.15), ("5", 0.25), ("6", 0.25), ("7", 0.25),
     ("8", 0.25), ("9", 0.075), ("10", 0.125), ("12", 0.80), ("13", 0.80)],
)
def test_equity_correlations(bucket: str, rho: float) -> None:
    assert p.EQUITY_CORR[bucket] == rho


@pytest.mark.parametrize(
    ("b", "c", "g"),
    [("1", "10", 0.15), ("5", "11", 0.0), ("11", "12", 0.0), ("12", "13", 0.75), ("1", "12", 0.45),
     ("13", "8", 0.45)],
)
def test_equity_gamma(b: str, c: str, g: float) -> None:
    assert sbm.gamma(EQ, b, c) == g


TABLE_9_10 = {"1": (0.30, 0.55), "2": (0.35, 0.95), "3a": (0.60, 0.40), "3b": (0.60, 0.40),
              "4": (0.80, 0.80), "5": (0.40, 0.60), "6": (0.45, 0.65), "7": (0.20, 0.55),
              "8": (0.35, 0.45), "9": (0.25, 0.15), "10": (0.35, 0.40), "11": (0.50, 0.15)}


@pytest.mark.parametrize(("bucket", "vals"), sorted(TABLE_9_10.items()))
def test_commodity_tables_9_10(bucket: str, vals: tuple[float, float]) -> None:
    assert p.COMMODITY_RW[bucket] == vals[0]
    assert p.COMMODITY_CORR[bucket] == vals[1]


def test_commodity_scalars_and_gamma() -> None:
    assert p.COMMODITY_TENOR_CORR == 0.99 and p.COMMODITY_BASIS_CORR == 0.999
    assert sbm.gamma(COM, "3a", "3b") == 0.20
    assert sbm.gamma(COM, "1", "10") == 0.20
    assert sbm.gamma(COM, "1", "11") == 0.0
    assert p.COMMODITY_VERTICES == (0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)


def test_fx_parameters() -> None:
    assert p.FX_RW == 0.15 and p.FX_GAMMA == 0.60 and sbm.gamma(FX, "USD", "EUR") == 0.60
    assert len(p.FX_MOST_LIQUID_PAIR_CURRENCIES) == 20


@pytest.mark.parametrize(
    ("rc", "bucket", "rw"),
    [(GIRR, "USD", 1.0), (CSR, "3", 1.0), (CTP, "3", 1.0), (SEC, "1", 1.0), (EQ, "5", 0.7778),
     (EQ, "12", 0.7778), (EQ, "13", 0.7778), (EQ, "9", 1.0), (EQ, "10", 1.0), (EQ, "11", 1.0),
     (COM, "1", 1.0), (FX, "USD", 1.0)],
)
def test_vega_table_11(rc: FRTBRiskClass, bucket: str, rw: float) -> None:
    assert bk.vega_rw(sens(rc, V), bucket) == rw


def test_scenario_and_misc_scalars() -> None:
    assert p.SCENARIO_HIGH_MULTIPLIER == 1.25 and p.SCENARIO_LOW_FLOOR_FACTOR == 0.75
    assert p.VEGA_ALPHA == 0.01 and p.CURVATURE_FX_SCALAR == 1.5
    assert p.RRAO_EXOTIC_RW == 0.01 and p.RRAO_OTHER_RW == 0.001
    assert p.EQUITY_LARGE_CAP_THRESHOLD_GBP_M == 1600.0
    assert p.LISTED_INDEX_MIN_CONSTITUENTS == 20 and p.LISTED_INDEX_MIN_MARKET_CAP_GBP_M == 32000


# =========================================================================
#  Table cells -- DRC and IMA
# =========================================================================


@pytest.mark.parametrize(
    ("grade", "rw"),
    [("AAA", 0.005), ("AA", 0.02), ("A", 0.03), ("BBB", 0.06), ("BB", 0.15), ("B", 0.30),
     ("CCC", 0.50), ("UNRATED", 0.15), ("DEFAULTED", 1.00)],
)
def test_drc_table_2(grade: str, rw: float) -> None:
    assert p.DRC_RW_BY_RATING[grade] == rw


@pytest.mark.parametrize(
    ("rating", "rw"),
    [(RatingBucket.AAA_TO_AA_MINUS, 0.02), (RatingBucket.A_PLUS_TO_A_MINUS, 0.03),
     (RatingBucket.BBB_PLUS_TO_BBB_MINUS, 0.06), (RatingBucket.BB_PLUS_TO_BB_MINUS, 0.15),
     (RatingBucket.B_PLUS_TO_B_MINUS, 0.30), (RatingBucket.BELOW_B_MINUS, 0.50),
     (RatingBucket.UNRATED, 0.15)],
)
def test_drc_rw_by_rating_bucket(rating: RatingBucket, rw: float) -> None:
    assert drc.default_risk_weight(drc_pos("x", "o", True, 1, 1, rating=rating)) == rw


def test_drc_rw_flags() -> None:
    aaa = drc_pos("x", "o", True, 1, 1, rating=RatingBucket.AAA_TO_AA_MINUS,
                  flags={"rating_aaa": True})
    assert drc.default_risk_weight(aaa) == 0.005
    zero = drc_pos("x", "o", True, 1, 1, rating=RatingBucket.B_PLUS_TO_B_MINUS,
                   flags={"sa_zero_risk_weight": True})
    assert drc.default_risk_weight(zero) == 0.0
    assert drc.default_risk_weight(drc_pos("x", "o", True, 1, 1, is_defaulted=True)) == 1.0


@pytest.mark.parametrize(
    ("seniority", "lgd"),
    [(DRCSeniority.NON_SENIOR, 1.0), (DRCSeniority.SENIOR, 0.75),
     (DRCSeniority.COVERED_BOND, 0.25), (DRCSeniority.EQUITY, 1.0)],
)
def test_drc_lgd(seniority: DRCSeniority, lgd: float) -> None:
    assert drc.lgd(drc_pos("x", "o", True, 1, 1, seniority=seniority)) == lgd


@pytest.mark.parametrize(
    ("n", "addon"),
    [(0, 0.0), (4, 0.0), (5, 0.20), (6, 0.26), (7, 0.33), (8, 0.38), (9, 0.42), (10, 0.50)],
)
def test_ima_backtesting_table_3(n: int, addon: float) -> None:
    assert R.ima_parameters().backtesting_addons[n] == addon


@pytest.mark.parametrize(
    ("key", "days"),
    [("IR_MOST_LIQUID_AND_DOMESTIC", 10), ("IR_OTHER_CURRENCIES", 20), ("IR_VOLATILITY", 60),
     ("IR_OTHER", 60), ("CS_SOVEREIGN_IG", 20), ("CS_SOVEREIGN_HY", 40), ("CS_CORPORATE_IG", 40),
     ("CS_CORPORATE_HY", 60), ("CS_VOLATILITY", 120), ("CS_OTHER", 120), ("EQ_LARGE_CAP", 10),
     ("EQ_SMALL_CAP", 20), ("EQ_VOL_LARGE_CAP", 20), ("EQ_VOL_SMALL_CAP", 60), ("EQ_OTHER", 60),
     ("FX_MOST_LIQUID_PAIRS", 10), ("FX_OTHER_PAIRS", 20), ("FX_VOLATILITY", 40),
     ("FX_OTHER", 40), ("COM_ENERGY_CARBON", 20), ("COM_PRECIOUS_NONFERROUS", 20),
     ("COM_OTHER_PRICES", 60), ("COM_VOL_ENERGY_CARBON", 60), ("COM_VOL_PRECIOUS_NONFERROUS", 60),
     ("COM_OTHER_VOL", 120), ("COM_OTHER", 120)],
)
def test_ima_liquidity_horizons(key: str, days: int) -> None:
    assert R.ima_parameters().liquidity_horizons_days[key] == days


def test_ima_parameters() -> None:
    ima = R.ima_parameters()
    assert ima.jurisdiction is Jurisdiction.UK
    assert ima.es_confidence == 0.975 and ima.multiplier_base == 1.5
    assert ima.imcc_rho == 0.5 and ima.ses_rho == 0.6
    assert ima.pla_spearman_thresholds == (0.80, 0.70)
    assert ima.pla_ks_thresholds == (0.09, 0.12)
    assert p.IMA_LIQUIDITY_HORIZON_TABLE_1 == {1: 10, 2: 20, 3: 40, 4: 60, 5: 120}
    assert p.IMA_DESK_BACKTEST_LIMIT_99 == 12 and p.IMA_DESK_BACKTEST_LIMIT_975 == 30
    assert p.IMA_DRC_CONFIDENCE == 0.999 and p.IMA_SES_MIN_HORIZON_DAYS == 20


# =========================================================================
#  Bucket assignment edge cases
# =========================================================================


@pytest.mark.parametrize(
    ("kw", "bucket"),
    [
        ({"credit_sector": CreditSector.SOVEREIGN, "rating": RatingBucket.BB_PLUS_TO_BB_MINUS,
          "flags": {"uk_central_government": True}}, "1"),
        ({"credit_sector": CreditSector.SOVEREIGN, "rating": RatingBucket.BB_PLUS_TO_BB_MINUS},
         "9"),
        ({"credit_sector": CreditSector.SOVEREIGN, "rating": RatingBucket.A_PLUS_TO_A_MINUS}, "1"),
        ({"credit_sector": CreditSector.FINANCIAL, "rating": RatingBucket.UNRATED}, "11"),
        ({"credit_sector": CreditSector.FINANCIAL, "rating": RatingBucket.UNRATED,
          "is_investment_grade": True}, "3"),
        ({"credit_sector": CreditSector.HEALTH_CARE, "rating": RatingBucket.BBB_PLUS_TO_BBB_MINUS},
         "7"),
        ({"credit_sector": CreditSector.COVERED_BOND, "rating": RatingBucket.BB_PLUS_TO_BB_MINUS},
         "16"),
        ({"credit_sector": CreditSector.INDEX, "rating": RatingBucket.A_PLUS_TO_A_MINUS}, "17"),
        ({"credit_sector": CreditSector.INDEX, "rating": RatingBucket.UNRATED}, "18"),
        ({"credit_sector": CreditSector.OTHER}, "16"),
        ({}, "16"),
        ({"credit_sector": CreditSector.FINANCIAL, "flags": {"gse_mbs": True}}, "2"),
        ({"credit_sector": CreditSector.OTHER, "bucket_hint": "5"}, "5"),
        ({"credit_sector": CreditSector.OTHER, "bucket_hint": "99"}, "16"),
    ],
)
def test_csr_nonsec_bucket(kw: dict, bucket: str) -> None:  # type: ignore[type-arg]
    assert R.assign_bucket(sens(CSR, **kw)) == bucket


@pytest.mark.parametrize(
    ("kw", "bucket"),
    [
        ({"credit_sector": CreditSector.CONSUMER, "rating": RatingBucket.A_PLUS_TO_A_MINUS}, "5"),
        ({"credit_sector": CreditSector.CONSUMER, "rating": RatingBucket.B_PLUS_TO_B_MINUS}, "13"),
        ({"credit_sector": CreditSector.INDEX}, "16"),
        ({"credit_sector": CreditSector.COVERED_BOND, "rating": RatingBucket.A_PLUS_TO_A_MINUS},
         "8"),
    ],
)
def test_ctp_bucket(kw: dict, bucket: str) -> None:  # type: ignore[type-arg]
    assert R.assign_bucket(sens(CTP, **kw)) == bucket


@pytest.mark.parametrize(
    ("tranche", "asset", "bucket"),
    [
        (SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_PRIME, "1"),
        (SecTrancheClass.SENIOR_IG, SecAssetClass.CLO_NON_CTP, "8"),
        (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.RMBS_PRIME, "9"),
        (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.CLO_NON_CTP, "16"),
        (SecTrancheClass.HY_NR, SecAssetClass.ABS_AUTO, "23"),
        (SecTrancheClass.HY_NR, SecAssetClass.CMBS, "20"),
        (SecTrancheClass.HY_NR, SecAssetClass.OTHER, "25"),
        (None, SecAssetClass.CMBS, "25"),
    ],
)
def test_sec_nonctp_bucket(
    tranche: SecTrancheClass | None, asset: SecAssetClass, bucket: str
) -> None:
    s = sens(SEC, sec_tranche_class=tranche, sec_asset_class=asset)
    assert R.assign_bucket(s) == bucket


@pytest.mark.parametrize(
    ("kw", "bucket"),
    [
        ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": True}, "12"),
        ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": False}, "13"),
        ({"is_equity_index": True}, "13"),
        ({"equity_sector": EquitySector.FINANCIALS_REALESTATE_TECH, "is_large_cap": True,
          "is_advanced_economy": False}, "4"),
        ({"equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES, "is_large_cap": True,
          "is_advanced_economy": True}, "5"),
        ({"equity_sector": EquitySector.MATERIALS_ENERGY, "is_large_cap": True,
          "is_advanced_economy": True}, "7"),
        ({"equity_sector": EquitySector.TELECOM_INDUSTRIALS, "is_large_cap": False,
          "is_advanced_economy": True}, "10"),
        ({"equity_sector": EquitySector.TELECOM_INDUSTRIALS, "is_large_cap": False,
          "is_advanced_economy": False}, "9"),
        ({"equity_sector": EquitySector.TELECOM_INDUSTRIALS}, "9"),
        ({"equity_sector": EquitySector.OTHER, "is_large_cap": True}, "11"),
        ({}, "11"),
    ],
)
def test_equity_bucket(kw: dict, bucket: str) -> None:  # type: ignore[type-arg]
    assert R.assign_bucket(sens(EQ, **kw)) == bucket


def test_equity_repo_rw() -> None:
    s = sens(EQ, equity_sector=EquitySector.MATERIALS_ENERGY, is_large_cap=True,
             is_advanced_economy=True, equity_risk_factor=EquityRiskFactor.REPO)
    assert bk.delta_rw(s, "7") == 0.004


@pytest.mark.parametrize(
    ("group", "flags", "bucket"),
    [
        (CommodityGroup.ENERGY_ELECTRICITY_CARBON, {}, "3a"),
        (CommodityGroup.ENERGY_ELECTRICITY_CARBON, {"carbon_trading": True}, "3b"),
        (CommodityGroup.GASEOUS_ENERGY, {}, "6"),
        (CommodityGroup.PRECIOUS_METALS, {}, "7"),
        (CommodityGroup.OTHER, {}, "11"),
        (None, {}, "11"),
    ],
)
def test_commodity_bucket(group: CommodityGroup | None, flags: dict, bucket: str) -> None:  # type: ignore[type-arg]
    assert R.assign_bucket(sens(COM, commodity_group=group, flags=flags)) == bucket


@pytest.mark.parametrize(
    ("ccy", "liquid_flag", "rw"),
    [("USD", None, 0.15 / S2), ("PLN", None, 0.15), ("TRY", None, 0.15 / S2),
     ("ZAR", None, 0.15 / S2), ("PLN", True, 0.15 / S2), ("USD", False, 0.15)],
)
def test_fx_rw(ccy: str, liquid_flag: bool | None, rw: float) -> None:
    s = sens(FX, fx_currency=ccy, fx_pair_is_liquid=liquid_flag)
    assert R.assign_bucket(s) == ccy
    assert bk.fx_rw(s) == pytest.approx(rw)


def test_fx_non_liquid_reporting_currency() -> None:
    s = sens(FX, fx_currency="USD")
    assert bk.fx_rw(s, reporting_currency="PLN") == 0.15


def test_missing_descriptors_raise() -> None:
    with pytest.raises(ValueError):
        R.assign_bucket(sens(GIRR))
    with pytest.raises(ValueError):
        R.assign_bucket(sens(FX))
    with pytest.raises(ValueError):
        R.sbm_capital([sens(CSR, value=1.0, issuer="A")])


def test_curvature_rw() -> None:
    assert bk.curvature_rw(sens(GIRR, C, currency="PLN"), "PLN") == 0.017
    assert bk.curvature_rw(sens(GIRR, C, currency="USD"), "USD") == pytest.approx(0.017 / S2)
    assert bk.curvature_rw(sens(CSR, C), "8") == 0.025
    assert bk.curvature_rw(sens(EQ, C), "5") == 0.30
    assert bk.curvature_rw(sens(FX, C, fx_currency="PLN"), "PLN") == 0.15


# =========================================================================
#  SBM hand-worked examples
# =========================================================================


def test_vertex_interpolation() -> None:
    assert sbm.allocate_to_vertices(1.5, p.GIRR_VERTICES) == [(1.0, 0.5), (2.0, 0.5)]
    assert sbm.allocate_to_vertices(0.1, p.GIRR_VERTICES) == [(0.25, 1.0)]
    assert sbm.allocate_to_vertices(40.0, p.GIRR_VERTICES) == [(30.0, 1.0)]
    assert sbm.allocate_to_vertices(5.0, p.GIRR_VERTICES) == [(5.0, 1.0)]


@pytest.mark.parametrize(
    ("rho", "scenario", "expected"),
    [(0.5, "MEDIUM", 0.5), (0.5, "HIGH", 0.625), (0.9, "HIGH", 1.0), (0.6, "LOW", 0.45),
     (0.9, "LOW", 0.8), (0.0, "LOW", 0.0), (1.0, "LOW", 1.0)],
)
def test_scenario_correlation(rho: float, scenario: str, expected: float) -> None:
    assert sbm.scenario_correlation(rho, scenario) == pytest.approx(expected)


def test_scenario_unknown() -> None:
    with pytest.raises(ValueError):
        sbm.scenario_correlation(0.5, "X")


def test_girr_single_bucket_delta() -> None:
    """USD 1y +100 and 5y -50 (most liquid: RW / sqrt(2)); rho = max(e^(-0.03*4/1), 40%)."""
    s = [sens(GIRR, value=100, currency="USD", tenor_years=1),
         sens(GIRR, value=-50, currency="USD", tenor_years=5)]
    ws1, ws2 = 100 * 0.016 / S2, -50 * 0.011 / S2
    rho = math.exp(-0.03 * 4 / 1)
    expected = math.sqrt(ws1**2 + ws2**2 + 2 * rho * ws1 * ws2)
    per = R.sbm_by_scenario(s)
    assert per["MEDIUM"][0].delta == pytest.approx(expected)
    rho_hi = min(1.25 * rho, 1.0)
    assert per["HIGH"][0].delta == pytest.approx(
        math.sqrt(ws1**2 + ws2**2 + 2 * rho_hi * ws1 * ws2)
    )
    rho_lo = max(2 * rho - 1, 0.75 * rho)
    assert per["LOW"][0].delta == pytest.approx(
        math.sqrt(ws1**2 + ws2**2 + 2 * rho_lo * ws1 * ws2)
    )
    rows = R.sbm_capital(s)
    assert rows[0].scenario == "LOW" and rows[0].total == pytest.approx(per["LOW"][0].delta)


def test_girr_tenor_floor_and_curves() -> None:
    k = sbm.Factor(GIRR, "USD", "OIS", 0.25, "RISK_FREE")
    j = sbm.Factor(GIRR, "USD", "OIS", 30.0, "RISK_FREE")
    j2 = sbm.Factor(GIRR, "USD", "LIBOR3M", 30.0, "RISK_FREE")
    k2 = sbm.Factor(GIRR, "USD", "LIBOR3M", 0.25, "RISK_FREE")
    infl = sbm.Factor(GIRR, "USD", "CPI", None, "INFLATION")
    infl2 = sbm.Factor(GIRR, "USD", "CPI2", None, "INFLATION")
    xc = sbm.Factor(GIRR, "USD", "EUR", None, "XCCY_BASIS")
    assert sbm._delta_rho(k, j) == 0.40
    assert sbm._delta_rho(k, j2) == pytest.approx(0.40 * 0.999)
    assert sbm._delta_rho(k, k2) == 0.999
    assert sbm._delta_rho(k, infl) == 0.40
    assert sbm._delta_rho(infl, infl2) == 0.999
    assert sbm._delta_rho(xc, k) == 0.0


def test_girr_two_bucket_gamma() -> None:
    """USD 1y +100 and EUR 1y +100: K_b = |WS|, gamma = 50%."""
    s = [sens(GIRR, value=100, currency="USD", tenor_years=1),
         sens(GIRR, value=100, currency="EUR", tenor_years=1)]
    ws = 100 * 0.016 / S2
    expected = math.sqrt(2 * ws**2 + 2 * 0.5 * ws * ws)
    assert R.sbm_by_scenario(s)["MEDIUM"][0].delta == pytest.approx(expected)


def test_csr_two_bucket_gamma_rating_sector() -> None:
    """Bucket 3 (IG financial) +10 WS and bucket 12 (HY basic materials) +7 WS:
    gamma = 5% (Table 5, 3/11 vs 4/12) x 50% (rating)."""
    a = sens(CSR, value=10 / 0.05, issuer="BANK", tenor_years=5,
             credit_sector=CreditSector.FINANCIAL, rating=RatingBucket.A_PLUS_TO_A_MINUS)
    b = sens(CSR, value=7 / 0.07, issuer="MINER", tenor_years=5,
             credit_sector=CreditSector.BASIC_MATERIALS, rating=RatingBucket.BB_PLUS_TO_BB_MINUS)
    expected = math.sqrt(100 + 49 + 2 * 0.025 * 70)
    assert R.sbm_by_scenario([a, b])["MEDIUM"][0].delta == pytest.approx(expected)


def test_csr_intra_bucket_name_tenor_basis() -> None:
    """Two issuers, different tenors and bond vs CDS: rho = 35% x 65% x 99.9%."""
    a = sens(CSR, value=100, issuer="A", tenor_years=1, credit_sector=CreditSector.CONSUMER,
             rating=RatingBucket.A_PLUS_TO_A_MINUS)
    b = sens(CSR, value=100, issuer="B", tenor_years=5, credit_sector=CreditSector.CONSUMER,
             rating=RatingBucket.A_PLUS_TO_A_MINUS, is_cds=True)
    ws = 100 * 0.03
    rho = 0.35 * 0.65 * 0.999
    assert R.sbm_by_scenario([a, b])["MEDIUM"][0].delta == pytest.approx(
        math.sqrt(2 * ws**2 + 2 * rho * ws**2)
    )


def test_csr_index_name_correlation() -> None:
    a = sbm.Factor(CSR, "17", "ITRAXX", 5.0, "CDS")
    b = sbm.Factor(CSR, "17", "CDX", 5.0, "CDS")
    assert sbm._delta_rho(a, b) == 0.80


def test_alternative_sb() -> None:
    """Ten IG sovereigns (bucket 1, WS +1 each) vs ten HY sovereigns (bucket 9, WS -1 each):
    K_b^2 = 10 + 90 x 0.35 = 41.5, gamma = 1 x 50%: 83 - 100 < 0 -> S_b = +/-K_b."""
    s = []
    for i in range(10):
        s.append(sens(CSR, value=1 / 0.005, issuer=f"IG{i}", tenor_years=5,
                      credit_sector=CreditSector.SOVEREIGN, rating=RatingBucket.A_PLUS_TO_A_MINUS))
        s.append(sens(CSR, value=-1 / 0.02, issuer=f"HY{i}", tenor_years=5,
                      credit_sector=CreditSector.SOVEREIGN, rating=RatingBucket.B_PLUS_TO_B_MINUS))
    k = math.sqrt(41.5)
    expected = math.sqrt(2 * k**2 - 2 * 0.5 * k * k)
    assert R.sbm_by_scenario(s)["MEDIUM"][0].delta == pytest.approx(expected)


def test_abs_sum_buckets() -> None:
    """CSR bucket 16, equity bucket 11: K_b = sum |WS| (no netting across names)."""
    c = [sens(CSR, value=100, issuer="X", tenor_years=1),
         sens(CSR, value=-100, issuer="Y", tenor_years=1)]
    assert R.sbm_by_scenario(c)["MEDIUM"][0].delta == pytest.approx(24.0)
    e = [sens(EQ, value=10, issuer="X"), sens(EQ, value=-10, issuer="Y")]
    assert R.sbm_by_scenario(e)["MEDIUM"][0].delta == pytest.approx(14.0)


def test_sec_nonctp_bucket_25_added_outside() -> None:
    """Bucket 25 (3.5%) is added linearly to the other buckets (Art 325ao(2))."""
    a = sens(SEC, value=100, tranche_id="T1", tenor_years=5,
             sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.CMBS)
    b = sens(SEC, value=100, tranche_id="T2", tenor_years=5,
             sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.ABS_AUTO)
    o = sens(SEC, value=100, tranche_id="T3", tenor_years=5)
    expected = math.sqrt(2.0**2 + 1.2**2) + 3.5
    assert R.sbm_by_scenario([a, b, o])["MEDIUM"][0].delta == pytest.approx(expected)


def test_sec_tranche_correlation() -> None:
    a = sens(SEC, value=100, tranche_id="T1", tenor_years=1,
             sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.CMBS)
    b = sens(SEC, value=100, tranche_id="T2", tenor_years=3,
             sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.CMBS)
    rho = 0.40 * 0.80
    assert R.sbm_by_scenario([a, b])["MEDIUM"][0].delta == pytest.approx(
        math.sqrt(2 * 4 + 2 * rho * 4)
    )


def test_equity_spot_repo_correlations() -> None:
    kw = {"equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES, "is_large_cap": True,
          "is_advanced_economy": True}
    a = sens(EQ, value=100, issuer="A", **kw)
    a_repo = sens(EQ, value=1000, issuer="A", equity_risk_factor=EquityRiskFactor.REPO, **kw)
    b_repo = sens(EQ, value=1000, issuer="B", equity_risk_factor=EquityRiskFactor.REPO, **kw)
    ws_s, ws_r = 30.0, 3.0
    same = R.sbm_by_scenario([a, a_repo])["MEDIUM"][0].delta
    assert same == pytest.approx(math.sqrt(ws_s**2 + ws_r**2 + 2 * 0.999 * ws_s * ws_r))
    diff = R.sbm_by_scenario([a, b_repo])["MEDIUM"][0].delta
    assert diff == pytest.approx(math.sqrt(ws_s**2 + ws_r**2 + 2 * 0.25 * 0.999 * ws_s * ws_r))


def test_commodity_intra_bucket() -> None:
    """Brent and WTI (bucket 2, rho 95%), different tenors (99%) and locations (99.9%)."""
    a = sens(COM, value=100, commodity_group=CommodityGroup.ENERGY_LIQUID,
             commodity_name="BRENT", tenor_years=1, delivery_location="UK")
    b = sens(COM, value=-50, commodity_group=CommodityGroup.ENERGY_LIQUID,
             commodity_name="WTI", tenor_years=2, delivery_location="US")
    rho = 0.95 * 0.99 * 0.999
    wa, wb = 35.0, -17.5
    assert R.sbm_by_scenario([a, b])["MEDIUM"][0].delta == pytest.approx(
        math.sqrt(wa**2 + wb**2 + 2 * rho * wa * wb)
    )


def test_commodity_3a_3b_separate_buckets() -> None:
    a = sens(COM, value=100, commodity_group=CommodityGroup.ENERGY_ELECTRICITY_CARBON,
             commodity_name="POWER")
    b = sens(COM, value=100, commodity_group=CommodityGroup.ENERGY_ELECTRICITY_CARBON,
             commodity_name="EUA", flags={"carbon_trading": True})
    assert R.sbm_by_scenario([a, b])["MEDIUM"][0].delta == pytest.approx(
        math.sqrt(2 * 60.0**2 + 2 * 0.20 * 60.0**2)
    )


def test_fx_delta_two_pairs() -> None:
    s = [sens(FX, value=100, fx_currency="USD"), sens(FX, value=-100, fx_currency="PLN")]
    a, b = 15 / S2, -15.0
    assert R.sbm_by_scenario(s)["MEDIUM"][0].delta == pytest.approx(
        math.sqrt(a**2 + b**2 + 2 * 0.6 * a * b)
    )


def test_girr_vega() -> None:
    """Two USD vega factors: option maturities 1y and 5y, underlying 1y; rho = e^(-0.01*4/1)."""
    s = [sens(GIRR, V, value=10, currency="USD", option_maturity_years=1,
              underlying_maturity_years=1),
         sens(GIRR, V, value=10, currency="USD", option_maturity_years=5,
              underlying_maturity_years=1)]
    rho = math.exp(-0.01 * 4)
    assert R.sbm_by_scenario(s)["MEDIUM"][0].vega == pytest.approx(math.sqrt(200 + 200 * rho))


def test_equity_vega() -> None:
    """Two large-cap AE names in bucket 5 at the same option maturity: rho = 25%; RW 77.78%."""
    kw = {"equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES, "is_large_cap": True,
          "is_advanced_economy": True, "option_maturity_years": 1.0}
    s = [sens(EQ, V, value=10, issuer="A", **kw), sens(EQ, V, value=10, issuer="B", **kw)]
    ws = 7.778
    assert R.sbm_by_scenario(s)["MEDIUM"][0].vega == pytest.approx(
        math.sqrt(2 * ws**2 + 2 * 0.25 * ws**2)
    )


def test_curvature_single_bucket() -> None:
    """Bucket 5 equities A (CVR+ 5, CVR- 3) and B (CVR+ -2, CVR- 4), rho^2 = 0.0625."""
    kw = {"equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES, "is_large_cap": True,
          "is_advanced_economy": True}
    s = [sens(EQ, C, issuer="A", cvr_up=5, cvr_down=3, **kw),
         sens(EQ, C, issuer="B", cvr_up=-2, cvr_down=4, **kw)]
    k_up = math.sqrt(25 + 2 * 0.0625 * 5 * -2)
    k_down = math.sqrt(9 + 16 + 2 * 0.0625 * 12)
    assert k_down > k_up
    assert R.sbm_by_scenario(s)["MEDIUM"][0].curvature == pytest.approx(k_down)


def test_curvature_psi_both_negative() -> None:
    k_b, s_b = sbm.curvature_bucket(
        {sbm.Factor(EQ, "5", "A"): (-3.0, -1.0), sbm.Factor(EQ, "5", "B"): (-4.0, -2.0)},
        lambda a, b: 0.5,
        False,
    )
    assert k_b == 0.0 and s_b == -3.0  # tie at 0: sum CVR+ (-7) < sum CVR- (-3) -> K-


def test_curvature_tie_rule() -> None:
    f = sbm.Factor(EQ, "5", "A")
    k_b, s_b = sbm.curvature_bucket({f: (4.0, 4.0)}, lambda a, b: 0.0, False)
    assert (k_b, s_b) == (4.0, 4.0)
    g = sbm.Factor(EQ, "5", "B")
    k_b, s_b = sbm.curvature_bucket({f: (4.0, 3.0), g: (-1.0, 0.0)}, lambda a, b: 0.0, False)
    # K+ = sqrt(16) = 4 > K- = sqrt(9) = 3 -> K+, S_b = sum CVR+ = 3
    assert (k_b, s_b) == (4.0, 3.0)


def test_curvature_two_buckets_gamma_squared_and_psi() -> None:
    kw5 = {"equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES, "is_large_cap": True,
           "is_advanced_economy": True}
    kw6 = {"equity_sector": EquitySector.TELECOM_INDUSTRIALS, "is_large_cap": True,
           "is_advanced_economy": True}
    pos = [sens(EQ, C, issuer="A", cvr_up=5, cvr_down=1, **kw5),
           sens(EQ, C, issuer="B", cvr_up=4, cvr_down=2, **kw6)]
    expected = math.sqrt(25 + 16 + 2 * 0.15**2 * 5 * 4)
    assert R.sbm_by_scenario(pos)["MEDIUM"][0].curvature == pytest.approx(expected)
    neg = [sens(EQ, C, issuer="A", cvr_up=-5, cvr_down=-6, **kw5),
           sens(EQ, C, issuer="B", cvr_up=-4, cvr_down=-7, **kw6)]
    assert R.sbm_by_scenario(neg)["MEDIUM"][0].curvature == 0.0


def test_curvature_other_bucket() -> None:
    s = [sens(EQ, C, issuer="A", cvr_up=5, cvr_down=-1),
         sens(EQ, C, issuer="B", cvr_up=-2, cvr_down=4)]
    assert R.sbm_by_scenario(s)["MEDIUM"][0].curvature == pytest.approx(5.0)


def test_curvature_no_inflation_or_repo() -> None:
    s = [sens(GIRR, C, currency="USD", girr_curve=GIRRCurve.INFLATION, cvr_up=5, cvr_down=5),
         sens(EQ, C, issuer="A", equity_risk_factor=EquityRiskFactor.REPO, cvr_up=5, cvr_down=5)]
    assert R.sbm_capital(s) == []


def test_fx_curvature_divisor() -> None:
    s = [sens(FX, C, fx_currency="USD", cvr_up=3, cvr_down=1.5,
              flags={"fx_curvature_div_1_5": True})]
    assert R.sbm_by_scenario(s)["MEDIUM"][0].curvature == pytest.approx(2.0)
    plain = [sens(FX, C, fx_currency="USD", cvr_up=3, cvr_down=1.5)]
    assert R.sbm_by_scenario(plain)["MEDIUM"][0].curvature == pytest.approx(3.0)
    perm = UKMarketRisk(fx_curvature_permission=True)
    assert perm.sbm_by_scenario(plain)["MEDIUM"][0].curvature == pytest.approx(2.0)


def test_curvature_gamma_from_csr() -> None:
    a = sens(CSR, C, issuer="A", credit_sector=CreditSector.FINANCIAL,
             rating=RatingBucket.A_PLUS_TO_A_MINUS, cvr_up=3, cvr_down=1)
    b = sens(CSR, C, issuer="B", credit_sector=CreditSector.FINANCIAL,
             rating=RatingBucket.A_PLUS_TO_A_MINUS, cvr_up=4, cvr_down=1)
    expected = math.sqrt(9 + 16 + 2 * 0.35**2 * 12)
    assert R.sbm_by_scenario([a, b])["MEDIUM"][0].curvature == pytest.approx(expected)


def test_scenario_selection_on_total() -> None:
    """The binding scenario maximises the total across classes; every class row reports it."""
    s = [sens(GIRR, value=100, currency="USD", tenor_years=1),
         sens(GIRR, value=-50, currency="USD", tenor_years=5),
         sens(FX, value=100, fx_currency="USD"), sens(FX, value=100, fx_currency="PLN")]
    per = R.sbm_by_scenario(s)
    totals = {sc: sum(r.total for r in rows) for sc, rows in per.items()}
    rows = R.sbm_capital(s)
    best = max(totals, key=lambda k: totals[k])
    assert {r.scenario for r in rows} == {best}
    assert sum(r.total for r in rows) == pytest.approx(totals[best])
    # FX alone prefers HIGH (positive correlation), GIRR alone prefers LOW
    assert class_row(per["HIGH"], FX).total > class_row(per["LOW"], FX).total
    assert class_row(per["LOW"], GIRR).total > class_row(per["HIGH"], GIRR).total


def test_market_risk_total_and_rwa() -> None:
    s = [sens(FX, value=100, fx_currency="PLN")]
    d = [drc_pos("b", "X", True, 100, 100, rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS)]
    q = [RRAOPositionInput(position_id="r", gross_notional=1000, category=RRAOCategory.EXOTIC)]
    res = R.market_risk(s, d, q)
    assert res.sbm_total == pytest.approx(15.0)
    assert res.drc_total == pytest.approx(75 * 0.06)
    assert res.rrao == pytest.approx(10.0)
    assert res.total_capital == pytest.approx(15 + 4.5 + 10)
    assert res.rwa == pytest.approx(12.5 * res.total_capital)
    assert res.binding_scenario in p.SCENARIOS


# =========================================================================
#  DRC
# =========================================================================


def test_gross_jtd() -> None:
    assert drc.gross_jtd(drc_pos("a", "X", True, 100, 90)) == pytest.approx(65.0)
    assert drc.gross_jtd(drc_pos("a", "X", False, 100, 90)) == pytest.approx(-65.0)
    assert drc.gross_jtd(drc_pos("a", "X", True, 100, 100,
                                 seniority=DRCSeniority.COVERED_BOND)) == pytest.approx(25.0)
    assert drc.gross_jtd(drc_pos("a", "X", True, 100, 100,
                                 seniority=DRCSeniority.NON_SENIOR)) == pytest.approx(100.0)
    assert drc.gross_jtd(drc_pos("a", "X", True, 0, 50,
                                 seniority=DRCSeniority.EQUITY)) == pytest.approx(50.0)
    # a deeply discounted long bond cannot produce a negative long JTD
    assert drc.gross_jtd(drc_pos("a", "X", True, 100, 10)) == 0.0
    assert drc.gross_jtd(drc_pos("a", "X", True, 100, 90,
                                 flags={"unwind_without_default_exposure": True})) == 0.0
    assert drc.gross_jtd(drc_pos("a", "X", True, 100, 90, is_defaulted=True,
                                 flags={"default_reflected_in_value": True})) == 0.0


@pytest.mark.parametrize(("m", "f"), [(0.0, 0.25), (0.1, 0.25), (0.5, 0.5), (1.0, 1.0), (5.0, 1.0)])
def test_maturity_factor(m: float, f: float) -> None:
    assert drc.maturity_factor(m) == f


def test_drc_netting_example() -> None:
    """Long senior bond JTD 75 (2y) vs short senior CDS JTD 45 (6m -> 22.5): net 52.5 x 6%."""
    pos = [drc_pos("b", "X", True, 100, 100, maturity_years=2,
                   rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS),
           drc_pos("c", "X", False, 60, 60, maturity_years=0.5,
                   rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS)]
    nets = drc.nonsec_net_jtds(pos)
    assert [n.amount for n in nets] == [pytest.approx(52.5)]
    assert R.drc_capital(pos)["nonsec"] == pytest.approx(52.5 * 0.06)


def test_drc_seniority_restriction() -> None:
    """A senior short cannot offset an equity long; WtS applies within the bucket."""
    pos = [drc_pos("e", "X", True, 0, 50, seniority=DRCSeniority.EQUITY,
                   rating=RatingBucket.A_PLUS_TO_A_MINUS),
           drc_pos("s", "X", False, 100, 100, rating=RatingBucket.A_PLUS_TO_A_MINUS)]
    nets = sorted(n.amount for n in drc.nonsec_net_jtds(pos))
    assert nets == [pytest.approx(-75.0), pytest.approx(50.0)]
    wts = 50 / 125
    assert R.drc_capital(pos)["nonsec"] == pytest.approx(max(50 * 0.03 - wts * 75 * 0.03, 0.0))


def test_drc_junior_short_offsets_senior_long() -> None:
    pos = [drc_pos("s", "X", True, 100, 100, rating=RatingBucket.A_PLUS_TO_A_MINUS),
           drc_pos("e", "X", False, 0, 50, seniority=DRCSeniority.EQUITY,
                   rating=RatingBucket.A_PLUS_TO_A_MINUS)]
    assert [n.amount for n in drc.nonsec_net_jtds(pos)] == [pytest.approx(25.0)]


def test_drc_buckets_and_hbr() -> None:
    pos = [drc_pos("a", "A", True, 100, 100, rating=RatingBucket.BB_PLUS_TO_BB_MINUS),
           drc_pos("b", "B", False, 100, 100, rating=RatingBucket.A_PLUS_TO_A_MINUS),
           drc_pos("c", "S", True, 100, 100, credit_sector=CreditSector.SOVEREIGN,
                   rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS),
           drc_pos("d", "L", True, 100, 100, credit_sector=CreditSector.LOCAL_GOVERNMENT,
                   rating=RatingBucket.UNRATED)]
    by = drc.drc_nonsec_by_bucket(pos)
    assert by["corporates"] == pytest.approx(75 * 0.15 - 0.5 * 75 * 0.03)
    assert by["sovereigns"] == pytest.approx(75 * 0.06)
    assert by["local governments/municipalities"] == pytest.approx(75 * 0.15)
    assert drc.drc_nonsec(pos) == pytest.approx(sum(by.values()))
    assert drc.hedge_benefit_ratio(0.0, 0.0) == 0.0


def test_drc_bucket_floor() -> None:
    pos = [drc_pos("a", "A", True, 100, 100, rating=RatingBucket.A_PLUS_TO_A_MINUS),
           drc_pos("b", "B", False, 1000, 1000, rating=RatingBucket.B_PLUS_TO_B_MINUS)]
    assert R.drc_capital(pos)["nonsec"] == 0.0


def test_drc_sec_nonctp() -> None:
    """RW = 8% x banking-book RW; netting within the same pool and tranche only."""
    base = {"kind": DRCKind.SEC_NON_CTP, "sec_asset_class": SecAssetClass.RMBS_PRIME,
            "region": "Europe", "banking_book_risk_weight": 0.5}
    pos = [drc_pos("a", "P", True, 100, 80, pool_id="P1", tranche_id="A", **base),
           drc_pos("b", "P", False, 100, 30, pool_id="P1", tranche_id="A", **base),
           drc_pos("c", "P", False, 100, 20, pool_id="P2", tranche_id="A", **base)]
    by = drc.drc_sec_nonctp_by_bucket(pos)
    key = "residential mortgage-backed securities | Europe"
    assert set(by) == {key}
    wts = 50 / 70
    assert by[key] == pytest.approx(50 * 0.04 - wts * 20 * 0.04)
    assert R.drc_capital(pos)["sec_nonctp"] == pytest.approx(by[key])


def test_drc_sec_buckets() -> None:
    def b(**kw: object) -> str:
        return drc.sec_bucket(drc_pos("x", "o", True, 1, 1, kind=DRCKind.SEC_NON_CTP, **kw))

    assert b(flags={"sec_corporate_bucket": True}) == "corporates"
    assert b(sec_asset_class=SecAssetClass.CLO_NON_CTP, region="Asia") == (
        "collateralised loan obligations | Asia")
    assert b(flags={"abcp": True}, region="North America") == (
        "asset-backed commercial paper | North America")
    assert b(sec_asset_class=SecAssetClass.OTHER, flags={"other_retail": True}) == (
        "other retail | rest of the world")
    assert b(sec_asset_class=SecAssetClass.OTHER) == "other wholesale | rest of the world"


def test_drc_sec_default_rw_and_cap() -> None:
    p_ = drc_pos("a", "P", True, 100, 100, kind=DRCKind.SEC_NON_CTP)
    assert drc.sec_risk_weight(p_) == pytest.approx(1.0)
    capped = drc_pos("a", "P", True, 100, 10, kind=DRCKind.SEC_NON_CTP,
                     banking_book_risk_weight=15.0, flags={"cash_securitisation": True})
    assert drc.drc_sec_nonctp([capped]) == pytest.approx(10.0)
    one_year = drc_pos("a", "P", True, 100, 10, kind=DRCKind.SEC_NON_CTP, maturity_years=0.25,
                       banking_book_risk_weight=1.0, flags={"rw_art_259_263": True})
    assert drc.drc_sec_nonctp([one_year]) == pytest.approx(0.8)


def test_drc_ctp() -> None:
    """Index bucket A long 100 (8% x 100% RW), index B short 100; WtS over the whole ACTP."""
    pos = [drc_pos("a", "N", True, 100, 100, kind=DRCKind.CTP, pool_id="IDX_A",
                   banking_book_risk_weight=1.0),
           drc_pos("b", "N", False, 100, 100, kind=DRCKind.CTP, pool_id="IDX_B",
                   banking_book_risk_weight=2.0),
           drc_pos("c", "N", True, 100, 50, kind=DRCKind.CTP, pool_id="IDX_B",
                   rating=RatingBucket.A_PLUS_TO_A_MINUS, tranche_id="untranched")]
    wts = 150 / 250
    a = 100 * 0.08
    b = 50 * 0.03 - wts * 100 * 0.16
    floored = drc.drc_ctp_by_bucket(pos)
    assert floored["IDX_A"] == pytest.approx(a) and floored["IDX_B"] == 0.0
    assert R.drc_capital(pos)["ctp"] == pytest.approx(a)
    unfloored = UKMarketRisk(ctp_bucket_floor=False)
    assert unfloored.drc_capital(pos)["ctp"] == pytest.approx(max(a + 0.5 * b, 0.0))
    total = R.drc_capital(pos)
    assert total["total"] == pytest.approx(total["nonsec"] + total["sec_nonctp"] + total["ctp"])


# =========================================================================
#  RRAO
# =========================================================================


@pytest.mark.parametrize(
    ("category", "flags", "exempt", "expected"),
    [
        (RRAOCategory.EXOTIC, {}, False, 10.0),
        (RRAOCategory.OTHER_RESIDUAL, {}, False, 1.0),
        (RRAOCategory.OTHER_RESIDUAL, {"listed": True}, False, 0.0),
        (RRAOCategory.OTHER_RESIDUAL, {"ccp_eligible": True}, False, 0.0),
        (RRAOCategory.EXOTIC, {"listed": True}, False, 10.0),
        (RRAOCategory.EXOTIC, {"back_to_back": True}, False, 0.0),
        (RRAOCategory.OTHER_RESIDUAL, {}, True, 0.0),
    ],
)
def test_rrao(category: RRAOCategory, flags: dict, exempt: bool, expected: float) -> None:  # type: ignore[type-arg]
    pos = RRAOPositionInput(position_id="r", gross_notional=1000, category=category,
                            exempt=exempt, flags=flags)
    assert R.rrao_capital([pos]) == pytest.approx(expected)
    assert rrao.rrao_capital([pos, pos]) == pytest.approx(2 * expected)


# =========================================================================
#  Simplified standardised approach
# =========================================================================


@pytest.mark.parametrize(
    ("multiplier", "value"),
    [(p.SSA_MULTIPLIER_DEBT, 1.3), (p.SSA_MULTIPLIER_EQUITY, 3.5), (p.SSA_MULTIPLIER_CIU, 3.5),
     (p.SSA_MULTIPLIER_FX, 1.2), (p.SSA_MULTIPLIER_COMMODITY, 1.9)],
)
def test_ssa_multipliers(multiplier: float, value: float) -> None:
    assert multiplier == value


@pytest.mark.parametrize(
    ("rw", "m", "rate"),
    [(0.0, 5, 0.0), (0.2, 0.5, 0.0025), (0.5, 1.0, 0.01), (0.5, 2.0, 0.01), (0.2, 3.0, 0.016),
     (0.75, 1.0, 0.08), (1.0, 1.0, 0.08), (1.5, 1.0, 0.12), (None, 1.0, 0.12)],
)
def test_ssa_debt_specific_table_1(rw: float | None, m: float, rate: float) -> None:
    pos = ssa.SSADebtPosition(position_id="d", amount=100, residual_maturity_years=m,
                              sa_risk_weight=rw)
    assert ssa.debt_specific_rate(pos) == rate


def test_ssa_debt_specific_special() -> None:
    cb = ssa.SSADebtPosition(position_id="d", amount=100, residual_maturity_years=3,
                             qualifying_covered_bond=True)
    assert ssa.debt_specific_rate(cb) == pytest.approx(0.008)
    sec = ssa.SSADebtPosition(position_id="d", amount=100, residual_maturity_years=3,
                              is_securitisation=True, banking_book_risk_weight=0.2)
    assert ssa.debt_specific_rate(sec) == pytest.approx(0.016)
    capped = ssa.SSADebtPosition(position_id="d", amount=-100, residual_maturity_years=3,
                                 sa_risk_weight=1.5, max_default_loss=5.0)
    assert ssa.debt_specific_risk([capped]) == 5.0


LADDER = [
    (1, 1 / 12, 1 / 12, 0.00, None), (1, 0.25, 0.25, 0.20, 1.00), (1, 0.5, 0.5, 0.40, 1.00),
    (1, 1.0, 1.0, 0.70, 1.00), (2, 2.0, 1.9, 1.25, 0.90), (2, 3.0, 2.8, 1.75, 0.80),
    (2, 4.0, 3.6, 2.25, 0.75), (3, 5.0, 4.3, 2.75, 0.75), (3, 7.0, 5.7, 3.25, 0.70),
    (3, 10.0, 7.3, 3.75, 0.65), (3, 15.0, 9.3, 4.50, 0.60), (3, 20.0, 10.6, 5.25, 0.60),
    (3, None, 12.0, 6.00, 0.60), (3, None, 20.0, 8.00, 0.60), (3, None, None, 12.50, 0.60),
]


@pytest.mark.parametrize(("i", "row"), list(enumerate(LADDER)))
def test_ssa_ladder_table_2(i: int, row: tuple) -> None:  # type: ignore[type-arg]
    got = p.SSA_MATURITY_LADDER[i]
    assert got[0] == row[0] and got[3] == row[3] and got[4] == row[4]
    for a, b in ((got[1], row[1]), (got[2], row[2])):
        assert (a is None and b is None) or a == pytest.approx(b)


@pytest.mark.parametrize(
    ("m", "coupon", "band"),
    [(0.0, 0.05, 0), (0.5, 0.05, 2), (1.95, 0.01, 5), (1.95, 0.05, 4), (25, 0.05, 12),
     (25, 0.01, 14), (11, 0.01, 12), (15, 0.01, 13)],
)
def test_ssa_ladder_band(m: float, coupon: float, band: int) -> None:
    assert ssa.ladder_band(m, coupon) == band


def test_ssa_ladder_cross_zone_example() -> None:
    """+100 at 6m (0.40%) and -100 at 4.5y (2.75%): m13 = 0.4 at 150%, residual 2.35."""
    pos = [ssa.SSADebtPosition(position_id="a", amount=100, residual_maturity_years=0.5,
                               coupon=0.05, sa_risk_weight=0),
           ssa.SSADebtPosition(position_id="b", amount=-100, residual_maturity_years=4.5,
                               coupon=0.05, sa_risk_weight=0)]
    assert ssa.debt_general_risk(pos) == pytest.approx(1.5 * 0.4 + 2.35)


def test_ssa_ladder_band_matching() -> None:
    """+100 and -50 in the 2-3y band (1.75%): matched 0.875 at 10% + residual 0.875."""
    pos = [ssa.SSADebtPosition(position_id="a", amount=100, residual_maturity_years=2.5,
                               coupon=0.05, sa_risk_weight=0),
           ssa.SSADebtPosition(position_id="b", amount=-50, residual_maturity_years=2.5,
                               coupon=0.05, sa_risk_weight=0)]
    assert ssa.debt_general_risk(pos) == pytest.approx(0.1 * 0.875 + 0.875)


def test_ssa_zone_orders() -> None:
    unmatched = {1: 1.0, 2: -1.0, 3: 1.0}
    m12, m23, m13, res = ssa._zones_charge(dict(unmatched), reverse=False)
    assert (m12, m23, m13, res) == (1.0, 0.0, 0.0, 1.0)
    m12, m23, m13, res = ssa._zones_charge(dict(unmatched), reverse=True)
    assert (m12, m23, m13, res) == (0.0, 1.0, 0.0, 1.0)


def test_ssa_ladder_zone_matching() -> None:
    """Zone two: +1.25 (1-2y) vs -1.75 (2-3y): zone matched 1.25 at 30%, residual 0.5."""
    pos = [ssa.SSADebtPosition(position_id="a", amount=100, residual_maturity_years=1.5,
                               coupon=0.05, sa_risk_weight=0),
           ssa.SSADebtPosition(position_id="b", amount=-100, residual_maturity_years=2.5,
                               coupon=0.05, sa_risk_weight=0)]
    assert ssa.debt_general_risk(pos) == pytest.approx(0.3 * 1.25 + 0.5)


def test_ssa_duration_method() -> None:
    assert p.SSA_DURATION_ZONES == ((1, 1.0, 1.0), (2, 3.6, 0.85), (3, None, 0.7))
    pos = [ssa.SSADebtPosition(position_id="a", amount=100, residual_maturity_years=1,
                               modified_duration=0.9, sa_risk_weight=0),
           ssa.SSADebtPosition(position_id="b", amount=-100, residual_maturity_years=1,
                               modified_duration=0.5, sa_risk_weight=0)]
    # zone 1: +0.9 and -0.5 -> matched 0.5 at 2%, residual 0.4
    got = ssa.debt_general_risk(pos, ssa.GeneralRiskMethod.DURATION)
    assert got == pytest.approx(0.02 * 0.5 + 0.4)
    with pytest.raises(ValueError):
        ssa.debt_general_risk([ssa.SSADebtPosition(position_id="x", amount=1,
                                                   residual_maturity_years=1)],
                              ssa.GeneralRiskMethod.DURATION)


def test_ssa_modified_duration() -> None:
    md = ssa.modified_duration([(1.0, 5.0), (2.0, 105.0)], 0.05)
    pv1, pv2 = 5 / 1.05, 105 / 1.05**2
    assert md == pytest.approx((pv1 + 2 * pv2) / (pv1 + pv2) / 1.05)


def test_ssa_equity() -> None:
    pos = [ssa.SSAEquityPosition(position_id="1", issuer="A", market="UK", amount=100),
           ssa.SSAEquityPosition(position_id="2", issuer="B", market="UK", amount=-40),
           ssa.SSAEquityPosition(position_id="3", issuer="C", market="US", amount=50),
           ssa.SSAEquityPosition(position_id="4", issuer="SPX", market="US", amount=200,
                                 diversified_index_future=True)]
    spec, gen = ssa.equity_charges(pos)
    assert spec == pytest.approx(0.08 * 190)
    assert gen == pytest.approx(0.08 * (60 + 250))


@pytest.mark.parametrize(
    ("day", "factor"), [(None, 1.0), (0, 1.0), (1, 0.9), (2, 0.75), (3, 0.75), (4, 0.5),
                        (5, 0.25), (6, 0.0)],
)
def test_ssa_underwriting_table_4(day: int | None, factor: float) -> None:
    assert ssa.underwriting_factor(day) == factor


def test_ssa_ciu_fx_commodity() -> None:
    assert ssa.ciu_charge([ssa.SSACIUPosition(position_id="c", value=100),
                           ssa.SSACIUPosition(position_id="d", value=100, include_fx=True)]) == (
        pytest.approx(72.0))
    fx = [ssa.SSAFXPosition(currency="USD", net_position=100),
          ssa.SSAFXPosition(currency="EUR", net_position=-30),
          ssa.SSAFXPosition(currency="JPY", net_position=-50),
          ssa.SSAFXPosition(currency="XAU", net_position=10, is_gold=True),
          ssa.SSAFXPosition(currency="GBP", net_position=1000)]
    assert ssa.fx_charge(fx) == pytest.approx(0.08 * 110)
    assert ssa.fx_charge(fx, total_own_funds=10_000) == 0.0
    assert ssa.fx_charge(fx, total_own_funds=1_000) == pytest.approx(8.8)
    assert ssa.fx_charge(fx, closely_correlated_matched=50) == pytest.approx(8.8 + 2.0)


def test_ssa_commodity_methods() -> None:
    pos = [ssa.SSACommodityPosition(commodity="OIL", units=100, spot_price=1, maturity_years=0.04),
           ssa.SSACommodityPosition(commodity="OIL", units=-60, spot_price=1, maturity_years=0.04),
           ssa.SSACommodityPosition(commodity="OIL", units=-30, spot_price=1, maturity_years=2.5)]
    # band 0: matched 60 -> 2 x 60 x 1.5% = 1.8; +40 carried 5 bands, 30 matched at 0.6% each
    # band -> 0.9; residual 10 x 15% = 1.5
    assert ssa.commodity_charge(pos) == pytest.approx(1.8 + 0.9 + 1.5)
    assert ssa.commodity_charge(pos, ssa.CommodityMethod.SIMPLIFIED) == pytest.approx(
        0.15 * 10 + 0.03 * 190
    )
    gold_like = [q.model_copy(update={"category": "PRECIOUS_METALS"}) for q in pos]
    assert ssa.commodity_charge(gold_like, ssa.CommodityMethod.EXTENDED_LADDER) == pytest.approx(
        2 * 60 * 0.010 + 30 * 0.003 * 5 + 10 * 0.08
    )


@pytest.mark.parametrize(
    ("cat", "rates"),
    [("PRECIOUS_METALS", (0.010, 0.003, 0.08)), ("BASE_METALS", (0.012, 0.005, 0.10)),
     ("AGRICULTURAL", (0.015, 0.006, 0.12)), ("OTHER", (0.015, 0.006, 0.15))],
)
def test_ssa_commodity_table_2(cat: str, rates: tuple[float, float, float]) -> None:
    assert p.SSA_COMMODITY_EXTENDED[cat] == rates


def test_ssa_options_non_delta() -> None:
    opts = [ssa.SSAOptionNonDelta(position_id="s", risk_type=ssa.SSARiskType.EQUITY,
                                  gross_amount=10, rw_delta_equivalent=4),
            ssa.SSAOptionNonDelta(position_id="g1", risk_type=ssa.SSARiskType.FX,
                                  underlying_type="EURUSD", gamma=-2.0, vu=3.0),
            ssa.SSAOptionNonDelta(position_id="g2", risk_type=ssa.SSARiskType.FX,
                                  underlying_type="EURUSD", gamma=1.0, vu=2.0),
            ssa.SSAOptionNonDelta(position_id="v", risk_type=ssa.SSARiskType.FX,
                                  underlying_type="EURUSD", vega=-4.0, implied_vol=0.2)]
    out = ssa.option_non_delta(opts)
    assert out["EQUITY"] == pytest.approx(6.0)
    # gamma: 0.5*(-2)*9 + 0.5*1*4 = -7 -> 7; vega: |-4 x 25% x 0.2| = 0.2
    assert out["FX"] == pytest.approx(7.2)


def test_ssa_total_and_eligibility() -> None:
    inputs = ssa.SSAInputs(
        debt=[ssa.SSADebtPosition(position_id="a", amount=100, residual_maturity_years=0.5,
                                  coupon=0.05, sa_risk_weight=0.2)],
        equities=[ssa.SSAEquityPosition(position_id="e", issuer="A", market="UK", amount=100)],
        cius=[ssa.SSACIUPosition(position_id="c", value=10)],
        fx=[ssa.SSAFXPosition(currency="USD", net_position=100)],
        commodities=[ssa.SSACommodityPosition(commodity="OIL", units=10, spot_price=1)],
        commodity_method=ssa.CommodityMethod.SIMPLIFIED,
    )
    res = R.simplified_standardised(inputs)
    debt = 0.25 + 0.4  # specific 0.25%, general 0.40% (unmatched, 100%)
    equity = 8 + 8
    expected = 1.3 * debt + 3.5 * equity + 3.5 * 3.2 + 1.2 * 8 + 1.9 * (1.5 + 0.3)
    assert res.debt_specific == pytest.approx(0.25) and res.debt_general == pytest.approx(0.4)
    assert res.total == pytest.approx(expected)
    assert res.rwa == pytest.approx(12.5 * expected)
    assert R.ssa_eligible(400, 5_000) and not R.ssa_eligible(450, 50_000)
    assert not R.ssa_eligible(400, 3_000)
