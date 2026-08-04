"""
DexSato Knowledge Aggregator

Build KnowledgeArtifact objects from
historical LearningArtifacts.

Responsibilities
----------------
- Aggregate LearningArtifacts
- Produce KnowledgeArtifact
- Contain domain logic only

This module does NOT:
- access databases
- serialize objects
- build DTOs
- access HTTP
"""

from core.artifacts.knowledge_artifact import (
    KnowledgeArtifact,
)

from core.artifacts.learning_artifact import (
    LearningArtifact,
)


ENGINE_VERSION = "1.0.0"


def build_knowledge(
    learnings: list[LearningArtifact],
) -> KnowledgeArtifact:
    """
    Aggregate LearningArtifacts into
    a single KnowledgeArtifact.

    Parameters
    ----------
    learnings

    Returns
    -------
    KnowledgeArtifact
    """

    if not learnings:

        raise ValueError(
            "Knowledge Aggregator requires at least one LearningArtifact."
        )

    latest = learnings[-1]

    sample_size = len(learnings)

    #
    # Placeholder implementation.
    #
    # Future versions will calculate:
    #
    # - success rate
    # - confidence
    # - fingerprint
    # - statistical weighting
    #

    knowledge_fingerprint = "UNKNOWN"

    success_rate = 100.0

    confidence = "HIGH"

    summary = (
        f"Knowledge generated from "
        f"{sample_size} learning artifact(s)."
    )

    return KnowledgeArtifact.from_learning(

        learning=latest,

        knowledge_fingerprint=
            knowledge_fingerprint,

        sample_size=
            sample_size,

        success_rate=
            success_rate,

        confidence=
            confidence,

        summary=
            summary,

        engine_version=
            ENGINE_VERSION,

    )