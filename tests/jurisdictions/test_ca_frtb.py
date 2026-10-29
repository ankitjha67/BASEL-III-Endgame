"""Tests for the Canada (OSFI CAR 2026 Chapter 9) market-risk package.

Every transcribed table cell is asserted against an independent literal transcription of the CAR
text (Tables 1-13, 15, 17-20), plus hand-worked examples (single-bucket delta, two-bucket
aggregation with γ, the alternative S_b, curvature with ψ and the tie rule, vega, DRC netting
and HBR, securitisation and CTP DRC, RRAO), scenario selection, bucket-assignment edge cases,
the IMA aggregation helpers, the MAR40 comparison method and protocol conformance.

References: OSFI CAR 2026 Ch.9 (see docs/jurisdictions/CA_frtb_reference.md)
"""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.ca.frtb import CAMarketRisk, drc, ima, rrao, sbm, ssa
from src.jurisdictions.ca.frtb import buckets as bk
from src.jurisdictions.ca.frtb import params as p
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

R = RatingBucket
RC = FRTBRiskClass
M = FRTBMeasure
CALC = CAMarketRisk()
S2 = math.sqrt(2.0)


def sens(rc: FRTBRiskClass, measure: FRTBMeasure = M.DELTA, **kw: object) -> FRTBSensitivity:
    return FRTBSensitivity(risk_class=rc, measure=measure, **kw)  # type: ignore[arg-type]


# =========================================================================
#  Table cells
# =========================================================================

TABLE1 = [(0.25, 0.017), (0.5, 0.017), (1, 0.016), (2, 0.013), (3, 0.012), (5, 0.011),
          (10, 0.011), (15, 0.011), (20, 0.011), (30, 0.011)]


@pytest.mark.parametrize(("tenor", "rw"), TABLE1)
def test_table1_girr_rw(tenor: float, rw: float) -> None:
    assert p.GIRR_RISK_WEIGHTS[float(tenor)] == pytest.approx(rw)


TENORS = [0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30]
TABLE2 = [
    [100.0, 97.0, 91.4, 81.1, 71.9, 56.6, 40.0, 40.0, 40.0, 40.0],
    [97.0, 100.0, 97.0, 91.4, 86.1, 76.3, 56.6, 41.9, 40.0, 40.0],
    [91.4, 97.0, 100.0, 97.0, 94.2, 88.7, 76.3, 65.7, 56.6, 41.9],
    [81.1, 91.4, 97.0, 100.0, 98.5, 95.6, 88.7, 82.3, 76.3, 65.7],
    [71.9, 86.1, 94.2, 98.5, 100.0, 98.0, 93.2, 88.7, 84.4, 76.3],
    [56.6, 76.3, 88.7, 95.6, 98.0, 100.0, 97.0, 94.2, 91.4, 86.1],
    [40.0, 56.6, 76.3, 88.7, 93.2, 97.0, 100.0, 98.5, 97.0, 94.2],
    [40.0, 41.9, 65.7, 82.3, 88.7, 94.2, 98.5, 100.0, 99.0, 97.0],
    [40.0, 40.0, 56.6, 76.3, 84.4, 91.4, 97.0, 99.0, 100.0, 98.5],
    [40.0, 40.0, 41.9, 65.7, 76.3, 86.1, 94.2, 97.0, 98.5, 100.0],
]
TABLE2_CELLS = [(i, j) for i in range(10) for j in range(10)]


@pytest.mark.parametrize(("i", "j"), TABLE2_CELLS)
def test_table2_girr_correlation(i: int, j: int) -> None:
    ti, tj = float(TENORS[i]), float(TENORS[j])
    assert p.GIRR_TENOR_CORRELATION[(ti, tj)] == pytest.approx(TABLE2[i][j] / 100)
    # footnote 38: max[e^(-3%|Tk-Tl|/min), 40%], printed to 0.1%
    formula = max(math.exp(-p.GIRR_TABLE2_THETA * abs(ti - tj) / min(ti, tj)), 0.40)
    assert p.GIRR_TENOR_CORRELATION[(ti, tj)] == pytest.approx(formula, abs=6e-4)


TABLE4 = {1: 0.5, 2: 1.0, 3: 5.0, 4: 3.0, 5: 3.0, 6: 2.0, 7: 1.5, 8: 2.5, 9: 2.0, 10: 4.0,
          11: 12.0, 12: 7.0, 13: 8.5, 14: 5.5, 15: 5.0, 16: 12.0, 17: 1.5, 18: 5.0}


@pytest.mark.parametrize(("b", "rw"), sorted(TABLE4.items()))
def test_table4_csr_nonsec_rw(b: int, rw: float) -> None:
    assert p.CSR_NONSEC_RW[b] == pytest.approx(rw / 100)


TABLE3_QUALITY = {**{b: "IG" for b in range(1, 9)}, **{b: "HY&NR" for b in range(9, 16)},
                  16: "N/A", 17: "IG", 18: "HY"}


@pytest.mark.parametrize(("b", "q"), sorted(TABLE3_QUALITY.items()))
def test_table3_csr_buckets(b: int, q: str) -> None:
    assert p.CSR_NONSEC_BUCKETS[b][0] == q


TABLE5_ORDER = ["1/9", "2/10", "3/11", "4/12", "5/13", "6/14", "7/15", "8", "16", "17", "18"]
TABLE5_ROWS = {
    "1/9": [75, 10, 20, 25, 20, 15, 10, 0, 45, 45],
    "2/10": [5, 15, 20, 15, 10, 10, 0, 45, 45],
    "3/11": [5, 15, 20, 5, 20, 0, 45, 45],
    "4/12": [20, 25, 5, 5, 0, 45, 45],
    "5/13": [25, 5, 15, 0, 45, 45],
    "6/14": [5, 20, 0, 45, 45],
    "7/15": [5, 0, 45, 45],
    "8": [0, 45, 45],
    "16": [0, 0],
    "17": [75],
}
TABLE5_CELLS = [
    (row, TABLE5_ORDER[TABLE5_ORDER.index(row) + 1 + k], v)
    for row, vals in TABLE5_ROWS.items() for k, v in enumerate(vals)
]


@pytest.mark.parametrize(("a", "b", "v"), TABLE5_CELLS)
def test_table5_csr_sector_gamma(a: str, b: str, v: int) -> None:
    assert p.CSR_SECTOR_GAMMA[(a, b)] == pytest.approx(v / 100)
    assert p.CSR_SECTOR_GAMMA[(b, a)] == pytest.approx(v / 100)


TABLE6 = {1: 4, 2: 4, 3: 8, 4: 5, 5: 4, 6: 3, 7: 2, 8: 6, 9: 13, 10: 13, 11: 16, 12: 10,
          13: 12, 14: 12, 15: 12, 16: 13}


@pytest.mark.parametrize(("b", "rw"), sorted(TABLE6.items()))
def test_table6_ctp_rw(b: int, rw: float) -> None:
    assert p.CSR_CTP_RW[b] == pytest.approx(rw / 100)


TABLE8 = {1: 0.9, 2: 1.5, 3: 2.0, 4: 2.0, 5: 0.8, 6: 1.2, 7: 1.2, 8: 1.4}


@pytest.mark.parametrize(("b", "rw"), sorted(TABLE8.items()))
def test_table8_sec_nonctp_rw_and_scalars(b: int, rw: float) -> None:
    assert p.SEC_NONCTP_RW[b] == pytest.approx(rw / 100)
    assert p.SEC_NONCTP_RW[b + 8] == pytest.approx(1.25 * rw / 100)
    assert p.SEC_NONCTP_RW[b + 16] == pytest.approx(1.75 * rw / 100)


def test_sec_nonctp_printed_examples_and_other() -> None:
    assert p.SEC_NONCTP_RW[9] == pytest.approx(0.01125)  # ¶177 "1.25 × 0.9% = 1.125%"
    assert p.SEC_NONCTP_RW[17] == pytest.approx(0.01575)  # ¶178 "1.75 × 0.9% = 1.575%"
    assert p.SEC_NONCTP_RW[25] == pytest.approx(0.035)


