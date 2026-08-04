"""
Tests for DexSato Dashboard Preview Entry Point.
"""

from unittest.mock import patch

from dashboard_preview import (
    build_preview_dashboard_card,
    open_dashboard_preview,
    write_dashboard_preview,
)


# ==========================================================
# Preview Card
# ==========================================================

def test_should_build_preview_dashboard_card():
    """
    Preview entry point should build a valid DashboardCard.
    """

    card = build_preview_dashboard_card()

    assert card.token == "BTC"

    assert card.decision == "WATCH"

    assert card.confidence == "HIGH"

    assert card.historical_success == 66.67

    assert card.seen_before is True

    assert card.metadata.engine_version == "1.0.0"


# ==========================================================
# HTML File
# ==========================================================

def test_should_write_dashboard_preview(
    tmp_path,
):
    """
    Preview entry point should save Dashboard V2 HTML.
    """

    card = build_preview_dashboard_card()

    output_file = (
        tmp_path
        / "dashboard_preview.html"
    )

    result = write_dashboard_preview(

        card=card,

        output_file=output_file,

    )

    assert result == output_file.resolve()

    assert result.exists()

    html = result.read_text(
        encoding="utf-8",
    )

    assert "<!DOCTYPE html>" in html

    assert "DexSato Dashboard" in html

    assert "DexSato" in html

    assert "BTC" in html

    assert "Market Decision" in html

    assert "WATCH" in html

    assert "Radar Confidence" in html

    assert "HIGH" in html

    assert "Historical Intelligence" in html

    assert "66.67%" in html

    assert "KNOWN PATTERN" in html

    assert "Intelligence Summary" in html

    assert "Evidence" in html

    assert "ACCUMULATION" in html

    assert "dashboard-component-stack" in html


# ==========================================================
# Browser Delegation
# ==========================================================

@patch(
    "dashboard_preview.webbrowser.open"
)
def test_should_open_dashboard_in_browser(
    mock_webbrowser_open,
    tmp_path,
):
    """
    Preview entry point should open the generated file URI.
    """

    output_file = (

        tmp_path
        / "dashboard_preview.html"

    ).resolve()

    output_file.write_text(

        "<html></html>",

        encoding="utf-8",

    )

    mock_webbrowser_open.return_value = True

    result = open_dashboard_preview(
        output_file,
    )

    assert result is True

    mock_webbrowser_open.assert_called_once_with(
        output_file.as_uri(),
    )