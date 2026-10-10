"""Loans: who may borrow, how much, what it does to the books and the leaderboard, repayment, and a debt that survives the weekly reset."""
import copy
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import activity, challenges, economy, games, ledger, loans, markets, progress, users, weekly, wealth   # noqa: E402
from backend.store import LOCK, db, store                                                                          # noqa: E402
from backend.util import ApiError, DAY_MS, now_ms, prev_week_key, week_bounds, week_key                          # noqa: E402
from tests.econ import books_balance, circle_of, gain, mk                                                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                                          # noqa: E402

HOUR = 3_600_000
START, END = week_bounds(week_key())
MID = START + 2 * DAY_MS + 12 * HOUR                      # Wednesday noon of this week, so no test depends on the day it is run
LATE = END - 5 * HOUR                                     # inside the "no new loans" window


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


class Base(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", weekly=300)
        self.other = mk("ben")


class Eligibility(Base):
    def test_a_normal_account_can_borrow_up_to_the_cap(self):
        lim = loans.limits(self.u, MID)
        self.assertTrue(lim["eligible"], lim["reasons"])
        self.assertEqual(lim["available_c"], 50_000, "half of the $1,000 allocation")
        self.assertEqual(loans.view(self.u, MID)["available"], 500.0)

    def test_a_loan_can_only_top_you_back_up_to_the_weekly_allocation(self):
        self.u["balance"] = 800.0
        self.assertEqual(loans.limits(self.u, MID)["available_c"], 20_000, "$800 held, so at most $200 more")
        self.u["balance"] = 1000.0
        lim = loans.limits(self.u, MID)
        self.assertFalse(lim["eligible"])
        self.assertIn("top you back up", lim["reasons"][0])

    def test_what_is_riding_on_bets_and_rounds_counts_as_held(self):
        m = markets.create(self.other, {"scope": "site", "question": "Will it hold up?"})
        markets.trade(self.u, m, {"outcome": 0, "amount": 100})
        held = markets.net_worth(self.u)
        self.assertAlmostEqual(loans.limits(self.u, MID)["available_c"] / 100, min(500, 1000 - held), places=1)

    def test_a_brand_new_account_cannot_borrow_yet(self):
        new = mk("newbie", weekly=100, age_days=0.01)
        lim = loans.limits(new, now_ms())
        self.assertFalse(lim["eligible"])
        self.assertIn("hours after you join", " ".join(lim["reasons"]))

    def test_nobody_can_borrow_in_the_last_hours_of_the_week(self):
        lim = loans.limits(self.u, LATE)
        self.assertFalse(lim["eligible"])
        self.assertIn("closes", lim["reasons"][0])
        err(loans.borrow, self.u, 100, now=LATE)
        self.assertEqual(self.u["balance"], 300.0)

    def test_only_one_loan_at_a_time(self):
        loans.borrow(self.u, 100, now=MID)
        e = err(loans.borrow, self.u, 50, now=MID)
        self.assertEqual(e.status, 403)
        self.assertIn("still owe", e.message)

    def test_at_most_two_loans_started_in_a_week(self):
        for _ in range(2):
            loans.borrow(self.u, 100, now=MID)
            loans.repay(self.u, "all", now=MID)
        lim = loans.limits(self.u, MID)
        self.assertFalse(lim["eligible"])
        self.assertIn("most allowed", " ".join(lim["reasons"]))

    def test_amounts_are_checked(self):
        for bad in (0, -5, "abc", None, 9.99, 500.01, 10.005):
            err(loans.borrow, self.u, bad, now=MID)
        self.assertEqual(self.u["balance"], 300.0)
        self.assertIsNone(loans.active(self.u))

    def test_switching_loans_off_stops_borrowing(self):
        with mock.patch.object(economy, "LOANS_ENABLED", False):
            self.assertFalse(loans.limits(self.u, MID)["eligible"])
            err(loans.borrow, self.u, 100, now=MID)

    def test_the_quote_says_exactly_what_will_happen_and_moves_nothing(self):
        q = loans.quote(self.u, 200, MID)
        self.assertEqual((q["amount"], q["fee"], q["total"], q["dueAt"]), (200.0, 0.0, 200.0, END))
        self.assertIn("interest-free", q["interest"])
        self.assertIn("weekly allocation", q["effect"])
        self.assertIn("accumulated account", q["effect"])
        self.assertEqual((self.u["balance"], loans.owed(self.u)), (300.0, 0.0))


class Disbursement(Base):
    def test_the_money_lands_in_the_weekly_account_only_and_is_written_down(self):
        accum = ledger.balance(self.u, "accumulated")
        res = loans.borrow(self.u, 250, "req-borrow-0001", now=MID)
        self.assertEqual((res["received"], res["owed"], res["balance"]), (250.0, 250.0, 550.0))
        self.assertEqual(ledger.balance(self.u, "weekly"), 550.0)
        self.assertEqual(ledger.balance(self.u, "accumulated"), accum, "the accumulated account is never touched")
        row = [r for r in ledger.entries(self.u) if r["reason"] == "loan.borrow"][0]
        self.assertEqual((row["account"], row["amount"], row["external"]), ("weekly", 250.0, False))
        self.assertEqual(row["ref"], res["loan"]["id"])
        self.assertTrue(books_balance(self.u))

    def test_borrowing_does_not_change_what_you_hold_or_how_the_week_went(self):
        c = circle_of(self.u, self.other)
        before = {r["user"]["username"]: (r["value"], r["delta"], r["position"]) for r in weekly.standings(c, week_key())}
        loans.borrow(self.u, 400, now=MID)
        after = {r["user"]["username"]: (r["value"], r["delta"], r["position"]) for r in weekly.standings(c, week_key())}
        self.assertEqual(before, after, "a loan is not income: the debt is subtracted, so the net worth does not move")
        self.assertEqual(markets.net_worth(self.u), 300.0)
        self.assertEqual(self.u["balance"], 700.0)

    def test_winning_with_borrowed_money_is_a_real_win_but_the_loan_itself_never_is(self):
        c = circle_of(self.u, self.other)
        loans.borrow(self.u, 400, now=MID)
        gain(self.u, 50)                                           # a genuine result on top
        rows = {r["user"]["username"]: r for r in weekly.standings(c, week_key())}
        self.assertEqual(rows["ann"]["delta"], 50.0)

    def test_a_fee_is_a_fixed_disclosed_cost(self):
        with mock.patch.object(economy, "LOAN_FEE", 15.0):
            q = loans.quote(self.u, 200, MID)
            self.assertEqual((q["fee"], q["total"]), (15.0, 215.0))
            self.assertIn("fixed fee of $15.00", q["interest"])
            res = loans.borrow(self.u, 200, now=MID)
            self.assertEqual(res["owed"], 215.0)
            self.assertEqual(self.u["balance"], 500.0)
            self.assertEqual(markets.net_worth(self.u), 285.0, "the fee is a real cost and shows up as one")

    def test_the_portfolio_shows_the_debt_and_still_adds_up_to_the_leaderboard_holding(self):
        loans.borrow(self.u, 300, now=MID)
        o = wealth.overview(self.u)
        parts = {p["key"]: p["amount"] for p in o["weekly"]["parts"]}
        self.assertEqual((parts["cash"], parts["debt"]), (600.0, -300.0))
        self.assertAlmostEqual(o["weekly"]["total"], markets.net_worth(self.u), places=2)

    def test_the_same_request_never_lends_twice_and_a_different_one_is_refused(self):
        a = loans.borrow(self.u, 100, "retry-request-1", now=MID)
        b = loans.borrow(self.u, 100, "retry-request-1", now=MID)
        self.assertTrue(b["duplicate"])
        self.assertEqual(b["loan"]["id"], a["loan"]["id"])
        self.assertEqual(self.u["balance"], 400.0)
        e = err(loans.borrow, self.u, 200, "retry-request-1", now=MID)
        self.assertEqual(e.status, 409)

    def test_a_failure_halfway_leaves_nothing_behind(self):
        rows_before = len(db()["ledger"].get(self.u["id"], []))
        with mock.patch.object(loans.users, "log", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                loans.borrow(self.u, 100, "retry-request-2", now=MID)
        self.assertEqual((self.u["balance"], loans.owed(self.u), self.u.get("loanId")), (300.0, 0.0, None))
        self.assertEqual(len(db()["ledger"].get(self.u["id"], [])), rows_before)
        self.assertEqual(db().get("loans", {}), {})
        self.assertTrue(books_balance(self.u))
        loans.borrow(self.u, 100, "retry-request-2", now=MID)       # and the same request can simply be tried again
        self.assertEqual(self.u["balance"], 400.0)

    def test_two_requests_at_the_same_moment_lend_once(self):
        results = []

        def go():
            with LOCK:
                try:
                    loans.borrow(self.u, 100, now=MID)
                    results.append("ok")
                except ApiError:
                    results.append("refused")
        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), ["ok"] + ["refused"] * 7)
        self.assertEqual(self.u["balance"], 400.0)


