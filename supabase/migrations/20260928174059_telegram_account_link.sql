begin;

create table if not exists public.dexsato_telegram_link_requests (
    token_hash char(64) primary key check (token_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid not null references public.dexsato_product_users(id) on delete cascade,
    created_at timestamptz not null,
    expires_at timestamptz not null,
    consumed_at timestamptz null,
    check (expires_at > created_at and expires_at <= created_at + interval '10 minutes')
);

create index if not exists dexsato_telegram_link_requests_user_id_idx
    on public.dexsato_telegram_link_requests(user_id);

create table if not exists public.dexsato_telegram_account_links (
    user_id uuid primary key references public.dexsato_product_users(id) on delete cascade,
    telegram_user_id bigint not null unique check (telegram_user_id > 0),
    chat_id bigint not null unique check (chat_id > 0 and chat_id = telegram_user_id),
    linked_at timestamptz not null
);

alter table public.dexsato_telegram_link_requests enable row level security;
alter table public.dexsato_telegram_account_links enable row level security;
revoke all on table public.dexsato_telegram_link_requests from anon, authenticated;
revoke all on table public.dexsato_telegram_account_links from anon, authenticated;
grant select, insert, update, delete on table public.dexsato_telegram_link_requests to service_role;
grant select, insert, update, delete on table public.dexsato_telegram_account_links to service_role;

-- Atomic redemption ensures a guessed or replayed code cannot bind an account.
-- Execute only with the server's secret-key client; no customer role can call it.
create or replace function public.dexsato_redeem_telegram_link(
    p_token_hash text,
    p_telegram_user_id bigint,
    p_chat_id bigint
) returns boolean
language plpgsql security invoker set search_path = ''
as $$
declare
    request_row public.dexsato_telegram_link_requests%rowtype;
    inserted_rows integer;
begin
    if p_token_hash is null or p_token_hash !~ '^[0-9a-f]{64}$'
       or p_telegram_user_id is null or p_telegram_user_id <= 0
       or p_chat_id is null or p_chat_id <= 0 or p_chat_id <> p_telegram_user_id then
        return false;
    end if;

    select r.* into request_row
    from public.dexsato_telegram_link_requests as r
    join public.dexsato_product_users as u on u.id = r.user_id
    where r.token_hash = p_token_hash and r.consumed_at is null
      and r.expires_at > now() and u.disabled_at is null
    for update of r;

    if not found then
        return false;
    end if;

    insert into public.dexsato_telegram_account_links
        (user_id, telegram_user_id, chat_id, linked_at)
    values (request_row.user_id, p_telegram_user_id, p_chat_id, now())
    on conflict do nothing;
    get diagnostics inserted_rows = row_count;
    if inserted_rows <> 1 then
        return false;
    end if;

    update public.dexsato_telegram_link_requests
    set consumed_at = now()
    where token_hash = p_token_hash;
    return true;
end;
$$;

revoke all on function public.dexsato_redeem_telegram_link(text, bigint, bigint) from public, anon, authenticated;
grant execute on function public.dexsato_redeem_telegram_link(text, bigint, bigint) to service_role;

commit;
