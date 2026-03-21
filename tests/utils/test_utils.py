"""Unit tests for utils module — aggregation, math helpers, and BCBS 239.

Tests cover:
- Intra-bucket aggregation: K_b = sqrt(sum rho_kl * WS_k * WS_l)
- Inter-bucket aggregation: capital = sqrt(sum K_b^2 + cross terms)
- Vasicek conditional PD and Merton distance-to-default
- Portfolio statistics (HHI, variance)
- VaR backtesting (Kupiec test)
- BCBS 239 data quality checks and lineage trail

References:
    - MAR21.4-21.6: SBM aggregation formulas
    - BCBS d424 CRE31.6: Vasicek model
    - BCBS 239: Data quality framework
"""

import math

import numpy as np
import pytest

from src.core.enums import CorrelationScenario
from src.utils.aggregation import (
    apply_scenario_multiplier,
    inter_bucket_aggregation,
    intra_bucket_aggregation,
)
from src.utils.bcbs239 import (
    DataQualityCheck,
    DataQualityDimension,
    DataQualityReport,
    LineageEventType,
    LineageTrail,
    QualityStatus,
    check_completeness,
    check_consistency,
    check_range,
)
from src.utils.math_helpers import (
    discount_factor,
    effective_maturity,
    herfindahl_index,
    interpolate_risk_weight,
    kupiec_test,
    merton_distance_to_default,
    pd_from_distance_to_default,
    portfolio_variance,
    present_value,
    vasicek_conditional_pd,
)


# =========================================================================
#  Aggregation Tests
# =========================================================================


class TestIntraBucketAggregation:
    """Tests for intra-bucket aggregation per MAR21.4(3)."""

    def test_two_sensitivities_with_correlation(self) -> None:
        """ws=[10, 5], rho=[[1, 0.5], [0.5, 1]] -> K_b = sqrt(175)."""
        ws = np.array([10.0, 5.0])
        rho = np.array([[1.0, 0.5], [0.5, 1.0]])
        k_b, s_b = intra_bucket_aggregation(ws, rho)
        # 10^2 + 2*0.5*10*5 + 5^2 = 100 + 50 + 25 = 175
        assert k_b == pytest.approx(math.sqrt(175.0), rel=1e-6)
        assert s_b == pytest.approx(15.0)

    def test_single_sensitivity(self) -> None:
        """Single sensitivity -> K_b = |ws|."""
        ws = np.array([7.0])
        rho = np.array([[1.0]])
        k_b, s_b = intra_bucket_aggregation(ws, rho)
        assert k_b == pytest.approx(7.0)
        assert s_b == pytest.approx(7.0)

    def test_perfectly_correlated(self) -> None:
        """rho=1 everywhere -> K_b = sum(ws)."""
        ws = np.array([10.0, 5.0, 3.0])
        rho = np.ones((3, 3))
        k_b, s_b = intra_bucket_aggregation(ws, rho)
        assert k_b == pytest.approx(18.0, rel=1e-6)

    def test_uncorrelated(self) -> None:
        """rho=0 off-diagonal -> K_b = sqrt(sum ws^2)."""
        ws = np.array([3.0, 4.0])
        rho = np.eye(2)
        k_b, s_b = intra_bucket_aggregation(ws, rho)
        assert k_b == pytest.approx(5.0, rel=1e-6)

    def test_negative_sensitivities(self) -> None:
        """Negative sensitivities are handled correctly."""
        ws = np.array([-10.0, 5.0])
        rho = np.array([[1.0, 0.5], [0.5, 1.0]])
        k_b, s_b = intra_bucket_aggregation(ws, rho)
        # (-10)^2 + 2*0.5*(-10)*5 + 5^2 = 100 - 50 + 25 = 75
        assert k_b == pytest.approx(math.sqrt(75.0), rel=1e-6)
        assert s_b == pytest.approx(-5.0)

    def test_empty_sensitivities(self) -> None:
        """Empty input returns (0, 0)."""
        ws = np.array([])
        rho = np.array([]).reshape(0, 0)
        k_b, s_b = intra_bucket_aggregation(ws, rho)
        assert k_b == pytest.approx(0.0)
        assert s_b == pytest.approx(0.0)


