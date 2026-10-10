"""The order of a weekly close with everything in play at once: leaderboard rewards, challenge rewards, loan collection, the reset
and the new allocation. Written to prove the order (ECONOMY.md, section 10) and that none of it disturbs the existing settlement."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import challenges, economy, ledger, loans, progress, weekly            # noqa: E402
from backend.store import db                                                         # noqa: E402
from backend.util import DAY_MS, prev_week_key, week_bounds, week_key               # noqa: E402
from tests.econ import books_balance, circle_of, gain, mk                           # noqa: E402
from tests.helpers import fresh_store, restore_store_path                           # noqa: E402
from tests.test_challenges import finish                                            # noqa: E402

HOUR = 3_600_000


def tearDownModule():
    restore_store_path()


class TheWholeClose(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.cur, self.prev = week_key(), prev_week_key(week_key())
        self.ann, self.ben = mk("ann", weekly=300), mk("ben")
        self.c = circle_of(self.ann, self.ben)
        for u in (self.ann, self.ben):
            u["wk"]["week"] = self.prev
            u["stats"][self.prev] = {"marketBets": 3, "gamesPlayed": 30}
        db()["meta"]["week"] = self.prev
        when = week_bounds(self.prev)[0] + 2 * DAY_MS + 12 * HOUR
        loans.borrow(self.ann, 400, now=when)                       # cash 700, owes 400
        gain(self.ann, 150)                                         # a good week: cash 850
        a = challenges.assign(self.prev)
        self.w_item = next(i for i in a["items"] if i["account"] == "weekly")
        self.a_item = next(i for i in a["items"] if i["account"] == "accumulated")
        finish(self.ann, self.w_item, self.prev)                    # both finished, neither claimed
        finish(self.ann, self.a_item, self.prev)
        self.n0 = len(db()["ledger"][self.ann["id"]])

    def rows(self):
        return db()["ledger"][self.ann["id"]][self.n0:]

    def test_the_steps_happen_in_the_published_order(self):
        weekly.tick()
        reasons = [r["r"] for r in self.rows()]
        pos = {name: reasons.index(name) for name in ("weekly.reward", "challenge.weekly", "challenge.accumulated", "loan.collect", "weekly.allocation")}
        self.assertLess(pos["weekly.reward"], pos["challenge.weekly"], "leaderboard rewards first")
        self.assertLess(pos["challenge.weekly"], pos["loan.collect"], "weekly challenge rewards are in the weekly account before it is collected from")
        self.assertLess(pos["challenge.accumulated"], pos["loan.collect"])
        self.assertLess(pos["loan.collect"], pos["weekly.allocation"], "the loan is collected before the reset")
        self.assertTrue(books_balance(self.ann))

    def test_each_reward_lands_in_the_account_it_names_and_the_loan_is_paid_from_the_weekly_account_only(self):
        accum_before = self.ann["accum"]
        weekly.tick()
        by = {}
        for r in self.rows():
            by.setdefault(r["r"], []).append((r["a"], r["c"]))
        self.assertEqual(by["challenge.weekly"][0][0], "weekly")
        self.assertEqual(by["challenge.accumulated"][0][0], "accumulated")
        self.assertEqual(by["loan.collect"], [("weekly", -40000)])
        self.assertEqual(by["weekly.reward"][0][0], "accumulated")
        self.assertGreater(self.ann["accum"], accum_before)
        loan = list(db()["loans"].values())[0]
        self.assertEqual((loan["status"], loan["owed_c"]), ("closed", 0))
        self.assertEqual(self.ann["balance"], 1000.0, "the reset leaves exactly the new allocation")

    def test_the_final_table_and_the_leaderboard_reward_are_what_they_always_were(self):
        before = {r["user"]["username"]: (r["value"], r["delta"], r["position"]) for r in weekly.standings(self.c, self.prev)}
        weekly.tick()
        recap = self.c["recaps"][self.prev]
        rows = {x["userId"]: x for x in recap["standings"]}
        self.assertEqual((rows[self.ann["id"]]["value"], rows[self.ann["id"]]["delta"], rows[self.ann["id"]]["position"]),
                         before["ann"], "a loan and rewards credited at the close change nothing about who won")
        self.assertEqual(before["ann"][1], 150.0, "the loan is not in her result, only the real 150")
        self.assertEqual(rows[self.ann["id"]]["position"], 1)
        self.assertGreater(recap["rewards"][self.ann["id"]]["amount"], 0)

    def test_closing_again_changes_nothing_at_all(self):
        weekly.tick()
        snapshot = (self.ann["balance"], self.ann["accum"], len(self.rows()), len(list(db()["loans"].values())[0]["payments"]))
        for _ in range(4):
            weekly.tick()
        challenges.settle_week(self.prev)
        loans.collect_at_close(self.prev)
        loans.collect_from_allocation(self.cur)
        self.assertEqual((self.ann["balance"], self.ann["accum"], len(self.rows()), len(list(db()["loans"].values())[0]["payments"])), snapshot)

    def test_xp_and_rank_come_through_untouched_apart_from_the_claims(self):
        xp_before = progress.xp_of(self.ann)
        weekly.tick()
        gained = progress.xp_of(self.ann) - xp_before
        self.assertGreaterEqual(gained, self.w_item["xp"] + self.a_item["xp"], "both finished challenges paid their XP when they were credited")
        self.assertEqual(self.ben["balance"], 1000.0)


if __name__ == "__main__":
    unittest.main()
