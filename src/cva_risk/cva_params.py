"""CVA risk parameters — ERBA NPR §__.220–§__.225 (March 2026 re-proposal).

Defines every supervisory parameter, risk weight table, correlation
parameter and bucket definition used by the basic approach (BA-CVA,
§__.222) and the standardized approach (SA-CVA, §__.224–§__.225) for
credit valuation adjustment risk.

All monetary amounts in USD millions ($M) unless stated otherwise.
Risk weights and correlations are stored as decimals (0.05 == 5%).

References (all section/table citations are to the ERBA NPR rule text,
pp. 950–988 of the March 2026 re-proposal, unless noted):
    - §__.220: scope and definitions for CVA risk
    - §__.222: BA-CVA — K_basic, SCVA_c, hedges; Table 1 (RW_c),
      Table 2 (r_hc)
    - §__.224: SA-CVA general requirements, sensitivity conventions,
      regulatory CVA and MPoR floor
    - §__.225: SA-CVA risk classes, buckets, risk weights and
      correlations; Tables 1–9
    - §__.202 / §__.201(b)(2): CVA risk covered position and scope
    - Preamble §V.B (pp. 434–500): rationale and worked explanations

US-specific points reflected here:
    - Credit quality is the bank's own assessment (investment grade /
      speculative grade / sub-speculative grade as defined in §__.2);
      no external ratings are used (Dodd-Frank §939A).
    - alpha = 1.4 except 1.0 for commercial end-user counterparties
      (§__.114(e)(4)).
    - Government-backed financials sit with financials in BA-CVA Table 1
      but in bucket 1(c) of the SA-CVA counterparty credit spread class.
    - Counterparty credit spread index bucket correlation gamma = 70%
      (raised from the 45% used in the market risk SBM).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Final

import numpy as np

# =========================================================================
#  Enumerations
# =========================================================================

class CVAApproach(Enum):
    """CVA capital approach per ERBA NPR §__.221.

    The basic measure (BA-CVA) is the default. The standardized measure
    (SA-CVA, plus BA-CVA for any carved-out netting sets) requires prior
    written approval from the primary Federal supervisor.

    Following §__.222 and preamble p. 457, the *reduced* BA-CVA is the
    form used when the banking organization recognizes no eligible CVA
    hedges (K_hedged = K_unhedged), and the *full* BA-CVA is the form
    that recognizes eligible hedges.
    """
    BA_CVA_REDUCED = "BA-CVA-REDUCED"
    BA_CVA_FULL = "BA-CVA-FULL"
    SA_CVA = "SA-CVA"


class CVACreditQuality(Enum):
    """Credit quality category of a counterparty or reference name.

    Per ERBA NPR §__.222 Table 1 and §__.225 Tables 3 and 5, risk weights
    are keyed by the banking organization's own classification of the
    obligor as investment grade (§__.2 of the current rule), speculative
    grade or sub-speculative grade (each as defined in §__.2 of the
    proposal). No external ratings are used (Dodd-Frank §939A).
    """
    INVESTMENT_GRADE = "IG"
    SPECULATIVE_GRADE = "SPEC"
    SUB_SPECULATIVE_GRADE = "SUB_SPEC"


class CVASector(Enum):
    """The eight counterparty sectors of ERBA NPR §__.222 Table 1.

    The same sector groupings drive bucket assignment in the SA-CVA
    counterparty credit spread class (§__.225 Table 3) and the reference
    credit spread class (§__.225 Table 5).
    """
    SOVEREIGN_MDB_SUPRANATIONAL = "SOVEREIGN_MDB_SUPRANATIONAL"
    """Sovereign exposures, MDBs and specified supranational entities."""
    PSE_GSE_PUBLIC_ADMIN = "PSE_GSE_PUBLIC_ADMIN"
    """PSEs, government-backed non-financials, GSEs, education and
    public administration."""
    FINANCIALS = "FINANCIALS"
    """Financials including government-backed financials."""
    BASIC_MATERIALS_ENERGY_INDUSTRIALS = "BASIC_MATERIALS_ENERGY_INDUSTRIALS"
    """Basic materials, energy, industrials, agriculture, manufacturing,
    and mining and quarrying."""
    CONSUMER_TRANSPORT_ADMIN = "CONSUMER_TRANSPORT_ADMIN"
    """Consumer goods and services, transportation and storage,
    administrative and support service activities."""
    TECHNOLOGY_TELECOM = "TECHNOLOGY_TELECOM"
    """Technology and telecommunications."""
    HEALTH_UTILITIES_PROFESSIONAL = "HEALTH_UTILITIES_PROFESSIONAL"
    """Health care, utilities, professional and technical activities."""
    OTHER_SECTOR = "OTHER_SECTOR"
    """Other sector."""


class CVAHedgeType(Enum):
    """Eligible BA-CVA hedge instruments per ERBA NPR §__.222(c).

    Under the BA-CVA the only eligible CVA hedges are single-name CDS,
    single-name contingent CDS and index CDS (preamble p. 443). The
    SA-CVA recognizes a broader set of hedges (§__.224(c)); for SA-CVA
    the hedge enters through its sensitivities rather than its type.
    """
    SINGLE_NAME_CDS = "SINGLE_NAME_CDS"
    CONTINGENT_CDS = "CONTINGENT_CDS"
    INDEX_CDS = "INDEX_CDS"


class BACVAHedgeRelationship(Enum):
    """Relationship of a single-name hedge to the hedged counterparty.

    Determines the supervisory correlation r_hc of ERBA NPR §__.222
    Table 2 between the counterparty's credit spread and the hedge.
    """
    DIRECT = "DIRECT"
    """Hedge references counterparty c directly (r_hc = 100%)."""
    AFFILIATE = "AFFILIATE"
    """Hedge references an affiliate of counterparty c (r_hc = 80%)."""
    SAME_SECTOR_REGION = "SAME_SECTOR_REGION"
    """Hedge references an entity in the same sector and region as
    counterparty c (r_hc = 50%). Region means a country or territorial
    entity (preamble fn. 483)."""


class SACVARiskFactorType(Enum):
    """SA-CVA risk classes per ERBA NPR §__.224(b).

    Delta capital requirements are computed for all six classes; vega
    capital requirements for the five exposure-related classes (no vega
    for counterparty credit spread).
    """
    INTEREST_RATE = "INTEREST_RATE"
    FX = "FX"
    COUNTERPARTY_CREDIT_SPREAD = "COUNTERPARTY_CREDIT_SPREAD"
    REFERENCE_CREDIT_SPREAD = "REFERENCE_CREDIT_SPREAD"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"


SACVARiskClass = SACVARiskFactorType
"""Alias: the NPR calls these *risk classes*."""

SA_CVA_DELTA_RISK_CLASSES: Final[tuple[SACVARiskFactorType, ...]] = tuple(
    SACVARiskFactorType
)
"""Six delta risk classes per ERBA NPR §__.224(b)(1)."""

SA_CVA_VEGA_RISK_CLASSES: Final[tuple[SACVARiskFactorType, ...]] = tuple(
    rc for rc in SACVARiskFactorType
    if rc is not SACVARiskFactorType.COUNTERPARTY_CREDIT_SPREAD
)
"""Five vega risk classes per ERBA NPR §__.224(b)(2) — no counterparty
credit spread vega."""


# =========================================================================
#  Credit quality and sector convenience mappers
# =========================================================================

_IG_GRADES: Final[frozenset[str]] = frozenset({
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "UNRATED_IG", "IG", "INVESTMENT_GRADE",
})
_SPEC_GRADES: Final[frozenset[str]] = frozenset({
    "BB+", "BB", "BB-", "B+", "B", "B-",
    "UNRATED_HY", "HY", "SPEC", "SPECULATIVE_GRADE",
})
_SUB_SPEC_GRADES: Final[frozenset[str]] = frozenset({
    "CCC+", "CCC", "CCC-", "CC", "C", "D",
    "SUB_SPEC", "SUB_SPECULATIVE_GRADE",
})


def credit_quality_from_grade(grade: str | CVACreditQuality) -> CVACreditQuality:
    """Map an internal grade label to an ERBA NPR credit quality category.

    Convenience mapper only. Under ERBA NPR §__.2 the classification is the
    banking organization's own assessment of the obligor's capacity to meet
    financial commitments; agency-style labels (``"BBB"``, ``"BB"``, ...)
    are accepted purely as shorthand for the internal grade scale
    (Dodd-Frank §939A — no external ratings are relied upon).

    Mapping: AAA…BBB- → investment grade; BB+…B- → speculative grade;
    CCC+ and below → sub-speculative grade.

    Args:
        grade: Internal grade label or a ``CVACreditQuality`` member.

    Returns:
        The ``CVACreditQuality`` category.

    Raises:
        ValueError: If the label cannot be mapped. An obligor with no
            internal assessment must be assessed before use; the rule text
            provides no default category.
    """
    if isinstance(grade, CVACreditQuality):
        return grade
    key = grade.strip().upper()
    if key in _IG_GRADES:
        return CVACreditQuality.INVESTMENT_GRADE
    if key in _SPEC_GRADES:
        return CVACreditQuality.SPECULATIVE_GRADE
    if key in _SUB_SPEC_GRADES:
        return CVACreditQuality.SUB_SPECULATIVE_GRADE
    raise ValueError(
        f"Cannot map grade {grade!r} to an ERBA NPR credit quality category; "
        "provide INVESTMENT_GRADE, SPECULATIVE_GRADE or SUB_SPECULATIVE_GRADE"
    )


def is_investment_grade(grade: str | CVACreditQuality) -> bool:
    """Return True if the grade maps to investment grade (ERBA NPR §__.2).

    Args:
        grade: Internal grade label or ``CVACreditQuality`` member.

    Returns:
        True for investment grade, False for speculative/sub-speculative.
    """
    return credit_quality_from_grade(grade) is CVACreditQuality.INVESTMENT_GRADE


_SECTOR_ALIASES: Final[dict[str, CVASector]] = {
    # Legacy five-sector labels used elsewhere in the engine; mapped to the
    # ERBA NPR §__.222 Table 1 sector that contains them. A corporate with
    # no finer sector information falls into "other sector", which carries
    # the most conservative non-sovereign risk weights.
    "SOVEREIGN": CVASector.SOVEREIGN_MDB_SUPRANATIONAL,
    "MDB": CVASector.SOVEREIGN_MDB_SUPRANATIONAL,
    "SUPRANATIONAL": CVASector.SOVEREIGN_MDB_SUPRANATIONAL,
    "PUBLIC_SECTOR": CVASector.PSE_GSE_PUBLIC_ADMIN,
    "PSE": CVASector.PSE_GSE_PUBLIC_ADMIN,
    "GSE": CVASector.PSE_GSE_PUBLIC_ADMIN,
    "FINANCIAL": CVASector.FINANCIALS,
    "BANK": CVASector.FINANCIALS,
    "CORPORATE": CVASector.OTHER_SECTOR,
    "OTHER": CVASector.OTHER_SECTOR,
}


def normalize_sector(sector: str | CVASector) -> CVASector:
    """Resolve a sector label to one of the eight ERBA NPR §__.222 sectors.

    Accepts ``CVASector`` members, their ``.value`` strings, or a small set
    of legacy aliases (``"SOVEREIGN"``, ``"FINANCIAL"``, ``"CORPORATE"``,
    ``"PUBLIC_SECTOR"``, ``"OTHER"``). ``"CORPORATE"`` with no finer sector
    information maps to *other sector*.

    Args:
        sector: Sector label.

    Returns:
        The ``CVASector`` member.

    Raises:
        ValueError: If the label is not recognized.
    """
    if isinstance(sector, CVASector):
        return sector
    key = sector.strip().upper()
    try:
        return CVASector(key)
    except ValueError:
        pass
    if key in _SECTOR_ALIASES:
        return _SECTOR_ALIASES[key]
    raise ValueError(
        f"Unknown CVA sector {sector!r}; expected one of "
        f"{[s.value for s in CVASector]}"
    )


# =========================================================================
#  BA-CVA parameters (ERBA NPR §__.222)
# =========================================================================

BA_CVA_DISCOUNT_SCALAR: Final[float] = 0.65
"""Calibration factor applied to the BA-CVA capital requirement.

