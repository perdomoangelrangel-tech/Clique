# OT-007 — Mapa de pantallas, navegación y textos en español

- **Fase:** 0
- **Agente:** E5 · Frontend
- **Rama:** `ot/007-mapa-pantallas`
- **Depende de:** — (empieza ya)
- **Contratos que usa:** ADR-001, ADR-004 (fichas compradas)
- **Contratos que crea:** `docs/producto/navegacion.md` y el catálogo de textos en `docs/producto/i18n/` (los dos con estado "Propuesto")

## Objetivo

Que antes de construir pantallas en la Fase 1 exista: el inventario completo de lo que hace hoy cada pantalla de la app actual, la propuesta de navegación de la app nueva para celular y computadora, y todos los textos visibles traducidos al español de México en formato i18next, listos para conectarse a `apps/web`.

## Contexto

El plan pone la "base de traducciones" en la Fase 0 y la función F1 (español de México) en la Fase 1. La app actual (`legacy/clique/static/`) está solo en inglés y sus textos están escritos dentro del HTML que arma JavaScript, así que hoy no hay de dónde traducir. Referencias:

- `static/index.html`, `static/js/app.js` (rutas de la SPA), `layout.js`, `ui.js`, `state.js`, `viewstate.js`.
- `static/js/views/` (28 vistas) y `static/js/games/` (15 archivos: 13 juegos más `betpanel.js` y `common.js`).
- `docs/screenshots/` (51 capturas) para ver cómo se ven.
- `server.py`: cada ruta de la API está registrada con el decorador `@route(...)`; los mensajes de error que ve la persona salen de `backend/*.py`.
- `ECONOMY.md` para los nombres de cada concepto de la economía.

## Alcance

**Incluye**

- `docs/producto/pantallas.md`: una fila por pantalla, vista, ventana emergente o panel de la app actual: nombre, archivo y función del legacy, qué muestra, qué acciones tiene, qué rutas de la API llama, sus estados (cargando, vacío, error, sin permiso), captura de `docs/screenshots/` si existe, a qué ruta de la app nueva pasa y en qué fase del plan se construye (1, 2, 3 o 4).
- `docs/producto/rutas-api.md`: cada ruta registrada en `server.py` con método, patrón, si pide sesión, función que la atiende, qué pantallas la usan y, como propuesta, qué tipo de pieza la reemplaza en la app nueva (lectura directa con seguridad por fila, función SQL, Edge Function o servidor de juego). Esa última columna es una propuesta para E2 y E3, no una decisión.
- `docs/producto/navegacion.md` (estado "Propuesto"): arquitectura de la app nueva: barra inferior en celular (máximo 5 destinos) y navegación de escritorio, la tabla de rutas de React Router con su pantalla, cuáles piden sesión, enlaces profundos (invitación a un círculo, un mercado, un resultado compartido) y dónde vive cada pantalla del inventario. Incluye el arreglo R3 del plan (sin buscador de mercados ni cinta de precios dentro del casino).
- `docs/producto/i18n/en/<espacio>.json` y `docs/producto/i18n/es-MX/<espacio>.json`: todos los textos visibles de la app actual, el original en inglés y la traducción, con las mismas claves en los dos idiomas. Formato i18next (JSON v4): plurales con `_one` y `_other`, variables con `{{nombre}}`. Un archivo por espacio de nombres (por ejemplo `comun`, `navegacion`, `cuenta`, `circulo`, `mercados`, `casino`, `poker`, `ranking`, `castigo`, `perfil`, `tienda`, `errores`). Cantidades, fechas y fichas no van dentro del texto: se formatean con `Intl` en `es-MX`.
- `docs/producto/glosario.md`: términos fijos inglés → español de México (por ejemplo chips, market, circle, punishment, leaderboard, stake, payout, cash out) y el tono de Clique: tuteo, español de México sin regionalismos fuertes, frases cortas, premium sin ser pomposo.
- En el glosario, una sección **"Términos sensibles para el dictamen legal"**: palabras que pueden sonar a dinero real o a apuestas con dinero (apostar, ganar, cobrar, premio, retiro, el signo `$`, "casino") con la alternativa que propones. Escríbela como "Pregunta para el cerebro"; no la decides tú.
- `docs/producto/herramientas/`: el script que uses para extraer los textos del legacy y comprobar la cobertura (que cada texto visible tenga clave y que `en` y `es-MX` tengan las mismas claves). Solo lee `legacy/`, nunca lo modifica.

**No incluye**

- Código en `apps/web/` (lo crea OT-002; las pantallas llegan en la Fase 1).
- Cambiar cualquier archivo de `legacy/`.
- Decidir el esquema de datos o la API nueva (eso es de E2 y E3; aquí solo propones).

## Archivos y carpetas permitidos

`docs/producto/`, `coordinacion/bitacoras/OT-007.md`.

## Criterios de aceptación

- [ ] `pantallas.md` cubre las 28 vistas de `static/js/views/`, los 13 juegos, el póker y las ventanas emergentes y paneles de `app.js`, `ui.js` y `layout.js`. La bitácora anota cómo se encontraron (comando y número).
- [ ] `rutas-api.md` tiene tantas filas como rutas registra `server.py` (anota el comando con que las contaste y el número).
- [ ] El script de `herramientas/` corre sin errores, confirma que todos los JSON son válidos y que `en` y `es-MX` tienen exactamente las mismas claves, y reporta cuántos textos visibles del legacy quedaron sin clave (meta: 0; cada excepción, justificada en la bitácora).
- [ ] Ningún texto en `es-MX` quedó en inglés salvo nombres propios y términos del glosario que se dejan así a propósito.
- [ ] `navegacion.md` existe con estado "Propuesto" y cada pantalla del inventario tiene lugar en ella.
- [ ] `glosario.md` existe con la sección de términos sensibles anotada como pregunta para el cerebro.
- [ ] El legacy sigue intacto (`sha256sum -c --quiet ../clique.sha256` dentro de `legacy/clique`).

## Cómo verificar

```bash
python docs/producto/herramientas/<tu script> --verificar     # o node, según lo que uses
cd legacy/clique && sha256sum -c --quiet ../clique.sha256 && echo "legacy intacto"
```

## Notas del cerebro

- Esta orden es la "base de traducciones" de la Fase 0 y el mapa que va a usar E5 en la Fase 1: piensa en quien construya cada pantalla sin haber visto la app actual.
- Usa las capturas para entender, pero el inventario se saca del código: hay pantallas sin captura.
- Nombres de claves en inglés y en minúsculas con puntos (`markets.create.title`); textos en español de México.
- Si una pantalla del legacy no tiene sentido en la app nueva (por ejemplo, algo que el plan reemplaza), anótala igual y márcala "se retira" con el motivo.

## Correcciones

(Vacío.)
