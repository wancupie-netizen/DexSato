"""Provider-neutral detected-signal quota enforcement for DexSato entitlements."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.product_entitlement_policy import ProductEntitlementPolicy
from application.product_identity_models import ProductPrincipal
from application.product_signal_quota_store import (
    ProductSignalQuotaAdmission,
    ProductSignalQuotaStore,
)


class ProductSignalQuotaLedger(Protocol):
    """Minimal ledger contract required by entitlement enforcement."""

    def admit(
        self,
        subject_key: str,
        signal_keys: Iterable[str],
        *,
        limit: int,
        now: datetime | None = None,
    ) -> ProductSignalQuotaAdmission: ...


@dataclass(frozen=True, slots=True)
class ProductSignalEntitlementAdmission:
    """Detected-signal projection after applying the resolved entitlement policy."""

    allowed_token_addresses: tuple[str, ...]
    newly_admitted_token_addresses: tuple[str, ...]
    quota_limit: int | None
    active_count: int | None
    remaining: int | None


def product_signal_quota_subject_key(
    principal: ProductPrincipal,
    *,
    guest_id: UUID | None = None,
) -> str:
    """Return the stable quota subject without reading or mutating HTTP cookies."""

    if not isinstance(principal, ProductPrincipal):
        raise TypeError("principal must be a ProductPrincipal")

    if principal.authenticated:
        if principal.user_id is None:
            raise ValueError("authenticated quota subject requires a user_id")
        return f"user:{principal.user_id}"

    if not isinstance(guest_id, UUID):
        raise ValueError("guest quota subject requires a guest UUID")
    return f"guest:{guest_id}"


def _ordered_unique_token_addresses(token_addresses: Iterable[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()

    for value in token_addresses:
        if not isinstance(value, str):
            raise TypeError("detected signal token address must be a string")
        token_address = value.strip()
        if (
            not token_address
            or token_address != value
            or any(character.isspace() for character in token_address)
            or len(token_address) > 128
        ):
            raise ValueError("detected signal token address is invalid")
        if token_address in seen:
            continue
        seen.add(token_address)
        ordered.append(token_address)

    return tuple(ordered)


def apply_detected_signal_entitlements(
    token_addresses: Iterable[str],
    policy: ProductEntitlementPolicy,
    *,
    subject_key: str | None = None,
    store: ProductSignalQuotaLedger | None = None,
    now: datetime | None = None,
) -> ProductSignalEntitlementAdmission:
    """Apply Public rolling quota or preserve all unique Pro detected signals."""

    if not isinstance(policy, ProductEntitlementPolicy):
        raise TypeError("policy must be a ProductEntitlementPolicy")

    ordered_addresses = _ordered_unique_token_addresses(token_addresses)
    quota_limit = policy.detected_signals_unique_rolling_24h_max

    if quota_limit is None:
        return ProductSignalEntitlementAdmission(
            allowed_token_addresses=ordered_addresses,
            newly_admitted_token_addresses=(),
            quota_limit=None,
            active_count=None,
            remaining=None,
        )

    if (
        isinstance(quota_limit, bool)
        or not isinstance(quota_limit, int)
        or quota_limit < 0
    ):
        raise ValueError(
            "detected signal quota limit must be a non-negative integer or None"
        )
    if not isinstance(subject_key, str) or not subject_key.strip():
        raise ValueError("limited detected signals require a quota subject")

    ledger = store if store is not None else ProductSignalQuotaStore()
    signal_keys = tuple(f"solana:{address}" for address in ordered_addresses)
    admission = ledger.admit(
        subject_key,
        signal_keys,
        limit=quota_limit,
        now=now,
    )
    if not isinstance(admission, ProductSignalQuotaAdmission):
        raise TypeError("quota ledger returned an invalid admission result")

    by_key = {
        f"solana:{address}": address
        for address in ordered_addresses
    }
    try:
        allowed_addresses = tuple(by_key[key] for key in admission.allowed_keys)
        newly_admitted_addresses = tuple(
            by_key[key] for key in admission.newly_admitted_keys
        )
    except KeyError as error:
        raise ValueError("quota ledger returned an unexpected signal key") from error

    return ProductSignalEntitlementAdmission(
        allowed_token_addresses=allowed_addresses,
        newly_admitted_token_addresses=newly_admitted_addresses,
        quota_limit=quota_limit,
        active_count=admission.active_count,
        remaining=admission.remaining,
    )
