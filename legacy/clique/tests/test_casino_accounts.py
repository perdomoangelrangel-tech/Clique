"""Casino rounds on the weekly account or the accumulated account (games.account_for / games.accum_account).

The choice is made per round by the page ("acct": "accumulated"). What matters: the chips come from and go back to the account that was chosen
and nothing else is touched, a round in progress belongs to its account, and the weekly week stays about weekly chips (standings, awards and the
weekly minimum ignore accumulated rounds) while XP, challenges and milestones count as for any real-chips round."""
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                    # noqa: E402
from backend import games, ledger, markets, progress, users, weekly   # noqa: E402
from backend.util import ApiError, week_key      # noqa: E402
from tests import helpers                        # noqa: E402
from tests.econ import books_balance, circle_of, mk   # noqa: E402
from tests.test_http import Client               # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        helpers.fresh_store()
        self.ann = mk("ann", weekly=1000.0, accum=800.0)

    def acc(self):
        return games.account_for(self.ann, False, "accumulated")

    def balances(self):
        return ledger.balance(self.ann, "weekly"), ledger.balance(self.ann, "accumulated")


class ChoosingTheWallet(Base):
    def test_weekly_is_the_default_and_the_practice_wallet_wins_over_everything(self):
        self.assertIs(games.account_for(self.ann, False), self.ann)
        self.assertIs(games.account_for(self.ann, False, "weekly"), self.ann)
        self.assertTrue(games.account_for(self.ann, True, "accumulated")["isDemo"])
        w = self.acc()
        self.assertEqual((w["balance"], w["isAcc"]), (800.0, True))

    def test_an_unknown_account_is_refused(self):
        with self.assertRaises(ApiError):
            games.account_for(self.ann, False, "savings")


class OneRound(Base):
    def bet(self, forced, target=2.0, amount=100, acct="accumulated"):
        with mock.patch.object(games, "limbo_roll_c", lambda: forced):
            return games.limbo(games.account_for(self.ann, False, acct), {"amount": amount, "target": target})

    def test_a_win_is_paid_into_the_accumulated_account_and_the_weekly_one_is_untouched(self):
        res = self.bet(forced=300)
        self.assertEqual((res["win"], res["payout"], res["balance"]), (True, 200.0, 900.0))
        self.assertEqual(self.balances(), (1000.0, 900.0))
        self.assertTrue(books_balance(self.ann))

    def test_a_loss_costs_the_accumulated_account_only(self):
        self.bet(forced=105)
        self.assertEqual(self.balances(), (1000.0, 700.0))

    def test_the_weekly_account_still_works_the_same_way(self):
        self.bet(forced=105, acct=None)
        self.assertEqual(self.balances(), (900.0, 800.0))

    def test_you_cannot_bet_more_than_the_account_you_chose_has(self):
        with self.assertRaises(ApiError) as e:
            self.bet(forced=300, amount=900)                        # the weekly account has it, the accumulated one does not
        self.assertIn("Not enough funds", str(e.exception))
        self.assertEqual(self.balances(), (1000.0, 800.0))

    def test_a_small_weekly_account_does_not_stop_a_bet_from_the_accumulated_one(self):
        ledger.post(self.ann, "weekly", -995, "test.setup")
        self.bet(forced=300, amount=100)
        self.assertEqual(self.balances(), (5.0, 900.0))

    def test_the_round_is_written_down_apart_from_the_weekly_history_and_statistics(self):
        self.bet(forced=300)
        self.assertEqual(self.ann["history"], [])
        self.assertEqual(self.ann["accGame"]["history"][0]["game"], "limbo")
        self.assertNotIn("gamesPlayed", self.ann["stats"].get(week_key(), {}))
        self.assertEqual(self.ann["accGame"]["stats"][week_key()]["gamesPlayed"], 1)
        self.assertEqual(games.account_for(self.ann, False, "accumulated")["history"][0]["profit"], 100.0)

    def test_the_weekly_standings_do_not_move(self):
        c = circle_of(self.ann, mk("ben"))
        before = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}
        self.bet(forced=500, target=4.0, amount=300)                # wins 900 net of the stake
        after = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}
        self.assertEqual(before, after)

    def test_xp_still_counts_for_the_person(self):
        xp = progress.state(self.ann)["xp"]
        self.bet(forced=300)
        self.assertGreater(progress.state(self.ann)["xp"], xp)

    def test_the_practice_wallet_is_still_separate(self):
        demo = games.account_for(self.ann, True, "accumulated")
        with mock.patch.object(games, "limbo_roll_c", lambda: 300):
            games.limbo(demo, {"amount": 10, "target": 2.0})
        self.assertEqual(self.balances(), (1000.0, 800.0))


