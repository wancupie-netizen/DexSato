"""
AlphaRadar Top 100 Snapshot Dashboard Presenter.

Renders the latest stored market snapshot without running
the AlphaRadar engine.

Responsibilities
----------------
- Render snapshot metadata
- Display all Top 100 market results
- Provide client-side token search
- Provide client-side decision filtering
- Escape all data-derived values

This module does NOT:
- run market scans
- read files
- send Telegram alerts
- modify snapshot data
"""

from __future__ import annotations

from html import escape

from presentation.dashboard_theme import (
    THEME,
    build_dashboard_css,
    decision_colour,
)


def _safe_text(
    value: object,
    *,
    fallback: str = "UNKNOWN",
) -> str:
    """
    Convert a value into escaped display text.
    """

    text = str(
        value
        if value is not None
        else fallback
    ).strip()

    return escape(
        text or fallback,
        quote=True,
    )


def render_snapshot_coin(
    coin: dict[str, object],
) -> str:
    """
    Render one serialized snapshot coin.
    """

    token = _safe_text(
        coin.get(
            "token",
        )
    )

    available = coin.get(
        "available",
        False,
    ) is True

    if not available:

        error = _safe_text(
            coin.get(
                "error",
            ),
            fallback=(
                "Market data is currently unavailable."
            ),
        )

        return f"""
<article
    class="snapshot-coin unavailable"
    data-token="{token.lower()}"
    data-decision="unavailable"
>
    <header class="snapshot-coin-header">
        <h2>{token}</h2>

        <span class="decision unavailable-label">
            UNAVAILABLE
        </span>
    </header>

    <p class="snapshot-error">
        {error}
    </p>
</article>
"""

    decision = _safe_text(
        coin.get(
            "decision",
        )
    )

    confidence = _safe_text(
        coin.get(
            "confidence",
        )
    )

    summary = _safe_text(
        coin.get(
            "summary",
        ),
        fallback="No summary available.",
    )

    success_value = coin.get(
        "historical_success",
        0.0,
    )

    try:

        historical_success = (
            f"{float(success_value):.2f}%"
        )

    except (
        TypeError,
        ValueError,
    ):

        historical_success = "0.00%"

    memory = (
        "KNOWN PATTERN"
        if coin.get(
            "seen_before",
            False,
        )
        else "NEW PATTERN"
    )

    reasons = coin.get(
        "reasons",
        [],
    )

    if isinstance(
        reasons,
        list,
    ) and reasons:

        reasons_html = "".join(
            (
                "<li>"
                f"{_safe_text(reason)}"
                "</li>"
            )
            for reason in reasons[:3]
        )

    else:

        reasons_html = (
            '<li class="empty-reason">'
            "No supporting evidence available."
            "</li>"
        )

    colour = decision_colour(
        str(
            coin.get(
                "decision",
                "",
            )
        )
    )

    decision_filter = _safe_text(
        coin.get(
            "decision",
        )
    ).lower()

    return f"""
<article
    class="snapshot-coin"
    data-token="{token.lower()}"
    data-decision="{decision_filter}"
>
    <header class="snapshot-coin-header">
        <h2>{token}</h2>

        <span
            class="decision"
            style="color:{colour};"
        >
            {decision}
        </span>
    </header>

    <div class="snapshot-metrics">
        <div>
            <span>Confidence</span>
            <strong>{confidence}</strong>
        </div>

        <div>
            <span>Historical</span>
            <strong>{historical_success}</strong>
        </div>

        <div>
            <span>Memory</span>
            <strong>{memory}</strong>
        </div>
    </div>

    <p class="snapshot-summary">
        {summary}
    </p>

    <ul class="snapshot-reasons">
        {reasons_html}
    </ul>
</article>
"""


