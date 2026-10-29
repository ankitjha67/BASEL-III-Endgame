"""United States market risk -- ERBA NPR Subpart F, behind :class:`MarketRiskCalculator`.

Maps the regime-neutral sensitivities and positions of
:mod:`src.jurisdictions.frtb_base` onto the engine's US FRTB calculators
(:class:`src.market_risk.frtb.calculator.FRTBCalculator`):

- bucket assignment from descriptors per ERBA NPR § __.209 Tables 1-11:
  GIRR by currency; CSR non-securitisation by sector x internally-assessed
  credit quality (Table 3, 20 buckets); CSR securitisation non-CTP by
  seniority x quality x asset type (Table 7, 25 buckets); CTP by sector x
  quality (Table 5); equity by market cap x economy x sector (Table 8,
  13 buckets); commodity by group (Table 9, 12 buckets); FX by pair;
- DRC per § __.210 (four non-securitisation buckets, Table 1 risk weights,
  LGD by seniority; securitisation non-CTP and CTP);
- RRAO per § __.211.

Credit quality is the bank's internal assessment (Dodd-Frank s.939A): an
exposure flagged ``is_investment_grade`` is investment grade; otherwise
ratings below B- (or ``flags['sub_speculative']``) are sub-speculative and
everything else speculative.

Curvature: the US engine scores one net CVR per curvature risk factor, so
the adapter passes the more adverse of CVR+ and CVR- (``max``), which is at
least as large as either branch of the § __.206(b)(3) max(K+, K-) test.

All amounts in USD millions ($M).
"""

from __future__ import annotations

from typing import Final

from src.core.enums import (
    CreditQuality,
    CSRSecAssetType,
    CSRSecSeniority,
    CSRSector,
    DRCCreditQuality,
    DRCExposureType,
    DRCSecBucket,
    DRCSecRegion,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.enums import DRCSeniority as USDRCSeniority
from src.core.enums import RRAOCategory as USRRAOCategory
from src.core.models import RRAOPosition, Sensitivity
from src.jurisdictions.base import Jurisdiction, RatingBucket
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
    MarketRiskResult,
    RRAOCategory,
    RRAOPositionInput,
    SBMClassResult,
    SecAssetClass,
    SecTrancheClass,
)
from src.market_risk.frtb.calculator import FRTBCalculator, FRTBResult
from src.market_risk.frtb.drc.drc_nonsec import DRCPosition as USDRCPosition
from src.market_risk.frtb.drc.drc_sec_ctp import DRCSecCTPPosition
from src.market_risk.frtb.drc.drc_sec_nonctp import DRCSecNonCTPPosition
from src.market_risk.frtb.sbm.csr_nonsec_params import get_bucket_for_sector_quality
from src.market_risk.frtb.sbm.csr_sec_params import (
    get_ctp_bucket_for_sector_quality,
    get_non_ctp_bucket,
)

RWA_PER_UNIT_CAPITAL: Final[float] = 12.5
"""RWA = 12.5 x market-risk capital (ERBA NPR § __.201 / 12 CFR 217.10)."""
REPORTING_CURRENCY: Final[str] = "USD"

_TENORS: Final[dict[float, GIRRTenor]] = {t.value: t for t in GIRRTenor}

