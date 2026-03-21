"""Tests for DRC Securitization Non-CTP and CTP calculators.

Covers:
- DRC Sec Non-CTP: single position, multiple positions, each rating,
  maturity scaling, defaulted positions, empty input, seniority impact.
- DRC Sec CTP: single position, netting within same tranche, hedge benefit
  calculation, multiple buckets, empty input.
- Edge cases: zero-value JTD, very short maturity, mixed seniorities.

Reference: BCBS d457 MAR22.24-22.46.
"""

from __future__ import annotations

import pytest

from src.core.enums import (
    DRCSecBucket,
    DRCSecCTPBucket,
    DRCSecRating,
    DRCSecSeniority,
)
from src.market_risk.frtb.drc.drc_params import (
    CTP_HEDGE_BENEFIT_RATIO,
    DRC_SEC_LGD,
    DRC_SEC_RISK_WEIGHTS_NON_SENIOR,
    DRC_SEC_RISK_WEIGHTS_SENIOR,
    get_sec_risk_weight,
)
from src.market_risk.frtb.drc.drc_sec_nonctp import (
    DRCSecNonCTPCalculator,
    DRCSecNonCTPPosition,
    DRCSecNonCTPResult,
)
from src.market_risk.frtb.drc.drc_sec_ctp import (
    DRCSecCTPCalculator,
    DRCSecCTPPosition,
    DRCSecCTPResult,
)


# =========================================================================
#  Helpers
# =========================================================================


def _nonctp_pos(
    tranche_id: str = "TRANCHE_A",
    deal_name: str = "DEAL_1",
    bucket: DRCSecBucket = DRCSecBucket.RMBS,
    rating: DRCSecRating = DRCSecRating.BBB,
    seniority: DRCSecSeniority = DRCSecSeniority.SENIOR,
    notional: float = 10_000_000.0,
    market_value: float = 9_800_000.0,
    maturity_years: float = 3.0,
    is_long: bool = True,
) -> DRCSecNonCTPPosition:
    return DRCSecNonCTPPosition(
        tranche_id=tranche_id,
        deal_name=deal_name,
        bucket=bucket,
        rating=rating,
        seniority=seniority,
        notional=notional,
        market_value=market_value,
        maturity_years=maturity_years,
        is_long=is_long,
    )


def _ctp_pos(
    tranche_id: str = "0-3",
    index_name: str = "CDX.NA.IG.42",
    bucket: DRCSecCTPBucket = DRCSecCTPBucket.INDEX_CDS,
    rating: DRCSecRating = DRCSecRating.BBB,
    seniority: DRCSecSeniority = DRCSecSeniority.SENIOR,
    notional: float = 10_000_000.0,
    market_value: float = 9_800_000.0,
    maturity_years: float = 3.0,
    is_long: bool = True,
) -> DRCSecCTPPosition:
    return DRCSecCTPPosition(
        tranche_id=tranche_id,
        index_name=index_name,
        bucket=bucket,
        rating=rating,
        seniority=seniority,
        notional=notional,
        market_value=market_value,
        maturity_years=maturity_years,
        is_long=is_long,
    )


# =========================================================================
#  DRC Sec Parameters Tests
# =========================================================================


