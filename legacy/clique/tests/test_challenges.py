"""Weekly challenges: made once and frozen, progress from what the server saw, claims paid once into the right account, closing the week."""
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import activity, challenges, economy, ledger, loans, markets, progress, rules, users, weekly   # noqa: E402
from backend.store import LOCK, db, store                                                                   # noqa: E402
from backend.util import ApiError, DAY_MS, next_week_key, prev_week_key, week_bounds, week_key             # noqa: E402
from tests.econ import books_balance, circle_of, mk                                                         # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                                   # noqa: E402

HOUR = 3_600_000
WEEK = week_key()
START, END = week_bounds(WEEK)
DAYS = [START + i * DAY_MS + 12 * HOUR for i in range(7)]
T0 = DAYS[2]
GAMES = ["dice", "limbo", "coinflip", "war", "mines", "wheel"]


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def finish(user, item, week=WEEK, now=None):
    """Does what it takes, through the real recorder, to finish one challenge."""
    now = now or (week_bounds(week)[0] + 2 * DAY_MS + 12 * HOUR)
    fam = item["family"]
    n = item["target"]
    if fam in ("play", "wins", "mult", "earn"):                           # the goals about one game: real rounds, shaped to hit the target
        game = item["game"]
        if fam == "play":
            for i in range(n):
                activity.record(user, "casino", f"f-{fam}-{i}", now=now, amount=5, game=game, payout=0.0, mult=None)
        elif fam == "wins":
            for i in range(n):
                activity.record(user, "casino", f"f-{fam}-{i}", now=now, amount=5, game=game, payout=8.0, mult=1.6)
        elif fam == "mult":
            activity.record(user, "casino", f"f-{fam}", now=now, amount=5, game=game, payout=5.0 * n, mult=float(n))
        else:
            for i in range(-(-n // 25)):                                  # each winning round is worth at most $25
                activity.record(user, "casino", f"f-{fam}-{i}", now=now, amount=5, game=game, payout=100.0, mult=20.0)
        return
    for i in range(n):
        day = week_bounds(week)[0] + (i % 7) * DAY_MS + 12 * HOUR
        if fam in ("games",):
            activity.record(user, "casino", f"f-{fam}-{i}", now=now, amount=5, game=GAMES[i])
        elif fam == "polls":
            activity.record(user, "polls", f"f-{fam}-{i}", now=now, amount=5, market=f"mk{i}", category="Sports")
        elif fam in ("days", "streak"):
            activity.record(user, "casino", f"f-{fam}-{i}", now=day, amount=5, game="dice")
        elif fam == "maker":
            activity.record(user, "create", f"f-{fam}-{i}", now=now)
        elif fam == "stocks":
            activity.record(user, "exchange", f"f-{fam}-{i}", now=now, amount=50, symbol=["NEXO", "ATLS", "ZEPH"][i])
        elif fam == "features":
            kind = ["polls", "casino", "exchange", "poker", "create", "circle"][i]
            kw = {"polls": {"amount": 5, "market": "mkx"}, "casino": {"amount": 5, "game": "dice"}, "exchange": {"amount": 50, "symbol": "NEXO"}}.get(kind, {})
            activity.record(user, kind, f"f-{fam}-{i}", now=now, **kw)
        elif fam == "cats":
            activity.record(user, "polls", f"f-{fam}-{i}", now=now, amount=5, market=f"mk{i}", category=["Sports", "Music", "Money"][i])


class Assignment(unittest.TestCase):
    def setUp(self):
        fresh_store()

    def test_four_for_each_account_two_general_and_two_about_a_particular_game(self):
        a = challenges.assign(WEEK)
        for acct in ("weekly", "accumulated"):
            items = [i for i in a["items"] if i["account"] == acct]
            self.assertEqual(len(items), 4)
            self.assertEqual(len({i["family"] for i in items}), 4, "no family twice in a week")
            general = [i for i in items if not i.get("game")]
            gamey = [i for i in items if i.get("game")]
            self.assertEqual((len(general), len(gamey)), (2, 2))
            for i in general:
                self.assertIn(i["family"], rules.POOLS[acct])
            self.assertEqual(sorted(i["family"] for i in gamey), sorted(rules.GAME_POOLS[acct]))
        self.assertEqual(len({i["id"] for i in a["items"]}), 8)
        games_used = [i["game"] for i in a["items"] if i.get("game")]
        self.assertEqual(len(set(games_used)), 4, "four different games, not the same one four times")

    def test_every_challenge_carries_what_the_page_needs(self):
        for i in challenges.assign(WEEK)["items"]:
            for k in ("id", "title", "desc", "rule", "unit", "kind", "target", "reward_c", "xp", "account", "href", "start", "end"):
                self.assertIn(k, i)
            self.assertTrue(i["id"].startswith(WEEK + ":"), "a stable id made of the week and the family")
            self.assertGreater(i["target"], 0)
            self.assertGreater(i["reward_c"], 0)
            self.assertEqual((i["start"], i["end"]), (START, END))
            self.assertTrue(i["rule"] and "{" not in i["rule"], "the qualifying rule is written out in full")

    def test_it_is_made_once_and_never_changes_even_if_the_settings_do(self):
        first = challenges.assign(WEEK)
        snapshot = [dict(i) for i in first["items"]]
        with mock.patch.object(economy, "REWARD_SCALE", 3.0):
            again = challenges.assign(WEEK)
        self.assertIs(again, first)
        self.assertEqual([dict(i) for i in again["items"]], snapshot, "targets and rewards are fixed for the week")
        store.save()
        store.load()
        self.assertEqual(db()["challenges"][WEEK]["items"], snapshot, "and they survive a restart")

    def test_the_choice_is_the_same_everywhere_and_changes_from_week_to_week(self):
        self.assertEqual(challenges.assign(WEEK)["items"], challenges.assign(WEEK)["items"])
        seen = set()
        w = WEEK
        for _ in range(8):
            seen.add(tuple(i["family"] for i in challenges.assign(w)["items"]))
            w = next_week_key(w)
        self.assertGreater(len(seen), 1, "the mix rotates")

    def test_rewards_follow_the_reward_scale_at_assignment(self):
        with mock.patch.object(economy, "REWARD_SCALE", 2.0):
            doubled = challenges.assign(next_week_key(WEEK))
        plain = challenges.assign(next_week_key(next_week_key(WEEK)))
        def possible(i, scale):
            if i.get("game"):
                money = [m for _, m in rules.weekly_targets(i["game"], i["metric"])]
                return [round(m * rules.ACCOUNT_FACTOR[i["account"]] * 100 * scale) for m in money]
            return [t[1] * 100 * scale for t in rules.FAMILIES[i["family"]]["tiers"]]
        for i in doubled["items"]:
            self.assertIn(i["reward_c"], possible(i, 2), i["id"])
        for i in plain["items"]:
            self.assertIn(i["reward_c"], possible(i, 1), i["id"])

    def test_the_page_gets_the_two_accounts_split_clearly(self):
        v = challenges.view(mk("ann"), T0)
        self.assertEqual((len(v["weekly"]), len(v["accumulated"])), (4, 4))
        self.assertTrue(all(c["account"] == "weekly" for c in v["weekly"]))
        self.assertTrue(all(c["account"] == "accumulated" for c in v["accumulated"]))


class Progress(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", accum=100)
        self.a = challenges.assign(WEEK)

    def item(self, family):
        return next(i for i in self.a["items"] if i["family"] == family)

    def families(self, account):
        return [i for i in self.a["items"] if i["account"] == account]

    def test_it_starts_available_and_moves_to_in_progress(self):
        v = challenges.view(self.u, T0)
        self.assertTrue(all(c["status"] == "available" and c["progress"] == 0 for c in v["weekly"] + v["accumulated"]))
        activity.record(self.u, "casino", "r1", now=T0, amount=5, game="dice")
        v = challenges.view(self.u, T0)
        games = [c for c in v["weekly"] + v["accumulated"] if c["family"] == "games"]
        for c in games:
            self.assertEqual((c["status"], c["progress"]), ("in_progress", 1))

    def test_distinct_games_count_once_each(self):
        for k in range(4):
            activity.record(self.u, "casino", f"d{k}", now=T0, amount=5, game="dice")
        w = challenges.week_state(self.u, WEEK)
        self.assertEqual(w["facts"]["games"], ["dice"], "ten rounds of one game are still one game")
        activity.record(self.u, "casino", "l1", now=T0, amount=5, game="limbo")
        self.assertEqual(w["facts"]["games"], ["dice", "limbo"])

    def test_a_challenge_finished_is_completed_and_the_person_is_told(self):
        for fam in ("games", "polls", "days", "maker"):
            for it in [i for i in self.a["items"] if i["family"] == fam]:
                finish(self.u, it)
                row = [c for c in challenges.view(self.u, T0)["weekly"] if c["id"] == it["id"]][0]
                self.assertEqual(row["status"], "completed", fam)
                self.assertEqual(row["progress"], it["target"])
                self.assertTrue(any(n["kind"] == "challenge" and "complete" in n["title"].lower() for n in self.u["inbox"]), fam)

    def test_progress_comes_in_while_no_page_is_open_and_never_from_the_browser(self):
        it = self.families("weekly")[0]
        finish(self.u, it)
        self.assertGreaterEqual(challenges._value(it, challenges.week_state(self.u, WEEK)["facts"]), it["target"])
        # there is nothing in the API that sets progress: only claim, which checks it
        e = err(challenges.claim, mk("bob"), it["id"], T0)
        self.assertIn("not finished", e.message)

    def test_loans_transfers_and_purchases_are_not_progress(self):
        before = dict(challenges.week_state(self.u, WEEK)["facts"])
        self.u["balance"] = 500.0
        loans.borrow(self.u, 100, now=T0)
        loans.repay(self.u, "all", now=T0)
        ledger.post(self.u, "accumulated", -10, "store.buy")
        self.assertEqual(challenges.week_state(self.u, WEEK)["facts"], before)

    def test_practice_play_and_small_stakes_count_for_nothing(self):
        activity.record(self.u, "casino", "tiny", now=T0, amount=0.5, game="dice")
        from backend import games
        games.dice(games.demo_account(self.u), {"amount": 10, "direction": "over", "target": 50})
        self.assertEqual(challenges.week_state(self.u, WEEK)["facts"]["games"], [])

    def test_the_week_is_decided_by_the_moment_the_action_happened(self):
        last_ms = END - 1                                          # the very last millisecond of the week
        first_ms = END                                             # the first of the next
        activity.record(self.u, "casino", "late", now=last_ms, amount=5, game="dice")
        activity.record(self.u, "casino", "early", now=first_ms, amount=5, game="limbo")
        self.assertEqual(challenges.week_state(self.u, WEEK)["facts"]["games"], ["dice"])
        self.assertEqual(challenges.week_state(self.u, next_week_key(WEEK))["facts"]["games"], ["limbo"])

    def test_days_need_different_days(self):
        for i in range(5):
            activity.record(self.u, "casino", f"x{i}", now=DAYS[0] + i * 60_000, amount=5, game="dice")
        self.assertEqual(len(challenges.week_state(self.u, WEEK)["facts"]["days"]), 1, "five rounds on one day are one day")
        for d in range(1, 4):
            activity.record(self.u, "polls", f"y{d}", now=DAYS[d], amount=5, market=f"m{d}", category="Money")
        self.assertEqual(len(challenges.week_state(self.u, WEEK)["facts"]["days"]), 4)

    def test_the_day_boundary_follows_the_site_time_zone(self):
        from backend.util import day_key
        activity.record(self.u, "casino", "n1", now=DAYS[1] + 11 * HOUR + 59 * 60_000, amount=5, game="dice")       # 23:59 local
        activity.record(self.u, "casino", "n2", now=DAYS[1] + 12 * HOUR + 1 * 60_000, amount=5, game="limbo")      # 00:01 next day
        self.assertEqual(len(challenges.week_state(self.u, WEEK)["facts"]["days"]), 2)
        self.assertNotEqual(day_key(DAYS[1] + 11 * HOUR + 59 * 60_000), day_key(DAYS[1] + 12 * HOUR + 60_000))


class Claiming(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", weekly=500, accum=100)
        self.a = challenges.assign(WEEK)
        self.w_item = next(i for i in self.a["items"] if i["account"] == "weekly")
        self.a_item = next(i for i in self.a["items"] if i["account"] == "accumulated")

    def test_a_weekly_reward_goes_to_the_weekly_account_and_an_accumulated_one_to_the_accumulated_account(self):
        finish(self.u, self.w_item)
        finish(self.u, self.a_item)
        weekly_before, accum_before = self.u["balance"], self.u["accum"]
        r = challenges.claim(self.u, self.w_item["id"], T0)
        self.assertEqual((r["account"], r["amount"]), ("weekly", self.w_item["reward_c"] / 100))
        self.assertEqual((self.u["balance"], self.u["accum"]), (weekly_before + r["amount"], accum_before))
        r2 = challenges.claim(self.u, self.a_item["id"], T0)
        self.assertEqual(r2["account"], "accumulated")
        self.assertEqual((self.u["balance"], self.u["accum"]), (weekly_before + r["amount"], accum_before + r2["amount"]))
        reasons = {row["reason"]: (row["account"], row["external"]) for row in ledger.entries(self.u) if row["reason"].startswith("challenge.")}
        self.assertEqual(reasons, {"challenge.weekly": ("weekly", True), "challenge.accumulated": ("accumulated", True)})
        self.assertTrue(books_balance(self.u))

    def test_a_reward_is_an_outside_credit_not_a_win_it_never_moves_the_leaderboard(self):
        other = mk("ben")
        c = circle_of(self.u, other)
        before = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, WEEK)}
        finish(self.u, self.w_item)
        challenges.claim(self.u, self.w_item["id"], T0)
        after = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, WEEK)}
        self.assertEqual(before, after)
        self.assertGreater(self.u["balance"], 500.0)

    def test_claiming_gives_the_xp_once(self):
        finish(self.u, self.w_item)
        xp = progress.xp_of(self.u)
        r = challenges.claim(self.u, self.w_item["id"], T0)
        self.assertEqual(r["xp"], self.w_item["xp"])
        self.assertEqual(progress.xp_of(self.u), xp + self.w_item["xp"])

    def test_the_same_reward_cannot_be_claimed_twice(self):
        finish(self.u, self.w_item)
        challenges.claim(self.u, self.w_item["id"], T0)
        e = err(challenges.claim, self.u, self.w_item["id"], T0)
        self.assertEqual(e.status, 409)
        self.assertEqual(len([r for r in ledger.entries(self.u) if r["reason"] == "challenge.weekly"]), 1)

    def test_eight_claims_at_once_pay_once(self):
        finish(self.u, self.a_item)
        results = []

        def go():
            with LOCK:
                try:
                    challenges.claim(self.u, self.a_item["id"], T0)
                    results.append("paid")
                except ApiError as e:
                    results.append(e.status)
        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((results.count("paid"), results.count(409)), (1, 7))
        self.assertEqual(self.u["accum"], 100.0 + self.a_item["reward_c"] / 100)

    def test_you_cannot_claim_what_is_not_finished_or_does_not_exist_or_is_somebody_elses(self):
        e = err(challenges.claim, self.u, self.w_item["id"], T0)
        self.assertIn("not finished", e.message)
        self.assertEqual(err(challenges.claim, self.u, "nonsense", T0).status, 404)
        self.assertEqual(err(challenges.claim, self.u, f"{WEEK}:nothing", T0).status, 404)
        self.assertEqual(err(challenges.claim, self.u, None, T0).status, 404)
        other = mk("ben")
        finish(self.u, self.w_item)
        e = err(challenges.claim, other, self.w_item["id"], T0)
        self.assertIn("not finished", e.message, "finishing is per person: ben has done nothing")
        self.assertEqual(other["balance"], 1000.0)

    def test_a_failed_claim_pays_nothing_and_can_be_retried(self):
        finish(self.u, self.a_item)
        with mock.patch.object(challenges.progress, "grant", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                challenges.claim(self.u, self.a_item["id"], T0)
        self.assertEqual(self.u["accum"], 100.0)
        self.assertNotIn(self.a_item["id"], challenges.week_state(self.u, WEEK)["claimed"])
        self.assertTrue(books_balance(self.u))
        challenges.claim(self.u, self.a_item["id"], T0)
        self.assertEqual(self.u["accum"], 100.0 + self.a_item["reward_c"] / 100)

    def test_a_week_that_is_over_cannot_be_claimed_by_hand(self):
        finish(self.u, self.w_item)
        e = err(challenges.claim, self.u, self.w_item["id"], END)
        self.assertEqual(e.status, 409)
        self.assertIn("credited automatically", e.message)


class ClosingTheWeek(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.prev, self.cur = prev_week_key(WEEK), WEEK
        self.u = mk("ann", weekly=800, accum=100)
        self.other = mk("ben")
        self.c = circle_of(self.u, self.other)
        for p in (self.u, self.other):
            p["wk"]["week"] = self.prev
        db()["meta"]["week"] = self.prev
        self.a = challenges.assign(self.prev)
        self.w_item = next(i for i in self.a["items"] if i["account"] == "weekly")
        self.a_item = next(i for i in self.a["items"] if i["account"] == "accumulated")

    def test_finished_but_unclaimed_challenges_are_credited_once_at_the_close(self):
        finish(self.u, self.a_item, self.prev)
        weekly.tick()
        self.assertEqual(self.u["accum"], 100.0 + self.a_item["reward_c"] / 100)
        row = [r for r in ledger.entries(self.u) if r["reason"] == "challenge.accumulated"]
        self.assertEqual(len(row), 1)
        self.assertIn("weekly close", row[0]["note"])
        claim = challenges.week_state(self.u, self.prev)["claimed"][self.a_item["id"]]
        self.assertTrue(claim["auto"])
        for _ in range(4):
            weekly.tick()
        challenges.settle_week(self.prev)
        self.assertEqual(self.u["accum"], 100.0 + self.a_item["reward_c"] / 100, "paid once however often the close runs")
        self.assertTrue(any("weekly close" in n["title"] for n in self.u["inbox"]))
        self.assertTrue(books_balance(self.u))

    def test_unfinished_challenges_simply_expire_and_the_history_says_so(self):
        activity.record(self.u, "casino", "one", now=week_bounds(self.prev)[0] + DAY_MS, amount=5, game="dice")   # some progress, not enough
        weekly.tick()
        v = challenges.view(self.u, T0)
        past = [h for h in v["history"] if h["week"] == self.prev][0]
        self.assertTrue(all(c["status"] in ("expired", "claimed", "completed") for c in past["items"]))
        self.assertTrue(any(c["status"] == "expired" for c in past["items"]))
        self.assertTrue(past["settled"])
        self.assertEqual(self.u["accum"], 100.0)

    def test_a_weekly_account_reward_is_credited_before_the_reset_and_never_lands_in_the_new_weeks_allocation(self):
        finish(self.u, self.w_item, self.prev)
        weekly.tick()
        self.assertEqual(self.u["balance"], 1000.0, "the reset leaves exactly the allocation: last week's chips are not carried over")
        rows = [(r["reason"], r["amount"]) for r in reversed(ledger.entries(self.u))]          # oldest first
        credit = [a for r, a in rows if r == "challenge.weekly"]
        self.assertEqual(credit, [self.w_item["reward_c"] / 100])
        reasons = [r for r, _ in rows]
        self.assertLess(reasons.index("challenge.weekly"), reasons.index("weekly.allocation"), "credited before the reset, so it could have paid a loan")
        self.assertTrue(books_balance(self.u))

    def test_the_reward_does_not_inflate_last_weeks_final_table_or_the_next_weeks_start(self):
        finish(self.u, self.w_item, self.prev)
        before = {r["user"]["username"]: r["delta"] for r in weekly.standings(self.c, self.prev)}
        weekly.tick()
        recap = self.c["recaps"][self.prev]
        rows = {x["userId"]: x for x in recap["standings"]}
        self.assertEqual(rows[self.u["id"]]["delta"], before["ann"], "the final table was written before any challenge reward")
        self.assertAlmostEqual(self.u["wk"]["start_c"] / 100, markets.net_worth(self.u), places=2)
        self.assertEqual(weekly.standings(self.c, self.cur)[0]["delta"], 0.0)

    def test_the_new_weeks_challenges_are_made_at_the_rollover_exactly_once(self):
        weekly.tick()
        self.assertIn(self.cur, db()["challenges"])
        snap = db()["challenges"][self.cur]["items"]
        weekly.tick()
        weekly.tick()
        self.assertEqual(db()["challenges"][self.cur]["items"], snap)

    def test_everyone_with_a_finished_challenge_is_paid_and_nobody_else(self):
        finish(self.u, self.a_item, self.prev)
        weekly.tick()
        self.assertEqual(self.other["accum"], 0.0)
        self.assertEqual([r for r in ledger.entries(self.other) if r["reason"].startswith("challenge.")], [])

    def test_one_failure_does_not_block_everybody_elses_reward_and_is_retried(self):
        third = mk("cyrus", accum=0)
        finish(self.u, self.a_item, self.prev)
        finish(third, self.a_item, self.prev)
        real = ledger.post
        calls = {"n": 0}

        def flaky(user, account, *a, **kw):
            if user["id"] == self.u["id"] and kw.get("txid", "").startswith("chal:") and calls["n"] == 0:
                calls["n"] += 1
                raise RuntimeError("one failure")
            return real(user, account, *a, **kw)
        with mock.patch.object(ledger, "post", flaky):
            challenges.settle_week(self.prev)
        self.assertEqual(third["accum"], self.a_item["reward_c"] / 100, "cyrus was paid")
        self.assertEqual(self.u["accum"], 100.0, "ann's failed attempt left nothing behind")
        self.assertFalse(db()["challenges"][self.prev]["settled"], "so the week is not marked done")
        self.assertGreater(challenges.settle_pending(self.cur), 0, "and the next pass pays her")
        self.assertEqual(self.u["accum"], 100.0 + self.a_item["reward_c"] / 100)
        self.assertTrue(db()["challenges"][self.prev]["settled"])
        self.assertEqual(challenges.settle_pending(self.cur), 0, "and then it is done")


class ExistingPlayersAndTheWeekUnderWay(unittest.TestCase):
    def test_what_the_old_records_show_counts_for_the_week_in_progress_and_nothing_is_invented(self):
        fresh_store()
        u = mk("old")
        now = DAYS[1]
        u["history"] = [{"id": "h1", "t": now, "game": "dice", "bet": 5.0, "payout": 0, "profit": -5.0},
                        {"id": "h2", "t": now + 1000, "game": "limbo", "bet": 0.5, "payout": 0, "profit": -0.5},          # too small to count
                        {"id": "h3", "t": START - 5 * DAY_MS, "game": "war", "bet": 5.0, "payout": 0, "profit": -5.0}]      # last week
        m = markets.create(mk("maker"), {"scope": "site", "question": "Is this an old poll?"})
        m["trades"].append({"t": DAYS[0], "u": u["id"], "k": "buy", "token": "y0", "amount": 10.0, "shares": 5, "price": 0.5})
        challenges.backfill_week(u, db(), WEEK)
        f = challenges.week_state(u, WEEK)["facts"]
        self.assertEqual(f["games"], ["dice"])
        self.assertEqual(f["polls"], [m["id"]])
        self.assertEqual(len(f["days"]), 2)
        self.assertEqual(f["symbols"], [])


if __name__ == "__main__":
    unittest.main()
