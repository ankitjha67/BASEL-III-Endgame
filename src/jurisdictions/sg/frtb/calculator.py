"""Singapore market-risk calculator (``Jurisdiction.SG``) implementing ``MarketRiskCalculator``.

SA(MR) capital = SBM + DRC + RRAO (MAS Notice 637 para 8.2.1); market RWA = 12.5 x capital
(para 8.1.1(a)). Extra methods: SSA(MR) (Part VIII Division 4, :meth:`SGMarketRisk.ssa`), the
para 8.1.18(a) SSA eligibility screen, and IMA helpers (Table 8-22 backtesting add-on, Table 8-23
PLA zones, paras 8.3.200 / 8.3.212 / 8.3.242-8.3.244 aggregation via the BCBS formulas, which
MAS transposes unchanged).

References: MAS Notice 637 Part VIII; docs/jurisdictions/SG_frtb_reference.md.
"""

from __future__ import annotations

from dataclasses import replace

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.bcbs.frtb import ima as bcbs_ima
from src.jurisdictions.frtb_base import (
    DRCPositionInput,
    FRTBMeasure,
    FRTBSensitivity,
    IMAParameters,
    MarketRiskResult,
    RRAOPositionInput,
    SBMClassResult,
)
from src.jurisdictions.sg.frtb import buckets as bk
from src.jurisdictions.sg.frtb import drc as drc_mod
from src.jurisdictions.sg.frtb import params as p
from src.jurisdictions.sg.frtb import rrao as rrao_mod
from src.jurisdictions.sg.frtb import sbm as sbm_mod
from src.jurisdictions.sg.frtb import ssa as ssa_mod

CITATIONS: dict[str, str] = {
    "structure": "MAS 637 para 8.2.1 (SBM + DRC + RRAO) [MAR20.4]",
    "rwa": "MAS 637 para 8.1.1(a): market RWA = 12.5 x capital [MAR20.1]",
    "sbm": "MAS 637 paras 8.2.10-8.2.157, Tables 8-1 to 8-13 [MAR21]",
    "scenarios": "MAS 637 para 8.2.14 (high x1.25 cap 100%; low max(2r-1, 0.75r)); "
                 "para 8.2.8(f) largest aggregate [MAR21.6-21.7]",
    "girr_sqrt2": "MAS 637 para 8.2.92: mandatory /sqrt(2) for EUR, USD, GBP, AUD, JPY, SEK, CAD, "
                  "SGD incl. inflation and xccy basis",
    "fx_sqrt2": "MAS 637 para 8.2.140: mandatory /sqrt(2) for specified pairs and crosses",
    "drc_nonsec": "MAS 637 paras 8.2.168-8.2.187, Table 8-14; 0% SA(CR)-0% names "
                  "para 8.2.184(b)(ii)",
    "drc_sec_nonctp": "MAS 637 paras 8.2.188-8.2.197, Table 8-15; RW = banking-book RW / 12.5",
    "drc_ctp": "MAS 637 paras 8.2.198-8.2.209",
    "rrao": "MAS 637 paras 8.2.210-8.2.217 (1.0% exotic / 0.1% other)",
    "ima": "MAS 637 paras 8.3.157 (Table 8-22), 8.3.175 (Table 8-23), 8.3.182, 8.3.184 "
           "(Table 8-24), 8.3.196 (Table 8-25), 8.3.200, 8.3.212, 8.3.242",
    "ssa": "MAS 637 para 8.4.2: 1.3 / 3.5 / 1.2 / 1.9; Annex 8E",
}


