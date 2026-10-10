"""The weekly minimum: bet in a poll and play the casino, or lose the week automatically.

Rules under test (see ECONOMY.md): at least WEEKLY_MIN_POLL_BETS poll bets and WEEKLY_MIN_CASINO_BETS casino rounds in the week;
whoever has not when the week closes is "out": placed below everybody who took part, the loser of the week (instead of whoever
finished last), and paid no reward. Practice rounds do not count; a new account is exempt for its first partial week; the rule
starts with the week stored in meta["requirements_from"]."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, economy, games, ledger, markets, users, weekly   # noqa: E402
from backend.store import db                                                  # noqa: E402
from backend.util import DAY_MS, next_week_key, now_ms, prev_week_key, week_bounds, week_key   # noqa: E402
from tests.econ import books_balance, circle_of, gain, mk                    # noqa: E402
from tests.helpers import fresh_store, restore_store_path                     # noqa: E402


def tearDownModule():
    restore_store_path()


def play(u, polls=0, casino=0, week=None):
    """Gives a person this many poll bets and casino rounds, the way the real code counts them (weekly stats)."""
    s = u["stats"].setdefault(week or week_key(), {})
    s["marketBets"] = s.get("marketBets", 0) + polls
    s["gamesPlayed"] = s.get("gamesPlayed", 0) + casino


def enforce(week=None):
    """Turns the rule on (it is off in tests unless asked for): in force from the given week, or from the beginning."""
    if week is None:
        db()["meta"].pop("requirements_from", None)
    else:
        db()["meta"]["requirements_from"] = week


def rows_of(c, week=None, final=True):
    return {r["user"]["username"]: r for r in weekly.standings(c, week or week_key(), final=final)}


class Counting(unittest.TestCase):
    def setUp(self):
        fresh_store()
        enforce()
        self.u = mk("ann", active=False)

    def req(self, u=None, week=None):
        return weekly.requirements(u or self.u, week or week_key())

    def test_the_defaults_are_one_poll_and_twenty_five_casino_bets(self):
        self.assertEqual((economy.WEEKLY_MIN_POLL_BETS, economy.WEEKLY_MIN_CASINO_BETS), (1, 25))

    def test_both_have_to_be_met_and_the_edge_is_exactly_the_minimum(self):
        self.assertFalse(self.req()["met"])
        play(self.u, polls=1)
        self.assertFalse(self.req()["met"], "a poll bet alone is not enough")
        play(self.u, casino=24)
        self.assertFalse(self.req()["met"], "24 casino rounds is one short")
        self.assertTrue(self.req()["atRisk"])
        play(self.u, casino=1)
        r = self.req()
        self.assertTrue(r["met"])
        self.assertFalse(r["atRisk"])
        self.assertEqual((r["polls"], r["casino"]), ({"have": 1, "need": 1}, {"have": 25, "need": 25}))

    def test_casino_rounds_alone_do_not_make_up_for_no_poll_bet(self):
        play(self.u, casino=100)
        self.assertFalse(self.req()["met"])
        self.assertTrue(self.req()["atRisk"])

    def test_only_this_weeks_bets_count(self):
        play(self.u, polls=3, casino=60, week=prev_week_key(week_key()))
        r = self.req()
        self.assertEqual((r["polls"]["have"], r["casino"]["have"]), (0, 0))
        self.assertTrue(self.req(week=prev_week_key(week_key()))["met"])

    def test_practice_rounds_do_not_count(self):
        demo = games.account_for(self.u, True)
        for _ in range(30):
            games._record(demo, "dice", 1, 0, None)
        self.assertEqual(self.req()["casino"]["have"], 0)

    def test_a_real_poll_purchase_counts_and_selling_it_does_not_add_another(self):
        maker = mk("maker")
        c = circle_of(maker, self.u)
        m = markets.create(maker, {"circleId": c["id"], "question": "Will the minimum be counted?"})
        markets.trade(self.u, m, {"outcome": 0, "amount": 10})
        self.assertEqual(self.req()["polls"]["have"], 1)
        pos = next(iter(m["positions"][self.u["id"]].values()))
        markets.trade(self.u, m, {"outcome": 0, "action": "sell", "shares": pos["shares"] / 2})
        self.assertEqual(self.req()["polls"]["have"], 1)

    def test_an_account_made_this_week_is_exempt_for_its_first_week(self):
        newbie = mk("newbie", age_days=0, active=False)
        r = self.req(newbie)
        self.assertTrue(r["exempt"])
        self.assertFalse(r["atRisk"])
        self.assertFalse(self.req(mk("old", age_days=40, active=False))["exempt"])

    def test_the_rule_can_be_switched_off(self):
        with mock.patch.object(economy, "WEEKLY_MIN_POLL_BETS", 0), mock.patch.object(economy, "WEEKLY_MIN_CASINO_BETS", 0):
            r = self.req()
        self.assertFalse(r["enabled"])
        self.assertFalse(r["atRisk"])

    def test_the_numbers_come_from_the_settings(self):
        with mock.patch.object(economy, "WEEKLY_MIN_POLL_BETS", 3), mock.patch.object(economy, "WEEKLY_MIN_CASINO_BETS", 5):
            play(self.u, polls=2, casino=5)
            self.assertTrue(self.req()["atRisk"])
            play(self.u, polls=1)
            self.assertTrue(self.req()["met"])

    def test_it_only_applies_from_the_week_it_starts(self):
        wk = week_key()
        enforce(next_week_key(wk))
        self.assertFalse(self.req()["enforced"])
        self.assertFalse(self.req()["atRisk"], "this week is only a preview")
        self.assertTrue(self.req(week=next_week_key(wk))["enforced"])
        enforce(wk)
        self.assertTrue(self.req()["atRisk"])

    def test_the_first_tick_starts_it_with_next_week_so_there_is_a_weeks_notice(self):
        db()["meta"].pop("requirements_from", None)
        weekly.tick()
        self.assertEqual(db()["meta"]["requirements_from"], next_week_key(week_key()))
        db()["meta"]["requirements_from"] = "2031-01-06"
        weekly.tick()
        self.assertEqual(db()["meta"]["requirements_from"], "2031-01-06", "set once, never moved")

    def test_a_week_that_closes_after_the_first_tick_but_before_the_start_is_not_enforced(self):
        db()["meta"].pop("requirements_from", None)
        weekly.tick()
        c = circle_of(mk("amy", active=False), mk("bob", active=False))
        weekly.finalize_week(week_key())
        recap = c["recaps"][week_key()]
        self.assertEqual(recap["reason"], "last", "nobody is out in a week the rule had not started")
        self.assertFalse(any(r["out"] for r in recap["standings"]))
        self.assertEqual(recap["loserIds"], [], "everybody finished level, so nobody pays")


class AtTheEndOfTheWeek(unittest.TestCase):
    def setUp(self):
        fresh_store()
        enforce()
        self.u = {n: mk(n, active=False) for n in ("ann", "ben", "cat", "dan", "eve")}
        self.c = circle_of(self.u["ann"], *[self.u[n] for n in ("ben", "cat", "dan", "eve")])
        for u in self.u.values():
            play(u, polls=2, casino=30)                                     # everybody kept the minimum unless a test says otherwise
        self.week = week_key()

    def close(self):
        weekly.finalize_week(self.week)
        return self.c["recaps"][self.week]

    def test_live_the_minimum_is_only_progress_it_changes_neither_order_nor_rewards(self):
        play(self.u["ben"], casino=-30)                                     # ben is far short, but the week is still running
        gain(self.u["ben"], 500)
        rows = rows_of(self.c, final=False)
        self.assertFalse(rows["ben"]["out"])
        self.assertEqual(rows["ben"]["position"], 1)
        self.assertTrue(rows["ben"]["req"]["atRisk"])
        plan = {self.c["id"]: (self.c, list(rows.values()))}
        weekly.plan_rewards(plan)
        self.assertGreater(rows["ben"]["reward"], 0)

    def test_somebody_who_missed_it_is_out_placed_last_and_paid_nothing_even_with_the_best_week(self):
        play(self.u["ben"], casino=-30)                                     # 0 casino rounds
        gain(self.u["ben"], 900)                                            # ...but the best week by far
        gain(self.u["cat"], 100)
        recap = self.close()
        order = [r["userId"] for r in recap["standings"]]
        self.assertEqual(order[-1], self.u["ben"]["id"])
        self.assertTrue(recap["standings"][-1]["out"])
        self.assertEqual(sum(1 for r in recap["standings"] if r["out"]), 1)
        self.assertNotIn(self.u["ben"]["id"], recap["rewards"])
        self.assertEqual(recap["rewards"][self.u["cat"]["id"]]["position"], 1, "the others close ranks: cat is first among those who qualified")
        self.assertEqual(sorted(r["position"] for r in recap["rewards"].values()), [1, 2, 3, 4])

    def test_the_loser_of_the_week_is_the_one_who_skipped_not_the_one_who_finished_last_on_money(self):
        play(self.u["dan"], polls=-2)                                       # dan: no poll bet at all
        gain(self.u["eve"], -300)                                           # eve: the worst week on money, but she took part
        recap = self.close()
        self.assertEqual(recap["loserIds"], [self.u["dan"]["id"]])
        self.assertEqual(recap["reason"], "minimum")
        self.assertIn("weekly minimum", recap["note"])
        self.assertNotIn(self.u["eve"]["id"], recap["loserIds"])

    def test_several_people_can_lose_the_week_and_all_of_them_take_the_punishment(self):
        play(self.u["ann"], polls=-2)
        play(self.u["cat"], casino=-6)                                      # 24 rounds: one short
        weekly.add_punishment(self.u["ben"], self.c, "Sing at the supermarket")
        recap = self.close()
        self.assertEqual(set(recap["loserIds"]), {self.u["ann"]["id"], self.u["cat"]["id"]})
        self.assertEqual(recap["punishment"]["text"], "Sing at the supermarket")
        awards = {a["key"]: a for a in recap["awards"]}
        self.assertEqual(set(awards["hotSeat"]["userIds"]), set(recap["loserIds"]))
        self.assertEqual(awards["hotSeat"]["value"], "Missed the weekly minimum")

    def test_when_everybody_kept_the_minimum_the_worst_week_still_decides(self):
        gain(self.u["eve"], -300)
        recap = self.close()
        self.assertEqual(recap["loserIds"], [self.u["eve"]["id"]])
        self.assertEqual(recap["reason"], "last")
        self.assertFalse(any(r["out"] for r in recap["standings"]))

    def test_a_circle_where_nobody_took_part_loses_together_and_pays_no_rewards(self):
        for u in self.u.values():
            u["stats"][self.week] = {"marketBets": 1}                       # active, but no casino rounds at all
        recap = self.close()
        self.assertEqual(len(recap["loserIds"]), 5)
        self.assertEqual(recap["rewards"], {})

    def test_the_circle_still_pays_on_the_full_scale_when_one_member_is_out(self):
        play(self.u["ben"], casino=-30)
        recap = self.close()
        self.assertEqual(recap["active"], 5, "five took part, so the table is paid in full")
        self.assertEqual(recap["scale"], 1.0)
        self.assertEqual(recap["rewards"][next(iter(recap["rewards"]))]["amount"] > 0, True)

    def test_the_week_records_why_each_person_was_out(self):
        play(self.u["ben"], polls=-2, casino=-6)                            # no poll bet, and 24 casino rounds
        recap = self.close()
        ben = next(r for r in recap["standings"] if r["userId"] == self.u["ben"]["id"])
        self.assertTrue(ben["out"])
        self.assertEqual((ben["req"]["polls"], ben["req"]["casino"]), ({"have": 0, "need": 1}, {"have": 24, "need": 25}))
        self.assertEqual(recap["rules"]["requirements"]["casino"], 25)

    def test_a_settled_week_is_shown_with_who_lost_it_and_why(self):
        past = prev_week_key(self.week)                                   # the page shows a closed week from its saved recap
        for u in self.u.values():
            u["stats"][past] = {"marketBets": 2, "gamesPlayed": 30}
        self.u["ben"]["stats"][past] = {"marketBets": 0, "gamesPlayed": 24}
        weekly.finalize_week(past)
        view = weekly.view(self.c, self.u["ann"], past)
        self.assertFalse(view["isCurrent"])
        row = next(r for r in view["standings"] if r["user"]["id"] == self.u["ben"]["id"])
        self.assertTrue(row["out"])
        self.assertEqual(row["position"], 5)
        self.assertIn("weekly minimum", row["rewardNote"])
        self.assertEqual(view["recap"]["reason"], "minimum")
        self.assertEqual([u["username"] for u in view["hotSeat"]], ["ben"])
        mine = weekly.view(self.c, self.u["ben"], past)["me"]
        self.assertTrue(mine["out"])
        self.assertEqual(mine["req"]["casino"], {"have": 24, "need": 25})

    def test_closing_twice_changes_nothing_and_money_is_paid_once(self):
        play(self.u["ben"], casino=-30)
        first = self.close()
        snapshot = {k: v for k, v in first.items() if k != "awards"}
        weekly.finalize_week(self.week)
        self.assertEqual({k: v for k, v in self.c["recaps"][self.week].items() if k != "awards"}, snapshot)
        before = {uid: ledger.balance(users.get(uid), "accumulated") for uid in self.c["members"]}
        weekly.pay_rewards()
        weekly.pay_rewards()
        self.assertEqual(before, {uid: ledger.balance(users.get(uid), "accumulated") for uid in self.c["members"]})
        self.assertEqual(ledger.balance(self.u["ben"], "accumulated"), 0)
        self.assertTrue(all(books_balance(u) for u in self.u.values()))

    def test_it_follows_the_person_into_every_circle_they_are_in(self):
        other = circle_of(self.u["ben"], mk("zed"), name="Second crew")
        play(next(u for u in db()["users"].values() if u["username"] == "zed"), polls=2, casino=30)
        play(self.u["ben"], casino=-30)
        weekly.finalize_week(self.week)
        self.assertIn(self.u["ben"]["id"], self.c["recaps"][self.week]["loserIds"])
        self.assertIn(self.u["ben"]["id"], other["recaps"][self.week]["loserIds"])

    def test_a_new_member_who_joined_this_week_is_not_punished_for_their_first_week(self):
        newbie = mk("newbie", age_days=0, active=False)
        circles.join_by_code(newbie, self.c["inviteCode"])
        recap = self.close()
        self.assertNotIn(newbie["id"], recap["loserIds"])
        row = next(r for r in recap["standings"] if r["userId"] == newbie["id"])
        self.assertFalse(row["out"])

    def test_a_week_before_the_rule_started_closes_the_old_way(self):
        enforce(next_week_key(self.week))
        play(self.u["ben"], casino=-30)
        gain(self.u["ben"], -50)
        recap = self.close()
        self.assertEqual(recap["reason"], "last")
        self.assertEqual(recap["loserIds"], [self.u["ben"]["id"]])


class Reminders(unittest.TestCase):
    def setUp(self):
        fresh_store()
        enforce()
        weekly.EVENTS.clear()
        self.short = mk("short", active=False)
        self.fine = mk("fine", active=False)
        play(self.fine, polls=1, casino=25)
        self.newbie = mk("newbie", age_days=0, active=False)
        self.c = circle_of(self.short, self.fine, self.newbie)
        self.week = week_key()
        self.end = week_bounds(self.week)[1]

    def test_nothing_is_sent_until_the_last_day(self):
        self.assertEqual(weekly.remind_short(self.week, self.end - 30 * 3600_000), 0)
        self.assertEqual(weekly.EVENTS, [])

    def test_in_the_last_day_only_people_who_are_short_are_told_exactly_what_is_left(self):
        play(self.short, polls=1, casino=10)
        self.assertEqual(weekly.remind_short(self.week, self.end - 3600_000), 1)
        (ev,) = weekly.EVENTS
        self.assertEqual((ev["type"], ev["userId"]), ("weekwarn", self.short["id"]))
        self.assertIn("15 more casino bets", ev["text"])
        self.assertNotIn("poll", ev["text"])
        self.assertEqual(self.short["activity"][0]["kind"], "warn")
        self.assertFalse(any(a["kind"] == "warn" for a in self.fine["activity"]), "somebody who kept the minimum is left alone")
        self.assertFalse(any(e["userId"] == self.newbie["id"] for e in weekly.EVENTS), "a new account is exempt, so it is not warned")

    def test_it_is_sent_once_per_week(self):
        weekly.remind_short(self.week, self.end - 3600_000)
        weekly.EVENTS.clear()
        self.assertEqual(weekly.remind_short(self.week, self.end - 1800_000), 0)
        self.assertEqual(weekly.EVENTS, [])

    def test_no_reminder_when_the_rule_is_off_or_not_yet_in_force_or_reminders_are_off(self):
        enforce(next_week_key(self.week))
        self.assertEqual(weekly.remind_short(self.week, self.end - 3600_000), 0)
        enforce()
        db()["meta"].pop("reminded", None)
        with mock.patch.object(economy, "WEEKLY_REMIND_H", 0):
            self.assertEqual(weekly.remind_short(self.week, self.end - 3600_000), 0)

    def test_the_background_tick_sends_it_too(self):
        db()["meta"]["week"] = self.week
        db()["meta"]["requirements_from"] = self.week
        with mock.patch.object(weekly, "now_ms", return_value=self.end - 3600_000):
            self.assertTrue(weekly.tick())
        self.assertEqual([e["userId"] for e in weekly.EVENTS if e["type"] == "weekwarn"], [self.short["id"]])


class WhatThePageIsTold(unittest.TestCase):
    def setUp(self):
        fresh_store()
        enforce()
        self.a, self.b = mk("ann", active=False), mk("ben", active=False)
        play(self.a, polls=1, casino=7)
        self.c = circle_of(self.a, self.b)

    def test_my_progress_and_the_rule_are_in_the_weekly_view(self):
        v = weekly.view(self.c, self.a)
        self.assertEqual(v["rules"]["requirements"]["polls"], 1)
        self.assertEqual(v["rules"]["requirements"]["casino"], 25)
        self.assertTrue(v["rules"]["requirements"]["exemptFirstWeek"])
        me = v["me"]
        self.assertEqual((me["req"]["polls"]["have"], me["req"]["casino"]["have"]), (1, 7))
        self.assertTrue(me["req"]["atRisk"])
        self.assertFalse(me["out"])

    def test_the_live_standings_flag_who_is_at_risk_but_do_not_mark_anybody_out(self):
        v = weekly.view(self.c, self.a)
        self.assertTrue(all(not r["out"] for r in v["standings"]))
        self.assertTrue(all(r["req"]["atRisk"] for r in v["standings"]))

    def test_a_person_who_never_joined_a_circle_has_no_row_and_no_requirement_shown(self):
        loner = mk("loner")
        self.assertIsNone(weekly.view(self.c, loner)["me"])


if __name__ == "__main__":
    unittest.main()