class TestDRCSecParams:
    """Tests for DRC securitization regulatory parameters."""

    def test_sec_lgd_is_100_percent(self):
        """Per MAR22.26, LGD = 100% for all securitization positions."""
        assert DRC_SEC_LGD == 1.0

    def test_ctp_hedge_benefit_ratio(self):
        """Per MAR22.41, hedge benefit ratio = 50%."""
        assert CTP_HEDGE_BENEFIT_RATIO == 0.5

    def test_senior_rw_aaa(self):
        """AAA senior tranche = 0.4% per MAR22.25 Table 5."""
        assert get_sec_risk_weight(DRCSecRating.AAA, DRCSecSeniority.SENIOR) == 0.004

    def test_senior_rw_aa(self):
        assert get_sec_risk_weight(DRCSecRating.AA, DRCSecSeniority.SENIOR) == 0.008

    def test_senior_rw_a(self):
        assert get_sec_risk_weight(DRCSecRating.A, DRCSecSeniority.SENIOR) == 0.016

    def test_senior_rw_bbb(self):
        assert get_sec_risk_weight(DRCSecRating.BBB, DRCSecSeniority.SENIOR) == 0.048

    def test_senior_rw_bb(self):
        assert get_sec_risk_weight(DRCSecRating.BB, DRCSecSeniority.SENIOR) == 0.08

    def test_senior_rw_b(self):
        assert get_sec_risk_weight(DRCSecRating.B, DRCSecSeniority.SENIOR) == 0.16

    def test_senior_rw_ccc(self):
        assert get_sec_risk_weight(DRCSecRating.CCC, DRCSecSeniority.SENIOR) == 0.32

    def test_senior_rw_unrated(self):
        assert get_sec_risk_weight(DRCSecRating.UNRATED, DRCSecSeniority.SENIOR) == 1.0

    def test_senior_rw_defaulted(self):
        assert get_sec_risk_weight(DRCSecRating.DEFAULTED, DRCSecSeniority.SENIOR) == 1.0

    def test_nonseniorrw_aaa(self):
        """AAA non-senior tranche = 1.0% per MAR22.25 Table 5."""
        assert get_sec_risk_weight(DRCSecRating.AAA, DRCSecSeniority.NON_SENIOR) == 0.01

    def test_nonseniorrw_ccc(self):
        """CCC non-senior tranche = 64% per MAR22.25 Table 5."""
        assert get_sec_risk_weight(DRCSecRating.CCC, DRCSecSeniority.NON_SENIOR) == 0.64

    def test_nonseniorrw_defaulted(self):
        assert get_sec_risk_weight(DRCSecRating.DEFAULTED, DRCSecSeniority.NON_SENIOR) == 1.0

    def test_senior_always_le_nonsenior(self):
        """Senior risk weights must be <= non-senior for all ratings."""
        for rating in DRCSecRating:
            rw_sr = get_sec_risk_weight(rating, DRCSecSeniority.SENIOR)
            rw_ns = get_sec_risk_weight(rating, DRCSecSeniority.NON_SENIOR)
            assert rw_sr <= rw_ns, f"Senior RW > Non-senior for {rating}"


# =========================================================================
#  DRC Sec Non-CTP Calculator Tests
# =========================================================================