class SGMarketRisk:
    """Singapore -- MAS Notice 637 Part VIII SA(MR) (FRTB standardised approach).

    Args:
        reporting_currency: the bank's reporting currency (para 8.2.55; SGD for a
            Singapore-incorporated bank). It anchors the FX buckets (para 8.2.138), the
            specified-pair / first-order-cross test for the FX sqrt(2) reduction (para 8.2.140)
            and the FX curvature 1.5 scalar (para 8.2.152). The GIRR sqrt(2) list is fixed by
            para 8.2.92 (EUR, USD, GBP, AUD, JPY, SEK, CAD, SGD): unlike MAR21.44 it does not add
            the reporting currency, so a non-listed reporting currency gets no GIRR reduction.
        options: further discretions (para 8.2.96, 8.2.107, 8.2.152(b)); ``reporting_currency``
            above overrides ``options.reporting_currency``.
    """

    jurisdiction: Jurisdiction = Jurisdiction.SG
    regime_name: str = "MAS Notice 637 Part VIII -- SA(MR)"
    legal_basis: str = "MAS Notice 637 (effective 1 January 2026) Part VIII Divisions 1-4"

    def __init__(self, reporting_currency: str = "SGD",
                 options: p.SGFRTBOptions | None = None) -> None:
        """Create a calculator for the given reporting currency (para 8.2.55)."""
        base = options or p.DEFAULT_FRTB_OPTIONS
        self.reporting_currency = reporting_currency.upper()
        self.options = replace(base, reporting_currency=self.reporting_currency)

    # ------------------------------------------------------------------ SBM
    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """MAS 637 bucket (currency for GIRR / FX; Table 8-3 / 8-7 / 8-9 / 8-11 number)."""
        return bk.assign_bucket(s)

    def risk_weight(self, s: FRTBSensitivity) -> float:
        """Delta (paras 8.2.92-8.2.140), vega (Table 8-13) or curvature shock (8.2.151-153)."""
        if s.measure is FRTBMeasure.VEGA:
            return bk.vega_risk_weight(s)
        if s.measure is FRTBMeasure.CURVATURE:
            return bk.curvature_risk_weight(s, self.options)
        return bk.delta_risk_weight(s, self.options)

    def sbm_scenarios(self, sensitivities: list[FRTBSensitivity]
                      ) -> list[sbm_mod.SBMScenarioResult]:
        """All three correlation scenarios by risk class (para 8.2.14)."""
        return sbm_mod.sbm_scenarios(sensitivities, self.options)

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM by risk class under the binding scenario (para 8.2.8(f))."""
        return sbm_mod.sbm_capital(sensitivities, self.options)

    # ------------------------------------------------------------------ DRC / RRAO
    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC by component (paras 8.2.159-8.2.162): ``nonsec``, ``sec_nonctp``, ``ctp``,
        ``total``."""
        return drc_mod.drc_capital(positions)

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """Residual risk add-on (para 8.2.217)."""
        return rrao_mod.rrao_capital(positions)

    # ------------------------------------------------------------------ total
    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """SA(MR) capital = SBM + DRC + RRAO (para 8.2.1); RWA = 12.5 x capital (8.1.1(a))."""
        sbm = self.sbm_capital(sensitivities)
        sbm_total = sum(r.total for r in sbm)
        drc = self.drc_capital(drc_positions)
        rrao = self.rrao_capital(rrao_positions)
        total = sbm_total + drc["total"] + rrao
        notes = [
            "SBM scenario chosen on the aggregate across all risk classes (para 8.2.8(f)); "
            "per-class figures are those of that scenario.",
            f"Reporting currency {self.reporting_currency}: FX buckets and specified pairs "
            "relative to it (paras 8.2.138, 8.2.140); GIRR sqrt(2) list fixed by para 8.2.92.",
        ]
        if any(x.credit_sector.value in ("SOVEREIGN", "LOCAL_GOVERNMENT") for x in drc_positions):
            notes.append("DRC 0% applied to names at 0% under SA(CR) (para 8.2.184(b)(ii)).")
        return MarketRiskResult(
            jurisdiction=self.jurisdiction,
            sbm_by_class=sbm,
            sbm_total=sbm_total,
            binding_scenario=sbm[0].scenario if sbm else "",
            drc_nonsec=drc["nonsec"],
            drc_sec_nonctp=drc["sec_nonctp"],
            drc_ctp=drc["ctp"],
            drc_total=drc["total"],
            rrao=rrao,
            total_capital=total,
            rwa=total * p.RWA_MULTIPLIER,
            citations=dict(CITATIONS),
            notes=notes,
        )

    # ------------------------------------------------------------------ IMA
    def ima_parameters(self) -> IMAParameters:
        """IMA scalars (MAS 637 Part VIII Division 3)."""
        return IMAParameters(
            jurisdiction=self.jurisdiction,
            es_confidence=p.IMA_ES_CONFIDENCE,
            liquidity_horizons_days=dict(p.IMA_LIQUIDITY_HORIZONS),
            multiplier_base=p.IMA_MULTIPLIER_BASE,
            backtesting_addons=dict(p.IMA_BACKTESTING_ADDON),
            imcc_rho=p.IMA_IMCC_RHO,
            ses_rho=p.IMA_SES_RHO,
            pla_spearman_thresholds=p.IMA_PLA_SPEARMAN,
            pla_ks_thresholds=p.IMA_PLA_KS,
            citations={
                "es_confidence": "MAS 637 para 8.3.182",
                "liquidity_horizons_days": "MAS 637 para 8.3.196, Table 8-25",
                "multiplier_base": "MAS 637 para 8.3.242(e)",
                "backtesting_addons": "MAS 637 para 8.3.157, Table 8-22 (key 10 = 10 or more)",
                "imcc_rho": "MAS 637 para 8.3.200(b)",
                "ses_rho": "MAS 637 para 8.3.212(d)",
                "pla_thresholds": "MAS 637 para 8.3.175, Table 8-23 (amber, red)",
            },
        )

    @staticmethod
    def backtesting_zone(exceptions: int) -> str:
        """Table 8-22: GREEN 0-4, AMBER 5-9, RED 10 or more."""
        if exceptions < 0:
            raise ValueError("exceptions must be non-negative")
        if exceptions <= p.IMA_GREEN_MAX_EXCEPTIONS:
            return "GREEN"
        return "AMBER" if exceptions <= p.IMA_AMBER_MAX_EXCEPTIONS else "RED"

    @staticmethod
    def multiplier(exceptions: int, qualitative_addon: float = 0.0) -> float:
        """Para 8.3.242(e): m_c = 1.5 + m_b (Table 8-22) + m_q."""
        if exceptions < 0:
            raise ValueError("exceptions must be non-negative")
        red = p.IMA_AMBER_MAX_EXCEPTIONS + 1
        return p.IMA_MULTIPLIER_BASE + p.IMA_BACKTESTING_ADDON[min(exceptions, red)] \
            + qualitative_addon

    @staticmethod
    def pla_zone(spearman: float, ks: float) -> str:
        """Para 8.3.175 / Table 8-23: green if rho > 0.8 and KS < 0.09; red if rho < 0.7 or
        KS > 0.12; amber otherwise."""
        amber_rho, red_rho = p.IMA_PLA_SPEARMAN
        amber_ks, red_ks = p.IMA_PLA_KS
        if spearman > amber_rho and ks < amber_ks:
            return "GREEN"
        if spearman < red_rho or ks > red_ks:
            return "RED"
        return "AMBER"

    @staticmethod
    def imcc(unconstrained: float, constrained_by_class: list[float]) -> float:
        """Para 8.3.200: rho IMCC(C) + (1 - rho) sum IMCC(C_i), rho = 0.5."""
        rho = p.IMA_IMCC_RHO
        return rho * unconstrained + (1.0 - rho) * sum(constrained_by_class)

    @staticmethod
    def ses(ises_credit: list[float], ises_equity: list[float], ses_other: list[float]) -> float:
        """Para 8.3.212 (rho = 0.6; identical to MAR33.17, BCBS helper reused)."""
        return bcbs_ima.ses(ises_credit, ises_equity, ses_other)

    @staticmethod
    def liquidity_adjusted_es(es_by_horizon: list[float]) -> float:
        """Para 8.3.184 / Table 8-24 cascade (identical to MAR33.4, BCBS helper reused)."""
        return bcbs_ima.liquidity_adjusted_es(es_by_horizon)

    @staticmethod
    def aggregate_capital(ima_ga: float, surcharge: float, c_u: float, sa_all_desks: float,
                          sa_ga: float) -> float:
        """Para 8.3.243: min(IMA_G,A + C_S + C_U; SA_all) + max(0; IMA_G,A - SA_G,A)."""
        return bcbs_ima.aggregate_capital(ima_ga, surcharge, c_u, sa_all_desks, sa_ga)

    # ------------------------------------------------------------------ SSA(MR)
    def ssa(self, inputs: ssa_mod.SGSSAInputs) -> dict[str, float]:
        """SSA(MR) (Part VIII Division 4): scaled capital by risk class, total and RWA."""
        return ssa_mod.ssa_capital(inputs)

    @staticmethod
    def ssa_eligible(market_rwa_sgd_mn: float, total_rwa_sgd_mn: float) -> bool:
        """Para 8.1.18(a) quantitative screen for SSA(MR) approval."""
        return ssa_mod.ssa_eligibility_screen(market_rwa_sgd_mn, total_rwa_sgd_mn)


__all__ = ["CITATIONS", "SGMarketRisk"]
