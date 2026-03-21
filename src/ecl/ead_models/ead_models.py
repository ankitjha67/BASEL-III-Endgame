"""EAD Models — Exposure at Default calculators for ECL.

Implements credit conversion factors, undrawn commitment estimation,
and off-balance sheet exposure models.

All amounts in USD millions ($M).

References:
    - BCBS d350 §6.1-6.3: EAD estimation for ECL
    - BCBS d424 CRE32.22-32.26: IRB EAD
    - ERBA NPR pp. 130-140: SA-CR CCFs
    - ASC 326-20-30-6: CECL contractual term
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.ecl.ead_models.ead_params import (
    DEFAULT_DRAWDOWN_RATES,
    DEFAULT_PREPAYMENT_RATES,
    SA_CCF,
)


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class EADResult:
    """Result of EAD estimation.

    Reference: BCBS d350 §6.1.
    """
    drawn_amount: float
    undrawn_amount: float
    ccf: float
    credit_equivalent: float
    total_ead: float
    product_type: str = ""
    prepayment_adjusted: bool = False


# =========================================================================
#  CCF Model
# =========================================================================

class CCFModel:
    """Credit Conversion Factor model for off-balance sheet exposures.

    Maps exposure types to regulatory or internally-calibrated CCFs.

    Reference: ERBA NPR pp. 130-140, 12 CFR 217.33.
    """

    def __init__(
        self,
        ccf_schedule: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize CCF model.

        Args:
            ccf_schedule: Exposure type to CCF mapping.

        Reference: 12 CFR 217.33.
        """
        self.ccf_schedule = ccf_schedule or SA_CCF

    def get_ccf(self, exposure_type: str) -> float:
        """Look up CCF for an exposure type.

        Args:
            exposure_type: Off-balance sheet exposure category.

        Returns:
            CCF (0 to 1).

        Reference: ERBA NPR pp. 130-140.
        """
        return self.ccf_schedule.get(exposure_type, 0.40)

    def compute_credit_equivalent(
        self,
        notional: float,
        exposure_type: str,
    ) -> float:
        """Compute credit-equivalent amount from off-balance sheet notional.

        Credit equivalent = notional × CCF.

        Args:
            notional: Off-balance sheet notional ($M).
            exposure_type: For CCF lookup.

        Returns:
            Credit-equivalent amount ($M).

        Reference: 12 CFR 217.33.
        """
        ccf = self.get_ccf(exposure_type)
        return notional * ccf


