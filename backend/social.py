"""Friends, and who is around right now.

Friends are people you added (they said yes) plus everybody you share a circle with: circle-mates
count as friends automatically, and stop counting if either of you leaves the circle.
Presence lives only in memory. A browser pings every 30 seconds while the site is open."""
from . import poker, users
from .store import db
from .util import bad, now_ms


def _person(uid):
    """Who, as the browser shows them: id, name and (if they have personalised it) how they look."""
    from . import users                           # imported here: users does not know about friends
    u = db()["users"][uid]
    return {"id": uid, "username": u["username"], **users.look_field(uid)}


MAX_FRIENDS = 200
MAX_PENDING = 50                    # requests you have sent that nobody has answered, and the same for ones sent to you
ONLINE_MS = 75_000                  # a browser pings every 30 s: two missed pings and the person is gone

GAMES = {"chicken": "Chicken", "blackjack": "Blackjack", "roulette": "Roulette", "limbo": "Limbo", "coinflip": "Coinflip",
         "war": "War", "dice": "Dice", "mines": "Mines", "moles": "Moles", "tower": "Tower"}
# What a friend can see you doing. Only these words ever leave the server: never a bet's title, a circle's name or a table.
LABELS = {"markets": "Browsing markets", "market": "Looking at a bet", "create": "Proposing a bet",
          "casino": "In the casino lobby", "poker": "In the poker room", "circles": "Browsing circles",
          "circle": "Inside a circle", "weekly": "Checking the weekly", "profile": "Looking at a profile",
          "friends": "Looking at friends", "chat": "Chatting", "other": "Around the site"}

_presence = {}                      # user id -> {"seen": ms, "where": (kind, game), "visible": bool}


def rec(uid):
    """The social record of one person: friends, requests, what they have read, whether they hide."""
    r = db().setdefault("social", {}).setdefault(uid, {})
    r.setdefault("friends", [])
    r.setdefault("incoming", [])
    r.setdefault("outgoing", [])
    r.setdefault("reads", {})
    r.setdefault("hide", False)
    r.setdefault("seen", 0)
    r.setdefault("receipts", True)           # read receipts: on means "let people see when I have read their messages", and see theirs
    r.setdefault("seenIn", {})               # chat id -> [last message I have read there, when]
    return r


# ---- who counts as a friend ---------------------------------------------------------

def circle_mates(uid):
    """Everyone who shares a circle with this person: id -> the names of the circles they share."""
    out = {}
    for c in db()["circles"].values():
        if uid in c["members"]:
            for m in c["members"]:
                if m != uid:
                    out.setdefault(m, []).append(c["name"])
    return out


def friend_ids(uid):
    ids = set(rec(uid)["friends"]) | set(circle_mates(uid))
    ids.discard(uid)
    known = db()["users"]
    return {i for i in ids if i in known}


def is_friend(a, b):
    return a != b and b in friend_ids(a)


# ---- adding and removing ------------------------------------------------------------

def _wait(key):
    """One person can only send so many requests in a while."""
    users._throttle(key, 20, 600)
    users._fail(key)


def request(user, username):
    """Ask somebody to be friends. If they already asked you, that is a yes. Returns 'requested' or 'friends'."""
    uid = user["id"]
    target = users.by_username(username)
    tid = target["id"]
    if tid == uid:
        raise bad("That's you. You already like yourself.", code="cannot_friend_self")
    me, them = rec(uid), rec(tid)
    if tid in me["friends"]:
        raise bad("You are already friends", code="already_friends")
    if tid in me["outgoing"]:
        raise bad("You already asked. Give them time to answer.", code="request_pending")
    if tid in me["incoming"]:
        return accept(user, tid)
    _wait("friendreq:" + uid)
    if len(me["friends"]) >= MAX_FRIENDS:
        raise bad(f"That is the most friends you can have ({MAX_FRIENDS})", code="friend_limit")
    if len(me["outgoing"]) >= MAX_PENDING:
        raise bad("You have too many requests waiting. Cancel a few first.", code="too_many_requests")
    if len(them["incoming"]) >= MAX_PENDING * 2:
        raise bad("They have a lot of requests waiting. Try again later.", code="too_many_requests")
    me["outgoing"].append(tid)
    them["incoming"].append(uid)
    return "requested"


def accept(user, other_id):
    uid = user["id"]
    me = rec(uid)
    if other_id not in me["incoming"]:
        raise bad("There is no request from them", 404, code="request_not_found")
    them = rec(other_id)
    if len(me["friends"]) >= MAX_FRIENDS or len(them["friends"]) >= MAX_FRIENDS:
        raise bad(f"Somebody has hit the {MAX_FRIENDS}-friend limit", code="friend_limit")
    me["incoming"].remove(other_id)
    if uid in them["outgoing"]:
        them["outgoing"].remove(uid)
    for a, b in ((me, other_id), (them, uid)):
        if b not in a["friends"]:
            a["friends"].append(b)
    return "friends"


