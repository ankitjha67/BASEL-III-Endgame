"""Unit tests for reference data module — counterparty, instrument, and regulatory lookups.

Tests cover:
- CounterpartyType and CounterpartyRecord creation/validation
- CounterpartyRegistry add/retrieve/filter operations
- SA-CCR alpha assignment (1.4 financial vs 1.0 commercial)
- Counterparty classification hierarchy
- InstrumentType classification (derivative, SFT, securitization)
- Book classification with FRTB threshold ($5B)
- Sovereign risk weights by CRC category
- Residential mortgage and CRE risk weights by LTV
- Corporate IG (65%), retail transactor (45%), MSA (250%) risk weights

References:
    - ERBA NPR pp. 100-160: SA-CR risk weight tables
    - 12 CFR 217.32: Risk-weighted assets
    - Dodd-Frank Section 939A: No external ratings for corporates
"""

import pytest
from pydantic import ValidationError

from src.reference_data.counterparty_reference import (
    CounterpartyRecord,
    CounterpartyRegistry,
    CounterpartyType,
    DomicileRegion,
    IndustryClassification,
    NettingSet,
    SovereignRiskCategory,
    classify_counterparty_type,
    get_sa_ccr_alpha,
)
from src.reference_data.instrument_reference import (
    BookClassification,
    InstrumentRecord,
    InstrumentType,
    SACCRAssetClass,
    classify_book,
    get_saccr_asset_class,
    is_derivative,
    is_securitization,
    is_sft,
)
from src.reference_data.regulatory_lookups import (
    SA_CR_RISK_WEIGHTS,
    SOVEREIGN_RISK_WEIGHTS,
    get_risk_weight,
)


# =========================================================================
#  Counterparty Reference Tests
# =========================================================================


class TestCounterpartyType:
    """Tests for CounterpartyType enum completeness."""

    def test_counterparty_type_count(self) -> None:
        """CounterpartyType has 21 members per ERBA NPR classification."""
        assert len(CounterpartyType) == 21

    def test_key_types_exist(self) -> None:
        """Critical counterparty types are defined."""
        assert CounterpartyType.SOVEREIGN.value == "SOVEREIGN"
        assert CounterpartyType.CORPORATE_IG.value == "CORPORATE_IG"
        assert CounterpartyType.RETAIL_TRANSACTOR.value == "RETAIL_TRANSACTOR"
        assert CounterpartyType.MSA.value == "MSA"
        assert CounterpartyType.DEFAULTED.value == "DEFAULTED"


class TestCounterpartyRecord:
    """Tests for CounterpartyRecord Pydantic model."""

    def test_create_valid_counterparty(self) -> None:
        """Create a corporate counterparty with all fields."""
        cp = CounterpartyRecord(
            counterparty_id="CP-001",
            name="Acme Corp",
            counterparty_type=CounterpartyType.CORPORATE_IG,
            is_investment_grade=True,
            exposure_amount_mm=500.0,
        )
        assert cp.counterparty_id == "CP-001"
        assert cp.counterparty_type == CounterpartyType.CORPORATE_IG
        assert cp.is_investment_grade is True

    def test_lei_validation_valid(self) -> None:
        """LEI must be exactly 20 characters."""
        cp = CounterpartyRecord(
            counterparty_id="CP-002",
            name="Test Bank",
            counterparty_type=CounterpartyType.BANK,
            lei="12345678901234567890",
        )
        assert cp.lei == "12345678901234567890"

    def test_lei_validation_invalid(self) -> None:
        """LEI with wrong length raises ValidationError."""
        with pytest.raises(ValidationError):
            CounterpartyRecord(
                counterparty_id="CP-003",
                name="Bad LEI",
                counterparty_type=CounterpartyType.BANK,
                lei="SHORT",
            )

    def test_negative_revenue_rejected(self) -> None:
        """Annual revenue must be non-negative."""
        with pytest.raises(ValidationError):
            CounterpartyRecord(
                counterparty_id="CP-004",
                name="Negative Rev",
                counterparty_type=CounterpartyType.CORPORATE,
                annual_revenue_mm=-100.0,
            )


