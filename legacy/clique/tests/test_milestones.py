"""Milestones: lifetime goals paid into the accumulated account, claimed once, never reset, with honest backfill."""
import copy
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import activity, challenges, circles, economy, exchange, games, ledger, loans, markets, migrations, milestones, poker, progress, rules, users, weekly   # noqa: E402
from backend.store import LOCK, db, store                                                                                                                  # noqa: E402
from backend.util import ApiError, DAY_MS, next_week_key, now_ms, prev_week_key, week_bounds, week_key                                                      # noqa: E402
from tests.econ import books_balance, circle_of, mk                                                                                                        # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                                                                                   # noqa: E402
from tests.test_challenges import finish                                                                                                                    # noqa: E402
from tests.test_exchange import T0 as EX_T0, new_engine                                                                                                     # noqa: E402

HOUR = 3_600_000
WEEK = week_key()
START, END = week_bounds(WEEK)
DAYS = [START + i * DAY_MS + 12 * HOUR for i in range(7)]
T0 = DAYS[2]
CASINO = list(rules.CASINO_GAMES)


def tearDownModule():
    restore_store_path()
    exchange.engine = None


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def rounds(user, n, tag="r", start=T0, game_cycle=("dice",)):
    for i in range(n):
        activity.record(user, "casino", f"{tag}{i}", now=start + (i // 30) * DAY_MS, amount=5, game=game_cycle[i % len(game_cycle)])


class TheCatalogue(unittest.TestCase):
    def test_there_are_at_least_ten_with_a_mix_of_first_steps_and_long_goals(self):
        ms = rules.MILESTONES
        self.assertGreaterEqual(len(ms), 10)
        self.assertEqual(len({m["id"] for m in ms}), len(ms))
        firsts = [m for m in ms if m["tiers"][0][0] <= 1]
        longs = [m for m in ms if m["tiers"][-1][0] >= 25 or m["metric"] == "rank_tier"]
        self.assertGreaterEqual(len(firsts), 5, "introductory goals")
        self.assertGreaterEqual(len(longs), 5, "long-term goals")

    def test_tiers_have_stable_ids_and_rise(self):
        tiers = rules.milestone_tiers()
        self.assertEqual(len({t["id"] for t in tiers}), len(tiers))
        self.assertEqual(rules.milestone_tiers()[0]["id"], "predictor:1")
        for m in rules.MILESTONES:
            targets = [t[0] for t in m["tiers"]]
            self.assertEqual(targets, sorted(set(targets)), m["id"])
            money = [t[1] for t in m["tiers"]]
            self.assertEqual(money, sorted(money), "a bigger goal pays more")

    def test_nothing_rewards_losses_borrowing_or_bigger_stakes(self):
        text = " ".join(m["desc"].lower() + m["metric"] for m in rules.MILESTONES)
        for word in ("loan", "borrow", "repay", "transfer", "lose", "loss", "stake", "wager", "balance"):
            self.assertNotIn(word, text)

    def test_rank_milestones_pay_money_only_so_ranks_cannot_feed_themselves(self):
        climber = next(m for m in rules.MILESTONES if m["metric"] == "rank_tier")
        self.assertTrue(all(xp == 0 for _, _, xp in climber["tiers"]))

    def test_the_scale_setting_changes_the_money(self):
        base = rules.milestone_tiers()[0]["money_c"]
        with mock.patch.object(economy, "REWARD_SCALE", 3.0):
            self.assertEqual(rules.milestone_tiers()[0]["money_c"], base * 3)


class Progress(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", accum=10)

    def test_the_first_qualifying_activity_reaches_the_first_tier_and_tells_the_person(self):
        self.assertEqual(milestones.metric(self.u, "casino_rounds"), 0)
        rounds(self.u, 1)
        self.assertEqual(milestones.metric(self.u, "casino_rounds"), 1)
        self.assertIn("house_guest:1", progress.state(self.u)["done"])
        self.assertTrue(any(n["kind"] == "milestone" for n in self.u["inbox"]))

    def test_tiers_are_reached_at_their_targets(self):
        rounds(self.u, 24, game_cycle=("dice", "limbo"))
        self.assertNotIn("house_guest:2", progress.state(self.u)["done"])
        rounds(self.u, 1, tag="x")
        self.assertIn("house_guest:2", progress.state(self.u)["done"])

    def test_the_view_shows_progress_the_next_tier_and_what_can_be_claimed(self):
        rounds(self.u, 3)
        v = milestones.view(self.u)
        m = next(x for x in v["milestones"] if x["id"] == "house_guest")
        self.assertEqual((m["value"], m["next"]["tier"], m["next"]["target"]), (3, 2, 25))
        self.assertEqual([t["status"] for t in m["tiers"]], ["reached", "upcoming", "upcoming", "upcoming"])
        self.assertEqual(m["claimable"], 1)
        self.assertGreaterEqual(v["totals"]["claimable"], 2, "taking part this week reached another first tier as well")
        self.assertEqual(v["account"], "accumulated")

    def test_distinct_games_and_parts_of_clique(self):
        for i, g in enumerate(CASINO[:7]):
            activity.record(self.u, "casino", f"g{i}", now=T0, amount=5, game=g)
        self.assertEqual(milestones.metric(self.u, "games_tried"), 7)
        self.assertIn("sampler:2", progress.state(self.u)["done"])
        self.assertEqual(milestones.metric(self.u, "features_used"), 1)
        activity.record(self.u, "polls", "p1", now=T0, amount=5, market="m1")
        activity.record(self.u, "poker", "k1", now=T0)
        self.assertEqual(milestones.metric(self.u, "features_used"), 3)
        self.assertIn("explorer:1", progress.state(self.u)["done"])

    def test_weeks_and_days_taken_part_in_are_counted_across_time(self):
        w0 = START - 7 * DAY_MS
        for k, now in enumerate([w0 + DAY_MS, w0 + 2 * DAY_MS, START + DAY_MS, START + 3 * DAY_MS]):
            activity.record(self.u, "casino", f"t{k}", now=now, amount=5, game="dice")
        self.assertEqual(milestones.metric(self.u, "weeks_active"), 2)
        self.assertEqual(milestones.metric(self.u, "days_active"), 4)
        activity.record(self.u, "casino", "same-day", now=START + 3 * DAY_MS + 1000, amount=5, game="limbo")
        self.assertEqual(milestones.metric(self.u, "days_active"), 4, "a second round the same day is not another day")

    def test_the_daily_caps_stop_the_counters_too(self):
        for i in range(45):                                        # forty-five rounds on one day...
            activity.record(self.u, "casino", f"same-day-{i}", now=T0, amount=5, game="dice")
        self.assertEqual(milestones.metric(self.u, "casino_rounds"), rules.COUNT_CAPS["casino"], "...count as thirty")
        activity.record(self.u, "casino", "next-day", now=DAYS[3], amount=5, game="dice")
        self.assertEqual(milestones.metric(self.u, "casino_rounds"), rules.COUNT_CAPS["casino"] + 1)

    def test_challenges_completed_counts_each_once(self):
        a = challenges.assign(WEEK)
        item = a["items"][0]
        finish(self.u, item)
        n = milestones.metric(self.u, "challenges_done")
        self.assertGreaterEqual(n, 1)
        challenges.evaluate(self.u, WEEK, T0)
        challenges.evaluate(self.u, WEEK, T0 + 1000)
        self.assertEqual(milestones.metric(self.u, "challenges_done"), n)
        challenges.claim(self.u, item["id"], T0)
        self.assertEqual(milestones.metric(self.u, "challenges_done"), n, "claiming is not completing again")

    def test_the_real_actions_all_feed_it(self):
        other = mk("maker")
        m = markets.create(self.u, {"scope": "site", "question": "Does everything feed it?"})
        self.assertEqual(milestones.metric(self.u, "polls_created"), 1)
        markets.trade(self.u, m, {"outcome": 0, "amount": 5})
        self.assertEqual(milestones.metric(self.u, "market_bets"), 1)
        games.limbo(self.u, {"amount": 5, "target": 1.5})
        self.assertEqual(milestones.metric(self.u, "casino_rounds"), 1)
        circle_of(self.u, other)
        self.assertEqual(milestones.metric(self.u, "circles_joined"), 1)
        c2 = circles.create(other, {"name": "Second"})
        circles.join(self.u, c2["id"], c2["inviteCode"])
        self.assertEqual(milestones.metric(self.u, "circles_joined"), 2)
        exchange.engine = new_engine(1)
        exchange.QUOTES.clear()
        ledger.post(self.u, "accumulated", 5000, "test.setup")
        q = exchange.quote(self.u, {"symbol": "NEXO", "side": "buy", "shares": 1}, EX_T0 + 5000)
        exchange.trade(self.u, {"quoteId": q["quoteId"]}, EX_T0 + 5000)
        self.assertEqual(milestones.metric(self.u, "stock_trades"), 1)
        self.assertIn("exchange", progress.state(self.u)["features"])

    def test_a_poker_hand_counts_as_taking_part(self):
        ann, bob = mk("annie", 5000), mk("bobby", 5000)
        t = poker.create(ann, {"name": "Table", "visibility": "public"})
        poker.join(bob, t["id"])
        poker.vote(ann, t, True)
        poker.vote(bob, t, True)
        poker.start(ann, t)
        for u in (ann, bob):
            self.assertIn("poker", progress.state(u)["features"])
            self.assertGreaterEqual(progress.xp_of(u), 1)

    def test_loans_transfers_and_purchases_move_none_of_it(self):
        from backend import cosmetics
        ledger.post(self.u, "accumulated", 500, "test.setup")
        self.u["balance"] = 400.0
        before = copy.deepcopy(progress.state(self.u))
        loans.borrow(self.u, 100, now=T0)
        loans.repay(self.u, "all", now=T0)
        cosmetics.buy(self.u, "avatar_chicken")
        self.assertEqual(progress.state(self.u), before)


class Claiming(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", weekly=700, accum=10)
        rounds(self.u, 1)

    def test_the_money_goes_to_the_accumulated_account_with_xp_and_a_ledger_row(self):
        weekly_before = self.u["balance"]
        xp = progress.xp_of(self.u)
        r = milestones.claim(self.u, "house_guest:1")
        self.assertEqual((r["account"], r["amount"]), ("accumulated", 10.0))
        self.assertEqual((self.u["accum"], self.u["balance"]), (20.0, weekly_before), "the weekly account is not touched")
        self.assertEqual(progress.xp_of(self.u), xp + 10)
        row = [x for x in ledger.entries(self.u) if x["reason"] == "milestone"][0]
        self.assertEqual((row["account"], row["amount"], row["external"], row["ref"]), ("accumulated", 10.0, True, "house_guest:1"))
        self.assertTrue(books_balance(self.u))

    def test_each_tier_pays_exactly_once(self):
        milestones.claim(self.u, "house_guest:1")
        self.assertEqual(err(milestones.claim, self.u, "house_guest:1").status, 409)
        self.assertEqual(self.u["accum"], 20.0)
        self.assertEqual(len([x for x in ledger.entries(self.u) if x["reason"] == "milestone"]), 1)

    def test_eight_claims_at_once_pay_once(self):
        results = []

        def go():
            with LOCK:
                try:
                    milestones.claim(self.u, "house_guest:1")
                    results.append("paid")
                except ApiError as e:
                    results.append(e.status)
        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((results.count("paid"), results.count(409)), (1, 7))
        self.assertEqual(self.u["accum"], 20.0)

    def test_what_is_not_reached_or_does_not_exist_cannot_be_claimed(self):
        self.assertIn("not reached", err(milestones.claim, self.u, "house_guest:2").message)
        self.assertEqual(err(milestones.claim, self.u, "nonsense:9").status, 404)
        self.assertEqual(err(milestones.claim, self.u, None).status, 404)

    def test_a_failed_claim_changes_nothing_and_can_be_repeated(self):
        with mock.patch.object(milestones.progress, "grant", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                milestones.claim(self.u, "house_guest:1")
        self.assertEqual(self.u["accum"], 10.0)
        self.assertNotIn("house_guest:1", progress.state(self.u)["claimed"])
        self.assertTrue(books_balance(self.u))
        milestones.claim(self.u, "house_guest:1")
        self.assertEqual(self.u["accum"], 20.0)

    def test_rewards_never_expire_and_progress_survives_weekly_resets_and_restarts(self):
        rounds(self.u, 30, tag="more", start=DAYS[0])
        self.u["wk"]["week"] = prev_week_key(WEEK)
        db()["meta"]["week"] = prev_week_key(WEEK)
        weekly.tick()                                              # a weekly reset
        weekly.tick()
        store.save()
        store.load()
        again = users.get(self.u["id"])
        self.assertEqual(milestones.metric(again, "casino_rounds"), 31)
        self.assertIn("house_guest:2", progress.state(again)["done"])
        self.assertEqual(milestones.claim(again, "house_guest:1")["amount"], 10.0, "claimed weeks later")
        self.assertEqual(milestones.claim(again, "house_guest:2")["amount"], 25.0)
        store.save()
        store.load()
        self.assertEqual(sorted(progress.state(users.get(self.u["id"]))["claimed"]), ["house_guest:1", "house_guest:2"])


class NoLoops(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", accum=0)

    def test_reaching_a_rank_completes_the_rank_milestone_and_claiming_it_gives_money_only(self):
        progress.grant(self.u, 120, "test", "x")
        self.assertEqual(progress.rank_of(self.u)["tierIndex"], 0)
        progress.grant(self.u, 900, "test", "y")                                    # Silver
        self.assertEqual(progress.rank_of(self.u)["tier"], "silver")
        self.assertIn("climber:1", progress.state(self.u)["done"])
        xp = progress.xp_of(self.u)
        r = milestones.claim(self.u, "climber:1")
        self.assertEqual((r["amount"], r["xp"]), (50.0, 0))
        self.assertEqual(progress.xp_of(self.u), xp, "rank rewards do not give XP, so they cannot raise the rank again")

    def test_claiming_everything_reached_settles_and_does_not_keep_paying(self):
        rounds(self.u, 30)
        for tid in list(progress.state(self.u)["done"]):
            milestones.claim(self.u, tid)
        xp, accum = progress.xp_of(self.u), self.u["accum"]
        for tid in list(progress.state(self.u)["done"]):
            err(milestones.claim, self.u, tid)
        milestones.evaluate(self.u)
        challenges.evaluate(self.u, WEEK)
        self.assertEqual((progress.xp_of(self.u), self.u["accum"]), (xp, accum))
        self.assertEqual(milestones.view(self.u)["totals"]["claimable"], 0)


class HistoryBackfill(unittest.TestCase):
    def old_user(self, name="vet"):
        u = users.register(name, "secret123")
        u["createdAt"] = now_ms() - 200 * DAY_MS
        u["stats"] = {"2026-06-01": {"marketBets": 12, "gamesPlayed": 40}, "2026-06-08": {"marketBets": 0, "gamesPlayed": 30},
                      "2026-06-15": {"gamesPlayed": 0, "marketBets": 0}, "2026-06-22": {"marketBets": 40}}
        u["history"] = [{"id": "a", "t": 1, "game": "dice", "bet": 5, "payout": 0, "profit": -5}, {"id": "b", "t": 2, "game": "poker", "bet": 5, "payout": 0, "profit": -5},
                        {"id": "c", "t": 3, "game": "limbo", "bet": 5, "payout": 0, "profit": -5}, {"id": "d", "t": 4, "game": "horses", "bet": 5, "payout": 0, "profit": -5}]
        u["trades"] = [{"id": "t1", "t": 1, "sym": "NEXO", "side": "buy", "sh": 1, "px": 100, "total": 100}] * 3
        return u

    def setUp(self):
        fresh_store()

    def test_only_what_the_old_records_show_is_counted(self):
        u = self.old_user()
        m = markets.create(u, {"scope": "site", "question": "A poll made long ago?"})
        circle_of(u, mk("pal"))
        progress.state(u).update({"m": {}, "games": [], "features": [], "done": {}, "claimed": {}, "seen": {}})
        xp_before = progress.xp_of(u)                              # (making the poll above was a real action and earned its own XP)
        milestones.backfill(u, db())
        mm = progress.state(u)["m"]
        self.assertEqual((mm["market_bets"], mm["casino_rounds"], mm["weeks_active"]), (52, 70, 3))
        self.assertEqual((mm["stock_trades"], mm["polls_created"], mm["circles_joined"]), (3, 1, 1))
        self.assertEqual(sorted(progress.state(u)["games"]), ["dice", "limbo"], "only real casino games from the history; poker and the retired one are not games here")
        self.assertEqual(sorted(progress.state(u)["features"]), ["casino", "circles", "create", "exchange", "poker", "polls"])
        self.assertNotIn("days_active", mm, "days taken part in cannot be known, so they are not invented")
        self.assertEqual(progress.xp_of(u), xp_before, "the past earns no XP: nobody is promoted for it")
        self.assertIn("predictor:3", progress.state(u)["done"])
        self.assertIn("house_guest:2", progress.state(u)["done"])
        self.assertNotIn("house_guest:3", progress.state(u)["done"], "70 rounds is not 150")
        self.assertNotIn("regular:4", progress.state(u)["done"])
        self.assertEqual(progress.state(u)["claimed"], {}, "nothing is paid until the person claims it")

    def test_running_it_twice_changes_nothing(self):
        u = self.old_user()
        milestones.backfill(u, db())
        first = copy.deepcopy(progress.state(u))
        n_inbox = len(u.get("inbox", []))
        milestones.backfill(u, db())
        self.assertEqual(progress.state(u)["m"], first["m"])
        self.assertEqual(progress.state(u)["done"], first["done"])
        self.assertEqual(len(u.get("inbox", [])), n_inbox, "and nobody is told twice")

    def test_the_migration_is_additive_keeps_every_balance_and_tells_each_person_once(self):
        u = self.old_user()
        data = db()
        before = {k: u[k] for k in ("balance", "accum", "username", "stats", "history")}
        data["meta"]["schema"] = 3
        for k in ("loans", "challenges", "transfers"):
            data.pop(k, None)
        u.pop("goals", None)
        u.pop("inbox", None)
        ran = migrations.run(data)
        self.assertEqual(ran, ["add_goals", "add_game_goals"])
        self.assertEqual(data["meta"]["schema"], migrations.SCHEMA)
        self.assertEqual({k: u[k] for k in before}, before, "nothing that existed was changed")
        self.assertTrue(all(k in data for k in ("loans", "challenges", "transfers")))
        self.assertEqual(data["meta"]["goals_migration"]["people"], len(data["users"]))
        self.assertEqual([n["title"] for n in u["inbox"]], ["Milestones unlocked from your history"])
        self.assertEqual(migrations.run(data), [], "and a second start-up does nothing")

    def test_the_week_under_way_keeps_the_progress_the_old_records_show(self):
        u = self.old_user("midweek")
        u["history"].insert(0, {"id": "z", "t": DAYS[0], "game": "wheel", "bet": 5, "payout": 0, "profit": -5})
        u["stats"][WEEK] = {"gamesPlayed": 1}
        data = db()
        data["meta"]["schema"] = 3
        data.pop("challenges", None)
        migrations.run(data)
        facts = challenges.week_state(u, WEEK)["facts"]
        self.assertEqual(facts["games"], ["wheel"])
        self.assertEqual(progress.state(u)["lastWeek"], WEEK, "so the first new action this week is not counted as a second week")


if __name__ == "__main__":
    unittest.main()
