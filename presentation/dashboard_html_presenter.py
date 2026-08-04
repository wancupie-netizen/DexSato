"""
DexSato Dashboard HTML Presenter.

Presentation boundary for converting a DashboardCard
into a complete standalone Dashboard V2 HTML document.

Responsibilities
----------------
- Receive DashboardCard
- Format presentation timestamps
- Coordinate Dashboard components
- Apply the central Dashboard theme
- Render a standalone HTML document

This module does NOT:
- access databases
- access repositories
- build DashboardRequest
- make trading decisions
- write files
- open web browsers
- calculate adaptive history
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from presentation.dashboard_components.ai_summary import (
    render_ai_summary_panel,
)

from presentation.dashboard_components.decision_card import (
    render_decision_card,
)

from presentation.dashboard_components.evidence_panel import (
    render_evidence_panel,
)

from presentation.dashboard_components.header import (
    render_dashboard_header,
)

from presentation.dashboard_components.historical_panel import (
    render_historical_panel,
)

from presentation.dashboard_theme import (
    THEME,
    build_dashboard_css,
)


# ==========================================================
# Formatting
# ==========================================================

def format_dashboard_datetime(
    value: datetime,
) -> str:
    """
    Format a Dashboard datetime for human-readable display.

    Timezone information is retained when available.
    """

    if not isinstance(
        value,
        datetime,
    ):

        raise ValueError(
            "Dashboard timestamp must be a datetime."
        )

    return value.isoformat(
        sep=" ",
        timespec="seconds",
    )


# ==========================================================
# Component Orchestration
# ==========================================================

def render_dashboard_components(
    card: DashboardCard,
) -> str:
    """
    Render all Dashboard V2 components.

    Component order is part of the presentation contract.
    """

    if not isinstance(
        card,
        DashboardCard,
    ):

        raise ValueError(
            "DashboardCard is required."
        )

    last_updated = format_dashboard_datetime(
        card.last_updated,
    )

    header = render_dashboard_header(

        token=
            card.token,

        last_updated=
            last_updated,

        engine_version=
            card.metadata.engine_version,

    )

    decision = render_decision_card(

        decision=
            card.decision,

        confidence=
            card.confidence,

    )

    history = render_historical_panel(

        historical_success=
            card.historical_success,

        seen_before=
            card.seen_before,

    )

    summary = render_ai_summary_panel(

        summary=
            card.summary,

    )

    evidence = render_evidence_panel(

        reasons=
            card.reasons,

    )

    return (
        '<div class="dashboard-component-stack">'
        f"{header}"
        '<div class="dashboard-primary-grid">'
        f"{decision}"
        f"{history}"
        "</div>"
        '<div class="dashboard-secondary-grid">'
        f"{summary}"
        f"{evidence}"
        "</div>"
        "</div>"
    )


# ==========================================================
# Dashboard CSS
# ==========================================================

def build_dashboard_v2_css() -> str:
    """
    Build shared and presenter-level Dashboard V2 CSS.
    """

    shared_css = build_dashboard_css()

    return f"""
{shared_css}

* {{
    box-sizing: border-box;
}}

:root {{
    color-scheme: dark;

    --dashboard-background:
        {THEME["background"]};

    --dashboard-surface:
        {THEME["surface"]};

    --dashboard-surface-alt:
        {THEME["surface_alt"]};

    --dashboard-text:
        {THEME["text"]};

    --dashboard-muted:
        {THEME["muted"]};

    --dashboard-border:
        {THEME["border"]};
}}

body {{
    min-height: 100vh;

    background:
        radial-gradient(
            circle at top right,
            rgba(59, 130, 246, 0.14),
            transparent 34%
        ),
        var(--dashboard-background);
}}

.page-shell {{
    width: min(
        1180px,
        calc(100% - 32px)
    );

    margin: 0 auto;

    padding:
        40px
        0
        64px;
}}

.dashboard-component-stack {{
    display: grid;

    gap: 24px;
}}

.dashboard-primary-grid,
.dashboard-secondary-grid {{
    display: grid;

    grid-template-columns:
        repeat(
            2,
            minmax(0, 1fr)
        );

    gap: 24px;
}}

.dashboard-panel {{
    margin-bottom: 0;
}}

.dashboard-panel-header {{
    margin-bottom: 22px;
}}

.dashboard-panel-title {{
    margin:
        0
        0
        7px;

    font-size: 1rem;

    letter-spacing: 0.05em;

    text-transform: uppercase;
}}

