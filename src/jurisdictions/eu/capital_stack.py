"""EU own funds requirements and buffer stack -- Article 92(1)-(1a) CRR; CRD Articles 128-140.

* Pillar 1 minima (Article 92(1), consolidated): CET1 4,5 %, Tier 1 6 %, total
  capital 8 %, leverage ratio 3 %.
* G-SII leverage ratio buffer (Article 92(1a)): 50 % of the G-SII buffer rate,
  met with Tier 1 capital.
* Combined buffer requirement (CRD Article 128(6), consolidated 28.06.2021):
  capital conservation buffer extended by, as applicable, the institution-specific
  CCyB, the G-SII buffer, the O-SII buffer and the systemic risk buffer. CET1 used for
  one element cannot meet another (Article 128, second paragraph).

  - Conservation buffer 2,5 % of TREA (Article 129(1)).
  - Institution-specific CCyB = weighted average of the CCyB rates where the relevant
    credit exposures are located, weighted by own funds requirements for credit risk
    (Article 140(1)); rates 0 %-2,5 % in 0,25 pp steps, higher allowed (Article 136(4)),
    with the 2,5 % reciprocity cap of Article 140(2)(b)/(3)(b).
  - G-SII buffer by sub-category (Article 131(4), (9)): 1 % for the lowest sub-category,
    rising in steps of at least 0,5 % (see ``params.GSII_BUFFER_BY_SUBCATEGORY``).
  - O-SII buffer up to 3 % (Article 131(5)); higher only with Commission authorisation
    (131(5a)).
  - Where a group is subject to both a G-SII and an O-SII buffer, the higher applies
    (Article 131(14)); the systemic risk buffer is cumulative with the O-SII or G-SII
    buffer (Article 131(15) first subparagraph). Above 5 % combined, the Article 131(5a)
    authorisation procedure applies (131(15) second subparagraph, as replaced by CRD VI
    Article 1 point (44)(c)) -- a procedure, not a cap.

There is no EU stress capital buffer in the combined buffer requirement; the
Pillar 2 requirement (Article 104a CRD) and Pillar 2 guidance (Article 104b) sit
outside it, so a ``stress_buffer`` argument is recorded but not stacked.

References:
    - Regulation (EU) No 575/2013, Article 92(1)-(1a) (consolidated 09.07.2024)
    - Directive 2013/36/EU, Articles 128-131, 133, 136, 140 (consolidated 28.06.2021)
    - Directive (EU) 2024/1619, Article 1 points (44)-(45); Article 2(1)
"""

from __future__ import annotations

from src.jurisdictions.base import CapitalRequirements, Jurisdiction
from src.jurisdictions.eu import params as prm


def gsii_buffer_rate(systemic_bucket_or_rate: float) -> float:
    """G-SII buffer rate from a sub-category (1-5) or an explicit rate (decimal < 1).

    Sub-category rates per CRD Article 131(9): 1 % for the lowest, then steps of at least
    0,5 %; sub-category 5 carries a ``TODO: VERIFY`` (see ``params``).
    """
    if systemic_bucket_or_rate >= 1.0:
        bucket = int(round(systemic_bucket_or_rate))
        if bucket not in prm.GSII_BUFFER_BY_SUBCATEGORY:
            raise ValueError(f"G-SII sub-category must be 1-5, got {systemic_bucket_or_rate}")
        return prm.GSII_BUFFER_BY_SUBCATEGORY[bucket]
    if systemic_bucket_or_rate < 0:
        raise ValueError("buffer rate must be non-negative")
    return systemic_bucket_or_rate


def osii_buffer_rate(o_sii_rate: float, commission_authorised: bool = False) -> float:
    """O-SII buffer rate -- CRD Article 131(5): up to 3 %; above only under 131(5a)."""
    if o_sii_rate < 0:
        raise ValueError("buffer rate must be non-negative")
    return o_sii_rate if commission_authorised else min(o_sii_rate, prm.OSII_BUFFER_CAP)


def osii_subsidiary_cap(
    group_gsii_or_osii_rate: float, authorised_group_rate: float = 0.0
) -> float:
    """Cap on a subsidiary O-SII's individual / sub-consolidated buffer -- CRD Article 131(8).

    Lower of (a) the higher group G-SII/O-SII rate + 1 % and (b) 3 % or the rate the
    Commission authorised for the group under 131(5a).
    """
    b = max(prm.OSII_BUFFER_CAP, authorised_group_rate)
    return min(group_gsii_or_osii_rate + prm.OSII_SUBSIDIARY_ADD_ON, b)


