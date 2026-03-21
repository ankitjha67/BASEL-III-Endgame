"""Tests for SA-CCR counterparty credit risk.

Comprehensive test suite covering Replacement Cost, PFE, EAD,
supervisory parameters, and edge cases per CRE52.

References:
    - CRE52: Standardised approach to counterparty credit risk
    - CRE52.30-52.38: Replacement cost
    - CRE52.39-52.72: PFE / add-on calculation
"""

from __future__ import annotations

import math
import pytest

from src.counterparty_risk.saccr.saccr import (
    SACCRCalculator,
    SACCRNettingSet,
    SACCRResult,
    SACCRTrade,
    adjusted_notional,
    supervisory_duration,
    trade_level_addon,
)
from src.counterparty_risk.saccr.saccr_params import (
    ALPHA_FINANCIAL,
    ALPHA_NON_FINANCIAL,
    PFE_FLOOR,
    SACCR_ASSET_CLASS_PARAMS,
    SACCRAssetClass,
    IRMaturityBucket,
    ir_maturity_bucket,
    mpor_scaling_factor,
)


# =========================================================================
#  Fixtures
# =========================================================================


@pytest.fixture
def calc() -> SACCRCalculator:
    """Shared SA-CCR calculator instance."""
    return SACCRCalculator()


def _make_trade(
    trade_id: str = "T1",
    asset_class: str = "IR",
    notional: float = 100e6,
    mtm_value: float = 0.0,
    start_years: float = 0.0,
    end_years: float = 5.0,
    is_long: bool = True,
    underlying: str = "USD",
    netting_set: str = "NS1",
    delta_override: float | None = None,
) -> SACCRTrade:
    """Helper to construct a SACCRTrade with sensible defaults."""
    return SACCRTrade(
        trade_id=trade_id,
        asset_class=asset_class,
        notional=notional,
        mtm_value=mtm_value,
        start_years=start_years,
        end_years=end_years,
        is_long=is_long,
        underlying=underlying,
        netting_set=netting_set,
        delta_override=delta_override,
    )


def _make_ns(
    trades: list[SACCRTrade],
    ns_id: str = "NS1",
    collateral: float = 0.0,
    is_margined: bool = False,
    threshold: float = 0.0,
    mta: float = 0.0,
    is_financial: bool = True,
    nica: float = 0.0,
) -> SACCRNettingSet:
    """Helper to construct a SACCRNettingSet."""
    return SACCRNettingSet(
        netting_set_id=ns_id,
        trades=trades,
        collateral=collateral,
        is_margined=is_margined,
        threshold=threshold,
        mta=mta,
        is_financial=is_financial,
        nica=nica,
    )


# =========================================================================
#  Original Tests (preserved)
# =========================================================================


class TestSACCRImports:
    def test_calculator_import(self):
        calc = SACCRCalculator()
        assert calc is not None

    def test_params_import(self):
        assert "IR" in {ac.value for ac in SACCRAssetClass}


class TestSACCRCalculatorOriginal:
    @pytest.fixture
    def calc(self):
        return SACCRCalculator()

    def test_single_ir_swap(self, calc):
        trade = _make_trade(notional=100e6, mtm_value=500_000.0, end_years=5.0)
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.ead > 0
        assert result.replacement_cost >= 0
        assert result.pfe >= 0
        assert result.alpha == 1.4

    def test_commercial_enduser_alpha(self, calc):
        trade = _make_trade(notional=50e6, mtm_value=100_000.0, end_years=3.0)
        ns = _make_ns([trade], is_financial=False)
        result = calc.calculate(ns)
        assert result.alpha == 1.0

    def test_collateralized_reduces_ead(self, calc):
        trade = _make_trade(
            asset_class="FX", notional=50e6, mtm_value=1e6,
            end_years=1.0, underlying="EURUSD",
        )
        uncollat = _make_ns([trade])
        collat = _make_ns([trade], collateral=500_000.0)
        assert calc.calculate(collat).ead <= calc.calculate(uncollat).ead

    def test_single_trade_netting_set(self, calc):
        """Netting set with one small trade should produce small EAD."""
        trade = _make_trade(notional=1e6, mtm_value=0.0, end_years=1.0)
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.ead >= 0


