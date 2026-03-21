"""Commodity Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the Commodity risk capital charge calculation per MAR21.19-21.20
of the Basel III Endgame framework.

Commodity covers:
- Delta risk: Linear sensitivities to commodity spot/forward prices
- Vega risk: Sensitivities to implied volatilities of commodity options
- Curvature risk: Non-linear risk from options on commodities

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
from src.market_risk.frtb.sbm.commodity_params import (
    COMMODITY_BUCKETS,
    COMMODITY_DELTA_RW,
    COMMODITY_INTRA_CORR,
    COMMODITY_VEGA_ALPHA,
    COMMODITY_VEGA_RW,
    apply_correlation_scenario,
    build_commodity_intra_bucket_corr_matrix,
    get_commodity_delta_rw,
    get_commodity_inter_bucket_corr,
)
from src.utils.aggregation import intra_bucket_aggregation


class CommodityResult:
    """Complete Commodity result across all three correlation scenarios.

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
        """Total Commodity capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge


class CommodityCalculator:
    """Main Commodity risk charge calculator.

    Orchestrates delta, vega, and curvature risk charge calculations across
    all three correlation scenarios (Low, Medium, High) per MAR21.19-21.20.

    Usage::

        calculator = CommodityCalculator()
        result = calculator.calculate(sensitivities)
        print(result.total_charge)
    """

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(self, sensitivities: list[Sensitivity]) -> CommodityResult:
        """Calculate the complete Commodity capital charge.

        Runs delta, vega, and curvature calculations across all three
        correlation scenarios (Low, Medium, High) per MAR21.6.

        Args:
            sensitivities: List of Commodity sensitivities (delta, vega, curvature).

        Returns:
            CommodityResult with charges for every scenario.

        Raises:
            ValidationError: If no sensitivities are provided or any
                sensitivity does not belong to the Commodity risk class.
        """
        if not sensitivities:
            scenarios = [
                CorrelationScenario.LOW,
                CorrelationScenario.MEDIUM,
                CorrelationScenario.HIGH,
            ]
            return CommodityResult(
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

        return CommodityResult(
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
        """Calculate Commodity delta risk charge for one correlation scenario.

        Steps per MAR21.4:
        1. Group sensitivities by bucket (1-11).
        2. Apply risk weights: WS_k = RW_k * s_k.
        3. Build intra-bucket correlation matrix (commodity * tenor * basis).
        4. Intra-bucket aggregation: K_b = sqrt(WS^T * rho * WS).
        5. Inter-bucket aggregation with bucket-pair specific gamma.

        Args:
            sensitivities: Commodity delta sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for delta under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.DELTA, scenario)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            bucket_int = int(bucket)

            # Weight every sensitivity
            ws_list = [self._apply_delta_risk_weight(s, bucket_int) for s in bucket_sens]

            # Extract tenor and basis information for correlation matrix
            tenors = self._extract_tenors(bucket_sens)
            basis_flags = self._extract_basis_flags(bucket_sens)

            # Build intra-bucket correlation matrix
            n = len(ws_list)
            corr = build_commodity_intra_bucket_corr_matrix(
                n, bucket_int,
                tenors=tenors,
                basis_flags=basis_flags,
                scenario=scenario,
            )

            ws_array = np.array(
                [w.weighted_value for w in ws_list], dtype=np.float64
            )

            # Intra-bucket aggregation
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

        # Inter-bucket aggregation with bucket-pair specific correlations
        total_charge = self._inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, scenario
        )

        return RiskChargeResult(
            risk_class=RiskClass.COMMODITY,
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
        """Calculate Commodity vega risk charge for one correlation scenario.

        Vega uses:
        - Risk weight: 100% for Commodity (LH = 120 days, capped).
        - 2-D correlation: option-maturity x underlying.
        - Same three-scenario framework as delta.

        Args:
            sensitivities: Commodity vega sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for vega under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.VEGA, scenario)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            bucket_int = int(bucket)

            # Apply vega risk weight
            ws_list = [self._apply_vega_risk_weight(s) for s in bucket_sens]

            # Build vega correlation matrix
            corr = self._build_vega_correlation_matrix(bucket_sens, bucket_int, scenario)

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

        total_charge = self._inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, scenario
        )

        return RiskChargeResult(
            risk_class=RiskClass.COMMODITY,
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
        """Calculate Commodity curvature risk charge for one correlation scenario.

        Curvature per MAR21.5:
        - CVR_k = max(CVR_k_up, CVR_k_down) for each risk factor.
        - Intra-bucket: K_b = sqrt(max(0, sum(CVR) + sum_{k!=l} rho_kl^2 * psi))
        - Uses squared correlations from delta.

        Args:
            sensitivities: Commodity curvature sensitivities only.
            scenario: LOW / MEDIUM / HIGH.

        Returns:
            RiskChargeResult for curvature under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.CURVATURE, scenario)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            bucket_int = int(bucket)

            cvr_values = np.array(
                [s.value for s in bucket_sens], dtype=np.float64
            )

            # Build delta correlation matrix, then square it
            n = len(bucket_sens)
            tenors = self._extract_tenors(bucket_sens)
            basis_flags = self._extract_basis_flags(bucket_sens)
            delta_corr = build_commodity_intra_bucket_corr_matrix(
                n, bucket_int,
                tenors=tenors,
                basis_flags=basis_flags,
                scenario=scenario,
            )
            rho_sq = delta_corr ** 2

            # Intra-bucket curvature aggregation per MAR21.5
            sum_cvr = float(np.sum(cvr_values))

            cross_term = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    cross_term += (
                        rho_sq[i, j]
                        * self._psi(cvr_values[i], cvr_values[j])
                    )
            cross_term *= 2.0

            k_b = math.sqrt(max(0.0, sum_cvr + cross_term))

            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = sum_cvr

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
                    bucket=bucket,
                    capital_charge=k_b,
                    net_weighted_sensitivity=sum_cvr,
                    weighted_sensitivities=ws_curvature,
                )
            )

        total_charge = self._curvature_inter_bucket(
            bucket_charges, bucket_net_sens, scenario
        )

        return RiskChargeResult(
            risk_class=RiskClass.COMMODITY,
            risk_measure=RiskMeasure.CURVATURE,
            scenario=scenario,
            capital_charge=total_charge,
            bucket_results=bucket_results,
        )

    # --------------------------------------------------------------------- #
    #  Helper: grouping                                                      #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _group_by_bucket(
        sensitivities: list[Sensitivity],
    ) -> dict[str, list[Sensitivity]]:
        """Group sensitivities by bucket.

        Args:
            sensitivities: Flat list of sensitivities.

        Returns:
            Dictionary mapping bucket identifier to its sensitivities.
        """
        grouped: dict[str, list[Sensitivity]] = defaultdict(list)
        for s in sensitivities:
            grouped[s.bucket].append(s)
        return dict(grouped)

    # --------------------------------------------------------------------- #
    #  Helper: extract tenor and basis information                           #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _extract_tenors(sensitivities: list[Sensitivity]) -> list[float] | None:
        """Extract delivery tenors from sensitivities.

        Uses the tenor field (GIRRTenor enum value) if available, falling
        back to option_maturity, then a default of 1.0.

        Args:
            sensitivities: List of sensitivities for a single bucket.

        Returns:
            List of tenor values in years, or None if no tenors are set.
        """
        tenors: list[float] = []
        has_any = False
        for s in sensitivities:
            if s.tenor is not None:
                tenors.append(s.tenor.value)
                has_any = True
            else:
                tenors.append(1.0)  # default delivery tenor
        return tenors if has_any else None

    @staticmethod
    def _extract_basis_flags(sensitivities: list[Sensitivity]) -> list[str] | None:
        """Extract delivery location identifiers from sensitivities.

        Uses the label field as a proxy for delivery location. If all
        labels are empty, returns None (uniform location assumed).

        Args:
            sensitivities: List of sensitivities for a single bucket.

        Returns:
            List of location identifiers, or None if not specified.
        """
        labels = [s.label or "DEFAULT" for s in sensitivities]
        if all(label == "DEFAULT" for label in labels):
            return None
        return labels

    # --------------------------------------------------------------------- #
    #  Helper: delta risk weights                                            #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _apply_delta_risk_weight(
        sensitivity: Sensitivity,
        bucket: int,
    ) -> WeightedSensitivity:
        """Apply risk weight to a single delta sensitivity.

        Args:
            sensitivity: A single delta sensitivity.
            bucket: Bucket number (1-11).

        Returns:
            WeightedSensitivity with WS_k = RW_k * s_k.
        """
        rw = get_commodity_delta_rw(bucket)
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

        For Commodity, the vega risk weight is 100% (LH = 120 days, capped).

        Args:
            sensitivity: A single vega sensitivity.

        Returns:
            WeightedSensitivity with WS_k = 1.0 * s_k.
        """
        rw = COMMODITY_VEGA_RW
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
        bucket: int,
        scenario: CorrelationScenario,
    ) -> np.ndarray:
        """Build intra-bucket correlation matrix for vega risk.

        Vega correlations combine option-maturity and underlying-tenor
        dimensions with the intra-bucket base correlation:

        rho_kl = rho_commodity * rho_opt(k,l) * rho_tenor(k,l)

        Args:
            sensitivities: Vega sensitivities for one bucket.
            bucket: Bucket number.
            scenario: Correlation scenario.

        Returns:
            numpy ndarray of shape (n, n).
        """
        n = len(sensitivities)
        corr = np.eye(n, dtype=np.float64)
        base_rho = COMMODITY_INTRA_CORR[bucket]

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
                        -COMMODITY_VEGA_ALPHA
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
                        -COMMODITY_VEGA_ALPHA
                        * abs(und_i - und_j)
                        / min(und_i, und_j)
                    )

                rho = base_rho * rho_opt * rho_tenor
                rho = apply_correlation_scenario(rho, scenario)
                corr[i, j] = rho
                corr[j, i] = rho

        return corr

    # --------------------------------------------------------------------- #
    #  Helper: inter-bucket aggregation (bucket-pair specific gamma)         #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _inter_bucket_aggregation(
        bucket_charges: dict[str, float],
        bucket_net_sensitivities: dict[str, float],
        scenario: CorrelationScenario,
    ) -> float:
        """Inter-bucket aggregation with bucket-pair specific correlations.

        Uses gamma = 0.40 within energy group (B1-B6), gamma = 0.20 otherwise.
        S_b is capped to [-K_b, K_b] per MAR21.4(4).

        Args:
            bucket_charges: {bucket: K_b} from intra-bucket aggregation.
            bucket_net_sensitivities: {bucket: raw S_b}.
            scenario: Correlation scenario.

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
            raw_s = bucket_net_sensitivities.get(b, 0.0)
            capped_s[b] = max(min(raw_s, k_b), -k_b)

        sum_kb_squared = sum(k ** 2 for k in bucket_charges.values())

        cross_sum = 0.0
        for i, b in enumerate(buckets):
            for j in range(i + 1, len(buckets)):
                c = buckets[j]
                b_int = int(b)
                c_int = int(c)
                gamma = get_commodity_inter_bucket_corr(b_int, c_int)
                gamma = apply_correlation_scenario(gamma, scenario, is_inter_bucket=True)
                cross_sum += gamma * capped_s[b] * capped_s[c]
        cross_sum *= 2.0

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
    #  Helper: curvature inter-bucket aggregation                            #
    # --------------------------------------------------------------------- #

    def _curvature_inter_bucket(
        self,
        bucket_charges: dict[str, float],
        bucket_net_cvr: dict[str, float],
        scenario: CorrelationScenario,
    ) -> float:
        """Curvature inter-bucket aggregation per MAR21.5(5).

        Uses squared gamma correlations between buckets.

        Args:
            bucket_charges: {bucket: K_b} from intra-bucket curvature.
            bucket_net_cvr: {bucket: sum(CVR_k)} per bucket.
            scenario: Correlation scenario.

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
                b_int = int(b)
                c_int = int(c)
                gamma = get_commodity_inter_bucket_corr(b_int, c_int)
                gamma = apply_correlation_scenario(gamma, scenario, is_inter_bucket=True)
                gamma_sq = gamma ** 2
                cvr_b = bucket_net_cvr.get(b, 0.0)
                cvr_c = bucket_net_cvr.get(c, 0.0)
                cross_sum += gamma_sq * self._psi(cvr_b, cvr_c)
        cross_sum *= 2.0

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
        """Validate that all sensitivities belong to the Commodity risk class.

        Args:
            sensitivities: Input sensitivity list.

        Raises:
            ValidationError: If the list is empty or contains non-Commodity
                sensitivities.
        """
        if not sensitivities:
            raise ValidationError("No sensitivities provided for Commodity calculation.")

        non_commodity = [
            s for s in sensitivities if s.risk_class != RiskClass.COMMODITY
        ]
        if non_commodity:
            bad_classes = {s.risk_class.value for s in non_commodity}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.COMMODITY. "
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
            risk_class=RiskClass.COMMODITY,
            risk_measure=risk_measure,
            scenario=scenario,
            capital_charge=0.0,
            bucket_results=[],
        )
