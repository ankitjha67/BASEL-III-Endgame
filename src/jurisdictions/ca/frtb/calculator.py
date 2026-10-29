"""OSFI CAR 2026 Chapter 9 -- market risk calculator implementing :class:`MarketRiskCalculator`.

Standardized approach capital = SBM + DRC + RRAO (CAR 9.5.1.2 ¶110 [MAR20.4]); RWA = 12.5 ×
capital (¶108 [MAR20.1]). The IMA scalars come from CAR 9.6. The Basel MAR40 simplified
standardised approach is exposed as :meth:`CAMarketRisk.simplified_standardised_approach` for
comparison only -- OSFI has not adopted it (CAR 9.1.2.2 [MAR11.7]; Ch.1 s.1.3.2 [RBC20.9]).

References:
    - OSFI CAR 2026 Chapter 9 (Market Risk), sections 9.5 and 9.6
    - docs/jurisdictions/CA_frtb_reference.md
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.ca.frtb import buckets as bk
from src.jurisdictions.ca.frtb import drc as drc_mod
from src.jurisdictions.ca.frtb import params as p
from src.jurisdictions.ca.frtb import rrao as rrao_mod
from src.jurisdictions.ca.frtb import sbm as sbm_mod
from src.jurisdictions.ca.frtb import ssa as ssa_mod
from src.jurisdictions.frtb_base import (
    DRCPositionInput,
    FRTBRiskClass,
    FRTBSensitivity,
    IMAParameters,
    MarketRiskResult,
    RRAOPositionInput,
    SBMClassResult,
)

_CITATIONS: dict[str, str] = {
    "structure": "CAR 9.5.1.2 ¶110 [MAR20.4] -- SA = SBM + DRC + RRAO; ¶108 [MAR20.1] RWA = 12.5x",
    "sbm": "CAR 9.5.2.3 ¶115-119 [MAR21.4-21.7]; buckets/RW/correlations ¶153-213 "
           "[MAR21.41-21.101]",
    "scenarios": "CAR 9.5.2.3 ¶118 [MAR21.6] high = min(1.25ρ,1), low = max(2ρ-1, 0.75ρ); "
                 "¶119 [MAR21.7] largest scenario total",
    "drc_nonsec": "CAR 9.5.3.4 ¶222-239 [MAR22.9-22.26]; sovereign 0%/0.5% ¶220 [MAR22.7]",
    "drc_sec_nonctp": "CAR 9.5.3.5 ¶240-248 [MAR22.27-22.35]",
    "drc_ctp": "CAR 9.5.3.6 ¶249-258 [MAR22.36-22.45]",
    "rrao": "CAR 9.5.4 ¶259-266 [MAR23.1-23.8] exotic 1.0%, other 0.1%",
    "scope": "CAR Ch.9 eligibility: internationally active institutions and all D-SIBs",
}


class CAMarketRisk:
    """Canada -- OSFI CAR 2026 Chapter 9 FRTB standardized approach.

    Args:
        reporting_currency: the institution's reporting currency (CAR ¶127 [MAR21.15]); it is
            added to the sqrt(2) GIRR currencies (¶156) and is the FX bucket base (¶198).
    """

    jurisdiction: Jurisdiction = Jurisdiction.CA
    regime_name: str = "OSFI CAR 2026 Chapter 9 -- Market Risk"

    def __init__(self, reporting_currency: str = "CAD") -> None:
        self.reporting_currency = reporting_currency.upper()

    # ------------------------------------------------------------------ SBM

    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """Regime bucket (CAR 9.5.2.5 Tables 3, 7, 9, 11; GIRR/FX per currency ¶153, ¶198)."""
        return bk.assign_bucket(s, self.reporting_currency)

    def sbm_by_scenario(
        self, sensitivities: list[FRTBSensitivity],
    ) -> dict[str, dict[FRTBRiskClass, sbm_mod.ClassScenarioResult]]:
        """Delta / vega / curvature per risk class under LOW, MEDIUM and HIGH (CAR ¶118)."""
        return sbm_mod.sbm_by_scenario(sensitivities, self.reporting_currency)

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM by risk class at the binding scenario (CAR ¶119 [MAR21.7]).

        Per ¶119(1)-(2) the scenario is chosen on the sum over all risk classes; each class is
        reported at that common binding scenario.
        """
        by_sc = self.sbm_by_scenario(sensitivities)
        sc = sbm_mod.binding_scenario(by_sc)
        return [
            SBMClassResult(
                risk_class=rc, delta=r.delta, vega=r.vega, curvature=r.curvature,
                total=r.total, scenario=sc,
            )
            for rc, r in by_sc.get(sc, {}).items()
        ]

    # ------------------------------------------------------------------ DRC / RRAO

    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC by component (CAR 9.5.3 ¶214-258 [MAR22])."""
        return drc_mod.drc_capital(positions)

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """Residual risk add-on (CAR 9.5.4 ¶259-266 [MAR23])."""
        return rrao_mod.rrao_capital(positions)

    # ------------------------------------------------------------------ total

    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """Standardized approach capital and RWA (CAR ¶108, ¶110 [MAR20.1, MAR20.4])."""
        by_sc = self.sbm_by_scenario(sensitivities)
        sc = sbm_mod.binding_scenario(by_sc) if sensitivities else ""
        classes = [
            SBMClassResult(
                risk_class=rc, delta=r.delta, vega=r.vega, curvature=r.curvature,
                total=r.total, scenario=sc,
            )
            for rc, r in by_sc.get(sc, {}).items()
        ]
        sbm_total = sum(c.total for c in classes)
        drc = self.drc_capital(drc_positions)
        rrao = self.rrao_capital(rrao_positions)
        total = sbm_total + drc["total"] + rrao
        notes = [
            "OSFI paragraph numbers are derived from CAR cross-references (see params.py).",
            "Equity large cap = market cap >= CAD 2.5bn (CAR ¶186); set is_large_cap accordingly.",
            "DRC: AAA vs AA separated only via flags['rating_aaa'] (else AA, 2%).",
        ]
        return MarketRiskResult(
            jurisdiction=self.jurisdiction,
            sbm_by_class=classes,
            sbm_total=sbm_total,
            binding_scenario=sc,
            drc_nonsec=drc["nonsec"],
            drc_sec_nonctp=drc["sec_nonctp"],
            drc_ctp=drc["ctp"],
            drc_total=drc["total"],
            rrao=rrao,
            total_capital=total,
            rwa=total * p.RWA_MULTIPLIER,
            citations=dict(_CITATIONS),
            notes=notes,
        )

    # ------------------------------------------------------------------ IMA

    def ima_parameters(self) -> IMAParameters:
        """CAR 9.6 IMA scalars (Tables 17, 18, 20; ρ 0.5 and 0.6)."""
        return IMAParameters(
            jurisdiction=self.jurisdiction,
            es_confidence=p.IMA_ES_CONFIDENCE,
            liquidity_horizons_days=dict(p.IMA_LIQUIDITY_HORIZONS),
            multiplier_base=p.IMA_MULTIPLIER_BASE,
            backtesting_addons=dict(p.IMA_BACKTESTING_ADDONS),
            imcc_rho=p.IMA_IMCC_RHO,
            ses_rho=p.IMA_SES_RHO,
            pla_spearman_thresholds=(p.IMA_PLA_SPEARMAN_GREEN, p.IMA_PLA_SPEARMAN_RED),
            pla_ks_thresholds=(p.IMA_PLA_KS_GREEN, p.IMA_PLA_KS_RED),
            citations={
                "es_confidence": "CAR 9.6.4.1 [MAR33.3] 97.5th percentile",
                "liquidity_horizons": "CAR 9.6.4.1 Table 20 [MAR33.12]",
                "multiplier": "CAR 9.6.4.6 [MAR33.42] m_c = 1.5 + plus factor; Table 17 "
                              "[MAR32.9]",
                "imcc_rho": "CAR 9.6.4.2 [MAR33.15] ρ = 0.5",
                "ses_rho": "CAR 9.6.4.3 [MAR33.17] ρ = 0.6",
                "pla": "CAR 9.6.3.2 Table 18 [MAR32.42]",
            },
        )

    # ------------------------------------------------------------------ MAR40 (comparison)

    def simplified_standardised_approach(self, **inputs: object) -> ssa_mod.SSAResult:
        """Basel MAR40 simplified standardised approach -- comparison only.

        Not permitted under CAR 2026 (CAR 9.1.2.2 [MAR11.7]; Ch.1 s.1.3.2 [RBC20.9]); the
        result's ``permitted_under_car`` is ``False``. Keyword arguments are those of
        :func:`src.jurisdictions.ca.frtb.ssa.ssa_capital`.
        """
        return ssa_mod.ssa_capital(**inputs)  # type: ignore[arg-type]
