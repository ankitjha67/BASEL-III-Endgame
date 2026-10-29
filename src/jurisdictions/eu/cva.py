"""EU CVA risk -- basic approach (BA-CVA), Articles 382-386 CRR as replaced by CRR3.

Formulas (CRR3 point (202), OJ pp.155-158, printed as images; transcribed in the
parameter reference):

* SCVA_c  = (1/alpha) RW_c sum_NS M_NS EAD_NS DF_NS, alpha = 1,4
* DF      = (1 - exp(-0,05 M)) / (0,05 M); DF = 1 for IMM users
* BACVA^csr-unhedged = DS_CVA sqrt((rho sum SCVA_c)^2 + (1 - rho^2) sum SCVA_c^2),
  rho = 0,5, DS_CVA = 0,65
* BACVA^csr-hedged   = sqrt((rho sum(SCVA_c - SNH_c) - IH)^2
                        + (1 - rho^2) sum(SCVA_c - SNH_c)^2 + sum HMA_c)
* SNH_c   = sum_h r_hc RW_h M_h B_h DF_h;  IH = sum_i RW_i^ind M_i B_i DF_i
* HMA_c   = sum_h (1 - r_hc^2) (RW_h M_h B_h DF_h)^2
* BACVA^total = beta BACVA^csr-unhedged + DS_CVA (1 - beta) BACVA^csr-hedged, beta = 0,25
* RW_i^ind = Table 1 weight (or constituent-weighted average) x 0,7
* M_NS per Article 162 but capped at the longest contractual remaining maturity, not 5 years.

Scope (Article 382): excluded are QCCP / client-clearing trades (382(3)) and
transactions with non-financial counterparties below the EMIR clearing
threshold, intragroup transactions, pension schemes under the EMIR transitional,
and EMIR-exempt / 0 %-RW sovereign counterparties (382(4)(a)-(d)). Article 385
offers a simplified approach (CVA = CCR RWA / 12,5) to institutions meeting
Article 273a(2). There is no BCBS-style materiality threshold (MAR50.9).

Counterparty dict keys read by :func:`ba_cva_capital`:
``ead``, ``maturity``, ``sector`` (key of ``params.BACVA_RW``), ``credit_quality``
(``IG``/``CQS1_3`` or anything else = CQS 4-6 / not rated), optional
``counterparty_id`` (netting sets sharing an id are one counterparty), ``imm``
(DF = 1), the exemption keys of ``params.CVA_EXEMPTION_KEYS``, single-name hedge
keys ``sn_hedge_notional``, ``sn_hedge_maturity``, ``sn_hedge_relation``
(DIRECT/LEGAL/SECTOR), ``sn_hedge_sector``, ``sn_hedge_credit_quality``; an entry
with ``index_hedge`` true is an index CDS with ``notional``, ``maturity``,
``sector``, ``credit_quality`` (or ``index_rw`` = constituent-weighted Table 1 RW).

References:
    - Regulation (EU) 2024/1623 Article 1 points (197)-(202)
    - Regulation (EU) No 575/2013 Article 382(3)-(4) (consolidated)
"""

from __future__ import annotations

import math
from collections import defaultdict

from src.jurisdictions.eu import params as prm


def supervisory_discount_factor(maturity: float) -> float:
    """DF = (1 - exp(-0,05 M)) / (0,05 M) -- Article 384(2); DF -> 1 as M -> 0."""
    if maturity <= 0:
        return 1.0
    r = prm.BACVA_DF_RATE
    return (1.0 - math.exp(-r * maturity)) / (r * maturity)


def risk_weight(sector: str, credit_quality: str) -> float:
    """Article 384(2) Table 1 risk weight; CQS 1-3 = ``IG``/``CQS1_3``, otherwise CQS 4-6 and not
    rated."""
    pair = prm.BACVA_RW.get(str(sector).upper(), prm.BACVA_RW["OTHER"])
    return pair[0] if str(credit_quality).upper() in ("IG", "CQS1_3") else pair[1]


