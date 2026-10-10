"""Goals about one particular game: play N hands of Blackjack, reach N x in Tower, win $N in Chicken. How they are counted, what they cannot be
used for, and how they appear as milestones and as weekly challenges."""
import copy
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import activity, challenges, economy, games, ledger, migrations, milestones, progress, rules, weekly   # noqa: E402
from backend.store import db                                                                                         # noqa: E402
from backend.util import ApiError, DAY_MS, next_week_key, prev_week_key, week_bounds, week_key                       # noqa: E402
from tests.econ import books_balance, mk                                                                             # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                                            # noqa: E402
from tests.test_challenges import finish                                                                              # noqa: E402

HOUR = 3_600_000
WEEK = week_key()
START, END = week_bounds(WEEK)
DAYS = [START + i * DAY_MS + 12 * HOUR for i in range(7)]
T0 = DAYS[2]


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def rnd(user, ref, game, stake=5.0, payout=0.0, mult=None, now=T0):
    """One finished round of `game`, as games._record reports it."""
    return activity.record(user, "casino", ref, now=now, amount=stake, game=game, payout=payout, mult=mult)


def gm(user, game):
    return progress.state(user)["gm"].get(game, {})


class TheCatalogue(unittest.TestCase):
    def by_id(self):
        return {m["id"]: m for m in rules.MILESTONES}

    def test_every_game_has_a_play_goal_and_a_signature_goal(self):
        ms = self.by_id()
        for gid in rules.GAME_INFO:
            self.assertIn(f"{gid}_play", ms, gid)
            self.assertEqual(ms[f"{gid}_play"]["metric"], f"rounds:{gid}")
            sig = rules.SIGNATURE[gid]
            self.assertIn(f"{gid}_{sig}", ms, gid)
            self.assertEqual(ms[f"{gid}_{sig}"]["metric"], f"{sig}:{gid}")
        self.assertIn("poker_play", ms)
        self.assertEqual(len([m for m in rules.MILESTONES if m["group"] == "game"]), 2 * len(rules.GAME_INFO) + 1)

    def test_the_examples_in_the_request_exist(self):
        ms = self.by_id()
        self.assertEqual((ms["chicken_won"]["kind"], ms["chicken_won"]["metric"]), ("money", "won:chicken"))           # earn x in chicken
        self.assertEqual((ms["blackjack_play"]["unit"], ms["blackjack_play"]["tiers"][0][0]), ("hands", 25))             # play x hands in blackjack
        self.assertEqual((ms["tower_best"]["kind"], ms["tower_best"]["metric"], [t[0] for t in ms["tower_best"]["tiers"]]), ("mult", "best:tower", [3, 10, 40]))

    def test_tiers_rise_in_targets_and_pay_more(self):
        for m in rules.game_milestones():
            targets = [t[0] for t in m["tiers"]]
            money = [t[1] for t in m["tiers"]]
            self.assertEqual(targets, sorted(set(targets)), m["id"])
            self.assertEqual(money, sorted(money), m["id"])
            self.assertTrue(all(t[1] > 0 for t in m["tiers"]))

    def test_a_multiplier_goal_only_exists_for_games_where_the_multiplier_is_yours_to_push(self):
        for gid in rules.GAME_INFO:
            if rules.SIGNATURE[gid] == "best":
                self.assertIn(gid, rules.GAME_BEST, gid)
                self.assertIn(f"{gid}_best", self.by_id())
            else:
                self.assertNotIn(f"{gid}_best", self.by_id())
        for gid in ("blackjack", "roulette", "war"):
            self.assertNotIn(gid, rules.GAME_BEST, "a table game's payout is not a multiplier you can push")
            self.assertNotIn(gid, rules.games_for("best"))
        self.assertIn("chicken", rules.games_for("best"), "chicken still has weekly multiplier challenges, next to its earning milestone")

    def test_every_multiplier_target_is_one_the_game_can_really_pay(self):
        most = {
            "coinflip": max(games.coin_mult(n) for n in range(1, games.COIN_MAX_FLIPS + 1)),
            "rps": games.rps_mult_x100(games.RPS_MAX_WINS) / 100,
            "wheel": max(max(games.wheel_layout(r)) for r in games.WHEEL_RISKS) / 100,
            "chicken": max(games.chicken_table(d)[-1] for d in games.CHICKEN),
            "tower": max(games.tower_mult(r, games.TOWER_ROWS) for r in games.TOWER_RISK),
            "mines": max(games.mines_mult(size, k, p) for size in games.MINES_SIZES for k in range(1, size) for p in range(1, size - k + 1)),
            "moles": max(games.moles_mult(m, h) for m in range(1, games.MOLES_HOLES) for h in range(games.MOLES_MAX_STEPS + 1)),
            "hilo": games.HILO_MAX_MULT,
            "limbo": games.LIMBO_MAX,
            "dice": 9900.0,
        }
        self.assertEqual(set(most), set(rules.GAME_BEST))
        for gid, (milestone_targets, weekly_targets) in rules.GAME_BEST.items():
            self.assertLessEqual(max(milestone_targets), most[gid], f"{gid}: the top milestone target must be possible")
            self.assertLessEqual(max(weekly_targets), most[gid], gid)
            self.assertEqual(milestone_targets, sorted(milestone_targets))
            self.assertEqual(weekly_targets, sorted(weekly_targets))
        # and the small ones are real steps of the games with fixed ladders, so "3x" really means "two in a row" and not an unreachable 4
        self.assertLessEqual(3, games.coin_mult(2))
        self.assertLessEqual(7, games.coin_mult(3))
        self.assertLessEqual(3, games.rps_mult_x100(2) / 100)

    def test_nothing_rewards_losing_borrowing_or_a_bigger_stake(self):
        text = " ".join(m["desc"].lower() for m in rules.game_milestones())
        for word in ("loan", "borrow", "lose", "loss", "stake more", "bigger"):
            self.assertNotIn(word, text)
        self.assertIn("up to $25 a round", self.by_id()["chicken_won"]["desc"], "the cap on a round is stated in the goal itself")

    def test_tiers_read_naturally(self):
        fresh_store()
        v = milestones.view(mk("ann"))["milestones"]
        by = {m["id"]: m for m in v}
        self.assertEqual([t["label"] for t in by["tower_best"]["tiers"]], ["reach 3×", "reach 10×", "reach 40×"])
        self.assertEqual([t["label"] for t in by["chicken_won"]["tiers"]], ["win $50", "win $250", "win $1,000"])
        self.assertEqual([t["label"] for t in by["blackjack_play"]["tiers"]], ["25 hands", "100 hands", "500 hands"])
        self.assertEqual([t["label"] for t in by["roulette_wins"]["tiers"]][0], "10 wins")
        self.assertEqual((by["tower_best"]["group"], by["tower_best"]["game"], by["tower_best"]["kind"]), ("game", "tower", "mult"))
        self.assertEqual(by["predictor"]["group"], "general")


