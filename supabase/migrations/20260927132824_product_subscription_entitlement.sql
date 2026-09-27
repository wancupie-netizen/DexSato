begin;

create table if not exists public.dexsato_product_subscriptions (
    id uuid primary key,
    user_id uuid not null unique references public.dexsato_product_users(id) on delete cascade,
    plan_code text not null check (plan_code in ('founder_pro', 'pro')),
    status text not null check (status in ('active', 'inactive', 'cancelled', 'expired')),
    access_starts_at timestamptz not null,
    access_ends_at timestamptz null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (access_ends_at is null or access_ends_at > access_starts_at),
    check (updated_at >= created_at)
);

create index if not exists dexsato_product_subscriptions_status_idx
    on public.dexsato_product_subscriptions (status);

alter table public.dexsato_product_subscriptions enable row level security;

revoke all on table public.dexsato_product_subscriptions from anon, authenticated;
grant select, insert, update, delete on table public.dexsato_product_subscriptions to service_role;

commit;
