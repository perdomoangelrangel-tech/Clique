#!/usr/bin/env python3
"""Clique: a private prediction market for you and your friends.

Run it with:   python3 server.py
No installs needed, it only uses Python's standard library.
"""
import gzip
import json
import mimetypes
import os
import queue
import re
import signal
import socket
import sys
import threading
import time
import traceback
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend import assets, challenges, chats, circles, config, cosmetics, economy, exchange, fundvotes, games, inbox, ledger, loans, mailer, markets, milestones, poker, progress, ranking, recovery, seed, social, stockengine, transfers, users, voice, weekly, wealth
from backend.store import LOCK, db, store
from backend.util import ApiError, bad, now_ms, week_key

ROUTES = []
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")


def route(method, pattern, auth=True, mutates=None):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn, auth, (method != "GET") if mutates is None else mutates))
        return fn
    return deco


# ---- live updates (server-sent events) -----------------------------------------------

class Hub:
    def __init__(self):
        self.clients = set()
        self.lock = threading.Lock()

    def add(self, client):
        with self.lock:
            self.clients.add(client)

    def remove(self, client):
        with self.lock:
            self.clients.discard(client)

    def publish_users(self, event, user_ids):
        """Sends `event` only to these people (private poker tables)."""
        ids = set(user_ids)
        with self.lock:
            targets = [cl for cl in self.clients if cl.user_id in ids]
        for cl in targets:
            try:
                cl.q.put_nowait(event)
            except queue.Full:
                pass

    def publish(self, event, circle_id=None):
        """Sends `event` to everyone who is allowed to see that circle."""
        circle = db()["circles"].get(circle_id) if circle_id else None
        with self.lock:
            targets = list(self.clients)
        for cl in targets:
            if circle and not circles.can_view(circle, db()["users"].get(cl.user_id)):
                continue
            try:
                cl.q.put_nowait(event)
            except queue.Full:                     # a stalled browser must never hold up everybody else
                pass


class Client:
    def __init__(self, user_id):
        self.user_id = user_id
        self.q = queue.Queue(maxsize=200)


hub = Hub()


# ---- request context -----------------------------------------------------------------

class Req:
    def __init__(self, user, body, query, ip, token):
        self.user, self.body, self.query, self.ip, self.token = user, body, query, ip, token
        self.new_token = None
        self.clear_token = False
        self.dirty = False                  # a read-only route sets this when it did change something that must be saved


def me_json(u):
    pv = markets.open_positions_value(u["id"])
    out = {"id": u["id"], "username": u["username"], **users.look_field(u["id"]),
           "balance": u["balance"],                                  # the WEEKLY account (the name the games have always used)
           "weekly": u["balance"], "accum": u.get("accum", 0.0),     # both accounts, spelled out
           "positionsValue": round(pv, 2), "debt": loans.owed(u), "netWorth": round(u["balance"] + pv - loans.owed(u), 2),
           "rank": progress.compact_rank(u), "unseen": len(inbox.unseen(u)),
           "voucher": users.voucher_info(u), "email": recovery.view(u)}
    if u.get("passGo"):
        out["passGo"] = u["passGo"]
    held = fundvotes.hold(u)
    if held:
        out["onHold"] = held                                         # funds added by this person that are waiting for a vote
    return out


def demo_json(acct):
    """The practice wallet, shaped like me_json so the browser can treat both the same way."""
    return {"id": acct["id"], "username": acct["username"], "balance": acct["balance"],
            "positionsValue": 0, "netWorth": acct["balance"], "demo": True}


RAW_UPLOADS = {("POST", "/api/profile/avatar")}

_REASONS = ((re.compile(r"^/api/games/(\w+)"), "casino."), (re.compile(r"^/api/poker"), "poker"),
            (re.compile(r"^/api/markets"), "market"), (re.compile(r"^/api/wallet/voucher"), "voucher"),
            (re.compile(r"^/api/store"), "store"), (re.compile(r"^/api/stocks"), "stocks"))


def reason_for(method, path):
    """A short name for what a request is about, written on any ledger row it creates without a better reason."""
    for rx, label in _REASONS:
        m = rx.match(path)
        if m:
            return label + (m.group(1) if label.endswith(".") else "")
    return "other"


def q1(req, key, default=None):
    vals = req.query.get(key)
    return vals[0] if vals else default


# ---- auth & wallet -------------------------------------------------------------------

@route("POST", "/api/auth/register", auth=False)
def api_register(req):
    email, addr = req.body.get("email"), None
    if email not in (None, "") and not (isinstance(email, str) and not email.strip()):
        addr = recovery.normalize_email(email)               # a bad address is refused before any account is made
        recovery.check_available(addr)
    elif config.EMAIL_REQUIRED:
        raise bad("Enter your email address. It is how you reset your password if you ever forget it.")
    u = users.register(req.body.get("username"), req.body.get("password"))
    if addr:
        _, code = recovery.attach(u, addr)
        if mailer.delivery_on():
            mailer.send_async(addr, *recovery.verify_message(code))
    req.new_token = users.make_session(u["id"])
    return {"user": me_json(u)}


@route("POST", "/api/auth/login", auth=False)
def api_login(req):
    u = users.login(req.body.get("username"), req.body.get("password"), req.ip)
    req.new_token = users.make_session(u["id"])
    return {"user": me_json(u)}


@route("POST", "/api/auth/reset", auth=False)
def api_reset(req):
    u = users.reset_password(req.body.get("username"), req.body.get("newPassword"), req.body.get("fundsPassword"), req.ip)
    return {"ok": True, "username": u["username"]}


@route("POST", "/api/auth/forgot", auth=False)
def api_forgot(req):
    """"Send me a code": always answers the same way, whoever the address belongs to."""
    out = recovery.request_reset(req.body.get("email"), req.ip)
    if out:
        mailer.send_async(out[0], *recovery.reset_message(out[1]))
    return {"ok": True, "message": recovery.GENERIC_SENT}


@route("POST", "/api/auth/reset-by-email", auth=False)
def api_reset_by_email(req):
    u = recovery.reset_with_code(req.body.get("email"), req.body.get("code"), req.body.get("newPassword"), req.ip)
    mailer.send_async(u["mail"]["addr"], *recovery.changed_message())
    return {"ok": True, "username": u["username"]}


@route("POST", "/api/me/email")
def api_set_email(req):
    addr, code = recovery.attach(req.user, req.body.get("email"), req.body.get("password"))
    if mailer.delivery_on():
        mailer.send_async(addr, *recovery.verify_message(code))
    return {"email": recovery.view(req.user)}


@route("POST", "/api/me/email/resend")
def api_resend_email(req):
    addr, code = recovery.resend(req.user)
    if mailer.delivery_on():
        mailer.send_async(addr, *recovery.verify_message(code))
    return {"email": recovery.view(req.user)}


@route("POST", "/api/me/email/verify")
def api_verify_email(req):
    recovery.confirm(req.user, req.body.get("code"))
    return {"email": recovery.view(req.user), "user": me_json(req.user)}