_RISK_CLASS: Final[dict[FRTBRiskClass, RiskClass]] = {
    FRTBRiskClass.GIRR: RiskClass.GIRR,
    FRTBRiskClass.CSR_NONSEC: RiskClass.CSR_NON_SEC,
    FRTBRiskClass.CSR_SEC_NONCTP: RiskClass.CSR_SEC_NON_CTP,
    FRTBRiskClass.CSR_SEC_CTP: RiskClass.CSR_SEC_CTP,
    FRTBRiskClass.EQUITY: RiskClass.EQUITY,
    FRTBRiskClass.COMMODITY: RiskClass.COMMODITY,
    FRTBRiskClass.FX: RiskClass.FX,
}
_MEASURE: Final[dict[FRTBMeasure, RiskMeasure]] = {
    FRTBMeasure.DELTA: RiskMeasure.DELTA,
    FRTBMeasure.VEGA: RiskMeasure.VEGA,
    FRTBMeasure.CURVATURE: RiskMeasure.CURVATURE,
}
_GIRR_CURVE: Final[dict[GIRRCurve, GIRRRiskFactorType]] = {
    GIRRCurve.RISK_FREE: GIRRRiskFactorType.YIELD_CURVE,
    GIRRCurve.INFLATION: GIRRRiskFactorType.INFLATION,
    GIRRCurve.XCCY_BASIS: GIRRRiskFactorType.CROSS_CURRENCY_BASIS,
}
_CSR_SECTOR: Final[dict[CreditSector, CSRSector]] = {
    CreditSector.SOVEREIGN: CSRSector.SOVEREIGN,
    CreditSector.LOCAL_GOVERNMENT: CSRSector.PSE,
    CreditSector.FINANCIAL: CSRSector.FINANCIALS,
    CreditSector.BASIC_MATERIALS: CSRSector.BASIC_MATERIALS,
    CreditSector.CONSUMER: CSRSector.CONSUMER,
    CreditSector.TECHNOLOGY: CSRSector.TECH_TELECOM,
    CreditSector.HEALTH_CARE: CSRSector.HEALTHCARE_UTILITIES,
    CreditSector.COVERED_BOND: CSRSector.COVERED_BOND,
    CreditSector.OTHER: CSRSector.OTHER,
    CreditSector.INDEX: CSRSector.INDEX,
}
"""Neutral credit sectors -> Table 3 to § __.209 sectors."""

_SEC_ASSET: Final[dict[SecAssetClass, CSRSecAssetType]] = {
    SecAssetClass.RMBS_PRIME: CSRSecAssetType.RMBS_PRIME,
    SecAssetClass.RMBS_MIDPRIME: CSRSecAssetType.RMBS_MIDPRIME,
    SecAssetClass.RMBS_SUBPRIME: CSRSecAssetType.RMBS_SUBPRIME,
    SecAssetClass.CMBS: CSRSecAssetType.CMBS,
    SecAssetClass.ABS_STUDENT_LOANS: CSRSecAssetType.ABS_STUDENT_LOANS,
    SecAssetClass.ABS_CREDIT_CARDS: CSRSecAssetType.ABS_CREDIT_CARDS_PERSONAL,
    SecAssetClass.ABS_AUTO: CSRSecAssetType.ABS_AUTO_FLOORPLAN,
    SecAssetClass.CLO_NON_CTP: CSRSecAssetType.CLO_NON_CTP,
    SecAssetClass.OTHER: CSRSecAssetType.OTHER,
}

# Table 8 to § __.209: large cap EM 1-4, large cap advanced 5-8 (same sector order),
# small cap EM 9, small cap advanced 10, other sector 11, large-cap advanced
# indices 12, other indices 13.
_EQUITY_SECTOR_OFFSET: Final[dict[EquitySector, int]] = {
    EquitySector.CONSUMER_HEALTH_UTILITIES: 1,
    EquitySector.TELECOM_INDUSTRIALS: 2,
    EquitySector.MATERIALS_ENERGY: 3,
    EquitySector.FINANCIALS_REALESTATE_TECH: 4,
}
EQUITY_LARGE_CAP_ADVANCED_OFFSET: Final[int] = 4
EQUITY_SMALL_CAP_EM_BUCKET: Final[int] = 9
EQUITY_SMALL_CAP_ADVANCED_BUCKET: Final[int] = 10
EQUITY_OTHER_SECTOR_BUCKET: Final[int] = 11
EQUITY_LARGE_CAP_INDEX_BUCKET: Final[int] = 12
EQUITY_OTHER_INDEX_BUCKET: Final[int] = 13

# Table 9 to § __.209 commodity buckets.
_COMMODITY_BUCKET: Final[dict[CommodityGroup, int]] = {
    CommodityGroup.ENERGY_SOLID: 1,
    CommodityGroup.ENERGY_LIQUID: 2,
    CommodityGroup.ENERGY_ELECTRICITY_CARBON: 3,  # Table 9 bucket 3 "energy -- carbon trading"
    CommodityGroup.FREIGHT: 4,
    CommodityGroup.METALS_NON_PRECIOUS: 5,
    CommodityGroup.GASEOUS_ENERGY: 6,  # Table 9 bucket 6 "gaseous combustibles & electricity"
    CommodityGroup.PRECIOUS_METALS: 7,
    CommodityGroup.GRAINS_OILSEED: 8,
    CommodityGroup.LIVESTOCK_DAIRY: 9,
    CommodityGroup.SOFTS_OTHER_AGRI: 10,
    CommodityGroup.OTHER: 11,
}
COMMODITY_INDEX_BUCKET: Final[int] = 12

