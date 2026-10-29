"""UK PRA Basel 3.1 capital requirements and buffer stack.

Minimum ratios -- Required Level of Own Funds (CRR) Part Article 92(1) (PS1/26
Appendix 1, p. 12): CET1 4.5%, Tier 1 6%, total capital 8% of TREA.

Buffers -- PRA Rulebook Capital Buffers Part (web text in force 1 January 2027):

* rule 1.2 'combined buffer' = the sum of the capital conservation buffer, the
  countercyclical capital buffer, the G-SII buffer (if any) and the O-SII buffer
  (if any). The G-SII and O-SII buffers therefore stack, and the Part has no
  systemic risk buffer component;
* rule 2.1: capital conservation buffer = 2.5% of the total risk exposure amount;
* rule 3.1(1)-(3): countercyclical buffer = TREA x the institution-specific rate,
  the own-funds-weighted average of FPC-set rates (caller supplies the rate);
* rule 4.3(4)-(7): MDA = distributable profits x a factor of 0 / 0.2 / 0.4 / 0.6
  by quartile of the combined buffer (:func:`mda_factor`).

Not settled by the supplied texts (``TODO: VERIFY`` in :mod:`params`): the G-SII
and O-SII rates (firm-specific; caller-supplied, each capped at a 3.5% sanity
bound), any CCyB maximum (2.5% sanity cap), the leverage ratio minimum and
leverage buffers (Leverage Ratio - Capital Requirements and Buffers Part, not
supplied; placeholders 3% and 50% of the systemic rate). The PRA buffer (Pillar
2B) is firm-specific and confidential and is *not* part of the rule 1.2 combined
buffer; it may be passed as ``pra_buffer`` (carried in ``stress_buffer``, which
the base model adds to the combined buffer).

References:
    - PRA Rulebook Required Level of Own Funds (CRR) Part, Article 92(1)
    - PRA Rulebook Capital Buffers Part, rules 1.2, 2.1, 3.1, 4.3
"""

from __future__ import annotations

from typing import Final

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.uk import params as p

ROF_PART: Final[str] = "PRA Rulebook Required Level of Own Funds (CRR) Part"
CB_PART: Final[str] = "PRA Rulebook Capital Buffers Part"


def capital_requirements(
    systemic_rate: float = 0.0,
    countercyclical_rate: float = 0.0,
    pra_buffer: float = 0.0,
    *,
    osii_rate: float = 0.0,
) -> CapitalRequirements:
    """Minimum ratios (Art 92(1)) and the buffer stack for a UK firm.

    ``systemic_rate`` is the firm's G-SII buffer rate (or, for a firm passing a single
    rate, its O-SII rate) as a decimal; ``osii_rate`` is an O-SII buffer rate held in
    addition -- the two are summed because the combined buffer is 'the sum of' both
    (Capital Buffers Part rule 1.2(c)-(d)). The CCyB rate is the exposure-weighted
    average of applicable rates (rule 3.1(1A)-(3)).
    """
    rates = (systemic_rate, countercyclical_rate, pra_buffer, osii_rate)
    if any(r < 0.0 for r in rates):
        raise ValueError("buffer rates must be non-negative")
    if max(systemic_rate, osii_rate) > p.SYSTEMIC_BUFFER_MAXIMUM_PLACEHOLDER:
        raise ValueError(
            "systemic rate above the 3.5% sanity cap (pass a decimal rate, not a bucket)"
        )
    if countercyclical_rate > p.CCYB_MAXIMUM_PLACEHOLDER:
        raise ValueError("CCyB above the 2.5% sanity cap")
    todo = "TODO: VERIFY -- not in the supplied texts; placeholder"
    return CapitalRequirements(
        jurisdiction=Jurisdiction.UK,
        cet1_minimum=p.CET1_MINIMUM,
        tier1_minimum=p.TIER1_MINIMUM,
        total_capital_minimum=p.TOTAL_CAPITAL_MINIMUM,
        conservation_buffer=p.CAPITAL_CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=systemic_rate + osii_rate,
        systemic_risk_buffer=0.0,
        stress_buffer=pra_buffer,
        leverage_minimum=p.LEVERAGE_RATIO_MINIMUM,
        leverage_buffer=p.LEVERAGE_BUFFER_SHARE_OF_SYSTEMIC * systemic_rate,
        citations={
            "cet1_minimum": f"{ROF_PART} Art 92(1)(a)",
            "tier1_minimum": f"{ROF_PART} Art 92(1)(b)",
            "total_capital_minimum": f"{ROF_PART} Art 92(1)(c)",
            "conservation_buffer": f"{CB_PART} rule 2.1 (2.5% of TREA)",
            "countercyclical_buffer": (
                f"{CB_PART} rule 3.1(1)-(3) (institution-specific weighted rate, supplied)"
            ),
            "systemic_buffer": (
                f"{CB_PART} rule 1.2 'combined buffer' (c)-(d): G-SII + O-SII buffers summed "
                f"(rates firm-specific, caller-supplied; {todo} 3.5% sanity cap)"
            ),
            "systemic_risk_buffer": f"{CB_PART} rule 1.2: no systemic risk buffer component",
            "stress_buffer": (
                "PRA buffer (Pillar 2B), firm-specific, caller-supplied; outside the rule 1.2 "
                "combined buffer"
            ),
            "leverage_minimum": (
                f"Leverage Ratio - Capital Requirements and Buffers Part 3.1 ({todo} BCBS LEV20 3%)"
            ),
            "leverage_buffer": (
                f"Leverage Ratio - Capital Requirements and Buffers Part 4A.1 "
                f"({todo} BCBS LEV40.2 50% of systemic rate)"
            ),
        },
    )


def mda_factor(cet1_above_requirements: float, combined_buffer: float) -> float:
    """MDA factor -- Capital Buffers Part rule 4.3(6)-(7).

    ``cet1_above_requirements`` is CET1 not used to meet Pillar 1 or Pillar 2A, and
    ``combined_buffer`` the combined buffer, both as amounts (or both as ratios). Quartile
    n spans [CB/4 x (n - 1), CB/4 x n]; factor 0 / 0.2 / 0.4 / 0.6 for quartiles 1-4. A firm
    meeting the combined buffer is not restricted (returns 1.0).
    """
    if combined_buffer <= 0.0 or cet1_above_requirements >= combined_buffer:
        return 1.0
    quarter = combined_buffer / 4.0
    for n, factor in enumerate(p.MDA_QUARTILE_FACTORS, start=1):
        if cet1_above_requirements <= quarter * n:
            return factor
    return p.MDA_QUARTILE_FACTORS[-1]
