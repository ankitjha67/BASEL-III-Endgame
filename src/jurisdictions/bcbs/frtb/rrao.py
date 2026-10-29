"""Residual risk add-on (Basel Framework MAR23).

RRAO = sum of gross notionals of instruments bearing residual risk x risk weight
(MAR23.8(2)): 1.0% for an exotic underlying (MAR23.3), 0.1% for other residual risks
(MAR23.4). Exclusions (MAR23.7): back-to-back transactions; listed and/or CCP-eligible
instruments are excluded from the *other residual risk* add-on only -- a listed or
CCP-eligible instrument with an exotic underlying stays in scope.

Documented ``flags`` keys on :class:`RRAOPositionInput`:
    - ``back_to_back``: exactly matched by a third-party transaction (MAR23.7) -> excluded
    - ``listed_or_ccp_eligible``: listed and/or eligible for central clearing (MAR23.7) ->
      excluded when the category is OTHER_RESIDUAL
``exempt`` = True is honoured as an exclusion the caller has already established under MAR23.7.
"""

from __future__ import annotations

from src.jurisdictions.bcbs.frtb import params as p
from src.jurisdictions.frtb_base import RRAOCategory, RRAOPositionInput


def is_excluded(pos: RRAOPositionInput) -> bool:
    """MAR23.7 exclusions."""
    if pos.exempt or pos.flags.get(p.RRAO_FLAG_BACK_TO_BACK, False):
        return True
    return (pos.category is RRAOCategory.OTHER_RESIDUAL
            and pos.flags.get(p.RRAO_FLAG_LISTED_OR_CCP, False))


def rrao_weight(category: RRAOCategory) -> float:
    """MAR23.8(2)(a)-(b)."""
    return p.RRAO_EXOTIC_RW if category is RRAOCategory.EXOTIC else p.RRAO_OTHER_RW


def rrao_capital(positions: list[RRAOPositionInput]) -> float:
    """MAR23.8(2): simple sum of gross notional x risk weight over in-scope positions."""
    return sum(pos.gross_notional * rrao_weight(pos.category)
               for pos in positions if not is_excluded(pos))


__all__ = ["is_excluded", "rrao_capital", "rrao_weight"]
