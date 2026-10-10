"""XP and ranks: the ladder, divisions, promotions, daily caps, repeats, what counts and what does not, and persistence."""
import copy
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import activity, challenges, economy, games, inbox, ledger, markets, milestones, progress, rules, users, weekly   # noqa: E402
from backend.store import LOCK, db, store                                                                                      # noqa: E402
from backend.util import ApiError, DAY_MS, prev_week_key, week_bounds, week_key                                               # noqa: E402
from tests.econ import circle_of, mk                                                                                                     # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                                                     # noqa: E402

HOUR = 3_600_000
START, _ = week_bounds(week_key())
DAYS = [START + i * DAY_MS + 12 * HOUR for i in range(7)]          # noon on each day of this week
T0 = DAYS[2]


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


class TheLadder(unittest.TestCase):
    def test_sixteen_steps_from_bronze_iii_to_master(self):
        lv = rules.levels()
        self.assertEqual(len(lv), 16)
        self.assertEqual([l["label"] for l in lv][:4], ["Bronze III", "Bronze II", "Bronze I", "Silver III"])
        self.assertEqual([l["label"] for l in lv][-4:], ["Diamond III", "Diamond II", "Diamond I", "Master"])
        self.assertEqual([t[1] for t in rules.TIERS], ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"])
        self.assertEqual([l["xp"] for l in lv], sorted(l["xp"] for l in lv), "each step needs more XP than the one before")
        self.assertEqual(lv[0]["xp"], 0)

    def test_three_divisions_per_tier_except_master(self):
        for key, _ in rules.TIERS[:-1]:
            self.assertEqual([l["division"] for l in rules.levels() if l["tier"] == key], [3, 2, 1])
        self.assertEqual([l["division"] for l in rules.levels() if l["tier"] == "master"], [None])

    def test_where_xp_puts_you(self):
        cases = {0: "Bronze III", 99: "Bronze III", 100: "Bronze II", 249: "Bronze II", 250: "Bronze I", 450: "Silver III", 1000: "Silver I",
                 1400: "Gold III", 2500: "Gold I", 3200: "Platinum III", 5000: "Platinum I", 6200: "Diamond III", 9200: "Diamond I",
                 10999: "Diamond I", 11000: "Master", 10 ** 7: "Master", -50: "Bronze III"}
        for xp, label in cases.items():
            self.assertEqual(rules.rank_for(xp)["label"], label, xp)

    def test_progress_toward_the_next_step(self):
        r = rules.rank_for(175)
        self.assertEqual((r["label"], r["floor"], r["next"], r["nextLabel"], r["toNext"], r["pct"]), ("Bronze II", 100, 250, "Bronze I", 75, 50))
        top = rules.rank_for(20000)
        self.assertEqual((top["max"], top["next"], top["toNext"], top["pct"], top["division"]), (True, None, 0, 100, None))

    def test_the_thresholds_can_all_be_scaled_at_once(self):
        with mock.patch.object(economy, "RANK_XP_SCALE", 2.0):
            self.assertEqual(rules.rank_for(199)["label"], "Bronze III")
            self.assertEqual(rules.rank_for(200)["label"], "Bronze II")
        self.assertEqual(rules.rank_for(199)["label"], "Bronze II")


class Promotions(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann")

    def test_crossing_a_threshold_promotes_records_it_and_tells_the_person(self):
        progress.grant(self.u, 90, "test", "a")
        self.assertEqual(progress.rank_of(self.u)["label"], "Bronze III")
        progress.grant(self.u, 15, "test", "b")
        self.assertEqual(progress.rank_of(self.u)["label"], "Bronze II")
        g = progress.state(self.u)
        self.assertEqual([(h["from"], h["to"]) for h in g["hist"]], [("Bronze III", "Bronze II")])
        self.assertEqual([(i["kind"], i["title"]) for i in self.u["inbox"]][0], ("promotion", "Promoted to Bronze II"))

    def test_a_big_jump_is_one_promotion_to_where_you_landed(self):
        progress.grant(self.u, 1000, "test", "big")
        self.assertEqual(progress.rank_of(self.u)["label"], "Silver I")
        self.assertEqual([(h["from"], h["to"]) for h in progress.state(self.u)["hist"]], [("Bronze III", "Silver I")])

    def test_the_same_award_twice_gives_xp_once(self):
        self.assertEqual(progress.grant(self.u, 40, "test", "same"), 40)
        self.assertEqual(progress.grant(self.u, 40, "test", "same"), 0)
        self.assertEqual(progress.xp_of(self.u), 40)

    def test_zero_and_negative_awards_do_nothing(self):
        for amount in (0, -10):
            self.assertEqual(progress.grant(self.u, amount, "test", f"z{amount}"), 0)
        self.assertEqual(progress.xp_of(self.u), 0)

    def test_no_demotion_xp_only_goes_up(self):
        progress.grant(self.u, 600, "test", "up")
        self.assertEqual(progress.rank_of(self.u)["label"], "Silver III")
        self.u["balance"] = 0.0
        ledger.post(self.u, "accumulated", 0.0, "test")
        self.assertEqual(progress.rank_of(self.u)["label"], "Silver III", "being broke is not a rank event")

    def test_everybody_starts_at_bronze_iii_and_it_is_shown_in_lists(self):
        self.assertEqual(users.public(self.u)["rank"], {"t": "bronze", "d": 3, "l": "Bronze III"})
        progress.grant(self.u, 2500, "test", "gold")
        self.assertEqual(users.public(self.u)["rank"], {"t": "gold", "d": 1, "l": "Gold I"})
        progress.grant(self.u, 9000, "test", "master")
        self.assertEqual(users.public(self.u)["rank"], {"t": "master", "d": 0, "l": "Master"})

    def test_it_survives_a_restart(self):
        progress.grant(self.u, 700, "test", "keep")
        store.save()
        store.load()
        again = users.get(self.u["id"])
        self.assertEqual((progress.xp_of(again), progress.rank_of(again)["label"]), (700, "Silver II"))
        self.assertEqual(progress.grant(again, 700, "test", "keep"), 0, "the record of what was already awarded survives too")


class WhatEarnsXp(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", accum=2000)
        self.m = markets.create(mk("maker"), {"scope": "site", "question": "Will it ever be quiet?"})

    def rec(self, kind, ref, now=T0, **kw):
        return activity.record(self.u, kind, ref, now=now, **kw)

    def test_each_kind_of_action_is_worth_a_little(self):
        self.assertEqual(self.rec("casino", "r1", amount=5, game="dice")["xp"], 2)
        self.assertEqual(self.rec("polls", "b1", amount=5, market="m1", category="Sports")["xp"], 5)
        self.assertEqual(self.rec("exchange", "t1", amount=50, symbol="NEXO")["xp"], 3)
        self.assertEqual(self.rec("poker", "h1")["xp"], 1)
        self.assertEqual(self.rec("create", "p1")["xp"], 4)
        self.assertEqual(progress.xp_of(self.u), 15)

    def test_circles_count_as_taking_part_but_are_worth_no_xp(self):
        r = self.rec("circle", "c1")
        self.assertEqual(r["xp"], 0)
        self.assertIn("circles", progress.state(self.u)["features"])

    def test_each_kind_stops_paying_after_its_daily_cap(self):
        paid = [self.rec("casino", f"r{i}", amount=5, game="dice")["xp"] for i in range(15)]
        self.assertEqual(paid, [2] * 10 + [0] * 5, "ten rounds a day are paid, the rest are not")
        self.assertEqual(progress.xp_of(self.u), 20)
        poll_xp = [self.rec("polls", f"b{i}", amount=5, market=f"m{i}")["xp"] for i in range(6)]
        self.assertEqual(poll_xp, [5, 5, 5, 5, 0, 0])

    def test_a_new_day_starts_fresh(self):
        for i in range(12):
            self.rec("casino", f"d1-{i}", amount=5, game="dice")
        before = progress.xp_of(self.u)
        self.assertEqual(self.rec("casino", "d2-0", now=DAYS[3], amount=5, game="dice")["xp"], 2)
        self.assertEqual(progress.xp_of(self.u), before + 2)

    def test_the_most_a_day_can_pay_is_the_sum_of_the_caps_and_never_more_than_the_ceiling(self):
        def everything(tag, now):
            total = 0
            for i in range(12):
                total += (self.rec("casino", f"{tag}c{i}", now=now, amount=5, game="dice") or {"xp": 0})["xp"]
            for i in range(6):
                total += (self.rec("polls", f"{tag}p{i}", now=now, amount=5, market=f"{tag}m{i}") or {"xp": 0})["xp"]
            for i in range(4):
                total += (self.rec("exchange", f"{tag}e{i}", now=now, amount=50, symbol="NEXO") or {"xp": 0})["xp"]
            for i in range(8):
                total += (self.rec("poker", f"{tag}k{i}", now=now) or {"xp": 0})["xp"]
            for i in range(4):
                total += (self.rec("create", f"{tag}n{i}", now=now) or {"xp": 0})["xp"]
            return total
        self.assertEqual(everything("a", DAYS[0]), 60, "every kind at its own cap is exactly the 60 XP ceiling")
        with mock.patch.object(rules, "XP_DAILY_CAP", 25):
            self.assertEqual(everything("b", DAYS[1]), 25, "and a lower ceiling clips the day, whatever was done")
        self.assertEqual(progress.state(self.u)["day"]["xp"], 25)

    def test_how_much_you_stake_does_not_change_the_xp(self):
        small = self.rec("casino", "s", amount=1.0, game="dice")["xp"]
        huge = self.rec("casino", "h", amount=10 ** 9, game="dice")["xp"]
        self.assertEqual(small, huge)

    def test_stakes_below_the_minimum_do_not_count(self):
        self.assertIsNone(self.rec("casino", "tiny", amount=0.5, game="dice"))
        self.assertIsNone(self.rec("polls", "tiny", amount=0.99, market="m1"))
        self.assertIsNone(self.rec("exchange", "tiny", amount=0.0, symbol="NEXO"))
        self.assertIsNone(self.rec("casino", "none", amount=None, game="dice"))
        self.assertEqual(progress.xp_of(self.u), 0)
        self.assertEqual(progress.state(self.u)["m"], {})

    def test_practice_rounds_never_count(self):
        demo = games.demo_account(self.u)
        self.assertIsNone(activity.record(demo, "casino", "demo-1", now=T0, amount=50, game="dice"))
        self.assertEqual(progress.xp_of(self.u), 0)
        games.dice(demo, {"amount": 10, "direction": "over", "target": 50})
        self.assertEqual(progress.xp_of(self.u), 0)
        self.assertNotIn("goals", demo)

    def test_an_unknown_game_or_kind_is_ignored(self):
        self.assertIsNone(self.rec("casino", "x", amount=5, game="horses"))
        self.assertIsNone(self.rec("casino", "x2", amount=5, game=None))
        self.assertIsNone(self.rec("store", "x3", amount=500))
        self.assertIsNone(self.rec("transfer", "x4", amount=500))
        self.assertEqual(progress.xp_of(self.u), 0)

    def test_the_same_action_twice_counts_once(self):
        self.assertEqual(self.rec("casino", "same-round", amount=5, game="dice")["xp"], 2)
        self.assertIsNone(self.rec("casino", "same-round", amount=5, game="dice"))
        self.assertEqual(progress.state(self.u)["m"]["casino_rounds"], 1)
        self.assertEqual(progress.xp_of(self.u), 2)

    def test_betting_again_in_the_same_poll_the_same_day_is_not_a_second_bet_for_xp(self):
        self.assertEqual(self.rec("polls", "b1", amount=5, market="m1")["xp"], 5)
        again = self.rec("polls", "b2", amount=5, market="m1")
        self.assertEqual((again["counted"], again["xp"]), (False, 0))
        self.assertEqual(progress.state(self.u)["m"]["market_bets"], 1)

    def test_two_requests_at_once_record_one(self):
        out = []

        def go():
            with LOCK:
                out.append(activity.record(self.u, "casino", "race", now=T0, amount=5, game="dice"))
        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len([o for o in out if o]), 1)
        self.assertEqual(progress.xp_of(self.u), 2)

    def test_a_real_bet_a_real_round_and_a_real_trade_earn_it_but_a_refused_one_does_not(self):
        markets.trade(self.u, self.m, {"outcome": 0, "amount": 20})
        self.assertEqual(progress.xp_of(self.u), 5)
        before = progress.xp_of(self.u)
        err(markets.trade, self.u, self.m, {"outcome": 0, "amount": 10 ** 9})                 # not enough funds: refused
        err(markets.trade, self.u, self.m, {"outcome": 0, "amount": "nonsense"})
        err(games.limbo, self.u, {"amount": 10 ** 9, "target": 2})
        self.assertEqual(progress.xp_of(self.u), before, "a rejected transaction earns nothing")
        games.limbo(self.u, {"amount": 5, "target": 1.5})
        self.assertEqual(progress.xp_of(self.u), before + 2)

    def test_the_balance_and_the_weekly_results_do_not_matter(self):
        rich = mk("rich", weekly=10 ** 9, accum=10 ** 9)
        poor = mk("poor", weekly=2, accum=0)
        for u in (rich, poor):
            activity.record(u, "casino", f"r-{u['username']}", now=T0, amount=5, game="dice")
        self.assertEqual(progress.xp_of(rich), progress.xp_of(poor))

    def test_looking_around_and_buying_cosmetics_earn_nothing(self):
        from backend import cosmetics
        before = copy.deepcopy(progress.state(self.u))
        cosmetics.buy(self.u, "avatar_chicken")
        self.assertEqual(self.u["accum"], 1880.0)
        self.assertEqual(progress.state(self.u), before, "a purchase is not progression")

    def test_the_rank_does_not_depend_on_money_it_takes_a_lot_of_taking_part(self):
        # the best possible day is capped, so even the keenest player needs weeks to climb
        per_day = rules.XP_DAILY_CAP
        self.assertGreater(rules.levels()[3]["xp"] / per_day, 7, "Silver III takes more than a week of perfect days")
        self.assertGreater(rules.levels()[15]["xp"] / per_day, 150, "Master takes months")


class WeeklyThings(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann")

    def test_a_steady_week_pays_a_bonus_once_at_the_close(self):
        prev = prev_week_key(week_key())
        w = challenges.week_state(self.u, prev)
        w["facts"]["days"] = ["a", "b", "c"]
        self.assertEqual(progress.close_week(prev), 1)
        self.assertEqual(progress.xp_of(self.u), rules.STEADY_WEEK_XP)
        self.assertEqual(progress.close_week(prev), 0)
        self.assertEqual(progress.xp_of(self.u), rules.STEADY_WEEK_XP, "closing again changes nothing")

    def test_two_days_are_not_a_steady_week(self):
        prev = prev_week_key(week_key())
        challenges.week_state(self.u, prev)["facts"]["days"] = ["a", "b"]
        self.assertEqual(progress.close_week(prev), 0)

    def test_rank_and_xp_come_through_the_weekly_reset_unchanged(self):
        progress.grant(self.u, 500, "test", "x")
        self.u["wk"]["week"] = prev_week_key(week_key())
        db()["meta"]["week"] = prev_week_key(week_key())
        weekly.tick()
        self.assertEqual((progress.xp_of(self.u), progress.rank_of(self.u)["label"]), (500, "Silver III"))
        self.assertEqual(self.u["balance"], 1000.0)

    def test_the_weekly_leaderboard_and_the_rank_are_separate_things(self):
        c = circle_of(self.u, mk("ben"))
        progress.grant(self.u, 5000, "test", "big")
        rows = {r["user"]["username"]: r for r in weekly.standings(c, week_key())}
        self.assertEqual(rows["ann"]["delta"], 0.0, "XP does not move the week's performance")
        self.assertEqual(rows["ann"]["user"]["rank"]["l"], "Platinum I", "the leaderboard row carries the rank for display only")
        self.assertEqual(rows["ann"]["position"], 1, "ties are broken by the usual rules (older account first), not by rank")


if __name__ == "__main__":
    unittest.main()
