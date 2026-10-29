"""OSFI CAR 2026 Chapter 7 s.7.1.8 -- exposures to central counterparties.

Qualifying CCPs (s.7.1.8.1): trade exposures 2% (clearing member, and clients meeting the two
protection conditions); 4% for clients not protected against the joint default of the clearing
member and another client; default fund contributions K_CM_i = max(K_CCP x DF_i^pref /
(DF_CCP + DF_CM^pref); 8% x 2% x DF_i^pref) with K_CCP = sum_i EAD_i x 20% x 8%; total capped at
the non-qualifying charge (s.7.1.8.1 C). Non-qualifying CCPs (s.7.1.8.2): Chapter 4 risk weight of
the CCP's counterparty category for trade exposures and a CET1 deduction of default fund
contributions (expressed here as an RWA equivalent of 12.5 x DF).

Regime-specific flags (``CCPExposureInput.flags``):

- ``ca_former_qccp_within_3_months``: CCP ceased to qualify within the last three months (s.7.1.8).
- ``ca_client_conditions_not_met``: client exposure failing the s.7.1.8.1 A(iii) conditions ->
  bilateral treatment (outside this calculator: raises ``ValueError``).
- ``ca_client_not_protected_joint_default``: client protected except against joint default -> 4%.
- ``ca_ccp_treated_as_corporate``: non-QCCP risk-weighted as a corporate (Table 9) rather than as a
  bank (Tables 5-6); a CCP "is a financial institution" for capital purposes (s.7.1.1).
- ``ca_ccp_scra_grade_a`` / ``ca_ccp_scra_grade_b``: SCRA grade of an unrated CCP treated as a
  bank (otherwise Grade C 150%, conservative).

References:
    - OSFI CAR 2026 Ch.7 s.7.1.8-7.1.8.2
    - Basel Framework CRE54
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, RatingBucket, SCRAGrade
from src.jurisdictions.ca import params as cap
from src.jurisdictions.ca.pillar1 import params as p
from src.jurisdictions.pillar1_base import CCPExposureInput, CCPResult


def k_ccp(eads: list[float], rw: float = p.KCCP_RISK_WEIGHT) -> float:
    """K_CCP = sum_i EAD_i x RW x 8%, RW >= 20% (CAR s.7.1.8.1 B, footnote 47 [CRE 54.29])."""
    if rw < p.KCCP_RISK_WEIGHT:
        raise ValueError("the K_CCP risk weight of 20% is a minimum (CAR Ch.7 footnote 47)")
    return sum(eads) * rw * p.KCCP_CAPITAL_RATIO


def sft_ead_to_member(ebrm: float, im: float, df: float) -> float:
    """EAD_i = max(EBRM_i - IM_i - DF_i; 0) for SFTs (CAR s.7.1.8.1 B [CRE 54.34])."""
    return max(ebrm - im - df, 0.0)


def k_cm(k_ccp_value: float, df_i: float, df_ccp: float, df_cm: float) -> float:
    """K_CM_i = max(K_CCP x DF_i / (DF_CCP + DF_CM); 8% x 2% x DF_i).

    CAR Ch.7 s.7.1.8.1 B [CRE 54.36].
    """
    denom = df_ccp + df_cm
    share = k_ccp_value * df_i / denom if denom > 0 else 0.0
    return max(share, p.KCM_FLOOR_CAPITAL_RATIO * p.KCM_FLOOR_RW * df_i)


def non_qccp_trade_rw(e: CCPExposureInput) -> tuple[float, str]:
    """Chapter 4 RW of the CCP's counterparty category (CAR s.7.1.8.2 [CRE 54.41])."""
    flags = e.flags
    if flags.get("ca_ccp_treated_as_corporate", False):
        if e.ccp_rating == RatingBucket.UNRATED:
            return cap.CORPORATE_UNRATED_RW, "CAR Ch.4 s.4.1.7 (unrated corporate 100%)"
        return cap.CORPORATE_RATED_RW[e.ccp_rating], "CAR Ch.4 s.4.1.7 Table 9"
    if e.ccp_rating != RatingBucket.UNRATED:
        return cap.BANK_ECRA_BASE_RW[e.ccp_rating], "CAR Ch.4 s.4.1.4 Table 5 (ECRA base)"
    if flags.get("ca_ccp_scra_grade_a", False):
        grade = SCRAGrade.A
    elif flags.get("ca_ccp_scra_grade_b", False):
        grade = SCRAGrade.B
    else:
        # TODO: VERIFY -- unrated CCP with no SCRA grade supplied: Grade C 150% is used as a
        # conservative default; the CCP's Chapter 4 category depends on its regulation.
        grade = SCRAGrade.C
    return cap.BANK_SCRA_BASE_RW[grade], f"CAR Ch.4 s.4.1.4 Table 6 (SCRA Grade {grade.value})"


