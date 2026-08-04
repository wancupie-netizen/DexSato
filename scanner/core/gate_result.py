"""
DexSato Gate Result

Official output produced by Decision Gate.

Responsibilities
----------------
- Represent Decision Gate validation result
- Carry validation errors
- Preserve original DecisionArtifact
- Remain immutable

This module contains no business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

from core.artifacts.decision_artifact import DecisionArtifact


# ==========================================================
# Gate Metadata
# ==========================================================

@dataclass(frozen=True, slots=True)
class GateMetadata:
    """
    Technical metadata produced by Decision Gate.
    """

    gate_version: str

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ==========================================================
# Validation Error
# ==========================================================

@dataclass(frozen=True, slots=True)
class ValidationError:
    """
    Represents a validation failure.
    """

    field: str

    message: str


# ==========================================================
# Gate Result
# ==========================================================

@dataclass(frozen=True, slots=True)
class GateResult:
    """
    Immutable output of Decision Gate.

    Architecture Notes
    ------------------
    - Immutable
    - Deterministic
    - Explainable
    - Side-effect free

    Decision Gate never modifies the incoming DecisionArtifact.
    """

    status: str

    artifact: DecisionArtifact

    errors: Tuple[ValidationError, ...] = ()

    metadata: GateMetadata = field(
        default_factory=lambda: GateMetadata(
            gate_version="1.0.0",
        )
    )

    gate_id: str = field(
        default_factory=lambda: f"GATE-{uuid4().hex[:12].upper()}"
    )

    @property
    def approved(self) -> bool:
        """
        True when Decision Gate approves the artifact.
        """
        return self.status == "APPROVED"

    @property
    def rejected(self) -> bool:
        """
        True when Decision Gate rejects the artifact.
        """
        return self.status == "REJECTED"