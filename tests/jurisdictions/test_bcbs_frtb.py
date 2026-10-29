"""Tests for the BCBS market-risk (FRTB) package (src/jurisdictions/bcbs/frtb).

Every MAR21 / MAR22 / MAR23 / MAR32-33 / MAR40 table cell transcribed in
``params.py`` is asserted against the value read from the Basel Framework text
(parametrised), followed by hand-worked examples (single-bucket delta, two-bucket
aggregation with gamma, the alternative S_b specification, curvature, DRC netting,
CTP aggregation, RRAO), correlation-scenario selection, bucket-assignment edge cases
and protocol conformance.

References: Basel Framework MAR20-MAR23, MAR32-MAR33, MAR40.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.bcbs.frtb import BCBSFRTBOptions, BCBSMarketRisk, drc, ima, rrao, sbm, ssa
from src.jurisdictions.bcbs.frtb import buckets as bk
from src.jurisdictions.bcbs.frtb import params as p
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
    IMAParameters,
    MarketRiskCalculator,
    MarketRiskResult,
    RRAOCategory,
    RRAOPositionInput,
    SecAssetClass,
    SecTrancheClass,
)

R = RatingBucket
RC = FRTBRiskClass
M = FRTBMeasure
OPTS = p.DEFAULT_FRTB_OPTIONS
SQ2 = math.sqrt(2.0)


def sens(rc: RC, measure: M = M.DELTA, **kw: Any) -> FRTBSensitivity:
    """Build a sensitivity."""
    return FRTBSensitivity(risk_class=rc, measure=measure, **kw)


def girr(value: float, tenor: float, ccy: str = "USD", curve: str = "OIS",
         **kw: Any) -> FRTBSensitivity:
    """GIRR delta sensitivity."""
    return sens(RC.GIRR, value=value, currency=ccy, tenor_years=tenor, curve_name=curve, **kw)


def eq(value: float, issuer: str, bucket: int | None = None, measure: M = M.DELTA,
       **kw: Any) -> FRTBSensitivity:
    """Equity sensitivity pinned to a bucket via bucket_hint."""
    return sens(RC.EQUITY, measure, value=value, issuer=issuer,
                bucket_hint=None if bucket is None else str(bucket), **kw)


def dpos(pid: str, obligor: str, long: bool, notional: float, **kw: Any) -> DRCPositionInput:
    """DRC position."""
    kw.setdefault("market_value", notional if long else -notional)
    return DRCPositionInput(position_id=pid, obligor=obligor, is_long=long, notional=notional,
                            **kw)


# =========================================================================
#  Table transcription checks
# =========================================================================

GIRR_TABLE1 = [(0.25, 0.017), (0.5, 0.017), (1.0, 0.016), (2.0, 0.013), (3.0, 0.012),
               (5.0, 0.011), (10.0, 0.011), (15.0, 0.011), (20.0, 0.011), (30.0, 0.011)]


@pytest.mark.parametrize(("tenor", "rw"), GIRR_TABLE1)
def test_girr_table1(tenor: float, rw: float) -> None:
    """MAR21.42 Table 1."""
    assert p.GIRR_DELTA_RW[tenor] == rw


GIRR_TABLE2_ROWS = {
    0.25: (100.0, 97.0, 91.4, 81.1, 71.9, 56.6, 40.0, 40.0, 40.0, 40.0),
    0.5: (97.0, 100.0, 97.0, 91.4, 86.1, 76.3, 56.6, 41.9, 40.0, 40.0),
    1.0: (91.4, 97.0, 100.0, 97.0, 94.2, 88.7, 76.3, 65.7, 56.6, 41.9),
    2.0: (81.1, 91.4, 97.0, 100.0, 98.5, 95.6, 88.7, 82.3, 76.3, 65.7),
    3.0: (71.9, 86.1, 94.2, 98.5, 100.0, 98.0, 93.2, 88.7, 84.4, 76.3),
    5.0: (56.6, 76.3, 88.7, 95.6, 98.0, 100.0, 97.0, 94.2, 91.4, 86.1),
    10.0: (40.0, 56.6, 76.3, 88.7, 93.2, 97.0, 100.0, 98.5, 97.0, 94.2),
    15.0: (40.0, 41.9, 65.7, 82.3, 88.7, 94.2, 98.5, 100.0, 99.0, 97.0),
    20.0: (40.0, 40.0, 56.6, 76.3, 84.4, 91.4, 97.0, 99.0, 100.0, 98.5),
    30.0: (40.0, 40.0, 41.9, 65.7, 76.3, 86.1, 94.2, 97.0, 98.5, 100.0),
}


@pytest.mark.parametrize(("row", "col"), [(r, c) for r in p.GIRR_TENORS for c in p.GIRR_TENORS])
def test_girr_table2_every_cell(row: float, col: float) -> None:
    """MAR21.46 Table 2, all 100 cells, and symmetry."""
    expected = GIRR_TABLE2_ROWS[row][p.GIRR_TENORS.index(col)] / 100
    assert sbm.girr_tenor_rho(row, col) == pytest.approx(expected)
    assert sbm.girr_tenor_rho(row, col) == sbm.girr_tenor_rho(col, row)


def test_girr_scalars() -> None:
    """MAR21.43, 21.44 fn 283, 21.45, 21.47, 21.48, 21.49, 21.50."""
    assert p.GIRR_INFLATION_RW == p.GIRR_XCCY_BASIS_RW == 0.016
    assert {"EUR", "USD", "GBP", "AUD", "JPY", "SEK", "CAD"} == p.GIRR_SPECIFIED_CURRENCIES
    assert p.GIRR_SAME_TENOR_DIFF_CURVE_RHO == 0.999
    assert p.GIRR_DIFF_CURVE_FACTOR == 0.999
    assert p.GIRR_INFLATION_VS_YIELD_RHO == 0.40
    assert p.GIRR_XCCY_RHO == 0.0
    assert p.GIRR_GAMMA == 0.50


CSR_TABLE4 = [0.5, 1.0, 5.0, 3.0, 3.0, 2.0, 1.5, 2.5, 2.0, 4.0, 12.0, 7.0, 8.5, 5.5, 5.0,
              12.0, 1.5, 5.0]


@pytest.mark.parametrize(("bucket", "rw_pct"), list(enumerate(CSR_TABLE4, start=1)))
def test_csr_nonsec_table4(bucket: int, rw_pct: float) -> None:
    """MAR21.53 Table 4."""
    assert p.CSR_NONSEC_RW[bucket] == pytest.approx(rw_pct / 100)


CSR_TABLE5 = {
    1: {2: 75, 3: 10, 4: 20, 5: 25, 6: 20, 7: 15, 8: 10, 16: 0, 17: 45, 18: 45},
    2: {3: 5, 4: 15, 5: 20, 6: 15, 7: 10, 8: 10, 16: 0, 17: 45, 18: 45},
    3: {4: 5, 5: 15, 6: 20, 7: 5, 8: 20, 16: 0, 17: 45, 18: 45},
    4: {5: 20, 6: 25, 7: 5, 8: 5, 16: 0, 17: 45, 18: 45},
    5: {6: 25, 7: 5, 8: 15, 16: 0, 17: 45, 18: 45},
    6: {7: 5, 8: 20, 16: 0, 17: 45, 18: 45},
    7: {8: 5, 16: 0, 17: 45, 18: 45},
    8: {16: 0, 17: 45, 18: 45},
    16: {17: 0, 18: 0},
    17: {18: 75},
}


@pytest.mark.parametrize(("g", "h", "pct"),
                         [(g, h, v) for g, row in CSR_TABLE5.items() for h, v in row.items()])
def test_csr_table5_every_cell(g: int, h: int, pct: float) -> None:
    """MAR21.57 Table 5 (gamma_sector), symmetric."""
    assert p.CSR_GAMMA_SECTOR[(g, h)] == pytest.approx(pct / 100)
    assert p.CSR_GAMMA_SECTOR[(h, g)] == pytest.approx(pct / 100)


@pytest.mark.parametrize(("b", "c", "expected"), [
    (1, 9, 0.50),            # same sector, different rating
    (3, 12, 0.5 * 0.05),     # rating x sector (3/11 vs 4/12)
    (3, 4, 0.05),            # same rating
    (1, 16, 0.0),
    (17, 18, 0.75),
    (9, 17, 0.45),           # rating factor 1 outside 1-15
    (8, 15, 0.5 * 0.05),     # covered bond vs HY health care
    (5, 13, 0.50),
])
def test_csr_gamma(b: int, c: int, expected: float) -> None:
    """MAR21.57: gamma = gamma_rating x gamma_sector."""
    assert sbm.csr_gamma(b, c) == pytest.approx(expected)


CTP_TABLE6 = [4, 4, 8, 5, 4, 3, 2, 6, 13, 13, 16, 10, 12, 12, 12, 13]


@pytest.mark.parametrize(("bucket", "pct"), list(enumerate(CTP_TABLE6, start=1)))
def test_ctp_table6(bucket: int, pct: float) -> None:
    """MAR21.59 Table 6."""
    assert p.CSR_CTP_RW[bucket] == pytest.approx(pct / 100)


SEC_TABLE8 = [0.9, 1.5, 2.0, 2.0, 0.8, 1.2, 1.2, 1.4]


@pytest.mark.parametrize(("bucket", "pct"), list(enumerate(SEC_TABLE8, start=1)))
def test_sec_nonctp_rw_all_blocks(bucket: int, pct: float) -> None:
    """MAR21.64 Table 8, MAR21.65 (x1.25), MAR21.66 (x1.75)."""
    assert p.CSR_SEC_NONCTP_RW[bucket] == pytest.approx(pct / 100)
    assert p.CSR_SEC_NONCTP_RW[bucket + 8] == pytest.approx(1.25 * pct / 100)
    assert p.CSR_SEC_NONCTP_RW[bucket + 16] == pytest.approx(1.75 * pct / 100)


def test_sec_examples_and_bucket25() -> None:
    """MAR21.65-21.67 worked numbers and bucket 25; MAR21.68 correlations; MAR21.70."""
    assert p.CSR_SEC_NONCTP_RW[9] == pytest.approx(0.01125)
    assert p.CSR_SEC_NONCTP_RW[17] == pytest.approx(0.01575)
    assert p.CSR_SEC_NONCTP_RW[25] == 0.035
    assert len(p.CSR_SEC_NONCTP_RW) == 25
    assert (p.SEC_RHO_TRANCHE_DIFF, p.SEC_RHO_TENOR_DIFF, p.SEC_RHO_BASIS_DIFF) == (
        0.40, 0.80, 0.999)
    assert p.SEC_GAMMA == 0.0


EQ_TABLE10 = [(1, 55), (2, 60), (3, 45), (4, 55), (5, 30), (6, 35), (7, 40), (8, 50),
              (9, 70), (10, 50), (11, 70), (12, 15), (13, 25)]


@pytest.mark.parametrize(("bucket", "pct"), EQ_TABLE10)
def test_equity_table10(bucket: int, pct: float) -> None:
    """MAR21.77 Table 10: spot RW and repo RW (= spot / 100)."""
    assert p.EQUITY_SPOT_RW[bucket] == pytest.approx(pct / 100)
    assert p.EQUITY_REPO_RW[bucket] == pytest.approx(pct / 10000)


@pytest.mark.parametrize(("bucket", "rho"), [(1, .15), (4, .15), (5, .25), (8, .25), (9, .075),
                                             (10, .125), (12, .80), (13, .80)])
def test_equity_intra_rho(bucket: int, rho: float) -> None:
    """MAR21.78(2)."""
    assert p.EQUITY_INTRA_RHO[bucket] == rho


@pytest.mark.parametrize(("b", "c", "g"), [(1, 10, .15), (3, 7, .15), (11, 5, 0.0), (11, 12, 0.0),
                                           (12, 13, .75), (1, 12, .45), (10, 13, .45)])
def test_equity_gamma(b: int, c: int, g: float) -> None:
    """MAR21.80."""
    assert sbm.equity_gamma(b, c) == g


CMDTY_TABLE = [(1, 30, 55), (2, 35, 95), (3, 60, 40), (4, 80, 80), (5, 40, 60), (6, 45, 65),
               (7, 20, 55), (8, 35, 45), (9, 25, 15), (10, 35, 40), (11, 50, 15)]


@pytest.mark.parametrize(("bucket", "rw", "rho"), CMDTY_TABLE)
def test_commodity_tables_11_12(bucket: int, rw: float, rho: float) -> None:
    """MAR21.82 Table 11 and MAR21.83 Table 12."""
    assert p.COMMODITY_RW[bucket] == pytest.approx(rw / 100)
    assert p.COMMODITY_RHO_CTY[bucket] == pytest.approx(rho / 100)


def test_commodity_fx_scalars() -> None:
    """MAR21.83(2)-(3), 21.85, 21.87, 21.88 fn 293, 21.89."""
    assert p.COMMODITY_RHO_TENOR_DIFF == 0.99
    assert p.COMMODITY_RHO_BASIS_DIFF == 0.999
    assert sbm.gamma(RC.COMMODITY, "1", "10") == 0.20
    assert sbm.gamma(RC.COMMODITY, "11", "3") == 0.0
    assert p.FX_RW == 0.15
    assert len(p.FX_SPECIFIED_PAIRS) == 19
    assert p.FX_GAMMA == 0.60
    assert p.COMMODITY_TENORS == (0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0)


@pytest.mark.parametrize(("key", "lh", "rw"), [
    ("GIRR", 60, 1.0), ("CSR_NONSEC", 120, 1.0), ("CSR_SEC_CTP", 120, 1.0),
    ("CSR_SEC_NONCTP", 120, 1.0), ("EQUITY_LARGE_CAP_INDEX", 20, 0.7778),
    ("EQUITY_SMALL_CAP_OTHER", 60, 1.0), ("COMMODITY", 120, 1.0), ("FX", 40, 1.0)])
def test_vega_table13(key: str, lh: int, rw: float) -> None:
    """MAR21.92 Table 13 (and consistency with RW_sigma x sqrt(LH/10) capped at 100%)."""
    assert p.VEGA_LIQUIDITY_HORIZON[key] == lh
    assert p.VEGA_RW[key] == rw
    assert min(p.VEGA_RW_SIGMA * math.sqrt(lh / 10), 1.0) == pytest.approx(rw, abs=1e-4)


DRC_TABLE2 = [("AAA", .005), ("AA", .02), ("A", .03), ("BBB", .06), ("BB", .15), ("B", .30),
              ("CCC", .50), ("UNRATED", .15), ("DEFAULTED", 1.0)]


@pytest.mark.parametrize(("cat", "rw"), DRC_TABLE2)
def test_drc_table2(cat: str, rw: float) -> None:
    """MAR22.24 Table 2."""
    assert p.DRC_RW_TABLE2[cat] == rw


@pytest.mark.parametrize(("sen", "lgd"), [(DRCSeniority.EQUITY, 1.0),
                                          (DRCSeniority.NON_SENIOR, 1.0),
                                          (DRCSeniority.SENIOR, 0.75),
                                          (DRCSeniority.COVERED_BOND, 0.25)])
def test_drc_lgd(sen: DRCSeniority, lgd: float) -> None:
    """MAR22.12."""
    assert p.DRC_LGD[sen] == lgd


def test_rrao_and_scenario_constants() -> None:
    """MAR23.8(2), MAR21.6, MAR20.1."""
    assert (p.RRAO_EXOTIC_RW, p.RRAO_OTHER_RW) == (0.01, 0.001)
    assert p.HIGH_CORRELATION_MULTIPLIER == 1.25
    assert p.LOW_CORRELATION_FLOOR_FACTOR == 0.75
    assert p.RWA_MULTIPLIER == 12.5


BT_TABLE1 = [(0, 1.5), (4, 1.5), (5, 1.70), (6, 1.76), (7, 1.83), (8, 1.88), (9, 1.92),
             (10, 2.0), (25, 2.0)]


@pytest.mark.parametrize(("exc", "mult"), BT_TABLE1)
def test_backtesting_table1(exc: int, mult: float) -> None:
    """MAR32.9 Table 1."""
    assert ima.backtesting_multiplier(exc) == pytest.approx(mult)


LH_TABLE2 = [("IR_SPECIFIED_CURRENCIES", 10), ("IR_UNSPECIFIED_CURRENCIES", 20),
             ("IR_VOLATILITY", 60), ("IR_OTHER", 60), ("CS_SOVEREIGN_IG", 20),
             ("CS_SOVEREIGN_HY", 40), ("CS_CORPORATE_IG", 40), ("CS_CORPORATE_HY", 60),
             ("CS_VOLATILITY", 120), ("CS_OTHER", 120), ("EQ_LARGE_CAP", 10),
             ("EQ_SMALL_CAP", 20), ("EQ_LARGE_CAP_VOLATILITY", 20),
             ("EQ_SMALL_CAP_VOLATILITY", 60), ("EQ_OTHER", 60), ("FX_SPECIFIED_PAIRS", 10),
             ("FX_PAIRS", 20), ("FX_VOLATILITY", 40), ("FX_OTHER", 40),
             ("CMDTY_ENERGY_CARBON", 20), ("CMDTY_PRECIOUS_NONFERROUS", 20), ("CMDTY_OTHER", 60),
             ("CMDTY_ENERGY_CARBON_VOLATILITY", 60), ("CMDTY_PRECIOUS_NONFERROUS_VOLATILITY", 60),
             ("CMDTY_OTHER_VOLATILITY", 120), ("CMDTY_OTHER_TYPES", 120)]


@pytest.mark.parametrize(("cat", "days"), LH_TABLE2)
def test_ima_liquidity_horizons(cat: str, days: int) -> None:
    """MAR33.12 Table 2."""
    assert p.IMA_LIQUIDITY_HORIZONS[cat] == days


def test_ima_parameters_object() -> None:
    """MAR33.3, 33.15, 33.17, 33.42, MAR32.42 Table 2."""
    ip = BCBSMarketRisk().ima_parameters()
    assert isinstance(ip, IMAParameters)
    assert ip.jurisdiction is Jurisdiction.BCBS
    assert ip.es_confidence == 0.975
    assert ip.multiplier_base == 1.5
    assert ip.imcc_rho == 0.5
    assert ip.ses_rho == 0.6
    assert ip.pla_spearman_thresholds == (0.80, 0.70)
    assert ip.pla_ks_thresholds == (0.09, 0.12)
    assert ip.backtesting_addons[5] == pytest.approx(0.20)
    assert ip.backtesting_addons[10] == pytest.approx(0.50)
    assert len(ip.liquidity_horizons_days) == 26
    assert p.IMA_LH_BUCKETS == (10, 20, 40, 60, 120)


@pytest.mark.parametrize(("low_coupon", "idx", "rw", "dy"), [
    (False, 0, 0.0, 1.0), (False, 3, 0.007, 1.0), (False, 4, 0.0125, 0.9),
    (False, 8, 0.0325, 0.7), (False, 12, 0.06, 0.6), (True, 13, 0.08, 0.6), (True, 14, 0.125, 0.6),
])
def test_mar40_table4(low_coupon: bool, idx: int, rw: float, dy: float) -> None:
    """MAR40.26 Table 4."""
    assert ssa.band_weight(idx) == rw
    if idx < 13:
        assert p.SSA_MATURITY_BANDS[idx][3] == dy


def test_mar40_scalars() -> None:
    """MAR40.2, 40.27, 40.28 Table 5, 40.43, 40.47, 40.61, 40.69-40.73."""
    assert p.SSA_SCALING == {"IRR": 1.30, "EQ": 3.50, "COMM": 1.90, "FX": 1.20}
    assert p.SSA_VERTICAL_DISALLOWANCE == 0.10
    assert p.SSA_HORIZONTAL_WITHIN_ZONE == {1: 0.40, 2: 0.30, 3: 0.30}
    assert (p.SSA_HORIZONTAL_ADJACENT, p.SSA_HORIZONTAL_ZONE1_ZONE3) == (0.40, 1.00)
    assert (p.SSA_EQUITY_SPECIFIC, p.SSA_EQUITY_GENERAL, p.SSA_EQUITY_INDEX_ADDON) == (
        0.08, 0.08, 0.02)
    assert p.SSA_FX_CHARGE == 0.08
    assert (p.SSA_COMMODITY_SPREAD_RATE, p.SSA_COMMODITY_CARRY_RATE,
            p.SSA_COMMODITY_OUTRIGHT) == (0.015, 0.006, 0.15)
    assert (p.SSA_COMMODITY_SIMPLIFIED_NET, p.SSA_COMMODITY_SIMPLIFIED_GROSS) == (0.15, 0.03)


# =========================================================================
#  Bucket assignment and risk weights
# =========================================================================


@pytest.mark.parametrize(("kw", "bucket"), [
    ({"credit_sector": CreditSector.SOVEREIGN, "rating": R.AAA_TO_AA_MINUS}, 1),
    ({"credit_sector": CreditSector.SOVEREIGN, "rating": R.BB_PLUS_TO_BB_MINUS}, 9),
    ({"credit_sector": CreditSector.FINANCIAL, "rating": R.UNRATED}, 11),     # NR -> HY block
    ({"credit_sector": CreditSector.FINANCIAL, "is_investment_grade": True}, 3),
    ({"credit_sector": CreditSector.HEALTH_CARE, "rating": R.BBB_PLUS_TO_BBB_MINUS}, 7),
    ({"credit_sector": CreditSector.COVERED_BOND, "rating": R.A_PLUS_TO_A_MINUS}, 8),
    ({"credit_sector": CreditSector.COVERED_BOND, "rating": R.BB_PLUS_TO_BB_MINUS}, 16),
    ({"credit_sector": None}, 16),
    ({"credit_sector": CreditSector.OTHER, "rating": R.AAA_TO_AA_MINUS}, 16),
    ({"credit_sector": CreditSector.INDEX, "rating": R.A_PLUS_TO_A_MINUS}, 17),
    ({"credit_sector": CreditSector.INDEX, "rating": R.B_PLUS_TO_B_MINUS}, 18),
    ({"credit_sector": CreditSector.SOVEREIGN, "bucket_hint": "15"}, 15),
])
def test_csr_nonsec_bucket_assignment(kw: dict[str, Any], bucket: int) -> None:
    """MAR21.51 Table 3, MAR21.52(2), MAR21.33(2)(b)."""
    s = sens(RC.CSR_NONSEC, value=1, issuer="X", tenor_years=1.0, **kw)
    assert bk.csr_nonsec_bucket(s) == bucket
    assert BCBSMarketRisk().assign_bucket(s) == str(bucket)


def test_covered_bond_aa_reduction() -> None:
    """MAR21.53 footnote 288 (bank discretion)."""
    s = sens(RC.CSR_NONSEC, value=1, credit_sector=CreditSector.COVERED_BOND,
             rating=R.AAA_TO_AA_MINUS, tenor_years=1.0)
    assert bk.csr_nonsec_rw(s, OPTS) == 0.015
    assert bk.csr_nonsec_rw(s, BCBSFRTBOptions(covered_bond_aa_reduction=False)) == 0.025


def test_ctp_bucket_rules() -> None:
    """MAR21.58(1) and FAQ: no index buckets; index CTP -> 16 absent a 75% sector."""
    idx = sens(RC.CSR_SEC_CTP, value=1, credit_sector=CreditSector.INDEX,
               rating=R.A_PLUS_TO_A_MINUS)
    assert bk.csr_ctp_bucket(idx) == 16
    fin = sens(RC.CSR_SEC_CTP, value=1, credit_sector=CreditSector.FINANCIAL, rating=R.UNRATED)
    assert bk.csr_ctp_bucket(fin) == 11
    with pytest.raises(ValueError):
        bk.csr_ctp_bucket(sens(RC.CSR_SEC_CTP, value=1, bucket_hint="17"))


@pytest.mark.parametrize(("tranche", "asset", "bucket"), [
    (SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_PRIME, 1),
    (SecTrancheClass.SENIOR_IG, SecAssetClass.CLO_NON_CTP, 8),
    (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.CMBS, 12),
    (SecTrancheClass.HY_NR, SecAssetClass.ABS_AUTO, 23),
    (SecTrancheClass.HY_NR, SecAssetClass.OTHER, 25),
    (None, SecAssetClass.CMBS, 25),
])
def test_sec_nonctp_bucket(tranche: SecTrancheClass | None, asset: SecAssetClass,
                           bucket: int) -> None:
    """MAR21.62 Table 7, MAR21.63(2)."""
    s = sens(RC.CSR_SEC_NONCTP, value=1, sec_tranche_class=tranche, sec_asset_class=asset)
    assert bk.csr_sec_nonctp_bucket(s) == bucket


@pytest.mark.parametrize(("kw", "bucket"), [
    ({"is_large_cap": True, "is_advanced_economy": False,
      "equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES}, 1),
    ({"is_large_cap": True, "is_advanced_economy": False,
      "equity_sector": EquitySector.FINANCIALS_REALESTATE_TECH}, 4),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.TELECOM_INDUSTRIALS}, 6),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, 7),
    ({"is_large_cap": False, "is_advanced_economy": False,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, 9),
    ({"is_large_cap": False, "is_advanced_economy": True,
      "equity_sector": EquitySector.TELECOM_INDUSTRIALS}, 10),
    ({"is_large_cap": True, "is_advanced_economy": True, "equity_sector": EquitySector.OTHER}, 11),
    ({"is_large_cap": None, "is_advanced_economy": True,
      "equity_sector": EquitySector.TELECOM_INDUSTRIALS}, 11),
    ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": True}, 12),
    ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": False}, 13),
])
def test_equity_bucket(kw: dict[str, Any], bucket: int) -> None:
    """MAR21.72 Table 9, MAR21.33(2)(a), MAR21.76(2)."""
    assert bk.equity_bucket(sens(RC.EQUITY, value=1, issuer="E", **kw)) == bucket


CMDTY_GROUPS = [*p.COMMODITY_GROUP_TO_BUCKET.items(), (None, 11)]


@pytest.mark.parametrize(("group", "bucket"), CMDTY_GROUPS)
def test_commodity_bucket(group: CommodityGroup | None, bucket: int) -> None:
    """MAR21.82 Table 11."""
    s = sens(RC.COMMODITY, value=1, commodity_group=group, commodity_name="c", tenor_years=0.0)
    assert bk.commodity_bucket(s) == bucket


def test_girr_rw_specified_and_unspecified() -> None:
    """MAR21.42-21.44: sqrt(2) for specified and reporting currencies only (Table 1)."""
    assert bk.girr_delta_rw(girr(1, 0.25, "USD"), OPTS) == pytest.approx(0.017 / SQ2)
    assert bk.girr_delta_rw(girr(1, 0.25, "BRL"), OPTS) == pytest.approx(0.017)
    rep_brl = BCBSFRTBOptions(reporting_currency="BRL")
    assert bk.girr_delta_rw(girr(1, 0.25, "BRL"), rep_brl) == pytest.approx(0.017 / SQ2)
    assert bk.girr_delta_rw(girr(1, 10, "USD"), BCBSFRTBOptions(
        girr_specified_currency_sqrt2=False)) == pytest.approx(0.011)
    infl = girr(1, 0.25, girr_curve=GIRRCurve.INFLATION)
    assert bk.girr_delta_rw(infl, OPTS) == 0.016  # TODO: VERIFY placeholder (no sqrt 2)


def test_girr_off_grid_tenor_rejected() -> None:
    """MAR21.8 FAQ2: sensitivities must sit on prescribed tenors."""
    with pytest.raises(ValueError):
        bk.girr_delta_rw(girr(1, 7.0), OPTS)


@pytest.mark.parametrize(("rep", "ccy", "liquid"), [
    ("USD", "EUR", True), ("USD", "ARS", False), ("EUR", "AUD", True), ("EUR", "ARS", False),
    ("USD", "USD", False),
])
def test_fx_liquid_pairs(rep: str, ccy: str, liquid: bool) -> None:
    """MAR21.88 footnotes 293-294 (first-order crosses)."""
    o = BCBSFRTBOptions(reporting_currency=rep)
    s = sens(RC.FX, value=1, fx_currency=ccy)
    assert bk.fx_is_liquid(s, o) is liquid
    assert bk.fx_delta_rw(s, o) == pytest.approx(0.15 / SQ2 if liquid else 0.15)


def test_fx_liquid_override() -> None:
    """``fx_pair_is_liquid`` overrides the inferred status."""
    s = sens(RC.FX, value=1, fx_currency="ARS", fx_pair_is_liquid=True)
    assert bk.fx_delta_rw(s, OPTS) == pytest.approx(0.15 / SQ2)


def test_vega_rw_equity_split() -> None:
    """MAR21.92 Table 13 FAQ: 77.78% for buckets 1-8, 12, 13; 100% for 9-11."""
    assert bk.vega_risk_weight(eq(1, "A", 5, M.VEGA, option_maturity_years=1.0)) == 0.7778
    assert bk.vega_risk_weight(eq(1, "A", 13, M.VEGA, option_maturity_years=1.0)) == 0.7778
    assert bk.vega_risk_weight(eq(1, "A", 9, M.VEGA, option_maturity_years=1.0)) == 1.0
    assert bk.vega_risk_weight(eq(1, "A", 11, M.VEGA, option_maturity_years=1.0)) == 1.0


def test_curvature_risk_weight() -> None:
    """MAR21.98-21.99: relative delta RW (FX, equity); highest bucket RW (GIRR)."""
    calc = BCBSMarketRisk()
    s = eq(0, "A", 5, M.CURVATURE)
    assert calc.risk_weight(s) == 0.30
    g = sens(RC.GIRR, M.CURVATURE, currency="BRL")
    assert calc.risk_weight(g) == 0.017


def test_bad_bucket_hint() -> None:
    """Hints outside the MAR21 range are rejected."""
    with pytest.raises(ValueError):
        bk.equity_bucket(eq(1, "A", 14))
    with pytest.raises(ValueError):
        bk.equity_bucket(sens(RC.EQUITY, value=1, bucket_hint="x"))


# =========================================================================
#  Hand-worked SBM examples
# =========================================================================


def test_single_bucket_girr_delta() -> None:
    """MAR21.4: two tenors on one curve, USD (sqrt 2), medium correlation 88.7% (Table 2)."""
    s = [girr(100, 1.0), girr(-50, 5.0)]
    ws1, ws2 = 100 * 0.016 / SQ2, -50 * 0.011 / SQ2
    k_med = math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * 0.887 * ws1 * ws2)
    res = {r.scenario: r for r in BCBSMarketRisk().sbm_scenarios(s)}
    assert res["MEDIUM"].by_class[RC.GIRR][0] == pytest.approx(k_med)
    rho_low = max(2 * 0.887 - 1, 0.75 * 0.887)
    k_low = math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * rho_low * ws1 * ws2)
    assert res["LOW"].by_class[RC.GIRR][0] == pytest.approx(k_low)
    out = BCBSMarketRisk().sbm_capital(s)
    assert out[0].scenario == "LOW" and out[0].delta == pytest.approx(k_low)


def test_girr_netting_and_curves() -> None:
    """MAR21.4(2) netting; MAR21.45 same tenor different curve 99.9%; MAR21.47."""
    s = [girr(10, 2.0, ccy="BRL"), girr(-10, 2.0, ccy="BRL")]
    assert BCBSMarketRisk().sbm_capital(s)[0].total == pytest.approx(0.0)
    s2 = [girr(10, 2.0, ccy="BRL", curve="OIS"), girr(-10, 2.0, ccy="BRL", curve="3M")]
    ws = 10 * 0.013
    expected = math.sqrt(2 * ws * ws - 2 * 0.999 * ws * ws)
    res = {r.scenario: r for r in sbm.sbm_scenarios(s2, OPTS)}
    assert res["MEDIUM"].by_class[RC.GIRR][0] == pytest.approx(expected)
    s3 = [girr(10, 2.0, ccy="BRL", curve="OIS"), girr(10, 5.0, ccy="BRL", curve="3M")]
    w1, w2 = 10 * 0.013, 10 * 0.011
    exp3 = math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.956 * 0.999 * w1 * w2)
    res3 = {r.scenario: r for r in sbm.sbm_scenarios(s3, OPTS)}
    assert res3["MEDIUM"].by_class[RC.GIRR][0] == pytest.approx(exp3)


def test_girr_inflation_xccy_correlations() -> None:
    """MAR21.48 (40%) and MAR21.49 (0%)."""
    y = girr(10, 1.0, ccy="BRL")
    i = sens(RC.GIRR, value=10, currency="BRL", girr_curve=GIRRCurve.INFLATION, curve_name="CPI")
    x = sens(RC.GIRR, value=10, currency="BRL", girr_curve=GIRRCurve.XCCY_BASIS, curve_name="USD")
    wy, wi = 10 * 0.016, 10 * 0.016
    res = {r.scenario: r for r in sbm.sbm_scenarios([y, i], OPTS)}
    assert res["MEDIUM"].by_class[RC.GIRR][0] == pytest.approx(
        math.sqrt(wy ** 2 + wi ** 2 + 2 * 0.4 * wy * wi))
    res2 = {r.scenario: r for r in sbm.sbm_scenarios([y, x], OPTS)}
    assert res2["MEDIUM"].by_class[RC.GIRR][0] == pytest.approx(math.sqrt(2) * wy)


def test_two_bucket_csr_with_gamma() -> None:
    """MAR21.4(5) and MAR21.57: IG financial (bucket 3) vs HY basic materials (bucket 12)."""
    a = sens(RC.CSR_NONSEC, value=100, issuer="BANK", tenor_years=5.0,
             credit_sector=CreditSector.FINANCIAL, rating=R.A_PLUS_TO_A_MINUS)
    b = sens(RC.CSR_NONSEC, value=50, issuer="MINE", tenor_years=5.0,
             credit_sector=CreditSector.BASIC_MATERIALS, rating=R.BB_PLUS_TO_BB_MINUS)
    wa, wb = 100 * 0.05, 50 * 0.07
    gam = 0.5 * 0.05
    expected = math.sqrt(wa ** 2 + wb ** 2 + 2 * gam * wa * wb)
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.CSR_NONSEC][0] == pytest.approx(expected)
    exp_high = math.sqrt(wa ** 2 + wb ** 2 + 2 * 1.25 * gam * wa * wb)
    assert res["HIGH"].by_class[RC.CSR_NONSEC][0] == pytest.approx(exp_high)


def test_csr_within_bucket_name_tenor_basis() -> None:
    """MAR21.54: rho = 35% x 65% x 99.9% for different name, tenor and curve."""
    a = sens(RC.CSR_NONSEC, value=100, issuer="A", tenor_years=5.0,
             credit_sector=CreditSector.TECHNOLOGY, rating=R.A_PLUS_TO_A_MINUS)
    b = sens(RC.CSR_NONSEC, value=100, issuer="G", tenor_years=10.0, is_cds=True,
             credit_sector=CreditSector.TECHNOLOGY, rating=R.A_PLUS_TO_A_MINUS)
    w = 100 * 0.02
    rho = 0.35 * 0.65 * 0.999
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.CSR_NONSEC][0] == pytest.approx(
        math.sqrt(2 * w * w * (1 + rho)))


def test_ctp_basis_correlation() -> None:
    """MAR21.60: CTP rho_basis 99%."""
    a = sens(RC.CSR_SEC_CTP, value=10, issuer="A", tenor_years=5.0, bucket_hint="3")
    b = sens(RC.CSR_SEC_CTP, value=-10, issuer="A", tenor_years=5.0, is_cds=True, bucket_hint="3")
    w = 10 * 0.08
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.CSR_SEC_CTP][0] == pytest.approx(
        math.sqrt(2 * w * w * (1 - 0.99)))


def test_other_sector_simple_sum_and_sec_bucket25() -> None:
    """MAR21.56(1), 21.79(1): sum |WS|; MAR21.71: bucket 25 outside the root."""
    a = sens(RC.CSR_NONSEC, value=10, issuer="A", tenor_years=1.0)
    b = sens(RC.CSR_NONSEC, value=-10, issuer="B", tenor_years=1.0)
    out = BCBSMarketRisk().sbm_capital([a, b])
    assert out[0].delta == pytest.approx(2 * 10 * 0.12)
    s1 = sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T1", tenor_years=1.0,
              sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.CMBS)
    s2 = sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T2", tenor_years=1.0,
              sec_tranche_class=SecTrancheClass.HY_NR, sec_asset_class=SecAssetClass.CMBS)
    s3 = sens(RC.CSR_SEC_NONCTP, value=-100, tranche_id="T3", tenor_years=1.0)
    w1, w2, w3 = 100 * 0.02, 100 * 0.02 * 1.75, 100 * 0.035
    out2 = BCBSMarketRisk().sbm_capital([s1, s2, s3])
    assert out2[0].delta == pytest.approx(math.sqrt(w1 ** 2 + w2 ** 2) + w3)


def test_equity_spot_repo_correlations() -> None:
    """MAR21.78(1) same issuer 99.9%; MAR21.78(4) different issuers rho x 99.9%."""
    spot = eq(100, "A", 5)
    repo = eq(1000, "A", 5, equity_risk_factor=EquityRiskFactor.REPO)
    ws, wr = 100 * 0.30, 1000 * 0.003
    res = {r.scenario: r for r in sbm.sbm_scenarios([spot, repo], OPTS)}
    assert res["MEDIUM"].by_class[RC.EQUITY][0] == pytest.approx(
        math.sqrt(ws ** 2 + wr ** 2 + 2 * 0.999 * ws * wr))
    repo_b = eq(1000, "B", 5, equity_risk_factor=EquityRiskFactor.REPO)
    res2 = {r.scenario: r for r in sbm.sbm_scenarios([spot, repo_b], OPTS)}
    assert res2["MEDIUM"].by_class[RC.EQUITY][0] == pytest.approx(
        math.sqrt(ws ** 2 + wr ** 2 + 2 * 0.25 * 0.999 * ws * wr))


def test_commodity_correlation() -> None:
    """MAR21.83 footnote 292 style: distinct commodity, tenor and location."""
    a = sens(RC.COMMODITY, value=10, commodity_name="BRENT", tenor_years=1.0,
             delivery_location="LE HAVRE", commodity_group=CommodityGroup.ENERGY_LIQUID)
    b = sens(RC.COMMODITY, value=10, commodity_name="WTI", tenor_years=5.0,
             delivery_location="OKLAHOMA", commodity_group=CommodityGroup.ENERGY_LIQUID)
    w = 10 * 0.35
    rho = 0.95 * 0.99 * 0.999
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.COMMODITY][0] == pytest.approx(
        math.sqrt(2 * w * w * (1 + rho)))


def test_fx_two_buckets() -> None:
    """MAR21.86-21.89: |WS| per bucket, gamma 60%."""
    a = sens(RC.FX, value=100, fx_currency="EUR")
    b = sens(RC.FX, value=-100, fx_currency="ARS")
    wa, wb = 100 * 0.15 / SQ2, -100 * 0.15
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.FX][0] == pytest.approx(
        math.sqrt(wa ** 2 + wb ** 2 + 2 * 0.6 * wa * wb))


def test_alternative_sb_specification() -> None:
    """MAR21.4(5)(b): S_b = max(min(sum WS, K_b), -K_b) when the sum is negative."""
    k = [math.sqrt(77.0), math.sqrt(77.0)]
    s = [20.0, -20.0]
    raw = 77 + 77 + 2 * 0.2 * 20 * -20
    assert raw < 0
    alt = 77 + 77 + 2 * 0.2 * math.sqrt(77) * -math.sqrt(77)
    assert sbm.across_buckets(k, s, lambda i, j: 0.2) == pytest.approx(math.sqrt(alt))
    # no alternative needed when the sum is positive
    assert sbm.across_buckets([3.0, 4.0], [3.0, 4.0], lambda i, j: 0.5) == pytest.approx(
        math.sqrt(9 + 16 + 2 * 0.5 * 12))


def test_vega_girr_correlation() -> None:
    """MAR21.93: rho = min(exp(-1% |dT|/min T) x exp(-1% |dTu|/min Tu), 1)."""
    a = sens(RC.GIRR, M.VEGA, value=10, currency="USD", option_maturity_years=1.0,
             underlying_maturity_years=5.0)
    b = sens(RC.GIRR, M.VEGA, value=10, currency="USD", option_maturity_years=5.0,
             underlying_maturity_years=10.0)
    rho = math.exp(-0.01 * 4 / 1) * math.exp(-0.01 * 5 / 5)
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.GIRR][1] == pytest.approx(math.sqrt(200 * (1 + rho)))


def test_vega_equity_correlation() -> None:
    """MAR21.94: rho = min(rho_delta x rho_option maturity, 1)."""
    a = eq(10, "A", 5, M.VEGA, option_maturity_years=1.0)
    b = eq(10, "B", 5, M.VEGA, option_maturity_years=3.0)
    w = 10 * 0.7778
    rho = 0.25 * math.exp(-0.01 * 2 / 1)
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.EQUITY][1] == pytest.approx(math.sqrt(2 * w * w * (1 + rho)))


def test_curvature_single_bucket() -> None:
    """MAR21.5(3): K_b+/- with psi, rho = delta rho squared (MAR21.100)."""
    a = eq(0, "A", 5, M.CURVATURE, cvr_up=10.0, cvr_down=-5.0)
    b = eq(0, "B", 5, M.CURVATURE, cvr_up=6.0, cvr_down=-2.0)
    rho = 0.25 ** 2
    kp = math.sqrt(100 + 36 + 2 * rho * 60)
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.EQUITY][2] == pytest.approx(kp)
    # downward scenario: both CVR- negative -> psi = 0, max(CVR, 0) = 0 -> K- = 0 < K+
    k, s, up = sbm.curvature_bucket([10.0, 6.0], [-5.0, -2.0], lambda i, j: rho)
    assert up and s == 16.0 and k == pytest.approx(kp)


def test_curvature_tie_rule_and_psi() -> None:
    """MAR21.5(3)(a)(iii): tie -> upward if sum CVR+ > sum CVR-; psi zero when both negative."""
    k, s, up = sbm.curvature_bucket([5.0, -1.0], [5.0, -3.0], lambda i, j: 0.0)
    assert k == pytest.approx(5.0) and up and s == 4.0
    k2, s2, up2 = sbm.curvature_bucket([5.0, -3.0], [5.0, -1.0], lambda i, j: 0.0)
    assert not up2 and s2 == 4.0
    assert sbm.curvature_across([3.0, 4.0], [-3.0, -4.0], lambda i, j: 0.5) == pytest.approx(5.0)
    assert sbm.curvature_across([3.0, 4.0], [3.0, -4.0], lambda i, j: 0.5) == pytest.approx(
        math.sqrt(25 - 12))


def test_curvature_other_bucket() -> None:
    """MAR21.79(2): K = max(sum max(CVR+,0), sum max(CVR-,0))."""
    a = eq(0, "A", 11, M.CURVATURE, cvr_up=4.0, cvr_down=-1.0)
    b = eq(0, "B", 11, M.CURVATURE, cvr_up=-2.0, cvr_down=3.0)
    out = BCBSMarketRisk().sbm_capital([a, b])
    assert out[0].curvature == pytest.approx(4.0)


def test_curvature_two_buckets_gamma_squared() -> None:
    """MAR21.101: gamma_curv = gamma^2 (GIRR 0.5^2 = 0.25)."""
    a = sens(RC.GIRR, M.CURVATURE, currency="USD", cvr_up=10.0, cvr_down=-20.0)
    b = sens(RC.GIRR, M.CURVATURE, currency="EUR", cvr_up=8.0, cvr_down=-10.0)
    res = {r.scenario: r for r in sbm.sbm_scenarios([a, b], OPTS)}
    assert res["MEDIUM"].by_class[RC.GIRR][2] == pytest.approx(math.sqrt(100 + 64 + 2 * .25 * 80))


def test_fx_curvature_scalar() -> None:
    """MAR21.98: CVR / 1.5 for options not referencing the reporting currency."""
    a = sens(RC.FX, M.CURVATURE, fx_currency="EUR", cvr_up=15.0, cvr_down=-3.0,
             flags={sbm.FX_CURVATURE_FLAG: True})
    assert BCBSMarketRisk().sbm_capital([a])[0].curvature == pytest.approx(10.0)


def test_no_curvature_for_inflation_or_repo() -> None:
    """MAR21.8(5)(b), MAR21.12(3)(b)."""
    with pytest.raises(ValueError):
        sbm.sbm_scenarios([sens(RC.GIRR, M.CURVATURE, currency="USD", cvr_up=1, cvr_down=1,
                                girr_curve=GIRRCurve.INFLATION)], OPTS)
    with pytest.raises(ValueError):
        sbm.sbm_scenarios([eq(0, "A", 5, M.CURVATURE, cvr_up=1, cvr_down=1,
                              equity_risk_factor=EquityRiskFactor.REPO)], OPTS)


# =========================================================================
#  Scenario selection
# =========================================================================


@pytest.mark.parametrize(("rho", "low", "high"), [
    (0.5, 0.375, 0.625), (0.9, 0.8, 1.0), (0.999, 0.998, 1.0), (0.0, 0.0, 0.0),
    (0.15, 0.1125, 0.1875), (0.75, 0.5625, 0.9375),
])
def test_scenario_correlation(rho: float, low: float, high: float) -> None:
    """MAR21.6(2)-(3)."""
    assert sbm.scenario_correlation(rho, "LOW") == pytest.approx(low)
    assert sbm.scenario_correlation(rho, "MEDIUM") == rho
    assert sbm.scenario_correlation(rho, "HIGH") == pytest.approx(high)
    with pytest.raises(ValueError):
        sbm.scenario_correlation(rho, "EXTREME")


def test_high_scenario_binds_for_same_sign() -> None:
    """MAR21.7(2): all-long positions -> high correlations bind."""
    s = [eq(100, "A", 5), eq(100, "B", 5)]
    out = BCBSMarketRisk().sbm_capital(s)
    assert out[0].scenario == "HIGH"
    w = 30.0
    assert out[0].delta == pytest.approx(math.sqrt(2 * w * w * (1 + 0.3125)))


def test_scenario_is_portfolio_level() -> None:
    """MAR21.7(1)-(2): one scenario for the sum across risk classes."""
    s = [eq(100, "A", 5), eq(100, "B", 5), girr(100, 1.0), girr(-100, 5.0)]
    scen = BCBSMarketRisk().sbm_scenarios(s)
    best = max(scen, key=lambda r: r.total)
    out = BCBSMarketRisk().sbm_capital(s)
    assert {r.scenario for r in out} == {best.scenario}
    assert sum(r.total for r in out) == pytest.approx(best.total)


# =========================================================================
#  DRC
# =========================================================================


def test_gross_jtd_and_lgd() -> None:
    """MAR22.11-22.13: JTD long = max(LGD N + PnL, 0); short = min(-LGD N + PnL, 0)."""
    lg = dpos("1", "X", True, 100, pnl=-5)
    assert drc.gross_jtd(lg) == pytest.approx(70.0)
    sh = dpos("2", "X", False, 100, pnl=5, seniority=DRCSeniority.NON_SENIOR)
    assert drc.gross_jtd(sh) == pytest.approx(-95.0)
    cb = dpos("3", "X", True, 100, seniority=DRCSeniority.COVERED_BOND)
    assert drc.gross_jtd(cb) == pytest.approx(25.0)
    call = dpos("4", "X", True, 0, pnl=-2)
    assert drc.gross_jtd(call) == 0.0
    nolgd = dpos("5", "X", True, 100, flags={"lgd_not_linked_to_recovery": True})
    assert drc.gross_jtd(nolgd) == 100.0


@pytest.mark.parametrize(("m", "w"), [(0.0, 0.25), (1 / 12, 0.25), (0.25, 0.25), (0.5, 0.5),
                                      (1.0, 1.0), (7.0, 1.0)])
def test_maturity_weight(m: float, w: float) -> None:
    """MAR22.15, MAR22.18."""
    assert drc.maturity_weight(m) == pytest.approx(w)


def test_cash_equity_maturity() -> None:
    """MAR22.16 and FAQ: no maturity between three months and one year for cash equities."""
    with pytest.raises(ValueError):
        drc.nonsec_drc([dpos("e", "X", True, 10, seniority=DRCSeniority.EQUITY,
                             maturity_years=0.5, flags={"cash_equity": True})], OPTS)


def test_drc_netting_example() -> None:
    """MAR22.19-22.25 worked example.

    X (A, 3%): long senior bond N=100, P&L -5 -> 70; short equity N=40 -> -40 (junior,
    may offset the bond) -> net long 30. Y (BBB, 6%): short senior CDS N=20 -> -15.
    HBR = 30 / 45; DRC = 0.03 x 30 - (2/3) x 0.06 x 15 = 0.3.
    """
    pos = [
        dpos("b", "X", True, 100, pnl=-5, rating=R.A_PLUS_TO_A_MINUS),
        dpos("e", "X", False, 40, seniority=DRCSeniority.EQUITY, rating=R.A_PLUS_TO_A_MINUS),
        dpos("c", "Y", False, 20, rating=R.BBB_PLUS_TO_BBB_MINUS),
    ]
    out = BCBSMarketRisk().drc_capital(pos)
    assert out["nonsec"] == pytest.approx(0.3)
    assert out["total"] == pytest.approx(0.3)


def test_drc_seniority_blocks_offset() -> None:
    """MAR22.19(1): a short bond cannot offset a long equity of the same obligor."""
    pos = [dpos("e", "X", True, 100, seniority=DRCSeniority.EQUITY, rating=R.BB_PLUS_TO_BB_MINUS),
           dpos("b", "X", False, 100, rating=R.BB_PLUS_TO_BB_MINUS)]
    # long 100, short 75 not offset: HBR = 100/175; DRC = 15 - (100/175) x 0.15 x 75
    expected = 0.15 * 100 - (100 / 175) * 0.15 * 75
    assert drc.nonsec_drc(pos, OPTS) == pytest.approx(expected)


def test_drc_maturity_scaled_offset() -> None:
    """MAR22.19(3)(b): a 3-month short offsets only a quarter of its size against a 2y long."""
    pos = [dpos("l", "X", True, 100, maturity_years=2.0, rating=R.UNRATED),
           dpos("s", "X", False, 100, maturity_years=0.25, rating=R.UNRATED)]
    assert drc.nonsec_drc(pos, OPTS) == pytest.approx(0.15 * (75 - 75 / 4))


def test_drc_buckets_no_hedging_across() -> None:
    """MAR22.22, 22.26: sovereign long and corporate short do not hedge each other."""
    pos = [dpos("s", "GOV", True, 100, credit_sector=CreditSector.SOVEREIGN,
                rating=R.BBB_PLUS_TO_BBB_MINUS),
           dpos("c", "CO", False, 100, rating=R.BBB_PLUS_TO_BBB_MINUS)]
    assert drc.nonsec_drc(pos, OPTS) == pytest.approx(0.06 * 75)
    assert drc.nonsec_bucket(pos[0]) == "SOVEREIGNS"
    lg = dpos("m", "CITY", True, 1, credit_sector=CreditSector.LOCAL_GOVERNMENT)
    assert drc.nonsec_bucket(lg) == "LOCAL_GOVERNMENTS"


@pytest.mark.parametrize(("rating", "flags", "defaulted", "rw"), [
    (R.AAA_TO_AA_MINUS, {}, False, 0.02),
    (R.AAA_TO_AA_MINUS, {"drc_aaa": True}, False, 0.005),
    (R.A_PLUS_TO_A_MINUS, {}, False, 0.03),
    (R.BBB_PLUS_TO_BBB_MINUS, {}, False, 0.06),
    (R.BB_PLUS_TO_BB_MINUS, {}, False, 0.15),
    (R.B_PLUS_TO_B_MINUS, {}, False, 0.30),
    (R.BELOW_B_MINUS, {}, False, 0.50),
    (R.UNRATED, {}, False, 0.15),
    (R.A_PLUS_TO_A_MINUS, {}, True, 1.0),
])
def test_default_rw_mapping(rating: R, flags: dict[str, bool], defaulted: bool, rw: float) -> None:
    """MAR22.24 Table 2 via the engine rating buckets."""
    pos = dpos("x", "X", True, 1, rating=rating, flags=flags, is_defaulted=defaulted)
    assert drc.default_rw(pos, OPTS) == rw


def test_drc_sovereign_zero_discretion() -> None:
    """MAR22.7."""
    pos = dpos("s", "GOV", True, 100, credit_sector=CreditSector.SOVEREIGN, rating=R.UNRATED)
    assert drc.default_rw(pos, BCBSFRTBOptions(drc_sovereign_zero_rw=True)) == 0.0


def test_sec_nonctp_drc() -> None:
    """MAR22.27-22.35: JTD = MV, offset within tranche only, RW = banking-book RW x 8%."""
    t1 = dpos("a", "SPV", True, 10, kind=DRCKind.SEC_NON_CTP, market_value=10, pool_id="P",
              tranche_id="A", banking_book_risk_weight=1.0, sec_asset_class=SecAssetClass.CMBS,
              region="Europe")
    t1s = dpos("b", "SPV", False, 4, kind=DRCKind.SEC_NON_CTP, market_value=-4, pool_id="P",
               tranche_id="A", banking_book_risk_weight=1.0, sec_asset_class=SecAssetClass.CMBS,
               region="Europe")
    other = dpos("c", "SPV", False, 6, kind=DRCKind.SEC_NON_CTP, market_value=-6, pool_id="P",
                 tranche_id="B", banking_book_risk_weight=2.5, sec_asset_class=SecAssetClass.CMBS,
                 region="Europe")
    out = drc.sec_nonctp_drc([t1, t1s, other])
    hbr = 6 / 12
    assert out == pytest.approx(max(0.08 * 6 - hbr * 0.2 * 6, 0.0))
    assert drc.sec_nonctp_bucket(t1) == "CMBS|EUROPE"
    assert drc.sec_nonctp_bucket(t1.model_copy(update={"region": ""})) == "OTHER"
    assert drc.sec_nonctp_bucket(t1.model_copy(update={"flags": {"sec_asset_corporate": True}})) \
        == "CORPORATES"
    assert drc.sec_nonctp_bucket(t1.model_copy(update={"region": "Latam"})) == "CMBS|OTHER"
    with pytest.raises(ValueError):
        drc.sec_rw(t1.model_copy(update={"banking_book_risk_weight": None}))


def test_ctp_aggregation() -> None:
    """MAR22.44-22.45: HBR_ctp over the CTP; negative bucket counted at 50%.

    Index A long 1000 (A, 3%) -> 30; index B short 1000 -> -0.5 x 30 = -15 (HBR_ctp = 0.5);
    DRC_CTP = 30 + 0.5 x (-15) = 22.5.
    """
    a = dpos("a", "IDX-A", True, 1000, kind=DRCKind.CTP, pool_id="CDX.IG.S18",
             rating=R.A_PLUS_TO_A_MINUS)
    b = dpos("b", "IDX-B", False, 1000, kind=DRCKind.CTP, pool_id="ITRAXX.S18",
             rating=R.A_PLUS_TO_A_MINUS)
    assert drc.ctp_drc([a, b], OPTS) == pytest.approx(22.5)
    assert drc.ctp_drc([b], OPTS) == 0.0  # floored at zero overall


def test_ctp_mar22_45_example() -> None:
    """MAR22.45 text example: +100 and -100 -> 50."""
    vals = [100.0, -100.0]
    total = sum(max(v, 0) + 0.5 * min(v, 0) for v in vals)
    assert max(total, 0) == 50.0


def test_hbr_empty() -> None:
    """HBR with no positions is zero (guard)."""
    assert drc.hedge_benefit_ratio([]) == 0.0


# =========================================================================
#  RRAO
# =========================================================================


def rpos(cat: RRAOCategory, notional: float = 1000.0, **kw: Any) -> RRAOPositionInput:
    """RRAO position."""
    return RRAOPositionInput(position_id="r", gross_notional=notional, category=cat, **kw)


def test_rrao_example() -> None:
    """MAR23.8: 1.0% x exotic + 0.1% x other; MAR23.7 exclusions."""
    positions = [
        rpos(RRAOCategory.EXOTIC, 100),                                  # 1.0
        rpos(RRAOCategory.OTHER_RESIDUAL, 1000),                         # 1.0
        rpos(RRAOCategory.OTHER_RESIDUAL, 1000, flags={"listed_or_ccp_eligible": True}),  # 0
        rpos(RRAOCategory.EXOTIC, 100, flags={"listed_or_ccp_eligible": True}),           # 1.0
        rpos(RRAOCategory.EXOTIC, 100, flags={"back_to_back": True}),                     # 0
        rpos(RRAOCategory.EXOTIC, 100, exempt=True),                                      # 0
    ]
    assert BCBSMarketRisk().rrao_capital(positions) == pytest.approx(3.0)
    assert rrao.rrao_weight(RRAOCategory.EXOTIC) == 0.01


# =========================================================================
#  Total, protocol, IMA helpers, MAR40
# =========================================================================


def test_protocol_conformance() -> None:
    """BCBSMarketRisk implements MarketRiskCalculator."""
    calc = BCBSMarketRisk()
    assert isinstance(calc, MarketRiskCalculator)
    assert calc.jurisdiction is Jurisdiction.BCBS


def test_market_risk_total() -> None:
    """MAR20.4: SBM + DRC + RRAO; MAR20.1: RWA = 12.5 x capital."""
    calc = BCBSMarketRisk()
    s = [girr(100, 1.0), eq(100, "A", 5)]
    d = [dpos("b", "X", True, 100, rating=R.BBB_PLUS_TO_BBB_MINUS)]
    r = [rpos(RRAOCategory.EXOTIC, 100)]
    res = calc.market_risk(s, d, r)
    assert isinstance(res, MarketRiskResult)
    sbm_total = sum(x.total for x in calc.sbm_capital(s))
    assert res.sbm_total == pytest.approx(sbm_total)
    assert res.drc_total == pytest.approx(0.06 * 75)
    assert res.rrao == pytest.approx(1.0)
    assert res.total_capital == pytest.approx(sbm_total + 4.5 + 1.0)
    assert res.rwa == pytest.approx(12.5 * res.total_capital)
    assert res.binding_scenario in ("LOW", "MEDIUM", "HIGH")
    assert "sbm" in res.citations


def test_empty_portfolio() -> None:
    """No positions -> zero capital."""
    res = BCBSMarketRisk().market_risk([], [], [])
    assert res.total_capital == 0.0 and res.sbm_by_class == []


def test_ima_helpers() -> None:
    """MAR33.6, 33.15, 33.17, 33.41, 33.43, 33.45; MAR32.9, 32.42."""
    assert ima.imcc(10.0, [6.0, 8.0]) == pytest.approx(12.0)
    assert ima.stressed_es(10.0, 12.0, 8.0) == pytest.approx(15.0)
    assert ima.stressed_es(10.0, 6.0, 8.0) == pytest.approx(10.0)  # ratio floored at 1
    expected_ses = 5.0 + 0.0 + math.sqrt((0.6 * 7) ** 2 + (1 - 0.36) * 25)
    assert ima.ses([3.0, 4.0], [], [3.0, 4.0]) == pytest.approx(expected_ses)
    assert ima.capital_eligible_desks(10, 2, 8, 1, 1.5) == pytest.approx(13.0)
    assert ima.backtesting_zone(4) == "GREEN"
    assert ima.backtesting_zone(5) == "AMBER"
    assert ima.backtesting_zone(10) == "RED"
    assert ima.pla_zone(0.85, 0.05) == "GREEN"
    assert ima.pla_zone(0.75, 0.05) == "AMBER"
    assert ima.pla_zone(0.65, 0.05) == "RED"
    assert ima.pla_zone(0.85, 0.13) == "RED"
    sur = ima.pla_surcharge({"d1": 60.0, "d2": 40.0}, {"d2"}, 80.0)
    assert sur == pytest.approx(0.5 * 0.4 * 20.0)
    assert ima.aggregate_capital(80.0, 4.0, 10.0, 200.0, 100.0) == pytest.approx(94.0)
    assert ima.liquidity_adjusted_es([10.0]) == pytest.approx(10.0)
    assert ima.liquidity_adjusted_es([10.0, 5.0]) == pytest.approx(math.sqrt(100 + 25))
    with pytest.raises(ValueError):
        ima.backtesting_multiplier(-1)


def test_ssa_fx_table9_example() -> None:
    """MAR40.61 Table 9: (300 + 35) x 8% = 26.8."""
    nets = {"JPY": 50, "EUR": 100, "GBP": 150, "CAD": -20, "USD": -180}
    assert ssa.fx_capital(nets, -35) == pytest.approx(26.8)


def test_ssa_option_example() -> None:
    """MAR40.76: 100 shares at 10 with a put struck at 11 -> 1000 x 16% - 100 = 60."""
    o = ssa.SSAOptionPosition(position_id="o", structure="HEDGED", underlying_value=1000,
                              charge_rate=0.16, in_the_money=100, risk_class="EQ")
    assert ssa.option_capital(o) == pytest.approx(60.0)
    naked = o.model_copy(update={"structure": "NAKED", "option_value": 50})
    assert ssa.option_capital(naked) == pytest.approx(50.0)


@pytest.mark.parametrize(("cat", "rating", "mat", "rate"), [
    (ssa.SSAIssuerCategory.GOVERNMENT, R.AAA_TO_AA_MINUS, 5.0, 0.0),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.A_PLUS_TO_A_MINUS, 0.5, 0.0025),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, 2.0, 0.01),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, 3.0, 0.016),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.B_PLUS_TO_B_MINUS, 3.0, 0.08),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BELOW_B_MINUS, 3.0, 0.12),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.UNRATED, 3.0, 0.08),
    (ssa.SSAIssuerCategory.QUALIFYING, R.A_PLUS_TO_A_MINUS, 1.0, 0.01),
    (ssa.SSAIssuerCategory.OTHER, R.BB_PLUS_TO_BB_MINUS, 1.0, 0.08),
    (ssa.SSAIssuerCategory.OTHER, R.B_PLUS_TO_B_MINUS, 1.0, 0.12),
    (ssa.SSAIssuerCategory.OTHER, R.UNRATED, 1.0, 0.08),
])
def test_ssa_specific_risk_table1(cat: ssa.SSAIssuerCategory, rating: R, mat: float,
                                  rate: float) -> None:
    """MAR40.6 Table 1."""
    d = ssa.SSADebtPosition(position_id="d", issue_id="i", currency="USD", amount=100,
                            residual_maturity_years=mat, category=cat, rating=rating)
    assert ssa.specific_risk_rate(d) == rate


def test_ssa_ladder() -> None:
    """MAR40.26-40.28: single position, vertical disallowance and horizontal offsets."""
    d = ssa.SSADebtPosition(position_id="d", issue_id="i", currency="USD", amount=100,
                            residual_maturity_years=6.0, general_market_risk_only=True)
    assert ssa.ir_general_market_risk([d]) == pytest.approx(3.25)
    # same band: long 100, short 90 (weighted 3.25 / 2.925) -> net 0.325 + 10% x 2.925
    s = d.model_copy(update={"amount": -90.0, "issue_id": "j"})
    assert ssa.ir_general_market_risk([d, s]) == pytest.approx(0.325 + 0.2925)
    # zone 1 long (0.5y, 0.4%) vs zone 3 short (6y, 3.25%)
    a = d.model_copy(update={"residual_maturity_years": 0.5, "amount": 1000.0})
    b = d.model_copy(update={"amount": -100.0})
    # weighted: +4.0 zone 1, -3.25 zone 3 -> zone1/zone3 offset 3.25 at 100%; net 0.75
    assert ssa.ir_general_market_risk([a, b]) == pytest.approx(0.75 + 3.25)
    assert ssa.maturity_band(15.0, 0.02) == 13
    assert ssa.maturity_band(25.0, 0.02) == 14
    assert ssa.maturity_band(25.0, 0.05) == 12
    assert ssa.maturity_band(11.0, 0.02) == 12


def test_ssa_equity_commodity_and_total() -> None:
    """MAR40.42-40.47, 40.69-40.73 and MAR40.2 scaling."""
    eqs = [ssa.SSAEquityPosition(position_id="1", issue_id="A", market="US", amount=100),
           ssa.SSAEquityPosition(position_id="2", issue_id="B", market="US", amount=-60),
           ssa.SSAEquityPosition(position_id="3", issue_id="SPX", market="US", amount=50,
                                 is_diversified_index=True)]
    assert ssa.equity_capital(eqs) == pytest.approx(0.08 * 210 + 0.08 * 90 + 0.02 * 50)
    cs = [ssa.SSACommodityPosition(position_id="1", commodity="GOLDX", amount=100),
          ssa.SSACommodityPosition(position_id="2", commodity="GOLDX", amount=-40,
                                   maturity_years=2.5)]
    assert ssa.commodity_simplified(cs) == pytest.approx(13.2)
    # ladder: band 0 long 100 carried forward five bands to meet the band-5 short (5 x 0.6% x
    # 100), matched 40 in band 5 (1.5% x (40 + 40)), residual 60 not carried further -> 15% x 60
    exp_ladder = 0.006 * 100 * 5 + 0.015 * 80 + 0.15 * 60
    assert ssa.commodity_ladder(cs) == pytest.approx(exp_ladder)
    inp = ssa.SSAInputs(equities=eqs, fx_net_positions={"EUR": 100}, commodities=cs)
    out = BCBSMarketRisk().ssa(inp)
    assert out["total"] == pytest.approx(out["eq"] * 3.5 + out["fx"] * 1.2 + out["comm"] * 1.9)
    assert out["rwa"] == pytest.approx(12.5 * out["total"])
