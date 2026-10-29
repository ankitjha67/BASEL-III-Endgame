"""Tests for the G-SIB surcharge (12 CFR 217 Subpart H and the 2026 G-SIB NPR).

Expected values are transcribed from the rule text:
- Table 1 to § 217.403 (method 1 bands) and § 217.403(b)(2)
- Table 2 to § 217.403 (current method 2 bands) and § 217.403(c)(2)
- Revised § 217.403(c) (FR Doc. 2026-05961): 1.0% to 189 bp; 1.1% + 0.1% per 20 bp above 190
- Table 1 to § 217.404 (weights), § 217.404(b)(2) (100 bp substitutability cap)
- Table 1 to § 217.405 (current and proposed coefficients), § 217.406 (STWF)
- 2025 aggregate global indicator amounts (FR Doc. 2025-22964)
"""

from __future__ import annotations

from datetime import date

import pytest

from src.capital.gsib import (
    AGGREGATE_GLOBAL_INDICATORS_2025,
    METHOD_1_INDICATORS_CURRENT,
    METHOD_1_INDICATORS_PROPOSAL,
    METHOD_2_COEFFICIENTS_CURRENT_PCT,
    METHOD_2_COEFFICIENTS_PROPOSAL_PCT,
    STWF_WEIGHTS,
    SUBSTITUTABILITY_CAP_BPS,
    GSIBCalculator,
    GSIBIndicatorCategory,
    GSIBIndicatorData,
    GSIBMethod,
    GSIBRuleVersion,
    STWFComponent,
    STWFMaturityBucket,
    calculate_method1_score,
    calculate_method2_score,
    calculate_stwf_score,
    create_indicator_data_from_dict,
    effective_surcharge_pct,
    gdp_growth_adjustment,
    generate_fr_y15_report,
    generate_method_comparison,
    generate_surcharge_bucket_report,
    score_to_method1_surcharge,
    score_to_method2_surcharge,
    surcharge_result_to_dict,
    weighted_stwf,
)
from src.capital.gsib.gsib_params import DenominationFactors

CUR = GSIBRuleVersion.CURRENT_RULE
PROP = GSIBRuleVersion.PROPOSAL_2026


def _gsib_data(**overrides: float) -> GSIBIndicatorData:
    """A large US GSIB profile ($M)."""
    base = dict(
        total_exposures=4_100_000.0, intra_financial_system_assets=420_000.0,
        intra_financial_system_liabilities=380_000.0, securities_outstanding=520_000.0,
        payments_activity=210_000_000.0, assets_under_custody=3_100_000.0,
        underwriting_activity=520_000.0, otc_derivatives_notional=46_000_000.0,
        trading_and_afs_securities=380_000.0, level_3_assets=20_000.0,
        cross_jurisdictional_claims=1_000_000.0, cross_jurisdictional_liabilities=880_000.0,
        avg_risk_weighted_assets=1_800_000.0, avg_total_assets=3_200_000.0,
    )
    base.update(overrides)
    d = GSIBIndicatorData(reporting_entity="Test BHC", reporting_date=date(2025, 12, 31), **base)
    d.stwf_components = [
        STWFComponent(1, STWFMaturityBucket.UP_TO_30_DAYS, 200_000.0),
        STWFComponent(2, STWFMaturityBucket.UP_TO_30_DAYS, 80_000.0),
        STWFComponent(3, STWFMaturityBucket.DAYS_31_TO_90, 150_000.0),
        STWFComponent(4, STWFMaturityBucket.UP_TO_30_DAYS, 60_000.0),
        STWFComponent(4, STWFMaturityBucket.DAYS_181_TO_365, 40_000.0),
    ]
    return d


# ---------------------------------------------------------------- bands
class TestMethod1Bands:
    """Table 1 to § 217.403 -- unchanged by the 2026 proposal."""

    @pytest.mark.parametrize("score,pct", [
        (0.0, 0.0), (129.99, 0.0), (130.0, 1.0), (229.99, 1.0), (230.0, 1.5), (329.99, 1.5),
        (330.0, 2.0), (430.0, 2.5), (529.99, 2.5), (530.0, 3.5), (629.99, 3.5),
        (630.0, 4.5), (729.99, 4.5), (730.0, 5.5), (830.0, 6.5),
    ])
    def test_table_1(self, score: float, pct: float) -> None:
        assert score_to_method1_surcharge(score)[0] == pytest.approx(pct)

    def test_table_jumps_from_2_5_to_3_5(self) -> None:
        """The table jumps from 2.5% to 3.5% at 530 bp (no 3.0% band)."""
        assert score_to_method1_surcharge(529.0)[0] == 2.5
        assert score_to_method1_surcharge(531.0)[0] == 3.5


