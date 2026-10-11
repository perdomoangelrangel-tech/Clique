-- Seguridad por fila en cada tabla. Regla general: el navegador (anon, authenticated) solo LEE, y solo lo suyo o lo de
-- sus círculos. Nadie escribe desde el navegador: no hay ninguna política de insert, update ni delete, y el dinero solo
-- se mueve con post_transaction (ADR-003). El servidor usa service_role, que en Supabase se salta RLS.

-- ¿La persona que llama es miembro de este círculo? security definer para no caer en la recursión de RLS al leer
-- circle_members desde una política de circle_members.
create or replace function public.is_circle_member(p_circle uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (select 1 from circle_members m where m.circle_id = p_circle and m.user_id = auth.uid());
$$;

-- ¿Comparte algún círculo con esta persona?
create or replace function public.shares_circle_with(p_user uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (select 1 from circle_members a join circle_members b on a.circle_id = b.circle_id
                    where a.user_id = auth.uid() and b.user_id = p_user);
$$;

-- ¿La cuenta es de quien llama?
create or replace function public.owns_account(p_account bigint)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (select 1 from accounts a where a.id = p_account and a.owner_id = auth.uid());
$$;

revoke all on function public.is_circle_member(uuid) from public;
revoke all on function public.shares_circle_with(uuid) from public;
revoke all on function public.owns_account(bigint) from public;
grant execute on function public.is_circle_member(uuid) to anon, authenticated, service_role;
grant execute on function public.shares_circle_with(uuid) to anon, authenticated, service_role;
grant execute on function public.owns_account(bigint) to anon, authenticated, service_role;

alter table public.profiles            enable row level security;
alter table public.circles             enable row level security;
alter table public.circle_members      enable row level security;
alter table public.accounts            enable row level security;
alter table public.ledger_transactions enable row level security;
alter table public.ledger_entries      enable row level security;
alter table public.app_settings        enable row level security;
alter table public.markets             enable row level security;
alter table public.market_positions    enable row level security;
alter table public.market_trades       enable row level security;
alter table public.casino_rounds       enable row level security;
alter table public.week_snapshots      enable row level security;
alter table public.week_closes         enable row level security;
alter table public.week_standings      enable row level security;
alter table public.week_rewards        enable row level security;

-- Sin escritura desde el navegador, ni siquiera por error de una política futura: se quitan los permisos de tabla.
revoke insert, update, delete, truncate on all tables in schema public from anon, authenticated;
grant select on all tables in schema public to authenticated;
revoke select on all tables in schema public from anon;

-- Personas: uno mismo y quien comparte un círculo.
create policy profiles_read on public.profiles for select to authenticated
    using (id = auth.uid() or public.shares_circle_with(id));

-- Círculos y miembros: solo los miembros.
create policy circles_read on public.circles for select to authenticated
    using (public.is_circle_member(id));
create policy circle_members_read on public.circle_members for select to authenticated
    using (public.is_circle_member(circle_id));

-- Cuentas y libro: solo las cuentas propias y las transacciones que las tocan.
create policy accounts_read on public.accounts for select to authenticated
    using (owner_id = auth.uid());
create policy ledger_entries_read on public.ledger_entries for select to authenticated
    using (public.owns_account(account_id));
create policy ledger_transactions_read on public.ledger_transactions for select to authenticated
    using (exists (select 1 from public.ledger_entries e
                    where e.transaction_id = ledger_transactions.id and public.owns_account(e.account_id)));

-- Ajustes: los lee cualquiera con sesión (por ejemplo, si la compra está encendida).
create policy app_settings_read on public.app_settings for select to authenticated using (true);

-- Mercados: los de un círculo, sus miembros; los del sitio (circle_id null), cualquiera con sesión.
create policy markets_read on public.markets for select to authenticated
    using (circle_id is null or public.is_circle_member(circle_id));
-- Posiciones: solo las propias.
create policy market_positions_read on public.market_positions for select to authenticated
    using (user_id = auth.uid());
-- Operaciones: quien puede ver el mercado (el historial de un mercado es público para su círculo).
create policy market_trades_read on public.market_trades for select to authenticated
    using (exists (select 1 from public.markets m
                    where m.id = market_trades.market_id
                      and (m.circle_id is null or public.is_circle_member(m.circle_id))));

-- Casino: solo las rondas propias. El estado de una ronda en curso (state) tampoco lo ve su dueño: lo quita la vista
-- que use la interfaz en la etapa B; aquí la columna se cierra al navegador.
create policy casino_rounds_read on public.casino_rounds for select to authenticated
    using (user_id = auth.uid());
revoke select on public.casino_rounds from authenticated;
grant select (id, user_id, account, game, status, bet, payout, multiplier, detail, created_at, finished_at)
    on public.casino_rounds to authenticated;

-- Cierre semanal: lo propio, y lo de los círculos de uno.
create policy week_snapshots_read on public.week_snapshots for select to authenticated
    using (user_id = auth.uid());
create policy week_closes_read on public.week_closes for select to authenticated
    using (public.is_circle_member(circle_id));
create policy week_standings_read on public.week_standings for select to authenticated
    using (public.is_circle_member(circle_id));
create policy week_rewards_read on public.week_rewards for select to authenticated
    using (public.is_circle_member(circle_id));
