import requests

from scanner.http_reliability import (
    get_provider_health,
    request_with_bounded_retry,
    reset_provider_telemetry,
)


class Response:
    status_code = 200


def test_success_records_one_request_and_attempt():
    reset_provider_telemetry()

    request_with_bounded_retry(lambda: Response(), provider="Provider A")
    health = get_provider_health()

    assert health["status"] == "HEALTHY"
    assert health["total_requests"] == 1
    assert health["total_attempts"] == 1
    assert health["total_retries"] == 0


def test_recovered_request_records_retry_without_failure():
    reset_provider_telemetry()
    calls = []

    def operation():
        calls.append(True)
        if len(calls) == 1:
            raise requests.ReadTimeout("temporary")
        return Response()

    request_with_bounded_retry(
        operation, provider="Provider B", sleep=lambda delay: None,
    )
    health = get_provider_health()

    assert health["status"] == "RECOVERED"
    assert health["total_attempts"] == 2
    assert health["total_retries"] == 1
    assert health["total_failures"] == 0


def test_final_failure_records_safe_error_metadata_only():
    reset_provider_telemetry()

    try:
        request_with_bounded_retry(
            lambda: (_ for _ in ()).throw(requests.ReadTimeout("secret URL")),
            provider="Provider C", sleep=lambda delay: None,
        )
    except requests.ReadTimeout:
        pass

    health = get_provider_health()
    provider = health["providers"][0]
    assert health["status"] == "DEGRADED"
    assert provider["failures"] == 1
    assert provider["last_failure"] == "ReadTimeout"
    assert "secret" not in str(provider)


def test_reset_isolates_each_snapshot_window():
    reset_provider_telemetry()
    request_with_bounded_retry(lambda: Response(), provider="Provider A")

    reset_provider_telemetry()

    assert get_provider_health()["status"] == "NO_ACTIVITY"
