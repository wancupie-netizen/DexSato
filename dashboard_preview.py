"""
DexSato Dashboard Preview Entry Point.

Creates a standalone DashboardCard preview,
renders it as HTML, saves the generated document,
and opens it in the default web browser.

This entry point is temporary.

It exists to verify the complete presentation path
before connecting the dashboard to stored Intelligence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import webbrowser

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
    create_dashboard_card,
)

from presentation.dashboard_html_presenter import (
    render_dashboard_html,
)


# ==========================================================
# Preview Configuration
# ==========================================================

OUTPUT_DIRECTORY = Path(
    "output",
    "dashboard",
)

OUTPUT_FILE = OUTPUT_DIRECTORY / "dashboard_preview.html"


# ==========================================================
# Preview Card
# ==========================================================

def build_preview_dashboard_card() -> DashboardCard:
    """
    Build a representative DexSato DashboardCard.

    This sample will later be replaced by real stored
    Intelligence and Adaptive history.
    """

    return create_dashboard_card(

        token=
            "BTC",

        decision=
            "WATCH",

        confidence=
            "HIGH",

        historical_success=
            66.67,

        seen_before=
            True,

        reasons=[

            "ACCUMULATION",

            "STRONG_LIQUIDITY",

            "PRICE_MOMENTUM",

        ],

        summary=(
            "Bullish market behaviour has been detected. "
            "Historical experience shows that similar "
            "conditions succeeded in approximately two "
            "out of three recorded observations."
        ),

        last_updated=datetime.now(
            timezone.utc,
        ),

    )


# ==========================================================
# HTML Output
# ==========================================================

def write_dashboard_preview(
    *,
    card: DashboardCard,
    output_file: Path = OUTPUT_FILE,
) -> Path:
    """
    Render and save the Dashboard preview.

    Parameters
    ----------
    card
        DashboardCard to render.

    output_file
        Target HTML file.

    Returns
    -------
    Path
        Absolute path to the generated HTML document.
    """

    html = render_dashboard_html(
        card,
    )

    output_file.parent.mkdir(

        parents=True,

        exist_ok=True,

    )

    output_file.write_text(

        html,

        encoding="utf-8",

    )

    return output_file.resolve()


# ==========================================================
# Browser
# ==========================================================

def open_dashboard_preview(
    output_file: Path,
) -> bool:
    """
    Open the generated Dashboard in the default browser.
    """

    return webbrowser.open(
        output_file.as_uri(),
    )


# ==========================================================
# Entry Point
# ==========================================================

def main() -> Path:
    """
    Generate and open the first DexSato Dashboard.
    """

    print()

    print("=" * 60)

    print(
        "DexSato Dashboard Preview"
    )

    print("=" * 60)

    card = build_preview_dashboard_card()

    output_file = write_dashboard_preview(
        card=card,
    )

    print()

    print(
        "Dashboard generated:"
    )

    print(
        output_file,
    )

    browser_opened = open_dashboard_preview(
        output_file,
    )

    print()

    if browser_opened:

        print(
            "Dashboard opened in the default browser."
        )

    else:

        print(
            "Browser could not be opened automatically."
        )

        print(
            "Open the generated HTML file manually."
        )

    print()

    return output_file


if __name__ == "__main__":

    main()