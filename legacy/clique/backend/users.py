"""Accounts, sessions, wallet, and the weekly stats every user collects."""
import hashlib
import hmac
import re
import secrets
import time

from . import config, economy, ledger, progress
from .store import db
from .util import bad, new_id, now_ms, round2, parse_money, week_bounds, week_key

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
PBKDF2_ROUNDS = 120_000
_attempts = {}   # rate limiting for logins and the add-funds password: key -> [timestamps]


def _hash(password, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ROUNDS).hex()


def _token_key(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _throttle(key, limit, window_s):
    now = time.time()
    recent = [t for t in _attempts.get(key, []) if now - t < window_s]
    _attempts[key] = recent
    if len(recent) >= limit:
        raise bad("Too many attempts. Wait a few minutes and try again.", 429)


def _fail(key):
    _attempts.setdefault(key, []).append(time.time())


# ---- accounts ----------------------------------------------------------------------

def register(username, password):
    d = db()
    if not isinstance(username, str) or not USERNAME_RE.match(username):
        raise bad("Username must be 3-20 characters: letters, numbers or underscores")
    if not isinstance(password, str) or len(password) < 6:
        raise bad("Password must be at least 6 characters")
    if len(password) > 200:
        raise bad("Password is too long")
    if username.lower() in d["usernames"]:
        raise bad("That username is already taken", 409)
    uid = new_id()
    salt = secrets.token_hex(16)
    user = {
        "id": uid, "username": username, "salt": salt, "hash": _hash(password, salt),
        "balance": 0.0, "accum": 0.0, "createdAt": now_ms(),
        "wk": {"week": week_key(), "start_c": 0, "ext_c": 0},      # where this week's performance is measured from
        "stats": {}, "activity": [], "history": [],
    }
    d["users"][uid] = user
    d["usernames"][username.lower()] = uid
    ledger.post(user, "weekly", config.START_BALANCE, "welcome", external=True)
    user["wk"] = {"week": week_key(), "start_c": ledger.balance_c(user, "weekly"), "ext_c": 0}      # the welcome money is the starting line
    log(user, "start", config.START_BALANCE, "Welcome bonus")
    return user


def login(username, password, ip="?"):
    d = db()
    # Limited per IP *and* per username: behind a proxy the IP comes from a header a client can fake.
    who = "loginname:" + str(username).lower()[:40]
    _throttle("login:" + ip, 12, 300)
    _throttle(who, 15, 600)
    uid = d["usernames"].get(str(username).lower())
    user = d["users"].get(uid) if uid else None
    salt = user["salt"] if user else "00" * 16
    ok = hmac.compare_digest(_hash(str(password), salt), user["hash"] if user else "x")
    if not user or not ok:
        _fail("login:" + ip)
        _fail(who)
        raise bad("Wrong username or password", 401)
    return user


def reset_password(username, new_password, funds_password, ip="?"):
    """A forgotten password: whoever knows the funds password can set a new one for any account.
    The old password is never shown (it is only stored scrambled), and every open log-in on that account ends."""
    _throttle("reset:" + ip, 10, 600)
    _throttle("deposit:everyone", 20, 600)          # one shared budget for guessing the funds password, whichever way it is tried
    given = hashlib.sha256(str(funds_password).encode("utf-8")).digest()
    wanted = hashlib.sha256(config.ADMIN_PASSWORD.encode("utf-8")).digest()
    if not hmac.compare_digest(given, wanted):
        _fail("reset:" + ip)
        _fail("deposit:everyone")
        raise bad("Wrong funds password", 403)
    if not isinstance(new_password, str) or len(new_password) < 6:
        raise bad("Password must be at least 6 characters")
    if len(new_password) > 200:
        raise bad("Password is too long")
    d = db()
    uid = d["usernames"].get(str(username).lower())
    if not uid:
        raise bad("There is no account with that username", 404)
    user = d["users"][uid]
    set_password(user, new_password)
    _attempts.pop("reset:" + ip, None)
    return user


def check_new_password(new_password):
    if not isinstance(new_password, str) or len(new_password) < 6:
        raise bad("Password must be at least 6 characters")
    if len(new_password) > 200:
        raise bad("Password is too long")


def set_password(user, new_password):
    """Gives the account a new password. Every open log-in on it ends, and a lock-out from too many wrong tries ends too."""
    check_new_password(new_password)
    d = db()
    user["salt"] = secrets.token_hex(16)
    user["hash"] = _hash(new_password, user["salt"])
    for key, sess in list(d["sessions"].items()):
        if sess["userId"] == user["id"]:
            del d["sessions"][key]
    _attempts.pop("loginname:" + user["username"].lower()[:40], None)


def password_ok(user, password):
    return isinstance(password, str) and hmac.compare_digest(_hash(password, user["salt"]), user["hash"])


def make_session(uid):
    token = secrets.token_urlsafe(32)
    db()["sessions"][_token_key(token)] = {
        "userId": uid, "expires": now_ms() + config.SESSION_DAYS * 86400000}
    return token


def user_for_token(token):
    if not token:
        return None
    d = db()
    s = d["sessions"].get(_token_key(token))
    if not s:
        return None
    if s["expires"] < now_ms():
        d["sessions"].pop(_token_key(token), None)
        return None
    return d["users"].get(s["userId"])


def drop_session(token):
    if token:
        db()["sessions"].pop(_token_key(token), None)


def get(uid):
    u = db()["users"].get(uid)
    if not u:
        raise bad("User not found", 404)
    return u


def by_username(name):
    uid = db()["usernames"].get(str(name).lower())
    if not uid:
        raise bad("User not found", 404)
    return db()["users"][uid]


def style_of(uid):
    """How somebody looks (picture, frame, badge, title, accent): {} if everything is the default."""
    from . import cosmetics                        # imported here: cosmetics uses the ledger, which uses nothing of ours
    u = db()["users"].get(uid)
    return cosmetics.public_style(u) if u else {}


def look_field(uid):
    """What to add to a person's entry in a list: their look, if they have ever personalised anything. Somebody who has
    reset to the defaults is sent with an empty look, so every browser forgets what it knew; somebody who never touched
    it is sent with nothing at all."""
    u = db()["users"].get(uid)
    if not u or u.get("profile") is None:
        return {}
    return {"st": style_of(uid)}


def public(u):
    return {"id": u["id"], "username": u["username"], "rank": progress.compact_rank(u), **look_field(u["id"])}


# ---- wallet ------------------------------------------------------------------------

def log(user, kind, amount, text, ref=None):
    entry = {"t": now_ms(), "kind": kind, "amount": amount, "text": text}
    if ref:
        entry["ref"] = ref
    user["activity"].insert(0, entry)
    del user["activity"][300:]


def credit(user, amount, reason=None, **kw):
    """Money into the WEEKLY account (or the practice wallet, which keeps no ledger)."""
    if user.get("isDemo"):
        user["balance"] = min(config.MAX_BALANCE, round2(user["balance"] + amount))
        return
    if user.get("isAcc"):                                                  # the accumulated account, as a casino wallet (games.accum_account)
        owner = user["_owner"]
        ledger.post(owner, "accumulated", amount, reason, **kw)
        user["balance"] = ledger.balance(owner, "accumulated")
        return
    ledger.post(user, "weekly", amount, reason, **kw)


def debit(user, amount, reason=None, **kw):
    """Money out of the WEEKLY account (or the accumulated one, for a casino wallet that is that account). Raises "Not enough funds" rather than going below zero."""
    if user.get("isDemo"):
        if amount > user["balance"] + 1e-9:
            raise bad("Not enough funds")
        user["balance"] = max(0.0, round2(user["balance"] - amount))
        return
    if user.get("isAcc"):
        owner = user["_owner"]
        ledger.post(owner, "accumulated", -amount, reason, **kw)
        user["balance"] = ledger.balance(owner, "accumulated")
        return
    ledger.post(user, "weekly", -amount, reason, **kw)


def check_deposit(user, amount, password, account="weekly"):
    """Everything the "add funds" box asks before any money moves: the account, the amount, and the funds password (with its limits on
    guessing). Returns (amount in dollars, account). Nothing is changed except the count of wrong passwords."""
    # Per account, plus one limit shared by everyone so new accounts can't be used to guess the password.
    _throttle("deposit:" + user["id"], 5, 600)
    _throttle("deposit:everyone", 20, 600)
    if account not in ledger.ACCOUNTS:
        raise bad("Choose the weekly or the accumulated account")
    amount = parse_money(amount, "Amount")
    if amount <= 0:
        raise bad("Enter an amount greater than 0")
    if amount > config.MAX_DEPOSIT:
        raise bad(f"Max {config.MAX_DEPOSIT:,.0f} per deposit")
    given = hashlib.sha256(str(password).encode("utf-8")).digest()
    wanted = hashlib.sha256(config.ADMIN_PASSWORD.encode("utf-8")).digest()
    if not hmac.compare_digest(given, wanted):
        _fail("deposit:" + user["id"])
        _fail("deposit:everyone")
        raise bad("Wrong password", 403)
    _attempts.pop("deposit:" + user["id"], None)
    return round2(amount), account


def apply_deposit(user, amount, account="weekly", ref=None, txid=None):
    """Puts the money into the account. Money added to the weekly account never counts as that week's winnings."""
    ledger.post(user, account, amount, "deposit", external=True, ref=ref, txid=txid)
    if account == "weekly":
        stat_add(user, "deposits", amount)
    log(user, "deposit", amount, "Funds added" + ("" if account == "weekly" else " (accumulated account)"))
    return amount


def deposit(user, amount, password, account="weekly"):
    """The host's "add funds" box, straight away: pretend money handed out by whoever knows the funds password, into either account.
    The website does not use this any more: what somebody adds there waits for a vote first (backend/fundvotes.py), and only an approved
    one reaches apply_deposit."""
    amount, account = check_deposit(user, amount, password, account)
    return apply_deposit(user, amount, account)


# ---- the weekly voucher ------------------------------------------------------------

def voucher_info(user):
    """Can this person redeem the rescue voucher right now? One per week, only when their cash is
    under $0.50, and not while a casino round is still on the table."""
    wk = week_key()
    used = (user.get("voucher") or {}).get("week") == wk
    from . import poker                       # imported here: poker itself uses this module
    busy = bool(db()["games"].get(user["id"])) or poker.real_stake(user["id"]) > 0
    broke = user["balance"] < config.VOUCHER_BELOW
    return {"amount": config.VOUCHER_AMOUNT, "below": config.VOUCHER_BELOW, "used": used, "busy": busy,
            "eligible": broke and not used and not busy, "resetsAt": week_bounds(wk)[1],
            "goAmount": economy.WEEKLY_ALLOCATION}


def add_deposit_stat(user, amount, week=None):
    """Money that was handed out (not won) is logged as a deposit so it never counts as winnings."""
    s = user["stats"].setdefault(week or week_key(), {})
    s["deposits"] = s.get("deposits", 0) + amount


def redeem_voucher(user):
    info = voucher_info(user)
    if info["used"]:
        raise bad("You already used this week's voucher. A new one turns up when the week does.")
    if user["balance"] >= config.VOUCHER_BELOW:
        raise bad(f"You still have chips. Vouchers are for when you are under ${config.VOUCHER_BELOW:.2f}.")
    if info["busy"]:
        raise bad("Finish the round you are playing first, then redeem.")
    user["voucher"] = {"week": week_key(), "t": now_ms()}
    credit(user, config.VOUCHER_AMOUNT, "voucher", external=True)
    add_deposit_stat(user, config.VOUCHER_AMOUNT)
    log(user, "voucher", config.VOUCHER_AMOUNT, "Weekly voucher redeemed")
    return config.VOUCHER_AMOUNT


# ---- weekly stats ------------------------------------------------------------------

def _week(user, t=None):
    return user["stats"].setdefault(week_key(t), {})


def stat_add(user, key, value=1):
    s = _week(user)
    s[key] = s.get(key, 0) + value


def stat_max(user, key, value):
    s = _week(user)
    if value > s.get(key, 0):
        s[key] = value


def stat_best(user, key, value, label):
    """Keeps the best {value, label} pair of the week."""
    s = _week(user)
    cur = s.get(key)
    if cur is None or value > cur["value"]:
        s[key] = {"value": value, "label": label}
