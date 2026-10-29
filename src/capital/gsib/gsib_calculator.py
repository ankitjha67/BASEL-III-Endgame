"""G-SIB surcharge calculator: method 1, method 2 and the binding surcharge.

12 CFR 217.403(a): the GSIB surcharge is the greater of the method 1
surcharge (Table 1 to § 217.403, method 1 score per § 217.404) and the
method 2 surcharge (Table 2 to § 217.403 under the current rule; revised
§ 217.403(c) under the March 2026 proposal, FR Doc. 2026-05961), with the
effective-date mechanics of § 217.403(d).

All monetary amounts in USD millions ($M); surcharges in percent of RWA.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from src.capital.gsib.gsib_indicators import (
    CategoryScore,
    GSIBIndicatorData,
    STWFComponent,
    STWFScore,
    calculate_method1_score,
    calculate_method2_score,
    validate_indicator_data,
)
from src.capital.gsib.gsib_params import (
    DEFAULT_DENOMINATION_FACTORS,
    DEFAULT_RULE_VERSION,
    DEFAULT_VALIDATION_BOUNDS,
    GSIB_IDENTIFICATION_THRESHOLD_BPS,
    INITIAL_GDP_GROWTH_ADJUSTMENT,
    METHOD_1_HIGHER_BASE_PCT,
    METHOD_1_HIGHER_STEP_BPS,
    METHOD_1_HIGHER_STEP_PCT,
    METHOD_1_HIGHER_THRESHOLD_BPS,
    METHOD_1_SURCHARGE_BANDS,
    METHOD_2_HIGHER_BASE_PCT_CURRENT,
    METHOD_2_HIGHER_STEP_BPS_CURRENT,
    METHOD_2_HIGHER_STEP_PCT_CURRENT,
    METHOD_2_HIGHER_THRESHOLD_BPS_CURRENT,
    METHOD_2_PROPOSAL_BAND_WIDTH_BPS,
    METHOD_2_PROPOSAL_FLOOR_MAX_SCORE_BPS,
    METHOD_2_PROPOSAL_FLOOR_PCT,
    METHOD_2_PROPOSAL_INCREMENT_PCT,
    METHOD_2_PROPOSAL_START_BPS,
    METHOD_2_PROPOSAL_START_PCT,
    METHOD_2_SURCHARGE_BANDS_CURRENT,
    STWF_MATURITY_BUCKETS,
    DenominationFactors,
    GSIBCategory,
    GSIBMethod,
    GSIBRuleVersion,
    SurchargeBand,
    ValidationBounds,
    effective_surcharge_pct,
    method1_indicators,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Results
# =========================================================================


@dataclass
class MethodResult:
    """Score and surcharge under one method.

    Attributes:
        method: Method 1 or 2.
        score_bps: Score in basis points.
        surcharge_pct: Surcharge in percent of RWA.
        surcharge_bucket: 1-based band index (0 for "below 130").
        band_lower_bps / band_upper_bps: The band the score falls in.
        category_scores: Category breakdown.
        stwf_score: STWF breakdown (method 2 only).
        validation_warnings: Data-quality warnings.
        citation: Provision producing the surcharge.
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
    citation: str = ""


