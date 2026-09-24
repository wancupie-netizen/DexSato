from unittest.mock import patch

import pytest

from application.product_identity_runtime import (
    _default_create_client,
    build_product_auth_provider,
    build_product_identity_repository,
    product_auth_enabled,
    product_identity_configured,
    product_identity_runtime_config,
)


def _enabled_environment(**overrides):
    environment = {
        "DEXSATO_PRODUCT_AUTH_ENABLED": "true",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_public",
        "SUPABASE_SECRET_KEY": "sb_secret_server",
    }
    environment.update(overrides)
    return environment


def test_disabled_runtime_is_inert_and_requires_no_keys():
    with patch.dict("os.environ", {}, clear=True):
        assert product_auth_enabled() is False
        assert product_identity_configured() is False
        with pytest.raises(RuntimeError, match="disabled"):
            build_product_auth_provider(create_client=lambda url, key: object())


def test_runtime_rejects_invalid_flags_placeholders_and_legacy_key_shapes():
    with patch.dict("os.environ", {"DEXSATO_PRODUCT_AUTH_ENABLED": "sometimes"}, clear=True):
        with pytest.raises(RuntimeError, match="boolean"):
            product_identity_runtime_config()
    with patch.dict("os.environ", _enabled_environment(SUPABASE_SECRET_KEY="your-secret"), clear=True):
        assert product_identity_configured() is False
    with patch.dict("os.environ", _enabled_environment(SUPABASE_SECRET_KEY="legacy-service-role"), clear=True):
        with pytest.raises(RuntimeError, match="secret key"):
            product_identity_runtime_config()


def test_runtime_uses_publishable_key_only_for_auth_and_secret_only_for_repository():
    calls = []

    class Client:
        auth = object()
        def table(self, name): raise AssertionError("not used")

    def create_client(url, key):
        calls.append((url, key))
        return Client()

    with patch.dict("os.environ", _enabled_environment(), clear=True):
        config = product_identity_runtime_config()
        provider = build_product_auth_provider(create_client=create_client)
        assert calls == []
        provider._client()
        repository = build_product_identity_repository(create_client=create_client)

    assert calls == [
        ("https://project.supabase.co", "sb_publishable_public"),
        ("https://project.supabase.co", "sb_secret_server"),
    ]
    assert "sb_publishable_public" not in repr(config)
    assert "sb_secret_server" not in repr(config)
    assert repository is not None


def test_default_supabase_client_disables_provider_session_persistence():
    sentinel = object()
    with patch("supabase.create_client", return_value=sentinel) as create_client:
        assert _default_create_client("https://project.supabase.co", "sb_publishable_public") is sentinel

    options = create_client.call_args.kwargs["options"]
    assert hasattr(options, "storage")
    assert options.persist_session is False
    assert options.auto_refresh_token is False
