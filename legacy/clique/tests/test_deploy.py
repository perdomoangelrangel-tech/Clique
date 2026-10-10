"""Things that only matter once the site is hosted: refusing a weak setup, starting over, brute-force limits."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, ROOT)

from backend import config, seed, users                    # noqa: E402
from backend.store import Store, store                     # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path   # noqa: E402


def run_py(args, env=None, stdin=None):
    full = {**os.environ, **(env or {})}
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=full, input=stdin,
                          capture_output=True, text=True, timeout=30)


def populated_store(path):
    """A database with two accounts, a circle, a market and some history, as a real one would have."""
    s = Store(path)
    s.load()
    saved = store.data
    store.data = s.data                       # users.register writes through the shared db() handle
    try:
        a = users.register("alice", "secret123")
        b = users.register("bobby", "secret456")
        a["balance"], b["balance"] = 40.0, 5000.0
        a["history"].append({"game": "limbo", "profit": 3.0})
        a["stats"]["2026-09-28"] = {"gamePnl": 3.0}
        s.data["circles"]["c1"] = {"id": "c1", "name": "Crew", "ownerId": a["id"], "members": {a["id"]: 1, b["id"]: 1},
                                   "inviteCode": "ABC234", "visibility": "private", "createdAt": 1,
                                   "punishments": {"2026-09-28": [{"id": "p"}]}, "recaps": {"2026-09-21": {"week": "x"}}}
        s.data["markets"]["m1"] = {"id": "m1"}
        s.data["snapshots"]["2026-09-21"] = {a["id"]: 900.0}
        s.data["feed"].append({"user": "alice"})
        s.data["games"][a["id"]] = {"chicken": {"bet": 5}}
        s.save()
    finally:
        store.data = saved
    return s


class StartingOver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "db.json")
        self.s = populated_store(self.path)

    def test_new_season_keeps_accounts_and_circles_but_resets_money(self):
        d = self.s.data
        result = seed.new_season(d)
        self.assertEqual(result["users"], 2)
        self.assertEqual({u["balance"] for u in d["users"].values()}, {config.START_BALANCE})
        self.assertEqual(sorted(d["usernames"]), ["alice", "bobby"])
        self.assertEqual(d["markets"], {})
        self.assertEqual(d["snapshots"], {})
        self.assertEqual(d["games"], {})
        self.assertEqual(d["feed"], [])
        for u in d["users"].values():
            self.assertEqual((u["stats"], u["history"]), ({}, []))
            self.assertEqual(len(u["activity"]), 1)
        crew = d["circles"]["c1"]
        self.assertEqual((crew["punishments"], crew["recaps"]), ({}, {}))
        self.assertEqual(len(crew["members"]), 2)
        self.assertEqual(crew["inviteCode"], "ABC234")

    def test_new_season_accounts_can_still_log_in(self):
        seed.new_season(self.s.data)
        saved = store.data
        store.data = self.s.data
        try:
            users._attempts.clear()
            self.assertEqual(users.login("ALICE", "secret123")["balance"], config.START_BALANCE)
        finally:
            store.data = saved

    def test_wipe_deletes_everything(self):
        d = self.s.data
        seed.wipe(d)
        for key in ("users", "usernames", "sessions", "circles", "markets", "snapshots", "games", "meta"):
            self.assertEqual(d[key], {}, key)
        self.assertEqual(d["feed"], [])

    def test_season_reset_setting_runs_once_per_label(self):
        old = config.SEASON_RESET
        try:
            config.SEASON_RESET = ""
            self.assertIsNone(seed.season_reset_if_requested(self.s))
            self.assertEqual(self.s.data["users"][next(iter(self.s.data["users"]))]["balance"], 40.0)

            config.SEASON_RESET = "2026-w42"
            first = seed.season_reset_if_requested(self.s)
            self.assertEqual(first["label"], "2026-w42")
            self.assertTrue(all(u["balance"] == config.START_BALANCE for u in self.s.data["users"].values()))

            next(iter(self.s.data["users"].values()))["balance"] = 7.0      # play a little
            self.assertIsNone(seed.season_reset_if_requested(self.s), "same label must not reset again on redeploy")
            self.assertEqual(next(iter(self.s.data["users"].values()))["balance"], 7.0)

            config.SEASON_RESET = "2026-w43"
            self.assertIsNotNone(seed.season_reset_if_requested(self.s))
            self.assertEqual(next(iter(self.s.data["users"].values()))["balance"], config.START_BALANCE)
        finally:
            config.SEASON_RESET = old


class SeedScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        populated_store(os.path.join(self.tmp, "db.json"))
        self.env = {"DATA_DIR": self.tmp, "PORT": "1"}      # port 1: nothing listens there

    def read(self):
        with open(os.path.join(self.tmp, "db.json")) as f:
            return json.load(f)

    def test_declining_changes_nothing(self):
        r = run_py(["scripts/seed.py", "new-season"], self.env, stdin="nope\n")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("Nothing was changed", r.stdout)
        self.assertEqual(sorted(u["balance"] for u in self.read()["users"].values()), [40.0, 5000.0])

    def test_new_season_with_backup(self):
        r = run_py(["scripts/seed.py", "new-season", "--yes"], {**self.env, "START_BALANCE": "2500"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        d = self.read()
        self.assertEqual({u["balance"] for u in d["users"].values()}, {2500.0})
        backups = os.listdir(os.path.join(self.tmp, "backups"))
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.tmp, "backups", backups[0])) as f:
            self.assertEqual(sorted(u["balance"] for u in json.load(f)["users"].values()), [40.0, 5000.0])

    def test_refuses_while_the_server_is_running(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            r = run_py(["scripts/seed.py", "wipe", "--yes"], {**self.env, "PORT": str(listener.getsockname()[1])})
        self.assertEqual(r.returncode, 1)
        self.assertIn("Stop the Clique server first", r.stdout)
        self.assertEqual(len(self.read()["users"]), 2)


class ProductionSettings(unittest.TestCase):
    def import_config(self, **env):
        base = {k: v for k, v in os.environ.items() if k not in ("ADMIN_PASSWORD", "CLIQUE_ENV", "START_BALANCE")}
        return subprocess.run([sys.executable, "-c", "from backend import config; print(config.START_BALANCE)"],
                              cwd=ROOT, env={**base, **env}, capture_output=True, text=True, timeout=30)

    def test_production_refuses_the_built_in_or_a_short_password(self):
        for env in ({"CLIQUE_ENV": "production"},
                    {"CLIQUE_ENV": "production", "ADMIN_PASSWORD": "local-test-only-password"},
                    {"CLIQUE_ENV": "production", "ADMIN_PASSWORD": "short"}):
            r = self.import_config(**env)
            self.assertNotEqual(r.returncode, 0, env)
            self.assertIn("ADMIN_PASSWORD", r.stderr)

    def test_production_starts_with_your_own_password(self):
        r = self.import_config(CLIQUE_ENV="production", ADMIN_PASSWORD="a-long-private-phrase")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_local_use_is_unchanged(self):
        r = self.import_config()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1000.0")

    def test_start_balance_setting(self):
        self.assertEqual(self.import_config(START_BALANCE="2500").stdout.strip(), "2500.0")
        for bad in ("abc", "0", "-5", "1e12"):
            self.assertNotEqual(self.import_config(START_BALANCE=bad).returncode, 0, bad)


class BruteForceLimits(unittest.TestCase):
    def setUp(self):
        fresh_store()

    def tearDown(self):
        restore_store_path()

    def test_login_is_limited_per_username_even_if_the_ip_keeps_changing(self):
        users.register("victim", "correct-horse")
        for i in range(15):
            with self.assertRaises(ApiError):
                users.login("victim", "wrong-guess", ip=f"10.0.0.{i}")
        with self.assertRaises(ApiError) as cm:
            users.login("victim", "correct-horse", ip="10.9.9.9")
        self.assertEqual(cm.exception.status, 429)

    def test_funds_password_guesses_are_limited_across_accounts(self):
        accounts = [users.register(f"guesser{i}", "secret123") for i in range(6)]
        wrong = 0
        for acct in accounts:
            for _ in range(4):
                if wrong >= 20:
                    break
                with self.assertRaises(ApiError) as cm:
                    users.deposit(acct, 10, "not-the-password")
                self.assertEqual(cm.exception.status, 403)
                wrong += 1
        self.assertEqual(wrong, 20)
        fresh = accounts[5]
        with self.assertRaises(ApiError) as cm:
            users.deposit(fresh, 10, config.ADMIN_PASSWORD)       # even the right password waits it out
        self.assertEqual(cm.exception.status, 429)


if __name__ == "__main__":
    unittest.main()