ERBA NPR §__.222(a): K_basic = 0.65 · (β · K_unhedged + (1 − β) · K_hedged).
Preamble p. 456: the 0.65 scalar calibrates the BA-CVA relative to the
SA-CVA.
"""

BA_CVA_BETA: Final[float] = 0.25
"""Weight of K_unhedged in K_basic per ERBA NPR §__.222(a).

Limits recognized hedge effectiveness to 75% (preamble p. 456): with a
perfect hedge K_basic = 0.65 · 0.25 · K_unhedged.
"""

BA_CVA_RHO: Final[float] = 0.50
"""Supervisory correlation ρ between a counterparty credit spread and the
systematic factor per ERBA NPR §__.222(b). ρ² = 0.25 is the implied
pairwise counterparty correlation (preamble p. 457).
"""

BA_CVA_DISCOUNT_RATE: Final[float] = 0.05
"""Interest rate used in the supervisory discount factor per ERBA NPR
§__.222(b): DF_NS = (1 − e^(−0.05·M_NS)) / (0.05·M_NS).
"""

BA_CVA_ALPHA_DEFAULT: Final[float] = 1.4
"""Alpha used in SCVA_c for counterparties that are not commercial
end-users per ERBA NPR §__.222(b) and §__.114 (SA-CCR alpha).
"""

BA_CVA_ALPHA_COMMERCIAL_END_USER: Final[float] = 1.0
"""Alpha used in SCVA_c for commercial end-user counterparties whose
SA-CCR exposure amount is calculated under ERBA NPR §__.114(e)(4).
"""

# Backward-compatible aliases (same values, SA-CCR naming).
SACCR_ALPHA_FINANCIAL: Final[float] = BA_CVA_ALPHA_DEFAULT
"""Alias of ``BA_CVA_ALPHA_DEFAULT`` (SA-CCR alpha for non-commercial
end-user counterparties)."""

SACCR_ALPHA_COMMERCIAL: Final[float] = BA_CVA_ALPHA_COMMERCIAL_END_USER
"""Alias of ``BA_CVA_ALPHA_COMMERCIAL_END_USER``."""


def get_ba_cva_alpha(is_commercial_end_user: bool) -> float:
    """Return the alpha divisor for SCVA_c per ERBA NPR §__.222(b).

    Args:
        is_commercial_end_user: True if the counterparty is a commercial
            end-user whose exposure amount is determined under §__.114(e)(4).

    Returns:
        1.0 for commercial end-users, otherwise 1.4.
    """
    if is_commercial_end_user:
        return BA_CVA_ALPHA_COMMERCIAL_END_USER
    return BA_CVA_ALPHA_DEFAULT


def get_saccr_alpha(is_financial: bool) -> float:
    """Legacy helper: alpha by financial / commercial end-user flag.

    Per ERBA NPR §__.114 and §__.222(b): alpha = 1.4 unless the
    counterparty is a commercial end-user (alpha = 1.0).

    Args:
        is_financial: True if the counterparty is *not* a commercial
            end-user (historically "financial counterparty").

    Returns:
        1.4 or 1.0.
    """
    return get_ba_cva_alpha(is_commercial_end_user=not is_financial)


BA_CVA_INDEX_HEDGE_FACTOR: Final[float] = 0.7
"""Multiplier applied to Table 1 risk weights for index hedges per ERBA
NPR §__.222(c): RW_i = 0.7 × (bucket RW, or notional-weighted average of
constituent RWs). Recognizes diversification of idiosyncratic risk within
the index (preamble p. 468).
"""

BA_CVA_HEDGE_CORRELATION: Final[Mapping[BACVAHedgeRelationship, float]] = {
    BACVAHedgeRelationship.DIRECT: 1.00,
    BACVAHedgeRelationship.AFFILIATE: 0.80,
    BACVAHedgeRelationship.SAME_SECTOR_REGION: 0.50,
}
"""Table 2 to ERBA NPR §__.222 — supervisory correlation r_hc between the
credit spread of counterparty c and single-name hedge h."""


# ---- Table 1 to §__.222: supervisory risk weights RW_c -------------------

_IG = CVACreditQuality.INVESTMENT_GRADE
_SPEC = CVACreditQuality.SPECULATIVE_GRADE
_SUB = CVACreditQuality.SUB_SPECULATIVE_GRADE


def _row(ig: float, spec: float, sub: float | None = None) -> dict[CVACreditQuality, float]:
    """Build one Table 1 row; spec and sub-spec share a weight unless given."""
    return {_IG: ig, _SPEC: spec, _SUB: spec if sub is None else sub}


BA_CVA_RISK_WEIGHT_TABLE: Final[Mapping[CVASector, Mapping[CVACreditQuality, float]]] = {
    CVASector.SOVEREIGN_MDB_SUPRANATIONAL: _row(0.005, 0.030, 0.070),
    CVASector.PSE_GSE_PUBLIC_ADMIN: _row(0.010, 0.040),
    CVASector.FINANCIALS: _row(0.050, 0.120),
    CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS: _row(0.030, 0.070),
    CVASector.CONSUMER_TRANSPORT_ADMIN: _row(0.030, 0.085),
    CVASector.TECHNOLOGY_TELECOM: _row(0.020, 0.055),
    CVASector.HEALTH_UTILITIES_PROFESSIONAL: _row(0.015, 0.050),
    CVASector.OTHER_SECTOR: _row(0.050, 0.120),
}
"""Table 1 to ERBA NPR §__.222 — supervisory risk weights RW_c by sector
and credit quality (IG / speculative / sub-speculative).

