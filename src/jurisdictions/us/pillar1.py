"""United States -- securitisation, SA-CVA, leverage, large exposures and CCPs.

Implements the protocols of :mod:`src.jurisdictions.pillar1_base` for the US:

- Securitisation: SEC-SA only (ERBA NPR § __.130-__.134) via
  :class:`src.securitization.sec_framework.SecuritizationCalculator`; a
  position for which SEC-SA cannot be applied is weighted 1,250%
  (§ __.130); resecuritisation and NPL floors 100%, otherwise 15% (§ __.133).
- SA-CVA: § __.224-__.225 via :class:`src.cva_risk.sa_cva.SACVACalculator`
  (m_CVA = 1, R = 0.01).
- Leverage: total leverage exposure, 12 CFR 217.10(c)(2) (current rule):
  on-balance assets less Tier 1 deductions; SA-CCR PFE with C = 0 and
  multiplied by 1.4 except for commercial end-users; replacement cost with
  eligible cash variation margin; effective notional of written credit
  derivatives; repo-style gross receivables and counterparty exposure;
  off-balance credit equivalent with a 10% minimum CCF.
- Large exposures: single-counterparty credit limits, 12 CFR 252.72 -- 25%
  of tier 1 capital; 15% for a major covered company to a major
  counterparty.
- CCPs: ERBA NPR § __.116 -- QCCP trade exposures 2% (4% for clients
  without the bankruptcy-remote arrangement); non-QCCP at the CCP's
  § __.111 weight; default fund: QCCP RWA = 12.5 x K_CM with
  K_CM = max(K_CCP x DF_pref / (DF_CCP + DF_CM), 0.16% x DF_pref);
  non-QCCP 1,250%.

All amounts in USD millions ($M).
"""

from __future__ import annotations

from typing import Final

from src.cva_risk.cva_params import (
    CVACreditQuality,
    CVASector,
    SACVARiskFactorType,
    normalize_sector,
)
from src.cva_risk.sa_cva import SACVACalculator as USSACVACalculator
from src.cva_risk.sa_cva import SACVASensitivity
from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import (
    CCPExposureInput,
    CCPResult,
    CVARiskClass,
    CVASensitivityInput,
    LargeExposureInput,
    LargeExposureRow,
    LeverageInputs,
    LeverageResult,
    SACVAResult,
    SecApproachUsed,
    SecResultRow,
    SecTrancheInput,
)
from src.securitization.sec_framework import (
    SecuritizationCalculator,
    SecuritizationPool,
    SecuritizationTranche,
)

RWA_PER_UNIT_CAPITAL: Final[float] = 12.5
MINIMUM_CAPITAL_RATIO: Final[float] = 0.08
"""K_G is expressed as a capital requirement (RWA x 8%) (§ __.133)."""
RW_1250: Final[float] = 12.5
"""1,250% (§ __.130)."""
NPL_RW_FLOOR: Final[float] = 1.0
"""RW floor 100% for NPL securitisations (§ __.133)."""

LEVERAGE_PFE_ALPHA: Final[float] = 1.4
"""12 CFR 217.10(c)(2)(ii)(B)(1): PFE multiplied by 1.4 except for commercial end-users."""
LEVERAGE_MIN_CCF: Final[float] = 0.10
"""12 CFR 217.10(c)(2)(viii): minimum credit conversion factor 10%."""

SCCL_GENERAL_LIMIT: Final[float] = 0.25
"""12 CFR 252.72(a): 25 percent of tier 1 capital."""
SCCL_MAJOR_LIMIT: Final[float] = 0.15
"""12 CFR 252.72(b): 15 percent of tier 1 capital (major covered company to major counterparty)."""
# TODO: VERIFY -- 12 CFR 252 Subpart H has no "reporting threshold" analogous to LEX20.3;
# the 10% figure below is used only to flag exposures for the comparison table.
SCCL_REPORTING_FLAG: Final[float] = 0.10

CCP_QCCP_RW: Final[float] = 0.02
"""ERBA NPR § __.116: QCCP trade exposures 2%."""
CCP_QCCP_CLIENT_NON_REMOTE_RW: Final[float] = 0.04
"""§ __.116: client trade exposure 4% without the bankruptcy-remote arrangement."""
CCP_NON_QCCP_DEFAULT_FUND_RW: Final[float] = 12.5
"""§ __.116: default-fund contributions to a non-QCCP 1,250%."""
CCP_KCM_FLOOR: Final[float] = 0.0016
"""§ __.116: K_CM floor 0.16% x DF_pref."""
CCP_NON_QCCP_TRADE_RW: Final[float] = 1.0
"""Non-QCCP trade exposures take the CCP's § __.111 weight; corporate 100% used as the
default (# TODO: VERIFY -- pass flags['ccp_rw'] style override via the credit regime)."""

