"""Exact-token discovery workspace with a controlled non-custodial D6 swap pilot."""

from __future__ import annotations

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
    symbol = escape(str(detail.get("symbol") or "Unknown"))
    quote = escape(str(detail.get("quote_symbol") or "SOL"))
    name = escape(str(detail.get("name") or "Unknown token"))

    token_raw = str(detail.get("token_address") or "")
    contract_short = escape(_compact_contract(token_raw))
    token_attr = escape(token_raw, quote=True)

    price = _usd(detail.get("price_usd"))
    change_text, change_tone = _change_percent(detail.get("change_24h"))
    if change_text == "&#8212;":
        change_text = "Unavailable"

    dex = escape(_dex_display(detail.get("dex_id")))

    age_value = _pair_age_display(detail)
    if age_value == "Age unavailable":
        age_text = "Age unavailable"
    else:
        age_text = f"{age_value} old"
    age_text = escape(age_text)

    source_url = _external_link(detail.get("source_url"))

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
    status_html = (
        '<span class="token-live"><i></i>LIVE</span>'
        if status == "LIVE"
        else '<span class="token-live stored"><i></i>STORED</span>'
    )

    if source_url:
        dex_html = (
            f'<a class="token-dex" href="{escape(source_url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{dex}</a>'
        )
    else:
        dex_html = f'<span class="token-dex">{dex}</span>'

    website = _info_link("Website", str(detail.get("website_url") or ""), "website")
    telegram = _info_link("Telegram", str(detail.get("telegram_url") or ""), "telegram")
    twitter = _info_link("Twitter", str(detail.get("twitter_url") or ""), "twitter")

    social_links = [link for link in (website, telegram, twitter) if link]
    social_html = ""
    if social_links:
        social_html = (
            '<span class="token-meta-sep social-sep">&#8226;</span>'
            + '<span class="token-social-links">'
            + '<span class="token-meta-sep social-inner-sep">&#8226;</span>'.join(social_links)
            + '</span>'
        )

    return (
        '<section class="token-overview-card" aria-label="Token market overview">'
        '<div class="token-overview-main">'
        f'<div class="token-avatar">{avatar}</div>'
        '<div class="token-overview-heading">'
        f'<h1>{symbol} / {quote}</h1>'
        '<div class="token-price-row">'
        f'<strong>{escape(price)}</strong>'
        f'<span class="token-change {escape(change_tone)}">{change_text}</span>'
        '</div></div>'
        '<div class="token-overview-actions">'
        f'{status_html}'
        f'<button class="token-watch" type="button" data-watch-token="{token_attr}" '
        f'aria-label="Watch {symbol}"><span aria-hidden="true">&#9734;</span> Watch</button>'
        '</div></div>'
        '<div class="token-meta-row">'
        f'{dex_html}<span class="token-meta-sep">&#8226;</span>'
        f'<span class="token-age"><svg class="token-age-leaf" aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M20.7 3.3C14.6 3.6 9.4 5.7 6.5 9.1c-2.2 2.6-2.8 5.6-1.7 8.2 3.5-4.5 7.6-7.2 12.8-8.9-4.5 2.1-8 5-10.8 8.9 2.7.4 5.4-.7 7.4-3.1 2.6-3.1 3.7-7.8 3.5-10.9z"/></svg> {age_text}</span>'
        '<span class="token-meta-sep">&#8226;</span>'
        f'<span class="token-contract">Contract <code title="{token_attr}">{contract_short}</code></span>'
        f'<button class="copy-address token-copy" type="button" data-copy-address="{token_attr}">Copy</button>'
        f'{social_html}'
        '</div>'
        f'{_trader_timeframe_strip(detail)}'
        '<span class="token-name-context">' + name + '</span>'
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

    return (
        '<section class="candlestick-panel" data-candlestick-panel '
        f'data-live-candle-url="{live_url}">'
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
        '<svg class="candlestick-chart" viewBox="0 0 1000 420" '
        'preserveAspectRatio="none" role="img" aria-label="Exact-pool interactive candlestick chart" '
        'tabindex="0" data-candlestick-svg></svg>'
        '<div class="candlestick-empty" data-candlestick-empty hidden>'
        'Market candles unavailable for this timeframe.'
        '</div>'
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
        '<div class="transactions-head">'
        '<h2>Transactions</h2>'
        '<span class="transactions-state" data-transactions-state>Loading</span>'
        '</div>'
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
    )


def render_solana_discovery_token_page(detail: dict[str, Any]) -> str:
    """Render exact-token evidence and explicit wallet-approved Jupiter execution."""
    token_overview_card = _token_overview_card(detail)
    candlestick_chart_panel = _candlestick_chart_panel(detail)
    transactions_table_panel = _transactions_table_panel(detail)
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
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__SYMBOL__ · Solana Discovery</title>
<script>try{const t=localStorage.getItem("dexsato-theme");if(t==="plain"||t==="intel")document.documentElement.dataset.theme=t;}catch(error){}</script>
<style>
:root{color-scheme:dark;--bg:#050b13;--panel:#091422;--panel2:#0d1b2d;--line:#20344b;--text:#f4f7fb;--muted:#91a8c5;--cyan:#0de6d1;--blue:#5a98ff;--amber:#ffb800;--green:#26d49a;--red:#ff5675;--display:"Bahnschrift SemiBold","Bahnschrift","Arial Narrow","Segoe UI",sans-serif;--ui:"Segoe UI Variable Text","Segoe UI",sans-serif;--mono:"Cascadia Mono","Consolas",monospace}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--ui);font-size:15px;line-height:1.55}.shell{width:min(1180px,calc(100% - 32px));margin:auto;padding:20px 0 34px}.topbar{display:flex;align-items:center;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:14px}.brand img{width:138px}.brand strong,h1,h2,h3,.value{font-family:var(--display)}a{color:#8ab9ff}.back{padding:8px 12px;border:1px solid var(--line);border-radius:6px;text-decoration:none;color:var(--text)}.hero{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:end;padding:28px 0 20px}.eyebrow{color:var(--cyan);font:700 11px var(--mono);letter-spacing:.12em;text-transform:uppercase}.hero h1{margin:5px 0 0;font-size:38px;line-height:1.05}.hero p{margin:8px 0 0;color:var(--muted)}.status{padding:12px 15px;border:1px solid var(--line);border-left:3px solid var(--green);background:var(--panel)}.status b,.status small{display:block}.status b{font-family:var(--mono)}.status small{color:var(--muted)}.identity,.chart-panel,.card{border:1px solid var(--line);background:var(--panel)}.identity{padding:20px}.identity-head{display:flex;justify-content:space-between;gap:18px}.identity h2{margin:0;font-size:25px}.identity .name{color:var(--muted)}.addresses{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:17px}.address{padding:12px;background:var(--panel2)}.address span,.metric span{display:block;color:var(--muted);font:700 10px var(--mono);text-transform:uppercase}.address code{display:block;margin-top:5px;font:12px var(--mono);overflow-wrap:anywhere}.chart-panel{margin-top:14px;padding:20px}.section-head{display:flex;justify-content:space-between;gap:15px;align-items:end}.section-head h2{margin:4px 0 0;font-size:23px}.section-head p{margin:4px 0 0;color:var(--muted)}.chart{display:block;width:100%;height:270px;margin-top:15px;background:var(--panel2);border:1px solid var(--line)}.chart line{stroke:var(--line);stroke-width:1}.chart polyline{fill:none;stroke:var(--cyan);stroke-width:3;vector-effect:non-scaling-stroke}.chart-empty{display:grid;place-items:center;min-height:240px;margin-top:15px;border:1px dashed var(--line);color:var(--amber);background:var(--panel2)}.grid{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin-top:14px}.card{padding:18px}.card h3{margin:0 0 12px;font-size:18px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:13px;background:var(--panel2)}.metric .value{display:block;margin-top:5px;font-size:19px}.change.up{color:var(--green)}.change.down{color:var(--red)}.evidence{margin-top:14px;padding:15px;border-left:2px solid var(--cyan);background:var(--panel2)}.evidence strong{display:block;margin-bottom:5px}.risk{margin-top:12px;padding:15px;border-left:2px solid var(--amber);background:rgba(255,184,0,.06)}.risk strong{color:var(--amber)}.check{padding:9px 0;border-top:1px solid var(--line)}.check:before{content:"\\2713";margin-right:8px;color:var(--green)}.jupiter{border-left:2px solid #9b5cff}.jupiter .badge{display:inline-block;padding:5px 8px;border:1px solid #7c45c8;border-radius:999px;color:#c9a8ff;font:700 10px var(--mono)}.source{margin-top:13px;padding-top:12px;border-top:1px solid var(--line)}footer{display:flex;justify-content:space-between;gap:20px;margin-top:18px;color:var(--muted);font-size:11px}
html[data-theme="plain"]{color-scheme:light;--bg:#f5f7fa;--panel:#fff;--panel2:#f0f4f8;--line:#d5dee8;--text:#102035;--muted:#60738b;--cyan:#087f8c;--blue:#276dcc;--amber:#9a6200;--green:#147c54;--red:#ba3654}
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
.transactions-table-wrap{max-height:480px;overflow:auto;-webkit-overflow-scrolling:touch;scrollbar-gutter:stable}
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
@media(max-width:700px){.transactions-table-wrap{max-height:400px}}

</style></head><body><main class="shell"><header class="topbar"><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><strong>Solana Discovery</strong></div><div class="theme-controls"><a class="back" href="/discovery/solana">&larr; Discovery Feed</a><div class="theme-switcher" role="group" aria-label="Theme"><button class="theme-option" type="button" data-theme-option="current" aria-label="Use current dark theme" title="Dark" aria-pressed="false">&#9790;</button><button class="theme-option" type="button" data-theme-option="intel" aria-label="Use market intelligence theme" title="Market Intelligence" aria-pressed="false">MI</button><button class="theme-option" type="button" data-theme-option="plain" aria-label="Use plain light theme" title="Light" aria-pressed="false">&#9728;</button></div></div></header>
__TOKEN_OVERVIEW_CARD__
<section class="hero"><div><span class="eyebrow">Qualified exact-token workspace</span><h1>__SYMBOL__ / __QUOTE__</h1><p>Review observed market activity, exact-pool identity and disclosed risk before taking any action.</p></div><div class="status"><span class="eyebrow">Market data</span><b>__STATUS__</b><small>__STATUS_LABEL__</small></div></section>
<section class="identity"><div class="identity-head"><div><span class="eyebrow">Token identity</span><h2>__NAME__</h2><span class="name">__DEX__ · Solana exact pool</span></div><div>__SOURCE_LINK__</div></div><div class="addresses"><div class="address"><span>Canonical token address</span><div class="address-row"><code title="__TOKEN__">__TOKEN_SHORT__</code><button class="copy-address" type="button" data-copy-address="__TOKEN__">Copy</button></div></div><div class="address"><span>Exact pool address</span><div class="address-row"><code title="__POOL__">__POOL_SHORT__</code><button class="copy-address" type="button" data-copy-address="__POOL__">Copy</button></div></div></div></section>
__CANDLESTICK_CHART_PANEL__
<div class="grid"><section class="card"><h3>Market Snapshot</h3><div class="metrics"><div class="metric"><span>Observed price</span><b class="value">__PRICE__</b></div><div class="metric"><span>24h change</span><b class="value change __CHANGE_TONE__">__CHANGE__</b></div><div class="metric"><span>Liquidity</span><b class="value">__LIQUIDITY__</b></div><div class="metric"><span>24h volume</span><b class="value">__VOLUME__</b></div><div class="metric"><span>Market cap / FDV</span><b class="value">__MARKET_CAP__</b></div><div class="metric"><span>Pair age</span><b class="value">__AGE__</b></div></div><div class="evidence"><strong>Why this token appeared</strong>__EVIDENCE__</div><div class="risk"><strong>Risk context</strong><p>__RISK__. Pool verification is not token verification. Inclusion is not an endorsement.</p></div><section class="qualification"><span class="eyebrow">Qualification evidence</span><h3>Checks passed for this feed</h3><div class="check">Solana token identity</div><div class="check">Exact token and pool match</div><div class="check">Observed liquidity threshold</div><div class="check">Observed 24h activity</div><div class="check">Fresh collector data</div><div class="source">Collector updated __UPDATED__</div></section></section>
<aside><section class="card jupiter" data-jupiter-sandbox data-token-address="__TOKEN__" data-token-symbol="__SYMBOL__"><span class="eyebrow">Jupiter integration sandbox</span><h3>Controlled wallet-approved swap</h3><span class="badge">D6 · NON-CUSTODIAL PILOT</span><p class="sandbox-note">Review an indicative Jupiter quote before choosing whether to approve one real Solana mainnet transaction in your connected wallet.</p><div class="wallet-state" data-wallet-state>Wallet not connected · required for swap approval</div><div class="sandbox-form"><button class="sandbox-button" type="button" data-connect-wallet>Connect supported wallet</button><label for="jupiter-amount">Amount in SOL</label><input class="sandbox-input" id="jupiter-amount" data-quote-amount inputmode="decimal" type="number" min="0.001" max="100" step="0.001" value="0.1"><button class="sandbox-button primary" type="button" data-get-quote>Get Jupiter quote</button></div><div class="quote-result" data-quote-result aria-live="polite"></div><div class="swap-warning"><strong>Real Solana mainnet transaction</strong>Discovery tokens may lose value, liquidity may change, and network or Jupiter fees may apply. A quote is not a guaranteed settlement result.</div><label class="swap-consent"><input type="checkbox" data-swap-risk-ack>I understand the risks and will review the transaction in my own wallet.</label><button class="sandbox-button primary" type="button" data-execute-swap disabled>Review and approve swap</button><div class="quote-result" data-swap-result aria-live="polite"></div><p class="quote-policy">DexSato integrator fee: <strong>0 bps</strong>. Trades are routed through Jupiter. DexSato never asks for a seed phrase and does not hold private keys or funds. Transactions must be approved in your connected wallet.</p></section></aside></div>
<footer><span>Experimental discovery · evidence synthesis only · not financial advice.</span><span>Market observations, indicative quotes and transaction results are distinct.</span></footer></main><script src="/static/js/dexsato_solana_discovery_swap.js" defer></script><script>
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
  const jupiter=[...document.querySelectorAll(".card")].find(el=>norm(el.textContent).includes("jupiter integration sandbox")) || cardByHeading("Controlled wallet-approved swap");

  if(market) market.classList.add("decision-main-v2");
  if(jupiter) jupiter.classList.add("decision-side-v2");

  if(market && jupiter && market.parentElement===jupiter.parentElement){
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
/* CHART_V21_INTERACTIVE_TRADING_CHART */
(function(){
  const panel=document.querySelector("[data-candlestick-panel]");
  if(!panel) return;

  const svg=panel.querySelector("[data-candlestick-svg]");
  const empty=panel.querySelector("[data-candlestick-empty]");
  const dataNode=panel.querySelector("[data-candlestick-data]");
  const buttons=[...panel.querySelectorAll("[data-candle-timeframe]")];
  const resetButton=panel.querySelector("[data-candle-reset]");
  const liveState=panel.querySelector("[data-candle-live-state]");
  const liveUrl=panel.dataset.liveCandleUrl||"";
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

    const values=[];
    visible.forEach(row=>{
      [row.high,row.low,row.open,row.close].forEach(value=>{
        const n=Number(value);
        if(Number.isFinite(n)) values.push(n);
      });
    });
    if(!values.length){
      empty.hidden=false;
      updateOHLC(null);
      state.geometry=null;
      return;
    }

    let low=Math.min(...values),high=Math.max(...values),spread=high-low;
    if(!spread){
      spread=Math.max(Math.abs(high)*0.02,1e-9);
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
      const x=left+slot*(index+.5),up=close>=open,cls=up?"candlestick-up":"candlestick-down";
      const yOpen=y(open),yClose=y(close),yHigh=y(highValue),yLow=y(lowValue);

      const volumeHeight=(volume/maxVolume)*(volumeBottom-volumeTop);
      svg.append(make("rect",{x:x-bodyWidth/2,y:volumeBottom-volumeHeight,width:bodyWidth,height:Math.max(1,volumeHeight),class:"candlestick-volume "+cls}));
      svg.append(make("line",{x1:x,y1:yHigh,x2:x,y2:yLow,class:"candlestick-wick "+cls}));
      svg.append(make("rect",{x:x-bodyWidth/2,y:Math.min(yOpen,yClose),width:bodyWidth,height:Math.max(1.5,Math.abs(yOpen-yClose)),rx:.5,class:"candlestick-body "+cls}));
    });

    const timeStep=Math.max(1,Math.floor(visible.length/6));
    visible.forEach((row,index)=>{
      if(index%timeStep!==0 && index!==visible.length-1) return;
      const x=left+slot*(index+.5);
      const label=make("text",{x:x,y:timeY,"text-anchor":"middle",class:"candlestick-time-label"});
      label.textContent=formatTime(row.time,state.timeframe);
      svg.append(label);
    });

    const last=visible[visible.length-1],lastPrice=Number(last.close);
    if(Number.isFinite(lastPrice)){
      const py=y(lastPrice);
      svg.append(make("line",{x1:left,y1:py,x2:priceRight,y2:py,class:"candlestick-price-line"}));
      svg.append(make("rect",{x:905,y:py-10,width:72,height:20,rx:3,class:"candlestick-price-tag"}));
      const text=make("text",{x:941,y:py+4,"text-anchor":"middle",class:"candlestick-price-tag-text"});
      text.textContent=formatPrice(lastPrice); svg.append(text);
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
    return html