Speculative and sub-speculative grade share one weight in every sector
except sovereigns, MDBs and specified supranationals (3.0% / 7.0%).
"""

BA_CVA_RISK_WEIGHTS: Final[dict[tuple[CVASector, CVACreditQuality], float]] = {
    (sector, quality): rw
    for sector, row in BA_CVA_RISK_WEIGHT_TABLE.items()
    for quality, rw in row.items()
}
"""Flat view of Table 1 to §__.222 keyed by (sector, credit quality)."""


def get_ba_cva_risk_weight(
    sector: str | CVASector,
    credit_quality: str | CVACreditQuality,
) -> float:
    """Look up RW_c from Table 1 to ERBA NPR §__.222.

    Args:
        sector: One of the eight NPR sectors (or a recognized alias).
        credit_quality: Credit quality category or internal grade label.

    Returns:
        Risk weight as a decimal (e.g. 0.05 for financials, IG).
    """
    s = normalize_sector(sector)
    q = credit_quality_from_grade(credit_quality)
    return BA_CVA_RISK_WEIGHT_TABLE[s][q]


# ---- Supervisory discount factor and effective maturity -----------------

def supervisory_discount_factor(maturity: float, rate: float = BA_CVA_DISCOUNT_RATE) -> float:
    """Supervisory discount factor per ERBA NPR §__.222(b).

    DF = (1 − e^(−r·M)) / (r·M) with r = 5%. The rule text applies no floor
    or cap to M; the same formula is used for netting sets (DF_NS),
    single-name hedges (DF_h) and index hedges (DF_i).

    Args:
        maturity: Remaining or effective maturity M in years.
        rate: Discount rate (default 0.05).

    Returns:
        DF in (0, 1]; returns 1.0 for M ≤ 0 (limit of the expression).
    """
    if maturity <= 0.0:
        return 1.0
    x = rate * maturity
    return float((1.0 - math.exp(-x)) / x)


def netting_set_effective_maturity(
    positions: list[tuple[float, float]],
) -> float:
    """Effective maturity M_NS of a netting set per ERBA NPR §__.222(b).

    M_NS is the notional-weighted average remaining maturity, in whole or
    fractional years, of the CVA risk covered positions in the netting set;
    the weight of each position is its notional divided by the aggregate
    notional of the netting set. A single-transaction netting set has
    M_NS equal to the transaction's remaining maturity (preamble fn. 491).
    No floor or cap is applied.

    Args:
        positions: List of (notional in $M, remaining maturity in years).

    Returns:
        M_NS in years.

    Raises:
        ValueError: If the positions list is empty or total notional ≤ 0.
    """
    if not positions:
        raise ValueError("Netting set must contain at least one position")
    total_notional = sum(abs(n) for n, _ in positions)
    if total_notional <= 0.0:
        raise ValueError("Netting set aggregate notional must be positive")
    weighted = sum(abs(n) * m for n, m in positions)
    return weighted / total_notional


# =========================================================================
#  SA-CVA general parameters (ERBA NPR §__.224 / §__.225)
# =========================================================================

SA_CVA_HEDGING_DISALLOWANCE_R: Final[float] = 0.01
"""Hedging disallowance parameter R per ERBA NPR §__.225(a).

