"""Tests for the Reporting module — Basel III Endgame.

Tests cover:
- reporting_params: line item definitions, filing frequencies
- fr_y9c: FR Y-9C Schedule HC-R generation and validation
- ffiec101: FFIEC 101 Schedule A generation and validation
- fr_y15: FR Y-15 systemic risk report and G-SIB scoring
- fr_y14: FR Y-14A/Q capital assessment
- report_engine: orchestration, cross-validation, BCBS 239 lineage

All monetary amounts in USD millions ($M).

References:
- FR Y-9C Instructions, FFIEC 101 Instructions, FR Y-15 Instructions
- 12 CFR 217.10-22, BCBS 239
"""

from __future__ import annotations

from datetime import date

import pytest

from src.capital.capital_components import (
    AT1Instrument,
    AT1Result,
    CET1Result,
    CapitalTier,
    CommonEquityInputs,
    DeductionCategory,
    DeductionItem,
    InstrumentType,
    LeverageExposureInputs,
    Tier2Instrument,
    Tier2Result,
    TotalCapitalResult,
    compute_total_capital,
)
from src.capital.capital_ratios import (
    BufferRequirements,
    BufferZone,
    CapitalAdequacyResult,
    CapitalRatios,
    CapitalSurplusDeficit,
    PCACategory,
    PCAClassification,
    compute_capital_adequacy,
)
from src.capital.rwa_aggregator import (
    CreditRiskExposureType,
    CreditRiskRWAInput,
    CreditRiskRWAItem,
    FFIEC101ScheduleA,
    MarketRiskRWAInput,
    OperationalRiskRWAInput,
    CVARiskRWAInput,
    RWABreakdown,
    aggregate_rwa,
)


# =========================================================================
#  Fixtures — Realistic G-SIB data ($3.2T Category I)
# =========================================================================

@pytest.fixture
def reporting_date() -> date:
    """Standard reporting date."""
    return date(2026, 3, 31)


@pytest.fixture
def prior_reporting_date() -> date:
    """Prior quarter reporting date."""
    return date(2025, 12, 31)


@pytest.fixture
def equity_inputs() -> CommonEquityInputs:
    """CET1 equity components for a $3.2T G-SIB."""
    return CommonEquityInputs(
        common_stock=25_000.0,
        surplus=75_000.0,
        retained_earnings=120_000.0,
        aoci=-3_000.0,
        treasury_stock=5_000.0,
        minority_interest_cet1=1_500.0,
    )


@pytest.fixture
def deductions() -> list[DeductionItem]:
    """CET1 deductions."""
    return [
        DeductionItem(
            category=DeductionCategory.GOODWILL,
            amount=28_000.0,
            tier=CapitalTier.CET1,
        ),
        DeductionItem(
            category=DeductionCategory.OTHER_INTANGIBLES,
            amount=5_000.0,
            tier=CapitalTier.CET1,
        ),
        DeductionItem(
            category=DeductionCategory.DTA_CARRYFORWARD,
            amount=2_000.0,
            tier=CapitalTier.CET1,
        ),
    ]


@pytest.fixture
def at1_instruments() -> list[AT1Instrument]:
    """AT1 instruments."""
    return [
        AT1Instrument(
            instrument_type=InstrumentType.PREFERRED_NONCUMULATIVE,
            amount=15_000.0,
        ),
    ]


@pytest.fixture
def tier2_instruments() -> list[Tier2Instrument]:
    """Tier 2 instruments."""
    return [
        Tier2Instrument(
            instrument_type=InstrumentType.SUBORDINATED_DEBT,
            face_amount=20_000.0,
            current_amount=18_000.0,
            remaining_maturity_years=7.0,
        ),
    ]


@pytest.fixture
def total_capital(
    equity_inputs: CommonEquityInputs,
    deductions: list[DeductionItem],
    at1_instruments: list[AT1Instrument],
    tier2_instruments: list[Tier2Instrument],
) -> TotalCapitalResult:
    """Computed total capital result."""
    return compute_total_capital(
        equity_inputs=equity_inputs,
        deductions=deductions,
        at1_instruments=at1_instruments,
        tier2_instruments=tier2_instruments,
        total_allowance=8_000.0,
        sa_rwa=1_200_000.0,
    )


