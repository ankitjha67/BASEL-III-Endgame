"""CSR Securitization Risk Charge Calculator -- FRTB Sensitivities-Based Method.

Implements the Credit Spread Risk -- Securitization (both Non-CTP and CTP)
capital charge calculation per MAR21.14-21.15 of the Basel III Endgame framework.

CSR Securitization covers:
- Delta risk: Linear sensitivities to credit spreads of securitized products
- Vega risk: Sensitivities to implied volatilities of securitization options
- Curvature risk: Non-linear risk from options on securitized credit

Non-CTP (Correlation Trading Portfolio excluded):
  8 buckets -- RMBS (prime/mid-prime/sub-prime), CMBS, ABS Consumer,
  CLO non-CTP, ABS Other, Other Securitization

CTP (Correlation Trading Portfolio):
  5 buckets -- CTP IG, CTP HY, CTP Index IG, CTP Index HY, CTP Other

Reference: BCBS d457 MAR21.14-21.15, US Federal Reserve Basel III Endgame Final Rule.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

import numpy as np

from src.core.enums import (
    CorrelationScenario,
    CSRSecBucket,
    CSRSecCTPBucket,
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
    CSR_SEC_CTP_CORR,
    CSR_SEC_CTP_RW,
    CSR_SEC_NON_CTP_CORR,
    CSR_SEC_NON_CTP_RW,
    GAMMA_CTP,
    GAMMA_NON_CTP,
    VEGA_ALPHA,
    VEGA_RISK_WEIGHT,
    apply_correlation_scenario,
    build_csr_sec_correlation_matrix,
    get_ctp_risk_weight,
    get_inter_bucket_correlation,
    get_non_ctp_risk_weight,
)
from src.utils.aggregation import intra_bucket_aggregation, inter_bucket_aggregation


# ---------------------------------------------------------------------------
#  Result model for CSR Securitization (parallels GIRRResult)
# ---------------------------------------------------------------------------

class CSRSecResult:
    """Complete CSR Securitization result across all three correlation scenarios.

    Per MAR21.6, the capital requirement is max across scenarios for each
    risk measure (delta, vega, curvature).
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
        """Total CSR Sec capital charge = delta + vega + curvature."""
        return self.delta_charge + self.vega_charge + self.curvature_charge


