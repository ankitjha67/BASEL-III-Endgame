#!/usr/bin/env python3
"""End-to-end run and smoke test of the Basel III Endgame capital engine.

Drives every calculator in ``src/`` on one synthetic Category I G-SIB
portfolio, in dependency order:

    data generation -> SA credit risk (§ __.111) -> off-balance sheet CCFs
    (§ __.112) -> SA-CCR (§ __.114) -> CVA (§ __.222) -> securitization
    SEC-SA (§ __.133) -> operational risk (§ __.150) -> FRTB SBM / DRC / RRAO
    (§ __.206-__.211) -> ECL / CECL -> RWA aggregation -> capital stack ->
    ratios, buffers and PCA -> G-SIB surcharge -> large exposures ->
    CCAR stress test -> FR Y-9C / FFIEC 101 / FR Y-15 / FR Y-14 ->
    Pillar 3 package.

Each stage is a smoke test: it must run without error and its headline
result must fall inside a plausibility band.  Results are written to
``output/reports/e2e/`` as ``e2e_results.json``, ``E2E_Report.md`` and
``E2E_Results.xlsx``.

All monetary amounts in USD millions ($M).  The portfolio is synthetic and
seeded; the figures illustrate the engine, they are not a real bank.

Usage::

    python scripts/run_end_to_end.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# --------------------------------------------------------------------------
#  Engine imports
# --------------------------------------------------------------------------
from src.capital.capital_components import (  # noqa: E402
    AT1Instrument,
    CapitalTier,
    CommonEquityInputs,
    DeductionCategory,
    DeductionItem,
    InstrumentType,
    LeverageExposureInputs,
    ThresholdDeductionInputs,
    Tier2Instrument,
    compute_total_capital,
)
from src.capital.capital_ratios import compute_capital_adequacy  # noqa: E402
from src.capital.gsib.gsib_params import GSIBRuleVersion  # noqa: E402
from src.jurisdictions.base import Jurisdiction, OpRiskInputs  # noqa: E402
from src.jurisdictions.comparison import (  # noqa: E402
    ComparisonResult,
    FloorSensitivityRow,
    banking_book_large_exposures,
    build_reference_book,
    floor_sensitivity,
    reference_securitisations,
    run_comparison,
)
from src.jurisdictions.frtb_base import RRAOCategory as NeutralRRAOCategory  # noqa: E402
from src.jurisdictions.frtb_base import RRAOPositionInput  # noqa: E402
from src.jurisdictions.pillar1_base import CCPExposureInput, LeverageInputs  # noqa: E402
from src.data_generation.frtb_inputs import (  # noqa: E402
    DEFAULT_NET_FRACTION,
    trading_positions_to_frtb_inputs,
    trading_positions_to_neutral_frtb,
)
from src.capital.gsib.gsib_calculator import (  # noqa: E402
    calculate_gsib_surcharge,
    create_indicator_data_from_dict,
)
from src.capital.rwa_aggregator import (  # noqa: E402
    CVARiskRWAInput,
    CreditRiskExposureType,
    CreditRiskRWAItem,
    MarketRiskRWAInput,
    OperationalRiskRWAInput,
    aggregate_credit_risk_rwa,
    aggregate_rwa,
    build_ffiec_101_schedule_a,
)
from src.core.enums import (  # noqa: E402
    RRAOCategory,
)
from src.core.models import RRAOPosition  # noqa: E402
from src.counterparty_risk.saccr.saccr import (  # noqa: E402
    SACCRCalculator,
    SACCRNettingSet,
    SACCRTrade,
)
from src.credit_risk.large_exposures import (  # noqa: E402
    CounterpartyCategory,
    CounterpartyExposure as LECounterpartyExposure,
    ExposureType as LEExposureType,
    LargeExposureCalculator,
)
from src.credit_risk.sa.calculator import CreditExposure, SACRCalculator  # noqa: E402
from src.credit_risk.sa.exposure_classes import CRESubType, ExposureClass  # noqa: E402
from src.credit_risk.sa.obs_ccf import OBSCategory, OBSCCFCalculator, OBSExposure  # noqa: E402
from src.credit_risk.sa.risk_weights import BankGrade, get_bank_risk_weight  # noqa: E402
from src.cva_risk.cva_calculator import CVACalculator, CVACounterparty  # noqa: E402
from src.cva_risk.cva_params import CVACreditQuality, CVASector  # noqa: E402
from src.data_generation.portfolio_generator import PortfolioGenerator  # noqa: E402
from src.ecl.ecl_calculator import ECLCalculator, ECLExposure  # noqa: E402
from src.market_risk.frtb.calculator import FRTBCalculator  # noqa: E402
from src.operational_risk.or_calculator import (  # noqa: E402
    BusinessIndicatorInputs,
    OpRiskCalculator,
    ServiceLineData,
)
from src.operational_risk.or_params import ServiceLine  # noqa: E402
from src.pillar3.disclosure_engine import (  # noqa: E402
    DisclosureCapitalData,
    DisclosureLeverageData,
    DisclosureMarketRiskData,
    DisclosureRWAData,
    generate_disclosure_package,
)
from src.pillar3.pillar3_params import DisclosureFrequency  # noqa: E402
from src.reporting.report_engine import ReportEngine  # noqa: E402
from src.securitization.sec_framework import (  # noqa: E402
    SecuritizationCalculator,
    SecuritizationPool,
    SecuritizationTranche,
)
from src.stress_testing.capital_projector import CapitalProjector  # noqa: E402
from src.stress_testing.scenario_engine import ScenarioEngine  # noqa: E402
from src.stress_testing.stress_params import ScenarioType  # noqa: E402
from src.stress_testing.stress_results import compute_stress_test_results  # noqa: E402

SEED = 20260319
REPORTING_DATE = date(2026, 6, 30)
ENTITY = "First National Banking Corp (synthetic)"

# Synthetic-input calibration (NOT regulatory parameters). The generator's
# trading positions are outright and unhedged; a dealer book is mostly
# hedged, so the net sensitivities fed to the SBM are this fraction of the
# generator's gross sensitivities. Chosen so FRTB capital lands in the range
# a Category I firm reports (~$10-25B).
TRADING_NET_FRACTION = DEFAULT_NET_FRACTION
# Derivative trade maturities: lognormal around this median (years), which
# mirrors the short-dated skew of dealer books (most notional < 5y).
DERIV_MEDIAN_MATURITY_YEARS = 2.5

# Synthetic securitisation book (investor positions; NOT regulatory parameters):
# (deal, pool size $M, pool K_SA, delinquent share W) and
# (tranche, attachment, detachment, senior, external rating).
SEC_DEALS = [("RMBS-1", 15_000.0, 0.035, 0.02), ("RMBS-2", 10_000.0, 0.030, 0.03),
             ("CMBS-1", 8_000.0, 0.080, 0.04), ("CLO-1", 10_000.0, 0.080, 0.03),
             ("CLO-2", 7_000.0, 0.080, 0.05)]
SEC_TRANCHES = [("SNR", 0.20, 1.00, True, "AAA"), ("MEZ", 0.08, 0.20, False, "A"),
                ("JNR", 0.03, 0.08, False, "BB")]
SEC_POOL_N_EFFECTIVE = 500.0
SEC_TRANCHE_MATURITY_YEARS = 5.0

# Residual-risk positions (gross notional $M): one exotic, one book of other residual risks.
RRAO_BOOK = [("WEATHER-1", 2_000.0, "EXOTIC"), ("BERMUDAN-BOOK", 60_000.0, "OTHER")]

# Synthetic balance-sheet items for the multi-jurisdiction leverage and CCP comparison.
TOTAL_ASSETS = 3_200_000.0
SFT_GROSS_ASSETS = 220_000.0
CENTRAL_BANK_RESERVES = 320_000.0
# (CCP, qualifying, trade exposure, client-cleared via member, default fund contribution,
#  K_CCP, total prefunded default fund) -- $M
CCP_BOOK = [("CCP-A", True, 45_000.0, False, 2_500.0, 6_000.0, 40_000.0),
            ("CCP-B", True, 12_000.0, True, 0.0, 4_000.0, 30_000.0),
            ("CCP-C", False, 800.0, False, 60.0, None, None)]

# --------------------------------------------------------------------------
#  Smoke-test bookkeeping
# --------------------------------------------------------------------------


@dataclass
class StageResult:
    """Outcome of one pipeline stage."""

    name: str
    status: str = "NOT RUN"
    seconds: float = 0.0
    headline: str = ""
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    error: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


class Pipeline:
    """Runs stages, captures timings, checks and errors."""

    def __init__(self) -> None:
        self.stages: list[StageResult] = []
        self.data: dict[str, Any] = {}

    def run(self, name: str, fn: Callable[[StageResult], None]) -> None:
        st = StageResult(name=name)
        t0 = time.perf_counter()
        try:
            fn(st)
            st.status = "PASS" if all(ok for _, ok, _ in st.checks) else "FAIL"
        except Exception as exc:  # noqa: BLE001 - smoke test records every failure
            st.status = "ERROR"
            st.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        st.seconds = time.perf_counter() - t0
        self.stages.append(st)
        mark = {"PASS": "PASS ", "FAIL": "FAIL ", "ERROR": "ERROR"}[st.status]
        print(f"  [{mark}] {name:<40} {st.seconds:6.2f}s  {st.headline}")
        for label, ok, detail in st.checks:
            if not ok:
                print(f"           check failed: {label} ({detail})")
        if st.error:
            print("           " + st.error.splitlines()[0])


def check(st: StageResult, label: str, value: float, lo: float, hi: float, fmt: str = ",.0f") -> None:
    """Record a plausibility-band check on a numeric result."""
    ok = (lo <= value <= hi) and math.isfinite(value)
    st.checks.append((label, ok, f"{value:{fmt}} in [{lo:{fmt}}, {hi:{fmt}}]"))


# --------------------------------------------------------------------------
#  Portfolio construction
# --------------------------------------------------------------------------

def build_portfolio(p: Pipeline, st: StageResult) -> None:
    gen = PortfolioGenerator(seed=SEED) if "seed" in PortfolioGenerator.__init__.__code__.co_varnames else PortfolioGenerator()
    credit = gen.generate_credit_portfolio()
    trading = gen.generate_trading_portfolio()
    p.data["gen_credit"] = credit
    p.data["gen_trading"] = trading
    p.data["rng"] = np.random.default_rng(SEED)
    st.headline = (f"{credit.count:,} credit exposures (${credit.total_ead:,.0f}M EAD), "
                   f"{len(trading.positions)} trading positions")
    check(st, "credit EAD $M", credit.total_ead, 1_000_000, 3_000_000)
    check(st, "trading positions", len(trading.positions), 50, 1_000)


# --------------------------------------------------------------------------
#  Credit risk
# --------------------------------------------------------------------------

_GEN_TO_CLASS: dict[str, ExposureClass] = {
    "SOVEREIGN": ExposureClass.SOVEREIGN,
    "AGENCY_MBS": ExposureClass.GSE,
    "CORPORATE_IG": ExposureClass.CORPORATE,
    "CORPORATE_HY": ExposureClass.CORPORATE,
    "RETAIL_MORTGAGE": ExposureClass.RESIDENTIAL_MORTGAGE,
    "RETAIL_REVOLVING": ExposureClass.RETAIL_TRANSACTOR,
    "CRE": ExposureClass.COMMERCIAL_REAL_ESTATE,
    "OTHER": ExposureClass.OTHER,
}

_CLASS_TO_FFIEC: dict[ExposureClass, tuple[CreditRiskExposureType, str]] = {
    ExposureClass.SOVEREIGN: (CreditRiskExposureType.SOVEREIGN, "1a"),
    ExposureClass.GSE: (CreditRiskExposureType.PUBLIC_SECTOR_ENTITY, "1c"),
    ExposureClass.BANK: (CreditRiskExposureType.DEPOSITORY_INSTITUTION, "2"),
    ExposureClass.CORPORATE: (CreditRiskExposureType.CORPORATE, "3a"),
    ExposureClass.RESIDENTIAL_MORTGAGE: (CreditRiskExposureType.RETAIL_RESIDENTIAL, "4a"),
    ExposureClass.RETAIL_TRANSACTOR: (CreditRiskExposureType.RETAIL_TRANSACTOR, "4d"),
    ExposureClass.RETAIL: (CreditRiskExposureType.RETAIL_OTHER, "4c"),
    ExposureClass.COMMERCIAL_REAL_ESTATE: (CreditRiskExposureType.OTHER_ASSETS, "8a"),
    ExposureClass.DEFAULTED: (CreditRiskExposureType.OTHER_ASSETS, "8c"),
    ExposureClass.OTHER: (CreditRiskExposureType.OTHER_ASSETS, "8b"),
    ExposureClass.EQUITY: (CreditRiskExposureType.EQUITY, "5"),
}


def run_credit(p: Pipeline, st: StageResult) -> None:
    rng = p.data["rng"]
    exposures: list[CreditExposure] = []
    for e in p.data["gen_credit"].exposures:
        ec = _GEN_TO_CLASS[e.exposure_type]
        kw: dict[str, Any] = {}
        if ec == ExposureClass.SOVEREIGN:
            kw["is_us_sovereign"] = True
        if ec == ExposureClass.RETAIL_TRANSACTOR:
            kw["is_transactor"] = True
        if e.exposure_type == "CORPORATE_IG":
            kw["is_investment_grade"] = True
        if ec in (ExposureClass.RESIDENTIAL_MORTGAGE, ExposureClass.COMMERCIAL_REAL_ESTATE):
            # generator LTVs are U(0, 0.8); stretch to a realistic 30-95% range
            kw["ltv_ratio"] = 0.30 + 0.65 * (e.ltv / 0.8)
        if ec == ExposureClass.COMMERCIAL_REAL_ESTATE:
            kw["cre_sub_type"] = CRESubType.INCOME_PRODUCING
        if e.is_defaulted:
            if ec == ExposureClass.RESIDENTIAL_MORTGAGE:
                kw["is_past_due"] = True
            else:
                ec = ExposureClass.DEFAULTED
        exposures.append(CreditExposure(
            exposure_id=e.exposure_id, exposure_class=ec, counterparty=e.counterparty_name,
            ead=e.ead, maturity_years=e.maturity_years, **kw,
        ))

    # Bank book the generator does not produce: Grade A/B/C interbank placements
    for i in range(80):
        grade = rng.choice([BankGrade.GRADE_A, BankGrade.GRADE_A, BankGrade.GRADE_B, BankGrade.GRADE_C],
                           p=[0.45, 0.35, 0.17, 0.03])
        exposures.append(CreditExposure(
            exposure_id=f"BK-{i:04d}", exposure_class=ExposureClass.BANK, counterparty=f"Bank-{i}",
            ead=float(rng.uniform(500, 3_500)), bank_grade=grade,
            bank_meets_enhanced_criteria=bool(i % 3 == 0 and grade == BankGrade.GRADE_A),
        ))

    res = SACRCalculator().calculate(exposures)
    p.data["credit_result"] = res
    p.data["credit_exposures"] = exposures
    density = res.total_rwa / res.total_ead
    st.headline = (f"EAD ${res.total_ead:,.0f}M  RWA ${res.total_rwa:,.0f}M  "
                   f"density {density:.1%}")
    check(st, "on-balance RWA density", density, 0.20, 0.70, ".2f")
    # Regulatory spot checks against Tables 5 and 2 to § __.111
    by_id = {r.exposure_id: r for r in res.exposure_results}
    mort = [x for x in exposures if x.exposure_class == ExposureClass.RESIDENTIAL_MORTGAGE
            and not x.is_past_due and x.ltv_ratio and x.ltv_ratio <= 0.5]
    if mort:
        check(st, "resi LTV<=50% RW (Table 5)", by_id[mort[0].exposure_id].risk_weight, 0.20, 0.20, ".2f")
    gb = [x for x in exposures if x.exposure_class == ExposureClass.BANK and x.bank_grade == BankGrade.GRADE_B]
    if gb:
        check(st, "bank Grade B RW (Table 2)", by_id[gb[0].exposure_id].risk_weight, 0.75, 0.75, ".2f")


def run_obs(p: Pipeline, st: StageResult) -> None:
    rng = p.data["rng"]
    spec = [  # (category, count, total notional, drawn share, exposure class)
        (OBSCategory.UCC, 400, 420_000.0, 0.0, ExposureClass.RETAIL_TRANSACTOR),
        (OBSCategory.COMMITMENT_GT_1Y, 300, 300_000.0, 0.25, ExposureClass.CORPORATE),
        (OBSCategory.COMMITMENT_LE_1Y, 150, 80_000.0, 0.20, ExposureClass.CORPORATE),
        (OBSCategory.DIRECT_CREDIT_SUB, 80, 55_000.0, 0.0, ExposureClass.CORPORATE),
        (OBSCategory.TRANSACTION_CONTINGENCY, 60, 40_000.0, 0.0, ExposureClass.CORPORATE),
        (OBSCategory.TRADE_LC, 50, 18_000.0, 0.0, ExposureClass.BANK),
    ]
    rw_by_class = {ExposureClass.RETAIL_TRANSACTOR: 0.45, ExposureClass.CORPORATE: 0.65,
                   ExposureClass.BANK: get_bank_risk_weight(BankGrade.GRADE_A)}
    items: list[OBSExposure] = []
    cls_of: dict[str, ExposureClass] = {}
    for cat, n, total, drawn, ec in spec:
        for i in range(n):
            notional = total / n * float(rng.uniform(0.5, 1.5))
            eid = f"{cat.name}-{i}"
            cls_of[eid] = ec
            items.append(OBSExposure(
                exposure_id=eid, obs_category=cat, notional_amount=notional,
                drawn_amount=0.0, original_maturity_years=3.0 if cat != OBSCategory.COMMITMENT_LE_1Y else 0.75,
                is_unconditionally_cancellable=cat == OBSCategory.UCC,
            ))
    res = OBSCCFCalculator().calculate(items, risk_weight_func=lambda x: rw_by_class[cls_of[x.exposure_id]])
    p.data["obs_result"] = res
    st.headline = f"notional ${res.total_notional:,.0f}M  EAD ${res.total_ead:,.0f}M  RWA ${res.total_rwa:,.0f}M"
    check(st, "OBS CCF-weighted EAD / notional", res.total_ead / res.total_notional, 0.10, 0.60, ".2f")
    ccfs = {k: v.get("ccf") for k, v in res.exposures_by_category.items()}
    check(st, "commitment <=1y CCF = 40% (§ __.112(b)(3))", float(ccfs.get("COMMITMENT_LE_1Y", 0)), 0.40, 0.40, ".2f")


def run_saccr(p: Pipeline, st: StageResult) -> None:
    rng = p.data["rng"]
    asset_mix = ["IR", "IR", "IR", "FX", "FX", "CREDIT_IG", "CREDIT_INDEX_IG", "EQUITY_SINGLE",
                 "EQUITY_INDEX", "COMMODITY_OTHER"]
    underlyings = {"IR": ["USD", "EUR", "GBP", "JPY"], "FX": ["EURUSD", "USDJPY", "GBPUSD"],
                   "CREDIT_IG": [f"CORP{i}" for i in range(30)], "CREDIT_INDEX_IG": ["CDX.IG", "ITRAXX.EUR"],
                   "EQUITY_SINGLE": [f"EQ{i}" for i in range(30)], "EQUITY_INDEX": ["SPX", "SX5E"],
                   "COMMODITY_OTHER": ["WTI", "GOLD", "CORN"]}
    calc = SACCRCalculator()
    rows = []
    for k in range(300):
        cpty_type = rng.choice(["BANK", "FINANCIAL", "CORPORATE", "SOVEREIGN"], p=[0.30, 0.30, 0.32, 0.08])
        end_user = cpty_type == "CORPORATE"
        margined = (not end_user) and rng.random() < 0.95
        trades = []
        for t in range(int(rng.integers(4, 12))):
            ac = str(rng.choice(asset_mix))
            notional = float(rng.lognormal(np.log(1_500), 1.0))
            trades.append(SACCRTrade(
                trade_id=f"NS{k}-T{t}", asset_class=ac, notional=notional,
                mtm_value=float(rng.normal(0, 0.01) * notional),
                end_years=float(np.clip(rng.lognormal(np.log(DERIV_MEDIAN_MATURITY_YEARS), 0.8), 0.1, 30.0)),
                is_long=bool(rng.random() < 0.5), underlying=str(rng.choice(underlyings[ac])),
            ))
        v = sum(t.mtm_value for t in trades)
        ns = SACCRNettingSet(
            netting_set_id=f"NS{k:04d}", trades=trades, is_margined=margined,
            collateral=max(v, 0.0) * 0.9 if margined else 0.0, mpor=10, is_financial=not end_user,
        )
        r = calc.calculate(ns)
        rw = {"BANK": 0.40, "FINANCIAL": 1.00, "CORPORATE": 0.65, "SOVEREIGN": 0.0}[cpty_type]
        m = sum(t.notional * t.end_years for t in trades) / sum(t.notional for t in trades)
        rows.append({"netting_set_id": ns.netting_set_id, "counterparty_type": cpty_type,
                     "commercial_end_user": end_user, "margined": margined, "trades": len(trades),
                     "rc": r.replacement_cost, "pfe": r.pfe, "multiplier": r.multiplier,
                     "alpha": r.alpha, "ead": r.ead, "risk_weight": rw, "rwa": r.ead * rw,
                     "notional": sum(t.notional for t in trades), "maturity": m,
                     "mtm": v, "collateral": ns.collateral})
    p.data["saccr_rows"] = rows
    ead = sum(r["ead"] for r in rows)
    rwa = sum(r["rwa"] for r in rows)
    notional = sum(r["notional"] for r in rows)
    st.headline = f"{len(rows)} netting sets  notional ${notional:,.0f}M  EAD ${ead:,.0f}M  RWA ${rwa:,.0f}M"
    check(st, "EAD / notional", ead / notional, 0.002, 0.20, ".3f")
    check(st, "alpha of commercial end-user sets = 1.0", min(r["alpha"] for r in rows if r["commercial_end_user"]), 1.0, 1.0, ".1f")
    check(st, "alpha of financial sets = 1.4", max(r["alpha"] for r in rows if not r["commercial_end_user"]), 1.4, 1.4, ".1f")


def run_cva(p: Pipeline, st: StageResult) -> None:
    rng = p.data["rng"]
    sector = {"BANK": CVASector.FINANCIALS, "FINANCIAL": CVASector.FINANCIALS,
              "CORPORATE": CVASector.CONSUMER_TRANSPORT_ADMIN, "SOVEREIGN": CVASector.SOVEREIGN_MDB_SUPRANATIONAL}
    cps = []
    for r in p.data["saccr_rows"]:
        quality = CVACreditQuality.INVESTMENT_GRADE if rng.random() < 0.8 else CVACreditQuality.SPECULATIVE_GRADE
        cps.append(CVACounterparty(
            counterparty_id=r["netting_set_id"], sector=sector[r["counterparty_type"]],
            credit_quality=quality, is_commercial_end_user=r["commercial_end_user"],
            ead=r["ead"], effective_maturity=r["maturity"],
        ))
    res = CVACalculator().calculate(counterparties=cps)
    p.data["cva_result"] = res
    st.headline = f"{res.approach.value} K ${res.k_cva:,.0f}M  RWA ${res.rwa:,.0f}M  ({res.counterparty_count} counterparties)"
    check(st, "CVA RWA / CCR EAD", res.rwa / max(1.0, sum(r["ead"] for r in p.data["saccr_rows"])), 0.05, 1.50, ".2f")
    check(st, "RWA = 12.5 x K", res.rwa / max(res.k_cva, 1e-9), 12.5, 12.5, ".2f")


def run_securitization(p: Pipeline, st: StageResult) -> None:
    deals = SEC_DEALS
    tranches_spec = [(n, a, d, sr) for n, a, d, sr, _ in SEC_TRANCHES]
    calc = SecuritizationCalculator()
    total_rwa = total_exp = 0.0
    rows = []
    for deal, size, kg, w in deals:
        pool = SecuritizationPool(pool_id=deal, total_ead=size, pool_rwa=size * kg * 12.5,
                                  delinquency_ratio=w, effective_number_of_obligors=SEC_POOL_N_EFFECTIVE)
        trs = [SecuritizationTranche(tranche_id=f"{deal}-{n}", pool_id=deal, attachment_point=a,
                                     detachment_point=d, notional=size * (d - a), is_senior=sr)
               for n, a, d, sr in tranches_spec]
        res = calc.calculate(trs, pool)
        total_rwa += res.total_rwa
        total_exp += sum(t.notional for t in trs)
        for t in trs:
            rows.append({"tranche": t.tranche_id, "A": t.attachment_point, "D": t.detachment_point,
                         "notional": t.notional, "rw": res.rw_by_tranche[t.tranche_id],
                         "rwa": res.rwa_by_tranche[t.tranche_id], "approach": res.approach_used[t.tranche_id],
                         "K_A": res.k_a})
    p.data["sec_rows"] = rows
    p.data["sec_rwa"] = total_rwa
    st.headline = f"{len(rows)} tranches  exposure ${total_exp:,.0f}M  RWA ${total_rwa:,.0f}M"
    check(st, "senior tranche RW floor 15%", min(r["rw"] for r in rows if r["tranche"].endswith("SNR")), 0.15, 0.30, ".2f")
    check(st, "only SEC-SA used (US rule)", float(all(r["approach"] == "SEC-SA" for r in rows)), 1, 1, ".0f")


def run_oprisk(p: Pipeline, st: StageResult) -> None:
    inputs = BusinessIndicatorInputs(
        total_interest_income=[95_000.0, 102_000.0, 115_000.0],
        total_interest_expense=[45_000.0, 52_000.0, 67_000.0],
        interest_earning_assets=list(np.linspace(2_200_000.0, 2_800_000.0, 12)),
        dividend_income=[2_100.0, 2_400.0, 2_700.0],
        total_noninterest_income=[58_000.0, 62_000.0, 68_000.0],
        realized_gains_losses_htm_securities=[300.0, -900.0, 200.0],
        realized_gains_losses_afs_debt_securities=[1_000.0, -800.0, 500.0],
        noninterest_expense_for_bi=[26_000.0, 28_000.0, 31_000.0],
        service_lines=[
            ServiceLineData(service_line=ServiceLine.INVESTMENT_MANAGEMENT,
                            noninterest_income=[9_000.0, 9_800.0, 10_500.0],
                            noninterest_expense_for_bi=[4_800.0, 5_100.0, 5_500.0]),
            ServiceLineData(service_line=ServiceLine.INVESTMENT_SERVICES,
                            noninterest_income=[5_000.0, 5_500.0, 6_000.0],
                            noninterest_expense_for_bi=[2_700.0, 3_000.0, 3_300.0]),
            ServiceLineData(service_line=ServiceLine.NON_LENDING_TREASURY_SERVICES,
                            noninterest_income=[2_000.0, 2_200.0, 2_500.0],
                            noninterest_expense_for_bi=[1_000.0, 1_100.0, 1_200.0]),
        ],
        total_operational_losses=[3_200.0, 4_100.0, 3_500.0],
    )
    res = OpRiskCalculator().calculate(inputs)
    p.data["op_result"] = res
    st.headline = f"BI ${res.business_indicator:,.0f}M  BIC ${res.bic:,.0f}M  RWA ${res.rwa:,.0f}M  ILM {res.ilm:.1f}"
    expected_bic = 4_470.0 + 0.18 * (res.business_indicator - 30_000.0)
    check(st, "BIC = $4.47B + 18% x (BI - $30B)", res.bic, expected_bic - 0.5, expected_bic + 0.5)
    check(st, "RWA = 12.5 x BIC (no ILM)", res.rwa / res.bic, 12.5, 12.5, ".2f")


def run_frtb(p: Pipeline, st: StageResult) -> None:
    """FRTB-SA from the generator's trading book (src.data_generation.frtb_inputs).

    Generator ``delta_sensitivity`` is read as PV01 ($M per bp) for rates
    and credit, and as the $M P&L of a 1% move for equity, commodity and
    FX; sensitivities follow § __.207(b) (divide by 0.0001 or 0.01).
    """
    sens, drc = trading_positions_to_frtb_inputs(p.data["gen_trading"].positions, p.data["rng"],
                                                 TRADING_NET_FRACTION)
    rrao = [RRAOPosition(instrument_id=i, notional=n, category=RRAOCategory[c]) for i, n, c in RRAO_BOOK]
    res = FRTBCalculator().calculate(sensitivities=sens, drc_positions=drc, rrao_positions=rrao)
    p.data["frtb_result"] = res
    p.data["frtb_counts"] = {"sensitivities": len(sens), "drc_positions": len(drc), "rrao_positions": len(rrao)}
    st.headline = (f"{len(sens)} sensitivities  SBM ${res.sbm_total:,.0f}M  DRC ${res.drc_total:,.0f}M  "
                   f"RRAO ${res.rrao_total:,.0f}M  RWA ${res.total_rwa:,.0f}M")
    check(st, "FRTB capital $M", res.total_capital_charge, 1_000, 60_000)
    check(st, "RRAO = 1.0% exotic + 0.1% other", res.rrao_total, 20.0 + 60.0 - 0.01, 80.01)


def run_ecl(p: Pipeline, st: StageResult) -> None:
    rating_map = {"AAA": "AAA", "AA+": "AA", "A": "A", "BBB": "BBB", "BBB-": "BBB", "BB": "BB", "B": "B", "D": "D"}
    exps = []
    for e in p.data["gen_credit"].exposures:
        if e.exposure_type in ("SOVEREIGN", "AGENCY_MBS"):
            continue
        exps.append(ECLExposure(
            exposure_id=e.exposure_id, rating=rating_map.get(e.rating, "BBB"), drawn_amount=e.ead,
            sector={"residential": "residential", "retail": "retail", "cre": "cre"}.get(e.sector, "corporate"),
            remaining_maturity_years=e.maturity_years, is_defaulted=e.is_defaulted,
            pd_current=1.0 if e.is_defaulted else None,
        ))
    res = ECLCalculator().compute_portfolio_ecl(exps)
    p.data["ecl_result"] = res
    st.headline = f"{len(exps):,} loans  EAD ${res.total_ead:,.0f}M  ECL ${res.total_ecl:,.0f}M  coverage {res.coverage_ratio:.2%}"
    check(st, "allowance coverage", res.coverage_ratio, 0.002, 0.06, ".4f")


def run_rwa(p: Pipeline, st: StageResult) -> None:
    cr = p.data["credit_result"]
    items: list[CreditRiskRWAItem] = []
    agg: dict[tuple[CreditRiskExposureType, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    cls_by_id = {e.exposure_id: e.exposure_class for e in p.data["credit_exposures"]}
    for r in cr.exposure_results:
        key = _CLASS_TO_FFIEC.get(cls_by_id[r.exposure_id], (CreditRiskExposureType.OTHER_ASSETS, "8b"))
        agg[key][0] += r.ead
        agg[key][1] += r.rwa
    obs = p.data["obs_result"]
    agg[(CreditRiskExposureType.CORPORATE, "9 OBS")] = [obs.total_ead, obs.total_rwa]
    sac = p.data["saccr_rows"]
    agg[(CreditRiskExposureType.CLEARED_TRANSACTIONS, "10 CCR")] = [sum(r["ead"] for r in sac), sum(r["rwa"] for r in sac)]
    sec_ead = sum(r["notional"] for r in p.data["sec_rows"])
    agg[(CreditRiskExposureType.SECURITIZATION, "6")] = [sec_ead, p.data["sec_rwa"]]
    for (et, line), (ead, rwa) in agg.items():
        items.append(CreditRiskRWAItem(exposure_type=et, exposure_amount=ead, risk_weight=rwa / ead if ead else 0.0,
                                       rwa=rwa, ffiec_101_line=line))
    msa = 9_000.0  # mortgage servicing assets -> 250% (§ __.111(j)(4))
    credit_in = aggregate_credit_risk_rwa(items, msa * 2.50)
    frtb = p.data["frtb_result"]
    market_in = MarketRiskRWAInput(
        total_capital_charge=frtb.total_capital_charge, sbm_charge=frtb.sbm_total, drc_charge=frtb.drc_total,
        rrao_charge=frtb.rrao_total, girr_charge=frtb.girr_charge, csr_nonsec_charge=frtb.csr_nonsec_charge,
        equity_charge=frtb.equity_charge, commodity_charge=frtb.commodity_charge, fx_charge=frtb.fx_charge)
    op = p.data["op_result"]
    op_in = OperationalRiskRWAInput(business_indicator=op.business_indicator, bic=op.bic, ilm=1.0, capital_charge=op.capital_charge)
    cva = p.data["cva_result"]
    cva_in = CVARiskRWAInput(ba_cva_charge=cva.k_ba_cva, sa_cva_charge=cva.k_sa_cva, total_cva_charge=cva.k_cva)
    rwa = aggregate_rwa(credit_in, market_in, op_in, cva_in)
    p.data.update(rwa=rwa, credit_items=items, market_in=market_in, op_in=op_in, cva_in=cva_in, msa=msa)
    p.data["ffiec_a"] = build_ffiec_101_schedule_a(items, rwa)
    st.headline = (f"total RWA ${rwa.total_rwa:,.0f}M  (credit {rwa.credit_risk_rwa / rwa.total_rwa:.0%}, "
                   f"market {rwa.market_risk_rwa / rwa.total_rwa:.0%}, op {rwa.operational_risk_rwa / rwa.total_rwa:.0%}, "
                   f"CVA {rwa.cva_risk_rwa / rwa.total_rwa:.0%})")
    check(st, "total RWA $M", rwa.total_rwa, 800_000, 2_500_000)
    check(st, "output floor not applied", float(rwa.output_floor_applied), 0, 0, ".0f")


def run_capital(p: Pipeline, st: StageResult) -> None:
    equity = CommonEquityInputs(common_stock=25_000.0, surplus=90_000.0, retained_earnings=150_000.0,
                                aoci=-6_000.0, treasury_stock=12_000.0, minority_interest_cet1=1_000.0)
    deductions = [DeductionItem(category=DeductionCategory.GOODWILL, amount=34_000.0, tier=CapitalTier.CET1),
                  DeductionItem(category=DeductionCategory.OTHER_INTANGIBLES, amount=4_000.0, tier=CapitalTier.CET1),
                  DeductionItem(category=DeductionCategory.DTA_CARRYFORWARD, amount=2_000.0, tier=CapitalTier.CET1)]
    thresholds = ThresholdDeductionInputs(significant_investments_cet1=8_000.0,
                                          mortgage_servicing_assets=p.data["msa"], dta_timing_differences=7_000.0)
    at1 = [AT1Instrument(instrument_type=InstrumentType.PREFERRED_NONCUMULATIVE, amount=24_000.0)]
    t2 = [Tier2Instrument(instrument_type=InstrumentType.SUBORDINATED_DEBT, face_amount=30_000.0,
                          current_amount=30_000.0, remaining_maturity_years=8.0)]
    rwa = p.data["rwa"]
    cap = compute_total_capital(equity, deductions, at1, t2, thresholds,
                                total_allowance=p.data["ecl_result"].total_ecl, sa_rwa=rwa.total_rwa)
    lev = LeverageExposureInputs(total_on_balance_sheet=TOTAL_ASSETS, derivative_exposures=sum(r["ead"] for r in p.data["saccr_rows"]),
                                 sft_exposures=SFT_GROSS_ASSETS, off_balance_sheet_items=p.data["obs_result"].total_ead)
    p.data.update(capital=cap, leverage_inputs=lev)
    st.headline = (f"CET1 ${cap.cet1.net_cet1:,.0f}M  T1 ${cap.tier1_capital:,.0f}M  "
                   f"Total ${cap.total_capital:,.0f}M")
    check(st, "CET1 $M", cap.cet1.net_cet1, 120_000, 280_000)
    check(st, "MSAs not deducted (250% RW instead)", cap.cet1.msa_deduction if hasattr(cap.cet1, "msa_deduction") else 0.0, 0, 0)


def run_gsib(p: Pipeline, st: StageResult) -> None:
    """G-SIB surcharge under the 2026 G-SIB NPR, with the current rule shown for comparison.

    STWF is supplied by funding category x remaining maturity (Table 1 to
    § 217.406); keys ``stwf_cat{c}_b{b}``.
    """
    ind = {"total_exposures": 4_100_000.0, "intra_financial_system_assets": 420_000.0,
           "intra_financial_system_liabilities": 380_000.0, "securities_outstanding": 520_000.0,
           "payments_activity": 210_000_000.0, "assets_under_custody": 3_100_000.0,
           "underwriting_activity": 520_000.0, "otc_derivatives_notional": 46_000_000.0,
           "trading_and_afs_securities": 380_000.0, "level_3_assets": 20_000.0,
           "cross_jurisdictional_claims": 1_000_000.0, "cross_jurisdictional_liabilities": 880_000.0,
           # STWF: Cat 1 L1-secured repo / non-financial wholesale; Cat 2 L2A repo;
           # Cat 3 unsecured financial wholesale; Cat 4 other
           "stwf_cat1_b1": 260_000.0, "stwf_cat1_b2": 60_000.0,
           "stwf_cat2_b1": 70_000.0, "stwf_cat2_b2": 20_000.0,
           "stwf_cat3_b1": 120_000.0, "stwf_cat3_b2": 45_000.0, "stwf_cat3_b3": 25_000.0,
           "stwf_cat3_b4": 15_000.0, "stwf_cat4_b1": 30_000.0, "stwf_cat4_b4": 10_000.0,
           "avg_total_assets": 3_200_000.0,
           "avg_risk_weighted_assets": p.data["rwa"].total_rwa}
    data = create_indicator_data_from_dict(ind, reporting_entity=ENTITY, reporting_date=REPORTING_DATE)
    res = calculate_gsib_surcharge(data, total_rwa=p.data["rwa"].total_rwa,
                                   version=GSIBRuleVersion.PROPOSAL_2026)
    cur = calculate_gsib_surcharge(data, total_rwa=p.data["rwa"].total_rwa,
                                   version=GSIBRuleVersion.CURRENT_RULE)
    # final_surcharge_pct is in percent (2.9 = 2.9%); downstream modules take a decimal rate
    p.data.update(gsib=res, gsib_current=cur, gsib_indicators=ind, gsib_rate=res.final_surcharge_rate)
    st.headline = (f"proposal: M1 {res.method1_score_bps:,.0f}bp ({res.method1_surcharge_pct:.1f}%) | "
                   f"M2 {res.method2_score_bps:,.0f}bp ({res.method2_surcharge_pct:.1f}%) -> "
                   f"{res.final_surcharge_pct:.1f}% ({res.binding_method.value}); current rule "
                   f"M2 {cur.method2_score_bps:,.0f}bp -> {cur.final_surcharge_pct:.1f}%")
    check(st, "surcharge between 1.0% and 5.0%", res.final_surcharge_rate, 0.010, 0.050, ".3f")
    check(st, "identified as GSIB (method 1 >= 130 bp)", res.method1_score_bps, 130.0, 2000.0, ".0f")
    check(st, "proposal lowers method 2 score vs current rule",
          res.method2_score_bps / cur.method2_score_bps, 0.0, 0.9999, ".3f")


def run_ratios(p: Pipeline, st: StageResult) -> None:
    """Ratios and buffers, with the SCB taken from the CCAR stage.

    SCB = max(2.5%, severely-adverse peak-to-trough CET1 decline + four
    quarters of planned common dividends / RWA), computed by the capital
    projector; the stress stage therefore runs first.
    """
    scb = p.data["stress"].stress_capital_buffer
    adq = compute_capital_adequacy(p.data["capital"], p.data["rwa"], p.data["leverage_inputs"],
                                   ccyb_rate=0.0, scb_rate=scb, gsib_surcharge=p.data["gsib_rate"])
    p.data["adequacy"] = adq
    r = adq.ratios
    st.headline = (f"CET1 {r.cet1_ratio:.2%}  T1 {r.tier1_ratio:.2%}  Total {r.total_capital_ratio:.2%}  "
                   f"SLR {r.leverage_ratio:.2%}  PCA {adq.pca.category.value}")
    check(st, "CET1 ratio (CLAUDE.md 10-15%)", r.cet1_ratio, 0.10, 0.15, ".4f")
    check(st, "SLR (CLAUDE.md 5-7%)", r.leverage_ratio, 0.05, 0.07, ".4f")
    check(st, "SCB in buffer stack = stress-test SCB", adq.buffers.stress_capital_buffer, scb, scb, ".4f")


def run_large_exposures(p: Pipeline, st: StageResult) -> None:
    rng = p.data["rng"]
    t1 = p.data["capital"].tier1_capital
    exps = [LECounterpartyExposure(
        counterparty_id=f"CP{i}", counterparty_name=f"Counterparty {i}",
        counterparty_category=CounterpartyCategory(rng.choice([c.value for c in CounterpartyCategory])),
        exposure_type=LEExposureType(rng.choice([e.value for e in LEExposureType])),
        gross_exposure=float(t1 * rng.uniform(0.01, 0.20)), collateral_value=float(t1 * rng.uniform(0, 0.03)),
        collateral_haircut=0.15) for i in range(40)]
    s = LargeExposureCalculator(tier1_capital=t1, is_gsib=True).calculate(exps)
    p.data["large_exposures"] = s
    st.headline = (f"{s.total_counterparties} counterparties, {s.reportable_exposures} reportable, "
                   f"{s.limit_breaches} limit breaches, largest {s.largest_exposure_pct:.1%} of T1")
    check(st, "counterparties assessed", float(len(exps)), 40, 40, ".0f")


def run_stress(p: Pipeline, st: StageResult) -> None:
    engine, proj = ScenarioEngine(), CapitalProjector(preferred_dividend_quarterly=400.0)
    rwa = p.data["rwa"].total_rwa
    cet1 = p.data["capital"].cet1.net_cet1
    out = {}
    for s in ScenarioType:
        sc = engine.generate_scenario(s)
        imp = engine.apply_scenario_to_portfolio(sc, 1_100_000.0, rwa, 450_000.0, 3_200_000.0)
        out[s] = proj.project_capital(imp, cet1, rwa, 3_200_000.0, 1_100_000.0)
    res = compute_stress_test_results(out[ScenarioType.BASELINE], out[ScenarioType.ADVERSE],
                                      out[ScenarioType.SEVERELY_ADVERSE], gsib_surcharge=p.data["gsib_rate"],
                                      total_rwa=rwa)
    p.data.update(stress=res, stress_paths=out)
    sa = out[ScenarioType.SEVERELY_ADVERSE]
    st.headline = (f"severely adverse min CET1 {sa.min_cet1_ratio:.2%} (Q{sa.min_cet1_quarter}), "
                   f"SCB {res.stress_capital_buffer:.2%}, pass={res.overall_pass}")
    check(st, "severely adverse min CET1 >= 4.5%", sa.min_cet1_ratio, 0.045, 0.20, ".4f")
    check(st, "SCB floor 2.5%", res.stress_capital_buffer, 0.025, 0.10, ".4f")


def run_reports(p: Pipeline, st: StageResult) -> None:
    proj = {}
    for s, path in p.data["stress_paths"].items():
        proj[s.value] = [{"cet1_capital": q.cet1_capital, "tier1_capital": q.tier1_capital,
                          "total_capital": q.total_capital, "total_rwa": q.total_rwa} for q in path.quarterly_states]
    pkg = ReportEngine(entity_name=ENTITY, rssd_id="0000000").generate_all(
        capital=p.data["capital"], adequacy=p.data["adequacy"], rwa_breakdown=p.data["rwa"],
        reporting_date=REPORTING_DATE, credit_risk_items=p.data["credit_items"], market_risk_input=p.data["market_in"],
        operational_risk_input=p.data["op_in"], cva_risk_input=p.data["cva_in"], indicator_values=p.data["gsib_indicators"],
        stress_projections=proj, is_annual=True)
    p.data["reports"] = pkg
    cv = pkg.cross_validation
    n_checks = len(getattr(cv, "checks", []) or [])
    n_pass = sum(1 for c in (getattr(cv, "checks", []) or []) if getattr(c, "passed", False))
    st.headline = f"reports: {', '.join(pkg.reports_generated)} | cross-validation {n_pass}/{n_checks} | DQ pass={pkg.overall_data_quality_pass}"
    check(st, "four Fed reports generated", float(len(pkg.reports_generated)), 4, 10, ".0f")


def run_pillar3(p: Pipeline, st: StageResult) -> None:
    cap, rwa, frtb = p.data["capital"], p.data["rwa"], p.data["frtb_result"]
    sac = p.data["saccr_rows"]
    capd = DisclosureCapitalData(common_stock=25_000.0, surplus=90_000.0, retained_earnings=150_000.0, aoci=-6_000.0,
                                 treasury_stock=12_000.0, cet1_minority_interest=1_000.0, goodwill_deduction=34_000.0,
                                 other_intangibles_deduction=4_000.0, dta_carryforward_deduction=2_000.0,
                                 at1_instruments=24_000.0, tier2_instruments=30_000.0,
                                 tier2_allowance=cap.tier2.general_allowance)
    rwad = DisclosureRWAData(credit_risk_rwa=rwa.credit_risk_rwa - sum(r["rwa"] for r in sac) - p.data["sec_rwa"],
                             counterparty_credit_risk_rwa=sum(r["rwa"] for r in sac), securitization_rwa=p.data["sec_rwa"],
                             threshold_deductions_rwa=rwa.threshold_250rw_rwa, market_risk_rwa=rwa.market_risk_rwa,
                             operational_risk_rwa=rwa.operational_risk_rwa, cva_risk_rwa=rwa.cva_risk_rwa)
    mrd = DisclosureMarketRiskData(girr_charge=frtb.girr_charge, csr_nonsec_charge=frtb.csr_nonsec_charge,
                                   equity_charge=frtb.equity_charge, commodity_charge=frtb.commodity_charge,
                                   fx_charge=frtb.fx_charge, drc_nonsec_charge=frtb.drc_total, rrao_charge=frtb.rrao_total)
    levd = DisclosureLeverageData(total_consolidated_assets=3_200_000.0, on_balance_sheet_excl_derivatives=3_200_000.0,
                                  derivative_replacement_cost=sum(r["rc"] for r in sac), derivative_pfe=sum(r["pfe"] for r in sac),
                                  sft_gross=220_000.0, off_bs_notional=p.data["obs_result"].total_notional,
                                  off_bs_ccf_adjustment=p.data["obs_result"].total_notional - p.data["obs_result"].total_ead,
                                  tier1_capital=cap.tier1_capital)
    pkg = generate_disclosure_package(REPORTING_DATE, DisclosureFrequency.QUARTERLY, capd, rwad, mrd, levd,
                                      gsib_surcharge=p.data["gsib_rate"], total_rwa=rwa.total_rwa,
                                      entity_name=ENTITY)
    p.data["pillar3"] = pkg
    templates = [k.upper() for k, v in pkg if isinstance(v, BaseModel)]
    st.headline = (f"{len(templates)} templates: {', '.join(templates)}"
                   + (f" | not produced: {', '.join(pkg.missing_templates)}" if pkg.missing_templates else ""))
    check(st, "Pillar 3 templates produced", float(len(templates)), 4, 40, ".0f")


# --------------------------------------------------------------------------
#  Output
# --------------------------------------------------------------------------

def _num(x: Any) -> Any:
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    return x


COMPARISON_YEAR = 2027
"""Reporting year for the cross-jurisdiction run (UK go-live; mid phase-in elsewhere)."""
FULLY_PHASED_YEAR = 2030
"""First year every floor schedule has reached its end-state (EU/UK 72.5% from 2030)."""


def _comparison_op_inputs() -> OpRiskInputs:
    """Business-indicator inputs in the BCBS item structure (OPE10), synthetic, USD $M.

    Consistent with the US stage's FR Y-9C inputs: same interest income,
    expense, earning assets and dividends; noninterest items split into
    fee / other operating income and expense plus trading and banking-book P&L.
    """
    iea = list(np.linspace(2_200_000.0, 2_800_000.0, 12))
    return OpRiskInputs(
        interest_income=[95_000.0, 102_000.0, 115_000.0],
        interest_expense=[45_000.0, 52_000.0, 67_000.0],
        interest_earning_assets=[float(np.mean(iea[i * 4:(i + 1) * 4])) for i in range(3)],
        dividend_income=[2_100.0, 2_400.0, 2_700.0],
        fee_income=[40_000.0, 43_000.0, 47_000.0], fee_expense=[15_000.0, 16_000.0, 17_500.0],
        other_operating_income=[8_000.0, 8_500.0, 9_000.0],
        other_operating_expense=[11_000.0, 12_000.0, 13_500.0],
        net_pnl_trading_book=[10_000.0, 10_500.0, 12_000.0],
        net_pnl_banking_book=[1_300.0, -1_700.0, 700.0],
        annual_operational_losses=[2_400.0, 2_700.0, 3_900.0, 2_600.0, 2_900.0, 3_100.0, 2_800.0,
                                   3_200.0, 4_100.0, 3_500.0],
    )


def _comparison_leverage_inputs(p: Pipeline) -> LeverageInputs:
    """Leverage-ratio inputs shared by every regime (LEV30 structure).

    On-balance assets exclude the derivative replacement cost and SFT assets,
    which enter through their own lines; off-balance items carry the CCF of
    stage 7 (US § __.112), which each regime then applies (LEV30.43-30.47).
    """
    sac = p.data["saccr_rows"]
    rc = sum(r["rc"] for r in sac)
    by_ccf: dict[float, float] = {}
    for v in p.data["obs_result"].exposures_by_category.values():
        by_ccf[float(v["ccf"])] = by_ccf.get(float(v["ccf"]), 0.0) + float(v["notional"])
    return LeverageInputs(
        on_balance_sheet_assets=TOTAL_ASSETS - SFT_GROSS_ASSETS - rc,
        derivative_rc=rc,
        derivative_pfe_addon=sum(r["pfe"] / (r["multiplier"] or 1.0) for r in sac),
        sft_gross_assets=SFT_GROSS_ASSETS,
        obs_notional_by_ccf=by_ccf,
        central_bank_reserves=CENTRAL_BANK_RESERVES,
    )


def run_jurisdictions(p: Pipeline, st: StageResult) -> None:
    """Run the bank through the BCBS, US, UK, EU, Singapore and Canada rulebooks.

    Uses src.jurisdictions.comparison. Every Pillar 1 component is computed under
    each regime's own rules: credit, CCR, CVA, op risk, FRTB (one regime-neutral
    trading book), securitisation (SEC-SA only in the US; SEC-ERBA for rated
    tranches elsewhere, subject to each regime's hierarchy), CCP exposures, the
    leverage exposure measure and large-exposure limits. Capital resources are
    held common. The bank uses standardised approaches, so the floor cannot bind;
    the floor what-if applies each regime's schedule to hypothetical modelled/SA
    ratios (50/60/70%) in 2027 and 2030. The US proposal has no floor.
    """
    book = build_reference_book(p.data["gen_credit"].exposures, p.data["saccr_rows"],
                                _comparison_op_inputs(), seed=SEED)
    sens, drc = trading_positions_to_neutral_frtb(p.data["gen_trading"].positions,
                                                  np.random.default_rng(SEED), TRADING_NET_FRACTION)
    book.frtb_sensitivities, book.drc_positions = sens, drc  # type: ignore[assignment]
    book.rrao_positions = [RRAOPositionInput(
        position_id=i, gross_notional=n,
        category=NeutralRRAOCategory.EXOTIC if c == "EXOTIC" else NeutralRRAOCategory.OTHER_RESIDUAL)
        for i, n, c in RRAO_BOOK]
    book.sec_tranches = reference_securitisations(SEC_DEALS, SEC_TRANCHES, SEC_POOL_N_EFFECTIVE,
                                                  SEC_TRANCHE_MATURITY_YEARS)
    book.ccp_exposures = [CCPExposureInput(
        ccp_id=c, is_qualifying=q, trade_exposure=te, is_client_cleared_via_member=cl,
        initial_margin_bankruptcy_remote=cl, default_fund_contribution=df, k_ccp=kc,
        total_default_fund=tdf) for c, q, te, cl, df, kc, tdf in CCP_BOOK]
    book.leverage = _comparison_leverage_inputs(p)
    book.large_exposures = banking_book_large_exposures(book.exposures)
    cap = p.data["capital"]
    # Stage-10 US FRTB RWA is used only for a regime without its own FRTB calculator
    # (reported in common_components).
    common = dict(capital_usd={"cet1": cap.cet1.net_cet1, "tier1": cap.tier1_capital,
                               "total": cap.total_capital},
                  market_rwa_usd=p.data["frtb_result"].total_rwa,
                  gsib_method1_score_bps=p.data["gsib"].method1_score_bps, us_gsib_rate=p.data["gsib_rate"],
                  us_scb=p.data["stress"].stress_capital_buffer)
    res = run_comparison(book, COMPARISON_YEAR, **common)
    full = run_comparison(book, FULLY_PHASED_YEAR, **common)
    sens_rows = floor_sensitivity(res, (COMPARISON_YEAR, FULLY_PHASED_YEAR))
    p.data.update(jurisdictions=res, jurisdictions_full=full, jurisdiction_book=book, floor_sens=sens_rows)
    st.headline = " | ".join(f"{r.jurisdiction.value} CET1 {r.cet1_ratio:.1%}" for r in res.regimes)
    by = {r.jurisdiction: r for r in res.regimes}
    us_frtb = p.data["frtb_result"].total_rwa
    check(st, "six regimes computed", float(len(res.regimes)), 6, 6, ".0f")
    check(st, "US: no output floor", float(by[Jurisdiction.US].floor_applies), 0, 0, ".0f")
    check(st, "EU floor factor 2027 (Art. 465(1))", by[Jurisdiction.EU].floor_factor, 0.60, 0.60, ".3f")
    check(st, "UK floor factor 2027 (Art. 92(5))", by[Jurisdiction.UK].floor_factor, 0.60, 0.60, ".3f")
    check(st, "CA floor factor (CAR Ch.1 1.5.1)", by[Jurisdiction.CA].floor_factor, 0.675, 0.675, ".3f")
    check(st, "fully phased BCBS/EU/UK/SG floor 72.5%",
          min(r.floor_factor for r in full.regimes if r.jurisdiction in
              (Jurisdiction.BCBS, Jurisdiction.EU, Jurisdiction.UK, Jurisdiction.SG)), 0.725, 0.725, ".3f")
    check(st, "UK/EU op-risk ILM = 1 (UK rule 5.9; CRR Art. 312)",
          max(by[Jurisdiction.UK].op_ilm, by[Jurisdiction.EU].op_ilm), 1.0, 1.0, ".2f")
    check(st, "US adapter FRTB RWA / stage-10 FRTB RWA", by[Jurisdiction.US].market_rwa / us_frtb,
          0.95, 1.05, ".3f")
    check(st, "US securitisation: SEC-SA / 1,250% only (§ __.133)",
          float(all(x["approach"] in ("SEC_SA", "RW_1250") for x in by[Jurisdiction.US].securitisation_rows)),
          1, 1, ".0f")
    check(st, "US adapter sec RWA = stage-8 SEC-SA RWA", by[Jurisdiction.US].securitisation_rwa,
          p.data["sec_rwa"] - 0.5, p.data["sec_rwa"] + 0.5)
    check(st, "UK leverage excludes central bank claims (Art 429a(A1)-(A2))",
          by[Jurisdiction.UK].leverage_exclusions, CENTRAL_BANK_RESERVES - 0.5, CENTRAL_BANK_RESERVES + 0.5)
    check(st, "no large-exposure limit breaches", float(sum(len(r.large_exposure_breaches)
                                                             for r in res.regimes)), 0, 0, ".0f")


def write_outputs(p: Pipeline, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    d = p.data
    summary: dict[str, Any] = {"entity": ENTITY, "reporting_date": REPORTING_DATE.isoformat(), "seed": SEED,
                               "stages": [{"name": s.name, "status": s.status, "seconds": round(s.seconds, 3),
                                           "headline": s.headline, "checks": [{"check": c, "ok": ok, "detail": det}
                                                                              for c, ok, det in s.checks],
                                           "error": s.error} for s in p.stages]}
    if "rwa" in d:
        r = d["rwa"]
        summary["rwa"] = {k: _num(v) for k, v in r.model_dump().items()}
    if "adequacy" in d:
        a = d["adequacy"]
        summary["ratios"] = {k: _num(v) for k, v in a.ratios.model_dump().items()}
        summary["buffers"] = {k: _num(v) for k, v in a.buffers.model_dump().items()}
        summary["pca"] = a.pca.category.value
    if "capital" in d:
        c = d["capital"]
        summary["capital"] = {"cet1": c.cet1.net_cet1, "at1": c.at1.net_at1 if hasattr(c.at1, "net_at1") else None,
                              "tier1": c.tier1_capital, "tier2": c.tier2.net_tier2, "total": c.total_capital}
    if "gsib" in d:
        g = d["gsib"]
        summary["gsib"] = {"method1_bps": g.method1_score_bps, "method2_bps": g.method2_score_bps,
                           "surcharge": g.final_surcharge_pct, "binding": str(g.binding_method)}
    if "jurisdictions" in d:
        summary["jurisdictions"] = {"year": d["jurisdictions"].year, "fx_source": d["jurisdictions"].fx_source,
                                    "common_components": d["jurisdictions"].common_components,
                                    "rows": d["jurisdictions"].table(),
                                    "fully_phased": d["jurisdictions_full"].table()}
    (out / "e2e_results.json").write_text(json.dumps(summary, indent=2, default=str))

    # ---- Excel workbook -------------------------------------------------
    try:
        import pandas as pd

        with pd.ExcelWriter(out / "E2E_Results.xlsx", engine="openpyxl") as w:
            pd.DataFrame([{k: v for k, v in s.items() if k != "checks"} for s in summary["stages"]]).to_excel(w, sheet_name="Smoke_Tests", index=False)
            pd.DataFrame([{"stage": s["name"], **c} for s in summary["stages"] for c in s["checks"]]).to_excel(w, sheet_name="Checks", index=False)
            if "rwa" in summary:
                pd.DataFrame(list(summary["rwa"].items()), columns=["item", "value_$M"]).to_excel(w, sheet_name="RWA", index=False)
            if "ratios" in summary:
                pd.DataFrame(list(summary["ratios"].items()) + list(summary["buffers"].items()),
                             columns=["item", "value"]).to_excel(w, sheet_name="Ratios_Buffers", index=False)
            if "credit_result" in d:
                pd.DataFrame([{"class": k, "ead": d["credit_result"].ead_by_class.get(k), "rwa": v}
                              for k, v in d["credit_result"].rwa_by_class.items()]).to_excel(w, sheet_name="Credit_By_Class", index=False)
            if "saccr_rows" in d:
                pd.DataFrame(d["saccr_rows"]).to_excel(w, sheet_name="SACCR_NettingSets", index=False)
            if "sec_rows" in d:
                pd.DataFrame(d["sec_rows"]).to_excel(w, sheet_name="Securitization", index=False)
            if "frtb_result" in d:
                pd.DataFrame(list(d["frtb_result"].model_dump().items()), columns=["item", "value_$M"]).to_excel(w, sheet_name="FRTB", index=False)
            if "op_result" in d:
                o = d["op_result"]
                pd.DataFrame([("business_indicator", o.business_indicator), ("ildc", o.ildc),
                              ("noninterest_component", o.noninterest_component), ("bic", o.bic),
                              ("ilm", o.ilm), ("rwa", o.rwa)], columns=["item", "value_$M"]).to_excel(w, sheet_name="OpRisk", index=False)
            if "ffiec_a" in d:
                pd.DataFrame(list(d["ffiec_a"].model_dump().items()), columns=["line", "value"]).to_excel(w, sheet_name="FFIEC101_SchedA", index=False)
            if "jurisdictions" in d:
                pd.DataFrame(d["jurisdictions"].table()).to_excel(w, sheet_name="Jurisdictions_2027", index=False)
                pd.DataFrame(d["jurisdictions_full"].table()).to_excel(w, sheet_name="Jurisdictions_2030", index=False)
                pd.DataFrame([{"jurisdiction": r.jurisdiction.value, "class": c, "rwa_$M": v}
                              for r in d["jurisdictions"].regimes for c, v in r.credit_rwa_by_class.items()]
                             ).to_excel(w, sheet_name="Jurisdiction_Credit", index=False)
                pd.DataFrame([{"jurisdiction": r.jurisdiction.value, **x}
                              for r in d["jurisdictions"].regimes for x in r.securitisation_rows]
                             ).to_excel(w, sheet_name="Jurisdiction_Securitisation", index=False)
                pd.DataFrame([{"jurisdiction": r.jurisdiction.value, "risk_class": c, "capital_$M": v}
                              for r in d["jurisdictions"].regimes for c, v in r.market_by_class.items()]
                             ).to_excel(w, sheet_name="Jurisdiction_FRTB", index=False)
                pd.DataFrame([x.model_dump() for x in d["floor_sens"]]).to_excel(
                    w, sheet_name="Output_Floor_WhatIf", index=False)
            if "reports" in d and d["reports"].fr_y9c is not None:
                pd.DataFrame(list(d["reports"].fr_y9c.model_dump().items()), columns=["field", "value"]).astype(str).to_excel(w, sheet_name="FR_Y9C", index=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  (Excel output skipped: {exc})")
    return summary


def write_markdown(p: Pipeline, summary: dict[str, Any], out: Path) -> None:
    d = p.data
    L: list[str] = []
    n_pass = sum(s.passed for s in p.stages)
    L.append("# End-to-end run and smoke test\n")
    L.append(f"Entity: {ENTITY}  ")
    L.append(f"Reporting date: {REPORTING_DATE}  ")
    L.append(f"Seed: {SEED}  ")
    L.append(f"Result: **{n_pass}/{len(p.stages)} stages passed**\n")
    L.append("All amounts in $M. Synthetic, seeded portfolio; figures illustrate the engine and are not a real bank.\n")
    L.append("## Smoke tests\n")
    L.append("| # | Stage | Status | Time (s) | Headline |")
    L.append("|---|---|---|---|---|")
    for i, s in enumerate(p.stages, 1):
        L.append(f"| {i} | {s.name} | {s.status} | {s.seconds:.2f} | {s.headline} |")
    L.append("\n### Plausibility and regulatory checks\n")
    L.append("| Stage | Check | OK | Detail |")
    L.append("|---|---|---|---|")
    for s in p.stages:
        for c, ok, det in s.checks:
            L.append(f"| {s.name} | {c} | {'yes' if ok else '**no**'} | {det} |")
    errs = [s for s in p.stages if s.error]
    if errs:
        L.append("\n### Errors\n")
        for s in errs:
            L.append(f"**{s.name}**\n\n```\n{s.error}\n```")
    if "rwa" in d:
        r = d["rwa"]
        L.append("\n## Risk-weighted assets (FFIEC 101 Schedule A view)\n")
        L.append("| Component | RWA | Share |")
        L.append("|---|---|---|")
        for label, v in [("Credit risk (incl. OBS, CCR, securitization, 250% items)", r.credit_risk_rwa),
                         ("Market risk (FRTB SA)", r.market_risk_rwa), ("Operational risk (12.5 x BIC)", r.operational_risk_rwa),
                         ("CVA risk", r.cva_risk_rwa)]:
            L.append(f"| {label} | {v:,.0f} | {v / r.total_rwa:.1%} |")
        L.append(f"| **Total** | **{r.total_rwa:,.0f}** | 100% |")
    if "adequacy" in d:
        a = d["adequacy"]
        c = d["capital"]
        L.append("\n## Capital and ratios (FR Y-9C HC-R view)\n")
        L.append("| Item | Value |")
        L.append("|---|---|")
        for label, v in [("CET1 capital", c.cet1.net_cet1), ("Tier 1 capital", c.tier1_capital),
                         ("Tier 2 capital", c.tier2.net_tier2), ("Total capital", c.total_capital)]:
            L.append(f"| {label} | {v:,.0f} |")
        rr = a.ratios
        for label, v in [("CET1 ratio", rr.cet1_ratio), ("Tier 1 ratio", rr.tier1_ratio),
                         ("Total capital ratio", rr.total_capital_ratio), ("Supplementary leverage ratio", rr.leverage_ratio)]:
            L.append(f"| {label} | {v:.2%} |")
        b = a.buffers
        bd = b.model_dump()
        for k in ("stress_capital_buffer", "gsib_surcharge", "ccyb", "total_buffer", "cet1_requirement"):
            if k in bd and isinstance(bd[k], (int, float)):
                L.append(f"| {k.replace('_', ' ')} | {bd[k]:.2%} |")
        L.append(f"| PCA category | {a.pca.category.value} |")
        L.append(f"| Meets minimums / buffers | {a.meets_minimum_requirements} / {a.meets_buffer_requirements} |")
    if "frtb_result" in d:
        f = d["frtb_result"]
        L.append("\n## Market risk (FRTB standardized)\n")
        L.append("| Charge | $M |")
        L.append("|---|---|")
        for k in ("girr_charge", "csr_nonsec_charge", "equity_charge", "commodity_charge", "fx_charge",
                  "sbm_total", "drc_total", "rrao_total", "total_capital_charge"):
            v = getattr(f, k, None)
            if v is not None:
                L.append(f"| {k.replace('_', ' ')} | {v:,.1f} |")
    if "op_result" in d:
        o = d["op_result"]
        L.append("\n## Operational risk (§ __.150)\n")
        L.append(f"BI {o.business_indicator:,.0f} = ILDC {o.ildc:,.0f} + noninterest component {o.noninterest_component:,.0f}; "
                 f"BIC {o.bic:,.0f}; RWA {o.rwa:,.0f}; ILM {o.ilm:.1f}.")
    if "cva_result" in d:
        c = d["cva_result"]
        L.append("\n## CVA (§ __.222)\n")
        L.append(f"Approach {c.approach.value}; K_unhedged {c.k_unhedged:,.0f}; K {c.k_cva:,.0f}; RWA {c.rwa:,.0f} over "
                 f"{c.counterparty_count} counterparties with total EAD {c.total_ead:,.0f}.")
    if "gsib" in d:
        g = d["gsib"]
        L.append("\n## G-SIB surcharge\n")
        L.append(f"Method 1 {g.method1_score_bps:,.0f} bp -> {g.method1_surcharge_pct:.1f}%; Method 2 {g.method2_score_bps:,.0f} bp -> "
                 f"{g.method2_surcharge_pct:.1f}%; binding {g.binding_method.value}: **{g.final_surcharge_pct:.1f}%**.")
    if "stress" in d:
        L.append("\n## CCAR stress test (9 quarters)\n")
        L.append("| Scenario | Start CET1 | Min CET1 | Quarter of min | Peak-to-trough |")
        L.append("|---|---|---|---|---|")
        for s, path in d["stress_paths"].items():
            L.append(f"| {s.value} | {path.starting_cet1_ratio:.2%} | {path.min_cet1_ratio:.2%} | Q{path.min_cet1_quarter} | "
                     f"{path.peak_to_trough_cet1:.2%} |")
        L.append(f"\nStress capital buffer {d['stress'].stress_capital_buffer:.2%}; overall pass {d['stress'].overall_pass}.")
    if "reports" in d:
        pkg = d["reports"]
        L.append("\n## Regulatory reports\n")
        L.append(f"Generated: {', '.join(pkg.reports_generated)}. Overall data-quality pass: {pkg.overall_data_quality_pass}.")
        cv = pkg.cross_validation
        checks = getattr(cv, "checks", []) or []
        if checks:
            L.append("\n| Cross-validation check | Passed | Detail |")
            L.append("|---|---|---|")
            for c in checks:
                det = getattr(c, "message", "") or getattr(c, "description", "")
                L.append(f"| {getattr(c, 'check_name', getattr(c, 'name', ''))} | {getattr(c, 'passed', '')} | {str(det)[:100]} |")
    if "jurisdictions" in d:
        L.extend(_jurisdiction_markdown(d["jurisdictions"], d["jurisdictions_full"], d["floor_sens"]))
    (out / "E2E_Report.md").write_text("\n".join(L) + "\n")


def _jurisdiction_markdown(res: ComparisonResult, full: ComparisonResult,
                           sens: list[FloorSensitivityRow]) -> list[str]:
    """Markdown section comparing the six regimes."""
    L = [f"\n## Multi-jurisdiction comparison ({res.year}; end-state rules {full.year})\n",
         "Same synthetic bank under each rulebook. Held common: " + "; ".join(res.common_components) + ".",
         f"FX: {res.fx_source}. The bank uses standardised approaches, so no output floor binds; "
         "see the floor what-if below (US proposal: no floor).\n",
         "| Regime | SA credit RWA | CCR RWA | CVA RWA | Op RWA (ILM) | Market RWA | Sec. RWA | CCP RWA | "
         "Total RWA | Floor factor | CET1 | CET1 req. | Surplus |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res.regimes:
        fl = f"{r.floor_factor:.1%}" if r.floor_applies else "none"
        L.append(f"| {r.jurisdiction.value} | {r.credit_rwa:,.0f} | {r.ccr_rwa:,.0f} | {r.cva_rwa:,.0f} | "
                 f"{r.op_rwa:,.0f} ({r.op_ilm:.2f}) | {r.market_rwa:,.0f} | {r.securitisation_rwa:,.0f} | "
                 f"{r.ccp_rwa:,.0f} | {r.total_rwa:,.0f} | {fl} | "
                 f"{r.cet1_ratio:.2%} | {r.cet1_requirement:.2%} | {r.cet1_surplus:+.2%} |")
    L += ["\nMarket risk (FRTB standardised approach, $M capital; one regime-neutral trading book, USD "
          "reporting currency):\n",
          "| Regime | SBM | Binding scenario | DRC | RRAO | RWA | GIRR | CSR | Equity | Commodity | FX |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res.regimes:
        c = r.market_by_class
        L.append(f"| {r.jurisdiction.value} | {r.market_sbm:,.0f} | {r.market_binding_scenario or '-'} | "
                 f"{r.market_drc:,.0f} | {r.market_rrao:,.0f} | {r.market_rwa:,.0f} | "
                 f"{c.get('GIRR', 0.0):,.0f} | {c.get('CSR_NONSEC', 0.0):,.0f} | {c.get('EQUITY', 0.0):,.0f} | "
                 f"{c.get('COMMODITY', 0.0):,.0f} | {c.get('FX', 0.0):,.0f} |")
    tranches = [x["tranche"] for x in res.regimes[0].securitisation_rows]
    L += ["\nSecuritisation risk weights by tranche (approach / RW; US: SEC-SA only, other regimes use "
          "SEC-ERBA for rated tranches subject to their hierarchy):\n",
          "| Tranche | " + " | ".join(r.jurisdiction.value for r in res.regimes) + " |",
          "|---|" + "---|" * len(res.regimes)]
    for k, t in enumerate(tranches):
        L.append(f"| {t} | " + " | ".join(
            f"{r.securitisation_rows[k]['approach']} {float(r.securitisation_rows[k]['risk_weight']):.0%}"  # type: ignore[arg-type]
            for r in res.regimes) + " |")
    L += ["\nLeverage and large exposures:\n",
          "| Regime | Exposure measure | Exclusions | Leverage ratio | Requirement | LE reportable | "
          "LE breaches | Largest non-exempt (% T1) |", "|---|---|---|---|---|---|---|---|"]
    for r in res.regimes:
        L.append(f"| {r.jurisdiction.value} | {r.leverage_exposure:,.0f} | {r.leverage_exclusions:,.0f} | "
                 f"{r.leverage_ratio:.2%} | {r.leverage_requirement:.2%} | {r.large_exposures_reportable} | "
                 f"{len(r.large_exposure_breaches)} | {r.large_exposure_max_pct_tier1:.1%} |")
    L += [f"\nEnd-state rules ({full.year}: transitionals such as equity phase-ins and the EU UCC CCF "
          "have run off):\n", "| Regime | Total RWA | CET1 | vs " + str(res.year) + " |", "|---|---|---|---|"]
    by_now = {r.jurisdiction: r for r in res.regimes}
    for r in full.regimes:
        L.append(f"| {r.jurisdiction.value} | {r.total_rwa:,.0f} | {r.cet1_ratio:.2%} | "
                 f"{r.total_rwa - by_now[r.jurisdiction].total_rwa:+,.0f} |")
    L += ["\nOutput-floor what-if: floor add-on ($M) for a hypothetical internal-models bank whose modelled "
          "RWA is 50/60/70% of its standardised RWA (scenario grid, not model output):\n",
          "| Regime | Year | Floor | 50% | 60% | 70% |", "|---|---|---|---|---|---|"]
    keyed: dict[tuple[str, int], dict[float, FloorSensitivityRow]] = {}
    for x in sens:
        keyed.setdefault((x.jurisdiction.value, x.year), {})[x.modelled_to_sa] = x
    for (jur, yr), cells in keyed.items():
        first = next(iter(cells.values()))
        fl = f"{first.floor_factor:.1%}" if first.floor_applies else "none"
        L.append(f"| {jur} | {yr} | {fl} | " + " | ".join(f"{cells[k].add_on:,.0f}" for k in sorted(cells)) + " |")
    L += ["\nSA credit RWA by exposure class ($M):\n"]
    classes = sorted({c for r in res.regimes for c in r.credit_rwa_by_class})
    L.append("| Class | " + " | ".join(r.jurisdiction.value for r in res.regimes) + " |")
    L.append("|---|" + "---|" * len(res.regimes))
    for c in classes:
        L.append(f"| {c} | " + " | ".join(f"{r.credit_rwa_by_class.get(c, 0.0):,.0f}" for r in res.regimes) + " |")
    return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "output" / "reports" / "e2e"))
    args = ap.parse_args()
    out = Path(args.out)
    p = Pipeline()
    print("Basel III Endgame engine -- end-to-end run and smoke test")
    print("=" * 78)
    stages: list[tuple[str, Callable[[Pipeline, StageResult], None]]] = [
        ("Portfolio generation", build_portfolio),
        ("SA credit risk (§ __.111)", run_credit),
        ("Off-balance sheet CCFs (§ __.112)", run_obs),
        ("SA-CCR (§ __.114)", run_saccr),
        ("CVA (§ __.222)", run_cva),
        ("Securitization SEC-SA (§ __.133)", run_securitization),
        ("Operational risk (§ __.150)", run_oprisk),
        ("FRTB SBM + DRC + RRAO", run_frtb),
        ("ECL / CECL", run_ecl),
        ("RWA aggregation", run_rwa),
        ("Capital stack", run_capital),
        ("G-SIB surcharge", run_gsib),
        ("CCAR stress test", run_stress),
        ("Ratios, buffers, PCA", run_ratios),
        ("Large exposures (SCCL)", run_large_exposures),
        ("Fed reports (Y-9C, 101, Y-15, Y-14)", run_reports),
        ("Pillar 3 disclosures", run_pillar3),
        ("Multi-jurisdiction comparison", run_jurisdictions),
    ]
    for name, fn in stages:
        p.run(name, lambda st, fn=fn: fn(p, st))
    summary = write_outputs(p, out)
    write_markdown(p, summary, out)
    n_pass = sum(s.passed for s in p.stages)
    print("=" * 78)
    print(f"{n_pass}/{len(p.stages)} stages passed.  Outputs in {out}")
    return 0 if n_pass == len(p.stages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
