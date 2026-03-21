"""ECL Calculator — Expected Credit Loss computation engine.

Implements the full ECL calculation pipeline combining PD, LGD, EAD,
and staging models. Supports both CECL (ASC 326) and IFRS 9 frameworks
with probability-weighted multi-scenario ECL.

ECL = PD × LGD × EAD × DF (discounted)
- Stage 1: 12-month ECL (marginal PD for year 1 only)
- Stage 2: Lifetime ECL (sum of annual ECL over remaining life)
- Stage 3: Lifetime ECL (PD = 1.0, LGD reflects recovery expectations)

All amounts in USD millions ($M).

References:
    - ASC 326-20-30: CECL measurement
    - IFRS 9 §5.5.1-5.5.20: Impairment measurement
    - BCBS d350: Guidance on credit risk and accounting for ECL
    - SR 11-7: Model risk management
    - Federal Reserve SR 20-15: Interagency Policy Statement on Allowances
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.ecl.pd_models.pd_models import PDModel, PDModelResult, PDTermStructure
from src.ecl.lgd_models.lgd_models import LGDModel, LGDResult
from src.ecl.ead_models.ead_models import EADModel, EADResult
from src.ecl.staging.staging_engine import StagingEngine, Stage, StageAssignment


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class MacroeconomicScenario:
    """A macroeconomic scenario for probability-weighted ECL.

    Per ASC 326-20-30-9, CECL requires consideration of reasonable
    and supportable forecasts. Multiple scenarios may be used with
    probability weights.

    Reference: ASC 326-20-30-9, IFRS 9 §5.5.17-5.5.18.
    """
    name: str
    regime: str  # "expansion", "normal", "mild_stress", "severe_stress"
    description: str = ""


@dataclass
class ScenarioWeight:
    """Probability weight for a macroeconomic scenario.

    Weights must sum to 1.0 across all scenarios.

    Reference: IFRS 9 §5.5.17, ASC 326-20-30-9.
    """
    scenario: MacroeconomicScenario
    weight: float


@dataclass
class ECLExposure:
    """Input exposure for ECL calculation.

    Contains all attributes needed to compute stage allocation
    and ECL amount for a single credit exposure.

    Reference: BCBS d350 §2.1.
    """
    exposure_id: str
    rating: str
    sector: str = "corporate"
    seniority: str = "senior_unsecured"
    drawn_amount: float = 0.0
    undrawn_amount: float = 0.0
    collateral_value: float = 0.0
    collateral_type: Optional[str] = None
    remaining_maturity_years: float = 1.0
    pd_at_origination: float = 0.01
    pd_current: Optional[float] = None
    days_past_due: int = 0
    is_defaulted: bool = False
    is_on_watchlist: bool = False
    has_forbearance: bool = False
    rating_at_origination: str = ""
    discount_rate: float = 0.05
    product_type: str = "commitments_gte_1y"


@dataclass
class ECLResult:
    """ECL calculation result for a single exposure.

    Reference: IFRS 9 §5.5.1, ASC 326-20-30.
    """
    exposure_id: str
    stage: Stage
    ecl_12_month: float
    ecl_lifetime: float
    ecl_final: float  # 12-month if Stage 1, lifetime otherwise
    pd_result: PDModelResult
    lgd_result: LGDResult
    ead_result: EADResult
    stage_assignment: StageAssignment
    ead: float
    effective_pd: float
    effective_lgd: float
    discount_factor: float = 1.0
    scenario_ecl: dict[str, float] = field(default_factory=dict)


@dataclass
class ECLPortfolioResult:
    """Portfolio-level ECL aggregation.

    Reference: ASC 326-20-30, IFRS 9 §5.5.1.
    """
    total_ecl: float = 0.0
    total_ead: float = 0.0
    total_ecl_stage1: float = 0.0
    total_ecl_stage2: float = 0.0
    total_ecl_stage3: float = 0.0
    count_stage1: int = 0
    count_stage2: int = 0
    count_stage3: int = 0
    ead_stage1: float = 0.0
    ead_stage2: float = 0.0
    ead_stage3: float = 0.0
    weighted_avg_pd: float = 0.0
    weighted_avg_lgd: float = 0.0
    coverage_ratio: float = 0.0  # ECL / Total EAD
    exposure_results: list[ECLResult] = field(default_factory=list)


# =========================================================================
#  ECL Calculator
# =========================================================================

class ECLCalculator:
    """Main ECL calculation engine.

    Orchestrates PD, LGD, EAD, and staging models to compute
    expected credit losses with probability-weighted scenarios.

    Reference: BCBS d350, ASC 326-20-30, IFRS 9 §5.5.1-5.5.20.
    """

    def __init__(
        self,
        pd_model: Optional[PDModel] = None,
        lgd_model: Optional[LGDModel] = None,
        ead_model: Optional[EADModel] = None,
        staging_engine: Optional[StagingEngine] = None,
        scenarios: Optional[list[ScenarioWeight]] = None,
    ) -> None:
        """Initialize ECL calculator with component models.

        Args:
            pd_model: PD estimation model.
            lgd_model: LGD estimation model.
            ead_model: EAD estimation model.
            staging_engine: IFRS 9 staging engine.
            scenarios: Probability-weighted macro scenarios.

        Reference: SR 11-7 §III.
        """
        self.pd_model = pd_model or PDModel()
        self.lgd_model = lgd_model or LGDModel()
        self.ead_model = ead_model or EADModel()
        self.staging_engine = staging_engine or StagingEngine()
        self.scenarios = scenarios or [
            ScenarioWeight(
                scenario=MacroeconomicScenario(
                    name="Base", regime="normal",
                    description="Central/baseline scenario"
                ),
                weight=1.0,
            ),
        ]

    def compute_ecl(self, exposure: ECLExposure) -> ECLResult:
        """Compute ECL for a single exposure.

        Pipeline:
        1. Compute EAD (drawn + CCF × undrawn)
        2. Assign IFRS 9 stage
        3. Compute PD (TTC → PIT, term structure)
        4. Compute LGD (with downturn and cure adjustments)
        5. Compute 12-month and lifetime ECL
        6. Apply probability-weighted scenarios
        7. Select final ECL based on stage

        Args:
            exposure: Input exposure with all attributes.

        Returns:
            ECLResult with full breakdown.

        Reference: BCBS d350 §2, ASC 326-20-30.
        """
        # Step 1: EAD
        ead_result = self.ead_model.compute_ead(
            drawn=exposure.drawn_amount,
            undrawn=exposure.undrawn_amount,
            product_type=exposure.product_type,
        )
        ead = ead_result.total_ead

        # Step 2: Stage assignment
        pd_current = exposure.pd_current
        if pd_current is None:
            pd_result_temp = self.pd_model.compute_pd(
                exposure.rating, exposure.sector
            )
            pd_current = pd_result_temp.pit_pd

        stage_assignment = self.staging_engine.assign_stage(
            pd_at_origination=exposure.pd_at_origination,
            pd_current=pd_current,
            days_past_due=exposure.days_past_due,
            is_defaulted=exposure.is_defaulted,
            rating_at_origination=exposure.rating_at_origination or exposure.rating,
            rating_current=exposure.rating,
            is_on_watchlist=exposure.is_on_watchlist,
            has_forbearance=exposure.has_forbearance,
        )

        # Step 3: PD with term structure
        horizon = max(1, int(exposure.remaining_maturity_years))
        pd_result = self.pd_model.compute_pd(
            rating=exposure.rating,
            sector=exposure.sector,
            horizon_years=horizon,
            use_pit=True,
        )

        # Step 4: LGD
        lgd_result = self.lgd_model.compute_lgd(
            asset_class=exposure.sector,
            seniority=exposure.seniority,
            collateral_value=exposure.collateral_value,
            collateral_type=exposure.collateral_type,
            ead=ead,
            use_downturn=True,
            apply_cure=True,
        )

        # Step 5: ECL computation
        effective_pd = pd_result.pit_pd
        effective_lgd = lgd_result.effective_lgd

        # 12-month ECL
        ecl_12m = ead * effective_pd * effective_lgd

        # Lifetime ECL (sum of discounted annual ECL)
        ecl_lifetime = self._compute_lifetime_ecl(
            ead=ead,
            pd_term_structure=pd_result.marginal_pd,
            lgd=effective_lgd,
            discount_rate=exposure.discount_rate,
            horizon=horizon,
        )

        # Stage 3: PD = 1.0
        if stage_assignment.stage == Stage.STAGE_3:
            ecl_12m = ead * effective_lgd
            ecl_lifetime = ead * effective_lgd

        # Step 6: Scenario-weighted ECL
        scenario_ecl: dict[str, float] = {}
        if len(self.scenarios) > 1:
            weighted_ecl_12m = 0.0
            weighted_ecl_lt = 0.0
            for sw in self.scenarios:
                # Compute PD under each scenario regime
                self.pd_model.pit_model.regime = sw.scenario.regime
                pd_s = self.pd_model.compute_pd(
                    exposure.rating, exposure.sector, horizon, True
                )
                s_12m = ead * pd_s.pit_pd * effective_lgd
                s_lt = self._compute_lifetime_ecl(
                    ead, pd_s.marginal_pd, effective_lgd,
                    exposure.discount_rate, horizon,
                )
                scenario_ecl[sw.scenario.name] = s_lt
                weighted_ecl_12m += sw.weight * s_12m
                weighted_ecl_lt += sw.weight * s_lt
            # Restore default regime
            self.pd_model.pit_model.regime = "normal"
            ecl_12m = weighted_ecl_12m
            ecl_lifetime = weighted_ecl_lt

        # Step 7: Final ECL based on stage
        if stage_assignment.stage == Stage.STAGE_1:
            ecl_final = ecl_12m
        else:
            ecl_final = ecl_lifetime

        # Discount factor
        avg_life = min(exposure.remaining_maturity_years, horizon) / 2.0
        discount_factor = 1.0 / (1.0 + exposure.discount_rate) ** avg_life

        return ECLResult(
            exposure_id=exposure.exposure_id,
            stage=stage_assignment.stage,
            ecl_12_month=ecl_12m,
            ecl_lifetime=ecl_lifetime,
            ecl_final=ecl_final * discount_factor,
            pd_result=pd_result,
            lgd_result=lgd_result,
            ead_result=ead_result,
            stage_assignment=stage_assignment,
            ead=ead,
            effective_pd=effective_pd,
            effective_lgd=effective_lgd,
            discount_factor=discount_factor,
            scenario_ecl=scenario_ecl,
        )

    def compute_portfolio_ecl(
        self,
        exposures: list[ECLExposure],
    ) -> ECLPortfolioResult:
        """Compute ECL for a portfolio of exposures.

        Args:
            exposures: List of credit exposures.

        Returns:
            ECLPortfolioResult with aggregated ECL and per-exposure results.

        Reference: ASC 326-20-30, IFRS 9 §5.5.1.
        """
        results: list[ECLResult] = []
        total_ecl = 0.0
        total_ead = 0.0
        ecl_by_stage = {Stage.STAGE_1: 0.0, Stage.STAGE_2: 0.0, Stage.STAGE_3: 0.0}
        ead_by_stage = {Stage.STAGE_1: 0.0, Stage.STAGE_2: 0.0, Stage.STAGE_3: 0.0}
        count_by_stage = {Stage.STAGE_1: 0, Stage.STAGE_2: 0, Stage.STAGE_3: 0}
        weighted_pd_sum = 0.0
        weighted_lgd_sum = 0.0

        for exp in exposures:
            result = self.compute_ecl(exp)
            results.append(result)
            total_ecl += result.ecl_final
            total_ead += result.ead
            ecl_by_stage[result.stage] += result.ecl_final
            ead_by_stage[result.stage] += result.ead
            count_by_stage[result.stage] += 1
            weighted_pd_sum += result.effective_pd * result.ead
            weighted_lgd_sum += result.effective_lgd * result.ead

        weighted_avg_pd = weighted_pd_sum / total_ead if total_ead > 0 else 0.0
        weighted_avg_lgd = weighted_lgd_sum / total_ead if total_ead > 0 else 0.0
        coverage_ratio = total_ecl / total_ead if total_ead > 0 else 0.0

        return ECLPortfolioResult(
            total_ecl=total_ecl,
            total_ead=total_ead,
            total_ecl_stage1=ecl_by_stage[Stage.STAGE_1],
            total_ecl_stage2=ecl_by_stage[Stage.STAGE_2],
            total_ecl_stage3=ecl_by_stage[Stage.STAGE_3],
            count_stage1=count_by_stage[Stage.STAGE_1],
            count_stage2=count_by_stage[Stage.STAGE_2],
            count_stage3=count_by_stage[Stage.STAGE_3],
            ead_stage1=ead_by_stage[Stage.STAGE_1],
            ead_stage2=ead_by_stage[Stage.STAGE_2],
            ead_stage3=ead_by_stage[Stage.STAGE_3],
            weighted_avg_pd=weighted_avg_pd,
            weighted_avg_lgd=weighted_avg_lgd,
            coverage_ratio=coverage_ratio,
            exposure_results=results,
        )

    def _compute_lifetime_ecl(
        self,
        ead: float,
        marginal_pds: list[float],
        lgd: float,
        discount_rate: float,
        horizon: int,
    ) -> float:
        """Compute lifetime ECL as sum of discounted annual ECL.

        Lifetime ECL = Σ (marginal_PD_t × LGD × EAD × DF_t)
        where DF_t = 1 / (1 + r)^t

        Args:
            ead: Exposure at default ($M).
            marginal_pds: Annual marginal PDs.
            lgd: Effective LGD.
            discount_rate: Discount rate.
            horizon: Number of years.

        Returns:
            Lifetime ECL in $M.

        Reference: IFRS 9 §B5.5.28-B5.5.29.
        """
        lifetime_ecl = 0.0
        for t in range(min(horizon, len(marginal_pds))):
            df = 1.0 / (1.0 + discount_rate) ** (t + 1)
            annual_ecl = marginal_pds[t] * lgd * ead * df
            lifetime_ecl += annual_ecl
        return lifetime_ecl
