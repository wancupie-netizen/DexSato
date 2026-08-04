"""
DexSato Decision Deserializer

Deserialize Decision dictionaries into DecisionArtifact objects.

Responsibilities
----------------
- Convert JSON-safe dict into DecisionArtifact
- Restore nested Decision domain objects
- Contain no business logic
- Contain no persistence logic

This module does NOT:
- load data
- save data
- validate decisions
"""

from datetime import datetime

from core.artifacts.decision_artifact import (
    DecisionArtifact,
    DecisionContext,
    DecisionMetadata,
    Evidence,
    Reason,
)


def deserialize_decision(
    payload: dict,
) -> DecisionArtifact:
    """
    Deserialize a JSON-safe Decision dictionary into
    a DecisionArtifact.
    """

    context = DecisionContext(

        trend=payload["context"].get("trend"),

        market_bias=payload["context"].get(
            "market_bias"
        ),

        risk=payload["context"].get("risk"),
    )

    metadata = DecisionMetadata(

        engine_version=payload["metadata"][
            "engine_version"
        ],

        symbol=payload["metadata"]["symbol"],

        pair=payload["metadata"]["pair"],

        timestamp=datetime.fromisoformat(
            payload["metadata"]["timestamp"]
        ),

        signal_version=payload["metadata"].get(
            "signal_version"
        ),

        interpretation_version=payload[
            "metadata"
        ].get(
            "interpretation_version"
        ),

        chain=payload["metadata"].get(
            "chain"
        ),
    )

    reasons = tuple(

        Reason(

            title=item["title"],

            description=item.get(
                "description",
                "",
            ),

            evidence=tuple(

                Evidence(

                    name=evidence["name"],

                    value=evidence["value"],

                    source=evidence.get(
                        "source"
                    ),

                )

                for evidence in item.get(
                    "evidence",
                    [],
                )

            ),

        )

        for item in payload.get(
            "reasons",
            [],
        )

    )

    return DecisionArtifact(

        recommended_action=payload[
            "recommended_action"
        ],

        confidence=payload["confidence"],

        summary=payload["summary"],

        context=context,

        reasons=reasons,

        metadata=metadata,

        artifact_id=payload[
            "artifact_id"
        ],

    )