def is_exempt(cp: dict[str, float | str | bool]) -> bool:
    """Article 382(3)-(4) exclusions from the own funds requirements for CVA risk."""
    return any(bool(cp.get(k, False)) for k in prm.CVA_EXEMPTION_KEYS)


def ba_cva_capital(
    counterparties: list[dict[str, float | str | bool]],
    hedged: bool = False,
) -> dict[str, float]:
    """Basic approach own funds requirement for CVA risk -- Article 384(2)-(3).

    Returns ``k_reduced`` (BACVA^csr-unhedged, DS included), ``k_hedged``
    (BACVA^csr-hedged), ``k`` (requirement used: unhedged formula unless
    ``hedged``), ``rwa`` = 12,5 k (Article 92(6)(b)) and ``excluded_ead``.
    """
    scva: dict[str, float] = defaultdict(float)
    snh: dict[str, float] = defaultdict(float)
    hma: dict[str, float] = defaultdict(float)
    ih = 0.0
    excluded = 0.0
    for idx, cp in enumerate(counterparties):
        if bool(cp.get("index_hedge", False)):
            m = float(cp.get("maturity", 0.0))
            b = float(cp.get("notional", 0.0))
            base_rw = (
                float(cp["index_rw"])
                if "index_rw" in cp
                else risk_weight(
                    str(cp.get("sector", "OTHER")), str(cp.get("credit_quality", "HY_NR"))
                )
            )
            ih += prm.BACVA_INDEX_RW_SCALAR * base_rw * m * b * supervisory_discount_factor(m)
            continue
        ead = float(cp.get("ead", 0.0))
        if is_exempt(cp):
            excluded += ead
            continue
        cid = str(cp.get("counterparty_id", f"cp{idx}"))
        m = float(cp.get("maturity", 0.0))
        df = 1.0 if bool(cp.get("imm", False)) else supervisory_discount_factor(m)
        rw = risk_weight(str(cp.get("sector", "OTHER")), str(cp.get("credit_quality", "HY_NR")))
        scva[cid] += rw * m * ead * df / prm.BACVA_ALPHA
        b_sn = float(cp.get("sn_hedge_notional", 0.0))
        if b_sn > 0:
            m_sn = float(cp.get("sn_hedge_maturity", m))
            r_hc = prm.BACVA_HEDGE_CORRELATION[str(cp.get("sn_hedge_relation", "DIRECT")).upper()]
            rw_sn = risk_weight(
                str(cp.get("sn_hedge_sector", cp.get("sector", "OTHER"))),
                str(cp.get("sn_hedge_credit_quality", cp.get("credit_quality", "HY_NR"))),
            )
            term = rw_sn * m_sn * b_sn * supervisory_discount_factor(m_sn)
            snh[cid] += r_hc * term
            hma[cid] += (1.0 - r_hc**2) * term**2
    rho = prm.BACVA_RHO
    s_vals = list(scva.values())
    k_reduced = prm.BACVA_DS * math.sqrt(
        (rho * sum(s_vals)) ** 2 + (1 - rho**2) * sum(v * v for v in s_vals)
    )
    net = [scva[c] - snh[c] for c in scva]
    k_hedged = math.sqrt(
        max(
            0.0,
            (rho * sum(net) - ih) ** 2 + (1 - rho**2) * sum(v * v for v in net) + sum(hma.values()),
        )
    )
    if hedged:
        k = prm.BACVA_BETA * k_reduced + prm.BACVA_DS * (1 - prm.BACVA_BETA) * k_hedged
    else:
        k = k_reduced
    return {
        "k_reduced": k_reduced,
        "k_hedged": k_hedged,
        "k": k,
        "rwa": prm.OWN_FUNDS_TO_RWA * k,
        "excluded_ead": excluded,
        "n_counterparties": float(len(scva)),
    }


def simplified_cva_capital(ccr_rwa: float) -> float:
    """Article 385(1): own funds requirement = CCR risk-weighted exposure amounts / 12,5."""
    return ccr_rwa / prm.OWN_FUNDS_TO_RWA