class Repayment(Base):
    def setUp(self):
        super().setUp()
        loans.borrow(self.u, 400, now=MID)

    def test_partial_then_full(self):
        r = loans.repay(self.u, 150, now=MID)
        self.assertEqual((r["paid"], r["owed"], r["closed"], r["balance"]), (150.0, 250.0, False, 550.0))
        r = loans.repay(self.u, "all", now=MID)
        self.assertEqual((r["paid"], r["owed"], r["closed"], r["balance"]), (250.0, 0.0, True, 300.0))
        self.assertIsNone(loans.active(self.u))
        self.assertEqual([p["amount"] for p in r["loan"]["payments"]], [250.0, 150.0], "the history lists every payment, newest first")
        self.assertTrue(books_balance(self.u))
        self.assertTrue(loans.limits(self.u, MID)["eligible"], "paid off, so a new loan is possible again")

    def test_only_the_weekly_account_is_ever_charged(self):
        ledger.post(self.u, "accumulated", 5000, "test.setup")
        self.u["balance"] = 20.0
        e = err(loans.repay, self.u, 100, now=MID)
        self.assertIn("weekly account", e.message)
        r = loans.repay(self.u, "all", now=MID)
        self.assertEqual(r["paid"], 20.0, "all you can pay from the weekly account")
        self.assertEqual(self.u["accum"], 5000.0, "the accumulated account is never charged")

    def test_you_cannot_repay_more_than_you_owe_or_with_nothing(self):
        err(loans.repay, self.u, 400.01, now=MID)
        err(loans.repay, self.u, 0, now=MID)
        err(loans.repay, self.u, -1, now=MID)
        err(loans.repay, self.u, 1.005, now=MID)
        self.u["balance"] = 0.0
        err(loans.repay, self.u, "all", now=MID)
        e = err(loans.repay, self.other, 10, now=MID)
        self.assertEqual(e.status, 409)

    def test_a_double_click_repays_once(self):
        a = loans.repay(self.u, 100, "repay-request-1", now=MID)
        b = loans.repay(self.u, 100, "repay-request-1", now=MID)
        self.assertTrue(b["duplicate"])
        self.assertEqual(loans.owed(self.u), 300.0)
        self.assertEqual(a["paid"], b["paid"])

    def test_repaying_is_not_a_gambling_loss_and_not_progress(self):
        before = (dict(self.u["stats"].get(week_key(), {})), progress.state(self.u)["xp"], dict(progress.state(self.u)["m"]))
        loans.repay(self.u, "all", now=MID)
        self.assertEqual(self.u["stats"].get(week_key(), {}).get("gamePnl"), before[0].get("gamePnl"))
        self.assertEqual(self.u["stats"].get(week_key(), {}).get("gameWagered"), before[0].get("gameWagered"))
        self.assertEqual((progress.state(self.u)["xp"], progress.state(self.u)["m"]), before[1:])