def ccp_exposure(e: CCPExposureInput) -> CCPResult:
    """Trade-exposure and default-fund RWA for one CCP (CAR Ch.7 s.7.1.8)."""
    flags = e.flags
    qualifying = e.is_qualifying or flags.get("ca_former_qccp_within_3_months", False)
    nq_rw, nq_cite = non_qccp_trade_rw(e)
    nq_trade_rwa = nq_rw * e.trade_exposure
    nq_df_rwa = p.NON_QCCP_DF_DEDUCTION_RW_EQUIVALENT * e.default_fund_contribution
    if not qualifying:
        return CCPResult(
            ccp_id=e.ccp_id, jurisdiction=Jurisdiction.CA, trade_rw=nq_rw,
            trade_rwa=nq_trade_rwa, default_fund_rwa=nq_df_rwa,
            total_rwa=nq_trade_rwa + nq_df_rwa,
            citation=(f"CAR Ch.7 s.7.1.8.2: trade exposures at {nq_cite} [CRE 54.41]; default "
                      "fund contributions deducted from CET1 (RWA equivalent 12.5 x DF) "
                      "[CRE 54.42]"))
    if e.is_client_cleared_via_member:
        if flags.get("ca_client_conditions_not_met", False):
            raise ValueError("client conditions of CAR s.7.1.8.1 A(iii) not met: capitalise the "
                             "exposure to the clearing member as a bilateral trade (Ch.4/Ch.7)")
        if flags.get("ca_client_not_protected_joint_default", False):
            trade_rw = p.QCCP_CLIENT_NOT_PROTECTED_JOINT_DEFAULT_RW
            trade_cite = "s.7.1.8.1 A(iii) client 4% [CRE 54.16]"
        else:
            trade_rw = p.QCCP_CLIENT_RW
            trade_cite = "s.7.1.8.1 A(iii) client 2% [CRE 54.14-54.15]"
    else:
        trade_rw = p.QCCP_CLEARING_MEMBER_RW
        trade_cite = "s.7.1.8.1 A(i) clearing member 2% [CRE 54.7]"
    trade_rwa = trade_rw * e.trade_exposure
    df_rwa = 0.0
    df_cite = ""
    if e.default_fund_contribution > 0:
        if e.k_ccp is None or e.total_default_fund is None:
            df_rwa = nq_df_rwa
            df_cite = ("; K_CCP / DF totals not supplied: default fund capitalised at the "
                       "non-qualifying CCP cap (s.7.1.8.1 C)")
        else:
            # total_default_fund = DF_CCP + DF_CM^pref: only the sum enters K_CM.
            kcm = k_cm(e.k_ccp, e.default_fund_contribution, 0.0, e.total_default_fund)
            df_rwa = p.CAPITAL_TO_RWA * kcm
            df_cite = "; K_CM per s.7.1.8.1 B [CRE 54.36]"
    total = trade_rwa + df_rwa
    cap_rwa = nq_trade_rwa + nq_df_rwa
    cap_note = ""
    if total > cap_rwa:
        total = cap_rwa
        cap_note = "; capped at the non-qualifying CCP charge (s.7.1.8.1 C [CRE 54.40])"
    if e.initial_margin_bankruptcy_remote:
        cap_note += ("; posted IM held bankruptcy-remote by a custodian: 0% (s.7.1.8.1 A(iv) "
                     "[CRE 54.21]) -- exclude it from trade_exposure")
    return CCPResult(
        ccp_id=e.ccp_id, jurisdiction=Jurisdiction.CA, trade_rw=trade_rw, trade_rwa=trade_rwa,
        default_fund_rwa=df_rwa, total_rwa=total,
        citation=f"CAR Ch.7 {trade_cite}{df_cite}{cap_note}")

