"""Presentation for the DexSato internal operations console."""

from __future__ import annotations

from collections import Counter
from html import escape


def _text(value: object, fallback: str = "Not available") -> str:
    text = str(value).strip() if value is not None else ""
    return escape(text or fallback)


def _status(value: object, fallback: str = "UNKNOWN") -> str:
    text = str(value).strip().upper() if value is not None else ""
    return text or fallback


def _effective_overall_health(
    base: str,
    *,
    freshness: str,
    provider: str,
    scheduler_healthy: bool,
    telegram: str,
) -> str:
    """Aggregate operations health without masking a failing dependency."""
    degraded_states = {"DEGRADED", "FAILED", "OFFLINE", "MISSING", "STALE"}
    if base in degraded_states or freshness in degraded_states or provider == "DEGRADED":
        return "DEGRADED"
    if (
        base == "ATTENTION"
        or not scheduler_healthy
        or telegram in {"FAILED", "ERROR"}
        or provider == "RECOVERED"
    ):
        return "ATTENTION"
    return "HEALTHY" if base == "HEALTHY" else base


def render_admin_system_page(
    snapshot: dict[str, object],
    *,
    system_status: dict[str, object] | None = None,
) -> str:
    """Render operational state separately from the trader experience."""
    if not isinstance(snapshot, dict):
        raise ValueError("Admin snapshot must be a dictionary.")
    coins = snapshot.get("coins")
    if not isinstance(coins, list):
        raise ValueError("Admin snapshot coin data must be a list.")

    resolved = [coin for coin in coins if isinstance(coin, dict)]
    counts = Counter(
        _status(coin.get("decision") if coin.get("available") is True else "UNAVAILABLE")
        for coin in resolved
    )
    status = system_status if isinstance(system_status, dict) else {}
    snapshot_health = status.get("snapshot") if isinstance(status.get("snapshot"), dict) else {}
    latest_run = status.get("latest_run") if isinstance(status.get("latest_run"), dict) else {}
    tasks = status.get("tasks") if isinstance(status.get("tasks"), list) else []
    scheduler_healthy = bool(tasks) and all(
        isinstance(task, dict)
        and task.get("installed") is True
        and _status(task.get("last_result_status")) in {"SUCCESS", "NOT RUN YET"}
        for task in tasks
    )

    provider_health = snapshot.get("provider_health")
    if not isinstance(provider_health, dict):
        provider_health = {}
    providers = provider_health.get("providers")
    if not isinstance(providers, list):
        providers = []
    provider_rows = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        provider_status = _status(provider.get("status"))
        provider_rows.append(
            '<div class="provider-row"><div><strong>'
            f'{_text(provider.get("provider"))}</strong><small>'
            f'{_text(provider.get("logical_requests"), "0")} requests · '
            f'{_text(provider.get("retries"), "0")} retries · '
            f'{_text(provider.get("failures"), "0")} failures</small></div>'
            f'<b class="state-{provider_status.lower()}">{_text(provider_status.title())}</b></div>'
        )
    provider_content = "".join(provider_rows) or '<p class="empty">No provider activity recorded for this snapshot.</p>'

    generated_at = _text(snapshot.get("generated_at", latest_run.get("generated_at")))
    base_overall = _status(status.get("overall_health"))
    freshness = _status(snapshot_health.get("status"))
    provider_overall = _status(provider_health.get("status"), "NO ACTIVITY")
    telegram = _status(latest_run.get("telegram_status"), "NOT RUN YET")
    scheduler = "HEALTHY" if scheduler_healthy else "ATTENTION"
    overall = _effective_overall_health(
        base_overall,
        freshness=freshness,
        provider=provider_overall,
        scheduler_healthy=scheduler_healthy,
        telegram=telegram,
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DexSato Admin · System Operations</title>
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
  <style>
    :root{{--bg:#06111f;--panel:#0b1a2c;--line:#1d3852;--text:#f5f8ff;--muted:#91a8c1;--green:#39df9a;--amber:#f7b928;--red:#ff5364;--cyan:#23d9d2}}
    *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.5}}
    .shell{{width:min(1180px,calc(100% - 32px));margin:0 auto;padding:24px 0 40px}}
    header{{display:flex;align-items:center;justify-content:space-between;gap:20px;padding-bottom:20px;border-bottom:1px solid var(--line)}}
    .brand{{display:flex;align-items:center;gap:14px}} .brand img{{width:142px;padding:6px;border-radius:9px;background:#071525}} .brand span{{color:var(--muted);font-weight:700}}
    .back{{padding:10px 14px;border:1px solid var(--line);border-radius:9px;color:var(--text);text-decoration:none;font-weight:700}}
    .intro{{display:flex;align-items:end;justify-content:space-between;gap:20px;margin:30px 0 20px}} h1{{margin:0;font-size:30px}} .intro p{{margin:6px 0 0;color:var(--muted)}} .updated{{color:var(--muted);font-size:12px}}
    .summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}} .summary-card,.card{{border:1px solid var(--line);border-radius:12px;background:var(--panel)}}
    .summary-card{{padding:16px}} .summary-card span{{display:block;color:var(--muted);font-size:12px}} .summary-card strong{{display:block;margin-top:5px;font-size:21px}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .card{{padding:20px}} .card-wide{{grid-column:1/-1}} h2{{margin:0 0 16px;font-size:18px}}
    .market-state{{display:grid;grid-template-columns:repeat(6,1fr)}} .market-state div{{padding:10px;border-right:1px solid var(--line);text-align:center}} .market-state div:last-child{{border:0}} .market-state span{{display:block;color:var(--muted);font-size:10px}} .market-state strong{{font-size:24px}}
    .health-list{{display:grid;gap:0}} .health-row,.provider-row{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 0;border-bottom:1px solid var(--line)}} .health-row:last-child,.provider-row:last-child{{border:0}} .health-row span,.provider-row small,.empty{{color:var(--muted)}} .provider-row strong,.provider-row small{{display:block}} .provider-row small{{margin-top:3px;font-size:11px}}
    b{{color:var(--green)}} .state-degraded,.state-failed{{color:var(--red)}} .state-recovered,.state-attention{{color:var(--amber)}}
    .policy{{margin-top:18px;padding:12px 14px;border-left:3px solid var(--amber);background:rgba(247,185,40,.07);color:var(--muted);font-size:12px}}
    @media(max-width:760px){{.shell{{width:min(100% - 20px,1180px);padding-top:12px}}header,.intro{{align-items:flex-start;flex-direction:column}}.summary{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}.card-wide{{grid-column:auto}}.market-state{{grid-template-columns:repeat(3,1fr)}}.market-state div:nth-child(3){{border-right:0}}}}
  </style>
</head>
<body><main class="shell">
  <header><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><span>Admin Operations</span></div><a class="back" href="/">← Dashboard</a></header>
  <section class="intro"><div><h1>System Operations</h1><p>Internal monitoring for market state, system health and data providers.</p></div><span class="updated" data-generated-at="{generated_at}">Snapshot {_text(generated_at)}</span></section>
  <section class="summary">
    <div class="summary-card"><span>Overall Health</span><strong class="state-{overall.lower()}">{_text(overall.title())}</strong></div>
    <div class="summary-card"><span>Snapshot</span><strong>{_text(freshness.title())}</strong></div>
    <div class="summary-card"><span>Provider APIs</span><strong>{_text(provider_overall.title())}</strong></div>
    <div class="summary-card"><span>Markets Available</span><strong>{_text(snapshot.get("available_coins", 0))}/{_text(snapshot.get("total_coins", len(resolved)))}</strong></div>
  </section>
  <section class="grid">
    <article class="card card-wide"><h2>Market State</h2><div class="market-state">
      <div><span>ALERT</span><strong>{counts["ALERT"]}</strong></div><div><span>WATCH</span><strong>{counts["WATCH"]}</strong></div><div><span>REVIEW</span><strong>{counts["REVIEW"]}</strong></div><div><span>REFERENCE</span><strong>{counts["REFERENCE"]}</strong></div><div><span>IGNORE</span><strong>{counts["IGNORE"]}</strong></div><div><span>UNAVAILABLE</span><strong>{counts["UNAVAILABLE"]}</strong></div>
    </div></article>
    <article class="card"><h2>System Health</h2><div class="health-list">
      <div class="health-row"><span>Decision Engine</span><b>{_text(overall)}</b></div><div class="health-row"><span>Snapshot</span><b>{_text(freshness)}</b></div><div class="health-row"><span>Scheduler</span><b class="state-{scheduler.lower()}">{scheduler}</b></div><div class="health-row"><span>Telegram</span><b>{_text(telegram)}</b></div>
    </div></article>
    <article class="card"><h2>Provider Operations</h2>{provider_content}</article>
  </section>
  <p class="policy">Internal operations console. Provider and scheduler status is diagnostic information and is not market evidence or trade guidance.</p>
</main>
<script>const item=document.querySelector("[data-generated-at]");const time=new Date(item.dataset.generatedAt);if(!Number.isNaN(time.getTime()))item.textContent="Snapshot "+new Intl.DateTimeFormat("en-MY",{{timeZone:"Asia/Kuala_Lumpur",day:"2-digit",month:"short",year:"numeric",hour:"numeric",minute:"2-digit",hour12:true}}).format(time)+" MYT";</script>
</body></html>"""
