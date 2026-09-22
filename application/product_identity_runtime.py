"""Feature-gated construction of separate Supabase identity clients."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import os
from typing import Any
from urllib.parse import urlparse

from application.product_identity_service import ProductIdentityService
from application.supabase_product_auth_provider import SupabaseProductAuthProvider
from application.supabase_product_identity_repository import (
    SupabaseProductIdentityRepository,
)


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"", "0", "false", "no", "off"}
_PLACEHOLDER_PREFIXES = ("your-", "replace-with-", "changeme")


@dataclass(frozen=True, slots=True)
class ProductIdentityRuntimeConfig:
    enabled: bool
    supabase_url: str
    publishable_key: str = field(repr=False)
    secret_key: str = field(repr=False)


def product_auth_enabled() -> bool:
    value = os.getenv("DEXSATO_PRODUCT_AUTH_ENABLED", "false").strip().casefold()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise RuntimeError("DEXSATO_PRODUCT_AUTH_ENABLED must be a boolean value.")


def _configured_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.casefold().startswith(_PLACEHOLDER_PREFIXES):
        raise RuntimeError(f"{name} is required when product authentication is enabled.")
    return value


def product_identity_runtime_config() -> ProductIdentityRuntimeConfig:
    enabled = product_auth_enabled()
    if not enabled:
        return ProductIdentityRuntimeConfig(False, "", "", "")

    url = _configured_value("SUPABASE_URL")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError("SUPABASE_URL must be an HTTPS URL without embedded credentials.")

    publishable_key = _configured_value("SUPABASE_PUBLISHABLE_KEY")
    secret_key = _configured_value("SUPABASE_SECRET_KEY")
    if not publishable_key.startswith("sb_publishable_"):
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY must use a publishable key.")
    if not secret_key.startswith("sb_secret_"):
        raise RuntimeError("SUPABASE_SECRET_KEY must use a secret key.")
    if publishable_key == secret_key:
        raise RuntimeError("Supabase product identity keys must be distinct.")
    return ProductIdentityRuntimeConfig(True, url, publishable_key, secret_key)


def product_identity_configured() -> bool:
    try:
        return product_identity_runtime_config().enabled
    except RuntimeError:
        return False


def _default_create_client(url: str, key: str) -> Any:
    from supabase import create_client
    from supabase.lib.client_options import ClientOptions

    return create_client(
        url,
        key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def build_product_auth_provider(
    *,
    create_client: Callable[[str, str], Any] = _default_create_client,
) -> SupabaseProductAuthProvider:
    config = product_identity_runtime_config()
    if not config.enabled:
        raise RuntimeError("Product authentication is disabled.")
    return SupabaseProductAuthProvider(
        lambda: create_client(config.supabase_url, config.publishable_key)
    )


def build_product_identity_repository(
    *,
    create_client: Callable[[str, str], Any] = _default_create_client,
) -> SupabaseProductIdentityRepository:
    config = product_identity_runtime_config()
    if not config.enabled:
        raise RuntimeError("Product authentication is disabled.")
    return SupabaseProductIdentityRepository(
        create_client(config.supabase_url, config.secret_key)
    )


def build_product_identity_service(
    *,
    create_client: Callable[[str, str], Any] = _default_create_client,
) -> ProductIdentityService:
    return ProductIdentityService(
        build_product_identity_repository(create_client=create_client)
    )
