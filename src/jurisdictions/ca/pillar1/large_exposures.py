"""OSFI Guideline B-2 Large Exposure Limits (2028) -- consultation draft of May 21, 2026.

Scope (B-2 s.II): D-SIBs and Category I/II SMSBs, on a consolidated basis; foreign bank branches
and Category III SMSBs are excluded. Effective November 1, 2027 / January 1, 2028. Capital base:
Tier 1 (CAR Ch.2).

Large exposure: >= 10% of Tier 1 (s.III). Limits (s.IV):

- Canadian G-SIB: 15% to a G-SIB (or a group containing one); 20% to a Canadian D-SIB that is
  not a G-SIB; otherwise 25%.
- Canadian D-SIB (not a G-SIB): 20% to a Canadian D-SIB or a G-SIB; otherwise 25%.
- Category I/II SMSB: 25%.

Exemptions (s.V) are read from ``LargeExposureInput.is_exempt`` or one of the flags in
:data:`EXEMPTION_FLAGS`. Footnote 16: exposures risk-weighted at 1,250% are not exempt
(flag ``ca_rw_1250`` overrides ``ca_exempt_capital_deduction``). Exempted exposures meeting the
10% definition remain reportable (s.III(c)) except intra-day interbank exposures (footnote 10).
Other flags: ``ca_counterparty_is_canadian_dsib`` (counterparty is, or the group includes, a
Canadian D-SIB that is not a G-SIB).

References:
    - OSFI Guideline B-2 Large Exposure Limits (2028), draft, s.II-VII
    - Basel Framework LEX10-LEX40
"""

from __future__ import annotations

from src.jurisdictions.ca.pillar1 import params as p
from src.jurisdictions.pillar1_base import LargeExposureInput, LargeExposureRow

EXEMPTION_FLAGS: dict[str, str] = {
    "ca_exempt_capital_deduction": "s.V(a) amounts deducted from regulatory capital (not BFI)",
    "ca_exempt_government_of_canada": "s.V(b) Government of Canada / Bank of Canada",
    "ca_exempt_level1_hqla": "s.V(c) Level 1 HQLA (LAR Ch.2)",
    "ca_exempt_zero_rw_sovereign_domestic": "s.V(d) 0% RW sovereign, domestic currency",
    "ca_exempt_zero_rw_entity": "s.V(e) other entities at 0% under CAR s.4.1.1",
    "ca_exempt_canadian_pse_sovereign": "s.V(f)(i) Canadian PSE treated as sovereign",
    "ca_exempt_us_pse_conservatorship": "s.V(f)(ii) US PSE in conservatorship (OSFI approval)",
    "ca_exempt_foreign_pse_zero_rw_domestic": "s.V(f)(iii) foreign PSE at 0%, domestic currency",
    "ca_exempt_zero_rw_mdb": "s.V(g) qualifying MDB at 0%",
    "ca_exempt_underwriting_5_days": "s.V(h) capital/TLAC underwriting held <= 5 working days",
    "ca_exempt_tlac_market_making": "s.V(i) Other TLAC of G-SIBs/D-SIBs under market-making",
    "ca_exempt_intraday_interbank": "s.V(j) intra-day interbank exposures",
    "ca_exempt_qccp_clearing": "s.V(k) QCCP exposures related to clearing activities",
}
"""B-2 s.V exemptions (paragraph 15) [LEX 30.1, 30.15, 30.31, 30.35]."""


def applicable_limit(reporting_bank_is_gsib: bool, reporting_bank_is_dsib: bool,
                     counterparty_is_gsib: bool, counterparty_is_canadian_dsib: bool
                     ) -> tuple[float, str]:
    """Limit as a share of Tier 1 and its citation (B-2 s.IV [LEX 20.1, 40.1])."""
    if reporting_bank_is_gsib:
        if counterparty_is_gsib:
            return p.LE_LIMIT_GSIB_TO_GSIB, "B-2 s.IV (Canadian G-SIB to G-SIB 15%) [LEX 40.1]"
        if counterparty_is_canadian_dsib:
            return (p.LE_LIMIT_DSIB_INTERCONNECTED,
                    "B-2 s.IV (Canadian G-SIB to Canadian D-SIB 20%; OSFI-specific)")
        return p.LE_LIMIT_GENERAL, "B-2 s.IV (Canadian G-SIB, other 25%) [LEX 20.1]"
    if reporting_bank_is_dsib:
        if counterparty_is_gsib or counterparty_is_canadian_dsib:
            return (p.LE_LIMIT_DSIB_INTERCONNECTED,
                    "B-2 s.IV (Canadian D-SIB to D-SIB/G-SIB 20%; OSFI-specific)")
        return p.LE_LIMIT_GENERAL, "B-2 s.IV (Canadian D-SIB, other 25%) [LEX 20.1]"
    return p.LE_LIMIT_GENERAL, "B-2 s.IV (Category I/II SMSB 25%) [LEX 20.1]"


