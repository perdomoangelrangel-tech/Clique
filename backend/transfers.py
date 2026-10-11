"""Friend-to-friend transfers: pretend money from one person's WEEKLY account to a friend's WEEKLY account, or from one person's
ACCUMULATED account to a friend's ACCUMULATED account. The sender chooses which. Money always arrives in the same account it left.

WHO. Only people who added each other as friends (a request that the other person accepted). A pending request, sharing a
circle, or anything else does not count. Friendship is checked again at the moment the money moves, so removing a friend
between "review" and "send" stops the transfer, and nothing moves.

WHAT. Same account to same account, no fee, a note of up to TRANSFER_NOTE_MAX characters. There is no way to turn weekly chips into
accumulated money or the other way round. Only cash can go: shares, and money riding on a bet, a round or a poker table, are not cash.
Money is conserved: what leaves one account arrives in the other, both written in the ledger under one transfer id, in one
all-or-nothing step (txn.Txn).

WEEKLY CHIPS carry three extra rules, because they reset every Monday and decide the weekly leaderboard:
  * Both legs are outside credits (external), so sending or receiving chips never changes anybody's weekly performance or position.
  * What you owe on a loan stays with you: only the cash above the debt can be sent, so borrowed money is never passed on.
  * A friend can only be topped up to the weekly allocation (TRANSFER_WEEKLY_RECEIVER_PCT), never above it, so nobody can pool chips from
    several friends to play with more than everybody else started with.

HOW MUCH. Each account has its own daily allowance (TRANSFER_DAILY_LIMIT for accumulated, TRANSFER_WEEKLY_DAILY_LIMIT for weekly),
across all recipients, counting only what was actually sent (a refused transfer costs nothing). Days follow the same time zone as the
weeks. Receiving money does not add to the allowance, and the amount sent so far is saved with the account, so a restart or a new login
does not reset it.

THE PASSWORD. Every transfer needs a dedicated transfer password, chosen in advance, asked again every time even while logged
in, never the login password and never a default. It is stored as a salted hash only, checked on the server, never logged,
never put in a URL or kept by the browser. Five wrong tries in a row lock transfers for 15 minutes (the count is saved, so a
restart does not clear it). Setting or changing it needs the login password too; a forgotten one is reset with the login password
plus a code emailed to the confirmed address.

NOT PROGRESSION. A transfer is not a qualifying action: it earns no XP, advances no challenge or milestone, does not touch the
weekly leaderboard, and a pair of friends sending money back and forth gains nothing from it. (This module never calls
activity.record.)
"""
import hmac
import secrets

from . import config, economy, idem, inbox, ledger, loans, mailer, recovery, social, users
from .store import db
from .txn import Txn
from .util import bad, day_key, new_id, next_day_start_ms, now_ms, parse_money

ACCOUNTS = ("weekly", "accumulated")
LOG_KEEP = 200
SENT_DAYS_KEEP = 14


def state(user):
    x = user.setdefault("xfer", {})
    x.setdefault("sent", {})                  # calendar day -> cents sent that day
    x.setdefault("log", [])                   # newest first: sent and received
    x.setdefault("fails", 0)
    x.setdefault("lockUntil", 0)
    return x


def has_password(user):
    return bool((user.get("xfer") or {}).get("pw"))


# ---- the transfer password ------------------------------------------------------------------------------------------

def _hash_pw(pw, salt):
    return users._hash(pw, salt)


def _locked_error(x, now):
    secs = max(1, int((x["lockUntil"] - now) / 1000))
    err = bad(f"Too many wrong transfer passwords. Transfers are locked for about {max(1, round(secs / 60))} more minute{'s' if round(secs / 60) != 1 else ''}.", 429, code="transfers_locked")
    err.data = {"retryAfter": secs}
    return err


