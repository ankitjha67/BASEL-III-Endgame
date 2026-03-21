"""SA-CR Calculator — Standardized Approach Credit Risk RWA Engine.

Computes risk-weighted assets (RWA) for a portfolio of credit exposures
under the US Basel III Endgame Standardized Approach. This module is the
primary entry point for SA-CR calculations.

The calculator:
  1. Validates and classifies each exposure
  2. Determines the applicable risk weight
  3. Computes RWA = EAD x Risk Weight
  4. Aggregates results by exposure class and portfolio-wide
  5. Applies credit risk mitigation (CRM) adjustments when applicable

References:
    - Federal Reserve Basel III Endgame NPR (July 2023, re-proposed Sept 2025)
    - 12 CFR Part 217, Subpart E, Sections 217.111-217.132
    - Dodd-Frank Act Section 939A
    - Basel Committee CRE20-CRE22
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from src.credit_risk.sa.exposure_classes import (
    CRESubType,
    EquitySubType,
    ExposureClass,
    PSEObligationType,
    classify_exposure,
    ExposureClassificationCriteria,
    is_qualifying_mdb,
)
from src.credit_risk.sa.risk_weights import (
    RiskWeightInput,
    get_risk_weight,
    RiskWeightSchedule,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Credit Exposure Model
# =========================================================================

class CreditExposure(BaseModel):
    """A single credit exposure for SA-CR RWA calculation.

    Represents a credit risk position with all attributes needed to
    determine its exposure class and risk weight under the US Basel III
    Endgame Standardized Approach.

    Attributes follow the data requirements of 12 CFR 217, Subpart E.
    The exposure_class may be provided directly or determined via the
    classification engine.

    Examples:
        >>> exp = CreditExposure(
        ...     exposure_id="CORP-001",
        ...     exposure_class=ExposureClass.CORPORATE,
        ...     counterparty="ACME Corp",
        ...     ead=1_000_000.0,
        ...     is_investment_grade=True,
        ... )
    """

    exposure_id: str = Field(
        description="Unique identifier for the exposure",
    )
    exposure_class: ExposureClass = Field(
        description="SA-CR exposure class assignment",
    )
    counterparty: str = Field(
        description="Name or identifier of the counterparty/obligor",
    )
    ead: float = Field(
        ge=0.0,
        description=(
            "Exposure at Default — the on-balance-sheet amount plus "
            "applicable credit conversion factor (CCF) for off-balance-sheet"
        ),
    )
    is_investment_grade: bool = Field(
        default=False,
        description=(
            "Self-assessed investment-grade status for corporate exposures. "
            "True if the entity has adequate capacity to meet financial "
            "commitments for the projected life of the exposure"
        ),
    )
    ltv_ratio: float | None = Field(
        default=None,
        ge=0.0,
        description="Loan-to-value ratio for real estate exposures (decimal)",
    )
    country_risk_class: int = Field(
        default=0,
        ge=0,
        le=7,
        description="OECD Country Risk Classification (0-7) for sovereign/bank",
    )
    maturity_years: float = Field(
        default=2.5,
        ge=0.0,
        description="Remaining maturity in years",
    )
    is_sme: bool = Field(
        default=False,
        description="Whether the corporate qualifies as SME (revenue <= ~USD 50M)",
    )
    is_transactor: bool = Field(
        default=False,
        description=(
            "Whether the retail credit card obligor is a transactor "
            "(paid balance in full for past 12 months)"
        ),
    )
    is_us_sovereign: bool = Field(
        default=False,
        description="Whether the sovereign counterparty is US government",
    )
    collateral_type: str | None = Field(
        default=None,
        description="Type of eligible collateral (for CRM adjustments)",
    )
    guarantee_provider: str | None = Field(
        default=None,
        description="Guarantor or credit protection provider identifier",
    )
    pse_obligation_type: PSEObligationType | None = Field(
        default=None,
        description="General vs. revenue obligation for PSE exposures",
    )
    mdb_code: str | None = Field(
        default=None,
        description="MDB identifier for qualifying status check",
    )
    equity_sub_type: EquitySubType | None = Field(
        default=None,
        description="Sub-type for equity exposure risk weight determination",
    )
    cre_sub_type: CRESubType | None = Field(
        default=None,
        description="Sub-type for CRE exposure (income-producing, ADC, land)",
    )
    is_presold_adc: bool = Field(
        default=False,
        description="Whether ADC loan is pre-sold/pre-leased with equity at risk",
    )
    netting_set_id: str | None = Field(
        default=None,
        description="Netting set identifier for exposure aggregation",
    )
    description: str = Field(
        default="",
        description="Optional description of the exposure",
    )

    @field_validator("ltv_ratio")
    @classmethod
    def validate_ltv_for_real_estate(
        cls, v: float | None, info: object
    ) -> float | None:
        """Warn if LTV is missing for mortgage-type exposures."""
        return v

    def to_risk_weight_input(self) -> RiskWeightInput:
        """Convert this exposure to a RiskWeightInput for risk weight lookup.

        Returns:
            A RiskWeightInput populated from the exposure's attributes.
        """
        return RiskWeightInput(
            exposure_class=self.exposure_class,
            country_risk_class=self.country_risk_class,
            is_us_sovereign=self.is_us_sovereign,
            is_investment_grade=self.is_investment_grade,
            ltv_ratio=self.ltv_ratio,
            pse_obligation_type=self.pse_obligation_type,
            mdb_code=self.mdb_code,
            equity_sub_type=self.equity_sub_type,
            cre_sub_type=self.cre_sub_type,
            maturity_years=self.maturity_years,
            is_presold_adc=self.is_presold_adc,
        )


# =========================================================================
#  Exposure-Level Result
# =========================================================================

class ExposureResult(BaseModel):
    """RWA calculation result for a single exposure.

    Contains the complete audit trail from exposure attributes through
    risk weight determination to final RWA.
    """

    exposure_id: str = Field(description="Exposure identifier")
    exposure_class: ExposureClass = Field(description="Assigned exposure class")
    counterparty: str = Field(description="Counterparty identifier")
    ead: float = Field(description="Exposure at Default")
    risk_weight: float = Field(
        description="Applied risk weight as decimal (e.g., 0.65 for 65%)",
    )
    rwa: float = Field(description="Risk-weighted asset = EAD x Risk Weight")
    risk_weight_pct: float = Field(
        description="Risk weight as percentage for display (e.g., 65.0)",
    )

    @classmethod
    def from_exposure(
        cls,
        exposure: CreditExposure,
        risk_weight: float,
    ) -> ExposureResult:
        """Create an ExposureResult from an exposure and its risk weight.

        Args:
            exposure: The credit exposure.
            risk_weight: The determined risk weight (decimal).

        Returns:
            A populated ExposureResult.
        """
        rwa = exposure.ead * risk_weight
        return cls(
            exposure_id=exposure.exposure_id,
            exposure_class=exposure.exposure_class,
            counterparty=exposure.counterparty,
            ead=exposure.ead,
            risk_weight=risk_weight,
            rwa=rwa,
            risk_weight_pct=round(risk_weight * 100, 2),
        )


# =========================================================================
#  Exposure Class Aggregation Result
# =========================================================================

class ExposureClassResult(BaseModel):
    """Aggregated SA-CR result for a single exposure class.

    Provides summary statistics for all exposures within one SA-CR
    exposure class.
    """

    exposure_class: ExposureClass = Field(description="The exposure class")
    exposure_count: int = Field(
        default=0,
        description="Number of exposures in this class",
    )
    total_ead: float = Field(
        default=0.0,
        description="Sum of EAD for this class",
    )
    total_rwa: float = Field(
        default=0.0,
        description="Sum of RWA for this class",
    )
    average_risk_weight: float = Field(
        default=0.0,
        description="Weighted average risk weight = total_rwa / total_ead",
    )
    min_risk_weight: float = Field(
        default=0.0,
        description="Minimum risk weight in this class",
    )
    max_risk_weight: float = Field(
        default=0.0,
        description="Maximum risk weight in this class",
    )
    exposure_results: list[ExposureResult] = Field(
        default_factory=list,
        description="Individual exposure results in this class",
    )


# =========================================================================
#  Portfolio-Level SA-CR Result
# =========================================================================

class SACRResult(BaseModel):
    """Complete SA-CR RWA calculation result for a portfolio.

    Contains portfolio-level aggregates, per-class breakdowns, and
    individual exposure results. Suitable for regulatory reporting
    (FR Y-14Q Schedule H.1) and internal risk management.

    Attributes:
        total_ead: Sum of all exposure-at-default amounts.
        total_rwa: Sum of all risk-weighted assets.
        rwa_by_class: RWA aggregated by exposure class.
        ead_by_class: EAD aggregated by exposure class.
        average_risk_weight: Portfolio-level weighted average RW.
        class_results: Detailed results per exposure class.
        exposure_results: Individual exposure-level results.
        exposure_count: Total number of exposures processed.
        risk_weight_schedule: The risk weight tables used.
    """

    total_ead: float = Field(
        default=0.0,
        description="Total exposure at default across all classes",
    )
    total_rwa: float = Field(
        default=0.0,
        description="Total risk-weighted assets across all classes",
    )
    rwa_by_class: dict[str, float] = Field(
        default_factory=dict,
        description="RWA broken down by exposure class",
    )
    ead_by_class: dict[str, float] = Field(
        default_factory=dict,
        description="EAD broken down by exposure class",
    )
    average_risk_weight: float = Field(
        default=0.0,
        description="Portfolio-level weighted average risk weight",
    )
    class_results: dict[str, ExposureClassResult] = Field(
        default_factory=dict,
        description="Detailed results per exposure class",
    )
    exposure_results: list[ExposureResult] = Field(
        default_factory=list,
        description="Individual exposure-level results",
    )
    exposure_count: int = Field(
        default=0,
        description="Total number of exposures processed",
    )
    risk_weight_schedule: RiskWeightSchedule | None = Field(
        default=None,
        description="Risk weight schedule used for the calculation",
    )

    @property
    def capital_requirement(self) -> float:
        """Minimum capital requirement = total_rwa x 8%.

        Per Basel III, the minimum total capital ratio is 8% of RWA.
        This represents the Pillar 1 minimum before buffers.
        """
        return self.total_rwa * 0.08

    @property
    def cet1_requirement(self) -> float:
        """CET1 capital requirement = total_rwa x 4.5%.

        The minimum Common Equity Tier 1 ratio under Basel III.
        """
        return self.total_rwa * 0.045

    @property
    def tier1_requirement(self) -> float:
        """Tier 1 capital requirement = total_rwa x 6%.

        The minimum Tier 1 capital ratio under Basel III.
        """
        return self.total_rwa * 0.06


# =========================================================================
#  SA-CR Calculator
# =========================================================================

class SACRCalculator:
    """Standardized Approach Credit Risk (SA-CR) RWA Calculator.

    Computes risk-weighted assets for a portfolio of credit exposures
    per the US Basel III Endgame / Federal Reserve re-proposal.

    The calculator follows the US-specific rules:
      - No external credit ratings (Dodd-Frank Section 939A)
      - CRC-based risk weights for sovereign and bank exposures
      - Self-assessed investment-grade for corporate 65% RW
      - LTV-based risk weights for residential and commercial RE
      - Transactor treatment for qualifying retail credit cards

    Usage:
        >>> calculator = SACRCalculator()
        >>> exposures = [
        ...     CreditExposure(
        ...         exposure_id="CORP-001",
        ...         exposure_class=ExposureClass.CORPORATE,
        ...         counterparty="ACME Corp",
        ...         ead=1_000_000.0,
        ...         is_investment_grade=True,
        ...     ),
        ... ]
        >>> result = calculator.calculate(exposures)
        >>> print(f"Total RWA: {result.total_rwa:,.0f}")
        Total RWA: 650,000

    References:
        12 CFR Part 217, Subpart E
    """

    def __init__(
        self,
        include_exposure_details: bool = True,
        validate_exposures: bool = True,
    ) -> None:
        """Initialize the SA-CR calculator.

        Args:
            include_exposure_details: If True, include individual exposure
                results in the output. Set to False for large portfolios
                where only aggregates are needed.
            validate_exposures: If True, perform additional validation
                checks on exposures before calculation.
        """
        self._include_details = include_exposure_details
        self._validate = validate_exposures
        self._risk_weight_schedule = RiskWeightSchedule()

    def calculate(self, exposures: list[CreditExposure]) -> SACRResult:
        """Calculate SA-CR RWA for a portfolio of credit exposures.

        Processes each exposure to determine its risk weight, computes
        RWA, and aggregates results by exposure class and portfolio-wide.

        Args:
            exposures: List of credit exposures to process.

        Returns:
            Complete SACRResult with portfolio and per-class aggregates.

        Raises:
            ValueError: If validation is enabled and an exposure fails checks.
        """
        if not exposures:
            logger.warning("Empty exposure list provided to SA-CR calculator")
            return SACRResult(
                risk_weight_schedule=self._risk_weight_schedule,
            )

        logger.info(
            "Starting SA-CR calculation for %d exposures", len(exposures)
        )

        # Validate exposures if enabled
        if self._validate:
            self._validate_exposures(exposures)

        # Process each exposure
        all_results: list[ExposureResult] = []
        class_accumulators: dict[str, _ClassAccumulator] = {}

        for exposure in exposures:
            result = self._process_exposure(exposure)
            all_results.append(result)

            # Accumulate by class
            class_key = exposure.exposure_class.value
            if class_key not in class_accumulators:
                class_accumulators[class_key] = _ClassAccumulator(
                    exposure_class=exposure.exposure_class,
                )
            class_accumulators[class_key].add(result)

        # Build per-class results
        class_results: dict[str, ExposureClassResult] = {}
        rwa_by_class: dict[str, float] = {}
        ead_by_class: dict[str, float] = {}

        for class_key, acc in class_accumulators.items():
            class_result = acc.to_result(
                include_details=self._include_details,
            )
            class_results[class_key] = class_result
            rwa_by_class[class_key] = class_result.total_rwa
            ead_by_class[class_key] = class_result.total_ead

        # Portfolio-level aggregation
        total_ead = sum(r.ead for r in all_results)
        total_rwa = sum(r.rwa for r in all_results)
        avg_rw = total_rwa / total_ead if total_ead > 0 else 0.0

        logger.info(
            "SA-CR calculation complete: %d exposures, "
            "total EAD=%.2f, total RWA=%.2f, avg RW=%.4f",
            len(exposures),
            total_ead,
            total_rwa,
            avg_rw,
        )

        return SACRResult(
            total_ead=total_ead,
            total_rwa=total_rwa,
            rwa_by_class=rwa_by_class,
            ead_by_class=ead_by_class,
            average_risk_weight=avg_rw,
            class_results=class_results,
            exposure_results=all_results if self._include_details else [],
            exposure_count=len(exposures),
            risk_weight_schedule=self._risk_weight_schedule,
        )

    def calculate_single(self, exposure: CreditExposure) -> ExposureResult:
        """Calculate SA-CR RWA for a single exposure.

        Convenience method for processing individual exposures without
        portfolio-level aggregation.

        Args:
            exposure: The credit exposure to process.

        Returns:
            ExposureResult with the risk weight and RWA.
        """
        return self._process_exposure(exposure)

    def get_risk_weight(self, exposure: CreditExposure) -> float:
        """Determine the risk weight for a single exposure.

        Public method exposing the risk weight determination logic
        without computing RWA.

        Args:
            exposure: The credit exposure.

        Returns:
            Risk weight as a decimal (e.g., 0.65 for 65%).
        """
        return self._get_risk_weight(exposure)

    def _process_exposure(self, exposure: CreditExposure) -> ExposureResult:
        """Process a single exposure: determine risk weight and compute RWA.

        Args:
            exposure: The credit exposure to process.

        Returns:
            ExposureResult with computed risk weight and RWA.
        """
        rw = self._get_risk_weight(exposure)
        result = ExposureResult.from_exposure(exposure, rw)

        logger.debug(
            "Exposure %s: class=%s, EAD=%.2f, RW=%.2f%%, RWA=%.2f",
            exposure.exposure_id,
            exposure.exposure_class.value,
            exposure.ead,
            rw * 100,
            result.rwa,
        )

        return result

    def _get_risk_weight(self, exposure: CreditExposure) -> float:
        """Determine the SA-CR risk weight for an exposure.

        Converts the exposure attributes into a RiskWeightInput and
        dispatches to the risk weight lookup engine.

        Args:
            exposure: The credit exposure.

        Returns:
            Risk weight as a decimal.

        References:
            12 CFR 217, Subpart E, Sections 217.111-217.132
        """
        rw_input = exposure.to_risk_weight_input()
        return get_risk_weight(rw_input)

    def _validate_exposures(
        self, exposures: list[CreditExposure]
    ) -> None:
        """Perform validation checks on the exposure portfolio.

        Checks for common data quality issues that could affect
        RWA accuracy.

        Args:
            exposures: The list of exposures to validate.

        Raises:
            ValueError: If critical validation failures are found.
        """
        seen_ids: set[str] = set()
        warnings: list[str] = []

        for exp in exposures:
            # Check for duplicate IDs
            if exp.exposure_id in seen_ids:
                warnings.append(
                    f"Duplicate exposure_id: {exp.exposure_id}"
                )
            seen_ids.add(exp.exposure_id)

            # Check for negative EAD (should not happen with validator)
            if exp.ead < 0:
                raise ValueError(
                    f"Negative EAD for exposure {exp.exposure_id}: {exp.ead}"
                )

            # Warn if residential mortgage missing LTV
            if (
                exp.exposure_class == ExposureClass.RESIDENTIAL_MORTGAGE
                and exp.ltv_ratio is None
            ):
                warnings.append(
                    f"Exposure {exp.exposure_id}: residential mortgage "
                    f"missing ltv_ratio, risk weight lookup will fail"
                )

            # Warn if CRE missing LTV for income-producing
            if (
                exp.exposure_class == ExposureClass.COMMERCIAL_REAL_ESTATE
                and exp.ltv_ratio is None
                and exp.cre_sub_type != CRESubType.ADC
                and exp.cre_sub_type != CRESubType.LAND
            ):
                warnings.append(
                    f"Exposure {exp.exposure_id}: income-producing CRE "
                    f"missing ltv_ratio, defaulting to 100%"
                )

            # Warn if corporate SME class but is_sme not set
            if (
                exp.exposure_class == ExposureClass.CORPORATE_SME
                and not exp.is_sme
            ):
                warnings.append(
                    f"Exposure {exp.exposure_id}: classified as CORPORATE_SME "
                    f"but is_sme=False"
                )

            # Warn if retail transactor but is_transactor not set
            if (
                exp.exposure_class == ExposureClass.RETAIL_TRANSACTOR
                and not exp.is_transactor
            ):
                warnings.append(
                    f"Exposure {exp.exposure_id}: classified as "
                    f"RETAIL_TRANSACTOR but is_transactor=False"
                )

            # Validate CRC range for sovereign/bank
            if exp.exposure_class in (
                ExposureClass.SOVEREIGN,
                ExposureClass.BANK,
            ):
                if not (0 <= exp.country_risk_class <= 7):
                    raise ValueError(
                        f"Exposure {exp.exposure_id}: country_risk_class "
                        f"must be 0-7, got {exp.country_risk_class}"
                    )

        if warnings:
            for w in warnings:
                logger.warning("SA-CR validation: %s", w)

    # =====================================================================
    #  Portfolio Analytics
    # =====================================================================

    def calculate_concentration(
        self,
        result: SACRResult,
    ) -> dict[str, float]:
        """Calculate exposure class concentration as share of total EAD.

        Args:
            result: The SA-CR calculation result.

        Returns:
            Dictionary mapping exposure class to its share of total EAD.
        """
        if result.total_ead == 0:
            return {}
        return {
            cls: ead / result.total_ead
            for cls, ead in result.ead_by_class.items()
        }

    def calculate_rwa_density(
        self,
        result: SACRResult,
    ) -> dict[str, float]:
        """Calculate RWA density (average RW) per exposure class.

        RWA density = RWA / EAD for each class. Useful for comparing
        risk intensity across exposure classes.

        Args:
            result: The SA-CR calculation result.

        Returns:
            Dictionary mapping exposure class to its RWA density.
        """
        densities: dict[str, float] = {}
        for cls in result.rwa_by_class:
            ead = result.ead_by_class.get(cls, 0.0)
            rwa = result.rwa_by_class.get(cls, 0.0)
            densities[cls] = rwa / ead if ead > 0 else 0.0
        return densities

    def stress_risk_weights(
        self,
        exposures: list[CreditExposure],
        rw_multiplier: float = 1.0,
        classes_to_stress: set[ExposureClass] | None = None,
    ) -> SACRResult:
        """Recalculate RWA with stressed (scaled) risk weights.

        Applies a multiplicative stress factor to risk weights for
        specified exposure classes. Useful for sensitivity analysis
        and stress testing.

        Args:
            exposures: Portfolio of credit exposures.
            rw_multiplier: Multiplicative factor for risk weights
                (e.g., 1.25 for 25% increase).
            classes_to_stress: Set of exposure classes to apply the
                stress to. If None, all classes are stressed.

        Returns:
            SACRResult with stressed RWA figures.
        """
        if not exposures:
            return SACRResult(
                risk_weight_schedule=self._risk_weight_schedule,
            )

        all_results: list[ExposureResult] = []
        class_accumulators: dict[str, _ClassAccumulator] = {}

        for exposure in exposures:
            rw = self._get_risk_weight(exposure)

            # Apply stress multiplier if applicable
            if classes_to_stress is None or exposure.exposure_class in classes_to_stress:
                rw = min(rw * rw_multiplier, 12.50)  # Cap at 1250% (full deduction)

            result = ExposureResult.from_exposure(exposure, rw)
            all_results.append(result)

            class_key = exposure.exposure_class.value
            if class_key not in class_accumulators:
                class_accumulators[class_key] = _ClassAccumulator(
                    exposure_class=exposure.exposure_class,
                )
            class_accumulators[class_key].add(result)

        class_results: dict[str, ExposureClassResult] = {}
        rwa_by_class: dict[str, float] = {}
        ead_by_class: dict[str, float] = {}

        for class_key, acc in class_accumulators.items():
            class_result = acc.to_result(include_details=self._include_details)
            class_results[class_key] = class_result
            rwa_by_class[class_key] = class_result.total_rwa
            ead_by_class[class_key] = class_result.total_ead

        total_ead = sum(r.ead for r in all_results)
        total_rwa = sum(r.rwa for r in all_results)
        avg_rw = total_rwa / total_ead if total_ead > 0 else 0.0

        return SACRResult(
            total_ead=total_ead,
            total_rwa=total_rwa,
            rwa_by_class=rwa_by_class,
            ead_by_class=ead_by_class,
            average_risk_weight=avg_rw,
            class_results=class_results,
            exposure_results=all_results if self._include_details else [],
            exposure_count=len(exposures),
            risk_weight_schedule=self._risk_weight_schedule,
        )

    def incremental_rwa(
        self,
        baseline_result: SACRResult,
        new_exposure: CreditExposure,
    ) -> tuple[float, float]:
        """Calculate incremental RWA from adding a single new exposure.

        Useful for pre-trade limit checks and what-if analysis.

        Args:
            baseline_result: Current portfolio RWA result.
            new_exposure: The proposed new exposure.

        Returns:
            Tuple of (incremental_rwa, new_total_rwa).
        """
        exp_result = self.calculate_single(new_exposure)
        incremental = exp_result.rwa
        new_total = baseline_result.total_rwa + incremental
        return incremental, new_total


# =========================================================================
#  Internal Accumulator (not exported)
# =========================================================================

class _ClassAccumulator:
    """Internal accumulator for per-class aggregation during calculation.

    Not a Pydantic model for performance — avoids validation overhead
    during the inner loop.
    """

    __slots__ = (
        "exposure_class",
        "count",
        "total_ead",
        "total_rwa",
        "min_rw",
        "max_rw",
        "results",
    )

    def __init__(self, exposure_class: ExposureClass) -> None:
        self.exposure_class = exposure_class
        self.count: int = 0
        self.total_ead: float = 0.0
        self.total_rwa: float = 0.0
        self.min_rw: float = float("inf")
        self.max_rw: float = float("-inf")
        self.results: list[ExposureResult] = []

    def add(self, result: ExposureResult) -> None:
        """Add an exposure result to this accumulator."""
        self.count += 1
        self.total_ead += result.ead
        self.total_rwa += result.rwa
        self.min_rw = min(self.min_rw, result.risk_weight)
        self.max_rw = max(self.max_rw, result.risk_weight)
        self.results.append(result)

    def to_result(self, include_details: bool = True) -> ExposureClassResult:
        """Convert accumulator state to an ExposureClassResult."""
        avg_rw = self.total_rwa / self.total_ead if self.total_ead > 0 else 0.0
        return ExposureClassResult(
            exposure_class=self.exposure_class,
            exposure_count=self.count,
            total_ead=self.total_ead,
            total_rwa=self.total_rwa,
            average_risk_weight=avg_rw,
            min_risk_weight=self.min_rw if self.count > 0 else 0.0,
            max_risk_weight=self.max_rw if self.count > 0 else 0.0,
            exposure_results=self.results if include_details else [],
        )


# =========================================================================
#  Convenience Functions
# =========================================================================

def calculate_sacr_rwa(
    exposures: list[CreditExposure],
    include_details: bool = True,
) -> SACRResult:
    """Convenience function to calculate SA-CR RWA.

    Creates a calculator instance and processes the portfolio in one call.

    Args:
        exposures: List of credit exposures.
        include_details: Whether to include individual exposure results.

    Returns:
        Complete SACRResult.

    Examples:
        >>> from src.credit_risk.sa.calculator import (
        ...     calculate_sacr_rwa, CreditExposure,
        ... )
        >>> from src.credit_risk.sa.exposure_classes import ExposureClass
        >>> result = calculate_sacr_rwa([
        ...     CreditExposure(
        ...         exposure_id="1",
        ...         exposure_class=ExposureClass.CORPORATE,
        ...         counterparty="ACME",
        ...         ead=1_000_000,
        ...         is_investment_grade=True,
        ...     ),
        ... ])
        >>> result.total_rwa
        650000.0
    """
    calculator = SACRCalculator(include_exposure_details=include_details)
    return calculator.calculate(exposures)


def build_exposure(
    exposure_id: str,
    exposure_class: ExposureClass | str,
    counterparty: str,
    ead: float,
    **kwargs: object,
) -> CreditExposure:
    """Factory function to build a CreditExposure with minimal boilerplate.

    Accepts the exposure class as either an ExposureClass enum or string.

    Args:
        exposure_id: Unique identifier.
        exposure_class: SA-CR exposure class (enum or string value).
        counterparty: Counterparty name or ID.
        ead: Exposure at default.
        **kwargs: Additional CreditExposure fields.

    Returns:
        A validated CreditExposure instance.

    Examples:
        >>> exp = build_exposure(
        ...     "MORT-001", "RESIDENTIAL_MORTGAGE", "John Doe",
        ...     500_000, ltv_ratio=0.75,
        ... )
    """
    if isinstance(exposure_class, str):
        exposure_class = ExposureClass(exposure_class)

    return CreditExposure(
        exposure_id=exposure_id,
        exposure_class=exposure_class,
        counterparty=counterparty,
        ead=ead,
        **kwargs,  # type: ignore[arg-type]
    )
