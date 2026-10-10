"""Coinflip, Dice, War, Mines, Moles and Tower. The random source is pinned so every outcome can be forced."""
import json
import math
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from backend import config, games, users                   # noqa: E402
from backend.store import store                            # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402
from tests.test_http import Client                         # noqa: E402


def tearDownModule():
    restore_store_path()


def mk(funds=1000.0):
    fresh_store()
    u = users.register("player", "secret123")
    u["balance"] = float(funds)
    return u


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def put_first(*wanted):
    """A shuffle that puts `wanted` at the front, like a lucky (or unlucky) draw."""
    def f(items):
        rest = [i for i in items if i not in wanted]
        items[:] = list(wanted) + rest
        return items
    return f


def stack(*cards):
    """A shuffle that makes the shoe deal exactly these cards, in this order (the shoe pops from the end)."""
    def f(shoe):
        shoe[-len(cards):] = list(reversed(cards))
        return shoe
    return f


def card(rank, suit):
    return {"r": rank, "s": suit}


class Coinflip(unittest.TestCase):
    def play(self, user, rolls, **body):
        rolls = iter(rolls)
        with mock.patch.object(games, "rand_below", lambda n: next(rolls)):
            return games.coinflip(user, {"amount": 10, **body})

    def test_classic_win_pays_198(self):
        u = mk()
        r = self.play(u, [0], side="heads")
        self.assertTrue(r["win"])
        self.assertEqual((r["payout"], r["mult"], r["results"]), (19.8, 1.98, ["heads"]))
        self.assertEqual(u["balance"], 1009.8)

    def test_classic_loss_costs_the_bet(self):
        u = mk()
        r = self.play(u, [1], side="heads")
        self.assertEqual((r["win"], r["payout"], r["results"]), (False, 0.0, ["tails"]))
        self.assertEqual(u["balance"], 990.0)

    def test_tails_side(self):
        u = mk()
        self.assertTrue(self.play(u, [1], side="tails")["win"])

    def test_target_streak_pays_the_compounded_multiplier(self):
        u = mk()
        r = self.play(u, [0, 0, 0], side="heads", mode="target", flips=3)
        self.assertEqual((r["win"], r["mult"], r["payout"]), (True, 7.92, 79.2))
        self.assertEqual(len(r["results"]), 3)

    def test_streak_stops_at_the_first_miss(self):
        u = mk()
        calls = []
        seq = iter([0, 1, 0, 0])
        with mock.patch.object(games, "rand_below", lambda n: calls.append(1) or next(seq)):
            r = games.coinflip(u, {"amount": 10, "side": "heads", "mode": "target", "flips": 4})
        self.assertFalse(r["win"])
        self.assertEqual((r["results"], len(calls)), (["heads", "tails"], 2))
        self.assertEqual(u["balance"], 990.0)

    def test_inputs_are_checked(self):
        u = mk(50)
        for body in ({"side": "edge"}, {"side": None}, {"side": "heads", "mode": "weird"},
                     {"side": "heads", "mode": "target", "flips": 0}, {"side": "heads", "mode": "target", "flips": 11},
                     {"side": "heads", "mode": "target", "flips": True}, {"side": "heads", "mode": "target", "flips": "3"},
                     {"side": "heads", "mode": "target"}):
            self.assertEqual(err(games.coinflip, u, {"amount": 5, **body}).status, 400, body)
        self.assertIn("minimum", err(games.coinflip, u, {"amount": 0.01, "side": "heads"}).message)
        self.assertIn("Not enough", err(games.coinflip, u, {"amount": 51, "side": "heads"}).message)
        self.assertEqual(u["balance"], 50.0)

    def test_return_to_player_is_99_percent_for_every_streak_length(self):
        for n in range(1, games.COIN_MAX_FLIPS + 1):
            rtp = games.coin_mult(n) / 2 ** n
            self.assertLessEqual(rtp, 0.99 + 1e-12)
            self.assertGreater(rtp, 0.99 - 0.01 / 2 ** n - 1e-12)


