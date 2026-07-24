"""
AlphaRadar V1 Snapshot Dashboard Presenter.

Renders the latest stored V1 market snapshot without
running the AlphaRadar engine.

Responsibilities
----------------
- Render snapshot metadata
- Display the active V1 market universe
- Provide client-side token search
- Provide client-side decision filtering
- Display confidence and decision states clearly
- Display radar, system-live and next-scan indicators
- Escape all data-derived values

This module does NOT:
- run market scans
- read files
- send Telegram alerts
- schedule scans
- modify snapshot data
"""

from __future__ import annotations

from html import escape

from presentation.dashboard_theme import (
    THEME,
    build_dashboard_css,
    decision_colour,
)


# ==========================================================
# Display Helpers
# ==========================================================

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


def confidence_class(
    confidence: object,
) -> str:
    """
    Return the visual class for a confidence level.
    """

    normalized = str(
        confidence
        if confidence is not None
        else ""
    ).strip().upper()

    mapping = {
        "HIGH": "confidence-high",
        "MEDIUM": "confidence-medium",
        "LOW": "confidence-low",
    }

    return mapping.get(
        normalized,
        "confidence-unknown",
    )


def decision_class(
    decision: object,
) -> str:
    """
    Return the visual class for a market decision.
    """

    normalized = str(
        decision
        if decision is not None
        else ""
    ).strip().upper()

    mapping = {
        "BUY": "decision-buy",
        "WATCH": "decision-watch",
        "REVIEW": "decision-review",
        "SELL": "decision-sell",
        "IGNORE": "decision-ignore",
        "UNAVAILABLE": "decision-unavailable",
    }

    return mapping.get(
        normalized,
        "decision-unknown",
    )


# ==========================================================
# Coin Card
# ==========================================================

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

        <span
            class="decision-badge decision-unavailable"
        >
            UNAVAILABLE
        </span>
    </header>

    <p class="snapshot-error">
        {error}
    </p>
