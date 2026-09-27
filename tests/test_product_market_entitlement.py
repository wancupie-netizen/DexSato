from pathlib import Path
from uuid import UUID

from application.product_entitlement_policy import (
    PRO_ENTITLEMENTS,
    PUBLIC_ENTITLEMENTS,
    ProductAccessTier,
)
from application.product_identity_models import ProductPrincipal
from application.product_market_entitlement import (
    apply_market_feed_entitlements,
    resolve_market_entitlement_policy,
)


USER_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeResolver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def resolve(self, principal):
        self.calls.append(principal)
        return self.result


def _principal() -> ProductPrincipal:
    return ProductPrincipal(
        authenticated=True,
        user_id=USER_ID,
        email_masked="u***@example.com",
    )


def _feed(prefix: str, count: int = 40) -> dict[str, object]:
    return {
        "connected": True,
        "status": "live",
        "source": "jupiter",
        "eligible_count": count,
        "rows": [
            {"rank": index + 1, "token": f"{prefix}-{index + 1}"}
            for index in range(count)
        ],
    }


def _market_feeds() -> dict[str, dict[str, object]]:
    return {
        "trending": _feed("trending"),
        "top_traded": _feed("top"),
        "organic_flow": _feed("organic"),
        "recent": _feed("recent"),
    }


def test_public_caps_trending_and_top_traded_at_25_only() -> None:
    feeds = _market_feeds()

    projected = apply_market_feed_entitlements(feeds, PUBLIC_ENTITLEMENTS)

    assert len(projected["trending"]["rows"]) == 25
    assert len(projected["top_traded"]["rows"]) == 25
    assert len(projected["organic_flow"]["rows"]) == 40
    assert len(projected["recent"]["rows"]) == 40
    assert projected["trending"]["source"] == "jupiter"
    assert projected["trending"]["eligible_count"] == 40
    assert projected["top_traded"]["eligible_count"] == 40


def test_pro_preserves_full_ranked_feed_rows() -> None:
    feeds = _market_feeds()

    projected = apply_market_feed_entitlements(feeds, PRO_ENTITLEMENTS)

    assert len(projected["trending"]["rows"]) == 40
    assert len(projected["top_traded"]["rows"]) == 40


def test_projection_does_not_mutate_loaded_market_feeds() -> None:
    feeds = _market_feeds()
    original_trending_rows = list(feeds["trending"]["rows"])
    original_top_rows = list(feeds["top_traded"]["rows"])

    projected = apply_market_feed_entitlements(feeds, PUBLIC_ENTITLEMENTS)

    assert feeds["trending"]["rows"] == original_trending_rows
    assert feeds["top_traded"]["rows"] == original_top_rows
    assert projected["trending"] is not feeds["trending"]
    assert projected["top_traded"] is not feeds["top_traded"]
    assert projected["organic_flow"] is feeds["organic_flow"]
    assert projected["recent"] is feeds["recent"]


def test_guest_is_public_without_building_entitlement_service() -> None:
    def should_not_build():
        raise AssertionError("guest must not build the entitlement service")

    policy = resolve_market_entitlement_policy(
        ProductPrincipal.guest(),
        service_builder=should_not_build,
    )

    assert policy.tier is ProductAccessTier.PUBLIC


def test_authenticated_principal_without_user_id_is_public_without_lookup() -> None:
    def should_not_build():
        raise AssertionError("malformed principal must not build the entitlement service")

    policy = resolve_market_entitlement_policy(
        ProductPrincipal(authenticated=True),
        service_builder=should_not_build,
    )

    assert policy.tier is ProductAccessTier.PUBLIC


def test_authenticated_active_entitlement_can_resolve_pro() -> None:
    resolver = FakeResolver(PRO_ENTITLEMENTS)
    principal = _principal()

    policy = resolve_market_entitlement_policy(
        principal,
        service_builder=lambda: resolver,
    )

    assert policy.tier is ProductAccessTier.PRO
    assert resolver.calls == [principal]


def test_entitlement_resolution_failure_fails_closed_public() -> None:
    def broken_builder():
        raise RuntimeError("subscription persistence unavailable")

    policy = resolve_market_entitlement_policy(
        _principal(),
        service_builder=broken_builder,
    )

    assert policy.tier is ProductAccessTier.PUBLIC


def test_invalid_entitlement_result_fails_closed_public() -> None:
    resolver = FakeResolver(object())

    policy = resolve_market_entitlement_policy(
        _principal(),
        service_builder=lambda: resolver,
    )

    assert policy.tier is ProductAccessTier.PUBLIC


def test_discovery_routes_apply_projection_before_presenter() -> None:
    source = Path("app/main.py").read_text(encoding="utf-8")

    assert source.count("market_feeds = apply_market_feed_entitlements(") == 2
    assert source.count("resolve_market_entitlement_policy(auth_view.principal)") == 2
