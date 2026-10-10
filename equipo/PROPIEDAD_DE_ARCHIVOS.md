# Propiedad de archivos

*Un archivo, un dueño. Si no está en la lista, pregunta en tu bitácora antes de tocarlo.*

*Hecho por E0 el 10 de octubre de 2026 para la ronda 1. Si esta tabla y una orden no coinciden,
manda la orden y se corrige aquí.*

**Cómo se lee:**
- Las rutas van completas desde la raíz del repositorio. `**` es "todo lo que cuelga de ahí".
- **Cuando dos filas cubren el mismo archivo, gana la más específica.**
- El gancho `PreToolUse` (`herramientas/ganchos/`) lee esta tabla tal cual: una fila por ruta, la
  ruta entre comillas invertidas en la primera columna y el dueño en la segunda.
- Los dueños posibles son:
  - `E1` a `E7`;
  - `E0`: lo escribe el cerebro; los agentes proponen en su bitácora;
  - `Dueño`: Ángel;
  - `Compartido`: cualquiera, solo agregando o con aviso en la bitácora.
- En la zona prohibida, como en `.gitignore`: una ruta que empieza con `/` es solo la de la raíz;
  sin `/` vale a cualquier profundidad (`.env` también es `backend/.env`).
- **Un archivo nuevo** dentro de una carpeta que es tuya es tuyo. Uno en un lugar sin dueño se pide
  primero en la bitácora.

## E1 · Plataforma

| Ruta | Dueño | Nota |
|---|---|---|
| `server.py` | **E1** | El servidor y sus rutas. Quien necesite una ruta nueva la pide con su firma (E3 y E5) |
| `backend/config.py` | E1 | Variables de entorno |
| `backend/assets.py` | E1 | La lista de precarga (falla en Windows: ronda 1) |
| `backend/mailer.py` | E1 | Correo saliente |
| `Dockerfile` | E1 | |
| `.dockerignore` | E1 | |
| `DEPLOY.md` | E1 | Se traduce al español en su lugar; el nombre se queda para no romper enlaces |
| `start.command` | E1 | |
| `.github/**` | E1 | CI |
| `scripts/**` | E1 | |
| `.gitignore` | E1 | |
| `.gitattributes` | E1 | |
| `.env.example` | E1 | Los demás piden sus variables por bitácora |
| `tests/test_deploy.py` | E1 | |
| `tests/test_http.py` | E1 | |
| `requirements-dev.txt` | E1 | Dependencias solo de pruebas. Los demás las piden por bitácora |
| `render.yaml` | E1 | Nuevo, si E1 elige Render |
| `fly.toml` | E1 | Nuevo, si E1 elige Fly.io |
| `docs/plataforma/**` | E1 | Nuevo: mediciones de carga y notas de operación |
| `equipo/contratos/api.md` | E1 | Nuevo: las rutas del servidor. E3 y E5 piden sus filas |

## E2 · Datos

| Ruta | Dueño | Nota |
|---|---|---|
| `backend/store.py` | **E2** | La base en archivo y su escritura segura |
| `backend/txn.py` | E2 | Todo o nada |
| `backend/idem.py` | E2 | Reintentos sin duplicar |
| `backend/migrations.py` | E2 | Migraciones del archivo |
| `backend/datos/**` | E2 | Nuevo: la capa de datos (etapa B) |
| `supabase/**` | E2 | Esquema, funciones SQL, políticas y pruebas pgTAP |
| `docs/datos/**` | E2 | Nuevo: el modelo de datos |
| `equipo/contratos/esquema.md` | E2 | Nuevo: el contrato del esquema |
| `tests/test_store.py` | E2 | |
| `tests/test_migration.py` | E2 | |
| `tests/test_retire_horses.py` | E2 | Una migración del archivo |
| `tests/test_esquema_pg.py` | E2 | Nuevo: el esquema en Postgres local |
| `tests/test_libro_pg.py` | E2 | Nuevo: el libro en SQL |
| `tests/test_importador.py` | E2 | Nuevo: el importador del archivo |

## E3 · Motor

| Ruta | Dueño | Nota |
|---|---|---|
| `backend/**` | **E3** | Toda la lógica del servidor, salvo lo que esta tabla da a E1 y E2 |
| `ECONOMY.md` | E3 | Se traduce al español en su lugar; el nombre se queda para no romper enlaces |
| `equipo/contratos/reglas-economia.md` | E3 | Nuevo |
| `equipo/contratos/errores.md` | E3 | Nuevo: los códigos de error de la API, uno por cada `bad()` |
| `tests/econ.py` | E3 | |
| `tests/test_*.py` | E3 | Las pruebas de la lógica, salvo las que esta tabla da a otros |

## E4 · Diseño