def decline(user, other_id):
    me = rec(user["id"])
    if other_id not in me["incoming"]:
        raise bad("There is no request from them", 404, code="request_not_found")
    me["incoming"].remove(other_id)
    them = rec(other_id)
    if user["id"] in them["outgoing"]:
        them["outgoing"].remove(user["id"])        # they are not told it was a no, their request just goes quiet


def cancel(user, other_id):
    me = rec(user["id"])
    if other_id not in me["outgoing"]:
        raise bad("You have no request waiting for them", 404, code="request_not_found")
    me["outgoing"].remove(other_id)
    them = rec(other_id)
    if user["id"] in them["incoming"]:
        them["incoming"].remove(user["id"])


def remove(user, other_id):
    """Ends a friendship you made by adding each other. Circle-mates stay friends for as long as they share a circle."""
    me, them = rec(user["id"]), rec(other_id)
    if other_id not in me["friends"]:
        raise bad("You didn't add each other as friends" + (". Circle-mates are friends for as long as you share a circle." if other_id in circle_mates(user["id"]) else ""), code="not_friends")
    me["friends"].remove(other_id)
    if user["id"] in them["friends"]:
        them["friends"].remove(user["id"])


def set_hidden(user, hide):
    if not isinstance(hide, bool):
        raise bad("Hidden is on or off", code="invalid_setting")
    rec(user["id"])["hide"] = hide


def search(user, text):
    """Usernames that start with `text`, for the add-a-friend box. People already friends or asked are left out."""
    text = str(text or "").strip().lower()
    if len(text) < 2:
        return []
    uid = user["id"]
    me = rec(uid)
    skip = set(me["friends"]) | set(me["outgoing"]) | set(me["incoming"]) | {uid}
    out = []
    for lower, other in sorted(db()["usernames"].items()):
        if lower.startswith(text) and other not in skip:
            out.append(_person(other))
            if len(out) == 8:
                break
    return out


# ---- who is around ------------------------------------------------------------------

def _clean_where(where):
    kind = where.get("k") if isinstance(where, dict) else None
    game = where.get("v") if isinstance(where, dict) else None
    kind, game = (kind if isinstance(kind, str) else None), (game if isinstance(game, str) else None)    # only plain text counts
    if kind == "game":
        return ("game", game if game in GAMES else None)
    return (kind if kind in LABELS else "other", None)


def ping(user, where, visible, now=None):
    """The browser says it is open and which page it is on. True if what friends would see just changed."""
    now = now or now_ms()
    uid = user["id"]
    clean, visible = _clean_where(where), bool(visible)
    old = _presence.get(uid)
    was_online = bool(old and now - old["seen"] < ONLINE_MS)
    _presence[uid] = {"seen": now, "where": clean, "visible": visible}
    rec(uid)["seen"] = now
    if rec(uid)["hide"]:
        return False
    return (not was_online) or old["where"] != clean or old["visible"] != visible


def _label(uid, where):
    if poker.table_of(uid):
        return "Playing poker"                                  # never which table: it may be a private one
    kind, game = where
    if kind == "game":
        return f"Playing {GAMES[game]}" if game else "In the casino lobby"
    return LABELS[kind]


def status(uid, now=None):
    """What anybody who is allowed to see this person sees. People who hide look offline, with no last-seen time."""
    now = now or now_ms()
    r = rec(uid)
    if r["hide"]:
        return {"online": False, "away": False, "where": None, "seen": None}
    p = _presence.get(uid)
    seen = (p["seen"] if p else r["seen"]) or None
    if not (p and now - p["seen"] < ONLINE_MS):
        return {"online": False, "away": False, "where": None, "seen": seen}
    return {"online": True, "away": not p["visible"], "where": _label(uid, p["where"]) if p["visible"] else None, "seen": seen}


def sweep(now=None):
    """Forgets people whose browser went quiet. Returns who just went offline, so their friends can be told."""
    now = now or now_ms()
    gone = []
    for uid, p in list(_presence.items()):
        if now - p["seen"] >= ONLINE_MS:
            gone.append(uid)
            rec(uid)["seen"] = p["seen"]
            del _presence[uid]
    return gone


# ---- what the friends page shows ---------------------------------------------------

def view(user, now=None):
    now = now or now_ms()
    uid = user["id"]
    me = rec(uid)
    mates = circle_mates(uid)
    known = db()["users"]
    rows = []
    for fid in friend_ids(uid):
        s = status(fid, now)
        rows.append({**_person(fid), "added": fid in me["friends"], "circles": mates.get(fid, []), **s})
    rows.sort(key=lambda r: (not r["online"], r["away"], r["username"].lower()))
    pend = lambda ids: [_person(i) for i in ids if i in known]       # noqa: E731
    return {"friends": rows, "incoming": pend(me["incoming"]), "outgoing": pend(me["outgoing"]), "hide": me["hide"],
            "online": sum(1 for r in rows if r["online"])}