class Dice(unittest.TestCase):
    def roll(self, user, r, **body):
        with mock.patch.object(games, "rand_below", lambda n: r):
            return games.dice(user, {"amount": 10, **body})

    def test_odds_match_the_reference(self):
        self.assertEqual(games.dice_odds("over", 5050), (4950, 2.0))        # chance 49.50%, 2.0000x
        self.assertEqual(games.dice_odds("under", 5050), (5050, 1.9603))

    def test_roll_over_wins_on_the_threshold_itself(self):
        u = mk()
        self.assertTrue(self.roll(u, 5050, direction="over", target=50.5)["win"])
        self.assertFalse(self.roll(u, 5049, direction="over", target=50.5)["win"])

    def test_roll_under_loses_on_the_threshold(self):
        u = mk()
        self.assertTrue(self.roll(u, 5049, direction="under", target=50.5)["win"])
        self.assertFalse(self.roll(u, 5050, direction="under", target=50.5)["win"])

    def test_payout_and_balance(self):
        u = mk()
        r = self.roll(u, 9000, direction="over", target=50.5)
        self.assertEqual((r["payout"], r["mult"], r["chance"], r["roll"]), (20.0, 2.0, 49.5, 90.0))
        self.assertEqual(u["balance"], 1010.0)
        r = self.roll(u, 100, direction="over", target=50.5)
        self.assertEqual((r["win"], r["payout"]), (False, 0.0))
        self.assertEqual(u["balance"], 1000.0)

    def test_extremes(self):
        u = mk()
        self.assertEqual(games.dice_odds("over", 9999), (1, 9900.0))         # 0.01% chance pays 9900x
        self.assertEqual(games.dice_odds("under", 9800)[0], 9800)            # 98% is the most likely allowed
        for direction, target in (("over", 100.0), ("over", 1.99), ("under", 98.01), ("under", 0.0), ("under", 0.004)):
            self.assertEqual(err(games.dice, u, {"amount": 5, "direction": direction, "target": target}).status, 400, (direction, target))
        self.assertEqual(err(games.dice, u, {"amount": 5, "direction": "sideways", "target": 50}).status, 400)
        self.assertEqual(err(games.dice, u, {"amount": 5, "direction": "over", "target": "nan"}).status, 400)
        self.assertEqual(u["balance"], 1000.0)

    def test_return_to_player_is_99_percent_at_every_chance(self):
        for count in range(1, games.DICE_MAX_CHANCE + 1):
            mult = games.dice_odds("under", count)[1]
            self.assertLessEqual(count / 10000 * mult, 0.99 + 1e-9)
            self.assertGreater(count / 10000 * mult, 0.99 - 1e-4 * count / 10000 - 1e-9)


