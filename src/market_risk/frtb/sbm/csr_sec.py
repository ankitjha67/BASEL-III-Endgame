"""CSR Securitization Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the Credit Spread Risk -- Securitization capital charges per ERBA
NPR §__.206 (SBM formulas), §__.208(d)-(e) (risk factors) and
§__.209(b)(3)-(4), (c), (d) (buckets, risk weights, correlations) of the
March 2026 US re-proposal, for both:

* **CTP** (correlation trading portfolio) -- 16 buckets, §__.209(b)(3)
  Table 5; intra-bucket name x tenor x basis (35 % / 65 % / 99 %);
  inter-bucket ``gamma_rating x gamma_sector`` (Table 6).
* **Non-CTP** -- 25 buckets, §__.209(b)(4) Table 7; intra-bucket
  tranche x tenor x basis (40 % / 80 % / 99.9 %); inter-bucket gamma 0 %.

Special cases implemented here:

- Other-sector buckets (16 CTP / 25 non-CTP): ``K_b = sum |WS_k|`` for delta
  and vega; ``K_b = max(sum max(CVR+,0), sum max(CVR-,0))`` for curvature.
- Vega RW 100 % (Table 11); curvature RW = bucket delta RW (§__.209(d)).

Risk-factor identification: the sensitivity ``label`` encodes
``tranche::curve`` (non-CTP) or ``name::curve`` (CTP); the curve part is
optional.  Tranches with more than 80 % notional overlap must be given the
same tranche identifier by the caller (§__.209(b)(4)).
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
from src.core.exceptions import CalculationError, ValidationError
from src.core.models import (
    BucketResult,
    RiskChargeResult,
    Sensitivity,
    WeightedSensitivity,
)
from src.market_risk.frtb.sbm.csr_sec_params import (
    CSR_SEC_CTP_RW,
    CSR_SEC_NON_CTP_RW,
    TENORS,
    VEGA_OPTION_MATURITIES,
    VEGA_RISK_WEIGHT,
    apply_correlation_scenario,
    build_csr_sec_correlation_matrix,
    build_csr_sec_curvature_correlation_matrix,
    build_csr_sec_vega_correlation_matrix,
    get_ctp_risk_weight,
    get_curvature_risk_weight,
    get_inter_bucket_correlation,
    get_non_ctp_risk_weight,
    is_other_sector_bucket,
)
from src.utils.aggregation import intra_bucket_aggregation

# ---------------------------------------------------------------------------
#  Result model for CSR Securitization (parallels GIRRResult)
# ---------------------------------------------------------------------------

class CSRSecResult:
    """Complete CSR securitization result across all three correlation scenarios.

    Per ERBA NPR §__.206 the capital requirement is the maximum across
    scenarios; per-measure maxima are exposed for reporting.
    """

    def __init__(
        self,
        delta_low: RiskChargeResult,
        delta_medium: RiskChargeResult,
        delta_high: RiskChargeResult,
        vega_low: RiskChargeResult,
        vega_medium: RiskChargeResult,
        vega_high: RiskChargeResult,
        curvature_low: RiskChargeResult,
        curvature_medium: RiskChargeResult,
        curvature_high: RiskChargeResult,
        is_ctp: bool = False,
    ) -> None:
        self.delta_low = delta_low
        self.delta_medium = delta_medium
        self.delta_high = delta_high
        self.vega_low = vega_low
        self.vega_medium = vega_medium
        self.vega_high = vega_high
        self.curvature_low = curvature_low
        self.curvature_medium = curvature_medium
        self.curvature_high = curvature_high
        self.is_ctp = is_ctp

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
        """Total CSR sec capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge


class CSRSecCalculator:
    """Main CSR securitization risk charge calculator.

    Orchestrates delta, vega and curvature risk charge calculations across
    all three correlation scenarios (low, medium, high) per ERBA NPR §__.206.

    Supports the non-CTP (25 buckets, §__.209(b)(4)) and CTP (16 buckets,
    §__.209(b)(3)) sub-classes through the ``is_ctp`` parameter.

    Usage::

        calculator = CSRSecCalculator()
        result_non_ctp = calculator.calculate(sensitivities, is_ctp=False)
        result_ctp = calculator.calculate(ctp_sensitivities, is_ctp=True)
    """

    def __init__(self) -> None:
        """Initialize with regulatory parameters.

        All parameters are sourced from :mod:`csr_sec_params` at module
        level, so no mutable configuration state is kept here.
        """

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(
        self,
        sensitivities: list[Sensitivity],
        is_ctp: bool = False,
    ) -> CSRSecResult:
        """Calculate the complete CSR securitization capital charge.

        Args:
            sensitivities: CSR sec sensitivities (delta, vega, curvature).
            is_ctp: True for the correlation trading portfolio
                (§__.209(b)(3), 16 buckets); False for non-CTP
                (§__.209(b)(4), 25 buckets).

        Returns:
            :class:`CSRSecResult` with charges for every scenario.

        Raises:
            ValidationError: If any sensitivity has the wrong risk class or
                is malformed.
        """
        risk_class = RiskClass.CSR_SEC_CTP if is_ctp else RiskClass.CSR_SEC_NON_CTP

        if not sensitivities:
            low, med, high = (
                CorrelationScenario.LOW,
                CorrelationScenario.MEDIUM,
                CorrelationScenario.HIGH,
            )

            def empty(measure: RiskMeasure, scenario: CorrelationScenario) -> RiskChargeResult:
                return self._empty_result(measure, scenario, risk_class)

            return CSRSecResult(
                delta_low=empty(RiskMeasure.DELTA, low),
                delta_medium=empty(RiskMeasure.DELTA, med),
                delta_high=empty(RiskMeasure.DELTA, high),
                vega_low=empty(RiskMeasure.VEGA, low),
                vega_medium=empty(RiskMeasure.VEGA, med),
                vega_high=empty(RiskMeasure.VEGA, high),
                curvature_low=empty(RiskMeasure.CURVATURE, low),
                curvature_medium=empty(RiskMeasure.CURVATURE, med),
                curvature_high=empty(RiskMeasure.CURVATURE, high),
                is_ctp=is_ctp,
            )

        self._validate_sensitivities(sensitivities, risk_class)

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
            delta_results[scenario] = self._calculate_delta_charge(
                delta_sens, scenario, is_ctp, risk_class
            )
            vega_results[scenario] = self._calculate_vega_charge(
                vega_sens, scenario, is_ctp, risk_class
            )
            curvature_results[scenario] = self._calculate_curvature_charge(
                curvature_sens, scenario, is_ctp, risk_class
            )

        return CSRSecResult(
            delta_low=delta_results[CorrelationScenario.LOW],
            delta_medium=delta_results[CorrelationScenario.MEDIUM],
            delta_high=delta_results[CorrelationScenario.HIGH],
            vega_low=vega_results[CorrelationScenario.LOW],
            vega_medium=vega_results[CorrelationScenario.MEDIUM],
            vega_high=vega_results[CorrelationScenario.HIGH],
            curvature_low=curvature_results[CorrelationScenario.LOW],
            curvature_medium=curvature_results[CorrelationScenario.MEDIUM],
            curvature_high=curvature_results[CorrelationScenario.HIGH],
            is_ctp=is_ctp,
        )

    # --------------------------------------------------------------------- #
    #  Delta                                                                 #
    # --------------------------------------------------------------------- #

    def _calculate_delta_charge(
        self,
        sensitivities: list[Sensitivity],
        scenario: CorrelationScenario,
        is_ctp: bool,
        risk_class: RiskClass,
    ) -> RiskChargeResult:
        """Calculate the CSR sec delta charge for one correlation scenario.

        Steps per ERBA NPR §__.206 and §__.209(b)(3)/(4):

        1. Group sensitivities by bucket.
        2. Net sensitivities to the same (tranche|name, tenor, curve).
        3. Apply risk weights ``WS_k = RW_b * s_k`` (Table 5 / Table 7).
        4. Other-sector bucket: ``K_b = sum |WS_k|``; otherwise build the
           tranche|name x tenor x basis correlation matrix and aggregate.
        5. Inter-bucket aggregation: gamma 0 % (non-CTP) or the Table 6
           pair-specific gamma (CTP).

        Args:
            sensitivities: CSR sec delta sensitivities only.
            scenario: LOW / MEDIUM / HIGH.
            is_ctp: Whether CTP parameters apply.
            risk_class: The risk class enum value.

        Returns:
            :class:`RiskChargeResult` for delta under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.DELTA, scenario, risk_class)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            bucket_int = self._parse_bucket(bucket, is_ctp)
            netted = self._net_sensitivities(bucket_sens)
            ws_list = [self._apply_delta_risk_weight(s, is_ctp) for s in netted]
            ws_array = np.array([w.weighted_value for w in ws_list], dtype=np.float64)

            if is_other_sector_bucket(bucket_int, is_ctp=is_ctp):
                k_b = float(np.sum(np.abs(ws_array)))
                s_b = float(np.sum(ws_array))
            else:
                corr = build_csr_sec_correlation_matrix(
                    bucket=bucket_int,
                    tranches=[self._get_tranche(s) for s in netted],
                    tenors=[self._get_tenor_years(s) for s in netted],
                    is_ctp=is_ctp,
                    scenario=scenario,
                    curves=[self._get_curve_label(s) for s in netted],
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
            bucket_charges, bucket_net_sens, scenario, is_ctp
        )

        return RiskChargeResult(
            risk_class=risk_class,
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
        is_ctp: bool,
        risk_class: RiskClass,
    ) -> RiskChargeResult:
        """Calculate the CSR sec vega charge for one correlation scenario.

        Per ERBA NPR §__.209(c): RW 100 % (Table 11); intra-bucket
        ``rho_kl = min(rho_tranche|name x exp(-0.01 |Tk-Tl|/min(Tk,Tl)), 1)``
        on option maturities; other-sector bucket ``K_b = sum |WS_k|``;
        inter-bucket gamma equals the delta gamma.

        Args:
            sensitivities: CSR sec vega sensitivities only.
            scenario: LOW / MEDIUM / HIGH.
            is_ctp: Whether CTP parameters apply.
            risk_class: The risk class enum value.

        Returns:
            :class:`RiskChargeResult` for vega under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.VEGA, scenario, risk_class)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            bucket_int = self._parse_bucket(bucket, is_ctp)
            ws_list = [self._apply_vega_risk_weight(s) for s in bucket_sens]
            ws_array = np.array([w.weighted_value for w in ws_list], dtype=np.float64)

            if is_other_sector_bucket(bucket_int, is_ctp=is_ctp):
                k_b = float(np.sum(np.abs(ws_array)))
                s_b = float(np.sum(ws_array))
            else:
                corr = build_csr_sec_vega_correlation_matrix(
                    tranches=[self._get_tranche(s) for s in bucket_sens],
                    option_maturities=[self._get_option_maturity(s) for s in bucket_sens],
                    is_ctp=is_ctp,
                    scenario=scenario,
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
            bucket_charges, bucket_net_sens, scenario, is_ctp
        )

        return RiskChargeResult(
            risk_class=risk_class,
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
        is_ctp: bool,
        risk_class: RiskClass,
    ) -> RiskChargeResult:
        """Calculate the CSR sec curvature charge for one correlation scenario.

        Per ERBA NPR §__.206 and §__.209(d): the sensitivity ``value`` is the
        net ``CVR_k`` per (tranche|name, curve) factor under a parallel shift
        by the bucket's delta RW; intra-bucket uses the squared
        (scenario-adjusted) tranche|name x basis correlation; the
        other-sector bucket uses ``sum max(CVR_k, 0)``; inter-bucket uses
        ``gamma_bc^2`` with the psi function.

        Args:
            sensitivities: CSR sec curvature sensitivities only.
            scenario: LOW / MEDIUM / HIGH.
            is_ctp: Whether CTP parameters apply.
            risk_class: The risk class enum value.

        Returns:
            :class:`RiskChargeResult` for curvature under the given scenario.
        """
        if not sensitivities:
            return self._empty_result(RiskMeasure.CURVATURE, scenario, risk_class)

        grouped = self._group_by_bucket(sensitivities)
        bucket_results: list[BucketResult] = []
        bucket_charges: dict[str, float] = {}
        bucket_net_sens: dict[str, float] = {}

        for bucket, bucket_sens in grouped.items():
            bucket_int = self._parse_bucket(bucket, is_ctp)
            self._check_bucket(bucket_int, is_ctp)

            cvr_values = np.array([s.value for s in bucket_sens], dtype=np.float64)
            sum_cvr = float(np.sum(cvr_values))

            if is_other_sector_bucket(bucket_int, is_ctp=is_ctp):
                k_b = float(np.sum(np.maximum(cvr_values, 0.0)))
            else:
                rho_sq = build_csr_sec_curvature_correlation_matrix(
                    tranches=[self._get_tranche(s) for s in bucket_sens],
                    is_ctp=is_ctp,
                    scenario=scenario,
                    curves=[self._get_curve_label(s) for s in bucket_sens],
                )
                k_b = self._curvature_intra_bucket(cvr_values, rho_sq)

            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = sum_cvr

            rw_curv = get_curvature_risk_weight(bucket_int, is_ctp=is_ctp)
            ws_curvature = [
                WeightedSensitivity(sensitivity=s, risk_weight=rw_curv, weighted_value=s.value)
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
            bucket_charges, bucket_net_sens, scenario, is_ctp
        )

        return RiskChargeResult(
            risk_class=risk_class,
            risk_measure=RiskMeasure.CURVATURE,
            scenario=scenario,
            capital_charge=total_charge,
            bucket_results=bucket_results,
        )

    # --------------------------------------------------------------------- #
    #  Helper: grouping / parsing / netting                                  #
    # --------------------------------------------------------------------- #

    def _group_by_bucket(
        self, sensitivities: list[Sensitivity]
    ) -> dict[str, list[Sensitivity]]:
        """Group sensitivities by bucket identifier.

        Args:
            sensitivities: Flat list of sensitivities.

        Returns:
            Dictionary mapping bucket identifier to its sensitivities.
        """
        grouped: dict[str, list[Sensitivity]] = defaultdict(list)
        for s in sensitivities:
            grouped[s.bucket].append(s)
        return dict(grouped)

    @staticmethod
    def _parse_bucket(bucket: str, is_ctp: bool) -> int:
        """Parse a bucket identifier into an integer bucket number.

        Args:
            bucket: Bucket identifier string.
            is_ctp: Whether CTP buckets are expected (for the error text).

        Returns:
            Integer bucket number.

        Raises:
            CalculationError: If the identifier is not an integer.
        """
        try:
            return int(bucket)
        except (ValueError, TypeError):
            valid = "1-16" if is_ctp else "1-25"
            raise CalculationError(
                f"Invalid CSR Sec bucket identifier: '{bucket}'. "
                f"Expected an integer bucket number ({valid})."
            ) from None

    @staticmethod
    def _check_bucket(bucket: int, is_ctp: bool) -> None:
        """Raise if *bucket* is outside the Table 5 / Table 7 range.

        Args:
            bucket: Integer bucket number.
            is_ctp: Whether CTP buckets are expected.

        Raises:
            CalculationError: If the bucket is unknown.
        """
        table = CSR_SEC_CTP_RW if is_ctp else CSR_SEC_NON_CTP_RW
        if bucket not in table:
            valid = "1-16" if is_ctp else "1-25"
            raise CalculationError(
                f"Bucket {bucket} is not a valid CSR Sec "
                f"{'CTP' if is_ctp else 'Non-CTP'} bucket. Valid buckets: {valid}."
            )

    def _net_sensitivities(self, sensitivities: list[Sensitivity]) -> list[Sensitivity]:
        """Net sensitivities to the same (tranche|name, tenor, curve) factor.

        Per ERBA NPR §__.206 sensitivities to the same risk factor are
        summed before risk-weighting (§__.208(d)(1), (e)(1)).

        Args:
            sensitivities: Sensitivities within a single bucket.

        Returns:
            One netted sensitivity per unique risk factor.
        """
        key_to_sens: dict[tuple[str, float, str], Sensitivity] = {}
        key_to_value: dict[tuple[str, float, str], float] = defaultdict(float)
        for s in sensitivities:
            key = (self._get_tranche(s), self._get_tenor_years(s), self._get_curve_label(s))
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
        self, sensitivity: Sensitivity, is_ctp: bool
    ) -> WeightedSensitivity:
        """Apply the Table 5 (CTP) / Table 7 (non-CTP) delta risk weight.

        ERBA NPR §__.209(b)(3)/(4): uniform across tenors within a bucket.

        Args:
            sensitivity: A single delta sensitivity.
            is_ctp: Whether to use CTP risk weights.

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = RW_b * s_k``.

        Raises:
            CalculationError: If the bucket is not recognised.
        """
        bucket_int = self._parse_bucket(sensitivity.bucket, is_ctp)
        try:
            rw = get_ctp_risk_weight(bucket_int) if is_ctp else get_non_ctp_risk_weight(bucket_int)
        except KeyError:
            valid = "1-16" if is_ctp else "1-25"
            raise CalculationError(
                f"Bucket {bucket_int} is not a valid CSR Sec "
                f"{'CTP' if is_ctp else 'Non-CTP'} bucket. Valid buckets: {valid}."
            ) from None
        return WeightedSensitivity(
            sensitivity=sensitivity,
            risk_weight=rw,
            weighted_value=rw * sensitivity.value,
        )

    def _apply_vega_risk_weight(self, sensitivity: Sensitivity) -> WeightedSensitivity:
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
        is_ctp: bool,
    ) -> float:
        """Inter-bucket aggregation with pair-specific gamma per ERBA NPR §__.206.

        ``Capital = sqrt(sum_b K_b^2 + sum_{b!=c} gamma_bc S_b S_c)`` with
        uncapped ``S_b``; only if the radicand is negative is it recomputed
        with ``S_b = max(min(sum WS, K_b), -K_b)``.  gamma is 0 % for
        non-CTP (§__.209(b)(4)) and Table 6-based for CTP (§__.209(b)(3)).

        Args:
            bucket_charges: ``{bucket: K_b}``.
            bucket_net_sens: ``{bucket: S_b}``.
            scenario: Correlation scenario for gamma adjustment.
            is_ctp: Whether CTP gamma applies.

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
                g = get_inter_bucket_correlation(int(b), int(c), is_ctp=is_ctp)
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
        - Both negative: ``0`` (psi = 0)
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

    def _curvature_intra_bucket(self, cvr_values: np.ndarray, rho_sq: np.ndarray) -> float:
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
        is_ctp: bool,
    ) -> float:
        """Curvature inter-bucket aggregation per ERBA NPR §__.206 / §__.209(d).

        ``Total = sqrt(max(0, sum_b K_b^2 + sum_{b!=c} gamma_bc^2 psi(S_b, S_c)))``

        Args:
            bucket_charges: ``{bucket: K_b}``.
            bucket_net_cvr: ``{bucket: sum CVR_k}``.
            scenario: Correlation scenario for gamma adjustment.
            is_ctp: Whether CTP gamma applies.

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
                    get_inter_bucket_correlation(int(b), int(c), is_ctp=is_ctp),
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
    def _get_tenor_years(sensitivity: Sensitivity) -> float:
        """Extract the tenor vertex in years from a sensitivity.

        Falls back to the first §__.208(d)/(e) vertex (0.5y) when no tenor
        is specified.

        Args:
            sensitivity: A sensitivity object.

        Returns:
            Tenor in years.
        """
        if sensitivity.tenor is not None:
            return float(sensitivity.tenor.value)
        return TENORS[0]

    @staticmethod
    def _get_option_maturity(sensitivity: Sensitivity) -> float:
        """Extract the option maturity in years from a vega sensitivity.

        Args:
            sensitivity: A vega sensitivity.

        Returns:
            Option maturity in years (defaults to 0.5y).
        """
        if sensitivity.option_maturity:
            return float(sensitivity.option_maturity)
        return VEGA_OPTION_MATURITIES[0]

    @staticmethod
    def _get_tranche(sensitivity: Sensitivity) -> str:
        """Extract the tranche (non-CTP) / name (CTP) identifier from the label.

        The label encodes ``tranche::curve``; the identifier is the portion
        before the last ``::`` separator.

        Args:
            sensitivity: A sensitivity object.

        Returns:
            Tranche / name identifier (``"DEFAULT"`` if empty).
        """
        label = sensitivity.label or ""
        if "::" in label:
            return label.rsplit("::", maxsplit=1)[0] or "DEFAULT"
        return label or "DEFAULT"

    @staticmethod
    def _get_curve_label(sensitivity: Sensitivity) -> str:
        """Extract the curve label from a sensitivity.

        The portion after the last ``::`` separator, defaulting to
        ``"DEFAULT"`` (all sensitivities on the same curve).

        Args:
            sensitivity: A sensitivity object.

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
    def _validate_sensitivities(
        sensitivities: list[Sensitivity],
        risk_class: RiskClass,
    ) -> None:
        """Validate CSR sec inputs.

        Checks per ERBA NPR §__.208(d)-(e): risk class, delta tenor present
        and on a prescribed vertex (0.5, 1, 3, 5, 10), vega option maturity
        present.

        Args:
            sensitivities: Input sensitivity list.
            risk_class: Expected risk class (CSR_SEC_NON_CTP or CSR_SEC_CTP).

        Raises:
            ValidationError: On any violation.
        """
        if not sensitivities:
            raise ValidationError(
                f"No sensitivities provided for {risk_class.value} calculation."
            )

        invalid = [s for s in sensitivities if s.risk_class != risk_class]
        if invalid:
            bad_classes = {s.risk_class.value for s in invalid}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.{risk_class.value}. "
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
                        f"{s.tenor.value}y; CSR sec vertices are {TENORS} "
                        f"(ERBA NPR §__.208(d)-(e))."
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
        risk_class: RiskClass,
    ) -> RiskChargeResult:
        """Return a zero-charge result for a given measure and scenario.

        Args:
            risk_measure: DELTA, VEGA, or CURVATURE.
            scenario: Correlation scenario.
            risk_class: The risk class enum value.

        Returns:
            :class:`RiskChargeResult` with zero charge and no bucket results.
        """
        return RiskChargeResult(
            risk_class=risk_class,
            risk_measure=risk_measure,
            scenario=scenario,
            capital_charge=0.0,
            bucket_results=[],
        )
