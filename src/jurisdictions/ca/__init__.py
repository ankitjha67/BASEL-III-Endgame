"""Canada -- OSFI Capital Adequacy Requirements (CAR) Guideline 2026.

See ``docs/jurisdictions/CA_parameter_reference.md`` for the verbatim parameter transcription.
"""

from src.jurisdictions.ca.calculator import CARegime
from src.jurisdictions.ca.operational_risk import OpRiskApproach

__all__ = ["CARegime", "OpRiskApproach"]