class War(unittest.TestCase):
    def deal(self, user, cards, **body):
        with mock.patch.object(games, "shuffle", stack(*cards)):
            return games.war(user, {"amount": 10, **body})

    def test_higher_card_wins_even_money(self):
        u = mk()
        r = self.deal(u, [card("K", "S"), card("5", "H")])
        self.assertEqual((r["outcome"], r["payout"], r["wagered"]), ("win", 20.0, 10.0))
        self.assertEqual(u["balance"], 1010.0)

    def test_aces_are_high(self):
        u = mk()
        self.assertEqual(self.deal(u, [card("A", "S"), card("K", "H")])["outcome"], "win")

    def test_lower_card_loses(self):
        u = mk()
        r = self.deal(u, [card("3", "D"), card("9", "C")])
        self.assertEqual((r["outcome"], r["payout"]), ("lose", 0.0))
        self.assertEqual(u["balance"], 990.0)

    def test_tie_goes_to_war_and_a_winning_war_pays_the_original_bet_only(self):
        u = mk()
        r = self.deal(u, [card("7", "S"), card("7", "H"), card("9", "D"), card("4", "C")])
        self.assertEqual((r["outcome"], r["payout"], r["wagered"]), ("warwin", 30.0, 20.0))
        self.assertTrue(r["tie"])
        self.assertEqual(r["war"]["raise"], 10.0)
        self.assertEqual(u["balance"], 1010.0)

    def test_a_losing_war_loses_bet_and_raise(self):
        u = mk()
        r = self.deal(u, [card("7", "S"), card("7", "H"), card("2", "D"), card("Q", "C")])
        self.assertEqual((r["outcome"], r["payout"], r["wagered"]), ("warlose", 0.0, 20.0))
        self.assertEqual(u["balance"], 980.0)

    def test_a_tie_in_the_war_round_counts_as_a_win(self):
        u = mk()
        r = self.deal(u, [card("7", "S"), card("7", "H"), card("J", "D"), card("J", "C")])
        self.assertEqual(r["outcome"], "warwin")

    def test_cannot_afford_the_raise_means_half_back(self):
        u = mk(10)                                   # the whole balance is on the table
        r = self.deal(u, [card("7", "S"), card("7", "H")])
        self.assertEqual((r["outcome"], r["payout"], r["wagered"]), ("surrender", 5.0, 10.0))
        self.assertEqual(u["balance"], 5.0)

    def test_tie_side_bet_pays_12_to_1_and_coloured_tie_pays_26_to_1(self):
        u = mk()
        # 7 of spades vs 7 of clubs: same rank, same colour, so both side bets win
        r = self.deal(u, [card("7", "S"), card("7", "C"), card("9", "D"), card("4", "C")], tie=10, colouredTie=5)
        self.assertEqual((r["tiePayout"], r["colouredTiePayout"]), (130.0, 135.0))
        self.assertEqual(r["payout"], 30.0 + 130.0 + 135.0)
        self.assertEqual(r["wagered"], 10 + 10 + 5 + 10)
        self.assertEqual(u["balance"], 1000 - 35 + 295)

    def test_a_tie_of_different_colours_wins_only_the_plain_tie_bet(self):
        u = mk()
        r = self.deal(u, [card("7", "S"), card("7", "H"), card("2", "D"), card("Q", "C")], tie=10, colouredTie=5)
        self.assertEqual((r["tiePayout"], r["colouredTiePayout"], r["colouredTie"]), (130.0, 0.0, False))

    def test_side_bets_lose_when_there_is_no_tie(self):
        u = mk()
        r = self.deal(u, [card("K", "S"), card("5", "H")], tie=10, colouredTie=5)
        self.assertEqual((r["payout"], r["tiePayout"], r["wagered"]), (20.0, 0.0, 25.0))
        self.assertEqual(u["balance"], 1000 - 25 + 20)

    def test_funds_and_minimums(self):
        u = mk(20)
        self.assertIn("Not enough", err(games.war, u, {"amount": 10, "tie": 10, "colouredTie": 5}).message)
        self.assertIn("minimum", err(games.war, u, {"amount": 10, "tie": 0.05}).message)
        self.assertEqual(err(games.war, u, {"amount": 10, "tie": "abc"}).status, 400)
        self.assertEqual(u["balance"], 20.0)

    def test_a_shoe_has_six_decks(self):
        seen = {}

        def look(shoe):
            seen["n"] = len(shoe)
            return shoe
        u = mk()
        with mock.patch.object(games, "shuffle", look):
            games.war(u, {"amount": 1})
        self.assertEqual(seen["n"], 312)


