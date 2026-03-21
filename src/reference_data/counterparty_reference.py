"""Counterparty reference data for Basel III Endgame engine.

Provides counterparty classification, registry, and netting set definitions
for SA-CR risk weight assignment and SA-CCR exposure calculations.

Key regulatory references:
- ERBA NPR pp. 100-130: Counterparty classification and risk weight assignment
- 12 CFR 217.32: Risk-weighted assets for general risk weights
- Dodd-Frank Act Section 939A: Prohibition on use of external credit ratings
- BCBS d424 Chapter 3: Credit risk — standardised approach

All monetary amounts in USD millions ($M) unless explicitly stated otherwise.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
#  Enums
# =============================================================================

class CounterpartyType(Enum):
    """Counterparty types for SA-CR risk weight assignment.

    Per ERBA NPR pp. 100-110 and 12 CFR 217.32.
    Note: US proposal does NOT use external ratings for corporate exposures
    per Dodd-Frank Section 939A.
    """
    SOVEREIGN = "SOVEREIGN"
    PSE = "PSE"                           # Public Sector Entity
    MDB = "MDB"                           # Multilateral Development Bank
    BANK = "BANK"
    COVERED_BOND = "COVERED_BOND"
    CORPORATE = "CORPORATE"
    CORPORATE_IG = "CORPORATE_IG"         # Investment-grade (self-assessment)
    SME = "SME"                           # Small/medium enterprise
    SME_RETAIL = "SME_RETAIL"             # SME treated as retail
    RETAIL = "RETAIL"
    RETAIL_MORTGAGE = "RETAIL_MORTGAGE"
    RETAIL_TRANSACTOR = "RETAIL_TRANSACTOR"
    CRE = "CRE"                           # Commercial Real Estate
    ADC = "ADC"                            # Acquisition, Development, Construction
    SUBORDINATED_DEBT = "SUBORDINATED_DEBT"
    EQUITY = "EQUITY"
    CCP_QUALIFYING = "CCP_QUALIFYING"
    CCP_NON_QUALIFYING = "CCP_NON_QUALIFYING"
    DEFAULTED = "DEFAULTED"
    MSA = "MSA"                           # Mortgage Servicing Assets (250% RW, not deducted)
    OTHER = "OTHER"


class SovereignRiskCategory(Enum):
    """Sovereign risk categories for SA-CR.

    Per ERBA NPR pp. 102-105 and 12 CFR 217.32(a).
    US sovereigns: 0% risk weight.
    Non-US sovereigns: based on CRC (Country Risk Classification).
    """
    CRC_0_1 = "CRC_0_1"    # 0% risk weight (US, G7, OECD low-risk)
    CRC_2 = "CRC_2"        # 20% risk weight
    CRC_3 = "CRC_3"        # 50% risk weight
    CRC_4_6 = "CRC_4_6"    # 100% risk weight
    CRC_7 = "CRC_7"        # 150% risk weight
    UNRATED = "UNRATED"     # 100% risk weight


class IndustryClassification(Enum):
    """Industry classification for sector-based analysis.

    Per ERBA NPR pp. 115-120, FR Y-9C Schedule HC.
    """
    FINANCIAL_SERVICES = "FINANCIAL_SERVICES"
    INSURANCE = "INSURANCE"
    TECHNOLOGY = "TECHNOLOGY"
    HEALTHCARE = "HEALTHCARE"
    ENERGY = "ENERGY"
    UTILITIES = "UTILITIES"
    CONSUMER_DISCRETIONARY = "CONSUMER_DISCRETIONARY"
    CONSUMER_STAPLES = "CONSUMER_STAPLES"
    INDUSTRIALS = "INDUSTRIALS"
    MATERIALS = "MATERIALS"
    REAL_ESTATE = "REAL_ESTATE"
    TELECOMMUNICATIONS = "TELECOMMUNICATIONS"
    GOVERNMENT = "GOVERNMENT"
    OTHER = "OTHER"


class DomicileRegion(Enum):
    """Counterparty domicile region for regulatory treatment.

    Per ERBA NPR pp. 100-102.
    """
    US = "US"
    EU = "EU"
    UK = "UK"
    JAPAN = "JAPAN"
    CANADA = "CANADA"
    AUSTRALIA = "AUSTRALIA"
    SWITZERLAND = "SWITZERLAND"
    OTHER_DEVELOPED = "OTHER_DEVELOPED"
    EMERGING_MARKET = "EMERGING_MARKET"


# =============================================================================
#  Pydantic Models
# =============================================================================

class CounterpartyRecord(BaseModel):
    """Complete counterparty reference record for regulatory capital calculations.

    Per ERBA NPR pp. 100-130 and 12 CFR 217.32.
    Supports SA-CR classification, SA-CCR netting, and G-SIB indicator reporting.
    """
    counterparty_id: str = Field(
        description="Unique counterparty identifier"
    )
    name: str = Field(
        description="Legal entity name"
    )
    lei: Optional[str] = Field(
        default=None,
        description="Legal Entity Identifier (20 chars, ISO 17442)"
    )
    counterparty_type: CounterpartyType = Field(
        description="SA-CR counterparty classification per 12 CFR 217.32"
    )
    sovereign_risk_category: Optional[SovereignRiskCategory] = Field(
        default=None,
        description="CRC-based risk category for sovereigns per ERBA NPR p.102"
    )
    industry: IndustryClassification = Field(
        default=IndustryClassification.OTHER,
        description="Industry sector for concentration analysis"
    )
    domicile: DomicileRegion = Field(
        default=DomicileRegion.US,
        description="Counterparty domicile per ERBA NPR pp. 100-102"
    )
    is_financial: bool = Field(
        default=False,
        description="True if financial institution (affects SA-CCR alpha: 1.4 vs 1.0)"
    )
    is_investment_grade: bool = Field(
        default=False,
        description=(
            "Self-assessed IG status per Dodd-Frank 939A — "
            "NO external rating dependency. Per ERBA NPR p.112, "
            "IG self-assessment based on obligor's financial condition."
        )
    )
    annual_revenue_mm: Optional[float] = Field(
        default=None,
        description="Annual revenue in $M for SME classification (threshold: EUR 50M)"
    )
    total_assets_mm: Optional[float] = Field(
        default=None,
        description="Total consolidated assets in $M"
    )
    exposure_amount_mm: float = Field(
        default=0.0,
        description="Total exposure to this counterparty in $M"
    )
    is_defaulted: bool = Field(
        default=False,
        description="True if counterparty is in default (150% RW per 12 CFR 217.32(k))"
    )
    is_us_gse: bool = Field(
        default=False,
        description="True if US Government-Sponsored Enterprise (20% RW)"
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="Parent entity ID for consolidated exposure tracking"
    )

    @field_validator("lei")
    @classmethod
    def validate_lei_format(cls, v: Optional[str]) -> Optional[str]:
        """LEI must be 20 alphanumeric characters per ISO 17442.

        Reference: BCBS 239 data quality requirements.
        """
        if v is not None and len(v) != 20:
            raise ValueError(f"LEI must be 20 characters, got {len(v)}")
        return v

    @field_validator("annual_revenue_mm")
    @classmethod
    def validate_revenue_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Revenue must be non-negative.

        Reference: ERBA NPR p.118 — SME classification threshold.
        """
        if v is not None and v < 0:
            raise ValueError("Annual revenue must be non-negative")
        return v