_DRC_SENIORITY: Final[dict[DRCSeniority, USDRCSeniority]] = {
    DRCSeniority.COVERED_BOND: USDRCSeniority.COVERED_BOND,
    DRCSeniority.SENIOR: USDRCSeniority.SENIOR_UNSECURED,
    DRCSeniority.NON_SENIOR: USDRCSeniority.SUBORDINATED,
    DRCSeniority.EQUITY: USDRCSeniority.EQUITY,
}
"""Neutral seniority -> § __.210(b)(1)(iv) LGD classes (100/75/25%)."""

_SUB_SPEC_RATINGS: Final[frozenset[RatingBucket]] = frozenset({RatingBucket.BELOW_B_MINUS})

# § __.215 Table 2 liquidity horizons (business days), ERBA reference doc.
US_LIQUIDITY_HORIZONS: Final[dict[str, int]] = {
    "IR_specified_currencies_and_inflation": 10,
    "IR_other_currencies": 20,
    "IR_volatility": 60,
    "IR_other": 60,
    "CS_sovereign_IG": 20,
    "CS_sovereign_spec_subspec": 40,
    "CS_GSE_debt": 40,
    "CS_corporate_IG": 40,
    "CS_corporate_spec_subspec": 60,
    "CS_volatility": 120,
    "CS_other": 120,
    "EQ_large_cap_and_index": 10,
    "EQ_small_cap": 20,
    "EQ_large_cap_volatility": 20,
    "EQ_small_cap_volatility": 60,
    "EQ_other": 60,
    "FX_specified_pairs": 10,
    "FX_other_pairs": 20,
    "FX_volatility": 40,
    "FX_other": 40,
    "COM_energy_carbon": 20,
    "COM_precious_nonferrous": 20,
    "COM_other": 60,
    "COM_energy_volatility": 60,
    "COM_metals_volatility": 60,
    "COM_other_volatility": 120,
    "COM_other_types": 120,
}
# § __.204 Table 1 backtesting multiplier (exceptions -> multiplier).
US_BACKTESTING_MULTIPLIER: Final[dict[int, float]] = {
    0: 1.50,
    1: 1.50,
    2: 1.50,
    3: 1.50,
    4: 1.50,
    5: 1.70,
    6: 1.76,
    7: 1.83,
    8: 1.88,
    9: 1.92,
    10: 2.00,
}
US_ES_CONFIDENCE: Final[float] = 0.975
US_IMCC_OMEGA: Final[float] = 0.5
US_SES_RHO: Final[float] = 0.36
US_PLA_KS_THRESHOLDS: Final[tuple[float, float]] = (0.09, 0.12)


def us_credit_quality(
    rating: RatingBucket, is_ig: bool | None, flags: dict[str, bool]
) -> CreditQuality:
    """Internally-assessed credit quality category (§ __.2 definitions; s.939A)."""
    if is_ig:
        return CreditQuality.INVESTMENT_GRADE
    if flags.get("sub_speculative") or rating in _SUB_SPEC_RATINGS:
        return CreditQuality.SUB_SPECULATIVE_GRADE
    if is_ig is None and rating in (
        RatingBucket.AAA_TO_AA_MINUS,
        RatingBucket.A_PLUS_TO_A_MINUS,
        RatingBucket.BBB_PLUS_TO_BBB_MINUS,
    ):
        return CreditQuality.INVESTMENT_GRADE
    return CreditQuality.SPECULATIVE_GRADE


