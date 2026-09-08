"""Exact-token discovery workspace with a controlled non-custodial D6 swap pilot."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import re
from typing import Any


def _usd(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.2f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:,.2f}K"
    if amount < .01:
        return f"${amount:,.8f}"
    return f"${amount:,.4f}"


def _short(value: str) -> str:
    return f"{value[:9]}…{value[-9:]}" if len(value) > 24 else value


def _relative_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Not recorded"
    try:
        observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "Not recorded"
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()))
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _chart_svg(candles: list[dict[str, Any]]) -> str:
    closes: list[float] = []
    for candle in candles:
        try:
            closes.append(float(candle["close"]))
        except (KeyError, TypeError, ValueError):
            continue
    if len(closes) < 6:
        count = len(closes)
        suffix = "s" if count != 1 else ""
        return (
            '<div class="chart-empty"><strong>Insufficient chart history</strong>'
            f'<span>Only {count} closed 4H candle{suffix} available. '
            'At least 6 are required before a trend chart is shown.</span></div>'
        )
    low, high = min(closes), max(closes)
    spread = high - low or 1.0
    points = " ".join(
        f"{20 + index * 960 / (len(closes) - 1):.1f},{220 - (value - low) * 180 / spread:.1f}"
        for index, value in enumerate(closes)
    )
    return (
        '<svg class="chart" viewBox="0 0 1000 250" role="img" '
        'aria-label="Validated exact-pool 4H closing-price chart">'
        '<line x1="20" y1="40" x2="980" y2="40"/><line x1="20" y1="130" x2="980" y2="130"/>'
        '<line x1="20" y1="220" x2="980" y2="220"/>'
        f'<polyline points="{points}"/></svg>'
    )


def _change_percent(value: Any) -> tuple[str, str]:
    """Format an observed timeframe change without inventing missing history."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "&#8212;", "unavailable"
    tone = "up" if amount > 0 else "down" if amount < 0 else "flat"
    return f"{amount:+.2f}%", tone


def _trader_timeframe_strip(detail: dict[str, Any]) -> str:
    """Render DexSato trader-standard quick timeframe evidence."""
    windows = (
        ("1m", "change_1m"),
        ("5m", "change_5m"),
        ("15m", "change_15m"),
        ("30m", "change_30m"),
        ("1H", "change_1h"),
        ("4H", "change_4h"),
    )
    cells: list[str] = []
    for label, key in windows:
        value, tone = _change_percent(detail.get(key))
        cells.append(
            '<div class="trader-tf-cell" data-timeframe="' + label + '">'
            '<span>' + label + '</span>'
            '<strong class="trader-tf-value ' + tone + '">' + value + '</strong>'
            '</div>'
        )
    return (
        '<div class="trader-tf-strip" aria-label="Trader timeframe changes">'
        + "".join(cells)
        + '</div>'
    )


# TOKEN_WORKSPACE_V24_UNIFIED_TOKEN_CARD
def _external_link(value: Any) -> str:
    url = str(value or "").strip()
    return url if url.startswith("https://") else ""


# TOKEN_WORKSPACE_V245_PRECISE_AGE_DISPLAY
def _format_pair_age_hours(hours: float) -> str:
    if hours < 0:
        return "Age unavailable"
    total_minutes = max(0, int(hours * 60))
    if total_minutes < 1:
        return "<1m"
    if total_minutes < 60:
        return f"{total_minutes}m"
    total_hours, minutes = divmod(total_minutes, 60)
    if total_hours < 24:
        return f"{total_hours}h {minutes}m" if minutes else f"{total_hours}h"
    days, hours_left = divmod(total_hours, 24)
    return f"{days}d {hours_left}h" if hours_left else f"{days}d"