class TestInterBucketAggregation:
    """Tests for inter-bucket aggregation per MAR21.4(4)."""

    def test_two_buckets_with_gamma(self) -> None:
        """Two buckets with gamma=0.25."""
        charges = {"A": 10.0, "B": 8.0}
        net_sens = {"A": 10.0, "B": 8.0}
        total = inter_bucket_aggregation(charges, net_sens, 0.25)
        # K_A^2 + K_B^2 + 2*gamma*S_A*S_B = 100 + 64 + 2*0.25*10*8 = 204
        assert total == pytest.approx(math.sqrt(204.0), rel=1e-6)

    def test_single_bucket(self) -> None:
        """Single bucket -> total = K_b."""
        charges = {"USD": 15.0}
        net_sens = {"USD": 15.0}
        total = inter_bucket_aggregation(charges, net_sens, 0.5)
        assert total == pytest.approx(15.0)

    def test_uncorrelated_buckets(self) -> None:
        """gamma=0 -> total = sqrt(sum K_b^2)."""
        charges = {"A": 3.0, "B": 4.0}
        net_sens = {"A": 3.0, "B": 4.0}
        total = inter_bucket_aggregation(charges, net_sens, 0.0)
        assert total == pytest.approx(5.0, rel=1e-6)

    def test_s_b_capping(self) -> None:
        """S_b is capped to [-K_b, K_b] before cross-bucket aggregation."""
        charges = {"A": 5.0, "B": 3.0}
        # S_b much larger than K_b -> should be capped to K_b
        net_sens = {"A": 100.0, "B": 100.0}
        total = inter_bucket_aggregation(charges, net_sens, 0.5)
        # Capped: S_A=5, S_B=3
        expected = math.sqrt(25.0 + 9.0 + 2 * 0.5 * 5.0 * 3.0)
        assert total == pytest.approx(expected, rel=1e-6)

    def test_empty_buckets(self) -> None:
        """Empty input returns 0."""
        total = inter_bucket_aggregation({}, {}, 0.5)
        assert total == pytest.approx(0.0)


class TestScenarioMultiplier:
    """Tests for correlation scenario adjustment per MAR21.6."""

    def test_medium_no_change(self) -> None:
        """MEDIUM scenario returns unchanged correlation."""
        assert apply_scenario_multiplier(0.5, CorrelationScenario.MEDIUM) == pytest.approx(0.5)

    def test_high_multiplies_by_125(self) -> None:
        """HIGH scenario: min(1.0, 1.25 * rho)."""
        assert apply_scenario_multiplier(0.5, CorrelationScenario.HIGH) == pytest.approx(0.625)

    def test_high_capped_at_1(self) -> None:
        """HIGH scenario capped at 1.0."""
        assert apply_scenario_multiplier(0.9, CorrelationScenario.HIGH) == pytest.approx(1.0)

    def test_low_scenario(self) -> None:
        """LOW scenario: max(2*rho - 1, 0.75*rho)."""
        result = apply_scenario_multiplier(0.8, CorrelationScenario.LOW)
        expected = max(2 * 0.8 - 1, 0.75 * 0.8)
        assert result == pytest.approx(expected)


# =========================================================================
#  Math Helpers Tests
# =========================================================================


class TestVasicek:
    """Tests for Vasicek conditional PD per BCBS d424 CRE31.6."""

    def test_known_inputs(self) -> None:
        """Vasicek conditional PD with known pd=0.01, R=0.15, conf=0.999."""
        cpd = vasicek_conditional_pd(0.01, 0.15, 0.999)
        # Should produce a significantly elevated PD (>>0.01)
        assert cpd > 0.01
        assert cpd < 1.0

    def test_pd_zero_returns_zero(self) -> None:
        """pd=0 is a boundary: returns 0."""
        assert vasicek_conditional_pd(0.0, 0.15) == pytest.approx(0.0)

    def test_pd_one_returns_one(self) -> None:
        """pd=1 is a boundary: returns 1."""
        assert vasicek_conditional_pd(1.0, 0.15) == pytest.approx(1.0)

    def test_higher_correlation_higher_cpd(self) -> None:
        """Higher correlation increases conditional PD."""
        cpd_low = vasicek_conditional_pd(0.02, 0.10)
        cpd_high = vasicek_conditional_pd(0.02, 0.24)
        assert cpd_high > cpd_low


