-- Esquema v1 de Clique (etapa A de ADR-006). Guarda lo que hoy guarda backend/store.py en db.json:
-- perfiles, círculos y miembros, cuentas, el libro, mercados y posiciones, rondas de casino y el cierre semanal.
-- El dinero va en centavos enteros (bigint), nunca en float (ADR-003). Lo que falta del modelo está en
-- docs/datos/modelo-actual.md como "ronda 2".
--
-- Se escribe para Supabase: usa auth.uid() y los roles anon, authenticated y service_role. Las pruebas locales
-- (pgserver) crean antes un sustituto mínimo de eso: supabase/pruebas/supabase_local.sql.

-- ---------------------------------------------------------------- personas y círculos

create table public.profiles (
    id          uuid primary key,                      -- el id de la persona en auth.users (Supabase Auth, ronda 2)
    legacy_id   text unique,                           -- el id de 12 caracteres del archivo, para el importador
    username    text not null,
    look        jsonb not null default '{}'::jsonb,    -- lo que se ve en las listas: avatar, marco, insignia, color
    bio         text not null default '',
    suspended   boolean not null default false,
    deleted_at  timestamptz,
    created_at  timestamptz not null default now(),
    constraint profiles_username_ok check (username ~ '^[A-Za-z0-9_]{3,20}$')
);
create unique index profiles_username_lower on public.profiles (lower(username));

create table public.circles (
    id           uuid primary key default gen_random_uuid(),
    legacy_id    text unique,
    name         text not null check (char_length(name) between 2 and 40),
    description  text not null default '' check (char_length(description) <= 200),
    emoji        text not null default '👥',
    visibility   text not null default 'private' check (visibility in ('private', 'public')),
    invite_code  text not null unique,
    owner_id     uuid not null references public.profiles (id),
    created_at   timestamptz not null default now()
);

create table public.circle_members (
    circle_id  uuid not null references public.circles (id) on delete cascade,
    user_id    uuid not null references public.profiles (id) on delete cascade,
    joined_at  timestamptz not null default now(),
    primary key (circle_id, user_id)
);
create index circle_members_user on public.circle_members (user_id);

-- ---------------------------------------------------------------- cuentas y libro (ADR-003, ADR-004)

-- Tres cuentas por persona y las del sistema (la casa, el pozo de cada mercado, lo que entra de fuera).
-- chips (fichas compradas, D3) existe pero nace apagada: el libro no la mueve mientras enabled = false.
create table public.accounts (
    id           bigint generated always as identity primary key,
    owner_id     uuid references public.profiles (id),
    kind         text not null check (kind in ('weekly', 'accumulated', 'chips', 'system')),
    system_code  text unique,                          -- 'casino', 'market', 'external'... solo para kind = 'system'
    enabled      boolean not null default true,
    balance      bigint not null default 0,            -- centavos; lo mantiene post_transaction, nadie más
    created_at   timestamptz not null default now(),
    constraint accounts_owner_by_kind check (
        (kind = 'system' and owner_id is null and system_code is not null)
        or (kind <> 'system' and owner_id is not null and system_code is null)),
    constraint accounts_person_not_negative check (kind = 'system' or balance >= 0),
    constraint accounts_one_per_kind unique (owner_id, kind)
);

create table public.ledger_transactions (
    id               bigint generated always as identity primary key,
    idempotency_key  text not null unique check (char_length(idempotency_key) between 1 and 200),
    reason           text not null check (char_length(reason) between 1 and 80),
    request_hash     text not null,                    -- md5 de las líneas: la misma clave con otras líneas se rechaza
    meta             jsonb not null default '{}'::jsonb,   -- ref, note, external, legacy...
    created_at       timestamptz not null default now()
);

create table public.ledger_entries (
    id              bigint generated always as identity primary key,
    transaction_id  bigint not null references public.ledger_transactions (id),
    account_id      bigint not null references public.accounts (id),
    amount          bigint not null check (amount <> 0),   -- centavos; + entra a la cuenta, - sale
    balance_after   bigint not null,
    created_at      timestamptz not null default now()
);
create index ledger_entries_account on public.ledger_entries (account_id, id);
create index ledger_entries_transaction on public.ledger_entries (transaction_id);

create table public.app_settings (
    key    text primary key,
    value  jsonb not null
);
insert into public.app_settings (key, value) values ('purchases_enabled', 'false'::jsonb);   -- D3: compra apagada

-- ---------------------------------------------------------------- mercados

