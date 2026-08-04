"""
Tests for DexSato Production Runner.

Responsibilities
----------------
- Verify production orchestration
- Verify fingerprint ownership
- Verify Dashboard integration
- Verify Lifecycle integration
- Verify Adaptive Experience integration
- Verify successful production result
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

from scanner.runner import run_scan


# ==========================================================
# Successful Production Scan
# ==========================================================

@patch("scanner.runner._finish_success")
@patch("scanner.runner.record_adaptive_experience")
@patch("scanner.runner._persist_lifecycle")
@patch("scanner.runner._build_lifecycle")
@patch("scanner.runner.build_adaptive_dashboard")
@patch("scanner.runner.build_dashboard_request")
@patch("scanner.runner._persist_intelligence")
@patch("scanner.runner.build_knowledge_fingerprint")
@patch("scanner.runner._build_intelligence")
@patch("scanner.runner._scan_market")
@patch("scanner.runner.start_job")
def test_should_complete_successful_scan(
    mock_start_job,
    mock_scan_market,
    mock_build_intelligence,
    mock_build_fingerprint,
    mock_persist_intelligence,
    mock_build_dashboard_request,
    mock_build_adaptive_dashboard,
    mock_build_lifecycle,
    mock_persist_lifecycle,
    mock_record_adaptive_experience,
    mock_finish_success,
):
    """
    Runner should orchestrate the complete production flow.
    """

    timestamp = datetime.now(
        timezone.utc,
    )

    decision = Mock()
    decision.metadata.timestamp = timestamp

    event = {
        "token": "BTC",
    }

    observation = {
        "token": "BTC",
    }

    learning = Mock()

    intelligence_package = {

        "token":
            "BTC",

        "observation":
            observation,

        "signals":
            [],

        "interpretations":
            [],

        "decision":
            decision,

    }

    lifecycle_package = {

        "outcome":
            Mock(),

        "learning":
            learning,

        "knowledge":
            Mock(),

    }

    dashboard_request = Mock()
    dashboard = Mock()
    job = Mock()

    expected_result = {

        "success":
            True,

        "job_status":
            "SUCCESS",

        "token":
            "BTC",

        "dashboard":
            dashboard,

    }

    mock_start_job.return_value = job

    mock_scan_market.return_value = {

        "event":
            event,

        "observation":
            observation,

        "first_scan":
            False,

    }

    mock_build_intelligence.return_value = {

        "intelligence_package":
            intelligence_package,

        "latest_package":
            None,

        "should_persist":
            True,

    }

    mock_build_fingerprint.return_value = (
        "KNOWLEDGE-FINGERPRINT"
    )

    mock_build_dashboard_request.return_value = (
        dashboard_request
    )

    mock_build_adaptive_dashboard.return_value = dashboard

    mock_build_lifecycle.return_value = {

        "market_snapshot":
            Mock(),

        "lifecycle_package":
            lifecycle_package,

    }

    mock_finish_success.return_value = expected_result

    result = run_scan(
        "BTC",
    )

    assert result == expected_result

    mock_start_job.assert_called_once_with(
        "BTC",
    )

    mock_scan_market.assert_called_once_with(
        "BTC",
    )

    mock_build_intelligence.assert_called_once_with(

        token=
            "BTC",

        observation=
            observation,

    )

    mock_build_fingerprint.assert_called_once_with(
        intelligence_package,
    )

    mock_persist_intelligence.assert_called_once_with(

        intelligence_package,
        "KNOWLEDGE-FINGERPRINT",

    )

    mock_build_dashboard_request.assert_called_once_with(

        token=
            "BTC",

        decision=
            decision,

        knowledge_fingerprint=
            "KNOWLEDGE-FINGERPRINT",

        last_updated=
            timestamp,

    )

    mock_build_adaptive_dashboard.assert_called_once_with(
        dashboard_request,
    )

    mock_build_lifecycle.assert_called_once_with(

        decision=
            decision,

        event=
            event,

    )

    mock_persist_lifecycle.assert_called_once_with(
        lifecycle_package,
    )

    mock_record_adaptive_experience.assert_called_once_with(

        knowledge_fingerprint=
            "KNOWLEDGE-FINGERPRINT",

        learning=
            learning,

    )

    mock_finish_success.assert_called_once_with(

        job=
            job,

        token=
            "BTC",

        event=
            event,

        intelligence_package=
            intelligence_package,

        lifecycle_package=
            lifecycle_package,

        dashboard=
            dashboard,

        knowledge_persisted=
            True,

    )


# ==========================================================
# Knowledge Gate Rejection
# ==========================================================

@patch("scanner.runner._finish_success")
@patch("scanner.runner.record_adaptive_experience")
@patch("scanner.runner._persist_lifecycle")
@patch("scanner.runner._build_lifecycle")
@patch("scanner.runner.build_adaptive_dashboard")
@patch("scanner.runner.build_dashboard_request")
@patch("scanner.runner._persist_intelligence")
@patch("scanner.runner.build_knowledge_fingerprint")
@patch("scanner.runner._build_intelligence")
@patch("scanner.runner._scan_market")
@patch("scanner.runner.start_job")
def test_should_build_dashboard_when_knowledge_is_not_persisted(
    mock_start_job,
    mock_scan_market,
    mock_build_intelligence,
    mock_build_fingerprint,
    mock_persist_intelligence,
    mock_build_dashboard_request,
    mock_build_adaptive_dashboard,
    mock_build_lifecycle,
    mock_persist_lifecycle,
    mock_record_adaptive_experience,
    mock_finish_success,
):
    """
    Dashboard and Adaptive Experience must still be built when
    the Knowledge Gate rejects Intelligence persistence.
    """

    timestamp = datetime.now(
        timezone.utc,
    )

    decision = Mock()
    decision.metadata.timestamp = timestamp

    learning = Mock()

    intelligence_package = {

        "token":
            "ETH",

        "observation":
            {},

        "signals":
            [],

        "interpretations":
            [],

        "decision":
            decision,

    }

    lifecycle_package = {

        "outcome":
            Mock(),

        "learning":
            learning,

        "knowledge":
            Mock(),

    }

    mock_start_job.return_value = Mock()

    mock_scan_market.return_value = {

        "event":
            {
                "token": "ETH",
            },

        "observation":
            {},

        "first_scan":
            False,

    }

    mock_build_intelligence.return_value = {

        "intelligence_package":
            intelligence_package,

        "latest_package":
            None,

        "should_persist":
            False,

    }

    mock_build_fingerprint.return_value = (
        "ETH-FINGERPRINT"
    )

    mock_build_dashboard_request.return_value = Mock()

    mock_build_adaptive_dashboard.return_value = Mock()

    mock_build_lifecycle.return_value = {

        "market_snapshot":
            Mock(),

        "lifecycle_package":
            lifecycle_package,

    }

    mock_finish_success.return_value = {
        "success": True,
    }

    result = run_scan(
        "ETH",
    )

    assert result["success"] is True

    mock_persist_intelligence.assert_not_called()

    mock_build_dashboard_request.assert_called_once()

    mock_build_adaptive_dashboard.assert_called_once()

    mock_persist_lifecycle.assert_called_once_with(
        lifecycle_package,
    )

    mock_record_adaptive_experience.assert_called_once_with(

        knowledge_fingerprint=
            "ETH-FINGERPRINT",

        learning=
            learning,

    )


# ==========================================================
# First Scan
# ==========================================================

@patch("scanner.runner.finish_job")
@patch("scanner.runner._scan_market")
@patch("scanner.runner.start_job")
def test_should_stop_after_first_market_scan(
    mock_start_job,
    mock_scan_market,
    mock_finish_job,
):
    """
    First scan should only persist the first market event.
    """

    job = Mock()

    event = {
        "token": "SOL",
    }

    mock_start_job.return_value = job

    mock_scan_market.return_value = {

        "event":
            event,

        "observation":
            None,

        "first_scan":
            True,

    }

    mock_finish_job.return_value = 25

    result = run_scan(
        "SOL",
    )

    assert result == {

        "success":
            True,

        "job_status":
            "SUCCESS",

        "token":
            "SOL",

        "duration_ms":
            25,

        "event":
            event,

        "message":
            (
                "First market event recorded. "
                "Waiting for next scan."
            ),

    }

    mock_finish_job.assert_called_once_with(
        job,
        "SUCCESS",
    )