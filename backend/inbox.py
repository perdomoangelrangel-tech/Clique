"""Notifications: a short list per person, kept until read, plus a live event when one arrives.

Used for promotions, finished challenges and milestones, rewards credited at the weekly close, loans that need attention
and money received from a friend. Each item is stored on the person (so one who was offline sees it next time) and the
server announces it to any open browser of theirs once the change has been saved (see server.announce_inbox).
"""
from .util import new_id, now_ms

KEEP = 60
PENDING = []              # live events waiting to be announced: {"type": "inbox", "userId": ..., "item": {...}}


def push(user, kind, title, text, **data):
    """Adds a notification and returns it."""
    item = {"id": new_id(), "t": now_ms(), "kind": kind, "title": str(title)[:80], "text": str(text)[:240], "seen": False}
    if data:
        item["data"] = data
    box = user.setdefault("inbox", [])
    box.insert(0, item)
    del box[KEEP:]
    PENDING.append({"type": "inbox", "userId": user["id"], "item": item})
    return item


def unseen(user):
    return [i for i in user.get("inbox", []) if not i.get("seen")]


def view(user, limit=30):
    return {"items": list(user.get("inbox", []))[:limit], "unseen": len(unseen(user))}


def mark_seen(user, ids=None):
    n = 0
    for i in user.get("inbox", []):
        if not i.get("seen") and (ids is None or i["id"] in ids):
            i["seen"] = True
            n += 1
    return n


def mark():
    """A bookmark in the list of live events, taken before a request runs (see rollback)."""
    return len(PENDING)


def rollback(bookmark):
    """Forgets the live events a failed request queued: the notifications they announce were undone with the request."""
    del PENDING[bookmark:]


def drain():
    """The live events to announce now (and forget)."""
    out, PENDING[:] = list(PENDING), []
    return out
