"""Tests for the CVA calculator entry point — ERBA NPR §__.201(b)(2), §__.202, §__.221–§__.223.

All monetary values in USD millions ($M).
"""

from __future__ import annotations

import math

import pytest

from src.cva_risk import (
    BA_CVA_RISK_WEIGHTS,
    CVAApproach,
    CVACalculator,
    CVACounterparty,
    CVAHedge,
    CVASector,
    SACVARiskFactorType,
    SACVASensitivity,
    determine_cva_scope,
    determine_eligibility,
    is_cva_risk_covered_position,
)


def cp(cp_id: str = "CP1", **kw) -> CVACounterparty:
    d = dict(counterparty_id=cp_id, sector="FINANCIALS", credit_quality="IG",
             ead=100.0, effective_maturity=2.0)
    d.update(kw)
    return CVACounterparty(**d)


@pytest.fixture
def calc() -> CVACalculator:
    return CVACalculator()


class TestScope:
    def test_category_i_ii_hc(self) -> None:
        assert determine_cva_scope(is_category_i_or_ii_holding_company=True).in_scope

    def test_di_subsidiary_needs_market_risk(self) -> None:
        assert not determine_cva_scope(is_subsidiary_di_of_category_i_or_ii=True).in_scope
        assert determine_cva_scope(is_subsidiary_di_of_category_i_or_ii=True,
                                   subject_to_market_risk_rule=True).in_scope

    def test_one_trillion_threshold_four_quarter_average(self) -> None:
        # $M: 1 trillion = 1,000,000
        over = [900_000.0, 1_100_000.0, 1_000_000.0, 1_000_000.0]
        under = [900_000.0, 900_000.0, 1_100_000.0, 1_000_000.0]
        assert determine_cva_scope(subject_to_market_risk_rule=True,
                                   quarterly_otc_gross_notional=over).in_scope
        assert not determine_cva_scope(subject_to_market_risk_rule=True,
                                       quarterly_otc_gross_notional=under).in_scope
        assert not determine_cva_scope(subject_to_market_risk_rule=False,
                                       quarterly_otc_gross_notional=over).in_scope
        r = determine_cva_scope(subject_to_market_risk_rule=True,
                                quarterly_otc_gross_notional=[0.0] + over)
        assert r.average_otc_gross_notional == pytest.approx(1_000_000.0)

    def test_supervisory_override(self) -> None:
        assert not determine_cva_scope(is_category_i_or_ii_holding_company=True,
                                       supervisory_override=False).in_scope
        assert determine_cva_scope(supervisory_override=True).in_scope

    def test_covered_position(self) -> None:
        assert is_cva_risk_covered_position(is_derivative=True)
        assert not is_cva_risk_covered_position(is_derivative=True, is_cleared_transaction=True)
        assert not is_cva_risk_covered_position(is_derivative=True, is_client_facing_derivative=True)
        assert not is_cva_risk_covered_position(is_derivative=False, is_sft=True)
        assert not is_cva_risk_covered_position(is_derivative=True, is_sft=True)
        assert not is_cva_risk_covered_position(is_derivative=True, is_crm_recognized_credit_derivative=True)
        assert is_cva_risk_covered_position(is_derivative=True, is_crm_recognized_credit_derivative=True,
                                            exclude_crm_credit_derivatives=False)


class TestEligibility:
    def test_default_is_reduced_ba_cva(self) -> None:
        assert determine_eligibility().recommended_approach is CVAApproach.BA_CVA_REDUCED

    def test_hedges_give_full_ba_cva(self) -> None:
        assert determine_eligibility(has_eligible_hedges=True).recommended_approach is CVAApproach.BA_CVA_FULL

    def test_sa_cva_requires_all_conditions(self) -> None:
        kw = dict(has_cva_desk=True, has_cva_sensitivities=True, supervisory_approval=True)
        assert determine_eligibility(**kw).recommended_approach is CVAApproach.SA_CVA
        assert determine_eligibility(uses_saccr=False, **kw).recommended_approach is not CVAApproach.SA_CVA
        assert determine_eligibility(has_cva_desk=True, has_cva_sensitivities=True).recommended_approach \
            is not CVAApproach.SA_CVA


