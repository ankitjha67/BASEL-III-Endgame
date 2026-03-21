"""Regulatory lookup tables for Basel III Endgame SA-CR risk weights.

Provides risk weight lookup by counterparty type and other regulatory
classification parameters. All risk weights per the 2026 US re-proposal.

Key regulatory references:
- ERBA NPR pp. 100-160: SA-CR risk weight tables
- 12 CFR 217.32: Risk-weighted assets for general risk weights
- Dodd-Frank Section 939A: No external ratings for corporates
- CLAUDE.md: Corporate IG = 65%, Retail transactor = 45%, MSA = 250%

All monetary amounts in USD millions ($M) unless explicitly stated otherwise.
"""

from __future__ import annotations

from typing import Optional

from src.reference_data.counterparty_reference import (
    CounterpartyType,
    SovereignRiskCategory,
)


# =============================================================================
#  SA-CR Risk Weight Tables
# =============================================================================

# Sovereign risk weights by CRC category
# Per ERBA NPR pp. 102-105 and 12 CFR 217.32(a)
SOVEREIGN_RISK_WEIGHTS: dict[SovereignRiskCategory, float] = {
    SovereignRiskCategory.CRC_0_1: 0.0,      # US, G7, low-risk OECD
    SovereignRiskCategory.CRC_2: 0.20,        # 20%
    SovereignRiskCategory.CRC_3: 0.50,        # 50%
    SovereignRiskCategory.CRC_4_6: 1.00,      # 100%
    SovereignRiskCategory.CRC_7: 1.50,        # 150%
    SovereignRiskCategory.UNRATED: 1.00,       # 100% conservative
}

# Base risk weights by counterparty type
# Per ERBA NPR pp. 100-160 and 12 CFR 217.32
# Note: Corporate IG = 65% (self-assessment, no external ratings per Dodd-Frank 939A)
# Note: Retail transactor = 45% (not 55% from 2023 NPR) per CLAUDE.md
# Note: MSA = 250% RW (deduction removed) per CLAUDE.md
SA_CR_RISK_WEIGHTS: dict[CounterpartyType, float] = {
    CounterpartyType.SOVEREIGN: 0.0,            # Placeholder — use sovereign lookup
    CounterpartyType.PSE: 0.20,                 # Per 12 CFR 217.32(c) — US PSE
    CounterpartyType.MDB: 0.0,                  # Qualifying MDB per 12 CFR 217.32(b)
    CounterpartyType.BANK: 0.20,                # Short-term per 12 CFR 217.32(d)
    CounterpartyType.COVERED_BOND: 0.10,        # IG covered bonds per ERBA NPR p.125
    CounterpartyType.CORPORATE: 1.00,           # General corporate per 12 CFR 217.32(e)
    CounterpartyType.CORPORATE_IG: 0.65,        # IG self-assessment per ERBA NPR p.112
    CounterpartyType.SME: 0.85,                 # SME corporate per ERBA NPR p.118
    CounterpartyType.SME_RETAIL: 0.75,          # SME retail per ERBA NPR p.120
    CounterpartyType.RETAIL: 0.75,              # Other retail per 12 CFR 217.32(g)
    CounterpartyType.RETAIL_MORTGAGE: 0.50,     # Placeholder — LTV-based, see table below
    CounterpartyType.RETAIL_TRANSACTOR: 0.45,   # Per CLAUDE.md (not 55% from 2023 NPR)
    CounterpartyType.CRE: 1.00,                 # Placeholder — LTV-based, see table below
    CounterpartyType.ADC: 1.50,                 # ADC per ERBA NPR p.145
    CounterpartyType.SUBORDINATED_DEBT: 1.50,   # Per 12 CFR 217.32(l)
    CounterpartyType.EQUITY: 2.50,              # Per ERBA NPR p.155 (listed equity)
    CounterpartyType.CCP_QUALIFYING: 0.02,      # 2% per 12 CFR 217.35
    CounterpartyType.CCP_NON_QUALIFYING: 1.00,  # Non-qualifying CCP
    CounterpartyType.DEFAULTED: 1.50,           # Per 12 CFR 217.32(k)
    CounterpartyType.MSA: 2.50,                 # 250% RW (deduction removed) per CLAUDE.md
    CounterpartyType.OTHER: 1.00,               # Conservative default
}

