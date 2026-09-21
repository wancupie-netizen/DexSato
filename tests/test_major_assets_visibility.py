"""Regression contract for the temporarily hidden Major Assets page."""

from app.main import app


def test_major_assets_route_is_temporarily_unregistered():
    """The unstable legacy dashboard must not be publicly routable."""
    registered_paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }

    assert "/major-assets" not in registered_paths
