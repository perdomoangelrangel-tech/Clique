"""Remembering that a request was already handled, so a double click, a retry or a reconnect cannot do it twice.

A request carries an id the browser made up (`requestId`). The first time the server sees it the result is stored here; the
same id with the same content returns that stored result, marked as a duplicate, and changes nothing. The same id with
DIFFERENT content is refused. Entries live in the saved data (db["idem"]), so a restart does not forget them.
"""
import json

from .store import db
from .util import bad, now_ms

KEEP = 1000


def clean_id(value):
    if value is None:
        return None
    if not isinstance(value, str) or not 8 <= len(value) <= 64:
        raise bad("Invalid request id")
    return value


def key_for(kind, user, request_id):
    return f"{kind}:{user['id']}:{request_id}" if request_id else None


def fingerprint(**content):
    return json.dumps(content, sort_keys=True, default=str)


def seen(key, fp):
    """The stored result for this request, or None if it is new. Refuses an id that was used for something different."""
    if not key:
        return None
    hit = db().setdefault("idem", {}).get(key)
    if not hit:
        return None
    if hit["fp"] != fp:
        raise bad("That request id was already used for something different", 409)
    return {**hit["result"], "duplicate": True}


def remember(key, fp, result):
    if not key:
        return
    box = db().setdefault("idem", {})
    box[key] = {"t": now_ms(), "fp": fp, "result": result}
    if len(box) > KEEP:
        for old in sorted(box, key=lambda k: box[k]["t"])[:len(box) - KEEP // 2]:
            del box[old]
