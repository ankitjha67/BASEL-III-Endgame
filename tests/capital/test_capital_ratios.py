"""Tests for Capital Ratio calculator.

Tests CET1 ratio, Tier 1 ratio, Total Capital ratio, SLR,
PCA classification, and buffer requirements.

References:
- 12 CFR 217.10: Minimum capital ratios
- 12 CFR 217.11: Capital buffers
- 12 CFR 6.4: Prompt Corrective Action
"""

import pytest

from src.capital.capital_ratios import (
    BufferZone,
    CapitalAdequacyResult,
    CapitalRatios,
    PCACategory,
    compute_buffer_requirements,
    compute_capital_adequacy,
    compute_capital_ratios,
    classify_pca,
)
from src.capital.capital_params import (
    CCB_RATE,
    CET1_MINIMUM_RATIO,
    TIER1_MINIMUM_RATIO,
    TOTAL_CAPITAL_MINIMUM_RATIO,
)


# =========================================================================
#  Fixtures — realistic Category I G-SIB
# =========================================================================

# $3.2T balance sheet, ~$1.7T RWA, CET1 ~12%
REALISTIC_CET1 = 195_000.0    # $195B
REALISTIC_TIER1 = 220_000.0   # $220B
REALISTIC_TOTAL = 250_000.0   # $250B
REALISTIC_RWA = 1_650_000.0   # $1.65T RWA
REALISTIC_TLE = 3_500_000.0   # $3.5T leverage exposure


class TestComputeCapitalRatios:
    """Tests for compute_capital_ratios function."""

    def test_basic_ratio_calculation(self) -> None:
        """Basic capital ratio = capital / RWA."""
        ratios = compute_capital_ratios(
            cet1_capital=100.0,
            tier1_capital=120.0,
            total_capital=150.0,
            total_rwa=1000.0,
        )
        assert ratios.cet1_ratio == pytest.approx(0.10)
        assert ratios.tier1_ratio == pytest.approx(0.12)
        assert ratios.total_capital_ratio == pytest.approx(0.15)

    def test_slr_calculation(self) -> None:
        """SLR = Tier 1 / Total Leverage Exposure."""
        ratios = compute_capital_ratios(
            cet1_capital=REALISTIC_CET1,
            tier1_capital=REALISTIC_TIER1,
            total_capital=REALISTIC_TOTAL,
            total_rwa=REALISTIC_RWA,
            total_leverage_exposure=REALISTIC_TLE,
        )
        expected_slr = REALISTIC_TIER1 / REALISTIC_TLE
        assert ratios.leverage_ratio == pytest.approx(expected_slr)
        # SLR for large G-SIB should be in 5-7% range
        assert 0.05 <= ratios.leverage_ratio <= 0.08

    def test_realistic_gsib_ratios(self) -> None:
        """CET1 ratio for a Category I G-SIB should be 10-15%."""
        ratios = compute_capital_ratios(
            cet1_capital=REALISTIC_CET1,
            tier1_capital=REALISTIC_TIER1,
            total_capital=REALISTIC_TOTAL,
            total_rwa=REALISTIC_RWA,
        )
        assert 0.10 <= ratios.cet1_ratio <= 0.15
        assert ratios.tier1_ratio > ratios.cet1_ratio
        assert ratios.total_capital_ratio > ratios.tier1_ratio

    def test_zero_rwa_handling(self) -> None:
        """Zero RWA should not cause division errors."""
        ratios = compute_capital_ratios(
            cet1_capital=100.0,
            tier1_capital=120.0,
            total_capital=150.0,
            total_rwa=0.0,
        )
        # Implementation may return 0, inf, or raise — just ensure no crash
        assert ratios is not None


class TestPCAClassification:
    """Tests for Prompt Corrective Action classification per 12 CFR 6.4."""

    def test_well_capitalized(self) -> None:
        """Well capitalized: CET1 >= 6.5%, T1 >= 8%, Total >= 10%, SLR >= 5%."""
        result = classify_pca(
            cet1_ratio=0.12,
            tier1_ratio=0.14,
            total_capital_ratio=0.16,
            leverage_ratio=0.065,
        )
        assert result.category == PCACategory.WELL_CAPITALIZED

    def test_adequately_capitalized(self) -> None:
        """Adequately capitalized: meets minimums but not well-capitalized."""
        result = classify_pca(
            cet1_ratio=0.05,   # Above 4.5% min but below 6.5% WC
            tier1_ratio=0.065,
            total_capital_ratio=0.09,
            leverage_ratio=0.04,
        )
        assert result.category == PCACategory.ADEQUATELY_CAPITALIZED

    def test_undercapitalized(self) -> None:
        """Undercapitalized: fails any minimum ratio."""
        result = classify_pca(
            cet1_ratio=0.03,  # Below 4.5% minimum
            tier1_ratio=0.04,
            total_capital_ratio=0.06,
            leverage_ratio=0.02,
        )
        assert result.category in (
            PCACategory.UNDERCAPITALIZED,
            PCACategory.SIGNIFICANTLY_UNDERCAPITALIZED,
            PCACategory.CRITICALLY_UNDERCAPITALIZED,
        )


class TestCapitalAdequacy:
    """Tests for compute_capital_adequacy end-to-end."""

    def test_meets_all_requirements(self) -> None:
        """Well-capitalized G-SIB meets all minimum and buffer requirements."""
        result = compute_capital_adequacy(
            cet1_capital=REALISTIC_CET1,
            tier1_capital=REALISTIC_TIER1,
            total_capital=REALISTIC_TOTAL,
            total_rwa=REALISTIC_RWA,
            total_leverage_exposure=REALISTIC_TLE,
            gsib_surcharge=0.035,  # 3.5% G-SIB surcharge
        )
        assert result.meets_minimum_requirements is True
        assert result.is_well_capitalized is True
        assert result.ratios.cet1_ratio > CET1_MINIMUM_RATIO

    def test_buffer_components(self) -> None:
        """Buffer requirements include CCB, CCyB, and G-SIB surcharge."""
        result = compute_capital_adequacy(
            cet1_capital=REALISTIC_CET1,
            tier1_capital=REALISTIC_TIER1,
            total_capital=REALISTIC_TOTAL,
            total_rwa=REALISTIC_RWA,
            gsib_surcharge=0.025,
        )
        buffers = result.buffers
        assert buffers.capital_conservation_buffer >= CCB_RATE
        assert buffers.gsib_surcharge == pytest.approx(0.025)
        assert buffers.combined_buffer_requirement >= CCB_RATE + 0.025