class CSRSecCalculator:
    """Main CSR Securitization risk charge calculator.

    Orchestrates delta, vega, and curvature risk charge calculations across
    all three correlation scenarios (Low, Medium, High) per MAR21.14-21.15.

    Supports both Non-CTP (8 buckets) and CTP (5 buckets) sub-portfolios
    through the ``is_ctp`` parameter on the :meth:`calculate` method.

    Usage::

        calculator = CSRSecCalculator()
        # Non-CTP
        result_non_ctp = calculator.calculate(sensitivities, is_ctp=False)
        # CTP
        result_ctp = calculator.calculate(ctp_sensitivities, is_ctp=True)
        print(result_non_ctp.total_charge)
    """

    # --------------------------------------------------------------------- #
    #  Initialization                                                        #
    # --------------------------------------------------------------------- #

    def __init__(self) -> None:
        """Initialize with regulatory parameters.

        All parameters are sourced from :mod:`csr_sec_params` at module level,
        so no mutable configuration state is kept here.
        """

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def calculate(
        self,
        sensitivities: list[Sensitivity],
        is_ctp: bool = False,
    ) -> CSRSecResult:
        """Calculate the complete CSR Securitization capital charge.

        Runs delta, vega, and curvature calculations across all three
        correlation scenarios (Low, Medium, High) per MAR21.6.

        Args:
            sensitivities: List of CSR Sec sensitivities (delta, vega, curvature).
            is_ctp: If True, treat as Correlation Trading Portfolio (CTP)
                with 5 buckets per MAR21.15. If False, treat as Non-CTP
                with 8 buckets per MAR21.14.

        Returns:
            :class:`CSRSecResult` with charges for every scenario.

        Raises:
            ValidationError: If no sensitivities are provided or any
                sensitivity does not belong to the correct risk class.
        """
        risk_class = RiskClass.CSR_SEC_CTP if is_ctp else RiskClass.CSR_SEC_NON_CTP

        if not sensitivities:
            empty = self._empty_result(RiskMeasure.DELTA, CorrelationScenario.MEDIUM, risk_class)
            return CSRSecResult(
                delta_low=self._empty_result(RiskMeasure.DELTA, CorrelationScenario.LOW, risk_class),
                delta_medium=self._empty_result(RiskMeasure.DELTA, CorrelationScenario.MEDIUM, risk_class),
                delta_high=self._empty_result(RiskMeasure.DELTA, CorrelationScenario.HIGH, risk_class),
                vega_low=self._empty_result(RiskMeasure.VEGA, CorrelationScenario.LOW, risk_class),
                vega_medium=self._empty_result(RiskMeasure.VEGA, CorrelationScenario.MEDIUM, risk_class),
                vega_high=self._empty_result(RiskMeasure.VEGA, CorrelationScenario.HIGH, risk_class),
                curvature_low=self._empty_result(RiskMeasure.CURVATURE, CorrelationScenario.LOW, risk_class),
                curvature_medium=self._empty_result(RiskMeasure.CURVATURE, CorrelationScenario.MEDIUM, risk_class),
                curvature_high=self._empty_result(RiskMeasure.CURVATURE, CorrelationScenario.HIGH, risk_class),
                is_ctp=is_ctp,
            )

        self._validate_sensitivities(sensitivities, risk_class)

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
        """Calculate CSR Sec delta risk charge for one correlation scenario.

        Steps per MAR21.4:

        1. Group sensitivities by bucket (securitization type).
        2. Apply risk weights: ``WS_k = RW_k * s_k``.
        3. Build intra-bucket correlation matrix (tranche x tenor).
        4. Intra-bucket aggregation: ``K_b = sqrt(WS^T * rho * WS)``.
        5. Inter-bucket aggregation with gamma = 0.25 (Non-CTP) or 0.20 (CTP).

        Args:
            sensitivities: CSR Sec delta sensitivities only.
            scenario: LOW / MEDIUM / HIGH.
            is_ctp: Whether CTP parameters should be used.
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
            # Weight every sensitivity ----------------------------------------
            ws_list = [
                self._apply_delta_risk_weight(s, is_ctp)
                for s in bucket_sens
            ]

            # Extract tranche and tenor metadata for correlation matrix -------
            tranches = [s.label or "DEFAULT" for s in bucket_sens]
            tenors = [self._get_tenor_years(s) for s in bucket_sens]

            bucket_int = int(bucket)

            # Build intra-bucket correlation matrix ---------------------------
            corr = build_csr_sec_correlation_matrix(
                bucket=bucket_int,
                tranches=tranches,
                tenors=tenors,
                is_ctp=is_ctp,
                scenario=scenario,
            )

            ws_array = np.array(
                [w.weighted_value for w in ws_list], dtype=np.float64
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
                    weighted_sensitivities=ws_list,
                )
            )

        # Inter-bucket aggregation --------------------------------------------
        gamma = apply_correlation_scenario(
            get_inter_bucket_correlation(is_ctp=is_ctp),
            scenario,
            is_inter_bucket=True,
        )
        total_charge = inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, gamma
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
        """Calculate CSR Sec vega risk charge for one correlation scenario.

        Vega uses (per MAR21.44-47):

        - Risk weight: 100% for CSR Sec.
        - 2-D correlation: option-maturity x underlying-tenor.
        - Same three-scenario framework as delta.

        Args:
            sensitivities: CSR Sec vega sensitivities only.
            scenario: LOW / MEDIUM / HIGH.
            is_ctp: Whether CTP parameters should be used.
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
            get_inter_bucket_correlation(is_ctp=is_ctp),
            scenario,
            is_inter_bucket=True,
        )
        total_charge = inter_bucket_aggregation(
            bucket_charges, bucket_net_sens, gamma
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
        """Calculate CSR Sec curvature risk charge for one correlation scenario.

        Curvature per MAR21.5:

        - ``CVR_k = max(CVR_k_up, CVR_k_down)`` for each risk factor (the
          *sensitivity value* already encodes the net CVR per risk factor).
        - Intra-bucket:
          ``K_b = max(0, sum(CVR) + sum_{k!=l} rho_kl^2 * psi(CVR_k, CVR_l))``
        - Uses **squared** correlations from delta.

        Args:
            sensitivities: CSR Sec curvature sensitivities only.
            scenario: LOW / MEDIUM / HIGH.
            is_ctp: Whether CTP parameters should be used.
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
            # CVR values are the sensitivity values themselves -----------------
            cvr_values = np.array(
                [s.value for s in bucket_sens], dtype=np.float64
            )

            # Build the delta correlation matrix, then square it ---------------
            tranches = [s.label or "DEFAULT" for s in bucket_sens]
            tenors = [self._get_tenor_years(s) for s in bucket_sens]
            bucket_int = int(bucket)

            delta_corr = build_csr_sec_correlation_matrix(
                bucket=bucket_int,
                tranches=tranches,
                tenors=tenors,
                is_ctp=is_ctp,
                scenario=scenario,
            )

            # Squared correlations for curvature per MAR21.5 ------------------
            rho_sq = delta_corr ** 2

            # Intra-bucket curvature aggregation per MAR21.5 ------------------
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
            bucket_charges[bucket] = k_b
            bucket_net_sens[bucket] = sum_cvr

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
                    bucket=bucket,
                    capital_charge=k_b,
                    net_weighted_sensitivity=sum_cvr,
                    weighted_sensitivities=ws_curvature,
                )
            )

        # Inter-bucket curvature aggregation -----------------------------------
        gamma = apply_correlation_scenario(
            get_inter_bucket_correlation(is_ctp=is_ctp),
            scenario,
            is_inter_bucket=True,
        )
        gamma_sq = gamma ** 2

        total_charge = self._curvature_inter_bucket(
            bucket_charges, bucket_net_sens, gamma_sq
        )

        return RiskChargeResult(
            risk_class=risk_class,
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
        """Group sensitivities by bucket (securitization type).

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
    #  Helper: delta risk weights                                            #
    # --------------------------------------------------------------------- #

    def _apply_delta_risk_weight(
        self, sensitivity: Sensitivity, is_ctp: bool
    ) -> WeightedSensitivity:
        """Apply risk weight to a single delta sensitivity.

        Uses bucket-level risk weights from MAR21.14 (Non-CTP) or
        MAR21.15 (CTP). The risk weight is uniform across all tenors
        within a bucket.

        Args:
            sensitivity: A single delta sensitivity.
            is_ctp: Whether to use CTP risk weights.

        Returns:
            :class:`WeightedSensitivity` with ``WS_k = RW_k * s_k``.

        Raises:
            CalculationError: If the bucket is not recognized.
        """
        try:
            bucket_int = int(sensitivity.bucket)
        except (ValueError, TypeError):
            raise CalculationError(
                f"Invalid CSR Sec bucket identifier: '{sensitivity.bucket}'. "
                f"Expected an integer bucket number."
            )

        try:
            if is_ctp:
                rw = get_ctp_risk_weight(bucket_int)
            else:
                rw = get_non_ctp_risk_weight(bucket_int)
        except KeyError:
            valid = "1-5" if is_ctp else "1-8"
            raise CalculationError(
                f"Bucket {bucket_int} is not a valid CSR Sec "
                f"{'CTP' if is_ctp else 'Non-CTP'} bucket. "
                f"Valid buckets: {valid}."
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

        For CSR Securitization, the vega risk weight is 100% per MAR21.44.

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
                und_i = self._get_tenor_years(si)
                und_j = self._get_tenor_years(sj)
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
    #  Helper: tenor extraction                                              #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _get_tenor_years(sensitivity: Sensitivity) -> float:
        """Extract the tenor in years from a sensitivity.

        Falls back to 0.25 if no tenor is specified.

        Args:
            sensitivity: A sensitivity object.

        Returns:
            Tenor in years.
        """
        if sensitivity.tenor is not None:
            return sensitivity.tenor.value
        return 0.25

    # --------------------------------------------------------------------- #
    #  Helper: curvature psi function                                        #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _psi(cvr_k: float, cvr_l: float) -> float:
        """Curvature psi function per MAR21.5(3).

        Returns the product ``|CVR_k| * |CVR_l|`` scaled by a sign factor:

        - Both positive: ``+|CVR_k| * |CVR_l|``
        - Both negative: ``0`` (both negative means no diversification benefit)
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

    @staticmethod
    def _curvature_inter_bucket(
        bucket_charges: dict[str, float],
        bucket_net_cvr: dict[str, float],
        gamma_sq: float,
    ) -> float:
        """Curvature inter-bucket aggregation per MAR21.5(5).

        Formula::

            Total = sqrt(max(0, sum_b K_b^2
                              + sum_{b!=c} gamma_bc^2
                                * Psi(sum_CVR_b, sum_CVR_c)))

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
                cross_sum += gamma_sq * CSRSecCalculator._psi(cvr_b, cvr_c)
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
    def _validate_sensitivities(
        sensitivities: list[Sensitivity],
        risk_class: RiskClass,
    ) -> None:
        """Validate that all sensitivities belong to the correct risk class.

        Args:
            sensitivities: Input sensitivity list.
            risk_class: Expected risk class (CSR_SEC_NON_CTP or CSR_SEC_CTP).

        Raises:
            ValidationError: If the list is empty or contains sensitivities
                with a mismatched risk class.
        """
        if not sensitivities:
            raise ValidationError(
                f"No sensitivities provided for {risk_class.value} calculation."
            )

        invalid = [
            s
            for s in sensitivities
            if s.risk_class != risk_class
        ]
        if invalid:
            bad_classes = {s.risk_class.value for s in invalid}
            raise ValidationError(
                f"All sensitivities must belong to RiskClass.{risk_class.value}. "
                f"Found: {bad_classes}"
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