@pytest.fixture
def credit_risk_items() -> list[CreditRiskRWAItem]:
    """Credit risk RWA line items for FFIEC 101."""
    return [
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.SOVEREIGN,
            exposure_amount=200_000.0, risk_weight=0.0, rwa=0.0,
            ffiec_101_line="1a",
        ),
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.CORPORATE,
            exposure_amount=400_000.0, risk_weight=1.0, rwa=400_000.0,
            ffiec_101_line="3a",
        ),
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.CORPORATE_IG,
            exposure_amount=300_000.0, risk_weight=0.65, rwa=195_000.0,
            ffiec_101_line="3b",
        ),
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.RETAIL_RESIDENTIAL,
            exposure_amount=500_000.0, risk_weight=0.50, rwa=250_000.0,
            ffiec_101_line="4a",
        ),
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.RETAIL_TRANSACTOR,
            exposure_amount=100_000.0, risk_weight=0.45, rwa=45_000.0,
            ffiec_101_line="4d",
        ),
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.SECURITIZATION,
            exposure_amount=80_000.0, risk_weight=1.0, rwa=80_000.0,
            ffiec_101_line="6",
        ),
        CreditRiskRWAItem(
            exposure_type=CreditRiskExposureType.OTHER_ASSETS,
            exposure_amount=120_000.0, risk_weight=1.0, rwa=120_000.0,
            ffiec_101_line="8b",
        ),
    ]


@pytest.fixture
def market_risk_input() -> MarketRiskRWAInput:
    """Market risk FRTB input."""
    return MarketRiskRWAInput(
        sbm_charge=4_500.0,
        drc_charge=1_200.0,
        rrao_charge=300.0,
        total_capital_charge=6_000.0,
        girr_charge=1_500.0,
        csr_nonsec_charge=1_200.0,
        equity_charge=800.0,
        commodity_charge=500.0,
        fx_charge=500.0,
    )


@pytest.fixture
def operational_risk_input() -> OperationalRiskRWAInput:
    """Operational risk input."""
    return OperationalRiskRWAInput(
        business_indicator=60_000.0,
        bic=8_000.0,
        ilm=1.0,
        capital_charge=8_000.0,
    )


@pytest.fixture
def cva_risk_input() -> CVARiskRWAInput:
    """CVA risk input."""
    return CVARiskRWAInput(
        sa_cva_charge=1_500.0,
        total_cva_charge=1_500.0,
    )


@pytest.fixture
def rwa_breakdown(
    credit_risk_items: list[CreditRiskRWAItem],
    market_risk_input: MarketRiskRWAInput,
    operational_risk_input: OperationalRiskRWAInput,
    cva_risk_input: CVARiskRWAInput,
) -> RWABreakdown:
    """Aggregated RWA breakdown."""
    from src.capital.rwa_aggregator import (
        CreditRiskRWAInput,
        aggregate_rwa,
        aggregate_credit_risk_rwa,
    )
    cr = aggregate_credit_risk_rwa(credit_risk_items)
    return aggregate_rwa(
        credit_risk=cr,
        market_risk=market_risk_input,
        operational_risk=operational_risk_input,
        cva_risk=cva_risk_input,
    )


@pytest.fixture
def capital_adequacy(
    total_capital: TotalCapitalResult,
    rwa_breakdown: RWABreakdown,
) -> CapitalAdequacyResult:
    """Capital adequacy assessment."""
    leverage_inputs = LeverageExposureInputs(
        total_on_balance_sheet=3_200_000.0,
        derivative_exposures=150_000.0,
        sft_exposures=100_000.0,
        off_balance_sheet_items=200_000.0,
    )
    return compute_capital_adequacy(
        capital_result=total_capital,
        rwa_breakdown=rwa_breakdown,
        leverage_inputs=leverage_inputs,
        gsib_score=0.0200,
        scb_rate=0.035,
    )


