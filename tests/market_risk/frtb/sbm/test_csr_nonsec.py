"""Tests for CSR non-securitization parameters and calculator.

Regulatory basis: ERBA NPR §__.208(c), §__.209(b)(2) (Table 3, Table 4),
§__.209(c), §__.209(d), §__.206.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.enums import (
    CorrelationScenario,
    CreditQuality,
    CSRBucket,
    CSRSector,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.exceptions import ValidationError
from src.core.models import Sensitivity
from src.market_risk.frtb.sbm.csr_nonsec import CSRNonSecCalculator
from src.market_risk.frtb.sbm.csr_nonsec_params import (
    BUCKET_SECTOR_QUALITY,
    DELTA_RISK_WEIGHTS,
    GAMMA_SECTOR_TABLE4,
    INTER_BUCKET_CORRELATIONS,
    OTHER_SECTOR_BUCKET,
    RHO_BASIS_DIFF_CURVE,
    RHO_NAME_DIFF,
    RHO_NAME_DIFF_INDEX,
    RHO_TENOR_DIFF,
    SECTOR_GROUPS,
    TENORS,
    VEGA_ALPHA,
    VEGA_RISK_WEIGHT,
    apply_correlation_scenario,
    build_csr_nonsec_correlation_matrix,
    compute_curvature_correlation,
    compute_gamma_rating,
    compute_gamma_sector,
    compute_intra_bucket_correlation,
    compute_name_correlation,
    compute_tenor_correlation,
    compute_vega_correlation,
    get_bucket_for_sector_quality,
    get_curvature_risk_weight,
    get_delta_risk_weight,
    get_inter_bucket_correlation,
)


def _sens(
    bucket: str,
    value: float,
    tenor: GIRRTenor | None = GIRRTenor.Y5,
    label: str = "ACME",
    risk_measure: RiskMeasure = RiskMeasure.DELTA,
    option_maturity: float | None = None,
) -> Sensitivity:
    return Sensitivity(
        risk_class=RiskClass.CSR_NON_SEC,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
        tenor=tenor,
        label=label,
        value=value,
        option_maturity=option_maturity,
    )


# =========================================================================
#  Table 3 -- buckets and delta risk weights
# =========================================================================

class TestTable3Buckets:
    """ERBA NPR §__.209(b)(2) Table 3."""

    def test_twenty_buckets(self) -> None:
        assert sorted(DELTA_RISK_WEIGHTS) == list(range(1, 21))
        assert sorted(BUCKET_SECTOR_QUALITY) == list(range(1, 21))
        assert len(CSRBucket) == 20

    @pytest.mark.parametrize(
        "bucket, rw",
        [
            (1, 0.005), (2, 0.010), (3, 0.050), (4, 0.030), (5, 0.030),
            (6, 0.020), (7, 0.015), (8, 0.015),
            (9, 0.030), (10, 0.040), (11, 0.120),
            (12, 0.070), (13, 0.085), (14, 0.055), (15, 0.050), (16, 0.025),
            (17, 0.070), (18, 0.120), (19, 0.015), (20, 0.050),
        ],
    )
    def test_delta_risk_weights(self, bucket: int, rw: float) -> None:
        assert get_delta_risk_weight(bucket) == pytest.approx(rw)

    def test_curvature_rw_equals_highest_delta_rw(self) -> None:
        """§__.209(d): curvature RW = highest delta RW in bucket (tenor-uniform here)."""
        for b in range(1, 21):
            assert get_curvature_risk_weight(b) == get_delta_risk_weight(b)

    def test_tenor_vertices(self) -> None:
        """§__.208(c)(1): 0.5, 1, 3, 5, 10 years."""
        assert TENORS == [0.5, 1.0, 3.0, 5.0, 10.0]

    @pytest.mark.parametrize(
        "sector, quality, bucket",
        [
            (CSRSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE, 1),
            (CSRSector.PSE, CreditQuality.INVESTMENT_GRADE, 2),
            (CSRSector.FINANCIALS, CreditQuality.INVESTMENT_GRADE, 3),
            (CSRSector.BASIC_MATERIALS, CreditQuality.INVESTMENT_GRADE, 4),
            (CSRSector.CONSUMER, CreditQuality.INVESTMENT_GRADE, 5),
            (CSRSector.TECH_TELECOM, CreditQuality.INVESTMENT_GRADE, 6),
            (CSRSector.HEALTHCARE_UTILITIES, CreditQuality.INVESTMENT_GRADE, 7),
            (CSRSector.COVERED_BOND, CreditQuality.INVESTMENT_GRADE, 8),
            (CSRSector.SOVEREIGN, CreditQuality.SPECULATIVE_GRADE, 9),
            (CSRSector.PSE, CreditQuality.SPECULATIVE_GRADE, 10),
            (CSRSector.FINANCIALS, CreditQuality.SPECULATIVE_GRADE, 11),
            (CSRSector.BASIC_MATERIALS, CreditQuality.SPECULATIVE_GRADE, 12),
            (CSRSector.BASIC_MATERIALS, CreditQuality.SUB_SPECULATIVE_GRADE, 12),
            (CSRSector.CONSUMER, CreditQuality.SUB_SPECULATIVE_GRADE, 13),
            (CSRSector.TECH_TELECOM, CreditQuality.SUB_SPECULATIVE_GRADE, 14),
            (CSRSector.HEALTHCARE_UTILITIES, CreditQuality.SPECULATIVE_GRADE, 15),
            (CSRSector.COVERED_BOND, CreditQuality.SUB_SPECULATIVE_GRADE, 16),
            (CSRSector.SOVEREIGN, CreditQuality.SUB_SPECULATIVE_GRADE, 17),
            (CSRSector.OTHER, CreditQuality.INVESTMENT_GRADE, 18),
            (CSRSector.OTHER, CreditQuality.SUB_SPECULATIVE_GRADE, 18),
            (CSRSector.INDEX, CreditQuality.INVESTMENT_GRADE, 19),
            (CSRSector.INDEX, CreditQuality.SPECULATIVE_GRADE, 20),
            (CSRSector.INDEX, CreditQuality.SUB_SPECULATIVE_GRADE, 20),
            # TODO: VERIFY mapping -- sub-spec PSE / financials -> 10 / 11
            (CSRSector.PSE, CreditQuality.SUB_SPECULATIVE_GRADE, 10),
            (CSRSector.FINANCIALS, CreditQuality.SUB_SPECULATIVE_GRADE, 11),
        ],
    )
    def test_bucket_lookup(self, sector: CSRSector, quality: CreditQuality, bucket: int) -> None:
        assert get_bucket_for_sector_quality(sector, quality) == bucket

    def test_every_sector_quality_pair_resolves(self) -> None:
        for sector in CSRSector:
            for quality in CreditQuality:
                assert 1 <= get_bucket_for_sector_quality(sector, quality) <= 20


# =========================================================================
#  Intra-bucket correlation
# =========================================================================

class TestIntraBucketCorrelation:
    """ERBA NPR §__.209(b)(2): rho = rho_name x rho_tenor x rho_basis."""

    def test_name_correlation(self) -> None:
        assert compute_name_correlation(3, same_issuer=True) == 1.0
        assert compute_name_correlation(3, same_issuer=False) == pytest.approx(0.35)
        assert compute_name_correlation(19, same_issuer=False) == pytest.approx(0.80)
        assert compute_name_correlation(20, same_issuer=False) == pytest.approx(0.80)
        assert RHO_NAME_DIFF == 0.35 and RHO_NAME_DIFF_INDEX == 0.80

    def test_tenor_correlation_is_fixed_not_exponential(self) -> None:
        assert compute_tenor_correlation(5.0, 5.0) == 1.0
        assert compute_tenor_correlation(0.5, 10.0) == pytest.approx(0.65)
        assert compute_tenor_correlation(3.0, 5.0) == pytest.approx(0.65)
        assert RHO_TENOR_DIFF == 0.65

    def test_basis_correlation(self) -> None:
        assert RHO_BASIS_DIFF_CURVE == 0.999

    def test_full_product(self) -> None:
        rho = compute_intra_bucket_correlation(
            bucket=4, tenor_k=1.0, tenor_l=3.0, same_issuer=False, same_curve=False
        )
        assert rho == pytest.approx(0.35 * 0.65 * 0.999)

    def test_same_name_same_tenor_different_curve(self) -> None:
        rho = compute_intra_bucket_correlation(1, 5.0, 5.0, same_issuer=True, same_curve=False)
        assert rho == pytest.approx(0.999)

    def test_matrix_symmetric_unit_diagonal(self) -> None:
        corr = build_csr_nonsec_correlation_matrix(
            bucket=4,
            issuers=["A", "A", "B"],
            tenors=[1.0, 5.0, 1.0],
            curves=["BOND", "BOND", "CDS"],
        )
        assert np.allclose(corr, corr.T)
        assert np.allclose(np.diag(corr), 1.0)
        assert corr[0, 1] == pytest.approx(0.65)
        assert corr[0, 2] == pytest.approx(0.35 * 0.999)

    def test_curvature_correlation_is_name_basis_squared(self) -> None:
        rho_4 = compute_curvature_correlation(4, same_issuer=False, same_curve=True)
        rho_19 = compute_curvature_correlation(19, same_issuer=False, same_curve=True)
        assert rho_4 == pytest.approx(0.35 ** 2)
        assert rho_19 == pytest.approx(0.80 ** 2)


# =========================================================================
#  Inter-bucket correlation -- gamma_rating x gamma_sector (Table 4)
# =========================================================================

class TestInterBucketCorrelation:
    """ERBA NPR §__.209(b)(2), Table 4."""

    def test_matrix_shape(self) -> None:
        assert len(INTER_BUCKET_CORRELATIONS) == 400
        for b in range(1, 21):
            assert INTER_BUCKET_CORRELATIONS[(b, b)] == 1.0

    def test_symmetric(self) -> None:
        for b in range(1, 21):
            for c in range(1, 21):
                assert get_inter_bucket_correlation(b, c) == pytest.approx(
                    get_inter_bucket_correlation(c, b)
                )

    @pytest.mark.parametrize(
        "b, c, gamma",
        [
            (1, 2, 0.75),    # same quality, sov vs PSE
            (1, 9, 0.50),    # same sector, different quality
            (1, 17, 0.50),   # IG vs sub-spec sovereigns
            (9, 17, 1.00),   # spec vs sub-spec = ONE category, same sector
            (1, 11, 0.05),   # different sector AND quality: 0.5 x 0.10
            (1, 3, 0.10),
            (3, 11, 0.50),
            (19, 20, 0.75),
            (18, 1, 0.0), (18, 11, 0.0), (18, 19, 0.0), (18, 20, 0.0),
            (1, 19, 0.45), (11, 20, 0.45), (8, 19, 0.45),
            (2, 3, 0.05), (4, 6, 0.25), (5, 6, 0.25), (3, 8, 0.20),
            (4, 13, 0.10),   # basic materials IG vs consumer spec: 0.5 x 0.20
            (12, 13, 0.20),  # both non-IG, different sector
            (7, 8, 0.05), (6, 8, 0.20), (2, 10, 0.50),
        ],
    )
    def test_regulatory_examples(self, b: int, c: int, gamma: float) -> None:
        assert get_inter_bucket_correlation(b, c) == pytest.approx(gamma)

    def test_gamma_rating_rules(self) -> None:
        assert compute_gamma_rating(1, 9) == 0.5
        assert compute_gamma_rating(9, 17) == 1.0
        assert compute_gamma_rating(1, 18) == 1.0
        assert compute_gamma_rating(1, 19) == 1.0
        assert compute_gamma_rating(19, 20) == 1.0

    def test_gamma_sector_table4_complete(self) -> None:
        n = len(SECTOR_GROUPS)
        assert n == 11
        assert len(GAMMA_SECTOR_TABLE4) == n * (n - 1) // 2
        assert compute_gamma_sector(1, 9) == 1.0
        assert compute_gamma_sector(1, 2) == 0.75

    def test_scenario_adjustment(self) -> None:
        high = apply_correlation_scenario(0.75, CorrelationScenario.HIGH)
        low = apply_correlation_scenario(0.75, CorrelationScenario.LOW)
        assert high == pytest.approx(0.9375)
        assert low == pytest.approx(max(0.5, 0.5625))
        assert apply_correlation_scenario(0.9, CorrelationScenario.HIGH) == 1.0


# =========================================================================
#  Vega
# =========================================================================

class TestVega:
    """ERBA NPR §__.209(c)."""

    def test_vega_rw_100pct(self) -> None:
        assert VEGA_RISK_WEIGHT == 1.0

    def test_vega_correlation(self) -> None:
        assert compute_vega_correlation(3, 1.0, 1.0, same_issuer=True) == 1.0
        expected = 0.35 * math.exp(-VEGA_ALPHA * abs(1.0 - 5.0) / 1.0)
        assert compute_vega_correlation(3, 1.0, 5.0, same_issuer=False) == pytest.approx(expected)
        assert compute_vega_correlation(3, 1.0, 5.0, same_issuer=False) <= 1.0


# =========================================================================
#  Calculator
# =========================================================================

class TestCalculator:
    """End-to-end CSR non-sec calculator behaviour."""

    @pytest.fixture
    def calc(self) -> CSRNonSecCalculator:
        return CSRNonSecCalculator()

    def test_single_bucket3_delta(self, calc: CSRNonSecCalculator) -> None:
        """Bucket 3 IG financials, RW 5.0 % -> K_b = 0.05 x 1e6."""
        result = calc.calculate([_sens("3", 1e6)])
        assert result.delta_medium.capital_charge == pytest.approx(50_000.0)
        assert result.delta_charge == pytest.approx(50_000.0)

    def test_single_bucket11_delta(self, calc: CSRNonSecCalculator) -> None:
        result = calc.calculate([_sens("11", 1e6)])
        assert result.delta_charge == pytest.approx(120_000.0)

    def test_two_names_same_bucket_medium(self, calc: CSRNonSecCalculator) -> None:
        """K_b = sqrt(WS1^2 + WS2^2 + 2 x 0.35 x WS1 WS2) for two names, same tenor."""
        sens = [_sens("4", 1e6, label="A"), _sens("4", 1e6, label="B")]
        result = calc.calculate(sens)
        ws = 0.03 * 1e6
        expected = math.sqrt(2 * ws ** 2 + 2 * 0.35 * ws * ws)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_same_name_different_tenor(self, calc: CSRNonSecCalculator) -> None:
        sens = [_sens("4", 1e6, tenor=GIRRTenor.Y1), _sens("4", 1e6, tenor=GIRRTenor.Y5)]
        result = calc.calculate(sens)
        ws = 0.03 * 1e6
        expected = math.sqrt(2 * ws ** 2 + 2 * 0.65 * ws * ws)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_bucket18_sum_of_abs(self, calc: CSRNonSecCalculator) -> None:
        """§__.209(b)(2): other sector K_b = sum |WS_k| -- no offsetting."""
        sens = [_sens("18", 1e6, label="X"), _sens("18", -1e6, label="Y")]
        result = calc.calculate(sens)
        assert result.delta_medium.capital_charge == pytest.approx(2 * 0.12 * 1e6)
        assert result.delta_low.capital_charge == pytest.approx(2 * 0.12 * 1e6)
        assert result.delta_high.capital_charge == pytest.approx(2 * 0.12 * 1e6)

    def test_bucket18_does_not_diversify_with_others(self, calc: CSRNonSecCalculator) -> None:
        """gamma(18, x) = 0 -> total = sqrt(K18^2 + Kx^2)."""
        result = calc.calculate([_sens("18", 1e6), _sens("3", 1e6)])
        expected = math.sqrt((0.12e6) ** 2 + (0.05e6) ** 2)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_inter_bucket_1_2(self, calc: CSRNonSecCalculator) -> None:
        """gamma(1,2) = 0.75."""
        result = calc.calculate([_sens("1", 1e6), _sens("2", 1e6)])
        k1, k2 = 0.005e6, 0.01e6
        expected = math.sqrt(k1 ** 2 + k2 ** 2 + 2 * 0.75 * k1 * k2)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_inter_bucket_1_11(self, calc: CSRNonSecCalculator) -> None:
        """gamma(1,11) = 0.05."""
        result = calc.calculate([_sens("1", 1e6), _sens("11", 1e6)])
        k1, k11 = 0.005e6, 0.12e6
        expected = math.sqrt(k1 ** 2 + k11 ** 2 + 2 * 0.05 * k1 * k11)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_index_buckets_name_corr_80pct(self, calc: CSRNonSecCalculator) -> None:
        sens = [_sens("19", 1e6, label="CDX.IG"), _sens("19", 1e6, label="ITRX.MAIN")]
        result = calc.calculate(sens)
        ws = 0.015e6
        expected = math.sqrt(2 * ws ** 2 + 2 * 0.80 * ws * ws)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_vega_charge(self, calc: CSRNonSecCalculator) -> None:
        vega = RiskMeasure.VEGA
        sens = [
            _sens("3", 1e5, tenor=None, risk_measure=vega, option_maturity=1.0, label="A"),
            _sens("3", 1e5, tenor=None, risk_measure=vega, option_maturity=5.0, label="A"),
        ]
        result = calc.calculate(sens)
        rho = math.exp(-0.01 * 4.0 / 1.0)
        expected = math.sqrt(2 * 1e10 + 2 * rho * 1e10)
        assert result.vega_medium.capital_charge == pytest.approx(expected)

    def test_vega_bucket18_sum_abs(self, calc: CSRNonSecCalculator) -> None:
        vega = RiskMeasure.VEGA
        sens = [
            _sens("18", 1e5, tenor=None, risk_measure=vega, option_maturity=1.0, label="A"),
            _sens("18", -1e5, tenor=None, risk_measure=vega, option_maturity=1.0, label="B"),
        ]
        result = calc.calculate(sens)
        assert result.vega_medium.capital_charge == pytest.approx(2e5)

    def test_curvature_two_names(self, calc: CSRNonSecCalculator) -> None:
        """rho_curv = 0.35^2 for different names in bucket 4."""
        sens = [
            _sens("4", 1e5, tenor=None, risk_measure=RiskMeasure.CURVATURE, label="A"),
            _sens("4", 1e5, tenor=None, risk_measure=RiskMeasure.CURVATURE, label="B"),
        ]
        result = calc.calculate(sens)
        expected = math.sqrt(2 * 1e10 + 2 * (0.35 ** 2) * 1e10)
        assert result.curvature_medium.capital_charge == pytest.approx(expected)

    def test_curvature_bucket18(self, calc: CSRNonSecCalculator) -> None:
        sens = [
            _sens("18", 1e5, tenor=None, risk_measure=RiskMeasure.CURVATURE, label="A"),
            _sens("18", -4e4, tenor=None, risk_measure=RiskMeasure.CURVATURE, label="B"),
        ]
        result = calc.calculate(sens)
        assert result.curvature_medium.capital_charge == pytest.approx(1e5)

    def test_rejects_non_csr_tenor(self, calc: CSRNonSecCalculator) -> None:
        with pytest.raises(ValidationError):
            calc.calculate([_sens("3", 1e6, tenor=GIRRTenor.Y2)])

    def test_rejects_unknown_bucket(self, calc: CSRNonSecCalculator) -> None:
        from src.core.exceptions import CalculationError
        with pytest.raises(CalculationError):
            calc.calculate([_sens("21", 1e6)])

    def test_scenarios_ordered(self, calc: CSRNonSecCalculator) -> None:
        sens = [_sens("1", 1e6), _sens("2", 1e6), _sens("3", 1e6)]
        result = calc.calculate(sens)
        assert result.delta_low.capital_charge <= result.delta_medium.capital_charge
        assert result.delta_medium.capital_charge <= result.delta_high.capital_charge

    def test_other_sector_constant(self) -> None:
        assert OTHER_SECTOR_BUCKET == 18
