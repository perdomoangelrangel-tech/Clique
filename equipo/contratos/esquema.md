# Contrato · Esquema de Postgres v1 y funciones del libro

**Estado: Propuesto** (E2, 10-oct). Lo revisa E0. Dueño: E2. Fuente: `supabase/migrations/` (si no coinciden, manda la
migración y esto es un error; `tests/test_esquema_pg.py` compara las dos cosas).

Para quién: **E3**, que en la etapa B (ronda 2) va a mover el dinero con estas funciones en vez de `backend/ledger.py`, y
**E5**, que va a leer estas tablas desde el navegador. Etapa A: nada de la app usa esto todavía; la app sigue en el archivo.

## Reglas que no cambian

1. **El dinero solo se mueve con `post_transaction`** (D2, ADR-003). Nadie escribe `accounts.balance`,
   `ledger_transactions` ni `ledger_entries` de otra forma.
2. **Todo monto de dinero es `bigint` en centavos.** Las `numeric` del esquema no son dinero: acciones, precios de 0 a 1,
   multiplicadores, la liquidez del LMSR y la escala de premios.
3. **El navegador solo lee** (roles `anon` y `authenticated`): no hay ninguna política de escritura y los permisos de
   insert, update y delete están quitados. El servidor escribe con `service_role`.
4. **La cuenta `chips` (fichas compradas) existe para cada persona y nace apagada** (`enabled = false`, D3). El libro la
   rechaza mientras esté apagada. `app_settings.purchases_enabled = false`.

## Funciones

Todas son `security definer` y solo las puede ejecutar `service_role`.

| Firma | Devuelve | Qué hace |
|---|---|---|
| `post_transaction(p_idempotency_key text, p_reason text, p_lines jsonb, p_meta jsonb default '{}')` | `bigint` (id de la transacción) | Asienta un movimiento de doble partida. Ver abajo. |
| `balance_of(p_account bigint)` | `bigint` | El saldo de una cuenta en centavos, **sumando el libro** (no lee `accounts.balance`). |
| `ledger_audit()` | `table (account_id bigint, stored bigint, from_entries bigint)` | Las cuentas cuyo saldo guardado no es la suma del libro. Debe salir vacía. |
| `open_accounts(p_user uuid)` | `void` | Crea `weekly`, `accumulated` (encendidas) y `chips` (apagada) de una persona. Se puede llamar dos veces. |
| `system_account(p_code text)` | `bigint` | El id de la cuenta del sistema con ese código (`casino`, `market`, `external`...); la crea si no existe. |

### `post_transaction`

`p_lines` es una lista: `[{"account": <accounts.id>, "amount": <centavos>}, ...]`. Monto positivo entra a la cuenta,
negativo sale. `p_meta` es libre (`ref`, `note`, `external`, `txid`...).

Reglas, en este orden:

1. **Idempotencia.** La misma `p_idempotency_key` con la misma razón y las mismas líneas (en cualquier orden) devuelve el id
   de la transacción que ya existe y no mueve nada. Con otra razón u otras líneas se rechaza. Dos llamadas al mismo tiempo
   con la misma clave mueven el dinero una sola vez. Un intento rechazado no gasta su clave.
2. **Forma.** Al menos dos líneas; cada cuenta una sola vez; montos enteros distintos de cero.
3. **Suma cero.**
4. **Cuentas** que existen y están encendidas.
5. **Candados** sobre las cuentas en orden de `id`, siempre: dos pagos cruzados (A→B y B→A) no se bloquean entre sí.
6. **Ninguna cuenta de persona negativa.** Las de sistema sí pueden quedar negativas (la casa paga).

Errores: `SQLSTATE P0001` con un mensaje que empieza con un código estable en inglés, dos puntos y el detalle en español:

| Código | Cuándo |
|---|---|
| `invalid_idempotency_key` | falta la clave |
| `invalid_reason` | falta la razón |
| `invalid_lines` | no es una lista, menos de dos líneas, cuenta repetida, monto no entero o cero |
| `unbalanced` | las líneas no suman cero |
| `unknown_account` | una cuenta no existe |
| `account_disabled` | una cuenta está apagada (`chips`) |
| `insufficient_funds` | una cuenta de persona quedaría negativa |
| `idempotency_conflict` | la clave ya se usó para otro movimiento |

`insufficient_funds` es el mismo caso que hoy da `ledger.post` con "Not enough funds"; cuando E3 publique
`equipo/contratos/errores.md`, estos códigos se alinean con los de la API.

Ejemplo (una apuesta de $20.00 en el casino):

```sql
select post_transaction(
  'casino:dice:<persona>:<requestId>', 'casino.dice',
  '[{"account": 41, "amount": -2000}, {"account": 3, "amount": 2000}]'::jsonb,   -- 41: weekly de la persona; 3: system casino
  '{"ref": "round-8c58"}'::jsonb);
```

