"""Public read-only prototype for DexSato Solana Discovery."""

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
    return f"${amount:,.6f}" if amount < 1 else f"${amount:,.2f}"


def _candidate_card(candidate: dict[str, Any]) -> str:
    symbol = escape(str(candidate.get("symbol") or "Unknown"))
    name = escape(str(candidate.get("name") or "Unknown token"))
    quote = escape(str(candidate.get("quote_symbol") or "Unknown"))
    address = escape(str(candidate.get("token_address") or ""))
    pool = escape(str(candidate.get("pair_address") or ""))
    dex = escape(str(candidate.get("dex_id") or "Unknown"))
    price = escape(_usd(candidate.get("price_usd")))
    liquidity = escape(_usd(candidate.get("liquidity_usd")))
    volume = escape(_usd(candidate.get("volume_24h_usd")))
    age = escape(str(candidate.get("pair_age") or "Unavailable"))
    evidence = escape(str(candidate.get("evidence") or "Exact-pool activity observed."))
    risk = escape(str(candidate.get("risk_label") or "Token security not independently verified"))
    source_url = str(candidate.get("source_url") or "")
    source = ""
    if source_url.startswith("https://dexscreener.com/"):
        source = f'<a class="candidate-source" href="{escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">View verified pool ↗</a>'
    return (
        f'<article class="candidate-card" data-token-address="{address}">'
        f'<div class="candidate-head"><div><strong>{name}</strong><span>{symbol} / {quote} · {dex}</span></div><span class="candidate-label">Emerging activity</span></div>'
        f'<div class="candidate-contract"><span>Contract</span><code>{address}</code></div>'
        f'<div class="candidate-stats"><div><span>Price</span><strong>{price}</strong></div><div><span>Liquidity</span><strong>{liquidity}</strong></div><div><span>24h volume</span><strong>{volume}</strong></div><div><span>Pair age</span><strong>{age}</strong></div></div>'
        f'<div class="candidate-evidence"><strong>Why it appeared</strong><span>{evidence}</span></div>'
        f'<div class="candidate-risk"><strong>Risk context</strong><span>{risk}. Inclusion is not an endorsement.</span></div>'
        f'<div class="candidate-footer"><span>Exact pool <code>{pool}</code></span>{source}</div></article>'
    )


