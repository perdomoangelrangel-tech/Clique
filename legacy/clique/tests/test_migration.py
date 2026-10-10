"""Splitting one balance into two accounts: nothing lost, nothing duplicated, nothing reset, and safe to run twice."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, economy, ledger, markets, migrations, users, weekly   # noqa: E402
from backend.store import db, store                                                  # noqa: E402
from backend.util import now_ms, prev_week_key, week_key                             # noqa: E402
from tests.helpers import fresh_store, restore_store_path                            # noqa: E402


def tearDownModule():
    restore_store_path()


def old_style_db(balances):
    """What db.json looked like before the two accounts existed: one `balance` per person, no ledger, no `wk`."""
    wk = week_key()
    data = {"meta": {"week": wk}, "users": {}, "usernames": {}, "sessions": {}, "circles": {}, "markets": {}, "snapshots": {},
            "games": {}, "feed": [], "poker": {}, "social": {}, "chats": {}, "idem": {}}
    for i, (name, bal) in enumerate(balances.items()):
        uid = f"u{i:02d}"
        data["users"][uid] = {"id": uid, "username": name, "salt": "00", "hash": "x", "balance": bal, "createdAt": now_ms() - 30 * 86400000,
                              "stats": {wk: {"deposits": 250.0}} if name == "voucher" else {}, "activity": [], "history": []}
        data["usernames"][name.lower()] = uid
    return data


class SplitAccounts(unittest.TestCase):
    def load(self, data):
        fresh_store()
        store.data = data
        store.load()
        return store.data

    def test_how_balances_are_distributed(self):
        d = self.load(old_style_db({"poor": 300.0, "exact": 1000.0, "emi": 1000.98, "rich": 5000.0, "broke": 0.0}))
        got = {u["username"]: (u["balance"], u["accum"]) for u in d["users"].values()}
        self.assertEqual(got, {"poor": (300.0, 0.0), "exact": (1000.0, 0.0), "emi": (1000.0, 0.98), "rich": (1000.0, 4000.0), "broke": (0.0, 0.0)})

    def test_not_a_cent_is_created_or_lost(self):
        balances = {"a": 1234.56, "b": 0.01, "c": 99999.99, "d": 1000.0, "e": 17.0}
        d = self.load(old_style_db(balances))
        for u in d["users"].values():
            self.assertEqual(ledger.to_cents(u["balance"]) + ledger.to_cents(u["accum"]), ledger.to_cents(balances[u["username"]]))
        self.assertAlmostEqual(sum(u["balance"] + u["accum"] for u in d["users"].values()), sum(balances.values()), places=2)

    def test_it_is_written_in_the_ledger_and_the_books_balance(self):
        d = self.load(old_style_db({"rich": 5000.0, "poor": 300.0}))
        for u in d["users"].values():
            self.assertEqual(ledger.audit(u), {"weekly": 0, "accumulated": 0})
            self.assertTrue(all(r["reason"] == "opening" for r in ledger.entries(u)))
        rich = next(u for u in d["users"].values() if u["username"] == "rich")
        self.assertEqual({(r["account"], r["amount"]) for r in ledger.entries(rich)}, {("weekly", 1000.0), ("accumulated", 4000.0)})
        self.assertEqual(d["meta"]["accounts_migration"]["people"], 2)
        self.assertEqual(d["meta"]["accounts_migration"]["movedToAccumulated"], 4000.0)

    def test_running_it_again_changes_nothing(self):
        d = self.load(old_style_db({"rich": 5000.0}))
        snapshot = json.dumps(d, sort_keys=True)
        self.assertEqual(migrations.run(d), [])
        self.assertEqual(json.dumps(d, sort_keys=True), snapshot)
        store.load()
        self.assertEqual(json.dumps(store.data, sort_keys=True), snapshot)

    def test_this_weeks_leaderboard_is_not_disturbed(self):
        d = self.load(old_style_db({"rich": 5000.0, "voucher": 1250.0}))
        # before: net worth 5000, started the week from the START_BALANCE snapshot rule, no deposits => performance 4000
        rich = next(u for u in d["users"].values() if u["username"] == "rich")
        voucher = next(u for u in d["users"].values() if u["username"] == "voucher")
        c = {"members": {rich["id"]: 0, voucher["id"]: 0}}
        before_rich = round(5000.0 - weekly.start_value(rich, week_key()) - 0, 2)
        before_voucher = round(1250.0 - weekly.start_value(voucher, week_key()) - 250.0, 2)
        rows = {r["user"]["username"]: r for r in weekly.standings(c, week_key())}
        self.assertEqual(rows["rich"]["delta"], before_rich)
        self.assertEqual(rows["voucher"]["delta"], before_voucher)
        self.assertEqual(rows["rich"]["value"], 1000.0, "what they hold in the weekly game is now the weekly account")

    def test_nobody_is_reset_and_their_history_and_stats_are_kept(self):
        data = old_style_db({"rich": 5000.0})
        uid = next(iter(data["users"]))
        data["users"][uid]["history"] = [{"id": "h1", "game": "dice", "bet": 5, "payout": 10}]
        data["users"][uid]["stats"] = {week_key(): {"gamesPlayed": 3, "marketBets": 2}}
        data["users"][uid]["activity"] = [{"t": 1, "kind": "buy", "amount": -5, "text": "Bought"}]
        d = self.load(data)
        u = d["users"][uid]
        self.assertEqual((u["history"][0]["id"], u["stats"][week_key()]["gamesPlayed"], u["activity"][0]["kind"]), ("h1", 3, "buy"))

    def test_a_week_close_right_after_the_migration_works(self):
        d = self.load(old_style_db({"a": 5000.0, "b": 800.0, "c": 1000.0}))
        for u in d["users"].values():
            users.stat_add(u, "marketBets")
        circ = circles.create(next(iter(d["users"].values())), {"name": "Old crew"})
        for u in d["users"].values():
            circ["members"][u["id"]] = 0
        circ["createdAt"] = 0
        d["meta"]["requirements_from"] = "9999-12-31"                   # this test is about the migration, not the weekly minimum
        weekly.finalize_week(week_key())
        self.assertTrue(circ["recaps"][week_key()]["rewards"])
        for u in d["users"].values():
            self.assertEqual(ledger.audit(u), {"weekly": 0, "accumulated": 0})

    def test_loading_a_saved_old_file_from_disk_migrates_it_and_makes_a_backup(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "db.json")
        with open(path, "w") as f:
            json.dump(old_style_db({"rich": 5000.0}), f)
        store.path, store.data = path, {}
        store.load()
        self.assertEqual(store.migrated, ["split_accounts", "retire_horses", "add_goals", "add_game_goals"])
        self.assertEqual(next(iter(store.data["users"].values()))["accum"], 4000.0)
        backups = os.listdir(os.path.join(folder, "backups"))
        self.assertEqual(len(backups), 1)
        with open(os.path.join(folder, "backups", backups[0])) as f:
            self.assertNotIn("accum", next(iter(json.load(f)["users"].values())), "the backup is the file exactly as it was")
        store.save()
        store.data = {}
        store.load()
        self.assertEqual(store.migrated, [], "the second start-up has nothing left to do")

    def test_the_preview_script_shows_the_split_checks_the_books_and_never_writes(self):
        import hashlib
        import subprocess
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "db.json")
        with open(path, "w") as f:
            json.dump(old_style_db({"poor": 300.0, "emi": 1000.98, "rich": 5000.0}), f)
        with open(path, "rb") as f:
            before = hashlib.sha256(f.read()).hexdigest()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run([sys.executable, os.path.join(root, "scripts", "preview_migration.py"), path], capture_output=True, text=True, cwd=root, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("rich", r.stdout)
        self.assertIn("4,000.00", r.stdout)
        self.assertIn("difference: $0.00", r.stdout)
        self.assertIn("every account's history adds up", r.stdout)
        with open(path, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), before, "a preview must not change the file")
        self.assertFalse(os.path.exists(os.path.join(folder, "backups")), "and must not leave copies around either")

    def test_a_brand_new_empty_database_just_records_its_version(self):
        d = self.load({})
        self.assertEqual(d["meta"]["schema"], migrations.SCHEMA)


if __name__ == "__main__":
    unittest.main()