## Tablas

Las fechas son `timestamptz`. Los `legacy_id` guardan el id de 12 caracteres del archivo (para el importador).

| Tabla | Columnas | Quién la ve (RLS, `select` para `authenticated`) |
|---|---|---|
| `profiles` | `id uuid` (pk, el id de Supabase Auth), `legacy_id`, `username` (3 a 20, único sin mayúsculas), `look jsonb`, `bio`, `suspended`, `deleted_at`, `created_at` | uno mismo y quien comparte un círculo |
| `circles` | `id uuid`, `legacy_id`, `name` (2 a 40), `description` (≤ 200), `emoji`, `visibility` (`private`/`public`), `invite_code` (único), `owner_id`, `created_at` | sus miembros |
| `circle_members` | `circle_id`, `user_id` (pk juntos), `joined_at` | los miembros del círculo |
| `accounts` | `id bigint`, `owner_id` (null en las de sistema), `kind` (`weekly`/`accumulated`/`chips`/`system`), `system_code` (único, solo sistema), `enabled`, `balance bigint`, `created_at`; una por persona y tipo; las de persona nunca negativas | solo su dueño |
| `ledger_transactions` | `id bigint`, `idempotency_key` (única), `reason`, `request_hash`, `meta jsonb`, `created_at` | quien tiene una línea en una cuenta suya |
| `ledger_entries` | `id bigint`, `transaction_id`, `account_id`, `amount bigint` (≠ 0), `balance_after bigint`, `created_at` | el dueño de la cuenta |
| `app_settings` | `key` (pk), `value jsonb`. Hoy: `purchases_enabled = false` | cualquiera con sesión |
| `markets` | `id uuid`, `legacy_id`, `circle_id` (null: todo el sitio), `creator_id`, `question` (5 a 160), `description`, `category`, `emoji`, `outcomes text[]` (2 a 12), `liquidity_b numeric`, `shares_q numeric[]`, `status` (`open`/`closed`/`resolved`/`void`), `winner`, `volume bigint`, `closes_at`, `created_at`, `resolved_at` | los miembros del círculo; los del sitio, cualquiera con sesión |
| `market_positions` | `market_id`, `user_id`, `token` (`y0`, `n1`...) (pk juntos), `shares numeric`, `invested bigint`, `settled`, `payout bigint` | solo su dueño |
| `market_trades` | `id bigint`, `market_id`, `user_id`, `kind` (`buy`/`sell`/`withdraw`/`refund`), `token`, `shares numeric`, `amount bigint`, `price numeric`, `created_at` | quien puede ver el mercado |
| `casino_rounds` | `id uuid`, `legacy_id`, `user_id`, `account` (`weekly`/`accumulated`/`chips`), `game`, `status` (`active`/`finished`), `bet bigint`, `payout bigint` (null mientras sigue), `multiplier numeric`, `detail`, `state jsonb`, `created_at`, `finished_at`; una ronda activa por persona, cuenta y juego | solo su dueño, **sin la columna `state`** (la baraja, las minas: decide el resultado, D8) |
| `week_snapshots` | `week date` (el lunes), `user_id` (pk juntos), `holding bigint` | solo su dueño |
| `week_closes` | `circle_id`, `week` (pk juntos), `finalized_at`, `reason` (`last`/`minimum`), `loser_ids uuid[]`, `punishment jsonb`, `note`, `awards jsonb`, `rules jsonb`, `active`, `scale numeric`, `served` | los miembros del círculo |
| `week_standings` | `circle_id`, `week`, `user_id` (pk juntos), `position`, `value`, `start_value`, `delta` (bigint), `moves`, `active`, `out_by_minimum`, `reward_note`, `requirements jsonb` | los miembros del círculo |
| `week_rewards` | `circle_id`, `week`, `user_id` (pk juntos), `amount bigint` (> 0), `position`, `paid`, `transaction_id` (el pago; null si no se ha pagado o si se importó de un renglón ya compactado) | los miembros del círculo |

Funciones de apoyo de las políticas (las puede llamar el navegador; solo responden sobre quien llama):
`is_circle_member(p_circle uuid) → boolean`, `shares_circle_with(p_user uuid) → boolean`, `owns_account(p_account bigint) → boolean`.

## Lo que falta (ronda 2)

Préstamos, transferencias, votos de fondos, retos, metas y rango, inventario de la tienda, bolsa, póker (mesas y el dinero
real sentado en ellas), chats, amistades, avisos, castigos, comentarios, ediciones e historial de precios de los mercados,
y las cuentas en Supabase Auth. La lista campo por campo está en `docs/datos/modelo-actual.md`.

## Cómo se prueba

- `python -m unittest tests.test_esquema_pg tests.test_libro_pg` (Postgres local con `pgserver`; sin él se omiten).
- `python -m backend.datos.mutantes`: cada regla de arriba tiene un mutante que pone su prueba en rojo.
