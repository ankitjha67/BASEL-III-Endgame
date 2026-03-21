"""FX Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the FX risk capital charge calculation per MAR21.21-21.22
of the Basel III Endgame framework.

FX covers:
- Delta risk: Linear sensitivities to FX spot rates
- Vega risk: Sensitivities to implied volatilities of FX options
- Curvature risk: Non-linear risk from FX options

FX is the simplest risk class -- no bucket structure. All currency pair
sensitivities are aggregated in a single correlation matrix with
uniform rho = 0.60 between all pairs.

Reference: BCBS d457 MAR21, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    RiskClass,
    RiskMeasure,
)
from src.core.exceptions import CalculationError, ValidationError
from src.core.models import (
    BucketResult,
    RiskChargeResult,
    Sensitivity,
    WeightedSensitivity,
)
from src.market_risk.frtb.sbm.fx_params import (
    FX_DELTA_RW,
    FX_INTRA_CORR,
    FX_VEGA_ALPHA,
    FX_VEGA_RW,
    apply_correlation_scenario,
    build_fx_correlation_matrix,
    get_fx_delta_rw,
)
from src.utils.aggregation import intra_bucket_aggregation


class FXResult:
    """Complete FX result across all three correlation scenarios.

    Per MAR21.6, the capital requirement is max across scenarios.
    """

    def __init__(
        self,
        delta_results: dict[CorrelationScenario, RiskChargeResult],
        vega_results: dict[CorrelationScenario, RiskChargeResult],
        curvature_results: dict[CorrelationScenario, RiskChargeResult],
    ) -> None:
        self.delta_results = delta_results
        self.vega_results = vega_results
        self.curvature_results = curvature_results

    @property
    def delta_charge(self) -> float:
        """Maximum delta charge across scenarios."""
        return max(r.capital_charge for r in self.delta_results.values())

    @property
    def vega_charge(self) -> float:
        """Maximum vega charge across scenarios."""
        return max(r.capital_charge for r in self.vega_results.values())

    @property
    def curvature_charge(self) -> float:
        """Maximum curvature charge across scenarios."""
        return max(r.capital_charge for r in self.curvature_results.values())

    @property
    def total_charge(self) -> float:
        """Total FX capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge


