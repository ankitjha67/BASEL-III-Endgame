"""United States regime adapter -- March 2026 ERBA NPR.

Wraps the engine's existing US calculators behind
:class:`src.jurisdictions.base.RegimeCalculator` so the US can be compared
line by line with the BCBS baseline and other jurisdictions:

- SA credit risk: :class:`src.credit_risk.sa.calculator.SACRCalculator`
  (Tables 1-8 to § __.111, § __.141 equity); CCFs § __.112
  (:class:`src.credit_risk.sa.obs_ccf.OBSCCFCalculator`); collateral haircuts
  § __.121 (:class:`src.credit_risk.crm.crm.CRMCalculator`); guarantees by
  substitution (§ __.120).
- Operational risk: § __.150 two-component BI, 12/15/18% BIC, no ILM
  (:class:`src.operational_risk.or_calculator.OpRiskCalculator`).
- Output floor: none -- the proposal replaces the dual advanced/standardised
  stack with the single expanded risk-based approach (no 72.5% floor).
- SA-CCR: § __.114 -- alpha 1.4, 1.0 for commercial end-users (§ __.114(e)(4));
  multiplier min(1; 0.05 + 0.95 exp((V-C)/(1.9 A))).
- BA-CVA: § __.222 via :class:`src.cva_risk.cva_calculator.CVACalculator`.
- Capital: 12 CFR 217.10 minimums; the SCB replaces the conservation buffer
  (12 CFR 217.11(a)); G-SIB surcharge per 12 CFR 217.403; eSLR 12 CFR 217.11(d).

Dodd-Frank s.939A: external ratings on :class:`SAExposure` are ignored.
All amounts in USD millions ($M).
"""

from __future__ import annotations

import math
from typing import Final

from src.capital.capital_params import (
    CCYB_MAXIMUM_RATE,
    CET1_MINIMUM_RATIO,
    SCB_FLOOR,
    SLR_ENHANCED_BUFFER,
    SLR_MINIMUM,
    TIER1_MINIMUM_RATIO,
    TOTAL_CAPITAL_MINIMUM_RATIO,
)
from src.counterparty_risk.saccr.saccr_params import ALPHA_FINANCIAL, ALPHA_NON_FINANCIAL, PFE_FLOOR
from src.credit_risk.crm.crm import CollateralType, CRMCalculator, CRMCollateral, CRMExposure
from src.credit_risk.sa.calculator import CreditExposure, SACRCalculator
from src.credit_risk.sa.exposure_classes import CRESubType, EquitySubType, ExposureClass
from src.credit_risk.sa.obs_ccf import OBSCategory as USOBSCategory
from src.credit_risk.sa.obs_ccf import OBSCCFCalculator
from src.credit_risk.sa.risk_weights import BankGrade
from src.cva_risk.cva_calculator import CVACalculator, CVACounterparty
from src.cva_risk.cva_params import CVACreditQuality
from src.jurisdictions.base import (
    AssetClass,
    CapitalRequirements,
    CreditRWAResult,
    EquityType,
    Jurisdiction,
    OBSCategory,
    OpRiskInputs,
    OpRiskResult,
    OutputFloorResult,
    PFPhase,
    RiskWeightResult,
    SACCRNettingSetInput,
    SACCRResult,
    SAExposure,
    SCRAGrade,
)
from src.operational_risk.or_calculator import BusinessIndicatorInputs, OpRiskCalculator

RWA_PER_UNIT_CAPITAL: Final[float] = 12.5
"""RWA = 12.5 x capital requirement (12 CFR 217.10; § __.150(a))."""

SHORT_TERM_TRADE_MONTHS: Final[float] = 3.0
"""Table 2 to § __.111: foreign-bank self-liquidating trade-related contingent items <= 3 months."""

SACCR_MULTIPLIER_DENOMINATOR: Final[float] = 2.0 * (1.0 - PFE_FLOOR)
"""§ __.114: multiplier = min(1; 0.05 + 0.95 exp((V - C) / (1.9 x AddOn)))."""

_OBS_MAP: Final[dict[OBSCategory, USOBSCategory]] = {
    OBSCategory.UNCONDITIONALLY_CANCELLABLE: USOBSCategory.UCC,
    OBSCategory.COMMITMENT_OTHER: USOBSCategory.COMMITMENT_GT_1Y,
    OBSCategory.NIF_RUF: USOBSCategory.NIF,
    OBSCategory.TRANSACTION_RELATED_CONTINGENT: USOBSCategory.TRANSACTION_CONTINGENCY,
    OBSCategory.SHORT_TERM_TRADE_LC: USOBSCategory.TRADE_LC,
    OBSCategory.DIRECT_CREDIT_SUBSTITUTE: USOBSCategory.DIRECT_CREDIT_SUB,
    OBSCategory.SECURITIES_LENDING_COLLATERAL: USOBSCategory.SEC_LENDING,
    OBSCategory.FORWARD_ASSET_PURCHASE: USOBSCategory.FORWARD_PURCHASE,
    OBSCategory.OTHER_100: USOBSCategory.DIRECT_CREDIT_SUB,
}
"""Neutral OBS categories -> § __.112 categories (all commitments 40% regardless of maturity)."""

