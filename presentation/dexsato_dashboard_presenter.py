"""High-fidelity DexSato Founder V1 decision dashboard."""

from __future__ import annotations

from collections import Counter
from html import escape


COIN_LOGOS = {
    token: (
        "https://s2.coinmarketcap.com/static/img/coins/128x128/"
        f"{coin_id}.png"
    )
    for token, coin_id in {
        "BTC": 1,
        "ETH": 1027,
        "SOL": 5426,
        "SUI": 20947,
        "LINK": 1975,
        "AAVE": 7278,
        "PEPE": 24478,
        "BONK": 23095,
        "XRP": 52,
        "DOGE": 74,
        "ADA": 2010,
        "BNB": 1839,
        "AVAX": 5805,
    }.items()
}


def _text(value: object, fallback: str = "UNKNOWN") -> str:
    resolved = str(value if value is not None else fallback).strip()
    return escape(resolved or fallback, quote=True)


def _status(value: object, fallback: str = "UNKNOWN") -> str:
    return str(value if value is not None else fallback).strip().upper()


def _reason_label(value: object) -> str:
    return _text(str(value).replace("_", " ").title())


def render_coin_logo(token: object) -> str:
    normalized = _status(token)
    source = COIN_LOGOS.get(normalized)
    fallback = _text(normalized[:4])
    if source is None:
        return f'<span class="coin-fallback">{fallback}</span>'
    return (
        f'<img src="{source}" alt="{_text(normalized)} official logo" '
        f'loading="lazy" onerror="this.hidden=true;'
        f'this.nextElementSibling.hidden=false">'
        f'<span class="coin-fallback" hidden>{fallback}</span>'
    )


def render_decision_card(coin: dict[str, object]) -> str:
    token = _status(coin.get("token"))
    available = coin.get("available", False) is True
    decision = _status(
        coin.get("decision") if available else "UNAVAILABLE"
    )
    confidence = _status(coin.get("confidence"))
    summary = _text(
        coin.get("summary"),
        "Market intelligence is not available for this snapshot.",
    )
    reasons = coin.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    reason_items = "".join(
        f"<li>{_reason_label(reason)}</li>" for reason in reasons[:3]
    ) or "<li>No supporting evidence recorded.</li>"
    historical = coin.get("historical_success", 0)
    try:
        historical_label = f"{float(historical):.2f}%"
    except (TypeError, ValueError):
        historical_label = "0.00%"

    return f"""
    <article class="decision-card tone-{decision.lower()}"
        data-token="{_text(token.lower())}"
        data-decision="{_text(decision.lower())}">
      <div class="coin-column">
        <div class="coin-logo">{render_coin_logo(token)}</div>
        <div>
          <h3>{_text(token)}</h3>
          <span class="decision-pill">{_text(decision)}</span>
          <p class="confidence">Confidence <strong>{_text(confidence)}</strong></p>
          <small>Historical {historical_label}</small>
        </div>
      </div>
      <div class="evidence-column">
        <h4>Why It Changed</h4>
        <ul>{reason_items}</ul>
      </div>
      <div class="summary-column">
        <h4>Intelligence Summary</h4>
        <p>{summary}</p>
      </div>
      <button class="decision-button" type="button"
          data-open-token="{_text(token)}">View Decision</button>
    </article>
    """


def _render_timeline(latest_run: dict[str, object]) -> str:
    changes = latest_run.get("change_summaries", [])
    if not isinstance(changes, list):
        changes = []
    entries = [
        f'<li><span class="timeline-dot"></span><strong>{_text(change)}</strong>'
        '<small>Latest completed scan</small></li>'
        for change in changes[:3]
    ]
    entries.append(
        '<li><span class="timeline-dot neutral"></span>'
        '<strong>Snapshot completed</strong><small>Founder automation</small></li>'
    )
    return "".join(entries)