@dataclass
class GSIBSurchargeResult:
    """Method 1, method 2 and the binding surcharge (§ 217.403(a)).

    ``final_surcharge_pct`` is the surcharge calculated this year;
    ``effective_surcharge_pct`` applies § 217.403(d) when the prior
    calculations are supplied.
    """

    method1_result: MethodResult
    method2_result: MethodResult
    binding_method: GSIBMethod = GSIBMethod.METHOD_1
    final_surcharge_pct: float = 0.0
    is_gsib: bool = True
    rule_version: GSIBRuleVersion = DEFAULT_RULE_VERSION
    gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT
    effective_surcharge_pct: Optional[float] = None
    gsib_category: GSIBCategory = GSIBCategory.CATEGORY_I
    reporting_entity: str = ""
    reporting_date: Optional[date] = None
    assessment_year: Optional[int] = None
    cet1_surcharge_amount: float = 0.0
    total_rwa: float = 0.0

    @property
    def method1_score_bps(self) -> float:
        """Method 1 score (bp)."""
        return self.method1_result.score_bps

    @property
    def method2_score_bps(self) -> float:
        """Method 2 score (bp)."""
        return self.method2_result.score_bps

    @property
    def method1_surcharge_pct(self) -> float:
        """Method 1 surcharge (%)."""
        return self.method1_result.surcharge_pct

    @property
    def method2_surcharge_pct(self) -> float:
        """Method 2 surcharge (%)."""
        return self.method2_result.surcharge_pct

    @property
    def final_surcharge_rate(self) -> float:
        """Binding surcharge as a decimal rate (2.9% -> 0.029)."""
        return self.final_surcharge_pct / 100.0

    @property
    def score_differential_bps(self) -> float:
        """Method 2 score minus method 1 score."""
        return self.method2_result.score_bps - self.method1_result.score_bps

    @property
    def surcharge_differential_pct(self) -> float:
        """Method 2 surcharge minus method 1 surcharge."""
        return self.method2_result.surcharge_pct - self.method1_result.surcharge_pct


# =========================================================================
#  Score -> surcharge
# =========================================================================


def score_to_surcharge(
    score_bps: float,
    bands: Sequence[SurchargeBand],
    higher_threshold_bps: float,
    higher_base_pct: float,
    higher_step_bps: float,
    higher_step_pct: float,
) -> tuple[float, int, float, float]:
    """Map a score to a surcharge using a banded table plus the open-ended rule.

    Used for Table 1 to § 217.403 with § 217.403(b)(2) and for Table 2 to
    § 217.403 with § 217.403(c)(2): above the table, the surcharge is the base
    percentage plus one step "for each" full step of score above the threshold.

    Returns:
        (surcharge_pct, bucket_index, band_lower_bps, band_upper_bps); bucket
        0 is the "below 130" row.
    """
    for i, band in enumerate(bands):
        if band.lower_bps <= score_bps < band.upper_bps:
            return band.surcharge_pct, i, band.lower_bps, band.upper_bps
    steps = math.floor((score_bps - higher_threshold_bps) / higher_step_bps)
    lower = higher_threshold_bps + steps * higher_step_bps
    return (
        higher_base_pct + steps * higher_step_pct,
        len(bands) + steps,
        lower,
        lower + higher_step_bps,
    )


def score_to_method1_surcharge(score_bps: float) -> tuple[float, int, float, float]:
    """Method 1 surcharge (Table 1 to § 217.403 and § 217.403(b)(2)).

    Unchanged by the 2026 proposal (preamble § II.D: "The proposal would not
    amend the score band ranges for method 1").
    """
    return score_to_surcharge(
        score_bps,
        METHOD_1_SURCHARGE_BANDS,
        METHOD_1_HIGHER_THRESHOLD_BPS,
        METHOD_1_HIGHER_BASE_PCT,
        METHOD_1_HIGHER_STEP_BPS,
        METHOD_1_HIGHER_STEP_PCT,
    )


