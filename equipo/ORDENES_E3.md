# Orden 1 · E3 · Motor · las reglas escritas, el dinero solo por el libro y errores con código · 10-oct

## Objetivo (una frase)
Que cada regla de la economía y de los juegos esté escrita en español con su archivo y línea, que una prueba garantice que ningún saldo se mueve fuera de `backend/ledger.py`, y que cada error que ve la persona llegue con un código estable para poder traducirlo.

## Parte de
Rama `e3-motor`, árbol `_ramas/e3-motor`, sobre `cimiento-1`. Cada sesión empieza con `cd _ramas/e3-motor && git fetch origin && git rebase origin/integracion` (desde la raíz el gancho no deja rebasar: la raíz es `main`), y empujas con `git push --force-with-lease origin e3-motor`.

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md` (D2, D8) y `equipo/GLOSARIO.md`
2. `ECONOMY.md` completo
3. `backend/ledger.py`, `backend/util.py` (`round2` redondea a la mitad hacia arriba) y `backend/lmsr.py:93` (`floor_cents`, hacia abajo, es el de los pagos de mercados)

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **`equipo/contratos/reglas-economia.md`** (Propuesto): cada regla y número (cuentas, semana, mínimo semanal, recompensas, préstamos, transferencias, bolsa, tienda, retos, hitos, rangos, casino: ventaja de la casa y pago de cada juego, póker, LMSR) en español, con `archivo:línea` y la prueba que la cubre. Una sección **"Diferencias"** con todo lo que `ECONOMY.md` dice y el código no hace, o al revés | lectura de E0; `grep -c "backend/" equipo/contratos/reglas-economia.md` | cada sección de `ECONOMY.md` tiene su regla con referencia; las diferencias, listadas y sin corregir todavía |
| 2 | **"Dónde se mueve el dinero"**, dentro del mismo contrato: cada función que cambia un saldo, la razón que escribe en el libro y la cuenta de origen y destino. Es lo que E2 convierte en funciones SQL en la ronda 2 | lectura de E2 y E0 | cada llamada a `ledger.*` del código está en la tabla |
| 3 | **Arnés "el dinero solo por el libro"** (`tests/test_dinero_solo_en_libro.py`): falla si algún módulo fuera de `ledger.py` asigna o suma a un saldo directamente | `python -m unittest tests.test_dinero_solo_en_libro` | en verde, y en rojo con un mutante (un `user["balance"] += 1` en un módulo cualquiera) |
| 4 | **Errores con código:** `bad(message, status=400, code=None)` y `ApiError.code` en `backend/util.py`; cada `bad(...)` de tus módulos lleva un código estable en inglés (`insufficient_funds`, `market_closed`…). La lista de códigos con su texto en español va en **`equipo/contratos/errores.md`** (tuyo; E5 la lee para traducir). Los `bad()` de `server.py` (15, de E1) y de `backend/idem.py` (2, de E2) los ponen ellos con códigos de tu lista: su orden ya lo dice. E1 agrega `code` a la respuesta en `server.py` | `python -m unittest discover -s tests -t .` y una prueba nueva que recorre `backend/` y `server.py` y falla si un `bad()` no tiene código (mientras E1 y E2 no entregan, sus archivos van en una lista de pendientes dentro de la prueba, que solo puede encogerse) | 0 errores sin código en tus módulos; la suite completa en verde |
| 5 | **Las diferencias del entregable 1 que sean errores del código**, corregidas una por una, cada una con su prueba vista en rojo. Las que sean errores del documento, se corrigen en el contrato; `ECONOMY.md` se traduce al español en su lugar cuando lo toques (el nombre se queda) | la prueba de cada corrección | cada diferencia cerrada o anotada como pregunta para el dueño |

## Tus archivos
`backend/**` salvo los de E1 y E2, `ECONOMY.md`, `equipo/contratos/reglas-economia.md`, `equipo/contratos/errores.md`, `tests/econ.py` y las pruebas de la lógica (`tests/test_*.py` que no son de otros).

## No hagas
- No cambies una regla de la economía sin que el dueño la firme: si el código y el documento no coinciden y no es un error claro, es una pregunta.
- No toques `backend/store.py`, `txn.py` ni `idem.py` (E2), ni `server.py` (E1): pide la línea.
- No muevas saldos fuera de `ledger.py`, ni para una prueba.

## Para y pregunta si
- Una regla tiene dos lecturas razonables (por ejemplo, qué cuenta paga un premio).
- Un cambio afecta lo que la gente ya ganó o debe.

## Cómo reportas
`[E3] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
