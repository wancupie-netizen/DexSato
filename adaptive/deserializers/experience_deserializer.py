"""
DexSato Experience Deserializer.

Restores ExperienceArtifact from a persistence payload.

Responsibilities
----------------
- Validate required persistence fields
- Restore datetime values
- Restore immutable ExperienceArtifact
- Preserve original artifact identity

This module does NOT:
- access databases
- calculate history
- create replacement IDs
- infer missing business values
"""

from __future__ import annotations

from datetime import datetime

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
    ExperienceMetadata,
)


# ==========================================================
# Contract
# ==========================================================

_REQUIRED_FIELDS = {

    "experience_id",

    "fingerprint",

    "sample_size",

    "success_count",

    "failure_count",

    "success_rate",

    "last_seen",

    "engine_version",

    "artifact_timestamp",

}


# ==========================================================
# Helpers
# ==========================================================

def _parse_datetime(
    value: object,
    *,
    field_name: str,
) -> datetime:
    """
    Parse an ISO datetime value.
    """

    if isinstance(
        value,
        datetime,
    ):

        return value

    if not isinstance(
        value,
        str,
    ):

        raise ValueError(
            f"{field_name} must be an ISO datetime string."
        )

    try:

        return datetime.fromisoformat(
            value,
        )

    except ValueError as error:

        raise ValueError(
            f"{field_name} contains an invalid datetime."
        ) from error


# ==========================================================
# Deserializer
# ==========================================================

def deserialize_experience(
    payload: dict,
) -> ExperienceArtifact:
    """
    Restore an ExperienceArtifact from persistence data.
    """

    if not isinstance(
        payload,
        dict,
    ):

        raise ValueError(
            "Experience payload must be a dictionary."
        )

    missing_fields = (
        _REQUIRED_FIELDS
        - payload.keys()
    )

    if missing_fields:

        fields = ", ".join(
            sorted(
                missing_fields,
            )
        )

        raise ValueError(
            f"Experience payload is missing: {fields}"
        )

    return ExperienceArtifact(

        experience_id=
            str(
                payload["experience_id"]
            ),

        fingerprint=
            str(
                payload["fingerprint"]
            ),

        sample_size=
            int(
                payload["sample_size"]
            ),

        success_count=
            int(
                payload["success_count"]
            ),

        failure_count=
            int(
                payload["failure_count"]
            ),

        success_rate=
            float(
                payload["success_rate"]
            ),

        last_seen=
            _parse_datetime(

                payload["last_seen"],

                field_name=
                    "last_seen",

            ),

        metadata=
            ExperienceMetadata(

                engine_version=
                    str(
                        payload["engine_version"]
                    ),

                timestamp=
                    _parse_datetime(

                        payload[
                            "artifact_timestamp"
                        ],

                        field_name=
                            "artifact_timestamp",

                    ),

            ),

    )