def score_to_method2_surcharge(
    score_bps: float,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
) -> tuple[float, int, float, float]:
    """Method 2 surcharge.

    Current rule: Table 2 to § 217.403 and § 217.403(c)(2).
    Proposal (revised § 217.403(c)): 1.0% if the score is 189 bp or less;
    otherwise 1.1% plus 0.1% for each 20 bp the score exceeds 190 bp.
    """
    if version == GSIBRuleVersion.CURRENT_RULE:
        return score_to_surcharge(
            score_bps,
            METHOD_2_SURCHARGE_BANDS_CURRENT,
            METHOD_2_HIGHER_THRESHOLD_BPS_CURRENT,
            METHOD_2_HIGHER_BASE_PCT_CURRENT,
            METHOD_2_HIGHER_STEP_BPS_CURRENT,
            METHOD_2_HIGHER_STEP_PCT_CURRENT,
        )
    if score_bps < METHOD_2_PROPOSAL_START_BPS:
        # Revised § 217.403(c)(1) covers scores of 189 bp or less; a fractional
        # score between 189 and 190 has not reached the 190 bp threshold of (c)(2).
        return METHOD_2_PROPOSAL_FLOOR_PCT, 0, 0.0, METHOD_2_PROPOSAL_FLOOR_MAX_SCORE_BPS + 1.0
    steps = math.floor((score_bps - METHOD_2_PROPOSAL_START_BPS) / METHOD_2_PROPOSAL_BAND_WIDTH_BPS)
    lower = METHOD_2_PROPOSAL_START_BPS + steps * METHOD_2_PROPOSAL_BAND_WIDTH_BPS
    surcharge = round(METHOD_2_PROPOSAL_START_PCT + steps * METHOD_2_PROPOSAL_INCREMENT_PCT, 10)
    return surcharge, steps + 1, lower, lower + METHOD_2_PROPOSAL_BAND_WIDTH_BPS


def get_surcharge_for_score(
    score_bps: float,
    method: GSIBMethod = GSIBMethod.METHOD_1,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
) -> float:
    """Surcharge (%) for a score under one method."""
    if method == GSIBMethod.METHOD_1:
        return score_to_method1_surcharge(score_bps)[0]
    return score_to_method2_surcharge(score_bps, version)[0]


# =========================================================================
#  Calculator
# =========================================================================


