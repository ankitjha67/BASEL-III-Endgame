"""Tests for the non-securitization default risk capital requirement, ERBA NPR §__.210(b)."""

from __future__ import annotations

import pytest

from src.core.enums import (
    DRCCreditQuality,
    DRCExposureType,
    DRCRatingCategory,
    DRCSeniority,
)
from src.core.exceptions import ValidationError
from src.core.models import DRCPosition as CoreDRCPosition
from src.market_risk.frtb.drc.drc_nonsec import DRCCalculator, DRCPosition
from src.market_risk.frtb.drc.drc_params import (
    DRC_DEFAULTED_RISK_WEIGHT,
    DRC_RISK_WEIGHTS,
    LGD_VALUES,
    compute_hedge_benefit_ratio,
    compute_maturity_weight,
    get_bucket_label,
    get_lgd,
    get_risk_weight,
    get_seniority_rank,
    rating_to_credit_quality,
)

IG = DRCCreditQuality.INVESTMENT_GRADE
SPEC = DRCCreditQuality.SPECULATIVE_GRADE
SUB = DRCCreditQuality.SUB_SPECULATIVE_GRADE
DEF = DRCCreditQuality.DEFAULTED


# =========================================================================
#  Helper
# =========================================================================

def _pos(
    issuer: str = "CORP_A",
    seniority: DRCSeniority = DRCSeniority.SENIOR_UNSECURED,
    credit_quality: DRCCreditQuality = IG,
    exposure_type: DRCExposureType = DRCExposureType.CORPORATE,
    notional: float = 100.0,
    market_value: float | None = None,
    maturity_years: float = 5.0,
    is_long: bool = True,
    **kwargs,
) -> DRCPosition:
    return DRCPosition(
        issuer=issuer,
        seniority=seniority,
        credit_quality=credit_quality,
        exposure_type=exposure_type,
        notional=notional,
        market_value=notional if market_value is None else market_value,
        maturity_years=maturity_years,
        is_long=is_long,
        **kwargs,
    )


# =========================================================================
#  Parameter tests -- §__.210(b)(1)(iv), Table 1 to §__.210
# =========================================================================

