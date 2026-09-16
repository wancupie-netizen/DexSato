"""Public read-only terminal for DexSato Solana Discovery."""

from __future__ import annotations

import json
import re
from html import escape, unescape
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


def _usd(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.2f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:,.2f}K"
    return f"${amount:,.6f}" if amount < 1 else f"${amount:,.2f}"

def _compact_usd(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    if amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.2f}".rstrip("0").rstrip(".")
        return f"${text}B"
    if amount >= 1_000_000:
        text = f"{amount / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"${text}M"
    if amount >= 1_000:
        text = f"{amount / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"${text}K"
    return f"${amount:,.0f}"


def _solana_dex_card_metrics() -> dict[str, str]:
    """Fetch presentation-only Solana DEX card metrics from public DefiLlama endpoints."""
    metrics = {
        "volume": "—",
        "change": "—",
        "change_class": "",
        "tvl": "—",
        "state": "UNAVAILABLE",
        "dot_class": " is-offline",
        "line_path": "",
        "area_path": "",
    }

    dex_endpoint = (
        "https://api.llama.fi/overview/dexs/solana"
        "?excludeTotalDataChart=false"
        "&excludeTotalDataChartBreakdown=true"
        "&dataType=dailyVolume"
    )
    try:
        request = Request(
            dex_endpoint,
            headers={"Accept": "application/json", "User-Agent": "DexSato/1.0"},
        )
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))

        total = float(payload.get("total24h"))
        if total < 0:
            raise ValueError("negative total24h")

        metrics["volume"] = _compact_usd(total)
        metrics["state"] = "LIVE"
        metrics["dot_class"] = ""

        change_value = None
        try:
            previous_value = float(payload.get("total48hto24h"))
            if previous_value > 0:
                change_value = ((total - previous_value) / previous_value) * 100
        except (TypeError, ValueError):
            change_value = None

        points: list[float] = []
        chart = payload.get("totalDataChart")
        if isinstance(chart, list):
            for item in chart[-30:]:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                try:
                    value = float(item[1])
                except (TypeError, ValueError):
                    continue
                if value >= 0:
                    points.append(value)

        if change_value is None and len(points) >= 2 and points[-2] > 0:
            change_value = ((points[-1] - points[-2]) / points[-2]) * 100

        if change_value is not None:
            arrow = "▲" if change_value >= 0 else "▼"
            metrics["change"] = f"{arrow} {abs(change_value):.1f}%"
            metrics["change_class"] = " up" if change_value >= 0 else " down"

        if len(points) >= 2:
            width, height = 1000.0, 150.0
            top_pad, bottom_pad = 10.0, 16.0
            low, high = min(points), max(points)
            span = high - low
            if span <= 0:
                span = max(high, 1.0)

            coordinates: list[tuple[float, float]] = []
            last_index = len(points) - 1
            for index, value in enumerate(points):
                x = (index / last_index) * width
                normalized = (value - low) / span
                y = (height - bottom_pad) - normalized * (height - top_pad - bottom_pad)
                coordinates.append((x, y))

            line = " ".join(
                ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
                for index, (x, y) in enumerate(coordinates)
            )
            first_x = coordinates[0][0]
            last_x = coordinates[-1][0]
            area = f"{line} L{last_x:.1f},{height:.1f} L{first_x:.1f},{height:.1f} Z"
            metrics["line_path"] = line
            metrics["area_path"] = area
    except Exception:
        pass

    tvl_endpoint = "https://api.llama.fi/v2/historicalChainTvl/Solana"
    try:
        request = Request(
            tvl_endpoint,
            headers={"Accept": "application/json", "User-Agent": "DexSato/1.0"},
        )
        with urlopen(request, timeout=4) as response:
            tvl_payload = json.loads(response.read().decode("utf-8"))

        if isinstance(tvl_payload, list) and tvl_payload:
            latest = tvl_payload[-1]
            if isinstance(latest, dict):
                metrics["tvl"] = _compact_usd(latest.get("tvl"))
    except Exception:
        pass

    return metrics


def _solana_perps_volume_24h() -> str:
    # SOLANA-UI-03C.1 — Replace Trades with Perps Volume 24H
    """Read Solana 24h perps volume for presentation only."""
    api_endpoint = (
        "https://api.llama.fi/overview/derivatives/Solana"
        "?excludeTotalDataChart=true"
        "&excludeTotalDataChartBreakdown=true"
        "&dataType=dailyVolume"
    )
    try:
        request = Request(
            api_endpoint,
            headers={"Accept": "application/json", "User-Agent": "DexSato/1.0"},
        )
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        total = float(payload.get("total24h"))
        if total >= 0:
            return _compact_usd(total)
    except Exception:
        pass

    page_endpoint = "https://defillama.com/chain/solana"
    try:
        request = Request(
            page_endpoint,
            headers={
                "Accept": "text/html",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/140 Safari/537.36"
                ),
            },
        )
        with urlopen(request, timeout=5) as response:
            raw_html = response.read().decode("utf-8", errors="ignore")

        plain = unescape(re.sub(r"<[^>]+>", " ", raw_html))
        plain = re.sub(r"\s+", " ", plain)

        match = re.search(
            r"Perps\s+Volume\s*\(24h\)\s*\$?\s*"
            r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*([kKmMbB]?)",
            plain,
        )
        if match:
            amount = float(match.group(1).replace(",", ""))
            suffix = match.group(2).lower()
            multiplier = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}.get(suffix, 1.0)
            return _compact_usd(amount * multiplier)
    except Exception:
        pass

    return "—"


def _solana_priority_fee() -> tuple[str, str]:
    """Read a presentation-only recent Solana priority fee from public RPC."""
    endpoint = "https://api.mainnet-beta.solana.com"
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getRecentPrioritizationFees",
            "params": [],
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "DexSato/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=4) as response:
            result = json.loads(response.read().decode("utf-8"))

        rows = result.get("result")
        if not isinstance(rows, list):
            raise ValueError("missing prioritization fee result")

        values: list[int] = []
        for row in rows[-60:]:
            if not isinstance(row, dict):
                continue
            try:
                fee = int(row.get("prioritizationFee"))
            except (TypeError, ValueError):
                continue
            if fee >= 0:
                values.append(fee)

        if not values:
            raise ValueError("no recent prioritization fee samples")

        nonzero = sorted(value for value in values if value > 0)
        samples = nonzero if nonzero else sorted(values)
        middle = len(samples) // 2
        if len(samples) % 2:
            median = samples[middle]
        else:
            median = int(round((samples[middle - 1] + samples[middle]) / 2))

        # HEADER V1.1A — Zero Priority Fee Display Fix
        if median == 0:
            return "Gas · Low", ""

        if median >= 1_000_000:
            label = f"{median / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
        elif median >= 1_000:
            label = f"{median / 1_000:.2f}".rstrip("0").rstrip(".") + "K"
        else:
            label = f"{median:,}"

        return f"Gas · {label} µLam/CU", ""
    except Exception:
        return "Gas · —", " is-offline"


def _short_address(value: str) -> str:
    return f"{value[:7]}…{value[-7:]}" if len(value) > 18 else value


def _why_now(candidate: dict[str, Any]) -> str:
    """Return one compact, non-promotional reason to inspect this candidate."""
    reasons: list[str] = []
    age = str(candidate.get("pair_age") or "").strip().lower()
    try:
        liquidity = float(candidate.get("liquidity_usd") or 0)
    except (TypeError, ValueError):
        liquidity = 0.0
    try:
        volume = float(candidate.get("volume_24h_usd") or 0)
    except (TypeError, ValueError):
        volume = 0.0

    if age.endswith("h"):
        try:
            hours = float(age[:-1] or 0)
        except ValueError:
            hours = 999
        if hours <= 6:
            reasons.append("Fresh pool")
    if volume >= 100_000:
        reasons.append("Strong 24h activity")
    elif volume >= 25_000:
        reasons.append("Active 24h volume")
    if liquidity >= 25_000:
        reasons.append("Healthy liquidity")
    elif liquidity >= 5_000:
        reasons.append("Liquidity qualified")
    return " / ".join(reasons[:2]) or "Qualified market activity"


def _signed_percent(value: Any) -> tuple[str, str]:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—", ""
    return f"{amount:+.2f}%", "up" if amount >= 0 else "down"


def _trending_row(item: dict[str, Any], rank: int) -> str:
    token_address = str(item.get("token_address") or "").strip()
    symbol = escape(str(item.get("symbol") or "Unknown"))
    name = escape(str(item.get("name") or "Unknown token"))
    icon = str(item.get("icon") or "").strip()
    href = escape(str(item.get("href") or ""), quote=True)
    price = escape(_usd(item.get("price_usd")))
    change, change_class = _signed_percent(item.get("change_1h"))
    volume = escape(_compact_usd(item.get("volume_1h_usd")))
    liquidity = escape(_compact_usd(item.get("liquidity_usd")))
    signal_data = item.get("detected_signal")
    signal_primary = ""
    signal_evidence: list[str] = []
    signal_direction = "neutral"
    if isinstance(signal_data, dict):
        signal_primary = str(signal_data.get("primary_signal") or "").strip()
        raw_evidence = signal_data.get("secondary_evidence")
        if isinstance(raw_evidence, list):
            signal_evidence = [
                str(value).strip()
                for value in raw_evidence[:2]
                if str(value).strip()
            ]
        raw_direction = str(signal_data.get("direction") or "neutral").strip().lower()
        if raw_direction in {"bullish", "bearish", "mixed", "neutral"}:
            signal_direction = raw_direction
    elif signal_data:
        signal_primary = str(signal_data).strip()

    if signal_primary:
        evidence_markup = (
            f'<small>{escape(" · ".join(signal_evidence))}</small>'
            if signal_evidence
            else ""
        )
        signal_markup = (
            f'<span class="dex-trending-signal is-active is-{signal_direction}">'
            f'<strong>{escape(signal_primary)}</strong>{evidence_markup}</span>'
        )
    else:
        signal_markup = '<span class="dex-trending-signal">—</span>'
    icon_markup = (
        f'<img src="{escape(icon, quote=True)}" alt="" loading="lazy" referrerpolicy="no-referrer">'
        if icon.startswith("https://")
        else f'<span class="dex-trending-avatar">{escape(symbol[:2].upper())}</span>'
    )
    token_content = f'{icon_markup}<span><strong>{symbol}</strong><small>{name}</small></span>'
    token_link = (
        f'<a class="dex-trending-token-link" href="{href}">{token_content}</a>'
        if token_address and href
        else f'<div class="dex-trending-token-link">{token_content}</div>'
    )

    return (
        '<article class="dex-trending-row">'
        f'<div class="dex-trending-token"><span class="dex-trending-rank">{rank:02d}</span>{token_link}</div>'
        f'<div class="dex-trending-value"><strong>{price}</strong></div>'
        f'<div class="dex-trending-value"><strong class="{change_class}">{escape(change)}</strong></div>'
        f'<div class="dex-trending-value"><strong>{volume}</strong></div>'
        f'<div class="dex-trending-value"><strong>{liquidity}</strong></div>'
        f'<div class="dex-trending-value dex-trending-signal-cell">{signal_markup}</div>'
        '</article>'
    )


