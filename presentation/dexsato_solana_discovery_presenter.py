"""Public read-only terminal for DexSato Solana Discovery."""

from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote


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
    age = escape(str(candidate.get("pair_age") or "Unavailable"))
    why_now = escape(_why_now(candidate))
    source = (
        f'<a class="inspect-link" href="/discovery/solana/{quote(address_raw, safe="")}">'
        'Open Analysis &rarr;</a>'
    ) if address_raw else ""
    return (
        f'<article class="candidate-row candidate-row-v32" data-token-address="{address}">'
        f'<div class="token-cell compact-token"><span class="rank">{rank:02d}</span><div>'
        f'<strong>{symbol} / {quote_symbol}</strong><span>{name}</span><small>{dex} / exact pool</small></div></div>'
        f'<div class="feed-value"><span>Price</span><strong>{price}</strong></div>'
        f'<div class="feed-value"><span>Liquidity</span><strong>{liquidity}</strong></div>'
        f'<div class="feed-value"><span>24h Vol</span><strong>{volume}</strong></div>'
        f'<div class="feed-value"><span>Age</span><strong>{age}</strong></div>'
        f'<div class="why-now"><span>Why now</span><strong><i class="why-dot" aria-hidden="true"></i>{why_now}</strong></div>'
        f'<div class="feed-action">{source}</div></article>'
    )


def render_solana_discovery_page(feed: dict[str, Any] | None = None) -> str:
    """Render qualified discovery evidence without implying token safety."""
    data = feed or {}
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
    candidate_rows = "".join(
        _candidate_row(item, rank)
        for rank, item in enumerate((item for item in candidates if isinstance(item, dict)), start=1)
    )
    empty_state = (
        '<div class="empty-state"><div class="empty-icon" aria-hidden="true">◎</div><div>'
        '<h3>Solana Discovery is preparing its first validated feed.</h3>'
        '<p>DexSato is validating token identity, exact-pool liquidity, market activity and freshness '
        'before showing candidates. No discovery tokens are available yet.</p>'
        '<div class="empty-actions"><a class="primary-link" href="/">Back to Markets</a>'
        '<a class="secondary-link" href="#qualification-rules">Review qualification rules</a></div></div></div>'
    )
    candidate_feed = f'<div class="candidate-list">{candidate_rows}</div>' if candidate_rows else empty_state
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DexSato · Solana Discovery Terminal</title>
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
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
    @media(max-width:480px){.shell{width:calc(100% - 16px)}.brand img{width:112px}.terminal-name strong{font-size:11px}.top-actions{margin-left:auto}.back-link{padding:7px 8px;font-size:10px}.theme-option{width:29px;height:29px}.terminal-head h1{font-size:25px}.terminal-head p{font-size:13px}.status-cluster{display:grid;grid-template-columns:1fr 1fr}.status-pill{padding:9px}.metric{padding:13px}.metric strong{font-size:19px}.feed-head{padding:15px}.filters button{font-size:9px}.token-cell,.market-cell,.evidence-cell,.action-cell{padding:14px}.market-cell{gap:7px}.candidate-row{border-left:2px solid var(--purple)}.action-cell{align-items:stretch;flex-direction:column}.inspect-link{text-align:center}.rail-card{padding:15px}.empty-state{margin:12px;padding:18px}.empty-actions{display:grid}.primary-link,.secondary-link{text-align:center}}
  </style>