def _check_pw(user, pw, now):
    """Checks the transfer password, counting wrong tries (and locking after too many). Raises if it is not right."""
    x = state(user)
    if x["lockUntil"] > now:
        raise _locked_error(x, now)
    ok = isinstance(pw, str) and has_password(user) and hmac.compare_digest(_hash_pw(pw, x["pw"]["salt"]), x["pw"]["hash"])
    if ok:
        x["fails"] = 0
        return
    x["fails"] += 1
    if x["fails"] >= economy.TRANSFER_PW_MAX_FAILS:
        x["fails"] = 0
        x["lockUntil"] = now + int(economy.TRANSFER_PW_LOCK_MIN * 60_000)
        err = _locked_error(x, now)
    else:
        left = economy.TRANSFER_PW_MAX_FAILS - x["fails"]
        err = bad(f"Wrong transfer password. {left} more tr{'y' if left == 1 else 'ies'} before transfers lock for {economy.TRANSFER_PW_LOCK_MIN:g} minutes.", 403, code="wrong_transfer_password")
    err.persist = True                         # the count of wrong tries must be saved even though this request fails
    raise err


def _check_login_pw(user, login_password):
    key = "tpwauth:" + user["id"]
    users._throttle(key, 8, 900)
    if not users.password_ok(user, login_password):
        users._fail(key)
        raise bad("Type your account (login) password to confirm it is you", 403, code="wrong_password")


def _validate_new(user, new_password):
    if not isinstance(new_password, str) or len(new_password) < 6:
        raise bad("The transfer password must be at least 6 characters", code="password_too_short")
    if len(new_password) > 200:
        raise bad("The transfer password is too long", code="password_too_long")
    if users.password_ok(user, new_password):
        raise bad("The transfer password must be different from your login password", code="password_same_as_login")


def _store_pw(user, new_password, now):
    x = state(user)
    salt = secrets.token_hex(16)
    x["pw"] = {"salt": salt, "hash": _hash_pw(new_password, salt), "setAt": now}
    x["fails"], x["lockUntil"] = 0, 0
    x.pop("codes", None)


def set_password(user, login_password, new_password, current_password=None, code=None, now=None):
    """First time: needs the login password. Change: also the current transfer password. Forgotten: the login password plus the
    emailed code. Returns "set", "changed" or "reset"."""
    now = now_ms() if now is None else now
    _check_login_pw(user, login_password)
    _validate_new(user, new_password)
    x = state(user)
    if not has_password(user):
        _store_pw(user, new_password, now)
        return "set"
    if current_password is not None:
        _check_pw(user, current_password, now)
        _store_pw(user, new_password, now)
        return "changed"
    if code is not None:
        users._throttle("tpwcode:" + user["id"], 10, 900)
        if not recovery._check(x, "tpw", str(code)):
            users._fail("tpwcode:" + user["id"])
            err = bad("That code is wrong or has expired. Ask for a new one.", 403, code="invalid_code")
            err.persist = True
            raise err
        _store_pw(user, new_password, now)
        return "reset"
    raise bad("Type your current transfer password, or use the emailed code if you forgot it", code="transfer_password_required")


def request_reset_code(user, login_password):
    """Starts a reset of a forgotten transfer password: needs the login password and a CONFIRMED email, which gets a code.
    Returns (address, code). The caller sends it."""
    _check_login_pw(user, login_password)
    if not has_password(user):
        raise bad("You have not set a transfer password yet. Just set one.", code="no_transfer_password")
    m = user.get("mail") or {}
    if not (m.get("verified") and m.get("addr")):
        raise bad("Resetting needs a confirmed email address on your account. Add and confirm one from the account menu first.", 403, code="email_not_confirmed")
    if not mailer.delivery_on():                                     # never claim a code was sent when this site cannot send one
        raise bad("Resetting by email is not switched on for this site yet. You can still change your transfer password with the current one.", 503, code="email_unavailable")
    users._throttle("tpwsend:" + user["id"], 5, 3600)
    users._fail("tpwsend:" + user["id"])
    return m["addr"], recovery._issue(state(user), "tpw", int(economy.TRANSFER_CODE_MIN * 60))


def reset_message(code):
    return ("Reset your transfer password",
            f"Your {recovery.APP} transfer-password code is {code}\n\nIt works for {economy.TRANSFER_CODE_MIN:g} minutes. Type it into the site, with your "
            f"account password, to choose a new transfer password.\n\nIf you did not ask for this, ignore this email and nothing changes. Consider "
            f"changing your account password.")


def changed_message(what):
    return (f"Your transfer password was {what}",
            f"The transfer password on your {recovery.APP} account was just {what}. If this was not you, change your account password now.")


# ---- who can be sent to ---------------------------------------------------------------------------------------------