TABLE7 = [
    (SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_PRIME, 1),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_MIDPRIME, 2),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_SUBPRIME, 3),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.CMBS, 4),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.ABS_STUDENT_LOANS, 5),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.ABS_CREDIT_CARDS, 6),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.ABS_AUTO, 7),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.CLO_NON_CTP, 8),
    (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.RMBS_PRIME, 9),
    (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.RMBS_SUBPRIME, 11),
    (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.CLO_NON_CTP, 16),
    (SecTrancheClass.HY_NR, SecAssetClass.RMBS_PRIME, 17),
    (SecTrancheClass.HY_NR, SecAssetClass.CMBS, 20),
    (SecTrancheClass.HY_NR, SecAssetClass.CLO_NON_CTP, 24),
    (SecTrancheClass.HY_NR, SecAssetClass.OTHER, 25),
]


@pytest.mark.parametrize(("tranche", "asset", "bucket"), TABLE7)
def test_table7_sec_nonctp_buckets(tranche: SecTrancheClass, asset: SecAssetClass,
                                   bucket: int) -> None:
    s = sens(RC.CSR_SEC_NONCTP, sec_tranche_class=tranche, sec_asset_class=asset, tenor_years=1)
    assert CALC.assign_bucket(s) == str(bucket)


TABLE10 = {1: (55, 0.55), 2: (60, 0.60), 3: (45, 0.45), 4: (55, 0.55), 5: (30, 0.30),
           6: (35, 0.35), 7: (40, 0.40), 8: (50, 0.50), 9: (70, 0.70), 10: (50, 0.50),
           11: (70, 0.70), 12: (15, 0.15), 13: (25, 0.25)}


@pytest.mark.parametrize(("b", "rws"), sorted(TABLE10.items()))
def test_table10_equity_rw(b: int, rws: tuple[float, float]) -> None:
    assert p.EQUITY_SPOT_RW[b] == pytest.approx(rws[0] / 100)
    assert p.EQUITY_REPO_RW[b] == pytest.approx(rws[1] / 100)


TABLE11 = {1: 30, 2: 35, 3: 60, 4: 80, 5: 40, 6: 45, 7: 20, 8: 35, 9: 25, 10: 35, 11: 50}
TABLE12 = {1: 55, 2: 95, 3: 40, 4: 80, 5: 60, 6: 65, 7: 55, 8: 45, 9: 15, 10: 40, 11: 15}


@pytest.mark.parametrize("b", range(1, 12))
def test_tables11_12_commodity(b: int) -> None:
    assert p.COMMODITY_RW[b] == pytest.approx(TABLE11[b] / 100)
    assert p.COMMODITY_CTY_CORRELATION[b] == pytest.approx(TABLE12[b] / 100)


TABLE13 = [("GIRR", 60, 1.0), ("CSR_NONSEC", 120, 1.0), ("CSR_SEC_CTP", 120, 1.0),
           ("CSR_SEC_NONCTP", 120, 1.0), ("EQUITY_LARGE_CAP_AND_INDICES", 20, 0.7778),
           ("EQUITY_SMALL_CAP_AND_OTHER", 60, 1.0), ("COMMODITY", 120, 1.0), ("FX", 40, 1.0)]


@pytest.mark.parametrize(("cls", "lh", "rw"), TABLE13)
def test_table13_vega(cls: str, lh: int, rw: float) -> None:
    assert p.VEGA_LIQUIDITY_HORIZON[cls] == lh
    assert p.VEGA_RW[cls] == pytest.approx(rw)
    assert bk.vega_rw_from_formula(lh) == pytest.approx(rw, abs=5e-5)  # footnote 47


TABLE15 = {"AAA": 0.5, "AA": 2, "A": 3, "BBB": 6, "BB": 15, "B": 30, "CCC": 50, "Unrated": 15,
           "Defaulted": 100}


@pytest.mark.parametrize(("cat", "rw"), sorted(TABLE15.items()))
def test_table15_drc_rw(cat: str, rw: float) -> None:
    assert p.DRC_RW_BY_CATEGORY[cat] == pytest.approx(rw / 100)


TABLE17 = {0: 1.50, 1: 1.50, 2: 1.50, 3: 1.50, 4: 1.50, 5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88,
           9: 1.92, 10: 2.00}


@pytest.mark.parametrize(("n", "m"), sorted(TABLE17.items()))
def test_table17_backtesting(n: int, m: float) -> None:
    assert p.IMA_BACKTESTING_MULTIPLIER[n] == pytest.approx(m)
    assert ima.multiplication_factor(n) == pytest.approx(m)
    assert CALC.ima_parameters().backtesting_addons[n] == pytest.approx(m - 1.5)


TABLE20 = {
    "Interest rate: unspecified currencies": 20, "Interest rate: volatility": 60,
    "Interest rate: other types": 60, "Credit spread: sovereign (IG)": 20,
    "Credit spread: sovereign (HY)": 40, "Credit spread: corporate (IG)": 40,
    "Credit spread: corporate (HY)": 60, "Credit spread: volatility": 120,
    "Credit spread: other types": 120, "Equity price (large cap)": 10,
    "Equity price (small cap)": 20, "Equity price (large cap): volatility": 20,
    "Equity price (small cap): volatility": 60, "Equity: other types": 60,
    "FX rate: specified currency pairs": 10, "FX rate: currency pairs": 20,
    "FX: volatility": 40, "FX: other types": 40,
    "Energy and carbon emissions trading price": 20,
    "Precious metals and non-ferrous metals price": 20, "Other commodities price": 60,
    "Energy and carbon emissions trading price: volatility": 60,
    "Precious metals and non-ferrous metals price: volatility": 60,
    "Other commodities price: volatility": 120, "Commodity: other types": 120,
}


@pytest.mark.parametrize(("cat", "n"), sorted(TABLE20.items()))
def test_table20_liquidity_horizons(cat: str, n: int) -> None:
    assert p.IMA_LIQUIDITY_HORIZONS[cat] == n


def test_ima_scalars() -> None:
    ip = CALC.ima_parameters()
    assert ip.jurisdiction == Jurisdiction.CA
    assert ip.es_confidence == 0.975
    assert ip.multiplier_base == 1.5
    assert ip.imcc_rho == 0.5
    assert ip.ses_rho == 0.6
    assert ip.pla_spearman_thresholds == (0.80, 0.70)
    assert ip.pla_ks_thresholds == (0.09, 0.12)
    assert p.IMA_LIQUIDITY_HORIZON_LADDER == (10, 20, 40, 60, 120)  # Table 19
    assert len(ip.liquidity_horizons_days) == 26


def test_scalar_parameters() -> None:
    assert p.GIRR_INFLATION_RW == p.GIRR_XCCY_BASIS_RW == 0.016
    assert p.GIRR_GAMMA == 0.5 and p.FX_GAMMA == 0.6 and p.FX_RW == 0.15
    assert p.EQUITY_LARGE_CAP_THRESHOLD_CAD == 2.5e9
    assert p.EQUITY_INDEX_MIN_MARKET_CAP_CAD == 50e9
    assert p.DRC_TRS_LARGE_CAP_THRESHOLD_CAD == 6.25e9
    assert (p.DRC_LGD_EQUITY, p.DRC_LGD_SENIOR, p.DRC_LGD_COVERED_BOND) == (1.0, 0.75, 0.25)
    assert (p.RRAO_EXOTIC_RW, p.RRAO_OTHER_RW) == (0.01, 0.001)
    assert p.EQUITY_INTRA_BUCKET_CORRELATION == {
        1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15, 5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25,
        9: 0.075, 10: 0.125, 12: 0.80, 13: 0.80}
    assert {"USD", "CAD", "BRL", "NOK", "INR", "ZAR"} <= p.FX_SPECIFIED_PAIR_CURRENCIES
    assert len(p.FX_SPECIFIED_PAIR_CURRENCIES) == 20


# =========================================================================
#  Scenarios and correlation primitives
# =========================================================================


