"""Loans: pretend money lent into the WEEKLY account, repaid from the WEEKLY account.

THE RULES (every number is a setting in economy.py; ECONOMY.md section 7 has the reasoning):
  * One loan at a time. Nothing more can be borrowed while any of it is still owed.
  * A loan is at most LOAN_MAX_PCT_OF_ALLOCATION of the weekly allocation, and never takes your weekly holdings (cash plus what
    your bets and rounds are worth) above the allocation itself. So a loan can top you back up to the starting line of the
    week, but it cannot be used to play with more chips than anybody else started with.
  * It is interest-free by default. If LOAN_FEE is set it is one fixed amount per loan, shown before you borrow and counted as
    owed from the start.
  * It must be repaid before the week closes, so nobody can borrow in the last LOAN_CUTOFF_H hours. A brand-new account cannot
    borrow yet (LOAN_MIN_ACCOUNT_AGE_H), and at most LOAN_MAX_PER_WEEK loans can be started in a week.
  * Repaying can be partial. Only the weekly account is ever charged: never the accumulated account, never shares, never items.
  * At the weekly close, whatever weekly funds you have are collected toward the debt BEFORE the account is reset. What is still
    owed stays owed across the reset (a debt cannot be forgiven by waiting, logging out, retrying or the new week), and the
    next weekly allocation pays LOAN_ALLOC_REPAY_PCT of itself toward it first; the rest is yours to spend.

MONEY AND PERFORMANCE. Borrowed money is not income. What you owe is subtracted when your net worth is worked out
(markets.net_worth), so borrowing changes nothing about your weekly performance or your standing: the cash goes up by exactly what
the debt goes up by (a fee, if any, is a real cost and shows up as one). Repayments and collections are likewise neutral. None of
it is a casino or trading result, none of it is XP, a challenge or a milestone (backend/activity.py never sees it), and the weekly
allocation that pays a debt is still an external credit like any other allocation.

STORAGE. db["loans"][id] is the record (principal, fee, what is still owed, every payment); user["loanId"] points at the one in
force. Every change goes through the ledger with a stable transaction id and is all-or-nothing (txn.Txn).
"""
from . import economy, idem, inbox, ledger, users
from .store import db
from .txn import Txn
from .util import bad, new_id, now_ms, parse_money, week_bounds, week_key

HOUR_MS = 3_600_000


def _loans():
    return db().setdefault("loans", {})


def active(user):
    lid = user.get("loanId")
    loan = _loans().get(lid) if lid else None
    return loan if loan and loan["status"] == "active" else None


def owed_c(user):
    """What this person owes right now, in cents (0 if nothing)."""
    loan = active(user)
    return loan["owed_c"] if loan else 0


def owed(user):
    return owed_c(user) / 100


def _holdings_c(user):
    """Weekly cash plus what bets and rounds in play are worth, before subtracting any debt."""
    from . import markets                                  # imported here: markets uses this module for net worth
    return ledger.balance_c(user, "weekly") + ledger.to_cents(markets.open_positions_value(user["id"]))


def holdings_c(user):
    """Weekly cash plus what bets and rounds in play are worth, before any debt (in cents)."""
    return _holdings_c(user)


def _money(value, field="Amount"):
    x = parse_money(value, field)
    if x <= 0:
        raise bad("Enter an amount greater than 0", code="amount_not_positive")
    c = ledger.to_cents(x)
    if abs(x * 100 - c) > 1e-6:
        raise bad("Use at most two decimals", code="too_many_decimals")
    return c


def _count_this_week(user, wk):
    return sum(1 for lid in user.get("loans", []) if (_loans().get(lid) or {}).get("week") == wk)


