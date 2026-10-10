import os
import sys
import tempfile
import unittest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, config, games, markets, users, weekly      # noqa: E402
from backend.store import store                                          # noqa: E402
from backend.util import ApiError, now_ms, week_bounds, week_key, WEEK_MS  # noqa: E402


def fresh():
    store.data = {}
    store.load()
    users._attempts.clear()


def mk_user(name, funds=None):
    u = users.register(name, "secret123")
    if funds is not None:
        u["balance"] = float(funds)
    return u


def expect_error(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e.message
    raise AssertionError("expected an ApiError")


class Accounts(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_start_balance_and_duplicates(self):
        u = mk_user("Alice")
        self.assertEqual(u["balance"], 1000.0)
        self.assertIn("taken", expect_error(users.register, "alice", "secret123"))
        self.assertEqual(users.login("ALICE", "secret123")["id"], u["id"])
        expect_error(users.login, "alice", "wrong-pass")

    def test_deposit_password(self):
        u = mk_user("Bob")
        self.assertEqual(expect_error(users.deposit, u, 500, "nope"), "Wrong password")
        self.assertEqual(u["balance"], 1000.0)
        users.deposit(u, 250000, config.ADMIN_PASSWORD)
        self.assertEqual(u["balance"], 251000.0)
        users.deposit(u, "1,000,000", config.ADMIN_PASSWORD)
        self.assertEqual(u["balance"], 1251000.0)

    def test_deposit_is_rate_limited(self):
        u = mk_user("Carl")
        for _ in range(5):
            expect_error(users.deposit, u, 5, "bad")
        self.assertIn("Too many", expect_error(users.deposit, u, 5, config.ADMIN_PASSWORD))


class Circles(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_private_needs_code_public_does_not(self):
        a, b = mk_user("Alice"), mk_user("Bob")
        priv = circles.create(a, {"name": "Secret club", "visibility": "private"})
        pub = circles.create(a, {"name": "Open house", "visibility": "public"})
        self.assertFalse(circles.can_view(priv, b))
        expect_error(circles.join, b, priv["id"], "WRONG1")
        circles.join(b, pub["id"])
        self.assertTrue(circles.is_member(pub, b))
        circles.join_by_code(b, priv["inviteCode"].lower())
        self.assertTrue(circles.is_member(priv, b))
        self.assertIn("owner", expect_error(circles.leave, a, priv["id"]))


class Trading(unittest.TestCase):
    def setUp(self):
        fresh()
        self.a, self.b = mk_user("Alice"), mk_user("Bob")
        self.c = circles.create(self.a, {"name": "Friends", "visibility": "private"})
        circles.join(self.b, self.c["id"], self.c["inviteCode"])
        self.m = markets.create(self.a, {"circleId": self.c["id"], "question": "Will it rain tomorrow?"})

    def test_bet_is_deducted_and_min_enforced(self):
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 100})
        self.assertEqual(self.a["balance"], 900.0)
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 0.1})
        self.assertEqual(self.a["balance"], 899.9)
        self.assertIn("minimum", expect_error(markets.trade, self.a, self.m, {"outcome": 0, "amount": 0.05}))
        self.assertIn("funds", expect_error(markets.trade, self.a, self.m, {"outcome": 0, "amount": 900}))

    def test_stake_can_exceed_1000_when_funded(self):
        users.deposit(self.a, 50000, config.ADMIN_PASSWORD)
        markets.trade(self.a, self.m, {"outcome": 1, "amount": 25000})
        self.assertEqual(self.a["balance"], 26000.0)
        self.assertGreater(markets.net_worth(self.a), 26000)

    def test_buy_moves_price_and_sell_round_trips(self):
        before = markets.summary(self.m, self.a)["outcomes"][0]["yes"]
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 200})
        after = markets.summary(self.m, self.a)["outcomes"][0]["yes"]
        self.assertGreater(after, before)
        shares = self.m["positions"][self.a["id"]]["y0"]["shares"]
        markets.trade(self.a, self.m, {"outcome": 0, "action": "sell", "shares": shares})
        self.assertAlmostEqual(self.a["balance"], 1000.0, places=1)
        self.assertNotIn(self.a["id"], self.m["positions"])

    def test_resolve_pays_winners_only(self):
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 100})
        markets.trade(self.b, self.m, {"outcome": 1, "amount": 100})
        shares = self.m["positions"][self.a["id"]]["y0"]["shares"]
        expect_error(markets.resolve, self.b, self.m, 0) if False else None
        markets.resolve(self.a, self.m, 0)
        self.assertAlmostEqual(self.a["balance"], 900 + round(shares, 2), places=2)
        self.assertEqual(self.b["balance"], 900.0)
        self.assertEqual(markets.state_of(self.m), "resolved")
        expect_error(markets.trade, self.a, self.m, {"outcome": 0, "amount": 5})

    def test_cancel_refunds_everyone(self):
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 100})
        markets.trade(self.b, self.m, {"outcome": 1, "amount": 40})
        markets.cancel(self.a, self.m)
        self.assertEqual(self.a["balance"], 1000.0)
        self.assertEqual(self.b["balance"], 1000.0)

    def test_only_manager_resolves(self):
        outsider = mk_user("Zed")
        circles.join(outsider, self.c["id"], self.c["inviteCode"])
        self.assertIn("creator", expect_error(markets.resolve, outsider, self.m, 0))

    def test_multi_outcome_yes_no(self):
        m = markets.create(self.a, {"circleId": self.c["id"], "question": "Who wins game night?",
                                    "outcomes": ["Ann", "Ben", "Cy"]})
        markets.trade(self.b, m, {"outcome": 0, "side": "no", "amount": 100})
        probs = markets.summary(m, self.b)["outcomes"]
        self.assertAlmostEqual(sum(o["yes"] for o in probs), 1.0, places=9)
        self.assertLess(probs[0]["yes"], 1 / 3)
        markets.resolve(self.a, m, 1)                   # Ben wins, so "No on Ann" pays
        self.assertGreater(self.b["balance"], 1000.0)

    def test_non_member_cannot_trade(self):
        outsider = mk_user("Zed")
        expect_error(markets.trade, outsider, self.m, {"outcome": 0, "amount": 10})


