from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

import pytest

from application.product_signal_quota_store import (
    PRODUCT_SIGNAL_QUOTA_FILENAME,
    PRODUCT_SIGNAL_QUOTA_SCHEMA_VERSION,
    PRODUCT_SIGNAL_QUOTA_WINDOW_SECONDS,
    ProductSignalQuotaStore,
    ProductSignalQuotaStoreUnavailable,
    product_signal_quota_store_path,
)


SUBJECT_A = "guest:11111111-1111-4111-8111-111111111111"
SUBJECT_B = "user:22222222-2222-4222-8222-222222222222"
T0 = datetime(2026, 9, 28, 0, 0, tzinfo=UTC)


def _key(index: int) -> str:
    return f"solana:TokenMint{index}"


def test_store_path_is_isolated_under_product_directory(tmp_path) -> None:
    assert product_signal_quota_store_path(tmp_path) == (
        tmp_path / "product" / PRODUCT_SIGNAL_QUOTA_FILENAME
    )


def test_admission_is_deterministic_and_stops_at_limit(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    result = store.admit(
        SUBJECT_A,
        [_key(index) for index in range(1, 8)],
        limit=5,
        now=T0,
    )

    assert result.allowed_keys == tuple(_key(index) for index in range(1, 6))
    assert result.newly_admitted_keys == tuple(_key(index) for index in range(1, 6))
    assert result.active_count == 5
    assert result.remaining == 0


def test_duplicate_signal_keys_use_one_slot_and_preserve_order(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    result = store.admit(
        SUBJECT_A,
        [_key(1), _key(1), _key(2), _key(1), _key(3)],
        limit=5,
        now=T0,
    )

    assert result.allowed_keys == (_key(1), _key(2), _key(3))
    assert result.newly_admitted_keys == (_key(1), _key(2), _key(3))
    assert result.active_count == 3
    assert result.remaining == 2


def test_existing_admission_is_reused_without_refreshing_timestamp(tmp_path) -> None:
    path = tmp_path / "quota.json"
    store = ProductSignalQuotaStore(path)

    first = store.admit(SUBJECT_A, [_key(1)], limit=5, now=T0)
    second = store.admit(
        SUBJECT_A,
        [_key(1), _key(2)],
        limit=5,
        now=T0 + timedelta(hours=23),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload["subjects"][SUBJECT_A]["signals"][_key(1)]

    assert first.newly_admitted_keys == (_key(1),)
    assert second.allowed_keys == (_key(1), _key(2))
    assert second.newly_admitted_keys == (_key(2),)
    assert record["first_admitted_at"] == "2026-09-28T00:00:00Z"


def test_non_requested_active_signals_still_consume_capacity(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")
    store.admit(
        SUBJECT_A,
        [_key(index) for index in range(1, 6)],
        limit=5,
        now=T0,
    )

    result = store.admit(SUBJECT_A, [_key(6)], limit=5, now=T0 + timedelta(hours=1))

    assert result.allowed_keys == ()
    assert result.newly_admitted_keys == ()
    assert result.active_count == 5
    assert result.remaining == 0


def test_exact_24h_expiry_frees_slots(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")
    store.admit(
        SUBJECT_A,
        [_key(index) for index in range(1, 6)],
        limit=5,
        now=T0,
    )

    before = store.admit(
        SUBJECT_A,
        [_key(6)],
        limit=5,
        now=T0 + timedelta(seconds=PRODUCT_SIGNAL_QUOTA_WINDOW_SECONDS - 1),
    )
    at_expiry = store.admit(
        SUBJECT_A,
        [_key(6)],
        limit=5,
        now=T0 + timedelta(seconds=PRODUCT_SIGNAL_QUOTA_WINDOW_SECONDS),
    )

    assert before.allowed_keys == ()
    assert at_expiry.allowed_keys == (_key(6),)
    assert at_expiry.newly_admitted_keys == (_key(6),)
    assert at_expiry.active_count == 1
    assert at_expiry.remaining == 4


def test_subject_ledgers_are_isolated(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")
    store.admit(
        SUBJECT_A,
        [_key(index) for index in range(1, 6)],
        limit=5,
        now=T0,
    )

    other = store.admit(SUBJECT_B, [_key(6)], limit=5, now=T0)

    assert other.allowed_keys == (_key(6),)
    assert other.active_count == 1
    assert other.remaining == 4


def test_reopened_store_preserves_ledger(tmp_path) -> None:
    path = tmp_path / "quota.json"
    ProductSignalQuotaStore(path).admit(
        SUBJECT_A,
        [_key(1), _key(2)],
        limit=5,
        now=T0,
    )

    reopened = ProductSignalQuotaStore(path)
    result = reopened.admit(
        SUBJECT_A,
        [_key(2), _key(3)],
        limit=5,
        now=T0 + timedelta(hours=2),
    )

    assert result.allowed_keys == (_key(2), _key(3))
    assert result.newly_admitted_keys == (_key(3),)
    assert result.active_count == 3


def test_persisted_schema_contains_only_subject_signal_key_and_timestamp(tmp_path) -> None:
    path = tmp_path / "quota.json"
    store = ProductSignalQuotaStore(path)
    store.admit(SUBJECT_A, [_key(1)], limit=5, now=T0)

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == PRODUCT_SIGNAL_QUOTA_SCHEMA_VERSION
    assert set(payload) == {"schema_version", "subjects"}
    assert set(payload["subjects"][SUBJECT_A]) == {"signals"}
    assert set(payload["subjects"][SUBJECT_A]["signals"][_key(1)]) == {
        "first_admitted_at"
    }


@pytest.mark.parametrize(
    "subject_key",
    [
        "guest:not-a-uuid",
        "anonymous:11111111-1111-4111-8111-111111111111",
        "",
    ],
)
def test_invalid_subject_keys_are_rejected_before_io(tmp_path, subject_key: str) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    with pytest.raises(ValueError):
        store.admit(subject_key, [_key(1)], limit=5, now=T0)

    assert not store.path.exists()


@pytest.mark.parametrize(
    "signal_key",
    ["", "ethereum:TokenMint1", "solana:", "solana:Token Mint1"],
)
def test_invalid_signal_keys_are_rejected_before_io(tmp_path, signal_key: str) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    with pytest.raises(ValueError):
        store.admit(SUBJECT_A, [signal_key], limit=5, now=T0)

    assert not store.path.exists()


def test_corrupt_or_wrong_schema_ledger_fails_closed(tmp_path) -> None:
    path = tmp_path / "quota.json"
    path.write_text("{not-json", encoding="utf-8")
    store = ProductSignalQuotaStore(path)

    with pytest.raises(ProductSignalQuotaStoreUnavailable):
        store.admit(SUBJECT_A, [_key(1)], limit=5, now=T0)

    path.write_text(
        json.dumps({"schema_version": 999, "subjects": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ProductSignalQuotaStoreUnavailable):
        store.admit(SUBJECT_A, [_key(1)], limit=5, now=T0)


def test_future_admission_time_fails_closed(tmp_path) -> None:
    path = tmp_path / "quota.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": PRODUCT_SIGNAL_QUOTA_SCHEMA_VERSION,
                "subjects": {
                    SUBJECT_A: {
                        "signals": {
                            _key(1): {
                                "first_admitted_at": "2026-09-28T00:00:01Z"
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    store = ProductSignalQuotaStore(path)

    with pytest.raises(ProductSignalQuotaStoreUnavailable, match="future"):
        store.admit(SUBJECT_A, [_key(2)], limit=5, now=T0)


def test_atomic_replace_failure_raises_and_does_not_commit_admission(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "quota.json"
    store = ProductSignalQuotaStore(path)
    store.admit(SUBJECT_A, [_key(1)], limit=5, now=T0)
    before = path.read_bytes()

    def broken_replace(source, destination):
        raise OSError("disk unavailable")

    monkeypatch.setattr(
        "application.product_signal_quota_store.os.replace",
        broken_replace,
    )

    with pytest.raises(ProductSignalQuotaStoreUnavailable, match="persisted"):
        store.admit(
            SUBJECT_A,
            [_key(2)],
            limit=5,
            now=T0 + timedelta(minutes=1),
        )

    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".quota.json.*.tmp"))
