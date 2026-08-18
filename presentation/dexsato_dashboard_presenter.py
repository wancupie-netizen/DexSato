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


def build_intelligence_summary(
    *,
    token: str,
    decision: str,
    confidence: str,
    reasons: list[object],
) -> str:
    """Build a deterministic explanation grounded in engine output."""

    labels = [
        str(reason).replace("_", " ").title()
        for reason in reasons[:3]
    ]
    evidence = (
        f" Current evidence includes {', '.join(labels)}."
        if labels
        else " No supporting evidence is currently recorded."
    )
    messages = {
        "ALERT": (
            f"{token} requires immediate founder attention."
            f"{evidence} Confidence is {confidence}."
        ),
        "WATCH": (
            f"{token} remains under active observation."
            f"{evidence} Continue monitoring the next scan."
        ),
        "REVIEW": (
            f"{token} requires further evidence review."
            f"{evidence} Maintain REVIEW while conditions develop."
        ),
        "IGNORE": (
            f"Current evidence does not justify further attention for {token}."
            " Maintain IGNORE until a meaningful change is detected."
        ),
        "UNAVAILABLE": (
            f"{token} could not be evaluated in the current snapshot."
            " Wait for market data to become available."
        ),
        "REFERENCE": (
            f"{token} reference price collection is active."
            " Gold intelligence policy is not enabled yet."
        ),
    }
    return messages.get(
        decision,
        f"{token} remains in the {decision} decision state.{evidence}",
    )


def render_coin_logo(token: object) -> str:
    normalized = _status(token)
    source = COIN_LOGOS.get(normalized)
    fallback = _text(normalized[:4])
    if normalized == "XAU":
        return '<span class="commodity-fallback">Au</span>'
    if source is None:
        return f'<span class="coin-fallback">{fallback}</span>'
    return (
        f'<img src="{source}" alt="{_text(normalized)} official logo" '
        f'loading="lazy" onerror="this.hidden=true;'
        f'this.nextElementSibling.hidden=false">'
        f'<span class="coin-fallback" hidden>{fallback}</span>'
    )


def format_usd(value: object) -> str:
    """Format a market price without implying false precision."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Not available"
    if amount >= 1000:
        return f"${amount:,.2f}"
    if amount >= 1:
        return f"${amount:,.4f}"
    return f"${amount:,.6f}".rstrip("0").rstrip(".")


def format_compact_usd(value: object) -> str:
    """Format liquidity and other large USD market values."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Not available"
    absolute = abs(amount)
    if absolute >= 1_000_000_000:
        return f"${amount / 1_000_000_000:,.2f}B"
    if absolute >= 1_000_000:
        return f"${amount / 1_000_000:,.2f}M"
    if absolute >= 1_000:
        return f"${amount / 1_000:,.2f}K"
    return f"${amount:,.2f}"


