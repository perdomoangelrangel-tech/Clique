"""The automated market maker: how prices move, what trades cost and pay, and why nobody can print money with it."""
import json
import math
import os
import random
import sys
import tempfile
import threading
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from backend import circles, config, lmsr, markets, users  # noqa: E402
from backend.store import db, store                        # noqa: E402
from backend.util import ApiError, now_ms                  # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402
from tests.test_http import Client                         # noqa: E402


def tearDownModule():
    restore_store_path()


def rich(name, funds=1_000_000.0):
    u = users.register(name, "secret123")
    u["balance"] = float(funds)
    return u


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def buy(u, m, outcome, amount, side="yes", **extra):
    return markets.trade(u, m, {"outcome": outcome, "side": side, "amount": amount, **extra})


def sell(u, m, outcome, shares=None, side="yes", **extra):
    body = {"outcome": outcome, "side": side, "action": "sell", **extra}
    body.update({"all": True} if shares is None else {"shares": shares})
    return markets.trade(u, m, body)


def probs(m):
    return lmsr.prices(m["q"], m["b"])


def implied_q(m):
    """The market's share counts, worked out from nothing but what people hold."""
    q = [0.0] * len(m["outcomes"])
    for toks in m["positions"].values():
        for token, pos in toks.items():
            q[int(token[1:])] += pos["shares"] if token[0] == "y" else -pos["shares"]
    return q


