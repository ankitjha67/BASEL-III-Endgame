"""Large exposures under MAS Notice 656 (last revised 22 May 2026, effective 1 July 2026).

- Limit: aggregate exposures to a single counterparty group must not exceed 25% of Tier 1
  capital, at Solo and Group levels (paras 7-8).
- A G-SIB headquartered in Singapore must not exceed 15% of Tier 1 to any other G-SIB or a
  connected counterparty group including a G-SIB (para 9), applied within 12 months of the
  bank (or the counterparty) becoming a G-SIB on or after 1 July 2021 (paras 10-11).
- A "large exposure" is >= 10% of Tier 1 (para 4). Semi-annual reporting covers all large
  exposures including exempt exposures except intraday interbank exposures (para 28(a)),
  all non-exempt exposures >= 10% of Tier 1 before CRM (28(b)) and the 20 largest (28(c)).
- Exempt exposures (Annex A para 1): Singapore Government / MAS; other sovereigns and central
  banks in domestic currency, or rated AA- or better, or for statutory liquidity / reserve
  requirements; PSEs at 0% under Table 7-3; BIS, IMF, ECB, EU, ESM, EFSF; qualifying MDBs;
  intraday interbank exposures (up to 2 business days); QCCP clearing exposures (Table C-2);
  qualifying intragroup exposures (Annex A para 1(g)).

Flags read from :attr:`LargeExposureInput.flags` (each marks an Annex A exemption):
``sg_government_or_mas`` (1(a)), ``sovereign_domestic_currency`` (1(b)(i)),
``sovereign_rated_aa_minus_or_better`` (1(b)(ii)), ``statutory_requirement`` (1(b)(iii)),
``pse_zero_rw_table_7_3`` (1(c)), ``supranational`` (1(d)), ``qualifying_mdb`` (1(da)),
``intraday_interbank`` (1(e)), ``qccp_clearing`` (1(f)), ``intragroup_exempt`` (1(g)).
Additional: ``gsib_headquartered_in_singapore`` (default True when the reporting bank is a
G-SIB, para 9), ``gsib_transition_period`` (paras 10-11: the 15% limit not yet applicable).

References:
    - MAS Notice 656 paras 4, 7-11, 16, 20, 28 (pp. 6, 10-15), Annex A (pp. 17-19),
      Annex C (pp. 25-38)
    - Basel Framework LEX10-LEX40 (comparison)
"""

from __future__ import annotations

from src.jurisdictions.pillar1_base import LargeExposureInput, LargeExposureRow
from src.jurisdictions.sg.pillar1 import params as p

EXEMPTION_FLAGS: dict[str, str] = {
    "sg_government_or_mas": "Annex A para 1(a)",
    "sovereign_domestic_currency": "Annex A para 1(b)(i)",
    "sovereign_rated_aa_minus_or_better": "Annex A para 1(b)(ii)",
    "statutory_requirement": "Annex A para 1(b)(iii)",
    "pse_zero_rw_table_7_3": "Annex A para 1(c)",
    "supranational": "Annex A para 1(d)",
    "qualifying_mdb": "Annex A para 1(da)",
    "intraday_interbank": "Annex A para 1(e)",
    "qccp_clearing": "Annex A para 1(f), Annex C Table C-2",
    "intragroup_exempt": "Annex A para 1(g)",
}
"""Exempt exposures of MAS Notice 656 Annex A para 1 (pp. 17-19), keyed by input flag."""


def exemption(exposure: LargeExposureInput) -> str | None:
    """Citation of the Annex A exemption that applies, or None.

    Reference: MAS Notice 656 Annex A para 1 (pp. 17-19); ``is_exempt`` is a caller-asserted
    exemption.
    """
    for flag, cite in EXEMPTION_FLAGS.items():
        if exposure.flags.get(flag, False):
            return cite
    if exposure.is_exempt:
        return "Annex A para 1 (caller-asserted)"
    return None


def applicable_limit(exposure: LargeExposureInput, reporting_bank_is_gsib: bool) -> float:
    """Limit as a share of Tier 1: 25%, or 15% G-SIB-to-G-SIB for a Singapore-HQ G-SIB.

    Reference: MAS Notice 656 paras 7, 8(b), 9, 10-11 (pp. 10, 11).
    """
    hq_sg = bool(exposure.flags.get("gsib_headquartered_in_singapore", True))
    transition = bool(exposure.flags.get("gsib_transition_period", False))
    if reporting_bank_is_gsib and hq_sg and exposure.counterparty_is_gsib and not transition:
        return p.LE_GSIB_TO_GSIB_LIMIT
    return p.LE_GENERAL_LIMIT


def large_exposures(
    exposures: list[LargeExposureInput], tier1_capital: float, reporting_bank_is_gsib: bool
) -> list[LargeExposureRow]:
    """Reporting threshold and limit test for each single counterparty group.

    Reference: MAS Notice 656 paras 4, 7-9, 20(a), 25, 28 (pp. 6, 10-15). ``breach`` is True
    where a non-exempt exposure exceeds the limit ("must not ... exceed"); ``reportable`` is
    True where the exposure is a large exposure (>= 10% of Tier 1), except intraday interbank
    exposures (para 28(a)).
    """
    if tier1_capital <= 0.0:
        raise ValueError("Tier 1 capital must be positive")
    rows: list[LargeExposureRow] = []
    for e in exposures:
        pct = applicable_limit(e, reporting_bank_is_gsib)
        limit = pct * tier1_capital
        ex = exemption(e)
        is_large = e.exposure_value >= p.LE_REPORTING_THRESHOLD * tier1_capital - 1e-9
        reportable = is_large and not e.flags.get("intraday_interbank", False)
        breach = ex is None and e.exposure_value > limit + 1e-9
        para = "9" if pct == p.LE_GSIB_TO_GSIB_LIMIT else "7-8"
        cite = f"MAS Notice 656 para {para} ({pct:.0%} of Tier 1); para 28 (>= 10% reported)"
        if ex is not None:
            cite += f"; exempt: {ex}"
        rows.append(
            LargeExposureRow(
                counterparty_id=e.counterparty_id,
                exposure_value=e.exposure_value,
                limit=limit,
                limit_pct_of_tier1=pct,
                reportable=reportable,
                breach=breach,
                citation=cite,
            )
        )
    return rows


def requires_dependence_due_diligence(exposure_value: float, tier1_capital: float) -> bool:
    """Economic-dependence due diligence where the exposure exceeds 5% of Tier 1.

    Reference: MAS Notice 656 para 16 (p. 12).
    """
    return exposure_value > p.LE_DUE_DILIGENCE_THRESHOLD * tier1_capital


def obs_exposure_value(notional: float, ccf: float) -> float:
    """Off-balance sheet exposure value = notional x Table 7B-1 CCF, CCF floored at 10%.

    Reference: MAS Notice 656 Annex C para 2.5 (p. 26).
    """
    return notional * max(ccf, p.LE_OBS_CCF_FLOOR)
