"""UK PRA Basel 3.1 output floor -- Required Level of Own Funds (CRR) Part Article 92.

    TREA = max{U-TREA; x * S-TREA + OF-ADJ}                      (Art 92(2A)(a))
    OF-ADJ = 12.5 * (IRB T2 - IRB CET1 - GCRA + SA T2)
    GCRA <= 1.25% of the RWEA calculated under paragraph 3A
    x = 72.5%; transitionally x may be 60% (2027), 65% (2028), 70% (2029) (Art 92(5))

UK-specific mechanics transcribed from Article 92 (p. 12-16):

* Scope (Art 92(2A)): the floor binds only (i) on an individual basis for a
  stand-alone institution in the UK and a ring-fenced body that is not in a
  sub-consolidation group, (ii) on a sub-consolidated basis for a ring-fenced
  body in a sub-consolidation group, and (iii) on a consolidated basis for a CRR
  consolidation entity that is not an international subsidiary. Other entities
  (non-RFB sub-consolidation, individual entities in groups, international
  subsidiaries under the rule 5.1 permission) use U-TREA.
* OF-ADJ reconciles the different treatment of provisions under IRB and SA.
* There is no transitional cap on the floor add-on (contrast BCBS RBC90.2,
  which allows a 25% cap during phase-in): Article 92 contains none.

References:
    - PRA Rulebook Required Level of Own Funds (CRR) Part, Article 92(2A)-(5), rule 5.1
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import Jurisdiction, OutputFloorResult
from src.jurisdictions.uk import params as p

ROF_PART: Final[str] = "PRA Rulebook Required Level of Own Funds (CRR) Part"


def floor_factor(year: int, use_transitional: bool = True) -> float:
    """Floor factor x for a reporting year -- Art 92(2A)(a) and 92(5)(a)-(c) (p. 13, 15).

    ``use_transitional`` reflects that an institution 'may apply' the Art 92(5)
    factors; if False the full 72.5% applies from 2027. Before 1 January 2027
    the PRA output floor is not in force (returns 0.0).
    """
    if year < p.OUTPUT_FLOOR_FIRST_YEAR:
        return 0.0
    if use_transitional and year in p.OUTPUT_FLOOR_TRANSITIONAL:
        return p.OUTPUT_FLOOR_TRANSITIONAL[year]
    return p.OUTPUT_FLOOR_FACTOR


def of_adj(
    irb_t2: float = 0.0,
    irb_cet1: float = 0.0,
    gcra: float = 0.0,
    sa_t2: float = 0.0,
    s_trea_credit_rwea: float | None = None,
) -> float:
    """OF-ADJ = 12.5 x (IRB T2 - IRB CET1 - GCRA + SA T2) -- Art 92(2A)(a) (p. 13).

    GCRA is limited to 1.25% of the RWEA under paragraph 3A when
    ``s_trea_credit_rwea`` is supplied (definition of GCRA, p. 13).
    """
    if s_trea_credit_rwea is not None:
        gcra = min(gcra, p.OUTPUT_FLOOR_GCRA_CAP * s_trea_credit_rwea)
    return p.OWN_FUNDS_TO_RWA_MULTIPLIER * (irb_t2 - irb_cet1 - gcra + sa_t2)


def apply_output_floor(
    pre_floor_rwa: float,
    standardised_rwa: float,
    year: int,
    *,
    in_scope: bool = True,
    use_transitional: bool = True,
    adjustment: float = 0.0,
) -> OutputFloorResult:
    """TREA = max{U-TREA; x * S-TREA + OF-ADJ} -- Art 92(2A)(a), (b)-(d), (5) (p. 13-15).

    ``pre_floor_rwa`` is U-TREA (Art 92(3)); ``standardised_rwa`` is S-TREA
    (Art 92(3A)); ``adjustment`` is OF-ADJ (see :func:`of_adj`); ``in_scope``
    is False for the entities Art 92(2A)(b)-(d) leave on U-TREA.
    """
    x = floor_factor(year, use_transitional)
    notes: list[str] = []
    if not in_scope:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.UK,
            applies=False,
            floor_factor=0.0,
            pre_floor_rwa=pre_floor_rwa,
            standardised_rwa=standardised_rwa,
            floored_rwa=pre_floor_rwa,
            add_on=0.0,
            citation=f"{ROF_PART} Art 92(2A)(b)-(d): TREA = U-TREA (entity outside floor scope)",
            notes=[
                "International subsidiary / non-RFB sub-consolidation / "
                "non-stand-alone individual entity."
            ],
        )
    if x == 0.0:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.UK,
            applies=False,
            floor_factor=0.0,
            pre_floor_rwa=pre_floor_rwa,
            standardised_rwa=standardised_rwa,
            floored_rwa=pre_floor_rwa,
            add_on=0.0,
            citation=f"{ROF_PART} Art 92 (in force from 1 January 2027, instrument commencement F)",
            notes=[f"Year {year} precedes the 1 January 2027 commencement."],
        )
    floor = x * standardised_rwa + adjustment
    trea = max(pre_floor_rwa, floor)
    if year in p.OUTPUT_FLOOR_TRANSITIONAL and use_transitional:
        notes.append(f"Transitional x = {x:.1%} (Art 92(5)); no transitional cap in the UK rule.")
    if adjustment:
        notes.append(f"OF-ADJ = {adjustment:,.3f}.")
    cite = f"{ROF_PART} Art 92(2A)(a) TREA = max{{U-TREA; x*S-TREA + OF-ADJ}}"
    if year in p.OUTPUT_FLOOR_TRANSITIONAL and use_transitional:
        cite += f"; Art 92(5)({'abc'[year - 2027]})"
    return OutputFloorResult(
        jurisdiction=Jurisdiction.UK,
        applies=True,
        floor_factor=x,
        pre_floor_rwa=pre_floor_rwa,
        standardised_rwa=standardised_rwa,
        floored_rwa=trea,
        add_on=trea - pre_floor_rwa,
        citation=cite,
        notes=notes,
    )
