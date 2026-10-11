"""Email addresses and getting back into an account you can no longer open.

THE ADDRESS. Everybody gives one (new accounts must; existing accounts are asked the next time they open the site). It only counts
for resetting a password once it is CONFIRMED: a 6-digit code is sent to it and typed back. Until then a typing mistake could
send somebody else the keys to the account. An address can be confirmed on one account only; changing a confirmed address
needs the account's password, and the old one keeps working until the new one is confirmed.

THE RESET. "Forgot your password?" asks for the email address. If a confirmed address matches an account, a 6-digit code goes to it
(15 minutes, five tries); typing it back together with a new password sets that password, ends every login on the account, and
tells the owner by email. The answer to "send me a code" is always the same whether or not the address belongs to anybody, so the
form cannot be used to find out who has an account. The address, and the codes (stored scrambled), are never shown to other people.

Nothing here sends anything itself: each function returns what to send, and the server hands it to mailer.send_async.
"""
import hashlib
import hmac
import re
import secrets
import time

from . import config, mailer, users
from .store import db
from .util import bad

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s.]{2,24}$")
VERIFY_TTL_S = 30 * 60
RESET_TTL_S = 15 * 60
MAX_TRIES = 5
RESEND_AFTER_S = 45
GENERIC_SENT = "If an account uses that email address, we have sent it a code. It works for 15 minutes."
APP = "Clique"


def normalize_email(value):
    if not isinstance(value, str) or not value.strip():
        raise bad("Enter your email address", code="email_required")
    addr = value.strip().lower()
    if len(addr) > 254 or ".." in addr or not EMAIL_RE.match(addr):
        raise bad("That does not look like an email address", code="invalid_email")
    return addr


def _owner(addr, except_uid=None):
    """The account that has CONFIRMED this address, if any."""
    for u in db()["users"].values():
        m = u.get("mail") or {}
        if m.get("verified") and m.get("addr") == addr and u["id"] != except_uid:
            return u
    return None


def check_available(addr, except_uid=None):
    if _owner(addr, except_uid):
        raise bad("That email is already confirmed on another account. Use a different one.", 409, code="email_taken")


# ---- codes -------------------------------------------------------------------------------------------------------

def _hash_code(code, salt):
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()


def _issue(holder, kind, ttl_s):
    code = f"{secrets.randbelow(10 ** 6):06d}"
    salt = secrets.token_hex(8)
    holder.setdefault("codes", {})[kind] = {"h": _hash_code(code, salt), "salt": salt, "exp": time.time() + ttl_s, "tries": 0, "sent": time.time()}
    return code


def _check(holder, kind, code):
    """True if `code` is the live code of this kind. A wrong guess uses up one of five tries; the code dies with the fifth."""
    c = (holder.get("codes") or {}).get(kind)
    if not c or not isinstance(code, str):
        return False
    if time.time() > c["exp"] or c["tries"] >= MAX_TRIES:
        holder["codes"].pop(kind, None)
        return False
    if hmac.compare_digest(_hash_code(code.strip(), c["salt"]), c["h"]):
        holder["codes"].pop(kind, None)
        return True
    c["tries"] += 1
    if c["tries"] >= MAX_TRIES:
        holder["codes"].pop(kind, None)
    return False


# ---- the address on an account -----------------------------------------------------------------------------------

def view(user):
    """What the account's owner is shown about their email (only ever to them)."""
    m = user.get("mail") or {}
    return {"address": m.get("addr"), "verified": bool(m.get("verified")), "pending": (m.get("pending") or {}).get("addr"),
            "needed": not m.get("addr"), "delivery": mailer.delivery_on(), "preview": not mailer.configured()}


def verify_message(code):
    return (f"Confirm your email for {APP}",
            f"Your {APP} confirmation code is {code}\n\nIt works for 30 minutes. Type it into the site to confirm this address, "
            f"so you can reset your password later if you ever forget it.\n\nIf you did not ask for this, ignore this email.")


