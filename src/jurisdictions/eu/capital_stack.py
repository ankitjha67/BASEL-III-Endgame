"""EU own funds requirements and buffer stack -- Article 92(1)-(1a) CRR; buffers per CRD.

* Pillar 1 minima (Article 92(1), consolidated): CET1 4,5 %, Tier 1 6 %, total
  capital 8 %, leverage ratio 3 %.
* G-SII leverage ratio buffer (Article 92(1a)): 50 % of the G-SII buffer rate,
  met with Tier 1 capital.
* Combined buffer requirement (Directive 2013/36/EU, Articles 128-131, 133,
  136): NOT in the source texts. The stacking logic implemented here takes the
  rates as inputs; the placeholder rates in ``params`` are flagged
  ``TODO: VERIFY``. Stacking assumed: CCB + institution-specific CCyB +
  max(G-SII, O-SII) + systemic risk buffer.
  # TODO: VERIFY -- the 'higher of G-SII and O-SII, systemic risk buffer
  # additive' rule is Article 131(14)-(15) CRD as amended by Directive (EU)
  # 2019/878, which is not among the source texts.

There is no EU stress capital buffer in the combined buffer requirement; the
Pillar 2 requirement (Article 104 CRD) and Pillar 2 guidance sit outside it,
so a ``stress_buffer`` argument is recorded but not stacked.

References:
    - Regulation (EU) No 575/2013, Article 92(1)-(1a) (consolidated 09.07.2024)
"""

from __future__ import annotations

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.eu import params as prm


def gsii_buffer_rate(systemic_bucket_or_rate: float) -> float:
    """G-SII buffer rate from a sub-category (1-5) or an explicit rate (decimal < 1).

    # TODO: VERIFY -- sub-category rates are set by Article 131(4) CRD (not in the sources).
    """
    if systemic_bucket_or_rate >= 1.0:
        bucket = int(round(systemic_bucket_or_rate))
        if bucket not in prm.GSII_BUFFER_BY_SUBCATEGORY:
            raise ValueError(f"G-SII sub-category must be 1-5, got {systemic_bucket_or_rate}")
        return prm.GSII_BUFFER_BY_SUBCATEGORY[bucket]
    if systemic_bucket_or_rate < 0:
        raise ValueError("buffer rate must be non-negative")
    return systemic_bucket_or_rate


def capital_requirements(
    systemic_bucket_or_rate: float = 0.0,
    countercyclical_rate: float = 0.0,
    stress_buffer: float = 0.0,
    o_sii_rate: float = 0.0,
    systemic_risk_buffer_rate: float = 0.0,
) -> CapitalRequirements:
    """Minimum ratios (Art. 92(1)), leverage buffer (Art. 92(1a)) and the CRD combined buffer.

    ``systemic_bucket_or_rate`` is the G-SII sub-category (1-5) or rate;
    ``o_sii_rate`` is capped at the CRD ceiling placeholder. The systemic buffer
    reported is max(G-SII, O-SII).
    """
    if countercyclical_rate < 0 or o_sii_rate < 0 or systemic_risk_buffer_rate < 0:
        raise ValueError("buffer rates must be non-negative")
    gsii = gsii_buffer_rate(systemic_bucket_or_rate)
    osii = min(o_sii_rate, prm.OSII_BUFFER_CAP)
    citations = {
        "cet1_minimum": "CRR Art. 92(1)(a)",
        "tier1_minimum": "CRR Art. 92(1)(b)",
        "total_capital_minimum": "CRR Art. 92(1)(c)",
        "leverage_minimum": "CRR Art. 92(1)(d)",
        "leverage_buffer": "CRR Art. 92(1a): 50 % of the G-SII buffer rate",
        "conservation_buffer": "CRD Art. 129 -- TODO: VERIFY (not in source texts)",
        "countercyclical_buffer": "CRD Art. 130/140 institution-specific rate (input)",
        "systemic_buffer": "CRD Art. 131 max(G-SII, O-SII) -- TODO: VERIFY",
        "systemic_risk_buffer": "CRD Art. 133 (input) -- TODO: VERIFY stacking",
    }
    if stress_buffer:
        citations["stress_buffer"] = (
            f"input {stress_buffer:.4f} not stacked: the EU combined buffer has no stress buffer "
            "(P2R/P2G sit outside the CBR, CRD Art. 104/104b)"
        )
    return CapitalRequirements(
        jurisdiction=Jurisdiction.EU,
        cet1_minimum=prm.CET1_MINIMUM,
        tier1_minimum=prm.TIER1_MINIMUM,
        total_capital_minimum=prm.TOTAL_CAPITAL_MINIMUM,
        conservation_buffer=prm.CAPITAL_CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=max(gsii, osii),
        systemic_risk_buffer=systemic_risk_buffer_rate,
        stress_buffer=0.0,
        leverage_minimum=prm.LEVERAGE_MINIMUM,
        leverage_buffer=prm.GSII_LEVERAGE_BUFFER_SHARE * gsii,
        citations=citations,
    )
