# OT-005 — Mapa de reglas y casos de referencia

- **Fase:** 0
- **Agente:** E3 · Motor
- **Rama:** `ot/005-reglas-referencias`
- **Depende de:** OT-001 para empezar; OT-002 fusionada para entregar (la prueba de formato usa su Vitest)
- **Contratos que usa:** —
- **Contratos que crea:** `coordinacion/contratos/reglas-economia.md`, `packages/engine/fixtures/`

## Objetivo

Convertir la app actual en una especificación que los demás agentes puedan seguir sin leer Python: un documento con cada regla y número de la economía y los juegos, y archivos JSON de casos de referencia generados ejecutando el código real de `legacy/clique`.

## Contexto

La app actual tiene 1,142 pruebas que pasan y un `ECONOMY.md` muy completo. La versión nueva en TypeScript debe comportarse igual. Los casos de referencia ("golden files") permiten comprobarlo automáticamente: la misma entrada debe dar la misma salida en Python y en TypeScript.

## Alcance

**Incluye**

- `coordinacion/contratos/reglas-economia.md`: cada regla con su número, su caso límite y la referencia `archivo:línea` en `legacy/clique`. Cubre: las dos cuentas, cierre semanal y su orden, premios por posición y círculos chicos, mínimo semanal, bono del miércoles, vale de rescate, préstamos, transferencias, XP y rangos, retos semanales, hitos, tienda, voto de fondos, mercados (LMSR, cotización, deslizamiento, redondeo hacia abajo, resolución, cancelación, edición) y cada juego (pagos, RTP, reglas, qué se oculta hasta el final).
- `legacy-tools/generate_fixtures.py` (fuera de `legacy/clique`, que no se toca) que importe el código de `legacy/clique/backend` y escriba JSON en `packages/engine/fixtures/`:
  - `lmsr.json`: precios y costo de 200 operaciones variadas (2 y 12 resultados, compras y ventas, montos chicos y grandes).
  - `games/<juego>.json`: tabla de pagos y multiplicadores de cada uno de los 13 juegos, y los resultados para secuencias aleatorias fijas.
  - `weekly-rewards.json`: premios para 30 clasificaciones de ejemplo, incluidos empates y círculos con menos de 5 activos.
  - `rounding.json`: casos de redondeo al centavo.
- Una prueba en `packages/engine` que lea cada fixture y verifique que tiene el formato esperado (la paridad real llega cuando se porte cada módulo).

**No incluye**

- Portar la lógica a TypeScript (Fase 1 y 2).
- Modificar `legacy/clique`.

## Archivos y carpetas permitidos

`coordinacion/contratos/reglas-economia.md`, `legacy-tools/`, `packages/engine/fixtures/`, `packages/engine/test/`, `coordinacion/bitacoras/OT-005.md`.

## Criterios de aceptación

- [ ] `python legacy-tools/generate_fixtures.py` regenera todos los fixtures de forma determinista (correrlo dos veces no cambia ningún archivo).
- [ ] Cada juego tiene su archivo. Para juegos con fórmula cerrada (Limbo, Coinflip, Dice, Mines, Tower, Hi-Lo, Wheel, Ruleta, Piedra-papel-tijera, Chicken, Moles) el RTP calculado coincide exactamente con el del código. Para Blackjack y War se calcula con el mismo método que sus pruebas del legacy y se acepta ±0.2 puntos contra el README.
- [ ] `reglas-economia.md` tiene todas las secciones listadas, cada regla con referencia `archivo:línea`.
- [ ] Después de rebasar sobre `main` con OT-002 fusionada, `pnpm test` pasa con la prueba de formato de fixtures (`packages/engine/test/fixtures.test.ts`).

## Notas del cerebro

- Antes de importar `backend`, el script debe fijar las mismas variables que `legacy/clique/tests/__init__.py`: `DATA_DIR` a una carpeta temporal (si no, usa la carpeta de datos REAL), `EMAIL_REQUIRED=0` y `MIDWEEK_BONUS=0`.
- Para fijar el azar, reemplaza el generador desde fuera como hacen las pruebas del legacy. Ojo: `games.py` importa `rand_below` y `rand_unit` con `from .util import ...`, así que hay que reemplazar `backend.games.rand_below` y `backend.games.rand_unit`, no solo los de `util`.
- Si encuentras una regla que el código hace distinto de lo que dice `ECONOMY.md`, anótala como pregunta: puede ser un error del documento o del código.

## Correcciones

(Vacío.)
