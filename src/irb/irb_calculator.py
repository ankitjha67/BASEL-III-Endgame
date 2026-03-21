"""IRB (Internal Ratings-Based) Capital Calculator per BCBS d424.

Implements the Foundation IRB (F-IRB) and Advanced IRB (A-IRB) risk weight
functions for credit risk capital requirements. This module exists for
COMPARISON PURPOSES ONLY as the US Basel III Endgame 2026 re-proposal
eliminates IRB for most exposure classes.

The core formula is the Vasicek single-factor model:
    K = LGD * [N((1-R)^-0.5 * G(PD) + (R/(1-R))^0.5 * G(0.999)) - PD*LGD]
    RWA = K * 12.5 * EAD * scaling_factor

References:
    - BCBS d424: "Basel III: Finalising Post-Crisis Reforms" (Dec 2017)
    - BCBS d424, CRE30-CRE36: IRB approach
    - BCBS d424, CRE31: Corporate, sovereign, bank exposures
    - BCBS d424, CRE32: Retail exposures

Model ID: FNBC-BIII-2026-001
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from scipy.stats import norm  # type: ignore[import-untyped]

from src.irb.irb_params import (
    CONFIDENCE_LEVEL,
    CORPORATE_CORRELATION_K,
    CORPORATE_CORRELATION_R_MAX,
    CORPORATE_CORRELATION_R_MIN,
    EFFECTIVE_MATURITY_DEFAULT,
    EFFECTIVE_MATURITY_MAX,
    EFFECTIVE_MATURITY_MIN,
    IRB_PARAMS,
    LGD_FLOORS,
    MATURITY_ADJUSTMENT_B_COEFFICIENTS,
    OUTPUT_FLOOR_PERCENTAGE,
    SCALING_FACTOR,
    SME_CORRELATION_ADJUSTMENT_FACTOR,
    SME_REVENUE_THRESHOLD_HIGH,
    SME_REVENUE_THRESHOLD_LOW,
    SUPERVISORY_LGD,
    SLOTTING_RISK_WEIGHTS,
    SLOTTING_RISK_WEIGHTS_HVCRE,
    IRBApproach,
    IRBExposureClass,
    IRBParameterSet,
    SpecializedLendingCategory,
)


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class IRBExposure:
    """Single exposure for IRB capital calculation.

    Represents a credit exposure with all parameters needed to compute
    IRB risk-weighted assets per BCBS d424 CRE30-CRE36.

    Attributes:
        exposure_id: Unique identifier for the exposure.
        exposure_class: IRB exposure classification.
        approach: F-IRB or A-IRB.
        ead: Exposure at default in $M.
        pd: Probability of default (annual, decimal).
        lgd: Loss given default (decimal). For F-IRB, supervisory values used.
        maturity: Effective maturity in years. For F-IRB, defaults to 2.5y.
        annual_revenue: Annual revenue in $M (for SME correlation adjustment).
        is_defaulted: Whether the exposure has defaulted.
        collateral_type: Type of collateral (for F-IRB LGD lookup).
    """
    exposure_id: str
    exposure_class: IRBExposureClass
    approach: IRBApproach = IRBApproach.FOUNDATION
    ead: float = 0.0
    pd: float = 0.01
    lgd: Optional[float] = None
    maturity: Optional[float] = None
    annual_revenue: Optional[float] = None
    is_defaulted: bool = False
    collateral_type: Optional[str] = None


@dataclass
class IRBResult:
    """Result of IRB capital calculation for a single exposure.

    Per BCBS d424 CRE31.1: Contains the capital requirement (K),
    risk-weighted assets, expected loss, and intermediate calculations.

    Attributes:
        exposure_id: Identifier of the source exposure.
        exposure_class: IRB classification.
        ead: Exposure at default ($M).
        pd: PD used (floored).
        lgd: LGD used (floored for A-IRB).
        correlation: Asset correlation R.
        maturity_adjustment: Maturity adjustment factor.
        capital_requirement_k: Capital requirement K (decimal).
        rwa: Risk-weighted assets ($M).
        expected_loss: Expected loss = PD * LGD * EAD ($M).
        risk_weight: Effective risk weight (decimal).
    """
    exposure_id: str
    exposure_class: IRBExposureClass
    ead: float
    pd: float
    lgd: float
    correlation: float
    maturity_adjustment: float
    capital_requirement_k: float
    rwa: float
    expected_loss: float
    risk_weight: float


@dataclass
class IRBPortfolioResult:
    """Aggregated IRB results for a portfolio of exposures.

    Per BCBS d424 CRE31.2: Portfolio-level RWA with scaling factor.

    Attributes:
        total_ead: Total exposure at default ($M).
        total_rwa: Total risk-weighted assets ($M).
        total_expected_loss: Total expected loss ($M).
        weighted_avg_rw: Weighted average risk weight.
        exposure_results: Individual exposure results.
        output_floor_rwa: RWA under output floor (72.5% of SA RWA).
        binding_rwa: Higher of IRB RWA and floor RWA.
    """
    total_ead: float = 0.0
    total_rwa: float = 0.0
    total_expected_loss: float = 0.0
    weighted_avg_rw: float = 0.0
    exposure_results: list[IRBResult] = field(default_factory=list)
    output_floor_rwa: Optional[float] = None
    binding_rwa: Optional[float] = None


# =========================================================================
#  Core IRB Functions
# =========================================================================

def compute_asset_correlation(
    pd: float,
    exposure_class: IRBExposureClass,
    annual_revenue: Optional[float] = None,
) -> float:
    """Compute asset correlation R for the Vasicek single-factor model.

    Per BCBS d424 CRE31.6, para 44 (corporate/bank/sovereign):
        R = 0.12 * (1 - exp(-50*PD)) / (1 - exp(-50))
          + 0.24 * [1 - (1 - exp(-50*PD)) / (1 - exp(-50))]

    Per BCBS d424 CRE31.8, para 46 (SME adjustment):
        R_sme = R - 0.04 * (1 - (max(5, min(S, 50)) - 5) / 45)

    Per BCBS d424 CRE32.5 (retail mortgage): R = 0.15 (fixed)
    Per BCBS d424 CRE32.7 (QRE): R = 0.04 (fixed)
    Per BCBS d424 CRE32.9 (other retail): Uses k=35 decay

    Args:
        pd: Probability of default (decimal).
        exposure_class: IRB exposure class.
        annual_revenue: Annual revenue in $M (for SME adjustment).

    Returns:
        Asset correlation R (decimal).
    """
    params = IRB_PARAMS.get(exposure_class)
    if params is None:
        # Fallback to corporate parameters for unlisted classes
        params = IRB_PARAMS[IRBExposureClass.CORPORATE]

    if params.fixed_correlation:
        return params.r_min  # r_min == r_max for fixed correlation

    # Exponential weighting function
    exp_term = (1.0 - math.exp(-params.r_decay_k * pd)) / (
        1.0 - math.exp(-params.r_decay_k)
    )

    r = params.r_min * exp_term + params.r_max * (1.0 - exp_term)

    # SME firm-size correlation adjustment per CRE31.8
    if exposure_class == IRBExposureClass.CORPORATE_SME and annual_revenue is not None:
        s = max(SME_REVENUE_THRESHOLD_LOW, min(annual_revenue, SME_REVENUE_THRESHOLD_HIGH))
        sme_adj = SME_CORRELATION_ADJUSTMENT_FACTOR * (
            1.0 - (s - SME_REVENUE_THRESHOLD_LOW)
            / (SME_REVENUE_THRESHOLD_HIGH - SME_REVENUE_THRESHOLD_LOW)
        )
        r = r - sme_adj

    return r


def compute_maturity_adjustment(pd: float, maturity: float) -> float:
    """Compute the maturity adjustment factor for IRB capital.

    Per BCBS d424 CRE31.6, para 44:
        b(PD) = (0.11852 - 0.05478 * ln(PD))^2
        MA = (1 + (M - 2.5) * b(PD)) / (1 - 1.5 * b(PD))

    The maturity adjustment captures the mark-to-market risk of
    longer-maturity exposures. Retail exposures are exempt.

    Args:
        pd: Probability of default (decimal, must be > 0).
        maturity: Effective maturity in years (1 to 5).

    Returns:
        Maturity adjustment factor (>= 1.0 for M > 2.5).
    """
    if pd <= 0:
        pd = 1e-10  # Avoid log(0)

    a, b_coeff = MATURITY_ADJUSTMENT_B_COEFFICIENTS
    b_pd = (a + b_coeff * math.log(pd)) ** 2

    # Clamp maturity
    m = max(EFFECTIVE_MATURITY_MIN, min(maturity, EFFECTIVE_MATURITY_MAX))

    adjustment = (1.0 + (m - 2.5) * b_pd) / (1.0 - 1.5 * b_pd)
    return adjustment


def compute_capital_requirement_k(
    pd: float,
    lgd: float,
    correlation: float,
    maturity_adjustment: float = 1.0,
) -> float:
    """Compute the IRB capital requirement K using the Vasicek formula.

    Per BCBS d424 CRE31.6, para 44:
        K = [LGD * N((1-R)^(-0.5) * G(PD) + (R/(1-R))^(0.5) * G(0.999))
             - PD * LGD] * MA

    Where:
        N() = standard normal CDF
        G() = standard normal inverse CDF (quantile function)
        R   = asset correlation
        MA  = maturity adjustment

    Args:
        pd: Probability of default (decimal).
        lgd: Loss given default (decimal).
        correlation: Asset correlation R.
        maturity_adjustment: Maturity adjustment factor.

    Returns:
        Capital requirement K (decimal, to be multiplied by 12.5 * EAD for RWA).
    """
    if pd >= 1.0:
        # Defaulted exposure: K = max(0, LGD - EL_best_estimate)
        # Simplified: K = 0 for defaulted (EL fully provisioned)
        return 0.0

    if pd <= 0.0:
        return 0.0

    # Standard normal inverse CDF
    g_pd = norm.ppf(pd)
    g_confidence = norm.ppf(CONFIDENCE_LEVEL)

    # Vasicek conditional default probability
    conditional_pd = norm.cdf(
        (1.0 - correlation) ** (-0.5) * g_pd
        + (correlation / (1.0 - correlation)) ** 0.5 * g_confidence
    )

    # Capital requirement
    k = (lgd * conditional_pd - pd * lgd) * maturity_adjustment
    return max(0.0, k)


def compute_risk_weight(capital_k: float) -> float:
    """Convert capital requirement K to risk weight.

    Per BCBS d424 CRE31.6: RW = K * 12.5
    Where 12.5 is the reciprocal of the 8% minimum capital ratio.

    Args:
        capital_k: Capital requirement K (decimal).

    Returns:
        Risk weight (decimal, e.g. 0.50 = 50%).
    """
    return capital_k * 12.5


def compute_rwa(
    capital_k: float,
    ead: float,
    scaling_factor: float = SCALING_FACTOR,
) -> float:
    """Compute risk-weighted assets from capital requirement.

    Per BCBS d424 CRE31.2: RWA = K * 12.5 * EAD * 1.06

    Args:
        capital_k: Capital requirement K (decimal).
        ead: Exposure at default ($M).
        scaling_factor: IRB scaling factor (default 1.06).

    Returns:
        Risk-weighted assets ($M).
    """
    return capital_k * 12.5 * ead * scaling_factor


# =========================================================================
#  LGD Resolution
# =========================================================================

def resolve_lgd(
    exposure: IRBExposure,
) -> float:
    """Resolve the LGD for an exposure based on approach and collateral.

    Per BCBS d424 CRE31.4 (F-IRB): Uses supervisory LGD values.
    Per BCBS d424 CRE31.4 (A-IRB): Uses bank-estimated LGD with floors.

    Args:
        exposure: The IRB exposure.

    Returns:
        LGD value (decimal).
    """
    if exposure.approach == IRBApproach.FOUNDATION:
        # F-IRB: use supervisory LGD
        if exposure.collateral_type == "financial":
            return SUPERVISORY_LGD.eligible_financial_collateral_lgd
        elif exposure.collateral_type == "receivables":
            return SUPERVISORY_LGD.eligible_receivables_lgd
        elif exposure.collateral_type == "cre_rre":
            return SUPERVISORY_LGD.eligible_cre_rre_lgd
        elif exposure.collateral_type == "other_physical":
            return SUPERVISORY_LGD.other_physical_collateral_lgd
        elif exposure.collateral_type == "subordinated":
            return SUPERVISORY_LGD.subordinated
        else:
            return SUPERVISORY_LGD.senior_unsecured

    # A-IRB: use bank-estimated LGD with floors
    lgd = exposure.lgd if exposure.lgd is not None else 0.45

    # Apply LGD floors per exposure class
    if exposure.exposure_class == IRBExposureClass.RETAIL_MORTGAGE:
        lgd = max(lgd, LGD_FLOORS.retail_mortgage)
    elif exposure.exposure_class == IRBExposureClass.RETAIL_QUALIFYING_REVOLVING:
        if exposure.collateral_type:
            lgd = max(lgd, LGD_FLOORS.retail_qre_secured)
        else:
            lgd = max(lgd, LGD_FLOORS.retail_qre_unsecured)
    elif exposure.exposure_class == IRBExposureClass.RETAIL_OTHER:
        if exposure.collateral_type:
            lgd = max(lgd, LGD_FLOORS.retail_other_secured)
        else:
            lgd = max(lgd, LGD_FLOORS.retail_other_unsecured)
    else:
        # Corporate/bank/sovereign
        if exposure.collateral_type == "financial":
            lgd = max(lgd, LGD_FLOORS.secured_financial_collateral)
        elif exposure.collateral_type == "receivables":
            lgd = max(lgd, LGD_FLOORS.secured_receivables)
        elif exposure.collateral_type == "cre_rre":
            lgd = max(lgd, LGD_FLOORS.secured_cre_rre)
        elif exposure.collateral_type == "other_physical":
            lgd = max(lgd, LGD_FLOORS.secured_other_physical)
        else:
            lgd = max(lgd, LGD_FLOORS.unsecured_corporate)

    return lgd


# =========================================================================
#  Single Exposure Calculator
# =========================================================================

def calculate_irb_single(exposure: IRBExposure) -> IRBResult:
    """Calculate IRB capital requirement for a single exposure.

    Implements the full IRB risk weight function per BCBS d424 CRE31-CRE32:
    1. Floor PD
    2. Resolve LGD (supervisory or bank-estimated with floors)
    3. Compute asset correlation R (with SME adjustment if applicable)
    4. Compute maturity adjustment (corporate/bank/sovereign only)
    5. Compute capital requirement K via Vasicek formula
    6. Compute RWA = K * 12.5 * EAD * 1.06

    Args:
        exposure: The IRB exposure to calculate.

    Returns:
        IRBResult with all computed values.
    """
    params = IRB_PARAMS.get(exposure.exposure_class, IRB_PARAMS[IRBExposureClass.CORPORATE])

    # Step 1: Floor PD
    pd = max(exposure.pd, params.pd_floor) if not exposure.is_defaulted else 1.0

    # Step 2: Resolve LGD
    lgd = resolve_lgd(exposure)

    # Step 3: Asset correlation
    correlation = compute_asset_correlation(
        pd=pd,
        exposure_class=exposure.exposure_class,
        annual_revenue=exposure.annual_revenue,
    )

    # Step 4: Maturity adjustment
    if params.maturity_adjustment_applies:
        maturity = exposure.maturity if exposure.maturity is not None else EFFECTIVE_MATURITY_DEFAULT
        maturity = max(EFFECTIVE_MATURITY_MIN, min(maturity, EFFECTIVE_MATURITY_MAX))
        ma = compute_maturity_adjustment(pd, maturity)
    else:
        ma = 1.0

    # Step 5: Capital requirement K
    k = compute_capital_requirement_k(pd, lgd, correlation, ma)

    # Step 6: RWA
    rwa = compute_rwa(k, exposure.ead)

    # Expected loss
    el = pd * lgd * exposure.ead

    # Risk weight
    rw = compute_risk_weight(k) * SCALING_FACTOR

    return IRBResult(
        exposure_id=exposure.exposure_id,
        exposure_class=exposure.exposure_class,
        ead=exposure.ead,
        pd=pd,
        lgd=lgd,
        correlation=correlation,
        maturity_adjustment=ma,
        capital_requirement_k=k,
        rwa=rwa,
        expected_loss=el,
        risk_weight=rw,
    )


# =========================================================================
#  Portfolio Calculator
# =========================================================================

def calculate_irb_portfolio(
    exposures: list[IRBExposure],
    sa_rwa: Optional[float] = None,
) -> IRBPortfolioResult:
    """Calculate IRB capital for a portfolio of exposures.

    Per BCBS d424 CRE31.2: Aggregates individual exposure RWA and applies
    the scaling factor. Optionally computes the output floor.

    Args:
        exposures: List of IRB exposures.
        sa_rwa: Standardized approach RWA ($M) for output floor comparison.

    Returns:
        IRBPortfolioResult with aggregated results.
    """
    if not exposures:
        return IRBPortfolioResult()

    results = [calculate_irb_single(exp) for exp in exposures]

    total_ead = sum(r.ead for r in results)
    total_rwa = sum(r.rwa for r in results)
    total_el = sum(r.expected_loss for r in results)

    weighted_avg_rw = total_rwa / total_ead if total_ead > 0 else 0.0

    portfolio = IRBPortfolioResult(
        total_ead=total_ead,
        total_rwa=total_rwa,
        total_expected_loss=total_el,
        weighted_avg_rw=weighted_avg_rw,
        exposure_results=results,
    )

    # Output floor calculation (for comparison only — NOT applied in US)
    if sa_rwa is not None:
        portfolio.output_floor_rwa = sa_rwa * OUTPUT_FLOOR_PERCENTAGE
        portfolio.binding_rwa = max(total_rwa, portfolio.output_floor_rwa)

    return portfolio


# =========================================================================
#  Specialized Lending (Supervisory Slotting)
# =========================================================================

def calculate_slotting_rwa(
    ead: float,
    category: SpecializedLendingCategory,
    is_hvcre: bool = False,
) -> float:
    """Calculate RWA for specialized lending using supervisory slotting.

    Per BCBS d424 CRE33.2-33.3: Banks that do not meet IRB requirements
    for specialized lending may use supervisory slotting criteria.

    Args:
        ead: Exposure at default ($M).
        category: Supervisory slotting category.
        is_hvcre: Whether the exposure is HVCRE.

    Returns:
        Risk-weighted assets ($M).
    """
    rw_table = SLOTTING_RISK_WEIGHTS_HVCRE if is_hvcre else SLOTTING_RISK_WEIGHTS
    rw = rw_table.get(category, 2.50)
    return ead * rw


# =========================================================================
#  SA vs IRB Comparison
# =========================================================================

@dataclass
class SAvsIRBComparison:
    """Comparison of SA and IRB RWA for analysis purposes.

    Per US Basel III Endgame 2026: The US eliminates IRB for most classes.
    This comparison quantifies the impact of that policy change.

    Attributes:
        sa_rwa: Standardized approach RWA ($M).
        irb_rwa: IRB approach RWA ($M).
        floor_rwa: Output floor RWA (72.5% of SA) ($M).
        rwa_difference: SA minus IRB ($M, positive = SA is higher).
        rwa_ratio: IRB/SA ratio.
        floor_binding: Whether the output floor would bind.
        capital_impact: Additional capital needed under SA vs IRB ($M).
    """
    sa_rwa: float
    irb_rwa: float
    floor_rwa: float
    rwa_difference: float
    rwa_ratio: float
    floor_binding: bool
    capital_impact: float


def compare_sa_vs_irb(
    sa_rwa: float,
    irb_rwa: float,
    cet1_ratio: float = 0.045,
) -> SAvsIRBComparison:
    """Compare SA and IRB RWA for policy analysis.

    Quantifies the impact of the US Basel III Endgame decision to
    eliminate IRB. The output floor (72.5% of SA RWA) is computed
    for international comparison but is NOT part of the US proposal.

    Per BCBS d424, para 4: Output floor = 72.5% of standardized RWA.
    Per US ERBA NPR: IRB eliminated entirely for most exposures.

    Args:
        sa_rwa: RWA under standardized approach ($M).
        irb_rwa: RWA under IRB approach ($M).
        cet1_ratio: CET1 minimum ratio for capital impact (default 4.5%).

    Returns:
        SAvsIRBComparison with full analysis.
    """
    floor_rwa = sa_rwa * OUTPUT_FLOOR_PERCENTAGE
    rwa_diff = sa_rwa - irb_rwa
    rwa_ratio = irb_rwa / sa_rwa if sa_rwa > 0 else 0.0
    floor_binding = irb_rwa < floor_rwa
    capital_impact = rwa_diff * cet1_ratio

    return SAvsIRBComparison(
        sa_rwa=sa_rwa,
        irb_rwa=irb_rwa,
        floor_rwa=floor_rwa,
        rwa_difference=rwa_diff,
        rwa_ratio=rwa_ratio,
        floor_binding=floor_binding,
        capital_impact=capital_impact,
    )
