"""Common contract for the remaining Pillar 1 sections, per jurisdiction.

Covers:

- Securitisation (Basel Framework CRE40-CRE45): hierarchy, SEC-IRBA,
  SEC-ERBA, SEC-IAA, SEC-SA, STC/STS treatment, caps and floors.
- SA-CVA (MAR50.27-50.77): sensitivity-based CVA capital.
- Leverage-ratio exposure measure (LEV30).
- Large exposures (LEX10-LEX40).
- Exposures to central counterparties (CRE54).

Each jurisdiction implements the protocols it has legal text for and cites
its own provisions. Inputs are regime-neutral; amounts are in the regime's
reporting currency, millions.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from src.jurisdictions.base import AssetClass, Jurisdiction, RatingBucket

# =========================================================================
#  Securitisation
# =========================================================================


class SecApproachUsed(str, Enum):  # noqa: UP042 -- repo convention
    """Approach that produced a securitisation risk weight (CRE40.41-40.47)."""

    SEC_IRBA = "SEC_IRBA"
    SEC_ERBA = "SEC_ERBA"
    SEC_IAA = "SEC_IAA"
    SEC_SA = "SEC_SA"
    RW_1250 = "RW_1250"
    LOOK_THROUGH = "LOOK_THROUGH"


class SecTrancheInput(BaseModel):
    """A securitisation position (CRE40-CRE44)."""

    tranche_id: str
    exposure_amount: float = Field(ge=0.0, description="Exposure value after CCF")
    attachment: float = Field(ge=0.0, le=1.0, description="A (CRE40.15)")
    detachment: float = Field(ge=0.0, le=1.0, description="D (CRE40.16)")
    is_resecuritisation: bool = False
    is_stc: bool = False
    """Meets the regime's simple, transparent and comparable (STC/STS) criteria."""
    is_senior: bool = False
    is_synthetic: bool = False
    is_npl_securitisation: bool = False
    maturity_years: float = Field(
        default=1.0, ge=0.0, description="Tranche maturity M_T (CRE40.54)"
    )
    # Pool parameters
    k_sa: float | None = Field(
        default=None, ge=0.0, description="K_SA: SA capital of the pool (CRE44.2)"
    )
    w: float = Field(default=0.0, ge=0.0, le=1.0, description="Delinquent share W (CRE44.3)")
    k_irb: float | None = Field(
        default=None, ge=0.0, description="K_IRB where the bank may use SEC-IRBA"
    )
    n_effective: float | None = Field(
        default=None, gt=0.0, description="Effective number of exposures N"
    )
    lgd_pool: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Exposure-weighted LGD"
    )
    is_retail_pool: bool = False
    # Ratings (SEC-ERBA)
    external_rating: str | None = Field(
        default=None, description="Long-term notch, e.g. 'AA-' (CRE42 Table 1)"
    )
    short_term_rating: str | None = Field(
        default=None, description="e.g. 'A-1/P-1' (CRE42 Table 1)"
    )
    internal_assessment_rating: str | None = Field(default=None, description="IAA-equivalent notch")
    flags: dict[str, bool] = Field(default_factory=dict)


class SecResultRow(BaseModel):
    """Risk weight and RWA for one securitisation position."""

    tranche_id: str
    jurisdiction: Jurisdiction
    approach: SecApproachUsed
    risk_weight: float = Field(description="Decimal, e.g. 0.15")
    rwa: float
    citation: str
    notes: list[str] = Field(default_factory=list)


@runtime_checkable
class SecuritisationCalculator(Protocol):
    """Securitisation framework of a regime."""

    jurisdiction: Jurisdiction

    def securitisation(self, tranche: SecTrancheInput) -> SecResultRow:
        """Risk weight via the regime's hierarchy (with caps/floors)."""
        ...


# =========================================================================
#  SA-CVA
# =========================================================================


class CVARiskClass(str, Enum):  # noqa: UP042
    """SA-CVA risk classes (MAR50.45)."""

    INTEREST_RATE = "INTEREST_RATE"
    FX = "FX"
    COUNTERPARTY_CREDIT_SPREAD = "COUNTERPARTY_CREDIT_SPREAD"
    REFERENCE_CREDIT_SPREAD = "REFERENCE_CREDIT_SPREAD"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"


class CVASensitivityInput(BaseModel):
    """One SA-CVA sensitivity of aggregate CVA and of eligible hedges (MAR50.48)."""

    risk_class: CVARiskClass
    measure: str = Field(description="'DELTA' or 'VEGA'")
    bucket: str = Field(description="Regime bucket, e.g. currency, sector key, MAR50 bucket number")
    risk_factor: str = Field(description="Tenor / sector / index / commodity key within the bucket")
    s_cva: float = 0.0
    s_hedge: float = 0.0
    is_investment_grade: bool | None = None
    name: str = ""
    flags: dict[str, bool] = Field(default_factory=dict)


