"""BCBS output floor (RBC20.4(2), RBC20.11-20.13, RBC90.1-90.2).

    RWA = max(pre-floor RWA, floor_factor x standardised RWA)

The floor factor is 72.5% fully phased-in (RBC20.4(2)), with the RBC90.1
transitional calibration 50% (2023) rising to 72.5% (from 1 January 2028).
At national discretion (RBC90.2) the floor-driven increase may be capped at
25% of pre-floor RWA during the phase-in period. BCBS d424 (Output floor
para 9) carried the same calibration one year earlier (2022-2027); the
Framework (revised implementation date of 27 March 2020) governs.

References:
    - Basel Framework RBC20.4, RBC20.11-20.13 (pp. 139-143)
    - Basel Framework RBC90.1-90.2 (p. 177)
    - BCBS d424, Output floor paras 4, 9, 10
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, OutputFloorResult
from src.jurisdictions.bcbs import params as p
from src.jurisdictions.bcbs.params import BCBSOptions


def floor_factor(year: int) -> float:
    """RBC90.1 Table 1 calibration for a reporting year (0.0 before 2023)."""
    if year < p.OUTPUT_FLOOR_START_YEAR:
        return 0.0
    last = max(p.OUTPUT_FLOOR_SCHEDULE)
    return p.OUTPUT_FLOOR_SCHEDULE[min(year, last)]


def is_phase_in_year(year: int) -> bool:
    """True for 2023-2027, the years before the 72.5% calibration (RBC90.1-90.2)."""
    return p.OUTPUT_FLOOR_START_YEAR <= year < max(p.OUTPUT_FLOOR_SCHEDULE)


def output_floor(pre_floor_rwa: float, standardised_rwa: float, year: int,
                 opts: BCBSOptions) -> OutputFloorResult:
    """Apply the output floor (RBC20.4(2)) with RBC90 transitional arrangements."""
    factor = floor_factor(year)
    notes: list[str] = []
    if factor == 0.0:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.BCBS, applies=False, floor_factor=0.0,
            pre_floor_rwa=pre_floor_rwa, standardised_rwa=standardised_rwa,
            floored_rwa=pre_floor_rwa, add_on=0.0, citation="RBC90.1",
            notes=[f"Output floor not yet implemented in {year} (from 1 January 2023)"])
    floored = max(pre_floor_rwa, factor * standardised_rwa)
    citation = "RBC20.4(2) / RBC90.1 Table 1"
    if opts.output_floor_transitional_cap and is_phase_in_year(year):
        cap = pre_floor_rwa * (1.0 + p.OUTPUT_FLOOR_TRANSITIONAL_CAP)
        if floored > cap:
            notes.append("RBC90.2 transitional cap: increase limited to 25% of pre-floor RWA")
            floored = cap
        citation += " / RBC90.2"
    return OutputFloorResult(
        jurisdiction=Jurisdiction.BCBS, applies=True, floor_factor=factor,
        pre_floor_rwa=pre_floor_rwa, standardised_rwa=standardised_rwa,
        floored_rwa=floored, add_on=floored - pre_floor_rwa, citation=citation, notes=notes)