class TestDRCParams:
    """Regulatory parameters per ERBA NPR §__.210(b)."""

    @pytest.mark.parametrize(
        "seniority, lgd",
        [
            (DRCSeniority.EQUITY, 1.00),
            (DRCSeniority.SUBORDINATED, 1.00),
            (DRCSeniority.SENIOR_UNSECURED, 0.75),
            (DRCSeniority.GSE_UNGUARANTEED, 0.75),
            (DRCSeniority.US_PSE, 0.50),
            (DRCSeniority.GSE_GUARANTEED, 0.25),
            (DRCSeniority.COVERED_BOND, 0.25),
            (DRCSeniority.NOT_LINKED_TO_RECOVERY, 0.00),
        ],
    )
    def test_lgd_table(self, seniority, lgd):
        """§__.210(b)(1)(iv) LGD rates."""
        assert get_lgd(seniority) == lgd
        assert LGD_VALUES[seniority] == lgd

    def test_senior_secured_alias_is_covered_bond(self):
        assert DRCSeniority.SENIOR_SECURED is DRCSeniority.COVERED_BOND
        assert get_lgd(DRCSeniority.SENIOR_SECURED) == 0.25

    def test_defaulted_lgd_overrides_seniority(self):
        assert get_lgd(DRCSeniority.COVERED_BOND, DEF) == 1.0

    @pytest.mark.parametrize(
        "exposure_type, cq, rw",
        [
            (DRCExposureType.NON_US_SOVEREIGN, IG, 0.006),
            (DRCExposureType.NON_US_SOVEREIGN, SPEC, 0.22),
            (DRCExposureType.NON_US_SOVEREIGN, SUB, 0.50),
            (DRCExposureType.PSE_GSE, IG, 0.021),
            (DRCExposureType.PSE_GSE, SPEC, 0.22),
            (DRCExposureType.PSE_GSE, SUB, 0.50),
            (DRCExposureType.CORPORATE, IG, 0.041),
            (DRCExposureType.CORPORATE, SPEC, 0.22),
            (DRCExposureType.CORPORATE, SUB, 0.50),
        ],
    )
    def test_table_1_risk_weights(self, exposure_type, cq, rw):
        """Table 1 to §__.210 (ERBA NPR p.906)."""
        assert get_risk_weight(cq, exposure_type) == pytest.approx(rw)
        assert DRC_RISK_WEIGHTS[exposure_type][cq] == pytest.approx(rw)

    def test_defaulted_rw_100pct_any_sector(self):
        assert DRC_DEFAULTED_RISK_WEIGHT == 1.0
        for et in (DRCExposureType.NON_US_SOVEREIGN, DRCExposureType.PSE_GSE,
                   DRCExposureType.CORPORATE):
            assert get_risk_weight(DEF, et) == 1.0

    def test_aliases(self):
        assert DRCExposureType.SOVEREIGN is DRCExposureType.NON_US_SOVEREIGN
        assert DRCExposureType.LOCAL_GOVERNMENT is DRCExposureType.PSE_GSE

    def test_exactly_four_buckets(self):
        labels = {
            get_bucket_label(DRCExposureType.NON_US_SOVEREIGN, IG),
            get_bucket_label(DRCExposureType.PSE_GSE, IG),
            get_bucket_label(DRCExposureType.CORPORATE, IG),
            get_bucket_label(DRCExposureType.CORPORATE, DEF),
        }
        assert labels == {"NON_US_SOVEREIGN", "PSE_GSE", "CORPORATE", "DEFAULTED"}
        assert get_bucket_label(DRCExposureType.NON_US_SOVEREIGN, DEF) == "DEFAULTED"

    @pytest.mark.parametrize(
        "rating, cq",
        [
            (DRCRatingCategory.AAA, IG), (DRCRatingCategory.AA, IG),
            (DRCRatingCategory.A, IG), (DRCRatingCategory.BBB, IG),
            (DRCRatingCategory.BB, SPEC), (DRCRatingCategory.B, SPEC),
            (DRCRatingCategory.CCC, SUB), (DRCRatingCategory.DEFAULTED, DEF),
            (DRCRatingCategory.UNRATED, SPEC),
        ],
    )
    def test_rating_convenience_mapping(self, rating, cq):
        assert rating_to_credit_quality(rating) is cq

    def test_seniority_rank_order(self):
        assert (get_seniority_rank(DRCSeniority.EQUITY)
                < get_seniority_rank(DRCSeniority.SUBORDINATED)
                < get_seniority_rank(DRCSeniority.SENIOR_UNSECURED)
                < get_seniority_rank(DRCSeniority.COVERED_BOND))

    def test_maturity_weight_1yr(self):
        assert compute_maturity_weight(1.0) == pytest.approx(1.0)

    def test_maturity_weight_5yr_capped(self):
        assert compute_maturity_weight(5.0) == pytest.approx(1.0)

    def test_maturity_weight_6mo(self):
        assert compute_maturity_weight(0.5) == pytest.approx(0.5)

    def test_maturity_weight_floor(self):
        """< 3 months floored at 0.25."""
        assert compute_maturity_weight(0.1) == pytest.approx(0.25)
        assert compute_maturity_weight(0.0) == pytest.approx(0.25)

    def test_hbr_formula(self):
        assert compute_hedge_benefit_ratio(100.0, -50.0) == pytest.approx(2.0 / 3.0)
        assert compute_hedge_benefit_ratio(0.0, -50.0) == 0.0
        assert compute_hedge_benefit_ratio(100.0, 0.0) == 1.0


# =========================================================================
#  Calculator tests
# =========================================================================

