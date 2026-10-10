"""The Store's catalog and the free profile options: the one place that says what exists, what it costs and what it needs.

Add a product by adding a line to ITEMS; change a price by changing `price`; take something off sale with
`"available": False`. Nothing else in the code (server or browser) lists products. The browser draws each kind of item
from the small `art` description it carries (colours, a glyph name, a pattern), so a new frame, badge, banner or accent
needs no front-end change at all.

Cosmetics never change a probability, a payout or an outcome. They change how a person looks to everybody else.

Optional overrides without editing this file: set STORE_OVERRIDES to JSON such as
    {"frame_gold": {"price": 900}, "badge_flame": {"available": false}}
and every product keeps its definition except for the fields you list.
"""
import json
import os

# slot = what an equipped item replaces. One item per slot at a time.
KINDS = {
    "avatar": "Profile picture",
    "frame": "Frame around your picture",
    "badge": "Badge beside your name",
    "title": "Title under your name",
    "banner": "Profile banner",
    "accent": "Accent colour",
    "font": "Name font",
}

LIME, VERM, CREAM, FELT, BONE, INK = "#C6F432", "#FF4B2B", "#EFE6D2", "#2F6B47", "#CFC3A8", "#2A2420"


def item(id, kind, name, desc, price, art, **extra):
    return {"id": id, "kind": kind, "name": name, "desc": desc, "price": float(price), "art": art,
            "requires": extra.pop("requires", None), "available": extra.pop("available", True),
            "free": float(price) == 0, **extra}


ITEMS = [
    # ---- always free: the starting options everybody has --------------------------------------------------------
    item("avatar_initial", "avatar", "Your initial", "A tile with the first letter of your name.", 0, {"initial": True}),
    item("frame_none", "frame", "No frame", "Just the picture.", 0, {"style": "none"}),
    item("frame_plain", "frame", "Ink outline", "A plain thick outline, like the rest of Clique.", 0, {"style": "solid", "color": "#0E0C0A", "width": 2}),
    item("badge_none", "badge", "No badge", "Nothing beside your name.", 0, {"none": True}),
    item("title_none", "title", "No title", "Nothing under your name.", 0, {"none": True}),
    item("banner_plain", "banner", "Plain", "A flat colour behind your profile.", 0, {"pattern": "plain", "a": "#2A2420", "b": "#2A2420"}),
    item("banner_lime", "banner", "Lime block", "Acid lime, flat.", 0, {"pattern": "plain", "a": LIME, "b": LIME}),
    item("banner_verm", "banner", "Vermillion block", "Hot vermillion, flat.", 0, {"pattern": "plain", "a": VERM, "b": VERM}),
    item("accent_lime", "accent", "Acid lime", "The house colour for wins.", 0, {"color": LIME}),
    item("accent_verm", "accent", "Vermillion", "The house colour for losses.", 0, {"color": VERM}),
    item("accent_cream", "accent", "Paper", "Warm off-white.", 0, {"color": CREAM}),
    item("font_display", "font", "Bricolage", "Clique's headline face.", 0, {"family": "display"}),
    item("font_body", "font", "Instrument", "Clique's calm text face.", 0, {"family": "body"}),
    item("font_mono", "font", "Mono", "Clique's number face.", 0, {"family": "mono"}),

    # ---- profile pictures ---------------------------------------------------------------------------------------
    item("avatar_chicken", "avatar", "Chicken", "Crosses the road. Does not cash out.", 120, {"icon": "chicken", "bg": LIME}),
    item("avatar_rocket", "avatar", "Rocket", "Ignores your target.", 120, {"icon": "limbo", "bg": CREAM}),
    item("avatar_mole", "avatar", "Mole", "Whacked, but cheerful.", 150, {"icon": "moles", "bg": LIME}),
    item("avatar_bomb", "avatar", "Bomb", "Lit. Always lit.", 180, {"icon": "mines", "bg": VERM}),
    item("avatar_dice", "avatar", "Lucky dice", "Lucky is a strong word.", 200, {"icon": "dice", "bg": "#1E3B2C"}),
    item("avatar_swords", "avatar", "Crossed swords", "For people who start the argument.", 250, {"icon": "war", "bg": CREAM}),
    item("avatar_crown", "avatar", "Crown", "Heads. Always heads.", 400, {"icon": "coinflip", "bg": INK}),

    # ---- frames: a ring around your picture wherever it appears ---------------------------------------------------
    item("frame_lime", "frame", "Lime ring", "A bright ring that says you won something once.", 150, {"style": "solid", "color": LIME, "width": 3}),
    item("frame_hot", "frame", "Hot seat", "Vermillion with a hard shadow.", 200, {"style": "solid", "color": VERM, "width": 3, "shadow": True}),
    item("frame_double", "frame", "Double ring", "Two rings. One is for luck.", 250, {"style": "double", "color": CREAM, "width": 3}),
    item("frame_dashed", "frame", "Tear line", "Cut here. Like a betting slip.", 300, {"style": "dashed", "color": LIME, "width": 3}),
    item("frame_gold", "frame", "Gold leaf", "Only for people who have been paid for finishing well, three times.", 750,
         {"style": "double", "color": "#F2C230", "width": 3, "shadow": True}, requires={"type": "rewards", "n": 3}),

    # ---- badges: a tiny sticker beside your name ------------------------------------------------------------------
    item("badge_flame", "badge", "Flame", "On a streak. Allegedly.", 180, {"glyph": "flame"}),
    item("badge_bolt", "badge", "Bolt", "Fast hands.", 180, {"glyph": "bolt"}),
    item("badge_ghost", "badge", "Ghost", "Here, but not here.", 250, {"glyph": "ghost"}),
    item("badge_crown", "badge", "Crown", "Holding the most when a week closes. Or just wearing it.", 600, {"glyph": "crown"}),

    # ---- titles: a line of text under your name -------------------------------------------------------------------
    item("title_nightowl", "title", "Night owl", "Bets after midnight.", 150, {"text": "Night owl"}),
    item("title_degenerate", "title", "Certified degenerate", "It says so right here.", 200, {"text": "Certified degenerate"}),
    item("title_oracle", "title", "The Oracle", "Saw it coming.", 300, {"text": "The Oracle"}),
    item("title_whale", "title", "Whale", "Moves the market. Mostly the wrong way.", 500, {"text": "Whale"}),
    item("title_veteran", "title", "Veteran", "Around for at least two weeks.", 100, {"text": "Veteran"}, requires={"type": "age_days", "n": 14}),

    # ---- banners for your profile page ----------------------------------------------------------------------------
    item("banner_stripes", "banner", "Slip stripes", "Diagonal stripes, like the edge of a betting slip.", 200, {"pattern": "stripes", "a": "#1E3B2C", "b": "#2F6B47"}),
    item("banner_dots", "banner", "Halftone", "Printed dots on lime.", 200, {"pattern": "dots", "a": LIME, "b": "#0E0C0A"}),
    item("banner_checks", "banner", "Checkered", "A finish line, in vermillion.", 300, {"pattern": "checks", "a": VERM, "b": "#0E0C0A"}),
    item("banner_waves", "banner", "Felt waves", "Soft waves on card-room green.", 350, {"pattern": "waves", "a": "#1E3B2C", "b": LIME}),

    # ---- accent colours ------------------------------------------------------------------------------------------
    item("accent_sky", "accent", "Sky", "A cool blue for a warm room.", 150, {"color": "#6EC6FF"}),
    item("accent_gold", "accent", "Gold", "Showing off.", 250, {"color": "#F2C230"}),
    item("accent_rose", "accent", "Rose", "Loud, but tasteful.", 150, {"color": "#FF8FB3"}),

    # ---- name fonts (profile page) -------------------------------------------------------------------------------
    item("font_serif", "font", "Fraunces", "A soft, old-fashioned serif for your name.", 250, {"family": "serif"}),
    item("font_marker", "font", "Marker", "Chunky and hand-made.", 300, {"family": "marker"}),
]


