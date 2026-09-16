"""Presentation adapter for the separate Trending market-feed workspace."""

from __future__ import annotations

from html import escape
from typing import Any

from presentation.dexsato_solana_discovery_token_presenter import (
    render_solana_discovery_token_page,
)


def _remove_section(html: str, marker: str) -> str:
    """Remove one complete section, including nested section elements."""
    start = html.find(marker)
    if start < 0:
        return html

    cursor = start
    depth = 0

    while True:
        next_open = html.find("<section", cursor)
        next_close = html.find("</section>", cursor)

        if next_close < 0:
            return html

        if next_open >= 0 and next_open < next_close:
            depth += 1
            cursor = next_open + len("<section")
            continue

        depth -= 1
        cursor = next_close + len("</section>")

        if depth == 0:
            return html[:start] + html[cursor:]


def _source_context(detail: dict[str, Any]) -> str:
    rank = detail.get("trending_rank")
    rank_text = f"#{rank}" if isinstance(rank, int) and rank > 0 else "—"
    dex_id = escape(str(detail.get("dex_id") or "Unknown"))
    liquidity = detail.get("liquidity_usd")
    try:
        liquidity_text = f"${float(liquidity):,.0f}"
    except (TypeError, ValueError):
        liquidity_text = "Unavailable"

    return (
        '<section class="card market-feed-context-v02c">'
        '<h3>Trending Context</h3>'
        '<div class="metrics">'
        '<div class="metric"><span>Source</span>'
        '<b class="value" style="font-size:13px">Jupiter · 1H</b></div>'
        '<div class="metric"><span>Trending rank</span>'
        f'<b class="value">{escape(rank_text)}</b></div>'
        '<div class="metric"><span>Exact SOL pool</span>'
        f'<b class="value" style="font-size:13px">{dex_id}</b></div>'
        '<div class="metric"><span>Pool liquidity</span>'
        f'<b class="value">{escape(liquidity_text)}</b></div>'
        '</div>'
        '</section>'
    )


def _top_traded_source_context(detail: dict[str, Any]) -> str:
    rank = detail.get("top_traded_rank")
    rank_text = f"#{rank}" if isinstance(rank, int) and rank > 0 else "—"
    dex_id = escape(str(detail.get("dex_id") or "Unknown"))
    liquidity = detail.get("liquidity_usd")
    try:
        liquidity_text = f"${float(liquidity):,.0f}"
    except (TypeError, ValueError):
        liquidity_text = "Unavailable"

    return (
        '<section class="card market-feed-context-v02c">'
        '<h3>Top Traded Context</h3>'
        '<div class="metrics">'
        '<div class="metric"><span>Source</span>'
        '<b class="value" style="font-size:13px">Jupiter · 24H</b></div>'
        '<div class="metric"><span>Top Traded rank</span>'
        f'<b class="value">{escape(rank_text)}</b></div>'
        '<div class="metric"><span>Exact SOL pool</span>'
        f'<b class="value" style="font-size:13px">{dex_id}</b></div>'
        '<div class="metric"><span>Pool liquidity</span>'
        f'<b class="value">{escape(liquidity_text)}</b></div>'
        '</div>'
        '</section>'
    )


def _organic_flow_source_context(detail: dict[str, Any]) -> str:
    rank = detail.get("organic_flow_rank")
    rank_text = f"#{rank}" if isinstance(rank, int) and rank > 0 else "—"
    organic_score = detail.get("organic_score")
    try:
        organic_score_text = f"{float(organic_score):.2f}"
    except (TypeError, ValueError):
        organic_score_text = "Unavailable"
    liquidity = detail.get("liquidity_usd")
    try:
        liquidity_text = f"${float(liquidity):,.0f}"
    except (TypeError, ValueError):
        liquidity_text = "Unavailable"

    return (
        '<section class="card market-feed-context-v02c">'
        '<h3>Organic Flow Context</h3>'
        '<div class="metrics">'
        '<div class="metric"><span>Source</span>'
        '<b class="value" style="font-size:13px">Jupiter Organic Score · 1H</b></div>'
        '<div class="metric"><span>Organic rank</span>'
        f'<b class="value">{escape(rank_text)}</b></div>'
        '<div class="metric"><span>Organic score</span>'
        f'<b class="value">{escape(organic_score_text)}</b></div>'
        '<div class="metric"><span>Pool liquidity</span>'
        f'<b class="value">{escape(liquidity_text)}</b></div>'
        '</div>'
        '</section>'
    )


