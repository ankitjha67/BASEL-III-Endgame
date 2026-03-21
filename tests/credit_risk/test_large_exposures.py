"""Tests for Large Exposures Framework (12 CFR 252 Subpart J / BCBS d283).

Validates single-counterparty credit limits, CRM application, exemptions,
connected counterparty aggregation, and reporting thresholds.
"""

from __future__ import annotations

import pytest

from src.credit_risk.large_exposures import (
    ConnectionType,
    CounterpartyCategory,
    CounterpartyExposure,
    CounterpartyGroup,
    ExemptionReason,
    ExposureType,
    GSIB_TO_GSIB_LIMIT,
    LargeExposureCalculator,
    REPORTING_THRESHOLD,
    STANDARD_LIMIT,
)


# =========================================================================
#  Fixtures
# =========================================================================

@pytest.fixture
def calc() -> LargeExposureCalculator:
    """Calculator with $200B Tier 1 capital (typical large G-SIB)."""
    return LargeExposureCalculator(tier1_capital=200_000.0, is_gsib=True)


@pytest.fixture
def non_gsib_calc() -> LargeExposureCalculator:
    """Calculator for a non-G-SIB bank with $50B Tier 1."""
    return LargeExposureCalculator(tier1_capital=50_000.0, is_gsib=False)


def _make_exposure(
    cp_id: str = "CP1",
    cp_name: str = "Counterparty 1",
    category: CounterpartyCategory = CounterpartyCategory.NON_FINANCIAL,
    exp_type: ExposureType = ExposureType.LOAN,
    gross: float = 10_000.0,
    collateral: float = 0.0,
    haircut: float = 0.0,
    guarantee: float = 0.0,
    is_exempt: bool = False,
    exemption_reason: ExemptionReason | None = None,
) -> CounterpartyExposure:
    return CounterpartyExposure(
        counterparty_id=cp_id,
        counterparty_name=cp_name,
        counterparty_category=category,
        exposure_type=exp_type,
        gross_exposure=gross,
        collateral_value=collateral,
        collateral_haircut=haircut,
        guarantee_amount=guarantee,
        is_exempt=is_exempt,
        exemption_reason=exemption_reason,
    )


# =========================================================================
#  Regulatory Constants
# =========================================================================

class TestRegulatoryConstants:
    """Verify regulatory limits match 12 CFR 252.72."""

    def test_gsib_to_gsib_limit_15_percent(self):
        """Per 12 CFR 252.72(a): G-SIB to G-SIB = 15% of T1."""
        assert GSIB_TO_GSIB_LIMIT == 0.15

    def test_standard_limit_25_percent(self):
        """Per 12 CFR 252.72(b): standard limit = 25% of T1."""
        assert STANDARD_LIMIT == 0.25

    def test_reporting_threshold_5_percent(self):
        """Per 12 CFR 252.78: reportable if >= 5% of T1."""
        assert REPORTING_THRESHOLD == 0.05


# =========================================================================
#  Initialisation
# =========================================================================

class TestInitialisation:
    def test_valid_initialisation(self):
        calc = LargeExposureCalculator(tier1_capital=100_000.0)
        assert calc.tier1_capital == 100_000.0
        assert calc.is_gsib is True

    def test_non_gsib_initialisation(self):
        calc = LargeExposureCalculator(tier1_capital=50_000.0, is_gsib=False)
        assert calc.is_gsib is False

    def test_zero_tier1_rejected(self):
        with pytest.raises(ValueError):
            LargeExposureCalculator(tier1_capital=0.0)

    def test_negative_tier1_rejected(self):
        with pytest.raises(ValueError):
            LargeExposureCalculator(tier1_capital=-100.0)


# =========================================================================
#  Single Counterparty Exposure
# =========================================================================

