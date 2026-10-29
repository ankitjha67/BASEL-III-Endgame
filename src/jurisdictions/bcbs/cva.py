"""BCBS basic approach for CVA risk, BA-CVA (MAR50.12-50.26), and the MAR50.9 option.

    SCVA_c    = (1/alpha) x RW_c x sum_NS M_NS x EAD_NS x DF_NS            (MAR50.15)
    DF        = (1 - exp(-0.05 M)) / (0.05 M)  (non-IMM; 1 for IMM)       (MAR50.15 fn 357)
    K_reduced = sqrt[(rho sum_c SCVA_c)^2 + (1 - rho^2) sum_c SCVA_c^2]   (MAR50.14)
    K_hedged  = sqrt[(rho sum_c (SCVA_c - SNH_c) - IH)^2
                     + (1 - rho^2) sum_c (SCVA_c - SNH_c)^2 + sum_c HMA_c] (MAR50.21)
    SNH_c     = sum_h r_hc x RW_h x M_h x B_h x DF_h                      (MAR50.23)
    IH        = sum_i RW_i x M_i x B_i x DF_i  (RW_i = 0.7 x Table 1)     (MAR50.24)
    HMA_c     = sum_h (1 - r_hc^2) x (RW_h x M_h x B_h x DF_h)^2          (MAR50.25)
    K_full    = beta x K_reduced + (1 - beta) x K_hedged, beta = 0.25     (MAR50.20)
    Capital   = DS x K, DS = 0.65; RWA = 12.5 x capital                   (MAR50.14, 50.20, 50.1)

The equations are images in the Framework text; they are transcribed from
BCBS d424 (CVA paras 12-23), which lacks the 0.65 discount scalar and had a
3.0% (not 2.0%) HY/NR sovereign risk weight. The Framework governs both.

Counterparty dict keys read by :func:`ba_cva_capital`:

- ``ead`` ($M), ``maturity`` (years), ``sector`` (one of
  :data:`~src.jurisdictions.bcbs.params.BA_CVA_SECTORS`), ``credit_quality``
  ("IG" or "HY_NR"; "HY" and "NR" accepted), optional ``counterparty``
  (id grouping netting sets; defaults to a unique id per row), optional
  ``imm`` (bool: DF = 1).
- Single-name hedge of the row's counterparty (full version only):
  ``hedge_notional``, ``hedge_maturity``, ``hedge_relation``
  ("DIRECT" / "LEGAL" / "SECTOR_REGION"), optional ``hedge_sector`` and
  ``hedge_credit_quality`` (default: the counterparty's).
- Index hedge rows: ``type`` = "INDEX_HEDGE" with ``notional``,
  ``maturity``, ``sector``, ``credit_quality``.

References:
    - Basel Framework MAR50.1-50.26 (pp. 722-729)
    - BCBS d424, CVA paras 7, 12-24
"""

from __future__ import annotations

import math
from collections import defaultdict

from src.jurisdictions.bcbs import params as p

CounterpartyRow = dict[str, float | str | bool]


def discount_factor(maturity: float, imm: bool = False) -> float:
    """Supervisory discount factor (MAR50.15(4), footnote 357)."""
    if imm:
        return 1.0
    if maturity <= 0:
        return 1.0
    r = p.BA_CVA_DF_RATE
    return (1.0 - math.exp(-r * maturity)) / (r * maturity)


def normalise_credit_quality(cq: str) -> str:
    """Map "IG" / "HY" / "NR" / "HY_NR" to the MAR50.16 Table 1 columns."""
    cq = cq.upper()
    if cq == "IG":
        return "IG"
    if cq in ("HY", "NR", "HY_NR", "HY_AND_NR"):
        return "HY_NR"
    raise ValueError(f"credit quality must be IG, HY or NR: {cq}")


def supervisory_rw(sector: str, credit_quality: str) -> float:
    """MAR50.16 Table 1 risk weight for (sector, credit quality)."""
    key = (sector.upper(), normalise_credit_quality(credit_quality))
    if key not in p.BA_CVA_RW:
        raise ValueError(f"unknown BA-CVA sector: {sector}")
    return p.BA_CVA_RW[key]


def stand_alone_cva(rw: float, netting_sets: list[tuple[float, float, float]]) -> float:
    """SCVA_c = (1/alpha) RW_c sum(M_NS EAD_NS DF_NS) (MAR50.15); tuples are (M, EAD, DF)."""
    return rw / p.BA_CVA_ALPHA * sum(m * ead * df for m, ead, df in netting_sets)


