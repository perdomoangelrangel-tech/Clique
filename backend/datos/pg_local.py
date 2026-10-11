"""Un Postgres local para las pruebas del esquema y del libro, con `pgserver` (Postgres embebido, sin instalar nada).

Las pruebas lo usan así:

    from backend.datos import pg_local

    @unittest.skipUnless(pg_local.AVAILABLE, pg_local.WHY_NOT)
    class Algo(unittest.TestCase):
        def setUp(self):
            self.dsn = pg_local.fresh_database()          # una base nueva con las migraciones aplicadas

Un solo servidor por proceso (arrancarlo tarda unos segundos), una base nueva por prueba que la pida. Nunca se conecta a
Supabase (D9): el servidor vive en una carpeta temporal y se apaga al terminar.
"""
import atexit
import glob
import itertools
import os
import shutil
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# backend/datos/mutantes.py la cambia para probar las migraciones con un error sembrado a propósito.
MIGRATIONS = os.environ.get("CLIQUE_MIGRATIONS_DIR") or os.path.join(ROOT, "supabase", "migrations")
SHIM = os.path.join(ROOT, "supabase", "pruebas", "supabase_local.sql")

try:
    import pgserver                      # noqa: F401
    import psycopg                       # noqa: F401
    AVAILABLE, WHY_NOT = True, ""
except ImportError as e:                 # pragma: no cover - depende de la computadora
    AVAILABLE = False
    WHY_NOT = f"Postgres local no disponible ({e.name} no está instalado): pip install \"psycopg[binary]\" pgserver"

_lock = threading.Lock()
_server = None
_folder = None
_names = itertools.count(1)


def migration_files():
    return sorted(glob.glob(os.path.join(MIGRATIONS, "*.sql")))


def _start():
    global _server, _folder
    with _lock:
        if _server is None:
            import pgserver
            _folder = tempfile.mkdtemp(prefix="clique-pg-")
            _server = pgserver.get_server(_folder, cleanup_mode="stop")
            atexit.register(_stop)
    return _server


def _stop():
    global _server
    if _server is not None:
        try:
            _server.cleanup()
        finally:
            _server = None
            shutil.rmtree(_folder, ignore_errors=True)


def admin_dsn(database="postgres"):
    uri = _start().get_uri()
    return uri.rsplit("/", 1)[0] + "/" + database


def fresh_database(migrate=True):
    """Crea una base vacía, le pone el sustituto de Supabase y (si migrate) aplica todas las migraciones en orden.
    Devuelve su cadena de conexión (como superusuario)."""
    import psycopg
    name = f"clique_{os.getpid()}_{next(_names)}"
    with psycopg.connect(admin_dsn(), autocommit=True) as c:
        c.execute(f'create database "{name}"')
    dsn = admin_dsn(name)
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(_read(SHIM))
        if migrate:
            for path in migration_files():
                c.execute(_read(path))
    return dsn


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def as_user(conn, user_id):
    """Dentro de la transacción abierta de `conn`, actúa como la persona `user_id` desde el navegador (rol authenticated)."""
    conn.execute("set local role authenticated")
    conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))


def as_server(conn):
    """Dentro de la transacción abierta de `conn`, actúa como el servidor (rol service_role, se salta RLS)."""
    conn.execute("set local role service_role")
