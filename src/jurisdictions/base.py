"""Common contract for the multi-jurisdiction Basel III capital engines.

Every jurisdiction package under ``src/jurisdictions/`` (BCBS baseline, US
ERBA NPR, UK PRA PS1/26, EU CRR3, Singapore MAS Notice 637, Canada OSFI CAR
2026) implements :class:`RegimeCalculator` against the jurisdiction-neutral
input models defined here, so that one portfolio can be run through every
regime and the results compared line by line.

The models below carry the *union* of the attributes any regime needs to
assign a standardised-approach risk weight (external ratings are ignored by
the US regime, LTV is ignored for unsecured corporates, and so on). Each
regime documents which fields it reads, and every number it returns cites
the paragraph, article or section of that regime's legal text that
produced it.

References:
    - Basel Framework (BIS consolidated, CRE20-CRE22, CRE52, MAR50, OPE25,
      RBC20, LEV30, RBC30-RBC40)
    - Basel III: Finalising post-crisis reforms (BCBS d424, Dec 2017)

All monetary amounts in USD millions ($M) unless explicitly stated otherwise
(regimes reporting in GBP/EUR/SGD/CAD take inputs already converted; the
engine is currency-agnostic).
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

# =========================================================================
#  Jurisdictions
# =========================================================================

class Jurisdiction(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Supported regulatory regimes."""

    BCBS = "BCBS"
    """Basel Committee international standard (Basel Framework)."""
    US = "US"
    """United States -- March 2026 ERBA NPR (OCC NR 2026-16a)."""
    UK = "UK"
    """United Kingdom -- PRA PS1/26, PRA Rulebook CRR Firms (CRR) Instrument 2026."""
    EU = "EU"
    """European Union -- CRR3, Regulation (EU) 2024/1623 amending Regulation (EU) No 575/2013."""
    SG = "SG"
    """Singapore -- MAS Notice 637 (version effective 1 January 2026)."""
    CA = "CA"
    """Canada -- OSFI Capital Adequacy Requirements (CAR) Guideline 2026."""


# =========================================================================
#  Jurisdiction-neutral exposure taxonomy
# =========================================================================

