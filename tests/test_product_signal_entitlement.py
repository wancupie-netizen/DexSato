from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from application.product_entitlement_policy import (
    PRO_ENTITLEMENTS,
    PUBLIC_ENTITLEMENTS,
    ProductAccessTier,
    ProductEntitlementPolicy,
)
from application.product_identity_models import ProductPrincipal
from application.product_signal_entitlement import (
    ProductSignalEntitlementAdmission,
    apply_detected_signal_entitlements,
    product_signal_quota_subject_key,
)
from application.product_signal_quota_store import (
    ProductSignalQuotaAdmission,
    ProductSignalQuotaStore,
    ProductSignalQuotaStoreUnavailable,
)


USER_ID = UUID("11111111-1111-4111-8111-111111111111")
GUEST_ID = UUID("22222222-2222-4222-8222-222222222222")
T0 = datetime(2026, 9, 28, 0, 0, tzinfo=UTC)


class FakeLedger:
    def __init__(self, result: ProductSignalQuotaAdmission):
        self.result = result
        self.calls = []

    def admit(self, subject_key, signal_keys, *, limit, now=None):
        self.calls.append((subject_key, tuple(signal_keys), limit, now))
        return self.result


class BrokenLedger:
    def admit(self, subject_key, signal_keys, *, limit, now=None):
        raise ProductSignalQuotaStoreUnavailable("quota unavailable")


class ShouldNotBeCalledLedger:
    def admit(self, subject_key, signal_keys, *, limit, now=None):
        raise AssertionError("Pro entitlement must bypass the quota ledger")


def _user_principal() -> ProductPrincipal:
    return ProductPrincipal(
        authenticated=True,
        user_id=USER_ID,
        email_masked="u***@example.com",
    )


def test_authenticated_subject_uses_stable_user_uuid() -> None:
    assert product_signal_quota_subject_key(_user_principal()) == f"user:{USER_ID}"


def test_guest_subject_uses_explicit_guest_uuid_without_cookie_io() -> None:
    assert (
        product_signal_quota_subject_key(
            ProductPrincipal.guest(),
            guest_id=GUEST_ID,
        )
        == f"guest:{GUEST_ID}"
    )


def test_guest_subject_requires_guest_uuid() -> None:
    with pytest.raises(ValueError, match="guest UUID"):
        product_signal_quota_subject_key(ProductPrincipal.guest())


def test_malformed_authenticated_subject_fails_closed() -> None:
    with pytest.raises(ValueError, match="user_id"):
        product_signal_quota_subject_key(ProductPrincipal(authenticated=True))


def test_public_policy_delegates_exact_limit_and_order_to_quota_store() -> None:
    ledger = FakeLedger(
        ProductSignalQuotaAdmission(
            allowed_keys=("solana:MintA", "solana:MintB"),
            newly_admitted_keys=("solana:MintA", "solana:MintB"),
            active_count=2,
            remaining=3,
        )
    )

    result = apply_detected_signal_entitlements(
        ["MintA", "MintA", "MintB", "MintC"],
        PUBLIC_ENTITLEMENTS,
        subject_key=f"guest:{GUEST_ID}",
        store=ledger,
        now=T0,
    )

    assert ledger.calls == [
        (
            f"guest:{GUEST_ID}",
            ("solana:MintA", "solana:MintB", "solana:MintC"),
            5,
            T0,
        )
    ]
    assert result == ProductSignalEntitlementAdmission(
        allowed_token_addresses=("MintA", "MintB"),
        newly_admitted_token_addresses=("MintA", "MintB"),
        quota_limit=5,
        active_count=2,
        remaining=3,
    )


