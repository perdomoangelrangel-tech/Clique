"""Voice rooms: one room per circle, for the members of that circle only. Nothing is recorded, and nothing here touches audio.

The audio itself travels directly between the people in the call (WebRTC, browser to browser, each person connected to each
other person). This server only does the introductions, which is called signaling: a person says "I am joining", the others
are told, and the small setup messages (session descriptions and network candidates) are passed from one person to another.
Those messages ride the same live-update stream the site already has, and are sent only to the one person they are for.

Rules the server enforces:
  * only members of a circle can see that its room exists, who is in it, join it, or send anything inside it,
  * a message can only be sent to somebody who is in the same room,
  * a person is in one room at a time, with one browser tab (opening it in a second tab moves the call there),
  * a room holds VOICE_MAX_PEOPLE people (a mesh of audio connections is for small groups),
  * people who stop checking in (closed laptop, lost signal) are removed after VOICE_STALE_S seconds and everybody is told.

STUN and TURN: people on ordinary home networks can connect with STUN servers alone (a public one is used by default). People
behind strict networks (some offices, some mobile carriers) need a TURN relay. Set ICE_SERVERS, or TURN_URL with TURN_SECRET
(a coturn server using "use-auth-secret"): short-lived passwords are then made for each person as they join.
"""
import base64
import hashlib
import hmac
import json
import re
import threading
import time

from . import circles, economy, users
from .util import bad, now_ms

_lock = threading.Lock()
ROOMS = {}                         # circle id -> {user id: {"sid", "joined", "seen", "muted", "deaf"}}
_signals = {}                      # user id -> recent signal times, for the rate limit
SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,40}$")
SIGNAL_TYPES = ("offer", "answer", "candidate", "ready")
MAX_SIGNAL_BYTES = 20_000
SIGNALS_PER_10S = 120


def _member(user, cid):
    c = circles.get(cid)
    if not circles.is_member(c, user):
        raise bad("Join this circle first", 403, code="not_circle_member")
    return c


def _sid(value):
    if not isinstance(value, str) or not SID_RE.match(value):
        raise bad("Invalid session", code="invalid_request")
    return value


def room_of(user_id):
    for cid, room in ROOMS.items():
        if user_id in room:
            return cid
    return None


def _person(uid, p):
    u = users.get(uid)
    return {**users.public(u), "muted": p["muted"], "deaf": p["deaf"], "since": p["joined"]}


def people(cid):
    return [_person(uid, p) for uid, p in sorted((ROOMS.get(cid) or {}).items(), key=lambda kv: kv[1]["joined"])]


def ice_servers(user):
    servers = [dict(s) for s in economy.ICE_SERVERS]
    if economy.TURN_URL and economy.TURN_SECRET:
        expiry = int(time.time()) + economy.TURN_TTL_S
        name = f"{expiry}:{user['id']}"
        cred = base64.b64encode(hmac.new(economy.TURN_SECRET.encode(), name.encode(), hashlib.sha1).digest()).decode()
        servers.append({"urls": [u.strip() for u in economy.TURN_URL.split(",")], "username": name, "credential": cred})
    return servers


def join(user, cid, sid):
    """Puts the person in the circle's room (leaving any other room). Returns who is already there, so they can be called."""
    _member(user, cid)
    sid = _sid(sid)
    changed = {cid}
    with _lock:
        before = room_of(user["id"])
        if before and before != cid:
            ROOMS[before].pop(user["id"], None)
            changed.add(before)
        room = ROOMS.setdefault(cid, {})
        existing = room.get(user["id"])
        if not existing and len(room) >= economy.VOICE_MAX_PEOPLE:
            raise bad(f"This room is full ({economy.VOICE_MAX_PEOPLE} people)", 409, code="room_full")
        replaced = existing["sid"] if existing and existing["sid"] != sid else None
        now = time.time()
        room[user["id"]] = {"sid": sid, "joined": existing["joined"] if existing and not replaced else int(now * 1000),
                            "seen": now, "muted": existing["muted"] if existing else False, "deaf": existing["deaf"] if existing else False}
        others = [{"id": uid, "sid": p["sid"], "username": users.get(uid)["username"]} for uid, p in room.items() if uid != user["id"]]
    return {"room": cid, "peers": others, "ice": ice_servers(user), "people": people(cid), "replacedSid": replaced, "changed": changed,
            "maxPeople": economy.VOICE_MAX_PEOPLE}


