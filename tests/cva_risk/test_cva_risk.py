"""Tests for CVA Risk module — SA-CVA, BA-CVA, and main calculator.

Validates regulatory parameter correctness, calculation accuracy,
and proper integration of the CVA risk framework per BCBS d424,
BCBS d457 MAR50/MAR51, and ERBA NPR pp. 280-295.

All monetary values in USD millions ($M).
"""

from __future__ import annotations

import math

import pytest


# =========================================================================
#  Test CVA Parameters (cva_params.py)
# =========================================================================

class TestCVAParams:
    """Tests for CVA risk parameters per ERBA NPR pp. 280-295."""

    def test_ba_cva_risk_weights_exist(self) -> None:
        """BA-CVA risk weights cover all required ratings per ERBA NPR p. 282."""
        from src.cva_risk.cva_params import BA_CVA_RISK_WEIGHTS

        required = {"AAA", "AA", "A", "BBB", "BB", "B", "CCC", "UNRATED"}
        assert required.issubset(set(BA_CVA_RISK_WEIGHTS.keys()))

    def test_ba_cva_risk_weight_monotonicity(self) -> None:
        """Risk weights increase with credit deterioration per ERBA NPR p. 282."""
        from src.cva_risk.cva_params import BA_CVA_RISK_WEIGHTS

        assert BA_CVA_RISK_WEIGHTS["AAA"] <= BA_CVA_RISK_WEIGHTS["AA"]
        assert BA_CVA_RISK_WEIGHTS["AA"] <= BA_CVA_RISK_WEIGHTS["A"]
        assert BA_CVA_RISK_WEIGHTS["A"] <= BA_CVA_RISK_WEIGHTS["BBB"]
        assert BA_CVA_RISK_WEIGHTS["BBB"] <= BA_CVA_RISK_WEIGHTS["BB"]
        assert BA_CVA_RISK_WEIGHTS["BB"] <= BA_CVA_RISK_WEIGHTS["B"]
        assert BA_CVA_RISK_WEIGHTS["B"] <= BA_CVA_RISK_WEIGHTS["CCC"]

    def test_ba_cva_specific_weights(self) -> None:
        """Verify specific risk weights per ERBA NPR p. 282, Table 1."""
        from src.cva_risk.cva_params import BA_CVA_RISK_WEIGHTS

        assert BA_CVA_RISK_WEIGHTS["AAA"] == 0.007
        assert BA_CVA_RISK_WEIGHTS["BBB"] == 0.010
        assert BA_CVA_RISK_WEIGHTS["CCC"] == 0.100

    def test_ba_cva_rho(self) -> None:
        """Supervisory correlation rho = 0.50 per MAR50.5 / ERBA NPR p. 281."""
        from src.cva_risk.cva_params import BA_CVA_RHO

        assert BA_CVA_RHO == 0.50

    def test_ba_cva_beta(self) -> None:
        """Hedging parameter beta = 0.25 per MAR50.6 / ERBA NPR p. 281."""
        from src.cva_risk.cva_params import BA_CVA_BETA

        assert BA_CVA_BETA == 0.25

    def test_sa_cva_buckets_complete(self) -> None:
        """SA-CVA must have 10 buckets per ERBA NPR pp. 285-287."""
        from src.cva_risk.cva_params import SA_CVA_BUCKETS

        assert len(SA_CVA_BUCKETS) == 10
        for i in range(1, 11):
            assert i in SA_CVA_BUCKETS

    def test_sa_cva_bucket_risk_weights(self) -> None:
        """Verify SA-CVA bucket risk weights per ERBA NPR pp. 285-287."""
        from src.cva_risk.cva_params import SA_CVA_BUCKETS

        assert SA_CVA_BUCKETS[1]["rw"] == 0.005  # Sovereign IG
        assert SA_CVA_BUCKETS[2]["rw"] == 0.020  # Sovereign HY
        assert SA_CVA_BUCKETS[3]["rw"] == 0.008  # Financial IG
        assert SA_CVA_BUCKETS[4]["rw"] == 0.025  # Financial HY
        assert SA_CVA_BUCKETS[5]["rw"] == 0.010  # Corporate IG
        assert SA_CVA_BUCKETS[6]["rw"] == 0.030  # Corporate HY

    def test_sa_cva_ig_rw_range(self) -> None:
        """IG risk weights in range 0.5%-3.0% per ERBA NPR p. 285."""
        from src.cva_risk.cva_params import SA_CVA_BUCKETS

        ig_buckets = [b for b in SA_CVA_BUCKETS.values() if b["quality"] == "IG"]
        for b in ig_buckets:
            assert 0.005 <= b["rw"] <= 0.030

    def test_sa_cva_hy_rw_range(self) -> None:
        """HY risk weights in range 1.5%-6.0% per ERBA NPR p. 285."""
        from src.cva_risk.cva_params import SA_CVA_BUCKETS

        hy_buckets = [b for b in SA_CVA_BUCKETS.values() if b["quality"] == "HY"]
        for b in hy_buckets:
            assert 0.015 <= b["rw"] <= 0.060

    def test_sa_cva_correlations(self) -> None:
        """Verify SA-CVA correlation parameters per ERBA NPR pp. 287-288."""
        from src.cva_risk.cva_params import (
            SA_CVA_INTRA_BUCKET_CORRELATION,
            SA_CVA_INTER_BUCKET_CORRELATION,
            SA_CVA_SAME_COUNTERPARTY_CORRELATION,
            SA_CVA_RISK_TYPE_CORRELATION,
        )

        assert SA_CVA_INTRA_BUCKET_CORRELATION == 0.35
        assert SA_CVA_INTER_BUCKET_CORRELATION == 0.50
        assert SA_CVA_SAME_COUNTERPARTY_CORRELATION == 0.50
        assert SA_CVA_RISK_TYPE_CORRELATION == 0.30

    def test_saccr_alpha_multipliers(self) -> None:
        """SA-CCR alpha per CRE52.30: 1.4 financial, 1.0 commercial."""
        from src.cva_risk.cva_params import (
            SACCR_ALPHA_FINANCIAL,
            SACCR_ALPHA_COMMERCIAL,
            get_saccr_alpha,
        )

        assert SACCR_ALPHA_FINANCIAL == 1.4
        assert SACCR_ALPHA_COMMERCIAL == 1.0
        assert get_saccr_alpha(is_financial=True) == 1.4
        assert get_saccr_alpha(is_financial=False) == 1.0

    def test_maturity_bounds(self) -> None:
        """Effective maturity floor = 1Y, cap = 5Y per ERBA NPR p. 283."""
        from src.cva_risk.cva_params import MIN_EFFECTIVE_MATURITY, MAX_EFFECTIVE_MATURITY

        assert MIN_EFFECTIVE_MATURITY == 1.0
        assert MAX_EFFECTIVE_MATURITY == 5.0

    def test_supervisory_discount_factor(self) -> None:
        """Supervisory discount factor d_c per MAR50.4 / ERBA NPR p. 283."""
        from src.cva_risk.cva_params import supervisory_discount_factor

        # At 1 year: d = (1 - exp(-0.05)) / 0.05 ≈ 0.9754
        d_1y = supervisory_discount_factor(1.0)
        assert 0.97 < d_1y < 0.98

        # At 5 years: d = (1 - exp(-0.25)) / 0.25 ≈ 0.8848
        d_5y = supervisory_discount_factor(5.0)
        assert 0.88 < d_5y < 0.89

        # Sub-floor maturity clipped to 1Y
        assert supervisory_discount_factor(0.5) == d_1y

    def test_tenor_correlation(self) -> None:
        """Tenor correlation per MAR51.4 / ERBA NPR p. 286."""
        from src.cva_risk.cva_params import tenor_correlation

        # Same tenor: rho = 1.0
        assert tenor_correlation(5.0, 5.0) == 1.0

        # Adjacent tenors: 0 < rho < 1
        rho = tenor_correlation(1.0, 3.0)
        assert 0.0 < rho < 1.0

        # Distant tenors have lower correlation
        rho_close = tenor_correlation(1.0, 2.0)
        rho_far = tenor_correlation(1.0, 10.0)
        assert rho_close > rho_far

    def test_investment_grade_classification(self) -> None:
        """IG classification per ERBA NPR p. 282."""
        from src.cva_risk.cva_params import is_investment_grade

        assert is_investment_grade("AAA") is True
        assert is_investment_grade("AA") is True
        assert is_investment_grade("BBB") is True
        assert is_investment_grade("BB") is False
        assert is_investment_grade("CCC") is False

    def test_inter_bucket_correlation_matrix(self) -> None:
        """Inter-bucket correlation matrix per ERBA NPR p. 288."""
        from src.cva_risk.cva_params import SA_CVA_INTER_BUCKET_CORRELATION_MATRIX

        matrix = SA_CVA_INTER_BUCKET_CORRELATION_MATRIX
        assert matrix.shape == (10, 10)

        # Diagonal = 1.0
        for i in range(10):
            assert matrix[i, i] == 1.0

        # Same-sector pairs have higher correlation (0.80)
        assert matrix[0, 1] == 0.80  # Sovereign IG/HY
        assert matrix[2, 3] == 0.80  # Financial IG/HY

        # Different-sector pairs have 0.50
        assert matrix[0, 2] == 0.50  # Sovereign vs Financial

    def test_rwa_multiplier(self) -> None:
        """RWA multiplier = 12.5 per ERBA NPR p. 280."""
        from src.cva_risk.cva_params import RWA_MULTIPLIER

        assert RWA_MULTIPLIER == 12.5

    def test_hedge_maturity_adjustment(self) -> None:
        """Hedge maturity adjustment per ERBA NPR p. 289."""
        from src.cva_risk.cva_params import hedge_maturity_adjustment

        # Perfect match: adjustment = 1.0
        assert hedge_maturity_adjustment(5.0, 5.0) == 1.0

        # Short hedge: proportional reduction
        adj = hedge_maturity_adjustment(2.5, 5.0)
        assert adj == pytest.approx(0.5)

        # Longer hedge: capped at 1.0
        assert hedge_maturity_adjustment(10.0, 5.0) == 1.0

    def test_bucket_assignment(self) -> None:
        """Bucket assignment by sector/quality per ERBA NPR pp. 285-287."""
        from src.cva_risk.cva_params import get_sa_cva_bucket

        assert get_sa_cva_bucket("SOVEREIGN", "IG") == 1
        assert get_sa_cva_bucket("SOVEREIGN", "HY") == 2
        assert get_sa_cva_bucket("FINANCIAL", "IG") == 3
        assert get_sa_cva_bucket("CORPORATE", "IG") == 5
        assert get_sa_cva_bucket("CORPORATE", "HY") == 6