class TestDRCSecNonCTPCalculator:
    """Tests for DRC securitization non-CTP calculator."""

    @pytest.fixture
    def calc(self):
        return DRCSecNonCTPCalculator()

    def test_import(self):
        calc = DRCSecNonCTPCalculator()
        assert calc is not None

    def test_empty_returns_zero(self, calc):
        """Empty portfolio returns zero charge."""
        result = calc.calculate([])
        assert result.total_charge == 0.0
        assert result.position_count == 0
        assert result.bucket_charges == {}

    def test_single_long_position(self, calc):
        """Single long position should produce a positive charge."""
        positions = [_nonctp_pos()]
        result = calc.calculate(positions)
        assert result.total_charge > 0
        assert result.position_count == 1

    def test_single_long_position_value(self, calc):
        """Verify exact charge for a single long senior BBB RMBS tranche.

        notional=10M, market_value=9.8M, maturity=3yr (weight=1.0)
        JTD = max(1.0 * 10M + (9.8M - 10M), 0) = max(9.8M, 0) = 9.8M
        RW(BBB, senior) = 0.048
        Charge = 0.048 * 9.8M = 470,400
        """
        positions = [_nonctp_pos()]
        result = calc.calculate(positions)
        expected = 0.048 * 9_800_000.0
        assert abs(result.total_charge - expected) < 1.0

    def test_short_position_produces_charge(self, calc):
        """Short positions also produce charge (no netting in non-CTP).

        Per MAR22.27, there is NO offsetting for non-CTP securitizations.
        """
        positions = [_nonctp_pos(is_long=False)]
        result = calc.calculate(positions)
        assert result.total_charge > 0

    def test_no_netting_long_short(self, calc):
        """Long + short in same tranche: charges are additive (no offset).

        Per MAR22.27, no netting in non-CTP securitizations.
        """
        long_only = calc.calculate([_nonctp_pos(is_long=True)])
        short_only = calc.calculate([_nonctp_pos(is_long=False)])
        both = calc.calculate([
            _nonctp_pos(is_long=True),
            _nonctp_pos(is_long=False),
        ])
        # Charges should be additive
        assert abs(both.total_charge - (long_only.total_charge + short_only.total_charge)) < 1.0

    def test_higher_rating_lower_charge(self, calc):
        """AAA-rated position should have lower charge than CCC."""
        aaa = calc.calculate([_nonctp_pos(rating=DRCSecRating.AAA)])
        ccc = calc.calculate([_nonctp_pos(rating=DRCSecRating.CCC)])
        assert aaa.total_charge < ccc.total_charge

    def test_senior_lower_charge_than_nonsenior(self, calc):
        """Senior tranche should have lower charge than non-senior."""
        senior = calc.calculate([_nonctp_pos(seniority=DRCSecSeniority.SENIOR)])
        nonsenior = calc.calculate([_nonctp_pos(seniority=DRCSecSeniority.NON_SENIOR)])
        assert senior.total_charge < nonsenior.total_charge

    def test_defaulted_position_100pct_rw(self, calc):
        """Defaulted position gets 100% risk weight."""
        positions = [_nonctp_pos(rating=DRCSecRating.DEFAULTED)]
        result = calc.calculate(positions)
        # JTD = market_value = 9.8M, RW=1.0, charge = 9.8M
        expected = 1.0 * 9_800_000.0
        assert abs(result.total_charge - expected) < 1.0

    def test_unrated_position_100pct_rw(self, calc):
        """Unrated position gets 100% risk weight."""
        positions = [_nonctp_pos(rating=DRCSecRating.UNRATED)]
        result = calc.calculate(positions)
        expected = 1.0 * 9_800_000.0
        assert abs(result.total_charge - expected) < 1.0

    def test_maturity_scaling_short_maturity(self, calc):
        """Short maturity (6 months) should scale JTD by 0.5."""
        full_mat = calc.calculate([_nonctp_pos(maturity_years=3.0)])
        short_mat = calc.calculate([_nonctp_pos(maturity_years=0.5)])
        assert short_mat.total_charge < full_mat.total_charge
        # 6-month maturity weight = 0.5
        assert abs(short_mat.total_charge / full_mat.total_charge - 0.5) < 0.01

    def test_maturity_floor_3_months(self, calc):
        """Maturity < 3 months gets floor weight of 0.25."""
        floor_mat = calc.calculate([_nonctp_pos(maturity_years=0.1)])
        quarter_mat = calc.calculate([_nonctp_pos(maturity_years=0.25)])
        assert abs(floor_mat.total_charge - quarter_mat.total_charge) < 1.0

    def test_multiple_buckets(self, calc):
        """Positions in different buckets should have separate charges."""
        positions = [
            _nonctp_pos(bucket=DRCSecBucket.RMBS, tranche_id="A"),
            _nonctp_pos(bucket=DRCSecBucket.CMBS, tranche_id="B"),
            _nonctp_pos(bucket=DRCSecBucket.CLO, tranche_id="C"),
        ]
        result = calc.calculate(positions)
        assert len(result.bucket_charges) == 3
        assert "RMBS" in result.bucket_charges
        assert "CMBS" in result.bucket_charges
        assert "CLO" in result.bucket_charges

    def test_gross_jtd_statistics(self, calc):
        """Verify gross JTD long/short statistics."""
        positions = [
            _nonctp_pos(is_long=True),
            _nonctp_pos(is_long=False, tranche_id="B"),
        ]
        result = calc.calculate(positions)
        assert result.gross_jtd_long > 0
        assert result.gross_jtd_short < 0

    def test_notional_validation(self):
        """Zero or negative notional should raise ValueError."""
        with pytest.raises(ValueError, match="notional must be positive"):
            _nonctp_pos(notional=0.0)

    def test_negative_maturity_validation(self):
        """Negative maturity should raise ValueError."""
        with pytest.raises(ValueError, match="maturity_years must be non-negative"):
            _nonctp_pos(maturity_years=-1.0)

    def test_all_ratings_produce_charge(self, calc):
        """Every rating should produce a non-negative charge."""
        for rating in DRCSecRating:
            positions = [_nonctp_pos(rating=rating)]
            result = calc.calculate(positions)
            assert result.total_charge >= 0, f"Rating {rating} produced negative charge"

    def test_zero_pnl_position(self, calc):
        """Position at par (MV = notional) should still produce charge.

        JTD = max(1.0 * 10M + 0, 0) = 10M
        """
        positions = [_nonctp_pos(notional=10e6, market_value=10e6)]
        result = calc.calculate(positions)
        expected = 0.048 * 10_000_000.0  # BBB senior
        assert abs(result.total_charge - expected) < 1.0


