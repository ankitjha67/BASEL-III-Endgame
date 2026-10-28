"""CSR Non-Securitization Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the Credit Spread Risk -- Non-Securitization (CSR non-sec) capital
charge per ERBA NPR §__.206 (SBM formulas), §__.208(c) (risk factors) and
§__.209(b)(2), (c), (d) (buckets, risk weights, correlations) of the March
2026 US re-proposal.

CSR non-sec covers:

- Delta risk: linear sensitivities to credit spreads across the 20 buckets
  of §__.209(b)(2) Table 3 at the five tenor vertices of §__.208(c)(1).
- Vega risk: sensitivities to implied volatilities of credit spread options
  at the five option maturities of §__.208(c)(2); RW 100 % (Table 11).
- Curvature risk: non-linear risk from a parallel shift of each name's
  curve by the bucket's delta risk weight (§__.209(d)).

Special cases implemented here:

- Bucket 18 (other sector): intra-bucket ``K_b = sum |WS_k|`` for delta and
  vega, and ``K_b = max(sum max(CVR+,0), sum max(CVR-,0))`` for curvature
  (§__.209(b)(2), (d)).
- Inter-bucket ``gamma_bc = gamma_rating x gamma_sector`` is pair-specific
  (20x20) rather than a single scalar.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from pydantic import BaseModel

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
from src.market_risk.frtb.sbm.csr_nonsec_params import (
    DELTA_RISK_WEIGHTS,
    INTER_BUCKET_CORRELATIONS,
    OTHER_SECTOR_BUCKET,
    TENORS,
    VEGA_OPTION_MATURITIES,
    VEGA_RISK_WEIGHT,
    apply_correlation_scenario,
    build_csr_nonsec_correlation_matrix,
    build_csr_nonsec_curvature_correlation_matrix,
    build_csr_nonsec_vega_correlation_matrix,
    get_delta_risk_weight,
    get_inter_bucket_correlation,
)
from src.utils.aggregation import intra_bucket_aggregation


class CSRNonSecCalculator:
    """Main CSR non-securitization risk charge calculator.

    Orchestrates delta, vega and curvature risk charge calculations across
    all three correlation scenarios (low, medium, high) per ERBA NPR §__.206
    using the bucket / risk-weight / correlation parameters of §__.209(b)(2).

    Within each bucket (other than 18) correlations decompose into three
    multiplicative factors: name, tenor and basis (curve).

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
        """Calculate the complete CSR non-sec capital charge.

        Runs delta, vega and curvature calculations across all three
        correlation scenarios per ERBA NPR §__.206.

        Args:
            sensitivities: List of CSR non-sec sensitivities (delta, vega,
                curvature).

        Returns:
            :class:`CSRNonSecResult` with charges for every scenario.

        Raises:
            ValidationError: If any sensitivity does not belong to the
                CSR_NON_SEC risk class or is malformed.
        """
        if not sensitivities:
            empty = self._empty_result
            low, med, high = (
                CorrelationScenario.LOW,
                CorrelationScenario.MEDIUM,
                CorrelationScenario.HIGH,
            )
            return CSRNonSecResult(
                delta_low=empty(RiskMeasure.DELTA, low),
                delta_medium=empty(RiskMeasure.DELTA, med),
                delta_high=empty(RiskMeasure.DELTA, high),
                vega_low=empty(RiskMeasure.VEGA, low),
                vega_medium=empty(RiskMeasure.VEGA, med),
                vega_high=empty(RiskMeasure.VEGA, high),
                curvature_low=empty(RiskMeasure.CURVATURE, low),
                curvature_medium=empty(RiskMeasure.CURVATURE, med),
                curvature_high=empty(RiskMeasure.CURVATURE, high),
            )

        self._validate_sensitivities(sensitivities)

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
        """Calculate the CSR non-sec delta charge for one correlation scenario.

        Steps per ERBA NPR §__.206 and §__.209(b)(2):

        1. Group sensitivities by bucket (1-20).
        2. Net sensitivities to the same (name, tenor, curve) risk factor.
        3. Apply risk weights: ``WS_k = RW_b * s_k`` (Table 3).
        4. Buckets other than 18: build the name x tenor x basis correlation
           matrix and aggregate ``K_b = sqrt(max(WS' rho WS, 0))``.
           Bucket 18: ``K_b = sum |WS_k|``.
        5. Inter-bucket aggregation with the pair-specific gamma matrix.

        Args:
            sensitivities: CSR non-sec delta sensitivities only.
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
            bucket_num = self._parse_bucket(bucket_str)

            netted = self._net_sensitivities(bucket_sens)
            ws_list = [self._apply_delta_risk_weight(s, bucket_num) for s in netted]
            ws_array = np.array([w.weighted_value for w in ws_list], dtype=np.float64)

            if bucket_num == OTHER_SECTOR_BUCKET:
                # §__.209(b)(2): other sector -- K_b = sum |WS_k|
                k_b = float(np.sum(np.abs(ws_array)))
                s_b = float(np.sum(ws_array))
            else:
                issuers = [self._get_issuer(s) for s in netted]
                tenors = [self._get_tenor_value(s) for s in netted]
                curves = [self._get_curve_label(s) for s in netted]
                corr = build_csr_nonsec_correlation_matrix(
                    bucket=bucket_num,
                    issuers=issuers,
                    tenors=tenors,
                    curves=curves,
                    scenario=scenario,
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
        """Calculate the CSR non-sec vega charge for one correlation scenario.

        Per ERBA NPR §__.209(c):

        - Risk weight 100 % (Table 11).
        - Intra-bucket ``rho_kl = min(rho_name x exp(-0.01 |Tk-Tl|/min(Tk,Tl)), 1)``
          on option maturities; bucket 18 uses ``K_b = sum |WS_k|``.
        - Inter-bucket gamma equals the delta gamma.

        Args:
            sensitivities: CSR non-sec vega sensitivities only.
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
            bucket_num = self._parse_bucket(bucket_str)
            ws_list = [self._apply_vega_risk_weight(s) for s in bucket_sens]
            ws_array = np.array([w.weighted_value for w in ws_list], dtype=np.float64)

            if bucket_num == OTHER_SECTOR_BUCKET:
                k_b = float(np.sum(np.abs(ws_array)))
                s_b = float(np.sum(ws_array))
            else:
                corr = build_csr_nonsec_vega_correlation_matrix(
                    bucket=bucket_num,
                    issuers=[self._get_issuer(s) for s in bucket_sens],
                    option_maturities=[
                        self._get_option_maturity(s) for s in bucket_sens
                    ],
                    scenario=scenario,
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
        """Calculate the CSR non-sec curvature charge for one correlation scenario.

        Per ERBA NPR §__.206 and §__.209(d):

        - The sensitivity ``value`` carries the net curvature risk ``CVR_k``
          of each (name, curve) risk factor under the parallel shift by the
          bucket's delta risk weight.
        - Buckets other than 18:
          ``K_b = sqrt(max(0, sum max(CVR_k,0)^2 + sum_{k!=l} rho_kl^2 psi CVR_k CVR_l))``
          with ``rho_kl`` the (scenario-adjusted) delta name x basis
          correlation.
        - Bucket 18: ``K_b = max(sum max(CVR+,0), sum max(CVR-,0))``; with
          one net CVR per factor this is ``sum max(CVR_k, 0)``.
        - Inter-bucket uses ``gamma_bc^2`` with the psi function.

        Args:
            sensitivities: CSR non-sec curvature sensitivities only.
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
            bucket_num = self._parse_bucket(bucket_str)
            if bucket_num not in DELTA_RISK_WEIGHTS:
                raise CalculationError(
                    f"Bucket {bucket_num} is not a valid CSR non-sec bucket (1-20)."
                )

            cvr_values = np.array([s.value for s in bucket_sens], dtype=np.float64)
            sum_cvr = float(np.sum(cvr_values))

            if bucket_num == OTHER_SECTOR_BUCKET:
                # §__.209(d): other sector -- no intra-bucket offsetting
                k_b = float(np.sum(np.maximum(cvr_values, 0.0)))
            else:
                rho_sq = build_csr_nonsec_curvature_correlation_matrix(
                    bucket=bucket_num,
                    issuers=[self._get_issuer(s) for s in bucket_sens],
                    curves=[self._get_curve_label(s) for s in bucket_sens],
                    scenario=scenario,
                )
                k_b = self._curvature_intra_bucket(cvr_values, rho_sq)

            bucket_charges[bucket_str] = k_b
            bucket_net_sens[bucket_str] = sum_cvr

            ws_curvature = [
                WeightedSensitivity(
                    sensitivity=s,
                    risk_weight=get_delta_risk_weight(bucket_num),
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
    #  Helper: grouping / parsing                                            #
    # --------------------------------------------------------------------- #

    def _group_by_bucket(
        self, sensitivities: list[Sensitivity]
    ) -> dict[str, list[Sensitivity]]:
        """Group sensitivities by bucket number.

        For CSR non-sec the bucket field holds the bucket number as a string
        (e.g. ``"3"`` for IG financials).

        Args:
            sensitivities: Flat list of sensitivities.

        Returns:
            Dictionary mapping bucket string to its sensitivities.
        """
        grouped: dict[str, list[Sensitivity]] = defaultdict(list)
        for s in sensitivities:
            grouped[s.bucket].append(s)
        return dict(grouped)

    @staticmethod
    def _parse_bucket(bucket_str: str) -> int:
        """Parse the bucket identifier into a Table 3 bucket number.

        Args:
            bucket_str: Bucket identifier string.

        Returns:
            Integer bucket number.

        Raises:
            CalculationError: If the identifier is not an integer.
        """
        try:
            return int(bucket_str)
        except (ValueError, TypeError):
            raise CalculationError(
                f"Invalid CSR non-sec bucket identifier: '{bucket_str}'. "
                f"Expected an integer bucket number (1-20)."
            ) from None

    # --------------------------------------------------------------------- #
    #  Helper: netting                                                       #
    # --------------------------------------------------------------------- #

    def _net_sensitivities(
        self, sensitivities: list[Sensitivity]
    ) -> list[Sensitivity]:
        """Net sensitivities to the same (name, tenor, curve) risk factor.

        Per ERBA NPR §__.206 sensitivities to the same risk factor are
        summed before risk-weighting.  For CSR non-sec a delta risk factor is
        identified by (name, tenor vertex, curve) per §__.208(c)(1).

        Args:
            sensitivities: Sensitivities within a single bucket.

        Returns:
            One netted sensitivity per unique (name, tenor, curve) triple.
        """
        key_to_sens: dict[tuple[str, float, str], Sensitivity] = {}
        key_to_value: dict[tuple[str, float, str], float] = defaultdict(float)

        for s in sensitivities:
            key = (self._get_issuer(s), self._get_tenor_value(s), self._get_curve_label(s))
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
    #  Helper: risk weights                                                  #
    # --------------------------------------------------------------------- #

    def _apply_delta_risk_weight(
        self, sensitivity: Sensitivity, bucket: int
    ) -> WeightedSensitivity:
        """Apply the Table 3 delta risk weight to a single sensitivity.

        ERBA NPR §__.209(b)(2): the risk weight is uniform within a bucket.

        Args:
            sensitivity: A single delta sensitivity.
            bucket: Bucket number (1-20).

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = RW_b * s_k``.

        Raises:
            CalculationError: If the bucket has no defined risk weight.
        """
        try:
            rw = get_delta_risk_weight(bucket)
        except KeyError:
            raise CalculationError(
                f"No delta risk weight defined for CSR non-sec bucket {bucket} "
                f"(valid buckets 1-20)."
            ) from None
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=rw,
            weighted_value=rw * sensitivity.value,
        )

    def _apply_vega_risk_weight(
        self, sensitivity: Sensitivity
    ) -> WeightedSensitivity:
        """Apply the vega risk weight (100 %) per ERBA NPR §__.209(c) Table 11.

        Args:
            sensitivity: A single vega sensitivity.

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = 1.0 * s_k``.
        """
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=VEGA_RISK_WEIGHT,
            weighted_value=VEGA_RISK_WEIGHT * sensitivity.value,
        )

    # --------------------------------------------------------------------- #
    #  Helper: inter-bucket aggregation                                      #
    # --------------------------------------------------------------------- #

    def _inter_bucket_aggregation(
        self,
        bucket_charges: dict[str, float],
        bucket_net_sens: dict[str, float],
        scenario: CorrelationScenario,
    ) -> float:
        """Inter-bucket aggregation with the pair-specific gamma matrix.

        Per ERBA NPR §__.206::

            Capital = sqrt(sum_b K_b^2 + sum_{b!=c} gamma_bc * S_b * S_c)

        with uncapped ``S_b``; only if the radicand is negative is the
        calculation repeated with ``S_b = max(min(sum WS, K_b), -K_b)``.
        ``gamma_bc = gamma_rating x gamma_sector`` per §__.209(b)(2).

        Args:
            bucket_charges: ``{bucket_str: K_b}``.
            bucket_net_sens: ``{bucket_str: S_b}``.
            scenario: Correlation scenario for gamma adjustment.

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
                g = get_inter_bucket_correlation(int(b), int(c))
                gammas[(b, c)] = apply_correlation_scenario(g, scenario, is_inter_bucket=True)

        def _cross(s: dict[str, float]) -> float:
            return 2.0 * sum(g * s[b] * s[c] for (b, c), g in gammas.items())

        raw_s = {b: bucket_net_sens.get(b, 0.0) for b in buckets}
        total_variance = sum_kb_squared + _cross(raw_s)
        if total_variance >= 0:
            return math.sqrt(total_variance)

        capped_s = {
            b: max(min(raw_s[b], bucket_charges[b]), -bucket_charges[b])
            for b in buckets
        }
        total_variance = sum_kb_squared + _cross(capped_s)
        return math.sqrt(max(total_variance, 0.0))

    # --------------------------------------------------------------------- #
    #  Helper: curvature                                                     #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _psi(cvr_k: float, cvr_l: float) -> float:
        """Curvature psi-weighted cross product per ERBA NPR §__.206.

        - Both positive: ``+|CVR_k| * |CVR_l|``
        - Both negative: ``0`` (psi = 0, no diversification benefit)
        - Mixed signs: ``-|CVR_k| * |CVR_l|``

        Args:
            cvr_k: Curvature risk for factor *k*.
            cvr_l: Curvature risk for factor *l*.

        Returns:
            Signed cross product for the curvature aggregation formula.
        """
        abs_product = abs(cvr_k) * abs(cvr_l)
        if cvr_k > 0 and cvr_l > 0:
            return abs_product
        elif cvr_k < 0 and cvr_l < 0:
            return 0.0
        else:
            return -abs_product

    def _curvature_intra_bucket(
        self, cvr_values: np.ndarray, rho_sq: np.ndarray
    ) -> float:
        """Intra-bucket curvature aggregation per ERBA NPR §__.206.

        ``K_b = sqrt(max(0, sum_k max(CVR_k,0)^2 + sum_{k!=l} rho_kl^2 psi(CVR_k,CVR_l)))``

        Args:
            cvr_values: Net curvature risk per factor.
            rho_sq: Squared (scenario-adjusted) delta correlation matrix.

        Returns:
            Bucket curvature charge ``K_b``.
        """
        n = len(cvr_values)
        diag_term = float(np.sum(np.maximum(cvr_values, 0.0) ** 2))
        cross_term = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                cross_term += rho_sq[i, j] * self._psi(cvr_values[i], cvr_values[j])
        cross_term *= 2.0
        return math.sqrt(max(0.0, diag_term + cross_term))

    def _curvature_inter_bucket(
        self,
        bucket_charges: dict[str, float],
        bucket_net_cvr: dict[str, float],
        scenario: CorrelationScenario,
    ) -> float:
        """Curvature inter-bucket aggregation per ERBA NPR §__.206 / §__.209(d).

        ``Total = sqrt(max(0, sum_b K_b^2 + sum_{b!=c} gamma_bc^2 psi(S_b, S_c)))``
        where ``gamma_bc`` is the (scenario-adjusted) delta inter-bucket
        correlation and the curvature gamma is its square.

        Args:
            bucket_charges: ``{bucket_str: K_b}``.
            bucket_net_cvr: ``{bucket_str: sum CVR_k}``.
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
                gamma = apply_correlation_scenario(
                    get_inter_bucket_correlation(int(b), int(c)),
                    scenario,
                    is_inter_bucket=True,
                )
                cross_sum += (gamma ** 2) * self._psi(
                    bucket_net_cvr.get(b, 0.0), bucket_net_cvr.get(c, 0.0)
                )
        cross_sum *= 2.0

        return math.sqrt(max(0.0, sum_kb_sq + cross_sum))

    # --------------------------------------------------------------------- #
    #  Helper: risk-factor attribute extraction                              #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _get_tenor_value(sensitivity: Sensitivity) -> float:
        """Extract the tenor vertex in years from a sensitivity.

        Falls back to the first §__.208(c)(1) vertex (0.5y) when no tenor
        is set (curvature / vega factors carry no tenor).

        Args:
            sensitivity: A single sensitivity.

        Returns:
            Tenor in years.
        """
        if sensitivity.tenor is not None:
            return float(sensitivity.tenor.value)
        return TENORS[0]

    @staticmethod
    def _get_option_maturity(sensitivity: Sensitivity) -> float:
        """Extract the option maturity in years from a vega sensitivity.

        Falls back to the first §__.208(c)(2) option maturity (0.5y).

        Args:
            sensitivity: A single vega sensitivity.

        Returns:
            Option maturity in years.
        """
        if sensitivity.option_maturity:
            return float(sensitivity.option_maturity)
        return VEGA_OPTION_MATURITIES[0]

    @staticmethod
    def _get_issuer(sensitivity: Sensitivity) -> str:
        """Extract the name (issuer / index) from a sensitivity label.

        The label encodes ``name::curve`` or just the name; the name is the
        portion before the last ``::`` separator.

        Args:
            sensitivity: A single sensitivity.

        Returns:
            Name string (``"UNKNOWN"`` if the label is empty).
        """
        label = sensitivity.label or ""
        if "::" in label:
            return label.rsplit("::", maxsplit=1)[0] or "UNKNOWN"
        return label or "UNKNOWN"

    @staticmethod
    def _get_curve_label(sensitivity: Sensitivity) -> str:
        """Extract the curve label from a sensitivity.

        The label encodes ``name::curve`` (e.g. ``"ACME::CDS"``); the curve
        is the portion after the last ``::`` separator, defaulting to
        ``"DEFAULT"`` (all sensitivities on the same curve).

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
        """Validate CSR non-sec inputs.

        Checks per ERBA NPR §__.208(c): risk class, delta tenor present and
        on a prescribed vertex (0.5, 1, 3, 5, 10), vega option maturity
        present.

        Args:
            sensitivities: Input sensitivity list.

        Raises:
            ValidationError: On any violation.
        """
        if not sensitivities:
            raise ValidationError("No sensitivities provided for CSR Non-Sec calculation.")

        non_csr = [s for s in sensitivities if s.risk_class != RiskClass.CSR_NON_SEC]
        if non_csr:
            bad_classes = {s.risk_class.value for s in non_csr}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.CSR_NON_SEC. "
                f"Found: {bad_classes}"
            )

        for s in sensitivities:
            if s.risk_measure == RiskMeasure.DELTA:
                if s.tenor is None:
                    raise ValidationError(
                        f"Delta sensitivity for bucket '{s.bucket}' must specify a tenor."
                    )
                if float(s.tenor.value) not in TENORS:
                    raise ValidationError(
                        f"Delta sensitivity for bucket '{s.bucket}' has tenor "
                        f"{s.tenor.value}y; CSR non-sec vertices are {TENORS} "
                        f"(ERBA NPR §__.208(c)(1))."
                    )
            if s.risk_measure == RiskMeasure.VEGA and s.option_maturity is None:
                raise ValidationError(
                    f"Vega sensitivity for bucket '{s.bucket}' must specify an option_maturity."
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

class CSRNonSecResult(BaseModel):
    """Complete CSR non-sec result across all three correlation scenarios.

    Per ERBA NPR §__.206 the capital requirement is the maximum across
    scenarios of the summed delta + vega + curvature charge; per-measure
    maxima are exposed for reporting.
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
        """Total CSR non-sec capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge
