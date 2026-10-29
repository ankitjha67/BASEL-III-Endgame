"""BCBS minimum capital ratios and buffer stack (RBC20, RBC30, RBC40, LEV20, LEV40).

- Minimums: CET1 4.5%, Tier 1 6%, Total 8% (RBC20.1)
- Capital conservation buffer 2.5% CET1 (RBC30.2)
- Countercyclical buffer 0-2.5% (RBC30.9-30.13), a weighted average of
  jurisdictional rates; national rates above 2.5% are not reciprocated
- G-SIB higher loss absorbency by bucket 1.0/1.5/2.0/2.5/3.5% (RBC40.4
  Table 1; SCO40.21 130 bp cutoff, 100 bp buckets; RBC40.5 new buckets +1%)
- D-SIB HLA is national; G-SIB and D-SIB HLA are not additive -- the higher
  applies (RBC40.8(3), RBC40.18-40.19)
- Leverage ratio minimum 3% (LEV20.7); G-SIB leverage buffer = 50% of the
  HLA (LEV40.2), met with Tier 1
- The Basel Framework has no systemic risk buffer or stress capital buffer.

References:
    - Basel Framework RBC20.1 (p. 138), RBC30.2-30.18 (pp. 156-167)
    - Basel Framework RBC40.1-40.23 (pp. 169-175), SCO40.19-40.22 (pp. 20-21)
    - Basel Framework LEV20.7 (p. 788), LEV40.1-40.5 (pp. 811-813)
"""

from __future__ import annotations

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.bcbs import params as p


def gsib_bucket_from_score(score_bps: float) -> int:
    """G-SIB bucket for a score (SCO40.21 / RBC40.4): 0 below the 130 bp cutoff.

    Buckets are 100 bp wide (130-229 = 1, ..., 530-629 = 5); scores above
    the top populated range create new buckets of the same width (RBC40.5).
    """
    if score_bps < p.GSIB_CUTOFF_SCORE_BPS:
        return 0
    return int((score_bps - p.GSIB_CUTOFF_SCORE_BPS) // p.GSIB_BUCKET_WIDTH_BPS) + 1


def gsib_hla(bucket: int) -> float:
    """Higher loss-absorbency requirement for a bucket (RBC40.4 Table 1, RBC40.5)."""
    if bucket <= 0:
        return 0.0
    top = max(p.GSIB_HLA_BY_BUCKET)
    if bucket <= top:
        return p.GSIB_HLA_BY_BUCKET[bucket]
    return p.GSIB_HLA_BY_BUCKET[top] + p.GSIB_NEW_BUCKET_INCREMENT * (bucket - top)


def resolve_systemic_buffer(systemic_bucket_or_rate: float) -> tuple[float, str]:
    """Interpret the protocol argument: an integer >= 1 is a G-SIB bucket, else a rate.

    Values in [0, 1) are taken as a decimal HLA rate (e.g. a D-SIB rate or
    the higher of G-SIB and D-SIB, RBC40.19).
    """
    x = systemic_bucket_or_rate
    if x >= 1.0 and float(x).is_integer():
        return gsib_hla(int(x)), f"RBC40.4 Table 1 (bucket {int(x)})"
    if x < 0 or x >= 1.0:
        raise ValueError(f"systemic buffer must be a bucket (1, 2, ...) or a rate in [0, 1): {x}")
    return x, "RBC40.4 / RBC40.8 (rate supplied)"


def conservation_ratio(cet1_ratio: float, buffer_requirement: float,
                       cet1_minimum: float = p.CET1_MINIMUM) -> float:
    """Minimum capital conservation ratio (share of earnings) by buffer quartile.

    RBC30.4 / RBC30.17: 100% / 80% / 60% / 40% within the 1st-4th quartiles
    of the combined buffer above the 4.5% CET1 minimum; 0% above the buffer.
    """
    if buffer_requirement <= 0 or cet1_ratio > cet1_minimum + buffer_requirement:
        return p.CONSERVATION_RATIOS_BY_QUARTILE[-1]
    quartile = buffer_requirement / 4.0
    for i in range(4):
        if cet1_ratio <= cet1_minimum + quartile * (i + 1) + 1e-12:
            return p.CONSERVATION_RATIOS_BY_QUARTILE[i]
    return p.CONSERVATION_RATIOS_BY_QUARTILE[-1]


def capital_requirements(systemic_bucket_or_rate: float = 0.0,
                         countercyclical_rate: float = 0.0,
                         stress_buffer: float = 0.0) -> CapitalRequirements:
    """Minimum ratios and buffer stack (RBC20.1, RBC30, RBC40, LEV20.7, LEV40.2).

    ``stress_buffer`` is accepted for protocol conformance; the Basel
    Framework has no stress buffer, so a non-zero value is carried as a
    national add-on.
    """
    if countercyclical_rate < 0:
        raise ValueError("countercyclical rate cannot be negative (RBC30.12)")
    hla, hla_cite = resolve_systemic_buffer(systemic_bucket_or_rate)
    return CapitalRequirements(
        jurisdiction=Jurisdiction.BCBS,
        cet1_minimum=p.CET1_MINIMUM,
        tier1_minimum=p.TIER1_MINIMUM,
        total_capital_minimum=p.TOTAL_CAPITAL_MINIMUM,
        conservation_buffer=p.CAPITAL_CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=hla,
        systemic_risk_buffer=0.0,
        stress_buffer=stress_buffer,
        leverage_minimum=p.LEVERAGE_MINIMUM,
        leverage_buffer=p.GSIB_LEVERAGE_BUFFER_SHARE * hla,
        citations={
            "cet1_minimum": "RBC20.1(1)",
            "tier1_minimum": "RBC20.1(2)",
            "total_capital_minimum": "RBC20.1(3)",
            "conservation_buffer": "RBC30.2",
            "countercyclical_buffer": "RBC30.9-30.13 (0-2.5%, reciprocity cap 2.5%)",
            "systemic_buffer": hla_cite,
            "stress_buffer": "Not in the Basel Framework (national add-on if non-zero)",
            "leverage_minimum": "LEV20.7",
            "leverage_buffer": "LEV40.2 (50% of G-SIB HLA)",
        },
    )
