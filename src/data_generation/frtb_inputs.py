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


# =========================================================================
#  Regime-neutral inputs (src.jurisdictions.frtb_base)
# =========================================================================

TENOR_YEARS: Final[dict[str, float]] = {
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "5Y": 5.0,
    "10Y": 10.0,
    "30Y": 30.0,
}
"""Generator tenor labels in years (GIRR vertices common to MAR21.8 and § __.208)."""

CSR_TENOR_YEARS: Final[dict[str, float]] = {k: v.value for k, v in CSR_TENORS.items()}
"""Generator tenor labels -> CSR vertices (0.5, 1, 3, 5, 10 years; MAR21.10)."""


def trading_positions_to_neutral_frtb(
    positions: Sequence[object],
    rng: np.random.Generator,
    net_fraction: float = DEFAULT_NET_FRACTION,
) -> tuple[list[object], list[object]]:
    """Generator positions -> regime-neutral FRTB sensitivities and DRC positions.

    The generator labels CSR, equity and commodity positions with US bucket
    numbers (Tables 3, 8 and 9 to ERBA NPR § __.209); those numbers are
    translated back into the descriptors (sector, credit quality, market cap,
    economy, commodity group) each regime uses to assign its own bucket, so
    the US adapter reproduces the US calculation exactly.

    Returns:
        (list[FRTBSensitivity], list[DRCPositionInput]).
    """
    from src.core.enums import CreditQuality
    from src.jurisdictions.base import RatingBucket
    from src.jurisdictions.frtb_base import (
        CommodityGroup,
        CreditSector,
        DRCPositionInput,
        EquitySector,
        FRTBMeasure,
        FRTBRiskClass,
        FRTBSensitivity,
    )
    from src.jurisdictions.frtb_base import DRCSeniority as NeutralSeniority
    from src.market_risk.frtb.sbm.csr_nonsec_params import BUCKET_SECTOR_QUALITY

    sector_of = {
        "SOVEREIGN": CreditSector.SOVEREIGN,
        "PSE": CreditSector.LOCAL_GOVERNMENT,
        "FINANCIALS": CreditSector.FINANCIAL,
        "BASIC_MATERIALS": CreditSector.BASIC_MATERIALS,
        "CONSUMER": CreditSector.CONSUMER,
        "TECH_TELECOM": CreditSector.TECHNOLOGY,
        "HEALTHCARE_UTILITIES": CreditSector.HEALTH_CARE,
        "COVERED_BOND": CreditSector.COVERED_BOND,
        "OTHER": CreditSector.OTHER,
        "INDEX": CreditSector.INDEX,
    }
    eq_sector = [
        EquitySector.CONSUMER_HEALTH_UTILITIES,
        EquitySector.TELECOM_INDUSTRIALS,
        EquitySector.MATERIALS_ENERGY,
        EquitySector.FINANCIALS_REALESTATE_TECH,
    ]
    commodity = [
        CommodityGroup.ENERGY_SOLID,
        CommodityGroup.ENERGY_LIQUID,
        CommodityGroup.ENERGY_ELECTRICITY_CARBON,
        CommodityGroup.FREIGHT,
        CommodityGroup.METALS_NON_PRECIOUS,
        CommodityGroup.GASEOUS_ENERGY,
        CommodityGroup.PRECIOUS_METALS,
        CommodityGroup.GRAINS_OILSEED,
        CommodityGroup.LIVESTOCK_DAIRY,
        CommodityGroup.SOFTS_OTHER_AGRI,
        CommodityGroup.OTHER,
    ]
    ratings = [
        (RatingBucket.A_PLUS_TO_A_MINUS, True),
        (RatingBucket.BBB_PLUS_TO_BBB_MINUS, True),
        (RatingBucket.BB_PLUS_TO_BB_MINUS, False),
    ]

    sens: list[object] = []
    drc: list[object] = []
    for pos in positions:
        b = int(pos.bucket)  # type: ignore[attr-defined]
        rc = pos.risk_class  # type: ignore[attr-defined]
        delta = net_fraction * pos.delta_sensitivity  # type: ignore[attr-defined]
        pid = str(pos.position_id)  # type: ignore[attr-defined]
        itype = pos.instrument_type  # type: ignore[attr-defined]
        if rc == "GIRR":
            sens.append(
                FRTBSensitivity(
                    risk_class=FRTBRiskClass.GIRR,
                    measure=FRTBMeasure.DELTA,
                    currency=str(pos.currency),
                    tenor_years=TENOR_YEARS[str(pos.tenor)],  # type: ignore[attr-defined]
                    curve_name="OIS",
                    value=delta / PV01_SHOCK,
                )
            )
        elif rc == "CSR_NONSEC":
            sec, quals = BUCKET_SECTOR_QUALITY[b]
            ig = CreditQuality.INVESTMENT_GRADE in quals
            issuer = f"ISSUER{b:02d}"
            sens.append(
                FRTBSensitivity(
                    risk_class=FRTBRiskClass.CSR_NONSEC,
                    measure=FRTBMeasure.DELTA,
                    issuer=issuer,
                    credit_sector=sector_of[sec.name],
                    is_investment_grade=ig,
                    rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS
                    if ig
                    else RatingBucket.BB_PLUS_TO_BB_MINUS,
                    tenor_years=CSR_TENOR_YEARS[str(pos.tenor)],  # type: ignore[attr-defined]
                    value=delta / PV01_SHOCK,
                )
            )
            notional = pos.notional * DRC_NOTIONAL_SHARE  # type: ignore[attr-defined]
            rb, rig = ratings[int(rng.integers(0, len(ratings)))]
            drc.append(
                DRCPositionInput(
                    position_id=f"DRC-{pid}",
                    obligor=issuer,
                    is_long=pos.delta_sensitivity >= 0,  # type: ignore[attr-defined]
                    notional=notional,
                    market_value=notional * DRC_PRICE,
                    pnl=notional * (DRC_PRICE - 1.0),
                    maturity_years=DRC_MATURITY_YEARS,
                    seniority=NeutralSeniority.SENIOR,
                    rating=rb,
                    is_investment_grade=rig,
                    credit_sector=CreditSector.CONSUMER,
                )
            )
        elif rc == "EQUITY":
            bucket = min(b, EQUITY_MAX_BUCKET)
            kw: dict[str, object] = {}
            if bucket <= 8:
                kw = {
                    "is_large_cap": True,
                    "is_advanced_economy": bucket > 4,
                    "equity_sector": eq_sector[(bucket - 1) % 4],
                }
            elif bucket in (9, 10):
                kw = {
                    "is_large_cap": False,
                    "is_advanced_economy": bucket == 10,
                    "equity_sector": EquitySector.CONSUMER_HEALTH_UTILITIES,
                }
            elif bucket == 11:
                kw = {
                    "is_large_cap": True,
                    "is_advanced_economy": True,
                    "equity_sector": EquitySector.OTHER,
                }
            else:
                kw = {
                    "is_equity_index": True,
                    "is_large_cap": bucket == 12,
                    "is_advanced_economy": bucket == 12,
                }
            name = f"EQ{pid}"
            sens.append(
                FRTBSensitivity(
                    risk_class=FRTBRiskClass.EQUITY,
                    measure=FRTBMeasure.DELTA,
                    issuer=name,
                    value=delta / RELATIVE_SHOCK,
                    **kw,
                )
            )  # type: ignore[arg-type]
            if itype == "EQUITY_OPTION":
                vega = net_fraction * pos.vega_sensitivity  # type: ignore[attr-defined]
                curv = net_fraction * pos.curvature_sensitivity  # type: ignore[attr-defined]
                sens.append(
                    FRTBSensitivity(
                        risk_class=FRTBRiskClass.EQUITY,
                        measure=FRTBMeasure.VEGA,
                        issuer=name,
                        value=vega,
                        option_maturity_years=OPTION_MATURITY_YEARS,
                        **kw,
                    )
                )  # type: ignore[arg-type]
                sens.append(
                    FRTBSensitivity(
                        risk_class=FRTBRiskClass.EQUITY,
                        measure=FRTBMeasure.CURVATURE,
                        issuer=name,
                        cvr_up=curv,
                        cvr_down=curv,
                        **kw,
                    )
                )  # type: ignore[arg-type]
        elif rc == "COMMODITY":
            bucket = min(b, COMMODITY_MAX_BUCKET)
            group_kw: dict[str, object] = (
                {"flags": {"commodity_index": True}}
                if bucket == COMMODITY_MAX_BUCKET
                else {"commodity_group": commodity[bucket - 1]}
            )
            sens.append(
                FRTBSensitivity(
                    risk_class=FRTBRiskClass.COMMODITY,
                    measure=FRTBMeasure.DELTA,
                    commodity_name=f"CMD{b}",
                    delivery_location=f"CMD{b}",
                    value=delta / RELATIVE_SHOCK,
                    **group_kw,
                )
            )  # type: ignore[arg-type]
        elif rc == "FX":
            ccy = str(pos.currency) if str(pos.currency) != "USD" else "EUR"  # type: ignore[attr-defined]
            sens.append(
                FRTBSensitivity(
                    risk_class=FRTBRiskClass.FX,
                    measure=FRTBMeasure.DELTA,
                    fx_currency=ccy,
                    value=delta / RELATIVE_SHOCK,
                )
            )
            if itype == "FX_OPTION":
                sens.append(
                    FRTBSensitivity(
                        risk_class=FRTBRiskClass.FX,
                        measure=FRTBMeasure.VEGA,
                        fx_currency=ccy,
                        value=net_fraction * pos.vega_sensitivity,  # type: ignore[attr-defined]
                        option_maturity_years=OPTION_MATURITY_YEARS,
                    )
                )
    return sens, drc
