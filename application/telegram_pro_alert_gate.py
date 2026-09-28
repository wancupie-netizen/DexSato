"""Server-only Pro admission immediately before customer Telegram delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID

from application.product_entitlement_policy import ProductAccessTier, ProductEntitlementPolicy
from application.product_identity_models import ProductPrincipal


@dataclass(frozen=True, slots=True)
class TelegramCustomerLink:
    user_id: UUID
    telegram_user_id: int
    chat_id: int


class TelegramCustomerLinkReader(Protocol):
    def get_active_for_user(self, *, user_id: UUID) -> TelegramCustomerLink | None: ...


class ProductEntitlementReader(Protocol):
    def resolve(self, principal: ProductPrincipal) -> ProductEntitlementPolicy: ...


class TelegramProAlertGate:
    def __init__(self, links: TelegramCustomerLinkReader, entitlements: ProductEntitlementReader) -> None:
        self._links = links
        self._entitlements = entitlements

    def recipient_for(self, *, user_id: UUID) -> TelegramCustomerLink | None:
        """Fail closed on invalid identity, stale link, or entitlement I/O failure."""
        if not isinstance(user_id, UUID):
            return None
        try:
            link = self._links.get_active_for_user(user_id=user_id)
            if not isinstance(link, TelegramCustomerLink) or link.user_id != user_id:
                return None
            if (type(link.telegram_user_id) is not int or type(link.chat_id) is not int
                    or link.telegram_user_id <= 0 or link.chat_id != link.telegram_user_id):
                return None
            policy = self._entitlements.resolve(ProductPrincipal(authenticated=True, user_id=user_id))
            if (not isinstance(policy, ProductEntitlementPolicy)
                    or policy.tier is not ProductAccessTier.PRO
                    or policy.telegram_alerts is not True):
                return None
            return link
        except Exception:
            return None

    def deliver(
        self, *, user_id: UUID, message: str,
        send: Callable[..., object],
    ) -> bool:
        """Authorize immediately before calling the customer transport."""
        if not isinstance(message, str) or not message.strip():
            return False
        recipient = self.recipient_for(user_id=user_id)
        if recipient is None:
            return False
        send(chat_id=recipient.chat_id, message=message)
        return True