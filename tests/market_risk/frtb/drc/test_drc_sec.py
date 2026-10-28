"""Tests for the securitization DRC calculators, ERBA NPR §__.210(c) and §__.210(d)."""

from __future__ import annotations

import pytest

from src.core.enums import (
    DRCCreditQuality,
    DRCExposureType,
    DRCSecBucket,
    DRCSecCTPBucket,
    DRCSecRating,
    DRCSecRegion,
    DRCSecSeniority,
    DRCSeniority,
)
from src.core.exceptions import ValidationError
from src.market_risk.frtb.drc.drc_params import (
    CTP_NEGATIVE_BUCKET_FACTOR,
    DRC_SEC_CAPITAL_CONVERSION,
    compute_sec_sa_risk_weight,
    get_sec_drc_risk_weight,
)
from src.market_risk.frtb.drc.drc_sec_ctp import (
    DRCSecCTPCalculator,
    DRCSecCTPPosition,
)
from src.market_risk.frtb.drc.drc_sec_nonctp import (
    DRCSecNonCTPCalculator,
    DRCSecNonCTPPosition,
    resolve_sec_drc_risk_weight,
)

# =========================================================================
#  Helpers
# =========================================================================


def _nonctp_pos(
    tranche_id: str = "A",
    pool_id: str = "POOL_1",
    asset_class: DRCSecBucket = DRCSecBucket.RMBS,
    region: DRCSecRegion | None = DRCSecRegion.NORTH_AMERICA,
    market_value: float = 100.0,
    maturity_years: float = 3.0,
    is_long: bool = True,
    banking_book_risk_weight: float | None = 0.15,
    **kwargs,
) -> DRCSecNonCTPPosition:
    return DRCSecNonCTPPosition(
        tranche_id=tranche_id,
        pool_id=pool_id,
        asset_class=asset_class,
        region=region,
        market_value=market_value,
        maturity_years=maturity_years,
        is_long=is_long,
        banking_book_risk_weight=banking_book_risk_weight,
        **kwargs,
    )


def _ctp_pos(
    tranche_id: str = "0-3",
    index_name: str = "CDX.NA.IG.42",
    market_value: float = 100.0,
    maturity_years: float = 3.0,
    is_long: bool = True,
    banking_book_risk_weight: float | None = 1.25,
    **kwargs,
) -> DRCSecCTPPosition:
    return DRCSecCTPPosition(
        tranche_id=tranche_id,
        index_name=index_name,
        market_value=market_value,
        maturity_years=maturity_years,
        is_long=is_long,
        banking_book_risk_weight=banking_book_risk_weight,
        **kwargs,
    )


# =========================================================================
#  Parameters -- §__.210(c)(3)(ii), §__.210(d)(4)
# =========================================================================


