"""BA-CVA under MAS Notice 637 Part VIII Division 5 Sub-division 2.

Reduced BA-CVA: capital = DS x K_reduced, DS = 0.65 (para 8.5.13);
K_reduced = sqrt((rho x sum SCVA_c)^2 + (1 - rho^2) x sum SCVA_c^2), rho = 50%;
SCVA_c = (1/alpha) x RW_c x sum_NS (M_NS x EAD_NS x DF_NS), alpha = 1.4,
DF = (1 - exp(-0.05 M)) / (0.05 M) for non-IMM banks (para 8.5.14).

Full BA-CVA: capital = DS x K_full, K_full = beta x K_reduced + (1 - beta) x
K_hedged, beta = 0.25 (para 8.5.17), with
K_hedged = sqrt((rho x sum(SCVA_c - SNH_c) - IH)^2 + (1 - rho^2) x sum(SCVA_c - SNH_c)^2
+ sum HMA_c).

CVA RWA = 12.5 x capital (para 8.5.1). A bank with non-centrally cleared
derivatives notional <= S$150bn may instead set CVA RWA = CCR RWA (para 8.5.10).

Counterparty dict keys (``ba_cva_capital``): ``ead`` (SGD m), ``maturity``
(years), ``sector`` (Table 8-26 key: SOVEREIGN, PSE, FINANCIAL,
BASIC_MATERIALS, CONSUMER, TECHNOLOGY, HEALTHCARE, OTHER) and
``credit_quality`` ("IG" = grade "3" or better; "HY_NR" = grade "4" or worse
or not rated). Optional single-name hedge keys: ``hedge_notional``,
``hedge_maturity``, ``hedge_reference`` (COUNTERPARTY / RELATED / SECTOR,
Table 8-27), ``hedge_sector`` and ``hedge_credit_quality`` (default: the
counterparty's). Index hedges are passed as separate dicts with
``index_hedge`` = True, ``notional``, ``maturity``, ``sector``,
``credit_quality`` and ``homogeneous`` (all constituents same sector and
quality -> RW x 0.7, para 8.5.17(c)(v)(B)(1)); a non-homogeneous index passes
its pre-computed weighted-average RW in ``rw`` (x 0.7 per (B)(2)).

References:
    - MAS Notice 637 paras 8.5.1, 8.5.10, 8.5.12-8.5.18, Tables 8-26 and 8-27
      (pp. 8-178 to 8-187)
    - Basel Framework MAR50.12-50.24 (comparison)
"""

from __future__ import annotations

import math

from src.jurisdictions.sg import params as p

_SECTOR_ALIASES: dict[str, str] = {
    "SOVEREIGN": "SOVEREIGN",
    "SOVEREIGNS": "SOVEREIGN",
    "MDB": "SOVEREIGN",
    "CENTRAL_BANK": "SOVEREIGN",
    "PSE": "PSE",
    "LOCAL_GOVERNMENT": "PSE",
    "EDUCATION": "PSE",
    "FINANCIAL": "FINANCIAL",
    "FINANCIALS": "FINANCIAL",
    "FINANCIAL_INSTITUTIONS": "FINANCIAL",
    "BASIC_MATERIALS": "BASIC_MATERIALS",
    "ENERGY": "BASIC_MATERIALS",
    "INDUSTRIALS": "BASIC_MATERIALS",
    "CONSUMER": "CONSUMER",
    "TRANSPORTATION": "CONSUMER",
    "TECHNOLOGY": "TECHNOLOGY",
    "TELECOMMUNICATIONS": "TECHNOLOGY",
    "HEALTHCARE": "HEALTHCARE",
    "UTILITIES": "HEALTHCARE",
    "OTHER": "OTHER",
}


def discount_factor(maturity_years: float) -> float:
    """DF = (1 - exp(-0.05 M)) / (0.05 M) (non-IMM banks).

    Reference: MAS Notice 637 para 8.5.14(b)(iv)(B) and footnote 826 (pp. 8-182, 8-183).
    """
    if maturity_years <= 0.0:
        return 1.0
    r = p.BA_CVA_DISCOUNT_RATE
    return (1.0 - math.exp(-r * maturity_years)) / (r * maturity_years)


def counterparty_risk_weight(sector: str, credit_quality: str) -> float:
    """RW_c from Table 8-26 by sector and credit quality.

    Reference: MAS Notice 637 para 8.5.14(b)(i), Table 8-26 (p. 8-183). Unknown sectors map to
    "Other sector". ``credit_quality`` "IG" = grade "3" or better; anything else = grade "4"
    or worse / not rated.
    """
    key = _SECTOR_ALIASES.get(sector.strip().upper(), "OTHER")
    ig, hy = p.BA_CVA_RW[key]
    return ig if credit_quality.strip().upper() == "IG" else hy


