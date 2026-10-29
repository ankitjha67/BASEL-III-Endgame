"""EU market-risk calculator -- implements the ``MarketRiskCalculator`` protocol (frtb_base).

Alternative standardised approach (ASA, CRR Part Three Title IV Chapter 1a, Article 325(1)(a) as
replaced by CRR3 point (156)):

    OFR_ASA = SBM (Section 2) + DRC (Section 5) + RRAO (Section 4)      [Article 325c(2)]
    RWA     = 12,5 x OFR                                                 [Article 92(6)(b)]

Extra methods:

* :meth:`EUMarketRisk.simplified_standardised` -- SSA, Article 325(2) with Arts 326-361;
* :meth:`EUMarketRisk.ssa_eligible` -- Article 325a(1) thresholds;
* :meth:`EUMarketRisk.aima_total` -- Article 325ba(3) (CRR3 point (179)(c)) combination of the
  alternative internal model with the ASA;
* :meth:`EUMarketRisk.imcc` / :meth:`EUMarketRisk.multiplication_factor` -- Articles 325bb(1),
  325bc(1)(c), 325bf(6).

Application: CRR3 applies from 1 January 2025 (Article 2), but Article 461a(2)(b) (CRR3 point
(236)) lets the Commission postpone the market-risk requirements by up to two years and apply
targeted multipliers in [0, 1); those delegated acts are outside the supplied texts, so an
optional ``targeted_multiplier`` can be configured explicitly.
"""

from __future__ import annotations

import math
from datetime import date

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.eu.frtb import buckets as bk
from src.jurisdictions.eu.frtb import drc as drc_mod
from src.jurisdictions.eu.frtb import params as p
from src.jurisdictions.eu.frtb import rrao as rrao_mod
from src.jurisdictions.eu.frtb.sbm import EUSBMEngine, SBMOutcome
from src.jurisdictions.eu.frtb.ssa import SSAInputs, SSAResult, ssa_capital
from src.jurisdictions.eu.frtb.ssa import ssa_eligible as _ssa_eligible
from src.jurisdictions.frtb_base import (
    DRCPositionInput,
    FRTBMeasure,
    FRTBRiskClass,
    FRTBSensitivity,
    IMAParameters,
    MarketRiskResult,
    RRAOPositionInput,
    SBMClassResult,
)

_CITATIONS: dict[str, str] = {
    "approach": "CRR Art 325(1)(a), Chapter 1a, as amended by Reg. (EU) 2024/1623 Art 1(156)",
    "sbm": "CRR Arts 325e-325h; scenarios Art 325h(2) (M12)",
    "girr": "CRR Arts 325l, 325ae (Table 3, M12; para 3 per CRR3 point (170)), 325af, 325ag",
    "csr_nonsec": "CRR Arts 325ah Table 4 (M12; CRR3 point (171)), 325ai (CRR3 point (172)), "
    "325aj Table 5 (CRR3 point (173))",
    "csr_ctp": "CRR Arts 325ak Table 6 (CRR3 point (174)), 325al",
    "csr_sec_nonctp": "CRR Arts 325am Table 7 (CRR3 point (175)), 325an, 325ao",
    "equity": "CRR Arts 325ap Table 8, 325aq, 325ar (M12)",
    "commodity": "CRR Arts 325as Table 9 (CRR3 point (176)), 325at Table 10, 325au",
    "fx": "CRR Arts 325av, 325aw",
    "vega_curvature": "CRR Arts 325ax (CRR3 point (177)), 325ay, 325g (M12)",
    "drc": "CRR Arts 325v-325ad (CRR3 points (165)-(169))",
    "rrao": "CRR Art 325u (CRR3 point (164))",
    "rwa": "CRR Art 92(6)(b) (CRR3 point (28)): x 12,5",
}


