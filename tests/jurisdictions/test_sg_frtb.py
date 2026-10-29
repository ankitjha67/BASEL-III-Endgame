"""Tests for the Singapore market-risk package (src/jurisdictions/sg/frtb), MAS 637 Part VIII.

Every SA(MR) table cell transcribed in ``params.py`` is asserted against the value printed in
MAS 637 (parametrised); MAS = MAR cells are cross-checked against the BCBS engine; each MAS
deviation from MAR is pinned; then hand-worked examples (single-bucket delta, two-bucket
aggregation with gamma, alternative S_b, curvature, DRC netting with HBR, the CTP fn 705
example, sec non-CTP /12.5 and fair-value cap, RRAO), scenario selection, bucket-assignment
edge cases, SSA(MR), IMA helpers, protocol conformance and the regime-neutral integration book.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.bcbs.frtb import BCBSMarketRisk
from src.jurisdictions.bcbs.frtb import params as bp
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
from src.jurisdictions.sg.frtb import SGFRTBOptions, SGMarketRisk, drc, rrao, sbm, ssa
from src.jurisdictions.sg.frtb import buckets as bk
from src.jurisdictions.sg.frtb import params as p

R = RatingBucket
RC = FRTBRiskClass
M = FRTBMeasure
OPTS = p.DEFAULT_FRTB_OPTIONS
SQ2 = math.sqrt(2.0)


def sens(rc: RC, measure: M = M.DELTA, **kw: Any) -> FRTBSensitivity:
    """Build a sensitivity."""
    return FRTBSensitivity(risk_class=rc, measure=measure, **kw)


def girr(value: float, tenor: float, ccy: str = "SGD", curve: str = "SORA",
         **kw: Any) -> FRTBSensitivity:
    """GIRR delta sensitivity."""
    return sens(RC.GIRR, value=value, currency=ccy, tenor_years=tenor, curve_name=curve, **kw)


def csr(value: float, issuer: str, sector: CreditSector, tenor: float = 5.0,
        rating: R = R.BBB_PLUS_TO_BBB_MINUS, **kw: Any) -> FRTBSensitivity:
    """CSR non-sec delta sensitivity."""
    return sens(RC.CSR_NONSEC, value=value, issuer=issuer, credit_sector=sector,
                tenor_years=tenor, rating=rating, **kw)


def drcpos(pid: str, obligor: str, is_long: bool, notional: float, **kw: Any) -> DRCPositionInput:
    """Non-sec DRC position at par (P&L 0) and 1-year maturity unless overridden."""
    kw.setdefault("market_value", notional)
    return DRCPositionInput(position_id=pid, obligor=obligor, is_long=is_long,
                            notional=notional, **kw)


# =========================================================================
#  Table cells -- transcribed values (MAS 637 Part VIII Division 2)
# =========================================================================

TABLE_8_1 = {0.25: 1.7, 0.5: 1.7, 1.0: 1.6, 2.0: 1.3, 3.0: 1.2, 5.0: 1.1, 10.0: 1.1,
             15.0: 1.1, 20.0: 1.1, 30.0: 1.1}


@pytest.mark.parametrize("tenor,pct", TABLE_8_1.items())
def test_table_8_1_girr_rw(tenor: float, pct: float) -> None:
    assert p.GIRR_DELTA_RW[tenor] == pytest.approx(pct / 100)


TABLE_8_2_ROW_025 = [100.0, 97.0, 91.4, 81.1, 71.9, 56.6, 40.0, 40.0, 40.0, 40.0]
TABLE_8_2_ROW_3Y = [71.9, 86.1, 94.2, 98.5, 100.0, 98.0, 93.2, 88.7, 84.4, 76.3]
TABLE_8_2_ROW_30Y = [40.0, 40.0, 41.9, 65.7, 76.3, 86.1, 94.2, 97.0, 98.5, 100.0]


@pytest.mark.parametrize("row,values", [(0, TABLE_8_2_ROW_025), (4, TABLE_8_2_ROW_3Y),
                                        (9, TABLE_8_2_ROW_30Y)])
def test_table_8_2_rows(row: int, values: list[float]) -> None:
    for j, v in enumerate(values):
        assert p.GIRR_TENOR_CORRELATION[row][j] == pytest.approx(v / 100)


@pytest.mark.parametrize("i", range(10))
@pytest.mark.parametrize("j", range(10))
def test_table_8_2_matches_fn657_formula(i: int, j: int) -> None:
    t1, t2 = p.GIRR_TENORS[i], p.GIRR_TENORS[j]
    assert p.GIRR_TENOR_CORRELATION[i][j] == pytest.approx(
        sbm.girr_tenor_rho_formula(t1, t2), abs=6e-4)
    assert p.GIRR_TENOR_CORRELATION[i][j] == p.GIRR_TENOR_CORRELATION[j][i]


def test_fn657_worked_example() -> None:
    assert sbm.girr_tenor_rho_formula(1.0, 5.0) == pytest.approx(0.8869, abs=1e-4)
    assert sbm.girr_tenor_rho_formula(1.0, 5.0) * 0.999 == pytest.approx(0.8860, abs=1e-4)


TABLE_8_4 = {1: 0.5, 2: 1.0, 3: 5.0, 4: 3.0, 5: 3.0, 6: 2.0, 7: 1.5, 8: 2.5, 9: 2.0, 10: 4.0,
             11: 12.0, 12: 7.0, 13: 8.5, 14: 5.5, 15: 5.0, 16: 12.0, 17: 1.5, 18: 5.0}


@pytest.mark.parametrize("bucket,pct", TABLE_8_4.items())
def test_table_8_4_csr_rw(bucket: int, pct: float) -> None:
    assert p.CSR_NONSEC_RW[bucket] == pytest.approx(pct / 100)


TABLE_8_5 = {
    (1, 2): 75, (1, 3): 10, (1, 4): 20, (1, 5): 25, (1, 6): 20, (1, 7): 15, (1, 8): 10,
    (1, 16): 0, (1, 17): 45, (1, 18): 45, (2, 3): 5, (2, 4): 15, (2, 5): 20, (2, 6): 15,
    (2, 7): 10, (2, 8): 10, (2, 16): 0, (2, 17): 45, (3, 4): 5, (3, 5): 15, (3, 6): 20,
    (3, 7): 5, (3, 8): 20, (4, 5): 20, (4, 6): 25, (4, 7): 5, (4, 8): 5, (5, 6): 25,
    (5, 7): 5, (5, 8): 15, (6, 7): 5, (6, 8): 20, (7, 8): 5, (8, 16): 0, (8, 18): 45,
    (16, 17): 0, (16, 18): 0, (17, 18): 75,
}


@pytest.mark.parametrize("pair,pct", TABLE_8_5.items())
def test_table_8_5_gamma_sector(pair: tuple[int, int], pct: float) -> None:
    a, b = pair
    assert p.CSR_GAMMA_SECTOR[(a, b)] == pytest.approx(pct / 100)
    assert p.CSR_GAMMA_SECTOR[(b, a)] == pytest.approx(pct / 100)


TABLE_8_6 = {1: 4, 2: 4, 3: 8, 4: 5, 5: 4, 6: 3, 7: 2, 8: 6, 9: 13, 10: 13, 11: 16, 12: 10,
             13: 12, 14: 12, 15: 12, 16: 13}


@pytest.mark.parametrize("bucket,pct", TABLE_8_6.items())
def test_table_8_6_ctp_rw(bucket: int, pct: float) -> None:
    assert p.CSR_CTP_RW[bucket] == pytest.approx(pct / 100)


TABLE_8_8 = {1: 0.9, 2: 1.5, 3: 2.0, 4: 2.0, 5: 0.8, 6: 1.2, 7: 1.2, 8: 1.4, 9: 1.125,
             10: 1.875, 11: 2.5, 12: 2.5, 13: 1.0, 14: 1.5, 15: 1.5, 16: 1.75, 17: 1.575,
             18: 2.625, 19: 3.5, 20: 3.5, 21: 1.4, 22: 2.1, 23: 2.1, 24: 2.45, 25: 3.5}


@pytest.mark.parametrize("bucket,pct", TABLE_8_8.items())
def test_table_8_8_sec_rw(bucket: int, pct: float) -> None:
    assert p.CSR_SEC_NONCTP_RW[bucket] == pytest.approx(pct / 100)
    assert p.CSR_SEC_NONCTP_RW[bucket] == pytest.approx(bp.CSR_SEC_NONCTP_RW[bucket])


TABLE_8_10 = {1: 55, 2: 60, 3: 45, 4: 55, 5: 30, 6: 35, 7: 40, 8: 50, 9: 70, 10: 50, 11: 70,
              12: 15, 13: 25}


@pytest.mark.parametrize("bucket,pct", TABLE_8_10.items())
def test_table_8_10_equity_rw(bucket: int, pct: float) -> None:
    assert p.EQUITY_SPOT_RW[bucket] == pytest.approx(pct / 100)
    assert p.EQUITY_REPO_RW[bucket] == pytest.approx(pct / 10000)


TABLE_8_11 = {1: 30, 2: 35, 3: 60, 4: 80, 5: 40, 6: 45, 7: 20, 8: 35, 9: 25, 10: 35, 11: 50}
TABLE_8_12 = {1: 55, 2: 95, 3: 40, 4: 80, 5: 60, 6: 65, 7: 55, 8: 45, 9: 15, 10: 40, 11: 15}


@pytest.mark.parametrize("bucket", range(1, 12))
def test_tables_8_11_8_12_commodity(bucket: int) -> None:
    assert p.COMMODITY_RW[bucket] == pytest.approx(TABLE_8_11[bucket] / 100)
    assert p.COMMODITY_RHO_CTY[bucket] == pytest.approx(TABLE_8_12[bucket] / 100)


TABLE_8_13 = {"GIRR": (60, 1.0), "CSR_NONSEC": (120, 1.0), "CSR_SEC_CTP": (120, 1.0),
              "CSR_SEC_NONCTP": (120, 1.0), "EQUITY_LARGE_CAP_INDEX": (20, 0.7778),
              "EQUITY_SMALL_CAP_OTHER": (60, 1.0), "COMMODITY": (120, 1.0), "FX": (40, 1.0)}


@pytest.mark.parametrize("key,lh_rw", TABLE_8_13.items())
def test_table_8_13_vega(key: str, lh_rw: tuple[int, float]) -> None:
    lh, rw = lh_rw
    assert p.VEGA_LIQUIDITY_HORIZON[key] == lh
    assert p.VEGA_RW[key] == pytest.approx(rw)
    assert bk.vega_rw_from_formula(lh) == pytest.approx(rw, abs=5e-5)  # fn 669


TABLE_8_14 = {"AAA": 0.5, "AA": 2, "A": 3, "BBB": 6, "BB": 15, "B": 30, "CCC": 50,
              "UNRATED": 15, "DEFAULTED": 100}


@pytest.mark.parametrize("cat,pct", TABLE_8_14.items())
def test_table_8_14_drc_rw(cat: str, pct: float) -> None:
    assert p.DRC_RW_TABLE814[cat] == pytest.approx(pct / 100)


def test_table_8_15_bucket_numbers() -> None:
    n = p.DRC_SEC_NONCTP_BUCKET_NUMBER
    assert n["COMPANIES"] == 1 and n["OTHERS"] == 46
    assert n["ABCP|ASIA"] == 2 and n["OTHER_WHOLESALE|ASIA"] == 12
    assert n["ABCP|EUROPE"] == 13 and n["RMBS|NORTH_AMERICA"] == 26
    assert n["SMALL_BUSINESSES|OTHER"] == 42 and len(n) == 46


@pytest.mark.parametrize("seniority,lgd", [(DRCSeniority.EQUITY, 1.0),
                                           (DRCSeniority.NON_SENIOR, 1.0),
                                           (DRCSeniority.SENIOR, 0.75),
                                           (DRCSeniority.COVERED_BOND, 0.25)])
def test_para_8_2_171_lgd(seniority: DRCSeniority, lgd: float) -> None:
    assert p.DRC_LGD[seniority] == lgd


@pytest.mark.parametrize("name,value", [
    ("GIRR_SAME_TENOR_DIFF_CURVE_RHO", 0.999), ("GIRR_INFLATION_VS_YIELD_RHO", 0.40),
    ("GIRR_GAMMA", 0.50), ("CSR_RHO_NAME_DIFF", 0.35), ("CSR_RHO_TENOR_DIFF", 0.65),
    ("CSR_RHO_BASIS_DIFF", 0.999), ("CSR_INDEX_RHO_NAME_DIFF", 0.80),
    ("CSR_GAMMA_RATING_DIFF", 0.50), ("CSR_CTP_RHO_BASIS_DIFF", 0.99),
    ("SEC_RHO_TRANCHE_DIFF", 0.40), ("SEC_RHO_TENOR_DIFF", 0.80), ("SEC_GAMMA", 0.0),
    ("EQUITY_SPOT_REPO_SAME_NAME_RHO", 0.999), ("EQUITY_GAMMA_1_10", 0.15),
    ("EQUITY_GAMMA_INDEX_PAIR", 0.75), ("EQUITY_GAMMA_DEFAULT", 0.45),
    ("COMMODITY_RHO_TENOR_DIFF", 0.99), ("COMMODITY_RHO_BASIS_DIFF", 0.999),
    ("COMMODITY_GAMMA_1_10", 0.20), ("FX_RW", 0.15), ("FX_GAMMA", 0.60), ("VEGA_ALPHA", 0.01),
    ("HIGH_CORRELATION_MULTIPLIER", 1.25), ("LOW_CORRELATION_FLOOR_FACTOR", 0.75),
    ("RRAO_EXOTIC_RW", 0.01), ("RRAO_OTHER_RW", 0.001), ("RWA_MULTIPLIER", 12.5),
    ("FX_CURVATURE_NON_REPORTING_SCALAR", 1.5), ("DRC_CTP_NEGATIVE_BUCKET_WEIGHT", 0.5),
    ("CSR_COVERED_BOND_CQG1_RW", 0.015), ("DRC_FUND_UNRATED_EQUITY_RW", 0.15),
    ("DRC_SEC_BANKING_BOOK_DIVISOR", 12.5),
])
def test_scalar_parameters(name: str, value: float) -> None:
    assert getattr(p, name) == pytest.approx(value)


def test_equity_intra_rho_para_8_2_131() -> None:
    assert [p.EQUITY_INTRA_RHO[b] for b in (1, 5, 9, 10, 12, 13)] == [
        0.15, 0.25, 0.075, 0.125, 0.80, 0.80]


# =========================================================================
#  MAS = MAR cross-checks against the BCBS engine
# =========================================================================

SAME_AS_BCBS = [
    "GIRR_TENORS", "GIRR_DELTA_RW", "GIRR_TENOR_CORRELATION", "CSR_TENORS", "VEGA_TENORS",
    "COMMODITY_TENORS", "CSR_NONSEC_RW", "CSR_GAMMA_SECTOR", "CSR_CTP_RW", "SEC_ASSET_ORDER",
    "EQUITY_SPOT_RW", "EQUITY_REPO_RW", "EQUITY_INTRA_RHO", "COMMODITY_RW",
    "COMMODITY_RHO_CTY", "COMMODITY_GROUP_TO_BUCKET", "FX_SPECIFIED_PAIRS", "VEGA_RW",
    "VEGA_LIQUIDITY_HORIZON", "DRC_LGD", "DRC_SENIORITY_RANK", "DRC_RATING_TO_CATEGORY",
    "IMA_LH_BUCKETS", "IMA_PLA_SPEARMAN", "IMA_PLA_KS", "IMA_FX_SPECIFIED_PAIRS",
    "ADVANCED_ECONOMIES", "EQUITY_SECTOR_TO_EME_BUCKET",
    # SSA(MR) tables the reused BCBS ladder / FX / commodity functions read:
    "SSA_MATURITY_BANDS", "SSA_LOW_COUPON_EXTRA_BANDS", "SSA_LOW_COUPON_THRESHOLD",
    "SSA_VERTICAL_DISALLOWANCE", "SSA_HORIZONTAL_WITHIN_ZONE", "SSA_HORIZONTAL_ADJACENT",
    "SSA_HORIZONTAL_ZONE1_ZONE3", "SSA_FX_CHARGE", "SSA_COMMODITY_SIMPLIFIED_NET",
    "SSA_COMMODITY_SIMPLIFIED_GROSS", "SSA_COMMODITY_SPREAD_RATE", "SSA_COMMODITY_CARRY_RATE",
    "SSA_COMMODITY_OUTRIGHT", "SSA_EQUITY_GENERAL", "SSA_EQUITY_INDEX_ADDON",
]


@pytest.mark.parametrize("name", SAME_AS_BCBS)
def test_mas_equals_mar(name: str) -> None:
    assert getattr(p, name) == getattr(bp, name)


def test_drc_table_8_14_equals_mar22_table2() -> None:
    assert p.DRC_RW_TABLE814 == bp.DRC_RW_TABLE2


def test_sec_divisor_equals_bcbs_8pct() -> None:
    assert pytest.approx(
        bp.DRC_SEC_BANKING_BOOK_TO_DRC_FACTOR) == 1 / p.DRC_SEC_BANKING_BOOK_DIVISOR


def test_backtesting_table_8_22_equals_mar32() -> None:
    assert pytest.approx(bp.IMA_BACKTESTING_ADDON) == p.IMA_BACKTESTING_ADDON
    assert p.IMA_BACKTESTING_ADDON[5] == 0.20 and p.IMA_BACKTESTING_ADDON[10] == 0.50


def test_ssa_scaling_equals_mar40() -> None:
    assert pytest.approx(bp.SSA_SCALING) == p.SSA_SCALING


# =========================================================================
#  MAS deviations from MAR
# =========================================================================


def test_girr_sqrt2_list_includes_sgd_and_is_fixed() -> None:
    assert bp.GIRR_SPECIFIED_CURRENCIES | {"SGD"} == p.GIRR_SQRT2_CURRENCIES
    assert bk.girr_delta_rw(girr(1.0, 0.25, "SGD")) == pytest.approx(0.017 / SQ2)
    assert bk.girr_delta_rw(girr(1.0, 0.25, "CHF")) == pytest.approx(0.017)
    # Reporting currency does not extend the list (para 8.2.92 vs MAR21.44 fn 283)
    m = SGMarketRisk(reporting_currency="CHF")
    assert m.risk_weight(girr(1.0, 0.25, "CHF")) == pytest.approx(0.017)
    b = BCBSMarketRisk(bp.BCBSFRTBOptions(reporting_currency="CHF"))
    assert b.risk_weight(girr(1.0, 0.25, "CHF")) == pytest.approx(0.017 / SQ2)


@pytest.mark.parametrize("curve", [GIRRCurve.INFLATION, GIRRCurve.XCCY_BASIS])
def test_girr_sqrt2_applies_to_inflation_xccy(curve: GIRRCurve) -> None:
    s = sens(RC.GIRR, value=1.0, currency="SGD", girr_curve=curve, curve_name="CPI")
    assert bk.girr_delta_rw(s) == pytest.approx(0.016 / SQ2)
    s2 = s.model_copy(update={"currency": "MYR"})
    assert bk.girr_delta_rw(s2) == pytest.approx(0.016)


def test_xccy_curves_99_9pct_para_8_2_95() -> None:
    a = ("XCCY", "SGD/USD onshore")
    b = ("XCCY", "SGD/USD offshore")
    assert sbm.girr_delta_rho(a, b) == pytest.approx(0.999)
    assert sbm.girr_delta_rho(a, ("RF", "SORA", 1.0)) == 0.0
    assert sbm.girr_delta_rho(a, ("INFLATION", "CPI")) == 0.0


def test_xccy_simple_sum_option_para_8_2_96() -> None:
    o = SGFRTBOptions(xccy_onshore_offshore_simple_sum=True)
    s1 = sens(RC.GIRR, value=1.0, currency="INR", girr_curve=GIRRCurve.XCCY_BASIS,
              curve_name="on")
    s2 = s1.model_copy(update={"curve_name": "off"})
    assert sbm.delta_factor_key(s1, o) == sbm.delta_factor_key(s2, o)
    assert sbm.delta_factor_key(s1, OPTS) != sbm.delta_factor_key(s2, OPTS)


def test_fx_sqrt2_mandatory() -> None:
    m = SGMarketRisk()
    usd = sens(RC.FX, value=1.0, fx_currency="USD")
    eur = sens(RC.FX, value=1.0, fx_currency="EUR")  # EUR/SGD: first-order cross
    myr = sens(RC.FX, value=1.0, fx_currency="MYR")
    assert m.risk_weight(usd) == pytest.approx(0.15 / SQ2)
    assert m.risk_weight(eur) == pytest.approx(0.15 / SQ2)
    assert m.risk_weight(myr) == pytest.approx(0.15)
    assert m.risk_weight(myr.model_copy(update={"fx_pair_is_liquid": True})) == pytest.approx(
        0.15 / SQ2)


def test_fx_reporting_currency_drives_pairs() -> None:
    chf = sens(RC.FX, value=1.0, fx_currency="CHF")
    assert SGMarketRisk(reporting_currency="USD").risk_weight(chf) == pytest.approx(0.15 / SQ2)
    assert SGMarketRisk(reporting_currency="MYR").risk_weight(chf) == pytest.approx(0.15)


def test_drc_zero_rw_mandatory_for_cqg1_sovereign() -> None:
    sov = drcpos("S", "UST", True, 100.0, credit_sector=CreditSector.SOVEREIGN,
                 rating=R.AAA_TO_AA_MINUS)
    assert drc.default_rw(sov) == 0.0
    assert SGMarketRisk().drc_capital([sov])["total"] == 0.0
    # BCBS default leaves MAR22.7 unexercised -> AA 2% x 75% x 100
    assert BCBSMarketRisk().drc_capital([sov])["total"] == pytest.approx(1.5)
    a_sov = sov.model_copy(update={"rating": R.A_PLUS_TO_A_MINUS})
    assert drc.default_rw(a_sov) == pytest.approx(0.03)


@pytest.mark.parametrize("flag", ["singapore_government_sgd", "zero_rw_international_org",
                                  "qualifying_mdb", "pse_zero_rw"])
def test_drc_zero_rw_flags(flag: str) -> None:
    x = drcpos("X", "N", True, 100.0, rating=R.UNRATED, flags={flag: True})
    assert drc.default_rw(x) == 0.0


def test_drc_zero_rw_explicit_override() -> None:
    sov = drcpos("S", "S", True, 100.0, credit_sector=CreditSector.SOVEREIGN,
                 rating=R.AAA_TO_AA_MINUS, flags={"sa_cr_zero_rw": False})
    assert drc.default_rw(sov) == pytest.approx(0.02)


def test_drc_buckets_para_8_2_183() -> None:
    assert drc.nonsec_bucket(drcpos("a", "a", True, 1, credit_sector=CreditSector.SOVEREIGN)) \
        == p.DRC_BUCKET_SOVEREIGNS
    assert drc.nonsec_bucket(drcpos("b", "b", True, 1, flags={"qualifying_mdb": True})) \
        == p.DRC_BUCKET_SOVEREIGNS
    assert drc.nonsec_bucket(drcpos("c", "c", True, 1,
                                    credit_sector=CreditSector.LOCAL_GOVERNMENT)) \
        == p.DRC_BUCKET_PSES
    assert drc.nonsec_bucket(drcpos("d", "d", True, 1, credit_sector=CreditSector.FINANCIAL)) \
        == p.DRC_BUCKET_COMPANIES


def test_drc_fund_treatments() -> None:
    f = drcpos("F", "FUND", True, 100.0, seniority=DRCSeniority.SENIOR,
               flags={"fund_unrated_equity": True})
    assert drc.lgd(f) == 1.0 and drc.default_rw(f) == pytest.approx(0.15)
    hy = f.model_copy(update={"flags": {"fund_unrated_equity": True, "fund_hy_mandate": True}})
    assert drc.default_rw(hy) == pytest.approx(p.DRC_FUND_HY_MANDATE_RW)


def test_rrao_listed_exclusion_scope_para_8_2_215() -> None:
    listed = RRAOPositionInput(position_id="a", gross_notional=1000,
                               category=RRAOCategory.OTHER_RESIDUAL,
                               flags={"listed_or_ccp_eligible": True})
    assert rrao.rrao_capital([listed]) == 0.0
    c_to_f = listed.model_copy(update={"flags": {"listed_or_ccp_eligible": True,
                                                  "rrao_8_2_210_c_to_f": True}})
    assert rrao.rrao_capital([c_to_f]) == pytest.approx(1.0)
    exotic = RRAOPositionInput(position_id="w", gross_notional=1000,
                               category=RRAOCategory.EXOTIC,
                               flags={"listed_or_ccp_eligible": True})
    assert rrao.rrao_capital([exotic]) == pytest.approx(10.0)


def test_ima_table_8_25_sgd_and_repo_rows() -> None:
    assert "SGD" in p.IMA_IR_SPECIFIED_CURRENCIES
    assert p.IMA_LIQUIDITY_HORIZONS["EQ_REPO_LARGE_CAP"] == 20
    assert p.IMA_LIQUIDITY_HORIZONS["EQ_DIVIDENDS_SMALL_CAP"] == 60
    common = set(bp.IMA_LIQUIDITY_HORIZONS) & set(p.IMA_LIQUIDITY_HORIZONS)
    assert common == set(bp.IMA_LIQUIDITY_HORIZONS)
    assert all(p.IMA_LIQUIDITY_HORIZONS[k] == bp.IMA_LIQUIDITY_HORIZONS[k] for k in common)


def test_deviation_register_is_populated() -> None:
    assert len(p.MAS_DEVIATIONS_FROM_MAR) >= 10


# =========================================================================
#  Bucket assignment edge cases
# =========================================================================


@pytest.mark.parametrize("sector,rating,ig,expected", [
    (CreditSector.SOVEREIGN, R.AAA_TO_AA_MINUS, None, 1),
    (CreditSector.LOCAL_GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, None, 2),
    (CreditSector.FINANCIAL, R.BB_PLUS_TO_BB_MINUS, None, 11),
    (CreditSector.FINANCIAL, R.UNRATED, None, 11),
    (CreditSector.FINANCIAL, R.UNRATED, True, 3),     # IRBA internal rating, 8.2.104(b)(i)
    (CreditSector.COVERED_BOND, R.A_PLUS_TO_A_MINUS, None, 8),
    (CreditSector.COVERED_BOND, R.BB_PLUS_TO_BB_MINUS, None, 16),
    (CreditSector.OTHER, R.AAA_TO_AA_MINUS, None, 16),
    (None, R.AAA_TO_AA_MINUS, None, 16),
    (CreditSector.INDEX, R.BBB_PLUS_TO_BBB_MINUS, None, 17),
    (CreditSector.INDEX, R.BB_PLUS_TO_BB_MINUS, None, 18),
])
def test_csr_nonsec_bucket(sector: CreditSector | None, rating: R, ig: bool | None,
                           expected: int) -> None:
    s = sens(RC.CSR_NONSEC, value=1.0, credit_sector=sector, rating=rating,
             is_investment_grade=ig, tenor_years=1.0)
    assert bk.csr_nonsec_bucket(s) == expected


def test_csr_ctp_index_goes_to_16() -> None:
    s = sens(RC.CSR_SEC_CTP, value=1.0, credit_sector=CreditSector.INDEX, tenor_years=1.0)
    assert bk.csr_ctp_bucket(s) == 16
    assert SGMarketRisk().risk_weight(s) == pytest.approx(0.13)


def test_covered_bond_cqg1_rw() -> None:
    s = csr(1.0, "CB", CreditSector.COVERED_BOND, rating=R.AAA_TO_AA_MINUS)
    assert bk.csr_nonsec_rw(s, OPTS) == pytest.approx(0.015)
    assert bk.csr_nonsec_rw(s, SGFRTBOptions(covered_bond_cqg1_reduction=False)) == 0.025


@pytest.mark.parametrize("tranche,asset,expected", [
    (SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_PRIME, 1),
    (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.CLO_NON_CTP, 16),
    (SecTrancheClass.HY_NR, SecAssetClass.CMBS, 20),
    (SecTrancheClass.HY_NR, SecAssetClass.OTHER, 25),
    (None, SecAssetClass.CMBS, 25),
])
def test_sec_nonctp_bucket(tranche: SecTrancheClass | None, asset: SecAssetClass,
                           expected: int) -> None:
    s = sens(RC.CSR_SEC_NONCTP, value=1.0, sec_tranche_class=tranche, sec_asset_class=asset,
             tenor_years=1.0)
    assert bk.csr_sec_nonctp_bucket(s) == expected


@pytest.mark.parametrize("kw,expected", [
    ({"is_large_cap": True, "is_advanced_economy": False,
      "equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES}, 1),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.FINANCIALS_REALESTATE_TECH}, 8),
    ({"is_large_cap": False, "is_advanced_economy": False,
      "equity_sector": EquitySector.MATERIALS_ENERGY}, 9),
    ({"is_large_cap": False, "is_advanced_economy": True,
      "equity_sector": EquitySector.TELECOM_INDUSTRIALS}, 10),
    ({"is_large_cap": True, "is_advanced_economy": True,
      "equity_sector": EquitySector.OTHER}, 11),
    ({"is_large_cap": None, "is_advanced_economy": True}, 11),
    ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": True}, 12),
    ({"is_equity_index": True, "is_large_cap": True, "is_advanced_economy": False}, 13),
])
def test_equity_bucket(kw: dict[str, Any], expected: int) -> None:
    assert bk.equity_bucket(sens(RC.EQUITY, value=1.0, **kw)) == expected


def test_commodity_bucket_and_hint() -> None:
    s = sens(RC.COMMODITY, value=1.0, commodity_group=CommodityGroup.FREIGHT, tenor_years=1.0)
    assert bk.commodity_bucket(s) == 4
    assert bk.commodity_bucket(s.model_copy(update={"commodity_group": None})) == 11
    assert bk.commodity_bucket(s.model_copy(update={"bucket_hint": "7"})) == 7
    with pytest.raises(ValueError):
        bk.commodity_bucket(s.model_copy(update={"bucket_hint": "12"}))
    with pytest.raises(ValueError):
        bk.commodity_bucket(s.model_copy(update={"bucket_hint": "x"}))


def test_off_grid_tenor_rejected() -> None:
    with pytest.raises(ValueError):
        bk.girr_delta_rw(girr(1.0, 4.0))


def test_missing_currency_rejected() -> None:
    with pytest.raises(ValueError):
        bk.girr_bucket(sens(RC.GIRR, value=1.0, tenor_years=1.0))
    with pytest.raises(ValueError):
        bk.fx_bucket(sens(RC.FX, value=1.0))


def test_vega_rw_equity_large_vs_small() -> None:
    large = sens(RC.EQUITY, M.VEGA, value=1.0, is_equity_index=True, is_large_cap=True,
                 is_advanced_economy=True, option_maturity_years=1.0)
    small = sens(RC.EQUITY, M.VEGA, value=1.0, is_large_cap=False, is_advanced_economy=True,
                 equity_sector=EquitySector.OTHER, option_maturity_years=1.0)
    assert bk.vega_risk_weight(large) == pytest.approx(0.7778)
    assert bk.vega_risk_weight(small) == 1.0


def test_curvature_rw_girr_highest_tenor() -> None:
    s = sens(RC.GIRR, M.CURVATURE, currency="SGD", cvr_up=1.0, cvr_down=1.0)
    assert bk.curvature_risk_weight(s, OPTS) == pytest.approx(0.017 / SQ2)


# =========================================================================
#  Hand-worked SBM examples
# =========================================================================


def test_single_bucket_girr_delta() -> None:
    # SGD 1y and 5y on one curve: WS = 100 x 1.6%/sqrt2, 100 x 1.1%/sqrt2, rho 88.7%
    w1, w2 = 1.6 / SQ2, 1.1 / SQ2
    expected = math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.887 * w1 * w2)
    res = SGMarketRisk().sbm_scenarios([girr(100, 1.0), girr(100, 5.0)])
    med = next(r for r in res if r.scenario == "MEDIUM")
    assert med.by_class[RC.GIRR][0] == pytest.approx(expected)


def test_girr_diff_curve_rho() -> None:
    assert sbm.girr_delta_rho(("RF", "A", 1.0), ("RF", "B", 1.0)) == pytest.approx(0.999)
    assert sbm.girr_delta_rho(("RF", "A", 1.0), ("RF", "B", 5.0)) == pytest.approx(0.887 * 0.999)
    assert sbm.girr_delta_rho(("INFLATION", "A"), ("INFLATION", "B")) == pytest.approx(0.999)
    assert sbm.girr_delta_rho(("INFLATION", "A"), ("RF", "B", 5.0)) == pytest.approx(0.40)


def test_csr_footnote_661_example() -> None:
    ka = ("APPLE", 5.0, False)
    kb = ("GOOGLE", 10.0, True)
    assert sbm.delta_rho(RC.CSR_NONSEC, "6", ka, kb) == pytest.approx(0.2273, abs=1e-4)


def test_commodity_footnote_666_example() -> None:
    ka = ("BRENT", 1.0, "LE_HAVRE")
    kb = ("WTI", 5.0, "OKLAHOMA")
    assert sbm.delta_rho(RC.COMMODITY, "2", ka, kb) == pytest.approx(0.9396, abs=1e-4)


def test_two_bucket_csr_aggregation_with_gamma() -> None:
    # Bucket 3 (financials CQG<=3) and bucket 12 (basic materials CQG>=4), one name each.
    a = csr(100, "BANK", CreditSector.FINANCIAL)
    b = csr(100, "MINER", CreditSector.BASIC_MATERIALS, rating=R.BB_PLUS_TO_BB_MINUS)
    ws_a, ws_b = 100 * 0.05, 100 * 0.07
    g = 0.5 * 0.05  # gamma_rating 50% x Table 8-5 (3/11, 4/12) 5%
    assert sbm.csr_gamma(3, 12) == pytest.approx(g)
    expected = math.sqrt(ws_a ** 2 + ws_b ** 2 + 2 * g * ws_a * ws_b)
    med = next(r for r in SGMarketRisk().sbm_scenarios([a, b]) if r.scenario == "MEDIUM")
    assert med.by_class[RC.CSR_NONSEC][0] == pytest.approx(expected)


def test_alternative_sb_when_negative() -> None:
    # Two GIRR buckets with opposite large sums; one bucket internally hedged.
    s = [girr(100, 1.0, "USD"), girr(-100, 1.0, "EUR"), girr(80, 10.0, "EUR")]
    res = next(r for r in SGMarketRisk().sbm_scenarios(s) if r.scenario == "HIGH")
    assert res.by_class[RC.GIRR][0] >= 0.0


def test_other_bucket_simple_sum() -> None:
    a = csr(100, "X", CreditSector.OTHER)
    b = csr(-100, "Y", CreditSector.OTHER)
    med = next(r for r in SGMarketRisk().sbm_scenarios([a, b]) if r.scenario == "MEDIUM")
    assert med.by_class[RC.CSR_NONSEC][0] == pytest.approx(24.0)


def test_sec_bucket_25_outside_root() -> None:
    a = sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T1", tenor_years=1.0)
    b = sens(RC.CSR_SEC_NONCTP, value=100, tranche_id="T2", tenor_years=1.0,
             sec_tranche_class=SecTrancheClass.SENIOR_IG, sec_asset_class=SecAssetClass.CMBS)
    med = next(r for r in SGMarketRisk().sbm_scenarios([a, b]) if r.scenario == "MEDIUM")
    assert med.by_class[RC.CSR_SEC_NONCTP][0] == pytest.approx(3.5 + 2.0)


def test_equity_spot_repo_same_name() -> None:
    kw = {"is_large_cap": True, "is_advanced_economy": True,
          "equity_sector": EquitySector.TELECOM_INDUSTRIALS, "issuer": "SINGTEL"}
    spot = sens(RC.EQUITY, value=100, **kw)
    repo = sens(RC.EQUITY, value=1000, equity_risk_factor=EquityRiskFactor.REPO, **kw)
    w1, w2 = 35.0, 3.5
    expected = math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.999 * w1 * w2)
    med = next(r for r in SGMarketRisk().sbm_scenarios([spot, repo]) if r.scenario == "MEDIUM")
    assert med.by_class[RC.EQUITY][0] == pytest.approx(expected)


def test_fx_two_buckets() -> None:
    s = [sens(RC.FX, value=100, fx_currency="USD"), sens(RC.FX, value=100, fx_currency="MYR")]
    w1, w2 = 15 / SQ2, 15.0
    expected = math.sqrt(w1 ** 2 + w2 ** 2 + 2 * 0.6 * w1 * w2)
    med = next(r for r in SGMarketRisk().sbm_scenarios(s) if r.scenario == "MEDIUM")
    assert med.by_class[RC.FX][0] == pytest.approx(expected)


def test_vega_girr_correlation() -> None:
    ka = ("RF", "", 1.0, 1.0)
    kb = ("RF", "", 5.0, 1.0)
    assert sbm.vega_rho(RC.GIRR, "SGD", ka, kb) == pytest.approx(math.exp(-0.01 * 4 / 1))


def test_vega_option_without_maturity_maps_to_10y() -> None:
    s = sens(RC.EQUITY, M.VEGA, value=1.0, issuer="X", is_large_cap=True,
             is_advanced_economy=True, equity_sector=EquitySector.OTHER)
    assert sbm.vega_factor_key(s) == ("X", 10.0)


def test_curvature_two_names_with_psi() -> None:
    kw = {"is_large_cap": True, "is_advanced_economy": True,
          "equity_sector": EquitySector.MATERIALS_ENERGY}
    a = sens(RC.EQUITY, M.CURVATURE, issuer="A", cvr_up=-10.0, cvr_down=5.0, **kw)
    b = sens(RC.EQUITY, M.CURVATURE, issuer="B", cvr_up=-20.0, cvr_down=8.0, **kw)
    rho = 0.25 ** 2
    k_up = 0.0  # both negative: psi 0, max(CVR, 0) 0
    k_dn = math.sqrt(25 + 64 + 2 * rho * 40)
    assert k_dn > k_up
    med = next(r for r in SGMarketRisk().sbm_scenarios([a, b]) if r.scenario == "MEDIUM")
    assert med.by_class[RC.EQUITY][2] == pytest.approx(k_dn)


def test_fx_curvature_scalar_flag() -> None:
    s = sens(RC.FX, M.CURVATURE, fx_currency="EUR", cvr_up=15.0, cvr_down=-3.0,
             flags={"fx_curvature_scalar_1_5": True})
    med = next(r for r in SGMarketRisk().sbm_scenarios([s]) if r.scenario == "MEDIUM")
    assert med.by_class[RC.FX][2] == pytest.approx(10.0)
    o = SGFRTBOptions(fx_curvature_all_div_1_5=True)
    s2 = s.model_copy(update={"flags": {}})
    med2 = next(r for r in sbm.sbm_scenarios([s2], o) if r.scenario == "MEDIUM")
    assert med2.by_class[RC.FX][2] == pytest.approx(10.0)


def test_no_curvature_for_inflation_or_repo() -> None:
    with pytest.raises(ValueError):
        sbm.curvature_factor_key(sens(RC.GIRR, M.CURVATURE, currency="SGD",
                                      girr_curve=GIRRCurve.INFLATION))
    with pytest.raises(ValueError):
        sbm.curvature_factor_key(sens(RC.EQUITY, M.CURVATURE, issuer="X",
                                      equity_risk_factor=EquityRiskFactor.REPO))


# =========================================================================
#  Scenarios
# =========================================================================


@pytest.mark.parametrize("rho,low,high", [(0.5, 0.375, 0.625), (0.9, 0.8, 1.0),
                                          (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)])
def test_scenario_transforms(rho: float, low: float, high: float) -> None:
    assert sbm.scenario_correlation(rho, "LOW") == pytest.approx(low)
    assert sbm.scenario_correlation(rho, "HIGH") == pytest.approx(high)
    assert sbm.scenario_correlation(rho, "MEDIUM") == rho
    with pytest.raises(ValueError):
        sbm.scenario_correlation(rho, "EXTREME")


def test_binding_scenario_is_portfolio_max() -> None:
    s = [girr(100, 1.0), girr(-100, 10.0), girr(50, 1.0, "USD"), girr(60, 1.0, "EUR")]
    m = SGMarketRisk()
    res = m.sbm_scenarios(s)
    best = max(res, key=lambda r: r.total)
    out = m.sbm_capital(s)
    assert sum(c.total for c in out) == pytest.approx(best.total)
    assert all(c.scenario == best.scenario for c in out)


def test_empty_book() -> None:
    m = SGMarketRisk()
    assert m.sbm_capital([]) == []
    r = m.market_risk([], [], [])
    assert r.total_capital == 0.0 and r.rwa == 0.0


# =========================================================================
#  DRC hand-worked examples
# =========================================================================


def test_drc_netting_and_hbr() -> None:
    # Obligor A: long senior 100 (BBB), short senior 40 -> net long 0.75 x 60 = 45 (RW 6%)
    # Obligor B: short senior 100 (BB) -> net short -75 (RW 15%)
    pos = [
        drcpos("1", "A", True, 100, rating=R.BBB_PLUS_TO_BBB_MINUS),
        drcpos("2", "A", False, 40, rating=R.BBB_PLUS_TO_BBB_MINUS),
        drcpos("3", "B", False, 100, rating=R.BB_PLUS_TO_BB_MINUS),
    ]
    hbr = 45 / (45 + 75)
    expected = max(0.06 * 45 - hbr * 0.15 * 75, 0.0)
    assert drc.nonsec_drc(pos) == pytest.approx(expected)


def test_drc_seniority_restriction_fn_691() -> None:
    long_eq = drcpos("1", "A", True, 100, seniority=DRCSeniority.EQUITY)
    short_bond = drcpos("2", "A", False, 100, seniority=DRCSeniority.SENIOR)
    # Long equity cannot be offset by a short (more senior) bond
    out = drc.nonsec_by_bucket([long_eq, short_bond])
    assert out[p.DRC_BUCKET_COMPANIES] > 0.0
    long_bond = drcpos("3", "B", True, 100, seniority=DRCSeniority.SENIOR)
    short_eq = drcpos("4", "B", False, 75, seniority=DRCSeniority.EQUITY)
    assert drc.nonsec_drc([long_bond, short_eq]) == pytest.approx(0.0)


def test_drc_maturity_weighting_fn_690() -> None:
    assert drc.maturity_weight(1 / 12) == 0.25
    assert drc.maturity_weight(0.5) == 0.5
    assert drc.maturity_weight(3.0) == 1.0
    fut = drcpos("F", "IDX", False, 10, maturity_years=1 / 12, seniority=DRCSeniority.EQUITY)
    assert drc.gross_jtd(fut) * drc.maturity_weight(fut.maturity_years) == pytest.approx(-2.5)


def test_drc_jtd_with_pnl_and_flags() -> None:
    x = drcpos("1", "A", True, 100, pnl=-10)
    assert drc.gross_jtd(x) == pytest.approx(65.0)
    y = x.model_copy(update={"flags": {"lgd_not_linked_to_recovery": True}})
    assert drc.gross_jtd(y) == pytest.approx(90.0)
    z = x.model_copy(update={"flags": {"unwind_without_default_exposure": True}})
    assert drc.gross_jtd(z) == 0.0
    with pytest.raises(ValueError):
        drc.nonsec_drc([drcpos("c", "E", True, 1, maturity_years=0.5,
                               flags={"cash_equity": True})])


def test_drc_defaulted_and_aaa() -> None:
    assert drc.default_rw(drcpos("d", "D", True, 1, is_defaulted=True)) == 1.0
    assert drc.default_rw(drcpos("a", "A", True, 1, rating=R.AAA_TO_AA_MINUS,
                                 flags={"drc_aaa": True})) == 0.005


def _sec(pid: str, is_long: bool, mv: float, rw: float, **kw: Any) -> DRCPositionInput:
    return DRCPositionInput(position_id=pid, kind=kw.pop("kind", DRCKind.SEC_NON_CTP),
                            obligor=kw.pop("obligor", "POOL"), is_long=is_long, notional=mv,
                            market_value=mv, banking_book_risk_weight=rw, **kw)


def test_sec_nonctp_divisor_and_cap() -> None:
    a = _sec("1", True, 100.0, 1.0, pool_id="P", tranche_id="A",
             sec_asset_class=SecAssetClass.CMBS, region="ASIA")
    assert drc.sec_rw(a) == pytest.approx(0.08)
    assert drc.sec_nonctp_drc([a]) == pytest.approx(8.0)
    capped = a.model_copy(update={"banking_book_risk_weight": 15.0})  # 1,500% RW
    assert drc.sec_nonctp_drc([capped]) == pytest.approx(100.0)  # capped at fair value
    deriv = capped.model_copy(update={"flags": {"sec_derivative": True}})
    assert drc.sec_nonctp_drc([deriv]) == pytest.approx(120.0)
    assert drc.sec_nonctp_bucket(a) == "CMBS|ASIA"
    assert drc.sec_nonctp_bucket(a.model_copy(update={"region": "LATAM"})) == "CMBS|OTHER"
    assert drc.sec_nonctp_bucket(a.model_copy(update={"region": ""})) == "OTHERS"


def test_sec_nonctp_no_cross_tranche_offset() -> None:
    a = _sec("1", True, 100.0, 1.0, pool_id="P", tranche_id="A", region="ASIA",
             sec_asset_class=SecAssetClass.CMBS)
    b = _sec("2", False, 100.0, 1.0, pool_id="P", tranche_id="B", region="ASIA",
             sec_asset_class=SecAssetClass.CMBS)
    same = b.model_copy(update={"tranche_id": "A"})
    assert drc.sec_nonctp_drc([a, same]) == pytest.approx(0.0)
    # different tranches: HBR = 0.5 -> 8 - 0.5 x 8 = 4
    assert drc.sec_nonctp_drc([a, b]) == pytest.approx(4.0)


def test_ctp_footnote_705_example() -> None:
    assert drc.ctp_aggregate([100.0, -100.0]) == pytest.approx(50.0)
    assert drc.ctp_aggregate([-100.0]) == 0.0


def test_ctp_cross_index_hbr() -> None:
    a = _sec("1", True, 1250.0, 1.0, kind=DRCKind.CTP, pool_id="CDX", tranche_id="0-3")
    b = _sec("2", False, 1250.0, 1.0, kind=DRCKind.CTP, pool_id="ITRX", tranche_id="0-3")
    # HBR_CTP = 0.5 across buckets: DRC_CDX = 100, DRC_ITRX = -50 -> 100 - 25 = 75
    assert drc.ctp_drc([a, b]) == pytest.approx(75.0)
    hedge = drcpos("h", "NAME", False, 100.0, kind=DRCKind.CTP, pool_id="CDX",
                   rating=R.A_PLUS_TO_A_MINUS)
    assert drc.ctp_rw(hedge, -75.0) == pytest.approx(0.03)


def test_drc_capital_components() -> None:
    m = SGMarketRisk()
    out = m.drc_capital([drcpos("1", "A", True, 100),
                         _sec("2", True, 100.0, 1.0, pool_id="P", tranche_id="A")])
    assert out["nonsec"] == pytest.approx(0.75 * 100 * 0.15)
    assert out["sec_nonctp"] == pytest.approx(8.0)
    assert out["total"] == pytest.approx(out["nonsec"] + out["sec_nonctp"] + out["ctp"])
    with pytest.raises(ValueError):
        drc.sec_rw(drcpos("x", "x", True, 1, kind=DRCKind.SEC_NON_CTP))


# =========================================================================
#  RRAO
# =========================================================================


def test_rrao_example() -> None:
    pos = [
        RRAOPositionInput(position_id="W", gross_notional=2000, category=RRAOCategory.EXOTIC),
        RRAOPositionInput(position_id="B", gross_notional=60000,
                          category=RRAOCategory.OTHER_RESIDUAL),
        RRAOPositionInput(position_id="X", gross_notional=5000, category=RRAOCategory.EXOTIC,
                          flags={"back_to_back": True}),
        RRAOPositionInput(position_id="E", gross_notional=5000, category=RRAOCategory.EXOTIC,
                          exempt=True),
    ]
    assert SGMarketRisk().rrao_capital(pos) == pytest.approx(20.0 + 60.0)


# =========================================================================
#  SSA(MR)
# =========================================================================


@pytest.mark.parametrize("cat,rating,mat,rate", [
    (ssa.SSAIssuerCategory.GOVERNMENT, R.AAA_TO_AA_MINUS, 5.0, 0.0),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.A_PLUS_TO_A_MINUS, 0.5, 0.0025),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, 1.0, 0.01),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BBB_PLUS_TO_BBB_MINUS, 3.0, 0.016),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.B_PLUS_TO_B_MINUS, 3.0, 0.08),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.BELOW_B_MINUS, 3.0, 0.12),
    (ssa.SSAIssuerCategory.GOVERNMENT, R.UNRATED, 3.0, 0.08),
    (ssa.SSAIssuerCategory.QUALIFYING, R.UNRATED, 2.0, 0.01),
    (ssa.SSAIssuerCategory.OTHER, R.BB_PLUS_TO_BB_MINUS, 2.0, 0.08),
    (ssa.SSAIssuerCategory.OTHER, R.B_PLUS_TO_B_MINUS, 2.0, 0.12),
    (ssa.SSAIssuerCategory.OTHER, R.UNRATED, 2.0, 0.08),
])
def test_table_8e_1(cat: ssa.SSAIssuerCategory, rating: R, mat: float, rate: float) -> None:
    d = ssa.SGSSADebtPosition(position_id="d", issue_id="i", currency="SGD", amount=100.0,
                              residual_maturity_years=mat, category=cat, rating=rating)
    assert ssa.specific_risk_rate(d) == pytest.approx(rate)


def test_annex_8e_para_1_4_zero_specific() -> None:
    d = ssa.SGSSADebtPosition(position_id="d", issue_id="SGS", currency="SGD", amount=100.0,
                              residual_maturity_years=5.0,
                              category=ssa.SSAIssuerCategory.GOVERNMENT, rating=R.UNRATED,
                              zero_specific_risk=True)
    assert ssa.specific_risk_rate(d) == 0.0


def test_ssa_equity_qualifying_index() -> None:
    idx = ssa.SSAEquityPosition(position_id="e", issue_id="STI", market="SG", amount=100.0,
                                is_diversified_index=True)
    single = ssa.SSAEquityPosition(position_id="s", issue_id="DBS", market="SG", amount=100.0)
    assert ssa.equity_capital([idx]) == pytest.approx(0.0 + 8.0 + 2.0)
    assert ssa.equity_capital([single]) == pytest.approx(8.0 + 8.0)


def test_ssa_total_scaling_and_rwa() -> None:
    inp = ssa.SGSSAInputs(
        equities=[ssa.SSAEquityPosition(position_id="s", issue_id="DBS", market="SG",
                                        amount=100.0)],
        fx_net_positions={"USD": 50.0, "EUR": -20.0},
        commodities=[ssa.SSACommodityPosition(position_id="c", commodity="GOLDX", amount=10.0)],
    )
    out = SGMarketRisk().ssa(inp)
    assert out["eq"] == pytest.approx(16.0)
    assert out["fx"] == pytest.approx(4.0)
    assert out["comm"] == pytest.approx(1.5 + 0.3)
    total = 16.0 * 3.5 + 4.0 * 1.2 + 1.8 * 1.9
    assert out["total"] == pytest.approx(total)
    assert out["rwa"] == pytest.approx(total * 12.5)


def test_ssa_general_market_risk_ladder() -> None:
    d = ssa.SGSSADebtPosition(position_id="d", issue_id="i", currency="SGD", amount=100.0,
                              residual_maturity_years=4.5, coupon=0.05,
                              general_market_risk_only=True)
    out = ssa.ssa_capital(ssa.SGSSAInputs(debt=[d]))
    assert out["irr"] == pytest.approx(2.75)  # band 8 (4-5y) 2.75%


def test_ssa_eligibility_and_fx_exemption() -> None:
    assert SGMarketRisk.ssa_eligible(150.0, 10000.0)
    assert not SGMarketRisk.ssa_eligible(250.0, 100000.0)
    assert not SGMarketRisk.ssa_eligible(150.0, 5000.0)
    assert ssa.fx_exemption_eligible(90.0, 1.5, 100.0)
    assert not ssa.fx_exemption_eligible(90.0, 2.5, 100.0)


# =========================================================================
#  IMA
# =========================================================================


@pytest.mark.parametrize("exc,zone,mult", [(0, "GREEN", 1.5), (4, "GREEN", 1.5),
                                           (5, "AMBER", 1.70), (7, "AMBER", 1.83),
                                           (9, "AMBER", 1.92), (10, "RED", 2.0),
                                           (15, "RED", 2.0)])
def test_backtesting(exc: int, zone: str, mult: float) -> None:
    assert SGMarketRisk.backtesting_zone(exc) == zone
    assert SGMarketRisk.multiplier(exc) == pytest.approx(mult)
    with pytest.raises(ValueError):
        SGMarketRisk.multiplier(-1)


@pytest.mark.parametrize("rho,ks,zone", [(0.85, 0.05, "GREEN"), (0.75, 0.05, "AMBER"),
                                         (0.85, 0.10, "AMBER"), (0.65, 0.05, "RED"),
                                         (0.85, 0.13, "RED")])
def test_pla_table_8_23(rho: float, ks: float, zone: str) -> None:
    assert SGMarketRisk.pla_zone(rho, ks) == zone


def test_ima_parameters_and_helpers() -> None:
    ip = SGMarketRisk().ima_parameters()
    assert isinstance(ip, IMAParameters)
    assert ip.jurisdiction is Jurisdiction.SG
    assert ip.es_confidence == 0.975 and ip.imcc_rho == 0.5 and ip.ses_rho == 0.6
    assert ip.liquidity_horizons_days["IR_SPECIFIED_CURRENCIES"] == 10
    assert SGMarketRisk.imcc(100.0, [60.0, 60.0]) == pytest.approx(110.0)
    assert SGMarketRisk.ses([3.0, 4.0], [], []) == pytest.approx(5.0)
    assert SGMarketRisk.liquidity_adjusted_es([10.0]) == pytest.approx(10.0)
    assert SGMarketRisk.aggregate_capital(100, 0, 20, 200, 90) == pytest.approx(130.0)


# =========================================================================
#  Protocol conformance and integration
# =========================================================================


def test_protocol_conformance() -> None:
    m = SGMarketRisk()
    assert isinstance(m, MarketRiskCalculator)
    assert m.jurisdiction is Jurisdiction.SG
    assert m.reporting_currency == "SGD" and m.options.reporting_currency == "SGD"
    assert SGMarketRisk(reporting_currency="usd").options.reporting_currency == "USD"


def test_market_risk_total() -> None:
    m = SGMarketRisk()
    s = [girr(100, 1.0), csr(100, "DBS", CreditSector.FINANCIAL)]
    d = [drcpos("1", "DBS", True, 100, rating=R.AAA_TO_AA_MINUS)]
    rr = [RRAOPositionInput(position_id="w", gross_notional=1000, category=RRAOCategory.EXOTIC)]
    r = m.market_risk(s, d, rr)
    assert isinstance(r, MarketRiskResult)
    assert r.total_capital == pytest.approx(r.sbm_total + r.drc_total + r.rrao)
    assert r.rwa == pytest.approx(12.5 * r.total_capital)
    assert r.rrao == pytest.approx(10.0)
    assert r.binding_scenario in p.SCENARIOS
    assert "rwa" in r.citations


def test_neutral_book_integration() -> None:
    from src.data_generation.frtb_inputs import (
        DEFAULT_NET_FRACTION,
        trading_positions_to_neutral_frtb,
    )
    from src.data_generation.portfolio_generator import PortfolioGenerator

    g = PortfolioGenerator(seed=20260319)
    tp = (g.generate_trading_portfolio() if hasattr(g, "generate_trading_portfolio")
          else g.generate_trading_book())  # type: ignore[attr-defined]
    s, d = trading_positions_to_neutral_frtb(tp.positions, np.random.default_rng(20260319),
                                             DEFAULT_NET_FRACTION)
    rr = [RRAOPositionInput(position_id="W", gross_notional=2000, category=RRAOCategory.EXOTIC)]
    sg = SGMarketRisk(reporting_currency="USD").market_risk(s, d, rr)  # type: ignore[arg-type]
    bc = BCBSMarketRisk().market_risk(s, d, rr)  # type: ignore[arg-type]
    assert sg.rwa > 0
    # No sovereign / PSE DRC names, no inflation / xccy, no SGD or unlisted-currency GIRR in
    # this book, and BCBS engine defaults exercise the sqrt(2) discretions MAS mandates:
    assert sg.sbm_total == pytest.approx(bc.sbm_total)
    assert sg.drc_total == pytest.approx(bc.drc_total)
    assert sg.rwa == pytest.approx(bc.rwa)