class TestDRCSecParams:

    def test_capital_conversion_is_8_percent(self):
        assert DRC_SEC_CAPITAL_CONVERSION == 0.08

    def test_banking_book_15pct_gives_1_2pct(self):
        """(d) SEC-SA floor 15% x 8% = 1.2%."""
        assert get_sec_drc_risk_weight(0.15) == pytest.approx(0.012)

    def test_banking_book_1250pct_gives_100pct(self):
        assert get_sec_drc_risk_weight(12.5) == pytest.approx(1.0)

    def test_banking_book_rw_out_of_range(self):
        with pytest.raises(ValidationError):
            get_sec_drc_risk_weight(13.0)
        with pytest.raises(ValidationError):
            get_sec_drc_risk_weight(-0.1)

    def test_ctp_negative_bucket_factor(self):
        assert CTP_NEGATIVE_BUCKET_FACTOR == 0.5

    def test_ssfa_fallback_senior_thick_tranche_hits_floor(self):
        """Senior tranche far above K_A -> SSFA ~0 -> floored at 15%."""
        rw = compute_sec_sa_risk_weight(attachment_point=0.5, detachment_point=1.0, k_g=0.04)
        assert rw == pytest.approx(0.15)

    def test_ssfa_fallback_below_ka_is_1250(self):
        rw = compute_sec_sa_risk_weight(attachment_point=0.0, detachment_point=0.03, k_g=0.04)
        assert rw == pytest.approx(12.5)

    def test_ssfa_fallback_mezzanine_between(self):
        rw = compute_sec_sa_risk_weight(attachment_point=0.05, detachment_point=0.10, k_g=0.04)
        assert 0.15 < rw < 12.5

    def test_ssfa_fallback_invalid_inputs(self):
        with pytest.raises(ValidationError):
            compute_sec_sa_risk_weight(attachment_point=0.5, detachment_point=0.4, k_g=0.04)
        with pytest.raises(ValidationError):
            compute_sec_sa_risk_weight(attachment_point=0.0, detachment_point=1.0, k_g=0.0)

    def test_resolver_precedence_and_error(self):
        # banking-book RW wins
        assert resolve_sec_drc_risk_weight(
            banking_book_risk_weight=0.5, attachment_point=0.0, detachment_point=0.03,
            k_g=0.04, w=None, is_resecuritization=False,
        ) == pytest.approx(0.04)
        # SSFA fallback
        assert resolve_sec_drc_risk_weight(
            banking_book_risk_weight=None, attachment_point=0.5, detachment_point=1.0,
            k_g=0.04, w=None, is_resecuritization=False,
        ) == pytest.approx(0.012)
        # nothing -> error, never the legacy table silently
        with pytest.raises(ValidationError, match="no securitization risk weight"):
            resolve_sec_drc_risk_weight(
                banking_book_risk_weight=None, attachment_point=None, detachment_point=None,
                k_g=None, w=None, is_resecuritization=False,
                rating=DRCSecRating.AAA, seniority=DRCSecSeniority.SENIOR,
            )
        # explicit legacy opt-in
        assert resolve_sec_drc_risk_weight(
            banking_book_risk_weight=None, attachment_point=None, detachment_point=None,
            k_g=None, w=None, is_resecuritization=False, legacy_rating_table=True,
            rating=DRCSecRating.AAA, seniority=DRCSecSeniority.SENIOR,
        ) == pytest.approx(0.004)


# =========================================================================
#  Securitization non-CTP -- §__.210(c)
# =========================================================================