def _render_trending_panel(trending: dict[str, Any] | None) -> str:
    data = trending if isinstance(trending, dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    row_markup = "".join(
        _trending_row(item, rank)
        for rank, item in enumerate(
            (row for row in rows if isinstance(row, dict)), start=1
        )
    )

    if not row_markup:
        message = escape(
            str(data.get("message") or "Trending data is temporarily unavailable.")
        )
        return (
            '<div class="dex-category-placeholder"><div>'
            '<strong>No eligible Trending tokens displayed</strong>'
            f'<small>{message} DexSato does not fabricate replacement rows.</small>'
            '</div></div>'
        )

    return (
        '<div class="dex-trending-table">'
        '<div class="dex-trending-head" aria-hidden="true">'
        '<span>Token</span><span>Price</span><span>1h %</span>'
        '<span>Volume 1h</span><span>Liquidity</span><span>Detected Signal</span>'
        '</div>'
        f'<div class="dex-trending-list">{row_markup}</div>'
        '</div>'
    )


def _candidate_row(candidate: dict[str, Any], rank: int) -> str:
    symbol = escape(str(candidate.get("symbol") or "Unknown"))
    name = escape(str(candidate.get("name") or "Unknown token"))
    quote_symbol = escape(str(candidate.get("quote_symbol") or "Unknown"))
    address_raw = str(candidate.get("token_address") or "")
    address = escape(address_raw)
    dex = escape(str(candidate.get("dex_id") or "Unknown"))
    price = escape(_usd(candidate.get("price_usd")))
    liquidity = escape(_usd(candidate.get("liquidity_usd")))
    volume = escape(_usd(candidate.get("volume_24h_usd")))
    try:
        change_value = float(candidate.get("change_24h"))
        change = f"{change_value:+.2f}%"
        change_class = "up" if change_value >= 0 else "down"
    except (TypeError, ValueError):
        change, change_class = "Unavailable", ""
    age = escape(str(candidate.get("pair_age") or "Unavailable"))
    observation = "Currently qualified" if candidate.get("currently_qualified") is True else "Previously qualified"
    source = (
        f'<a class="inspect-link" href="/discovery/solana/{quote(address_raw, safe="")}">'
        'Open Analysis &rarr;</a>'
    ) if address_raw else ""
    return (
        f'<article class="candidate-row candidate-row-v32" data-token-address="{address}">'
        f'<div class="token-cell compact-token"><span class="rank">{rank:02d}</span><div>'
        f'<strong>{symbol} / {quote_symbol}</strong><span>{name}</span><small>{dex} / exact pool</small></div></div>'
        f'<div class="feed-value"><span>Price / 24h</span><strong>{price}</strong><small class="{change_class}">{escape(change)}</small></div>'
        f'<div class="feed-value"><span>Liquidity</span><strong>{liquidity}</strong></div>'
        f'<div class="feed-value"><span>24h Vol</span><strong>{volume}</strong></div>'
        f'<div class="feed-value"><span>Age</span><strong>{age}</strong></div>'
        f'<div class="why-now"><span>Observation</span><strong><i class="why-dot" aria-hidden="true"></i>{observation}</strong></div>'
        f'<div class="feed-action">{source}</div></article>'
    )


def render_solana_discovery_page(
    feed: dict[str, Any] | None = None,
    *,
    trending: dict[str, Any] | None = None,
) -> str:
    """Render qualified discovery evidence without implying token safety."""
    data = feed or {}
    trending_panel = _render_trending_panel(trending)
    dex_card = _solana_dex_card_metrics()
    dex_volume_24h = dex_card["volume"]
    dex_volume_change = dex_card["change"]
    dex_volume_change_class = dex_card["change_class"]
    dex_tvl = dex_card["tvl"]
    dex_volume_state = dex_card["state"]
    dex_volume_dot_class = dex_card["dot_class"]
    dex_volume_line = dex_card["line_path"]
    dex_volume_area = dex_card["area_path"]
    perps_volume_24h = _solana_perps_volume_24h()
    solana_gas_label, solana_gas_dot_class = _solana_priority_fee()
    connected = data.get("connected") is True
    fresh = data.get("fresh") is True
    status_heading = "Collector live" if connected and fresh else (
        "Collector connected" if connected else "Feed unavailable"
    )
    status_message = str(
        data.get("message")
        or "The collector remains separate while its data contract and qualification rules are validated."
    )
    tokens = str(data.get("tokens_observed")) if data.get("tokens_observed") is not None else "—"
    pairs = str(data.get("pair_resolved")) if data.get("pair_resolved") is not None else "—"
    updated = str(data.get("updated_label") or "Not connected")
    status_label = str(data.get("collector_status") or "Prototype state")
    candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
    qualified = str(data.get("qualified_candidates")) if data.get("qualified_candidates") is not None else "—"
    view = str(data.get("view") or "qualified")
    page_number = int(data.get("page") or 1)
    page_size = int(data.get("page_size") or 25)
    page_count = int(data.get("page_count") or 1)
    search_query = str(data.get("search_query") or "")
    query_suffix = f'&q={quote(search_query)}' if search_query else ""
    offset = (page_number - 1) * page_size
    candidate_rows = "".join(
        _candidate_row(item, rank)
        for rank, item in enumerate((item for item in candidates if isinstance(item, dict)), start=offset + 1)
    )
    previous_link = f'/discovery/solana?view={quote(view)}&page={page_number - 1}{query_suffix}' if page_number > 1 else ""
    next_link = f'/discovery/solana?view={quote(view)}&page={page_number + 1}{query_suffix}' if page_number < page_count else ""
    pagination = (
        '<nav class="pagination" aria-label="Discovery pages">'
        + (f'<a href="{previous_link}">← Previous</a>' if previous_link else '<span>← Previous</span>')
        + f'<strong>Page {page_number} of {page_count}</strong>'
        + (f'<a href="{next_link}">Next →</a>' if next_link else '<span>Next →</span>')
        + '</nav>'
    )
    dex_ids = data.get("observed_dex_ids") if isinstance(data.get("observed_dex_ids"), list) else []
    dex_badges = "".join(f'<span>{escape(str(dex))}</span>' for dex in dex_ids) or '<em>None currently observed</em>'
    txns = data.get("observed_txns_24h")
    txns_label = f'{int(txns):,}' if isinstance(txns, (int, float)) else "Unavailable"
    observed_volume_raw = data.get("observed_volume_24h_usd")
    observed_volume = "$0.00" if observed_volume_raw == 0 else _usd(observed_volume_raw)
    sort_label = {"qualified": "Last observed", "recent": "First qualified", "archive": "Last qualified"}.get(view, "Last qualified")
    clear_search = f'<a class="clear-search" href="/discovery/solana?view={quote(view)}&page=1">Clear</a>' if search_query else ""
    if search_query:
        empty_heading = "No matching token found."
        empty_copy = "Try another name, symbol, contract, pair address or DEX."
        empty_actions = f'<a class="primary-link" href="/discovery/solana?view={quote(view)}&page=1">Clear search</a>'
    elif view == "qualified":
        empty_heading = "No qualified SOL pairs right now."
        empty_copy = "Tokens appear here only after identity, liquidity, activity and freshness checks pass."
        empty_actions = ""
    elif view == "recent":
        empty_heading = "No new discovery was first qualified in the last 24 hours."
        empty_copy = "Older observations remain available in the persistent archive."
        empty_actions = ""
    else:
        empty_heading = "The discovery archive is empty."
        empty_copy = "Records will appear after a token first passes every qualification requirement."
        empty_actions = '<a class="primary-link" href="/">Back to Markets</a>'
    empty_actions_markup = (
        f'<div class="empty-actions">{empty_actions}</div>' if empty_actions else ""
    )
    empty_state = (
        '<div class="empty-state"><div class="empty-icon" aria-hidden="true">◎</div><div>'
        f'<h3>{empty_heading}</h3><p>{empty_copy}</p>'
        f'{empty_actions_markup}</div></div>'
    )
    discovery_feed = (
        '<div class="sort-note"><span>__VIEW_TOTAL__ matching observations</span><span>Sorted by: __SORT_LABEL__</span></div>'
        '<div class="feed-columns-v33" aria-hidden="true"><span>Token</span><span>Price / 24h</span><span>Liquidity</span><span>24h Vol</span><span>Age</span><span>Observation</span><span></span></div>'
        f'<div class="candidate-list">{candidate_rows}</div>{pagination}'
        if candidate_rows
        else empty_state
    )
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DexSato · Solana Discovery Terminal</title>
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script>try{const t=localStorage.getItem("dexsato-theme");if(t==="plain"||t==="intel")document.documentElement.dataset.theme=t;}catch(error){}</script>
  <style>
    :root{color-scheme:dark;--bg:#070b12;--panel:#0c111b;--panel2:#101827;--panel3:#131e2e;--line:#1b2b3d;--line2:#25384e;--text:#e8eef7;--muted:#90a0b5;--faint:#64758b;--blue:#518df4;--cyan:#14f1d9;--purple:#9945ff;--amber:#f4b544;--green:#22c88c;--risk:#f05d72;--font-display:"Bahnschrift SemiBold","Bahnschrift","Arial Narrow","Segoe UI",sans-serif;--font-ui:"Segoe UI Variable Text","Segoe UI Variable","Segoe UI",Arial,sans-serif;--font-mono:"Cascadia Mono","Cascadia Code","Consolas","Courier New",monospace}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-ui);font-size:15px;line-height:1.5;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}button,input{font:inherit}
    h1,h2,h3,.terminal-name strong,.status-pill strong,.metric strong,.token-cell strong,.evidence-cell>strong,.rail-card h3,.future-box strong{font-family:var(--font-display);font-stretch:semi-condensed;font-weight:700}.eyebrow,.terminal-name span,.status-pill span,.metric span,.market-cell span,.activity-tag,.rail-kicker,.risk-line b,.jupiter-status{font-family:var(--font-mono)}code,.rank,.market-cell strong,.status-detail strong,.action-cell code{font-family:var(--font-mono)}
    .shell{width:min(1420px,calc(100% - 40px));margin:0 auto;padding:16px 0 30px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 0 14px;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:13px}.brand img{width:132px;padding:5px;border-radius:7px;background:#071525}.terminal-name{display:flex;flex-direction:column}.terminal-name strong{font-size:13px;letter-spacing:.04em}.terminal-name span{color:var(--muted);font-size:10px;letter-spacing:.1em;text-transform:uppercase}.top-actions,.theme-switcher{display:flex;align-items:center;gap:7px}.back-link{padding:8px 11px;border:1px solid var(--line2);border-radius:6px;color:var(--text);font-size:12px;font-weight:800;text-decoration:none}.theme-switcher{gap:2px;padding:2px;border:1px solid var(--line2);border-radius:7px;background:var(--panel)}.theme-option{display:grid;place-items:center;width:31px;height:31px;padding:0;border:0;border-radius:5px;background:transparent;color:var(--muted);cursor:pointer}.theme-option.active{background:#211c4c;color:#fff}.theme-option:focus-visible,.back-link:focus-visible,.inspect-link:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
    .terminal-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:end;padding:28px 2px 20px}.eyebrow{color:var(--cyan);font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase}.terminal-head h1{margin:7px 0 0;font-size:36px;line-height:1.05;letter-spacing:-.025em}.terminal-head p{max-width:720px;margin:9px 0 0;color:var(--muted);font-size:15px}.status-cluster{display:flex;gap:8px}.status-pill{min-width:150px;padding:10px 12px;border:1px solid var(--line2);border-radius:7px;background:var(--panel)}.status-pill span,.status-pill small{display:block}.status-pill span{color:var(--faint);font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}.status-pill strong{display:block;margin-top:3px;font-size:15px;letter-spacing:.01em}.status-pill small{margin-top:2px;color:var(--muted);font-size:10px}.status-pill.live{border-left:2px solid var(--green)}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);background:var(--panel)}.metric{position:relative;padding:16px 18px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric:before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,var(--purple),var(--cyan));opacity:.7}.metric span{display:block;color:var(--faint);font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.metric strong{display:block;margin-top:5px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:23px}.metric small{display:block;margin-top:2px;color:var(--muted);font-size:10px}
    .workspace{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:14px;margin-top:14px}.feed-panel,.rail-card{border:1px solid var(--line);background:var(--panel)}.feed-panel{min-width:0}.feed-head{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:18px;border-bottom:1px solid var(--line)}.feed-head h2{margin:0;font-size:20px}.feed-head p{margin:4px 0 0;color:var(--muted);font-size:12px}.feed-tools{display:flex;align-items:center;gap:8px}.filters{display:flex;gap:5px}.filters button{padding:7px 9px;border:1px solid var(--line2);border-radius:5px;background:var(--panel2);color:var(--muted);font-size:10px;font-weight:800;white-space:nowrap}.filters button:first-child{border-color:var(--blue);color:var(--text)}.filters button:disabled{cursor:not-allowed;opacity:.7}.search{width:235px;padding:8px 10px;border:1px solid var(--line2);border-radius:5px;background:var(--panel2);color:var(--text);font-size:11px}.search:disabled{cursor:not-allowed;opacity:.7}
    .candidate-list{display:grid}.candidate-row{display:grid;grid-template-columns:minmax(180px,.8fr) minmax(330px,1.35fr) minmax(260px,1fr) minmax(135px,.55fr);min-width:0;border-bottom:1px solid var(--line)}.candidate-row:last-child{border-bottom:0}.candidate-row:hover{background:rgba(81,141,244,.025)}.token-cell,.market-cell,.evidence-cell,.action-cell{padding:17px;border-right:1px solid var(--line)}.action-cell{border-right:0}.token-cell{display:flex;gap:12px}.rank{color:var(--faint);font:700 10px ui-monospace,SFMono-Regular,Consolas,monospace}.token-cell strong,.token-cell span,.token-cell small{display:block}.token-cell strong{font-size:16px}.token-cell span{margin-top:3px;color:var(--muted);font-size:12px}.token-cell small{margin-top:5px;color:var(--faint);font-size:10px;text-transform:uppercase}.market-cell{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.market-cell span,.market-cell strong{display:block}.market-cell span{color:var(--faint);font-size:9px;text-transform:uppercase}.market-cell strong{margin-top:5px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13px}.evidence-cell{position:relative}.activity-tag{display:inline-block;margin-bottom:7px;color:var(--cyan);font-size:9px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.evidence-cell>strong{display:block;font-size:11px}.evidence-cell p{margin:4px 0 0;color:var(--muted);font-size:10px}.risk-line{display:flex;gap:7px;margin-top:9px;padding-top:8px;border-top:1px solid var(--line)}.risk-line b{color:var(--amber);font-size:9px;text-transform:uppercase}.risk-line span{color:var(--muted);font-size:9px}.action-cell{display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:6px}.action-cell code{color:var(--text);font-size:10px}.action-cell small{color:var(--faint);font-size:9px}.inspect-link{margin-top:5px;padding:7px 9px;border:1px solid var(--blue);border-radius:5px;color:#8bb9ff;font-size:10px;font-weight:850;text-decoration:none}
    .intel-rail{display:grid;align-content:start;gap:12px}.rail-card{padding:17px}.rail-card h3{margin:0;font-size:14px}.rail-card>p{margin:5px 0 0;color:var(--muted);font-size:11px}.rail-kicker{display:block;margin-bottom:7px;color:var(--cyan);font-size:9px;font-weight:900;letter-spacing:.09em;text-transform:uppercase}.rule-list{display:grid;margin-top:12px}.rule{display:flex;align-items:center;gap:8px;padding:8px 0;border-top:1px solid var(--line);font-size:11px}.rule:before{content:"✓";display:grid;place-items:center;width:17px;height:17px;border-radius:50%;background:rgba(34,200,140,.1);color:var(--green);font-size:9px}.risk-card{border-left:2px solid var(--amber)}.risk-card strong{display:block;margin-top:9px;color:var(--amber);font-size:11px}.jupiter-card{border-left:2px solid var(--purple)}.jupiter-status{display:inline-block;margin-top:11px;padding:5px 7px;border:1px solid rgba(153,69,255,.5);border-radius:999px;color:#cbb2ff;font-size:9px;font-weight:850;text-transform:uppercase}.status-detail{display:grid;margin-top:11px}.status-detail div{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid var(--line);font-size:10px}.status-detail span{color:var(--muted)}.status-detail strong{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
    .empty-state{display:grid;grid-template-columns:60px 1fr;gap:17px;align-items:center;margin:18px;padding:25px;border:1px dashed var(--line2);background:var(--panel2)}.empty-icon{display:grid;place-items:center;width:60px;height:60px;border:1px solid rgba(153,69,255,.45);border-radius:50%;color:#cbb2ff;font-size:25px}.empty-state h3{margin:0;font-size:17px}.empty-state p{max-width:680px;margin:6px 0 0;color:var(--muted);font-size:12px}.empty-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}.primary-link,.secondary-link{padding:7px 10px;border-radius:5px;font-size:10px;font-weight:850;text-decoration:none}.primary-link{border:1px solid var(--blue);color:#8bb9ff}.secondary-link{border:1px solid var(--line2);color:var(--text)}
    footer{display:flex;justify-content:space-between;gap:16px;padding:17px 2px 0;color:var(--faint);font-size:10px}
    /* Readability polish: retain terminal density without micro-sized copy. */
    .feed-head .eyebrow{font-size:11px}.feed-head h2{font-size:24px;line-height:1.15}.feed-head p{font-size:13px;line-height:1.5}
    .rank{font-size:12px}.token-cell strong{font-size:18px}.token-cell span{font-size:13px}.token-cell small{font-size:11px}
    .market-cell span{font-size:10px}.market-cell strong{font-size:15px}.activity-tag{font-size:10px}
    .evidence-cell>strong{font-size:13px}.evidence-cell p{font-size:12px;line-height:1.55}.risk-line b{font-size:10px}.risk-line span{font-size:10.5px;line-height:1.5}
    .action-cell code{font-size:11px}.action-cell small{font-size:10px}.inspect-link{font-size:11px}
    .rail-kicker{font-size:10px}.rail-card h3{font-size:16px;line-height:1.3}.rail-card>p{font-size:12px;line-height:1.55}.rail-card strong{line-height:1.4}
    .rule{font-size:12px}.status-detail div{font-size:11px}.jupiter-status{font-size:10px}
    .status-pill span{font-size:10px}.status-pill small{font-size:11px}.metric span{font-size:10px}.metric small{font-size:11px}
    html[data-theme="plain"]{color-scheme:light;--bg:#f5f7fa;--panel:#fff;--panel2:#f2f5f8;--panel3:#eaf0f5;--line:#dce3ea;--line2:#cbd5df;--text:#132033;--muted:#607086;--faint:#78889a;--blue:#2869c7;--cyan:#087f8c;--purple:#6557c7;--amber:#9a5b00;--green:#14804a;--risk:#bd3652}html[data-theme="plain"] body{background:var(--bg)}html[data-theme="plain"] .theme-option.active{background:#172033;color:#fff}html[data-theme="plain"] .candidate-row:hover{background:#f8fafc}html[data-theme="plain"] .empty-state{background:#f8fafc}
    html[data-theme="intel"]{color-scheme:dark;--bg:#090b0f;--panel:#0e1116;--panel2:#12161c;--panel3:#171c23;--line:#20262f;--line2:#2b333e;--text:#edf0f4;--muted:#8a929d;--faint:#59626e;--blue:#ff9418;--cyan:#ff9418;--purple:#c76a00;--amber:#ff9418;--green:#18c98b;--risk:#ff5470}
    html[data-theme="intel"] body{background:linear-gradient(180deg,#090b0f,#080a0d)}
    html[data-theme="intel"] .theme-switcher{background:#0b0e12;border-color:#262c34}
    html[data-theme="intel"] .theme-option.active{background:#ff9418;color:#090b0f}
    html[data-theme="intel"] .terminal-head{border-bottom:1px solid #1d2229}
    html[data-theme="intel"] .terminal-head h1{font-size:40px}
    html[data-theme="intel"] .eyebrow,html[data-theme="intel"] .activity-tag,html[data-theme="intel"] .rail-kicker{color:#ff9418}
    html[data-theme="intel"] .status-pill{background:#0d1015;border-color:#262d36;border-radius:2px}
    html[data-theme="intel"] .status-pill.live{border-left:3px solid #ff9418}
    html[data-theme="intel"] .metrics{gap:12px;margin-top:16px;border:0;background:transparent}
    html[data-theme="intel"] .metric{border:1px solid #242a32;border-left:3px solid #ff9418;background:#0f1217}
    html[data-theme="intel"] .metric:last-child{border-right:1px solid #242a32}
    html[data-theme="intel"] .metric:before{display:none}
    html[data-theme="intel"] .workspace{gap:16px;margin-top:16px}
    html[data-theme="intel"] .feed-panel,html[data-theme="intel"] .rail-card{background:#0d1015;border-color:#232a33}
    html[data-theme="intel"] .search,html[data-theme="intel"] .filters button{background:#11151b;border-color:#29313a;border-radius:2px}
    html[data-theme="intel"] .filters button:first-child{border-color:#ff9418;color:#ffb45e}
    html[data-theme="intel"] .candidate-list{gap:8px;padding:10px}
    html[data-theme="intel"] .candidate-row{border:1px solid #212832;background:#0f1318}
    html[data-theme="intel"] .candidate-row:last-child{border-bottom:1px solid #212832}
    html[data-theme="intel"] .rank{color:#ff9418}
    html[data-theme="intel"] .inspect-link{border-color:#ff9418;color:#ffad4b;border-radius:2px}
    html[data-theme="intel"] .risk-card,html[data-theme="intel"] .jupiter-card{border-left-color:#ff9418}
    /* MI v3.1 Polish â€” CSS-only refinement */
    html[data-theme="intel"] .shell{width:min(1460px,calc(100% - 56px));padding-top:18px}
    html[data-theme="intel"] .topbar{padding-bottom:18px}
    html[data-theme="intel"] .terminal-head{padding:34px 2px 28px}
    html[data-theme="intel"] .terminal-head h1{font-size:42px;line-height:1.02;letter-spacing:-.035em}
    html[data-theme="intel"] .terminal-head p{max-width:760px;font-size:14px;line-height:1.6}
    html[data-theme="intel"] .status-cluster{gap:10px}
    html[data-theme="intel"] .status-pill{min-width:152px;padding:12px 13px}
    html[data-theme="intel"] .status-pill strong{font-size:16px}
    html[data-theme="intel"] .metrics{gap:14px;margin-top:14px}
    html[data-theme="intel"] .metric{min-height:112px;padding:20px 22px}
    html[data-theme="intel"] .metric span{color:#747e8a;letter-spacing:.13em}
    html[data-theme="intel"] .metric strong{margin-top:10px;font-size:29px;line-height:1}
    html[data-theme="intel"] .metric small{margin-top:8px;color:#757f8a}
    html[data-theme="intel"] .workspace{grid-template-columns:minmax(0,1fr) 320px;gap:18px;margin-top:18px}
    html[data-theme="intel"] .feed-panel{border-color:#262d35;background:#0c0f13}
    html[data-theme="intel"] .feed-head{padding:22px 22px 18px}
    html[data-theme="intel"] .feed-head h2{font-size:25px;letter-spacing:-.015em}
    html[data-theme="intel"] .feed-head p{margin-top:6px;color:#858e99}
    html[data-theme="intel"] .feed-tools{gap:10px}
    html[data-theme="intel"] .search{height:36px}
    html[data-theme="intel"] .filters button{height:36px;padding-inline:11px}
    html[data-theme="intel"] .candidate-list{gap:10px;padding:10px}
    html[data-theme="intel"] .candidate-row{border-color:#242b33;background:#0f1216;transition:background .15s ease,border-color .15s ease,transform .15s ease}
    html[data-theme="intel"] .candidate-row:hover{background:#12161b;border-color:#343c45;transform:translateY(-1px)}
    html[data-theme="intel"] .token-cell,html[data-theme="intel"] .market-cell,html[data-theme="intel"] .evidence-cell,html[data-theme="intel"] .action-cell{padding:18px 16px}
    html[data-theme="intel"] .token-cell strong{font-size:18px;letter-spacing:-.01em}
    html[data-theme="intel"] .token-cell span{margin-top:5px;color:#8c96a2}
    html[data-theme="intel"] .token-cell small{margin-top:7px;color:#69737f}
    html[data-theme="intel"] .market-cell{gap:14px}
    html[data-theme="intel"] .market-cell span{color:#606a76;letter-spacing:.11em}
    html[data-theme="intel"] .market-cell strong{margin-top:7px;font-size:15px}
    html[data-theme="intel"] .activity-tag{margin-bottom:8px;letter-spacing:.1em}
    html[data-theme="intel"] .evidence-cell>strong{font-size:13px}
    html[data-theme="intel"] .evidence-cell p{margin-top:6px;color:#8a949f;line-height:1.6}
    html[data-theme="intel"] .risk-line{margin-top:11px;padding-top:10px;border-top-color:#252c34}
    html[data-theme="intel"] .risk-line span{color:#737d88}
    html[data-theme="intel"] .action-cell{gap:8px}
    html[data-theme="intel"] .action-cell code{color:#d6dbe1}
    html[data-theme="intel"] .action-cell small{color:#68727d}
    html[data-theme="intel"] .inspect-link{padding:8px 10px;background:rgba(255,148,24,.025);font-size:11px}
    html[data-theme="intel"] .inspect-link:hover{background:rgba(255,148,24,.07)}
    html[data-theme="intel"] .intel-rail{gap:14px}
    html[data-theme="intel"] .rail-card{padding:19px 18px;background:#0e1115;border-color:#252c34}
    html[data-theme="intel"] .rail-card h3{font-size:16px;letter-spacing:-.01em}
    html[data-theme="intel"] .rail-card>p{color:#858f9a;line-height:1.6}
    html[data-theme="intel"] .status-detail{margin-top:13px}
    html[data-theme="intel"] .status-detail div{padding:8px 0;border-top-color:#262d35}
    html[data-theme="intel"] .rule{padding:9px 0;border-top-color:#262d35}
    html[data-theme="intel"] .rule:before{background:rgba(24,201,139,.08)}
    html[data-theme="intel"] .risk-card strong{margin-top:11px}
    html[data-theme="intel"] footer{padding-top:20px;color:#5e6873}
    /* MI v3.2 Feed â€” compact decision scanner */
    .candidate-row-v32{display:grid;grid-template-columns:minmax(210px,1.35fr) minmax(105px,.72fr) minmax(105px,.72fr) minmax(110px,.78fr) minmax(70px,.48fr) minmax(230px,1.45fr) minmax(130px,.82fr);align-items:stretch}
    .candidate-row-v32>.token-cell,.candidate-row-v32>.feed-value,.candidate-row-v32>.why-now,.candidate-row-v32>.feed-action{padding:15px 14px;border-right:1px solid var(--line)}
    .candidate-row-v32>.feed-action{border-right:0}
    .compact-token{display:flex;gap:10px;align-items:flex-start}
    .compact-token strong,.compact-token span,.compact-token small{display:block}
    .compact-token strong{font-size:15px}
    .compact-token span{margin-top:3px;color:var(--muted);font-size:11px}
    .compact-token small{margin-top:4px;color:var(--faint);font-size:9px;text-transform:uppercase}
    .feed-value{display:flex;flex-direction:column;justify-content:center}
    .feed-value span,.why-now span{font-family:var(--font-mono);color:var(--faint);font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
    .feed-value strong{margin-top:5px;font-family:var(--font-mono);font-size:13px}
    .why-now{display:flex;flex-direction:column;justify-content:center}
    .why-now strong{margin-top:5px;font-size:11px;line-height:1.45;color:var(--text)}
    .feed-action{display:flex;align-items:center;justify-content:flex-end}
    .feed-action .inspect-link{margin-top:0;white-space:nowrap}
    html[data-theme="intel"] .candidate-list{gap:6px;padding:8px}
    html[data-theme="intel"] .candidate-row-v32{min-height:74px;background:#0f1216;border:1px solid #242b33}
    html[data-theme="intel"] .candidate-row-v32:hover{background:#12161b;border-color:#343c45;transform:translateY(-1px)}
    html[data-theme="intel"] .candidate-row-v32>.token-cell,
    html[data-theme="intel"] .candidate-row-v32>.feed-value,
    html[data-theme="intel"] .candidate-row-v32>.why-now{border-right-color:#242b33}
    html[data-theme="intel"] .compact-token .rank{color:#ff9418}
    html[data-theme="intel"] .why-now strong{color:#d9dee4}
    html[data-theme="intel"] .feed-action .inspect-link{border-color:#ff9418;color:#ffad4b;background:rgba(255,148,24,.025)}
    /* MI v3.3 Reference Polish */
    html[data-theme="intel"] .shell{width:min(1480px,calc(100% - 48px));padding-top:16px}
    html[data-theme="intel"] .topbar{padding-bottom:16px}
    html[data-theme="intel"] .terminal-head{padding:30px 2px 24px}
    html[data-theme="intel"] .terminal-head h1{font-size:40px;line-height:1.03;letter-spacing:-.035em}
    html[data-theme="intel"] .terminal-head p{max-width:760px;font-size:13px;line-height:1.55}
    html[data-theme="intel"] .status-pill{min-width:150px;padding:11px 12px}
    html[data-theme="intel"] .metrics{gap:12px;margin-top:12px}
    html[data-theme="intel"] .metric{min-height:100px;padding:18px 20px;background:#0f1318}
    html[data-theme="intel"] .metric strong{font-size:27px}
    html[data-theme="intel"] .metric small{margin-top:6px}
    html[data-theme="intel"] .workspace{grid-template-columns:minmax(0,1fr) 320px;gap:16px;margin-top:16px}
    html[data-theme="intel"] .feed-panel{background:#0c1014;border-color:#252c34}
    html[data-theme="intel"] .feed-head{padding:18px 18px 14px}
    html[data-theme="intel"] .feed-head h2{font-size:23px}
    html[data-theme="intel"] .feed-head p{font-size:12px}
    html[data-theme="intel"] .search{height:34px}
    html[data-theme="intel"] .filters button{height:34px;padding:6px 10px}
    .feed-columns-v33{display:grid;grid-template-columns:minmax(210px,1.35fr) minmax(105px,.72fr) minmax(105px,.72fr) minmax(110px,.78fr) minmax(70px,.48fr) minmax(230px,1.45fr) minmax(130px,.82fr);align-items:center;padding:0 8px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--panel2)}
    .feed-columns-v33 span{padding:9px 14px;font-family:var(--font-mono);font-size:9px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--faint)}
    html[data-theme="intel"] .feed-columns-v33{background:#101419;border-color:#252c34}
    html[data-theme="intel"] .candidate-list{gap:4px;padding:6px}
    html[data-theme="intel"] .candidate-row-v32{min-height:64px;background:#0f1318;border-color:#232a32}
    html[data-theme="intel"] .candidate-row-v32:hover{background:#12171d;border-color:#343c45;transform:none}
    .candidate-row-v32>.token-cell,.candidate-row-v32>.feed-value,.candidate-row-v32>.why-now,.candidate-row-v32>.feed-action{padding:11px 12px}
    .compact-token{gap:9px}
    .compact-token strong{font-size:14px;line-height:1.25}
    .compact-token span{margin-top:2px;font-size:10px}
    .compact-token small{margin-top:3px;font-size:8.5px}
    .feed-value span,.why-now span{font-size:8.5px;letter-spacing:.08em}
    .feed-value strong{margin-top:4px;font-size:12.5px}
    .why-now strong{margin-top:4px;font-size:10.5px;line-height:1.35}
    html[data-theme="intel"] .why-now strong{color:#e0e4e9}
    html[data-theme="intel"] .feed-action .inspect-link{padding:7px 10px;font-size:10.5px;font-weight:850;border-radius:2px;background:transparent}
    html[data-theme="intel"] .feed-action .inspect-link:hover{background:rgba(255,148,24,.08)}
    html[data-theme="intel"] .intel-rail{gap:12px}
    html[data-theme="intel"] .rail-card{padding:16px 15px}
    html[data-theme="intel"] .rail-card h3{font-size:15px}
    html[data-theme="intel"] .rail-card>p{font-size:11px;line-height:1.5}
    html[data-theme="intel"] .status-detail div{padding:7px 0}
    html[data-theme="intel"] .rule{padding:7px 0;font-size:11px}
    /* MI v3.4 Feed Typography + KPI icons */
    html[data-theme="intel"] .feed-panel,
    html[data-theme="intel"] .feed-panel button,
    html[data-theme="intel"] .feed-panel input{
      font-family:Inter,"Segoe UI Variable Text","Segoe UI Variable","Segoe UI",Arial,sans-serif;
    }
    html[data-theme="intel"] .feed-head h2,
    html[data-theme="intel"] .compact-token strong,
    html[data-theme="intel"] .why-now strong{
      font-family:Inter,"Segoe UI Variable Display","Segoe UI",Arial,sans-serif;
      font-stretch:normal;
    }
    html[data-theme="intel"] .feed-columns-v33 span,
    html[data-theme="intel"] .feed-value span,
    html[data-theme="intel"] .why-now>span{
      font-family:"Cascadia Mono","Cascadia Code",Consolas,monospace;
      letter-spacing:.07em;
    }
    html[data-theme="intel"] .feed-value strong{
      font-family:"Cascadia Mono","Cascadia Code",Consolas,monospace;
      font-weight:700;
    }
    html[data-theme="intel"] .compact-token strong{font-weight:700;letter-spacing:-.012em}
    html[data-theme="intel"] .compact-token span{font-weight:400}
    html[data-theme="intel"] .why-now strong{display:flex;align-items:center;gap:7px;font-weight:600}
    html[data-theme="intel"] .why-dot{
      display:inline-block;flex:0 0 auto;width:7px;height:7px;border-radius:50%;
      background:#22d27f;box-shadow:0 0 0 3px rgba(34,210,127,.08),0 0 8px rgba(34,210,127,.3);
    }
    html[data-theme="intel"] .candidate-row-v32{min-height:60px}
    html[data-theme="intel"] .candidate-row-v32>.token-cell,
    html[data-theme="intel"] .candidate-row-v32>.feed-value,
    html[data-theme="intel"] .candidate-row-v32>.why-now,
    html[data-theme="intel"] .candidate-row-v32>.feed-action{padding-top:9px;padding-bottom:9px}
    html[data-theme="intel"] .metrics .metric{position:relative;padding-right:58px}
    html[data-theme="intel"] .metric-icon{
      position:absolute;right:18px;bottom:16px;width:26px;height:26px;color:#7f8995;opacity:.8;
    }
    html[data-theme="intel"] .metric-icon svg{
      display:block;width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:1.35;stroke-linecap:round;stroke-linejoin:round;
    }
    html[data-theme="intel"] .metric-network .sol-icon{width:30px;height:24px;color:#8d98a5}
    html[data-theme="intel"] .metric-network .sol-icon svg{fill:currentColor;stroke:none}
    html[data-theme="intel"] .metric:hover .metric-icon{color:#ff9418;opacity:1}
    @media(max-width:820px){
      html[data-theme="intel"] .metrics .metric{padding-right:46px}
      html[data-theme="intel"] .metric-icon{right:12px;bottom:12px;width:22px;height:22px}
    }
    /* MI v3.5 Compact Type â€” reduce expanded/kembang appearance */
    html[data-theme="intel"] .compact-token strong{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:13px;
      font-weight:650;
      letter-spacing:-.02em;
      line-height:1.18;
      font-stretch:normal;
    }
    html[data-theme="intel"] .compact-token span{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:9.5px;
      letter-spacing:-.005em;
      line-height:1.25;
    }
    html[data-theme="intel"] .compact-token small{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:8px;
      letter-spacing:.015em;
      line-height:1.2;
    }
    html[data-theme="intel"] .feed-value strong{
      font-family:"Cascadia Mono","Consolas","Courier New",monospace;
      font-size:11.5px;
      font-weight:600;
      letter-spacing:-.035em;
      line-height:1.15;
      font-variant-numeric:tabular-nums;
    }
    html[data-theme="intel"] .feed-value span,
    html[data-theme="intel"] .feed-columns-v33 span,
    html[data-theme="intel"] .why-now>span{
      font-family:"Cascadia Mono","Consolas","Courier New",monospace;
      font-size:8px;
      font-weight:600;
      letter-spacing:.04em;
    }
    html[data-theme="intel"] .why-now strong{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:10px;
      font-weight:600;
      letter-spacing:-.01em;
      line-height:1.25;
    }
    html[data-theme="intel"] .rank{
      font-family:"Cascadia Mono","Consolas","Courier New",monospace;
      font-size:9px;
      font-weight:600;
      letter-spacing:-.02em;
    }
    html[data-theme="intel"] .candidate-row-v32{
      min-height:56px;
    }
    html[data-theme="intel"] .candidate-row-v32>.token-cell,
    html[data-theme="intel"] .candidate-row-v32>.feed-value,
    html[data-theme="intel"] .candidate-row-v32>.why-now,
    html[data-theme="intel"] .candidate-row-v32>.feed-action{
      padding-top:8px;
      padding-bottom:8px;
    }
    html[data-theme="intel"] .feed-action .inspect-link{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:10px;
      font-weight:700;
      letter-spacing:-.01em;
    }
    /* MI v3.6.1 Feed Layout Fix - UI only */
    html[data-theme="intel"] .candidate-row-v32{
      display:grid;
      grid-template-columns:
        minmax(190px,1.45fr)
        minmax(96px,.72fr)
        minmax(96px,.72fr)
        minmax(104px,.78fr)
        minmax(62px,.45fr)
        minmax(220px,1.55fr)
        minmax(118px,.82fr);
      align-items:center;
      min-height:58px;
    }
    html[data-theme="intel"] .candidate-row-v32>.token-cell,
    html[data-theme="intel"] .candidate-row-v32>.feed-value,
    html[data-theme="intel"] .candidate-row-v32>.why-now,
    html[data-theme="intel"] .candidate-row-v32>.feed-action{
      min-width:0;
      height:100%;
      padding:9px 10px;
      border-right:1px solid #232a32;
      border-bottom:0;
      display:flex;
      justify-content:center;
    }
    html[data-theme="intel"] .candidate-row-v32>.feed-action{
      border-right:0;
      align-items:center;
      justify-content:flex-end;
    }
    html[data-theme="intel"] .candidate-row-v32>.token-cell{
      align-items:flex-start;
      justify-content:flex-start;
    }
    html[data-theme="intel"] .compact-token>div{
      min-width:0;
    }
    html[data-theme="intel"] .compact-token strong,
    html[data-theme="intel"] .compact-token span,
    html[data-theme="intel"] .compact-token small{
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    html[data-theme="intel"] .feed-value{
      flex-direction:column;
      align-items:flex-start;
    }
    html[data-theme="intel"] .why-now{
      flex-direction:column;
      align-items:flex-start;
    }
    html[data-theme="intel"] .why-now strong{
      max-width:100%;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    html[data-theme="intel"] .feed-action .inspect-link{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:30px;
      padding:6px 9px;
      white-space:nowrap;
    }

    html[data-theme="intel"] .feed-columns-v33{
      display:grid;
      grid-template-columns:
        minmax(190px,1.45fr)
        minmax(96px,.72fr)
        minmax(96px,.72fr)
        minmax(104px,.78fr)
        minmax(62px,.45fr)
        minmax(220px,1.55fr)
        minmax(118px,.82fr);
      padding:0 6px;
    }
    html[data-theme="intel"] .feed-columns-v33 span{
      padding:8px 10px;
      min-width:0;
    }

    html[data-theme="intel"] .candidate-list{
      gap:4px;
      padding:6px;
    }

    /* MI v3.6.2 Feed Breakpoint Hotfix - UI only */
    @media(min-width:761px){
      html[data-theme="intel"] .feed-columns-v33{
        display:grid !important;
        grid-template-columns:
          minmax(190px,1.45fr)
          minmax(96px,.72fr)
          minmax(96px,.72fr)
          minmax(104px,.78fr)
          minmax(62px,.45fr)
          minmax(220px,1.55fr)
          minmax(118px,.82fr) !important;
      }

      html[data-theme="intel"] .candidate-row-v32{
        display:grid !important;
        grid-template-columns:
          minmax(190px,1.45fr)
          minmax(96px,.72fr)
          minmax(96px,.72fr)
          minmax(104px,.78fr)
          minmax(62px,.45fr)
          minmax(220px,1.55fr)
          minmax(118px,.82fr) !important;
        align-items:center !important;
        min-height:58px !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.token-cell,
      html[data-theme="intel"] .candidate-row-v32>.feed-value,
      html[data-theme="intel"] .candidate-row-v32>.why-now,
      html[data-theme="intel"] .candidate-row-v32>.feed-action{
        grid-column:auto !important;
        width:auto !important;
        min-width:0 !important;
        height:100% !important;
        padding:9px 10px !important;
        border-bottom:0 !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.token-cell,
      html[data-theme="intel"] .candidate-row-v32>.feed-value,
      html[data-theme="intel"] .candidate-row-v32>.why-now{
        border-right:1px solid #232a32 !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.feed-action{
        border-top:0 !important;
        border-right:0 !important;
        justify-content:flex-end !important;
      }

      html[data-theme="intel"] .feed-action .inspect-link{
        width:auto !important;
        min-width:0 !important;
      }
    }

    @media(max-width:760px){
      html[data-theme="intel"] .feed-columns-v33{display:none !important}

      html[data-theme="intel"] .candidate-row-v32{
        grid-template-columns:1fr 1fr !important;
        min-height:auto !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.token-cell{
        grid-column:1/-1 !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.why-now{
        grid-column:1/-1 !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.feed-action{
        grid-column:1/-1 !important;
        justify-content:stretch !important;
        border-top:1px solid #232a32 !important;
      }

      html[data-theme="intel"] .candidate-row-v32>.token-cell,
      html[data-theme="intel"] .candidate-row-v32>.feed-value,
      html[data-theme="intel"] .candidate-row-v32>.why-now{
        border-right:0 !important;
        border-bottom:1px solid #232a32 !important;
      }

      html[data-theme="intel"] .feed-action .inspect-link{
        width:100% !important;
      }
    }
    /* MI v3.7 Typography Comfort Pass - UI only */
    html[data-theme="intel"]{
      --bg:#0b0f14;
      --panel:#0f141a;
      --panel2:#121820;
      --panel3:#151c24;
      --line:#28313b;
      --line2:#333d48;
      --text:#e6e9ed;
      --muted:#a0a8b3;
      --faint:#737d88;
    }

    html[data-theme="intel"] body{
      background:#0b0f14;
      color:var(--text);
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:15px;
      line-height:1.58;
      -webkit-font-smoothing:antialiased;
      text-rendering:optimizeLegibility;
    }

    html[data-theme="intel"] .terminal-head h1,
    html[data-theme="intel"] .feed-head h2,
    html[data-theme="intel"] .rail-card h3,
    html[data-theme="intel"] .status-pill strong,
    html[data-theme="intel"] .metric strong{
      font-family:"Segoe UI Variable Display","Segoe UI",Arial,sans-serif;
      font-weight:600;
      letter-spacing:-.018em;
    }

    html[data-theme="intel"] .terminal-head h1{
      font-size:39px;
      line-height:1.08;
    }

    html[data-theme="intel"] .terminal-head p,
    html[data-theme="intel"] .feed-head p,
    html[data-theme="intel"] .rail-card>p,
    html[data-theme="intel"] footer{
      color:#a6aeb8;
      font-weight:400;
      letter-spacing:0;
    }

    html[data-theme="intel"] .eyebrow,
    html[data-theme="intel"] .rail-kicker,
    html[data-theme="intel"] .feed-columns-v33 span,
    html[data-theme="intel"] .feed-value span,
    html[data-theme="intel"] .why-now>span,
    html[data-theme="intel"] .metric>span:first-child,
    html[data-theme="intel"] .status-pill span{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-weight:600;
      letter-spacing:.045em;
      text-transform:uppercase;
    }

    html[data-theme="intel"] .compact-token strong{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:13.5px;
      font-weight:600;
      letter-spacing:-.01em;
      line-height:1.25;
    }

    html[data-theme="intel"] .compact-token span{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:10px;
      font-weight:400;
      letter-spacing:0;
      line-height:1.35;
      color:#a1a9b3;
    }

    html[data-theme="intel"] .compact-token small{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:8.5px;
      font-weight:500;
      letter-spacing:.02em;
      line-height:1.3;
      color:#7d8792;
    }

    html[data-theme="intel"] .feed-value strong{
      font-family:"Cascadia Mono","Consolas","Courier New",monospace;
      font-size:11.5px;
      font-weight:500;
      letter-spacing:-.015em;
      line-height:1.2;
      color:#f0f2f4;
      font-variant-numeric:tabular-nums;
    }

    html[data-theme="intel"] .feed-value span,
    html[data-theme="intel"] .feed-columns-v33 span,
    html[data-theme="intel"] .why-now>span{
      font-size:8.5px;
      font-weight:600;
      color:#7f8994;
    }

    html[data-theme="intel"] .why-now strong{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:10.5px;
      font-weight:500;
      letter-spacing:0;
      line-height:1.35;
      color:#dce1e6;
    }

    html[data-theme="intel"] .rank{
      font-family:"Cascadia Mono","Consolas","Courier New",monospace;
      font-size:9px;
      font-weight:600;
      letter-spacing:0;
    }

    html[data-theme="intel"] .inspect-link,
    html[data-theme="intel"] .filters button,
    html[data-theme="intel"] .search{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-weight:500;
      letter-spacing:0;
    }

    html[data-theme="intel"] .inspect-link{
      font-size:10px;
    }

    html[data-theme="intel"] .metric{
      background:#11161c;
    }

    html[data-theme="intel"] .metric strong{
      color:#f0f2f4;
      font-size:26px;
      font-weight:600;
    }

    html[data-theme="intel"] .metric small{
      color:#8e98a3;
      font-size:10px;
      line-height:1.4;
    }

    html[data-theme="intel"] .status-pill,
    html[data-theme="intel"] .feed-panel,
    html[data-theme="intel"] .rail-card,
    html[data-theme="intel"] .candidate-row-v32{
      background:#0f141a;
    }

    html[data-theme="intel"] .candidate-row-v32{
      border-color:#2a323c;
    }

    html[data-theme="intel"] .feed-columns-v33{
      background:#11171d;
      border-color:#2a323c;
    }

    html[data-theme="intel"] .rule,
    html[data-theme="intel"] .status-detail div{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-size:11px;
      font-weight:400;
      line-height:1.45;
    }

    html[data-theme="intel"] .rail-card h3{
      font-size:15px;
      font-weight:600;
    }

    html[data-theme="intel"] .risk-card strong{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-weight:600;
    }

    @media(max-width:760px){
      html[data-theme="intel"] body{
        font-size:14px;
      }
      html[data-theme="intel"] .terminal-head h1{
        font-size:31px;
      }
    }
    /* MI v3.7.1 Clean Numbers - UI only */
    html[data-theme="intel"] .feed-value strong,
    html[data-theme="intel"] .rank{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-variant-numeric:tabular-nums lining-nums;
      font-feature-settings:"tnum" 1,"lnum" 1;
      font-weight:600;
      letter-spacing:-.012em;
    }

    html[data-theme="intel"] .feed-value strong{
      font-size:11.5px;
      line-height:1.25;
    }

    html[data-theme="intel"] .rank{
      font-size:9px;
      line-height:1.2;
    }

    html[data-theme="intel"] .status-detail strong,
    html[data-theme="intel"] .status-pill strong{
      font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
      font-variant-numeric:tabular-nums lining-nums;
      font-feature-settings:"tnum" 1,"lnum" 1;
      letter-spacing:-.01em;
    }
    @media(max-width:1180px){
      html[data-theme="intel"] .feed-columns-v33{display:none}
      html[data-theme="intel"] .candidate-row-v32{
        grid-template-columns:1fr 1fr;
        min-height:auto;
      }
      html[data-theme="intel"] .candidate-row-v32>.token-cell{
        grid-column:1/-1;
      }
      html[data-theme="intel"] .candidate-row-v32>.why-now{
        grid-column:1/-1;
      }
      html[data-theme="intel"] .candidate-row-v32>.feed-action{
        grid-column:1/-1;
        justify-content:stretch;
        border-top:1px solid #232a32;
      }
      html[data-theme="intel"] .candidate-row-v32>.token-cell,
      html[data-theme="intel"] .candidate-row-v32>.feed-value,
      html[data-theme="intel"] .candidate-row-v32>.why-now{
        border-right:0;
        border-bottom:1px solid #232a32;
      }
      html[data-theme="intel"] .feed-action .inspect-link{
        width:100%;
      }
    }
    @media(max-width:1180px){
      .feed-columns-v33{display:none}
    }
    @media(max-width:820px){
      html[data-theme="intel"] .shell{width:min(100% - 20px,1480px)}
      html[data-theme="intel"] .candidate-row-v32{min-height:auto}
    }
    @media(max-width:1180px){
      .candidate-row-v32{grid-template-columns:minmax(190px,1.2fr) repeat(4,minmax(90px,.7fr)) minmax(210px,1.35fr)}
      .candidate-row-v32>.feed-action{grid-column:1/-1;justify-content:flex-end;border-top:1px solid var(--line);padding:9px 14px}
    }
    @media(max-width:820px){
      .candidate-row-v32{grid-template-columns:1fr 1fr}
      .candidate-row-v32>.token-cell{grid-column:1/-1}
      .candidate-row-v32>.why-now{grid-column:1/-1}
      .candidate-row-v32>.feed-action{grid-column:1/-1;justify-content:stretch}
      .candidate-row-v32>.feed-action .inspect-link{width:100%;text-align:center}
      .candidate-row-v32>.token-cell,.candidate-row-v32>.feed-value,.candidate-row-v32>.why-now{border-right:0;border-bottom:1px solid var(--line)}
    }
    @media(max-width:1180px){
      html[data-theme="intel"] .workspace{grid-template-columns:1fr}
      html[data-theme="intel"] .intel-rail{grid-template-columns:repeat(3,1fr)}
    }
    @media(max-width:820px){
      html[data-theme="intel"] .shell{width:min(100% - 22px,1460px)}
      html[data-theme="intel"] .terminal-head h1{font-size:31px}
      html[data-theme="intel"] .metrics{gap:8px}
      html[data-theme="intel"] .metric{min-height:auto;padding:16px}
      html[data-theme="intel"] .metric strong{font-size:23px}
      html[data-theme="intel"] .intel-rail{grid-template-columns:1fr}
    }
    @media(max-width:1180px){.workspace{grid-template-columns:1fr}.intel-rail{grid-template-columns:repeat(3,1fr)}.candidate-row{grid-template-columns:minmax(170px,.8fr) minmax(310px,1.25fr) minmax(240px,1fr)}.action-cell{grid-column:1/-1;flex-direction:row;align-items:center;justify-content:flex-end;border-top:1px solid var(--line);border-right:0;padding:10px 17px}.feed-tools{align-items:flex-end;flex-direction:column}}
    @media(max-width:820px){.shell{width:min(100% - 22px,1420px);padding-top:11px}.topbar{align-items:flex-start}.terminal-name span{display:none}.terminal-head{grid-template-columns:1fr;align-items:start;padding-top:22px}.terminal-head h1{font-size:29px}.status-cluster{width:100%}.status-pill{flex:1;min-width:0}.metrics{grid-template-columns:repeat(2,1fr)}.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}.workspace{display:block}.intel-rail{grid-template-columns:1fr;margin-top:12px}.feed-head{align-items:flex-start;flex-direction:column}.feed-tools{width:100%;align-items:stretch}.filters{overflow-x:auto;scrollbar-width:none}.search{width:100%}.candidate-row{grid-template-columns:1fr}.token-cell,.market-cell,.evidence-cell,.action-cell{border-right:0;border-bottom:1px solid var(--line)}.market-cell{grid-template-columns:repeat(2,1fr)}.market-cell>div{padding:5px 0}.action-cell{grid-column:auto;justify-content:flex-start;border-top:0;border-bottom:0}.empty-state{grid-template-columns:1fr}footer{flex-direction:column}}
        /* DISCOVERY-SEGMENTS-V1 — product-level navigation foundation */
    .discovery-segments-v1{
      display:flex;
      align-items:stretch;
      gap:24px;
      min-width:0;
      padding:0 18px;
      overflow-x:auto;
      border-bottom:1px solid var(--line);
      background:var(--panel);
      scrollbar-width:none;
    }
    .discovery-segments-v1::-webkit-scrollbar{display:none}
    .discovery-segment-v1{
      position:relative;
      display:flex;
      align-items:center;
      gap:8px;
      min-height:44px;
      padding:0;
      color:var(--muted);
      font-size:11px;
      font-weight:850;
      letter-spacing:.02em;
      text-decoration:none;
      white-space:nowrap;
    }
    .discovery-segment-v1 small{
      padding:3px 5px;
      border:1px solid var(--line2);
      color:var(--faint);
      font:8px var(--font-mono);
      letter-spacing:.06em;
      text-transform:uppercase;
    }
    .discovery-segment-v1.active{color:var(--text)}
    .discovery-segment-v1.active:after{
      content:"";
      position:absolute;
      right:0;
      bottom:-1px;
      left:0;
      height:2px;
      background:var(--cyan);
      box-shadow:0 0 9px rgba(76,244,214,.28);
    }
    .discovery-segment-v1.active small{
      border-color:rgba(76,244,214,.42);
      color:var(--cyan);
    }
    .discovery-segment-v1.upcoming{
      cursor:not-allowed;
      opacity:.62;
      user-select:none;
    }
    @media(max-width:480px){
      .discovery-segments-v1{gap:18px;padding-inline:15px}
      .discovery-segment-v1{min-height:42px;font-size:10px}
    }
.feed-tabs{display:flex;gap:6px;padding:12px 18px;border-bottom:1px solid var(--line);overflow:auto}.feed-tab{display:flex;align-items:center;gap:8px;padding:8px 11px;border:1px solid var(--line2);border-radius:5px;color:var(--muted);text-decoration:none;font-size:11px;font-weight:800;white-space:nowrap}.feed-tab b{color:var(--text);font-family:var(--font-mono)}.feed-tab.active{border-color:var(--blue);color:var(--text);background:var(--panel2)}.page-summary{color:var(--muted);font:11px var(--font-mono)}.pagination{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-top:1px solid var(--line)}.pagination a,.pagination span{min-width:86px;color:var(--blue);font-size:11px;text-decoration:none}.pagination span{color:var(--faint)}.pagination strong{font:11px var(--font-mono)}.network-mark{display:flex;align-items:center;gap:10px;margin-top:14px;padding:12px;border:1px solid var(--line)}.network-mark svg{width:30px;fill:var(--purple)}.network-mark strong,.network-mark small{display:block}.network-mark small{color:var(--muted)}.dex-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.dex-badges span{padding:5px 7px;border:1px solid var(--line2);border-radius:999px;color:var(--text);font:10px var(--font-mono)}.dex-badges em{color:var(--muted);font-size:11px}.coming-soon{margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}.coming-soon span{display:block;color:var(--amber);font:9px var(--font-mono);text-transform:uppercase}.coming-soon strong{display:block;margin-top:3px}.feed-value small{display:block;margin-top:4px;font:10px var(--font-mono)}.feed-value small.up{color:var(--green)}.feed-value small.down{color:var(--risk)}
    @media(max-width:480px){.shell{width:calc(100% - 16px)}.brand img{width:112px}.terminal-name strong{font-size:11px}.top-actions{margin-left:auto}.back-link{padding:7px 8px;font-size:10px}.theme-option{width:29px;height:29px}.terminal-head h1{font-size:25px}.terminal-head p{font-size:13px}.status-cluster{display:grid;grid-template-columns:1fr 1fr}.status-pill{padding:9px}.metric{padding:13px}.metric strong{font-size:19px}.feed-head{padding:15px}.filters button{font-size:9px}.token-cell,.market-cell,.evidence-cell,.action-cell{padding:14px}.market-cell{gap:7px}.candidate-row{border-left:2px solid var(--purple)}.action-cell{align-items:stretch;flex-direction:column}.inspect-link{text-align:center}.rail-card{padding:15px}.empty-state{margin:12px;padding:18px}.empty-actions{display:grid}.primary-link,.secondary-link{text-align:center}}
    .terminal-search{display:flex;align-items:center;gap:7px}.terminal-search input{width:290px;padding:9px 11px;border:1px solid var(--line2);border-radius:5px;background:var(--panel2);color:var(--text);font-size:11px}.terminal-search button,.clear-search{padding:9px 11px;border:1px solid var(--blue);border-radius:5px;background:transparent;color:var(--blue);font-size:10px;font-weight:850;text-decoration:none;cursor:pointer}.sort-note{display:flex;justify-content:space-between;gap:12px;padding:9px 18px;border-bottom:1px solid var(--line);color:var(--muted);font:10px var(--font-mono)}

    /* SOLANA-UI-01 — DEX Intelligence re-skin / shell migration */
    :root,
    html[data-theme="plain"],
    html[data-theme="intel"]{
      color-scheme:dark;
      --bg:#080B10;
      --panel:#0E141C;
      --panel2:#10171F;
      --panel3:#10171F;
      --line:#1D2733;
      --line2:#2A3847;
      --text:#E7EDF4;
      --muted:#7C8CA0;
      --faint:#45505F;
      --blue:#4CF4D6;
      --cyan:#4CF4D6;
      --purple:#B98CFF;
      --amber:#B98CFF;
      --green:#4CF4D6;
      --risk:#FF5C7A;
      --font-display:"Space Grotesk",sans-serif;
      --font-ui:"JetBrains Mono",monospace;
      --font-mono:"JetBrains Mono",monospace;
    }
    body,
    html[data-theme="plain"] body,
    html[data-theme="intel"] body{
      margin:0;
      background-color:var(--bg);
      background-image:
        linear-gradient(rgba(76,244,214,.035) 1px,transparent 1px),
        linear-gradient(90deg,rgba(76,244,214,.035) 1px,transparent 1px);
      background-size:42px 42px;
      color:var(--text);
      font-family:"JetBrains Mono",monospace;
    }
    /* DISCOVERY-LIVE-01A — Compact Sidebar aligned to Token Workspace */
    .dex-app-shell{display:grid;grid-template-columns:76px minmax(0,1fr);min-height:100vh}
    .dex-side-rail{
      position:sticky;top:0;height:100vh;z-index:40;
      display:flex;flex-direction:column;align-items:center;gap:0;
      width:76px;padding:12px 10px;border-right:1px solid var(--line);
      background:#0E141C;font-family:"Space Grotesk",sans-serif
    }
    .dex-rail-logo{
      width:100%;min-height:52px;display:grid;place-items:center;
      padding:0 0 12px;margin:0
    }
    .dex-rail-logo img{width:34px;height:34px;object-fit:contain}
    .dex-market-nav,.dex-main-nav{
      width:100%;display:grid;gap:10px;margin:0;justify-items:center
    }
    .dex-market-nav{margin-top:18px}
    .dex-main-nav{margin-top:10px}
    .dex-side-item.dex-side-icon{
      position:relative;display:grid;place-items:center;
      width:42px;height:42px;min-height:42px;padding:0;
      border:0;border-radius:8px;background:transparent;
      color:#45505F;text-decoration:none;cursor:pointer
    }
    .dex-side-item.dex-side-icon:hover{
      color:#7C8CA0;background:rgba(76,244,214,.035)
    }
    .dex-side-item.dex-side-icon.active{
      color:#4CF4D6;background:rgba(76,244,214,.055);box-shadow:none
    }
    .dex-side-item.dex-side-icon.active:before{display:none}
    .dex-side-item.dex-side-icon svg{
      width:22px;height:22px;fill:none;stroke:currentColor;
      stroke-width:1.55;stroke-linecap:round;stroke-linejoin:round
    }
    .dex-side-item.dex-side-icon .dex-solana-icon{fill:currentColor;stroke:none}
    .dex-rail-spacer{flex:1}
    .dex-utility-nav{
      width:100%;display:flex;flex-direction:column;align-items:center;
      gap:7px;padding:8px 0 2px
    }
    .dex-utility-nav .dex-side-item{
      width:56px;min-height:26px;display:flex;align-items:center;justify-content:center;
      padding:0;color:var(--faint);font-size:9px;font-weight:500;
      line-height:1.15;text-align:center;text-decoration:none;border:0;background:transparent
    }
    .dex-utility-nav .dex-side-item:hover{color:var(--muted)}
    .dex-app-main{min-width:0}
    .dex-topbar{
      position:fixed;top:0;left:76px;right:0;height:64px;z-index:35;
      display:flex;align-items:center;gap:24px;padding:0 28px;
      border-bottom:1px solid var(--line);
      background:rgba(8,11,16,.86);backdrop-filter:blur(8px)
    }
    .dex-brand{display:flex;align-items:baseline;gap:8px;white-space:nowrap}
    .dex-brand strong{font:700 19px "Space Grotesk",sans-serif;letter-spacing:.01em}
    .dex-brand span{color:var(--faint);font:500 10px "JetBrains Mono",monospace;letter-spacing:.08em}
    .dex-header-search{
      flex:1;max-width:420px;height:36px;display:flex;align-items:center;gap:8px;
      padding:0 12px;border:1px solid var(--line);background:var(--panel2);color:var(--muted)
    }
    .dex-header-search svg{width:14px;height:14px;flex:0 0 auto}
    .dex-header-search input{
      width:100%;border:0;outline:0;background:transparent;color:var(--muted);
      font:500 12.5px "JetBrains Mono",monospace
    }
    .dex-header-search input::placeholder{color:var(--faint)}
    .dex-header-search kbd{
      margin-left:auto;padding:2px 5px;border:1px solid var(--line2);
      color:var(--faint);font:500 10px "JetBrains Mono",monospace
    }
    .dex-top-actions{margin-left:auto;display:flex;align-items:center;gap:14px}
    .dex-gas-pill{
      height:32px;display:flex;align-items:center;gap:7px;padding:0 10px;
      border:1px solid var(--line);color:var(--muted);
      font:500 11px "JetBrains Mono",monospace;white-space:nowrap
    }
    .dex-gas-dot{width:6px;height:6px;background:var(--cyan);box-shadow:0 0 6px var(--cyan)}
    .dex-gas-dot.is-offline{background:var(--risk);box-shadow:0 0 6px var(--risk)}
    .dex-connect-wallet{
      height:36px;padding:0 16px;border:0;background:var(--cyan);color:#06110F;
      font:600 12.5px "Space Grotesk",sans-serif;cursor:pointer;
      clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px)
    }
    .dex-connect-wallet:hover{filter:brightness(1.06)}
    .dex-connect-wallet:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}
    .dex-connect-wallet.is-connected{
      background:var(--panel2);color:var(--cyan);border:1px solid var(--cyan);
    }
    .dex-connect-wallet.is-busy{opacity:.72;cursor:wait}
    .dex-connect-wallet.is-error{background:var(--panel2);color:var(--risk);border:1px solid var(--risk)}

    /* DISCOVERY-LIVE-01B — Full-width Discovery content */
    .shell{
      width:100%;max-width:none;margin:0;padding:92px 28px 38px;
      font-family:"JetBrains Mono",monospace
    }
    h1,h2,h3,.status-pill strong,.metric strong,.token-cell strong,
    .evidence-cell>strong,.rail-card h3,.future-box strong{
      font-family:"Space Grotesk",sans-serif;font-stretch:normal
    }
    .terminal-head{padding:10px 0 20px;align-items:end}
    .terminal-head .eyebrow{color:var(--cyan);font-size:10px;letter-spacing:.12em}
    .terminal-head h1{font-size:36px;font-weight:700}
    .terminal-head p{color:var(--muted)}
    .status-pill{
      border:1px solid var(--line);border-radius:0;background:var(--panel);
      padding:11px 13px
    }
    .status-pill.live{border-left:2px solid var(--cyan)}
    .status-pill span{color:var(--faint)}
    .status-pill small{color:var(--muted)}

    .metrics{gap:1px;border:1px solid var(--line);background:var(--line)}
    .metric{
      border:0!important;border-radius:0!important;background:var(--panel);
      padding:18px 20px
    }
    .metric:before{height:1px;background:var(--cyan);opacity:.55}
    .metric span{color:var(--faint)}
    .metric strong{font:600 22px "Space Grotesk",sans-serif}
    .metric small{color:var(--muted)}

    .workspace{grid-template-columns:minmax(0,1fr) 300px;gap:14px;margin-top:18px}
    .feed-panel,.rail-card{border:1px solid var(--line);border-radius:0!important;background:var(--panel)}
    .feed-head{padding:18px;border-bottom:1px solid var(--line);align-items:end}
    .feed-head .eyebrow{color:var(--cyan)}
    .feed-head h2{font-family:"Space Grotesk",sans-serif;font-weight:600}
    .feed-head p{color:var(--muted)}
    .terminal-search input{
      border:1px solid var(--line2);border-radius:0;background:var(--panel2);
      color:var(--text)
    }
    .terminal-search button,.clear-search{
      border:1px solid var(--cyan);border-radius:0;background:transparent;
      color:var(--cyan)
    }
    .feed-tabs{gap:1px;padding:12px 18px;background:var(--panel);border-bottom:1px solid var(--line)}
    .feed-tab{
      border:1px solid var(--line);border-radius:0;background:var(--panel2);
      color:var(--muted);font-weight:600
    }
    .feed-tab.active{border-color:var(--cyan);background:rgba(76,244,214,.07);color:var(--cyan)}
    .feed-tab b{color:inherit}
    .sort-note{color:var(--muted);border-color:var(--line)}
    .feed-columns-v33,
    html[data-theme="intel"] .feed-columns-v33{background:var(--panel2);border-color:var(--line)}
    .feed-columns-v33 span,
    html[data-theme="intel"] .feed-columns-v33 span{color:var(--faint)}
    .candidate-row-v32,
    html[data-theme="intel"] .candidate-row-v32{
      background:var(--panel);border-color:var(--line);
      border-radius:0!important;box-shadow:none!important;transform:none!important
    }
    .candidate-row-v32:hover,
    html[data-theme="intel"] .candidate-row-v32:hover{background:rgba(76,244,214,.035)}
    .candidate-row-v32>.token-cell,
    .candidate-row-v32>.feed-value,
    .candidate-row-v32>.why-now,
    .candidate-row-v32>.feed-action,
    html[data-theme="intel"] .candidate-row-v32>.token-cell,
    html[data-theme="intel"] .candidate-row-v32>.feed-value,
    html[data-theme="intel"] .candidate-row-v32>.why-now,
    html[data-theme="intel"] .candidate-row-v32>.feed-action{border-color:var(--line)}
    .rank{color:var(--faint)}
    .token-cell strong{color:var(--text)}
    .token-cell span,.token-cell small,.feed-value span,.why-now p{color:var(--muted)}
    .activity-tag{color:var(--cyan)}
    .inspect-link{
      border:1px solid var(--cyan)!important;border-radius:0!important;
      color:var(--cyan)!important;background:transparent!important
    }
    .inspect-link:hover{background:rgba(76,244,214,.07)!important}
    .rail-card{padding:18px}
    .rail-kicker{color:var(--cyan)}
    .network-mark{border-color:var(--line);background:var(--panel2)}
    .network-mark svg{fill:#B98CFF}
    .status-detail div,.coming-soon{border-color:var(--line)}
    .dex-badges span{border-color:var(--line2);border-radius:0;background:var(--panel2)}
    .coming-soon span{color:#B98CFF}
    .pagination{border-color:var(--line)}
    .pagination a{color:var(--cyan)}
    footer{color:var(--faint)}

    @media(max-width:980px){
      .dex-header-search{max-width:300px}
      .dex-gas-pill{display:none}
    }
    @media(max-width:820px){
      .dex-header-search{display:none}
      .shell{width:100%;padding:82px 16px 28px}
    }
    @media(max-width:520px){
      .dex-side-rail{display:none}
      .dex-app-shell{display:block}
      .dex-topbar{left:0;padding:0 12px}
      .dex-brand span{display:none}
      .dex-connect-wallet{padding:0 11px}
      .shell{padding-left:12px;padding-right:12px}
    }


    /* SOLANA-UI-02 — DEX Terminal Presentation Rebuild */
    .shell{padding-top:84px;display:flex;flex-direction:column;gap:16px}

    .dex-volume-panel{
      position:relative;min-height:210px;overflow:hidden;
      border:1px solid var(--line);background:
        radial-gradient(ellipse 800px 230px at 18% 0%,rgba(76,244,214,.075),transparent 62%),
        var(--panel)
    }
    .dex-volume-top{
      position:relative;z-index:2;display:flex;align-items:flex-start;justify-content:space-between;
      gap:20px;padding:20px 22px 0
    }
    .dex-section-kicker,.dex-section-label span{
      color:var(--faint);font:500 11px "JetBrains Mono",monospace;
      letter-spacing:.11em;text-transform:uppercase
    }
    .dex-volume-value{
      margin-top:10px;color:var(--text);font:700 44px "Space Grotesk",sans-serif;
      line-height:1
    }
    .dex-volume-source{
      margin-top:7px;color:var(--faint);
      font:500 10px "JetBrains Mono",monospace;
      letter-spacing:.08em
    }
    .dex-volume-state{
      display:flex;align-items:center;gap:7px;margin-top:2px;color:var(--faint);
      font:500 11px "JetBrains Mono",monospace;letter-spacing:.07em
    }
    .dex-status-dot{width:5px;height:5px;background:var(--cyan);box-shadow:0 0 6px var(--cyan)}
    .dex-status-dot.is-offline{background:var(--risk);box-shadow:0 0 6px var(--risk)}
    .dex-volume-chart{position:absolute;left:18px;right:18px;bottom:14px;height:122px}
    .dex-chart-grid{
      position:absolute;inset:0;
      background-image:linear-gradient(rgba(42,56,71,.45) 1px,transparent 1px);
      background-size:100% 30px;opacity:.45
    }
    .dex-chart-baseline{
      position:absolute;left:0;right:0;bottom:18px;height:1px;
      background:linear-gradient(90deg,transparent,var(--line2) 10%,var(--line2) 90%,transparent)
    }

    .dex-terminal-section{display:flex;flex-direction:column;gap:8px}
    .dex-section-label{display:flex;align-items:center;gap:10px}
    .dex-section-label i{height:1px;flex:1;background:var(--line)}
    .dex-panel-shell{min-width:0;border:1px solid var(--line);background:var(--panel)}
    .dex-panel-head{
      min-height:40px;display:flex;align-items:center;justify-content:space-between;gap:12px;
      padding:0 13px;border-bottom:1px solid var(--line)
    }
    .dex-panel-head strong{font:600 13.5px "Space Grotesk",sans-serif;letter-spacing:.01em}
    .dex-panel-head span{
      color:var(--faint);font:500 10.5px "JetBrains Mono",monospace;
      letter-spacing:.07em;text-transform:uppercase
    }

    .dex-signals-panel .dex-panel-shell{min-height:155px}
    .dex-empty-stream,.dex-intelligence-empty{
      min-height:108px;display:flex;align-items:center;gap:12px;padding:16px
    }
    .dex-empty-icon{
      width:28px;height:28px;display:grid;place-items:center;flex:0 0 auto;
      border:1px solid var(--line2);color:var(--cyan);
      font:500 12px "JetBrains Mono",monospace
    }
    .dex-empty-stream strong,.dex-intelligence-empty strong{
      display:block;color:var(--muted);font:600 12.5px "Space Grotesk",sans-serif
    }
    .dex-empty-stream small,.dex-intelligence-empty small{
      display:block;margin-top:4px;color:var(--faint);font-size:10.5px
    }

    .dex-market-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
    .dex-market-grid>.dex-panel-shell{min-height:180px}
    .dex-mini-table-head{
      display:grid;grid-template-columns:24px minmax(0,1fr) 96px 56px;
      gap:8px;padding:9px 12px;border-bottom:1px solid var(--line);
      background:var(--panel2)
    }
    .dex-mini-table-head span{
      color:var(--faint);font:500 10.5px "JetBrains Mono",monospace;
      letter-spacing:.05em;text-transform:uppercase
    }
    .dex-mini-table-head span:nth-child(3),
    .dex-mini-table-head span:nth-child(4){text-align:right}
    .dex-panel-empty{
      min-height:116px;display:grid;place-items:center;padding:16px;text-align:center;
      color:var(--faint);font:500 10.5px "JetBrains Mono",monospace
    }

    .dex-token-list .feed-panel{width:100%;border-radius:0;background:var(--panel)}
    .dex-token-list .feed-head{padding:14px 16px}
    .dex-token-list .feed-head h2{margin:3px 0 0;font:600 18px "Space Grotesk",sans-serif}
    .dex-token-list .feed-head p{font-size:11px;line-height:1.5}
    .dex-token-list .feed-head .eyebrow{color:var(--cyan);font-size:10.5px;letter-spacing:.08em}
    .dex-token-list .feed-tabs{padding:9px 12px}
    .dex-token-list .sort-note{padding:8px 12px}
    .dex-token-list .candidate-row-v32:hover{background:rgba(76,244,214,.03)}
    .dex-token-list .inspect-link{
      padding:6px 8px!important;font-family:"JetBrains Mono",monospace!important;
      font-size:10.5px!important;text-transform:uppercase
    }

    .terminal-head,.metrics,.workspace,.intel-rail{display:none!important}

    @media(max-width:1050px){
      .dex-market-grid{grid-template-columns:1fr}
      .dex-market-grid>.dex-panel-shell{min-height:150px}
    }
    @media(max-width:760px){
      .dex-volume-panel{min-height:185px}
      .dex-volume-top{padding:16px 16px 0}
      .dex-volume-chart{left:12px;right:12px}
      .dex-market-grid{gap:8px}
    }


    /* SOLANA-UI-03B CORRECTED — Typography Match Pass */
    .dex-panel-head{min-height:46px;padding:0 16px}
    .dex-mini-table-head{padding:11px 14px}

    .feed-columns-v33 span{
      font-family:"JetBrains Mono",monospace!important;
      font-size:10.5px!important;
      font-weight:500!important;
      letter-spacing:.04em!important;
    }

    .dex-token-list .candidate-row-v32{font-size:12.5px}
    .dex-token-list .candidate-row-v32 .compact-token strong{
      font-family:"Space Grotesk",sans-serif!important;
      font-size:13px!important;
      font-weight:600!important;
      letter-spacing:-.01em!important;
    }
    .dex-token-list .candidate-row-v32 .compact-token span,
    .dex-token-list .candidate-row-v32 .compact-token small{
      font-family:"JetBrains Mono",monospace!important;
    }
    .dex-token-list .candidate-row-v32 .feed-value span,
    .dex-token-list .candidate-row-v32 .feed-value strong,
    .dex-token-list .candidate-row-v32 .why-now>span{
      font-family:"JetBrains Mono",monospace!important;
    }
    .dex-token-list .candidate-row-v32 .feed-value strong{
      font-size:12.5px!important;
      font-weight:600!important;
      letter-spacing:-.015em!important;
    }
    .dex-token-list .candidate-row-v32 .why-now strong{
      font-family:"Space Grotesk",sans-serif!important;
      font-size:11px!important;
      font-weight:600!important;
    }

    .terminal-search input,
    .terminal-search button,
    .clear-search,
    .feed-tab,
    .sort-note{
      font-family:"JetBrains Mono",monospace!important;
      font-size:11.5px;
    }

    .dex-brand strong,
    .dex-connect-wallet{
      font-family:"Space Grotesk",sans-serif!important;
    }
    .dex-brand span,
    .dex-header-search input,
    .dex-header-search kbd,
    .dex-gas-pill{
      font-family:"JetBrains Mono",monospace!important;
    }


    /* SOLANA-UI-03C — DEX Volume Card Live Metrics + SVG Trend */
    .dex-volume-primary{
      display:flex;
      align-items:baseline;
      gap:14px;
    }
    .dex-volume-change{
      font-family:"JetBrains Mono",monospace;
      font-size:14px;
      font-weight:600;
      color:var(--faint);
      white-space:nowrap;
    }
    .dex-volume-change.up{color:var(--cyan)}
    .dex-volume-change.down{color:var(--risk)}

    .dex-volume-side{
      display:flex;
      flex-direction:column;
      align-items:flex-end;
      gap:12px;
    }
    .dex-volume-substats{
      display:flex;
      align-items:flex-start;
      justify-content:flex-end;
      gap:28px;
    }
    .dex-volume-substat{text-align:right}
    .dex-volume-substat strong{
      display:block;
      font-family:"Space Grotesk",sans-serif;
      font-size:19px;
      font-weight:600;
      line-height:1.1;
      color:var(--text);
    }
    .dex-volume-substat span{
      display:block;
      margin-top:5px;
      font-family:"JetBrains Mono",monospace;
      font-size:10.5px;
      font-weight:500;
      letter-spacing:.04em;
      color:var(--faint);
      white-space:nowrap;
    }

    .dex-volume-chart svg{
      position:absolute;
      inset:0;
      width:100%;
      height:100%;
      display:block;
      overflow:visible;
    }
    .dex-volume-line{
      fill:none;
      stroke:var(--cyan);
      stroke-width:1.8;
      stroke-linecap:round;
      stroke-linejoin:round;
      filter:drop-shadow(0 0 5px rgba(76,244,214,.55));
    }

    @media(max-width:980px){
      .dex-volume-top{flex-direction:column}
      .dex-volume-side{width:100%;align-items:flex-start}
      .dex-volume-substats{justify-content:flex-start;gap:22px}
      .dex-volume-substat{text-align:left}
    }
    @media(max-width:620px){
      .dex-volume-primary{align-items:flex-start;flex-direction:column;gap:5px}
      .dex-volume-substats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
      .dex-volume-substat:last-child{grid-column:1/-1}
    }


    /* HEADER V1.2 CORRECTED — Mobile/Tablet Responsive Fix */

    /* Tablet: keep Gas visible; preserve KPI row beside primary DEX metric. */
    @media(max-width:980px){
      .dex-gas-pill{
        display:flex!important;
        height:30px;
        padding:0 8px;
        font-size:10px;
        flex:0 0 auto;
      }

      .dex-volume-top{
        display:grid!important;
        grid-template-columns:minmax(150px,.78fr) minmax(300px,1.22fr)!important;
        align-items:start!important;
        column-gap:18px!important;
      }
      .dex-volume-side{
        width:auto!important;
        align-items:flex-end!important;
        gap:9px!important;
      }
      .dex-volume-substats{
        width:100%!important;
        display:grid!important;
        grid-template-columns:repeat(3,minmax(0,1fr))!important;
        gap:14px!important;
        justify-content:stretch!important;
      }
      .dex-volume-substat{
        text-align:right!important;
      }
      .dex-volume-substat strong{
        font-size:16px!important;
      }
      .dex-volume-substat span{
        margin-top:4px!important;
        font-size:8px!important;
        line-height:1.3!important;
        letter-spacing:.03em!important;
        white-space:nowrap!important;
      }
    }

    /* Narrow tablet: search yields space first, Gas + Connect remain. */
    @media(max-width:820px){
      .dex-topbar{
        gap:12px!important;
        padding-left:18px!important;
        padding-right:18px!important;
      }
      .dex-header-search{display:none!important}
      .dex-top-actions{gap:8px!important}
      .dex-gas-pill{display:flex!important}
      .dex-connect-wallet{
        flex:0 0 auto;
        height:34px!important;
        padding:0 12px!important;
        font-size:11.5px!important;
      }

      .dex-volume-top{
        grid-template-columns:minmax(138px,.72fr) minmax(260px,1.28fr)!important;
        column-gap:14px!important;
      }
      .dex-volume-substats{gap:10px!important}
      .dex-volume-substat strong{font-size:15px!important}
      .dex-volume-substat span{font-size:7.5px!important}
    }

    /* Phone: turn KPI row into one controlled strip, not loose stacked text. */
    @media(max-width:620px){
      .dex-volume-top{display:block!important}
      .dex-volume-side{
        width:100%!important;
        margin-top:10px!important;
        align-items:stretch!important;
      }
      .dex-volume-substats{
        display:grid!important;
        grid-template-columns:repeat(3,minmax(0,1fr))!important;
        gap:1px!important;
        width:100%!important;
        border-top:1px solid var(--line);
        border-bottom:1px solid var(--line);
        background:var(--line);
      }
      .dex-volume-substat,
      .dex-volume-substat:last-child{
        grid-column:auto!important;
        min-width:0;
        padding:8px 7px;
        text-align:left!important;
        background:var(--panel);
      }
      .dex-volume-substat strong{font-size:14px!important}
      .dex-volume-substat span{
        font-size:7px!important;
        line-height:1.3!important;
        white-space:normal!important;
      }
      .dex-volume-state{align-self:flex-start!important}
    }

    @media(max-width:520px){
      .dex-topbar{
        gap:8px!important;
        padding-left:10px!important;
        padding-right:10px!important;
      }
      .dex-brand strong{font-size:17px!important}
      .dex-top-actions{gap:6px!important}
      .dex-gas-pill{
        display:flex!important;
        height:28px!important;
        padding:0 6px!important;
        font-size:9px!important;
      }
      .dex-connect-wallet{
        height:32px!important;
        padding:0 9px!important;
        font-size:10.5px!important;
      }
    }

    /* TW-UI-03B — Market category tabs and Discovery relocation. */
    .dex-market-category-shell{border:1px solid var(--line);background:var(--panel)}
    .dex-market-tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-bottom:1px solid var(--line);background:var(--panel2)}
    .dex-market-tab{min-height:46px;padding:0 14px;border:0;border-right:1px solid var(--line);background:transparent;color:var(--muted);font:600 12px "Space Grotesk",sans-serif;cursor:pointer}
    .dex-market-tab:last-child{border-right:0}
    .dex-market-tab:hover{background:rgba(76,244,214,.035);color:var(--text)}
    .dex-market-tab[aria-selected="true"]{background:rgba(76,244,214,.07);box-shadow:inset 0 -2px 0 var(--cyan);color:var(--cyan)}
    .dex-market-tab:focus-visible{position:relative;z-index:1;outline:2px solid var(--cyan);outline-offset:-2px}
    .dex-market-panel[hidden]{display:none!important}
    .dex-market-panel>.feed-panel{border:0}
    /* TOKEN-LIST-UI-01 — compact premium market-feed table. */
    .dex-trending-table{min-width:0;background:var(--panel)}
    .dex-trending-head,.dex-trending-row{display:grid;grid-template-columns:minmax(230px,1.25fr) minmax(100px,.62fr) minmax(82px,.48fr) minmax(110px,.68fr) minmax(110px,.68fr) minmax(250px,1.45fr);align-items:center}
    .dex-trending-head{min-height:34px;border-bottom:1px solid var(--line);background:var(--panel2)}
    .dex-trending-head span{padding:0 12px;color:var(--faint);font:600 10px "JetBrains Mono",monospace;letter-spacing:.055em;text-transform:uppercase}
    .dex-trending-head span:not(:first-child){text-align:right}
    .dex-trending-head span:last-child{text-align:left;padding-left:16px}
    .dex-trending-row{min-height:58px;border-bottom:1px solid rgba(42,56,71,.72);transition:background .12s ease,box-shadow .12s ease}
    .dex-trending-row:last-child{border-bottom:0}
    .dex-trending-row:hover{background:rgba(76,244,214,.035);box-shadow:inset 2px 0 0 rgba(76,244,214,.72)}
    .dex-trending-token{display:flex;align-items:center;gap:9px;min-width:0;padding:8px 12px}
    .dex-trending-rank{width:22px;flex:0 0 22px;color:var(--faint);font:500 9.5px "JetBrains Mono",monospace}
    .dex-trending-token-link{display:flex;align-items:center;gap:10px;min-width:0;color:inherit;text-decoration:none;border-radius:6px}
    .dex-trending-token-link:focus-visible{outline:2px solid var(--cyan);outline-offset:4px}
    .dex-trending-token-link img,.dex-trending-avatar{width:32px;height:32px;flex:0 0 32px;border:1px solid var(--line2);border-radius:50%;background:var(--panel2)}
    .dex-trending-token-link img{object-fit:cover}
    .dex-trending-avatar{display:grid;place-items:center;color:var(--cyan);font:600 9px "JetBrains Mono",monospace}
    .dex-trending-token-link span{min-width:0}
    .dex-trending-token-link strong{display:block;color:var(--text);font:700 13px/1.15 "Space Grotesk",sans-serif;letter-spacing:.005em}
    .dex-trending-token-link small{display:block;max-width:190px;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--faint);font:500 9px/1.2 "JetBrains Mono",monospace}
    .dex-trending-value{padding:8px 12px;text-align:right;font-variant-numeric:tabular-nums}
    .dex-trending-value strong{color:var(--text);font:650 11.5px "JetBrains Mono",monospace}
    .dex-trending-value strong.up{color:var(--cyan)}
    .dex-trending-value strong.down{color:var(--risk)}
    .dex-trending-signal-cell{text-align:left;padding-left:16px;padding-right:14px}
    .dex-trending-signal{display:block;max-width:340px;color:var(--faint);font:500 10px/1.35 "JetBrains Mono",monospace;text-align:left}
    .dex-trending-signal.is-active{color:var(--text)}
    .dex-trending-signal strong{display:block;color:inherit;font:700 11px/1.25 "Space Grotesk",sans-serif;white-space:normal}
    .dex-trending-signal small{display:block;margin-top:3px;color:var(--faint);font:600 9px/1.25 "JetBrains Mono",monospace;white-space:normal}
    .dex-trending-signal.is-bullish strong{color:var(--cyan)}
    .dex-trending-signal.is-bearish strong{color:var(--risk)}
    .dex-trending-signal.is-mixed strong{color:var(--violet)}
    @media(max-width:1180px){
      .dex-trending-head,.dex-trending-row{grid-template-columns:minmax(220px,1.2fr) 100px 82px 110px 110px minmax(230px,1.35fr)}
    }
    @media(max-width:980px){
      .dex-trending-table{overflow-x:auto;overscroll-behavior-inline:contain}
      .dex-trending-head,.dex-trending-row{min-width:920px}
    }
    .dex-category-placeholder{min-height:260px;display:grid;place-items:center;padding:28px;text-align:center}
    .dex-category-placeholder strong{display:block;color:var(--muted);font:600 14px "Space Grotesk",sans-serif}
    .dex-category-placeholder small{display:block;max-width:520px;margin-top:6px;color:var(--faint);font:500 11px "JetBrains Mono",monospace;line-height:1.55}
    .dex-market-intelligence>.dex-panel-shell{min-height:150px}
    /* TW-UI-03D — Compact, honest Token List empty state. */
    .dex-token-list .empty-state{min-height:150px;display:flex;align-items:center;justify-content:center;gap:14px;margin:0;padding:32px 24px;border:0;background:var(--panel)}
    .dex-token-list .empty-icon{width:38px;height:38px;flex:0 0 38px;border-color:var(--line2);color:var(--cyan);font-size:15px}
    .dex-token-list .empty-state h3{font:600 16px "Space Grotesk",sans-serif;letter-spacing:0}
    .dex-token-list .empty-state p{max-width:620px;margin-top:5px;color:var(--muted);font:500 11px/1.55 "JetBrains Mono",monospace}
    .dex-token-list .empty-actions{margin-top:10px}
    @media(max-width:760px){
      .dex-market-tabs{display:flex;overflow-x:auto;scrollbar-width:thin}
      .dex-market-tab{min-width:112px;flex:1 0 auto}
      .dex-category-placeholder{min-height:210px}
      .dex-token-list .empty-state{min-height:132px;justify-content:flex-start;padding:26px 16px}
    }

    /* TW-UI-03E — Responsive and accessibility hardening. */
    :root,
    html[data-theme="plain"],
    html[data-theme="intel"]{--faint:#718096}
    .terminal-search input:focus-visible,
    .terminal-search button:focus-visible,
    .clear-search:focus-visible,
    .discovery-segment-v1:focus-visible{
      outline:2px solid var(--cyan);
      outline-offset:2px;
    }
    @media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
    @media(max-width:760px){
      .dex-token-list .feed-head{align-items:stretch}
      .dex-token-list .terminal-search{width:100%;min-width:0;flex-wrap:wrap}
      .dex-token-list .terminal-search input{width:auto;min-width:0;flex:1 1 180px}
      .dex-token-list .terminal-search button,
      .dex-token-list .clear-search{min-height:44px;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto}
      .dex-market-tabs{scroll-snap-type:x proximity;overscroll-behavior-inline:contain}
      .dex-market-tab{scroll-snap-align:start}
    }
    @media(max-width:620px){
      .dex-volume-substat span{font-size:9px!important}
    }
    @media(max-width:480px){
      .dex-token-list .empty-state{align-items:flex-start;gap:12px}
    }

  </style>
</head>
<body><div class="dex-app-shell">
  <aside class="dex-side-rail" aria-label="DexSato navigation">
    <a class="dex-rail-logo" href="/" aria-label="DexSato"><img src="/static/branding/dexsato-mark.png" alt=""></a>
    <nav class="dex-market-nav" aria-label="Market scope">
      <a class="dex-side-item dex-side-icon active" href="/discovery/solana" aria-current="page" aria-label="Solana" title="Solana">
        <svg class="dex-solana-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M5.2 5.2h12.9l-2.7 2.7H2.5l2.7-2.7Zm0 5.45h12.9l2.7 2.7H7.9l-2.7-2.7Zm0 5.45h12.9l-2.7 2.7H2.5l2.7-2.7Z"/>
        </svg>
      </a>
      <a class="dex-side-item dex-side-icon" href="/major-assets" aria-label="Major Assets" title="Major Assets">
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="8"></circle>
          <path d="M4 12h16M12 4c2.2 2.2 3.3 4.9 3.3 8S14.2 17.8 12 20M12 4C9.8 6.2 8.7 8.9 8.7 12S9.8 17.8 12 20"></path>
        </svg>
      </a>
    </nav>
    <nav class="dex-main-nav" aria-label="Main navigation">
      <span class="dex-side-item dex-side-icon" role="button" tabindex="0" aria-label="Watchlist" title="Watchlist">
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="m12 4 2.35 4.76 5.25.76-3.8 3.7.9 5.23L12 16l-4.7 2.45.9-5.23-3.8-3.7 5.25-.76L12 4Z"></path>
        </svg>
      </span>
    </nav>
    <div class="dex-rail-spacer"></div>
    <nav class="dex-utility-nav" aria-label="Utility navigation">
      <span class="dex-side-item" aria-disabled="true">Wallet Profile</span>
      <span class="dex-side-item" aria-disabled="true">Documentation</span>
      <span class="dex-side-item" aria-disabled="true">Disclaimer</span>
    </nav>
  </aside>
  <div class="dex-app-main">
    <header class="dex-topbar">
      <div class="dex-brand"><strong>dexsato</strong><span>DEX INTELLIGENCE</span></div>
      <label class="dex-header-search" aria-label="Search token, pair or contract">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
        <input type="search" placeholder="Search token, pair or contract" autocomplete="off">
        <kbd>/</kbd>
      </label>
      <div class="dex-top-actions">
        <div class="dex-gas-pill" aria-label="Solana recent priority fee"><span class="dex-gas-dot__SOLANA_GAS_DOT_CLASS__"></span><span>__SOLANA_GAS_LABEL__</span></div>
        <button id="dex-solana-wallet-button" class="dex-connect-wallet" type="button" aria-label="Connect Solana Wallet" aria-live="polite">Connect Wallet</button>
      </div>
    </header>
    <main class="shell">
  <section class="dex-volume-panel" aria-label="Total DEX volume">
    <div class="dex-volume-top">
      <div>
        <span class="dex-section-kicker">TOTAL DEX VOLUME · 24H · SOLANA</span>
        <div class="dex-volume-primary">
          <div class="dex-volume-value" aria-live="polite">__SOLANA_DEX_VOLUME__</div>
          <div class="dex-volume-change__SOLANA_DEX_CHANGE_CLASS__">__SOLANA_DEX_CHANGE__</div>
        </div>
        <div class="dex-volume-source">SOURCE · DEFILLAMA</div>
      </div>

      <div class="dex-volume-side">
        <div class="dex-volume-substats">
          <div class="dex-volume-substat">
            <strong>__SOLANA_TVL__</strong>
            <span>TOTAL VALUE LOCKED</span>
          </div>
          <div class="dex-volume-substat">
            <strong>__SOLANA_PERPS_VOLUME_24H__</strong>
            <span>PERPS VOLUME · 24H</span>
          </div>
          <div class="dex-volume-substat">
            <strong>__SOLANA_ACTIVE_PAIRS__</strong>
            <span>ACTIVE PAIRS</span>
          </div>
        </div>
        <div class="dex-volume-state">
          <span class="dex-status-dot__SOLANA_DEX_DOT_CLASS__"></span>
          <span>__SOLANA_DEX_STATE__</span>
        </div>
      </div>
    </div>

    <div class="dex-volume-chart" aria-hidden="true">
      <div class="dex-chart-grid"></div>
      <svg viewBox="0 0 1000 150" preserveAspectRatio="none">
        <defs>
          <linearGradient id="solanaDexVolumeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#4CF4D6" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="#4CF4D6" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="__SOLANA_DEX_AREA_PATH__" fill="url(#solanaDexVolumeFill)"/>
        <path class="dex-volume-line" d="__SOLANA_DEX_LINE_PATH__"/>
      </svg>
      <div class="dex-chart-baseline"></div>
    </div>
  </section>

  <section class="dex-terminal-section dex-signals-panel" aria-label="Live signals">
    <div class="dex-section-label"><span>LIVE SIGNALS</span><i></i></div>
    <div class="dex-panel-shell">
      <div class="dex-panel-head"><strong>Live market signal stream</strong><span>Solana discovery</span></div>
      <div class="dex-empty-stream"><span class="dex-empty-icon" aria-hidden="true">↗</span><div><strong>No signal data displayed yet</strong><small>Presentation shell only. Existing signal logic is unchanged.</small></div></div>
    </div>
  </section>

  <section class="dex-terminal-section dex-market-categories" aria-label="Solana market categories">
    <div class="dex-section-label"><span>MARKET VIEWS</span><i></i></div>
    <div class="dex-market-category-shell">
      <div class="dex-market-tabs" role="tablist" aria-label="Solana market categories" aria-orientation="horizontal">
        <button id="dex-market-tab-trending" class="dex-market-tab" type="button" role="tab" aria-selected="false" aria-controls="dex-market-panel-trending" tabindex="-1" data-market-tab="trending">Trending</button>
        <button id="dex-market-tab-top-traded" class="dex-market-tab" type="button" role="tab" aria-selected="false" aria-controls="dex-market-panel-top-traded" tabindex="-1" data-market-tab="top-traded">Top Traded</button>
        <button id="dex-market-tab-organic" class="dex-market-tab" type="button" role="tab" aria-selected="false" aria-controls="dex-market-panel-organic" tabindex="-1" data-market-tab="organic">Organic</button>
        <button id="dex-market-tab-discovery" class="dex-market-tab" type="button" role="tab" aria-selected="true" aria-controls="dex-market-panel-discovery" tabindex="0" data-market-tab="discovery">Discovery</button>
        <button id="dex-market-tab-recent" class="dex-market-tab" type="button" role="tab" aria-selected="false" aria-controls="dex-market-panel-recent" tabindex="-1" data-market-tab="recent">Recent</button>
      </div>

      <section id="dex-market-panel-trending" class="dex-market-panel" role="tabpanel" aria-labelledby="dex-market-tab-trending" data-market-panel="trending" hidden>
        __TRENDING_PANEL__
      </section>
      <section id="dex-market-panel-top-traded" class="dex-market-panel" role="tabpanel" aria-labelledby="dex-market-tab-top-traded" data-market-panel="top-traded" hidden>
        <div class="dex-category-placeholder"><div><strong>Top Traded market feed is not connected yet</strong><small>No data is generated or simulated in this UI phase.</small></div></div>
      </section>
      <section id="dex-market-panel-organic" class="dex-market-panel" role="tabpanel" aria-labelledby="dex-market-tab-organic" data-market-panel="organic" hidden>
        <div class="dex-category-placeholder"><div><strong>Organic market feed is not connected yet</strong><small>No data is generated or simulated in this UI phase.</small></div></div>
      </section>
      <section id="dex-market-panel-discovery" class="dex-market-panel dex-token-list" role="tabpanel" aria-labelledby="dex-market-tab-discovery" data-market-panel="discovery">
        <section class="feed-panel">
          <div class="feed-head">
            <div><span class="eyebrow">SOLANA DISCOVERY</span><h2>Token List</h2><p>Persistent, server-paginated observations. Historical inclusion does not mean current qualification.</p></div>
            <form class="terminal-search" method="get" action="/discovery/solana"><input type="hidden" name="view" value="__VIEW__"><input type="hidden" name="page" value="1"><input type="search" name="q" value="__SEARCH_QUERY__" placeholder="Search token, symbol, contract or DEX" aria-label="Search the discovery archive"><button type="submit">Search</button>__CLEAR_SEARCH__</form>
          </div>
          <nav class="discovery-segments-v1" aria-label="Solana discovery products">
            <a class="discovery-segment-v1 active" href="/discovery/solana" aria-current="page"><span>New Discoveries</span><small>Active</small></a>
            <span class="discovery-segment-v1 upcoming" aria-disabled="true"><span>Established Solana</span><small>Soon</small></span>
          </nav>
          <!-- TW-UI-03C: legacy discovery view controls intentionally omitted. -->
          __DISCOVERY_FEED__
        </section>
      </section>
      <section id="dex-market-panel-recent" class="dex-market-panel" role="tabpanel" aria-labelledby="dex-market-tab-recent" data-market-panel="recent" hidden>
        <div class="dex-category-placeholder"><div><strong>Recent market feed is not connected yet</strong><small>No data is generated or simulated in this UI phase.</small></div></div>
      </section>
    </div>
  </section>

  <section class="dex-terminal-section dex-market-intelligence" aria-label="Market intelligence">
    <div class="dex-section-label"><span>MARKET INTELLIGENCE</span><i></i></div>
    <article class="dex-panel-shell">
      <div class="dex-panel-head"><strong>MARKET INTELLIGENCE</strong><span>DexSato</span></div>
      <div class="dex-intelligence-empty"><span class="dex-empty-icon" aria-hidden="true">◇</span><div><strong>No intelligence items displayed yet</strong><small>Insights will appear only when backed by existing DexSato data.</small></div></div>
    </article>
  </section>
  <footer><span>Experimental discovery · evidence synthesis only · not financial advice.</span><span>__STATUS_MESSAGE__</span></footer>
</main>
  </div>
</div><script>
  const themeOptions=[...document.querySelectorAll("[data-theme-option]")];function applyTheme(theme){const value=theme==="plain"?"plain":theme==="intel"?"intel":"current";if(value==="current")delete document.documentElement.dataset.theme;else document.documentElement.dataset.theme=value;themeOptions.forEach(button=>{const active=button.dataset.themeOption===value;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));});try{localStorage.setItem("dexsato-theme",value);}catch(error){}}let saved="current";try{saved=localStorage.getItem("dexsato-theme")||"current";}catch(error){}applyTheme(saved);themeOptions.forEach(button=>button.addEventListener("click",()=>applyTheme(button.dataset.themeOption)));

  /* TW-UI-03B — Presentation-only market category navigation. */
  (() => {
    const tabs = [...document.querySelectorAll("[data-market-tab]")];
    const panels = [...document.querySelectorAll("[data-market-panel]")];
    if (!tabs.length || !panels.length) return;

    function activateTab(tab) {
      const selected = tab.dataset.marketTab;
      tabs.forEach(item => {
        const active = item === tab;
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
      });
      panels.forEach(panel => {
        panel.hidden = panel.dataset.marketPanel !== selected;
      });
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activateTab(tab));
      tab.addEventListener("keydown", event => {
        let nextIndex = index;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = tabs.length - 1;
        else return;
        event.preventDefault();
        activateTab(tabs[nextIndex]);
        tabs[nextIndex].focus();
      });
    });
  })();

  /* HEADER V1.3 — Solana Wallet Connect */
  (() => {
    const button = document.getElementById("dex-solana-wallet-button");
    if (!button) return;

    let provider = null;
    let connectedPublicKey = "";

    function detectProvider() {
      if (window.phantom && window.phantom.solana && window.phantom.solana.isPhantom) {
        return window.phantom.solana;
      }
      if (window.solflare && window.solflare.isSolflare) {
        return window.solflare;
      }
      if (window.solana && typeof window.solana.connect === "function") {
        return window.solana;
      }
      return null;
    }

    function shortAddress(value) {
      const address = String(value || "");
      if (address.length <= 12) return address;
      return address.slice(0, 4) + "…" + address.slice(-4);
    }

    function setDefault() {
      connectedPublicKey = "";
      button.textContent = "Connect Wallet";
      button.title = "";
      button.classList.remove("is-connected", "is-busy", "is-error");
      button.setAttribute("aria-label", "Connect Solana Wallet");
    }

    function setConnected(publicKey) {
      connectedPublicKey = String(publicKey || "");
      button.textContent = shortAddress(connectedPublicKey);
      button.title = connectedPublicKey;
      button.classList.remove("is-busy", "is-error");
      button.classList.add("is-connected");
      button.setAttribute("aria-label", "Solana wallet connected: " + connectedPublicKey);
    }

    function setError(message) {
      button.textContent = message;
      button.title = message;
      button.classList.remove("is-busy", "is-connected");
      button.classList.add("is-error");
      window.setTimeout(setDefault, 2200);
    }

    async function connectWallet() {
      provider = detectProvider();
      if (!provider) {
        setError("Wallet not found");
        return;
      }

      button.classList.add("is-busy");
      button.classList.remove("is-error");
      button.textContent = "Connecting…";

      try {
        const response = await provider.connect();
        const publicKey =
          (response && response.publicKey && response.publicKey.toString()) ||
          (provider.publicKey && provider.publicKey.toString()) ||
          "";
        if (!publicKey) throw new Error("Wallet connected without public key");
        try{localStorage.removeItem("dexsato-wallet-manual-disconnect");}catch(error){}
        setConnected(publicKey);
      } catch (error) {
        const rejected =
          error &&
          (error.code === 4001 ||
           /reject|cancel|declin/i.test(String(error.message || error)));
        setError(rejected ? "Cancelled" : "Connect failed");
      }
    }

    async function disconnectWallet() {
      button.classList.add("is-busy");
      button.textContent = "Disconnecting…";
      try {
        try{localStorage.setItem("dexsato-wallet-manual-disconnect","1");}catch(error){}
        if (provider && typeof provider.disconnect === "function") {
          await provider.disconnect();
        }
      } catch (error) {
        /* Provider disconnect errors should not trap the UI in connected state. */
      } finally {
        setDefault();
      }
    }

    button.addEventListener("click", () => {
      if (connectedPublicKey) {
        disconnectWallet();
        return;
      }
      connectWallet();
    });

    provider = detectProvider();
    let manualDisconnect = false;
    try{manualDisconnect=localStorage.getItem("dexsato-wallet-manual-disconnect")==="1";}catch(error){}
    if (provider && typeof provider.connect === "function" && !manualDisconnect) {
      Promise.resolve(provider.connect({ onlyIfTrusted: true }))
        .then((response) => {
          const publicKey =
            (response && response.publicKey && response.publicKey.toString()) ||
            (provider.publicKey && provider.publicKey.toString()) ||
            "";
          if (publicKey) setConnected(publicKey);
        })
        .catch(() => {});

      if (typeof provider.on === "function") {
        provider.on("connect", (publicKey) => {
          const value =
            (publicKey && publicKey.toString && publicKey.toString()) ||
            (provider.publicKey && provider.publicKey.toString()) ||
            "";
          if (value) setConnected(value);
        });
        provider.on("disconnect", () => setDefault());
        provider.on("accountChanged", (publicKey) => {
          if (publicKey) setConnected(publicKey.toString());
          else setDefault();
        });
      }
    }
  })();
</script>
</script></body></html>"""
    return (
        page.replace("__STATUS_HEADING__", escape(status_heading))
        .replace("__STATUS_MESSAGE__", escape(status_message))
        .replace("__TOKENS__", escape(tokens))
        .replace("__PAIRS__", escape(pairs))
        .replace("__QUALIFIED__", escape(qualified))
        .replace("__UPDATED__", escape(updated))
        .replace("__STATUS_LABEL__", escape(status_label))
        .replace("__DISCOVERY_FEED__", discovery_feed)
        .replace("__TRENDING_PANEL__", trending_panel)
        .replace("__PAGE__", str(page_number))
        .replace("__PAGE_COUNT__", str(page_count))
        .replace("__OBSERVED_VOLUME__", escape(observed_volume))
        .replace("__OBSERVED_TXNS__", escape(txns_label))
        .replace("__DEX_BADGES__", dex_badges)
        .replace("__VIEW__", escape(view, quote=True))
        .replace("__SEARCH_QUERY__", escape(search_query, quote=True))
        .replace("__CLEAR_SEARCH__", clear_search)
        .replace("__VIEW_TOTAL__", str(data.get("view_total", len(candidates))))
        .replace("__SORT_LABEL__", escape(sort_label))
        .replace("__SOLANA_DEX_VOLUME__", escape(dex_volume_24h))
        .replace("__SOLANA_DEX_CHANGE__", escape(dex_volume_change))
        .replace("__SOLANA_DEX_CHANGE_CLASS__", escape(dex_volume_change_class, quote=True))
        .replace("__SOLANA_TVL__", escape(dex_tvl))
        .replace("__SOLANA_PERPS_VOLUME_24H__", escape(perps_volume_24h))
        .replace("__SOLANA_ACTIVE_PAIRS__", escape(pairs))
        .replace("__SOLANA_DEX_STATE__", escape(dex_volume_state))
        .replace("__SOLANA_DEX_DOT_CLASS__", escape(dex_volume_dot_class, quote=True))
        .replace("__SOLANA_DEX_LINE_PATH__", escape(dex_volume_line, quote=True))
        .replace("__SOLANA_DEX_AREA_PATH__", escape(dex_volume_area, quote=True))
        .replace("__SOLANA_GAS_LABEL__", escape(solana_gas_label))
        .replace("__SOLANA_GAS_DOT_CLASS__", escape(solana_gas_dot_class, quote=True))
    )