# =========================================================================
#  Test BA-CVA Calculator (ba_cva.py)
# =========================================================================

class TestBACVACalculator:
    """Tests for BA-CVA calculation per ERBA NPR pp. 280-284."""

    @pytest.fixture
    def calculator(self) -> "BACVACalculator":
        from src.cva_risk.ba_cva import BACVACalculator
        return BACVACalculator()

    def _make_cp(self, **kwargs) -> "BACVACounterparty":
        from src.cva_risk.ba_cva import BACVACounterparty
        defaults = {
            "counterparty_id": "CP1",
            "rating": "BBB",
            "sector": "CORPORATE",
            "ead": 100.0,
            "effective_maturity": 3.0,
        }
        defaults.update(kwargs)
        return BACVACounterparty(**defaults)

    def test_empty_counterparties(self, calculator) -> None:
        """Empty input produces zero charge."""
        result = calculator.calculate_full([])
        assert result.k_ba_cva == 0.0
        assert result.rwa == 0.0

    def test_single_counterparty_full(self, calculator) -> None:
        """Single counterparty BA-CVA Full per ERBA NPR p. 281.

        SCR = w * M * EAD = 0.01 * 3.0 * 100 = 3.0
        K_full = sqrt(0.50^2 * 3.0^2 + (1-0.50^2) * 3.0^2)
               = sqrt(0.25 * 9 + 0.75 * 9) = sqrt(9) = 3.0
        """
        cp = self._make_cp()
        result = calculator.calculate_full([cp])

        assert result.k_full > 0
        expected_scr = 0.01 * 3.0 * 100.0  # 3.0
        assert result.total_scr == pytest.approx(expected_scr, rel=1e-6)

        # For single counterparty: K_full = SCR (no diversification)
        assert result.k_full == pytest.approx(expected_scr, rel=1e-6)

    def test_higher_rating_lower_charge(self, calculator) -> None:
        """Better rating produces lower charge per ERBA NPR p. 282."""
        aaa = self._make_cp(counterparty_id="AAA", rating="AAA")
        ccc = self._make_cp(counterparty_id="CCC", rating="CCC")

        r_aaa = calculator.calculate_full([aaa])
        r_ccc = calculator.calculate_full([ccc])

        assert r_aaa.k_ba_cva < r_ccc.k_ba_cva

    def test_diversification_benefit(self, calculator) -> None:
        """Multiple counterparties provide diversification per ERBA NPR p. 281.

        Sum of individual charges > combined charge due to rho < 1.
        """
        cp1 = self._make_cp(counterparty_id="A", rating="A", ead=50.0)
        cp2 = self._make_cp(counterparty_id="B", rating="BBB", ead=50.0)

        individual_1 = calculator.calculate_full([cp1])
        individual_2 = calculator.calculate_full([cp2])
        combined = calculator.calculate_full([cp1, cp2])

        sum_individual = individual_1.k_ba_cva + individual_2.k_ba_cva
        assert combined.k_ba_cva < sum_individual

    def test_maturity_effect(self, calculator) -> None:
        """Longer maturity increases charge per ERBA NPR p. 283."""
        short = self._make_cp(counterparty_id="S", effective_maturity=1.0)
        long_ = self._make_cp(counterparty_id="L", effective_maturity=5.0)

        r_short = calculator.calculate_full([short])
        r_long = calculator.calculate_full([long_])

        assert r_short.k_ba_cva < r_long.k_ba_cva

    def test_ead_proportionality(self, calculator) -> None:
        """Charge scales proportionally with EAD per ERBA NPR p. 281."""
        cp_100 = self._make_cp(counterparty_id="100", ead=100.0)
        cp_200 = self._make_cp(counterparty_id="200", ead=200.0)

        r_100 = calculator.calculate_full([cp_100])
        r_200 = calculator.calculate_full([cp_200])

        # For single counterparty, charge is linear in EAD
        assert r_200.k_ba_cva == pytest.approx(2.0 * r_100.k_ba_cva, rel=1e-6)

    def test_rwa_conversion(self, calculator) -> None:
        """RWA = K * 12.5 per ERBA NPR p. 280."""
        cp = self._make_cp()
        result = calculator.calculate_full([cp])
        assert result.rwa == pytest.approx(result.k_ba_cva * 12.5, rel=1e-6)

    def test_systematic_and_idiosyncratic_components(self, calculator) -> None:
        """Components sum correctly per ERBA NPR p. 281."""
        cps = [
            self._make_cp(counterparty_id="A", rating="A", ead=100.0),
            self._make_cp(counterparty_id="B", rating="BBB", ead=80.0),
        ]
        result = calculator.calculate_full(cps)

        # K_full^2 = systematic + idiosyncratic
        k_sq = result.k_full ** 2
        assert k_sq == pytest.approx(
            result.systematic_component + result.idiosyncratic_component,
            rel=1e-6,
        )

    def test_ba_cva_reduced_with_single_name_hedge(self, calculator) -> None:
        """BA-CVA Reduced with single-name CDS per ERBA NPR p. 282."""
        from src.cva_risk.ba_cva import BACVAHedge

        cp = self._make_cp(counterparty_id="CP1", ead=100.0)
        hedge = BACVAHedge(
            hedge_id="H1",
            hedge_type="SINGLE_NAME_CDS",
            counterparty_id="CP1",
            notional=50.0,
            maturity=3.0,
            rating="BBB",
        )

        full_result = calculator.calculate_full([cp])
        hedged_result = calculator.calculate_reduced([cp], [hedge])

        # Hedged charge should be less than full charge
        assert hedged_result.k_ba_cva < full_result.k_ba_cva
        assert hedged_result.hedge_count == 1

    def test_ba_cva_reduced_with_index_hedge(self, calculator) -> None:
        """BA-CVA Reduced with index CDS per ERBA NPR p. 283."""
        from src.cva_risk.ba_cva import BACVAHedge

        cps = [
            self._make_cp(counterparty_id="A", rating="A", ead=100.0),
            self._make_cp(counterparty_id="B", rating="BBB", ead=80.0),
        ]
        hedge = BACVAHedge(
            hedge_id="IDX1",
            hedge_type="INDEX_CDS",
            notional=100.0,
            maturity=5.0,
            rating="A",
        )

        full_result = calculator.calculate_full(cps)
        hedged_result = calculator.calculate_reduced(cps, [hedge])

        assert hedged_result.k_ba_cva < full_result.k_ba_cva

    def test_ba_cva_auto_select(self, calculator) -> None:
        """Auto-select full vs reduced based on hedges."""
        from src.cva_risk.ba_cva import BACVAHedge

        cp = self._make_cp()

        # No hedges -> full
        result_full = calculator.calculate([cp])
        assert result_full.approach == "BA-CVA-FULL"

        # With hedges -> reduced
        hedge = BACVAHedge(
            hedge_id="H1",
            hedge_type="SINGLE_NAME_CDS",
            counterparty_id="CP1",
            notional=50.0,
            maturity=3.0,
        )
        result_reduced = calculator.calculate([cp], hedges=[hedge])
        assert result_reduced.approach == "BA-CVA-REDUCED"

    def test_maturity_clipping(self) -> None:
        """Effective maturity clipped to [1, 5] per ERBA NPR p. 283."""
        cp_short = self._make_cp(effective_maturity=0.3)
        assert cp_short.effective_maturity == 1.0

        cp_long = self._make_cp(effective_maturity=10.0)
        assert cp_long.effective_maturity == 5.0

    def test_negative_ead_rejected(self) -> None:
        """Negative EAD is rejected per ERBA NPR p. 281."""
        with pytest.raises(ValueError, match="non-negative"):
            self._make_cp(ead=-100.0)


