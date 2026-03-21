"""Operational Risk module — Standardized Measurement Approach (SMA).

Implements operational risk capital calculation per BCBS d424 Section 5
and the US Basel III Endgame March 2026 Re-Proposal.

Key features:
- Business Indicator (BI) = ILDC + SC + FC
- BIC marginal coefficients: 12% / 15% / 18% at $1B / $30B thresholds
- ILM = 1.0 (NOT applied per US 2026 proposal)
- NIC uses NET basis with 0.7x factor for investment management

Exports:
    OpRiskCalculator: Main calculator class
    FinancialStatementData: Input model for financial statements
    OpRiskResult: Output model with full breakdown
    NICCalculator: Net Interest Component calculator
    OpRiskReportGenerator: Pillar 3 OR1 and FFIEC reporting
"""

from src.operational_risk.or_calculator import (
    FinancialStatementData,
    InvestmentManagementData,
    LossComponentData,
    NICCalculator,
    OpRiskCalculator,
    OpRiskResult,
)
from src.operational_risk.or_params import (
    BIC_COEFFICIENTS,
    ILDC_INTEREST_CAP_RATE,
    ILM,
    NIC_INVESTMENT_MANAGEMENT_FACTOR,
    compute_bic,
)
from src.operational_risk.or_reporting import OpRiskReportGenerator

__all__ = [
    "BIC_COEFFICIENTS",
    "FinancialStatementData",
    "ILDC_INTEREST_CAP_RATE",
    "ILM",
    "InvestmentManagementData",
    "LossComponentData",
    "NIC_INVESTMENT_MANAGEMENT_FACTOR",
    "NICCalculator",
    "OpRiskCalculator",
    "OpRiskReportGenerator",
    "OpRiskResult",
    "compute_bic",
]
