"""Minimum CARs, buffers and the leverage ratio under MAS Notice 637 Part IV.

Singapore's D-SIB treatment is built into the minimum ratios: a bank
designated by MAS as a D-SIB must maintain CET1 / Tier 1 / Total CARs of
6.5% / 8% / 10% (Table 4-1), two percentage points above the 4.5% / 6% / 8%
that apply to other banks (Table 4-2). The Notice does not set a separate
D-SIB higher-loss-absorbency buffer rate; the disclosure templates (Annex
11A rows 64 and 67) refer to "G-SIB and/or D-SIB buffer requirement(s)",
which this module accepts as an input rate (default 0%).

Buffers: capital conservation buffer 2.5% CET1 (para 4.1.7); countercyclical
buffer 0-2.5% as the RWA-weighted average of jurisdictional rates (paras
4.1.17-4.1.19; a Singapore rate may exceed 2.5%, para 4.1.30). No systemic
risk buffer and no stress capital buffer exist in the Notice. Leverage ratio
minimum 3% (para 4.2.2).

References:
    - MAS Notice 637 paras 4.1.5-4.1.32, 4.2.2, Tables 4-1 to 4-7 (pp. 4-1 to 4-12)
    - MAS Notice 637 Annex 11A rows 64-67 (p. 11-148), Annex 11D row 27 (p. 11-164)
    - Basel Framework RBC20.1-20.2, RBC30, RBC40, LEV30 (comparison)
"""

from __future__ import annotations

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.sg import params as p


def minimum_ratios(is_dsib: bool) -> tuple[float, float, float]:
    """(CET1, Tier 1, Total) minimum CARs.

    Reference: MAS Notice 637 paras 4.1.5-4.1.6, Tables 4-1 and 4-2 (pp. 4-1, 4-2).
    """
    if is_dsib:
        return p.DSIB_CET1_MIN, p.DSIB_T1_MIN, p.DSIB_TOTAL_MIN
    return p.NON_DSIB_CET1_MIN, p.NON_DSIB_T1_MIN, p.NON_DSIB_TOTAL_MIN


def countercyclical_buffer(
    exposures_by_jurisdiction: dict[str, tuple[float, float, bool]],
) -> float:
    """Bank-specific CCyB: RWA-weighted average of jurisdictional rates.

    Reference: MAS Notice 637 paras 4.1.18-4.1.21 (pp. 4-6 to 4-8). Each value is
    (private-sector credit RWA, jurisdiction rate, is_relevant_jurisdiction). Weights use all
    private-sector RWA; a zero weight applies to non-relevant jurisdictions (4.1.21(b)); foreign
    rates are capped at 2.5% (4.1.18(a)(ii)) -- Singapore ("SG") is not capped (4.1.30).
    """
    total = sum(rwa for rwa, _, _ in exposures_by_jurisdiction.values())
    if total <= 0.0:
        return 0.0
    acc = 0.0
    for code, (rwa, rate, relevant) in exposures_by_jurisdiction.items():
        if not relevant:
            continue
        applied = rate if code.upper() == "SG" else min(rate, p.CCYB_MAX)
        acc += (rwa / total) * applied
    return acc


def capital_conservation_ratio(cet1_car: float, cet1_minimum: float, buffer: float) -> float:
    """Minimum capital conservation ratio (share of earnings to be retained).

    Reference: MAS Notice 637 paras 4.1.10-4.1.12, 4.1.25, Tables 4-3, 4-4, 4-5 (pp. 4-4, 4-9).
    Quartile boundaries are inclusive at the top (e.g. D-SIB first quartile 6.5% - 7.125%).
    """
    if buffer <= 0.0:
        return p.CONSERVATION_RATIOS[-1]
    for i, ratio in enumerate(p.CONSERVATION_RATIOS[:-1]):
        if cet1_car <= cet1_minimum + buffer * (i + 1) / 4.0 + 1e-12:
            return ratio
    return p.CONSERVATION_RATIOS[-1]


def capital_requirements(
    is_dsib: bool = True,
    systemic_buffer_rate: float = 0.0,
    countercyclical_rate: float = 0.0,
) -> CapitalRequirements:
    """Minimum ratios and buffer stack for a Singapore-incorporated bank.

    Reference: MAS Notice 637 paras 4.1.5-4.1.7, 4.1.17, 4.2.2 (pp. 4-1 to 4-12).

    Args:
        is_dsib: bank is designated by MAS as a D-SIB (Table 4-1) -- default True.
        systemic_buffer_rate: any G-SIB / D-SIB buffer rate MAS imposes (Annex 11A row 64(iv));
            the Notice sets none, so the default is 0.
        countercyclical_rate: the bank-specific CCyB (see :func:`countercyclical_buffer`).
    """
    if countercyclical_rate < 0.0 or systemic_buffer_rate < 0.0:
        raise ValueError("buffer rates must be non-negative")
    cet1, t1, total = minimum_ratios(is_dsib)
    table = "Table 4-1 (D-SIB)" if is_dsib else "Table 4-2 (non-D-SIB)"
    return CapitalRequirements(
        jurisdiction=Jurisdiction.SG,
        cet1_minimum=cet1,
        tier1_minimum=t1,
        total_capital_minimum=total,
        conservation_buffer=p.CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=systemic_buffer_rate,
        systemic_risk_buffer=0.0,
        stress_buffer=0.0,
        leverage_minimum=p.LEVERAGE_MINIMUM,
        leverage_buffer=p.DSIB_LEVERAGE_BUFFER if is_dsib else 0.0,
        citations={
            "minimums": f"MAS 637 para {'4.1.5' if is_dsib else '4.1.6'}, {table}",
            "conservation_buffer": "MAS 637 para 4.1.7 (2.5% CET1)",
            "countercyclical_buffer": "MAS 637 paras 4.1.17-4.1.32 (0-2.5%, weighted average)",
            "systemic_buffer": "No D-SIB HLA buffer rate in MAS 637; D-SIB loading is in Table 4-1 "
            "minimums (+2pp); input rate per Annex 11A row 64(iv)",
            "systemic_risk_buffer": "not in MAS 637",
            "stress_buffer": "not in MAS 637",
            "leverage_minimum": "MAS 637 para 4.2.2 (3%)",
            "leverage_buffer": "Annex 11D row 27 references a D-SIB leverage buffer; rate not set "
            "in the Notice (TODO: VERIFY)",
        },
    )
