"""Exact-token discovery workspace with a controlled non-custodial D6 swap pilot."""

from __future__ import annotations

from html import escape
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


def _pair_age_display(detail: dict[str, Any]) -> str:
    # Prefer the current token-detail age field first. Older stored labels are
    # only fallbacks because they may be stale or inherited from fixture/feed data.
    for key in (
        "age",
        "pair_age",
        "age_label",
        "pair_age_label",
        "freshness",
        "freshness_label",
    ):
        value = detail.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {
            "none",
            "unknown",
            "unavailable",
            "age unavailable",
        }:
            return text

    for key in ("age_hours", "pair_age_hours", "hours_old"):
        try:
            hours = float(detail.get(key))
        except (TypeError, ValueError):
            continue
        if hours < 1:
            return "<1h"
        return f"{hours:.0f}h"

    return "Age unavailable"


    for key in ("pair_age_hours", "age_hours", "hours_old"):
        try:
            hours = float(detail.get(key))
        except (TypeError, ValueError):
            continue
        if hours < 1:
            return "<1h"
        return f"{hours:.0f}h"

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
        f'<span class="token-age"><span aria-hidden="true">&#9201;</span> {age_text}</span>'
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
def render_solana_discovery_token_page(detail: dict[str, Any]) -> str:
    """Render exact-token evidence and explicit wallet-approved Jupiter execution."""
    token_overview_card = _token_overview_card(detail)
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
    chart = _chart_svg(detail.get("chart") if isinstance(detail.get("chart"), list) else [])
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

</style></head><body><main class="shell"><header class="topbar"><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><strong>Solana Discovery</strong></div><div class="theme-controls"><a class="back" href="/discovery/solana">&larr; Discovery Feed</a><div class="theme-switcher" role="group" aria-label="Theme"><button class="theme-option" type="button" data-theme-option="current" aria-label="Use current dark theme" title="Dark" aria-pressed="false">&#9790;</button><button class="theme-option" type="button" data-theme-option="intel" aria-label="Use market intelligence theme" title="Market Intelligence" aria-pressed="false">MI</button><button class="theme-option" type="button" data-theme-option="plain" aria-label="Use plain light theme" title="Light" aria-pressed="false">&#9728;</button></div></div></header>
__TOKEN_OVERVIEW_CARD__
<section class="hero"><div><span class="eyebrow">Qualified exact-token workspace</span><h1>__SYMBOL__ / __QUOTE__</h1><p>Review observed market activity, exact-pool identity and disclosed risk before taking any action.</p></div><div class="status"><span class="eyebrow">Market data</span><b>__STATUS__</b><small>__STATUS_LABEL__</small></div></section>
<section class="identity"><div class="identity-head"><div><span class="eyebrow">Token identity</span><h2>__NAME__</h2><span class="name">__DEX__ · Solana exact pool</span></div><div>__SOURCE_LINK__</div></div><div class="addresses"><div class="address"><span>Canonical token address</span><div class="address-row"><code title="__TOKEN__">__TOKEN_SHORT__</code><button class="copy-address" type="button" data-copy-address="__TOKEN__">Copy</button></div></div><div class="address"><span>Exact pool address</span><div class="address-row"><code title="__POOL__">__POOL_SHORT__</code><button class="copy-address" type="button" data-copy-address="__POOL__">Copy</button></div></div></div></section>
<section class="chart-panel"><div class="section-head"><div><span class="eyebrow">Validated exact-pool data</span><h2>4H Market Chart</h2><p>Closed market intervals; not an executable quote.</p></div><span class="eyebrow">GeckoTerminal · base token</span></div>__CHART__</section>
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
    return html