class NettingSet(BaseModel):
    """Netting set definition for SA-CCR counterparty credit risk.

    Per BCBS d424 Section 7 (SA-CCR) and ERBA NPR pp. 280-300.
    A netting set groups derivative transactions under a single
    legally enforceable netting agreement.
    """
    netting_set_id: str = Field(
        description="Unique netting set identifier"
    )
    counterparty_id: str = Field(
        description="Associated counterparty ID"
    )
    is_margined: bool = Field(
        default=False,
        description="True if subject to margin agreement per SA-CCR"
    )
    margin_period_of_risk_days: int = Field(
        default=10,
        description=(
            "Margin period of risk in days. "
            "10 days for bilateral OTC; 5 days for cleared; "
            "20 days for large netting sets (>5000 trades). "
            "Per ERBA NPR p.285."
        )
    )
    threshold_mm: float = Field(
        default=0.0,
        description="Margin threshold in $M (below which no VM is exchanged)"
    )
    minimum_transfer_amount_mm: float = Field(
        default=0.0,
        description="Minimum transfer amount in $M per CSA"
    )
    independent_collateral_amount_mm: float = Field(
        default=0.0,
        description="Independent collateral amount (ICA) in $M per SA-CCR"
    )
    variation_margin_mm: float = Field(
        default=0.0,
        description="Current variation margin held in $M"
    )
    has_enforceable_netting: bool = Field(
        default=True,
        description="True if netting agreement is legally enforceable per ERBA NPR p.282"
    )

    @field_validator("margin_period_of_risk_days")
    @classmethod
    def validate_mpor(cls, v: int) -> int:
        """MPOR must be positive and within regulatory bounds.

        Reference: ERBA NPR p.285 — MPOR floors.
        """
        if v < 5:
            raise ValueError("MPOR must be >= 5 days (cleared CCP floor)")
        return v


