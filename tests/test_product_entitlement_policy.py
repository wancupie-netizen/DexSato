from __future__ import annotations

from uuid import uuid4

import pytest

from application.product_entitlement_policy import (
    PRO_ENTITLEMENTS,
    PUBLIC_ENTITLEMENTS,
    ProductAccessTier,
    resolve_product_entitlements,
)
from application.product_identity_models import ProductPrincipal


def _authenticated_principal() -> ProductPrincipal:
    return ProductPrincipal(
        authenticated=True,
        user_id=uuid4(),
        email_masked="u***@example.com",
    )


def test_guest_is_public() -> None:
    policy = resolve_product_entitlements(
        ProductPrincipal.guest(),
        subscription_active=False,
    )

    assert policy is PUBLIC_ENTITLEMENTS
    assert policy.tier is ProductAccessTier.PUBLIC


def test_guest_cannot_become_pro_even_if_subscription_flag_is_true() -> None:
    policy = resolve_product_entitlements(
        ProductPrincipal.guest(),
        subscription_active=True,
    )

    assert policy is PUBLIC_ENTITLEMENTS


def test_authenticated_user_without_active_subscription_is_public() -> None:
    policy = resolve_product_entitlements(
        _authenticated_principal(),
        subscription_active=False,
    )

    assert policy is PUBLIC_ENTITLEMENTS
    assert policy.tier is ProductAccessTier.PUBLIC


def test_authenticated_active_subscriber_is_pro() -> None:
    policy = resolve_product_entitlements(
        _authenticated_principal(),
        subscription_active=True,
    )

    assert policy is PRO_ENTITLEMENTS
    assert policy.tier is ProductAccessTier.PRO


def test_public_policy_matches_locked_live_03a1_limits() -> None:
    policy = PUBLIC_ENTITLEMENTS

    assert policy.trending_max_items == 25
    assert policy.top_traded_max_items == 25
    assert policy.detected_signals_unique_rolling_24h_max == 5
    assert policy.full_discovery is False
    assert policy.recent_24h is False
    assert policy.archive is False
    assert policy.full_context_history is False
    assert policy.telegram_alerts is False


def test_pro_policy_removes_entitlement_caps_and_unlocks_pro_surfaces() -> None:
    policy = PRO_ENTITLEMENTS

    assert policy.trending_max_items is None
    assert policy.top_traded_max_items is None
    assert policy.detected_signals_unique_rolling_24h_max is None
    assert policy.full_discovery is True
    assert policy.recent_24h is True
    assert policy.archive is True
    assert policy.full_context_history is True
    assert policy.telegram_alerts is True


def test_essential_risk_warnings_are_never_paywalled() -> None:
    assert PUBLIC_ENTITLEMENTS.essential_risk_warnings is True
    assert PRO_ENTITLEMENTS.essential_risk_warnings is True


def test_subscription_flag_requires_real_boolean() -> None:
    with pytest.raises(TypeError):
        resolve_product_entitlements(
            _authenticated_principal(),
            subscription_active=1,  # type: ignore[arg-type]
        )
