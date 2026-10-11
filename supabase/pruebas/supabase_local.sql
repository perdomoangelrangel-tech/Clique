-- Lo mínimo de Supabase que necesitan las migraciones, para probarlas en un Postgres local (pgserver).
-- NO se aplica en Supabase: allí estos roles y auth.uid() ya existen. Lo usa backend/datos/pg_local.py.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon nologin noinherit;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin noinherit;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role nologin noinherit bypassrls;
    end if;
end
$$;

create schema if not exists auth;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;

-- Igual que en Supabase: el id de la persona sale del JWT de la petición.
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid;
$$;
grant execute on function auth.uid() to anon, authenticated, service_role;

-- Como en Supabase, service_role puede todo en public.
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
alter default privileges in schema public grant execute on functions to service_role;