| Ruta | Dueño | Nota |
|---|---|---|
| `static/css/**` | **E4** | Tokens y estilos. Nada de colores sueltos fuera de `tokens.css` |
| `static/fonts/**` | E4 | |
| `static/js/theme.js` | E4 | |
| `static/js/looks.js` | E4 | |
| `static/js/art.js` | E4 | El arte 2D de los pósters de juego; E6 da los renders |
| `static/js/views/diseno.js` | E4 | Nuevo: la página de muestras |
| `equipo/contratos/tokens.md` | E4 | Nuevo |
| `tests/test_tokens.py` | E4 | Nuevo: contraste y colores sueltos |
| `docs/diseno/**` | E4 | Nuevo: capturas antes y después |

## E5 · Frontend

| Ruta | Dueño | Nota |
|---|---|---|
| `static/index.html` | **E5** | |
| `static/js/**` | **E5** | Pantallas, navegación, estado y conexión con el servidor, salvo lo de E4 |
| `static/i18n/**` | E5 | Nuevo: textos en `es-MX` y `en` |
| `static/manifest.webmanifest` | E5 | Nuevo: PWA |
| `static/sw.js` | E5 | Nuevo: PWA |
| `static/vendor/**` | E5 | Nuevo: bibliotecas servidas con la app (three.js), con su licencia |
| `docs/producto/**` | E5 | Nuevo: pantallas, rutas, navegación, glosario de textos |
| `equipo/contratos/textos.md` | E5 | Nuevo: cómo se escriben las claves y los textos |
| `tests/js/**` | E5 | |
| `tests/layout/**` | E5 | |
| `tests/layout_world.py` | E5 | |
| `tests/test_layout.py` | E5 | |
| `tests/test_i18n.py` | E5 | Nuevo: textos sin traducir |

## E6 · Arte 3D

| Ruta | Dueño | Nota |
|---|---|---|
| `assets3d/**` | **E6** | `.blend` en Git LFS |
| `docs/arte/**` | E6 | |
| `static/3d/**` | E6 | Modelos para la web y sus respaldos 2D |
| `static/renders/**` | E6 | Nuevo: renders que usa la app |
| `static/casino-icons/**` | E6 | |
| `equipo/contratos/arte3d.md` | E6 | |
| `tests/test_arte.py` | E6 | Nuevo: archivos, medidas y presupuestos de las imágenes |

## E7 · Integración

| Ruta | Dueño | Nota |
|---|---|---|
| `equipo/BITACORA_COMBINADA.md` | **E7** | Se genera con `combinar_bitacoras.sh` |
| `equipo/VERIFICADO.md` | E7 | Lo que E7 comprobó de cada entregable, con el comando |
| `equipo/ROJOS_CONOCIDOS.json` | E7 | Pruebas en rojo que el CI tolera, con dueño y porqué |
| `herramientas/ganchos.test.mjs` | E7 | La prueba de las reglas de los ganchos |
| `herramientas/ganchos.en-vivo.test.mjs` | E7 | La prueba de punta a punta, en una carpeta de juguete |
| `herramientas/revisar_propiedad.mjs` | E7 | Nuevo: qué archivos de otro dueño cambió una rama |

## E0 · Cerebro

| Ruta | Dueño | Nota |
|---|---|---|
| `equipo/ORDENES_*.md` | **E0** | Las órdenes |
| `equipo/DECISIONES.md` | E0 | Las escribe E0 cuando el dueño decide |
| `equipo/decisiones/**` | E0 | |
| `equipo/EQUIPO.md` | E0 | |
| `equipo/COORDINACION.md` | E0 | |
| `equipo/PROPIEDAD_DE_ARCHIVOS.md` | E0 | Esta tabla |
| `equipo/CONTRATOS.md` | E0 | El índice; cada contrato es de su encargo |
| `equipo/GLOSARIO.md` | E0 | |
| `equipo/COMO_ESCRIBIR_ORDENES.md` | E0 | |
| `equipo/DEFINICION_DE_TERMINADO.md` | E0 | |
| `equipo/LEEME.md` | E0 | |
| `equipo/combinar_bitacoras.sh` | E0 | |
| `equipo/historia/**` | E0 | La ronda 0, como historia |
| `CLAUDE.md` | E0 | |
| `COMO-EMPEZAR.md` | E0 | |
| `README.md` | E0 | |
| `.claude/**` | E0 | Roles, comandos y ganchos de Claude Code |
| `herramientas/ganchos/**` | E0 | |
| `docs/plan-maestro.md` | E0 | |

## Compartidos

| Ruta | Dueño | Nota |
|---|---|---|
| `equipo/BITACORA.md` | Compartido | Cada rama solo agrega al final |
| `tests/helpers.py` | Compartido | Con aviso en la bitácora |
| `tests/__init__.py` | Compartido | |
| `tests/test_speed.py` | Compartido | La parte de archivos servidos es de E1; la de la base, de E2 |
| `tests/test_backend.py` | Compartido | Con aviso en la bitácora |

## Zona prohibida

Nadie la toca, ni con gancho ni sin él:

- `.env`, `.env.local`, cualquier archivo con claves
- `/data/` (la base local de cada computadora: solo la carpeta de la raíz)
- `.claude/settings.local.json` (los permisos de cada computadora)
- `.git/` por dentro (los candados huérfanos se tratan como dice COORDINACION.md)