</head>
<body><main class="shell">
  <header class="topbar"><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><div class="terminal-name"><strong>Solana Discovery</strong><span>Market intelligence terminal</span></div></div><div class="top-actions"><a class="back-link" href="/">← Markets</a><div class="theme-switcher" role="group" aria-label="Discovery theme"><button class="theme-option active" type="button" data-theme-option="current" aria-label="Use current dark theme" title="Current dark theme" aria-pressed="true">🌙</button><button class="theme-option" type="button" data-theme-option="intel" aria-label="Use market intelligence theme" title="Market intelligence theme" aria-pressed="false">MI</button><button class="theme-option" type="button" data-theme-option="plain" aria-label="Use plain white theme" title="Plain white theme" aria-pressed="false">☀️</button></div></div></header>
  <section class="terminal-head"><div><span class="eyebrow">Evidence-led Solana intelligence</span><h1>Solana Discovery Terminal</h1><p>Track emerging tokens through verified pool identity, observable liquidity and recent market activity. Discovery rank reflects activity, not safety.</p></div><div class="status-cluster"><div class="status-pill live"><span>Feed status</span><strong>__STATUS_HEADING__</strong><small>__STATUS_LABEL__</small></div><div class="status-pill"><span>Last update</span><strong>__UPDATED__</strong><small>Collector telemetry</small></div></div></section>
  <section class="metrics" aria-label="Discovery summary">
  <div class="metric metric-observed"><span>Tokens observed</span><strong>__TOKENS__</strong><small>Collector universe</small><span class="metric-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/></svg></span></div>
  <div class="metric metric-resolved"><span>Pairs resolved</span><strong>__PAIRS__</strong><small>Identity mapping</small><span class="metric-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="18" cy="17" r="2.5"/><path d="M8.5 11l7-3M8.5 13l7 3"/></svg></span></div>
  <div class="metric metric-qualified"><span>Qualified now</span><strong>__QUALIFIED__</strong><small>Exact-pool qualification</small><span class="metric-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 4.8-2.8 8.1-7 10-4.2-1.9-7-5.2-7-10V6l7-3z"/><path d="M8.5 12l2.2 2.2 4.8-5"/></svg></span></div>
  <div class="metric metric-network"><span>Network</span><strong>SOL</strong><small>Experimental discovery</small><span class="metric-icon sol-icon" aria-hidden="true"><svg viewBox="0 0 30 24"><path d="M6 3h17l3 3H9z"/><path d="M9 10h17l-3 3H6z"/><path d="M6 17h17l3 3H9z"/></svg></span></div>
</section>
  <div class="workspace"><section class="feed-panel"><div class="feed-head"><div><span class="eyebrow">Observed market activity</span><h2>Discovery Feed</h2><p>Qualified candidates sorted from the bounded, freshest pool review.</p></div><div class="feed-tools"><input class="search" type="search" placeholder="Search token, symbol, or address" aria-label="Search Solana discovery" disabled><div class="filters" role="group" aria-label="Discovery filters"><button type="button" disabled>All</button><button type="button" disabled>New activity</button><button type="button" disabled>Volume</button><button type="button" disabled>Liquidity</button></div></div></div><div class="feed-columns-v33" aria-hidden="true"><span>Token</span><span>Price</span><span>Liquidity</span><span>24h Vol</span><span>Age</span><span>Why Now</span><span></span></div>__CANDIDATE_FEED__</section>
  <aside class="intel-rail"><section class="rail-card"><span class="rail-kicker">Discovery status</span><h3>Current qualification</h3><div class="status-detail"><div><span>Observed</span><strong>__TOKENS__</strong></div><div><span>Resolved pools</span><strong>__PAIRS__</strong></div><div><span>Qualified</span><strong>__QUALIFIED__</strong></div><div><span>Updated</span><strong>__UPDATED__</strong></div></div></section>
  <section id="qualification-rules" class="rail-card"><span class="rail-kicker">Qualification rules</span><h3>A token must pass every check</h3><div class="rule-list"><div class="rule">Solana network identity</div><div class="rule">Exact token and pool match</div><div class="rule">Liquidity at least $5,000</div><div class="rule">24h volume at least $1,000</div><div class="rule">Fresh collector data</div></div></section>
  <section class="rail-card risk-card"><span class="rail-kicker">Risk notice</span><h3>Pool verification is not token verification</h3><strong>Token security is not independently assessed.</strong><p>Contract controls, holder concentration and rug-pull risk may remain unknown. Inclusion is not an endorsement.</p></section>
  <section class="rail-card jupiter-card"><span class="rail-kicker">Jupiter execution</span><h3>Planned, not active</h3><span class="jupiter-status">Read-only</span><p>No wallet connection, quote or trade capability is enabled. DexSato does not hold keys or funds.</p></section></aside></div>
  <footer><span>Experimental discovery · evidence synthesis only · not financial advice.</span><span>__STATUS_MESSAGE__</span></footer>
</main><script>
  const themeOptions=[...document.querySelectorAll("[data-theme-option]")];function applyTheme(theme){const value=theme==="plain"?"plain":theme==="intel"?"intel":"current";if(value==="current")delete document.documentElement.dataset.theme;else document.documentElement.dataset.theme=value;themeOptions.forEach(button=>{const active=button.dataset.themeOption===value;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));});try{localStorage.setItem("dexsato-theme",value);}catch(error){}}let saved="current";try{saved=localStorage.getItem("dexsato-theme")||"current";}catch(error){}applyTheme(saved);themeOptions.forEach(button=>button.addEventListener("click",()=>applyTheme(button.dataset.themeOption)));
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