def render_organic_flow_token_page(
    detail: dict[str, Any],
    *,
    feed: dict[str, Any],
) -> str:
    """Reuse the stable Token Workspace shell with Organic Flow semantics."""
    html = render_solana_discovery_token_page(detail, feed=feed)
    token_address = escape(
        str(detail.get("token_address") or ""),
        quote=True,
    )

    html = html.replace(
        f"/api/discovery/solana/{token_address}/candles",
        f"/api/market/organic-flow/{token_address}/candles",
    )
    html = html.replace(
        f"/api/discovery/solana/{token_address}/transactions",
        f"/api/market/organic-flow/{token_address}/transactions",
    )
    html = html.replace(
        'href="/discovery/solana/',
        'href="/market/organic-flow/',
    )

    html = html.replace(
        " · Solana Discovery</title>",
        " · Organic Flow Workspace</title>",
        1,
    )
    html = html.replace(
        '<span class="eyebrow">Qualified exact-token workspace</span>',
        '<span class="eyebrow">Organic Flow market workspace · Jupiter 1H</span>',
        1,
    )
    html = html.replace(
        "Review observed market activity, exact-pool identity and disclosed risk before taking any action.",
        "Review current Organic Flow context and exact-pool market evidence. "
        "Organic Flow inclusion is separate from DexSato Discovery qualification.",
        1,
    )

    # Discovery qualification semantics do not belong to market-feed workspaces.
    html = _remove_section(
        html,
        '<section class="qualification qualification-vp0d3',
    )
    html = _remove_section(
        html,
        '<section class="discovery-engine-v12',
    )

    # Bind the inherited production Jupiter trade UI to the separate
    # Organic Flow execution route contract.
    html = html.replace(
        'data-jupiter-sandbox data-token-address=',
        f'data-jupiter-sandbox data-api-base="/api/market/organic-flow/{token_address}" data-token-address=',
        1,
    )

    context = _organic_flow_source_context(detail)
    html = html.replace(
        '<section class="card market-snapshot-v26">',
        context + '<section class="card market-snapshot-v26">',
        1,
    )

    html = html.replace(
        "<h2>Token List</h2>",
        "<h2>Organic Flow Tokens</h2>",
        1,
    )
    html = html.replace(
        '<span class="token-list-chain-v07a">SOLANA</span>',
        '<span class="token-list-chain-v07a">JUPITER · ORGANIC 1H</span>',
        1,
    )
    html = html.replace(
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Token list views">',
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Organic Flow market feed" hidden>',
        1,
    )

    return html