# =========================================================================
#  DRC Sec CTP Calculator Tests
# =========================================================================


class TestDRCSecCTPCalculator:
    """Tests for DRC securitization CTP calculator."""

    @pytest.fixture
    def calc(self):
        return DRCSecCTPCalculator()

    def test_import(self):
        calc = DRCSecCTPCalculator()
        assert calc is not None

    def test_empty_returns_zero(self, calc):
        """Empty portfolio returns zero charge."""
        result = calc.calculate([])
        assert result.total_charge == 0.0
        assert result.position_count == 0
        assert result.bucket_charges == {}

    def test_single_long_position(self, calc):
        """Single long position should produce a positive charge."""
        positions = [_ctp_pos()]
        result = calc.calculate(positions)
        assert result.total_charge > 0
        assert result.position_count == 1

    def test_single_long_position_value(self, calc):
        """Verify exact charge for a single long senior BBB CTP tranche.

        notional=10M, market_value=9.8M, maturity=3yr (weight=1.0)
        JTD = max(1.0 * 10M + (9.8M - 10M), 0) = 9.8M
        RW(BBB, senior) = 0.048
        WtS = 0.048 * 9.8M = 470,400
        No shorts => DRC = max(470400 - 0, 0) = 470,400
        """
        positions = [_ctp_pos()]
        result = calc.calculate(positions)
        expected = 0.048 * 9_800_000.0
        assert abs(result.total_charge - expected) < 1.0

    def test_same_tranche_netting(self, calc):
        """Long + short in SAME tranche/index should net per MAR22.38.

        Long JTD = 9.8M, Short JTD = -9.8M => net = 0 => charge = 0.
        """
        positions = [
            _ctp_pos(is_long=True),
            _ctp_pos(is_long=False),
        ]
        result = calc.calculate(positions)
        assert abs(result.total_charge) < 1.0

    def test_different_tranche_no_netting(self, calc):
        """Long + short in DIFFERENT tranches should NOT net."""
        positions = [
            _ctp_pos(tranche_id="0-3", is_long=True),
            _ctp_pos(tranche_id="3-7", is_long=False),
        ]
        result = calc.calculate(positions)
        # Both should contribute: WtS from long, WtB from short
        assert result.total_charge > 0

    def test_different_index_no_netting(self, calc):
        """Long + short in DIFFERENT indices should NOT net."""
        positions = [
            _ctp_pos(index_name="CDX.NA.IG.42", is_long=True),
            _ctp_pos(index_name="iTraxx.Europe.41", is_long=False),
        ]
        result = calc.calculate(positions)
        assert result.total_charge > 0

    def test_hedge_benefit_50_percent(self, calc):
        """Verify 50% hedge benefit when shorts are in different tranches.

        Long: BBB senior, JTD = 9.8M, RW = 0.048 => WtS = 470,400
        Short: BBB senior, JTD = -9.8M, RW = 0.048 => WtB = 470,400
        DRC = max(470,400 - 0.5 * 470,400, 0) = 235,200
        """
        positions = [
            _ctp_pos(tranche_id="0-3", is_long=True),
            _ctp_pos(tranche_id="3-7", is_long=False),
        ]
        result = calc.calculate(positions)
        wts = 0.048 * 9_800_000.0
        expected = max(wts - 0.5 * wts, 0.0)
        assert abs(result.total_charge - expected) < 1.0

    def test_hedge_benefit_shorts_exceed_longs(self, calc):
        """When shorts exceed longs, charge floored at 0.

        WtS - 0.5 * WtB < 0 => charge = 0.
        """
        positions = [
            _ctp_pos(tranche_id="0-3", is_long=True, notional=5e6, market_value=4.9e6),
            _ctp_pos(tranche_id="3-7", is_long=False, notional=20e6, market_value=19.6e6),
        ]
        result = calc.calculate(positions)
        # Long JTD = 4.9M, WtS = 0.048 * 4.9M = 235,200
        # Short JTD = -19.6M, WtB = 0.048 * 19.6M = 940,800
        # DRC = max(235200 - 0.5 * 940800, 0) = max(235200 - 470400, 0) = 0
        assert abs(result.total_charge) < 1.0

    def test_multiple_buckets(self, calc):
        """Positions in different buckets should produce separate charges."""
        positions = [
            _ctp_pos(bucket=DRCSecCTPBucket.INDEX_CDS, tranche_id="A"),
            _ctp_pos(bucket=DRCSecCTPBucket.BESPOKE, tranche_id="B"),
        ]
        result = calc.calculate(positions)
        assert len(result.bucket_charges) == 2
        assert "INDEX_CDS" in result.bucket_charges
        assert "BESPOKE" in result.bucket_charges

    def test_net_jtd_statistics(self, calc):
        """Verify net JTD statistics after netting."""
        positions = [
            _ctp_pos(is_long=True),
            _ctp_pos(tranche_id="3-7", is_long=False),
        ]
        result = calc.calculate(positions)
        assert result.net_jtd_long > 0
        assert result.net_jtd_short < 0

    def test_partial_netting(self, calc):
        """Partial netting: long 10M, short 6M in same tranche => net 4M long.

        Long JTD = max(10M + (9.8M - 10M), 0) = 9.8M
        Short JTD = min(-(6M + (5.88M - 6M)), 0) = min(-5.88M, 0) = -5.88M
        Net = 9.8M - 5.88M = 3.92M
        RW(BBB, sr) = 0.048
        WtS = 0.048 * 3.92M = 188,160
        DRC = 188,160
        """
        positions = [
            _ctp_pos(is_long=True, notional=10e6, market_value=9.8e6),
            _ctp_pos(is_long=False, notional=6e6, market_value=5.88e6),
        ]
        result = calc.calculate(positions)
        # Net JTD = 9.8M - 5.88M = 3.92M
        expected = 0.048 * 3_920_000.0
        assert abs(result.total_charge - expected) < 1.0

    def test_maturity_scaling_ctp(self, calc):
        """Short maturity CTP positions should be scaled down."""
        full = calc.calculate([_ctp_pos(maturity_years=5.0)])
        half = calc.calculate([_ctp_pos(maturity_years=0.5)])
        assert half.total_charge < full.total_charge

    def test_notional_validation_ctp(self):
        """Zero or negative notional should raise ValueError."""
        with pytest.raises(ValueError, match="notional must be positive"):
            _ctp_pos(notional=0.0)

    def test_negative_maturity_validation_ctp(self):
        """Negative maturity should raise ValueError."""
        with pytest.raises(ValueError, match="maturity_years must be non-negative"):
            _ctp_pos(maturity_years=-1.0)

    def test_all_ratings_produce_charge_ctp(self, calc):
        """Every rating should produce a non-negative charge."""
        for rating in DRCSecRating:
            positions = [_ctp_pos(rating=rating)]
            result = calc.calculate(positions)
            assert result.total_charge >= 0, f"Rating {rating} produced negative charge"

    def test_nonsenior_higher_charge_ctp(self, calc):
        """Non-senior tranche should have higher charge than senior."""
        senior = calc.calculate([_ctp_pos(seniority=DRCSecSeniority.SENIOR)])
        nonsenior = calc.calculate([_ctp_pos(seniority=DRCSecSeniority.NON_SENIOR)])
        assert nonsenior.total_charge > senior.total_charge
