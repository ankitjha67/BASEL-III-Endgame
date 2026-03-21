"""SA-CR Exposure Classes per US Basel III Endgame / Federal Reserve Re-Proposal.

Defines exposure classification taxonomy for the Standardized Approach to
Credit Risk (SA-CR). Implements the US-specific exposure classes that diverge
from the Basel Committee framework due to Dodd-Frank Act Section 939A
(prohibition on use of external credit ratings in federal regulations).

References:
    - Federal Reserve Basel III Endgame NPR (July 2023, re-proposed Sept 2025)
    - 12 CFR Part 217, Subpart E - Risk-Weighted Assets: Standardized Approach
    - Dodd-Frank Act Section 939A (no external ratings for risk weighting)
    - Basel Committee CRE20-CRE22 (international standard, adapted for US)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# =========================================================================
#  Exposure Class Enumeration
# =========================================================================

class ExposureClass(Enum):
    """SA-CR exposure classes per US Basel III Endgame proposal.

    The US framework eliminates reliance on external credit ratings per
    Dodd-Frank Section 939A and instead uses Country Risk Classifications
    (CRC), investment-grade self-assessment, and LTV ratios.

    Each value corresponds to the regulatory abbreviation used in the
    Federal Reserve's proposed rule text.
    """

    # Sovereign and government exposures
    SOVEREIGN = "SOVEREIGN"
    """US government: 0% RW. Other sovereigns: 0-150% based on CRC."""

    PUBLIC_SECTOR_ENTITY = "PSE"
    """General obligation: 20%. Revenue obligation: 50%. US PSEs."""

    MULTILATERAL_DEV_BANK = "MDB"
    """Qualifying MDBs (e.g., IBRD, IFC, ADB): 0%. Non-qualifying: 100%."""

    # Financial institutions
    BANK = "BANK"
    """Depository institutions and foreign banks: 20-150% based on CRC."""

    # Corporate exposures
    CORPORATE = "CORPORATE"
    """Investment grade: 65%. All other corporates: 100%."""

    CORPORATE_SME = "CORPORATE_SME"
    """SME corporates (annual revenue <= EUR 50M / ~USD 50M): 85%."""

    # Retail exposures
    RETAIL = "RETAIL"
    """Regulatory retail portfolio: 75%. Granularity and size criteria."""

    RETAIL_TRANSACTOR = "RETAIL_TRANSACTOR"
    """Credit card transactors (balance paid in full): 45% per 2026 proposal."""

    # Real estate exposures
    RESIDENTIAL_MORTGAGE = "RESIDENTIAL_MORTGAGE"
    """First-lien residential mortgages: 40-90% based on LTV ratio."""

    COMMERCIAL_REAL_ESTATE = "CRE"
    """Income-producing CRE: 100%. ADC loans: 150%."""

    HIGH_VOLATILITY_CRE = "HVCRE"
    """High-volatility commercial real estate (ADC): 150%."""

    # Equity and subordinated instruments
    EQUITY = "EQUITY"
    """Equity exposures: 100-400% depending on type (public/VC/speculative)."""

    SUBORDINATED_DEBT = "SUBORDINATED_DEBT"
    """Subordinated debt and other capital instruments: 150%."""

    # Special categories
    DEFAULTED = "DEFAULTED"
    """Exposures past due > 90 days or on nonaccrual: 150%."""

    OTHER = "OTHER"
    """Catch-all for exposures not fitting other classes: 100%."""

    CASH = "CASH"
    """Cash and cash equivalents, gold bullion: 0%."""

    MSA = "MSA"
    """Mortgage servicing assets: 250% (deduction threshold removed in 2026)."""


# =========================================================================
#  Equity Sub-Classification
# =========================================================================

class EquitySubType(Enum):
    """Sub-classification for equity exposures to determine risk weight.

    Per the US proposal, equity risk weights vary significantly by type.
    """

    PUBLIC_TRADED = "PUBLIC_TRADED"
    """Publicly traded equity on a recognized exchange: 250%."""

    SPECULATIVE = "SPECULATIVE"
    """Speculative unlisted equity (not venture capital): 400%."""

    VENTURE_CAPITAL = "VENTURE_CAPITAL"
    """Venture capital and private equity fund investments: 400%."""

    COMMUNITY_DEVELOPMENT = "COMMUNITY_DEVELOPMENT"
    """Community development equity exposures: 100%."""

    FEDERAL_RESERVE_STOCK = "FEDERAL_RESERVE_STOCK"
    """Federal Reserve Bank stock and FHLB stock: 100%."""

    OTHER = "OTHER"
    """Other equity holdings not classified above: 100%."""


# =========================================================================
#  CRE Sub-Classification
# =========================================================================

class CRESubType(Enum):
    """Sub-classification for commercial real estate exposures.

    Risk weight depends on whether the exposure is income-producing,
    acquisition/development/construction (ADC), or land.
    """

    INCOME_PRODUCING = "INCOME_PRODUCING"
    """Income-producing real estate, LTV-dependent: 70-110%."""

    ADC = "ADC"
    """Acquisition, development, and construction loans: 150%."""

    LAND = "LAND"
    """Land loans (not ADC): 150%."""


# =========================================================================
#  PSE Sub-Classification
# =========================================================================

class PSEObligationType(Enum):
    """Type of public sector entity obligation.

    General obligation PSEs receive lower risk weights than revenue
    obligation PSEs under the US framework.
    """

    GENERAL_OBLIGATION = "GENERAL_OBLIGATION"
    """Backed by full faith and credit of the PSE: 20%."""

    REVENUE_OBLIGATION = "REVENUE_OBLIGATION"
    """Repaid from specific revenue streams: 50%."""


# =========================================================================
#  Qualifying MDB List
# =========================================================================

QUALIFYING_MDBS: frozenset[str] = frozenset({
    "IBRD",   # International Bank for Reconstruction and Development
    "IFC",    # International Finance Corporation
    "MIGA",   # Multilateral Investment Guarantee Agency
    "ADB",    # Asian Development Bank
    "AFDB",   # African Development Bank
    "EBRD",   # European Bank for Reconstruction and Development
    "IADB",   # Inter-American Development Bank
    "IDB",    # Islamic Development Bank (alternate abbreviation)
    "NIB",    # Nordic Investment Bank
    "CDB",    # Council of Europe Development Bank
    "EIB",    # European Investment Bank
    "AIIB",   # Asian Infrastructure Investment Bank
})
"""MDBs qualifying for 0% risk weight per 12 CFR 217.