create table public.markets (
    id           uuid primary key default gen_random_uuid(),
    legacy_id    text unique,
    circle_id    uuid references public.circles (id),  -- null: mercado de todo el sitio
    creator_id   uuid not null references public.profiles (id),
    question     text not null check (char_length(question) between 5 and 160),
    description  text not null default '',
    category     text not null default 'General',
    emoji        text not null default '',
    outcomes     text[] not null check (cardinality(outcomes) between 2 and 12),
    liquidity_b  numeric not null check (liquidity_b > 0),           -- el parámetro b del LMSR (no es dinero)
    shares_q     numeric[] not null,                                 -- acciones vendidas por resultado (no es dinero)
    status       text not null default 'open' check (status in ('open', 'closed', 'resolved', 'void')),
    winner       integer,
    volume       bigint not null default 0,                          -- centavos apostados
    closes_at    timestamptz,
    created_at   timestamptz not null default now(),
    resolved_at  timestamptz,
    constraint markets_q_matches check (cardinality(shares_q) = cardinality(outcomes)),
    constraint markets_winner_ok check (winner is null or (winner >= 0 and winner < cardinality(outcomes)))
);
create index markets_circle on public.markets (circle_id);

create table public.market_positions (
    market_id  uuid not null references public.markets (id) on delete cascade,
    user_id    uuid not null references public.profiles (id),
    token      text not null check (token ~ '^[yn][0-9]{1,2}$'),     -- y0 = "sí" al resultado 0, n1 = "no" al 1
    shares     numeric not null check (shares >= 0),
    invested   bigint not null default 0,                            -- centavos
    settled    boolean not null default false,
    payout     bigint,                                               -- centavos, al liquidar
    primary key (market_id, user_id, token)
);
create index market_positions_user on public.market_positions (user_id);

create table public.market_trades (
    id          bigint generated always as identity primary key,
    market_id   uuid not null references public.markets (id) on delete cascade,
    user_id     uuid not null references public.profiles (id),
    kind        text not null check (kind in ('buy', 'sell', 'withdraw', 'refund')),
    token       text not null,
    shares      numeric not null,
    amount      bigint not null,                                     -- centavos
    price       numeric not null,                                    -- precio promedio, 0 a 1 (no es dinero)
    created_at  timestamptz not null default now()
);
create index market_trades_market on public.market_trades (market_id, id);

-- ---------------------------------------------------------------- casino

create table public.casino_rounds (
    id           uuid primary key default gen_random_uuid(),
    legacy_id    text,
    user_id      uuid not null references public.profiles (id),
    account      text not null check (account in ('weekly', 'accumulated', 'chips')),
    game         text not null,
    status       text not null check (status in ('active', 'finished')),
    bet          bigint not null check (bet >= 0),                   -- centavos
    payout       bigint,                                             -- centavos; null mientras sigue
    multiplier   numeric,
    detail       text not null default '',
    state        jsonb,                                              -- la ronda en curso (cartas, minas...): solo el servidor la lee
    created_at   timestamptz not null default now(),
    finished_at  timestamptz,
    constraint casino_rounds_finished check ((status = 'finished') = (payout is not null))
);
create index casino_rounds_user on public.casino_rounds (user_id, created_at desc);
create unique index casino_rounds_one_active on public.casino_rounds (user_id, account, game) where status = 'active';

-- ---------------------------------------------------------------- cierre semanal (ECONOMY.md §2 y §12)

create table public.week_snapshots (                                 -- lo que tenía cada persona al cerrar la semana
    week     date not null,                                          -- el lunes que la empieza
    user_id  uuid not null references public.profiles (id),
    holding  bigint not null,                                        -- centavos, neto de deudas
    primary key (week, user_id)
);

create table public.week_closes (                                    -- la tabla final de un círculo, guardada para siempre
    circle_id     uuid not null references public.circles (id) on delete cascade,
    week          date not null,
    finalized_at  timestamptz not null,
    reason        text not null check (reason in ('last', 'minimum')),
    loser_ids     uuid[] not null default '{}',
    punishment    jsonb,
    note          text not null default '',
    awards        jsonb not null default '[]'::jsonb,
    rules         jsonb not null default '{}'::jsonb,                -- las reglas que aplicaron esa semana
    active        integer not null default 0,
    scale         numeric not null default 1,
    served        boolean not null default false,
    primary key (circle_id, week)
);

create table public.week_standings (
    circle_id    uuid not null,
    week         date not null,
    user_id      uuid not null references public.profiles (id),
    position     integer not null check (position >= 1),
    value        bigint not null,                                    -- centavos al cerrar
    start_value  bigint not null,                                    -- centavos al empezar
    delta        bigint not null,                                    -- centavos de desempeño
    moves        integer not null default 0,
    active       boolean not null,
    out_by_minimum boolean not null default false,
    reward_note  text not null default '',
    requirements jsonb not null default '{}'::jsonb,
    primary key (circle_id, week, user_id),
    foreign key (circle_id, week) references public.week_closes (circle_id, week) on delete cascade
);

create table public.week_rewards (
    circle_id       uuid not null,
    week            date not null,
    user_id         uuid not null references public.profiles (id),
    amount          bigint not null check (amount > 0),              -- centavos
    position        integer not null,
    paid            boolean not null default false,
    transaction_id  bigint references public.ledger_transactions (id),
    primary key (circle_id, week, user_id),
    foreign key (circle_id, week) references public.week_closes (circle_id, week) on delete cascade,
    constraint week_rewards_paid_has_tx check (not paid or transaction_id is not null)
);
