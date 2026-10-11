"""El dinero solo se mueve por el libro (D2).

Un saldo es user["balance"] (la cuenta semanal) o user["accum"] (la acumulada). Esta prueba lee el código de la app (server.py,
backend/ y scripts/) y falla si algún módulo fuera de backend/ledger.py asigna, suma, resta o borra uno de esos campos sin
pasar por ledger.post. Las pocas escrituras directas que no son dinero (la cartera de práctica, el espejo de la acumulada en
la cartera del casino, un diccionario de respuesta) están en EXCEPCIONES, cada una con su razón y su texto exacto: si alguien
cambia una de esas líneas, o escribe un saldo en otro lado, la prueba lo ve. Las que sí son dinero y todavía no pasan por el
libro están en PENDIENTES, que solo puede encogerse.

Las pruebas (tests/) quedan fuera: muchas preparan un saldo a mano para empezar.

También revisa que cada función que llama a ledger.post o ledger.opening esté en la tabla "Dónde se mueve el dinero" de
equipo/contratos/reglas-economia.md, que es la lista que E2 lleva a SQL.
"""
import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ("balance", "accum")
CONTRACT = os.path.join(ROOT, "equipo", "contratos", "reglas-economia.md")

# (archivo, función, texto exacto de la escritura) -> por qué no es mover dinero
EXCEPCIONES = {
    ("backend/users.py", "credit", "user['balance'] = min(config.MAX_BALANCE, round2(user['balance'] + amount))"):
        "la cartera de práctica (demo): no es una cuenta",
    ("backend/users.py", "debit", "user['balance'] = max(0.0, round2(user['balance'] - amount))"):
        "la cartera de práctica (demo): no es una cuenta",
    ("backend/users.py", "credit", "user['balance'] = ledger.balance(owner, 'accumulated')"):
        "espejo de la acumulada en la cartera del casino, después de ledger.post",
    ("backend/users.py", "debit", "user['balance'] = ledger.balance(owner, 'accumulated')"):
        "espejo de la acumulada en la cartera del casino, después de ledger.post",
    ("backend/games.py", "demo_account", "d.update({'balance': DEMO_START, 'stats': {}, 'activity': [], 'history': []})"):
        "abre la cartera de práctica",
    ("backend/games.py", "demo_reset", "d.update({'balance': DEMO_START, 'stats': {}, 'activity': [], 'history': []})"):
        "reinicia la cartera de práctica",
    ("backend/markets.py", "detail", "out['balance'] = viewer['balance'] if viewer else 0"):
        "un diccionario de respuesta, no un usuario",
    ("server.py", "api_games_state", "out['balance'] = acct['balance']"):
        "un diccionario de respuesta, no un usuario",
    ("backend/migrations.py", "split_accounts", "u['balance'] = ledger.to_dollars(weekly_part)"):
        "migración de una sola vez al pasar a dos cuentas, con su renglón opening en el libro (archivo de E2)",
    ("backend/migrations.py", "split_accounts", "u['accum'] = ledger.to_dollars(accum_part)"):
        "migración de una sola vez al pasar a dos cuentas, con su renglón opening en el libro (archivo de E2)",
    ("backend/migrations.py", "retire_horses", "demo['balance'] = round(demo['balance'] + stake_c / 100, 2)"):
        "devuelve una apuesta de Horses a la cartera de práctica (archivo de E2)",
}

# Escrituras que SÍ mueven dinero fuera del libro y todavía no se corrigen. Esta lista solo puede encogerse.
PENDIENTES = {}


def app_files():
    yield "server.py"
    for top in ("backend", "scripts"):
        for folder, _, names in os.walk(os.path.join(ROOT, top)):
            for name in sorted(names):
                if name.endswith(".py"):
                    yield os.path.relpath(os.path.join(folder, name), ROOT).replace("\\", "/")


def _is_money_key(node):
    return isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and node.slice.value in FIELDS


def _writes_money(node):
    """Does this node assign, add to, delete or otherwise set user["balance"] or user["accum"]?"""
    if isinstance(node, (ast.Assign, ast.Delete)):
        targets = node.targets
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        targets = [node.target]
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        name = node.func.attr
        if name == "update":
            for arg in node.args:
                if isinstance(arg, ast.Dict) and any(isinstance(k, ast.Constant) and k.value in FIELDS for k in arg.keys):
                    return True
            return any(k.arg in FIELDS for k in node.keywords)
        return (name in ("setdefault", "__setitem__", "pop") and bool(node.args)
                and isinstance(node.args[0], ast.Constant) and node.args[0].value in FIELDS)
    else:
        return False
    return any(_is_money_key(x) for t in targets for x in ast.walk(t))