@pytest.fixture
def gsib_indicator_values() -> dict[str, float]:
    """G-SIB indicator values for a $3.2T Category I G-SIB."""
    return {
        "total_exposures": 3_500_000.0,
        "intra_financial_system_assets": 250_000.0,
        "intra_financial_system_liabilities": 280_000.0,
        "securities_outstanding": 350_000.0,
        "payments_activity": 80_000_000.0,
        "assets_under_custody": 25_000_000.0,
        "underwriting_activity": 400_000.0,
        "otc_derivatives_notional": 45_000_000.0,
        "trading_and_afs_securities": 450_000.0,
        "level_3_assets": 30_000.0,
        "cross_jurisdictional_claims": 800_000.0,
        "cross_jurisdictional_liabilities": 600_000.0,
        "stwf_0_30_days": 150_000.0,
        "stwf_31_90_days": 120_000.0,
        "stwf_91_180_days": 80_000.0,
        "stwf_181_365_days": 60_000.0,
        "avg_total_assets": 3_200_000.0,
    }


@pytest.fixture
def stress_projections() -> dict[str, list[dict[str, float]]]:
    """Stress projections for FR Y-14 (9 quarters, 2 scenarios)."""
    base = []
    sa = []
    for q in range(9):
        # Baseline: stable
        base.append({
            "cet1_capital": 180_000.0 + q * 500.0,
            "tier1_capital": 195_000.0 + q * 500.0,
            "total_capital": 213_000.0 + q * 500.0,
            "total_rwa": 1_300_000.0,
        })
        # Severely adverse: declining capital
        sa.append({
            "cet1_capital": 180_000.0 - q * 5_000.0,
            "tier1_capital": 195_000.0 - q * 5_000.0,
            "total_capital": 213_000.0 - q * 5_000.0,
            "total_rwa": 1_300_000.0 + q * 10_000.0,
        })
    return {
        "BASELINE": base,
        "SEVERELY_ADVERSE": sa,
    }


# =========================================================================
#  Tests: reporting_params
# =========================================================================