@pytest.mark.parametrize(("rho", "low", "high"), [
    (0.5, 0.375, 0.625), (0.9, 0.8, 1.0), (0.999, 0.998, 1.0), (0.2, 0.15, 0.25), (0.0, 0.0, 0.0),
])
def test_scenario_correlation(rho: float, low: float, high: float) -> None:
    assert sbm.scenario_correlation(rho, "LOW") == pytest.approx(low)
    assert sbm.scenario_correlation(rho, "MEDIUM") == pytest.approx(rho)
    assert sbm.scenario_correlation(rho, "HIGH") == pytest.approx(high)


def test_printed_correlation_examples() -> None:
    # footnote 39: 1y Eonia vs 5y Euribor = 88.69% x 99.90% = 88.60%
    rho = sbm.delta_rho_fn(RC.GIRR)("EUR", ("RF", "EONIA", 1.0), ("RF", "EURIBOR3M", 5.0))
    assert rho == pytest.approx(0.887 * 0.999)
    # footnote 43: 35% x 65% x 99.90% = 22.73%
    rho = sbm.delta_rho_fn(RC.CSR_NONSEC)("3", ("APPLE", False, 5.0), ("GOOGLE", True, 10.0))
    assert rho == pytest.approx(0.2273, abs=1e-4)
    # footnote 46: 95% x 99% x 99.9% = 93.96%
    rho = sbm.delta_rho_fn(RC.COMMODITY)("2", ("BRENT", "LE HAVRE", 1.0), ("WTI", "OK", 5.0))
    assert rho == pytest.approx(0.9396, abs=1e-4)


def test_girr_special_correlations() -> None:
    f = sbm.delta_rho_fn(RC.GIRR)
    assert f("CAD", ("RF", "A", 5.0), ("RF", "B", 5.0)) == pytest.approx(0.999)
    assert f("CAD", ("INF", "CPI"), ("RF", "A", 5.0)) == pytest.approx(0.40)
    assert f("CAD", ("INF", "CPI"), ("INF", "HICP")) == pytest.approx(0.999)
    assert f("CAD", ("XCCY", "USD"), ("RF", "A", 5.0)) == 0.0
    assert f("CAD", ("XCCY", "USD"), ("INF", "CPI")) == 0.0


def test_equity_and_ctp_correlations() -> None:
    f = sbm.delta_rho_fn(RC.EQUITY)
    assert f("5", ("X", "SPOT"), ("X", "REPO")) == pytest.approx(0.999)
    assert f("5", ("X", "SPOT"), ("Y", "SPOT")) == pytest.approx(0.25)
    assert f("9", ("X", "SPOT"), ("Y", "SPOT")) == pytest.approx(0.075)
    assert f("10", ("X", "REPO"), ("Y", "REPO")) == pytest.approx(0.125)
    assert f("12", ("X", "SPOT"), ("Y", "REPO")) == pytest.approx(0.80 * 0.999)
    ctp = sbm.delta_rho_fn(RC.CSR_SEC_CTP)
    assert ctp("3", ("A", False, 5.0), ("A", True, 5.0)) == pytest.approx(0.99)
    idx = sbm.delta_rho_fn(RC.CSR_NONSEC)
    assert idx("17", ("CDX", False, 5.0), ("ITRX", False, 5.0)) == pytest.approx(0.80)
    sec = sbm.delta_rho_fn(RC.CSR_SEC_NONCTP)
    assert sec("1", ("T1", False, 1.0), ("T2", False, 3.0)) == pytest.approx(0.4 * 0.8)


@pytest.mark.parametrize(("b", "c", "g"), [
    ("1", "9", 0.5), ("3", "11", 0.5), ("1", "2", 0.75), ("1", "10", 0.375), ("8", "17", 0.45),
    ("16", "1", 0.0), ("17", "18", 0.75), ("9", "17", 0.45), ("4", "6", 0.25),
])
def test_csr_gamma(b: str, c: str, g: float) -> None:
    assert sbm.csr_gamma(b, c) == pytest.approx(g)


@pytest.mark.parametrize(("b", "c", "g"), [
    ("1", "10", 0.15), ("11", "3", 0.0), ("12", "13", 0.75), ("12", "5", 0.45), ("13", "13", 0.45),
])
def test_equity_gamma(b: str, c: str, g: float) -> None:
    assert sbm.equity_gamma(b, c) == pytest.approx(g)


def test_commodity_gamma() -> None:
    assert sbm.commodity_gamma("1", "10") == 0.2
    assert sbm.commodity_gamma("11", "2") == 0.0


def test_vega_maturity_correlation() -> None:
    gi = sbm.vega_rho_fn(RC.GIRR)
    rho = gi("CAD", ("RISK_FREE", "", 1.0, 5.0), ("RISK_FREE", "", 5.0, 5.0))
    assert rho == pytest.approx(math.exp(-0.01 * 4 / 1))
    eq = sbm.vega_rho_fn(RC.EQUITY)
    assert eq("5", ("X", 1.0), ("Y", 3.0)) == pytest.approx(0.25 * math.exp(-0.01 * 2 / 1))


# =========================================================================
#  Bucket assignment edge cases
# =========================================================================


@pytest.mark.parametrize(("kw", "bucket"), [
    ({"credit_sector": CreditSector.SOVEREIGN, "rating": R.AAA_TO_AA_MINUS}, "1"),
    ({"credit_sector": CreditSector.SOVEREIGN, "rating": R.BB_PLUS_TO_BB_MINUS}, "9"),
    ({"credit_sector": CreditSector.FINANCIAL, "rating": R.UNRATED}, "11"),
    ({"credit_sector": CreditSector.FINANCIAL, "is_investment_grade": True}, "3"),
    ({"credit_sector": CreditSector.HEALTH_CARE, "rating": R.BBB_PLUS_TO_BBB_MINUS}, "7"),
    ({"credit_sector": CreditSector.COVERED_BOND, "rating": R.AAA_TO_AA_MINUS}, "8"),
    ({"credit_sector": CreditSector.COVERED_BOND, "rating": R.BB_PLUS_TO_BB_MINUS}, "16"),
    ({"credit_sector": CreditSector.INDEX, "rating": R.A_PLUS_TO_A_MINUS}, "17"),
    ({"credit_sector": CreditSector.INDEX, "rating": R.B_PLUS_TO_B_MINUS}, "18"),
    ({"credit_sector": None}, "16"),
    ({"credit_sector": CreditSector.OTHER, "rating": R.AAA_TO_AA_MINUS}, "16"),
    ({"credit_sector": CreditSector.LOCAL_GOVERNMENT,
      "flags": {"canadian_province_or_agent": True}}, "1"),
    ({"credit_sector": CreditSector.FINANCIAL, "flags": {"gse_non_tranched_mbs": True}}, "2"),
    ({"credit_sector": CreditSector.FINANCIAL, "bucket_hint": "5"}, "5"),
    ({"credit_sector": CreditSector.FINANCIAL, "rating": R.UNRATED, "bucket_hint": "99"}, "11"),
])
def test_csr_bucket_assignment(kw: dict[str, object], bucket: str) -> None:
    assert CALC.assign_bucket(sens(RC.CSR_NONSEC, tenor_years=5, **kw)) == bucket


def test_ctp_bucket_assignment() -> None:
    assert CALC.assign_bucket(sens(RC.CSR_SEC_CTP, credit_sector=CreditSector.INDEX)) == "16"
    assert CALC.assign_bucket(
        sens(RC.CSR_SEC_CTP, credit_sector=CreditSector.INDEX, bucket_hint="3")) == "3"
    assert CALC.assign_bucket(sens(RC.CSR_SEC_CTP, credit_sector=CreditSector.TECHNOLOGY,
                                   rating=R.BB_PLUS_TO_BB_MINUS)) == "14"