class TestCounterpartyRegistry:
    """Tests for CounterpartyRegistry operations."""

    @pytest.fixture
    def registry(self) -> CounterpartyRegistry:
        """Create a registry with a few counterparties."""
        reg = CounterpartyRegistry()
        reg.add_counterparty(CounterpartyRecord(
            counterparty_id="SOV-001",
            name="US Treasury",
            counterparty_type=CounterpartyType.SOVEREIGN,
            exposure_amount_mm=500_000.0,
        ))
        reg.add_counterparty(CounterpartyRecord(
            counterparty_id="BANK-001",
            name="JPM",
            counterparty_type=CounterpartyType.BANK,
            is_financial=True,
            exposure_amount_mm=10_000.0,
        ))
        reg.add_counterparty(CounterpartyRecord(
            counterparty_id="CORP-001",
            name="Apple Inc",
            counterparty_type=CounterpartyType.CORPORATE_IG,
            is_investment_grade=True,
            exposure_amount_mm=5_000.0,
        ))
        return reg

    def test_add_and_retrieve(self, registry: CounterpartyRegistry) -> None:
        """Add counterparty and retrieve by ID."""
        cp = registry.get_counterparty("SOV-001")
        assert cp.name == "US Treasury"

    def test_count(self, registry: CounterpartyRegistry) -> None:
        """Registry count matches added counterparties."""
        assert registry.count == 3

    def test_get_by_type(self, registry: CounterpartyRegistry) -> None:
        """Filter counterparties by type."""
        banks = registry.get_counterparties_by_type(CounterpartyType.BANK)
        assert len(banks) == 1
        assert banks[0].name == "JPM"

    def test_get_financial_counterparties(self, registry: CounterpartyRegistry) -> None:
        """Financial counterparties identified for SA-CCR alpha."""
        fin = registry.get_financial_counterparties()
        assert len(fin) == 1
        assert fin[0].counterparty_id == "BANK-001"

    def test_total_exposure(self, registry: CounterpartyRegistry) -> None:
        """Total exposure across all counterparties."""
        assert registry.total_exposure_mm() == pytest.approx(515_000.0)

    def test_missing_counterparty_raises(self, registry: CounterpartyRegistry) -> None:
        """KeyError for non-existent counterparty."""
        with pytest.raises(KeyError):
            registry.get_counterparty("NONEXISTENT")

    def test_netting_set(self, registry: CounterpartyRegistry) -> None:
        """Add and retrieve netting set."""
        ns = NettingSet(
            netting_set_id="NS-001",
            counterparty_id="BANK-001",
            is_margined=True,
        )
        registry.add_netting_set(ns)
        retrieved = registry.get_netting_set("NS-001")
        assert retrieved.is_margined is True

    def test_netting_set_requires_counterparty(self, registry: CounterpartyRegistry) -> None:
        """Netting set for unknown counterparty raises ValueError."""
        with pytest.raises(ValueError):
            registry.add_netting_set(NettingSet(
                netting_set_id="NS-BAD",
                counterparty_id="DOES_NOT_EXIST",
            ))


class TestSACCRAlpha:
    """Tests for SA-CCR alpha multiplier assignment."""

    def test_financial_counterparty_alpha_14(self) -> None:
        """Financial counterparty -> alpha = 1.4 per ERBA NPR p.290."""
        cp = CounterpartyRecord(
            counterparty_id="FIN-001",
            name="Goldman",
            counterparty_type=CounterpartyType.BANK,
            is_financial=True,
        )
        assert get_sa_ccr_alpha(cp) == pytest.approx(1.4)

    def test_commercial_counterparty_alpha_10(self) -> None:
        """Commercial end-user -> alpha = 1.0."""
        cp = CounterpartyRecord(
            counterparty_id="COM-001",
            name="Ford Motor",
            counterparty_type=CounterpartyType.CORPORATE,
            is_financial=False,
        )
        assert get_sa_ccr_alpha(cp) == pytest.approx(1.0)


class TestCounterpartyClassification:
    """Tests for classify_counterparty_type function."""

    def test_defaulted_takes_priority(self) -> None:
        """Defaulted overrides all other classifications."""
        ct = classify_counterparty_type(is_sovereign=True, is_defaulted=True)
        assert ct == CounterpartyType.DEFAULTED

    def test_sovereign(self) -> None:
        """Sovereign classification."""
        ct = classify_counterparty_type(is_sovereign=True)
        assert ct == CounterpartyType.SOVEREIGN

    def test_corporate_ig_self_assessment(self) -> None:
        """Corporate IG via self-assessment (no external rating per Dodd-Frank 939A)."""
        ct = classify_counterparty_type(is_investment_grade=True)
        assert ct == CounterpartyType.CORPORATE_IG

    def test_sme_by_revenue(self) -> None:
        """SME classification when revenue <= EUR 50M (~$55M)."""
        ct = classify_counterparty_type(annual_revenue_mm=40.0)
        assert ct == CounterpartyType.SME

    def test_general_corporate(self) -> None:
        """General corporate: not IG, not SME."""
        ct = classify_counterparty_type()
        assert ct == CounterpartyType.CORPORATE


# =========================================================================
#  Instrument Reference Tests
# =========================================================================


