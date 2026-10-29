"""UK exposures to central counterparties -- PRA Rulebook CCR (CRR) Part, Arts 300-311.

* Trade exposures (Art 306(1)): 2% to a QCCP; to a non-qualifying CCP, the
  Standardised Approach risk weight under Credit Risk: General Provisions (CRR)
  Part Art 107(2)(b) -- i.e. as an exposure to a corporate.
* Clients (Art 305): Art 306 treatment (2%) where the Art 305(2) segregation and
  portability conditions hold and the CCP is a QCCP; 4% where only joint-default
  protection is missing (Art 305(3)); otherwise the bilateral CCR treatment of
  Sections 1-8 against the clearing member.
* Pre-funded default fund contributions to a QCCP (Art 308(2)):
  K_i = max{K_CCP * DF_i / (DF_CCP + DF_CM); 8% * 2% * DF_i}; RWEA = 12.5 * K_i.
* Non-qualifying CCP default fund (Art 309): K = DF + UC; RWEA = 12.5 * K.
* Unfunded contributions to a QCCP: 0% (Art 310).
* Cap (Art 303(2)): a clearing member's QCCP trade + default fund requirement is
  capped at the requirement that would apply if the CCP were non-qualifying.
* Art 311: a CCP that will cease to meet its authorisation / recognition
  conditions is treated as non-qualifying within three months.

``CCPExposureInput.flags`` keys read here: ``art305_2_conditions_met`` (default
True for client-cleared trades), ``art305_3_joint_default_unprotected``,
``cm_no_client_reimbursement`` (Art 306(1)(c), exposure value zero),
``ccp_ceasing_conditions`` (Art 311), ``cash_transactions_only`` (Art 301(1)),
``is_clearing_member`` (Art 303(2) cap; default True unless client-cleared).
``total_default_fund`` is DF_CCP + DF_CM. ``ccp_rating`` gives the corporate CQS
for non-qualifying CCPs and, for client trades failing Art 305(2), is read as the
clearing member's rating (contract gap: no separate field).
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.pillar1_base import CCPExposureInput, CCPResult
from src.jurisdictions.uk import params as uk
from src.jurisdictions.uk.credit_risk import cqs_of
from src.jurisdictions.uk.pillar1 import params as p


def corporate_rw(rating: RatingBucket) -> float:
    """Corporate risk weight for a non-qualifying CCP -- Art 107(2)(b) -> SA Part Art 122(2)
    Table 6 by CQS; 100% unrated (Art 122(5))."""
    cqs = cqs_of(rating)
    return uk.CORPORATE_UNRATED_RW if cqs is None else uk.CORPORATE_RATED_TABLE_6[cqs]


def institution_rw(rating: RatingBucket) -> float:
    """Clearing-member (institution) risk weight -- SA Part Art 120(1) Table 3 by CQS.

    # TODO: VERIFY -- unrated clearing members need the Art 121 SCRA grade, which the
    contract does not carry; the conservative SCRA Grade C 150% is used.
    """
    cqs = cqs_of(rating)
    return uk.INSTITUTION_SCRA_TABLE_5["C"] if cqs is None else uk.INSTITUTION_RATED_TABLE_3[cqs]


def qccp_default_fund_capital(df_i: float, k_ccp: float, df_ccp_plus_cm: float) -> float:
    """K_i = max{K_CCP * DF_i / (DF_CCP + DF_CM); 8% * 2% * DF_i} -- Art 308(2) (formula
    image on the Rulebook page; transcribed from CRR Art 308(2))."""
    floor = p.QCCP_DF_FLOOR_CAPITAL_RATIO * p.QCCP_DF_FLOOR_RW * df_i
    if df_ccp_plus_cm <= 0.0:
        return max(k_ccp, floor) if df_i > 0.0 else 0.0
    return max(k_ccp * df_i / df_ccp_plus_cm, floor)


def non_qccp_default_fund_capital(df: float, uc: float = 0.0) -> float:
    """K = DF + UC -- Art 309(1)."""
    return df + uc


def ccp_exposure_rwa(e: CCPExposureInput) -> CCPResult:
    """Trade-exposure and default-fund RWEA for one CCP exposure."""
    qualifying = e.is_qualifying and not e.flags.get("ccp_ceasing_conditions", False)
    cites: list[str] = []
    ead = e.trade_exposure
    if e.flags.get("cm_no_client_reimbursement", False):
        ead = 0.0
        cites.append(f"{p.CCR} Art 306(1)(c) (exposure value zero)")
    if e.flags.get("ccp_ceasing_conditions", False):
        cites.append(f"{p.CCR} Art 311(2)(a)-(b) (treated as non-qualifying)")

    client = e.is_client_cleared_via_member
    joint_default_gap = e.flags.get("art305_3_joint_default_unprotected", False)
    if client and qualifying and joint_default_gap:
        trade_rw = p.QCCP_CLIENT_NOT_PROTECTED_JOINT_DEFAULT_RW
        cites.append(f"{p.CCR} Art 305(3) (4% in place of 2%)")
    elif client and not (qualifying and e.flags.get("art305_2_conditions_met", True)):
        trade_rw = institution_rw(e.ccp_rating)
        cites.append(
            f"{p.CCR} Art 305(1) (bilateral CCR to the clearing member; SA Part Art 120 "
            "Table 3 on ccp_rating read as the clearing member's rating -- contract gap)"
        )
    elif qualifying:
        trade_rw = p.QCCP_TRADE_RW
        cites.append(f"{p.CCR} Art 306(1)(a) (2% QCCP)"
                     + ("; Art 305(2) client treatment" if client else ""))
    else:
        trade_rw = corporate_rw(e.ccp_rating)
        cites.append(f"{p.CCR} Art 306(1)(b); Credit Risk: General Provisions (CRR) Part "
                     "Art 107(2)(b) (corporate risk weight)")
    trade_rwa = ead * trade_rw

    df_rwa = 0.0
    df = e.default_fund_contribution
    if df > 0.0:
        if e.flags.get("cash_transactions_only", False):
            cites.append(f"{p.CCR} Art 301(1) (0% DF for cash transactions only)")
        elif qualifying and e.k_ccp is not None and e.total_default_fund is not None:
            k_i = qccp_default_fund_capital(df, e.k_ccp, e.total_default_fund)
            df_rwa = p.DF_RWA_MULTIPLIER * k_i
            cites.append(f"{p.CCR} Art 308(2)-(3) (formula per {p.CRR_EU} Art 308(2))")
        else:
            # Non-qualifying (Art 309), or a QCCP whose K_CCP / DF totals were not
            # supplied -- conservative fall-back to Art 309 (TODO: VERIFY input gap).
            df_rwa = p.DF_RWA_MULTIPLIER * non_qccp_default_fund_capital(df)
            cites.append(f"{p.CCR} Art 309(1)-(2)" + (
                "" if not qualifying else " (K_CCP not supplied: conservative fall-back)"))

    is_cm = e.flags.get("is_clearing_member", not client)
    if qualifying and is_cm:
        cap = ead * corporate_rw(e.ccp_rating) + p.DF_RWA_MULTIPLIER * df
        if trade_rwa + df_rwa > cap:
            scale = cap / (trade_rwa + df_rwa)
            trade_rwa *= scale
            df_rwa *= scale
            cites.append(f"{p.CCR} Art 303(2) (capped at the non-qualifying CCP requirement)")
    return CCPResult(
        ccp_id=e.ccp_id,
        jurisdiction=Jurisdiction.UK,
        trade_rw=trade_rw,
        trade_rwa=trade_rwa,
        default_fund_rwa=df_rwa,
        total_rwa=trade_rwa + df_rwa,
        citation="; ".join(cites) if cites else f"{p.CCR} Art 306",
    )