K_b = sqrt( Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l + R · Σ_k (WS_k^Hdg)² ).
With perfect hedging the R term floors K_b at 10% of the hedge weighted
sensitivities aggregated as idiosyncratic risk (preamble p. 494).
"""

SA_CVA_MULTIPLIER_DEFAULT: Final[float] = 1.0
"""Default m_CVA per ERBA NPR §__.225(a). The primary Federal supervisor
may require a higher value in writing where CVA model risk warrants.
"""

SA_CVA_DELTA_SHIFT_ABSOLUTE: Final[float] = 0.0001
"""Shift used for interest rate, counterparty credit spread and reference
credit spread delta sensitivities per ERBA NPR §__.224(e): one basis
point (0.0001) absolute, with the CVA change divided by 0.0001.
"""

SA_CVA_DELTA_SHIFT_RELATIVE: Final[float] = 0.01
"""Shift used for FX, equity and commodity delta sensitivities per ERBA
NPR §__.224(e): one percentage point relative, divided by 0.01.
"""

SA_CVA_VEGA_SHIFT_RELATIVE: Final[float] = 0.01
"""Shift used for all vega sensitivities per ERBA NPR §__.224(e): one
percentage point relative change in volatilities, divided by 0.01.
"""

SA_CVA_MPOR_FLOOR_BASE_BUSINESS_DAYS: Final[int] = 9
"""Base of the regulatory margin period of risk floor per ERBA NPR
§__.224(d): MPoR ≥ 9 + N business days, where N is the re-margining
period in business days."""

SA_CVA_MPOR_DAILY_MARGIN_BUSINESS_DAYS: Final[int] = 10
"""MPoR floor for margin agreements with daily or intra-daily exchange of
margin per ERBA NPR §__.224(d) (9 + 1)."""


def regulatory_mpor_floor_business_days(remargining_period_days: int) -> int:
    """Minimum margin period of risk for regulatory CVA per ERBA NPR §__.224(d).

    Args:
        remargining_period_days: Contractual re-margining period N in
            business days (1 for daily or intra-daily margining).

    Returns:
        9 + N business days (10 for daily / intra-daily margining).
    """
    n = max(int(remargining_period_days), 1)
    return SA_CVA_MPOR_FLOOR_BASE_BUSINESS_DAYS + n


def delta_sensitivity(cva_shifted: float, cva_base: float, shift: float) -> float:
    """Finite-difference sensitivity per ERBA NPR §__.224(e).

    s = (CVA(x + shift) − CVA(x)) / shift, with ``shift`` equal to
    ``SA_CVA_DELTA_SHIFT_ABSOLUTE`` (IR and credit), ``SA_CVA_DELTA_SHIFT_RELATIVE``
    (FX, equity, commodity) or ``SA_CVA_VEGA_SHIFT_RELATIVE`` (vega). Smaller
    shifts consistent with internal risk management are permitted.

    Args:
        cva_shifted: Aggregate regulatory CVA (or hedge market value) after
            the shift, in $M.
        cva_base: Aggregate regulatory CVA (or hedge market value) before
            the shift, in $M.
        shift: Shift size used.

    Returns:
        Sensitivity in $M per unit of the risk factor.
    """
    if shift == 0.0:
        raise ValueError("shift must be non-zero")
    return (cva_shifted - cva_base) / shift


# =========================================================================
#  SA-CVA interest rate risk class (§__.225 Table 1 / Table 2)
# =========================================================================

SA_CVA_IR_SPECIFIED_CURRENCIES: Final[frozenset[str]] = frozenset({
    "USD", "AUD", "CAD", "EUR", "JPY", "SEK", "GBP",
})
"""Specified currencies per ERBA NPR §__.225(b)(1): five tenor risk
factors plus inflation. All other currencies use a parallel-shift risk
factor plus inflation."""

SA_CVA_IR_TENORS: Final[tuple[float, ...]] = (1.0, 2.0, 5.0, 10.0, 30.0)
"""Interest rate delta tenor points (years) for specified currencies per
ERBA NPR §__.225(b)(1)."""

SA_CVA_IR_INFLATION_KEY: Final[str] = "INFLATION"
"""Key used for the inflation risk factor of a currency bucket."""

SA_CVA_IR_PARALLEL_KEY: Final[str] = "PARALLEL"
"""Key used for the parallel-shift risk factor of a non-specified
currency bucket."""

SA_CVA_IR_DELTA_RW_SPECIFIED: Final[Mapping[float | str, float]] = {
    1.0: 0.0111,
    2.0: 0.0093,
    5.0: 0.0074,
    10.0: 0.0074,
    30.0: 0.0074,
    SA_CVA_IR_INFLATION_KEY: 0.0111,
}
"""Table 1 to ERBA NPR §__.225 — interest rate delta risk weights for
specified currencies (1y 1.11%, 2y 0.93%, 5y/10y/30y 0.74%, inflation
1.11%)."""

SA_CVA_IR_DELTA_RW_OTHER: Final[float] = 0.0158
"""Interest rate delta risk weight for non-specified currencies per ERBA
NPR §__.225(b)(1): 1.58% for both the parallel shift and inflation."""

SA_CVA_IR_DELTA_RHO_OTHER: Final[float] = 0.40
"""Correlation between the parallel-shift and inflation risk factors of a
non-specified currency per ERBA NPR §__.225(b)(1)."""

_IR_FACTOR_ORDER: Final[tuple[float | str, ...]] = (
    1.0, 2.0, 5.0, 10.0, 30.0, SA_CVA_IR_INFLATION_KEY,
)

SA_CVA_IR_DELTA_CORRELATION_SPECIFIED: Final[np.ndarray] = np.array([
    # 1y    2y    5y    10y   30y   infl
    [1.00, 0.91, 0.72, 0.55, 0.31, 0.40],
    [0.91, 1.00, 0.87, 0.72, 0.45, 0.40],
    [0.72, 0.87, 1.00, 0.91, 0.68, 0.40],
    [0.55, 0.72, 0.91, 1.00, 0.83, 0.40],
    [0.31, 0.45, 0.68, 0.83, 1.00, 0.40],
    [0.40, 0.40, 0.40, 0.40, 0.40, 1.00],
])
"""Table 2 to ERBA NPR §__.225 — intra-bucket correlations ρ_kl among the
five tenor risk factors and inflation for specified currencies. Row/column
order: 1y, 2y, 5y, 10y, 30y, inflation."""


def ir_delta_correlation(
    factor_k: float | str,
    factor_l: float | str,
    specified_currency: bool,
) -> float:
    """Intra-bucket interest rate delta correlation per ERBA NPR §__.225(b)(1).

    Args:
        factor_k: Tenor in years (1, 2, 5, 10, 30), ``"INFLATION"`` or
            ``"PARALLEL"``.
        factor_l: Same.
        specified_currency: True if the currency is in
            ``SA_CVA_IR_SPECIFIED_CURRENCIES``.

    Returns:
        ρ_kl (Table 2 for specified currencies; 40% between parallel and
        inflation otherwise; 1.0 for identical factors).
    """
    if factor_k == factor_l:
        return 1.0
    if specified_currency:
        i = _IR_FACTOR_ORDER.index(factor_k)
        j = _IR_FACTOR_ORDER.index(factor_l)
        return float(SA_CVA_IR_DELTA_CORRELATION_SPECIFIED[i, j])
    return SA_CVA_IR_DELTA_RHO_OTHER


def ir_delta_risk_weight(factor: float | str, specified_currency: bool) -> float:
    """Interest rate delta risk weight per ERBA NPR §__.225 Table 1.

    Args:
        factor: Tenor in years, ``"INFLATION"`` or ``"PARALLEL"``.
        specified_currency: True for USD, AUD, CAD, EUR, JPY, SEK, GBP.

    Returns:
        Risk weight as a decimal.
    """
    if specified_currency:
        return SA_CVA_IR_DELTA_RW_SPECIFIED[factor]
    return SA_CVA_IR_DELTA_RW_OTHER


SA_CVA_IR_GAMMA: Final[float] = 0.50
"""Cross-bucket (cross-currency) correlation γ_bc for interest rate delta
and vega per ERBA NPR §__.225(b)(1)."""

SA_CVA_IR_VEGA_RW: Final[float] = 1.00
"""Interest rate vega risk weight (100%) for both the rate-volatility and
inflation-volatility risk factors per ERBA NPR §__.225(b)(1)."""

SA_CVA_IR_VEGA_RHO: Final[float] = 0.40
"""Intra-bucket correlation between interest rate volatility and inflation
volatility risk factors per ERBA NPR §__.225(b)(1)."""

SA_CVA_IR_VEGA_RATE_KEY: Final[str] = "RATE_VOL"
SA_CVA_IR_VEGA_INFLATION_KEY: Final[str] = "INFLATION_VOL"


# =========================================================================
#  SA-CVA foreign exchange risk class (§__.225(b)(2))
# =========================================================================

SA_CVA_FX_DELTA_RW: Final[float] = 0.11
"""FX delta risk weight (11%) for every currency per ERBA NPR §__.225(b)(2);
a single value regardless of currency pair (preamble fn. 509)."""

SA_CVA_FX_VEGA_RW: Final[float] = 1.00
"""FX vega risk weight (100%) per ERBA NPR §__.225(b)(2)."""

SA_CVA_FX_GAMMA: Final[float] = 0.60
"""Cross-bucket correlation γ_bc for FX delta and vega per ERBA NPR
§__.225(b)(2)."""


# =========================================================================
#  SA-CVA counterparty credit spread risk class (§__.225 Tables 3–4)
# =========================================================================

SA_CVA_CCS_TENORS: Final[tuple[float, ...]] = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Counterparty credit spread delta tenor points (years) per ERBA NPR
§__.225(b)(3)."""

