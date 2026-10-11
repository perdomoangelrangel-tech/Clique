"""Corre la suite completa y falla solo por pruebas en rojo que no están en equipo/ROJOS_CONOCIDOS.json.

    python scripts/correr_pruebas.py                    # toda la suite (unos 8 minutos)
    python scripts/correr_pruebas.py tests.test_http    # solo algunas pruebas, con el mismo filtro

Sale con 0 si todo lo que falló es un rojo conocido de este sistema, y con 1 si hay un rojo nuevo.
Un rojo conocido vale solo en el sistema que dice su campo "donde" ("solo Windows", "solo Linux"...);
si no nombra ningún sistema, vale en todos. Si dice "intermitente", puede pasar o fallar sin aviso.
"""
import argparse
import json
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROJOS = os.path.join(ROOT, "equipo", "ROJOS_CONOCIDOS.json")
SYSTEMS = {"windows": "win32", "linux": "linux", "macos": "darwin", "mac": "darwin"}


def system_name():
    for name, prefix in (("Windows", "win32"), ("Linux", "linux"), ("macOS", "darwin")):
        if sys.platform.startswith(prefix):
            return name
    return sys.platform


def applies_here(entry, platform=None):
    """Does this known red count on this computer? Reads the "donde" field ("solo Windows, intermitente")."""
    platform = platform or sys.platform
    where = entry.get("donde", "").lower()
    named = [prefix for word, prefix in SYSTEMS.items() if word in where]
    return not named or any(platform.startswith(prefix) for prefix in named)


def known_reds(path=ROJOS, platform=None):
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)["rojos"]
    return {e["prueba"]: e for e in entries if applies_here(e, platform)}


def test_id(test):
    """The id the list uses: a failing subtest counts as its test."""
    case = getattr(test, "test_case", test)
    return case.id()


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.red = {}                        # test id -> "falla" or "error"
        self.ran_ids = set()

    def startTest(self, test):
        super().startTest(test)
        self.ran_ids.add(test.id())

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.red.setdefault(test_id(test), "falla")

    def addError(self, test, err):
        super().addError(test, err)
        self.red.setdefault(test_id(test), "error")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            kind = "falla" if issubclass(err[0], test.failureException) else "error"
            self.red.setdefault(test_id(subtest), kind)


def classify(red, ran, known):
    """Split the reds into new and known, and find the known reds that ran and passed."""
    new = {t: k for t, k in red.items() if t not in known}
    expected = {t: k for t, k in red.items() if t in known}
    now_green = sorted(t for t in known if t in ran and t not in red
                       and "intermitente" not in known[t].get("donde", "").lower())
    return new, expected, now_green


def main(argv=None):
    parser = argparse.ArgumentParser(description="Corre la suite y falla solo por rojos que no son conocidos.")
    parser.add_argument("pruebas", nargs="*", help="módulos o pruebas (tests.test_http); sin nada, toda la suite")
    parser.add_argument("--rojos", default=ROJOS, help="la lista de rojos conocidos (por defecto equipo/ROJOS_CONOCIDOS.json)")
    parser.add_argument("-q", "--callado", action="store_true", help="no imprime el detalle de cada falla")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):              # Windows writes in its old code page: "dueño" came out garbled
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    known = known_reds(args.rojos)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(args.pruebas) if args.pruebas else loader.discover("tests", top_level_dir=".")

    started = time.monotonic()
    runner = unittest.TextTestRunner(resultclass=Result, verbosity=0 if args.callado else 1, stream=sys.stderr)
    result = runner.run(suite)
    minutes = (time.monotonic() - started) / 60

    new, expected, now_green = classify(result.red, result.ran_ids, known)
    out = sys.stdout
    print("", file=out)
    print("=" * 72, file=out)
    print(f"Resumen en {system_name()} (Python {sys.version.split()[0]}), {minutes:.1f} min", file=out)
    print(f"  Corrieron:  {result.testsRun}", file=out)
    print(f"  En verde:   {result.testsRun - len(result.red) - len(result.skipped)}", file=out)
    print(f"  Omitidas:   {len(result.skipped)}", file=out)
    print(f"  Rojos conocidos en este sistema: {len(expected)} de {len(known)}", file=out)
    for t, k in sorted(expected.items()):
        print(f"    - {t} ({k}; dueño {known[t].get('dueno', '?')})", file=out)
    if now_green:
        print("  Rojos conocidos que ya pasan (avisa a E7 para quitarlos de la lista):", file=out)
        for t in now_green:
            print(f"    - {t}", file=out)
    if new:
        print(f"  ROJOS NUEVOS: {len(new)}", file=out)
        for t, k in sorted(new.items()):
            print(f"    - {t} ({k})", file=out)
        print("Resultado: EN ROJO. Hay pruebas que fallan y no están en equipo/ROJOS_CONOCIDOS.json.", file=out)
        return 1
    print("Resultado: EN VERDE. Nada falla fuera de los rojos conocidos.", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