@route("POST", "/api/auth/logout", auth=False)
def api_logout(req):
    users.drop_session(req.token)
    req.clear_token = True
    return {"ok": True}


@route("GET", "/api/me", auth=False)
def api_me(req):
    return {"user": me_json(req.user) if req.user else None, "categories": config.CATEGORIES,
            "minBet": config.MIN_BET, "startBalance": config.START_BALANCE, "week": week_key()}


@route("POST", "/api/wallet/voucher")
def api_voucher(req):
    amount = users.redeem_voucher(req.user)
    return {"added": amount, "user": me_json(req.user)}


@route("POST", "/api/wallet/deposit")
def api_deposit(req):
    """The funds password opens the box, but the money waits for a vote of everybody else before it is added (backend/fundvotes.py)."""
    v = fundvotes.propose(req.user, req.body.get("amount"), req.body.get("password"), req.body.get("account") or "weekly")
    return {"added": v["amount"] if v["status"] == "approved" else 0, "vote": fundvotes.mine(req.user, 1)[0], "user": me_json(req.user)}


@route("GET", "/api/fundvotes", mutates=False)
def api_fundvotes(req):
    """The votes this person still has to cast, and their own requests."""
    return {"owed": fundvotes.owed(req.user), "mine": fundvotes.mine(req.user)}


@route("POST", r"/api/fundvotes/(\w+)/vote")
def api_fundvote(req, vote_id):
    fundvotes.cast(req.user, vote_id, req.body.get("favor"))
    return {"owed": fundvotes.owed(req.user), "user": me_json(req.user)}


@route("GET", "/api/ledger", mutates=False)
def api_ledger(req):
    """Your own statement: every movement in both accounts, newest first (older ones are summed up by week)."""
    account = q1(req, "account")
    if account and account not in ledger.ACCOUNTS:
        raise bad("Unknown account")
    try:
        limit = max(1, min(200, int(q1(req, "limit", "60"))))
        before = int(q1(req, "before")) if q1(req, "before") else None
    except ValueError:
        raise bad("Invalid paging")
    return {"entries": ledger.entries(req.user, account, limit, before), "older": ledger.summaries(req.user) if not before else [],
            "balances": {"weekly": ledger.balance(req.user, "weekly"), "accumulated": ledger.balance(req.user, "accumulated")},
            "labels": ledger.LABEL}


@route("GET", "/api/week", mutates=False)
def api_my_week(req):
    """Where the signed-in person stands this week, and what the rules are."""
    from backend import util
    return {"week": weekly.my_week(req.user), "rules": weekly.rules_snapshot(), "timezone": util.TZ_NAME,
            "weekly": req.user["balance"], "accum": req.user.get("accum", 0.0)}


# ---- loans, ranks, challenges, milestones, notifications and transfers ---------------------------------------------
# Each of these answers with the person's refreshed account ("user") after any change, so the browser can update both balances.

@route("GET", "/api/loans", mutates=False)
def api_loans(req):
    return loans.view(req.user)


@route("POST", "/api/loans/quote", mutates=False)
def api_loan_quote(req):
    """Exactly what borrowing this amount would do. Moves nothing."""
    q = loans.quote(req.user, req.body.get("amount"))
    return {k: v for k, v in q.items() if not k.startswith("_")}


@route("POST", "/api/loans/borrow")
def api_loan_borrow(req):
    if req.body.get("confirm") is not True:
        raise bad("Confirm the loan to borrow it")
    out = loans.borrow(req.user, req.body.get("amount"), req.body.get("requestId"))
    out["user"] = me_json(req.user)
    return out


@route("POST", "/api/loans/repay")
def api_loan_repay(req):
    out = loans.repay(req.user, req.body.get("amount"), req.body.get("requestId"))
    out["user"] = me_json(req.user)
    return out


@route("GET", "/api/progress", mutates=False)
def api_progress(req):
    """The Rank page: XP, rank, ladder, how XP is earned, promotions, and every milestone."""
    out = progress.overview(req.user)
    out["milestones"] = milestones.view(req.user)
    req.dirty = milestones.evaluate(req.user) != []
    return out


@route("POST", "/api/milestones/claim")
def api_milestone_claim(req):
    out = milestones.claim(req.user, req.body.get("id"))
    out["user"] = me_json(req.user)
    return out


@route("GET", "/api/challenges", mutates=False)
def api_challenges(req):
    req.dirty = True                        # the week's challenges are made the first time anybody asks, and that must be kept
    return challenges.view(req.user)


@route("POST", "/api/challenges/claim")
def api_challenge_claim(req):
    out = challenges.claim(req.user, req.body.get("id"))
    out["user"] = me_json(req.user)
    return out


@route("GET", "/api/inbox", mutates=False)
def api_inbox(req):
    return inbox.view(req.user)


@route("POST", "/api/inbox/seen")
def api_inbox_seen(req):
    ids = req.body.get("ids")
    if ids is not None and not (isinstance(ids, list) and all(isinstance(i, str) for i in ids)):
        raise bad("Invalid notifications")
    inbox.mark_seen(req.user, set(ids) if ids is not None else None)
    return {"unseen": len(inbox.unseen(req.user))}


@route("GET", "/api/transfers", mutates=False)
def api_transfers(req):
    return transfers.view(req.user)


@route("POST", "/api/transfers/preview", mutates=False)
def api_transfer_preview(req):
    return transfers.preview(req.user, req.body)


@route("POST", "/api/transfers")
def api_transfer_send(req):
    out = transfers.send(req.user, req.body)
    out["user"] = me_json(req.user)
    return out


@route("POST", "/api/transfers/password")
def api_transfer_password(req):
    what = transfers.set_password(req.user, req.body.get("loginPassword"), req.body.get("newPassword"), req.body.get("currentPassword"), req.body.get("code"))
    m = req.user.get("mail") or {}
    if what != "set" and m.get("verified") and m.get("addr") and mailer.delivery_on():
        mailer.send_async(m["addr"], *transfers.changed_message("changed" if what == "changed" else "reset"))
    return {"ok": True, "result": what, "transfers": transfers.view(req.user)}


@route("POST", "/api/transfers/password/code")
def api_transfer_password_code(req):
    addr, code = transfers.request_reset_code(req.user, req.body.get("loginPassword"))
    mailer.send_async(addr, *transfers.reset_message(code))
    return {"ok": True, "message": "We sent a code to your confirmed email address."}


# ---- circles -------------------------------------------------------------------------

@route("GET", "/api/circles")
def api_circles(req):
    allc = sorted(circles.visible_to(req.user), key=lambda c: -len(c["members"]))
    mine = [circles.summary(c, req.user) for c in allc if circles.is_member(c, req.user)]
    discover = [circles.summary(c, req.user) for c in allc if not circles.is_member(c, req.user)]
    return {"mine": mine, "discover": discover}