class NothingToFarm(Base):
    def test_borrowing_and_repaying_in_a_loop_earns_nothing(self):
        c = circle_of(self.u, self.other)                          # (making a circle is a real action; it is done before the snapshot)
        goals_before = copy.deepcopy(progress.state(self.u))
        delta_before = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}
        stats_before = copy.deepcopy(self.u["stats"].get(week_key(), {}))
        inbox_before = list(self.u.get("inbox", []))
        for _ in range(2):                                         # (two loans a week is the limit; the point is that none of it counts)
            loans.borrow(self.u, 300, now=MID)
            loans.repay(self.u, "all", now=MID)
        self.assertEqual(progress.state(self.u), goals_before, "no XP, no challenge fact, no milestone counter, nothing")
        self.assertEqual({r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}, delta_before)
        self.assertEqual(self.u["stats"].get(week_key(), {}), stats_before, "no wagered, no profit, no rounds, nothing")
        self.assertEqual(self.u.get("inbox", []), inbox_before)
        self.assertEqual(self.u["balance"], 300.0)
        self.assertTrue(books_balance(self.u))

    def test_playing_with_borrowed_money_counts_like_playing_with_any_money_and_no_more(self):
        loans.borrow(self.u, 400, now=MID)
        res = activity.record(self.u, "casino", "round-1", now=MID, amount=5.0, game="dice")
        self.assertEqual((res["counted"], res["xp"]), (True, 2), "a round is a round: the same XP whoever's chips it was")
        self.assertEqual(progress.state(self.u)["xp"], 2)