def are_friends(a_id, b_id):
    """Both people have the other in their list of added friends (an accepted request). Nothing else counts."""
    if a_id == b_id:
        return False
    return b_id in social.rec(a_id)["friends"] and a_id in social.rec(b_id)["friends"]


def eligible(u):
    return bool(u) and not u.get("suspended") and not u.get("deleted")


def friends(user):
    out = []
    for fid in social.rec(user["id"])["friends"]:
        other = db()["users"].get(fid)
        if other and are_friends(user["id"], fid):
            out.append({"id": fid, "username": other["username"], "eligible": eligible(other)})
    return sorted(out, key=lambda r: r["username"].lower())


def _account(body):
    """Which account the person is sending from (accumulated when they do not say, as before there was a choice)."""
    a = body.get("account", "accumulated")
    if not isinstance(a, str) or a not in ACCOUNTS:
        raise bad("Choose the weekly account or the accumulated account", code="invalid_account")
    if a not in economy.TRANSFER_ACCOUNTS:
        raise bad(f"Sending from the {a} account is switched off right now.", 403, code="transfers_disabled")
    return a


def _limit_c(account):
    return ledger.to_cents(economy.TRANSFER_DAILY_LIMIT if account == "accumulated" else economy.TRANSFER_WEEKLY_DAILY_LIMIT)


def _sent_box(x, account, create=False):
    """What has been sent each day from this account. (The accumulated one keeps the name it always had.) Only sending creates anything."""
    if account == "accumulated":
        return x["sent"]
    return x.setdefault("sent_weekly", {}) if create else x.get("sent_weekly", {})


def _allowance(user, now, account="accumulated"):
    sent = _sent_box(state(user), account).get(day_key(now), 0)
    limit = _limit_c(account)
    return {"limit_c": limit, "sent_c": sent, "remaining_c": max(0, limit - sent), "resetsAt": next_day_start_ms(now), "day": day_key(now)}


def sendable_c(user, account):
    """The cash that can go, in cents. Weekly: what is in the account minus what is owed on a loan (borrowed money is never passed on)."""
    cash = ledger.balance_c(user, account)
    return max(0, cash - loans.owed_c(user)) if account == "weekly" else cash


def receiver_room_c(to, account):
    """How much more this person's account can take. Weekly chips can only top them up to the weekly allocation."""
    room = ledger.to_cents(config.MAX_BALANCE) - ledger.balance_c(to, account)
    if account == "weekly" and economy.TRANSFER_WEEKLY_RECEIVER_PCT > 0:
        top = ledger.to_cents(economy.WEEKLY_ALLOCATION) * int(economy.TRANSFER_WEEKLY_RECEIVER_PCT * 100) // 10_000
        room = min(room, max(0, top - loans.holdings_c(to)))
    return room


def account_rule(account):
    if account == "weekly":
        return (f"Weekly chips reset every Monday. A friend can only be topped up to the weekly allocation (${ledger.to_dollars(ledger.to_cents(economy.WEEKLY_ALLOCATION)):,.2f}), "
                f"and what you owe on a loan stays with you.")
    return "Accumulated money never resets. Only cash in the account can be sent: shares are not cash."


def _parse_amount(value):
    x = parse_money(value, "Amount")
    c = ledger.to_cents(x)
    if x <= 0 or c <= 0:
        raise bad("Enter an amount greater than 0", code="amount_not_positive")
    if abs(x * 100 - c) > 1e-6:
        raise bad("Use at most two decimals", code="too_many_decimals")
    return c


def _clean_note(value):
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise bad("The note must be text", code="invalid_request")
    note = " ".join(value.split())
    if len(note) > economy.TRANSFER_NOTE_MAX:
        raise bad(f"The note can be at most {economy.TRANSFER_NOTE_MAX} characters", code="text_too_long")
    return note