@pytest.mark.parametrize(("kw", "bucket"), [
    ({"is_large_cap": True, "is_advanced_economy": False,
      "equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES}, "1"),
    ({"is_large_cap": True, "is_advanced_economy": False,
      "equity_sector": EquitySector.FINANCIALS_REALESTATE_TECH}, "4"),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.TELECOM_INDUSTRIALS}, "6"),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, "7"),
    ({"is_large_cap": False, "is_advanced_economy": False,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, "9"),
    ({"is_large_cap": False, "is_advanced_economy": True,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, "10"),
    ({"is_large_cap": None, "is_advanced_economy": True,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, "10"),
    ({"is_large_cap": True, "is_advanced_economy": None,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, "3"),
    ({"is_large_cap": True, "is_advanced_economy": True, "equity_sector": None}, "11"),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.OTHER}, "11"),
    ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": True}, "12"),
    ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": False}, "13"),
    ({"is_equity_index": True}, "13"),
])
def test_equity_bucket_assignment(kw: dict[str, object], bucket: str) -> None:
    assert CALC.assign_bucket(sens(RC.EQUITY, **kw)) == bucket


@pytest.mark.parametrize(("group", "bucket"), [
    (CommodityGroup.ENERGY_SOLID, "1"), (CommodityGroup.FREIGHT, "4"),
    (CommodityGroup.PRECIOUS_METALS, "7"), (CommodityGroup.SOFTS_OTHER_AGRI, "10"),
    (CommodityGroup.OTHER, "11"), (None, "11"),
])
def test_commodity_bucket_assignment(group: CommodityGroup | None, bucket: str) -> None:
    assert CALC.assign_bucket(sens(RC.COMMODITY, commodity_group=group)) == bucket


def test_girr_fx_buckets_and_rw() -> None:
    assert CALC.assign_bucket(sens(RC.GIRR, currency="usd", tenor_years=1)) == "USD"
    assert CALC.assign_bucket(sens(RC.FX, fx_currency="USD")) == "USD/CAD"
    with pytest.raises(ValueError):
        CALC.assign_bucket(sens(RC.GIRR))
    # GIRR sqrt(2): specified currencies and the reporting currency (¶156)
    assert bk.delta_risk_weight(sens(RC.GIRR, currency="CAD"), "CAD", 1.0) == pytest.approx(
        0.016 / S2)
    assert bk.delta_risk_weight(sens(RC.GIRR, currency="BRL"), "BRL", 1.0) == pytest.approx(0.016)
    assert bk.delta_risk_weight(sens(RC.GIRR, currency="BRL"), "BRL", 1.0, "BRL") == (
        pytest.approx(0.016 / S2))
    opt_out = sens(RC.GIRR, currency="USD", flags={"no_sqrt2_discretion": True})
    assert bk.delta_risk_weight(opt_out, "USD", 1.0) == pytest.approx(0.016)
    infl = sens(RC.GIRR, currency="USD", girr_curve=GIRRCurve.INFLATION)
    assert bk.delta_risk_weight(infl, "USD", None) == pytest.approx(0.016)
    # FX sqrt(2): USD/CAD specified; ARS/CAD not; first-order cross BRL/CAD specified (¶200)
    assert bk.delta_risk_weight(sens(RC.FX, fx_currency="USD"), "USD/CAD", None) == (
        pytest.approx(0.15 / S2))
    assert bk.delta_risk_weight(sens(RC.FX, fx_currency="ARS"), "ARS/CAD", None) == (
        pytest.approx(0.15))
    assert bk.fx_pair_is_specified("BRL", "CAD")
    assert not bk.fx_pair_is_specified("ARS", "USD")
    forced = sens(RC.FX, fx_currency="ARS", fx_pair_is_liquid=True)
    assert bk.delta_risk_weight(forced, "ARS/CAD", None) == pytest.approx(0.15 / S2)


def test_special_csr_risk_weights() -> None:
    gse = sens(RC.CSR_NONSEC, flags={"gse_non_tranched_mbs": True})
    assert bk.delta_risk_weight(gse, "2", 5.0) == pytest.approx(0.010)
    cb = sens(RC.CSR_NONSEC, credit_sector=CreditSector.COVERED_BOND, rating=R.AAA_TO_AA_MINUS)
    assert bk.delta_risk_weight(cb, "8", 5.0) == pytest.approx(0.025)
    cb_opt = cb.model_copy(update={"flags": {"covered_bond_aa_discretion": True}})
    assert bk.delta_risk_weight(cb_opt, "8", 5.0) == pytest.approx(0.015)
    repo = sens(RC.EQUITY, equity_risk_factor=EquityRiskFactor.REPO)
    assert bk.delta_risk_weight(repo, "9", None) == pytest.approx(0.007)


def test_vega_and_curvature_rw() -> None:
    assert bk.vega_risk_weight(sens(RC.EQUITY), "5") == pytest.approx(0.7778)
    assert bk.vega_risk_weight(sens(RC.EQUITY), "12") == pytest.approx(0.7778)
    assert bk.vega_risk_weight(sens(RC.EQUITY), "11") == pytest.approx(1.0)
    assert bk.vega_risk_weight(sens(RC.FX), "USD/CAD") == pytest.approx(1.0)
    girr = sens(RC.GIRR, currency="CAD")
    assert bk.curvature_risk_weight(girr, "CAD") == pytest.approx(0.017 / S2)
    assert bk.curvature_risk_weight(sens(RC.EQUITY), "5") == pytest.approx(0.30)


@pytest.mark.parametrize(("t", "expected"), [
    (4.0, [(3.0, 0.5), (5.0, 0.5)]), (0.1, [(0.25, 1.0)]), (40.0, [(30.0, 1.0)]),
    (5.0, [(5.0, 1.0)]), (7.5, [(5.0, 0.5), (10.0, 0.5)]),
])
def test_linear_interpolation(t: float, expected: list[tuple[float, float]]) -> None:
    got = bk.allocate_to_vertices(t, p.GIRR_TENORS)
    assert [(a, pytest.approx(b)) for a, b in got] == expected


# =========================================================================
#  Hand-worked SBM examples
# =========================================================================


def test_single_bucket_girr_delta() -> None:
    s = [sens(RC.GIRR, value=100, currency="CAD", tenor_years=1),
         sens(RC.GIRR, value=-50, currency="CAD", tenor_years=5)]
    ws1, ws2 = 100 * 0.016 / S2, -50 * 0.011 / S2
    by_sc = CALC.sbm_by_scenario(s)
    for sc, rho in (("MEDIUM", 0.887), ("HIGH", 1.0), ("LOW", max(2 * 0.887 - 1, 0.75 * 0.887))):
        k = math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * rho * ws1 * ws2)
        assert by_sc[sc][RC.GIRR].delta == pytest.approx(k)


def test_netting_same_risk_factor() -> None:
    # ¶116(2): two opposite sensitivities to the same risk factor net to zero.
    s = [sens(RC.GIRR, value=100, currency="CAD", tenor_years=2, curve_name="CORRA"),
         sens(RC.GIRR, value=-100, currency="CAD", tenor_years=2, curve_name="CORRA")]
    assert all(r.total == 0.0 for r in CALC.sbm_capital(s))


def test_two_bucket_csr_with_gamma_and_low_scenario_binding() -> None:
    s = [sens(RC.CSR_NONSEC, value=100, issuer="A", tenor_years=5,
              credit_sector=CreditSector.FINANCIAL, rating=R.A_PLUS_TO_A_MINUS),
         sens(RC.CSR_NONSEC, value=-50, issuer="B", tenor_years=5,
              credit_sector=CreditSector.FINANCIAL, rating=R.BB_PLUS_TO_BB_MINUS)]
    by_sc = CALC.sbm_by_scenario(s)
    # WS = 5 (bucket 3) and -6 (bucket 11); γ = 50% (rating) x 1 (same sector)
    assert by_sc["MEDIUM"][RC.CSR_NONSEC].delta == pytest.approx(math.sqrt(31.0))
    assert by_sc["HIGH"][RC.CSR_NONSEC].delta == pytest.approx(math.sqrt(61 - 60 * 0.625))
    assert by_sc["LOW"][RC.CSR_NONSEC].delta == pytest.approx(math.sqrt(61 - 60 * 0.375))
    res = CALC.sbm_capital(s)
    assert res[0].scenario == "LOW"
    assert res[0].total == pytest.approx(math.sqrt(38.5))


