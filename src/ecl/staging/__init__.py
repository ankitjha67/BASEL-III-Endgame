"""Staging Engine — IFRS 9 / CECL stage allocation and SICR assessment.

References:
    - IFRS 9 §5.5.1-5.5.20: Impairment staging
    - ASC 326-20-35: CECL subsequent measurement
    - BCBS d350 §3.1: Stage allocation requirements
"""

from src.ecl.staging.staging_engine import (
    StagingEngine,
    StageAssignment,
    SICRAssessment,
    SICRIndicator,
    Stage,
)

__all__ = [
    "StagingEngine",
    "StageAssignment",
    "SICRAssessment",
    "SICRIndicator",
    "Stage",
]
