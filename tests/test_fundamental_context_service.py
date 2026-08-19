from datetime import datetime, timezone

import pytest

from application.fundamental_context_service import (
    BLS_API_URL, SERIES_IDS, build_fundamental_context, fetch_fundamental_context,
)


def _series(series_id, values):
    data = []
    year, month = 2025, 1
    for value in values:
        data.append({"year": str(year), "period": f"M{month:02d}",
                     "periodName": datetime(year, month, 1).strftime("%B"),
                     "value": str(value)})
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return {"seriesID": series_id, "data": list(reversed(data))}


def _payload():
    return {"status": "REQUEST_SUCCEEDED", "Results": {"series": [
        _series(SERIES_IDS[0], [100000, 100100, 100250]),
        _series(SERIES_IDS[1], [4.0, 4.1, 4.2]),
        _series(SERIES_IDS[2], [100 + index for index in range(14)]),
    ]}}


def test_builds_auditable_official_context_without_causal_claim():
    context = build_fundamental_context(
        _payload(), collected_at=datetime(2026, 3, 1, tzinfo=timezone.utc)
    )
    assert context["status"] == "AVAILABLE"
    assert context["source_tier"] == "PRIMARY_OFFICIAL"
    assert context["relationship"] == "CONTEXTUAL"
    assert context["causality"] == "NOT_ESTABLISHED"
    assert context["state"] == "MIXED_MACRO_CONTEXT"
    assert context["indicators"][0]["actual_display"] == "+150K"
    assert context["indicators"][0]["previous_display"] == "+100K"
    assert context["indicators"][1]["actual_display"] == "4.2%"
    assert context["indicators"][2]["series_id"] == "CUUR0000SA0"
    assert "does not" in context["summary"]


def test_rejects_incomplete_official_series():
    payload = _payload()
    payload["Results"]["series"][2]["data"] = payload["Results"]["series"][2]["data"][:3]
    with pytest.raises(ValueError, match="CPI"):
        build_fundamental_context(payload)


def test_fetch_posts_all_series_once():
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _payload()

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    result = fetch_fundamental_context(request_post=post, timeout=3.0)
    assert result["status"] == "AVAILABLE"
    assert calls == [(BLS_API_URL, {"json": {"seriesid": list(SERIES_IDS)}, "timeout": 3.0})]
