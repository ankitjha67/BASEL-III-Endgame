"""Tests for OBS/CCF — Off-Balance Sheet Credit Conversion Factors.

Validates CCF values, credit-equivalent amount computation, and
integration with SA-CR risk weights per 12 CFR 217.33 and
BCBS d424 CRE20.69-20.93.
"""

from __future__ import annotations

import pytest

from src.credit_risk.sa.obs_ccf import (
    OBSCategory,
    OBSCCFCalculator,
    OBSExposure,
    OBSResult,
)


# =========================================================================
#  Fixtures
# =========================================================================

@pytest.fixture
def calculator() -> OBSCCFCalculator:
    """Create a fresh OBS CCF calculator instance."""
    return OBSCCFCalculator()


def _make_exposure(
    exposure_id: str = "OBS-001",
    obs_category: OBSCategory = OBSCategory.COMMITMENT_GT_1Y,
    notional_amount: float = 100.0,
    drawn_amount: float = 0.0,
    original_maturity_years: float = 2.0,
    is_unconditionally_cancellable: bool = False,
    counterparty_id: str | None = None,
    exposure_class: str | None = None,
) -> OBSExposure:
    """Helper to create an OBSExposure with sensible defaults."""
    return OBSExposure(
        exposure_id=exposure_id,
        obs_category=obs_category,
        notional_amount=notional_amount,
        drawn_amount=drawn_amount,
        original_maturity_years=original_maturity_years,
        is_unconditionally_cancellable=is_unconditionally_cancellable,
        counterparty_id=counterparty_id,
        exposure_class=exposure_class,
    )


# =========================================================================
#  CCF Value Tests — One per Category (12 tests)
#  Verify all CCF values match 12 CFR 217.33
# =========================================================================

class TestCCFValues:
    """Verify CCF values for each OBS category per 12 CFR 217.33."""

    def test_ccf_ucc(self, calculator: OBSCCFCalculator) -> None:
        """UCC (unconditionally cancellable commitments) = 10%.
        Per 12 CFR 217.33(b) and BCBS d424 CRE20.71.
        """
        assert calculator.get_ccf(OBSCategory.UCC) == 0.10

    def test_ccf_trade_lc(self, calculator: OBSCCFCalculator) -> None:
        """Short-term trade letters of credit = 20%.
        Per 12 CFR 217.33(c) and BCBS d424 CRE20.72.
        """
        assert calculator.get_ccf(OBSCategory.TRADE_LC) == 0.20

    def test_ccf_transaction_contingency(self, calculator: OBSCCFCalculator) -> None:
        """Transaction-related contingencies = 50%.
        Per 12 CFR 217.33(d) and BCBS d424 CRE20.73.
        """
        assert calculator.get_ccf(OBSCategory.TRANSACTION_CONTINGENCY) == 0.50

    def test_ccf_nif(self, calculator: OBSCCFCalculator) -> None:
        """Note issuance facilities = 50%.
        Per 12 CFR 217.33(d) and BCBS d424 CRE20.74.
        """
        assert calculator.get_ccf(OBSCategory.NIF) == 0.50

    def test_ccf_ruf(self, calculator: OBSCCFCalculator) -> None:
        """Revolving underwriting facilities = 50%.
        Per 12 CFR 217.33(d) and BCBS d424 CRE20.74.
        """
        assert calculator.get_ccf(OBSCategory.RUF) == 0.50

    def test_ccf_commitment_gt_1y(self, calculator: OBSCCFCalculator) -> None:
        """Other commitments > 1 year = 40%.
        Per US Basel III Endgame 2026 Re-Proposal (reduced from 50%).
        BCBS d424 CRE20.75.
        """
        assert calculator.get_ccf(OBSCategory.COMMITMENT_GT_1Y) == 0.40

    def test_ccf_commitment_le_1y(self, calculator: OBSCCFCalculator) -> None:
        """Other commitments <= 1 year = 20%.
        Per 12 CFR 217.33(e) and BCBS d424 CRE20.76.
        """
        assert calculator.get_ccf(OBSCategory.COMMITMENT_LE_1Y) == 0.20

    def test_ccf_direct_credit_sub(self, calculator: OBSCCFCalculator) -> None:
        """Direct credit substitutes = 100%.
        Per 12 CFR 217.33(f) and BCBS d424 CRE20.77.
        """
        assert calculator.get_ccf(OBSCategory.DIRECT_CREDIT_SUB) == 1.00

    def test_ccf_forward_purchase(self, calculator: OBSCCFCalculator) -> None:
        """Forward asset purchases = 100%.
        Per 12 CFR 217.33(f) and BCBS d424 CRE20.78.
        """
        assert calculator.get_ccf(OBSCategory.FORWARD_PURCHASE) == 1.00

    def test_ccf_repo_style(self, calculator: OBSCCFCalculator) -> None:
        """Repo-style transactions = 100%.
        Per 12 CFR 217.33(f) and BCBS d424 CRE20.79.
        """
        assert calculator.get_ccf(OBSCategory.REPO_STYLE) == 1.00

    def test_ccf_sec_lending(self, calculator: OBSCCFCalculator) -> None:
        """Securities lending/borrowing = 100%.
        Per 12 CFR 217.33(f) and BCBS d424 CRE20.80.
        """
        assert calculator.get_ccf(OBSCategory.SEC_LENDING) == 1.00

    def test_ccf_acceptance(self, calculator: OBSCCFCalculator) -> None:
        """Banker's acceptances = 100%.
        Per 12 CFR 217.33(f) and BCBS d424 CRE20.81.
        """
        assert calculator.get_ccf(OBSCategory.ACCEPTANCE) == 1.00