def _functions(tree):
    """Each node's outermost enclosing function name ("" at module level)."""
    owner = {}

    def visit(node, fn):
        for child in ast.iter_child_nodes(node):
            here = fn
            if not fn and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                here = child.name
            owner[child] = here
            visit(child, here)
    visit(tree, "")
    return owner


def money_writes(rel, source):
    """[(archivo, función, texto, línea)] de cada escritura directa a un saldo en `source`."""
    tree = ast.parse(source)
    owner = _functions(tree)
    return [(rel, owner.get(n, ""), ast.unparse(n), n.lineno) for n in ast.walk(tree) if _writes_money(n)]


def ledger_callers(rel, source):
    """{(módulo.función, línea)} de cada llamada a ledger.post o ledger.opening en `source`."""
    tree = ast.parse(source)
    owner = _functions(tree)
    module = os.path.splitext(os.path.basename(rel))[0]
    out = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("post", "opening")
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "ledger"):
            out.add((f"{module}.{owner.get(n, '')}", n.lineno))
    return out


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def all_money_writes():
    found = []
    for rel in app_files():
        if rel == "backend/ledger.py":
            continue
        found.extend(money_writes(rel, read(rel)))
    return found


class MoneyOnlyMovesThroughTheLedger(unittest.TestCase):
    def test_no_module_outside_the_ledger_writes_a_balance(self):
        allowed = set(EXCEPCIONES) | set(PENDIENTES)
        wrong = [f"{rel}:{line} en {fn or 'el módulo'}: {text}" for rel, fn, text, line in all_money_writes()
                 if (rel, fn, text) not in allowed]
        self.assertEqual(wrong, [], "Un saldo se mueve fuera de backend/ledger.py. Usa ledger.post (o users.credit/debit):\n  "
                         + "\n  ".join(wrong))

    def test_every_exception_and_pending_write_is_still_there(self):
        """Si una excepción o un pendiente ya no existe en el código, se quita de la lista: así solo puede encogerse."""
        present = {(rel, fn, text) for rel, fn, text, _ in all_money_writes()}
        gone = [f"{k[0]} {k[1]}: {k[2]}" for k in list(EXCEPCIONES) + list(PENDIENTES) if k not in present]
        self.assertEqual(gone, [], "Ya no están en el código; quítalas de la lista:\n  " + "\n  ".join(gone))

    def test_the_scan_catches_every_way_of_writing_a_balance(self):
        mutants = [
            'def f(user):\n    user["balance"] += 1\n',
            'def f(user):\n    user["accum"] = 5\n',
            'def f(user):\n    user["balance"] -= 0.01\n',
            'def f(a, b):\n    a["balance"], b["accum"] = 1, 2\n',
            'def f(user):\n    user.update({"balance": 3})\n',
            'def f(user):\n    user.update(accum=3)\n',
            'def f(user):\n    user.setdefault("balance", 9)\n',
            'def f(user):\n    del user["accum"]\n',
            'user = {}\nuser["balance"] = 1\n',
        ]
        for src in mutants:
            with self.subTest(src=src):
                self.assertTrue(money_writes("backend/x.py", src), "the scan missed it")
        harmless = 'def f(user):\n    x = user["balance"] + 1\n    out = {"balance": x}\n    return ledger.post(user, "weekly", 1)\n'
        self.assertEqual(money_writes("backend/x.py", harmless), [])


class EveryLedgerCallIsInTheContract(unittest.TestCase):
    def test_every_function_that_calls_the_ledger_is_in_the_money_table(self):
        text = read(os.path.relpath(CONTRACT, ROOT))
        start = text.index("## Dónde se mueve el dinero")
        end = text.index("\n## ", start + 1)
        listed = set(re.findall(r"`([a-z_]+\.[a-z_]+)`", text[start:end]))
        missing = []
        for rel in app_files():
            if rel == "backend/ledger.py":
                continue
            for name, line in sorted(ledger_callers(rel, read(rel))):
                if name not in listed:
                    missing.append(f"{name} ({rel}:{line})")
        self.assertEqual(missing, [], "Llaman al libro y no están en «Dónde se mueve el dinero» de reglas-economia.md:\n  "
                         + "\n  ".join(missing))

    def test_the_contract_check_sees_a_new_caller(self):
        src = 'from . import ledger\n\ndef pay_bonus(user):\n    ledger.post(user, "weekly", 5, "bonus")\n'
        self.assertEqual(ledger_callers("backend/bonus.py", src), {("bonus.pay_bonus", 4)})


if __name__ == "__main__":
    unittest.main()
