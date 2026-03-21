"""Credit Risk Mitigation (CRM) — Comprehensive & Substitution Approaches.

Implements eligible collateral recognition, supervisory haircuts, and guarantee
substitution per Basel III Endgame rules (MAR22 / CRE22).

Key formulas
------------
Comprehensive Approach (collateral):
    E* = max(0, E * (1 + He) - C * (1 - Hc - Hfx))

Substitution Approach (guarantees / credit derivatives):
    Covered portion uses guarantor risk weight; uncovered portion keeps
    original obligor risk weight.

References
----------
- CRE22: Credit risk mitigation — overview
- CRE22.51-22.75: Comprehensive approach
- CRE22.76-22.89: Substitution approach for guarantees / credit derivatives
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# ============================================================================
#  Constants — Supervisory Haircuts
# ============================================================================

SUPERVISORY_HAIRCUTS: dict[str, float] = {
    # Cash
    "cash": 0.00,
    # Gold
    "gold": 0.15,
    # Sovereign securities by residual maturity
    "sovereign_residual_1y": 0.005,
    "sovereign_residual_5y": 0.02,
    "sovereign_residual_10y": 0.04,
    "sovereign_residual_10y_plus": 0.06,
    # Investment-grade corporate bonds by residual maturity
    "corporate_ig_residual_1y": 0.01,
    "corporate_ig_residual_5y": 0.04,
    "corporate_ig_residual_10y": 0.06,
    "corporate_ig_residual_10y_plus": 0.10,
    # Equities
    "equity_main_index": 0.15,
    "equity_other": 0.25,
    # Mutual funds — highest haircut of underlying assets
    "mutual_fund": 0.20,
}

# FX mismatch add-on per CRE22.62
CURRENCY_MISMATCH_HAIRCUT: float = 0.08

# Holding-period scaling: standard = 10 business days.
# For repo-style transactions the standard period is 5 days.
STANDARD_HOLDING_PERIOD_DAYS: int = 10
REPO_HOLDING_PERIOD_DAYS: int = 5


# ============================================================================
#  Enumerations
# ============================================================================


class CollateralType(str, Enum):
    """Types of eligible financial collateral per CRE22.39-22.45."""

    CASH = "cash"
    GOLD = "gold"
    SOVEREIGN_DEBT = "sovereign_debt"
    CORPORATE_IG_BOND = "corporate_ig_bond"
    EQUITY_MAIN_INDEX = "equity_main_index"
    EQUITY_OTHER = "equity_other"
    MUTUAL_FUND = "mutual_fund"


class GuarantorType(str, Enum):
    """Eligible guarantor types per CRE22.76."""

    SOVEREIGN = "sovereign"
    PSE = "pse"
    BANK = "bank"
    CORPORATE_IG = "corporate_ig"


class ExposureType(str, Enum):
    """Broad exposure categories for CRM eligibility."""

    ON_BALANCE_SHEET = "on_balance_sheet"
    OFF_BALANCE_SHEET = "off_balance_sheet"
    REPO_STYLE = "repo_style"
    OTC_DERIVATIVE = "otc_derivative"


# ============================================================================
#  Pydantic Models
# ============================================================================


class CRMCollateral(BaseModel):
    """A single piece of eligible financial collateral.

    Attributes
    ----------
    collateral_id : str
        Unique identifier for the collateral.
    collateral_type : CollateralType
        Category of collateral.
    market_value : float
        Current market value of the collateral (must be > 0).
    currency : str
        ISO 4217 currency code of the collateral.
    residual_maturity_years : float | None
        Residual maturity in years (required for debt securities).
    is_main_index : bool
        Whether equity is part of a main index.
    holding_period_days : int
        Holding period used for haircut scaling.
    """

    collateral_id: str
    collateral_type: CollateralType
    market_value: float = Field(gt=0, description="Current market value")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    residual_maturity_years: Optional[float] = Field(
        default=None, ge=0, description="Residual maturity in years"
    )
    is_main_index: bool = Field(
        default=False, description="Equity listed on a main index"
    )
    holding_period_days: int = Field(
        default=STANDARD_HOLDING_PERIOD_DAYS,
        gt=0,
        description="Holding period for haircut scaling",
    )

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()


class CRMExposure(BaseModel):
    """An exposure subject to credit risk mitigation.

    Attributes
    ----------
    exposure_id : str
        Unique identifier for the exposure.
    exposure_type : ExposureType
        Category of exposure.
    exposure_amount : float
        Gross exposure amount (E).
    risk_weight : float
        Original risk weight of the obligor (0-1 scale or percentage).
    currency : str
        ISO 4217 currency code of the exposure.
    exposure_haircut : float
        Haircut applied to the exposure side (He); typically 0 except for
        repo-style transactions.
    """

    exposure_id: str
    exposure_type: ExposureType = ExposureType.ON_BALANCE_SHEET
    exposure_amount: float = Field(ge=0, description="Gross exposure (E)")
    risk_weight: float = Field(ge=0, description="Obligor risk weight")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    exposure_haircut: float = Field(
        default=0.0, ge=0, description="Exposure-side haircut (He)"
    )

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()


class CRMGuarantee(BaseModel):
    """A guarantee or credit derivative providing credit protection.

    Attributes
    ----------
    guarantee_id : str
        Unique identifier.
    guarantor_type : GuarantorType
        Category of guarantor.
    guarantor_risk_weight : float
        Risk weight applicable to the guarantor.
    covered_amount : float
        Nominal amount of the guarantee (protection coverage).
    currency : str
        ISO 4217 currency code.
    maturity_mismatch_factor : float
        Adjustment factor for maturity mismatch (0 < factor <= 1).
        Set to 1.0 when maturities match.
    """

    guarantee_id: str
    guarantor_type: GuarantorType
    guarantor_risk_weight: float = Field(ge=0)
    covered_amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    maturity_mismatch_factor: float = Field(default=1.0, gt=0, le=1.0)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _check_rw_consistency(self) -> "CRMGuarantee":
        if self.guarantor_type == GuarantorType.SOVEREIGN and self.guarantor_risk_weight > 0.20:
            logger.warning(
                "Sovereign guarantor %s has unusually high risk weight %.2f%%",
                self.guarantee_id,
                self.guarantor_risk_weight * 100,
            )
        return self


class CRMResult(BaseModel):
    """Result of CRM adjustment for a single exposure.

    Attributes
    ----------
    exposure_id : str
        Identifier of the exposure.
    original_ead : float
        Exposure before CRM.
    adjusted_ead : float
        Exposure after CRM (E*).
    collateral_benefit : float
        Reduction from collateral.
    guarantee_benefit : float
        Reduction from guarantee / credit derivative.
    effective_risk_weight : float
        Blended risk weight after substitution.
    details : dict
        Intermediate calculation details.
    """

    exposure_id: str
    original_ead: float
    adjusted_ead: float
    collateral_benefit: float = 0.0
    guarantee_benefit: float = 0.0
    effective_risk_weight: float = 0.0
    details: dict = Field(default_factory=dict)


# ============================================================================
#  Haircut helpers
# ============================================================================


def _residual_maturity_bucket(years: float | None) -> str:
    """Map residual maturity in years to a haircut bucket suffix."""
    if years is None:
        return "residual_5y"  # default mid-bucket
    if years <= 1.0:
        return "residual_1y"
    if years <= 5.0:
        return "residual_5y"
    if years <= 10.0:
        return "residual_10y"
    return "residual_10y_plus"


def collateral_haircut_key(collateral: CRMCollateral) -> str:
    """Derive the SUPERVISORY_HAIRCUTS key for a given collateral piece."""
    ctype = collateral.collateral_type

    if ctype == CollateralType.CASH:
        return "cash"
    if ctype == CollateralType.GOLD:
        return "gold"
    if ctype == CollateralType.SOVEREIGN_DEBT:
        bucket = _residual_maturity_bucket(collateral.residual_maturity_years)
        return f"sovereign_{bucket}"
    if ctype == CollateralType.CORPORATE_IG_BOND:
        bucket = _residual_maturity_bucket(collateral.residual_maturity_years)
        return f"corporate_ig_{bucket}"
    if ctype == CollateralType.EQUITY_MAIN_INDEX:
        return "equity_main_index"
    if ctype == CollateralType.EQUITY_OTHER:
        return "equity_other"
    if ctype == CollateralType.MUTUAL_FUND:
        return "mutual_fund"

    raise ValueError(f"Unknown collateral type: {ctype}")


def get_collateral_haircut(collateral: CRMCollateral) -> float:
    """Return the supervisory haircut Hc for a collateral piece.

    The base haircut is scaled for non-standard holding periods using:
        H_adj = H_10 * sqrt(N / 10)
    where N is the actual holding period in business days.
    """
    key = collateral_haircut_key(collateral)
    base_haircut = SUPERVISORY_HAIRCUTS[key]

    # Scale for holding period
    if collateral.holding_period_days != STANDARD_HOLDING_PERIOD_DAYS:
        scaling = np.sqrt(
            collateral.holding_period_days / STANDARD_HOLDING_PERIOD_DAYS
        )
        return float(base_haircut * scaling)

    return base_haircut


def get_fx_haircut(
    exposure_currency: str, collateral_currency: str
) -> float:
    """Return FX mismatch haircut Hfx.

    Returns CURRENCY_MISMATCH_HAIRCUT (8 %) if currencies differ, else 0.
    """
    if exposure_currency.upper() != collateral_currency.upper():
        return CURRENCY_MISMATCH_HAIRCUT
    return 0.0


# ============================================================================
#  Maturity mismatch helpers
# ============================================================================


def maturity_mismatch_adjustment(
    protection_residual_years: float,
    exposure_residual_years: float,
) -> float:
    """Compute the maturity-mismatch adjustment factor per CRE22.69.

    Parameters
    ----------
    protection_residual_years : float
        Residual maturity of the protection (guarantee / collateral).
    exposure_residual_years : float
        Residual maturity of the exposure.

    Returns
    -------
    float
        Factor in (0, 1].  Returns 1.0 if no mismatch.  Returns 0.0 if
        protection maturity < 1 year (protection ineligible).
    """
    if protection_residual_years >= exposure_residual_years:
        return 1.0

    # Protection with residual maturity < 1 year is not eligible when
    # there is a maturity mismatch
    if protection_residual_years < 1.0:
        return 0.0

    t = protection_residual_years
    big_t = exposure_residual_years
    # CRE22.69: factor = (t - 0.25) / (T - 0.25), with t >= 1
    factor = (t - 0.25) / (big_t - 0.25) if big_t > 0.25 else 0.0
    return max(0.0, min(factor, 1.0))


# ============================================================================
#  CRM Calculator
# ============================================================================


class CRMCalculator:
    """Credit Risk Mitigation calculator.

    Applies the *Comprehensive Approach* for eligible financial collateral
    and the *Substitution Approach* for guarantees / credit derivatives,
    following Basel III Endgame rules.

    Usage
    -----
    >>> calc = CRMCalculator()
    >>> result = calc.adjusted_ead(exposure, collateral=collateral)
    >>> result.adjusted_ead
    85000.0
    """

    # ------------------------------------------------------------------
    #  Comprehensive Approach — Collateral
    # ------------------------------------------------------------------

    def apply_collateral(
        self,
        exposure: CRMExposure,
        collateral: CRMCollateral,
    ) -> float:
        """Compute adjusted exposure E* using supervisory haircuts.

        E* = max(0, E * (1 + He) - C * (1 - Hc - Hfx))

        Parameters
        ----------
        exposure : CRMExposure
            The exposure to be mitigated.
        collateral : CRMCollateral
            Eligible financial collateral.

        Returns
        -------
        float
            Adjusted exposure E*.
        """
        e = exposure.exposure_amount
        he = exposure.exposure_haircut
        c = collateral.market_value
        hc = get_collateral_haircut(collateral)
        hfx = get_fx_haircut(exposure.currency, collateral.currency)

        e_star = e * (1.0 + he) - c * (1.0 - hc - hfx)
        e_star = max(0.0, e_star)

        logger.debug(
            "Collateral CRM: E=%.2f, He=%.4f, C=%.2f, Hc=%.4f, Hfx=%.4f -> E*=%.2f",
            e, he, c, hc, hfx, e_star,
        )
        return e_star

    def apply_collateral_multiple(
        self,
        exposure: CRMExposure,
        collaterals: list[CRMCollateral],
    ) -> float:
        """Apply multiple collateral pieces sequentially.

        For multiple pieces of collateral, the adjusted exposure is computed
        iteratively: each piece reduces the remaining exposure.

        Parameters
        ----------
        exposure : CRMExposure
            The exposure to be mitigated.
        collaterals : list[CRMCollateral]
            List of eligible collateral pieces.

        Returns
        -------
        float
            Final adjusted exposure after all collateral is applied.
        """
        remaining = exposure.exposure_amount
        he = exposure.exposure_haircut

        for coll in collaterals:
            hc = get_collateral_haircut(coll)
            hfx = get_fx_haircut(exposure.currency, coll.currency)
            c_adj = coll.market_value * (1.0 - hc - hfx)
            remaining = remaining * (1.0 + he) - c_adj
            remaining = max(0.0, remaining)
            # Reset He after first application (avoids double-counting)
            he = 0.0

        return remaining

    # ------------------------------------------------------------------
    #  Substitution Approach — Guarantees / Credit Derivatives
    # ------------------------------------------------------------------

    def apply_guarantee(
        self,
        exposure: CRMExposure,
        guarantee: CRMGuarantee,
    ) -> float:
        """Compute the guarantee benefit via the substitution approach.

        The covered portion of the exposure adopts the guarantor's risk
        weight.  The uncovered portion retains the original obligor's
        risk weight.

        Parameters
        ----------
        exposure : CRMExposure
            Exposure to be mitigated.
        guarantee : CRMGuarantee
            Guarantee or credit derivative.

        Returns
        -------
        float
            Effective (blended) risk-weighted amount after substitution.
        """
        e = exposure.exposure_amount
        rw_obligor = exposure.risk_weight
        rw_guarantor = guarantee.guarantor_risk_weight

        # FX mismatch reduces effective coverage
        fx_factor = 1.0
        if exposure.currency.upper() != guarantee.currency.upper():
            fx_factor = 1.0 - CURRENCY_MISMATCH_HAIRCUT

        effective_coverage = (
            guarantee.covered_amount
            * guarantee.maturity_mismatch_factor
            * fx_factor
        )
        effective_coverage = min(effective_coverage, e)

        uncovered = e - effective_coverage

        rwa_covered = effective_coverage * rw_guarantor
        rwa_uncovered = uncovered * rw_obligor
        total_rwa = rwa_covered + rwa_uncovered

        logger.debug(
            "Guarantee CRM: E=%.2f, covered=%.2f, rw_g=%.4f, rw_o=%.4f -> RWA=%.2f",
            e, effective_coverage, rw_guarantor, rw_obligor, total_rwa,
        )
        return total_rwa

    def effective_risk_weight_after_guarantee(
        self,
        exposure: CRMExposure,
        guarantee: CRMGuarantee,
    ) -> float:
        """Return the blended effective risk weight after substitution.

        Returns
        -------
        float
            Weighted-average risk weight across covered and uncovered portions.
        """
        total_rwa = self.apply_guarantee(exposure, guarantee)
        if exposure.exposure_amount <= 0:
            return exposure.risk_weight
        return total_rwa / exposure.exposure_amount

    # ------------------------------------------------------------------
    #  Combined CRM
    # ------------------------------------------------------------------

    def adjusted_ead(
        self,
        exposure: CRMExposure,
        collateral: Optional[CRMCollateral | list[CRMCollateral]] = None,
        guarantee: Optional[CRMGuarantee | list[CRMGuarantee]] = None,
    ) -> CRMResult:
        """Calculate fully adjusted EAD after all CRM techniques.

        Applies collateral first (reduces EAD), then guarantees (reduces
        effective risk weight on the remaining exposure).

        Parameters
        ----------
        exposure : CRMExposure
            Original exposure.
        collateral : CRMCollateral | list | None
            One or more pieces of eligible collateral.
        guarantee : CRMGuarantee | list | None
            One or more guarantees / credit derivatives.

        Returns
        -------
        CRMResult
            Full result including adjusted EAD, benefits, and details.
        """
        original_ead = exposure.exposure_amount
        details: dict = {"original_ead": original_ead}

        # --- Step 1: apply collateral ---
        collateral_benefit = 0.0
        e_after_collateral = original_ead

        if collateral is not None:
            collaterals = (
                collateral if isinstance(collateral, list) else [collateral]
            )
            e_after_collateral = self.apply_collateral_multiple(
                exposure, collaterals
            )
            collateral_benefit = original_ead - e_after_collateral
            details["collateral_count"] = len(collaterals)
            details["e_after_collateral"] = e_after_collateral
            details["haircuts_applied"] = [
                {
                    "id": c.collateral_id,
                    "type": c.collateral_type.value,
                    "value": c.market_value,
                    "haircut": get_collateral_haircut(c),
                    "fx_haircut": get_fx_haircut(
                        exposure.currency, c.currency
                    ),
                }
                for c in collaterals
            ]

        # --- Step 2: apply guarantees (substitution) ---
        guarantee_benefit = 0.0
        effective_rw = exposure.risk_weight

        if guarantee is not None:
            guarantees = (
                guarantee if isinstance(guarantee, list) else [guarantee]
            )

            # Build a proxy exposure reflecting post-collateral EAD
            post_coll_exposure = CRMExposure(
                exposure_id=exposure.exposure_id,
                exposure_type=exposure.exposure_type,
                exposure_amount=e_after_collateral,
                risk_weight=exposure.risk_weight,
                currency=exposure.currency,
                exposure_haircut=0.0,  # already applied
            )

            # For multiple guarantees, apply sequentially — each covers
            # a portion of the remaining exposure.
            remaining_exposure = e_after_collateral
            total_rwa = 0.0

            for g in guarantees:
                if remaining_exposure <= 0:
                    break

                fx_factor = 1.0
                if exposure.currency.upper() != g.currency.upper():
                    fx_factor = 1.0 - CURRENCY_MISMATCH_HAIRCUT

                eff_coverage = min(
                    g.covered_amount * g.maturity_mismatch_factor * fx_factor,
                    remaining_exposure,
                )

                total_rwa += eff_coverage * g.guarantor_risk_weight
                remaining_exposure -= eff_coverage

            # Add uncovered portion at obligor risk weight
            total_rwa += remaining_exposure * exposure.risk_weight

            # Effective (blended) risk weight
            if e_after_collateral > 0:
                effective_rw = total_rwa / e_after_collateral
            else:
                effective_rw = 0.0

            guarantee_benefit = (
                e_after_collateral * exposure.risk_weight - total_rwa
            )
            guarantee_benefit = max(0.0, guarantee_benefit)

            details["guarantee_count"] = len(guarantees)
            details["effective_risk_weight"] = effective_rw
            details["guarantee_details"] = [
                {
                    "id": g.guarantee_id,
                    "type": g.guarantor_type.value,
                    "rw": g.guarantor_risk_weight,
                    "coverage": g.covered_amount,
                    "maturity_factor": g.maturity_mismatch_factor,
                }
                for g in guarantees
            ]

        adjusted_ead = e_after_collateral
        details["adjusted_ead"] = adjusted_ead
        details["effective_risk_weight"] = effective_rw

        return CRMResult(
            exposure_id=exposure.exposure_id,
            original_ead=original_ead,
            adjusted_ead=adjusted_ead,
            collateral_benefit=collateral_benefit,
            guarantee_benefit=guarantee_benefit,
            effective_risk_weight=effective_rw,
            details=details,
        )

    # ------------------------------------------------------------------
    #  Batch processing
    # ------------------------------------------------------------------

    def batch_adjusted_ead(
        self,
        exposures: list[CRMExposure],
        collateral_map: dict[str, list[CRMCollateral]] | None = None,
        guarantee_map: dict[str, list[CRMGuarantee]] | None = None,
    ) -> list[CRMResult]:
        """Process a batch of exposures through CRM.

        Parameters
        ----------
        exposures : list[CRMExposure]
            Exposures to process.
        collateral_map : dict | None
            Mapping from exposure_id to list of collateral pieces.
        guarantee_map : dict | None
            Mapping from exposure_id to list of guarantees.

        Returns
        -------
        list[CRMResult]
            Results for each exposure.
        """
        collateral_map = collateral_map or {}
        guarantee_map = guarantee_map or {}
        results: list[CRMResult] = []

        for exp in exposures:
            colls = collateral_map.get(exp.exposure_id)
            guars = guarantee_map.get(exp.exposure_id)
            result = self.adjusted_ead(
                exposure=exp,
                collateral=colls if colls else None,
                guarantee=guars if guars else None,
            )
            results.append(result)

        return results

    # ------------------------------------------------------------------
    #  Reporting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def summarize(results: list[CRMResult]) -> dict:
        """Produce aggregate summary statistics over CRM results.

        Returns
        -------
        dict
            Dictionary with totals and averages.
        """
        if not results:
            return {
                "count": 0,
                "total_original_ead": 0.0,
                "total_adjusted_ead": 0.0,
                "total_collateral_benefit": 0.0,
                "total_guarantee_benefit": 0.0,
                "avg_effective_rw": 0.0,
            }

        total_original = sum(r.original_ead for r in results)
        total_adjusted = sum(r.adjusted_ead for r in results)
        total_coll = sum(r.collateral_benefit for r in results)
        total_guar = sum(r.guarantee_benefit for r in results)

        # Weighted-average effective risk weight
        if total_adjusted > 0:
            avg_rw = sum(
                r.effective_risk_weight * r.adjusted_ead for r in results
            ) / total_adjusted
        else:
            avg_rw = 0.0

        return {
            "count": len(results),
            "total_original_ead": round(total_original, 2),
            "total_adjusted_ead": round(total_adjusted, 2),
            "total_collateral_benefit": round(total_coll, 2),
            "total_guarantee_benefit": round(total_guar, 2),
            "avg_effective_rw": round(avg_rw, 6),
        }
