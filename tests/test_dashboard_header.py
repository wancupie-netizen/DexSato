"""
Tests for Dashboard Header Component.
"""

from presentation.dashboard_components.header import (
    render_dashboard_header,
)


def test_should_render_dashboard_header():

    html = render_dashboard_header(

        token="BTC",

        last_updated="2026-07-23 10:30 UTC",

        engine_version="1.0.0",

    )

    assert "DexSato" in html

    assert "BTC" in html

    assert "1.0.0" in html


def test_should_escape_html():

    html = render_dashboard_header(

        token="<BTC>",

        last_updated="NOW",

        engine_version="1.0.0",

    )

    assert "<BTC>" not in html

    assert "&lt;BTC&gt;" in html