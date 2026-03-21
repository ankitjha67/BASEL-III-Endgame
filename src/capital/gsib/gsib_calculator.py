"""G-SIB surcharge calculator implementing Method 1 and Method 2.

This module is the core engine for computing the G-SIB capital surcharge
per the US Federal Reserve 2026 Re-Proposal. It implements:
- Method 1: BCBS substitutability-based approach (12 indicators, 5 categories)
- Method 2: US-specific short-term wholesale funding approach
- Higher-of Method 1 vs Method 2 determination
- Score-to-surcharge band mapping

Regulatory References:
- G-SIB NPR (128 pages): "Risk-Based Capital Surcharges for GSIBs"
- 12 CFR 217.403: G-SIB surcharge calculation
- 12 CFR 217.404: Method 1 (substitutability-based)
- 12 CFR 217.406: Method 2 (STWF-based)
- BCBS d445: Global Systemically Important Banks assessment methodology

Key 2026 Re-Proposal provisions per CLAUDE.md:
- Method 2 coefficients adjusted by 1.2x DOWNWARD factor
- Surcharge bands: 20bp score ranges / 0.1% increments (NOT 100bp/0.5%)

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.capital.gsib.gsib_indicators import (
    CategoryScore,
    GSIBIndicatorData,
    STWFScore,
    calculate_method1_score,
    calculate_method2_score,
    validate_indicator_data,
)
from src.capital.gsib.gsib_params import (
    DEFAULT_DENOMINATION_FACTORS,
    DEFAULT_VALIDATION_BOUNDS,
    DenominationFactors,
    GSIBCategory,
    GSIBIndicatorCategory,
    GSIBMethod,
    METHOD_1_BAND_WIDTH_BPS,
    METHOD_1_INITIAL_THRESHOLD_BPS,
    METHOD_1_MIN_SURCHARGE_PCT,
    METHOD_1_SURCHARGE_INCREMENT_PCT,
    METHOD_1_SURCHARGE_TABLE,
    METHOD_2_BAND_WIDTH_BPS,
    METHOD_2_INITIAL_THRESHOLD_BPS,
    METHOD_2_MIN_SURCHARGE_PCT,
    METHOD_2_SURCHARGE_INCREMENT_PCT,
    METHOD_2_SURCHARGE_TABLE,
    ValidationBounds,
    generate_surcharge_table,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Result Data Classes
# =========================================================================

@dataclass
class MethodResult:
    """Result of a single G-SIB surcharge method calculation.

    Per 12 CFR 217.403-406, each method produces:
    - A systemic importance score in basis points
    - A surcharge bucket assignment
    - A surcharge percentage

    Attributes:
        method: Which method (1 or 2)
        score_bps: Total systemic importance score in basis points
        surcharge_pct: Capital surcharge as a percentage of RWA
        surcharge_bucket: Which band the score falls into (1-based)
        band_lower_bps: Lower bound of the assigned band
        band_upper_bps: Upper bound of the assigned band
        category_scores: Breakdown by systemic importance category
        stwf_score: STWF score (Method 2 only)
        validation_warnings: Any data quality warnings
    """
    method: GSIBMethod
    score_bps: float = 0.0
    surcharge_pct: float = 0.0
    surcharge_bucket: int = 0
    band_lower_bps: float = 0.0
    band_upper_bps: float = 0.0
    category_scores: list[CategoryScore] = field(default_factory=list)
    stwf_score: Optional[STWFScore] = None
    validation_warnings: list[str] = field(default_factory=list)


@dataclass
class GSIBSurchargeResult:
    """Complete G-SIB surcharge calculation result.

    Per 12 CFR 217.403(a):
    The G-SIB surcharge is the HIGHER of Method 1 and Method 2.
    This result contains both method calculations and the final
    determination.

    Attributes:
        method1_result: Full Method 1 calculation
        method2_result: Full Method 2 calculation
        binding_method: Which method produced the higher surcharge
        final_surcharge_pct: The binding surcharge percentage
        gsib_category: Bank's G-SIB category classification
        reporting_entity: Name of the reporting bank
        reporting_date: As-of date for the calculation
        assessment_year: G-SIB assessment year
        cet1_surcharge_amount: Surcharge amount in $M (if RWA provided)
        total_rwa: Total RWA used for surcharge amount calculation ($M)
    """
    method1_result: MethodResult
    method2_result: MethodResult
    binding_method: GSIBMethod = GSIBMethod.METHOD_1
    final_surcharge_pct: float = 0.0
    gsib_category: GSIBCategory = GSIBCategory.CATEGORY_I
    reporting_entity: str = ""
    reporting_date: Optional[date] = None
    assessment_year: Optional[int] = None
    cet1_surcharge_amount: float = 0.0
    total_rwa: float = 0.0

    @property
    def method1_score_bps(self) -> float:
        """Method 1 systemic importance score in basis points."""
        return self.method1_result.score_bps

    @property
    def method2_score_bps(self) -> float:
        """Method 2 systemic importance score in basis points."""
        return self.method2_result.score_bps

    @property
    def method1_surcharge_pct(self) -> float:
        """Method 1 surcharge as percentage of RWA."""
        return self.method1_result.surcharge_pct

    @property
    def method2_surcharge_pct(self) -> float:
        """Method 2 surcharge as percentage of RWA."""
        return self.method2_result.surcharge_pct

    @property
    def score_differential_bps(self) -> float:
        """Difference between Method 2 and Method 1 scores."""
        return self.method2_result.score_bps - self.method1_result.score_bps

    @property
    def surcharge_differential_pct(self) -> float:
        """Difference between Method 2 and Method 1 surcharges."""
        return self.method2_result.surcharge_pct - self.method1_result.surcharge_pct


# =========================================================================
#  Score-to-Surcharge Mapping
# =========================================================================

def score_to_surcharge(
    score_bps: float,
    initial_threshold_bps: float,
    band_width_bps: float,
    surcharge_increment_pct: float,
    min_surcharge_pct: float,
) -> tuple[float, int, float, float]:
    """Convert a G-SIB score to a surcharge percentage.

    Per G-SIB NPR pp.25-26 / 12 CFR 217.403(b):
    The surcharge is determined by which band the score falls into.
    Bands are defined by:
    - Initial threshold: score must exceed this to be a G-SIB
    - Band width: 20bp per band (per 2026 Re-Proposal)
    - Increment: 0.1% per band (per 2026 Re-Proposal)
    - Minimum: 1.0% for any G-SIB

    CRITICAL per CLAUDE.md:
    - Surcharge bands: 20bp score ranges / 0.1% increments
    - NOT the BCBS standard 100bp/0.5%

    Args:
        score_bps: G-SIB systemic importance score in basis points
        initial_threshold_bps: First band lower bound (130bp)
        band_width_bps: Width of each band (20bp)
        surcharge_increment_pct: Surcharge increase per band (0.1%)
        min_surcharge_pct: Minimum surcharge (1.0%)

    Returns:
        Tuple of (surcharge_pct, bucket_number, band_lower, band_upper)
    """
    if score_bps < initial_threshold_bps:
        # Below the first band — technically not a G-SIB under this method.
        # However, if already designated, minimum surcharge applies.
        logger.info(
            "Score (%.2f bps) below initial threshold (%.2f bps). "
            "Applying minimum surcharge of %.1f%%.",
            score_bps, initial_threshold_bps, min_surcharge_pct,
        )
        return min_surcharge_pct, 1, 0.0, initial_threshold_bps

    # Determine which band the score falls into
    bands_above_threshold = (score_bps - initial_threshold_bps) / band_width_bps
    bucket_index = int(math.floor(bands_above_threshold))

    surcharge = min_surcharge_pct + bucket_index * surcharge_increment_pct
    band_lower = initial_threshold_bps + bucket_index * band_width_bps
    band_upper = band_lower + band_width_bps

    bucket_number = bucket_index + 1  # 1-based

    logger.info(
        "Score %.2f bps -> Band %d [%.0f, %.0f) -> Surcharge %.1f%%",
        score_bps, bucket_number, band_lower, band_upper, surcharge,
    )

    return surcharge, bucket_number, band_lower, band_upper


def score_to_method1_surcharge(score_bps: float) -> tuple[float, int, float, float]:
    """Convert a Method 1 G-SIB score to surcharge.

    Per G-SIB NPR pp.25-26 / 12 CFR 217.404:
    Uses 20bp bands and 0.1% increments per 2026 Re-Proposal.

    Args:
        score_bps: Method 1 score in basis points

    Returns:
        Tuple of (surcharge_pct, bucket, band_lower, band_upper)
    """
    return score_to_surcharge(
        score_bps=score_bps,
        initial_threshold_bps=METHOD_1_INITIAL_THRESHOLD_BPS,
        band_width_bps=METHOD_1_BAND_WIDTH_BPS,
        surcharge_increment_pct=METHOD_1_SURCHARGE_INCREMENT_PCT,
        min_surcharge_pct=METHOD_1_MIN_SURCHARGE_PCT,
    )


def score_to_method2_surcharge(score_bps: float) -> tuple[float, int, float, float]:
    """Convert a Method 2 G-SIB score to surcharge.

    Per G-SIB NPR p.36 / 12 CFR 217.406(d):
    Uses 20bp bands and 0.1% increments per 2026 Re-Proposal.

    Args:
        score_bps: Method 2 score in basis points

    Returns:
        Tuple of (surcharge_pct, bucket, band_lower, band_upper)
    """
    return score_to_surcharge(
        score_bps=score_bps,
        initial_threshold_bps=METHOD_2_INITIAL_THRESHOLD_BPS,
        band_width_bps=METHOD_2_BAND_WIDTH_BPS,
        surcharge_increment_pct=METHOD_2_SURCHARGE_INCREMENT_PCT,
        min_surcharge_pct=METHOD_2_MIN_SURCHARGE_PCT,
    )


# =========================================================================
#  Main Calculator
# =========================================================================

class GSIBCalculator:
    """G-SIB surcharge calculator implementing Method 1 and Method 2.

    Per 12 CFR 217.403:
    A G-SIB's capital surcharge is the higher of the surcharge
    calculated under Method 1 (substitutability-based, 12 indicators)
    and Method 2 (short-term wholesale funding-based).

    Key 2026 Re-Proposal changes per CLAUDE.md:
    - Method 2 coefficients adjusted by 1.2x downward factor
    - Surcharge bands: 20bp score ranges / 0.1% increments

    Usage:
        calculator = GSIBCalculator()
        result = calculator.calculate(indicator_data)
        print(f"G-SIB surcharge: {result.final_surcharge_pct}%")
    """

    def __init__(
        self,
        denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
        validation_bounds: ValidationBounds = DEFAULT_VALIDATION_BOUNDS,
        validate_inputs: bool = True,
    ) -> None:
        """Initialize the G-SIB calculator.

        Per G-SIB NPR p.24 / BCBS d445:
        Denomination factors are the global aggregates used to
        normalize individual bank indicators. These are published
        annually by the BCBS.

        Args:
            denomination_factors: Global aggregates for score normalization
            validation_bounds: Plausibility bounds for data quality checks
            validate_inputs: Whether to run validation checks on input data
        """
        self._denomination_factors = denomination_factors
        self._validation_bounds = validation_bounds
        self._validate_inputs = validate_inputs

    def calculate(
        self,
        indicator_data: GSIBIndicatorData,
        total_rwa: float = 0.0,
    ) -> GSIBSurchargeResult:
        """Calculate the G-SIB surcharge using both methods.

        Per 12 CFR 217.403(a):
        1. Calculate Method 1 score and surcharge
        2. Calculate Method 2 score and surcharge
        3. Final surcharge = max(Method 1, Method 2)

        The final surcharge is an additional CET1 requirement on top of
        the minimum 4.5% CET1 ratio.

        Args:
            indicator_data: Complete set of indicator values
            total_rwa: Total risk-weighted assets ($M) for computing
                        the surcharge dollar amount. Optional.

        Returns:
            GSIBSurchargeResult with full breakdown of both methods
        """
        # Step 0: Validate inputs
        validation_warnings: list[str] = []
        if self._validate_inputs:
            validation_warnings = validate_indicator_data(
                indicator_data, self._validation_bounds
            )
            for warning in validation_warnings:
                logger.warning("Validation: %s", warning)

        # Step 1: Calculate Method 1
        # Per 12 CFR 217.404
        method1_result = self._calculate_method1(indicator_data, validation_warnings)

        # Step 2: Calculate Method 2
        # Per 12 CFR 217.406
        method2_result = self._calculate_method2(indicator_data, validation_warnings)

        # Step 3: Determine binding method
        # Per 12 CFR 217.403(a): surcharge = max(Method 1, Method 2)
        if method2_result.surcharge_pct >= method1_result.surcharge_pct:
            binding_method = GSIBMethod.METHOD_2
            final_surcharge = method2_result.surcharge_pct
        else:
            binding_method = GSIBMethod.METHOD_1
            final_surcharge = method1_result.surcharge_pct

        logger.info(
            "G-SIB surcharge determination: Method 1=%.1f%%, Method 2=%.1f%%, "
            "Binding=%s, Final=%.1f%%",
            method1_result.surcharge_pct,
            method2_result.surcharge_pct,
            binding_method.value,
            final_surcharge,
        )

        # Calculate surcharge dollar amount if RWA provided
        cet1_surcharge_amount = 0.0
        if total_rwa > 0:
            cet1_surcharge_amount = total_rwa * (final_surcharge / 100.0)
            logger.info(
                "CET1 surcharge amount: $%.0fM (%.1f%% of $%.0fM RWA)",
                cet1_surcharge_amount, final_surcharge, total_rwa,
            )

        return GSIBSurchargeResult(
            method1_result=method1_result,
            method2_result=method2_result,
            binding_method=binding_method,
            final_surcharge_pct=final_surcharge,
            gsib_category=GSIBCategory.CATEGORY_I,
            reporting_entity=indicator_data.reporting_entity,
            reporting_date=indicator_data.reporting_date,
            assessment_year=indicator_data.assessment_year,
            cet1_surcharge_amount=cet1_surcharge_amount,
            total_rwa=total_rwa,
        )

    def _calculate_method1(
        self,
        indicator_data: GSIBIndicatorData,
        validation_warnings: list[str],
    ) -> MethodResult:
        """Calculate Method 1 G-SIB score and surcharge.

        Per 12 CFR 217.404 / G-SIB NPR Section II.B:
        Method 1 uses 12 indicators across 5 categories, each
        weighted at 20%. The substitutability category is capped
        at 500bp.

        Args:
            indicator_data: Bank's indicator values
            validation_warnings: Pre-computed validation warnings

        Returns:
            MethodResult with Method 1 score and surcharge
        """
        score_bps, category_scores = calculate_method1_score(
            indicator_data, self._denomination_factors
        )

        surcharge, bucket, band_lower, band_upper = score_to_method1_surcharge(score_bps)

        return MethodResult(
            method=GSIBMethod.METHOD_1,
            score_bps=score_bps,
            surcharge_pct=surcharge,
            surcharge_bucket=bucket,
            band_lower_bps=band_lower,
            band_upper_bps=band_upper,
            category_scores=category_scores,
            validation_warnings=validation_warnings,
        )

    def _calculate_method2(
        self,
        indicator_data: GSIBIndicatorData,
        validation_warnings: list[str],
    ) -> MethodResult:
        """Calculate Method 2 G-SIB score and surcharge.

        Per 12 CFR 217.406 / G-SIB NPR Section II.D:
        Method 2 replaces the substitutability category with
        the Short-Term Wholesale Funding (STWF) component.

        CRITICAL per CLAUDE.md:
        Method 2 coefficients are adjusted by 1.2x downward factor.

        Args:
            indicator_data: Bank's indicator values
            validation_warnings: Pre-computed validation warnings

        Returns:
            MethodResult with Method 2 score and surcharge
        """
        score_bps, category_scores, stwf_score = calculate_method2_score(
            indicator_data, self._denomination_factors
        )

        surcharge, bucket, band_lower, band_upper = score_to_method2_surcharge(score_bps)

        return MethodResult(
            method=GSIBMethod.METHOD_2,
            score_bps=score_bps,
            surcharge_pct=surcharge,
            surcharge_bucket=bucket,
            band_lower_bps=band_lower,
            band_upper_bps=band_upper,
            category_scores=category_scores,
            stwf_score=stwf_score,
            validation_warnings=validation_warnings,
        )

    def calculate_method1_only(
        self,
        indicator_data: GSIBIndicatorData,
    ) -> MethodResult:
        """Calculate only Method 1 G-SIB score and surcharge.

        Per 12 CFR 217.404: standalone Method 1 calculation
        for analysis or comparison purposes.

        Args:
            indicator_data: Bank's indicator values

        Returns:
            MethodResult with Method 1 results
        """
        warnings = (
            validate_indicator_data(indicator_data, self._validation_bounds)
            if self._validate_inputs else []
        )
        return self._calculate_method1(indicator_data, warnings)

    def calculate_method2_only(
        self,
        indicator_data: GSIBIndicatorData,
    ) -> MethodResult:
        """Calculate only Method 2 G-SIB score and surcharge.

        Per 12 CFR 217.406: standalone Method 2 calculation
        for analysis or comparison purposes.

        Args:
            indicator_data: Bank's indicator values

        Returns:
            MethodResult with Method 2 results
        """
        warnings = (
            validate_indicator_data(indicator_data, self._validation_bounds)
            if self._validate_inputs else []
        )
        return self._calculate_method2(indicator_data, warnings)

    def sensitivity_analysis(
        self,
        indicator_data: GSIBIndicatorData,
        indicator_name: str,
        shock_pcts: list[float] | None = None,
    ) -> list[tuple[float, float, float]]:
        """Run sensitivity analysis on a single indicator.

        Per SR 11-7 model governance requirements, models must
        include sensitivity analysis capabilities.

        Shocks the specified indicator by each percentage and
        recalculates the surcharge.

        Args:
            indicator_data: Base case indicator values
            indicator_name: Name of the indicator to shock
            shock_pcts: List of shock percentages (e.g., [-20, -10, 0, 10, 20])
                        Defaults to [-20, -10, -5, 0, 5, 10, 20]

        Returns:
            List of (shock_pct, score_bps, surcharge_pct) tuples
        """
        if shock_pcts is None:
            shock_pcts = [-20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0]

        base_value = indicator_data.get_indicator_value(indicator_name)
        results: list[tuple[float, float, float]] = []

        for shock in shock_pcts:
            # Create shocked data by copying and modifying the indicator
            shocked_data = GSIBIndicatorData(
                reporting_entity=indicator_data.reporting_entity,
                reporting_date=indicator_data.reporting_date,
                assessment_year=indicator_data.assessment_year,
                total_exposures=indicator_data.total_exposures,
                intra_financial_system_assets=indicator_data.intra_financial_system_assets,
                intra_financial_system_liabilities=indicator_data.intra_financial_system_liabilities,
                securities_outstanding=indicator_data.securities_outstanding,
                payments_activity=indicator_data.payments_activity,
                assets_under_custody=indicator_data.assets_under_custody,
                underwriting_activity=indicator_data.underwriting_activity,
                otc_derivatives_notional=indicator_data.otc_derivatives_notional,
                trading_and_afs_securities=indicator_data.trading_and_afs_securities,
                level_3_assets=indicator_data.level_3_assets,
                cross_jurisdictional_claims=indicator_data.cross_jurisdictional_claims,
                cross_jurisdictional_liabilities=indicator_data.cross_jurisdictional_liabilities,
                stwf_0_30_days=indicator_data.stwf_0_30_days,
                stwf_31_90_days=indicator_data.stwf_31_90_days,
                stwf_91_180_days=indicator_data.stwf_91_180_days,
                stwf_181_365_days=indicator_data.stwf_181_365_days,
                avg_total_assets=indicator_data.avg_total_assets,
            )

            # Apply shock
            shocked_value = base_value * (1 + shock / 100.0)
            setattr(shocked_data, indicator_name, shocked_value)

            # Recalculate
            calc_result = self.calculate(shocked_data)
            results.append((
                shock,
                max(calc_result.method1_score_bps, calc_result.method2_score_bps),
                calc_result.final_surcharge_pct,
            ))

        return results

    def what_if_analysis(
        self,
        indicator_data: GSIBIndicatorData,
        target_surcharge_pct: float,
        indicator_name: str,
    ) -> Optional[float]:
        """Determine what indicator value would achieve a target surcharge.

        Per SR 11-7 requirements for model interpretability,
        this function performs a reverse calculation to find what
        indicator level would result in a specific surcharge.

        Uses bisection method to find the indicator value.

        Args:
            indicator_data: Base case indicator values
            target_surcharge_pct: Desired surcharge percentage
            indicator_name: Which indicator to adjust

        Returns:
            Required indicator value in $M, or None if not achievable
        """
        base_value = indicator_data.get_indicator_value(indicator_name)
        if base_value <= 0:
            return None

        # Search range: 10% to 300% of current value
        low_mult = 0.1
        high_mult = 3.0

        for _ in range(50):  # Max 50 iterations
            mid_mult = (low_mult + high_mult) / 2.0
            test_value = base_value * mid_mult

            # Create modified data
            modified_data = GSIBIndicatorData(
                reporting_entity=indicator_data.reporting_entity,
                total_exposures=indicator_data.total_exposures,
                intra_financial_system_assets=indicator_data.intra_financial_system_assets,
                intra_financial_system_liabilities=indicator_data.intra_financial_system_liabilities,
                securities_outstanding=indicator_data.securities_outstanding,
                payments_activity=indicator_data.payments_activity,
                assets_under_custody=indicator_data.assets_under_custody,
                underwriting_activity=indicator_data.underwriting_activity,
                otc_derivatives_notional=indicator_data.otc_derivatives_notional,
                trading_and_afs_securities=indicator_data.trading_and_afs_securities,
                level_3_assets=indicator_data.level_3_assets,
                cross_jurisdictional_claims=indicator_data.cross_jurisdictional_claims,
                cross_jurisdictional_liabilities=indicator_data.cross_jurisdictional_liabilities,
                stwf_0_30_days=indicator_data.stwf_0_30_days,
                stwf_31_90_days=indicator_data.stwf_31_90_days,
                stwf_91_180_days=indicator_data.stwf_91_180_days,
                stwf_181_365_days=indicator_data.stwf_181_365_days,
                avg_total_assets=indicator_data.avg_total_assets,
            )
            setattr(modified_data, indicator_name, test_value)

            result = self.calculate(modified_data)
            actual = result.final_surcharge_pct

            if abs(actual - target_surcharge_pct) < 0.01:
                return test_value

            if actual < target_surcharge_pct:
                low_mult = mid_mult
            else:
                high_mult = mid_mult

        logger.warning(
            "What-if analysis did not converge for indicator '%s' "
            "targeting %.1f%% surcharge.",
            indicator_name, target_surcharge_pct,
        )
        return None

    def marginal_contribution(
        self,
        indicator_data: GSIBIndicatorData,
        shock_pct: float = 1.0,
    ) -> dict[str, float]:
        """Calculate the marginal contribution of each indicator to the score.

        Per SR 11-7 model documentation requirements:
        Shows how much the overall G-SIB score changes when each
        indicator increases by shock_pct%.

        Args:
            indicator_data: Base case indicator values
            shock_pct: Percentage shock to apply (default 1%)

        Returns:
            Dict mapping indicator name to marginal score change in bps
        """
        base_result = self.calculate(indicator_data)
        base_score = max(base_result.method1_score_bps, base_result.method2_score_bps)

        contributions: dict[str, float] = {}
        indicator_names = [ind.name for ind in METHOD_1_INDICATORS]

        for name in indicator_names:
            base_value = indicator_data.get_indicator_value(name)
            if base_value <= 0:
                contributions[name] = 0.0
                continue

            shocked_data = GSIBIndicatorData(
                reporting_entity=indicator_data.reporting_entity,
                total_exposures=indicator_data.total_exposures,
                intra_financial_system_assets=indicator_data.intra_financial_system_assets,
                intra_financial_system_liabilities=indicator_data.intra_financial_system_liabilities,
                securities_outstanding=indicator_data.securities_outstanding,
                payments_activity=indicator_data.payments_activity,
                assets_under_custody=indicator_data.assets_under_custody,
                underwriting_activity=indicator_data.underwriting_activity,
                otc_derivatives_notional=indicator_data.otc_derivatives_notional,
                trading_and_afs_securities=indicator_data.trading_and_afs_securities,
                level_3_assets=indicator_data.level_3_assets,
                cross_jurisdictional_claims=indicator_data.cross_jurisdictional_claims,
                cross_jurisdictional_liabilities=indicator_data.cross_jurisdictional_liabilities,
                stwf_0_30_days=indicator_data.stwf_0_30_days,
                stwf_31_90_days=indicator_data.stwf_31_90_days,
                stwf_91_180_days=indicator_data.stwf_91_180_days,
                stwf_181_365_days=indicator_data.stwf_181_365_days,
                avg_total_assets=indicator_data.avg_total_assets,
            )
            setattr(shocked_data, name, base_value * (1 + shock_pct / 100.0))

            shocked_result = self.calculate(shocked_data)
            shocked_score = max(
                shocked_result.method1_score_bps,
                shocked_result.method2_score_bps,
            )
            contributions[name] = shocked_score - base_score

        return contributions


# =========================================================================
#  Convenience Functions
# =========================================================================

def calculate_gsib_surcharge(
    indicator_data: GSIBIndicatorData,
    total_rwa: float = 0.0,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
) -> GSIBSurchargeResult:
    """Calculate G-SIB surcharge using default settings.

    Per 12 CFR 217.403(a):
    Convenience function that creates a GSIBCalculator with default
    denomination factors and computes the surcharge.

    Args:
        indicator_data: Complete set of indicator values
        total_rwa: Total RWA ($M) for computing dollar surcharge amount
        denomination_factors: Global aggregates for normalization

    Returns:
        GSIBSurchargeResult with full breakdown
    """
    calculator = GSIBCalculator(denomination_factors=denomination_factors)
    return calculator.calculate(indicator_data, total_rwa=total_rwa)


def get_surcharge_for_score(
    score_bps: float,
    method: GSIBMethod = GSIBMethod.METHOD_1,
) -> float:
    """Quick lookup: convert a G-SIB score to a surcharge percentage.

    Per G-SIB NPR pp.25-26 / CLAUDE.md:
    Uses 20bp bands and 0.1% increments.

    Args:
        score_bps: G-SIB score in basis points
        method: Which method's conversion table to use

    Returns:
        Surcharge percentage
    """
    if method == GSIBMethod.METHOD_1:
        surcharge, _, _, _ = score_to_method1_surcharge(score_bps)
    else:
        surcharge, _, _, _ = score_to_method2_surcharge(score_bps)
    return surcharge


# =========================================================================
#  Helper: Create indicator data from a dict
# =========================================================================

def create_indicator_data_from_dict(
    data: dict[str, float],
    reporting_entity: str = "",
    reporting_date: Optional[date] = None,
    assessment_year: Optional[int] = None,
) -> GSIBIndicatorData:
    """Create GSIBIndicatorData from a flat dictionary.

    Convenience function for building indicator data from external
    sources (e.g., FR Y-15 filings, data warehouses).

    Per FR Y-15 Instructions:
    Maps standard field names to indicator data attributes.

    Args:
        data: Dictionary mapping indicator names to values in $M
        reporting_entity: Name of the bank
        reporting_date: As-of date
        assessment_year: G-SIB assessment year

    Returns:
        GSIBIndicatorData populated from the dictionary
    """
    return GSIBIndicatorData(
        reporting_entity=reporting_entity,
        reporting_date=reporting_date,
        assessment_year=assessment_year,
        total_exposures=data.get("total_exposures", 0.0),
        intra_financial_system_assets=data.get("intra_financial_system_assets", 0.0),
        intra_financial_system_liabilities=data.get("intra_financial_system_liabilities", 0.0),
        securities_outstanding=data.get("securities_outstanding", 0.0),
        payments_activity=data.get("payments_activity", 0.0),
        assets_under_custody=data.get("assets_under_custody", 0.0),
        underwriting_activity=data.get("underwriting_activity", 0.0),
        otc_derivatives_notional=data.get("otc_derivatives_notional", 0.0),
        trading_and_afs_securities=data.get("trading_and_afs_securities", 0.0),
        level_3_assets=data.get("level_3_assets", 0.0),
        cross_jurisdictional_claims=data.get("cross_jurisdictional_claims", 0.0),
        cross_jurisdictional_liabilities=data.get("cross_jurisdictional_liabilities", 0.0),
        stwf_0_30_days=data.get("stwf_0_30_days", 0.0),
        stwf_31_90_days=data.get("stwf_31_90_days", 0.0),
        stwf_91_180_days=data.get("stwf_91_180_days", 0.0),
        stwf_181_365_days=data.get("stwf_181_365_days", 0.0),
        avg_total_assets=data.get("avg_total_assets", 0.0),
    )


# Import for convenient access
from src.capital.gsib.gsib_params import METHOD_1_INDICATORS  # noqa: E402
