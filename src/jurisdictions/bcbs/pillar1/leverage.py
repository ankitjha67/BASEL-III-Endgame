"""BCBS leverage ratio exposure measure (Basel Framework LEV30).

    Exposure = on-balance (LEV30.8-30.12, less Tier 1 deductions LEV30.3)
             + derivatives: alpha x (RC + PFE), alpha = 1.4, PFE multiplier = 1
               (LEV30.14-30.16; RC = max(V - CVM_r + CVM_p, 0), image p. 795)
               + written credit derivative effective notional net of eligible
               purchased protection (LEV30.30-30.35)
             + SFTs: gross SFT assets (LEV30.37(1)) less eligible netted cash payables
               + CCR current exposure (LEV30.37(2): E* = max(0, sum E_i - sum C_i))
             + off-balance: CCF x notional, CCFs of LEV30.49-30.54
             - exclusions (LEV30.7 central bank reserves where the discretion is used;
               LEV30.26 client-cleared trade exposures to a QCCP)

Input conventions (``LeverageInputs``):

- ``derivative_rc`` is sum over netting sets of max(V + CVM_p, 0), i.e. the replacement
  cost *before* eligible cash variation margin received; ``derivative_cash_vm_received``
  is the LEV30.24-eligible cash VM, deducted from RC only (LEV30.25(1)). The netting-set
  level floor of LEV30.16 cannot be enforced on aggregate inputs; the aggregate RC is
  floored at zero. Set ``flags["rc_net_of_cash_vm"]`` when ``derivative_rc`` already
  reflects the cash VM.
- ``derivative_pfe_addon`` is the SA-CCR aggregate add-on (CRE52.20-52.76) computed with
  the LEV30.16(3) modifications (multiplier = 1; written options included).
- ``sft_ccr_addon`` is the LEV30.37(2) current-exposure amount E*.
- ``obs_notional_by_ccf`` keys must be one of 100%, 50%, 40%, 20%, 10% (LEV30.49-30.54).
- ``central_bank_reserves`` is excluded only under the LEV30.7 discretion
  (option, or ``flags["central_bank_reserves_exemption"]``).
- ``client_cleared_trade_exposures_exempt``: the LEV30.26 amount *included in* the
  derivative component that the clearing member need not recognise.

References:
    - Basel Framework LEV30.1-30.56 (pp. 790-810)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.bcbs.pillar1 import params as p
from src.jurisdictions.pillar1_base import LeverageInputs, LeverageResult


def derivative_exposure(rc_before_vm: float, cash_vm_received: float, pfe_addon: float) -> float:
    """LEV30.15-30.16: alpha x (max(RC - CVM_r, 0) + 1 x AddOn)."""
    rc = max(rc_before_vm - cash_vm_received, 0.0)
    return p.LEV_ALPHA * (rc + p.LEV_PFE_MULTIPLIER * pfe_addon)


def written_credit_derivatives(effective_notional: float, eligible_offsets: float) -> float:
    """LEV30.31: effective notional less eligible purchased protection (not below zero)."""
    return max(effective_notional - eligible_offsets, 0.0)


def sft_current_exposure(lent: list[float], received: list[float], qualifying_mna: bool) -> float:
    """LEV30.37(2): E* = max(0, sum E_i - sum C_i) under a qualifying MNA, else
    sum_i max(0, E_i - C_i) transaction by transaction."""
    if qualifying_mna:
        return max(0.0, sum(lent) - sum(received))
    return sum(max(0.0, e - c) for e, c in zip(lent, received, strict=True))


def off_balance_sheet(notional_by_ccf: dict[float, float]) -> float:
    """LEV30.46-30.54: sum CCF x notional (CCFs 100/50/40/20/10%)."""
    total = 0.0
    for ccf, notional in notional_by_ccf.items():
        if not any(abs(ccf - k) < 1e-12 for k in p.LEV_CCF):
            raise ValueError(f"LEV30.49-30.54: CCF {ccf} is not a leverage-ratio CCF")
        total += ccf * notional
    return total


def leverage_exposure(inputs: LeverageInputs,
                      central_bank_reserves_exemption: bool = False) -> LeverageResult:
    """Total leverage ratio exposure measure (LEV30)."""
    on_bs = max(inputs.on_balance_sheet_assets - inputs.tier1_deductions, 0.0)
    vm = 0.0 if inputs.flags.get("rc_net_of_cash_vm", False) else inputs.derivative_cash_vm_received
    deriv = derivative_exposure(inputs.derivative_rc, vm, inputs.derivative_pfe_addon)
    deriv += written_credit_derivatives(inputs.written_credit_derivative_notional,
                                        inputs.written_credit_derivative_offsets)
    sfts = (max(inputs.sft_gross_assets - inputs.sft_netted_cash_payables, 0.0)
            + inputs.sft_ccr_addon)
    obs = off_balance_sheet(inputs.obs_notional_by_ccf)
    exempt_cb = central_bank_reserves_exemption or inputs.flags.get(
        "central_bank_reserves_exemption", False)
    exclusions = (inputs.central_bank_reserves if exempt_cb else 0.0)
    exclusions += min(inputs.client_cleared_trade_exposures_exempt, deriv)
    total = on_bs + deriv + sfts + obs - exclusions
    return LeverageResult(
        jurisdiction=Jurisdiction.BCBS,
        on_balance_sheet=on_bs,
        derivatives=deriv,
        sfts=sfts,
        off_balance_sheet=obs,
        exclusions=exclusions,
        total_exposure=total,
        citations={
            "on_balance_sheet": "LEV30.8-30.12; LEV30.3 Tier 1 deductions",
            "derivatives": "LEV30.13-30.16 (alpha 1.4, PFE multiplier 1); LEV30.25; "
                           "LEV30.30-30.35 written credit derivatives",
            "sfts": "LEV30.37 (gross SFT assets, netting criteria, E*)",
            "off_balance_sheet": "LEV30.45-30.56 (CCFs 100/50/50/40/20/10%)",
            "exclusions": "LEV30.7 central bank reserves (discretion); LEV30.26 client clearing",
        },
    )
