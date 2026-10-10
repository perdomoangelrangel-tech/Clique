"""The Portfolio page's numbers: where the weekly money and the accumulated money are, plus the shares and the polls."""
import os
import sys
import tempfile
import threading
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                                  # noqa: E402
from backend import exchange, games, ledger, markets, wealth          # noqa: E402
from backend.store import db, store                                           # noqa: E402
from tests.econ import books_balance, circle_of, mk                           # noqa: E402
from tests.helpers import fresh_store, restore_store_path                     # noqa: E402
from tests.test_exchange import T0, new_engine                                # noqa: E402
from tests.test_http import Client                                            # noqa: E402


def tearDownModule():
    restore_store_path()
    exchange.engine = None


def parts(section):
    return {p["key"]: p["amount"] for p in section["parts"]}


class WhereTheMoneyIs(unittest.TestCase):
    def setUp(self):
        fresh_store()
        exchange.engine = new_engine(1)
        exchange.QUOTES.clear()
        self.now = T0 + 5000
        self.u = mk("alice", weekly=1000, accum=2000)
        self.maker = mk("maker")
        self.c = circle_of(self.maker, self.u)

    def poll(self, question="Will the portfolio add up?"):
        return markets.create(self.maker, {"circleId": self.c["id"], "question": question})

    def buy_shares(self, sym="NEXO", n=10):
        q = exchange.quote(self.u, {"symbol": sym, "side": "buy", "shares": n}, self.now)
        return exchange.trade(self.u, {"quoteId": q["quoteId"]}, self.now)

    def test_a_person_with_nothing_working_has_all_cash_and_empty_lists(self):
        o = wealth.overview(self.u)
        self.assertEqual(parts(o["weekly"]), {"cash": 1000.0, "polls": 0.0, "casino": 0.0, "poker": 0.0})
        self.assertEqual(parts(o["accumulated"]), {"cash": 2000.0, "stocks": 0.0})
        self.assertEqual((o["weekly"]["total"], o["accumulated"]["total"], o["total"]), (1000.0, 2000.0, 3000.0))
        self.assertEqual(o["polls"]["open"], [])
        self.assertEqual(o["polls"]["closed"], [])
        self.assertEqual(o["stocks"]["positions"], [])

    def test_open_poll_bets_are_part_of_the_weekly_money_at_their_cash_out_value(self):
        m = self.poll()
        markets.trade(self.u, m, {"outcome": 0, "amount": 100})
        o = wealth.overview(self.u)
        p = parts(o["weekly"])
        self.assertAlmostEqual(p["cash"], 900.0, places=2)
        self.assertGreater(p["polls"], 90)
        self.assertLessEqual(p["polls"], 100, "cashing out right away never returns more than was paid")
        self.assertAlmostEqual(p["cash"] + p["polls"], o["weekly"]["total"], places=2)
        (row,) = o["polls"]["open"]
        self.assertEqual((row["market"], row["invested"], row["settled"]), (m["id"], 100.0, False))
        self.assertAlmostEqual(row["value"], p["polls"], places=2)
        self.assertEqual(o["polls"]["openInvested"], 100.0)
        self.assertIn("closes", row)

    def test_the_weekly_total_is_what_the_weekly_leaderboard_calls_holding(self):
        m = self.poll()
        markets.trade(self.u, m, {"outcome": 0, "amount": 150})
        games.chicken_start(self.u, {"amount": 20, "difficulty": "medium"})
        games.hilo_start(self.u, {"amount": 30})
        o = wealth.overview(self.u)
        self.assertEqual(parts(o["weekly"])["casino"], 50.0, "both rounds still in play are counted")
        self.assertNotIn("races", parts(o["weekly"]))
        self.assertAlmostEqual(o["weekly"]["total"], markets.net_worth(self.u), delta=0.05)

    def test_what_you_spent_on_a_stock_moves_from_cash_to_shares_and_only_the_spread_is_lost(self):
        before = wealth.overview(self.u)
        r = self.buy_shares("NEXO", 10)
        after = wealth.overview(self.u)
        self.assertAlmostEqual(parts(after["accumulated"])["cash"], 2000 - r["total"], places=2)
        self.assertGreater(parts(after["accumulated"])["stocks"], 0)
        lost = before["accumulated"]["total"] - after["accumulated"]["total"]
        self.assertGreaterEqual(lost, 0, "buying never makes money")
        self.assertLess(lost, 0.01 * r["total"], "and costs only the gap between buying and selling price")
        self.assertEqual(before["weekly"]["total"], after["weekly"]["total"], "the weekly account is not touched")

    def test_shares_are_listed_with_what_they_cost_and_are_worth(self):
        self.buy_shares("NEXO", 10)
        self.buy_shares("ATLS", 3)
        o = wealth.overview(self.u)
        values = [p["value"] for p in o["stocks"]["positions"]]
        self.assertEqual(values, sorted(values, reverse=True), "biggest holding first")
        by = {p["symbol"]: p for p in o["stocks"]["positions"]}
        self.assertEqual((by["NEXO"]["shares"], by["ATLS"]["shares"]), (10, 3))
        self.assertAlmostEqual(o["stocks"]["value"], sum(p["value"] for p in by.values()), places=2)
        self.assertAlmostEqual(o["stocks"]["unrealized"], o["stocks"]["value"] - o["stocks"]["invested"], places=2)
        self.assertAlmostEqual(parts(o["accumulated"])["stocks"], o["stocks"]["value"], places=2)

    def test_settled_polls_are_listed_with_what_they_paid(self):
        m = self.poll("Will it end?")
        markets.trade(self.u, m, {"outcome": 0, "amount": 50})
        markets.resolve(self.maker, m, 0)
        o = wealth.overview(self.u)
        self.assertEqual(o["polls"]["open"], [])
        (row,) = o["polls"]["closed"]
        self.assertTrue(row["settled"])
        self.assertGreater(row["value"], 50, "a winning bet pays more than it cost")
        self.assertAlmostEqual(parts(o["weekly"])["cash"], ledger.balance(self.u, "weekly"), places=2)
        self.assertEqual(parts(o["weekly"])["polls"], 0.0)

    def test_practice_money_is_not_in_it(self):
        demo = games.account_for(self.u, True)
        games.chicken_start(demo, {"amount": 50, "difficulty": "medium"})
        o = wealth.overview(self.u)
        self.assertEqual((parts(o["weekly"])["casino"], o["weekly"]["total"]), (0.0, 1000.0))

    def test_when_the_exchange_is_not_open_the_rest_still_works(self):
        exchange.engine = None
        o = wealth.overview(self.u)
        self.assertIsNone(o["stocks"])
        self.assertEqual(parts(o["accumulated"]), {"cash": 2000.0, "stocks": 0.0})

    def test_looking_changes_nothing(self):
        m = self.poll()
        markets.trade(self.u, m, {"outcome": 0, "amount": 40})
        self.buy_shares("MARE", 4)
        snapshot = (self.u["balance"], self.u["accum"], len(db()["ledger"].get(self.u["id"], [])), self.u.get("trades") and len(self.u["trades"]))
        a, b = wealth.overview(self.u), wealth.overview(self.u)
        self.assertEqual(a, b)
        self.assertEqual(snapshot, (self.u["balance"], self.u["accum"], len(db()["ledger"].get(self.u["id"], [])), self.u.get("trades") and len(self.u["trades"])))
        self.assertTrue(books_balance(self.u))


class ThroughTheServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.data = {}
        store.load()
        exchange.engine = new_engine(2)
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        exchange.engine = None

    def test_you_must_be_signed_in_and_only_ever_see_your_own(self):
        anon = Client(self.port)
        self.assertEqual(anon.call("GET", "/api/portfolio/overview")[0], 401)
        a, b = Client(self.port), Client(self.port)
        a.call("POST", "/api/auth/register", {"username": "folio_ann", "password": "secret123"})
        b.call("POST", "/api/auth/register", {"username": "folio_ben", "password": "secret123"})
        st, d = a.call("GET", "/api/portfolio/overview")
        self.assertEqual(st, 200)
        self.assertEqual(d["weekly"]["total"], 1000.0)
        self.assertEqual(set(d), {"weekly", "accumulated", "total", "stocks", "polls"})
        _, other = b.call("GET", "/api/portfolio/overview")
        self.assertEqual(other["polls"]["open"], [])


if __name__ == "__main__":
    unittest.main()