class Base(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.ann, self.bob, self.cat = rich("ann_x"), rich("bob_x"), rich("cat_x")
        self.circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        for u in (self.bob, self.cat):
            circles.join(u, self.circle["id"], self.circle["inviteCode"])
        self.m = self.market("Will it rain tomorrow?")

    def market(self, question, outcomes=None, b=None):
        body = {"circleId": self.circle["id"], "question": question}
        if outcomes:
            body["outcomes"] = outcomes
        m = markets.create(self.ann, body)
        if b:
            m["b"] = float(b)                                           # a market made before there was one standard depth
        return m


class Direction(Base):
    def test_buying_yes_raises_yes_and_selling_it_lowers_it_again(self):
        p0 = probs(self.m)[0]
        buy(self.bob, self.m, 0, 100)
        p1 = probs(self.m)[0]
        self.assertGreater(p1, p0)
        sell(self.bob, self.m, 0, shares=self.m["positions"][self.bob["id"]]["y0"]["shares"] / 2)
        p2 = probs(self.m)[0]
        self.assertTrue(p0 < p2 < p1)
        sell(self.bob, self.m, 0)
        self.assertAlmostEqual(probs(self.m)[0], p0, places=9)

    def test_buying_no_does_the_opposite_and_selling_no_undoes_it(self):
        p0 = probs(self.m)[0]
        buy(self.bob, self.m, 0, 100, side="no")                         # NO on a two-sided market is YES on the other side
        self.assertLess(probs(self.m)[0], p0)
        self.assertGreater(probs(self.m)[1], 1 - p0)
        sell(self.bob, self.m, 0, side="no")
        self.assertAlmostEqual(probs(self.m)[0], p0, places=9)

    def test_named_outcomes_every_other_outcome_gives_way_in_proportion(self):
        m = self.market("Who wins game night?", ["Ann", "Ben", "Cy", "Dee"])
        before = probs(m)
        buy(self.bob, m, 1, 120)                                         # Ben is backed
        after = probs(m)
        self.assertGreater(after[1], before[1])
        for i in (0, 2, 3):
            self.assertLess(after[i], before[i])
        self.assertAlmostEqual(after[0] / after[2], before[0] / before[2], places=9)        # the rest keep their pecking order
        sell(self.bob, m, 1)                                              # and selling that back restores every odds
        for a, b in zip(probs(m), before):
            self.assertAlmostEqual(a, b, places=9)

    def test_no_on_one_of_several_outcomes_lowers_it_and_lifts_the_rest(self):
        m = self.market("Who wins game night?", ["Ann", "Ben", "Cy"])
        before = probs(m)
        buy(self.bob, m, 0, 80, side="no")
        after = probs(m)
        self.assertLess(after[0], before[0])
        self.assertGreater(after[1], before[1])
        self.assertGreater(after[2], before[2])
        sell(self.bob, m, 0, side="no")
        for a, b in zip(probs(m), before):
            self.assertAlmostEqual(a, b, places=9)

    def test_probabilities_always_total_exactly_100_percent_for_any_number_of_outcomes(self):
        rng = random.Random(7)
        for n in range(2, 13):
            m = self.market(f"Pick one of {n}", [f"Option {k}" for k in range(n)])
            for _ in range(25):
                i, side = rng.randrange(n), rng.choice(["yes", "no"])
                try:
                    buy(self.bob, m, i, round(rng.uniform(0.1, 400), 2), side=side)
                except ApiError:
                    pass
                self.assertAlmostEqual(sum(probs(m)), 1.0, places=9)
                rows = markets.summary(m, self.bob)["outcomes"]
                self.assertEqual(sum(r["pct"] for r in rows), 100)
                self.assertTrue(all(isinstance(r["pct"], int) and 0 <= r["pct"] <= 100 for r in rows))

    def test_a_fresh_market_starts_even(self):
        for n in (2, 3, 12):
            m = self.market(f"Even odds for {n}", [f"O{k}" for k in range(n)])
            self.assertTrue(all(abs(p - 1 / n) < 1e-12 for p in probs(m)))
            self.assertEqual(sum(r["pct"] for r in markets.summary(m, self.bob)["outcomes"]), 100)


class SizeVersusLiquidity(Base):
    def test_a_bigger_trade_moves_the_price_further(self):
        moves = []
        for stake in (1, 10, 50, 250, 1000, 10000):
            m = self.market(f"Size {stake}?")
            buy(self.bob, m, 0, stake)
            moves.append(probs(m)[0] - 0.5)
        self.assertEqual(moves, sorted(moves))
        self.assertTrue(all(b > a for a, b in zip(moves, moves[1:])))

    def test_the_same_stake_moves_a_shallow_market_more_than_a_deep_one(self):
        after = {}
        for b in (100, 250, 1000, 5000):
            m = self.market(f"Depth {b}?", b=b)
            buy(self.bob, m, 0, 100)
            after[b] = probs(m)[0]
        self.assertTrue(after[100] > after[250] > after[1000] > after[5000] > 0.5)

    def test_what_matters_is_the_stake_compared_with_the_depth(self):
        landings = []
        for b in (100, 250, 1000, 5000):
            m = self.market(f"Scale {b}?", b=b)
            buy(self.bob, m, 0, 0.25 * b)                                # a quarter of the depth, whatever the depth
            landings.append(probs(m)[0])
        for p in landings:
            self.assertAlmostEqual(p, landings[0], places=9)

    def test_the_one_standard_depth_behaves_as_advertised(self):
        self.assertEqual(self.m["b"], config.MARKET_LIQUIDITY)
        m = self.market("An even $250 bet")
        buy(self.bob, m, 0, config.MARKET_LIQUIDITY)
        self.assertTrue(0.80 < probs(m)[0] < 0.83)                        # about 82%: stake equal to the depth
        small = self.market("An even $10 bet")
        buy(self.bob, small, 0, 10)
        self.assertTrue(0.51 < probs(small)[0] < 0.53)

    def test_later_shares_cost_more_the_average_price_sits_between_before_and_after(self):
        q = markets.quote(self.m, self.bob, {"outcome": 0, "amount": 400})
        self.assertTrue(q["priceBefore"] < q["avgPrice"] < q["priceAfter"])
        self.assertAlmostEqual(q["shares"] * q["avgPrice"], 400, places=9)


class Accounting(Base):
    def test_a_buy_costs_exactly_what_the_cost_function_says(self):
        c0 = lmsr.cost(self.m["q"], self.m["b"])
        before = self.bob["balance"]
        r = buy(self.bob, self.m, 0, 137.42)
        self.assertEqual(self.bob["balance"], round(before - 137.42, 2))
        self.assertAlmostEqual(lmsr.cost(self.m["q"], self.m["b"]) - c0, 137.42, places=7)
        pos = self.m["positions"][self.bob["id"]]["y0"]
        self.assertAlmostEqual(pos["shares"], r["shares"], places=9)
        self.assertAlmostEqual(pos["invested"], 137.42, places=9)

    def test_the_quote_is_the_trade_and_asking_changes_nothing(self):
        snapshot = json.dumps(self.m, sort_keys=True), self.bob["balance"]
        q = markets.quote(self.m, self.bob, {"outcome": 0, "side": "yes", "amount": 75.5})
        self.assertEqual((json.dumps(self.m, sort_keys=True), self.bob["balance"]), snapshot)
        r = buy(self.bob, self.m, 0, 75.5)
        for key in ("amount", "shares", "avgPrice", "priceBefore", "priceAfter"):
            self.assertAlmostEqual(q[key], r[key], places=12)
        self.assertAlmostEqual(q["probsAfter"][0], probs(self.m)[0], places=12)
        self.assertEqual(q["pctAfter"], r["pctAfter"])
        self.assertEqual(q["balanceAfter"], self.bob["balance"])
        sq = markets.quote(self.m, self.bob, {"outcome": 0, "action": "sell", "shares": r["shares"]})
        sr = sell(self.bob, self.m, 0)
        self.assertEqual((sq["amount"], sq["shares"]), (sr["amount"], sr["shares"]))

    def test_the_quote_has_everything_the_confirmation_needs(self):
        q = markets.quote(self.m, self.bob, {"outcome": 0, "amount": 50})
        self.assertEqual((q["action"], q["amount"], q["label"]), ("buy", 50.0, "Yes"))
        self.assertTrue(q["shares"] > 50 and 0 < q["avgPrice"] < 1)
        self.assertTrue(q["probsBefore"][0] == 0.5 and q["probsAfter"][0] > 0.5)
        self.assertEqual(sum(q["pctAfter"]), 100)
        self.assertAlmostEqual(q["payout"], q["shares"])
        buy(self.bob, self.m, 0, 50)
        s = markets.quote(self.m, self.bob, {"outcome": 0, "action": "sell", "shares": 10})
        self.assertEqual((s["action"], s["shares"]), ("sell", 10))
        self.assertTrue(s["amount"] > 0 and s["probsAfter"][0] < probs(self.m)[0])
        self.assertAlmostEqual(s["heldAfter"], self.m["positions"][self.bob["id"]]["y0"]["shares"] - 10)

    def test_selling_pays_the_cost_function_difference_rounded_down_to_the_cent(self):
        r = buy(self.bob, self.m, 0, 300)
        half = r["shares"] / 3
        exact = lmsr.cost(self.m["q"], self.m["b"])
        before = self.bob["balance"]
        out = sell(self.bob, self.m, 0, shares=half)
        exact -= lmsr.cost(self.m["q"], self.m["b"])
        self.assertAlmostEqual(self.bob["balance"] - before, out["amount"], places=9)
        self.assertTrue(exact - 0.01 < out["amount"] <= exact + 1e-9)
        self.assertAlmostEqual(out["amount"] * 100, round(out["amount"] * 100), places=9)           # a whole number of cents
        pos = self.m["positions"][self.bob["id"]]["y0"]
        self.assertAlmostEqual(pos["shares"], r["shares"] - half, places=9)
        self.assertAlmostEqual(pos["invested"], 200, places=9)                                       # a third of the cost leaves with a third of the shares

    def test_selling_everything_clears_the_position(self):
        buy(self.bob, self.m, 0, 20)
        sell(self.bob, self.m, 0)
        self.assertNotIn(self.bob["id"], self.m["positions"])

    def test_shares_and_state_always_agree(self):
        rng = random.Random(11)
        for n, outcomes in ((2, None), (4, ["a", "b", "c", "d"])):
            m = self.market(f"Agree {n}?", outcomes)
            for step in range(120):
                u, i = rng.choice([self.ann, self.bob, self.cat]), rng.randrange(n)
                side = rng.choice(["yes", "no"])
                held = m["positions"].get(u["id"], {}).get(markets.token_of(m, i, side)[2])
                try:
                    if held and rng.random() < 0.4:
                        sell(u, m, i, side=side, **({} if rng.random() < 0.3 else {"shares": held["shares"] * rng.random()}))
                    else:
                        buy(u, m, i, round(rng.uniform(0.1, 300), 2), side=side)
                except ApiError:
                    pass
            for a, b in zip(lmsr.prices(implied_q(m), m["b"]), probs(m)):
                self.assertAlmostEqual(a, b, places=7)

    def test_the_market_maker_never_pays_out_more_than_it_took_in(self):
        rng = random.Random(3)
        taken = {self.m["id"]: 0.0}
        c0 = lmsr.cost(self.m["q"], self.m["b"])
        for _ in range(300):
            u, i = rng.choice([self.ann, self.bob, self.cat]), rng.randrange(2)
            token = markets.token_of(self.m, i, "yes")[2]
            held = self.m["positions"].get(u["id"], {}).get(token)
            try:
                if held and rng.random() < 0.5:
                    taken[self.m["id"]] -= sell(u, self.m, i, shares=held["shares"] * rng.choice([1, 0.5, 0.01]))["amount"]
                else:
                    taken[self.m["id"]] += buy(u, self.m, i, round(rng.uniform(0.1, 200), 2))["amount"]
            except ApiError:
                continue
            self.assertGreaterEqual(taken[self.m["id"]], lmsr.cost(self.m["q"], self.m["b"]) - c0 - 1e-7)

    def test_a_trade_that_is_refused_changes_nothing_at_all(self):
        buy(self.bob, self.m, 0, 50)
        snap = lambda: (json.dumps(self.m, sort_keys=True), self.bob["balance"], json.dumps(self.bob["stats"], sort_keys=True), len(self.bob["activity"]))   # noqa: E731
        before = snap()
        for body in ({"outcome": 0, "amount": 10 ** 9}, {"outcome": 0, "amount": 0.01}, {"outcome": 1, "action": "sell", "shares": 1},
                     {"outcome": 0, "action": "sell", "shares": 10 ** 6}, {"outcome": 5, "amount": 5}, {"outcome": 0, "amount": "x"}):
            err(markets.trade, self.bob, self.m, body)
        self.assertEqual(snap(), before)


class Refusals(Base):
    def test_not_enough_funds(self):
        poor = rich("poor_x", 10)
        circles.join(poor, self.circle["id"], self.circle["inviteCode"])
        self.assertEqual(err(buy, poor, self.m, 0, 10.01).message, "Not enough funds")
        buy(poor, self.m, 0, 10)
        self.assertEqual(poor["balance"], 0.0)
        self.assertEqual(err(buy, poor, self.m, 0, 0.1).message, "Not enough funds")

    def test_you_cannot_sell_what_you_do_not_hold(self):
        self.assertIn("don't hold", err(sell, self.bob, self.m, 0, shares=1).message)
        r = buy(self.bob, self.m, 0, 30)
        self.assertIn("only hold", err(sell, self.bob, self.m, 0, shares=r["shares"] + 1).message)
        self.assertIn("don't hold", err(sell, self.bob, self.m, 1, shares=1).message)                       # the other side
        self.assertIn("don't hold", err(sell, self.bob, self.m, 0, shares=1, side="no").message)            # a different token
        self.assertIn("don't hold", err(sell, self.cat, self.m, 0).message)                                  # somebody else's shares
        sell(self.bob, self.m, 0, shares=r["shares"] * 0.4)
        self.assertIn("only hold", err(sell, self.bob, self.m, 0, shares=r["shares"] * 0.7).message)

    def test_nonsense_amounts(self):
        for amount in (0, -5, float("nan"), float("inf"), "abc", None, True, [1], {"a": 1}, "", 0.05):
            self.assertEqual(err(buy, self.bob, self.m, 0, amount).status, 400, repr(amount))
        buy(self.bob, self.m, 0, 10)
        for shares in (0, -1, float("nan"), float("inf"), "abc", None, True, [1], ""):
            self.assertEqual(err(markets.trade, self.bob, self.m, {"outcome": 0, "action": "sell", "shares": shares}).status, 400, repr(shares))
        self.assertEqual(err(markets.trade, self.bob, self.m, {"outcome": 0, "amount": 5, "action": "borrow"}).status, 400)
        self.assertEqual(err(buy, self.bob, self.m, 7, 5).status, 400)
        self.assertEqual(err(buy, self.bob, self.m, "x", 5).status, 400)

    def test_a_sliver_worth_less_than_a_cent_cannot_be_sold(self):
        buy(self.bob, self.m, 0, 10)
        self.assertIn("less than a cent", err(sell, self.bob, self.m, 0, shares=0.01).message)

    def test_only_members_can_trade_or_even_ask(self):
        outsider = rich("zed_x")
        self.assertEqual(err(buy, outsider, self.m, 0, 5).status, 403)
        self.assertEqual(err(markets.quote, self.m, outsider, {"outcome": 0, "amount": 5}).status, 403)


class NoFreeMoney(Base):
    def test_buying_then_selling_straight_away_never_leaves_you_ahead(self):
        rng = random.Random(21)
        for n, outcomes in ((2, None), (3, ["x", "y", "z"]), (12, [f"o{k}" for k in range(12)])):
            m = self.market(f"Round trips {n}", outcomes)
            for _ in range(150):
                i, side = rng.randrange(n), rng.choice(["yes", "no"])
                stake = round(rng.choice([0.1, 0.11, 1, 5.55, 49.99, 250, rng.uniform(0.1, 3000)]), 2)
                before = self.bob["balance"]
                try:
                    buy(self.bob, m, i, stake, side=side)
                except ApiError:
                    continue
                sell(self.bob, m, i, side=side)
                self.assertLessEqual(self.bob["balance"], before + 1e-9, (n, i, side, stake))
                self.assertGreaterEqual(self.bob["balance"], before - 0.01 - 1e-9)                          # and it costs at most a cent
                if rng.random() < 0.5:                                                                       # move the market around in between
                    try:
                        buy(self.cat, m, rng.randrange(n), round(rng.uniform(0.1, 500), 2), side=rng.choice(["yes", "no"]))
                    except ApiError:
                        pass

    def test_in_pieces_a_round_trip_is_no_better(self):
        rng = random.Random(5)
        for _ in range(60):
            m = self.market("Pieces")
            stake = round(rng.uniform(0.1, 2000), 2)
            before = self.bob["balance"]
            r = buy(self.bob, m, 0, stake)
            left = r["shares"]
            while left > 1e-9:
                part = left if rng.random() < 0.15 else left * rng.choice([0.5, 0.2, 0.05, 0.9])
                try:
                    sell(self.bob, m, 0, shares=part)
                except ApiError:
                    try:
                        sell(self.bob, m, 0)                                                                # a piece was too small: sell the lot
                    except ApiError:
                        break                                                                               # what is left is under a cent
                left = m["positions"].get(self.bob["id"], {}).get("y0", {}).get("shares", 0.0)
            self.assertLessEqual(self.bob["balance"], before + 1e-9)
            for held in m["positions"].get(self.bob["id"], {}).values():                                    # whatever is left over is worth under a cent
                ln_p, ln_q = lmsr.token_logs(m["q"], m["b"], 0, "y")
                self.assertLess(lmsr.proceeds_for_shares(ln_p, ln_q, m["b"], held["shares"]), 0.01 + 1e-9)

    def test_farming_the_rounding_with_tiny_sells_does_not_work(self):
        buy(self.bob, self.m, 0, 100)
        worth = lmsr.floor_cents(lmsr.proceeds_for_shares(*lmsr.token_logs(self.m["q"], self.m["b"], 0, "y"), self.m["b"], 1))
        before = self.bob["balance"]
        done = 0
        for _ in range(3000):
            try:
                sell(self.bob, self.m, 0, shares=0.0105)                                                    # worth about half a cent each
                done += 1
            except ApiError:
                break
        self.assertEqual(done, 0)
        self.assertEqual(self.bob["balance"], before)
        for chunk in (0.03, 0.04, 0.5):                                                                      # chunks big enough to pay out never overpay
            total_exact = 0.0
            total_paid = 0.0
            m = self.market(f"Chunks {chunk}")
            r = buy(self.bob, m, 0, 100)
            left = r["shares"]
            while left > chunk * 2:
                exact = lmsr.cost(m["q"], m["b"])
                got = sell(self.bob, m, 0, shares=chunk)["amount"]
                total_exact += exact - lmsr.cost(m["q"], m["b"])
                total_paid += got
                left -= chunk
                self.assertLessEqual(got, exact - lmsr.cost(m["q"], m["b"]) + 1e-9)
            self.assertLessEqual(total_paid, total_exact + 1e-9)
        self.assertGreater(worth, 0)

    def test_the_old_double_dip_is_gone(self):
        """Selling a bit under 1.5 cents' worth used to round UP to 2 cents. Now it rounds down to 1."""
        buy(self.bob, self.m, 0, 100)
        shares = 0.0295                                                                                     # ~1.5 cents at a price of ~0.5
        exact = lmsr.cost(self.m["q"], self.m["b"])
        got = sell(self.bob, self.m, 0, shares=shares)["amount"]
        exact -= lmsr.cost(self.m["q"], self.m["b"])
        self.assertLessEqual(got, exact + 1e-9)

    def test_many_people_trading_cannot_drain_the_market_maker(self):
        rng = random.Random(99)
        crowd = [self.ann, self.bob, self.cat]
        start = sum(u["balance"] for u in crowd)
        m = self.market("Crowd", ["a", "b", "c"])
        c0 = lmsr.cost(m["q"], m["b"])
        for _ in range(600):
            u, i, side = rng.choice(crowd), rng.randrange(3), rng.choice(["yes", "no"])
            token = markets.token_of(m, i, side)[2]
            held = m["positions"].get(u["id"], {}).get(token)
            try:
                if held and rng.random() < 0.55:
                    sell(u, m, i, side=side, **({} if rng.random() < 0.3 else {"shares": held["shares"] * rng.random()}))
                else:
                    buy(u, m, i, round(rng.uniform(0.1, 600), 2), side=side)
            except ApiError:
                pass
        for u in crowd:                                                                                      # everybody cashes out everything
            for token in list(m["positions"].get(u["id"], {})):
                i, side = int(token[1:]), "yes" if token[0] == "y" else "no"
                try:
                    sell(u, m, i, side=side)
                except ApiError:
                    pass
        spent = start - sum(u["balance"] for u in crowd)
        self.assertGreaterEqual(spent, -1e-6)                                                                # nobody as a group is ahead
        self.assertGreaterEqual(spent, lmsr.cost(m["q"], m["b"]) - c0 - 1e-6)


class Safeguards(Base):
    def test_pressing_the_button_twice_trades_once(self):
        first = buy(self.bob, self.m, 0, 60, requestId="press-0001")
        second = buy(self.bob, self.m, 0, 60, requestId="press-0001")
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["shares"], first["shares"])
        self.assertEqual(self.bob["balance"], 1_000_000 - 60)
        self.assertEqual(self.m["positions"][self.bob["id"]]["y0"]["invested"], 60.0)
        self.assertEqual(len(self.m["trades"]), 1)
        buy(self.bob, self.m, 0, 60, requestId="press-0002")                                              # a new press is a new trade
        self.assertEqual(self.bob["balance"], 1_000_000 - 120)

    def test_an_id_cannot_be_reused_for_a_different_trade_or_by_a_different_person(self):
        buy(self.bob, self.m, 0, 60, requestId="press-0001")
        self.assertEqual(err(buy, self.bob, self.m, 0, 61, requestId="press-0001").status, 409)
        self.assertEqual(err(buy, self.bob, self.m, 1, 60, requestId="press-0001").status, 409)
        other = buy(self.cat, self.m, 0, 60, requestId="press-0001")                                      # ids belong to whoever sent them
        self.assertFalse(other["duplicate"])

    def test_a_failed_attempt_does_not_use_up_its_id(self):
        poor = rich("poor_x", 5)
        circles.join(poor, self.circle["id"], self.circle["inviteCode"])
        self.assertEqual(err(buy, poor, self.m, 0, 50, requestId="retry-0001").message, "Not enough funds")
        poor["balance"] = 100.0
        self.assertFalse(buy(poor, self.m, 0, 50, requestId="retry-0001")["duplicate"])

    def test_bad_ids_are_refused(self):
        for rid in ("short", "x" * 65, "has space!!", 12345678, ["abcdefgh"], ""):
            self.assertEqual(err(buy, self.bob, self.m, 0, 5, requestId=rid).status, 400, repr(rid))

    def test_a_buy_is_refused_if_the_price_ran_away_since_the_quote(self):
        q = markets.quote(self.m, self.bob, {"outcome": 0, "amount": 100})
        buy(self.cat, self.m, 0, 400)                                                                      # somebody moves the market first
        snap = json.dumps(self.m, sort_keys=True), self.bob["balance"]
        e = err(buy, self.bob, self.m, 0, 100, minShares=q["shares"] * 0.995)
        self.assertEqual((e.status, "price moved" in e.message), (409, True))
        self.assertEqual((json.dumps(self.m, sort_keys=True), self.bob["balance"]), snap)
        fresh = markets.quote(self.m, self.bob, {"outcome": 0, "amount": 100})
        self.assertEqual(buy(self.bob, self.m, 0, 100, minShares=fresh["shares"] * 0.995)["shares"], fresh["shares"])

    def test_a_sell_is_refused_if_the_price_fell_since_the_quote(self):
        r = buy(self.bob, self.m, 0, 200)
        q = markets.quote(self.m, self.bob, {"outcome": 0, "action": "sell", "shares": r["shares"]})
        sell(self.cat, self.m, 1) if False else buy(self.cat, self.m, 1, 500)                              # the other side gets backed: ours falls
        e = err(sell, self.bob, self.m, 0, minAmount=q["amount"] * 0.995)
        self.assertEqual(e.status, 409)
        self.assertIn(self.bob["id"], self.m["positions"])

    def test_the_agreed_price_may_be_met_or_beaten(self):
        q = markets.quote(self.m, self.bob, {"outcome": 0, "amount": 10})
        self.assertGreaterEqual(buy(self.bob, self.m, 0, 10, minShares=q["shares"])["shares"], q["shares"] - 1e-9)

    def test_guard_values_must_be_numbers(self):
        self.assertEqual(err(buy, self.bob, self.m, 0, 10, minShares="lots").status, 400)