@route("POST", "/api/circles")
def api_circle_create(req):
    c = circles.create(req.user, req.body)
    hub.publish({"type": "circle", "id": c["id"]}, c["id"])
    return {"circle": circles.summary(c, req.user)}


@route("POST", "/api/circles/join")
def api_circle_join_code(req):
    c = circles.join_by_code(req.user, req.body.get("code"))
    hub.publish({"type": "circle", "id": c["id"]}, c["id"])
    return {"circle": circles.summary(c, req.user)}


@route("GET", r"/api/circles/(\w+)")
def api_circle_get(req, cid):
    c = circles.view_or_404(cid, req.user)
    rows = weekly.standings(c, week_key())
    joined = c["members"]
    members = [{"user": r["user"], "value": r["value"], "delta": r["delta"], "position": r["position"], "active": r["active"],
                "joinedAt": joined[r["user"]["id"]], "isOwner": r["user"]["id"] == c["ownerId"]} for r in rows]
    return {"circle": circles.summary(c, req.user), "members": members, "rankBy": "performance"}


@route("PATCH", r"/api/circles/(\w+)")
def api_circle_update(req, cid):
    c = circles.update(req.user, cid, req.body)
    hub.publish({"type": "circle", "id": cid}, cid)
    return {"circle": circles.summary(c, req.user)}


@route("POST", r"/api/circles/(\w+)/join")
def api_circle_join(req, cid):
    c = circles.join(req.user, cid, req.body.get("code"))
    hub.publish({"type": "circle", "id": cid}, cid)
    return {"circle": circles.summary(c, req.user)}


@route("POST", r"/api/circles/(\w+)/leave")
def api_circle_leave(req, cid):
    circles.leave(req.user, cid)
    voice_leave_after_removal(req.user["id"], cid)
    hub.publish({"type": "circle", "id": cid})
    return {"ok": True}


@route("POST", r"/api/circles/(\w+)/regen")
def api_circle_regen(req, cid):
    c = circles.regen_code(req.user, cid)
    return {"circle": circles.summary(c, req.user)}


@route("POST", r"/api/circles/(\w+)/kick")
def api_circle_kick(req, cid):
    target = req.body.get("userId")
    circles.kick(req.user, cid, target)
    voice_leave_after_removal(target, cid)
    hub.publish({"type": "circle", "id": cid})
    return {"ok": True}


# ---- weekly poll / awards ------------------------------------------------------------

@route("GET", r"/api/circles/(\w+)/weekly")
def api_weekly(req, cid):
    c = circles.view_or_404(cid, req.user)
    return {"circle": circles.summary(c, req.user), **weekly.view(c, req.user, q1(req, "week"))}


@route("POST", r"/api/circles/(\w+)/punishments")
def api_punish_add(req, cid):
    c = circles.get(cid)
    weekly.add_punishment(req.user, c, req.body.get("text"))
    hub.publish({"type": "weekly", "circleId": cid}, cid)
    return {"ok": True}


@route("POST", r"/api/circles/(\w+)/punishments/(\w+)/vote")
def api_punish_vote(req, cid, pid):
    weekly.vote(req.user, circles.get(cid), pid)
    hub.publish({"type": "weekly", "circleId": cid}, cid)
    return {"ok": True}


@route("DELETE", r"/api/circles/(\w+)/punishments/(\w+)")
def api_punish_delete(req, cid, pid):
    weekly.delete_punishment(req.user, circles.get(cid), pid)
    hub.publish({"type": "weekly", "circleId": cid}, cid)
    return {"ok": True}


@route("POST", r"/api/circles/(\w+)/recaps/([\d-]+)/served")
def api_served(req, cid, week):
    weekly.mark_served(req.user, circles.get(cid), week)
    hub.publish({"type": "weekly", "circleId": cid}, cid)
    return {"ok": True}


# ---- markets -------------------------------------------------------------------------

@route("GET", "/api/markets")
def api_markets(req):
    rows = markets.list_markets(req.user, circle=q1(req, "circle"), q=q1(req, "q"), category=q1(req, "category"),
                                status=q1(req, "status", "open"), sort=q1(req, "sort", "trending"))
    return {"markets": rows}


@route("POST", "/api/markets")
def api_market_create(req):
    m = markets.create(req.user, req.body)
    hub.publish({"type": "market", "action": "created", "id": m["id"], "circleId": m["circleId"],
                 "question": m["question"], "by": req.user["username"]}, m["circleId"])
    return {"market": markets.summary(m, req.user)}


@route("POST", r"/api/markets/(\w+)/edit/preview", mutates=False)
def api_market_edit_preview(req, mid):
    m = markets.view_or_404(mid, req.user)
    return {"preview": markets.edit_preview(req.user, m, req.body)}


@route("POST", r"/api/markets/(\w+)/edit")
def api_market_edit(req, mid):
    m = markets.view_or_404(mid, req.user)
    out = markets.edit_apply(req.user, m, req.body)
    if not out.get("duplicate"):
        hub.publish({"type": "market", "action": "edited", "id": m["id"], "circleId": m["circleId"], "question": m["question"],
                     "by": req.user["username"], "material": out["class"] == "material"}, m["circleId"])
    return {"edit": out, "market": markets.detail(m, req.user)}


@route("GET", r"/api/markets/(\w+)/history", mutates=False)
def api_market_history(req, mid):
    m = markets.view_or_404(mid, req.user)
    return markets.history(m, req.user)


@route("POST", r"/api/markets/(\w+)/withdraw")
def api_market_withdraw(req, mid):
    m = markets.view_or_404(mid, req.user)
    out = markets.withdraw(req.user, m, req.body)
    if not out.get("duplicate"):
        hub.publish({"type": "market", "action": "trade", "id": m["id"], "circleId": m["circleId"]}, m["circleId"])
    return {**out, "user": me_json(req.user), "market": markets.detail(m, req.user)}


@route("GET", r"/api/markets/(\w+)")
def api_market_get(req, mid):
    return {"market": markets.detail(markets.view_or_404(mid, req.user), req.user)}


@route("POST", r"/api/markets/(\w+)/quote", mutates=False)
def api_market_quote(req, mid):
    return {"quote": markets.quote(markets.view_or_404(mid, req.user), req.user, req.body)}


@route("POST", r"/api/markets/(\w+)/trade")
def api_market_trade(req, mid):
    m = markets.view_or_404(mid, req.user)
    result = markets.trade(req.user, m, req.body)
    if not result["duplicate"]:                        # a repeated request changes nothing, so there is nothing to announce
        hub.publish({"type": "market", "action": "trade", "id": mid, "circleId": m["circleId"]}, m["circleId"])
    return {"trade": result, "user": me_json(req.user), "market": markets.detail(m, req.user)}


@route("POST", r"/api/markets/(\w+)/resolve")
def api_market_resolve(req, mid):
    m = markets.view_or_404(mid, req.user)
    markets.resolve(req.user, m, req.body.get("outcome"))
    hub.publish({"type": "market", "action": "resolved", "id": mid, "circleId": m["circleId"],
                 "question": m["question"]}, m["circleId"])
    return {"market": markets.detail(m, req.user), "user": me_json(req.user)}