class Mines(unittest.TestCase):
    def start(self, user, mines_at, size=25, bet=10):
        with mock.patch.object(games, "shuffle", put_first(*mines_at)):
            return games.mines_start(user, {"amount": bet, "size": size, "mines": len(mines_at)})

    def test_multipliers(self):
        self.assertEqual(games.mines_mult(25, 3, 0), 1.0)
        self.assertEqual(games.mines_mult(25, 3, 1), 1.12)          # 0.99 x 25/22
        self.assertEqual(games.mines_mult(25, 3, 2), 1.28)
        self.assertEqual(games.mines_mult(25, 24, 1), 24.75)
        self.assertEqual(len(games.mines_table(25, 3)), 23)
        self.assertEqual(len(games.mines_table(64, 1)), 64)

    def test_return_to_player_is_99_percent_everywhere(self):
        for size in games.MINES_SIZES:
            for mines in range(1, size):
                for k in range(1, size - mines + 1):
                    p = math.comb(size - mines, k) / math.comb(size, k)
                    m = games.mines_mult(size, mines, k)
                    self.assertLessEqual(p * m, 0.99 + 1e-9, (size, mines, k))
                    self.assertGreater(p * m, 0.99 - 0.01 * p - 1e-9, (size, mines, k))

    def test_safe_picks_raise_the_multiplier_and_cashout_pays(self):
        u = mk()
        s = self.start(u, [0, 1, 2])
        self.assertEqual((u["balance"], s["status"], s["picked"]), (990.0, "active", []))
        s = games.mines_pick(u, {"tile": 5})
        s = games.mines_pick(u, {"tile": 9})
        self.assertEqual((s["mult"], s["picked"], s["payoutNow"]), (1.28, [5, 9], 12.8))
        out = games.mines_cashout(u)
        self.assertEqual((out["payout"], out["status"], out["finished"]), (12.8, "cashed", True))
        self.assertEqual(u["balance"], 1002.8)
        self.assertIsNone(games.mines_state(u))

    def test_hitting_a_mine_loses_and_reveals_the_board(self):
        u = mk()
        self.start(u, [0, 7, 13])
        games.mines_pick(u, {"tile": 4})
        r = games.mines_pick(u, {"tile": 7})
        self.assertEqual((r["crashed"], r["hit"], r["payout"], r["mineIndices"]), (True, 7, 0.0, [0, 7, 13]))
        self.assertEqual(u["balance"], 990.0)
        self.assertIsNone(games.mines_state(u))
        self.assertEqual(err(games.mines_pick, u, {"tile": 3}).status, 400)

    def test_the_mines_are_never_sent_while_the_round_is_live(self):
        u = mk()
        start = self.start(u, [3, 4, 5])
        pick = games.mines_pick(u, {"tile": 20})
        for payload in (start, pick, games.mines_state(u), games.active_state(u)["mines"]):
            self.assertNotIn("mineIndices", payload)
            self.assertNotIn("board", payload)
            self.assertNotIn("3, 4, 5", json.dumps(payload))

    def test_cannot_cash_out_before_opening_a_tile(self):
        u = mk()
        self.start(u, [0])
        self.assertIn("at least one", err(games.mines_cashout, u).message)

    def test_rules_are_enforced(self):
        u = mk()
        self.start(u, [0, 1])
        self.assertIn("already have", err(games.mines_start, u, {"amount": 1, "size": 25, "mines": 3}).message)
        games.mines_pick(u, {"tile": 10})
        for tile in (10, -1, 25, "3", 2.5, True, None):
            self.assertEqual(err(games.mines_pick, u, {"tile": tile}).status, 400, tile)

    def test_bad_setups(self):
        u = mk()
        for body in ({"size": 30, "mines": 3}, {"size": 25, "mines": 0}, {"size": 25, "mines": 25}, {"size": 25, "mines": True},
                     {"size": True, "mines": 3}, {"size": 25, "mines": "3"}):
            self.assertEqual(err(games.mines_start, u, {"amount": 5, **body}).status, 400, body)
        self.assertEqual(err(games.mines_pick, u, {"tile": 1}).status, 400)         # no round
        self.assertEqual(err(games.mines_cashout, u).status, 400)
        self.assertEqual(u["balance"], 1000.0)

    def test_clearing_the_board_cashes_out_by_itself(self):
        u = mk()
        self.start(u, list(range(24)))                    # 24 mines, one safe tile
        r = games.mines_pick(u, {"tile": 24})
        self.assertEqual((r["finished"], r["payout"], r["status"]), (True, 247.5, "cashed"))
        self.assertEqual(u["balance"], 1237.5)

    def test_big_grids_and_a_round_survives_a_save(self):
        u = mk()
        s = self.start(u, [0], size=64)
        self.assertEqual(s["size"], 64)
        json.dumps(store.data)                            # the live round must be storable
        self.assertEqual(games.mines_state(u)["id"], s["id"])


