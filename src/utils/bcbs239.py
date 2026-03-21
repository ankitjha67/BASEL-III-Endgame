"""BCBS 239 Data Quality and Lineage Framework.

Implements data quality validation and lineage tracking per BCBS 239
(Principles for Effective Risk Data Aggregation and Risk Reporting).

Provides:
- Data quality checks: completeness, accuracy, range, referential integrity
- Lineage trail: tracks data transformations from source to output
- Quality scoring: aggregated quality metrics across risk modules
- Audit trail: timestamped log of all model computations

References:
    - BCBS 239: Principles for effective risk data aggregation (Jan 2013)
    - SR 11-7: Supervisory Guidance on Model Risk Management
    - BCBS d424 para 30: Data quality requirements
    - Federal Reserve FR Y-14 Data Quality Standards
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =========================================================================
#  Enumerations
# =========================================================================

class DataQualityDimension(Enum):
    """BCBS 239 data quality dimensions.

    Reference: BCBS 239 Principle 3 (Accuracy and Integrity).
    """
    COMPLETENESS = "COMPLETENESS"
    ACCURACY = "ACCURACY"
    TIMELINESS = "TIMELINESS"
    CONSISTENCY = "CONSISTENCY"
    RANGE_VALIDITY = "RANGE_VALIDITY"
    REFERENTIAL_INTEGRITY = "REFERENTIAL_INTEGRITY"
    UNIQUENESS = "UNIQUENESS"


class QualityStatus(Enum):
    """Quality check result status.

    Reference: BCBS 239 Principle 3.
    """
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class LineageEventType(Enum):
    """Types of data lineage events.

    Reference: BCBS 239 Principle 2 (Data Architecture and IT Infrastructure).
    """
    SOURCE_INPUT = "SOURCE_INPUT"
    TRANSFORMATION = "TRANSFORMATION"
    VALIDATION = "VALIDATION"
    AGGREGATION = "AGGREGATION"
    CALCULATION = "CALCULATION"
    OUTPUT = "OUTPUT"
    ERROR = "ERROR"


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class DataQualityCheck:
    """Result of a single data quality check.

    Reference: BCBS 239 Principle 3.
    """
    dimension: DataQualityDimension
    check_name: str
    status: QualityStatus
    field_name: str = ""
    expected_value: str = ""
    actual_value: str = ""
    message: str = ""
    severity: str = "INFO"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DataQualityReport:
    """Aggregated data quality report.

    Reference: BCBS 239 Principle 6 (Accuracy).
    """
    module_name: str
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failures: int = 0
    skipped: int = 0
    checks: list[DataQualityCheck] = field(default_factory=list)
    overall_quality_score: float = 1.0  # 0.0 to 1.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_check(self, check: DataQualityCheck) -> None:
        """Add a quality check result.

        Reference: BCBS 239 Principle 3.
        """
        self.checks.append(check)
        self.total_checks += 1
        if check.status == QualityStatus.PASS:
            self.passed += 1
        elif check.status == QualityStatus.WARNING:
            self.warnings += 1
        elif check.status == QualityStatus.FAIL:
            self.failures += 1
        else:
            self.skipped += 1
        self._update_score()

    def _update_score(self) -> None:
        """Recalculate overall quality score."""
        if self.total_checks == 0:
            self.overall_quality_score = 1.0
            return
        effective = self.passed + 0.5 * self.warnings
        self.overall_quality_score = effective / self.total_checks


@dataclass
class LineageEntry:
    """A single data lineage event.

    Reference: BCBS 239 Principle 2.
    """
    event_type: LineageEventType
    module: str
    description: str
    input_hash: str = ""
    output_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class LineageTrail:
    """Data lineage tracker for BCBS 239 compliance.

    Records the full transformation chain from source data to
    final regulatory outputs, enabling auditability and traceability.

    Reference: BCBS 239 Principle 2 (Data Architecture and IT Infrastructure).
    """

    def __init__(self, trail_id: Optional[str] = None) -> None:
        """Initialize lineage trail.

        Args:
            trail_id: Unique identifier for this trail.
        """
        self.trail_id = trail_id or datetime.utcnow().strftime("%Y%m%d%H%M%S")
        self.entries: list[LineageEntry] = []

    def record(
        self,
        event_type: LineageEventType,
        module: str,
        description: str,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> LineageEntry:
        """Record a lineage event.

        Args:
            event_type: Type of event.
            module: Module that generated the event.
            description: Human-readable description.
            input_data: Input data (for hashing).
            output_data: Output data (for hashing).
            metadata: Additional metadata.

        Returns:
            The recorded LineageEntry.

        Reference: BCBS 239 Principle 2.
        """
        entry = LineageEntry(
            event_type=event_type,
            module=module,
            description=description,
            input_hash=self._compute_hash(input_data) if input_data else "",
            output_hash=self._compute_hash(output_data) if output_data else "",
            metadata=metadata or {},
        )
        self.entries.append(entry)
        logger.debug(
            "LINEAGE [%s] %s: %s",
            event_type.value, module, description
        )
        return entry

    def get_trail(self) -> list[LineageEntry]:
        """Get the full lineage trail.

        Returns:
            List of LineageEntry in chronological order.
        """
        return self.entries.copy()

    @staticmethod
    def _compute_hash(data: Any) -> str:
        """Compute a SHA-256 hash of data for integrity verification.

        Args:
            data: Data to hash.

        Returns:
            Hex digest string.
        """
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]


# =========================================================================
#  Common Quality Checks
# =========================================================================

def check_completeness(
    field_name: str,
    value: Any,
    required: bool = True,
) -> DataQualityCheck:
    """Check if a required field is populated.

    Reference: BCBS 239 Principle 3 — Completeness.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        status = QualityStatus.FAIL if required else QualityStatus.WARNING
        return DataQualityCheck(
            dimension=DataQualityDimension.COMPLETENESS,
            check_name=f"completeness_{field_name}",
            status=status,
            field_name=field_name,
            message=f"Field '{field_name}' is missing or empty",
        )
    return DataQualityCheck(
        dimension=DataQualityDimension.COMPLETENESS,
        check_name=f"completeness_{field_name}",
        status=QualityStatus.PASS,
        field_name=field_name,
    )


