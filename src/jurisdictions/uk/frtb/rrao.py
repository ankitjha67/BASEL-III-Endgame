"""UK residual risk add-on -- PRA Market Risk: Advanced Standardised Approach Part, Section 4.

Article 325u (p. 333-335): the add-on is the sum of gross notional amounts of instruments
bearing residual risks multiplied by 1% (exotic underlyings, Art 325u(2)(a), (5)) or 0.1%
(other residual risks, Art 325u(2)(b), (6)).

Exemptions:

* Art 325u(4) (p. 334): the 0.1% 'other residual risk' charge does not apply to an instrument
  listed on a recognised exchange or eligible for central clearing -- flags ``listed`` or
  ``ccp_eligible``;
* Art 325u(4a) (p. 334): no add-on (exotic or other) for an instrument that perfectly offsets
  the market risk of another trading-book position with a third party -- flag ``back_to_back``
  (for a notional mismatch, pass the remaining net notional as ``gross_notional``);
* ``RRAOPositionInput.exempt`` -- any other exclusion established by the caller, e.g. an
  Art 325u(3A) PRA permission or the Art 325u(7) items that do not by themselves create
  residual risk (cheapest-to-deliver, smile, index correlation, dividend risk).
"""

from __future__ import annotations

from src.jurisdictions.frtb_base import RRAOCategory, RRAOPositionInput
from src.jurisdictions.uk.frtb import params as p


def rrao_risk_weight(pos: RRAOPositionInput) -> float:
    """1% exotic / 0.1% other residual risk (Art 325u(3), p. 333)."""
    return p.RRAO_EXOTIC_RW if pos.category is RRAOCategory.EXOTIC else p.RRAO_OTHER_RW


def is_exempt(pos: RRAOPositionInput) -> bool:
    """Exempt from the add-on (Art 325u(4), (4a), p. 334)."""
    if pos.exempt or pos.flags.get("back_to_back"):
        return True
    listed_or_cleared = bool(pos.flags.get("listed") or pos.flags.get("ccp_eligible"))
    return pos.category is RRAOCategory.OTHER_RESIDUAL and listed_or_cleared


def rrao_capital(positions: list[RRAOPositionInput]) -> float:
    """Sum of gross notional x RW over non-exempt instruments (Art 325u(3), p. 333)."""
    return sum(
        q.gross_notional * rrao_risk_weight(q) for q in positions if not is_exempt(q)
    )
