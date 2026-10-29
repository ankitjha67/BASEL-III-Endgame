"""OSFI CAR 2026 Chapter 9 -- Residual risk add-on (RRAO).

CAR 9.5.4 ¶259-266 [Basel Framework MAR23]: RRAO = Σ gross notional × RW, with RW 1.0% for
instruments with an exotic underlying (¶261) and 0.1% for instruments bearing other residual
risks (¶262), ¶266 [MAR23.8].

Exclusions (¶265 [MAR23.7]):

* back-to-back transactions exactly matching a third-party transaction are excluded from the RRAO
  (``flags['back_to_back']``, also a TRS with an equal and opposite exposure in the same TRS);
* "Any instrument that is listed and/or eligible for central clearing must be excluded from the
  RRAO for other residual risks"; but "Any instrument that is listed and/or eligible for central
  clearing with an exotic underlying must be included" (``flags['listed_or_cc_eligible']``).

``RRAOPositionInput.exempt = True`` is honoured as a caller-asserted exclusion, except that it
cannot exempt an exotic-underlying instrument whose only ground is listing / clearing
eligibility (``flags['listed_or_cc_eligible']`` without ``flags['back_to_back']``).
"""

from __future__ import annotations

from src.jurisdictions.ca.frtb import params as p
from src.jurisdictions.frtb_base import RRAOCategory, RRAOPositionInput


def rrao_risk_weight(category: RRAOCategory) -> float:
    """RRAO risk weight (CAR ¶266(3)-(4) [MAR23.8])."""
    return p.RRAO_EXOTIC_RW if category == RRAOCategory.EXOTIC else p.RRAO_OTHER_RW


def is_excluded(pos: RRAOPositionInput) -> bool:
    """Apply the CAR ¶265 exclusions [MAR23.7]."""
    back_to_back = pos.flags.get("back_to_back", False)
    listed = pos.flags.get("listed_or_cc_eligible", False)
    if back_to_back:
        return True
    if pos.category == RRAOCategory.EXOTIC:
        if listed:
            return False  # listed / CCP-eligible exotics must be included (¶265)
        return pos.exempt
    return listed or pos.exempt


def rrao_capital(positions: list[RRAOPositionInput]) -> float:
    """Σ gross notional × RW over non-excluded positions (CAR ¶266 [MAR23.8])."""
    return sum(
        pos.gross_notional * rrao_risk_weight(pos.category)
        for pos in positions
        if not is_excluded(pos)
    )