class SACVAResult(BaseModel):
    """SA-CVA capital under one regime."""

    jurisdiction: Jurisdiction
    k_by_class: dict[str, float] = Field(default_factory=dict)
    k_total: float = 0.0
    rwa: float = 0.0
    m_cva: float = 0.0
    r_hedging_disallowance: float = 0.0
    citations: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class SACVACalculator(Protocol):
    """SA-CVA of a regime."""

    jurisdiction: Jurisdiction

    def sa_cva(self, sensitivities: list[CVASensitivityInput]) -> SACVAResult:
        """K_SA-CVA = m_CVA x sum over risk classes (MAR50.53)."""
        ...


# =========================================================================
#  Leverage-ratio exposure measure
# =========================================================================


class LeverageInputs(BaseModel):
    """Inputs to the leverage-ratio exposure measure (LEV30)."""

    on_balance_sheet_assets: float = Field(ge=0.0, description="Excl. derivatives and SFTs")
    tier1_deductions: float = Field(default=0.0, ge=0.0, description="Assets deducted from Tier 1")
    derivative_rc: float = Field(
        default=0.0, ge=0.0, description="Replacement cost, unmargined/after VM rules"
    )
    derivative_pfe_addon: float = Field(default=0.0, ge=0.0, description="SA-CCR aggregate add-on")
    derivative_cash_vm_received: float = Field(default=0.0, ge=0.0)
    written_credit_derivative_notional: float = Field(default=0.0, ge=0.0)
    written_credit_derivative_offsets: float = Field(default=0.0, ge=0.0)
    sft_gross_assets: float = Field(default=0.0, ge=0.0)
    sft_netted_cash_payables: float = Field(default=0.0, ge=0.0)
    sft_ccr_addon: float = Field(default=0.0, ge=0.0)
    obs_notional_by_ccf: dict[float, float] = Field(
        default_factory=dict, description="SA CCF -> notional (LEV30.43-30.47 apply the CCF)"
    )
    central_bank_reserves: float = Field(
        default=0.0, ge=0.0, description="Excludable where permitted"
    )
    client_cleared_trade_exposures_exempt: float = Field(default=0.0, ge=0.0)
    flags: dict[str, bool] = Field(default_factory=dict)


class LeverageResult(BaseModel):
    """Exposure measure components and total."""

    jurisdiction: Jurisdiction
    on_balance_sheet: float
    derivatives: float
    sfts: float
    off_balance_sheet: float
    exclusions: float = 0.0
    total_exposure: float
    citations: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class LeverageCalculator(Protocol):
    """Leverage-ratio exposure measure of a regime."""

    jurisdiction: Jurisdiction

    def leverage_exposure(self, inputs: LeverageInputs) -> LeverageResult:
        """Total exposure measure."""
        ...


# =========================================================================
#  Large exposures
# =========================================================================


class LargeExposureInput(BaseModel):
    """Exposure to one counterparty or group of connected counterparties (LEX20-LEX30)."""

    counterparty_id: str
    exposure_value: float = Field(ge=0.0, description="After eligible CRM (LEX30)")
    counterparty_is_gsib: bool = False
    counterparty_asset_class: AssetClass = AssetClass.CORPORATE
    is_exempt: bool = False
    """Regime exemption (e.g. sovereigns, intraday interbank) as provided by the caller."""
    flags: dict[str, bool] = Field(default_factory=dict)


class LargeExposureRow(BaseModel):
    """Limit test for one counterparty."""

    counterparty_id: str
    exposure_value: float
    limit: float
    limit_pct_of_tier1: float
    reportable: bool
    breach: bool
    citation: str


@runtime_checkable
class LargeExposuresCalculator(Protocol):
    """Large-exposure limits of a regime."""

    jurisdiction: Jurisdiction

    def large_exposures(
        self,
        exposures: list[LargeExposureInput],
        tier1_capital: float,
        reporting_bank_is_gsib: bool,
    ) -> list[LargeExposureRow]:
        """Reporting threshold and limit test for each counterparty."""
        ...


# =========================================================================
#  CCP exposures
# =========================================================================


class CCPExposureInput(BaseModel):
    """Exposure to a central counterparty (CRE54)."""

    ccp_id: str
    is_qualifying: bool = True
    trade_exposure: float = Field(ge=0.0)
    is_client_cleared_via_member: bool = False
    initial_margin_bankruptcy_remote: bool = False
    default_fund_contribution: float = Field(default=0.0, ge=0.0)
    k_ccp: float | None = Field(
        default=None, ge=0.0, description="Hypothetical capital of the CCP (CRE54.31)"
    )
    total_default_fund: float | None = Field(default=None, ge=0.0, description="DF_CCP + DF_CM")
    ccp_rating: RatingBucket = RatingBucket.UNRATED
    flags: dict[str, bool] = Field(default_factory=dict)


class CCPResult(BaseModel):
    """RWA on trade exposures and default-fund contributions."""

    ccp_id: str
    jurisdiction: Jurisdiction
    trade_rw: float
    trade_rwa: float
    default_fund_rwa: float
    total_rwa: float
    citation: str


@runtime_checkable
class CCPCalculator(Protocol):
    """CCP exposure treatment of a regime."""

    jurisdiction: Jurisdiction

    def ccp_exposure(self, exposure: CCPExposureInput) -> CCPResult:
        """Trade-exposure and default-fund RWA."""
        ...
