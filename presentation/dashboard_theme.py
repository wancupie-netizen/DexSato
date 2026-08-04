"""
DexSato Dashboard Theme.

Centralised visual language for every Dashboard presenter.

Responsibilities
----------------
- Dashboard colour palette
- Typography
- Card spacing
- Badge appearance
- Shared responsive CSS
- Visual interaction states

This module does NOT:
- render HTML
- access DashboardCard
- calculate values
- access repositories
"""

from __future__ import annotations


# ==========================================================
# Theme
# ==========================================================

THEME = {

    "background":
        "#07111f",

    "background_soft":
        "#0b1728",

    "surface":
        "#102033",

    "surface_alt":
        "#162a41",

    "surface_highlight":
        "#1d3550",

    "text":
        "#f8fafc",

    "muted":
        "#94a3b8",

    "muted_soft":
        "#64748b",

    "border":
        "#29415c",

    "border_soft":
        "#1d334b",

    "accent":
        "#22cdb8",

    "buy":
        "#22c55e",

    "watch":
        "#3b82f6",

    "sell":
        "#ef4444",

    "warning":
        "#f59e0b",

    "unknown":
        "#64748b",

}


# ==========================================================
# Decision Colours
# ==========================================================

_DECISION_COLOURS = {

    "BUY":
        THEME["buy"],

    "WATCH":
        THEME["watch"],

    "SELL":
        THEME["sell"],

}


def decision_colour(
    decision: str,
) -> str:
    """
    Return the official Dashboard colour for a decision.
    """

    if not isinstance(
        decision,
        str,
    ):

        return THEME[
            "unknown"
        ]

    return _DECISION_COLOURS.get(

        decision.strip().upper(),

        THEME["unknown"],

    )


# ==========================================================
# Shared CSS
# ==========================================================

def build_dashboard_css() -> str:
    """
    Build the shared DexSato Dashboard V2 CSS.
    """

    return f"""
html {{

    min-width: 320px;

    background:
        {THEME["background"]};

    scroll-behavior: smooth;

}}

body {{

    margin: 0;

    min-height: 100vh;

    background:
        {THEME["background"]};

    color:
        {THEME["text"]};

    font-family:
        Inter,
        "Segoe UI",
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        Arial,
        sans-serif;

    font-size: 16px;

    line-height: 1.5;

    text-rendering:
        optimizeLegibility;

    -webkit-font-smoothing:
        antialiased;

}}

.container {{

    width:
        min(
            1200px,
            calc(
                100% - 32px
            )
        );

    margin:
        40px
        auto;

}}

.card {{

    position: relative;

    overflow: hidden;

    padding: 26px;

    border:
        1px solid
        {THEME["border_soft"]};

    border-radius:
        18px;

    background:
        linear-gradient(
            145deg,
            rgba(
                22,
                42,
                65,
                0.96
            ),
            rgba(
                11,
                23,
                40,
                0.98
            )
        );

    box-shadow:
        0
        18px
        45px
        rgba(
            0,
            0,
            0,
            0.22
        );

    transition:
        transform
        180ms
        ease,
        border-color
        180ms
        ease,
        box-shadow
        180ms
        ease;

}}

.card::before {{

    position: absolute;

    top: 0;

    right: 0;

    left: 0;

    height: 1px;

    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(
                34,
                205,
                184,
                0.55
            ),
            transparent
        );

    content: "";

    opacity: 0.72;

}}

.card:hover {{

    transform:
        translateY(
            -2px
        );

    border-color:
        {THEME["border"]};

    box-shadow:
        0
        24px
        60px
        rgba(
            0,
            0,
            0,
            0.3
        );

}}

.badge {{

    display:
        inline-flex;

    align-items:
        center;

    justify-content:
        center;

    min-height:
        34px;

    padding:
        7px
        14px;

    border-radius:
        999px;

    font-size:
        0.75rem;

    font-weight:
        800;

    letter-spacing:
        0.06em;

    line-height:
        1;

    text-transform:
        uppercase;

}}

h1,
h2,
h3,
p {{

    overflow-wrap:
        anywhere;

}}

h1,
h2,
h3 {{

    margin-top: 0;

    color:
        {THEME["text"]};

}}

h1 {{

    letter-spacing:
        -0.035em;

}}

small {{

    color:
        {THEME["muted"]};

}}

a {{

    color:
        {THEME["accent"]};

}}

::selection {{

    background:
        rgba(
            34,
            205,
            184,
            0.24
        );

    color:
        {THEME["text"]};

}}

@media (
    max-width: 820px
) {{

    .container {{

        width:
            min(
                100% - 24px,
                1200px
            );

        margin:
            24px
            auto;

    }}

    .card {{

        padding:
            22px;

        border-radius:
            16px;

    }}

}}

@media (
    max-width: 520px
) {{

    body {{

        font-size:
            15px;

    }}

    .container {{

        width:
            min(
                100% - 16px,
                1200px
            );

        margin:
            16px
            auto;

    }}

    .card {{

        padding:
            18px;

        border-radius:
            14px;

    }}

    .badge {{

        min-height:
            30px;

        padding:
            6px
            11px;

        font-size:
            0.68rem;

    }}

}}

@media (
    prefers-reduced-motion:
    reduce
) {{

    html {{

        scroll-behavior:
            auto;

    }}

    *,
    *::before,
    *::after {{

        scroll-behavior:
            auto !important;

        transition-duration:
            0.01ms !important;

        animation-duration:
            0.01ms !important;

        animation-iteration-count:
            1 !important;

    }}

}}
"""