def limits(user, now=None):
    """Can this person borrow right now, how much, and if not, exactly why not."""
    now = now_ms() if now is None else now
    wk = week_key(now)
    _, end = week_bounds(wk)
    alloc_c = ledger.to_cents(economy.WEEKLY_ALLOCATION)
    cap_c = alloc_c * int(economy.LOAN_MAX_PCT_OF_ALLOCATION * 100) // 10_000
    holdings = _holdings_c(user)
    room_c = max(0, alloc_c - holdings)
    available = min(cap_c, room_c)
    min_c = ledger.to_cents(economy.LOAN_MIN)
    loan = active(user)
    reasons = []
    if not economy.LOANS_ENABLED:
        reasons.append("Loans are switched off.")
    if loan:
        reasons.append("You still owe a loan. Repay it first, then you can borrow again." + (" It is overdue." if now >= loan["dueAt"] or loan.get("overdue") else ""))
    age_h = (now - user["createdAt"]) / HOUR_MS
    if age_h < economy.LOAN_MIN_ACCOUNT_AGE_H:
        left = economy.LOAN_MIN_ACCOUNT_AGE_H - age_h
        reasons.append(f"Loans open {economy.LOAN_MIN_ACCOUNT_AGE_H:g} hours after you join. About {left:.0f} to go.")
    taken = _count_this_week(user, wk)
    if taken >= economy.LOAN_MAX_PER_WEEK:
        reasons.append(f"You already took {taken} loan{'s' if taken != 1 else ''} this week, the most allowed. Next week you can borrow again.")
    if end - now < economy.LOAN_CUTOFF_H * HOUR_MS:
        reasons.append(f"Borrowing closes {economy.LOAN_CUTOFF_H:g} hours before the week ends, so a loan can be repaid in time. It opens again when the new week starts.")
    if not loan and available < min_c:
        if cap_c <= 0:
            reasons.append("There is no weekly allocation to borrow against.")
        elif room_c < min_c:
            reasons.append(f"A loan can only top you back up to the weekly allocation (${alloc_c / 100:,.2f}). Your weekly holdings are ${holdings / 100:,.2f}, so there is nothing to borrow.")
        else:
            reasons.append(f"The smallest loan is ${min_c / 100:,.2f}.")
    eligible = not reasons
    return {"eligible": eligible, "reasons": reasons, "available_c": available if eligible else 0, "maxLoan_c": cap_c, "min_c": min_c,
            "holdings_c": holdings, "allocation_c": alloc_c, "dueAt": end, "week": wk, "takenThisWeek": taken}


def quote(user, amount, now=None):
    """Exactly what borrowing `amount` would do: shown to the person before they confirm. Raises if they cannot borrow it."""
    now = now_ms() if now is None else now
    lim = limits(user, now)
    if not lim["eligible"]:
        raise bad(lim["reasons"][0], 403, code="loan_not_allowed")
    c = _money(amount)
    if c < lim["min_c"]:
        raise bad(f"The smallest loan is ${lim['min_c'] / 100:,.2f}", code="loan_too_small")
    if c > lim["available_c"]:
        raise bad(f"You can borrow up to ${lim['available_c'] / 100:,.2f} right now", 403, code="loan_too_large")
    fee_c = ledger.to_cents(economy.LOAN_FEE)
    return {"amount": c / 100, "fee": fee_c / 100, "total": (c + fee_c) / 100, "dueAt": lim["dueAt"], "week": lim["week"],
            "weeklyAfter": (ledger.balance_c(user, "weekly") + c) / 100,
            "interest": "None. This loan is interest-free." if fee_c == 0 else f"A fixed fee of ${fee_c / 100:,.2f}, added to what you owe.",
            "effect": (f"You receive ${c / 100:,.2f} in your weekly account and owe ${(c + fee_c) / 100:,.2f}. Repay it any time before the week closes. "
                       f"If anything is still owed then, your weekly funds are collected first, the rest stays owed, and {economy.LOAN_ALLOC_REPAY_PCT:g}% of the next "
                       f"weekly allocation goes to it before you can spend it. Nothing is ever taken from your accumulated account."),
            "_c": c, "_fee_c": fee_c}


