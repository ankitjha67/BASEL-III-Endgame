"""BCBS capital requirements for bank exposures to central counterparties (CRE54).

Qualifying CCPs (CRE54.6-54.40):

- trade exposures: 2% for a clearing member (CRE54.7) and for a client meeting
  CRE54.14-54.15; 4% where the client is not protected against the joint default of
  the clearing member and another client (CRE54.16); otherwise bilateral (CRE54.17);
- default fund: K_CCP = sum_i EAD_i x 20% x 8% (CRE54.29, image p. 491);
  K_CM_i = max(K_CCP x DF_i / (DF_CCP + DF_CM), 8% x 2% x DF_i) (CRE54.36, image p. 493);
- cap: total QCCP capital <= the non-qualifying CCP capital (CRE54.40).

Non-qualifying CCPs (CRE54.41-54.42): trade exposures at the SA risk weight of the
counterparty category; default fund contributions (funded and unfunded) at 1250%.

Keys read from ``CCPExposureInput.flags``:

- ``client_conditions_met`` (default True): CRE54.15 conditions for a client.
- ``protected_against_joint_default`` (default True): False -> CRE54.16 4%.
- ``ccp_is_bank``: non-QCCP trade exposure under the bank ECRA table (CRE20.18 Table 6);
  otherwise the corporate table (CRE20.43 Table 10).
- ``settlement_only_default_fund``: CRE54.1 footnote 241, 0% on the default fund.

``total_default_fund`` is DF_CCP + DF_CM^pref (the CRE54.36 denominator).
``initial_margin_bankruptcy_remote`` is informational: posted collateral that is
bankruptcy remote has a zero CCR requirement (CRE54.21) and must be left out of
``trade_exposure`` by the caller.

References:
    - Basel Framework CRE54.1-54.42 (pp. 483-494); CRE20.18, CRE20.43 (SA risk weights)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, RatingBucket, SCRAGrade
from src.jurisdictions.bcbs import params as sa
from src.jurisdictions.bcbs.pillar1 import params as p
from src.jurisdictions.pillar1_base import CCPExposureInput, CCPResult


def k_ccp(eads: list[float], rw: float = p.CCP_KCCP_RW) -> float:
    """CRE54.29: K_CCP = sum_i EAD_i x RW x capital ratio (RW 20% minimum, ratio 8%)."""
    return sum(eads) * rw * p.CCP_KCCP_CAPITAL_RATIO


def sft_ead_for_kccp(ebrm: float, im: float, df: float) -> float:
    """CRE54.34: EAD_i = max(EBRM_i - IM_i - DF_i; 0) for SFTs."""
    return max(ebrm - im - df, 0.0)


def k_cm(kccp: float, df_i: float, df_ccp_plus_df_cm: float) -> float:
    """CRE54.36: K_CM_i = max(K_CCP x DF_i^pref/(DF_CCP + DF_CM^pref); 8% x 2% x DF_i^pref)."""
    if df_ccp_plus_df_cm <= 0:
        raise ValueError("DF_CCP + DF_CM^pref must be positive")
    return max(kccp * df_i / df_ccp_plus_df_cm,
               p.CCP_KCM_FLOOR_RATIO * p.CCP_KCM_FLOOR_RW * df_i)


def non_qccp_trade_rw(rating: RatingBucket, is_bank: bool) -> float:
    """CRE54.41: SA risk weight by counterparty category.

    Bank: CRE20.18 Table 6 (ECRA base RW). An unrated bank needs an SCRA grade, which
    the contract does not carry: TODO: VERIFY -- conservative placeholder SCRA Grade C
    (150%, CRE20.21 Table 7). Corporate: CRE20.43 Table 10 (unrated 100%).
    """
    if is_bank:
        if rating == RatingBucket.UNRATED:
            return sa.BANK_SCRA_BASE_RW[SCRAGrade.C]
        return sa.BANK_ECRA_BASE_RW[rating]
    return sa.CORPORATE_RW[rating]


def qccp_trade_rw(e: CCPExposureInput) -> tuple[float, str]:
    """Trade-exposure risk weight for a QCCP (CRE54.7, CRE54.14-54.17)."""
    if not e.is_client_cleared_via_member:
        return p.CCP_QCCP_TRADE_RW, "CRE54.7"
    if not e.flags.get("client_conditions_met", True):
        raise ValueError("CRE54.17: client exposure is a bilateral trade with the clearing "
                         "member; its SA risk weight is outside this contract")
    if not e.flags.get("protected_against_joint_default", True):
        return p.CCP_QCCP_CLIENT_NO_JOINT_DEFAULT_RW, "CRE54.16"
    return p.CCP_QCCP_TRADE_RW, "CRE54.14-54.15"


def ccp_exposure(e: CCPExposureInput) -> CCPResult:
    """Trade-exposure and default-fund RWA for one CCP (CRE54)."""
    nq_rw = non_qccp_trade_rw(e.ccp_rating, e.flags.get("ccp_is_bank", False))
    nq_trade = nq_rw * e.trade_exposure
    settlement_only = e.flags.get("settlement_only_default_fund", False)
    nq_df = 0.0 if settlement_only else p.CCP_NON_QUALIFYING_DF_RW * e.default_fund_contribution
    if not e.is_qualifying:
        return CCPResult(ccp_id=e.ccp_id, jurisdiction=Jurisdiction.BCBS, trade_rw=nq_rw,
                         trade_rwa=nq_trade, default_fund_rwa=nq_df, total_rwa=nq_trade + nq_df,
                         citation="CRE54.41 (SA RW of the counterparty); CRE54.42 (DF 1250%)")
    rw, cite = qccp_trade_rw(e)
    trade_rwa = rw * e.trade_exposure
    if settlement_only or e.default_fund_contribution == 0.0:
        df_rwa = 0.0
        df_cite = "CRE54.1 fn 241 (0%)" if settlement_only else "no default fund contribution"
    else:
        if e.k_ccp is None or e.total_default_fund is None:
            raise ValueError("CRE54.36: K_CCP and DF_CCP + DF_CM^pref are required")
        df_rwa = p.CAPITAL_TO_RWA * k_cm(e.k_ccp, e.default_fund_contribution,
                                         e.total_default_fund)
        df_cite = "CRE54.36 K_CM"
    total = trade_rwa + df_rwa
    citation = f"{cite} trade RW; {df_cite}"
    if total > nq_trade + nq_df:
        total = nq_trade + nq_df
        citation += "; CRE54.40 cap (non-qualifying CCP requirement) applied"
    return CCPResult(ccp_id=e.ccp_id, jurisdiction=Jurisdiction.BCBS, trade_rw=rw,
                     trade_rwa=trade_rwa, default_fund_rwa=df_rwa, total_rwa=total,
                     citation=citation)