class TestMethod2Bands:
    @pytest.mark.parametrize("score,pct", [
        (129.0, 0.0), (130.0, 1.0), (230.0, 1.5), (330.0, 2.0), (430.0, 2.5), (530.0, 3.0),
        (630.0, 3.5), (730.0, 4.0), (830.0, 4.5), (930.0, 5.0), (1030.0, 5.5), (1129.9, 5.5),
        (1130.0, 6.5), (1229.9, 6.5), (1230.0, 7.0),
    ])
    def test_current_table_2(self, score: float, pct: float) -> None:
        assert score_to_method2_surcharge(score, CUR)[0] == pytest.approx(pct)

    @pytest.mark.parametrize("score,pct", [
        (0.0, 1.0), (189.0, 1.0), (189.5, 1.0), (190.0, 1.1), (209.99, 1.1), (210.0, 1.2),
        (229.99, 1.2), (230.0, 1.3), (480.0, 2.5), (1130.0, 5.8),
    ])
    def test_proposed_20bp_bands(self, score: float, pct: float) -> None:
        assert score_to_method2_surcharge(score, PROP)[0] == pytest.approx(pct)

    @pytest.mark.parametrize("centre", [280.0, 380.0, 480.0, 580.0, 680.0])
    def test_proposal_preserves_band_centres(self, centre: float) -> None:
        """Preamble § II.D: the proposal equals the current surcharge at band centres."""
        assert score_to_method2_surcharge(centre, PROP)[0] == pytest.approx(
            score_to_method2_surcharge(centre, CUR)[0])


# ------------------------------------------------------------ parameters
class TestParameters:
    def test_method1_weights_current(self) -> None:
        w = {s.name: s.weight for s in METHOD_1_INDICATORS_CURRENT}
        assert w["total_exposures"] == 0.20
        assert w["underwriting_activity"] == 0.0667
        assert w["cross_jurisdictional_claims"] == 0.10
        assert len(w) == 12

    def test_method1_weights_proposal(self) -> None:
        w = {s.name: s.weight for s in METHOD_1_INDICATORS_PROPOSAL}
        assert w["underwriting_activity"] == 0.0333
        assert w["trading_volume_fixed_income"] == 0.0167
        assert w["trading_volume_equity_other"] == 0.0167
        assert len(w) == 14

    def test_substitutability_cap_100(self) -> None:
        assert SUBSTITUTABILITY_CAP_BPS == 100.0

    @pytest.mark.parametrize("name,cur,prop", [
        ("total_exposures", 4.423, 3.686), ("intra_financial_system_assets", 12.007, 10.006),
        ("intra_financial_system_liabilities", 12.490, 10.408),
        ("securities_outstanding", 9.056, 7.547), ("otc_derivatives_notional", 0.155, 0.129),
        ("trading_and_afs_securities", 30.169, 25.141), ("level_3_assets", 161.177, 134.314),
        ("cross_jurisdictional_claims", 9.277, 7.731),
        ("cross_jurisdictional_liabilities", 9.926, 8.272),
    ])
    def test_method2_coefficients(self, name: str, cur: float, prop: float) -> None:
        assert METHOD_2_COEFFICIENTS_CURRENT_PCT[name] == cur
        assert METHOD_2_COEFFICIENTS_PROPOSAL_PCT[name] == prop
        # One-time 1.2 downward adjustment (preamble § II.A.i), to table rounding
        assert cur / 1.2 == pytest.approx(prop, abs=0.001)

    def test_stwf_coefficient_proposal(self) -> None:
        assert METHOD_2_COEFFICIENTS_PROPOSAL_PCT["weighted_stwf_amount"] == 23.003

    @pytest.mark.parametrize("cat,weights", [
        (1, (0.25, 0.10, 0.0, 0.0)), (2, (0.50, 0.25, 0.10, 0.0)),
        (3, (0.75, 0.50, 0.25, 0.10)), (4, (1.00, 0.75, 0.50, 0.25)),
    ])
    def test_stwf_table(self, cat: int, weights: tuple[float, ...]) -> None:
        assert STWF_WEIGHTS[cat] == weights

    def test_aggregate_global_indicators_2025(self) -> None:
        a = AGGREGATE_GLOBAL_INDICATORS_2025
        assert a.total_exposures == pytest.approx(115_610_567.459028)
        assert a.payments_activity == pytest.approx(3_583_068_096.731293)
        assert a.level_3_assets == pytest.approx(785_843.290915)
        assert a.trading_volume_fixed_income is None