# =========================================================================
#  Single Exposure Conversion Tests
# =========================================================================

class TestSingleConversion:
    """Test convert_single for individual OBS exposures."""

    def test_fully_undrawn_commitment_gt_1y(self, calculator: OBSCCFCalculator) -> None:
        """Fully undrawn > 1yr commitment: EAD = 0 + (100 x 0.40) = 40."""
        exp = _make_exposure(
            obs_category=OBSCategory.COMMITMENT_GT_1Y,
            notional_amount=100.0,
            drawn_amount=0.0,
        )
        result = calculator.convert_single(exp)
        assert result["ead"] == pytest.approx(40.0)
        assert result["undrawn"] == pytest.approx(100.0)
        assert result["ccf"] == 0.40

    def test_partially_drawn_commitment(self, calculator: OBSCCFCalculator) -> None:
        """Partially drawn commitment: EAD = 20 + (80 x 0.40) = 52."""
        exp = _make_exposure(
            obs_category=OBSCategory.COMMITMENT_GT_1Y,
            notional_amount=100.0,
            drawn_amount=20.0,
        )
        result = calculator.convert_single(exp)
        assert result["ead"] == pytest.approx(52.0)
        assert result["drawn"] == pytest.approx(20.0)
        assert result["undrawn"] == pytest.approx(80.0)

    def test_fully_drawn_exposure(self, calculator: OBSCCFCalculator) -> None:
        """Fully drawn exposure: EAD = notional (CCF on zero undrawn)."""
        exp = _make_exposure(
            obs_category=OBSCategory.COMMITMENT_GT_1Y,
            notional_amount=100.0,
            drawn_amount=100.0,
        )
        result = calculator.convert_single(exp)
        assert result["ead"] == pytest.approx(100.0)
        assert result["undrawn"] == pytest.approx(0.0)

    def test_direct_credit_sub_100pct(self, calculator: OBSCCFCalculator) -> None:
        """Direct credit substitute at 100% CCF: EAD = notional."""
        exp = _make_exposure(
            obs_category=OBSCategory.DIRECT_CREDIT_SUB,
            notional_amount=500.0,
            drawn_amount=0.0,
        )
        result = calculator.convert_single(exp)
        assert result["ead"] == pytest.approx(500.0)
        assert result["ccf"] == 1.00

    def test_ucc_10pct(self, calculator: OBSCCFCalculator) -> None:
        """UCC at 10% CCF: EAD = 0 + (200 x 0.10) = 20."""
        exp = _make_exposure(
            obs_category=OBSCategory.UCC,
            notional_amount=200.0,
            drawn_amount=0.0,
        )
        result = calculator.convert_single(exp)
        assert result["ead"] == pytest.approx(20.0)
        assert result["ccf"] == 0.10


# =========================================================================
#  UCC Flag Override Tests
# =========================================================================