def leave(user, cid, sid=None):
    _member(user, cid)
    with _lock:
        room = ROOMS.get(cid) or {}
        mine = room.get(user["id"])
        if not mine or (sid and mine["sid"] != sid):
            return False                                      # a stale tab saying goodbye must not remove the live one
        del room[user["id"]]
        if not room:
            ROOMS.pop(cid, None)
    return True


def state(user, cid, sid, muted=None, deaf=None):
    """A check-in, every ten seconds or so, and whenever the mute buttons change. Tells the client if it was dropped."""
    _member(user, cid)
    sid = _sid(sid)
    with _lock:
        mine = (ROOMS.get(cid) or {}).get(user["id"])
        if not mine or mine["sid"] != sid:
            return {"inRoom": False, "changed": False}
        mine["seen"] = time.time()
        changed = False
        for key, value in (("muted", muted), ("deaf", deaf)):
            if isinstance(value, bool) and mine[key] != value:
                mine[key] = value
                changed = True
    return {"inRoom": True, "changed": changed, "people": people(cid)}


def signal(user, cid, sid, to_uid, to_sid, data):
    """Passes one setup message to one person in the same room. Returns the event to deliver and who gets it."""
    _member(user, cid)
    sid = _sid(sid)
    if not isinstance(data, dict) or data.get("type") not in SIGNAL_TYPES:
        raise bad("Invalid message", code="invalid_request")
    if len(json.dumps(data, separators=(",", ":"))) > MAX_SIGNAL_BYTES:
        raise bad("That message is too large", 413, code="request_too_large")
    now = time.time()
    with _lock:
        recent = [t for t in _signals.get(user["id"], []) if now - t < 10]
        if len(recent) >= SIGNALS_PER_10S:
            raise bad("Too many messages. Slow down.", 429, code="rate_limited")
        recent.append(now)
        _signals[user["id"]] = recent
        room = ROOMS.get(cid) or {}
        mine, theirs = room.get(user["id"]), room.get(to_uid)
        if not mine or mine["sid"] != sid:
            raise bad("You are not in this room", 409, code="not_in_room")
        if not theirs or (to_sid and theirs["sid"] != to_sid):
            raise bad("That person is no longer in the room", 409, code="not_in_room")
        target = theirs["sid"]
    return {"type": "voice", "k": "signal", "room": cid, "from": user["id"], "fromSid": sid, "fromName": user["username"],
            "toSid": target, "data": data}, to_uid


def rooms_for(user):
    """Every room of every circle the person belongs to, with who is in it (for the little 'in voice' hints)."""
    out = []
    for c in circles.visible_to(user):
        if circles.is_member(c, user):
            out.append({"circleId": c["id"], "name": c["name"], "people": people(c["id"]), "full": len(ROOMS.get(c["id"]) or {}) >= economy.VOICE_MAX_PEOPLE})
    return out


def sweep(now=None):
    """Removes people who have gone quiet. Returns the circle ids whose rooms changed."""
    now = time.time() if now is None else now
    changed = set()
    with _lock:
        for cid, room in list(ROOMS.items()):
            for uid in [u for u, p in room.items() if now - p["seen"] > economy.VOICE_STALE_S]:
                del room[uid]
                changed.add(cid)
            if not room:
                ROOMS.pop(cid, None)
    return changed


def members_of(cid):
    c = circles.get(cid)
    return list(c["members"])


def clear():
    with _lock:
        ROOMS.clear()
        _signals.clear()