class RoundsInProgress(Base):
    def test_a_round_belongs_to_the_account_it_started_on(self):
        games.mines_start(self.acc(), {"amount": 100, "size": 25, "mines": 3})
        self.assertEqual(self.balances(), (1000.0, 700.0))
        self.assertIsNotNone(games.active_state(self.acc())["mines"])
        self.assertIsNone(games.active_state(self.ann)["mines"])        # the weekly account has no round going
        games.mines_start(self.ann, {"amount": 50, "size": 25, "mines": 3})       # and can start its own at the same time
        self.assertEqual(self.balances(), (950.0, 700.0))

    def test_a_second_round_on_the_same_account_is_still_refused(self):
        games.mines_start(self.acc(), {"amount": 100, "size": 25, "mines": 3})
        with self.assertRaises(ApiError):
            games.mines_start(self.acc(), {"amount": 100, "size": 25, "mines": 3})

    def test_chips_in_a_round_are_not_counted_in_the_weekly_week_and_the_payout_goes_home(self):
        nw = markets.net_worth(self.ann)
        escrow = games.escrow(self.ann["id"])
        games.tower_start(self.acc(), {"amount": 100, "risk": "easy"})
        self.assertEqual((markets.net_worth(self.ann), games.escrow(self.ann["id"])), (nw, escrow))     # nothing weekly changed
        st = games._games(self.acc())["tower"]
        safe = next(c for c in range(st["cols"]) if c not in st["layout"][0])
        games.tower_pick(self.acc(), {"tile": safe})
        games.tower_cashout(self.acc())
        w, a = self.balances()
        self.assertEqual(w, 1000.0)
        self.assertGreater(a, 700.0)
        self.assertTrue(books_balance(self.ann))

    def test_the_round_state_comes_back_for_the_account_it_was_started_on(self):
        games.moles_start(self.acc(), {"amount": 10, "moles": 3})
        again = games.account_for(self.ann, False, "accumulated")
        self.assertEqual(games.moles_state(again)["bet"], 10.0)
        self.assertIsNone(games.moles_state(self.ann))


class EveryGameCanUseIt(Base):
    def test_every_game_plays_from_the_accumulated_account_and_never_touches_the_weekly_one(self):
        w = self.acc()
        starts = [
            lambda: games.limbo(w, {"amount": 5, "target": 2.0}),
            lambda: games.roulette(w, {"bets": [{"type": "red", "amount": 5}]}),
            lambda: games.coinflip(w, {"amount": 5, "side": "heads"}),
            lambda: games.dice(w, {"amount": 5, "direction": "over", "target": 50}),
            lambda: games.war(w, {"amount": 5}),
            lambda: games.wheel(w, {"risk": "low", "amount": 5}),
            lambda: games.blackjack_deal(w, {"amount": 5}),
            lambda: games.chicken_start(w, {"amount": 5, "difficulty": "easy"}),
            lambda: games.hilo_start(w, {"amount": 5}),
            lambda: games.rps_start(w, {"amount": 5}),
            lambda: games.mines_start(w, {"amount": 5, "size": 25, "mines": 3}),
            lambda: games.moles_start(w, {"amount": 5, "moles": 3}),
            lambda: games.tower_start(w, {"amount": 5, "risk": "easy"}),
        ]
        for i, play in enumerate(starts):
            play()
            self.assertEqual(ledger.balance(self.ann, "weekly"), 1000.0, f"game #{i}")
        self.assertLess(ledger.balance(self.ann, "accumulated"), 800.0)
        self.assertTrue(books_balance(self.ann))


class ThroughTheServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helpers.fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        helpers.restore_store_path()

    def test_the_page_picks_the_account_per_request(self):
        c = Client(self.port)
        self.assertEqual(c.call("POST", "/api/auth/register", {"username": "tess", "password": "secret123"})[0], 200)
        _, me = c.call("GET", "/api/me")
        uid = me["user"]["id"]
        from backend.store import db
        u = db()["users"][uid]
        ledger.post(u, "accumulated", 300.0, "test.setup")
        st, out = c.call("POST", "/api/games/limbo", {"amount": 50, "target": 1.01, "acct": "accumulated"})
        self.assertEqual(st, 200)
        self.assertEqual(out["user"]["weekly"], 1000.0)                                  # nothing came out of the weekly account
        self.assertEqual(out["user"]["accum"], 300.0 - 50 + out["payout"])
        accum_after = out["user"]["accum"]
        st, out = c.call("POST", "/api/games/limbo", {"amount": 10, "target": 1.01})     # no account named: the weekly one
        self.assertNotEqual(out["user"]["weekly"], 1000.0)                               # it moved the weekly account...
        self.assertEqual(out["user"]["accum"], accum_after)                              # ...and left the accumulated one alone
        self.assertEqual(c.call("POST", "/api/games/limbo", {"amount": 1, "target": 2, "acct": "savings"})[0], 400)
        st, hist = c.call("GET", "/api/games/history?acct=accumulated")
        self.assertEqual((st, len(hist["history"])), (200, 1))
        st, hist = c.call("GET", "/api/games/history")
        self.assertEqual((st, len(hist["history"])), (200, 1))                           # one weekly round, kept apart
        st, state = c.call("GET", "/api/games/state?acct=accumulated")
        self.assertEqual(st, 200)
        self.assertEqual(state["balance"], out["user"]["accum"])

    def test_the_demo_flag_beats_the_account_over_http(self):
        c = Client(self.port)
        self.assertEqual(c.call("POST", "/api/auth/register", {"username": "uma", "password": "secret123"})[0], 200)
        st, out = c.call("POST", "/api/games/limbo", {"amount": 5, "target": 1.01, "acct": "accumulated", "demo": True})
        self.assertEqual(st, 200)
        self.assertTrue(out["user"]["demo"])


if __name__ == "__main__":
    unittest.main()
