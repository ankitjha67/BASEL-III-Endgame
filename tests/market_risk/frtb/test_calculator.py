"""Tests for the Master FRTB Calculator."""

from __future__ import annotations

import pytest

from src.core.enums import (
    DRCRatingCategory,
    DRCSeniority,
    DRCExposureType,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
    RRAOCategory,
)
from src.core.models import (
    DRCPosition,
    RRAOPosition,
    Sensitivity,
)
from src.market_risk.frtb.calculator import FRTBCalculator, FRTBResult


class TestFRTBCalculator:
    """Tests for the master FRTB calculator."""

    @pytest.fixture
    def calc(self):
        return FRTBCalculator()

    def test_import_and_init(self):
        calc = FRTBCalculator()
        assert calc is not None

    def test_empty_inputs(self, calc):
        result = calc.calculate()
        assert isinstance(result, FRTBResult)
        assert result.total_capital_charge == 0.0

    def test_girr_only(self, calc):
        sens = [Sensitivity(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.DELTA,
            bucket="USD",
            risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
            tenor=GIRRTenor.Y10,
            label="OIS",
            value=1_000_000.0,
        )]
        result = calc.calculate(sensitivities=sens)
        assert result.girr_charge > 0
        assert result.total_capital_charge > 0
        assert result.csr_nonsec_charge == 0.0

    def test_multi_risk_class(self, calc):
        """Test with sensitivities across multiple risk classes."""
        sens = [
            Sensitivity(
                risk_class=RiskClass.GIRR,
                risk_measure=RiskMeasure.DELTA,
                bucket="USD",
                risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
                tenor=GIRRTenor.Y10,
                label="OIS",
                value=1e6,
            ),
            Sensitivity(
                risk_class=RiskClass.EQUITY,
                risk_measure=RiskMeasure.DELTA,
                bucket="6",
                risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
                tenor=None,
                label="AAPL",
                value=500_000.0,
            ),
            Sensitivity(
                risk_class=RiskClass.FX,
                risk_measure=RiskMeasure.DELTA,
                bucket="EURUSD",
                risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
                tenor=None,
                label="EURUSD",
                value=2e6,
            ),
        ]
        result = calc.calculate(sensitivities=sens)
        assert result.girr_charge > 0
        assert result.equity_charge > 0
        assert result.fx_charge > 0
        assert result.total_capital_charge > 0

    def test_drc_only(self, calc):
        positions = [DRCPosition(
            issuer="CORP_A",
            seniority=DRCSeniority.SENIOR_UNSECURED,
            rating=DRCRatingCategory.BBB,
            exposure_type=DRCExposureType.CORPORATE,
            notional=10e6,
            market_value=9.8e6,
            maturity_years=3.0,
            is_long=True,
        )]
        result = calc.calculate(drc_positions=positions)
        assert result.drc_nonsec > 0
        assert result.total_capital_charge > 0

    def test_rrao_only(self, calc):
        positions = [RRAOPosition(
            instrument_id="EXOTIC_1",
            notional=5e6,
            category=RRAOCategory.EXOTIC,
        )]
        result = calc.calculate(rrao_positions=positions)
        assert result.rrao_total > 0
        assert result.total_capital_charge > 0

    def test_full_frtb(self, calc):
        """Full FRTB with SBM + DRC + RRAO."""
        sens = [
            Sensitivity(
                risk_class=RiskClass.GIRR,
                risk_measure=RiskMeasure.DELTA,
                bucket="USD",
                risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
                tenor=GIRRTenor.Y5,
                label="OIS",
                value=5e6,
            ),
        ]
        drc = [DRCPosition(
            issuer="CORP_B",
            seniority=DRCSeniority.SENIOR_UNSECURED,
            rating=DRCRatingCategory.A,
            exposure_type=DRCExposureType.CORPORATE,
            notional=20e6,
            market_value=19.5e6,
            maturity_years=2.0,
            is_long=True,
        )]
        rrao = [RRAOPosition(
            instrument_id="WEATHER_1",
            notional=10e6,
            category=RRAOCategory.EXOTIC,
        )]
        result = calc.calculate(
            sensitivities=sens,
            drc_positions=drc,
            rrao_positions=rrao,
        )
        assert result.girr_charge > 0
        assert result.drc_nonsec > 0
        assert result.rrao_total > 0
        total = result.girr_charge + result.drc_nonsec + result.rrao_total
        assert abs(result.total_capital_charge - total) < 1.0

    def test_sbm_total_computed(self, calc):
        """SBM total = sum of all risk class charges (computed during calculate)."""
        # sbm_total is set during calculate(), not a computed property
        sens = [Sensitivity(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.DELTA,
            bucket="USD",
            risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
            tenor=GIRRTenor.Y10,
            label="OIS",
            value=1e6,
        )]
        result = calc.calculate(sensitivities=sens)
        assert result.sbm_total > 0
        assert result.sbm_total == result.girr_charge  # only GIRR in this case

    def test_summary_output(self, calc):
        """Summary method should produce formatted text."""
        result = FRTBResult(girr_charge=11000, drc_nonsec=50000, rrao_total=5000)
        summary = calc.summary(result)
        assert "GIRR" in summary or "girr" in summary.lower()
