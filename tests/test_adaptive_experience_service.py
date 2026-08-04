"""
Tests for DexSato Adaptive Experience Service.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)

from application.adaptive_experience_service import (
    classify_learning_success,
    record_adaptive_experience,
)

from core.artifacts.learning_artifact import (
    LearningArtifact,
    LearningMetadata,
)


# ==========================================================
# Fixtures
# ==========================================================

def build_learning(
    status: str,
) -> LearningArtifact:
    """
    Build a reusable LearningArtifact.
    """

    return LearningArtifact(

        token="BTC",

        outcome_artifact_id="OUT-TEST",

        learning_status=status,

        summary="Learning test.",

        metadata=LearningMetadata(

            engine_version="1.0.0",

            timestamp=datetime(
                2026,
                7,
                22,
                10,
                30,
                tzinfo=timezone.utc,
            ),

        ),

    )


# ==========================================================
# Classification
# ==========================================================

def test_should_classify_confirmed_learning_as_success():
    """
    Confirmed learning should become a successful experience.
    """

    learning = build_learning(
        "CONFIRMED",
    )

    assert classify_learning_success(
        learning,
    ) is True


def test_should_classify_unknown_learning_as_failure():
    """
    Non-confirmed learning should become an unsuccessful experience.
    """

    learning = build_learning(
        "UNKNOWN",
    )

    assert classify_learning_success(
        learning,
    ) is False


def test_should_reject_missing_learning():
    """
    Missing LearningArtifact should fail clearly.
    """

    with pytest.raises(
        ValueError,
        match="LearningArtifact is required",
    ):

        classify_learning_success(
            None,
        )


# ==========================================================
# Experience Recording
# ==========================================================

@patch(
    "application.adaptive_experience_service.save"
)
@patch(
    "application.adaptive_experience_service.compile_experience"
)
def test_should_compile_and_save_adaptive_experience(
    mock_compile_experience,
    mock_save,
):
    """
    Service should compile and save one ExperienceArtifact.
    """

    learning = build_learning(
        "CONFIRMED",
    )

    experience = Mock(
        spec=ExperienceArtifact,
    )

    mock_compile_experience.return_value = experience

    result = record_adaptive_experience(

        knowledge_fingerprint="BTC-FINGERPRINT",

        learning=learning,

    )

    assert result is experience

    mock_compile_experience.assert_called_once_with(

        fingerprint="BTC-FINGERPRINT",

        success=True,

        timestamp=learning.metadata.timestamp,

    )

    mock_save.assert_called_once_with(
        experience,
    )


def test_should_reject_empty_fingerprint():
    """
    Empty fingerprints must not create history records.
    """

    learning = build_learning(
        "CONFIRMED",
    )

    with pytest.raises(
        ValueError,
        match="Knowledge Fingerprint is required",
    ):

        record_adaptive_experience(

            knowledge_fingerprint="   ",

            learning=learning,

        )