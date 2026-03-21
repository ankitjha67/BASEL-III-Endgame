"""PD Models — Through-the-cycle, point-in-time PD estimation and term structures.

Implements the core probability of default models for the ECL engine:
- TTC PD calibration from internal rating scales
- PIT PD adjustment using macroeconomic regime scalars
- PD term structure construction for lifetime ECL
- Rating migration matrices for multi-period projections

All PDs are expressed as annualized decimals (e.g., 0.01 = 1%).

References:
    - BCBS d350 §4.1-4.3: PD estimation requirements for ECL
    - ASC 326-20-30-2: CECL reasonable and supportable forecasts
    - IFRS 9 §B5.5.4-B5.5.6: PD estimation methodology
    - SR 11-7: Model risk management
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from src.ecl.pd_models.pd_params import (
    ASSET_CORRELATION_PARAMS,
    MASTER_SCALE_PD,
    MIGRATION_MATRIX_HY,
    MIGRATION_MATRIX_IG,
    PD_CAP,
    PD_FLOOR,
    RATING_TO_PD,
    TTC_TO_PIT_SCALARS,
)


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class PDModelResult:
    """Result of a PD model calculation.

    Contains TTC PD, PIT PD, term structure, and model metadata.

    Reference: BCBS d350 §4.1, SR 11-7 §IV.
    """
    rating: str
    ttc_pd: float
    pit_pd: float
    sector: str = "corporate"
    regime: str = "normal"
    pd_term_structure: list[float] = field(default_factory=list)
    cumulative_pd: list[float] = field(default_factory=list)
    marginal_pd: list[float] = field(default_factory=list)
    horizon_years: int = 1
    model_version: str = "1.0"


@dataclass
class PDTermStructure:
    """Multi-period PD term structure for lifetime ECL calculation.

    Contains annual marginal and cumulative PDs out to the exposure maturity.
    Used for Stage 2 (lifetime ECL) calculation under IFRS 9 / CECL.

    Reference: IFRS 9 §B5.5.4, ASC 326-20-30-3.
    """
    annual_marginal_pds: list[float]
    annual_cumulative_pds: list[float]
    annual_survival_probs: list[float]
    horizon_years: int
    base_pd: float
    is_pit: bool = False

    @property
    def lifetime_pd(self) -> float:
        """Cumulative PD over the full horizon.

        Reference: IFRS 9 §B5.5.5.
        """
        if self.annual_cumulative_pds:
            return self.annual_cumulative_pds[-1]
        return 0.0

    @property
    def twelve_month_pd(self) -> float:
        """12-month PD for Stage 1 ECL.

        Reference: IFRS 9 §5.5.5.
        """
        if self.annual_marginal_pds:
            return self.annual_marginal_pds[0]
        return self.base_pd


class MigrationMatrix:
    """Rating migration matrix for multi-period PD projection.

    Implements the cohort-based migration approach where a rating
    transition matrix is raised to the power T to project T-year
    cumulative PDs from the default column.

    Reference: BCBS d350 §4.2.3, Moody's Annual Default Study methodology.
    """

    def __init__(self, matrix: np.ndarray, rating_labels: list[str]) -> None:
        """Initialize migration matrix.

        Args:
            matrix: N x N transition probability matrix where rows sum to 1.
                    Last column/row represents default state (absorbing).
            rating_labels: Labels for each rating grade (rows/columns).

        Reference: BCBS d350 §4.2.3.
        """
        self.matrix = matrix
        self.rating_labels = rating_labels
        self._validate()

    def _validate(self) -> None:
        """Validate matrix properties per BCBS d350 §4.2.3."""
        n = self.matrix.shape[0]
        assert self.matrix.shape == (n, n), "Matrix must be square"
        assert len(self.rating_labels) == n, "Labels must match matrix size"
        row_sums = self.matrix.sum(axis=1)
        np.testing.assert_allclose(
            row_sums, 1.0, atol=1e-6,
            err_msg="Each row must sum to 1.0"
        )

    def project_pd(self, rating: str, horizon_years: int) -> list[float]:
        """Project cumulative PDs over a multi-year horizon.

        Uses matrix exponentiation: P(T) = M^T, then reads the default
        column for the given starting rating.

        Args:
            rating: Starting rating grade.
            horizon_years: Projection horizon in years.

        Returns:
            List of cumulative PDs for years 1 through horizon_years.

        Reference: BCBS d350 §4.2.3.
        """
        if rating not in self.rating_labels:
            raise ValueError(f"Rating '{rating}' not in migration matrix")

        idx = self.rating_labels.index(rating)
        default_idx = len(self.rating_labels) - 1  # Last = default

        cumulative_pds: list[float] = []
        powered = np.eye(self.matrix.shape[0])

        for _ in range(horizon_years):
            powered = powered @ self.matrix
            cumulative_pds.append(float(powered[idx, default_idx]))

        return cumulative_pds

    def get_marginal_pds(self, rating: str, horizon_years: int) -> list[float]:
        """Compute marginal (conditional) PDs from cumulative PDs.

        Marginal PD(t) = [Cum_PD(t) - Cum_PD(t-1)] / [1 - Cum_PD(t-1)]

        Args:
            rating: Starting rating grade.
            horizon_years: Projection horizon.

        Returns:
            List of marginal PDs for each year.

        Reference: IFRS 9 §B5.5.4.
        """
        cum_pds = self.project_pd(rating, horizon_years)
        marginals: list[float] = []
        prev_cum = 0.0

        for cum in cum_pds:
            if prev_cum < 1.0:
                marginal = (cum - prev_cum) / (1.0 - prev_cum)
            else:
                marginal = 0.0
            marginals.append(min(max(marginal, PD_FLOOR), PD_CAP))
            prev_cum = cum

        return marginals


class TTCCalibrator:
    """Through-the-cycle PD calibrator.

    Calibrates TTC PDs from the master rating scale, applying central
    tendency adjustments to ensure portfolio-level PDs are consistent
    with long-run observed default rates.

    Reference: BCBS d350 §4.1.3, Internal Model Documentation §3.2.
    """

    def __init__(
        self,
        master_scale: Optional[dict[str, float]] = None,
        central_tendency: float = 1.0,
    ) -> None:
        """Initialize TTC calibrator.

        Args:
            master_scale: Rating-to-PD mapping. Defaults to MASTER_SCALE_PD.
            central_tendency: Multiplicative adjustment to long-run PDs.
                             1.0 = no adjustment. Per BCBS d350 §4.1.3.
        """
        self.master_scale = master_scale or MASTER_SCALE_PD
        self.central_tendency = central_tendency

    def get_ttc_pd(self, rating: str) -> float:
        """Look up TTC PD for a given rating.

        Args:
            rating: Internal rating grade (e.g., 'BBB', 'BB+').

        Returns:
            TTC PD as decimal, floored at PD_FLOOR.

        Reference: BCBS d350 §4.1.3.
        """
        base_pd = self.master_scale.get(
            rating, RATING_TO_PD.get(rating, PD_FLOOR)
        )
        adjusted = base_pd * self.central_tendency
        return min(max(adjusted, PD_FLOOR), PD_CAP)

    def calibrate_portfolio(
        self,
        ratings: list[str],
        weights: list[float],
        target_default_rate: float,
    ) -> float:
        """Calibrate central tendency to match portfolio target default rate.

        Adjusts the central tendency scalar so that the weighted-average
        TTC PD matches the observed long-run default rate.

        Args:
            ratings: List of ratings in the portfolio.
            weights: Exposure weights for each rating.
            target_default_rate: Target portfolio default rate (annual).

        Returns:
            Calibrated central tendency scalar.

        Reference: BCBS d350 §4.1.3, SR 11-7 §IV.3.
        """
        total_weight = sum(weights)
        if total_weight <= 0:
            return 1.0

        weighted_pd = sum(
            w * self.master_scale.get(r, PD_FLOOR)
            for r, w in zip(ratings, weights)
        ) / total_weight

        if weighted_pd <= 0:
            return 1.0

        self.central_tendency = target_default_rate / weighted_pd
        return self.central_tendency


class PITPDModel:
    """Point-in-time PD model using macroeconomic regime adjustment.

    Converts TTC PDs to PIT PDs using regime-dependent scalars.
    The macroeconomic regime is determined externally (expansion, normal,
    mild_stress, severe_stress) based on macro indicators.

    Reference: BCBS d350 §4.2, ASC 326-20-30-9.
    """

    def __init__(
        self,
        regime: str = "normal",
        sector_scalars: Optional[dict[str, dict[str, float]]] = None,
    ) -> None:
        """Initialize PIT PD model.

        Args:
            regime: Current macroeconomic regime.
            sector_scalars: Regime-sector scalar mapping.
                           Defaults to TTC_TO_PIT_SCALARS.

        Reference: BCBS d350 §4.2.
        """
        self.regime = regime
        self.sector_scalars = sector_scalars or TTC_TO_PIT_SCALARS

    def compute_pit_pd(
        self,
        ttc_pd: float,
        sector: str = "corporate",
    ) -> float:
        """Convert TTC PD to PIT PD.

        PIT PD = TTC PD × regime_scalar(sector), capped at PD_CAP.

        Args:
            ttc_pd: Through-the-cycle PD (decimal).
            sector: Borrower sector for scalar lookup.

        Returns:
            Point-in-time PD (decimal).

        Reference: BCBS d350 §4.2, Internal Model Doc §3.3.
        """
        regime_map = self.sector_scalars.get(self.regime, {})
        scalar = regime_map.get(sector, 1.0)
        pit_pd = ttc_pd * scalar
        return min(max(pit_pd, PD_FLOOR), PD_CAP)


class PDModel:
    """Main PD model combining TTC calibration, PIT adjustment, and term structures.

    This is the primary interface for PD estimation in the ECL engine.
    It orchestrates TTC lookup, PIT conversion, and multi-year term
    structure construction.

    Reference: BCBS d350 §4.1-4.3, ASC 326-20-30-2.
    """

    def __init__(
        self,
        ttc_calibrator: Optional[TTCCalibrator] = None,
        pit_model: Optional[PITPDModel] = None,
        migration_matrix: Optional[MigrationMatrix] = None,
    ) -> None:
        """Initialize PD model.

        Args:
            ttc_calibrator: TTC PD calibrator. Defaults to standard calibrator.
            pit_model: PIT PD model. Defaults to 'normal' regime.
            migration_matrix: Migration matrix for term structure.

        Reference: SR 11-7 §III: Model development.
        """
        self.ttc_calibrator = ttc_calibrator or TTCCalibrator()
        self.pit_model = pit_model or PITPDModel()
        self.migration_matrix = migration_matrix

    def compute_pd(
        self,
        rating: str,
        sector: str = "corporate",
        horizon_years: int = 1,
        use_pit: bool = True,
    ) -> PDModelResult:
        """Compute PD for a given rating and horizon.

        Args:
            rating: Internal rating grade.
            sector: Borrower sector.
            horizon_years: ECL horizon in years.
            use_pit: If True, apply PIT adjustment.

        Returns:
            PDModelResult with TTC, PIT, and term structure.

        Reference: BCBS d350 §4.1-4.3.
        """
        ttc_pd = self.ttc_calibrator.get_ttc_pd(rating)
        pit_pd = self.pit_model.compute_pit_pd(ttc_pd, sector) if use_pit else ttc_pd

        term_structure = self.build_term_structure(
            pit_pd if use_pit else ttc_pd,
            horizon_years,
            rating,
        )

        return PDModelResult(
            rating=rating,
            ttc_pd=ttc_pd,
            pit_pd=pit_pd,
            sector=sector,
            regime=self.pit_model.regime,
            pd_term_structure=term_structure.annual_marginal_pds,
            cumulative_pd=term_structure.annual_cumulative_pds,
            marginal_pd=term_structure.annual_marginal_pds,
            horizon_years=horizon_years,
        )

    def build_term_structure(
        self,
        base_pd: float,
        horizon_years: int,
        rating: Optional[str] = None,
    ) -> PDTermStructure:
        """Build PD term structure for lifetime ECL.

        If a migration matrix is available and rating is provided, uses
        matrix exponentiation. Otherwise uses flat PD extrapolation with
        slight upward drift for longer horizons.

        Args:
            base_pd: Base annual PD (TTC or PIT).
            horizon_years: Number of years.
            rating: Optional rating for migration-based projection.

        Returns:
            PDTermStructure with marginal and cumulative PDs.

        Reference: IFRS 9 §B5.5.4, ASC 326-20-30-3.
        """
        if self.migration_matrix is not None and rating is not None:
            try:
                cum_pds = self.migration_matrix.project_pd(rating, horizon_years)
                marginals = self.migration_matrix.get_marginal_pds(
                    rating, horizon_years
                )
                survivals = [1.0 - cp for cp in cum_pds]
                return PDTermStructure(
                    annual_marginal_pds=marginals,
                    annual_cumulative_pds=cum_pds,
                    annual_survival_probs=survivals,
                    horizon_years=horizon_years,
                    base_pd=base_pd,
                    is_pit=True,
                )
            except (ValueError, KeyError):
                pass

        # Flat extrapolation with mild upward drift
        marginals: list[float] = []
        cum_pds: list[float] = []
        survivals: list[float] = []
        survival = 1.0

        for year in range(1, horizon_years + 1):
            # Slight upward drift: PD increases ~2% per year for longer horizons
            # per empirical term structure observations
            drift = 1.0 + 0.02 * (year - 1)
            annual_pd = min(base_pd * drift, PD_CAP)
            marginals.append(annual_pd)
            survival *= (1.0 - annual_pd)
            cum_pds.append(1.0 - survival)
            survivals.append(survival)

        return PDTermStructure(
            annual_marginal_pds=marginals,
            annual_cumulative_pds=cum_pds,
            annual_survival_probs=survivals,
            horizon_years=horizon_years,
            base_pd=base_pd,
        )
