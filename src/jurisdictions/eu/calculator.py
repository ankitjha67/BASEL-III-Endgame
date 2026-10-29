"""EU CRR3 regime calculator -- implements :class:`~src.jurisdictions.base.RegimeCalculator`.

Delegates to the EU modules:

* :mod:`.credit_risk`       -- SA-CR (Articles 111-134, 223-235, 495a-495d, 501-501a)
* :mod:`.operational_risk`  -- Articles 312-314 (BIC only, no ILM)
* :mod:`.output_floor`      -- Article 92(3) and Article 465
* :mod:`.capital_stack`     -- Article 92(1)-(1a); CRD buffers as inputs
* :mod:`.saccr`             -- Articles 274, 278
* :mod:`.cva`               -- Articles 382-386

The reporting year drives every CRR3 transitional (equity phase-in, UCC
factor, output-floor factor, Article 465 S-TREA risk weights).

References:
    - Regulation (EU) No 575/2013 as amended by Regulation (EU) 2024/1623
"""

from __future__ import annotations

from collections import defaultdict

from src.jurisdictions.base import (
    CapitalRequirements,
    CreditRWAResult,
    Jurisdiction,
    OpRiskInputs,
    OpRiskResult,
    OutputFloorResult,
    RiskWeightResult,
    SACCRNettingSetInput,
    SACCRResult,
    SAExposure,
)
from src.jurisdictions.eu import (
    capital_stack,
    credit_risk,
    cva,
    operational_risk,
    output_floor,
    saccr,
)


class EURegime:
    """European Union -- CRR (Regulation (EU) No 575/2013) as amended by CRR3 (Reg. 2024/1623).

    Args:
        year: reporting year for the CRR3 transitionals (default 2026).
        apply_465_2_cap: exercise the Article 465(2) option (TREA capped at
            125 % of U-TREA until 2029).
        individual_basis_floor_waiver: Member State derogation of Article 92(3)
            second subparagraph (floor not applied at individual level).
    """

    jurisdiction: Jurisdiction = Jurisdiction.EU
    regime_name: str = "EU CRR3"
    legal_basis: str = (
        "Regulation (EU) No 575/2013 (CRR) as amended by Regulation (EU) 2024/1623 (CRR3), "
        "applicable from 1 January 2025"
    )

    def __init__(
        self,
        year: int = 2026,
        apply_465_2_cap: bool = True,
        individual_basis_floor_waiver: bool = False,
    ) -> None:
        """Configure the reporting year and the Article 92(3)/465(2) options."""
        self.year = year
        self.apply_465_2_cap = apply_465_2_cap
        self.individual_basis_floor_waiver = individual_basis_floor_waiver

    # ----------------------------------------------------------------- credit
    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CCF and RWEA for one exposure -- CRR Part Three Title II Chapter 2."""
        return credit_risk.assign_risk_weight(exposure, self.year)

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """Aggregate SA credit RWEA -- Article 92(4)(a) credit-risk component."""
        return self._aggregate([self.risk_weight(e) for e in exposures])

    def credit_rwa_for_output_floor(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """SA credit RWEA for S-TREA -- Article 92(5)(a) with the Article 465(3)/(5)/(9)
        transitionals."""
        return self._aggregate(
            [credit_risk.assign_risk_weight(e, self.year, for_output_floor=True) for e in exposures]
        )

    @staticmethod
    def _aggregate(lines: list[RiskWeightResult]) -> CreditRWAResult:
        """Sum line items by regime exposure class (Article 112)."""
        rwa_by: dict[str, float] = defaultdict(float)
        exp_by: dict[str, float] = defaultdict(float)
        for r in lines:
            rwa_by[r.regime_exposure_class] += r.rwa
            exp_by[r.regime_exposure_class] += r.exposure_amount
        return CreditRWAResult(
            jurisdiction=Jurisdiction.EU,
            total_exposure=sum(r.exposure_amount for r in lines),
            total_rwa=sum(r.rwa for r in lines),
            rwa_by_class=dict(rwa_by),
            exposure_by_class=dict(exp_by),
            line_items=lines,
        )

    def ccf(self, exposure: SAExposure) -> float:
        """Credit conversion factor -- Article 111(2), Annex I, Article 495d."""
        return credit_risk.ccf(exposure, self.year)[0]

    # ---------------------------------------------------------- op risk
    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """Operational risk own funds requirement and RWA -- Articles 312-314, 92(6)(b)."""
        return operational_risk.operational_risk(inputs)

    # ---------------------------------------------------------- floor
    def output_floor(
        self, pre_floor_rwa: float, standardised_rwa: float, year: int
    ) -> OutputFloorResult:
        """TREA = max{U-TREA; x S-TREA} with Article 465 transitionals -- Article 92(3)."""
        return output_floor.total_risk_exposure_amount(
            pre_floor_rwa,
            standardised_rwa,
            year,
            apply_transitional_cap=self.apply_465_2_cap,
            individual_basis_waiver=self.individual_basis_floor_waiver,
        )

    # ---------------------------------------------------------- capital
    def capital_requirements(
        self,
        systemic_bucket_or_rate: float = 0.0,
        countercyclical_rate: float = 0.0,
        stress_buffer: float = 0.0,
        o_sii_rate: float = 0.0,
        systemic_risk_buffer_rate: float = 0.0,
    ) -> CapitalRequirements:
        """Article 92(1)-(1a) minima and the CRD combined buffer (rates as inputs)."""
        return capital_stack.capital_requirements(
            systemic_bucket_or_rate,
            countercyclical_rate,
            stress_buffer,
            o_sii_rate,
            systemic_risk_buffer_rate,
        )

    # ---------------------------------------------------------- CCR / CVA
    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """SA-CCR exposure value -- Articles 274(2), 278."""
        return saccr.saccr_ead(netting_set, self.year)

    def ba_cva_capital(
        self,
        counterparties: list[dict[str, float | str | bool]],
        hedged: bool = False,
    ) -> dict[str, float]:
        """Basic approach CVA own funds requirement -- Article 384."""
        return cva.ba_cva_capital(counterparties, hedged)
