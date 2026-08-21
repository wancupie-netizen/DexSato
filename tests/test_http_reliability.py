import pytest

from scanner.http_reliability import request_with_bounded_retry


def test_retry_policy_rejects_unbounded_attempts():
    with pytest.raises(ValueError, match="between 1 and 3"):
        request_with_bounded_retry(lambda: object(), provider="test", max_attempts=4)


def test_retry_policy_rejects_excessive_backoff():
    with pytest.raises(ValueError, match="between 0 and 5"):
        request_with_bounded_retry(
            lambda: object(), provider="test", backoff_seconds=6,
        )
