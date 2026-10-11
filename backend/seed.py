"""Starting over. Two tools, used by scripts/seed.py and by the SEASON_RESET setting:

  new_season  keeps every account (same usernames and passwords) and every circle, and gives
              everyone the starting balance again. Markets, positions, game history, weekly
              recaps and the win feed are cleared.
  wipe        deletes everything, accounts included.

Both write a copy of the old database to <data folder>/backups first (Store.load does that)."""
import os

from . import config, ledger
from .store import store
from .util import now_ms, round2

_SHARED = ("markets", "snapshots", "games", "poker")      # poker tables go too: balances are reset anyway


def new_season(data):
    # Always the same START_BALANCE that new sign-ups get: the weekly standings measure from it.
    balance = round2(config.START_BALANCE)
    for key in _SHARED:
        data[key] = {}
    data["feed"] = []
    saved, store.data = store.data, data                    # the ledger writes into the database being reset, whichever it is
    try:
        for user in data["users"].values():                 # through the ledger, as money from outside the game (D2)
            change = balance - ledger.balance(user, "weekly")
            if change:
                ledger.post(user, "weekly", change, "season.reset", external=True, note="New season")
    finally:
        store.data = saved
    for user in data["users"].values():
        user["stats"], user["history"] = {}, []
        user["activity"] = [{"t": now_ms(), "kind": "start", "amount": balance, "text": "New season"}]
        for perk in ("voucher", "passGo", "demo"):        # a new season starts with a fresh voucher and practice wallet
            user.pop(perk, None)
    for circle in data["circles"].values():
        circle["punishments"], circle["recaps"] = {}, {}
    return {"users": len(data["users"]), "circles": len(data["circles"]), "balance": balance}


def wipe(data):
    summary = {"users": len(data["users"]), "circles": len(data["circles"]), "markets": len(data["markets"])}
    for key in ("users", "usernames", "sessions", "circles", *_SHARED, "meta"):
        data[key] = {}
    data["feed"] = []
    return summary


def season_reset_if_requested(store):
    """Hosted copies have no shell, so SEASON_RESET=<any label> starts a new season once. The label
    is remembered in the data folder, so a redeploy with the same label does nothing; use a new
    label (for example 2026-w42) to reset again. Returns the summary if a reset happened."""
    label = config.SEASON_RESET
    marker = os.path.join(os.path.dirname(store.path), "season-marker")
    if not label:
        return None
    try:
        with open(marker, "r", encoding="utf-8") as f:
            if f.read().strip() == label:
                return None
    except OSError:
        pass
    summary = new_season(store.data)
    store.save()
    with open(marker, "w", encoding="utf-8") as f:
        f.write(label)
    return {"label": label, **summary}