</article>
"""

    decision_raw = coin.get(
        "decision",
    )

    confidence_raw = coin.get(
        "confidence",
    )

    decision = _safe_text(
        decision_raw,
    )

    confidence = _safe_text(
        confidence_raw,
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
            decision_raw
            if decision_raw is not None
            else ""
        )
    )

    resolved_decision_class = decision_class(
        decision_raw,
    )

    resolved_confidence_class = confidence_class(
        confidence_raw,
    )

    decision_filter = _safe_text(
        decision_raw,
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
            class="
                decision-badge
                {resolved_decision_class}
            "
            style="--decision-colour:{colour};"
        >
            {decision}
        </span>
    </header>

    <div class="snapshot-metrics">
        <div class="snapshot-metric">
            <span>Confidence</span>

            <strong
                class="
                    confidence-badge
                    {resolved_confidence_class}
                "
            >
                {confidence}
            </strong>
        </div>

        <div class="snapshot-metric">
            <span>Historical</span>
            <strong>{historical_success}</strong>
        </div>

        <div class="snapshot-metric">
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


# ==========================================================
# Full Dashboard
# ==========================================================

def render_founder_snapshot_dashboard(
    snapshot: dict[str, object],
) -> str:
    """
    Render the complete AlphaRadar V1 snapshot dashboard.
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

    generated_at_attribute = _safe_text(
        snapshot.get(
            "generated_at",
        ),
        fallback="",
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

    <title>AlphaRadar Market Intelligence</title>

    <style>
        {shared_css}

        * {{
            box-sizing: border-box;
        }}

        :root {{
            --live-green: #22c55e;
            --watch-blue: #38bdf8;
            --review-yellow: #fbbf24;
            --buy-green: #4ade80;
            --sell-red: #fb7185;
            --ignore-grey: #94a3b8;
            --danger-red: #f87171;
            --confidence-high: #4ade80;
            --confidence-medium: #fbbf24;
            --confidence-low: #f87171;
            --confidence-unknown: #94a3b8;
        }}

        body {{
            min-height: 100vh;
            background:
                radial-gradient(
                    circle at top right,
                    rgba(59, 130, 246, 0.15),
                    transparent 30%
                ),
                radial-gradient(
                    circle at top left,
                    rgba(20, 184, 166, 0.08),
                    transparent 22%
                ),
                {THEME["background"]};
        }}

        .snapshot-shell {{
            width: min(1380px, calc(100% - 32px));
            margin: 0 auto;
            padding: 34px 0 60px;
        }}

        .snapshot-header {{
            margin-bottom: 22px;
        }}

        .header-topline {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 13px;
        }}

        .snapshot-kicker {{
            margin: 0;
            color: {THEME["accent"]};
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .live-indicator {{
            display: inline-flex;
            align-items: center;
            gap: 9px;
            padding: 8px 12px;
            border: 1px solid rgba(34, 197, 94, 0.32);
            border-radius: 999px;
            background: rgba(34, 197, 94, 0.08);
            color: #bbf7d0;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        .live-dot {{
            position: relative;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--live-green);
            box-shadow:
                0 0 0 4px rgba(34, 197, 94, 0.10),
                0 0 16px rgba(34, 197, 94, 0.75);
        }}

        .live-dot::after {{
            position: absolute;
            inset: -5px;
            border: 1px solid rgba(34, 197, 94, 0.45);
            border-radius: inherit;
            content: "";
            animation: live-pulse 1.8s ease-out infinite;
        }}

        .snapshot-title {{
            margin: 0;
            font-size: clamp(2rem, 5vw, 3.5rem);
        }}

        .snapshot-description {{
            margin: 10px 0 0;
            color: {THEME["muted"]};
            font-size: 1rem;
        }}

        .system-panel {{
            display: grid;
            grid-template-columns:
                minmax(180px, 230px)
                minmax(0, 1fr)
                minmax(230px, 300px);
            gap: 16px;
            margin: 24px 0;
        }}

        .system-card {{
            min-height: 150px;
            padding: 18px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 16px;
            background:
                linear-gradient(
                    145deg,
                    rgba(22, 42, 65, 0.96),
                    rgba(11, 23, 40, 0.98)
                );
            box-shadow:
                0 18px 45px rgba(0, 0, 0, 0.18);
        }}

        .system-card-label {{
            display: block;
            margin-bottom: 10px;
            color: {THEME["muted"]};
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }}

        .radar-card {{
            display: grid;
            place-items: center;
        }}

        .radar-wrap {{
            position: relative;
            width: 112px;
            height: 112px;
            border: 1px solid rgba(56, 189, 248, 0.46);
            border-radius: 50%;
            overflow: hidden;
            background:
                radial-gradient(
                    circle,
                    rgba(56, 189, 248, 0.14) 0 2px,
                    transparent 3px
                ),
                repeating-radial-gradient(
                    circle,
                    transparent 0 20px,
                    rgba(56, 189, 248, 0.12) 21px 22px
                );
            box-shadow:
                inset 0 0 30px rgba(56, 189, 248, 0.10),
                0 0 25px rgba(56, 189, 248, 0.08);
        }}

        .radar-wrap::before,
        .radar-wrap::after {{
            position: absolute;
            content: "";
            background: rgba(56, 189, 248, 0.18);
        }}

        .radar-wrap::before {{
            top: 50%;
            left: 0;
            width: 100%;
            height: 1px;
        }}

        .radar-wrap::after {{
            top: 0;
            left: 50%;
            width: 1px;
            height: 100%;
        }}

        .radar-sweep {{
            position: absolute;
            inset: 50% 50% 0 0;
            transform-origin: 100% 0;
            border-radius: 100% 0 0 0;
            background:
                linear-gradient(
                    36deg,
                    rgba(56, 189, 248, 0.55),
                    rgba(56, 189, 248, 0)
                );
            animation: radar-sweep 3.2s linear infinite;
        }}

        .radar-target {{
            position: absolute;
            top: 28px;
            right: 25px;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--live-green);
            box-shadow:
                0 0 0 4px rgba(34, 197, 94, 0.10),
                0 0 12px rgba(34, 197, 94, 0.85);
            animation: target-blink 2s ease-in-out infinite;
        }}

        .system-main {{
            display: grid;
            align-content: center;
            gap: 8px;
        }}

        .system-title {{
            margin: 0;
            font-size: 1.25rem;
        }}

        .system-subtitle {{
            margin: 0;
            color: {THEME["muted"]};
            line-height: 1.55;
        }}

        .snapshot-age {{
            color: var(--live-green);
            font-size: 0.88rem;
            font-weight: 800;
        }}

        .next-scan-card {{
            display: grid;
            align-content: center;
            gap: 8px;
        }}

        .next-scan-time {{
            margin: 0;
            font-size: 1.55rem;
            font-weight: 900;
        }}

        .next-scan-countdown {{
            color: var(--review-yellow);
            font-size: 0.88rem;
            font-weight: 800;
        }}

        .planned-note {{
            margin: 0;
            color: {THEME["muted"]};
            font-size: 0.76rem;
            line-height: 1.5;
        }}

        .snapshot-stats {{
            display: grid;
            grid-template-columns:
                repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin: 0 0 24px;
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

        .snapshot-controls input:focus,
        .snapshot-controls select:focus {{
            border-color: {THEME["accent"]};
            box-shadow:
                0 0 0 3px rgba(56, 189, 248, 0.10);
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
            transition:
                transform 160ms ease,
                border-color 160ms ease,
                box-shadow 160ms ease;
        }}

        .snapshot-coin:hover {{
            transform: translateY(-2px);
            border-color: rgba(56, 189, 248, 0.40);
            box-shadow:
                0 16px 38px rgba(0, 0, 0, 0.24);
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

        .decision-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 92px;
            padding: 8px 12px;
            border: 1px solid
                color-mix(
                    in srgb,
                    var(--decision-colour, #94a3b8) 50%,
                    transparent
                );
            border-radius: 999px;
            background:
                color-mix(
                    in srgb,
                    var(--decision-colour, #94a3b8) 12%,
                    transparent
                );
            color:
                var(--decision-colour, #94a3b8);
            font-size: 0.86rem;
            font-weight: 900;
            letter-spacing: 0.07em;
            text-transform: uppercase;
        }}

        .decision-buy {{
            --decision-colour: var(--buy-green);
        }}

        .decision-watch {{
            --decision-colour: var(--watch-blue);
            min-width: 104px;
            font-size: 0.95rem;
        }}

        .decision-review {{
            --decision-colour: var(--review-yellow);
            min-width: 104px;
            font-size: 0.94rem;
        }}

        .decision-sell {{
            --decision-colour: var(--sell-red);
        }}

        .decision-ignore {{
            --decision-colour: var(--ignore-grey);
            min-width: 98px;
            font-size: 0.88rem;
        }}

        .decision-unavailable {{
            --decision-colour: var(--danger-red);
        }}

        .decision-unknown {{
            --decision-colour: var(--ignore-grey);
        }}

        .snapshot-metrics {{
            display: grid;
            grid-template-columns:
                repeat(3, minmax(0, 1fr));
            gap: 8px;
        }}

        .snapshot-metric {{
            min-width: 0;
            padding: 10px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 9px;
        }}

        .snapshot-metric span {{
            display: block;
            margin-bottom: 7px;
            color: {THEME["muted"]};
            font-size: 0.62rem;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .snapshot-metric strong {{
            font-size: 0.83rem;
        }}

        .confidence-badge {{
            display: inline-flex;
            align-items: center;
            padding: 5px 8px;
            border-radius: 7px;
            font-weight: 900;
        }}

        .confidence-high {{
            border: 1px solid rgba(74, 222, 128, 0.35);
            background: rgba(74, 222, 128, 0.10);
            color: var(--confidence-high);
        }}

        .confidence-medium {{
            border: 1px solid rgba(251, 191, 36, 0.38);
            background: rgba(251, 191, 36, 0.11);
            color: var(--confidence-medium);
        }}

        .confidence-low {{
            border: 1px solid rgba(248, 113, 113, 0.38);
            background: rgba(248, 113, 113, 0.11);
            color: var(--confidence-low);
        }}

        .confidence-unknown {{
            border: 1px solid rgba(148, 163, 184, 0.30);
            background: rgba(148, 163, 184, 0.08);
            color: var(--confidence-unknown);
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
            display: grid;
            gap: 8px;
            margin-top: 34px;
            color: {THEME["muted"]};
            font-size: 0.8rem;
            text-align: center;
        }}

        .snapshot-footer-love {{
            color: {THEME["text"]};
            font-size: 0.9rem;
            font-weight: 700;
        }}

        @keyframes live-pulse {{
            0% {{
                opacity: 0.8;
                transform: scale(0.6);
            }}

            100% {{
                opacity: 0;
                transform: scale(1.5);
            }}
        }}

        @keyframes radar-sweep {{
            from {{
                transform: rotate(0deg);
            }}

            to {{
                transform: rotate(360deg);
            }}
        }}

        @keyframes target-blink {{
            0%,
            100% {{
                opacity: 0.35;
            }}

            50% {{
                opacity: 1;
            }}
        }}

        @media (max-width: 1080px) {{
            .system-panel {{
                grid-template-columns:
                    minmax(160px, 210px)
                    minmax(0, 1fr);
            }}

            .next-scan-card {{
                grid-column: span 2;
            }}

            .snapshot-grid {{
                grid-template-columns:
                    repeat(2, minmax(0, 1fr));
            }}
        }}

        @media (max-width: 720px) {{
            .header-topline {{
                align-items: flex-start;
                flex-direction: column;
            }}

            .system-panel,
            .snapshot-stats,
            .snapshot-grid,
            .snapshot-controls {{
                grid-template-columns: 1fr;
            }}

            .next-scan-card {{
                grid-column: auto;
            }}

            .snapshot-metrics {{
                grid-template-columns: 1fr;
            }}

            .decision-badge {{
                min-width: 88px;
            }}
        }}

        @media (
            prefers-reduced-motion: reduce
        ) {{
            .live-dot::after,
            .radar-sweep,
            .radar-target {{
                animation: none;
            }}

            .snapshot-coin {{
                transition: none;
            }}
        }}
    </style>
</head>

<body>
    <main class="snapshot-shell">
        <header class="snapshot-header">
            <div class="header-topline">
                <p class="snapshot-kicker">
                    AlphaRadar V1
                </p>

                <div class="live-indicator">
                    <span class="live-dot"></span>
                    System Live
                </div>
            </div>

            <h1 class="snapshot-title">
                AlphaRadar Market Intelligence
            </h1>

            <p class="snapshot-description">
                Current V1 production market universe.
            </p>
        </header>

        <section class="system-panel">
            <div class="system-card radar-card">
                <div
                    class="radar-wrap"
                    role="img"
                    aria-label="AlphaRadar active radar"
                >
                    <span class="radar-sweep"></span>
                    <span class="radar-target"></span>
                </div>
            </div>

            <div class="system-card system-main">
                <span class="system-card-label">
                    Radar Status
                </span>

                <h2 class="system-title">
                    Snapshot Online
                </h2>

                <p class="system-subtitle">
                    Dashboard is reading the latest completed
                    AlphaRadar engine snapshot.
                </p>

                <span
                    id="snapshot-age"
                    class="snapshot-age"
                    data-generated-at="{generated_at_attribute}"
                >
                    Calculating snapshot age…
                </span>
            </div>

            <div class="system-card next-scan-card">
                <span class="system-card-label">
                    Next Planned Scan
                </span>

                <p
                    id="next-scan-time"
                    class="next-scan-time"
                >
                    Calculating…
                </p>

                <span
                    id="next-scan-countdown"
                    class="next-scan-countdown"
                >
                    Calculating countdown…
                </span>

                <p class="planned-note">
                    Planned V1 windows:
                    08:00, 14:00 and 20:00 MYT.
                    Automatic scheduler is not active yet.
                </p>
            </div>
        </section>

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
            <span>
                Snapshot generated: {generated_at}
            </span>

            <span class="snapshot-footer-love">
                Made for Sya ❤️
            </span>
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

        const snapshotAge =
            document.getElementById("snapshot-age");

        const nextScanTime =
            document.getElementById("next-scan-time");

        const nextScanCountdown =
            document.getElementById(
                "next-scan-countdown"
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

        function formatDuration(
            milliseconds
        ) {{
            const totalMinutes = Math.max(
                0,
                Math.floor(
                    milliseconds / 60000
                )
            );

            const days = Math.floor(
                totalMinutes / 1440
            );

            const hours = Math.floor(
                (totalMinutes % 1440) / 60
            );

            const minutes =
                totalMinutes % 60;

            if (days > 0) {{
                return `${{days}}d ${{hours}}h ago`;
            }}

            if (hours > 0) {{
                return `${{hours}}h ${{minutes}}m ago`;
            }}

            return `${{minutes}}m ago`;
        }}

        function updateSnapshotAge() {{
            const rawGeneratedAt =
                snapshotAge.dataset.generatedAt;

            const generatedAt =
                new Date(rawGeneratedAt);

            if (
                !rawGeneratedAt
                || Number.isNaN(
                    generatedAt.getTime()
                )
            ) {{
                snapshotAge.textContent =
                    "Snapshot time unavailable";

                return;
            }}

            const difference =
                Date.now()
                - generatedAt.getTime();

            snapshotAge.textContent =
                `Updated ${{
                    formatDuration(
                        difference
                    )
                }}`;
        }}

        function buildMalaysiaDateParts(
            date
        ) {{
            const formatter =
                new Intl.DateTimeFormat(
                    "en-CA",
                    {{
                        timeZone:
                            "Asia/Kuala_Lumpur",
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        hour12: false,
                    }}
                );

            const parts = Object.fromEntries(
                formatter
                    .formatToParts(date)
                    .filter(
                        part =>
                            part.type !== "literal"
                    )
                    .map(
                        part => [
                            part.type,
                            part.value,
                        ]
                    )
            );

            return {{
                year: Number(parts.year),
                month: Number(parts.month),
                day: Number(parts.day),
                hour: Number(parts.hour),
                minute: Number(parts.minute),
                second: Number(parts.second),
            }};
        }}

        function malaysiaTimeToUtc(
            year,
            month,
            day,
            hour
        ) {{
            return new Date(
                Date.UTC(
                    year,
                    month - 1,
                    day,
                    hour - 8,
                    0,
                    0,
                )
            );
        }}

        function nextPlannedScan(
            now
        ) {{
            const malaysia =
                buildMalaysiaDateParts(now);

            const plannedHours = [
                8,
                14,
                20,
            ];

            for (
                const plannedHour
                of plannedHours
            ) {{
                if (
                    malaysia.hour
                    < plannedHour
                ) {{
                    return malaysiaTimeToUtc(
                        malaysia.year,
                        malaysia.month,
                        malaysia.day,
                        plannedHour,
                    );
                }}
            }}

            const tomorrow =
                malaysiaTimeToUtc(
                    malaysia.year,
                    malaysia.month,
                    malaysia.day,
                    8,
                );

            tomorrow.setUTCDate(
                tomorrow.getUTCDate() + 1
            );

            return tomorrow;
        }}

        function updateNextScan() {{
            const now = new Date();

            const nextScan =
                nextPlannedScan(now);

            nextScanTime.textContent =
                new Intl.DateTimeFormat(
                    "en-MY",
                    {{
                        timeZone:
                            "Asia/Kuala_Lumpur",
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: true,
                    }}
                ).format(nextScan)
                + " MYT";

            const difference =
                nextScan.getTime()
                - now.getTime();

            const totalMinutes = Math.max(
                0,
                Math.ceil(
                    difference / 60000
                )
            );

            const hours = Math.floor(
                totalMinutes / 60
            );

            const minutes =
                totalMinutes % 60;

            nextScanCountdown.textContent =
                hours > 0
                ? `in ${{hours}}h ${{minutes}}m`
                : `in ${{minutes}}m`;
        }}

        searchInput.addEventListener(
            "input",
            applyFilters
        );

        decisionFilter.addEventListener(
            "change",
            applyFilters
        );

        updateSnapshotAge();
        updateNextScan();

        window.setInterval(
            updateSnapshotAge,
            30000
        );

        window.setInterval(
            updateNextScan,
            30000
        );
    </script>
</body>
</html>
"""