begin;

create table if not exists public.dexsato_product_users (
    id uuid primary key,
    auth_provider text not null check (auth_provider <> ''),
    auth_subject text not null check (auth_subject <> ''),
    email_normalized text not null check (
        email_normalized = lower(trim(email_normalized))
        and length(email_normalized) <= 254
    ),
    created_at timestamptz not null,
    last_login_at timestamptz not null,
    disabled_at timestamptz null,
    unique (auth_provider, auth_subject),
    unique (email_normalized)
);

create table if not exists public.dexsato_product_sessions (
    id uuid primary key,
    user_id uuid not null references public.dexsato_product_users(id) on delete cascade,
    token_hash char(64) not null unique check (token_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null,
    expires_at timestamptz not null,
    last_seen_at timestamptz not null,
    revoked_at timestamptz null,
    check (expires_at > created_at)
);

create index if not exists dexsato_product_sessions_user_id_idx
    on public.dexsato_product_sessions (user_id);

create index if not exists dexsato_product_sessions_expires_at_idx
    on public.dexsato_product_sessions (expires_at);

alter table public.dexsato_product_users enable row level security;
alter table public.dexsato_product_sessions enable row level security;

revoke all on table public.dexsato_product_users from anon, authenticated;
revoke all on table public.dexsato_product_sessions from anon, authenticated;
grant select, insert, update, delete on table public.dexsato_product_users to service_role;
grant select, insert, update, delete on table public.dexsato_product_sessions to service_role;

commit;
