"""Cada error que ve la persona llega con un código estable, para que la interfaz lo pueda traducir.

bad(message, status=400, code=None) hace un ApiError con .code. Esta prueba recorre backend/ y server.py y falla si un bad()
no lleva código, si el código no es un nombre estable (minúsculas, en inglés, con guion bajo) o si no está en
equipo/contratos/errores.md, que es la lista que E5 traduce.

server.py (de E1) e idem.py (de E2) ponen sus códigos ellos mismos: mientras no entregan, están en PENDIENTES con cuántos
bad() sin código les quedan, y ese número solo puede bajar.
"""
import ast
import os
import re
import unittest

from backend.util import ApiError, bad

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT = os.path.join(ROOT, "equipo", "contratos", "errores.md")
CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# archivo -> bad() sin código que le quedan a su dueño. Solo puede bajar; en 0 se quita.
PENDIENTES = {
    "server.py": 15,           # E1
    "backend/idem.py": 2,      # E2
}


def files():
    yield "server.py"
    for name in sorted(os.listdir(os.path.join(ROOT, "backend"))):
        if name.endswith(".py"):
            yield "backend/" + name


def bad_calls(rel):
    """[(línea, código o None, ¿el código es un texto fijo?)] de cada llamada a bad() en el archivo."""
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "bad":
            node = next((k.value for k in n.keywords if k.arg == "code"), n.args[2] if len(n.args) > 2 else None)
            if node is None:
                out.append((n.lineno, None, True))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append((n.lineno, node.value, True))
            else:
                out.append((n.lineno, ast.unparse(node), False))
    return out


def contract_codes():
    with open(CONTRACT, encoding="utf-8") as f:
        return set(re.findall(r"^\| `([a-z0-9_]+)` \|", f.read(), re.M))


class BadCarriesACode(unittest.TestCase):
    def test_bad_takes_a_code_and_the_error_keeps_it(self):
        err = bad("Not enough funds", 400, code="insufficient_funds")
        self.assertIsInstance(err, ApiError)
        self.assertEqual((err.status, err.message, err.code), (400, "Not enough funds", "insufficient_funds"))
        self.assertEqual(bad("Nope", code="market_closed").status, 400)

    def test_without_a_code_it_is_none(self):
        self.assertIsNone(bad("Something").code)
        self.assertIsNone(ApiError(404, "Gone").code)


class EveryErrorHasACode(unittest.TestCase):
    def test_every_bad_in_the_engine_has_a_code(self):
        missing = []
        for rel in files():
            if rel in PENDIENTES:
                continue
            missing += [f"{rel}:{line}" for line, code, _ in bad_calls(rel) if code is None]
        self.assertEqual(missing, [], "bad() sin código (ponle code=\"...\" de equipo/contratos/errores.md):\n  " + "\n  ".join(missing))

    def test_the_pending_files_only_shrink(self):
        for rel, allowed in PENDIENTES.items():
            left = sum(1 for _, code, _ in bad_calls(rel) if code is None)
            with self.subTest(rel=rel):
                self.assertLessEqual(left, allowed, f"{rel} tiene más bad() sin código que antes")
                self.assertEqual(left, allowed, f"{rel} ya tiene menos bad() sin código: baja PENDIENTES a {left}"
                                 + (" (o quítalo)" if left == 0 else ""))

    def test_codes_are_fixed_stable_names_listed_in_the_contract(self):
        listed = contract_codes()
        wrong = []
        for rel in files():
            for line, code, fixed in bad_calls(rel):
                if code is None:
                    continue
                if not fixed or not CODE_RE.match(code):
                    wrong.append(f"{rel}:{line}: {code} no es un nombre fijo en minúsculas")
                elif code not in listed:
                    wrong.append(f"{rel}:{line}: {code} no está en equipo/contratos/errores.md")
        self.assertEqual(wrong, [], "\n  ".join(wrong))

    def test_every_code_in_the_contract_is_used_or_reserved(self):
        with open(CONTRACT, encoding="utf-8") as f:
            text = f.read()
        reserved = set(re.findall(r"`([a-z0-9_]+)`", text[text.index("## Para E1 y E2"):]))
        used = {code for rel in files() for _, code, fixed in bad_calls(rel) if code and fixed}
        unused = sorted(contract_codes() - used - reserved)
        self.assertEqual(unused, [], "Códigos en errores.md que nadie usa: " + ", ".join(unused))


if __name__ == "__main__":
    unittest.main()
