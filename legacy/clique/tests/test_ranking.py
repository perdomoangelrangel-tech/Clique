"""The global ranking: everybody registered, by the money in their accumulated account."""
import os
import sys
import tempfile
import threading
import unittest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                    # noqa: E402
from backend import games, ledger, ranking      # noqa: E402
from tests import helpers                        # noqa: E402
from tests.econ import mk                        # noqa: E402
from tests.test_http import Client               # noqa: E402


class Board(unittest.TestCase):
    def setUp(self):
        helpers.fresh_store()
        self.ann, self.ben, self.cat = mk("ann", accum=500), mk("ben", accum=1200.5), mk("cat", accum=0)

    def names(self, viewer=None):
        return [p["username"] for p in ranking.board(viewer or self.ann)["people"]]

    def test_everybody_is_listed_richest_first_with_their_accumulated_money(self):
        out = ranking.board(self.ann)
        self.assertEqual([(p["username"], p["place"], p["accum"]) for p in out["people"]], [("ben", 1, 1200.5), ("ann", 2, 500.0), ("cat", 3, 0.0)])
        self.assertEqual((out["count"], out["myPlace"], out["richest"], out["poorest"]), (3, 2, 1200.5, 0.0))

    def test_only_the_accumulated_account_counts_not_the_weekly_chips(self):
        ledger.post(self.cat, "weekly", 50000, "test.setup")
        self.assertEqual(self.names(), ["ben", "ann", "cat"])

    def test_equal_money_shares_a_place_and_the_next_place_skips(self):
        dan = mk("dan", accum=500)
        out = ranking.board(self.ann)["people"]
        self.assertEqual([(p["username"], p["place"]) for p in out], [("ben", 1), ("ann", 2), ("dan", 2), ("cat", 4)])

    def test_people_with_the_same_money_are_listed_oldest_account_first(self):
        dan = mk("dan", accum=500, age_days=90)
        self.assertEqual(self.names(), ["ben", "dan", "ann", "cat"])

    def test_suspended_and_deleted_people_are_left_out_and_practice_chips_are_not_a_person(self):
        self.cat["suspended"] = True
        games.demo_account(self.ben)["balance"] = 9999999
        self.assertEqual(self.names(), ["ben", "ann"])

    def test_you_are_marked_and_the_list_tells_nothing_else_about_anybody(self):
        out = ranking.board(self.ann)["people"]
        self.assertEqual([p["isMe"] for p in out], [False, True, False])
        for p in out:
            self.assertEqual(set(p) - {"look", "u", "a", "f", "b", "fr"}, {"id", "username", "rank", "place", "accum", "isMe", "since"})
            self.assertNotIn("balance", p)                           # no weekly money, no email, no stats

    def test_a_huge_balance_and_cents_are_exact(self):
        ledger.post(self.cat, "accumulated", 131086490.29, "test.setup")
        top = ranking.board(self.ann)["people"][0]
        self.assertEqual((top["username"], top["accum"]), ("cat", 131086490.29))


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

    def test_it_needs_a_login_and_shows_everybody_including_strangers(self):
        a, b = Client(self.port), Client(self.port)
        self.assertEqual(a.call("GET", "/api/ranking")[0], 401)
        self.assertEqual(a.call("POST", "/api/auth/register", {"username": "rita", "password": "secret123"})[0], 200)
        self.assertEqual(b.call("POST", "/api/auth/register", {"username": "sven", "password": "secret123"})[0], 200)    # no circle, no friendship
        st, out = a.call("GET", "/api/ranking")
        self.assertEqual(st, 200)
        self.assertEqual(sorted(p["username"] for p in out["people"]), ["rita", "sven"])
        self.assertEqual([p["place"] for p in out["people"]], [1, 1])                     # both have 0 in the accumulated account
        self.assertEqual(out["myPlace"], 1)


if __name__ == "__main__":
    unittest.main()