def scva(rw: float, netting_sets: list[tuple[float, float]], imm_bank: bool = False) -> float:
    """SCVA_c = (1/alpha) x RW_c x sum(M_NS x EAD_NS x DF_NS).

    Reference: MAS Notice 637 para 8.5.14(b) (p. 8-181). ``netting_sets`` holds (EAD, M) pairs;
    DF = 1 for a bank using the CCR internal models method (8.5.14(b)(iv)(A)).
    """
    total = sum(m * ead * (1.0 if imm_bank else discount_factor(m)) for ead, m in netting_sets)
    return rw * total / p.BA_CVA_ALPHA


def k_reduced(scvas: list[float]) -> float:
    """K_reduced per MAS Notice 637 para 8.5.14 (p. 8-181)."""
    rho = p.BA_CVA_RHO
    return math.sqrt((rho * sum(scvas)) ** 2 + (1.0 - rho**2) * sum(s**2 for s in scvas))


def k_hedged(scvas: list[float], snhs: list[float], ih: float, hmas: list[float]) -> float:
    """K_hedged per MAS Notice 637 para 8.5.17(c) (p. 8-184)."""
    rho = p.BA_CVA_RHO
    net = [s - h for s, h in zip(scvas, snhs, strict=True)]
    return math.sqrt(
        (rho * sum(net) - ih) ** 2 + (1.0 - rho**2) * sum(x**2 for x in net) + sum(hmas)
    )


def ba_cva_capital(
    counterparties: list[dict[str, float | str | bool]],
    hedged: bool = False,
    imm_bank: bool = False,
) -> dict[str, float]:
    """Reduced or full BA-CVA capital and RWA.

    Reference: MAS Notice 637 paras 8.5.1, 8.5.13-8.5.17 (pp. 8-178 to 8-186).

    Returns ``k_reduced`` (K_reduced before the discount scalar), ``k_hedged`` and ``k_full``
    (full version only), ``discount_scalar``, ``k`` (the CVA risk capital requirement =
    DS x K_reduced or DS x K_full) and ``rwa`` (12.5 x k).
    """
    scvas: list[float] = []
    snhs: list[float] = []
    hmas: list[float] = []
    ih = 0.0
    for cp in counterparties:
        if bool(cp.get("index_hedge", False)):
            if "rw" in cp:
                rw_i = float(cp["rw"]) * p.BA_CVA_INDEX_SAME_SECTOR_SCALAR
            else:
                rw_i = counterparty_risk_weight(
                    str(cp.get("sector", "OTHER")), str(cp.get("credit_quality", "HY_NR"))
                )
                if bool(cp.get("homogeneous", True)):
                    rw_i *= p.BA_CVA_INDEX_SAME_SECTOR_SCALAR
            m_i = float(cp["maturity"])
            ih += rw_i * m_i * float(cp["notional"]) * discount_factor(m_i)
            continue
        sector = str(cp.get("sector", "OTHER"))
        quality = str(cp.get("credit_quality", "HY_NR"))
        rw_c = counterparty_risk_weight(sector, quality)
        scvas.append(scva(rw_c, [(float(cp["ead"]), float(cp["maturity"]))], imm_bank))
        notional = float(cp.get("hedge_notional", 0.0))
        if notional > 0.0:
            m_h = float(cp.get("hedge_maturity", cp["maturity"]))
            r_hc = p.BA_CVA_HEDGE_CORRELATION[
                str(cp.get("hedge_reference", "COUNTERPARTY")).upper()
            ]
            rw_h = counterparty_risk_weight(
                str(cp.get("hedge_sector", sector)), str(cp.get("hedge_credit_quality", quality))
            )
            term = rw_h * m_h * notional * discount_factor(m_h)
            snhs.append(r_hc * term)
            hmas.append((1.0 - r_hc**2) * term**2)
        else:
            snhs.append(0.0)
            hmas.append(0.0)
    kr = k_reduced(scvas)
    ds = p.BA_CVA_DISCOUNT_SCALAR
    out: dict[str, float] = {"k_reduced": kr, "discount_scalar": ds}
    if hedged:
        kh = k_hedged(scvas, snhs, ih, hmas)
        kf = p.BA_CVA_BETA * kr + (1.0 - p.BA_CVA_BETA) * kh
        out.update({"k_hedged": kh, "k_full": kf, "k": ds * kf})
    else:
        out["k"] = ds * kr
    out["rwa"] = p.CVA_RWA_MULTIPLIER * out["k"]
    return out


def cva_rwa_ccr_election(non_centrally_cleared_notional: float, ccr_rwa: float) -> float | None:
    """Para 8.5.10 election: CVA RWA = CCR-SA RWA + CCR-IRBA RWA if notional <= S$150bn.

    Reference: MAS Notice 637 paras 8.5.10-8.5.11 (p. 8-180). Returns None if not eligible.
    """
    if non_centrally_cleared_notional <= p.CVA_CCR_ELECTION_NOTIONAL_SGD_M:
        return ccr_rwa
    return None
