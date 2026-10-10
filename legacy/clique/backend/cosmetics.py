"""The Store, the inventory, and profile personalization: one system.

What a person looks like is a handful of slots (picture, frame, badge, title, banner, accent, font) plus a background and
a short bio, kept in user["profile"]. Each slot holds a catalog id. Free items can always be picked. Anything with a price
must be owned (bought in the Store, paid for from the ACCUMULATED account) before it can go in a slot, and the server checks
that every time: the browser cannot equip what it has not paid for. Cosmetics are only ever shown. They never change a
probability, a payout, a price or an outcome anywhere in Clique.

Uploaded pictures live on the data volume under DATA_DIR/uploads/avatars and are served back by the server (see server.py).
"""
import hashlib
import os
import re

from . import catalog, config, economy, images, ledger
from .store import db
from .util import bad, clean_text, new_id, now_ms

UPLOAD_DIR = os.path.join(config.DATA_DIR, "uploads", "avatars")
FILE_RE = re.compile(r"^[a-f0-9]{12}-[a-f0-9]{8}\.(png|jpg|webp)$")
SLOTS = tuple(catalog.DEFAULTS)                                    # avatar frame badge title banner accent font


# ---- what is owned ------------------------------------------------------------------------------------------------

def inventory(user):
    return user.setdefault("inv", {})


def owns(user, item_id):
    it = catalog.get(item_id)
    if not it:
        return False
    return it["price"] == 0 or item_id in inventory(user)


def rewards_earned(user):
    """How many weekly rewards this person has been paid, across every circle and week."""
    n = 0
    for c in db()["circles"].values():
        for recap in c["recaps"].values():
            rw = (recap.get("rewards") or {}).get(user["id"])
            if rw and rw.get("paid") and rw["amount"] > 0:
                n += 1
    return n


def requirement_text(req):
    if not req:
        return None
    if req["type"] == "rewards":
        return f"Be paid a weekly reward {req['n']} time{'s' if req['n'] != 1 else ''}"
    if req["type"] == "age_days":
        return f"Have an account that is at least {req['n']} days old"
    return "Meet the requirement"


def requirement_met(user, req):
    if not req:
        return True
    if req["type"] == "rewards":
        return rewards_earned(user) >= req["n"]
    if req["type"] == "age_days":
        return (now_ms() - user["createdAt"]) >= req["n"] * 86400000
    return False