class Lifecycle(Base):
    def test_nothing_can_be_bought_sold_or_quoted_after_the_deadline(self):
        buy(self.bob, self.m, 0, 50)
        self.m["closesAt"] = now_ms() - 1000
        self.assertEqual(markets.state_of(self.m), "closed")
        for fn in (lambda: buy(self.bob, self.m, 0, 5), lambda: sell(self.bob, self.m, 0),
                   lambda: markets.quote(self.m, self.bob, {"outcome": 0, "amount": 5}),
                   lambda: markets.quote(self.m, self.bob, {"outcome": 0, "action": "sell", "shares": 1})):
            self.assertIn("closed", err(fn).message)
        self.assertIn(self.bob["id"], self.m["positions"])                                                  # your shares are still yours

    def test_nothing_can_be_traded_once_it_is_settled_or_called_off(self):
        buy(self.bob, self.m, 0, 50)
        markets.resolve(self.ann, self.m, 0)
        for fn in (lambda: buy(self.bob, self.m, 0, 5), lambda: sell(self.bob, self.m, 0),
                   lambda: markets.quote(self.m, self.bob, {"outcome": 0, "amount": 5})):
            self.assertIn("no longer open", err(fn).message)
        other = self.market("Called off?")
        buy(self.bob, other, 0, 50)
        markets.cancel(self.ann, other)
        self.assertIn("no longer open", err(buy, self.bob, other, 0, 5).message)
        self.assertIn("no longer open", err(sell, self.bob, other, 0).message)

    def test_a_deadline_in_the_future_leaves_trading_open(self):
        self.m["closesAt"] = now_ms() + 3_600_000
        buy(self.bob, self.m, 0, 5)


