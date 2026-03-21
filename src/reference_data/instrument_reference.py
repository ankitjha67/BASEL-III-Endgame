"""Instrument reference data for Basel III Endgame engine.

Provides instrument classification, product taxonomy, and trading/banking book
assignment for FRTB, SA-CR, and SA-CCR calculations.

Key regulatory references:
- BCBS d457: Minimum capital requirements for market risk (Jan 2019)
- ERBA NPR pp. 300-310: Trading book / banking book boundary
- 12 CFR 217.202: Scope of market risk capital rule
- ERBA NPR pp. 50-60: FRTB threshold and scope

All monetary amounts in USD millions ($M) unless explicitly stated otherwise.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
#  Enums
# =============================================================================

class InstrumentType(Enum):
    """Instrument type classification for regulatory capital treatment.

    Per ERBA NPR pp. 300-310 and 12 CFR 217.202.
    Determines which capital framework applies (SA-CR vs FRTB vs SA-CCR).
    """
    # Credit instruments (banking book)
    LOAN = "LOAN"
    REVOLVING_CREDIT = "REVOLVING_CREDIT"
    LETTER_OF_CREDIT = "LETTER_OF_CREDIT"
    TRADE_FINANCE = "TRADE_FINANCE"

    # Securities
    BOND = "BOND"
    SOVEREIGN_BOND = "SOVEREIGN_BOND"
    COVERED_BOND = "COVERED_BOND"
    EQUITY = "EQUITY"

    # Derivatives
    IRS = "IRS"                           # Interest Rate Swap
    CCS = "CCS"                           # Cross-Currency Swap
    FX_FORWARD = "FX_FORWARD"
    FX_OPTION = "FX_OPTION"
    EQUITY_OPTION = "EQUITY_OPTION"
    CDS = "CDS"                           # Credit Default Swap
    CDX_INDEX = "CDX_INDEX"               # Credit Index
    COMMODITY_FORWARD = "COMMODITY_FORWARD"
    COMMODITY_OPTION = "COMMODITY_OPTION"
    SWAPTION = "SWAPTION"
    CAP_FLOOR = "CAP_FLOOR"

    # Securities Financing Transactions (SFTs)
    REPO = "REPO"
    REVERSE_REPO = "REVERSE_REPO"
    SECURITIES_LENDING = "SECURITIES_LENDING"
    SECURITIES_BORROWING = "SECURITIES_BORROWING"
    MARGIN_LOAN = "MARGIN_LOAN"

    # Securitization
    RMBS = "RMBS"
    CMBS = "CMBS"
    CLO = "CLO"
    ABS = "ABS"
    RESECURITIZATION = "RESECURITIZATION"

    # Other
    STRUCTURED_NOTE = "STRUCTURED_NOTE"
    CONVERTIBLE_BOND = "CONVERTIBLE_BOND"
    OTHER = "OTHER"


class BookClassification(Enum):
    """Trading book vs banking book assignment.

    Per BCBS d457 Chapter 1 and ERBA NPR pp. 300-310.
    The boundary determines whether FRTB or SA-CR capital applies.
    """
    TRADING_BOOK = "TRADING_BOOK"
    BANKING_BOOK = "BANKING_BOOK"


class SACCRAssetClass(Enum):
    """SA-CCR asset class for derivative exposure calculation.

    Per 12 CFR 217.132 and ERBA NPR pp. 280-300.
    Determines hedging set construction and supervisory factors.
    """
    INTEREST_RATE = "INTEREST_RATE"
    FOREIGN_EXCHANGE = "FOREIGN_EXCHANGE"
    CREDIT = "CREDIT"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"


class CollateralType(Enum):
    """Collateral type for credit risk mitigation.

    Per ERBA NPR pp. 200-220 and 12 CFR 217.37.
    """
    NONE = "NONE"
    CASH = "CASH"
    SOVEREIGN_DEBT = "SOVEREIGN_DEBT"
    CORPORATE_BOND_IG = "CORPORATE_BOND_IG"
    CORPORATE_BOND_HY = "CORPORATE_BOND_HY"
    EQUITY = "EQUITY"
    GOLD = "GOLD"
    REAL_ESTATE_RESIDENTIAL = "REAL_ESTATE_RESIDENTIAL"
    REAL_ESTATE_COMMERCIAL = "REAL_ESTATE_COMMERCIAL"
    OTHER = "OTHER"


class SecuritizationType(Enum):
    """Securitization exposure type for SEC-ERBA/SEC-SA.

    Per ERBA NPR pp. 350-380.
    """
    STC = "STC"                           # Simple, Transparent, Comparable
    TRADITIONAL = "TRADITIONAL"
    SYNTHETIC = "SYNTHETIC"
    RESECURITIZATION = "RESECURITIZATION"


# =============================================================================
#  Pydantic Models
# =============================================================================

class InstrumentRecord(BaseModel):
    """Complete instrument reference record for regulatory capital calculations.

    Per ERBA NPR pp. 300-310, BCBS d457, and 12 CFR 217.202.
    """
    instrument_id: str = Field(
        description="Unique instrument identifier"
    )
    instrument_type: InstrumentType = Field(
        description="Product type classification per ERBA NPR pp. 300-310"
    )
    book: BookClassification = Field(
        default=BookClassification.BANKING_BOOK,
        description="Trading/banking book assignment per BCBS d457 Chapter 1"
    )
    counterparty_id: Optional[str] = Field(
        default=None,
        description="Associated counterparty for credit risk"
    )
    netting_set_id: Optional[str] = Field(
        default=None,
        description="Netting set for SA-CCR (derivatives only)"
    )
    notional_mm: float = Field(
        description="Notional/face value in $M"
    )
    market_value_mm: float = Field(
        default=0.0,
        description="Current market value in $M"
    )
    currency: str = Field(
        default="USD",
        description="Denomination currency (ISO 4217)"
    )
    maturity_date: Optional[date] = Field(
        default=None,
        description="Contractual maturity date"
    )
    remaining_maturity_years: Optional[float] = Field(
        default=None,
        description="Remaining maturity in years"
    )
    collateral_type: CollateralType = Field(
        default=CollateralType.NONE,
        description="Collateral type per 12 CFR 217.37"
    )
    collateral_value_mm: float = Field(
        default=0.0,
        description="Collateral market value in $M"
    )
    ltv_ratio: Optional[float] = Field(
        default=None,
        description="Loan-to-value ratio for real estate exposures"
    )
    is_traded: bool = Field(
        default=False,
        description="True if held with trading intent"
    )
    saccr_asset_class: Optional[SACCRAssetClass] = Field(
        default=None,
        description="SA-CCR asset class for derivatives per 12 CFR 217.132"
    )
    securitization_type: Optional[SecuritizationType] = Field(
        default=None,
        description="Securitization type if applicable per ERBA NPR pp. 350-380"
    )
    tranche_attachment: Optional[float] = Field(
        default=None,
        description="Securitization tranche attachment point (0-1)"
    )
    tranche_detachment: Optional[float] = Field(
        default=None,
        description="Securitization tranche detachment point (0-1)"
    )
    desk_id: Optional[str] = Field(
        default=None,
        description="Trading desk ID for FRTB desk-level assignment"
    )

    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        """Currency must be 3-letter ISO 4217 code.

        Reference: BCBS d457 MAR21.8 — currency identification.
        """
        if len(v) != 3 or not v.isalpha():
            raise ValueError(f"Currency must be 3-letter ISO 4217 code, got '{v}'")
        return v.upper()

    @field_validator("ltv_ratio")
    @classmethod
    def validate_ltv_range(cls, v: Optional[float]) -> Optional[float]:
        """LTV ratio must be between 0 and 2.0 (allowing underwater loans).

        Reference: ERBA NPR pp. 140-150 — real estate LTV buckets.
        """
        if v is not None and (v < 0 or v > 2.0):
            raise ValueError(f"LTV ratio must be 0-2.0, got {v}")
        return v

    @field_validator("tranche_attachment", "tranche_detachment")
    @classmethod
    def validate_tranche_points(cls, v: Optional[float]) -> Optional[float]:
        """Tranche points must be between 0 and 1.

        Reference: ERBA NPR p.355 — securitization tranche definition.
        """
        if v is not None and (v < 0 or v > 1.0):
            raise ValueError(f"Tranche point must be 0-1, got {v}")
        return v


# =============================================================================
#  Product Classification
# =============================================================================

# Instrument types that are derivatives for SA-CCR purposes
# Per 12 CFR 217.132(b) — derivative transaction definition
_DERIVATIVE_TYPES: frozenset[InstrumentType] = frozenset({
    InstrumentType.IRS,
    InstrumentType.CCS,
    InstrumentType.FX_FORWARD,
    InstrumentType.FX_OPTION,
    InstrumentType.EQUITY_OPTION,
    InstrumentType.CDS,
    InstrumentType.CDX_INDEX,
    InstrumentType.COMMODITY_FORWARD,
    InstrumentType.COMMODITY_OPTION,
    InstrumentType.SWAPTION,
    InstrumentType.CAP_FLOOR,
})

# Instrument types that are SFTs
# Per 12 CFR 217.2 — securities financing transaction definition
_SFT_TYPES: frozenset[InstrumentType] = frozenset({
    InstrumentType.REPO,
    InstrumentType.REVERSE_REPO,
    InstrumentType.SECURITIES_LENDING,
    InstrumentType.SECURITIES_BORROWING,
    InstrumentType.MARGIN_LOAN,
})

# Instrument types that are securitization exposures
# Per ERBA NPR pp. 350-380
_SECURITIZATION_TYPES: frozenset[InstrumentType] = frozenset({
    InstrumentType.RMBS,
    InstrumentType.CMBS,
    InstrumentType.CLO,
    InstrumentType.ABS,
    InstrumentType.RESECURITIZATION,
})

# SA-CCR asset class mapping for derivative types
# Per 12 CFR 217.132(c) — hedging set definitions
_SACCR_ASSET_CLASS_MAP: dict[InstrumentType, SACCRAssetClass] = {
    InstrumentType.IRS: SACCRAssetClass.INTEREST_RATE,
    InstrumentType.CCS: SACCRAssetClass.FOREIGN_EXCHANGE,
    InstrumentType.SWAPTION: SACCRAssetClass.INTEREST_RATE,
    InstrumentType.CAP_FLOOR: SACCRAssetClass.INTEREST_RATE,
    InstrumentType.FX_FORWARD: SACCRAssetClass.FOREIGN_EXCHANGE,
    InstrumentType.FX_OPTION: SACCRAssetClass.FOREIGN_EXCHANGE,
    InstrumentType.EQUITY_OPTION: SACCRAssetClass.EQUITY,
    InstrumentType.CDS: SACCRAssetClass.CREDIT,
    InstrumentType.CDX_INDEX: SACCRAssetClass.CREDIT,
    InstrumentType.COMMODITY_FORWARD: SACCRAssetClass.COMMODITY,
    InstrumentType.COMMODITY_OPTION: SACCRAssetClass.COMMODITY,
}


def is_derivative(instrument_type: InstrumentType) -> bool:
    """Check if instrument type is a derivative for SA-CCR purposes.

    Reference: 12 CFR 217.132(b) — derivative transaction definition.

    Args:
        instrument_type: The instrument type to check.

    Returns:
        True if the instrument is a derivative.
    """
    return instrument_type in _DERIVATIVE_TYPES


def is_sft(instrument_type: InstrumentType) -> bool:
    """Check if instrument type is a securities financing transaction.

    Reference: 12 CFR 217.2 — SFT definition.

    Args:
        instrument_type: The instrument type to check.

    Returns:
        True if the instrument is an SFT.
    """
    return instrument_type in _SFT_TYPES


def is_securitization(instrument_type: InstrumentType) -> bool:
    """Check if instrument type is a securitization exposure.

    Reference: ERBA NPR pp. 350-380 — securitization framework.

    Args:
        instrument_type: The instrument type to check.

    Returns:
        True if the instrument is a securitization exposure.
    """
    return instrument_type in _SECURITIZATION_TYPES


def get_saccr_asset_class(instrument_type: InstrumentType) -> Optional[SACCRAssetClass]:
    """Return the SA-CCR asset class for a derivative instrument type.

    Per 12 CFR 217.132(c), derivatives are mapped to one of five asset
    classes for hedging set construction and add-on calculation.

    Reference: 12 CFR 217.132(c), ERBA NPR pp. 280-300.

    Args:
        instrument_type: The instrument type.

    Returns:
        SA-CCR asset class, or None if not a derivative.
    """
    return _SACCR_ASSET_CLASS_MAP.get(instrument_type)


def classify_book(
    instrument: InstrumentRecord,
    trading_activity_4q_avg_mm: float = 0.0,
) -> BookClassification:
    """Assign instrument to trading book or banking book.

    Per BCBS d457 Chapter 1 and ERBA NPR pp. 300-310:
    - Trading book: instruments held for short-term resale, benefiting from
      price movements, or hedging trading book positions.
    - Banking book: all other instruments.

    FRTB threshold per CLAUDE.md: $5B (4-quarter average trading activity),
    NOT $1B from 2023 NPR. Banks below threshold use simplified SA.

    Reference: BCBS d457 Chapter 1, ERBA NPR pp. 300-310, 12 CFR 217.202.

    Args:
        instrument: The instrument record.
        trading_activity_4q_avg_mm: 4-quarter average trading activity in $M.
            FRTB threshold is $5,000M ($5B). Per ERBA NPR p.305.

    Returns:
        BookClassification (TRADING_BOOK or BANKING_BOOK).
    """
    # FRTB trading activity threshold: $5B = $5,000M
    # Per CLAUDE.md and ERBA NPR p.305
    FRTB_THRESHOLD_MM: float = 5_000.0

    # If bank is below FRTB threshold, all positions are banking book
    # for FRTB purposes (simplified standardised approach applies)
    if trading_activity_4q_avg_mm < FRTB_THRESHOLD_MM:
        return BookClassification.BANKING_BOOK

    # Derivatives and SFTs in the trading book if traded
    if instrument.is_traded:
        return BookClassification.TRADING_BOOK

    # Securitization correlation trading positions go to trading book
    if (
        instrument.instrument_type in (InstrumentType.CDX_INDEX, InstrumentType.CDS)
        and instrument.is_traded
    ):
        return BookClassification.TRADING_BOOK

    # Default: banking book
    return BookClassification.BANKING_BOOK