class TestUCCOverride:
    """Test that is_unconditionally_cancellable overrides the stated category."""

    def test_ucc_flag_overrides_commitment_gt_1y(
        self, calculator: OBSCCFCalculator
    ) -> None:
        """A commitment > 1Y flagged as UCC should use 10% CCF, not 40%."""
        exp = _make_exposure(
            obs_category=OBSCategory.COMMITMENT_GT_1Y,
            notional_amount=100.0,
            is_unconditionally_cancellable=True,
        )
        result = calculator.convert_single(exp)
        assert result["effective_category"] == OBSCategory.UCC.value
        assert result["ccf"] == 0.10
        assert result["ead"] == pytest.approx(10.0)

    def test_ucc_flag_overrides_transaction_contingency(
        self, calculator: OBSCCFCalculator
    ) -> None:
        """A transaction contingency flagged as UCC should use 10%."""
        exp = _make_exposure(
            obs_category=OBSCategory.TRANSACTION_CONTINGENCY,
            notional_amount=100.0,
            is_unconditionally_cancellable=True,
        )
        result = calculator.convert_single(exp)
        assert result["effective_category"] == OBSCategory.UCC.value
        assert result["ccf"] == 0.10

    def test_no_ucc_flag_preserves_category(
        self, calculator: OBSCCFCalculator
    ) -> None:
        """Without UCC flag, stated category is preserved."""
        exp = _make_exposure(
            obs_category=OBSCategory.TRANSACTION_CONTINGENCY,
            notional_amount=100.0,
            is_unconditionally_cancellable=False,
        )
        result = calculator.convert_single(exp)
        assert result["effective_category"] == OBSCategory.TRANSACTION_CONTINGENCY.value
        assert result["ccf"] == 0.50


# =========================================================================
#  Maturity-Based Classification Tests
# =========================================================================

class TestMaturityClassification:
    """Test the classify_commitment_by_maturity helper."""

    def test_maturity_gt_1y(self, calculator: OBSCCFCalculator) -> None:
        """Commitment with maturity > 1 year -> COMMITMENT_GT_1Y."""
        cat = calculator.classify_commitment_by_maturity(2.5)
        assert cat == OBSCategory.COMMITMENT_GT_1Y

    def test_maturity_le_1y(self, calculator: OBSCCFCalculator) -> None:
        """Commitment with maturity <= 1 year -> COMMITMENT_LE_1Y."""
        cat = calculator.classify_commitment_by_maturity(0.5)
        assert cat == OBSCategory.COMMITMENT_LE_1Y

    def test_maturity_exactly_1y(self, calculator: OBSCCFCalculator) -> None:
        """Commitment with maturity exactly 1 year -> COMMITMENT_LE_1Y."""
        cat = calculator.classify_commitment_by_maturity(1.0)
        assert cat == OBSCategory.COMMITMENT_LE_1Y

    def test_maturity_ucc_override(self, calculator: OBSCCFCalculator) -> None:
        """UCC flag overrides maturity-based classification."""
        cat = calculator.classify_commitment_by_maturity(
            5.0, is_unconditionally_cancellable=True
        )
        assert cat == OBSCategory.UCC


# =========================================================================
#  Portfolio / Batch Calculation Tests
# =========================================================================

