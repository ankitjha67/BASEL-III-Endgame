"""Unit tests for core module — enums, models, and exceptions.

Tests cover:
- Enum completeness and value correctness for all FRTB risk classes
- Pydantic model creation, validation, and serialization
- Custom exception hierarchy
- Model computed properties (charges, totals)

References:
    - MAR21: FRTB risk class definitions
    - MAR22: DRC framework
    - MAR23: RRAO framework
"""

import pytest

from src.core.enums import (
    CommodityBucket,
    CorrelationScenario,
    CSRBucket,
    CSRSecBucket,
    CSRSecCTPBucket,
    CreditQuality,
    CurrencyCategory,
    DRCExposureType,
    DRCRatingCategory,
    DRCSeniority,
    DRCSecBucket,
    DRCSecCTPBucket,
    DRCSecRating,
    DRCSecSeniority,
    EquityBucket,
    EquityMarket,
    EquitySize,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
    RRAOCategory,
    SensitivityType,
)
from src.core.exceptions import (
    BaselEngineError,
    CalculationError,
    ConfigurationError,
    DataError,
    ValidationError,
)
from src.core.models import (
    BucketResult,
    DRCBucketResult,
    DRCPosition,
    DRCResult,
    FRTBResult,
    GIRRResult,
    RiskChargeResult,
    RRAOPosition,
    RRAOResult,
    SBMRiskClassResult,
    Sensitivity,
    WeightedSensitivity,
)


# =========================================================================
#  Enum Tests
# =========================================================================


class TestRiskClassEnum:
    """Tests for FRTB RiskClass enum per MAR21.1."""

    def test_risk_class_has_7_members(self) -> None:
        """RiskClass must have exactly 7 members per MAR21.1."""
        assert len(RiskClass) == 7

    def test_all_risk_classes_present(self) -> None:
        """All 7 FRTB risk classes must exist."""
        expected = {"GIRR", "CSR_NON_SEC", "CSR_SEC_NON_CTP", "CSR_SEC_CTP",
                    "EQUITY", "COMMODITY", "FX"}
        actual = {rc.value for rc in RiskClass}
        assert actual == expected

    def test_risk_class_string_values(self) -> None:
        """Each RiskClass value matches its name string."""
        assert RiskClass.GIRR.value == "GIRR"
        assert RiskClass.FX.value == "FX"
        assert RiskClass.EQUITY.value == "EQUITY"


class TestCSRBucketEnum:
    """Tests for CSR Non-Sec bucket enum per MAR21.12 Table 4."""

    def test_csr_bucket_has_18_values(self) -> None:
        """CSRBucket must have 18 buckets per MAR21.12."""
        assert len(CSRBucket) == 18

    def test_csr_bucket_values_1_to_18(self) -> None:
        """CSRBucket values are integers 1 through 18."""
        values = sorted(b.value for b in CSRBucket)
        assert values == list(range(1, 19))


class TestEquityBucketEnum:
    """Tests for Equity bucket enum per MAR21.17 Table 8."""

    def test_equity_bucket_has_13_values(self) -> None:
        """EquityBucket must have 13 buckets per MAR21.17."""
        assert len(EquityBucket) == 13

    def test_equity_bucket_values_1_to_13(self) -> None:
        """EquityBucket values are integers 1 through 13."""
        values = sorted(b.value for b in EquityBucket)
        assert values == list(range(1, 14))


class TestCommodityBucketEnum:
    """Tests for Commodity bucket enum per MAR21.19 Table 10."""

    def test_commodity_bucket_has_11_values(self) -> None:
        """CommodityBucket must have 11 buckets per MAR21.19."""
        assert len(CommodityBucket) == 11

    def test_commodity_bucket_values_1_to_11(self) -> None:
        """CommodityBucket values are integers 1 through 11."""
        values = sorted(b.value for b in CommodityBucket)
        assert values == list(range(1, 12))


class TestOtherEnums:
    """Tests for remaining enums: RiskMeasure, CorrelationScenario, GIRRTenor, etc."""

    def test_risk_measure_has_5_members(self) -> None:
        """RiskMeasure: DELTA, VEGA, CURVATURE, DRC, RRAO."""
        assert len(RiskMeasure) == 5

    def test_correlation_scenario_has_3_members(self) -> None:
        """LOW, MEDIUM, HIGH per MAR21.6."""
        assert len(CorrelationScenario) == 3

    def test_girr_tenor_has_12_members(self) -> None:
        """12 standard tenors from 0.25Y to 30Y per MAR21.8."""
        assert len(GIRRTenor) == 12

    def test_girr_tenor_values(self) -> None:
        """Tenor values match regulatory specification."""
        assert GIRRTenor.Y0_25.value == 0.25
        assert GIRRTenor.Y30.value == 30.0

    def test_girr_risk_factor_types(self) -> None:
        """YIELD_CURVE, INFLATION, CROSS_CURRENCY_BASIS per MAR21.8-21.9."""
        assert len(GIRRRiskFactorType) == 3

    def test_currency_category(self) -> None:
        """LOW_VOLATILITY, HIGH_VOLATILITY, SPECIFIED per MAR21.8."""
        assert len(CurrencyCategory) == 3

    def test_drc_seniority(self) -> None:
        """4 seniority levels per MAR22.12."""
        assert len(DRCSeniority) == 4

    def test_drc_rating_category(self) -> None:
        """9 rating categories per MAR22.14 (AAA through DEFAULTED)."""
        assert len(DRCRatingCategory) == 9

    def test_rrao_category(self) -> None:
        """EXOTIC (1.0%), OTHER (0.1%), EXEMPT per MAR23."""
        assert len(RRAOCategory) == 3
        assert RRAOCategory.EXOTIC.value == "EXOTIC"
        assert RRAOCategory.OTHER.value == "OTHER"