class GSIBCalculator:
    """GSIB surcharge under 12 CFR 217 Subpart H (current rule or 2026 proposal)."""

    def __init__(
        self,
        denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
        version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
        gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT,
        validation_bounds: ValidationBounds = DEFAULT_VALIDATION_BOUNDS,
        validate_inputs: bool = True,
    ) -> None:
        """Configure the calculator.

        Args:
            denomination_factors: Aggregate global indicator amounts (§ 217.401).
            version: Rule version.
            gdp_growth_adjustment: Scalar of proposed § 217.405(c)(2).
            validation_bounds: Data-quality tolerances.
            validate_inputs: Run data-quality checks.
        """
        self.denomination_factors = denomination_factors
        self.version = version
        self.gdp_growth_adjustment = gdp_growth_adjustment
        self._validation_bounds = validation_bounds
        self._validate_inputs = validate_inputs

    def method1(
        self, data: GSIBIndicatorData, warnings: Optional[list[str]] = None
    ) -> MethodResult:
        """Method 1 score and surcharge (§ 217.404, Table 1 to § 217.403)."""
        score, cats = calculate_method1_score(data, self.denomination_factors, self.version)
        pct, bucket, lo, hi = score_to_method1_surcharge(score)
        return MethodResult(
            GSIBMethod.METHOD_1,
            score,
            pct,
            bucket,
            lo,
            hi,
            cats,
            validation_warnings=list(warnings or []),
            citation="12 CFR 217.404; Table 1 to § 217.403",
        )

    def method2(
        self, data: GSIBIndicatorData, warnings: Optional[list[str]] = None
    ) -> MethodResult:
        """Method 2 score and surcharge (§ 217.405-406 / revised § 217.403(c), § 217.405)."""
        score, cats, stwf = calculate_method2_score(data, self.version, self.gdp_growth_adjustment)
        pct, bucket, lo, hi = score_to_method2_surcharge(score, self.version)
        cite = (
            "12 CFR 217.405-406; Table 2 to § 217.403"
            if self.version == GSIBRuleVersion.CURRENT_RULE
            else "Proposed § 217.405 and § 217.403(c), FR Doc. 2026-05961"
        )
        return MethodResult(
            GSIBMethod.METHOD_2, score, pct, bucket, lo, hi, cats, stwf, list(warnings or []), cite
        )

    def calculate(
        self,
        indicator_data: GSIBIndicatorData,
        total_rwa: float = 0.0,
        calculated_prior_year_pct: Optional[float] = None,
    ) -> GSIBSurchargeResult:
        """Full determination (§ 217.403(a), (d)).

        Args:
            indicator_data: FR Y-15 indicators.
            total_rwa: Total RWA ($M) for the dollar surcharge amount.
            calculated_prior_year_pct: Surcharge calculated in the previous
                calendar year; with it, ``effective_surcharge_pct`` for the
                following year is the lower of the two (§ 217.403(d)).

        Returns:
            GSIBSurchargeResult.
        """
        warnings = (
            validate_indicator_data(indicator_data, self._validation_bounds)
            if self._validate_inputs
            else []
        )
        for w in warnings:
            logger.warning("G-SIB data quality: %s", w)
        m1 = self.method1(indicator_data, warnings)
        is_gsib = m1.score_bps >= GSIB_IDENTIFICATION_THRESHOLD_BPS
        m2 = self.method2(indicator_data, warnings)
        if not is_gsib:
            # § 217.402: method 2 applies only to a BHC identified as a GSIB.
            m2.surcharge_pct = 0.0
        binding = (
            GSIBMethod.METHOD_2 if m2.surcharge_pct >= m1.surcharge_pct else GSIBMethod.METHOD_1
        )
        final = max(m1.surcharge_pct, m2.surcharge_pct)
        effective = (
            effective_surcharge_pct(final, calculated_prior_year_pct)
            if calculated_prior_year_pct is not None
            else None
        )
        return GSIBSurchargeResult(
            method1_result=m1,
            method2_result=m2,
            binding_method=binding,
            final_surcharge_pct=final,
            is_gsib=is_gsib,
            rule_version=self.version,
            gdp_growth_adjustment=self.gdp_growth_adjustment,
            effective_surcharge_pct=effective,
            reporting_entity=indicator_data.reporting_entity,
            reporting_date=indicator_data.reporting_date,
            assessment_year=indicator_data.assessment_year,
            cet1_surcharge_amount=total_rwa * final / 100.0 if total_rwa > 0 else 0.0,
            total_rwa=total_rwa,
        )

    def calculate_method1_only(self, indicator_data: GSIBIndicatorData) -> MethodResult:
        """Method 1 only."""
        return self.method1(indicator_data)

    def calculate_method2_only(self, indicator_data: GSIBIndicatorData) -> MethodResult:
        """Method 2 only."""
        return self.method2(indicator_data)

    def sensitivity_analysis(
        self,
        indicator_data: GSIBIndicatorData,
        indicator_name: str,
        shock_pcts: Optional[list[float]] = None,
    ) -> list[tuple[float, float, float]]:
        """Shock one indicator and recompute (SR 11-7 sensitivity analysis).

        Returns:
            (shock_pct, max(method 1, method 2) score, final surcharge) tuples.
        """
        shocks = (
            shock_pcts if shock_pcts is not None else [-20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0]
        )
        base = indicator_data.get_indicator_value(indicator_name)
        out: list[tuple[float, float, float]] = []
        for s in shocks:
            r = self.calculate(
                indicator_data.with_indicator(indicator_name, base * (1 + s / 100.0))
            )
            out.append((s, max(r.method1_score_bps, r.method2_score_bps), r.final_surcharge_pct))
        return out

    def what_if_analysis(
        self,
        indicator_data: GSIBIndicatorData,
        target_surcharge_pct: float,
        indicator_name: str,
    ) -> Optional[float]:
        """Largest value of one indicator at which the surcharge stays at or below a target.

        Bisection over 0x-3x the current value; the surcharge is a step
        function, so the boundary is located to within 0.01% of the value.

        Returns:
            Indicator value ($M), or None if even 3x stays below the target or
            0x exceeds it.
        """
        base = indicator_data.get_indicator_value(indicator_name)
        if base <= 0:
            return None

        def surcharge(mult: float) -> float:
            return self.calculate(
                indicator_data.with_indicator(indicator_name, base * mult)
            ).final_surcharge_pct

        lo, hi = 0.0, 3.0
        if surcharge(lo) > target_surcharge_pct or surcharge(hi) <= target_surcharge_pct:
            return None
        while hi - lo > 1e-4:
            mid = (lo + hi) / 2.0
            if surcharge(mid) <= target_surcharge_pct:
                lo = mid
            else:
                hi = mid
        return base * lo

    def marginal_contribution(
        self,
        indicator_data: GSIBIndicatorData,
        shock_pct: float = 1.0,
    ) -> dict[str, dict[str, float]]:
        """Change in each method's score for a shock_pct rise in each indicator.

        Returns:
            {indicator: {"method1_bps": ..., "method2_bps": ...}}.
        """
        base = self.calculate(indicator_data)
        names = [s.name for s in method1_indicators(self.version)] + ["weighted_stwf_amount"]
        out: dict[str, dict[str, float]] = {}
        for name in names:
            v = indicator_data.get_indicator_value(name)
            r = self.calculate(indicator_data.with_indicator(name, v * (1 + shock_pct / 100.0)))
            out[name] = {
                "method1_bps": r.method1_score_bps - base.method1_score_bps,
                "method2_bps": r.method2_score_bps - base.method2_score_bps,
            }
        return out


