"""UK PRA market-risk calculator -- :class:`UKMarketRisk`.

Implements :class:`~src.jurisdictions.frtb_base.MarketRiskCalculator` for the PRA Rulebook CRR
Firms (CRR) Instrument 2026 (PS1/26 Appendix 1):

* advanced standardised approach (Annex I, Art 325c(2), p. 313): SBM (Section 2) + residual
  risk add-on (Section 4) + default risk charge (Section 5); RWA = 12.5 x own funds requirement
  (Required Level of Own Funds (CRR) Part Art 92(4)(b), p. 15);
* simplified standardised approach (Annex J, with the General Provisions Art 325(2) multipliers
  and Art 325a eligibility) as the extra method :meth:`UKMarketRisk.simplified_standardised`;
* the internal-model scalars (Annex H) via :meth:`UKMarketRisk.ima_parameters`.
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.frtb_base import (
    DRCPositionInput,
    FRTBSensitivity,
    IMAParameters,
    MarketRiskResult,
    RRAOPositionInput,
    SBMClassResult,
)
from src.jurisdictions.uk.frtb import buckets as bk
from src.jurisdictions.uk.frtb import drc as drc_mod
from src.jurisdictions.uk.frtb import params as p
from src.jurisdictions.uk.frtb import rrao as rrao_mod
from src.jurisdictions.uk.frtb import ssa as ssa_mod
from src.jurisdictions.uk.frtb.sbm import SBMEngine

LEGAL_BASIS = (
    "PRA PS1/26 Appendix 1 -- PRA Rulebook: CRR Firms: (CRR) Instrument 2026 (PRA2026/1): "
    "Market Risk: General Provisions (CRR) Part, Market Risk: Advanced Standardised Approach "
    "(CRR) Part, Market Risk: Simplified Standardised Approach (CRR) Part, Market Risk: "
    "Internal Model Approach (CRR) Part"
)


class UKMarketRisk:
    """UK FRTB calculator (advanced standardised approach, SSA, IMA scalars).

    Args:
        domestic_currency: the institution's domestic / reporting currency; it receives the
            GIRR sqrt(2) reduction (Art 325ae(3), p. 344) and is the reference currency of the
            FX risk factors (Art 325q(1), p. 327). Default GBP.
        fx_curvature_permission: PRA permission of Art 325q(6) (p. 328) to divide all FX
            curvature positions by 1.5.
        ctp_bucket_floor: apply the zero floor printed in Art 325ad(3) (p. 343) to ACTP bucket
            DRC (default True, literal text; BCBS MAR22.44(2) has no floor).
    """

    jurisdiction: Jurisdiction = Jurisdiction.UK
    legal_basis: str = LEGAL_BASIS

    def __init__(
        self,
        domestic_currency: str = p.REPORTING_CURRENCY,
        fx_curvature_permission: bool = False,
        ctp_bucket_floor: bool = p.DRC_CTP_BUCKET_FLOOR_AT_ZERO,
    ) -> None:
        """Configure the regime options (see class docstring)."""
        self.domestic_currency = domestic_currency.upper()
        self.ctp_bucket_floor = ctp_bucket_floor
        self._sbm = SBMEngine(self.domestic_currency, fx_curvature_permission)

    # ------------------------------------------------------------------
    #  MarketRiskCalculator protocol
    # ------------------------------------------------------------------
    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """UK bucket of a sensitivity (Art 325l-325q, Section 6 tables, p. 322-360)."""
        return bk.assign_bucket(s)

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM capital by risk class for the binding (highest-total) correlation scenario
        (Art 325h(3)-(4), p. 318)."""
        rows, _ = self._sbm.capital(sensitivities)
        return rows

    def sbm_by_scenario(
        self, sensitivities: list[FRTBSensitivity]
    ) -> dict[str, list[SBMClassResult]]:
        """Risk-class charges under each of the three correlation scenarios (Art 325h(2))."""
        return self._sbm.by_scenario(sensitivities)

    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC by component: ``nonsec``, ``sec_nonctp``, ``ctp``, ``total`` (Art 325v-325ad,
        p. 335-343)."""
        return drc_mod.drc_capital(positions, self.ctp_bucket_floor)

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """Residual risk add-on (Art 325u, p. 333-335)."""
        return rrao_mod.rrao_capital(positions)

    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """Advanced standardised approach total = SBM + RRAO + DRC (Art 325c(2), p. 313);
        RWA = 12.5 x total (Art 92(4)(b), p. 15)."""
        rows, binding = self._sbm.capital(sensitivities)
        sbm_total = sum(r.total for r in rows)
        drc = self.drc_capital(drc_positions)
        rrao = self.rrao_capital(rrao_positions)
        total = sbm_total + drc["total"] + rrao
        notes = [
            "UK SBM scenario selected on the sum over risk classes (Art 325h(3)-(4)).",
            "GIRR sqrt(2) reduction for AUD/CAD/EUR/GBP/JPY/SEK/USD and the domestic currency "
            f"({self.domestic_currency}) (Art 325ae(3)).",
        ]
        if self.ctp_bucket_floor:
            notes.append(
                "ACTP bucket DRC floored at zero as printed in Art 325ad(3) (TODO: VERIFY vs "
                "BCBS MAR22.44(2))."
            )
        return MarketRiskResult(
            jurisdiction=self.jurisdiction,
            sbm_by_class=rows,
            sbm_total=sbm_total,
            binding_scenario=binding if rows else "",
            drc_nonsec=drc["nonsec"],
            drc_sec_nonctp=drc["sec_nonctp"],
            drc_ctp=drc["ctp"],
            drc_total=drc["total"],
            rrao=rrao,
            total_capital=total,
            rwa=p.RWA_MULTIPLIER * total,
            citations={
                "structure": "Market Risk: Advanced Standardised Approach (CRR) Part Art 325c(2)",
                "sbm": "Art 325e-325h; Section 6 Articles 325ae-325ay (p. 314-361)",
                "drc": "Art 325v-325ad (p. 335-343)",
                "rrao": "Art 325u (p. 333-335)",
                "rwa": "Required Level of Own Funds (CRR) Part Art 92(4)(b) (p. 15)",
            },
            notes=notes,
        )

    def ima_parameters(self) -> IMAParameters:
        """IMA scalars of the Market Risk: Internal Model Approach (CRR) Part (Annex H)."""
        return IMAParameters(
            jurisdiction=self.jurisdiction,
            es_confidence=p.IMA_ES_CONFIDENCE,
            liquidity_horizons_days=dict(p.IMA_LIQUIDITY_HORIZONS),
            multiplier_base=p.IMA_MULTIPLIER_BASE,
            backtesting_addons=dict(p.IMA_BACKTESTING_ADDON),
            imcc_rho=p.IMA_ES_RHO,
            ses_rho=p.IMA_SES_RHO,
            pla_spearman_thresholds=p.IMA_PLA_SPEARMAN,
            pla_ks_thresholds=p.IMA_PLA_KS,
            citations={
                "es_confidence": "Art 325bc(1)(b) (p. 245)",
                "liquidity_horizons": "Art 325bd(7) Table 2 (p. 249-251)",
                "multiplier": "Art 325bf(6) and Table 3 (p. 261-262)",
                "imcc_rho": "Art 325bb(1) (p. 244)",
                "ses_rho": "Art 325bk(13) (p. 283)",
                "pla": "Art 325bg(7) (p. 269)",
                "transitional": "Glossary 'IMA transitional period' (p. 5); IMA Part rule 4.1 "
                "(p. 238)",
            },
        )

    # ------------------------------------------------------------------
    #  Alternatives
    # ------------------------------------------------------------------
    def simplified_standardised(self, inputs: ssa_mod.SSAInputs) -> ssa_mod.SSAResult:
        """Simplified standardised approach (Market Risk: Simplified Standardised Approach
        (CRR) Part, scaled per General Provisions Art 325(2), p. 226-227)."""
        return ssa_mod.simplified_standardised(inputs)

    @staticmethod
    def ssa_eligible(business_size: float, total_assets: float) -> bool:
        """SSA eligibility thresholds of Art 325a(1) (p. 231)."""
        return ssa_mod.ssa_eligible(business_size, total_assets)