def render_founder_snapshot_dashboard(
    snapshot: dict[str, object],
) -> str:
    """
    Render the complete Top 100 snapshot dashboard.
    """

    if not isinstance(
        snapshot,
        dict,
    ):

        raise ValueError(
            "Founder snapshot must be a dictionary."
        )

    coins = snapshot.get(
        "coins",
    )

    if not isinstance(
        coins,
        list,
    ):

        raise ValueError(
            "Founder snapshot coin data must be a list."
        )

    cards_html = "".join(
        render_snapshot_coin(
            coin,
        )
        for coin in coins
        if isinstance(
            coin,
            dict,
        )
    )

    generated_at = _safe_text(
        snapshot.get(
            "generated_at",
        ),
        fallback="Not available",
    )

    total_coins = _safe_text(
        snapshot.get(
            "total_coins",
            len(coins),
        )
    )

    available_coins = _safe_text(
        snapshot.get(
            "available_coins",
            0,
        )
    )

    unavailable_coins = _safe_text(
        snapshot.get(
            "unavailable_coins",
            0,
        )
    )

    shared_css = build_dashboard_css()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>AlphaRadar Top 100 Dashboard</title>

    <style>
        {shared_css}

        * {{
            box-sizing: border-box;
        }}

        body {{
            background:
                radial-gradient(
                    circle at top right,
                    rgba(59, 130, 246, 0.14),
                    transparent 30%
                ),
                {THEME["background"]};
        }}

        .snapshot-shell {{
            width: min(1380px, calc(100% - 32px));
            margin: 0 auto;
            padding: 36px 0 60px;
        }}

        .snapshot-header {{
            margin-bottom: 24px;
        }}

        .snapshot-kicker {{
            margin: 0 0 7px;
            color: {THEME["accent"]};
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .snapshot-title {{
            margin: 0;
            font-size: clamp(2rem, 5vw, 3.5rem);
        }}

        .snapshot-description {{
            margin: 10px 0 0;
            color: {THEME["muted"]};
        }}

        .snapshot-stats {{
            display: grid;
            grid-template-columns:
                repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin: 24px 0;
        }}

        .snapshot-stat {{
            padding: 18px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 14px;
            background: {THEME["surface"]};
        }}

        .snapshot-stat span {{
            display: block;
            margin-bottom: 7px;
            color: {THEME["muted"]};
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .snapshot-stat strong {{
            font-size: 1.55rem;
        }}

        .snapshot-controls {{
            display: grid;
            grid-template-columns:
                minmax(0, 1fr)
                minmax(180px, 260px);
            gap: 12px;
            margin-bottom: 22px;
        }}

        .snapshot-controls input,
        .snapshot-controls select {{
            width: 100%;
            padding: 13px 15px;
            border: 1px solid {THEME["border"]};
            border-radius: 11px;
            outline: none;
            background: {THEME["surface"]};
            color: {THEME["text"]};
            font: inherit;
        }}

        .snapshot-grid {{
            display: grid;
            grid-template-columns:
                repeat(3, minmax(0, 1fr));
            gap: 16px;
        }}

        .snapshot-coin {{
            padding: 20px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 16px;
            background:
                linear-gradient(
                    145deg,
                    rgba(22, 42, 65, 0.96),
                    rgba(11, 23, 40, 0.98)
                );
        }}

        .snapshot-coin[hidden] {{
            display: none;
        }}

        .snapshot-coin-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 15px;
            margin-bottom: 17px;
        }}

        .snapshot-coin-header h2 {{
            margin: 0;
            font-size: 1.55rem;
        }}

        .decision {{
            font-size: 0.8rem;
            font-weight: 900;
            letter-spacing: 0.06em;
        }}

        .unavailable-label {{
            color: {THEME["unknown"]};
        }}

        .snapshot-metrics {{
            display: grid;
            grid-template-columns:
                repeat(3, minmax(0, 1fr));
            gap: 8px;
        }}

        .snapshot-metrics div {{
            padding: 10px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 9px;
        }}

        .snapshot-metrics span {{
            display: block;
            margin-bottom: 5px;
            color: {THEME["muted"]};
            font-size: 0.62rem;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .snapshot-metrics strong {{
            font-size: 0.83rem;
        }}

        .snapshot-summary,
        .snapshot-error {{
            margin: 16px 0;
            color: {THEME["muted"]};
            line-height: 1.55;
        }}

        .snapshot-reasons {{
            display: grid;
            gap: 7px;
            margin: 0;
            padding: 0;
            list-style: none;
        }}

        .snapshot-reasons li {{
            padding: 9px 10px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 8px;
            color: {THEME["muted"]};
            font-size: 0.82rem;
        }}

        .snapshot-reasons li::before {{
            margin-right: 7px;
            color: {THEME["accent"]};
            content: "✓";
        }}

        .unavailable {{
            opacity: 0.72;
        }}

        .snapshot-footer {{
            margin-top: 26px;
            color: {THEME["muted"]};
            font-size: 0.8rem;
            text-align: center;
        }}

        @media (max-width: 1080px) {{
            .snapshot-grid {{
                grid-template-columns:
                    repeat(2, minmax(0, 1fr));
            }}
        }}

        @media (max-width: 720px) {{
            .snapshot-stats,
            .snapshot-grid,
            .snapshot-controls {{
                grid-template-columns: 1fr;
            }}

            .snapshot-metrics {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>

<body>
    <main class="snapshot-shell">
        <header class="snapshot-header">
            <p class="snapshot-kicker">
                AlphaRadar V1
            </p>

            <h1 class="snapshot-title">
                Top 100 Market Intelligence
            </h1>

            <p class="snapshot-description">
                Latest stored AlphaRadar engine snapshot.
                Opening this page does not trigger a new scan.
            </p>
        </header>

        <section class="snapshot-stats">
            <div class="snapshot-stat">
                <span>Total Markets</span>
                <strong>{total_coins}</strong>
            </div>

            <div class="snapshot-stat">
                <span>Available</span>
                <strong>{available_coins}</strong>
            </div>

            <div class="snapshot-stat">
                <span>Unavailable</span>
                <strong>{unavailable_coins}</strong>
            </div>
        </section>

        <section class="snapshot-controls">
            <input
                id="token-search"
                type="search"
                placeholder="Search token, e.g. BTC"
                aria-label="Search token"
            >

            <select
                id="decision-filter"
                aria-label="Filter by decision"
            >
                <option value="">All decisions</option>
                <option value="buy">BUY</option>
                <option value="watch">WATCH</option>
                <option value="review">REVIEW</option>
                <option value="sell">SELL</option>
                <option value="ignore">IGNORE</option>
                <option value="unavailable">
                    UNAVAILABLE
                </option>
            </select>
        </section>

        <section
            id="snapshot-grid"
            class="snapshot-grid"
        >
            {cards_html}
        </section>

        <footer class="snapshot-footer">
            Snapshot generated: {generated_at}
        </footer>
    </main>

    <script>
        const searchInput =
            document.getElementById("token-search");

        const decisionFilter =
            document.getElementById("decision-filter");

        const cards = Array.from(
            document.querySelectorAll(
                ".snapshot-coin"
            )
        );

        function applyFilters() {{
            const query =
                searchInput.value.trim().toLowerCase();

            const decision =
                decisionFilter.value.toLowerCase();

            for (const card of cards) {{
                const token =
                    card.dataset.token || "";

                const cardDecision =
                    card.dataset.decision || "";

                const tokenMatches =
                    !query || token.includes(query);

                const decisionMatches =
                    !decision
                    || cardDecision === decision;

                card.hidden = !(
                    tokenMatches
                    && decisionMatches
                );
            }}
        }}

        searchInput.addEventListener(
            "input",
            applyFilters
        );

        decisionFilter.addEventListener(
            "change",
            applyFilters
        );
    </script>
</body>
</html>
"""