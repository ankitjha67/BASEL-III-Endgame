"""UK PRA Basel 3.1 capital requirements and buffer stack.

What the PS1/26 instrument settles (Required Level of Own Funds (CRR) Part
Article 92(1), p. 12): CET1 4.5%, Tier 1 6%, total capital 8% of TREA.

What it does NOT settle -- the buffer rates and the leverage framework sit in
other Parts of the PRA Rulebook (Capital Buffers Part; Leverage Ratio - Capital
Requirements and Buffers Part), which the instrument only cross-references
(Credit Risk: Standardised Approach (CRR) Part Art 121(1A), p. 42) or amends for
the CCyB exposure weighting (Annex AA rule 3.1(2)-(3), p. 491-492). Those
values are placeholders flagged ``TODO: VERIFY`` in :mod:`params`:

* capital conservation buffer -- placeholder 2.5% (BCBS RBC30.2);
* countercyclical buffer -- caller supplies the weighted rate (Annex AA rule 3.1);
* G-SII / O-SII buffer -- caller supplies the firm-specific rate;
* systemic risk buffer -- not modelled (0);
* PRA buffer (Pillar 2B) -- caller may pass it as ``stress_buffer``; it is
  firm-specific and confidential, not part of the published combined buffer;
* leverage minimum -- placeholder 3% (BCBS LEV20); additional leverage ratio
  buffer -- placeholder 50% of the systemic rate (BCBS LEV40.2).

References:
    - PRA Rulebook Required Level of Own Funds (CRR) Part, Article 92(1)
    - PRA Rulebook Capital Buffers Part (amended by Annex AA) -- not reproduced
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.uk import params as p

ROF_PART: Final[str] = "PRA Rulebook Required Level of Own Funds (CRR) Part"


def capital_requirements(
    systemic_rate: float = 0.0,
    countercyclical_rate: float = 0.0,
    pra_buffer: float = 0.0,
) -> CapitalRequirements:
    """Minimum ratios (Art 92(1)) and the buffer stack for a UK firm.

    ``systemic_rate`` is the firm's G-SII or O-SII buffer rate as a decimal
    (e.g. 0.01). The CCyB rate is the exposure-weighted average of applicable
    national rates (Capital Buffers Part rule 3.1(1A)-(3) as amended by Annex AA).

    # TODO: VERIFY -- whether the G-SII and O-SII buffers stack or the higher
    applies is set in the Capital Buffers Part / FPC framework, not in this
    instrument; a single caller-supplied rate is used.
    """
    if systemic_rate < 0.0 or countercyclical_rate < 0.0 or pra_buffer < 0.0:
        raise ValueError("buffer rates must be non-negative")
    if systemic_rate > p.SYSTEMIC_BUFFER_MAXIMUM_PLACEHOLDER:
        raise ValueError(
            "systemic rate above the 3.5% sanity cap (pass a decimal rate, not a bucket)"
        )
    if countercyclical_rate > p.CCYB_MAXIMUM_PLACEHOLDER:
        raise ValueError("CCyB above the 2.5% sanity cap")
    todo = "TODO: VERIFY -- not in PS1/26 Appendix 1; placeholder"
    return CapitalRequirements(
        jurisdiction=Jurisdiction.UK,
        cet1_minimum=p.CET1_MINIMUM,
        tier1_minimum=p.TIER1_MINIMUM,
        total_capital_minimum=p.TOTAL_CAPITAL_MINIMUM,
        conservation_buffer=p.CAPITAL_CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=systemic_rate,
        systemic_risk_buffer=0.0,
        stress_buffer=pra_buffer,
        leverage_minimum=p.LEVERAGE_RATIO_MINIMUM,
        leverage_buffer=p.LEVERAGE_BUFFER_SHARE_OF_SYSTEMIC * systemic_rate,
        citations={
            "cet1_minimum": f"{ROF_PART} Art 92(1)(a)",
            "tier1_minimum": f"{ROF_PART} Art 92(1)(b)",
            "total_capital_minimum": f"{ROF_PART} Art 92(1)(c)",
            "conservation_buffer": f"Capital Buffers Part ({todo} BCBS RBC30.2 2.5%)",
            "countercyclical_buffer": (
                "Capital Buffers Part rule 3.1 as amended by PS1/26 Annex AA (rate supplied)"
            ),
            "systemic_buffer": f"Capital Buffers Part G-SII/O-SII ({todo}: caller-supplied rate)",
            "systemic_risk_buffer": f"{todo}: not modelled",
            "stress_buffer": "PRA buffer (Pillar 2B), firm-specific, caller-supplied",
            "leverage_minimum": (
                f"Leverage Ratio - Capital Requirements and Buffers Part 3.1 ({todo} BCBS LEV20 3%)"
            ),
            "leverage_buffer": (
                f"Leverage Ratio - Capital Requirements and Buffers Part 4A.1 "
                f"({todo} BCBS LEV40.2 50% of systemic rate)"
            ),
        },
    )
