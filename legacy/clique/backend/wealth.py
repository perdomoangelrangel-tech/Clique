"""One answer to "where is all my money?": the Portfolio page.

Two accounts, so two pictures:
  * WEEKLY account (this week's chips): the cash in it, plus what it is working on right now. Open poll bets at what they
    would pay if cashed out, stakes in casino rounds still being played, and real money at a poker table.
    (These are the same pieces the weekly leaderboard adds up to say what you "hold".)
  * ACCUMULATED account (what you keep): the cash in it, plus the shares you own on the Exchange at what they would sell for
    right now (the bid).
Below those: every share held and every poll bet, open and settled.

Everything is read from the server's own books at the moment of asking and nothing here changes anything, so the page can
never show a number the rest of the site disagrees with. Practice (demo) money is not part of it.
"""
from . import exchange, games, ledger, loans, markets, poker
from .util import ApiError, round2


def _part(key, label, amount, note):
    return {"key": key, "label": label, "amount": round2(amount), "note": note}


def overview(user):
    uid = user["id"]
    mk = markets.portfolio(user)
    try:
        ex = exchange.portfolio(user)
    except ApiError:                                  # the exchange is not open (it has not started yet): no shares to show
        ex = None

    weekly_parts = [
        _part("cash", "Cash", ledger.balance(user, "weekly"), "Spendable now: bets, casino, poker."),
        _part("polls", "Open poll bets", mk["positionsValue"], "What they would pay if you cashed out right now."),
        _part("casino", "Casino rounds in play", games.escrow(uid), "Stakes in rounds you have not finished."),
        _part("poker", "At a poker table", poker.real_stake(uid), "Real money in front of you at a table."),
    ]
    if loans.owed_c(user):                                       # a debt is subtracted, exactly as the weekly leaderboard does
        weekly_parts.append(_part("debt", "Loan owed", -loans.owed(user), "What you still owe. It is paid from the weekly account only."))
    accumulated_parts = [
        _part("cash", "Cash", ledger.balance(user, "accumulated"), "Spendable now: the Store and the Exchange."),
        _part("stocks", "Shares", ex["stockValue"] if ex else 0.0, "What they would sell for right now."),
    ]
    weekly_total = round2(sum(p["amount"] for p in weekly_parts))
    accumulated_total = round2(sum(p["amount"] for p in accumulated_parts))
    open_rows = mk["open"]
    return {
        "weekly": {"total": weekly_total, "parts": weekly_parts},
        "accumulated": {"total": accumulated_total, "parts": accumulated_parts},
        "total": round2(weekly_total + accumulated_total),
        "stocks": None if ex is None else {
            "positions": ex["positions"], "value": ex["stockValue"], "invested": ex["invested"],
            "unrealized": ex["unrealized"], "realized": ex["realized"]},
        "polls": {"open": open_rows, "closed": mk["closed"][:30], "openValue": mk["positionsValue"],
                  "openInvested": round2(sum(r["invested"] for r in open_rows)),
                  "openPnl": round2(sum(r.get("pnl", 0) for r in open_rows))},
    }