class TestInstrumentType:
    """Tests for InstrumentType enum."""

    def test_instrument_type_count(self) -> None:
        """InstrumentType has 32 members."""
        assert len(InstrumentType) == 32

    def test_derivative_identification(self) -> None:
        """Derivative types correctly identified."""
        assert is_derivative(InstrumentType.IRS) is True
        assert is_derivative(InstrumentType.CDS) is True
        assert is_derivative(InstrumentType.FX_OPTION) is True
        assert is_derivative(InstrumentType.LOAN) is False
        assert is_derivative(InstrumentType.BOND) is False

    def test_sft_identification(self) -> None:
        """SFT types correctly identified."""
        assert is_sft(InstrumentType.REPO) is True
        assert is_sft(InstrumentType.REVERSE_REPO) is True
        assert is_sft(InstrumentType.SECURITIES_LENDING) is True
        assert is_sft(InstrumentType.MARGIN_LOAN) is True
        assert is_sft(InstrumentType.LOAN) is False

    def test_securitization_identification(self) -> None:
        """Securitization types correctly identified."""
        assert is_securitization(InstrumentType.RMBS) is True
        assert is_securitization(InstrumentType.CLO) is True
        assert is_securitization(InstrumentType.RESECURITIZATION) is True
        assert is_securitization(InstrumentType.BOND) is False

    def test_saccr_asset_class_mapping(self) -> None:
        """SA-CCR asset class mapping for derivatives."""
        assert get_saccr_asset_class(InstrumentType.IRS) == SACCRAssetClass.INTEREST_RATE
        assert get_saccr_asset_class(InstrumentType.FX_FORWARD) == SACCRAssetClass.FOREIGN_EXCHANGE
        assert get_saccr_asset_class(InstrumentType.CDS) == SACCRAssetClass.CREDIT
        assert get_saccr_asset_class(InstrumentType.EQUITY_OPTION) == SACCRAssetClass.EQUITY
        assert get_saccr_asset_class(InstrumentType.COMMODITY_FORWARD) == SACCRAssetClass.COMMODITY
        assert get_saccr_asset_class(InstrumentType.LOAN) is None


class TestBookClassification:
    """Tests for trading/banking book assignment."""

    def test_trading_book_when_traded(self) -> None:
        """Traded instrument above FRTB threshold goes to trading book."""
        inst = InstrumentRecord(
            instrument_id="INST-001",
            instrument_type=InstrumentType.IRS,
            notional_mm=100.0,
            is_traded=True,
        )
        book = classify_book(inst, trading_activity_4q_avg_mm=10_000.0)
        assert book == BookClassification.TRADING_BOOK

    def test_banking_book_below_frtb_threshold(self) -> None:
        """Below $5B FRTB threshold -> all banking book."""
        inst = InstrumentRecord(
            instrument_id="INST-002",
            instrument_type=InstrumentType.IRS,
            notional_mm=100.0,
            is_traded=True,
        )
        book = classify_book(inst, trading_activity_4q_avg_mm=3_000.0)
        assert book == BookClassification.BANKING_BOOK

    def test_banking_book_not_traded(self) -> None:
        """Non-traded instrument defaults to banking book."""
        inst = InstrumentRecord(
            instrument_id="INST-003",
            instrument_type=InstrumentType.LOAN,
            notional_mm=1000.0,
            is_traded=False,
        )
        book = classify_book(inst, trading_activity_4q_avg_mm=10_000.0)
        assert book == BookClassification.BANKING_BOOK

    def test_currency_validation(self) -> None:
        """Currency must be 3-letter ISO 4217."""
        with pytest.raises(ValidationError):
            InstrumentRecord(
                instrument_id="INST-004",
                instrument_type=InstrumentType.BOND,
                notional_mm=100.0,
                currency="US",
            )

    def test_ltv_validation(self) -> None:
        """LTV ratio must be 0-2.0."""
        with pytest.raises(ValidationError):
            InstrumentRecord(
                instrument_id="INST-005",
                instrument_type=InstrumentType.LOAN,
                notional_mm=100.0,
                ltv_ratio=3.0,
            )


# =========================================================================
#  Regulatory Lookups Tests
# =========================================================================