def borrow(user, amount, request_id=None, now=None):
    """Lends the money. All-or-nothing; the same request id never lends twice."""
    now = now_ms() if now is None else now
    request_id = idem.clean_id(request_id)
    key = idem.key_for("loan", user, request_id)
    fp = idem.fingerprint(op="borrow", amount=str(amount))
    hit = idem.seen(key, fp)
    if hit:
        return hit
    q = quote(user, amount, now)
    lid = new_id()
    with Txn(users=[user], extras=[(_loans(), lid), (db().setdefault("idem", {}), key or "-")]):
        loan = {"id": lid, "uid": user["id"], "principal_c": q["_c"], "fee_c": q["_fee_c"], "total_c": q["_c"] + q["_fee_c"],
                "owed_c": q["_c"] + q["_fee_c"], "repaid_c": 0, "status": "active", "overdue": False, "createdAt": now,
                "week": week_key(now), "dueAt": q["dueAt"], "closedAt": None, "payments": []}
        ledger.post(user, "weekly", q["_c"] / 100, "loan.borrow", ref=lid, txid=f"loan:{lid}:out", note="Loan received")   # not external: the debt is subtracted from net worth, so it is not income
        _loans()[lid] = loan
        user["loanId"] = lid
        user.setdefault("loans", []).insert(0, lid)
        users.log(user, "loan", q["_c"] / 100, f"Borrowed ${q['_c'] / 100:,.2f}")
        result = {"loan": loan_json(loan, now), "received": q["_c"] / 100, "owed": loan["owed_c"] / 100, "balance": ledger.balance(user, "weekly")}
        idem.remember(key, fp, result)
    return {**result, "duplicate": False}


def _apply_payment(user, loan, c, kind, txid, now, note):
    """Takes `c` cents of weekly cash toward a loan. Caller has checked the amount and runs this inside a Txn."""
    ledger.post(user, "weekly", -c / 100, f"loan.{'repay' if kind == 'repay' else 'collect'}", ref=loan["id"], txid=txid, note=note)
    loan["owed_c"] -= c
    loan["repaid_c"] += c
    loan["payments"].append({"id": new_id(), "t": now, "c": c, "kind": kind, "tx": txid})
    if loan["owed_c"] <= 0:
        loan["owed_c"] = 0
        loan["status"] = "closed"
        loan["closedAt"] = now
        user["loanId"] = None
        users.log(user, "loan", 0, f"Loan repaid in full (${loan['total_c'] / 100:,.2f})")


def repay(user, amount, request_id=None, now=None):
    """Repays part of the loan, or all of it (amount "all"). From the weekly account only."""
    now = now_ms() if now is None else now
    request_id = idem.clean_id(request_id)
    key = idem.key_for("repay", user, request_id)
    fp = idem.fingerprint(op="repay", amount=str(amount))
    hit = idem.seen(key, fp)
    if hit:
        return hit
    loan = active(user)
    if not loan:
        raise bad("You do not owe anything", 409, code="no_debt")
    cash = ledger.balance_c(user, "weekly")
    if isinstance(amount, str) and amount.strip().lower() == "all":
        c = min(loan["owed_c"], cash)
        if c <= 0:
            raise bad("There is nothing in your weekly account to repay with", code="insufficient_funds")
    else:
        c = _money(amount)
        if c > loan["owed_c"]:
            raise bad(f"You only owe ${loan['owed_c'] / 100:,.2f}", code="repay_too_large")
        if c > cash:
            raise bad(f"Your weekly account has ${cash / 100:,.2f}. Loans are only repaid from the weekly account.", code="insufficient_funds")
    with Txn(users=[user], extras=[(_loans(), loan["id"]), (db().setdefault("idem", {}), key or "-")]):
        _apply_payment(user, loan, c, "repay", f"loan:{loan['id']}:pay:{request_id or new_id()}", now, "Loan repayment")
        result = {"loan": loan_json(loan, now), "paid": c / 100, "owed": loan["owed_c"] / 100, "closed": loan["status"] == "closed",
                  "balance": ledger.balance(user, "weekly")}
        idem.remember(key, fp, result)
    return {**result, "duplicate": False}