class TestDRCCalculator:
    """§__.210(b) pipeline."""

    @pytest.fixture
    def calc(self):
        return DRCCalculator()

    def test_empty_returns_zero(self, calc):
        assert calc.calculate([]).total_charge == 0.0

    def test_closed_form_corporate_ig_senior(self, calc):
        """(a) Corporate IG long 100 senior (LGD 0.75), 5y: JTD 75; DRC = 0.041 x 75 = 3.075."""
        result = calc.calculate([_pos()])
        assert result.gross_jtd_long == pytest.approx(75.0)
        assert result.total_charge == pytest.approx(3.075)
        assert result.bucket_charges == {"CORPORATE": pytest.approx(3.075)}

    def test_gross_jtd_includes_pnl(self, calc):
        """GDE_long = max(LGD x N + P&L, 0): 0.75 x 100 + (98 - 100) = 73."""
        result = calc.calculate([_pos(market_value=98.0)])
        assert result.gross_jtd_long == pytest.approx(73.0)

    def test_short_gross_jtd_sign(self, calc):
        result = calc.calculate([_pos(is_long=False, market_value=98.0)])
        assert result.gross_jtd_short == pytest.approx(-73.0)
        assert result.total_charge == 0.0  # no longs -> nothing to charge

    def test_nonsenior_short_offsets_senior_long(self, calc):
        """(b) Same obligor: short SUBORDINATED (lower seniority) MAY offset long SENIOR.

        Long senior 100 -> JTD 75; short sub 50 -> JTD -50; net long 25 senior.
        DRC = 0.041 x 25 = 1.025.
        """
        result = calc.calculate([
            _pos(issuer="X", is_long=True, seniority=DRCSeniority.SENIOR_UNSECURED),
            _pos(issuer="X", is_long=False, seniority=DRCSeniority.SUBORDINATED, notional=50.0),
        ])
        assert result.net_jtd_long == pytest.approx(25.0)
        assert result.net_jtd_short == pytest.approx(0.0)
        assert result.total_charge == pytest.approx(0.041 * 25.0)

    def test_senior_short_cannot_offset_nonsenior_long(self, calc):
        """(b) Same obligor: short SENIOR may NOT offset long SUBORDINATED.

        Long sub 100 -> JTD 100; short senior 50 -> JTD -37.5; no offset.
        HBR = 100 / 137.5; DRC = 0.041 x 100 - HBR x 0.041 x 37.5.
        """
        result = calc.calculate([
            _pos(issuer="X", is_long=True, seniority=DRCSeniority.SUBORDINATED),
            _pos(issuer="X", is_long=False, seniority=DRCSeniority.SENIOR_UNSECURED,
                 notional=50.0),
        ])
        assert result.net_jtd_long == pytest.approx(100.0)
        assert result.net_jtd_short == pytest.approx(-37.5)
        hbr = 100.0 / 137.5
        assert result.total_charge == pytest.approx(0.041 * 100.0 - hbr * 0.041 * 37.5)

    def test_same_seniority_same_obligor_full_offset(self, calc):
        result = calc.calculate([
            _pos(issuer="X", is_long=True),
            _pos(issuer="X", is_long=False),
        ])
        assert result.total_charge == pytest.approx(0.0)
        assert result.net_jtd_long == pytest.approx(0.0)

    def test_hbr_different_obligors(self, calc):
        """(c) Long 100 / short 50 in different corporate IG obligors -> HBR = 2/3.

        JTD long 75, short -37.5 -> HBR = 75 / 112.5 = 2/3.
        DRC = 0.041 x 75 - (2/3) x 0.041 x 37.5 = 3.075 - 1.025 = 2.05.
        """
        result = calc.calculate([
            _pos(issuer="A", is_long=True),
            _pos(issuer="B", is_long=False, notional=50.0),
        ])
        detail = result.bucket_details[0]
        assert detail.hbr == pytest.approx(2.0 / 3.0)
        assert result.total_charge == pytest.approx(2.05)

    def test_us_treasury_excluded(self, calc):
        """(f) US sovereign exposure is not a default risk position -> 0."""
        result = calc.calculate([
            _pos(issuer="UST", exposure_type=DRCExposureType.US_SOVEREIGN_MDB),
            _pos(issuer="IBRD", is_us_sovereign_or_mdb=True),
        ])
        assert result.total_charge == 0.0
        assert result.excluded_positions == 2
        assert result.gross_jtd_long == 0.0

    def test_non_us_sovereign_bucket(self, calc):
        result = calc.calculate([
            _pos(issuer="DE", exposure_type=DRCExposureType.NON_US_SOVEREIGN),
        ])
        assert result.bucket_charges == {"NON_US_SOVEREIGN": pytest.approx(0.006 * 75.0)}

    def test_pse_gse_bucket_and_gse_lgd(self, calc):
        """GSE guaranteed debt LGD 25%, PSE/GSE IG RW 2.1%."""
        result = calc.calculate([
            _pos(issuer="FNMA", exposure_type=DRCExposureType.PSE_GSE,
                 seniority=DRCSeniority.GSE_GUARANTEED),
        ])
        assert result.gross_jtd_long == pytest.approx(25.0)
        assert result.bucket_charges == {"PSE_GSE": pytest.approx(0.021 * 25.0)}

    def test_defaulted_goes_to_defaulted_bucket(self, calc):
        result = calc.calculate([
            _pos(issuer="DE", exposure_type=DRCExposureType.NON_US_SOVEREIGN,
                 credit_quality=DEF, market_value=30.0),
        ])
        # LGD 100% -> 100 + (30 - 100) = 30; RW 100%
        assert result.bucket_charges == {"DEFAULTED": pytest.approx(30.0)}

    def test_umbs_offset_group_across_gses(self, calc):
        """GSEs are separate obligors unless an explicit offset_group is given (UMBS)."""
        no_group = calc.calculate([
            _pos(issuer="FNMA", exposure_type=DRCExposureType.PSE_GSE,
                 seniority=DRCSeniority.GSE_GUARANTEED, is_long=True),
            _pos(issuer="FHLMC", exposure_type=DRCExposureType.PSE_GSE,
                 seniority=DRCSeniority.GSE_GUARANTEED, is_long=False),
        ])
        grouped = calc.calculate([
            _pos(issuer="FNMA", exposure_type=DRCExposureType.PSE_GSE,
                 seniority=DRCSeniority.GSE_GUARANTEED, is_long=True, offset_group="UMBS"),
            _pos(issuer="FHLMC", exposure_type=DRCExposureType.PSE_GSE,
                 seniority=DRCSeniority.GSE_GUARANTEED, is_long=False, offset_group="UMBS"),
        ])
        assert no_group.total_charge > 0.0
        assert grouped.total_charge == pytest.approx(0.0)

    def test_spec_grade_higher_than_ig(self, calc):
        ig = calc.calculate([_pos(credit_quality=IG)]).total_charge
        spec = calc.calculate([_pos(credit_quality=SPEC)]).total_charge
        sub = calc.calculate([_pos(credit_quality=SUB)]).total_charge
        assert ig < spec < sub

    def test_rating_convenience_input(self, calc):
        via_rating = DRCPosition(
            issuer="A", seniority=DRCSeniority.SENIOR_UNSECURED,
            rating=DRCRatingCategory.BBB, exposure_type=DRCExposureType.CORPORATE,
            notional=100.0, market_value=100.0, maturity_years=5.0, is_long=True,
        )
        assert via_rating.credit_quality is IG
        assert calc.calculate([via_rating]).total_charge == pytest.approx(3.075)

    def test_requires_credit_quality_or_rating(self):
        with pytest.raises(ValueError, match="credit_quality"):
            DRCPosition(
                issuer="A", seniority=DRCSeniority.SENIOR_UNSECURED,
                notional=100.0, market_value=100.0, maturity_years=5.0, is_long=True,
            )

    def test_core_models_position_is_coerced(self, calc):
        """The lightweight src.core.models.DRCPosition is accepted by the calculator."""
        core = CoreDRCPosition(
            issuer="A", seniority=DRCSeniority.SENIOR_UNSECURED,
            rating=DRCRatingCategory.A, exposure_type=DRCExposureType.CORPORATE,
            notional=100.0, market_value=100.0, maturity_years=5.0, is_long=True,
        )
        assert calc.calculate([core]).total_charge == pytest.approx(3.075)

    def test_maturity_scaling(self, calc):
        full = calc.calculate([_pos(maturity_years=5.0)]).total_charge
        half = calc.calculate([_pos(maturity_years=0.5)]).total_charge
        floor = calc.calculate([_pos(maturity_years=0.1)]).total_charge
        assert half == pytest.approx(0.5 * full)
        assert floor == pytest.approx(0.25 * full)

    def test_unhedged_cash_equity_maturity_option(self):
        eq = _pos(seniority=DRCSeniority.EQUITY, maturity_years=0.0, is_cash_equity=True)
        one_year = DRCCalculator(unhedged_cash_equity_maturity_years=1.0).calculate([eq])
        three_month = DRCCalculator(unhedged_cash_equity_maturity_years=0.25).calculate([eq])
        assert one_year.total_charge == pytest.approx(0.041 * 100.0)
        assert three_month.total_charge == pytest.approx(0.25 * 0.041 * 100.0)
        with pytest.raises(ValidationError):
            DRCCalculator(unhedged_cash_equity_maturity_years=0.5)

    def test_cash_equity_hedging_derivative_takes_derivative_maturity(self, calc):
        eq = _pos(seniority=DRCSeniority.EQUITY, maturity_years=0.0, is_cash_equity=True,
                  hedged_derivative_maturity_years=0.5)
        assert calc.calculate([eq]).total_charge == pytest.approx(0.5 * 0.041 * 100.0)

    def test_not_linked_to_recovery_zero_lgd(self, calc):
        result = calc.calculate([
            _pos(seniority=DRCSeniority.NOT_LINKED_TO_RECOVERY, market_value=100.0),
        ])
        assert result.total_charge == pytest.approx(0.0)

    def test_securitization_rejected(self):
        with pytest.raises(ValueError, match="Securitization"):
            _pos(exposure_type=DRCExposureType.SECURITIZATION)

    def test_total_is_sum_of_buckets(self, calc):
        result = calc.calculate([
            _pos(issuer="A"),
            _pos(issuer="DE", exposure_type=DRCExposureType.NON_US_SOVEREIGN),
            _pos(issuer="FNMA", exposure_type=DRCExposureType.PSE_GSE,
                 seniority=DRCSeniority.GSE_UNGUARANTEED),
        ])
        assert len(result.bucket_charges) == 3
        assert result.total_charge == pytest.approx(sum(result.bucket_charges.values()))