def _normalize_pair_age_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text.lower() in {
        "none", "unknown", "unavailable", "age unavailable",
    }:
        return None
    compact = text.lower().replace(" ", "")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(m|h|d)", compact)
    if not match:
        return text
    amount = float(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return _format_pair_age_hours(amount / 60.0)
    if unit == "d":
        return _format_pair_age_hours(amount * 24.0)
    return _format_pair_age_hours(amount)


def _pair_age_display(detail: dict[str, Any]) -> str:
    # Prefer numeric age because it preserves sub-hour precision.
    for key in ("age_hours", "pair_age_hours", "hours_old"):
        try:
            hours = float(detail.get(key))
        except (TypeError, ValueError):
            continue
        return _format_pair_age_hours(hours)

    # Older labels remain safe fallbacks.
    for key in (
        "age", "pair_age", "age_label", "pair_age_label",
        "freshness", "freshness_label",
    ):
        normalized = _normalize_pair_age_text(detail.get(key))
        if normalized:
            return normalized

    return "Age unavailable"



def _dex_display(value: Any) -> str:
    raw = str(value or "DEX").strip()
    known = {
        "pumpswap": "PumpSwap",
        "pumpfun": "Pump.fun",
        "raydium": "Raydium",
        "meteora": "Meteora",
        "orca": "Orca",
    }
    return known.get(raw.lower(), raw or "DEX")


def _compact_contract(value: str) -> str:
    value = str(value or "")
    if len(value) <= 14:
        return value
    return f"{value[:6]}...{value[-4:]}"


def _info_link(label: str, url: str, css_class: str) -> str:
    safe = _external_link(url)
    if not safe:
        return ""
    return (
        f'<a class="token-info-link {css_class}" href="{escape(safe, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">'
        f'<span>{escape(label)}</span><b aria-hidden="true">&#8599;</b></a>'
    )



def _token_overview_card(detail: dict[str, Any]) -> str:
    """Render the production token data in the TW-DEX compact market header."""
    symbol = escape(str(detail.get("symbol") or "Unknown"))
    quote = escape(str(detail.get("quote_symbol") or "SOL"))
    name = escape(str(detail.get("name") or "Unknown token"))

    token_raw = str(detail.get("token_address") or "")
    token_attr = escape(token_raw, quote=True)
    contract_short = escape(_compact_contract(token_raw)) if token_raw else "Unavailable"

    pair_raw = str(detail.get("pair_address") or "")
    pair_attr = escape(pair_raw, quote=True)
    pair_short = escape(_compact_contract(pair_raw)) if pair_raw else "Unavailable"

    price = escape(_usd(detail.get("price_usd")))
    change_text, change_tone = _change_percent(detail.get("change_24h"))
    if change_text == "&#8212;":
        change_text = "Unavailable"

    liquidity = escape(_usd(detail.get("liquidity_usd")))
    volume_24h = escape(_usd(detail.get("volume_24h_usd")))
    dex = escape(_dex_display(detail.get("dex_id")))

    age_value = _pair_age_display(detail)
    age_text = escape(age_value if age_value != "Age unavailable" else "Unavailable")

    source_url = _external_link(detail.get("source_url"))
    dex_html = (
        f'<a class="tw-market-dex" href="{escape(source_url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{dex}</a>'
        if source_url else f'<span class="tw-market-dex">{dex}</span>'
    )

    image_url = _external_link(detail.get("token_image_url"))
    if image_url:
        avatar = (
            f'<img class="token-avatar-image" src="{escape(image_url, quote=True)}" '
            f'alt="{symbol} token logo" loading="lazy" referrerpolicy="no-referrer">'
        )
    else:
        initial = escape((str(detail.get("symbol") or "?")[:1] or "?").upper())
        avatar = f'<span class="token-avatar-fallback" aria-hidden="true">{initial}</span>'

    status = str(detail.get("quote_status") or "STORED").upper()
    status_label = "LIVE" if status == "LIVE" else "STORED"
    status_class = "" if status == "LIVE" else " stored"

    token_copy = (
        f'<button class="copy-address tw-market-copy" type="button" '
        f'data-copy-address="{token_attr}" aria-label="Copy token contract">Copy</button>'
        if token_raw else ""
    )
    pair_copy = (
        f'<button class="copy-address tw-market-copy" type="button" '
        f'data-copy-address="{pair_attr}" aria-label="Copy pair address">Copy</button>'
        if pair_raw else ""
    )

    return (
        '<section class="token-overview-card tw-market-header" aria-label="Token market overview">'
        '<div class="tw-market-top">'
        '<div class="tw-market-identity">'
        f'<div class="token-avatar tw-market-avatar">{avatar}</div>'
        '<div class="tw-market-identity-copy">'
        f'<h1>{symbol} / {quote}</h1>'
        f'<span>{name} · {dex} exact pool</span>'
        '</div></div>'
        '<div class="tw-market-price">'
        '<span>PRICE · USD</span>'
        f'<strong>{price}</strong>'
        f'<b class="token-change {escape(change_tone)}">{change_text} · 24H</b>'
        '</div>'
        '<div class="tw-market-kpi"><span>DEX VENUE</span>'
        f'<strong>{dex_html}</strong></div>'
        '<div class="tw-market-kpi"><span>AGE</span>'
        f'<strong>{age_text}</strong></div>'
        '<div class="tw-market-kpi"><span>LIQUIDITY</span>'
        f'<strong>{liquidity}</strong></div>'
        '<div class="tw-market-kpi"><span>VOLUME · 24H</span>'
        f'<strong>{volume_24h}</strong></div>'
        '</div>'
        '<div class="tw-market-meta">'
        '<div class="tw-market-meta-cell"><span>CONTRACT</span><div>'
        f'<code title="{token_attr}">{contract_short}</code>{token_copy}</div></div>'
        '<div class="tw-market-meta-cell"><span>PAIR ADDRESS</span><div>'
        f'<code title="{pair_attr}">{pair_short}</code>{pair_copy}</div></div>'
        '<div class="tw-market-meta-cell"><span>STATUS</span>'
        f'<strong class="tw-market-status{status_class}"><i></i>{status_label}</strong></div>'
        '<div class="tw-market-meta-cell tw-market-watch-cell"><span>ACTION</span>'
        f'<button class="token-watch tw-market-watch" type="button" data-watch-token="{token_attr}" '
        f'aria-label="Watch {symbol}"><span aria-hidden="true">&#9734;</span> Watch</button></div>'
        '</div>'
        f'{_trader_timeframe_strip(detail)}'
        '</section>'
    )

# TOKEN_WORKSPACE_V24_NAMEERROR_HOTFIX
# TOKEN_WORKSPACE_V24_SINGLE_TF_STRIP
# TOKEN_WORKSPACE_V244_AGE_DISPLAY_HOTFIX
# TOKEN_WORKSPACE_V245_AGE_PRIORITY_HOTFIX
# TOKEN_WORKSPACE_V246_ARIA_CLEANUP
# TOKEN_WORKSPACE_V247_SOCIAL_SEPARATOR_CLEANUP
# TOKEN_WORKSPACE_V248_DETERMINISTIC_SOCIAL_LINKS

# CHART_V21_INTERACTIVE_TRADING_CHART
# CHART_V22_LIVE_CANDLE
def _candlestick_chart_panel(detail: dict[str, Any]) -> str:
    raw = detail.get("candlestick_timeframes")
    datasets = raw if isinstance(raw, dict) else {}
    safe: dict[str, list[dict[str, float]]] = {}
    for timeframe in ("1m", "5m", "15m", "30m", "1H", "4H"):
        rows = datasets.get(timeframe)
        safe[timeframe] = rows if isinstance(rows, list) else []

    payload = escape(
        json.dumps(safe, separators=(",", ":"), ensure_ascii=True),
        quote=False,
    )
    buttons = "".join(
        (
            '<button class="candle-tf-button'
            + (' active' if timeframe == "5m" else '')
            + '" type="button" data-candle-timeframe="'
            + timeframe
            + '">'
            + timeframe
            + '</button>'
        )
        for timeframe in ("1m", "5m", "15m", "30m", "1H", "4H")
    )

    token_address = escape(str(detail.get("token_address") or ""), quote=True)
    live_url = f"/api/discovery/solana/{token_address}/candles"
    current_price_value = detail.get("price_usd")
    try:
        current_price = float(current_price_value)
        current_price_attr = str(current_price) if current_price > 0 else ""
    except (TypeError, ValueError):
        current_price_attr = ""

    return (
        '<section class="candlestick-panel" data-candlestick-panel '
        f'data-live-candle-url="{live_url}" '
        f'data-current-price-usd="{escape(current_price_attr, quote=True)}">'
        '<div class="candle-toolbar">'
        '<div class="candle-timeframe-tabs" role="group" aria-label="Candlestick timeframe">'
        + buttons
        + '</div>'
        '<div class="candle-toolbar-actions">'
        '<div class="candle-ohlc" data-candle-ohlc aria-live="polite">'
        '<span>O <b data-ohlc-open>--</b></span>'
        '<span>H <b data-ohlc-high>--</b></span>'
        '<span>L <b data-ohlc-low>--</b></span>'
        '<span>C <b data-ohlc-close>--</b></span>'
        '<span>V <b data-ohlc-volume>--</b></span>'
        '</div>'
        '<span class="candle-live-state" data-candle-live-state>'
        '<i aria-hidden="true"></i>LIVE'
        '</span>'
        '<button class="candle-reset" type="button" data-candle-reset>Reset view</button>'
        '</div>'
        '</div>'
        '<div class="candlestick-stage">'
        '<div class="lightweight-chart" data-lightweight-chart '
        'role="img" aria-label="Exact-pool interactive candlestick chart powered by TradingView Lightweight Charts"></div>'
        '<svg class="candlestick-chart lightweight-fallback-chart" viewBox="0 0 1000 420" '
        'preserveAspectRatio="none" role="img" aria-label="Exact-pool interactive candlestick chart fallback" '
        'tabindex="0" data-candlestick-svg hidden></svg>'
        '<div class="candlestick-empty" data-candlestick-empty hidden>'
        'Market candles unavailable for this timeframe.'
        '</div>'
        '<div class="lw-runtime-diagnostic static-bootstrap-diagnostic" '
        'data-static-bootstrap-diagnostic>'
        'TW-DEX-03F.2 HTML BOOTSTRAP ACTIVE'
        '</div>'
        '<script>'
        '(function(){'
        'var n=document.querySelector("[data-static-bootstrap-diagnostic]");'
        'if(n){n.textContent+=" | JS ACTIVE";n.dataset.scriptProbe="1";}'
        '})();'
        '</script>'
        '<div class="lw-runtime-diagnostic" data-lw-runtime-diagnostic hidden></div>'
        '</div>'
        '<script type="application/json" data-candlestick-data>'
        + payload
        + '</script>'
        '</section>'
    )


# TOKEN_WORKSPACE_V25_MULTITIMEFRAME_CANDLESTICK

# TRANSACTIONS_FEED_V121_ROBUST_UI_MOUNT
def _transactions_table_panel(detail: dict[str, Any]) -> str:
    token_address = escape(str(detail.get("token_address") or ""), quote=True)
    symbol = escape(str(detail.get("symbol") or "Token"))
    transactions_url = f"/api/discovery/solana/{token_address}/transactions"

    return (
        '<section class="transactions-panel" data-transactions-panel '
        f'data-transactions-url="{transactions_url}">'
        '<div class="recent-flow-label"><span>Recent Flow</span><small>30 latest exact-pool trades</small></div>'
        '<div class="transactions-flow" data-transactions-flow aria-label="Recent transaction flow">'
        '<div class="transactions-flow-item buy"><span>Buy volume</span>'
        '<b data-flow-buy-volume>--</b><small data-flow-buy-count>-- buys</small>'
        '<div class="transactions-flow-meter" aria-hidden="true"><i data-flow-buy-meter></i></div></div>'
        '<div class="transactions-flow-item sell"><span>Sell volume</span>'
        '<b data-flow-sell-volume>--</b><small data-flow-sell-count>-- sells</small>'
        '<div class="transactions-flow-meter" aria-hidden="true"><i data-flow-sell-meter></i></div></div>'
        '<div class="transactions-flow-item net" data-flow-net-card><span>Net flow</span>'
        '<b data-flow-net>--</b><small class="transactions-flow-bias">'
        '<i class="transactions-flow-bias-dot" aria-hidden="true"></i>'
        '<span data-flow-bias>Balanced</span></small></div>'
        '<div class="transactions-flow-item largest"><span>Largest trade</span>'
        '<b class="flow-largest-tone" data-flow-largest>--</b>'
        '<small class="flow-largest-tone" data-flow-largest-side>--</small></div>'
        '</div>'
        '<div class="transactions-detail-grid">'
        '<section class="recent-trades-card" aria-label="Recent exact-pool trades">'
        '<div class="transactions-head">'
        '<h2>Recent Trades</h2>'
        '<span class="transactions-state" data-transactions-state>Loading</span>'
        '</div>'
        '<div class="transactions-table-wrap">'
        '<table class="transactions-table">'
        '<thead><tr>'
        '<th>Time</th><th>Type</th><th>Price USD</th>'
        f'<th>Amount {symbol}</th><th>Total USD</th><th>Trader</th><th>Tx</th>'
        '</tr></thead>'
        '<tbody data-transactions-body>'
        '<tr class="transactions-placeholder">'
        '<td colspan="7">Loading recent exact-pool transactions...</td>'
        '</tr>'
        '</tbody></table></div></section>'
        '<section class="market-activity" data-market-activity aria-label="Multi-timeframe exact-pool market activity">'
        '<div class="market-activity-head"><span>Market Activity</span><small data-market-activity-source>Loading aggregate</small></div>'
        '<div class="market-activity-wrap"><table class="market-activity-table"><thead><tr><th>Window</th><th>Buy</th><th>Sell</th><th>Trades</th><th>Volume</th></tr></thead>'
        '<tbody data-market-activity-body><tr><td colspan="5">Loading exact-pool activity...</td></tr></tbody></table></div></section>'
        '</div>'
        '</section>'
    )


# TOKEN_OBSERVATION_V28_LEFT_RAIL
def _token_observation_panel(detail: dict[str, Any]) -> str:
    """Render verified facts only; unavailable evidence is never inferred."""
    change, change_tone = _change_percent(detail.get("change_24h"))
    rows = (
        ("Mint authority", str(detail.get("mint_authority_observation") or "Unavailable"), ""),
        ("Freeze authority", str(detail.get("freeze_authority_observation") or "Unavailable"), ""),
        ("Metadata", str(detail.get("metadata_observation") or "Unavailable"), ""),
        ("Sell route verified", "Unavailable", "sell-route"),
        ("Liquidity", _usd(detail.get("liquidity_usd")), ""),
        ("24h change", change, change_tone),
        ("Observed price", _usd(detail.get("price_usd")), ""),
        ("Market cap / FDV", _usd(detail.get("market_cap")), ""),
        ("Pair age", str(detail.get("pair_age") or "Unavailable"), ""),
    )
    rendered = []
    for label, value, tone in rows:
        attribute = ' data-sell-route-status' if tone == "sell-route" else ""
        css_tone = "" if tone == "sell-route" else f" {escape(tone)}" if tone else ""
        rendered.append(f'<div class="token-observation-row"><span>{escape(label)}</span><b class="token-observation-value{css_tone}"{attribute}>{escape(value)}</b></div>')
    return ('<section class="workspace-rail-card token-observation-v28" data-token-observation>'
            '<div class="workspace-rail-head"><h2>Token Intelligence</h2><small>Observed data only</small></div>'
            f'<div class="token-observation-rows">{"".join(rendered)}</div>'
            '<p class="token-observation-note">Route availability is not a safety guarantee.</p></section>')


def _coin_list_panel(detail: dict[str, Any], feed: dict[str, Any] | None) -> str:
    """Render the current discovery archive as token navigation, not a ranking."""
    candidates = feed.get("candidates") if isinstance(feed, dict) else None
    rows = [dict(item) for item in candidates or [] if isinstance(item, dict)]
    current_token = str(detail.get("token_address") or "")
    if current_token:
        selected = next(
            (item for item in rows if str(item.get("token_address") or "") == current_token),
            None,
        )
        other_rows = [
            item for item in rows
            if str(item.get("token_address") or "") != current_token
        ]
        rows = [{**(selected or {}), **detail}, *other_rows]

    rendered: list[str] = []
    seen: set[str] = set()
    for item in rows:
        token_address = str(item.get("token_address") or "").strip()
        if not token_address or token_address in seen:
            continue
        seen.add(token_address)
        symbol = escape(str(item.get("symbol") or "Unknown"))
        quote = escape(str(item.get("quote_symbol") or "SOL"))
        price = escape(_usd(item.get("price_usd")))
        change_text, change_tone = _change_percent(item.get("change_24h"))
        active = token_address == current_token
        current = ' aria-current="page"' if active else ""
        active_class = " active" if active else ""
        initial = escape((str(item.get("symbol") or "?")[:1] or "?").upper())
        image_url = _external_link(item.get("token_image_url"))
        avatar = (
            f'<img src="{escape(image_url, quote=True)}" alt="" loading="lazy" '
            'referrerpolicy="no-referrer">'
            if image_url else f'<span aria-hidden="true">{initial}</span>'
        )
        rendered.append(
            f'<a class="coin-list-row{active_class}" href="/discovery/solana/'
            f'{escape(token_address, quote=True)}"{current}>'
            f'<span class="coin-list-avatar">{avatar}</span>'
            f'<span class="coin-list-identity"><strong>{symbol} / {quote}</strong>'
            f'<small>{price}</small></span>'
            f'<b class="coin-list-change {escape(change_tone)}">{change_text}</b></a>'
        )
        if len(rendered) >= 30:
            break

    body = "".join(rendered) if rendered else (
        '<div class="coin-list-empty">No discovery tokens are available.</div>'
    )
    return (
        '<section class="workspace-rail-card coin-list token-list-v07a" data-coin-list>'
        '<div class="workspace-rail-head token-list-head-v07a"><h2>Token List</h2>'
        '<span class="token-list-chain-v07a">SOLANA</span></div>'
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Token list views">'
        '<button type="button" class="token-list-tab-v07a active" role="tab" aria-selected="true">Trending</button>'
        '<button type="button" class="token-list-tab-v07a" role="tab" aria-selected="false">Fresh</button>'
        '<button type="button" class="token-list-tab-v07a" role="tab" aria-selected="false">Watchlist</button>'
        '</div>'
        '<label class="coin-list-search"><span class="sr-only">Search coin list</span>'
        '<input type="search" placeholder="Search token or pair" data-coin-list-search></label>'
        f'<div class="coin-list-rows" data-coin-list-rows>{body}</div></section>'
    )


def render_solana_discovery_token_page(
    detail: dict[str, Any],
    feed: dict[str, Any] | None = None,
) -> str:
    """Render exact-token evidence and explicit wallet-approved Jupiter execution."""
    token_overview_card = _token_overview_card(detail)
    candlestick_chart_panel = _candlestick_chart_panel(detail)
    transactions_table_panel = _transactions_table_panel(detail)
    token_observation_panel = _token_observation_panel(detail)
    coin_list_panel = _coin_list_panel(detail, feed)
    symbol = escape(str(detail.get("symbol") or "Unknown"))
    trader_tf_strip = _trader_timeframe_strip(detail)
    name = escape(str(detail.get("name") or "Unknown token"))
    quote = escape(str(detail.get("quote_symbol") or "SOL"))
    token_raw = str(detail.get("token_address") or "")
    pool_raw = str(detail.get("pair_address") or "")
    token = escape(token_raw)
    pool = escape(pool_raw)
    change_value = detail.get("change_24h")
    try:
        change = f"{float(change_value):+.2f}%"
        change_tone = "up" if float(change_value) >= 0 else "down"
    except (TypeError, ValueError):
        change, change_tone = "Unavailable", ""
    source_url = str(detail.get("source_url") or "")
    source_link = (
        f'<a href="{escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">Open market source â†—</a>'
        if source_url.startswith("https://dexscreener.com/") else "Market source unavailable"
    )
    evidence = escape(str(detail.get("evidence") or "Exact-pool market activity was observed."))
    risk = escape(str(detail.get("risk_label") or "Token security is not independently verified."))
    chart = ""
    status = escape(str(detail.get("quote_status") or "STORED"))
    status_label = escape(str(detail.get("quote_label") or "Stored collector observation"))
    assessment = detail.get("current_qualification") if isinstance(detail.get("current_qualification"), dict) else {}
    if detail.get("currently_qualified") is True:
        qualification_title = escape(str(assessment.get("title") or "Qualified now"))
        qualification_message = escape(str(assessment.get("message") or "Current identity, exact-pool, liquidity and 24h activity checks passed."))
        qualification_tone = "qualified"
    else:
        qualification_title = escape(str(assessment.get("title") or "Not evaluated in this scan"))
        qualification_message = escape(str(assessment.get("message") or "No current scan assessment was recorded for this archived observation."))
        qualification_tone = "not-qualified"
    last_qualified = escape(_relative_timestamp(detail.get("last_qualified_at")))
    current_scan = escape(_relative_timestamp(assessment.get("scan_at")))
    qualification_panel = (
        f'<section class="qualification qualification-vp0d3 {qualification_tone}">'
        '<span class="eyebrow">Qualification</span>'
        f'<h3>{qualification_title}</h3><p class="qualification-reason">{qualification_message}</p>'
        '<span class="eyebrow qualification-history-label">Last confirmed checks</span>'
        '<div class="check">Solana token identity</div><div class="check">Exact token and pool match</div>'
        '<div class="check">Observed liquidity threshold</div><div class="check">Observed 24h activity</div>'
        f'<div class="source">Last qualified: {last_qualified}<br>Current scan: {current_scan}</div>'
        '</section>'
    )
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__SYMBOL__ · Solana Discovery</title>
<script>try{const t=localStorage.getItem("dexsato-theme");if(t==="plain"||t==="intel")document.documentElement.dataset.theme=t;}catch(error){}</script>
<style>
:root{color-scheme:dark;--bg:#050b13;--panel:#091422;--panel2:#0d1b2d;--line:#20344b;--text:#f4f7fb;--muted:#91a8c5;--cyan:#0de6d1;--blue:#5a98ff;--amber:#ffb800;--green:#26d49a;--red:#ff5675;--display:"Bahnschrift SemiBold","Bahnschrift","Arial Narrow","Segoe UI",sans-serif;--ui:"Segoe UI Variable Text","Segoe UI",sans-serif;--mono:"Cascadia Mono","Consolas",monospace}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--ui);font-size:15px;line-height:1.55}.shell{width:min(1180px,calc(100% - 32px));margin:auto;padding:20px 0 34px}.topbar{display:flex;align-items:center;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:14px}.brand img{width:138px}.brand strong,h1,h2,h3,.value{font-family:var(--display)}a{color:#8ab9ff}.back{padding:8px 12px;border:1px solid var(--line);border-radius:6px;text-decoration:none;color:var(--text)}.hero{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:end;padding:28px 0 20px}.eyebrow{color:var(--cyan);font:700 11px var(--mono);letter-spacing:.12em;text-transform:uppercase}.hero h1{margin:5px 0 0;font-size:38px;line-height:1.05}.hero p{margin:8px 0 0;color:var(--muted)}.status{padding:12px 15px;border:1px solid var(--line);border-left:3px solid var(--green);background:var(--panel)}.status b,.status small{display:block}.status b{font-family:var(--mono)}.status small{color:var(--muted)}.identity,.chart-panel,.card{border:1px solid var(--line);background:var(--panel)}.identity{padding:20px}.identity-head{display:flex;justify-content:space-between;gap:18px}.identity h2{margin:0;font-size:25px}.identity .name{color:var(--muted)}.addresses{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:17px}.address{padding:12px;background:var(--panel2)}.address span,.metric span{display:block;color:var(--muted);font:700 10px var(--mono);text-transform:uppercase}.address code{display:block;margin-top:5px;font:12px var(--mono);overflow-wrap:anywhere}.chart-panel{margin-top:14px;padding:20px}.section-head{display:flex;justify-content:space-between;gap:15px;align-items:end}.section-head h2{margin:4px 0 0;font-size:23px}.section-head p{margin:4px 0 0;color:var(--muted)}.chart{display:block;width:100%;height:270px;margin-top:15px;background:var(--panel2);border:1px solid var(--line)}.chart line{stroke:var(--line);stroke-width:1}.chart polyline{fill:none;stroke:var(--cyan);stroke-width:3;vector-effect:non-scaling-stroke}.chart-empty{display:grid;place-items:center;min-height:240px;margin-top:15px;border:1px dashed var(--line);color:var(--amber);background:var(--panel2)}.grid{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin-top:14px}.card{padding:18px}.card h3{margin:0 0 12px;font-size:18px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:13px;background:var(--panel2)}.metric .value{display:block;margin-top:5px;font-size:19px}.change.up{color:var(--green)}.change.down{color:var(--red)}.evidence{margin-top:14px;padding:15px;border-left:2px solid var(--cyan);background:var(--panel2)}.evidence strong{display:block;margin-bottom:5px}.risk{margin-top:12px;padding:15px;border-left:2px solid var(--amber);background:rgba(255,184,0,.06)}.risk strong{color:var(--amber)}.check{padding:9px 0;border-top:1px solid var(--line)}.check:before{content:"\\2713";margin-right:8px;color:var(--green)}.jupiter{border-left:2px solid #9b5cff}.jupiter .badge{display:inline-block;padding:5px 8px;border:1px solid #7c45c8;border-radius:999px;color:#c9a8ff;font:700 10px var(--mono)}.source{margin-top:13px;padding-top:12px;border-top:1px solid var(--line)}footer{display:flex;justify-content:space-between;gap:20px;margin-top:18px;color:var(--muted);font-size:11px}
html[data-theme="plain"]{color-scheme:light;--bg:#f5f7fa;--panel:#fff;--panel2:#eef3f8;--line:#c8d3df;--text:#102035;--muted:#526981;--cyan:#087f8c;--blue:#276dcc;--amber:#9a6200;--green:#147c54;--red:#ba3654}
@media(max-width:760px){.shell{width:calc(100% - 18px);padding-top:10px}.brand img{width:112px}.hero{grid-template-columns:1fr;padding-top:21px}.hero h1{font-size:29px}.status{width:100%}.identity-head{display:block}.addresses,.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.chart{height:210px}.section-head{display:block}footer{flex-direction:column}}
.address-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.copy-address{flex:0 0 auto;padding:6px 8px;border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--blue);font:700 10px var(--mono);cursor:pointer}.copy-address:focus-visible,.sandbox-button:focus-visible,.sandbox-input:focus-visible{outline:2px solid var(--blue);outline-offset:2px}.chart-empty{place-content:center;gap:7px;padding:24px;text-align:center}.chart-empty strong{font:700 18px var(--display)}.chart-empty span{max-width:560px;color:var(--muted);font-size:13px}
.qualification{margin-top:14px}.jupiter{padding:21px}.jupiter h3{margin:4px 0 12px;font-size:22px}.jupiter>.eyebrow{font-size:11px}.sandbox-note{margin:13px 0;color:var(--muted);font-size:14px;line-height:1.6}.wallet-state{margin:12px 0;padding:12px;background:var(--panel2);font:13px/1.5 var(--mono);overflow-wrap:anywhere}.sandbox-form{display:grid;gap:11px;margin-top:14px}.sandbox-form label{color:var(--muted);font:700 11px var(--mono);letter-spacing:.07em;text-transform:uppercase}.sandbox-input{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:5px;background:var(--panel2);color:var(--text);font-size:15px}.sandbox-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.sandbox-button{padding:11px 12px;border:1px solid var(--blue);border-radius:5px;background:transparent;color:var(--blue);font:700 13px var(--ui);cursor:pointer}.sandbox-button.primary{background:var(--blue);color:#fff}.sandbox-button:disabled{cursor:not-allowed;opacity:.55}.quote-result{display:none;margin-top:14px;padding-top:14px;border-top:1px solid var(--line)}.quote-result.visible{display:block}.quote-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.quote-cell{padding:11px;background:var(--panel2)}.quote-cell span,.fee-row span{display:block;color:var(--muted);font:700 10px var(--mono);text-transform:uppercase}.quote-cell b{display:block;margin-top:5px;font:700 15px/1.4 var(--mono);overflow-wrap:anywhere}.fee-row{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid var(--line);font-size:13px}.quote-policy{margin-top:11px;color:var(--muted);font-size:12px;line-height:1.55}.quote-error{color:var(--amber)}
.swap-warning{margin:14px 0;padding:12px;border-left:2px solid var(--amber);background:rgba(255,184,0,.08);font-size:12px;line-height:1.55}.swap-warning strong{display:block;color:var(--amber)}.swap-consent{display:flex;gap:9px;align-items:flex-start;margin:14px 0;color:var(--text);font-size:12px;line-height:1.5}.swap-consent input{margin-top:3px;accent-color:var(--blue)}.swap-success{color:var(--green)}.swap-success p{overflow-wrap:anywhere;color:var(--muted);font:11px/1.6 var(--mono)}
@media(max-width:430px){.sandbox-actions,.quote-grid{grid-template-columns:1fr}}

/* Token Workspace MI v4 */
html[data-theme="intel"]{
  color-scheme:dark;
  --bg:#0b0f14;
  --panel:#0f141a;
  --panel2:#121820;
  --line:#28313b;
  --text:#e6e9ed;
  --muted:#a0a8b3;
  --cyan:#ff9418;
  --blue:#ff9418;
  --amber:#ff9418;
  --green:#22d27f;
  --red:#ff5f78;
  --display:"Segoe UI Variable Display","Segoe UI",Arial,sans-serif;
  --ui:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
  --mono:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
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
html[data-theme="intel"] .brand strong,
html[data-theme="intel"] h1,
html[data-theme="intel"] h2,
html[data-theme="intel"] h3,
html[data-theme="intel"] .value{
  font-family:"Segoe UI Variable Display","Segoe UI",Arial,sans-serif;
  font-weight:600;
  letter-spacing:-.015em;
}
html[data-theme="intel"] .hero h1{font-weight:600;letter-spacing:-.025em}
html[data-theme="intel"] .hero p,
html[data-theme="intel"] .section-head p,
html[data-theme="intel"] .sandbox-note,
html[data-theme="intel"] footer{color:#a6aeb8}
html[data-theme="intel"] .eyebrow{
  color:#ff9418;
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
  font-weight:650;
  letter-spacing:.065em;
}
html[data-theme="intel"] .identity,
html[data-theme="intel"] .chart-panel,
html[data-theme="intel"] .card,
html[data-theme="intel"] .status{
  background:#0f141a;
  border-color:#28313b;
}
html[data-theme="intel"] .status{border-left-color:#ff9418}
html[data-theme="intel"] .address,
html[data-theme="intel"] .metric,
html[data-theme="intel"] .wallet-state,
html[data-theme="intel"] .quote-cell{background:#121820}
html[data-theme="intel"] .address span,
html[data-theme="intel"] .metric span,
html[data-theme="intel"] .quote-cell span,
html[data-theme="intel"] .fee-row span,
html[data-theme="intel"] .sandbox-form label{
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
  font-weight:600;
  letter-spacing:.04em;
  color:#87919c;
}
html[data-theme="intel"] .address code,
html[data-theme="intel"] .wallet-state,
html[data-theme="intel"] .quote-cell b,
html[data-theme="intel"] .metric .value{
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
  font-variant-numeric:tabular-nums lining-nums;
  font-feature-settings:"tnum" 1,"lnum" 1;
  letter-spacing:0;
}
html[data-theme="intel"] .address code,
html[data-theme="intel"] .wallet-state,
html[data-theme="intel"] .quote-cell b{font-weight:500}
html[data-theme="intel"] .metric .value{font-weight:600}
html[data-theme="intel"] .chart{background:#121820;border-color:#28313b}
html[data-theme="intel"] .chart-empty{background:#121820;border-color:#34404c;color:#ffad4b}
html[data-theme="intel"] .evidence{background:#121820;border-left-color:#22d27f}
html[data-theme="intel"] .risk{background:rgba(255,148,24,.055);border-left-color:#ff9418}
html[data-theme="intel"] .risk strong{color:#ffad4b}
html[data-theme="intel"] .check{border-top-color:#28313b}
html[data-theme="intel"] .check:before{color:#22d27f}
html[data-theme="intel"] .source,
html[data-theme="intel"] .quote-result,
html[data-theme="intel"] .fee-row{border-color:#28313b}
html[data-theme="intel"] .sandbox-input{
  background:#121820;
  border-color:#303a45;
  color:#e6e9ed;
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
}
html[data-theme="intel"] .sandbox-button{
  border-color:#ff9418;
  color:#ffad4b;
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
}
html[data-theme="intel"] .sandbox-button.primary{
  background:#ff9418;
  border-color:#ff9418;
  color:#0b0f14;
}
html[data-theme="intel"] .copy-address{
  border-color:#303a45;
  color:#ffad4b;
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
}
html[data-theme="intel"] .swap-warning{
  border-left-color:#ff9418;
  background:rgba(255,148,24,.065);
}
html[data-theme="intel"] .swap-warning strong{color:#ffad4b}
html[data-theme="intel"] .back{border-color:#303a45}
html[data-theme="intel"] a{color:#ffad4b}

.theme-controls{display:flex;align-items:center;gap:8px}
.theme-switcher{
  display:flex;align-items:center;gap:4px;padding:3px;
  border:1px solid var(--line);border-radius:7px;background:var(--panel)
}
.theme-option{
  display:grid;place-items:center;min-width:30px;height:30px;padding:0 7px;
  border:0;border-radius:5px;background:transparent;color:var(--muted);
  font:600 12px/1 var(--ui);cursor:pointer
}
.theme-option:hover{color:var(--text)}
.theme-option.active{background:var(--blue);color:#fff}
html[data-theme="intel"] .theme-switcher{background:#0f141a;border-color:#303a45}
html[data-theme="intel"] .theme-option.active{background:#ff9418;color:#0b0f14}
html[data-theme="plain"] .theme-option.active{background:var(--blue);color:#fff}

/* Token Workspace v2 Decision Layout - UI only */
html[data-theme="intel"] .hero{margin-bottom:18px}
html[data-theme="intel"] .hero h1{font-size:clamp(30px,3vw,42px);line-height:1.08;margin-bottom:7px}
html[data-theme="intel"] .hero p{max-width:760px;font-size:14px;line-height:1.55}
html[data-theme="intel"] .identity{padding:20px 22px}
html[data-theme="intel"] .chart-panel{padding:20px 22px}

/* Main decision hierarchy */
html[data-theme="intel"] .decision-grid-v2{
  display:grid !important;
  grid-template-columns:minmax(0,1fr) 330px !important;
  gap:16px !important;
  align-items:start !important;
}
html[data-theme="intel"] .decision-main-v2{min-width:0}
html[data-theme="intel"] .decision-side-v2{
  position:sticky;
  top:16px;
  border-color:#34404c;
}
html[data-theme="intel"] .decision-side-v2 h2{font-size:20px;line-height:1.25}

/* TOKEN_WORKSPACE_V283_THEME_PARITY */
.dexsato-evidence-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;margin:0 0 16px;border:1px solid var(--line);background:var(--panel)}
.dexsato-evidence-item{min-width:0;padding:12px 14px;border-right:1px solid var(--line)}
.dexsato-evidence-item:last-child{border-right:0}
.dexsato-evidence-label{display:block;margin-bottom:5px;color:var(--muted);font-size:10px;font-weight:650;letter-spacing:.08em;text-transform:uppercase}
.dexsato-evidence-value{display:flex;align-items:center;gap:7px;color:var(--text);font-size:13px;font-weight:600;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dexsato-evidence-value>span{overflow:hidden;text-overflow:ellipsis}
.dexsato-evidence-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 3px color-mix(in srgb,var(--green) 9%,transparent);flex:0 0 auto}
.dexsato-evidence-item.security .dexsato-evidence-dot{background:var(--amber);box-shadow:0 0 0 3px color-mix(in srgb,var(--amber) 9%,transparent)}
@media(max-width:900px){.dexsato-evidence-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.dexsato-evidence-item{border-bottom:1px solid var(--line)}}
@media(max-width:560px){.dexsato-evidence-strip{grid-template-columns:1fr}.dexsato-evidence-item{border-right:0}}

/* DexSato signature evidence strip */
html[data-theme="intel"] .dexsato-evidence-strip{
  display:grid;
  grid-template-columns:repeat(5,minmax(0,1fr));
  gap:0;
  margin:0 0 16px;
  border:1px solid #303a45;
  background:#0f141a;
}
html[data-theme="intel"] .dexsato-evidence-item{
  min-width:0;
  padding:12px 14px;
  border-right:1px solid #28313b;
}
html[data-theme="intel"] .dexsato-evidence-item:last-child{border-right:0}
html[data-theme="intel"] .dexsato-evidence-label{
  display:block;
  margin-bottom:5px;
  color:#87919c;
  font-size:10px;
  font-weight:650;
  letter-spacing:.08em;
  text-transform:uppercase;
}
html[data-theme="intel"] .dexsato-evidence-value{
  display:flex;
  align-items:center;
  gap:7px;
  color:#e6e9ed;
  font-size:13px;
  font-weight:600;
  line-height:1.25;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
html[data-theme="intel"] .dexsato-evidence-dot{
  width:7px;height:7px;border-radius:50%;background:#22d27f;box-shadow:0 0 0 3px rgba(34,210,127,.09);flex:0 0 auto
}
html[data-theme="intel"] .dexsato-evidence-item.security .dexsato-evidence-dot{background:#ff9418;box-shadow:0 0 0 3px rgba(255,148,24,.09)}

/* Market snapshot: fast scan, not a wall of cards */
html[data-theme="intel"] .decision-main-v2 > h2:first-child{margin-bottom:12px}
html[data-theme="intel"] .decision-main-v2 .metric{
  padding:12px 14px;
  min-height:70px;
  border:1px solid #202933;
  background:#121820;
}
html[data-theme="intel"] .decision-main-v2 .metric span{font-size:10px;letter-spacing:.055em}
html[data-theme="intel"] .decision-main-v2 .metric .value{font-size:17px;line-height:1.25}

/* Why now becomes the primary explanation */
html[data-theme="intel"] .decision-main-v2 .evidence{
  margin-top:12px;
  padding:14px 16px;
  background:#111a20;
  border-left:3px solid #22d27f;
}
html[data-theme="intel"] .decision-main-v2 .evidence strong{font-size:14px}
html[data-theme="intel"] .decision-main-v2 .evidence p{margin:5px 0 0;line-height:1.5}
html[data-theme="intel"] .decision-main-v2 .risk{
  margin-top:10px;
  padding:14px 16px;
  background:rgba(255,148,24,.045);
  border-left:3px solid #ff9418;
}

/* Supporting verification detail */
html[data-theme="intel"] .decision-main-v2 .check{padding:10px 0;font-size:13px}
html[data-theme="intel"] .decision-main-v2 .check:before{font-size:13px}

/* Action panel: calm, deliberate, visually separate from evidence */
html[data-theme="intel"] .decision-side-v2 .eyebrow{margin-bottom:8px}
html[data-theme="intel"] .decision-side-v2 .wallet-state{margin-top:14px;padding:12px 13px}
html[data-theme="intel"] .decision-side-v2 .sandbox-button{min-height:42px}
html[data-theme="intel"] .decision-side-v2 .sandbox-button.primary{font-weight:650}
html[data-theme="intel"] .decision-side-v2 .swap-warning{font-size:12px;line-height:1.45}

/* Reduce visual noise */
html[data-theme="intel"] .card{box-shadow:none}
html[data-theme="intel"] .metric,html[data-theme="intel"] .address,html[data-theme="intel"] .wallet-state{box-shadow:none}
html[data-theme="intel"] footer{font-size:11px;line-height:1.45}

@media(max-width:900px){
  html[data-theme="intel"] .decision-grid-v2{grid-template-columns:1fr !important}
  html[data-theme="intel"] .decision-side-v2{position:static}
  html[data-theme="intel"] .dexsato-evidence-strip{grid-template-columns:repeat(2,minmax(0,1fr))}
  html[data-theme="intel"] .dexsato-evidence-item{border-bottom:1px solid #28313b}
}
@media(max-width:560px){
  html[data-theme="intel"] .dexsato-evidence-strip{grid-template-columns:1fr}
  html[data-theme="intel"] .dexsato-evidence-item{border-right:0}
}
/* Token Workspace v2.0.1 Test Safety Hotfix - no visual change */

/* Token Workspace v2.1 Clean Header - UI only */
html[data-theme="intel"] .hero > div:first-child > .eyebrow{display:none !important}
html[data-theme="intel"] .hero > p{display:none !important}
html[data-theme="intel"] .hero > .status,
html[data-theme="intel"] .hero > .market-status,
html[data-theme="intel"] .hero > [class*="status"]{display:none !important}
html[data-theme="intel"] .hero{display:block !important;padding-top:4px}
html[data-theme="intel"] .hero h1{margin-top:0;margin-bottom:0}
html[data-theme="intel"] .identity > .eyebrow{display:none !important}
html[data-theme="intel"] .identity h2{margin-top:0}
html[data-theme="intel"] .identity{padding-top:18px}

/* Token Header v2.2 Trader Timeframes */
.trader-tf-strip{
  display:grid;
  grid-template-columns:repeat(6,minmax(0,1fr));
  gap:0;
  margin-top:14px;
  width:min(650px,100%);
  border:1px solid var(--line);
  background:var(--panel);
}
.trader-tf-cell{
  min-width:0;
  padding:9px 12px;
  border-right:1px solid var(--line);
}
.trader-tf-cell:last-child{border-right:0}
.trader-tf-cell span{
  display:block;
  color:var(--muted);
  font:600 9px/1.2 var(--ui);
  letter-spacing:.06em;
  text-transform:uppercase;
}
.trader-tf-value{
  display:block;
  margin-top:5px;
  color:var(--text);
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
  font-size:13px;
  font-weight:650;
  font-variant-numeric:tabular-nums lining-nums;
  font-feature-settings:"tnum" 1,"lnum" 1;
  letter-spacing:-.01em;
}
.trader-tf-value.up{color:var(--green)}
.trader-tf-value.down{color:var(--red)}
.trader-tf-value.flat{color:var(--text)}
.trader-tf-value.unavailable{color:var(--muted);font-weight:500}

html[data-theme="intel"] .trader-tf-strip{
  border-color:#303a45;
  background:#0f141a;
}
html[data-theme="intel"] .trader-tf-cell{
  border-right-color:#28313b;
  padding:10px 13px;
}
html[data-theme="intel"] .trader-tf-cell span{
  color:#7f8994;
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
}
html[data-theme="intel"] .trader-tf-value{
  font-family:"Segoe UI Variable Text","Segoe UI",Arial,sans-serif;
  font-size:13px;
}
html[data-theme="intel"] .trader-tf-value.up{color:#22d27f}
html[data-theme="intel"] .trader-tf-value.down{color:#ff5f78}
html[data-theme="intel"] .trader-tf-value.unavailable{color:#69737e}

@media(max-width:700px){
  .trader-tf-strip{grid-template-columns:repeat(3,1fr)}
  .trader-tf-cell:nth-child(3){border-right:0}
  .trader-tf-cell:nth-child(-n+3){border-bottom:1px solid var(--line)}
}

/* Token Header v2.2.2 Robust Hotfix */
html[data-theme="intel"] .hero > div:first-child{
  display:block !important;
  width:100%;
}
html[data-theme="intel"] .hero h1{
  display:block !important;
}
html[data-theme="intel"] .trader-tf-strip{
  display:grid !important;
  margin-top:12px;
}


/* Token Workspace v2.4 Unified Token Card */
.token-overview-card{
  margin-top:22px;padding:22px;border:1px solid var(--line);border-radius:10px;background:var(--panel);
}
.token-overview-main{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:18px;align-items:center}
.token-avatar{width:86px;height:86px;border-radius:50%;display:grid;place-items:center;overflow:hidden;border:2px solid var(--line);background:var(--panel2)}
.token-avatar-image{width:100%;height:100%;object-fit:cover;display:block}
.token-avatar-fallback{font:700 34px/1 var(--display);color:var(--text)}
.token-overview-heading h1{margin:0;font-size:34px;line-height:1.05;letter-spacing:-.025em}
.token-price-row{display:flex;align-items:center;gap:13px;flex-wrap:wrap;margin-top:9px}
.token-price-row>strong{font:700 28px/1.1 var(--display);font-variant-numeric:tabular-nums lining-nums}
.token-change{padding:7px 11px;border-radius:6px;font:700 17px/1 var(--ui);font-variant-numeric:tabular-nums lining-nums;border:1px solid var(--line)}
.token-change.up{color:var(--green);background:rgba(38,212,154,.08);border-color:rgba(38,212,154,.32)}
.token-change.down{color:var(--red);background:rgba(255,86,117,.08);border-color:rgba(255,86,117,.32)}
.token-overview-actions{display:grid;gap:9px;justify-items:stretch;min-width:118px}
.token-live,.token-watch{min-height:39px;padding:8px 12px;border-radius:6px;display:flex;align-items:center;justify-content:center;gap:8px;font:700 12px/1 var(--ui)}
.token-live{color:var(--green);border:1px solid rgba(38,212,154,.32);background:rgba(38,212,154,.06)}
.token-live i{width:8px;height:8px;border-radius:50%;background:currentColor}
.token-live.stored{color:var(--muted);border-color:var(--line);background:transparent}
.token-watch{border:1px solid var(--line);background:transparent;color:var(--muted);cursor:pointer}
.token-watch.active{color:var(--amber);border-color:rgba(255,184,0,.42)}
.token-meta-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:20px;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);color:var(--muted)}
.token-dex{font-weight:700;color:var(--text);text-decoration:none}
a.token-dex:hover{text-decoration:underline}
.token-meta-sep{color:#627184}
.token-age{display:inline-flex;align-items:center;gap:6px}
.token-contract code{color:var(--blue);font:600 13px var(--mono)}
.token-copy{margin-left:-4px}
.token-info-row{display:grid;grid-template-columns:auto repeat(3,minmax(0,1fr));align-items:stretch;margin:15px 0}
.token-info-label{display:flex;align-items:center;padding-right:18px;color:var(--muted);font:700 12px var(--ui);letter-spacing:.08em}
.token-info-link{min-width:0;display:flex;align-items:center;justify-content:center;gap:8px;padding:10px 15px;border-left:1px solid var(--line);color:var(--blue);text-decoration:none;font-weight:650}
.token-info-link b{color:var(--muted);font-size:12px}
.token-info-link.unavailable{color:var(--muted)}
.token-info-link.unavailable small{font-size:10px}
.token-overview-card .trader-tf-strip{width:100%;max-width:none;margin-top:0;border-radius:7px;overflow:hidden}
.token-observation-note{display:flex;align-items:center;gap:8px;margin-top:13px;color:var(--muted);font-size:12px}
.token-observation-note>span{width:18px;height:18px;border:1px solid var(--muted);border-radius:50%;display:grid;place-items:center;font:700 10px var(--ui)}
.token-name-context{display:none}
.hero,.identity{display:none !important}

html[data-theme="intel"] .token-overview-card{background:#0f141a;border-color:#303a45}
html[data-theme="intel"] .token-avatar{background:#090d12;border-color:#48525e}
html[data-theme="intel"] .token-info-link{border-left-color:#28313b}
html[data-theme="intel"] .token-meta-row{border-color:#28313b}

@media(max-width:760px){
  .token-overview-card{padding:16px;margin-top:16px}
  .token-overview-main{grid-template-columns:auto 1fr}
  .token-avatar{width:64px;height:64px}
  .token-overview-heading h1{font-size:27px}
  .token-price-row>strong{font-size:22px}
  .token-change{font-size:14px}
  .token-overview-actions{grid-column:1/-1;grid-template-columns:1fr 1fr;width:100%}
  .token-info-row{grid-template-columns:1fr 1fr}
  .token-info-label{grid-column:1/-1;padding:0 0 8px}
  .token-info-link{border:1px solid var(--line);margin:-1px 0 0 -1px}
}
@media(max-width:430px){
  .token-overview-main{grid-template-columns:1fr}
  .token-avatar{width:58px;height:58px}
  .token-overview-actions{grid-template-columns:1fr}
  .token-info-row{grid-template-columns:1fr}
  .token-info-link{justify-content:flex-start}
}



/* TOKEN_WORKSPACE_V243_FINAL_HEADER_CLEANUP */
.token-overview-card{
  margin-top:16px;
  padding:18px 20px 16px;
}
.token-overview-main{gap:14px}
.token-meta-row{
  margin-top:14px;
  padding:10px 0 11px;
  gap:8px;
}
.token-meta-row .token-info-link{
  display:inline-flex;
  align-items:center;
  justify-content:flex-start;
  gap:5px;
  min-width:auto;
  padding:0;
  border:0 !important;
  font-size:12px;
  font-weight:650;
  white-space:nowrap;
}
.token-meta-row .token-info-link b{font-size:10px}
.token-meta-row .token-info-link.unavailable{display:none}
/* TOKEN_WORKSPACE_V2453_LEAF_AGE_ICON */
.token-age{
  display:inline-flex;
  align-items:center;
  gap:5px;
}
.token-age-leaf{
  width:14px;
  height:14px;
  flex:0 0 14px;
  fill:var(--green);
  opacity:.95;
}

.token-overview-card .trader-tf-strip{margin-top:10px}
.token-observation-note,
.token-info-row,
.token-info-label{display:none !important}
.hero{
  display:none !important;
  margin:0 !important;
  padding:0 !important;
  height:0 !important;
  overflow:hidden !important;
}
.identity{display:none !important}
.token-overview-card ~ .chart-panel{margin-top:14px}

@media(max-width:760px){
  .token-overview-card{padding:15px}
  .token-meta-row{gap:7px}
  .token-meta-row .token-info-link{font-size:11px}
}



/* TOKEN_WORKSPACE_V248_DETERMINISTIC_SOCIAL_LINKS */
.token-social-links{
  display:inline-flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
}
.token-social-links .social-inner-sep{
  margin:0 1px;
}



/* TOKEN_WORKSPACE_V25_MULTITIMEFRAME_CANDLESTICK */
.candlestick-panel{
  margin-top:14px;
  border:1px solid var(--line);
  background:var(--panel);
  overflow:hidden;
}
.candle-timeframe-tabs{
  display:flex;
  align-items:center;
  gap:4px;
  padding:10px 12px;
  border-bottom:1px solid var(--line);
  background:var(--panel);
}
.candle-tf-button{
  min-width:54px;
  height:32px;
  padding:0 12px;
  border:1px solid transparent;
  border-radius:5px;
  background:transparent;
  color:var(--muted);
  font:650 12px/1 var(--ui);
  cursor:pointer;
}
.candle-tf-button:hover{color:var(--text);background:var(--panel2)}
.candle-tf-button.active{
  color:var(--text);
  border-color:var(--line);
  background:var(--panel2);
}
.candlestick-stage{
  position:relative;
  min-height:390px;
  padding:12px;
  background:var(--panel2);
}
.candlestick-chart{
  display:block;
  width:100%;
  height:360px;
  background:var(--panel2);
}
.candlestick-grid{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}
.candlestick-wick{stroke-width:1.4;vector-effect:non-scaling-stroke}
.candlestick-body{vector-effect:non-scaling-stroke}
.candlestick-up{stroke:var(--green);fill:var(--green)}
.candlestick-down{stroke:var(--red);fill:var(--red)}
.candlestick-axis{fill:var(--muted);font:11px var(--ui)}
.candlestick-empty{
  position:absolute;
  inset:12px;
  display:grid;
  place-items:center;
  color:var(--muted);
  font-size:13px;
}
.candlestick-empty[hidden]{display:none}
html[data-theme="intel"] .candlestick-panel{border-color:#303a45;background:#0f141a}
html[data-theme="intel"] .candle-timeframe-tabs{border-bottom-color:#28313b;background:#0f141a}
html[data-theme="intel"] .candle-tf-button.active{background:#151c24;border-color:#3a4652}
html[data-theme="intel"] .candlestick-stage,
html[data-theme="intel"] .candlestick-chart{background:#0d1218}
@media(max-width:700px){
  .candle-timeframe-tabs{overflow-x:auto}
  .candle-tf-button{flex:0 0 auto}
  .candlestick-stage{min-height:310px}
  .candlestick-chart{height:280px}
}



/* CHART_V21_INTERACTIVE_TRADING_CHART */
.candle-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);background:var(--panel)}
.candle-toolbar .candle-timeframe-tabs{border-bottom:0;min-width:0;flex:1 1 auto}
.candle-toolbar-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:8px 12px 8px 0;min-width:0}
.candle-ohlc{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:8px 12px;color:var(--muted);font:600 10px/1.2 var(--mono);font-variant-numeric:tabular-nums}
.candle-ohlc span{white-space:nowrap}.candle-ohlc b{color:var(--text);font-weight:700}
.candle-reset{flex:0 0 auto;height:30px;padding:0 10px;border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--muted);font:650 11px/1 var(--ui);cursor:pointer}
.candle-reset:hover{background:var(--panel2);color:var(--text)}
.candle-reset:focus-visible,.candlestick-chart:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.candlestick-stage{min-height:450px;user-select:none}.candlestick-chart{height:420px;touch-action:pan-y;cursor:crosshair}
.candlestick-volume{opacity:.5;vector-effect:non-scaling-stroke}
.candlestick-axis-line{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}
.candlestick-crosshair{stroke:#788391;stroke-width:1;stroke-dasharray:4 4;vector-effect:non-scaling-stroke;pointer-events:none}
.candlestick-price-line{stroke:var(--cyan);stroke-width:1;stroke-dasharray:4 3;vector-effect:non-scaling-stroke}
.candlestick-price-tag{fill:var(--cyan)}.candlestick-price-tag-text{fill:#071018;font:700 10px var(--mono)}
.candlestick-axis-label,.candlestick-time-label{fill:var(--muted);font:10px var(--mono)}
.candlestick-cross-label{fill:var(--panel);stroke:var(--line);stroke-width:1}.candlestick-cross-label-text{fill:var(--text);font:10px var(--mono)}
html[data-theme="intel"] .candle-toolbar{border-bottom-color:#28313b;background:#0f141a}
html[data-theme="intel"] .candlestick-crosshair{stroke:#6f7985}
html[data-theme="intel"] .candlestick-price-line{stroke:#ff9418}
html[data-theme="intel"] .candlestick-price-tag{fill:#ff9418}
@media(max-width:900px){.candle-toolbar{align-items:stretch;flex-direction:column;gap:0}.candle-toolbar-actions{justify-content:space-between;padding:8px 12px;border-top:1px solid var(--line)}.candle-ohlc{justify-content:flex-start}}
@media(max-width:560px){.candle-toolbar-actions{align-items:flex-start;flex-direction:column}.candle-ohlc{gap:6px 10px}.candlestick-stage{min-height:350px}.candlestick-chart{height:330px}}



/* CHART_V22_LIVE_CANDLE */
/* CHART_V23_TRADE_OVERLAY */
.candlestick-trade-marker{vector-effect:non-scaling-stroke;pointer-events:none}
.candlestick-trade-marker.buy{fill:var(--green);stroke:var(--panel2);stroke-width:1.4}
.candlestick-trade-marker.sell{fill:var(--red);stroke:var(--panel2);stroke-width:1.4}
.candlestick-trade-marker.large{stroke-width:1.8}
/* CHART_V24_TRADE_SIZE_INTELLIGENCE */
.candlestick-trade-marker.size-small{opacity:.62}
.candlestick-trade-marker.size-medium{opacity:.84;stroke-width:1.6}
.candlestick-trade-marker.size-large{opacity:1;stroke-width:2.2}
.candlestick-trade-count{
  fill:var(--text);
  stroke:var(--panel2);
  stroke-width:3px;
  paint-order:stroke;
  font:700 9px var(--mono);
  pointer-events:none;
}
.candlestick-trade-hit{fill:transparent;cursor:crosshair}
.candlestick-trade-tooltip{
  position:absolute;
  z-index:5;
  min-width:132px;
  max-width:220px;
  padding:7px 9px;
  border:1px solid var(--line);
  border-radius:5px;
  background:var(--panel);
  color:var(--text);
  box-shadow:0 8px 24px rgba(0,0,0,.28);
  font:10px/1.45 var(--mono);
  pointer-events:none;
}
.candlestick-trade-tooltip b{display:block;margin-bottom:2px}
.candlestick-trade-tooltip.buy b{color:var(--green)}
.candlestick-trade-tooltip.sell b{color:var(--red)}
.candlestick-trade-tooltip[hidden]{display:none}
.candle-live-state{display:inline-flex;align-items:center;gap:6px;color:var(--green);font:700 10px/1 var(--mono);letter-spacing:.04em}
.candle-live-state i{width:6px;height:6px;border-radius:50%;background:currentColor}
.candle-live-state.stale{color:var(--amber)}



/* TRANSACTIONS_FEED_V121_ROBUST_UI_MOUNT */
/* TRANSACTIONS_FEED_V1221_UI_SCOPE_FIX */
.transactions-panel{margin-top:14px;border:1px solid var(--line);background:var(--panel);overflow:hidden}
.transactions-head{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:48px;padding:0 14px;border-bottom:1px solid var(--line)}
.transactions-head h2{margin:0;font-size:15px;line-height:1.2}
.transactions-state{color:var(--muted);font:700 10px/1 var(--mono);letter-spacing:.04em;text-transform:uppercase}
.transactions-state.ready{color:var(--green)}
.transactions-state.unavailable{color:var(--amber)}
/* TRANSACTIONS_FEED_V13_LIVE_POLLING */
.transactions-state.live{color:var(--green)}
.transactions-state.stale{color:var(--amber)}

/* TRANSACTIONS_FEED_V15_FLOW_INTELLIGENCE */
/* TRANSACTIONS_FEED_V151_FLOW_VISUAL_FINAL */
.transactions-flow-meter{
  height:3px;
  margin-top:7px;
  overflow:hidden;
  border-radius:999px;
  background:rgba(145,168,197,.12);
}
.transactions-flow-meter i{
  display:block;
  width:0;
  height:100%;
  border-radius:inherit;
  transition:width .28s ease;
}
.transactions-flow-item.buy .transactions-flow-meter i{background:var(--green)}
.transactions-flow-item.sell .transactions-flow-meter i{background:var(--red)}
.flow-largest-tone.buy{color:var(--green)!important}
.flow-largest-tone.sell{color:var(--red)!important}
.transactions-flow-bias{
  display:inline-flex!important;
  align-items:center;
  gap:5px;
}
.transactions-flow-bias-dot{
  width:6px;
  height:6px;
  flex:0 0 6px;
  border-radius:50%;
  background:var(--muted);
}
.transactions-flow-item.net.positive .transactions-flow-bias-dot{background:var(--green)}
.transactions-flow-item.net.negative .transactions-flow-bias-dot{background:var(--red)}
@media (prefers-reduced-motion:reduce){
  .transactions-flow-meter i{transition:none}
}

/* TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI */
.market-activity{border-top:1px solid var(--line);background:var(--panel)}
.market-activity-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid var(--line)}
.market-activity-head span{display:block;color:var(--text);font:750 12px/1.25 var(--mono);letter-spacing:.06em;text-transform:uppercase}
.market-activity-head small{display:block;margin-top:4px;color:var(--muted);font:11px/1.3 var(--ui)}
.recent-flow-label span{display:block;color:var(--text);font:750 10px/1.2 var(--mono);letter-spacing:.06em;text-transform:uppercase}
.recent-flow-label small{display:block;margin-top:3px;color:var(--muted);font:10px/1.2 var(--ui)}
.market-activity-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.market-activity-table{width:100%;min-width:690px;border-collapse:collapse;table-layout:fixed;font-variant-numeric:tabular-nums lining-nums}
.market-activity-table th,.market-activity-table td{padding:10px 12px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-align:right;font:12px/1.35 var(--mono);white-space:nowrap}
.market-activity-table th:last-child,.market-activity-table td:last-child{border-right:0}.market-activity-table tbody tr:last-child td{border-bottom:0}
.market-activity-table th{color:var(--muted);background:var(--panel2);font-size:10px;letter-spacing:.05em;text-transform:uppercase}
.market-activity-table th:first-child,.market-activity-table td:first-child{text-align:left;width:128px}
.market-activity-table td:first-child{color:var(--muted);font-weight:700;text-transform:uppercase;font-size:10px;letter-spacing:.04em}
.market-activity-table tr.activity-buys td:not(:first-child),.market-activity-table tr.activity-buyers td:not(:first-child),.market-activity-table tr.activity-buy-percent td:not(:first-child){color:var(--green)}
.market-activity-table tr.activity-sells td:not(:first-child),.market-activity-table tr.activity-sellers td:not(:first-child){color:var(--red)}
.market-activity-table .activity-unavailable{color:var(--muted)!important}.recent-flow-label{padding:9px 14px 7px;background:var(--panel2);border-bottom:1px solid var(--line)}
html[data-theme="intel"] .market-activity{background:#0f141a;border-bottom-color:#28313b}html[data-theme="intel"] .market-activity-table th{background:#121820}
html[data-theme="intel"] .market-activity-table th,html[data-theme="intel"] .market-activity-table td{border-color:#222b35}
@media(max-width:700px){.market-activity-head{align-items:flex-start;flex-direction:column}.market-activity-table{min-width:650px}}

.transactions-flow{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  border-bottom:1px solid var(--line);
  background:var(--panel2);
}
.transactions-flow-item{
  min-width:0;
  padding:10px 14px;
  border-right:1px solid var(--line);
}
.transactions-flow-item:last-child{border-right:0}
.transactions-flow-item span{
  display:block;
  color:var(--muted);
  font:700 9px/1.2 var(--mono);
  letter-spacing:.05em;
  text-transform:uppercase;
}
.transactions-flow-item b{
  display:block;
  margin-top:5px;
  color:var(--text);
  font:700 13px/1.2 var(--mono);
  font-variant-numeric:tabular-nums lining-nums;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.transactions-flow-item small{
  display:block;
  margin-top:4px;
  color:var(--muted);
  font:10px/1.2 var(--mono);
}
.transactions-flow-item.buy b{color:var(--green)}
.transactions-flow-item.sell b{color:var(--red)}
.transactions-flow-item.net.positive b{color:var(--green)}
.transactions-flow-item.net.negative b{color:var(--red)}
.transactions-flow-item.net.flat b{color:var(--muted)}
html[data-theme="intel"] .transactions-flow{
  background:#121820;
  border-bottom-color:#28313b;
}
html[data-theme="intel"] .transactions-flow-item{border-right-color:#28313b}
@media(max-width:700px){
  .transactions-flow{grid-template-columns:repeat(2,minmax(0,1fr))}
  .transactions-flow-item:nth-child(2){border-right:0}
  .transactions-flow-item:nth-child(-n+2){border-bottom:1px solid var(--line)}
}

/* TRANSACTIONS_FEED_V122_COMPACT_LIVE_TABLE */
.transactions-table-wrap{max-height:none;overflow-x:auto;overflow-y:visible;-webkit-overflow-scrolling:touch;scrollbar-gutter:auto}
.transactions-table{width:100%;min-width:850px;border-collapse:separate;border-spacing:0;table-layout:fixed;font-variant-numeric:tabular-nums lining-nums}
.transactions-table th,.transactions-table td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.transactions-table th{position:sticky;top:0;z-index:2;color:var(--muted);background:var(--panel2);box-shadow:0 1px 0 var(--line);font:700 9px/1.2 var(--mono);letter-spacing:.05em;text-transform:uppercase}
.transactions-table td{color:var(--text);font:12px/1.3 var(--mono)}
.transactions-table th:first-child,.transactions-table td:first-child,.transactions-table th:nth-child(2),.transactions-table td:nth-child(2){text-align:left}
.transactions-table tbody tr:last-child td{border-bottom:0}
.transaction-side{display:inline-flex;align-items:center;justify-content:center;min-width:42px;padding:4px 7px;border-radius:4px;font:800 10px/1 var(--mono)}
.transaction-side.buy{color:var(--green);background:rgba(38,212,154,.08)}
.transaction-side.sell{color:var(--red);background:rgba(255,86,117,.08)}
.transaction-trader,.transaction-tx{color:var(--blue);text-decoration:none}
.transaction-tx:hover{text-decoration:underline}
.transactions-placeholder td,.transactions-empty td,.transactions-error td{padding:22px 14px;text-align:center!important;color:var(--muted);font-family:var(--ui)}
.transactions-error td{color:var(--amber)}
html[data-theme="intel"] .transactions-panel{border-color:#303a45;background:#0f141a}
html[data-theme="intel"] .transactions-head{border-bottom-color:#28313b}
html[data-theme="intel"] .transactions-table th{background:#121820}
html[data-theme="intel"] .transactions-table th,html[data-theme="intel"] .transactions-table td{border-bottom-color:#222b35}
@media(max-width:700px){.transactions-table-wrap{max-height:none}}

/* TW-DEX-05 — Flow, Recent Trades and Market Activity presentation. */
.transactions-panel{display:grid;gap:12px;margin-top:14px;border:0;background:transparent;overflow:visible}
.recent-flow-label{display:flex;align-items:end;justify-content:space-between;gap:10px;padding:0 2px;background:transparent;border:0}.recent-flow-label span{font-size:11px}.recent-flow-label small{margin:0;text-align:right}
.transactions-flow{grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;border:0;background:transparent}
.transactions-flow-item{min-height:86px;padding:13px 14px;border:1px solid #2a3948!important;border-radius:10px;background:linear-gradient(155deg,#111b25,#0d151e);box-shadow:0 8px 22px rgba(0,0,0,.12)}
.transactions-flow-item span{font-weight:750}.transactions-flow-item b{margin-top:7px;font:800 16px/1.15 var(--mono);letter-spacing:-.015em}.transactions-flow-item small{margin-top:6px;font-weight:700}.transactions-flow-meter{margin-top:9px;height:3px}
.transactions-detail-grid{display:grid;grid-template-columns:minmax(0,1.32fr) minmax(340px,.88fr);gap:10px;align-items:start}
.recent-trades-card,.market-activity{min-width:0;overflow:hidden;border:1px solid #2a3948;border-radius:11px;background:var(--panel);box-shadow:0 8px 24px rgba(0,0,0,.12)}
.transactions-head,.market-activity-head{min-height:48px;padding:0 14px;border-bottom:1px solid var(--line)}.transactions-head h2,.market-activity-head span{font:800 13px/1.2 var(--mono);letter-spacing:.045em;text-transform:uppercase}.market-activity-head>small{margin:0;text-align:right;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.transactions-state{display:inline-flex;align-items:center;gap:5px;font-weight:800}.transactions-state:before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}
.transactions-table{min-width:640px}.transactions-table th,.transactions-table td{padding:10px 11px}.transactions-table td{font-weight:650}.transactions-table th:nth-child(6),.transactions-table td:nth-child(6){display:none}.transactions-table th:first-child,.transactions-table td:first-child{width:16%}.transactions-table th:nth-child(2),.transactions-table td:nth-child(2){width:13%}.transactions-table th:nth-child(3),.transactions-table td:nth-child(3){width:20%}.transactions-table th:nth-child(4),.transactions-table td:nth-child(4){width:22%}.transactions-table th:nth-child(5),.transactions-table td:nth-child(5){width:17%}.transactions-table th:nth-child(7),.transactions-table td:nth-child(7){width:12%}.transactions-table tbody tr:hover{background:rgba(76,244,214,.025)}
.market-activity{border-top:1px solid #2a3948}.market-activity-table{min-width:470px}.market-activity-table th,.market-activity-table td{padding:11px 12px;font-weight:700}.market-activity-table th:first-child,.market-activity-table td:first-child{width:20%}.market-activity-table td.activity-buys{color:var(--green)}.market-activity-table td.activity-sells{color:var(--red)}.market-activity-table td.activity-volume{font-weight:800}
html[data-theme="intel"] .transactions-panel,html[data-theme="intel"] .transactions-flow{background:transparent}html[data-theme="intel"] .recent-trades-card,html[data-theme="intel"] .market-activity{border-color:#303a45;background:#0f141a}
@media(max-width:980px){.transactions-detail-grid{grid-template-columns:1fr}}
@media(max-width:700px){.transactions-flow{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.transactions-flow-item:nth-child(-n+2){border-bottom:1px solid #2a3948}.recent-flow-label{align-items:flex-start;flex-direction:column}.recent-flow-label small{text-align:left}.recent-trades-card,.market-activity{border-radius:10px}}

/* TW-DEX-05A — Market Activity visual polish. */
.market-activity{border-color:#1d2733;background:#0e141c}
.market-activity-head{border-bottom-color:#1d2733}.market-activity-head span{color:#e7edf4;font-weight:800}.market-activity-head>small{color:#7c8ca0;font-weight:750}
.market-activity-wrap{overflow-x:hidden}
.market-activity-table{width:100%;min-width:0;background:#10171f}
.market-activity-table th,.market-activity-table td{padding:11px 10px;border-right:0!important;border-bottom:0!important;background:transparent!important;font-weight:750}
.market-activity-table th{color:#45505f;font-weight:800}.market-activity-table td{color:#e7edf4}.market-activity-table td:first-child{color:#7c8ca0;font-weight:800}.market-activity-table td.activity-buys{color:#4cf4d6}.market-activity-table td.activity-sells{color:#ff5c7a}.market-activity-table td.activity-total,.market-activity-table td.activity-volume{color:#e7edf4;font-weight:800}
.market-activity-table tbody tr:hover{background:rgba(76,244,214,.035)}
html[data-theme="intel"] .market-activity{border-color:#1d2733;background:#0e141c}html[data-theme="intel"] .market-activity-table{background:#10171f}
@media(max-width:700px){.market-activity-table{min-width:0}.market-activity-head{align-items:center;flex-direction:row}}

/* TW-DEX-05B — Recent Trades Visual Alignment
   UI only: align Recent Trades with TW-DEX-05A Market Activity. */
.recent-trades-card{border-color:#1d2733;background:#0e141c}
.transactions-head{border-bottom-color:#1d2733}
.transactions-head h2{color:#e7edf4;font:800 13px/1.2 var(--mono);letter-spacing:.045em;text-transform:uppercase}
.transactions-state{color:#7c8ca0;font-weight:750}
.transactions-state.ready,.transactions-state.live{color:#4cf4d6}
.transactions-state.stale,.transactions-state.unavailable{color:#7c8ca0}
.transactions-table-wrap{overflow-x:hidden;background:#10171f}
.transactions-table{width:100%;min-width:0;background:#10171f;border-collapse:collapse}
.transactions-table th,.transactions-table td{
  padding:11px 10px;
  border-right:0!important;
  border-bottom:0!important;
  background:transparent!important;
  font:750 12px/1.35 var(--mono);
}
.transactions-table th{color:#45505f;font-size:10px;font-weight:800;letter-spacing:.05em;text-transform:uppercase}
.transactions-table td{color:#e7edf4}
.transactions-table tbody tr:hover{background:rgba(76,244,214,.035)}
.transactions-table .transaction-side{font-weight:800}
.transactions-table .transaction-side.buy{color:#4cf4d6;background:rgba(76,244,214,.07)}
.transactions-table .transaction-side.sell{color:#ff5c7a;background:rgba(255,92,122,.07)}
.transactions-table .transaction-trader,.transactions-table .transaction-tx{color:#7c8ca0;font-weight:750}
.transactions-table .transaction-trader:hover,.transactions-table .transaction-tx:hover{color:#4cf4d6}
.transactions-table .transactions-placeholder td,.transactions-table .transactions-empty td{color:#7c8ca0}
.transactions-table .transactions-error td{color:#ff5c7a}
html[data-theme="intel"] .recent-trades-card{border-color:#1d2733;background:#0e141c}
html[data-theme="intel"] .transactions-table{background:#10171f}
@media(max-width:700px){.transactions-table{min-width:0}}

/* TW-DEX-06 — Token Intelligence + Qualification
   UI-only evidence hierarchy. Existing observations, qualification facts and data semantics remain unchanged. */

/* Left rail: verified observation card */
.token-observation-v28{
  padding:0!important;
  border-color:#1D2733!important;
  border-radius:10px;
  background:#0E141C!important;
}
.token-observation-v28 .workspace-rail-head{
  padding:14px 15px 12px!important;
  border-bottom:1px solid #1D2733!important;
  background:#0E141C;
}
.token-observation-v28 .workspace-rail-head h2{
  color:#E7EDF4;
  font:800 12px/1.25 var(--mono);
  letter-spacing:.055em;
  text-transform:uppercase;
}
.token-observation-v28 .workspace-rail-head small{
  color:#7C8CA0;
  font:500 10px/1.3 var(--ui);
}
.token-observation-rows{
  border-top:0!important;
  background:#10171F;
}
.token-observation-row{
  padding:11px 14px!important;
  border-bottom:1px solid #1D2733!important;
}
.token-observation-row span{
  color:#45505F!important;
  font:700 10px/1.35 var(--mono);
  letter-spacing:.025em;
}
.token-observation-value{
  color:#E7EDF4;
  font:750 11px/1.35 var(--mono)!important;
  font-variant-numeric:tabular-nums lining-nums;
}
.token-observation-value.up,
.token-observation-value.verified{color:#4CF4D6!important}
.token-observation-value.down{color:#FF5C7A!important}
.token-observation-note{
  margin:0!important;
  padding:11px 14px!important;
  border-left:0!important;
  border-top:1px solid #1D2733;
  background:#0E141C!important;
  color:#7C8CA0!important;
  font:500 10px/1.45 var(--ui)!important;
}

/* Right rail: Market Snapshot becomes a compact intelligence stack. */
.market-snapshot-v26{
  padding:0!important;
  overflow:hidden;
  border-color:#1D2733!important;
  border-radius:10px;
  background:#0E141C!important;
}
.market-snapshot-v26>h3{
  margin:0!important;
  padding:14px 15px 12px;
  border-bottom:1px solid #1D2733;
  color:#E7EDF4;
  font:800 12px/1.25 var(--mono)!important;
  letter-spacing:.055em;
  text-transform:uppercase;
}
.market-snapshot-v26 .metrics{
  gap:0!important;
  background:#10171F;
}
.market-snapshot-v26 .metric{
  min-height:62px!important;
  padding:11px 12px!important;
  border:0!important;
  border-right:1px solid #1D2733!important;
  border-bottom:1px solid #1D2733!important;
  background:#10171F!important;
}
.market-snapshot-v26 .metric:nth-child(2n){border-right:0!important}
.market-snapshot-v26 .metric span{
  color:#45505F!important;
  font:700 9px/1.25 var(--mono)!important;
  letter-spacing:.04em!important;
  text-transform:uppercase;
}
.market-snapshot-v26 .metric .value{
  margin-top:5px;
  color:#E7EDF4;
  font:750 13px/1.25 var(--mono)!important;
}
.market-snapshot-v26 .metric .value.up{color:#4CF4D6!important}
.market-snapshot-v26 .metric .value.down{color:#FF5C7A!important}

/* Why this token appeared: positive evidence, not a recommendation. */
.market-snapshot-v26 .evidence{
  margin:0!important;
  padding:13px 14px!important;
  border-left:0!important;
  border-bottom:1px solid #1D2733;
  background:#10171F!important;
  color:#7C8CA0;
  font:500 11px/1.5 var(--ui);
}
.market-snapshot-v26 .evidence strong{
  display:block;
  margin:0 0 5px!important;
  color:#E7EDF4;
  font:800 10px/1.3 var(--mono);
  letter-spacing:.04em;
  text-transform:uppercase;
}
.market-snapshot-v26 .evidence strong:before{
  content:"";
  display:inline-block;
  width:6px;height:6px;
  margin-right:7px;
  border-radius:50%;
  background:#4CF4D6;
  vertical-align:1px;
}

/* Risk stays visually distinct but calm. */
.market-snapshot-v26 .risk{
  margin:0!important;
  padding:13px 14px!important;
  border-left:0!important;
  border-bottom:1px solid #1D2733;
  background:#0E141C!important;
}
.market-snapshot-v26 .risk strong{
  color:#FF5C7A!important;
  font:800 10px/1.3 var(--mono);
  letter-spacing:.04em;
  text-transform:uppercase;
}
.market-snapshot-v26 .risk p{
  margin:5px 0 0;
  color:#7C8CA0;
  font:500 10px/1.5 var(--ui);
}

/* Qualification: evidence-first state, existing text/checks only. */
.market-snapshot-v26 .qualification-vp0d3{
  margin:0!important;
  padding:13px 14px 14px;
  background:#10171F;
}
.market-snapshot-v26 .qualification-vp0d3>.eyebrow{
  color:#45505F!important;
  font:800 9px/1.25 var(--mono)!important;
  letter-spacing:.06em!important;
}
.market-snapshot-v26 .qualification-vp0d3 h3{
  margin:6px 0 8px!important;
  color:#E7EDF4;
  font:750 13px/1.3 var(--mono)!important;
}
.market-snapshot-v26 .qualification-reason{
  margin:0 0 11px!important;
  padding:10px 11px!important;
  border:1px solid #1D2733!important;
  border-left:2px solid #FF5C7A!important;
  border-radius:6px;
  background:#0E141C!important;
  color:#7C8CA0!important;
  font:500 10px/1.5 var(--ui)!important;
}
.market-snapshot-v26 .qualification-vp0d3.qualified .qualification-reason{
  border-left-color:#4CF4D6!important;
}
.market-snapshot-v26 .qualification-history-label{
  margin:0!important;
  padding:8px 0 5px;
  color:#45505F!important;
  border-top:1px solid #1D2733;
}
.market-snapshot-v26 .qualification-vp0d3 .check{
  position:relative;
  padding:8px 0 8px 16px!important;
  border-top:1px solid #1D2733!important;
  color:#E7EDF4;
  font:650 10px/1.35 var(--ui)!important;
}
.market-snapshot-v26 .qualification-vp0d3 .check:before{
  position:absolute;
  left:0;
  margin:0!important;
  color:#4CF4D6!important;
  font-size:10px!important;
}
.market-snapshot-v26 .qualification-vp0d3 .source{
  margin:9px 0 0!important;
  padding:9px 0 0!important;
  border-top:1px solid #1D2733!important;
  color:#7C8CA0;
  font:500 9px/1.5 var(--mono);
}

/* Theme override: retain the official DEX Intelligence palette. */
html[data-theme="intel"] .token-observation-v28,
html[data-theme="intel"] .market-snapshot-v26{border-color:#1D2733!important;background:#0E141C!important}
html[data-theme="intel"] .token-observation-rows,
html[data-theme="intel"] .market-snapshot-v26 .metrics,
html[data-theme="intel"] .market-snapshot-v26 .qualification-vp0d3{background:#10171F!important}

@media(max-width:620px){
  .market-snapshot-v26 .metrics{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}

/* TW-DEX-06A — Token Intelligence & Qualification Relocation
   UI-only relocation. Two independent rounded cards under Jupiter. */
.workspace-right-v26>.token-observation-v28,
.workspace-right-v26>.qualification-vp0d3{
  margin:0!important;
  border:1px solid #1D2733!important;
  border-radius:10px!important;
  overflow:hidden;
  background:#0E141C!important;
}
.workspace-right-v26>.token-observation-v28 .workspace-rail-head{
  background:#0E141C!important;
}
.workspace-right-v26>.qualification-vp0d3{
  padding:0!important;
}
.workspace-right-v26>.qualification-vp0d3>.eyebrow{
  display:block;
  margin:0!important;
  padding:14px 15px 12px;
  border-bottom:1px solid #1D2733;
  color:#E7EDF4!important;
  background:#0E141C;
  font:800 12px/1.25 var(--mono)!important;
  letter-spacing:.055em!important;
  text-transform:uppercase;
}
.workspace-right-v26>.qualification-vp0d3 h3{
  margin:0!important;
  padding:12px 14px 5px!important;
  color:#E7EDF4;
  background:#10171F;
  font:750 13px/1.3 var(--mono)!important;
}
.workspace-right-v26>.qualification-vp0d3 .qualification-reason{
  margin:0 14px 11px!important;
}
.workspace-right-v26>.qualification-vp0d3 .qualification-history-label{
  padding:9px 14px 6px!important;
  background:#10171F;
}
.workspace-right-v26>.qualification-vp0d3 .check{
  margin:0 14px;
}
.workspace-right-v26>.qualification-vp0d3 .source{
  margin:9px 14px 0!important;
  padding:9px 0 12px!important;
}
html[data-theme="intel"] .workspace-right-v26>.token-observation-v28,
html[data-theme="intel"] .workspace-right-v26>.qualification-vp0d3{
  border-color:#1D2733!important;
  background:#0E141C!important;
}

/* TW-DEX-06C — Market Snapshot Consolidation
   UI-only: preserve Market Snapshot markup/data, hide the card for now. */
.workspace-right-v26>.market-snapshot-v26{
  display:none!important;
}

/* TW-DEX-06D — Card Divider & Qualification Alignment
   UI-only polish: keep rounded outer cards, remove internal dividers,
   align Qualification typography with Token Intelligence, move checks right. */
/* TW-DEX-06E — Qualification Visual Polish
   Qualification-only refinement. TOKEN INTELLIGENCE intentionally untouched. */
.workspace-right-v26>.qualification-vp0d3{
  background:#0E141C!important;
}
.workspace-right-v26>.qualification-vp0d3>.eyebrow{
  padding:14px 15px 10px!important;
}
.workspace-right-v26>.qualification-vp0d3 .qualification-history-label{
  display:block;
  padding:10px 14px 7px!important;
  color:#7C8CA0!important;
  font:700 10px/1.35 var(--mono)!important;
  letter-spacing:.035em!important;
  text-transform:uppercase;
}
.workspace-right-v26>.qualification-vp0d3 .check{
  position:relative;
  display:flex!important;
  align-items:center!important;
  justify-content:space-between!important;
  min-height:31px;
  margin:0!important;
  padding:7px 32px 7px 14px!important;
  color:#7C8CA0!important;
  font:650 10px/1.4 var(--mono)!important;
  letter-spacing:.01em!important;
}
.workspace-right-v26>.qualification-vp0d3 .check:before{
  position:absolute!important;
  left:auto!important;
  right:14px!important;
  top:50%!important;
  transform:translateY(-50%)!important;
  margin:0!important;
  color:#4CF4D6!important;
  font-size:11px!important;
  line-height:1!important;
}
.workspace-right-v26>.qualification-vp0d3 .source{
  margin:8px 14px 0!important;
  padding:7px 0 12px!important;
  color:#7C8CA0!important;
  font:500 10px/1.5 var(--mono)!important;
  letter-spacing:.005em!important;
}


/* TOKEN INTELLIGENCE: remove internal separator lines only. */
.workspace-right-v26>.token-observation-v28 .workspace-rail-head{
  border-bottom:0!important;
}
.workspace-right-v26>.token-observation-v28 .token-observation-row{
  border-bottom:0!important;
}
.workspace-right-v26>.token-observation-v28 .token-observation-note{
  border-top:0!important;
}

/* QUALIFICATION: remove internal separator lines only. */
.workspace-right-v26>.qualification-vp0d3>.eyebrow,
.workspace-right-v26>.qualification-vp0d3 .qualification-history-label,
.workspace-right-v26>.qualification-vp0d3 .check,
.workspace-right-v26>.qualification-vp0d3 .source{
  border-top:0!important;
  border-bottom:0!important;
}

/* Match Token Intelligence text hierarchy. */
.workspace-right-v26>.qualification-vp0d3 .qualification-history-label{
  color:#45505F!important;
  font:700 10px/1.35 var(--mono)!important;
  letter-spacing:.025em!important;
}
.workspace-right-v26>.qualification-vp0d3 .check{
  position:relative;
  margin:0!important;
  padding:9px 34px 9px 14px!important;
  color:#45505F!important;
  font:700 10px/1.35 var(--mono)!important;
  letter-spacing:.025em!important;
}
.workspace-right-v26>.qualification-vp0d3 .check:before{
  left:auto!important;
  right:14px!important;
  top:50%!important;
  transform:translateY(-50%);
  margin:0!important;
  color:#4CF4D6!important;
}
.workspace-right-v26>.qualification-vp0d3 .source{
  margin:5px 14px 0!important;
  padding:8px 0 12px!important;
  color:#7C8CA0!important;
  font:500 10px/1.45 var(--mono)!important;
}

/* TW-DEX-06B — Qualification Status Cleanup
   UI-only: hide current-cycle status/reason copy, keep all qualification evidence/checks/timestamps. */
.workspace-right-v26>.qualification-vp0d3>h3,
.workspace-right-v26>.qualification-vp0d3>.qualification-reason{
  display:none!important;
}
.workspace-right-v26>.qualification-vp0d3 .qualification-history-label{
  border-top:0!important;
  padding-top:11px!important;
}



/* TW-DEX-07A — Token List Tabs & Header
   UI-only. Existing discovery feed, current-token-first ordering, links and search behavior remain unchanged. */
.workspace-left-v26>.token-list-v07a{
  border:1px solid #1D2733!important;
  border-radius:10px!important;
  overflow:hidden;
  background:#0E141C!important;
}
.workspace-left-v26>.token-list-v07a .token-list-head-v07a{
  padding:14px 14px 8px!important;
  border-bottom:0!important;
  align-items:center;
  background:#0E141C!important;
}
.workspace-left-v26>.token-list-v07a .token-list-head-v07a h2{
  color:#E7EDF4!important;
  font:800 12px/1.25 var(--mono)!important;
  letter-spacing:.055em!important;
  text-transform:none!important;
}
.token-list-chain-v07a{
  color:#7C8CA0;
  font:700 10px/1.25 var(--mono);
  letter-spacing:.055em;
}
.token-list-tabs-v07a{
  display:flex;
  align-items:center;
  gap:6px;
  padding:0 14px 10px;
  background:#0E141C;
}
.token-list-tab-v07a{
  appearance:none;
  min-height:27px;
  padding:5px 10px;
  border:1px solid #1D2733;
  border-radius:4px;
  background:#10171F;
  color:#7C8CA0;
  font:700 9px/1.2 var(--mono);
  letter-spacing:.025em;
  cursor:default;
}
.token-list-tab-v07a.active{
  border-color:#4CF4D6;
  background:rgba(76,244,214,.055);
  color:#4CF4D6;
}
.workspace-left-v26>.token-list-v07a .coin-list-search{
  padding:0 14px 10px!important;
  background:#0E141C;
}
.workspace-left-v26>.token-list-v07a .coin-list-search input{
  border:1px solid #1D2733!important;
  border-radius:6px!important;
  background:#10171F!important;
  color:#E7EDF4!important;
  font:500 10px/1.35 var(--mono)!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-search input::placeholder{
  color:#45505F;
}
.workspace-left-v26>.token-list-v07a .coin-list-rows{
  background:#10171F;
}
.workspace-left-v26>.token-list-v07a .coin-list-row{
  border-top:1px solid #1D2733!important;
  background:#10171F;
  color:#E7EDF4!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-row:hover{
  background:rgba(76,244,214,.035)!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-row.active{
  background:rgba(76,244,214,.045)!important;
  box-shadow:inset 2px 0 #4CF4D6!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-avatar{
  border-color:#1D2733!important;
  background:#0E141C!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-identity strong{
  color:#E7EDF4!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-identity small{
  color:#7C8CA0!important;
}
.workspace-left-v26>.token-list-v07a .coin-list-change.up{color:#4CF4D6!important}
.workspace-left-v26>.token-list-v07a .coin-list-change.down{color:#FF5C7A!important}
.workspace-left-v26>.token-list-v07a .coin-list-change.unavailable{color:#7C8CA0!important}
html[data-theme="intel"] .workspace-left-v26>.token-list-v07a{
  border-color:#1D2733!important;
  background:#0E141C!important;
}

/* TW-DEX-07B — Header Connect Wallet
   Header-only presentation. Existing Jupiter wallet control remains the source action. */
.tw-dex-topbar .tw-header-wallet-v07b{
  appearance:none;
  min-height:38px;
  padding:9px 16px;
  border:1px solid #4CF4D6;
  border-radius:8px;
  background:#4CF4D6;
  color:#080B10;
  font:800 11px/1.2 var(--ui);
  letter-spacing:.01em;
  cursor:pointer;
}
.tw-dex-topbar .tw-header-wallet-v07b:hover{
  filter:brightness(.96);
}
.tw-dex-topbar .tw-header-wallet-v07b:focus-visible{
  outline:2px solid #E7EDF4;
  outline-offset:2px;
}

/* TW-DEX-07C — Header Search & Gas Indicator
   Header-only presentation. Search and gas are intentionally non-operational placeholders for now. */
.tw-dex-topbar{
  gap:18px;
}
.tw-header-tools-v07c{
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:10px;
  flex:1 1 auto;
  min-width:0;
}
.tw-header-search-v07c{
  position:relative;
  display:flex;
  align-items:center;
  width:min(520px,46vw);
  min-width:220px;
  height:38px;
  border:1px solid #1D2733;
  border-radius:6px;
  background:#10171F;
}
.tw-header-search-icon-v07c{
  flex:0 0 auto;
  margin-left:11px;
  color:#45505F;
  font:700 11px/1 var(--mono);
  pointer-events:none;
}
.tw-header-search-v07c input{
  width:100%;
  min-width:0;
  height:100%;
  padding:8px 11px 8px 8px;
  border:0;
  outline:0;
  background:transparent;
  color:#E7EDF4;
  font:500 10px/1.3 var(--mono);
}
.tw-header-search-v07c input::placeholder{
  color:#45505F;
  opacity:1;
}
.tw-header-search-v07c:focus-within{
  border-color:#2A3847;
}
.tw-header-gas-v07c{
  display:flex;
  align-items:center;
  gap:7px;
  min-height:38px;
  padding:8px 11px;
  border:1px solid #1D2733;
  border-radius:6px;
  background:#0E141C;
  color:#7C8CA0;
  font:700 9px/1.2 var(--mono);
  white-space:nowrap;
}
.tw-header-gas-v07c i{
  width:6px;
  height:6px;
  border-radius:50%;
  background:#4CF4D6;
  box-shadow:0 0 0 3px rgba(76,244,214,.06);
}
@media(max-width:900px){
  .tw-header-search-v07c{width:min(390px,42vw);min-width:180px}
}
@media(max-width:700px){
  .tw-header-tools-v07c{gap:7px}
  .tw-header-search-v07c{display:none}
}
@media(max-width:520px){
  .tw-header-gas-v07c{display:none}
}

/* TOKEN_WORKSPACE_V26A_THREE_COLUMN_SHELL */
.shell{width:min(1780px,calc(100% - 24px))}
.token-workspace-v26{display:grid;grid-template-columns:minmax(220px,280px) minmax(0,1fr) minmax(290px,330px);gap:14px;align-items:start;margin-top:14px}
.workspace-main-v26{min-width:0}
.workspace-main-v26 .token-overview-card{margin-top:0}
.workspace-rail-v26{display:grid;gap:14px;position:sticky;top:14px;min-width:0}
.workspace-rail-card{min-width:0;border:1px solid var(--line);background:var(--panel);overflow:hidden}
.workspace-rail-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:15px;border-bottom:1px solid var(--line)}
.workspace-rail-head h2{margin:0;font:650 15px/1.2 var(--display);text-transform:uppercase;letter-spacing:.03em}
.workspace-rail-head small{display:block;margin-top:5px;color:var(--muted);font-size:11px}
.workspace-rail-head a{color:var(--blue);font-size:11px;text-decoration:none;white-space:nowrap}
.timeline-empty{display:grid;justify-items:start;gap:7px;padding:18px 15px;color:var(--muted)}
.timeline-empty i{width:10px;height:10px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px rgba(38,212,154,.09)}
.timeline-empty strong{color:var(--text);font-size:13px}
.timeline-empty p{margin:0;font-size:12px;line-height:1.55}
.coin-list-search{display:block;padding:12px 12px 8px}
.coin-list-search input{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:5px;background:var(--panel2);color:var(--text);font:12px var(--ui)}
.coin-list-rows{max-height:620px;overflow:auto;scrollbar-gutter:stable}
.coin-list-row{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:9px;align-items:center;padding:10px 12px;border-top:1px solid var(--line);color:var(--text);text-decoration:none}
.coin-list-row:hover{background:var(--panel2)}
.coin-list-row.active{background:rgba(255,148,24,.055);box-shadow:inset 2px 0 var(--amber)}
.coin-list-avatar{width:34px;height:34px;display:grid;place-items:center;overflow:hidden;border:1px solid var(--line);border-radius:50%;background:var(--panel2);font:700 13px var(--display)}
.coin-list-avatar img{width:100%;height:100%;display:block;object-fit:cover}
.coin-list-identity{min-width:0}
.coin-list-identity strong,.coin-list-identity small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.coin-list-identity strong{font-size:12px}.coin-list-identity small{margin-top:3px;color:var(--muted);font:10px var(--mono)}
.coin-list-change{font:650 10px var(--ui);font-variant-numeric:tabular-nums}.coin-list-change.up{color:var(--green)}.coin-list-change.down{color:var(--red)}.coin-list-change.unavailable{color:var(--muted)}
.coin-list-empty{padding:18px 14px;color:var(--muted);font-size:12px}
.workspace-right-v26{position:static;max-height:none;overflow:visible;scrollbar-gutter:auto;overscroll-behavior:auto}
.workspace-right-v26 .card{margin:0}html[data-theme="intel"] .workspace-right-v26 .decision-side-v2{position:static!important;top:auto!important}.workspace-right-v26 .jupiter{padding:16px}.workspace-right-v26 .jupiter h3{font-size:18px}.workspace-right-v26 .sandbox-note{font-size:12px}.workspace-right-v26 .market-snapshot-v26{position:static;padding:16px}.workspace-right-v26 .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.workspace-right-v26 .metric{padding:10px;min-height:62px}.workspace-right-v26 .metric .value{font-size:14px}.workspace-right-v26 .dexsato-evidence-strip{grid-template-columns:repeat(2,minmax(0,1fr))!important}.workspace-right-v26 .dexsato-evidence-item{padding:9px!important}.workspace-right-v26 .qualification h3{font-size:15px}.workspace-right-v26 .check{font-size:11px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
html{scrollbar-width:none}html::-webkit-scrollbar{display:none}
html[data-theme="intel"] .workspace-rail-card{border-color:#303a45;background:#0f141a}
html[data-theme="intel"] .workspace-rail-head,html[data-theme="intel"] .coin-list-row{border-color:#28313b}
html[data-theme="intel"] .coin-list-search input{border-color:#303a45;background:#121820}
@media(max-width:1180px){.token-workspace-v26{grid-template-columns:minmax(0,1fr) minmax(290px,340px)}.workspace-main-v26{grid-column:1}.workspace-left-v26{grid-column:1/-1;grid-row:2;position:static;grid-template-columns:1fr 1fr}.workspace-right-v26{grid-column:2;grid-row:1;position:static}.coin-list-rows{max-height:340px}}
@media(max-width:820px){.token-workspace-v26{grid-template-columns:1fr}.workspace-main-v26,.workspace-left-v26,.workspace-right-v26{grid-column:1;position:static}.workspace-main-v26{grid-row:1}.workspace-left-v26{grid-row:2}.workspace-right-v26{grid-row:3;grid-template-columns:1fr 1fr;max-height:none;overflow:visible}}
@media(max-width:620px){.workspace-left-v26,.workspace-right-v26{grid-template-columns:1fr}.workspace-right-v26 .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}

/* TOKEN_WORKSPACE_V27_JUPITER_UX */
.jupiter-v27{display:grid;gap:14px}.jupiter-v27 h3{margin:0!important;font-size:20px!important}.jupiter-v27>.eyebrow{margin-bottom:-8px}.jupiter-v27 .badge{justify-self:start}.wallet-bar-v27{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;padding:10px 11px;border:1px solid var(--line);border-radius:6px;background:var(--panel2)}.wallet-bar-v27 .wallet-state{margin:0;padding:0;background:transparent;font:600 11px/1.35 var(--ui);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.wallet-bar-v27 .sandbox-button{padding:7px 9px;font-size:11px}.swap-entry-v27{overflow:hidden;border:1px solid var(--line);border-radius:7px;background:var(--panel2)}.swap-leg-v27{padding:13px}.swap-leg-v27+.swap-leg-v27{border-top:1px solid var(--line)}.swap-leg-head-v27{display:flex;align-items:center;justify-content:space-between;gap:10px;color:var(--muted);font-size:11px}.token-pill-v27{padding:4px 7px;border:1px solid var(--line);border-radius:999px;color:var(--text);font:700 11px var(--mono)}.swap-amount-v27{width:100%;margin-top:6px;padding:0;border:0;background:transparent;color:var(--text);font:700 25px/1.2 var(--display);font-variant-numeric:tabular-nums}.swap-amount-v27:focus{outline:0}.swap-receive-v27{display:block;margin-top:6px;color:var(--text);font:700 25px/1.2 var(--display);overflow-wrap:anywhere}.swap-leg-note-v27{display:block;margin-top:5px;color:var(--muted);font-size:10px}.jupiter-v27 .sandbox-form{margin:0;gap:10px}.jupiter-v27 .sandbox-button.primary{width:100%}.quote-result-v27{display:none}.quote-result-v27.visible{display:block;margin:0;padding:0;border:1px solid var(--line);border-radius:7px;overflow:hidden}.quote-preview-head-v27{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 12px;border-bottom:1px solid var(--line);background:var(--panel2)}.quote-preview-head-v27 strong{font:750 11px var(--mono);letter-spacing:.05em;text-transform:uppercase}.quote-fresh-v27{color:var(--green);font-size:10px}.quote-summary-v27{padding:4px 12px}.quote-summary-row-v27{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px solid var(--line);font-size:11px}.quote-summary-row-v27:first-child{border-top:0}.quote-summary-row-v27 span{color:var(--muted)}.quote-summary-row-v27 b{text-align:right;font:650 11px/1.35 var(--mono);overflow-wrap:anywhere}.swap-warning-v27{margin:0;padding:11px 12px;border:1px solid rgba(255,148,24,.35);border-left:2px solid var(--amber);border-radius:5px;background:rgba(255,148,24,.06);font-size:11px;line-height:1.45}.swap-warning-v27 strong{display:block;margin-bottom:3px;color:var(--amber)}.jupiter-v27 .swap-consent{margin:0;font-size:11px}.swap-confirmation-v27{padding:12px;border:1px solid var(--amber);border-radius:7px;background:rgba(255,148,24,.045)}.swap-confirmation-v27[hidden]{display:none}.swap-confirmation-v27 h4{margin:0 0 4px;font:700 14px var(--display)}.swap-confirmation-v27>p{margin:0 0 8px;color:var(--muted);font-size:10px}.confirmation-list-v27{display:grid;gap:6px}.confirmation-row-v27{display:flex;justify-content:space-between;gap:10px;font-size:11px}.confirmation-row-v27 span{color:var(--muted)}.confirmation-row-v27 b{text-align:right;font:650 11px var(--mono)}.wallet-safety-v27{display:flex;gap:8px;align-items:flex-start;margin:0;padding-top:2px;color:var(--muted);font-size:10px;line-height:1.45}.wallet-safety-v27 i{color:var(--green);font-style:normal}.jupiter-v27 .quote-error{padding:11px;color:var(--amber);font-size:11px}.jupiter-v27 .swap-success{padding:11px}.workspace-right-v26 .jupiter-v27{padding:16px}
/* TOKEN_WORKSPACE_V271_JUPITER_COMPACT_HEADER */
.jupiter-v27{gap:11px}.jupiter-v27>.eyebrow{margin:0 0 -7px;font-size:9px!important}.jupiter-v27 h3{line-height:1.15}.jupiter-v27 .badge{margin-top:-4px;padding:3px 6px;font-size:8px;opacity:.8}.wallet-bar-v27{padding:7px 8px;min-height:42px}.wallet-bar-v27 .wallet-state{font:650 12px/1.3 var(--ui)}.wallet-bar-v27 .wallet-state.connected{color:var(--green)}.wallet-bar-v27 .wallet-state.connected:before{content:"";display:inline-block;width:6px;height:6px;margin-right:6px;border-radius:50%;background:var(--green);box-shadow:0 0 0 3px rgba(34,210,127,.08);vertical-align:1px}.wallet-bar-v27 .sandbox-button{padding:6px 8px;font-size:10px}.swap-pay-v27{text-align:center;padding:16px 13px}.swap-pay-v27 .swap-leg-head-v27{justify-content:center;flex-direction:column;gap:7px}.swap-pay-v27 .swap-amount-v27{text-align:center;margin-top:8px}.swap-pay-v27 .swap-leg-note-v27{text-align:center}.token-pill-v27{display:inline-flex;align-items:center;gap:5px}.solana-mark-v27{width:14px;height:12px;display:block;flex:0 0 auto}
/* TOKEN_WORKSPACE_V272_QUOTE_FAILURE_STATE */
.swap-input-error-v272{display:block;margin:8px auto 0;padding:7px 8px;border-radius:4px;background:rgba(255,95,120,.07);color:var(--red);font:650 10px/1.4 var(--ui);text-align:left}.swap-input-error-v272[hidden]{display:none}
/* TW-DEX-04 — two-way Jupiter execution panel, adapted from the approved mockup. */
/* TW-DEX-04A — rounded trade-card polish. */
.trade-v04{--trade-accent:var(--green);display:grid;gap:12px;padding:16px!important;border-radius:11px!important;overflow:hidden;background:linear-gradient(155deg,#14202a,#0e151e 45%)!important;border-color:#2c3c49!important;box-shadow:0 12px 36px rgba(0,0,0,.2)}
.trade-v04[data-side="sell"]{--trade-accent:var(--red)}
.trade-head-v04{display:flex;align-items:center;justify-content:space-between;gap:10px}.trade-head-v04 h3{margin:0!important;font-size:17px!important}.trade-head-v04 .trade-network-v04{display:inline-flex;align-items:center;gap:5px;margin:0;padding:5px 8px;border:1px solid #254c45;border-radius:5px;background:#16322f;color:var(--cyan);font:700 8px/1 var(--mono);letter-spacing:.02em}.trade-network-v04 i{width:5px;height:5px;border-radius:50%;background:var(--cyan);box-shadow:0 0 0 2px rgba(76,244,214,.08)}
.trade-switch-v04{display:grid;grid-template-columns:1fr 1fr;gap:5px;padding:4px;border:1px solid var(--line);border-radius:9px;background:#080e15}.trade-switch-v04 button{height:39px;border:0;border-radius:6px;background:transparent;color:var(--muted);font:700 13px var(--ui);cursor:pointer}.trade-switch-v04 button[aria-pressed="true"]{background:var(--trade-accent);color:#07120f}.trade-switch-v04 button:disabled{cursor:wait;opacity:.65}
.trade-orderline-v04{display:flex;justify-content:space-between;align-items:center;gap:10px;color:var(--muted);font-size:10px}.trade-orderline-v04 strong{padding-bottom:6px;border-bottom:2px solid var(--trade-accent);color:var(--text);font-weight:650}.trade-orderline-v04 span:last-child{font-size:9px}
.trade-v04 .wallet-bar-v27{margin:0;padding:8px 9px;background:#090f17}
.trade-amount-v04,.trade-receive-v04{padding:13px;border:1px solid #2a3948;border-radius:8px;background:#090f17}.trade-receive-v04{background:#121e27;border-color:#263642}.trade-field-head-v04{display:flex;justify-content:space-between;gap:8px;margin-bottom:10px;color:var(--muted);font-size:9px}.trade-field-head-v04 span:last-child{text-align:right}.trade-amount-row-v04{display:flex;align-items:center;gap:8px}.trade-amount-row-v04 input{width:100%;min-width:0;padding:0;border:0;background:transparent;color:var(--text);font:650 27px/1.2 var(--display)}.trade-amount-row-v04 input:focus{outline:0}.trade-amount-row-v04 strong{min-width:0;font:650 22px/1.2 var(--display);overflow-wrap:anywhere}.trade-coin-v04{flex:0 0 auto;padding:8px 10px;border-radius:20px;background:#1a2734;color:var(--text);font:700 11px var(--display);white-space:nowrap}.trade-receive-v04 .trade-coin-v04{background:transparent;padding-right:0}.trade-note-v04{display:block;margin-top:7px;color:var(--muted);font-size:9px}
.trade-presets-v04{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.trade-presets-v04 button{padding:7px 0;border:1px solid var(--line2);border-radius:5px;background:#15202b;color:#afbfce;font-size:9px;cursor:pointer}.trade-presets-v04 button:hover{border-color:var(--trade-accent);color:var(--trade-accent)}
.trade-route-v04{display:flex;justify-content:space-between;gap:10px;padding:11px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);color:var(--muted);font-size:9px}.trade-route-v04 b{color:var(--text);font-weight:550;text-align:right}
.trade-v04 .quote-result-v27.visible{margin:0}.trade-v04 .swap-warning-v27,.trade-v04 .swap-consent{margin:0}.trade-v04 .sandbox-button.primary{height:43px;border:0;border-radius:7px;background:var(--trade-accent);color:#07120f;font-size:12px}.trade-v04 .sandbox-button.primary:disabled{opacity:.4}.trade-v04 .wallet-safety-v27{padding-top:0}
@media(max-width:820px){.trade-v04{padding:15px!important}.trade-amount-row-v04 input{font-size:25px}}
/* PHASE02_P0D2_ARCHIVE_SWAP_GATING */
.jupiter-archive-gate{display:grid;gap:11px}.jupiter-archive-gate h3{margin:0!important}.jupiter-archive-gate .badge{justify-self:start}.archive-swap-message{margin:2px 0 0;padding:12px;border:1px solid var(--line);border-left:2px solid var(--amber);border-radius:5px;background:var(--panel2);color:var(--muted);font-size:12px;line-height:1.55}.archive-swap-message strong{display:block;margin-bottom:4px;color:var(--text);font-size:13px}.archive-swap-action{display:block;width:100%;padding:10px 12px;border:1px solid var(--amber);border-radius:5px;color:var(--amber);font:700 12px var(--ui);text-align:center;text-decoration:none}.archive-swap-action:hover{background:rgba(255,148,24,.06)}
/* PHASE02_P0D3_QUALIFICATION_REASON_TRANSPARENCY */
.qualification-vp0d3 h3{margin:5px 0 6px}.qualification-reason{margin:0 0 13px;padding:11px;border-left:2px solid var(--amber);background:var(--panel2);color:var(--muted);font-size:11px;line-height:1.55}.qualification-vp0d3.qualified .qualification-reason{border-left-color:var(--green)}.qualification-history-label{display:block;margin-top:4px;color:var(--muted)}
/* TOKEN_OBSERVATION_V28_LEFT_RAIL */
.token-observation-v28{padding:17px}.token-observation-v28 .workspace-rail-head{padding:0 0 12px}.token-observation-rows{border-top:1px solid var(--line)}.token-observation-row{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:12px 0;border-bottom:1px solid var(--line)}.token-observation-row span{color:var(--muted);font-size:11px}.token-observation-value{text-align:right;font:650 12px/1.35 var(--mono)}.token-observation-value.up,.token-observation-value.verified{color:var(--green)}.token-observation-value.down{color:var(--red)}.token-observation-note{margin:13px 0 0;padding:10px 11px;border-left:2px solid var(--amber);background:rgba(255,148,24,.055);color:var(--muted);font-size:10px;line-height:1.45}


/* TW-DEX-01 — Shell & Workspace Grid
   Presentation-only. Existing token, chart, transaction, qualification and Jupiter hooks remain unchanged. */
.tw-dex-app{
  min-height:100vh;
  display:grid;
  grid-template-columns:144px minmax(0,1fr);
  background:
    linear-gradient(rgba(76,244,214,.025) 1px,transparent 1px),
    linear-gradient(90deg,rgba(76,244,214,.025) 1px,transparent 1px),
    #080B10;
  background-size:42px 42px;
}
.tw-dex-side{
  position:sticky;top:0;height:100vh;min-width:0;
  display:flex;flex-direction:column;
  padding:14px 12px;
  border-right:1px solid #1D2733;
  background:#0B1118;
  z-index:20;
}
.tw-dex-side-brand{
  min-height:48px;display:flex;align-items:center;gap:10px;
  padding:0 4px 12px;border-bottom:1px solid #1D2733;
  color:#E7EDF4;text-decoration:none;
}
.tw-dex-side-brand img{width:30px;height:30px;object-fit:contain;flex:0 0 30px}
.tw-dex-side-brand span{min-width:0;display:block}
.tw-dex-side-brand strong{
  display:block;font-family:"Space Grotesk","Segoe UI",sans-serif;
  font-size:16px;font-weight:700;line-height:1;letter-spacing:-.02em;
}
.tw-dex-side-brand small{
  display:block;margin-top:4px;color:#45505F;
  font-family:"JetBrains Mono","Cascadia Mono",monospace;
  font-size:7px;line-height:1;letter-spacing:.12em;white-space:nowrap;
}
.tw-dex-side-nav{display:grid;gap:6px;margin-top:18px}
.tw-dex-side-nav a,.tw-dex-side-nav span{
  display:block;padding:10px 9px;border-left:2px solid transparent;
  color:#7C8CA0;font-family:"Space Grotesk","Segoe UI",sans-serif;
  font-size:11px;font-weight:600;text-decoration:none;
}
.tw-dex-side-nav .active{
  color:#4CF4D6;border-left-color:#4CF4D6;
  background:linear-gradient(90deg,rgba(76,244,214,.08),transparent);
}
.tw-dex-side-bottom{display:grid;gap:4px;margin-top:auto}
.tw-dex-side-bottom span{
  display:block;padding:8px 9px;color:#45505F;
  font-family:"JetBrains Mono","Cascadia Mono",monospace;font-size:9px;
}
.tw-dex-stage{min-width:0;display:grid;grid-template-rows:64px minmax(0,1fr)}
.tw-dex-topbar{
  position:sticky;top:0;z-index:19;
  min-height:64px;padding:0 20px;border-bottom:1px solid #1D2733;
  background:rgba(8,11,16,.94);backdrop-filter:blur(12px);
}
.tw-dex-topbar .tw-dex-brand{gap:10px}
.tw-dex-topbar .tw-dex-brand>img{display:none}
.tw-dex-topbar .tw-dex-brand>span{display:flex;align-items:baseline;gap:9px}
.tw-dex-topbar .tw-dex-brand strong{
  font-family:"Space Grotesk","Segoe UI",sans-serif;font-size:18px;font-weight:700;letter-spacing:-.02em;
}
.tw-dex-topbar .tw-dex-brand small{
  color:#45505F;font-family:"JetBrains Mono","Cascadia Mono",monospace;
  font-size:8px;letter-spacing:.12em;
}
.tw-dex-content{
  width:100%!important;max-width:none!important;margin:0!important;
  padding:14px!important;min-width:0;
}
.tw-dex-workspace-title{
  min-height:31px;display:flex;align-items:center;justify-content:space-between;gap:14px;
  margin:0 0 10px;padding:0 2px;
}
.tw-dex-workspace-title h1{
  margin:0;color:#E7EDF4;font-family:"Space Grotesk","Segoe UI",sans-serif;
  font-size:18px;font-weight:700;line-height:1.1;letter-spacing:-.02em;
}
.tw-dex-workspace-title span{
  color:#7C8CA0;font-family:"JetBrains Mono","Cascadia Mono",monospace;
  font-size:9px;letter-spacing:.06em;
}
/* Keep the production three-zone workspace, but size it to the approved DEX mockup proportions. */
.tw-dex-content .token-workspace-v26{
  display:grid!important;
  grid-template-columns:230px minmax(0,1fr) 340px!important;
  gap:10px!important;align-items:start!important;margin-top:0!important;
}
.tw-dex-content .workspace-rail-v26{gap:10px!important;top:78px}
.tw-dex-content .workspace-main-v26{min-width:0}
.tw-dex-content .workspace-left-v26{grid-column:1}
.tw-dex-content .workspace-main-v26{grid-column:2}
.tw-dex-content .workspace-right-v26{grid-column:3}

@media(max-width:1450px){
  .tw-dex-app{grid-template-columns:116px minmax(0,1fr)}
  .tw-dex-side-brand span{display:none}
  .tw-dex-side-nav a,.tw-dex-side-nav span{padding-left:7px;padding-right:5px;font-size:10px}
  .tw-dex-content .token-workspace-v26{grid-template-columns:210px minmax(0,1fr) 320px!important}
}
@media(max-width:1180px){
  .tw-dex-content .token-workspace-v26{grid-template-columns:minmax(0,1fr) minmax(290px,340px)!important}
  .tw-dex-content .workspace-main-v26{grid-column:1!important;grid-row:1!important}
  .tw-dex-content .workspace-right-v26{grid-column:2!important;grid-row:1!important;position:static!important}
  .tw-dex-content .workspace-left-v26{
    grid-column:1/-1!important;grid-row:2!important;position:static!important;
    grid-template-columns:1fr 1fr!important;
  }
}
@media(max-width:820px){
  .tw-dex-app{display:block}
  .tw-dex-side{display:none}
  .tw-dex-stage{display:block}
  .tw-dex-topbar{min-height:60px;padding:0 10px}
  .tw-dex-topbar .tw-dex-brand small{display:none}
  .tw-dex-content{padding:10px!important}
  .tw-dex-content .token-workspace-v26{grid-template-columns:1fr!important}
  .tw-dex-content .workspace-main-v26{grid-column:1!important;grid-row:1!important}
  .tw-dex-content .workspace-left-v26{grid-column:1!important;grid-row:2!important;grid-template-columns:1fr 1fr!important}
  .tw-dex-content .workspace-right-v26{grid-column:1!important;grid-row:3!important;grid-template-columns:1fr 1fr!important}
}
@media(max-width:620px){
  .tw-dex-workspace-title span{font-size:8px}
  .tw-dex-content .workspace-left-v26,.tw-dex-content .workspace-right-v26{grid-template-columns:1fr!important}
}


/* TW-DEX-02 — Compact Market Header
   Presentation/data mapping only. Existing production data sources and hooks are preserved. */
.tw-market-header{
  margin:0!important;padding:0!important;border:1px solid #1D2733!important;
  border-radius:0!important;background:#0E141C!important;overflow:hidden;
}
.tw-market-top{
  display:grid;grid-template-columns:minmax(220px,1.2fr) minmax(170px,.85fr)
  repeat(4,minmax(88px,.55fr));min-height:92px;
}
.tw-market-top>div{min-width:0;padding:15px 14px;border-right:1px solid #1D2733}
.tw-market-top>div:last-child{border-right:0}
.tw-market-identity{display:flex;align-items:center;gap:12px}
.tw-market-avatar{
  width:50px!important;height:50px!important;flex:0 0 50px;border:1px solid #2A3847!important;
  border-radius:50%!important;background:#0B1118!important;
}
.tw-market-avatar .token-avatar-fallback{font:700 20px/1 "Space Grotesk","Segoe UI",sans-serif}
.tw-market-identity-copy{min-width:0}
.tw-market-identity-copy h1{
  margin:0;color:#E7EDF4;font-family:"Space Grotesk","Segoe UI",sans-serif;
  font-size:22px;font-weight:700;line-height:1.05;letter-spacing:-.025em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.tw-market-identity-copy>span{
  display:block;margin-top:6px;color:#7C8CA0;
  font-family:"JetBrains Mono","Cascadia Mono",monospace;font-size:9px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.tw-market-price>span,.tw-market-kpi>span,.tw-market-meta-cell>span{
  display:block;color:#45505F;font-family:"JetBrains Mono","Cascadia Mono",monospace;
  font-size:8px;font-weight:600;line-height:1.2;letter-spacing:.08em;text-transform:uppercase;
}
.tw-market-price strong{
  display:block;margin-top:7px;color:#E7EDF4;
  font-family:"Space Grotesk","Segoe UI",sans-serif;font-size:22px;font-weight:700;line-height:1.1;
  font-variant-numeric:tabular-nums;
}
.tw-market-price .token-change{
  display:block;margin-top:7px;padding:0;border:0!important;background:transparent!important;
  font-family:"JetBrains Mono","Cascadia Mono",monospace;font-size:10px;font-weight:700;line-height:1.2;
}
.tw-market-price .token-change.up{color:#31D89C}
.tw-market-price .token-change.down{color:#FF5C7A}
.tw-market-price .token-change.flat,.tw-market-price .token-change.unavailable{color:#7C8CA0}
.tw-market-kpi strong{
  display:block;margin-top:9px;color:#E7EDF4;font-family:"Space Grotesk","Segoe UI",sans-serif;
  font-size:12px;font-weight:600;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.tw-market-dex{color:#E7EDF4!important;text-decoration:none!important}
a.tw-market-dex:hover{color:#4CF4D6!important}
.tw-market-meta{
  display:grid;grid-template-columns:minmax(170px,1.25fr) minmax(170px,1.25fr) minmax(100px,.6fr) minmax(100px,.55fr);
  border-top:1px solid #1D2733;
}
.tw-market-meta-cell{min-width:0;padding:9px 11px;border-right:1px solid #1D2733}
.tw-market-meta-cell:last-child{border-right:0}
.tw-market-meta-cell>div{display:flex;align-items:center;gap:7px;min-width:0;margin-top:4px}
.tw-market-meta-cell code{
  min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  color:#C9D5E2;font-family:"JetBrains Mono","Cascadia Mono",monospace;font-size:9px;
}
.tw-market-copy{
  flex:0 0 auto;margin:0!important;padding:3px 5px!important;border:1px solid #2A3847!important;
  border-radius:2px!important;color:#4CF4D6!important;font:600 7px/1.2 "JetBrains Mono","Cascadia Mono",monospace!important;
}
.tw-market-status{
  display:inline-flex;align-items:center;gap:6px;margin-top:5px;color:#31D89C;
  font-family:"JetBrains Mono","Cascadia Mono",monospace;font-size:9px;font-weight:700;
}
.tw-market-status i{width:6px;height:6px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor}
.tw-market-status.stored{color:#7C8CA0}
.tw-market-watch{
  min-height:0!important;margin-top:4px;padding:3px 6px!important;border:1px solid #2A3847!important;
  border-radius:2px!important;background:transparent!important;color:#7C8CA0!important;
  font:600 8px/1.2 "JetBrains Mono","Cascadia Mono",monospace!important;
}
.tw-market-watch.active{color:#F4B95F!important;border-color:rgba(244,185,95,.45)!important}
.tw-market-header .trader-tf-strip{
  width:100%!important;max-width:none!important;margin:0!important;
  grid-template-columns:repeat(6,minmax(0,1fr))!important;
  border:0!important;border-top:1px solid #1D2733!important;border-radius:0!important;
  background:#0B1118!important;
}
.tw-market-header .trader-tf-cell{
  padding:8px 10px!important;border-right:1px solid #1D2733!important;
}
.tw-market-header .trader-tf-cell:last-child{border-right:0!important}
.tw-market-header .trader-tf-cell span{
  color:#45505F!important;font-family:"JetBrains Mono","Cascadia Mono",monospace!important;
  font-size:8px!important;font-weight:600!important;letter-spacing:.06em!important;
}
.tw-market-header .trader-tf-value{
  margin-top:4px!important;font-family:"JetBrains Mono","Cascadia Mono",monospace!important;
  font-size:10px!important;font-weight:700!important;letter-spacing:0!important;
}
.tw-market-header .trader-tf-value.up{color:#31D89C!important}
.tw-market-header .trader-tf-value.down{color:#FF5C7A!important}
.tw-market-header .trader-tf-value.unavailable{color:#7C8CA0!important}

@media(max-width:1450px){
  .tw-market-top{grid-template-columns:minmax(210px,1.2fr) minmax(155px,.85fr) repeat(2,minmax(84px,.55fr))}
  .tw-market-top>.tw-market-kpi:nth-last-child(-n+2){display:none}
  .tw-market-meta{grid-template-columns:minmax(150px,1fr) minmax(150px,1fr) 92px 90px}
}
@media(max-width:1180px){
  .tw-market-top{grid-template-columns:minmax(210px,1.15fr) minmax(150px,.85fr) repeat(2,minmax(82px,.55fr))}
}
@media(max-width:820px){
  .tw-market-top{grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}
  .tw-market-top>.tw-market-kpi{display:none!important}
  .tw-market-meta{grid-template-columns:1fr 1fr}
  .tw-market-meta-cell:nth-child(2){border-right:0}
  .tw-market-meta-cell:nth-child(-n+2){border-bottom:1px solid #1D2733}
  .tw-market-header .trader-tf-strip{grid-template-columns:repeat(3,minmax(0,1fr))!important}
  .tw-market-header .trader-tf-cell:nth-child(3){border-right:0!important}
  .tw-market-header .trader-tf-cell:nth-child(-n+3){border-bottom:1px solid #1D2733!important}
}
@media(max-width:520px){
  .tw-market-top{grid-template-columns:1fr}
  .tw-market-top>div{border-right:0;border-bottom:1px solid #1D2733}
  .tw-market-price strong{font-size:20px}
  .tw-market-meta{grid-template-columns:1fr}
  .tw-market-meta-cell{border-right:0!important;border-bottom:1px solid #1D2733}
  .tw-market-meta-cell:last-child{border-bottom:0}
}


/* TW-DEX-02A — Market Header Round + Weight Polish
   CSS-only. No data, behavior, engine, API, chart, transaction or Jupiter changes. */
.tw-market-header{
  border-radius:10px!important;
  overflow:hidden!important;
}
.tw-market-identity-copy h1{
  font-weight:700!important;
}
.tw-market-price>span,
.tw-market-kpi>span,
.tw-market-meta-cell>span{
  font-weight:700!important;
}
.tw-market-price strong{
  font-weight:700!important;
}
.tw-market-price .token-change{
  font-weight:700!important;
}
.tw-market-kpi strong{
  font-weight:700!important;
}
.tw-market-meta-cell code{
  font-weight:600!important;
}
.tw-market-status{
  font-weight:700!important;
}
.tw-market-watch{
  font-weight:700!important;
}
.tw-market-header .trader-tf-cell span{
  font-weight:700!important;
}
.tw-market-header .trader-tf-value{
  font-weight:700!important;
}


/* TW-DEX-03 — Chart Terminal
   CSS-only presentation pass. Candle data, live API, interactions and JS hooks remain unchanged. */
.tw-dex-content .candlestick-panel{
  margin-top:10px!important;
  border:1px solid #1D2733!important;
  border-radius:10px!important;
  background:#0E141C!important;
  overflow:hidden!important;
  box-shadow:none!important;
}
.tw-dex-content .candle-toolbar{
  min-height:46px!important;
  gap:10px!important;
  border-bottom:1px solid #1D2733!important;
  background:#0E141C!important;
}
.tw-dex-content .candle-timeframe-tabs{
  gap:3px!important;
  padding:7px 9px!important;
  background:transparent!important;
}
.tw-dex-content .candle-tf-button{
  min-width:42px!important;
  height:30px!important;
  padding:0 9px!important;
  border:1px solid transparent!important;
  border-radius:4px!important;
  background:transparent!important;
  color:#7C8CA0!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:9px!important;
  font-weight:700!important;
  letter-spacing:.02em!important;
}
.tw-dex-content .candle-tf-button:hover{
  color:#E7EDF4!important;
  background:#10171F!important;
  border-color:#1D2733!important;
}
.tw-dex-content .candle-tf-button.active{
  color:#4CF4D6!important;
  background:rgba(76,244,214,.055)!important;
  border-color:#4CF4D6!important;
}
.tw-dex-content .candle-toolbar-actions{
  gap:9px!important;
  padding:7px 10px 7px 0!important;
}
.tw-dex-content .candle-ohlc{
  gap:7px 10px!important;
  color:#7C8CA0!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:8px!important;
  font-weight:700!important;
  letter-spacing:.01em!important;
}
.tw-dex-content .candle-ohlc span{
  color:#7C8CA0!important;
}
.tw-dex-content .candle-ohlc b{
  color:#E7EDF4!important;
  font-weight:700!important;
}
.tw-dex-content .candle-live-state{
  color:#4CF4D6!important;
  border-color:rgba(76,244,214,.34)!important;
  background:rgba(76,244,214,.045)!important;
  border-radius:3px!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:8px!important;
  font-weight:700!important;
  letter-spacing:.05em!important;
}
.tw-dex-content .candle-live-state i{
  background:#4CF4D6!important;
  box-shadow:0 0 8px rgba(76,244,214,.65)!important;
}
.tw-dex-content .candle-reset{
  height:30px!important;
  padding:0 9px!important;
  border:1px solid #2A3847!important;
  border-radius:4px!important;
  background:transparent!important;
  color:#7C8CA0!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:8px!important;
  font-weight:700!important;
}
.tw-dex-content .candle-reset:hover{
  color:#E7EDF4!important;
  background:#10171F!important;
}
.tw-dex-content .candlestick-stage{
  min-height:450px!important;
  padding:0!important;
  background:
    linear-gradient(rgba(124,140,160,.055) 1px,transparent 1px),
    linear-gradient(90deg,rgba(124,140,160,.045) 1px,transparent 1px),
    #0A1118!important;
  background-size:100% 54px,86px 100%!important;
}
.tw-dex-content .candlestick-chart{
  display:block!important;
  width:100%!important;
  height:450px!important;
  background:transparent!important;
  cursor:crosshair!important;
}
.tw-dex-content .candlestick-grid{
  stroke:#1D2733!important;
  stroke-opacity:.88!important;
  stroke-width:1!important;
}
.tw-dex-content .candlestick-axis-line{
  stroke:#2A3847!important;
  stroke-opacity:.75!important;
}
.tw-dex-content .candlestick-axis,
.tw-dex-content .candlestick-axis-label,
.tw-dex-content .candlestick-time-label{
  fill:#7C8CA0!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:9px!important;
  font-weight:600!important;
}
.tw-dex-content .candlestick-up{
  stroke:#31D89C!important;
  fill:#31D89C!important;
}
.tw-dex-content .candlestick-down{
  stroke:#FF5C7A!important;
  fill:#FF5C7A!important;
}
.tw-dex-content .candlestick-wick{
  stroke-width:1.25!important;
}
.tw-dex-content .candlestick-body{
  shape-rendering:geometricPrecision;
}
.tw-dex-content .candlestick-volume{
  opacity:.46!important;
}
.tw-dex-content .candlestick-price-line{
  stroke:#4CF4D6!important;
  stroke-width:1!important;
  stroke-dasharray:4 3!important;
}
.tw-dex-content .candlestick-price-tag{
  fill:#4CF4D6!important;
}
.tw-dex-content .candlestick-price-tag-text{
  fill:#06110F!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:9px!important;
  font-weight:700!important;
}
.tw-dex-content .candlestick-crosshair{
  stroke:#7C8CA0!important;
  stroke-opacity:.72!important;
  stroke-width:1!important;
  stroke-dasharray:3 4!important;
}
.tw-dex-content .candlestick-cross-label{
  fill:#10171F!important;
  stroke:#2A3847!important;
}
.tw-dex-content .candlestick-cross-label-text{
  fill:#E7EDF4!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:9px!important;
  font-weight:700!important;
}
.tw-dex-content .candlestick-empty{
  inset:0!important;
  color:#7C8CA0!important;
  background:#0A1118!important;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
  font-size:10px!important;
}
@media(max-width:1180px){
  .tw-dex-content .candle-ohlc{gap:6px!important;font-size:7.5px!important}
  .tw-dex-content .candle-tf-button{min-width:38px!important;padding:0 7px!important}
}
@media(max-width:820px){
  .tw-dex-content .candle-toolbar{
    display:block!important;
    min-height:0!important;
  }
  .tw-dex-content .candle-timeframe-tabs{
    overflow-x:auto!important;
    border-bottom:1px solid #1D2733!important;
  }
  .tw-dex-content .candle-toolbar-actions{
    justify-content:space-between!important;
    padding:7px 9px!important;
  }
  .tw-dex-content .candle-ohlc{
    overflow-x:auto!important;
    flex-wrap:nowrap!important;
    justify-content:flex-start!important;
  }
  .tw-dex-content .candlestick-stage{min-height:340px!important}
  .tw-dex-content .candlestick-chart{height:340px!important}
}
@media(max-width:520px){
  .tw-dex-content .candle-ohlc{display:none!important}
  .tw-dex-content .candle-toolbar-actions{justify-content:flex-end!important}
  .tw-dex-content .candlestick-stage{min-height:300px!important}
  .tw-dex-content .candlestick-chart{height:300px!important}
}


/* TW-DEX-03D — TradingView Lightweight Charts Integration */
.tw-dex-content .lightweight-chart{
  width:100%;
  height:450px;
  min-height:450px;
  background:#0A1118;
}
.tw-dex-content .lightweight-chart table{
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace!important;
}
.tw-dex-content .lightweight-fallback-chart[hidden]{display:none!important}
.tw-dex-content .candlestick-panel[data-lightweight-active="1"] .candlestick-stage{
  padding:0!important;
  background:#0A1118!important;
}
.tw-dex-content .candlestick-panel[data-lightweight-active="1"] .candlestick-empty{
  z-index:4;
  background:rgba(10,17,24,.94)!important;
}
@media(max-width:820px){
  .tw-dex-content .lightweight-chart{height:340px;min-height:340px}
}
@media(max-width:520px){
  .tw-dex-content .lightweight-chart{height:300px;min-height:300px}
}


/* TW-DEX-03F — Lightweight Runtime Diagnostic */
.tw-dex-content .lw-runtime-diagnostic{
  display:none;
  position:absolute;
  z-index:8;
  left:10px;
  bottom:10px;
  max-width:min(520px,calc(100% - 20px));
  padding:8px 10px;
  border:1px solid #2A3847;
  border-radius:6px;
  background:rgba(8,11,16,.94);
  color:#B8C5D2;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace;
  font-size:9px;
  line-height:1.5;
  white-space:pre-wrap;
  pointer-events:none;
}
.tw-dex-content .lw-runtime-diagnostic.visible{display:block}
.tw-dex-content .lw-runtime-diagnostic.error{
  border-color:rgba(255,92,122,.7);
  color:#FFD2DA;
}
.tw-dex-content .lw-runtime-diagnostic.ok{
  border-color:rgba(76,244,214,.45);
  color:#BFFCF0;
}
.tw-dex-content .static-bootstrap-diagnostic{
  display:block!important;
  position:absolute;
  z-index:9;
  left:10px;
  top:10px;
  bottom:auto;
  max-width:420px;
  padding:7px 10px;
  border:1px solid rgba(185,140,255,.7);
  border-radius:6px;
  background:rgba(15,13,24,.96);
  color:#DCC7FF;
  font-family:"JetBrains Mono","Cascadia Mono",Consolas,monospace;
  font-size:9px;
  font-weight:700;
  line-height:1.4;
  letter-spacing:.03em;
  white-space:normal;
  pointer-events:none;
}

</style>
<script src="/static/vendor/lightweight-charts.standalone.production.js?v=5.2.1"></script>
</head><body><div class="tw-dex-app">
<aside class="tw-dex-side" aria-label="DexSato navigation">
  <a class="tw-dex-side-brand" href="/" aria-label="DexSato home"><img src="/static/branding/dexsato-mark.png" alt=""><span><strong>dexsato</strong><small>DEX INTELLIGENCE</small></span></a>
  <nav class="tw-dex-side-nav" aria-label="Market navigation">
    <a href="/discovery/solana">Solana</a>
    <a href="/">Major Assets</a>
    <span>Watchlist</span>
    <span class="active" aria-current="page">Token Workspace</span>
  </nav>
  <nav class="tw-dex-side-bottom" aria-label="Secondary navigation">
    <span>Wallet Profile</span><span>Documentation</span><span>Disclaimer</span>
  </nav>
</aside>
<div class="tw-dex-stage">
<header class="topbar tw-dex-topbar"><div class="brand tw-dex-brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><span><strong>dexsato</strong><small>DEX INTELLIGENCE</small></span></div><div class="tw-header-tools-v07c"><label class="tw-header-search-v07c"><span class="sr-only">Search token, pair or contract</span><span class="tw-header-search-icon-v07c" aria-hidden="true">&#9906;</span><input type="search" placeholder="Search token, pair or contract" aria-label="Search token, pair or contract" data-header-search-v07c></label><div class="tw-header-gas-v07c" aria-label="Gas status"><i aria-hidden="true"></i><span>Gas · --</span></div><button class="tw-header-wallet-v07b" type="button" data-header-connect-wallet>Connect Wallet</button></div></header>
<main class="shell tw-dex-content"><div class="tw-dex-workspace-title"><h1>TOKEN WORKSPACE</h1><span>SOLANA · EXACT POOL</span></div>
<div class="token-workspace-v26" data-token-workspace-v26>
<aside class="workspace-rail-v26 workspace-left-v26" aria-label="Coin navigation">__COIN_LIST_PANEL__</aside>
<section class="workspace-main-v26" aria-label="Selected token market evidence">
__TOKEN_OVERVIEW_CARD__
<section class="hero"><div><span class="eyebrow">Qualified exact-token workspace</span><h1>__SYMBOL__ / __QUOTE__</h1><p>Review observed market activity, exact-pool identity and disclosed risk before taking any action.</p></div><div class="status"><span class="eyebrow">Market data</span><b>__STATUS__</b><small>__STATUS_LABEL__</small></div></section>
<section class="identity"><div class="identity-head"><div><span class="eyebrow">Token identity</span><h2>__NAME__</h2><span class="name">__DEX__ · Solana exact pool</span></div><div>__SOURCE_LINK__</div></div><div class="addresses"><div class="address"><span>Canonical token address</span><div class="address-row"><code title="__TOKEN__">__TOKEN_SHORT__</code><button class="copy-address" type="button" data-copy-address="__TOKEN__">Copy</button></div></div><div class="address"><span>Exact pool address</span><div class="address-row"><code title="__POOL__">__POOL_SHORT__</code><button class="copy-address" type="button" data-copy-address="__POOL__">Copy</button></div></div></div></section>
__CANDLESTICK_CHART_PANEL__
</section>
<aside class="workspace-rail-v26 workspace-right-v26" aria-label="Execution sandbox and market snapshot">
<section class="card jupiter jupiter-v27 trade-v04" data-jupiter-sandbox data-token-address="__TOKEN__" data-token-symbol="__SYMBOL__" data-side="buy">
  <div class="trade-head-v04"><h3>Trade __SYMBOL__</h3><span class="trade-network-v04"><i aria-hidden="true"></i>Solana</span></div>
  <div class="trade-switch-v04" role="group" aria-label="Trade direction"><button type="button" data-trade-side="buy" aria-pressed="true">Buy</button><button type="button" data-trade-side="sell" aria-pressed="false">Sell</button></div>
  <div class="wallet-bar-v27"><div class="wallet-state" data-wallet-state>Wallet not connected</div><button class="sandbox-button" type="button" data-connect-wallet>Connect wallet</button></div>
  <div class="trade-orderline-v04"><strong>Market swap</strong><span>Slippage · managed by Jupiter</span></div>
  <label class="trade-amount-v04" for="jupiter-amount"><span class="trade-field-head-v04"><span>You pay</span><span data-balance-label>SOL balance checked at order</span></span><span class="trade-amount-row-v04"><input id="jupiter-amount" data-quote-amount inputmode="decimal" type="number" min="0" step="any" value="0.1" aria-label="Amount to pay"><span class="trade-coin-v04" data-pay-coin>&#9678; SOL</span></span><small class="trade-note-v04" data-amount-note>Enter an amount between 0.001 and 100 SOL</small><span class="swap-input-error-v272" data-swap-input-error hidden role="alert"></span></label>
  <div class="trade-presets-v04" aria-label="Amount presets"><button type="button" data-amount-preset data-buy-value="0.1" data-sell-value="25">0.1</button><button type="button" data-amount-preset data-buy-value="0.5" data-sell-value="50">0.5</button><button type="button" data-amount-preset data-buy-value="1" data-sell-value="75">1</button><button type="button" data-amount-preset data-buy-value="2" data-sell-value="100">2</button></div>
  <div class="trade-receive-v04"><span class="trade-field-head-v04"><span>You receive</span><span>Estimated after quote</span></span><span class="trade-amount-row-v04"><strong data-receive-amount>—</strong><span class="trade-coin-v04" data-receive-coin>__SYMBOL__</span></span></div>
  <button class="sandbox-button primary" type="button" data-get-quote>Get buy quote</button>
  <div class="quote-result quote-result-v27" data-quote-result aria-live="polite"></div>
  <div class="trade-route-v04"><span>Route</span><b data-route-summary>SOL &rarr; Jupiter &rarr; __SYMBOL__</b></div>
  <div class="swap-warning-v27"><strong>Before you continue</strong>Price, output and route can change before wallet approval.</div>
  <label class="swap-consent"><input type="checkbox" data-swap-risk-ack>I reviewed the quote and risks.</label>
  <section class="swap-confirmation-v27" data-confirmation-summary hidden aria-live="polite"></section>
  <button class="sandbox-button primary" type="button" data-execute-swap disabled>Review buy</button>
  <div class="quote-result" data-swap-result aria-live="polite"></div>
  <p class="wallet-safety-v27"><i aria-hidden="true">&#10003;</i><span>You approve every transaction in your wallet. DexSato never holds your funds or private keys. Fees are shown in the quote and order review before wallet approval.</span></p>
</section>
__TOKEN_OBSERVATION_PANEL__
__QUALIFICATION_PANEL__
<section class="card market-snapshot-v26"><h3>Market Snapshot</h3><div class="metrics"><div class="metric"><span>Observed price</span><b class="value">__PRICE__</b></div><div class="metric"><span>24h change</span><b class="value change __CHANGE_TONE__">__CHANGE__</b></div><div class="metric"><span>Liquidity</span><b class="value">__LIQUIDITY__</b></div><div class="metric"><span>24h volume</span><b class="value">__VOLUME__</b></div><div class="metric"><span>Market cap / FDV</span><b class="value">__MARKET_CAP__</b></div><div class="metric"><span>Pair age</span><b class="value">__AGE__</b></div></div><div class="evidence"><strong>Why this token appeared</strong>__EVIDENCE__</div><div class="risk"><strong>Risk context</strong><p>__RISK__. Pool verification is not token verification. Inclusion is not an endorsement.</p></div></section>
</aside></div>
<footer><span>Experimental discovery · evidence synthesis only · not financial advice.</span><span>Market observations, indicative quotes and transaction results are distinct.</span></footer></main></div></div><script src="/static/js/dexsato_solana_discovery_swap.js?v=tw-dex-04" defer></script><script>
(function(){
  const options=[...document.querySelectorAll("[data-theme-option]")];
  function applyTheme(theme){
    const value=theme==="plain"?"plain":theme==="intel"?"intel":"current";
    if(value==="current") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme=value;

    options.forEach(button=>{
      const active=button.dataset.themeOption===value;
      button.classList.toggle("active",active);
      button.setAttribute("aria-pressed",String(active));
    });

    try{localStorage.setItem("dexsato-theme",value);}catch(error){}
  }

  let saved="current";
  try{saved=localStorage.getItem("dexsato-theme")||"current";}catch(error){}
  applyTheme(saved);

  options.forEach(button=>{
    button.addEventListener("click",()=>applyTheme(button.dataset.themeOption));
  });
})();
</script>
<script>
/* TW_DEX_07B_HEADER_WALLET_BRIDGE */
(function(){
  const headerButton=document.querySelector("[data-header-connect-wallet]");
  const jupiterButton=document.querySelector(".jupiter-v27 [data-connect-wallet]");
  if(!headerButton||!jupiterButton)return;
  headerButton.addEventListener("click",()=>jupiterButton.click());
})();
</script>
<script>
/* TOKEN_WORKSPACE_V26A_COIN_LIST_FILTER */
(function(){
  const input=document.querySelector("[data-coin-list-search]");
  const rows=[...document.querySelectorAll("[data-coin-list-rows] .coin-list-row")];
  if(!input||!rows.length)return;
  input.addEventListener("input",()=>{
    const query=(input.value||"").trim().toLowerCase();
    rows.forEach(row=>{row.hidden=Boolean(query)&&!row.textContent.toLowerCase().includes(query);});
  });
})();
</script>
<script>
/* Token Workspace v2 Decision Layout - UI only */
(function(){
  function norm(s){return (s||"").replace(/\\s+/g," ").trim().toLowerCase();}
  function cardByHeading(text){
    const needle=norm(text);
    const heading=[...document.querySelectorAll("h1,h2,h3")].find(el=>norm(el.textContent)===needle);
    return heading ? (heading.closest(".card") || heading.parentElement) : null;
  }
  function textFromMetric(root,label){
    if(!root) return "Ã¢â‚¬â€";
    const needle=norm(label);
    const metrics=[...root.querySelectorAll(".metric")];
    const metric=metrics.find(el=>{
      const span=el.querySelector("span");
      return span && norm(span.textContent).includes(needle);
    });
    if(!metric) return "Ã¢â‚¬â€";
    const value=metric.querySelector(".value,strong,b");
    return value ? value.textContent.trim() : "Ã¢â‚¬â€";
  }
  function hasCheck(root,phrase){
    if(!root) return false;
    const needle=norm(phrase);
    return [...root.querySelectorAll(".check")].some(el=>norm(el.textContent).includes(needle));
  }
  function item(label,value,security){
    const el=document.createElement("div");
    el.className="dexsato-evidence-item"+(security?" security":"");
    const lab=document.createElement("span"); lab.className="dexsato-evidence-label"; lab.textContent=label;
    const val=document.createElement("span"); val.className="dexsato-evidence-value";
    const dot=document.createElement("i"); dot.className="dexsato-evidence-dot"; dot.setAttribute("aria-hidden","true");
    const txt=document.createElement("span"); txt.textContent=value;
    val.append(dot,txt); el.append(lab,val); return el;
  }

  const market=cardByHeading("Market Snapshot");
  const jupiter=document.querySelector("[data-jupiter-sandbox]");

  if(market) market.classList.add("decision-main-v2");
  if(jupiter) jupiter.classList.add("decision-side-v2");

  if(market && jupiter && market.parentElement===jupiter.parentElement && !market.parentElement.classList.contains("workspace-right-v26")){
    market.parentElement.classList.add("decision-grid-v2");
  }

  if(market && !document.querySelector(".dexsato-evidence-strip")){
    const strip=document.createElement("section");
    strip.className="dexsato-evidence-strip";
    strip.setAttribute("aria-label","DexSato evidence summary");

    const poolOk=hasCheck(market,"exact token and pool match") || hasCheck(market,"solana token identity");
    const liquidity=textFromMetric(market,"liquidity");
    const volume=textFromMetric(market,"24h volume");
    const age=textFromMetric(market,"pair age");

    strip.append(
      item("Pool",poolOk?"Verified":"Observed",false),
      item("Liquidity",liquidity,false),
      item("Activity",volume,false),
      item("Freshness",age,false),
      item("Security","Not independently verified",true)
    );

    const title=[...market.querySelectorAll("h2,h3")].find(el=>norm(el.textContent)==="market snapshot");
    if(title) title.insertAdjacentElement("afterend",strip); else market.prepend(strip);
  }
})();
</script>
<script>

/* Token Header v2.2.2 Robust Hotfix */

(function(){

  const clean = s => (s || "").replace(/\\s+/g," ").trim().toLowerCase();



  const hero = document.querySelector(".hero");

  if(hero){

    const heroEyebrow = hero.querySelector(":scope > div:first-child > .eyebrow");

    if(heroEyebrow && clean(heroEyebrow.textContent)==="qualified exact-token workspace"){

      heroEyebrow.style.display="none";

    }



    const heroParagraph = hero.querySelector(":scope > div:first-child > p");

    if(heroParagraph){

      const text = clean(heroParagraph.textContent);

      if(

        text.includes("review observed market activity") &&

        text.includes("exact-pool identity") &&

        text.includes("disclosed risk")

      ){

        heroParagraph.style.display="none";

      }

    }



    const status = hero.querySelector(":scope > .status");

    if(status){

      const text = clean(status.textContent);

      if(

        text.includes("market data") &&

        text.includes("live") &&

        text.includes("live exact-pool observation")

      ){

        status.style.display="none";

      }

    }



    const content = hero.querySelector(":scope > div:first-child");

    if(content){

      content.style.display="block";

    }



    const h1 = hero.querySelector("h1");

    if(h1){

      h1.style.display="block";

    }



    const strip = hero.querySelector(".trader-tf-strip");

    if(strip){

      strip.style.display="grid";

    }

  }



  const identity=document.querySelector(".identity");

  if(identity){

    const identityEyebrow=identity.querySelector(".identity-head .eyebrow");

    if(identityEyebrow && clean(identityEyebrow.textContent)==="token identity"){

      identityEyebrow.style.display="none";

    }

  }

})();

</script>

<script>
/* Token Workspace v2.4 local Watch UI */
(function(){
  const button=document.querySelector("[data-watch-token]");
  if(!button) return;
  const token=button.getAttribute("data-watch-token") || "";
  const key="dexsato-token-watchlist";
  function load(){
    try{
      const value=JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(value) ? value : [];
    }catch(error){ return []; }
  }
  function paint(active){
    button.classList.toggle("active",active);
    button.innerHTML=active
      ? '<span aria-hidden="true">&#9733;</span> Watching'
      : '<span aria-hidden="true">&#9734;</span> Watch';
  }
  let watched=load();
  paint(watched.includes(token));
  button.addEventListener("click",function(){
    watched=load();
    if(watched.includes(token)){
      watched=watched.filter(item=>item!==token);
      paint(false);
    }else{
      watched.push(token);
      paint(true);
    }
    try{localStorage.setItem(key,JSON.stringify(watched));}catch(error){}
  });
})();
</script>


<script>
/* TW-DEX-03F.5 — Pre Runtime Script Probe */
/* TW-DEX-03F.6 — Pre-Runtime Error Trap */
(function(){
  var n=document.querySelector("[data-static-bootstrap-diagnostic]");
  if(n) n.textContent+=" | BEFORE LW";

  window.__dexsatoLwErrorTrap=function(kind,message){
    try{
      var probe=document.querySelector("[data-static-bootstrap-diagnostic]");
      if(!probe) return;
      var text=String(message||"unknown");
      if(text.length>180) text=text.slice(0,177)+"...";
      probe.textContent+=" | "+kind+": "+text;
    }catch(_error){}
  };

  window.addEventListener("error",function(event){
    var message=String(event&&event.message||"");
    var filename=String(event&&event.filename||"");
    var lineno=event&&event.lineno?String(event.lineno):"";
    var detail=message;
    if(filename) detail+=" @ "+filename+(lineno?":"+lineno:"");
    window.__dexsatoLwErrorTrap("LW ERROR",detail);
  },true);

  window.addEventListener("unhandledrejection",function(event){
    var reason=event&&event.reason;
    var message=String(reason&&reason.message||reason||"unknown rejection");
    window.__dexsatoLwErrorTrap("LW PROMISE",message);
  });
})();
</script>

<script>
/* TW-DEX-03D — TradingView Lightweight Charts Integration */
(function(){
  /* TW-DEX-03F.4 — Runtime Entry Probe */
  var runtimeProbe=document.querySelector("[data-static-bootstrap-diagnostic]");
  if(runtimeProbe) runtimeProbe.textContent+=" | LW ENTRY";

  const panel=document.querySelector("[data-candlestick-panel]");
  if(!panel){
    if(runtimeProbe) runtimeProbe.textContent+=" | PANEL MISSING";
    return;
  }
  if(runtimeProbe) runtimeProbe.textContent+=" | PANEL FOUND";

  const L=window.LightweightCharts;
  const container=panel.querySelector("[data-lightweight-chart]");
  const fallbackSvg=panel.querySelector("[data-candlestick-svg]");
  const empty=panel.querySelector("[data-candlestick-empty]");
  const dataNode=panel.querySelector("[data-candlestick-data]");
  const buttons=[...panel.querySelectorAll("[data-candle-timeframe]")];
  const resetButton=panel.querySelector("[data-candle-reset]");
  const liveState=panel.querySelector("[data-candle-live-state]");
  const liveUrl=panel.dataset.liveCandleUrl||"";
  const currentObservedPrice=Number(panel.dataset.currentPriceUsd||"");
  const hasCurrentObservedPrice=Number.isFinite(currentObservedPrice)&&currentObservedPrice>0;
  const ohlc={
    open:panel.querySelector("[data-ohlc-open]"),
    high:panel.querySelector("[data-ohlc-high]"),
    low:panel.querySelector("[data-ohlc-low]"),
    close:panel.querySelector("[data-ohlc-close]"),
    volume:panel.querySelector("[data-ohlc-volume]")
  };
  const diagnostic=panel.querySelector("[data-lw-runtime-diagnostic]");
  const diagnosticState={
    library:!!L,
    chartCreated:false,
    seriesCreated:false,
    rawRows:0,
    sanitizedRows:0,
    timeframe:"5m",
    setDataOk:false,
    lastError:"",
    firstTime:null,
    lastTime:null,
    firstOhlc:null,
    lastOhlc:null
  };

  function showDiagnostic(kind,message){
    if(!diagnostic) return;
    diagnostic.hidden=false;
    diagnostic.classList.add("visible");
    diagnostic.classList.toggle("error",kind==="error");
    diagnostic.classList.toggle("ok",kind==="ok");
    diagnostic.textContent=message;
  }

  function diagnosticText(prefix=""){
    const lines=[
      prefix,
      "Lightweight library: "+(diagnosticState.library?"loaded":"missing"),
      "Chart created: "+(diagnosticState.chartCreated?"yes":"no"),
      "Series created: "+(diagnosticState.seriesCreated?"yes":"no"),
      "Timeframe: "+diagnosticState.timeframe,
      "Raw rows: "+diagnosticState.rawRows,
      "Sanitized rows: "+diagnosticState.sanitizedRows,
      "setData(): "+(diagnosticState.setDataOk?"ok":"not confirmed"),
      "First time: "+(diagnosticState.firstTime??"--"),
      "Last time: "+(diagnosticState.lastTime??"--"),
      "First OHLC: "+(diagnosticState.firstOhlc??"--"),
      "Last OHLC: "+(diagnosticState.lastOhlc??"--"),
      "Error: "+(diagnosticState.lastError||"--")
    ];
    /* TW-DEX-03G — Lightweight Runtime Escape Fix */
    return lines.filter(Boolean).join("\\n");
  }

  function reportDiagnostic(kind=""){
    const finalKind=kind||(diagnosticState.lastError?"error":(diagnosticState.setDataOk?"ok":""));
    showDiagnostic(finalKind,diagnosticText());
  }

  /* TW-DEX-03F.1 — Diagnostic Bootstrap Guard
     Make diagnostics visible before any Lightweight Charts API call can throw. */
  showDiagnostic("",diagnosticText("Diagnostic bootstrap: script entered"));

  window.addEventListener("error",event=>{
    const message=String(event?.message||"");
    if(!message) return;
    diagnosticState.lastError="window.error: "+message;
    reportDiagnostic("error");
  });

  window.addEventListener("unhandledrejection",event=>{
    const reason=String(event?.reason?.message||event?.reason||"");
    if(!reason) return;
    diagnosticState.lastError="promise: "+reason;
    reportDiagnostic("error");
  });

  if(!L||!container||typeof L.createChart!=="function"||!L.CandlestickSeries||!L.HistogramSeries){
    diagnosticState.lastError="Lightweight Charts library/API unavailable";
    reportDiagnostic("error");
    if(fallbackSvg) fallbackSvg.hidden=false;
    return;
  }

  panel.dataset.lightweightActive="1";
  if(fallbackSvg) fallbackSvg.hidden=true;

  let datasets={};
  try{datasets=JSON.parse(dataNode?.textContent||"{}");}catch(error){datasets={};}

  const TIMEFRAME_SECONDS={"1m":60,"5m":300,"15m":900,"30m":1800,"1H":3600,"4H":14400};
  const state={timeframe:"5m",liveInFlight:false};
  let tradeOverlayRows=[];
  let markerPlugin=null;

  const finitePositive=value=>{
    const n=Number(value);
    return Number.isFinite(n)&&n>0?n:null;
  };

  function formatPrice(value){
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    if(Math.abs(n)>=1000) return n.toLocaleString(undefined,{maximumFractionDigits:2});
    if(Math.abs(n)>=1) return n.toLocaleString(undefined,{maximumFractionDigits:6});
    if(Math.abs(n)>=0.01) return n.toFixed(6);
    if(Math.abs(n)>=0.000001) return n.toFixed(8);
    return n.toFixed(10);
  }

  function formatVolume(value){
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    if(Math.abs(n)>=1e9) return (n/1e9).toFixed(2)+"B";
    if(Math.abs(n)>=1e6) return (n/1e6).toFixed(2)+"M";
    if(Math.abs(n)>=1e3) return (n/1e3).toFixed(2)+"K";
    return n.toFixed(2);
  }

  function precisionForPrice(value){
    const n=Math.abs(Number(value));
    if(!Number.isFinite(n)||n<=0) return 8;
    if(n>=100) return 2;
    if(n>=1) return 4;
    if(n>=0.01) return 6;
    if(n>=0.000001) return 8;
    return 10;
  }

  function updateOHLC(row){
    if(!row){
      Object.values(ohlc).forEach(node=>{if(node) node.textContent="--";});
      return;
    }
    if(ohlc.open) ohlc.open.textContent=formatPrice(row.open);
    if(ohlc.high) ohlc.high.textContent=formatPrice(row.high);
    if(ohlc.low) ohlc.low.textContent=formatPrice(row.low);
    if(ohlc.close) ohlc.close.textContent=formatPrice(row.close);
    if(ohlc.volume) ohlc.volume.textContent=formatVolume(row.volume);
  }

  function setLiveState(ok){
    if(!liveState) return;
    liveState.classList.toggle("stale",!ok);
    const textNode=[...liveState.childNodes].find(node=>node.nodeType===Node.TEXT_NODE);
    if(textNode) textNode.textContent=ok?"LIVE":"STALE";
  }

  function normalizeRows(rows){
    const source=Array.isArray(rows)?rows:[];
    const result=[];
    const seen=new Set();

    function sanitizeOhlc(row){
      const open=finitePositive(row.open);
      const high=finitePositive(row.high);
      const low=finitePositive(row.low);
      const close=finitePositive(row.close);

      /* TW-DEX-03J.1 — Observed Candle Sanitizer
         Accept only complete provider-owned OHLC. Never repair rejected history
         with the current token price or manufacture missing candle fields. */
      if([open,high,low,close].some(value=>value===null)) return null;
      if(!(high>=open&&high>=close&&low<=open&&low<=close&&high>=low)) return null;

      const epsilon=Math.max(Math.abs(close)*1e-12,1e-18);
      const visualFlat=
        Math.abs(close-open)<=epsilon&&
        Math.abs(high-low)<=epsilon;
      return {
        open,
        high,
        low,
        close,
        visualFlat
      };
    }

    source.forEach(row=>{
      if(!row||typeof row!=="object") return;
      const time=Math.floor(Number(row.time));
      if(!Number.isFinite(time)||seen.has(time)) return;

      const clean=sanitizeOhlc(row);
      if(!clean) return;

      const volume=Math.max(0,Number(row.volume)||0);
      seen.add(time);
      result.push({
        time,
        open:clean.open,
        high:clean.high,
        low:clean.low,
        close:clean.close,
        volume,
        visualFlat:!!clean.visualFlat
      });
    });
    result.sort((a,b)=>a.time-b.time);
    return result;
  }

  let chart;
  try{
    chart=L.createChart(container,{
    autoSize:true,
    height:450,
    layout:{
      background:{type:L.ColorType.Solid,color:"#0A1118"},
      textColor:"#7C8CA0",
      fontSize:10,
      fontFamily:'"JetBrains Mono","Cascadia Mono",Consolas,monospace',
      attributionLogo:true
    },
    grid:{
      vertLines:{color:"#17212B"},
      horzLines:{color:"#17212B"}
    },
    rightPriceScale:{
      borderColor:"#2A3847",
      scaleMargins:{top:.08,bottom:.24}
    },
    timeScale:{
      borderColor:"#2A3847",
      timeVisible:true,
      secondsVisible:false,
      rightOffset:4,
      barSpacing:8,
      minBarSpacing:3,
      fixLeftEdge:false,
      fixRightEdge:false
    },
    crosshair:{
      mode:L.CrosshairMode.Normal,
      vertLine:{color:"#607084",width:1,labelBackgroundColor:"#10171F"},
      horzLine:{color:"#607084",width:1,labelBackgroundColor:"#10171F"}
    },
    handleScroll:{
      mouseWheel:true,
      pressedMouseMove:true,
      horzTouchDrag:true,
      vertTouchDrag:false
    },
    handleScale:{
      axisPressedMouseMove:true,
      mouseWheel:true,
      pinch:true,
      axisDoubleClickReset:true
    },
    kineticScroll:{mouse:true,touch:true}
    });
    diagnosticState.chartCreated=true;
  }catch(error){
    diagnosticState.lastError="createChart: "+String(error?.message||error);
    reportDiagnostic("error");
    if(fallbackSvg) fallbackSvg.hidden=false;
    panel.dataset.lightweightActive="0";
    return;
  }

  const precision=precisionForPrice(currentObservedPrice);
  let candleSeries,volumeSeries,flatVisibilitySeries=null;
  try{
    candleSeries=chart.addSeries(L.CandlestickSeries,{
    upColor:"#31D89C",
    downColor:"#FF5C7A",
    wickUpColor:"#31D89C",
    wickDownColor:"#FF5C7A",
    borderUpColor:"#31D89C",
    borderDownColor:"#FF5C7A",
    priceLineVisible:false,
    lastValueVisible:true,
    priceFormat:{
      type:"price",
      precision,
      minMove:Math.pow(10,-precision)
    }
  });

    volumeSeries=chart.addSeries(L.HistogramSeries,{
      priceFormat:{type:"volume"},
      priceScaleId:"",
      lastValueVisible:false,
      priceLineVisible:false
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins:{top:.82,bottom:0}
    });

    /* TW-DEX-03J — Flat Candle Visibility Polish
       Flat candles remain numerically flat; a point-only LineSeries gives them a small
       visible body marker without fabricating OHLC movement or changing price values. */
    if(L.LineSeries){
      flatVisibilitySeries=chart.addSeries(L.LineSeries,{
        color:"#4CF4D6",
        lineVisible:false,
        pointMarkersVisible:true,
        pointMarkersRadius:2.4,
        crosshairMarkerVisible:false,
        priceLineVisible:false,
        lastValueVisible:false,
        priceFormat:{
          type:"price",
          precision,
          minMove:Math.pow(10,-precision)
        }
      });
    }

    diagnosticState.seriesCreated=true;
  }catch(error){
    diagnosticState.lastError="addSeries: "+String(error?.message||error);
    reportDiagnostic("error");
    if(fallbackSvg) fallbackSvg.hidden=false;
    panel.dataset.lightweightActive="0";
    try{chart.remove();}catch(_error){}
    return;
  }

  let currentPriceLine=null;
  if(hasCurrentObservedPrice){
    try{
      currentPriceLine=candleSeries.createPriceLine({
        price:currentObservedPrice,
        color:"#4CF4D6",
        lineWidth:1,
        lineStyle:L.LineStyle.Dashed,
        axisLabelVisible:true,
        title:""
      });
    }catch(error){
      diagnosticState.lastError="createPriceLine: "+String(error?.message||error);
      reportDiagnostic("error");
    }
  }

  function tradeTimestampSeconds(value){
    const ms=Date.parse(String(value||""));
    return Number.isFinite(ms)?Math.floor(ms/1000):null;
  }

  function candleBucket(timestamp,timeframe){
    const seconds=TIMEFRAME_SECONDS[timeframe]||60;
    return Math.floor(Number(timestamp)/seconds)*seconds;
  }

  function updateTradeMarkers(rows){
    if(typeof L.createSeriesMarkers!=="function") return;
    const candles=normalizeRows(datasets[state.timeframe]);
    const candleTimes=new Set(candles.map(row=>row.time));
    const buckets=new Map();

    (Array.isArray(rows)?rows:[]).slice(0,30).forEach(item=>{
      if(!item||typeof item!=="object") return;
      const ts=tradeTimestampSeconds(item.timestamp);
      const side=String(item.side||"").toUpperCase();
      if(!Number.isFinite(ts)||!["BUY","SELL"].includes(side)) return;
      const bucket=candleBucket(ts,state.timeframe);
      if(!candleTimes.has(bucket)) return;
      const key=side+":"+bucket;
      const current=buckets.get(key)||{side,time:bucket,count:0};
      current.count+=1;
      buckets.set(key,current);
    });

    const markers=[...buckets.values()]
      .sort((a,b)=>a.time-b.time)
      .map(item=>({
        time:item.time,
        position:item.side==="BUY"?"belowBar":"aboveBar",
        color:item.side==="BUY"?"#31D89C":"#FF5C7A",
        shape:item.side==="BUY"?"arrowUp":"arrowDown",
        text:item.count>1?String(item.count):"",
        size:item.count>2?1.05:.75
      }));

    if(!markerPlugin){
      markerPlugin=L.createSeriesMarkers(candleSeries,markers,{autoScale:false});
    }else{
      markerPlugin.setMarkers(markers);
    }
  }

  function render(fit=false){
    buttons.forEach(button=>{
      button.classList.toggle("active",button.dataset.candleTimeframe===state.timeframe);
    });

    const rawRows=Array.isArray(datasets[state.timeframe])?datasets[state.timeframe]:[];
    const rows=normalizeRows(rawRows);
    diagnosticState.timeframe=state.timeframe;
    diagnosticState.rawRows=rawRows.length;
    diagnosticState.sanitizedRows=rows.length;
    diagnosticState.firstTime=rows.length?rows[0].time:null;
    diagnosticState.lastTime=rows.length?rows[rows.length-1].time:null;
    diagnosticState.firstOhlc=rows.length?JSON.stringify({
      o:rows[0].open,h:rows[0].high,l:rows[0].low,c:rows[0].close
    }):null;
    diagnosticState.lastOhlc=rows.length?JSON.stringify({
      o:rows[rows.length-1].open,h:rows[rows.length-1].high,l:rows[rows.length-1].low,c:rows[rows.length-1].close
    }):null;
    diagnosticState.setDataOk=false;
    diagnosticState.lastError="";

    if(!rows.length){
      try{
        candleSeries.setData([]);
        volumeSeries.setData([]);
        if(flatVisibilitySeries) flatVisibilitySeries.setData([]);
        diagnosticState.setDataOk=true;
      }catch(error){
        diagnosticState.lastError="setData(empty): "+String(error?.message||error);
      }
      if(empty){
        empty.textContent="No renderable exact-pool candles for this timeframe.";
        empty.hidden=false;
      }
      updateOHLC(null);
      updateTradeMarkers(tradeOverlayRows);
      reportDiagnostic(diagnosticState.lastError?"error":"");
      return;
    }

    if(empty) empty.hidden=true;

    try{
      candleSeries.setData(rows.map(row=>({
        time:row.time,open:row.open,high:row.high,low:row.low,close:row.close
      })));
      volumeSeries.setData(rows.map(row=>({
        time:row.time,
        value:row.volume,
        color:row.close>=row.open?"rgba(49,216,156,.34)":"rgba(255,92,122,.34)"
      })));
      if(flatVisibilitySeries){
        flatVisibilitySeries.setData(
          rows
            .filter(row=>row.visualFlat)
            .map(row=>({time:row.time,value:row.close}))
        );
      }
      diagnosticState.setDataOk=true;
    }catch(error){
      diagnosticState.lastError="setData: "+String(error?.message||error);
      reportDiagnostic("error");
      if(fallbackSvg) fallbackSvg.hidden=false;
      return;
    }

    const latest=rows[rows.length-1];
    updateOHLC(latest);
    updateTradeMarkers(tradeOverlayRows);

    try{
      if(fit) chart.timeScale().fitContent();
    }catch(error){
      diagnosticState.lastError="fitContent: "+String(error?.message||error);
    }
    reportDiagnostic(diagnosticState.lastError?"error":"ok");
  }

  chart.subscribeCrosshairMove(param=>{
    if(!param||!param.time){
      const rows=normalizeRows(datasets[state.timeframe]);
      updateOHLC(rows.length?rows[rows.length-1]:null);
      return;
    }
    const row=param.seriesData?.get(candleSeries);
    if(row&&Number.isFinite(Number(row.open))) updateOHLC(row);
  });

  async function pollLive(force=false){
    if(!liveUrl||state.liveInFlight) return;
    if(document.hidden&&!force) return;
    state.liveInFlight=true;
    try{
      const response=await fetch(
        liveUrl+"?timeframe="+encodeURIComponent(state.timeframe),
        {
          method:"GET",
          credentials:"same-origin",
          headers:{"Accept":"application/json"},
          cache:"no-store"
        }
      );
      if(!response.ok) throw new Error("live candle unavailable");
      const payload=await response.json();
      const incoming=Array.isArray(payload.candles)?payload.candles:[];
      if(payload.timeframe===state.timeframe&&incoming.length){
        datasets[state.timeframe]=incoming;
        render(false);
      }
      setLiveState(true);
    }catch(error){
      setLiveState(false);
    }finally{
      state.liveInFlight=false;
    }
  }

  buttons.forEach(button=>{
    button.addEventListener("click",()=>{
      state.timeframe=button.dataset.candleTimeframe;
      render(true);
      pollLive(true);
    });
  });

  resetButton?.addEventListener("click",()=>{
    chart.priceScale("right").applyOptions({autoScale:true});
    chart.timeScale().fitContent();
  });

  window.addEventListener("dexsato:transactions-updated",event=>{
    const rows=event?.detail?.transactions;
    tradeOverlayRows=Array.isArray(rows)?rows:[];
    updateTradeMarkers(tradeOverlayRows);
  });

  render(true);
  window.setTimeout(()=>pollLive(true),1200);
  window.setInterval(()=>pollLive(false),10000);
  document.addEventListener("visibilitychange",()=>{
    if(!document.hidden) pollLive(true);
  });
})();
</script>

<script>
/* TW-DEX-03F.5 — Post Runtime Script Probe */
/* TW-DEX-03F.6 — Runtime Script Inspection */
(function(){
  var n=document.querySelector("[data-static-bootstrap-diagnostic]");
  if(n) n.textContent+=" | AFTER LW";

  try{
    var scripts=[].slice.call(document.scripts||[]);
    var runtimeScript=scripts.find(function(script){
      return String(script.textContent||"").indexOf(
        "TW-DEX-03D — TradingView Lightweight Charts Integration"
      )!==-1;
    });

    if(!runtimeScript){
      if(n) n.textContent+=" | LW SCRIPT MISSING";
      return;
    }

    var source=String(runtimeScript.textContent||"");
    var type=String(runtimeScript.type||"classic");
    var hasEntry=source.indexOf("LW ENTRY")!==-1;
    if(n){
      n.textContent+=" | LW SCRIPT FOUND";
      n.textContent+=" | TYPE "+type;
      n.textContent+=" | LEN "+source.length;
      n.textContent+=" | ENTRY "+(hasEntry?"YES":"NO");
    }
  }catch(error){
    if(window.__dexsatoLwErrorTrap){
      window.__dexsatoLwErrorTrap("LW INSPECT",error&&error.message||error);
    }
  }
})();
</script>

<script>
/* CHART_V21_INTERACTIVE_TRADING_CHART */
(function(){
  const panel=document.querySelector("[data-candlestick-panel]");
  if(!panel) return;
  if(panel.dataset.lightweightActive==="1") return;

  const svg=panel.querySelector("[data-candlestick-svg]");
  const empty=panel.querySelector("[data-candlestick-empty]");
  const dataNode=panel.querySelector("[data-candlestick-data]");
  const buttons=[...panel.querySelectorAll("[data-candle-timeframe]")];
  const resetButton=panel.querySelector("[data-candle-reset]");
  const liveState=panel.querySelector("[data-candle-live-state]");
  const liveUrl=panel.dataset.liveCandleUrl||"";
  const currentObservedPrice=Number(panel.dataset.currentPriceUsd||"");
  const hasCurrentObservedPrice=Number.isFinite(currentObservedPrice)&&currentObservedPrice>0;
  const ohlc={
    open:panel.querySelector("[data-ohlc-open]"),
    high:panel.querySelector("[data-ohlc-high]"),
    low:panel.querySelector("[data-ohlc-low]"),
    close:panel.querySelector("[data-ohlc-close]"),
    volume:panel.querySelector("[data-ohlc-volume]")
  };

  let datasets={};
  try{datasets=JSON.parse(dataNode.textContent||"{}");}catch(error){datasets={};}

  const NS="http://www.w3.org/2000/svg";
  const make=(name,attrs={})=>{
    const el=document.createElementNS(NS,name);
    Object.entries(attrs).forEach(([key,value])=>el.setAttribute(key,String(value)));
    return el;
  };
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));

  const state={timeframe:"5m",visibleCount:60,offset:0,dragging:false,dragStartX:0,dragStartOffset:0,geometry:null,liveInFlight:false};

  /* CHART_V23_TRADE_OVERLAY */
  let tradeOverlayRows=[];
  let tradeTooltip=null;
  const TIMEFRAME_SECONDS={"1m":60,"5m":300,"15m":900,"30m":1800,"1H":3600,"4H":14400};

  function ensureTradeTooltip(){
    if(tradeTooltip) return tradeTooltip;
    const stage=panel.querySelector(".candlestick-stage");
    if(!stage) return null;
    tradeTooltip=document.createElement("div");
    tradeTooltip.className="candlestick-trade-tooltip";
    tradeTooltip.hidden=true;
    stage.append(tradeTooltip);
    return tradeTooltip;
  }

  function tradeTimestampSeconds(value){
    const ms=Date.parse(String(value||""));
    return Number.isFinite(ms)?Math.floor(ms/1000):null;
  }

  function tradeUsd(value){
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    if(Math.abs(n)>=1000) return "$"+(n/1000).toFixed(n>=10000?1:2)+"K";
    return "$"+n.toLocaleString(undefined,{
      minimumFractionDigits:n<1?4:2,
      maximumFractionDigits:n<1?4:2
    });
  }

  function tradeTime(value){
    const d=new Date(String(value||""));
    if(Number.isNaN(d.getTime())) return "--";
    return d.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"});
  }

  function candleBucket(timestamp,timeframe){
    const seconds=TIMEFRAME_SECONDS[timeframe]||60;
    return Math.floor(Number(timestamp)/seconds)*seconds;
  }

  /* CHART_V24_TRADE_SIZE_INTELLIGENCE */
  function tradeSizeThresholds(values){
    const sorted=(Array.isArray(values)?values:[])
      .map(Number)
      .filter(value=>Number.isFinite(value)&&value>=0)
      .sort((a,b)=>a-b);
    if(!sorted.length) return {p50:0,p80:0};
    const quantile=q=>{
      const pos=(sorted.length-1)*q;
      const lower=Math.floor(pos),upper=Math.ceil(pos);
      if(lower===upper) return sorted[lower];
      const weight=pos-lower;
      return sorted[lower]*(1-weight)+sorted[upper]*weight;
    };
    return {p50:quantile(.50),p80:quantile(.80)};
  }

  function tradeSizeLabel(value,thresholds){
    const n=Number(value);
    if(!Number.isFinite(n)||n<0) return "SMALL";
    if(n>thresholds.p80) return "LARGE";
    if(n>thresholds.p50) return "MEDIUM";
    return "SMALL";
  }

  function tradeOverlayBuckets(rows,timeframe){
    const buckets=new Map();
    (Array.isArray(rows)?rows:[]).slice(0,30).forEach(item=>{
      if(!item||typeof item!=="object") return;
      const ts=tradeTimestampSeconds(item.timestamp);
      const side=String(item.side||"").toUpperCase();
      const volume=Number(item.volume_usd);
      if(!Number.isFinite(ts)||!["BUY","SELL"].includes(side)||!Number.isFinite(volume)) return;
      const key=candleBucket(ts,timeframe);
      if(!buckets.has(key)) buckets.set(key,{BUY:[],SELL:[]});
      buckets.get(key)[side].push({timestamp:item.timestamp,volume,side});
    });
    return buckets;
  }

  function showTradeTooltip(event,summary){
    const tip=ensureTradeTooltip();
    if(!tip) return;
    tip.classList.remove("buy","sell");
    tip.classList.add(summary.side.toLowerCase());
    const total=summary.trades.reduce((sum,item)=>sum+item.volume,0);
    const largest=summary.trades.reduce((best,item)=>!best||item.volume>best.volume?item:best,null);
    tip.replaceChildren();
    const title=document.createElement("b");
    title.textContent=summary.side+" · "+tradeUsd(total);
    const detail=document.createElement("span");
    detail.textContent="Trade size: "+summary.size+" · "+summary.trades.length+" trade"+(summary.trades.length===1?"":"s")+" · "+tradeTime(largest?.timestamp);
    tip.append(title,detail);
    tip.hidden=false;

    const stage=panel.querySelector(".candlestick-stage");
    const rect=stage?.getBoundingClientRect();
    if(rect){
      tip.style.left=Math.max(8,Math.min(rect.width-230,event.clientX-rect.left+12))+"px";
      tip.style.top=Math.max(8,event.clientY-rect.top-46)+"px";
    }
  }

  function hideTradeTooltip(){
    if(tradeTooltip) tradeTooltip.hidden=true;
  }

  function drawTradeOverlay(visible,slot,left,y){
    if(!visible.length||!tradeOverlayRows.length) return;
    const buckets=tradeOverlayBuckets(tradeOverlayRows,state.timeframe);
    const volumeValues=tradeOverlayRows
      .slice(0,30)
      .map(item=>Number(item?.volume_usd))
      .filter(Number.isFinite);
    const maxTrade=Math.max(...volumeValues,1);
    /* CHART_V24_TRADE_SIZE_INTELLIGENCE */
    const sizeThresholds=tradeSizeThresholds(volumeValues);

    visible.forEach((row,index)=>{
      const bucket=buckets.get(candleBucket(row.time,state.timeframe));
      if(!bucket) return;
      const x=left+slot*(index+.5);

      ["BUY","SELL"].forEach(side=>{
        const trades=bucket[side];
        if(!trades.length) return;
        const total=trades.reduce((sum,item)=>sum+item.volume,0);
        const largest=Math.max(...trades.map(item=>item.volume),0);
        /* CHART_V24_TRADE_SIZE_INTELLIGENCE */
        const size=tradeSizeLabel(largest,sizeThresholds);
        const radius=size==="LARGE"?8:size==="MEDIUM"?6:4.5;
        const anchor=side==="BUY"?Number(row.low):Number(row.high);
        if(!Number.isFinite(anchor)) return;
        const markerY=side==="BUY"?y(anchor)+12:y(anchor)-12;
        const points=side==="BUY"
          ? `${x},${markerY-5} ${x-radius},${markerY+4} ${x+radius},${markerY+4}`
          : `${x},${markerY+5} ${x-radius},${markerY-4} ${x+radius},${markerY-4}`;

        const marker=make("polygon",{
          points,
          class:"candlestick-trade-marker "+side.toLowerCase()+(largest>=maxTrade*.65?" large":"")+" size-"+size.toLowerCase()
        });
        svg.append(marker);

        if(trades.length>1){
          const count=make("text",{
            x:x+(radius+3),
            y:markerY+3,
            class:"candlestick-trade-count"
          });
          count.textContent=String(trades.length);
          svg.append(count);
        }

        const hit=make("circle",{
          cx:x,cy:markerY,r:Math.max(10,radius+4),
          class:"candlestick-trade-hit",
          "data-trade-overlay-hit":"1"
        });
        hit.addEventListener("pointerenter",event=>showTradeTooltip(event,{side,trades,total,size}));
        hit.addEventListener("pointermove",event=>showTradeTooltip(event,{side,trades,total,size}));
        hit.addEventListener("pointerleave",hideTradeTooltip);
        svg.append(hit);
      });
    });
  }

  window.addEventListener("dexsato:transactions-updated",event=>{
    const rows=event?.detail?.transactions;
    tradeOverlayRows=Array.isArray(rows)?rows:[];
    draw();
  });

  function formatPrice(value){
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    if(Math.abs(n)>=1000) return n.toLocaleString(undefined,{maximumFractionDigits:2});
    if(Math.abs(n)>=1) return n.toLocaleString(undefined,{maximumFractionDigits:6});
    if(Math.abs(n)>=0.01) return n.toFixed(6);
    return n.toFixed(8);
  }

  function formatVolume(value){
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    if(Math.abs(n)>=1e9) return (n/1e9).toFixed(2)+"B";
    if(Math.abs(n)>=1e6) return (n/1e6).toFixed(2)+"M";
    if(Math.abs(n)>=1e3) return (n/1e3).toFixed(2)+"K";
    return n.toFixed(2);
  }

  function formatTime(timestamp,timeframe){
    const n=Number(timestamp);
    if(!Number.isFinite(n)) return "";
    const d=new Date(n*1000);
    const short=["1m","5m","15m","30m","1H"].includes(timeframe);
    return short
      ? d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})
      : d.toLocaleDateString([], {month:"short",day:"numeric"})+" "+d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  }

  function updateOHLC(row){
    if(!row){
      Object.values(ohlc).forEach(node=>{if(node) node.textContent="--";});
      return;
    }
    if(ohlc.open) ohlc.open.textContent=formatPrice(row.open);
    if(ohlc.high) ohlc.high.textContent=formatPrice(row.high);
    if(ohlc.low) ohlc.low.textContent=formatPrice(row.low);
    if(ohlc.close) ohlc.close.textContent=formatPrice(row.close);
    if(ohlc.volume) ohlc.volume.textContent=formatVolume(row.volume);
  }

  function currentRows(){
    const all=Array.isArray(datasets[state.timeframe]) ? datasets[state.timeframe] : [];
    if(!all.length) return {all,visible:[],start:0};
    state.visibleCount=clamp(state.visibleCount,8,Math.min(120,all.length));
    const maxOffset=Math.max(0,all.length-state.visibleCount);
    state.offset=clamp(state.offset,0,maxOffset);
    const end=all.length-state.offset;
    const start=Math.max(0,end-state.visibleCount);
    return {all,visible:all.slice(start,end),start};
  }

  function draw(){
    svg.replaceChildren();
    const {all,visible,start}=currentRows();

    buttons.forEach(button=>{
      button.classList.toggle("active",button.dataset.candleTimeframe===state.timeframe);
    });

    if(!visible.length){
      empty.hidden=false;
      updateOHLC(null);
      state.geometry=null;
      return;
    }
    empty.hidden=true;

    const left=18,right=900,priceRight=978;
    const priceTop=18,priceBottom=300;
    const volumeTop=315,volumeBottom=380;
    const timeY=408;

    /* TW-DEX-03A — Chart Price Scale Guard
       Protect the visual Y-axis from malformed/extreme OHLC points without mutating source candles. */
    const finitePositive=value=>{
      const n=Number(value);
      return Number.isFinite(n)&&n>0?n:null;
    };
    const median=items=>{
      if(!items.length) return null;
      const sorted=[...items].sort((a,b)=>a-b);
      const middle=Math.floor(sorted.length/2);
      return sorted.length%2 ? sorted[middle] : (sorted[middle-1]+sorted[middle])/2;
    };

    const closeValues=visible
      .map(row=>finitePositive(row.close))
      .filter(value=>value!==null);
    /* TW-DEX-03C — Cross-Timeframe Current Price Anchor
       Use the production observed token price as the canonical visual anchor for every
       timeframe. Fall back to newest valid candle close only when current price is absent. */
    const latestClose=[...visible].reverse()
      .map(row=>finitePositive(row.close))
      .find(value=>value!==null);
    const fallbackAnchor=latestClose!==undefined ? latestClose : median(closeValues);
    const anchor=hasCurrentObservedPrice ? currentObservedPrice : fallbackAnchor;

    const allValues=[];
    visible.forEach(row=>{
      [row.high,row.low,row.open,row.close].forEach(value=>{
        const n=finitePositive(value);
        if(n!==null) allValues.push(n);
      });
    });
    if(!allValues.length&&!(anchor!==null&&anchor!==undefined&&anchor>0)){
      empty.hidden=false;
      updateOHLC(null);
      state.geometry=null;
      return;
    }

    let scaleValues=allValues;
    let scaleGuardLow=null,scaleGuardHigh=null;
    if(anchor!==null&&anchor!==undefined&&anchor>0){
      scaleGuardLow=anchor/100;
      scaleGuardHigh=anchor*100;
      const guarded=allValues.filter(value=>value>=scaleGuardLow&&value<=scaleGuardHigh);
      if(guarded.length>=4){
        scaleValues=guarded;
      }else if(hasCurrentObservedPrice){
        /* No compatible candle evidence in this timeframe: keep the axis honest around
           current production price instead of falling back to stale/malformed history. */
        scaleValues=[anchor*.99,anchor,anchor*1.01];
      }else{
        scaleGuardLow=null;
        scaleGuardHigh=null;
      }
    }

    let low=Math.min(...scaleValues),high=Math.max(...scaleValues),spread=high-low;
    const renderLow=scaleGuardLow,renderHigh=scaleGuardHigh;
    if(!spread){
      spread=Math.max(Math.abs(high)*0.02,1e-12);
      low-=spread/2; high+=spread/2;
    }else{
      const pad=spread*.08; low-=pad; high+=pad; spread=high-low;
    }

    const maxVolume=Math.max(...visible.map(row=>Number(row.volume)||0),1);
    const y=value=>priceTop+(high-Number(value))*(priceBottom-priceTop)/spread;
    const priceFromY=py=>high-((py-priceTop)/(priceBottom-priceTop))*spread;

    for(let i=0;i<5;i++){
      const gy=priceTop+i*(priceBottom-priceTop)/4;
      svg.append(make("line",{x1:left,y1:gy,x2:priceRight,y2:gy,class:"candlestick-grid"}));
      const label=make("text",{x:priceRight-4,y:gy-4,"text-anchor":"end",class:"candlestick-axis-label"});
      label.textContent=formatPrice(high-i*spread/4);
      svg.append(label);
    }

    svg.append(make("line",{x1:left,y1:volumeTop-6,x2:priceRight,y2:volumeTop-6,class:"candlestick-axis-line"}));

    const slot=(right-left)/visible.length;
    const bodyWidth=Math.max(2,Math.min(12,slot*.62));

    visible.forEach((row,index)=>{
      const open=Number(row.open),close=Number(row.close),highValue=Number(row.high),lowValue=Number(row.low),volume=Number(row.volume)||0;
      if(![open,close,highValue,lowValue].every(Number.isFinite)) return;
      if([open,close,highValue,lowValue].some(value=>value<=0)) return;
      if(renderLow!==null&&renderHigh!==null&&
         [open,close,highValue,lowValue].some(value=>value<renderLow||value>renderHigh)) return;
      const x=left+slot*(index+.5),up=close>=open,cls=up?"candlestick-up":"candlestick-down";
      const yOpen=y(open),yClose=y(close),yHigh=y(highValue),yLow=y(lowValue);

      const volumeHeight=(volume/maxVolume)*(volumeBottom-volumeTop);
      svg.append(make("rect",{x:x-bodyWidth/2,y:volumeBottom-volumeHeight,width:bodyWidth,height:Math.max(1,volumeHeight),class:"candlestick-volume "+cls}));
      svg.append(make("line",{x1:x,y1:yHigh,x2:x,y2:yLow,class:"candlestick-wick "+cls}));
      svg.append(make("rect",{x:x-bodyWidth/2,y:Math.min(yOpen,yClose),width:bodyWidth,height:Math.max(1.5,Math.abs(yOpen-yClose)),rx:.5,class:"candlestick-body "+cls}));
    });

    /* CHART_V23_TRADE_OVERLAY */
    drawTradeOverlay(visible,slot,left,y);

    const timeStep=Math.max(1,Math.floor(visible.length/6));
    visible.forEach((row,index)=>{
      if(index%timeStep!==0 && index!==visible.length-1) return;
      const x=left+slot*(index+.5);
      const label=make("text",{x:x,y:timeY,"text-anchor":"middle",class:"candlestick-time-label"});
      label.textContent=formatTime(row.time,state.timeframe);
      svg.append(label);
    });

    const last=visible[visible.length-1],lastPrice=Number(last.close);
    const displayPrice=hasCurrentObservedPrice ? currentObservedPrice : lastPrice;
    const displayPriceInScale=
      Number.isFinite(displayPrice)&&displayPrice>0&&
      (renderLow===null||renderHigh===null||(displayPrice>=renderLow&&displayPrice<=renderHigh));
    if(displayPriceInScale){
      const py=y(displayPrice);
      svg.append(make("line",{x1:left,y1:py,x2:priceRight,y2:py,class:"candlestick-price-line"}));
      svg.append(make("rect",{x:905,y:py-10,width:72,height:20,rx:3,class:"candlestick-price-tag"}));
      const text=make("text",{x:941,y:py+4,"text-anchor":"middle",class:"candlestick-price-tag-text"});
      text.textContent=formatPrice(displayPrice); svg.append(text);
    }

    updateOHLC(last);
    state.geometry={all,visible,start,left,right,priceRight,priceTop,priceBottom,volumeTop,volumeBottom,slot,low,high,spread,y,priceFromY};
  }

  function drawCrosshair(clientX,clientY){
    draw();
    const g=state.geometry;
    if(!g||!g.visible.length) return;
    const rect=svg.getBoundingClientRect();
    const sx=(clientX-rect.left)*(1000/rect.width),sy=(clientY-rect.top)*(420/rect.height);
    if(sx<g.left||sx>g.right||sy<g.priceTop||sy>g.volumeBottom) return;

    const index=clamp(Math.floor((sx-g.left)/g.slot),0,g.visible.length-1);
    const row=g.visible[index],candleX=g.left+g.slot*(index+.5);
    svg.append(make("line",{x1:candleX,y1:g.priceTop,x2:candleX,y2:g.volumeBottom,class:"candlestick-crosshair"}));
    svg.append(make("line",{x1:g.left,y1:sy,x2:g.priceRight,y2:sy,class:"candlestick-crosshair"}));

    const price=g.priceFromY(clamp(sy,g.priceTop,g.priceBottom));
    svg.append(make("rect",{x:905,y:sy-10,width:72,height:20,rx:3,class:"candlestick-cross-label"}));
    const priceText=make("text",{x:941,y:sy+4,"text-anchor":"middle",class:"candlestick-cross-label-text"});
    priceText.textContent=formatPrice(price); svg.append(priceText);

    const timeText=formatTime(row.time,state.timeframe),timeWidth=Math.max(58,timeText.length*6.2+14);
    const timeX=clamp(candleX-timeWidth/2,g.left,g.right-timeWidth);
    svg.append(make("rect",{x:timeX,y:386,width:timeWidth,height:22,rx:3,class:"candlestick-cross-label"}));
    const timeLabel=make("text",{x:timeX+timeWidth/2,y:401,"text-anchor":"middle",class:"candlestick-cross-label-text"});
    timeLabel.textContent=timeText; svg.append(timeLabel);

    updateOHLC(row);
  }


  function setLiveState(ok){
    if(!liveState) return;
    liveState.classList.toggle("stale",!ok);
    const textNode=[...liveState.childNodes].find(node=>node.nodeType===Node.TEXT_NODE);
    if(textNode) textNode.textContent=ok?"LIVE":"STALE";
  }

  async function pollLive(force=false){
    if(!liveUrl||state.liveInFlight) return;
    if(document.hidden&&!force) return;

    state.liveInFlight=true;
    try{
      const response=await fetch(
        liveUrl+"?timeframe="+encodeURIComponent(state.timeframe),
        {
          method:"GET",
          credentials:"same-origin",
          headers:{"Accept":"application/json"},
          cache:"no-store"
        }
      );
      if(!response.ok) throw new Error("live candle unavailable");

      const payload=await response.json();
      const incoming=Array.isArray(payload.candles)?payload.candles:[];
      if(payload.timeframe!==state.timeframe||!incoming.length){
        setLiveState(true);
        return;
      }

      const previous=Array.isArray(datasets[state.timeframe])?datasets[state.timeframe]:[];
      const previousLength=previous.length;
      const wasPanned=state.offset>0;

      datasets[state.timeframe]=incoming;

      if(wasPanned&&incoming.length>previousLength){
        state.offset+=incoming.length-previousLength;
      }

      draw();
      setLiveState(true);
    }catch(error){
      setLiveState(false);
    }finally{
      state.liveInFlight=false;
    }
  }

  buttons.forEach(button=>{
    button.addEventListener("click",()=>{
      state.timeframe=button.dataset.candleTimeframe;
      const all=Array.isArray(datasets[state.timeframe]) ? datasets[state.timeframe] : [];
      state.visibleCount=Math.min(60,Math.max(8,all.length||60));
      state.offset=0;
      draw();
      pollLive(true);
    });
  });

  resetButton?.addEventListener("click",()=>{
    const all=Array.isArray(datasets[state.timeframe]) ? datasets[state.timeframe] : [];
    state.visibleCount=Math.min(60,Math.max(8,all.length||60));
    state.offset=0;
    draw();
  });

  svg.addEventListener("wheel",event=>{
    const all=Array.isArray(datasets[state.timeframe]) ? datasets[state.timeframe] : [];
    if(all.length<2) return;
    event.preventDefault();
    state.visibleCount=clamp(state.visibleCount+(event.deltaY>0?6:-6),8,Math.min(120,all.length));
    state.offset=clamp(state.offset,0,Math.max(0,all.length-state.visibleCount));
    draw();
  },{passive:false});

  svg.addEventListener("pointerdown",event=>{
    if(event.button!==0) return;
    state.dragging=true; state.dragStartX=event.clientX; state.dragStartOffset=state.offset;
    svg.setPointerCapture?.(event.pointerId); svg.style.cursor="grabbing";
  });

  svg.addEventListener("pointermove",event=>{
    if(state.dragging){
      const g=state.geometry;
      if(!g) return;
      const rect=svg.getBoundingClientRect(),candlePx=(g.slot/1000)*rect.width;
      if(candlePx>0){
        state.offset=Math.round(state.dragStartOffset+((event.clientX-state.dragStartX)/candlePx));
        const all=Array.isArray(datasets[state.timeframe]) ? datasets[state.timeframe] : [];
        state.offset=clamp(state.offset,0,Math.max(0,all.length-state.visibleCount));
        draw();
      }
    }else{
      drawCrosshair(event.clientX,event.clientY);
    }
  });

  function stopDrag(event){
    if(!state.dragging) return;
    state.dragging=false;
    try{svg.releasePointerCapture?.(event.pointerId);}catch(error){}
    svg.style.cursor="crosshair"; draw();
  }

  svg.addEventListener("pointerup",stopDrag);
  svg.addEventListener("pointercancel",stopDrag);
  svg.addEventListener("pointerleave",event=>{if(state.dragging) stopDrag(event); else draw();});

  svg.addEventListener("keydown",event=>{
    const all=Array.isArray(datasets[state.timeframe]) ? datasets[state.timeframe] : [];
    if(!all.length) return;
    if(event.key==="ArrowLeft"){event.preventDefault();state.offset=clamp(state.offset+1,0,Math.max(0,all.length-state.visibleCount));draw();}
    else if(event.key==="ArrowRight"){event.preventDefault();state.offset=clamp(state.offset-1,0,Math.max(0,all.length-state.visibleCount));draw();}
    else if(event.key==="+"||event.key==="="){event.preventDefault();state.visibleCount=clamp(state.visibleCount-4,8,Math.min(120,all.length));draw();}
    else if(event.key==="-"||event.key==="_"){event.preventDefault();state.visibleCount=clamp(state.visibleCount+4,8,Math.min(120,all.length));draw();}
  });

  draw();
  window.setTimeout(()=>pollLive(true),1200);
  window.setInterval(()=>pollLive(false),10000);
  document.addEventListener("visibilitychange",()=>{
    if(!document.hidden) pollLive(true);
  });
})();
</script>


<script>
/* TRANSACTIONS_FEED_V121_ROBUST_UI_MOUNT */
(function(){
  const panel=document.querySelector("[data-transactions-panel]");
  if(!panel) return;

  const url=panel.dataset.transactionsUrl||"";
  const tbody=panel.querySelector("[data-transactions-body]");
  const state=panel.querySelector("[data-transactions-state]");
  const scrollBox=panel.querySelector(".transactions-table-wrap");

  /* TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI */
  const marketActivityBody=panel.querySelector("[data-market-activity-body]");
  const marketActivitySource=panel.querySelector("[data-market-activity-source]");
  const MARKET_ACTIVITY_WINDOWS=[["m5","5M"],["m15","15M"],["m30","30M"],["h1","1H"],["h6","6H"],["h24","24H"]];

  /* TRANSACTIONS_FEED_V15_FLOW_INTELLIGENCE */
  const flowBuyVolume=panel.querySelector("[data-flow-buy-volume]");
  const flowBuyCount=panel.querySelector("[data-flow-buy-count]");
  const flowSellVolume=panel.querySelector("[data-flow-sell-volume]");
  const flowSellCount=panel.querySelector("[data-flow-sell-count]");
  const flowNet=panel.querySelector("[data-flow-net]");
  const flowNetCard=panel.querySelector("[data-flow-net-card]");
  const flowBias=panel.querySelector("[data-flow-bias]");
  const flowBuyMeter=panel.querySelector("[data-flow-buy-meter]");
  const flowSellMeter=panel.querySelector("[data-flow-sell-meter]");
  const flowLargest=panel.querySelector("[data-flow-largest]");
  const flowLargestSide=panel.querySelector("[data-flow-largest-side]");

  /* TRANSACTIONS_FEED_V13_LIVE_POLLING */
  const POLL_INTERVAL_MS=5000;
  let pollInFlight=false;

  const rawText=(value)=>value===null||value===undefined?"":String(value);
  const compact=(value)=>{
    const raw=rawText(value);
    if(!raw) return "--";
    return raw.length>14?raw.slice(0,6)+"..."+raw.slice(-4):raw;
  };
  const formatPrice=(value)=>{
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    if(Math.abs(n)>=1) return "$"+n.toLocaleString(undefined,{maximumFractionDigits:6});
    if(Math.abs(n)>=0.01) return "$"+n.toFixed(6);
    return "$"+n.toFixed(8);
  };
  const formatUsd=(value)=>{
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    return "$"+n.toLocaleString(undefined,{minimumFractionDigits:n<1?4:2,maximumFractionDigits:n<1?4:2});
  };
  const formatAmount=(value)=>{
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    return n.toLocaleString(undefined,{maximumFractionDigits:4});
  };
  const formatTime=(value)=>{
    const d=new Date(rawText(value));
    if(Number.isNaN(d.getTime())) return "--";
    return d.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"});
  };

  function textCell(value){
    const td=document.createElement("td");
    td.textContent=value;
    return td;
  }

  function nodeCell(node){
    const td=document.createElement("td");
    td.append(node);
    return td;
  }

  function sideNode(value){
    const side=rawText(value).toUpperCase()==="SELL"?"SELL":"BUY";
    const span=document.createElement("span");
    span.className="transaction-side "+side.toLowerCase();
    span.textContent=side;
    return span;
  }

  function traderNode(value){
    const raw=rawText(value);
    const span=document.createElement("span");
    span.className="transaction-trader";
    span.textContent=compact(raw);
    if(raw) span.title=raw;
    return span;
  }

  function txNode(value){
    const raw=rawText(value);
    if(!raw){
      const span=document.createElement("span");
      span.textContent="--";
      return span;
    }

    const link=document.createElement("a");
    link.className="transaction-tx";
    link.href="https://solscan.io/tx/"+encodeURIComponent(raw);
    link.target="_blank";
    link.rel="noopener noreferrer";
    link.title=raw;
    link.textContent=compact(raw);
    return link;
  }

  const MAX_VISIBLE_TRANSACTIONS=30;

  /* TRANSACTIONS_FEED_V15_FLOW_INTELLIGENCE */
  function flowUsd(value,{signed=false}={}){
    const n=Number(value);
    if(!Number.isFinite(n)) return "--";
    const abs=Math.abs(n);
    let formatted;
    if(abs>=1000000) formatted="$"+(abs/1000000).toFixed(abs>=10000000?1:2)+"M";
    else if(abs>=1000) formatted="$"+(abs/1000).toFixed(abs>=10000?1:2)+"K";
    else formatted="$"+abs.toLocaleString(undefined,{
      minimumFractionDigits:abs<1?4:2,
      maximumFractionDigits:abs<1?4:2
    });
    if(!signed||n===0) return formatted;
    return (n>0?"+":"-")+formatted;
  }

  /* TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI */
  function activityNumber(value){const n=Number(value);return Number.isFinite(n)?Math.max(0,Math.round(n)).toLocaleString():"--";}
  function activityPercent(value){const n=Number(value);return Number.isFinite(n)?n.toFixed(1)+"%":"--";}
  function activityUsd(value){const n=Number(value);if(!Number.isFinite(n))return "--";if(n>=1000000)return "$"+(n/1000000).toFixed(n>=10000000?1:2)+"M";if(n>=1000)return "$"+(n/1000).toFixed(n>=10000?1:2)+"K";return "$"+n.toLocaleString(undefined,{maximumFractionDigits:2});}
  function renderMarketActivity(activity){
    if(!marketActivityBody)return;
    const windows=activity&&typeof activity==="object"&&activity.windows&&typeof activity.windows==="object"?activity.windows:{};
    const specs=[["buys","activity-buys",activityNumber],["sells","activity-sells",activityNumber],["total_transactions","activity-total",activityNumber],["volume_usd","activity-volume",activityUsd]];
    marketActivityBody.replaceChildren();
    MARKET_ACTIVITY_WINDOWS.forEach(([key,label])=>{const row=windows[key];const tr=document.createElement("tr");tr.className="activity-window";tr.append(textCell(label));specs.forEach(([field,cls,formatter])=>{const value=row&&typeof row==="object"?row[field]:null;const td=textCell(formatter(value));td.classList.add(cls);if(value===null||value===undefined||!Number.isFinite(Number(value)))td.classList.add("activity-unavailable");tr.append(td);});marketActivityBody.append(tr);});
    if(marketActivitySource)marketActivitySource.textContent=Object.keys(windows).length?"Exact-pool aggregate":"Aggregate unavailable";
  }

  function calculateRecentFlow(rows){
    const recent=(Array.isArray(rows)?rows:[])
      .slice(0,MAX_VISIBLE_TRANSACTIONS);

    let buyCount=0;
    let sellCount=0;
    let buyVolume=0;
    let sellVolume=0;
    let largest=null;

    recent.forEach(item=>{
      if(!item||typeof item!=="object") return;
      const side=rawText(item.side).toUpperCase();
      const volume=Number(item.volume_usd);
      if(!Number.isFinite(volume)||volume<0) return;

      if(side==="BUY"){
        buyCount+=1;
        buyVolume+=volume;
      }else if(side==="SELL"){
        sellCount+=1;
        sellVolume+=volume;
      }else{
        return;
      }

      if(largest===null||volume>largest.volume){
        largest={volume,side};
      }
    });

    return {
      buyCount,
      sellCount,
      buyVolume,
      sellVolume,
      netFlow:buyVolume-sellVolume,
      largest
    };
  }

  function renderRecentFlow(rows){
    const flow=calculateRecentFlow(rows);

    if(flowBuyVolume) flowBuyVolume.textContent=flowUsd(flow.buyVolume);
    if(flowBuyCount) flowBuyCount.textContent=flow.buyCount+" buys";
    if(flowSellVolume) flowSellVolume.textContent=flowUsd(flow.sellVolume);
    if(flowSellCount) flowSellCount.textContent=flow.sellCount+" sells";
    if(flowNet) flowNet.textContent=flowUsd(flow.netFlow,{signed:true});

    if(flowNetCard){
      flowNetCard.classList.remove("positive","negative","flat");
      flowNetCard.classList.add(
        flow.netFlow>0?"positive":flow.netFlow<0?"negative":"flat"
      );
    }

    const totalVolume=flow.buyVolume+flow.sellVolume;
    const buyShare=totalVolume>0 ? (flow.buyVolume/totalVolume)*100 : 0;
    const sellShare=totalVolume>0 ? (flow.sellVolume/totalVolume)*100 : 0;

    if(flowBuyMeter) flowBuyMeter.style.width=buyShare.toFixed(1)+"%";
    if(flowSellMeter) flowSellMeter.style.width=sellShare.toFixed(1)+"%";

    if(flowBias){
      flowBias.textContent=flow.netFlow>0
        ? "Buy pressure"
        : flow.netFlow<0
          ? "Sell pressure"
          : "Balanced";
    }

    if(flowLargest){
      flowLargest.textContent=flow.largest
        ? flowUsd(flow.largest.volume)
        : "--";
    }
    if(flowLargestSide){
      flowLargestSide.textContent=flow.largest
        ? flow.largest.side
        : "--";
    }

    [flowLargest,flowLargestSide].forEach(node=>{
      if(!node) return;
      node.classList.remove("buy","sell");
      if(flow.largest){
        node.classList.add(flow.largest.side.toLowerCase());
      }
    });
  }

  function captureScrollAnchor(){
    if(!scrollBox||scrollBox.scrollTop<=8) return null;

    const rows=[...tbody.querySelectorAll("tr[data-transaction-id]")];
    const top=scrollBox.scrollTop;
    const anchor=rows.find(row=>row.offsetTop+row.offsetHeight>top);
    if(!anchor) return null;

    return {
      id:anchor.dataset.transactionId||"",
      delta:anchor.offsetTop-top
    };
  }

  function restoreScrollAnchor(anchor){
    if(!anchor||!scrollBox||!anchor.id) return;

    const rows=[...tbody.querySelectorAll("tr[data-transaction-id]")];
    const matched=rows.find(row=>row.dataset.transactionId===anchor.id);
    if(matched){
      scrollBox.scrollTop=Math.max(0,matched.offsetTop-anchor.delta);
    }
  }

  function renderRows(rows){
    const scrollAnchor=captureScrollAnchor();
    tbody.replaceChildren();
    const visibleRows=rows.slice(0,MAX_VISIBLE_TRANSACTIONS);

    if(!visibleRows.length){
      const tr=document.createElement("tr");
      tr.className="transactions-empty";
      const td=document.createElement("td");
      td.colSpan=7;
      td.textContent="No recent exact-pool transactions available.";
      tr.append(td);
      tbody.append(tr);
      return;
    }

    visibleRows.forEach(item=>{
      if(!item||typeof item!=="object") return;

      const tr=document.createElement("tr");
      tr.dataset.transactionId=rawText(item.id);
      tr.append(
        textCell(formatTime(item.timestamp)),
        nodeCell(sideNode(item.side)),
        textCell(formatPrice(item.price_usd)),
        textCell(formatAmount(item.token_amount)),
        textCell(formatUsd(item.volume_usd)),
        nodeCell(traderNode(item.trader)),
        nodeCell(txNode(item.tx_hash))
      );
      tbody.append(tr);
    });

    restoreScrollAnchor(scrollAnchor);
  }

  /* TRANSACTIONS_FEED_V14_FRESHNESS_DIAGNOSTICS */
  function formatFreshnessSeconds(value){
    const seconds=Number(value);
    if(!Number.isFinite(seconds)||seconds<0) return null;
    if(seconds<60) return Math.round(seconds)+"s";
    const minutes=Math.floor(seconds/60);
    const remain=Math.round(seconds-(minutes*60));
    return remain>0 ? minutes+"m "+remain+"s" : minutes+"m";
  }

  /* TRANSACTIONS_FEED_V141_FRESHNESS_SEMANTICS_FIX */
  function applyFreshnessDiagnostics(payload){
    if(!state||!payload||typeof payload!=="object") return;
    const freshness=payload.freshness;
    if(!freshness||typeof freshness!=="object") return;

    const lastTradeAge=formatFreshnessSeconds(
      freshness.last_trade_age_seconds
    );
    const apiAge=formatFreshnessSeconds(freshness.api_age_seconds);

    const diagnostics=[];
    if(lastTradeAge) diagnostics.push("Last trade "+lastTradeAge);
    if(apiAge) diagnostics.push("API age "+apiAge);

    if(diagnostics.length){
      state.textContent+=" · "+diagnostics.join(" · ");
    }

    const detail=[];
    if(freshness.cache_hit===true) detail.push("cache hit");
    if(freshness.stale===true) detail.push("stale fallback");
    if(freshness.latest_trade_at){
      detail.push("latest trade "+freshness.latest_trade_at);
    }

    if(detail.length) state.title=detail.join(" · ");
    else state.removeAttribute("title");
  }

  function setTransactionState(mode,shown=0){
    if(!state) return;

    state.classList.remove("ready","unavailable","live","stale");

    if(mode==="LIVE"){
      state.textContent="LIVE";
      state.classList.add("ready","live");
      return;
    }

    state.textContent="STALE";
    state.classList.add("stale");
  }

  function keepExistingRowsOnFailure(){
    const existing=tbody.querySelector("tr[data-transaction-id]");
    if(existing) return;

    const placeholder=tbody.querySelector(".transactions-placeholder");
    if(placeholder){
      const cell=placeholder.querySelector("td");
      if(cell) cell.textContent="Recent transactions are temporarily unavailable.";
      placeholder.classList.add("transactions-error");
    }
  }

  async function loadTransactions(force=false){
    if(!url||pollInFlight) return;
    if(document.hidden&&!force) return;

    pollInFlight=true;

    try{
      const response=await fetch(url,{
        method:"GET",
        credentials:"same-origin",
        headers:{"Accept":"application/json"},
        cache:"no-store"
      });

      if(!response.ok) throw new Error("transactions unavailable");

      const payload=await response.json();
      const incoming=Array.isArray(payload.transactions)
        ? payload.transactions
        : [];

      const deduped=[];
      const seen=new Set();

      incoming.forEach(item=>{
        if(!item||typeof item!=="object") return;
        const id=rawText(item.id);
        if(!id||seen.has(id)) return;
        seen.add(id);
        deduped.push(item);
      });

      renderRows(deduped);
      renderRecentFlow(deduped);
      renderMarketActivity(payload.market_activity);

      /* CHART_V23_TRADE_OVERLAY */
      window.dispatchEvent(new CustomEvent("dexsato:transactions-updated",{
        detail:{transactions:deduped.slice(0,MAX_VISIBLE_TRANSACTIONS)}
      }));

      const shown=Math.min(deduped.length,MAX_VISIBLE_TRANSACTIONS);
      setTransactionState(payload.stale===true?"STALE":"LIVE",shown);
      applyFreshnessDiagnostics(payload);
    }catch(error){
      keepExistingRowsOnFailure();

      const existingCount=tbody.querySelectorAll(
        "tr[data-transaction-id]"
      ).length;

      setTransactionState("STALE",existingCount);
    }finally{
      pollInFlight=false;
    }
  }

  loadTransactions(true);
  window.setInterval(()=>loadTransactions(false),POLL_INTERVAL_MS);

  document.addEventListener("visibilitychange",()=>{
    if(!document.hidden) loadTransactions(true);
  });
})();
</script>

</body></html>"""
    replacements = {
        "__SYMBOL__": symbol, "__QUOTE__": quote, "__NAME__": name,
        "__DEX__": escape(str(detail.get("dex_id") or "Unknown venue")),
        "__STATUS__": status, "__STATUS_LABEL__": status_label,
        "__SOURCE_LINK__": source_link, "__TOKEN__": token, "__POOL__": pool,
        "__TOKEN_SHORT__": escape(_short(token_raw)), "__POOL_SHORT__": escape(_short(pool_raw)),
        "__CHART__": chart, "__PRICE__": escape(_usd(detail.get("price_usd"))),
        "__CHANGE__": escape(change), "__CHANGE_TONE__": change_tone,
        "__LIQUIDITY__": escape(_usd(detail.get("liquidity_usd"))),
        "__VOLUME__": escape(_usd(detail.get("volume_24h_usd"))),
        "__MARKET_CAP__": escape(_usd(detail.get("market_cap"))),
        "__AGE__": escape(str(detail.get("pair_age") or "Unavailable")),
        "__EVIDENCE__": evidence, "__RISK__": risk,
        "__UPDATED__": escape(str(detail.get("feed_updated_label") or "Unknown")),
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    html = html.replace("__TRADER_TF_STRIP__", trader_tf_strip)
    html = html.replace("__TOKEN_OVERVIEW_CARD__", token_overview_card)
    html = html.replace("__CANDLESTICK_CHART_PANEL__", candlestick_chart_panel + transactions_table_panel)
    html = html.replace("__TOKEN_OBSERVATION_PANEL__", token_observation_panel)
    html = html.replace("__QUALIFICATION_PANEL__", qualification_panel)
    html = html.replace("__COIN_LIST_PANEL__", coin_list_panel)
    return html
