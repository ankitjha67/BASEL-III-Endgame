"""UK leverage-ratio total exposure measure -- PRA Rulebook Leverage Ratio (CRR) Part.

Art 429(4): total exposure measure = (a) assets excluding derivatives and SFT add-ons
+ (b) derivatives (Arts 429c-429d) + (c) SFT counterparty add-ons (Art 429e)
+ (d) off-balance-sheet items (Art 429f) + (e) regular-way purchases awaiting
settlement (Art 429g), less the Art 429a exclusions.

Input conventions (``LeverageInputs``; amounts in GBP millions):

* ``on_balance_sheet_assets``: Art 429b(1) asset values excluding derivatives and SFTs,
  including regular-way trades awaiting settlement per Art 429g (gross SFT assets go
  in ``sft_gross_assets``).
* ``derivative_rc``: SA-CCR replacement cost of the derivative netting sets *before*
  recognising cash variation margin received; ``derivative_cash_vm_received``: the
  cash VM eligible under Art 429c(3)(a)-(e), which reduces RC (floored at zero).
  ``flags['cash_vm_conditions_met'] = False`` disables the offset.
* ``derivative_pfe_addon``: SA-CCR aggregate add-on; the leverage PFE uses a
  multiplier of one (Art 429c(5)) and no NICA reduction (Art 429c(4)).
* alpha = 1.4 unless ``flags['alpha_one_counterparties']`` (all netting sets with
  NFCs / pension scheme arrangements: CCR Part Art 274(2) alpha = 1).
* ``written_credit_derivative_notional`` / ``..._offsets``: Art 429d(2)-(3).
* ``sft_gross_assets``, ``sft_netted_cash_payables`` (Art 429b(4) netting),
  ``sft_ccr_addon`` (Art 429e(2)-(3): max{0, E - C}; see :func:`sft_addon`).
* ``obs_notional_by_ccf``: Credit Risk: SA (CRR) Part Art 111 conversion factor ->
  notional; low-risk items take 10% (Art 429f(3)).
* ``central_bank_reserves``: central bank claims netted against same-currency
  liabilities under Art 429a(A1)-(A2) (``flags['central_bank_netting_conditions_met']``,
  default True).
* ``client_cleared_trade_exposures_exempt``: Art 429a(1)(g)-(h) QCCP trade exposures
  (not excluded where ``flags['affiliate_client_in_scope']``, Art 429a(4) / 429(5)).
* ``tier1_deductions``: Art 429a(1)(a)-(b) items deducted from the capital measure.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.pillar1_base import LeverageInputs, LeverageResult
from src.jurisdictions.uk.pillar1 import params as p


def sft_addon(
    lent_and_received: Sequence[tuple[float, float]], under_master_netting: bool
) -> float:
    """SFT counterparty credit risk add-on -- Art 429e(2)-(3).

    Per transaction (no qualifying MNA): sum_i max{0, E_i - C_i}; per master netting
    agreement: max{0, sum E_i - sum C_i}. The formulas are images on the Rulebook page;
    they are transcribed from CRR Art 429e(2)-(3), which the rule corresponds to.
    """
    if under_master_netting:
        return max(0.0, sum(e for e, _ in lent_and_received) - sum(c for _, c in lent_and_received))
    return sum(max(0.0, e - c) for e, c in lent_and_received)


def obs_exposure(obs_notional_by_ccf: dict[float, float]) -> float:
    """Off-balance-sheet items -- Art 429f(1), (3): notional x Art 111(1) conversion factor,
    with the 10% factor for low-risk items (no factor below 10%)."""
    return sum(n * max(ccf, p.LEV_LOW_RISK_OBS_CCF) for ccf, n in obs_notional_by_ccf.items())


def derivatives_exposure(inputs: LeverageInputs) -> float:
    """Derivatives -- Art 429c(1)-(5), 429d(2)-(3).

    alpha * (RC + 1 * AggAddOn) with RC reduced by eligible cash VM received
    (Art 429c(3)); plus written credit derivatives' effective notional less eligible
    purchased-protection offsets (Art 429d).
    """
    alpha = (p.LEV_SACCR_ALPHA_NFC_PENSION if inputs.flags.get("alpha_one_counterparties", False)
             else p.LEV_SACCR_ALPHA)
    vm = (inputs.derivative_cash_vm_received
          if inputs.flags.get("cash_vm_conditions_met", True) else 0.0)
    rc = max(inputs.derivative_rc - vm, 0.0)
    pfe = p.LEV_SACCR_MULTIPLIER * inputs.derivative_pfe_addon
    written = max(inputs.written_credit_derivative_notional
                  - inputs.written_credit_derivative_offsets, 0.0)
    return alpha * (rc + pfe) + written


def leverage_exposure_measure(inputs: LeverageInputs) -> LeverageResult:
    """Total exposure measure -- Art 429(4), less Art 429a exclusions."""
    on_bs = inputs.on_balance_sheet_assets
    deriv = derivatives_exposure(inputs)
    sfts = (max(inputs.sft_gross_assets - inputs.sft_netted_cash_payables, 0.0)
            + inputs.sft_ccr_addon)
    obs = obs_exposure(inputs.obs_notional_by_ccf)
    exclusions = inputs.tier1_deductions
    if inputs.flags.get("central_bank_netting_conditions_met", True):
        exclusions += inputs.central_bank_reserves
    if not inputs.flags.get("affiliate_client_in_scope", False):
        exclusions += inputs.client_cleared_trade_exposures_exempt
    total = max(on_bs + deriv + sfts + obs - exclusions, 0.0)
    return LeverageResult(
        jurisdiction=Jurisdiction.UK,
        on_balance_sheet=on_bs,
        derivatives=deriv,
        sfts=sfts,
        off_balance_sheet=obs,
        exclusions=exclusions,
        total_exposure=total,
        citations={
            "total": f"{p.LR} Art 429(2)-(4)",
            "on_balance_sheet": f"{p.LR} Art 429(4)(a), 429b(1); Art 429(7) (no CRM, no netting)",
            "derivatives": (
                f"{p.LR} Art 429c(1),(3)-(5) (SA-CCR, multiplier 1, cash VM only), 429d "
                "(written credit derivatives); CCR Part Art 274(2) alpha"
            ),
            "sfts": f"{p.LR} Art 429b(1),(4), 429e(1)-(3) (formula per CRR Art 429e)",
            "off_balance_sheet": f"{p.LR} Art 429f(1),(3) (10% for low-risk items)",
            "exclusions": (
                f"{p.LR} Art 429a(A1)-(A2) (central bank claims), 429a(1)(a)-(b) (Tier 1 "
                "deductions), 429a(1)(g)-(h) and (4) (QCCP client-clearing trade exposures)"
            ),
            "minimum": (
                "Leverage Ratio - Capital Requirements and Buffers Part (not supplied; "
                "TODO: VERIFY)"
            ),
        },
    )


def leverage_ratio(tier1_leverage_capital: float, total_exposure: float) -> float:
    """Leverage ratio = tier 1 capital (leverage) / total exposure measure -- Art 429(2)-(3)."""
    if total_exposure <= 0.0:
        raise ValueError("total exposure measure must be positive")
    return tier1_leverage_capital / total_exposure
