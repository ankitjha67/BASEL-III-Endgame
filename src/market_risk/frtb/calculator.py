"""Master FRTB Calculator.

Orchestrates all FRTB components:
- SBM: GIRR, CSR Non-Sec, CSR Sec (Non-CTP + CTP), Equity, Commodity, FX
- DRC: Default Risk Charge (Non-Sec)
- RRAO: Residual Risk Add-On

Produces the total FRTB capital charge per MAR21-MAR23 of the Basel III
Endgame framework.

Reference: BCBS d457 MAR21-MAR23, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from pydantic import BaseModel, Field

from src.core.enums import RiskClass, RiskMeasure
from src.core.exceptions import CalculationError, ValidationError
from src.core.models import Sensitivity

logger = logging.getLogger(__name__)


# =========================================================================
#  Result Model
# =========================================================================

class FRTBResult(BaseModel):
    """Complete FRTB capital charge result.

    Captures SBM results by risk class, DRC, RRAO, and aggregated totals
    for regulatory reporting (FR Y-9C / Pillar 3 MR1-MR4).
    """

    # SBM results by risk class -------------------------------------------
    girr_charge: float = Field(default=0.0, description="GIRR SBM charge (delta + vega + curvature)")
    csr_nonsec_charge: float = Field(default=0.0, description="CSR Non-Sec SBM charge")
    csr_sec_nonctp_charge: float = Field(default=0.0, description="CSR Sec Non-CTP SBM charge")
    csr_sec_ctp_charge: float = Field(default=0.0, description="CSR Sec CTP SBM charge")
    equity_charge: float = Field(default=0.0, description="Equity SBM charge")
    commodity_charge: float = Field(default=0.0, description="Commodity SBM charge")
    fx_charge: float = Field(default=0.0, description="FX SBM charge")

    # SBM subtotals -------------------------------------------------------
    sbm_delta: float = Field(default=0.0, description="Total SBM delta charge across all risk classes")
    sbm_vega: float = Field(default=0.0, description="Total SBM vega charge across all risk classes")
    sbm_curvature: float = Field(default=0.0, description="Total SBM curvature charge across all risk classes")
    sbm_total: float = Field(default=0.0, description="Total SBM charge = delta + vega + curvature")

    # DRC -----------------------------------------------------------------
    drc_nonsec: float = Field(default=0.0, description="DRC Non-Sec charge")
    drc_total: float = Field(default=0.0, description="Total DRC charge")

    # RRAO ----------------------------------------------------------------
    rrao_total: float = Field(default=0.0, description="Total RRAO charge")

    # Component detail (optional, for reporting) --------------------------
    girr_delta: float = Field(default=0.0, description="GIRR delta sub-charge")
    girr_vega: float = Field(default=0.0, description="GIRR vega sub-charge")
    girr_curvature: float = Field(default=0.0, description="GIRR curvature sub-charge")
    csr_nonsec_delta: float = Field(default=0.0, description="CSR Non-Sec delta sub-charge")
    csr_nonsec_vega: float = Field(default=0.0, description="CSR Non-Sec vega sub-charge")
    csr_nonsec_curvature: float = Field(default=0.0, description="CSR Non-Sec curvature sub-charge")
    csr_sec_nonctp_delta: float = Field(default=0.0, description="CSR Sec Non-CTP delta sub-charge")
    csr_sec_nonctp_vega: float = Field(default=0.0, description="CSR Sec Non-CTP vega sub-charge")
    csr_sec_nonctp_curvature: float = Field(default=0.0, description="CSR Sec Non-CTP curvature sub-charge")
    csr_sec_ctp_delta: float = Field(default=0.0, description="CSR Sec CTP delta sub-charge")
    csr_sec_ctp_vega: float = Field(default=0.0, description="CSR Sec CTP vega sub-charge")
    csr_sec_ctp_curvature: float = Field(default=0.0, description="CSR Sec CTP curvature sub-charge")
    equity_delta: float = Field(default=0.0, description="Equity delta sub-charge")
    equity_vega: float = Field(default=0.0, description="Equity vega sub-charge")
    equity_curvature: float = Field(default=0.0, description="Equity curvature sub-charge")
    commodity_delta: float = Field(default=0.0, description="Commodity delta sub-charge")
    commodity_vega: float = Field(default=0.0, description="Commodity vega sub-charge")
    commodity_curvature: float = Field(default=0.0, description="Commodity curvature sub-charge")
    fx_delta: float = Field(default=0.0, description="FX delta sub-charge")
    fx_vega: float = Field(default=0.0, description="FX vega sub-charge")
    fx_curvature: float = Field(default=0.0, description="FX curvature sub-charge")

    @property
    def total_capital_charge(self) -> float:
        """Grand total FRTB capital charge = SBM + DRC + RRAO."""
        return self.sbm_total + self.drc_total + self.rrao_total

    @property
    def total_rwa(self) -> float:
        """Total risk-weighted assets = 12.5 x capital charge."""
        return 12.5 * self.total_capital_charge


# =========================================================================
#  Sensitivity Partitioner
# =========================================================================

_RISK_CLASS_MAP: dict[RiskClass, str] = {
    RiskClass.GIRR: "girr",
    RiskClass.CSR_NON_SEC: "csr_nonsec",
    RiskClass.CSR_SEC_NON_CTP: "csr_sec_nonctp",
    RiskClass.CSR_SEC_CTP: "csr_sec_ctp",
    RiskClass.EQUITY: "equity",
    RiskClass.COMMODITY: "commodity",
    RiskClass.FX: "fx",
}


def _partition_sensitivities(
    sensitivities: list[Sensitivity],
) -> dict[RiskClass, list[Sensitivity]]:
    """Partition sensitivities by risk class.

    Args:
        sensitivities: Mixed list of sensitivities across all risk classes.

    Returns:
        Dictionary mapping each :class:`RiskClass` to its sensitivities.
        Risk classes with no sensitivities are not included.
    """
    partitioned: dict[RiskClass, list[Sensitivity]] = defaultdict(list)
    for s in sensitivities:
        partitioned[s.risk_class].append(s)
    return dict(partitioned)


# =========================================================================
#  Master FRTB Calculator
# =========================================================================

class FRTBCalculator:
    """Master FRTB calculator that orchestrates all components.

    Ties together all SBM risk classes, DRC, and RRAO into a single
    entry point for computing the total FRTB capital charge.

    Usage::

        calculator = FRTBCalculator()
        result = calculator.calculate(
            sensitivities=all_sensitivities,
            drc_positions=drc_positions,
            rrao_positions=rrao_positions,
        )
        print(result.total_capital_charge)
        print(calculator.summary(result))
    """

    # --------------------------------------------------------------------- #
    #  Initialization                                                        #
    # --------------------------------------------------------------------- #

    def __init__(self) -> None:
        """Initialize all sub-calculators.

        Imports are deferred to avoid circular dependencies and to allow
        the calculator to be instantiated even if some modules are still
        under development (missing calculators will log a warning).
        """
        self._girr = None
        self._csr_nonsec = None
        self._csr_sec = None
        self._equity = None
        self._commodity = None
        self._fx = None
        self._drc = None
        self._rrao = None

        # Attempt to import each sub-calculator; log warnings for any
        # that are not yet available.
        try:
            from src.market_risk.frtb.sbm.girr import GIRRCalculator
            self._girr = GIRRCalculator()
        except ImportError:
            logger.warning("GIRRCalculator not available; GIRR charges will be zero.")

        try:
            from src.market_risk.frtb.sbm.csr_nonsec import CSRNonSecCalculator
            self._csr_nonsec = CSRNonSecCalculator()
        except ImportError:
            logger.warning("CSRNonSecCalculator not available; CSR Non-Sec charges will be zero.")

        try:
            from src.market_risk.frtb.sbm.csr_sec import CSRSecCalculator
            self._csr_sec = CSRSecCalculator()
        except ImportError:
            logger.warning("CSRSecCalculator not available; CSR Sec charges will be zero.")

        try:
            from src.market_risk.frtb.sbm.equity import EquityCalculator
            self._equity = EquityCalculator()
        except ImportError:
            logger.warning("EquityCalculator not available; Equity charges will be zero.")

        try:
            from src.market_risk.frtb.sbm.commodity import CommodityCalculator
            self._commodity = CommodityCalculator()
        except ImportError:
            logger.warning("CommodityCalculator not available; Commodity charges will be zero.")

        try:
            from src.market_risk.frtb.sbm.fx import FXCalculator
            self._fx = FXCalculator()
        except ImportError:
            logger.warning("FXCalculator not available; FX charges will be zero.")

        try:
            from src.market_risk.frtb.drc.drc_nonsec import DRCCalculator
            self._drc = DRCCalculator()
        except ImportError:
            logger.warning("DRCCalculator not available; DRC charges will be zero.")

        try:
            from src.market_risk.frtb.rrao.rrao import RRAOCalculator
            self._rrao = RRAOCalculator()
        except ImportError:
            logger.warning("RRAOCalculator not available; RRAO charges will be zero.")

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(
        self,
        sensitivities: Optional[list[Sensitivity]] = None,
        drc_positions: Optional[list] = None,
        rrao_positions: Optional[list] = None,
    ) -> FRTBResult:
        """Calculate total FRTB capital charge.

        Partitions sensitivities by risk class, runs each SBM calculator,
        runs DRC and RRAO, then aggregates all results into an
        :class:`FRTBResult`.

        Args:
            sensitivities: List of SBM sensitivities across all risk classes.
                Each sensitivity must have a valid ``risk_class`` attribute.
            drc_positions: List of DRC positions for the Default Risk Charge.
            rrao_positions: List of positions for the Residual Risk Add-On.

        Returns:
            :class:`FRTBResult` with all charges and aggregated totals.
        """
        sensitivities = sensitivities or []
        drc_positions = drc_positions or []
        rrao_positions = rrao_positions or []

        result = FRTBResult()

        # -----------------------------------------------------------------
        # SBM: Partition and calculate per risk class
        # -----------------------------------------------------------------
        partitioned = _partition_sensitivities(sensitivities)

        # --- GIRR ---------------------------------------------------------
        girr_sens = partitioned.get(RiskClass.GIRR, [])
        if girr_sens and self._girr is not None:
            try:
                girr_result = self._girr.calculate(girr_sens)
                result.girr_charge = girr_result.total_charge
                result.girr_delta = girr_result.delta_charge
                result.girr_vega = girr_result.vega_charge
                result.girr_curvature = girr_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("GIRR calculation failed: %s", e)

        # --- CSR Non-Sec --------------------------------------------------
        csr_nonsec_sens = partitioned.get(RiskClass.CSR_NON_SEC, [])
        if csr_nonsec_sens and self._csr_nonsec is not None:
            try:
                csr_nonsec_result = self._csr_nonsec.calculate(csr_nonsec_sens)
                result.csr_nonsec_charge = csr_nonsec_result.total_charge
                result.csr_nonsec_delta = csr_nonsec_result.delta_charge
                result.csr_nonsec_vega = csr_nonsec_result.vega_charge
                result.csr_nonsec_curvature = csr_nonsec_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("CSR Non-Sec calculation failed: %s", e)

        # --- CSR Sec Non-CTP ----------------------------------------------
        csr_sec_nonctp_sens = partitioned.get(RiskClass.CSR_SEC_NON_CTP, [])
        if csr_sec_nonctp_sens and self._csr_sec is not None:
            try:
                csr_sec_nonctp_result = self._csr_sec.calculate(
                    csr_sec_nonctp_sens, is_ctp=False
                )
                result.csr_sec_nonctp_charge = csr_sec_nonctp_result.total_charge
                result.csr_sec_nonctp_delta = csr_sec_nonctp_result.delta_charge
                result.csr_sec_nonctp_vega = csr_sec_nonctp_result.vega_charge
                result.csr_sec_nonctp_curvature = csr_sec_nonctp_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("CSR Sec Non-CTP calculation failed: %s", e)

        # --- CSR Sec CTP --------------------------------------------------
        csr_sec_ctp_sens = partitioned.get(RiskClass.CSR_SEC_CTP, [])
        if csr_sec_ctp_sens and self._csr_sec is not None:
            try:
                csr_sec_ctp_result = self._csr_sec.calculate(
                    csr_sec_ctp_sens, is_ctp=True
                )
                result.csr_sec_ctp_charge = csr_sec_ctp_result.total_charge
                result.csr_sec_ctp_delta = csr_sec_ctp_result.delta_charge
                result.csr_sec_ctp_vega = csr_sec_ctp_result.vega_charge
                result.csr_sec_ctp_curvature = csr_sec_ctp_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("CSR Sec CTP calculation failed: %s", e)

        # --- Equity -------------------------------------------------------
        equity_sens = partitioned.get(RiskClass.EQUITY, [])
        if equity_sens and self._equity is not None:
            try:
                equity_result = self._equity.calculate(equity_sens)
                result.equity_charge = equity_result.total_charge
                result.equity_delta = equity_result.delta_charge
                result.equity_vega = equity_result.vega_charge
                result.equity_curvature = equity_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("Equity calculation failed: %s", e)

        # --- Commodity ----------------------------------------------------
        commodity_sens = partitioned.get(RiskClass.COMMODITY, [])
        if commodity_sens and self._commodity is not None:
            try:
                commodity_result = self._commodity.calculate(commodity_sens)
                result.commodity_charge = commodity_result.total_charge
                result.commodity_delta = commodity_result.delta_charge
                result.commodity_vega = commodity_result.vega_charge
                result.commodity_curvature = commodity_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("Commodity calculation failed: %s", e)

        # --- FX -----------------------------------------------------------
        fx_sens = partitioned.get(RiskClass.FX, [])
        if fx_sens and self._fx is not None:
            try:
                fx_result = self._fx.calculate(fx_sens)
                result.fx_charge = fx_result.total_charge
                result.fx_delta = fx_result.delta_charge
                result.fx_vega = fx_result.vega_charge
                result.fx_curvature = fx_result.curvature_charge
            except (CalculationError, ValidationError) as e:
                logger.error("FX calculation failed: %s", e)

        # -----------------------------------------------------------------
        # SBM Subtotals
        # -----------------------------------------------------------------
        result.sbm_delta = (
            result.girr_delta
            + result.csr_nonsec_delta
            + result.csr_sec_nonctp_delta
            + result.csr_sec_ctp_delta
            + result.equity_delta
            + result.commodity_delta
            + result.fx_delta
        )
        result.sbm_vega = (
            result.girr_vega
            + result.csr_nonsec_vega
            + result.csr_sec_nonctp_vega
            + result.csr_sec_ctp_vega
            + result.equity_vega
            + result.commodity_vega
            + result.fx_vega
        )
        result.sbm_curvature = (
            result.girr_curvature
            + result.csr_nonsec_curvature
            + result.csr_sec_nonctp_curvature
            + result.csr_sec_ctp_curvature
            + result.equity_curvature
            + result.commodity_curvature
            + result.fx_curvature
        )
        result.sbm_total = result.sbm_delta + result.sbm_vega + result.sbm_curvature

        # -----------------------------------------------------------------
        # DRC
        # -----------------------------------------------------------------
        if drc_positions and self._drc is not None:
            try:
                drc_result = self._drc.calculate(drc_positions)
                result.drc_nonsec = drc_result.total_charge
                result.drc_total = drc_result.total_charge
            except (CalculationError, ValidationError, AttributeError) as e:
                logger.error("DRC calculation failed: %s", e)

        # -----------------------------------------------------------------
        # RRAO
        # -----------------------------------------------------------------
        if rrao_positions and self._rrao is not None:
            try:
                rrao_result = self._rrao.calculate(rrao_positions)
                result.rrao_total = rrao_result.total_charge
            except (CalculationError, ValidationError, AttributeError) as e:
                logger.error("RRAO calculation failed: %s", e)

        return result

    # --------------------------------------------------------------------- #
    #  Summary Reporting                                                     #
    # --------------------------------------------------------------------- #

    def summary(self, result: FRTBResult) -> str:
        """Generate a formatted summary report of FRTB results.

        Produces output suitable for FR Y-9C / Pillar 3 MR1-MR4 disclosure
        templates.

        Args:
            result: An :class:`FRTBResult` from a prior :meth:`calculate` call.

        Returns:
            Multi-line formatted string with the full FRTB breakdown.
        """
        lines: list[str] = []
        sep = "-" * 78
        eq_sep = "=" * 78

        lines.append(eq_sep)
        lines.append("  FRTB CAPITAL CHARGE SUMMARY")
        lines.append("  Basel III Endgame -- Standardized Approach (SA)")
        lines.append(eq_sep)
        lines.append("")

        # SBM by risk class ------------------------------------------------
        lines.append("  SENSITIVITIES-BASED METHOD (SBM)")
        lines.append(sep)
        lines.append(
            f"  {'Risk Class':30s} {'Delta':>12s} {'Vega':>12s} "
            f"{'Curvature':>12s} {'Total':>12s}"
        )
        lines.append(f"  {sep}")

        sbm_rows = [
            ("GIRR", result.girr_delta, result.girr_vega, result.girr_curvature, result.girr_charge),
            ("CSR Non-Sec", result.csr_nonsec_delta, result.csr_nonsec_vega, result.csr_nonsec_curvature, result.csr_nonsec_charge),
            ("CSR Sec (Non-CTP)", result.csr_sec_nonctp_delta, result.csr_sec_nonctp_vega, result.csr_sec_nonctp_curvature, result.csr_sec_nonctp_charge),
            ("CSR Sec (CTP)", result.csr_sec_ctp_delta, result.csr_sec_ctp_vega, result.csr_sec_ctp_curvature, result.csr_sec_ctp_charge),
            ("Equity", result.equity_delta, result.equity_vega, result.equity_curvature, result.equity_charge),
            ("Commodity", result.commodity_delta, result.commodity_vega, result.commodity_curvature, result.commodity_charge),
            ("FX", result.fx_delta, result.fx_vega, result.fx_curvature, result.fx_charge),
        ]

        for name, delta, vega, curv, total in sbm_rows:
            lines.append(
                f"  {name:30s} ${delta:>10,.0f}  ${vega:>10,.0f}  "
                f"${curv:>10,.0f}  ${total:>10,.0f}"
            )

        lines.append(f"  {sep}")
        lines.append(
            f"  {'SBM TOTAL':30s} ${result.sbm_delta:>10,.0f}  "
            f"${result.sbm_vega:>10,.0f}  ${result.sbm_curvature:>10,.0f}  "
            f"${result.sbm_total:>10,.0f}"
        )
        lines.append("")

        # DRC --------------------------------------------------------------
        lines.append("  DEFAULT RISK CHARGE (DRC)")
        lines.append(sep)
        lines.append(f"  {'DRC Non-Sec':30s} ${result.drc_nonsec:>10,.0f}")
        lines.append(f"  {'DRC TOTAL':30s} ${result.drc_total:>10,.0f}")
        lines.append("")

        # RRAO -------------------------------------------------------------
        lines.append("  RESIDUAL RISK ADD-ON (RRAO)")
        lines.append(sep)
        lines.append(f"  {'RRAO TOTAL':30s} ${result.rrao_total:>10,.0f}")
        lines.append("")

        # Grand total ------------------------------------------------------
        lines.append(eq_sep)
        lines.append(f"  {'TOTAL FRTB CAPITAL CHARGE':30s} ${result.total_capital_charge:>10,.0f}")
        lines.append(f"  {'TOTAL MARKET RISK RWA':30s} ${result.total_rwa:>10,.0f}")
        lines.append(eq_sep)

        return "\n".join(lines)

    # --------------------------------------------------------------------- #
    #  Pillar 3 MR1-MR4 Reporting                                            #
    # --------------------------------------------------------------------- #

    def pillar3_mr1(self, result: FRTBResult) -> dict[str, float]:
        """Generate Pillar 3 MR1 template data: Market risk under SA.

        MR1 discloses the components of market risk capital charge under
        the Standardized Approach.

        Args:
            result: An :class:`FRTBResult` from a prior :meth:`calculate` call.

        Returns:
            Dictionary with MR1 line items and their values.
        """
        return {
            "1_sa_sbm_girr": result.girr_charge,
            "2_sa_sbm_csr_nonsec": result.csr_nonsec_charge,
            "3_sa_sbm_csr_sec_nonctp": result.csr_sec_nonctp_charge,
            "4_sa_sbm_csr_sec_ctp": result.csr_sec_ctp_charge,
            "5_sa_sbm_equity": result.equity_charge,
            "6_sa_sbm_commodity": result.commodity_charge,
            "7_sa_sbm_fx": result.fx_charge,
            "8_sa_sbm_total": result.sbm_total,
            "9_sa_drc_nonsec": result.drc_nonsec,
            "10_sa_drc_total": result.drc_total,
            "11_sa_rrao": result.rrao_total,
            "12_sa_total_capital": result.total_capital_charge,
            "13_sa_total_rwa": result.total_rwa,
        }

    def pillar3_mr2(self, result: FRTBResult) -> dict[str, dict[str, float]]:
        """Generate Pillar 3 MR2 template data: SBM by risk measure.

        MR2 breaks down each risk class into delta, vega, and curvature.

        Args:
            result: An :class:`FRTBResult` from a prior :meth:`calculate` call.

        Returns:
            Nested dictionary with risk class -> measure -> value.
        """
        return {
            "GIRR": {
                "delta": result.girr_delta,
                "vega": result.girr_vega,
                "curvature": result.girr_curvature,
                "total": result.girr_charge,
            },
            "CSR_Non_Sec": {
                "delta": result.csr_nonsec_delta,
                "vega": result.csr_nonsec_vega,
                "curvature": result.csr_nonsec_curvature,
                "total": result.csr_nonsec_charge,
            },
            "CSR_Sec_Non_CTP": {
                "delta": result.csr_sec_nonctp_delta,
                "vega": result.csr_sec_nonctp_vega,
                "curvature": result.csr_sec_nonctp_curvature,
                "total": result.csr_sec_nonctp_charge,
            },
            "CSR_Sec_CTP": {
                "delta": result.csr_sec_ctp_delta,
                "vega": result.csr_sec_ctp_vega,
                "curvature": result.csr_sec_ctp_curvature,
                "total": result.csr_sec_ctp_charge,
            },
            "Equity": {
                "delta": result.equity_delta,
                "vega": result.equity_vega,
                "curvature": result.equity_curvature,
                "total": result.equity_charge,
            },
            "Commodity": {
                "delta": result.commodity_delta,
                "vega": result.commodity_vega,
                "curvature": result.commodity_curvature,
                "total": result.commodity_charge,
            },
            "FX": {
                "delta": result.fx_delta,
                "vega": result.fx_vega,
                "curvature": result.fx_curvature,
                "total": result.fx_charge,
            },
        }

    def pillar3_mr3(self, result: FRTBResult) -> dict[str, float]:
        """Generate Pillar 3 MR3 template data: Capital charge flow.

        MR3 shows the composition of capital requirements at a high level.

        Args:
            result: An :class:`FRTBResult` from a prior :meth:`calculate` call.

        Returns:
            Dictionary with high-level capital components.
        """
        return {
            "sbm_delta": result.sbm_delta,
            "sbm_vega": result.sbm_vega,
            "sbm_curvature": result.sbm_curvature,
            "sbm_total": result.sbm_total,
            "drc_total": result.drc_total,
            "rrao_total": result.rrao_total,
            "total_capital": result.total_capital_charge,
            "total_rwa": result.total_rwa,
        }

    def pillar3_mr4(self, result: FRTBResult) -> dict[str, float]:
        """Generate Pillar 3 MR4 template data: SA comparison by risk class.

        MR4 maps to FR Y-9C Schedule HC-R Part II market risk reporting.

        Args:
            result: An :class:`FRTBResult` from a prior :meth:`calculate` call.

        Returns:
            Dictionary mapping FR Y-9C line items to capital values.
        """
        return {
            "line_1_girr": result.girr_charge,
            "line_2_credit_spread_risk": (
                result.csr_nonsec_charge
                + result.csr_sec_nonctp_charge
                + result.csr_sec_ctp_charge
            ),
            "line_2a_csr_nonsec": result.csr_nonsec_charge,
            "line_2b_csr_sec_nonctp": result.csr_sec_nonctp_charge,
            "line_2c_csr_sec_ctp": result.csr_sec_ctp_charge,
            "line_3_equity_risk": result.equity_charge,
            "line_4_commodity_risk": result.commodity_charge,
            "line_5_fx_risk": result.fx_charge,
            "line_6_sbm_subtotal": result.sbm_total,
            "line_7_drc": result.drc_total,
            "line_8_rrao": result.rrao_total,
            "line_9_total_sa_capital": result.total_capital_charge,
            "line_10_total_sa_rwa": result.total_rwa,
        }
