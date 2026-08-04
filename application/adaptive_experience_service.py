"""
DexSato Adaptive Experience Service.

Application service responsible for converting a completed
LearningArtifact into an ExperienceArtifact and recording it
inside the Adaptive History Repository.

Responsibilities
----------------
- Receive operational Knowledge Fingerprint
- Receive completed LearningArtifact
- Classify the learning record
- Compile ExperienceArtifact
- Save Adaptive experience
- Return the recorded ExperienceArtifact

This module does NOT:
- make trading decisions
- calculate market profit or loss
- build Knowledge Fingerprints
- build DashboardCard
- access production databases
"""

from __future__ import annotations

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)

from adaptive.compiler.experience_compiler import (
    compile_experience,
)

from adaptive.history.history_repository import (
    save,
)

from core.artifacts.learning_artifact import (
    LearningArtifact,
)


# ==========================================================
# Learning Classification
# ==========================================================

def classify_learning_success(
    learning: LearningArtifact,
) -> bool:
    """
    Classify whether a LearningArtifact was confirmed.

    Notes
    -----
    This represents learning confirmation, not realised
    trading profitability.
    """

    if learning is None:

        raise ValueError(
            "LearningArtifact is required."
        )

    status = learning.learning_status.strip().upper()

    return status == "CONFIRMED"


# ==========================================================
# Adaptive Experience
# ==========================================================

def record_adaptive_experience(
    *,
    knowledge_fingerprint: str,
    learning: LearningArtifact,
) -> ExperienceArtifact:
    """
    Compile and record one Adaptive experience.

    Parameters
    ----------
    knowledge_fingerprint
        Operational fingerprint associated with the
        Intelligence Package.

    learning
        Completed LearningArtifact produced by Lifecycle.

    Returns
    -------
    ExperienceArtifact
        Experience recorded in Adaptive History.
    """

    fingerprint = knowledge_fingerprint.strip()

    if not fingerprint:

        raise ValueError(
            "Knowledge Fingerprint is required."
        )

    success = classify_learning_success(
        learning,
    )

    experience = compile_experience(

        fingerprint=fingerprint,

        success=success,

        timestamp=learning.metadata.timestamp,

    )

    save(
        experience,
    )

    return experience