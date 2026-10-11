"""Circles: groups of friends. Public ones can be found and joined by anyone,
private ones can only be joined with the invite code."""
import secrets

from .store import db
from .util import bad, clean_text, new_id, now_ms
from . import activity, users

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _code():
    taken = {c["inviteCode"] for c in db()["circles"].values()}
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if code not in taken:
            return code


def get(cid):
    c = db()["circles"].get(cid)
    if not c:
        raise bad("Circle not found", 404, code="circle_not_found")
    return c


def is_member(c, user):
    return bool(user) and user["id"] in c["members"]


def can_view(c, user):
    return c["visibility"] == "public" or is_member(c, user)


def view_or_404(cid, user):
    c = get(cid)
    if not can_view(c, user):
        raise bad("Circle not found", 404, code="circle_not_found")       # don't reveal that private circles exist
    return c


def member_or_403(c, user):
    if not is_member(c, user):
        raise bad("Join this circle first", 403, code="not_circle_member")


def owner_or_403(c, user):
    if c["ownerId"] != user["id"]:
        raise bad("Only the circle owner can do that", 403, code="not_circle_owner")


def create(user, body):
    name = clean_text(body.get("name"), "Circle name", 2, 40)
    desc = clean_text(body.get("description") or "", "Description", 0, 200) if body.get("description") else ""
    vis = body.get("visibility", "private")
    if vis not in ("public", "private"):
        raise bad("Visibility must be public or private", code="invalid_setting")
    emoji = str(body.get("emoji") or "👥").strip()[:8] or "👥"
    cid = new_id()
    c = {
        "id": cid, "name": name, "description": desc, "visibility": vis, "emoji": emoji,
        "ownerId": user["id"], "inviteCode": _code(), "createdAt": now_ms(),
        "members": {user["id"]: now_ms()}, "punishments": {}, "recaps": {},
    }
    db()["circles"][cid] = c
    activity.safe_record(user, "circle", f"create:{cid}")
    return c


def join(user, cid, code=None):
    c = get(cid)
    if is_member(c, user):
        return c
    if c["visibility"] == "private":
        if not code or str(code).strip().upper() != c["inviteCode"]:
            raise bad("This circle is private. You need its invite code.", 403, code="invite_code_required")
    c["members"][user["id"]] = now_ms()
    activity.safe_record(user, "circle", f"join:{cid}:{user['id']}")
    return c


def join_by_code(user, code):
    code = str(code or "").strip().upper()
    for c in db()["circles"].values():
        if c["inviteCode"] == code:
            if user["id"] not in c["members"]:
                c["members"][user["id"]] = now_ms()
                activity.safe_record(user, "circle", f"join:{c['id']}:{user['id']}")
            return c
    raise bad("No circle has that invite code", 404, code="circle_not_found")


def leave(user, cid):
    c = get(cid)
    if not is_member(c, user):
        raise bad("You are not in this circle", code="not_circle_member")
    if c["ownerId"] == user["id"]:
        raise bad("The owner can't leave their own circle", code="owner_cannot_leave")
    del c["members"][user["id"]]
    return c


def kick(owner, cid, target_id):
    c = get(cid)
    owner_or_403(c, owner)
    if target_id == owner["id"]:
        raise bad("You can't remove yourself", code="cannot_remove_self")
    if target_id not in c["members"]:
        raise bad("That person isn't in the circle", code="not_circle_member")
    del c["members"][target_id]
    return c


def update(owner, cid, body):
    c = get(cid)
    owner_or_403(c, owner)
    if "name" in body:
        c["name"] = clean_text(body["name"], "Circle name", 2, 40)
    if "description" in body:
        c["description"] = clean_text(body["description"] or "", "Description", 0, 200) if body["description"] else ""
    if "visibility" in body:
        if body["visibility"] not in ("public", "private"):
            raise bad("Visibility must be public or private", code="invalid_setting")
        c["visibility"] = body["visibility"]
    if "emoji" in body:
        c["emoji"] = str(body["emoji"] or "👥").strip()[:8] or "👥"
    return c


def regen_code(owner, cid):
    c = get(cid)
    owner_or_403(c, owner)
    c["inviteCode"] = _code()
    return c


def summary(c, viewer):
    member = is_member(c, viewer)
    out = {
        "id": c["id"], "name": c["name"], "description": c["description"],
        "visibility": c["visibility"], "emoji": c["emoji"], "ownerId": c["ownerId"],
        "memberCount": len(c["members"]), "isMember": member,
        "isOwner": bool(viewer) and c["ownerId"] == viewer["id"], "createdAt": c["createdAt"],
        "ownerName": users.get(c["ownerId"])["username"],
    }
    if member:
        out["inviteCode"] = c["inviteCode"]
    return out


def visible_to(viewer):
    return [c for c in db()["circles"].values() if can_view(c, viewer)]