def render_solana_discovery_page(feed: dict[str, Any] | None = None) -> str:
    """Render collector telemetry without inventing qualified candidates."""
    data = feed or {}
    connected = data.get("connected") is True
    status_heading = "Collector telemetry is connected." if connected else "Discovery candidates are not connected yet."
    status_message = str(data.get("message") or "The collector remains separate while its data contract and qualification rules are validated.")
    tokens = str(data.get("tokens_observed")) if data.get("tokens_observed") is not None else "—"
    pairs = str(data.get("pair_resolved")) if data.get("pair_resolved") is not None else "—"
    updated = str(data.get("updated_label") or "Not connected")
    status_label = str(data.get("collector_status") or "Prototype state")
    candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
    qualified = str(data.get("qualified_candidates")) if data.get("qualified_candidates") is not None else "—"
    empty_state = '<div class="empty-state"><div class="empty-icon" aria-hidden="true">◎</div><div><h3>Solana Discovery is preparing its first validated feed.</h3><p>DexSato is validating token identity, exact-pool liquidity, market activity and freshness before showing candidates. No discovery tokens are available yet.</p><div class="empty-actions"><a class="primary-link" href="/">Back to Markets</a><a class="secondary-link" href="#how-discovery-works">Learn how discovery works</a></div></div></div>'
    candidate_feed = '<div class="candidate-grid">' + ''.join(_candidate_card(item) for item in candidates if isinstance(item, dict)) + '</div>' if candidates else empty_state
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DexSato · Solana Discovery</title>
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
  <script>try{if(localStorage.getItem("dexsato-theme")==="plain")document.documentElement.dataset.theme="plain";}catch(error){}</script>
  <style>
    :root{color-scheme:dark;--bg:#06111f;--panel:#0b1d30;--panel2:#10253c;--line:#203d59;--text:#f4f8ff;--muted:#91a8c2;--blue:#5394ff;--cyan:#23d9d2;--purple:#8b7bff;--amber:#f7b928;--green:#2dd38b}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 50% -12%,#132c50 0,transparent 36%),var(--bg);color:var(--text);font-family:"Segoe UI Variable Text","Segoe UI Variable","Segoe UI",Inter,system-ui,sans-serif;font-size:16px;line-height:1.55;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}
    button,input{font:inherit}.shell{width:min(1220px,calc(100% - 40px));margin:0 auto;padding:20px 0 40px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-bottom:18px;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:14px}.brand img{width:154px;padding:6px;border-radius:9px;background:#071525}.brand span{color:var(--muted);font-size:13px;font-weight:750}.top-actions,.theme-switcher{display:flex;align-items:center;gap:8px}.back-link{padding:9px 12px;border:1px solid var(--line);border-radius:9px;color:var(--text);font-size:13px;font-weight:800;text-decoration:none}.theme-switcher{gap:3px;padding:3px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}.theme-option{display:grid;place-items:center;width:34px;height:34px;padding:0;border:0;border-radius:7px;background:transparent;color:var(--muted);font-size:17px;cursor:pointer}.theme-option.active{background:#1b1d4e;color:#fff}.theme-option:focus-visible,.back-link:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
    .hero{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(310px,.75fr);gap:18px;margin:28px 0 16px}.hero-copy,.status-card,.metric,.discovery-panel,.empty-state,.how-it-works,.safety-card{border:1px solid var(--line);border-radius:14px;background:linear-gradient(145deg,var(--panel2),var(--panel))}.hero-copy{padding:30px}.eyebrow{color:var(--cyan);font-size:11px;font-weight:900;letter-spacing:.09em;text-transform:uppercase}.hero h1{max-width:690px;margin:10px 0 0;font-size:40px;line-height:1.12;letter-spacing:-.035em}.hero-copy p{max-width:720px;margin:13px 0 0;color:var(--muted);font-size:16px}.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:19px}.chip{padding:6px 9px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:11px;font-weight:850}.chip.experimental{border-color:rgba(247,185,40,.5);color:var(--amber)}.chip.solana{border-color:rgba(139,123,255,.55);color:#b8afff}.status-card{display:flex;flex-direction:column;justify-content:center;padding:26px;border-left:4px solid var(--amber)}.status-card small{color:var(--amber);font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.status-card strong{margin-top:8px;font-size:22px;line-height:1.3}.status-card p{margin:9px 0 0;color:var(--muted);font-size:13px}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}.metric{padding:17px}.metric span{display:block;color:var(--muted);font-size:12px}.metric strong{display:block;margin-top:6px;font-size:23px}.metric small{display:block;margin-top:3px;color:var(--muted)}
    .discovery-panel{padding:22px}.section-head{display:flex;align-items:end;justify-content:space-between;gap:18px}.section-head h2,.how-it-works h2{margin:0;font-size:25px}.section-head p,.how-it-works>p{margin:5px 0 0;color:var(--muted)}.search{width:min(360px,42vw);padding:11px 13px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);color:var(--text)}.search:disabled{cursor:not-allowed;opacity:.7}.filters{display:flex;gap:8px;margin:15px 0 18px;overflow-x:auto;scrollbar-width:none}.filters::-webkit-scrollbar{display:none}.filters button{padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:var(--panel2);color:var(--muted);font-size:12px;font-weight:800;white-space:nowrap}.filters button:first-child{border-color:var(--blue);color:var(--text)}.filters button:disabled{cursor:not-allowed;opacity:.65}
    .empty-state{display:grid;grid-template-columns:72px 1fr;gap:20px;align-items:center;padding:30px;border-style:dashed;background:rgba(16,37,60,.55)}.empty-icon{display:grid;place-items:center;width:72px;height:72px;border:1px solid rgba(139,123,255,.5);border-radius:50%;background:rgba(139,123,255,.08);font-size:30px}.empty-state h3{margin:0;font-size:21px}.empty-state p{max-width:760px;margin:7px 0 0;color:var(--muted)}.empty-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:16px}.primary-link,.secondary-link{padding:9px 12px;border-radius:8px;font-size:12px;font-weight:850;text-decoration:none}.primary-link{border:1px solid var(--blue);color:#8bb9ff}.secondary-link{border:1px solid var(--line);color:var(--text)}
    .lower-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-top:18px}.how-it-works,.safety-card{padding:24px}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:16px}.step{padding:16px;border-radius:10px;background:var(--panel2)}.step b{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:rgba(35,217,210,.1);color:var(--cyan);font-size:12px}.step strong{display:block;margin-top:10px}.step span{display:block;margin-top:5px;color:var(--muted);font-size:12px}.safety-card{border-left:3px solid var(--cyan)}.safety-card small{color:var(--cyan);font-size:10px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}.safety-card h2{margin:7px 0 0;font-size:21px}.safety-card p{margin:9px 0 0;color:var(--muted);font-size:13px}.future-box{margin-top:16px;padding:14px;border:1px solid var(--line);border-radius:9px;background:var(--panel2)}.future-box strong{display:block}.future-box span{display:block;margin-top:4px;color:var(--muted);font-size:12px}
    footer{display:flex;justify-content:space-between;gap:16px;margin-top:18px;color:var(--muted);font-size:12px}
    html[data-theme="plain"]{color-scheme:light;--bg:#f7f8fa;--panel:#fff;--panel2:#f1f4f7;--line:#dce2e8;--text:#152033;--muted:#607086;--blue:#2869c7;--cyan:#087f8c;--purple:#6557c7;--amber:#9a5b00;--green:#14804a}html[data-theme="plain"] body{background:#f7f8fa}html[data-theme="plain"] .theme-option.active{background:#172033;color:#fff}html[data-theme="plain"] .hero-copy,html[data-theme="plain"] .status-card,html[data-theme="plain"] .metric,html[data-theme="plain"] .discovery-panel,html[data-theme="plain"] .empty-state,html[data-theme="plain"] .how-it-works,html[data-theme="plain"] .safety-card{box-shadow:0 1px 3px rgba(15,23,42,.05)}
    @media(max-width:820px){.shell{width:min(100% - 24px,1220px);padding-top:12px}.hero,.lower-grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.section-head{align-items:flex-start;flex-direction:column}.search{width:100%}.steps{grid-template-columns:1fr}.empty-state{grid-template-columns:1fr}.empty-icon{width:60px;height:60px}.topbar{align-items:flex-start}.brand span{display:none}footer{flex-direction:column}}
    @media(max-width:480px){.shell{width:calc(100% - 20px)}.topbar{align-items:center}.brand img{width:132px}.top-actions{margin-left:auto}.back-link{padding:8px 9px;font-size:11px}.hero-copy{padding:23px}.hero h1{font-size:31px}.hero-copy p{font-size:14px;line-height:1.65}.status-card{padding:21px}.metrics{gap:9px}.metric{padding:14px}.metric strong{font-size:20px}.discovery-panel,.how-it-works,.safety-card{padding:17px}.filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));overflow:visible}.filters button:last-child{grid-column:1/-1}.empty-state{padding:22px}.empty-actions{display:grid}.primary-link,.secondary-link{text-align:center}}
  
    /* DexSato Discovery plain-theme empty-state hotfix */

    html[data-theme="plain"] .empty-state,
    html[data-theme="plain"] .empty,
    html[data-theme="plain"] .discovery-empty {
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
        color: #0f172a !important;
    }

    html[data-theme="plain"] .empty-state h2,
    html[data-theme="plain"] .empty-state h3,
    html[data-theme="plain"] .empty h2,
    html[data-theme="plain"] .empty h3,
    html[data-theme="plain"] .discovery-empty h2,
    html[data-theme="plain"] .discovery-empty h3 {
        color: #0f172a !important;
    }

    html[data-theme="plain"] .empty-state p,
    html[data-theme="plain"] .empty p,
    html[data-theme="plain"] .discovery-empty p {
        color: #475569 !important;
    }

    html[data-theme="plain"] .empty-icon {
        background: #eef2ff !important;
        border-color: #c7d2fe !important;
        color: #4338ca !important;
    }

    html[data-theme="plain"] .empty-actions a,
    html[data-theme="plain"] .empty-actions button {
        background: #ffffff !important;
        border-color: #cbd5e1 !important;
        color: #334155 !important;
    }

    html[data-theme="plain"] .empty-actions .primary {
        background: #eff6ff !important;
        border-color: #93c5fd !important;
        color: #1d4ed8 !important;
    }
    .candidate-grid{display:grid;gap:14px}.candidate-card{padding:19px;border:1px solid var(--line);border-radius:12px;background:var(--panel2)}.candidate-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.candidate-head>div strong,.candidate-head>div span{display:block}.candidate-head>div strong{font-size:18px}.candidate-head>div span,.candidate-contract span,.candidate-stats span,.candidate-evidence span,.candidate-risk span,.candidate-footer{color:var(--muted);font-size:12px}.candidate-label{padding:5px 8px;border:1px solid rgba(35,217,210,.4);border-radius:999px;color:var(--cyan);font-size:10px;font-weight:800}.candidate-contract{display:flex;flex-direction:column;gap:4px;margin-top:14px}.candidate-contract code,.candidate-footer code{font-size:11px;overflow-wrap:anywhere}.candidate-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px;padding:12px;border:1px solid var(--line);border-radius:9px;background:var(--panel)}.candidate-stats span,.candidate-stats strong{display:block}.candidate-stats strong{margin-top:4px}.candidate-evidence,.candidate-risk{display:flex;flex-direction:column;gap:4px;margin-top:12px}.candidate-evidence strong,.candidate-risk strong{font-size:12px}.candidate-risk{padding:10px;border-left:3px solid var(--amber);background:rgba(247,185,40,.07)}.candidate-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:14px}.candidate-footer>span{min-width:0}.candidate-source{color:var(--cyan);font-size:12px;font-weight:750;text-decoration:none;white-space:nowrap}@media(max-width:600px){.candidate-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.candidate-footer{align-items:flex-start;flex-direction:column}.candidate-head{flex-direction:column}}
