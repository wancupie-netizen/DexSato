"""
DexSato Knowledge Aggregator

Transform a LearningArtifact into a reusable
KnowledgeArtifact.

Responsibilities
----------------
- Consume LearningArtifact
- Produce KnowledgeArtifact
- Aggregate reusable knowledge

Knowledge Aggregator does NOT

- modify LearningArtifact
- modify OutcomeArtifact
- modify DecisionArtifact
- access databases
- access external APIs
- persist KnowledgeArtifact
"""

from core.artifacts.learning_artifact import (
    LearningArtifact,
)

from core.artifacts.knowledge_artifact import (
    KnowledgeArtifact,
)

from scanner.knowledge_fingerprint import (
    build_knowledge_fingerprint,
)


ENGINE_VERSION = "1.0.0"


def build_knowledge(
    learning: LearningArtifact,
) -> KnowledgeArtifact:
    """
    Build a KnowledgeArtifact from a LearningArtifact.

    Parameters
    ----------
    learning
        Completed LearningArtifact.

    Returns
    -------
    KnowledgeArtifact
    """

    if learning is None:

        raise ValueError(
            "LearningArtifact is required."
        )

    # ------------------------------------------------------
    # Knowledge Fingerprint
    # ------------------------------------------------------

    fingerprint = build_knowledge_fingerprint(

        {

            "decision": {

                "decision":
                    learning.learning_status,

            },

            "interpretations": [],

        }

    )

    # ------------------------------------------------------
    # Initial Statistics
    # ------------------------------------------------------

    sample_size = 1

    success_rate = 100.0

    confidence = "HIGH"

    summary = (

        "Knowledge generated from a single "
        "LearningArtifact."

    )

    # ------------------------------------------------------
    # Build Knowledge Artifact
    # ------------------------------------------------------

    return KnowledgeArtifact.from_learning(

        learning=learning,

        knowledge_fingerprint=fingerprint,

        sample_size=sample_size,

        success_rate=success_rate,

        confidence=confidence,

        summary=summary,

        engine_version=ENGINE_VERSION,

    )