"""Lee el código de la app (backend/*.py y server.py) y encuentra, función por función, qué partes del archivo de datos
escribe y cuáles lee. Lo usa backend/datos/inventario.py.

Es un análisis del código sin correrlo, así que es aproximado: sigue las cadenas de claves (`db()["markets"][mid]["q"]`),
los alias dentro de una función (`wk = u.setdefault("wk", {})`, `for u in db()["users"].values()`) y, para los registros que
llegan como parámetro, el nombre de la variable (`user`, `m`, `loan`...; ver HINTS). Lo que no puede seguir, no lo cuenta.

Una ruta es una tupla de pasos: una clave ("users"), "{}" para la clave de un mapa (un id) o "[]" para un elemento de lista.
"""
import ast
import glob
import os
from collections import defaultdict

from .pg_local import ROOT

U = ("users", "{}")
HINTS = {                                   # nombre de variable -> la ruta del registro que suele ser
    "user": U, "u": U, "me": U, "to": U, "them": U, "viewer": U, "other": U, "owner": U, "sender": U, "receiver": U,
    "target": U, "person": U, "member": U, "winner": U, "payer": U, "borrower": U, "lender": U, "acct": U,
    "wk": U + ("wk",), "xf": U + ("xfer",), "xfer": U + ("xfer",), "goals": U + ("goals",), "prof": U + ("profile",),
    "profile": U + ("profile",), "mail": U + ("mail",), "inv": U + ("inv",),
    "m": ("markets", "{}"), "market": ("markets", "{}"), "pos": ("markets", "{}", "positions", "{}", "{}"),
    "circle": ("circles", "{}"), "recap": ("circles", "{}", "recaps", "{}"),
    "loan": ("loans", "{}"), "chat": ("chats", "{}"), "tr": ("transfers", "{}"), "transfer": ("transfers", "{}"),
}
MODULE_HINTS = {                             # los mismos nombres significan otra cosa en estos módulos
    "circles.py": {"c": ("circles", "{}")},
    "weekly.py": {"c": ("circles", "{}"), "r": None},
    "markets.py": {"c": ("circles", "{}"), "t": ("markets", "{}", "trades", "[]"), "p": None},
    "chats.py": {"c": ("chats", "{}"), "chat": ("chats", "{}"), "m": ("chats", "{}", "msgs", "[]"), "msg": ("chats", "{}", "msgs", "[]")},
    "social.py": {"s": ("social", "{}"), "me": ("social", "{}"), "them": ("social", "{}")},
    "fundvotes.py": {"v": ("fundvotes", "{}"), "vote": ("fundvotes", "{}")},
    "poker.py": {"t": ("poker", "{}"), "table": ("poker", "{}"), "seat": ("poker", "{}", "seats", "[]"), "v": None, "s": None},
    "loans.py": {"loan": ("loans", "{}")},
    "challenges.py": {"item": ("challenges", "{}", "items", "[]"), "it": ("challenges", "{}", "items", "[]")},
    "exchange.py": {"pos": U + ("pos", "{}")},
    "games.py": {"acct": U, "g": None, "v": None, "table": None, "m": None},
    "recovery.py": {"m": None, "u": U, "user": U},
    "mailer.py": {"m": None, "msg": None},
    "transfers.py": {"t": ("transfers", "{}"), "m": None},
    "ledger.py": {"r": ("ledger", "{}", "[]"), "row": ("ledger", "{}", "[]")},
    "idem.py": {"hit": ("idem", "{}"), "box": ("idem",)},
    "server.py": {"m": ("markets", "{}"), "c": ("circles", "{}"), "t": ("poker", "{}"), "v": None},
}
MUTATORS = {"append", "insert", "extend", "update", "clear", "remove", "discard", "add", "sort", "popitem"}
DB_NAMES = {"d", "data", "db_", "state"}


def files():
    out = sorted(glob.glob(os.path.join(ROOT, "backend", "*.py"))) + [os.path.join(ROOT, "server.py")]
    return [p for p in out if os.path.basename(p) != "__init__.py"]


