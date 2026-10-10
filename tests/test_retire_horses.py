"""Taking the Horses game away: nobody loses money to it, and nothing of it is left behind."""
import os
import sys
import tempfile
import threading
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                         # noqa: E402
from backend import ledger, migrations                                # noqa: E402
from backend.store import store                                       # noqa: E402
from backend.util import now_ms                                       # noqa: E402
from tests.helpers import fresh_store, restore_store_path             # noqa: E402
from tests.test_http import Client                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tearDownModule():
    restore_store_path()


def person(uid, name, balance=900.0):
    return {"id": uid, "username": name, "salt": "00", "hash": "x", "balance": balance, "accum": 0.0, "createdAt": now_ms() - 30 * 86400000,
            "stats": {}, "activity": [], "history": [], "demo": {"balance": 400.0, "stats": {}, "activity": [], "history": []}}


def bet(stake_c, settled=False):
    return {"horse": 1, "stake_c": stake_c, "mult": 250, "t": now_ms(), "settled": settled, "rid": None}


def old_data(**extra):
    """What the saved data looks like on a site that still has Horses: schema 2, a race in progress, a few bets."""
    data = {"meta": {"schema": 2}, "users": {"a": person("a", "ann"), "b": person("b", "bob"), "c": person("c", "cy")},
            "usernames": {"ann": "a", "bob": "b", "cy": "c"}, "sessions": {}, "circles": {}, "markets": {}, "snapshots": {},
            "games": {}, "feed": [], "poker": {}, "social": {}, "chats": {}, "idem": {}, "ledger": {}, "ledger_sum": {}}
    data["horse"] = {"seq": 7, "history": [{"no": 6}], "previous": {"id": "r6", "bets": {}},
                     "race": {"id": "r7", "no": 7, "phase": "betting", "bets": {"a": bet(2500), "b:demo": bet(1000), "c": bet(4000, settled=True)}}}
    data["feed"] = [{"t": 3, "user": "ann", "game": "horses", "mult": 4.0, "profit": 30.0},
                    {"t": 2, "user": "bob", "game": "limbo", "mult": 3.0, "profit": 20.0},
                    {"t": 1, "user": "cy", "game": "hilo", "mult": 2.5, "profit": 15.0}]
    data.update(extra)
    return data


class Retire(unittest.TestCase):
    def load(self, data):
        fresh_store()
        store.data = data
        store.load()
        return store.data

    def test_a_stake_riding_on_an_unfinished_race_comes_back_in_full(self):
        d = self.load(old_data())
        self.assertEqual(d["users"]["a"]["balance"], 925.0)
        self.assertEqual(d["users"]["b"]["demo"]["balance"], 410.0, "a practice bet goes back into the practice wallet")
        self.assertEqual(d["users"]["b"]["balance"], 900.0, "and costs nobody's real money")
        (row,) = ledger.entries(d["users"]["a"])
        self.assertEqual((row["amount"], row["reason"], row["ref"]), (25.0, "casino.horses", "r7"))
        self.assertIn("Horses", row["note"])

    def test_a_race_that_was_already_settled_is_left_alone(self):
        d = self.load(old_data())
        self.assertEqual(d["users"]["c"]["balance"], 900.0, "its winnings were paid when it finished")
        self.assertEqual(ledger.entries(d["users"]["c"]), [])

    def test_the_refund_can_never_be_paid_twice(self):
        d = self.load(old_data())
        d["horse"] = old_data()["horse"]                               # the same race turning up again (a restored copy, a retry)
        migrations.retire_horses(d)
        migrations.retire_horses(d)
        self.assertEqual(d["users"]["a"]["balance"], 925.0)
        self.assertEqual(len(ledger.entries(d["users"]["a"])), 1)

    def test_starting_up_again_does_nothing_more(self):
        d = self.load(old_data())
        self.assertEqual(migrations.run(d), [])
        self.assertEqual(d["users"]["a"]["balance"], 925.0)
        self.assertEqual(d["meta"]["schema"], migrations.SCHEMA)

    def test_the_game_leaves_no_state_and_no_horse_wins_on_the_board(self):
        d = self.load(old_data())
        self.assertNotIn("horse", d)
        self.assertEqual([w["game"] for w in d["feed"]], ["limbo", "hilo"], "the other winners stay")
        self.assertEqual((d["meta"]["horses_retired"]["betsRefunded"], d["meta"]["horses_retired"]["refunded"]), (2, 25.0))

    def test_a_site_that_never_had_a_race_is_just_brought_up_to_date(self):
        data = old_data()
        del data["horse"]
        d = self.load(data)
        self.assertEqual([u["balance"] for u in d["users"].values()], [900.0, 900.0, 900.0])
        self.assertEqual((d["meta"]["schema"], d["meta"]["horses_retired"]["betsRefunded"]), (migrations.SCHEMA, 0))

    def test_a_bet_from_somebody_who_no_longer_exists_does_not_stop_the_start_up(self):
        data = old_data()
        data["horse"]["race"]["bets"]["gone"] = bet(500)
        d = self.load(data)
        self.assertEqual(d["users"]["a"]["balance"], 925.0)


class NothingOfItIsLeft(unittest.TestCase):
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

    def test_the_addresses_are_gone(self):
        c = Client(self.port)
        c.call("POST", "/api/auth/register", {"username": "no_horses", "password": "secret123"})
        self.assertEqual(c.call("GET", "/api/games/horses/state")[0], 404)
        self.assertEqual(c.call("POST", "/api/games/horses/bet", {"amount": 10})[0], 404)

    def test_the_casino_has_thirteen_games_and_none_of_them_is_horses(self):
        with open(os.path.join(ROOT, "static", "js", "gamelist.js"), encoding="utf-8") as f:
            ids = [line.split("'")[1] for line in f if line.startswith("  { id: '")]
        self.assertEqual(len(ids), 14, "thirteen games and poker")
        self.assertNotIn("horses", ids)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "backend", "horses.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "static", "js", "games", "horses.js")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "static", "casino-icons", "horses.svg")))


if __name__ == "__main__":
    unittest.main()
