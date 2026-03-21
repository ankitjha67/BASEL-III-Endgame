"""CSR Non-Securitization Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the Credit Spread Risk -- Non-Securitization (CSR Non-Sec) capital
charge calculation per MAR21.12-21.13 of the Basel III Endgame framework.

CSR Non-Sec covers:
- Delta risk: Linear sensitivities to credit spreads across 18 sector/quality buckets
- Vega risk: Sensitivities to implied volatilities of credit spread options
- Curvature risk: Non-linear risk from options on credit spreads

Reference: BCBS d457 MAR21.12-21.13, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    CreditQuality,
    CSRBucket,
    CSRSector,
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
from src.market_risk.frtb.sbm.csr_nonsec_params import (
    DELTA_RISK_WEIGHTS,
    INTER_BUCKET_CORRELATIONS,
    NAME_CORRELATIONS,
    RHO_BASIS_DIFF_CURVE,
    RHO_BASIS_SAME_CURVE,
    TENORS,
    VEGA_ALPHA,
    VEGA_OPTION_MATURITIES,
    VEGA_RISK_WEIGHT,
    VEGA_UNDERLYING_TENORS,
    apply_correlation_scenario,
    build_csr_nonsec_correlation_matrix,
    compute_tenor_correlation,
    get_delta_risk_weight,
    get_inter_bucket_correlation,
)
from src.utils.aggregation import intra_bucket_aggregation, inter_bucket_aggregation


class CSRNonSecCalculator:
    """Main CSR Non-Securitization risk charge calculator.

    Orchestrates delta, vega, and curvature risk charge calculations across
    all three correlation scenarios (Low, Medium, High) per MAR21.12-21.13.

    CSR Non-Sec has 18 buckets organised by sector and credit quality.
    Within each bucket, correlations decompose into three multiplicative
    factors: name, tenor, and basis (curve).

    Usage::

        calculator = CSRNonSecCalculator()
        result = calculator.calculate(sensitivities)
        print(result.total_charge)
    """

    # --------------------------------------------------------------------- #
    #  Initialization                                                        #
    # --------------------------------------------------------------------- #

    def __init__(self) -> None:
        """Initialize with regulatory parameters.

        All parameters are sourced from :mod:`csr_nonsec_params` at module
        level, so no mutable configuration state is kept here.
        """
        self._inter_bucket_correlations = INTER_BUCKET_CORRELATIONS

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(self, sensitivities: list[Sensitivity]) -> CSRNonSecResult:
        """Calculate the complete CSR Non-Sec capital charge.

        Runs delta, vega, and curvature calculations across all three
        correlation scenarios (Low, Medium, High) per MAR21.6.

        Args:
            sensitivities: List of CSR Non-Sec sensitivities (delta, vega,
                curvature).

        Returns:
            :class:`CSRNonSecResult` with charges for every scenario.

        Raises:
            ValidationError: If no sensitivities are provided or any
                sensitivity does not belong to the CSR_NON_SEC risk class.
        """
        if not sensitivities:
            return CSRNonSecResult(
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

        return CSRNonSecResult(
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
        """Calculate CSR Non-Sec delta risk charge for one correlation scenario.

        Steps per MAR21.4:

        1. Group sensitivities by bucket (1-18).
        2. Within each bucket, net sensitivities to the same issuer + tenor +
           curve before applying risk weights.
        3. Apply risk weights: ``WS_k = RW_b * s_k``.
        4. Build three-factor correlation matrix per bucket
           (name x tenor x basis).
        5. Intra-bucket aggregation:
           ``K_b = sqrt(WS^T * rho * WS)``.
        6. Inter-bucket aggregation with the 18x18 gamma matrix.

        Args:
            sensitivities: CSR Non-Sec delta sensitivities only.
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

        for bucket_str, bucket_sens in grouped.items():
            bucket_num = int(bucket_str)

            # Net sensitivities by (issuer, tenor, curve) ----------------------
            netted = self._net_sensitivities(bucket_sens)

            # Apply risk weights -----------------------------------------------
            ws_list = [
                self._apply_delta_risk_weight(s, bucket_num) for s in netted
            ]

            # Extract metadata for correlation matrix --------------------------
            issuers = [s.label or "UNKNOWN" for s in netted]
            tenors = [self._get_tenor_value(s) for s in netted]
            curves = [self._get_curve_label(s) for s in netted]

            # Build intra-bucket correlation matrix ----------------------------
            corr = build_csr_nonsec_correlation_matrix(
                bucket=bucket_num,
                issuers=issuers,
                tenors=tenors,
                curves=curves,
                scenario=scenario,
            )

            ws_array = np.array(
                [w.weighted_value for w in ws_list], dtype=np.float64
            )

            # Intra-bucket aggregation -----------------------------------------
            k_b, s_b = intra_bucket_aggregation(ws_array, corr)

            bucket_charges[bucket_str] = k_b
            bucket_net_sens[bucket_str] = s_b
            bucket_results.append(
                BucketResult(
                    bucket=bucket_str,
                    capital_charge=k_b,
                    net_weighted_sensitivity=s_b,
                    weighted_sensitivities=ws_list,
                )
            )

        # Inter-bucket aggregation ---------------------------------------------
        total_charge = self._inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, scenario
        )

        return RiskChargeResult(
            risk_class=RiskClass.CSR_NON_SEC,
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
        """Calculate CSR Non-Sec vega risk charge for one correlation scenario.

        Vega uses (per MAR21.44-47):

        - Risk weight: 100% for CSR Non-Sec since
          ``min(sqrt(120/10), 1.0) = 1.0``.
        - 2-D correlation: option-maturity x underlying-tenor.
        - Same three-scenario framework as delta.

        Args:
            sensitivities: CSR Non-Sec vega sensitivities only.
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

        for bucket_str, bucket_sens in grouped.items():
            # Apply vega risk weight (100%) ------------------------------------
            ws_list = [self._apply_vega_risk_weight(s) for s in bucket_sens]

            # Build vega correlation matrix ------------------------------------
            corr = self._build_vega_correlation_matrix(bucket_sens, scenario)

            ws_array = np.array(
                [w.weighted_value for w in ws_list], dtype=np.float64
            )

            k_b, s_b = intra_bucket_aggregation(ws_array, corr)

            bucket_charges[bucket_str] = k_b
            bucket_net_sens[bucket_str] = s_b
            bucket_results.append(
                BucketResult(
                    bucket=bucket_str,
                    capital_charge=k_b,
                    net_weighted_sensitivity=s_b,
                    weighted_sensitivities=ws_list,
                )
            )

        total_charge = self._inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, scenario
        )

        return RiskChargeResult(
            risk_class=RiskClass.CSR_NON_SEC,
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
        """Calculate CSR Non-Sec curvature risk charge for one correlation scenario.

        Curvature per MAR21.5:

        - ``CVR_k = max(CVR_k_up, CVR_k_down)`` for each risk factor (the
          *sensitivity value* already encodes the net CVR per risk factor).
        - Intra-bucket:
          ``K_b = max(0, sum(CVR) + sum_{k!=l} rho_kl^2 * psi(CVR_k, CVR_l))``
        - Uses **squared** correlations from delta.

        Args:
            sensitivities: CSR Non-Sec curvature sensitivities only.
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

        for bucket_str, bucket_sens in grouped.items():
            bucket_num = int(bucket_str)

            # CVR values are the sensitivity values themselves -----------------
            cvr_values = np.array(
                [s.value for s in bucket_sens], dtype=np.float64
            )

            # Build the delta correlation matrix, then square it ---------------
            issuers = [s.label or "UNKNOWN" for s in bucket_sens]
            tenors = [self._get_tenor_value(s) for s in bucket_sens]
            curves = [self._get_curve_label(s) for s in bucket_sens]

            delta_corr = build_csr_nonsec_correlation_matrix(
                bucket=bucket_num,
                issuers=issuers,
                tenors=tenors,
                curves=curves,
                scenario=scenario,
            )

            # Squared correlations for curvature per MAR21.5 -------------------
            rho_sq = delta_corr ** 2

            # Intra-bucket curvature aggregation per MAR21.5 -------------------
            n = len(cvr_values)
            sum_cvr = float(np.sum(cvr_values))

            cross_term = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    cross_term += (
                        rho_sq[i, j]
                        * self._psi(cvr_values[i], cvr_values[j])
                    )
            cross_term *= 2.0  # symmetric: (i,j) and (j,i)

            k_b = math.sqrt(max(0.0, sum_cvr + cross_term))

            # For curvature inter-bucket, S_b = sum(CVR_k) --------------------
            bucket_charges[bucket_str] = k_b
            bucket_net_sens[bucket_str] = sum_cvr

            # Build WeightedSensitivity wrappers for reporting -----------------
            ws_curvature = [
                WeightedSensitivity(
                    sensitivity=s,
                    risk_weight=1.0,
                    weighted_value=s.value,
                )
                for s in bucket_sens
            ]

            bucket_results.append(
                BucketResult(
                    bucket=bucket_str,
                    capital_charge=k_b,
                    net_weighted_sensitivity=sum_cvr,
                    weighted_sensitivities=ws_curvature,
                )
            )

        # Inter-bucket curvature aggregation -----------------------------------
        total_charge = self._curvature_inter_bucket(
            bucket_charges, bucket_net_sens, scenario
        )

        return RiskChargeResult(
            risk_class=RiskClass.CSR_NON_SEC,
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
        """Group sensitivities by bucket number.

        For CSR Non-Sec the bucket field holds the bucket number as a string
        (e.g. ``"3"`` for Financials IG).

        Args:
            sensitivities: Flat list of sensitivities.

        Returns:
            Dictionary mapping bucket string to its sensitivities.
        """
        grouped: dict[str, list[Sensitivity]] = defaultdict(list)
        for s in sensitivities:
            grouped[s.bucket].append(s)
        return dict(grouped)

    # --------------------------------------------------------------------- #
    #  Helper: netting                                                       #
    # --------------------------------------------------------------------- #

    def _net_sensitivities(
        self, sensitivities: list[Sensitivity]
    ) -> list[Sensitivity]:
        """Net sensitivities to the same (issuer, tenor, curve) triple.

        Per MAR21.4, sensitivities to the same risk factor are summed before
        risk-weighting.  For CSR Non-Sec a risk factor is identified by
        (issuer, tenor, curve).

        Args:
            sensitivities: Sensitivities within a single bucket.

        Returns:
            List of netted sensitivities with one entry per unique
            (issuer, tenor, curve) triple.
        """
        key_to_sens: dict[tuple[str, float, str], Sensitivity] = {}
        key_to_value: dict[tuple[str, float, str], float] = defaultdict(float)

        for s in sensitivities:
            issuer = s.label or "UNKNOWN"
            tenor = self._get_tenor_value(s)
            curve = self._get_curve_label(s)
            key = (issuer, tenor, curve)

            key_to_value[key] += s.value
            if key not in key_to_sens:
                key_to_sens[key] = s

        netted: list[Sensitivity] = []
        for key, total_value in key_to_value.items():
            template = key_to_sens[key]
            netted.append(
                Sensitivity(
                    risk_class=template.risk_class,
                    risk_measure=template.risk_measure,
                    bucket=template.bucket,
                    risk_factor_type=template.risk_factor_type,
                    tenor=template.tenor,
                    label=template.label,
                    value=total_value,
                    option_maturity=template.option_maturity,
                )
            )

        return netted

    # --------------------------------------------------------------------- #
    #  Helper: delta risk weights                                            #
    # --------------------------------------------------------------------- #

    def _apply_delta_risk_weight(
        self, sensitivity: Sensitivity, bucket: int
    ) -> WeightedSensitivity:
        """Apply risk weight to a single delta sensitivity.

        For CSR Non-Sec the risk weight is uniform within a bucket (does not
        vary by tenor).

        Args:
            sensitivity: A single delta sensitivity.
            bucket: Bucket number (1-18).

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = RW_b * s_k``.

        Raises:
            CalculationError: If the bucket has no defined risk weight.
        """
        try:
            rw = get_delta_risk_weight(bucket)
        except KeyError:
            raise CalculationError(
                f"No delta risk weight defined for CSR Non-Sec bucket {bucket}"
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

        For CSR Non-Sec, the vega risk weight is 100% per MAR21.44 because
        ``min(sqrt(LH/10), 1) = min(sqrt(120/10), 1) = 1.0``.

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
    #  Helper: vega correlation matrix                                       #
    # --------------------------------------------------------------------- #

    def _build_vega_correlation_matrix(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
    ) -> np.ndarray:
        """Build the intra-bucket correlation matrix for vega risk.

        Vega correlations are two-dimensional per MAR21.47:

        .. math::

            \\rho_{kl} = \\rho^{\\mathrm{opt}}_{kl}
                        \\times \\rho^{\\mathrm{tenor}}_{kl}

        where:

        - ``rho_opt(k, l) = exp(-alpha * |Tk_opt - Tl_opt| / min(Tk_opt, Tl_opt))``
        - ``rho_tenor(k, l) = exp(-alpha * |Tk_und - Tl_und| / min(Tk_und, Tl_und))``

        and ``alpha = 0.01`` per the regulatory parameter.

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
                if opt_i == opt_j:
                    rho_opt = 1.0
                else:
                    rho_opt = math.exp(
                        -VEGA_ALPHA
                        * abs(opt_i - opt_j)
                        / min(opt_i, opt_j)
                    )

                # Underlying tenor correlation ---------------------------------
                und_i = self._get_tenor_value(si)
                und_j = self._get_tenor_value(sj)
                if und_i == und_j:
                    rho_tenor = 1.0
                else:
                    rho_tenor = math.exp(
                        -VEGA_ALPHA
                        * abs(und_i - und_j)
                        / min(und_i, und_j)
                    )

                rho = rho_opt * rho_tenor
                rho = apply_correlation_scenario(rho, scenario)
                corr[i, j] = rho
                corr[j, i] = rho

        return corr

    # --------------------------------------------------------------------- #
    #  Helper: inter-bucket aggregation                                      #
    # --------------------------------------------------------------------- #

    def _inter_bucket_aggregation(
        self,
        bucket_charges: dict[str, float],
        bucket_net_sens: dict[str, float],
        scenario: CorrelationScenario,
    ) -> float:
        """Compute inter-bucket aggregation using the 18x18 gamma matrix.

        Unlike GIRR (which uses a single gamma for all pairs), CSR Non-Sec
        has bucket-pair-specific inter-bucket correlations per MAR21.13.

        Formula per MAR21.4(4)::

            Capital = sqrt(sum_b K_b^2
                          + sum_{b!=c} gamma_bc * S_b_capped * S_c_capped)

        where ``S_b_capped = max(min(S_b, K_b), -K_b)``.

        Args:
            bucket_charges: ``{bucket_str: K_b}`` from intra-bucket.
            bucket_net_sens: ``{bucket_str: raw S_b}`` per bucket.
            scenario: Correlation scenario for gamma adjustment.

        Returns:
            Total aggregated capital charge.
        """
        if not bucket_charges:
            return 0.0

        buckets = list(bucket_charges.keys())

        # Cap S_b to [-K_b, K_b]
        capped_s: dict[str, float] = {}
        for b in buckets:
            k_b = bucket_charges[b]
            raw_s = bucket_net_sens.get(b, 0.0)
            capped_s[b] = max(min(raw_s, k_b), -k_b)

        # Sum of K_b^2
        sum_kb_squared = sum(k ** 2 for k in bucket_charges.values())

        # Cross-bucket terms with pair-specific gammas
        cross_sum = 0.0
        for i, b in enumerate(buckets):
            for j in range(i + 1, len(buckets)):
                c = buckets[j]
                bi = int(b)
                ci = int(c)
                gamma = get_inter_bucket_correlation(bi, ci)
                gamma = apply_correlation_scenario(
                    gamma, scenario, is_inter_bucket=True
                )
                cross_sum += gamma * capped_s[b] * capped_s[c]
        cross_sum *= 2.0  # symmetric

        total_variance = sum_kb_squared + cross_sum

        if total_variance >= 0:
            return math.sqrt(total_variance)
        else:
            return sum(abs(k) for k in bucket_charges.values())

    # --------------------------------------------------------------------- #
    #  Helper: curvature psi function                                        #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _psi(cvr_k: float, cvr_l: float) -> float:
        """Curvature psi function per MAR21.5(3).

        Returns the product ``|CVR_k| * |CVR_l|`` scaled by a sign factor:

        - Both positive: ``+|CVR_k| * |CVR_l|``
        - Both negative: ``0``  (no diversification benefit)
        - Mixed signs: ``-|CVR_k| * |CVR_l|`` (reduces the charge)

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

    def _curvature_inter_bucket(
        self,
        bucket_charges: dict[str, float],
        bucket_net_cvr: dict[str, float],
        scenario: CorrelationScenario,
    ) -> float:
        """Curvature inter-bucket aggregation per MAR21.5(5).

        Formula::

            Total = sqrt(max(0, sum_b K_b^2
                              + sum_{b!=c} gamma_bc^2
                                * Psi(sum_CVR_b, sum_CVR_c)))

        where ``Psi`` is the same psi function applied to bucket-level
        net curvature values, and ``gamma_bc^2`` is the squared inter-bucket
        correlation.

        Args:
            bucket_charges: ``{bucket_str: K_b}`` from intra-bucket curvature.
            bucket_net_cvr: ``{bucket_str: sum(CVR_k)}`` per bucket.
            scenario: Correlation scenario for gamma adjustment.

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
                bi = int(b)
                ci = int(c)
                gamma = get_inter_bucket_correlation(bi, ci)
                gamma = apply_correlation_scenario(
                    gamma, scenario, is_inter_bucket=True
                )
                gamma_sq = gamma ** 2
                cvr_b = bucket_net_cvr.get(b, 0.0)
                cvr_c = bucket_net_cvr.get(c, 0.0)
                cross_sum += gamma_sq * self._psi(cvr_b, cvr_c)
        cross_sum *= 2.0  # symmetric

        total_var = sum_kb_sq + cross_sum
        if total_var >= 0:
            return math.sqrt(total_var)
        else:
            return sum(abs(k) for k in bucket_charges.values())

    # --------------------------------------------------------------------- #
    #  Helper: tenor extraction                                              #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _get_tenor_value(sensitivity: Sensitivity) -> float:
        """Extract the tenor value in years from a sensitivity.

        Falls back to 0.25 if no tenor is set.

        Args:
            sensitivity: A single sensitivity.

        Returns:
            Tenor in years.
        """
        if sensitivity.tenor is not None:
            return sensitivity.tenor.value
        return 0.25

    @staticmethod
    def _get_curve_label(sensitivity: Sensitivity) -> str:
        """Extract the curve label from a sensitivity.

        Uses the label field.  For CSR Non-Sec, the label encodes
        ``issuer::curve`` or just the issuer name.  The curve portion
        is extracted after the last ``::`` separator if present.

        Falls back to ``"DEFAULT"`` if no curve information is available.

        Args:
            sensitivity: A single sensitivity.

        Returns:
            Curve label string.
        """
        label = sensitivity.label or ""
        if "::" in label:
            return label.rsplit("::", maxsplit=1)[1]
        return "DEFAULT"

    # --------------------------------------------------------------------- #
    #  Validation                                                            #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _validate_sensitivities(sensitivities: list[Sensitivity]) -> None:
        """Validate that all sensitivities belong to the CSR_NON_SEC risk class.

        Args:
            sensitivities: Input sensitivity list.

        Raises:
            ValidationError: If the list is empty or contains non-CSR-Non-Sec
                sensitivities.
        """
        if not sensitivities:
            raise ValidationError(
                "No sensitivities provided for CSR Non-Sec calculation."
            )

        non_csr = [
            s
            for s in sensitivities
            if s.risk_class != RiskClass.CSR_NON_SEC
        ]
        if non_csr:
            bad_classes = {s.risk_class.value for s in non_csr}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.CSR_NON_SEC. "
                f"Found: {bad_classes}"
            )

        # Validate delta sensitivities have tenors ----------------------------
        for s in sensitivities:
            if s.risk_measure == RiskMeasure.DELTA and s.tenor is None:
                raise ValidationError(
                    f"Delta sensitivity for bucket '{s.bucket}' must "
                    f"specify a tenor."
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
            risk_class=RiskClass.CSR_NON_SEC,
            risk_measure=risk_measure,
            scenario=scenario,
            capital_charge=0.0,
            bucket_results=[],
        )


# --------------------------------------------------------------------------- #
#  CSR Non-Sec Result Model                                                    #
# --------------------------------------------------------------------------- #

from pydantic import BaseModel, Field  # noqa: E402


class CSRNonSecResult(BaseModel):
    """Complete CSR Non-Sec result across all three correlation scenarios.

    Per MAR21.6, the capital requirement is max across scenarios for each
    risk measure.
    """
    delta_low: RiskChargeResult
    delta_medium: RiskChargeResult
    delta_high: RiskChargeResult
    vega_low: RiskChargeResult
    vega_medium: RiskChargeResult
    vega_high: RiskChargeResult
    curvature_low: RiskChargeResult
    curvature_medium: RiskChargeResult
    curvature_high: RiskChargeResult

    @property
    def delta_charge(self) -> float:
        """Maximum delta charge across scenarios."""
        return max(
            self.delta_low.capital_charge,
            self.delta_medium.capital_charge,
            self.delta_high.capital_charge,
        )

    @property
    def vega_charge(self) -> float:
        """Maximum vega charge across scenarios."""
        return max(
            self.vega_low.capital_charge,
            self.vega_medium.capital_charge,
            self.vega_high.capital_charge,
        )

    @property
    def curvature_charge(self) -> float:
        """Maximum curvature charge across scenarios."""
        return max(
            self.curvature_low.capital_charge,
            self.curvature_medium.capital_charge,
            self.curvature_high.capital_charge,
        )

    @property
    def total_charge(self) -> float:
        """Total CSR Non-Sec capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge
