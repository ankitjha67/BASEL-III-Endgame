"""OSFI CAR 2026 Chapter 1 -- minimum ratios, buffers, D-SIB surcharge, DSB and leverage.

Stack (s.1.6-1.10): CET1 4.5% / Tier 1 6% / Total 8%; capital conservation buffer 2.5%;
countercyclical buffer 0-2.5% (jurisdictional weighted average); D-SIB surcharge 1% CET1
(the higher of the D-SIB and G-SIB surcharges applies, Annex 1); Domestic Stability Buffer
0-4.0% for D-SIBs -- a Pillar 2 buffer whose level is set in OSFI's semi-annual announcements,
not in CAR, so it is an input here. Leverage: 3% minimum; D-SIBs 3.5% (CAR Ch.4 s.4.1.4,
Ch.1 Table 7), i.e. a 0.5% D-SIB leverage buffer.

References:
    - OSFI CAR 2026 Ch.1 s.1.6-1.10, Tables 2-8, Annexes 1-2
    - OSFI CAR 2026 Ch.4 s.4.1.4 (published Canadian minimums incl. leverage)
    - Basel Framework RBC30, RBC40
"""

from __future__ import annotations

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.ca import params as p


def gsib_surcharge(systemic_bucket_or_rate: float) -> float:
    """G-SIB higher loss absorbency from a bucket (1-5) or a rate (< 1).

    CAR Ch.1 Annex 1 adopts the BCBS G-SIB framework (1%-3.5%); bucket rates per Basel Framework
    RBC40.4 Table 1. A value in (0, 1) is read as the surcharge rate itself.
    """
    v = systemic_bucket_or_rate
    if v <= 0:
        return 0.0
    if v < 1:
        return v
    bucket = int(round(v))
    if bucket not in p.GSIB_HLA_BY_BUCKET or abs(v - bucket) > 1e-9:
        raise ValueError(f"G-SIB bucket must be an integer 1-5, got {v}")
    return p.GSIB_HLA_BY_BUCKET[bucket]


def capital_requirements(
    is_dsib: bool = True,
    systemic_bucket_or_rate: float = 0.0,
    countercyclical_rate: float = 0.0,
    domestic_stability_buffer: float | None = None,
) -> CapitalRequirements:
    """Minimum ratios and buffer stack under CAR 2026 Chapter 1.

    The systemic buffer is max(D-SIB 1%, G-SIB HLA) for D-SIBs (Annex 1: "the higher of the D-SIB
    and G-SIB surcharges will apply"). ``domestic_stability_buffer`` (0-4%, D-SIBs only) is
    reported in ``stress_buffer``; ``None`` -> 0 with a flagged citation, because CAR does not
    state the current level.
    """
    if countercyclical_rate < 0:
        raise ValueError("countercyclical buffer rate cannot be negative")
    gsib = gsib_surcharge(systemic_bucket_or_rate)
    systemic = max(p.DSIB_SURCHARGE, gsib) if is_dsib else gsib
    citations = {
        "minimums": "CAR Ch.1 s.1.6.1 Table 2 (4.5% / 6.0% / 8.0%)",
        "conservation_buffer": "CAR Ch.1 s.1.7.1 Table 4 (2.5%) [RBC 30.2]",
        "countercyclical_buffer": ("CAR Ch.1 s.1.7.2 (0%-2.5% in Canada; weighted average of "
                                   "jurisdictional rates) [RBC 30.8-30.14]"),
        "systemic_buffer": ("CAR Ch.1 s.1.8 (D-SIB 1% CET1) and Annex 1 (higher of D-SIB and "
                            "G-SIB surcharges) [RBC 40]"),
        "leverage": ("CAR Ch.4 s.4.1.4: minimum Leverage Ratio 3%; D-SIBs >= 3.5% (Ch.1 Table 7); "
                     "Leverage Requirements Guideline governs"),
    }
    dsb = 0.0
    if domestic_stability_buffer is None:
        if is_dsib:
            citations["stress_buffer"] = ("CAR Ch.1 s.1.9: DSB range 0-4.0% set by OSFI "
                                          "announcement -- TODO: VERIFY current level "
                                          "(input; 0 used)")
    else:
        if not p.DSB_MINIMUM <= domestic_stability_buffer <= p.DSB_MAXIMUM:
            raise ValueError("Domestic Stability Buffer must be within 0%-4.0% (CAR Ch.1 s.1.9)")
        if not is_dsib and domestic_stability_buffer > 0:
            raise ValueError(
                "the Domestic Stability Buffer applies to D-SIBs only (CAR Ch.1 s.1.9)")
        dsb = domestic_stability_buffer
        citations["stress_buffer"] = ("CAR Ch.1 s.1.9 Domestic Stability Buffer (Pillar 2, CET1; "
                                      "breach -> remediation plan, not automatic constraints)")
    return CapitalRequirements(
        jurisdiction=Jurisdiction.CA,
        cet1_minimum=p.CET1_MINIMUM,
        tier1_minimum=p.TIER1_MINIMUM,
        total_capital_minimum=p.TOTAL_CAPITAL_MINIMUM,
        conservation_buffer=p.CAPITAL_CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=systemic,
        systemic_risk_buffer=0.0,
        stress_buffer=dsb,
        leverage_minimum=p.LEVERAGE_MINIMUM,
        leverage_buffer=p.DSIB_LEVERAGE_BUFFER if is_dsib else 0.0,
        citations=citations,
    )


def target_ratios(is_dsib: bool, dsb: float = 0.0) -> dict[str, float]:
    """Supervisory target ratios (CAR Ch.1 s.1.10 Table 8; footnote 35 example)."""
    if is_dsib:
        return {"CET1": p.DSIB_TARGET_CET1_EX_DSB + dsb, "Tier1": p.DSIB_TARGET_TIER1_EX_DSB + dsb,
                "Total": p.DSIB_TARGET_TOTAL_EX_DSB + dsb}
    return {"CET1": p.SMSB_TARGET_CET1, "Tier1": p.SMSB_TARGET_TIER1, "Total": p.SMSB_TARGET_TOTAL}


def minimum_conservation_ratio(cet1_ratio: float, is_dsib: bool,
                               tier1_leverage_ratio: float | None = None) -> float:
    """Minimum capital conservation ratio (share of earnings retained).

    CAR Ch.1 Table 5 (non-D-SIB CET1 bands to 7.0%) and Table 7 (D-SIB CET1 bands to 8.0% or
    Tier 1 leverage bands to 3.50%); the most constraining applies (footnote 30). Assumes no
    countercyclical buffer (with a CCyB the bands scale by quartile, Table 6).
    """
    ratio = 0.0
    if is_dsib:
        for cet1_ub, _lev, r in p.CONSERVATION_RATIOS_DSIB:
            if cet1_ratio <= cet1_ub:
                ratio = max(ratio, r)
                break
        if tier1_leverage_ratio is not None:
            for _c, lev_ub, r in p.CONSERVATION_RATIOS_DSIB:
                if tier1_leverage_ratio <= lev_ub:
                    ratio = max(ratio, r)
                    break
        return ratio
    for cet1_ub, r in p.CONSERVATION_RATIOS_NON_DSIB:
        if cet1_ratio <= cet1_ub:
            return r
    return 0.0