class TestPortfolioCalculation:
    """Test the calculate method with portfolios of OBS exposures."""

    def test_empty_portfolio(self, calculator: OBSCCFCalculator) -> None:
        """Empty input returns zero-valued result."""
        result = calculator.calculate([])
        assert result.total_notional == 0.0
        assert result.total_ead == 0.0
        assert result.total_rwa == 0.0
        assert len(result.details) == 0

    def test_mixed_portfolio(self, calculator: OBSCCFCalculator) -> None:
        """Mixed portfolio aggregates correctly across categories."""
        exposures = [
            _make_exposure(
                exposure_id="OBS-001",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=100.0,
                drawn_amount=20.0,
            ),
            _make_exposure(
                exposure_id="OBS-002",
                obs_category=OBSCategory.DIRECT_CREDIT_SUB,
                notional_amount=50.0,
                drawn_amount=0.0,
            ),
            _make_exposure(
                exposure_id="OBS-003",
                obs_category=OBSCategory.UCC,
                notional_amount=200.0,
                drawn_amount=0.0,
            ),
        ]
        result = calculator.calculate(exposures)

        # OBS-001: 20 + (80 x 0.40) = 52
        # OBS-002: 0 + (50 x 1.00) = 50
        # OBS-003: 0 + (200 x 0.10) = 20
        assert result.total_notional == pytest.approx(350.0)
        assert result.total_drawn == pytest.approx(20.0)
        assert result.total_undrawn == pytest.approx(330.0)
        assert result.total_ead == pytest.approx(122.0)
        assert len(result.details) == 3

    def test_category_aggregation(self, calculator: OBSCCFCalculator) -> None:
        """Multiple exposures in same category aggregate correctly."""
        exposures = [
            _make_exposure(
                exposure_id="OBS-A",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=100.0,
            ),
            _make_exposure(
                exposure_id="OBS-B",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=200.0,
            ),
        ]
        result = calculator.calculate(exposures)

        cat_data = result.exposures_by_category.get(OBSCategory.COMMITMENT_GT_1Y.value)
        assert cat_data is not None
        assert cat_data["count"] == 2
        assert cat_data["notional"] == pytest.approx(300.0)
        assert cat_data["ead"] == pytest.approx(120.0)  # 300 x 0.40
        assert cat_data["ccf"] == 0.40

    def test_portfolio_with_risk_weights(self, calculator: OBSCCFCalculator) -> None:
        """Portfolio calculation with risk weight function produces RWA."""
        exposures = [
            _make_exposure(
                exposure_id="OBS-RW1",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=100.0,
                drawn_amount=0.0,
            ),
        ]

        def rw_func(exp: OBSExposure) -> float:
            return 0.65  # Investment-grade corporate

        result = calculator.calculate(exposures, risk_weight_func=rw_func)

        # EAD = 100 x 0.40 = 40
        # RWA = 40 x 0.65 = 26
        assert result.total_ead == pytest.approx(40.0)
        assert result.total_rwa == pytest.approx(26.0)

    def test_portfolio_without_risk_weights(self, calculator: OBSCCFCalculator) -> None:
        """Without risk weight function, RWA should be 0."""
        exposures = [
            _make_exposure(
                exposure_id="OBS-NRW",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=100.0,
            ),
        ]
        result = calculator.calculate(exposures, risk_weight_func=None)
        assert result.total_rwa == 0.0


# =========================================================================
#  Edge Cases
# =========================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_notional(self, calculator: OBSCCFCalculator) -> None:
        """Zero notional exposure produces zero EAD."""
        exp = _make_exposure(
            obs_category=OBSCategory.COMMITMENT_GT_1Y,
            notional_amount=0.0,
            drawn_amount=0.0,
        )
        result = calculator.convert_single(exp)
        assert result["ead"] == pytest.approx(0.0)
        assert result["undrawn"] == pytest.approx(0.0)

    def test_drawn_exceeds_notional_raises(self) -> None:
        """Drawn > notional should raise validation error."""
        with pytest.raises(ValueError, match="cannot exceed"):
            _make_exposure(
                notional_amount=100.0,
                drawn_amount=150.0,
            )

    def test_negative_notional_raises(self) -> None:
        """Negative notional should raise validation error."""
        with pytest.raises(ValueError):
            _make_exposure(notional_amount=-50.0)

    def test_all_categories_in_ccf_table(self, calculator: OBSCCFCalculator) -> None:
        """Every OBSCategory enum value has a CCF entry."""
        for category in OBSCategory:
            ccf = calculator.get_ccf(category)
            assert 0.0 <= ccf <= 1.0, (
                f"CCF for {category.value} is {ccf}, expected 0-1"
            )


# =========================================================================
#  Drawn + Undrawn Decomposition
# =========================================================================

class TestDrawnUndrawnDecomposition:
    """Verify correct decomposition of notional into drawn + undrawn."""

    def test_decomposition_basic(self, calculator: OBSCCFCalculator) -> None:
        """drawn + undrawn = notional."""
        exp = _make_exposure(
            notional_amount=150.0,
            drawn_amount=37.5,
        )
        result = calculator.convert_single(exp)
        assert result["drawn"] + result["undrawn"] == pytest.approx(150.0)

    def test_ead_formula(self, calculator: OBSCCFCalculator) -> None:
        """EAD = drawn + undrawn x CCF for various drawn levels."""
        for drawn in [0.0, 25.0, 50.0, 75.0, 100.0]:
            exp = _make_exposure(
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=100.0,
                drawn_amount=drawn,
            )
            result = calculator.convert_single(exp)
            expected_ead = drawn + (100.0 - drawn) * 0.40
            assert result["ead"] == pytest.approx(expected_ead), (
                f"Failed for drawn={drawn}"
            )


