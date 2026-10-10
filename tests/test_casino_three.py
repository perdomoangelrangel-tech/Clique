"""Hi-Lo, Wheel and Rock Paper Scissors. The random source is pinned so every outcome can be forced, and the maths is proven by
running every possible outcome through the real code (not by sampling)."""
import json
import os
import sys
import tempfile
import threading
import unittest
from fractions import Fraction
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                          # noqa: E402
from backend import games, ledger, markets, util                       # noqa: E402
from backend.store import db, store                                    # noqa: E402
from backend.util import ApiError                                      # noqa: E402
from tests.econ import books_balance, mk                               # noqa: E402
from tests.helpers import fresh_store, restore_store_path              # noqa: E402
from tests.test_http import Client                                     # noqa: E402


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def pin(*values):
    """Makes the server's random choices come out as `values`, in order (and fails loudly if it asks for more or for a number
    that does not fit)."""
    it = iter(values)

    def fake(n):
        v = next(it)
        assert 0 <= v < n, f"asked for a number below {n}, was given {v}"
        return v
    return fake


def card(rank, suit=0):
    """The two numbers Hi-Lo asks the random source for to draw a card: the rank (0 for an ace) and the suit."""
    return [rank - 1, suit]


class Setup(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("player", weekly=1000, accum=0)
        self.week_before = self.u["balance"]

    def balance(self):
        return ledger.balance(self.u, "weekly")


# ---------------------------------------------------------------------------------------------------------------------
class HiLoMaths(unittest.TestCase):
    def test_the_numbers_match_the_ones_a_queen_shows(self):
        o = games.hilo_options(12)
        self.assertEqual((o["lower"]["k"], round(o["lower"]["chance"] * 100, 2), o["lower"]["mult_x100"]), (12, 92.31, 104))
        self.assertEqual((o["higher"]["k"], round(o["higher"]["chance"] * 100, 2), o["higher"]["mult_x100"]), (2, 15.38, 624))

    def test_a_guess_that_cannot_lose_is_not_offered(self):
        self.assertFalse(games.hilo_options(1)["higher"]["offered"])
        self.assertFalse(games.hilo_options(13)["lower"]["offered"])
        for rank in range(1, 14):
            o = games.hilo_options(rank)
            self.assertEqual(o["higher"]["k"] + o["lower"]["k"], 14, "the two guesses overlap on the card itself")
            self.assertTrue(any(v["offered"] for v in o.values()), "there is always something to guess")

    def test_every_guess_that_is_offered_returns_at_most_96_percent_and_the_clean_ones_exactly_96(self):
        for rank in range(1, 14):
            for pick, o in games.hilo_options(rank).items():
                if not o["offered"]:
                    continue
                ev = Fraction(o["k"], 13) * Fraction(o["mult_x100"], 100)
                self.assertLessEqual(ev, Fraction(96, 100), (rank, pick))
                if o["k"] in (1, 2, 3, 4, 6, 8, 12):
                    self.assertEqual(ev, Fraction(96, 100), (rank, pick, "divides evenly, so there is no rounding loss"))

    def test_running_every_possible_next_card_through_the_real_code_gives_the_same_return(self):
        """For each card and each offered guess: bet $100, try all 13 next ranks, add up what is paid. Exactly 13 x 96 when
        the multiplier is clean, and never more."""
        for rank in range(1, 14):
            for pick in ("higher", "lower"):
                if not games.hilo_options(rank)[pick]["offered"]:
                    continue
                total = 0.0
                for nxt in range(1, 14):
                    fresh_store()
                    u = mk("player", weekly=1000)
                    with mock.patch.object(games, "rand_below", pin(*card(rank), *card(nxt, 1))):
                        games.hilo_start(u, {"amount": "100"})
                        res = games.hilo_guess(u, {"pick": pick})
                        if res["won"]:
                            total += games.hilo_cashout(u)["payout"]
                self.assertLessEqual(total / 13, 96.0 + 1e-9, (rank, pick))
                if games.hilo_options(rank)[pick]["k"] in (1, 2, 3, 4, 6, 8, 12):
                    self.assertAlmostEqual(total / 13, 96.0, places=6, msg=(rank, pick))


# ---------------------------------------------------------------------------------------------------------------------
class HiLoRounds(Setup):
    def start(self, rank=12, bet="10", suit=0):
        with mock.patch.object(games, "rand_below", pin(*card(rank, suit))):
            return games.hilo_start(self.u, {"amount": bet})

    def guess(self, pick, nxt, suit=1):
        with mock.patch.object(games, "rand_below", pin(*card(nxt, suit))):
            return games.hilo_guess(self.u, {"pick": pick})

    def test_starting_takes_the_stake_and_shows_a_card_and_what_each_guess_pays(self):
        r = self.start(12, "10")
        self.assertEqual(self.balance(), 990.0)
        self.assertEqual((r["card"]["r"], r["card"]["s"], r["bet"], r["wins"], r["mult"]), ("Q", "S", 10.0, 0, 1.0))
        self.assertEqual((r["options"]["higher"]["mult"], r["options"]["lower"]["mult"]), (6.24, 1.04))
        self.assertTrue(books_balance(self.u))

    def test_the_next_card_is_never_in_what_the_server_sends_before_you_guess(self):
        r = self.start()
        blob = json.dumps(games.hilo_state(self.u))
        self.assertNotIn('"next"', blob)
        self.assertEqual(set(r) & {"next", "deck", "upcoming"}, set())
        self.assertEqual(json.dumps(db()["games"][self.u["id"]]["hilo"]).count('"next"'), 0, "and it is not even stored: it is drawn when you guess")

    def test_a_right_guess_multiplies_and_a_wrong_one_ends_the_round(self):
        self.start(12)
        r = self.guess("higher", 13)                                   # Q then K: higher wins, x6.24
        self.assertTrue(r["won"])
        self.assertEqual((r["next"]["r"], r["mult"], r["payoutNow"], r["wins"]), ("K", 6.24, 62.4, 1))
        self.assertEqual(r["card"]["r"], "K", "the card you just turned over is the one you guess from next")
        r = self.guess("higher", 5)                                    # K then 5: wrong (K can still be guessed higher: only a K wins)
        self.assertFalse(r["won"])
        self.assertTrue(r["finished"])
        self.assertEqual(r["payout"], 0.0)
        self.assertEqual(self.balance(), 990.0)
        self.assertNotIn("hilo", db()["games"].get(self.u["id"], {}))
        self.assertEqual(self.u["history"][0]["game"], "hilo")
        self.assertEqual(self.u["history"][0]["payout"], 0.0)

    def test_the_activity_log_and_best_multiplier_use_the_name_not_the_id(self):
        self.assertEqual((games.game_title("hilo"), games.game_title("rps"), games.game_title("coinflip")),
                         ("Hi-Lo", "Rock Paper Scissors", "Coinflip"))
        self.start(12)
        self.guess("higher", 1)                                        # Q then A: wrong
        self.assertEqual(self.u["activity"][0]["text"], "Hi-Lo: lost")

    def test_the_multiplier_on_record_is_rounded_down_like_the_payout(self):
        self.start(4, "10")
        self.guess("higher", 5)                                        # x1.24
        self.guess("higher", 8)                                        # x1.38
        self.guess("lower", 3)                                         # x1.56: 1.24 x 1.38 x 1.56 = 2.669472
        res = games.hilo_cashout(self.u)
        self.assertEqual(res["payout"], 26.69)
        self.assertEqual(self.u["history"][0]["mult"], 2.66, "2.669x is never written down as 2.67x")

    def test_the_same_rank_wins_both_ways(self):
        for pick in ("higher", "lower"):
            fresh_store()
            self.u = mk("player", weekly=1000)
            self.start(7)
            self.assertTrue(self.guess(pick, 7)["won"], pick)

    def test_a_streak_multiplies_exactly_and_pays_down_to_the_cent(self):
        self.start(12, "10")
        self.guess("lower", 11)                                        # Q then J, lower: x1.04
        r = self.guess("higher", 13)                                   # J then K, higher: k=3, x4.16
        self.assertAlmostEqual(r["mult"], 1.04 * 4.16, places=6)
        self.assertEqual(r["payoutNow"], 43.26, "10 x 4.3264 = 43.264, paid down to the cent")
        res = games.hilo_cashout(self.u)
        self.assertEqual(res["payout"], 43.26)
        self.assertEqual(self.balance(), 990.0 + 43.26)
        self.assertTrue(books_balance(self.u))
        self.assertEqual(self.u["history"][0]["payout"], 43.26)

    def test_you_cannot_cash_out_before_a_right_guess(self):
        self.start()
        self.assertEqual(err(games.hilo_cashout, self.u).status, 400)
        self.assertEqual(self.balance(), 990.0)

    def test_a_guess_that_cannot_lose_is_refused_and_draws_nothing(self):
        self.start(1)                                                  # an ace: "higher or same" always wins
        with mock.patch.object(games, "rand_below", pin()):            # asking for any random number would fail
            e = err(games.hilo_guess, self.u, {"pick": "higher"})
        self.assertEqual(e.status, 400)
        self.assertEqual(games.hilo_state(self.u)["card"]["r"], "A")

    def test_only_higher_and_lower_are_guesses(self):
        self.start()
        self.assertEqual(err(games.hilo_guess, self.u, {"pick": "same"}).status, 400)
        self.assertEqual(err(games.hilo_guess, self.u, {}).status, 400)

    def test_skipping_changes_the_card_and_costs_nothing(self):
        self.start(12)
        before = self.balance()
        with mock.patch.object(games, "rand_below", pin(*card(3, 2))):
            r = games.hilo_skip(self.u)
        self.assertEqual((r["card"]["r"], r["mult"], r["wins"], self.balance(), r["skipsLeft"]), ("3", 1.0, 0, before, games.HILO_MAX_SKIPS - 1))

    def test_a_round_has_a_limited_number_of_skips(self):
        self.start(12)
        for _ in range(games.HILO_MAX_SKIPS):
            games.hilo_skip(self.u)
        e = err(games.hilo_skip, self.u)
        self.assertEqual(e.status, 400)

    def test_one_round_at_a_time_and_the_stake_is_taken_once(self):
        self.start()
        self.assertEqual(err(games.hilo_start, self.u, {"amount": "10"}).status, 400)
        self.assertEqual(self.balance(), 990.0)

    def test_the_stake_in_play_counts_as_the_players_money(self):
        self.start(12, "10")
        self.assertEqual(games.escrow(self.u["id"]), 10.0)
        self.assertAlmostEqual(markets.net_worth(self.u), 1000.0, places=2)

    def test_a_round_in_progress_is_found_again_from_the_server(self):
        self.start(12, "10")
        self.guess("lower", 11)
        state = games.active_state(self.u)["hilo"]
        self.assertEqual((state["card"]["r"], state["wins"], state["bet"]), ("J", 1, 10.0))

    def test_not_enough_money_and_bad_amounts_are_refused(self):
        self.assertEqual(err(games.hilo_start, self.u, {"amount": "5000"}).status, 400)
        self.assertEqual(err(games.hilo_start, self.u, {"amount": "0.01"}).status, 400)
        self.assertEqual(err(games.hilo_start, self.u, {"amount": "abc"}).status, 400)
        self.assertEqual(self.balance(), 1000.0)

    def test_practice_rounds_never_touch_the_real_account_or_the_big_wins_board(self):
        demo = games.account_for(self.u, True)
        feed_before = list(db()["feed"])
        with mock.patch.object(games, "rand_below", pin(*card(12), *card(13))):
            games.hilo_start(demo, {"amount": "100"})
            games.hilo_guess(demo, {"pick": "higher"})
            games.hilo_cashout(demo)
        self.assertEqual(self.balance(), 1000.0)
        self.assertEqual(db()["feed"], feed_before)
        self.assertFalse(any("gamesPlayed" in week for week in self.u["stats"].values()), "a practice round is not a casino round for the weekly minimum")
        self.assertFalse(any(h["game"] == "hilo" for h in self.u["history"]))
        self.assertGreater(demo["balance"], 1000.0)

    def test_the_random_source_is_the_secure_one(self):
        self.assertIs(games.rand_below, util.rand_below)


# ---------------------------------------------------------------------------------------------------------------------
class WheelMaths(unittest.TestCase):
    def test_every_risk_level_returns_exactly_96_percent(self):
        for risk, table in games.WHEEL_RISKS.items():
            self.assertEqual(sum(c for _, c in table), games.WHEEL_SEGMENTS, risk)
            self.assertEqual(sum(m * c for m, c in table), games.WHEEL_SEGMENTS * games.WHEEL_RTP_X100, risk)

    def test_the_low_wheel_has_the_multipliers_the_game_shows(self):
        self.assertEqual({m for m, _ in games.WHEEL_RISKS["low"]}, {0, 110, 120, 140, 200})

    def test_the_layout_is_fifty_segments_with_the_right_number_of_each(self):
        for risk, table in games.WHEEL_RISKS.items():
            layout = games.wheel_layout(risk)
            self.assertEqual(len(layout), games.WHEEL_SEGMENTS)
            for mult, count in table:
                self.assertEqual(layout.count(mult), count, (risk, mult))

    def test_the_same_multiplier_is_spread_round_the_wheel_not_bunched_up(self):
        for risk, table in games.WHEEL_RISKS.items():
            layout = games.wheel_layout(risk)
            for mult, count in table:
                if count < 2:
                    continue
                spots = [i for i, m in enumerate(layout) if m == mult]
                gaps = [(spots[(k + 1) % count] - spots[k]) % games.WHEEL_SEGMENTS for k in range(count)]
                self.assertGreaterEqual(min(gaps), games.WHEEL_SEGMENTS // count - 2, (risk, mult, gaps))

    def test_spinning_every_segment_through_the_real_code_returns_96_percent_of_the_bet(self):
        for risk in games.WHEEL_RISKS:
            total = 0.0
            for i in range(games.WHEEL_SEGMENTS):
                fresh_store()
                u = mk("player", weekly=1000)
                with mock.patch.object(games, "rand_below", pin(i)):
                    total += games.wheel(u, {"risk": risk, "amount": "100"})["payout"]
            self.assertAlmostEqual(total / games.WHEEL_SEGMENTS, 96.0, places=6, msg=risk)


class WheelSpins(Setup):
    def spin(self, index, risk="low", amount="10"):
        with mock.patch.object(games, "rand_below", pin(index)):
            return games.wheel(self.u, {"risk": risk, "amount": amount})

    def test_the_segment_the_server_picks_decides_the_payout(self):
        layout = games.wheel_layout("medium")
        i = layout.index(500)
        r = self.spin(i, "medium", "10")
        self.assertEqual((r["index"], r["mult"], r["payout"], r["win"]), (i, 5.0, 50.0, True))
        self.assertEqual(self.balance(), 1040.0)

    def test_the_activity_log_calls_it_wheel(self):
        self.spin(games.wheel_layout("low").index(200), "low", "10")
        self.assertEqual(self.u["activity"][0]["text"], "Wheel: won")

    def test_a_zero_segment_loses_the_stake(self):
        i = games.wheel_layout("low").index(0)
        r = self.spin(i, "low", "10")
        self.assertEqual((r["mult"], r["payout"], r["win"]), (0.0, 0.0, False))
        self.assertEqual(self.balance(), 990.0)
        self.assertEqual(self.u["history"][0]["game"], "wheel")

    def test_payouts_are_paid_down_to_the_cent(self):
        i = games.wheel_layout("low").index(110)
        r = self.spin(i, "low", "0.10")
        self.assertEqual(r["payout"], 0.11)
        r = self.spin(i, "low", "0.99")
        self.assertEqual(r["payout"], 1.08, "0.99 x 1.1 = 1.089, down to 1.08")
        self.assertTrue(books_balance(self.u))

    def test_a_bad_risk_or_amount_is_refused_and_nothing_is_taken(self):
        for body in ({"risk": "wild", "amount": "10"}, {"amount": "10"}, {"risk": "low", "amount": "99999"}, {"risk": "low", "amount": "0"}, {"risk": "low"}):
            self.assertEqual(err(games.wheel, self.u, body).status, 400, body)
        self.assertEqual(self.balance(), 1000.0)

    def test_practice_spins_stay_in_the_practice_wallet(self):
        demo = games.account_for(self.u, True)
        i = games.wheel_layout("risky").index(2400)
        with mock.patch.object(games, "rand_below", pin(i)):
            games.wheel(demo, {"risk": "risky", "amount": "100"})
        self.assertEqual(self.balance(), 1000.0)
        self.assertEqual(demo["balance"], games.DEMO_START - 100 + 2400.0)
        self.assertFalse(db()["feed"], "a practice win never reaches the big-wins board")

    def test_a_real_win_of_2x_or_more_reaches_the_big_wins_board(self):
        i = games.wheel_layout("high").index(1000)
        self.spin(i, "high", "10")
        self.assertEqual(db()["feed"][0]["game"], "wheel")
        self.assertEqual(db()["feed"][0]["mult"], 10.0)


# ---------------------------------------------------------------------------------------------------------------------
class RpsMaths(unittest.TestCase):
    def test_the_ladder_doubles_from_1_96(self):
        self.assertEqual(games.rps_ladder()[:4], [1.96, 3.92, 7.84, 15.68])
        self.assertEqual(len(games.rps_ladder()), games.RPS_MAX_WINS)

    def test_every_rung_returns_98_percent_when_each_round_is_a_fair_coin(self):
        for n in range(1, games.RPS_MAX_WINS + 1):
            self.assertEqual(Fraction(1, 2 ** n) * Fraction(games.rps_mult_x100(n), 100), Fraction(98, 100), n)

    def test_of_the_nine_ways_a_round_can_go_three_win_three_lose_three_draw(self):
        tally = {"win": 0, "lose": 0, "draw": 0}
        for pick in games.RPS_MOVES:
            for h, house in enumerate(games.RPS_MOVES):
                fresh_store()
                u = mk("player", weekly=1000)
                games.rps_start(u, {"amount": "10"})
                with mock.patch.object(games, "rand_below", pin(h)):
                    tally[games.rps_play(u, {"pick": pick})["result"]] += 1
        self.assertEqual(tally, {"win": 3, "lose": 3, "draw": 3})

    def test_the_winning_pairs_are_the_usual_ones(self):
        for pick, house in (("rock", "scissors"), ("scissors", "paper"), ("paper", "rock")):
            fresh_store()
            u = mk("player", weekly=1000)
            games.rps_start(u, {"amount": "10"})
            with mock.patch.object(games, "rand_below", pin(games.RPS_MOVES.index(house))):
                self.assertEqual(games.rps_play(u, {"pick": pick})["result"], "win", (pick, house))


class RpsRounds(Setup):
    def play(self, pick, house):
        with mock.patch.object(games, "rand_below", pin(games.RPS_MOVES.index(house))):
            return games.rps_play(self.u, {"pick": pick})

    def test_starting_takes_the_stake(self):
        r = games.rps_start(self.u, {"amount": "10"})
        self.assertEqual((self.balance(), r["wins"], r["mult"], r["next"]), (990.0, 0, 1.0, 1.96))

    def test_a_win_climbs_and_shows_what_is_next(self):
        games.rps_start(self.u, {"amount": "10"})
        r = self.play("rock", "scissors")
        self.assertEqual((r["result"], r["wins"], r["mult"], r["payoutNow"], r["next"], r["house"]), ("win", 1, 1.96, 19.6, 3.92, "scissors"))
        r = self.play("paper", "rock")
        self.assertEqual((r["wins"], r["mult"], r["payoutNow"], r["next"]), (2, 3.92, 39.2, 7.84))

    def test_the_activity_log_says_rock_paper_scissors_not_rps(self):
        games.rps_start(self.u, {"amount": "10"})
        self.play("rock", "paper")
        self.assertEqual(self.u["activity"][0]["text"], "Rock Paper Scissors: lost")

    def test_a_draw_is_played_again_and_costs_nothing(self):
        games.rps_start(self.u, {"amount": "10"})
        for _ in range(5):
            r = self.play("rock", "rock")
            self.assertEqual((r["result"], r["wins"]), ("draw", 0))
        self.assertEqual(self.balance(), 990.0)
        self.assertEqual(games.rps_state(self.u)["draws"], 5)
        self.assertEqual(self.play("rock", "scissors")["wins"], 1)

    def test_a_loss_ends_the_round_and_keeps_the_stake(self):
        games.rps_start(self.u, {"amount": "10"})
        self.play("rock", "scissors")
        r = self.play("rock", "paper")
        self.assertEqual((r["result"], r["finished"], r["payout"]), ("lose", True, 0.0))
        self.assertEqual(self.balance(), 990.0)
        self.assertNotIn("rps", db()["games"].get(self.u["id"], {}))
        self.assertEqual(self.u["history"][0]["game"], "rps")
        self.assertEqual(err(games.rps_play, self.u, {"pick": "rock"}).status, 400, "the round is over")

    def test_cashing_out_needs_a_win_and_pays_down_to_the_cent(self):
        games.rps_start(self.u, {"amount": "10.55"})
        self.assertEqual(err(games.rps_cashout, self.u).status, 400)
        self.play("rock", "scissors")
        self.play("rock", "scissors")
        r = games.rps_cashout(self.u)
        self.assertEqual(r["payout"], 41.35, "10.55 x 3.92 = 41.356, down to the cent")
        self.assertEqual(self.balance(), 1000.0 - 10.55 + 41.35)
        self.assertTrue(books_balance(self.u))

    def test_ten_wins_in_a_row_pay_out_by_themselves(self):
        games.rps_start(self.u, {"amount": "1"})
        for _ in range(games.RPS_MAX_WINS - 1):
            self.assertNotIn("finished", self.play("rock", "scissors"))
        r = self.play("rock", "scissors")
        self.assertTrue(r["finished"])
        self.assertEqual(r["payout"], 1003.52)
        self.assertNotIn("rps", db()["games"].get(self.u["id"], {}))

    def test_one_round_at_a_time_and_bad_picks_are_refused(self):
        games.rps_start(self.u, {"amount": "10"})
        self.assertEqual(err(games.rps_start, self.u, {"amount": "10"}).status, 400)
        self.assertEqual(err(games.rps_play, self.u, {"pick": "lizard"}).status, 400)
        self.assertEqual(err(games.rps_play, self.u, {}).status, 400)
        self.assertEqual(self.balance(), 990.0)

    def test_the_stake_in_play_counts_and_a_round_in_progress_is_found_again(self):
        games.rps_start(self.u, {"amount": "10"})
        self.play("rock", "scissors")
        self.assertEqual(games.escrow(self.u["id"]), 10.0)
        s = games.active_state(self.u)["rps"]
        self.assertEqual((s["wins"], s["bet"], s["next"]), (1, 10.0, 3.92))

    def test_practice_rounds_stay_in_the_practice_wallet(self):
        demo = games.account_for(self.u, True)
        games.rps_start(demo, {"amount": "100"})
        with mock.patch.object(games, "rand_below", pin(2)):
            games.rps_play(demo, {"pick": "rock"})
        games.rps_cashout(demo)
        self.assertEqual(self.balance(), 1000.0)
        self.assertEqual(db()["feed"], [])
        self.assertGreater(demo["balance"], 1000.0)


# ---------------------------------------------------------------------------------------------------------------------
class ThroughTheServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.data = {}
        store.load()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def person(self, name):
        a, b = Client(self.port), Client(self.port)
        a.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})
        b.call("POST", "/api/auth/login", {"username": name, "password": "secret123"})
        return a, b

    def test_meta_describes_all_three(self):
        a, _ = self.person("meta_p")
        st, m = a.call("GET", "/api/games/meta")
        self.assertEqual(st, 200)
        self.assertEqual(m["hilo"]["rtp"], 0.96)
        self.assertEqual(set(m["wheel"]["risks"]), {"low", "medium", "high", "risky"})
        self.assertEqual(len(m["wheel"]["risks"]["low"]["layout"]), 50)
        self.assertEqual(m["rps"]["ladder"][:4], [1.96, 3.92, 7.84, 15.68])

    def test_a_hilo_round_is_the_same_round_on_another_device_and_cannot_be_started_twice(self):
        phone, laptop = self.person("hilo_p")
        st, d = phone.call("POST", "/api/games/hilo/start", {"amount": 10})
        self.assertEqual(st, 200, d)
        seen = laptop.call("GET", "/api/games/state")[1]["hilo"]
        self.assertEqual((seen["id"], seen["card"]), (d["id"], d["card"]))
        self.assertEqual(laptop.call("POST", "/api/games/hilo/start", {"amount": 10})[0], 400)
        self.assertEqual(phone.call("POST", "/api/games/hilo/cashout")[0], 400, "no right guess yet")

    def test_the_wheel_pays_through_the_api(self):
        a, _ = self.person("wheel_p")
        before = a.call("GET", "/api/me")[1]["user"]["balance"]
        st, d = a.call("POST", "/api/games/wheel", {"risk": "low", "amount": 10})
        self.assertEqual(st, 200, d)
        self.assertAlmostEqual(d["user"]["balance"], before - 10 + d["payout"], places=2)
        self.assertEqual(a.call("POST", "/api/games/wheel", {"risk": "nope", "amount": 10})[0], 400)

    def test_a_rock_paper_scissors_round_can_be_played_until_it_ends(self):
        a, _ = self.person("rps_p")
        self.assertEqual(a.call("POST", "/api/games/rps/start", {"amount": 10})[0], 200)
        for _ in range(200):
            st, d = a.call("POST", "/api/games/rps/play", {"pick": "rock"})
            self.assertEqual(st, 200, d)
            if d.get("finished"):
                break
            if d["result"] == "win":
                self.assertEqual(a.call("POST", "/api/games/rps/cashout")[0], 200)
                break
        self.assertIsNone(a.call("GET", "/api/games/state")[1]["rps"])

    def test_you_must_be_logged_in(self):
        anon = Client(self.port)
        for path in ("/api/games/hilo/start", "/api/games/wheel", "/api/games/rps/start"):
            self.assertEqual(anon.call("POST", path, {"amount": 10})[0], 401)


if __name__ == "__main__":
    unittest.main()
