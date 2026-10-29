"""OSFI CAR 2026 Chapter 8 -- CVA risk: basic approach (BA-CVA) and the materiality option.

BA-CVA (s.8.2): K_reduced = sqrt((rho sum SCVA_c)^2 + (1 - rho^2) sum SCVA_c^2), rho = 50%;
SCVA_c = (1/alpha) RW_c sum_NS M_NS EAD_NS DF_NS, alpha = 1.4, DF = (1 - e^{-0.05M})/(0.05M)
(1 for IMM institutions); capital = DS x K with DS = 0.65; full version
K_full = 0.25 K_reduced + 0.75 K_hedged with single-name hedges (r_hc 100/80/50%), index hedges
(RW x 0.7) and the HMA term. Table 1 risk weights are the Basel MAR50.16 values.

Materiality (s.8.1): an institution with aggregate non-centrally-cleared derivative notional
<= $150 billion (CAD) may set CVA capital = 100% of its CCR capital requirement.

References:
    - OSFI CAR 2026 Ch.8 s.8.1-8.2.2, Tables 1-2
    - Basel Framework MAR50.9-50.26
"""

from __future__ import annotations

import math
from collections import defaultdict

from src.jurisdictions.ca import params as p

_SECTOR_ALIASES: dict[str, str] = {
    "SOVEREIGNS": "SOVEREIGN", "CENTRAL_BANK": "SOVEREIGN", "MDB": "SOVEREIGN",
    "LOCAL_GOV": "LOCAL_GOVERNMENT", "PSE": "LOCAL_GOVERNMENT", "EDUCATION": "LOCAL_GOVERNMENT",
    "FINANCIALS": "FINANCIAL", "BANK": "FINANCIAL",
    "ENERGY": "BASIC_MATERIALS", "INDUSTRIALS": "BASIC_MATERIALS",
    "CONSUMER_GOODS": "CONSUMER", "TRANSPORTATION": "CONSUMER",
    "TELECOM": "TECHNOLOGY", "TELECOMMUNICATIONS": "TECHNOLOGY",
    "UTILITIES": "HEALTH_CARE", "HEALTHCARE": "HEALTH_CARE",
}


def supervisory_rw(sector: str, credit_quality: str) -> float:
    """RW_c from CAR Ch.8 s.8.2.1 Table 1 [MAR 50.16].

    ``credit_quality`` "IG" selects the IG column; anything else ("HY", "NR", "HY_NR") the
    "HY and NR" column. Unknown sectors fall to "Other sector".
    """
    key = sector.upper()
    key = _SECTOR_ALIASES.get(key, key)
    ig, hy = p.BA_CVA_RISK_WEIGHTS.get(key, p.BA_CVA_RISK_WEIGHTS["OTHER"])
    return ig if credit_quality.upper() == "IG" else hy


def discount_factor(maturity: float, imm: bool = False) -> float:
    """DF = (1 - exp(-0.05 M)) / (0.05 M); 1 for IMM institutions (CAR Ch.8 s.8.2.1 [MAR 50.15])."""
    if imm or maturity <= 0:
        return 1.0
    x = p.BA_CVA_DF_RATE * maturity
    return (1.0 - math.exp(-x)) / x


def ba_cva(
    counterparties: list[dict[str, float | str | bool]],
    hedged: bool = False,
) -> dict[str, float]:
    """Reduced / full BA-CVA capital (CAR Ch.8 s.8.2.1-8.2.2 [MAR 50.14-50.26]).

    Each dict: ``ead``, ``maturity``, ``sector``, ``credit_quality``; optional ``counterparty``
    (netting sets with the same id aggregate into one SCVA_c), ``imm`` (DF = 1). For the full
    version (``hedged=True``) a netting-set dict may carry single-name hedge fields
    ``hedge_notional``, ``hedge_maturity``, ``hedge_relation`` (DIRECT / LEGAL_RELATION /
    SECTOR_REGION), ``hedge_sector``, ``hedge_credit_quality``; a dict with ``index_hedge`` True
    is an index hedge (``notional``, ``maturity``, ``sector``, ``credit_quality``).
    Returns k_reduced, k_hedged, k_full, k (= DS x K used) and rwa (= 12.5 k).
    """
    scva: dict[str, float] = defaultdict(float)
    snh: dict[str, float] = defaultdict(float)
    hma: dict[str, float] = defaultdict(float)
    ih = 0.0
    for i, cp in enumerate(counterparties):
        if bool(cp.get("index_hedge", False)):
            m = float(cp["maturity"])
            rw = supervisory_rw(str(cp.get("sector", "OTHER")), str(cp.get("credit_quality", "IG")))
            ih += p.BA_CVA_INDEX_RW_SCALAR * rw * m * float(cp["notional"]) * discount_factor(m)
            continue
        name = str(cp.get("counterparty", f"cp{i}"))
        m = float(cp["maturity"])
        rw_c = supervisory_rw(str(cp["sector"]), str(cp["credit_quality"]))
        df = discount_factor(m, bool(cp.get("imm", False)))
        scva[name] += rw_c * m * float(cp["ead"]) * df / p.BA_CVA_ALPHA
        if hedged and float(cp.get("hedge_notional", 0.0)) > 0:
            mh = float(cp.get("hedge_maturity", m))
            r = p.BA_CVA_HEDGE_CORRELATION[str(cp.get("hedge_relation", "DIRECT")).upper()]
            rw_h = supervisory_rw(str(cp.get("hedge_sector", cp["sector"])),
                                  str(cp.get("hedge_credit_quality", cp["credit_quality"])))
            x = rw_h * mh * float(cp["hedge_notional"]) * discount_factor(mh)
            snh[name] += r * x
            hma[name] += (1.0 - r * r) * x * x
    rho = p.BA_CVA_RHO
    total = sum(scva.values())
    idio = sum(v * v for v in scva.values())
    k_reduced = math.sqrt((rho * total) ** 2 + (1.0 - rho * rho) * idio)
    net = {c: scva[c] - snh.get(c, 0.0) for c in scva}
    k_hedged = math.sqrt(max(0.0, (rho * sum(net.values()) - ih) ** 2
                             + (1.0 - rho * rho) * sum(v * v for v in net.values())
                             + sum(hma.values())))
    k_full = p.BA_CVA_BETA * k_reduced + (1.0 - p.BA_CVA_BETA) * k_hedged
    k = p.BA_CVA_DISCOUNT_SCALAR * (k_full if hedged else k_reduced)
    return {
        "k_reduced": k_reduced,
        "k_hedged": k_hedged,
        "k_full": k_full,
        "discount_scalar": p.BA_CVA_DISCOUNT_SCALAR,
        "k": k,
        "rwa": p.CVA_RWA_MULTIPLIER * k,
    }


def below_materiality_threshold(non_cleared_notional_cad_m: float) -> bool:
    """Materiality test: notional <= $150 billion (CAD) (CAR Ch.8 s.8.1 [MAR 50.9])."""
    return non_cleared_notional_cad_m <= p.CVA_MATERIALITY_THRESHOLD_CAD_M


def alternative_cva_capital(ccr_capital: float, non_cleared_notional_cad_m: float) -> float:
    """CVA capital = 100% of CCR capital for institutions below the threshold (CAR Ch.8 s.8.1)."""
    if not below_materiality_threshold(non_cleared_notional_cad_m):
        raise ValueError("institution is above the $150 billion CVA materiality threshold")
    return p.CVA_ALTERNATIVE_CCR_MULTIPLE * ccr_capital
