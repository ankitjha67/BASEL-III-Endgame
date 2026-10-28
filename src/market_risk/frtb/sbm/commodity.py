"""Commodity Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the Commodity risk capital charge calculation per the US ERBA
NPR (March 2026), 12 CFR 217 Subpart F §__.206-§__.209 (BCBS d457
MAR21.19-21.20 cross-reference).

Commodity covers:
- Delta risk: Linear sensitivities to commodity prices by delivery location
  and contract maturity (§__.208(b)(6); Table 9/10 parameters per
  §__.209(b)(6), 12 buckets).
- Vega risk: Sensitivities to implied volatilities of commodity options
  (RW 100%, §__.209 Table 11).
- Curvature risk: Non-linear risk from options on commodities (curvature
  RW = highest delta RW of the bucket; correlations squared).

Sensitivity conventions for this risk class:

* ``bucket`` -- Table 9 bucket number as a string (``"1"`` .. ``"12"``).
* ``tenor``  -- contract maturity vertex (``GIRRTenor``); ``None`` means
  spot (maturity 0).
* ``label``  -- delivery-location identifier (basis); the generic label
  ``"DEFAULT"`` / empty means a single location.
"""

from __future__ import annotations

import math
from collections import defaultdict

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
from src.market_risk.frtb.sbm.commodity_params import (
    COMMODITY_DELTA_MATURITIES,
    COMMODITY_INTRA_CORR,
    COMMODITY_VEGA_ALPHA,
    COMMODITY_VEGA_RW,
    apply_correlation_scenario,
    build_commodity_intra_bucket_corr_matrix,
    get_commodity_curvature_rw,
    get_commodity_delta_rw,
    get_commodity_inter_bucket_corr,
)
from src.utils.aggregation import intra_bucket_aggregation

# Spot maturity used when a commodity sensitivity carries no tenor
# (ERBA NPR §__.208(b)(6): maturity vertex 0 = spot).
COMMODITY_SPOT_MATURITY: float = COMMODITY_DELTA_MATURITIES[0]


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
    all three correlation scenarios (Low, Medium, High) per ERBA NPR
    §__.206(c) and §__.209(b)(6).

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

        Steps per ERBA NPR §__.206(b) and §__.209(b)(6):
        1. Group sensitivities by bucket (1-12).
        2. Apply risk weights: WS_k = RW_k * s_k (Table 9).
        3. Build intra-bucket correlation matrix
           rho_cty (Table 10) * rho_tenor (99%) * rho_basis (99.9%).
        4. Intra-bucket aggregation: K_b = sqrt(WS^T * rho * WS).
        5. Inter-bucket aggregation with gamma = 20% (0% with bucket 11).

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

        Vega per ERBA NPR §__.209 (Table 11 and vega paragraph):
        - Risk weight: 100% for Commodity.
        - Correlation: min(rho_delta * rho_option_maturity, 1), alpha = 1%.
        - Inter-bucket gamma = delta gamma.

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

        Curvature per ERBA NPR §__.206(b)(3) and §__.209 (curvature):
        - CVR_k is the net curvature risk position per commodity factor,
          computed with a shock equal to the highest delta risk weight of
          the bucket (:func:`commodity_params.get_commodity_curvature_rw`).
        - Intra-bucket: K_b = sqrt(max(0, sum max(CVR,0)^2
          + sum_{k!=l} rho_kl^2 * psi)) using SQUARED delta correlations.
        - Inter-bucket: squared delta gamma.

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

            # Intra-bucket curvature aggregation per MAR21.5(4)
            # K_b = sqrt(max(0, sum_k max(CVR_k,0)^2 + sum_{k!=l} rho^2 CVR_k CVR_l psi))
            sum_cvr = float(np.sum(cvr_values))          # S_b for inter-bucket
            diag_term = float(np.sum(np.maximum(cvr_values, 0.0) ** 2))

            cross_term = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    cross_term += (
                        rho_sq[i, j]
                        * self._psi(cvr_values[i], cvr_values[j])
                    )
            cross_term *= 2.0

            k_b = math.sqrt(max(0.0, diag_term + cross_term))

            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = sum_cvr

            # The recorded risk weight is the curvature shock size.
            curvature_rw = get_commodity_curvature_rw(bucket_int)
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
        """Extract contract maturities from sensitivities.

        Uses the tenor field (GIRRTenor enum value) if available; a missing
        tenor means spot (maturity 0 on the ERBA NPR §__.208(b)(6) grid
        {0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30}).

        Args:
            sensitivities: List of sensitivities for a single bucket.

        Returns:
            List of maturities in years, or None if no tenors are set
            (all spot, so the tenor correlation factor is 100%).
        """
        tenors: list[float] = []
        has_any = False
        for s in sensitivities:
            if s.tenor is not None:
                tenors.append(s.tenor.value)
                has_any = True
            else:
                tenors.append(COMMODITY_SPOT_MATURITY)
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

        ERBA NPR §__.209(b)(6) Table 9.

        Args:
            sensitivity: A single delta sensitivity.
            bucket: Bucket number (1-12).

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

        For Commodity, the vega risk weight is 100% per ERBA NPR §__.209
        Table 11.

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

        ERBA NPR §__.209 (vega paragraph): for risk classes other than
        GIRR,

            rho_kl = min(rho_delta * rho_opt(k,l), 1)

        where rho_delta is the Table 10 commodity correlation of the bucket
        and rho_opt(k,l) = exp(-alpha * |Tk_opt - Tl_opt| / min(Tk_opt, Tl_opt)),
        alpha = 1%.

        Args:
            sensitivities: Vega sensitivities for one bucket.
            bucket: Bucket number.
            scenario: Correlation scenario.

        Returns:
            numpy ndarray of shape (n, n).
        """
        n = len(sensitivities)
        corr = np.eye(n, dtype=np.float64)
        rho_delta = COMMODITY_INTRA_CORR[bucket]

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

                rho = min(rho_delta * rho_opt, 1.0)
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

        ERBA NPR §__.209(b)(6): gamma = 20% among buckets 1-10 and 12;
        0% whenever either bucket is 11 (other commodity).  S_b is capped
        to [-K_b, K_b] only if the radicand is negative (§__.206(b)(1)).

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
        sum_kb_squared = sum(k ** 2 for k in bucket_charges.values())

        gammas: dict[tuple[str, str], float] = {}
        for i, b in enumerate(buckets):
            for j in range(i + 1, len(buckets)):
                c = buckets[j]
                g = get_commodity_inter_bucket_corr(int(b), int(c))
                gammas[(b, c)] = apply_correlation_scenario(g, scenario, is_inter_bucket=True)

        def _cross(s: dict[str, float]) -> float:
            return 2.0 * sum(g * s[b] * s[c] for (b, c), g in gammas.items())

        # MAR21.4(4): first pass uses UNCAPPED S_b
        raw_s = {b: bucket_net_sensitivities.get(b, 0.0) for b in buckets}
        total_variance = sum_kb_squared + _cross(raw_s)
        if total_variance >= 0:
            return math.sqrt(total_variance)

        # MAR21.4(5): only if negative, recompute with S_b capped to [-K_b, K_b]
        capped_s = {
            b: max(min(raw_s[b], bucket_charges[b]), -bucket_charges[b])
            for b in buckets
        }
        total_variance = sum_kb_squared + _cross(capped_s)
        return math.sqrt(max(total_variance, 0.0))

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
        """Curvature inter-bucket aggregation per ERBA NPR §__.206(b)(3).

        Uses the squared delta gamma correlations between buckets
        (§__.209 curvature paragraph).

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
