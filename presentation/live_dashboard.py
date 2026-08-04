"""
DexSato Live Dashboard Entry Point.

Runs the DexSato Production Runner for one token,
extracts the resulting DashboardCard, renders it as HTML,
saves the document, and opens it in the default browser.

Responsibilities
----------------
- Accept token input
- Invoke Production Runner
- Handle first-scan and failure results
- Render the returned DashboardCard
- Save standalone HTML
- Open the generated dashboard

This module does NOT:
- make trading decisions
- access stores directly
- deserialize Intelligence
- build DashboardRequest manually
- modify DashboardCard
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import webbrowser

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from presentation.dashboard_html_presenter import (
    render_dashboard_html,
)

from scanner.runner import (
    run_scan,
)


# ==========================================================
# Configuration
# ==========================================================

OUTPUT_DIRECTORY = Path(
    "output",
    "dashboard",
)


# ==========================================================
# Token Helpers
# ==========================================================

def normalize_token(
    token: str,
) -> str:
    """
    Normalize and validate a token symbol.
    """

    normalized = token.strip().upper()

    if not normalized:

        raise ValueError(
            "Token symbol is required."
        )

    if not re.fullmatch(
        r"[A-Z0-9_-]+",
        normalized,
    ):

        raise ValueError(
            "Token symbol contains unsupported characters."
        )

    return normalized


def build_output_file(
    token: str,
) -> Path:
    """
    Build the output HTML path for a token.
    """

    normalized = normalize_token(
        token,
    )

    return (
        OUTPUT_DIRECTORY
        / f"{normalized.lower()}_dashboard.html"
    )


# ==========================================================
# Scan Result
# ==========================================================

def extract_dashboard(
    result: dict,
) -> DashboardCard:
    """
    Extract DashboardCard from a Runner result.

    Raises
    ------
    RuntimeError
        When the scan failed, produced only a first-scan
        checkpoint, or returned no DashboardCard.
    """

    if not result.get(
        "success",
        False,
    ):

        message = result.get(
            "error",
            "DexSato scan failed.",
        )

        raise RuntimeError(
            str(message)
        )

    dashboard = result.get(
        "dashboard",
    )

    if dashboard is None:

        message = result.get(
            "message",
            (
                "Dashboard is not available. "
                "The token may require another scan."
            ),
        )

        raise RuntimeError(
            str(message)
        )

    if not isinstance(
        dashboard,
        DashboardCard,
    ):

        raise RuntimeError(
            "Runner returned an invalid DashboardCard."
        )

    return dashboard


# ==========================================================
# HTML Output
# ==========================================================

def write_live_dashboard(
    *,
    card: DashboardCard,
    output_file: Path,
) -> Path:
    """
    Render and save a live DashboardCard.
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


def open_live_dashboard(
    output_file: Path,
) -> bool:
    """
    Open the live dashboard in the default browser.
    """

    return webbrowser.open(
        output_file.as_uri(),
    )


# ==========================================================
# Live Dashboard Flow
# ==========================================================

def generate_live_dashboard(
    token: str,
) -> Path:
    """
    Run a production scan and generate its dashboard HTML.
    """

    normalized_token = normalize_token(
        token,
    )

    result = run_scan(
        normalized_token,
    )

    card = extract_dashboard(
        result,
    )

    output_file = build_output_file(
        normalized_token,
    )

    return write_live_dashboard(

        card=card,

        output_file=output_file,

    )


# ==========================================================
# CLI
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(

        description=(
            "Run DexSato and open a live token dashboard."
        ),

    )

    parser.add_argument(

        "token",

        help=(
            "Token symbol to scan, for example BTC."
        ),

    )

    parser.add_argument(

        "--no-browser",

        action="store_true",

        help=(
            "Generate HTML without opening the browser."
        ),

    )

    return parser.parse_args()


def main() -> int:
    """
    Generate the live DexSato dashboard.
    """

    arguments = parse_arguments()

    print()

    print("=" * 60)

    print(
        "DexSato Live Dashboard"
    )

    print("=" * 60)

    try:

        output_file = generate_live_dashboard(
            arguments.token,
        )

    except (
        ValueError,
        RuntimeError,
    ) as error:

        print()

        print(
            f"Dashboard unavailable: {error}"
        )

        print()

        return 1

    print()

    print(
        "Dashboard generated:"
    )

    print(
        output_file,
    )

    if not arguments.no_browser:

        opened = open_live_dashboard(
            output_file,
        )

        print()

        if opened:

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

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )