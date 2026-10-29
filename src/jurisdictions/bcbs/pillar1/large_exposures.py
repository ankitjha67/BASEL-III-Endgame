"""BCBS large exposures framework (Basel Framework LEX10-LEX40).

- Large exposure / reporting threshold: >= 10% of Tier 1 (LEX10.8, LEX20.4(1)-(3)).
- Limit: sum of exposure values must not be higher than 25% of Tier 1 at all times
  (LEX20.1); 15% for a G-SIB's exposure to another G-SIB (LEX20.1, LEX40.1).
- Exempt from the limit: sovereigns, their central banks and PSEs treated as sovereigns
  (LEX10.7, LEX30.31) -- still reported when >= 10% (LEX30.33); QCCP clearing exposures
  (LEX30.54, reported per LEX20.4). Intraday interbank exposures are outside the
  framework for both reporting and the limit (LEX30.35).

Keys read from ``LargeExposureInput.flags``:

- ``intraday_interbank``: LEX30.35, neither limited nor reported.
- ``qccp_clearing_exposure``: LEX30.54, exempt from the limit, reported if >= 10%.
- ``pse_treated_as_sovereign``: LEX30.31 sovereign exemption for a PSE.

``is_exempt`` (caller-supplied) is treated as a limit exemption that remains
reportable, as LEX20.4(3) requires for exempted exposures.

References:
    - Basel Framework LEX10 (pp. 937-941), LEX20 (pp. 942-943), LEX30 (pp. 944-956),
      LEX40 (pp. 957-958)
"""

from __future__ import annotations

from src.jurisdictions.base import AssetClass
from src.jurisdictions.bcbs.pillar1 import params as p
from src.jurisdictions.pillar1_base import LargeExposureInput, LargeExposureRow


def limit_pct(counterparty_is_gsib: bool, reporting_bank_is_gsib: bool) -> float:
    """LEX20.1 / LEX40.1: 15% G-SIB to G-SIB, otherwise 25%."""
    if counterparty_is_gsib and reporting_bank_is_gsib:
        return p.LEX_GSIB_TO_GSIB_LIMIT
    return p.LEX_GENERAL_LIMIT


def is_sovereign_exempt(e: LargeExposureInput) -> bool:
    """LEX10.7 / LEX30.31: sovereigns, central banks, PSEs treated as sovereigns."""
    return e.counterparty_asset_class == AssetClass.SOVEREIGN or (
        e.counterparty_asset_class == AssetClass.PSE
        and e.flags.get("pse_treated_as_sovereign", False))


def covered_bond_exposure_value(nominal: float, qualifies_lex30_39: bool) -> float:
    """LEX30.38: qualifying covered bonds may use 20% of nominal; others 100%."""
    return nominal * (p.LEX_COVERED_BOND_MIN_EXPOSURE_FACTOR if qualifies_lex30_39 else 1.0)


def obs_exposure_value(notional: float, sa_ccf: float) -> float:
    """LEX30.6: SA CCF with a floor of 10%."""
    return notional * max(sa_ccf, p.LEX_OBS_CCF_FLOOR)


def look_through_required(underlying_exposure: float, tier1_capital: float) -> bool:
    """LEX30.42-30.43: look through where an underlying exposure >= 0.25% of Tier 1."""
    return underlying_exposure >= p.LEX_LOOK_THROUGH_THRESHOLD * tier1_capital


def look_through_exposure(share_in_tranche: float, tranche_value: float,
                          underlying_nominal: float) -> float:
    """LEX30.48-30.49: pro rata share x min(tranche value, underlying asset nominal)."""
    return share_in_tranche * min(tranche_value, underlying_nominal)


def interdependence_check_required(exposure: float, tier1_capital: float) -> bool:
    """LEX10.18: assess economic interdependence where exposure > 5% of Tier 1."""
    return exposure > p.LEX_ECONOMIC_INTERDEPENDENCE_THRESHOLD * tier1_capital


def large_exposures(exposures: list[LargeExposureInput], tier1_capital: float,
                    reporting_bank_is_gsib: bool) -> list[LargeExposureRow]:
    """Reporting threshold and limit test per counterparty (LEX10.8, LEX20.1-20.4, LEX40.1)."""
    if tier1_capital <= 0:
        raise ValueError("Tier 1 capital must be positive")
    rows: list[LargeExposureRow] = []
    for e in exposures:
        if e.flags.get("intraday_interbank", False):
            rows.append(LargeExposureRow(
                counterparty_id=e.counterparty_id, exposure_value=e.exposure_value,
                limit=float("inf"), limit_pct_of_tier1=float("inf"), reportable=False,
                breach=False, citation="LEX30.35 (intraday interbank, out of scope)"))
            continue
        pct = limit_pct(e.counterparty_is_gsib, reporting_bank_is_gsib)
        reportable = e.exposure_value >= p.LEX_LARGE_EXPOSURE_THRESHOLD * tier1_capital
        if is_sovereign_exempt(e):
            exempt, cite = True, "LEX10.7, LEX30.31 (sovereign exemption); LEX30.33 reporting"
        elif e.flags.get("qccp_clearing_exposure", False):
            exempt, cite = True, "LEX30.54 (QCCP clearing exposure exempt); LEX20.4"
        elif e.is_exempt:
            exempt, cite = True, "Exempt per caller; LEX20.4(3) reporting"
        else:
            exempt = False
            cite = ("LEX20.1, LEX40.1 (15% G-SIB to G-SIB)" if pct == p.LEX_GSIB_TO_GSIB_LIMIT
                    else "LEX20.1 (25% of Tier 1)")
        limit = pct * tier1_capital
        rows.append(LargeExposureRow(
            counterparty_id=e.counterparty_id, exposure_value=e.exposure_value,
            limit=float("inf") if exempt else limit,
            limit_pct_of_tier1=float("inf") if exempt else pct,
            reportable=reportable,
            breach=(not exempt) and e.exposure_value > limit,
            citation=f"{cite}; LEX10.8 reporting threshold 10%"))
    return rows
