"""OSFI Leverage Requirements Guideline (2023) -- leverage ratio exposure measure and requirement.

Exposure measure = on-balance sheet + derivatives + SFTs + off-balance sheet (LR s.VI, [LEV 20.5]).

- On-balance sheet: gross accounting values net of specific provisions; balance sheet assets
  deducted from CET1/AT1 may be deducted (LR s.VI(a), paragraph 25 [LEV 30.3, 30.9]).
- Derivatives: 1.4 x (RC + PFE) "as described in section 7.1.7 of the CAR Guideline" (LR
  paragraph 37 [LEV 30.14]). Unlike Basel LEV30.15-30.24, the OSFI text does **not** fix the PFE
  multiplier at one nor restrict RC to cash variation margin: the CAR s.7.1.7 SA-CCR applies as is
  (except that the SWWR treatment is not applied). Written credit derivatives add their effective
  notional net of eligible purchased protection (LR paragraphs 42-49 [LEV 30.30-30.35]).
- SFTs: gross SFT assets (adjusted for qualifying netting of cash payables/receivables) plus a
  current-exposure CCR add-on without PFE (LR s.VI(c), paragraph 53 [LEV 30.37]).
- Off-balance sheet: notional x CCF with the LR s.VI(d) CCFs, incl. the OSFI-only 25% CCF on
  undrawn credit and charge card balances.
- Central bank reserves may be excluded only while OSFI applies the temporary exemption of LR
  s.VI (exceptional macroeconomic circumstances [LEV 30.7]); OSFI then recalibrates the minimum.

Requirement: 3% minimum (paragraph 17 [LEV 20.7]); D-SIBs add a leverage ratio buffer equal to
50% of their higher-loss absorbency requirement (1% D-SIB surcharge -> 3.5%) [LEV 40.1-40.2];
plus any institution-specific authorized leverage ratio communicated bilaterally.

Regime-specific inputs (``LeverageInputs.flags``):

- ``ca_central_bank_reserves_exemption``: OSFI's temporary exemption is in force.

``derivative_rc`` is read as the CAR s.7.1.7 replacement cost and ``derivative_pfe_addon`` as the
SA-CCR aggregate add-on; because ``LeverageInputs`` does not carry V - C, the PFE multiplier is
taken as 1 (conservative: CAR's multiplier is <= 1). ``derivative_cash_vm_received`` is not
deducted again.

References:
    - OSFI Leverage Requirements Guideline (2023) s.III-VI
    - Basel Framework LEV10-LEV40
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.ca.pillar1 import params as p
from src.jurisdictions.pillar1_base import LeverageInputs, LeverageResult


def derivative_exposure(rc: float, pfe_addon: float, pfe_multiplier: float = 1.0) -> float:
    """1.4 x (RC + multiplier x AddOn) per CAR s.7.1.7 (LR paragraph 37 [LEV 30.14])."""
    if not 0.0 < pfe_multiplier <= 1.0:
        raise ValueError("SA-CCR PFE multiplier must lie in (0, 1] (CAR s.7.1.7.3)")
    return p.LR_DERIVATIVE_ALPHA * (rc + pfe_multiplier * pfe_addon)


def written_credit_derivative_exposure(effective_notional: float, offsets: float) -> float:
    """Effective notional of written credit derivatives less eligible offsets, floored at 0.

    LR s.VI(b)(iii) paragraphs 43-45 [LEV 30.31]: reduced by negative fair-value changes in Tier 1
    and by purchased protection on the same reference name meeting the paragraph 45 conditions.
    """
    return max(effective_notional - offsets, 0.0)


def sft_current_exposure(lent: list[float], received: list[float], qualifying_mna: bool) -> float:
    """CCR add-on for SFTs (LR paragraph 53(ii) [LEV 30.37(2)]).

    With a qualifying MNA: E' = max(0, sum E_i - sum C_i); otherwise per transaction
    E_i' = max(0, E_i - C_i).
    """
    if qualifying_mna:
        return max(0.0, sum(lent) - sum(received))
    return sum(max(0.0, e - c) for e, c in zip(lent, received, strict=True))


def off_balance_sheet(obs_notional_by_ccf: dict[float, float]) -> float:
    """Sum of notional x CCF with the LR s.VI(d) CCFs (paragraphs 61-75 [LEV 30.45-30.56])."""
    total = 0.0
    for ccf, notional in obs_notional_by_ccf.items():
        if not any(abs(ccf - c) < 1e-12 for c in p.LR_PERMITTED_CCFS):
            raise ValueError(f"CCF {ccf} is not an LR s.VI(d) credit conversion factor")
        total += ccf * notional
    return total


def leverage_exposure(inputs: LeverageInputs) -> LeverageResult:
    """Total leverage ratio exposure measure (LR s.VI [LEV 20.5, 30])."""
    on_bs = max(inputs.on_balance_sheet_assets - inputs.tier1_deductions, 0.0)
    # TODO: VERIFY -- PFE multiplier taken as 1 because LeverageInputs carries no V - C; the
    # LR text applies the CAR s.7.1.7 multiplier (<= 1), so this is conservative.
    deriv = (derivative_exposure(inputs.derivative_rc, inputs.derivative_pfe_addon)
             + written_credit_derivative_exposure(inputs.written_credit_derivative_notional,
                                                  inputs.written_credit_derivative_offsets))
    sfts = (max(inputs.sft_gross_assets - inputs.sft_netted_cash_payables, 0.0)
            + inputs.sft_ccr_addon)
    obs = off_balance_sheet(inputs.obs_notional_by_ccf)
    exclusions = inputs.client_cleared_trade_exposures_exempt
    citations = {
        "on_balance_sheet": "LR s.VI(a) (paragraph 25 deductions) [LEV 30.3, 30.8-30.9]",
        "derivatives": ("LR paragraph 37: 1.4 x (RC + PFE) per CAR s.7.1.7, no leverage "
                        "modification; PFE multiplier taken as 1 (V - C not supplied); written "
                        "credit derivatives paragraphs 42-49 [LEV 30.14, 30.30-30.35]"),
        "sfts": "LR s.VI(c) paragraph 53 [LEV 30.37]",
        "off_balance_sheet": ("LR s.VI(d) CCFs 10/20/25(cards)/40/50/100% [LEV 30.45-30.56]"),
        "client_cleared": "LR paragraph 39 (QCCP leg not guaranteed to the client) [LEV 30.26]",
        "derivative_cash_vm_received": ("not deducted: the RC input is the CAR s.7.1.7 RC, which "
                                        "already reflects collateral (LR paragraph 37)"),
    }
    if inputs.flags.get("ca_central_bank_reserves_exemption", False):
        exclusions += inputs.central_bank_reserves
        citations["central_bank_reserves"] = (
            "LR s.VI temporary exemption in exceptional macroeconomic circumstances, with a "
            "commensurate increase in the minimum [LEV 30.7]")
    else:
        citations["central_bank_reserves"] = ("not excluded: no OSFI temporary exemption in force "
                                              "(LR s.VI [LEV 30.7])")
    total = on_bs + deriv + sfts + obs - exclusions
    return LeverageResult(
        jurisdiction=Jurisdiction.CA, on_balance_sheet=on_bs, derivatives=deriv, sfts=sfts,
        off_balance_sheet=obs, exclusions=exclusions, total_exposure=max(total, 0.0),
        citations=citations,
    )


def leverage_requirement(is_dsib: bool, hla: float = 0.0,
                         authorized_ratio: float | None = None) -> float:
    """Minimum leverage ratio: 3% + 50% x HLA for D-SIBs, or the authorized ratio if higher.

    LR s.IV (paragraph 17 [LEV 20.7]; D-SIB buffer [LEV 40.1-40.2]); ``hla`` is the risk-based
    higher-loss absorbency (the higher of the D-SIB 1% and any G-SIB surcharge, CAR Ch.1 Annex 1).
    """
    req = p.LR_MINIMUM + (p.LR_DSIB_BUFFER_SHARE_OF_HLA * hla if is_dsib else 0.0)
    if authorized_ratio is not None:
        req = max(req, authorized_ratio)
    return req


def leverage_conservation_ratio(tier1_leverage_ratio: float) -> float:
    """Minimum capital conservation ratio from the Tier 1 leverage ratio (LR Table 1 [LEV 40.5]).

    For a D-SIB in the first HLA bucket (1%).
    """
    for _cet1_ub, lev_ub, ratio in p.LR_DSIB_CONSERVATION_BANDS:
        if tier1_leverage_ratio <= lev_ub:
            return ratio
    return 0.0
