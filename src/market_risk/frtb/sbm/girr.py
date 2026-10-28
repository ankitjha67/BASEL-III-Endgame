"""GIRR Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the General Interest Rate Risk (GIRR) capital charge calculation
per the US ERBA NPR (March 2026), 12 CFR 217 Subpart F §__.206-§__.209
(BCBS d457 MAR21.8-21.12 cross-reference).

GIRR covers:
- Delta risk: Linear sensitivities to risk-free yield curves (ten vertices),
  inflation, and cross-currency basis (§__.208(b)(1), §__.209(b)(1)).
- Vega risk: Sensitivities to implied volatilities of interest rate options
  on the option-maturity x underlying-maturity grid (§__.208(b)(2)).
- Curvature risk: Parallel-shift curvature of each yield curve; no curvature
  for inflation or cross-currency basis (§__.208(b)(3)).

All parameters are sourced from :mod:`girr_params`.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    GIRRRiskFactorType,
    RiskClass,
    RiskMeasure,
)
from src.core.exceptions import CalculationError, ValidationError
from src.core.models import (
    BucketResult,
    GIRRResult,
    RiskChargeResult,
    Sensitivity,
    WeightedSensitivity,
)
from src.market_risk.frtb.sbm.girr_params import (
    GAMMA_GIRR,
    RW_INFLATION,
    RW_XCCY_BASIS,
    VEGA_RISK_WEIGHT,
    apply_correlation_scenario,
    build_girr_correlation_matrix,
    build_girr_curvature_correlation_matrix,
    compute_vega_maturity_correlation,
    get_curvature_risk_weight,
    get_delta_risk_weight,
)
from src.utils.aggregation import intra_bucket_aggregation, inter_bucket_aggregation


class GIRRCalculator:
    """Main GIRR risk charge calculator.

    Orchestrates delta, vega, and curvature risk charge calculations across
    all three correlation scenarios (Low, Medium, High) per MAR21.

    Usage::

        calculator = GIRRCalculator()
        result = calculator.calculate(sensitivities)
        print(result.total_charge)
    """

    # --------------------------------------------------------------------- #
    #  Initialization                                                        #
    # --------------------------------------------------------------------- #

    def __init__(self) -> None:
        """Initialize with regulatory parameters.

        All parameters are sourced from :mod:`girr_params` at module level,
        so no mutable configuration state is kept here.
        """
        self._inter_bucket_gamma: float = GAMMA_GIRR

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(self, sensitivities: list[Sensitivity]) -> GIRRResult:
        """Calculate the complete GIRR capital charge.

        Runs delta, vega, and curvature calculations across all three
        correlation scenarios (Low, Medium, High) per MAR21.6.

        Args:
            sensitivities: List of GIRR sensitivities (delta, vega, curvature).

        Returns:
            :class:`GIRRResult` with charges for every scenario.

        Raises:
            ValidationError: If no sensitivities are provided or any
                sensitivity does not belong to the GIRR risk class.
        """
        if not sensitivities:
            empty = self._empty_result(RiskMeasure.DELTA, CorrelationScenario.MEDIUM)
            return GIRRResult(
                delta_low=self._empty_result(RiskMeasure.DELTA, CorrelationScenario.LOW),
                delta_medium=self._empty_result(RiskMeasure.DELTA, CorrelationScenario.MEDIUM),
                delta_high=self._empty_result(RiskMeasure.DELTA, CorrelationScenario.HIGH),
                vega_low=self._empty_result(RiskMeasure.VEGA, CorrelationScenario.LOW),
                vega_medium=self._empty_result(RiskMeasure.VEGA, CorrelationScenario.MEDIUM),
                vega_high=self._empty_result(RiskMeasure.VEGA, CorrelationScenario.HIGH),
                curvature_low=self._empty_result(RiskMeasure.CURVATURE, CorrelationScenario.LOW),
                curvature_medium=self._empty_result(RiskMeasure.CURVATURE, CorrelationScenario.MEDIUM),
                curvature_high=self._empty_result(RiskMeasure.CURVATURE, CorrelationScenario.HIGH),
            )

        self._validate_sensitivities(sensitivities)

        # Partition by risk measure ----------------------------------------
        delta_sens = [
            s for s in sensitivities if s.risk_measure == RiskMeasure.DELTA
        ]
        vega_sens = [
            s for s in sensitivities if s.risk_measure == RiskMeasure.VEGA
        ]
        curvature_sens = [
            s for s in sensitivities if s.risk_measure == RiskMeasure.CURVATURE
        ]

        # Run all 9 scenario combinations ---------------------------------
        scenarios = [
            CorrelationScenario.LOW,
            CorrelationScenario.MEDIUM,
            CorrelationScenario.HIGH,
        ]

        delta_results: dict[CorrelationScenario, RiskChargeResult] = {}
        vega_results: dict[CorrelationScenario, RiskChargeResult] = {}
        curvature_results: dict[CorrelationScenario, RiskChargeResult] = {}

        for scenario in scenarios:
            delta_results[scenario] = self._calculate_delta_charge(
                delta_sens, scenario
            )
            vega_results[scenario] = self._calculate_vega_charge(
                vega_sens, scenario
            )
            curvature_results[scenario] = self._calculate_curvature_charge(
                curvature_sens, scenario
            )

        return GIRRResult(
            delta_low=delta_results[CorrelationScenario.LOW],
            delta_medium=delta_results[CorrelationScenario.MEDIUM],
            delta_high=delta_results[CorrelationScenario.HIGH],
            vega_low=vega_results[CorrelationScenario.LOW],
            vega_medium=vega_results[CorrelationScenario.MEDIUM],
            vega_high=vega_results[CorrelationScenario.HIGH],
            curvature_low=curvature_results[CorrelationScenario.LOW],
            curvature_medium=curvature_results[CorrelationScenario.MEDIUM],
            curvature_high=curvature_results[CorrelationScenario.HIGH],
        )

    # --------------------------------------------------------------------- #
    #  Delta                                                                 #
    # --------------------------------------------------------------------- #

    def _calculate_delta_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Calculate GIRR delta risk charge for one correlation scenario.

        Steps per ERBA NPR §__.206(b) and §__.209(b)(1):

        1. Group sensitivities by bucket (currency).
        2. Apply risk weights: ``WS_k = RW_k * s_k`` (Table 1, divided by
           sqrt(2) for specified currencies).
        3. Build the intra-bucket correlation matrix (Table 2 tenor
           correlations, 99.9% cross-curve, 40% inflation, 0% basis).
        4. Intra-bucket aggregation:
           ``K_b = sqrt(WS^T * rho * WS)``.
        5. Inter-bucket aggregation with ``gamma = 50%``.

        Args:
            sensitivities: GIRR delta sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            :class:`RiskChargeResult` for delta under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.DELTA, scenario)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            # Weight every sensitivity ----------------------------------------
            ws_list = [self._apply_delta_risk_weights(s) for s in bucket_sens]

            # Separate risk-factor metadata for correlation matrix building ----
            yc_ws: list[WeightedSensitivity] = []
            yc_labels: list[str] = []
            yc_tenors: list[float] = []
            infl_ws: list[WeightedSensitivity] = []
            infl_labels: list[str] = []
            xccy_ws: list[WeightedSensitivity] = []
            xccy_labels: list[str] = []

            for ws in ws_list:
                rf_type = ws.sensitivity.risk_factor_type
                if rf_type == GIRRRiskFactorType.YIELD_CURVE:
                    yc_ws.append(ws)
                    yc_labels.append(ws.sensitivity.label or "DEFAULT")
                    yc_tenors.append(
                        ws.sensitivity.tenor.value
                        if ws.sensitivity.tenor is not None
                        else 0.25
                    )
                elif rf_type == GIRRRiskFactorType.INFLATION:
                    infl_ws.append(ws)
                    infl_labels.append(ws.sensitivity.label or "INFLATION")
                elif rf_type == GIRRRiskFactorType.CROSS_CURRENCY_BASIS:
                    xccy_ws.append(ws)
                    xccy_labels.append(ws.sensitivity.label or "XCCY")

            # Build correlation matrix via girr_params helper -----------------
            corr = build_girr_correlation_matrix(
                currency=bucket,
                num_yield_curve_sensitivities=len(yc_ws),
                curve_labels=yc_labels,
                tenors=yc_tenors,
                scenario=scenario,
                inflation_labels=infl_labels,
                xccy_basis_labels=xccy_labels,
            )

            # Assemble the ordered WS vector (yield curves, then infl, xccy) --
            ordered_ws = yc_ws + infl_ws + xccy_ws
            ws_array = np.array(
                [w.weighted_value for w in ordered_ws], dtype=np.float64
            )

            # Intra-bucket aggregation ----------------------------------------
            k_b, s_b = intra_bucket_aggregation(ws_array, corr)

            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = s_b
            bucket_results.append(
                BucketResult(
                    bucket=bucket,
                    capital_charge=k_b,
                    net_weighted_sensitivity=s_b,
                    weighted_sensitivities=ordered_ws,
                )
            )

        # Inter-bucket aggregation --------------------------------------------
        gamma = apply_correlation_scenario(
            self._inter_bucket_gamma, scenario, is_inter_bucket=True
        )
        total_charge = inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, gamma
        )

        return RiskChargeResult(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.DELTA,
            scenario=scenario,
            capital_charge=total_charge,
            bucket_results=bucket_results,
        )

    # --------------------------------------------------------------------- #
    #  Vega                                                                  #
    # --------------------------------------------------------------------- #

    def _calculate_vega_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Calculate GIRR vega risk charge for one correlation scenario.

        Vega per ERBA NPR §__.208(b)(2) and §__.209 Table 11:

        - Risk weight: 100% for GIRR (Table 11).
        - 2-D correlation: ``min(rho_option_maturity * rho_underlying_maturity, 1)``
          with ``alpha = 1%``.
        - Inter-bucket ``gamma = 50%`` (same as delta).

        Args:
            sensitivities: GIRR vega sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            :class:`RiskChargeResult` for vega under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.VEGA, scenario)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            # Apply vega risk weight (100%) -----------------------------------
            ws_list = [self._apply_vega_risk_weight(s) for s in bucket_sens]

            # Build vega correlation matrix -----------------------------------
            corr = self._build_vega_correlation_matrix(bucket_sens, scenario)

            ws_array = np.array(
                [w.weighted_value for w in ws_list], dtype=np.float64
            )

            k_b, s_b = intra_bucket_aggregation(ws_array, corr)

            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = s_b
            bucket_results.append(
                BucketResult(
                    bucket=bucket,
                    capital_charge=k_b,
                    net_weighted_sensitivity=s_b,
                    weighted_sensitivities=ws_list,
                )
            )

        gamma = apply_correlation_scenario(
            self._inter_bucket_gamma, scenario, is_inter_bucket=True
        )
        total_charge = inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, gamma
        )

        return RiskChargeResult(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.VEGA,
            scenario=scenario,
            capital_charge=total_charge,
            bucket_results=bucket_results,
        )

    # --------------------------------------------------------------------- #
    #  Curvature                                                             #
    # --------------------------------------------------------------------- #

    def _calculate_curvature_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> RiskChargeResult:
        """Calculate GIRR curvature risk charge for one correlation scenario.

        Curvature per ERBA NPR §__.206(b)(3), §__.208(b)(3) and the
        §__.209 curvature paragraph:

        - The curvature shock is a parallel shift of every vertex of a
          yield curve by the bucket's highest delta risk weight
          (:func:`girr_params.get_curvature_risk_weight`), so each curve is
          ONE curvature risk factor.  The *sensitivity value* is the net
          ``CVR_k`` for that curve computed with that shock.
        - Inflation and cross-currency basis carry no curvature charge and
          are rejected by validation.
        - Intra-bucket correlation: 100% within a curve, 99.8% between
          different curves (stated directly by the NPR; not re-squared).
        - ``K_b = sqrt(max(0, sum_k max(CVR_k,0)^2
          + sum_{k!=l} rho_kl * CVR_k * CVR_l * psi))``.
        - Inter-bucket correlation: ``gamma^2`` with ``gamma = 50%``.

        Args:
            sensitivities: GIRR curvature sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            :class:`RiskChargeResult` for curvature under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.CURVATURE, scenario)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            # CVR values are the sensitivity values themselves -----------------
            cvr_values = np.array(
                [s.value for s in bucket_sens], dtype=np.float64
            )

            # Curve-level curvature correlation (100% same curve, 99.8%
            # different curves) per ERBA NPR §__.209 ---------------------------
            curve_labels = [s.label or "DEFAULT" for s in bucket_sens]
            rho_curv = build_girr_curvature_correlation_matrix(
                curve_labels, scenario
            )

            # Intra-bucket curvature aggregation per §__.206(b)(3) ------------
            #   K_b = sqrt(max(0, sum_k max(CVR_k,0)^2
            #                   + sum_{k!=l} rho_kl * CVR_k * CVR_l * psi))
            # NOTE: the diagonal term is the SQUARE of the positive part, not
            # the plain sum of CVR_k (which would mix linear and quadratic
            # terms under the square root).
            n = len(cvr_values)
            sum_cvr = float(np.sum(cvr_values))          # S_b for inter-bucket
            diag_term = float(np.sum(np.maximum(cvr_values, 0.0) ** 2))

            cross_term = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    cross_term += (
                        rho_curv[i, j]
                        * self._psi(cvr_values[i], cvr_values[j])
                    )
            cross_term *= 2.0  # symmetric: (i,j) and (j,i)

            k_b = math.sqrt(max(0.0, diag_term + cross_term))

            # For curvature inter-bucket, S_b = sum(CVR_k) --------------------
            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = sum_cvr

            # Build WeightedSensitivity wrappers for reporting; the recorded
            # risk weight is the parallel shock size used to compute CVR_k.
            curvature_rw = get_curvature_risk_weight(bucket)
            ws_curvature = [
                WeightedSensitivity(
                    sensitivity=s,
                    risk_weight=curvature_rw,
                    weighted_value=s.value,
                )
                for s in bucket_sens
            ]

            bucket_results.append(
                BucketResult(
                    bucket=bucket,
                    capital_charge=k_b,
                    net_weighted_sensitivity=sum_cvr,
                    weighted_sensitivities=ws_curvature,
                )
            )

        # Inter-bucket curvature aggregation -----------------------------------
        # ERBA NPR §__.209 (curvature): gamma_bc for curvature is the delta
        # gamma squared.
        gamma = apply_correlation_scenario(
            self._inter_bucket_gamma, scenario, is_inter_bucket=True
        )
        gamma_sq = gamma ** 2

        total_charge = self._curvature_inter_bucket(
            bucket_charges, bucket_net_sens, gamma_sq
        )

        return RiskChargeResult(
            risk_class=RiskClass.GIRR,
            risk_measure=RiskMeasure.CURVATURE,
            scenario=scenario,
            capital_charge=total_charge,
            bucket_results=bucket_results,
        )

    # --------------------------------------------------------------------- #
    #  Helper: grouping                                                      #
    # --------------------------------------------------------------------- #

    def _group_by_bucket(
        self, sensitivities: list[Sensitivity]
    ) -> dict[str, list[Sensitivity]]:
        """Group sensitivities by bucket (currency for GIRR).

        Args:
            sensitivities: Flat list of sensitivities.

        Returns:
            Dictionary mapping bucket (currency code) to its sensitivities.
        """
        grouped: dict[str, list[Sensitivity]] = defaultdict(list)
        for s in sensitivities:
            grouped[s.bucket].append(s)
        return dict(grouped)

    # --------------------------------------------------------------------- #
    #  Helper: delta risk weights                                            #
    # --------------------------------------------------------------------- #

    def _apply_delta_risk_weights(
        self, sensitivity: Sensitivity
    ) -> WeightedSensitivity:
        """Apply risk weight to a single delta sensitivity.

        Rules per ERBA NPR §__.209(b)(1):

        - **Yield curve:** Table 1 risk weight for the vertex, DIVIDED by
          ``sqrt(2)`` for specified currencies (USD, AUD, CAD, EUR, JPY,
          SEK, GBP); all other currencies use Table 1 unchanged.
        - **Inflation:** ``RW = 1.6%``.
        - **XCCY basis:** ``RW = 1.6%``.

        Args:
            sensitivity: A single delta sensitivity.

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = RW_k * s_k``.

        Raises:
            CalculationError: If the risk factor type is unrecognised or a
                yield-curve sensitivity is missing its tenor.
        """
        rf_type = sensitivity.risk_factor_type

        if rf_type == GIRRRiskFactorType.YIELD_CURVE:
            if sensitivity.tenor is None:
                raise CalculationError(
                    f"Yield-curve sensitivity for bucket '{sensitivity.bucket}' "
                    f"is missing a tenor."
                )
            rw = get_delta_risk_weight(
                sensitivity.tenor.value, sensitivity.bucket
            )
        elif rf_type == GIRRRiskFactorType.INFLATION:
            rw = RW_INFLATION
        elif rf_type == GIRRRiskFactorType.CROSS_CURRENCY_BASIS:
            rw = RW_XCCY_BASIS
        else:
            raise CalculationError(
                f"Unrecognised GIRR risk factor type: {rf_type}"
            )

        weighted_value = rw * sensitivity.value
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=rw,
            weighted_value=weighted_value,
        )

    # --------------------------------------------------------------------- #
    #  Helper: vega risk weights                                             #
    # --------------------------------------------------------------------- #

    def _apply_vega_risk_weight(
        self, sensitivity: Sensitivity
    ) -> WeightedSensitivity:
        """Apply vega risk weight to a single vega sensitivity.

        For GIRR, the vega risk weight is 100% per ERBA NPR §__.209
        Table 11 (BCBS MAR21.92 cross-reference).

        Args:
            sensitivity: A single vega sensitivity.

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = 1.0 * s_k``.
        """
        rw = VEGA_RISK_WEIGHT  # 1.0
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=rw,
            weighted_value=rw * sensitivity.value,
        )

    # --------------------------------------------------------------------- #
    #  Helper: intra-bucket correlation (delta uses girr_params directly)    #
    # --------------------------------------------------------------------- #

    def _build_intra_bucket_correlation_matrix(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> np.ndarray:
        """Build the full intra-bucket correlation matrix for delta.

        Delegates to :func:`girr_params.build_girr_correlation_matrix` after
        extracting the necessary metadata from the sensitivity list.  The
        matrix is ordered yield-curve factors, then inflation, then
        cross-currency basis (ERBA NPR §__.209(b)(1)):

        - **Tenor-to-tenor (same curve):**
          ``max(exp(-0.03 * |Tk - Tl| / min(Tk, Tl)), 0.40)``
        - **Cross-curve:** multiply tenor correlation by 0.999.
        - **Inflation to yield curve:** 0.40; inflation curves 0.999.
        - **XCCY basis to everything:** 0.00.

        Args:
            sensitivities: Sensitivities for a single bucket.
            scenario: Correlation scenario.

        Returns:
            numpy ``ndarray`` of shape ``(total, total)``.
        """
        yc_labels: list[str] = []
        yc_tenors: list[float] = []
        infl_labels: list[str] = []
        xccy_labels: list[str] = []

        for s in sensitivities:
            if s.risk_factor_type == GIRRRiskFactorType.YIELD_CURVE:
                yc_labels.append(s.label or "DEFAULT")
                yc_tenors.append(
                    s.tenor.value if s.tenor is not None else 0.25
                )
            elif s.risk_factor_type == GIRRRiskFactorType.INFLATION:
                infl_labels.append(s.label or "INFLATION")
            elif s.risk_factor_type == GIRRRiskFactorType.CROSS_CURRENCY_BASIS:
                xccy_labels.append(s.label or "XCCY")

        currency = sensitivities[0].bucket if sensitivities else "USD"
        return build_girr_correlation_matrix(
            currency=currency,
            num_yield_curve_sensitivities=len(yc_labels),
            curve_labels=yc_labels,
            tenors=yc_tenors,
            scenario=scenario,
            inflation_labels=infl_labels,
            xccy_basis_labels=xccy_labels,
        )

    # --------------------------------------------------------------------- #
    #  Helper: vega correlation matrix                                       #
    # --------------------------------------------------------------------- #

    def _build_vega_correlation_matrix(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> np.ndarray:
        """Build the intra-bucket correlation matrix for vega risk.

        Vega correlations are two-dimensional per ERBA NPR §__.209 (vega
        paragraph; BCBS MAR21.93 cross-reference):

        .. math::

            \\rho_{kl} = \\min\\bigl(\\rho^{\\mathrm{opt}}_{kl}
                        \\times \\rho^{\\mathrm{und}}_{kl},\\; 1\\bigr)

        where:

        - ``rho_opt(k, l) = exp(-alpha * |Tk_opt - Tl_opt| / min(Tk_opt, Tl_opt))``
        - ``rho_und(k, l) = exp(-alpha * |Tk_und - Tl_und| / min(Tk_und, Tl_und))``

        and ``alpha = 1%``.

        Args:
            sensitivities: Vega sensitivities for one bucket.
            scenario: Correlation scenario.

        Returns:
            numpy ``ndarray`` of shape ``(n, n)``.
        """
        n = len(sensitivities)
        corr = np.eye(n, dtype=np.float64)

        for i in range(n):
            for j in range(i + 1, n):
                si = sensitivities[i]
                sj = sensitivities[j]

                # Option maturity correlation ----------------------------------
                opt_i = si.option_maturity if si.option_maturity else 0.5
                opt_j = sj.option_maturity if sj.option_maturity else 0.5
                rho_opt = compute_vega_maturity_correlation(opt_i, opt_j)

                # Underlying residual maturity correlation ---------------------
                und_i = si.tenor.value if si.tenor is not None else 0.5
                und_j = sj.tenor.value if sj.tenor is not None else 0.5
                rho_und = compute_vega_maturity_correlation(und_i, und_j)

                rho = min(rho_opt * rho_und, 1.0)
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

        Returns the product ``|CVR_k| * |CVR_l|`` scaled by a sign factor:

        - Both positive: ``+|CVR_k| * |CVR_l|``
        - Both negative: ``0``  (both negative means no diversification benefit)
        - Mixed signs: ``-|CVR_k| * |CVR_l|`` (reduces the charge)

        Formally::

            psi(k, l) = { + |CVR_k|*|CVR_l|  if CVR_k > 0 and CVR_l > 0
                        {   0                 if CVR_k < 0 and CVR_l < 0
                        { - |CVR_k|*|CVR_l|  otherwise (mixed signs)

        .. note::

            This function returns the *full cross-product term* including
            the absolute-value magnitudes, not just the sign indicator.
            The caller multiplies by ``rho_kl^2`` to get the contribution.

        Args:
            cvr_k: Curvature risk ``CVR_k`` for factor *k*.
            cvr_l: Curvature risk ``CVR_l`` for factor *l*.

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
    #  Helper: curvature inter-bucket aggregation                            #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _curvature_inter_bucket(
        bucket_charges: dict[str, float],
        bucket_net_cvr: dict[str, float],
        gamma_sq: float,
    ) -> float:
        """Curvature inter-bucket aggregation per ERBA NPR §__.206(b)(3).

        Formula::

            Total = sqrt(max(0, sum_b K_b^2
                              + sum_{b!=c} gamma_bc^2
                                * Psi(sum_CVR_b, sum_CVR_c)))

        where ``Psi`` is the same psi function applied to bucket-level
        net curvature values, and ``gamma_bc^2`` is the squared inter-bucket
        correlation.

        Args:
            bucket_charges: ``{bucket: K_b}`` from intra-bucket curvature.
            bucket_net_cvr: ``{bucket: sum(CVR_k)}`` per bucket.
            gamma_sq: Squared inter-bucket correlation.

        Returns:
            Aggregated curvature capital charge.
        """
        if not bucket_charges:
            return 0.0

        buckets = list(bucket_charges.keys())
        sum_kb_sq = sum(k ** 2 for k in bucket_charges.values())

        cross_sum = 0.0
        for i, b in enumerate(buckets):
            for j in range(i + 1, len(buckets)):
                c = buckets[j]
                cvr_b = bucket_net_cvr.get(b, 0.0)
                cvr_c = bucket_net_cvr.get(c, 0.0)
                cross_sum += gamma_sq * GIRRCalculator._psi(cvr_b, cvr_c)
        cross_sum *= 2.0  # symmetric

        total_var = sum_kb_sq + cross_sum
        if total_var >= 0:
            return math.sqrt(total_var)
        else:
            return sum(abs(k) for k in bucket_charges.values())

    # --------------------------------------------------------------------- #
    #  Validation                                                            #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _validate_sensitivities(sensitivities: list[Sensitivity]) -> None:
        """Validate that all sensitivities belong to the GIRR risk class.

        Args:
            sensitivities: Input sensitivity list.

        Raises:
            ValidationError: If the list is empty or contains non-GIRR
                sensitivities.
        """
        if not sensitivities:
            raise ValidationError("No sensitivities provided for GIRR calculation.")

        non_girr = [
            s
            for s in sensitivities
            if s.risk_class != RiskClass.GIRR
        ]
        if non_girr:
            bad_classes = {s.risk_class.value for s in non_girr}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.GIRR. "
                f"Found: {bad_classes}"
            )

        # Validate yield-curve delta sensitivities have tenors ----------------
        for s in sensitivities:
            if (
                s.risk_measure == RiskMeasure.DELTA
                and s.risk_factor_type == GIRRRiskFactorType.YIELD_CURVE
                and s.tenor is None
            ):
                raise ValidationError(
                    f"Delta yield-curve sensitivity for bucket "
                    f"'{s.bucket}' must specify a tenor."
                )

        # Validate vega sensitivities have option_maturity --------------------
        for s in sensitivities:
            if (
                s.risk_measure == RiskMeasure.VEGA
                and s.option_maturity is None
            ):
                raise ValidationError(
                    f"Vega sensitivity for bucket '{s.bucket}' must "
                    f"specify an option_maturity."
                )

        # ERBA NPR §__.208(b)(3): no curvature for inflation / xccy basis -----
        for s in sensitivities:
            if (
                s.risk_measure == RiskMeasure.CURVATURE
                and s.risk_factor_type != GIRRRiskFactorType.YIELD_CURVE
            ):
                raise ValidationError(
                    f"Curvature sensitivity for bucket '{s.bucket}' has risk "
                    f"factor type {s.risk_factor_type.value}; the ERBA NPR "
                    f"prescribes no curvature charge for inflation or "
                    f"cross-currency basis risk factors."
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

        Used when no sensitivities of a particular type are present.

        Args:
            risk_measure: DELTA, VEGA, or CURVATURE.
            scenario: Correlation scenario.

        Returns:
            :class:`RiskChargeResult` with zero charge and no bucket results.
        """
        return RiskChargeResult(
            risk_class=RiskClass.GIRR,
            risk_measure=risk_measure,
            scenario=scenario,
            capital_charge=0.0,
            bucket_results=[],
        )