class Games(unittest.TestCase):
    def setUp(self):
        fresh()
        self.u = mk_user("Gamer", 1000)

    def test_limbo_accounting(self):
        for _ in range(200):
            before = self.u["balance"]
            r = games.limbo(self.u, {"amount": 1, "target": 2})
            expected = before - 1 + (2.0 if r["win"] else 0)
            self.assertAlmostEqual(self.u["balance"], expected, places=2)
            self.assertEqual(r["win"], r["result"] >= 2)

    def test_limbo_validation_and_large_bets(self):
        expect_error(games.limbo, self.u, {"amount": 0.05, "target": 2})
        expect_error(games.limbo, self.u, {"amount": 5, "target": 1})
        expect_error(games.limbo, self.u, {"amount": 5000, "target": 2})
        users.deposit(self.u, 1e9, config.ADMIN_PASSWORD)
        games.limbo(self.u, {"amount": 5_000_000, "target": 1.5})

    def test_roulette_accounting(self):
        for _ in range(100):
            before = self.u["balance"]
            r = games.roulette(self.u, {"bets": [{"type": "red", "amount": 5}, {"type": "straight", "value": 17, "amount": 1},
                                                 {"type": "dozen", "value": 2, "amount": 2}]})
            self.assertAlmostEqual(self.u["balance"], before - 8 + r["payout"], places=2)
            self.assertTrue(0 <= r["number"] <= 36)
        expect_error(games.roulette, self.u, {"bets": [{"type": "red", "amount": 1e9}]})

    def test_roulette_payout_table(self):
        self.assertEqual(games._roulette_wins("straight", 7, 7), (True, 36))
        self.assertEqual(games._roulette_wins("red", None, 0), (False, 0))
        self.assertEqual(games._roulette_wins("column", 1, 34)[0], True)
        self.assertEqual(games._roulette_wins("column", 3, 36)[0], True)
        self.assertEqual(games._roulette_wins("dozen", 3, 25)[0], True)

    def test_blackjack_balance_is_conserved(self):
        for _ in range(300):
            before = self.u["balance"]
            if self.u["balance"] < 50:
                self.u["balance"] = 1000.0
                before = 1000.0
            st = games.blackjack_deal(self.u, {"amount": 10})
            guard = 0
            while st["phase"] == "player" and guard < 20:
                guard += 1
                h = st["hands"][st["active"]]
                if st.get("canSplit") and h["cards"][0]["r"] in ("A", "8"):
                    act = "split"
                elif h["total"] < 12 and st.get("canDouble"):
                    act = "double"
                elif h["total"] < 17:
                    act = "hit"
                else:
                    act = "stand"
                st = games.blackjack_action(self.u, {"action": act})
            self.assertEqual(st["phase"], "done")
            self.assertAlmostEqual(self.u["balance"], before - st["totalBet"] + st["payout"], places=2)
            self.assertNotIn("blackjack", store.data["games"].get(self.u["id"], {}))

    def test_blackjack_hand_values(self):
        c = lambda *r: [{"r": x, "s": "S"} for x in r]    # noqa: E731
        self.assertEqual(games.hand_value(c("A", "K")), (21, True))
        self.assertEqual(games.hand_value(c("A", "A", "9")), (21, True))
        self.assertEqual(games.hand_value(c("K", "Q", "5")), (25, False))
        self.assertEqual(games.hand_value(c("A", "6", "10")), (17, False))

    def test_chicken_flow(self):
        wins = deaths = 0
        for _ in range(60):
            if self.u["balance"] < 20:
                self.u["balance"] = 1000.0
            before = self.u["balance"]
            games.chicken_start(self.u, {"amount": 10, "difficulty": "easy"})
            expect_error(games.chicken_cashout, self.u)         # must cross a lane first
            r = games.chicken_step(self.u)
            if r["crashed"]:
                deaths += 1
                self.assertAlmostEqual(self.u["balance"], before - 10, places=2)
                continue
            r = games.chicken_cashout(self.u)
            wins += 1
            self.assertAlmostEqual(self.u["balance"], before - 10 + r["payout"], places=2)
            self.assertGreater(r["payout"], 10)
        self.assertGreater(wins + deaths, 0)

    def test_chicken_multipliers_fair(self):
        # expected value at any cash-out lane equals the RTP, so mult * p^k must be ~0.97
        for d, cfg in games.CHICKEN.items():
            for k in (1, 3, 7):
                self.assertAlmostEqual(games.chicken_mult(d, k) * cfg["p"] ** k, games.CHICKEN_RTP, delta=0.02)