def test_high_scenario_binds_for_same_sign_book() -> None:
    s = [sens(RC.GIRR, value=100, currency="CAD", tenor_years=5),
         sens(RC.GIRR, value=100, currency="USD", tenor_years=5)]
    res = CALC.sbm_capital(s)
    assert res[0].scenario == "HIGH"
    ws = 100 * 0.011 / S2
    assert res[0].delta == pytest.approx(math.sqrt(2 * ws ** 2 + 2 * 0.625 * ws * ws))


def test_alternative_sb_specification() -> None:
    k = {"9": math.sqrt(48.5), "10": math.sqrt(67.5)}
    s = {"9": 20.0, "10": -20.0}
    # 48.5 + 67.5 + 2 x 0.15 x 20 x (-20) = -4 < 0 -> S_b = max(min(S_b, K_b), -K_b)
    got = sbm.across_buckets_linear(k, s, sbm.equity_gamma, "MEDIUM")
    expected = math.sqrt(116 + 2 * 0.15 * k["9"] * (-k["10"]))
    assert got == pytest.approx(expected)
    # same result end-to-end: 20 small-cap EM names long, 20 small-cap AE names short (WS = ±1)
    rw9, rw10 = 0.70, 0.50
    sens_list = [sens(RC.EQUITY, value=1 / rw9, issuer=f"E{i}", is_large_cap=False,
                      is_advanced_economy=False, equity_sector=EquitySector.MATERIALS_ENERGY)
                 for i in range(20)]
    sens_list += [sens(RC.EQUITY, value=-1 / rw10, issuer=f"A{i}", is_large_cap=False,
                       is_advanced_economy=True, equity_sector=EquitySector.MATERIALS_ENERGY)
                  for i in range(20)]
    by_sc = CALC.sbm_by_scenario(sens_list)
    assert by_sc["MEDIUM"][RC.EQUITY].delta == pytest.approx(expected)


def test_other_bucket_simple_sum() -> None:
    s = [sens(RC.CSR_NONSEC, value=100, issuer="X", tenor_years=5),
         sens(RC.CSR_NONSEC, value=-100, issuer="Y", tenor_years=5)]
    by_sc = CALC.sbm_by_scenario(s)
    assert by_sc["MEDIUM"][RC.CSR_NONSEC].delta == pytest.approx(24.0)  # 12 + 12
    assert by_sc["LOW"][RC.CSR_NONSEC].delta == pytest.approx(24.0)


def test_sec_nonctp_other_bucket_added_linearly() -> None:
    s = [sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T1", tenor_years=1,
              sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.CMBS),
         sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T2", tenor_years=1,
              sec_tranche_class=SecTrancheClass.SENIOR_IG,
              sec_asset_class=SecAssetClass.ABS_AUTO),
         sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T3", tenor_years=1)]
    by_sc = CALC.sbm_by_scenario(s)
    expected = math.sqrt(2.0 ** 2 + 1.2 ** 2) + 3.5  # γ = 0 for 1-24, bucket 25 added
    for sc in ("LOW", "MEDIUM", "HIGH"):
        assert by_sc[sc][RC.CSR_SEC_NONCTP].delta == pytest.approx(expected)


def test_fx_delta_two_buckets() -> None:
    s = [sens(RC.FX, value=100, fx_currency="USD"), sens(RC.FX, value=-100, fx_currency="ARS")]
    ws1, ws2 = 100 * 0.15 / S2, -100 * 0.15
    by_sc = CALC.sbm_by_scenario(s)
    assert by_sc["MEDIUM"][RC.FX].delta == pytest.approx(
        math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * 0.6 * ws1 * ws2))


def test_commodity_delta_within_bucket() -> None:
    s = [sens(RC.COMMODITY, value=100, commodity_name="WTI", tenor_years=1,
              commodity_group=CommodityGroup.ENERGY_LIQUID),
         sens(RC.COMMODITY, value=-100, commodity_name="BRENT", tenor_years=1,
              commodity_group=CommodityGroup.ENERGY_LIQUID)]
    ws = 35.0
    rho = 0.95
    by_sc = CALC.sbm_by_scenario(s)
    assert by_sc["MEDIUM"][RC.COMMODITY].delta == pytest.approx(math.sqrt(2 * ws * ws * (1 - rho)))


def test_vega_equity_single_bucket() -> None:
    s = [sens(RC.EQUITY, M.VEGA, value=10, issuer="X", option_maturity_years=1,
              is_large_cap=True, is_advanced_economy=True,
              equity_sector=EquitySector.TELECOM_INDUSTRIALS),
         sens(RC.EQUITY, M.VEGA, value=10, issuer="Y", option_maturity_years=1,
              is_large_cap=True, is_advanced_economy=True,
              equity_sector=EquitySector.TELECOM_INDUSTRIALS)]
    ws = 10 * 0.7778
    by_sc = CALC.sbm_by_scenario(s)
    assert by_sc["MEDIUM"][RC.EQUITY].vega == pytest.approx(math.sqrt(2 * ws * ws * 1.25))


def test_vega_missing_maturity_goes_to_longest_tenor() -> None:
    s = [sens(RC.FX, M.VEGA, value=10, fx_currency="USD")]
    grouped = sbm._group(s, "CAD")
    assert list(grouped[M.VEGA]["USD/CAD"].factors) == [("", 10.0)]


def test_girr_curvature_two_buckets() -> None:
    s = [sens(RC.GIRR, M.CURVATURE, currency="CAD", cvr_up=10, cvr_down=-5),
         sens(RC.GIRR, M.CURVATURE, currency="USD", cvr_up=-4, cvr_down=6)]
    by_sc = CALC.sbm_by_scenario(s)
    assert by_sc["MEDIUM"][RC.GIRR].curvature == pytest.approx(math.sqrt(136 + 2 * 0.25 * 60))
    assert by_sc["HIGH"][RC.GIRR].curvature == pytest.approx(math.sqrt(136 + 2 * 0.3125 * 60))
    assert by_sc["LOW"][RC.GIRR].curvature == pytest.approx(math.sqrt(136 + 2 * 0.1875 * 60))


def test_curvature_within_bucket_and_psi() -> None:
    rho = sbm.curvature_rho_fn(RC.EQUITY)
    k, s_b = sbm.curvature_bucket([10.0, 20.0], [-1.0, -2.0], [("X",), ("Y",)], "5", rho,
                                  "MEDIUM")
    assert k == pytest.approx(math.sqrt(100 + 400 + 2 * 0.0625 * 200))
    assert s_b == 30.0
    # ψ = 0 when both CVR negative: cross term removed; max(CVR,0)² terms 0 -> K = 0
    k2, _ = sbm.curvature_bucket([-10.0, -20.0], [-10.0, -20.0], [("X",), ("Y",)], "5", rho,
                                 "MEDIUM")
    assert k2 == 0.0


def test_curvature_tie_rule() -> None:
    rho = sbm.curvature_rho_fn(RC.FX)
    # K+ = K- = 5; Σ CVR+ = 5 > Σ CVR- = 5? equal -> downward selected
    k, s_b = sbm.curvature_bucket([5.0], [5.0], [("FX",)], "USD/CAD", rho, "MEDIUM")
    assert (k, s_b) == (5.0, 5.0)
    k, s_b = sbm.curvature_bucket([5.0, -1.0], [5.0, -3.0], [("A",), ("B",)], "1",
                                  sbm.curvature_rho_fn(RC.COMMODITY), "MEDIUM", other=True)
    # other-bucket formula: max(Σ max(CVR+,0), Σ max(CVR-,0)) = 5 both; Σ CVR+ = 4 > 2 -> up
    assert (k, s_b) == (5.0, 4.0)


