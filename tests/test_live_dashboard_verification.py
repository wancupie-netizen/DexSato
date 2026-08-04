"""
Tests for DexSato Live Dashboard Verification.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from adaptive.dashboard.dashboard_card import (
    create_dashboard_card,
)

from validation.live_dashboard_verification import (
    extract_live_artifacts,
    render_verification_report,
    verify_dashboard_result,
)


# ==========================================================
# Fixtures
# ==========================================================

def build_verification_fixture():
    """
    Build a consistent Runner result for verification.
    """

    timestamp = datetime.now(
        timezone.utc,
    )

    reason = Mock()
    reason.title = "ACCUMULATION"

    metadata = Mock()
    metadata.timestamp = timestamp

    decision = Mock()
    decision.recommended_action = "WATCH"
    decision.confidence = "HIGH"
    decision.summary = "Bullish momentum detected."
    decision.reasons = [reason]
    decision.metadata = metadata

    intelligence_package = {

        "token":
            "BTC",

        "observation":
            {},

        "signals":
            [],

        "interpretations":
            [],

        "decision":
            decision,

    }

    dashboard = create_dashboard_card(

        token="BTC",

        decision="WATCH",

        confidence="HIGH",

        historical_success=66.67,

        seen_before=True,

        reasons=[
            "ACCUMULATION",
        ],

        summary="Bullish momentum detected.",

        last_updated=timestamp,

    )

    result = {

        "success":
            True,

        "token":
            "BTC",

        "intelligence_package":
            intelligence_package,

        "dashboard":
            dashboard,

    }

    return result


# ==========================================================
# Extraction
# ==========================================================

def test_should_extract_live_artifacts():
    """
    Verifier should extract official Runner artifacts.
    """

    result = build_verification_fixture()

    intelligence, dashboard = extract_live_artifacts(
        result,
    )

    assert intelligence is result[
        "intelligence_package"
    ]

    assert dashboard is result[
        "dashboard"
    ]


def test_should_reject_failed_result():
    """
    Failed Runner results should not be verified.
    """

    with pytest.raises(
        RuntimeError,
        match="Scan failed",
    ):

        extract_live_artifacts(
            {
                "success": False,
                "error": "Scan failed",
            }
        )


# ==========================================================
# Verification
# ==========================================================

@patch(
    "validation.live_dashboard_verification."
    "build_history_summary"
)
@patch(
    "validation.live_dashboard_verification.find"
)
@patch(
    "validation.live_dashboard_verification."
    "build_knowledge_fingerprint"
)
def test_should_verify_real_dashboard_mapping(
    mock_build_fingerprint,
    mock_find,
    mock_build_history,
):
    """
    Dashboard fields should match their authoritative sources.
    """

    result = build_verification_fixture()

    history = Mock()

    history.sample_size = 3

    history.success_rate = 66.67

    history.seen_before = True

    mock_build_fingerprint.return_value = (
        "BTC-FINGERPRINT"
    )

    mock_find.return_value = [
        Mock(),
        Mock(),
        Mock(),
    ]

    mock_build_history.return_value = history

    verification = verify_dashboard_result(
        result,
    )

    assert verification.all_checks_passed is True

    assert verification.token_matches is True

    assert verification.decision_matches is True

    assert verification.confidence_matches is True

    assert verification.summary_matches is True

    assert verification.reasons_match is True

    assert verification.timestamp_matches is True

    assert verification.historical_success_matches is True

    assert verification.seen_before_matches is True

    assert verification.knowledge_fingerprint == (
        "BTC-FINGERPRINT"
    )

    assert verification.history_sample_size == 3


# ==========================================================
# Failure Detection
# ==========================================================

@patch(
    "validation.live_dashboard_verification."
    "build_history_summary"
)
@patch(
    "validation.live_dashboard_verification.find"
)
@patch(
    "validation.live_dashboard_verification."
    "build_knowledge_fingerprint"
)
def test_should_detect_dashboard_mismatch(
    mock_build_fingerprint,
    mock_find,
    mock_build_history,
):
    """
    Verifier should detect mismatched historical values.
    """

    result = build_verification_fixture()

    history = Mock()

    history.sample_size = 10

    history.success_rate = 20.0

    history.seen_before = False

    mock_build_fingerprint.return_value = (
        "BTC-FINGERPRINT"
    )

    mock_find.return_value = []

    mock_build_history.return_value = history

    verification = verify_dashboard_result(
        result,
    )

    assert verification.all_checks_passed is False

    assert (
        verification.historical_success_matches
        is False
    )

    assert verification.seen_before_matches is False


# ==========================================================
# Report
# ==========================================================

@patch(
    "validation.live_dashboard_verification."
    "build_history_summary"
)
@patch(
    "validation.live_dashboard_verification.find"
)
@patch(
    "validation.live_dashboard_verification."
    "build_knowledge_fingerprint"
)
def test_should_render_verification_report(
    mock_build_fingerprint,
    mock_find,
    mock_build_history,
):
    """
    Verification report should expose provenance details.
    """

    result = build_verification_fixture()

    history = Mock()

    history.sample_size = 3

    history.success_rate = 66.67

    history.seen_before = True

    mock_build_fingerprint.return_value = (
        "BTC-FINGERPRINT"
    )

    mock_find.return_value = []

    mock_build_history.return_value = history

    verification = verify_dashboard_result(
        result,
    )

    report = render_verification_report(
        verification,
    )

    assert "FINAL RESULT" in report

    assert "PASS" in report

    assert "BTC-FINGERPRINT" in report

    assert "History Sample Size" in report