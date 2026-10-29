"""EU residual risk add-on -- CRR Article 325u as amended by CRR3 point (164).

    RRAO = Sum gross notional x RW,  RW = 1,0 % (exotic underlying, 325u(2)(a), (3)(a))
                                         0,1 % (other residual risks, 325u(2)(b), (3)(b))

Exemptions (Article 325u(4)): instrument listed on a recognised exchange; eligible for central
clearing under Regulation (EU) No 648/2012; perfectly offsetting another trading-book position
(both legs exempt). CRR3 adds Article 325u(4a): until 31 December 2032, with permission,
instruments that solely hedge the market risk of RRAO positions and bear the same type of
residual risk are exempt.

Documented position ``flags`` (default False): ``listed``, ``ccp_eligible``,
``perfect_offset``, ``eu_rrao_hedge_derogation`` (Article 325u(4a)), ``actp_hedge`` (ACTP hedges
of Article 325(8) are not 'other residual risk' instruments, 325u(2)(b)(ii)).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.jurisdictions.eu.frtb import params as p
from src.jurisdictions.frtb_base import RRAOCategory, RRAOPositionInput

EXEMPTION_FLAGS: tuple[str, ...] = ("listed", "ccp_eligible", "perfect_offset", "actp_hedge")
"""Article 325u(4)(a)-(c) and 325u(2)(b)(ii)."""


@dataclass
class RRAOResult:
    """RRAO with the per-position contributions."""

    total: float = 0.0
    by_position: dict[str, float] = field(default_factory=dict)
    exempted: list[str] = field(default_factory=list)


def rrao_risk_weight(category: RRAOCategory) -> float:
    """Article 325u(3)(a)-(b)."""
    return p.RRAO_RW_EXOTIC if category == RRAOCategory.EXOTIC else p.RRAO_RW_OTHER


def is_exempt(pos: RRAOPositionInput, as_of: date) -> bool:
    """Article 325u(4) exemptions and the CRR3 Article 325u(4a) hedge derogation."""
    if pos.exempt or any(pos.flags.get(k, False) for k in EXEMPTION_FLAGS):
        return True
    return bool(pos.flags.get("eu_rrao_hedge_derogation", False)) and (
        as_of <= p.RRAO_HEDGE_DEROGATION_END
    )


def rrao(positions: list[RRAOPositionInput], as_of: date) -> RRAOResult:
    """Sum of gross notional x risk weight over non-exempt instruments (Article 325u(3))."""
    res = RRAOResult()
    for pos in positions:
        if is_exempt(pos, as_of):
            res.exempted.append(pos.position_id)
            res.by_position[pos.position_id] = 0.0
            continue
        charge = pos.gross_notional * rrao_risk_weight(pos.category)
        res.by_position[pos.position_id] = charge
        res.total += charge
    return res
