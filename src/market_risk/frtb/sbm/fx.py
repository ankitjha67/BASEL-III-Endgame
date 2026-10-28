"""FX Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the FX risk capital charge calculation per the US ERBA NPR
(March 2026), 12 CFR 217 Subpart F §__.206-§__.209 (BCBS d457
MAR21.21-21.22 cross-reference).

FX covers:
- Delta risk: Linear sensitivities to FX spot rates; RW 15%, or 15%/sqrt(2)
  for pairs of specified currencies (§__.209(b)(7)).
- Vega risk: Sensitivities to implied volatilities of FX options; RW 100%
  (§__.209 Table 11).
- Curvature risk: Non-linear risk from FX options; curvature RW = delta RW,
  with an optional division of the curvature risk position by 1.5 for
  options not referencing the reporting currency (§__.209 curvature).

FX has no bucket structure.  All currency-pair sensitivities are
aggregated in a single correlation matrix with uniform rho = 60%.  The
``bucket`` field of each sensitivity carries the currency pair (e.g.
``"EURUSD"`` or ``"EUR/USD"``).
"""

from __future__ import annotations

import math

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    RiskClass,
    RiskMeasure,
)
from src.core.exceptions import ValidationError
from src.core.models import (
    BucketResult,
    RiskChargeResult,
    Sensitivity,
    WeightedSensitivity,
)
from src.market_risk.frtb.sbm.fx_params import (
    APPLY_FX_CURVATURE_NON_REPORTING_CCY_DIVISOR,
    FX_CURVATURE_NON_REPORTING_CCY_DIVISOR,
    FX_INTRA_CORR,
    FX_VEGA_ALPHA,
    FX_VEGA_RW,
    apply_correlation_scenario,
    build_fx_correlation_matrix,
    get_fx_curvature_rw,
    get_fx_delta_rw,
    references_reporting_currency,
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
    all three correlation scenarios (Low, Medium, High) per ERBA NPR
    §__.206(c) and §__.209(b)(7).

    FX is simpler than other risk classes because it has no bucket structure.
    All sensitivities are aggregated in a single pool with uniform
    correlation rho = 60% between all currency pairs.

    Usage::

        calculator = FXCalculator()
        result = calculator.calculate(sensitivities)
        print(result.total_charge)
    """

    # Single bucket name for FX (no bucket structure)
    FX_BUCKET = "FX"

    def __init__(
        self,
        reporting_currency: str = "USD",
        apply_curvature_divisor: bool | None = None,
    ) -> None:
        """Initialise the FX calculator.

        Args:
            reporting_currency: ISO 4217 reporting currency of the banking
                organization (ERBA NPR §__.208(b)(7): FX risk factors are
                measured against the reporting currency).
            apply_curvature_divisor: Whether to divide the curvature risk
                position of options that do not reference the reporting
                currency by 1.5 (ERBA NPR §__.209, curvature paragraph:
                an optional election).  ``None`` uses the module default
                :data:`fx_params.APPLY_FX_CURVATURE_NON_REPORTING_CCY_DIVISOR`
                (off).
        """
        self.reporting_currency = reporting_currency.upper()
        self.apply_curvature_divisor = (
            APPLY_FX_CURVATURE_NON_REPORTING_CCY_DIVISOR
            if apply_curvature_divisor is None
            else apply_curvature_divisor
        )

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
        a single pool with uniform correlation rho = 60%.

        Steps per ERBA NPR §__.206(b) and §__.209(b)(7):
        1. Apply risk weight (15%, or 15%/sqrt(2) for specified-currency
           pairs) to each sensitivity.
        2. Build uniform correlation matrix with rho = 60%.
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

        Vega per ERBA NPR §__.209 (Table 11 and vega paragraph):
        - Risk weight: 100% for FX.
        - Correlation: min(rho_delta * rho_option_maturity, 1) with
          rho_delta = 60% and alpha = 1%.
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

        Curvature per ERBA NPR §__.206(b)(3) and §__.209 (curvature):
        - CVR_k values are the sensitivity values themselves, computed with
          a relative spot shock equal to the delta risk weight
          (:func:`fx_params.get_fx_curvature_rw`).
        - If elected, CVR_k of an option that does not reference the
          reporting currency is divided by 1.5.
        - Single-pool aggregation with squared delta correlations.
        - K = sqrt(max(0, sum max(CVR,0)^2 + sum_{k!=l} rho_kl^2 * psi(CVR_k, CVR_l)))

        Args:
            sensitivities: FX curvature sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for curvature under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.CURVATURE, scenario)

        cvr_values = np.array(
            [self._scaled_cvr(s) for s in sensitivities], dtype=np.float64
        )

        # Build correlation matrix, then square it
        n = len(sensitivities)
        delta_corr = build_fx_correlation_matrix(n, scenario)
        rho_sq = delta_corr ** 2

        # Curvature aggregation per MAR21.5(4)
        # K = sqrt(max(0, sum_k max(CVR_k,0)^2 + sum_{k!=l} rho^2 CVR_k CVR_l psi))
        sum_cvr = float(np.sum(cvr_values))
        diag_term = float(np.sum(np.maximum(cvr_values, 0.0) ** 2))

        cross_term = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                cross_term += (
                    rho_sq[i, j]
                    * self._psi(cvr_values[i], cvr_values[j])
                )
        cross_term *= 2.0

        total_charge = math.sqrt(max(0.0, diag_term + cross_term))

        # Build WeightedSensitivity wrappers for reporting; the recorded risk
        # weight is the curvature shock size, the weighted value the (scaled)
        # CVR actually aggregated.
        ws_curvature = [
            WeightedSensitivity(
                sensitivity=s,
                risk_weight=get_fx_curvature_rw(s.bucket),
                weighted_value=float(cvr),
            )
            for s, cvr in zip(sensitivities, cvr_values, strict=True)
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

    def _scaled_cvr(self, sensitivity: Sensitivity) -> float:
        """Return CVR_k after the optional non-reporting-currency division.

        ERBA NPR §__.209 (curvature): the curvature risk position of an FX
        option whose currency pair does not include the reporting currency
        may be divided by 1.5.  Applied only when
        :attr:`apply_curvature_divisor` is set.

        Args:
            sensitivity: A single FX curvature sensitivity whose ``bucket``
                is the currency pair.

        Returns:
            Scaled curvature risk position.
        """
        if self.apply_curvature_divisor and not references_reporting_currency(
            sensitivity.bucket, self.reporting_currency
        ):
            return sensitivity.value / FX_CURVATURE_NON_REPORTING_CCY_DIVISOR
        return sensitivity.value

    @staticmethod
    def _apply_delta_risk_weight(sensitivity: Sensitivity) -> WeightedSensitivity:
        """Apply risk weight to a single delta sensitivity.

        ERBA NPR §__.209(b)(7): 15%, or 15%/sqrt(2) when both currencies
        of the pair (taken from ``sensitivity.bucket``) are specified
        currencies and the reduction is elected.

        Args:
            sensitivity: A single delta sensitivity.

        Returns:
            WeightedSensitivity with WS_k = RW * s_k.
        """
        rw = get_fx_delta_rw(sensitivity.bucket)
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

        For FX, the vega risk weight is 100% per ERBA NPR §__.209 Table 11.

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

        ERBA NPR §__.209 (vega paragraph): for risk classes other than
        GIRR the vega correlation is

            rho_kl = min(rho_delta * rho_opt(k,l), 1)

        where:
        - rho_delta = 60% (the FX delta correlation; 100% for the same pair)
        - rho_opt(k,l) = exp(-alpha * |Tk_opt - Tl_opt| / min(Tk_opt, Tl_opt)),
          alpha = 1%.

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

                # Delta correlation between the underlying currency pairs
                rho_delta = 1.0 if si.bucket == sj.bucket else FX_INTRA_CORR

                rho = min(rho_delta * rho_opt, 1.0)
                rho = apply_correlation_scenario(rho, scenario)
                corr[i, j] = rho
                corr[j, i] = rho

        return corr

    # --------------------------------------------------------------------- #
    #  Helper: curvature psi function                                        #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _psi(cvr_k: float, cvr_l: float) -> float:
        """Curvature psi function per ERBA NPR §__.206(b)(3) (BCBS MAR21.5(3)).

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