# --------------------------------------------------------------- scoring
class TestScores:
    def test_method1_indicator_formula(self) -> None:
        d = _gsib_data()
        score, cats = calculate_method1_score(d, version=CUR)
        size = next(c for c in cats if c.category == GSIBIndicatorCategory.SIZE)
        expected = 4_100_000.0 / 115_610_567.459028 * 10_000 * 0.20
        assert size.capped_score_bps == pytest.approx(expected)
        assert expected == pytest.approx(70.93, abs=0.01)
        assert score == pytest.approx(sum(c.capped_score_bps for c in cats))

    def test_substitutability_cap(self) -> None:
        d = _gsib_data(payments_activity=3_000_000_000.0)
        _, cats = calculate_method1_score(d, version=CUR)
        sub = next(c for c in cats if c.category == GSIBIndicatorCategory.SUBSTITUTABILITY)
        assert sub.cap_applied and sub.capped_score_bps == 100.0 and sub.raw_score_bps > 100.0

    def test_proposal_needs_trading_volume_denominators(self) -> None:
        d = _gsib_data(trading_volume_fixed_income=1_000_000.0)
        with pytest.raises(ValueError, match="aggregate global indicator"):
            calculate_method1_score(d, version=PROP)
        denoms = DenominationFactors(**{**AGGREGATE_GLOBAL_INDICATORS_2025.__dict__,
                                        "trading_volume_fixed_income": 100_000_000.0,
                                        "trading_volume_equity_other": 50_000_000.0})
        score, cats = calculate_method1_score(d, denoms, PROP)
        sub = next(c for c in cats if c.category == GSIBIndicatorCategory.SUBSTITUTABILITY)
        tv = next(i for i in sub.indicators if i.indicator_name == "trading_volume_fixed_income")
        assert tv.weighted_score_bps == pytest.approx(1_000_000 / 100_000_000 * 10_000 * 0.0167)

    def test_weighted_stwf(self) -> None:
        s = weighted_stwf(_gsib_data())
        expected = 200_000 * 0.25 + 80_000 * 0.50 + 150_000 * 0.50 + 60_000 * 1.0 + 40_000 * 0.25
        assert s.weighted_amount == pytest.approx(expected)
        assert s.total_wholesale_funding == pytest.approx(530_000.0)

    def test_stwf_score_current_rule(self) -> None:
        """§ 217.406(a): weighted STWF / average RWA x 350."""
        d = _gsib_data()
        s = calculate_stwf_score(d, CUR)
        assert s.stwf_score_bps == pytest.approx(s.weighted_amount / 1_800_000.0 * 350.0)

    def test_stwf_score_proposal(self) -> None:
        """Proposed § 217.405: $bn x 23.003% / GDP growth adjustment; no RWA denominator."""
        d = _gsib_data(avg_risk_weighted_assets=0.0)
        s = calculate_stwf_score(d, PROP, gdp_growth_adjustment=1.1)
        assert s.stwf_score_bps == pytest.approx(s.weighted_amount / 1000 * 23.003 / 100 / 1.1)

    def test_current_rule_requires_rwa(self) -> None:
        with pytest.raises(ValueError):
            calculate_stwf_score(_gsib_data(avg_risk_weighted_assets=0.0), CUR)

    def test_method2_indicator_formula(self) -> None:
        d = _gsib_data()
        _, cats_c, _ = calculate_method2_score(d, CUR)
        _, cats_p, _ = calculate_method2_score(d, PROP, gdp_growth_adjustment=1.05)
        size_c = next(c for c in cats_c if c.category == GSIBIndicatorCategory.SIZE)
        size_p = next(c for c in cats_p if c.category == GSIBIndicatorCategory.SIZE)
        assert size_c.capped_score_bps == pytest.approx(4_100 * 4.423 / 100)
        assert size_p.capped_score_bps == pytest.approx(4_100 * 3.686 / 100 / 1.05)
        assert not any(c.category == GSIBIndicatorCategory.SUBSTITUTABILITY for c in cats_c)

    def test_legacy_stwf_fields_weighted_as_category_4(self) -> None:
        d = GSIBIndicatorData(stwf_0_30_days=100.0, stwf_31_90_days=100.0,
                              stwf_91_180_days=100.0, stwf_181_365_days=100.0)
        assert weighted_stwf(d).weighted_amount == pytest.approx(100 * (1 + 0.75 + 0.5 + 0.25))

    def test_dict_builder_cells(self) -> None:
        d = create_indicator_data_from_dict({"total_exposures": 1.0, "stwf_cat3_b2": 10.0,
                                             "stwf_cat1_b1": 4.0})
        assert weighted_stwf(d).weighted_amount == pytest.approx(10 * 0.5 + 4 * 0.25)