class Settlement(Base):
    def test_winning_shares_pay_one_dollar_each_and_losers_nothing(self):
        a = buy(self.bob, self.m, 0, 100)
        buy(self.cat, self.m, 1, 100)
        b0 = (self.bob["balance"], self.cat["balance"])
        markets.resolve(self.ann, self.m, 0)
        self.assertEqual(round(self.bob["balance"] - b0[0], 2), round(a["shares"], 2))
        self.assertEqual(self.cat["balance"], b0[1])

    def test_named_outcomes_pay_yes_and_no_correctly(self):
        m = self.market("Who wins?", ["Ann", "Ben", "Cy"])
        y = buy(self.bob, m, 0, 60)                                        # YES Ann
        n = buy(self.cat, m, 0, 60, side="no")                             # NO Ann
        before = (self.bob["balance"], self.cat["balance"])
        markets.resolve(self.ann, m, 2)                                    # Cy wins: Ann loses
        self.assertEqual(self.bob["balance"], before[0])
        self.assertEqual(round(self.cat["balance"] - before[1], 2), round(n["shares"], 2))
        self.assertGreater(y["shares"], 0)

    def test_after_selling_some_the_rest_still_settles_properly(self):
        r = buy(self.bob, self.m, 0, 100)
        sell(self.bob, self.m, 0, shares=r["shares"] * 0.25)
        left = self.m["positions"][self.bob["id"]]["y0"]["shares"]
        before = self.bob["balance"]
        markets.resolve(self.ann, self.m, 0)
        self.assertEqual(round(self.bob["balance"] - before, 2), round(left, 2))

    def test_calling_it_off_refunds_what_is_still_invested(self):
        r = buy(self.bob, self.m, 0, 100)
        out = sell(self.bob, self.m, 0, shares=r["shares"] / 2)
        buy(self.cat, self.m, 1, 40)
        start = (self.bob["balance"], self.cat["balance"])
        markets.cancel(self.ann, self.m)
        self.assertEqual(round(self.bob["balance"] - start[0], 2), 50.0)
        self.assertEqual(round(self.cat["balance"] - start[1], 2), 40.0)
        self.assertGreater(out["amount"], 0)

    def test_net_worth_and_cash_out_values_match_what_selling_would_pay(self):
        r = buy(self.bob, self.m, 0, 100)
        row = markets.detail(self.m, self.bob)["myPositions"][0]
        before = self.bob["balance"]
        out = sell(self.bob, self.m, 0)
        self.assertEqual(row["value"], out["amount"])
        self.assertEqual(round(self.bob["balance"] - before, 2), out["amount"])
        self.assertGreater(r["shares"], 0)

    def test_a_market_saved_before_this_change_still_works_end_to_end(self):
        legacy = {"id": "legacy000001", "circleId": self.circle["id"], "creatorId": self.ann["id"], "question": "An old bet from last month?",
                  "description": "", "category": "General", "emoji": "🎲", "outcomes": ["Yes", "No"], "b": 100.0, "q": [30.0, 0.0],
                  "status": "open", "closesAt": None, "createdAt": 1, "resolvedAt": None, "winner": None, "volume": 55.0,
                  "positions": {self.bob["id"]: {"y0": {"shares": 31.5, "invested": 20.0}}}, "trades": [], "comments": [],
                  "history": [{"t": 1, "p": [0.5, 0.5]}]}
        db()["markets"][legacy["id"]] = legacy
        legacy = json.loads(json.dumps(legacy))                            # as if it had just been loaded from the file
        db()["markets"][legacy["id"]] = legacy
        self.assertEqual(legacy["b"], 100.0)
        self.assertEqual(sum(r["pct"] for r in markets.summary(legacy, self.bob)["outcomes"]), 100)
        row = markets.detail(legacy, self.bob)["myPositions"][0]
        self.assertGreater(row["value"], 0)
        q = markets.quote(legacy, self.cat, {"outcome": 1, "amount": 25})
        got = buy(self.cat, legacy, 1, 25)
        self.assertEqual(got["shares"], q["shares"])
        self.assertEqual(legacy["b"], 100.0)                                # nobody's market was re-priced
        sell(self.bob, legacy, 0, shares=10)
        before = self.bob["balance"]
        markets.resolve(self.ann, legacy, 0)
        self.assertEqual(round(self.bob["balance"] - before, 2), round(21.5, 2))

    def test_new_markets_get_the_one_standard_depth_whatever_the_old_setting_said(self):
        for old in ("volatile", "stable", "deep", "whale", "nonsense", None, 12, {"x": 1}):
            m = markets.create(self.ann, {"circleId": self.circle["id"], "question": "Old forms still submit?", "liquidity": old})
            self.assertEqual(m["b"], config.MARKET_LIQUIDITY)

    def test_trade_records_survive_a_save_and_reload(self):
        buy(self.bob, self.m, 0, 10, requestId="saved-0001")
        store.save()
        with open(store.path) as f:
            reloaded = json.load(f)
        self.assertIn(f"{self.bob['id']}:saved-0001", reloaded["idem"])
        self.assertEqual(reloaded["markets"][self.m["id"]]["b"], config.MARKET_LIQUIDITY)


