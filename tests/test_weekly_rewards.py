"""Rewards by weekly position: how the leaderboard is calculated, tie-breaks, small circles, exactly-once delivery."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, config, economy, games, ledger, markets, users, weekly   # noqa: E402
from backend.store import db, store                                                    # noqa: E402
from backend.util import ApiError, now_ms, prev_week_key, week_bounds, week_key       # noqa: E402
from tests.econ import books_balance, circle_of, gain, mk                              # noqa: E402
from tests.helpers import fresh_store, restore_store_path                              # noqa: E402


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def rewards_of(c, week=None):
    recap = c["recaps"][week or week_key()]
    return {uid: r["amount"] / 100 for uid, r in recap["rewards"].items()}


class Leaderboard(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.names = ["ann", "ben", "cat", "dan", "eve"]
        self.u = {n: mk(n) for n in self.names}
        self.c = circle_of(self.u["ann"], *[self.u[n] for n in self.names[1:]])

    def rows(self):
        return {r["user"]["username"]: r for r in weekly.standings(self.c, week_key())}

    def test_performance_is_what_you_hold_minus_where_you_started_minus_handouts(self):
        gain(self.u["ann"], 120)
        gain(self.u["ben"], -80)
        users.deposit(self.u["cat"], 5000, config.ADMIN_PASSWORD)             # a top-up is not a win
        rows = self.rows()
        self.assertEqual(rows["ann"]["delta"], 120.0)
        self.assertEqual(rows["ben"]["delta"], -80.0)
        self.assertEqual(rows["cat"]["delta"], 0.0)
        self.assertEqual(rows["cat"]["value"], 6000.0)
        self.assertEqual([rows[n]["position"] for n in ("ann", "cat", "dan", "eve", "ben")][:2], [1, 2][:2])

    def test_the_accumulated_account_and_what_you_spend_there_do_not_count(self):
        ledger.post(self.u["ann"], "accumulated", 900, "weekly.reward")
        ledger.post(self.u["ben"], "accumulated", 900, "weekly.reward")
        ledger.post(self.u["ben"], "accumulated", -400, "store.buy")
        self.assertEqual({n: r["delta"] for n, r in self.rows().items()}, dict.fromkeys(self.names, 0.0))

    def test_open_bets_and_unfinished_rounds_count_as_money_you_hold(self):
        m = markets.create(self.u["ann"], {"circleId": self.c["id"], "question": "Will it hold up?"})
        before = self.rows()["ann"]["value"]
        markets.trade(self.u["ann"], m, {"outcome": 0, "amount": 100})
        self.assertAlmostEqual(self.rows()["ann"]["value"], before, delta=1.0)    # 100 left the cash, ~100 is working
        with mock.patch.object(games, "shuffle", lambda items: items):
            games.mines_start(self.u["ben"], {"amount": 50, "size": 25, "mines": 3})
        self.assertEqual(self.rows()["ben"]["value"], 1000.0)                    # the stake in the round still counts
        self.assertEqual(self.rows()["ben"]["delta"], 0.0)

    def test_order_and_tie_breakers_are_fixed(self):
        # all level: held at the end is equal too, so the older account goes first, then the lower id
        for i, n in enumerate(self.names):
            self.u[n]["createdAt"] = 1_000_000 + (3 - i) * 10 if i < 3 else 1_000_000
        order = [r["user"]["username"] for r in weekly.standings(self.c, week_key())]
        again = [r["user"]["username"] for r in weekly.standings(self.c, week_key())]
        self.assertEqual(order, again)
        self.assertEqual(set(order), set(self.names))
        created = [users.by_username(n)["createdAt"] for n in order]
        self.assertEqual(created, sorted(created))

    def test_a_tie_on_performance_goes_to_whoever_holds_more_then_the_older_account(self):
        a, b = self.u["ann"], self.u["ben"]
        # equal performance, different holdings: ben started $50 higher and ended $50 higher
        b["balance"] += 50.0
        b["wk"]["start_c"] += 5000
        rows = self.rows()
        self.assertEqual(rows["ann"]["delta"], rows["ben"]["delta"])
        self.assertLess(rows["ben"]["position"], rows["ann"]["position"])         # holds more
        b["balance"] -= 50.0
        b["wk"]["start_c"] -= 5000
        a["createdAt"], b["createdAt"] = 100, 200                                  # now fully level: older first
        rows = self.rows()
        self.assertLess(rows["ann"]["position"], rows["ben"]["position"])
        a["createdAt"] = b["createdAt"] = 100                                      # and finally the id decides
        rows = self.rows()
        first = min((a, b), key=lambda u: u["id"])["username"]
        self.assertEqual(min(("ann", "ben"), key=lambda n: rows[n]["position"]), first)

    def test_the_hot_seat_is_the_worst_week_not_the_smallest_balance(self):
        gain(self.u["ann"], -300)
        gain(self.u["eve"], 10)
        users.deposit(self.u["ben"], 100000, config.ADMIN_PASSWORD)
        self.assertEqual([r["user"]["username"] for r in weekly.bottom(weekly.standings(self.c, week_key()))], ["ann"])


class Rewards(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.names = ["ann", "ben", "cat", "dan", "eve", "fay"]
        self.u = {n: mk(n) for n in self.names}
        self.c = circle_of(self.u["ann"], *[self.u[n] for n in self.names[1:]])
        for n, g in zip(self.names, (60, 40, 20, 0, -20, -40)):
            gain(self.u[n], g)

    def close(self, week=None):
        weekly.finalize_week(week or week_key())

    def test_each_position_earns_its_configured_amount(self):
        self.close()
        got = rewards_of(self.c)
        by_name = {users.get(uid)["username"]: amt for uid, amt in got.items()}
        self.assertEqual(by_name, {"ann": 400.0, "ben": 250.0, "cat": 150.0, "dan": 100.0, "eve": 50.0, "fay": 25.0})
        for n, amt in by_name.items():
            self.assertEqual(self.u[n]["accum"], amt, n)
            self.assertTrue(books_balance(self.u[n]))

    def test_rewards_go_to_the_accumulated_account_never_the_weekly_one(self):
        weekly_before = {n: u["balance"] for n, u in self.u.items()}
        self.close()
        for n, u in self.u.items():
            self.assertEqual(u["balance"], weekly_before[n])
            row = next(r for r in ledger.entries(u) if r["reason"] == "weekly.reward")
            self.assertEqual((row["account"], row["external"]), ("accumulated", False))
            self.assertEqual(row["ref"], f"{week_key()}:{self.c['id']}")

    def test_the_final_leaderboard_is_saved_with_positions_and_rewards(self):
        self.close()
        recap = self.c["recaps"][week_key()]
        self.assertEqual([r["position"] for r in recap["standings"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual([users.get(r["userId"])["username"] for r in recap["standings"]], self.names)
        self.assertEqual(recap["rules"]["rewards"], economy.WEEKLY_REWARDS)
        self.assertEqual(recap["active"], 6)
        self.assertTrue(all(r["paid"] and r["txid"] for r in recap["rewards"].values()))

    def test_you_can_look_back_at_any_past_week_with_positions_and_rewards(self):
        self.close()
        later = prev_week_key(week_key())
        self.c["recaps"][later] = json.loads(json.dumps(self.c["recaps"][week_key()]))
        v = weekly.view(self.c, self.u["ben"], later)
        self.assertEqual([(r["user"]["username"], r["position"], r["reward"]) for r in v["standings"]][:2], [("ann", 1, 400.0), ("ben", 2, 250.0)])
        self.assertEqual(v["me"]["position"], 2)
        self.assertEqual(v["me"]["reward"], 250.0)
        self.assertTrue(v["me"]["paid"])
        self.assertEqual(sorted(v["weeks"]), sorted([later, week_key()]))

    def test_a_week_of_doing_nothing_earns_no_place_and_no_reward(self):
        users.get(self.u["dan"]["id"])["stats"].clear()                       # dan sat the week out
        self.close()
        got = rewards_of(self.c)
        self.assertNotIn(self.u["dan"]["id"], got)
        by_name = {users.get(uid)["username"]: amt for uid, amt in got.items()}
        self.assertEqual(by_name, {"ann": 400.0, "ben": 250.0, "cat": 150.0, "eve": 100.0, "fay": 50.0})   # places close ranks around dan
        rows = {r["user"]["username"]: r for r in weekly.standings(self.c, week_key())}
        self.assertFalse(rows["dan"]["active"])

    def test_small_circles_are_paid_on_a_sliding_scale_and_a_lone_player_gets_nothing(self):
        for n, expected in ((1, 0.0), (2, 0.25), (3, 0.5), (4, 0.75), (5, 1.0), (9, 1.0)):
            self.assertAlmostEqual(economy.reward_scale(n), expected)
        fresh_store()
        a, b = mk("ann"), mk("ben")
        pair = circle_of(a, b)
        gain(a, 10)
        weekly.finalize_week(week_key())
        self.assertEqual(rewards_of(pair), {a["id"]: 100.0, b["id"]: 62.5})
        fresh_store()
        a, b, c3 = mk("ann"), mk("ben", active=False), mk("cat", active=False)
        trio = circle_of(a, b, c3)
        weekly.finalize_week(week_key())
        self.assertEqual(rewards_of(trio), {}, "one active member is not a contest")
        self.assertEqual(a["accum"], 0.0)

    def test_circles_with_one_member_have_no_week_to_settle(self):
        fresh_store()
        solo = mk("solo")
        c = circle_of(solo)
        weekly.finalize_week(week_key())
        self.assertNotIn(week_key(), c["recaps"])
        self.assertEqual(solo["accum"], 0.0)

    def test_somebody_in_several_circles_is_paid_for_their_best_finish_only(self):
        other = circle_of(self.u["fay"], self.u["ann"], mk("gus"), mk("hal"), mk("ivy"), name="Second")
        for n in ("gus", "hal", "ivy"):
            gain(users.by_username(n), -500)
        self.close()
        # ann: 1st of 6 in Crew (400) and 1st-2nd of 5 in Second: only the better one is paid
        paid = [r for r in ledger.entries(self.u["ann"]) if r["reason"] == "weekly.reward"]
        self.assertEqual(len(paid), 1)
        self.assertEqual(self.u["ann"]["accum"], 400.0)
        note = [r for r in other["recaps"][week_key()]["standings"] if r["userId"] == self.u["ann"]["id"]][0]["rewardNote"]
        self.assertIn("better finish in another circle", note)

    def test_the_numbers_the_week_view_shows_match_what_gets_paid(self):
        v = weekly.view(self.c, self.u["cat"])
        self.assertEqual((v["me"]["position"], v["me"]["of"], v["me"]["reward"]), (3, 6, 150.0))
        self.assertGreater(v["remainingMs"], 0)
        self.assertLessEqual(v["remainingMs"], week_bounds(week_key())[1] - week_bounds(week_key())[0])
        self.assertEqual(v["rules"]["rewards"], economy.WEEKLY_REWARDS)
        self.assertEqual(v["rules"]["account"], "accumulated")
        self.assertTrue(v["provisional"])
        self.close()
        self.assertEqual(self.u["cat"]["accum"], v["me"]["reward"])

    def test_the_best_current_finish_across_circles_for_the_header(self):
        w = weekly.my_week(self.u["ann"])
        self.assertEqual((w["best"]["position"], w["best"]["of"], w["best"]["reward"]), (1, 6, 400.0))
        self.assertEqual(w["week"], week_key())
        self.assertIsNone(weekly.my_week(mk("loner")))

    def test_rewards_follow_the_configuration_and_nothing_else(self):
        with mock.patch.object(economy, "WEEKLY_REWARDS", [1000.0, 10.0]), mock.patch.object(economy, "PARTICIPATION_REWARD", 1.0):
            self.close()
        got = {users.get(uid)["username"]: a for uid, a in rewards_of(self.c).items()}
        self.assertEqual(got["ann"], 1000.0)
        self.assertEqual(got["ben"], 10.0)
        self.assertEqual(got["cat"], 1.0)


class ExactlyOnce(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = {n: mk(n) for n in ("ann", "ben", "cat")}
        self.c = circle_of(self.u["ann"], self.u["ben"], self.u["cat"])
        for n, g in zip(("ann", "ben", "cat"), (30, 20, 10)):
            gain(self.u[n], g)
        self.total = {n: 0.0 for n in self.u}

    def accum(self):
        return {n: u["accum"] for n, u in self.u.items()}

    def test_closing_the_same_week_twice_pays_once(self):
        weekly.finalize_week(week_key())
        first = self.accum()
        weekly.finalize_week(week_key())
        weekly.finalize_week(week_key())
        self.assertEqual(self.accum(), first)
        self.assertEqual(first, {"ann": 200.0, "ben": 125.0, "cat": 75.0})        # 3 active members: half scale

    def test_paying_again_changes_nothing(self):
        weekly.finalize_week(week_key())
        first = self.accum()
        self.assertEqual(weekly.pay_rewards(), [])
        self.assertEqual(weekly.pay_rewards(week_key()), [])
        self.assertEqual(self.accum(), first)
        for u in self.u.values():
            self.assertEqual(len([r for r in ledger.entries(u) if r["reason"] == "weekly.reward"]), 1)
            self.assertTrue(books_balance(u))

    def test_the_tick_pays_once_even_if_it_runs_again_and_again(self):
        db()["meta"]["week"] = prev_week_key(week_key())
        self.u["ann"]["wk"]["week"] = prev_week_key(week_key())
        for u in self.u.values():
            u["wk"]["week"] = prev_week_key(week_key())
        closing = prev_week_key(week_key())
        for u in self.u.values():                                                  # the circle's week that is closing
            u["stats"][closing] = dict(u["stats"].get(week_key(), {}))
        self.c["createdAt"] = now_ms() - 40 * 86400000
        self.assertTrue(weekly.tick())
        after = self.accum()
        self.assertEqual(sum(after.values()), 200.0 + 125.0 + 75.0 if after["ann"] else 0)
        for _ in range(5):
            weekly.tick()
        self.assertEqual(self.accum(), after)

    def test_a_crash_half_way_through_paying_is_finished_later_without_double_paying(self):
        weekly.finalize_week(week_key())                                           # decide + pay normally...
        recap = self.c["recaps"][week_key()]
        # ...then pretend the process died after the second payment: undo the third one completely
        victim = self.u["cat"]
        cid = recap["rewards"][victim["id"]]
        ledger.post(victim, "accumulated", -cid["amount"] / 100, "test.undo")
        cid["paid"] = False
        cid.pop("txid", None)
        db()["ledger"][victim["id"]] = [r for r in db()["ledger"][victim["id"]] if r["r"] != "weekly.reward"]
        before = self.accum()
        self.assertEqual(len(weekly.rewards_pending()), 1)
        weekly.pay_rewards()
        self.assertEqual(self.accum()["cat"], 75.0)
        self.assertEqual({k: v for k, v in self.accum().items() if k != "cat"}, {k: v for k, v in before.items() if k != "cat"})
        weekly.pay_rewards()
        self.assertEqual(self.accum()["cat"], 75.0)

    def test_a_failure_while_paying_leaves_the_rest_payable_and_nothing_doubled(self):
        real = ledger.post
        calls = {"n": 0}

        def flaky(user, account, amount, reason=None, **kw):
            if reason == "weekly.reward":
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RuntimeError("disk full")
            return real(user, account, amount, reason, **kw)
        with mock.patch.object(ledger, "post", flaky):
            with self.assertRaises(RuntimeError):
                weekly.finalize_week(week_key())
        paid_now = sum(self.accum().values())
        self.assertEqual(paid_now, 200.0)                                           # only the first reward made it
        self.assertEqual(len(weekly.rewards_pending()), 3 - 1)
        weekly.finalize_week(week_key())                                            # the retry: the recap exists, nothing is re-decided
        self.assertEqual(self.accum(), {"ann": 200.0, "ben": 125.0, "cat": 75.0})
        weekly.pay_rewards()
        self.assertEqual(self.accum(), {"ann": 200.0, "ben": 125.0, "cat": 75.0})

    def test_a_restart_in_between_changes_nothing(self):
        weekly.finalize_week(week_key())
        saved = json.dumps(store.data)
        before = self.accum()
        store.data = json.loads(saved)                                              # the server started again from disk
        store.load()
        for u in store.data["users"].values():
            self.assertEqual(u["accum"], before[u["username"]])
        weekly.finalize_week(week_key())
        weekly.pay_rewards()
        weekly.tick()
        self.assertEqual({u["username"]: u["accum"] for u in store.data["users"].values()}, before)

    def test_rewards_are_announced_to_the_people_they_belong_to(self):
        weekly.EVENTS.clear()
        weekly.finalize_week(week_key())
        got = {e["userId"]: (e["amount"], e["position"]) for e in weekly.EVENTS}
        self.assertEqual(got[self.u["ann"]["id"]], (200.0, 1))
        self.assertEqual(len(got), 3)
        notes = [a for a in self.u["ann"]["activity"] if a["kind"] == "reward"]
        self.assertEqual(len(notes), 1)


class PendingAtTheEndOfAWeek(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.a, self.b = mk("ann"), mk("ben")
        self.c = circle_of(self.a, self.b)
        self.cur = week_key()
        self.prev = prev_week_key(self.cur)
        for u in (self.a, self.b):
            u["wk"]["week"] = self.prev
        db()["meta"]["week"] = self.prev
        self.m = markets.create(self.a, {"circleId": self.c["id"], "question": "Will this survive the weekend?"})

    def test_open_bets_survive_the_close_and_nothing_is_duplicated_or_taken(self):
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 300})
        shares = self.m["positions"][self.a["id"]]["y0"]["shares"]
        value_before = markets.net_worth(self.a)
        weekly.tick()
        self.assertEqual(self.m["positions"][self.a["id"]]["y0"]["shares"], shares, "the position is still there, untouched")
        self.assertEqual(self.m["status"], "open")
        self.assertEqual(self.a["balance"], 1000.0, "weekly account refilled to the allocation")
        self.assertAlmostEqual(self.a["wk"]["start_c"] / 100, 1000.0 + markets.open_positions_value(self.a["id"]), places=1)
        rows = {r["user"]["username"]: r for r in weekly.standings(self.c, self.cur)}
        self.assertEqual(rows["ann"]["delta"], 0.0, "the new week starts level, carrying the bet at its current value")
        # money leaving at the close was only the leftover weekly cash, written down as such
        refill = [r for r in ledger.entries(self.a) if r["reason"] == "weekly.allocation"]
        self.assertEqual([(r["amount"], r["external"]) for r in refill], [(300.0, True)], "topped back up from $700 to $1,000")
        self.assertTrue(books_balance(self.a))
        self.assertAlmostEqual(markets.net_worth(self.a), 1000.0 + markets.open_positions_value(self.a["id"]), places=2)
        self.assertGreater(value_before, 0)

    def test_leftover_weekly_cash_above_the_allocation_expires_and_is_written_down_as_such(self):
        gain(self.a, 450)
        weekly.tick()
        self.assertEqual(self.a["balance"], 1000.0)
        expired = [r for r in ledger.entries(self.a) if r["reason"] == "weekly.expired"]
        self.assertEqual([(r["amount"], r["external"], r["account"]) for r in expired], [(-450.0, True, "weekly")])
        self.assertEqual(self.a["accum"], 0.0, "leftover weekly money is not turned into accumulated money")
        self.assertTrue(books_balance(self.a))

    def test_a_bet_that_settles_next_week_pays_into_that_weeks_weekly_account_and_counts_there(self):
        markets.trade(self.a, self.m, {"outcome": 0, "amount": 300})
        weekly.tick()
        start = self.a["wk"]["start_c"] / 100
        markets.resolve(self.a, self.m, 0)                                           # it wins: pays $1 a share
        rows = {r["user"]["username"]: r for r in weekly.standings(self.c, self.cur)}
        self.assertGreater(rows["ann"]["delta"], 0.0)                                # the win lands in the week it was settled
        self.assertAlmostEqual(rows["ann"]["value"] - start, rows["ann"]["delta"], places=2)
        self.assertTrue(books_balance(self.a))

    def test_a_casino_round_in_progress_is_not_lost_when_the_week_closes(self):
        with mock.patch.object(games, "shuffle", lambda items: items):
            games.mines_start(self.a, {"amount": 100, "size": 25, "mines": 3})
        self.assertEqual(self.a["balance"], 900.0)
        weekly.tick()
        self.assertEqual(self.a["balance"], 1000.0, "reset to the allocation; the stake is still on the table")
        self.assertIn("mines", db()["games"][self.a["id"]])
        self.assertEqual(self.a["wk"]["start_c"] / 100, 1100.0, "this week starts from the cash plus the stake in play")


if __name__ == "__main__":
    unittest.main()