class EUMarketRisk:
    """European Union market risk -- CRR Title IV as amended by CRR3.

    Args:
        domestic_currency: the institution's domestic currency (Article 325ae(3)).
        most_liquid_currencies: Article 325bd(7)(b) currencies (EBA RTS, not supplied; default
            empty -- see ``params.GIRR_MOST_LIQUID_CURRENCIES``).
        fx_curvature_divide_all: Article 325q(6) permission (divide FX CVRs by 1,5).
        cash_equity_maturity_years: Article 325x(4) election (1 year or 3 months).
        as_of: reporting date (drives the Article 325u(4a) RRAO derogation).
        targeted_multiplier: optional Article 461a(2)(a) multiplier applied to the total
            (must be >= 0 and < 1 when set; ``None`` = not applied).
    """

    jurisdiction: Jurisdiction = Jurisdiction.EU

    def __init__(
        self,
        domestic_currency: str = p.GIRR_DEFAULT_DOMESTIC_CURRENCY,
        most_liquid_currencies: frozenset[str] = p.GIRR_MOST_LIQUID_CURRENCIES,
        fx_curvature_divide_all: bool = False,
        cash_equity_maturity_years: float = p.DRC_CASH_EQUITY_MATURITY_OPTIONS[0],
        as_of: date | None = None,
        targeted_multiplier: float | None = None,
    ) -> None:
        """Configure the EU-specific options."""
        if cash_equity_maturity_years not in p.DRC_CASH_EQUITY_MATURITY_OPTIONS:
            raise ValueError("Article 325x(4): cash equity maturity must be 1 year or 3 months")
        lo, hi = p.MARKET_RISK_TARGETED_MULTIPLIER_RANGE
        if targeted_multiplier is not None and not lo <= targeted_multiplier < hi:
            raise ValueError("Article 461a(2)(a): targeted multiplier must be >= 0 and < 1")
        self.domestic_currency = domestic_currency.upper()
        self.most_liquid = frozenset(c.upper() for c in most_liquid_currencies)
        self.cash_equity_maturity = cash_equity_maturity_years
        self.as_of = as_of or date.today()
        self.targeted_multiplier = targeted_multiplier
        self._engine = EUSBMEngine(self.domestic_currency, self.most_liquid,
                                   fx_curvature_divide_all)

    # ------------------------------------------------------------------
    #  MarketRiskCalculator protocol
    # ------------------------------------------------------------------

    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """EU bucket label (Articles 325l-325q, 325ah, 325ak, 325am, 325ap, 325as)."""
        return bk.assign_bucket(s)

    def risk_weight(self, s: FRTBSensitivity) -> float:
        """Risk weight for the sensitivity's measure (Articles 325ae-325ax)."""
        return bk.risk_weight(s, self.domestic_currency, self.most_liquid)

    def sbm_outcome(self, sensitivities: list[FRTBSensitivity]) -> SBMOutcome:
        """Full per-scenario SBM detail (Article 325h)."""
        return self._engine.compute(sensitivities)

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM by risk class under the binding scenario.

        Article 325h(3)-(4): the scenario is chosen on the sum across all risk classes and
        measures, so every class reports the same (binding) scenario.
        """
        out = self._engine.compute(sensitivities)
        scen = out.binding_scenario
        results: list[SBMClassResult] = []
        for rc in FRTBRiskClass:
            vals = out.by_scenario.get(scen, {}).get(rc)
            if not vals:
                continue
            d = vals.get(FRTBMeasure.DELTA, 0.0)
            v = vals.get(FRTBMeasure.VEGA, 0.0)
            c = vals.get(FRTBMeasure.CURVATURE, 0.0)
            results.append(SBMClassResult(risk_class=rc, delta=d, vega=v, curvature=c,
                                          total=d + v + c, scenario=scen))
        return results

    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC by component (Article 325v(2)): ``nonsec``, ``sec_nonctp``, ``ctp``, ``total``."""
        comps = drc_mod.drc_all(positions, self.cash_equity_maturity)
        out = {k: v.total for k, v in comps.items()}
        out["total"] = sum(out.values())
        return out

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """Residual risk add-on (Article 325u)."""
        return rrao_mod.rrao(positions, self.as_of).total

    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """Total ASA own funds requirement and RWA (Articles 325c(2), 92(6)(b))."""
        sbm = self._engine.compute(sensitivities)
        classes = self.sbm_capital(sensitivities)
        drc = self.drc_capital(drc_positions)
        rrao_total = self.rrao_capital(rrao_positions)
        total = sbm.total + drc["total"] + rrao_total
        notes = list(sbm.notes)
        if self.targeted_multiplier is not None:
            total *= self.targeted_multiplier
            notes.append(f"Article 461a(2)(a) targeted multiplier {self.targeted_multiplier} "
                         "applied to the total")
        notes.append(
            "CRR3 applies from 1 January 2025 (Art 2); market-risk application may be postponed "
            "by up to two years by delegated act (Art 461a(2)(b)) -- not modelled"
        )
        return MarketRiskResult(
            jurisdiction=self.jurisdiction,
            sbm_by_class=classes,
            sbm_total=sbm.total,
            binding_scenario=sbm.binding_scenario,
            drc_nonsec=drc["nonsec"],
            drc_sec_nonctp=drc["sec_nonctp"],
            drc_ctp=drc["ctp"],
            drc_total=drc["total"],
            rrao=rrao_total,
            total_capital=total,
            rwa=p.RWA_MULTIPLIER * total,
            citations=dict(_CITATIONS),
            notes=notes,
        )

    def ima_parameters(self) -> IMAParameters:
        """Alternative internal model approach scalars (Articles 325bb-325bf)."""
        return IMAParameters(
            jurisdiction=self.jurisdiction,
            es_confidence=p.IMA_ES_CONFIDENCE,
            liquidity_horizons_days=dict(p.IMA_LH_BY_SUBCATEGORY),
            multiplier_base=p.IMA_MULTIPLIER_BASE,
            backtesting_addons=dict(p.IMA_BACKTESTING_ADDON),
            imcc_rho=p.IMA_RHO,
            ses_rho=p.IMA_SES_RHO,
            pla_spearman_thresholds=p.IMA_PLA_SPEARMAN,
            pla_ks_thresholds=p.IMA_PLA_KS,
            citations={
                "es_confidence": "CRR Art 325bc(1)(b)",
                "liquidity_horizons": "CRR Art 325bc(1) Table 1, Art 325bd(1) Table 2 "
                "(CRR3 point (181))",
                "multiplier": "CRR Art 325bf(6) Table 3 (CRR3 point (183))",
                "imcc_rho": "CRR Art 325bb(1): rho = 50 %",
                "ses": "CRR Art 325bk(3) -- aggregation by EBA RTS (not supplied)",
                "pla": "CRR Art 325bg(4) (CRR3 point (184)) -- thresholds by EBA RTS "
                "(not supplied)",
                "drc_model": "CRR Arts 325bn (99,9 %, one year), 325bp(5)(a) PD floors "
                "(CRR3 point (188))",
            },
        )

    # ------------------------------------------------------------------
    #  Extra EU methods
    # ------------------------------------------------------------------

    @staticmethod
    def ssa_eligible(market_risk_business: float, total_assets: float,
                     eur_per_reporting_unit: float = 1.0) -> bool:
        """Article 325a(1) thresholds for the simplified standardised approach."""
        return _ssa_eligible(market_risk_business, total_assets, eur_per_reporting_unit)

    @staticmethod
    def simplified_standardised(inputs: SSAInputs) -> SSAResult:
        """Simplified standardised approach (Article 325(2), Arts 326-361)."""
        return ssa_capital(inputs)

    @staticmethod
    def multiplication_factor(overshootings: int) -> float:
        """m_c = 1,5 + add-on of Article 325bf(6) Table 3 (more than 9 -> 0,50)."""
        key = min(max(overshootings, 0), max(p.IMA_BACKTESTING_ADDON))
        return p.IMA_MULTIPLIER_BASE + p.IMA_BACKTESTING_ADDON[key]

    @staticmethod
    def partial_es(pes_by_horizon: dict[int, float]) -> float:
        """PES_t = sqrt(PES_t(T)^2 + Sum_{j>=2} (PES_t(T,j) sqrt((LH_j - LH_{j-1})/10))^2).

        Article 325bc(1)(c) (C7, rendered consolidated p.477). ``pes_by_horizon`` maps LH_j
        (10, 20, 40, 60, 120) to PES_t(T, j); the 10-day entry is PES_t(T).
        """
        lhs = p.IMA_LIQUIDITY_HORIZONS
        tot = pes_by_horizon.get(lhs[0], 0.0) ** 2
        for j in range(1, len(lhs)):
            scale = math.sqrt((lhs[j] - lhs[j - 1]) / p.IMA_BASE_HORIZON_DAYS)
            tot += (pes_by_horizon.get(lhs[j], 0.0) * scale) ** 2
        return math.sqrt(tot)

    @staticmethod
    def imcc(ues_total: float, ues_by_category: list[float]) -> float:
        """ES_t = rho x UES_t + (1 - rho) x Sum_i UES_t^i, rho = 50 % (Article 325bb(1))."""
        return p.IMA_RHO * ues_total + (1.0 - p.IMA_RHO) * sum(ues_by_category)

    @staticmethod
    def unconstrained_es(pes_rs: float, pes_rc: float, pes_fc: float) -> float:
        """UES_t = PES_RS x max(PES_FC / PES_RC; 1) (Article 325bb(1))."""
        if pes_rc <= 0.0:
            return pes_rs
        return pes_rs * max(pes_fc / pes_rc, 1.0)

    @staticmethod
    def aima_capital(es_prev: float, ss_prev: float, es_avg: float, ss_avg: float,
                     overshootings: int) -> float:
        """Article 325ba(1): max(ES_{t-1} + SS_{t-1}; m_c x ES_avg + SS_avg)."""
        mc = EUMarketRisk.multiplication_factor(overshootings)
        return max(es_prev + ss_prev, mc * es_avg + ss_avg)

    @staticmethod
    def aima_total(aima: float, pla_addon: float, asa_non_aima: float,
                   asa_all_portfolio: float, asa_aima: float) -> float:
        """AIMA_total = min(AIMA + PLA_addon + ASA_non-aima; ASA_all portfolio)
        + max(AIMA - ASA_aima; 0) -- Article 325ba(3) (CRR3 point (179)(c), rendered p.125)."""
        return min(aima + pla_addon + asa_non_aima, asa_all_portfolio) + max(aima - asa_aima, 0.0)