class Moles(unittest.TestCase):
    def start(self, user, moles_at, bet=10):
        with mock.patch.object(games, "shuffle", put_first(*moles_at)):
            return games.moles_start(user, {"amount": bet, "moles": len(moles_at)})

    def whack(self, user, hole, moles_at):
        with mock.patch.object(games, "shuffle", put_first(*moles_at)):
            return games.moles_pick(user, {"hole": hole})

    def test_multipliers_match_the_reference(self):
        self.assertEqual(games.moles_mult(3, 1), 2.24)                    # 0.96 x 7/3
        self.assertEqual(games.moles_mult(3, 2), 5.22)
        self.assertEqual(games.moles_table(3)[:3], [1.0, 2.24, 5.22])

    def test_return_to_player_is_96_percent(self):
        for moles in range(1, games.MOLES_HOLES):
            for k in range(1, games.moles_max_steps(moles) + 1):
                p = (moles / games.MOLES_HOLES) ** k
                m = games.moles_mult(moles, k)
                self.assertLessEqual(p * m, 0.96 + 1e-9)
                self.assertGreater(p * m, 0.96 - 0.01 * p - 1e-9)

    def test_the_multiplier_never_goes_past_a_million(self):
        for moles in range(1, games.MOLES_HOLES):
            self.assertLessEqual(games.moles_table(moles)[-1], 1_000_000)
            self.assertLessEqual(games.moles_max_steps(moles), games.MOLES_MAX_STEPS)

    def test_a_hit_keeps_going_and_cashout_pays(self):
        u = mk()
        self.start(u, [2, 4, 6])
        r = self.whack(u, 4, [2, 4, 6])
        self.assertEqual((r["hit"], r["crashed"], r["popped"], r["hits"], r["mult"]), (True, False, [2, 4, 6], 1, 2.24))
        self.assertEqual(r["nextMult"], 5.22)
        out = games.moles_cashout(u)
        self.assertEqual((out["payout"], out["finished"]), (22.4, True))
        self.assertEqual(u["balance"], 1012.4)

    def test_a_miss_loses_and_shows_where_the_moles_were(self):
        u = mk()
        self.start(u, [2, 4, 6])
        r = self.whack(u, 0, [2, 4, 6])
        self.assertEqual((r["hit"], r["crashed"], r["popped"], r["payout"]), (False, True, [2, 4, 6], 0.0))
        self.assertEqual(u["balance"], 990.0)
        self.assertIsNone(games.moles_state(u))

    def test_cannot_cash_out_with_no_hits(self):
        u = mk()
        self.start(u, [1])
        self.assertIn("at least one", err(games.moles_cashout, u).message)

    def test_the_streak_ends_by_itself_at_the_cap(self):
        u = mk()
        self.start(u, [3])                                  # one mole: chance 1/7 each round
        cap = games.moles_max_steps(1)
        for i in range(cap):
            r = self.whack(u, 3, [3])
        self.assertEqual((r["finished"], r["hits"]), (True, cap))
        self.assertAlmostEqual(r["payout"], games.moles_mult(1, cap) * 10, places=2)
        self.assertIsNone(games.moles_state(u))

    def test_bad_input(self):
        u = mk()
        for moles in (0, 7, True, "3", None):
            self.assertEqual(err(games.moles_start, u, {"amount": 5, "moles": moles}).status, 400, moles)
        self.start(u, [1, 2])
        self.assertIn("already have", err(games.moles_start, u, {"amount": 1, "moles": 2}).message)
        for hole in (-1, 7, "2", True, None, 1.5):
            self.assertEqual(err(games.moles_pick, u, {"hole": hole}).status, 400, hole)


