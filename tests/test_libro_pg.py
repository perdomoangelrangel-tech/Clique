"""El libro en SQL (supabase/migrations/*_libro.sql): post_transaction y balance_of, regla por regla, sobre un Postgres
local. Cada regla tiene un mutante en backend/datos/mutantes.py que la rompe y debe poner en rojo su prueba aquí.

Sin psycopg y pgserver instalados, estas pruebas se omiten con un aviso (no fallan)."""
import itertools
import random
import threading
import unittest
import uuid

from backend.datos import pg_local

if pg_local.AVAILABLE:
    import psycopg
    from psycopg.types.json import Jsonb

_keys = itertools.count(1)


def key(tag="k"):
    return f"{tag}-{next(_keys)}-{uuid.uuid4().hex[:8]}"


class Ledger:
    """Lo que hace el servidor: llamar a las funciones del libro como service_role."""

    def __init__(self, dsn):
        self.dsn = dsn
        self.conn = psycopg.connect(dsn, autocommit=True)

    def close(self):
        self.conn.close()

    def person(self, name=None):
        uid = uuid.uuid4()
        name = name or "p" + uid.hex[:10]
        self.conn.execute("insert into profiles (id, username) values (%s, %s)", (uid, name))
        self.conn.execute("select open_accounts(%s)", (uid,))
        rows = self.conn.execute("select kind, id from accounts where owner_id = %s", (uid,)).fetchall()
        return uid, dict(rows)

    def system(self, code):
        return self.conn.execute("select system_account(%s)", (code,)).fetchone()[0]

    def post(self, idem, reason, lines, conn=None):
        conn = conn or self.conn
        with conn.transaction():
            conn.execute("set local role service_role")
            return conn.execute("select post_transaction(%s, %s, %s)",
                                (idem, reason, Jsonb([{"account": a, "amount": c} for a, c in lines]))).fetchone()[0]

    def fund(self, account, cents):
        return self.post(key("fund"), "test.setup", [(self.system("external"), -cents), (account, cents)])

    def balance(self, account):
        return self.conn.execute("select balance_of(%s)", (account,)).fetchone()[0]

    def stored(self, account):
        return self.conn.execute("select balance from accounts where id = %s", (account,)).fetchone()[0]

    def count(self, table):
        return self.conn.execute(f"select count(*) from {table}").fetchone()[0]

    def audit(self):
        return self.conn.execute("select * from ledger_audit()").fetchall()


@unittest.skipUnless(pg_local.AVAILABLE, pg_local.WHY_NOT)
class LibroBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = pg_local.fresh_database()

    def setUp(self):
        self.L = Ledger(self.dsn)
        self.addCleanup(self.L.close)
        self.ana, self.a = self.L.person()
        self.beto, self.b = self.L.person()
        self.L.fund(self.a["weekly"], 10_000)

    def refused(self, code, idem, lines, reason="test.move"):
        before = (self.L.count("ledger_transactions"), self.L.count("ledger_entries"))
        with self.assertRaises(psycopg.errors.RaiseException) as cm:
            self.L.post(idem, reason, lines)
        self.assertTrue(str(cm.exception).startswith(code + ":"), str(cm.exception))
        self.assertEqual((self.L.count("ledger_transactions"), self.L.count("ledger_entries")), before,
                         "un movimiento rechazado no deja nada escrito")
        self.assertEqual(self.L.audit(), [])
        return cm.exception


class UnMovimientoQueSumaCero(LibroBase):
    def test_moves_money_and_writes_one_entry_per_line(self):
        tx = self.L.post(key(), "transfer", [(self.a["weekly"], -2_500), (self.b["weekly"], 2_500)])
        self.assertEqual((self.L.balance(self.a["weekly"]), self.L.balance(self.b["weekly"])), (7_500, 2_500))
        self.assertEqual((self.L.stored(self.a["weekly"]), self.L.stored(self.b["weekly"])), (7_500, 2_500))
        rows = self.L.conn.execute("select account_id, amount, balance_after from ledger_entries where transaction_id = %s "
                                   "order by account_id", (tx,)).fetchall()
        self.assertEqual(sorted(rows), sorted([(self.a["weekly"], -2_500, 7_500), (self.b["weekly"], 2_500, 2_500)]))
        self.assertEqual(self.L.audit(), [])

    def test_lines_that_do_not_add_up_to_zero_are_refused(self):
        self.refused("unbalanced", key(), [(self.a["weekly"], -2_500), (self.b["weekly"], 2_499)])
        self.refused("unbalanced", key(), [(self.a["weekly"], -1), (self.b["weekly"], 2)])
        self.assertEqual(self.L.balance(self.a["weekly"]), 10_000)

    def test_three_way_moves_are_fine_when_they_add_up(self):
        casino = self.L.system("casino")
        self.L.post(key(), "casino.split", [(self.a["weekly"], -300), (self.b["weekly"], 200), (casino, 100)])
        self.assertEqual((self.L.balance(self.a["weekly"]), self.L.balance(self.b["weekly"])), (9_700, 200))

    def test_badly_shaped_lines_are_refused(self):
        w, v = self.a["weekly"], self.b["weekly"]
        self.refused("invalid_lines", key(), [(w, 0), (v, 0)])
        self.refused("invalid_lines", key(), [(w, -10)])
        self.refused("invalid_lines", key(), [(w, -10), (w, 10)])
        self.refused("invalid_lines", key(), [(w, -10.5), (v, 10.5)])
        self.refused("unknown_account", key(), [(w, -10), (987654321, 10)])

    def test_the_reason_and_the_key_are_required(self):
        self.refused("invalid_idempotency_key", "", [(self.a["weekly"], -1), (self.b["weekly"], 1)])
        self.refused("invalid_reason", key(), [(self.a["weekly"], -1), (self.b["weekly"], 1)], reason="")


