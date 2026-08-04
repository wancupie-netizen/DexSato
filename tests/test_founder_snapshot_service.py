"""
Tests for DexSato Founder Snapshot Service.
"""

from datetime import (
    datetime,
    timezone,
)

import pytest

from application.founder_snapshot_service import (
    build_snapshot_payload,
    generate_latest_snapshot,
    read_latest_snapshot,
    write_latest_snapshot,
)


GENERATED_AT = datetime(
    2026,
    7,
    24,
    8,
    0,
    tzinfo=timezone.utc,
)


def build_unavailable_results():
    """
    Build JSON-serializable service input without engine calls.
    """

    return [
        {
            "token": "BTC",
            "card": None,
            "error": "Test unavailable.",
        },
        {
            "token": "ETH",
            "card": None,
            "error": "Test unavailable.",
        },
    ]


def test_should_build_snapshot_payload():
    """
    Snapshot should contain metadata and coin totals.
    """

    payload = build_snapshot_payload(
        results=build_unavailable_results(),
        generated_at=GENERATED_AT,
    )

    assert payload["generated_at"] == (
        "2026-07-24T08:00:00+00:00"
    )

    assert payload["total_coins"] == 2

    assert payload["available_coins"] == 0

    assert payload["unavailable_coins"] == 2

    assert len(
        payload["coins"],
    ) == 2


def test_should_write_and_read_latest_snapshot(
    tmp_path,
):
    """
    Written snapshot should be readable.
    """

    snapshot_file = (
        tmp_path
        / "latest_snapshot.json"
    )

    payload = build_snapshot_payload(
        results=build_unavailable_results(),
        generated_at=GENERATED_AT,
    )

    output_file = write_latest_snapshot(
        payload=payload,
        snapshot_file=snapshot_file,
    )

    assert output_file == (
        snapshot_file.resolve()
    )

    loaded = read_latest_snapshot(
        snapshot_file=snapshot_file,
    )

    assert loaded == payload


def test_should_generate_latest_snapshot(
    tmp_path,
):
    """
    Generator should scan once and store one snapshot.
    """

    calls = 0

    def fake_build_results():

        nonlocal calls

        calls += 1

        return build_unavailable_results()

    snapshot_file = (
        tmp_path
        / "latest_snapshot.json"
    )

    result = generate_latest_snapshot(
        snapshot_file=snapshot_file,
        build_results=fake_build_results,
        generated_at=GENERATED_AT,
    )

    assert calls == 1

    assert result["success"] is True

    assert result["total_coins"] == 2

    assert result["unavailable_coins"] == 2

    assert snapshot_file.exists()


def test_should_reject_naive_timestamp():
    """
    Snapshot timestamps must include timezone information.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Snapshot timestamp must be timezone-aware"
        ),
    ):

        build_snapshot_payload(
            results=[],
            generated_at=datetime(
                2026,
                7,
                24,
                8,
                0,
            ),
        )


def test_should_reject_missing_snapshot(
    tmp_path,
):
    """
    Reader should clearly reject a missing snapshot.
    """

    with pytest.raises(
        FileNotFoundError,
        match=(
            "Latest DexSato snapshot is not available"
        ),
    ):

        read_latest_snapshot(
            snapshot_file=(
                tmp_path
                / "missing.json"
            ),
        )