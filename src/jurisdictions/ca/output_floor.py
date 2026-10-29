"""OSFI CAR 2026 Chapter 1 s.1.5 -- capital floor (output floor).

The floor adjustment factor is **67.5% "until further notice"** (s.1.5.1, paragraph 33); OSFI
will give at least two years' notice before resuming increases, so CAR 2026 prints no
year-by-year schedule (Basel RBC20.11 reaches 72.5%). Newly approved IRB institutions start at
90% and step down by up to 7.5% per review after four quarters (s.1.4).

Floor mechanics (s.1.5.1-1.5.2): the capital floor is the factor applied to
(standardized RWA - 12.5 x general allowances eligible in Tier 2 under the SA); the adjusted
capital requirement is RWA + 12.5 x provisioning shortfall - 12.5 x excess provisions in Tier 2 -
12.5 x general allowances in Tier 2 for SA portfolios. Any positive difference is added to RWA.
Institutions using only standardized approaches are not subject to the floor.

References:
    - OSFI CAR 2026 Ch.1 s.1.3, 1.4, 1.5
    - Basel Framework RBC20.4, RBC20.11-20.12
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, OutputFloorResult
from src.jurisdictions.ca import params as p


def floor_factor(year: int, institution_factor: float | None = None) -> tuple[float, list[str]]:
    """Floor adjustment factor for a fiscal year (CAR Ch.1 s.1.5.1 paragraph 33, s.1.4).

    67.5% for every year covered by CAR 2026 ("until further notice"). An institution-specific
    factor (e.g. 90% on new IRB approval, s.1.4) overrides it if higher.
    """
    notes: list[str] = []
    factor = p.FLOOR_ADJUSTMENT_FACTOR
    if year < p.CAR_2026_FIRST_YEAR:
        notes.append(f"{year} precedes CAR 2026; earlier-guideline factors are not in this text "
                     "(TODO: VERIFY) -- 67.5% applied")
    if institution_factor is not None:
        if not 0.0 <= institution_factor <= 1.0:
            raise ValueError("institution floor factor must be in [0, 1]")
        if institution_factor > factor:
            notes.append(f"institution-specific floor factor {institution_factor:.1%} (s.1.4)")
            factor = institution_factor
    return factor, notes


def apply_capital_floor(
    pre_floor_rwa: float,
    standardised_rwa: float,
    year: int,
    uses_internal_models: bool = True,
    institution_factor: float | None = None,
    general_allowances_t2_sa: float = 0.0,
    provisioning_shortfall: float = 0.0,
    excess_provisions_t2: float = 0.0,
) -> OutputFloorResult:
    """Apply the OSFI capital floor (CAR Ch.1 s.1.5.1-1.5.2, [RBC 20.11-20.12]).

    capital floor = factor x (SA RWA - 12.5 x GA_T2_SA);
    adjusted requirement = RWA + 12.5 x shortfall - 12.5 x excess - 12.5 x GA_T2_SA;
    add-on = max(0, floor - adjusted). All amounts in $M of RWA (allowances in $M).
    """
    factor, notes = floor_factor(year, institution_factor)
    if not uses_internal_models:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.CA, applies=False, floor_factor=factor,
            pre_floor_rwa=pre_floor_rwa, standardised_rwa=standardised_rwa,
            floored_rwa=pre_floor_rwa, add_on=0.0,
            citation="CAR Ch.1 s.1.5 (standardized-only institutions not subject to the floor)",
            notes=notes,
        )
    ga = p.FLOOR_ALLOWANCE_MULTIPLIER * general_allowances_t2_sa
    floor_amount = factor * (standardised_rwa - ga)
    adjusted = (pre_floor_rwa + p.FLOOR_ALLOWANCE_MULTIPLIER * provisioning_shortfall
                - p.FLOOR_ALLOWANCE_MULTIPLIER * excess_provisions_t2 - ga)
    add_on = max(0.0, floor_amount - adjusted)
    return OutputFloorResult(
        jurisdiction=Jurisdiction.CA, applies=True, floor_factor=factor,
        pre_floor_rwa=pre_floor_rwa, standardised_rwa=standardised_rwa,
        floored_rwa=pre_floor_rwa + add_on, add_on=add_on,
        citation=("CAR Ch.1 s.1.5.1 (paragraph 33: floor adjustment factor 67.5% until further "
                  "notice) and s.1.5.2 [Basel Framework, RBC 20.11-20.12]"),
        notes=notes,
    )