def render_decision_card(coin: dict[str, object]) -> str:
    token = _status(coin.get("token"))
    pair = _text(coin.get("pair") or token)
    price = format_usd(coin.get("price"))
    liquidity = format_compact_usd(coin.get("liquidity"))
    available = coin.get("available", False) is True
    decision = _status(
        coin.get("decision") if available else "UNAVAILABLE"
    )
    confidence = _status(coin.get("confidence"))
    reasons = coin.get("reasons", [])
    if decision == "REFERENCE":
        reasons = coin.get("reference_evidence", [])
    if not isinstance(reasons, list):
        reasons = []
    summary = _text(
        coin.get("summary")
        if decision == "REFERENCE"
        else build_intelligence_summary(
            token=token,
            decision=decision,
            confidence=confidence,
            reasons=reasons,
        )
    )
    risk_note = _text(
        coin.get("risk_note")
        or "Current risk information is unavailable."
    )
    reason_items = "".join(
        f"<li>{_reason_label(reason)}</li>" for reason in reasons[:3]
    ) or "<li>No supporting evidence recorded.</li>"
    memory = (
        "Known pattern"
        if coin.get("seen_before", False) is True
        else "New pattern"
    )

    return f"""
    <article class="decision-card tone-{decision.lower()}"
        data-token="{_text(pair.lower())}"
        data-decision="{_text(decision.lower())}">
      <div class="coin-column">
        <div class="coin-logo">{render_coin_logo(token)}</div>
        <div>
          <h3>{_text(pair)}</h3>
          <small class="market-price">{_text(price)}</small>
          <small class="market-liquidity">Liquidity {_text(liquidity)}</small>
          <span class="decision-pill">{_text(decision)}</span>
          <p class="confidence">Confidence <strong>{_text(confidence)}</strong></p>
        </div>
      </div>
      <div class="evidence-column">
        <h4>Decision Evidence</h4>
        <ul>{reason_items}</ul>
      </div>
      <div class="summary-column">
        <h4>Intelligence Summary</h4>
        <p>{summary}</p>
        <h4 class="risk-note-heading">⚠ Risk Note</h4>
        <p class="risk-note">{risk_note}</p>
      </div>
      <button class="decision-button" type="button"
          data-open-token="{_text(token)}" aria-expanded="false">
        View Decision
      </button>
      <div class="decision-detail" hidden>
        <div><span>Market</span><strong>{_text(pair)}</strong></div>
        <div><span>Price</span><strong>{_text(price)}</strong></div>
        <div><span>Liquidity</span><strong>{_text(liquidity)}</strong></div>
        <div><span>Decision</span><strong>{_text(decision)}</strong></div>
        <div><span>Confidence</span><strong>{_text(confidence)}</strong></div>
        <div><span>Memory</span><strong>{_text(memory)}</strong></div>
        <p>{summary}</p>
        <p><strong>⚠ Risk Note:</strong> {risk_note}</p>
      </div>
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
        snapshot.get("generated_at", latest_run.get("generated_at")),
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
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
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
    .brand{{display:flex;align-items:center;margin:0 8px 34px}}
    .brand img{{display:block;width:100%;max-width:188px;height:auto}}
    nav{{display:grid;gap:9px}} nav a{{display:flex;align-items:center;gap:12px;padding:13px 15px;
      border-radius:10px;color:#bdc9da;text-decoration:none}} nav a.active{{background:#171c48;color:#a997ff}}
    nav span{{font-size:20px;width:24px;text-align:center}}
    .engine-card{{position:absolute;right:16px;bottom:26px;left:16px;padding:16px;border:1px solid var(--line);
      border-radius:12px;background:#09182a}} .engine-card strong,.engine-card small{{display:block}}
    .engine-card b{{color:var(--green)}} .engine-card small{{margin-top:10px;color:var(--muted)}}
    .content{{min-width:0;padding:22px 28px 18px}} .topbar{{display:flex;justify-content:space-between;gap:20px;align-items:start}}
    h1{{margin:0;font-size:30px}} .subtitle{{margin:7px 0 0;color:var(--muted)}} .top-actions{{display:flex;align-items:center;gap:10px}}
    .top-status{{display:flex;gap:10px}}
    .theme-switcher{{display:flex;gap:3px;padding:3px;border:1px solid var(--line);border-radius:10px;background:#091625}}
    .theme-option{{padding:7px 10px;border:0;border-radius:7px;background:transparent;color:#91a8c1;font-size:12px;font-weight:700;cursor:pointer}}
    .theme-option.active{{background:#1b1d4e;color:#fff;box-shadow:0 1px 4px rgba(0,0,0,.25)}}
    .theme-option:focus-visible{{outline:2px solid var(--cyan);outline-offset:2px}}
    .status-chip{{padding:11px 14px;border:1px solid var(--line);border-radius:9px;background:#091625;color:#cbd6e4}}
    .status-chip b{{color:var(--green)}} .workspace{{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;margin-top:22px}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
    .metric{{padding:16px;border:1px solid var(--line);border-radius:11px;background:linear-gradient(145deg,var(--panel2),#091727)}}
    .metric strong{{display:block;font-size:26px}} .metric span{{color:var(--muted)}} .section-title{{display:flex;justify-content:space-between;align-items:center}}
    .section-title h2{{margin:0;font-size:21px}} .search-wrap{{position:relative;width:min(310px,42vw)}}
    .search-wrap:before{{position:absolute;top:50%;left:13px;transform:translateY(-50%);color:#6f91b4;content:"⌕";font-size:20px}}
    .search-wrap input{{width:100%;padding:10px 38px;border:1px solid #254662;border-radius:9px;outline:0;background:#091827;color:#edf5ff}}
    .search-wrap input::placeholder{{color:#65809d}} .search-wrap input:focus{{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(35,217,210,.12)}}
    .clear-search{{position:absolute;top:50%;right:8px;transform:translateY(-50%);width:26px;height:26px;border:0;border-radius:50%;background:transparent;color:#8ba2bb;cursor:pointer}}
    .filters{{display:flex;gap:8px;margin:14px 0;overflow:auto}}
    .filters button{{padding:8px 14px;border:1px solid var(--line);border-radius:8px;background:#0b1929;color:#aebdd0;cursor:pointer}}
    .filters button.active{{border-color:var(--violet);background:#1b1d4e;color:#fff}}
    .decision-list{{display:grid;gap:12px}} .decision-card{{display:grid;grid-template-columns:250px 1fr 1.15fr 140px;
      align-items:center;min-height:150px;border:1px solid var(--line);border-left:2px solid var(--blue);
      border-radius:11px;background:linear-gradient(100deg,#0c1c2e,#081522);overflow:hidden}}
    .tone-alert{{border-left-color:var(--red)}} .tone-watch{{border-left-color:var(--amber)}}
    .tone-review{{border-left-color:var(--blue)}} .tone-reference{{border-left-color:var(--cyan)}} .tone-ignore,.tone-unavailable{{border-left-color:#718198}}
    .coin-column,.evidence-column,.summary-column{{min-width:0;padding:18px}}
    .coin-column{{display:flex;align-items:center;gap:16px}} .evidence-column,.summary-column{{border-left:1px solid #183149}}
    .coin-logo{{display:grid;place-items:center;flex:0 0 72px;width:72px;height:72px;border:1px solid #315474;
      border-radius:50%;background:#10253c;overflow:hidden}} .coin-logo img{{width:100%;height:100%;object-fit:cover}}
    .coin-fallback,.commodity-fallback{{font-weight:900}} .commodity-fallback{{color:#f7c948;font-size:25px}} h3{{margin:0 0 7px;font-size:24px}} h4{{margin:0 0 10px;font-size:13px}}
    .decision-pill{{display:inline-flex;padding:5px 10px;border:1px solid currentColor;border-radius:6px;font-size:12px;font-weight:800}}
    .tone-alert .decision-pill{{color:var(--red)}} .tone-watch .decision-pill{{color:var(--amber)}}
    .tone-review .decision-pill{{color:var(--blue)}} .tone-reference .decision-pill{{color:var(--cyan)}} .confidence{{margin:12px 0 3px;color:var(--muted);font-size:12px}}
    .confidence strong{{display:block;color:#f2c94c;font-size:13px}} .coin-column small{{display:block;margin-top:4px;color:var(--muted)}}
    ul{{margin:0;padding-left:18px;color:#cad7e5;font-size:14px}} li{{margin:8px 0}} .summary-column p{{margin:0;color:#bdcada;font-size:14px;line-height:1.55}} .risk-note-heading{{margin-top:14px!important;color:#ffbf3c}} .risk-note{{color:#f0dca8!important}}
    .decision-button{{margin-right:18px;padding:11px;border:1px solid var(--blue);border-radius:7px;background:transparent;color:#7fb0ff;cursor:pointer}}
    .decision-button:hover{{background:rgba(83,148,255,.1)}} .decision-detail{{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,1fr);gap:15px;padding:17px 20px;border-top:1px solid #183149;background:#071522}}
    .decision-detail span{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase}} .decision-detail strong{{display:block;margin-top:4px}}
    .decision-detail p{{grid-column:1/-1;margin:0;color:#bdcada;line-height:1.55}}
    .rail{{position:sticky;top:18px;display:grid;align-content:start;gap:12px;align-self:start}} .rail-card{{padding:17px;border:1px solid var(--line);border-radius:11px;background:#091827}}
    .rail-card h2{{margin:0 0 14px;font-size:17px}} .timeline{{padding:0;list-style:none}} .timeline li{{position:relative;margin:0;padding:0 0 18px 25px}}
    .timeline li:before{{position:absolute;top:9px;bottom:-8px;left:6px;width:1px;background:#34506d;content:""}}
    .timeline li:last-child:before{{display:none}} .timeline-dot{{position:absolute;top:5px;left:1px;width:11px;height:11px;border-radius:50%;background:var(--amber)}}
    .timeline-dot.neutral{{background:#7f91a5}} .timeline small{{display:block;margin-top:4px;color:var(--muted)}}
    .market-state{{display:grid;grid-template-columns:repeat(5,1fr);text-align:center}} .market-state div{{border-right:1px solid var(--line)}}
    .market-state div:last-child{{border:0}} .market-state span{{display:block;font-size:11px;color:var(--muted)}} .market-state strong{{font-size:25px}}
    .health-list{{display:grid;gap:10px}} .health-row{{display:flex;justify-content:space-between;color:var(--muted)}} .health-row b{{color:var(--green)}}
    .footer{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px;padding:15px;border:1px solid var(--line);
      border-radius:11px;color:var(--muted);text-align:center}} .footer b{{color:var(--green)}} .dedication{{grid-column:1/-1;color:#fff}}
    .mobile-toggle{{display:none}} [hidden]{{display:none!important}}
    html[data-theme="plain"]{{color-scheme:light;--bg:#f7f8fa;--panel:#fff;--panel2:#fff;--line:#dfe3e8;
      --text:#172033;--muted:#64748b;--violet:#6558d9;--cyan:#087f8c;--green:#14804a;--amber:#a86100;
      --red:#c83242;--blue:#2869c7}}
    html[data-theme="plain"] body{{background:#f7f8fa;color:var(--text)}}
    html[data-theme="plain"] .sidebar{{border-right-color:#e3e7ec;background:#fff;box-shadow:1px 0 0 rgba(15,23,42,.02)}}
    html[data-theme="plain"] .brand{{margin-right:0;margin-left:0;padding:7px;border-radius:9px;background:#071525}}
    html[data-theme="plain"] nav a{{color:#526071}}
    html[data-theme="plain"] nav a.active{{background:#eef0ff;color:#5548c8}}
    html[data-theme="plain"] .engine-card,
    html[data-theme="plain"] .status-chip,
    html[data-theme="plain"] .theme-switcher,
    html[data-theme="plain"] .rail-card{{border-color:#dfe3e8;background:#fff;color:#334155;box-shadow:0 1px 3px rgba(15,23,42,.04)}}
    html[data-theme="plain"] .theme-option{{color:#64748b}}
    html[data-theme="plain"] .theme-option.active{{background:#172033;color:#fff;box-shadow:none}}
    html[data-theme="plain"] .metric{{border-color:#dfe3e8;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.04)}}
    html[data-theme="plain"] .search-wrap:before{{color:#8290a3}}
    html[data-theme="plain"] .search-wrap input{{border-color:#cfd6df;background:#fff;color:#172033}}
    html[data-theme="plain"] .search-wrap input::placeholder{{color:#8a96a6}}
    html[data-theme="plain"] .filters button{{border-color:#dfe3e8;background:#fff;color:#526071}}
    html[data-theme="plain"] .filters button.active{{border-color:#172033;background:#172033;color:#fff}}
    html[data-theme="plain"] .decision-card{{border-color:#dfe3e8;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.04)}}
    html[data-theme="plain"] .coin-logo{{border-color:#d7dde5;background:#f2f5f8}}
    html[data-theme="plain"] .evidence-column,
    html[data-theme="plain"] .summary-column{{border-color:#e6e9ee}}
    html[data-theme="plain"] ul{{color:#435166}}
    html[data-theme="plain"] .summary-column p,
    html[data-theme="plain"] .decision-detail p{{color:#526071}}
    html[data-theme="plain"] .risk-note{{color:#805f1d!important}}
    html[data-theme="plain"] .decision-detail{{border-color:#e6e9ee;background:#f8fafc}}
    html[data-theme="plain"] .timeline li:before{{background:#d7dde5}}
    html[data-theme="plain"] .footer{{border-color:#dfe3e8;background:#fff}}
    html[data-theme="plain"] .dedication{{color:#172033}}
    @media(max-width:1180px){{.workspace{{grid-template-columns:1fr}}.rail{{position:static;grid-template-columns:repeat(3,1fr)}}.decision-card{{grid-template-columns:220px 1fr 1fr}}.decision-button{{grid-column:1/-1;margin:0 18px 16px}}}}
    @media(max-width:820px){{.app{{grid-template-columns:1fr}}.sidebar{{position:relative;height:auto}}nav,.engine-card{{display:none}}.content{{padding:18px}}.topbar{{display:block}}.top-actions{{align-items:flex-start;flex-direction:column;margin-top:14px}}.top-status{{overflow:auto;width:100%}}.metrics{{grid-template-columns:repeat(2,1fr)}}.section-title{{align-items:start;flex-direction:column;gap:12px}}.search-wrap{{width:100%}}.decision-card{{grid-template-columns:1fr}}.evidence-column,.summary-column{{border-top:1px solid #183149;border-left:0}}html[data-theme="plain"] .evidence-column,html[data-theme="plain"] .summary-column{{border-top-color:#e6e9ee}}.decision-button{{width:calc(100% - 36px)}}.decision-detail{{grid-template-columns:repeat(2,1fr)}}.rail{{grid-template-columns:1fr}}.footer{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <img src="/static/branding/dexsato-logo.png" alt="DexSato">
    </div>
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
      <div class="top-actions">
        <div class="theme-switcher" role="group" aria-label="Dashboard theme">
          <button class="theme-option active" type="button" data-theme-option="current" aria-pressed="true">Current</button>
          <button class="theme-option" type="button" data-theme-option="plain" aria-pressed="false">Plain White</button>
        </div>
        <div class="top-status"><span class="status-chip">● <b>System {_text(effective_health.title())}</b></span><span class="status-chip">Last scan <b id="last-scan-age">calculating…</b></span></div>
      </div>
    </header>
    <div class="workspace">
      <section>
        <div class="metrics">
          <div class="metric"><strong>{total}</strong><span>Markets Analysed</span></div>
          <div class="metric"><strong>{attention}</strong><span>Require Attention</span></div>
          <div class="metric"><strong>{_text(freshness.title())}</strong><span>Snapshot</span></div>
          <div class="metric"><strong id="next-scan">--:--</strong><span>Next Scan MYT</span></div>
        </div>
        <div id="decisions" class="section-title"><h2>Market Decisions</h2><div class="search-wrap">
          <input id="token-search" type="search" placeholder="Search BTC, ETH, SUI..." aria-label="Search market">
          <button id="clear-search" class="clear-search" type="button" aria-label="Clear search" hidden>×</button>
        </div></div>
        <div class="filters">
          <button class="active" data-filter="">All</button><button data-filter="alert">ALERT</button>
          <button data-filter="watch">WATCH</button><button data-filter="review">REVIEW</button><button data-filter="reference">REFERENCE</button><button data-filter="ignore">IGNORE</button><button data-filter="unavailable">UNAVAILABLE</button>
        </div>
        <div id="decision-list" class="decision-list">{cards}</div>
      </section>
      <aside class="rail">
        <section id="timeline" class="rail-card"><h2>Decision Timeline</h2><ol class="timeline">{_render_timeline(latest_run)}</ol></section>
        <section class="rail-card"><h2>Market State</h2><div class="market-state">
          <div><span>ALERT</span><strong>{counts["ALERT"]}</strong></div><div><span>WATCH</span><strong>{counts["WATCH"]}</strong></div>
          <div><span>REVIEW</span><strong>{counts["REVIEW"]}</strong></div><div><span>REFERENCE</span><strong>{counts["REFERENCE"]}</strong></div><div><span>IGNORE</span><strong>{counts["IGNORE"]}</strong></div>
        </div></section>
        <section class="rail-card"><h2>System Health</h2><div class="health-list">
          <div class="health-row"><span>Engine</span><b>ONLINE</b></div><div class="health-row"><span>Snapshot</span><b>{_text(freshness)}</b></div>
          <div class="health-row"><span>Telegram</span><b>{_text(telegram)}</b></div><div class="health-row"><span>Scheduler</span><b>{scheduler_label}</b></div>
        </div></section>
      </aside>
    </div>
    <footer class="footer"><span>Engine <b>{_text(health)}</b></span><span>Last completed scan <b id="completed-scan" data-generated-at="{generated_at}">calculating…</b></span>
      <span><b>{available}/{total}</b> markets available</span><span class="dedication">Made for Sya ❤️</span></footer>
  </main>
</div>
<script>
  const themeOptions=[...document.querySelectorAll("[data-theme-option]")];
  function applyTheme(theme){{
    const resolved=theme==="plain"?"plain":"current";
    if(resolved==="plain")document.documentElement.dataset.theme="plain";
    else delete document.documentElement.dataset.theme;
    themeOptions.forEach(button=>{{const active=button.dataset.themeOption===resolved;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));}});
    try{{localStorage.setItem("dexsato-theme",resolved);}}catch(error){{}}
  }}
  let savedTheme="current";
  try{{savedTheme=localStorage.getItem("dexsato-theme")||"current";}}catch(error){{}}
  applyTheme(savedTheme);
  themeOptions.forEach(button=>button.addEventListener("click",()=>applyTheme(button.dataset.themeOption)));
  const cards=[...document.querySelectorAll(".decision-card")];
  const search=document.getElementById("token-search");
  const clearSearch=document.getElementById("clear-search");
  const filters=[...document.querySelectorAll("[data-filter]")];
  let selected="";
  function applyFilters(){{
    const query=search.value.trim().toLowerCase();
    cards.forEach(card=>card.hidden=!((!selected||card.dataset.decision===selected)&&(!query||card.dataset.token.includes(query))));
  }}
  filters.forEach(button=>button.addEventListener("click",()=>{{filters.forEach(item=>item.classList.remove("active"));button.classList.add("active");selected=button.dataset.filter;applyFilters();}}));
  search.addEventListener("input",()=>{{clearSearch.hidden=!search.value;applyFilters();}});
  clearSearch.addEventListener("click",()=>{{search.value="";clearSearch.hidden=true;search.focus();applyFilters();}});
  document.querySelectorAll(".decision-button").forEach(button=>button.addEventListener("click",()=>{{
    const detail=button.parentElement.querySelector(".decision-detail");
    const opening=detail.hidden;
    detail.hidden=!opening;
    button.setAttribute("aria-expanded",String(opening));
    button.textContent=opening?"Close Decision":"View Decision";
  }}));
  function malaysiaParts(date){{return Object.fromEntries(new Intl.DateTimeFormat("en-CA",{{timeZone:"Asia/Kuala_Lumpur",hour:"2-digit",minute:"2-digit",hour12:false,year:"numeric",month:"2-digit",day:"2-digit"}}).formatToParts(date).filter(p=>p.type!=="literal").map(p=>[p.type,p.value]));}}
  function nextPlannedScan(now=new Date()){{const p=malaysiaParts(now),hours=[8,14,20];let h=hours.find(x=>x>Number(p.hour));if(h===undefined)h=8;return `${{String(h).padStart(2,"0")}}:00`;}}
  function updateNextScan(){{document.getElementById("next-scan").textContent=nextPlannedScan();}}
  function updateSnapshotAge(){{const raw="{generated_at}",time=new Date(raw),minutes=Math.max(0,Math.floor((Date.now()-time.getTime())/60000));document.getElementById("last-scan-age").textContent=Number.isNaN(minutes)?"unavailable":minutes<60?`${{minutes}} min ago`:`${{Math.floor(minutes/60)}} hr ago`;}}
  function formatMYT(raw){{const time=new Date(raw);if(Number.isNaN(time.getTime()))return"Not available";return new Intl.DateTimeFormat("en-MY",{{timeZone:"Asia/Kuala_Lumpur",day:"2-digit",month:"short",year:"numeric",hour:"numeric",minute:"2-digit",hour12:true}}).format(time)+" MYT";}}
  document.getElementById("completed-scan").textContent=formatMYT(document.getElementById("completed-scan").dataset.generatedAt);
  updateNextScan();updateSnapshotAge();window.setInterval(updateSnapshotAge,60000);
</script>
</body></html>"""