_EQUITY_MAP: Final[dict[EquityType, EquitySubType]] = {
    EquityType.GENERAL: EquitySubType.PUBLIC_TRADED,
    EquityType.PUBLICLY_TRADED: EquitySubType.PUBLIC_TRADED,
    EquityType.NON_PUBLIC: EquitySubType.SPECULATIVE,
    EquityType.SPECULATIVE_UNLISTED: EquitySubType.SPECULATIVE,
    EquityType.LEGISLATIVE_PROGRAMME: EquitySubType.COMMUNITY_DEVELOPMENT,
    EquityType.SIGNIFICANT_FI: EquitySubType.SIGNIFICANT_FI_NOT_DEDUCTED,
}
"""Neutral equity types -> § __.141 sub-types (300% publicly traded, 400% non-public)."""

_BANK_GRADE: Final[dict[SCRAGrade, BankGrade]] = {
    SCRAGrade.A: BankGrade.GRADE_A,
    SCRAGrade.B: BankGrade.GRADE_B,
    SCRAGrade.C: BankGrade.GRADE_C,
}
"""The ERBA Grade A/B/C bank taxonomy (§ __.101) corresponds to the SCRA grades."""


_US_CVA_QUALITY: Final[dict[str, CVACreditQuality]] = {
    "IG": CVACreditQuality.INVESTMENT_GRADE,
    "HY_NR": CVACreditQuality.SPECULATIVE_GRADE,
    "HY": CVACreditQuality.SPECULATIVE_GRADE,
    "NR": CVACreditQuality.SPECULATIVE_GRADE,
}
"""Cross-regime BA-CVA credit-quality labels -> Table 1 to § __.222 columns."""


