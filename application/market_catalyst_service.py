"""Verified market catalysts from primary-source government RSS feeds."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from xml.etree import ElementTree


OFFICIAL_FEEDS = (
    ("Federal Reserve", "MONETARY_POLICY", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("U.S. Bureau of Labor Statistics", "EMPLOYMENT", "https://www.bls.gov/feed/empsit.rss"),
    ("U.S. Bureau of Labor Statistics", "INFLATION", "https://www.bls.gov/feed/cpi.rss"),
    ("U.S. Securities and Exchange Commission", "REGULATION", "https://www.sec.gov/news/pressreleases.rss"),
)
SEC_RELEVANCE_TERMS = (
    "crypto", "digital asset", "bitcoin", "ether", "blockchain",
    "exchange-traded", "securities market", "trading platform",
)


def _text(node: ElementTree.Element, name: str) -> str:
    child = node.find(name)
    return "" if child is None or child.text is None else child.text.strip()


def parse_official_feed(
    xml_text: str, *, source: str, category: str,
    now: datetime | None = None, maximum_age_days: int = 45,
) -> list[dict[str, object]]:
    """Parse recent RSS items and retain only relevant SEC announcements."""
    root = ElementTree.fromstring(xml_text)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=maximum_age_days)
    catalysts = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        published_raw = _text(item, "pubDate")
        if not title or not link or not published_raw:
            continue
        try:
            published_at = parsedate_to_datetime(published_raw)
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            published_at = published_at.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        if published_at < cutoff:
            continue
        if category == "REGULATION" and not any(
            term in title.casefold() for term in SEC_RELEVANCE_TERMS
        ):
            continue
        catalysts.append({
            "title": title,
            "url": link,
            "published_at": published_at.isoformat(),
            "source": source,
            "category": category,
            "source_tier": "PRIMARY_OFFICIAL",
            "relationship": "CONTEXTUAL",
            "causality": "NOT_ESTABLISHED",
        })
    return catalysts


def fetch_market_catalysts(
    *, request_get: Callable[..., Any] | None = None,
    now: datetime | None = None, timeout: float = 12.0,
) -> dict[str, object]:
    """Fetch official feeds independently so one provider cannot fail all."""
    if request_get is None:
        import requests

        request_get = requests.get
    catalysts: list[dict[str, object]] = []
    failed_sources: list[str] = []
    for source, category, url in OFFICIAL_FEEDS:
        try:
            response = request_get(
                url, timeout=timeout,
                headers={"User-Agent": "DexSato market-context contact@dexsato.com"},
            )
            response.raise_for_status()
            catalysts.extend(parse_official_feed(
                response.text, source=source, category=category, now=now,
            ))
        except Exception:
            if source not in failed_sources:
                failed_sources.append(source)
    catalysts.sort(key=lambda item: str(item["published_at"]), reverse=True)
    return {
        "status": "AVAILABLE" if catalysts else "NO_RECENT_CATALYSTS",
        "collected_at": (now or datetime.now(timezone.utc)).isoformat(),
        "relationship": "CONTEXTUAL",
        "causality": "NOT_ESTABLISHED",
        "catalysts": catalysts[:6],
        "failed_sources": failed_sources,
    }