class TestMerton:
    """Tests for Merton distance-to-default."""

    def test_basic_calculation(self) -> None:
        """DD for a healthy firm (V/D=2, sigma=0.3)."""
        dd = merton_distance_to_default(200.0, 100.0, 0.3, 1.0, 0.04)
        # ln(2) + (0.04 - 0.045)*1 = 0.6931 - 0.005 = 0.6881 / 0.3 = ~2.29
        expected = (math.log(2) + (0.04 - 0.5 * 0.09)) / 0.3
        assert dd == pytest.approx(expected, rel=1e-4)

    def test_zero_asset_value(self) -> None:
        """Asset value <= 0 returns DD=0."""
        assert merton_distance_to_default(0.0, 100.0, 0.3) == pytest.approx(0.0)

    def test_pd_from_dd(self) -> None:
        """PD = N(-DD): high DD -> low PD."""
        pd = pd_from_distance_to_default(3.0)
        assert pd < 0.01  # 3 sigma away -> very low PD


class TestInterpolation:
    """Tests for LTV-based risk weight interpolation."""

    def test_below_first_breakpoint(self) -> None:
        """LTV below first breakpoint returns first RW."""
        rw = interpolate_risk_weight(0.1, [0.5, 0.8, 1.0], [0.2, 0.5, 1.0])
        assert rw == pytest.approx(0.2)

    def test_above_last_breakpoint(self) -> None:
        """LTV above last breakpoint returns last RW."""
        rw = interpolate_risk_weight(1.5, [0.5, 0.8, 1.0], [0.2, 0.5, 1.0])
        assert rw == pytest.approx(1.0)

    def test_midpoint_interpolation(self) -> None:
        """LTV at midpoint between breakpoints interpolates linearly."""
        rw = interpolate_risk_weight(0.65, [0.5, 0.8], [0.2, 0.5])
        # (0.65-0.5)/(0.8-0.5) = 0.5, so 0.2 + 0.5*(0.5-0.2) = 0.35
        assert rw == pytest.approx(0.35)


class TestEffectiveMaturity:
    """Tests for effective maturity per BCBS d424 CRE32.17."""

    def test_basic_cashflows(self) -> None:
        """Weighted average of cash flows, clamped to [1, 5]."""
        cfs = [(1.0, 50.0), (2.0, 50.0), (3.0, 100.0)]
        m = effective_maturity(cfs)
        expected = (50 + 100 + 300) / 200
        assert m == pytest.approx(expected)

    def test_floor_at_1_year(self) -> None:
        """Effective maturity floored at 1 year."""
        cfs = [(0.25, 100.0)]
        m = effective_maturity(cfs)
        assert m == pytest.approx(1.0)

    def test_cap_at_5_years(self) -> None:
        """Effective maturity capped at 5 years."""
        cfs = [(10.0, 100.0)]
        m = effective_maturity(cfs)
        assert m == pytest.approx(5.0)

    def test_empty_cashflows_default(self) -> None:
        """Empty cash flows return default 2.5 years (F-IRB)."""
        m = effective_maturity([])
        assert m == pytest.approx(2.5)


