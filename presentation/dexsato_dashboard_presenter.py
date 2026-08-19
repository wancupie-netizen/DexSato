"""High-fidelity DexSato Founder V1 decision dashboard."""

from __future__ import annotations

from collections import Counter
from html import escape
from urllib.parse import urlparse


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


def format_percentage(value: object) -> str:
    """Format a percentage while preserving unavailable data honestly."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Not available"
    sign = "+" if amount > 0 else ""
    return f"{sign}{amount:,.2f}%"


def _safe_market_url(value: object) -> str | None:
    """Allow only public HTTPS DexScreener links from provider data."""
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or parsed.hostname not in {
        "dexscreener.com",
        "www.dexscreener.com",
    }:
        return None
    return escape(candidate, quote=True)


def _safe_bls_url(value: object) -> str:
    """Allow links only to official BLS HTTPS hosts."""
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or parsed.hostname not in {
        "www.bls.gov", "bls.gov", "data.bls.gov",
    }:
        return "https://www.bls.gov/data/"
    return escape(candidate, quote=True)


def _format_network(value: object) -> str:
    """Format known network identifiers without damaging brand casing."""
    normalized = str(value or "").strip().lower()
    labels = {
        "bsc": "BSC",
        "ethereum": "Ethereum",
        "solana": "Solana",
        "sui": "Sui",
        "spot-metals": "Spot Metals",
    }
    return labels.get(normalized, normalized.replace("-", " ").title()) or "Not available"


def _metric_number(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "Not available"


def _render_rule_conditions(
    conditions: object,
    *,
    group: str,
) -> str:
    """Render auditable rule states with actual values and thresholds."""
    if not isinstance(conditions, list):
        return '<p class="rule-empty">No rule conditions available.</p>'
    icons = {
        "MET": "✓",
        "PENDING": "○",
        "CLEAR": "✓",
        "TRIGGERED": "!",
        "NOT_APPLICABLE": "—",
    }
    rows: list[str] = []
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        status = _status(condition.get("status"), "UNKNOWN")
        rows.append(
            f'<div class="rule-row rule-{_text(status.lower())}">'
            f'<span class="rule-icon" aria-hidden="true">{icons.get(status, "?")}</span>'
            '<div class="rule-copy">'
            f'<div><strong>{_text(condition.get("label"))}</strong>'
            f'<b>{_text(status.replace("_", " ").title())}</b></div>'
            f'<p>Actual: <strong>{_text(condition.get("actual"))}</strong></p>'
            f'<small>Rule: {_text(condition.get("requirement"))}</small>'
            "</div></div>"
        )
    return "".join(rows) or '<p class="rule-empty">No rule conditions available.</p>'


def _render_technical_outlook(evidence: dict[str, object]) -> str:
    outlook = evidence.get("outlook", {})
    if not isinstance(outlook, dict) or not outlook:
        return (
            '<div class="outlook-empty">Confirmation and invalidation '
            "rules will be available after the next snapshot.</div>"
        )
    bias = _status(outlook.get("bias"), "MIXED")
    bias_label = bias.replace("_", " ").title()
    summary = _text(outlook.get("summary"), "Technical outlook is unavailable.")
    confirmation = _render_rule_conditions(
        outlook.get("confirmation"), group="confirmation"
    )
    invalidation = _render_rule_conditions(
        outlook.get("invalidation"), group="invalidation"
    )
    return f"""
        <div class="technical-outlook">
          <div class="outlook-heading"><div><span>Evidence assessment</span>
            <h4>Current technical bias</h4></div>
            <strong class="bias-badge bias-{_text(bias.lower())}">{_text(bias_label)}</strong>
          </div>
          <p class="outlook-summary">{summary}</p>
          <div class="rule-groups">
            <section class="rule-group confirmation-rules"><h5>Confirmation</h5>
              <p>Conditions required to strengthen this technical thesis.</p>{confirmation}</section>
            <section class="rule-group invalidation-rules"><h5>Invalidation</h5>
              <p>Conditions that weaken or cancel the active thesis.</p>{invalidation}</section>
          </div>
          <p class="outlook-policy">Technical context only · does not override the DexSato decision.</p>
        </div>
    """


def _render_technical_evidence(coin: dict[str, object]) -> str:
    """Render deterministic indicator values from exact-pool OHLCV."""
    status = _status(coin.get("technical_evidence_status"), "NOT_REQUESTED")
    evidence = coin.get("technical_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    if status != "AVAILABLE":
        messages = {
            "INSUFFICIENT_DATA": (
                "At least 200 closed 4H candles are required before "
                "RSI and long-term EMA evidence can be reported."
            ),
            "UNAVAILABLE": (
                "Technical candle data is temporarily unavailable. "
                "The existing DexSato decision has not been changed."
            ),
            "NOT_REQUESTED": "Technical evidence has not been collected for this snapshot.",
        }
        return (
            '<div class="technical-empty"><strong>Technical Evidence · 4H</strong>'
            f'<p>{_text(messages.get(status, messages["UNAVAILABLE"]))}</p></div>'
        )

    metrics = evidence.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    rsi = metrics.get("rsi_14", {})
    ema_50 = metrics.get("ema_50", {})
    ema_200 = metrics.get("ema_200", {})
    volume = metrics.get("relative_volume_20", {})
    structure = metrics.get("market_structure", {})
    rsi = rsi if isinstance(rsi, dict) else {}
    ema_50 = ema_50 if isinstance(ema_50, dict) else {}
    ema_200 = ema_200 if isinstance(ema_200, dict) else {}
    volume = volume if isinstance(volume, dict) else {}
    structure = structure if isinstance(structure, dict) else {}

    rsi_value = _metric_number(rsi.get("value"))
    rsi_previous = _metric_number(rsi.get("previous"))
    rsi_state = str(rsi.get("state", "UNKNOWN")).replace("_", " ").title()
    rsi_direction = str(rsi.get("direction", "UNKNOWN")).replace("_", " ").lower()
    ema50_distance = format_percentage(ema_50.get("price_distance_pct"))
    ema200_distance = format_percentage(ema_200.get("price_distance_pct"))
    volume_ratio = _metric_number(volume.get("value"))
    structure_state = str(structure.get("state", "UNKNOWN")).replace("_", " ").title()
    timeframe = _text(evidence.get("timeframe"), "4H")
    source = _text(evidence.get("source"), "GeckoTerminal")
    candle_closed_at = _text(evidence.get("candle_closed_at"), "Not available")

    return f"""
        <div class="technical-heading">
          <div><h4>Technical Evidence · {timeframe}</h4>
          <p>Calculated from closed candles for this exact DEX pool.</p></div>
          <span>Source: {source}</span>
        </div>
        <div class="technical-grid">
          <div class="technical-metric"><span>RSI(14)</span><strong>{_text(rsi_value)}</strong>
            <p>{_text(rsi_state)} · {_text(rsi_direction)}, previously {_text(rsi_previous)}</p></div>
          <div class="technical-metric"><span>EMA50 distance</span><strong>{_text(ema50_distance)}</strong>
            <p>Positive means price closed above the 4H EMA50.</p></div>
          <div class="technical-metric"><span>EMA200 distance</span><strong>{_text(ema200_distance)}</strong>
            <p>Shows price position against the longer 4H trend.</p></div>
          <div class="technical-metric"><span>Relative volume</span><strong>{_text(volume_ratio)}×</strong>
            <p>Latest closed candle versus the previous 20-candle average.</p></div>
          <div class="technical-metric technical-structure"><span>Market structure</span>
            <strong>{_text(structure_state)}</strong><p>Compared with the previous closed 4H candle.</p></div>
        </div>
        {_render_technical_outlook(evidence)}
        <p class="technical-freshness" data-technical-at="{candle_closed_at}">
          Latest closed candle <strong class="technical-updated">{candle_closed_at}</strong>
        </p>
    """


def _render_fundamental_context(coin: dict[str, object]) -> str:
    """Render official macro readings without claiming price causality."""
    status = _status(coin.get("fundamental_context_status"), "NOT_REQUESTED")
    context = coin.get("fundamental_context", {})
    if not isinstance(context, dict) or status != "AVAILABLE":
        message = (
            "Official macro data is temporarily unavailable. No fundamental "
            "cause has been assigned to this market move."
            if status == "UNAVAILABLE"
            else "Verified fundamental context will be collected in the next snapshot."
        )
        return (
            '<div class="fundamental-empty"><strong>Verified Fundamental Context</strong>'
            f"<p>{_text(message)}</p></div>"
        )
    rows = []
    indicators = context.get("indicators", [])
    if isinstance(indicators, list):
        for indicator in indicators:
            if not isinstance(indicator, dict):
                continue
            rows.append(
                '<div class="fundamental-row">'
                f'<div><strong>{_text(indicator.get("label"))}</strong>'
                f'<span>{_text(indicator.get("reference_period"))} · '
                f'{_text(indicator.get("direction"), "MIXED").title()}</span></div>'
                f'<div><small>Latest</small><strong>{_text(indicator.get("actual_display"))}</strong></div>'
                f'<div><small>Previous</small><strong>{_text(indicator.get("previous_display"))}</strong></div>'
                f'<a href="{_safe_bls_url(indicator.get("source_url"))}" target="_blank" '
                'rel="noopener noreferrer">BLS series</a></div>'
            )
    return f"""
        <div class="fundamental-context">
          <div class="fundamental-heading"><div><span>Primary official source</span>
            <h4>Verified Fundamental Context</h4></div>
            <strong>Contextual · causality not established</strong></div>
          <h5>{_text(context.get("headline"))}</h5>
          <p class="fundamental-summary">{_text(context.get("summary"))}</p>
          <div class="fundamental-list">{"".join(rows)}</div>
          <p class="fundamental-source">Source: <a href="{_safe_bls_url(context.get("source_url"))}"
            target="_blank" rel="noopener noreferrer">{_text(context.get("source"))}</a> ·
            Official data may be revised after publication.</p>
        </div>
    """


def _render_market_detail_content(coin: dict[str, object]) -> str:
    """Render reusable market-detail content from one stored snapshot."""
    token = _status(coin.get("token"))
    pair = _text(coin.get("pair") or token)
    price = _text(format_usd(coin.get("price")))
    change = _text(format_percentage(coin.get("price_change_24h")))
    volume = _text(format_compact_usd(coin.get("volume_24h")))
    liquidity = _text(format_compact_usd(coin.get("liquidity")))
    market_cap = _text(format_compact_usd(coin.get("market_cap")))
    decision = _text(_status(coin.get("decision")))
    confidence = _text(_status(coin.get("confidence")))
    source = _text(coin.get("source"), "Not available")
    chain = _text(_format_network(coin.get("chain")))
    market_cap_label = (
        "On-chain Market Cap"
        if _status(coin.get("asset_class"), "CRYPTO") == "CRYPTO"
        else "Market Cap"
    )
    scanned_at = _text(coin.get("scanned_at"), "Not available")
    risk_note = _text(
        coin.get("risk_note") or "Current risk information is unavailable."
    )
    reasons = coin.get("reasons", [])
    if decision == "REFERENCE":
        reasons = coin.get("reference_evidence", [])
    if not isinstance(reasons, list):
        reasons = []
    evidence = "".join(
        f"<li>{_reason_label(reason)}</li>" for reason in reasons[:3]
    ) or "<li>No supporting evidence recorded.</li>"

    venues = coin.get("trading_venues", [])
    if not isinstance(venues, list):
        venues = []
    venue_rows: list[str] = []
    for index, venue in enumerate(venues[:3], start=1):
        if not isinstance(venue, dict):
            continue
        url = _safe_market_url(venue.get("url"))
        name = _text(venue.get("name"), "Unknown DEX")
        name_html = (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
            f"{name}</a>"
            if url
            else name
        )
        venue_rows.append(
            '<div class="venue-row">'
            f'<span class="venue-rank">{index}</span>'
            f'<div><strong>{name_html}</strong>'
            f'<small>{_text(venue.get("type"), "DEX")} · '
            f'{_text(venue.get("pair"), pair)}</small></div>'
            f'<div><strong>{_text(format_compact_usd(venue.get("volume_24h")))}</strong>'
            '<small>24h volume</small></div>'
            f'<div><strong>{_text(format_compact_usd(venue.get("liquidity")))}</strong>'
            '<small>Liquidity</small></div>'
            "</div>"
        )
    venue_status = _status(coin.get("trading_venues_status"), "NOT_REQUESTED")
    venue_html = "".join(venue_rows)
    if not venue_html:
        messages = {
            "UNAVAILABLE": "Trading venue data is temporarily unavailable.",
            "NO_MATCH": "No verified matching DEX venue was returned.",
            "NOT_APPLICABLE": "Trading venue ranking does not apply to this market.",
        }
        venue_html = (
            '<p class="detail-empty">'
            f'{_text(messages.get(venue_status, "Trading venue data will be collected on the next scan."))}'
            "</p>"
        )

    return f"""
      <div class="drawer-heading">
        <div class="drawer-logo">{render_coin_logo(token)}</div>
        <div><small>Market Detail</small><h2>{pair}</h2>
          <p>{price} <span class="market-change">{change} · 24h</span></p></div>
      </div>
      <section class="detail-section">
        <h3>Market Snapshot</h3>
        <div class="detail-metrics">
          <div><span>Price</span><strong>{price}</strong></div>
          <div><span>24h Change</span><strong>{change}</strong></div>
          <div><span>24h Volume</span><strong>{volume}</strong></div>
          <div><span>Liquidity</span><strong>{liquidity}</strong></div>
          <div><span>{market_cap_label}</span><strong>{market_cap}</strong></div>
          <div><span>Network</span><strong>{chain}</strong></div>
        </div>
      </section>
      <section class="detail-section">
        <h3>DexSato Decision</h3>
        <div class="drawer-decision"><span>{decision}</span><strong>Confidence {confidence}</strong></div>
        <div class="engine-evidence"><strong>Engine signals</strong><ul>{evidence}</ul></div>
        {_render_technical_evidence(coin)}
        {_render_fundamental_context(coin)}
        <p class="drawer-risk"><strong>Risk note</strong>{risk_note}</p>
      </section>
      <section class="detail-section">
        <div class="detail-title-row"><h3>Top Trading Venues</h3><span>DEX · ranked by 24h volume</span></div>
        <div class="venue-list">{venue_html}</div>
        <p class="data-note">Venue ranking is informational and is not an endorsement.</p>
      </section>
      <section class="detail-source">
        <span>Market source <strong>{source}</strong></span>
        <span data-scanned-at="{scanned_at}">Updated <strong class="detail-updated">{scanned_at}</strong></span>
      </section>
    """


def render_market_detail(coin: dict[str, object]) -> str:
    """Render one hidden detail template for backward compatibility."""
    return (
        '<template class="market-detail-template">'
        f"{_render_market_detail_content(coin)}"
        "</template>"
    )


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
          <a class="market-title-button" href="/market/{_text(token.lower())}">
            {_text(pair)}<span aria-hidden="true">›</span>
          </a>
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


def render_market_detail_page(
    coin: dict[str, object],
    *,
    generated_at: object = None,
) -> str:
    """Render a dedicated market workspace from the latest snapshot."""
    if not isinstance(coin, dict):
        raise ValueError("Market detail requires a coin dictionary.")

    token = _status(coin.get("token"))
    pair = _text(coin.get("pair") or token)
    content = _render_market_detail_content(coin)
    summary = _text(
        coin.get("summary") or f"Latest stored DexSato snapshot for {pair}."
    )
    generated = _text(generated_at, "Not available")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{pair} · DexSato Market Detail</title>
  <link rel="icon" type="image/png" href="/static/branding/favicon.png">
  <script>
    try{{if(localStorage.getItem("dexsato-theme")==="plain")document.documentElement.dataset.theme="plain";}}catch(error){{}}
  </script>
  <style>
    :root{{--bg:#06111f;--panel:#0b1a2c;--panel2:#0f2238;--line:#1d3852;--text:#f5f8ff;--muted:#91a8c1;--cyan:#23d9d2;--blue:#5394ff;--amber:#f7b928}}
    *{{box-sizing:border-box}} html{{color-scheme:dark}} body{{margin:0;min-height:100vh;background:radial-gradient(circle at 50% -20%,#102746 0,transparent 35%),var(--bg);color:var(--text);font-family:"Segoe UI Variable Text","Segoe UI Variable","Segoe UI",Inter,system-ui,-apple-system,sans-serif;font-size:16px;line-height:1.6;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}}
    button{{font:inherit}} .market-page{{width:min(1180px,calc(100% - 36px));margin:0 auto;padding:24px 0 42px}}
    .market-page-header{{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--line)}}
    .page-brand{{display:flex;align-items:center;gap:15px}} .page-brand img{{width:150px;border-radius:9px}} .page-brand span{{color:var(--muted);font-size:14px;font-weight:600;letter-spacing:.01em}}
    .page-actions{{display:flex;align-items:center;gap:9px}} .page-action{{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:9px 14px;border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--text);font-size:14px;font-weight:700;text-decoration:none;cursor:pointer}}
    .page-action:hover{{border-color:var(--blue)}} .theme-switcher{{display:flex;gap:3px;padding:3px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}}
    .theme-option{{min-height:34px;padding:7px 11px;border:0;border-radius:7px;background:transparent;color:var(--muted);font-size:13px;font-weight:700;cursor:pointer}} .theme-option.active{{background:#1b1d4e;color:#fff}}
    .page-intro{{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:20px}} .page-intro h1{{margin:0;font-size:32px;line-height:1.2;letter-spacing:-.025em;font-weight:750}} .page-intro p{{max-width:700px;margin:8px 0 0;color:var(--muted);font-size:16px;line-height:1.55}} .snapshot-time{{color:var(--muted);font-size:13px;font-weight:500;line-height:1.5;text-align:right}}
    #market-page-content{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(350px,.75fr);gap:18px;align-items:start}}
    .drawer-heading{{grid-column:1/-1;display:flex;align-items:center;gap:16px;padding:20px;border:1px solid var(--line);border-radius:13px;background:var(--panel)}}
    .drawer-heading small{{color:var(--muted);font-size:13px;font-weight:750;text-transform:uppercase;letter-spacing:.09em}} .drawer-heading h2{{margin:3px 0 0;font-size:31px;line-height:1.2;letter-spacing:-.02em}} .drawer-heading p{{margin:5px 0 0;color:var(--muted);font-size:15px}}
    .drawer-logo{{display:grid;place-items:center;flex:0 0 72px;width:72px;height:72px;border:1px solid var(--line);border-radius:50%;background:#10253c;overflow:hidden}} .drawer-logo img{{width:100%;height:100%;object-fit:cover}} .coin-fallback,.commodity-fallback{{font-weight:900}} .commodity-fallback{{color:#f7c948;font-size:25px}} .market-change{{color:var(--cyan);font-size:13px;font-weight:700}}
    .detail-section{{padding:24px;border:1px solid var(--line);border-radius:13px;background:var(--panel)}} .detail-section>h3,.detail-title-row h3{{margin:0 0 17px;font-size:19px;font-weight:750;line-height:1.35;letter-spacing:-.012em}}
    .detail-section:nth-of-type(1),.detail-section:nth-of-type(2){{grid-column:1}} .detail-section:nth-of-type(3){{grid-column:2;grid-row:2/span 2}}
    .detail-metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}} .detail-metrics div{{min-height:76px;padding:15px;border-radius:9px;background:var(--panel2)}} .detail-metrics span,.venue-row small{{display:block;color:var(--muted);font-size:12.5px;font-weight:500;line-height:1.45}} .detail-metrics strong{{display:block;margin-top:6px;font-size:16.5px;font-weight:750;line-height:1.35;overflow-wrap:anywhere}}
    ul{{margin:0;padding-left:21px;color:var(--text);font-size:15.5px;line-height:1.6}} li{{margin:8px 0}} .drawer-decision{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:14px}} .drawer-decision span{{padding:5px 10px;border:1px solid var(--blue);border-radius:6px;color:var(--blue);font-size:13px;font-weight:800}} .drawer-decision strong{{font-size:13.5px;color:var(--amber)}}
    .engine-evidence{{margin-bottom:20px}} .engine-evidence>strong{{display:block;margin-bottom:8px;color:var(--muted);font-size:12.5px;font-weight:750;text-transform:uppercase;letter-spacing:.055em}}
    .technical-heading{{display:flex;align-items:start;justify-content:space-between;gap:16px;margin-top:20px;padding-top:20px;border-top:1px solid var(--line)}} .technical-heading h4{{margin:0;font-size:17px;font-weight:750;letter-spacing:-.008em}} .technical-heading p{{max-width:470px;margin:5px 0 0;color:var(--muted);font-size:13.5px;font-weight:500;line-height:1.5}} .technical-heading span{{margin:3px 0 0;color:var(--muted);font-size:12.5px;font-weight:600;white-space:nowrap}}
    .technical-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:15px}} .technical-metric{{min-height:112px;padding:17px;border:1px solid transparent;border-radius:10px;background:var(--panel2)}} .technical-metric span{{display:block;color:var(--muted);font-size:13.5px;font-weight:650;line-height:1.4}} .technical-metric strong{{display:block;margin-top:6px;font-size:20px;font-weight:780;line-height:1.3;letter-spacing:-.012em}} .technical-metric p{{margin:8px 0 0;color:var(--muted);font-size:14px;font-weight:500;line-height:1.55}} .technical-structure{{grid-column:1/-1;min-height:100px}} .technical-empty{{margin-top:20px;padding:17px;border:1px dashed var(--line);border-radius:9px}} .technical-empty strong{{font-size:16px}} .technical-empty p,.technical-freshness{{margin:7px 0 0;color:var(--muted);font-size:13.25px;font-weight:550;line-height:1.55}} .technical-freshness{{margin-top:12px;text-align:right}}
    .technical-outlook{{margin-top:20px;padding:20px;border:1px solid var(--line);border-radius:11px;background:rgba(83,148,255,.035)}} .outlook-heading{{display:flex;align-items:center;justify-content:space-between;gap:16px}} .outlook-heading span{{display:block;color:var(--muted);font-size:12.5px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}} .outlook-heading h4{{margin:4px 0 0;font-size:18.5px;font-weight:780}} .bias-badge{{padding:7px 11px;border:1px solid var(--line);border-radius:7px;font-size:13px;font-weight:850}} .bias-bullish_developing{{border-color:var(--cyan);color:var(--cyan)}} .bias-bearish_developing{{border-color:#ff6b78;color:#ff8792}} .bias-mixed{{color:var(--amber)}} .outlook-summary{{margin:14px 0 0;color:var(--text);font-size:15px;font-weight:550;line-height:1.65}}
    .fundamental-context,.fundamental-empty{{margin-top:22px;padding-top:21px;border-top:1px solid var(--line)}} .fundamental-heading{{display:flex;align-items:center;justify-content:space-between;gap:15px}} .fundamental-heading span{{color:var(--muted);font-size:12.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}} .fundamental-heading h4{{margin:5px 0 0;font-size:18.5px;font-weight:800}} .fundamental-heading>strong{{max-width:230px;padding:7px 10px;border:1px solid var(--line);border-radius:7px;color:var(--amber);font-size:12px;text-align:center}} .fundamental-context>h5{{margin:17px 0 0;font-size:17px}} .fundamental-summary{{margin:7px 0 0;font-size:14.5px;font-weight:520;line-height:1.65}} .fundamental-list{{display:grid;gap:9px;margin-top:15px}} .fundamental-row{{display:grid;grid-template-columns:minmax(190px,1fr) 90px 90px 70px;align-items:center;gap:12px;padding:13px 14px;border:1px solid var(--line);border-radius:9px;background:var(--panel2)}} .fundamental-row span,.fundamental-row small{{display:block;margin-top:3px;color:var(--muted);font-size:12px}} .fundamental-row>div>strong{{font-size:14px}} .fundamental-row a,.fundamental-source a{{color:var(--cyan);font-weight:700;text-decoration:none}} .fundamental-row>a{{font-size:12px;text-align:right}} .fundamental-source,.fundamental-empty p{{margin:11px 0 0;color:var(--muted);font-size:12.5px;line-height:1.55}}
    .rule-groups{{display:grid;grid-template-columns:1fr;gap:14px;margin-top:18px}} .rule-group{{padding:17px;border-radius:10px;background:var(--panel2)}} .rule-group h5{{margin:0;font-size:16.5px;font-weight:780}} .rule-group>p{{margin:5px 0 13px;color:var(--muted);font-size:13.5px;font-weight:500;line-height:1.5}} .rule-row{{display:grid;grid-template-columns:28px minmax(0,1fr);gap:11px;padding:13px 0;border-top:1px solid var(--line)}} .rule-icon{{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:rgba(145,168,193,.12);color:var(--muted);font-size:13px;font-weight:900}} .rule-copy>div{{display:flex;align-items:start;justify-content:space-between;gap:12px}} .rule-copy>div>strong{{font-size:14px;font-weight:750;line-height:1.45}} .rule-copy b{{color:var(--muted);font-size:11.5px;font-weight:800;line-height:1.5;text-transform:uppercase;white-space:nowrap}} .rule-copy p{{margin:6px 0 0;color:var(--muted);font-size:13px;line-height:1.45}} .rule-copy p strong{{color:var(--text);font-size:13px}} .rule-copy small{{display:block;margin-top:4px;color:var(--muted);font-size:12.5px;font-weight:500;line-height:1.5}} .rule-met .rule-icon,.rule-clear .rule-icon{{background:rgba(35,217,210,.12);color:var(--cyan)}} .rule-triggered .rule-icon{{background:rgba(255,83,100,.13);color:#ff6b78}} .rule-triggered .rule-copy b{{color:#ff8792}} .rule-pending .rule-icon{{background:rgba(247,185,40,.12);color:var(--amber)}} .outlook-policy{{margin:14px 0 0;color:var(--muted);font-size:12.5px;font-weight:550;text-align:right}} .outlook-empty{{margin-top:17px;padding:15px;border:1px dashed var(--line);border-radius:8px;color:var(--muted);font-size:13.5px}}
    .drawer-risk{{margin:18px 0 0;padding:16px;border-radius:8px;background:rgba(247,185,40,.08);color:#e9d39c;font-size:14.5px;font-weight:500;line-height:1.65}} .drawer-risk strong{{display:block;margin-bottom:5px;color:var(--amber);text-transform:uppercase;font-size:12.5px;font-weight:800;letter-spacing:.04em}}
    .detail-title-row{{display:flex;align-items:start;justify-content:space-between;gap:12px}} .detail-title-row span{{color:var(--muted);font-size:12px;line-height:1.4;text-align:right}} .venue-list{{display:grid;gap:9px}} .venue-row{{display:grid;grid-template-columns:28px minmax(110px,1fr) 96px 96px;align-items:center;gap:10px;min-height:62px;padding:12px;border:1px solid var(--line);border-radius:9px;background:var(--panel2)}}
    .venue-rank{{display:grid;place-items:center;width:24px;height:24px;border-radius:6px;background:#182b43;color:var(--cyan);font-size:12px;font-weight:800}} .venue-row strong{{display:block;font-size:13.5px;line-height:1.4;overflow-wrap:anywhere}} .venue-row a{{color:var(--cyan);font-weight:750;text-decoration:none}} .venue-row a:hover{{text-decoration:underline}} .detail-empty,.data-note{{margin:0;color:var(--muted);font-size:13px;line-height:1.5}} .data-note{{margin-top:13px}}
    .detail-source{{grid-column:1/-1;display:flex;justify-content:space-between;gap:15px;padding:18px 3px;color:var(--muted);font-size:13px;font-weight:500;line-height:1.5}} .detail-source strong{{color:var(--text);font-weight:750}} .copy-status{{min-height:20px;margin:10px 0 0;color:var(--cyan);font-size:13px;text-align:right}}
    html[data-theme="plain"]{{color-scheme:light;--bg:#f7f8fa;--panel:#fff;--panel2:#f3f5f7;--line:#d9dfe6;--text:#111c30;--muted:#53657a;--cyan:#087783;--blue:#245fb5;--amber:#985800}}
    html[data-theme="plain"] body{{background:#f7f8fa}} html[data-theme="plain"] .theme-option.active{{background:#172033;color:#fff}} html[data-theme="plain"] .drawer-logo{{background:#f2f5f8}} html[data-theme="plain"] .drawer-risk{{background:#fff7e3;color:#674b13}} html[data-theme="plain"] .venue-rank{{background:#e9f7f7;color:#087f8c}} html[data-theme="plain"] .technical-metric{{border-color:#e4e8ed}} html[data-theme="plain"] .technical-outlook{{background:#f9fbfd}} html[data-theme="plain"] .rule-met .rule-icon,html[data-theme="plain"] .rule-clear .rule-icon{{background:#e6f7f5}} html[data-theme="plain"] .rule-pending .rule-icon{{background:#fff4d9}}
    @media(max-width:860px){{.market-page-header,.page-intro{{align-items:flex-start;flex-direction:column}}.page-actions{{flex-wrap:wrap}}#market-page-content{{grid-template-columns:1fr}}.detail-section:nth-of-type(1),.detail-section:nth-of-type(2),.detail-section:nth-of-type(3){{grid-column:1;grid-row:auto}}.detail-metrics{{grid-template-columns:repeat(2,1fr)}}.rule-groups{{grid-template-columns:1fr}}.venue-row{{grid-template-columns:26px 1fr 88px}}.venue-row>div:last-child{{display:none}}.detail-source{{flex-direction:column}}.snapshot-time{{text-align:left}}}}
    @media(max-width:560px){{.market-page{{width:min(100% - 24px,1180px)}}.detail-section{{padding:19px}}.technical-heading,.outlook-heading,.fundamental-heading{{align-items:flex-start;flex-direction:column}}.technical-heading span{{white-space:normal}}.technical-grid{{grid-template-columns:1fr}}.technical-structure{{grid-column:auto}}.technical-outlook{{padding:16px}}.rule-group{{padding:15px}}.rule-copy>div{{flex-direction:column;gap:2px}}.fundamental-row{{grid-template-columns:1fr 1fr}}.fundamental-row>div:first-child{{grid-column:1/-1}}.fundamental-row>a{{text-align:left}}}}
  </style>
</head>
<body>
  <main class="market-page">
    <header class="market-page-header">
      <div class="page-brand"><img src="/static/branding/dexsato-logo.png" alt="DexSato"><span>Market Workspace</span></div>
      <div class="page-actions">
        <div class="theme-switcher" role="group" aria-label="Page theme"><button class="theme-option active" type="button" data-theme-option="current">Current</button><button class="theme-option" type="button" data-theme-option="plain">Plain White</button></div>
        <button id="copy-summary" class="page-action" type="button">Copy Summary</button>
        <a class="page-action" href="/">← Dashboard</a>
      </div>
    </header>
    <section class="page-intro"><div><h1>{pair} Market Workspace</h1><p>{summary}</p></div><span class="snapshot-time" data-snapshot-at="{generated}">Snapshot <strong>{generated}</strong></span></section>
    <div id="market-page-content">{content}</div>
    <p id="copy-status" class="copy-status" role="status"></p>
  </main>
  <script>
    const themeOptions=[...document.querySelectorAll("[data-theme-option]")];
    function applyTheme(theme){{const resolved=theme==="plain"?"plain":"current";if(resolved==="plain")document.documentElement.dataset.theme="plain";else delete document.documentElement.dataset.theme;themeOptions.forEach(button=>button.classList.toggle("active",button.dataset.themeOption===resolved));try{{localStorage.setItem("dexsato-theme",resolved);}}catch(error){{}}}}
    let savedTheme="current";try{{savedTheme=localStorage.getItem("dexsato-theme")||"current";}}catch(error){{}}applyTheme(savedTheme);themeOptions.forEach(button=>button.addEventListener("click",()=>applyTheme(button.dataset.themeOption)));
    function formatMYT(raw){{const time=new Date(raw);if(Number.isNaN(time.getTime()))return"Not available";return new Intl.DateTimeFormat("en-MY",{{timeZone:"Asia/Kuala_Lumpur",day:"2-digit",month:"short",year:"numeric",hour:"numeric",minute:"2-digit",hour12:true}}).format(time)+" MYT";}}
    document.querySelectorAll("[data-scanned-at]").forEach(item=>{{const strong=item.querySelector(".detail-updated");if(strong)strong.textContent=formatMYT(item.dataset.scannedAt);}});document.querySelectorAll("[data-technical-at]").forEach(item=>{{const strong=item.querySelector(".technical-updated");if(strong)strong.textContent=formatMYT(item.dataset.technicalAt);}});const snapshot=document.querySelector("[data-snapshot-at] strong");if(snapshot)snapshot.textContent=formatMYT(snapshot.parentElement.dataset.snapshotAt);
    document.getElementById("copy-summary").addEventListener("click",async()=>{{const status=document.getElementById("copy-status");try{{await navigator.clipboard.writeText(document.getElementById("market-page-content").innerText.trim());status.textContent="Market summary copied.";}}catch(error){{status.textContent="Copy is unavailable in this browser.";}}}});
  </script>
</body>
</html>"""


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
    .market-title-button{{display:flex;align-items:center;gap:7px;margin:0 0 7px;padding:0;border:0;background:transparent;color:var(--text);font-size:24px;font-weight:800;cursor:pointer;text-align:left;text-decoration:none}}
    .market-title-button span{{color:var(--blue);font-size:28px;line-height:1;transition:transform .16s ease}}
    .market-title-button:hover span{{transform:translateX(3px)}} .market-title-button:focus-visible{{outline:2px solid var(--cyan);outline-offset:4px;border-radius:3px}}
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