_CVA_CLASS: Final[dict[CVARiskClass, SACVARiskFactorType]] = {
    CVARiskClass.INTEREST_RATE: SACVARiskFactorType.INTEREST_RATE,
    CVARiskClass.FX: SACVARiskFactorType.FX,
    CVARiskClass.COUNTERPARTY_CREDIT_SPREAD: SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD,
    CVARiskClass.REFERENCE_CREDIT_SPREAD: SACVARiskFactorType.REFERENCE_CREDIT_SPREAD,
    CVARiskClass.EQUITY: SACVARiskFactorType.EQUITY,
    CVARiskClass.COMMODITY: SACVARiskFactorType.COMMODITY,
}
INFLATION_FACTOR_KEY: Final[str] = "INFLATION"


class USPillar1:
    """US securitisation, SA-CVA, leverage, SCCL and CCP treatment."""

    jurisdiction: Jurisdiction = Jurisdiction.US

    def __init__(self) -> None:
        """Build the wrapped calculators."""
        self._sec = SecuritizationCalculator()

    # ------------------------------------------------------------ securitisation
    def securitisation(self, tranche: SecTrancheInput) -> SecResultRow:
        """SEC-SA risk weight (§ __.133) or 1,250% where SEC-SA cannot be applied (§ __.130)."""
        if tranche.k_sa is None:
            return SecResultRow(
                tranche_id=tranche.tranche_id,
                jurisdiction=self.jurisdiction,
                approach=SecApproachUsed.RW_1250,
                risk_weight=RW_1250,
                rwa=tranche.exposure_amount * RW_1250,
                citation="ERBA NPR § __.130 (SEC-SA inputs unavailable)",
            )
        ead = max(tranche.exposure_amount, 1.0)
        pool = SecuritizationPool(
            pool_id=f"{tranche.tranche_id}-POOL",
            total_ead=ead,
            pool_rwa=tranche.k_sa / MINIMUM_CAPITAL_RATIO * ead,
            delinquency_ratio=tranche.w,
            is_synthetic=tranche.is_synthetic,
        )
        t = SecuritizationTranche(
            tranche_id=tranche.tranche_id,
            pool_id=pool.pool_id,
            attachment_point=tranche.attachment,
            detachment_point=tranche.detachment,
            notional=tranche.exposure_amount,
            is_senior=tranche.is_senior,
            is_resecuritization=tranche.is_resecuritisation,
            maturity_years=max(tranche.maturity_years, 1.0),
            is_stc=False,
        )
        res = self._sec.calculate([t], pool)
        rw = res.rw_by_tranche[tranche.tranche_id]
        notes: list[str] = []
        if tranche.is_npl_securitisation and rw < NPL_RW_FLOOR:
            rw = NPL_RW_FLOOR
            notes.append("NPL securitisation floor 100% (§ __.133)")
        if tranche.is_stc:
            notes.append("No STC treatment in the ERBA NPR; SEC-SA applied without STC parameters")
        approach = SecApproachUsed.RW_1250 if rw >= RW_1250 else SecApproachUsed.SEC_SA
        return SecResultRow(
            tranche_id=tranche.tranche_id,
            jurisdiction=self.jurisdiction,
            approach=approach,
            risk_weight=rw,
            rwa=tranche.exposure_amount * rw,
            citation="ERBA NPR § __.133 (SEC-SA)",
            notes=notes,
        )

    # ------------------------------------------------------------ SA-CVA
    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """§ __.224-__.225 SA-CVA: K = m_CVA x sqrt(Σ K_b² + ΣΣ γ S_b S_c) per class."""
        mapped: list[SACVASensitivity] = []
        for s in sensitivities:
            rc = _CVA_CLASS[s.risk_class]
            kw: dict[str, object] = {
                "risk_class": rc,
                "is_vega": s.measure.upper() == "VEGA",
                "cva_sensitivity": s.s_cva,
                "hedge_sensitivity": s.s_hedge,
            }
            quality = (
                CVACreditQuality.INVESTMENT_GRADE
                if s.is_investment_grade
                else CVACreditQuality.SPECULATIVE_GRADE
            )
            if rc in (SACVARiskFactorType.INTEREST_RATE, SACVARiskFactorType.FX):
                kw["currency"] = s.bucket.upper()
                if rc is SACVARiskFactorType.INTEREST_RATE:
                    if s.risk_factor.upper() == INFLATION_FACTOR_KEY:
                        kw["is_inflation"] = True
                    elif s.risk_factor:
                        kw["tenor"] = float(s.risk_factor)
            elif rc is SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD:
                kw.update(
                    tenor=float(s.risk_factor), entity_id=s.name or s.bucket, credit_quality=quality
                )
                if s.bucket.isdigit():
                    kw["bucket"] = int(s.bucket)
                else:
                    kw["sector"] = (
                        normalize_sector(s.bucket) if s.bucket else CVASector.OTHER_SECTOR
                    )
            else:
                kw["bucket"] = int(s.bucket)
                kw["entity_id"] = s.name
                if rc is SACVARiskFactorType.REFERENCE_CREDIT_SPREAD:
                    kw["credit_quality"] = quality
            mapped.append(SACVASensitivity(**kw))  # type: ignore[arg-type]
        r = USSACVACalculator().calculate(mapped)
        return SACVAResult(
            jurisdiction=self.jurisdiction,
            k_by_class=r.k_by_risk_class,
            k_total=r.k_cva,
            rwa=r.rwa,
            m_cva=r.m_cva,
            r_hedging_disallowance=0.01,
            citations={"sa_cva": "ERBA NPR § __.224-__.225"},
        )

    # ------------------------------------------------------------ leverage
    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Total leverage exposure, 12 CFR 217.10(c)(2)(i)-(viii).

        Derivatives: RC net of eligible cash VM plus 1.4 x PFE (C = 0; the
        commercial end-user exception is applied by passing the PFE of those
        netting sets with ``flags['pfe_includes_alpha']`` already applied).
        """
        on_bs = inputs.on_balance_sheet_assets - inputs.tier1_deductions
        alpha = 1.0 if inputs.flags.get("pfe_includes_alpha") else LEVERAGE_PFE_ALPHA
        deriv = (
            max(inputs.derivative_rc - inputs.derivative_cash_vm_received, 0.0)
            + alpha * inputs.derivative_pfe_addon
            + max(
                inputs.written_credit_derivative_notional
                - inputs.written_credit_derivative_offsets,
                0.0,
            )
        )
        sft = (
            max(inputs.sft_gross_assets - inputs.sft_netted_cash_payables, 0.0)
            + inputs.sft_ccr_addon
        )
        obs = sum(n * max(ccf, LEVERAGE_MIN_CCF) for ccf, n in inputs.obs_notional_by_ccf.items())
        excl = inputs.client_cleared_trade_exposures_exempt
        return LeverageResult(
            jurisdiction=self.jurisdiction,
            on_balance_sheet=on_bs,
            derivatives=deriv,
            sfts=sft,
            off_balance_sheet=obs,
            exclusions=excl,
            total_exposure=on_bs + deriv + sft + obs - excl,
            citations={"total_leverage_exposure": "12 CFR 217.10(c)(2)"},
        )

    # ------------------------------------------------------------ large exposures
    def large_exposures(
        self,
        exposures: list[LargeExposureInput],
        tier1_capital: float,
        reporting_bank_is_gsib: bool,
    ) -> list[LargeExposureRow]:
        """SCCL limits, 12 CFR 252.72(a)-(b)."""
        rows: list[LargeExposureRow] = []
        for e in exposures:
            major = reporting_bank_is_gsib and e.counterparty_is_gsib
            pct = SCCL_MAJOR_LIMIT if major else SCCL_GENERAL_LIMIT
            limit = pct * tier1_capital
            rows.append(
                LargeExposureRow(
                    counterparty_id=e.counterparty_id,
                    exposure_value=e.exposure_value,
                    limit=limit,
                    limit_pct_of_tier1=pct,
                    reportable=e.exposure_value >= SCCL_REPORTING_FLAG * tier1_capital,
                    breach=(not e.is_exempt) and e.exposure_value > limit,
                    citation="12 CFR 252.72(b)" if major else "12 CFR 252.72(a)",
                )
            )
        return rows

    # ------------------------------------------------------------ CCP
    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """ERBA NPR § __.116 cleared transactions and default-fund contributions."""
        e = exposure
        if e.is_qualifying:
            trade_rw = (
                CCP_QCCP_CLIENT_NON_REMOTE_RW
                if e.is_client_cleared_via_member and not e.initial_margin_bankruptcy_remote
                else CCP_QCCP_RW
            )
            if e.k_ccp is not None and e.total_default_fund:
                k_cm = max(
                    e.k_ccp * e.default_fund_contribution / e.total_default_fund,
                    CCP_KCM_FLOOR * e.default_fund_contribution,
                )
            else:
                k_cm = (
                    e.default_fund_contribution * MINIMUM_CAPITAL_RATIO
                )  # TODO: VERIFY -- K_CCP needed
            df_rwa = RWA_PER_UNIT_CAPITAL * k_cm
        else:
            trade_rw = CCP_NON_QCCP_TRADE_RW
            df_rwa = e.default_fund_contribution * CCP_NON_QCCP_DEFAULT_FUND_RW
        trade_rwa = e.trade_exposure * trade_rw
        return CCPResult(
            ccp_id=e.ccp_id,
            jurisdiction=self.jurisdiction,
            trade_rw=trade_rw,
            trade_rwa=trade_rwa,
            default_fund_rwa=df_rwa,
            total_rwa=trade_rwa + df_rwa,
            citation="ERBA NPR § __.116",
        )