class TestPortfolioStats:
    """Tests for portfolio variance and HHI."""

    def test_portfolio_variance(self) -> None:
        """Portfolio variance = w' * C * w for weighted exposures."""
        exposures = np.array([100.0, 200.0])
        corr = np.array([[1.0, 0.3], [0.3, 1.0]])
        lr = np.array([0.01, 0.02])
        var = portfolio_variance(exposures, corr, lr)
        # weighted = [1.0, 4.0], var = 1*1*1 + 2*0.3*1*4 + 4*4*1 = 1+2.4+16=19.4
        weighted = exposures * lr  # [1.0, 4.0]
        expected = float(weighted @ corr @ weighted)
        assert var == pytest.approx(expected)

    def test_hhi_equal_weights(self) -> None:
        """HHI for equal exposures = 1/n."""
        exposures = np.array([100.0, 100.0, 100.0, 100.0])
        assert herfindahl_index(exposures) == pytest.approx(0.25)

    def test_hhi_concentrated(self) -> None:
        """HHI for fully concentrated portfolio = 1.0."""
        exposures = np.array([1000.0, 0.0, 0.0])
        # Only one non-zero: (1)^2 = 1.0
        assert herfindahl_index(exposures) == pytest.approx(1.0)

    def test_hhi_zero_total(self) -> None:
        """HHI for zero total exposure = 0."""
        exposures = np.array([0.0, 0.0])
        assert herfindahl_index(exposures) == pytest.approx(0.0)


class TestKupiecTest:
    """Tests for Kupiec VaR backtesting per MAR99."""

    def test_basic_pass(self) -> None:
        """2 exceptions in 250 days at 99% should pass."""
        lr, passed = kupiec_test(2, 250, 0.99)
        assert passed is True

    def test_many_exceptions_fail(self) -> None:
        """20 exceptions in 250 days at 99% should fail."""
        lr, passed = kupiec_test(20, 250, 0.99)
        assert passed is False

    def test_zero_exceptions(self) -> None:
        """0 exceptions always passes."""
        lr, passed = kupiec_test(0, 250, 0.99)
        assert passed is True
        assert lr == pytest.approx(0.0)

    def test_zero_observations(self) -> None:
        """0 observations returns (0, True)."""
        lr, passed = kupiec_test(0, 0, 0.99)
        assert passed is True


class TestDiscountFactor:
    """Tests for discount factor and present value calculations."""

    def test_continuous_discount(self) -> None:
        """Continuous: DF = exp(-r*t)."""
        df = discount_factor(0.05, 2.0, "continuous")
        assert df == pytest.approx(math.exp(-0.1), rel=1e-6)

    def test_annual_discount(self) -> None:
        """Annual: DF = 1/(1+r)^t."""
        df = discount_factor(0.05, 2.0, "annual")
        assert df == pytest.approx(1.0 / 1.05**2, rel=1e-6)

    def test_present_value(self) -> None:
        """PV of two cash flows."""
        cfs = [(1.0, 100.0), (2.0, 100.0)]
        pv = present_value(cfs, 0.05, "continuous")
        expected = 100.0 * math.exp(-0.05) + 100.0 * math.exp(-0.10)
        assert pv == pytest.approx(expected, rel=1e-6)


# =========================================================================
#  BCBS 239 Tests
# =========================================================================


class TestDataQualityChecks:
    """Tests for BCBS 239 data quality check functions."""

    def test_completeness_pass(self) -> None:
        """Non-null value passes completeness check."""
        check = check_completeness("counterparty_id", "CP-001")
        assert check.status == QualityStatus.PASS
        assert check.dimension == DataQualityDimension.COMPLETENESS

    def test_completeness_fail_none(self) -> None:
        """None value fails completeness check for required field."""
        check = check_completeness("counterparty_id", None, required=True)
        assert check.status == QualityStatus.FAIL

    def test_completeness_fail_empty_string(self) -> None:
        """Empty string fails completeness check."""
        check = check_completeness("name", "  ", required=True)
        assert check.status == QualityStatus.FAIL

    def test_completeness_warning_optional(self) -> None:
        """None in optional field gives WARNING, not FAIL."""
        check = check_completeness("lei", None, required=False)
        assert check.status == QualityStatus.WARNING

    def test_range_pass(self) -> None:
        """Value within range passes."""
        check = check_range("risk_weight", 0.65, min_val=0.0, max_val=2.5)
        assert check.status == QualityStatus.PASS

    def test_range_fail_below_min(self) -> None:
        """Value below minimum fails."""
        check = check_range("pd", -0.01, min_val=0.0)
        assert check.status == QualityStatus.FAIL

    def test_range_fail_above_max(self) -> None:
        """Value above maximum fails."""
        check = check_range("lgd", 1.5, max_val=1.0)
        assert check.status == QualityStatus.FAIL

    def test_consistency_pass(self) -> None:
        """Two values within tolerance pass consistency check."""
        check = check_consistency("total_rwa", 1000.0, 1005.0, tolerance=0.01)
        assert check.status == QualityStatus.PASS

    def test_consistency_warning(self) -> None:
        """Moderate difference gives WARNING."""
        check = check_consistency("total_rwa", 1000.0, 1020.0, tolerance=0.01)
        assert check.status == QualityStatus.WARNING