def test_curvature_across_psi_negative_pair() -> None:
    got = sbm.curvature_across({"CAD": 3.0, "USD": 4.0}, {"CAD": -3.0, "USD": -4.0},
                               lambda _b, _c: 0.5, "MEDIUM")
    assert got == pytest.approx(5.0)


def test_fx_curvature_scalar_and_other_bucket_curvature() -> None:
    s = [sens(RC.FX, M.CURVATURE, fx_currency="USD", cvr_up=15, cvr_down=3,
              flags={"fx_curvature_no_reporting_ccy": True})]
    assert CALC.sbm_by_scenario(s)["MEDIUM"][RC.FX].curvature == pytest.approx(10.0)
    s2 = [sens(RC.EQUITY, M.CURVATURE, issuer="A", cvr_up=5, cvr_down=1),
          sens(RC.EQUITY, M.CURVATURE, issuer="B", cvr_up=4, cvr_down=2)]
    assert CALC.sbm_by_scenario(s2)["MEDIUM"][RC.EQUITY].curvature == pytest.approx(9.0)


def test_no_curvature_for_inflation_or_repo() -> None:
    s = [sens(RC.GIRR, M.CURVATURE, currency="CAD", girr_curve=GIRRCurve.INFLATION,
              cvr_up=10, cvr_down=10),
         sens(RC.EQUITY, M.CURVATURE, equity_risk_factor=EquityRiskFactor.REPO, cvr_up=10)]
    by_sc = CALC.sbm_by_scenario(s)
    assert by_sc["MEDIUM"][RC.GIRR].curvature == 0.0
    assert by_sc["MEDIUM"][RC.EQUITY].curvature == 0.0


# =========================================================================
#  DRC
# =========================================================================


def drc_pos(
    pid: str, obligor: str, is_long: bool, notional: float, **kw: object,
) -> DRCPositionInput:
    mv = kw.pop("market_value", notional)
    return DRCPositionInput(position_id=pid, obligor=obligor, is_long=is_long, notional=notional,
                            market_value=mv, **kw)  # type: ignore[arg-type]


def test_gross_jtd_and_lgd() -> None:
    bond = drc_pos("1", "X", True, 100, market_value=90)
    assert drc.gross_jtd_nonsec(bond) == pytest.approx(0.75 * 100 - 10)
    short = drc_pos("2", "X", False, 100, market_value=90)
    assert drc.gross_jtd_nonsec(short) == pytest.approx(-0.75 * 100 + 10)
    eq = drc_pos("3", "X", True, 100, seniority=DRCSeniority.EQUITY)
    assert drc.gross_jtd_nonsec(eq) == pytest.approx(100)
    cb = drc_pos("4", "X", True, 100, seniority=DRCSeniority.COVERED_BOND)
    assert drc.gross_jtd_nonsec(cb) == pytest.approx(25)
    hybrid = drc_pos("5", "X", True, 100, flags={"price_not_linked_to_recovery": True})
    assert drc.gross_jtd_nonsec(hybrid) == pytest.approx(100)
    gse = drc_pos("6", "X", True, 100, seniority=DRCSeniority.NON_SENIOR,
                  flags={"gse_non_tranched_mbs": True})
    assert drc.lgd(gse) == 0.75
    # call option on a bond: notional 0, JTD = P&L floored at 0 for a long
    call = drc_pos("7", "X", True, 0, market_value=5, pnl=-5)
    assert drc.gross_jtd_nonsec(call) == 0.0


@pytest.mark.parametrize(("m", "w"), [(0.0, 0.25), (1 / 12, 0.25), (0.25, 0.25), (0.5, 0.5),
                                      (1.0, 1.0), (5.0, 1.0)])
def test_maturity_weight(m: float, w: float) -> None:
    assert drc.maturity_weight(m) == pytest.approx(w)


def test_index_future_example_nets_to_zero() -> None:
    # ¶228 example: -10 index future (1M) hedged with +10 equities (3M): 1/4 x 10 - 1/4 x 10 = 0
    pos = [drc_pos("f", "IDX", False, 10, seniority=DRCSeniority.EQUITY, maturity_years=1 / 12),
           drc_pos("e", "IDX", True, 10, seniority=DRCSeniority.EQUITY, maturity_years=0.25)]
    assert drc.drc_nonsec(pos)[0] == 0.0


def test_drc_netting_and_hbr_example() -> None:
    pos = [
        drc_pos("1", "X", True, 100, maturity_years=2, rating=R.BBB_PLUS_TO_BBB_MINUS),
        drc_pos("2", "X", False, 30, maturity_years=0.5, seniority=DRCSeniority.EQUITY,
                rating=R.BBB_PLUS_TO_BBB_MINUS),
        drc_pos("3", "Y", False, 50, maturity_years=2, rating=R.BBB_PLUS_TO_BBB_MINUS),
    ]
    total, detail = drc.drc_nonsec(pos)
    # X: 75 - 0.5 x 30 = 60 net long; Y: -37.5 net short; HBR = 60 / 97.5
    hbr = 60 / 97.5
    assert detail["corporates"] == pytest.approx(0.06 * 60 - hbr * 0.06 * 37.5)
    assert total == pytest.approx(detail["corporates"])


def test_drc_seniority_blocks_offset() -> None:
    # A short bond cannot offset a long equity of the same obligor (¶232(1)).
    pos = [drc_pos("1", "X", True, 100, seniority=DRCSeniority.EQUITY, rating=R.UNRATED),
           drc_pos("2", "X", False, 100, seniority=DRCSeniority.SENIOR, rating=R.UNRATED)]
    net = drc.net_jtd_nonsec(pos)
    assert sorted(n.amount for n in net) == [-75.0, 100.0]
    total, _ = drc.drc_nonsec(pos)
    hbr = 100 / 175
    assert total == pytest.approx(0.15 * 100 - hbr * 0.15 * 75)


def test_drc_sovereign_overrides_and_buckets() -> None:
    gov = drc_pos("1", "GOC", True, 100, credit_sector=CreditSector.SOVEREIGN,
                  flags={"canadian_sovereign_zero_rw": True})
    assert drc.default_risk_weight_nonsec(gov) == 0.0
    prov = drc_pos("2", "ONT", True, 100, credit_sector=CreditSector.LOCAL_GOVERNMENT,
                   flags={"canadian_province_or_agent": True}, rating=R.A_PLUS_TO_A_MINUS)
    assert drc.default_risk_weight_nonsec(prov) == 0.0
    assert drc.nonsec_bucket(prov) == "sovereigns"
    other = drc_pos("3", "DEU", True, 100, credit_sector=CreditSector.SOVEREIGN,
                    rating=R.AAA_TO_AA_MINUS, flags={"other_ig_sovereign_local_funded": True})
    assert drc.default_risk_weight_nonsec(other) == pytest.approx(0.005)
    hy = drc_pos("4", "ARG", True, 100, credit_sector=CreditSector.SOVEREIGN,
                 rating=R.B_PLUS_TO_B_MINUS, flags={"other_ig_sovereign_local_funded": True})
    assert drc.default_risk_weight_nonsec(hy) == pytest.approx(0.30)
    muni = drc_pos("5", "M", True, 100, credit_sector=CreditSector.LOCAL_GOVERNMENT)
    assert drc.nonsec_bucket(muni) == "local governments and municipalities"
    assert drc.nonsec_bucket(drc_pos("6", "C", True, 1)) == "corporates"


@pytest.mark.parametrize(("rating", "flags", "defaulted", "rw"), [
    (R.AAA_TO_AA_MINUS, {}, False, 0.02), (R.AAA_TO_AA_MINUS, {"rating_aaa": True}, False, 0.005),
    (R.A_PLUS_TO_A_MINUS, {}, False, 0.03), (R.BB_PLUS_TO_BB_MINUS, {}, False, 0.15),
    (R.B_PLUS_TO_B_MINUS, {}, False, 0.30), (R.BELOW_B_MINUS, {}, False, 0.50),
    (R.UNRATED, {}, False, 0.15), (R.A_PLUS_TO_A_MINUS, {}, True, 1.0),
])
def test_drc_rating_mapping(rating: RatingBucket, flags: dict[str, bool], defaulted: bool,
                            rw: float) -> None:
    pos = drc_pos("1", "X", True, 1, rating=rating, flags=flags, is_defaulted=defaulted)
    assert drc.default_risk_weight_nonsec(pos) == pytest.approx(rw)


