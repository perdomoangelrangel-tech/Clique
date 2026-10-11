"""Roulette odds: the maths is exact for every bet, the payouts are right to the cent, and the real random source is fair.

European wheel (one zero). Every bet on it returns 36/37 of what is staked, on average: 97.3%, the figure the lobby shows.
"""
import json
import os
import random
import re
import sys
import unittest
from fractions import Fraction
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config, games, users                       # noqa: E402
from backend.store import store                                 # noqa: E402
from backend.util import ApiError, rand_below                   # noqa: E402
from tests.helpers import fresh_store                           # noqa: E402

# Written out by hand here, not borrowed from the game, so the game is checked against something independent.
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK = set(range(1, 37)) - RED
# bet -> (numbers that win, total paid back per $1 staked when it wins, stake included)
BETS = {("straight", n): ({n}, 36) for n in range(37)}
BETS.update({
    ("red", None): (RED, 2), ("black", None): (BLACK, 2),
    ("odd", None): ({n for n in range(1, 37) if n % 2 == 1}, 2), ("even", None): ({n for n in range(1, 37) if n % 2 == 0}, 2),
    ("low", None): (set(range(1, 19)), 2), ("high", None): (set(range(19, 37)), 2),
    ("dozen", 1): (set(range(1, 13)), 3), ("dozen", 2): (set(range(13, 25)), 3), ("dozen", 3): (set(range(25, 37)), 3),
    ("column", 1): (set(range(1, 37, 3)), 3), ("column", 2): (set(range(2, 37, 3)), 3), ("column", 3): (set(range(3, 37, 3)), 3),
})


def chip(kind, value, amount):
    c = {"type": kind, "amount": amount}
    if value is not None:
        c["value"] = value
    return c


class TheMathIsExact(unittest.TestCase):
    def test_every_bet_returns_exactly_36_over_37(self):
        self.assertEqual(len(BETS), 49)
        for (kind, value), (_, pays) in BETS.items():
            wins = Fraction(0)
            for n in range(37):
                ok, mult = games._roulette_wins(kind, value, n)
                if ok:
                    self.assertEqual(mult, pays, f"{kind} {value} pays {mult} on {n}")
                    wins += mult
            self.assertEqual(wins / 37, Fraction(36, 37), f"{kind} {value}")

    def test_the_game_agrees_with_an_independent_table_for_every_bet_and_number(self):
        for (kind, value), (numbers, pays) in BETS.items():
            for n in range(37):
                ok, mult = games._roulette_wins(kind, value, n)
                self.assertEqual(ok, n in numbers, f"{kind} {value} on {n}")
                if ok:                                  # what a losing bet "would have paid" is never used
                    self.assertEqual(mult, pays, f"{kind} {value} on {n}")

    def test_the_wheel_has_the_standard_colours(self):
        self.assertEqual(games.REDS, RED)
        self.assertEqual((len(RED), len(BLACK)), (18, 18))

    def test_zero_beats_every_outside_bet(self):
        for kind in ("red", "black", "odd", "even", "low", "high"):
            self.assertEqual(games._roulette_wins(kind, None, 0), (False, 0))
        for kind in ("dozen", "column"):
            for value in (1, 2, 3):
                self.assertFalse(games._roulette_wins(kind, value, 0)[0])

    def test_what_the_lobby_promises_matches_the_maths(self):
        with open(os.path.join(config.STATIC_DIR, "js", "gamelist.js"), encoding="utf-8") as f:
            text = f.read()
        block = text[text.index("id: 'roulette'"):]
        block = block[:block.index("},\n")] if "},\n" in block else block
        self.assertIn(f"rtp: '{36 / 37 * 100:.1f}%'", block)
        self.assertIn("paga 35 a 1", block)          # 36 back including the stake
        self.assertIn("2 a 1", block)
        self.assertIn("1 a 1", block)
        # the lobby text is a Spanish key (static/js/i18n.js); its English must promise the same
        with open(os.path.join(config.STATIC_DIR, "i18n", "en.json"), encoding="utf-8") as f:
            info = json.load(f)[re.search(r"info: '([^']*)'", block).group(1)]
        self.assertIn("pays 35 to 1", info)
        self.assertIn("2 to 1", info)
        self.assertIn("1 to 1", info)