# =========================================================================
#  Convenience
# =========================================================================


def calculate_gsib_surcharge(
    indicator_data: GSIBIndicatorData,
    total_rwa: float = 0.0,
    denomination_factors: DenominationFactors = DEFAULT_DENOMINATION_FACTORS,
    version: GSIBRuleVersion = DEFAULT_RULE_VERSION,
    gdp_growth_adjustment: float = INITIAL_GDP_GROWTH_ADJUSTMENT,
) -> GSIBSurchargeResult:
    """One-call GSIB surcharge (§ 217.403(a))."""
    return GSIBCalculator(denomination_factors, version, gdp_growth_adjustment).calculate(
        indicator_data, total_rwa=total_rwa
    )


_STWF_KEY_PREFIX = "stwf_cat"


def create_indicator_data_from_dict(
    data: dict[str, float],
    reporting_entity: str = "",
    reporting_date: Optional[date] = None,
    assessment_year: Optional[int] = None,
) -> GSIBIndicatorData:
    """Build :class:`GSIBIndicatorData` from a flat dict of $M values.

    Recognised keys: every indicator field name; ``weighted_stwf_amount``
    (reported Schedule G total); ``stwf_cat{1-4}_b{1-4}`` for the category x
    maturity cells of Table 1 to § 217.406 (b1 = 30 days or less, b2 = 31-90,
    b3 = 91-180/179, b4 = 181-365/180-364); the legacy ``stwf_*_days``
    fields; ``avg_risk_weighted_assets``; ``avg_total_assets``.
    """
    obj = GSIBIndicatorData(
        reporting_entity=reporting_entity,
        reporting_date=reporting_date,
        assessment_year=assessment_year,
    )
    components: list[STWFComponent] = []
    for key, value in data.items():
        if key.startswith(_STWF_KEY_PREFIX):
            cat, bucket = key[len(_STWF_KEY_PREFIX) :].split("_b")
            components.append(
                STWFComponent(int(cat), STWF_MATURITY_BUCKETS[int(bucket) - 1], float(value))
            )
        elif key == "weighted_stwf_amount":
            obj.weighted_stwf_amount_reported = float(value)
        elif hasattr(obj, key):
            setattr(obj, key, float(value))
    obj.stwf_components = components
    return obj
