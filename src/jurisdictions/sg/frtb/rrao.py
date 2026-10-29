"""Residual risk add-on under MAS Notice 637 paras 8.2.210-8.2.218.

RRAO = sum over in-scope instruments of gross notional x risk weight (para 8.2.217): 1.0% for an
exotic underlying (para 8.2.210(a)), 0.1% for the para 8.2.210(b)-(f) instruments (other
residual risks; behavioural prepayment options; options without maturity; options without
strike or barrier; options with multiple strikes or barriers).

Exclusions:
    - back-to-back transactions (para 8.2.214), flag ``back_to_back``;
    - listed and/or CCP-eligible instruments, "despite paragraph 8.2.210(b)" (para 8.2.215),
      flag ``listed_or_ccp_eligible``. The exclusion does not apply to exotic underlyings and,
      per its wording, not to instruments in scope only through para 8.2.210(c)-(f) (flag
      ``rrao_8_2_210_c_to_f``).
``exempt`` = True is honoured as an exclusion the caller has already established.
Para 8.2.218: the Authority may impose more under Part X (Pillar 2) -- not modelled.
"""

from __future__ import annotations

from src.jurisdictions.frtb_base import RRAOCategory, RRAOPositionInput
from src.jurisdictions.sg.frtb import params as p


def is_excluded(pos: RRAOPositionInput) -> bool:
    """Paras 8.2.214-8.2.215."""
    if pos.exempt or pos.flags.get(p.RRAO_FLAG_BACK_TO_BACK, False):
        return True
    return (pos.category is RRAOCategory.OTHER_RESIDUAL
            and pos.flags.get(p.RRAO_FLAG_LISTED_OR_CCP, False)
            and not pos.flags.get(p.RRAO_FLAG_210_C_TO_F, False))


def rrao_weight(category: RRAOCategory) -> float:
    """Para 8.2.217(a)-(b)."""
    return p.RRAO_EXOTIC_RW if category is RRAOCategory.EXOTIC else p.RRAO_OTHER_RW


def rrao_capital(positions: list[RRAOPositionInput]) -> float:
    """Para 8.2.217: sum of gross notional x risk weight over in-scope instruments."""
    return sum(x.gross_notional * rrao_weight(x.category)
               for x in positions if not is_excluded(x))


__all__ = ["is_excluded", "rrao_capital", "rrao_weight"]
