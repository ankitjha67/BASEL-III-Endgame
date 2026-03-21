"""Tests for RWA Aggregation Engine.

Tests aggregation of RWA across credit, market, operational, and CVA risk types.

References:
- FFIEC 101 Schedule A: RWA by exposure type
- 12 CFR 217.10(a): Risk-based capital ratios
"""

import pytest

from src.capital.rwa_aggregator import (
    CreditRiskExposureType,
    CreditRiskRWAInput,
    CreditRiskRWAItem,
    CVARiskRWAInput,
    MarketRiskRWAInput,
    OperationalRiskRWAInput,
    RWABreakdown,
    aggregate_credit_risk_rwa,
    aggregate_rwa,
    convert_capital_charge_to_rwa,
    compute_output_floor,
)


class TestConvertCapitalChargeToRWA:
    """Tests for capital charge to RWA conversion."""

    def test_12_5x_multiplier(self) -> None:
        """RWA = capital charge * 12.5 (reciprocal of 8%)."""
        assert convert_capital_charge_to_rwa(100.0) == pytest.approx(1_250.0)
        assert convert_capital_charge_to_rwa(0.0) == pytest.approx(0.0)
        assert convert_capital_charge_to_rwa(1_000.0) == pytest.approx(12_500.0)


class TestOutputFloor:
    """Tests for output floor calculation."""

    def test_72_5_percent_floor(self) -> None:
        """Output floor = 72.5% of standardized RWA."""
        assert compute_output_floor(1_000_000.0) == pytest.approx(725_000.0)

    def test_output_floor_not_applied_by_default(self) -> None:
        """US 2026 proposal does NOT apply the output floor."""
        result = aggregate_rwa()
        assert result.output_floor_applied is False


class TestAggregateCreditRiskRWA:
    """Tests for credit risk RWA aggregation."""

    def test_empty_items(self) -> None:
        """No items produces zero RWA."""
        result = aggregate_credit_risk_rwa([])
        assert result.total_rwa == pytest.approx(0.0)
        assert result.total_exposure == pytest.approx(0.0)

    def test_aggregation_with_threshold_items(self) -> None:
        """250% RW threshold items are added to total credit risk RWA."""
        items = [
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.CORPORATE,
                exposure_amount=100_000.0,
                risk_weight=1.0,
                rwa=100_000.0,
                ffiec_101_line="3a",
            ),
        ]
        threshold_rwa = 5_000.0  # MSA/DTA at 250%
        result = aggregate_credit_risk_rwa(items, threshold_rwa)
        assert result.total_rwa == pytest.approx(105_000.0)
        assert result.threshold_250rw_rwa == pytest.approx(5_000.0)

    def test_multiple_exposure_types(self) -> None:
        """Aggregation across multiple exposure types."""
        items = [
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.SOVEREIGN,
                exposure_amount=500_000.0,
                risk_weight=0.0,
                rwa=0.0,
                ffiec_101_line="1a",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.CORPORATE_IG,
                exposure_amount=200_000.0,
                risk_weight=0.65,  # IG corporate per US 2026
                rwa=130_000.0,
                ffiec_101_line="3b",
            ),
            CreditRiskRWAItem(
                exposure_type=CreditRiskExposureType.RETAIL_TRANSACTOR,
                exposure_amount=50_000.0,
                risk_weight=0.45,  # Transactor per US 2026
                rwa=22_500.0,
                ffiec_101_line="4d",
            ),
        ]
        result = aggregate_credit_risk_rwa(items)
        assert result.total_exposure == pytest.approx(750_000.0)
        assert result.total_rwa == pytest.approx(152_500.0)


class TestAggregateRWA:
    """Tests for total RWA aggregation across risk types."""

    def test_all_risk_types(self) -> None:
        """Aggregate across credit, market, operational, CVA risk."""
        credit = CreditRiskRWAInput(total_rwa=1_000_000.0)
        market = MarketRiskRWAInput(total_capital_charge=5_000.0)
        oprisk = OperationalRiskRWAInput(capital_charge=10_000.0)
        cva = CVARiskRWAInput(total_cva_charge=2_000.0)

        result = aggregate_rwa(credit, market, oprisk, cva)

        expected = (
            1_000_000.0           # Credit
            + 5_000.0 * 12.5     # Market = 62,500
            + 10_000.0 * 12.5    # OpRisk = 125,000
            + 2_000.0 * 12.5     # CVA = 25,000
        )
        assert result.total_rwa == pytest.approx(expected)
        assert result.credit_risk_rwa == pytest.approx(1_000_000.0)
        assert result.market_risk_rwa == pytest.approx(62_500.0)

    def test_credit_only(self) -> None:
        """RWA with only credit risk input."""
        credit = CreditRiskRWAInput(total_rwa=800_000.0)
        result = aggregate_rwa(credit_risk=credit)
        assert result.total_rwa == pytest.approx(800_000.0)
        assert result.market_risk_rwa == pytest.approx(0.0)

    def test_empty_inputs(self) -> None:
        """No inputs produces zero total RWA."""
        result = aggregate_rwa()
        assert result.total_rwa == pytest.approx(0.0)

    def test_ilm_is_1_0(self) -> None:
        """ILM = 1.0 per US 2026 proposal — OpRisk capital = BIC * 1.0."""
        oprisk = OperationalRiskRWAInput(
            bic=8_000.0,
            ilm=1.0,  # US proposal: ILM not applied
            capital_charge=8_000.0,
        )
        assert oprisk.ilm == pytest.approx(1.0)
        assert oprisk.operational_risk_rwa == pytest.approx(100_000.0)

    def test_market_risk_rwa_property(self) -> None:
        """Market risk RWA = capital charge * 12.5."""
        market = MarketRiskRWAInput(total_capital_charge=4_000.0)
        assert market.market_risk_rwa == pytest.approx(50_000.0)