def render_top_traded_token_page(
    detail: dict[str, Any],
    *,
    feed: dict[str, Any],
) -> str:
    """Reuse the Token Workspace shell with Top Traded-only semantics."""
    html = render_solana_discovery_token_page(detail, feed=feed)
    token_address = escape(
        str(detail.get("token_address") or ""),
        quote=True,
    )

    html = html.replace(
        f"/api/discovery/solana/{token_address}/candles",
        f"/api/market/top-traded/{token_address}/candles",
    )
    html = html.replace(
        f"/api/discovery/solana/{token_address}/transactions",
        f"/api/market/top-traded/{token_address}/transactions",
    )
    html = html.replace(
        'href="/discovery/solana/',
        'href="/market/top-traded/',
    )

    html = html.replace(
        " · Solana Discovery</title>",
        " · Top Traded Workspace</title>",
        1,
    )
    html = html.replace(
        '<span class="eyebrow">Qualified exact-token workspace</span>',
        '<span class="eyebrow">Top Traded market workspace · Jupiter 24H</span>',
        1,
    )
    html = html.replace(
        "Review observed market activity, exact-pool identity and disclosed risk before taking any action.",
        "Review current Top Traded context and exact-pool market evidence. "
        "Top Traded inclusion is separate from DexSato Discovery qualification.",
        1,
    )

    # Discovery qualification semantics do not belong to market-feed workspaces.
    html = _remove_section(
        html,
        '<section class="qualification qualification-vp0d3',
    )
    html = _remove_section(
        html,
        '<section class="discovery-engine-v12',
    )

    # Bind the inherited production Jupiter trade UI to the separate
    # Top Traded execution route contract.
    html = html.replace(
        'data-jupiter-sandbox data-token-address=',
        f'data-jupiter-sandbox data-api-base="/api/market/top-traded/{token_address}" data-token-address=',
        1,
    )

    context = _top_traded_source_context(detail)
    html = html.replace(
        '<section class="card market-snapshot-v26">',
        context + '<section class="card market-snapshot-v26">',
        1,
    )

    html = html.replace(
        "<h2>Token List</h2>",
        "<h2>Top Traded Tokens</h2>",
        1,
    )
    html = html.replace(
        '<span class="token-list-chain-v07a">SOLANA</span>',
        '<span class="token-list-chain-v07a">JUPITER · 24H</span>',
        1,
    )
    html = html.replace(
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Token list views">',
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Top Traded market feed" hidden>',
        1,
    )

    return html


def render_trending_token_page(
    detail: dict[str, Any],
    *,
    feed: dict[str, Any],
) -> str:
    """Reuse the stable Token Workspace shell with Trending-only semantics."""
    html = render_solana_discovery_token_page(detail, feed=feed)

    # Separate route/API context. No Discovery archive semantics are introduced.
    html = html.replace(
        f"/api/discovery/solana/{escape(str(detail.get('token_address') or ''), quote=True)}/candles",
        f"/api/market/trending/{escape(str(detail.get('token_address') or ''), quote=True)}/candles",
    )
    html = html.replace(
        f"/api/discovery/solana/{escape(str(detail.get('token_address') or ''), quote=True)}/transactions",
        f"/api/market/trending/{escape(str(detail.get('token_address') or ''), quote=True)}/transactions",
    )
    html = html.replace('href="/discovery/solana/', 'href="/market/trending/')

    html = html.replace(" · Solana Discovery</title>", " · Trending Workspace</title>", 1)
    html = html.replace(
        '<span class="eyebrow">Qualified exact-token workspace</span>',
        '<span class="eyebrow">Trending market workspace · Jupiter 1H</span>',
        1,
    )
    html = html.replace(
        "Review observed market activity, exact-pool identity and disclosed risk before taking any action.",
        "Review current Trending context and exact-pool market evidence. "
        "Trending inclusion is separate from DexSato Discovery qualification.",
        1,
    )

    # Discovery-only UI must not imply that a Trending token was qualified.
    html = _remove_section(
        html,
        '<section class="qualification qualification-vp0d3',
    )
    html = _remove_section(
        html,
        '<section class="discovery-engine-v12',
    )

    # Reuse the production Jupiter execution UI while binding it to the
    # separate Trending route contract.
    token_address = escape(str(detail.get("token_address") or ""), quote=True)
    html = html.replace(
        'data-jupiter-sandbox data-token-address=',
        f'data-jupiter-sandbox data-api-base="/api/market/trending/{token_address}" data-token-address=',
        1,
    )

    context = _source_context(detail)

    html = html.replace(
        '<section class="card market-snapshot-v26">',
        context + '<section class="card market-snapshot-v26">',
        1,
    )

    # Keep the left rail scoped to the market-feed list rather than Discovery.
    html = html.replace("<h2>Token List</h2>", "<h2>Trending Tokens</h2>", 1)
    html = html.replace(
        '<span class="token-list-chain-v07a">SOLANA</span>',
        '<span class="token-list-chain-v07a">JUPITER · 1H</span>',
        1,
    )
    html = html.replace(
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Token list views">',
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Trending market feed" hidden>',
        1,
    )

    return html