class FXCalculator:
    """Main FX risk charge calculator.

    Orchestrates delta, vega, and curvature risk charge calculations across
    all three correlation scenarios (Low, Medium, High) per MAR21.21-21.22.

    FX is simpler than other risk classes because it has no bucket structure.
    All sensitivities are aggregated in a single pool with uniform
    correlation rho = 0.60 between all currency pairs.

    Usage::

        calculator = FXCalculator()
        result = calculator.calculate(sensitivities)
        print(result.total_charge)
    """

    # Single bucket name for FX (no bucket structure)
    FX_BUCKET = "FX"

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(self, sensitivities: list[Sensitivity]) -> FXResult:
        """Calculate the complete FX capital charge.

        Runs delta, vega, and curvature calculations across all three
        correlation scenarios (Low, Medium, High) per MAR21.6.

        Args:
            sensitivities: List of FX sensitivities (delta, vega, curvature).

        Returns:
            FXResult with charges for every scenario.

        Raises:
            ValidationError: If no sensitivities are provided or any
                sensitivity does not belong to the FX risk class.
        """
        if not sensitivities:
            scenarios = [
                CorrelationScenario.LOW,
                CorrelationScenario.MEDIUM,
                CorrelationScenario.HIGH,
            ]
            return FXResult(
                delta_results={s: self._empty_result(RiskMeasure.DELTA, s) for s in scenarios},
                vega_results={s: self._empty_result(RiskMeasure.VEGA, s) for s in scenarios},
                curvature_results={s: self._empty_result(RiskMeasure.CURVATURE, s) for s in scenarios},
            )

        self._validate_sensitivities(sensitivities)

        # Partition by risk measure
        delta_sens = [s for s in sensitivities if s.risk_measure == RiskMeasure.DELTA]
        vega_sens = [s for s in sensitivities if s.risk_measure == RiskMeasure.VEGA]
        curvature_sens = [s for s in sensitivities if s.risk_measure == RiskMeasure.CURVATURE]

        scenarios = [
            CorrelationScenario.LOW,
            CorrelationScenario.MEDIUM,
            CorrelationScenario.HIGH,
        ]

        delta_results: dict[CorrelationScenario, RiskChargeResult] = {}
        vega_results: dict[CorrelationScenario, RiskChargeResult] = {}
        curvature_results: dict[CorrelationScenario, RiskChargeResult] = {}

        for scenario in scenarios:
            delta_results[scenario] = self._calculate_delta_charge(delta_sens, scenario)
            vega_results[scenario] = self._calculate_vega_charge(vega_sens, scenario)
            curvature_results[scenario] = self._calculate_curvature_charge(curvature_sens, scenario)

        return FXResult(
            delta_results=delta_results,
            vega_results=vega_results,
            curvature_results=curvature_results,
        )

    # --------------------------------------------------------------------- #
    #  Delta                                                                 #
    # --------------------------------------------------------------------- #

    def _calculate_delta_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Calculate FX delta risk charge for one correlation scenario.

        FX has no bucket structure. All sensitivities are aggregated in
        a single pool with uniform correlation rho = 0.60.

        Steps per MAR21.4:
        1. Apply risk weight (15%) to all sensitivities.
        2. Build uniform correlation matrix with rho = 0.60.
        3. Single-pool aggregation: K = sqrt(WS^T * rho * WS).

        Args:
            sensitivities: FX delta sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for delta under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.DELTA, scenario)

        # Weight every sensitivity
        ws_list = [self._apply_delta_risk_weight(s) for s in sensitivities]

        # Build correlation matrix
        n = len(ws_list)
        corr = build_fx_correlation_matrix(n, scenario)

        ws_array = np.array(
            [w.weighted_value for w in ws_list], dtype=np.float64
        )

        # Single-pool aggregation (no inter-bucket step needed)
        k_b, s_b = intra_bucket_aggregation(ws_array, corr)

        bucket_result = BucketResult(
            bucket=self.FX_BUCKET,
            capital_charge=k_b,
            net_weighted_sensitivity=s_b,
            weighted_sensitivities=ws_list,
        )

        return RiskChargeResult(
            risk_class=RiskClass.FX,
            risk_measure=RiskMeasure.DELTA,
            scenario=scenario,
            capital_charge=k_b,
            bucket_results=[bucket_result],
        )

    # --------------------------------------------------------------------- #
    #  Vega                                                                  #
    # --------------------------------------------------------------------- #

    def _calculate_vega_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Calculate FX vega risk charge for one correlation scenario.

        Vega uses:
        - Risk weight: 100% for FX (LH = 40 days, capped).
        - 2-D correlation: rho_base * rho_opt(k,l) * rho_tenor(k,l).
        - Single-pool aggregation (no buckets).

        Args:
            sensitivities: FX vega sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for vega under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.VEGA, scenario)

        # Apply vega risk weight
        ws_list = [self._apply_vega_risk_weight(s) for s in sensitivities]

        # Build vega correlation matrix
        corr = self._build_vega_correlation_matrix(sensitivities, scenario)

        ws_array = np.array(
            [w.weighted_value for w in ws_list], dtype=np.float64
        )

        k_b, s_b = intra_bucket_aggregation(ws_array, corr)

        bucket_result = BucketResult(
            bucket=self.FX_BUCKET,
            capital_charge=k_b,
            net_weighted_sensitivity=s_b,
            weighted_sensitivities=ws_list,
        )

        return RiskChargeResult(
            risk_class=RiskClass.FX,
            risk_measure=RiskMeasure.VEGA,
            scenario=scenario,
            capital_charge=k_b,
            bucket_results=[bucket_result],
        )

    # --------------------------------------------------------------------- #
    #  Curvature                                                             #
    # --------------------------------------------------------------------- #

    def _calculate_curvature_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Calculate FX curvature risk charge for one correlation scenario.

        Curvature per MAR21.5:
        - CVR_k values are the sensitivity values themselves.
        - Single-pool aggregation with squared correlations.
        - K = sqrt(max(0, sum(CVR) + sum_{k!=l} rho_kl^2 * psi(CVR_k, CVR_l)))

        Args:
            sensitivities: FX curvature sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for curvature under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.CURVATURE, scenario)

        cvr_values = np.array(
            [s.value for s in sensitivities], dtype=np.float64
        )

        # Build correlation matrix, then square it
        n = len(sensitivities)
        delta_corr = build_fx_correlation_matrix(n, scenario)
        rho_sq = delta_corr ** 2

        # Curvature aggregation per MAR21.5
        sum_cvr = float(np.sum(cvr_values))

        cross_term = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                cross_term += (
                    rho_sq[i, j]
                    * self._psi(cvr_values[i], cvr_values[j])
                )
        cross_term *= 2.0

        total_charge = math.sqrt(max(0.0, sum_cvr + cross_term))

        # Build WeightedSensitivity wrappers for reporting
        ws_curvature = [
            WeightedSensitivity(
                sensitivity=s,
                risk_weight=1.0,
                weighted_value=s.value,
            )
            for s in sensitivities
        ]

        bucket_result = BucketResult(
            bucket=self.FX_BUCKET,
            capital_charge=total_charge,
            net_weighted_sensitivity=sum_cvr,
            weighted_sensitivities=ws_curvature,
        )

        return RiskChargeResult(
            risk_class=RiskClass.FX,
            risk_measure=RiskMeasure.CURVATURE,
            scenario=scenario,
            capital_charge=total_charge,
            bucket_results=[bucket_result],
        )

    # --------------------------------------------------------------------- #
    #  Helper: delta risk weight                                             #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _apply_delta_risk_weight(sensitivity: Sensitivity) -> WeightedSensitivity:
        """Apply risk weight to a single delta sensitivity.

        All FX pairs receive a 15% risk weight.

        Args:
            sensitivity: A single delta sensitivity.

        Returns:
            WeightedSensitivity with WS_k = 0.15 * s_k.
        """
        rw = get_fx_delta_rw()
        weighted_value = rw * sensitivity.value
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=rw,
            weighted_value=weighted_value,
        )

    # --------------------------------------------------------------------- #
    #  Helper: vega risk weight                                              #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _apply_vega_risk_weight(sensitivity: Sensitivity) -> WeightedSensitivity:
        """Apply vega risk weight to a single vega sensitivity.

        For FX, the vega risk weight is 100% (LH = 40 days, capped).

        Args:
            sensitivity: A single vega sensitivity.

        Returns:
            WeightedSensitivity with WS_k = 1.0 * s_k.
        """
        rw = FX_VEGA_RW
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=rw,
            weighted_value=rw * sensitivity.value,
        )

    # --------------------------------------------------------------------- #
    #  Helper: vega correlation matrix                                       #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _build_vega_correlation_matrix(
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> np.ndarray:
        """Build correlation matrix for FX vega risk.

        Vega correlations combine option-maturity and underlying-tenor
        dimensions with the base FX correlation:

        rho_kl = rho_fx * rho_opt(k,l) * rho_tenor(k,l)

        where:
        - rho_fx = 0.60 (base FX correlation)
        - rho_opt(k,l) = exp(-alpha * |Tk_opt - Tl_opt| / min(Tk_opt, Tl_opt))
        - rho_tenor(k,l) = exp(-alpha * |Tk_und - Tl_und| / min(Tk_und, Tl_und))

        Args:
            sensitivities: Vega sensitivities for FX.
            scenario: Correlation scenario.

        Returns:
            numpy ndarray of shape (n, n).
        """
        n = len(sensitivities)
        corr = np.eye(n, dtype=np.float64)

        for i in range(n):
            for j in range(i + 1, n):
                si = sensitivities[i]
                sj = sensitivities[j]

                # Option maturity correlation
                opt_i = si.option_maturity if si.option_maturity else 0.5
                opt_j = sj.option_maturity if sj.option_maturity else 0.5
                if opt_i == opt_j:
                    rho_opt = 1.0
                else:
                    rho_opt = math.exp(
                        -FX_VEGA_ALPHA
                        * abs(opt_i - opt_j)
                        / min(opt_i, opt_j)
                    )

                # Underlying tenor correlation
                und_i = si.tenor.value if si.tenor is not None else 0.5
                und_j = sj.tenor.value if sj.tenor is not None else 0.5
                if und_i == und_j:
                    rho_tenor = 1.0
                else:
                    rho_tenor = math.exp(
                        -FX_VEGA_ALPHA
                        * abs(und_i - und_j)
                        / min(und_i, und_j)
                    )

                rho = FX_INTRA_CORR * rho_opt * rho_tenor
                rho = apply_correlation_scenario(rho, scenario)
                corr[i, j] = rho
                corr[j, i] = rho

        return corr

    # --------------------------------------------------------------------- #
    #  Helper: curvature psi function                                        #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _psi(cvr_k: float, cvr_l: float) -> float:
        """Curvature psi function per MAR21.5(3).

        Returns the product |CVR_k| * |CVR_l| scaled by a sign factor:
        - Both positive: +|CVR_k| * |CVR_l|
        - Both negative: 0
        - Mixed signs: -|CVR_k| * |CVR_l|

        Args:
            cvr_k: Curvature risk CVR_k for factor k.
            cvr_l: Curvature risk CVR_l for factor l.

        Returns:
            Signed cross-product for the curvature aggregation formula.
        """
        abs_product = abs(cvr_k) * abs(cvr_l)
        if cvr_k > 0 and cvr_l > 0:
            return abs_product
        elif cvr_k < 0 and cvr_l < 0:
            return 0.0
        else:
            return -abs_product

    # --------------------------------------------------------------------- #
    #  Validation                                                            #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _validate_sensitivities(sensitivities: list[Sensitivity]) -> None:
        """Validate that all sensitivities belong to the FX risk class.

        Args:
            sensitivities: Input sensitivity list.

        Raises:
            ValidationError: If the list is empty or contains non-FX
                sensitivities.
        """
        if not sensitivities:
            raise ValidationError("No sensitivities provided for FX calculation.")

        non_fx = [
            s for s in sensitivities if s.risk_class != RiskClass.FX
        ]
        if non_fx:
            bad_classes = {s.risk_class.value for s in non_fx}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.FX. "
                f"Found: {bad_classes}"
            )

    # --------------------------------------------------------------------- #
    #  Helper: empty result                                                  #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _empty_result(
        risk_measure: RiskMeasure,
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Return a zero-charge result for a given measure and scenario.

        Args:
            risk_measure: DELTA, VEGA, or CURVATURE.
            scenario: Correlation scenario.

        Returns:
            RiskChargeResult with zero charge and no bucket results.
        """
        return RiskChargeResult(
            risk_class=RiskClass.FX,
            risk_measure=risk_measure,
            scenario=scenario,
            capital_charge=0.0,
            bucket_results=[],
        )