SA_CVA_CCS_INDEX_BUCKET: Final[int] = 8
"""Bucket for credit indices under the optional index treatment per ERBA
NPR §__.225(b)(3) / Table 3."""

SA_CVA_CCS_SECTOR_BUCKET: Final[Mapping[CVASector, int]] = {
    CVASector.SOVEREIGN_MDB_SUPRANATIONAL: 1,
    CVASector.PSE_GSE_PUBLIC_ADMIN: 1,
    CVASector.FINANCIALS: 2,
    CVASector.BASIC_MATERIALS_ENERGY_INDUSTRIALS: 3,
    CVASector.CONSUMER_TRANSPORT_ADMIN: 4,
    CVASector.TECHNOLOGY_TELECOM: 5,
    CVASector.HEALTH_UTILITIES_PROFESSIONAL: 6,
    CVASector.OTHER_SECTOR: 7,
}
"""Table 3 to ERBA NPR §__.225 — bucket by sector. Government-backed
financials are moved from bucket 2 to bucket 1(c) (preamble p. 491); see
``get_ccs_bucket``."""

SA_CVA_CCS_RISK_WEIGHTS: Final[Mapping[int, Mapping[CVACreditQuality, float]]] = {
    2: _row(0.050, 0.120),
    3: _row(0.030, 0.070),
    4: _row(0.030, 0.085),
    5: _row(0.020, 0.055),
    6: _row(0.015, 0.050),
    7: _row(0.050, 0.120),
    8: _row(0.015, 0.050),
}
"""Table 3 to ERBA NPR §__.225 — counterparty credit spread delta risk
weights for buckets 2–8 (IG / speculative-and-sub-speculative). Bucket 1
is split into sub-buckets (a), (b), (c); see ``SA_CVA_CCS_BUCKET1_RISK_WEIGHTS``."""