@route("POST", r"/api/markets/(\w+)/cancel")
def api_market_cancel(req, mid):
    m = markets.view_or_404(mid, req.user)
    markets.cancel(req.user, m)
    hub.publish({"type": "market", "action": "cancelled", "id": mid, "circleId": m["circleId"]}, m["circleId"])
    return {"market": markets.detail(m, req.user), "user": me_json(req.user)}


@route("POST", r"/api/markets/(\w+)/comments")
def api_market_comment(req, mid):
    m = markets.view_or_404(mid, req.user)
    markets.add_comment(req.user, m, req.body.get("text"))
    hub.publish({"type": "market", "action": "comment", "id": mid, "circleId": m["circleId"]}, m["circleId"])
    return {"market": markets.detail(m, req.user)}


# ---- portfolio & profiles ------------------------------------------------------------

@route("GET", "/api/portfolio")
def api_portfolio(req):
    out = markets.portfolio(req.user)
    out["history"] = req.user["history"][:50]
    return out


@route("GET", "/api/portfolio/overview", mutates=False)
def api_portfolio_overview(req):
    return wealth.overview(req.user)


@route("GET", r"/api/users/([A-Za-z0-9_]+)")
def api_user(req, name):
    u = users.by_username(name)
    counts, recent = weekly.trophies(u)
    totals = {}
    for wk in u["stats"].values():
        for k, v in wk.items():
            if isinstance(v, (int, float)) and k not in ("biggestBet", "bestWin", "badBeat", "biggestGameWin",
                                                         "chickenBest", "limboBest"):
                totals[k] = totals.get(k, 0) + v
    return {"user": {"id": u["id"], "username": u["username"], "createdAt": u["createdAt"],
                     "profile": {k: v for k, v in cosmetics.profile_json(u).items() if k not in ("fonts", "backgrounds")}},
            "netWorth": markets.net_worth(u), "rank": progress.rank_of(u), "trophies": counts, "recent": recent, "totals": totals,
            "awardDefs": weekly.AWARD_DEFS,
            "rewards": weekly.reward_history(u)[:40] if req.user and req.user["id"] == u["id"] else None,
            "accounts": {"weekly": u["balance"], "accumulated": u.get("accum", 0.0)} if req.user and req.user["id"] == u["id"] else None,
            "circles": [{"id": c["id"], "name": c["name"], "emoji": c["emoji"]} for c in circles.visible_to(req.user)
                        if u["id"] in c["members"]]}


# ---- voice rooms (signaling only: the audio goes straight between browsers) -----------------

def voice_announce(cid, extra=None):
    """Tells every member of a circle who is in its voice room now."""
    ev = {"type": "voice", "k": "room", "room": cid, "people": voice.people(cid), **(extra or {})}
    hub.publish_users(ev, voice.members_of(cid))


def voice_leave_after_removal(uid, cid):
    """Somebody left or was removed from a circle: they are no longer allowed in its voice room."""
    with voice._lock:
        mine = (voice.ROOMS.get(cid) or {}).pop(uid, None)
        if cid in voice.ROOMS and not voice.ROOMS[cid]:
            voice.ROOMS.pop(cid, None)
    if mine:
        hub.publish_users({"type": "voice", "k": "removed", "room": cid, "sid": mine["sid"]}, [uid])
        voice_announce(cid)


@route("GET", "/api/voice/rooms", mutates=False)
def api_voice_rooms(req):
    return {"rooms": voice.rooms_for(req.user), "mine": voice.room_of(req.user["id"]), "maxPeople": economy.VOICE_MAX_PEOPLE}


@route("POST", "/api/voice/join", mutates=False)
def api_voice_join(req):
    out = voice.join(req.user, req.body.get("circleId"), req.body.get("sid"))
    if out["replacedSid"]:
        hub.publish_users({"type": "voice", "k": "replaced", "room": out["room"], "sid": out["replacedSid"]}, [req.user["id"]])
    for cid in out.pop("changed"):
        voice_announce(cid)
    out.pop("replacedSid")
    return out


@route("POST", "/api/voice/leave", mutates=False)
def api_voice_leave(req):
    cid = req.body.get("circleId")
    left = voice.leave(req.user, cid, req.body.get("sid"))
    if left:
        voice_announce(cid)
    return {"ok": True, "left": left}


@route("POST", "/api/voice/state", mutates=False)
def api_voice_state(req):
    cid = req.body.get("circleId")
    out = voice.state(req.user, cid, req.body.get("sid"), req.body.get("muted"), req.body.get("deaf"))
    if out["changed"]:
        voice_announce(cid)
    return {"inRoom": out["inRoom"], "people": out.get("people", [])}


@route("POST", "/api/voice/signal", mutates=False)
def api_voice_signal(req):
    event, target = voice.signal(req.user, req.body.get("circleId"), req.body.get("sid"), req.body.get("to"), req.body.get("toSid"), req.body.get("data"))
    hub.publish_users(event, [target])
    return {"ok": True}


# ---- the stock exchange (all pretend; prices are the same for everyone) --------------------

@route("GET", "/api/stocks", mutates=False)
def api_stocks(req):
    return exchange.listing(req.user)


@route("GET", "/api/stocks/portfolio", mutates=False)
def api_stocks_portfolio(req):
    return exchange.portfolio(req.user)


@route("GET", "/api/stocks/news", mutates=False)
def api_stocks_news(req):
    eng = exchange.market()
    return {"news": [exchange._news_json(n) for n in eng.news(q1(req, "symbol"), 30)], "simulated": True}


@route("GET", r"/api/stocks/([A-Za-z]{2,6})", mutates=False)
def api_stock(req, sym):
    return exchange.detail(req.user, sym.upper(), q1(req, "interval", "5m"), q1(req, "limit", "200"))


@route("POST", "/api/stocks/quote", mutates=False)
def api_stocks_quote(req):
    return exchange.quote(req.user, req.body)


@route("POST", "/api/stocks/trade")
def api_stocks_trade(req):
    out = exchange.trade(req.user, req.body)
    out["user"] = me_json(req.user)
    return out


# ---- the store and profile personalization -----------------------------------------------

@route("GET", "/api/store", mutates=False)
def api_store(req):
    return cosmetics.store_view(req.user)


@route("POST", "/api/store/buy")
def api_store_buy(req):
    result = cosmetics.buy(req.user, req.body.get("item"), req.body.get("requestId"))
    return {**result, "store": cosmetics.store_view(req.user), "user": me_json(req.user)}


@route("POST", "/api/store/equip")
def api_store_equip(req):
    return {"profile": cosmetics.equip(req.user, req.body.get("item")), "store": cosmetics.store_view(req.user)}


@route("POST", "/api/store/unequip")
def api_store_unequip(req):
    return {"profile": cosmetics.unequip(req.user, req.body.get("kind")), "store": cosmetics.store_view(req.user)}


