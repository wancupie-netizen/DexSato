"""Read-only D4 workspace for one qualified Solana Discovery token."""

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


def render_solana_discovery_token_page(detail: dict[str, Any]) -> str:
    """Render exact-token evidence while keeping execution explicitly disabled."""
    symbol = escape(str(detail.get("symbol") or "Unknown"))
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
        f'<a href="{escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">Open market source ↗</a>'
        if source_url.startswith("https://dexscreener.com/") else "Market source unavailable"
    )
    evidence = escape(str(detail.get("evidence") or "Exact-pool market activity was observed."))
    risk = escape(str(detail.get("risk_label") or "Token security is not independently verified."))
    chart = _chart_svg(detail.get("chart") if isinstance(detail.get("chart"), list) else [])
    status = escape(str(detail.get("quote_status") or "STORED"))
    status_label = escape(str(detail.get("quote_label") or "Stored collector observation"))
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__SYMBOL__ · Solana Discovery</title>
<style>
:root{color-scheme:dark;--bg:#050b13;--panel:#091422;--panel2:#0d1b2d;--line:#20344b;--text:#f4f7fb;--muted:#91a8c5;--cyan:#0de6d1;--blue:#5a98ff;--amber:#ffb800;--green:#26d49a;--red:#ff5675;--display:"Bahnschrift SemiBold","Bahnschrift","Arial Narrow","Segoe UI",sans-serif;--ui:"Segoe UI Variable Text","Segoe UI",sans-serif;--mono:"Cascadia Mono","Consolas",monospace}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--ui);font-size:15px;line-height:1.55}.shell{width:min(1180px,calc(100% - 32px));margin:auto;padding:20px 0 34px}.topbar{display:flex;align-items:center;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:14px}.brand img{width:138px}.brand strong,h1,h2,h3,.value{font-family:var(--display)}a{color:#8ab9ff}.back{padding:8px 12px;border:1px solid var(--line);border-radius:6px;text-decoration:none;color:var(--text)}.hero{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:end;padding:28px 0 20px}.eyebrow{color:var(--cyan);font:700 11px var(--mono);letter-spacing:.12em;text-transform:uppercase}.hero h1{margin:5px 0 0;font-size:38px;line-height:1.05}.hero p{margin:8px 0 0;color:var(--muted)}.status{padding:12px 15px;border:1px solid var(--line);border-left:3px solid var(--green);background:var(--panel)}.status b,.status small{display:block}.status b{font-family:var(--mono)}.status small{color:var(--muted)}.identity,.chart-panel,.card{border:1px solid var(--line);background:var(--panel)}.identity{padding:20px}.identity-head{display:flex;justify-content:space-between;gap:18px}.identity h2{margin:0;font-size:25px}.identity .name{color:var(--muted)}.addresses{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:17px}.address{padding:12px;background:var(--panel2)}.address span,.metric span{display:block;color:var(--muted);font:700 10px var(--mono);text-transform:uppercase}.address code{display:block;margin-top:5px;font:12px var(--mono);overflow-wrap:anywhere}.chart-panel{margin-top:14px;padding:20px}.section-head{display:flex;justify-content:space-between;gap:15px;align-items:end}.section-head h2{margin:4px 0 0;font-size:23px}.section-head p{margin:4px 0 0;color:var(--muted)}.chart{display:block;width:100%;height:270px;margin-top:15px;background:var(--panel2);border:1px solid var(--line)}.chart line{stroke:var(--line);stroke-width:1}.chart polyline{fill:none;stroke:var(--cyan);stroke-width:3;vector-effect:non-scaling-stroke}.chart-empty{display:grid;place-items:center;min-height:240px;margin-top:15px;border:1px dashed var(--line);color:var(--amber);background:var(--panel2)}.grid{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin-top:14px}.card{padding:18px}.card h3{margin:0 0 12px;font-size:18px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:13px;background:var(--panel2)}.metric .value{display:block;margin-top:5px;font-size:19px}.change.up{color:var(--green)}.change.down{color:var(--red)}.evidence{margin-top:14px;padding:15px;border-left:2px solid var(--cyan);background:var(--panel2)}.evidence strong{display:block;margin-bottom:5px}.risk{margin-top:12px;padding:15px;border-left:2px solid var(--amber);background:rgba(255,184,0,.06)}.risk strong{color:var(--amber)}.check{padding:9px 0;border-top:1px solid var(--line)}.check:before{content:"✓";margin-right:8px;color:var(--green)}.jupiter{border-left:2px solid #9b5cff}.jupiter .badge{display:inline-block;padding:5px 8px;border:1px solid #7c45c8;border-radius:999px;color:#c9a8ff;font:700 10px var(--mono)}.source{margin-top:13px;padding-top:12px;border-top:1px solid var(--line)}footer{display:flex;justify-content:space-between;gap:20px;margin-top:18px;color:var(--muted);font-size:11px}
html[data-theme="plain"]{color-scheme:light;--bg:#f5f7fa;--panel:#fff;--panel2:#f0f4f8;--line:#d5dee8;--text:#102035;--muted:#60738b;--cyan:#087f8c;--blue:#276dcc;--amber:#9a6200;--green:#147c54;--red:#ba3654}
@media(max-width:760px){.shell{width:calc(100% - 18px);padding-top:10px}.brand img{width:112px}.hero{grid-template-columns:1fr;padding-top:21px}.hero h1{font-size:29px}.status{width:100%}.identity-head{display:block}.addresses,.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.chart{height:210px}.section-head{display:block}footer{flex-direction:column}}
.address-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.copy-address{flex:0 0 auto;padding:6px 8px;border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--blue);font:700 10px var(--mono);cursor:pointer}.copy-address:focus-visible{outline:2px solid var(--blue);outline-offset:2px}.chart-empty{place-content:center;gap:7px;padding:24px;text-align:center}.chart-empty strong{font:700 18px var(--display)}.chart-empty span{max-width:560px;color:var(--muted);font-size:13px}
</style></head><body><main class="shell"><header class="topbar"><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><strong>Solana Discovery</strong></div><a class="back" href="/discovery/solana">← Discovery Feed</a></header>
<section class="hero"><div><span class="eyebrow">Qualified exact-token workspace</span><h1>__SYMBOL__ / __QUOTE__</h1><p>Review observed market activity, exact-pool identity and disclosed risk before taking any action.</p></div><div class="status"><span class="eyebrow">Market data</span><b>__STATUS__</b><small>__STATUS_LABEL__</small></div></section>
<section class="identity"><div class="identity-head"><div><span class="eyebrow">Token identity</span><h2>__NAME__</h2><span class="name">__DEX__ · Solana exact pool</span></div><div>__SOURCE_LINK__</div></div><div class="addresses"><div class="address"><span>Canonical token address</span><div class="address-row"><code title="__TOKEN__">__TOKEN_SHORT__</code><button class="copy-address" type="button" data-copy-address="__TOKEN__">Copy</button></div></div><div class="address"><span>Exact pool address</span><div class="address-row"><code title="__POOL__">__POOL_SHORT__</code><button class="copy-address" type="button" data-copy-address="__POOL__">Copy</button></div></div></div></section>
<section class="chart-panel"><div class="section-head"><div><span class="eyebrow">Validated exact-pool data</span><h2>4H Market Chart</h2><p>Closed market intervals; not an executable quote.</p></div><span class="eyebrow">GeckoTerminal · base token</span></div>__CHART__</section>
<div class="grid"><section class="card"><h3>Market Snapshot</h3><div class="metrics"><div class="metric"><span>Observed price</span><b class="value">__PRICE__</b></div><div class="metric"><span>24h change</span><b class="value change __CHANGE_TONE__">__CHANGE__</b></div><div class="metric"><span>Liquidity</span><b class="value">__LIQUIDITY__</b></div><div class="metric"><span>24h volume</span><b class="value">__VOLUME__</b></div><div class="metric"><span>Market cap / FDV</span><b class="value">__MARKET_CAP__</b></div><div class="metric"><span>Pair age</span><b class="value">__AGE__</b></div></div><div class="evidence"><strong>Why this token appeared</strong>__EVIDENCE__</div><div class="risk"><strong>Risk context</strong><p>__RISK__. Pool verification is not token verification. Inclusion is not an endorsement.</p></div></section>
<aside><section class="card"><span class="eyebrow">Qualification evidence</span><h3>Checks passed for this feed</h3><div class="check">Solana token identity</div><div class="check">Exact token and pool match</div><div class="check">Observed liquidity threshold</div><div class="check">Observed 24h activity</div><div class="check">Fresh collector data</div><div class="source">Collector updated __UPDATED__</div></section><section class="card jupiter" style="margin-top:14px"><span class="eyebrow">Jupiter execution</span><h3>Planned, not active</h3><span class="badge">READ-ONLY</span><p>No wallet connection, executable quote or swap is enabled. DexSato does not hold private keys or funds.</p></section></aside></div>
<footer><span>Experimental discovery · evidence synthesis only · not financial advice.</span><span>Informational price, chart data and future execution quotes are distinct.</span></footer></main><script>document.querySelectorAll("[data-copy-address]").forEach(function(button){button.addEventListener("click",async function(){try{await navigator.clipboard.writeText(button.dataset.copyAddress);button.textContent="Copied";window.setTimeout(function(){button.textContent="Copy"},1600)}catch(error){button.textContent="Unavailable"}})})</script></body></html>"""
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
    return html