def k_reduced(scva: list[float]) -> float:
    """MAR50.14: sqrt[(rho sum SCVA)^2 + (1 - rho^2) sum SCVA^2]."""
    rho = p.BA_CVA_RHO
    return math.sqrt((rho * sum(scva)) ** 2 + (1.0 - rho ** 2) * sum(s * s for s in scva))


def k_hedged(scva: list[float], snh: list[float], hma: list[float], ih: float) -> float:
    """MAR50.21: hedged BA-CVA term (per-counterparty lists aligned by index)."""
    rho = p.BA_CVA_RHO
    net = [s - h for s, h in zip(scva, snh, strict=True)]
    return math.sqrt((rho * sum(net) - ih) ** 2 + (1.0 - rho ** 2) * sum(x * x for x in net)
                     + sum(hma))


def k_full(kr: float, kh: float) -> float:
    """MAR50.20: K_full = beta K_reduced + (1 - beta) K_hedged, beta = 0.25."""
    return p.BA_CVA_BETA * kr + (1.0 - p.BA_CVA_BETA) * kh


def materiality_alternative(non_cleared_notional_eur_m: float,
                            ccr_capital: float) -> float | None:
    """MAR50.9: CVA capital = 100% of CCR capital for banks at or below EUR 100bn
    of non-centrally-cleared notional (EUR millions); None above the threshold."""
    if non_cleared_notional_eur_m <= p.CVA_MATERIALITY_THRESHOLD_EUR_M:
        return p.CVA_MATERIALITY_CCR_SHARE * ccr_capital
    return None


def _f(row: CounterpartyRow, key: str, default: float = 0.0) -> float:
    """Read a numeric field from a counterparty row."""
    v = row.get(key, default)
    return float(v)


def ba_cva_capital(counterparties: list[CounterpartyRow], hedged: bool = False) -> dict[str, float]:
    """Reduced (MAR50.14) or full (MAR50.20) BA-CVA capital and RWA.

    Returns ``k_reduced`` and ``k_hedged`` / ``k_full`` (before the discount
    scalar), ``ds``, ``k`` (DS x K_reduced or DS x K_full) and ``rwa``
    (12.5 x k, MAR50.1).
    """
    ns: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    rw_c: dict[str, float] = {}
    snh: dict[str, float] = defaultdict(float)
    hma: dict[str, float] = defaultdict(float)
    ih = 0.0
    for i, row in enumerate(counterparties):
        if str(row.get("type", "")).upper() == "INDEX_HEDGE":
            m = _f(row, "maturity")
            rw_i = p.BA_CVA_INDEX_RW_SCALAR * supervisory_rw(str(row["sector"]),
                                                             str(row["credit_quality"]))
            ih += rw_i * m * _f(row, "notional") * discount_factor(m)
            continue
        cid = str(row.get("counterparty", f"cp{i}"))
        rw = supervisory_rw(str(row["sector"]), str(row["credit_quality"]))
        rw_c[cid] = rw
        m = _f(row, "maturity")
        ns[cid].append((m, _f(row, "ead"), discount_factor(m, bool(row.get("imm", False)))))
        if _f(row, "hedge_notional") > 0:
            mh = _f(row, "hedge_maturity")
            r_hc = p.BA_CVA_HEDGE_CORRELATION[str(row.get("hedge_relation", "DIRECT")).upper()]
            rw_h = supervisory_rw(str(row.get("hedge_sector", row["sector"])),
                                  str(row.get("hedge_credit_quality", row["credit_quality"])))
            term = rw_h * mh * _f(row, "hedge_notional") * discount_factor(mh)
            snh[cid] += r_hc * term
            hma[cid] += (1.0 - r_hc ** 2) * term ** 2
    ids = list(ns)
    scva = [stand_alone_cva(rw_c[c], ns[c]) for c in ids]
    kr = k_reduced(scva)
    out: dict[str, float] = {"k_reduced": kr, "ds": p.BA_CVA_DISCOUNT_SCALAR,
                             "sum_scva": sum(scva)}
    if hedged:
        kh = k_hedged(scva, [snh[c] for c in ids], [hma[c] for c in ids], ih)
        kf = k_full(kr, kh)
        out.update({"k_hedged": kh, "k_full": kf, "k": p.BA_CVA_DISCOUNT_SCALAR * kf})
    else:
        out["k"] = p.BA_CVA_DISCOUNT_SCALAR * kr
    out["rwa"] = p.CVA_RWA_MULTIPLIER * out["k"]
    return out