def requirement_progress(user, req):
    if not req:
        return None
    if req["type"] == "rewards":
        return {"have": rewards_earned(user), "need": req["n"]}
    if req["type"] == "age_days":
        return {"have": int((now_ms() - user["createdAt"]) // 86400000), "need": req["n"]}
    return None


# ---- the profile: what is equipped --------------------------------------------------------------------------------

def profile(user, create=False):
    """The person's appearance settings. Just looking does not create anything: somebody who has never changed a thing stays
    on the plain defaults (and is sent to browsers with no look at all). Changing something (create=True) makes it theirs."""
    p = user.setdefault("profile", {}) if create else dict(user.get("profile") or {})
    for slot, default in catalog.DEFAULTS.items():
        p.setdefault(slot, default)
    p.setdefault("bg", catalog.DEFAULT_BG)
    p.setdefault("bio", "")
    return p


def equipped(user, slot):
    """The catalog entry in a slot. Falls back to the free default when the stored id is gone or no longer owned."""
    pid = profile(user).get(slot)
    it = catalog.get(pid)
    if it and it["kind"] == slot and owns(user, pid):
        return it
    return catalog.get(catalog.DEFAULTS[slot])


def uploaded_file(user):
    f = (user.get("profile") or {}).get("upload")
    return f if f and FILE_RE.match(f) else None


def _avatar_choice(user):
    p = profile(user)
    if p["avatar"] == "upload" and uploaded_file(user):
        return "upload"
    return equipped(user, "avatar")["id"]


# ---- how a person is shown --------------------------------------------------------------------------------------

def public_style(user):
    """The small description of how a person looks, sent along with their name wherever lists show them. Empty for
    somebody who has changed nothing."""
    p = user.get("profile")
    if not p:
        return {}
    out = {}
    choice = _avatar_choice(user)
    if choice == "upload":
        out["u"] = uploaded_file(user)
    else:
        art = catalog.get(choice)["art"]
        if art.get("icon"):
            out["a"] = {"icon": art["icon"], "bg": art.get("bg")}
    frame = equipped(user, "frame")["art"]
    if frame.get("style") not in (None, "none"):
        out["f"] = frame
    badge = equipped(user, "badge")["art"]
    if badge.get("glyph"):
        out["b"] = badge["glyph"]
    title = equipped(user, "title")["art"]
    if title.get("text"):
        out["t"] = title["text"]
    accent = equipped(user, "accent")
    if accent["id"] != catalog.DEFAULTS["accent"]:
        out["c"] = accent["art"]["color"]
    return out


def profile_json(user):
    """Everything the profile page and the editor need."""
    p = profile(user)
    slots = {slot: equipped(user, slot)["id"] for slot in SLOTS}
    slots["avatar"] = _avatar_choice(user)
    return {"slots": slots, "bg": p["bg"], "bio": p["bio"], "upload": uploaded_file(user) and f"/uploads/avatars/{uploaded_file(user)}",
            "style": public_style(user), "fonts": catalog.FONTS, "backgrounds": catalog.BACKGROUNDS,
            "art": {slot: equipped(user, slot)["art"] for slot in SLOTS}}


# ---- the contrast rule --------------------------------------------------------------------------------------------

def _lum(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4          # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


MIN_CONTRAST = 3.0


def readable(accent_hex, bg_id):
    return contrast(accent_hex, catalog.BACKGROUNDS[bg_id]["color"]) >= MIN_CONTRAST


# ---- customizing --------------------------------------------------------------------------------------------------

def _check_slot(user, slot, item_id):
    it = catalog.get(item_id) if isinstance(item_id, str) else None
    if not it or it["kind"] != slot:
        raise bad("That is not an option for " + catalog.KINDS[slot].lower())
    if not owns(user, item_id):
        raise bad(f"You do not own {it['name']} yet. Get it in the Store first.", 403)
    return it


def customize(user, body):
    """Applies any of: avatar frame badge title banner accent font bg bio. All of it or none of it."""
    if not isinstance(body, dict):
        raise bad("Invalid request")
    p = profile(user)
    new = dict(p)
    if body.get("reset") is True:
        new.update(catalog.DEFAULTS)
        new["bg"] = catalog.DEFAULT_BG
        new["bio"] = ""
    for slot in SLOTS:
        if slot not in body:
            continue
        if slot == "avatar" and body["avatar"] == "upload":
            if not uploaded_file(user):
                raise bad("Upload a picture first")
            new["avatar"] = "upload"
            continue
        new[slot] = _check_slot(user, slot, body[slot])["id"]
    if "bg" in body:
        if body["bg"] not in catalog.BACKGROUNDS:
            raise bad("Unknown background")
        new["bg"] = body["bg"]
    if "bio" in body:
        new["bio"] = clean_text(body["bio"], "Bio", 0, 140) if body["bio"] else ""
    accent = catalog.get(new["accent"])
    if not readable(accent["art"]["color"], new["bg"]):
        raise bad(f"{accent['name']} is hard to read on the {catalog.BACKGROUNDS[new['bg']]['name']} background. "
                  "Pick a different colour or background.")
    profile(user, create=True).update(new)
    return profile_json(user)


# ---- uploaded pictures --------------------------------------------------------------------------------------------

def _delete_file(name):
    if name and FILE_RE.match(name):
        try:
            os.remove(os.path.join(UPLOAD_DIR, name))
        except OSError:
            pass


def set_upload(user, data, claimed_type=None):
    kind, width, height = images.inspect(data, claimed_type)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{user['id']}-{hashlib.sha256(bytes(data)).hexdigest()[:8]}.{images.EXT[kind]}"
    path = os.path.join(UPLOAD_DIR, name)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(bytes(data))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    p = profile(user, create=True)
    old = p.get("upload")
    p["upload"], p["avatar"] = name, "upload"
    if old and old != name:
        _delete_file(old)
    return {"file": name, "kind": kind, "width": width, "height": height, "profile": profile_json(user)}


def remove_upload(user):
    p = profile(user, create=True)
    old = p.get("upload")
    if not old:
        raise bad("You have not uploaded a picture")
    _delete_file(old)
    p["upload"] = None
    if p["avatar"] == "upload":
        p["avatar"] = catalog.DEFAULTS["avatar"]
    return profile_json(user)


def read_upload(name):
    """(bytes, content type) for a stored picture, or None. The name must be exactly one this server made."""
    if not FILE_RE.match(name or ""):
        return None
    path = os.path.join(UPLOAD_DIR, name)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    ext = name.rsplit(".", 1)[1]
    return data, {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[ext]


# ---- the store ----------------------------------------------------------------------------------------------------

def _why_not(user, it):
    """Why this person cannot buy this right now, or None if they can."""
    if it["price"] == 0:
        return "free"
    if it["id"] in inventory(user):
        return "owned"
    if not it.get("available", True):
        return "unavailable"
    if it.get("until") and it["until"] < now_ms():
        return "unavailable"
    if not requirement_met(user, it.get("requires")):
        return "locked"
    return None


def store_view(user):
    accum = ledger.balance(user, "accumulated")
    rows = []
    for it in catalog.CATALOG.values():
        if it["price"] > 0 and not it.get("available", True) and it["id"] not in inventory(user):
            continue                                                  # off sale and not yours: not shown
        row = catalog.public(it, owned=owns(user, it["id"]))
        row["equipped"] = (_avatar_choice(user) if it["kind"] == "avatar" else equipped(user, it["kind"])["id"]) == it["id"]
        row["state"] = _why_not(user, it)
        row["affordable"] = accum >= it["price"]
        row["requirementText"] = requirement_text(it.get("requires"))
        row["progress"] = requirement_progress(user, it.get("requires"))
        row["bought"] = (inventory(user).get(it["id"]) or {}).get("t")
        rows.append(row)
    return {"items": rows, "kinds": catalog.KINDS, "accumulated": accum, "weekly": ledger.balance(user, "weekly"),
            "slots": profile_json(user)["slots"], "fonts": catalog.FONTS, "style": public_style(user)}


def _remember_key(user, request_id):
    if request_id is None:
        return None
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", request_id):
        raise bad("Invalid request id")
    return f"store:{user['id']}:{request_id}"


def buy(user, item_id, request_id=None):
    """Buys one product from the ACCUMULATED account. Checked on the server every time: the product exists and is on sale,
    the requirement is met, it is not already owned, the balance covers the price. The charge and the ownership are written
    in the same step, and the charge has a transaction id of its own, so a double click or a retry can never charge twice."""
    key = _remember_key(user, request_id)
    seen = db().setdefault("idem", {}).get(key) if key else None
    if seen:
        if seen["fp"] != item_id:
            raise bad("That request id was already used for a different purchase", 409)
        return {**seen["result"], "duplicate": True}
    it = catalog.get(item_id) if isinstance(item_id, str) else None
    if not it:
        raise bad("There is no such product", 404)
    why = _why_not(user, it)
    if why == "free":
        raise bad("That one is free: just equip it")
    if why == "owned":
        raise bad("You already own this", 409)
    if why == "unavailable":
        raise bad("That product is not on sale right now", 409)
    if why == "locked":
        raise bad("Not yet: " + requirement_text(it["requires"]), 403)
    price_c = ledger.to_cents(it["price"])
    have_c = ledger.balance_c(user, "accumulated")
    if have_c < price_c:
        raise bad(f"You need ${(price_c - have_c) / 100:,.2f} more in your accumulated account", 402)
    before = have_c / 100
    ledger.post(user, "accumulated", -price_c / 100, "store.buy", ref=item_id, txid=f"buy:{item_id}")
    inventory(user)[item_id] = {"t": now_ms(), "paid": price_c}
    result = {"item": item_id, "name": it["name"], "paid": price_c / 100, "before": before, "after": ledger.balance(user, "accumulated")}
    if key:
        memory = db().setdefault("idem", {})
        memory[key] = {"t": now_ms(), "fp": item_id, "result": result}
        if len(memory) > 1000:                                       # a retry comes seconds later, not days
            for old in sorted(memory, key=lambda k: memory[k]["t"])[:-500]:
                del memory[old]
    return {**result, "duplicate": False}


def equip(user, item_id):
    it = catalog.get(item_id) if isinstance(item_id, str) else None
    if not it:
        raise bad("There is no such product", 404)
    _check_slot(user, it["kind"], item_id)
    profile(user, create=True)[it["kind"]] = item_id
    return profile_json(user)


def unequip(user, kind):
    if kind not in SLOTS:
        raise bad("Unknown slot")
    profile(user, create=True)[kind] = catalog.DEFAULTS[kind]
    return profile_json(user)