# =============================================================================
#  Counterparty Registry
# =============================================================================

class CounterpartyRegistry:
    """Registry for counterparty reference data with regulatory classification.

    Provides lookup by ID, type, and regulatory classification.
    Implements Dodd-Frank Section 939A requirements: risk weights
    are NOT based on external credit ratings for corporates.

    Reference: ERBA NPR pp. 100-130, 12 CFR 217.32.
    """

    def __init__(self) -> None:
        """Initialize empty counterparty registry."""
        self._counterparties: dict[str, CounterpartyRecord] = {}
        self._netting_sets: dict[str, NettingSet] = {}

    def add_counterparty(self, record: CounterpartyRecord) -> None:
        """Add a counterparty record to the registry.

        Reference: BCBS 239 — data lineage and completeness requirements.
        """
        self._counterparties[record.counterparty_id] = record

    def add_netting_set(self, netting_set: NettingSet) -> None:
        """Add a netting set definition.

        Reference: ERBA NPR p.282 — netting set identification.
        """
        if netting_set.counterparty_id not in self._counterparties:
            raise ValueError(
                f"Counterparty {netting_set.counterparty_id} not found in registry. "
                "Add counterparty before netting set."
            )
        self._netting_sets[netting_set.netting_set_id] = netting_set

    def get_counterparty(self, counterparty_id: str) -> CounterpartyRecord:
        """Look up counterparty by ID.

        Reference: BCBS 239 — data accessibility requirements.
        """
        if counterparty_id not in self._counterparties:
            raise KeyError(f"Counterparty {counterparty_id} not found in registry")
        return self._counterparties[counterparty_id]

    def get_netting_set(self, netting_set_id: str) -> NettingSet:
        """Look up netting set by ID.

        Reference: ERBA NPR p.282 — netting set identification.
        """
        if netting_set_id not in self._netting_sets:
            raise KeyError(f"Netting set {netting_set_id} not found in registry")
        return self._netting_sets[netting_set_id]

    def get_netting_sets_for_counterparty(
        self, counterparty_id: str
    ) -> list[NettingSet]:
        """Get all netting sets associated with a counterparty.

        Reference: SA-CCR aggregation per ERBA NPR p.290.
        """
        return [
            ns for ns in self._netting_sets.values()
            if ns.counterparty_id == counterparty_id
        ]

    def get_counterparties_by_type(
        self, cpty_type: CounterpartyType
    ) -> list[CounterpartyRecord]:
        """Filter counterparties by type for SA-CR segmentation.

        Reference: 12 CFR 217.32 — exposure classification.
        """
        return [
            c for c in self._counterparties.values()
            if c.counterparty_type == cpty_type
        ]

    def get_counterparties_by_industry(
        self, industry: IndustryClassification
    ) -> list[CounterpartyRecord]:
        """Filter counterparties by industry for concentration analysis.

        Reference: FR Y-15 systemic risk indicators — interconnectedness.
        """
        return [
            c for c in self._counterparties.values()
            if c.industry == industry
        ]

    def get_financial_counterparties(self) -> list[CounterpartyRecord]:
        """Return all financial institution counterparties.

        Important for SA-CCR: alpha = 1.4 for financial counterparties
        vs 1.0 for commercial end-users per ERBA NPR p.290.
        """
        return [
            c for c in self._counterparties.values()
            if c.is_financial
        ]

    def get_defaulted_counterparties(self) -> list[CounterpartyRecord]:
        """Return all defaulted counterparties (150% RW).

        Reference: 12 CFR 217.32(k) — defaulted exposures.
        """
        return [
            c for c in self._counterparties.values()
            if c.is_defaulted
        ]

    def total_exposure_mm(self) -> float:
        """Total exposure across all counterparties in $M.

        Reference: FR Y-9C Schedule HC-R — total RWA computation.
        """
        return sum(c.exposure_amount_mm for c in self._counterparties.values())

    @property
    def count(self) -> int:
        """Number of counterparties in registry."""
        return len(self._counterparties)

    @property
    def netting_set_count(self) -> int:
        """Number of netting sets in registry."""
        return len(self._netting_sets)

    def all_counterparties(self) -> list[CounterpartyRecord]:
        """Return all counterparties as a list.

        Reference: BCBS 239 — data completeness requirement.
        """
        return list(self._counterparties.values())


# =============================================================================
#  Regulatory Classification Logic
# =============================================================================