class Tower(unittest.TestCase):
    def start(self, user, risk="easy", traps_at=(0,), bet=10):
        with mock.patch.object(games, "shuffle", put_first(*traps_at)):
            return games.tower_start(user, {"amount": bet, "risk": risk})

    def test_multipliers_match_the_reference(self):
        self.assertEqual(games.tower_mult("easy", 1), 1.28)                 # 0.96 / (3/4)
        self.assertEqual([games.tower_mult(r, 1) for r in ("medium", "hard", "expert", "master")], [1.44, 1.92, 2.88, 3.84])
        self.assertEqual(games.tower_mult("easy", 8), 9.58)
        self.assertEqual(len(games.tower_table("easy")), games.TOWER_ROWS + 1)

    def test_return_to_player_is_96_percent(self):
        for risk, (cols, traps) in games.TOWER_RISK.items():
            for k in range(1, games.TOWER_ROWS + 1):
                p = ((cols - traps) / cols) ** k
                m = games.tower_mult(risk, k)
                self.assertLessEqual(p * m, 0.96 + 1e-9, (risk, k))
                self.assertGreater(p * m, 0.96 - 0.01 * p - 1e-9, (risk, k))

    def test_climb_and_cash_out(self):
        u = mk()
        s = self.start(u, "easy", traps_at=(0,))
        self.assertEqual((s["cols"], s["traps"], s["rows"], u["balance"]), (4, 1, 8, 990.0))
        games.tower_pick(u, {"tile": 2})
        r = games.tower_pick(u, {"tile": 3})
        self.assertEqual((r["step"], r["mult"], r["picks"]), (2, 1.7, [2, 3]))
        out = games.tower_cashout(u)
        self.assertEqual((out["payout"], out["finished"]), (17.0, True))
        self.assertEqual(u["balance"], 1007.0)

    def test_falling_loses_and_shows_the_traps(self):
        u = mk()
        self.start(u, "hard", traps_at=(1,))                       # two tiles per row, one trap
        games.tower_pick(u, {"tile": 0})
        r = games.tower_pick(u, {"tile": 1})
        self.assertEqual((r["crashed"], r["payout"]), (True, 0.0))
        self.assertEqual(r["layout"], [[1]] * 8)
        self.assertEqual(u["balance"], 990.0)
        self.assertIsNone(games.tower_state(u))

    def test_the_traps_are_hidden_while_climbing(self):
        u = mk()
        start = self.start(u, "expert", traps_at=(0, 1))
        pick = games.tower_pick(u, {"tile": 2})
        for payload in (start, pick, games.tower_state(u), games.active_state(u)["tower"]):
            self.assertNotIn("layout", payload)

    def test_reaching_the_top_cashes_out_by_itself(self):
        u = mk()
        self.start(u, "medium", traps_at=(0,))
        for _ in range(games.TOWER_ROWS):
            r = games.tower_pick(u, {"tile": 1})
        self.assertEqual((r["finished"], r["status"]), (True, "cashed"))
        self.assertEqual(r["payout"], round(10 * games.tower_mult("medium", 8), 2))

    def test_cannot_cash_out_before_climbing(self):
        u = mk()
        self.start(u)
        self.assertIn("at least one", err(games.tower_cashout, u).message)

    def test_bad_input(self):
        u = mk()
        self.assertEqual(err(games.tower_start, u, {"amount": 5, "risk": "insane"}).status, 400)
        self.start(u, "easy", traps_at=(0,))
        self.assertIn("already have", err(games.tower_start, u, {"amount": 1, "risk": "easy"}).message)
        for tile in (-1, 4, "1", True, None):
            self.assertEqual(err(games.tower_pick, u, {"tile": tile}).status, 400, tile)