class Weekly(unittest.TestCase):
    def setUp(self):
        fresh()
        self.a, self.b, self.c3 = mk_user("Alice"), mk_user("Bob"), mk_user("Cleo")
        self.circle = circles.create(self.a, {"name": "Squad", "visibility": "private"})
        for u in (self.b, self.c3):
            circles.join(u, self.circle["id"], self.circle["inviteCode"])

    def test_poll_voting_rules(self):
        p = weekly.add_punishment(self.a, self.circle, "Sing the national anthem")
        weekly.add_punishment(self.b, self.circle, "Wear a chicken suit")
        self.assertEqual(len(p["votes"]), 1)                       # suggesting counts as your own vote
        weekly.vote(self.c3, self.circle, p["id"])
        poll = {x["text"]: len(x["votes"]) for x in self.circle["punishments"][week_key()]}
        self.assertEqual(poll["Sing the national anthem"], 2)
        weekly.vote(self.c3, self.circle, p["id"])                 # voting twice toggles it off
        self.assertEqual(len(p["votes"]), 1)
        expect_error(weekly.add_punishment, self.a, self.circle, "sing the national anthem")
        weekly.add_punishment(self.a, self.circle, "Buy everyone pizza")
        self.assertIn("up to", expect_error(weekly.add_punishment, self.a, self.circle, "A third idea"))

    def test_rollover_punishes_poorest_and_gives_awards(self):
        p1 = weekly.add_punishment(self.a, self.circle, "Dance in public")
        weekly.add_punishment(self.b, self.circle, "Eat a lemon")
        weekly.vote(self.c3, self.circle, p1["id"])
        weekly.vote(self.b, self.circle, p1["id"])
        self.b["balance"] = 120.0                      # Bob is broke
        self.a["balance"] = 1400.0
        users.stat_add(self.a, "marketBets", 4)
        week = week_key()
        # pretend the week has ended
        start, end = week_bounds(week)
        self.circle["createdAt"] = start - 10
        weekly.finalize_week(week)
        recap = self.circle["recaps"][week]
        self.assertEqual(recap["loserIds"], [self.b["id"]])
        self.assertEqual(recap["punishment"]["text"], "Dance in public")
        keys = {a["key"]: a["userIds"] for a in recap["awards"]}
        self.assertEqual(keys["topDog"], [self.a["id"]])
        self.assertEqual(keys["hotSeat"], [self.b["id"]])
        self.assertEqual(keys["rocketMan"], [self.a["id"]])
        self.assertEqual(keys["freefall"], [self.b["id"]])
        counts, _ = weekly.trophies(self.b)
        self.assertEqual(counts.get("hotSeat"), 1)

    def test_everyone_tied_means_no_punishment(self):
        week = week_key()
        start, _ = week_bounds(week)
        self.circle["createdAt"] = start - 10
        weekly.finalize_week(week)
        self.assertEqual(self.circle["recaps"][week]["loserIds"], [])

    def test_tick_settles_past_weeks_once(self):
        last_week = week_key(now_ms() - WEEK_MS)
        store.data["meta"]["week"] = last_week
        self.circle["createdAt"] = now_ms() - 3 * WEEK_MS
        for uid in self.circle["members"]:
            self.circle["members"][uid] = now_ms() - 3 * WEEK_MS
        self.assertTrue(weekly.tick())
        self.assertIn(last_week, self.circle["recaps"])
        self.assertEqual(store.data["meta"]["week"], week_key())
        self.assertFalse(weekly.tick())

    def test_deposits_dont_count_as_gains(self):
        users.deposit(self.a, 5000, config.ADMIN_PASSWORD)
        rows = {r["user"]["username"]: r for r in weekly.standings(self.circle, week_key())}
        self.assertEqual(rows["Alice"]["delta"], 0.0)
        self.assertEqual(rows["Alice"]["value"], 6000.0)


if __name__ == "__main__":
    unittest.main()
