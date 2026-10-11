-- El libro de doble partida en SQL (ADR-003). Es lo único que mueve dinero: ninguna otra cosa escribe en
-- accounts.balance, ledger_transactions ni ledger_entries. Lo llama el servidor (service_role), nunca el navegador.
--
-- post_transaction(idempotency_key, reason, lines, meta) -> id de la transacción
--   lines: [{"account": <accounts.id>, "amount": <centavos, entero distinto de 0>}, ...]
--   Reglas, en este orden:
--     1. la misma clave con las mismas líneas devuelve la transacción que ya existe y no mueve nada;
--        la misma clave con otras líneas se rechaza (idempotency_conflict);
--     2. al menos dos líneas, montos enteros distintos de cero, cada cuenta una sola vez;
--     3. las líneas suman cero;
--     4. cada cuenta existe y está encendida (chips nace apagada, D3);
--     5. se toman los candados de las cuentas en orden de id (así dos pagos cruzados no se bloquean entre sí);
--     6. ninguna cuenta de persona queda negativa.
--   Los errores salen con SQLSTATE P0001 y un mensaje que empieza con un código estable en inglés.

create or replace function public.post_transaction(
    p_idempotency_key text,
    p_reason text,
    p_lines jsonb,
    p_meta jsonb default '{}'::jsonb
) returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_lines    jsonb;
    v_hash     text;
    v_tx       bigint;
    v_prior    text;
    v_n        integer;
    v_sum      numeric;
    v_acct     record;
    v_line     record;
    v_new      bigint;
begin
    if p_idempotency_key is null or char_length(p_idempotency_key) = 0 then
        raise exception 'invalid_idempotency_key: falta la clave de idempotencia';
    end if;
    if p_reason is null or char_length(p_reason) = 0 then
        raise exception 'invalid_reason: falta la razón';
    end if;
    if p_lines is null or jsonb_typeof(p_lines) <> 'array' then
        raise exception 'invalid_lines: las líneas deben ser una lista';
    end if;

    -- La huella de la petición: las líneas ordenadas por cuenta, para que el orden en que llegan no importe.
    select coalesce(jsonb_agg(jsonb_build_object('account', l->'account', 'amount', l->'amount')
                              order by (l->>'account'), (l->>'amount')), '[]'::jsonb)
      into v_lines
      from jsonb_array_elements(p_lines) as l;
    v_hash := md5(p_reason || '|' || v_lines::text);

    -- 1. Idempotencia. Si otra sesión está insertando la misma clave, este insert espera a que termine.
    insert into ledger_transactions (idempotency_key, reason, request_hash, meta)
    values (p_idempotency_key, p_reason, v_hash, coalesce(p_meta, '{}'::jsonb))
    on conflict (idempotency_key) do nothing
    returning id into v_tx;
    if v_tx is null then
        select id, request_hash into v_tx, v_prior from ledger_transactions where idempotency_key = p_idempotency_key;
        if v_prior <> v_hash then
            raise exception 'idempotency_conflict: la clave % ya se usó para otro movimiento', p_idempotency_key;
        end if;
        return v_tx;
    end if;

    -- 2. Forma de las líneas.
    select count(*), count(distinct l->>'account')
      into v_n, v_sum
      from jsonb_array_elements(p_lines) as l;
    if v_n < 2 then
        raise exception 'invalid_lines: una transacción necesita al menos dos líneas';
    end if;
    if v_sum <> v_n then
        raise exception 'invalid_lines: cada cuenta puede aparecer una sola vez';
    end if;
    if exists (select 1 from jsonb_array_elements(p_lines) as l
                where jsonb_typeof(l->'account') <> 'number' or jsonb_typeof(l->'amount') <> 'number'
                   or (l->>'amount')::numeric <> trunc((l->>'amount')::numeric)
                   or (l->>'amount')::numeric = 0
                   or abs((l->>'amount')::numeric) > 9000000000000000000) then
        raise exception 'invalid_lines: cada línea lleva una cuenta y un monto entero de centavos distinto de cero';
    end if;

    -- 3. Suma cero.
    select sum((l->>'amount')::numeric) into v_sum from jsonb_array_elements(p_lines) as l;
    if v_sum <> 0 then
        raise exception 'unbalanced: las líneas suman % centavos y deben sumar cero', v_sum;
    end if;

    -- 4 y 5. Candados en orden fijo, y que cada cuenta exista y esté encendida.
    select count(*) into v_n
      from (select a.id from accounts a
             where a.id in (select (l->>'account')::bigint from jsonb_array_elements(p_lines) as l)
             order by a.id
               for update) as locked;
    if v_n <> jsonb_array_length(p_lines) then
        raise exception 'unknown_account: una de las cuentas no existe';
    end if;
    if exists (select 1 from accounts a
                where a.id in (select (l->>'account')::bigint from jsonb_array_elements(p_lines) as l)
                  and not a.enabled) then
        raise exception 'account_disabled: una de las cuentas está apagada';
    end if;

    -- 6. Asentar, en el mismo orden, sin dejar negativa una cuenta de persona.
    for v_line in
        select (l->>'account')::bigint as account, (l->>'amount')::bigint as amount
          from jsonb_array_elements(p_lines) as l
         order by 1
    loop
        select id, kind, balance into v_acct from accounts where id = v_line.account;
        v_new := v_acct.balance + v_line.amount;
        if v_acct.kind <> 'system' and v_new < 0 then
            raise exception 'insufficient_funds: la cuenta % tiene % centavos y se le quieren quitar %',
                v_acct.id, v_acct.balance, -v_line.amount;
        end if;
        update accounts set balance = v_new where id = v_acct.id;
        insert into ledger_entries (transaction_id, account_id, amount, balance_after)
        values (v_tx, v_acct.id, v_line.amount, v_new);
    end loop;

    return v_tx;
