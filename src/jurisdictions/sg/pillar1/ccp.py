"""Exposures to central counterparties under MAS Notice 637 Part VII Division 7.

Qualifying CCP (para 7.7.4): trade-exposure RWA + 12.5 x K_CM.

- Clearing member, own account or client trades it guarantees: 2% (7.7.15).
- Client of a clearing member meeting all 7.7.20 conditions: 2%; all except 7.7.20(b)(i)(C)
  (no protection against the joint default of the clearing member and another client): 4%
  (7.7.23); otherwise a bilateral exposure to the clearing member (7.7.24).
- Collateral: bankruptcy remote -> no capital (7.7.25, 7.7.27); otherwise 2% / 4% (7.7.26,
  7.7.28).
- Default fund: K_CCP = sum EAD_i x 20% x 8% (7.7.41);
  K_CM = max(K_CCP x DF_CM(Bank) / (DF_CCP + DF_CM), 8% x 2% x DF_CM(Bank)) (7.7.44);
  0% for settlement-risk-only default funds (7.7.4(b)).
- Cap: if QCCP RWA exceeds the non-qualifying RWA, use the latter (7.7.5).

Non-qualifying CCP (7.7.6): trade exposures as bilateral CCR (risk weight of the CCP under the
SA(CR)) + 1250% on funded and unfunded default fund contributions. A CCP whose K_CCP is not
available fails 7.7.3(c) (read with 7.7.37(a)-(b)) and is treated as non-qualifying.

Flags read from :attr:`CCPExposureInput.flags`:

``client_no_joint_default_protection``  client meets 7.7.20 except (b)(i)(C) -> 4% (7.7.23).
``client_conditions_not_met``           client fails 7.7.20 / 7.7.23 -> bilateral (7.7.24).
``clearing_member_reimburses_client``   default True; a clearing member's client-leg exposure
                                        to the CCP is capitalised only if it must reimburse the
                                        client (7.7.15).
``settlement_risk_only_default_fund``   0% on the default fund (7.7.4(b), 7.7.6(b)).
``counterparty_is_bank``                the CCP (non-qualifying) or the clearing member
                                        (7.7.24) is risk-weighted in the bank asset class;
                                        otherwise the general corporate class.
``scra_grade_a`` / ``scra_grade_b``     assessment grade for an unrated bank counterparty
                                        (default Grade C, para 7.3.60).

``ccp_rating`` is the rating of the CCP (non-qualifying) or of the clearing member (7.7.24).
``trade_exposure`` is E / EAD of the CCP trade exposures including non-bankruptcy-remote posted
collateral; bankruptcy-remote collateral must be excluded by the caller (7.7.25, 7.7.27).

References:
    - MAS Notice 637 paras 7.7.1-7.7.45 (pp. 7-154 to 7-166)
    - Basel Framework CRE54 (comparison)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, RatingBucket, SCRAGrade
from src.jurisdictions.pillar1_base import CCPExposureInput, CCPResult
from src.jurisdictions.sg.credit_risk import bank_rw, corporate_rw
from src.jurisdictions.sg.pillar1 import params as p


def k_ccp(eads: list[float], risk_weight: float = p.KCCP_RISK_WEIGHT) -> float:
    """Hypothetical capital of the CCP: K_CCP = sum EAD_i x 20% x 8%.

    Reference: MAS Notice 637 paras 7.7.41-7.7.43 (pp. 7-163 to 7-165); MAS may specify a risk
    weight above 20% (7.7.42(e)).
    """
    if risk_weight < p.KCCP_RISK_WEIGHT:
        raise ValueError("the K_CCP risk weight may not be below 20% (7.7.41, 7.7.42(e))")
    return sum(eads) * risk_weight * p.KCCP_CAPITAL_RATIO


def k_cm(kccp: float, df_bank: float, df_ccp: float, df_cm_total: float) -> float:
    """K_CM(Bank) = max(K_CCP x DF_bank / (DF_CCP + DF_CM), 8% x 2% x DF_bank).

    Reference: MAS Notice 637 para 7.7.44 (p. 7-166).
    """
    denom = df_ccp + df_cm_total
    if denom <= 0.0:
        raise ValueError("DF_CCP + DF_CM must be positive")
    return max(kccp * df_bank / denom, p.DF_CAPITAL_RATIO * p.DF_RW_FLOOR * df_bank)


def counterparty_rw(rating: RatingBucket, is_bank: bool, flags: dict[str, bool]) -> float:
    """SA(CR) risk weight of a CCP or clearing member treated bilaterally.

    Reference: MAS Notice 637 paras 7.7.6(a), 7.7.24, 7.1.9; Tables 7-5 / 7-7 (bank) and
    Table 7-10 (general corporate) (pp. 7-44 to 7-49).
    """
    if is_bank:
        grade = SCRAGrade.A if flags.get("scra_grade_a") else (
            SCRAGrade.B if flags.get("scra_grade_b") else SCRAGrade.C
        )
        return bank_rw(rating, scra_grade=grade)
    return corporate_rw(rating)


def _non_qualifying(e: CCPExposureInput) -> tuple[float, float, float]:
    """(trade RW, trade RWA, default fund RWA) for a non-qualifying CCP (para 7.7.6)."""
    rw = counterparty_rw(e.ccp_rating, bool(e.flags.get("counterparty_is_bank")), e.flags)
    df_rw = (
        p.SETTLEMENT_ONLY_DF_RW
        if e.flags.get("settlement_risk_only_default_fund")
        else p.NON_QCCP_DF_RW
    )
    return rw, rw * e.trade_exposure, df_rw * e.default_fund_contribution


def ccp_exposure(e: CCPExposureInput) -> CCPResult:
    """Trade-exposure and default-fund RWA for one CCP.

    Reference: MAS Notice 637 paras 7.7.3-7.7.6, 7.7.15-7.7.28, 7.7.41-7.7.44
    (pp. 7-154 to 7-166).
    """
    flags = e.flags
    nq_rw, nq_trade, nq_df = _non_qualifying(e)
    qualifying = e.is_qualifying and e.k_ccp is not None and e.total_default_fund is not None
    if not qualifying:
        why = "" if e.is_qualifying else " (not a qualifying CCP)"
        if e.is_qualifying:
            why = " (K_CCP / DF data unavailable: 7.7.3(c), 7.7.37(a)-(b) not met)"
        return CCPResult(
            ccp_id=e.ccp_id,
            jurisdiction=Jurisdiction.SG,
            trade_rw=nq_rw,
            trade_rwa=nq_trade,
            default_fund_rwa=nq_df,
            total_rwa=nq_trade + nq_df,
            citation=f"MAS 637 paras 7.7.6-7.7.9{why}: bilateral SA(CR) RW on trade exposures, "
            "1250% on default fund contributions",
        )

    # ---- Trade exposures to a qualifying CCP ----
    if e.is_client_cleared_via_member:
        if flags.get("client_conditions_not_met"):
            trade_rw = counterparty_rw(e.ccp_rating, bool(flags.get("counterparty_is_bank")),
                                       flags)
            trade_cite = "7.7.24 (bilateral exposure to the clearing member)"
        elif flags.get("client_no_joint_default_protection"):
            trade_rw = p.QCCP_CLIENT_RW_NO_JOINT_DEFAULT_PROTECTION
            trade_cite = "7.7.23 (4%)"
        else:
            trade_rw = p.QCCP_TRADE_RW
            trade_cite = "7.7.20 (2%)"
    else:
        trade_rw = p.QCCP_TRADE_RW
        trade_cite = "7.7.15 (2%)"
        if not flags.get("clearing_member_reimburses_client", True):
            trade_cite += "; client leg with no reimbursement obligation excluded by caller"
    trade_rwa = trade_rw * e.trade_exposure

    # ---- Default fund (7.7.36-7.7.45) ----
    assert e.k_ccp is not None and e.total_default_fund is not None
    if flags.get("settlement_risk_only_default_fund"):
        df_rwa = 0.0
        df_cite = "7.7.4(b) (0%, settlement-risk-only default fund)"
    else:
        # total_default_fund = DF_CCP + DF_CM^pref (contract field)
        if e.total_default_fund > 0.0:
            cap_req = k_cm(e.k_ccp, e.default_fund_contribution, 0.0, e.total_default_fund)
        else:
            cap_req = p.DF_CAPITAL_RATIO * p.DF_RW_FLOOR * e.default_fund_contribution
        df_rwa = p.CCP_RWA_MULTIPLIER * cap_req
        df_cite = "7.7.44 (K_CM, 2% RW floor) x 12.5 (7.7.4(b))"

    total = trade_rwa + df_rwa
    cite = f"MAS 637 paras 7.7.4, {trade_cite}, {df_cite}"
    if total > nq_trade + nq_df:
        cite += "; capped at non-qualifying RWA (7.7.5)"
        return CCPResult(
            ccp_id=e.ccp_id,
            jurisdiction=Jurisdiction.SG,
            trade_rw=nq_rw,
            trade_rwa=nq_trade,
            default_fund_rwa=nq_df,
            total_rwa=nq_trade + nq_df,
            citation=cite,
        )
    return CCPResult(
        ccp_id=e.ccp_id,
        jurisdiction=Jurisdiction.SG,
        trade_rw=trade_rw,
        trade_rwa=trade_rwa,
        default_fund_rwa=df_rwa,
        total_rwa=total,
        citation=cite,
    )