class TestSingleCounterparty:
    def test_single_loan_exposure(self, calc):
        """Single $10B loan to non-financial = 5% of $200B T1."""
        exp = _make_exposure(gross=10_000.0)
        result = calc.calculate([exp])
        assert result.total_counterparties == 1
        cp = result.counterparty_results[0]
        assert cp.gross_exposure == pytest.approx(10_000.0)
        assert cp.net_exposure == pytest.approx(10_000.0)
        assert cp.exposure_pct_tier1 == pytest.approx(0.05)
        assert cp.is_reportable is True
        assert cp.is_breach is False

    def test_multiple_exposure_types_same_cp(self, calc):
        """Aggregate loan + derivative + securities to same counterparty."""
        exposures = [
            _make_exposure(gross=20_000.0, exp_type=ExposureType.LOAN),
            _make_exposure(gross=5_000.0, exp_type=ExposureType.DERIVATIVE),
            _make_exposure(gross=3_000.0, exp_type=ExposureType.SECURITIES),
        ]
        result = calc.calculate(exposures)
        assert result.total_counterparties == 1
        cp = result.counterparty_results[0]
        assert cp.gross_exposure == pytest.approx(28_000.0)
        assert cp.exposure_breakdown["LOAN"] == pytest.approx(20_000.0)
        assert cp.exposure_breakdown["DERIVATIVE"] == pytest.approx(5_000.0)
        assert cp.exposure_breakdown["SECURITIES"] == pytest.approx(3_000.0)


# =========================================================================
#  Limit Determination
# =========================================================================

