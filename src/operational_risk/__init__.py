"""Operational risk module — US ERBA NPR §__.150 (12 CFR 217.150, Subpart E).

Implements the business-indicator-based operational risk capital
requirement of the March 2026 re-proposal:

- RWA_op = 12.5 x BIC; no internal loss multiplier (§__.150(a))
- BIC marginal coefficients 12% / 15% / 18% at $1B / $30B, indexed (§__.150(b))
- BI = interest, lease and dividend component + noninterest component
  (§__.150(c)(1)(i)-(ii))
- Net income from investment management, investment services and
  non-lending treasury services reduced by the 0.7 factor (§__.150(c)(1)(ii))
- Loss event data: $20,000 threshold, ten years, seven §__.101 event types

Exports:
    OpRiskCalculator: Main calculator class
    BusinessIndicatorInputs: Input model (alias: FinancialStatementData)
    ServiceLineData / ServiceLine: Service-line inputs for the 0.7 netting
    OperationalLossData: Loss event data (alias: LossComponentData)
    OpRiskResult: Output model with full breakdown
    OpRiskReportGenerator: Pillar 3 OR1, FFIEC 101 and HC-R reporting
"""

from src.operational_risk.or_calculator import (
    BIComponentBreakdown,
    BusinessIndicatorInputs,
    FinancialStatementData,
    LossComponentData,
    OperationalLossData,
    OpRiskCalculator,
    OpRiskResult,
    ServiceLineData,
)
from src.operational_risk.or_params import (
    BIC_COEFFICIENTS,
    BIC_THRESHOLD_1_USD_M,
    BIC_THRESHOLD_2_USD_M,
    ILDC_INTEREST_CAP_RATE,
    ILM,
    LOSS_COLLECTION_THRESHOLD_USD,
    LOSS_DATA_YEARS,
    NIC_INVESTMENT_MANAGEMENT_FACTOR,
    RWA_CONVERSION_FACTOR,
    SERVICES_NET_INCOME_FACTOR,
    LossEventType,
    ServiceLine,
    compute_bic,
    compute_bic_closed_form,
)
from src.operational_risk.or_reporting import OpRiskReportGenerator

__all__ = [
    "BIC_COEFFICIENTS",
    "BIC_THRESHOLD_1_USD_M",
    "BIC_THRESHOLD_2_USD_M",
    "BIComponentBreakdown",
    "BusinessIndicatorInputs",
    "FinancialStatementData",
    "ILDC_INTEREST_CAP_RATE",
    "ILM",
    "LOSS_COLLECTION_THRESHOLD_USD",
    "LOSS_DATA_YEARS",
    "LossComponentData",
    "LossEventType",
    "NIC_INVESTMENT_MANAGEMENT_FACTOR",
    "OperationalLossData",
    "OpRiskCalculator",
    "OpRiskReportGenerator",
    "OpRiskResult",
    "RWA_CONVERSION_FACTOR",
    "SERVICES_NET_INCOME_FACTOR",
    "ServiceLine",
    "ServiceLineData",
    "compute_bic",
    "compute_bic_closed_form",
]
