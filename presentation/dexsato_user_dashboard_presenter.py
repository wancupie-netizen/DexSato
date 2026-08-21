"""User-facing DexSato market decision dashboard."""

from __future__ import annotations

from collections import Counter
from html import escape

from presentation.dexsato_dashboard_presenter import render_decision_card


def _text(value: object, fallback: str = "Not available") -> str:
    text = str(value).strip() if value is not None else ""
    return escape(text or fallback)


def _status(value: object, fallback: str = "UNKNOWN") -> str:
    text = str(value).strip().upper() if value is not None else ""
    return text or fallback


def render_user_dashboard(
    snapshot: dict[str, object],
    *,
    system_status: dict[str, object] | None = None,
) -> str:
    """Render the product experience without internal operations telemetry."""
    if not isinstance(snapshot, dict):
        raise ValueError("User snapshot must be a dictionary.")
    coins = snapshot.get("coins")
    if not isinstance(coins, list):
        raise ValueError("User snapshot coin data must be a list.")

    markets = [coin for coin in coins if isinstance(coin, dict)]
    counts = Counter(
        _status(coin.get("decision") if coin.get("available") is True else "UNAVAILABLE")
        for coin in markets
    )
    attention = counts["ALERT"] + counts["WATCH"]
    status = system_status if isinstance(system_status, dict) else {}
    snapshot_health = status.get("snapshot")
    if not isinstance(snapshot_health, dict):
        snapshot_health = {}
    freshness = _status(snapshot_health.get("status"), "UNKNOWN")
    generated_at = _text(snapshot.get("generated_at"))
    cards = "".join(render_decision_card(coin) for coin in markets)
    available = _text(snapshot.get("available_coins", sum(coin.get("available") is True for coin in markets)))
    total = _text(snapshot.get("total_coins", len(markets)))

    attention_message = (
        f"{attention} market{'s' if attention != 1 else ''} currently need a closer review."
        if attention
        else "No market currently requires immediate attention."
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DexSato · Market Evidence</title>
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
  <script>try{{if(localStorage.getItem("dexsato-theme")==="plain")document.documentElement.dataset.theme="plain";}}catch(error){{}}</script>
  <style>
    :root{{--bg:#06111f;--panel:#0b1a2c;--panel2:#0f2238;--line:#1d3852;--text:#f5f8ff;--muted:#91a8c1;--green:#39df9a;--amber:#f7b928;--red:#ff5364;--blue:#5394ff;--cyan:#23d9d2}}
    *{{box-sizing:border-box}} html{{color-scheme:dark;scroll-behavior:smooth}} body{{margin:0;background:radial-gradient(circle at 50% -15%,#102746 0,transparent 34%),var(--bg);color:var(--text);font-family:"Segoe UI Variable Text","Segoe UI Variable","Segoe UI",Inter,system-ui,sans-serif;font-size:16px;line-height:1.55;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}}
    button,input{{font:inherit}} .shell{{width:min(1380px,calc(100% - 40px));margin:0 auto;padding:20px 0 38px}}
    .topbar{{display:flex;align-items:center;justify-content:space-between;gap:20px;padding-bottom:18px;border-bottom:1px solid var(--line)}} .brand{{display:flex;align-items:center;gap:15px}} .brand img{{width:155px;padding:6px;border-radius:9px;background:#071525}} .brand span{{color:var(--muted);font-size:13px;font-weight:700}}
    .top-actions,.theme-switcher{{display:flex;align-items:center;gap:8px}} .theme-switcher{{gap:3px;padding:3px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}} .theme-option{{display:grid;place-items:center;width:34px;height:34px;padding:0;border:0;border-radius:7px;background:transparent;color:var(--muted);font-size:17px;line-height:1;cursor:pointer}} .theme-option.active{{background:#1b1d4e;color:#fff}} .theme-option:focus-visible{{outline:2px solid var(--blue);outline-offset:2px}} .learn-link{{padding:9px 12px;border:1px solid var(--line);border-radius:9px;color:var(--text);font-size:13px;font-weight:750;text-decoration:none}}
    .hero{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(330px,.8fr);gap:20px;align-items:stretch;margin:28px 0 18px}} .hero-copy,.attention-card{{border:1px solid var(--line);border-radius:14px;background:linear-gradient(145deg,var(--panel2),var(--panel))}} .hero-copy{{padding:28px}} .eyebrow{{display:block;color:var(--cyan);font-size:11px;font-weight:850;letter-spacing:.09em;text-transform:uppercase}} h1{{max-width:760px;margin:9px 0 0;font-size:38px;line-height:1.15;letter-spacing:-.035em}} .hero-copy p{{max-width:720px;margin:12px 0 0;color:var(--muted);font-size:16px}}
    .attention-card{{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:24px;border-left:4px solid var(--amber)}} .attention-card span{{color:var(--muted);font-size:12px;font-weight:750;text-transform:uppercase}} .attention-card strong{{display:block;margin-top:5px;font-size:21px;line-height:1.35}} .attention-card button{{flex:0 0 auto;padding:10px 13px;border:1px solid var(--amber);border-radius:8px;background:transparent;color:var(--amber);font-size:12px;font-weight:800;cursor:pointer}}
    .pulse{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:25px}} .pulse-card{{padding:16px;border:1px solid var(--line);border-radius:11px;background:var(--panel)}} .pulse-card span{{display:block;color:var(--muted);font-size:12px}} .pulse-card strong{{display:block;margin-top:5px;font-size:22px}} .pulse-card small{{display:block;margin-top:3px;color:var(--muted)}}
    .market-head{{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:12px}} .market-head h2{{margin:0;font-size:24px}} .market-head p{{margin:5px 0 0;color:var(--muted)}} .search{{width:min(320px,40vw);padding:10px 13px;border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--text);outline:0}} .search:focus{{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(35,217,210,.1)}}
    .filters{{display:flex;gap:8px;margin-bottom:14px;overflow-x:auto}} .filters button{{padding:8px 13px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--muted);font-size:13px;font-weight:750;cursor:pointer;white-space:nowrap}} .filters button.active{{border-color:var(--blue);background:rgba(83,148,255,.12);color:var(--text)}}
    .decision-list{{display:grid;gap:12px}} .decision-card{{display:grid;grid-template-columns:250px 1fr 1.25fr 145px;align-items:center;min-height:160px;border:1px solid var(--line);border-left:3px solid var(--blue);border-radius:12px;background:var(--panel);overflow:hidden}} .tone-alert{{border-left-color:var(--red)}} .tone-watch{{border-left-color:var(--amber)}} .tone-reference{{border-left-color:var(--cyan)}} .tone-unavailable,.tone-ignore{{border-left-color:#718198}}
    .coin-column,.evidence-column,.summary-column{{min-width:0;padding:18px}} .coin-column{{display:flex;align-items:center;gap:15px}} .evidence-column,.summary-column{{border-left:1px solid var(--line)}} .coin-logo{{display:grid;place-items:center;flex:0 0 68px;width:68px;height:68px;border:1px solid var(--line);border-radius:50%;background:#10253c;overflow:hidden}} .coin-logo img{{width:100%;height:100%;object-fit:cover}} .coin-fallback,.commodity-fallback{{font-weight:900}} .commodity-fallback{{color:#f7c948;font-size:24px}}
    .market-title-button{{display:flex;align-items:center;gap:5px;margin:0 0 5px;color:var(--text);font-size:22px;font-weight:850;text-decoration:none}} .market-title-button span{{color:var(--blue);font-size:26px}} .coin-column small{{display:block;color:var(--muted);font-size:12px}} .decision-pill{{display:inline-flex;margin-top:6px;padding:4px 8px;border:1px solid currentColor;border-radius:6px;color:var(--blue);font-size:11px;font-weight:850}} .tone-alert .decision-pill{{color:var(--red)}} .tone-watch .decision-pill{{color:var(--amber)}} .tone-reference .decision-pill{{color:var(--cyan)}} .confidence{{margin:8px 0 0;color:var(--muted);font-size:11px}} .confidence strong{{display:block;color:var(--amber);font-size:12px}}
    .evidence-column h4,.teaser-title{{margin:0 0 9px;font-size:13px}} .evidence-snapshot{{display:grid;gap:7px}} .evidence-row{{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding-bottom:7px;border-bottom:1px solid var(--line)}} .evidence-row:last-child{{border:0}} .evidence-row span,.evidence-row small{{color:var(--muted);font-size:11px}} .evidence-row strong{{font-size:14px;text-align:right}} .evidence-row small{{grid-column:1/-1}} .evidence-fallback{{padding:4px 0;color:var(--muted);font-size:12px}}
    .teaser-context{{display:block;margin-bottom:4px;color:var(--cyan);font-size:10px;font-weight:850;letter-spacing:.06em;text-transform:uppercase}} .teaser-headline{{display:block;font-size:15px;line-height:1.4}} .summary-column p{{margin:5px 0 0;color:var(--muted);font-size:12px;line-height:1.5}} .next-confirmation{{display:grid;gap:2px;margin-top:9px;padding:8px 10px;border-left:2px solid var(--amber);background:rgba(247,185,40,.07)}} .next-confirmation small{{color:var(--amber);font-size:9px;font-weight:850;text-transform:uppercase}} .next-confirmation strong{{font-size:12px}} .next-confirmation span{{color:var(--muted);font-size:10px;overflow-wrap:anywhere}}
    .decision-button{{display:flex;align-items:center;justify-content:center;gap:6px;margin-right:16px;padding:10px;border:1px solid var(--blue);border-radius:8px;color:#7fb0ff;font-size:11px;font-weight:800;line-height:1.35;text-align:center;text-decoration:none}} .decision-detail{{display:none}} [hidden]{{display:none!important}}
    .empty-results{{display:none;padding:30px;border:1px dashed var(--line);border-radius:11px;color:var(--muted);text-align:center}} .empty-results.visible{{display:block}}
    .learn{{margin-top:28px;padding:24px;border:1px solid var(--line);border-radius:13px;background:var(--panel)}} .learn h2{{margin:0;font-size:21px}} .learn>p{{margin:6px 0 0;color:var(--muted)}} .learn-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}} .learn-grid div{{padding:16px;border-radius:9px;background:var(--panel2)}} .learn-grid strong{{display:block}} .learn-grid span{{display:block;margin-top:5px;color:var(--muted);font-size:13px}} footer{{display:flex;justify-content:space-between;gap:15px;margin-top:18px;color:var(--muted);font-size:12px}}
    html[data-theme="plain"]{{color-scheme:light;--bg:#f7f8fa;--panel:#fff;--panel2:#f1f4f7;--line:#dce2e8;--text:#152033;--muted:#607086;--green:#14804a;--amber:#9a5b00;--red:#c83242;--blue:#2869c7;--cyan:#087f8c}} html[data-theme="plain"] body{{background:#f7f8fa}} html[data-theme="plain"] .theme-option.active{{background:#172033;color:#fff}} html[data-theme="plain"] .coin-logo{{background:#f2f5f8}} html[data-theme="plain"] .decision-card,.pulse-card,.learn,.search,.filters button{{box-shadow:0 1px 3px rgba(15,23,42,.04)}}
    @media(max-width:1080px){{.decision-card{{grid-template-columns:220px 1fr 1.15fr}}.decision-button{{grid-column:1/-1;margin:0 16px 14px}}}}
    @media(max-width:780px){{
      html,body{{width:100%;max-width:100%;overflow-x:hidden}} .shell{{width:min(100% - 24px,1380px);padding-top:12px}}
      .topbar,.market-head{{align-items:flex-start;flex-direction:column}} .top-actions{{width:100%;justify-content:space-between}}
      .hero{{grid-template-columns:1fr}} h1{{font-size:31px}} .pulse{{grid-template-columns:repeat(2,minmax(0,1fr))}} .pulse-card{{min-width:0}}
      #markets{{scroll-margin-top:12px}} .search{{width:100%}} .filters{{max-width:100%;padding-bottom:3px;scrollbar-width:none}} .filters::-webkit-scrollbar{{display:none}}
      .decision-list,.decision-card{{width:100%;min-width:0;max-width:100%}} .decision-card{{grid-template-columns:minmax(0,1fr);contain:inline-size}}
      .coin-column{{display:grid;grid-template-columns:64px minmax(0,1fr);gap:15px;min-height:126px;padding:17px}}
      .coin-logo{{width:64px;height:64px;min-width:0;flex-basis:auto}} .coin-column>div:last-child{{min-width:0}}
      .market-title-button{{font-size:21px;line-height:1.25;overflow-wrap:anywhere}} .coin-column small{{font-size:12.5px;line-height:1.45}}
      .evidence-column,.summary-column{{min-width:0;padding:18px 17px;border-top:1px solid var(--line);border-left:0}}
      .evidence-column h4,.teaser-title{{font-size:14px}} .evidence-row{{gap:3px 10px;padding:9px 0}} .evidence-row span,.evidence-row small{{font-size:12px;line-height:1.5}} .evidence-row strong{{font-size:15px}}
      .teaser-context{{font-size:10.5px}} .teaser-headline{{font-size:16px;line-height:1.45}} .summary-column p{{font-size:13px;line-height:1.6}}
      .next-confirmation{{padding:11px 12px}} .next-confirmation strong{{font-size:13px}} .next-confirmation span{{font-size:11.5px;line-height:1.5}}
      .decision-button{{grid-column:auto;width:calc(100% - 34px);min-height:46px;margin:0 17px 17px;padding:11px 14px;font-size:12.5px}}
      .learn-grid{{grid-template-columns:1fr}} footer{{flex-direction:column}}
    }}
    @media(max-width:520px){{
      .filters{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;overflow:visible}} .filters button{{width:100%;min-height:42px;padding:8px 9px;white-space:normal}}
      .filters button:last-child{{grid-column:1/-1}} .market-head p{{font-size:14px;line-height:1.6}}
    }}
    @media(max-width:430px){{
      .shell{{width:calc(100% - 20px)}} .brand span,.learn-link{{display:none}} .brand img{{width:135px}} .topbar{{flex-direction:row;align-items:center}} .top-actions{{width:auto;margin-left:auto;justify-content:flex-end}}
      .hero-copy{{padding:22px}} .hero-copy p{{font-size:15px;line-height:1.65}} .attention-card{{align-items:flex-start;flex-direction:column}}
      .pulse{{grid-template-columns:1fr 1fr;gap:9px}} .pulse-card{{padding:14px}} .pulse-card strong{{font-size:20px}}
      .coin-column{{grid-template-columns:58px minmax(0,1fr);gap:13px;min-height:116px;padding:16px}} .coin-logo{{width:58px;height:58px}}
      .market-title-button{{font-size:20px}} .evidence-column,.summary-column{{padding:17px 16px}}
    }}
  </style>
</head>
<body><main class="shell">
  <header class="topbar"><div class="brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><span>Market Evidence</span></div><div class="top-actions"><a class="learn-link" href="#how-to-read">How to read DexSato</a><div class="theme-switcher" role="group" aria-label="Dashboard theme"><button class="theme-option active" type="button" data-theme-option="current" aria-label="Use current dark theme" title="Current dark theme" aria-pressed="true">🌙</button><button class="theme-option" type="button" data-theme-option="plain" aria-label="Use plain white theme" title="Plain white theme" aria-pressed="false">☀️</button></div></div></header>
  <section class="hero"><div class="hero-copy"><span class="eyebrow">Evidence-led market decisions</span><h1>See what changed, what supports it, and what must happen next.</h1><p>DexSato turns technical evidence and verified context into a structured market review—without pretending uncertainty is a trade signal.</p></div><div class="attention-card"><div><span>Needs attention</span><strong>{_text(attention_message)}</strong></div><button id="show-attention" type="button">Review markets</button></div></section>
  <section class="pulse" aria-label="Market pulse"><div class="pulse-card"><span>Markets covered</span><strong>{available}/{total}</strong><small>Latest universe</small></div><div class="pulse-card"><span>Alerts</span><strong>{counts["ALERT"]}</strong><small>Immediate review</small></div><div class="pulse-card"><span>Under review</span><strong>{counts["REVIEW"]}</strong><small>Evidence developing</small></div><div class="pulse-card"><span>Data status</span><strong>{_text(freshness.title())}</strong><small id="scan-age" data-generated-at="{generated_at}">Updated recently</small></div></section>
  <section id="markets"><div class="market-head"><div><h2>Market Decisions</h2><p>Start with the evidence snapshot, then open the full conditions only when relevant.</p></div><input id="market-search" class="search" type="search" placeholder="Search BTC, ETH, SOL..." aria-label="Search markets"></div>
    <div class="filters" role="group" aria-label="Filter market decisions"><button class="active" data-filter="">All markets</button><button data-filter="attention">Needs attention</button><button data-filter="alert">Alerts</button><button data-filter="review">Review</button><button data-filter="reference">Reference</button></div>
    <div id="decision-list" class="decision-list">{cards}</div><p id="empty-results" class="empty-results">No markets match this view.</p>
  </section>
  <section id="how-to-read" class="learn"><h2>How to read DexSato</h2><p>Use the dashboard as a review process, not as an instruction to enter a trade.</p><div class="learn-grid"><div><strong>1. Read the current evidence</strong><span>Check 4H bias, RSI, trend structure and relative volume.</span></div><div><strong>2. Check what changed</strong><span>A decision change matters more when the underlying evidence also changed.</span></div><div><strong>3. Wait for confirmation</strong><span>Open the market workspace to see pending conditions and invalidation.</span></div></div></section>
  <footer><span>Evidence synthesis only · not financial advice.</span><span>Snapshot <strong data-footer-at="{generated_at}">{generated_at}</strong></span></footer>
</main><script>
  const themeOptions=[...document.querySelectorAll("[data-theme-option]")];function applyTheme(theme){{const value=theme==="plain"?"plain":"current";if(value==="plain")document.documentElement.dataset.theme="plain";else delete document.documentElement.dataset.theme;themeOptions.forEach(button=>{{const active=button.dataset.themeOption===value;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));}});try{{localStorage.setItem("dexsato-theme",value);}}catch(error){{}}}}let saved="current";try{{saved=localStorage.getItem("dexsato-theme")||"current";}}catch(error){{}}applyTheme(saved);themeOptions.forEach(button=>button.addEventListener("click",()=>applyTheme(button.dataset.themeOption)));
  const cards=[...document.querySelectorAll(".decision-card")],filters=[...document.querySelectorAll("[data-filter]")],search=document.getElementById("market-search"),empty=document.getElementById("empty-results");let selected="";function matches(card){{return !selected||(selected==="attention"?["alert","watch"].includes(card.dataset.decision):card.dataset.decision===selected);}}function applyFilters(){{const query=search.value.trim().toLowerCase();let visible=0;cards.forEach(card=>{{card.hidden=!(matches(card)&&(!query||card.dataset.token.includes(query)));if(!card.hidden)visible+=1;}});empty.classList.toggle("visible",visible===0);}}filters.forEach(button=>button.addEventListener("click",()=>{{filters.forEach(item=>item.classList.remove("active"));button.classList.add("active");selected=button.dataset.filter;applyFilters();}}));search.addEventListener("input",applyFilters);document.getElementById("show-attention").addEventListener("click",()=>{{const button=document.querySelector('[data-filter="attention"]');button.click();document.getElementById("markets").scrollIntoView({{behavior:"smooth",block:"start"}});}});
  function formatMYT(raw){{const date=new Date(raw);if(Number.isNaN(date.getTime()))return"Not available";return new Intl.DateTimeFormat("en-MY",{{timeZone:"Asia/Kuala_Lumpur",day:"2-digit",month:"short",year:"numeric",hour:"numeric",minute:"2-digit",hour12:true}}).format(date)+" MYT";}}const footer=document.querySelector("[data-footer-at]");footer.textContent=formatMYT(footer.dataset.footerAt);const age=document.getElementById("scan-age"),time=new Date(age.dataset.generatedAt),minutes=Math.max(0,Math.floor((Date.now()-time.getTime())/60000));age.textContent=Number.isNaN(minutes)?"Update unavailable":minutes<60?`Updated ${{minutes}} min ago`:`Updated ${{Math.floor(minutes/60)}} hr ago`;
</script></body></html>"""