class TestSovereignRiskWeights:
    """Tests for sovereign risk weight lookup by CRC category."""

    def test_crc_0_1_zero_rw(self) -> None:
        """CRC 0-1 (US, G7): 0% risk weight."""
        rw = get_risk_weight(CounterpartyType.SOVEREIGN,
                             sovereign_risk_category=SovereignRiskCategory.CRC_0_1)
        assert rw == pytest.approx(0.0)

    def test_crc_2_twenty_rw(self) -> None:
        """CRC 2: 20% risk weight."""
        rw = get_risk_weight(CounterpartyType.SOVEREIGN,
                             sovereign_risk_category=SovereignRiskCategory.CRC_2)
        assert rw == pytest.approx(0.20)

    def test_crc_3_fifty_rw(self) -> None:
        """CRC 3: 50% risk weight."""
        rw = get_risk_weight(CounterpartyType.SOVEREIGN,
                             sovereign_risk_category=SovereignRiskCategory.CRC_3)
        assert rw == pytest.approx(0.50)

    def test_crc_4_6_hundred_rw(self) -> None:
        """CRC 4-6: 100% risk weight."""
        rw = get_risk_weight(CounterpartyType.SOVEREIGN,
                             sovereign_risk_category=SovereignRiskCategory.CRC_4_6)
        assert rw == pytest.approx(1.00)

    def test_crc_7_hundred_fifty_rw(self) -> None:
        """CRC 7: 150% risk weight."""
        rw = get_risk_weight(CounterpartyType.SOVEREIGN,
                             sovereign_risk_category=SovereignRiskCategory.CRC_7)
        assert rw == pytest.approx(1.50)

    def test_us_sovereign_default(self) -> None:
        """US sovereign without CRC category defaults to 0%."""
        rw = get_risk_weight(CounterpartyType.SOVEREIGN)
        assert rw == pytest.approx(0.0)


class TestResidentialMortgageRW:
    """Tests for residential mortgage risk weights by LTV per ERBA NPR Table 3."""

    def test_ltv_below_50(self) -> None:
        """LTV <= 50%: 20% RW."""
        rw = get_risk_weight(CounterpartyType.RETAIL_MORTGAGE, ltv_ratio=0.45)
        assert rw == pytest.approx(0.20)

    def test_ltv_60(self) -> None:
        """50% < LTV <= 60%: 25% RW."""
        rw = get_risk_weight(CounterpartyType.RETAIL_MORTGAGE, ltv_ratio=0.55)
        assert rw == pytest.approx(0.25)

    def test_ltv_80(self) -> None:
        """70% < LTV <= 80%: 40% RW."""
        rw = get_risk_weight(CounterpartyType.RETAIL_MORTGAGE, ltv_ratio=0.75)
        assert rw == pytest.approx(0.40)

    def test_ltv_above_100(self) -> None:
        """LTV > 100%: 100% RW (whole-loan approach)."""
        rw = get_risk_weight(CounterpartyType.RETAIL_MORTGAGE, ltv_ratio=1.10)
        assert rw == pytest.approx(1.00)


class TestCRERiskWeights:
    """Tests for CRE risk weights by LTV per ERBA NPR Table 4."""

    def test_cre_ltv_below_60(self) -> None:
        """CRE LTV <= 60%: 70% RW."""
        rw = get_risk_weight(CounterpartyType.CRE, ltv_ratio=0.50)
        assert rw == pytest.approx(0.70)

    def test_cre_ltv_70(self) -> None:
        """CRE 60% < LTV <= 80%: 90% RW."""
        rw = get_risk_weight(CounterpartyType.CRE, ltv_ratio=0.70)
        assert rw == pytest.approx(0.90)

    def test_cre_ltv_above_80(self) -> None:
        """CRE LTV > 80%: 110% RW."""
        rw = get_risk_weight(CounterpartyType.CRE, ltv_ratio=0.90)
        assert rw == pytest.approx(1.10)


class TestCriticalRiskWeights:
    """Tests for critical regulatory risk weights per CLAUDE.md."""

    def test_corporate_ig_65_percent(self) -> None:
        """Corporate IG = 65% (self-assessment per Dodd-Frank 939A)."""
        rw = get_risk_weight(CounterpartyType.CORPORATE_IG)
        assert rw == pytest.approx(0.65)

    def test_retail_transactor_45_percent(self) -> None:
        """Retail transactor = 45% (NOT 55% from 2023 NPR)."""
        rw = get_risk_weight(CounterpartyType.RETAIL_TRANSACTOR)
        assert rw == pytest.approx(0.45)

    def test_msa_250_percent(self) -> None:
        """MSA = 250% RW (deduction removed per 2026 re-proposal)."""
        rw = get_risk_weight(CounterpartyType.MSA)
        assert rw == pytest.approx(2.50)

    def test_adc_150_percent(self) -> None:
        """ADC = 150% RW per ERBA NPR p.145."""
        rw = get_risk_weight(CounterpartyType.ADC)
        assert rw == pytest.approx(1.50)

    def test_defaulted_150_percent(self) -> None:
        """Defaulted = 150% RW per 12 CFR 217.32(k)."""
        rw = get_risk_weight(CounterpartyType.DEFAULTED)
        assert rw == pytest.approx(1.50)

    def test_qualifying_ccp_2_percent(self) -> None:
        """Qualifying CCP = 2% RW per 12 CFR 217.35."""
        rw = get_risk_weight(CounterpartyType.CCP_QUALIFYING)
        assert rw == pytest.approx(0.02)
