"""Helpers for the economy tests: people with known accounts and a known starting line for the week."""
from backend import circles, ledger, markets, users
from backend.util import DAY_MS, now_ms, week_key


def mk(name, weekly=1000.0, accum=0.0, age_days=30, active=True):
    """An account that has been around for `age_days`, holding exactly `weekly` / `accum`, whose week starts from there."""
    u = users.register(name, "secret123")
    u["createdAt"] = now_ms() - int(age_days * DAY_MS)
    for acct, target in (("weekly", weekly), ("accumulated", accum)):             # through the ledger, so the books balance
        diff = float(target) - ledger.balance(u, acct)
        if abs(diff) > 0.001:
            ledger.post(u, acct, diff, "test.setup")
    u["wk"] = {"week": week_key(), "start_c": ledger.to_cents(markets.net_worth(u)), "ext_c": 0}
    if active:
        users.stat_add(u, "marketBets")
    return u


def circle_of(owner, *others, name="Crew", age_days=30):
    c = circles.create(owner, {"name": name})
    c["createdAt"] = now_ms() - int(age_days * DAY_MS)
    c["members"][owner["id"]] = c["createdAt"]
    for o in others:
        circles.join_by_code(o, c["inviteCode"])
        c["members"][o["id"]] = c["createdAt"]
    return c


def gain(u, amount):
    """Win (or lose) `amount` this week by playing: moves the weekly account, not an external flow."""
    ledger.post(u, "weekly", amount, "test.play")


def books_balance(u):
    return ledger.audit(u) == {"weekly": 0, "accumulated": 0}