class TestDRCSecNonCTPCalculator:

    @pytest.fixture
    def calc(self):
        return DRCSecNonCTPCalculator()

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0
        assert result.position_count == 0
        assert result.bucket_charges == {}

    def test_closed_form_banking_book_15pct(self, calc):
        """(d) MV 100, banking-book RW 15% -> DRC RW 1.2% -> charge 1.2."""
        result = calc.calculate([_nonctp_pos()])
        assert result.gross_jtd_long == pytest.approx(100.0)
        assert result.total_charge == pytest.approx(1.2)
        assert result.bucket_charges == {"RMBS_NORTH_AMERICA": pytest.approx(1.2)}

    def test_gross_de_is_market_value_no_lgd(self, calc):
        result = calc.calculate([_nonctp_pos(market_value=37.0)])
        assert result.gross_jtd_long == pytest.approx(37.0)

    def test_short_only_no_charge(self, calc):
        result = calc.calculate([_nonctp_pos(is_long=False)])
        assert result.gross_jtd_short == pytest.approx(-100.0)
        assert result.total_charge == 0.0

    def test_same_pool_same_tranche_offsets(self, calc):
        result = calc.calculate([
            _nonctp_pos(is_long=True),
            _nonctp_pos(is_long=False, market_value=60.0),
        ])
        assert result.net_jtd_long == pytest.approx(40.0)
        assert result.total_charge == pytest.approx(0.012 * 40.0)

    def test_different_tranche_same_pool_hbr(self, calc):
        """Different tranches do not offset; HBR applies within the bucket.

        Long 100 (RW 1.2%), short 50 (RW 4%): HBR = 100/150 = 2/3.
        DRC = 1.2 - (2/3) x 0.04 x 50 = 1.2 - 1.3333 -> floored 0.
        Use short RW 1.2% instead: DRC = 1.2 - (2/3) x 0.6 = 0.8.
        """
        result = calc.calculate([
            _nonctp_pos(tranche_id="A", is_long=True),
            _nonctp_pos(tranche_id="B", is_long=False, market_value=50.0),
        ])
        assert result.net_jtd_long == pytest.approx(100.0)
        assert result.net_jtd_short == pytest.approx(-50.0)
        assert result.bucket_details[0].hbr == pytest.approx(2.0 / 3.0)
        assert result.total_charge == pytest.approx(0.8)

    def test_different_pool_no_offset(self, calc):
        result = calc.calculate([
            _nonctp_pos(pool_id="P1", is_long=True),
            _nonctp_pos(pool_id="P2", is_long=False),
        ])
        assert result.net_jtd_long == pytest.approx(100.0)
        assert result.net_jtd_short == pytest.approx(-100.0)
        # HBR = 0.5; DRC = 1.2 - 0.5 x 1.2 = 0.6
        assert result.total_charge == pytest.approx(0.6)

    def test_shorts_exceed_longs_floored_zero(self, calc):
        result = calc.calculate([
            _nonctp_pos(tranche_id="A", is_long=True, market_value=10.0),
            _nonctp_pos(tranche_id="B", is_long=False, market_value=100.0,
                        banking_book_risk_weight=12.5),
        ])
        assert result.total_charge == 0.0

    def test_buckets_asset_class_x_region(self, calc):
        result = calc.calculate([
            _nonctp_pos(tranche_id="A", asset_class=DRCSecBucket.RMBS,
                        region=DRCSecRegion.NORTH_AMERICA),
            _nonctp_pos(tranche_id="B", asset_class=DRCSecBucket.RMBS,
                        region=DRCSecRegion.EUROPE),
            _nonctp_pos(tranche_id="C", asset_class=DRCSecBucket.CLO,
                        region=DRCSecRegion.NORTH_AMERICA),
            _nonctp_pos(tranche_id="D", asset_class=DRCSecBucket.CORPORATE, region=None),
        ])
        assert set(result.bucket_charges) == {
            "RMBS_NORTH_AMERICA", "RMBS_EUROPE", "CLO_NORTH_AMERICA", "CORPORATE",
        }
        assert result.total_charge == pytest.approx(4 * 1.2)

    def test_region_required_unless_corporate(self):
        with pytest.raises(ValueError, match="region is required"):
            _nonctp_pos(region=None)
        _nonctp_pos(asset_class=DRCSecBucket.CORPORATE, region=None)  # ok

    def test_asset_class_enum_covers_npr_list(self):
        names = {m.name for m in DRCSecBucket}
        assert {"CORPORATE", "ABCP", "AUTO", "RMBS", "CREDIT_CARDS", "CMBS", "CLO",
                "CDO_SQUARED", "SME", "STUDENT_LOANS", "OTHER_RETAIL",
                "OTHER_WHOLESALE"} <= names
        assert {m.name for m in DRCSecRegion} == {"ASIA", "EUROPE", "NORTH_AMERICA", "OTHER"}
        assert DRCSecBucket.ABS_AUTO is DRCSecBucket.AUTO

    def test_legacy_aliases_deal_name_and_bucket(self):
        pos = DRCSecNonCTPPosition(
            tranche_id="A", deal_name="D1", bucket=DRCSecBucket.CMBS,
            region=DRCSecRegion.ASIA, market_value=10.0, maturity_years=1.0,
            is_long=True, banking_book_risk_weight=0.2,
        )
        assert pos.pool_id == "D1"
        assert pos.bucket_label == "CMBS_ASIA"

    def test_ssfa_fallback_when_banking_book_rw_absent(self, calc):
        result = calc.calculate([
            _nonctp_pos(banking_book_risk_weight=None, attachment_point=0.5,
                        detachment_point=1.0, k_g=0.04),
        ])
        assert result.total_charge == pytest.approx(1.2)

    def test_no_rw_source_raises(self, calc):
        with pytest.raises(ValidationError, match="no securitization risk weight"):
            calc.calculate([_nonctp_pos(banking_book_risk_weight=None,
                                        rating=DRCSecRating.AAA,
                                        seniority=DRCSecSeniority.SENIOR)])

    def test_legacy_table_only_with_explicit_switch(self):
        legacy = DRCSecNonCTPCalculator(legacy_rating_table=True)
        result = legacy.calculate([_nonctp_pos(banking_book_risk_weight=None,
                                               rating=DRCSecRating.AAA,
                                               seniority=DRCSecSeniority.SENIOR)])
        assert result.total_charge == pytest.approx(0.4)

    def test_fair_value_cap_for_cash_positions(self, calc):
        """1,250% x 8% = 100%, so the charge never exceeds fair value."""
        result = calc.calculate([_nonctp_pos(banking_book_risk_weight=12.5)])
        assert result.total_charge == pytest.approx(100.0)

    def test_maturity_scaling(self, calc):
        full = calc.calculate([_nonctp_pos(maturity_years=3.0)]).total_charge
        half = calc.calculate([_nonctp_pos(maturity_years=0.5)]).total_charge
        floor = calc.calculate([_nonctp_pos(maturity_years=0.1)]).total_charge
        assert half == pytest.approx(0.5 * full)
        assert floor == pytest.approx(0.25 * full)

    def test_market_value_sign_validation(self):
        with pytest.raises(ValueError, match="market_value"):
            _nonctp_pos(market_value=-1.0)

    def test_negative_maturity_validation(self):
        with pytest.raises(ValueError, match="maturity_years must be non-negative"):
            _nonctp_pos(maturity_years=-1.0)


