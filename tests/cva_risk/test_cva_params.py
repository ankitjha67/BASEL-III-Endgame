"""Tests for CVA risk parameters — ERBA NPR §__.222 Tables 1–2, §__.225 Tables 1–9.

All monetary values in USD millions ($M).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.cva_risk.cva_params import (
    BA_CVA_ALPHA_COMMERCIAL_END_USER,
    BA_CVA_ALPHA_DEFAULT,
    BA_CVA_BETA,
    BA_CVA_DISCOUNT_RATE,
    BA_CVA_DISCOUNT_SCALAR,
    BA_CVA_HEDGE_CORRELATION,
    BA_CVA_INDEX_HEDGE_FACTOR,
    BA_CVA_RHO,
    BA_CVA_RISK_WEIGHT_TABLE,
    BA_CVA_RISK_WEIGHTS,
    CVA_SCOPE_OTC_NOTIONAL_THRESHOLD,
    RWA_MULTIPLIER,
    SA_CVA_CCS_GAMMA,
    SA_CVA_CCS_TENORS,
    SA_CVA_COMMODITY_DELTA_RW,
    SA_CVA_DELTA_SHIFT_ABSOLUTE,
    SA_CVA_DELTA_SHIFT_RELATIVE,
    SA_CVA_EQUITY_DELTA_RW,
    SA_CVA_FX_DELTA_RW,
    SA_CVA_FX_GAMMA,
    SA_CVA_HEDGING_DISALLOWANCE_R,
    SA_CVA_IR_DELTA_CORRELATION_SPECIFIED,
    SA_CVA_IR_DELTA_RHO_OTHER,
    SA_CVA_IR_DELTA_RW_OTHER,
    SA_CVA_IR_DELTA_RW_SPECIFIED,
    SA_CVA_IR_GAMMA,
    SA_CVA_IR_SPECIFIED_CURRENCIES,
    SA_CVA_IR_TENORS,
    SA_CVA_IR_VEGA_RHO,
    SA_CVA_IR_VEGA_RW,
    SA_CVA_MULTIPLIER_DEFAULT,
    SA_CVA_RCS_GAMMA,
    SA_CVA_RCS_RISK_WEIGHTS,
    SA_CVA_VEGA_RISK_CLASSES,
    SA_CVA_VEGA_SHIFT_RELATIVE,
    BACVAHedgeRelationship,
    CVACreditQuality,
    CVASector,
    SACVARiskFactorType,
    ccs_gamma,
    commodity_gamma,
    credit_quality_from_grade,
    delta_sensitivity,
    equity_gamma,
    equity_vega_risk_weight,
    get_ba_cva_alpha,
    get_ba_cva_risk_weight,
    get_ccs_bucket,
    get_ccs_risk_weight,
    get_saccr_alpha,
    ir_delta_correlation,
    netting_set_effective_maturity,
    normalize_sector,
    rcs_gamma,
    regulatory_mpor_floor_business_days,
    supervisory_discount_factor,
)

IG = CVACreditQuality.INVESTMENT_GRADE
SPEC = CVACreditQuality.SPECULATIVE_GRADE
SUB = CVACreditQuality.SUB_SPECULATIVE_GRADE


# =========================================================================
#  Enumerations and mappers
# =========================================================================

class TestEnums:
    def test_exactly_eight_sectors(self) -> None:
        """Table 1 to §__.222 lists exactly eight sectors."""
        assert len(CVASector) == 8

    def test_three_credit_quality_grades(self) -> None:
        """IG / speculative / sub-speculative per §__.2 (no external ratings)."""
        assert {q.name for q in CVACreditQuality} == {
            "INVESTMENT_GRADE", "SPECULATIVE_GRADE", "SUB_SPECULATIVE_GRADE",
        }

    def test_grade_mapper(self) -> None:
        assert credit_quality_from_grade("AAA") is IG
        assert credit_quality_from_grade("BBB-") is IG
        assert credit_quality_from_grade("BB+") is SPEC
        assert credit_quality_from_grade("B-") is SPEC
        assert credit_quality_from_grade("CCC") is SUB
        assert credit_quality_from_grade("D") is SUB
        assert credit_quality_from_grade(SPEC) is SPEC
        with pytest.raises(ValueError):
            credit_quality_from_grade("NR")

    def test_sector_aliases(self) -> None:
        assert normalize_sector("FINANCIAL") is CVASector.FINANCIALS
        assert normalize_sector("SOVEREIGN") is CVASector.SOVEREIGN_MDB_SUPRANATIONAL
        assert normalize_sector("CORPORATE") is CVASector.OTHER_SECTOR
        assert normalize_sector("TECHNOLOGY_TELECOM") is CVASector.TECHNOLOGY_TELECOM
        with pytest.raises(ValueError):
            normalize_sector("UTILITY_CO_OP")

    def test_vega_risk_classes_exclude_counterparty_cs(self) -> None:
        """§__.224(b)(2): five vega risk classes."""
        assert len(SA_CVA_VEGA_RISK_CLASSES) == 5
        assert SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD not in SA_CVA_VEGA_RISK_CLASSES


# =========================================================================
#  BA-CVA parameters (§__.222)
# =========================================================================

class TestBACVAParams:
    def test_core_constants(self) -> None:
        assert BA_CVA_DISCOUNT_SCALAR == 0.65
        assert BA_CVA_BETA == 0.25
        assert BA_CVA_RHO == 0.50
        assert BA_CVA_DISCOUNT_RATE == 0.05
        assert BA_CVA_ALPHA_DEFAULT == 1.4
        assert BA_CVA_ALPHA_COMMERCIAL_END_USER == 1.0
        assert BA_CVA_INDEX_HEDGE_FACTOR == 0.7
        assert RWA_MULTIPLIER == 12.5

    def test_alpha_helpers(self) -> None:
        assert get_ba_cva_alpha(is_commercial_end_user=True) == 1.0
        assert get_ba_cva_alpha(is_commercial_end_user=False) == 1.4
        assert get_saccr_alpha(is_financial=True) == 1.4
        assert get_saccr_alpha(is_financial=False) == 1.0

    @pytest.mark.parametrize(
        "sector, ig, spec, sub",
        [
            (CVASector.SOVEREIGN_MDB_SUPRANATIONAL, 0.005, 0.030, 0.070),
            (CVASector.PSE_GSE_PUBLIC_ADMIN, 0.010, 0.040, 0.040),
            (CVASector.FINANCIALS, 0.050, 0.120, 0.120),
            (CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS, 0.030, 0.070, 0.070),
            (CVASector.CONSUMER_TRANSPORT_ADMIN, 0.030, 0.085, 0.085),
            (CVASector.TECHNOLOGY_TELECOM, 0.020, 0.055, 0.055),
            (CVASector.HEALTH_UTILITIES_PROFESSIONAL, 0.015, 0.050, 0.050),
            (CVASector.OTHER_SECTOR, 0.050, 0.120, 0.120),
        ],
    )
    def test_table_1_risk_weights(self, sector, ig, spec, sub) -> None:
        """Table 1 to ERBA NPR §__.222."""
        assert get_ba_cva_risk_weight(sector, IG) == ig
        assert get_ba_cva_risk_weight(sector, SPEC) == spec
        assert get_ba_cva_risk_weight(sector, SUB) == sub

    def test_table_1_flat_view(self) -> None:
        assert len(BA_CVA_RISK_WEIGHTS) == 24
        assert BA_CVA_RISK_WEIGHTS[(CVASector.FINANCIALS, IG)] == 0.05
        assert set(BA_CVA_RISK_WEIGHT_TABLE) == set(CVASector)

    def test_only_sovereign_splits_spec_and_sub_spec(self) -> None:
        for sector, row in BA_CVA_RISK_WEIGHT_TABLE.items():
            if sector is CVASector.SOVEREIGN_MDB_SUPRANATIONAL:
                assert row[SPEC] != row[SUB]
            else:
                assert row[SPEC] == row[SUB]

    def test_risk_weight_lookup_by_grade_label(self) -> None:
        assert get_ba_cva_risk_weight("FINANCIAL", "A") == 0.05
        assert get_ba_cva_risk_weight("SOVEREIGN", "CCC") == 0.07

    def test_table_2_hedge_correlations(self) -> None:
        """Table 2 to §__.222: 100% / 80% / 50%."""
        assert BA_CVA_HEDGE_CORRELATION[BACVAHedgeRelationship.DIRECT] == 1.0
        assert BA_CVA_HEDGE_CORRELATION[BACVAHedgeRelationship.AFFILIATE] == 0.8
        assert BA_CVA_HEDGE_CORRELATION[BACVAHedgeRelationship.SAME_SECTOR_REGION] == 0.5

    def test_discount_factor_closed_form_and_no_clipping(self) -> None:
        """DF = (1 − e^(−0.05 M)) / (0.05 M) with no floor or cap on M."""
        assert supervisory_discount_factor(2.0) == pytest.approx((1 - math.exp(-0.1)) / 0.1)
        assert supervisory_discount_factor(0.5) == pytest.approx((1 - math.exp(-0.025)) / 0.025)
        assert supervisory_discount_factor(0.5) != supervisory_discount_factor(1.0)
        assert supervisory_discount_factor(10.0) < supervisory_discount_factor(5.0)
        assert supervisory_discount_factor(0.0) == 1.0
        assert supervisory_discount_factor(-1.0) == 1.0

    def test_netting_set_effective_maturity_notional_weighted(self) -> None:
        """M_NS = notional-weighted average remaining maturity, no floor/cap."""
        m = netting_set_effective_maturity([(100.0, 0.5), (300.0, 8.0)])
        assert m == pytest.approx((100 * 0.5 + 300 * 8.0) / 400)
        assert netting_set_effective_maturity([(50.0, 0.25)]) == 0.25
        assert netting_set_effective_maturity([(50.0, 12.0)]) == 12.0
        with pytest.raises(ValueError):
            netting_set_effective_maturity([])


# =========================================================================
#  SA-CVA parameters (§__.224 / §__.225)
# =========================================================================

class TestSACVAGeneralParams:
    def test_general_constants(self) -> None:
        assert SA_CVA_HEDGING_DISALLOWANCE_R == 0.01
        assert SA_CVA_MULTIPLIER_DEFAULT == 1.0
        assert SA_CVA_DELTA_SHIFT_ABSOLUTE == 0.0001
        assert SA_CVA_DELTA_SHIFT_RELATIVE == 0.01
        assert SA_CVA_VEGA_SHIFT_RELATIVE == 0.01
        assert CVA_SCOPE_OTC_NOTIONAL_THRESHOLD == 1_000_000.0  # $1 trillion in $M

    def test_sensitivity_convention(self) -> None:
        """§__.224(e): ΔCVA for a 1 bp shift divided by 0.0001."""
        assert delta_sensitivity(100.02, 100.0, SA_CVA_DELTA_SHIFT_ABSOLUTE) == pytest.approx(200.0)
        assert delta_sensitivity(101.0, 100.0, SA_CVA_DELTA_SHIFT_RELATIVE) == pytest.approx(100.0)

    def test_mpor_floor(self) -> None:
        """§__.224(d): MPoR ≥ 9 + N business days; 10 for daily margining."""
        assert regulatory_mpor_floor_business_days(1) == 10
        assert regulatory_mpor_floor_business_days(5) == 14


class TestSACVAInterestRate:
    def test_specified_currencies_and_tenors(self) -> None:
        assert {"USD", "AUD", "CAD", "EUR", "JPY", "SEK", "GBP"} == SA_CVA_IR_SPECIFIED_CURRENCIES
        assert SA_CVA_IR_TENORS == (1.0, 2.0, 5.0, 10.0, 30.0)

    def test_risk_weights(self) -> None:
        assert SA_CVA_IR_DELTA_RW_SPECIFIED[1.0] == 0.0111
        assert SA_CVA_IR_DELTA_RW_SPECIFIED[2.0] == 0.0093
        assert SA_CVA_IR_DELTA_RW_SPECIFIED[5.0] == 0.0074
        assert SA_CVA_IR_DELTA_RW_SPECIFIED[10.0] == 0.0074
        assert SA_CVA_IR_DELTA_RW_SPECIFIED[30.0] == 0.0074
        assert SA_CVA_IR_DELTA_RW_SPECIFIED["INFLATION"] == 0.0111
        assert SA_CVA_IR_DELTA_RW_OTHER == 0.0158
        assert SA_CVA_IR_VEGA_RW == 1.0

    def test_correlation_matrix(self) -> None:
        m = SA_CVA_IR_DELTA_CORRELATION_SPECIFIED
        assert m.shape == (6, 6)
        assert np.allclose(m, m.T)
        assert np.allclose(np.diag(m), 1.0)
        assert ir_delta_correlation(1.0, 2.0, True) == 0.91
        assert ir_delta_correlation(1.0, 30.0, True) == 0.31
        assert ir_delta_correlation(2.0, 5.0, True) == 0.87
        assert ir_delta_correlation(5.0, 10.0, True) == 0.91
        assert ir_delta_correlation(10.0, 30.0, True) == 0.83
        assert ir_delta_correlation(5.0, "INFLATION", True) == 0.40
        assert ir_delta_correlation("PARALLEL", "INFLATION", False) == SA_CVA_IR_DELTA_RHO_OTHER == 0.40
        assert SA_CVA_IR_VEGA_RHO == 0.40
        assert SA_CVA_IR_GAMMA == 0.50


class TestSACVAFX:
    def test_fx_params(self) -> None:
        assert SA_CVA_FX_DELTA_RW == 0.11
        assert SA_CVA_FX_GAMMA == 0.60


class TestSACVACounterpartyCreditSpread:
    def test_tenors(self) -> None:
        assert SA_CVA_CCS_TENORS == (0.5, 1.0, 3.0, 5.0, 10.0)

    def test_bucket_assignment(self) -> None:
        assert get_ccs_bucket(CVASector.SOVEREIGN_MDB_SUPRANATIONAL) == 1
        assert get_ccs_bucket(CVASector.PSE_GSE_PUBLIC_ADMIN) == 1
        assert get_ccs_bucket(CVASector.FINANCIALS) == 2
        assert get_ccs_bucket(CVASector.FINANCIALS, government_backed_financial=True) == 1
        assert get_ccs_bucket(CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS) == 3
        assert get_ccs_bucket(CVASector.CONSUMER_TRANSPORT_ADMIN) == 4
        assert get_ccs_bucket(CVASector.TECHNOLOGY_TELECOM) == 5
        assert get_ccs_bucket(CVASector.HEALTH_UTILITIES_PROFESSIONAL) == 6
        assert get_ccs_bucket(CVASector.OTHER_SECTOR) == 7
        assert get_ccs_bucket(CVASector.OTHER_SECTOR, is_index=True) == 8

    def test_table_3_risk_weights(self) -> None:
        sov = CVASector.SOVEREIGN_MDB_SUPRANATIONAL
        assert get_ccs_risk_weight(sov, IG) == 0.005
        assert get_ccs_risk_weight(sov, SPEC) == 0.030
        assert get_ccs_risk_weight(sov, SUB) == 0.070
        assert get_ccs_risk_weight(CVASector.PSE_GSE_PUBLIC_ADMIN, IG) == 0.010
        assert get_ccs_risk_weight(CVASector.PSE_GSE_PUBLIC_ADMIN, SUB) == 0.040
        assert get_ccs_risk_weight(CVASector.FINANCIALS, IG, government_backed_financial=True) == 0.05
        assert get_ccs_risk_weight(CVASector.FINANCIALS, SPEC, government_backed_financial=True) == 0.12
        assert get_ccs_risk_weight(CVASector.FINANCIALS, IG) == 0.05
        assert get_ccs_risk_weight(CVASector.FINANCIALS, SPEC) == 0.12
        assert get_ccs_risk_weight(CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS, IG) == 0.03
        assert get_ccs_risk_weight(CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS, SPEC) == 0.07
        assert get_ccs_risk_weight(CVASector.CONSUMER_TRANSPORT_ADMIN, IG) == 0.03
        assert get_ccs_risk_weight(CVASector.CONSUMER_TRANSPORT_ADMIN, SUB) == 0.085
        assert get_ccs_risk_weight(CVASector.TECHNOLOGY_TELECOM, IG) == 0.02
        assert get_ccs_risk_weight(CVASector.TECHNOLOGY_TELECOM, SPEC) == 0.055
        assert get_ccs_risk_weight(CVASector.HEALTH_UTILITIES_PROFESSIONAL, IG) == 0.015
        assert get_ccs_risk_weight(CVASector.HEALTH_UTILITIES_PROFESSIONAL, SPEC) == 0.05
        assert get_ccs_risk_weight(CVASector.OTHER_SECTOR, IG) == 0.05
        assert get_ccs_risk_weight(CVASector.OTHER_SECTOR, SPEC) == 0.12
        assert get_ccs_risk_weight(CVASector.OTHER_SECTOR, IG, is_index=True) == 0.015
        assert get_ccs_risk_weight(CVASector.OTHER_SECTOR, SPEC, is_index=True) == 0.05

    def test_table_4_gamma(self) -> None:
        expected = {
            (1, 2): 0.10, (1, 3): 0.20, (1, 4): 0.25, (1, 5): 0.20, (1, 6): 0.15, (1, 7): 0.0, (1, 8): 0.70,
            (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.05, (2, 7): 0.0, (2, 8): 0.70,
            (3, 4): 0.20, (3, 5): 0.25, (3, 6): 0.05, (3, 7): 0.0, (3, 8): 0.70,
            (4, 5): 0.25, (4, 6): 0.05, (4, 7): 0.0, (4, 8): 0.70,
            (5, 6): 0.05, (5, 7): 0.0, (5, 8): 0.70,
            (6, 7): 0.0, (6, 8): 0.70,
            (7, 8): 0.0,
        }
        for (b, c), g in expected.items():
            assert ccs_gamma(b, c) == pytest.approx(g)
            assert ccs_gamma(c, b) == pytest.approx(g)
        assert SA_CVA_CCS_GAMMA.shape == (8, 8)
        assert np.allclose(np.diag(SA_CVA_CCS_GAMMA), 1.0)


class TestSACVAReferenceCreditSpread:
    def test_table_5_risk_weights(self) -> None:
        expected = {1: 0.005, 2: 0.010, 3: 0.050, 4: 0.030, 5: 0.030, 6: 0.020, 7: 0.015,
                    9: 0.040, 10: 0.120, 11: 0.070, 12: 0.085, 13: 0.055, 14: 0.050,
                    15: 0.120, 16: 0.015, 17: 0.050}
        for b, rw in expected.items():
            assert SA_CVA_RCS_RISK_WEIGHTS[b][IG] == rw
            assert SA_CVA_RCS_RISK_WEIGHTS[b][SPEC] == rw
        assert SA_CVA_RCS_RISK_WEIGHTS[8][SPEC] == 0.030
        assert SA_CVA_RCS_RISK_WEIGHTS[8][SUB] == 0.070
        assert len(SA_CVA_RCS_RISK_WEIGHTS) == 17

    def test_table_6_same_quality_gamma(self) -> None:
        assert rcs_gamma(1, 2) == 0.75
        assert rcs_gamma(1, 3) == 0.10
        assert rcs_gamma(1, 4) == 0.20
        assert rcs_gamma(1, 5) == 0.25
        assert rcs_gamma(1, 6) == 0.20
        assert rcs_gamma(1, 7) == 0.15
        assert rcs_gamma(2, 3) == 0.05
        assert rcs_gamma(3, 7) == 0.05
        assert rcs_gamma(4, 6) == 0.25
        assert rcs_gamma(5, 6) == 0.25
        assert rcs_gamma(6, 7) == 0.05
        # Speculative buckets share the same sector-group structure
        assert rcs_gamma(8, 9) == 0.75
        assert rcs_gamma(10, 14) == 0.05
        # Bucket 15 is zero with all; indices 45% to 1–14 and 75% with each other
        for b in range(1, 18):
            if b != 15:
                assert rcs_gamma(15, b) == 0.0
        assert rcs_gamma(16, 17) == 0.75
        assert rcs_gamma(16, 3) == 0.45
        assert rcs_gamma(17, 10) == 0.45

    def test_table_7_different_quality_gamma(self) -> None:
        assert rcs_gamma(1, 8) == 0.50       # same sector, IG vs spec
        assert rcs_gamma(3, 10) == 0.50
        assert rcs_gamma(1, 9) == 0.375      # group 1 vs 2 halved
        assert rcs_gamma(1, 10) == 0.05
        assert rcs_gamma(1, 11) == 0.10
        assert rcs_gamma(1, 12) == 0.125
        assert rcs_gamma(1, 13) == 0.10
        assert rcs_gamma(1, 14) == 0.075
        assert rcs_gamma(9, 3) == 0.025
        assert rcs_gamma(13, 7) == 0.025

    def test_gamma_matrix_symmetric(self) -> None:
        assert SA_CVA_RCS_GAMMA.shape == (17, 17)
        assert np.allclose(SA_CVA_RCS_GAMMA, SA_CVA_RCS_GAMMA.T)
        assert np.allclose(np.diag(SA_CVA_RCS_GAMMA), 1.0)


class TestSACVAEquityCommodity:
    def test_table_8_equity(self) -> None:
        assert [SA_CVA_EQUITY_DELTA_RW[b] for b in range(1, 14)] == [
            0.55, 0.60, 0.45, 0.55, 0.30, 0.35, 0.40, 0.50, 0.70, 0.50, 0.70, 0.15, 0.25,
        ]
        assert equity_gamma(1, 2) == 0.15
        assert equity_gamma(3, 10) == 0.15
        assert equity_gamma(11, 4) == 0.0
        assert equity_gamma(11, 12) == 0.0
        assert equity_gamma(12, 13) == 0.75
        assert equity_gamma(12, 1) == 0.45
        assert equity_gamma(13, 9) == 0.45
        for b in (1, 2, 3, 4, 5, 6, 7, 8, 12, 13):
            assert equity_vega_risk_weight(b) == 0.78
        for b in (9, 10, 11):
            assert equity_vega_risk_weight(b) == 1.00

    def test_table_9_commodity(self) -> None:
        assert [SA_CVA_COMMODITY_DELTA_RW[b] for b in range(1, 13)] == [
            0.30, 0.35, 0.60, 0.80, 0.40, 0.45, 0.20, 0.35, 0.25, 0.35, 0.50, 0.30,
        ]
        assert commodity_gamma(1, 2) == 0.20
        assert commodity_gamma(1, 12) == 0.20
        assert commodity_gamma(11, 3) == 0.0
        assert commodity_gamma(11, 12) == 0.0
