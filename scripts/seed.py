#!/usr/bin/env python3
"""Start over on your own computer (or any machine where you can run commands).

  python3 scripts/seed.py new-season   keep accounts and circles, everyone back to the starting balance
  python3 scripts/seed.py wipe         delete everything, accounts included

STOP THE SERVER FIRST. A running server keeps the database in memory and would write its old
copy back over the reset. Nothing is changed until you type RESET (or pass --yes), and a copy of the
current database is saved in <data folder>/backups before anything is touched.

The data folder is ./data unless DATA_DIR is set. The starting balance is 1000 unless START_BALANCE is set.
On a hosted copy use the SEASON_RESET setting instead (see DEPLOY.md)."""
import argparse
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config, seed                       # noqa: E402
from backend.store import store                        # noqa: E402


def server_is_running():
    try:
        with socket.create_connection(("127.0.0.1", config.PORT), timeout=0.5):
            return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["new-season", "wipe"])
    ap.add_argument("--yes", action="store_true", help="skip the typed confirmation")
    ap.add_argument("--force", action="store_true", help="run even though something is listening on the server port")
    args = ap.parse_args()

    if not os.path.exists(store.path):
        print(f"Nothing to reset: {store.path} does not exist yet.")
        return 0
    if server_is_running() and not args.force:
        print(f"Something is listening on port {config.PORT}. Stop the Clique server first, then run this again.")
        return 1

    store.load()          # also saves a backup copy
    d = store.data
    print(f"Database: {store.path}")
    print(f"  {len(d['users'])} accounts, {len(d['circles'])} circles, {len(d['markets'])} markets")
    if args.mode == "new-season":
        print(f"new-season: accounts and circles stay; everyone gets ${config.START_BALANCE:,.2f}; markets, positions, history and recaps are cleared.")
    else:
        print("wipe: EVERYTHING is deleted, accounts included.")
    print(f"A backup copy is saved in {os.path.join(os.path.dirname(store.path), 'backups')} first.")
    if not args.yes and input("Type RESET to continue: ").strip() != "RESET":
        print("Cancelled. Nothing was changed.")
        return 1

    summary = seed.new_season(d) if args.mode == "new-season" else seed.wipe(d)
    store.save()
    print("Done.", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
