"""Tests for the US securitisation / SA-CVA / leverage / SCCL / CCP adapter."""

from __future__ import annotations

import math

import pytest

from src.jurisdictions.pillar1_base import (
    CCPCalculator,
    CCPExposureInput,
    CVARiskClass,
    CVASensitivityInput,
    LargeExposureInput,
    LargeExposuresCalculator,
    LeverageCalculator,
    LeverageInputs,
    SACVACalculator,
    SecApproachUsed,
    SecTrancheInput,
    SecuritisationCalculator,
)
from src.jurisdictions.us.pillar1 import USPillar1

P = USPillar1()


def test_protocols() -> None:
    for proto in (
        SecuritisationCalculator,
        SACVACalculator,
        LeverageCalculator,
        LargeExposuresCalculator,
        CCPCalculator,
    ):
        assert isinstance(P, proto)


def _ssfa(a: float, d: float, ka: float, p: float) -> float:
    alpha = -1.0 / (p * ka)
    u, lo = d - ka, max(a - ka, 0.0)
    return (math.exp(alpha * u) - math.exp(alpha * lo)) / (alpha * (u - lo))


def test_sec_sa_mezzanine() -> None:
    """§ __.133: RW = 12.5 x K_SSFA above K_A; p = 0.5; K_A = (1-W)K_G + 0.5W."""
    r = P.securitisation(
        SecTrancheInput(
            tranche_id="m",
            exposure_amount=100.0,
            attachment=0.10,
            detachment=0.30,
            k_sa=0.08,
            w=0.0,
        )
    )
    assert r.approach == SecApproachUsed.SEC_SA
    assert r.risk_weight == pytest.approx(12.5 * _ssfa(0.10, 0.30, 0.08, 0.5))


def test_sec_sa_delinquency() -> None:
    ka = (1 - 0.2) * 0.08 + 0.5 * 0.2
    r = P.securitisation(
        SecTrancheInput(
            tranche_id="m",
            exposure_amount=100.0,
            attachment=0.30,
            detachment=0.60,
            k_sa=0.08,
            w=0.2,
        )
    )
    assert r.risk_weight == pytest.approx(max(0.15, 12.5 * _ssfa(0.30, 0.60, ka, 0.5)))


def test_sec_sa_floor_and_1250() -> None:
    senior = P.securitisation(
        SecTrancheInput(
            tranche_id="s", exposure_amount=100.0, attachment=0.4, detachment=1.0, k_sa=0.08
        )
    )
    assert senior.risk_weight == pytest.approx(0.15)
    first = P.securitisation(
        SecTrancheInput(
            tranche_id="f", exposure_amount=100.0, attachment=0.0, detachment=0.05, k_sa=0.08
        )
    )
    assert first.risk_weight == pytest.approx(12.5)
    unknown = P.securitisation(
        SecTrancheInput(tranche_id="u", exposure_amount=100.0, attachment=0.3, detachment=1.0)
    )
    assert unknown.approach == SecApproachUsed.RW_1250


def test_npl_floor() -> None:
    r = P.securitisation(
        SecTrancheInput(
            tranche_id="n",
            exposure_amount=100.0,
            attachment=0.5,
            detachment=1.0,
            k_sa=0.08,
            is_npl_securitisation=True,
        )
    )
    assert r.risk_weight == pytest.approx(1.0)


def test_sa_cva_ir_and_ccs() -> None:
    """§ __.224: USD 5y RW 0.74%; counterparty CS financials IG 5.0%; m_CVA = 1."""
    r = P.sa_cva(
        [
            CVASensitivityInput(
                risk_class=CVARiskClass.INTEREST_RATE,
                measure="DELTA",
                bucket="USD",
                risk_factor="5",
                s_cva=100.0,
            ),
            CVASensitivityInput(
                risk_class=CVARiskClass.COUNTERPARTY_CREDIT_SPREAD,
                measure="DELTA",
                bucket="FINANCIAL",
                risk_factor="5",
                s_cva=50.0,
                name="B",
                is_investment_grade=True,
            ),
        ]
    )
    assert r.k_by_class["INTEREST_RATE:DELTA"] == pytest.approx(0.74)
    assert r.k_by_class["COUNTERPARTY_CREDIT_SPREAD:DELTA"] == pytest.approx(2.5)
    assert r.rwa == pytest.approx(12.5 * r.k_total)


def test_leverage() -> None:
    """12 CFR 217.10(c)(2): PFE x 1.4; 10% minimum CCF."""
    r = P.leverage_exposure(
        LeverageInputs(
            on_balance_sheet_assets=1000.0,
            derivative_rc=10.0,
            derivative_pfe_addon=20.0,
            obs_notional_by_ccf={0.0: 100.0, 0.4: 100.0},
        )
    )
    assert r.total_exposure == pytest.approx(1000 + 10 + 28 + 10 + 40)


def test_sccl_limits() -> None:
    rows = P.large_exposures(
        [
            LargeExposureInput(counterparty_id="g", exposure_value=16.0, counterparty_is_gsib=True),
            LargeExposureInput(counterparty_id="c", exposure_value=16.0),
        ],
        100.0,
        True,
    )
    assert rows[0].limit_pct_of_tier1 == 0.15 and rows[0].breach
    assert rows[1].limit_pct_of_tier1 == 0.25 and not rows[1].breach


def test_ccp() -> None:
    q = P.ccp_exposure(
        CCPExposureInput(
            ccp_id="q",
            trade_exposure=100.0,
            default_fund_contribution=10.0,
            k_ccp=50.0,
            total_default_fund=1000.0,
        )
    )
    assert q.trade_rwa == pytest.approx(2.0) and q.default_fund_rwa == pytest.approx(12.5 * 0.5)
    nq = P.ccp_exposure(
        CCPExposureInput(
            ccp_id="n", is_qualifying=False, trade_exposure=100.0, default_fund_contribution=10.0
        )
    )
    assert nq.default_fund_rwa == pytest.approx(125.0)