# =========================================================================
#  Integration with SA-CR Calculator
# =========================================================================

class TestSACRIntegration:
    """Test integration of OBS/CCF with the SA-CR calculator."""

    def test_calculate_with_obs(self) -> None:
        """SACRCalculator.calculate_with_obs combines on- and off-balance sheet."""
        from src.credit_risk.sa.calculator import (
            CreditExposure,
            SACRCalculator,
        )
        from src.credit_risk.sa.exposure_classes import ExposureClass

        calc = SACRCalculator()

        on_balance = [
            CreditExposure(
                exposure_id="ON-001",
                exposure_class=ExposureClass.CORPORATE,
                counterparty="CORP_A",
                ead=1000.0,
                is_investment_grade=True,
            ),
        ]

        obs = [
            _make_exposure(
                exposure_id="OBS-001",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=500.0,
                drawn_amount=100.0,
            ),
        ]

        result = calc.calculate_with_obs(on_balance, obs)

        # On-balance: 1000 x 0.65 = 650 RWA
        assert result["on_balance_result"].total_rwa == pytest.approx(650.0)

        # OBS: EAD = 100 + (400 x 0.40) = 260, RWA = 260 x 1.00 = 260
        assert result["obs_result"].total_ead == pytest.approx(260.0)

        # Combined
        assert result["combined_ead"] == pytest.approx(1260.0)
        assert result["combined_rwa"] == pytest.approx(910.0)
        assert result["combined_capital_requirement"] == pytest.approx(910.0 * 0.08)

    def test_calculate_with_obs_custom_rw_func(self) -> None:
        """calculate_with_obs with custom risk weight function."""
        from src.credit_risk.sa.calculator import (
            CreditExposure,
            SACRCalculator,
        )
        from src.credit_risk.sa.exposure_classes import ExposureClass

        calc = SACRCalculator()

        on_balance = [
            CreditExposure(
                exposure_id="ON-001",
                exposure_class=ExposureClass.CORPORATE,
                counterparty="CORP_A",
                ead=1000.0,
                is_investment_grade=True,
            ),
        ]

        obs = [
            _make_exposure(
                exposure_id="OBS-001",
                obs_category=OBSCategory.COMMITMENT_GT_1Y,
                notional_amount=500.0,
                drawn_amount=0.0,
            ),
        ]

        def obs_rw(exp: OBSExposure) -> float:
            return 0.65  # IG corporate

        result = calc.calculate_with_obs(on_balance, obs, obs_risk_weight_func=obs_rw)

        # OBS: EAD = 500 x 0.40 = 200, RWA = 200 x 0.65 = 130
        assert result["obs_result"].total_ead == pytest.approx(200.0)
        assert result["obs_result"].total_rwa == pytest.approx(130.0)
        assert result["combined_rwa"] == pytest.approx(650.0 + 130.0)

    def test_calculate_with_obs_empty_obs(self) -> None:
        """calculate_with_obs handles empty OBS list."""
        from src.credit_risk.sa.calculator import (
            CreditExposure,
            SACRCalculator,
        )
        from src.credit_risk.sa.exposure_classes import ExposureClass

        calc = SACRCalculator()

        on_balance = [
            CreditExposure(
                exposure_id="ON-001",
                exposure_class=ExposureClass.CORPORATE,
                counterparty="CORP_A",
                ead=1000.0,
            ),
        ]

        result = calc.calculate_with_obs(on_balance, [])
        assert result["obs_result"].total_ead == 0.0
        assert result["combined_rwa"] == pytest.approx(1000.0)


# =========================================================================
#  Data Model Validation Tests
# =========================================================================

class TestDataModelValidation:
    """Test OBSExposure Pydantic model validation."""

    def test_valid_exposure_creation(self) -> None:
        """Valid OBSExposure can be created."""
        exp = _make_exposure()
        assert exp.exposure_id == "OBS-001"
        assert exp.obs_category == OBSCategory.COMMITMENT_GT_1Y
        assert exp.notional_amount == 100.0

    def test_obs_category_enum_values(self) -> None:
        """All 12 OBS categories are defined."""
        assert len(OBSCategory) == 12

    def test_obs_result_defaults(self) -> None:
        """OBSResult with defaults has zero values."""
        result = OBSResult()
        assert result.total_notional == 0.0
        assert result.total_ead == 0.0
        assert result.total_rwa == 0.0
        assert result.details == []