# =========================================================================
#  CTP -- §__.210(d)
# =========================================================================


class TestDRCSecCTPCalculator:

    @pytest.fixture
    def calc(self):
        return DRCSecCTPCalculator()

    def test_empty_returns_zero(self, calc):
        result = calc.calculate([])
        assert result.total_charge == 0.0
        assert result.position_count == 0

    def test_single_long_value(self, calc):
        """MV 100, banking-book RW 125% -> DRC RW 10% -> 10."""
        result = calc.calculate([_ctp_pos()])
        assert result.total_charge == pytest.approx(10.0)
        assert result.hbr_ctp == pytest.approx(1.0)

    def test_two_bucket_closed_form(self):
        """(e) Buckets +10 and -4 -> total 10 + 0.5 x (-4) = 8."""
        total = DRCSecCTPCalculator.aggregate_buckets({"CDX": 10.0, "ITRAXX": -4.0})
        assert total == pytest.approx(8.0)

    def test_total_floored_at_zero(self):
        assert DRCSecCTPCalculator.aggregate_buckets({"A": 2.0, "B": -10.0}) == 0.0

    def test_two_bucket_closed_form_from_positions(self, calc):
        """Long 100 in CDX (RW 10%), short 100 in iTraxx (RW 10%).

        HBR_CTP = 100 / 200 = 0.5 (computed once across both indices).
        CDX:    DRC_b = 10 - 0.5 x 0   = 10
        iTraxx: DRC_b = 0  - 0.5 x 10  = -5
        Total = max(10 + 0.5 x (-5), 0) = 7.5
        """
        result = calc.calculate([
            _ctp_pos(index_name="CDX.NA.IG.42", is_long=True),
            _ctp_pos(index_name="iTraxx.Europe.41", is_long=False),
        ])
        assert result.hbr_ctp == pytest.approx(0.5)
        assert result.bucket_charges["CDX.NA.IG.42"] == pytest.approx(10.0)
        assert result.bucket_charges["iTraxx.Europe.41"] == pytest.approx(-5.0)
        assert result.total_charge == pytest.approx(7.5)

    def test_bucket_amount_not_floored(self, calc):
        result = calc.calculate([
            _ctp_pos(index_name="A", is_long=True, market_value=10.0),
            _ctp_pos(index_name="B", is_long=False, market_value=100.0),
        ])
        assert result.bucket_charges["B"] < 0.0

    def test_each_index_is_own_bucket(self, calc):
        result = calc.calculate([
            _ctp_pos(index_name="CDX.NA.IG.42"),
            _ctp_pos(index_name="CDX.NA.HY.42"),
            _ctp_pos(index_name="iTraxx.Europe.41"),
        ])
        assert set(result.bucket_charges) == {"CDX.NA.IG.42", "CDX.NA.HY.42", "iTraxx.Europe.41"}

    def test_same_tranche_same_index_offsets(self, calc):
        result = calc.calculate([_ctp_pos(is_long=True), _ctp_pos(is_long=False)])
        assert result.total_charge == pytest.approx(0.0)
        assert result.net_jtd_long == pytest.approx(0.0)

    def test_partial_same_tranche_offset(self, calc):
        result = calc.calculate([
            _ctp_pos(is_long=True, market_value=100.0),
            _ctp_pos(is_long=False, market_value=60.0),
        ])
        assert result.total_charge == pytest.approx(0.1 * 40.0)

    def test_different_tranche_same_index_hbr_within_bucket(self, calc):
        """Long 0-3 (100), short 3-7 (50), both RW 10%: HBR = 2/3.

        DRC_b = 10 - (2/3) x 5 = 6.6667; single bucket -> total 6.6667.
        """
        result = calc.calculate([
            _ctp_pos(tranche_id="0-3", is_long=True),
            _ctp_pos(tranche_id="3-7", is_long=False, market_value=50.0),
        ])
        assert result.hbr_ctp == pytest.approx(2.0 / 3.0)
        assert result.total_charge == pytest.approx(10.0 - (2.0 / 3.0) * 5.0)

    def test_bespoke_maps_to_index_bucket(self, calc):
        result = calc.calculate([
            _ctp_pos(tranche_id="0-3", index_name="CDX.NA.IG.42"),
            _ctp_pos(tranche_id="BESPOKE_7", index_name="CDX.NA.IG.42",
                     position_type=DRCSecCTPBucket.BESPOKE),
        ])
        assert set(result.bucket_charges) == {"CDX.NA.IG.42"}

    def test_nth_to_default_attachment_detachment(self):
        """Second-to-default on 100 names: A = 1/100, D = 2/100."""
        pos = _ctp_pos(position_type=DRCSecCTPBucket.NTD, nth=2, total_names=100,
                       banking_book_risk_weight=None, k_g=0.04)
        assert pos.attachment_point == pytest.approx(0.01)
        assert pos.detachment_point == pytest.approx(0.02)
        # entirely below K_A = 4% -> 1,250% x 8% = 100% RW
        result = DRCSecCTPCalculator().calculate([pos])
        assert result.total_charge == pytest.approx(100.0)

    def test_nonsec_hedge_uses_nonsec_lgd_and_rw(self, calc):
        """Single-name CDS hedge (short, corporate IG senior, notional 100) in the CTP bucket.

        Hedge GDE = -(0.75 x 100 + 0) = -75, RW = 4.1%.
        Long tranche 100 at RW 10%.  HBR = 100 / 175.
        DRC_b = 10 - (100/175) x 0.041 x 75.
        """
        result = calc.calculate([
            _ctp_pos(index_name="CDX.NA.IG.42", is_long=True),
            DRCSecCTPPosition(
                tranche_id="ACME", index_name="CDX.NA.IG.42",
                position_type=DRCSecCTPBucket.NON_SEC_HEDGE,
                market_value=100.0, notional=100.0, maturity_years=5.0, is_long=False,
                nonsec_seniority=DRCSeniority.SENIOR_UNSECURED,
                nonsec_exposure_type=DRCExposureType.CORPORATE,
                nonsec_credit_quality=DRCCreditQuality.INVESTMENT_GRADE,
            ),
        ])
        hbr = 100.0 / 175.0
        assert result.net_jtd_short == pytest.approx(-75.0)
        assert result.total_charge == pytest.approx(10.0 - hbr * 0.041 * 75.0)

    def test_nonsec_hedge_requires_fields(self):
        with pytest.raises(ValueError, match="NON_SEC_HEDGE"):
            DRCSecCTPPosition(
                tranche_id="ACME", index_name="CDX", position_type=DRCSecCTPBucket.NON_SEC_HEDGE,
                market_value=100.0, maturity_years=5.0, is_long=False,
            )

    def test_no_rw_source_raises(self, calc):
        with pytest.raises(ValidationError, match="no securitization risk weight"):
            calc.calculate([_ctp_pos(banking_book_risk_weight=None)])

    def test_legacy_table_explicit_only(self):
        legacy = DRCSecCTPCalculator(legacy_rating_table=True)
        result = legacy.calculate([_ctp_pos(banking_book_risk_weight=None,
                                            rating=DRCSecRating.BBB,
                                            seniority=DRCSecSeniority.SENIOR)])
        assert result.total_charge == pytest.approx(0.048 * 100.0)

    def test_maturity_scaling_ctp(self, calc):
        full = calc.calculate([_ctp_pos(maturity_years=5.0)]).total_charge
        half = calc.calculate([_ctp_pos(maturity_years=0.5)]).total_charge
        assert half == pytest.approx(0.5 * full)

    def test_legacy_bucket_alias(self):
        assert DRCSecCTPBucket.INDEX_CDS is DRCSecCTPBucket.INDEX_TRANCHE
        pos = _ctp_pos(bucket=DRCSecCTPBucket.INDEX_CDS)
        assert pos.position_type is DRCSecCTPBucket.INDEX_TRANCHE

    def test_negative_maturity_validation_ctp(self):
        with pytest.raises(ValueError, match="maturity_years must be non-negative"):
            _ctp_pos(maturity_years=-1.0)
