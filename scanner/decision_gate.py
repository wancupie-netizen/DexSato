"""
DexSato Decision Gate

Validate DecisionArtifact before it enters
the downstream pipeline.

Responsibilities
----------------
- Validate DecisionArtifact integrity
- Validate mandatory fields
- Produce GateResult

Decision Gate does NOT:
- modify DecisionArtifact
- generate decisions
- access databases
- access external APIs
- perform business validation
"""

from core.artifacts.decision_artifact import DecisionArtifact

from scanner.core.gate_result import (
    GateMetadata,
    GateResult,
    ValidationError,
)


# ==========================================================
# Configuration
# ==========================================================

GATE_VERSION = "1.0.0"

REQUIRED_FIELDS = (
    "recommended_action",
    "confidence",
    "summary",
    "context",
    "reasons",
    "metadata",
    "artifact_id",
)


# ==========================================================
# Helpers
# ==========================================================

def _validate_required_fields(
    artifact: DecisionArtifact,
) -> tuple[ValidationError, ...]:

    errors: list[ValidationError] = []

    for field_name in REQUIRED_FIELDS:

        value = getattr(
            artifact,
            field_name,
            None,
        )

        # Missing value

        if value is None:

            errors.append(
                ValidationError(
                    field=field_name,
                    message="Missing required field",
                )
            )

            continue

        # Empty string

        if isinstance(value, str):

            if not value.strip():

                errors.append(
                    ValidationError(
                        field=field_name,
                        message="Empty string is not allowed",
                    )
                )

    return tuple(errors)


# ==========================================================
# Decision Gate
# ==========================================================

def validate(
    artifact: DecisionArtifact,
) -> GateResult:
    """
    Validate a DecisionArtifact.

    Validation Scope
    ----------------
    - Object type
    - Required fields
    - Missing values
    - Empty strings

    Decision Gate intentionally does NOT validate:

    - confidence policy
    - recommended action
    - business rules
    - market correctness
    """

    # ------------------------------------------------------
    # Object Validation
    # ------------------------------------------------------

    if not isinstance(artifact, DecisionArtifact):

        return GateResult(

            status="REJECTED",

            artifact=artifact,

            errors=(
                ValidationError(
                    field="artifact",
                    message="Invalid DecisionArtifact instance",
                ),
            ),

            metadata=GateMetadata(
                gate_version=GATE_VERSION,
            ),
        )

    # ------------------------------------------------------
    # Structural Validation
    # ------------------------------------------------------

    errors = _validate_required_fields(
        artifact
    )

    if errors:

        return GateResult(

            status="REJECTED",

            artifact=artifact,

            errors=errors,

            metadata=GateMetadata(
                gate_version=GATE_VERSION,
            ),
        )

    # ------------------------------------------------------
    # Approved
    # ------------------------------------------------------

    return GateResult(

        status="APPROVED",

        artifact=artifact,

        errors=(),

        metadata=GateMetadata(
            gate_version=GATE_VERSION,
        ),
    )


# ==========================================================
# Backward Compatibility
# ==========================================================

validate_decision = validate