class UndrawnCommitmentModel:
    """Undrawn commitment EAD model.

    Estimates EAD for revolving facilities as drawn + CCF × undrawn.

    Reference: BCBS d350 §6.2, BCBS d424 CRE32.22.
    """

    def __init__(
        self,
        ccf_model: Optional[CCFModel] = None,
        drawdown_rates: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize undrawn commitment model.

        Args:
            ccf_model: CCF model for off-balance sheet conversion.
            drawdown_rates: Product-specific drawdown rates.

        Reference: BCBS d350 §6.2.
        """
        self.ccf_model = ccf_model or CCFModel()
        self.drawdown_rates = drawdown_rates or DEFAULT_DRAWDOWN_RATES

    def compute_ead(
        self,
        drawn: float,
        undrawn: float,
        product_type: str = "commitments_gte_1y",
        use_drawdown_rate: bool = False,
    ) -> EADResult:
        """Compute EAD for a revolving facility.

        EAD = drawn + CCF × undrawn

        If use_drawdown_rate, uses internal drawdown rates instead of
        regulatory CCFs.

        Args:
            drawn: Current drawn amount ($M).
            undrawn: Undrawn commitment amount ($M).
            product_type: For CCF/drawdown lookup.
            use_drawdown_rate: Use internal drawdown rates.

        Returns:
            EADResult with all components.

        Reference: BCBS d350 §6.2.
        """
        if use_drawdown_rate:
            ccf = self.drawdown_rates.get(product_type, 0.60)
        else:
            ccf = self.ccf_model.get_ccf(product_type)

        credit_equivalent = undrawn * ccf
        total_ead = drawn + credit_equivalent

        return EADResult(
            drawn_amount=drawn,
            undrawn_amount=undrawn,
            ccf=ccf,
            credit_equivalent=credit_equivalent,
            total_ead=total_ead,
            product_type=product_type,
        )


class OffBalanceSheetModel:
    """Off-balance sheet exposure model.

    Handles guarantees, letters of credit, derivatives, and other
    off-balance sheet items.

    Reference: BCBS d350 §6.3, 12 CFR 217.33.
    """

    def __init__(
        self,
        ccf_model: Optional[CCFModel] = None,
    ) -> None:
        """Initialize off-balance sheet model.

        Reference: 12 CFR 217.33.
        """
        self.ccf_model = ccf_model or CCFModel()

    def compute_ead(
        self,
        notional: float,
        exposure_type: str = "other_commitments",
    ) -> EADResult:
        """Compute EAD for an off-balance sheet exposure.

        EAD = notional × CCF (no drawn component).

        Args:
            notional: Notional/nominal amount ($M).
            exposure_type: Off-balance sheet category.

        Returns:
            EADResult.

        Reference: 12 CFR 217.33.
        """
        ccf = self.ccf_model.get_ccf(exposure_type)
        credit_equivalent = notional * ccf

        return EADResult(
            drawn_amount=0.0,
            undrawn_amount=notional,
            ccf=ccf,
            credit_equivalent=credit_equivalent,
            total_ead=credit_equivalent,
            product_type=exposure_type,
        )


class EADModel:
    """Main EAD model combining all sub-models.

    Provides a unified interface for EAD estimation across on-balance
    sheet, revolving, and off-balance sheet exposures.

    Reference: BCBS d350 §6.1-6.3.
    """

    def __init__(
        self,
        ccf_model: Optional[CCFModel] = None,
        commitment_model: Optional[UndrawnCommitmentModel] = None,
        obs_model: Optional[OffBalanceSheetModel] = None,
        prepayment_rates: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize EAD model.

        Reference: SR 11-7 §III.
        """
        self.ccf_model = ccf_model or CCFModel()
        self.commitment_model = commitment_model or UndrawnCommitmentModel(
            ccf_model=self.ccf_model
        )
        self.obs_model = obs_model or OffBalanceSheetModel(
            ccf_model=self.ccf_model
        )
        self.prepayment_rates = prepayment_rates or DEFAULT_PREPAYMENT_RATES

    def compute_ead(
        self,
        drawn: float = 0.0,
        undrawn: float = 0.0,
        product_type: str = "commitments_gte_1y",
        is_off_balance_sheet: bool = False,
        remaining_maturity_years: float = 1.0,
        apply_prepayment: bool = False,
    ) -> EADResult:
        """Compute EAD through the full model pipeline.

        Args:
            drawn: Current drawn amount ($M).
            undrawn: Undrawn or notional amount ($M).
            product_type: Product/exposure category.
            is_off_balance_sheet: Pure off-balance sheet (no drawn).
            remaining_maturity_years: For prepayment adjustment.
            apply_prepayment: Apply prepayment adjustment.

        Returns:
            EADResult with all components.

        Reference: BCBS d350 §6.1-6.3.
        """
        if is_off_balance_sheet:
            result = self.obs_model.compute_ead(undrawn, product_type)
        elif undrawn > 0:
            result = self.commitment_model.compute_ead(
                drawn, undrawn, product_type
            )
        else:
            result = EADResult(
                drawn_amount=drawn,
                undrawn_amount=0.0,
                ccf=0.0,
                credit_equivalent=0.0,
                total_ead=drawn,
                product_type=product_type,
            )

        # Prepayment adjustment
        if apply_prepayment and remaining_maturity_years > 0:
            annual_prepay = self.prepayment_rates.get(product_type, 0.05)
            prepay_factor = max(
                0.0,
                1.0 - annual_prepay * min(remaining_maturity_years, 5.0)
            )
            result = EADResult(
                drawn_amount=result.drawn_amount,
                undrawn_amount=result.undrawn_amount,
                ccf=result.ccf,
                credit_equivalent=result.credit_equivalent,
                total_ead=result.total_ead * prepay_factor,
                product_type=result.product_type,
                prepayment_adjusted=True,
            )

        return result
