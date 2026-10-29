"""EU exposures to central counterparties -- CRR Articles 300-311 (consolidated, not amended
by CRR3).

Trade exposures (Article 306):

* QCCP: 2 % (306(1)(a)); client positions meeting 305(2): 2 %; where the client is not
  protected against the joint default of the clearing member and another client, 4 %
  (305(3)); clearing member not obliged to reimburse its client on CCP default: exposure
  value zero (306(1)(c)); bankruptcy-remote posted collateral: exposure value zero (306(2)).
* Non-qualifying CCP: the SA risk weight of a corporate (306(1)(b) -> 107(2)(b)), i.e.
  Article 122 Table 1 by credit quality step, 100 % unrated.

Default fund contributions (Articles 307-310):

* QCCP pre-funded (308(2), formula image cons. p.400):
  K_i = max{ K_CCP x DF_i / (DF_CCP + DF_CM) ; 8 % x 2 % x DF_i }, RWEA = 12,5 K_i (308(3)).
* Non-QCCP pre-funded and unfunded (309): K = DF + UC, RWEA = 12,5 K (i.e. 1 250 %).
* QCCP unfunded (310): 0 %.
* DF covering only cash transactions: 0 % (301(1) second subparagraph).

Cap (303(2)): the clearing member's QCCP requirement (trade + DF) is capped at the
requirement that would apply if the CCP were non-qualifying.

CCP ceasing to meet authorisation/recognition conditions (311): non-QCCP treatment.

Input conventions (``CCPExposureInput``):

* ``total_default_fund`` = DF_CCP + DF_CM (both communicated under Article 50c EMIR).
* ``k_ccp`` = hypothetical capital communicated by the QCCP (Article 50c EMIR; its
  formula is in EMIR Article 50a, not in the CRR). Where it is missing the engine
  applies the conservative Article 309 treatment to the contribution.
* ``trade_exposure`` should already exclude bankruptcy-remote posted collateral (306(2)).
* flags: ``eu_305_3_joint_default`` (4 %), ``eu_305_2_not_met`` (client positions not
  eligible for Article 306: bilateral treatment, see TODO), ``eu_306_1_c_no_reimbursement``,
  ``eu_311_ceasing``, ``eu_df_cash_only``, ``eu_cqs<n>`` (CCP credit quality step for the
  non-QCCP corporate weight; else ``ccp_rating`` is used).

References:
    - Regulation (EU) No 575/2013, Articles 107(2), 122, 300-311 (consolidated 09.07.2024)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, RatingBucket
from src.jurisdictions.eu import params as eu_prm
from src.jurisdictions.eu.pillar1 import params as prm
from src.jurisdictions.pillar1_base import CCPExposureInput, CCPResult

# TODO: VERIFY -- where a client's CCP-related positions fail Article 305(2), Article 305(1)
# sends them to the bilateral CCR framework against the clearing member, whose risk weight
# is not part of the CCPExposureInput contract. A conservative 150 % (Article 121 SCRA
# grade C, the highest unrated institution weight) is used as a placeholder.
CLIENT_NON_SEGREGATED_PLACEHOLDER_RW: float = eu_prm.INSTITUTION_SCRA_RW["C"]


def non_qccp_trade_rw(x: CCPExposureInput) -> float:
    """Corporate SA risk weight of a non-qualifying CCP -- Articles 306(1)(b), 107(2)(b), 122."""
    for k, v in x.flags.items():
        if v and k.startswith("eu_cqs") and k[6:].isdigit():
            return eu_prm.CORPORATE_RW_RATED_BY_CQS.get(int(k[6:]), eu_prm.CORPORATE_RW_UNRATED)
    if x.ccp_rating is RatingBucket.UNRATED:
        return eu_prm.CORPORATE_RW_UNRATED
    return eu_prm.CORPORATE_RW_RATED_BY_CQS[eu_prm.CQS_OF_RATING[x.ccp_rating]]


def k_cm_prefunded(df_i: float, k_ccp: float, df_ccp_plus_cm: float) -> float:
    """K_i = max{K_CCP x DF_i / (DF_CCP + DF_CM); 8 % x 2 % x DF_i} -- Article 308(2)."""
    if df_ccp_plus_cm <= 0:
        raise ValueError("DF_CCP + DF_CM must be positive")
    return max(
        k_ccp * df_i / df_ccp_plus_cm,
        prm.CCP_OWN_FUNDS_RATIO * prm.CCP_DF_FLOOR_RW * df_i,
    )


def non_qccp_default_fund_k(df: float, uc: float = 0.0) -> float:
    """K = DF + UC -- Article 309(1)."""
    return df + uc


def ccp_exposure(x: CCPExposureInput) -> CCPResult:
    """Trade-exposure and default-fund RWEA -- Articles 303-311."""
    f = x.flags
    qualifying = x.is_qualifying and not f.get("eu_311_ceasing", False)
    cites: list[str] = []

    # ---- trade exposures (Articles 305, 306)
    nq_rw = non_qccp_trade_rw(x)
    if f.get("eu_306_1_c_no_reimbursement", False):
        trade_rw, ead = 0.0, 0.0
        cites.append("Art. 306(1)(c): exposure value zero")
    elif not qualifying:
        trade_rw, ead = nq_rw, x.trade_exposure
        cites.append("Art. 306(1)(b) -> 107(2)(b), 122: corporate RW (non-QCCP)")
        if f.get("eu_311_ceasing", False):
            cites.append("Art. 311(2)(a)")
    elif x.is_client_cleared_via_member and f.get("eu_305_2_not_met", False):
        trade_rw, ead = CLIENT_NON_SEGREGATED_PLACEHOLDER_RW, x.trade_exposure
        cites.append("Art. 305(1): bilateral treatment (placeholder RW, TODO: VERIFY)")
    elif x.is_client_cleared_via_member and f.get("eu_305_3_joint_default", False):
        trade_rw, ead = prm.CCP_CLIENT_JOINT_DEFAULT_RW, x.trade_exposure
        cites.append("Art. 305(3): 4 %")
    else:
        trade_rw, ead = prm.CCP_QCCP_TRADE_RW, x.trade_exposure
        cites.append(
            "Art. 305(2) -> 306(1)(a): 2 %" if x.is_client_cleared_via_member
            else "Art. 306(1)(a): 2 %"
        )  # fmt: skip
    trade_rwa = trade_rw * ead

    # ---- default fund contributions (Articles 307-310)
    df = x.default_fund_contribution
    df_rwa = 0.0
    if df > 0:
        if f.get("eu_df_cash_only", False):
            cites.append("Art. 301(1): DF for cash transactions only, 0 %")
        elif not qualifying:
            df_rwa = prm.CCP_K_TO_RWA * non_qccp_default_fund_k(df)
            cites.append("Art. 309: K = DF + UC, x 12,5")
        elif x.k_ccp is None or not x.total_default_fund:
            df_rwa = prm.CCP_K_TO_RWA * non_qccp_default_fund_k(df)
            cites.append("Art. 308 inputs (K_CCP, DF_CCP + DF_CM) missing: Art. 309 applied")
        else:
            df_rwa = prm.CCP_K_TO_RWA * k_cm_prefunded(df, x.k_ccp, x.total_default_fund)
            cites.append("Art. 308(2)-(3): K_i = max(K_CCP DF_i/(DF_CCP+DF_CM); 8%x2%xDF_i)")

    total = trade_rwa + df_rwa
    # ---- cap for clearing members' QCCP exposures (Article 303(2))
    if qualifying and not x.is_client_cleared_via_member:
        cap = nq_rw * ead + prm.CCP_K_TO_RWA * non_qccp_default_fund_k(df)
        if total > cap:
            scale = cap / total
            trade_rwa, df_rwa, total = trade_rwa * scale, df_rwa * scale, cap
            cites.append("Art. 303(2) cap at non-QCCP requirement")
    return CCPResult(
        ccp_id=x.ccp_id,
        jurisdiction=Jurisdiction.EU,
        trade_rw=trade_rw,
        trade_rwa=trade_rwa,
        default_fund_rwa=df_rwa,
        total_rwa=total,
        citation="CRR " + "; ".join(cites) if cites else "CRR Art. 306",
    )
