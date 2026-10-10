# Orden 1 · E2 · Datos · etapa A: el modelo real, el esquema de Postgres y el libro en SQL · 10-oct

## Objetivo (una frase)
Que exista en Postgres un esquema que guarda todo lo que hoy guarda el archivo, con un libro de doble partida en funciones SQL probado, y un importador que demuestra con números que no se pierde nada (etapa A de ADR-006). La app sigue en el archivo.

## Parte de
Rama `e2-datos`, árbol `_ramas/e2-datos`, sobre `cimiento-1`. Cada sesión empieza con `cd _ramas/e2-datos && git fetch origin && git rebase origin/integracion` (desde la raíz el gancho no deja rebasar: la raíz es `main`), y empujas con `git push --force-with-lease origin e2-datos`.

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md` (D2, D3, D6, D9) y `equipo/decisiones/ADR-003-dinero-en-postgres.md`, `ADR-004`, `ADR-006`
2. `backend/store.py`, `backend/txn.py`, `backend/idem.py`, `backend/ledger.py` (este último es de E3: léelo, no lo cambies)
3. `ECONOMY.md` secciones 1, 2 y 12

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **La escritura del archivo no falla en Windows**: `store.py` escribe aunque otro hilo esté leyendo `db.json` (reintento corto o escritura que no choque) | `python -m unittest tests.test_speed.TheDatabaseIsWrittenCarefully` en Windows, 3 veces | 3 de 3 en verde; pide a E7 quitar esa fila de `ROJOS_CONOCIDOS.json` |
| 2 | **El modelo real, generado del código** (`backend/datos/inventario.py` → `docs/datos/modelo-actual.md`): cada colección y campo del archivo, su tipo, quién lo escribe y quién lo lee (módulo y función). Se genera sembrando con `scripts/seed.py` y leyendo el código | `python -m backend.datos.inventario --verificar` | el documento sale del programa y `--verificar` falla si alguien agrega un campo sin documentarlo |
| 3 | **Esquema v1 en `supabase/migrations/`**: perfiles, círculos y miembros, cuentas (`weekly`, `accumulated` y `chips` apagada, D3), libro (`ledger_transactions` y `ledger_entries`, centavos `bigint`), mercados y posiciones, rondas de casino, cierre semanal. Seguridad por fila en cada tabla. Lo que falte del modelo, listado como "ronda 2" | `python -m unittest tests.test_esquema_pg` (Postgres local con `pgserver`) | las migraciones aplican desde cero; cada tabla tiene RLS y una prueba de que **otro** usuario no la ve |
| 4 | **El libro en SQL**: `post_transaction(idempotency_key, reason, lines jsonb)`: suma cero, ninguna cuenta de persona negativa, candados en orden fijo, la misma clave devuelve la misma transacción. Más `balance_of(account)` | `python -m unittest tests.test_libro_pg` | casos de cada regla, cada uno visto en rojo con un mutante; una prueba de 20 hilos pagando a la vez sin perder un centavo |
| 5 | **Importador con simulación** (`backend/datos/importar_archivo.py --simular <db.json>`): cuenta lo que insertaría por tabla y comprueba que el saldo de cada cuenta en el archivo coincide con la suma del libro importado; lista toda diferencia | `python -m backend.datos.importar_archivo --simular data/db.json` sobre la base sembrada | 0 diferencias en la base sembrada; si el archivo real tiene diferencias, se listan, no se corrigen |
| 6 | **`equipo/contratos/esquema.md`** (Propuesto): tablas, columnas, políticas y firmas de las funciones. Es lo que E3 va a llamar en la etapa B | lectura de E0 | existe y coincide con las migraciones |
| 7 | **Los 2 `bad()` de `backend/idem.py` con código**, de la lista de E3 (`equipo/contratos/errores.md`); si el código no está, pídeselo a E3 en tu bitácora | la prueba de códigos de E3 | ningún `bad()` tuyo sin código |

Dependencias permitidas (solo para pruebas, las agrega E1 a `requirements-dev.txt`; mientras tanto instálalas en tu computadora): `psycopg[binary]` y `pgserver`. **Si no están instaladas, tus pruebas de Postgres se omiten con un aviso (`unittest.skipUnless`), no fallan**: la suite completa tiene que pasar en una computadora sin ellas.

## Tus archivos
Los de E2 en `equipo/PROPIEDAD_DE_ARCHIVOS.md`, más los nuevos: `backend/datos/**`, `supabase/**`, `docs/datos/**`, `tests/test_esquema_pg.py`, `tests/test_libro_pg.py`, `tests/test_importador.py`.

## No hagas
- No escribas en el Supabase de producción (D9). Si necesitas probar en Supabase, pide a E0 una rama de base de datos en tu bitácora.
- No cambies `backend/ledger.py` ni los módulos de E3: la etapa B (que los módulos usen la capa de datos) es la ronda 2.
- No uses `float` para dinero en ningún lado.

## Para y pregunta si
- El modelo real tiene algo que no cabe en un esquema relacional sin decidir (por ejemplo, historial que se reescribe).
- Encuentras dinero que no cuadra en la base sembrada.

## Cómo reportas
`[E2] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