@route("GET", "/api/profile", mutates=False)
def api_my_profile(req):
    return {"profile": cosmetics.profile_json(req.user)}


@route("POST", "/api/profile")
def api_profile_save(req):
    return {"profile": cosmetics.customize(req.user, req.body)}


@route("POST", "/api/profile/avatar")
def api_profile_avatar(req):
    out = cosmetics.set_upload(req.user, req.body.get("_raw"), req.body.get("_type"))
    return {"profile": out["profile"], "width": out["width"], "height": out["height"]}


@route("DELETE", "/api/profile/avatar")
def api_profile_avatar_remove(req):
    return {"profile": cosmetics.remove_upload(req.user)}


# ---- games ---------------------------------------------------------------------------

def demo_asked(req):
    return q1(req, "demo") == "1"


def acct_asked(req):
    """Which account a casino request plays with: "accumulated", or nothing for the weekly account (see games.account_for)."""
    return q1(req, "acct")


@route("GET", "/api/games/state", mutates=True)
def api_games_state(req):
    acct = games.account_for(req.user, demo_asked(req), acct_asked(req))
    out = games.active_state(acct)
    out["balance"] = acct["balance"]
    return out


@route("GET", "/api/games/meta")
def api_games_meta(req):
    return {"chicken": {k: {"lanes": v["lanes"], "chance": v["p"], "mults": games.chicken_table(k)}
                        for k, v in games.CHICKEN.items()},
            "limboRtp": games.LIMBO_RTP, "minBet": config.MIN_BET,
            "coinflip": {"maxFlips": games.COIN_MAX_FLIPS, "mults": [games.coin_mult(n) for n in range(1, games.COIN_MAX_FLIPS + 1)]},
            "dice": {"rtp": games.DICE_RTP, "maxChance": games.DICE_MAX_CHANCE / 100},
            "war": {"tiePays": games.WAR_TIE_PAYS, "colouredTiePays": games.WAR_COLOUR_TIE_PAYS},
            "mines": {"sizes": list(games.MINES_SIZES)},
            "hilo": {"rtp": games.HILO_RTP_X100 / 100, "maxSkips": games.HILO_MAX_SKIPS},
            "wheel": {"segments": games.WHEEL_SEGMENTS, "rtp": games.WHEEL_RTP_X100 / 100,
                      "risks": {k: {"layout": [m / 100 for m in games.wheel_layout(k)], "table": games.wheel_table(k)} for k in games.WHEEL_RISKS}},
            "rps": {"ladder": games.rps_ladder(), "maxWins": games.RPS_MAX_WINS, "rtp": games.RPS_RTP_X100 / 100},
            "moles": {"holes": games.MOLES_HOLES, "tables": {str(m): games.moles_table(m) for m in range(1, games.MOLES_HOLES)}},
            "tower": {"rows": games.TOWER_ROWS, "risks": {k: {"cols": c, "traps": t, "mults": games.tower_table(k)}
                                                         for k, (c, t) in games.TOWER_RISK.items()}}}


@route("GET", "/api/games/mines/table")
def api_mines_table(req):
    try:
        size, mines = int(q1(req, "size", "25")), int(q1(req, "mines", "3"))
    except ValueError:
        raise bad("Pick a grid size and a number of mines")
    return {"mults": games.mines_table(size, mines)}


@route("GET", "/api/games/summary")
def api_games_summary(req):
    return games.profit_summary(req.user)


@route("GET", "/api/games/feed")
def api_games_feed(req):
    return {"feed": db()["feed"][:15]}


@route("GET", "/api/games/history")
def api_games_history(req):
    acct = games.account_for(req.user, demo_asked(req), acct_asked(req))
    return {"history": acct["history"][:40]}


@route("GET", "/api/games/demo", mutates=True)
def api_demo(req):
    return {"user": demo_json(games.demo_account(req.user))}


@route("POST", "/api/games/demo/reset")
def api_demo_reset(req):
    return {"user": demo_json(games.demo_reset(req.user))}


def _game_post(path, fn, takes_body=True):
    """Every game round runs on one wallet: the real one, or the practice one when the request says
    demo. The game code is identical either way; only the account it is handed differs."""
    @route("POST", path)
    def handler(req):
        acct = games.account_for(req.user, req.body.get("demo") is True, req.body.get("acct"))
        out = fn(acct, req.body) if takes_body else fn(acct)
        out["user"] = demo_json(acct) if acct.get("isDemo") else me_json(req.user)
        return out
    return handler


for _path, _fn, _body in (
        ("/api/games/limbo", "limbo", True), ("/api/games/roulette", "roulette", True),
        ("/api/games/blackjack/deal", "blackjack_deal", True), ("/api/games/blackjack/action", "blackjack_action", True),
        ("/api/games/chicken/start", "chicken_start", True), ("/api/games/chicken/step", "chicken_step", False),
        ("/api/games/chicken/cashout", "chicken_cashout", False),
        ("/api/games/coinflip", "coinflip", True), ("/api/games/dice", "dice", True), ("/api/games/war", "war", True),
        ("/api/games/mines/start", "mines_start", True), ("/api/games/mines/pick", "mines_pick", True),
        ("/api/games/mines/cashout", "mines_cashout", False),
        ("/api/games/moles/start", "moles_start", True), ("/api/games/moles/pick", "moles_pick", True),
        ("/api/games/moles/cashout", "moles_cashout", False),
        ("/api/games/tower/start", "tower_start", True), ("/api/games/tower/pick", "tower_pick", True),
        ("/api/games/tower/cashout", "tower_cashout", False),
        ("/api/games/hilo/start", "hilo_start", True), ("/api/games/hilo/guess", "hilo_guess", True),
        ("/api/games/hilo/skip", "hilo_skip", False), ("/api/games/hilo/cashout", "hilo_cashout", False),
        ("/api/games/wheel", "wheel", True),
        ("/api/games/rps/start", "rps_start", True), ("/api/games/rps/play", "rps_play", True),
        ("/api/games/rps/cashout", "rps_cashout", False)):
    _game_post(_path, getattr(games, _fn), _body)


# ---- poker ---------------------------------------------------------------------------
# The events carry no cards, only "table X changed": each browser then asks for its own view.

def poker_notify(tid, extra_ids=()):
    table = poker.tables().get(tid)
    if table is None:
        hub.publish({"type": "poker", "id": tid, "gone": True})
    elif table["visibility"] == "public":
        hub.publish({"type": "poker", "id": tid, "v": table["v"]})
    else:
        hub.publish_users({"type": "poker", "id": tid, "v": table["v"]},
                          [s["userId"] for s in poker.seated(table)] + list(extra_ids))


def poker_table_for(req, tid):
    t = poker.get(tid)
    if t["visibility"] == "private" and poker.seat_index(t, req.user["id"]) is None:
        raise bad("That table is gone", 404)             # private tables don't admit they exist
    return t


