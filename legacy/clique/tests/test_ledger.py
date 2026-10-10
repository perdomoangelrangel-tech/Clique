"""The two accounts and the ledger that records every movement in them."""
import os
import random
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from backend import config, economy, games, ledger, users   # noqa: E402
from backend.store import db, store                         # noqa: E402
from backend.util import ApiError                           # noqa: E402
from tests.econ import books_balance, mk                    # noqa: E402
from tests.helpers import fresh_store, restore_store_path   # noqa: E402
from tests.test_http import Client                          # noqa: E402


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


class TwoAccounts(unittest.TestCase):
    def setUp(self):
        fresh_store()

    def test_a_new_member_gets_the_welcome_money_in_the_weekly_account_only(self):
        u = users.register("alice", "secret123")
        self.assertEqual((u["balance"], u["accum"]), (config.START_BALANCE, 0.0))
        self.assertEqual(ledger.balance(u, "weekly"), config.START_BALANCE)
        self.assertEqual(ledger.balance(u, "accumulated"), 0.0)
        rows = ledger.entries(u)
        self.assertEqual([(r["account"], r["reason"], r["amount"], r["external"]) for r in rows],
                         [("weekly", "welcome", config.START_BALANCE, True)])
        self.assertTrue(books_balance(u))

    def test_weekly_money_cannot_pay_from_the_accumulated_account_or_the_other_way_round(self):
        u = mk("alice", 100, 50)
        err(ledger.post, u, "accumulated", -50.01, "test")
        err(ledger.post, u, "weekly", -100.01, "test")
        self.assertEqual((u["balance"], u["accum"]), (100.0, 50.0))
        ledger.post(u, "accumulated", -50, "test")
        self.assertEqual((u["balance"], u["accum"]), (100.0, 0.0))

    def test_there_is_no_way_to_move_money_between_the_accounts(self):
        # The only "transfer" there is moves money between two FRIENDS, accumulated to accumulated (tests/test_transfers.py proves it can
        # never reach the weekly account). Nothing moves money from one account of the same person to their other one.
        paths = {r[1].pattern for r in server.ROUTES if "/api/transfers" not in r[1].pattern}
        for p in paths:
            self.assertNotIn("transfer", p)
        self.assertNotIn("transfer", " ".join(n for n in dir(ledger) if not n.startswith("_")))

    def test_a_row_says_what_where_when_and_how_much(self):
        u = mk("alice")
        row = ledger.post(u, "accumulated", 12.34, "weekly.reward", ref="2026-09-28:abc")
        self.assertEqual(set(row) - {"x", "n", "i", "e"}, {"id", "t", "a", "c", "b", "r"})
        self.assertEqual((row["a"], row["c"], row["b"], row["r"], row["x"]), ("accumulated", 1234, 1234, "weekly.reward", "2026-09-28:abc"))
        self.assertTrue(row["id"])
        self.assertAlmostEqual(row["t"] / 1000, __import__("time").time(), delta=5)

    def test_cents_never_drift(self):
        u = mk("alice", 0.0)
        for _ in range(1000):
            ledger.post(u, "weekly", 0.1, "test")
        self.assertEqual(u["balance"], 100.0)
        for _ in range(1000):
            ledger.post(u, "weekly", -0.1, "test")
        self.assertEqual(u["balance"], 0.0)
        self.assertEqual(ledger.balance_c(u, "weekly"), 0)
        ledger.post(u, "weekly", 0.07, "test")
        ledger.post(u, "weekly", 0.01, "test")
        self.assertEqual(ledger.balance_c(u, "weekly"), 8)

    def test_random_activity_always_adds_up(self):
        rng = random.Random(7)
        u = mk("alice", 500, 500)
        for _ in range(1500):
            acct = rng.choice(ledger.ACCOUNTS)
            amount = round(rng.uniform(-30, 30), 2)
            try:
                ledger.post(u, acct, amount, rng.choice(["a", "b", "c"]), external=rng.random() < .2)
            except ApiError:
                pass
            self.assertGreaterEqual(u["balance"], 0)
            self.assertGreaterEqual(u["accum"], 0)
        self.assertTrue(books_balance(u))
        self.assertLessEqual(len(db()["ledger"][u["id"]]), economy.LEDGER_KEEP + 50)

    def test_old_rows_are_folded_into_weekly_totals_and_the_books_still_balance(self):
        u = mk("alice", 0.0)
        with mock.patch.object(economy, "LEDGER_KEEP", 60):
            for i in range(300):
                ledger.post(u, "weekly", 1.0, "casino.dice")
        self.assertTrue(books_balance(u))
        summary = ledger.summaries(u)
        self.assertTrue(summary)
        self.assertEqual(sum(r["amount"] for r in summary) + sum(r["amount"] for r in ledger.entries(u, limit=500)), u["balance"])

    def test_a_transaction_id_makes_a_retry_harmless(self):
        u = mk("alice", 0.0, 0.0)
        a = ledger.post(u, "accumulated", 100, "weekly.reward", txid="reward:x:y:z")
        b = ledger.post(u, "accumulated", 100, "weekly.reward", txid="reward:x:y:z")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(u["accum"], 100.0)
        ledger.post(u, "accumulated", 100, "weekly.reward", txid="reward:x:y:other")
        self.assertEqual(u["accum"], 200.0)

    def test_the_practice_wallet_never_touches_the_ledger(self):
        u = mk("alice", 1000)
        d = games.demo_account(u)
        before = len(db()["ledger"][u["id"]])
        users.credit(d, 50)
        users.debit(d, 20)
        self.assertEqual(d["balance"], 1030.0)
        self.assertEqual(len(db()["ledger"][u["id"]]), before)
        self.assertEqual(u["balance"], 1000.0)

    def test_external_money_is_marked_and_kept_out_of_this_weeks_performance(self):
        u = mk("alice", 1000)
        users.deposit(u, 5000, config.ADMIN_PASSWORD)
        users.deposit(u, 700, config.ADMIN_PASSWORD, "accumulated")
        self.assertEqual((u["balance"], u["accum"]), (6000.0, 700.0))
        ext = [r for r in ledger.entries(u) if r["external"] and r["reason"] != "welcome"]
        self.assertEqual({(r["account"], r["amount"]) for r in ext}, {("weekly", 5000.0), ("accumulated", 700.0)})
        self.assertEqual(u["wk"]["ext_c"], 500000, "only the weekly top-up counts as handed over")
        self.assertTrue(books_balance(u))

    def test_deposit_account_must_be_a_real_one(self):
        u = mk("alice", 1000)
        self.assertIn("weekly or the accumulated", err(users.deposit, u, 5, config.ADMIN_PASSWORD, "savings").message)
        self.assertEqual(u["balance"], 1000.0)

    def test_the_voucher_is_external_money_in_the_weekly_account(self):
        u = mk("alice", 0.1)
        users.redeem_voucher(u)
        row = ledger.entries(u)[0]
        self.assertEqual((row["account"], row["reason"], row["amount"], row["external"]), ("weekly", "voucher", 250.0, True))