def attach(user, address, password=None):
    """Puts an address on the account (a first one, or a new one) and returns (address, code to email)."""
    addr = normalize_email(address)
    users._throttle("setmail:" + user["id"], 10, 3600)
    users._fail("setmail:" + user["id"])
    m = user.get("mail") or {}
    if m.get("verified") and m.get("addr") == addr and not m.get("pending"):
        raise bad("That is already your confirmed email", code="email_already_confirmed")
    check_available(addr, user["id"])
    if m.get("verified"):                              # replacing a confirmed address: prove it is you, and keep the old one until the new one works
        if not users.password_ok(user, password):
            raise bad("Type your current password to change your email", 403, code="wrong_password")
        m["pending"] = {"addr": addr}
        m["codes"] = {}
    else:                                              # nothing confirmed yet: the address simply replaces what was there
        m = {"addr": addr, "verified": False}
    user["mail"] = m
    return addr, _issue(m, "verify", VERIFY_TTL_S)


def resend(user):
    """A fresh confirmation code for the address waiting to be confirmed. Returns (address, code)."""
    m = user.get("mail") or {}
    target = (m.get("pending") or {}).get("addr") or m.get("addr")
    if not target or (m.get("verified") and not m.get("pending")):
        raise bad("There is no email waiting to be confirmed", code="no_pending_email")
    last = (m.get("codes") or {}).get("verify")
    if last and time.time() - last["sent"] < RESEND_AFTER_S:
        raise bad("A code was just sent. Give it a minute, and check your spam folder.", 429, code="rate_limited")
    users._throttle("vsend:" + user["id"], 6, 3600)
    users._fail("vsend:" + user["id"])
    return target, _issue(m, "verify", VERIFY_TTL_S)


def confirm(user, code):
    m = user.get("mail") or {}
    target = (m.get("pending") or {}).get("addr") or m.get("addr")
    if not target or (m.get("verified") and not m.get("pending")):
        raise bad("There is no email waiting to be confirmed", code="no_pending_email")
    users._throttle("vcheck:" + user["id"], 20, 3600)
    if not _check(m, "verify", code):
        users._fail("vcheck:" + user["id"])
        raise bad("That code is wrong or has expired. Ask for a new one.", code="invalid_code")
    check_available(target, user["id"])
    m["addr"], m["verified"] = target, True
    m.pop("pending", None)
    return m


# ---- forgot password ---------------------------------------------------------------------------------------------

def reset_message(code):
    return (f"Your {APP} password code",
            f"Your {APP} password reset code is {code}\n\nIt works for 15 minutes. Type it into the site together with your new "
            f"password.\n\nIf you did not ask to reset your password, ignore this email: nothing has changed and nobody can use "
            f"this code without it.")


def changed_message():
    return (f"Your {APP} password was changed",
            f"The password on your {APP} account was just changed using your email address. Everybody logged in to it was signed out.\n\n"
            f"If this was not you, reset it again from the log-in page and tell whoever runs the site.")


def request_reset(email, ip):
    """Starts a reset. Returns (address, code to email), or None when nothing is to be sent. Raises only for a malformed address,
    too many requests from one place, or when this site cannot send email at all: never because of who has an account."""
    users._throttle("forgot:" + ip, 10, 3600)
    users._fail("forgot:" + ip)
    addr = normalize_email(email)
    if not mailer.delivery_on():
        raise bad("Resetting by email is not switched on for this site yet. Ask whoever runs it to set a new password for you.", 503, code="email_unavailable")
    try:
        users._throttle("forgotmail:" + addr, 3, 3600)         # one address cannot be flooded with codes; the answer does not change
    except Exception:
        return None
    users._fail("forgotmail:" + addr)
    u = _owner(addr)
    if not u:
        return None
    return addr, _issue(u["mail"], "reset", RESET_TTL_S)


def reset_with_code(email, code, new_password, ip):
    """Sets the new password if the code is right. Returns the user. Every wrong answer looks the same."""
    users._throttle("resetmail:" + ip, 20, 3600)
    users.check_new_password(new_password)
    wrong = bad("That code is wrong or has expired. Ask for a new one.", code="invalid_code")
    try:
        addr = normalize_email(email)
    except Exception:
        users._fail("resetmail:" + ip)
        raise wrong
    u = _owner(addr)
    if not u or not _check(u["mail"], "reset", code):
        users._fail("resetmail:" + ip)
        raise wrong
    users.set_password(u, new_password)
    (u["mail"].get("codes") or {}).clear()
    users._attempts.pop("resetmail:" + ip, None)
    return u
