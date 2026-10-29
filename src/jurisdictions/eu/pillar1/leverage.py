"""EU leverage-ratio total exposure measure -- CRR Articles 429-429g (CRR3 points (209)-(213)).

Total exposure measure (Article 429(4)) = sum of:

(a) assets other than derivatives / SFT add-ons, at their Article 111(1) exposure
    value (429b(1)), net of assets deducted from Tier 1 (429a(1)(a)-(b));
(b) derivatives at their SA-CCR exposure value (429c(1)): alpha 1,4 x (RC + PFE),
    with the PFE multiplier set to 1 (429c(5)), only cash variation margin meeting
    429c(3)(a)-(e) recognised in RC, collateral excluded from NICA (429c(4)),
    plus the effective notional of written credit derivatives net of eligible
    purchased protection (429d);
(c) SFTs: gross assets (no netting, 429b(1)(b), except cash payables/receivables
    meeting 429b(4)) plus the counterparty credit risk add-on (429e);
(d) off-balance-sheet items at the Article 111 CCFs (429f(1) as replaced by CRR3), with
    10 % for unconditionally cancellable commitments (429f(3) as replaced by CRR3 --
    the Article 495d 0 % transitional does NOT apply to the leverage ratio).

Exclusions (Article 429a(1)) supported from the inputs:

* (g)/(h) client-cleared QCCP trade exposures (``client_cleared_trade_exposures_exempt``),
  unless the 429(5) third-subparagraph condition fails (429a(4); flag
  ``eu_429a_4_condition_failed``);
* (n) central bank reserves and banknotes (``central_bank_reserves``) only where the
  competent authority has declared exceptional circumstances (429a(5)-(6); flag
  ``eu_429a_5_exceptional_circumstances``), in which case the adjusted requirement of
  429a(7) applies (:func:`adjusted_leverage_requirement`).

Inputs and flags (``LeverageInputs.flags``):

* ``derivative_rc`` is the replacement cost BEFORE eligible cash VM received;
  ``derivative_cash_vm_received`` is deducted (floor 0) unless flag
  ``eu_rc_net_of_vm`` says the RC already reflects it.
* ``obs_notional_by_ccf`` keys are Article 111(2) CCFs; a 0 % key (Article 495d UCC
  transitional) is raised to 10 % per 429f(3).

Amounts in the reporting currency, millions.

References:
    - Regulation (EU) No 575/2013, Articles 429-429g (consolidated 09.07.2024)
    - Regulation (EU) 2024/1623, Article 1 points (209)-(213)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction
from src.jurisdictions.eu.pillar1 import params as prm
from src.jurisdictions.pillar1_base import LeverageInputs, LeverageResult

_VALID_CCFS = frozenset(prm.LEV_CCF_BY_BUCKET.values())


def derivative_exposure(inputs: LeverageInputs) -> float:
    """Derivatives exposure -- Articles 429c(1), (3), (5) and 429d(2)-(3).

    alpha x (RC + multiplier x AddOn) with multiplier = 1, plus written credit
    derivative effective notionals net of eligible purchased protection (floor 0).
    """
    rc = inputs.derivative_rc
    if not inputs.flags.get("eu_rc_net_of_vm", False):
        rc = max(rc - inputs.derivative_cash_vm_received, 0.0)
    pfe = prm.LEV_PFE_MULTIPLIER * inputs.derivative_pfe_addon
    written = max(
        inputs.written_credit_derivative_notional - inputs.written_credit_derivative_offsets, 0.0
    )
    return prm.LEV_SACCR_ALPHA * (rc + pfe) + written


def sft_exposure(inputs: LeverageInputs) -> float:
    """SFT exposure -- Articles 429b(1)(b), 429b(4) netting and the 429e add-on."""
    gross = max(inputs.sft_gross_assets - inputs.sft_netted_cash_payables, 0.0)
    return gross + inputs.sft_ccr_addon


def off_balance_exposure(inputs: LeverageInputs) -> tuple[float, list[str]]:
    """Off-balance-sheet exposure -- Article 429f(1) (Article 111(2) CCFs) and 429f(3)."""
    total = 0.0
    notes: list[str] = []
    for ccf, notional in inputs.obs_notional_by_ccf.items():
        applied = ccf
        if ccf < prm.LEV_UCC_CCF:
            applied = prm.LEV_UCC_CCF
            notes.append(f"CCF {ccf:.0%} raised to 10 % for UCCs (Art. 429f(3))")
        elif ccf not in _VALID_CCFS:
            notes.append(f"CCF {ccf:.2%} is not an Article 111(2) bucket factor; used as given")
        total += applied * notional
    return total, notes


def leverage_exposure(inputs: LeverageInputs) -> LeverageResult:
    """Total exposure measure -- Article 429(4) with the Article 429a exclusions."""
    on_bs = max(inputs.on_balance_sheet_assets - inputs.tier1_deductions, 0.0)
    deriv = derivative_exposure(inputs)
    sfts = sft_exposure(inputs)
    obs, _ = off_balance_exposure(inputs)
    exclusions = 0.0
    cites = {
        "on_balance_sheet": "CRR Art. 429(4)(a), 429b(1); Tier 1 deductions out, 429a(1)(a)-(b)",
        "derivatives": "CRR Art. 429c(1), (3), (5) (alpha 1,4, multiplier 1); 429d written CDS",
        "sfts": "CRR Art. 429b(1)(b), 429b(4), 429e",
        "off_balance_sheet": "CRR Art. 429f(1) -> Art. 111(2) CCFs; 429f(3) 10 % for UCCs",
    }
    if inputs.client_cleared_trade_exposures_exempt and not inputs.flags.get(
        "eu_429a_4_condition_failed", False
    ):
        exclusions += inputs.client_cleared_trade_exposures_exempt
        cites["client_cleared"] = "CRR Art. 429a(1)(g)-(h)"
    if inputs.central_bank_reserves and inputs.flags.get(
        "eu_429a_5_exceptional_circumstances", False
    ):
        exclusions += inputs.central_bank_reserves
        cites["central_bank_reserves"] = (
            "CRR Art. 429a(1)(n), (5)-(6); adjusted requirement Art. 429a(7)"
        )
    total = on_bs + deriv + sfts + obs - exclusions
    return LeverageResult(
        jurisdiction=Jurisdiction.EU,
        on_balance_sheet=on_bs,
        derivatives=deriv,
        sfts=sfts,
        off_balance_sheet=obs,
        exclusions=exclusions,
        total_exposure=max(total, 0.0),
        citations=cites,
    )


def leverage_ratio(tier1_capital: float, total_exposure: float) -> float:
    """Leverage ratio = Tier 1 / total exposure measure -- Article 429(2)-(3)."""
    if total_exposure <= 0:
        raise ValueError("total exposure measure must be positive")
    return tier1_capital / total_exposure


def adjusted_leverage_requirement(em_lr: float, central_bank_exposures: float) -> float:
    """aLR = 3 % x EM_LR / (EM_LR - CB) -- Article 429a(7) (cons. pp.633-634).

    EM_LR includes the excluded central bank exposures on the reference date; CB is the
    daily average of the eligible central bank exposures over the preceding maintenance
    period.
    """
    if em_lr <= central_bank_exposures:
        raise ValueError("EM_LR must exceed CB")
    return prm.LEV_MINIMUM * em_lr / (em_lr - central_bank_exposures)


def leverage_requirement(gsii_buffer_rate: float = 0.0) -> float:
    """3 % minimum plus the G-SII leverage ratio buffer of 50 % x G-SII rate -- Art. 92(1), (1a)."""
    return prm.LEV_MINIMUM + prm.LEV_GSII_BUFFER_SHARE * gsii_buffer_rate
