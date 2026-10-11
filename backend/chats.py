"""Chats: one for the whole site, one for each circle you are in, and private ones (two friends, or a group of friends).

Ids: 'global', 'circle_<circle id>', 'dm_<id>_<id>' and 'group_<id>'. Who can read a chat is never stored for the
global and circle chats: the site and the circle's member list decide, so leaving a circle closes its chat at once."""
import re
import time

from . import social, users
from .store import db
from .util import bad, clean_text, new_id, now_ms

GLOBAL = "global"
MAX_TEXT = 500
PAGE = 60                                   # messages sent when a chat is opened
KEEP = {"global": 400, "circle": 300, "dm": 300, "group": 300}       # the newest messages of each kind that are kept
MAX_GROUP = 20
SPEED = (12, 10)                            # at most this many messages in this many seconds, per person

_sent = {}                                  # user id -> times of their recent messages
_HIDDEN_CONTROLS = re.compile("[‪-‮⁦-⁩]")       # text-direction tricks that can make a message read backwards


def _chats():
    return db().setdefault("chats", {})


def _kind(chat_id):
    if chat_id == GLOBAL:
        return "global"
    for prefix in ("circle", "dm", "group"):
        if chat_id.startswith(prefix + "_"):
            return prefix
    return None


def _ensure(chat_id):
    chat = _chats().get(chat_id)
    if chat is None:
        chat = _chats()[chat_id] = {"id": chat_id, "kind": _kind(chat_id), "name": "", "members": [], "owner": None,
                                    "created": now_ms(), "seq": 0, "msgs": [], "last": 0}
    return chat


def chat_for(user, chat_id):
    """The chat, if this person may be in it. Anything else looks like it does not exist."""
    kind = _kind(chat_id)
    uid = user["id"]
    if kind == "global":
        return _ensure(chat_id)
    if kind == "circle":
        c = db()["circles"].get(chat_id[len("circle_"):])
        if not c or uid not in c["members"]:
            raise bad("Chat not found", 404, code="chat_not_found")
        return _ensure(chat_id)
    chat = _chats().get(chat_id)
    if kind is None or not chat or uid not in chat["members"]:
        raise bad("Chat not found", 404, code="chat_not_found")
    return chat


def recipients(chat):
    """Who should be told about something new in this chat. None means everybody on the site."""
    if chat["kind"] == "global":
        return None
    if chat["kind"] == "circle":
        c = db()["circles"].get(chat["id"][len("circle_"):])
        return list(c["members"]) if c else []
    return list(chat["members"])


def _person(uid):
    """Who, as the browser shows them: id, name and (if they have personalised it) how they look."""
    return {"id": uid, "username": _name(uid), **users.look_field(uid)}


def _name(uid):
    u = db()["users"].get(uid)
    return u["username"] if u else "someone"


def _other(chat, uid):
    return next(m for m in chat["members"] if m != uid)


def title(chat, viewer_id):
    kind = chat["kind"]
    if kind == "global":
        return "Everyone"
    if kind == "circle":
        return db()["circles"][chat["id"][len("circle_"):]]["name"]
    if kind == "dm":
        return _name(_other(chat, viewer_id))
    if chat["name"]:
        return chat["name"]
    others = [_name(m) for m in chat["members"] if m != viewer_id]
    return ", ".join(others[:3]) + (f" +{len(others) - 3}" if len(others) > 3 else "")


def fmt(msg):
    out = {"n": msg["n"], "u": msg["u"], "name": _name(msg["u"]) if msg["u"] else None, "t": msg["t"], "x": msg["x"]}
    if msg.get("sys"):
        out["sys"] = True
    return out


# ---- reading ------------------------------------------------------------------------

def _pointer(uid, chat):
    """The last message this person has read here. Joining a big chat late does not start you with a pile of unread."""
    reads = social.rec(uid)["reads"]
    if chat["id"] not in reads:
        reads[chat["id"]] = chat["seq"] if chat["kind"] in ("global", "circle") else 0
    return reads[chat["id"]]


