"""
DexSato Decision Serializer

Serialize DecisionArtifact into a JSON-safe structure.

Responsibilities
----------------
- Convert DecisionArtifact into dict
- Preserve DecisionArtifact information
- Contain no business logic
- Contain no persistence logic

This module does NOT:
- save data
- load data
- deserialize artifacts
"""

from core.artifacts.decision_artifact import (
    DecisionArtifact,
)


def serialize_decision(
    decision: DecisionArtifact,
) -> dict:
    """
    Serialize a DecisionArtifact into a JSON-safe dict.
    """

    return {

        "artifact_id":
            decision.artifact_id,

        "recommended_action":
            decision.recommended_action,

        "confidence":
            decision.confidence,

        "summary":
            decision.summary,

        "context": {

            "trend":
                decision.context.trend,

            "market_bias":
                decision.context.market_bias,

            "risk":
                decision.context.risk,

        },

        "metadata": {

            "engine_version":
                decision.metadata.engine_version,

            "symbol":
                decision.metadata.symbol,

            "pair":
                decision.metadata.pair,

            "timestamp":
                decision.metadata.timestamp.isoformat(),

            "signal_version":
                decision.metadata.signal_version,

            "interpretation_version":
                decision.metadata.interpretation_version,

            "chain":
                decision.metadata.chain,

        },

        "reasons": [

            {

                "title":
                    reason.title,

                "description":
                    reason.description,

                "evidence": [

                    {

                        "name":
                            evidence.name,

                        "value":
                            evidence.value,

                        "source":
                            evidence.source,

                    }

                    for evidence in reason.evidence

                ],

            }

            for reason in decision.reasons

        ],

    }