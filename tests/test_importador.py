"""El importador del archivo a Postgres (backend/datos/importar_archivo.py): sobre una base sembrada con la app de verdad
no encuentra diferencias, y encuentra cada diferencia que se le siembra a propósito. Si hay Postgres local, además mete el
plan en el libro SQL (por post_transaction) y comprueba que cada saldo sale igual que en el archivo."""
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from backend.datos import importar_archivo as imp
from backend.datos import pg_local

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDED = {}


def setUpModule():
    """Una base sembrada por la app (en otro proceso, para no tocar el estado global de las demás pruebas)."""
    folder = tempfile.mkdtemp(prefix="clique-importador-")
    path = os.path.join(folder, "db.json")
    p = subprocess.run([sys.executable, "-m", "backend.datos.sembrar", "--salida", path], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                       env={**os.environ, "DATA_DIR": folder})
    if p.returncode != 0:
        raise RuntimeError("no se pudo sembrar la base:\n" + p.stdout[-2000:] + p.stderr[-2000:])
    SEEDED["path"] = path
    with open(path, "r", encoding="utf-8") as f:
        SEEDED["data"] = json.load(f)


def seeded():
    return copy.deepcopy(SEEDED["data"])


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def first_user(d):
    return next(iter(d["users"]))


class LaBaseSembradaCuadra(unittest.TestCase):
    def test_no_differences_in_the_seeded_database(self):
        plan = imp.plan_from(seeded())
        self.assertEqual(plan.differences, [])

    def test_the_seeded_database_exercises_what_the_importer_has_to_handle(self):
        d = seeded()
        self.assertTrue(any(d["ledger_sum"].values()), "la base sembrada debe tener resúmenes compactados")
        self.assertTrue(any(c["recaps"] for c in d["circles"].values()), "y al menos un cierre semanal")
        reasons = {r["r"] for rows in d["ledger"].values() for r in rows}
        # (el bono del miércoles no se pide: depende del día de la semana en que corre la prueba)
        for reason in ("weekly.reward", "market.buy", "transfer.in", "transfer.out", "store.buy", "poker"):
            self.assertIn(reason, reasons)

    def test_counts_follow_the_file(self):
        d = seeded()
        counts = imp.plan_from(d).counts()
        self.assertEqual(counts["profiles"], len(d["users"]))
        self.assertEqual(counts["accounts"] - len({s for s in imp.plan_from(d).balances if s[0] == "system"}), 3 * len(d["users"]))
        self.assertEqual(counts["circles"], len(d["circles"]))
        self.assertEqual(counts["circle_members"], sum(len(c["members"]) for c in d["circles"].values()))
        self.assertEqual(counts["markets"], len(d["markets"]))
        self.assertEqual(counts["market_trades"], sum(len(m["trades"]) for m in d["markets"].values()))
        self.assertEqual(counts["ledger_entries"], 2 * counts["ledger_transactions"])
        self.assertEqual(counts["week_closes"], sum(len(c["recaps"]) for c in d["circles"].values()))

    def test_every_transaction_adds_up_to_zero_and_the_whole_book_too(self):
        plan = imp.plan_from(seeded())
        for t in plan.transactions:
            self.assertEqual(sum(c for _, c in t["lines"]), 0, t["key"])
            self.assertTrue(all(c != 0 for _, c in t["lines"]), t["key"])
        self.assertEqual(sum(plan.balances.values()), 0)
        self.assertEqual(len({t["key"] for t in plan.transactions}), len(plan.transactions), "las claves no se repiten")

    def test_the_same_file_gives_the_same_ids(self):
        a, b = imp.plan_from(seeded()), imp.plan_from(seeded())
        self.assertEqual([r["id"] for r in a.rows["profiles"]], [r["id"] for r in b.rows["profiles"]])

    def test_money_is_whole_cents(self):
        plan = imp.plan_from(seeded())
        for table, column in (("market_positions", "invested"), ("market_trades", "amount"), ("casino_rounds", "bet"),
                              ("week_snapshots", "holding"), ("week_standings", "value"), ("week_rewards", "amount")):
            for r in plan.rows[table]:
                self.assertIsInstance(r[column], int, f"{table}.{column}")

    def test_the_command_line_reads_the_file_and_never_changes_it(self):
        path = SEEDED["path"]
        before = digest(path)
        p = subprocess.run([sys.executable, "-m", "backend.datos.importar_archivo", "--simular", path], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("0 diferencias", p.stdout)
        self.assertIn("ledger_transactions", p.stdout)
        self.assertEqual(digest(path), before)


class CadaDiferenciaSeLista(unittest.TestCase):
    def differences(self, d):
        return imp.plan_from(d).differences

    def test_a_balance_that_does_not_match_its_book(self):
        d = seeded()
        uid = first_user(d)
        d["users"][uid]["balance"] = round(d["users"][uid]["balance"] + 0.01, 2)
        diffs = self.differences(d)
        self.assertEqual(len(diffs), 1, diffs)
        self.assertIn(uid, diffs[0])
        self.assertIn("weekly", diffs[0])
        self.assertIn("diferencia 1)", diffs[0])

    def test_a_missing_row_in_the_middle_of_the_book(self):
        d = seeded()
        uid = next(u for u, rows in d["ledger"].items() if len(rows) > 3)
        rows = d["ledger"][uid]
        gone = rows.pop(len(rows) // 2)
        diffs = self.differences(d)
        self.assertTrue(any(uid in x and gone["a"] in x for x in diffs), diffs)

    def test_the_accumulated_account_is_checked_too(self):
        d = seeded()
        uid = first_user(d)
        d["users"][uid]["accum"] = d["users"][uid].get("accum", 0) + 5
        self.assertTrue(any(uid in x and "accumulated" in x for x in self.differences(d)))

    def test_rows_of_someone_who_does_not_exist(self):
        d = seeded()
        d["ledger"]["ffffffffffff"] = [{"id": "x1", "t": 1, "a": "weekly", "c": 100, "b": 100, "r": "casino.dice"}]
        self.assertTrue(any("ffffffffffff" in x for x in self.differences(d)))

    def test_a_book_that_goes_below_zero(self):
        d = seeded()
        uid = first_user(d)
        d["ledger"][uid].insert(0, {"id": "neg1", "t": 1, "a": "accumulated", "c": -10_000_000, "b": -10_000_000, "r": "store.buy"})
        d["ledger"][uid].insert(1, {"id": "neg2", "t": 2, "a": "accumulated", "c": 10_000_000, "b": 0, "r": "deposit"})
        diffs = self.differences(d)
        self.assertTrue(any("neg1" in x and "queda en" in x for x in diffs), diffs)

    def test_a_name_the_schema_would_refuse(self):
        d = seeded()
        uid = first_user(d)
        d["users"][uid]["username"] = "no vale"
        self.assertTrue(any("no vale" in x for x in self.differences(d)))

    def test_differences_are_listed_not_fixed_and_the_exit_code_says_so(self):
        d = seeded()
        uid = first_user(d)
        d["users"][uid]["balance"] = d["users"][uid]["balance"] + 1
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "db.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
        p = subprocess.run([sys.executable, "-m", "backend.datos.importar_archivo", "--simular", path], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(p.returncode, 1)
        self.assertIn("1 diferencias", p.stdout)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["users"][uid]["balance"], d["users"][uid]["balance"])

    def test_the_report_prints(self):
        out = io.StringIO()
        imp.report(imp.plan_from(seeded()), out)
        self.assertIn("profiles", out.getvalue())


@unittest.skipUnless(pg_local.AVAILABLE, pg_local.WHY_NOT)
class ElPlanEntraAlLibroSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.d = seeded()
        cls.plan = imp.plan_from(cls.d)
        cls.dsn = pg_local.fresh_database()
        cls.ids = imp.aplicar(cls.plan, cls.dsn)
        cls.conn = psycopg.connect(cls.dsn, autocommit=True)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def balance(self, account_id):
        return self.conn.execute("select balance_of(%s)", (account_id,)).fetchone()[0]

    def test_every_person_account_has_the_balance_of_the_file(self):
        for uid, u in self.d["users"].items():
            for kind, field in imp.PERSON_ACCOUNTS:
                with self.subTest(user=u["username"], account=kind):
                    self.assertEqual(self.balance(self.ids[("person", uid, kind)]), imp.to_cents(u.get(field, 0)))

    def test_the_book_audits_clean_and_adds_up_to_zero(self):
        self.assertEqual(self.conn.execute("select * from ledger_audit()").fetchall(), [])
        self.assertEqual(self.conn.execute("select coalesce(sum(amount), 0) from ledger_entries").fetchone()[0], 0)

    def test_every_table_got_what_the_plan_said(self):
        for table, n in self.plan.counts().items():
            with self.subTest(table=table):
                self.assertEqual(self.conn.execute(f"select count(*) from {table}").fetchone()[0], n)

    def test_chips_accounts_exist_and_are_off(self):
        self.assertEqual(self.conn.execute("select count(*) from accounts where kind = 'chips' and enabled").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("select count(*) from accounts where kind = 'chips'").fetchone()[0], len(self.d["users"]))

    def test_paid_rewards_point_at_their_payment_when_it_is_still_in_full(self):
        linked = self.conn.execute("select count(*) from week_rewards r join ledger_transactions t on t.id = r.transaction_id "
                                   "where t.reason = 'weekly.reward'").fetchone()[0]
        paid = self.conn.execute("select count(*) from week_rewards where paid").fetchone()[0]
        compacted = self.plan.notes.get("premios pagados cuyo renglón ya estaba compactado (sin transacción enlazada)", 0)
        self.assertEqual(linked + compacted, paid)
        self.assertGreater(linked, 0)

    def test_importing_twice_moves_no_money_twice(self):
        import psycopg
        from psycopg.types.json import Jsonb
        t = self.plan.transactions[0]
        with psycopg.connect(self.dsn, autocommit=True) as c:
            again = c.execute("select post_transaction(%s, %s, %s, %s)",
                              (t["key"], t["reason"], Jsonb([{"account": self.ids[a], "amount": v} for a, v in t["lines"]]),
                               Jsonb(t["meta"]))).fetchone()[0]
        self.assertEqual(self.conn.execute("select count(*) from ledger_transactions where id = %s", (again,)).fetchone()[0], 1)
        self.test_the_book_audits_clean_and_adds_up_to_zero()


if __name__ == "__main__":
    unittest.main()