class USRegime:
    """United States: March 2026 ERBA NPR (OCC NR 2026-16a)."""

    jurisdiction: Jurisdiction = Jurisdiction.US
    regime_name: str = "US ERBA NPR (March 2026)"
    legal_basis: str = (
        "Regulatory Capital Rule: Category I and II Banking Organizations ... "
        "(OCC/Board/FDIC NPR, March 2026), common rule text §§ __.101-__.225"
    )

    def __init__(self) -> None:
        """Build the wrapped calculators."""
        self._sacr = SACRCalculator()
        self._ccf = OBSCCFCalculator()
        self._crm = CRMCalculator()

    # ------------------------------------------------------------------ credit
    def _to_credit_exposure(self, e: SAExposure, ead: float) -> CreditExposure:
        """Map a neutral exposure to the ERBA :class:`CreditExposure` (§ __.111)."""
        kw: dict[str, object] = {}
        ac = e.asset_class
        if ac == AssetClass.SOVEREIGN:
            cls = ExposureClass.SOVEREIGN
            kw["is_us_sovereign"] = e.flags.get("is_us_sovereign", e.oecd_crc in (None, 0))
            if e.oecd_crc is not None:
                kw["country_risk_class"] = e.oecd_crc
        elif ac == AssetClass.PSE:
            cls = ExposureClass.PUBLIC_SECTOR_ENTITY
            if e.oecd_crc is not None:
                kw["country_risk_class"] = e.oecd_crc
        elif ac == AssetClass.MDB:
            cls = ExposureClass.MULTILATERAL_DEV_BANK
        elif ac in (AssetClass.BANK, AssetClass.COVERED_BOND):
            # No covered-bond weight in the ERBA NPR: a covered bond is a bank exposure.
            cls = ExposureClass.BANK
            kw["bank_grade"] = _BANK_GRADE[e.scra_grade or SCRAGrade.C]
            kw["bank_meets_enhanced_criteria"] = e.scra_grade_a_enhanced
            kw["is_short_term_trade_related"] = bool(
                e.is_trade_related
                and (e.original_maturity_months or math.inf) <= SHORT_TERM_TRADE_MONTHS
            )
        elif ac in (
            AssetClass.CORPORATE,
            AssetClass.SPECIALISED_LENDING_OF,
            AssetClass.SPECIALISED_LENDING_CF,
        ):
            # Object and commodities finance have no separate US weight (§ __.111(h)).
            cls = ExposureClass.CORPORATE
            kw["is_investment_grade"] = bool(e.is_investment_grade)
        elif ac == AssetClass.CORPORATE_SME:
            cls = ExposureClass.CORPORATE_SME
            kw["is_sme"] = True
            kw["is_investment_grade"] = bool(e.is_investment_grade)
        elif ac == AssetClass.SPECIALISED_LENDING_PF:
            cls = ExposureClass.CORPORATE
            kw["is_project_finance"] = True
            kw["is_project_finance_operational"] = e.pf_phase in (
                PFPhase.OPERATIONAL,
                PFPhase.HIGH_QUALITY_OPERATIONAL,
            )
        elif ac == AssetClass.SUBORDINATED_DEBT:
            cls = ExposureClass.SUBORDINATED_DEBT
            kw["is_subordinated"] = True
        elif ac == AssetClass.EQUITY:
            cls = ExposureClass.EQUITY
            kw["equity_sub_type"] = _EQUITY_MAP[e.equity_type or EquityType.GENERAL]
        elif ac == AssetClass.RETAIL_REGULATORY:
            cls = (
                ExposureClass.RETAIL
                if e.meets_regulatory_retail_criteria
                else ExposureClass.RETAIL_OTHER
            )
        elif ac == AssetClass.RETAIL_TRANSACTOR:
            cls = ExposureClass.RETAIL_TRANSACTOR
            kw["is_transactor"] = True
        elif ac == AssetClass.RETAIL_OTHER:
            cls = ExposureClass.RETAIL_OTHER
        elif ac == AssetClass.RESIDENTIAL_RE:
            cls = ExposureClass.RESIDENTIAL_MORTGAGE
            kw["ltv_ratio"] = e.ltv
            kw["is_dependent_on_cash_flows"] = e.is_cash_flow_dependent
            kw["is_regulatory_real_estate"] = e.is_regulatory_real_estate
        elif ac == AssetClass.COMMERCIAL_RE:
            cls = ExposureClass.COMMERCIAL_REAL_ESTATE
            kw["ltv_ratio"] = e.ltv
            kw["is_dependent_on_cash_flows"] = e.is_cash_flow_dependent
            kw["is_regulatory_real_estate"] = e.is_regulatory_real_estate
            kw["cre_sub_type"] = (
                CRESubType.INCOME_PRODUCING
                if e.is_cash_flow_dependent
                else CRESubType.REGULATORY_CRE
            )
        elif ac == AssetClass.LAND_ADC:
            cls = ExposureClass.COMMERCIAL_REAL_ESTATE
            kw["cre_sub_type"] = (
                CRESubType.PRESOLD_CONSTRUCTION
                if e.is_adc_presold_or_equity_at_risk
                else CRESubType.ADC
            )
            kw["is_presold_adc"] = e.is_adc_presold_or_equity_at_risk
        elif ac == AssetClass.DEFAULTED:
            cls = ExposureClass.DEFAULTED
        else:
            cls = ExposureClass.OTHER
        if e.is_defaulted and cls not in (
            ExposureClass.RESIDENTIAL_MORTGAGE,
            ExposureClass.DEFAULTED,
        ):
            cls = ExposureClass.DEFAULTED
        elif e.is_defaulted:
            kw["is_past_due"] = True
        return CreditExposure(
            exposure_id=e.exposure_id,
            exposure_class=cls,
            counterparty=e.counterparty or e.exposure_id,
            ead=ead,
            maturity_years=e.residual_maturity_years or 1.0,
            **kw,
        )

    def ccf(self, exposure: SAExposure) -> float:
        """§ __.112 CCF for the off-balance part (10% UCC; 40% all other commitments; ...)."""
        if exposure.off_balance_notional <= 0 or exposure.obs_category is None:
            return 0.0
        return self._ccf.get_ccf(_OBS_MAP[exposure.obs_category])

    def _apply_crm(self, e: SAExposure, amount: float) -> tuple[float, list[str]]:
        """§ __.121 collateral haircut approach: E* = max(0, E(1+He) - C(1-Hc-Hfx))."""
        notes: list[str] = []
        if e.financial_collateral_value <= 0:
            return amount, notes
        ctype = CollateralType(e.collateral_haircut_class or CollateralType.OTHER.value)
        coll = CRMCollateral(
            collateral_id=f"{e.exposure_id}-C",
            collateral_type=ctype,
            market_value=e.financial_collateral_value,
            residual_maturity_years=e.residual_maturity_years,
        )
        e_star = self._crm.apply_collateral(
            CRMExposure(exposure_id=e.exposure_id, exposure_amount=amount, risk_weight=1.0), coll
        )
        notes.append(f"§ __.121 collateral haircut ({ctype.value}): E*={e_star:,.2f}")
        return e_star, notes

    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CCF and RWA under Tables 1-8 to § __.111 / § __.141."""
        ccf = self.ccf(exposure)
        gross = exposure.on_balance_amount + ccf * exposure.off_balance_notional
        amount, notes = self._apply_crm(exposure, gross)
        ce = self._to_credit_exposure(exposure, amount)
        rw = self._sacr.get_risk_weight(ce)
        rwa = amount * rw
        if exposure.guarantee_amount > 0 and exposure.guarantor_asset_class is not None:
            covered = min(exposure.guarantee_amount, amount)
            g = exposure.model_copy(
                update={
                    "asset_class": exposure.guarantor_asset_class,
                    "is_defaulted": False,
                    "guarantee_amount": 0.0,
                    "financial_collateral_value": 0.0,
                }
            )
            g_rw = self._sacr.get_risk_weight(self._to_credit_exposure(g, covered))
            if g_rw < rw:
                rwa = covered * g_rw + (amount - covered) * rw
                notes.append(f"§ __.120 guarantee substitution: {covered:,.2f} at {g_rw:.0%}")
        return RiskWeightResult(
            exposure_id=exposure.exposure_id,
            jurisdiction=self.jurisdiction,
            regime_exposure_class=ce.exposure_class.value,
            risk_weight=rw,
            ccf=ccf,
            exposure_amount=amount,
            rwa=rwa,
            citation=f"ERBA NPR § __.111 / § __.141 ({ce.exposure_class.value})",
            notes=notes,
        )

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """Portfolio SA credit RWA."""
        items = [self.risk_weight(e) for e in exposures]
        by_rwa: dict[str, float] = {}
        by_exp: dict[str, float] = {}
        for e, r in zip(exposures, items, strict=True):
            by_rwa[e.asset_class.value] = by_rwa.get(e.asset_class.value, 0.0) + r.rwa
            by_exp[e.asset_class.value] = by_exp.get(e.asset_class.value, 0.0) + r.exposure_amount
        return CreditRWAResult(
            jurisdiction=self.jurisdiction,
            total_exposure=sum(r.exposure_amount for r in items),
            total_rwa=sum(r.rwa for r in items),
            rwa_by_class=by_rwa,
            exposure_by_class=by_exp,
            line_items=items,
        )

    # ------------------------------------------------------------------ op risk
    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """§ __.150: RWA = 12.5 x BIC with no loss multiplier.

        The neutral BCBS-style BI items map to the FR Y-9C lines the US BI uses:
        noninterest income = fee + other operating income + net trading P&L;
        realized securities gains = net banking-book P&L; noninterest expense
        for BI = fee + other operating expense.
        """
        nii = [
            f + o + t
            for f, o, t in zip(
                inputs.fee_income,
                inputs.other_operating_income,
                inputs.net_pnl_trading_book,
                strict=True,
            )
        ]
        nie = [
            f + o for f, o in zip(inputs.fee_expense, inputs.other_operating_expense, strict=True)
        ]
        losses = (
            inputs.annual_operational_losses[-3:]
            if len(inputs.annual_operational_losses) >= 3
            else None
        )
        bi_inputs = BusinessIndicatorInputs(
            total_interest_income=list(inputs.interest_income),
            total_interest_expense=list(inputs.interest_expense),
            interest_earning_assets=list(inputs.interest_earning_assets),
            dividend_income=list(inputs.dividend_income),
            total_noninterest_income=nii,
            realized_gains_losses_afs_debt_securities=list(inputs.net_pnl_banking_book),
            noninterest_expense_for_bi=nie,
            total_operational_losses=losses,
        )
        r = OpRiskCalculator().calculate(bi_inputs)
        return OpRiskResult(
            jurisdiction=self.jurisdiction,
            business_indicator=r.business_indicator,
            bic=r.bic,
            loss_component=None,
            ilm=r.ilm,
            capital=r.capital_charge,
            rwa=r.rwa,
            citation="ERBA NPR § __.150(a)-(c); no ILM",
            components={"ildc": r.ildc, "noninterest_component": r.noninterest_component},
        )

    # ------------------------------------------------------------------ floor
    def output_floor(
        self, pre_floor_rwa: float, standardised_rwa: float, year: int
    ) -> OutputFloorResult:
        """No output floor: the ERBA NPR uses a single expanded risk-based approach."""
        return OutputFloorResult(
            jurisdiction=self.jurisdiction,
            applies=False,
            floor_factor=0.0,
            pre_floor_rwa=pre_floor_rwa,
            standardised_rwa=standardised_rwa,
            floored_rwa=pre_floor_rwa,
            add_on=0.0,
            citation="ERBA NPR (March 2026): no output floor; no internal models for credit risk",
            notes=["US banks compute RWA under the expanded risk-based approach only"],
        )

    # ------------------------------------------------------------------ capital
    def capital_requirements(
        self,
        systemic_bucket_or_rate: float = 0.0,
        countercyclical_rate: float = 0.0,
        stress_buffer: float = SCB_FLOOR,
    ) -> CapitalRequirements:
        """12 CFR 217.10 minimums; SCB (floor 2.5%) in place of the CCB; G-SIB surcharge rate.

        Args:
            systemic_bucket_or_rate: G-SIB surcharge as a decimal rate (12 CFR 217.403).
            countercyclical_rate: CCyB (0 to 2.5%, 12 CFR 217.11(b)).
            stress_buffer: Stress capital buffer (floored at 2.5%).
        """
        if not 0.0 <= countercyclical_rate <= CCYB_MAXIMUM_RATE:
            raise ValueError("CCyB must be between 0 and 2.5%")
        # TODO: VERIFY -- eSLR buffer per current 12 CFR 217.11(d)(4) (2%); later
        # eSLR amendments are outside the sources reviewed for this engine.
        return CapitalRequirements(
            jurisdiction=self.jurisdiction,
            cet1_minimum=CET1_MINIMUM_RATIO,
            tier1_minimum=TIER1_MINIMUM_RATIO,
            total_capital_minimum=TOTAL_CAPITAL_MINIMUM_RATIO,
            conservation_buffer=0.0,
            countercyclical_buffer=countercyclical_rate,
            systemic_buffer=systemic_bucket_or_rate,
            stress_buffer=max(stress_buffer, SCB_FLOOR),
            leverage_minimum=SLR_MINIMUM,
            leverage_buffer=SLR_ENHANCED_BUFFER,
            citations={
                "minimums": "12 CFR 217.10(a)",
                "scb": "12 CFR 217.11(a); 225.8",
                "gsib": "12 CFR 217.403",
                "ccyb": "12 CFR 217.11(b)",
                "eslr": "12 CFR 217.10(a)(4), 217.11(d)(4)",
            },
        )

    # ------------------------------------------------------------------ SA-CCR
    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """§ __.114: EAD = alpha x (RC + multiplier x AddOn); alpha 1.0 for commercial end-users."""
        alpha = ALPHA_NON_FINANCIAL if netting_set.counterparty_is_nonfinancial else ALPHA_FINANCIAL
        a = netting_set.aggregate_addon
        if a > 0:
            mult = min(
                1.0,
                PFE_FLOOR
                + (1.0 - PFE_FLOOR)
                * math.exp(
                    (netting_set.mtm - netting_set.net_collateral)
                    / (SACCR_MULTIPLIER_DENOMINATOR * a)
                ),
            )
        else:
            mult = 1.0
        pfe = mult * a
        return SACCRResult(
            jurisdiction=self.jurisdiction,
            netting_set_id=netting_set.netting_set_id,
            alpha=alpha,
            multiplier=mult,
            pfe=pfe,
            ead=alpha * (netting_set.replacement_cost + pfe),
            citation="ERBA NPR § __.114(c), (e)(4)",
        )

    # ------------------------------------------------------------------ CVA
    def ba_cva_capital(
        self,
        counterparties: list[dict[str, float | str | bool]],
        hedged: bool = False,
    ) -> dict[str, float]:
        """§ __.222 BA-CVA via the engine's CVA calculator (reduced form without hedges).

        ``credit_quality`` accepts the cross-regime labels "IG" and "HY_NR" as
        well as internal grade labels; "HY_NR" maps to speculative grade (the
        Table 1 to § __.222 sub-speculative column requires an internal grade).
        """
        cps = [
            CVACounterparty(
                counterparty_id=str(c.get("id", i)),
                sector=str(c["sector"]),
                credit_quality=_US_CVA_QUALITY.get(str(c["credit_quality"]).upper(),
                                                   str(c["credit_quality"])),
                is_commercial_end_user=bool(c.get("commercial_end_user", False)),
                ead=float(c["ead"]),
                effective_maturity=float(c["maturity"]),
            )
            for i, c in enumerate(counterparties)
        ]
        res = CVACalculator().calculate(counterparties=cps)
        return {"k_reduced": res.k_unhedged, "k": res.k_cva, "rwa": res.rwa}