SA_CVA_CCS_BUCKET1_RISK_WEIGHTS: Final[Mapping[str, Mapping[CVACreditQuality, float]]] = {
    "1a": _row(0.005, 0.030, 0.070),   # sovereigns, MDBs, supranationals
    "1b": _row(0.010, 0.040),          # PSEs, gov-backed non-financials, GSE debt, education, public admin
    "1c": _row(0.050, 0.120),          # government-backed financials
}
"""Table 3 to ERBA NPR §__.225 — bucket 1 sub-bucket risk weights."""


def get_ccs_bucket(
    sector: str | CVASector,
    government_backed_financial: bool = False,
    is_index: bool = False,
) -> int:
    """Assign the SA-CVA counterparty credit spread bucket per Table 3.

    Args:
        sector: Sector of the counterparty or reference name.
        government_backed_financial: True if the entity is a government-backed
            financial (bucket 1(c) rather than bucket 2).
        is_index: True for a credit index under the optional index treatment
            (bucket 8).

    Returns:
        Bucket number 1–8.
    """
    if is_index:
        return SA_CVA_CCS_INDEX_BUCKET
    s = normalize_sector(sector)
    if s is CVASector.FINANCIALS and government_backed_financial:
        return 1
    return SA_CVA_CCS_SECTOR_BUCKET[s]


def get_ccs_risk_weight(
    sector: str | CVASector,
    credit_quality: str | CVACreditQuality,
    government_backed_financial: bool = False,
    is_index: bool = False,
) -> float:
    """Counterparty credit spread delta risk weight per ERBA NPR §__.225 Table 3.

    Args:
        sector: Sector of the entity (ignored for indices).
        credit_quality: Credit quality category.
        government_backed_financial: True for bucket 1(c) entities.
        is_index: True for the index bucket 8.

    Returns:
        Risk weight as a decimal.
    """
    q = credit_quality_from_grade(credit_quality)
    if is_index:
        return SA_CVA_CCS_RISK_WEIGHTS[SA_CVA_CCS_INDEX_BUCKET][q]
    s = normalize_sector(sector)
    bucket = get_ccs_bucket(s, government_backed_financial)
    if bucket == 1:
        if s is CVASector.SOVEREIGN_MDB_SUPRANATIONAL:
            return SA_CVA_CCS_BUCKET1_RISK_WEIGHTS["1a"][q]
        if s is CVASector.PSE_GSE_PUBLIC_ADMIN:
            return SA_CVA_CCS_BUCKET1_RISK_WEIGHTS["1b"][q]
        return SA_CVA_CCS_BUCKET1_RISK_WEIGHTS["1c"][q]
    return SA_CVA_CCS_RISK_WEIGHTS[bucket][q]


SA_CVA_CCS_RHO_TENOR_SAME: Final[float] = 1.00
SA_CVA_CCS_RHO_TENOR_DIFF: Final[float] = 0.90
"""ρ_tenor per ERBA NPR §__.225(b)(3): 100% same tenor, 90% otherwise."""

SA_CVA_CCS_RHO_NAME_SAME: Final[float] = 1.00
SA_CVA_CCS_RHO_NAME_AFFILIATE: Final[float] = 0.90
SA_CVA_CCS_RHO_NAME_DIFF: Final[float] = 0.50
"""ρ_name per ERBA NPR §__.225(b)(3): 100% same entity, 90% affiliates
(legal entities under common control), 50% otherwise."""

SA_CVA_CCS_RHO_INDEX_SAME_SERIES: Final[float] = 1.00
SA_CVA_CCS_RHO_INDEX_SAME_INDEX: Final[float] = 0.90
SA_CVA_CCS_RHO_INDEX_DIFF: Final[float] = 0.80
"""ρ_name within bucket 8 per ERBA NPR §__.225(b)(3): 100% same index and
series, 90% same index different series, 80% otherwise."""

SA_CVA_CCS_RHO_QUALITY_SAME: Final[float] = 1.00
SA_CVA_CCS_RHO_QUALITY_DIFF: Final[float] = 0.80
"""ρ_quality per ERBA NPR §__.225(b)(3): 100% if both names are in the
same credit quality category (speculative and sub-speculative grade form
one category), 80% otherwise."""


def ccs_quality_category(quality: CVACreditQuality) -> str:
    """Collapse the three grades to the two SA-CVA correlation categories.

    Per ERBA NPR §__.225(b)(3) speculative and sub-speculative grade are
    treated as one credit quality category for ρ_quality.
    """
    return "IG" if quality is CVACreditQuality.INVESTMENT_GRADE else "NON_IG"


def _symmetric_from_upper(n: int, upper: Mapping[tuple[int, int], float]) -> np.ndarray:
    """Build an n×n correlation matrix (1-indexed pairs) with unit diagonal."""
    m = np.eye(n)
    for (i, j), v in upper.items():
        m[i - 1, j - 1] = v
        m[j - 1, i - 1] = v
    return m


