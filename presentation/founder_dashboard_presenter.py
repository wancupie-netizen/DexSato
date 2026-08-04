"""
DexSato Founder Multi-Coin Dashboard Presenter.

Renders the Founder MVP multi-coin dashboard as one
standalone HTML document.

Responsibilities
----------------
- Render five coin summaries
- Render successful engine results
- Render unavailable-token states
- Escape all data-derived text
- Reuse the official DexSato Theme

This module does NOT:
- run scans
- access databases
- send Telegram messages
- calculate decisions
- modify DashboardCard
"""

from __future__ import annotations

from html import escape

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from presentation.dashboard_theme import (
    THEME,
    build_dashboard_css,
    decision_colour,
)


# ==========================================================
# Coin Card
# ==========================================================

def render_founder_coin_card(
    *,
    token: str,
    card: DashboardCard | None,
    error: str | None,
) -> str:
    """
    Render one coin result for the Founder Dashboard.
    """

    safe_token = escape(
        token,
        quote=True,
    )

    if card is None:

        safe_error = escape(
            error
            or "Dashboard result is currently unavailable.",
            quote=True,
        )

        return (
            '<article class="founder-coin-card unavailable">'
            '<div class="coin-card-header">'
            f'<h2 class="coin-symbol">{safe_token}</h2>'
            '<span class="coin-status unavailable-status">'
            "UNAVAILABLE"
            "</span>"
            "</div>"
            '<p class="coin-error">'
            f"{safe_error}"
            "</p>"
            "</article>"
        )

    safe_decision = escape(
        card.decision,
        quote=True,
    )

    safe_confidence = escape(
        card.confidence,
        quote=True,
    )

    safe_summary = escape(
        card.summary,
        quote=True,
    )

    decision_color = decision_colour(
        card.decision,
    )

    historical_success = (
        f"{card.historical_success:.2f}%"
    )

    memory_status = (
        "KNOWN PATTERN"
        if card.seen_before
        else "NEW PATTERN"
    )

    reasons = card.reasons[:3]

    if reasons:

        reasons_html = "".join(
            (
                "<li>"
                f"{escape(reason, quote=True)}"
                "</li>"
            )
            for reason in reasons
        )

    else:

        reasons_html = (
            '<li class="empty-reason">'
            "No supporting evidence available."
            "</li>"
        )

    return (
        '<article class="founder-coin-card">'
        '<div class="coin-card-header">'
        f'<h2 class="coin-symbol">{safe_token}</h2>'
        '<span class="coin-status" '
        f'style="color:{decision_color};">'
        f"{safe_decision}"
        "</span>"
        "</div>"

        '<div class="coin-metrics">'
        '<div class="coin-metric">'
        '<span>Confidence</span>'
        f"<strong>{safe_confidence}</strong>"
        "</div>"

        '<div class="coin-metric">'
        '<span>Historical Success</span>'
        f"<strong>{historical_success}</strong>"
        "</div>"

        '<div class="coin-metric">'
        '<span>Adaptive Memory</span>'
        f"<strong>{memory_status}</strong>"
        "</div>"
        "</div>"

        '<p class="coin-summary">'
        f"{safe_summary}"
        "</p>"

        '<ul class="coin-reasons">'
        f"{reasons_html}"
        "</ul>"
        "</article>"
    )


# ==========================================================
# Full Dashboard
# ==========================================================