def unread(uid, chat):
    ptr = _pointer(uid, chat)
    return sum(1 for m in chat["msgs"] if m["n"] > ptr and m["u"] != uid and not m.get("sys"))      # notices like "ann left" are not news


def summary(user, chat):
    uid = user["id"]
    last = chat["msgs"][-1] if chat["msgs"] else None
    out = {"id": chat["id"], "kind": chat["kind"], "name": title(chat, uid), "unread": unread(uid, chat),
           "t": chat["last"] or chat["created"],
           "last": {"name": _name(last["u"]) if last["u"] else None, "x": last["x"][:90], "t": last["t"]} if last else None}
    if chat["kind"] == "circle":
        c = db()["circles"][chat["id"][len("circle_"):]]
        out.update({"emoji": c["emoji"], "members": len(c["members"]), "circleId": c["id"]})
    elif chat["kind"] in ("dm", "group"):
        out["members"] = len(chat["members"])
        if chat["kind"] == "dm":
            out["with"] = _other(chat, uid)
    return out


def list_for(user):
    uid = user["id"]
    chats = [_ensure(GLOBAL)]
    chats += [_ensure("circle_" + c["id"]) for c in db()["circles"].values() if uid in c["members"]]
    chats += [c for c in _chats().values() if c["kind"] in ("dm", "group") and uid in c["members"] and c["msgs"]]      # a DM shows up with its first message
    rows = [summary(user, c) for c in chats]
    rows.sort(key=lambda r: (-r["t"], r["name"].lower()))
    return rows


def unread_totals(user):
    """What the little badge in the header counts: everything unread except the busy site-wide chat."""
    rows = list_for(user)
    return {"total": sum(r["unread"] for r in rows if r["kind"] != "global"),
            "global": next((r["unread"] for r in rows if r["kind"] == "global"), 0)}


def detail(user, chat):
    out = summary(user, chat)
    uid = user["id"]
    if chat["kind"] in ("dm", "group"):
        out["people"] = [_person(m) for m in chat["members"]]
    if chat["kind"] == "group":
        out["owner"] = chat["owner"]
        out["canManage"] = chat["owner"] == uid
    if chat["kind"] == "dm":
        out["canSend"] = social.is_friend(uid, _other(chat, uid))
    else:
        out["canSend"] = True
    out["readers"] = readers(user, chat)
    out["receipts"] = receipts_on(uid)
    return out


def history(user, chat_id, before=None, after=None):
    chat = chat_for(user, chat_id)
    msgs = chat["msgs"]
    if after is not None:
        picked = [m for m in msgs if m["n"] > after][:200]
    elif before is not None:
        picked = [m for m in msgs if m["n"] < before][-PAGE:]
    else:
        picked = msgs[-PAGE:]
    return {"chat": detail(user, chat), "messages": [fmt(m) for m in picked],
            "more": bool(picked and msgs and msgs[0]["n"] < picked[0]["n"])}


def _see(uid, chat, n):
    """Remembers how far this person has read in this chat, and when they got there (for read receipts).
    Returns [n, when] if that moved forward, otherwise None. It never moves back."""
    seen = social.rec(uid)["seenIn"]
    n = min(n, chat["seq"])
    if n > seen.get(chat["id"], [0, 0])[0]:
        seen[chat["id"]] = [n, now_ms()]
        return seen[chat["id"]]
    return None


def mark_read(user, chat_id, upto):
    """The person has read up to message `upto`. Returns (chat, [n, when] or None if nothing new was read)."""
    chat = chat_for(user, chat_id)
    if isinstance(upto, bool) or not isinstance(upto, int):
        raise bad("Which message?", code="invalid_request")
    reads = social.rec(user["id"])["reads"]
    reads[chat["id"]] = max(_pointer(user["id"], chat), min(upto, chat["seq"]))
    return chat, _see(user["id"], chat, upto)