def render_dexsato_dashboard(
    snapshot: dict[str, object],
    *,
    system_status: dict[str, object] | None = None,
) -> str:
    if not isinstance(snapshot, dict):
        raise ValueError("Founder snapshot must be a dictionary.")
    coins = snapshot.get("coins")
    if not isinstance(coins, list):
        raise ValueError("Founder snapshot coin data must be a list.")

    resolved_coins = [coin for coin in coins if isinstance(coin, dict)]
    cards = "".join(render_decision_card(coin) for coin in resolved_coins)
    counts = Counter(
        _status(
            coin.get("decision")
            if coin.get("available", False) is True
            else "UNAVAILABLE"
        )
        for coin in resolved_coins
    )
    attention = counts["ALERT"] + counts["WATCH"]
    status = system_status if isinstance(system_status, dict) else {}
    health = _status(status.get("overall_health"))
    snapshot_health = status.get("snapshot", {})
    if not isinstance(snapshot_health, dict):
        snapshot_health = {}
    freshness = _status(snapshot_health.get("status"))
    latest_run = status.get("latest_run", {})
    if not isinstance(latest_run, dict):
        latest_run = {}
    telegram = _status(latest_run.get("telegram_status"), "NOT RUN YET")
    generated_at = _text(
        latest_run.get("generated_at", snapshot.get("generated_at")),
        "Not available",
    )
    tasks = status.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    scheduler_healthy = bool(tasks) and all(
        isinstance(task, dict)
        and task.get("installed") is True
        and _status(task.get("last_result_status")) in {"SUCCESS", "NOT RUN YET"}
        for task in tasks
    )
    scheduler_label = "HEALTHY" if scheduler_healthy else "ATTENTION"
    effective_health = (
        health
        if scheduler_healthy
        else "ATTENTION"
    )
    total = _text(snapshot.get("total_coins", len(resolved_coins)))
    available = _text(snapshot.get("available_coins", 0))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DexSato Market Decision Intelligence</title>
  <style>
    :root{{--bg:#06111f;--panel:#0b1a2c;--panel2:#0d2034;--line:#1d3852;
      --text:#f5f8ff;--muted:#91a8c1;--violet:#8068ff;--cyan:#23d9d2;
      --green:#39df9a;--amber:#f7b928;--red:#ff5364;--blue:#5394ff}}
    *{{box-sizing:border-box}} html{{color-scheme:dark}}
    body{{margin:0;background:radial-gradient(circle at 50% -20%,#102746 0,transparent 35%),var(--bg);
      color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}
    button,input{{font:inherit}} .app{{min-height:100vh;display:grid;grid-template-columns:230px 1fr}}
    .sidebar{{position:sticky;top:0;height:100vh;padding:26px 16px;border-right:1px solid #132941;
      background:linear-gradient(180deg,#06101d,#071525)}}
    .brand{{display:flex;align-items:center;gap:11px;margin:0 14px 34px;font-size:20px;font-weight:800;letter-spacing:.08em}}
    .brand-mark{{display:grid;place-items:center;width:38px;height:44px;border:2px solid var(--cyan);
      color:var(--cyan);clip-path:polygon(0 0,72% 0,100% 22%,100% 78%,72% 100%,0 100%)}}
    nav{{display:grid;gap:9px}} nav a{{display:flex;align-items:center;gap:12px;padding:13px 15px;
      border-radius:10px;color:#bdc9da;text-decoration:none}} nav a.active{{background:#171c48;color:#a997ff}}
    nav span{{font-size:20px;width:24px;text-align:center}}
    .engine-card{{position:absolute;right:16px;bottom:26px;left:16px;padding:16px;border:1px solid var(--line);
      border-radius:12px;background:#09182a}} .engine-card strong,.engine-card small{{display:block}}
    .engine-card b{{color:var(--green)}} .engine-card small{{margin-top:10px;color:var(--muted)}}
    .content{{min-width:0;padding:22px 28px 18px}} .topbar{{display:flex;justify-content:space-between;gap:20px;align-items:start}}
    h1{{margin:0;font-size:30px}} .subtitle{{margin:7px 0 0;color:var(--muted)}} .top-status{{display:flex;gap:10px}}
    .status-chip{{padding:11px 14px;border:1px solid var(--line);border-radius:9px;background:#091625;color:#cbd6e4}}
    .status-chip b{{color:var(--green)}} .workspace{{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;margin-top:22px}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
    .metric{{padding:16px;border:1px solid var(--line);border-radius:11px;background:linear-gradient(145deg,var(--panel2),#091727)}}
    .metric strong{{display:block;font-size:26px}} .metric span{{color:var(--muted)}} .section-title{{display:flex;justify-content:space-between;align-items:center}}
    .section-title h2{{margin:0;font-size:21px}} .filters{{display:flex;gap:8px;margin:14px 0}}
    .filters button{{padding:8px 14px;border:1px solid var(--line);border-radius:8px;background:#0b1929;color:#aebdd0;cursor:pointer}}
    .filters button.active{{border-color:var(--violet);background:#1b1d4e;color:#fff}}
    .decision-list{{display:grid;gap:12px}} .decision-card{{display:grid;grid-template-columns:250px 1fr 1.15fr 140px;
      align-items:center;min-height:150px;border:1px solid var(--line);border-left:2px solid var(--blue);
      border-radius:11px;background:linear-gradient(100deg,#0c1c2e,#081522);overflow:hidden}}
    .tone-alert{{border-left-color:var(--red)}} .tone-watch{{border-left-color:var(--amber)}}
    .tone-review{{border-left-color:var(--blue)}} .tone-ignore,.tone-unavailable{{border-left-color:#718198}}
    .coin-column,.evidence-column,.summary-column{{min-width:0;padding:18px}}
    .coin-column{{display:flex;align-items:center;gap:16px}} .evidence-column,.summary-column{{border-left:1px solid #183149}}
    .coin-logo{{display:grid;place-items:center;flex:0 0 72px;width:72px;height:72px;border:1px solid #315474;
      border-radius:50%;background:#10253c;overflow:hidden}} .coin-logo img{{width:100%;height:100%;object-fit:cover}}
    .coin-fallback{{font-weight:900}} h3{{margin:0 0 7px;font-size:24px}} h4{{margin:0 0 10px;font-size:13px}}
    .decision-pill{{display:inline-flex;padding:5px 10px;border:1px solid currentColor;border-radius:6px;font-size:12px;font-weight:800}}
    .tone-alert .decision-pill{{color:var(--red)}} .tone-watch .decision-pill{{color:var(--amber)}}
    .tone-review .decision-pill{{color:var(--blue)}} .confidence{{margin:12px 0 3px;color:var(--muted);font-size:12px}}
    .confidence strong{{display:block;color:#f2c94c;font-size:13px}} .coin-column small{{color:var(--muted)}}
    ul{{margin:0;padding-left:18px;color:#c1cedc}} li{{margin:8px 0}} .summary-column p{{margin:0;color:#aebdd0;line-height:1.55}}
    .decision-button{{margin-right:18px;padding:11px;border:1px solid var(--blue);border-radius:7px;background:transparent;color:#7fb0ff;cursor:pointer}}
    .rail{{display:grid;align-content:start;gap:12px}} .rail-card{{padding:17px;border:1px solid var(--line);border-radius:11px;background:#091827}}
    .rail-card h2{{margin:0 0 14px;font-size:17px}} .timeline{{padding:0;list-style:none}} .timeline li{{position:relative;margin:0;padding:0 0 18px 25px}}
    .timeline li:before{{position:absolute;top:9px;bottom:-8px;left:6px;width:1px;background:#34506d;content:""}}
    .timeline li:last-child:before{{display:none}} .timeline-dot{{position:absolute;top:5px;left:1px;width:11px;height:11px;border-radius:50%;background:var(--amber)}}
    .timeline-dot.neutral{{background:#7f91a5}} .timeline small{{display:block;margin-top:4px;color:var(--muted)}}
    .market-state{{display:grid;grid-template-columns:repeat(4,1fr);text-align:center}} .market-state div{{border-right:1px solid var(--line)}}
    .market-state div:last-child{{border:0}} .market-state span{{display:block;font-size:11px;color:var(--muted)}} .market-state strong{{font-size:25px}}
    .health-list{{display:grid;gap:10px}} .health-row{{display:flex;justify-content:space-between;color:var(--muted)}} .health-row b{{color:var(--green)}}
    .footer{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px;padding:15px;border:1px solid var(--line);
      border-radius:11px;color:var(--muted);text-align:center}} .footer b{{color:var(--green)}} .dedication{{grid-column:1/-1;color:#fff}}
    .mobile-toggle{{display:none}} [hidden]{{display:none!important}}
    @media(max-width:1180px){{.workspace{{grid-template-columns:1fr}}.rail{{grid-template-columns:repeat(3,1fr)}}.decision-card{{grid-template-columns:220px 1fr 1fr}}.decision-button{{grid-column:1/-1;margin:0 18px 16px}}}}
    @media(max-width:820px){{.app{{grid-template-columns:1fr}}.sidebar{{position:relative;height:auto}}nav,.engine-card{{display:none}}.content{{padding:18px}}.topbar{{display:block}}.top-status{{margin-top:14px;overflow:auto}}.metrics{{grid-template-columns:repeat(2,1fr)}}.decision-card{{grid-template-columns:1fr}}.evidence-column,.summary-column{{border-top:1px solid #183149;border-left:0}}.rail{{grid-template-columns:1fr}}.footer{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand"><span class="brand-mark">D</span> DEXSATO</div>
    <nav>
      <a class="active" href="#"><span>⌂</span>Overview</a>
      <a href="#decisions"><span>◉</span>Market Radar</a>
      <a href="#timeline"><span>◷</span>Decision History</a>
      <a href="/api/system-status"><span>⌁</span>System Health</a>
      <a href="#decisions"><span>☆</span>Watchlist</a>
      <a href="#"><span>⚙</span>Settings</a>
    </nav>
    <div class="engine-card"><strong>Decision Engine</strong><b>● ONLINE</b><small>3 scheduled scans daily</small></div>
  </aside>
  <main class="content">
    <header class="topbar">
      <div><h1>Market Decision Intelligence</h1><p class="subtitle">Evidence-led decisions across the Founder V1 market universe.</p></div>
      <div class="top-status"><span class="status-chip">● <b>System {_text(effective_health.title())}</b></span><span class="status-chip">Last scan <b id="last-scan-age">calculating…</b></span></div>
    </header>
    <div class="workspace">
      <section>
        <div class="metrics">
          <div class="metric"><strong>{total}</strong><span>Markets Analysed</span></div>
          <div class="metric"><strong>{attention}</strong><span>Require Attention</span></div>
          <div class="metric"><strong>{_text(freshness.title())}</strong><span>Snapshot</span></div>
          <div class="metric"><strong id="next-scan">--:--</strong><span>Next Scan MYT</span></div>
        </div>
        <div id="decisions" class="section-title"><h2>Market Decisions</h2><input id="token-search" type="search" placeholder="Search market" aria-label="Search market"></div>
        <div class="filters">
          <button class="active" data-filter="">All</button><button data-filter="alert">ALERT</button>
          <button data-filter="watch">WATCH</button><button data-filter="review">REVIEW</button><button data-filter="ignore">IGNORE</button>
        </div>
        <div id="decision-list" class="decision-list">{cards}</div>
      </section>
      <aside class="rail">
        <section id="timeline" class="rail-card"><h2>Decision Timeline</h2><ol class="timeline">{_render_timeline(latest_run)}</ol></section>
        <section class="rail-card"><h2>Market State</h2><div class="market-state">
          <div><span>ALERT</span><strong>{counts["ALERT"]}</strong></div><div><span>WATCH</span><strong>{counts["WATCH"]}</strong></div>
          <div><span>REVIEW</span><strong>{counts["REVIEW"]}</strong></div><div><span>IGNORE</span><strong>{counts["IGNORE"]}</strong></div>
        </div></section>
        <section class="rail-card"><h2>System Health</h2><div class="health-list">
          <div class="health-row"><span>Engine</span><b>ONLINE</b></div><div class="health-row"><span>Snapshot</span><b>{_text(freshness)}</b></div>
          <div class="health-row"><span>Telegram</span><b>{_text(telegram)}</b></div><div class="health-row"><span>Scheduler</span><b>{scheduler_label}</b></div>
        </div></section>
      </aside>
    </div>
    <footer class="footer"><span>Engine <b>{_text(health)}</b></span><span>Last completed scan <b>{generated_at}</b></span>
      <span><b>{available}/{total}</b> markets available</span><span class="dedication">Made for Sya ❤️</span></footer>
  </main>
</div>
<script>
  const cards=[...document.querySelectorAll(".decision-card")];
  const search=document.getElementById("token-search");
  const filters=[...document.querySelectorAll("[data-filter]")];
  let selected="";
  function applyFilters(){{
    const query=search.value.trim().toLowerCase();
    cards.forEach(card=>card.hidden=!((!selected||card.dataset.decision===selected)&&(!query||card.dataset.token.includes(query))));
  }}
  filters.forEach(button=>button.addEventListener("click",()=>{{filters.forEach(item=>item.classList.remove("active"));button.classList.add("active");selected=button.dataset.filter;applyFilters();}}));
  search.addEventListener("input",applyFilters);
  function malaysiaParts(date){{return Object.fromEntries(new Intl.DateTimeFormat("en-CA",{{timeZone:"Asia/Kuala_Lumpur",hour:"2-digit",minute:"2-digit",hour12:false,year:"numeric",month:"2-digit",day:"2-digit"}}).formatToParts(date).filter(p=>p.type!=="literal").map(p=>[p.type,p.value]));}}
  function nextPlannedScan(now=new Date()){{const p=malaysiaParts(now),hours=[8,14,20];let h=hours.find(x=>x>Number(p.hour));if(h===undefined)h=8;return `${{String(h).padStart(2,"0")}}:00`;}}
  function updateNextScan(){{document.getElementById("next-scan").textContent=nextPlannedScan();}}
  function updateSnapshotAge(){{const raw="{generated_at}",time=new Date(raw),minutes=Math.max(0,Math.floor((Date.now()-time.getTime())/60000));document.getElementById("last-scan-age").textContent=Number.isNaN(minutes)?"unavailable":minutes<60?`${{minutes}} min ago`:`${{Math.floor(minutes/60)}} hr ago`;}}
  updateNextScan();updateSnapshotAge();window.setInterval(updateSnapshotAge,60000);
</script>
</body></html>"""
