"""Passing Go every week, the rescue voucher, and demo bets."""
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from backend import circles, config, economy, games, seed, users, weekly   # noqa: E402
from backend.store import db, store                        # noqa: E402
from backend.util import ApiError, DAY_MS, WEEK_MS, now_ms, prev_week_key, week_bounds, week_key   # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402
from tests.test_http import Client                         # noqa: E402


def tearDownModule():
    restore_store_path()


def mk(name, funds=None, age_days=0):
    u = users.register(name, "secret123")
    u["createdAt"] = now_ms() - int(age_days * DAY_MS)
    u["wk"]["week"] = week_key(u["createdAt"])              # an older account last had its week set up back then
    if funds is not None:
        u["balance"] = float(funds)
    return u


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def put_first(*wanted):
    def f(items):
        rest = [i for i in items if i not in wanted]
        items[:] = list(wanted) + rest
        return items
    return f


class PassGo(unittest.TestCase):
    """The weekly refill (what used to be "pass Go"): the weekly account is set up again when a new week starts."""
    def setUp(self):
        fresh_store()
        self.cur = week_key()
        self.prev = prev_week_key(self.cur)

    def roll_over(self, weeks_back=1):
        key = self.cur
        for _ in range(weeks_back):
            key = prev_week_key(key)
        db()["meta"]["week"] = key
        return weekly.tick()

    def test_everyone_who_was_around_starts_the_week_with_the_allocation(self):
        a, b, new = mk("alice", 500, 30), mk("bobby", 2000, 30), mk("newbie", 1000, 0)
        self.assertTrue(self.roll_over())
        self.assertEqual((a["balance"], b["balance"]), (1000.0, 1000.0), "reset: topped up, or trimmed back, to the allocation")
        self.assertEqual(new["balance"], 1000.0, "joined this week: the sign-up cash was their allocation")
        for u in (a, b):
            self.assertEqual(u["activity"][0]["kind"], "go")
            self.assertEqual(u["activity"][0]["amount"], 1000.0)
            self.assertEqual(u["passGo"], {"week": self.cur, "amount": 1000.0})

    def test_topup_mode_adds_the_allocation_on_top(self):
        a, b = mk("alice", 500, 30), mk("bobby", 2000, 30)
        with mock.patch.object(economy, "WEEKLY_RESET", False):
            self.roll_over()
        self.assertEqual((a["balance"], b["balance"]), (1500.0, 3000.0))

    def test_it_is_not_winnings(self):
        a, b = mk("alice", 500, 30), mk("bobby", 900, 30)
        crew = circles.create(a, {"name": "Crew"})
        circles.join_by_code(b, crew["inviteCode"])
        self.roll_over()
        rows = {r["user"]["username"]: r for r in weekly.standings(crew, self.cur)}
        self.assertEqual((rows["alice"]["delta"], rows["bobby"]["delta"]), (0.0, 0.0))     # nobody 'gained' anything
        self.assertEqual((rows["alice"]["value"], rows["bobby"]["value"]), (1000.0, 1000.0))

    def test_the_old_week_is_settled_before_the_refill_lands(self):
        a = mk("alice", 500, 30)
        self.roll_over()
        self.assertEqual(db()["snapshots"][self.prev][a["id"]], 500.0)         # the refill is not in last week's numbers

    def test_only_once_per_week(self):
        a = mk("alice", 500, 30)
        self.roll_over()
        self.assertFalse(weekly.tick())
        self.assertEqual(a["balance"], 1000.0)

    def test_weeks_missed_while_the_server_was_off_still_leave_a_fresh_week(self):
        old, mid = mk("old", 0, 60), mk("mid", 0, 10)
        self.roll_over(weeks_back=3)
        self.assertEqual(old["balance"], 1000.0)
        self.assertEqual(mid["balance"], 1000.0)
        self.assertEqual(old["wk"]["week"], self.cur)

    def test_a_brand_new_server_pays_nothing(self):
        a = mk("alice", 500, 30)
        db()["meta"].pop("week", None)
        weekly.tick()
        self.assertEqual(a["balance"], 500.0)

    def test_can_be_switched_off(self):
        a = mk("alice", 500, 30)
        with mock.patch.object(economy, "WEEKLY_ALLOCATION", 0.0):
            self.roll_over()
        self.assertEqual(a["balance"], 500.0)


