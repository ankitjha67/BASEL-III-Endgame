"""OBS/CCF — Off-Balance Sheet Credit Conversion Factors for SA-CR.

Converts off-balance sheet (OBS) notional amounts to credit-equivalent
amounts (CEA) using credit conversion factors (CCFs) per the US Basel III
Endgame Standardized Approach. The CEA is then used as the exposure at
default (EAD) for SA-CR RWA calculation.

The credit-equivalent amount is computed as:
    CEA = drawn_amount + (undrawn_amount x CCF)

where undrawn_amount = notional_amount - drawn_amount.

CCF values follow the US Federal Reserve Basel III Endgame 2026 Re-Proposal,
which adopts 40% (not 50%) for other commitments > 1 year and 10% for
unconditionally cancellable commitments (UCCs).

References:
    - 12 CFR 217.33 — Off-balance sheet exposures
    - BCBS d424 CRE20.69-20.93 — Credit conversion factors
    - US Federal Reserve Basel III Endgame 2026 Re-Proposal
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# =========================================================================
#  OBS Category Enumeration
# =========================================================================

class OBSCategory(str, Enum):
    """Off-balance sheet item categories per 12 CFR 217.33.

    Each category maps to a specific credit conversion factor (CCF)
    that converts the off-balance sheet notional to a credit-equivalent
    on-balance sheet amount.

    References:
        12 CFR 217.33 — Off-Balance Sheet Items
        BCBS d424 CRE20.70 — Table of CCFs
    """

    UCC = "UCC"
    """Unconditionally cancellable commitments: 10% CCF.

    Commitments that the banking organization can revoke unconditionally
    at any time without prior notice, or that effectively provide for
    automatic cancellation due to deterioration in borrower
    creditworthiness.

    Per 12 CFR 217.33(b) and BCBS d424 CRE20.71.
    """

    TRADE_LC = "TRADE_LC"
    """Short-term self-liquidating trade letters of credit: 20% CCF.

    Letters of credit arising from the movement of goods (e.g.,
    documentary credits collateralized by the underlying shipment)
    where the maturity is generally limited to the transit period.

    Per 12 CFR 217.33(c) and BCBS d424 CRE20.72.
    """

    TRANSACTION_CONTINGENCY = "TRANSACTION_CONTINGENCY"
    """Transaction-related contingent items: 50% CCF.

    Includes performance bonds, bid bonds, warranties, and standby
    letters of credit related to particular transactions. These
    guarantee performance rather than financial obligation.

    Per 12 CFR 217.33(d) and BCBS d424 CRE20.73.
    """

    NIF = "NIF"
    """Note issuance facilities: 50% CCF.

    Arrangements whereby a borrower can issue short-term paper
    (typically commercial paper) with the facility providing a
    backstop commitment to purchase unsold notes.

    Per 12 CFR 217.33(d) and BCBS d424 CRE20.74.
    """

    RUF = "RUF"
    """Revolving underwriting facilities: 50% CCF.

    Similar to NIFs; the banking organization commits to underwrite
    issuances of short-term paper by the borrower on a revolving basis.

    Per 12 CFR 217.33(d) and BCBS d424 CRE20.74.
    """

    COMMITMENT_GT_1Y = "COMMITMENT_GT_1Y"
    """Other commitments with original maturity > 1 year: 40% CCF.

    Commitments to extend credit (including revolving credit lines,
    term loan commitments) with original maturity exceeding one year
    that do not qualify as UCCs.

    Per US Federal Reserve Basel III Endgame 2026 Re-Proposal.
    Note: The 2026 re-proposal reduces this from 50% to 40%.
    BCBS d424 CRE20.75.
    """

    COMMITMENT_LE_1Y = "COMMITMENT_LE_1Y"
    """Other commitments with original maturity <= 1 year: 20% CCF.

    Short-term commitments to extend credit that do not qualify
    as unconditionally cancellable.

    Per 12 CFR 217.33(e) and BCBS d424 CRE20.76.
    """

    DIRECT_CREDIT_SUB = "DIRECT_CREDIT_SUB"
    """Direct credit substitutes: 100% CCF.

    Includes financial guarantees, standby letters of credit serving
    as financial guarantees, and other instruments that substitute
    for direct extensions of credit. The banking organization assumes
    the credit risk of the underlying obligor.

    Per 12 CFR 217.33(f) and BCBS d424 CRE20.77.
    """

    FORWARD_PURCHASE = "FORWARD_PURCHASE"
    """Forward asset purchases: 100% CCF.

    Commitments to purchase assets (including loans, securities) at
    a specified future date. The full notional is converted because
    the banking organization is committed to taking the asset onto
    its balance sheet.

    Per 12 CFR 217.33(f) and BCBS d424 CRE20.78.
    """

    REPO_STYLE = "REPO_STYLE"
    """Repo-style transactions: 100% CCF.

    Securities repurchase agreements, reverse repos, and similar
    collateralized borrowing/lending arrangements.

    Per 12 CFR 217.33(f) and BCBS d424 CRE20.79.
    """

    SEC_LENDING = "SEC_LENDING"
    """Securities lending/borrowing: 100% CCF.

    Collateralized securities lending and borrowing transactions
    where the banking organization lends or borrows securities.

    Per 12 CFR 217.33(f) and BCBS d424 CRE20.80.
    """

    ACCEPTANCE = "ACCEPTANCE"
    """Banker's acceptances: 100% CCF.

    Time drafts drawn on and accepted by a banking organization,
    creating an unconditional obligation to pay.

    Per 12 CFR 217.33(f) and BCBS d424 CRE20.81.
    """


# =========================================================================
#  OBS Exposure Data Model
# =========================================================================

class OBSExposure(BaseModel):
    """Off-balance sheet exposure for CCF conversion.

    Represents a single off-balance sheet item with all attributes
    needed to determine the applicable CCF and compute the
    credit-equivalent amount (CEA).

    The CEA is computed as:
        CEA = drawn_amount + (undrawn_amount x CCF)

    where undrawn_amount = notional_amount - drawn_amount.

    References:
        12 CFR 217.33 — Off-Balance Sheet Items
        BCBS d424 CRE20.69-20.93 — Credit Conversion Factors
    """

    exposure_id: str = Field(
        description="Unique identifier for the OBS exposure",
    )
    obs_category: OBSCategory = Field(
        description="OBS classification determining the applicable CCF",
    )
    notional_amount: float = Field(
        ge=0,
        description="Notional or committed amount in $M",
    )
    drawn_amount: float = Field(
        ge=0,
        default=0.0,
        description="Already drawn/funded amount in $M",
    )
    original_maturity_years: float = Field(
        ge=0,
        default=1.0,
        description=(
            "Original maturity of the commitment in years. "
            "Used to distinguish COMMITMENT_GT_1Y from COMMITMENT_LE_1Y "
            "when auto-classifying commitments."
        ),
    )
    is_unconditionally_cancellable: bool = Field(
        default=False,
        description=(
            "Whether the commitment can be unconditionally cancelled "
            "at any time without prior notice. If True, overrides "
            "obs_category to UCC for CCF purposes."
        ),
    )
    counterparty_id: str | None = Field(
        default=None,
        description="Counterparty reference for linkage to SA-CR exposure",
    )
    exposure_class: str | None = Field(
        default=None,
        description=(
            "SA-CR exposure class for risk weight determination. "
            "If provided, enables RWA calculation on the CEA."
        ),
    )

    @model_validator(mode="after")
    def validate_drawn_le_notional(self) -> OBSExposure:
        """Ensure drawn amount does not exceed notional.

        Per 12 CFR 217.33, the drawn amount represents the portion
        already funded, which logically cannot exceed the total
        committed notional.
        """
        if self.drawn_amount > self.notional_amount:
            raise ValueError(
                f"drawn_amount ({self.drawn_amount}) cannot exceed "
                f"notional_amount ({self.notional_amount}) for "
                f"exposure {self.exposure_id}"
            )
        return self


# =========================================================================
#  OBS Result Data Model
# =========================================================================

class OBSResult(BaseModel):
    """Result of OBS CCF conversion for a portfolio of OBS exposures.

    Aggregates credit-equivalent amounts across all OBS exposures and
    provides breakdowns by category for regulatory reporting.

    References:
        12 CFR 217.33 — Off-Balance Sheet Items
        FR Y-9C Schedule HC-R — Regulatory Capital Components
    """

    total_notional: float = Field(
        default=0.0,
        description="Sum of all notional/committed amounts ($M)",
    )
    total_drawn: float = Field(
        default=0.0,
        description="Sum of all drawn/funded amounts ($M)",
    )
    total_undrawn: float = Field(
        default=0.0,
        description="Sum of all undrawn amounts ($M)",
    )
    total_ead: float = Field(
        default=0.0,
        description=(
            "Total credit-equivalent amount after CCF application ($M). "
            "CEA = drawn + (undrawn x CCF)"
        ),
    )
    total_rwa: float = Field(
        default=0.0,
        description=(
            "Total risk-weighted assets ($M). "
            "RWA = EAD x risk_weight (only if risk weights provided)"
        ),
    )
    exposures_by_category: dict[str, dict] = Field(
        default_factory=dict,
        description=(
            "Aggregated results by OBS category. Each entry contains: "
            "count, notional, drawn, undrawn, ead, ccf, rwa"
        ),
    )
    details: list[dict] = Field(
        default_factory=list,
        description="Per-exposure conversion details for audit trail",
    )


# =========================================================================
#  OBS CCF Calculator
# =========================================================================

class OBSCCFCalculator:
    """Calculate credit-equivalent amounts for off-balance sheet exposures.

    Converts OBS notional amounts to credit exposure using CCFs
    per 12 CFR 217.33 and BCBS d424 CRE20.69-20.93.

    The credit-equivalent amount (CEA) = drawn + (undrawn x CCF).
    This CEA is then used as the EAD in SA-CR RWA calculation.

    Usage:
        >>> calculator = OBSCCFCalculator()
        >>> exposures = [
        ...     OBSExposure(
        ...         exposure_id="OBS-001",
        ...         obs_category=OBSCategory.COMMITMENT_GT_1Y,
        ...         notional_amount=100.0,
        ...         drawn_amount=20.0,
        ...     ),
        ... ]
        >>> result = calculator.calculate(exposures)
        >>> print(f"Total EAD: {result.total_ead:.2f}")
        Total EAD: 52.00

    References:
        12 CFR 217.33 — Off-Balance Sheet Items
        BCBS d424 CRE20.69-20.93 — Credit Conversion Factors
        US Federal Reserve Basel III Endgame 2026 Re-Proposal
    """

    CCF_TABLE: dict[OBSCategory, float] = {
        OBSCategory.UCC: 0.10,
        OBSCategory.TRADE_LC: 0.20,
        OBSCategory.TRANSACTION_CONTINGENCY: 0.50,
        OBSCategory.NIF: 0.50,
        OBSCategory.RUF: 0.50,
        OBSCategory.COMMITMENT_GT_1Y: 0.40,
        OBSCategory.COMMITMENT_LE_1Y: 0.20,
        OBSCategory.DIRECT_CREDIT_SUB: 1.00,
        OBSCategory.FORWARD_PURCHASE: 1.00,
        OBSCategory.REPO_STYLE: 1.00,
        OBSCategory.SEC_LENDING: 1.00,
        OBSCategory.ACCEPTANCE: 1.00,
    }
    """CCF values per 12 CFR 217.33 and BCBS d424 CRE20.70.

    Key US-specific adjustments in 2026 re-proposal:
      - COMMITMENT_GT_1Y: 40% (reduced from 50% in prior rules)
      - UCC: 10% (unconditionally cancellable commitments)
    """

    def __init__(self) -> None:
        """Initialize the OBS CCF calculator.

        References:
            12 CFR 217.33 — Off-Balance Sheet Items
        """
        logger.debug("OBSCCFCalculator initialized with %d CCF categories",
                      len(self.CCF_TABLE))

    def get_ccf(self, category: OBSCategory) -> float:
        """Get the credit conversion factor for a given OBS category.

        Args:
            category: The OBS item category per 12 CFR 217.33.

        Returns:
            CCF as a decimal (e.g., 0.40 for 40%).

        Raises:
            ValueError: If the category is not recognized.

        References:
            12 CFR 217.33 — Off-Balance Sheet Items
            BCBS d424 CRE20.70 — Table of CCFs
        """
        if category not in self.CCF_TABLE:
            raise ValueError(
                f"Unknown OBS category: {category}. "
                f"Valid categories: {[c.value for c in OBSCategory]}"
            )
        return self.CCF_TABLE[category]

    def _resolve_category(self, exposure: OBSExposure) -> OBSCategory:
        """Resolve the effective OBS category for an exposure.

        Applies the UCC override: if is_unconditionally_cancellable is True,
        the exposure is treated as UCC regardless of the stated category.

        Args:
            exposure: The OBS exposure to classify.

        Returns:
            The effective OBS category for CCF lookup.

        References:
            12 CFR 217.33(b) — Unconditionally cancellable commitments
            BCBS d424 CRE20.71 — UCC treatment
        """
        if exposure.is_unconditionally_cancellable:
            if exposure.obs_category != OBSCategory.UCC:
                logger.info(
                    "Exposure %s: overriding category %s to UCC "
                    "(is_unconditionally_cancellable=True) per 12 CFR 217.33(b)",
                    exposure.exposure_id,
                    exposure.obs_category.value,
                )
            return OBSCategory.UCC
        return exposure.obs_category

    def convert_single(self, exposure: OBSExposure) -> dict:
        """Convert a single OBS exposure to its credit-equivalent amount.

        Computes:
            undrawn = notional - drawn
            ccf = CCF_TABLE[effective_category]
            ead = drawn + (undrawn x ccf)

        Args:
            exposure: The OBS exposure to convert.

        Returns:
            Dictionary containing the conversion details:
              - exposure_id: Identifier
              - obs_category: Stated category
              - effective_category: Category after UCC override
              - notional: Notional amount ($M)
              - drawn: Drawn amount ($M)
              - undrawn: Undrawn amount ($M)
              - ccf: Applied credit conversion factor
              - ead: Credit-equivalent amount ($M)
              - rwa: 0.0 (set by caller if risk weight available)

        References:
            12 CFR 217.33 — Off-Balance Sheet Items
            BCBS d424 CRE20.69 — CEA computation
        """
        effective_category = self._resolve_category(exposure)
        ccf = self.get_ccf(effective_category)

        undrawn = exposure.notional_amount - exposure.drawn_amount
        ead = exposure.drawn_amount + (undrawn * ccf)

        logger.debug(
            "OBS %s: category=%s, effective=%s, notional=%.2f, "
            "drawn=%.2f, undrawn=%.2f, CCF=%.2f, EAD=%.2f",
            exposure.exposure_id,
            exposure.obs_category.value,
            effective_category.value,
            exposure.notional_amount,
            exposure.drawn_amount,
            undrawn,
            ccf,
            ead,
        )

        return {
            "exposure_id": exposure.exposure_id,
            "obs_category": exposure.obs_category.value,
            "effective_category": effective_category.value,
            "notional": exposure.notional_amount,
            "drawn": exposure.drawn_amount,
            "undrawn": undrawn,
            "ccf": ccf,
            "ead": ead,
            "rwa": 0.0,
            "counterparty_id": exposure.counterparty_id,
            "exposure_class": exposure.exposure_class,
        }

    def calculate(
        self,
        exposures: list[OBSExposure],
        risk_weight_func: Callable[[OBSExposure], float] | None = None,
    ) -> OBSResult:
        """Calculate credit-equivalent amounts for all OBS exposures.

        Processes each OBS exposure to determine its CCF, computes the
        credit-equivalent amount (CEA), and aggregates results by category
        and portfolio-wide.

        If a risk_weight_func is provided, RWA is computed as EAD x RW
        for each exposure. Otherwise, RWA is set to 0.

        Args:
            exposures: List of OBS exposures to process.
            risk_weight_func: Optional callable that takes an OBSExposure
                and returns the applicable risk weight (decimal). If None,
                RWA is not computed.

        Returns:
            Complete OBSResult with portfolio and per-category aggregates.

        References:
            12 CFR 217.33 — Off-Balance Sheet Items
            BCBS d424 CRE20.69-20.93 — Credit Conversion Factors
        """
        if not exposures:
            logger.warning("Empty exposure list provided to OBS CCF calculator")
            return OBSResult()

        logger.info(
            "Starting OBS CCF calculation for %d exposures", len(exposures)
        )

        details: list[dict] = []
        category_accumulators: dict[str, dict] = {}

        total_notional = 0.0
        total_drawn = 0.0
        total_undrawn = 0.0
        total_ead = 0.0
        total_rwa = 0.0

        for exposure in exposures:
            detail = self.convert_single(exposure)

            # Apply risk weight if function provided
            rwa = 0.0
            if risk_weight_func is not None:
                rw = risk_weight_func(exposure)
                rwa = detail["ead"] * rw
                detail["risk_weight"] = rw
                detail["rwa"] = rwa

            details.append(detail)

            # Accumulate totals
            total_notional += detail["notional"]
            total_drawn += detail["drawn"]
            total_undrawn += detail["undrawn"]
            total_ead += detail["ead"]
            total_rwa += rwa

            # Accumulate by category
            cat_key = detail["effective_category"]
            if cat_key not in category_accumulators:
                category_accumulators[cat_key] = {
                    "count": 0,
                    "notional": 0.0,
                    "drawn": 0.0,
                    "undrawn": 0.0,
                    "ead": 0.0,
                    "ccf": detail["ccf"],
                    "rwa": 0.0,
                }
            acc = category_accumulators[cat_key]
            acc["count"] += 1
            acc["notional"] += detail["notional"]
            acc["drawn"] += detail["drawn"]
            acc["undrawn"] += detail["undrawn"]
            acc["ead"] += detail["ead"]
            acc["rwa"] += rwa

        logger.info(
            "OBS CCF calculation complete: %d exposures, "
            "total_notional=%.2f, total_ead=%.2f, total_rwa=%.2f",
            len(exposures),
            total_notional,
            total_ead,
            total_rwa,
        )

        return OBSResult(
            total_notional=total_notional,
            total_drawn=total_drawn,
            total_undrawn=total_undrawn,
            total_ead=total_ead,
            total_rwa=total_rwa,
            exposures_by_category=category_accumulators,
            details=details,
        )

    def classify_commitment_by_maturity(
        self,
        original_maturity_years: float,
        is_unconditionally_cancellable: bool = False,
    ) -> OBSCategory:
        """Classify a generic commitment based on maturity and cancellability.

        Helper method to determine the appropriate OBS category for
        commitments that need maturity-based classification.

        Args:
            original_maturity_years: Original maturity in years.
            is_unconditionally_cancellable: Whether the commitment can be
                cancelled unconditionally at any time.

        Returns:
            The appropriate OBSCategory.

        References:
            12 CFR 217.33(b)-(e) — Commitment classification
            BCBS d424 CRE20.71-20.76 — Maturity-based CCFs
        """
        if is_unconditionally_cancellable:
            return OBSCategory.UCC
        if original_maturity_years > 1.0:
            return OBSCategory.COMMITMENT_GT_1Y
        return OBSCategory.COMMITMENT_LE_1Y