# =========================================================================
#  Test SA-CVA Calculator (sa_cva.py)
# =========================================================================

class TestSACVACalculator:
    """Tests for SA-CVA calculation per ERBA NPR pp. 284-295."""

    @pytest.fixture
    def calculator(self) -> "SACVACalculator":
        from src.cva_risk.sa_cva import SACVACalculator
        return SACVACalculator()

    def _make_cp(self, **kwargs) -> "SACVACounterparty":
        from src.cva_risk.sa_cva import SACVACounterparty
        defaults = {
            "counterparty_id": "CP1",
            "sector": "CORPORATE",
            "rating": "BBB",
            "ead": 100.0,
            "effective_maturity": 3.0,
        }
        defaults.update(kwargs)
        return SACVACounterparty(**defaults)

    def test_empty_counterparties(self, calculator) -> None:
        """Empty input produces zero charge."""
        result = calculator.calculate([])
        assert result.k_cva == 0.0
        assert result.rwa == 0.0

    def test_single_counterparty_sa_cva(self, calculator) -> None:
        """Single counterparty SA-CVA produces positive charge."""
        cp = self._make_cp()
        result = calculator.calculate([cp])

        assert result.k_cva > 0
        assert result.rwa > 0
        assert result.approach == "SA-CVA"

    def test_rwa_is_12_5x_charge(self, calculator) -> None:
        """RWA = K_CVA * 12.5 per ERBA NPR p. 280."""
        cp = self._make_cp()
        result = calculator.calculate([cp])
        assert result.rwa == pytest.approx(result.k_cva * 12.5, rel=1e-6)

    def test_higher_ead_higher_charge(self, calculator) -> None:
        """Higher EAD produces higher charge per ERBA NPR p. 284."""
        small = self._make_cp(counterparty_id="S", ead=50.0)
        large = self._make_cp(counterparty_id="L", ead=200.0)

        r_small = calculator.calculate([small])
        r_large = calculator.calculate([large])

        assert r_small.k_cva < r_large.k_cva

    def test_sector_affects_charge(self, calculator) -> None:
        """Different sectors get different risk weights per ERBA NPR pp. 285-287."""
        sovereign = self._make_cp(counterparty_id="S", sector="SOVEREIGN", rating="AAA")
        corporate = self._make_cp(counterparty_id="C", sector="CORPORATE", rating="BBB")

        r_sov = calculator.calculate([sovereign])
        r_corp = calculator.calculate([corporate])

        # Sovereign IG (0.5% RW) < Corporate IG (1.0% RW) -> lower charge
        assert r_sov.k_cva < r_corp.k_cva

    def test_diversification_across_sectors(self, calculator) -> None:
        """Cross-sector diversification per ERBA NPR p. 288."""
        fin = self._make_cp(counterparty_id="F", sector="FINANCIAL", rating="A", ead=50.0)
        corp = self._make_cp(counterparty_id="C", sector="CORPORATE", rating="BBB", ead=50.0)

        r_fin = calculator.calculate([fin])
        r_corp = calculator.calculate([corp])
        r_combined = calculator.calculate([fin, corp])

        # Combined < sum of individuals (diversification)
        assert r_combined.k_cva < r_fin.k_cva + r_corp.k_cva

    def test_sa_cva_with_hedges(self, calculator) -> None:
        """SA-CVA with eligible hedges reduces charge per ERBA NPR p. 289."""
        from src.cva_risk.sa_cva import SACVAHedge

        cp = self._make_cp(ead=200.0)
        hedge = SACVAHedge(
            hedge_id="H1",
            counterparty_id="CP1",
            hedge_type="SINGLE_NAME_CDS",
            notional=100.0,
            maturity=3.0,
            rating="BBB",
            sector="CORPORATE",
        )

        r_unhedged = calculator.calculate([cp])
        r_hedged = calculator.calculate([cp], hedges=[hedge])

        assert r_hedged.k_cva < r_unhedged.k_cva

    def test_k_cva_formula(self, calculator) -> None:
        """K_CVA = sqrt(K_spread^2 + K_IR^2 + 2*rho*K_spread*K_IR).

        Per ERBA NPR p. 288.
        """
        cp = self._make_cp()
        result = calculator.calculate([cp], include_ir=True)

        rho = 0.30
        expected = math.sqrt(
            result.k_spread ** 2
            + result.k_ir ** 2
            + 2 * rho * result.k_spread * result.k_ir
        )
        assert result.k_cva == pytest.approx(expected, rel=1e-6)

    def test_vega_component(self, calculator) -> None:
        """Vega component is included per ERBA NPR p. 289."""
        cp = self._make_cp()

        r_with_vega = calculator.calculate([cp], include_vega=True)
        r_no_vega = calculator.calculate([cp], include_vega=False)

        assert r_with_vega.k_spread >= r_no_vega.k_spread

    def test_bucket_results_populated(self, calculator) -> None:
        """Bucket results are returned for reporting."""
        cps = [
            self._make_cp(counterparty_id="F", sector="FINANCIAL", rating="A"),
            self._make_cp(counterparty_id="C", sector="CORPORATE", rating="BBB"),
        ]
        result = calculator.calculate(cps)
        assert len(result.bucket_results) > 0

    def test_counterparty_breakdown(self, calculator) -> None:
        """Counterparty breakdown shows contribution per counterparty."""
        cps = [
            self._make_cp(counterparty_id="A", ead=100.0),
            self._make_cp(counterparty_id="B", ead=200.0),
        ]
        result = calculator.calculate(cps)
        assert "A" in result.counterparty_breakdown
        assert "B" in result.counterparty_breakdown