SA_CVA_CCS_GAMMA: Final[np.ndarray] = _symmetric_from_upper(8, {
    (1, 2): 0.10, (1, 3): 0.20, (1, 4): 0.25, (1, 5): 0.20, (1, 6): 0.15, (1, 7): 0.00, (1, 8): 0.70,
    (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.05, (2, 7): 0.00, (2, 8): 0.70,
    (3, 4): 0.20, (3, 5): 0.25, (3, 6): 0.05, (3, 7): 0.00, (3, 8): 0.70,
    (4, 5): 0.25, (4, 6): 0.05, (4, 7): 0.00, (4, 8): 0.70,
    (5, 6): 0.05, (5, 7): 0.00, (5, 8): 0.70,
    (6, 7): 0.00, (6, 8): 0.70,
    (7, 8): 0.00,
})
"""Table 4 to ERBA NPR §__.225 — cross-bucket correlations γ_bc for the
counterparty credit spread risk class (8×8, 1-indexed buckets). The index
bucket 8 carries 70% with buckets 1–6 (preamble p. 492)."""


def ccs_gamma(bucket_b: int, bucket_c: int) -> float:
    """γ_bc for the counterparty credit spread class per Table 4 to §__.225."""
    return float(SA_CVA_CCS_GAMMA[bucket_b - 1, bucket_c - 1])


# =========================================================================
#  SA-CVA reference credit spread risk class (§__.225 Tables 5–7)
# =========================================================================

SA_CVA_RCS_RISK_WEIGHTS: Final[Mapping[int, Mapping[CVACreditQuality, float]]] = {
    1: _row(0.005, 0.005),
    2: _row(0.010, 0.010),
    3: _row(0.050, 0.050),
    4: _row(0.030, 0.030),
    5: _row(0.030, 0.030),
    6: _row(0.020, 0.020),
    7: _row(0.015, 0.015),
    8: _row(0.030, 0.030, 0.070),
    9: _row(0.040, 0.040),
    10: _row(0.120, 0.120),
    11: _row(0.070, 0.070),
    12: _row(0.085, 0.085),
    13: _row(0.055, 0.055),
    14: _row(0.050, 0.050),
    15: _row(0.120, 0.120),
    16: _row(0.015, 0.015),
    17: _row(0.050, 0.050),
}
"""Table 5 to ERBA NPR §__.225 — reference credit spread delta risk weights
for the 17 buckets. Buckets 1–7: investment grade by sector (sovereigns,
PSE/GSE, financials, basic materials, consumer, technology, health care);
buckets 8–14: the same sectors for speculative and sub-speculative grade
(bucket 8 sovereigns: 3.0% speculative / 7.0% sub-speculative); 15 other
sector; 16 IG indices; 17 speculative / sub-speculative indices. Each
bucket has a single risk factor; the credit quality key matters only for
bucket 8."""

SA_CVA_RCS_VEGA_RW: Final[float] = 1.00
"""Reference credit spread vega risk weight (100%) per ERBA NPR §__.225(b)(4)."""

SA_CVA_RCS_SECTOR_GROUP: Final[Mapping[int, int]] = {
    1: 1, 8: 1,
    2: 2, 9: 2,
    3: 3, 10: 3,
    4: 4, 11: 4,
    5: 5, 12: 5,
    6: 6, 13: 6,
    7: 7, 14: 7,
}
"""Sector group of reference credit spread buckets 1–14 (IG bucket b and
speculative bucket b+7 share a sector)."""

SA_CVA_RCS_IG_BUCKETS: Final[frozenset[int]] = frozenset(range(1, 8)) | {16}
"""Investment grade reference credit spread buckets (1–7 and index bucket 16)."""

_RCS_GROUP_GAMMA_SAME_QUALITY: Final[np.ndarray] = _symmetric_from_upper(7, {
    (1, 2): 0.75, (1, 3): 0.10, (1, 4): 0.20, (1, 5): 0.25, (1, 6): 0.20, (1, 7): 0.15,
    (2, 3): 0.05, (2, 4): 0.15, (2, 5): 0.20, (2, 6): 0.15, (2, 7): 0.10,
    (3, 4): 0.05, (3, 5): 0.15, (3, 6): 0.20, (3, 7): 0.05,
    (4, 5): 0.20, (4, 6): 0.25, (4, 7): 0.05,
    (5, 6): 0.25, (5, 7): 0.05,
    (6, 7): 0.05,
})
"""Table 6 to ERBA NPR §__.225 — cross-bucket correlations between sector
groups for buckets of the *same* credit quality."""

SA_CVA_RCS_GAMMA_SAME_SECTOR_DIFF_QUALITY: Final[float] = 0.50
"""Table 7 to ERBA NPR §__.225 — correlation between the IG and
speculative buckets of the same sector (e.g. buckets 1 and 8)."""

SA_CVA_RCS_GAMMA_DIFF_QUALITY_SCALAR: Final[float] = 0.50
"""Table 7 to ERBA NPR §__.225 — cross-sector correlations for buckets of
different credit quality are one half of the Table 6 values
(37.5 / 5 / 10 / 12.5 / 10 / 7.5 for group 1 vs groups 2–7, etc.)."""

SA_CVA_RCS_GAMMA_INDEX_TO_SINGLE_NAME: Final[float] = 0.45
"""Tables 6/7 to §__.225 — correlation between index buckets 16/17 and
buckets 1–14."""

SA_CVA_RCS_GAMMA_INDEX_TO_INDEX: Final[float] = 0.75
"""Tables 6/7 to §__.225 — correlation between index buckets 16 and 17."""

SA_CVA_RCS_OTHER_BUCKET: Final[int] = 15
"""Bucket 15 (other sector) has γ = 0 with every other bucket."""


def rcs_gamma(bucket_b: int, bucket_c: int) -> float:
    """γ_bc for the reference credit spread class per Tables 6–7 to §__.225.

    Args:
        bucket_b: Bucket 1–17.
        bucket_c: Bucket 1–17.

    Returns:
        Cross-bucket correlation as a decimal (1.0 if b == c).
    """
    if bucket_b == bucket_c:
        return 1.0
    b, c = sorted((bucket_b, bucket_c))
    if SA_CVA_RCS_OTHER_BUCKET in (b, c):
        return 0.0
    if b >= 16:                       # both are index buckets
        return SA_CVA_RCS_GAMMA_INDEX_TO_INDEX
    if c >= 16:                       # index vs single-name bucket
        return SA_CVA_RCS_GAMMA_INDEX_TO_SINGLE_NAME
    gb, gc = SA_CVA_RCS_SECTOR_GROUP[b], SA_CVA_RCS_SECTOR_GROUP[c]
    same_quality = (b in SA_CVA_RCS_IG_BUCKETS) == (c in SA_CVA_RCS_IG_BUCKETS)
    if gb == gc:
        # Same sector, necessarily different quality when b != c.
        return SA_CVA_RCS_GAMMA_SAME_SECTOR_DIFF_QUALITY
    base = float(_RCS_GROUP_GAMMA_SAME_QUALITY[gb - 1, gc - 1])
    return base if same_quality else base * SA_CVA_RCS_GAMMA_DIFF_QUALITY_SCALAR


SA_CVA_RCS_GAMMA: Final[np.ndarray] = np.array(
    [[rcs_gamma(b, c) for c in range(1, 18)] for b in range(1, 18)]
)
"""Full 17×17 reference credit spread γ_bc matrix (Tables 6–7 to §__.225)."""


# =========================================================================
#  SA-CVA equity risk class (§__.225 Table 8)
# =========================================================================

SA_CVA_EQUITY_DELTA_RW: Final[Mapping[int, float]] = {
    1: 0.55,   # EM, large cap: consumer goods/services, transportation, admin, health, utilities
    2: 0.60,   # EM, large cap: telecom, industrials
    3: 0.45,   # EM, large cap: basic materials, energy, agriculture, manufacturing, mining
    4: 0.55,   # EM, large cap: financials, real estate, technology
    5: 0.30,   # liquid market, large cap: consumer/transport/admin/health/utilities
    6: 0.35,   # liquid market, large cap: telecom, industrials
    7: 0.40,   # liquid market, large cap: basic materials, energy, agri, manufacturing, mining
    8: 0.50,   # liquid market, large cap: financials, real estate, technology
    9: 0.70,   # EM, small cap
    10: 0.50,  # liquid market, small cap
    11: 0.70,  # other sector
    12: 0.15,  # large-liquid-market indices
    13: 0.25,  # other indices
}
"""Table 8 to ERBA NPR §__.225 — equity delta risk weights by bucket
(one risk factor per bucket; same buckets as the market risk SBM)."""

SA_CVA_EQUITY_LARGE_CAP_BUCKETS: Final[frozenset[int]] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 12, 13})
"""Large-cap and index buckets with vega RW 78% per ERBA NPR §__.225(b)(5)."""

