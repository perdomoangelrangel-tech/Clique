"""Site-wide bets, who-bet-what, and the portfolio breakdown."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, markets, users            # noqa: E402
from backend.store import store                        # noqa: E402
from backend.util import ApiError                      # noqa: E402
from tests.helpers import fresh_store, restore_store_path   # noqa: E402


def fresh():
    fresh_store()


def tearDownModule():
    restore_store_path()


def mk(name, funds=1000.0):
    u = users.register(name, "secret123")
    u["balance"] = float(funds)
    return u


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def circle_bet(owner, circle, question="Will the circle bet happen?", **extra):
    return markets.create(owner, {"circleId": circle["id"], "question": question, **extra})


def site_bet(owner, question="Will the whole site agree?", **extra):
    return markets.create(owner, {"scope": "site", "question": question, **extra})


class SiteWideBets(unittest.TestCase):
    def setUp(self):
        fresh()
        self.alice, self.bob = mk("alice"), mk("bobby")       # bob is in no circle at all
        self.crew = circles.create(self.alice, {"name": "Crew", "visibility": "private"})

    def test_everyone_signed_in_can_see_trade_and_comment(self):
        m = site_bet(self.alice)
        self.assertIsNone(m["circleId"])
        s = markets.summary(m, self.bob)
        self.assertEqual((s["scope"], s["circle"]), ("site", None))
        self.assertEqual([x["id"] for x in markets.list_markets(self.bob)], [m["id"]])
        markets.trade(self.bob, m, {"action": "buy", "outcome": 0, "side": "yes", "amount": 50})
        markets.add_comment(self.bob, m, "I'm in")
        d = markets.detail(m, self.bob)
        self.assertTrue(d["isMember"])
        self.assertEqual(d["myPositions"][0]["invested"], 50.0)
        self.assertEqual(users.get(self.bob["id"])["balance"], 950.0)

    def test_private_circle_bets_stay_hidden_from_outsiders(self):
        hidden = circle_bet(self.alice, self.crew)
        shown = site_bet(self.alice)
        ids = [x["id"] for x in markets.list_markets(self.bob)]
        self.assertEqual(ids, [shown["id"]])
        self.assertEqual(err(markets.view_or_404, hidden["id"], self.bob).status, 404)
        self.assertEqual(err(markets.trade, self.bob, hidden, {"action": "buy", "outcome": 0, "amount": 5}).status, 403)

    def test_site_filter_and_circle_filter(self):
        a = circle_bet(self.alice, self.crew)
        b = site_bet(self.alice)
        self.assertEqual([x["id"] for x in markets.list_markets(self.alice, circle="site")], [b["id"]])
        self.assertEqual([x["id"] for x in markets.list_markets(self.alice, circle=self.crew["id"])], [a["id"]])
        self.assertEqual(len(markets.list_markets(self.alice)), 2)

    def test_only_the_creator_settles_a_site_bet(self):
        m = site_bet(self.alice)
        markets.trade(self.bob, m, {"action": "buy", "outcome": 0, "side": "yes", "amount": 100})
        self.assertEqual(err(markets.resolve, self.bob, m, 0).status, 403)
        self.assertEqual(err(markets.cancel, self.bob, m).status, 403)
        self.assertFalse(markets.summary(m, self.bob)["canManage"])
        self.assertTrue(markets.summary(m, self.alice)["canManage"])
        paid = markets.resolve(self.alice, m, 0)
        self.assertGreater(paid, 100.0)
        self.assertGreater(users.get(self.bob["id"])["balance"], 1000.0)

    def test_cancel_refunds_a_site_bet(self):
        m = site_bet(self.alice)
        markets.trade(self.bob, m, {"action": "buy", "outcome": 1, "side": "yes", "amount": 80})
        markets.cancel(self.alice, m)
        self.assertEqual(users.get(self.bob["id"])["balance"], 1000.0)

    def test_circle_owner_still_settles_circle_bets_and_site_bets_have_no_owner(self):
        circles.join_by_code(self.bob, self.crew["inviteCode"])
        inside = circle_bet(self.bob, self.crew)
        self.assertTrue(markets.summary(inside, self.alice)["canManage"])        # alice owns the circle
        outside = site_bet(self.bob)
        self.assertFalse(markets.summary(outside, self.alice)["canManage"])      # but owns nothing site-wide
        self.assertEqual(err(markets.resolve, self.alice, outside, 0).status, 403)

    def test_cap_on_open_public_bets(self):
        for i in range(markets.MAX_OPEN_PUBLIC):
            site_bet(self.alice, f"Public question number {i}?")
        self.assertIn("open public bets", err(site_bet, self.alice, "One too many?").message)
        site_bet(self.bob, "A different person is fine?")           # the cap is per person


class WhoBetWhat(unittest.TestCase):
    def setUp(self):
        fresh()
        self.a, self.b, self.c = mk("alice"), mk("bobby"), mk("carol")
        self.m = site_bet(self.a, "Will it rain tomorrow?")

    def buy(self, user, outcome, amount):
        markets.trade(user, self.m, {"action": "buy", "outcome": outcome, "side": "yes", "amount": amount})

    def test_lists_each_person_with_their_side_and_amount_biggest_first(self):
        self.buy(self.a, 0, 100)
        self.buy(self.b, 1, 250)
        self.buy(self.c, 0, 40)
        rows = markets.detail(self.m, self.a)["holders"]
        self.assertEqual([(r["user"]["username"], r["label"], r["invested"]) for r in rows],
                         [("bobby", "No", 250.0), ("alice", "Yes", 100.0), ("carol", "Yes", 40.0)])
        for r in rows:
            self.assertGreater(r["shares"], r["invested"])           # shares cost less than $1 each
            self.assertTrue(0 < r["avgPrice"] < 1)
            self.assertIsNotNone(r["value"])
            self.assertFalse(r["settled"])
        self.assertEqual(markets.detail(self.m, self.a)["investedTotal"], 390.0)

    def test_adding_to_a_position_adds_to_the_investment(self):
        self.buy(self.a, 0, 30)
        self.buy(self.a, 0, 20)
        rows = markets.detail(self.m, self.b)["holders"]
        self.assertEqual((len(rows), rows[0]["invested"]), (1, 50.0))

    def test_selling_everything_removes_the_person(self):
        self.buy(self.a, 0, 60)
        shares = markets.detail(self.m, self.a)["holders"][0]["shares"]
        markets.trade(self.a, self.m, {"action": "sell", "outcome": 0, "side": "yes", "shares": shares})
        self.assertEqual(markets.detail(self.m, self.b)["holders"], [])

    def test_after_the_result_each_row_shows_what_it_paid(self):
        self.buy(self.a, 0, 100)
        self.buy(self.b, 1, 100)
        markets.resolve(self.a, self.m, 0)
        rows = {r["user"]["username"]: r for r in markets.detail(self.m, self.c)["holders"]}
        self.assertTrue(rows["alice"]["settled"] and rows["bobby"]["settled"])
        self.assertGreater(rows["alice"]["value"], 100.0)
        self.assertEqual(rows["bobby"]["value"], 0.0)


class PortfolioBreakdown(unittest.TestCase):
    def setUp(self):
        fresh()
        self.a = mk("alice", 1000)
        self.crew = circles.create(self.a, {"name": "Crew"})

    def test_cash_and_positions_add_up_to_net_worth(self):
        m1 = circle_bet(self.a, self.crew, "Circle bet about sports?", category="Sports")
        m2 = site_bet(self.a, "Public bet about money?", category="Money")
        m3 = site_bet(self.a, "Another public sports bet?", category="Sports")
        markets.trade(self.a, m1, {"action": "buy", "outcome": 0, "side": "yes", "amount": 300})
        markets.trade(self.a, m2, {"action": "buy", "outcome": 1, "side": "yes", "amount": 100})
        markets.trade(self.a, m3, {"action": "buy", "outcome": 0, "side": "yes", "amount": 50})
        p = markets.portfolio(self.a)
        d = p["distribution"]
        self.assertEqual(d["cash"], 550.0)
        self.assertAlmostEqual(d["cash"] + d["invested"], d["total"], places=2)
        self.assertAlmostEqual(d["total"], p["netWorth"], delta=0.02)
        self.assertEqual([g["key"] for g in d["byMarket"]], [m1["id"], m2["id"], m3["id"]])   # biggest first
        cats = {g["key"]: g for g in d["byCategory"]}
        self.assertEqual(set(cats), {"Sports", "Money"})
        self.assertEqual(cats["Sports"]["invested"], 350.0)
        for view in ("byMarket", "byCategory", "byCircle"):
            self.assertAlmostEqual(sum(g["value"] for g in d[view]), d["invested"], delta=0.03, msg=view)
        circles_by = {g["label"]: g for g in d["byCircle"]}
        self.assertEqual(set(circles_by), {"Crew", "Public"})
        self.assertEqual(circles_by["Public"]["invested"], 150.0)

    def test_empty_portfolio_is_all_cash(self):
        d = markets.portfolio(self.a)["distribution"]
        self.assertEqual((d["cash"], d["invested"], d["total"]), (1000.0, 0.0, 1000.0))
        self.assertEqual((d["byMarket"], d["byCategory"], d["byCircle"]), ([], [], []))

    def test_settled_positions_are_not_counted_as_invested(self):
        m = site_bet(self.a, "Settled public bet?")
        markets.trade(self.a, m, {"action": "buy", "outcome": 0, "side": "yes", "amount": 100})
        markets.resolve(self.a, m, 0)
        d = markets.portfolio(self.a)["distribution"]
        self.assertEqual(d["invested"], 0.0)
        self.assertGreater(d["cash"], 1000.0)


if __name__ == "__main__":
    unittest.main()
