"""Common contract for per-jurisdiction market risk (FRTB) calculations.

Every jurisdiction package implements :class:`MarketRiskCalculator` against
the jurisdiction-neutral inputs below. Sensitivities carry *descriptors*
(currency, tenor, issuer sector, credit quality, market capitalisation,
commodity group, ...) rather than a bucket number, because bucket taxonomies
differ by regime (e.g. the US ERBA NPR has 20 CSR non-securitisation buckets
by IG / speculative / sub-speculative; MAR21 has 18). Each regime assigns
its own bucket, risk weight and correlations from the descriptors, citing its
own text. ``bucket_hint`` lets a caller pin a MAR21-numbered bucket where the
descriptors are not enough; a regime may ignore it.

Units: delta sensitivities are s_k as defined in MAR21.8-21.25 (PV01 / 0.0001
for rates and spreads; P&L of a 1% relative move / 0.01 for equity,
commodity and FX); vega sensitivities are vega x implied volatility
(MAR21.25); curvature inputs are CVR+ and CVR- (MAR21.5). All amounts in the
regime's reporting currency millions; the comparison layer converts.

References: Basel Framework MAR20-MAR23 (standardised approach), MAR33 (IMA),
MAR40 (simplified standardised approach).
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from src.jurisdictions.base import Jurisdiction, RatingBucket


class FRTBRiskClass(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """SBM risk classes (MAR21.1)."""

    GIRR = "GIRR"
    CSR_NONSEC = "CSR_NONSEC"
    CSR_SEC_NONCTP = "CSR_SEC_NONCTP"
    CSR_SEC_CTP = "CSR_SEC_CTP"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FX = "FX"


class FRTBMeasure(str, Enum):  # noqa: UP042
    """Risk measures (MAR21.3)."""

    DELTA = "DELTA"
    VEGA = "VEGA"
    CURVATURE = "CURVATURE"


class GIRRCurve(str, Enum):  # noqa: UP042
    """GIRR risk-factor type (MAR21.8)."""

    RISK_FREE = "RISK_FREE"
    INFLATION = "INFLATION"
    XCCY_BASIS = "XCCY_BASIS"


class CreditSector(str, Enum):  # noqa: UP042
    """Issuer sector descriptor for CSR non-securitisation and DRC.

    The groupings follow the MAR21.51 Table 3 bucket descriptions; regimes
    map them to their own buckets.
    """

    SOVEREIGN = "SOVEREIGN"  # sovereigns incl. central banks, MDBs
    LOCAL_GOVERNMENT = (
        "LOCAL_GOVERNMENT"  # local govt, govt-backed non-financials, education, public admin
    )
    FINANCIAL = "FINANCIAL"  # financials incl. government-backed financials
    # basic materials, energy, industrials, agriculture, manufacturing, mining
    BASIC_MATERIALS = "BASIC_MATERIALS"
    CONSUMER = "CONSUMER"  # consumer goods/services, transportation, admin & support
    TECHNOLOGY = "TECHNOLOGY"  # technology, telecommunications
    HEALTH_CARE = "HEALTH_CARE"  # health care, utilities, professional & technical
    COVERED_BOND = "COVERED_BOND"
    OTHER = "OTHER"
    INDEX = "INDEX"  # qualified credit index


class SecTrancheClass(str, Enum):  # noqa: UP042
    """CSR securitisation (non-CTP) tranche class (MAR21.61)."""

    SENIOR_IG = "SENIOR_IG"
    NON_SENIOR_IG = "NON_SENIOR_IG"
    HY_NR = "HY_NR"


class SecAssetClass(str, Enum):  # noqa: UP042
    """Underlying asset class for CSR securitisation buckets (MAR21.61 Table 6)."""

    RMBS_PRIME = "RMBS_PRIME"
    RMBS_MIDPRIME = "RMBS_MIDPRIME"
    RMBS_SUBPRIME = "RMBS_SUBPRIME"
    CMBS = "CMBS"
    ABS_STUDENT_LOANS = "ABS_STUDENT_LOANS"
    ABS_CREDIT_CARDS = "ABS_CREDIT_CARDS"
    ABS_AUTO = "ABS_AUTO"
    CLO_NON_CTP = "CLO_NON_CTP"
    OTHER = "OTHER"


class EquitySector(str, Enum):  # noqa: UP042
    """Equity sector descriptor (MAR21.72 Table 8 sector groupings)."""

    CONSUMER_HEALTH_UTILITIES = "CONSUMER_HEALTH_UTILITIES"
    TELECOM_INDUSTRIALS = "TELECOM_INDUSTRIALS"
    MATERIALS_ENERGY = "MATERIALS_ENERGY"
    FINANCIALS_REALESTATE_TECH = "FINANCIALS_REALESTATE_TECH"
    OTHER = "OTHER"


class EquityRiskFactor(str, Enum):  # noqa: UP042
    """Equity delta risk factors (MAR21.13)."""

    SPOT = "SPOT"
    REPO = "REPO"


class CommodityGroup(str, Enum):  # noqa: UP042
    """Commodity bucket descriptor (MAR21.82 Table 9)."""

    ENERGY_SOLID = "ENERGY_SOLID"
    ENERGY_LIQUID = "ENERGY_LIQUID"
    ENERGY_ELECTRICITY_CARBON = "ENERGY_ELECTRICITY_CARBON"
    FREIGHT = "FREIGHT"
    METALS_NON_PRECIOUS = "METALS_NON_PRECIOUS"
    GASEOUS_ENERGY = "GASEOUS_ENERGY"
    PRECIOUS_METALS = "PRECIOUS_METALS"
    GRAINS_OILSEED = "GRAINS_OILSEED"
    LIVESTOCK_DAIRY = "LIVESTOCK_DAIRY"
    SOFTS_OTHER_AGRI = "SOFTS_OTHER_AGRI"
    OTHER = "OTHER"


class FRTBSensitivity(BaseModel):
    """One SBM sensitivity, described in regime-neutral terms."""

    risk_class: FRTBRiskClass
    measure: FRTBMeasure
    value: float = Field(default=0.0, description="s_k (delta) or vega sensitivity")
    cvr_up: float | None = Field(default=None, description="CVR+ for curvature (MAR21.5)")
    cvr_down: float | None = Field(default=None, description="CVR- for curvature (MAR21.5)")
    bucket_hint: str | None = Field(default=None, description="MAR21-numbered bucket, optional")
    label: str = Field(default="", description="Name / curve / issuer key for same-name tests")

    # GIRR
    currency: str | None = None
    tenor_years: float | None = None
    girr_curve: GIRRCurve = GIRRCurve.RISK_FREE
    curve_name: str = ""
    """Distinct risk-free curve identifier within a currency (MAR21.46 correlation)."""

    # Vega
    option_maturity_years: float | None = None
    underlying_maturity_years: float | None = None

    # Credit (CSR non-sec, CTP, sec non-CTP)
    issuer: str = ""
    rating: RatingBucket = RatingBucket.UNRATED
    is_investment_grade: bool | None = None
    credit_sector: CreditSector | None = None
    is_cds: bool = False
    """Basis risk factor: CDS curve vs bond curve (MAR21.54)."""
    sec_tranche_class: SecTrancheClass | None = None
    sec_asset_class: SecAssetClass | None = None
    tranche_id: str = ""

    # Equity
    is_large_cap: bool | None = None
    is_advanced_economy: bool | None = None
    equity_sector: EquitySector | None = None
    is_equity_index: bool = False
    equity_risk_factor: EquityRiskFactor = EquityRiskFactor.SPOT

    # Commodity
    commodity_group: CommodityGroup | None = None
    commodity_name: str = ""
    delivery_location: str = ""

    # FX
    fx_currency: str | None = None
    """Currency of the FX risk factor against the reporting currency."""
    fx_pair_is_liquid: bool | None = None
    """Specified-pair / most-liquid-pair status where the regime divides the RW by sqrt(2)."""

    flags: dict[str, bool] = Field(default_factory=dict)


class DRCSeniority(str, Enum):  # noqa: UP042
    """Seniority for DRC LGD (MAR22.12)."""

    COVERED_BOND = "COVERED_BOND"
    SENIOR = "SENIOR"
    NON_SENIOR = "NON_SENIOR"
    EQUITY = "EQUITY"


class DRCKind(str, Enum):  # noqa: UP042
    """DRC component (MAR22.2)."""

    NON_SECURITISATION = "NON_SECURITISATION"
    SEC_NON_CTP = "SEC_NON_CTP"
    CTP = "CTP"


class DRCPositionInput(BaseModel):
    """A default-risk position (MAR22)."""

    position_id: str
    kind: DRCKind = DRCKind.NON_SECURITISATION
    obligor: str
    is_long: bool
    notional: float = Field(ge=0.0)
    market_value: float = Field(description="Current market value of the position")
    pnl: float = Field(default=0.0, description="Cumulative P&L already realised on the position")
    maturity_years: float = Field(default=1.0, ge=0.0)
    seniority: DRCSeniority = DRCSeniority.SENIOR
    rating: RatingBucket = RatingBucket.UNRATED
    is_investment_grade: bool | None = None
    is_defaulted: bool = False
    credit_sector: CreditSector = CreditSector.OTHER
    """Bucket driver: SOVEREIGN / LOCAL_GOVERNMENT / other -> corporates (MAR22.21)."""
    # Securitisation DRC
    tranche_id: str = ""
    pool_id: str = ""
    sec_asset_class: SecAssetClass | None = None
    region: str = ""
    banking_book_risk_weight: float | None = Field(
        default=None,
        description="Securitisation RW from the regime's banking-book framework (decimal)",
    )
    flags: dict[str, bool] = Field(default_factory=dict)


class RRAOCategory(str, Enum):  # noqa: UP042
    """RRAO categories (MAR23.8)."""

    EXOTIC = "EXOTIC"
    OTHER_RESIDUAL = "OTHER_RESIDUAL"


class RRAOPositionInput(BaseModel):
    """A residual-risk position (MAR23)."""

    position_id: str
    gross_notional: float = Field(ge=0.0)
    category: RRAOCategory
    exempt: bool = False
    """Exempted per the regime's exclusions (e.g. MAR23.5 listed / CCP-eligible, back-to-back)."""
    flags: dict[str, bool] = Field(default_factory=dict)