def is_exempt(e: LargeExposureInput) -> tuple[bool, str]:
    """Whether an exposure is exempt from the limits (B-2 s.V, footnote 16)."""
    hits = [k for k in EXEMPTION_FLAGS if e.flags.get(k, False)]
    if e.flags.get("ca_rw_1250", False) and hits == ["ca_exempt_capital_deduction"]:
        return False, "footnote 16: 1,250% risk-weighted exposures are not exempt"
    if e.flags.get("ca_rw_1250", False):
        hits = [h for h in hits if h != "ca_exempt_capital_deduction"]
    if hits:
        return True, "; ".join(EXEMPTION_FLAGS[h] for h in hits)
    if e.is_exempt:
        return True, "caller-designated exemption (B-2 s.V)"
    return False, ""


def large_exposures(exposures: list[LargeExposureInput], tier1_capital: float,
                    reporting_bank_is_gsib: bool, reporting_bank_is_dsib: bool = True
                    ) -> list[LargeExposureRow]:
    """Reporting threshold (10% of Tier 1) and limit test per counterparty (B-2 s.III-V)."""
    if tier1_capital <= 0:
        raise ValueError("Tier 1 capital must be positive")
    rows: list[LargeExposureRow] = []
    for e in exposures:
        pct, cite = applicable_limit(
            reporting_bank_is_gsib, reporting_bank_is_dsib or reporting_bank_is_gsib,
            e.counterparty_is_gsib, e.flags.get("ca_counterparty_is_canadian_dsib", False))
        exempt, why = is_exempt(e)
        share = e.exposure_value / tier1_capital
        large = share >= p.LE_REPORTING_THRESHOLD
        intraday = e.flags.get("ca_exempt_intraday_interbank", False)
        reportable = large and not (exempt and intraday)
        breach = (not exempt) and share > pct
        citation = f"{cite}; large exposure >= 10% of Tier 1 (B-2 s.III) [LEX 20.2]"
        if exempt:
            citation += f"; exempt: {why}"
        elif why:
            citation += f"; {why}"
        rows.append(LargeExposureRow(
            counterparty_id=e.counterparty_id, exposure_value=e.exposure_value,
            limit=pct * tier1_capital, limit_pct_of_tier1=pct, reportable=reportable,
            breach=breach, citation=citation))
    return rows


def structure_threshold(tier1_capital: float, is_dsib: bool = True) -> float:
    """Applicable look-through threshold for structured vehicles (B-2 paragraph 48 [LEX 30.42]).

    D-SIBs: 0.25% of Tier 1; Category I/II SMSBs: max(0.25% of Tier 1, $1.5 million).
    """
    base = p.LE_STRUCTURE_LOOKTHROUGH_THRESHOLD * tier1_capital
    return base if is_dsib else max(base, p.LE_SMSB_STRUCTURE_THRESHOLD_FLOOR_CAD_M)


def covered_bond_exposure_value(nominal: float, qualifying: bool) -> float:
    """Covered bond exposure value: >= 25% of nominal if qualifying, else 100% (B-2 para. 27)."""
    factor = (p.LE_QUALIFYING_COVERED_BOND_FACTOR if qualifying
              else p.LE_NON_QUALIFYING_COVERED_BOND_FACTOR)
    return factor * nominal


def obs_exposure_value(notional: float, ccf: float) -> float:
    """Off-balance sheet exposure value with the CAR s.4.1.18 CCF floored at 10% (B-2 s.VI)."""
    return notional * max(ccf, p.LE_OBS_CCF_FLOOR)


def ccp_clearing_exposure_value(kind: str, amount: float) -> float:
    """Exposure value of clearing exposures to a CCP (B-2 paragraph 30 table [LEX 30.57]).

    ``kind``: TRADE, SEGREGATED_IM (0), NON_SEGREGATED_IM, PREFUNDED_DF, UNFUNDED_DF (0), EQUITY.
    """
    zero = {"SEGREGATED_IM", "UNFUNDED_DF"}
    nominal = {"TRADE", "NON_SEGREGATED_IM", "PREFUNDED_DF", "EQUITY"}
    k = kind.upper()
    if k in zero:
        return 0.0
    if k in nominal:
        return amount
    raise ValueError(f"unknown CCP exposure kind {kind!r}")


def requires_interdependence_review(exposure_value: float, tier1_capital: float) -> bool:
    """Economic-interdependence investigation above 5% of Tier 1 (B-2 s.VII [LEX 10.18])."""
    return exposure_value > p.LE_ECONOMIC_INTERDEPENDENCE_REVIEW * tier1_capital