class NingunaCuentaDePersonaQuedaNegativa(LibroBase):
    def test_taking_more_than_a_person_has_is_refused(self):
        self.refused("insufficient_funds", key(), [(self.a["weekly"], -10_001), (self.b["weekly"], 10_001)])
        self.assertEqual(self.L.balance(self.a["weekly"]), 10_000)

    def test_taking_exactly_what_there_is_leaves_zero(self):
        self.L.post(key(), "all.in", [(self.a["weekly"], -10_000), (self.b["weekly"], 10_000)])
        self.assertEqual(self.L.balance(self.a["weekly"]), 0)

    def test_an_empty_account_cannot_pay(self):
        self.refused("insufficient_funds", key(), [(self.b["accumulated"], -1), (self.a["accumulated"], 1)])

    def test_system_accounts_may_go_below_zero(self):
        casino = self.L.system("casino")
        self.L.post(key(), "casino.win", [(casino, -5_000), (self.b["weekly"], 5_000)])
        self.assertEqual(self.L.balance(casino), -5_000)


class LasFichasCompradasEstanApagadas(LibroBase):
    def test_chips_cannot_move_while_switched_off(self):
        self.refused("account_disabled", key(), [(self.L.system("store"), -500), (self.a["chips"], 500)])

    def test_purchases_are_switched_off(self):
        value = self.L.conn.execute("select value from app_settings where key = 'purchases_enabled'").fetchone()[0]
        self.assertIs(value, False)


class LaMismaClaveDevuelveLaMismaTransaccion(LibroBase):
    def test_a_retry_returns_the_first_transaction_and_moves_nothing(self):
        k = key("retry")
        first = self.L.post(k, "transfer", [(self.a["weekly"], -1_000), (self.b["weekly"], 1_000)])
        again = self.L.post(k, "transfer", [(self.a["weekly"], -1_000), (self.b["weekly"], 1_000)])
        self.assertEqual(first, again)
        self.assertEqual(self.L.balance(self.a["weekly"]), 9_000)
        self.assertEqual(self.L.conn.execute("select count(*) from ledger_entries where transaction_id = %s", (first,)).fetchone()[0], 2)

    def test_the_order_of_the_lines_does_not_change_the_request(self):
        k = key("order")
        first = self.L.post(k, "transfer", [(self.a["weekly"], -1_000), (self.b["weekly"], 1_000)])
        self.assertEqual(self.L.post(k, "transfer", [(self.b["weekly"], 1_000), (self.a["weekly"], -1_000)]), first)

    def test_the_same_key_for_something_else_is_refused(self):
        k = key("clash")
        self.L.post(k, "transfer", [(self.a["weekly"], -1_000), (self.b["weekly"], 1_000)])
        self.refused("idempotency_conflict", k, [(self.a["weekly"], -2_000), (self.b["weekly"], 2_000)])
        self.refused("idempotency_conflict", k, [(self.a["weekly"], -1_000), (self.b["weekly"], 1_000)], reason="other")
        self.assertEqual(self.L.balance(self.a["weekly"]), 9_000)

    def test_a_refused_move_does_not_burn_its_key(self):
        k = key("later")
        self.refused("insufficient_funds", k, [(self.b["weekly"], -500), (self.a["weekly"], 500)])
        self.L.post(k, "transfer", [(self.a["weekly"], -500), (self.b["weekly"], 500)])
        self.assertEqual(self.L.balance(self.b["weekly"]), 500)

    def test_the_same_key_from_many_threads_moves_money_once(self):
        k, ids, errors = key("race"), [], []

        def go():
            c = psycopg.connect(self.dsn, autocommit=True)
            try:
                ids.append(self.L.post(k, "transfer", [(self.a["weekly"], -700), (self.b["weekly"], 700)], conn=c))
            except Exception as e:                                        # pragma: no cover
                errors.append(repr(e))
            finally:
                c.close()

        threads = [threading.Thread(target=go) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.L.balance(self.b["weekly"]), 700)