def _check(user, body, now):
    """Everything about a transfer that can be refused before money moves. Returns (recipient, cents, note, account)."""
    if not economy.TRANSFERS_ENABLED:
        raise bad("Transfers are switched off right now.", 403, code="transfers_disabled")
    if not has_password(user):
        raise bad("Choose a transfer password first (on the Transfers page).", 403, code="no_transfer_password")
    account = _account(body)
    label = ledger.LABEL[account].lower()
    if not isinstance(body.get("to"), str):
        raise bad("Choose who to send to", code="recipient_required")
    to = db()["users"].get(body["to"])
    if to is None:
        raise bad("That person was not found", 404, code="user_not_found")
    if to["id"] == user["id"]:
        raise bad("You cannot send money to yourself", code="cannot_send_to_self")
    if not are_friends(user["id"], to["id"]):
        raise bad("You can only send money to friends you have added, and who added you back.", 403, code="not_friends")
    if not eligible(to) or not eligible(user):
        raise bad("That account cannot receive money right now.", 403, code="recipient_unavailable")
    c = _parse_amount(body.get("amount"))
    if c < ledger.to_cents(economy.TRANSFER_MIN):
        raise bad(f"The smallest transfer is ${economy.TRANSFER_MIN:,.2f}", code="amount_too_small")
    note = _clean_note(body.get("note"))
    have, cash = sendable_c(user, account), ledger.balance_c(user, account)
    if c > have:
        if account == "weekly" and loans.owed_c(user) and cash > have:
            raise bad(f"Your weekly account has ${cash / 100:,.2f}, but ${loans.owed_c(user) / 100:,.2f} of it is what you owe on a loan and stays with you, so ${have / 100:,.2f} can be sent.", code="insufficient_funds")
        raise bad(f"Your {label} has ${cash / 100:,.2f}. Only cash in it can be sent: shares and money riding on a bet, a round or a poker table are not cash.", code="insufficient_funds")
    al = _allowance(user, now, account)
    if c > al["remaining_c"]:
        raise bad(f"That is over your daily limit for the {account} account. You can send ${al['remaining_c'] / 100:,.2f} more today (limit ${al['limit_c'] / 100:,.2f}, resets at midnight).", 403, code="daily_limit_reached")
    room = receiver_room_c(to, account)
    if c > room:
        if account == "weekly" and economy.TRANSFER_WEEKLY_RECEIVER_PCT > 0 and room < ledger.to_cents(config.MAX_BALANCE) - ledger.balance_c(to, account):
            if room <= 0:
                raise bad(f"{to['username']} already holds the whole weekly allocation, so there is nothing to top up.", 403, code="recipient_cap_reached")
            raise bad(f"Weekly chips can only top a friend up to the weekly allocation. {to['username']} can take ${room / 100:,.2f} right now.", 403, code="recipient_cap_reached")
        raise bad("That account cannot hold that much more.", 403, code="recipient_cap_reached")
    return to, c, note, account


def preview(user, body, now=None):
    """What a transfer would do, shown before the person types the password. Moves nothing and uses no allowance."""
    now = now_ms() if now is None else now
    to, c, note, account = _check(user, body, now)
    al = _allowance(user, now, account)
    have = ledger.balance_c(user, account)
    return {"to": {"id": to["id"], "username": to["username"]}, "amount": c / 100, "fee": 0.0, "note": note, "account": account,
            "fromAccount": account, "toAccount": account, "fromLabel": ledger.LABEL[account], "toLabel": ledger.LABEL[account],
            "senderBalanceAfter": (have - c) / 100, "dailyLimit": al["limit_c"] / 100, "sentToday": al["sent_c"] / 100,
            "remainingAfter": (al["remaining_c"] - c) / 100, "resetsAt": al["resetsAt"], "rule": account_rule(account)}


