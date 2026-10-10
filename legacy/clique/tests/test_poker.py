"""Texas Hold'em: hand ranking, the betting rules, pots, timers, tables, votes and real money."""
import json
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import markets, poker, users                  # noqa: E402
from backend.store import db                               # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402

NOW = 1_000_000


def tearDownModule():
    restore_store_path()


def mk(name, funds=1000.0):
    u = users.register(name, "secret123")
    u["balance"] = float(funds)
    return u


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def stacked(seq):
    """A shuffle that deals exactly `seq` first (the deck is dealt from the end)."""
    assert len(set(seq)) == len(seq), "duplicate card in the stacked deck"

    def f(deck):
        rest = [c for c in deck if c not in seq]
        deck[:] = rest + list(reversed(seq))
        return deck
    return f


def rigged(table_button, seats, hole, board):
    """The deck order for: hole cards dealt starting left of the button, then burn+flop, burn+turn, burn+river."""
    n = len(seats)
    order = [(table_button + 1 + k) % n for k in range(n)]
    seq = []
    for s in order:
        seq += list(hole[s])
    used = set(seq) | set(board)
    spare = [r + s for r in "23456789" for s in "shdc" if r + s not in used][:3]
    return seq + [spare[0]] + board[:3] + [spare[1]] + [board[3]] + [spare[2]] + [board[4]]


def new_table(names, stacks, bb=20, sb=10, turn=45, rebuy=True, blinds_up=0, money="fake", deck=None, button=-1):
    """A running table with exact stacks, skipping the lobby (that part is tested separately)."""
    fresh_store()
    us = [mk(n, 5000) for n in names]
    t = poker.create(us[0], {"name": "Test", "maxSeats": max(2, len(names))})
    for u in us[1:]:
        poker.join(u, t["id"])
    t["settings"].update({"money": money, "bigBlind": bb, "smallBlind": sb, "stack": max(stacks), "turnSeconds": turn,
                          "rebuy": rebuy, "blindsUp": blinds_up})
    t["status"] = "playing"
    t["blinds"] = {"sb": sb, "bb": bb}
    t["button"] = button
    for seat, st in zip(t["seats"], stacks):
        seat["stack"] = st
        seat["bought"] = st if money == "real" else 0
    if money == "real":
        for u, st in zip(us, stacks):
            u["balance"] -= st / 100
    with mock.patch.object(poker, "shuffle", stacked(deck) if deck else (lambda d: d)):
        poker._start_hand(t, NOW)
    return t, us


def do(us, t, who, action, amount=None, now=NOW):
    poker.act(us[who], t, action, amount, now)


def run_clock(t, start=NOW, steps=12):
    """Advance time in jumps (the way the server's ticker does) until the current hand has finished."""
    now = start
    for _ in range(steps):
        now += poker.RUNOUT_MS + 1
        poker.catch_up(t, now)
        if t["id"] not in poker.tables() or t["hand"] is None or t["hand"]["street"] == "ended":
            break
    return now


def chips(t):
    """Every chip on the table: stacks plus whatever is committed to the hand that is in progress."""
    h = t["hand"]
    live = h is not None and h["street"] != "ended"
    return sum(s["stack"] for s in t["seats"] if s) + (sum(h["contrib"]) if live else 0)