class SBMClassResult(BaseModel):
    """SBM capital for one risk class."""

    risk_class: FRTBRiskClass
    delta: float = 0.0
    vega: float = 0.0
    curvature: float = 0.0
    total: float = 0.0
    scenario: str = Field(default="", description="Binding correlation scenario (LOW/MEDIUM/HIGH)")


class MarketRiskResult(BaseModel):
    """FRTB standardised-approach capital under one regime (regime currency, millions)."""

    jurisdiction: Jurisdiction
    sbm_by_class: list[SBMClassResult] = Field(default_factory=list)
    sbm_total: float = 0.0
    binding_scenario: str = ""
    drc_nonsec: float = 0.0
    drc_sec_nonctp: float = 0.0
    drc_ctp: float = 0.0
    drc_total: float = 0.0
    rrao: float = 0.0
    total_capital: float = 0.0
    rwa: float = 0.0
    citations: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class IMAParameters(BaseModel):
    """Internal-models scalars of a regime (MAR33), for reference and the MR2 template."""

    jurisdiction: Jurisdiction
    es_confidence: float
    liquidity_horizons_days: dict[str, int] = Field(default_factory=dict)
    multiplier_base: float
    backtesting_addons: dict[int, float] = Field(default_factory=dict)
    """Exceptions -> plus factor (MAR32 Table 1)."""
    imcc_rho: float
    ses_rho: float | None = None
    pla_spearman_thresholds: tuple[float, float] | None = None
    pla_ks_thresholds: tuple[float, float] | None = None
    citations: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class MarketRiskCalculator(Protocol):
    """Market-risk interface every jurisdiction implements."""

    jurisdiction: Jurisdiction

    def assign_bucket(self, s: FRTBSensitivity) -> str:
        """Regime bucket for a sensitivity."""
        ...

    def sbm_capital(self, sensitivities: list[FRTBSensitivity]) -> list[SBMClassResult]:
        """SBM capital by risk class under the binding correlation scenario.

        The binding scenario is the one with the largest SBM total across all
        risk classes (MAR21.7; ERBA NPR § __.206); per-class maxima would
        overstate capital.
        """
        ...

    def drc_capital(self, positions: list[DRCPositionInput]) -> dict[str, float]:
        """DRC by component: keys ``nonsec``, ``sec_nonctp``, ``ctp``, ``total``."""
        ...

    def rrao_capital(self, positions: list[RRAOPositionInput]) -> float:
        """Residual risk add-on."""
        ...

    def market_risk(
        self,
        sensitivities: list[FRTBSensitivity],
        drc_positions: list[DRCPositionInput],
        rrao_positions: list[RRAOPositionInput],
    ) -> MarketRiskResult:
        """Total FRTB-SA capital and RWA (= 12.5 x capital)."""
        ...

    def ima_parameters(self) -> IMAParameters:
        """The regime's IMA scalars."""
        ...
