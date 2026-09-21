from pathlib import Path


SCHEMA_PATH = Path(__file__).parents[1] / "database" / "migrations" / "001_product_identity.sql"


def test_product_identity_schema_is_server_only_and_constrained() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8").lower()

    required_markers = (
        "create table if not exists public.dexsato_product_users",
        "unique (auth_provider, auth_subject)",
        "unique (email_normalized)",
        "create table if not exists public.dexsato_product_sessions",
        "token_hash char(64) not null unique",
        "check (expires_at > created_at)",
        "enable row level security",
        "revoke all on table public.dexsato_product_users from anon, authenticated",
        "revoke all on table public.dexsato_product_sessions from anon, authenticated",
        "to service_role",
    )
    for marker in required_markers:
        assert marker in sql


def test_schema_never_stores_raw_session_token_or_product_tier() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8").lower()

    assert "raw_token" not in sql
    assert "session_token text" not in sql
    assert "is_pro" not in sql
    assert "access_tier" not in sql
    assert "subscription_tier" not in sql
