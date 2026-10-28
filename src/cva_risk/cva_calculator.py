"""CVA risk calculator — entry point for ERBA NPR §__.220–§__.225.

Orchestrates the basic measure (BA-CVA, §__.222) and the standardized
measure (SA-CVA, §__.224–§__.225, plus BA-CVA for carved-out netting
sets), determines scope and approach eligibility, converts the capital
requirement to RWA (12.5 ×, §__.221) and produces reporting breakdowns.

Scope (§__.201(b)(2), §__.202):
    - The CVA risk capital requirement applies to a Category I or II
      depository institution holding company, to a subsidiary depository
      institution of such an organization that is subject to market risk
      capital requirements, and to any banking organization subject to
      market risk capital requirements whose average aggregate OTC
      derivative gross notional over the prior four quarters is ≥ $1
      trillion (CPI-W indexed).
    - A CVA risk covered position is a derivative contract that is not a
      cleared transaction and not a client-facing derivative transaction.
      SFTs are not covered positions. An eligible credit derivative for
      which the banking organization recognizes credit risk mitigation may
      be excluded.

Approach (§__.221): the basic measure (BA-CVA) is the default; the
standardized measure requires prior written supervisory approval, SA-CCR
for counterparty credit risk, a CVA desk or similar function and the
ability to compute regulatory CVA and its sensitivities at least monthly.

All monetary amounts in USD millions ($M).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, field_validator

from src.cva_risk.ba_cva import (
    BACVACalculator,
    BACVACounterparty,
    BACVAHedge,
    BACVAIndexConstituent,
    BACVANettingSet,
    BACVAResult,
)
from src.cva_risk.cva_params import (
    CVA_SCOPE_AVERAGING_QUARTERS,
    CVA_SCOPE_OTC_NOTIONAL_THRESHOLD,
    RWA_MULTIPLIER,
    BACVAHedgeRelationship,
    CVAApproach,
    CVACreditQuality,
    CVAHedgeType,
    CVASector,
    credit_quality_from_grade,
    normalize_sector,
)
from src.cva_risk.sa_cva import SACVACalculator, SACVAResult, SACVASensitivity

logger = logging.getLogger(__name__)


# =========================================================================
#  Scope
# =========================================================================

class CVAScopeDetermination(BaseModel):
    """Whether the CVA risk capital requirement applies (ERBA NPR §__.201(b)(2))."""
    in_scope: bool
    reason: str
    average_otc_gross_notional: float = Field(
        default=0.0, description="Four-quarter average OTC gross notional in $M"
    )


def determine_cva_scope(
    is_category_i_or_ii_holding_company: bool = False,
    is_subsidiary_di_of_category_i_or_ii: bool = False,
    subject_to_market_risk_rule: bool = False,
    quarterly_otc_gross_notional: list[float] | None = None,
    supervisory_override: bool | None = None,
) -> CVAScopeDetermination:
    """Determine whether CVA risk capital requirements apply per ERBA NPR §__.201(b)(2).

    Args:
        is_category_i_or_ii_holding_company: Category I or II depository
            institution holding company.
        is_subsidiary_di_of_category_i_or_ii: Subsidiary depository
            institution of a Category I or II banking organization (in
            scope only if also subject to market risk capital requirements).
        subject_to_market_risk_rule: Subject to the market risk capital
            requirements (subpart F).
        quarterly_otc_gross_notional: Aggregate OTC derivative gross notional
            ($M) for the prior four quarters; the average is compared with
            the $1 trillion threshold.
        supervisory_override: The primary Federal supervisor may require or
            exclude application (reservation of authority); True forces in
            scope, False forces out of scope.

    Returns:
        CVAScopeDetermination.
    """
    avg = 0.0
    if quarterly_otc_gross_notional:
        recent = quarterly_otc_gross_notional[-CVA_SCOPE_AVERAGING_QUARTERS:]
        avg = sum(recent) / len(recent)

    if supervisory_override is not None:
        return CVAScopeDetermination(
            in_scope=supervisory_override,
            reason="Supervisory reservation of authority (§__.201(b)(2))",
            average_otc_gross_notional=avg,
        )
    if is_category_i_or_ii_holding_company:
        return CVAScopeDetermination(
            in_scope=True,
            reason="Category I or II depository institution holding company",
            average_otc_gross_notional=avg,
        )
    if is_subsidiary_di_of_category_i_or_ii and subject_to_market_risk_rule:
        return CVAScopeDetermination(
            in_scope=True,
            reason="Market-risk subsidiary DI of a Category I or II banking organization",
            average_otc_gross_notional=avg,
        )
    if subject_to_market_risk_rule and avg >= CVA_SCOPE_OTC_NOTIONAL_THRESHOLD:
        return CVAScopeDetermination(
            in_scope=True,
            reason="Market-risk banking organization with four-quarter average OTC "
                   "gross notional at or above $1 trillion",
            average_otc_gross_notional=avg,
        )
    return CVAScopeDetermination(
        in_scope=False,
        reason="Not a Category I/II HC, market-risk Category I/II DI subsidiary, "
               "or market-risk bank at or above the $1 trillion OTC notional threshold",
        average_otc_gross_notional=avg,
    )


def is_cva_risk_covered_position(
    is_derivative: bool,
    is_cleared_transaction: bool = False,
    is_client_facing_derivative: bool = False,
    is_sft: bool = False,
    is_crm_recognized_credit_derivative: bool = False,
    exclude_crm_credit_derivatives: bool = True,
) -> bool:
    """CVA risk covered position test per ERBA NPR §__.202.

    A CVA risk covered position is a derivative contract that is not a
    cleared transaction or a client-facing derivative transaction. SFTs
    are not covered positions. An eligible credit derivative recognized as
    a credit risk mitigant may, at the banking organization's election, be
    excluded.

    Args:
        is_derivative: Position is a derivative contract.
        is_cleared_transaction: Cleared transaction (excluded).
        is_client_facing_derivative: Client-facing derivative transaction
            of a clearing member (excluded).
        is_sft: Securities financing transaction (excluded).
        is_crm_recognized_credit_derivative: Eligible credit derivative for
            which CRM benefit is recognized under §__.120.
        exclude_crm_credit_derivatives: Election to exclude such credit
            derivatives.

    Returns:
        True if the position is a CVA risk covered position.
    """
    if not is_derivative or is_sft:
        return False
    if is_cleared_transaction or is_client_facing_derivative:
        return False
    if is_crm_recognized_credit_derivative and exclude_crm_credit_derivatives:
        return False
    return True


# =========================================================================
#  Unified input models
# =========================================================================

class CVACounterparty(BaseModel):
    """Unified counterparty model (converted to ``BACVACounterparty``).

    Per ERBA NPR §__.222(b): sector and bank-internal credit quality
    (Table 1 to §__.222), commercial end-user status (alpha), and netting
    sets with EAD_NS and M_NS.
    """
    counterparty_id: str = Field(description="Unique counterparty identifier")
    name: str = Field(default="", description="Counterparty name")
    sector: CVASector = Field(default=CVASector.OTHER_SECTOR)
    credit_quality: CVACreditQuality | None = Field(default=None)
    rating: str | None = Field(
        default=None, description="Convenience internal grade label (e.g. 'BBB')"
    )
    is_commercial_end_user: bool = Field(default=False)
    region: str = Field(default="")
    netting_sets: list[BACVANettingSet] = Field(default_factory=list)
    ead: float | None = Field(default=None, description="Shorthand single-netting-set EAD in $M")
    effective_maturity: float | None = Field(default=None, description="Shorthand M in years")

    @field_validator("sector", mode="before")
    @classmethod
    def _coerce_sector(cls, v: object) -> CVASector:
        return v if isinstance(v, CVASector) else normalize_sector(str(v))

    @field_validator("credit_quality", mode="before")
    @classmethod
    def _coerce_quality(cls, v: object) -> CVACreditQuality | None:
        if v is None or isinstance(v, CVACreditQuality):
            return v
        return credit_quality_from_grade(str(v))

    def to_ba_cva(self) -> BACVACounterparty:
        """Convert to the BA-CVA counterparty model (ERBA NPR §__.222(b))."""
        return BACVACounterparty(
            counterparty_id=self.counterparty_id,
            sector=self.sector,
            credit_quality=self.credit_quality,
            rating=self.rating,
            is_commercial_end_user=self.is_commercial_end_user,
            region=self.region,
            netting_sets=list(self.netting_sets),
            ead=self.ead,
            effective_maturity=self.effective_maturity,
        )

    @property
    def total_ead(self) -> float:
        """Σ_NS EAD_NS in $M."""
        if self.netting_sets:
            return sum(ns.ead for ns in self.netting_sets)
        return self.ead or 0.0


class CVAHedge(BaseModel):
    """Unified BA-CVA hedge model (converted to ``BACVAHedge``).

    Per ERBA NPR §__.222(c): single-name CDS, single-name contingent CDS or
    index CDS, with the Table 2 relationship to the hedged counterparty.
    """
    hedge_id: str
    hedge_type: CVAHedgeType
    notional: float = Field(description="B_h in $M (market value of reference portfolio for contingent CDS)")
    maturity: float = Field(description="M_h in years")
    counterparty_id: str = Field(default="")
    relationship: BACVAHedgeRelationship = Field(default=BACVAHedgeRelationship.DIRECT)
    reference_sector: CVASector | None = Field(default=None)
    reference_credit_quality: CVACreditQuality | None = Field(default=None)
    rating: str | None = Field(default=None)
    constituents: list[BACVAIndexConstituent] = Field(default_factory=list)

    @field_validator("hedge_type", mode="before")
    @classmethod
    def _coerce_type(cls, v: object) -> CVAHedgeType:
        return v if isinstance(v, CVAHedgeType) else CVAHedgeType(str(v))

    @field_validator("relationship", mode="before")
    @classmethod
    def _coerce_relationship(cls, v: object) -> BACVAHedgeRelationship:
        return v if isinstance(v, BACVAHedgeRelationship) else BACVAHedgeRelationship(str(v))

    @field_validator("reference_sector", mode="before")
    @classmethod
    def _coerce_sector(cls, v: object) -> CVASector | None:
        if v is None or isinstance(v, CVASector):
            return v
        return normalize_sector(str(v))

    @field_validator("reference_credit_quality", mode="before")
    @classmethod
    def _coerce_quality(cls, v: object) -> CVACreditQuality | None:
        if v is None or isinstance(v, CVACreditQuality):
            return v
        return credit_quality_from_grade(str(v))

    def to_ba_cva(self) -> BACVAHedge:
        """Convert to the BA-CVA hedge model (ERBA NPR §__.222(c))."""
        return BACVAHedge(
            hedge_id=self.hedge_id,
            hedge_type=self.hedge_type,
            notional=self.notional,
            maturity=self.maturity,
            counterparty_id=self.counterparty_id,
            relationship=self.relationship,
            reference_sector=self.reference_sector,
            reference_credit_quality=self.reference_credit_quality,
            rating=self.rating,
            constituents=list(self.constituents),
        )


# =========================================================================
#  Eligibility
# =========================================================================

class CVAEligibility(BaseModel):
    """Approach eligibility per ERBA NPR §__.221 / §__.223."""
    sa_cva_eligible: bool = Field(default=False)
    ba_cva_full_eligible: bool = Field(
        default=False, description="Eligible hedges exist, so the full BA-CVA applies"
    )
    ba_cva_reduced_eligible: bool = Field(default=True, description="Always available")
    recommended_approach: CVAApproach = Field(default=CVAApproach.BA_CVA_REDUCED)
    reason: str = Field(default="")


def determine_eligibility(
    uses_saccr: bool = True,
    has_cva_desk: bool = False,
    has_cva_sensitivities: bool = False,
    has_eligible_hedges: bool = False,
    supervisory_approval: bool = False,
) -> CVAEligibility:
    """Determine the CVA approach per ERBA NPR §__.221 and §__.223.

    The standardized measure requires (i) SA-CCR for counterparty credit
    risk, (ii) a CVA desk or similar dedicated function, (iii) the ability
    to calculate regulatory CVA and its sensitivities at least monthly and
    (iv) prior written approval of the primary Federal supervisor.
    Otherwise the basic measure applies: the full BA-CVA when eligible
    hedges are recognized, the reduced BA-CVA when they are not.

    Args:
        uses_saccr: Uses SA-CCR for counterparty credit risk exposure.
        has_cva_desk: Has a CVA desk or similar dedicated function.
        has_cva_sensitivities: Can compute regulatory CVA sensitivities monthly.
        has_eligible_hedges: Holds eligible BA-CVA hedges.
        supervisory_approval: Written approval for the standardized measure.

    Returns:
        CVAEligibility with the recommended approach.
    """
    sa_eligible = uses_saccr and has_cva_desk and has_cva_sensitivities and supervisory_approval
    if sa_eligible:
        return CVAEligibility(
            sa_cva_eligible=True,
            ba_cva_full_eligible=has_eligible_hedges,
            recommended_approach=CVAApproach.SA_CVA,
            reason="Standardized measure: SA-CCR, CVA function, monthly sensitivities "
                   "and supervisory approval (§__.223)",
        )
    if has_eligible_hedges:
        return CVAEligibility(
            ba_cva_full_eligible=True,
            recommended_approach=CVAApproach.BA_CVA_FULL,
            reason="Basic measure with eligible hedges recognized (§__.222(c))",
        )
    return CVAEligibility(
        recommended_approach=CVAApproach.BA_CVA_REDUCED,
        reason="Basic measure without eligible hedges: K_basic = 0.65·K_unhedged (§__.222)",
    )


# =========================================================================
#  Unified result
# =========================================================================

class CVACapitalResult(BaseModel):
    """CVA capital requirement and RWA per ERBA NPR §__.221."""
    approach: CVAApproach
    k_cva: float = Field(description="Total CVA capital requirement in $M")
    rwa: float = Field(description="RWA_CVA = 12.5 · K_CVA in $M")
    k_sa_cva: float = Field(default=0.0, description="SA-CVA component in $M")
    k_ba_cva: float = Field(default=0.0, description="BA-CVA component (K_basic) in $M")
    k_unhedged: float = Field(default=0.0, description="BA-CVA K_unhedged in $M")
    k_hedged: float = Field(default=0.0, description="BA-CVA K_hedged in $M")
    counterparty_rwa: dict[str, float] = Field(
        default_factory=dict, description="BA-CVA RWA allocated by SCVA_c share, $M"
    )
    sector_rwa: dict[str, float] = Field(default_factory=dict)
    risk_class_rwa: dict[str, float] = Field(
        default_factory=dict, description="SA-CVA RWA by risk class / delta-vega, $M"
    )
    total_ead: float = Field(default=0.0)
    counterparty_count: int = Field(default=0)
    hedge_count: int = Field(default=0)
    hedge_benefit_pct: float = Field(
        default=0.0, description="BA-CVA: (0.65·K_unhedged − K_basic) / (0.65·K_unhedged) × 100"
    )
    eligibility: CVAEligibility | None = Field(default=None)
    ba_cva_result: BACVAResult | None = Field(default=None)
    sa_cva_result: SACVAResult | None = Field(default=None)


# =========================================================================
#  Calculator
# =========================================================================

class CVACalculator:
    """Main CVA risk calculator (ERBA NPR §__.220–§__.225).

    Usage::

        calc = CVACalculator()
        # Basic measure (default)
        result = calc.calculate(counterparties, hedges)
        # Standardized measure: SA-CVA on sensitivities, BA-CVA on carve-outs
        result = calc.calculate(
            counterparties=carved_out_counterparties,
            sensitivities=sa_cva_sensitivities,
            approach=CVAApproach.SA_CVA,
        )
    """

    def __init__(self, m_cva: float = 1.0) -> None:
        """Initialize engines; ``m_cva`` is the SA-CVA multiplier (§__.225(a))."""
        self.ba_cva_calculator = BACVACalculator()
        self.sa_cva_calculator = SACVACalculator(m_cva=m_cva)

    def calculate(
        self,
        counterparties: list[CVACounterparty] | None = None,
        hedges: list[CVAHedge] | None = None,
        sensitivities: list[SACVASensitivity] | None = None,
        approach: CVAApproach | None = None,
        uses_saccr: bool = True,
        has_cva_desk: bool = False,
        has_cva_sensitivities: bool = False,
        supervisory_approval: bool = False,
    ) -> CVACapitalResult:
        """Compute the CVA capital requirement and RWA.

        Under the basic measure all ``counterparties`` (and ``hedges``) are
        processed with the BA-CVA. Under the standardized measure the
        ``sensitivities`` are processed with the SA-CVA and any
        ``counterparties`` passed are treated as carved-out netting sets
        processed with the BA-CVA; the two capital requirements are summed
        (§__.221, §__.223).

        Args:
            counterparties: BA-CVA counterparties (all, or carve-outs under SA-CVA).
            hedges: Eligible BA-CVA hedges.
            sensitivities: SA-CVA sensitivities (required for SA_CVA).
            approach: Force an approach; otherwise selected by eligibility.
            uses_saccr: SA-CCR used for counterparty credit risk.
            has_cva_desk: CVA desk or similar function exists.
            has_cva_sensitivities: Monthly regulatory CVA sensitivities available.
            supervisory_approval: Written approval for the standardized measure.

        Returns:
            CVACapitalResult.

        Raises:
            ValueError: If SA_CVA is selected without sensitivities.
        """
        counterparties = counterparties or []
        hedges = hedges or []
        sensitivities = sensitivities or []

        eligibility = determine_eligibility(
            uses_saccr=uses_saccr,
            has_cva_desk=has_cva_desk,
            has_cva_sensitivities=has_cva_sensitivities,
            has_eligible_hedges=bool(hedges),
            supervisory_approval=supervisory_approval,
        )
        selected = approach or eligibility.recommended_approach
        if selected is CVAApproach.BA_CVA_FULL and not hedges:
            selected = CVAApproach.BA_CVA_REDUCED
        if selected is CVAApproach.BA_CVA_REDUCED and hedges:
            selected = CVAApproach.BA_CVA_FULL

        logger.info(
            "CVA calculation: approach=%s counterparties=%d hedges=%d sensitivities=%d",
            selected.value, len(counterparties), len(hedges), len(sensitivities),
        )

        if selected is CVAApproach.SA_CVA:
            if not sensitivities:
                raise ValueError(
                    "SA-CVA requires regulatory CVA sensitivities (ERBA NPR §__.224)"
                )
            return self._run_standardized_measure(
                counterparties, hedges, sensitivities, eligibility,
            )
        return self._run_basic_measure(counterparties, hedges, eligibility)

    # ---- basic measure ----------------------------------------------------

    def _run_basic_measure(
        self,
        counterparties: list[CVACounterparty],
        hedges: list[CVAHedge],
        eligibility: CVAEligibility,
    ) -> CVACapitalResult:
        """BA-CVA per ERBA NPR §__.222 with reporting breakdown."""
        ba_result = self.ba_cva_calculator.calculate(
            [cp.to_ba_cva() for cp in counterparties],
            [h.to_ba_cva() for h in hedges],
        )
        cp_rwa, sector_rwa = self._allocate_ba_cva_rwa(ba_result)
        return CVACapitalResult(
            approach=ba_result.approach,
            k_cva=ba_result.k_basic,
            rwa=ba_result.rwa,
            k_ba_cva=ba_result.k_basic,
            k_unhedged=ba_result.k_unhedged,
            k_hedged=ba_result.k_hedged,
            counterparty_rwa=cp_rwa,
            sector_rwa=sector_rwa,
            total_ead=sum(cp.total_ead for cp in counterparties),
            counterparty_count=len(counterparties),
            hedge_count=len(hedges),
            hedge_benefit_pct=self._hedge_benefit_pct(ba_result),
            eligibility=eligibility,
            ba_cva_result=ba_result,
        )

    # ---- standardized measure --------------------------------------------

    def _run_standardized_measure(
        self,
        carve_out_counterparties: list[CVACounterparty],
        hedges: list[CVAHedge],
        sensitivities: list[SACVASensitivity],
        eligibility: CVAEligibility,
    ) -> CVACapitalResult:
        """SA-CVA (§__.224–§__.225) plus BA-CVA for carved-out netting sets (§__.223)."""
        sa_result = self.sa_cva_calculator.calculate(sensitivities)
        ba_result: BACVAResult | None = None
        k_ba = 0.0
        cp_rwa: dict[str, float] = {}
        sector_rwa: dict[str, float] = {}
        if carve_out_counterparties:
            ba_result = self.ba_cva_calculator.calculate(
                [cp.to_ba_cva() for cp in carve_out_counterparties],
                [h.to_ba_cva() for h in hedges],
            )
            k_ba = ba_result.k_basic
            cp_rwa, sector_rwa = self._allocate_ba_cva_rwa(ba_result)

        k_total = sa_result.k_cva + k_ba
        return CVACapitalResult(
            approach=CVAApproach.SA_CVA,
            k_cva=k_total,
            rwa=k_total * RWA_MULTIPLIER,
            k_sa_cva=sa_result.k_cva,
            k_ba_cva=k_ba,
            k_unhedged=ba_result.k_unhedged if ba_result else 0.0,
            k_hedged=ba_result.k_hedged if ba_result else 0.0,
            counterparty_rwa=cp_rwa,
            sector_rwa=sector_rwa,
            risk_class_rwa={
                k: v * RWA_MULTIPLIER for k, v in sa_result.k_by_risk_class.items()
            },
            total_ead=sum(cp.total_ead for cp in carve_out_counterparties),
            counterparty_count=len(carve_out_counterparties),
            hedge_count=len(hedges),
            hedge_benefit_pct=self._hedge_benefit_pct(ba_result) if ba_result else 0.0,
            eligibility=eligibility,
            ba_cva_result=ba_result,
            sa_cva_result=sa_result,
        )

    # ---- reporting helpers ------------------------------------------------

    @staticmethod
    def _allocate_ba_cva_rwa(
        result: BACVAResult,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Allocate BA-CVA RWA to counterparties and sectors pro rata to SCVA_c.

        Reporting convenience only (FR Y-9C HC-R / FFIEC 101 do not require
        a counterparty split); the rule defines K_basic at portfolio level.
        """
        total_scva = sum(r.scva for r in result.counterparty_results)
        cp_rwa: dict[str, float] = {}
        sector_rwa: dict[str, float] = {}
        if total_scva <= 0.0:
            return cp_rwa, sector_rwa
        for r in result.counterparty_results:
            share = r.scva / total_scva
            cp_rwa[r.counterparty_id] = result.rwa * share
            sector_rwa[r.sector.value] = sector_rwa.get(r.sector.value, 0.0) + result.rwa * share
        return cp_rwa, sector_rwa

    @staticmethod
    def _hedge_benefit_pct(result: BACVAResult) -> float:
        """Reduction of K_basic relative to the reduced BA-CVA (0.65·K_unhedged)."""
        from src.cva_risk.cva_params import BA_CVA_DISCOUNT_SCALAR

        base = BA_CVA_DISCOUNT_SCALAR * result.k_unhedged
        if base <= 0.0:
            return 0.0
        return (base - result.k_basic) / base * 100.0

    def compute_rwa(
        self,
        counterparties: list[CVACounterparty] | None = None,
        hedges: list[CVAHedge] | None = None,
        sensitivities: list[SACVASensitivity] | None = None,
        approach: CVAApproach | None = None,
    ) -> float:
        """Convenience: RWA_CVA = 12.5 · K_CVA per ERBA NPR §__.221."""
        return self.calculate(
            counterparties, hedges, sensitivities, approach=approach,
        ).rwa