# =========================================================================
#  Replacement Cost Tests
# =========================================================================


class TestReplacementCost:
    """Tests for replacement cost (RC) calculation per CRE52.30-52.38."""

    @pytest.fixture
    def calc(self):
        return SACCRCalculator()

    def test_unmargined_positive_mtm_no_collateral(self, calc):
        """Unmargined RC = max(V - C, 0). V > 0, C = 0 => RC = V."""
        trade = _make_trade(mtm_value=2_000_000.0)
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.replacement_cost == pytest.approx(2_000_000.0, rel=1e-6)

    def test_unmargined_negative_mtm(self, calc):
        """Unmargined RC = max(V - C, 0). V < 0 => RC = 0."""
        trade = _make_trade(mtm_value=-500_000.0)
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.replacement_cost == pytest.approx(0.0, abs=0.01)

    def test_unmargined_fully_collateralized(self, calc):
        """Unmargined RC = max(V - C, 0). C > V => RC = 0."""
        trade = _make_trade(mtm_value=1_000_000.0)
        ns = _make_ns([trade], collateral=2_000_000.0)
        result = calc.calculate(ns)
        assert result.replacement_cost == pytest.approx(0.0, abs=0.01)

    def test_unmargined_partial_collateral(self, calc):
        """Unmargined RC = max(V - C, 0). V > C => RC = V - C."""
        trade = _make_trade(mtm_value=3_000_000.0)
        ns = _make_ns([trade], collateral=1_000_000.0)
        result = calc.calculate(ns)
        assert result.replacement_cost == pytest.approx(2_000_000.0, rel=1e-6)

    def test_unmargined_multiple_trades(self, calc):
        """RC uses portfolio-level MTM (sum of trade MTMs)."""
        t1 = _make_trade(trade_id="T1", mtm_value=1_000_000.0, end_years=3.0)
        t2 = _make_trade(trade_id="T2", mtm_value=-500_000.0, end_years=2.0)
        ns = _make_ns([t1, t2])
        # V = 1M - 0.5M = 0.5M, C = 0 => RC = 0.5M
        result = calc.calculate(ns)
        assert result.replacement_cost == pytest.approx(500_000.0, rel=1e-6)

    def test_margined_rc_threshold_mta(self, calc):
        """Margined RC = max(V - C, TH + MTA - NICA, 0).

        CRE52.33: For margined netting sets, RC is the larger of
        V - C and TH + MTA - NICA, floored at zero.
        """
        trade = _make_trade(mtm_value=200_000.0)
        ns = _make_ns(
            [trade],
            is_margined=True,
            collateral=100_000.0,
            threshold=500_000.0,
            mta=50_000.0,
            nica=100_000.0,
        )
        result = calc.calculate(ns)
        # V - C = 100K, TH + MTA - NICA = 450K => RC = 450K
        assert result.replacement_cost == pytest.approx(450_000.0, rel=1e-6)

    def test_margined_rc_vminus_c_dominates(self, calc):
        """Margined RC where V - C > TH + MTA - NICA."""
        trade = _make_trade(mtm_value=5_000_000.0)
        ns = _make_ns(
            [trade],
            is_margined=True,
            collateral=1_000_000.0,
            threshold=100_000.0,
            mta=10_000.0,
            nica=50_000.0,
        )
        result = calc.calculate(ns)
        # V - C = 4M, TH + MTA - NICA = 60K => RC = 4M
        assert result.replacement_cost == pytest.approx(4_000_000.0, rel=1e-6)

    def test_margined_rc_floored_at_zero(self, calc):
        """Margined RC is floored at zero even when both terms are negative."""
        trade = _make_trade(mtm_value=-1_000_000.0)
        ns = _make_ns(
            [trade],
            is_margined=True,
            collateral=2_000_000.0,
            threshold=0.0,
            mta=0.0,
            nica=500_000.0,
        )
        result = calc.calculate(ns)
        assert result.replacement_cost == pytest.approx(0.0, abs=0.01)