# =========================================================================
#  Model Tests
# =========================================================================


class TestSensitivityModel:
    """Tests for Sensitivity Pydantic model."""

    def test_create_basic_sensitivity(self) -> None:
        """Create a GIRR delta sensitivity with all required fields."""
        s = Sensitivity(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.DELTA,
            bucket="USD",
            risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
            tenor=GIRRTenor.Y10,
            label="OIS",
            value=5.0,
        )
        assert s.risk_class == RiskClass.GIRR
        assert s.value == 5.0
        assert s.tenor == GIRRTenor.Y10

    def test_sensitivity_default_values(self) -> None:
        """Sensitivity uses sensible defaults for optional fields."""
        s = Sensitivity(
            risk_class=RiskClass.FX,
            risk_measure=RiskMeasure.DELTA,
            bucket="EURUSD",
            value=10.0,
        )
        assert s.risk_factor_type == GIRRRiskFactorType.YIELD_CURVE
        assert s.tenor is None
        assert s.label == ""
        assert s.option_maturity is None

    def test_sensitivity_serialization_roundtrip(self) -> None:
        """Sensitivity can be serialized to dict and back."""
        s = Sensitivity(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.DELTA,
            bucket="USD",
            tenor=GIRRTenor.Y5,
            value=3.14,
        )
        d = s.model_dump()
        s2 = Sensitivity(**d)
        assert s2.value == pytest.approx(3.14)
        assert s2.tenor == GIRRTenor.Y5


class TestWeightedSensitivityModel:
    """Tests for WeightedSensitivity model."""

    def test_create_weighted_sensitivity(self) -> None:
        """WS_k = RW_k * s_k per MAR21.4."""
        s = Sensitivity(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.DELTA,
            bucket="USD",
            value=10.0,
        )
        ws = WeightedSensitivity(
            sensitivity=s,
            risk_weight=0.015,
            weighted_value=0.15,
        )
        assert ws.weighted_value == pytest.approx(0.15)
        assert ws.risk_weight == pytest.approx(0.015)


class TestBucketResult:
    """Tests for BucketResult model."""

    def test_bucket_result_creation(self) -> None:
        """BucketResult stores K_b and S_b."""
        br = BucketResult(
            bucket="USD",
            capital_charge=13.2288,
            net_weighted_sensitivity=15.0,
        )
        assert br.bucket == "USD"
        assert br.capital_charge == pytest.approx(13.2288)
        assert br.net_weighted_sensitivity == pytest.approx(15.0)


class TestGIRRResult:
    """Tests for GIRRResult and its computed properties."""

    @pytest.fixture
    def girr_result(self) -> GIRRResult:
        """Build a GIRRResult with known charge values."""
        def make_rc(rc: RiskClass, rm: RiskMeasure, sc: CorrelationScenario, charge: float) -> RiskChargeResult:
            return RiskChargeResult(
                risk_class=rc, risk_measure=rm, scenario=sc, capital_charge=charge
            )

        return GIRRResult(
            delta_low=make_rc(RiskClass.GIRR, RiskMeasure.DELTA, CorrelationScenario.LOW, 100.0),
            delta_medium=make_rc(RiskClass.GIRR, RiskMeasure.DELTA, CorrelationScenario.MEDIUM, 120.0),
            delta_high=make_rc(RiskClass.GIRR, RiskMeasure.DELTA, CorrelationScenario.HIGH, 90.0),
            vega_low=make_rc(RiskClass.GIRR, RiskMeasure.VEGA, CorrelationScenario.LOW, 30.0),
            vega_medium=make_rc(RiskClass.GIRR, RiskMeasure.VEGA, CorrelationScenario.MEDIUM, 25.0),
            vega_high=make_rc(RiskClass.GIRR, RiskMeasure.VEGA, CorrelationScenario.HIGH, 35.0),
            curvature_low=make_rc(RiskClass.GIRR, RiskMeasure.CURVATURE, CorrelationScenario.LOW, 10.0),
            curvature_medium=make_rc(RiskClass.GIRR, RiskMeasure.CURVATURE, CorrelationScenario.MEDIUM, 12.0),
            curvature_high=make_rc(RiskClass.GIRR, RiskMeasure.CURVATURE, CorrelationScenario.HIGH, 8.0),
        )

    def test_delta_charge_is_max_across_scenarios(self, girr_result: GIRRResult) -> None:
        """Delta charge = max(low, medium, high) per MAR21.6."""
        assert girr_result.delta_charge == pytest.approx(120.0)

    def test_vega_charge_is_max_across_scenarios(self, girr_result: GIRRResult) -> None:
        """Vega charge = max(low, medium, high) per MAR21.6."""
        assert girr_result.vega_charge == pytest.approx(35.0)

    def test_curvature_charge_is_max_across_scenarios(self, girr_result: GIRRResult) -> None:
        """Curvature charge = max(low, medium, high) per MAR21.6."""
        assert girr_result.curvature_charge == pytest.approx(12.0)

    def test_total_charge_is_sum(self, girr_result: GIRRResult) -> None:
        """Total = delta + vega + curvature."""
        assert girr_result.total_charge == pytest.approx(120.0 + 35.0 + 12.0)