class Voucher(unittest.TestCase):
    def setUp(self):
        fresh_store()

    def test_only_under_fifty_cents(self):
        for funds, ok in ((0.0, True), (0.49, True), (0.5, False), (0.51, False), (1000.0, False)):
            u = mk(f"user{int(funds * 100)}", funds)
            self.assertEqual(users.voucher_info(u)["eligible"], ok, funds)

    def test_redeeming_pays_250_once_a_week(self):
        u = mk("alice", 0.2)
        self.assertEqual(users.redeem_voucher(u), 250.0)
        self.assertEqual(u["balance"], 250.2)
        self.assertEqual(u["activity"][0]["kind"], "voucher")
        self.assertEqual(u["stats"][week_key()]["deposits"], 250.0)
        u["balance"] = 0.0                                              # blow it all again
        info = users.voucher_info(u)
        self.assertEqual((info["used"], info["eligible"]), (True, False))
        self.assertIn("already used", err(users.redeem_voucher, u).message)
        self.assertEqual(u["balance"], 0.0)

    def test_a_new_week_brings_a_new_voucher(self):
        u = mk("alice", 0.0)
        users.redeem_voucher(u)
        u["balance"] = 0.0
        u["voucher"]["week"] = prev_week_key(week_key())                # as if it was redeemed last week
        self.assertTrue(users.voucher_info(u)["eligible"])
        self.assertEqual(users.redeem_voucher(u), 250.0)

    def test_not_when_you_still_have_chips(self):
        u = mk("alice", 0.5)
        self.assertIn("still have chips", err(users.redeem_voucher, u).message)
        self.assertEqual(u["balance"], 0.5)
        self.assertNotIn("voucher", u)

    def test_not_while_a_round_is_on_the_table(self):
        u = mk("alice", 0.55)
        with mock.patch.object(games, "shuffle", put_first(0, 1, 2)):
            games.mines_start(u, {"amount": 0.1, "size": 25, "mines": 3})
        info = users.voucher_info(u)
        self.assertEqual((u["balance"], info["busy"], info["eligible"]), (0.45, True, False))
        self.assertIn("Finish the round", err(users.redeem_voucher, u).message)
        games.mines_pick(u, {"tile": 0})                                # a mine: the round is over
        self.assertTrue(users.voucher_info(u)["eligible"])
        self.assertEqual(users.redeem_voucher(u), 250.0)

    def test_the_voucher_helps_but_never_counts_as_winnings(self):
        a, b = mk("alice", 0.0, 3), mk("bobby", 400.0, 3)
        crew = circles.create(a, {"name": "Crew"})
        circles.join_by_code(b, crew["inviteCode"])
        users.redeem_voucher(a)
        rows = {r["user"]["username"]: r for r in weekly.standings(crew, week_key())}
        self.assertEqual(rows["alice"]["delta"], rows["alice"]["value"] - rows["alice"]["start"] - 250.0)
        self.assertEqual(rows["alice"]["value"], 250.0)


