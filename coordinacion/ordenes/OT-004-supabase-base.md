# OT-004 — Supabase: esquema base y libro contable

- **Fase:** 0
- **Agente:** E2 · Datos
- **Rama:** `ot/004-supabase-base`
- **Depende de:** — para empezar; OT-002 fusionada para agregar los scripts de la raíz y para entregar
- **Contratos que usa:** ADR-001, ADR-003
- **Contratos que crea:** `coordinacion/contratos/esquema.md`

## Objetivo

Que exista el esquema base en Supabase con perfiles, círculos, las dos cuentas por persona y un libro contable de doble partida, protegido por seguridad por fila, con una función SQL que mueve dinero de forma atómica y pruebas que demuestran que el dinero no se crea ni se pierde.

## Contexto

Proyecto de Supabase: `Clique`, ref `rrmifvptjajfvxxdqqek`, región us-east-1, plan Pro. Hoy todo vive en `legacy/clique/data/db.json`. Referencias: `backend/ledger.py` (el libro), `backend/txn.py` (todo o nada), `backend/idem.py` (reintentos), `backend/circles.py`, `backend/users.py` y `ECONOMY.md` secciones 1 y 12. Lee ADR-003 y ADR-004 antes de empezar.

## Alcance

**Incluye**

- `supabase init` en la raíz y migraciones en `supabase/migrations/`. Instala la CLI como dependencia de desarrollo de la raíz (`pnpm add -D supabase -w`) y agrega scripts `db:reset`, `db:test` y `db:push`.
- Dónde probar: si hay Docker Desktop, con `supabase start` en local. Si no, pide al cerebro una rama de base de datos del proyecto (Pro lo permite) y anótalo en la bitácora; nunca pruebes contra la base principal.
- Tablas: `profiles` (1 a 1 con `auth.users`, username único sin importar mayúsculas, fecha de nacimiento para el filtro 18+), `circles`, `circle_members` (rol owner o member), `accounts` (una `weekly`, una `accumulated` y una `chips` por persona —ADR-004—, más una cuenta de sistema por tipo de origen: asignación semanal, premios, casino, mercados), `ledger_entries` (doble partida: cada transacción tiene renglones que suman cero; monto en centavos `bigint`, nunca `float`), `ledger_transactions` (id, motivo, clave de idempotencia única, metadatos).
- Función `post_transaction(idempotency_key, reason, lines jsonb)` con `security definer`: valida que sume cero, que ninguna cuenta de usuario quede negativa, bloquea las cuentas en orden fijo para evitar interbloqueos, y si la clave ya existe devuelve la transacción original sin repetirla.
- Saldos como vista o columna mantenida por la función, nunca editable desde el cliente.
- RLS: cada persona lee su perfil y sus cuentas; los miembros de un círculo leen el círculo y la lista de miembros; nadie escribe en `accounts` ni en el libro desde el cliente.
- Pruebas pgTAP en `supabase/tests/`: suma cero en cada transacción, no hay saldos negativos, la misma clave de idempotencia no cobra dos veces, una persona no puede leer las cuentas de otra, un no miembro no ve un círculo privado, y toda tabla de `public` tiene RLS activado (consulta a `pg_class.relrowsecurity`).
- Prueba de concurrencia en `supabase/tests/concurrency/` (script de Node con varias conexiones a la vez, porque pgTAP corre en una sola sesión).
- `coordinacion/contratos/esquema.md` con el diagrama de tablas y la firma de cada función.

**No incluye**

- Mercados, juegos, cierre semanal (Fase 1 y 2).
- Conectar la app web.

## Archivos y carpetas permitidos

`supabase/`, `coordinacion/contratos/esquema.md`, `coordinacion/bitacoras/OT-004.md`, `.env.example`, `package.json` de la raíz (solo la dependencia `supabase` y los scripts `db:*`) y `pnpm-lock.yaml` (solo lo que cambie `pnpm add`).

## Criterios de aceptación

- [ ] `supabase db reset` aplica todas las migraciones desde cero sin errores (local con Docker, o en una rama de base del proyecto en la nube).
- [ ] `supabase test db` pasa todas las pruebas pgTAP listadas.
- [ ] El script de concurrencia lanza 50 transferencias simultáneas entre dos cuentas y la suma total queda igual a la inicial.
- [ ] La prueba pgTAP de RLS confirma que ninguna tabla de `public` queda sin RLS (el cerebro corre además los asesores de Supabase al revisar).
- [ ] `contratos/esquema.md` existe con estado "Propuesto".

## Notas del cerebro

- Montos en centavos enteros: `legacy` usa flotantes con redondeo a dos decimales; documenta en el contrato cómo se convierte.
- Si no hay Docker en Windows, no lo instales sin preguntar: anota el bloqueo y espera el proyecto en la nube.

## Correcciones

**2026-10-10 · E0 — Empiezas ya, en paralelo con OT-001 y OT-002**

- No esperes a OT-001: comprueba tú mismo `git`, `node` y si hay Docker Desktop (`docker --version`), y anótalo en la bitácora.
- Mientras OT-002 no esté fusionada no hay `package.json` en la raíz: usa la CLI con `npx supabase@<versión estable>` (anota la versión) para `init`, migraciones y pruebas. Cuando OT-002 se fusione: `git fetch origin && git rebase origin/main`, `pnpm add -D supabase -w` con esa misma versión y los scripts `db:reset`, `db:test` y `db:push` en la raíz. Después `/entregar`.
- Si no hay Docker, pide la rama de base de datos en la nube como dice el alcance: escríbelo como "Pregunta para el cerebro" y avísale al dueño. Mientras tanto escribe las migraciones y las pruebas pgTAP.