class LosCandadosVanEnOrdenFijo(LibroBase):
    def test_crossed_payments_never_deadlock(self):
        """Ana le paga a Beto y Beto a Ana al mismo tiempo, cada uno escribiendo las líneas en su orden. Si los candados se
        tomaran en el orden de llegada, Postgres mataría una de las dos por interbloqueo (40P01)."""
        self.L.fund(self.b["weekly"], 10_000)
        errors = []

        def pay(src, dst, n):
            c = psycopg.connect(self.dsn, autocommit=True)
            try:
                for _ in range(n):
                    with c.transaction():
                        c.execute("set local role service_role")
                        # mantiene el candado un momento, para que el otro hilo llegue en medio
                        c.execute("select post_transaction(%s, 'cross', %s), pg_sleep(0.002)",
                                  (key("x"), Jsonb([{"account": src, "amount": -1}, {"account": dst, "amount": 1}])))
            except Exception as e:
                errors.append(type(e).__name__ + ": " + str(e).splitlines()[0])
            finally:
                c.close()

        threads = [threading.Thread(target=pay, args=(self.a["weekly"], self.b["weekly"], 60)),
                   threading.Thread(target=pay, args=(self.b["weekly"], self.a["weekly"], 60)),
                   threading.Thread(target=pay, args=(self.a["weekly"], self.b["weekly"], 60)),
                   threading.Thread(target=pay, args=(self.b["weekly"], self.a["weekly"], 60))]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.L.balance(self.a["weekly"]) + self.L.balance(self.b["weekly"]), 20_000)
        self.assertEqual(self.L.audit(), [])


class VeinteHilosPagandoALaVez(LibroBase):
    def test_no_cent_is_lost(self):
        people = [self.L.person() for _ in range(6)]
        accounts = [acc["weekly"] for _, acc in people]
        for acc in accounts:
            self.L.fund(acc, 5_000)
        casino = self.L.system("casino")
        total_before = sum(self.L.balance(a) for a in accounts) + self.L.balance(casino)
        done, refused, errors = [], [], []

        def worker(seed):
            rnd = random.Random(seed)
            c = psycopg.connect(self.dsn, autocommit=True)
            try:
                for _ in range(25):
                    src, dst = rnd.sample(accounts + [casino], 2)
                    amount = rnd.randint(1, 900)
                    try:
                        done.append(self.L.post(key("w"), "load", [(src, -amount), (dst, amount)], conn=c))
                    except psycopg.errors.RaiseException as e:
                        if not str(e).startswith("insufficient_funds:"):
                            raise
                        refused.append(1)
            except Exception as e:                                        # pragma: no cover
                errors.append(type(e).__name__ + ": " + str(e).splitlines()[0])
            finally:
                c.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(done) + len(refused), 20 * 25)
        self.assertEqual(sum(self.L.balance(a) for a in accounts) + self.L.balance(casino), total_before)
        self.assertTrue(all(self.L.balance(a) >= 0 for a in accounts))
        self.assertEqual(self.L.audit(), [])
        moved = self.L.conn.execute("select count(*) from ledger_entries where transaction_id = any(%s)", (done,)).fetchone()[0]
        self.assertEqual(moved, 2 * len(done))


class SoloElServidorMueveDinero(LibroBase):
    def test_the_browser_cannot_call_the_ledger(self):
        c = psycopg.connect(self.dsn)
        try:
            for fn, args in (("post_transaction(%s, %s, %s)", (key(), "hack", Jsonb([{"account": self.a["weekly"], "amount": -1},
                                                                                        {"account": self.b["weekly"], "amount": 1}]))),
                             ("balance_of(%s)", (self.a["weekly"],))):
                for role in ("authenticated", "anon"):
                    with self.subTest(fn=fn, role=role):
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            with c.transaction():
                                pg_local.as_user(c, self.ana)
                                c.execute(f"set local role {role}")
                                c.execute(f"select {fn}", args)
        finally:
            c.close()
        self.assertEqual(self.L.balance(self.a["weekly"]), 10_000)

    def test_the_browser_cannot_write_a_balance(self):
        c = psycopg.connect(self.dsn)
        try:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with c.transaction():
                    pg_local.as_user(c, self.ana)
                    c.execute("update accounts set balance = balance + 100 where owner_id = %s", (self.ana,))
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