class Demo(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("player", 1000.0)

    def roll(self, acct, r, **body):
        with mock.patch.object(games, "rand_below", lambda n: r):
            return games.dice(acct, {"amount": 10, "direction": "over", "target": 50, **body})

    def test_practice_wallet_starts_with_a_thousand_and_is_separate(self):
        d = games.demo_account(self.u)
        self.assertEqual(d["balance"], 1000.0)
        self.assertNotEqual(d["id"], self.u["id"])
        self.assertTrue(d["isDemo"])
        self.assertIs(games.account_for(self.u, False), self.u)
        self.assertIs(games.account_for(self.u, True), d)
        for sneaky in ("true", 1, "1", None):
            self.assertIs(games.account_for(self.u, sneaky), self.u, sneaky)

    def test_demo_rounds_never_touch_the_real_wallet_stats_history_or_feed(self):
        d = games.demo_account(self.u)
        self.roll(d, 9500, target=90)                       # a 9.9x demo win: big enough for the board, if it counted
        self.roll(d, 9500, target=90)
        self.roll(d, 100)                                   # and a loss
        self.assertNotEqual(d["balance"], 1000.0)
        self.assertEqual(self.u["balance"], 1000.0)
        self.assertEqual((self.u["history"], self.u["stats"], self.u["activity"][-1]["kind"]), ([], {}, "start"))
        self.assertEqual(db()["feed"], [], "practice wins must not reach the big-wins board")
        self.assertEqual(len(d["history"]), 3)
        self.roll(self.u, 9500, target=90)                  # the same win on the real wallet does reach the board
        self.assertEqual(len(db()["feed"]), 1)

    def test_a_real_round_and_a_demo_round_can_run_side_by_side(self):
        d = games.demo_account(self.u)
        with mock.patch.object(games, "shuffle", put_first(0, 1, 2)):
            real = games.mines_start(self.u, {"amount": 10, "size": 25, "mines": 3})
            demo = games.mines_start(d, {"amount": 10, "size": 25, "mines": 3})
        self.assertNotEqual(real["id"], demo["id"])
        games.mines_pick(d, {"tile": 0})                    # the demo round dies...
        self.assertIsNone(games.active_state(d)["mines"])
        self.assertEqual(games.active_state(self.u)["mines"]["id"], real["id"])      # ...the real one carries on
        self.assertEqual(self.u["balance"], 990.0)
        self.assertEqual(d["balance"], 990.0)

    def test_the_two_balances_are_checked_independently(self):
        d = games.demo_account(self.u)
        d["balance"] = 5.0
        self.assertIn("Not enough", err(games.dice, d, {"amount": 50, "direction": "over", "target": 50}).message)
        self.u["balance"] = 5.0
        d["balance"] = 5000.0
        self.assertEqual(self.roll(d, 9000, amount=2000)["win"], True)
        self.assertIn("Not enough", err(games.dice, self.u, {"amount": 2000, "direction": "over", "target": 50}).message)

    def test_reset_gives_a_fresh_thousand_and_clears_a_round_in_progress(self):
        d = games.demo_account(self.u)
        with mock.patch.object(games, "shuffle", put_first(5)):
            games.tower_start(d, {"amount": 100, "risk": "easy"})
        d["balance"] = 3.0
        fresh = games.demo_reset(self.u)
        self.assertEqual((fresh["balance"], fresh["history"], fresh["stats"]), (1000.0, [], {}))
        self.assertIsNone(games.active_state(fresh)["tower"])

    def test_every_game_plays_on_the_practice_wallet(self):
        d = games.demo_account(self.u)
        games.coinflip(d, {"amount": 1, "side": "heads"})
        games.war(d, {"amount": 1})
        games.limbo(d, {"amount": 1, "target": 2})
        games.roulette(d, {"bets": [{"type": "red", "amount": 1}]})
        games.blackjack_deal(d, {"amount": 1})
        games.chicken_start(d, {"amount": 1, "difficulty": "easy"})
        games.mines_start(d, {"amount": 1, "size": 25, "mines": 1})
        games.moles_start(d, {"amount": 1, "moles": 3})
        games.tower_start(d, {"amount": 1, "risk": "easy"})
        self.assertEqual(self.u["balance"], 1000.0)
        self.assertEqual(self.u["history"], [])
        self.assertEqual(db()["games"].get(self.u["id"], {}), {})

    def test_a_new_season_clears_perks(self):
        users.redeem_voucher(mk("broke", 0.0))
        player = self.u
        games.demo_account(player)["balance"] = 7.0
        player["voucher"], player["passGo"] = {"week": week_key(), "t": 1}, {"week": week_key(), "amount": 1000}
        seed.new_season(store.data)
        for u in store.data["users"].values():
            for perk in ("voucher", "passGo", "demo"):
                self.assertNotIn(perk, u)


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.c = Client(cls.port)
        assert cls.c.call("POST", "/api/auth/register", {"username": "gamer", "password": "secret123"})[0] == 200

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        restore_store_path()

    def me(self):
        return self.c.call("GET", "/api/me")[1]["user"]

    def test_me_tells_the_browser_about_the_voucher(self):
        v = self.me()["voucher"]
        self.assertEqual((v["amount"], v["below"], v["eligible"], v["used"]), (250.0, 0.5, False, False))
        self.assertEqual(v["goAmount"], 1000.0)
        self.assertGreater(v["resetsAt"], now_ms())

    def test_redeem_over_http(self):
        self.assertEqual(self.c.call("POST", "/api/wallet/voucher", {})[0], 400)        # $1,000: not allowed
        gamer = next(u for u in store.data["users"].values() if u["username"] == "gamer")
        gamer["balance"] = 0.1
        st, d = self.c.call("POST", "/api/wallet/voucher", {})
        self.assertEqual((st, d["added"], d["user"]["balance"]), (200, 250.0, 250.1))
        self.assertTrue(d["user"]["voucher"]["used"])
        self.assertEqual(self.c.call("POST", "/api/wallet/voucher", {})[0], 400)        # once a week
        gamer["balance"] = 1000.0
        gamer.pop("voucher", None)

    def test_demo_bets_over_http(self):
        before = self.me()["balance"]
        st, d = self.c.call("GET", "/api/games/demo")
        self.assertEqual((st, d["user"]["balance"], d["user"]["demo"]), (200, 1000.0, True))
        st, d = self.c.call("POST", "/api/games/dice", {"amount": 10, "direction": "under", "target": 60, "demo": True})
        self.assertEqual(st, 200)
        self.assertTrue(d["user"]["demo"])
        self.assertNotEqual(d["user"]["balance"], 1000.0)
        self.assertEqual(self.me()["balance"], before)
        self.assertEqual(len(self.c.call("GET", "/api/games/history?demo=1")[1]["history"]), 1)
        real_rows = [h for h in self.c.call("GET", "/api/games/history")[1]["history"] if h["game"] == "dice"]
        self.assertEqual(real_rows, [])
        st, d = self.c.call("POST", "/api/games/demo/reset", {})
        self.assertEqual((st, d["user"]["balance"]), (200, 1000.0))
        self.assertEqual(self.c.call("GET", "/api/games/history?demo=1")[1]["history"], [])

    def test_a_demo_round_can_be_resumed_but_stays_out_of_the_real_state(self):
        self.c.call("POST", "/api/games/mines/start", {"amount": 5, "size": 25, "mines": 3, "demo": True})
        st, demo_state = self.c.call("GET", "/api/games/state?demo=1")
        self.assertIsNotNone(demo_state["mines"])
        self.assertEqual(demo_state["balance"], 995.0)
        self.assertIsNone(self.c.call("GET", "/api/games/state")[1]["mines"])
        self.c.call("POST", "/api/games/demo/reset", {})

    def test_only_a_real_true_means_demo(self):
        before = self.me()["balance"]
        st, d = self.c.call("POST", "/api/games/coinflip", {"amount": 1, "side": "heads", "demo": "true"})
        self.assertEqual(st, 200)
        self.assertNotIn("demo", d["user"])                 # a string is not a switch: this was a real flip
        self.assertIn(self.me()["balance"], (before - 1.0, before + 0.98))


if __name__ == "__main__":
    unittest.main()
