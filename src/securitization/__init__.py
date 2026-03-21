"""Securitization module — SEC-SA, SEC-ERBA, and STC framework.

Implements securitization risk weight calculations per BCBS d424 CRE40
and the US Basel III Endgame March 2026 Re-Proposal.

Key features:
- SEC-SA: Simplified Supervisory Formula Approach (SSFA)
- SEC-ERBA: External Ratings-Based Approach
- STC: Simple, Transparent, Comparable criteria checking
- Tranche capital calculation with attachment/detachment points
- RWA cap at 1250%
- Resecuritization risk weight multipliers

Exports:
    SecuritizationCalculator: Main calculator class
    SecuritizationPool: Pool model
    SecuritizationTranche: Tranche model
    SecResult: Output model
    SecReportGenerator: SEC1-SEC4 Pillar 3 reporting
"""

from src.securitization.sec_framework import (
    SecResult,
    SecuritizationCalculator,
    SecuritizationPool,
    SecuritizationTranche,
    STCCriteria,
    STCResult,
    get_erba_risk_weight,
)
from src.securitization.sec_params import (
    ExternalRating,
    MaturityBucket,
    SecApproach,
    SecPoolAssetType,
    TrancheSeniority,
)
from src.securitization.sec_reporting import SecReportGenerator

__all__ = [
    "ExternalRating",
    "MaturityBucket",
    "SecApproach",
    "SecPoolAssetType",
    "SecReportGenerator",
    "SecResult",
    "SecuritizationCalculator",
    "SecuritizationPool",
    "SecuritizationTranche",
    "STCCriteria",
    "STCResult",
    "TrancheSeniority",
    "get_erba_risk_weight",
]