def render_founder_dashboard(
    results: list[dict[str, object]],
) -> str:
    """
    Render the complete DexSato Founder Dashboard.
    """

    if not isinstance(
        results,
        list,
    ):

        raise ValueError(
            "Founder dashboard results must be a list."
        )

    coin_cards: list[str] = []

    for result in results:

        token = str(
            result.get(
                "token",
                "UNKNOWN",
            )
        )

        card = result.get(
            "card",
        )

        error = result.get(
            "error",
        )

        if card is not None and not isinstance(
            card,
            DashboardCard,
        ):

            raise ValueError(
                "Founder dashboard result contains "
                "an invalid DashboardCard."
            )

        coin_cards.append(
            render_founder_coin_card(

                token=token,

                card=card,

                error=(
                    str(error)
                    if error is not None
                    else None
                ),

            )
        )

    cards_html = "".join(
        coin_cards,
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

    <title>DexSato Founder Dashboard</title>

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
                    transparent 32%
                ),
                {THEME["background"]};
        }}

        .founder-shell {{
            width: min(1240px, calc(100% - 32px));
            margin: 0 auto;
            padding: 40px 0 64px;
        }}

        .founder-header {{
            margin-bottom: 28px;
        }}

        .founder-kicker {{
            margin: 0 0 8px;
            color: {THEME["accent"]};
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .founder-title {{
            margin: 0;
            font-size: clamp(2rem, 5vw, 3.6rem);
        }}

        .founder-description {{
            max-width: 720px;
            margin: 12px 0 0;
            color: {THEME["muted"]};
            line-height: 1.7;
        }}

        .coin-grid {{
            display: grid;
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
            gap: 20px;
        }}

        .founder-coin-card {{
            padding: 24px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 18px;
            background:
                linear-gradient(
                    145deg,
                    rgba(22, 42, 65, 0.96),
                    rgba(11, 23, 40, 0.98)
                );
            box-shadow:
                0 18px 45px rgba(0, 0, 0, 0.22);
        }}

        .founder-coin-card:first-child {{
            grid-column: span 2;
        }}

        .coin-card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 22px;
        }}

        .coin-symbol {{
            margin: 0;
            font-size: 2rem;
        }}

        .coin-status {{
            font-size: 1.15rem;
            font-weight: 900;
            letter-spacing: 0.06em;
        }}

        .coin-metrics {{
            display: grid;
            grid-template-columns:
                repeat(3, minmax(0, 1fr));
            gap: 12px;
        }}

        .coin-metric {{
            display: grid;
            gap: 7px;
            padding: 14px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.025);
        }}

        .coin-metric span {{
            color: {THEME["muted"]};
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
        }}

        .coin-summary {{
            margin: 20px 0;
            color: {THEME["text"]};
            line-height: 1.7;
        }}

        .coin-reasons {{
            display: grid;
            gap: 8px;
            margin: 0;
            padding: 0;
            list-style: none;
        }}

        .coin-reasons li {{
            padding: 10px 12px;
            border: 1px solid {THEME["border_soft"]};
            border-radius: 10px;
            color: {THEME["muted"]};
        }}

        .coin-reasons li::before {{
            margin-right: 9px;
            color: {THEME["accent"]};
            content: "✓";
            font-weight: 900;
        }}

        .unavailable {{
            opacity: 0.78;
        }}

        .unavailable-status {{
            color: {THEME["unknown"]};
        }}

        .coin-error {{
            margin: 0;
            color: {THEME["muted"]};
            line-height: 1.6;
        }}

        .founder-footer {{
            margin-top: 26px;
            color: {THEME["muted"]};
            font-size: 0.78rem;
            text-align: center;
        }}

        @media (max-width: 820px) {{
            .coin-grid {{
                grid-template-columns: 1fr;
            }}

            .founder-coin-card:first-child {{
                grid-column: auto;
            }}

            .coin-metrics {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>

<body>
    <main class="founder-shell">
        <header class="founder-header">
            <p class="founder-kicker">
                Founder MVP
            </p>

            <h1 class="founder-title">
                DexSato Market Intelligence
            </h1>

            <p class="founder-description">
                Five markets. One engine. Clear decisions,
                confidence and supporting evidence.
            </p>
        </header>

        <section class="coin-grid">
            {cards_html}
        </section>

        <footer class="founder-footer">
            DexSato Founder MVP · Engine-driven market
            intelligence
        </footer>
    </main>
</body>
</html>
"""