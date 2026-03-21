"""Securitization Framework — SEC-SA, SEC-ERBA, and STC per CRE40 / BCBS d424.

Implements risk weight calculations for securitization exposures using:
- SEC-SA: Simplified Supervisory Formula Approach (SSFA)
- SEC-ERBA: External Ratings-Based Approach (with maturity interpolation)
- STC: Simple, Transparent, Comparable criteria checking

The hierarchy is: SEC-IRBA > SEC-ERBA > SEC-SA.
US Basel III Endgame primarily uses SEC-SA with limited ERBA
(Dodd-Frank §939A constrains use of external ratings).

Key formulas:
- SSFA: K_SSFA(A, D) = (e^(alpha*u) - e^(alpha*l)) / (alpha * (u - l))
- K_A = K_g + W * (1 - K_g)  [delinquency-adjusted pool capital ratio]
- SEC-SA floor = 15% for non-resecuritization, 100% for resecuritization
- RWA cap = 1250% (full deduction equivalent)

Reference:
    BCBS d424 CRE40, US Federal Reserve Basel III Endgame March 2026 Re-Proposal.
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.securitization.sec_params import (
    CONCENTRATION_N_THRESHOLD,
    CONCENTRATION_RW_ADDON,
    CTP_LONG_FLOOR,
    CTP_SHORT_FLOOR,
    DEFAULT_POOL_CAPITAL_RATIO,
    MAX_POOL_CAPITAL_RATIO,
    MAX_RISK_WEIGHT,
    MIN_RISK_WEIGHT_NON_RESEC,
    MIN_RISK_WEIGHT_RESEC,
    P_NON_RESECURITIZATION as P_NON_RESEC,
    P_RESECURITIZATION as P_RESEC,
    P_STC_NON_RESEC,
    RESEC_RW_FLOOR,
    RESEC_RW_MULTIPLIER,
    SEC4_RW_BANDS,
    SEC_ERBA_RW,
    STC_ELIGIBLE_ASSET_TYPES,
    STC_ERBA_MULTIPLIER,
    STC_MAX_MATURITY_YEARS,
    STC_MAX_SINGLE_OBLIGOR,
    STC_MIN_EFFECTIVE_OBLIGORS,
    STC_MIN_EXPOSURES,
    STC_RISK_WEIGHT_FLOOR,
    TRANCHE_THICKNESS,
    SecApproach,
    interpolate_erba_rw,
)

# Regulatory constants
MAX_RW: float = MAX_RISK_WEIGHT   # 1250% cap
MIN_RW_RESEC: float = MIN_RISK_WEIGHT_RESEC  # 100% floor for resecuritization


def get_erba_risk_weight(
    rating: str, is_senior: bool, maturity_years: float
) -> float | None:
    """Look up SEC-ERBA risk weight with maturity interpolation.

    For maturities between 1 and 5 years, linearly interpolates
    between SHORT and LONG risk weights per CRE40.43.

    Args:
        rating: External rating (AAA, AA, A, BBB, BB, B, CCC, BELOW_CCC).
        is_senior: Whether the tranche is senior.
        maturity_years: Remaining maturity in years.

    Returns:
        Risk weight as decimal, or None if rating not in table.

    Reference:
        CRE40.42-43; ERBA NPR Tables 2-5.
    """
    seniority = "SENIOR" if is_senior else "NON_SENIOR"
    return interpolate_erba_rw(rating.upper(), seniority, maturity_years)


# =========================================================================
#  Models
# =========================================================================

class SecuritizationPool(BaseModel):
    """Underlying securitization pool characteristics per CRE40.48.

    All monetary values in USD.

    Reference:
        CRE40.48-50; ERBA NPR Section IV.
    """
    pool_id: str
    total_ead: float = Field(
        description="Total EAD of underlying pool (CRE40.48)"
    )
    pool_rwa: float = Field(
        description="RWA of pool if held directly, for K_g (CRE40.48)"
    )
    delinquency_ratio: float = Field(
        default=0.0,
        description="W parameter: ratio of delinquent exposures (CRE40.54)"
    )
    asset_type: str = Field(
        default="CORPORATE",
        description="RMBS, CMBS, CLO, ABS, CORPORATE (CRE40.4)"
    )
    number_of_exposures: int = Field(
        default=100,
        description="Number of underlying exposures in the pool"
    )
    effective_number_of_obligors: float = Field(
        default=50.0,
        description="Effective number of obligors (N) for concentration (CRE40.56)"
    )
    largest_obligor_share: float = Field(
        default=0.01,
        description="Largest single obligor share of pool (0 to 1)"
    )
    weighted_average_maturity: float = Field(
        default=5.0,
        description="Weighted average maturity of underlying pool in years"
    )
    is_synthetic: bool = Field(
        default=False,
        description="Whether this is a synthetic securitization"
    )

    @field_validator("delinquency_ratio")
    @classmethod
    def delinquency_in_range(cls, v: float) -> float:
        """W must be between 0 and 1 per CRE40.54."""
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Delinquency ratio must be 0-1, got {v}")
        return v


class SecuritizationTranche(BaseModel):
    """A single securitization tranche/position per CRE40.41.

    All monetary values in USD.

    Reference:
        CRE40.41-46; ERBA NPR Section IV.
    """
    tranche_id: str
    pool_id: str
    attachment_point: float = Field(
        description="A: lower attachment point (0.0 to 1.0) per CRE40.41"
    )
    detachment_point: float = Field(
        description="D: upper detachment point (0.0 to 1.0) per CRE40.41"
    )
    notional: float = Field(description="Notional exposure amount in USD")
    is_senior: bool = Field(
        default=False,
        description="Whether this is the most senior tranche per CRE40.42"
    )
    is_resecuritization: bool = Field(
        default=False,
        description="Whether this is a resecuritization per CRE40.63"
    )
    external_rating: Optional[str] = Field(
        default=None,
        description="External rating (AAA..BELOW_CCC) for SEC-ERBA"
    )
    maturity_years: float = Field(
        default=5.0,
        description="Remaining maturity in years for ERBA interpolation"
    )
    is_stc: bool = Field(
        default=False,
        description="Whether this tranche meets STC criteria per CRE40.70"
    )
    is_ctp: bool = Field(
        default=False,
        description="Whether this is a Correlation Trading Portfolio position"
    )
    is_long: bool = Field(
        default=True,
        description="Long (True) or short (False) position"
    )

    @field_validator("attachment_point", "detachment_point")
    @classmethod
    def point_in_range(cls, v: float) -> float:
        """Attachment/detachment must be between 0 and 1 per CRE40.41."""
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Attachment/detachment must be 0-1, got {v}")
        return v


class SecResult(BaseModel):
    """Result of securitization RWA calculation.

    Reference:
        CRE40.46; ERBA NPR Section IV.
    """
    total_rwa: float = Field(
        default=0.0, description="Total securitization RWA in USD"
    )
    rwa_by_tranche: dict[str, float] = Field(
        default_factory=dict, description="RWA by tranche ID"
    )
    rw_by_tranche: dict[str, float] = Field(
        default_factory=dict, description="Risk weight by tranche ID"
    )
    approach_used: dict[str, str] = Field(
        default_factory=dict, description="Approach used by tranche ID"
    )
    k_g: float = Field(
        default=0.0, description="Pool capital ratio K_g"
    )
    k_a: float = Field(
        default=0.0, description="Delinquency-adjusted K_A"
    )
    rw_band_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="RWA distribution by risk weight band for SEC4"
    )
    stc_rwa: float = Field(
        default=0.0, description="RWA from STC-compliant tranches"
    )
    non_stc_rwa: float = Field(
        default=0.0, description="RWA from non-STC tranches"
    )


# =========================================================================
#  STC Criteria Checker
# =========================================================================

class STCCriteria(BaseModel):
    """STC (Simple, Transparent, Comparable) criteria inputs per CRE40.70.

    Reference:
        CRE40.70-40.80; BCBS d424 STC criteria.
    """
    asset_type: str = Field(description="Pool asset type")
    number_of_exposures: int = Field(description="Number of underlying exposures")
    effective_number_of_obligors: float = Field(description="Effective N")
    largest_obligor_share: float = Field(description="Max single obligor %")
    tranche_maturity_years: float = Field(description="Tranche maturity")
    is_synthetic: bool = Field(default=False, description="Synthetic securitization")
    has_revolving_period: bool = Field(
        default=False, description="Whether pool has revolving period"
    )
    has_currency_mismatch: bool = Field(
        default=False, description="Whether there is currency mismatch"
    )
    has_interest_rate_mismatch: bool = Field(
        default=False, description="Whether there is interest rate mismatch"
    )
    originator_retains_risk: bool = Field(
        default=True, description="Whether originator retains >= 5% risk"
    )


class STCResult(BaseModel):
    """Result of STC criteria check.

    Reference:
        CRE40.70-40.80.
    """
    is_stc_compliant: bool = Field(description="Whether all STC criteria are met")
    criteria_met: list[str] = Field(
        default_factory=list, description="List of criteria met"
    )
    criteria_failed: list[str] = Field(
        default_factory=list, description="List of criteria failed"
    )


def check_stc_criteria(criteria: STCCriteria) -> STCResult:
    """Check whether a securitization meets STC criteria per CRE40.70-40.80.

    STC (Simple, Transparent, Comparable) securitizations receive
    preferential capital treatment. This function checks the quantitative
    criteria; qualitative criteria (documentation, disclosure) must be
    verified separately.

    Args:
        criteria: STC criteria inputs.

    Returns:
        STCResult indicating compliance and which criteria passed/failed.

    Reference:
        CRE40.70-40.80; BCBS d424 STC criteria.
    """
    met: list[str] = []
    failed: list[str] = []

    # 1. Eligible asset type per CRE40.78
    if criteria.asset_type in STC_ELIGIBLE_ASSET_TYPES:
        met.append("Eligible asset type")
    else:
        failed.append(f"Asset type '{criteria.asset_type}' not STC-eligible")

    # 2. Minimum number of exposures per CRE40.76
    if criteria.number_of_exposures >= STC_MIN_EXPOSURES:
        met.append(f"Minimum exposures ({criteria.number_of_exposures} >= {STC_MIN_EXPOSURES})")
    else:
        failed.append(f"Too few exposures ({criteria.number_of_exposures} < {STC_MIN_EXPOSURES})")

    # 3. Granularity: effective obligors per CRE40.76
    if criteria.effective_number_of_obligors >= STC_MIN_EFFECTIVE_OBLIGORS:
        met.append(f"Sufficient granularity (N={criteria.effective_number_of_obligors:.0f})")
    else:
        failed.append(f"Insufficient granularity (N={criteria.effective_number_of_obligors:.0f})")

    # 4. Concentration limit per CRE40.77
    if criteria.largest_obligor_share <= STC_MAX_SINGLE_OBLIGOR:
        met.append(f"Concentration OK ({criteria.largest_obligor_share:.2%} <= {STC_MAX_SINGLE_OBLIGOR:.0%})")
    else:
        failed.append(f"Over-concentrated ({criteria.largest_obligor_share:.2%} > {STC_MAX_SINGLE_OBLIGOR:.0%})")

    # 5. Maturity limit per CRE40.75
    if criteria.tranche_maturity_years <= STC_MAX_MATURITY_YEARS:
        met.append(f"Maturity OK ({criteria.tranche_maturity_years}y <= {STC_MAX_MATURITY_YEARS}y)")
    else:
        failed.append(f"Maturity too long ({criteria.tranche_maturity_years}y > {STC_MAX_MATURITY_YEARS}y)")

    # 6. Not synthetic per CRE40.71
    if not criteria.is_synthetic:
        met.append("Not synthetic")
    else:
        failed.append("Synthetic securitizations not STC-eligible")

    # 7. No currency mismatch per CRE40.79
    if not criteria.has_currency_mismatch:
        met.append("No currency mismatch")
    else:
        failed.append("Currency mismatch present")

    # 8. Risk retention per CRE40.80
    if criteria.originator_retains_risk:
        met.append("Originator risk retention met")
    else:
        failed.append("Originator risk retention not met")

    return STCResult(
        is_stc_compliant=len(failed) == 0,
        criteria_met=met,
        criteria_failed=failed,
    )


# =========================================================================
#  Calculator
# =========================================================================

class SecuritizationCalculator:
    """Securitization risk weight calculator using SEC-SA (SSFA) and SEC-ERBA.

    Implements the full securitization framework per CRE40:
    - SEC-SA with SSFA formula
    - SEC-ERBA with maturity interpolation
    - STC preferential treatment
    - Resecuritization multipliers
    - CTP handling
    - Concentration add-on
    - Risk weight bands for SEC4 reporting

    Usage::

        calc = SecuritizationCalculator()
        result = calc.calculate(tranches, pool)
        print(f"Sec RWA: {result.total_rwa:,.0f}")

    Reference:
        BCBS d424 CRE40; US Fed Basel III Endgame March 2026 Re-Proposal.
    """

    def calculate(
        self,
        tranches: list[SecuritizationTranche],
        pool: SecuritizationPool,
    ) -> SecResult:
        """Calculate RWA for all tranches per CRE40.

        Determines the appropriate approach (SEC-ERBA or SEC-SA) for
        each tranche and computes risk-weighted assets.

        Args:
            tranches: List of securitization tranches.
            pool: Underlying pool characteristics.

        Returns:
            SecResult with RWA and risk weights per tranche.

        Reference:
            CRE40.3-40.5; ERBA NPR Section IV.
        """
        if not tranches:
            return SecResult(total_rwa=0.0)

        # Pool capital ratio K_g per CRE40.48
        k_g = self._compute_k_g(pool)

        # Delinquency-adjusted K_A per CRE40.54
        k_a = k_g + pool.delinquency_ratio * (1 - k_g)

        total_rwa = 0.0
        stc_rwa = 0.0
        non_stc_rwa = 0.0
        rwa_by_tranche: dict[str, float] = {}
        rw_by_tranche: dict[str, float] = {}
        approach_by_tranche: dict[str, str] = {}
        rw_band_rwa: dict[str, float] = {band[2]: 0.0 for band in SEC4_RW_BANDS}

        for tranche in tranches:
            rw, approach = self._compute_tranche_rw(tranche, k_g, k_a, pool)

            # Apply caps and floors per CRE40.44-46
            rw = self._apply_caps_and_floors(rw, tranche)

            # Compute RWA
            tranche_rwa = tranche.notional * rw
            total_rwa += tranche_rwa

            # Track STC vs non-STC
            if tranche.is_stc:
                stc_rwa += tranche_rwa
            else:
                non_stc_rwa += tranche_rwa

            rwa_by_tranche[tranche.tranche_id] = tranche_rwa
            rw_by_tranche[tranche.tranche_id] = rw
            approach_by_tranche[tranche.tranche_id] = approach

            # Classify into risk weight bands for SEC4
            for low, high, label in SEC4_RW_BANDS:
                if low == high == 12.50:
                    if rw >= 12.50:
                        rw_band_rwa[label] += tranche_rwa
                elif low <= rw < high:
                    rw_band_rwa[label] += tranche_rwa
                    break

        return SecResult(
            total_rwa=total_rwa,
            rwa_by_tranche=rwa_by_tranche,
            rw_by_tranche=rw_by_tranche,
            approach_used=approach_by_tranche,
            k_g=k_g,
            k_a=k_a,
            rw_band_distribution=rw_band_rwa,
            stc_rwa=stc_rwa,
            non_stc_rwa=non_stc_rwa,
        )

    def _compute_tranche_rw(
        self,
        tranche: SecuritizationTranche,
        k_g: float,
        k_a: float,
        pool: SecuritizationPool,
    ) -> tuple[float, str]:
        """Compute risk weight for a single tranche.

        Applies the approach hierarchy: SEC-ERBA > SEC-SA.
        If ERBA is available and produces a lower RW, use it.

        Args:
            tranche: The tranche to evaluate.
            k_g: Pool capital ratio.
            k_a: Delinquency-adjusted pool capital ratio.
            pool: Pool characteristics.

        Returns:
            Tuple of (risk_weight, approach_name).

        Reference:
            CRE40.3-40.5; ERBA NPR Section IV.
        """
        # Always compute SEC-SA as fallback
        sa_rw = self._ssfa_risk_weight(tranche, k_a, pool)

        # Try SEC-ERBA if external rating is available
        if tranche.external_rating:
            erba_rw = get_erba_risk_weight(
                tranche.external_rating,
                tranche.is_senior,
                tranche.maturity_years,
            )

            # Apply STC multiplier to ERBA if applicable
            if erba_rw is not None and tranche.is_stc:
                erba_rw = max(erba_rw * STC_ERBA_MULTIPLIER, STC_RISK_WEIGHT_FLOOR)

            # Apply resecuritization multiplier to ERBA
            if erba_rw is not None and tranche.is_resecuritization:
                erba_rw = erba_rw * RESEC_RW_MULTIPLIER

            if erba_rw is not None:
                # Use the lower of ERBA and SA per CRE40.5
                if erba_rw <= sa_rw:
                    return erba_rw, SecApproach.SEC_ERBA.value
                else:
                    return sa_rw, SecApproach.SEC_SA.value

        return sa_rw, SecApproach.SEC_SA.value

    def _ssfa_risk_weight(
        self,
        tranche: SecuritizationTranche,
        k_a: float,
        pool: SecuritizationPool,
    ) -> float:
        """Compute SEC-SA risk weight using SSFA per CRE40.4.

        SSFA formula:
            K_SSFA(A, D) = (e^(alpha*u) - e^(alpha*l)) / (alpha * (u - l))

        Where:
            alpha = -(1 / (p * K_A))
            u = D - K_A
            l = max(A - K_A, 0)
            p = supervisory parameter (0.5 non-resec, 1.5 resec, 0.3 STC)
            K_A = K_g + W * (1 - K_g) [delinquency-adjusted pool capital]

        Args:
            tranche: The tranche to evaluate.
            k_a: Delinquency-adjusted pool capital ratio.
            pool: Pool characteristics.

        Returns:
            Risk weight as a decimal (e.g., 0.15 for 15%).

        Reference:
            CRE40.4, CRE40.50-54; ERBA NPR Section IV.
        """
        a = tranche.attachment_point
        d = tranche.detachment_point

        # Select supervisory parameter p
        if tranche.is_resecuritization:
            p = P_RESEC
        elif tranche.is_stc:
            p = P_STC_NON_RESEC
        else:
            p = P_NON_RESEC

        # SSFA parameters
        u = d - k_a
        l_val = max(a - k_a, 0.0)

        # If entire tranche is below K_A -> 1250% RW
        if d <= k_a:
            return MAX_RW

        if a >= d:
            return MAX_RW

        # Avoid division by zero
        k_a_safe = max(k_a, 0.0001)

        alpha = -(1.0 / (p * k_a_safe))

        if u <= l_val or u <= 0:
            return MAX_RW

        # SSFA formula per CRE40.50
        try:
            numerator = math.exp(alpha * u) - math.exp(alpha * l_val)
            denominator = alpha * (u - l_val)

            if abs(denominator) < 1e-12:
                return MAX_RW

            rw = numerator / denominator
        except (OverflowError, ValueError):
            rw = MAX_RW

        # Concentration add-on per CRE40.56
        if pool.effective_number_of_obligors < CONCENTRATION_N_THRESHOLD:
            concentration_addon = CONCENTRATION_RW_ADDON * (
                CONCENTRATION_N_THRESHOLD - pool.effective_number_of_obligors
            )
            rw += concentration_addon

        return min(max(rw, 0.0), MAX_RW)

    @staticmethod
    def _apply_caps_and_floors(
        rw: float,
        tranche: SecuritizationTranche,
    ) -> float:
        """Apply regulatory risk weight caps and floors per CRE40.44-46.

        Floors:
        - Non-resecuritization: 15% per CRE40.44
        - Resecuritization: 100% per CRE40.63
        - STC: 10% per CRE40.73
        - CTP long: 8%, CTP short: 2% per CRE40.66

        Cap: 1250% for all positions per CRE40.46.

        Args:
            rw: Computed risk weight.
            tranche: Tranche for context.

        Returns:
            Adjusted risk weight.

        Reference:
            CRE40.44-46, CRE40.63, CRE40.66, CRE40.73.
        """
        # CTP floors per CRE40.66
        if tranche.is_ctp:
            floor = CTP_LONG_FLOOR if tranche.is_long else CTP_SHORT_FLOOR
            rw = max(rw, floor)

        # Resecuritization floor per CRE40.63
        elif tranche.is_resecuritization:
            rw = max(rw, RESEC_RW_FLOOR)

        # STC floor per CRE40.73
        elif tranche.is_stc:
            rw = max(rw, STC_RISK_WEIGHT_FLOOR)

        # Standard non-resec floor per CRE40.44
        else:
            rw = max(rw, MIN_RISK_WEIGHT_NON_RESEC)

        # 1250% cap per CRE40.46
        rw = min(rw, MAX_RW)

        return rw

    @staticmethod
    def _compute_k_g(pool: SecuritizationPool) -> float:
        """Compute pool capital ratio K_g per CRE40.48.

        K_g = Pool RWA / Pool EAD

        Represents the capital ratio that would apply if the
        underlying exposures were held directly (not securitized).

        Args:
            pool: Pool characteristics.

        Returns:
            K_g as a decimal (e.g., 0.08 for 8%).

        Reference:
            CRE40.48-49.
        """
        if pool.total_ead <= 0:
            return DEFAULT_POOL_CAPITAL_RATIO

        k_g = pool.pool_rwa / pool.total_ead
        return min(k_g, MAX_POOL_CAPITAL_RATIO)

    def compute_tranche_thickness(
        self, tranche: SecuritizationTranche
    ) -> str:
        """Classify tranche thickness per CRE40.52.

        Args:
            tranche: The tranche to classify.

        Returns:
            'THIN', 'STANDARD', or 'THICK'.

        Reference:
            CRE40.52; ERBA NPR Section IV.
        """
        thickness = tranche.detachment_point - tranche.attachment_point

        if thickness < TRANCHE_THICKNESS.thin_threshold:
            return "THIN"
        elif thickness > TRANCHE_THICKNESS.thick_threshold:
            return "THICK"
        else:
            return "STANDARD"

    @staticmethod
    def validate_tranche_structure(
        tranches: list[SecuritizationTranche],
    ) -> list[str]:
        """Validate tranche structure for consistency.

        Checks:
        - No overlapping tranches
        - Attachment < Detachment for all tranches
        - Complete waterfall coverage (optional warning)

        Args:
            tranches: List of tranches to validate.

        Returns:
            List of warning messages (empty if all checks pass).

        Reference:
            CRE40.41; BCBS 239 data quality.
        """
        warnings: list[str] = []

        for t in tranches:
            if t.attachment_point >= t.detachment_point:
                warnings.append(
                    f"Tranche {t.tranche_id}: A ({t.attachment_point}) >= D ({t.detachment_point})"
                )

        # Check for overlaps within same pool
        pool_tranches: dict[str, list[SecuritizationTranche]] = {}
        for t in tranches:
            pool_tranches.setdefault(t.pool_id, []).append(t)

        for pool_id, pts in pool_tranches.items():
            sorted_pts = sorted(pts, key=lambda x: x.attachment_point)
            for i in range(len(sorted_pts) - 1):
                if sorted_pts[i].detachment_point > sorted_pts[i + 1].attachment_point:
                    warnings.append(
                        f"Pool {pool_id}: Tranche {sorted_pts[i].tranche_id} "
                        f"overlaps with {sorted_pts[i + 1].tranche_id}"
                    )

            # Check coverage
            if sorted_pts and sorted_pts[0].attachment_point > 0.01:
                warnings.append(
                    f"Pool {pool_id}: No tranche covers first-loss "
                    f"(lowest A = {sorted_pts[0].attachment_point:.2%})"
                )
            if sorted_pts and sorted_pts[-1].detachment_point < 0.99:
                warnings.append(
                    f"Pool {pool_id}: Incomplete waterfall "
                    f"(highest D = {sorted_pts[-1].detachment_point:.2%})"
                )

        return warnings
