"""El modelo real del archivo de datos, generado del código: docs/datos/modelo-actual.md.

    python -m backend.datos.inventario              # escribe docs/datos/modelo-actual.md
    python -m backend.datos.inventario --verificar  # falla si algo no está documentado o el documento está viejo

Junta tres cosas:
  1. el catálogo escrito a mano (backend/datos/catalogo.py): cada campo, qué es y a dónde va en Postgres;
  2. el código (backend/datos/codigo.py): qué funciones escriben y leen cada campo;
  3. una base sembrada con la app de verdad (backend/datos/sembrar.py): lo que el archivo guarda de hecho.

--verificar falla (sale con 1) si:
  * la base sembrada tiene un campo que no está en el catálogo, o de un tipo que el catálogo no dice;
  * el código escribe un campo que no está en el catálogo (aunque la siembra no lo toque);
  * docs/datos/modelo-actual.md no es exactamente lo que este programa genera hoy.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

from . import codigo
from .catalogo import BY_PATH, CATALOG, NOT_DATA
from .pg_local import ROOT

DOC = os.path.join(ROOT, "docs", "datos", "modelo-actual.md")
SHOW = 6                      # cuántas funciones se nombran por campo antes de decir "y N más"


# ---------------------------------------------------------------- la base sembrada contra el catálogo

def _allowed(kind):
    k = kind.lower()
    ok = set()
    if "mapa" in k or "objeto" in k:
        ok.add(dict)
    if "lista" in k:
        ok.add(list)
    if "texto" in k or "semana" in k or "fecha" in k:
        ok.add(str)
    if "bool" in k:
        ok.add(bool)
    if any(w in k for w in ("entero", "centavos", "ms", "1")):
        ok.add(int)
    if "dólares" in k or "decimal" in k:
        ok.update((int, float))
    if "null" in k or "ms o" in k:
        ok.add(type(None))
    return ok


def walk(data):
    """Recorre el archivo guiado por el catálogo. Devuelve (rutas vistas, campos sin documentar, tipos que no cuadran)."""
    seen, missing, wrong = set(), set(), set()

    def go(value, path):
        f = BY_PATH.get(path)
        if f is None:
            missing.add(path)
            return
        seen.add(path)
        allowed = _allowed(f.kind)
        if allowed and type(value) not in allowed:
            wrong.add(f"{path}: el catálogo dice {f.kind!r} y la base tiene {type(value).__name__}")
        if f.opaque:
            return
        if isinstance(value, dict):
            is_map = f.kind.startswith("mapa")
            for k, v in value.items():
                go(v, f"{path}.{{}}" if is_map else f"{path}.{k}")
        elif isinstance(value, list):
            for v in value:
                go(v, f"{path}[]")

    for key, value in data.items():
        go(value, key)
    return seen, missing, wrong


# ---------------------------------------------------------------- el código contra el catálogo

def _covering(path):
    """El campo del catálogo que cubre esta ruta: ella misma o un ancestro opaco."""
    if path in BY_PATH:
        return path
    probe = path
    while True:
        cut = max(probe.rfind("."), probe.rfind("["))
        if cut <= 0:
            return None
        probe = probe[:cut]
        f = BY_PATH.get(probe)
        if f is not None:
            return probe if f.opaque else None


def who(events=None):
    """{campo del catálogo: {"write": {funciones}, "read": {funciones}}} y las rutas escritas que no cubre el catálogo."""
    events = codigo.scan() if events is None else events
    out = {f.path: {"write": set(), "read": set()} for f in CATALOG}
    uncovered = {}
    tops = {f.path for f in CATALOG if "." not in f.path and "[" not in f.path}
    for path, mode, module, func, line in events:
        p = codigo.fmt(path)
        target = _covering(p)
        if target is not None:
            out[target][mode].add(f"{module}.{func}")
        elif mode == "write" and path[0] in tops and p not in NOT_DATA:
            uncovered.setdefault(p, set()).add(f"{module}.py:{line} ({func})")
    return out, uncovered


# ---------------------------------------------------------------- el documento

def _names(funcs):
    funcs = sorted(funcs)
    if not funcs:
        return "—"
    shown = ", ".join(f"`{f}`" for f in funcs[:SHOW])
    return shown + (f" y {len(funcs) - SHOW} más" if len(funcs) > SHOW else "")


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


SECTIONS = [
    ("Datos de la base", ("meta",)),
    ("Personas y sesiones", ("users", "usernames", "sessions")),
    ("Círculos y cierre semanal", ("circles", "snapshots", "challenges")),
    ("Mercados", ("markets",)),
    ("Casino y póker", ("games", "feed", "poker")),
    ("El libro del archivo", ("ledger", "ledger_sum", "idem")),
    ("Préstamos, transferencias y votos de fondos", ("loans", "transfers", "fundvotes")),
    ("Amigos y chats", ("social", "chats")),
]


def render(usage=None):
    usage = who()[0] if usage is None else usage
    top = lambda p: p.split(".")[0].split("[")[0]
    lines = [
        "# El modelo real del archivo de datos",
        "",
        "*Generado por `python -m backend.datos.inventario`. No se edita a mano: se cambia `backend/datos/catalogo.py` y se",
        "vuelve a generar. `python -m backend.datos.inventario --verificar` falla si la app guarda un campo que aquí no está.*",
        "",
        "Hoy toda la app vive en un archivo, `data/db.json` (`backend/store.py`), cargado en memoria y guardado completo",
        "después de cada cambio. La bolsa de valores guarda sus precios aparte, en `data/market.json` (`backend/stockengine.py`),",
        "y no está en este documento. Este es el inventario de lo que guarda `db.json`, de quién lo escribe y quién lo lee, y",
        "de a dónde va en el esquema de Postgres v1 (`supabase/migrations/`).",
        "",
        "**Cómo leerlo.** Rutas con punto: `{}` es la clave de un mapa (un id, una semana), `[]` un elemento de una lista. Un",
        "campo *opaco* se guarda entero y no se describe por dentro. *Lo escriben* y *Lo leen* salen de leer el código",
        "(`backend/datos/codigo.py`): es aproximado, sigue cadenas de claves, alias y nombres de variable; lo que no puede",
        "seguir no lo cuenta. **El dinero** del archivo está en dólares con decimales (`balance`, `accum`, apuestas,",
        "posiciones) salvo el libro (`ledger`), los préstamos y las transferencias, que ya van en centavos. En Postgres todo",
        "va en centavos `bigint`.",
        "",
    ]
    r2 = [f for f in CATALOG if "." not in f.path and "[" not in f.path and f.dest.startswith("ronda 2")]
    skip = [f for f in CATALOG if "." not in f.path and "[" not in f.path and f.dest.startswith("no se migra")]
    lines += ["## Lo que el esquema v1 todavía no guarda", "",
              "Colecciones enteras que quedan para la ronda 2 (dentro de las demás, cada campo dice lo suyo en su fila):", ""]
    lines += [f"- `{f.path}`: {f.what} → {f.dest[len('ronda 2: '):] if f.dest.startswith('ronda 2: ') else 'por diseñar'}" for f in r2]
    lines += ["", "Y lo que no se migra a propósito:", ""]
    lines += [f"- `{f.path}`: {f.dest[len('no se migra: '):] if f.dest.startswith('no se migra: ') else f.what}" for f in skip]
    lines += [""]
    for title, tops in SECTIONS:
        lines += [f"## {title}", "", "| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |", "|---|---|---|---|---|---|"]
        for f in CATALOG:
            if top(f.path) not in tops:
                continue
            u = usage.get(f.path, {"write": set(), "read": set()})
            kind = f.kind + (" · opaco" if f.opaque else "")
            lines.append(f"| `{f.path}` | {_cell(kind)} | {_cell(f.what)} | {_names(u['write'])} | {_names(u['read'])} | {_cell(f.dest)} |")
        lines.append("")
    done = {t for _, tops in SECTIONS for t in tops}
    left = sorted({top(f.path) for f in CATALOG} - done)
    if left:
        raise RuntimeError(f"colecciones del catálogo sin sección: {left}")
    return "\n".join(lines)


# ---------------------------------------------------------------- verificar

def seeded_data():
    folder = tempfile.mkdtemp(prefix="clique-inventario-")
    path = os.path.join(folder, "db.json")
    p = subprocess.run([sys.executable, "-m", "backend.datos.sembrar", "--salida", path], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=900, env={**os.environ, "DATA_DIR": folder})
    if p.returncode != 0:
        raise RuntimeError("no se pudo sembrar la base:\n" + p.stdout[-2000:] + p.stderr[-2000:])
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify(data=None):
    """Lista de problemas (vacía si todo está documentado y el documento está al día)."""
    problems = []
    usage, uncovered = who()
    _, missing, wrong = walk(seeded_data() if data is None else data)
    for p in sorted(missing):
        problems.append(f"la base sembrada tiene {p} y el catálogo no lo documenta")
    problems += sorted(wrong)
    for p, where in sorted(uncovered.items()):
        problems.append(f"el código escribe {p} y el catálogo no lo documenta ({', '.join(sorted(where)[:3])})")
    try:
        with open(DOC, "r", encoding="utf-8") as f:
            current = f.read()
    except OSError:
        current = None
    if current != render(usage) + "\n":
        problems.append(f"{os.path.relpath(DOC, ROOT)} no está al día: python -m backend.datos.inventario")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="El modelo real del archivo de datos de Clique.")
    ap.add_argument("--verificar", action="store_true", help="no escribe nada; falla si falta documentar algo")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.verificar:
        problems = verify()
        for p in problems:
            print("  -", p)
        print(f"{len(problems)} problemas." if problems else f"El modelo está completo: {len(CATALOG)} campos documentados.")
        return 1 if problems else 0
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    with open(DOC, "w", encoding="utf-8", newline="\n") as f:
        f.write(render() + "\n")
    print(f"Escrito {os.path.relpath(DOC, ROOT)} ({len(CATALOG)} campos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
