"""
DexSato Experience Compiler

Compile Learning into Experience.

Responsibilities
----------------
- Build ExperienceArtifact
- Initialize Experience statistics

This module does NOT:
- access databases
- load historical experience
- merge experience
- build recommendations
- perform similarity search
"""

from datetime import datetime

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
    create_experience,
)


# --------------------------------------------------
# Compile
# --------------------------------------------------

def compile_experience(
    *,
    fingerprint: str,
    success: bool,
    timestamp: datetime,
) -> ExperienceArtifact:
    """
    Compile a single Learning event into
    an initial ExperienceArtifact.
    """

    success_count = 1 if success else 0

    failure_count = 0 if success else 1

    success_rate = 100.0 if success else 0.0

    return create_experience(

        fingerprint=fingerprint,

        sample_size=1,

        success_count=success_count,

        failure_count=failure_count,

        success_rate=success_rate,

        last_seen=timestamp,

    )