.dashboard-panel-subtitle {{
    margin: 0;

    color: var(--dashboard-muted);

    font-size: 0.84rem;

    line-height: 1.55;
}}

.dashboard-panel-content {{
    min-width: 0;
}}

.decision-card-content {{
    display: grid;

    grid-template-columns:
        minmax(0, 1fr)
        auto;

    align-items: end;

    gap: 24px;
}}

.decision-card-primary,
.decision-card-confidence {{
    display: grid;

    gap: 10px;
}}

.decision-card-label,
.historical-metric-label {{
    color: var(--dashboard-muted);

    font-size: 0.74rem;

    font-weight: 700;

    letter-spacing: 0.09em;

    text-transform: uppercase;
}}

.decision-card-value {{
    font-size:
        clamp(
            2.25rem,
            7vw,
            4.4rem
        );

    line-height: 1;

    letter-spacing: -0.04em;
}}

.confidence-badge {{
    border:
        1px solid
        var(--dashboard-border);

    background:
        rgba(
            255,
            255,
            255,
            0.04
        );

    color: var(--dashboard-text);

    text-align: center;
}}

.historical-panel-grid {{
    display: grid;

    grid-template-columns:
        repeat(
            3,
            minmax(0, 1fr)
        );

    gap: 14px;
}}

.historical-metric {{
    display: grid;

    align-content: start;

    gap: 10px;

    min-height: 112px;

    padding: 16px;

    border:
        1px solid
        var(--dashboard-border);

    border-radius: 12px;

    background:
        rgba(
            255,
            255,
            255,
            0.025
        );
}}

.historical-metric-value {{
    font-size: 1.4rem;
}}

.adaptive-memory-known {{
    border:
        1px solid
        rgba(
            34,
            197,
            94,
            0.42
        );

    color: {THEME["buy"]};
}}

.adaptive-memory-new {{
    border:
        1px solid
        rgba(
            100,
            116,
            139,
            0.55
        );

    color: {THEME["unknown"]};
}}

.intelligence-summary {{
    margin: 0;

    color: var(--dashboard-text);

    font-size: 1.04rem;

    line-height: 1.75;
}}

.evidence-list {{
    display: grid;

    gap: 10px;

    margin: 0;

    padding: 0;

    list-style: none;
}}

.evidence-list li {{
    padding: 12px 14px;

    border:
        1px solid
        var(--dashboard-border);

    border-radius: 11px;

    background:
        rgba(
            255,
            255,
            255,
            0.025
        );

    color: var(--dashboard-muted);
}}

.evidence-list li::before {{
    content: "✓";

    margin-right: 10px;

    color: {THEME["watch"]};

    font-weight: 800;
}}

.empty-state {{
    margin: 0;

    color: var(--dashboard-muted);

    font-style: italic;
}}

.dashboard-footer {{
    display: flex;

    justify-content: space-between;

    gap: 20px;

    margin-top: 24px;

    padding:
        16px
        4px;

    color: var(--dashboard-muted);

    font-size: 0.76rem;
}}

@media (
    max-width: 820px
) {{

    .dashboard-primary-grid,
    .dashboard-secondary-grid {{
        grid-template-columns: 1fr;
    }}

    .historical-panel-grid {{
        grid-template-columns: 1fr;
    }}

    .decision-card-content {{
        grid-template-columns: 1fr;

        align-items: start;
    }}

    .dashboard-footer {{
        flex-direction: column;
    }}
}}
"""


# ==========================================================
# Complete Presenter
# ==========================================================

def render_dashboard_html(
    card: DashboardCard,
) -> str:
    """
    Render a DashboardCard as a standalone HTML document.
    """

    if not isinstance(
        card,
        DashboardCard,
    ):

        raise ValueError(
            "DashboardCard is required."
        )

    safe_token = escape(
        card.token,
        quote=True,
    )

    generated_at = format_dashboard_datetime(
        card.metadata.generated_at,
    )

    last_updated = format_dashboard_datetime(
        card.last_updated,
    )

    components = render_dashboard_components(
        card,
    )

    css = build_dashboard_v2_css()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>
        DexSato Dashboard — {safe_token}
    </title>

    <style>
        {css}
    </style>
</head>

<body>
    <main class="page-shell">
        {components}

        <footer class="dashboard-footer">
            <span>
                Last updated:
                {escape(last_updated)}
            </span>

            <span>
                Dashboard generated:
                {escape(generated_at)}
            </span>
        </footer>
    </main>
</body>
</html>
"""