class TestReportingParams:
    """Tests for reporting_params.py."""

    def test_report_definitions_complete(self) -> None:
        """All 5 report types have definitions."""
        from src.reporting.reporting_params import REPORT_DEFINITIONS, ReportType
        for rt in ReportType:
            assert rt in REPORT_DEFINITIONS, f"Missing definition for {rt}"

    def test_hcr_part_i_line_items(self) -> None:
        """HC-R Part I has all 17+ key line items defined."""
        from src.reporting.reporting_params import HCR_PART_I_LINE_ITEMS
        required_lines = ["1", "2", "3", "7", "8", "11", "12", "13",
                          "15", "15a", "16a", "16b", "17", "18"]
        for line in required_lines:
            assert line in HCR_PART_I_LINE_ITEMS, f"Missing line {line}"

    def test_ffiec_101_lines(self) -> None:
        """FFIEC 101 Schedule A has lines 1a through 13."""
        from src.reporting.reporting_params import FFIEC_101_SCHEDULE_A_LINES
        required_lines = ["1a", "1b", "2", "3a", "3b", "4a", "4b", "4c",
                          "4d", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
        for line in required_lines:
            assert line in FFIEC_101_SCHEDULE_A_LINES, f"Missing line {line}"

    def test_fr_y15_indicators(self) -> None:
        """FR Y-15 has all 12 Method 1 indicators."""
        from src.reporting.reporting_params import FR_Y15_INDICATORS
        assert len(FR_Y15_INDICATORS) == 12

    def test_bcbs_239_thresholds(self) -> None:
        """BCBS 239 thresholds have plausible values."""
        from src.reporting.reporting_params import BCBS_239_THRESHOLDS
        assert 0.0 < BCBS_239_THRESHOLDS.completeness_minimum <= 1.0
        assert BCBS_239_THRESHOLDS.timeliness_max_days > 0

    def test_pillar3_templates(self) -> None:
        """All Pillar 3 templates defined."""
        from src.reporting.reporting_params import Pillar3Template
        assert len(Pillar3Template) == 20

    def test_filing_frequencies(self) -> None:
        """Filing frequencies are correct."""
        from src.reporting.reporting_params import REPORT_DEFINITIONS, ReportType, FilingFrequency
        assert REPORT_DEFINITIONS[ReportType.FR_Y_9C].frequency == FilingFrequency.QUARTERLY
        assert REPORT_DEFINITIONS[ReportType.FR_Y_14A].frequency == FilingFrequency.ANNUAL


# =========================================================================
#  Tests: fr_y9c
# =========================================================================

class TestFRY9C:
    """Tests for FR Y-9C Schedule HC-R generation."""

    def test_generate_fr_y9c(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Generate a complete FR Y-9C and verify structure."""
        report = generate_fr_y9c(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            entity_name="Test G-SIB",
        )
        assert report.report_type == "FR_Y_9C"
        assert report.reporting_date == reporting_date
        assert report.part_i.item_12_cet1_capital.amount > 0
        assert report.part_i.item_18_total_capital.amount > 0
        assert report.part_ii.base_report.total_rwa > 0

    def test_y9c_data_quality_passes(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Data quality checks should pass for valid data."""
        report = generate_fr_y9c(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        assert report.data_quality.overall_pass is True
        assert report.data_quality.failed_checks == 0

    def test_y9c_capital_footing(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """CET1 + AT1 = Tier 1, Tier 1 + Tier 2 = Total Capital."""
        report = generate_fr_y9c(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        pi = report.part_i
        cet1 = pi.item_12_cet1_capital.amount
        at1 = pi.item_15_at1_capital.amount
        tier1 = pi.item_15a_tier1_capital.amount
        tier2 = pi.item_17_tier2_capital.amount
        total = pi.item_18_total_capital.amount

        assert abs(tier1 - (cet1 + at1)) < 1.0
        assert abs(total - (tier1 + tier2)) < 1.0

    def test_y9c_variance_analysis(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
        prior_reporting_date: date,
    ) -> None:
        """Variance analysis produces results when prior period provided."""
        report = generate_fr_y9c(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            prior_capital=total_capital,
            prior_reporting_date=prior_reporting_date,
        )
        # Same data => all variances should be zero / NONE materiality
        assert len(report.variances) > 0
        for v in report.variances:
            assert v.absolute_change == 0.0
            assert v.materiality.value == "NONE"

    def test_materiality_classification(self) -> None:
        """Materiality classification works correctly."""
        from src.reporting.fr_y9c import classify_materiality, MaterialityFlag
        assert classify_materiality(100.0, 100.0) == MaterialityFlag.NONE
        assert classify_materiality(106.0, 100.0) == MaterialityFlag.NOTABLE
        assert classify_materiality(115.0, 100.0) == MaterialityFlag.MATERIAL
        assert classify_materiality(130.0, 100.0) == MaterialityFlag.SIGNIFICANT
        assert classify_materiality(50.0, 0.0) == MaterialityFlag.SIGNIFICANT

    def test_y9c_extended_part_ii(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Extended Part II includes buffer and PCA analysis."""
        report = generate_fr_y9c(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        p2 = report.part_ii
        assert p2.combined_buffer > 0
        assert p2.effective_cet1_minimum > 0.045
        assert p2.pca_category in [c.value for c in PCACategory]


# =========================================================================
#  Tests: ffiec101
# =========================================================================

class TestFFIEC101:
    """Tests for FFIEC 101 Schedule A generation."""

    def test_generate_ffiec_101(
        self, credit_risk_items: list[CreditRiskRWAItem],
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Generate FFIEC 101 and verify structure."""
        report = generate_ffiec_101(
            credit_risk_items=credit_risk_items,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            entity_name="Test G-SIB",
        )
        assert report.report_type == "FFIEC_101"
        assert report.schedule_a.total_rwa > 0
        assert len(report.schedule_a.credit_risk_details) > 0

    def test_ffiec_101_data_quality(
        self, credit_risk_items: list[CreditRiskRWAItem],
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Data quality checks pass for valid data."""
        report = generate_ffiec_101(
            credit_risk_items=credit_risk_items,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        assert report.data_quality.overall_pass is True

    def test_ffiec_101_with_market_risk(
        self, credit_risk_items: list[CreditRiskRWAItem],
        rwa_breakdown: RWABreakdown,
        market_risk_input: MarketRiskRWAInput,
        reporting_date: date,
    ) -> None:
        """Market risk FRTB detail populated when input provided."""
        report = generate_ffiec_101(
            credit_risk_items=credit_risk_items,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            market_risk_input=market_risk_input,
        )
        assert report.schedule_a.market_risk_detail is not None
        assert report.schedule_a.market_risk_detail.girr_charge == 1_500.0

    def test_ffiec_101_line_details(
        self, credit_risk_items: list[CreditRiskRWAItem],
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Credit risk detail lines map to correct line references."""
        report = generate_ffiec_101(
            credit_risk_items=credit_risk_items,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        details = report.schedule_a.credit_risk_details
        line_refs = {d.line_reference for d in details}
        # Should have corporate (3a), corporate IG (3b), etc.
        assert "3a" in line_refs
        assert "3b" in line_refs
        assert "4d" in line_refs  # Retail transactor


# =========================================================================
#  Tests: fr_y15
# =========================================================================

class TestFRY15:
    """Tests for FR Y-15 Systemic Risk Report."""

    def test_generate_fr_y15(
        self, gsib_indicator_values: dict[str, float],
        reporting_date: date,
    ) -> None:
        """Generate FR Y-15 and verify structure."""
        report = generate_fr_y15(
            indicator_values=gsib_indicator_values,
            reporting_date=reporting_date,
            entity_name="Test G-SIB",
        )
        assert report.report_type == "FR_Y_15"
        assert report.surcharge_determination.method1.total_score_bps > 0
        assert report.surcharge_determination.final_surcharge_pct >= 1.0

    def test_method1_score(
        self, gsib_indicator_values: dict[str, float],
    ) -> None:
        """Method 1 score computation produces positive score."""
        from src.reporting.fr_y15 import compute_method1_score
        result = compute_method1_score(gsib_indicator_values)
        assert result.total_score_bps > 0
        assert len(result.category_scores) == 5
        # All 5 categories present
        cats = {c.category for c in result.category_scores}
        assert "Size" in cats
        assert "Interconnectedness" in cats
        assert "Substitutability" in cats
        assert "Complexity" in cats
        assert "Cross-Jurisdictional Activity" in cats

    def test_method2_score(
        self, gsib_indicator_values: dict[str, float],
    ) -> None:
        """Method 2 score includes STWF component."""
        from src.reporting.fr_y15 import compute_method2_score
        stwf = {
            "stwf_0_30_days": 150_000.0,
            "stwf_31_90_days": 120_000.0,
            "stwf_91_180_days": 80_000.0,
            "stwf_181_365_days": 60_000.0,
        }
        result = compute_method2_score(
            gsib_indicator_values, stwf, 3_200_000.0,
        )
        assert result.total_score_bps > 0
        # Should have STWF category
        cats = {c.category for c in result.category_scores}
        assert "STWF (Method 2)" in cats

    def test_surcharge_bands(self) -> None:
        """Score-to-surcharge uses 20bp bands / 0.1% increments per 2026."""
        from src.reporting.fr_y15 import score_to_surcharge
        # Score of 130 bps -> first band -> 1.0%
        surcharge, bucket, _, _ = score_to_surcharge(130.0)
        assert surcharge == 1.0
        assert bucket == 1

        # Score of 150 bps -> second band -> 1.1%
        surcharge, bucket, _, _ = score_to_surcharge(150.0)
        assert surcharge == pytest.approx(1.1)
        assert bucket == 2

        # Score of 170 bps -> third band -> 1.2%
        surcharge, bucket, _, _ = score_to_surcharge(170.0)
        assert surcharge == pytest.approx(1.2)
        assert bucket == 3

    def test_surcharge_minimum(self) -> None:
        """Score below threshold gets minimum 1.0% surcharge."""
        from src.reporting.fr_y15 import score_to_surcharge
        surcharge, _, _, _ = score_to_surcharge(50.0)
        assert surcharge == 1.0

    def test_substitutability_cap(self) -> None:
        """Substitutability category capped at 500bps."""
        from src.reporting.fr_y15 import compute_method1_score
        # Create data with extremely high substitutability
        vals = {
            "total_exposures": 3_500_000.0,
            "intra_financial_system_assets": 250_000.0,
            "intra_financial_system_liabilities": 280_000.0,
            "securities_outstanding": 350_000.0,
            "payments_activity": 500_000_000.0,  # Very high
            "assets_under_custody": 100_000_000.0,  # Very high
            "underwriting_activity": 5_000_000.0,  # Very high
            "otc_derivatives_notional": 45_000_000.0,
            "trading_and_afs_securities": 450_000.0,
            "level_3_assets": 30_000.0,
            "cross_jurisdictional_claims": 800_000.0,
            "cross_jurisdictional_liabilities": 600_000.0,
        }
        result = compute_method1_score(vals)
        sub_cat = [c for c in result.category_scores if c.category == "Substitutability"][0]
        assert sub_cat.cap_applied is True
        assert sub_cat.capped_score_bps == 500.0

    def test_fr_y15_data_quality(
        self, gsib_indicator_values: dict[str, float],
        reporting_date: date,
    ) -> None:
        """Data quality passes for valid G-SIB data."""
        report = generate_fr_y15(
            indicator_values=gsib_indicator_values,
            reporting_date=reporting_date,
        )
        assert report.data_quality.overall_pass is True

    def test_fr_y15_binding_method(
        self, gsib_indicator_values: dict[str, float],
        reporting_date: date,
    ) -> None:
        """Binding method is whichever produces higher surcharge."""
        report = generate_fr_y15(
            indicator_values=gsib_indicator_values,
            reporting_date=reporting_date,
        )
        det = report.surcharge_determination
        if det.method2.surcharge_pct >= det.method1.surcharge_pct:
            assert det.binding_method == "Method 2"
        else:
            assert det.binding_method == "Method 1"
        assert det.final_surcharge_pct == max(
            det.method1.surcharge_pct, det.method2.surcharge_pct
        )


# =========================================================================
#  Tests: fr_y14
# =========================================================================

class TestFRY14:
    """Tests for FR Y-14A/Q Capital Assessment."""

    def test_generate_fr_y14(
        self, capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Generate FR Y-14 and verify structure."""
        report = generate_fr_y14(
            base_adequacy=capital_adequacy,
            base_rwa_breakdown=rwa_breakdown,
            stress_projections=stress_projections,
            reporting_date=reporting_date,
            entity_name="Test G-SIB",
        )
        assert report.report_type == "FR_Y_14"
        assert len(report.summary_schedules) == 2  # Baseline + SA

    def test_y14_9_quarter_horizon(
        self, capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Each scenario has 9 quarters of projections."""
        report = generate_fr_y14(
            base_adequacy=capital_adequacy,
            base_rwa_breakdown=rwa_breakdown,
            stress_projections=stress_projections,
            reporting_date=reporting_date,
        )
        for schedule in report.summary_schedules:
            assert len(schedule.projections) == 9

    def test_y14_severely_adverse_declining(
        self, capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Severely adverse shows declining CET1 ratio."""
        report = generate_fr_y14(
            base_adequacy=capital_adequacy,
            base_rwa_breakdown=rwa_breakdown,
            stress_projections=stress_projections,
            reporting_date=reporting_date,
        )
        sa_schedule = [
            s for s in report.summary_schedules
            if s.scenario == "SEVERELY_ADVERSE"
        ][0]
        # First quarter CET1 > last quarter CET1
        assert sa_schedule.projections[0].cet1_ratio > sa_schedule.projections[-1].cet1_ratio

    def test_y14_data_quality(
        self, capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Data quality passes for valid projections."""
        report = generate_fr_y14(
            base_adequacy=capital_adequacy,
            base_rwa_breakdown=rwa_breakdown,
            stress_projections=stress_projections,
            reporting_date=reporting_date,
        )
        assert report.data_quality.overall_pass is True

    def test_y14_annual_vs_quarterly(
        self, capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Y-14A vs Y-14Q distinction."""
        annual = generate_fr_y14(
            base_adequacy=capital_adequacy,
            base_rwa_breakdown=rwa_breakdown,
            stress_projections=stress_projections,
            reporting_date=reporting_date,
            is_annual=True,
        )
        quarterly = generate_fr_y14(
            base_adequacy=capital_adequacy,
            base_rwa_breakdown=rwa_breakdown,
            stress_projections=stress_projections,
            reporting_date=reporting_date,
            is_annual=False,
        )
        assert annual.report_subtype == "Y-14A"
        assert quarterly.report_subtype == "Y-14Q"


# =========================================================================
#  Tests: report_engine
# =========================================================================

class TestReportEngine:
    """Tests for the report orchestrator."""

    def test_generate_all_reports(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        credit_risk_items: list[CreditRiskRWAItem],
        market_risk_input: MarketRiskRWAInput,
        gsib_indicator_values: dict[str, float],
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Generate all reports via the engine."""
        from src.reporting.report_engine import ReportEngine
        engine = ReportEngine(entity_name="Test G-SIB", rssd_id="12345")
        package = engine.generate_all(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            credit_risk_items=credit_risk_items,
            market_risk_input=market_risk_input,
            indicator_values=gsib_indicator_values,
            stress_projections=stress_projections,
        )
        assert package.fr_y9c is not None
        assert package.ffiec_101 is not None
        assert package.fr_y15 is not None
        assert package.fr_y14 is not None
        assert len(package.reports_generated) == 4

    def test_cross_validation(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        credit_risk_items: list[CreditRiskRWAItem],
        reporting_date: date,
    ) -> None:
        """Cross-validation between Y-9C and FFIEC 101."""
        from src.reporting.report_engine import ReportEngine
        engine = ReportEngine(entity_name="Test G-SIB")
        package = engine.generate_all(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            credit_risk_items=credit_risk_items,
        )
        # Cross-validation should include RWA comparison
        xval = package.cross_validation
        assert xval.total_checks > 0
        # Total RWA should match between Y-9C and FFIEC 101
        rwa_check = [
            c for c in xval.checks
            if "Total RWA" in c.check_name
        ]
        assert len(rwa_check) > 0

    def test_bcbs_239_lineage(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """BCBS 239 lineage trail is populated."""
        from src.reporting.report_engine import ReportEngine
        engine = ReportEngine(entity_name="Test G-SIB")
        package = engine.generate_all(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        assert package.lineage.total_operations > 0
        assert len(package.lineage.entries) > 0

    def test_engine_handles_partial_inputs(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        reporting_date: date,
    ) -> None:
        """Engine generates only Y-9C when no other inputs provided."""
        from src.reporting.report_engine import ReportEngine
        engine = ReportEngine(entity_name="Test G-SIB")
        package = engine.generate_all(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
        )
        assert package.fr_y9c is not None
        assert package.ffiec_101 is None
        assert package.fr_y15 is None
        assert package.fr_y14 is None
        assert "FR_Y_9C" in package.reports_generated

    def test_overall_data_quality(
        self, total_capital: TotalCapitalResult,
        capital_adequacy: CapitalAdequacyResult,
        rwa_breakdown: RWABreakdown,
        credit_risk_items: list[CreditRiskRWAItem],
        gsib_indicator_values: dict[str, float],
        stress_projections: dict[str, list[dict[str, float]]],
        reporting_date: date,
    ) -> None:
        """Overall quality aggregation works correctly."""
        from src.reporting.report_engine import ReportEngine
        engine = ReportEngine(entity_name="Test G-SIB")
        package = engine.generate_all(
            capital=total_capital,
            adequacy=capital_adequacy,
            rwa_breakdown=rwa_breakdown,
            reporting_date=reporting_date,
            credit_risk_items=credit_risk_items,
            indicator_values=gsib_indicator_values,
            stress_projections=stress_projections,
        )
        # With valid data, overall quality should pass
        assert package.overall_data_quality_pass is True