class EveryMovementIsRecorded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_casino_rounds_and_market_trades_leave_rows_with_a_reason_and_the_statement_matches(self):
        c = Client(self.port)
        st, d = c.call("POST", "/api/auth/register", {"username": "ledgerlad", "password": "secret123"})
        self.assertEqual(st, 200)
        self.assertEqual((d["user"]["weekly"], d["user"]["accum"], d["user"]["balance"]), (1000.0, 0.0, 1000.0))
        for _ in range(5):
            st, _ = c.call("POST", "/api/games/dice", {"amount": 5, "direction": "over", "target": 50})
            self.assertEqual(st, 200)
        st, circ = c.call("POST", "/api/circles", {"name": "Books", "visibility": "private"})
        st, m = c.call("POST", "/api/markets", {"circleId": circ["circle"]["id"], "question": "Will the books balance?"})
        mid = m["market"]["id"]
        st, _ = c.call("POST", f"/api/markets/{mid}/trade", {"outcome": 0, "amount": 20})
        self.assertEqual(st, 200)
        st, s = c.call("GET", "/api/ledger?limit=100")
        self.assertEqual(st, 200)
        reasons = [e["reason"] for e in s["entries"]]
        self.assertIn("market.buy", reasons)
        self.assertIn("casino.dice", reasons)
        self.assertIn("welcome", reasons)
        self.assertEqual(s["balances"]["weekly"], round(sum(e["amount"] for e in s["entries"] if e["account"] == "weekly"), 2))
        st, me = c.call("GET", "/api/me")
        self.assertEqual(me["user"]["weekly"], s["balances"]["weekly"])
        for e in s["entries"]:
            self.assertTrue(e["id"] and e["t"] and e["account"] in ledger.ACCOUNTS)
        self.assertEqual(c.call("GET", "/api/ledger?account=savings")[0], 400)

    def test_nobody_can_read_somebody_elses_statement(self):
        a, b = Client(self.port), Client(self.port)
        a.call("POST", "/api/auth/register", {"username": "privatea", "password": "secret123"})
        b.call("POST", "/api/auth/register", {"username": "privateb", "password": "secret123"})
        a.call("POST", "/api/games/dice", {"amount": 5, "direction": "over", "target": 50})
        _, sb = b.call("GET", "/api/ledger")
        self.assertEqual({e["reason"] for e in sb["entries"]}, {"welcome"})
        self.assertEqual(Client(self.port).call("GET", "/api/ledger")[0], 401)


if __name__ == "__main__":
    unittest.main()
