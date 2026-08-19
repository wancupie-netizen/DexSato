from datetime import datetime, timezone

from application.market_catalyst_service import (
    OFFICIAL_FEEDS, fetch_market_catalysts, parse_official_feed,
)


def _rss(*items):
    return "<rss><channel>" + "".join(
        f"<item><title>{title}</title><link>{url}</link><pubDate>{date}</pubDate></item>"
        for title, url, date in items
    ) + "</channel></rss>"


def test_parses_recent_primary_source_release():
    items = parse_official_feed(
        _rss(("Federal Reserve issues FOMC statement",
              "https://www.federalreserve.gov/newsevents/pressreleases/a.htm",
              "Tue, 18 Aug 2026 18:00:00 GMT")),
        source="Federal Reserve", category="MONETARY_POLICY",
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert items[0]["source_tier"] == "PRIMARY_OFFICIAL"
    assert items[0]["causality"] == "NOT_ESTABLISHED"


def test_filters_irrelevant_sec_release():
    items = parse_official_feed(
        _rss(
            ("SEC charges accounting firm", "https://www.sec.gov/news/a", "Tue, 18 Aug 2026 18:00:00 GMT"),
            ("SEC proposes new regulation for crypto assets", "https://www.sec.gov/news/b", "Tue, 18 Aug 2026 17:00:00 GMT"),
        ), source="SEC", category="REGULATION",
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert [item["title"] for item in items] == ["SEC proposes new regulation for crypto assets"]


def test_one_failed_feed_does_not_remove_other_sources():
    class Response:
        def __init__(self, text): self.text = text
        def raise_for_status(self): return None

    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if "sec.gov" in url:
            raise RuntimeError("blocked")
        return Response(_rss(("Official release", url.replace("/feeds/", "/news/"),
                              "Tue, 18 Aug 2026 18:00:00 GMT")))

    result = fetch_market_catalysts(
        request_get=get, now=datetime(2026, 8, 19, tzinfo=timezone.utc)
    )
    assert len(calls) == len(OFFICIAL_FEEDS)
    assert result["status"] == "AVAILABLE"
    assert "U.S. Securities and Exchange Commission" in result["failed_sources"]
