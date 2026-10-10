"""XP and ranks: the long-term progression, kept apart from the weekly leaderboard.

The weekly leaderboard measures how one week of play went. Rank measures how much a person has taken part over the whole
time, and it never goes down or resets (no demotion, no seasons, for now). It is made of XP, and XP only comes from:
  * qualifying actions (backend/activity.py), each worth a little and capped per day;
  * a "steady week" bonus at the weekly close, for taking part on several different days;
  * claiming a completed weekly challenge or milestone.
Balances, wagers, losses, loans, transfers and Store purchases never give XP. Each award has an id and is recorded once, so a
retry, a double click or two requests at the same moment cannot pay twice.

Everything about a person's progression lives in user["goals"]:
  xp, hist (promotions), xplog (recent awards), seen (award ids), day (today's counters), m (milestone counters),
  games / features (distinct things used), done / claimed (milestones), chal (per-week challenge facts and claims).
"""
from . import economy, inbox, rules
from .store import db
from .util import now_ms, day_key

SEEN_KEEP = 800


def state(user):
    g = user.get("goals")
    if g is None:
        g = user["goals"] = {}
    g.setdefault("xp", 0)
    g.setdefault("hist", [])                  # promotions: {t, from, to, xp}
    g.setdefault("xplog", [])                 # the newest XP awards: {t, xp, src, label}
    g.setdefault("seen", {})                  # award / event id -> the day it was recorded (so repeats are ignored)
    g.setdefault("day", {"k": None, "n": {}, "xn": {}, "mk": [], "xp": 0})
    g.setdefault("m", {})                     # milestone counters
    g.setdefault("games", [])                 # distinct casino games ever played with real money
    g.setdefault("gm", {})                    # per game: {rounds, wins, best_x100, won_c}, the lifetime numbers the game milestones read
    g.setdefault("features", [])              # distinct parts of Clique ever used
    g.setdefault("lastDay", None)
    g.setdefault("lastWeek", None)
    g.setdefault("done", {})                  # milestone tier id -> when it was reached
    g.setdefault("claimed", {})               # milestone tier id -> {t, c}
    g.setdefault("chal", {})                  # week -> {facts, done, claimed}
    return g


def xp_of(user):
    return int((user.get("goals") or {}).get("xp", 0))


def rank_of(user):
    return rules.rank_for(xp_of(user))


def compact_rank(user):
    """The small version shown next to a name in lists: tier, division and label."""
    r = rank_of(user)
    return {"t": r["tier"], "d": r["division"] or 0, "l": r["label"]}


def remember(g, key, when=None):
    """Writes down that `key` was handled. False if it already was (so the caller must do nothing)."""
    if key in g["seen"]:
        return False
    g["seen"][key] = day_key(when)
    if len(g["seen"]) > SEEN_KEEP:
        cutoff = sorted(set(g["seen"].values()))[-30:][0]
        for k in [k for k, v in g["seen"].items() if v < cutoff]:
            del g["seen"][k]
    return True


def grant(user, amount, source, eid, now=None, label=""):
    """Adds XP once for the award `eid`. Returns the XP actually added (0 for a repeat or a zero award)."""
    amount = int(amount)
    if amount <= 0:
        return 0
    now = now_ms() if now is None else now
    g = state(user)
    if not remember(g, "xp:" + eid, now):
        return 0
    before = rules.rank_for(g["xp"])
    g["xp"] += amount
    g["xplog"].insert(0, {"t": now, "xp": amount, "src": source, "label": label})
    del g["xplog"][60:]
    after = rules.rank_for(g["xp"])
    if after["index"] > before["index"]:
        g["hist"].insert(0, {"t": now, "from": before["label"], "to": after["label"], "xp": g["xp"], "tier": after["tier"]})
        del g["hist"][40:]
        inbox.push(user, "promotion", f"Promoted to {after['label']}", f"You reached {after['label']} with {g['xp']:,} XP.", rank=after["label"])
        from . import milestones                  # the rank milestones watch the tier
        milestones.evaluate(user, now)
    return amount


def close_week(week):
    """The weekly close: the steady-week bonus for everybody who took part on enough different days. Safe to run twice."""
    n = 0
    for u in db()["users"].values():
        facts = ((u.get("goals") or {}).get("chal", {}).get(week) or {}).get("facts") or {}
        if len(facts.get("days", [])) >= rules.STEADY_WEEK_DAYS:
            if grant(u, rules.xp_amount(rules.STEADY_WEEK_XP), "steady", f"steady:{week}", label=f"A steady week ({len(facts['days'])} days)"):
                n += 1
    return n


def overview(user, now=None):
    """Everything the Rank page shows."""
    now = now_ms() if now is None else now
    g = state(user)
    r = rules.rank_for(g["xp"])
    d = g["day"]
    today = d["k"] == day_key(now)
    used = d["xp"] if today else 0
    xn = d["xn"] if today else {}
    return {
        "rank": r, "xp": g["xp"], "history": g["hist"][:20], "recent": g["xplog"][:15],
        "ladder": [{**lv, "reached": g["xp"] >= lv["xp"], "current": lv["index"] == r["index"]} for lv in rules.levels()],
        "today": {"xp": used, "cap": rules.XP_DAILY_CAP, "remaining": max(0, rules.XP_DAILY_CAP - used)},
        "sources": [{"kind": k, "xp": rules.xp_amount(v["xp"]), "cap": v["cap"], "usedToday": xn.get(k, 0), "text": v["text"]}
                    for k, v in rules.XP_RULES.items()],
        "bonuses": [{"text": f"A steady week: taking part on {rules.STEADY_WEEK_DAYS} different days", "xp": rules.xp_amount(rules.STEADY_WEEK_XP)},
                    {"text": "Completing a weekly challenge (claimed)", "xp": "15 to 25"},
                    {"text": "Reaching a milestone (claimed)", "xp": "10 to 120"}],
        "notCounted": ["Looking at pages or pressing buttons", "Practice (demo) rounds", "Rejected or cancelled actions", "Borrowing or repaying a loan",
                       "Sending or receiving money", "Store purchases", f"How much you stake: only stakes of ${economy.QUALIFY_MIN_STAKE:,.2f} or more count, and bigger ones are worth the same"],
    }