A multilateral development bank qualifies for the 0% risk weight if it
meets the criteria in the Federal Reserve's proposed rule, including
substantial paid-in capital, callable capital commitments, and
strong credit standing.
"""


# =========================================================================
#  Exposure Classification Criteria
# =========================================================================

class ExposureClassificationCriteria(BaseModel):
    """Criteria used to determine the exposure class for a credit exposure.

    Encapsulates the regulatory tests that map a raw exposure to one of
    the SA-CR exposure classes. Used by the classification engine to
    ensure consistent and auditable assignment.

    References:
        12 CFR 217, Subpart E, Sections 217.111-217.115
    """

    is_sovereign: bool = Field(
        default=False,
        description="Exposure to a sovereign or central bank",
    )
    is_pse: bool = Field(
        default=False,
        description="Exposure to a US or foreign public sector entity",
    )
    pse_obligation_type: Optional[PSEObligationType] = Field(
        default=None,
        description="General obligation vs. revenue obligation for PSEs",
    )
    is_mdb: bool = Field(
        default=False,
        description="Exposure to a multilateral development bank",
    )
    mdb_code: Optional[str] = Field(
        default=None,
        description="MDB identifier for qualifying check",
    )
    is_bank: bool = Field(
        default=False,
        description="Exposure to a depository institution or foreign bank",
    )
    is_corporate: bool = Field(
        default=False,
        description="Corporate obligor (non-retail, non-financial)",
    )
    is_investment_grade: bool = Field(
        default=False,
        description=(
            "Self-assessed investment grade per US proposal criteria: "
            "the entity has adequate capacity to meet financial commitments "
            "for the projected life of the exposure"
        ),
    )
    is_sme: bool = Field(
        default=False,
        description="SME corporate (annual revenue <= ~USD 50M equivalent)",
    )
    is_retail: bool = Field(
        default=False,
        description="Meets regulatory retail criteria (granularity, size)",
    )
    is_transactor: bool = Field(
        default=False,
        description=(
            "Retail credit card exposure where the obligor has paid the "
            "outstanding balance in full at each scheduled payment date "
            "for the previous 12 months"
        ),
    )
    is_residential_mortgage: bool = Field(
        default=False,
        description="First-lien residential mortgage",
    )
    is_cre: bool = Field(
        default=False,
        description="Commercial real estate exposure",
    )
    cre_sub_type: Optional[CRESubType] = Field(
        default=None,
        description="Sub-type for CRE exposures (income-producing, ADC, land)",
    )
    is_equity: bool = Field(
        default=False,
        description="Equity exposure (direct or indirect)",
    )
    equity_sub_type: Optional[EquitySubType] = Field(
        default=None,
        description="Sub-type for equity exposures",
    )
    is_subordinated_debt: bool = Field(
        default=False,
        description="Subordinated debt or other capital instrument",
    )
    is_defaulted: bool = Field(
        default=False,
        description="Past due > 90 days or on nonaccrual status",
    )
    is_cash: bool = Field(
        default=False,
        description="Cash, cash equivalents, or gold bullion",
    )
    is_msa: bool = Field(
        default=False,
        description="Mortgage servicing asset",
    )
    country_risk_class: int = Field(
        default=0,
        ge=0,
        le=7,
        description="OECD Country Risk Classification (0-7) for sovereign/bank exposures",
    )
    ltv_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Loan-to-value ratio for mortgage exposures (as decimal, e.g. 0.80)",
    )


def classify_exposure(criteria: ExposureClassificationCriteria) -> ExposureClass:
    """Determine the SA-CR exposure class from classification criteria.

    Applies the exposure class hierarchy defined in the US Basel III
    Endgame proposal. Defaulted status takes priority over other
    classifications. Cash is checked early for efficiency.

    Args:
        criteria: The classification criteria for the exposure.

    Returns:
        The appropriate ExposureClass enum value.

    References:
        12 CFR 217, Subpart E, Sections 217.111-217.115
    """
    # Defaulted exposures override other classifications
    if criteria.is_defaulted:
        return ExposureClass.DEFAULTED

    # Cash items are always 0%
    if criteria.is_cash:
        return ExposureClass.CASH

    # Mortgage servicing assets
    if criteria.is_msa:
        return ExposureClass.MSA

    # Sovereign exposures (including US government)
    if criteria.is_sovereign:
        return ExposureClass.SOVEREIGN

    # Public sector entities
    if criteria.is_pse:
        return ExposureClass.PUBLIC_SECTOR_ENTITY

    # Multilateral development banks
    if criteria.is_mdb:
        return ExposureClass.MULTILATERAL_DEV_BANK

    # Banks and depository institutions
    if criteria.is_bank:
        return ExposureClass.BANK

    # Subordinated debt (check before corporate/equity)
    if criteria.is_subordinated_debt:
        return ExposureClass.SUBORDINATED_DEBT

    # Equity exposures
    if criteria.is_equity:
        return ExposureClass.EQUITY

    # Residential mortgages
    if criteria.is_residential_mortgage:
        return ExposureClass.RESIDENTIAL_MORTGAGE

    # Commercial real estate
    if criteria.is_cre:
        if criteria.cre_sub_type == CRESubType.ADC:
            return ExposureClass.HIGH_VOLATILITY_CRE
        return ExposureClass.COMMERCIAL_REAL_ESTATE

    # Retail exposures (transactor is a sub-class of retail)
    if criteria.is_retail:
        if criteria.is_transactor:
            return ExposureClass.RETAIL_TRANSACTOR
        return ExposureClass.RETAIL

    # Corporate exposures (SME is a sub-class)
    if criteria.is_corporate:
        if criteria.is_sme:
            return ExposureClass.CORPORATE_SME
        return ExposureClass.CORPORATE

    # Default catch-all
    return ExposureClass.OTHER


def is_qualifying_mdb(mdb_code: str | None) -> bool:
    """Check whether an MDB qualifies for the 0% risk weight.

    Args:
        mdb_code: The MDB identifier (e.g., 'IBRD', 'IFC').

    Returns:
        True if the MDB is in the qualifying list.

    References:
        12 CFR 217, Subpart E, Table of qualifying MDBs
    """
    if mdb_code is None:
        return False
    return mdb_code.upper() in QUALIFYING_MDBS


# =========================================================================
#  LTV Bucket Determination for Residential Mortgages
# =========================================================================

def get_resi_mortgage_ltv_bucket(ltv_ratio: float) -> str:
    """Determine the LTV bucket for a residential mortgage exposure.

    The US Basel III Endgame proposal assigns risk weights to residential
    mortgages based on the current loan-to-value ratio, using the
    following buckets.

    Args:
        ltv_ratio: LTV as a decimal (e.g., 0.75 for 75%).

    Returns:
        String key for the LTV bucket (e.g., '70-80').

    Raises:
        ValueError: If ltv_ratio is negative.

    References:
        12 CFR 217, Subpart E, Table: Risk weights for residential
        mortgage exposures
    """
    if ltv_ratio < 0:
        raise ValueError(f"LTV ratio cannot be negative: {ltv_ratio}")

    if ltv_ratio <= 0.50:
        return "0-50"
    elif ltv_ratio <= 0.60:
        return "50-60"
    elif ltv_ratio <= 0.70:
        return "60-70"
    elif ltv_ratio <= 0.80:
        return "70-80"
    elif ltv_ratio <= 0.90:
        return "80-90"
    elif ltv_ratio <= 1.00:
        return "90-100"
    else:
        return "100+"


# =========================================================================
#  CRE LTV Bucket Determination
# =========================================================================

def get_cre_ltv_bucket(ltv_ratio: float) -> str:
    """Determine the LTV bucket for an income-producing CRE exposure.

    Args:
        ltv_ratio: LTV as a decimal (e.g., 0.60 for 60%).

    Returns:
        String key for the CRE LTV bucket.

    Raises:
        ValueError: If ltv_ratio is negative.

    References:
        12 CFR 217, Subpart E, Table: Risk weights for commercial
        real estate exposures
    """
    if ltv_ratio < 0:
        raise ValueError(f"LTV ratio cannot be negative: {ltv_ratio}")

    if ltv_ratio <= 0.60:
        return "0-60"
    elif ltv_ratio <= 0.80:
        return "60-80"
    else:
        return "80+"
