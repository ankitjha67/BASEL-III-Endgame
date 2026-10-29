"""UK CVA risk -- the PRA Rulebook Credit Valuation Adjustment Risk Part.

PS1/26 Appendix 1 Annex K (p. 393-425) introduces this Part (Annex Q deletes the
old CVA Risk (CRR) Part). Implemented here:

* BA-CVA reduced version (rules 4.2-4.4):
      K_reduced = sqrt((rho * sum_c SCVA_c)^2 + (1 - rho^2) * sum_c SCVA_c^2),  rho = 50%
      SCVA_c   = (1/alpha) * RW_c * sum_NS M_NS * EAD_NS * DF_NS
      DF_NS    = (1 - exp(-0.05 M)) / (0.05 M)   (1 for IMM firms)
      own funds = DS * K_reduced,  DS = 0.65
* BA-CVA full version (rules 4.5-4.10):
      K_full   = beta * K_reduced + (1 - beta) * K_hedged,  beta = 0.25
      K_hedged = sqrt((rho * sum(SCVA_c - SNH_c) - IH)^2 + (1 - rho^2) * sum(SCVA_c - SNH_c)^2
                      + sum HMA_c)
* the rule 4.4 risk-weight table -- which, unlike BCBS MAR50.16, carries a
  separate 'pension funds' row (3.5% IG / 8.5% HY-NR) and excludes pension
  funds from 'financials';
* the alternative approach (rules 6.1-6.4): firms with non-centrally-cleared
  derivative notional < GBP 88bn may hold 100% of their CCR own funds requirement;
* the transitional provisions (rules 7.1-7.5): legacy exemption of pre-2027
  trades with NFCs / pension schemes / exempt sovereigns until 1 January 2030,
  or the final discount scalar.

RWA = 12.5 x own funds requirement (Required Level of Own Funds (CRR) Part
Art 92(3)(d), 92(4)(b)).

References:
    - PRA Rulebook Credit Valuation Adjustment Risk Part, rules 3.1-3.6, 4.1-4.10, 6.1-6.4, 7.1-7.5
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from src.jurisdictions.uk import params as p

CVA_PART: Final[str] = "PRA Rulebook Credit Valuation Adjustment Risk Part"

SECTOR_ALIASES: Final[Mapping[str, str]] = {
    "SOVEREIGN": "SOVEREIGN",
    "CENTRAL_BANK": "SOVEREIGN",
    "MDB": "SOVEREIGN",
    "LOCAL_GOVERNMENT": "LOCAL_GOVERNMENT",
    "PSE": "LOCAL_GOVERNMENT",
    "EDUCATION": "LOCAL_GOVERNMENT",
    "FINANCIAL": "FINANCIAL",
    "FINANCIALS": "FINANCIAL",
    "PENSION_FUND": "PENSION_FUND",
    "PENSION": "PENSION_FUND",
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
"""Convenience aliases onto the rule 4.4 sector rows (no regulatory content)."""


def _sector_key(sector: str) -> str:
    """Normalise a sector label to a rule 4.4 row key (unknown -> 'OTHER', rule 4.4 'Other
    sector')."""
    return SECTOR_ALIASES.get(sector.strip().upper(), "OTHER")


def _quality_key(credit_quality: str) -> str:
    """'IG' or 'HY_NR' per the rule 4.4 columns ('Investment grade' / 'High yield and
    Non-rated')."""
    return "IG" if credit_quality.strip().upper() in ("IG", "INVESTMENT_GRADE") else "HY_NR"


def risk_weight(sector: str, credit_quality: str) -> float:
    """RW_C from the rule 4.4 table (p. 401)."""
    return p.BA_CVA_RISK_WEIGHTS[_sector_key(sector)][_quality_key(credit_quality)]


def discount_factor(maturity: float, imm: bool = False) -> float:
    """Supervisory discount factor -- rule 4.3 DF_NS (p. 400); also rules 4.7, 4.8 for hedges.

    DF = 1 for a firm with IMM permission (Art 283 CRR); otherwise
    (1 - exp(-0.05 M)) / (0.05 M).
    """
    if imm:
        return 1.0
    if maturity <= 0.0:
        return 1.0
    r = p.BA_CVA_DISCOUNT_RATE * maturity
    return (1.0 - math.exp(-r)) / r


@dataclass(frozen=True)
class NettingSet:
    """One netting set of a counterparty for BA-CVA (rule 4.3 inputs)."""

    ead: float
    maturity: float
    imm: bool = False


def scva(rw: float, netting_sets: Sequence[NettingSet], alpha: float = p.SACCR_ALPHA) -> float:
    """SCVA_c = (1/alpha) * RW_c * sum_NS M_NS * EAD_NS * DF_NS -- rule 4.3 (p. 400).

    ``alpha`` is the CCR Part alpha used to compute EAD (1.4, or 1 for NFC /
    pension scheme counterparties, CCR Part Art 274(2)).
    """
    return (
        rw
        / alpha
        * sum(ns.maturity * ns.ead * discount_factor(ns.maturity, ns.imm) for ns in netting_sets)
    )


def k_reduced(scvas: Sequence[float]) -> float:
    """K_reduced = sqrt((rho * sum SCVA)^2 + (1 - rho^2) * sum SCVA^2) -- rule 4.2 (p. 399)."""
    rho = p.BA_CVA_RHO
    return math.sqrt((rho * sum(scvas)) ** 2 + (1.0 - rho**2) * sum(s * s for s in scvas))


@dataclass(frozen=True)
class SingleNameHedge:
    """A single-name eligible BA-CVA hedge (rule 4.7 inputs; definition in rule 1.2)."""

    counterparty: str
    notional: float
    maturity: float
    rw: float
    relation: str = "DIRECT"
    """'DIRECT', 'LEGALLY_RELATED' or 'SECTOR_REGION' (rule 4.10)."""


@dataclass(frozen=True)
class IndexHedge:
    """An index eligible BA-CVA hedge (rule 4.8 inputs)."""

    notional: float
    maturity: float
    constituent_rws: tuple[float, ...]
    """Rule 4.4 RWs of the constituents (one value if homogeneous)."""

    def rw(self) -> float:
        """RW_ind = (name-weighted) average rule 4.4 RW x 0.7 -- rule 4.8(1)-(2) (p. 403)."""
        return p.BA_CVA_INDEX_RW_SCALAR * sum(self.constituent_rws) / len(self.constituent_rws)


def _hedge_term(h: SingleNameHedge) -> float:
    """RW_h * M_h * B_h * DF_h (rules 4.7, 4.9)."""
    return h.rw * h.maturity * h.notional * discount_factor(h.maturity)


def snh(hedges: Sequence[SingleNameHedge]) -> float:
    """SNH_c = sum_h r_hc * RW_h * M_h * B_h * DF_h -- rule 4.7 (p. 402)."""
    return sum(p.BA_CVA_HEDGE_CORRELATION[h.relation] * _hedge_term(h) for h in hedges)


def hma(hedges: Sequence[SingleNameHedge]) -> float:
    """HMA_c = sum_h (1 - r_hc^2) * (RW_h * M_h * B_h * DF_h)^2 -- rule 4.9 (p. 403).

    The extracted text shows '(1 - r_hc)' with a detached superscript 2; the
    squared correlation is used (consistent with BCBS MAR50.23).
    # TODO: VERIFY -- confirm the exponent placement in rule 4.9 against the PDF.
    """
    return sum(
        (1.0 - p.BA_CVA_HEDGE_CORRELATION[h.relation] ** 2) * _hedge_term(h) ** 2 for h in hedges
    )


def index_hedge_total(index_hedges: Sequence[IndexHedge]) -> float:
    """IH = sum_i RW_i * M_i * B_i * DF_i -- rule 4.8 (p. 402-403)."""
    return sum(i.rw() * i.maturity * i.notional * discount_factor(i.maturity) for i in index_hedges)


def k_hedged(
    scvas: Mapping[str, float],
    single_name: Sequence[SingleNameHedge],
    index_hedges: Sequence[IndexHedge] = (),
) -> float:
    """K_hedged -- rule 4.6 (p. 401-402)."""
    rho = p.BA_CVA_RHO
    net = {c: s - snh([h for h in single_name if h.counterparty == c]) for c, s in scvas.items()}
    ih = index_hedge_total(index_hedges)
    hma_total = sum(hma([h for h in single_name if h.counterparty == c]) for c in scvas)
    systematic = (rho * sum(net.values()) - ih) ** 2
    idiosyncratic = (1.0 - rho**2) * sum(v * v for v in net.values())
    return math.sqrt(systematic + idiosyncratic + hma_total)


def _alpha_from_dict(cp: Mapping[str, float | str | bool]) -> float:
    """Alpha for a counterparty dict: explicit 'alpha', or 1 for NFC / pension (CCR Part Art
    274(2))."""
    if "alpha" in cp:
        return float(cp["alpha"])
    if bool(cp.get("nonfinancial", False)) or bool(cp.get("pension", False)):
        return p.SACCR_ALPHA_NFC_PENSION
    if _sector_key(str(cp.get("sector", "OTHER"))) == "PENSION_FUND":
        return p.SACCR_ALPHA_NFC_PENSION
    return p.SACCR_ALPHA


def ba_cva(
    counterparties: Sequence[Mapping[str, float | str | bool]],
    hedged: bool = False,
    index_hedges: Sequence[IndexHedge] = (),
) -> dict[str, float]:
    """BA-CVA own funds requirement (reduced, or full if ``hedged``) -- rules 4.2-4.10.

    Each counterparty dict: ``ead``, ``maturity``, ``sector``, ``credit_quality``
    and optionally ``id``, ``alpha`` / ``nonfinancial`` / ``pension`` (see
    :func:`_alpha_from_dict`), ``imm`` (DF = 1), and one single-name hedge:
    ``hedge_notional``, ``hedge_maturity``, ``hedge_relation`` (rule 4.10 key),
    ``hedge_sector`` / ``hedge_credit_quality`` (default: the counterparty's).
    Several dicts with the same ``id`` are netting sets of one counterparty.

    Returns ``k_reduced``, ``k_hedged``, ``k_full``, ``k`` (= DS x K, the own
    funds requirement), ``rwa`` (= 12.5 x k), ``ds``.
    """
    per_cp: dict[str, list[NettingSet]] = {}
    meta: dict[str, tuple[float, float]] = {}
    hedges: list[SingleNameHedge] = []
    for i, cp in enumerate(counterparties):
        cid = str(cp.get("id", f"cp{i}"))
        per_cp.setdefault(cid, []).append(
            NettingSet(float(cp["ead"]), float(cp["maturity"]), bool(cp.get("imm", False)))
        )
        rw = risk_weight(str(cp.get("sector", "OTHER")), str(cp.get("credit_quality", "HY_NR")))
        meta[cid] = (rw, _alpha_from_dict(cp))
        if hedged and float(cp.get("hedge_notional", 0.0)) > 0.0:
            h_rw = risk_weight(
                str(cp.get("hedge_sector", cp.get("sector", "OTHER"))),
                str(cp.get("hedge_credit_quality", cp.get("credit_quality", "HY_NR"))),
            )
            hedges.append(
                SingleNameHedge(
                    counterparty=cid,
                    notional=float(cp["hedge_notional"]),
                    maturity=float(cp.get("hedge_maturity", cp["maturity"])),
                    rw=h_rw,
                    relation=str(cp.get("hedge_relation", "DIRECT")).upper(),
                )
            )
    scvas = {c: scva(meta[c][0], ns, meta[c][1]) for c, ns in per_cp.items()}
    kr = k_reduced(list(scvas.values()))
    use_full = hedged and (bool(hedges) or bool(index_hedges))
    kh = k_hedged(scvas, hedges, index_hedges) if use_full else kr
    kf = p.BA_CVA_BETA * kr + (1.0 - p.BA_CVA_BETA) * kh if use_full else kr
    k = p.BA_CVA_DS * kf
    return {
        "k_reduced": kr,
        "k_hedged": kh,
        "k_full": kf,
        "ds": p.BA_CVA_DS,
        "k": k,
        "capital": k,
        "rwa": p.OWN_FUNDS_TO_RWA_MULTIPLIER * k,
    }


def alternative_approach(
    ccr_own_funds_requirement: float, uncleared_notional: float, sa_cva_permission: bool = False
) -> float | None:
    """Alternative approach -- rules 6.1-6.3 (p. 422-423).

    Available if non-centrally cleared derivative notional < GBP 88bn and the
    firm has no SA-CVA permission; the CVA own funds requirement is then 100% of
    the CCR own funds requirement (no hedge recognition, whole portfolio).
    Returns None when the approach is not available.
    """
    if sa_cva_permission or uncleared_notional >= p.CVA_ALTERNATIVE_APPROACH_NOTIONAL_GBP_M:
        return None
    return p.CVA_ALTERNATIVE_APPROACH_CCR_SHARE * ccr_own_funds_requirement


def intermediate_discount_scalar(year: int, k1_b31_scope: float, k1_crr_scope: float) -> float:
    """Intermediate discount scalar omega_bar_t -- rule 7.2 (p. 423-424).

        omega_bar_t = max(omega_t,
                          100% - (K1_b31 - K1_CRR) / K1_b31 * (5 - t)/5 * (1 - omega_t)/(1 - omega))

    with omega_t = 70/80/90% (2027/28/29), t = 2/3/4, omega = 0.5.
    # TODO: VERIFY -- reconstructed from a garbled two-dimensional formula in the
    text extraction; confirm term placement against the PDF of rule 7.2.
    """
    if year not in p.CVA_TRANSITIONAL_WEIGHTING_CAP:
        return 1.0
    w_t = p.CVA_TRANSITIONAL_WEIGHTING_CAP[year]
    t = p.CVA_TRANSITIONAL_ELAPSED_T[year]
    legacy_ratio = (k1_b31_scope - k1_crr_scope) / k1_b31_scope if k1_b31_scope else 0.0
    time_factor = (p.CVA_TRANSITIONAL_HORIZON_YEARS - t) / p.CVA_TRANSITIONAL_HORIZON_YEARS
    weighting = (1.0 - w_t) / (1.0 - p.CVA_TRANSITIONAL_OMEGA)
    return max(w_t, 1.0 - legacy_ratio * time_factor * weighting)


def final_discount_scalar(
    year: int, k1_b31_scope: float, k1_crr_scope: float, kt_b31_scope: float
) -> float:
    """Final discount scalar omega_hat_T -- rule 7.1(2) (p. 423).

        omega_hat_T = max(omega_bar_t, (K1_b31 * omega_bar_t + (K_T_b31 - K1_b31)) / K_T_b31)

    # TODO: VERIFY -- reconstructed from a garbled formula in the text extraction.
    """
    w_bar = intermediate_discount_scalar(year, k1_b31_scope, k1_crr_scope)
    if year not in p.CVA_TRANSITIONAL_WEIGHTING_CAP or kt_b31_scope <= 0.0:
        return w_bar
    return max(w_bar, (k1_b31_scope * w_bar + (kt_b31_scope - k1_b31_scope)) / kt_b31_scope)