def collect_at_close(week, now=None):
    """The weekly close, step before the reset: every loan gets whatever weekly funds its owner has. What is left stays owed (and
    the loan is marked overdue). Safe to run twice for the same week. Returns how many loans were touched."""
    now = now_ms() if now is None else now
    n = 0
    for loan in [l for l in _loans().values() if l["status"] == "active"]:
        user = users.get(loan["uid"])
        txid = f"loan:{loan['id']}:close:{week}"
        if ledger.find(user, txid) is not None:
            continue
        pay = min(ledger.balance_c(user, "weekly"), loan["owed_c"])
        with Txn(users=[user], extras=[(_loans(), loan["id"])]):
            if pay > 0:
                _apply_payment(user, loan, pay, "collect", txid, now, f"Collected at the close of the week of {week}")
            if loan["status"] == "active":
                loan["overdue"] = True
        n += 1
        if loan["status"] == "closed":
            inbox.push(user, "loan", "Loan repaid", f"${pay / 100:,.2f} was collected from your weekly account and your loan is paid off.")
        else:
            inbox.push(user, "loan", "Your loan is overdue",
                       f"${loan['owed_c'] / 100:,.2f} is still owed after ${pay / 100:,.2f} was collected. {economy.LOAN_ALLOC_REPAY_PCT:g}% of your next weekly allocation goes to it first. "
                       f"You cannot borrow again until it is paid.", loan=loan["id"])
    return n


def collect_from_allocation(week, now=None):
    """A new week's allocation has just landed: the share that goes to a debt is taken before anyone can spend it. Twice-safe."""
    now = now_ms() if now is None else now
    alloc_c = ledger.to_cents(economy.WEEKLY_ALLOCATION)
    n = 0
    for loan in [l for l in _loans().values() if l["status"] == "active"]:
        user = users.get(loan["uid"])
        txid = f"loan:{loan['id']}:alloc:{week}"
        if ledger.find(user, txid) is not None:
            continue
        if (user.get("wk") or {}).get("week") != week or alloc_c <= 0:
            continue                                           # no allocation reached this person this week
        pay = min(loan["owed_c"], alloc_c * int(economy.LOAN_ALLOC_REPAY_PCT * 100) // 10_000, ledger.balance_c(user, "weekly"))
        if pay <= 0:
            continue
        with Txn(users=[user], extras=[(_loans(), loan["id"])]):
            _apply_payment(user, loan, pay, "allocation", txid, now, f"Taken from the weekly allocation of {week}")
        n += 1
        inbox.push(user, "loan", "Debt paid from your new weekly allocation",
                   f"${pay / 100:,.2f} of your allocation went to your loan. " + ("It is paid off." if loan["status"] == "closed" else f"${loan['owed_c'] / 100:,.2f} is still owed."))
    return n


def loan_json(loan, now=None):
    now = now_ms() if now is None else now
    over = loan["status"] == "active" and (loan.get("overdue") or now >= loan["dueAt"])
    return {"id": loan["id"], "principal": loan["principal_c"] / 100, "fee": loan["fee_c"] / 100, "total": loan["total_c"] / 100,
            "owed": loan["owed_c"] / 100, "repaid": loan["repaid_c"] / 100, "status": loan["status"], "overdue": bool(over),
            "createdAt": loan["createdAt"], "dueAt": loan["dueAt"], "closedAt": loan["closedAt"], "week": loan["week"],
            "payments": [{"id": p["id"], "t": p["t"], "amount": p["c"] / 100, "kind": p["kind"]} for p in reversed(loan["payments"])]}


def view(user, now=None):
    """Everything the Loans page shows."""
    now = now_ms() if now is None else now
    lim = limits(user, now)
    loan = active(user)
    hist = [loan_json(_loans()[lid], now) for lid in user.get("loans", [])[:20] if lid in _loans() and _loans()[lid]["status"] == "closed"]
    return {
        "enabled": economy.LOANS_ENABLED, "eligible": lim["eligible"], "reasons": lim["reasons"], "available": lim["available_c"] / 100,
        "min": lim["min_c"] / 100, "maxLoan": lim["maxLoan_c"] / 100, "allocation": lim["allocation_c"] / 100, "holdings": lim["holdings_c"] / 100,
        "fee": economy.LOAN_FEE, "dueAt": lim["dueAt"], "week": lim["week"], "weekly": ledger.balance(user, "weekly"),
        "active": loan_json(loan, now) if loan else None, "history": hist, "now": now,
        "rules": {"allocationRepayPct": economy.LOAN_ALLOC_REPAY_PCT, "cutoffHours": economy.LOAN_CUTOFF_H, "maxPerWeek": economy.LOAN_MAX_PER_WEEK,
                  "maxPct": economy.LOAN_MAX_PCT_OF_ALLOCATION, "minAgeHours": economy.LOAN_MIN_ACCOUNT_AGE_H},
    }