class AssetClass(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Standardised-approach exposure classes (union across regimes).

    Mapped to CRE20 sections in the Basel Framework; each regime maps these
    to its own exposure classes (e.g. CRR Article 112, MAS Notice 637
    Part VII Division 3, OSFI CAR Chapter 4).
    """

    SOVEREIGN = "SOVEREIGN"                      # CRE20.7-20.11
    PSE = "PSE"                                  # CRE20.11-20.12
    MDB = "MDB"                                  # CRE20.13-20.15
    # CRE20.16-20.21 (incl. securities firms treated as banks)
    BANK = "BANK"
    COVERED_BOND = "COVERED_BOND"                # CRE20.33-20.39
    CORPORATE = "CORPORATE"                      # CRE20.42-20.43 (general corporate)
    CORPORATE_SME = "CORPORATE_SME"              # CRE20.47 (SME corporate)
    SPECIALISED_LENDING_PF = "SPECIALISED_LENDING_PF"   # CRE20.48-20.52 project finance
    SPECIALISED_LENDING_OF = "SPECIALISED_LENDING_OF"   # object finance
    SPECIALISED_LENDING_CF = "SPECIALISED_LENDING_CF"   # commodities finance
    # CRE20.53 (and capital instruments other than equity)
    SUBORDINATED_DEBT = "SUBORDINATED_DEBT"
    EQUITY = "EQUITY"                            # CRE20.53-20.62
    # CRE20.65-20.66 (regulatory retail, non-transactor)
    RETAIL_REGULATORY = "RETAIL_REGULATORY"
    RETAIL_TRANSACTOR = "RETAIL_TRANSACTOR"      # CRE20.66 footnote (transactors)
    RETAIL_OTHER = "RETAIL_OTHER"                # CRE20.67 (other retail)
    RESIDENTIAL_RE = "RESIDENTIAL_RE"            # CRE20.71-20.85 residential real estate
    COMMERCIAL_RE = "COMMERCIAL_RE"              # CRE20.86-20.89 commercial real estate
    # CRE20.90-20.91 land acquisition, development, construction
    LAND_ADC = "LAND_ADC"
    DEFAULTED = "DEFAULTED"                      # CRE20.104-20.108
    OTHER_ASSETS = "OTHER_ASSETS"                # CRE20.109-20.110 (cash, gold, other)


class RatingBucket(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Long-term external credit assessment buckets (CRE20 rating tables).

    The Basel Framework tables use S&P-style notation; CRR "credit quality
    steps" 1-6 map one-to-one onto the six rated buckets
    (CQS1 = AAA..AA-, ..., CQS6 = below B-).
    """

    AAA_TO_AA_MINUS = "AAA_TO_AA-"
    A_PLUS_TO_A_MINUS = "A+_TO_A-"
    BBB_PLUS_TO_BBB_MINUS = "BBB+_TO_BBB-"
    BB_PLUS_TO_BB_MINUS = "BB+_TO_BB-"
    B_PLUS_TO_B_MINUS = "B+_TO_B-"
    BELOW_B_MINUS = "BELOW_B-"
    UNRATED = "UNRATED"


class ShortTermRating(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Short-term external credit assessments (CRE20.22 / CRE20.44 tables)."""

    A1_P1 = "A-1/P-1"
    A2_P2 = "A-2/P-2"
    A3_P3 = "A-3/P-3"
    OTHERS = "OTHERS"


class SCRAGrade(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Standardised Credit Risk Assessment Approach grades (CRE20.18-20.21)."""

    A = "A"
    B = "B"
    C = "C"


class RealEstateTreatment(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """How a regime applies risk weights to real-estate exposures."""

    WHOLE_LOAN = "WHOLE_LOAN"          # CRE20.82 / CRE20.86(1)
    LOAN_SPLITTING = "LOAN_SPLITTING"  # CRE20.83 / CRE20.86(2) (national discretion)


class PFPhase(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Project finance phase (CRE20.52)."""

    PRE_OPERATIONAL = "PRE_OPERATIONAL"
    OPERATIONAL = "OPERATIONAL"
    HIGH_QUALITY_OPERATIONAL = "HIGH_QUALITY_OPERATIONAL"


class EquityType(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Equity holding categories (CRE20.55-20.61)."""

    GENERAL = "GENERAL"                          # 250% (CRE20.57)
    SPECULATIVE_UNLISTED = "SPECULATIVE_UNLISTED"  # 400% (CRE20.58)
    LEGISLATIVE_PROGRAMME = "LEGISLATIVE_PROGRAMME"  # 100% national discretion (CRE20.59)
    PUBLICLY_TRADED = "PUBLICLY_TRADED"          # US-specific bucket
    NON_PUBLIC = "NON_PUBLIC"                    # US-specific bucket
    SIGNIFICANT_FI = "SIGNIFICANT_FI"            # 250% threshold-deduction RW (CAP30.32 etc.)


class OBSCategory(str, Enum):  # noqa: UP042 -- repo convention (str-valued enums)
    """Off-balance-sheet credit-conversion-factor categories (CRE20.94-20.101)."""

    UNCONDITIONALLY_CANCELLABLE = "UNCONDITIONALLY_CANCELLABLE"   # CRE20.95 (10%)
    COMMITMENT_OTHER = "COMMITMENT_OTHER"                         # CRE20.94 (40%)
    NIF_RUF = "NIF_RUF"                                           # CRE20.96 (50%)
    TRANSACTION_RELATED_CONTINGENT = "TRANSACTION_RELATED_CONTINGENT"  # CRE20.97 (50%)
    SHORT_TERM_TRADE_LC = "SHORT_TERM_TRADE_LC"                   # CRE20.98 (20%)
    DIRECT_CREDIT_SUBSTITUTE = "DIRECT_CREDIT_SUBSTITUTE"         # CRE20.99 (100%)
    SECURITIES_LENDING_COLLATERAL = "SECURITIES_LENDING_COLLATERAL"  # CRE20.100 (100%)
    FORWARD_ASSET_PURCHASE = "FORWARD_ASSET_PURCHASE"             # CRE20.101 (100%)
    OTHER_100 = "OTHER_100"                                       # residual 100%


class SAExposure(BaseModel):
    """A standardised-approach credit exposure, jurisdiction-neutral.

    ``on_balance_amount`` is the drawn/carrying amount net of specific
    provisions; ``off_balance_notional`` is the undrawn or contingent amount
    to which the regime's CCF for ``obs_category`` applies.
    """

    exposure_id: str
    asset_class: AssetClass
    counterparty: str = ""
    on_balance_amount: float = Field(
        default=0.0, ge=0.0, description="$M, net of specific provisions"
    )
    off_balance_notional: float = Field(default=0.0, ge=0.0, description="$M undrawn / contingent")
    obs_category: OBSCategory | None = None
    commitment_original_maturity_years: float | None = None
    residual_maturity_years: float | None = None
    original_maturity_months: float | None = None
    currency_matches_borrower_income: bool = True
    domestic_currency_funded: bool = False
    """Exposure denominated and funded in the sovereign's/bank's domestic currency."""

    # Ratings-based inputs (ignored by the US regime -- Dodd-Frank s.939A)
    rating: RatingBucket = RatingBucket.UNRATED
    short_term_rating: ShortTermRating | None = None
    sovereign_rating: RatingBucket = RatingBucket.UNRATED
    """Rating of the sovereign of incorporation (PSE option 1, bank floors)."""
    oecd_crc: int | None = Field(
        default=None, ge=0, le=7, description="Country risk classification"
    )
    scra_grade: SCRAGrade | None = None
    scra_grade_a_enhanced: bool = False
    """Bank meets CET1 >= 14% and leverage >= 5% (CRE20.21 30% treatment)."""
    is_trade_related: bool = False
    is_investment_grade: bool | None = None
    """Bank-assessed investment grade (unrated corporates where the regime permits)."""

    # Corporate / SME
    is_sme: bool = False
    annual_turnover: float | None = Field(default=None, description="Consolidated group sales, $M")
    pf_phase: PFPhase | None = None

    # Retail
    is_transactor: bool = False
    meets_regulatory_retail_criteria: bool = True
    aggregate_retail_exposure_to_obligor: float | None = None

    # Real estate
    ltv: float | None = Field(default=None, ge=0.0, description="Loan-to-value (0.75 = 75%)")
    property_value: float | None = Field(default=None, ge=0.0)
    is_regulatory_real_estate: bool = True
    """Meets the CRE20.71 criteria (finished property, legal enforceability, valuation, etc.)."""
    is_cash_flow_dependent: bool = False
    """Repayment materially dependent on cash flows generated by the property (CRE20.79)."""
    is_owner_occupied: bool = True
    is_adc_presold_or_equity_at_risk: bool = False
    """ADC residential with pre-sales/equity at risk (CRE20.91 100%)."""

    # Equity
    equity_type: EquityType | None = None

    # Defaults
    is_defaulted: bool = False
    specific_provision_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    """Specific provisions as share of outstanding (CRE20.103 20% test)."""

    # Covered bonds
    covered_bond_rated: bool = False

    # Credit risk mitigation
    financial_collateral_value: float = Field(default=0.0, ge=0.0)
    collateral_haircut_class: str | None = None
    """Regime-specific supervisory-haircut key (e.g. 'SOVEREIGN_AAA_1Y', 'MAIN_INDEX_EQUITY')."""
    guarantee_amount: float = Field(default=0.0, ge=0.0)
    guarantor_asset_class: AssetClass | None = None
    guarantor_rating: RatingBucket = RatingBucket.UNRATED

    # Free-form regime-specific flags (documented by each regime)
    flags: dict[str, bool] = Field(default_factory=dict)


# =========================================================================
#  Results
# =========================================================================

class RiskWeightResult(BaseModel):
    """Risk-weight assignment for one exposure under one regime."""

    exposure_id: str
    jurisdiction: Jurisdiction
    regime_exposure_class: str
    risk_weight: float = Field(description="Decimal, e.g. 0.65 = 65%")
    ccf: float = Field(default=0.0, description="CCF applied to the off-balance notional")
    exposure_amount: float = Field(description="On-balance + CCF x off-balance, after CRM ($M)")
    rwa: float
    citation: str = Field(description="Paragraph / article / section producing the risk weight")
    notes: list[str] = Field(default_factory=list)


class CreditRWAResult(BaseModel):
    """Aggregate SA credit RWA under one regime."""

    jurisdiction: Jurisdiction
    total_exposure: float
    total_rwa: float
    rwa_by_class: dict[str, float] = Field(default_factory=dict)
    exposure_by_class: dict[str, float] = Field(default_factory=dict)
    line_items: list[RiskWeightResult] = Field(default_factory=list)

    @property
    def density(self) -> float:
        """RWA density = RWA / exposure."""
        return self.total_rwa / self.total_exposure if self.total_exposure else 0.0


class OpRiskInputs(BaseModel):
    """Business-indicator inputs, three-year averages (OPE10 / OPE25.4-25.8).

    Each list holds the three annual observations, oldest first. Regimes
    with non-BCBS BI definitions (US two-component BI) document how they map
    these fields.
    """

    interest_income: list[float] = Field(min_length=3, max_length=3)
    interest_expense: list[float] = Field(min_length=3, max_length=3)
    interest_earning_assets: list[float] = Field(min_length=3, max_length=3)
    dividend_income: list[float] = Field(min_length=3, max_length=3)
    fee_income: list[float] = Field(min_length=3, max_length=3)
    fee_expense: list[float] = Field(min_length=3, max_length=3)
    other_operating_income: list[float] = Field(min_length=3, max_length=3)
    other_operating_expense: list[float] = Field(min_length=3, max_length=3)
    net_pnl_trading_book: list[float] = Field(min_length=3, max_length=3)
    net_pnl_banking_book: list[float] = Field(min_length=3, max_length=3)
    annual_operational_losses: list[float] = Field(
        default_factory=list, description="Up to 10 years of net losses, oldest first ($M)"
    )


class OpRiskResult(BaseModel):
    """Operational-risk capital under one regime."""

    jurisdiction: Jurisdiction
    business_indicator: float
    bic: float
    loss_component: float | None = None
    ilm: float
    capital: float
    rwa: float
    citation: str
    components: dict[str, float] = Field(default_factory=dict)


class OutputFloorResult(BaseModel):
    """Output-floor outcome (RBC20.11 and national transitions)."""

    jurisdiction: Jurisdiction
    applies: bool
    floor_factor: float
    pre_floor_rwa: float
    standardised_rwa: float
    floored_rwa: float
    add_on: float
    citation: str
    notes: list[str] = Field(default_factory=list)


class CapitalRequirements(BaseModel):
    """Minimum ratios and buffers under one regime (decimals)."""

    jurisdiction: Jurisdiction
    cet1_minimum: float
    tier1_minimum: float
    total_capital_minimum: float
    conservation_buffer: float
    countercyclical_buffer: float
    systemic_buffer: float
    """G-SIB / G-SII / O-SII / D-SIB buffer applied (the higher where they do not stack)."""
    systemic_risk_buffer: float = 0.0
    stress_buffer: float = 0.0
    """US SCB / OSFI DSB / PRA buffer where it forms part of the combined buffer."""
    leverage_minimum: float
    leverage_buffer: float = 0.0
    citations: dict[str, str] = Field(default_factory=dict)

    @property
    def combined_buffer(self) -> float:
        """Combined buffer requirement on top of the CET1 minimum."""
        return (self.conservation_buffer + self.countercyclical_buffer + self.systemic_buffer
                + self.systemic_risk_buffer + self.stress_buffer)

    @property
    def cet1_requirement(self) -> float:
        """CET1 minimum plus the combined buffer."""
        return self.cet1_minimum + self.combined_buffer


class SACCRNettingSetInput(BaseModel):
    """Netting-set inputs for a regime's SA-CCR (CRE52)."""

    netting_set_id: str
    replacement_cost: float = Field(description="RC per CRE52.10-52.20 ($M)")
    aggregate_addon: float = Field(description="AddOn_aggregate per CRE52.24 ($M)")
    mtm: float = 0.0
    net_collateral: float = 0.0
    is_margined: bool = False
    counterparty_is_nonfinancial: bool = False
    counterparty_is_pension_scheme: bool = False
    flags: dict[str, bool] = Field(default_factory=dict)


class SACCRResult(BaseModel):
    """SA-CCR exposure at default for one netting set."""

    jurisdiction: Jurisdiction
    netting_set_id: str
    alpha: float
    multiplier: float
    pfe: float
    ead: float
    citation: str


# =========================================================================
#  Regime protocol
# =========================================================================

@runtime_checkable
class RegimeCalculator(Protocol):
    """Interface every jurisdiction implements."""

    jurisdiction: Jurisdiction
    regime_name: str
    legal_basis: str

    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CCF and RWA for one exposure."""
        ...

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """SA credit RWA for a portfolio."""
        ...

    def ccf(self, exposure: SAExposure) -> float:
        """Credit conversion factor for the off-balance part of an exposure."""
        ...

    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """Operational-risk capital and RWA."""
        ...

    def output_floor(
        self, pre_floor_rwa: float, standardised_rwa: float, year: int
    ) -> OutputFloorResult:
        """Apply the regime's output floor (if any) for a reporting year."""
        ...

    def capital_requirements(
        self,
        systemic_bucket_or_rate: float = 0.0,
        countercyclical_rate: float = 0.0,
        stress_buffer: float = 0.0,
    ) -> CapitalRequirements:
        """Minimum ratios and buffer stack."""
        ...

    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """SA-CCR EAD for a netting set (alpha, multiplier, PFE)."""
        ...

    def ba_cva_capital(
        self,
        counterparties: list[dict[str, float | str | bool]],
        hedged: bool = False,
    ) -> dict[str, float]:
        """Reduced/full BA-CVA capital (MAR50.12-50.24 or national equivalent).

        Each counterparty dict holds ``ead`` ($M), ``maturity`` (years),
        ``sector`` (regime sector key) and ``credit_quality``
        ("IG"/"HY_NR" or regime equivalent). Returns at least ``k_reduced``,
        ``k`` and ``rwa``.
        """
        ...


def rating_bucket_from_cqs(cqs: int) -> RatingBucket:
    """Map a CRR credit quality step (1-6) to a :class:`RatingBucket`.

    Reference: CRR Article 136 / Commission Implementing Regulation (EU)
    2016/1799 mapping tables (CQS1 = AAA..AA-, ..., CQS6 = CCC+ and below).
    """
    mapping = {
        1: RatingBucket.AAA_TO_AA_MINUS,
        2: RatingBucket.A_PLUS_TO_A_MINUS,
        3: RatingBucket.BBB_PLUS_TO_BBB_MINUS,
        4: RatingBucket.BB_PLUS_TO_BB_MINUS,
        5: RatingBucket.B_PLUS_TO_B_MINUS,
        6: RatingBucket.BELOW_B_MINUS,
    }
    if cqs not in mapping:
        raise ValueError(f"credit quality step must be 1-6, got {cqs}")
    return mapping[cqs]