end;
$$;

-- El saldo de una cuenta, en centavos, sumando el libro (no el saldo guardado): así se audita el uno con el otro.
create or replace function public.balance_of(p_account bigint)
returns bigint
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select coalesce(sum(e.amount), 0)::bigint from ledger_entries e where e.account_id = p_account;
$$;

-- Las cuentas cuyo saldo guardado no coincide con el libro (debe salir vacío).
create or replace function public.ledger_audit()
returns table (account_id bigint, stored bigint, from_entries bigint)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select a.id, a.balance, coalesce(sum(e.amount), 0)::bigint
      from accounts a left join ledger_entries e on e.account_id = a.id
     group by a.id, a.balance
    having a.balance <> coalesce(sum(e.amount), 0);
$$;

-- Las cuentas de una persona nueva: weekly y accumulated encendidas, chips apagada (D3).
create or replace function public.open_accounts(p_user uuid)
returns void
language sql
security definer
set search_path = public, pg_temp
as $$
    insert into accounts (owner_id, kind, enabled)
    values (p_user, 'weekly', true), (p_user, 'accumulated', true), (p_user, 'chips', false)
    on conflict (owner_id, kind) do nothing;
$$;

-- Las cuentas del sistema (la contrapartida de todo lo que entra o sale de una persona). Se crean al pedirlas.
create or replace function public.system_account(p_code text)
returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_id bigint;
begin
    select id into v_id from accounts where system_code = p_code;
    if v_id is null then
        insert into accounts (kind, system_code) values ('system', p_code)
        on conflict (system_code) do nothing
        returning id into v_id;
        if v_id is null then
            select id into v_id from accounts where system_code = p_code;
        end if;
    end if;
    return v_id;
end;
$$;

-- Nadie fuera del servidor llama a estas funciones (ADR-003). Supabase da EXECUTE a public por omisión: se quita.
revoke all on function public.post_transaction(text, text, jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.balance_of(bigint) from public, anon, authenticated;
revoke all on function public.ledger_audit() from public, anon, authenticated;
revoke all on function public.open_accounts(uuid) from public, anon, authenticated;
revoke all on function public.system_account(text) from public, anon, authenticated;
grant execute on function public.post_transaction(text, text, jsonb, jsonb) to service_role;
grant execute on function public.balance_of(bigint) to service_role;
grant execute on function public.ledger_audit() to service_role;
grant execute on function public.open_accounts(uuid) to service_role;
grant execute on function public.system_account(text) to service_role;
