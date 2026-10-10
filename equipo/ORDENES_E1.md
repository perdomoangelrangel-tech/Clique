# Orden 1 · E1 · Plataforma · la app corre igual en Windows, en el CI y en un servidor · 10-oct

## Objetivo (una frase)
Que cada cambio de cualquier encargo se pruebe solo en Linux y en Windows, que la app arranque en un servidor de prueba con un solo comando, y que las fallas de Windows desaparezcan.

## Parte de
Rama `e1-plataforma`, árbol `_ramas/e1-plataforma`, sobre `cimiento-1`. Cada sesión empieza con `cd _ramas/e1-plataforma && git fetch origin && git rebase origin/integracion` (desde la raíz el gancho no deja rebasar: la raíz es `main`), y empujas con `git push --force-with-lease origin e1-plataforma`.

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md` y `equipo/EQUIPO.md`
2. `equipo/historia/ronda-0/bitacoras/OT-001.md` (tu verificación de la computadora: las 4 fallas de Windows y su causa)
3. `equipo/ROJOS_CONOCIDOS.json`, `DEPLOY.md`, `Dockerfile`

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **Las rutas de URL con `/` en `backend/assets.py`** (con `posixpath`, nunca `os.path`), y el servidor **lee el cuerpo antes de rechazar** con 413/415 en `server.py`, para que Windows no corte la conexión | `python -m unittest tests.test_speed.FilesAreServedFast tests.test_profile.UploadingOverHttp` en Windows, 3 veces seguidas | 3 de 3 en verde en Windows; pide a E7 quitar esas 3 filas de `ROJOS_CONOCIDOS.json` |
| 2 | **`requirements-dev.txt`** con lo que necesitan las pruebas y no la app: `tzdata` (la prueba de horario de verano en Windows) y lo que pide E2 en su orden (`psycopg[binary]`, `pgserver`). La app sigue sin dependencias | `pip install -r requirements-dev.txt && python -m unittest tests.test_timezone` | la prueba que se omitía corre y pasa en Windows |
| 3 | **`scripts/correr_pruebas.py`**: corre la suite completa y falla solo por pruebas en rojo que NO estén en `equipo/ROJOS_CONOCIDOS.json` (filtrando por sistema). Imprime el resumen en español | `python scripts/correr_pruebas.py` en Windows y en Linux | sale 0 con los rojos conocidos y 1 si alguien mete un rojo nuevo (compruébalo con un mutante) |
| 4 | **CI en GitHub Actions** (`.github/workflows/ci.yml`): en cada push a `e*-*`, `integracion` y `main`, y en cada PR. Trabajos: `linux` (ubuntu, Python **3.11 y 3.12**: el dueño tiene 3.11), `windows` (igual), los dos con `pip install -r requirements-dev.txt` y `correr_pruebas.py`, para que las pruebas de Postgres de E2 corran; `js` (`node --test tests/js/`, Node 22); y `ganchos` (`node herramientas/ganchos.test.mjs && node herramientas/ganchos.en-vivo.test.mjs`, en ubuntu y en windows) | el enlace de la corrida en verde en tu bitácora | los cuatro trabajos en verde en tu rama |
| 5 | **Ruta `GET /api/salud`**: versión (commit), tiempo encendido y si la base se puede leer y escribir, sin datos de personas. Con su prueba en `tests/test_http.py` | `python -m unittest tests.test_http` | en verde, y la ruta descrita en `equipo/contratos/api.md` (lo creas tú con esta ruta como primera fila) |
| 6 | **Despliegue de prueba listo para un clic**: configuración para un servicio de contenedores con disco persistente (Render o Fly.io: elige uno y di por qué), `DEPLOY.md` traducido al español en su lugar (el nombre se queda: lo enlazan otros archivos) con los pasos que hace el dueño (crear cuenta, pegar variables) y las variables en `.env.example` | `docker build -t clique . && docker run -p 3000:3000 -e ADMIN_PASSWORD=prueba-local-123 clique` y abrir `/api/salud` | el contenedor arranca y responde; el dueño solo tiene que crear la cuenta y pegar valores |
| 7 | **Medición de carga base** (`scripts/medir_carga.py`): N personas simuladas apostando en mercados y casino contra un servidor local; reporta peticiones por segundo y latencia p50/p95/p99 | `python scripts/medir_carga.py --personas 50 --segundos 30` | los números en tu bitácora y en `docs/plataforma/carga.md` (es la línea base para decidir la etapa C de ADR-006) |
| 8 | **Errores con código en `server.py`**: la respuesta de error lleva `code` además de `error` (`ApiError.code`, que agrega E3 en `backend/util.py`), y tus 15 `bad()` de `server.py` llevan un código de la lista de E3 (`equipo/contratos/errores.md`). Si un código no está, pídeselo a E3 en tu bitácora | `python -m unittest tests.test_http` y la prueba de códigos de E3 | ningún `bad()` de `server.py` sin código; `equipo/contratos/api.md` dice cómo es la respuesta de error |

## Tus archivos
Los de E1 en `equipo/PROPIEDAD_DE_ARCHIVOS.md`, más los nuevos: `requirements-dev.txt`, `scripts/correr_pruebas.py`, `scripts/medir_carga.py`, `docs/plataforma/**`, `equipo/contratos/api.md` y la configuración del servicio de despliegue (`render.yaml` o `fly.toml`).

## No hagas
- No cambies la lógica de los módulos de E3 ni la base de E2 (`backend/store.py` es de E2: su falla de Windows es de E2).
- No subas valores reales de variables a ningún archivo.
- No agregues dependencias a la app (solo a `requirements-dev.txt`, y solo las de esta orden).

## Para y pregunta si
- El servicio de despliegue pide tarjeta o un plan de pago: eso lo decide el dueño.
- Una prueba falla en Linux y no está en `ROJOS_CONOCIDOS.json`.
- Necesitas un archivo de otro encargo (pídelo en tu bitácora y sigue con otro entregable).

## Cómo reportas
Al final de tu `equipo/BITACORA.md`, por cada entregable:
`[E1] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