class PayoutsAreRightToTheCent(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = users.register("spinner", "secret123")
        self.u["balance"] = 1_000_000.0

    def spin(self, n, bets):
        with mock.patch.object(games, "rand_below", return_value=n) as rb:
            r = games.roulette(self.u, {"bets": bets})
        rb.assert_called_once_with(37)               # one number is drawn, from 0 to 36, whatever was bet
        return r

    def test_one_chip_on_every_bet_for_every_number(self):
        for (kind, value), (numbers, pays) in BETS.items():
            for n in range(37):
                before = self.u["balance"]
                r = self.spin(n, [chip(kind, value, 2)])
                expected = 2 * pays if n in numbers else 0
                self.assertEqual(r["number"], n)
                self.assertEqual(r["payout"], expected, f"{kind} {value} on {n}")
                self.assertEqual(round(self.u["balance"] - before, 2), expected - 2)
                self.assertEqual(len(r["wins"]), 1 if expected else 0)

    def test_the_colour_reported_for_each_number(self):
        for n in range(37):
            colour = "green" if n == 0 else ("red" if n in RED else "black")
            self.assertEqual(self.spin(n, [chip("red", None, 1)])["color"], colour)

    def test_many_chips_with_odd_cents_balance_to_the_cent(self):
        rng = random.Random(2024)
        keys = list(BETS)
        for _ in range(400):
            n = rng.randrange(37)
            picked = [rng.choice(keys) for _ in range(rng.randint(1, 12))]
            amounts = [round(rng.choice([0.1, 0.15, 0.33, 0.5, 1.07, 2.5, 7.77, 19.99, 123.45]), 2) for _ in picked]
            bets = [chip(k, v, a) for (k, v), a in zip(picked, amounts)]
            expected = round(sum(round(a * BETS[(k, v)][1], 2) for (k, v), a in zip(picked, amounts) if n in BETS[(k, v)][0]), 2)
            before = self.u["balance"]
            r = self.spin(n, bets)
            self.assertEqual(r["total"], round(sum(amounts), 2))
            self.assertEqual(r["payout"], expected)
            self.assertEqual(round(self.u["balance"] - before, 2), round(expected - sum(amounts), 2))
            self.assertAlmostEqual(r["balance"], self.u["balance"], places=2)

    def test_the_smallest_chip_pays_the_exact_amount(self):
        self.assertEqual(self.spin(17, [chip("straight", 17, 0.1)])["payout"], 3.6)

    def test_the_most_chips_allowed(self):
        r = self.spin(5, [chip("straight", i % 37, 0.1) for i in range(120)])
        self.assertEqual(r["total"], 12.0)
        self.assertEqual(r["payout"], round(0.1 * 36 * len([i for i in range(120) if i % 37 == 5]), 2))


class NothingIsDrawnUntilYouSpin(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = users.register("careful", "secret123")

    def test_the_game_state_endpoints_never_draw_a_number(self):
        with mock.patch.object(games, "rand_below") as rb, mock.patch.object(games, "rand_unit") as ru:
            games.active_state(self.u)
        rb.assert_not_called()
        ru.assert_not_called()

    def test_roulette_keeps_no_round_between_spins(self):
        self.assertNotIn("roulette", games.active_state(self.u))
        self.assertNotIn("roulette", games._games(self.u))

    def test_the_answer_holds_only_the_finished_spin(self):
        with mock.patch.object(games, "rand_below", return_value=3):
            r = games.roulette(self.u, {"bets": [chip("red", None, 1)]})
        self.assertEqual(set(r), {"number", "color", "payout", "total", "wins", "balance"})


class BadBetsChangeNothing(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = users.register("sloppy", "secret123")

    def refused(self, body):
        before = (self.u["balance"], json.dumps(self.u.get("stats", {}), sort_keys=True), len(store.data.get("feed", [])))
        with mock.patch.object(games, "rand_below") as rb:
            with self.assertRaises(ApiError, msg=repr(body)):
                games.roulette(self.u, body)
        rb.assert_not_called()
        self.assertEqual((self.u["balance"], json.dumps(self.u.get("stats", {}), sort_keys=True), len(store.data.get("feed", []))), before)

    def test_refused_bets(self):
        bad = [
            {}, {"bets": []}, {"bets": "red"}, {"bets": None},
            {"bets": [chip("red", None, 1)] * 121},
            {"bets": [chip("blue", None, 1)]},
            {"bets": [chip("straight", 37, 1)]}, {"bets": [chip("straight", -1, 1)]}, {"bets": [chip("straight", "7", 1)]},
            {"bets": [chip("straight", 7.5, 1)]}, {"bets": [chip("straight", None, 1)]},
            {"bets": [chip("dozen", 4, 1)]}, {"bets": [chip("dozen", 0, 1)]}, {"bets": [chip("column", 0, 1)]},
            {"bets": [chip("red", None, 0.05)]}, {"bets": [chip("red", None, 0)]}, {"bets": [chip("red", None, -5)]},
            {"bets": [chip("red", None, "lots")]}, {"bets": [chip("red", None, None)]},
            {"bets": [chip("red", None, 1_000_001)]},                          # more than the account holds
            {"bets": [chip("red", None, 600), chip("black", None, 600)]},      # each fine alone, too much together
            {"bets": [chip("red", None, 1), chip("straight", 99, 1)]},         # one bad chip spoils the whole spin
            {"bets": [5]}, {"bets": ["red"]}, {"bets": [None]}, {"bets": [[1, 2]]},
        ]
        for body in bad:
            self.refused(body)


class TheRealRandomSourceIsFair(unittest.TestCase):
    def test_every_pocket_comes_up_equally_often(self):
        spins = 74_000
        counts = [0] * 37
        for _ in range(spins):
            counts[rand_below(37)] += 1
        expected = spins / 37
        chi2 = sum((c - expected) ** 2 / expected for c in counts)
        # 36 degrees of freedom: this limit is crossed by chance about 2 times in 100,000
        self.assertLess(chi2, 80, f"chi-square {chi2:.1f}")
        self.assertEqual(sum(counts), spins)
        self.assertTrue(all(c > 0 for c in counts))

    def test_playing_through_the_game_returns_about_97_3_percent_and_uses_every_pocket_evenly(self):
        fresh_store()
        u = users.register("grinder", "secret123")
        u["balance"] = 1e9
        spins, stake = 37_000, 1.0
        paid, counts = 0.0, [0] * 37
        for _ in range(spins):
            r = games.roulette(u, {"bets": [chip("red", None, stake)]})
            paid += r["payout"]
            self.assertIn(r["number"], range(37))                # only 0 to 36 ever comes up
            counts[r["number"]] += 1
        rtp = paid / (spins * stake)
        # one spin has a spread of about 1.0, so 37,000 spins pin the average to about 0.005: 0.03 is five of those
        self.assertAlmostEqual(rtp, 36 / 37, delta=0.03, msg=f"returned {rtp:.4f}")
        expected = spins / 37
        chi2 = sum((c - expected) ** 2 / expected for c in counts)
        self.assertLess(chi2, 80, f"chi-square {chi2:.1f}")      # 36 degrees of freedom: chance of a false alarm ~2 in 100,000
        self.assertTrue(all(c > 0 for c in counts))

    def test_no_pattern_between_one_spin_and_the_next(self):
        fresh_store()
        draws = [rand_below(37) for _ in range(60_000)]
        same_as_last = sum(1 for a, b in zip(draws, draws[1:]) if a == b)
        n = len(draws) - 1
        # the chance two spins in a row land on the same number is 1/37
        self.assertLess(abs(same_as_last - n / 37), 5 * (n * (1 / 37) * (36 / 37)) ** 0.5)


if __name__ == "__main__":
    unittest.main()