def poker_reply(req, tid, extra=None):
    t = poker.tables().get(tid)
    out = {"user": me_json(req.user), "table": poker.view(t, req.user["id"]) if t else None}
    out.update(extra or {})
    return out


@route("GET", "/api/poker/tables", mutates=False)
def api_poker_lobby(req):
    return {"tables": poker.lobby(req.user["id"]), "user": me_json(req.user)}


@route("POST", "/api/poker/tables")
def api_poker_create(req):
    t = poker.create(req.user, req.body)
    poker_notify(t["id"])
    return poker_reply(req, t["id"])


@route("POST", "/api/poker/join")
def api_poker_join(req):
    t = poker.join(req.user, req.body.get("id"), req.body.get("code"), req.body.get("confirm") is True)
    poker_notify(t["id"])
    return poker_reply(req, t["id"])


@route("GET", r"/api/poker/tables/(\w+)", mutates=False)
def api_poker_table(req, tid):
    t = poker_table_for(req, tid)
    if poker.catch_up(t):
        req.dirty = True                           # watching a table must not rewrite the whole database unless a timer fired
        poker_notify(tid)
    return poker_reply(req, tid) if tid in poker.tables() else {"table": None, "user": me_json(req.user)}


@route("POST", r"/api/poker/tables/(\w+)/settings")
def api_poker_settings(req, tid):
    t = poker_table_for(req, tid)
    poker.set_settings(req.user, t, req.body)
    poker_notify(tid)
    return poker_reply(req, tid)


@route("POST", r"/api/poker/tables/(\w+)/vote")
def api_poker_vote(req, tid):
    t = poker_table_for(req, tid)
    poker.vote(req.user, t, req.body.get("accept"))
    poker_notify(tid)
    return poker_reply(req, tid)


@route("POST", r"/api/poker/tables/(\w+)/start")
def api_poker_start(req, tid):
    t = poker_table_for(req, tid)
    poker.start(req.user, t)
    poker_notify(tid)
    return poker_reply(req, tid)


@route("POST", r"/api/poker/tables/(\w+)/action")
def api_poker_action(req, tid):
    t = poker_table_for(req, tid)
    poker.act(req.user, t, req.body.get("action"), req.body.get("amount"))
    poker_notify(tid)
    return poker_reply(req, tid)


@route("POST", r"/api/poker/tables/(\w+)/leave")
def api_poker_leave(req, tid):
    t = poker_table_for(req, tid)
    seated_before = [s["userId"] for s in poker.seated(t)]
    poker.leave(req.user, t)
    poker_notify(tid, seated_before)
    after = poker.tables().get(tid)
    return poker_reply(req, tid, {"left": after is None or poker.seat_index(after, req.user["id"]) is None})


@route("POST", r"/api/poker/tables/(\w+)/kick")
def api_poker_kick(req, tid):
    t = poker_table_for(req, tid)
    seated_before = [s["userId"] for s in poker.seated(t)]
    poker.kick(req.user, t, req.body.get("userId"))
    poker_notify(tid, seated_before)
    return poker_reply(req, tid)


@route("POST", r"/api/poker/tables/(\w+)/end")
def api_poker_end(req, tid):
    t = poker_table_for(req, tid)
    poker.end_game(req.user, t)
    poker_notify(tid)
    return poker_reply(req, tid)


@route("POST", r"/api/poker/tables/(\w+)/rebuy")
def api_poker_rebuy(req, tid):
    t = poker_table_for(req, tid)
    poker.rebuy(req.user, t)
    poker_notify(tid)
    return poker_reply(req, tid)


# ---- friends and who is online --------------------------------------------------------
# Events only say "something changed"; each browser then asks for what it is allowed to see.

def presence_notify(uid):
    hub.publish_users({"type": "presence", "id": uid}, social.friend_ids(uid))


@route("GET", "/api/friends", mutates=False)
def api_friends(req):
    return social.view(req.user)


@route("GET", "/api/friends/search", mutates=False)
def api_friend_search(req):
    return {"users": social.search(req.user, q1(req, "q"))}


@route("POST", "/api/friends/request")
def api_friend_request(req):
    other = users.by_username(req.body.get("username"))["id"]
    outcome = social.request(req.user, req.body.get("username"))
    hub.publish_users({"type": "friends", "what": outcome, "by": req.user["username"]}, [req.user["id"], other])
    return {**social.view(req.user), "outcome": outcome}


@route("POST", "/api/friends/accept")
def api_friend_accept(req):
    other = req.body.get("userId")
    social.accept(req.user, other)
    hub.publish_users({"type": "friends", "what": "friends", "by": req.user["username"]}, [req.user["id"], other])
    return {**social.view(req.user), "outcome": "friends"}


def _friend_change(action):
    def handler(req):
        other = req.body.get("userId")
        action(req.user, other)
        hub.publish_users({"type": "friends", "what": "changed"}, [req.user["id"], other])
        return social.view(req.user)
    return handler


for _path, _fn in (("decline", social.decline), ("cancel", social.cancel), ("remove", social.remove)):
    route("POST", f"/api/friends/{_path}")(_friend_change(_fn))


@route("POST", "/api/friends/hide")
def api_friend_hide(req):
    social.set_hidden(req.user, req.body.get("hide"))
    presence_notify(req.user["id"])
    return social.view(req.user)


@route("POST", "/api/presence", mutates=False)
def api_presence(req):
    if social.ping(req.user, req.body.get("where"), req.body.get("visible", True)):
        presence_notify(req.user["id"])
    return {"ok": True}


# ---- chats -----------------------------------------------------------------------------

def chat_notify(chat, msg):
    title = chats.title(chat, None) if chat["kind"] == "circle" else (chat["name"] or None) if chat["kind"] == "group" else None
    event = {"type": "chat", "id": chat["id"], "kind": chat["kind"], "title": title, "msg": chats.fmt(msg)}
    ids = chats.recipients(chat)
    if ids is None:
        hub.publish(event)
    else:
        hub.publish_users(event, ids)


def chats_changed(ids):
    hub.publish_users({"type": "chats"}, ids)


@route("GET", "/api/ranking")
def api_ranking(req):
    """Everybody on the site, by the money in their accumulated account."""
    return ranking.board(req.user)


def _int_or_none(text):
    return int(text) if text and text.isdigit() else None


@route("GET", "/api/chats", mutates=False)
def api_chats(req):
    return {"chats": chats.list_for(req.user), "receipts": chats.receipts_on(req.user["id"])}


@route("POST", "/api/chats/receipts")
def api_chat_receipts(req):
    chats.set_receipts(req.user, req.body.get("on"))
    return {"receipts": chats.receipts_on(req.user["id"])}


@route("GET", "/api/chats/unread", mutates=False)
def api_chats_unread(req):
    return chats.unread_totals(req.user)


@route("GET", r"/api/chats/(\w+)", mutates=False)
def api_chat(req, cid):
    return chats.history(req.user, cid, before=_int_or_none(q1(req, "before")), after=_int_or_none(q1(req, "after")))


