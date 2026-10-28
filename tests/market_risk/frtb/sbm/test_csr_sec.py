"""Tests for CSR securitization (CTP and non-CTP) parameters and calculator.

Regulatory basis: ERBA NPR §__.208(d)-(e), §__.209(b)(3) (Table 5, Table 6),
§__.209(b)(4) (Table 7), §__.209(c), §__.209(d), §__.206.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.enums import (
    CreditQuality,
    CSRSecAssetType,
    CSRSecBucket,
    CSRSecCTPBucket,
    CSRSecSeniority,
    CSRSector,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.exceptions import CalculationError, ValidationError
from src.core.models import Sensitivity
from src.market_risk.frtb.sbm.csr_sec import CSRSecCalculator
from src.market_risk.frtb.sbm.csr_sec_params import (
    CSR_SEC_CTP_RW,
    CSR_SEC_NON_CTP_RW,
    CTP_INTER_BUCKET_CORRELATIONS,
    CTP_SECTOR_GROUPS,
    GAMMA_NON_CTP,
    GAMMA_SECTOR_TABLE6,
    NON_CTP_BUCKET_NAMES,
    OTHER_SECTOR_BUCKET_CTP,
    OTHER_SECTOR_BUCKET_NON_CTP,
    RHO_CTP_BASIS_DIFF_CURVE,
    RHO_CTP_NAME_DIFF,
    RHO_CTP_TENOR_DIFF,
    RHO_TENOR_DIFF_NON_CTP,
    RHO_TRANCHE_DIFF,
    TENORS,
    TRANCHE_NOTIONAL_OVERLAP_THRESHOLD,
    VEGA_RISK_WEIGHT,
    build_csr_sec_correlation_matrix,
    compute_curvature_correlation,
    compute_intra_bucket_correlation,
    compute_vega_correlation,
    get_ctp_bucket_for_sector_quality,
    get_ctp_risk_weight,
    get_inter_bucket_correlation,
    get_non_ctp_bucket,
    get_non_ctp_risk_weight,
)


def _sens(
    risk_class: RiskClass,
    bucket: str,
    value: float,
    tenor: GIRRTenor | None = GIRRTenor.Y5,
    label: str = "TRANCHE_A",
    risk_measure: RiskMeasure = RiskMeasure.DELTA,
    option_maturity: float | None = None,
) -> Sensitivity:
    return Sensitivity(
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
        tenor=tenor,
        label=label,
        value=value,
        option_maturity=option_maturity,
    )


NC = RiskClass.CSR_SEC_NON_CTP
CTP = RiskClass.CSR_SEC_CTP
SEN, NSEN = CSRSecSeniority.SENIOR, CSRSecSeniority.NON_SENIOR
IG, SG, SSG = (
    CreditQuality.INVESTMENT_GRADE,
    CreditQuality.SPECULATIVE_GRADE,
    CreditQuality.SUB_SPECULATIVE_GRADE,
)
AT = CSRSecAssetType


# =========================================================================
#  Non-CTP -- Table 7
# =========================================================================

class TestNonCTPTable7:
    """ERBA NPR §__.209(b)(4) Table 7."""

    def test_25_buckets(self) -> None:
        assert sorted(CSR_SEC_NON_CTP_RW) == list(range(1, 26))
        assert len(CSRSecBucket) == 25
        assert len(NON_CTP_BUCKET_NAMES) == 25

    @pytest.mark.parametrize(
        "bucket, rw",
        [
            (1, 0.0090), (2, 0.0150), (3, 0.0200), (4, 0.0200),
            (5, 0.0080), (6, 0.0120), (7, 0.0120), (8, 0.0140),
            (9, 0.0113), (10, 0.0188), (11, 0.0250), (12, 0.0250),
            (13, 0.0100), (14, 0.0150), (15, 0.0150), (16, 0.0175),
            (17, 0.0158), (18, 0.0263), (19, 0.0350), (20, 0.0350),
            (21, 0.0140), (22, 0.0210), (23, 0.0210), (24, 0.0245),
            (25, 0.0350),
        ],
    )
    def test_risk_weights(self, bucket: int, rw: float) -> None:
        assert get_non_ctp_risk_weight(bucket) == pytest.approx(rw)

    @pytest.mark.parametrize(
        "seniority, quality, asset, bucket",
        [
            (SEN, IG, AT.RMBS_PRIME, 1),
            (SEN, IG, AT.CLO_NON_CTP, 8),
            (NSEN, IG, AT.RMBS_PRIME, 9),
            (NSEN, IG, AT.ABS_STUDENT_LOANS, 13),
            (SEN, SG, AT.RMBS_PRIME, 17),
            (NSEN, SSG, AT.CMBS, 20),
            (NSEN, SG, AT.ABS_AUTO_FLOORPLAN, 23),
            (SEN, SSG, AT.CLO_NON_CTP, 24),
            (SEN, IG, AT.OTHER, 25),
            (NSEN, SG, AT.OTHER, 25),
        ],
    )
    def test_bucket_lookup(
        self,
        seniority: CSRSecSeniority,
        quality: CreditQuality,
        asset: CSRSecAssetType,
        bucket: int,
    ) -> None:
        assert get_non_ctp_bucket(seniority, quality, asset) == bucket

    def test_all_combinations_resolve(self) -> None:
        for sen in CSRSecSeniority:
            for q in CreditQuality:
                for a in CSRSecAssetType:
                    assert 1 <= get_non_ctp_bucket(sen, q, a) <= 25

    def test_tenors(self) -> None:
        assert TENORS == [0.5, 1.0, 3.0, 5.0, 10.0]

    def test_gamma_zero(self) -> None:
        """§__.209(b)(4): gamma_bc = 0 % across non-CTP buckets."""
        assert GAMMA_NON_CTP == 0.0
        assert get_inter_bucket_correlation(1, 4) == 0.0
        assert get_inter_bucket_correlation(25, 1) == 0.0

    def test_intra_bucket_components(self) -> None:
        assert RHO_TRANCHE_DIFF == 0.40
        assert RHO_TENOR_DIFF_NON_CTP == 0.80
        assert TRANCHE_NOTIONAL_OVERLAP_THRESHOLD == 0.80
        rho_diff = compute_intra_bucket_correlation(1, 1.0, 5.0, same_tranche=False)
        assert rho_diff == pytest.approx(0.40 * 0.80)
        assert compute_intra_bucket_correlation(1, 5.0, 5.0, same_tranche=True) == 1.0
        assert compute_intra_bucket_correlation(
            1, 5.0, 5.0, same_tranche=True, same_curve=False
        ) == pytest.approx(0.999)

    def test_curvature_correlation_tranche_squared(self) -> None:
        assert compute_curvature_correlation(same_tranche=False) == pytest.approx(0.40 ** 2)
        assert compute_curvature_correlation(same_tranche=True) == 1.0

    def test_vega(self) -> None:
        assert VEGA_RISK_WEIGHT == 1.0
        rho = compute_vega_correlation(1.0, 3.0, same_tranche=False)
        assert rho == pytest.approx(0.40 * math.exp(-0.01 * 2.0 / 1.0))


# =========================================================================
#  CTP -- Table 5 / Table 6
# =========================================================================

class TestCTPTable5:
    """ERBA NPR §__.209(b)(3) Table 5 and Table 6."""

    def test_16_buckets(self) -> None:
        assert sorted(CSR_SEC_CTP_RW) == list(range(1, 17))
        assert len(CSRSecCTPBucket) == 16

    @pytest.mark.parametrize(
        "bucket, rw",
        [
            (1, 0.04), (2, 0.04), (3, 0.08), (4, 0.05), (5, 0.04), (6, 0.03), (7, 0.02),
            (8, 0.13), (9, 0.13),
            (10, 0.16), (11, 0.10), (12, 0.12), (13, 0.12), (14, 0.12),
            (15, 0.16), (16, 0.13),
        ],
    )
    def test_risk_weights(self, bucket: int, rw: float) -> None:
        assert get_ctp_risk_weight(bucket) == pytest.approx(rw)

    @pytest.mark.parametrize(
        "sector, quality, bucket",
        [
            (CSRSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE, 1),
            (CSRSector.FINANCIALS, CreditQuality.INVESTMENT_GRADE, 3),
            (CSRSector.SOVEREIGN, CreditQuality.SPECULATIVE_GRADE, 8),
            (CSRSector.PSE, CreditQuality.SPECULATIVE_GRADE, 9),
            (CSRSector.PSE, CreditQuality.SUB_SPECULATIVE_GRADE, 9),  # TODO: VERIFY mapping
            (CSRSector.FINANCIALS, CreditQuality.SPECULATIVE_GRADE, 10),
            (CSRSector.FINANCIALS, CreditQuality.SUB_SPECULATIVE_GRADE, 10),
            (CSRSector.HEALTHCARE_UTILITIES, CreditQuality.SUB_SPECULATIVE_GRADE, 14),
            (CSRSector.SOVEREIGN, CreditQuality.SUB_SPECULATIVE_GRADE, 15),
            (CSRSector.OTHER, CreditQuality.INVESTMENT_GRADE, 16),
        ],
    )
    def test_bucket_lookup(self, sector: CSRSector, quality: CreditQuality, bucket: int) -> None:
        assert get_ctp_bucket_for_sector_quality(sector, quality) == bucket

    def test_no_covered_bond_or_index_in_ctp(self) -> None:
        with pytest.raises(ValueError):
            get_ctp_bucket_for_sector_quality(CSRSector.COVERED_BOND, IG)
        with pytest.raises(ValueError):
            get_ctp_bucket_for_sector_quality(CSRSector.INDEX, IG)

    def test_intra_components(self) -> None:
        assert RHO_CTP_NAME_DIFF == 0.35
        assert RHO_CTP_TENOR_DIFF == 0.65
        assert RHO_CTP_BASIS_DIFF_CURVE == 0.99
        rho = compute_intra_bucket_correlation(
            3, 1.0, 5.0, same_tranche=False, is_ctp=True, same_curve=False
        )
        assert rho == pytest.approx(0.35 * 0.65 * 0.99)

    def test_inter_bucket_matrix(self) -> None:
        assert len(CTP_INTER_BUCKET_CORRELATIONS) == 256
        n = len(CTP_SECTOR_GROUPS)
        assert n == 8
        assert len(GAMMA_SECTOR_TABLE6) == n * (n - 1) // 2
        for b in range(1, 17):
            assert CTP_INTER_BUCKET_CORRELATIONS[(b, b)] == 1.0
            for c in range(1, 17):
                assert get_inter_bucket_correlation(b, c, is_ctp=True) == pytest.approx(
                    get_inter_bucket_correlation(c, b, is_ctp=True)
                )

    @pytest.mark.parametrize(
        "b, c, gamma",
        [
            (1, 2, 0.75),    # sov IG vs PSE IG
            (1, 8, 0.50),    # same sector, IG vs spec
            (8, 15, 1.00),   # spec vs sub-spec sovereigns = one category
            (1, 10, 0.05),   # sov IG vs fin spec: 0.5 x 0.10
            (1, 3, 0.10), (2, 3, 0.05), (3, 4, 0.05), (4, 6, 0.25), (5, 6, 0.25),
            (6, 7, 0.05), (1, 7, 0.15), (2, 7, 0.10), (3, 7, 0.05), (4, 7, 0.05), (5, 7, 0.05),
            (16, 1, 0.0), (16, 10, 0.0), (16, 15, 0.0),
            (4, 12, 0.10),   # basic materials IG vs consumer spec: 0.5 x 0.20
            (11, 12, 0.20),  # both non-IG, different sector
        ],
    )
    def test_regulatory_examples(self, b: int, c: int, gamma: float) -> None:
        assert get_inter_bucket_correlation(b, c, is_ctp=True) == pytest.approx(gamma)


# =========================================================================
#  Calculator -- non-CTP
# =========================================================================

class TestNonCTPCalculator:

    @pytest.fixture
    def calc(self) -> CSRSecCalculator:
        return CSRSecCalculator()

    def test_bucket1_single(self, calc: CSRSecCalculator) -> None:
        """Senior IG prime RMBS, RW 0.90 %."""
        result = calc.calculate([_sens(NC, "1", 1e6)], is_ctp=False)
        assert result.delta_charge == pytest.approx(0.009 * 1e6)

    def test_gamma_zero_between_buckets(self, calc: CSRSecCalculator) -> None:
        """Total = sqrt(K1^2 + K4^2) since gamma = 0."""
        result = calc.calculate([_sens(NC, "1", 1e6), _sens(NC, "4", 1e6)], is_ctp=False)
        expected = math.sqrt((0.009e6) ** 2 + (0.02e6) ** 2)
        for r in (result.delta_low, result.delta_medium, result.delta_high):
            assert r.capital_charge == pytest.approx(expected)

    def test_two_tranches_same_bucket(self, calc: CSRSecCalculator) -> None:
        sens = [_sens(NC, "4", 1e6, label="T1"), _sens(NC, "4", 1e6, label="T2")]
        result = calc.calculate(sens, is_ctp=False)
        ws = 0.02e6
        expected = math.sqrt(2 * ws ** 2 + 2 * 0.40 * ws * ws)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_same_tranche_different_tenor(self, calc: CSRSecCalculator) -> None:
        sens = [_sens(NC, "4", 1e6, tenor=GIRRTenor.Y1), _sens(NC, "4", 1e6, tenor=GIRRTenor.Y5)]
        result = calc.calculate(sens, is_ctp=False)
        ws = 0.02e6
        expected = math.sqrt(2 * ws ** 2 + 2 * 0.80 * ws * ws)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_bucket25_sum_abs(self, calc: CSRSecCalculator) -> None:
        sens = [_sens(NC, "25", 1e6, label="A"), _sens(NC, "25", -1e6, label="B")]
        result = calc.calculate(sens, is_ctp=False)
        assert result.delta_medium.capital_charge == pytest.approx(2 * 0.035e6)
        assert OTHER_SECTOR_BUCKET_NON_CTP == 25

    def test_curvature_two_tranches(self, calc: CSRSecCalculator) -> None:
        sens = [
            _sens(NC, "1", 1e5, tenor=None, risk_measure=RiskMeasure.CURVATURE, label="T1"),
            _sens(NC, "1", 1e5, tenor=None, risk_measure=RiskMeasure.CURVATURE, label="T2"),
        ]
        result = calc.calculate(sens, is_ctp=False)
        expected = math.sqrt(2 * 1e10 + 2 * (0.40 ** 2) * 1e10)
        assert result.curvature_medium.capital_charge == pytest.approx(expected)

    def test_vega_two_maturities(self, calc: CSRSecCalculator) -> None:
        sens = [
            _sens(NC, "1", 1e5, tenor=None, risk_measure=RiskMeasure.VEGA, option_maturity=1.0),
            _sens(NC, "1", 1e5, tenor=None, risk_measure=RiskMeasure.VEGA, option_maturity=3.0),
        ]
        result = calc.calculate(sens, is_ctp=False)
        rho = math.exp(-0.01 * 2.0 / 1.0)
        assert result.vega_medium.capital_charge == pytest.approx(math.sqrt(2e10 + 2 * rho * 1e10))

    def test_invalid_bucket(self, calc: CSRSecCalculator) -> None:
        with pytest.raises(CalculationError):
            calc.calculate([_sens(NC, "26", 1e6)], is_ctp=False)

    def test_invalid_tenor(self, calc: CSRSecCalculator) -> None:
        with pytest.raises(ValidationError):
            calc.calculate([_sens(NC, "1", 1e6, tenor=GIRRTenor.Y2)], is_ctp=False)


# =========================================================================
#  Calculator -- CTP
# =========================================================================

class TestCTPCalculator:

    @pytest.fixture
    def calc(self) -> CSRSecCalculator:
        return CSRSecCalculator()

    def test_bucket10_single(self, calc: CSRSecCalculator) -> None:
        """Spec & sub-spec financials, RW 16 %."""
        result = calc.calculate([_sens(CTP, "10", 1e6)], is_ctp=True)
        assert result.delta_charge == pytest.approx(0.16e6)

    def test_inter_bucket_1_2(self, calc: CSRSecCalculator) -> None:
        result = calc.calculate([_sens(CTP, "1", 1e6), _sens(CTP, "2", 1e6)], is_ctp=True)
        k = 0.04e6
        expected = math.sqrt(2 * k ** 2 + 2 * 0.75 * k * k)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_inter_bucket_1_10(self, calc: CSRSecCalculator) -> None:
        result = calc.calculate([_sens(CTP, "1", 1e6), _sens(CTP, "10", 1e6)], is_ctp=True)
        k1, k10 = 0.04e6, 0.16e6
        expected = math.sqrt(k1 ** 2 + k10 ** 2 + 2 * 0.05 * k1 * k10)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_two_names_same_bucket(self, calc: CSRSecCalculator) -> None:
        sens = [_sens(CTP, "3", 1e6, label="BANK_A"), _sens(CTP, "3", 1e6, label="BANK_B")]
        result = calc.calculate(sens, is_ctp=True)
        ws = 0.08e6
        expected = math.sqrt(2 * ws ** 2 + 2 * 0.35 * ws * ws)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_bucket16_sum_abs(self, calc: CSRSecCalculator) -> None:
        sens = [_sens(CTP, "16", 1e6, label="A"), _sens(CTP, "16", -1e6, label="B")]
        result = calc.calculate(sens, is_ctp=True)
        assert result.delta_medium.capital_charge == pytest.approx(2 * 0.13e6)
        assert OTHER_SECTOR_BUCKET_CTP == 16

    def test_bucket16_no_diversification(self, calc: CSRSecCalculator) -> None:
        result = calc.calculate([_sens(CTP, "16", 1e6), _sens(CTP, "1", 1e6)], is_ctp=True)
        expected = math.sqrt((0.13e6) ** 2 + (0.04e6) ** 2)
        assert result.delta_medium.capital_charge == pytest.approx(expected)

    def test_old_ctp_bucket_range_rejected(self, calc: CSRSecCalculator) -> None:
        with pytest.raises(CalculationError):
            calc.calculate([_sens(CTP, "17", 1e6)], is_ctp=True)

    def test_matrix_builder_ctp_basis(self) -> None:
        corr = build_csr_sec_correlation_matrix(
            bucket=3, tranches=["A", "A"], tenors=[5.0, 5.0], is_ctp=True, curves=["BOND", "CDS"]
        )
        assert corr[0, 1] == pytest.approx(0.99)
        assert np.allclose(corr, corr.T)