class TestDataQualityReport:
    """Tests for DataQualityReport aggregation."""

    def test_report_scoring(self) -> None:
        """Overall quality score: (passed + 0.5*warnings) / total."""
        report = DataQualityReport(module_name="test_module")
        report.add_check(DataQualityCheck(
            dimension=DataQualityDimension.COMPLETENESS,
            check_name="check1",
            status=QualityStatus.PASS,
        ))
        report.add_check(DataQualityCheck(
            dimension=DataQualityDimension.ACCURACY,
            check_name="check2",
            status=QualityStatus.WARNING,
        ))
        # Score = (1 + 0.5) / 2 = 0.75
        assert report.overall_quality_score == pytest.approx(0.75)
        assert report.total_checks == 2
        assert report.passed == 1
        assert report.warnings == 1

    def test_report_all_pass(self) -> None:
        """All passing checks -> score = 1.0."""
        report = DataQualityReport(module_name="perfect")
        for i in range(5):
            report.add_check(DataQualityCheck(
                dimension=DataQualityDimension.COMPLETENESS,
                check_name=f"check{i}",
                status=QualityStatus.PASS,
            ))
        assert report.overall_quality_score == pytest.approx(1.0)

    def test_report_empty(self) -> None:
        """Empty report defaults to 1.0 score."""
        report = DataQualityReport(module_name="empty")
        assert report.overall_quality_score == pytest.approx(1.0)


class TestLineageTrail:
    """Tests for BCBS 239 data lineage tracking."""

    def test_record_and_retrieve(self) -> None:
        """Record events and retrieve full trail."""
        trail = LineageTrail(trail_id="TEST-001")
        trail.record(
            LineageEventType.SOURCE_INPUT,
            "credit_risk",
            "Loaded counterparty data",
        )
        trail.record(
            LineageEventType.CALCULATION,
            "credit_risk",
            "Computed RWA",
        )
        entries = trail.get_trail()
        assert len(entries) == 2
        assert entries[0].event_type == LineageEventType.SOURCE_INPUT
        assert entries[1].event_type == LineageEventType.CALCULATION

    def test_hash_generation(self) -> None:
        """SHA-256 hash is generated for input/output data."""
        trail = LineageTrail()
        entry = trail.record(
            LineageEventType.TRANSFORMATION,
            "utils",
            "Transformed data",
            input_data={"key": "value"},
            output_data=[1, 2, 3],
        )
        assert len(entry.input_hash) == 16  # truncated hex
        assert len(entry.output_hash) == 16

    def test_lineage_event_type_enum(self) -> None:
        """All 7 lineage event types exist."""
        assert len(LineageEventType) == 7
        assert LineageEventType.SOURCE_INPUT.value == "SOURCE_INPUT"
        assert LineageEventType.ERROR.value == "ERROR"

    def test_trail_returns_copy(self) -> None:
        """get_trail returns a copy, not the internal list."""
        trail = LineageTrail()
        trail.record(LineageEventType.OUTPUT, "test", "output")
        entries = trail.get_trail()
        entries.clear()
        assert len(trail.get_trail()) == 1