class HandRanking(unittest.TestCase):
    def rank(self, cards):
        return poker.best_hand(cards.split())

    def test_every_category_beats_the_one_below(self):
        hands = ["As Ks Qs Js Ts", "9d 8d 7d 6d 5d", "Kc Kd Kh Ks 2d", "Qc Qd Qh 7s 7d", "Ah 9h 7h 4h 2h",
                 "9s 8d 7c 6h 5d", "Jc Jd Jh 9s 4d", "Tc Td 4h 4s Ad", "8c 8d Ah Ks 3d", "Ac Kd Js 9h 5d"]
        scores = [self.rank(h) for h in hands]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([s[0] for s in scores], [8, 8, 7, 6, 5, 4, 3, 2, 1, 0])

    def test_the_wheel_is_the_lowest_straight(self):
        wheel, six = self.rank("As 2d 3c 4h 5d"), self.rank("2s 3d 4c 5h 6d")
        self.assertEqual(wheel, (4, (5,)))
        self.assertLess(wheel, six)
        self.assertEqual(self.rank("As 2s 3s 4s 5s"), (8, (5,)))        # and a wheel can be a straight flush

    def test_no_wrap_around_straights(self):
        self.assertEqual(self.rank("Qs Ks As 2d 3c")[0], 0)

    def test_kickers_decide(self):
        self.assertGreater(self.rank("Ac Ad Ks Qh Jd"), self.rank("As Ah Kd Qc 9s"))
        self.assertGreater(self.rank("Kc Kd 7s 7h Ad"), self.rank("Kh Ks 7c 7d Qd"))
        self.assertGreater(self.rank("Tc Td Th 9s 8d"), self.rank("Ts Tc Td 9h 7d"))

    def test_same_hand_different_suits_tie(self):
        self.assertEqual(self.rank("Ac Kd 9s 7h 3d"), self.rank("Ad Kh 9c 7s 3c"))

    def test_picks_the_best_five_of_seven(self):
        self.assertEqual(self.rank("As Ks Qs Js Ts 2d 3c"), (8, (14,)))
        self.assertEqual(self.rank("9c 9d 9h 4s 4d 4c 2s")[0], 6)                  # two trips: a full house, not quads
        self.assertEqual(self.rank("2c 2d 5h 9s Kd Kc 3s"), (2, (13, 2, 9)))       # three pair: the best two plus the kicker
        self.assertEqual(self.rank("Ah Kh 3h 4h 9h 2h 7c")[1], (14, 13, 9, 4, 3))  # six hearts: the best five

    def test_board_plays(self):
        board = "As Ks Qs Js Ts"
        self.assertEqual(self.rank(board + " 2d 3c"), self.rank(board + " 9h 8d"))

    def test_descriptions(self):
        d = lambda c: poker.describe(self.rank(c))                                    # noqa: E731
        self.assertEqual(d("As Ks Qs Js Ts"), "Royal flush")
        self.assertEqual(d("9d 8d 7d 6d 5d"), "Straight flush, Nine high")
        self.assertEqual(d("Kc Kd Kh Ks 2d"), "Four of a kind, Kings")
        self.assertEqual(d("Qc Qd Qh 7s 7d"), "Full house, Queens over Sevens")
        self.assertEqual(d("Ah 9h 7h 4h 2h"), "Flush, Ace high")
        self.assertEqual(d("As 2d 3c 4h 5d"), "Straight, Five high")
        self.assertEqual(d("Jc Jd Jh 9s 4d"), "Three of a kind, Jacks")
        self.assertEqual(d("Tc Td 4h 4s Ad"), "Two pair, Tens and Fours")
        self.assertEqual(d("8c 8d Ah Ks 3d"), "Pair of Eights")
        self.assertEqual(d("Ac Kd Js 9h 5d"), "High card, Ace")


class SidePots(unittest.TestCase):
    def pots(self, contrib, st):
        return poker._build_pots({"contrib": contrib, "st": st})

    def test_one_pot_when_everyone_matches(self):
        self.assertEqual(self.pots([100, 100, 100], ["in"] * 3), [{"amount": 300, "eligible": [0, 1, 2]}])

    def test_three_all_ins_make_three_pots(self):
        self.assertEqual(self.pots([100, 300, 500], ["allin"] * 3),
                         [{"amount": 300, "eligible": [0, 1, 2]}, {"amount": 400, "eligible": [1, 2]},
                          {"amount": 200, "eligible": [2]}])

    def test_folded_money_stays_in_but_cannot_win(self):
        pots = self.pots([50, 100, 100, 80], ["allin", "in", "in", "folded"])
        self.assertEqual(sum(p["amount"] for p in pots), 330)
        self.assertEqual(pots[0], {"amount": 200, "eligible": [0, 1, 2]})
        self.assertEqual(pots[1], {"amount": 130, "eligible": [1, 2]})
        for p in pots:
            self.assertNotIn(3, p["eligible"])

    def test_pots_with_the_same_players_merge(self):
        self.assertEqual(self.pots([40, 40, 0], ["in", "in", "folded"]), [{"amount": 80, "eligible": [0, 1]}])


