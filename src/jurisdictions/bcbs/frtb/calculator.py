"""BCBS market-risk calculator (``Jurisdiction.BCBS``) implementing ``MarketRiskCalculator``.

Standardised approach capital = SBM + DRC + RRAO (MAR20.4); RWA = 12.5 x capital (MAR20.1).
Extra methods: the simplified standardised approach (MAR40, :meth:`BCBSMarketRisk.ssa`) and
the IMA aggregation helpers (MAR32-MAR33, module :mod:`.ima`).

References: Basel Framework MAR20-MAR23, MAR32-MAR33, MAR40 (BIS consolidated, 29/10/2026).
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.bcbs.frtb import buckets as bk
from src.jurisdictions.bcbs.frtb import drc as drc_mod
from src.jurisdictions.bcbs.frtb import params as p
from src.jurisdictions.bcbs.frtb import rrao as rrao_mod
from src.jurisdictions.bcbs.frtb import sbm as sbm_mod
from src.jurisdictions.bcbs.frtb import ssa as ssa_mod
from src.jurisdictions.frtb_base import (
    DRCPositionInput,
    FRTBMeasure,
    FRTBSensitivity,
    IMAParameters,
    MarketRiskResult,
    RRAOPositionInput,
    SBMClassResult,
)

CITATIONS: dict[str, str] = {
    "structure": "Basel Framework MAR20.1, MAR20.4",
    "sbm": "MAR21.4-21.7 (Tables 1-13), MAR21.98-21.101",
    "scenarios": "MAR21.6 (high x1.25 cap 100%; low max(2r-1, 0.75r)); MAR21.7(2) max of totals",
    "drc_nonsec": "MAR22.9-22.26 (Table 2)",
    "drc_sec_nonctp": "MAR22.27-22.35",
    "drc_ctp": "MAR22.36-22.45",
    "rrao": "MAR23.2-23.8 (1.0% exotic / 0.1% other)",
    "rwa": "MAR20.1: RWA = 12.5 x capital",
    "ima": "MAR32.9 Table 1, MAR32.42 Table 2, MAR33.3, MAR33.12 Table 2, MAR33.15, MAR33.17, "
           "MAR33.42",
    "ssa": "MAR40.2 scaling 1.30 / 3.50 / 1.20 / 1.90",
}


class BCBSMarketRisk:
    """FRTB under the consolidated Basel Framework (the international baseline)."""

    jurisdiction: Jurisdiction = Jurisdiction.BCBS
    regime_name: str = "Basel Framework market risk (FRTB)"
    legal_basis: str = "BIS Basel Framework MAR20-MAR23, MAR30-MAR33, MAR40"

    def __init__(self, options: p.BCBSFRTBOptions | None = None) -> None:
        """Create a calculator with the given discretions (MAR21.44, 21.88, 22.7, ...)."""
        self.options = options or p.DEFAULT_FRTB_OPTIONS

    # ------------------------------------------------------------------ SBM
    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """MAR21 bucket for a sensitivity (currency for GIRR / FX; Table number otherwise)."""
        return bk.assign_bucket(s)

    def risk_weight(self, s: FRTBSensitivity) -> float:
        """Delta (MAR21.42-21.88) or vega (MAR21.92) risk weight; curvature shock (MAR21.98-99)."""
        if s.measure is FRTBMeasure.VEGA:
            return bk.vega_risk_weight(s)
        if s.measure is FRTBMeasure.CURVATURE:
            return bk.curvature_risk_weight(s, self.options)
        return bk.delta_risk_weight(s, self.options)

    def sbm_scenarios(
        self, sensitivities: list[FRTBSensitivity]
    ) -> list[sbm_mod.SBMScenarioResult]:
        """All three correlation scenarios by risk class (MAR21.6)."""
        return sbm_mod.sbm_scenarios(sensitivities, self.options)

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM by risk class under the binding scenario (largest portfolio total, MAR21.7(2))."""
        return sbm_mod.sbm_capital(sensitivities, self.options)

    # ------------------------------------------------------------------ DRC / RRAO
    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC by component (MAR22.4): ``nonsec``, ``sec_nonctp``, ``ctp``, ``total``."""
        return drc_mod.drc_capital(positions, self.options)

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """Residual risk add-on (MAR23.8)."""
        return rrao_mod.rrao_capital(positions)

    # ------------------------------------------------------------------ total
    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """SA capital = SBM + DRC + RRAO (MAR20.4); RWA = 12.5 x capital (MAR20.1)."""
        sbm = self.sbm_capital(sensitivities)
        sbm_total = sum(r.total for r in sbm)
        drc = self.drc_capital(drc_positions)
        rrao = self.rrao_capital(rrao_positions)
        total = sbm_total + drc["total"] + rrao
        notes = [
            "SBM scenario chosen on the portfolio total across all risk classes (MAR21.7(2)); "
            "per-class figures are those of that scenario.",
        ]
        if any(x.banking_book_risk_weight is not None for x in drc_positions):
            notes.append("Securitisation DRC weights = banking-book RW x 8% "
                         "(TODO: VERIFY, MAR22.34 / MAR22.42).")
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
        """IMA scalars (MAR32-MAR33)."""
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
                "es_confidence": "MAR33.3",
                "liquidity_horizons_days": "MAR33.12 Table 2",
                "multiplier_base": "MAR33.42",
                "backtesting_addons": "MAR32.9 Table 1 (multiplier - 1.5; key 10 = 10 or more)",
                "imcc_rho": "MAR33.15",
                "ses_rho": "MAR33.17",
                "pla_thresholds": "MAR32.42 Table 2 (amber, red)",
            },
        )

    # ------------------------------------------------------------------ MAR40
    def ssa(self, inputs: ssa_mod.SSAInputs) -> dict[str, float]:
        """Simplified standardised approach (MAR40): scaled capital and RWA."""
        return ssa_mod.ssa_capital(inputs)


__all__ = ["BCBSMarketRisk", "CITATIONS"]
