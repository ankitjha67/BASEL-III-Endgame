"""Output floor under MAS Notice 637 Part V.

Output floor = output floor calibration x (credit + market + operational RWA
calculated using only the standardised approaches of Table 5-1) (para 5.1.1).
The CAR denominator is the higher of nominated-approach RWA and the output
floor (para 4.1.4). The calibration follows Table 5-3 (50% from 1 July 2024
rising to 72.5% from 1 January 2029), or a higher percentage (max 100%) set
by MAS for a bank (para 5.1.6). MAS does not adopt the BCBS RBC90.2 transitional
25% cap on the floor-driven RWA increase.

References:
    - MAS Notice 637 paras 4.1.4, 5.1.1-5.1.6, Tables 5-1 and 5-3 (pp. 4-1, 5-1 to 5-4)
    - Basel Framework RBC20.4, RBC90.1-90.2 (comparison)
"""

from __future__ import annotations

from datetime import date

from src.jurisdictions.base import Jurisdiction, OutputFloorResult
from src.jurisdictions.sg import params as p


def floor_calibration(on: date) -> float:
    """Output floor calibration in force on a date (0.0 before 1 July 2024).

    Reference: MAS Notice 637 para 5.1.6, Table 5-3 (p. 5-4).
    """
    factor = 0.0
    for start, value in p.OUTPUT_FLOOR_SCHEDULE:
        if on >= start:
            factor = value
    return factor


def floor_calibration_for_year(year: int) -> float:
    """Calibration for a reporting year, read at 31 December of that year.

    Reference: MAS Notice 637 Table 5-3 (p. 5-4). 2024 returns 50% (applies from 1 July 2024).
    """
    return floor_calibration(date(year, 12, 31))


def output_floor(
    pre_floor_rwa: float,
    standardised_rwa: float,
    year: int,
    mas_specified_calibration: float | None = None,
) -> OutputFloorResult:
    """Apply the MAS output floor for a reporting year.

    Reference: MAS Notice 637 paras 4.1.4, 5.1.1, 5.1.6 (pp. 4-1, 5-1, 5-4).

    Args:
        pre_floor_rwa: RWA under the nominated approaches.
        standardised_rwa: base of the floor (RWA using only the Table 5-1 standardised approaches).
        year: reporting year.
        mas_specified_calibration: a bank-specific higher percentage set by MAS (para 5.1.6);
            ignored if lower than Table 5-3, capped at 100%.
    """
    factor = floor_calibration_for_year(year)
    notes: list[str] = []
    if mas_specified_calibration is not None and mas_specified_calibration > factor:
        factor = min(mas_specified_calibration, p.OUTPUT_FLOOR_MAX)
        notes.append("MAS-specified higher calibration (para 5.1.6)")
    if factor == 0.0:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.SG,
            applies=False,
            floor_factor=0.0,
            pre_floor_rwa=pre_floor_rwa,
            standardised_rwa=standardised_rwa,
            floored_rwa=pre_floor_rwa,
            add_on=0.0,
            citation="MAS 637 Table 5-3: output floor applies from 1 July 2024",
            notes=["reporting year precedes the output floor"],
        )
    floor = factor * standardised_rwa
    floored = max(pre_floor_rwa, floor)
    if year == 2024:
        notes.append("2024 calibration of 50% applies only from 1 July 2024")
    notes.append("no transitional cap on the floor add-on (BCBS RBC90.2 not adopted)")
    return OutputFloorResult(
        jurisdiction=Jurisdiction.SG,
        applies=True,
        floor_factor=factor,
        pre_floor_rwa=pre_floor_rwa,
        standardised_rwa=standardised_rwa,
        floored_rwa=floored,
        add_on=floored - pre_floor_rwa,
        citation="MAS 637 paras 4.1.4, 5.1.1, 5.1.6, Table 5-3",
        notes=notes,
    )
