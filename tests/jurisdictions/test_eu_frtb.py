"""Tests for the EU market-risk (FRTB) package -- CRR Title IV as amended by CRR3.

Table cells are checked against the transcription in docs/jurisdictions/EU_frtb_reference.md;
hand-worked examples recompute the Article 325f-325h, 325g, 325w-325ad and 325u formulas
independently of the engine.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.eu.frtb import EUMarketRisk
from src.jurisdictions.eu.frtb import buckets as bk
from src.jurisdictions.eu.frtb import drc as drc_mod
from src.jurisdictions.eu.frtb import params as p
from src.jurisdictions.eu.frtb import sbm as sbm_mod
from src.jurisdictions.eu.frtb.ssa import (
    SSACommodityPosition,
    SSADebtPosition,
    SSAEquityPosition,
    SSAFXPosition,
    SSAInputs,
    SSASpecificCategory,
    commodity_requirement,
    fx_requirement,
    general_risk_maturity,
    specific_risk_rate,
)
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

R = FRTBRiskClass
M = FRTBMeasure
SQRT2 = math.sqrt(2.0)


@pytest.fixture
def calc() -> EUMarketRisk:
    return EUMarketRisk(as_of=date(2026, 10, 29))


def girr(value: float, tenor: float, ccy: str = "USD", **kw: object) -> FRTBSensitivity:
    return FRTBSensitivity(risk_class=R.GIRR, measure=M.DELTA, value=value, currency=ccy,
                           tenor_years=tenor, **kw)


def csr(value: float, issuer: str, sector: CreditSector, rating: RatingBucket,
        tenor: float = 5.0, measure: FRTBMeasure = M.DELTA, **kw: object) -> FRTBSensitivity:
    return FRTBSensitivity(risk_class=R.CSR_NONSEC, measure=measure, value=value, issuer=issuer,
                           credit_sector=sector, rating=rating, tenor_years=tenor, **kw)


def equity(value: float, issuer: str, sector: EquitySector, large: bool = True,
           advanced: bool = True, **kw: object) -> FRTBSensitivity:
    return FRTBSensitivity(risk_class=R.EQUITY, measure=kw.pop("measure", M.DELTA),  # type: ignore[arg-type]
                           value=value, issuer=issuer, equity_sector=sector,
                           is_large_cap=large, is_advanced_economy=advanced, **kw)


BBB = RatingBucket.BBB_PLUS_TO_BBB_MINUS
AAA = RatingBucket.AAA_TO_AA_MINUS
BB = RatingBucket.BB_PLUS_TO_BB_MINUS
NR = RatingBucket.UNRATED


# =========================================================================
#  Table cells
# =========================================================================


@pytest.mark.parametrize(
    ("tenor", "rw"),
    [(0.25, 0.017), (0.5, 0.017), (1.0, 0.016), (2.0, 0.013), (3.0, 0.012), (5.0, 0.011),
     (10.0, 0.011), (15.0, 0.011), (20.0, 0.011), (30.0, 0.011)],
)
def test_girr_table3(tenor: float, rw: float) -> None:
    """Article 325ae(1) Table 3 (M12)."""
    assert p.GIRR_RW_BY_TENOR[tenor] == rw
    assert bk.girr_delta_rw(girr(1.0, tenor)) == pytest.approx(rw)
    assert bk.girr_delta_rw(girr(1.0, tenor, "EUR")) == pytest.approx(rw / SQRT2)


@pytest.mark.parametrize(
    ("bucket", "rw"),
    [(1, 0.005), (2, 0.005), (3, 0.01), (4, 0.05), (5, 0.03), (6, 0.03), (7, 0.02), (8, 0.015),
     (9, 0.01), (10, 0.025), (11, 0.02), (12, 0.04), (13, 0.12), (14, 0.07), (15, 0.085),
     (16, 0.055), (17, 0.05), (18, 0.12), (19, 0.015), (20, 0.05)],
)
def test_csr_table4(bucket: int, rw: float) -> None:
    """Article 325ah(1) Table 4 (M12)."""
    assert p.CSR_NONSEC_RW[bucket] == rw


@pytest.mark.parametrize(
    ("bucket", "rw"),
    [(1, 0.04), (2, 0.04), (3, 0.04), (4, 0.08), (5, 0.05), (6, 0.04), (7, 0.03), (8, 0.02),
     (9, 0.03), (10, 0.06), (11, 0.13), (12, 0.13), (13, 0.16), (14, 0.10), (15, 0.12),
     (16, 0.12), (17, 0.12), (18, 0.13)],
)
def test_csr_ctp_table6(bucket: int, rw: float) -> None:
    """Article 325ak Table 6 (M12)."""
    assert p.CSR_CTP_RW[bucket] == rw


@pytest.mark.parametrize(
    ("bucket", "rw"),
    [(1, 0.009), (2, 0.015), (3, 0.02), (4, 0.02), (5, 0.008), (6, 0.012), (7, 0.012),
     (8, 0.014), (9, 0.01125), (10, 0.01875), (11, 0.025), (12, 0.025), (13, 0.01),
     (14, 0.015), (15, 0.015), (16, 0.0175), (17, 0.01575), (18, 0.02625), (19, 0.035),
     (20, 0.035), (21, 0.014), (22, 0.021), (23, 0.021), (24, 0.0245), (25, 0.035)],
)
def test_csr_sec_table7(bucket: int, rw: float) -> None:
    """Article 325am(1) Table 7 (M12)."""
    assert p.CSR_SEC_NONCTP_RW[bucket] == pytest.approx(rw)


@pytest.mark.parametrize(
    ("bucket", "spot", "repo"),
    [(1, 0.55, 0.0055), (2, 0.60, 0.006), (3, 0.45, 0.0045), (4, 0.55, 0.0055), (5, 0.30, 0.003),
     (6, 0.35, 0.0035), (7, 0.40, 0.004), (8, 0.50, 0.005), (9, 0.70, 0.007), (10, 0.50, 0.005),
     (11, 0.70, 0.007), (12, 0.15, 0.0015), (13, 0.25, 0.0025)],
)
def test_equity_table8(bucket: int, spot: float, repo: float) -> None:
    """Article 325ap(1) Table 8 (M12)."""
    assert p.EQUITY_RW_SPOT[bucket] == spot
    assert p.EQUITY_RW_REPO[bucket] == pytest.approx(repo)


@pytest.mark.parametrize(
    ("bucket", "rw", "rho"),
    [("1", 0.30, 0.55), ("2", 0.35, 0.95), ("3", 0.60, 0.40), ("3a", 0.40, 0.40),
     ("3b", 0.60, 0.40), ("4", 0.80, 0.80), ("5", 0.40, 0.60), ("6", 0.45, 0.65),
     ("7", 0.20, 0.55), ("8", 0.35, 0.45), ("9", 0.25, 0.15), ("10", 0.35, 0.40),
     ("11", 0.50, 0.15)],
)
def test_commodity_tables_9_10(bucket: str, rw: float, rho: float) -> None:
    """Article 325as Table 9 (CRR3 point (176)) and 325at Table 10."""
    assert p.COMMODITY_RW[bucket] == rw
    assert p.COMMODITY_RHO[bucket] == rho


@pytest.mark.parametrize(
    ("key", "rw"),
    [("GIRR", 1.0), ("CSR_NONSEC", 1.0), ("CSR_SEC_CTP", 1.0), ("CSR_SEC_NONCTP", 1.0),
     ("EQUITY_LARGE_INDEX", 0.7778), ("EQUITY_SMALL_OTHER", 1.0), ("COMMODITY", 1.0),
     ("FX", 1.0)],
)
def test_vega_table1(key: str, rw: float) -> None:
    """Article 325ax(2) Table 1 (CRR3 point (177))."""
    assert p.VEGA_RW[key] == rw


def test_vega_rw_reproduces_former_lh_formula() -> None:
    """The CRR3 vega weights equal min(55 % sqrt(LH/10), 100 %) of the deleted Table 11."""
    for key, lh in p.LIQUIDITY_HORIZON_VEGA_FORMER.items():
        former = min(p.VEGA_RW_SIGMA_FORMER * math.sqrt(lh / 10), 1.0)
        assert former == pytest.approx(p.VEGA_RW[key], abs=1e-4)


@pytest.mark.parametrize(
    ("cqs", "rw"), [(1, 0.005), (2, 0.03), (3, 0.06), (4, 0.15), (5, 0.30), (6, 0.50)]
)
def test_drc_table2(cqs: int, rw: float) -> None:
    """Article 325y(1) Table 2."""
    assert p.DRC_RW_BY_CQS[cqs] == rw


def test_drc_scalars() -> None:
    """Articles 325y(1)-(2), 325w(3), (6), 325aa(1), 325ad(4)."""
    assert (p.DRC_RW_UNRATED, p.DRC_RW_DEFAULTED, p.DRC_RW_ZERO_SA) == (0.15, 1.0, 0.0)
    assert p.DRC_LGD == {"NON_SENIOR": 1.0, "SENIOR": 0.75, "COVERED_BOND": 0.25, "EQUITY": 1.0}
    assert p.DRC_SEC_RW_FACTOR == 0.08
    assert p.DRC_CTP_NEGATIVE_BUCKET_FACTOR == 0.5
    assert len(p.DRC_SEC_ASSET_CLASSES) == 11 and len(p.DRC_SEC_REGIONS) == 4


@pytest.mark.parametrize(
    ("b", "c", "gamma"),
    [(1, 3, 0.75), (2, 4, 0.10), (11, 5, 0.20), (1, 6, 0.25), (2, 7, 0.20), (1, 8, 0.15),
     (1, 9, 0.10), (3, 4, 0.05), (4, 6, 0.15), (4, 7, 0.20), (4, 9, 0.20), (5, 7, 0.25),
     (6, 7, 0.25), (6, 9, 0.15), (7, 9, 0.20), (8, 9, 0.05), (1, 18, 0.0), (1, 19, 0.45),
     (9, 20, 0.45), (18, 19, 0.0), (19, 20, 0.75)],
)
def test_csr_table5_sector(b: int, c: int, gamma: float) -> None:
    """Article 325aj Table 5 (M12) gamma_bc(sector)."""
    assert sbm_mod.gamma_csr_sector(b, c) == gamma
    assert sbm_mod.gamma_csr_sector(c, b) == gamma


@pytest.mark.parametrize(
    ("b", "c", "gamma"),
    [(1, 5, 1.0), (2, 11, 0.5), (5, 14, 0.5), (12, 17, 1.0), (18, 3, 1.0), (19, 4, 1.0),
     (19, 13, 0.5), (20, 13, 1.0), (20, 4, 0.5), (19, 20, 0.5), (1, 11, 0.5)],
)
def test_csr_gamma_rating_crr3(b: int, c: int, gamma: float) -> None:
    """Article 325aj gamma_bc(rating) as replaced by CRR3 point (173)(a)-(d)."""
    assert sbm_mod.gamma_csr_rating(b, c) == gamma


def test_ima_table3_and_scalars(calc: EUMarketRisk) -> None:
    """Article 325bf(6) Table 3, 325bb(1), 325bc(1), 325bd Table 2."""
    ima = calc.ima_parameters()
    assert ima.es_confidence == 0.975 and ima.imcc_rho == 0.5 and ima.multiplier_base == 1.5
    assert {k: ima.backtesting_addons[k] for k in (4, 5, 6, 7, 8, 9, 10)} == {
        4: 0.0, 5: 0.20, 6: 0.26, 7: 0.33, 8: 0.38, 9: 0.42, 10: 0.50}
    assert ima.liquidity_horizons_days["CS_CENTRAL_GOVERNMENT_MEMBER_STATES"] == 20
    assert ima.liquidity_horizons_days["CO_OTHER_VOL"] == 120
    assert ima.ses_rho is None and ima.pla_ks_thresholds is None
    assert calc.multiplication_factor(3) == 1.5
    assert calc.multiplication_factor(7) == pytest.approx(1.83)
    assert calc.multiplication_factor(25) == 2.0


# =========================================================================
#  Bucket assignment edge cases
# =========================================================================


@pytest.mark.parametrize(
    ("sector", "rating", "flags", "bucket"),
    [
        (CreditSector.SOVEREIGN, BB, {"eu_member_state": True}, 1),
        (CreditSector.SOVEREIGN, AAA, {}, 2),
        (CreditSector.SOVEREIGN, NR, {}, 11),
        (CreditSector.LOCAL_GOVERNMENT, BBB, {}, 3),
        (CreditSector.FINANCIAL, BB, {}, 13),
        (CreditSector.BASIC_MATERIALS, BBB, {}, 5),
        (CreditSector.CONSUMER, NR, {}, 15),
        (CreditSector.TECHNOLOGY, AAA, {}, 7),
        (CreditSector.HEALTH_CARE, BB, {}, 17),
        (CreditSector.COVERED_BOND, AAA, {"eu_member_state": True}, 9),
        (CreditSector.COVERED_BOND, AAA, {}, 10),
        (CreditSector.COVERED_BOND, NR, {"issuer_cqs_1_to_3": True}, 4),
        (CreditSector.COVERED_BOND, NR, {}, 13),
        (CreditSector.COVERED_BOND, BB, {}, 13),
        (CreditSector.OTHER, AAA, {}, 18),
        (CreditSector.INDEX, BBB, {}, 19),
        (CreditSector.INDEX, BB, {}, 20),
    ],
)
def test_csr_nonsec_bucket(sector: CreditSector, rating: RatingBucket,
                           flags: dict[str, bool], bucket: int) -> None:
    """Article 325ah(1)-(3) (CRR3 point (171))."""
    s = csr(1.0, "X", sector, rating, flags=flags)
    assert bk.csr_nonsec_bucket(s) == bucket


def test_csr_bucket10_cqs_split() -> None:
    """Table 4 bucket 10: CQS 1 1,5 %; CQS 2-3 2,5 %."""
    s1 = csr(1.0, "X", CreditSector.COVERED_BOND, AAA)
    s2 = csr(1.0, "X", CreditSector.COVERED_BOND, RatingBucket.A_PLUS_TO_A_MINUS)
    assert bk.delta_risk_weight(s1) == 0.015
    assert bk.delta_risk_weight(s2) == 0.025


@pytest.mark.parametrize(
    ("sector", "large", "adv", "index", "bucket"),
    [
        (EquitySector.CONSUMER_HEALTH_UTILITIES, True, False, False, 1),
        (EquitySector.FINANCIALS_REALESTATE_TECH, True, False, False, 4),
        (EquitySector.TELECOM_INDUSTRIALS, True, True, False, 6),
        (EquitySector.MATERIALS_ENERGY, True, True, False, 7),
        (EquitySector.MATERIALS_ENERGY, False, False, False, 9),
        (EquitySector.TELECOM_INDUSTRIALS, False, True, False, 10),
        (EquitySector.OTHER, True, True, False, 11),
        (None, True, True, False, 11),
        (None, True, True, True, 12),
        (None, False, True, True, 13),
    ],
)
def test_equity_bucket(sector: EquitySector | None, large: bool, adv: bool, index: bool,
                       bucket: int) -> None:
    """Article 325ap(1) Table 8 and (4)."""
    s = FRTBSensitivity(risk_class=R.EQUITY, measure=M.DELTA, equity_sector=sector,
                        is_large_cap=large, is_advanced_economy=adv, is_equity_index=index)
    assert bk.equity_bucket(s) == bucket


def test_equity_unknown_size_goes_to_other() -> None:
    s = FRTBSensitivity(risk_class=R.EQUITY, measure=M.DELTA,
                        equity_sector=EquitySector.MATERIALS_ENERGY)
    assert bk.equity_bucket(s) == 11


@pytest.mark.parametrize(
    ("flags", "bucket", "rw"),
    [({}, "3", 0.60), ({"eu_ets_carbon": True}, "3a", 0.40),
     ({"non_eu_ets_carbon": True}, "3b", 0.60)],
)
def test_commodity_carbon_buckets(flags: dict[str, bool], bucket: str, rw: float) -> None:
    """CRR3 point (176): buckets 3, 3a, 3b."""
    s = FRTBSensitivity(risk_class=R.COMMODITY, measure=M.DELTA,
                        commodity_group=CommodityGroup.ENERGY_ELECTRICITY_CARBON, flags=flags)
    assert bk.commodity_bucket(s) == bucket
    assert bk.delta_risk_weight(s) == rw


@pytest.mark.parametrize(
    ("tranche", "asset", "bucket"),
    [(SecTrancheClass.SENIOR_IG, SecAssetClass.RMBS_PRIME, 1),
     (SecTrancheClass.SENIOR_IG, SecAssetClass.CLO_NON_CTP, 8),
     (SecTrancheClass.NON_SENIOR_IG, SecAssetClass.CMBS, 12),
     (SecTrancheClass.HY_NR, SecAssetClass.ABS_AUTO, 23),
     (SecTrancheClass.HY_NR, SecAssetClass.OTHER, 25)],
)
def test_sec_nonctp_bucket(tranche: SecTrancheClass, asset: SecAssetClass, bucket: int) -> None:
    """Article 325am Table 7."""
    s = FRTBSensitivity(risk_class=R.CSR_SEC_NONCTP, measure=M.DELTA, sec_tranche_class=tranche,
                        sec_asset_class=asset)
    assert bk.csr_sec_nonctp_bucket(s) == bucket


def test_ctp_bucket_and_rw() -> None:
    s = FRTBSensitivity(risk_class=R.CSR_SEC_CTP, measure=M.DELTA,
                        credit_sector=CreditSector.FINANCIAL, rating=BB)
    assert bk.csr_ctp_bucket(s) == 13 and bk.delta_risk_weight(s) == 0.16


@pytest.mark.parametrize(
    ("kw", "rw"),
    [({}, 0.15), ({"fx_pair_is_liquid": True}, 0.15 / SQRT2),
     ({"flags": {"erm2_pair": True}}, 0.05), ({"flags": {"eu_constant_pair": True}}, 0.075)],
)
def test_fx_rw(kw: dict[str, object], rw: float) -> None:
    """Article 325av(1), (2)(a), (4), (5)."""
    s = FRTBSensitivity(risk_class=R.FX, measure=M.DELTA, fx_currency="USD", **kw)
    assert bk.fx_delta_rw(s) == pytest.approx(rw)


def test_girr_inflation_liquid_reduction() -> None:
    """Article 325ae(3)(b) as replaced by CRR3: inflation RW / sqrt(2) for liquid currencies."""
    eur = FRTBSensitivity(risk_class=R.GIRR, measure=M.DELTA, currency="EUR",
                          girr_curve=GIRRCurve.INFLATION)
    usd = FRTBSensitivity(risk_class=R.GIRR, measure=M.DELTA, currency="USD",
                          girr_curve=GIRRCurve.INFLATION)
    erm = FRTBSensitivity(risk_class=R.GIRR, measure=M.DELTA, currency="DKK", tenor_years=1.0,
                          flags={"erm2_currency": True})
    assert bk.delta_risk_weight(eur) == pytest.approx(0.016 / SQRT2)
    assert bk.delta_risk_weight(usd) == 0.016
    assert bk.delta_risk_weight(erm) == pytest.approx(0.016 / SQRT2)


def test_domestic_currency_configurable() -> None:
    c = EUMarketRisk(domestic_currency="SEK", as_of=date(2026, 1, 1))
    assert c.risk_weight(girr(1.0, 1.0, "SEK")) == pytest.approx(0.016 / SQRT2)
    assert c.risk_weight(girr(1.0, 1.0, "EUR")) == pytest.approx(0.016)


def test_vega_and_curvature_rw() -> None:
    large = equity(1.0, "A", EquitySector.TELECOM_INDUSTRIALS, measure=M.VEGA)
    small = equity(1.0, "A", EquitySector.TELECOM_INDUSTRIALS, large=False, measure=M.VEGA)
    assert bk.risk_weight(large) == 0.7778 and bk.risk_weight(small) == 1.0
    curv = FRTBSensitivity(risk_class=R.GIRR, measure=M.CURVATURE, currency="USD")
    assert bk.risk_weight(curv) == 0.017


# =========================================================================
#  SBM hand-worked examples
# =========================================================================


def test_scenario_transform() -> None:
    """Article 325h(2)."""
    assert sbm_mod.scenario_correlation(0.5, "MEDIUM") == 0.5
    assert sbm_mod.scenario_correlation(0.5, "HIGH") == 0.625
    assert sbm_mod.scenario_correlation(0.5, "LOW") == pytest.approx(0.375)
    assert sbm_mod.scenario_correlation(0.9, "HIGH") == 1.0
    assert sbm_mod.scenario_correlation(0.9, "LOW") == pytest.approx(0.8)


def test_girr_tenor_correlation() -> None:
    """Article 325af(2): theta 3 %, floor 40 %."""
    assert sbm_mod.girr_tenor_correlation(1.0, 5.0) == pytest.approx(math.exp(-0.12))
    assert sbm_mod.girr_tenor_correlation(0.25, 30.0) == 0.40


def test_single_bucket_csr_delta(calc: EUMarketRisk) -> None:
    """Two issuers in bucket 5, same tenor and basis: rho = 35 % (Article 325ai)."""
    s = [csr(100.0, "X", CreditSector.BASIC_MATERIALS, BBB),
         csr(50.0, "Y", CreditSector.BASIC_MATERIALS, BBB)]
    out = calc.sbm_outcome(s)
    ws1, ws2 = 3.0, 1.5
    for scen, rho in (("MEDIUM", 0.35), ("HIGH", 0.4375), ("LOW", 0.2625)):
        expect = math.sqrt(ws1 ** 2 + ws2 ** 2 + 2 * rho * ws1 * ws2)
        assert out.by_scenario[scen][R.CSR_NONSEC][M.DELTA] == pytest.approx(expect)
    assert out.binding_scenario == "HIGH"
    assert calc.sbm_capital(s)[0].total == pytest.approx(math.sqrt(11.25 + 2 * 0.4375 * 4.5))


def test_two_bucket_equity_with_gamma(calc: EUMarketRisk) -> None:
    """Buckets 5 and 6, gamma = 15 % (Article 325ar(a)); hedged -> LOW scenario binds."""
    s = [equity(100.0, "A", EquitySector.CONSUMER_HEALTH_UTILITIES),
         equity(-50.0, "B", EquitySector.TELECOM_INDUSTRIALS)]
    out = calc.sbm_outcome(s)
    k5, k6 = 30.0, 17.5
    for scen, g in (("MEDIUM", 0.15), ("HIGH", 0.1875), ("LOW", 0.1125)):
        expect = math.sqrt(k5 ** 2 + k6 ** 2 + 2 * g * 30.0 * -17.5)
        assert out.by_scenario[scen][R.EQUITY][M.DELTA] == pytest.approx(expect)
    assert out.binding_scenario == "LOW"
    assert all(r.scenario == "LOW" for r in calc.sbm_capital(s))


def test_alternative_sb_specification(calc: EUMarketRisk) -> None:
    """Article 325f(8) (C7): negative sum -> S_b = max(min(Sum WS, K_b), -K_b)."""
    s = [csr(100 / 3, f"L{i}", CreditSector.BASIC_MATERIALS, BBB) for i in range(5)]
    s += [csr(-100 / 7, f"S{i}", CreditSector.BASIC_MATERIALS, BB) for i in range(5)]
    out = calc.sbm_outcome(s)
    kb = math.sqrt(5 + 0.35 * 20)  # WS = +-1 each
    expect = math.sqrt(2 * kb ** 2 - 2 * 0.5 * kb * kb)
    assert out.by_scenario["MEDIUM"][R.CSR_NONSEC][M.DELTA] == pytest.approx(expect)


def test_other_bucket_sum_of_absolutes(calc: EUMarketRisk) -> None:
    """Article 325ai(2): bucket 18 = Sum |WS_k|."""
    s = [csr(10.0, "X", CreditSector.OTHER, NR), csr(-10.0, "Y", CreditSector.OTHER, NR)]
    out = calc.sbm_outcome(s)
    assert out.by_scenario["MEDIUM"][R.CSR_NONSEC][M.DELTA] == pytest.approx(2.4)


def test_sec_nonctp_bucket25_added_linearly(calc: EUMarketRisk) -> None:
    """Article 325ao: gamma 0 and bucket 25 added without diversification."""
    s = [FRTBSensitivity(risk_class=R.CSR_SEC_NONCTP, measure=M.DELTA, value=100.0,
                         tranche_id="T1", tenor_years=1.0,
                         sec_tranche_class=SecTrancheClass.SENIOR_IG,
                         sec_asset_class=SecAssetClass.RMBS_PRIME),
         FRTBSensitivity(risk_class=R.CSR_SEC_NONCTP, measure=M.DELTA, value=100.0,
                         tranche_id="T2", tenor_years=1.0,
                         sec_tranche_class=SecTrancheClass.SENIOR_IG,
                         sec_asset_class=SecAssetClass.CMBS),
         FRTBSensitivity(risk_class=R.CSR_SEC_NONCTP, measure=M.DELTA, value=100.0,
                         tranche_id="T3", tenor_years=1.0)]
    out = calc.sbm_outcome(s)
    expect = math.sqrt(0.9 ** 2 + 2.0 ** 2) + 3.5
    assert out.by_scenario["MEDIUM"][R.CSR_SEC_NONCTP][M.DELTA] == pytest.approx(expect)


def test_girr_erm2_gamma() -> None:
    """Article 325ag(2): 80 % between an ERM II (narrower band) currency and the euro."""
    eng = sbm_mod.EUSBMEngine()
    g = eng._gamma_fn(R.GIRR, {"DKK": {"erm2_narrow_band"}})
    assert g("EUR", "DKK") == 0.8 and g("DKK", "EUR") == 0.8 and g("USD", "DKK") == 0.5


def test_girr_inflation_xccy_correlations() -> None:
    """Article 325af(4)-(5)."""
    rf = {"kind": "RF", "curve": "", "tenor": 1.0}
    inf = {"kind": "INF", "curve": "", "tenor": None}
    xccy = {"kind": "XCCY", "curve": "USD", "tenor": None}
    assert sbm_mod.rho_girr_delta(rf, inf) == 0.40
    assert sbm_mod.rho_girr_delta(rf, xccy) == 0.0
    other = {"kind": "RF", "curve": "OIS2", "tenor": 1.0}
    assert sbm_mod.rho_girr_delta(rf, other) == 0.999


def test_curvature_two_issuers(calc: EUMarketRisk) -> None:
    """Article 325g(4) with rho = 35 %^2 (Article 325ay(5)) and psi."""
    s = [csr(0.0, "X", CreditSector.BASIC_MATERIALS, BBB, measure=M.CURVATURE, cvr_up=10.0,
             cvr_down=4.0),
         csr(0.0, "Y", CreditSector.BASIC_MATERIALS, BBB, measure=M.CURVATURE, cvr_up=-6.0,
             cvr_down=3.0)]
    out = calc.sbm_outcome(s)
    for scen, rho in (("MEDIUM", 0.1225), ("HIGH", 0.153125), ("LOW", 0.091875)):
        kp = math.sqrt(100 + 2 * rho * 10 * -6)
        km = math.sqrt(16 + 9 + 2 * rho * 12)
        assert out.by_scenario[scen][R.CSR_NONSEC][M.CURVATURE] == pytest.approx(max(kp, km))
    assert out.binding_scenario == "LOW"


def test_curvature_psi_both_negative(calc: EUMarketRisk) -> None:
    s = [csr(0.0, "X", CreditSector.FINANCIAL, BBB, measure=M.CURVATURE, cvr_up=-5, cvr_down=-1),
         csr(0.0, "Y", CreditSector.FINANCIAL, BBB, measure=M.CURVATURE, cvr_up=-5, cvr_down=-1)]
    out = calc.sbm_outcome(s)
    assert out.by_scenario["MEDIUM"][R.CSR_NONSEC][M.CURVATURE] == 0.0


def test_curvature_other_bucket_formula(calc: EUMarketRisk) -> None:
    """Article 325g(5): equity bucket 11."""
    s = [equity(0.0, "A", EquitySector.OTHER, measure=M.CURVATURE, cvr_up=3.0, cvr_down=-1.0),
         equity(0.0, "B", EquitySector.OTHER, measure=M.CURVATURE, cvr_up=-2.0, cvr_down=4.0)]
    out = calc.sbm_outcome(s)
    assert out.by_scenario["MEDIUM"][R.EQUITY][M.CURVATURE] == pytest.approx(4.0)


def test_curvature_across_buckets_gamma_squared(calc: EUMarketRisk) -> None:
    """Article 325g(6): RCCR with gamma^2 (equity 15 % -> 2,25 %)."""
    s = [equity(0.0, "A", EquitySector.CONSUMER_HEALTH_UTILITIES, measure=M.CURVATURE,
                cvr_up=8.0, cvr_down=1.0),
         equity(0.0, "B", EquitySector.TELECOM_INDUSTRIALS, measure=M.CURVATURE,
                cvr_up=6.0, cvr_down=2.0)]
    out = calc.sbm_outcome(s)
    expect = math.sqrt(64 + 36 + 2 * 0.0225 * 8 * 6)
    assert out.by_scenario["MEDIUM"][R.EQUITY][M.CURVATURE] == pytest.approx(expect)


def test_fx_curvature_cross_pair_division(calc: EUMarketRisk) -> None:
    """Article 325q(5): CVR components divided by 1,5."""
    s = [FRTBSensitivity(risk_class=R.FX, measure=M.CURVATURE, fx_currency="JPY", cvr_up=3.0,
                         cvr_down=1.5, flags={"fx_curvature_cross_pair": True})]
    assert calc.sbm_outcome(s).by_scenario["MEDIUM"][R.FX][M.CURVATURE] == pytest.approx(2.0)


def test_vega_girr_correlation(calc: EUMarketRisk) -> None:
    """Article 325ay(1): rho = min(rho(option) x rho(underlying), 1), alpha = 1 %."""
    s = [FRTBSensitivity(risk_class=R.GIRR, measure=M.VEGA, value=10.0, currency="USD",
                         option_maturity_years=1.0, underlying_maturity_years=6.0),
         FRTBSensitivity(risk_class=R.GIRR, measure=M.VEGA, value=10.0, currency="USD",
                         option_maturity_years=5.0, underlying_maturity_years=10.0)]
    out = calc.sbm_outcome(s)
    rho = math.exp(-0.01 * 4 / 1) * 1.0  # underlying residuals both 5y
    assert out.by_scenario["MEDIUM"][R.GIRR][M.VEGA] == pytest.approx(
        math.sqrt(200 + 2 * rho * 100))


def test_vega_equity_correlation(calc: EUMarketRisk) -> None:
    """Article 325ay(2): rho = min(rho_delta x rho_option, 1); large cap RW 77,78 %."""
    s = [equity(10.0, "A", EquitySector.TELECOM_INDUSTRIALS, measure=M.VEGA,
                option_maturity_years=1.0),
         equity(10.0, "B", EquitySector.TELECOM_INDUSTRIALS, measure=M.VEGA,
                option_maturity_years=3.0)]
    out = calc.sbm_outcome(s)
    ws = 7.778
    rho = 0.25 * math.exp(-0.01 * 2 / 1)
    assert out.by_scenario["MEDIUM"][R.EQUITY][M.VEGA] == pytest.approx(
        math.sqrt(2 * ws ** 2 + 2 * rho * ws ** 2))


def test_repo_vega_skipped(calc: EUMarketRisk) -> None:
    s = [equity(10.0, "A", EquitySector.TELECOM_INDUSTRIALS, measure=M.VEGA,
                equity_risk_factor=EquityRiskFactor.REPO)]
    out = calc.sbm_outcome(s)
    assert out.total == 0.0 and any("325o(3)" in n for n in out.notes)


def test_equity_spot_repo_same_name() -> None:
    a = {"name": "A", "factor": "SPOT"}
    b = {"name": "A", "factor": "REPO"}
    c = {"name": "B", "factor": "REPO"}
    assert sbm_mod.rho_equity("5", a, b) == 0.999
    assert sbm_mod.rho_equity("5", a, c) == pytest.approx(0.25 * 0.999)


def test_commodity_correlation() -> None:
    """Article 325at(2): commodity x tenor x basis."""
    a = {"name": "WTI", "tenor": 1.0, "basis": "Cushing"}
    b = {"name": "Brent", "tenor": 2.0, "basis": "Rotterdam"}
    assert sbm_mod.rho_commodity("2", a, b) == pytest.approx(0.95 * 0.99 * 0.999)
    assert sbm_mod.gamma_commodity("1", "11") == 0.0
    assert sbm_mod.gamma_commodity("3a", "7") == 0.20


# =========================================================================
#  DRC
# =========================================================================


def pos(pid: str, obligor: str, is_long: bool, notional: float, **kw: object) -> DRCPositionInput:
    return DRCPositionInput(position_id=pid, obligor=obligor, is_long=is_long, notional=notional,
                            market_value=kw.pop("market_value", notional), **kw)  # type: ignore[arg-type]


def test_gross_jtd() -> None:
    """Article 325w(1)-(3), (5)-(6)."""
    assert drc_mod.gross_jtd(pos("a", "A", True, 100.0, pnl=-10.0)) == pytest.approx(65.0)
    assert drc_mod.gross_jtd(pos("b", "A", False, 40.0, seniority=DRCSeniority.NON_SENIOR)) == -40
    assert drc_mod.gross_jtd(pos("c", "A", True, 100.0,
                                 seniority=DRCSeniority.COVERED_BOND)) == pytest.approx(25.0)
    assert drc_mod.gross_jtd(pos("d", "A", True, 10.0, pnl=-20.0)) == 0.0
    assert drc_mod.gross_jtd(pos("e", "A", True, 10.0,
                                 flags={"hedged_derivative_closeout": True})) == 0.0


def test_drc_netting_seniority_and_hbr(calc: EUMarketRisk) -> None:
    """Articles 325x(1)-(2), 325y(4): worked example."""
    positions = [
        pos("A1", "A", True, 100.0, pnl=-10.0, maturity_years=2.0, rating=BBB),
        pos("A2", "A", False, 40.0, maturity_years=0.5, rating=BBB,
            seniority=DRCSeniority.NON_SENIOR),
        pos("B1", "B", True, 100.0, seniority=DRCSeniority.NON_SENIOR),
        pos("B2", "B", False, 50.0),
    ]
    res = drc_mod.drc_nonsec(positions)
    assert res.net_jtd["A1"] == pytest.approx(45.0)
    assert res.net_jtd["A2"] == pytest.approx(0.0)
    assert res.net_jtd["B1"] == pytest.approx(100.0)  # senior short cannot offset non-senior long
    assert res.net_jtd["B2"] == pytest.approx(-37.5)
    wts = 145.0 / 182.5
    assert res.hbr["CORPORATES"] == pytest.approx(wts)
    expect = 45 * 0.06 + 100 * 0.15 - wts * 37.5 * 0.15
    assert res.total == pytest.approx(expect)
    assert calc.drc_capital(positions)["nonsec"] == pytest.approx(expect)


def test_drc_maturity_floor_without_offsetting() -> None:
    """Article 325x(3): three-month floor where no offsetting is possible."""
    res = drc_mod.drc_nonsec([pos("x", "X", True, 100.0, maturity_years=0.1, rating=BBB)])
    assert res.net_jtd["x"] == pytest.approx(75.0 * 0.25)


def test_drc_partial_offset_no_floor() -> None:
    """Article 325x(2)(b): plain maturity ratio for offsetting exposures under one year."""
    res = drc_mod.drc_nonsec([
        pos("l", "X", True, 100.0, maturity_years=2.0),
        pos("s", "X", False, 100.0, maturity_years=0.1),
    ])
    assert res.net_jtd["l"] == pytest.approx(75.0 - 7.5)


def test_drc_buckets_and_zero_rw() -> None:
    """Article 325y(2)-(3)."""
    positions = [
        pos("s", "DE", True, 100.0, credit_sector=CreditSector.SOVEREIGN, rating=AAA,
            flags={"zero_sa_risk_weight": True}),
        pos("m", "Paris", True, 100.0, credit_sector=CreditSector.LOCAL_GOVERNMENT, rating=AAA),
        pos("d", "Corp", True, 100.0, is_defaulted=True),
        pos("e", "EqCo", True, 50.0, seniority=DRCSeniority.EQUITY, flags={"cash_equity": True}),
    ]
    res = drc_mod.drc_nonsec(positions)
    assert res.buckets["SOVEREIGNS"] == 0.0
    assert res.buckets["LOCAL_GOVERNMENTS_MUNICIPALITIES"] == pytest.approx(75 * 0.005)
    assert res.buckets["CORPORATES"] == pytest.approx(75 * 1.0 + 50 * 0.15)


def test_drc_sec_nonctp() -> None:
    """Articles 325z-325aa: same pool/tranche offsetting, 8 % x banking-book RW."""
    positions = [
        pos("a", "P1", True, 0.0, market_value=100.0, kind=DRCKind.SEC_NON_CTP, pool_id="P1",
            tranche_id="A", banking_book_risk_weight=0.5, sec_asset_class=SecAssetClass.CMBS,
            region="Europe"),
        pos("b", "P1", False, 0.0, market_value=30.0, kind=DRCKind.SEC_NON_CTP, pool_id="P1",
            tranche_id="A", banking_book_risk_weight=0.5, sec_asset_class=SecAssetClass.CMBS,
            region="Europe"),
        pos("c", "P2", False, 0.0, market_value=20.0, kind=DRCKind.SEC_NON_CTP, pool_id="P2",
            tranche_id="A", banking_book_risk_weight=1.0, sec_asset_class=SecAssetClass.CMBS,
            region="Europe"),
    ]
    res = drc_mod.drc_sec_nonctp(positions)
    assert res.net_jtd["a"] == pytest.approx(70.0)
    bucket = "CMBS|EUROPE"
    wts = 70.0 / 90.0
    assert res.buckets[bucket] == pytest.approx(70 * 0.04 - wts * 20 * 0.08)


def test_drc_sec_bucket_mapping() -> None:
    x = pos("x", "P", True, 0.0, kind=DRCKind.SEC_NON_CTP, region="Mars",
            flags={"sec_sme": True})
    assert drc_mod.sec_bucket(x) == "SME|REST_OF_WORLD"
    y = pos("y", "P", True, 0.0, kind=DRCKind.SEC_NON_CTP, flags={"sec_corporate": True})
    assert drc_mod.sec_bucket(y) == "CORPORATES"


def test_drc_ctp_aggregation() -> None:
    """Article 325ad(3) (CRR3, no floor) and 325ad(4)."""
    positions = [
        pos("l", "I1", True, 0.0, market_value=100.0, kind=DRCKind.CTP, pool_id="I1",
            tranche_id="3-7", banking_book_risk_weight=0.2),
        pos("s", "I2", False, 0.0, market_value=50.0, kind=DRCKind.CTP, pool_id="I2",
            tranche_id="0-3", banking_book_risk_weight=0.4),
    ]
    res = drc_mod.drc_ctp(positions)
    wts = 100.0 / 150.0
    assert res.buckets["I1"] == pytest.approx(1.6)
    assert res.buckets["I2"] == pytest.approx(-wts * 1.6)
    assert res.total == pytest.approx(1.6 - 0.5 * wts * 1.6)


def test_drc_ctp_non_tranched_uses_table2() -> None:
    """Article 325ad(1)(a) as replaced by CRR3 point (169)(a)."""
    x = pos("x", "N", True, 0.0, market_value=10.0, kind=DRCKind.CTP, rating=BB)
    assert drc_mod.ctp_risk_weight(x, []) == 0.15


# =========================================================================
#  RRAO
# =========================================================================


def test_rrao(calc: EUMarketRisk) -> None:
    """Article 325u(3)-(4), (4a)."""
    positions = [
        RRAOPositionInput(position_id="e", gross_notional=1000.0, category=RRAOCategory.EXOTIC),
        RRAOPositionInput(position_id="o", gross_notional=1000.0,
                          category=RRAOCategory.OTHER_RESIDUAL),
        RRAOPositionInput(position_id="l", gross_notional=1000.0, category=RRAOCategory.EXOTIC,
                          flags={"listed": True}),
        RRAOPositionInput(position_id="h", gross_notional=1000.0, category=RRAOCategory.EXOTIC,
                          flags={"eu_rrao_hedge_derogation": True}),
    ]
    assert calc.rrao_capital(positions) == pytest.approx(11.0)
    late = EUMarketRisk(as_of=date(2033, 1, 1))
    assert late.rrao_capital(positions) == pytest.approx(21.0)


# =========================================================================
#  Protocol and totals
# =========================================================================


def test_protocol_conformance(calc: EUMarketRisk) -> None:
    assert isinstance(calc, MarketRiskCalculator)
    assert calc.jurisdiction == Jurisdiction.EU
    assert calc.assign_bucket(girr(1.0, 1.0, "gbp")) == "GBP"


def test_market_risk_totals(calc: EUMarketRisk) -> None:
    sens = [csr(100.0, "X", CreditSector.BASIC_MATERIALS, BBB)]
    drc = [pos("A", "A", True, 100.0, rating=BBB)]
    rr = [RRAOPositionInput(position_id="e", gross_notional=100.0, category=RRAOCategory.EXOTIC)]
    res = calc.market_risk(sens, drc, rr)
    assert res.sbm_total == pytest.approx(3.0)
    assert res.drc_total == pytest.approx(4.5)
    assert res.rrao == pytest.approx(1.0)
    assert res.total_capital == pytest.approx(8.5)
    assert res.rwa == pytest.approx(12.5 * 8.5)
    assert res.citations["rwa"].startswith("CRR Art 92(6)(b)")


def test_targeted_multiplier_bounds() -> None:
    """Article 461a(2)(a): multipliers >= 0 and < 1."""
    with pytest.raises(ValueError):
        EUMarketRisk(targeted_multiplier=1.0)
    c = EUMarketRisk(targeted_multiplier=0.5, as_of=date(2026, 1, 1))
    res = c.market_risk([csr(100.0, "X", CreditSector.BASIC_MATERIALS, BBB)], [], [])
    assert res.total_capital == pytest.approx(1.5)


def test_cash_equity_option_validated() -> None:
    with pytest.raises(ValueError):
        EUMarketRisk(cash_equity_maturity_years=0.5)


# =========================================================================
#  IMA helpers
# =========================================================================


def test_partial_es() -> None:
    """Article 325bc(1)(c)."""
    pes = EUMarketRisk.partial_es({10: 10.0, 20: 5.0, 40: 4.0, 60: 3.0, 120: 2.0})
    assert pes == pytest.approx(math.sqrt(100 + 25 + 32 + 18 + 24))


def test_imcc_and_aima() -> None:
    """Articles 325bb(1), 325ba(1), 325ba(3)."""
    assert EUMarketRisk.imcc(10.0, [6.0, 8.0]) == pytest.approx(12.0)
    assert EUMarketRisk.unconstrained_es(5.0, 4.0, 6.0) == pytest.approx(7.5)
    assert EUMarketRisk.aima_capital(10.0, 2.0, 8.0, 1.0, 6) == pytest.approx(1.76 * 8 + 1)
    assert EUMarketRisk.aima_total(100.0, 5.0, 50.0, 140.0, 120.0) == pytest.approx(140.0)
    assert EUMarketRisk.aima_total(100.0, 0.0, 20.0, 200.0, 80.0) == pytest.approx(140.0)


# =========================================================================
#  Simplified standardised approach
# =========================================================================


@pytest.mark.parametrize(
    ("cat", "mat", "rate"),
    [(SSASpecificCategory.ZERO_RW, 5.0, 0.0), (SSASpecificCategory.QUALIFYING, 0.5, 0.0025),
     (SSASpecificCategory.QUALIFYING, 2.0, 0.01), (SSASpecificCategory.QUALIFYING, 3.0, 0.016),
     (SSASpecificCategory.RW_100, 1.0, 0.08), (SSASpecificCategory.RW_150, 1.0, 0.12),
     (SSASpecificCategory.COVERED_BOND_10PCT, 3.0, 0.008)],
)
def test_ssa_specific_table1(cat: SSASpecificCategory, mat: float, rate: float) -> None:
    """Article 336(1) Table 1 and 336(3)."""
    d = SSADebtPosition(position_id="x", amount=1.0, category=cat, residual_maturity_years=mat)
    assert specific_risk_rate(d) == pytest.approx(rate)


def test_ssa_general_risk_maturity_ladder() -> None:
    """Article 339: zone-1 long vs zone-3 short -> 150 % matched + 100 % residual."""
    debt = [
        SSADebtPosition(position_id="l", amount=100.0, residual_maturity_years=0.5, coupon=0.05),
        SSADebtPosition(position_id="s", amount=100.0, is_long=False,
                        residual_maturity_years=6.0, coupon=0.05),
    ]
    assert general_risk_maturity(debt) == pytest.approx(1.5 * 0.4 + 2.85)


def test_ssa_low_coupon_band() -> None:
    """Article 339(4) Table 2: coupon < 3 %, 15 years -> 8,00 %."""
    d = [SSADebtPosition(position_id="x", amount=100.0, residual_maturity_years=15.0,
                         coupon=0.01)]
    assert general_risk_maturity(d) == pytest.approx(8.0)


def test_ssa_fx_and_de_minimis() -> None:
    """Articles 351-352 (CRR3 point (193))."""
    fx = [SSAFXPosition(currency="USD", net_position=30.0),
          SSAFXPosition(currency="GBP", net_position=-20.0),
          SSAFXPosition(currency="JPY", net_position=5.0),
          SSAFXPosition(currency="XAU", net_position=-2.0, is_gold=True),
          SSAFXPosition(currency="EUR", net_position=999.0)]
    assert fx_requirement(fx, "EUR", 1000.0) == pytest.approx(0.08 * 37)
    assert fx_requirement(fx, "EUR", 5000.0) == 0.0


def test_ssa_commodity_methods() -> None:
    """Articles 359-360."""
    simple = [SSACommodityPosition(commodity="Cu", amount=100.0),
              SSACommodityPosition(commodity="Cu", amount=40.0, is_long=False)]
    assert commodity_requirement(simple, "SIMPLIFIED") == pytest.approx(13.2)
    ladder = [SSACommodityPosition(commodity="Cu", amount=100.0, maturity_years=0.05),
              SSACommodityPosition(commodity="Cu", amount=60.0, is_long=False,
                                   maturity_years=0.5)]
    assert commodity_requirement(ladder, "MATURITY_LADDER") == pytest.approx(0.72 + 6.0)
    ladder2 = [SSACommodityPosition(commodity="Au", amount=100.0, maturity_years=0.05,
                                    commodity_type="PRECIOUS_METALS"),
               SSACommodityPosition(commodity="Au", amount=100.0, is_long=False,
                                    maturity_years=0.05, commodity_type="PRECIOUS_METALS")]
    assert commodity_requirement(ladder2, "EXTENDED") == pytest.approx(2 * 100 * 0.01)


def test_ssa_total_multipliers(calc: EUMarketRisk) -> None:
    """Article 325(2) multipliers 1,3 / 3,5 / 1,2 / 1,9 and Article 337 securitisation."""
    inp = SSAInputs(
        debt=[
            SSADebtPosition(position_id="l", amount=100.0, residual_maturity_years=0.5,
                            coupon=0.05, category=SSASpecificCategory.QUALIFYING),
            SSADebtPosition(position_id="s", amount=100.0, is_long=False,
                            residual_maturity_years=6.0, coupon=0.05),
        ],
        equity=[SSAEquityPosition(position_id="e1", issuer="A", amount=100.0),
                SSAEquityPosition(position_id="e2", issuer="B", amount=40.0, is_long=False),
                SSAEquityPosition(position_id="c", issuer="Fund", amount=10.0, is_ciu=True)],
        fx=[SSAFXPosition(currency="USD", net_position=50.0)],
        commodity=[SSACommodityPosition(commodity="Cu", amount=100.0)],
        total_own_funds=100.0,
        commodity_method="SIMPLIFIED",
    )
    res = calc.simplified_standardised(inp)
    assert res.debt_specific == pytest.approx(0.25 + 8.0)
    assert res.debt_general == pytest.approx(3.45)
    assert res.equity_specific == pytest.approx(0.08 * 140)
    assert res.equity_general == pytest.approx(0.08 * 60)
    assert res.ciu == pytest.approx(3.2)
    assert res.fx == pytest.approx(4.0)
    assert res.commodity == pytest.approx(18.0)
    expect = 1.3 * 11.7 + 3.5 * 16.0 + 3.5 * 3.2 + 1.2 * 4.0 + 1.9 * 18.0
    assert res.total == pytest.approx(expect)
    assert res.rwa == pytest.approx(12.5 * expect)


def test_ssa_securitisation_ctp() -> None:
    """Article 337(1), (4) and Article 338(2) (CRR3)."""
    inp = SSAInputs(debt=[
        SSADebtPosition(position_id="a", amount=100.0, is_securitisation=True,
                        banking_book_risk_weight=1.0, residual_maturity_years=0.0),
        SSADebtPosition(position_id="b", amount=50.0, is_securitisation=True, is_long=False,
                        banking_book_risk_weight=1.0, in_correlation_trading_portfolio=True,
                        residual_maturity_years=0.0),
        SSADebtPosition(position_id="c", amount=20.0, is_securitisation=True,
                        banking_book_risk_weight=1.0, in_correlation_trading_portfolio=True,
                        residual_maturity_years=0.0),
    ])
    assert EUMarketRisk.simplified_standardised(inp).securitisation == pytest.approx(8.0 + 4.0)


def test_ssa_eligibility() -> None:
    """Article 325a(1): 10 % of total assets and EUR 500 million."""
    assert EUMarketRisk.ssa_eligible(400.0, 5000.0)
    assert not EUMarketRisk.ssa_eligible(600.0, 10000.0)
    assert not EUMarketRisk.ssa_eligible(400.0, 3000.0)
