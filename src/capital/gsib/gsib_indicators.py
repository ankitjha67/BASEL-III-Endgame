"""FR Y-15 systemic indicators and G-SIB method 1 / method 2 scores.

Implements:

- Method 1 score (12 CFR 217.404): sum over systemic indicators of
  (indicator / aggregate global indicator amount) x 10,000 x indicator weight,
  with the substitutability sum capped at 100 basis points (§ 217.404(b)(2)).
- Weighted short-term wholesale funding (Table 1 to § 217.406): funding
  category (1-4) x remaining-maturity weights.
- Method 2 score (§ 217.405): indicator in $bn x coefficient (%), plus
    * current rule -- the STWF score of § 217.406(a):
      average weighted STWF / average RWA x 350;
    * 2026 proposal -- weighted STWF as a tenth indicator with coefficient
      23.003 and every coefficient divided by the GDP growth adjustment
      (revised § 217.405(c), FR Doc. 2026-05961).

All monetary inputs in USD millions ($M).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields, replace
from datetime import date
from typing import Optional

from src.capital.gsib.gsib_params import (
    DEFAULT_DENOMINATION_FACTORS,
    DEFAULT_RULE_VERSION,
    DEFAULT_VALIDATION_BOUNDS,
    INITIAL_GDP_GROWTH_ADJUSTMENT,
    LEGACY_STWF_CATEGORY,
    METHOD_1_SCALING_FACTOR,
    METHOD_2_INDICATOR_CATEGORY,
    MILLIONS_PER_BILLION,
    PERCENT,
    STWF_FIXED_FACTOR_CURRENT,
    STWF_MATURITY_BUCKETS,
    STWF_WEIGHTS,
    SUBSTITUTABILITY_CAP_BPS,
    DenominationFactors,
    GSIBIndicatorCategory,
    GSIBRuleVersion,
    IndicatorSpec,
    STWFMaturityBucket,
    ValidationBounds,
    method1_indicators,
    method2_coefficients_pct,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Input data
# =========================================================================


@dataclass(frozen=True)
class STWFComponent:
    """One cell of Table 1 to § 217.406: amount by funding category and maturity.

    Attributes:
        category: Funding category 1-4 (Table 1 to § 217.406).
        bucket: Remaining-maturity column.
        amount: Average daily amount over the prior calendar year ($M)
            (§ 217.406(b)(1)).
    """

    category: int
    bucket: STWFMaturityBucket
    amount: float

    def __post_init__(self) -> None:
        """Validate the category against Table 1 to § 217.406."""
        if self.category not in STWF_WEIGHTS:
            raise ValueError(f"STWF category must be 1-4, got {self.category}")


@dataclass
class GSIBIndicatorData:
    """FR Y-15 systemic indicator values for one bank holding company ($M).

    Field names match :class:`IndicatorSpec.name`. Under the 2026 proposal
    the averaged indicators (preamble § II.C) are reported as annual averages
    of daily or monthly values; supply them already averaged.

    STWF may be given three ways, in order of precedence:
    ``weighted_stwf_amount_reported`` (FR Y-15 Schedule G total);
    ``stwf_components`` (category x maturity cells); or the legacy
    maturity-only fields ``stwf_*_days``, which carry no funding category and
    are weighted as Category 4 (``LEGACY_STWF_CATEGORY``, conservative).
    """

    reporting_entity: str = ""
    reporting_date: Optional[date] = None
    assessment_year: Optional[int] = None

    total_exposures: float = 0.0
    intra_financial_system_assets: float = 0.0
    intra_financial_system_liabilities: float = 0.0
    securities_outstanding: float = 0.0
    payments_activity: float = 0.0
    assets_under_custody: float = 0.0
    underwriting_activity: float = 0.0
    trading_volume_fixed_income: float = 0.0
    trading_volume_equity_other: float = 0.0
    otc_derivatives_notional: float = 0.0
    trading_and_afs_securities: float = 0.0
    level_3_assets: float = 0.0
    cross_jurisdictional_claims: float = 0.0
    cross_jurisdictional_liabilities: float = 0.0

    stwf_components: list[STWFComponent] = field(default_factory=list)
    weighted_stwf_amount_reported: Optional[float] = None
    stwf_0_30_days: float = 0.0
    stwf_31_90_days: float = 0.0
    stwf_91_180_days: float = 0.0
    stwf_181_365_days: float = 0.0

    avg_risk_weighted_assets: float = 0.0
    """§ 217.406(a)(2) denominator (current rule only)."""
    avg_total_assets: float = 0.0
    """Average total consolidated assets (data-quality cross-checks only)."""

    def get_indicator_value(self, indicator_name: str) -> float:
        """Raw value of a systemic indicator by name ($M).

        Raises:
            ValueError: If the name is not a systemic indicator field.
        """
        if indicator_name == "weighted_stwf_amount":
            return weighted_stwf(self).weighted_amount
        valid = {f.name for f in fields(self)} - _NON_INDICATOR_FIELDS
        if indicator_name not in valid:
            raise ValueError(f"Unknown indicator '{indicator_name}'. Valid: {sorted(valid)}")
        return float(getattr(self, indicator_name))

    def get_stwf_amounts(self) -> list[float]:
        """Legacy maturity-only STWF amounts in Table 1 column order ($M)."""
        return [
            self.stwf_0_30_days,
            self.stwf_31_90_days,
            self.stwf_91_180_days,
            self.stwf_181_365_days,
        ]

    def with_indicator(self, indicator_name: str, value: float) -> GSIBIndicatorData:
        """Copy of the data with one indicator replaced (sensitivity analysis)."""
        if indicator_name == "weighted_stwf_amount":
            return replace(self, weighted_stwf_amount_reported=value)
        self.get_indicator_value(indicator_name)
        return replace(self, **{indicator_name: value})


_NON_INDICATOR_FIELDS = {
    "reporting_entity",
    "reporting_date",
    "assessment_year",
    "stwf_components",
    "weighted_stwf_amount_reported",
    "stwf_0_30_days",
    "stwf_31_90_days",
    "stwf_91_180_days",
    "stwf_181_365_days",
    "avg_risk_weighted_assets",
    "avg_total_assets",
}


# =========================================================================
#  Result data
# =========================================================================


@dataclass
class IndicatorValue:
    """One indicator's contribution to a method score.

    Attributes:
        indicator_name: Indicator field name.
        raw_value: Bank's value ($M).
        denomination_factor: Method 1 aggregate global amount ($M); for
            method 2 the effective coefficient in % per $bn.
        weighted_score_bps: Contribution to the score (basis points).
        fr_y15_line: FR Y-15 schedule reference.
    """

    indicator_name: str
    raw_value: float
    denomination_factor: float
    weighted_score_bps: float = 0.0
    fr_y15_line: str = ""


@dataclass
class CategoryScore:
    """Score of one systemic category.

    Attributes:
        category: The category.
        indicators: Indicator contributions.
        raw_score_bps: Sum before any cap.
        capped_score_bps: Sum after the § 217.404(b)(2) substitutability cap.
        cap_applied: Whether the cap bound.
    """

    category: GSIBIndicatorCategory
    indicators: list[IndicatorValue] = field(default_factory=list)
    raw_score_bps: float = 0.0
    capped_score_bps: float = 0.0
    cap_applied: bool = False


@dataclass
class STWFBucketValue:
    """Weighted STWF for one category x maturity cell of Table 1 to § 217.406."""

    category: int
    bucket: STWFMaturityBucket
    weight: float
    amount: float = 0.0
    weighted_amount: float = 0.0


@dataclass
class STWFScore:
    """Weighted short-term wholesale funding and its method 2 score.

    Attributes:
        buckets: Cell-by-cell breakdown (empty when a reported total is used).
        total_wholesale_funding: Unweighted STWF ($M).
        weighted_amount: Weighted STWF amount ($M).
        denominator: Average RWA used under the current rule ($M; 0 under
            the proposal, which removes the denominator).
        stwf_ratio: weighted_amount / denominator (current rule only).
        coefficient: 350 (current) or the proposal coefficient in % per $bn.
        stwf_score_bps: Contribution to the method 2 score.
        source: How the weighted amount was obtained.
    """

    buckets: list[STWFBucketValue] = field(default_factory=list)
    total_wholesale_funding: float = 0.0
    weighted_amount: float = 0.0
    denominator: float = 0.0
    stwf_ratio: float = 0.0
    coefficient: float = 0.0
    stwf_score_bps: float = 0.0
    source: str = ""

    @property
    def total_weighted_funding(self) -> float:
        """Alias of :attr:`weighted_amount`."""
        return self.weighted_amount


# =========================================================================
#  Weighted STWF -- Table 1 to § 217.406
# =========================================================================


def weighted_stwf(indicator_data: GSIBIndicatorData) -> STWFScore:
    """Weighted short-term wholesale funding amount (§ 217.406(b), Table 1).

    Each component is weighted by its funding category (1-4) and remaining
    maturity column; the weighted amount is the average over each business
    day of the prior calendar year (supply averaged amounts).

    Returns:
        STWFScore with the weighted amount and breakdown (score fields unset).
    """
    if indicator_data.weighted_stwf_amount_reported is not None:
        return STWFScore(
            weighted_amount=float(indicator_data.weighted_stwf_amount_reported),
            source="FR Y-15 Schedule G reported total",
        )

    components = list(indicator_data.stwf_components)
    source = "category x maturity components (Table 1 to § 217.406)"
    if not components and any(a > 0 for a in indicator_data.get_stwf_amounts()):
        components = [
            STWFComponent(LEGACY_STWF_CATEGORY, bucket, amount)
            for bucket, amount in zip(
                STWF_MATURITY_BUCKETS, indicator_data.get_stwf_amounts(), strict=True
            )
        ]
        source = (
            f"maturity-only inputs weighted as Category {LEGACY_STWF_CATEGORY} "
            "(no funding category supplied)"
        )
        logger.warning(
            "STWF supplied without funding categories; applying Category %d weights",
            LEGACY_STWF_CATEGORY,
        )

    cells: list[STWFBucketValue] = []
    total = weighted = 0.0
    for comp in components:
        weight = STWF_WEIGHTS[comp.category][STWF_MATURITY_BUCKETS.index(comp.bucket)]
        cells.append(
            STWFBucketValue(comp.category, comp.bucket, weight, comp.amount, comp.amount * weight)
        )
        total += comp.amount
        weighted += comp.amount * weight
    return STWFScore(
        buckets=cells, total_wholesale_funding=total, weighted_amount=weighted, source=source
    )


def calculate_stwf_score(
    indicator_data: GSIBIndicatorData,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
    gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT,
) -> STWFScore:
    """STWF contribution to the method 2 score.

    Current rule, § 217.406(a): (1) the average weighted STWF amount,
    (2) divided by average risk-weighted assets, (3) multiplied by 350.

    Proposal, revised § 217.405(b)-(c): weighted STWF amount in $bn x
    (23.003% / GDP growth adjustment) -- "remove the average risk-weighted
    assets denominator" (preamble § II.B.i).
    """
    stwf = weighted_stwf(indicator_data)
    if version == GSIBRuleVersion.CURRENT_RULE:
        denom = indicator_data.avg_risk_weighted_assets
        stwf.coefficient = STWF_FIXED_FACTOR_CURRENT
        stwf.denominator = denom
        if denom <= 0:
            if stwf.weighted_amount > 0:
                raise ValueError("§ 217.406(a)(2) requires average risk-weighted assets > 0")
            return stwf
        stwf.stwf_ratio = stwf.weighted_amount / denom
        stwf.stwf_score_bps = stwf.stwf_ratio * STWF_FIXED_FACTOR_CURRENT
        return stwf

    coeff = method2_coefficients_pct(version)["weighted_stwf_amount"] / gdp_growth_adjustment
    stwf.coefficient = coeff
    stwf.stwf_score_bps = stwf.weighted_amount / MILLIONS_PER_BILLION * coeff / PERCENT
    return stwf


# =========================================================================
#  Method 1 -- § 217.404
# =========================================================================


def calculate_indicator_score(
    raw_value: float,
    denomination_factor: float,
    indicator_weight: float,
    scaling_factor: float = METHOD_1_SCALING_FACTOR,
) -> float:
    """Systemic indicator score in basis points (§ 217.404(b)(1)).

    score = (indicator / aggregate global indicator amount) x 10,000 x weight.
    Negative indicator values are floored at zero.
    """
    if denomination_factor <= 0:
        raise ValueError("aggregate global indicator amount must be positive")
    return max(raw_value, 0.0) / denomination_factor * scaling_factor * indicator_weight


def calculate_category_scores(
    indicator_data: GSIBIndicatorData,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
) -> list[CategoryScore]:
    """Method 1 category scores, with the substitutability cap (§ 217.404).

    Raises:
        ValueError: If an indicator with a positive value has no published
            aggregate global indicator amount.
    """
    specs = method1_indicators(version)
    by_cat: dict[GSIBIndicatorCategory, list[IndicatorSpec]] = {}
    for spec in specs:
        by_cat.setdefault(spec.category, []).append(spec)

    results: list[CategoryScore] = []
    for category, cat_specs in by_cat.items():
        values: list[IndicatorValue] = []
        raw = 0.0
        for spec in cat_specs:
            amount = indicator_data.get_indicator_value(spec.name)
            denom = denomination_factors.get(spec.name)
            if denom is None:
                if amount > 0:
                    raise ValueError(
                        f"No aggregate global indicator amount for '{spec.name}'; supply it in "
                        "DenominationFactors (published by the Board under § 217.401)"
                    )
                logger.info(
                    "No aggregate global amount for %s and no reported value; scored 0", spec.name
                )
                values.append(IndicatorValue(spec.name, amount, 0.0, 0.0, spec.fr_y15_line))
                continue
            score = calculate_indicator_score(amount, denom, spec.weight)
            values.append(IndicatorValue(spec.name, amount, denom, score, spec.fr_y15_line))
            raw += score
        capped, cap_applied = raw, False
        if category == GSIBIndicatorCategory.SUBSTITUTABILITY and raw > SUBSTITUTABILITY_CAP_BPS:
            capped, cap_applied = SUBSTITUTABILITY_CAP_BPS, True
        results.append(CategoryScore(category, values, raw, capped, cap_applied))
    return results


def calculate_method1_score(
    indicator_data: GSIBIndicatorData,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
) -> tuple[float, list[CategoryScore]]:
    """Method 1 score: sum of systemic indicator scores (§ 217.404(a))."""
    cats = calculate_category_scores(indicator_data, denomination_factors, version)
    return sum(c.capped_score_bps for c in cats), cats


# =========================================================================
#  Method 2 -- § 217.405
# =========================================================================


def calculate_method2_score(
    indicator_data: GSIBIndicatorData,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
    gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT,
) -> tuple[float, list[CategoryScore], STWFScore]:
    """Method 2 score (§ 217.405).

    Systemic indicator score = indicator in billions of dollars x coefficient
    (Table 1 to § 217.405, in %). Under the proposal each coefficient is
    divided by the GDP growth adjustment (revised § 217.405(c)(2)) and the
    weighted STWF amount is the tenth indicator; under the current rule the
    STWF score of § 217.406 is added (§ 217.405(a)(1)(ii)).

    Returns:
        (score_bps, category_scores, stwf_score); the STWF category appears in
        ``category_scores`` under both versions.
    """
    if gdp_growth_adjustment <= 0:
        raise ValueError("GDP growth adjustment must be positive")
    coeffs = method2_coefficients_pct(version)
    stwf = calculate_stwf_score(indicator_data, version, gdp_growth_adjustment)

    by_cat: dict[GSIBIndicatorCategory, CategoryScore] = {}
    for name, coeff_pct in coeffs.items():
        if name == "weighted_stwf_amount":
            continue
        eff = (
            coeff_pct / gdp_growth_adjustment
            if version == GSIBRuleVersion.PROPOSAL_2026
            else coeff_pct
        )
        amount = indicator_data.get_indicator_value(name)
        score = max(amount, 0.0) / MILLIONS_PER_BILLION * eff / PERCENT
        cat = METHOD_2_INDICATOR_CATEGORY[name]
        cs = by_cat.setdefault(cat, CategoryScore(cat))
        cs.indicators.append(IndicatorValue(name, amount, eff, score))
        cs.raw_score_bps += score
        cs.capped_score_bps += score

    stwf_cat = CategoryScore(
        GSIBIndicatorCategory.SHORT_TERM_WHOLESALE_FUNDING,
        [
            IndicatorValue(
                "weighted_stwf_amount",
                stwf.weighted_amount,
                stwf.coefficient,
                stwf.stwf_score_bps,
                "Schedule G",
            )
        ],
        stwf.stwf_score_bps,
        stwf.stwf_score_bps,
    )
    categories = list(by_cat.values()) + [stwf_cat]
    total = sum(c.capped_score_bps for c in categories)
    logger.info(
        "Method 2 score (%s): %.1f bp (STWF %.1f bp)", version.value, total, stwf.stwf_score_bps
    )
    return total, categories, stwf


# =========================================================================
#  Validation
# =========================================================================


def validate_indicator_data(
    indicator_data: GSIBIndicatorData,
    bounds: ValidationBounds = DEFAULT_VALIDATION_BOUNDS,
) -> list[str]:
    """Plausibility checks on FR Y-15 inputs (BCBS 239 / SR 11-7).

    Returns:
        Warning messages (empty if all checks pass).
    """
    warnings: list[str] = []
    te = indicator_data.total_exposures
    if te == 0:
        warnings.append("Total exposures is zero; it is required for both methods.")
    elif te < bounds.min_total_exposures:
        warnings.append(f"Total exposures ({te:,.0f} $M) below the Category I plausibility bound.")
    elif te > bounds.max_total_exposures:
        warnings.append(f"Total exposures ({te:,.0f} $M) above the plausibility bound; verify.")
    for f in fields(indicator_data):
        if f.name in _NON_INDICATOR_FIELDS:
            continue
        if getattr(indicator_data, f.name) < 0:
            warnings.append(f"Indicator '{f.name}' is negative.")
    stwf = weighted_stwf(indicator_data)
    if any(c.amount < 0 for c in indicator_data.stwf_components) or any(
        a < 0 for a in indicator_data.get_stwf_amounts()
    ):
        warnings.append("Negative short-term wholesale funding amount.")
    if te > 0 and stwf.total_wholesale_funding > bounds.max_stwf_to_total_exposures * te:
        warnings.append("Short-term wholesale funding exceeds total exposures.")
    if (
        not indicator_data.stwf_components
        and indicator_data.weighted_stwf_amount_reported is None
        and any(a > 0 for a in indicator_data.get_stwf_amounts())
    ):
        warnings.append(
            f"STWF supplied without funding categories; Category {LEGACY_STWF_CATEGORY} "
            "weights applied (conservative)."
        )
    return warnings


def calculate_reporting_period(assessment_year: int) -> tuple[date, date]:
    """Calendar-year measurement period for a G-SIB assessment (§ 217.403(a))."""
    return date(assessment_year, 1, 1), date(assessment_year, 12, 31)