class Betting(unittest.TestCase):
    def test_blinds_and_who_acts_first_three_handed(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        h = t["hand"]
        self.assertEqual((h["button"], h["sb"], h["bb"], h["toAct"]), (0, 1, 2, 0))
        self.assertEqual((h["bets"], h["currentBet"], h["minRaise"]), ([0, 10, 20], 20, 20))
        self.assertEqual([s["stack"] for s in t["seats"]], [1000, 990, 980])
        self.assertEqual(chips(t), 3000)

    def test_heads_up_button_posts_the_small_blind_and_acts_first(self):
        t, us = new_table(["ann", "bob"], [1000, 1000])
        h = t["hand"]
        self.assertEqual((h["button"], h["sb"], h["bb"], h["toAct"]), (0, 0, 1, 0))
        do(us, t, 0, "call")
        self.assertEqual(h["toAct"], 1)                       # the big blind still has the option
        do(us, t, 1, "check")
        self.assertEqual((h["street"], h["toAct"]), ("flop", 1))      # after the flop the big blind acts first

    def test_big_blind_gets_the_option_when_everyone_just_calls(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        do(us, t, 0, "call")
        do(us, t, 1, "call")
        h = t["hand"]
        self.assertEqual((h["street"], h["toAct"]), ("preflop", 2))
        legal = poker._legal(t, 2)
        self.assertTrue(legal["canCheck"] and legal["canRaise"])
        do(us, t, 2, "check")
        self.assertEqual(t["hand"]["street"], "flop")

    def test_raise_sizes(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        self.assertEqual(poker._legal(t, 0)["minRaiseTo"], 40)
        self.assertIn("smallest raise is to 40", err(poker.act, us[0], t, "raise", 30, NOW).message)
        do(us, t, 0, "raise", 40)
        self.assertEqual(t["hand"]["minRaise"], 20)
        self.assertEqual(poker._legal(t, 1)["minRaiseTo"], 60)         # a raise of 20 on top of 40
        do(us, t, 1, "raise", 140)                                    # a raise of 100
        self.assertEqual(t["hand"]["minRaise"], 100)
        self.assertEqual(poker._legal(t, 2)["minRaiseTo"], 240)
        self.assertIn("only have", err(poker.act, us[2], t, "raise", 5000, NOW).message)

    def test_cannot_check_facing_a_bet_or_call_nothing(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        self.assertIn("can't check", err(poker.act, us[0], t, "check", None, NOW).message)
        do(us, t, 0, "call")
        do(us, t, 1, "call")
        do(us, t, 2, "check")
        self.assertIn("nothing to call", err(poker.act, us[1], t, "call", None, NOW).message)

    def test_only_the_player_to_act_can_act(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        self.assertIn("not your turn", err(poker.act, us[1], t, "call", None, NOW).message)
        self.assertIn("not your turn", err(poker.act, us[2], t, "fold", None, NOW).message)

    def test_a_short_all_in_does_not_reopen_the_betting(self):
        t, us = new_table(["ann", "bob", "cat"], [1000, 1000, 280])
        do(us, t, 0, "raise", 100)
        do(us, t, 1, "call")
        do(us, t, 2, "call")                                           # cat has 180 left
        self.assertEqual(t["hand"]["street"], "flop")
        self.assertEqual(t["hand"]["toAct"], 1)
        do(us, t, 1, "raise", 100)                                    # bob bets 100
        do(us, t, 2, "allin")                                         # cat is all in for 180: a raise of only 80
        h = t["hand"]
        self.assertEqual((h["currentBet"], h["minRaise"]), (180, 100))
        self.assertTrue(poker._legal(t, 0)["canRaise"])               # ann has not acted this street
        do(us, t, 0, "call")
        legal = poker._legal(t, 1)                                    # bob already bet: this didn't re-open it for him
        self.assertEqual((legal["canRaise"], legal["toCall"]), (False, 80))
        self.assertIn("re-opened", err(poker.act, us[1], t, "raise", 500, NOW).message)
        do(us, t, 1, "call")
        self.assertEqual(t["hand"]["street"], "turn")

    def test_a_full_raise_reopens_for_everyone(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        do(us, t, 0, "raise", 60)
        do(us, t, 1, "call")
        do(us, t, 2, "raise", 160)                                    # a full re-raise
        self.assertEqual(t["hand"]["toAct"], 0)
        self.assertTrue(poker._legal(t, 0)["canRaise"])               # ann may re-raise again

    def test_short_all_in_blind_still_costs_everyone_the_full_big_blind(self):
        t, us = new_table(["ann", "bob", "cat"], [1000, 1000, 12])
        h = t["hand"]
        self.assertEqual((h["bets"][2], h["st"][2], h["currentBet"]), (12, "allin", 20))
        self.assertEqual(poker._legal(t, 0)["toCall"], 20)

    def test_everyone_folds_to_one_player_and_nothing_is_shown(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        do(us, t, 0, "fold")
        do(us, t, 1, "fold")
        h = t["hand"]
        self.assertEqual(h["street"], "ended")
        self.assertEqual((h["result"]["reason"], h["result"]["shown"]), ("fold", {}))
        self.assertEqual([s["stack"] for s in t["seats"]], [1000, 990, 1010])
        self.assertEqual(chips(t), 3000)

    def test_check_down_to_a_showdown(self):
        hole = {0: ("As", "Ad"), 1: ("Kc", "Kd"), 2: ("7h", "2c")}
        board = ["Ah", "Kh", "9s", "4d", "3c"]
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, deck=rigged(0, [0, 1, 2], hole, board))
        do(us, t, 0, "call")
        do(us, t, 1, "call")
        do(us, t, 2, "check")
        for street in ("flop", "turn", "river"):
            self.assertEqual(t["hand"]["street"], street)
            for who in (1, 2, 0):
                do(us, t, who, "check")
        h = t["hand"]
        self.assertEqual(h["street"], "ended")
        self.assertEqual(h["board"], board)
        self.assertEqual(h["result"]["pots"][0]["winners"][0]["seat"], 0)
        self.assertEqual(h["result"]["hands"]["0"], "Three of a kind, Aces")
        self.assertEqual([s["stack"] for s in t["seats"]], [1040, 980, 980])
        self.assertEqual(sorted(h["result"]["shown"]), ["0", "1", "2"])

    def test_split_pot_when_the_board_plays(self):
        hole = {0: ("2c", "3d"), 1: ("4c", "5d"), 2: ("6c", "7d")}
        board = ["As", "Ks", "Qs", "Js", "Ts"]                          # a royal flush on the board: everybody ties
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, bb=20, sb=10, deck=rigged(0, [0, 1, 2], hole, board))
        do(us, t, 0, "raise", 40)
        do(us, t, 1, "call")
        do(us, t, 2, "call")
        for _ in range(3):
            for who in (1, 2, 0):
                do(us, t, who, "check")
        self.assertEqual([s["stack"] for s in t["seats"]], [1000, 1000, 1000])
        self.assertEqual(chips(t), 3000)

    def test_odd_chip_goes_to_the_first_seat_left_of_the_button(self):
        hole = {0: ("2c", "3d"), 1: ("4c", "5d"), 2: ("6c", "7d")}
        board = ["As", "Ks", "Qs", "Js", "Ts"]
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, bb=2, sb=1, deck=rigged(0, [0, 1, 2], hole, board))
        do(us, t, 0, "call")                 # ann calls 2
        do(us, t, 1, "fold")                 # bob folds his small blind: a 5-chip pot
        do(us, t, 2, "check")
        for _ in range(3):
            for who in (2, 0):
                do(us, t, who, "check")
        # ann and cat tie. 5 does not split evenly: the extra chip goes to the first seat left of the button (cat)
        self.assertEqual([s["stack"] for s in t["seats"]], [1000, 999, 1001])
        self.assertEqual(chips(t), 3000)

    def test_all_in_runout_deals_street_by_street(self):
        hole = {0: ("As", "Ad"), 1: ("Kc", "Kd")}
        board = ["2h", "7d", "9s", "4c", "Jh"]
        t, us = new_table(["ann", "bob"], [500, 500], deck=rigged(0, [0, 1], hole, board))
        do(us, t, 0, "allin")
        do(us, t, 1, "call")
        h = t["hand"]
        self.assertTrue(h["runout"])
        self.assertEqual(h["board"], [])
        steps = []
        for k in range(1, 6):
            poker.catch_up(t, NOW + poker.RUNOUT_MS * k + 1)
            steps.append((h["street"], len(h["board"])))
        self.assertEqual(steps[:3], [("flop", 3), ("turn", 4), ("river", 5)])
        self.assertEqual(h["street"], "ended")
        self.assertEqual([s["stack"] for s in t["seats"]], [1000, 0])
        self.assertEqual(chips(t), 1000)

    def test_main_pot_side_pot_and_the_uncalled_part_come_back(self):
        hole = {0: ("As", "Ad"), 1: ("Kc", "Kd"), 2: ("7h", "2c")}      # ann best, bob second, cat worst
        board = ["Qh", "9s", "5d", "4c", "3h"]
        t, us = new_table(["ann", "bob", "cat"], [100, 300, 500], deck=rigged(0, [0, 1, 2], hole, board))
        do(us, t, 0, "allin")
        do(us, t, 1, "allin")
        do(us, t, 2, "allin")
        run_clock(t)
        self.assertEqual(t["hand"]["street"], "ended")
        # ann wins the 300 main pot, bob the 400 side pot, cat gets her extra 200 back
        self.assertEqual([s["stack"] for s in t["seats"]], [300, 400, 200])
        pots = t["hand"]["result"]["pots"]
        self.assertEqual([(p["amount"], p["returned"]) for p in pots], [(300, False), (400, False), (200, True)])
        self.assertEqual(chips(t), 900)

    def test_folded_players_money_goes_to_the_winner(self):
        hole = {0: ("As", "Ad"), 1: ("Kc", "Kd"), 2: ("7h", "2c")}
        board = ["Qh", "9s", "5d", "4c", "3h"]
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, deck=rigged(0, [0, 1, 2], hole, board))
        do(us, t, 0, "raise", 100)
        do(us, t, 1, "call")
        do(us, t, 2, "fold")                                           # cat folds her big blind into the pot
        for who in (1, 0):
            do(us, t, who, "check")                                    # flop
        do(us, t, 1, "raise", 50)                                      # turn
        do(us, t, 0, "call")
        for who in (1, 0):
            do(us, t, who, "check")                                    # river
        self.assertEqual(t["hand"]["street"], "ended")
        # ann and bob each put in 150, cat's folded 20 is in the pot too: ann wins 320
        self.assertEqual([s["stack"] for s in t["seats"]], [1170, 850, 980])
        self.assertEqual(chips(t), 3000)


class Clocks(unittest.TestCase):
    def test_out_of_time_checks_when_free_and_folds_when_not(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, turn=30)
        h = t["hand"]
        self.assertEqual(h["deadline"], NOW + 30_000)
        poker.catch_up(t, NOW + 30_001)                                # ann faces the big blind: fold
        self.assertEqual(h["st"][0], "folded")
        self.assertEqual(t["seats"][0]["timeouts"], 1)
        do(us, t, 1, "call", now=NOW + 31_000)
        poker.catch_up(t, NOW + 31_000 + 30_001)                       # cat has the option to check: check
        self.assertEqual(h["street"], "flop")
        self.assertEqual(t["seats"][2]["timeouts"], 1)

    def test_three_timeouts_in_a_row_stands_you_up_after_the_hand(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, turn=15)
        t["seats"][0]["timeouts"] = 2                                  # ann has already missed two turns
        poker.catch_up(t, t["hand"]["deadline"] + 1)                    # and now a third
        self.assertTrue(t["seats"][0]["leaving"])
        do(us, t, 1, "fold", now=NOW + 99_999)
        self.assertEqual(t["hand"]["street"], "ended")
        poker.catch_up(t, NOW + 99_999 + poker.FOLD_WIN_MS + 1)
        self.assertIsNone(t["seats"][0])

    def test_a_manual_move_resets_the_timeout_count(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, turn=15)
        t["seats"][0]["timeouts"] = 2
        do(us, t, 0, "call")
        self.assertEqual(t["seats"][0]["timeouts"], 0)

    def test_no_clock_means_it_waits(self):
        t, us = new_table(["ann", "bob"], [1000, 1000], turn=0)
        self.assertIsNone(t["hand"]["deadline"])
        self.assertFalse(poker.catch_up(t, NOW + 10 ** 9))

    def test_the_next_hand_starts_by_itself_after_the_pause(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        do(us, t, 0, "fold")
        do(us, t, 1, "fold")
        self.assertFalse(poker.catch_up(t, NOW + poker.FOLD_WIN_MS - 1))
        poker.catch_up(t, NOW + poker.FOLD_WIN_MS + 1)
        self.assertEqual((t["handNo"], t["hand"]["street"], t["hand"]["button"]), (2, "preflop", 1))   # the button moved

    def test_blinds_double_every_n_hands(self):
        t, us = new_table(["ann", "bob"], [10_000, 10_000], bb=20, sb=10, blinds_up=2)
        now = NOW
        seen = [dict(t["blinds"])]
        for _ in range(4):
            h = t["hand"]
            do(us, t, h["toAct"], "fold", now=now)
            now += poker.FOLD_WIN_MS + 1
            poker.catch_up(t, now)
            seen.append(dict(t["blinds"]))
        self.assertEqual([b["bb"] for b in seen], [20, 20, 40, 40, 80])


class Rebuys(unittest.TestCase):
    def bust_bob(self, rebuy):
        hole = {0: ("As", "Ad"), 1: ("Kc", "Kd")}
        t, us = new_table(["ann", "bob", "cat"], [1000, 200, 1000], rebuy=rebuy,
                          deck=rigged(0, [0, 1, 2], {0: ("As", "Ad"), 1: ("Kc", "Kd"), 2: ("7h", "2c")}, ["Qh", "9s", "5d", "4c", "3h"]))
        do(us, t, 0, "allin")                  # ann has the button...
        do(us, t, 1, "call")                   # bob (small blind) calls all in with kings
        do(us, t, 2, "fold")
        run_clock(t)
        return t, us

    def test_busted_player_can_rebuy_when_it_is_on(self):
        t, us = self.bust_bob(True)
        self.assertEqual(t["seats"][1]["stack"], 0)
        poker.catch_up(t, NOW + 99_999 + poker.SHOWDOWN_MS + 1)
        self.assertTrue(t["seats"][1]["busted"])
        self.assertIn("still have chips", err(poker.rebuy, us[0], t).message)
        poker.rebuy(us[1], t)
        self.assertEqual((t["seats"][1]["stack"], t["seats"][1]["busted"]), (t["settings"]["stack"], False))

    def test_busted_player_is_stood_up_when_rebuys_are_off(self):
        t, us = self.bust_bob(False)
        poker.catch_up(t, NOW + 99_999 + poker.SHOWDOWN_MS + 1)
        self.assertIsNone(t["seats"][1])                                # no rebuy: out of chips means out
        self.assertIn("not at this table", err(poker.rebuy, us[1], t).message)

    def test_a_busted_player_who_never_rebuys_loses_the_seat(self):
        t, us = self.bust_bob(True)
        later = NOW + 99_999 + poker.SHOWDOWN_MS + 1
        poker.catch_up(t, later)
        self.assertTrue(t["seats"][1]["busted"])
        poker.catch_up(t, later + poker.BUST_WAIT_MS + 5)
        self.assertIsNone(t["seats"][1])


class LeavingMidHand(unittest.TestCase):
    def test_leaving_when_it_is_your_turn_folds_and_you_go_after_the_hand(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        poker.leave(us[0], t)
        h = t["hand"]
        self.assertEqual(h["st"][0], "folded")
        self.assertTrue(t["seats"][0]["leaving"])
        do(us, t, 1, "fold")
        poker.catch_up(t, NOW + poker.FOLD_WIN_MS + 1)
        self.assertIsNone(t["seats"][0])

    def test_a_folded_player_can_leave_straight_away(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        do(us, t, 0, "fold")
        poker.leave(us[0], t)
        self.assertIsNone(t["seats"][0])
        self.assertEqual(t["hand"]["st"][0], "out")
        do(us, t, 1, "call")
        do(us, t, 2, "check")
        self.assertEqual(t["hand"]["street"], "flop")

    def test_the_host_role_moves_on_and_an_empty_table_disappears(self):
        t, us = new_table(["ann", "bob"], [1000, 1000])
        t["status"] = "setup"
        t["hand"] = None
        poker.leave(us[0], t)
        self.assertEqual(t["hostId"], us[1]["id"])
        poker.leave(us[1], t)
        self.assertNotIn(t["id"], poker.tables())


class YourOwnHand(unittest.TestCase):
    """The table tells you what you are holding, and what everybody just did, without leaking anything."""

    def live(self, hole, board=()):
        return poker.live_hand(hole.split(), list(board.split()) if board else [])

    def test_before_the_flop_it_is_a_pair_or_a_high_card(self):
        self.assertEqual(self.live("Js Jd")["name"], "Pair of Jacks")
        self.assertEqual(self.live("7c Ah")["name"], "High card, Ace")
        self.assertEqual(self.live("7c Ah")["draws"], [])

    def test_it_names_the_best_five_cards_from_seven(self):
        self.assertEqual(self.live("Ks Kd", "Kh 2c 2d 9s 4h")["name"], "Full house, Kings over Twos")
        self.assertEqual(self.live("9h 8d", "7c 6s Ts")["name"], "Straight, Ten high")
        self.assertEqual(self.live("Ah 2h", "9h 5h Kh")["name"], "Flush, Ace high")

    def test_flush_and_straight_draws_show_on_the_flop_and_turn(self):
        self.assertEqual(self.live("As 9s", "2s 7s Kd")["draws"], ["Flush draw"])
        self.assertEqual(self.live("9h 8d", "7c 6s 2d")["draws"], ["Open-ended straight draw"])
        self.assertEqual(self.live("9h 7d", "6c 5s Kd")["draws"], ["Straight draw"])
        self.assertEqual(self.live("Ah Kh", "Qh Jh 2c")["draws"], ["Flush draw", "Straight draw"])

    def test_no_draws_once_the_hand_is_made_or_the_river_is_down(self):
        self.assertEqual(self.live("9h 8d", "7c 6s Ts")["draws"], [])                 # already a straight
        self.assertEqual(self.live("As 9s", "2s 7s Kd 3c 4h")["draws"], [])            # river: nothing left to draw to
        self.assertEqual(self.live("Ah 2h", "9h 5h Kh")["draws"], [])                  # already a flush

    def test_a_draw_that_everybody_shares_is_not_yours(self):
        self.assertEqual(self.live("2c 2d", "9h Tc Js Qd")["draws"], [])               # the board has the straight draw
        self.assertEqual(self.live("2c 3d", "9s 7s Ks As")["draws"], [])               # four spades on board, none in hand

    def test_the_view_gives_you_your_own_hand_and_nobody_elses(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3,
                          deck=rigged(0, [0, 1, 2], {0: ["Ah", "Ad"], 1: ["7c", "2d"], 2: ["Ks", "Qs"]},
                                      ["3c", "8d", "Jh", "4s", "9c"]))
        mine = poker.view(t, us[0]["id"])["hand"]["mine"]
        self.assertEqual(mine, {"name": "Pair of Aces", "draws": []})
        self.assertEqual(poker.view(t, us[1]["id"])["hand"]["mine"]["name"], "High card, Seven")
        t["status"], spectator = "playing", mk("spec")
        self.assertIsNone(poker.view(t, spectator["id"])["hand"]["mine"])               # watchers hold nothing
        do(us, t, 0, "fold")
        self.assertIsNone(poker.view(t, us[0]["id"])["hand"]["mine"])                   # nor do folded players

    def test_everybody_can_see_what_the_others_just_did(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        last = lambda: [s["last"] for s in poker.view(t, us[0]["id"])["seats"]]        # noqa: E731
        self.assertEqual(last(), [None, None, None])                                   # blinds are not actions
        do(us, t, 0, "raise", 60)
        do(us, t, 1, "call")
        self.assertEqual(last(), ["raise", "call", None])
        do(us, t, 2, "raise", 200)                                                     # a re-raise clears the stale labels
        self.assertEqual(last(), [None, None, "raise"])
        do(us, t, 0, "call")
        do(us, t, 1, "call")
        self.assertEqual(t["hand"]["street"], "flop")
        self.assertEqual(last(), [None, None, None])                                   # new street, new slate
        do(us, t, 1, "raise", 40)
        self.assertEqual(poker.view(t, us[0]["id"])["seats"][1]["last"], "bet")
        do(us, t, 2, "fold")
        self.assertEqual(poker.view(t, us[0]["id"])["seats"][2]["last"], None)         # a fold shows as the seat's status
        self.assertEqual(poker.view(t, us[0]["id"])["seats"][2]["status"], "folded")

    def test_the_action_log_speaks_in_dollars_and_card_symbols(self):
        t, us = new_table(["ann", "bob", "cat"], [10_000] * 3, bb=100, sb=50, money="real")
        do(us, t, 0, "raise", 350)
        do(us, t, 1, "call")
        do(us, t, 2, "fold")
        self.assertEqual(t["log"][-4:-1], ["ann raises to $3.50", "bob calls $3", "cat folds"])
        flop = t["log"][-1]
        self.assertRegex(flop, "^Flop: \\S+ \\S+ \\S+$")
        self.assertRegex(flop, "[\u2660\u2665\u2666\u2663]")
        f, us = new_table(["ann", "bob", "cat"], [1000] * 3)
        do(us, f, 0, "raise", 1000)
        self.assertEqual(f["log"][-1], "ann raises to 1,000 and is all in")

    def test_a_timed_out_check_is_labelled_too(self):
        t, us = new_table(["ann", "bob", "cat"], [1000] * 3, turn=30)
        do(us, t, 0, "call")
        do(us, t, 1, "call")
        poker.catch_up(t, NOW + 30_001)                                                 # cat has the option and times out
        self.assertEqual(t["hand"]["street"], "flop")
        do(us, t, 1, "check")
        self.assertEqual(poker.view(t, us[0]["id"])["seats"][1]["last"], "check")


class Conservation(unittest.TestCase):
    """Random but legal play, many hands: not one chip may appear or vanish, and every hand must finish."""

    def play(self, seed, n_players, real=False):
        rnd = random.Random(seed)
        stacks = [rnd.choice([40, 100, 300, 1000, 5000]) for _ in range(n_players)]
        t, us = new_table([f"player{k}" for k in range(n_players)], stacks, bb=20, sb=10, turn=0, rebuy=False,
                          money="real" if real else "fake")
        total = chips(t)
        now = NOW
        for _ in range(60):
            if t["id"] not in poker.tables() or t["hand"] is None:
                break
            h = t["hand"]
            steps = 0
            while h["street"] != "ended":
                steps += 1
                self.assertLess(steps, 400, "a hand never finished")
                if h["runout"]:
                    now += poker.RUNOUT_MS + 1
                    poker.catch_up(t, now)
                else:
                    i = h["toAct"]
                    self.assertIsNotNone(i)
                    legal = poker._legal(t, i)
                    options = ["fold", "call" if legal["canCall"] else "check"]
                    if legal["canRaise"]:
                        options += ["raise", "raise", "allin"]
                    choice = rnd.choice(options)
                    if choice == "raise":
                        poker.act(us[i], t, "raise", rnd.randint(legal["minRaiseTo"], legal["maxRaiseTo"]), now)
                    else:
                        poker.act(us[i], t, choice, None, now)
                self.assertEqual(chips(t), total, f"chips changed (seed {seed})")
                for s in t["seats"]:
                    if s:
                        self.assertGreaterEqual(s["stack"], 0)
            self.assertEqual(chips(t), total)
            now += poker.SHOWDOWN_MS + 1
            poker.catch_up(t, now)
            if t["id"] in poker.tables():
                total = sum(s["stack"] for s in t["seats"] if s) + (sum(t["hand"]["contrib"]) if t["hand"] else 0)
            else:
                break
        return t, us

    def test_many_random_games_conserve_every_chip(self):
        for seed in range(120):
            self.play(seed, 2 + seed % 6)

    def test_real_money_dollars_are_conserved_too(self):
        for seed in range(25):
            t, us = self.play(1000 + seed, 2 + seed % 4, real=True)
            if t["id"] in poker.tables():
                money = sum(u["balance"] for u in us) + sum(s["stack"] for s in t["seats"] if s) / 100
                h = t["hand"]
                if h and h["street"] != "ended":
                    money += sum(h["contrib"]) / 100
                self.assertAlmostEqual(money, 5000 * len(us), places=2)


if __name__ == "__main__":
    unittest.main()