# ---- read receipts -------------------------------------------------------------------

def set_receipts(user, on):
    if not isinstance(on, bool):
        raise bad("Read receipts are on or off", code="invalid_setting")
    social.rec(user["id"])["receipts"] = on


def receipts_on(uid):
    return social.rec(uid)["receipts"]


def readers(user, chat):
    """Who has read how far in this chat, for the little "Seen" marks. Like WhatsApp, it goes both ways: if you have
    receipts off you see nobody's, and nobody sees yours. The site-wide chat has none."""
    if chat["kind"] == "global" or not receipts_on(user["id"]):
        return []
    out = []
    for pid in recipients(chat) or []:
        if pid == user["id"] or not receipts_on(pid):
            continue
        n, t = social.rec(pid)["seenIn"].get(chat["id"], [0, 0])
        if n:
            out.append({**_person(pid), "n": n, "t": t})
    out.sort(key=lambda r: (-r["n"], r["username"].lower()))
    return out


def seen_audience(chat, reader_id):
    """Who should be told, live, that `reader_id` just read something: the others in the chat who have receipts on.
    Nobody, if the reader keeps theirs off."""
    if chat["kind"] == "global" or not receipts_on(reader_id):
        return []
    return [i for i in (recipients(chat) or []) if i != reader_id and receipts_on(i)]


# ---- writing ------------------------------------------------------------------------

def clean_message(text):
    if not isinstance(text, str):
        raise bad("Write something first", code="text_required")
    text = _HIDDEN_CONTROLS.sub("", text)
    text = "".join(ch for ch in text if ch == "\n" or (ch >= " " and ch != "\x7f"))
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise bad("Write something first", code="text_required")
    if len(text) > MAX_TEXT:
        raise bad(f"Messages can be {MAX_TEXT} characters at most", code="text_too_long")
    return text


def _slow_down(uid):
    now = time.time()
    recent = [t for t in _sent.get(uid, []) if now - t < SPEED[1]]
    if len(recent) >= SPEED[0]:
        _sent[uid] = recent
        raise bad("Easy. You are sending messages too fast.", 429, code="rate_limited")
    recent.append(now)
    _sent[uid] = recent


def _append(chat, uid, text, system=False):
    chat["seq"] += 1
    msg = {"n": chat["seq"], "u": None if system else uid, "t": now_ms(), "x": text}
    if system:
        msg["sys"] = True
    chat["msgs"].append(msg)
    del chat["msgs"][:-KEEP[chat["kind"]]]
    chat["last"] = msg["t"]
    return msg


def send(user, chat_id, text):
    chat = chat_for(user, chat_id)
    uid = user["id"]
    text = clean_message(text)
    if chat["kind"] == "dm" and not social.is_friend(uid, _other(chat, uid)):
        raise bad("You can only message friends. Add them first.", 403, code="not_friends")
    _slow_down(uid)
    msg = _append(chat, uid, text)
    social.rec(uid)["reads"][chat["id"]] = chat["seq"]
    _see(uid, chat, chat["seq"])                   # writing in a chat means you have read what came before
    return chat, msg


def delete_message(user, chat_id, n):
    """You can take back your own message. The owner of a circle can also clear things out of its chat."""
    chat = chat_for(user, chat_id)
    if isinstance(n, bool) or not isinstance(n, int):
        raise bad("Which message?", code="invalid_request")
    msg = next((m for m in chat["msgs"] if m["n"] == n and not m.get("sys")), None)
    if msg is None:
        raise bad("That message is gone", 404, code="message_not_found")
    owner = chat["kind"] == "circle" and db()["circles"][chat["id"][len("circle_"):]]["ownerId"] == user["id"]
    if msg["u"] != user["id"] and not owner:
        raise bad("You can only delete your own messages", 403, code="not_your_message")
    chat["msgs"].remove(msg)