def _overrides():
    raw = os.environ.get("STORE_OVERRIDES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        raise SystemExit("STORE_OVERRIDES must be valid JSON")
    if not isinstance(data, dict):
        raise SystemExit("STORE_OVERRIDES must be a JSON object of {product id: {fields to change}}")
    return data


def build():
    """The catalog with any STORE_OVERRIDES applied (a new id with kind, name, desc, price and art adds a product)."""
    items = {i["id"]: dict(i) for i in ITEMS}
    for pid, change in _overrides().items():
        if not isinstance(change, dict):
            raise SystemExit(f"STORE_OVERRIDES[{pid}] must be an object")
        if pid in items:
            items[pid].update({k: v for k, v in change.items() if k in ("price", "available", "requires", "name", "desc", "art", "until")})
            items[pid]["free"] = float(items[pid]["price"]) == 0
        elif {"kind", "name", "desc", "price", "art"} <= set(change):
            items[pid] = item(pid, change["kind"], change["name"], change["desc"], change["price"], change["art"],
                              requires=change.get("requires"), available=change.get("available", True))
        else:
            raise SystemExit(f"STORE_OVERRIDES[{pid}] is not a known product and lacks kind, name, desc, price, art")
    for i in items.values():
        if i["kind"] not in KINDS:
            raise SystemExit(f"Product {i['id']} has an unknown kind {i['kind']!r}")
        if i["price"] < 0:
            raise SystemExit(f"Product {i['id']} has a negative price")
    return items


CATALOG = build()

DEFAULTS = {"avatar": "avatar_initial", "frame": "frame_none", "badge": "badge_none", "title": "title_none",
            "banner": "banner_plain", "accent": "accent_lime", "font": "font_display"}

# Backgrounds a profile page can use (flat colours, all readable with every accent that passes the contrast check).
BACKGROUNDS = {
    "ink": {"name": "Ink", "color": "#14110F"}, "felt": {"name": "Felt", "color": "#1E3B2C"},
    "wine": {"name": "Wine", "color": "#3A1A16"}, "slate": {"name": "Slate", "color": "#22262B"},
    "paper": {"name": "Paper", "color": "#EFE6D2"},
}
DEFAULT_BG = "ink"

# Fonts the profile page may use: only these names, never a URL. `stack` is the CSS fallback chain.
FONTS = {
    "display": "'Bricolage Grotesque', 'Helvetica Neue', Arial, sans-serif",
    "body": "'Instrument Sans', 'Helvetica Neue', Arial, sans-serif",
    "mono": "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace",
    "serif": "'Fraunces', Georgia, 'Times New Roman', serif",
    "marker": "'Rubik Mono One', 'Arial Black', Impact, sans-serif",
}


def get(item_id):
    return CATALOG.get(item_id)


def public(item_row, owned=False):
    """What the browser is told about a product."""
    return {k: item_row[k] for k in ("id", "kind", "name", "desc", "price", "art", "requires", "free")} | {"owned": owned}