@route("POST", r"/api/chats/(\w+)/send")
def api_chat_send(req, cid):
    chat, msg = chats.send(req.user, cid, req.body.get("text"))
    chat_notify(chat, msg)
    return {"message": chats.fmt(msg)}


@route("POST", r"/api/chats/(\w+)/read", mutates=False)
def api_chat_read(req, cid):
    chat, moved = chats.mark_read(req.user, cid, req.body.get("upTo"))
    if moved:                                      # there is something new to remember (and to tell the others, if allowed)
        req.dirty = True
        hub.publish_users({"type": "seen", "id": cid, "u": req.user["id"], "name": req.user["username"], "n": moved[0], "t": moved[1]},
                          chats.seen_audience(chat, req.user["id"]))
    return chats.unread_totals(req.user)


@route("POST", r"/api/chats/(\w+)/delete")
def api_chat_delete(req, cid):
    chats.delete_message(req.user, cid, req.body.get("n"))
    chat = chats.chat_for(req.user, cid)
    ids = chats.recipients(chat)
    event = {"type": "chat", "id": cid, "del": req.body.get("n")}
    hub.publish(event) if ids is None else hub.publish_users(event, ids)
    return {"ok": True}


@route("POST", "/api/chats/dm")
def api_chat_dm(req):
    chat = chats.open_dm(req.user, req.body.get("userId"))
    return {"chat": chats.detail(req.user, chat)}


@route("POST", "/api/chats/group")
def api_chat_group(req):
    chat = chats.create_group(req.user, req.body.get("name"), req.body.get("members"))
    chats_changed(chat["members"])
    return {"chat": chats.detail(req.user, chat)}


@route("POST", r"/api/chats/(\w+)/members")
def api_chat_members(req, cid):
    if req.body.get("remove"):
        before = chats.recipients(chats.chat_for(req.user, cid))
        chat = chats.remove_member(req.user, cid, req.body["remove"])
        chats_changed(before)
    else:
        chat = chats.add_members(req.user, cid, req.body.get("add"))
        chats_changed(chat["members"])
    return {"chat": chats.detail(req.user, chat)}


@route("POST", r"/api/chats/(\w+)/rename")
def api_chat_rename(req, cid):
    chat = chats.rename(req.user, cid, req.body.get("name"))
    chats_changed(chat["members"])
    return {"chat": chats.detail(req.user, chat)}


@route("POST", r"/api/chats/(\w+)/leave")
def api_chat_leave(req, cid):
    before = chats.recipients(chats.chat_for(req.user, cid))
    chats.leave(req.user, cid)
    chats_changed(before)
    return {"ok": True}