# =========================================================================
#  Test Main CVA Calculator (cva_calculator.py)
# =========================================================================

class TestCVACalculator:
    """Tests for the main CVA calculator per ERBA NPR pp. 280-295."""

    @pytest.fixture
    def calculator(self) -> "CVACalculator":
        from src.cva_risk.cva_calculator import CVACalculator
        return CVACalculator()

    def _make_cp(self, **kwargs) -> "CVACounterparty":
        from src.cva_risk.cva_calculator import CVACounterparty
        defaults = {
            "counterparty_id": "CP1",
            "rating": "BBB",
            "sector": "CORPORATE",
            "ead": 100.0,
            "effective_maturity": 3.0,
        }
        defaults.update(kwargs)
        return CVACounterparty(**defaults)

    def test_empty_counterparties(self, calculator) -> None:
        """Empty input returns zero."""
        result = calculator.calculate([])
        assert result.k_cva == 0.0
        assert result.rwa == 0.0

    def test_default_approach_is_ba_cva_full(self, calculator) -> None:
        """Default approach is BA-CVA Full per ERBA NPR p. 280."""
        from src.cva_risk.cva_params import CVAApproach

        cp = self._make_cp()
        result = calculator.calculate([cp])
        assert result.approach == CVAApproach.BA_CVA_FULL

    def test_force_sa_cva(self, calculator) -> None:
        """Can force SA-CVA approach."""
        from src.cva_risk.cva_params import CVAApproach

        cp = self._make_cp()
        result = calculator.calculate([cp], approach=CVAApproach.SA_CVA)
        assert result.approach == CVAApproach.SA_CVA
        assert result.k_cva > 0

    def test_force_ba_cva_reduced(self, calculator) -> None:
        """Can force BA-CVA Reduced with hedges."""
        from src.cva_risk.cva_params import CVAApproach
        from src.cva_risk.cva_calculator import CVAHedge

        cp = self._make_cp()
        hedge = CVAHedge(
            hedge_id="H1",
            hedge_type="SINGLE_NAME_CDS",
            counterparty_id="CP1",
            notional=50.0,
            maturity=3.0,
        )
        result = calculator.calculate(
            [cp], hedges=[hedge],
            approach=CVAApproach.BA_CVA_REDUCED,
        )
        assert result.approach == CVAApproach.BA_CVA_REDUCED

    def test_auto_select_with_hedges(self, calculator) -> None:
        """Auto-selects BA-CVA Reduced when hedges present."""
        from src.cva_risk.cva_params import CVAApproach
        from src.cva_risk.cva_calculator import CVAHedge

        cp = self._make_cp()
        hedge = CVAHedge(
            hedge_id="H1",
            hedge_type="SINGLE_NAME_CDS",
            counterparty_id="CP1",
            notional=50.0,
            maturity=3.0,
        )
        result = calculator.calculate([cp], hedges=[hedge])
        assert result.approach == CVAApproach.BA_CVA_REDUCED

    def test_rwa_positive(self, calculator) -> None:
        """RWA is positive for non-zero exposures."""
        cp = self._make_cp()
        result = calculator.calculate([cp])
        assert result.rwa > 0

    def test_reporting_breakdown_by_counterparty(self, calculator) -> None:
        """Counterparty-level RWA breakdown for reporting."""
        cps = [
            self._make_cp(counterparty_id="A", ead=100.0),
            self._make_cp(counterparty_id="B", ead=200.0),
        ]
        result = calculator.calculate(cps)
        assert "A" in result.counterparty_rwa
        assert "B" in result.counterparty_rwa

    def test_reporting_breakdown_by_sector(self, calculator) -> None:
        """Sector-level RWA breakdown for FR Y-9C reporting."""
        cps = [
            self._make_cp(counterparty_id="F", sector="FINANCIAL", ead=100.0),
            self._make_cp(counterparty_id="C", sector="CORPORATE", ead=200.0),
        ]
        result = calculator.calculate(cps)
        assert "FINANCIAL" in result.sector_rwa
        assert "CORPORATE" in result.sector_rwa

    def test_total_ead_tracked(self, calculator) -> None:
        """Total EAD is tracked for reporting."""
        cps = [
            self._make_cp(counterparty_id="A", ead=100.0),
            self._make_cp(counterparty_id="B", ead=200.0),
        ]
        result = calculator.calculate(cps)
        assert result.total_ead == pytest.approx(300.0)

    def test_counterparty_count(self, calculator) -> None:
        """Counterparty count in result."""
        cps = [
            self._make_cp(counterparty_id="A"),
            self._make_cp(counterparty_id="B"),
        ]
        result = calculator.calculate(cps)
        assert result.counterparty_count == 2

    def test_compute_rwa_convenience(self, calculator) -> None:
        """Convenience method returns RWA directly."""
        cp = self._make_cp()
        rwa = calculator.compute_rwa([cp])
        assert rwa > 0