class TestDRCModels:
    """Tests for DRC position and result models per MAR22."""

    def test_drc_position_creation(self) -> None:
        """DRCPosition captures all required fields for JTD calculation."""
        pos = DRCPosition(
            issuer="CORP-001",
            seniority=DRCSeniority.SENIOR_UNSECURED,
            rating=DRCRatingCategory.BBB,
            exposure_type=DRCExposureType.CORPORATE,
            notional=100.0,
            market_value=98.5,
            maturity_years=5.0,
            is_long=True,
        )
        assert pos.issuer == "CORP-001"
        assert pos.seniority == DRCSeniority.SENIOR_UNSECURED
        assert pos.is_long is True

    def test_drc_result(self) -> None:
        """DRCResult aggregates bucket results and gross JTD."""
        result = DRCResult(
            total_charge=50.0,
            gross_jtd_long=200.0,
            gross_jtd_short=80.0,
        )
        assert result.total_charge == pytest.approx(50.0)


class TestRRAOModels:
    """Tests for RRAO models per MAR23."""

    def test_rrao_position_exotic(self) -> None:
        """Exotic RRAO position with 1.0% risk weight."""
        pos = RRAOPosition(
            instrument_id="EXOTIC-001",
            notional=1000.0,
            category=RRAOCategory.EXOTIC,
        )
        assert pos.category == RRAOCategory.EXOTIC

    def test_rrao_result(self) -> None:
        """RRAOResult separates exotic and other charges."""
        result = RRAOResult(
            total_charge=15.0,
            exotic_charge=10.0,
            other_charge=5.0,
            exempt_notional=500.0,
        )
        assert result.total_charge == pytest.approx(15.0)


class TestFRTBResult:
    """Tests for FRTBResult master aggregation model."""

    def test_sbm_total(self) -> None:
        """SBM total = sum of all 7 risk class charges."""
        result = FRTBResult(
            girr_charge=100.0,
            csr_nonsec_charge=80.0,
            csr_sec_nonctp_charge=20.0,
            csr_sec_ctp_charge=10.0,
            equity_charge=50.0,
            commodity_charge=30.0,
            fx_charge=25.0,
        )
        assert result.sbm_total == pytest.approx(315.0)

    def test_total_capital_charge(self) -> None:
        """Total = SBM + DRC + RRAO."""
        result = FRTBResult(
            girr_charge=100.0,
            drc_nonsec=40.0,
            rrao_total=5.0,
        )
        assert result.total_capital_charge == pytest.approx(100.0 + 40.0 + 5.0)

    def test_drc_total(self) -> None:
        """DRC total equals drc_nonsec."""
        result = FRTBResult(drc_nonsec=42.0)
        assert result.drc_total == pytest.approx(42.0)


# =========================================================================
#  Exception Tests
# =========================================================================


class TestExceptions:
    """Tests for custom exception hierarchy."""

    def test_base_exception(self) -> None:
        """BaselEngineError is the root exception."""
        with pytest.raises(BaselEngineError):
            raise BaselEngineError("test error")

    def test_validation_error_is_subclass(self) -> None:
        """ValidationError inherits from BaselEngineError."""
        assert issubclass(ValidationError, BaselEngineError)
        with pytest.raises(BaselEngineError):
            raise ValidationError("bad input")

    def test_configuration_error(self) -> None:
        """ConfigurationError for missing regulatory parameters."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("missing param")

    def test_calculation_error(self) -> None:
        """CalculationError for computation failures."""
        with pytest.raises(CalculationError):
            raise CalculationError("non-PSD matrix")

    def test_data_error(self) -> None:
        """DataError for missing/malformed data."""
        with pytest.raises(DataError):
            raise DataError("missing data")

    def test_all_exceptions_caught_by_base(self) -> None:
        """All custom exceptions can be caught via BaselEngineError."""
        for exc_cls in [ValidationError, ConfigurationError, CalculationError, DataError]:
            with pytest.raises(BaselEngineError):
                raise exc_cls("test")