# ---- HTTP plumbing -------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Clique"

    def log_message(self, fmt, *args):
        if "/api/stream" not in str(args[0] if args else ""):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):                      # uptime monitors send HEAD
        self._dispatch("HEAD")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # -- helpers
    def _ip(self):
        fwd = self.headers.get("X-Forwarded-For")
        return fwd.split(",")[0].strip() if fwd else self.client_address[0]

    def _token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            c = SimpleCookie(raw)
            return c["sid"].value if "sid" in c else None
        except Exception:
            return None

    def _send(self, status, body, ctype="application/json; charset=utf-8", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, payload, headers=None):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        h = {"Cache-Control": "no-store"}
        h.update(headers or {})
        if len(body) > 1400 and self._accepts_gzip():          # long lists shrink to a fraction of their size
            body = gzip.compress(body, 5)
            h["Content-Encoding"] = "gzip"
            h["Vary"] = "Accept-Encoding"
        self._send(status, body, headers=h)

    def _accepts_gzip(self):
        return "gzip" in (self.headers.get("Accept-Encoding") or "").lower()

    def _cookie_header(self, token, clear=False):
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        if clear:
            return f"sid=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"
        return f"sid={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={config.SESSION_DAYS * 86400}{secure}"

    # -- routing
    def _dispatch(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            if path == "/api/stream" and method == "GET":
                return self._stream()
            return self._api(method, path, urllib.parse.parse_qs(parsed.query))
        if method not in ("GET", "HEAD"):
            return self._json(404, {"error": "Not found"})
        if path.startswith("/uploads/avatars/"):
            return self._upload(path.rsplit("/", 1)[1])
        self._static(path)

    def _api(self, method, path, query):
        match = None
        for m, rx, fn, auth, mutates in ROUTES:
            if m != method:
                continue
            hit = rx.match(path)
            if hit:
                match = (fn, hit.groups(), auth, mutates)
                break
        if not match:
            return self._json(404, {"error": "Not found"})
        fn, groups, needs_auth, mutates = match
        unread = False
        ticket = None
        try:
            body = {}
            if method != "GET":
                unread = int(self.headers.get("Content-Length") or 0) > 0
                origin = self.headers.get("Origin")
                if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host"):
                    raise bad("Cross-site request blocked", 403)
                length = int(self.headers.get("Content-Length") or 0)
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
                if (method, path) in RAW_UPLOADS:                                  # a picture, sent as the file itself
                    if length > economy.AVATAR_MAX_BYTES:
                        raise bad(f"That picture is too big. The limit is {economy.AVATAR_MAX_BYTES / 1_000_000:.1f} MB.", 413)
                    if ctype not in ("image/png", "image/jpeg", "image/webp"):
                        raise bad("Send a PNG, JPEG or WebP picture", 415)
                    body = {"_raw": self.rfile.read(length), "_type": ctype}
                    unread = False
                else:
                    if length > 1_000_000:
                        raise bad("Request too large", 413)
                    if length:
                        if ctype != "application/json":
                            raise bad("Expected JSON", 415)
                        try:
                            body = json.loads(self.rfile.read(length) or b"{}")
                            unread = False
                        except ValueError:
                            unread = False
                            raise bad("Invalid JSON")
                        if not isinstance(body, dict):
                            raise bad("Invalid JSON")
            token = self._token()
            ticket = None
            with LOCK:
                user = users.user_for_token(token)
                if needs_auth and not user:
                    raise bad("Please log in", 401)
                req = Req(user, body, query, self._ip(), token)
                bookmark = inbox.mark()
                try:
                    with ledger.source(reason_for(method, path)):
                        result = fn(req, *groups)
                except Exception as failure:
                    inbox.rollback(bookmark)                     # notifications of a request that failed were undone with it
                    if getattr(failure, "persist", False):       # a wrong-password count must survive the error answer
                        ticket = store.stage()
                    raise
                if mutates or req.dirty:
                    ticket = store.stage()                  # snapshot in memory while we hold the lock...
            if ticket:
                store.commit(ticket)                        # ...and write it to disk after letting everyone else in
            announce_inbox()
            headers = {}
            if req.new_token:
                headers["Set-Cookie"] = self._cookie_header(req.new_token)
            elif req.clear_token:
                headers["Set-Cookie"] = self._cookie_header(None, clear=True)
            self._json(200, result, headers)
        except ApiError as e:
            if ticket:                                          # an error that has to be remembered (wrong transfer passwords): save it
                try:
                    store.commit(ticket)
                except Exception:
                    traceback.print_exc()
            if unread:                                          # refused before the body was read: the leftover bytes would
                self.close_connection = True                    # be mistaken for the next request, so end this connection
            self._json(e.status, {"error": e.message, **(e.data or {})}, {"Connection": "close"} if unread else None)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            self.close_connection = True
            try:
                self._json(500, {"error": "Something went wrong on the server"}, {"Connection": "close"})
            except Exception:
                pass

    def _stream(self):
        with LOCK:
            user = users.user_for_token(self._token())
        if not user:
            return self._json(401, {"error": "Please log in"})
        client = Client(user["id"])
        hub.add(client)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(b"retry: 3000\n\n")
            self.wfile.flush()
            while True:
                try:
                    event = client.q.get(timeout=20)
                    self.wfile.write(b"data: " + json.dumps(event).encode("utf-8") + b"\n\n")
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            hub.remove(client)

    def _upload(self, name):
        """A profile picture. Only members can see them, only names this server made are served, and the type sent is the
        one found when the picture was checked, never one a visitor chose."""
        with LOCK:
            who = users.user_for_token(self._token())
        found = cosmetics.read_upload(name) if who else None
        if not found:
            return self._json(404, {"error": "Not found"})
        data, ctype = found
        self._send(200, data, ctype, {"Cache-Control": "private, max-age=31536000, immutable", "Content-Disposition": "inline"})

    def _static(self, path):
        asset = assets.get(assets.find(urllib.parse.unquote(path)))
        gz = asset.gz is not None and self._accepts_gzip()
        etag = asset.etag_for(gz)
        headers = {"ETag": etag, "Cache-Control": asset.cache}
        if asset.gz is not None:
            headers["Vary"] = "Accept-Encoding"
        if assets.matches(self.headers.get("If-None-Match"), etag):      # the browser already has this exact file
            self.send_response(304)
            for k, v in {**SECURITY_HEADERS, **headers}.items():
                self.send_header(k, v)
            self.end_headers()
            return
        if gz:
            headers["Content-Encoding"] = "gzip"
        self._send(200, asset.gz if gz else asset.body, asset.ctype, headers)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


def announce_inbox():
    """Tells each person's open browsers about the notifications that were just saved for them."""
    for ev in inbox.drain():
        hub.publish_users({"type": "inbox", "item": ev["item"]}, [ev["userId"]])


def announce_week_events():
    """Tells people what the weekly close did, once it has been saved: rewards to each person, a new-week notice to all."""
    events, weekly.EVENTS[:] = list(weekly.EVENTS), []
    for ev in events:
        hub.publish_users({k: v for k, v in ev.items() if k != "userId"}, [ev["userId"]])


def background():
    stop = threading.Event()
    n = 0
    while not stop.wait(1):
        n += 1
        try:
            ticket = None
            with LOCK:
                if weekly.tick():                          # every second: a week boundary is exact to the second
                    ticket = store.stage()
                    hub.publish({"type": "week"})
                if fundvotes.tick():                       # a vote on added funds whose time is up
                    ticket = store.stage()
                if n % 10 == 0:
                    for cid in voice.sweep():              # people who went quiet in a voice room are out of it
                        voice_announce(cid)
                    gone = social.sweep()                  # browsers that went quiet: those people are offline now
                    if gone:
                        ticket = store.stage()
                        for uid in gone:
                            presence_notify(uid)
            if ticket:
                store.commit(ticket)
                announce_week_events()
                announce_inbox()
        except Exception:
            traceback.print_exc()


def stocks_loop():
    """Moves the market about once a second and saves it every few seconds."""
    stop = threading.Event()
    last_save = 0.0
    while not stop.wait(economy.STOCK_TICK_S):
        try:
            blob = None
            with LOCK:
                exchange.engine.tick()
                if time.time() - last_save >= economy.STOCK_SAVE_EVERY_S:
                    last_save, blob = time.time(), exchange.engine.snapshot()
            if blob:
                exchange.engine.write(blob)
        except Exception:
            traceback.print_exc()


def poker_loop():
    stop = threading.Event()
    while not stop.wait(1.0):
        try:
            ticket = None
            with LOCK:
                changed = poker.tick()
                if changed:
                    ticket = store.stage()
                    for tid in changed:
                        poker_notify(tid)
            if ticket:
                store.commit(ticket)
                announce_inbox()
        except Exception:
            traceback.print_exc()


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def _stop(*_):
    raise KeyboardInterrupt


def main():
    if config.PRODUCTION and not os.path.ismount(config.DATA_DIR):
        print(f"\n  WARNING: {config.DATA_DIR} is not a mounted volume. If this host wipes its disk on every\n"
              "  deploy, every account and balance will be lost. Attach a volume at that path (see DEPLOY.md).\n",
              file=sys.stderr, flush=True)
    store.load()
    if store.migrated:                                  # a one-off change to how data is saved; a copy of the old file is in backups/
        note = (store.data.get("meta") or {}).get("accounts_migration") or {}
        print(f"  Data migration ran: {', '.join(store.migrated)}"
              + (f" ({note['people']} accounts, ${note['movedToAccumulated']:,.2f} moved to the accumulated account)." if "split_accounts" in store.migrated and note else "."),
              flush=True)
    with LOCK:
        weekly.tick()
        weekly.pay_rewards()                       # anything decided before a restart and not yet delivered
        done = seed.season_reset_if_requested(store)
        if done:
            print(f"  New season '{done['label']}': {done['users']} accounts back to ${done['balance']:,.2f}.")
        store.save()
    exchange.engine = stockengine.Engine(path=os.path.join(config.DATA_DIR, "market.json"))
    with LOCK:
        exchange.engine.load()
    if exchange.engine.catchup:
        c = exchange.engine.catchup
        print(f"  Stock market: replayed {c['replayedSeconds'] // 60} minutes it missed while the server was off"
              f"{' (the outage was longer, so only the last part is replayed)' if c['capped'] else ''}.")
    # Hosts stop a program with SIGTERM. Treat it like Ctrl+C so the final save below runs.
    signal.signal(signal.SIGTERM, _stop)
    threading.Thread(target=background, daemon=True).start()
    threading.Thread(target=poker_loop, daemon=True).start()
    threading.Thread(target=stocks_loop, daemon=True).start()
    server = Server((config.HOST, config.PORT), Handler)
    print("\n  Clique is running!\n")
    print(f"  On this computer:      http://localhost:{config.PORT}")
    ip = lan_ip()
    if ip:
        print(f"  Friends on your Wi-Fi: http://{ip}:{config.PORT}")
    print("\n  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Saving and shutting down...")
    finally:
        with LOCK:
            store.save()
            blob = exchange.engine.snapshot()
        exchange.engine.write(blob)
        server.server_close()


if __name__ == "__main__":
    main()