def test_public_integration_with_persistent_store_admits_only_first_five(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    result = apply_detected_signal_entitlements(
        [f"Mint{index}" for index in range(1, 8)],
        PUBLIC_ENTITLEMENTS,
        subject_key=f"guest:{GUEST_ID}",
        store=store,
        now=T0,
    )

    assert result.allowed_token_addresses == tuple(f"Mint{index}" for index in range(1, 6))
    assert result.newly_admitted_token_addresses == tuple(
        f"Mint{index}" for index in range(1, 6)
    )
    assert result.quota_limit == 5
    assert result.active_count == 5
    assert result.remaining == 0


def test_public_existing_signal_reuses_slot_without_recount(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")
    subject = f"user:{USER_ID}"

    first = apply_detected_signal_entitlements(
        ["MintA", "MintB"],
        PUBLIC_ENTITLEMENTS,
        subject_key=subject,
        store=store,
        now=T0,
    )
    second = apply_detected_signal_entitlements(
        ["MintB", "MintC"],
        PUBLIC_ENTITLEMENTS,
        subject_key=subject,
        store=store,
        now=T0,
    )

    assert first.active_count == 2
    assert second.allowed_token_addresses == ("MintB", "MintC")
    assert second.newly_admitted_token_addresses == ("MintC",)
    assert second.active_count == 3
    assert second.remaining == 2


def test_pro_bypasses_quota_store_and_preserves_ordered_unique_signals() -> None:
    result = apply_detected_signal_entitlements(
        ["MintB", "MintA", "MintB", "MintC"],
        PRO_ENTITLEMENTS,
        subject_key=None,
        store=ShouldNotBeCalledLedger(),
        now=T0,
    )

    assert result == ProductSignalEntitlementAdmission(
        allowed_token_addresses=("MintB", "MintA", "MintC"),
        newly_admitted_token_addresses=(),
        quota_limit=None,
        active_count=None,
        remaining=None,
    )


def test_limited_policy_requires_subject_before_any_store_write(tmp_path) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    with pytest.raises(ValueError, match="quota subject"):
        apply_detected_signal_entitlements(
            ["MintA"],
            PUBLIC_ENTITLEMENTS,
            store=store,
            now=T0,
        )

    assert not store.path.exists()


@pytest.mark.parametrize("token_address", ["", " MintA", "MintA ", "Mint A"])
def test_invalid_token_address_is_rejected_before_quota_io(
    tmp_path,
    token_address: str,
) -> None:
    store = ProductSignalQuotaStore(tmp_path / "quota.json")

    with pytest.raises(ValueError, match="token address"):
        apply_detected_signal_entitlements(
            [token_address],
            PUBLIC_ENTITLEMENTS,
            subject_key=f"guest:{GUEST_ID}",
            store=store,
            now=T0,
        )

    assert not store.path.exists()


def test_non_string_token_address_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        apply_detected_signal_entitlements(
            ["MintA", 123],
            PRO_ENTITLEMENTS,
        )


def test_quota_store_unavailable_propagates_fail_closed() -> None:
    with pytest.raises(ProductSignalQuotaStoreUnavailable, match="quota unavailable"):
        apply_detected_signal_entitlements(
            ["MintA"],
            PUBLIC_ENTITLEMENTS,
            subject_key=f"guest:{GUEST_ID}",
            store=BrokenLedger(),
            now=T0,
        )


def test_invalid_quota_policy_is_rejected() -> None:
    invalid = ProductEntitlementPolicy(
        tier=ProductAccessTier.PUBLIC,
        trending_max_items=25,
        top_traded_max_items=25,
        detected_signals_unique_rolling_24h_max=-1,
        full_discovery=False,
        recent_24h=False,
        archive=False,
        full_context_history=False,
        telegram_alerts=False,
        essential_risk_warnings=True,
    )

    with pytest.raises(ValueError, match="non-negative integer"):
        apply_detected_signal_entitlements(
            ["MintA"],
            invalid,
            subject_key=f"guest:{GUEST_ID}",
        )


def test_unexpected_quota_key_is_rejected() -> None:
    ledger = FakeLedger(
        ProductSignalQuotaAdmission(
            allowed_keys=("solana:OtherMint",),
            newly_admitted_keys=(),
            active_count=1,
            remaining=4,
        )
    )

    with pytest.raises(ValueError, match="unexpected signal key"):
        apply_detected_signal_entitlements(
            ["MintA"],
            PUBLIC_ENTITLEMENTS,
            subject_key=f"guest:{GUEST_ID}",
            store=ledger,
            now=T0,
        )
