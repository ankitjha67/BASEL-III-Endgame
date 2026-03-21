"""Tests for Default Risk Charge (DRC) Non-Securitization calculator."""

from __future__ import annotations

import pytest

from src.core.enums import DRCExposureType, DRCRatingCategory, DRCSeniority
from src.core.models import DRCPosition
from src.market_risk.frtb.drc.drc_nonsec import DRCCalculator
from src.market_risk.frtb.drc.drc_params import (
    DRC_RISK_WEIGHTS,
    LGD_VALUES,
    compute_maturity_weight,
    get_lgd,
    get_risk_weight,
)


# =========================================================================
#  Helper
# =========================================================================

def _pos(
    issuer: str = "CORP_A",
    seniority: DRCSeniority = DRCSeniority.SENIOR_UNSECURED,
    rating: DRCRatingCategory = DRCRatingCategory.BBB,
    notional: float = 10_000_000.0,
    market_value: float = 9_800_000.0,
    maturity_years: float = 3.0,
    is_long: bool = True,
) -> DRCPosition:
    return DRCPosition(
        issuer=issuer,
        seniority=seniority,
        rating=rating,
        exposure_type=DRCExposureType.CORPORATE,
        notional=notional,
        market_value=market_value,
        maturity_years=maturity_years,
        is_long=is_long,
    )


# =========================================================================
#  Parameter Tests
# =========================================================================

class TestDRCParams:
    """Tests for DRC regulatory parameters."""

    def test_lgd_senior_secured(self):
        assert get_lgd(DRCSeniority.SENIOR_SECURED) == 0.25

    def test_lgd_senior_unsecured(self):
        assert get_lgd(DRCSeniority.SENIOR_UNSECURED) == 0.75

    def test_lgd_subordinated(self):
        assert get_lgd(DRCSeniority.SUBORDINATED) == 0.75

    def test_lgd_equity(self):
        assert get_lgd(DRCSeniority.EQUITY) == 1.00

    def test_risk_weight_aaa(self):
        assert get_risk_weight(DRCRatingCategory.AAA) == 0.005

    def test_risk_weight_bbb(self):
        assert get_risk_weight(DRCRatingCategory.BBB) == 0.06

    def test_risk_weight_ccc(self):
        assert get_risk_weight(DRCRatingCategory.CCC) == 0.50

    def test_risk_weight_defaulted(self):
        assert get_risk_weight(DRCRatingCategory.DEFAULTED) == 1.00

    def test_risk_weight_unrated(self):
        assert get_risk_weight(DRCRatingCategory.UNRATED) == 0.15

    def test_maturity_weight_1yr(self):
        assert abs(compute_maturity_weight(1.0) - 1.0) < 1e-10

    def test_maturity_weight_5yr(self):
        """Maturities > 1 year are capped at 1.0."""
        assert abs(compute_maturity_weight(5.0) - 1.0) < 1e-10

    def test_maturity_weight_6mo(self):
        assert abs(compute_maturity_weight(0.5) - 0.5) < 1e-10

    def test_maturity_weight_floor(self):
        """Maturities < 3 months get 0.25 floor."""
        assert abs(compute_maturity_weight(0.1) - 0.25) < 1e-10


# =========================================================================
#  DRC Calculator Tests
# =========================================================================

class TestDRCCalculator:
    """Tests for DRC calculator."""

    @pytest.fixture
    def calc(self):
        return DRCCalculator()

    def test_import(self):
        calc = DRCCalculator()
        assert calc is not None

    def test_single_long_position(self, calc):
        positions = [_pos()]
        result = calc.calculate(positions)
        assert result.total_charge > 0

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0

    def test_short_position_reduces_charge(self, calc):
        """A short position should reduce the DRC charge via HBR."""
        long_only = [_pos(issuer="A", is_long=True, notional=10e6, market_value=9.8e6)]
        with_hedge = [
            _pos(issuer="A", is_long=True, notional=10e6, market_value=9.8e6),
            _pos(issuer="B", is_long=False, notional=5e6, market_value=5.1e6,
                 rating=DRCRatingCategory.BBB),
        ]
        long_result = calc.calculate(long_only)
        hedged_result = calc.calculate(with_hedge)
        assert hedged_result.total_charge <= long_result.total_charge

    def test_same_issuer_netting(self, calc):
        """Same issuer + same seniority should net."""
        positions = [
            _pos(issuer="CORP_X", is_long=True, notional=10e6, market_value=9.5e6),
            _pos(issuer="CORP_X", is_long=False, notional=8e6, market_value=8.2e6),
        ]
        result = calc.calculate(positions)
        assert result.total_charge >= 0

    def test_higher_rating_lower_charge(self, calc):
        """AAA-rated position should have lower charge than CCC."""
        aaa = [_pos(rating=DRCRatingCategory.AAA)]
        ccc = [_pos(rating=DRCRatingCategory.CCC)]
        aaa_result = calc.calculate(aaa)
        ccc_result = calc.calculate(ccc)
        assert aaa_result.total_charge < ccc_result.total_charge

    def test_equity_seniority_full_lgd(self, calc):
        """Equity seniority has 100% LGD → higher charge."""
        senior = [_pos(seniority=DRCSeniority.SENIOR_SECURED)]
        equity = [_pos(seniority=DRCSeniority.EQUITY)]
        senior_result = calc.calculate(senior)
        equity_result = calc.calculate(equity)
        assert equity_result.total_charge > senior_result.total_charge

    def test_short_maturity_reduces_charge(self, calc):
        """Short maturity positions get lower maturity weight."""
        long_mat = [_pos(maturity_years=5.0)]
        short_mat = [_pos(maturity_years=0.25)]
        long_result = calc.calculate(long_mat)
        short_result = calc.calculate(short_mat)
        assert short_result.total_charge <= long_result.total_charge