# =========================================================================
#  Test CVA Eligibility
# =========================================================================

class TestCVAEligibility:
    """Tests for CVA approach eligibility per ERBA NPR p. 280."""

    def test_default_is_ba_cva_full(self) -> None:
        """Default eligibility is BA-CVA Full."""
        from src.cva_risk.cva_calculator import determine_eligibility
        from src.cva_risk.cva_params import CVAApproach

        elig = determine_eligibility()
        assert elig.recommended_approach == CVAApproach.BA_CVA_FULL

    def test_sa_cva_requires_all_criteria(self) -> None:
        """SA-CVA requires CVA desk + sensitivities + approval."""
        from src.cva_risk.cva_calculator import determine_eligibility
        from src.cva_risk.cva_params import CVAApproach

        # Missing approval
        elig = determine_eligibility(
            has_cva_desk=True, has_cva_sensitivities=True,
        )
        assert elig.recommended_approach != CVAApproach.SA_CVA

        # All criteria met
        elig = determine_eligibility(
            has_cva_desk=True,
            has_cva_sensitivities=True,
            supervisory_approval=True,
        )
        assert elig.recommended_approach == CVAApproach.SA_CVA

    def test_hedges_enable_reduced(self) -> None:
        """Eligible hedges enable BA-CVA Reduced."""
        from src.cva_risk.cva_calculator import determine_eligibility
        from src.cva_risk.cva_params import CVAApproach

        elig = determine_eligibility(has_eligible_hedges=True)
        assert elig.recommended_approach == CVAApproach.BA_CVA_REDUCED


# =========================================================================
#  Test Module Imports
# =========================================================================

class TestCVAImports:
    """Test that all public exports are importable."""

    def test_main_imports(self) -> None:
        """All key classes importable from src.cva_risk."""
        from src.cva_risk import (
            CVACalculator,
            CVACounterparty,
            CVAHedge,
            BACVACalculator,
            SACVACalculator,
            CVAApproach,
        )
        assert CVACalculator is not None
        assert CVACounterparty is not None

    def test_params_imports(self) -> None:
        """Parameter constants importable."""
        from src.cva_risk import (
            BA_CVA_BETA,
            BA_CVA_RHO,
            BA_CVA_RISK_WEIGHTS,
            SA_CVA_BUCKETS,
            SACCR_ALPHA_FINANCIAL,
        )
        assert BA_CVA_BETA == 0.25
        assert SACCR_ALPHA_FINANCIAL == 1.4

    def test_enum_imports(self) -> None:
        """Enums importable."""
        from src.cva_risk import (
            CVAApproach,
            CVARating,
            CVASector,
            CVAHedgeType,
            SACVARiskFactorType,
        )
        assert CVAApproach.SA_CVA.value == "SA-CVA"
        assert CVARating.AAA.value == "AAA"