def check_range(
    field_name: str,
    value: float,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> DataQualityCheck:
    """Check if a numeric value is within expected range.

    Reference: BCBS 239 Principle 3 — Accuracy.
    """
    if min_val is not None and value < min_val:
        return DataQualityCheck(
            dimension=DataQualityDimension.RANGE_VALIDITY,
            check_name=f"range_{field_name}",
            status=QualityStatus.FAIL,
            field_name=field_name,
            expected_value=f">= {min_val}",
            actual_value=str(value),
            message=f"'{field_name}' = {value} below minimum {min_val}",
        )
    if max_val is not None and value > max_val:
        return DataQualityCheck(
            dimension=DataQualityDimension.RANGE_VALIDITY,
            check_name=f"range_{field_name}",
            status=QualityStatus.FAIL,
            field_name=field_name,
            expected_value=f"<= {max_val}",
            actual_value=str(value),
            message=f"'{field_name}' = {value} above maximum {max_val}",
        )
    return DataQualityCheck(
        dimension=DataQualityDimension.RANGE_VALIDITY,
        check_name=f"range_{field_name}",
        status=QualityStatus.PASS,
        field_name=field_name,
    )


def check_consistency(
    field_name: str,
    value_a: float,
    value_b: float,
    tolerance: float = 0.01,
    description: str = "",
) -> DataQualityCheck:
    """Check consistency between two values (e.g., cross-validation).

    Reference: BCBS 239 Principle 3 — Consistency.
    """
    if abs(value_a) < 1e-10 and abs(value_b) < 1e-10:
        diff_pct = 0.0
    elif abs(value_a) < 1e-10:
        diff_pct = 1.0
    else:
        diff_pct = abs(value_a - value_b) / abs(value_a)

    if diff_pct > tolerance:
        return DataQualityCheck(
            dimension=DataQualityDimension.CONSISTENCY,
            check_name=f"consistency_{field_name}",
            status=QualityStatus.WARNING if diff_pct < tolerance * 5 else QualityStatus.FAIL,
            field_name=field_name,
            expected_value=str(value_a),
            actual_value=str(value_b),
            message=description or f"Inconsistency: {diff_pct:.2%} difference",
        )
    return DataQualityCheck(
        dimension=DataQualityDimension.CONSISTENCY,
        check_name=f"consistency_{field_name}",
        status=QualityStatus.PASS,
        field_name=field_name,
    )