class TheWeeklyClose(unittest.TestCase):
    """The order of a close: leaderboard, challenge rewards, loan collection, reset, new allocation (and a debt that survives all of it)."""

    def setUp(self):
        fresh_store()
        self.cur, self.prev = week_key(), prev_week_key(week_key())
        self.u = mk("ann", weekly=300)
        self.other = mk("ben")
        self.c = circle_of(self.u, self.other)
        for p in (self.u, self.other):
            p["wk"]["week"] = self.prev
        db()["meta"]["week"] = self.prev
        pstart, _ = week_bounds(self.prev)
        self.when = pstart + 2 * DAY_MS + 12 * HOUR                # the middle of last week
        loans.borrow(self.u, 400, now=self.when)                   # cash is now 700, owed 400 (dated last week)

    def close(self):
        return weekly.tick()

    def test_the_funds_you_have_pay_the_debt_before_the_reset(self):
        self.close()
        loan = list(db()["loans"].values())[0]
        self.assertEqual(loan["status"], "closed")
        self.assertEqual(loan["owed_c"], 0)
        self.assertIsNone(self.u.get("loanId"))
        self.assertEqual(self.u["balance"], 1000.0, "then the account is reset to the allocation as usual")
        rows = {r["reason"]: r for r in ledger.entries(self.u)}
        self.assertEqual(rows["loan.collect"]["amount"], -400.0)
        self.assertTrue(books_balance(self.u))

    def test_a_debt_that_funds_cannot_cover_stays_owed_through_the_reset(self):
        self.u["balance"] = 120.0                                  # lost most of it
        with mock.patch.object(economy, "LOAN_ALLOC_REPAY_PCT", 10.0):
            self.close()
        loan = list(db()["loans"].values())[0]
        self.assertEqual((loan["status"], loan["overdue"]), ("active", True))
        self.assertEqual([p["kind"] for p in loan["payments"]], ["collect", "allocation"])
        self.assertEqual(loan["owed_c"], 18_000, "400, minus the 120 collected before the reset, minus 100 from the new allocation")
        self.assertEqual(self.u["balance"], 900.0)

    def test_the_default_allocation_share_clears_a_normal_loan_in_one_week(self):
        self.u["balance"] = 0.0
        self.close()
        loan = list(db()["loans"].values())[0]
        self.assertEqual((loan["status"], loan["owed_c"]), ("closed", 0))
        self.assertEqual(self.u["balance"], 600.0, "50% of the new allocation ($500) went to the debt, $400 of it needed, so $600 is spendable")

    def test_a_big_debt_takes_its_share_of_each_new_allocation(self):
        self.u["balance"] = 0.0
        with mock.patch.object(economy, "LOAN_ALLOC_REPAY_PCT", 10.0):
            self.close()
            loan = list(db()["loans"].values())[0]
            self.assertEqual(loan["status"], "active")
            self.assertEqual(loan["owed_c"], 30_000, "$400 owed, 10% of $1,000 taken from the new allocation")
            self.assertEqual(self.u["balance"], 900.0)
            self.assertEqual(loans.owed(self.u), 300.0)
            # still owed: no new loan, whatever the week or the balance
            lim = loans.limits(self.u, now_ms())
            self.assertFalse(lim["eligible"])
            self.assertIn("still owe", lim["reasons"][0])

    def test_waiting_retrying_or_a_new_week_never_forgives_it(self):
        self.u["balance"] = 0.0
        with mock.patch.object(economy, "LOAN_ALLOC_REPAY_PCT", 10.0):
            self.close()
            owed = loans.owed(self.u)
            self.assertGreater(owed, 0)
            for _ in range(5):                                     # the tick running again and again
                weekly.tick()
            self.assertEqual(loans.owed(self.u), owed)
            store.save()
            store.load()                                           # a restart
            self.assertEqual(loans.owed(users.get(self.u["id"])), owed)

    def test_closing_twice_collects_once(self):
        weekly.finalize_week(self.prev)
        loans.collect_at_close(self.prev)
        n = len([r for r in ledger.entries(self.u) if r["reason"] == "loan.collect"])
        loans.collect_at_close(self.prev)
        loans.collect_at_close(self.prev)
        self.assertEqual(len([r for r in ledger.entries(self.u) if r["reason"] == "loan.collect"]), n)

    def test_the_debt_is_subtracted_in_the_final_table_of_the_week(self):
        before = {r["user"]["username"]: r["value"] for r in weekly.standings(self.c, self.prev)}
        weekly.finalize_week(self.prev)
        snap = db()["snapshots"][self.prev]
        self.assertEqual(snap[self.u["id"]], before["ann"])
        self.assertEqual(snap[self.u["id"]], 300.0, "700 cash minus 400 owed")

    def test_a_weekly_challenge_reward_credited_at_the_close_pays_the_loan_first(self):
        self.u["balance"] = 0.0
        a = challenges.assign(self.prev)
        item = next(i for i in a["items"] if i["account"] == "weekly")
        w = challenges.week_state(self.u, self.prev)
        w["facts"][item["fact"]] = ["x"] * 7 if item["fact"] != "created" else 5      # finished, never claimed
        w["facts"]["days"] = [f"d{i}" for i in range(7)]
        self.close()
        loan = list(db()["loans"].values())[0]
        credited = sum(r["amount"] for r in ledger.entries(self.u) if r["reason"] == "challenge.weekly")
        self.assertGreater(credited, 0)
        collect = [p for p in loan["payments"] if p["kind"] == "collect"]
        self.assertEqual(collect[0]["c"], round(credited * 100), "what the challenges paid into the weekly account at the close was collected first")

    def test_the_weekly_reset_does_not_mint_or_lose_anything_else(self):
        accum = ledger.balance(self.u, "accumulated")
        self.close()
        self.assertEqual(ledger.balance(self.u, "accumulated"), accum)
        self.assertTrue(books_balance(self.u))
        self.assertTrue(books_balance(self.other))


if __name__ == "__main__":
    unittest.main()
