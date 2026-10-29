"""Singapore regime calculator -- MAS Notice 637 (version effective 1 January 2026).

:class:`SGRegime` implements :class:`src.jurisdictions.base.RegimeCalculator`
by delegating to the SG modules (credit risk, operational risk, output floor,
capital stack, SA-CCR and BA-CVA).

References:
    - MAS Notice 637, Notice on Risk Based Capital Adequacy Requirements for Banks
      Incorporated in Singapore (20 September 2023, last revised 9 October 2025)
"""

from __future__ import annotations

from datetime import date

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
from src.jurisdictions.sg import capital_stack, cva, operational_risk, output_floor, saccr
from src.jurisdictions.sg.credit_risk import SGCreditRiskEngine


class SGRegime:
    """MAS Notice 637 regime (Singapore-incorporated banks).

    Args:
        is_dsib: designated by MAS as a D-SIB (Table 4-1 minimums); default True.
        as_of: reporting date -- drives the equity phase-in of Table 7-16; default 1 January 2026
            (the version date of the Notice transcribed here).
        loss_data_criteria_met: bank meets the loss-data criteria of paras 9.1.16-9.1.41.
        small_bank_ilm_approved: MAS approval for a BI <= S$1.5bn bank to use the ILM (9.1.8(a)).
        mas_floor_calibration: bank-specific higher output-floor calibration (para 5.1.6).
        imm_bank: the bank uses the CCR internal models method (DF = 1 in BA-CVA, 8.5.14).
    """

    jurisdiction: Jurisdiction = Jurisdiction.SG
    regime_name: str = "MAS Notice 637 (Singapore Basel III final reforms)"
    legal_basis: str = (
        "MAS Notice 637, Notice on Risk Based Capital Adequacy Requirements for Banks "
        "Incorporated in Singapore (Banking Act 1970 s.10), 20 September 2023, last revised "
        "9 October 2025; version effective 1 January 2026"
    )

    def __init__(
        self,
        is_dsib: bool = True,
        as_of: date = date(2026, 1, 1),
        loss_data_criteria_met: bool = True,
        small_bank_ilm_approved: bool = False,
        mas_floor_calibration: float | None = None,
        imm_bank: bool = False,
    ) -> None:
        """Configure the regime (see class docstring; MAS Notice 637 Parts IV, V, VII, IX)."""
        self.is_dsib = is_dsib
        self.as_of = as_of
        self.loss_data_criteria_met = loss_data_criteria_met
        self.small_bank_ilm_approved = small_bank_ilm_approved
        self.mas_floor_calibration = mas_floor_calibration
        self.imm_bank = imm_bank
        self._credit = SGCreditRiskEngine(as_of)

    # ------------------------------------------------------------------ credit risk

    def risk_weight(self, exposure: SAExposure) -> RiskWeightResult:
        """Risk weight, CCF and RWA for one exposure (MAS Notice 637 Part VII Division 3).

        ``risk_weight`` is the effective weight after CRM (RWA / E*); the pre-CRM obligor weight
        is in ``notes`` where they differ.
        """
        ccf, e_star, rwa, eff, out = self._credit.assess(exposure)
        notes = list(out.notes)
        if abs(eff - out.risk_weight) > 1e-12:
            notes.insert(0, f"obligor risk weight {out.risk_weight:.4f}")
        return RiskWeightResult(
            exposure_id=exposure.exposure_id,
            jurisdiction=Jurisdiction.SG,
            regime_exposure_class=out.regime_class,
            risk_weight=eff,
            ccf=ccf,
            exposure_amount=e_star,
            rwa=rwa,
            citation=out.citation,
            notes=notes,
        )

    def credit_rwa(self, exposures: list[SAExposure]) -> CreditRWAResult:
        """SA(CR) RWA for a portfolio (MAS Notice 637 para 7.1 / Part VII Division 3)."""
        items = [self.risk_weight(e) for e in exposures]
        rwa_by: dict[str, float] = {}
        exp_by: dict[str, float] = {}
        for it in items:
            rwa_by[it.regime_exposure_class] = rwa_by.get(it.regime_exposure_class, 0.0) + it.rwa
            exp_by[it.regime_exposure_class] = (
                exp_by.get(it.regime_exposure_class, 0.0) + it.exposure_amount
            )
        return CreditRWAResult(
            jurisdiction=Jurisdiction.SG,
            total_exposure=sum(i.exposure_amount for i in items),
            total_rwa=sum(i.rwa for i in items),
            rwa_by_class=rwa_by,
            exposure_by_class=exp_by,
            line_items=items,
        )

    def ccf(self, exposure: SAExposure) -> float:
        """CCF per MAS Notice 637 Annex 7B Table 7B-1."""
        return self._credit.ccf(exposure)

    # ------------------------------------------------------------------ other risks

    def operational_risk(self, inputs: OpRiskInputs) -> OpRiskResult:
        """SA(OR) per MAS Notice 637 Part IX (ILM computed for BI > S$1.5bn)."""
        return operational_risk.operational_risk(
            inputs,
            loss_data_criteria_met=self.loss_data_criteria_met,
            small_bank_ilm_approved=self.small_bank_ilm_approved,
        )

    def output_floor(
        self, pre_floor_rwa: float, standardised_rwa: float, year: int
    ) -> OutputFloorResult:
        """Output floor per MAS Notice 637 Part V, Table 5-3."""
        return output_floor.output_floor(
            pre_floor_rwa, standardised_rwa, year, self.mas_floor_calibration
        )

    def capital_requirements(
        self,
        systemic_bucket_or_rate: float = 0.0,
        countercyclical_rate: float = 0.0,
        stress_buffer: float = 0.0,
    ) -> CapitalRequirements:
        """Minimum CARs and buffers per MAS Notice 637 Part IV.

        ``systemic_bucket_or_rate`` is read as a G-SIB / D-SIB buffer *rate* (decimal). MAS 637
        has no stress capital buffer; ``stress_buffer`` is ignored (protocol compatibility).
        """
        del stress_buffer  # no stress buffer in MAS Notice 637
        return capital_stack.capital_requirements(
            is_dsib=self.is_dsib,
            systemic_buffer_rate=systemic_bucket_or_rate,
            countercyclical_rate=countercyclical_rate,
        )

    def saccr_ead(self, netting_set: SACCRNettingSetInput) -> SACCRResult:
        """SA-CCR EAD per MAS Notice 637 Annex 7D (alpha = 1.4 for all counterparties)."""
        return saccr.saccr_ead(netting_set)

    def ba_cva_capital(
        self,
        counterparties: list[dict[str, float | str | bool]],
        hedged: bool = False,
    ) -> dict[str, float]:
        """BA-CVA (reduced / full) per MAS Notice 637 paras 8.5.12-8.5.18."""
        return cva.ba_cva_capital(counterparties, hedged=hedged, imm_bank=self.imm_bank)
