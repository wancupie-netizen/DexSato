"""Founder-only Content Control Center presentation."""

from __future__ import annotations

import json
from html import escape


def _safe(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def render_content_login(*, configured: bool) -> str:
    notice = "" if configured else (
        '<div class="warning">Content Control Center is not configured. '
        'Set CONTENT_CONTROL_PASSWORD and CONTENT_CONTROL_SESSION_SECRET.</div>'
    )
    disabled = "" if configured else " disabled"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DexSato - Founder Access</title><link rel="icon" href="/static/branding/favicon.png">
<style>
:root{{--bg:#f7f9fc;--panel:#fff;--line:#dfe6ef;--text:#142033;--muted:#68788d;--cyan:#14c9c4;--blue:#286ff4;--red:#d94352}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);font-family:Inter,"Segoe UI",Arial,sans-serif}}.card{{width:min(430px,calc(100% - 32px));padding:28px;border:1px solid var(--line);border-radius:16px;background:var(--panel);box-shadow:0 18px 55px rgba(35,55,80,.08)}}img{{width:150px}}h1{{margin:24px 0 7px}}p{{color:var(--muted);line-height:1.55}}label{{display:block;margin:18px 0 7px;font-size:13px;font-weight:800}}input{{width:100%;padding:12px 13px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--text);font:inherit;outline:none}}input:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(40,111,244,.10)}}button{{width:100%;margin-top:13px;padding:12px;border:0;border-radius:9px;background:var(--blue);color:#fff;font:inherit;font-weight:850;cursor:pointer}}button:disabled{{opacity:.5;cursor:not-allowed}}#error{{min-height:22px;color:var(--red);font-size:14px}}.warning{{margin:14px 0;padding:12px;border:1px solid #f0c777;border-radius:8px;background:#fff9e9;color:#805d14;font-size:14px}}
</style></head><body><main class="card"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><h1>Founder Access</h1><p>Private access to the DexSato Content Control Center.</p>{notice}<form id="login"><label for="password">Password</label><input id="password" type="password" autocomplete="current-password" required{disabled}><button type="submit"{disabled}>Sign In</button><p id="error"></p></form></main>
<script>
document.getElementById('login').addEventListener('submit',async e=>{{e.preventDefault();const error=document.getElementById('error');error.textContent='';const r=await fetch('/content-control/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{password:document.getElementById('password').value}})}});if(r.ok){{location.href='/content-control';return;}}let msg='Access denied.';try{{const data=await r.json();msg=data.detail||msg;}}catch(_e){{}}error.textContent=msg;}});
</script></body></html>"""


def render_content_control(
    snapshot: dict[str, object],
    *,
    ai_enabled: bool,
    ai_model: str,
) -> str:
    coins = snapshot.get("coins")
    coins = [coin for coin in coins if isinstance(coin, dict)] if isinstance(coins, list) else []
    options: list[str] = []
    for coin in coins:
        token = str(coin.get("token") or "").strip().upper()
        if not token:
            continue
        decision = str(coin.get("decision") or "UNKNOWN").strip().upper()
        options.append(f'<option value="{_safe(token)}">{_safe(token)} - {_safe(decision)}</option>')

    market_json = json.dumps(coins, ensure_ascii=True, default=str).replace("</", "<\\/")
    generated = _safe(snapshot.get("generated_at") or "Not available")
    ai_label = (
        f"AI ready - {_safe(ai_model)}"
        if ai_enabled
        else "AI not configured - deterministic fallback active"
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DexSato - Content Control Center</title><link rel="icon" href="/static/branding/favicon.png">
<style>
:root{{--bg:#f7f9fc;--panel:#fff;--panel2:#f8fafc;--line:#dfe6ef;--line2:#edf1f6;--text:#142033;--muted:#68788d;--cyan:#14c9c4;--blue:#286ff4;--green:#169b62;--amber:#a86500;--red:#d94352;--shadow:0 10px 32px rgba(35,55,80,.06)}}
#message{{padding:9px 11px;border:1px solid transparent;border-radius:8px}}#message.ai-ok{{border-color:#bde8dc;background:#effbf7;color:var(--green)}}#message.ai-fallback{{border-color:#ecdab9;background:#fffaf1;color:var(--amber)}}#message.ai-error{{border-color:#f0ccd2;background:#fff6f7;color:var(--red)}}
*{{box-sizing:border-box}}html{{color-scheme:light}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,"Segoe UI",Arial,sans-serif;line-height:1.5}}button,select,textarea{{font:inherit}}.shell{{width:min(1380px,calc(100% - 32px));margin:0 auto;padding:22px 0 48px}}header{{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 0 18px;border-bottom:1px solid var(--line)}}header img{{width:156px}}.actions{{display:flex;gap:8px}}.btn,.link{{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--text);text-decoration:none;cursor:pointer}}.btn:hover,.link:hover{{border-color:#bfcbd9;background:#fafcff}}.primary{{border-color:var(--blue);background:var(--blue);color:#fff;font-weight:850}}.primary:hover{{background:#1760e9;border-color:#1760e9}}.intro{{margin:24px 0 18px}}.intro h1{{margin:0;font-size:31px;letter-spacing:-.025em}}.intro p{{margin:7px 0;color:var(--muted)}}.status{{display:inline-flex;padding:6px 10px;border:1px solid #bde8dc;border-radius:999px;background:#effbf7;color:var(--green);font-size:13px;font-weight:750}}.snapshot{{margin-top:10px;color:var(--muted);font-size:12px}}.grid{{display:grid;grid-template-columns:minmax(500px,.98fr) minmax(600px,1.35fr);gap:18px;align-items:start}}.card{{padding:20px;border:1px solid var(--line);border-radius:14px;background:var(--panel);box-shadow:var(--shadow)}}.card h2{{margin:0 0 15px;font-size:19px}}label{{display:block;margin:13px 0 7px;color:#42536a;font-size:13px;font-weight:800}}select{{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--text);outline:none}}select:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(40,111,244,.09)}}.settings-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.settings-grid .wide{{grid-column:1/-1}}.market-glance{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:2px}}.glance{{min-width:0;padding:11px 12px;border:1px solid var(--line);border-radius:9px;background:var(--panel2)}}.glance span{{display:block;color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.045em}}.glance strong{{display:block;margin-top:4px;font-size:14px;overflow-wrap:anywhere}}.tone-green{{border-color:#c9ebdc!important;background:#f3fbf7!important}}.tone-green strong{{color:var(--green)}}.tone-red{{border-color:#f0ccd2!important;background:#fff6f7!important}}.tone-red strong{{color:var(--red)}}.tone-amber{{border-color:#ecdab9!important;background:#fffaf1!important}}.tone-amber strong{{color:var(--amber)}}.tone-blue{{border-color:#d5e2fb!important;background:#f5f8ff!important}}.tone-blue strong{{color:var(--blue)}}.factor-wrap{{margin-top:20px;border-top:1px solid var(--line);padding-top:18px}}.factor-title{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}}.factor-title h3{{margin:0;font-size:16px}}.factor-title span{{color:var(--muted);font-size:12px}}.factor-sections{{display:grid;gap:9px}}details.factor-section{{border:1px solid var(--line);border-radius:10px;background:#fff}}details.factor-section>summary{{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:13px 14px;cursor:pointer;list-style:none;font-size:13px;font-weight:850}}details.factor-section>summary::-webkit-details-marker{{display:none}}details.factor-section>summary:after{{content:'+';color:var(--muted);font-size:16px}}details.factor-section[open]>summary:after{{content:'-'}}.factor-body{{padding:0 13px 13px}}.metric-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}.metric{{min-width:0;padding:9px 10px;border:1px solid var(--line2);border-radius:8px;background:var(--panel2)}}.metric span{{display:block;color:var(--muted);font-size:10px;font-weight:750;text-transform:uppercase;letter-spacing:.035em}}.metric strong{{display:block;margin-top:4px;font-size:13px;overflow-wrap:anywhere}}.text-block{{margin-top:8px;padding:10px;border:1px solid var(--line2);border-radius:8px;background:var(--panel2)}}.text-block b{{display:block;margin-bottom:4px;font-size:11px;text-transform:uppercase;color:#53657b}}.text-block p{{margin:0;color:#34455b;font-size:13px;line-height:1.55}}.rows{{display:grid;gap:6px;margin-top:8px}}.row{{padding:9px 10px;border:1px solid var(--line2);border-radius:8px;background:var(--panel2);font-size:12px}}.row strong{{display:block}}.row span{{display:block;margin-top:3px;color:var(--muted);line-height:1.45}}.empty{{color:var(--muted);font-size:12px}}textarea{{width:100%;min-height:350px;resize:vertical;padding:16px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--text);line-height:1.6;outline:none}}textarea:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(40,111,244,.09)}}.toolbar{{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin-top:11px}}.counter{{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums}}.counter.over{{color:var(--red);font-weight:850}}#message{{min-height:22px;margin:11px 0 0;color:var(--muted);font-size:13px}}.note{{margin-top:14px;padding:12px;border:1px solid #dbe7fb;border-radius:9px;background:#f4f8ff;color:#49617e;font-size:12px;line-height:1.55}}@media(max-width:1080px){{.grid{{grid-template-columns:1fr}}}}@media(max-width:620px){{header{{align-items:flex-start;flex-direction:column}}.actions{{width:100%;flex-wrap:wrap}}.settings-grid,.metric-grid,.market-glance{{grid-template-columns:1fr}}.settings-grid .wide{{grid-column:auto}}}}
</style></head><body><main class="shell"><header><img src="/static/branding/dexsato-logo.png" alt="DexSato"><div class="actions"><a class="link" href="/">Dashboard</a><button id="logout" class="btn">Sign Out</button></div></header><section class="intro"><h1>Content Control Center</h1><p>Founder-only writing workspace. DexSato facts stay authoritative; AI only rewrites them into publishable trader language.</p><span class="status">{ai_label}</span><div class="snapshot">Snapshot: {generated}</div></section><div class="grid"><section class="card"><h2>Draft Settings</h2><div class="settings-grid"><div class="wide"><label for="market">Market</label><select id="market">{''.join(options)}</select></div><div id="market-glance" class="market-glance wide"></div><div><label for="type">Content Type</label><select id="type"><option value="current_update">Current Market Read</option><option value="what_changed">What Changed</option><option value="trader_brief">Trader Brief</option><option value="technical_update">Technical Update</option><option value="risk_focus">Risk / Invalidation</option><option value="fundamental_context">Fundamental Context</option><option value="catalyst_update">Catalyst Update</option></select></div><div><label for="style">Writing Style</label><select id="style"><option value="trader">Trader - Natural</option><option value="professional">Professional</option><option value="educational">Educational</option><option value="concise">Concise</option></select></div><div class="wide"><label for="length">Length</label><select id="length"><option value="short">Short</option><option value="medium" selected>Medium</option><option value="full">Near 280 characters</option></select></div></div><button id="generate" class="btn primary" style="width:100%;margin-top:15px">Generate Draft</button><div class="factor-wrap"><div class="factor-title"><h3>DexSato Fact Inspector</h3><span>Full read-only market context</span></div><div id="factor-sections" class="factor-sections"></div></div></section><section class="card"><h2>X Draft</h2><textarea id="draft" maxlength="500" placeholder="Generate a draft, then edit it here before copying to X."></textarea><div class="toolbar"><button id="regenerate" class="btn">Regenerate</button><button id="copy" class="btn primary">Copy Post</button><span id="counter" class="counter">0 / 280</span></div><p id="message"></p><div class="note">The AI writing layer is not allowed to change DexSato decisions, technical bias, confirmation rules, invalidation rules, indicators or verified context. Always review the final draft before posting.</div></section></div></main>
<script>
const markets={market_json};
const market=document.getElementById('market');
const draft=document.getElementById('draft');
const counter=document.getElementById('counter');
const message=document.getElementById('message');
const factorSections=document.getElementById('factor-sections');
const marketGlance=document.getElementById('market-glance');

function selected(){{
  const token=(market.value||'').toUpperCase();
  return markets.find(x=>String(x.token||'').toUpperCase()===token)||markets[0]||{{}};
}}
function obj(v){{return v&&typeof v==='object'&&!Array.isArray(v)?v:{{}}}}
function arr(v){{return Array.isArray(v)?v:[]}}
function display(v){{
  if(v===null||v===undefined||v==='')return 'Not available';
  if(typeof v==='boolean')return v?'Yes':'No';
  if(typeof v==='number')return Number.isInteger(v)?String(v):String(Math.round(v*10000)/10000);
  return String(v).replaceAll('_',' ');
}}
function money(v){{
  const n=Number(v); if(!Number.isFinite(n))return display(v);
  if(Math.abs(n)>=1e9)return '$'+(n/1e9).toFixed(2)+'B';
  if(Math.abs(n)>=1e6)return '$'+(n/1e6).toFixed(2)+'M';
  if(Math.abs(n)>=1e3)return '$'+(n/1e3).toFixed(2)+'K';
  if(Math.abs(n)>=1)return '$'+n.toLocaleString(undefined,{{maximumFractionDigits:4}});
  return '$'+n.toLocaleString(undefined,{{maximumFractionDigits:8}});
}}
function pct(v){{const n=Number(v);return Number.isFinite(n)?((n>0?'+':'')+n.toFixed(2)+'%'):display(v)}}
function tone(value){{
  const v=String(value??'').trim().toUpperCase().replaceAll('_',' ');
  if(['ALERT','BEARISH','TRIGGERED','LOW'].includes(v))return 'tone-red';
  if(['HIGH','BULLISH','MET','CLEAR','AVAILABLE'].includes(v))return 'tone-green';
  if(['WATCH','PENDING','MIXED','MEDIUM'].includes(v))return 'tone-amber';
  if(['REVIEW','REFERENCE','NEUTRAL'].includes(v))return 'tone-blue';
  return '';
}}
function metric(label,value){{return `<div class="metric ${{tone(value)}}"><span>${{esc(label)}}</span><strong>${{esc(display(value))}}</strong></div>`}}
function glance(label,value){{return `<div class="glance ${{tone(value)}}"><span>${{esc(label)}}</span><strong>${{esc(display(value))}}</strong></div>`}}
function textBlock(label,value){{if(value===null||value===undefined||value==='')return '';return `<div class="text-block"><b>${{esc(label)}}</b><p>${{esc(display(value))}}</p></div>`}}
function row(title,subtitle=''){{return `<div class="row"><strong>${{esc(display(title))}}</strong>${{subtitle?`<span>${{esc(display(subtitle))}}</span>`:''}}</div>`}}
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function section(title,html,open=false){{if(!html||!html.trim())html='<div class="empty">No data available in the current snapshot.</div>';return `<details class="factor-section" ${{open?'open':''}}><summary>${{esc(title)}}</summary><div class="factor-body">${{html}}</div></details>`}}
function rules(title,values){{const rows=arr(values);if(!rows.length)return section(title,'');return section(title,`<div class="rows">${{rows.map(x=>row(`${{display(x.label)}} - ${{display(x.status)}}`,`Actual: ${{display(x.actual)}} | Rule: ${{display(x.requirement)}}`)).join('')}}</div>`)}}

function renderFactors(){{
  const c=selected();
  const evidence=obj(c.technical_evidence), metrics=obj(evidence.metrics), outlook=obj(evidence.outlook);
  const rsi=obj(metrics.rsi_14), ema50=obj(metrics.ema_50), ema200=obj(metrics.ema_200), rel=obj(metrics.relative_volume_20), structure=obj(metrics.market_structure);
  const brief=obj(c.trader_decision_brief), change=obj(c.change_since_previous), fundamental=obj(c.fundamental_context), catalysts=obj(c.market_catalysts);
  const reasons=(String(c.decision||'').toUpperCase()==='REFERENCE'?arr(c.reference_evidence):arr(c.reasons));
  marketGlance.innerHTML =
    glance('Decision',c.decision)+
    glance('Confidence',c.confidence)+
    glance('4H Bias',outlook.bias)+
    glance('RSI 14',rsi.value)+
    glance('Relative Volume',rel.value==null?'Not available':display(rel.value)+'x')+
    glance('24H Change',pct(c.price_change_24h));
  let html='';
  html+=section('Core Market',`<div class="metric-grid">${{metric('Market',c.token)}}${{metric('Pair',c.pair)}}${{metric('Decision',c.decision)}}${{metric('Confidence',c.confidence)}}${{metric('Price',money(c.price))}}${{metric('24H Change',pct(c.price_change_24h))}}${{metric('24H Volume',money(c.volume_24h))}}${{metric('Liquidity',money(c.liquidity))}}${{metric('Market Cap',money(c.market_cap))}}${{metric('Chain',c.chain)}}${{metric('Source',c.source)}}${{metric('Seen Before',c.seen_before)}} </div>${{textBlock('Summary',c.summary)}}`,true);
  html+=section('Decision Evidence',reasons.length?`<div class="rows">${{reasons.map(x=>row(x)).join('')}}</div>`:'');
  html+=section('Risk Note',textBlock('Current Risk',c.risk_note));
  html+=section('Technical Evidence',`<div class="metric-grid">${{metric('Status',c.technical_evidence_status)}}${{metric('Timeframe',evidence.timeframe)}}${{metric('4H Bias',outlook.bias)}}${{metric('RSI 14',rsi.value)}}${{metric('RSI Previous',rsi.previous)}}${{metric('RSI State',rsi.state)}}${{metric('RSI Direction',rsi.direction)}}${{metric('EMA50',ema50.value)}}${{metric('EMA50 Distance',pct(ema50.price_distance_pct))}}${{metric('EMA200',ema200.value)}}${{metric('EMA200 Distance',pct(ema200.price_distance_pct))}}${{metric('Relative Volume',rel.value==null?null:display(rel.value)+'x')}}${{metric('Market Structure',structure.state)}}${{metric('Candle Closed',evidence.candle_closed_at)}}${{metric('Technical Source',evidence.source)}}</div>${{textBlock('Technical Outlook',outlook.summary)}}`);
  html+=rules('Confirmation Rules',outlook.confirmation);
  html+=rules('Invalidation Rules',outlook.invalidation);
  const pending=arr(brief.pending_confirmation), binv=arr(brief.invalidation), context=arr(brief.context_notes);
  html+=section('Trader Decision Brief',`<div class="metric-grid">${{metric('Status',brief.status)}}${{metric('State',brief.state)}}</div>${{textBlock('Headline',brief.headline)}}${{textBlock('Brief Summary',brief.summary)}}${{textBlock('What This Means Now',brief.next_action)}}${{pending.length?`<div class="text-block"><b>Still Needed</b><div class="rows">${{pending.map(x=>row(`${{display(x.label)}} - ${{display(x.status)}}`,`Actual: ${{display(x.actual)}} | Rule: ${{display(x.requirement)}}`)).join('')}}</div></div>`:''}}${{binv.length?`<div class="text-block"><b>View Changes If</b><div class="rows">${{binv.map(x=>row(`${{display(x.label)}} - ${{display(x.status)}}`,`Actual: ${{display(x.actual)}} | Rule: ${{display(x.requirement)}}`)).join('')}}</div></div>`:''}}${{context.length?`<div class="text-block"><b>Context, Not Cause</b><div class="rows">${{context.map(x=>row(x.type,x.text)).join('')}}</div></div>`:''}}`);
  const changes=arr(change.changes);
  html+=section('Change Since Previous Scan',`<div class="metric-grid">${{metric('Status',change.status)}}</div>${{textBlock('Headline',change.headline)}}${{changes.length?`<div class="rows">${{changes.map(x=>row(x.label,`${{display(x.previous)}} -> ${{display(x.current)}}`)).join('')}}</div>`:''}}`);
  const history=arr(c.recent_scan_history).slice(-6).reverse();
  html+=section('Recent Scan Trail',history.length?`<div class="rows">${{history.map(x=>row(`${{display(x.recorded_at)}} - ${{display(x.decision)}}`,`4H bias: ${{display(x.technical_bias)}} | RSI: ${{display(x.rsi_14)}} | Rel vol: ${{display(x.relative_volume)}}x`)).join('')}}</div>`:'');
  const indicators=arr(fundamental.indicators);
  html+=section('Verified Fundamental Context',`<div class="metric-grid">${{metric('Status',c.fundamental_context_status)}}${{metric('Source',fundamental.source)}}</div>${{textBlock('Headline',fundamental.headline)}}${{textBlock('Summary',fundamental.summary)}}${{indicators.length?`<div class="rows">${{indicators.map(x=>row(`${{display(x.label)}} - ${{display(x.direction)}}`,`Latest: ${{display(x.actual_display)}} | Previous: ${{display(x.previous_display)}} | Period: ${{display(x.reference_period)}}`)).join('')}}</div>`:''}}`);
  const catalystRows=arr(catalysts.catalysts);
  html+=section('Verified Market Catalysts',`<div class="metric-grid">${{metric('Status',c.market_catalysts_status)}}</div>${{textBlock('Headline',catalysts.headline)}}${{textBlock('Summary',catalysts.summary)}}${{catalystRows.length?`<div class="rows">${{catalystRows.slice(0,6).map(x=>row(`${{display(x.category)}} - ${{display(x.title)}}`,`${{display(x.source)}} | ${{display(x.published_at)}}`)).join('')}}</div>`:''}}`);
  const venues=arr(c.trading_venues);
  html+=section('Top Trading Venues',venues.length?`<div class="rows">${{venues.slice(0,3).map((x,i)=>row(`#${{i+1}} ${{display(x.name)}}`,`${{display(x.type)}} | ${{display(x.pair)}} | Volume: ${{money(x.volume_24h)}} | Liquidity: ${{money(x.liquidity)}}`)).join('')}}</div>`:'');
  factorSections.innerHTML=html;
}}
function count(){{const n=draft.value.length;counter.textContent=`${{n}} / 280`;counter.classList.toggle('over',n>280)}}
function showDiagnostic(data){{
  const status=String(data.status||'UNKNOWN_STATUS');
  const diagnostic=String(data.diagnostic||'').trim();
  const model=String(data.model||'').trim();
  message.className='';
  if(status==='AI_GENERATED'||status==='AI_REWRITTEN'){{
    message.classList.add('ai-ok');
    message.textContent=`${{status}}${{model?' - '+model:''}} - review before posting`;
  }}else if(status==='AI_ERROR_FALLBACK'){{
    message.classList.add('ai-error');
    message.textContent=`${{status}}${{diagnostic?' - '+diagnostic:''}}`;
  }}else{{
    message.classList.add('ai-fallback');
    message.textContent=`${{status}}${{diagnostic?' - '+diagnostic:''}}`;
  }}
}}
async function generate(){{message.className='';message.textContent='Generating from latest DexSato facts...';const b=document.getElementById('generate');b.disabled=true;try{{const r=await fetch('/content-control/generate',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{token:market.value,content_type:document.getElementById('type').value,style:document.getElementById('style').value,length:document.getElementById('length').value}})}});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Unable to generate draft.');draft.value=data.draft||'';count();showDiagnostic(data);}}catch(e){{message.className='ai-error';message.textContent=e.message||'Unable to generate draft.';}}finally{{b.disabled=false}}}}
market.addEventListener('change',renderFactors);draft.addEventListener('input',count);document.getElementById('generate').addEventListener('click',generate);document.getElementById('regenerate').addEventListener('click',generate);document.getElementById('copy').addEventListener('click',async()=>{{if(!draft.value.trim())return;await navigator.clipboard.writeText(draft.value);message.textContent='Copied. Review once more before posting to X.';}});document.getElementById('logout').addEventListener('click',async()=>{{await fetch('/content-control/logout',{{method:'POST'}});location.href='/content-control';}});renderFactors();count();
</script></body></html>"""
