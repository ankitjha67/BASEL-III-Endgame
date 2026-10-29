"""FR Y-15 schedules, method comparison and surcharge-band reporting.

Builds the FR Y-15 schedules (A-E systemic indicators, G short-term
wholesale funding) from :class:`GSIBIndicatorData` and a
:class:`GSIBSurchargeResult`, plus analytical reports on the method 1 vs
method 2 outcome and the position of each score within its surcharge band.

References:
- FR Y-15 Systemic Risk Report (OMB 7100-0352), Schedules A-G
- 12 CFR 217.401 (indicator definitions by FR Y-15 schedule), 217.403-406
- FR Doc. 2026-05961 (proposed revisions: trading-volume indicators,
  Schedule G as a method 2 indicator, method 2 bands)

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from src.capital.gsib.gsib_calculator import (
    GSIBSurchargeResult,
    MethodResult,
    score_to_method1_surcharge,
    score_to_method2_surcharge,
)
from src.capital.gsib.gsib_indicators import (
    GSIBIndicatorData,
    validate_indicator_data,
    weighted_stwf,
)
from src.capital.gsib.gsib_params import (
    FR_Y15_OMB_NUMBER,
    FR_Y15_REPORT_NAME,
    FR_Y15_SCHEDULES,
    STWF_CATEGORY_DESCRIPTIONS,
    SUBSTITUTABILITY_CAP_BPS,
    GSIBIndicatorCategory,
    GSIBMethod,
    GSIBRuleVersion,
    method1_indicators,
)

logger = logging.getLogger(__name__)

_SCHEDULE_FOR_CATEGORY: dict[GSIBIndicatorCategory, str] = {
    GSIBIndicatorCategory.SIZE: "A",
    GSIBIndicatorCategory.INTERCONNECTEDNESS: "B",
    GSIBIndicatorCategory.SUBSTITUTABILITY: "C",
    GSIBIndicatorCategory.COMPLEXITY: "D",
    GSIBIndicatorCategory.CROSS_JURISDICTIONAL: "E",
}


# =========================================================================
#  Report data structures
# =========================================================================


@dataclass
class FRY15ScheduleLineItem:
    """One FR Y-15 line item ($M unless stated)."""

    line_number: str
    description: str
    value: float = 0.0
    memo_items: dict[str, float] = field(default_factory=dict)


@dataclass
class FRY15Schedule:
    """One FR Y-15 schedule."""

    schedule_id: str
    schedule_name: str
    line_items: list[FRY15ScheduleLineItem] = field(default_factory=list)
    schedule_total: float = 0.0


@dataclass
class FRY15Report:
    """FR Y-15 schedules with the resulting G-SIB scores and surcharge."""

    report_name: str = FR_Y15_REPORT_NAME
    omb_number: str = FR_Y15_OMB_NUMBER
    reporting_entity: str = ""
    reporting_date: Optional[date] = None
    rule_version: GSIBRuleVersion = GSIBRuleVersion.PROPOSAL_2026
    schedules: list[FRY15Schedule] = field(default_factory=list)
    method1_score_bps: float = 0.0
    method2_score_bps: float = 0.0
    method1_surcharge_pct: float = 0.0
    method2_surcharge_pct: float = 0.0
    final_surcharge_pct: float = 0.0
    binding_method: GSIBMethod = GSIBMethod.METHOD_1
    generation_timestamp: Optional[datetime] = None
    validation_warnings: list[str] = field(default_factory=list)


@dataclass
class MethodComparisonReport:
    """Side-by-side method 1 / method 2 breakdown."""

    method1_result: MethodResult
    method2_result: MethodResult
    score_differential_bps: float = 0.0
    surcharge_differential_pct: float = 0.0
    binding_method: GSIBMethod = GSIBMethod.METHOD_1
    category_comparison: list[dict[str, Any]] = field(default_factory=list)
    stwf_impact_bps: float = 0.0


@dataclass
class SurchargeBucketReport:
    """Where a score sits in its surcharge band."""

    method: GSIBMethod
    score_bps: float = 0.0
    assigned_bucket: int = 0
    surcharge_pct: float = 0.0
    band_lower_bps: float = 0.0
    band_upper_bps: float = 0.0
    distance_to_next_band_bps: float = 0.0
    distance_to_prior_band_bps: float = 0.0
    next_band_surcharge_pct: float = 0.0


# =========================================================================
#  FR Y-15 schedules
# =========================================================================


def generate_fr_y15_report(
    indicator_data: GSIBIndicatorData,
    surcharge_result: GSIBSurchargeResult,
) -> FRY15Report:
    """Populate FR Y-15 Schedules A-E and G (§ 217.401 definitions).

    Schedules A-E list the method 1 systemic indicators of the rule version
    used for ``surcharge_result``; Schedule G lists the STWF cells of
    Table 1 to § 217.406 and the weighted total.
    """
    version = surcharge_result.rule_version
    by_schedule: dict[str, list[FRY15ScheduleLineItem]] = {s: [] for s in "ABCDE"}
    for spec in method1_indicators(version):
        sched = _SCHEDULE_FOR_CATEGORY[spec.category]
        items = by_schedule[sched]
        items.append(
            FRY15ScheduleLineItem(
                str(len(items) + 1), spec.description, indicator_data.get_indicator_value(spec.name)
            )
        )
    schedules = [
        FRY15Schedule(s, FR_Y15_SCHEDULES[s], items, sum(i.value for i in items))
        for s, items in by_schedule.items()
    ]

    stwf = weighted_stwf(indicator_data)
    g_items = [
        FRY15ScheduleLineItem(
            f"{b.category}.{i + 1}",
            f"Category {b.category} ({STWF_CATEGORY_DESCRIPTIONS[b.category][:40]}...) "
            f"- {b.bucket.value}",
            b.amount,
            {"weight": b.weight, "weighted_amount": b.weighted_amount},
        )
        for i, b in enumerate(stwf.buckets)
    ]
    g_items.append(
        FRY15ScheduleLineItem(
            "Total", "Total weighted short-term wholesale funding amount", stwf.weighted_amount
        )
    )
    schedules.append(FRY15Schedule("G", FR_Y15_SCHEDULES["G"], g_items, stwf.weighted_amount))

    return FRY15Report(
        reporting_entity=indicator_data.reporting_entity,
        reporting_date=indicator_data.reporting_date,
        rule_version=version,
        schedules=schedules,
        method1_score_bps=surcharge_result.method1_score_bps,
        method2_score_bps=surcharge_result.method2_score_bps,
        method1_surcharge_pct=surcharge_result.method1_surcharge_pct,
        method2_surcharge_pct=surcharge_result.method2_surcharge_pct,
        final_surcharge_pct=surcharge_result.final_surcharge_pct,
        binding_method=surcharge_result.binding_method,
        generation_timestamp=datetime.now(),
        validation_warnings=validate_indicator_data(indicator_data),
    )


# =========================================================================
#  Method comparison
# =========================================================================


def generate_method_comparison(surcharge_result: GSIBSurchargeResult) -> MethodComparisonReport:
    """Category-by-category comparison of the two methods.

    Method 1 scores relative to global aggregates (§ 217.404) and includes
    substitutability (capped at 100 bp); method 2 scores dollar amounts by
    fixed coefficients (§ 217.405) and replaces substitutability with STWF.
    """
    m1, m2 = surcharge_result.method1_result, surcharge_result.method2_result
    s1 = {c.category: c.capped_score_bps for c in m1.category_scores}
    s2 = {c.category: c.capped_score_bps for c in m2.category_scores}
    rows: list[dict[str, Any]] = []
    for cat in GSIBIndicatorCategory:
        if cat not in s1 and cat not in s2:
            continue
        note = ""
        if cat == GSIBIndicatorCategory.SUBSTITUTABILITY:
            note = f"Method 1 only; capped at {SUBSTITUTABILITY_CAP_BPS:.0f} bp (§ 217.404(b)(2))"
        elif cat == GSIBIndicatorCategory.SHORT_TERM_WHOLESALE_FUNDING:
            note = "Method 2 only"
        rows.append(
            {
                "category": cat.value,
                "method1_score_bps": s1.get(cat, 0.0),
                "method2_score_bps": s2.get(cat, 0.0),
                "differential_bps": s2.get(cat, 0.0) - s1.get(cat, 0.0),
                "note": note,
            }
        )
    stwf_bps = m2.stwf_score.stwf_score_bps if m2.stwf_score else 0.0
    return MethodComparisonReport(
        method1_result=m1,
        method2_result=m2,
        score_differential_bps=surcharge_result.score_differential_bps,
        surcharge_differential_pct=surcharge_result.surcharge_differential_pct,
        binding_method=surcharge_result.binding_method,
        category_comparison=rows,
        stwf_impact_bps=stwf_bps - s1.get(GSIBIndicatorCategory.SUBSTITUTABILITY, 0.0),
    )


# =========================================================================
#  Surcharge band position
# =========================================================================


def generate_surcharge_bucket_report(
    method_result: MethodResult,
    version: GSIBRuleVersion = GSIBRuleVersion.PROPOSAL_2026,
) -> SurchargeBucketReport:
    """Distance from a score to the edges of its band and the next band's surcharge.

    Uses the same mapping as the calculator: Table 1 to § 217.403 for
    method 1; Table 2 / revised § 217.403(c) for method 2.
    """
    score = method_result.score_bps
    if method_result.method == GSIBMethod.METHOD_1:
        pct, bucket, lo, hi = score_to_method1_surcharge(score)
        nxt = score_to_method1_surcharge(hi)[0]
    else:
        pct, bucket, lo, hi = score_to_method2_surcharge(score, version)
        nxt = score_to_method2_surcharge(hi, version)[0]
    return SurchargeBucketReport(
        method_result.method,
        score,
        bucket,
        pct,
        lo,
        hi,
        hi - score,
        score - lo if lo != float("-inf") else score,
        nxt,
    )


# =========================================================================
#  Text and dict renderings
# =========================================================================


def format_fr_y15_text(report: FRY15Report) -> str:
    """Plain-text rendering of an FR Y-15 report."""
    lines = [
        f"{report.report_name} (OMB {report.omb_number}) -- {report.reporting_entity}",
        f"As of {report.reporting_date}  Rule version: {report.rule_version.value}",
        "",
    ]
    for s in report.schedules:
        lines.append(f"Schedule {s.schedule_id}: {s.schedule_name}")
        for li in s.line_items:
            lines.append(f"  {li.line_number:>6}  {li.description[:70]:<70}  {li.value:>18,.0f}")
        lines.append("")
    lines += [
        f"Method 1 score {report.method1_score_bps:,.1f} bp -> {report.method1_surcharge_pct:.1f}%",
        f"Method 2 score {report.method2_score_bps:,.1f} bp -> {report.method2_surcharge_pct:.1f}%",
        f"GSIB surcharge {report.final_surcharge_pct:.1f}% ({report.binding_method.value})",
    ]
    lines += [f"WARNING: {w}" for w in report.validation_warnings]
    return "\n".join(lines)


def format_method_comparison_text(report: MethodComparisonReport) -> str:
    """Plain-text rendering of a method comparison."""
    lines = [f"{'Category':<32}{'Method 1':>12}{'Method 2':>12}{'Diff':>12}  Note"]
    for r in report.category_comparison:
        lines.append(
            f"{r['category']:<32}{r['method1_score_bps']:>12.1f}{r['method2_score_bps']:>12.1f}"
            f"{r['differential_bps']:>+12.1f}  {r['note']}"
        )
    lines.append(
        f"Score differential {report.score_differential_bps:+.1f} bp; surcharge differential "
        f"{report.surcharge_differential_pct:+.1f}%; binding {report.binding_method.value}"
    )
    stwf = report.method2_result.stwf_score
    if stwf:
        lines.append(
            f"Weighted STWF ${stwf.weighted_amount:,.0f}M x coefficient {stwf.coefficient:.3f} "
            f"-> {stwf.stwf_score_bps:.1f} bp ({stwf.source})"
        )
    return "\n".join(lines)


def format_surcharge_bucket_text(report: SurchargeBucketReport) -> str:
    """Plain-text rendering of a band-position report."""
    return (
        f"{report.method.value}: score {report.score_bps:.1f} bp in band {report.assigned_bucket} "
        f"[{report.band_lower_bps:.0f}, {report.band_upper_bps:.0f}) -> "
        f"{report.surcharge_pct:.1f}%; {report.distance_to_next_band_bps:.1f} bp to next band "
        f"({report.next_band_surcharge_pct:.1f}%)"
    )


def fr_y15_report_to_dict(report: FRY15Report) -> dict[str, Any]:
    """JSON-serialisable dict of an FR Y-15 report."""
    return {
        "report_name": report.report_name,
        "omb_number": report.omb_number,
        "reporting_entity": report.reporting_entity,
        "reporting_date": report.reporting_date.isoformat() if report.reporting_date else None,
        "rule_version": report.rule_version.value,
        "schedules": [
            {
                "schedule_id": s.schedule_id,
                "schedule_name": s.schedule_name,
                "schedule_total": s.schedule_total,
                "line_items": [
                    {
                        "line_number": li.line_number,
                        "description": li.description,
                        "value": li.value,
                        "memo_items": li.memo_items,
                    }
                    for li in s.line_items
                ],
            }
            for s in report.schedules
        ],
        "method1_score_bps": report.method1_score_bps,
        "method2_score_bps": report.method2_score_bps,
        "method1_surcharge_pct": report.method1_surcharge_pct,
        "method2_surcharge_pct": report.method2_surcharge_pct,
        "final_surcharge_pct": report.final_surcharge_pct,
        "binding_method": report.binding_method.value,
        "validation_warnings": list(report.validation_warnings),
    }


def surcharge_result_to_dict(result: GSIBSurchargeResult) -> dict[str, Any]:
    """JSON-serialisable dict of a surcharge result."""

    def method(m: MethodResult) -> dict[str, Any]:
        out: dict[str, Any] = {
            "method": m.method.value,
            "score_bps": m.score_bps,
            "surcharge_pct": m.surcharge_pct,
            "surcharge_bucket": m.surcharge_bucket,
            "band_lower_bps": m.band_lower_bps,
            "band_upper_bps": m.band_upper_bps,
            "citation": m.citation,
            "categories": [
                {
                    "category": c.category.value,
                    "raw_score_bps": c.raw_score_bps,
                    "capped_score_bps": c.capped_score_bps,
                    "cap_applied": c.cap_applied,
                    "indicators": [
                        {
                            "name": i.indicator_name,
                            "value": i.raw_value,
                            "denominator_or_coefficient": i.denomination_factor,
                            "score_bps": i.weighted_score_bps,
                        }
                        for i in c.indicators
                    ],
                }
                for c in m.category_scores
            ],
        }
        if m.stwf_score:
            s = m.stwf_score
            out["stwf"] = {
                "weighted_amount": s.weighted_amount,
                "total_wholesale_funding": s.total_wholesale_funding,
                "denominator": s.denominator,
                "ratio": s.stwf_ratio,
                "coefficient": s.coefficient,
                "score_bps": s.stwf_score_bps,
                "source": s.source,
                "cells": [
                    {
                        "category": b.category,
                        "bucket": b.bucket.value,
                        "weight": b.weight,
                        "amount": b.amount,
                        "weighted_amount": b.weighted_amount,
                    }
                    for b in s.buckets
                ],
            }
        return out

    return {
        "rule_version": result.rule_version.value,
        "is_gsib": result.is_gsib,
        "gdp_growth_adjustment": result.gdp_growth_adjustment,
        "method1": method(result.method1_result),
        "method2": method(result.method2_result),
        "binding_method": result.binding_method.value,
        "final_surcharge_pct": result.final_surcharge_pct,
        "effective_surcharge_pct": result.effective_surcharge_pct,
        "cet1_surcharge_amount": result.cet1_surcharge_amount,
        "total_rwa": result.total_rwa,
        "reporting_entity": result.reporting_entity,
        "reporting_date": result.reporting_date.isoformat() if result.reporting_date else None,
    }