# Residential mortgage risk weights by LTV bucket
# Per ERBA NPR pp. 140-145 — Table 3
# LTV thresholds and corresponding risk weights
RESIDENTIAL_MORTGAGE_RW_BY_LTV: list[tuple[float, float]] = [
    (0.50, 0.20),    # LTV <= 50%: 20% RW
    (0.60, 0.25),    # 50% < LTV <= 60%: 25% RW
    (0.70, 0.30),    # 60% < LTV <= 70%: 30% RW
    (0.80, 0.40),    # 70% < LTV <= 80%: 40% RW
    (0.90, 0.50),    # 80% < LTV <= 90%: 50% RW
    (1.00, 0.70),    # 90% < LTV <= 100%: 70% RW
    (float("inf"), 1.00),  # LTV > 100%: 100% RW (whole-loan approach)
]

# Commercial real estate risk weights by LTV bucket
# Per ERBA NPR pp. 145-148 — Table 4
CRE_RW_BY_LTV: list[tuple[float, float]] = [
    (0.60, 0.70),    # LTV <= 60%: 70% RW
    (0.80, 0.90),    # 60% < LTV <= 80%: 90% RW
    (float("inf"), 1.10),  # LTV > 80%: 110% RW
]

# Bank risk weights by maturity
# Per ERBA NPR p.108 and 12 CFR 217.32(d)
# TODO: VERIFY — exact maturity buckets for bank exposures under 2026 re-proposal
BANK_RW_BY_MATURITY: list[tuple[float, float]] = [
    (0.25, 0.20),    # <= 3 months (short-term claims)
    (float("inf"), 0.20),  # > 3 months — 20% base for US banks
]


# =============================================================================
#  Lookup Functions
# =============================================================================

def get_risk_weight(
    counterparty_type: CounterpartyType,
    sovereign_risk_category: Optional[SovereignRiskCategory] = None,
    ltv_ratio: Optional[float] = None,
    remaining_maturity_years: Optional[float] = None,
) -> float:
    """Look up SA-CR risk weight for a given counterparty classification.

    Implements the risk weight assignment per 12 CFR 217.32 and ERBA NPR
    Tables 2-5. For sovereigns, uses CRC-based lookup. For real estate,
    uses LTV-based risk weight schedules.

    Note: Per Dodd-Frank Section 939A, corporate risk weights do NOT
    depend on external credit ratings. IG status is self-assessed.

    Reference: ERBA NPR pp. 100-160, 12 CFR 217.32.

    Args:
        counterparty_type: SA-CR classification.
        sovereign_risk_category: CRC category for sovereigns.
        ltv_ratio: Loan-to-value ratio for real estate exposures.
        remaining_maturity_years: Remaining maturity for bank exposures.

    Returns:
        Risk weight as a decimal (e.g., 0.65 for 65%).
    """
    # Sovereign — CRC-based lookup
    if counterparty_type == CounterpartyType.SOVEREIGN:
        if sovereign_risk_category is not None:
            return SOVEREIGN_RISK_WEIGHTS.get(sovereign_risk_category, 1.00)
        return 0.0  # US sovereign default

    # Residential mortgage — LTV-based
    if counterparty_type == CounterpartyType.RETAIL_MORTGAGE and ltv_ratio is not None:
        return _lookup_ltv_rw(ltv_ratio, RESIDENTIAL_MORTGAGE_RW_BY_LTV)

    # CRE — LTV-based
    if counterparty_type == CounterpartyType.CRE and ltv_ratio is not None:
        return _lookup_ltv_rw(ltv_ratio, CRE_RW_BY_LTV)

    # Bank — maturity-based
    if counterparty_type == CounterpartyType.BANK and remaining_maturity_years is not None:
        return _lookup_maturity_rw(remaining_maturity_years, BANK_RW_BY_MATURITY)

    # All others — direct lookup
    return SA_CR_RISK_WEIGHTS.get(counterparty_type, 1.00)


def _lookup_ltv_rw(
    ltv: float,
    table: list[tuple[float, float]],
) -> float:
    """Look up risk weight from an LTV-based table.

    Reference: ERBA NPR pp. 140-148 — LTV-based risk weight schedules.

    Args:
        ltv: Loan-to-value ratio (e.g., 0.75 for 75%).
        table: List of (ltv_threshold, risk_weight) tuples, sorted ascending.

    Returns:
        Applicable risk weight.
    """
    for threshold, rw in table:
        if ltv <= threshold:
            return rw
    # Should not reach here if table includes inf
    return table[-1][1]


def _lookup_maturity_rw(
    maturity_years: float,
    table: list[tuple[float, float]],
) -> float:
    """Look up risk weight from a maturity-based table.

    Reference: ERBA NPR p.108 — bank exposure maturity buckets.

    Args:
        maturity_years: Remaining maturity in years.
        table: List of (maturity_threshold, risk_weight) tuples, sorted ascending.

    Returns:
        Applicable risk weight.
    """
    for threshold, rw in table:
        if maturity_years <= threshold:
            return rw
    return table[-1][1]