# =========================================================================
#  PFE Tests
# =========================================================================


class TestPFE:
    """Tests for Potential Future Exposure calculation per CRE52.39-52.72."""

    @pytest.fixture
    def calc(self):
        return SACCRCalculator()

    def test_single_ir_swap_pfe(self, calc):
        """PFE for a single IR swap uses supervisory duration and SF=0.005."""
        trade = _make_trade(
            asset_class="IR", notional=100e6,
            start_years=0.0, end_years=5.0,
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        # adjusted_notional = 100M * SD(0,5)
        sd = supervisory_duration(0.0, 5.0)
        expected_addon = 0.005 * 100e6 * sd  # SF * notional * SD
        # multiplier = 1.0 when V=0, C=0 (positive V-C exponent)
        assert result.pfe > 0
        assert result.addon_aggregate == pytest.approx(expected_addon, rel=0.01)

    def test_single_fx_forward_pfe(self, calc):
        """PFE for a single FX forward uses notional directly (no SD), SF=0.04."""
        trade = _make_trade(
            asset_class="FX", notional=10e6, end_years=1.0,
            underlying="EURUSD",
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        # FX: adjusted notional = notional, addon = SF * |EN| = 0.04 * 10M
        expected_addon = 0.04 * 10e6
        assert result.addon_aggregate == pytest.approx(expected_addon, rel=0.01)

    def test_single_equity_option_pfe(self, calc):
        """PFE for a single-name equity option."""
        trade = _make_trade(
            asset_class="EQUITY_SINGLE", notional=5e6,
            end_years=1.0, underlying="AAPL", delta_override=0.6,
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.pfe > 0
        assert "EQUITY_SINGLE" in result.addon_by_asset_class

    def test_single_commodity_future_pfe(self, calc):
        """PFE for a commodity (other) future."""
        trade = _make_trade(
            asset_class="COMMODITY_OTHER", notional=20e6,
            end_years=2.0, underlying="GOLD",
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        # SF=0.18, rho=0.4
        assert result.pfe > 0
        assert "COMMODITY_OTHER" in result.addon_by_asset_class

    def test_single_credit_derivative_pfe(self, calc):
        """PFE for a credit IG protection trade (CDS)."""
        trade = _make_trade(
            asset_class="CREDIT_IG", notional=50e6,
            start_years=0.0, end_years=5.0, underlying="ACME_CORP",
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.pfe > 0
        assert "CREDIT_IG" in result.addon_by_asset_class

    def test_multiple_asset_classes_addon(self, calc):
        """AddOns from different asset classes are summed (no cross-class netting)."""
        ir_trade = _make_trade(
            trade_id="IR1", asset_class="IR", notional=100e6,
            end_years=5.0, underlying="USD",
        )
        fx_trade = _make_trade(
            trade_id="FX1", asset_class="FX", notional=50e6,
            end_years=1.0, underlying="EURUSD",
        )
        ns = _make_ns([ir_trade, fx_trade])
        result = calc.calculate(ns)
        # Should have both asset class add-ons
        assert "IR" in result.addon_by_asset_class
        assert "FX" in result.addon_by_asset_class
        # Total addon = sum of individual
        total = sum(result.addon_by_asset_class.values())
        assert result.addon_aggregate == pytest.approx(total, rel=0.01)

    def test_multiplier_negative_mtm(self, calc):
        """PFE multiplier < 1 when netting set has negative V - C.

        CRE52.41: multiplier reduces PFE when netting set is out-of-the-money.
        """
        trade = _make_trade(
            asset_class="IR", notional=100e6,
            mtm_value=-5_000_000.0, end_years=5.0,
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.multiplier < 1.0
        assert result.multiplier >= PFE_FLOOR

    def test_multiplier_at_the_money(self, calc):
        """PFE multiplier = 1.0 when V = C = 0."""
        trade = _make_trade(
            asset_class="IR", notional=100e6,
            mtm_value=0.0, end_years=5.0,
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        # V - C = 0, exp(0/(2*0.95*addon)) = exp(0) = 1
        # multiplier = min(0.05 + 0.95*1, 1) = 1.0
        assert result.multiplier == pytest.approx(1.0, abs=1e-6)

    def test_multiplier_with_excess_collateral(self, calc):
        """PFE multiplier < 1 when C > V (excess collateral)."""
        trade = _make_trade(
            asset_class="FX", notional=50e6,
            mtm_value=1_000_000.0, end_years=1.0, underlying="EURUSD",
        )
        ns = _make_ns([trade], collateral=5_000_000.0)
        result = calc.calculate(ns)
        assert result.multiplier < 1.0

    def test_hedging_set_aggregation_ir(self, calc):
        """IR trades in same currency aggregate within maturity buckets.

        CRE52.49: Partial offsetting across maturity buckets using the
        correlation formula D = sqrt(D1^2 + D2^2 + D3^2 + 1.4*D1*D2 + ...).
        """
        # Two IR trades in USD: one short-term, one long-term
        t1 = _make_trade(
            trade_id="T1", asset_class="IR", notional=100e6,
            end_years=1.0, underlying="USD", is_long=True,
        )
        t2 = _make_trade(
            trade_id="T2", asset_class="IR", notional=100e6,
            end_years=10.0, underlying="USD", is_long=False,
        )
        ns = _make_ns([t1, t2])
        result = calc.calculate(ns)

        # Should have partial offset — addon < sum of individual addons
        ns1 = _make_ns([t1])
        ns2_only = _make_ns([t2])
        r1 = calc.calculate(ns1)
        r2 = calc.calculate(ns2_only)
        assert result.addon_aggregate < r1.addon_aggregate + r2.addon_aggregate

    def test_equity_index_addon(self, calc):
        """Equity index uses SF=0.20, rho=0.80."""
        trade = _make_trade(
            asset_class="EQUITY_INDEX", notional=25e6,
            end_years=1.0, underlying="SPX",
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.EQUITY_INDEX]
        assert params.supervisory_factor == 0.20
        assert params.correlation == 0.80
        assert result.pfe > 0


# =========================================================================
#  EAD Tests
# =========================================================================


class TestEAD:
    """Tests for EAD = alpha * (RC + PFE) per CRE52.30."""

    @pytest.fixture
    def calc(self):
        return SACCRCalculator()

    def test_ead_formula(self, calc):
        """EAD = alpha * (RC + PFE)."""
        trade = _make_trade(mtm_value=1_000_000.0, notional=100e6, end_years=5.0)
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        expected_ead = result.alpha * (result.replacement_cost + result.pfe)
        assert result.ead == pytest.approx(expected_ead, rel=1e-6)

    def test_alpha_financial_counterparty(self, calc):
        """Alpha = 1.4 for financial counterparties per CRE52.30."""
        trade = _make_trade()
        ns = _make_ns([trade], is_financial=True)
        result = calc.calculate(ns)
        assert result.alpha == ALPHA_FINANCIAL
        assert result.alpha == 1.4

    def test_alpha_commercial_end_user(self, calc):
        """Alpha = 1.0 for commercial end-users per 2026 re-proposal."""
        trade = _make_trade()
        ns = _make_ns([trade], is_financial=False)
        result = calc.calculate(ns)
        assert result.alpha == ALPHA_NON_FINANCIAL
        assert result.alpha == 1.0

    def test_ead_commercial_lower_than_financial(self, calc):
        """EAD with alpha=1.0 should be lower than alpha=1.4, ceteris paribus."""
        trade = _make_trade(mtm_value=500_000.0, notional=100e6, end_years=5.0)
        ns_fin = _make_ns([trade], is_financial=True)
        ns_com = _make_ns([trade], is_financial=False)
        ead_fin = calc.calculate(ns_fin).ead
        ead_com = calc.calculate(ns_com).ead
        assert ead_com < ead_fin
        assert ead_com == pytest.approx(ead_fin / 1.4, rel=1e-6)

    def test_ead_increases_with_notional(self, calc):
        """Larger notional produces larger EAD."""
        small = _make_trade(notional=10e6, end_years=5.0)
        large = _make_trade(notional=100e6, end_years=5.0)
        ns_small = _make_ns([small])
        ns_large = _make_ns([large])
        assert calc.calculate(ns_large).ead > calc.calculate(ns_small).ead

    def test_batch_calculation(self, calc):
        """calculate_batch processes multiple netting sets."""
        t1 = _make_trade(trade_id="T1", notional=100e6, end_years=5.0)
        t2 = _make_trade(
            trade_id="T2", asset_class="FX", notional=50e6,
            end_years=1.0, underlying="EURUSD",
        )
        ns1 = _make_ns([t1], ns_id="NS1")
        ns2 = _make_ns([t2], ns_id="NS2")
        results = calc.calculate_batch([ns1, ns2])
        assert len(results) == 2
        assert all(r.ead > 0 for r in results)

    def test_portfolio_ead(self, calc):
        """calculate_portfolio_ead returns aggregate summary."""
        t1 = _make_trade(trade_id="T1", notional=100e6, end_years=5.0)
        t2 = _make_trade(
            trade_id="T2", asset_class="FX", notional=50e6,
            end_years=1.0, underlying="GBPUSD",
        )
        ns1 = _make_ns([t1], ns_id="NS1")
        ns2 = _make_ns([t2], ns_id="NS2")
        portfolio = calc.calculate_portfolio_ead([ns1, ns2])
        assert portfolio["portfolio_ead"] > 0
        assert portfolio["netting_set_count"] == 2
        assert portfolio["trade_count"] == 2


# =========================================================================
#  Supervisory Parameter Tests
# =========================================================================


class TestSupervisoryParameters:
    """Tests verifying supervisory parameters match CRE52 tables."""

    def test_supervisory_duration_5y(self):
        """SD for S=0, E=5 per CRE52.46."""
        sd = supervisory_duration(0.0, 5.0)
        expected = (math.exp(-0.05 * 0) - math.exp(-0.05 * 5)) / 0.05
        assert sd == pytest.approx(expected, rel=1e-10)

    def test_supervisory_duration_1y(self):
        """SD for S=0, E=1."""
        sd = supervisory_duration(0.0, 1.0)
        expected = (1.0 - math.exp(-0.05)) / 0.05
        assert sd == pytest.approx(expected, rel=1e-10)

    def test_supervisory_duration_10y(self):
        """SD for S=0, E=10."""
        sd = supervisory_duration(0.0, 10.0)
        expected = (1.0 - math.exp(-0.50)) / 0.05
        assert sd == pytest.approx(expected, rel=1e-10)

    def test_supervisory_duration_forward_start(self):
        """SD for a forward-starting trade S=2, E=7."""
        sd = supervisory_duration(2.0, 7.0)
        expected = (math.exp(-0.10) - math.exp(-0.35)) / 0.05
        assert sd == pytest.approx(expected, rel=1e-10)

    def test_supervisory_delta_long(self):
        """Delta = +1 for long linear trades."""
        trade = _make_trade(is_long=True)
        assert trade.supervisory_delta == 1.0

    def test_supervisory_delta_short(self):
        """Delta = -1 for short linear trades."""
        trade = _make_trade(is_long=False)
        assert trade.supervisory_delta == -1.0

    def test_supervisory_delta_override(self):
        """Delta override for options (e.g., 0.6)."""
        trade = _make_trade(delta_override=0.6)
        assert trade.supervisory_delta == 0.6

    def test_sf_ir(self):
        """Supervisory factor for IR = 0.005."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.IR]
        assert params.supervisory_factor == 0.005

    def test_sf_fx(self):
        """Supervisory factor for FX = 0.04."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.FX]
        assert params.supervisory_factor == 0.04

    def test_sf_equity_single(self):
        """Supervisory factor for equity single-name = 0.32."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.EQUITY_SINGLE]
        assert params.supervisory_factor == 0.32

    def test_sf_equity_index(self):
        """Supervisory factor for equity index = 0.20."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.EQUITY_INDEX]
        assert params.supervisory_factor == 0.20

    def test_sf_credit_ig(self):
        """Supervisory factor for Credit IG = 0.0038."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.CREDIT_IG]
        assert params.supervisory_factor == 0.0038

    def test_sf_credit_spec(self):
        """Supervisory factor for Credit Speculative = 0.0054."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.CREDIT_SPEC]
        assert params.supervisory_factor == 0.0054

    def test_sf_commodity_elec(self):
        """Supervisory factor for commodity electricity = 0.40."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.COMMODITY_ELEC]
        assert params.supervisory_factor == 0.40

    def test_sf_commodity_other(self):
        """Supervisory factor for commodity other = 0.18."""
        params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.COMMODITY_OTHER]
        assert params.supervisory_factor == 0.18

    def test_ir_maturity_bucket_short(self):
        """Trades <= 1Y go to bucket 1."""
        assert ir_maturity_bucket(0.5) == IRMaturityBucket.BUCKET_1
        assert ir_maturity_bucket(1.0) == IRMaturityBucket.BUCKET_1

    def test_ir_maturity_bucket_medium(self):
        """Trades 1Y-5Y go to bucket 2."""
        assert ir_maturity_bucket(2.0) == IRMaturityBucket.BUCKET_2
        assert ir_maturity_bucket(5.0) == IRMaturityBucket.BUCKET_2

    def test_ir_maturity_bucket_long(self):
        """Trades > 5Y go to bucket 3."""
        assert ir_maturity_bucket(5.01) == IRMaturityBucket.BUCKET_3
        assert ir_maturity_bucket(30.0) == IRMaturityBucket.BUCKET_3

    def test_pfe_floor_value(self):
        """PFE multiplier floor = 0.05 per CRE52.41."""
        assert PFE_FLOOR == 0.05


# =========================================================================
#  Edge Cases
# =========================================================================


class TestEdgeCases:
    """Edge case tests for SA-CCR."""

    @pytest.fixture
    def calc(self):
        return SACCRCalculator()

    def test_very_short_maturity(self, calc):
        """Trade with very short maturity (< 10 business days ~ 0.04 years)."""
        trade = _make_trade(
            notional=100e6, start_years=0.0, end_years=0.04,
        )
        ns = _make_ns([trade])
        result = calc.calculate(ns)
        assert result.ead >= 0
        assert result.pfe >= 0

    def test_short_position_negative_delta(self, calc):
        """Short position contributes negative effective notional."""
        long_trade = _make_trade(
            trade_id="LONG", is_long=True, notional=100e6, end_years=5.0,
        )
        short_trade = _make_trade(
            trade_id="SHORT", is_long=False, notional=100e6, end_years=5.0,
        )
        # Perfectly offsetting trades in same bucket/currency
        ns = _make_ns([long_trade, short_trade])
        result = calc.calculate(ns)
        # With perfect offset, addon should be near zero
        assert result.addon_aggregate == pytest.approx(0.0, abs=1.0)

    def test_mixed_long_short_partial_offset(self, calc):
        """Mixed long/short positions with partial offset."""
        long = _make_trade(
            trade_id="L1", notional=100e6, end_years=5.0,
            is_long=True, underlying="USD",
        )
        short = _make_trade(
            trade_id="S1", notional=60e6, end_years=5.0,
            is_long=False, underlying="USD",
        )
        ns = _make_ns([long, short])
        result = calc.calculate(ns)
        # Net = 40M exposure worth of addon, not 160M
        ns_long_only = _make_ns([long])
        result_long = calc.calculate(ns_long_only)
        assert result.addon_aggregate < result_long.addon_aggregate

    def test_adjusted_notional_ir_uses_duration(self):
        """For IR trades, adjusted notional = notional * SD."""
        trade = _make_trade(
            asset_class="IR", notional=100e6,
            start_years=0.0, end_years=5.0,
        )
        sd = supervisory_duration(0.0, 5.0)
        an = adjusted_notional(trade)
        assert an == pytest.approx(100e6 * sd, rel=1e-10)

    def test_adjusted_notional_fx_uses_notional_directly(self):
        """For FX trades, adjusted notional = notional (no SD)."""
        trade = _make_trade(
            asset_class="FX", notional=50e6,
            start_years=0.0, end_years=1.0, underlying="EURUSD",
        )
        an = adjusted_notional(trade)
        assert an == pytest.approx(50e6, rel=1e-10)

    def test_trade_level_addon_function(self):
        """trade_level_addon returns delta * adjusted_notional."""
        trade = _make_trade(
            asset_class="FX", notional=50e6,
            end_years=1.0, is_long=True, underlying="GBPUSD",
        )
        tla = trade_level_addon(trade)
        assert tla == pytest.approx(50e6, rel=1e-10)  # delta=+1, adj_not=50M

    def test_trade_level_addon_short(self):
        """Short trade has negative trade-level addon."""
        trade = _make_trade(
            asset_class="FX", notional=50e6,
            end_years=1.0, is_long=False, underlying="GBPUSD",
        )
        tla = trade_level_addon(trade)
        assert tla == pytest.approx(-50e6, rel=1e-10)

    def test_invalid_asset_class_rejected(self):
        """Invalid asset class should be rejected by validation."""
        with pytest.raises(ValueError, match="Invalid asset class"):
            _make_trade(asset_class="INVALID")

    def test_end_before_start_rejected(self):
        """end_years <= start_years should be rejected."""
        with pytest.raises(ValueError, match="end_years"):
            _make_trade(start_years=5.0, end_years=3.0)

    def test_sensitivity_to_mtm(self, calc):
        """EAD sensitivity analysis produces results at different MTM levels."""
        trade = _make_trade(notional=100e6, mtm_value=1_000_000.0, end_years=5.0)
        ns = _make_ns([trade])
        results = calc.ead_sensitivity_to_mtm(ns)
        assert len(results) == 5
        # Higher MTM => higher EAD (through RC)
        eads = [r["ead"] for r in results]
        assert eads[-1] >= eads[0]

    def test_sensitivity_to_collateral(self, calc):
        """EAD sensitivity to collateral produces monotonically decreasing EADs."""
        trade = _make_trade(
            asset_class="FX", notional=50e6,
            mtm_value=2_000_000.0, end_years=1.0, underlying="EURUSD",
        )
        ns = _make_ns([trade])
        results = calc.ead_sensitivity_to_collateral(ns)
        assert len(results) == 5
        eads = [r["ead"] for r in results]
        # More collateral => lower or equal EAD
        for i in range(len(eads) - 1):
            assert eads[i + 1] <= eads[i] + 0.01

    def test_mpor_scaling_factor(self):
        """MPOR scaling factor = 1.5 * sqrt(MPOR/250)."""
        import numpy as np
        factor = mpor_scaling_factor(10)
        expected = 1.5 * np.sqrt(10 / 250.0)
        assert factor == pytest.approx(expected, rel=1e-10)

    def test_netting_set_alpha_property(self):
        """NettingSet.alpha returns correct value based on is_financial."""
        trade = _make_trade()
        ns_fin = _make_ns([trade], is_financial=True)
        ns_com = _make_ns([trade], is_financial=False)
        assert ns_fin.alpha == 1.4
        assert ns_com.alpha == 1.0

    def test_portfolio_mtm_property(self):
        """NettingSet.portfolio_mtm sums trade MTMs."""
        t1 = _make_trade(trade_id="T1", mtm_value=1_000_000.0, end_years=3.0)
        t2 = _make_trade(trade_id="T2", mtm_value=-400_000.0, end_years=2.0)
        ns = _make_ns([t1, t2])
        assert ns.portfolio_mtm == pytest.approx(600_000.0, rel=1e-10)