def test_drc_buckets_not_hedged_across() -> None:
    pos = [drc_pos("1", "C", True, 100, rating=R.UNRATED),
           drc_pos("2", "S", False, 100, rating=R.UNRATED, credit_sector=CreditSector.SOVEREIGN)]
    total, detail = drc.drc_nonsec(pos)
    assert detail["corporates"] == pytest.approx(0.15 * 75)
    assert detail["sovereigns"] == 0.0
    assert total == pytest.approx(11.25)


def test_drc_sec_nonctp() -> None:
    pos = [
        drc_pos("1", "P", True, 100, kind=DRCKind.SEC_NON_CTP, pool_id="P", tranche_id="A",
                banking_book_risk_weight=1.0, sec_asset_class=SecAssetClass.CMBS,
                region="North America"),
        drc_pos("2", "P", False, 50, kind=DRCKind.SEC_NON_CTP, pool_id="P", tranche_id="B",
                banking_book_risk_weight=1.0, sec_asset_class=SecAssetClass.CMBS,
                region="North America"),
    ]
    total, detail = drc.drc_sec_nonctp(pos)
    assert list(detail) == ["commercial MBS | North America"]
    assert total == pytest.approx(8 - (100 / 150) * 4)
    # same tranche nets fully; missing RW -> 1,250% x 8% = 100% (fair-value cap)
    same = [pos[0], pos[1].model_copy(update={"tranche_id": "A"})]
    assert drc.drc_sec_nonctp(same)[0] == pytest.approx(0.08 * 50)
    assert drc.sec_default_risk_weight(drc_pos("x", "P", True, 1)) == pytest.approx(1.0)
    assert drc.sec_nonctp_bucket(drc_pos("x", "P", True, 1)) == "other bucket"
    assert drc.sec_nonctp_bucket(drc_pos("x", "P", True, 1, flags={"sec_corporate": True})) == (
        "corporates")


def test_drc_ctp_negative_bucket_half_weight() -> None:
    pos = [
        drc_pos("1", "A", True, 1000, kind=DRCKind.CTP, pool_id="CDX.NA.IG", tranche_id="0-3",
                banking_book_risk_weight=1.25),
        drc_pos("2", "B", False, 1000, kind=DRCKind.CTP, pool_id="MAJOR.SOV", tranche_id="0-3",
                banking_book_risk_weight=1.25),
    ]
    total, detail = drc.drc_ctp(pos)
    assert detail["CDX.NA.IG"] == pytest.approx(100.0)
    assert detail["MAJOR.SOV"] == pytest.approx(-50.0)  # HBR_ctp = 0.5, not floored
    assert total == pytest.approx(100 - 0.5 * 50)


def test_ctp_printed_example_formula() -> None:
    # ¶258: +100 and -100 -> 100 - 0.5 x 100 = 50
    vals = [100.0, -100.0]
    assert max(sum(max(v, 0) + 0.5 * min(v, 0) for v in vals), 0) == 50.0


def test_drc_capital_components() -> None:
    pos = [drc_pos("1", "X", True, 100, rating=R.UNRATED),
           drc_pos("2", "P", True, 100, kind=DRCKind.SEC_NON_CTP, banking_book_risk_weight=0.2),
           drc_pos("3", "I", True, 100, kind=DRCKind.CTP, flags={"ctp_non_tranched": True},
                   rating=R.A_PLUS_TO_A_MINUS)]
    out = CALC.drc_capital(pos)
    assert out["nonsec"] == pytest.approx(11.25)
    assert out["sec_nonctp"] == pytest.approx(100 * 0.2 * 0.08)
    assert out["ctp"] == pytest.approx(3.0)
    assert out["total"] == pytest.approx(11.25 + 1.6 + 3.0)


# =========================================================================
#  RRAO
# =========================================================================


@pytest.mark.parametrize(("cat", "exempt", "flags", "expected"), [
    (RRAOCategory.EXOTIC, False, {}, 10.0),
    (RRAOCategory.OTHER_RESIDUAL, False, {}, 1.0),
    (RRAOCategory.OTHER_RESIDUAL, False, {"listed_or_cc_eligible": True}, 0.0),
    (RRAOCategory.EXOTIC, False, {"listed_or_cc_eligible": True}, 10.0),
    (RRAOCategory.EXOTIC, True, {"listed_or_cc_eligible": True}, 10.0),
    (RRAOCategory.EXOTIC, False, {"back_to_back": True}, 0.0),
    (RRAOCategory.OTHER_RESIDUAL, True, {}, 0.0),
])
def test_rrao(cat: RRAOCategory, exempt: bool, flags: dict[str, bool], expected: float) -> None:
    pos = RRAOPositionInput(position_id="r", gross_notional=1000, category=cat, exempt=exempt,
                            flags=flags)
    assert rrao.rrao_capital([pos]) == pytest.approx(expected)
    assert CALC.rrao_capital([pos, pos]) == pytest.approx(2 * expected)


# =========================================================================
#  Total and protocol
# =========================================================================


def test_protocol_conformance_and_total() -> None:
    assert isinstance(CALC, MarketRiskCalculator)
    assert CALC.jurisdiction == Jurisdiction.CA
    s = [sens(RC.GIRR, value=100, currency="CAD", tenor_years=5),
         sens(RC.FX, value=50, fx_currency="USD")]
    d = [drc_pos("1", "X", True, 100, rating=R.UNRATED)]
    r = [RRAOPositionInput(position_id="r", gross_notional=1000, category=RRAOCategory.EXOTIC)]
    res = CALC.market_risk(s, d, r)
    assert res.jurisdiction == Jurisdiction.CA
    assert res.sbm_total == pytest.approx(sum(c.total for c in res.sbm_by_class))
    assert res.drc_total == pytest.approx(11.25)
    assert res.rrao == pytest.approx(10.0)
    assert res.total_capital == pytest.approx(res.sbm_total + 11.25 + 10.0)
    assert res.rwa == pytest.approx(12.5 * res.total_capital)
    assert res.binding_scenario in ("LOW", "MEDIUM", "HIGH")
    assert {c.risk_class for c in res.sbm_by_class} == {RC.GIRR, RC.FX}
    assert "drc_nonsec" in res.citations


def test_empty_portfolio() -> None:
    res = CALC.market_risk([], [], [])
    assert res.total_capital == 0.0 and res.rwa == 0.0 and res.sbm_by_class == []


# =========================================================================
#  IMA helpers
# =========================================================================


def test_liquidity_adjusted_es() -> None:
    got = ima.liquidity_adjusted_es(10.0, [5.0, 4.0, 3.0, 2.0])
    exp = math.sqrt(100 + (5 * 1) ** 2 + (4 * math.sqrt(2)) ** 2 + (3 * math.sqrt(2)) ** 2
                    + (2 * math.sqrt(6)) ** 2)
    assert got == pytest.approx(exp)
    with pytest.raises(ValueError):
        ima.liquidity_adjusted_es(1.0, [1.0] * 5)


def test_ima_aggregation_formulas() -> None:
    assert ima.stressed_es(10.0, 8.0, 10.0) == 10.0  # ratio floored at 1
    assert ima.stressed_es(10.0, 12.0, 10.0) == pytest.approx(12.0)
    assert ima.imcc(100.0, [40.0, 50.0, 30.0]) == pytest.approx(0.5 * 100 + 0.5 * 120)
    assert ima.ses([3.0], [4.0], [1.0, 1.0]) == pytest.approx(
        3 + 4 + math.sqrt((0.6 * 2) ** 2 + 0.64 * 2))
    assert ima.capital_ca(100, 10, 80, 12, 1.5) == pytest.approx(132.0)
    assert ima.pla_surcharge(50, 200, 300, 200) == pytest.approx(0.125 * 100)
    assert ima.aggregate_capital(200, 12.5, 50, 400, 300) == pytest.approx(262.5)