class _Function(ast.NodeVisitor):
    def __init__(self, module, name, hints, events):
        self.module, self.name, self.events = module, name, events
        self.hints = hints
        self.alias = {}                       # nombre -> ruta
        self.literal = {}                     # nombre -> claves del dict literal que se le asignó

    # ---- resolver una expresión a una ruta del archivo
    def resolve(self, e):
        if isinstance(e, ast.Name):
            if e.id in self.alias:
                return self.alias[e.id]
            if e.id in DB_NAMES and self.alias.get(e.id) is None and e.id in self._db_vars:
                return ()
            h = self.hints.get(e.id)
            return h
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Name) and f.id == "db" and not e.args:
                return ()
            if isinstance(f, ast.Attribute):
                if f.attr == "db" and isinstance(f.value, ast.Name) and f.value.id == "store":
                    return ()
                base = self.resolve(f.value)
                if base is None:
                    return None
                if f.attr in ("get", "setdefault", "pop") and e.args:
                    k = self._key(e.args[0], base)
                    if k is not None:
                        self._event(base + (k,), "write" if f.attr in ("setdefault", "pop") else "read", e)
                        return base + (k,)
                if f.attr == "values":
                    return base + ("{}",)
            return None
        if isinstance(e, ast.Attribute) and e.attr == "data" and isinstance(e.value, ast.Name) and e.value.id == "store":
            return ()
        if isinstance(e, ast.Subscript):
            base = self.resolve(e.value)
            if base is None:
                return None
            k = self._key(e.slice, base)
            return None if k is None else base + (k,)
        return None

    _db_vars = set()

    @staticmethod
    def _key(s, base):
        if isinstance(s, ast.Constant):
            if isinstance(s.value, str):
                return s.value
            if isinstance(s.value, int):
                return "[]"
            return None
        if isinstance(s, ast.Slice):
            return None
        return "{}"

    def _event(self, path, mode, node):
        if path and path[0] not in ("[]", "{}"):
            self.events.append((path, mode, self.module, self.name, getattr(node, "lineno", 0)))

    # ---- recorrer
    def visit_Subscript(self, node):
        path = self.resolve(node)
        if path is not None:
            mode = "write" if isinstance(node.ctx, (ast.Store, ast.Del)) else "read"
            self._event(path, mode, node)
        self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute):
            base = self.resolve(f.value)
            if base is not None and f.attr in MUTATORS:
                self._event(base, "write", node)
                for a in node.args:
                    keys = self._dict_keys(a)
                    for k in keys:
                        self._event(base + ("[]", k) if f.attr in ("append", "insert", "extend") else base + (k,), "write", node)
            elif base is not None and f.attr in ("get", "setdefault", "pop"):
                self.resolve(node)                      # anota la lectura o escritura
        self.generic_visit(node)

    def _nested(self, e, base):
        """Las rutas que escribe un dict literal puesto en `base`, entrando en dicts, listas y comprensiones anidadas."""
        out = []
        if isinstance(e, ast.Dict):
            for k, v in zip(e.keys, e.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    out.append(base + (k.value,))
                    out += self._nested(v, base + (k.value,))
        elif isinstance(e, (ast.ListComp, ast.List)):
            for elt in ([e.elt] if isinstance(e, ast.ListComp) else e.elts):
                out += self._nested(elt, base + ("[]",))
        elif isinstance(e, ast.DictComp):
            out += self._nested(e.value, base + ("{}",))
        return out

    def _dict_keys(self, e):
        if isinstance(e, ast.Dict):
            return [k.value for k in e.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if isinstance(e, ast.Name):
            return self.literal.get(e.id, [])
        return []

    def visit_Assign(self, node):
        self.visit(node.value)
        value_path = self.resolve(node.value)
        keys = self._dict_keys(node.value)
        for t in node.targets:
            if isinstance(t, ast.Name):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "db":
                    self._db_vars.add(t.id)
                    self.alias[t.id] = ()
                elif value_path is not None:
                    self.alias[t.id] = value_path
                if keys:
                    self.literal[t.id] = keys
                    target = self.alias.get(t.id) or self.hints.get(t.id)
                    if target is not None and value_path is None:
                        for k in keys:
                            self._event(target + (k,), "write", node)
            else:
                path = self.resolve(t)
                if path is not None:
                    self._event(path, "write", node)
                    for k in keys:
                        self._event(path + (k,), "write", node)
                    for nested in self._nested(node.value, path):
                        self._event(nested, "write", node)
                self.visit(t)

    def visit_AugAssign(self, node):
        path = self.resolve(node.target)
        if path is not None:
            self._event(path, "write", node)
        self.generic_visit(node)

    def visit_For(self, node):
        it = node.iter
        base, kind = None, None
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr in ("values", "items", "keys"):
            base, kind = self.resolve(it.func.value), it.func.attr
        elif isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id in ("reversed", "list", "sorted") and it.args:
            base, kind = self.resolve(it.args[0]), "list"
        else:
            base, kind = self.resolve(it), "list"
        if base is not None:
            item = base + ("{}",) if kind in ("values", "items") else base + ("[]",)
            if kind == "keys":
                item = None
            tgt = node.target
            if isinstance(tgt, ast.Name) and item is not None:
                self.alias[tgt.id] = item
            elif isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2 and isinstance(tgt.elts[1], ast.Name) and kind == "items":
                self.alias[tgt.elts[1].id] = item
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name != self.name:          # una función dentro de otra: la recorre con sus alias
            _Function(self.module, f"{self.name}.{node.name}", {**self.hints, **{k: v for k, v in self.alias.items()}}, self.events).run(node)
            return
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def run(self, node):
        self._db_vars = set()
        for stmt in node.body:
            self.visit(stmt)


def scan():
    """[(ruta, "write"|"read", módulo, función, línea)] de todo el código de la app."""
    events = []
    for path in files():
        module = os.path.basename(path)
        hints = {**HINTS, **{k: v for k, v in MODULE_HINTS.get(module, {}).items()}}
        hints = {k: v for k, v in hints.items() if v is not None}
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _Function(module[:-3], node.name, hints, events).run(node)
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        _Function(module[:-3], f"{node.name}.{sub.name}", hints, events).run(sub)
    return events


def fmt(path):
    out = ""
    for step in path:
        out += step if step == "[]" else ("." + step if out else step)
    return out


def by_path(events):
    out = defaultdict(lambda: {"write": set(), "read": set()})
    for path, mode, module, func, _ in events:
        out[path][mode].add(f"{module}.{func}")
    return out
