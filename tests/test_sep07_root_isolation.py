from types import SimpleNamespace
from unittest.mock import patch

from app import main
from application.product_entitlement_policy import PRO_ENTITLEMENTS


def test_pro_root_does_not_read_legacy_archive():
    feeds = {name: {} for name in ("trending", "top_traded", "organic_flow", "recent")}
    auth = SimpleNamespace(available=True, principal=None)
    with (
        patch.object(main, "_request_entitlement_policy", return_value=(auth, PRO_ENTITLEMENTS)),
        patch.object(main, "_load_discovery_page_context", return_value=(feeds, {})),
        patch.object(main, "apply_market_feed_entitlements", return_value=feeds),
        patch.object(main, "load_solana_discovery_feed", side_effect=AssertionError("archive read")),
        patch.object(main, "locked_discovery_feed", return_value={"locked": True}),
        patch.object(main, "render_solana_discovery_page", return_value="ROOT") as render,
    ):
        assert main.app_home(object()) == "ROOT"
    assert render.call_args.args[0] == {"locked": True}
    assert render.call_args.kwargs["show_discovery_tab"] is False
