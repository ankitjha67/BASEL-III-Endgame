"""Map synthetic trading positions to FRTB-SA inputs (sensitivities and DRC positions).

The synthetic :class:`~src.data_generation.portfolio_generator.PortfolioGenerator`
produces outright, unhedged trading positions. This module converts them into
the inputs of :class:`~src.market_risk.frtb.calculator.FRTBCalculator`:

- ``delta_sensitivity`` is read as PV01 ($M per basis point) for GIRR and
  CSR, and as the $M P&L of a 1% relative move for equity, commodity and FX.
  The SBM sensitivity is then PV01 / 0.0001 or P&L / 0.01 (ERBA NPR
  § __.207(b); MAR21.8-21.25).
- Every sensitivity is multiplied by ``net_fraction``: a dealer book is mostly
  hedged, so only this fraction of the generator's gross sensitivity is
  treated as the net exposure. This is a synthetic-data calibration, NOT a
  regulatory parameter.

All amounts in USD millions ($M).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np

from src.core.enums import (
    DRCExposureType,
    DRCRatingCategory,
    DRCSeniority,
    GIRRRiskFactorType,
    GIRRTenor,
    RiskClass,
    RiskMeasure,
)
from src.core.models import DRCPosition, Sensitivity

DEFAULT_NET_FRACTION: Final[float] = 0.35
"""Share of gross synthetic sensitivity treated as net (unhedged) exposure.