def send(user, body, now=None):
    """Sends the money. Needs the transfer password, explicit confirmation and a request id (so a retry cannot send twice)."""
    now = now_ms() if now is None else now
    request_id = idem.clean_id(body.get("requestId"))
    if not request_id:
        raise bad("Missing request id", code="invalid_request_id")
    if body.get("confirm") is not True:
        raise bad("Confirm the transfer to send it", code="confirm_required")
    key = idem.key_for("xfer", user, request_id)
    fp = idem.fingerprint(to=body.get("to"), amount=str(body.get("amount")), note=body.get("note") or "", account=body.get("account") or "accumulated")
    hit = idem.seen(key, fp)
    if hit:
        return hit
    if not has_password(user):                                       # say so plainly, and do not count it as a wrong try
        raise bad("Choose a transfer password first (on the Transfers page).", 403, code="no_transfer_password")
    _check_pw(user, body.get("password"), now)
    to, c, note, account = _check(user, body, now)
    tid = new_id()
    boxes = db().setdefault("transfers", {})
    with Txn(users=[user, to], extras=[(boxes, tid), (db().setdefault("idem", {}), key)]):
        # both legs are outside credits (external): for the weekly account that keeps everybody's weekly performance exactly where it was
        row_out = ledger.post(user, account, -c / 100, "transfer.out", ref=tid, external=True, txid=f"xfer:{tid}:out", note=f"To {to['username']}")
        ledger.post(to, account, c / 100, "transfer.in", ref=tid, external=True, txid=f"xfer:{tid}:in", note=f"From {user['username']}")
        sx, rx = state(user), state(to)
        box = _sent_box(sx, account, create=True)
        box[day_key(now)] = box.get(day_key(now), 0) + c
        for old in sorted(box)[:-SENT_DAYS_KEEP]:
            del box[old]
        rec = {"id": tid, "from": user["id"], "to": to["id"], "c": c, "note": note, "t": now, "status": "completed", "day": day_key(now), "account": account}
        boxes[tid] = rec
        sx["log"].insert(0, {"id": tid, "t": now, "dir": "out", "peer": to["id"], "peerName": to["username"], "c": c, "note": note, "status": "completed", "acct": account})
        rx["log"].insert(0, {"id": tid, "t": now, "dir": "in", "peer": user["id"], "peerName": user["username"], "c": c, "note": note, "status": "completed", "acct": account})
        del sx["log"][LOG_KEEP:]
        del rx["log"][LOG_KEEP:]
        users.log(user, "transfer", -c / 100, f"Sent ${c / 100:,.2f} ({account} account) to {to['username']}", tid)
        users.log(to, "transfer", c / 100, f"Received ${c / 100:,.2f} ({account} account) from {user['username']}", tid)
        al = _allowance(user, now, account)
        result = {"receipt": {"id": tid, "status": "completed", "t": now, "amount": c / 100, "fee": 0.0, "note": note,
                              "to": {"id": to["id"], "username": to["username"]}, "from": {"id": user["id"], "username": user["username"]},
                              "account": account, "fromAccount": account, "toAccount": account, "senderBalanceAfter": ledger.balance(user, account),
                              "remainingToday": al["remaining_c"] / 100, "ledgerId": row_out["id"]}}
        idem.remember(key, fp, result)
    inbox.push(to, "transfer", f"{user['username']} sent you ${c / 100:,.2f}", (f"“{note}” " if note else "") + f"It is in your {account} account.", transfer=tid, account=account)
    return {**result, "duplicate": False}


def view(user, now=None):
    """Everything the Transfers page shows."""
    now = now_ms() if now is None else now
    x = state(user)
    m = user.get("mail") or {}
    locked = x["lockUntil"] > now
    accounts = {}
    for a in ACCOUNTS:
        al = _allowance(user, now, a)
        accounts[a] = {"label": ledger.LABEL[a], "enabled": a in economy.TRANSFER_ACCOUNTS, "balance": ledger.balance(user, a), "sendable": sendable_c(user, a) / 100,
                       "owed": loans.owed(user) if a == "weekly" else 0.0, "rule": account_rule(a),
                       "limit": {"daily": al["limit_c"] / 100, "sent": al["sent_c"] / 100, "remaining": al["remaining_c"] / 100, "resetsAt": al["resetsAt"]}}
    acc = accounts["accumulated"]
    return {"enabled": economy.TRANSFERS_ENABLED, "passwordSet": has_password(user), "passwordSetAt": (x.get("pw") or {}).get("setAt"),
            "locked": {"until": x["lockUntil"], "seconds": int((x["lockUntil"] - now) / 1000)} if locked else None,
            "accounts": accounts, "defaultAccount": "accumulated",
            "balance": acc["balance"], "account": "accumulated", "accountLabel": acc["label"], "limit": acc["limit"],       # (what there was before the choice of account)
            "min": economy.TRANSFER_MIN, "noteMax": economy.TRANSFER_NOTE_MAX, "fee": 0.0, "friends": friends(user),
            "history": [{"id": h["id"], "t": h["t"], "dir": h["dir"], "peer": {"id": h["peer"], "username": h["peerName"]}, "amount": h["c"] / 100,
                         "note": h["note"], "status": h["status"], "account": h.get("acct", "accumulated")} for h in x["log"][:60]],
            "canReset": bool(m.get("verified") and m.get("addr")), "now": now}
