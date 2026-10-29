"""Leverage-ratio total exposure measure (TEM) under MAS Notice 637 Annex 4C.

TEM = on-balance sheet items (2.8-2.12) + derivative transactions (2.13-2.39)
      + SFTs (2.40-2.50) + off-balance sheet items (2.51-2.53), then the deductions of
      paras 1.3, 2.6, 2.8 and 2.21(b) (para 2.3, p. 4-18).

- On-balance sheet: carrying amount net of specific allowances; items deducted from CET1 / AT1
  may be deducted (1.3); no netting of collateral or CRM (2.2).
- Derivatives: alpha x (RC + PFE), alpha = 1.4, RC = max(V - CVM_r + CVM_p, 0), PFE = SA-CCR
  add-on with the multiplier fixed at one (2.13-2.14, 2.17); eligible cash VM received may
  reduce RC (2.18, 2.21(a)); client-cleared QCCP trade exposures may be excluded where the
  clearing member is not obliged to reimburse the client (2.22-2.23); written credit derivatives
  add their effective notional, less eligible purchased protection (2.31-2.39).
- SFTs: gross SFT assets (cash payables / receivables netted only under 2.40(a)(ii)) plus the
  counterparty exposure max(0, sum CE - sum C) (2.40(b)).
- Off-balance sheet: notional x CCF of Table 4D-1 (Annex 4D) or Annex 7C (securitisation),
  less specific / general allowances (2.51-2.53).

MAS Notice 637 contains no exclusion of central bank reserves from the TEM (contrast BCBS
LEV30.7, a temporary national-discretion exemption): ``central_bank_reserves`` is not excluded
(it is part of ``on_balance_sheet_assets``).

Flags read from :attr:`LeverageInputs.flags`:

``cash_vm_conditions_met`` (default True): the cash VM received satisfies all conditions of
    para 2.18 and has not already reduced V under the Accounting Standards (2.21(a)).
``client_clearing_no_reimbursement`` (default True): the client-cleared trade exposures passed
    in ``client_cleared_trade_exposures_exempt`` meet paras 2.22 / 2.23.

References:
    - MAS Notice 637 Part IV Division 2 paras 4.2.1-4.2.2 (p. 4-12), Annex 4C (pp. 4-17 to
      4-36), Annex 4D Table 4D-1 (pp. 4-37, 4-38), Annex 7C (p. 7-181)
    - Basel Framework LEV30 (comparison)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import LeverageInputs, LeverageResult
from src.jurisdictions.sg.pillar1 import params as p


def derivative_exposure(
    replacement_cost_gross: float,
    pfe_addon: float,
    cash_vm_received: float = 0.0,
    cash_vm_eligible: bool = True,
) -> float:
    """EM for derivatives = alpha x (RC + multiplier x AddOn), multiplier fixed at 1.

    Reference: MAS Notice 637 Annex 4C paras 2.13-2.14, 2.17 and 2.21(a) (pp. 4-21 to 4-25).
    ``replacement_cost_gross`` is V (+ CVM_p) before eligible cash VM received.
    """
    vm = cash_vm_received if cash_vm_eligible else 0.0
    rc = max(replacement_cost_gross - vm, 0.0)
    return p.LEVERAGE_ALPHA * (rc + p.LEVERAGE_PFE_MULTIPLIER * pfe_addon)


def written_credit_derivative_addon(effective_notional: float, eligible_offsets: float) -> float:
    """Effective notional of written credit derivatives less eligible purchased protection.

    Reference: MAS Notice 637 Annex 4C paras 2.31-2.38 (pp. 4-28 to 4-31). Offsets cannot make
    the add-on negative.
    """
    return max(effective_notional - eligible_offsets, 0.0)


def sft_exposure(gross_assets: float, netted_cash_payables: float, ccr_addon: float) -> float:
    """EM for SFTs = (gross SFT assets - qualifying netted cash payables) + counterparty exposure.

    Reference: MAS Notice 637 Annex 4C para 2.40(a)-(b) (pp. 4-31, 4-32).
    """
    return max(gross_assets - netted_cash_payables, 0.0) + ccr_addon


def off_balance_exposure(notional_by_ccf: dict[float, float], allowances: float = 0.0) -> float:
    """Sum of notional x CCF (Table 4D-1 / Annex 7C), less allowances, floored at zero.

    Reference: MAS Notice 637 Annex 4C paras 2.51-2.53 (pp. 4-35, 4-36), Annex 4D Table 4D-1.
    Only CCFs that Table 4D-1 / Annex 7C can produce (10%, 20%, 40%, 50%, 100%) are accepted.
    """
    total = 0.0
    for ccf, notional in notional_by_ccf.items():
        if not any(abs(ccf - c) < 1e-12 for c in p.LEVERAGE_ALLOWED_CCFS):
            raise ValueError(f"CCF {ccf} is not a Table 4D-1 / Annex 7C CCF")
        total += ccf * notional
    return max(total - allowances, 0.0)


def leverage_ratio(tier1_capital: float, total_exposure: float) -> float:
    """Leverage ratio = capital measure / TEM.

    Reference: MAS Notice 637 Annex 4C para 1.1 (p. 4-17); minimum 3% (para 4.2.2).
    """
    if total_exposure <= 0.0:
        raise ValueError("total exposure measure must be positive")
    return tier1_capital / total_exposure


def leverage_exposure(inputs: LeverageInputs) -> LeverageResult:
    """Total exposure measure under MAS Notice 637 Annex 4C.

    Reference: MAS Notice 637 Annex 4C paras 1.3, 2.3, 2.8, 2.13-2.53 (pp. 4-17 to 4-36).
    """
    flags = inputs.flags
    on_bs = max(inputs.on_balance_sheet_assets - inputs.tier1_deductions, 0.0)
    deriv = derivative_exposure(
        inputs.derivative_rc,
        inputs.derivative_pfe_addon,
        inputs.derivative_cash_vm_received,
        bool(flags.get("cash_vm_conditions_met", True)),
    ) + written_credit_derivative_addon(
        inputs.written_credit_derivative_notional, inputs.written_credit_derivative_offsets
    )
    exclusions = 0.0
    if bool(flags.get("client_clearing_no_reimbursement", True)):
        exclusions = min(inputs.client_cleared_trade_exposures_exempt, deriv)
        deriv -= exclusions
    sfts = sft_exposure(
        inputs.sft_gross_assets, inputs.sft_netted_cash_payables, inputs.sft_ccr_addon
    )
    obs = off_balance_exposure(inputs.obs_notional_by_ccf)
    total = on_bs + deriv + sfts + obs
    return LeverageResult(
        jurisdiction=Jurisdiction.SG,
        on_balance_sheet=on_bs,
        derivatives=deriv,
        sfts=sfts,
        off_balance_sheet=obs,
        exclusions=exclusions,
        total_exposure=total,
        citations={
            "on_balance_sheet": "MAS 637 Annex 4C paras 1.3, 2.8-2.12 (net of CET1/AT1 "
            "deductions)",
            "derivatives": "MAS 637 Annex 4C paras 2.13-2.21 (alpha 1.4, multiplier 1), "
            "2.31-2.39 (written credit derivatives)",
            "sfts": "MAS 637 Annex 4C paras 2.40-2.50",
            "off_balance_sheet": "MAS 637 Annex 4C paras 2.51-2.53, Annex 4D Table 4D-1, "
            "Annex 7C",
            "exclusions": "MAS 637 Annex 4C paras 2.22-2.23 (client-cleared QCCP trade "
            "exposures); no central bank reserve exclusion in MAS 637",
            "minimum": "MAS 637 para 4.2.2 (3% at Solo and Group levels)",
        },
    )