class Counting(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann")

    def test_a_round_counts_by_what_happened_in_it(self):
        rnd(self.u, "a", "tower", stake=5, payout=15.0, mult=3.0)          # a win at 3x
        rnd(self.u, "b", "tower", stake=5, payout=0.0, mult=None)          # a loss
        rnd(self.u, "c", "tower", stake=5, payout=5.0, mult=1.0)           # a push: stake back, no profit
        self.assertEqual(gm(self.u, "tower"), {"rounds": 3, "wins": 1, "won_c": 1000, "best_x100": 300})
        self.assertEqual(milestones.metric(self.u, "rounds:tower"), 3)
        self.assertEqual(milestones.metric(self.u, "wins:tower"), 1)
        self.assertEqual(milestones.metric(self.u, "won:tower"), 10.0)
        self.assertEqual(milestones.metric(self.u, "best:tower"), 3.0)

    def test_a_loss_has_no_multiplier_and_never_lowers_the_best(self):
        rnd(self.u, "a", "tower", payout=40.0, mult=8.0)
        rnd(self.u, "b", "tower", payout=0.0, mult=None)
        rnd(self.u, "c", "tower", payout=10.0, mult=2.0)
        self.assertEqual(gm(self.u, "tower")["best_x100"], 800)
        rnd(self.u, "d", "tower", payout=0.0, mult=9.9)                    # a multiplier on a round that paid nothing is not a win
        self.assertEqual(gm(self.u, "tower")["best_x100"], 800)

    def test_each_game_is_counted_on_its_own(self):
        rnd(self.u, "a", "chicken", payout=10.0, mult=2.0)
        rnd(self.u, "b", "blackjack", payout=0.0)
        rnd(self.u, "c", "blackjack", payout=0.0)
        self.assertEqual((gm(self.u, "chicken")["rounds"], gm(self.u, "blackjack")["rounds"]), (1, 2))
        self.assertEqual(gm(self.u, "dice"), {})

    def test_one_round_never_counts_for_more_than_the_cap_so_a_huge_stake_is_no_shortcut(self):
        small, huge = mk("small"), mk("huge")
        rnd(small, "s", "chicken", stake=5, payout=30.0, mult=6.0)                  # won 25: exactly the cap
        rnd(huge, "h", "chicken", stake=1000, payout=2000.0, mult=2.0)              # won 1,000
        self.assertEqual(gm(small, "chicken")["won_c"], 2500)
        self.assertEqual(gm(huge, "chicken")["won_c"], 2500, "the same credit: the bigger stake only bought a bigger risk")
        with mock.patch.object(economy, "GAME_WIN_CREDIT_CAP", 10.0):
            rnd(huge, "h2", "chicken", stake=1000, payout=2000.0, mult=2.0)
        self.assertEqual(gm(huge, "chicken")["won_c"], 3500)

    def test_the_stake_does_not_change_a_multiplier_goal(self):
        a, b = mk("lowbet"), mk("highbet")
        rnd(a, "a", "limbo", stake=1, payout=10.0, mult=10.0)
        rnd(b, "b", "limbo", stake=900, payout=9000.0, mult=10.0)
        self.assertEqual(gm(a, "limbo")["best_x100"], gm(b, "limbo")["best_x100"])

    def test_small_stakes_and_practice_play_count_for_nothing(self):
        self.assertIsNone(rnd(self.u, "t", "dice", stake=0.99, payout=5.0, mult=5.0))
        self.assertEqual(gm(self.u, "dice"), {})
        demo = games.demo_account(self.u)
        games.dice(demo, {"amount": 10, "direction": "over", "target": 50})
        self.assertNotIn("goals", demo)
        self.assertEqual(gm(self.u, "dice"), {})

    def test_the_daily_cap_stops_rounds_wins_and_winnings_but_not_a_best_multiplier(self):
        for i in range(30):
            rnd(self.u, f"r{i}", "dice", payout=6.0, mult=1.2)
        before = dict(gm(self.u, "dice"))
        self.assertEqual((before["rounds"], before["wins"], before["won_c"]), (30, 30, 3000))
        rnd(self.u, "r31", "dice", payout=500.0, mult=100.0)                         # over the cap: rounds, wins and winnings stop...
        after = gm(self.u, "dice")
        self.assertEqual((after["rounds"], after["wins"], after["won_c"]), (30, 30, 3000))
        self.assertEqual(after["best_x100"], 10000, "...but a 100x is a 100x")
        rnd(self.u, "next-day", "dice", payout=6.0, mult=1.2, now=DAYS[3])
        self.assertEqual(gm(self.u, "dice")["rounds"], 31, "and the next day counts again")

    def test_the_same_round_twice_is_one_round(self):
        rnd(self.u, "same", "war", payout=10.0, mult=2.0)
        self.assertIsNone(rnd(self.u, "same", "war", payout=10.0, mult=2.0))
        self.assertEqual(gm(self.u, "war")["rounds"], 1)

    def test_poker_hands_count_as_rounds_and_nothing_else(self):
        for i in range(3):
            activity.record(self.u, "poker", f"h{i}", now=T0)
        self.assertEqual(gm(self.u, "poker"), {"rounds": 3})
        self.assertEqual(milestones.metric(self.u, "rounds:poker"), 3)

    def test_the_weeks_own_numbers_follow_the_same_rules_and_the_boundary(self):
        rnd(self.u, "late", "chicken", payout=20.0, mult=4.0, now=END - 1)
        rnd(self.u, "early", "chicken", payout=20.0, mult=4.0, now=END)
        this_week = challenges.week_state(self.u, WEEK)["facts"]["gm"]["chicken"]
        next_one = challenges.week_state(self.u, next_week_key(WEEK))["facts"]["gm"]["chicken"]
        self.assertEqual((this_week["rounds"], next_one["rounds"]), (1, 1), "the very last millisecond belongs to the old week, the next one to the new")
        self.assertEqual(gm(self.u, "chicken")["rounds"], 2, "and the lifetime number has both")

    def test_real_games_feed_it_through_the_real_code_path(self):
        with mock.patch.object(games, "rand_unit", return_value=0.001):              # limbo rolls huge: a certain win
            games.limbo(self.u, {"amount": 5, "target": 5})
        self.assertEqual(gm(self.u, "limbo")["rounds"], 1)
        self.assertEqual(gm(self.u, "limbo")["best_x100"], 500)
        self.assertEqual(gm(self.u, "limbo")["won_c"], 2000, "5 x 5 = 25 paid, 20 profit")
        with mock.patch.object(games, "rand_unit", return_value=1.0):                # and a certain loss
            games.limbo(self.u, {"amount": 5, "target": 50})
        self.assertEqual((gm(self.u, "limbo")["rounds"], gm(self.u, "limbo")["wins"]), (2, 1))
        self.assertIn("limbo_best:1", progress.state(self.u)["done"], "5x reached the first multiplier tier")

    def test_loans_and_transfers_move_none_of_it(self):
        before = copy.deepcopy(progress.state(self.u)["gm"])
        self.u["balance"] = 400.0
        from backend import loans
        loans.borrow(self.u, 100, now=T0)
        loans.repay(self.u, "all", now=T0)
        self.assertEqual(progress.state(self.u)["gm"], before)


class AsMilestones(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("ann", accum=10)

    def test_reaching_a_tier_unlocks_it_and_the_view_shows_how_far_you_are(self):
        for i in range(25):
            rnd(self.u, f"b{i}", "blackjack", payout=0.0)
        self.assertIn("blackjack_play:1", progress.state(self.u)["done"])
        m = next(x for x in milestones.view(self.u)["milestones"] if x["id"] == "blackjack_play")
        self.assertEqual((m["value"], m["next"]["target"], m["tiers"][0]["status"]), (25, 100, "reached"))

    def test_a_money_goal_shows_dollars_and_a_multiplier_goal_shows_the_multiplier(self):
        rnd(self.u, "c", "chicken", stake=5, payout=30.0, mult=6.0)
        rnd(self.u, "t", "tower", stake=5, payout=17.5, mult=3.5)
        v = {m["id"]: m for m in milestones.view(self.u)["milestones"]}
        self.assertEqual((v["chicken_won"]["value"], v["chicken_won"]["kind"]), (25.0, "money"))
        self.assertEqual((v["tower_best"]["value"], v["tower_best"]["kind"]), (3.5, "mult"))
        self.assertIn("tower_best:1", progress.state(self.u)["done"])
        self.assertNotIn("tower_best:2", progress.state(self.u)["done"])

    def test_claiming_pays_the_accumulated_account_once_with_xp(self):
        rnd(self.u, "t", "tower", payout=17.5, mult=3.5)
        r = milestones.claim(self.u, "tower_best:1")
        self.assertEqual((r["account"], r["amount"], r["xp"]), ("accumulated", 10.0, 10))
        self.assertEqual(self.u["accum"], 20.0)
        self.assertEqual(err(milestones.claim, self.u, "tower_best:1").status, 409)
        self.assertEqual(err(milestones.claim, self.u, "tower_best:2").status, 400)
        self.assertEqual(self.u["accum"], 20.0)
        row = [x for x in ledger.entries(self.u) if x["reason"] == "milestone"][0]
        self.assertEqual((row["account"], row["external"], row["ref"]), ("accumulated", True, "tower_best:1"))
        self.assertTrue(books_balance(self.u))

    def test_a_game_milestone_adds_nothing_to_the_general_ones_by_itself(self):
        rnd(self.u, "x", "mines", payout=10.0, mult=2.0)
        self.assertEqual(milestones.metric(self.u, "casino_rounds"), 1, "the general counter still sees the round, once")
        self.assertEqual(milestones.metric(self.u, "market_bets"), 0)


class AsWeeklyChallenges(unittest.TestCase):
    def setUp(self):
        fresh_store()

    def items(self, week=WEEK):
        return {i["family"]: i for i in challenges.assign(week)["items"]}

    def test_each_week_has_a_play_and_a_multiplier_goal_for_the_weekly_account_and_a_wins_and_an_earn_goal_for_the_accumulated_one(self):
        it = self.items()
        self.assertEqual({f: it[f]["account"] for f in ("play", "mult", "wins", "earn")}, {"play": "weekly", "mult": "weekly", "wins": "accumulated", "earn": "accumulated"})

    def test_the_combinations_are_always_valid_and_the_games_rotate(self):
        seen = {f: set() for f in ("play", "mult", "wins", "earn")}
        w = WEEK
        for _ in range(60):
            it = self.items(w)
            games_used = [it[f]["game"] for f in seen]
            self.assertEqual(len(set(games_used)), 4, "four different games in a week")
            for f, i in it.items():
                if f not in seen:
                    continue
                seen[f].add(i["game"])
                self.assertIn(i["game"], rules.games_for(i["metric"]), "a multiplier goal is never set in a game that has none")
                self.assertIn(i["target"], [t for t, _ in rules.weekly_targets(i["game"], i["metric"])])
            w = next_week_key(w)
        for f, gs in seen.items():
            self.assertGreaterEqual(len(gs), 8, f"{f} visits many different games over a couple of months")
        self.assertTrue({"blackjack", "tower", "chicken"} <= seen["play"] | seen["mult"] | seen["wins"] | seen["earn"])

    def test_the_wording_names_the_game_and_the_rules(self):
        it = self.items()
        for f in ("play", "mult", "wins", "earn"):
            i = it[f]
            name = rules.GAME_INFO[i["game"]][0]
            self.assertIn(name, i["title"])
            self.assertIn(name, i["desc"])
            self.assertIn(name, i["rule"])
            self.assertIn("$1.00", i["rule"])
            self.assertNotIn("{", i["desc"] + i["rule"] + i["title"])
            self.assertEqual(i["href"], f"#/games/{i['game']}")
        self.assertIn("never how much you staked", it["mult"]["rule"])
        self.assertIn("$25 per round", it["earn"]["rule"])

    def test_the_accumulated_account_pays_half_because_that_money_is_kept(self):
        for w in (WEEK, next_week_key(WEEK), next_week_key(next_week_key(WEEK))):
            it = self.items(w)
            for f in ("wins", "earn"):
                base = dict(rules.weekly_targets(it[f]["game"], it[f]["metric"]))[it[f]["target"]]
                self.assertEqual(it[f]["reward_c"], round(base * 50))
            for f in ("play", "mult"):
                base = dict(rules.weekly_targets(it[f]["game"], it[f]["metric"]))[it[f]["target"]]
                self.assertEqual(it[f]["reward_c"], base * 100)

    def test_they_are_frozen_with_the_week_even_if_the_cap_or_the_scale_changes(self):
        first = copy.deepcopy(challenges.assign(WEEK)["items"])
        with mock.patch.object(economy, "GAME_WIN_CREDIT_CAP", 99.0), mock.patch.object(economy, "REWARD_SCALE", 4.0):
            self.assertEqual(challenges.assign(WEEK)["items"], first)
        self.assertIn("$25 per round", self.items()["earn"]["rule"])

    def test_progress_reads_each_games_numbers_for_the_week(self):
        u = mk("ann")
        it = self.items()
        play, mult, wins, earn = it["play"], it["mult"], it["wins"], it["earn"]
        for i in range(3):
            rnd(u, f"p{i}", play["game"], payout=0.0)
        row = {r["id"]: r for r in challenges.view(u, T0)["weekly"] + challenges.view(u, T0)["accumulated"]}
        self.assertEqual((row[play["id"]]["progress"], row[play["id"]]["status"], row[play["id"]]["kind"]), (3, "in_progress", "count"))
        rnd(u, "m", mult["game"], stake=5, payout=5.0 * 1.5, mult=1.5)
        row = {r["id"]: r for r in challenges.view(u, T0)["weekly"]}
        self.assertEqual((row[mult["id"]]["progress"], row[mult["id"]]["kind"]), (1.5, "mult"))
        rnd(u, "w", wins["game"], payout=8.0, mult=1.6)
        rnd(u, "e", earn["game"], stake=5, payout=15.0, mult=3.0)
        row = {r["id"]: r for r in challenges.view(u, T0)["accumulated"]}
        self.assertEqual((row[wins["id"]]["progress"], row[earn["id"]]["progress"], row[earn["id"]]["kind"]), (1, 10.0, "money"))

    def test_other_games_do_not_count(self):
        u = mk("ann")
        play = self.items()["play"]
        other = next(g for g in rules.GAME_INFO if g != play["game"])
        for i in range(20):
            rnd(u, f"o{i}", other, payout=0.0)
        self.assertEqual(challenges._value(play, challenges.week_state(u, WEEK)["facts"]), 0)

    def test_finishing_each_one_pays_the_right_account_exactly_once(self):
        u = mk("ann", weekly=500, accum=100)
        it = self.items()
        for f in ("play", "mult"):
            finish(u, it[f])
            r = challenges.claim(u, it[f]["id"], T0)
            self.assertEqual((r["account"], r["amount"]), ("weekly", it[f]["reward_c"] / 100), f)
        for f in ("wins", "earn"):
            finish(u, it[f])
            r = challenges.claim(u, it[f]["id"], T0)
            self.assertEqual((r["account"], r["amount"]), ("accumulated", it[f]["reward_c"] / 100), f)
            self.assertEqual(err(challenges.claim, u, it[f]["id"], T0).status, 409)
        self.assertTrue(books_balance(u))

    def test_one_giant_round_counts_for_no_more_than_the_cap(self):
        u = mk("ann")
        earn = self.items()["earn"]
        rnd(u, "giant", earn["game"], stake=5000, payout=50000.0, mult=10.0)           # a 45,000 profit, but it counts as 25
        self.assertEqual(challenges._value(earn, challenges.week_state(u, WEEK)["facts"]), 25.0)
        self.assertEqual(challenges.week_state(u, WEEK)["facts"]["gm"][earn["game"]]["won_c"], 2500)
        rnd(u, "giant2", earn["game"], stake=5000, payout=50000.0, mult=10.0)
        self.assertEqual(challenges._value(earn, challenges.week_state(u, WEEK)["facts"]), 50.0, "a second one adds another 25, not another 45,000")

    def test_a_finished_one_that_nobody_claimed_is_credited_once_at_the_close(self):
        prev = prev_week_key(WEEK)
        u = mk("ann", accum=100)
        other = mk("ben")
        a = challenges.assign(prev)
        earn = next(i for i in a["items"] if i["family"] == "earn")
        finish(u, earn, prev)
        for p in (u, other):
            p["wk"]["week"] = prev
        db()["meta"]["week"] = prev
        weekly.tick()
        self.assertEqual(u["accum"], 100.0 + earn["reward_c"] / 100)
        weekly.tick()
        challenges.settle_week(prev)
        self.assertEqual(u["accum"], 100.0 + earn["reward_c"] / 100, "once, however often the close runs")
        self.assertEqual(other["accum"], 0.0)
        self.assertTrue(books_balance(u))

    def test_unfinished_ones_simply_expire(self):
        prev = prev_week_key(WEEK)
        u = mk("ann", accum=100)
        a = challenges.assign(prev)
        play = next(i for i in a["items"] if i["family"] == "play")
        rnd(u, "one", play["game"], now=week_bounds(prev)[0] + DAY_MS, payout=0.0)
        u["wk"]["week"] = prev
        db()["meta"]["week"] = prev
        weekly.tick()
        row = [r for h in challenges.view(u, T0)["history"] if h["week"] == prev for r in h["items"] if r["id"] == play["id"]][0]
        self.assertEqual((row["status"], row["progress"]), ("expired", 1))
        self.assertEqual(u["accum"], 100.0)


class FromTheOldRecords(unittest.TestCase):
    def setUp(self):
        fresh_store()

    def history(self):
        return [{"id": "1", "t": DAYS[1], "game": "chicken", "bet": 5.0, "payout": 30.0, "mult": 6.0, "profit": 25.0},
                {"id": "2", "t": DAYS[1], "game": "chicken", "bet": 5.0, "payout": 0.0, "mult": None, "profit": -5.0},
                {"id": "3", "t": DAYS[1], "game": "chicken", "bet": 0.5, "payout": 3.0, "mult": 6.0, "profit": 2.5},          # too small to count
                {"id": "4", "t": DAYS[0], "game": "tower", "bet": 10.0, "payout": 45.0, "mult": 4.5, "profit": 35.0},
                {"id": "5", "t": DAYS[0], "game": "poker", "bet": 20.0, "payout": 0.0, "mult": None, "profit": -20.0},       # a poker SESSION is not a hand
                {"id": "6", "t": START - 3 * DAY_MS, "game": "tower", "bet": 10.0, "payout": 20.0, "mult": 2.0, "profit": 10.0}]

    def test_the_numbers_come_only_from_what_the_history_shows_with_the_live_rules(self):
        u = mk("vet")
        u["history"] = self.history()
        milestones.backfill_games(u)
        self.assertEqual(gm(u, "chicken"), {"rounds": 2, "wins": 1, "won_c": 2500, "best_x100": 600})
        self.assertEqual(gm(u, "tower"), {"rounds": 2, "wins": 2, "won_c": 3500, "best_x100": 450}, "a 35 profit counts as the 25 cap, and a 10 profit counts in full")
        self.assertNotIn("poker", progress.state(u)["gm"])
        self.assertIn("tower_best:1", progress.state(u)["done"])
        self.assertNotIn("tower_best:2", progress.state(u)["done"])
        self.assertEqual(progress.state(u)["claimed"], {}, "nothing is paid until it is claimed")

    def test_it_is_idempotent_and_tells_the_person_once(self):
        u = mk("vet")
        u["history"] = self.history()
        n = milestones.backfill_games(u)
        first = copy.deepcopy(progress.state(u)["gm"])
        notes = len(u.get("inbox", []))
        self.assertGreaterEqual(n, 1)
        self.assertEqual(milestones.backfill_games(u), 0)
        self.assertEqual(progress.state(u)["gm"], first)
        self.assertEqual(len(u.get("inbox", [])), notes)
        self.assertEqual([x["title"] for x in u["inbox"]].count("More milestones unlocked from your history"), 1)

    def test_the_migration_step_changes_nothing_that_exists(self):
        u = mk("vet")
        u["history"] = self.history()
        data = db()
        data["meta"]["schema"] = 4
        data["meta"].pop("game_goals_migration", None)
        before = {k: copy.deepcopy(u[k]) for k in ("balance", "accum", "history", "stats", "username")}
        self.assertEqual(migrations.run(data), ["add_game_goals"])
        self.assertEqual({k: u[k] for k in before}, before)
        self.assertEqual(data["meta"]["schema"], migrations.SCHEMA)
        self.assertEqual(data["meta"]["game_goals_migration"]["people"], len(data["users"]))
        self.assertEqual(migrations.run(data), [])

    def test_the_week_under_way_remembers_its_games_too(self):
        u = mk("vet")
        u["history"] = self.history()
        challenges.backfill_week(u, db(), WEEK)
        gmf = challenges.week_state(u, WEEK)["facts"]["gm"]
        self.assertEqual((gmf["chicken"]["rounds"], gmf["chicken"]["wins"], gmf["chicken"]["best_x100"]), (2, 1, 600))
        self.assertEqual(gmf["tower"]["rounds"], 1, "last week's tower round is not this week's")


if __name__ == "__main__":
    unittest.main()