# ---- private chats ------------------------------------------------------------------

def open_dm(user, other_id):
    uid = user["id"]
    if other_id not in db()["users"] or not social.is_friend(uid, other_id):
        raise bad("You can only message friends. Add them first.", 403, code="not_friends")
    chat_id = "dm_" + "_".join(sorted([uid, other_id]))
    chat = _ensure(chat_id)
    if not chat["members"]:
        chat["members"] = [uid, other_id]
    return chat


def _friends_only(uid, ids):
    out = []
    for i in ids:
        if not isinstance(i, str) or i not in db()["users"]:
            raise bad("Somebody on that list doesn't exist", code="user_not_found")
        if i != uid and i not in out:
            if not social.is_friend(uid, i):
                raise bad(f"{_name(i)} is not your friend yet", code="not_friends")
            out.append(i)
    return out


def create_group(user, name, member_ids):
    uid = user["id"]
    if not isinstance(member_ids, list):
        raise bad("Pick who is in the group", code="invalid_group")
    others = _friends_only(uid, member_ids)
    if len(others) < 2:
        raise bad("A group needs at least two friends. For one friend, just message them.", code="invalid_group")
    if len(others) + 1 > MAX_GROUP:
        raise bad(f"A group can have {MAX_GROUP} people at most", code="group_full")
    name = clean_text(name, "Group name", 1, 40) if name else ""
    chat = _ensure("group_" + new_id())
    chat.update({"name": name, "members": [uid] + others, "owner": uid})
    _append(chat, uid, f"{_name(uid)} started the group", system=True)
    return chat


def _group_owned(user, chat_id):
    chat = chat_for(user, chat_id)
    if chat["kind"] != "group":
        raise bad("That only works in a group chat", code="not_a_group")
    if chat["owner"] != user["id"]:
        raise bad("Only the person who made the group can do that", 403, code="not_group_owner")
    return chat


def add_members(user, chat_id, ids):
    chat = _group_owned(user, chat_id)
    new = [i for i in _friends_only(user["id"], ids) if i not in chat["members"]]
    if not new:
        raise bad("Pick friends who are not in the group yet", code="invalid_group")
    if len(chat["members"]) + len(new) > MAX_GROUP:
        raise bad(f"A group can have {MAX_GROUP} people at most", code="group_full")
    chat["members"] += new
    _append(chat, user["id"], f"{_name(user['id'])} added {', '.join(_name(i) for i in new)}", system=True)
    return chat


def remove_member(user, chat_id, target_id):
    chat = _group_owned(user, chat_id)
    if target_id == user["id"]:
        raise bad("To go yourself, leave the group", code="invalid_group")
    if target_id not in chat["members"]:
        raise bad("They are not in this group", code="invalid_group")
    chat["members"].remove(target_id)
    _append(chat, user["id"], f"{_name(user['id'])} removed {_name(target_id)}", system=True)
    return chat


def rename(user, chat_id, name):
    chat = _group_owned(user, chat_id)
    chat["name"] = clean_text(name, "Group name", 1, 40)
    _append(chat, user["id"], f"{_name(user['id'])} named the group {chat['name']}", system=True)
    return chat


def leave(user, chat_id):
    """Leaves a group. Returns the chat, or None if it closed because fewer than two people were left."""
    chat = chat_for(user, chat_id)
    if chat["kind"] != "group":
        raise bad("You can only leave a group. For a circle chat, leave the circle." if chat["kind"] == "circle" else "You can only leave a group.", code="cannot_leave_chat")
    uid = user["id"]
    chat["members"].remove(uid)
    if len(chat["members"]) < 2:
        _chats().pop(chat["id"], None)
        return None
    if chat["owner"] == uid:
        chat["owner"] = chat["members"][0]
    _append(chat, uid, f"{_name(uid)} left", system=True)
    return chat