</style>
</head>
<body><main class="shell">
  <header class="topbar"><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><span>Solana Discovery</span></div><div class="top-actions"><a class="back-link" href="/">← Markets</a><div class="theme-switcher" role="group" aria-label="Discovery theme"><button class="theme-option active" type="button" data-theme-option="current" aria-label="Use current dark theme" title="Current dark theme" aria-pressed="true">🌙</button><button class="theme-option" type="button" data-theme-option="plain" aria-label="Use plain white theme" title="Plain white theme" aria-pressed="false">☀️</button></div></div></header>
  <section class="hero"><div class="hero-copy"><span class="eyebrow">Evidence-led token discovery</span><h1>Find emerging Solana activity without mistaking attention for safety.</h1><p>DexSato will surface qualified token candidates using observable market activity, verified pool identity and transparent risk context.</p><div class="chips"><span class="chip experimental">Experimental</span><span class="chip solana">Solana network</span><span class="chip">Read-only preview</span></div></div><aside class="status-card"><small>Feed status</small><strong>__STATUS_HEADING__</strong><p>__STATUS_MESSAGE__</p></aside></section>
  <section class="metrics" aria-label="Discovery summary"><div class="metric"><span>Tokens observed</span><strong>__TOKENS__</strong><small>Collector universe, not recommendations</small></div><div class="metric"><span>Pairs resolved</span><strong>__PAIRS__</strong><small>Identity mapping only</small></div><div class="metric"><span>Qualified candidates</span><strong>__QUALIFIED__</strong><small>Exact-pool qualification</small></div><div class="metric"><span>Data updated</span><strong>__UPDATED__</strong><small>__STATUS_LABEL__</small></div></section>
  <section class="discovery-panel"><div class="section-head"><div><h2>Discovery Feed</h2><p>Candidate results appear only after token identity, pool liquidity and market activity are validated.</p></div><input class="search" type="search" placeholder="Search token name, symbol, or contract address" aria-label="Search Solana discovery" disabled></div><div class="filters" role="group" aria-label="Discovery filters"><button type="button" disabled>All</button><button type="button" disabled>Newly active</button><button type="button" disabled>Volume rising</button><button type="button" disabled>Liquidity improving</button><button type="button" disabled>Higher risk</button></div>__CANDIDATE_FEED__</section>
  <div class="lower-grid"><section id="how-discovery-works" class="how-it-works"><h2>How discovery will work</h2><p>A token must earn its place in the feed through observable evidence.</p><div class="steps"><div class="step"><b>1</b><strong>Discover activity</strong><span>Identify emerging activity from the validated Solana data pipeline.</span></div><div class="step"><b>2</b><strong>Verify the market</strong><span>Match the canonical token address to a specific observable pool.</span></div><div class="step"><b>3</b><strong>Review evidence and risk</strong><span>Explain why it appeared and disclose what remains unknown.</span></div></div></section><aside class="safety-card"><small>Non-custodial by design</small><h2>DexSato will not hold your keys or funds.</h2><p>A future Jupiter integration will require users to approve transactions in their own connected wallet. Discovery inclusion will never be an endorsement or guarantee of safety.</p><div class="future-box"><strong>Jupiter execution · planned, not active</strong><span>No wallet connection, quote or trading capability is enabled in this prototype.</span></div></aside></div>
  <footer><span>Experimental discovery · not financial advice.</span><span>No private keys, seed phrases or user funds are stored by DexSato.</span></footer>
</main><script>
  const themeOptions=[...document.querySelectorAll("[data-theme-option]")];function applyTheme(theme){const value=theme==="plain"?"plain":"current";if(value==="plain")document.documentElement.dataset.theme="plain";else delete document.documentElement.dataset.theme;themeOptions.forEach(button=>{const active=button.dataset.themeOption===value;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));});try{localStorage.setItem("dexsato-theme",value);}catch(error){}}let saved="current";try{saved=localStorage.getItem("dexsato-theme")||"current";}catch(error){}applyTheme(saved);themeOptions.forEach(button=>button.addEventListener("click",()=>applyTheme(button.dataset.themeOption)));
</script></body></html>"""
    return (
        page.replace("__STATUS_HEADING__", escape(status_heading))
        .replace("__STATUS_MESSAGE__", escape(status_message))
        .replace("__TOKENS__", escape(tokens))
        .replace("__PAIRS__", escape(pairs))
        .replace("__QUALIFIED__", escape(qualified))
        .replace("__UPDATED__", escape(updated))
        .replace("__STATUS_LABEL__", escape(status_label))
        .replace("__CANDIDATE_FEED__", candidate_feed)
    )