# ------------------------------------------------------------- calculator
class TestCalculator:
    def test_binding_is_greater(self) -> None:
        r = GSIBCalculator(version=PROP).calculate(_gsib_data(), total_rwa=1_800_000.0)
        assert r.final_surcharge_pct == max(r.method1_surcharge_pct, r.method2_surcharge_pct)
        assert r.cet1_surcharge_amount == pytest.approx(1_800_000.0 * r.final_surcharge_pct / 100)
        assert r.final_surcharge_rate == pytest.approx(r.final_surcharge_pct / 100)

    def test_proposal_lowers_method2(self) -> None:
        d = _gsib_data()
        cur = GSIBCalculator(version=CUR).calculate(d)
        prop = GSIBCalculator(version=PROP).calculate(d)
        assert prop.method2_score_bps < cur.method2_score_bps

    def test_not_gsib_below_130(self) -> None:
        d = _gsib_data(total_exposures=600_000.0, intra_financial_system_assets=1.0,
                       intra_financial_system_liabilities=1.0, securities_outstanding=1.0,
                       payments_activity=1.0, assets_under_custody=1.0, underwriting_activity=1.0,
                       otc_derivatives_notional=1.0, trading_and_afs_securities=1.0, level_3_assets=1.0,
                       cross_jurisdictional_claims=1.0, cross_jurisdictional_liabilities=1.0)
        r = GSIBCalculator(version=PROP).calculate(d)
        assert not r.is_gsib and r.final_surcharge_pct == 0.0

    def test_effective_date_rule(self) -> None:
        """Preamble § II.F example: 2.2% calculated 2026, 2.1% calculated 2027 -> 2.1% in 2029."""
        assert effective_surcharge_pct(2.1, 2.2) == 2.1
        assert effective_surcharge_pct(2.4, 2.2) == 2.2
        assert effective_surcharge_pct(2.0) == 2.0

    def test_gdp_growth_adjustment(self) -> None:
        assert gdp_growth_adjustment(110.0, 100.0) == pytest.approx(1.1)
        assert gdp_growth_adjustment(95.0, 100.0, prior_year_adjustment=1.02) == pytest.approx(1.02)

    def test_sensitivity_and_what_if(self) -> None:
        calc = GSIBCalculator(version=PROP)
        d = _gsib_data()
        rows = calc.sensitivity_analysis(d, "total_exposures", [-10.0, 0.0, 10.0])
        assert rows[0][1] <= rows[1][1] <= rows[2][1]
        base = calc.calculate(d).final_surcharge_pct
        v = calc.what_if_analysis(d, base, "total_exposures")
        assert v is not None and v >= d.total_exposures * 0.99
        mc = calc.marginal_contribution(d)
        assert mc["total_exposures"]["method2_bps"] > 0

    def test_reports(self) -> None:
        d = _gsib_data()
        r = GSIBCalculator(version=PROP).calculate(d)
        rep = generate_fr_y15_report(d, r)
        assert {s.schedule_id for s in rep.schedules} == set("ABCDEG")
        sched_c = next(s for s in rep.schedules if s.schedule_id == "C")
        assert len(sched_c.line_items) == 5
        cmp = generate_method_comparison(r)
        assert any(row["category"] == "SHORT_TERM_WHOLESALE_FUNDING" for row in cmp.category_comparison)
        b = generate_surcharge_bucket_report(r.method2_result, PROP)
        assert b.band_upper_bps - b.band_lower_bps == pytest.approx(20.0)
        assert surcharge_result_to_dict(r)["method1"]["citation"]
        assert r.binding_method in (GSIBMethod.METHOD_1, GSIBMethod.METHOD_2)


class TestFRY15Consistency:
    """The FR Y-15 and the capital stack must produce the same surcharge."""

    def test_fr_y15_matches_calculator(self) -> None:
        from src.reporting.fr_y15 import generate_fr_y15
        vals = {k: v for k, v in _gsib_data().__dict__.items() if isinstance(v, float)}
        vals.update({"stwf_cat1_b1": 200_000.0, "stwf_cat2_b1": 80_000.0, "stwf_cat3_b2": 150_000.0,
                     "stwf_cat4_b1": 60_000.0, "stwf_cat4_b4": 40_000.0})
        for version in (CUR, PROP):
            rep = generate_fr_y15(vals, date(2025, 12, 31), version=version)
            calc = GSIBCalculator(version=version).calculate(create_indicator_data_from_dict(vals))
            det = rep.surcharge_determination
            assert det.final_surcharge_pct == calc.final_surcharge_pct
            assert det.method1.total_score_bps == pytest.approx(calc.method1_score_bps)
            assert det.method2.total_score_bps == pytest.approx(calc.method2_score_bps)
