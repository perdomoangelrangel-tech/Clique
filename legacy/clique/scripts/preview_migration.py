#!/usr/bin/env python3
"""Shows what the pending data migrations (two accounts, the Horses removal, loans/ranks/challenges/milestones/transfers) will do to a database,
WITHOUT changing anything.

    python3 scripts/preview_migration.py                 # reads data/db.json (or $DATA_DIR/db.json)
    python3 scripts/preview_migration.py path/to/db.json

It loads the file into memory, runs the very same migration the server runs on start-up, prints each person's balance before
and after, and checks that no money appeared or vanished. It never writes to the file, and the real migration also makes a
timestamped copy of db.json in backups/ before it touches anything.
"""
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from backend import economy, ledger, migrations, rules     # noqa: E402
from backend.store import store                     # noqa: E402


def main(argv):
    path = argv[1] if len(argv) > 1 else os.path.join(os.environ.get("DATA_DIR") or os.path.join(HERE, "data"), "db.json")
    if not os.path.exists(path):
        print(f"No database at {path}")
        return 1
    with open(path, "rb") as f:
        raw = f.read()
    before_hash = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw)
    version = (d.get("meta") or {}).get("schema", 1)
    print(f"Database: {path}\nSchema version now: {version}   Weekly allocation: ${economy.WEEKLY_ALLOCATION:,.2f}\n")
    if version >= migrations.SCHEMA:
        print("Already up to date. Nothing to do.")
        return 0

    work = copy.deepcopy(d)
    work.setdefault("meta", {})
    old_data = store.data
    store.data = work                                # some steps read the loaded database; this one is a throw-away copy
    try:
        ran = migrations.run(work)
        problems = [u["username"] for u in work["users"].values() if ledger.audit(u) != {"weekly": 0, "accumulated": 0}]     # the audit reads the loaded copy
    finally:
        store.data = old_data
    print(f"Steps that would run: {', '.join(ran) or 'none'}\n")

    print(f"{'person':<20}{'balance now':>14}{'weekly after':>14}{'accumulated after':>19}")
    total_before = total_after = 0
    for uid, u in sorted(d["users"].items(), key=lambda kv: kv[1]["username"].lower()):
        new = work["users"][uid]
        b = ledger.to_cents(u.get("balance", 0))
        w, a = ledger.to_cents(new["balance"]), ledger.to_cents(new["accum"])
        total_before += b
        total_after += w + a
        print(f"{u['username'][:19]:<20}{b / 100:>14,.2f}{w / 100:>14,.2f}{a / 100:>19,.2f}")
    print(f"\nTotal money before: ${total_before / 100:,.2f}   after: ${total_after / 100:,.2f}   difference: ${(total_after - total_before) / 100:,.2f}")

    ok = total_before == total_after and not problems
    print("Ledger check: " + ("every account's history adds up to its balance." if not problems else "DOES NOT ADD UP for: " + ", ".join(problems)))
    note = (work.get("meta") or {}).get("accounts_migration") or {}
    print(f"Moved to the accumulated account in total: ${note.get('movedToAccumulated', 0):,.2f} (everything above the weekly allocation).")

    if "add_goals" in ran:
        print("\nLoans, ranks, challenges, milestones and transfers are added without changing any balance. From the old records only:")
        for uid, u in sorted(work["users"].items(), key=lambda kv: kv[1]["username"].lower()):
            g = u.get("goals") or {}
            tiers = {t["id"]: t for t in rules.milestone_tiers()}
            worth = sum(tiers[t]["money_c"] for t in g.get("done", {}) if t in tiers) / 100
            print(f"  {u['username'][:19]:<20}{len(g.get('done', {})):>3} milestone tiers unlocked (worth ${worth:,.2f} once claimed, nothing is paid automatically), XP {g.get('xp', 0)}")

    with open(path, "rb") as f:
        untouched = hashlib.sha256(f.read()).hexdigest() == before_hash
    print("The database file was not changed." if untouched else "WARNING: the file changed while this ran.")
    return 0 if ok and untouched else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