Synthetic calibration only: chosen so FRTB-SA capital for the synthetic
$3.2T bank lands in the range Category I firms report (~$10-25B)."""

PV01_SHOCK: Final[float] = 1e-4
"""1 basis point (§ __.207(b) GIRR/CSR delta sensitivity definition)."""
RELATIVE_SHOCK: Final[float] = 0.01
"""1% relative move (§ __.207(b) equity, commodity and FX delta sensitivity definition)."""

DRC_NOTIONAL_SHARE: Final[float] = 0.10
"""Synthetic: bond notional held for each CSR position as a DRC jump-to-default exposure."""
DRC_PRICE: Final[float] = 0.98
"""Synthetic market value per unit notional for the DRC positions."""
DRC_MATURITY_YEARS: Final[float] = 3.0

GIRR_TENORS: Final[dict[str, GIRRTenor]] = {
    "3M": GIRRTenor.Y0_25,
    "6M": GIRRTenor.Y0_5,
    "1Y": GIRRTenor.Y1,
    "2Y": GIRRTenor.Y2,
    "3Y": GIRRTenor.Y3,
    "5Y": GIRRTenor.Y5,
    "10Y": GIRRTenor.Y10,
    "30Y": GIRRTenor.Y30,
}
"""Generator tenor labels -> GIRR vertices (§ __.209 Table 1: no 7Y/25Y in the US)."""

CSR_TENORS: Final[dict[str, GIRRTenor]] = {
    "3M": GIRRTenor.Y0_5,
    "6M": GIRRTenor.Y0_5,
    "1Y": GIRRTenor.Y1,
    "2Y": GIRRTenor.Y3,
    "3Y": GIRRTenor.Y3,
    "5Y": GIRRTenor.Y5,
    "10Y": GIRRTenor.Y10,
    "30Y": GIRRTenor.Y10,
}
"""Generator tenor labels -> CSR vertices (0.5, 1, 3, 5, 10 years)."""

EQUITY_MAX_BUCKET: Final[int] = 13
COMMODITY_MAX_BUCKET: Final[int] = 12
OPTION_MATURITY_YEARS: Final[float] = 1.0


def trading_positions_to_frtb_inputs(
    positions: Sequence[object],
    rng: np.random.Generator,
    net_fraction: float = DEFAULT_NET_FRACTION,
) -> tuple[list[Sensitivity], list[DRCPosition]]:
    """Convert generator trading positions to SBM sensitivities and DRC positions.

    Args:
        positions: ``PortfolioGenerator.generate_trading_portfolio().positions``.
        rng: Random generator used to assign synthetic DRC ratings.
        net_fraction: See :data:`DEFAULT_NET_FRACTION`.

    Returns:
        (sensitivities, drc_positions).
    """
    sens: list[Sensitivity] = []
    drc: list[DRCPosition] = []
    for pos in positions:
        b = int(pos.bucket)  # type: ignore[attr-defined]
        rc = pos.risk_class  # type: ignore[attr-defined]
        delta = net_fraction * pos.delta_sensitivity  # type: ignore[attr-defined]
        pid = pos.position_id  # type: ignore[attr-defined]
        itype = pos.instrument_type  # type: ignore[attr-defined]
        if rc == "GIRR":
            sens.append(
                Sensitivity(
                    risk_class=RiskClass.GIRR,
                    risk_measure=RiskMeasure.DELTA,
                    bucket=pos.currency,  # type: ignore[attr-defined]
                    risk_factor_type=GIRRRiskFactorType.YIELD_CURVE,
                    tenor=GIRR_TENORS[pos.tenor],  # type: ignore[attr-defined]
                    label="OIS",
                    value=delta / PV01_SHOCK,
                )
            )
        elif rc == "CSR_NONSEC":
            issuer = f"ISSUER{b:02d}"
            sens.append(
                Sensitivity(
                    risk_class=RiskClass.CSR_NON_SEC,
                    risk_measure=RiskMeasure.DELTA,
                    bucket=str(b),
                    tenor=CSR_TENORS[pos.tenor],  # type: ignore[attr-defined]
                    label=f"{issuer}::BOND",
                    value=delta / PV01_SHOCK,
                )
            )
            notional = pos.notional * DRC_NOTIONAL_SHARE  # type: ignore[attr-defined]
            drc.append(
                DRCPosition(
                    issuer=issuer,
                    seniority=DRCSeniority.SENIOR_UNSECURED,
                    rating=rng.choice(
                        [DRCRatingCategory.A, DRCRatingCategory.BBB, DRCRatingCategory.BB]
                    ),
                    exposure_type=DRCExposureType.CORPORATE,
                    notional=notional,
                    market_value=notional * DRC_PRICE,
                    maturity_years=DRC_MATURITY_YEARS,
                    is_long=pos.delta_sensitivity >= 0,
                )
            )  # type: ignore[attr-defined]
        elif rc == "EQUITY":
            bucket = str(min(b, EQUITY_MAX_BUCKET))
            sens.append(
                Sensitivity(
                    risk_class=RiskClass.EQUITY,
                    risk_measure=RiskMeasure.DELTA,
                    bucket=bucket,
                    label=f"EQ{pid}",
                    value=delta / RELATIVE_SHOCK,
                )
            )
            if itype == "EQUITY_OPTION":
                sens.append(
                    Sensitivity(
                        risk_class=RiskClass.EQUITY,
                        risk_measure=RiskMeasure.VEGA,
                        bucket=bucket,
                        label=f"EQ{pid}",
                        value=net_fraction * pos.vega_sensitivity,  # type: ignore[attr-defined]
                        option_maturity=OPTION_MATURITY_YEARS,
                    )
                )
                sens.append(
                    Sensitivity(
                        risk_class=RiskClass.EQUITY,
                        risk_measure=RiskMeasure.CURVATURE,
                        bucket=bucket,
                        label=f"EQ{pid}",
                        value=net_fraction * pos.curvature_sensitivity,
                    )
                )  # type: ignore[attr-defined]
        elif rc == "COMMODITY":
            sens.append(
                Sensitivity(
                    risk_class=RiskClass.COMMODITY,
                    risk_measure=RiskMeasure.DELTA,
                    bucket=str(min(b, COMMODITY_MAX_BUCKET)),
                    label=f"CMD{b}",
                    value=delta / RELATIVE_SHOCK,
                )
            )
        elif rc == "FX":
            ccy = pos.currency if pos.currency != "USD" else "EUR"  # type: ignore[attr-defined]
            sens.append(
                Sensitivity(
                    risk_class=RiskClass.FX,
                    risk_measure=RiskMeasure.DELTA,
                    bucket=f"{ccy}USD",
                    label=f"{ccy}USD",
                    value=delta / RELATIVE_SHOCK,
                )
            )
            if itype == "FX_OPTION":
                sens.append(
                    Sensitivity(
                        risk_class=RiskClass.FX,
                        risk_measure=RiskMeasure.VEGA,
                        bucket=f"{ccy}USD",
                        label=f"{ccy}USD",
                        value=net_fraction * pos.vega_sensitivity,  # type: ignore[attr-defined]
                        option_maturity=OPTION_MATURITY_YEARS,
                    )
                )
    return sens, drc