def institution_specific_ccyb(
    rates_by_jurisdiction: dict[str, float],
    credit_own_funds_by_jurisdiction: dict[str, float],
    recognised_above_cap: frozenset[str] | set[str] = frozenset(),
) -> float:
    """Weighted-average CCyB -- CRD Article 140(1), with the 2,5 % cap of 140(2)(b)/(3)(b).

    Weights are the own funds requirements for credit risk on relevant credit exposures
    in each jurisdiction over the total. A jurisdiction's rate above 2,5 % is applied in
    full only where listed in ``recognised_above_cap`` (domestic authority or recognition
    under Article 137 / 139); otherwise 2,5 % is applied.
    """
    total = sum(credit_own_funds_by_jurisdiction.values())
    if total <= 0:
        return 0.0
    out = 0.0
    for j, req in credit_own_funds_by_jurisdiction.items():
        rate = rates_by_jurisdiction.get(j, 0.0)
        if rate < 0:
            raise ValueError("CCyB rates must be non-negative")
        if rate > prm.CCYB_RECIPROCITY_CAP and j not in recognised_above_cap:
            rate = prm.CCYB_RECIPROCITY_CAP
        out += rate * req / total
    return out


def systemic_risk_buffer_amount(
    rate_total: float, trea: float, sectoral: list[tuple[float, float]] | None = None
) -> float:
    """B_SR = r_T E_T + sum_i r_i E_i -- CRD Article 133(2) (CRD cons. p.129)."""
    return rate_total * trea + sum(r * e for r, e in (sectoral or []))


def capital_requirements(
    systemic_bucket_or_rate: float = 0.0,
    countercyclical_rate: float = 0.0,
    stress_buffer: float = 0.0,
    o_sii_rate: float = 0.0,
    systemic_risk_buffer_rate: float = 0.0,
    o_sii_commission_authorised: bool = False,
) -> CapitalRequirements:
    """Minimum ratios (Art. 92(1)), leverage buffer (Art. 92(1a)) and the CRD combined buffer.

    ``systemic_bucket_or_rate`` is the G-SII sub-category (1-5) or rate; ``o_sii_rate``
    is capped at 3 % unless the Commission authorised more (CRD 131(5)-(5a)). The
    systemic buffer reported is max(G-SII, O-SII) (CRD 131(14)); the systemic risk
    buffer is added on top (CRD 131(15)).
    """
    if countercyclical_rate < 0 or o_sii_rate < 0 or systemic_risk_buffer_rate < 0:
        raise ValueError("buffer rates must be non-negative")
    gsii = gsii_buffer_rate(systemic_bucket_or_rate)
    osii = osii_buffer_rate(o_sii_rate, o_sii_commission_authorised)
    systemic = max(gsii, osii)
    citations = {
        "cet1_minimum": "CRR Art. 92(1)(a)",
        "tier1_minimum": "CRR Art. 92(1)(b)",
        "total_capital_minimum": "CRR Art. 92(1)(c)",
        "leverage_minimum": "CRR Art. 92(1)(d)",
        "leverage_buffer": "CRR Art. 92(1a): 50 % of the G-SII buffer rate",
        "conservation_buffer": "CRD Art. 129(1): 2,5 % of TREA",
        "countercyclical_buffer": "CRD Art. 130(1), 140(1) institution-specific rate (input); "
        "Art. 136(4) range 0-2,5 % in 0,25 pp steps",
        "systemic_buffer": "CRD Art. 131(14): higher of G-SII (131(4), (9)) and O-SII "
        "(131(5), <= 3 % absent 131(5a) authorisation)",
        "systemic_risk_buffer": "CRD Art. 131(15): cumulative with the G-SII / O-SII buffer; "
        "Art. 133 (input)",
        "combined_buffer": "CRD Art. 128(6)",
    }
    if systemic_risk_buffer_rate + systemic > prm.SYRB_PLUS_SYSTEMIC_AUTHORISATION_THRESHOLD:
        citations["systemic_risk_buffer"] += (
            "; > 5 % combined with the G-SII/O-SII rate: CRD Art. 131(15) second subpara. "
            "(as replaced by CRD VI) -> Art. 131(5a) procedure"
        )
    if stress_buffer:
        citations["stress_buffer"] = (
            f"input {stress_buffer:.4f} not stacked: the EU combined buffer has no stress buffer "
            "(P2R/P2G sit outside the CBR, CRD Art. 104a/104b)"
        )
    return CapitalRequirements(
        jurisdiction=Jurisdiction.EU,
        cet1_minimum=prm.CET1_MINIMUM,
        tier1_minimum=prm.TIER1_MINIMUM,
        total_capital_minimum=prm.TOTAL_CAPITAL_MINIMUM,
        conservation_buffer=prm.CAPITAL_CONSERVATION_BUFFER,
        countercyclical_buffer=countercyclical_rate,
        systemic_buffer=systemic,
        systemic_risk_buffer=systemic_risk_buffer_rate,
        stress_buffer=0.0,
        leverage_minimum=prm.LEVERAGE_MINIMUM,
        leverage_buffer=prm.GSII_LEVERAGE_BUFFER_SHARE * gsii,
        citations=citations,
    )
