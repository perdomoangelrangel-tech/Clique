"""The ledger: every movement of money in or out of an account, written down once.

Clique has two accounts per person (all pretend money):
    weekly       user["balance"]  chips for this week's bets, casino and poker
    accumulated  user["accum"]    what you keep: weekly rewards in, Store and Stock Exchange spending out

Every change to either account goes through post() below. It works in whole cents (integers), so nothing is ever
rounded twice, refuses to take more than an account holds, clamps at the global ceiling, and records a row with a
transaction id, the account, the amount, the balance afterwards, the reason and the time. A caller may pass its own
transaction id (txid): posting the same txid twice does nothing the second time, which is how retries stay harmless.

The practice (demo) wallet is not an account and never appears here.

Storage: db["ledger"][user id] holds the newest LEDGER_KEEP rows in full. Older rows are folded into
db["ledger_sum"][user id][week][account][reason] = {"n": rows, "c": cents}, so the books always add up
(audit() checks that) without the database growing forever.
"""
import contextlib
import math
import threading

from . import config, economy
from .store import db
from .util import bad, new_id, now_ms, week_key

ACCOUNTS = ("weekly", "accumulated")
FIELD = {"weekly": "balance", "accumulated": "accum"}
LABEL = {"weekly": "Weekly account", "accumulated": "Accumulated account"}

_ctx = threading.local()


def to_cents(x):
    return int(math.floor(x * 100 + 0.5))


def to_dollars(c):
    return round(c / 100, 2)


@contextlib.contextmanager
def source(label):
    """Names what the code inside is doing, for any money it moves without saying why ("casino.dice")."""
    before = getattr(_ctx, "label", None)
    _ctx.label = label
    try:
        yield
    finally:
        _ctx.label = before


def current_reason():
    return getattr(_ctx, "label", None) or "other"


def balance_c(user, account):
    return to_cents(user.get(FIELD[account], 0.0))


def balance(user, account):
    return to_dollars(balance_c(user, account))


def _rows(uid):
    return db().setdefault("ledger", {}).setdefault(uid, [])


def find(user, txid):
    for row in reversed(_rows(user["id"])):
        if row.get("i") == txid:
            return row
    return None


def _compact(uid):
    rows = _rows(uid)
    if len(rows) <= economy.LEDGER_KEEP + 50:
        return
    old, rows[:] = rows[:-economy.LEDGER_KEEP], rows[-economy.LEDGER_KEEP:]
    sums = db().setdefault("ledger_sum", {}).setdefault(uid, {})
    for r in old:
        cell = sums.setdefault(week_key(r["t"]), {}).setdefault(r["a"], {}).setdefault(r["r"], {"n": 0, "c": 0})
        cell["n"] += 1
        cell["c"] += r["c"]


def post(user, account, amount, reason=None, *, ref=None, external=False, txid=None, note=None):
    """Moves `amount` dollars into (+) or out of (-) one account and records it. Returns the ledger row.

    external=True marks money that arrived from, or left for, outside the game (a top-up, a gift, the weekly refill):
    it never counts as the person's weekly performance."""
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account!r}")
    if txid:
        prior = find(user, txid)
        if prior is not None:
            return prior
    delta = to_cents(amount)
    field = FIELD[account]
    have = to_cents(user.get(field, 0.0))
    if delta < 0 and have + delta < 0:
        raise bad("Not enough funds" if account == "weekly" else "Not enough in your accumulated account", code="insufficient_funds")
    cap = to_cents(config.MAX_BALANCE)
    new = min(cap, have + delta)
    delta = new - have
    user[field] = to_dollars(new)
    row = {"id": new_id(), "t": now_ms(), "a": account, "c": delta, "b": new, "r": reason or current_reason()}
    if ref:
        row["x"] = ref
    if note:
        row["n"] = note
    if txid:
        row["i"] = txid
    if external:
        row["e"] = 1
        if account == "weekly":
            wk = user.setdefault("wk", {})
            wk["ext_c"] = wk.get("ext_c", 0) + delta
    _rows(user["id"]).append(row)
    _compact(user["id"])
    return row


def opening(user, account, cents, note):
    """Writes down a balance that already existed when the ledger was introduced. Changes no balance."""
    row = {"id": new_id(), "t": now_ms(), "a": account, "c": int(cents), "b": balance_c(user, account), "r": "opening", "n": note, "e": 1}
    _rows(user["id"]).append(row)
    return row


def audit(user):
    """Do the rows and the summaries add up to what each account holds? Returns {account: difference in cents}."""
    out = {a: 0 for a in ACCOUNTS}
    for r in _rows(user["id"]):
        out[r["a"]] += r["c"]
    for week in (db().get("ledger_sum", {}).get(user["id"]) or {}).values():
        for acct, reasons in week.items():
            out[acct] += sum(cell["c"] for cell in reasons.values())
    return {a: balance_c(user, a) - out[a] for a in ACCOUNTS}


def entries(user, account=None, limit=100, before=None):
    """The newest rows first, in dollars, for the statement."""
    out = []
    for r in reversed(_rows(user["id"])):
        if account and r["a"] != account:
            continue
        if before and r["t"] >= before:
            continue
        out.append({"id": r["id"], "t": r["t"], "account": r["a"], "amount": r["c"] / 100, "balance": r["b"] / 100,
                    "reason": r["r"], "ref": r.get("x"), "note": r.get("n"), "external": bool(r.get("e"))})
        if len(out) >= limit:
            break
    return out


def summaries(user):
    """Older activity folded by week, account and reason."""
    rows = []
    for week, accts in sorted((db().get("ledger_sum", {}).get(user["id"]) or {}).items(), reverse=True):
        for acct, reasons in accts.items():
            for reason, cell in sorted(reasons.items()):
                rows.append({"week": week, "account": acct, "reason": reason, "count": cell["n"], "amount": cell["c"] / 100})
    return rows


def weekly_flow(user, week=None):
    """What moved in the weekly account this week, by reason (from the rows still held in full)."""
    start_key = week or week_key()
    out = {}
    for r in _rows(user["id"]):
        if r["a"] == "weekly" and week_key(r["t"]) == start_key:
            out[r["r"]] = out.get(r["r"], 0) + r["c"]
    return {k: v / 100 for k, v in out.items()}