def classify_counterparty_type(
    is_sovereign: bool = False,
    is_pse: bool = False,
    is_mdb: bool = False,
    is_bank: bool = False,
    is_financial: bool = False,
    is_investment_grade: bool = False,
    annual_revenue_mm: Optional[float] = None,
    exposure_amount_mm: float = 0.0,
    is_retail_exposure: bool = False,
    is_mortgage: bool = False,
    is_cre: bool = False,
    is_adc: bool = False,
    is_defaulted: bool = False,
    is_ccp: bool = False,
    is_qualifying_ccp: bool = False,
) -> CounterpartyType:
    """Classify a counterparty into the appropriate SA-CR category.

    Implements the classification hierarchy per 12 CFR 217.32 and
    ERBA NPR pp. 100-130. Classification follows a priority order:
    defaulted > sovereign > MDB > PSE > bank > CCP > corporate subtypes > retail.

    Note: Per Dodd-Frank Section 939A, external credit ratings are NOT used
    for risk weight determination. Investment-grade status is self-assessed.

    Reference: ERBA NPR pp. 100-130, 12 CFR 217.32.

    Args:
        is_sovereign: True if sovereign/central bank exposure.
        is_pse: True if public sector entity.
        is_mdb: True if multilateral development bank.
        is_bank: True if depository institution or bank holding company.
        is_financial: True if financial institution.
        is_investment_grade: True if self-assessed as IG per ERBA NPR p.112.
        annual_revenue_mm: Annual revenue in $M (for SME classification).
        exposure_amount_mm: Exposure amount in $M.
        is_retail_exposure: True if qualifies as retail.
        is_mortgage: True if residential mortgage.
        is_cre: True if commercial real estate.
        is_adc: True if acquisition/development/construction.
        is_defaulted: True if counterparty is in default.
        is_ccp: True if central counterparty.
        is_qualifying_ccp: True if qualifying CCP.

    Returns:
        CounterpartyType classification.
    """
    # Defaulted takes priority — 150% RW per 12 CFR 217.32(k)
    if is_defaulted:
        return CounterpartyType.DEFAULTED

    # Sovereign exposures — 0% to 150% based on CRC
    if is_sovereign:
        return CounterpartyType.SOVEREIGN

    # MDB — 0% for qualifying MDBs per 12 CFR 217.32(b)
    if is_mdb:
        return CounterpartyType.MDB

    # PSE — risk weight depends on sovereign risk weight
    if is_pse:
        return CounterpartyType.PSE

    # Bank/DI — 20-150% per 12 CFR 217.32(d)
    if is_bank:
        return CounterpartyType.BANK

    # CCP — per 12 CFR 217.35
    if is_ccp:
        if is_qualifying_ccp:
            return CounterpartyType.CCP_QUALIFYING
        return CounterpartyType.CCP_NON_QUALIFYING

    # Real estate classifications
    if is_adc:
        return CounterpartyType.ADC
    if is_cre:
        return CounterpartyType.CRE
    if is_mortgage:
        return CounterpartyType.RETAIL_MORTGAGE

    # Retail classification
    if is_retail_exposure:
        # SME treated as retail: revenue <= EUR 50M (~$55M) and
        # exposure <= EUR 1M (~$1.1M) per ERBA NPR p.118
        sme_revenue_threshold_mm = 55.0  # EUR 50M approx
        sme_retail_exposure_threshold_mm = 1.1  # EUR 1M approx
        if (
            annual_revenue_mm is not None
            and annual_revenue_mm <= sme_revenue_threshold_mm
            and exposure_amount_mm <= sme_retail_exposure_threshold_mm
        ):
            return CounterpartyType.SME_RETAIL
        return CounterpartyType.RETAIL

    # Corporate classification
    # SME threshold: annual revenue <= EUR 50M (~$55M)
    sme_revenue_threshold_mm = 55.0
    if annual_revenue_mm is not None and annual_revenue_mm <= sme_revenue_threshold_mm:
        return CounterpartyType.SME

    # Corporate IG: 65% RW per CLAUDE.md (self-assessment, no external ratings)
    if is_investment_grade:
        return CounterpartyType.CORPORATE_IG

    # General corporate: 100% RW
    return CounterpartyType.CORPORATE


def get_sa_ccr_alpha(counterparty: CounterpartyRecord) -> float:
    """Return the SA-CCR alpha multiplier for a counterparty.

    Per ERBA NPR p.290 and CLAUDE.md:
    - alpha = 1.4 for financial counterparties
    - alpha = 1.0 for commercial end-users

    Reference: 12 CFR 217.132(c), ERBA NPR p.290.

    Args:
        counterparty: Counterparty record.

    Returns:
        SA-CCR alpha multiplier (1.0 or 1.4).
    """
    if counterparty.is_financial:
        return 1.4
    return 1.0