@pytest.mark.parametrize(("n", "zone"), [(0, "GREEN"), (4, "GREEN"), (5, "AMBER"), (9, "AMBER"),
                                         (10, "RED"), (14, "RED")])
def test_backtesting_zone(n: int, zone: str) -> None:
    assert ima.backtesting_zone(n) == zone


@pytest.mark.parametrize(("sp", "ks", "zone"), [(0.85, 0.05, "GREEN"), (0.80, 0.05, "AMBER"),
                                                (0.75, 0.10, "AMBER"), (0.69, 0.05, "RED"),
                                                (0.90, 0.13, "RED")])
def test_pla_zone(sp: float, ks: float, zone: str) -> None:
    assert ima.pla_zone(sp, ks) == zone


def test_desk_backtesting_limits() -> None:
    assert not ima.desk_fails_backtesting(12, 30)
    assert ima.desk_fails_backtesting(13, 0)
    assert ima.desk_fails_backtesting(0, 31)


# =========================================================================
#  MAR40 simplified standardised approach (comparison only)
# =========================================================================


def test_ssa_scaling_and_not_permitted() -> None:
    assert p.SSA_SCALING_FACTORS == {"IRR": 1.30, "EQ": 3.50, "COMM": 1.90, "FX": 1.20}
    res = CALC.simplified_standardised_approach(
        fx_net_by_currency={"JPY": 50, "EUR": 100, "GBP": 150, "CAD": -20, "USD": -180},
        gold_net=-35,
    )
    assert res.permitted_under_car is False
    assert res.fx == pytest.approx(26.8)  # MAR40.61 Table 9 example
    assert res.scaled_total == pytest.approx(26.8 * 1.2)
    assert res.rwa == pytest.approx(12.5 * 26.8 * 1.2)


@pytest.mark.parametrize(("cat", "rating", "mat", "rate"), [
    (ssa.SSAIssuerCategory.GOVERNMENT, R.AAA_TO_AA_MINUS, 5, 0.0),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.A_PLUS_TO_A_MINUS, 0.5, 0.0025),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, 1.5, 0.01),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, 3, 0.016),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.B_PLUS_TO_B_MINUS, 3, 0.08),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BELOW_B_MINUS, 3, 0.12),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.UNRATED, 3, 0.08),
    (ssa.SSAIssuerCategory.QUALIFYING, R.UNRATED, 2, 0.01),
    (ssa.SSAIssuerCategory.OTHER, R.A_PLUS_TO_A_MINUS, 10, 0.016),
    (ssa.SSAIssuerCategory.OTHER, R.BB_PLUS_TO_BB_MINUS, 3, 0.08),
    (ssa.SSAIssuerCategory.OTHER, R.B_PLUS_TO_B_MINUS, 3, 0.12),
    (ssa.SSAIssuerCategory.OTHER, R.UNRATED, 3, 0.08),
])
def test_ssa_specific_risk_table1(cat: ssa.SSAIssuerCategory, rating: RatingBucket, mat: float,
                                  rate: float) -> None:
    pos = ssa.SSAInterestRatePosition(issue_id="b", currency="CAD", is_long=True,
                                      market_value=100, residual_maturity_years=mat,
                                      issuer_category=cat, rating=rating)
    assert ssa.specific_risk_rate(pos) == pytest.approx(rate)


@pytest.mark.parametrize(("mat", "coupon", "rw", "zone"), [
    (1 / 24, 0.05, 0.0, 1), (0.2, 0.05, 0.002, 1), (0.75, 0.05, 0.007, 1), (1.5, 0.05, 0.0125, 2),
    (3.5, 0.05, 0.0225, 2), (4.5, 0.05, 0.0275, 3), (25, 0.05, 0.06, 3), (3.7, 0.01, 0.0275, 3),
    (11, 0.01, 0.06, 3), (15, 0.01, 0.08, 3), (25, 0.01, 0.125, 3), (1.95, 0.01, 0.0175, 2),
])
def test_ssa_table4_bands(mat: float, coupon: float, rw: float, zone: int) -> None:
    assert ssa.band_weight_and_zone(ssa.maturity_band(mat, coupon)) == (pytest.approx(rw), zone)


def test_ssa_vertical_disallowance_example() -> None:
    # MAR40.27: weighted longs 100, shorts 90 in a band -> vertical disallowance 9
    out = ssa.ladder_general_market_risk({4: (100.0, 90.0)})
    assert out["vertical"] == pytest.approx(9.0)
    assert out["net_position"] == pytest.approx(10.0)


def test_ssa_horizontal_disallowances() -> None:
    # zone 1 band long 10, zone 1 band short 4 -> within zone 1: 40% x 4; zone 3 short 3 ->
    # zone1 (+6) vs zone3 (-3): 100% x 3; net = 3
    out = ssa.ladder_general_market_risk({0: (10.0, 0.0), 2: (0.0, 4.0), 10: (0.0, 3.0)})
    assert out["horizontal_within"] == pytest.approx(1.6)
    assert out["horizontal_across"] == pytest.approx(3.0)
    assert out["net_position"] == pytest.approx(3.0)
    adj = ssa.ladder_general_market_risk({0: (5.0, 0.0), 5: (0.0, 2.0)})
    assert adj["horizontal_across"] == pytest.approx(0.8)


def test_ssa_equity_and_commodity() -> None:
    eq = [ssa.SSAEquityPosition(issue_id="A", national_market="CA", is_long=True,
                                market_value=100),
          ssa.SSAEquityPosition(issue_id="B", national_market="CA", is_long=False,
                                market_value=60),
          ssa.SSAEquityPosition(issue_id="TSX60", national_market="CA", is_long=True,
                                market_value=50, is_diversified_index=True)]
    assert ssa.equity_capital(eq) == pytest.approx(0.08 * 160 + 0.02 * 50 + 0.08 * 90)
    com = [ssa.SSACommodityPosition(commodity="WTI", is_long=True, market_value=100),
           ssa.SSACommodityPosition(commodity="WTI", is_long=False, market_value=40,
                                    maturity_years=2)]
    assert ssa.commodity_simplified(com) == pytest.approx(0.15 * 60 + 0.03 * 140)
    # ladder: band 0 long 100, band 4 short 40 -> carried 4 bands (0.6% x 100 each),
    # matched 40 -> 1.5% x 80; residual 60 x 15%
    assert ssa.commodity_ladder(com) == pytest.approx(4 * 0.006 * 100 + 0.015 * 80 + 0.15 * 60)


def test_ssa_options() -> None:
    put = ssa.SSAOptionSimplified(risk_class="EQ", hedged_with_underlying=True,
                                  underlying_market_value=1000, in_the_money_amount=100)
    assert ssa.option_simplified_capital(put) == pytest.approx(60.0)  # MAR40.76 example
    call = ssa.SSAOptionSimplified(risk_class="FX", hedged_with_underlying=False,
                                   underlying_market_value=1000, option_market_value=30)
    assert ssa.option_simplified_capital(call) == pytest.approx(30.0)
    with pytest.raises(ValueError):
        ssa.option_simplified_capital(ssa.SSAOptionSimplified(
            risk_class="IRR", hedged_with_underlying=False, underlying_market_value=1))
    g = ssa.delta_plus_gamma_vega([
        ssa.SSAOptionGreeks(risk_class="EQ", underlying_id="CA", gamma=-0.02,
                            underlying_value=1000, vega=2.0, implied_vol=0.2),
        ssa.SSAOptionGreeks(risk_class="EQ", underlying_id="US", gamma=0.05,
                            underlying_value=1000, vega=-1.0, implied_vol=0.3),
    ])
    assert g["EQ"]["gamma"] == pytest.approx(0.5 * 0.02 * 80 ** 2)
    assert g["EQ"]["vega"] == pytest.approx(2 * 0.25 * 0.2 + 1 * 0.25 * 0.3)