class Concurrency(unittest.TestCase):
    """Real simultaneous requests through the real server."""

    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        type(self).n += 1
        tag = self.n
        self.clients, self.ids = {}, {}
        for short in ("ann", "bob", "cat", "dan"):
            c = Client(self.port)
            st, d = c.call("POST", "/api/auth/register", {"username": f"{short}{tag}", "password": "secret123"})
            self.assertEqual(st, 200)
            self.clients[short], self.ids[short] = c, d["user"]["id"]
        st, d = self.clients["ann"].call("POST", "/api/circles", {"name": f"Crew {tag}", "visibility": "private"})
        circle, code = d["circle"]["id"], d["circle"]["inviteCode"]
        for short in ("bob", "cat", "dan"):
            self.clients[short].call("POST", "/api/circles/join", {"code": code})
        st, d = self.clients["ann"].call("POST", "/api/markets", {"circleId": circle, "question": "Who is faster, really?", "outcomes": ["Ann", "Bob", "Cy"]})
        self.mid = d["market"]["id"]
        self.market = db()["markets"][self.mid]

    def fire(self, jobs):
        """Starts every job at the same moment and returns their (status, body) answers."""
        gate, out = threading.Barrier(len(jobs)), [None] * len(jobs)

        def run(k, fn):
            gate.wait()
            out[k] = fn()
        threads = [threading.Thread(target=run, args=(k, fn)) for k, fn in enumerate(jobs)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        return out

    def cash(self, short):
        return db()["users"][self.ids[short]]["balance"]

    def test_you_cannot_spend_the_same_money_twice(self):
        bob = self.clients["bob"]
        jobs = [lambda k=k: bob.call("POST", f"/api/markets/{self.mid}/trade", {"outcome": 0, "amount": 300, "requestId": f"spend-{k:04d}-xx"}) for k in range(12)]
        answers = self.fire(jobs)
        ok = [a for a in answers if a[0] == 200]
        self.assertEqual(len(ok), 3)                                         # $1,000 pays for three $300 bets and not a fourth
        self.assertTrue(all(a[0] == 400 and a[1]["error"] == "Not enough funds" for a in answers if a[0] != 200))
        self.assertEqual(self.cash("bob"), 100.0)
        self.assertAlmostEqual(self.market["positions"][self.ids["bob"]]["y0"]["invested"], 900.0)

    def test_you_cannot_sell_the_same_shares_twice(self):
        bob = self.clients["bob"]
        st, d = bob.call("POST", f"/api/markets/{self.mid}/trade", {"outcome": 1, "amount": 400})
        shares = d["trade"]["shares"]
        jobs = [lambda k=k: bob.call("POST", f"/api/markets/{self.mid}/trade", {"outcome": 1, "action": "sell", "shares": shares * 0.6, "requestId": f"sell-{k:04d}-xx"}) for k in range(10)]
        answers = self.fire(jobs)
        self.assertEqual(sum(1 for a in answers if a[0] == 200), 1)
        self.assertTrue(all("only hold" in a[1]["error"] for a in answers if a[0] != 200))
        self.assertAlmostEqual(self.market["positions"][self.ids["bob"]]["y1"]["shares"], shares * 0.4, places=6)

    def test_the_same_press_sent_many_times_at_once_trades_once(self):
        cat = self.clients["cat"]
        jobs = [lambda: cat.call("POST", f"/api/markets/{self.mid}/trade", {"outcome": 2, "amount": 70, "requestId": "double-click-1"}) for _ in range(10)]
        answers = self.fire(jobs)
        self.assertTrue(all(a[0] == 200 for a in answers))
        self.assertEqual(sum(1 for a in answers if not a[1]["trade"]["duplicate"]), 1)
        self.assertEqual(self.cash("cat"), 930.0)
        self.assertEqual(len(self.market["trades"]), 1)

    def test_a_storm_of_mixed_trades_stays_consistent(self):
        rng = random.Random(1234)
        shorts = ("ann", "bob", "cat", "dan")
        start = {s: self.cash(s) for s in shorts}
        c0 = lmsr.cost(self.market["q"], self.market["b"])
        log = []

        def job(short, k):
            def go():
                body = {"outcome": rng.randrange(3), "side": rng.choice(["yes", "no"]), "requestId": f"storm-{short}-{k:04d}"}
                if rng.random() < 0.35:
                    body.update({"action": "sell", "shares": round(rng.uniform(0.5, 120), 4)})
                else:
                    body["amount"] = round(rng.uniform(0.1, 250), 2)
                st, d = self.clients[short].call("POST", f"/api/markets/{self.mid}/trade", body)
                if st == 200:
                    log.append((short, d["trade"]["action"], d["trade"]["amount"]))
                return st
            return go
        answers = self.fire([job(rng.choice(shorts), k) for k in range(80)])
        self.assertTrue(all(a in (200, 400) for a in answers), answers)
        self.assertGreater(sum(1 for a in answers if a == 200), 10)
        for s in shorts:                                                      # money moved exactly as the answers said, to the cent
            net = sum(-amt if act == "buy" else amt for who, act, amt in log if who == s)
            self.assertAlmostEqual(self.cash(s) - start[s], net, places=2)
            self.assertGreaterEqual(self.cash(s), 0)
        taken = sum(amt if act == "buy" else -amt for _, act, amt in log)
        self.assertGreaterEqual(taken, lmsr.cost(self.market["q"], self.market["b"]) - c0 - 1e-6)
        for a, b in zip(lmsr.prices(implied_q(self.market), self.market["b"]), probs(self.market)):
            self.assertAlmostEqual(a, b, places=6)                            # what people hold and what the price says still agree
        self.assertAlmostEqual(sum(probs(self.market)), 1.0, places=9)
        for toks in self.market["positions"].values():
            self.assertTrue(all(p["shares"] > 0 and p["invested"] >= -1e-9 for p in toks.values()))

    def test_closing_while_people_are_trading_lets_nothing_through_afterwards(self):
        bob, cat = self.clients["bob"], self.clients["cat"]
        results = []

        def close():
            self.market["closesAt"] = now_ms() - 1
            return 0
        jobs = [close] + [lambda k=k: results.append(bob.call("POST", f"/api/markets/{self.mid}/trade", {"outcome": 0, "amount": 5, "requestId": f"late-{k:04d}-xx"})[0]) or 0 for k in range(6)]
        self.fire(jobs)
        n_before = len(self.market["trades"])
        st, d = cat.call("POST", f"/api/markets/{self.mid}/trade", {"outcome": 0, "amount": 5})
        self.assertEqual((st, "closed" in d["error"]), (400, True))
        self.assertEqual(len(self.market["trades"]), n_before)


if __name__ == "__main__":
    unittest.main()