SA_CVA_EQUITY_VEGA_RW_LARGE_CAP: Final[float] = 0.78
SA_CVA_EQUITY_VEGA_RW_OTHER: Final[float] = 1.00
"""Equity vega risk weights per ERBA NPR §__.225(b)(5): 78% for large-cap
buckets (1–8, 12, 13), 100% otherwise (9, 10, 11)."""

SA_CVA_EQUITY_GAMMA_SINGLE_NAME: Final[float] = 0.15
SA_CVA_EQUITY_GAMMA_INDEX_INDEX: Final[float] = 0.75
SA_CVA_EQUITY_GAMMA_INDEX_SINGLE: Final[float] = 0.45
SA_CVA_EQUITY_OTHER_BUCKET: Final[int] = 11


def equity_vega_risk_weight(bucket: int) -> float:
    """Equity vega risk weight per ERBA NPR §__.225(b)(5)."""
    if bucket in SA_CVA_EQUITY_LARGE_CAP_BUCKETS:
        return SA_CVA_EQUITY_VEGA_RW_LARGE_CAP
    return SA_CVA_EQUITY_VEGA_RW_OTHER


def equity_gamma(bucket_b: int, bucket_c: int) -> float:
    """γ_bc for the equity class per ERBA NPR §__.225(b)(5).

    15% between buckets 1–10; 0% for bucket 11 with any other bucket;
    75% between index buckets 12 and 13; 45% between an index bucket and
    buckets 1–10.
    """
    if bucket_b == bucket_c:
        return 1.0
    b, c = sorted((bucket_b, bucket_c))
    if SA_CVA_EQUITY_OTHER_BUCKET in (b, c):
        return 0.0
    if b >= 12:
        return SA_CVA_EQUITY_GAMMA_INDEX_INDEX
    if c >= 12:
        return SA_CVA_EQUITY_GAMMA_INDEX_SINGLE
    return SA_CVA_EQUITY_GAMMA_SINGLE_NAME


# =========================================================================
#  SA-CVA commodity risk class (§__.225 Table 9)
# =========================================================================

SA_CVA_COMMODITY_DELTA_RW: Final[Mapping[int, float]] = {
    1: 0.30,   # energy – solid combustibles
    2: 0.35,   # energy – liquid combustibles
    3: 0.60,   # energy – electricity and carbon trading
    4: 0.80,   # freight
    5: 0.40,   # metals – non-precious
    6: 0.45,   # gaseous combustibles
    7: 0.20,   # precious metals (incl. gold)
    8: 0.35,   # grains and oilseed
    9: 0.25,   # livestock and dairy
    10: 0.35,  # softs and other agriculturals
    11: 0.50,  # other commodity
    12: 0.30,  # commodity indices
}
"""Table 9 to ERBA NPR §__.225 — commodity delta risk weights by bucket
(one risk factor per bucket; same buckets as the market risk SBM)."""

SA_CVA_COMMODITY_VEGA_RW: Final[float] = 1.00
"""Commodity vega risk weight (100%) per ERBA NPR §__.225(b)(6)."""

SA_CVA_COMMODITY_GAMMA: Final[float] = 0.20
SA_CVA_COMMODITY_OTHER_BUCKET: Final[int] = 11


def commodity_gamma(bucket_b: int, bucket_c: int) -> float:
    """γ_bc for the commodity class per ERBA NPR §__.225(b)(6).

    20% between any two of buckets 1–10 and 12; 0% for bucket 11 with any
    other bucket.
    """
    if bucket_b == bucket_c:
        return 1.0
    if SA_CVA_COMMODITY_OTHER_BUCKET in (bucket_b, bucket_c):
        return 0.0
    return SA_CVA_COMMODITY_GAMMA


# =========================================================================
#  Scope (§__.201(b)(2) / §__.202)
# =========================================================================

CVA_SCOPE_OTC_NOTIONAL_THRESHOLD: Final[float] = 1_000_000.0
"""Average aggregate OTC derivative gross notional threshold, $M ($1
trillion, CPI-W indexed), above which a banking organization subject to
market risk capital requirements is subject to CVA risk capital
requirements per ERBA NPR §__.201(b)(2). The threshold is a four-quarter
average."""

CVA_SCOPE_AVERAGING_QUARTERS: Final[int] = 4
"""Number of consecutive quarters averaged for the notional threshold."""


# =========================================================================
#  RWA conversion
# =========================================================================

RWA_MULTIPLIER: Final[float] = 12.5
"""RWA_CVA = 12.5 × K per ERBA NPR §__.221 (preamble p. 455)."""