class TestLimitDetermination:
    def test_gsib_to_gsib_15_percent(self, calc):
        """G-SIB reporting bank to G-SIB counterparty: 15% limit."""
        exp = _make_exposure(
            category=CounterpartyCategory.GSIB,
            gross=25_000.0,
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.limit_pct == pytest.approx(0.15)
        assert cp.limit_amount == pytest.approx(30_000.0)  # 15% × 200,000

    def test_gsib_to_non_financial_25_percent(self, calc):
        """G-SIB to non-financial: 25% limit."""
        exp = _make_exposure(
            category=CounterpartyCategory.NON_FINANCIAL,
            gross=25_000.0,
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.limit_pct == pytest.approx(0.25)
        assert cp.limit_amount == pytest.approx(50_000.0)

    def test_non_gsib_to_gsib_25_percent(self, non_gsib_calc):
        """Non-G-SIB bank to G-SIB counterparty: 25% (not 15%)."""
        exp = _make_exposure(
            category=CounterpartyCategory.GSIB,
            gross=10_000.0,
        )
        result = non_gsib_calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.limit_pct == pytest.approx(0.25)

    def test_breach_detection(self, calc):
        """Detect breach when exposure > limit."""
        # 15% of 200,000 = 30,000. Expose 35,000 → breach
        exp = _make_exposure(
            category=CounterpartyCategory.GSIB,
            gross=35_000.0,
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.is_breach is True
        assert cp.headroom < 0

    def test_no_breach_at_limit(self, calc):
        """No breach when exposure exactly at limit."""
        exp = _make_exposure(
            category=CounterpartyCategory.NON_FINANCIAL,
            gross=50_000.0,  # Exactly 25% of 200,000
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.is_breach is False
        assert cp.headroom == pytest.approx(0.0)

    def test_headroom_calculation(self, calc):
        """Headroom = limit_amount - net_exposure."""
        exp = _make_exposure(gross=20_000.0)
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        # limit = 25% × 200,000 = 50,000; headroom = 50,000 - 20,000 = 30,000
        assert cp.headroom == pytest.approx(30_000.0)


# =========================================================================
#  Credit Risk Mitigation
# =========================================================================

class TestCRM:
    def test_collateral_reduces_exposure(self, calc):
        """Eligible collateral reduces net exposure per 12 CFR 252.74."""
        exp = _make_exposure(
            gross=20_000.0,
            collateral=5_000.0,
            haircut=0.10,  # 10% haircut
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        # Net = 20,000 - 5,000 × (1 - 0.10) = 20,000 - 4,500 = 15,500
        assert cp.net_exposure == pytest.approx(15_500.0)

    def test_guarantee_reduces_exposure(self, calc):
        """Eligible guarantee reduces net exposure per 12 CFR 252.74."""
        exp = _make_exposure(gross=20_000.0, guarantee=8_000.0)
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.net_exposure == pytest.approx(12_000.0)

    def test_combined_crm(self, calc):
        """Collateral + guarantee combined."""
        exp = _make_exposure(
            gross=30_000.0,
            collateral=10_000.0,
            haircut=0.20,
            guarantee=5_000.0,
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        # Net = 30,000 - 10,000 × 0.8 - 5,000 = 30,000 - 8,000 - 5,000 = 17,000
        assert cp.net_exposure == pytest.approx(17_000.0)

    def test_crm_cannot_make_negative(self, calc):
        """Net exposure floored at zero."""
        exp = _make_exposure(
            gross=10_000.0,
            collateral=15_000.0,  # More collateral than exposure
            haircut=0.0,
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.net_exposure == pytest.approx(0.0)

    def test_full_haircut_no_benefit(self, calc):
        """100% haircut means collateral provides no benefit."""
        exp = _make_exposure(
            gross=20_000.0,
            collateral=10_000.0,
            haircut=1.0,
        )
        result = calc.calculate([exp])
        cp = result.counterparty_results[0]
        assert cp.net_exposure == pytest.approx(20_000.0)


# =========================================================================
#  Exemptions
# =========================================================================

class TestExemptions:
    def test_exempt_exposure_excluded(self, calc):
        """Exempt exposures are excluded from calculation."""
        exposures = [
            _make_exposure(cp_id="CP1", gross=10_000.0),
            _make_exposure(
                cp_id="CP2", gross=50_000.0,
                is_exempt=True,
                exemption_reason=ExemptionReason.US_GOVERNMENT,
            ),
        ]
        result = calc.calculate(exposures)
        assert result.total_counterparties == 1
        assert result.counterparty_results[0].counterparty_id == "CP1"

    def test_sovereign_auto_exempt(self, calc):
        """Sovereign counterparties are auto-exempt per 12 CFR 252.77."""
        exp = _make_exposure(
            category=CounterpartyCategory.SOVEREIGN,
            gross=100_000.0,
        )
        result = calc.calculate([exp])
        assert result.total_counterparties == 0

    def test_intraday_exempt(self, calc):
        """Intraday exposures exempt per 12 CFR 252.77."""
        exp = _make_exposure(
            gross=5_000.0,
            is_exempt=True,
            exemption_reason=ExemptionReason.INTRADAY,
        )
        result = calc.calculate([exp])
        assert result.total_counterparties == 0


# =========================================================================
#  Connected Counterparties
# =========================================================================

class TestConnectedCounterparties:
    def test_connected_group_aggregation(self, calc):
        """Connected counterparties aggregated per 12 CFR 252.76."""
        exposures = [
            _make_exposure(cp_id="A", cp_name="Corp A", gross=15_000.0),
            _make_exposure(cp_id="B", cp_name="Corp B", gross=20_000.0),
        ]
        group = CounterpartyGroup(
            group_id="G1",
            group_name="A-B Group",
            member_ids=["A", "B"],
            connection_type=ConnectionType.REVENUE,
        )
        result = calc.calculate(exposures, connected_groups=[group])
        assert len(result.connected_groups) == 1
        g = result.connected_groups[0]
        assert g["aggregate_net_exposure"] == pytest.approx(35_000.0)
        assert g["member_count"] == 2

    def test_connected_group_breach(self, calc):
        """Connected group can breach even if individuals don't."""
        exposures = [
            _make_exposure(cp_id="A", cp_name="Corp A", gross=30_000.0),
            _make_exposure(cp_id="B", cp_name="Corp B", gross=25_000.0),
        ]
        group = CounterpartyGroup(
            group_id="G1",
            group_name="A-B Group",
            member_ids=["A", "B"],
            connection_type=ConnectionType.GUARANTEE,
        )
        result = calc.calculate(exposures, connected_groups=[group])
        g = result.connected_groups[0]
        # Aggregate = 55,000 > 25% × 200,000 = 50,000
        assert g["is_breach"] is True

    def test_connected_gsib_uses_stricter_limit(self, calc):
        """If a group contains a G-SIB, use the 15% limit."""
        exposures = [
            _make_exposure(
                cp_id="A", cp_name="G-SIB A", gross=15_000.0,
                category=CounterpartyCategory.GSIB,
            ),
            _make_exposure(cp_id="B", cp_name="Corp B", gross=10_000.0),
        ]
        group = CounterpartyGroup(
            group_id="G1",
            group_name="Mixed Group",
            member_ids=["A", "B"],
            connection_type=ConnectionType.CONTROL,
        )
        result = calc.calculate(exposures, connected_groups=[group])
        g = result.connected_groups[0]
        assert g["limit_pct"] == pytest.approx(0.15)


# =========================================================================
#  Reporting
# =========================================================================

class TestReporting:
    def test_reportable_at_5_percent(self, calc):
        """Exposures >= 5% of T1 are reportable per 12 CFR 252.78."""
        exp = _make_exposure(gross=10_000.0)  # 5% of 200,000
        result = calc.calculate([exp])
        assert result.counterparty_results[0].is_reportable is True

    def test_not_reportable_below_5_percent(self, calc):
        """Exposures < 5% of T1 are not reportable."""
        exp = _make_exposure(gross=9_000.0)  # 4.5% of 200,000
        result = calc.calculate([exp])
        assert result.counterparty_results[0].is_reportable is False

    def test_summary_statistics(self, calc):
        """Verify summary statistics are correct."""
        exposures = [
            _make_exposure(cp_id="A", cp_name="Corp A", gross=30_000.0),
            _make_exposure(cp_id="B", cp_name="Corp B", gross=5_000.0),
            _make_exposure(cp_id="C", cp_name="Corp C", gross=15_000.0),
        ]
        result = calc.calculate(exposures)
        assert result.total_counterparties == 3
        assert result.total_gross_exposure == pytest.approx(50_000.0)
        assert result.reportable_exposures == 2  # A (15%) and C (7.5%)
        assert result.largest_exposure_pct == pytest.approx(0.15)


# =========================================================================
#  Edge Cases
# =========================================================================

class TestEdgeCases:
    def test_empty_portfolio(self, calc):
        result = calc.calculate([])
        assert result.total_counterparties == 0
        assert result.total_gross_exposure == 0.0
        assert result.limit_breaches == 0

    def test_zero_exposure(self, calc):
        exp = _make_exposure(gross=0.0)
        result = calc.calculate([exp])
        assert result.counterparty_results[0].net_exposure == 0.0

    def test_all_exempt(self, calc):
        """All exposures exempt → empty results."""
        exposures = [
            _make_exposure(
                cp_id="US", category=CounterpartyCategory.SOVEREIGN,
                gross=100_000.0,
            ),
        ]
        result = calc.calculate(exposures)
        assert result.total_counterparties == 0

    def test_multiple_counterparties(self, calc):
        """Multiple distinct counterparties processed correctly."""
        exposures = [
            _make_exposure(cp_id="A", cp_name="Corp A", gross=20_000.0),
            _make_exposure(cp_id="B", cp_name="Corp B", gross=30_000.0),
            _make_exposure(cp_id="A", cp_name="Corp A", gross=10_000.0,
                          exp_type=ExposureType.DERIVATIVE),
        ]
        result = calc.calculate(exposures)
        assert result.total_counterparties == 2
        # Find Corp A — should aggregate to 30,000
        a_result = next(r for r in result.counterparty_results if r.counterparty_id == "A")
        assert a_result.gross_exposure == pytest.approx(30_000.0)