class USMarketRisk:
    """US ERBA NPR Subpart F market risk (FRTB standardised approach)."""

    jurisdiction: Jurisdiction = Jurisdiction.US

    def __init__(self) -> None:
        """Build the wrapped calculator."""
        self._calc = FRTBCalculator()

    # ------------------------------------------------------------ buckets
    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """Bucket under § __.209 for a neutral sensitivity."""
        rc = s.risk_class
        if s.bucket_hint and s.flags.get("use_bucket_hint"):
            return s.bucket_hint
        if rc == FRTBRiskClass.GIRR:
            if not s.currency:
                raise ValueError("GIRR sensitivity needs a currency (§ __.209(b)(1))")
            return s.currency.upper()
        if rc == FRTBRiskClass.FX:
            if not s.fx_currency:
                raise ValueError("FX sensitivity needs fx_currency (§ __.209(b)(7))")
            return f"{s.fx_currency.upper()}{REPORTING_CURRENCY}"
        q = us_credit_quality(s.rating, s.is_investment_grade, s.flags)
        if rc == FRTBRiskClass.CSR_NONSEC:
            return str(
                get_bucket_for_sector_quality(_CSR_SECTOR[s.credit_sector or CreditSector.OTHER], q)
            )
        if rc == FRTBRiskClass.CSR_SEC_CTP:
            return str(
                get_ctp_bucket_for_sector_quality(
                    _CSR_SECTOR[s.credit_sector or CreditSector.OTHER], q
                )
            )
        if rc == FRTBRiskClass.CSR_SEC_NONCTP:
            seniority = (
                CSRSecSeniority.SENIOR
                if s.sec_tranche_class == SecTrancheClass.SENIOR_IG
                else CSRSecSeniority.NON_SENIOR
            )
            if s.sec_tranche_class == SecTrancheClass.HY_NR:
                q = CreditQuality.SPECULATIVE_GRADE if q == CreditQuality.INVESTMENT_GRADE else q
            return str(
                get_non_ctp_bucket(
                    seniority, q, _SEC_ASSET[s.sec_asset_class or SecAssetClass.OTHER]
                )
            )
        if rc == FRTBRiskClass.EQUITY:
            return str(self._equity_bucket(s))
        if rc == FRTBRiskClass.COMMODITY:
            if s.flags.get("commodity_index"):
                return str(COMMODITY_INDEX_BUCKET)
            return str(_COMMODITY_BUCKET[s.commodity_group or CommodityGroup.OTHER])
        raise ValueError(f"unsupported risk class {rc}")

    @staticmethod
    def _equity_bucket(s: FRTBSensitivity) -> int:
        """Table 8 to § __.209 equity bucket."""
        advanced = bool(s.is_advanced_economy)
        if s.is_equity_index:
            return (
                EQUITY_LARGE_CAP_INDEX_BUCKET
                if (advanced and s.is_large_cap)
                else EQUITY_OTHER_INDEX_BUCKET
            )
        if s.equity_sector in (None, EquitySector.OTHER):
            return EQUITY_OTHER_SECTOR_BUCKET
        if s.is_large_cap:
            base = _EQUITY_SECTOR_OFFSET[s.equity_sector]
            return base + EQUITY_LARGE_CAP_ADVANCED_OFFSET if advanced else base
        return EQUITY_SMALL_CAP_ADVANCED_BUCKET if advanced else EQUITY_SMALL_CAP_EM_BUCKET

    def _to_us(self, s: FRTBSensitivity) -> Sensitivity:
        """Translate one neutral sensitivity to the engine's US model."""
        bucket = self.assign_bucket(s)
        value = s.value
        if s.measure == FRTBMeasure.CURVATURE:
            value = max(s.cvr_up or 0.0, s.cvr_down or 0.0)
        tenor: GIRRTenor | None = None
        if s.tenor_years is not None:
            if s.tenor_years not in _TENORS:
                raise ValueError(f"tenor {s.tenor_years}y is not a § __.208 vertex")
            tenor = _TENORS[s.tenor_years]
        rc = s.risk_class
        if rc == FRTBRiskClass.GIRR:
            label = s.curve_name or "OIS"
        elif rc in (FRTBRiskClass.CSR_NONSEC, FRTBRiskClass.CSR_SEC_CTP):
            label = f"{s.issuer or s.label}::{'CDS' if s.is_cds else 'BOND'}"
        elif rc == FRTBRiskClass.CSR_SEC_NONCTP:
            label = f"{s.tranche_id or s.label}::{'CDS' if s.is_cds else 'BOND'}"
        elif rc == FRTBRiskClass.EQUITY:
            name = s.issuer or s.label
            label = f"{name}|REPO" if s.equity_risk_factor == EquityRiskFactor.REPO else name
        elif rc == FRTBRiskClass.COMMODITY:
            label = s.delivery_location or s.commodity_name or "DEFAULT"
        else:
            label = bucket
        return Sensitivity(
            risk_class=_RISK_CLASS[rc],
            risk_measure=_MEASURE[s.measure],
            bucket=bucket,
            risk_factor_type=_GIRR_CURVE[s.girr_curve],
            tenor=tenor,
            label=label,
            value=value,
            option_maturity=s.option_maturity_years,
        )

    # ------------------------------------------------------------ DRC / RRAO
    @staticmethod
    def _drc_quality(p: DRCPositionInput) -> DRCCreditQuality:
        """§ __.210 Table 1 credit-quality column."""
        if p.is_defaulted:
            return DRCCreditQuality.DEFAULTED
        q = us_credit_quality(p.rating, p.is_investment_grade, p.flags)
        return {
            CreditQuality.INVESTMENT_GRADE: DRCCreditQuality.INVESTMENT_GRADE,
            CreditQuality.SPECULATIVE_GRADE: DRCCreditQuality.SPECULATIVE_GRADE,
            CreditQuality.SUB_SPECULATIVE_GRADE: DRCCreditQuality.SUB_SPECULATIVE_GRADE,
        }[q]

    def _to_us_drc(self, p: DRCPositionInput) -> object:
        """Translate a neutral DRC position (§ __.210(b)-(d))."""
        if p.kind == DRCKind.SEC_NON_CTP:
            return DRCSecNonCTPPosition(
                tranche_id=p.tranche_id or p.position_id,
                pool_id=p.pool_id or p.obligor,
                asset_class=DRCSecBucket.CORPORATE
                if p.sec_asset_class is None
                else _DRC_SEC_BUCKET.get(p.sec_asset_class, DRCSecBucket.CORPORATE),
                region=None
                if p.sec_asset_class is None
                else DRCSecRegion(p.region or "NORTH_AMERICA"),
                market_value=abs(p.market_value),
                maturity_years=p.maturity_years,
                is_long=p.is_long,
                banking_book_risk_weight=p.banking_book_risk_weight,
            )
        if p.kind == DRCKind.CTP:
            return DRCSecCTPPosition(
                tranche_id=p.tranche_id or p.position_id,
                index_name=p.pool_id or p.obligor,
                market_value=abs(p.market_value),
                maturity_years=p.maturity_years,
                is_long=p.is_long,
                banking_book_risk_weight=p.banking_book_risk_weight,
            )
        if p.credit_sector == CreditSector.SOVEREIGN:
            et = DRCExposureType.NON_US_SOVEREIGN
        elif p.credit_sector == CreditSector.LOCAL_GOVERNMENT:
            et = DRCExposureType.PSE_GSE
        else:
            et = DRCExposureType.CORPORATE
        if p.is_defaulted:
            et = DRCExposureType.DEFAULTED
        return USDRCPosition(
            issuer=p.obligor,
            seniority=_DRC_SENIORITY[p.seniority],
            exposure_type=et,
            credit_quality=self._drc_quality(p),
            notional=p.notional,
            market_value=p.notional + p.pnl,
            maturity_years=p.maturity_years,
            is_long=p.is_long,
            is_us_sovereign_or_mdb=bool(p.flags.get("us_sovereign_or_mdb")),
        )

    def _run(
        self,
        sensitivities: list[FRTBSensitivity],
        drc: list[DRCPositionInput],
        rrao: list[RRAOPositionInput],
    ) -> FRTBResult:
        """Run the engine's FRTB calculator on translated inputs."""
        rr = [
            RRAOPosition(
                instrument_id=r.position_id,
                notional=r.gross_notional,
                category=USRRAOCategory.EXEMPT
                if r.exempt
                else (
                    USRRAOCategory.EXOTIC
                    if r.category == RRAOCategory.EXOTIC
                    else USRRAOCategory.OTHER
                ),
            )
            for r in rrao
        ]
        return self._calc.calculate(
            sensitivities=[self._to_us(s) for s in sensitivities],
            drc_positions=[self._to_us_drc(p) for p in drc],
            rrao_positions=rr,
        )

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM capital by risk class (§ __.206)."""
        return self._sbm_rows(self._run(sensitivities, [], []))

    @staticmethod
    def _sbm_rows(r: FRTBResult) -> list[SBMClassResult]:
        """SBM rows from an engine result."""
        spec = [
            (FRTBRiskClass.GIRR, "girr"),
            (FRTBRiskClass.CSR_NONSEC, "csr_nonsec"),
            (FRTBRiskClass.CSR_SEC_NONCTP, "csr_sec_nonctp"),
            (FRTBRiskClass.CSR_SEC_CTP, "csr_sec_ctp"),
            (FRTBRiskClass.EQUITY, "equity"),
            (FRTBRiskClass.COMMODITY, "commodity"),
            (FRTBRiskClass.FX, "fx"),
        ]
        return [
            SBMClassResult(
                risk_class=rc,
                delta=getattr(r, f"{k}_delta"),
                vega=getattr(r, f"{k}_vega"),
                curvature=getattr(r, f"{k}_curvature"),
                total=getattr(r, f"{k}_charge"),
            )
            for rc, k in spec
        ]

    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC components (§ __.210); no diversification across components."""
        r = self._run([], positions, [])
        return {
            "nonsec": r.drc_nonsec,
            "sec_nonctp": r.drc_sec_nonctp,
            "ctp": r.drc_sec_ctp,
            "total": r.drc_total,
        }

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """RRAO (§ __.211): 1.0% exotic, 0.1% other residual risk."""
        return self._run([], [], positions).rrao_total

    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """Total FRTB-SA capital = SBM + DRC + RRAO; RWA = 12.5 x capital."""
        r = self._run(sensitivities, drc_positions, rrao_positions)
        return MarketRiskResult(
            jurisdiction=self.jurisdiction,
            sbm_by_class=self._sbm_rows(r),
            sbm_total=r.sbm_total,
            drc_nonsec=r.drc_nonsec,
            drc_sec_nonctp=r.drc_sec_nonctp,
            drc_ctp=r.drc_sec_ctp,
            drc_total=r.drc_total,
            rrao=r.rrao_total,
            total_capital=r.total_capital_charge,
            rwa=r.total_capital_charge * RWA_PER_UNIT_CAPITAL,
            citations={
                "sbm": "ERBA NPR § __.206-__.209",
                "drc": "ERBA NPR § __.210",
                "rrao": "ERBA NPR § __.211",
            },
            notes=["curvature: adverse of CVR+/CVR- passed to the US engine (single-CVR model)"],
        )

    def ima_parameters(self) -> IMAParameters:
        """§ __.204, § __.212-__.215 IMA scalars."""
        return IMAParameters(
            jurisdiction=self.jurisdiction,
            es_confidence=US_ES_CONFIDENCE,
            liquidity_horizons_days=dict(US_LIQUIDITY_HORIZONS),
            multiplier_base=US_BACKTESTING_MULTIPLIER[0],
            backtesting_addons=dict(US_BACKTESTING_MULTIPLIER),
            imcc_rho=US_IMCC_OMEGA,
            ses_rho=US_SES_RHO,
            pla_spearman_thresholds=None,
            pla_ks_thresholds=US_PLA_KS_THRESHOLDS,
            citations={
                "multiplier": "ERBA NPR § __.204 Table 1",
                "lh": "§ __.215 Table 2",
                "imcc": "§ __.215 (omega 0.5)",
                "ses": "§ __.215 (rho_b 0.36)",
                "pla": "§ __.213 (KS only, 0.09 / 0.12)",
            },
        )


_DRC_SEC_BUCKET: Final[dict[SecAssetClass, DRCSecBucket]] = {
    SecAssetClass.RMBS_PRIME: DRCSecBucket.RMBS,
    SecAssetClass.RMBS_MIDPRIME: DRCSecBucket.RMBS,
    SecAssetClass.RMBS_SUBPRIME: DRCSecBucket.RMBS,
    SecAssetClass.CMBS: DRCSecBucket.CMBS,
    SecAssetClass.ABS_STUDENT_LOANS: DRCSecBucket.STUDENT_LOANS,
    SecAssetClass.ABS_CREDIT_CARDS: DRCSecBucket.CREDIT_CARDS,
    SecAssetClass.ABS_AUTO: DRCSecBucket.AUTO,
    SecAssetClass.CLO_NON_CTP: DRCSecBucket.CLO,
    SecAssetClass.OTHER: DRCSecBucket.CORPORATE,
}
"""Neutral asset classes -> § __.210(c)(3)(i) DRC securitisation buckets."""