class TestCalculator:
    def test_basic_measure_default(self, calc) -> None:
        result = calc.calculate([cp()])
        df2 = (1 - math.exp(-0.1)) / 0.1
        scva = (1 / 1.4) * 0.05 * 2.0 * 100.0 * df2
        assert result.approach is CVAApproach.BA_CVA_REDUCED
        assert result.k_cva == pytest.approx(0.65 * scva)
        assert result.rwa == pytest.approx(12.5 * 0.65 * scva)
        assert result.k_unhedged == pytest.approx(scva)
        assert result.total_ead == 100.0
        assert result.counterparty_count == 1
        assert result.counterparty_rwa["CP1"] == pytest.approx(result.rwa)
        assert result.sector_rwa["FINANCIALS"] == pytest.approx(result.rwa)

    def test_hedges_select_full_ba_cva(self, calc) -> None:
        hedge = CVAHedge(hedge_id="H", hedge_type="SINGLE_NAME_CDS", counterparty_id="CP1",
                         notional=30.0, maturity=2.0, reference_sector="FINANCIALS",
                         reference_credit_quality="IG")
        result = calc.calculate([cp()], [hedge])
        assert result.approach is CVAApproach.BA_CVA_FULL
        assert result.hedge_count == 1
        assert 0.0 < result.hedge_benefit_pct < 100.0
        assert result.k_cva < calc.calculate([cp()]).k_cva

    def test_legacy_labels_and_sector_breakdown(self, calc) -> None:
        cps = [
            cp("A", sector="FINANCIAL", rating="A", credit_quality=None, ead=100.0),
            cp("B", sector="CORPORATE", rating="BB", credit_quality=None, ead=200.0),
        ]
        result = calc.calculate(cps)
        assert "FINANCIALS" in result.sector_rwa and "OTHER_SECTOR" in result.sector_rwa
        assert set(result.counterparty_rwa) == {"A", "B"}
        assert sum(result.counterparty_rwa.values()) == pytest.approx(result.rwa)
        assert result.total_ead == pytest.approx(300.0)

    def test_sa_cva_requires_sensitivities(self, calc) -> None:
        with pytest.raises(ValueError, match="sensitivities"):
            calc.calculate([cp()], approach=CVAApproach.SA_CVA)

    def test_standardized_measure_with_carve_outs(self, calc) -> None:
        """K = K_SA-CVA + K_BA-CVA(carve-outs); RWA = 12.5·K."""
        sens = [SACVASensitivity(risk_class=SACVARiskFactorType.INTEREST_RATE, currency="USD",
                                 tenor=5.0, cva_sensitivity=100.0)]
        result = calc.calculate(counterparties=[cp()], sensitivities=sens, approach=CVAApproach.SA_CVA)
        ba_only = calc.calculate([cp()])
        assert result.approach is CVAApproach.SA_CVA
        assert result.k_sa_cva == pytest.approx(0.74)
        assert result.k_ba_cva == pytest.approx(ba_only.k_cva)
        assert result.k_cva == pytest.approx(0.74 + ba_only.k_cva)
        assert result.rwa == pytest.approx(12.5 * result.k_cva)
        assert result.risk_class_rwa["INTEREST_RATE:DELTA"] == pytest.approx(12.5 * 0.74)
        assert result.sa_cva_result is not None and result.ba_cva_result is not None

    def test_standardized_measure_auto_selected(self, calc) -> None:
        sens = [SACVASensitivity(risk_class=SACVARiskFactorType.FX, currency="EUR", cva_sensitivity=10.0)]
        result = calc.calculate(sensitivities=sens, has_cva_desk=True, has_cva_sensitivities=True,
                                supervisory_approval=True)
        assert result.approach is CVAApproach.SA_CVA
        assert result.k_cva == pytest.approx(1.1)
        assert result.k_ba_cva == 0.0

    def test_m_cva_passthrough(self) -> None:
        sens = [SACVASensitivity(risk_class=SACVARiskFactorType.FX, currency="EUR", cva_sensitivity=10.0)]
        r = CVACalculator(m_cva=2.0).calculate(sensitivities=sens, approach=CVAApproach.SA_CVA)
        assert r.k_cva == pytest.approx(2.2)

    def test_compute_rwa_and_empty(self, calc) -> None:
        assert calc.compute_rwa([cp()]) > 0
        empty = calc.calculate([])
        assert empty.k_cva == 0.0 and empty.rwa == 0.0


class TestImports:
    def test_public_api(self) -> None:
        from src.cva_risk import (  # noqa: F401
            SACCR_ALPHA_COMMERCIAL,
            SACCR_ALPHA_FINANCIAL,
            BACVACalculator,
            BACVACounterparty,
            BACVAHedge,
            CVACreditQuality,
            SACVACalculator,
        )
        assert SACCR_ALPHA_FINANCIAL == 1.4 and SACCR_ALPHA_COMMERCIAL == 1.0
        assert len(BA_CVA_RISK_WEIGHTS) == 24
        assert len(CVASector) == 8