class Fairness(unittest.TestCase):
    """The real random source over many rounds: payouts should land near the promised return."""
    N = 30000

    def rtp(self, play, band):
        u = mk(1e12)
        before = u["balance"]
        for _ in range(self.N):
            play(u)
        back = (u["balance"] - before + self.N) / self.N
        self.assertGreater(back, band[0])
        self.assertLess(back, band[1])

    def test_coinflip(self):
        self.rtp(lambda u: games.coinflip(u, {"amount": 1, "side": "heads"}), (0.955, 1.025))

    def test_dice(self):
        self.rtp(lambda u: games.dice(u, {"amount": 1, "direction": "over", "target": 50.5}), (0.955, 1.025))

    def test_mines_cash_out_after_three(self):
        def play(u):
            games.mines_start(u, {"amount": 1, "size": 25, "mines": 3})
            for t in range(3):
                if games.mines_pick(u, {"tile": t}).get("crashed"):
                    return
            games.mines_cashout(u)
        self.rtp(play, (0.955, 1.025))

    def test_moles_one_round(self):
        def play(u):
            games.moles_start(u, {"amount": 1, "moles": 3})
            if not games.moles_pick(u, {"hole": 0}).get("crashed"):
                games.moles_cashout(u)
        self.rtp(play, (0.93, 1.0))

    def test_tower_two_rows(self):
        def play(u):
            games.tower_start(u, {"amount": 1, "risk": "easy"})
            for _ in range(2):
                if games.tower_pick(u, {"tile": 0}).get("crashed"):
                    return
            games.tower_cashout(u)
        self.rtp(play, (0.93, 1.0))

    def test_war_main_bet(self):
        self.N = 4000          # each hand shuffles six decks, so keep it short; the band only catches gross mistakes
        self.rtp(lambda u: games.war(u, {"amount": 1}), (0.90, 1.05))


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.c = Client(cls.port)
        assert cls.c.call("POST", "/api/auth/register", {"username": "gamer", "password": "secret123"})[0] == 200

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        restore_store_path()

    def test_you_must_be_logged_in(self):
        anon = Client(self.port)
        for path in ("/api/games/dice", "/api/games/mines/start", "/api/games/tower/pick", "/api/games/war"):
            self.assertEqual(anon.call("POST", path, {"amount": 1})[0], 401, path)

    def test_meta_lists_every_table(self):
        st, d = self.c.call("GET", "/api/games/meta")
        self.assertEqual(st, 200)
        self.assertEqual(d["moles"]["tables"]["3"][1], 2.24)
        self.assertEqual(d["tower"]["risks"]["easy"]["mults"][1], 1.28)
        self.assertEqual(d["mines"]["sizes"], [25, 36, 49, 64])
        self.assertEqual(d["coinflip"]["mults"][0], 1.98)
        self.assertEqual(d["war"], {"tiePays": 12, "colouredTiePays": 26})

    def test_mines_table_endpoint(self):
        st, d = self.c.call("GET", "/api/games/mines/table?size=25&mines=3")
        self.assertEqual((st, d["mults"][1]), (200, 1.12))
        self.assertEqual(self.c.call("GET", "/api/games/mines/table?size=26&mines=3")[0], 400)
        self.assertEqual(self.c.call("GET", "/api/games/mines/table?size=abc&mines=3")[0], 400)

    def test_single_shot_games(self):
        for path, body in (("/api/games/coinflip", {"amount": 1, "side": "tails"}),
                           ("/api/games/dice", {"amount": 1, "direction": "under", "target": 60}),
                           ("/api/games/war", {"amount": 1, "tie": 1, "colouredTie": 1})):
            st, d = self.c.call("POST", path, body)
            self.assertEqual(st, 200, path)
            self.assertIn("user", d)
            self.assertAlmostEqual(d["user"]["balance"], d["balance"], places=2)

    def test_a_mines_round_over_the_wire(self):
        st, d = self.c.call("POST", "/api/games/mines/start", {"amount": 1, "size": 25, "mines": 1})
        self.assertEqual(st, 200)
        self.assertNotIn("mineIndices", d)
        st, state = self.c.call("GET", "/api/games/state")
        self.assertEqual(state["mines"]["id"], d["id"])
        for tile in range(25):
            st, d = self.c.call("POST", "/api/games/mines/pick", {"tile": tile})
            self.assertEqual(st, 200)
            if d.get("crashed") or d.get("finished"):
                break
        self.assertIn("mineIndices", d)
        self.assertEqual(self.c.call("POST", "/api/games/mines/cashout", {})[0], 400)       # round is over
        self.assertIsNone(self.c.call("GET", "/api/games/state")[1]["mines"])

    def test_tower_and_moles_over_the_wire(self):
        st, d = self.c.call("POST", "/api/games/tower/start", {"amount": 1, "risk": "master"})
        self.assertEqual((st, d["cols"], d["traps"]), (200, 4, 3))
        st, d = self.c.call("POST", "/api/games/tower/pick", {"tile": 0})
        self.assertEqual(st, 200)
        if not d["crashed"]:
            self.assertEqual(self.c.call("POST", "/api/games/tower/cashout", {})[0], 200)
        st, d = self.c.call("POST", "/api/games/moles/start", {"amount": 1, "moles": 6})
        self.assertEqual((st, d["holes"]), (200, 7))
        st, d = self.c.call("POST", "/api/games/moles/pick", {"hole": 0})
        self.assertEqual(st, 200)
        self.assertEqual(len(d["popped"]), 6)
        if not d["crashed"]:
            self.assertEqual(self.c.call("POST", "/api/games/moles/cashout", {})[0], 200)


if __name__ == "__main__":
    unittest.main()
