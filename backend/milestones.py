"""Milestones: long-term goals that never reset. Each tier pays money into the ACCUMULATED account (and some XP), once.

Progress comes only from the server's own records of qualifying actions (backend/activity.py), never from a number the browser
sends. A tier is "reached" the moment progress gets to its target and is written down; the person then claims it (an explicit
button) and the money and XP are credited exactly once: the reward has a stable transaction id (`mile:<tier>:<person>`), and
the tier is marked claimed in the same all-or-nothing step, so a double click, a retry or two requests at once pay one time.
Rewards do not expire.

What counts from before this feature existed: only what the old records reliably show (see backfill()). Nothing is invented.
"""
from . import economy, inbox, ledger, progress, rules
from .store import db
from .txn import Txn
from .util import bad, now_ms

LABELS = {
    "market_bets": "Poll bets", "casino_rounds": "Casino rounds", "games_tried": "Different casino games", "weeks_active": "Weeks taken part in",
    "challenges_done": "Weekly challenges completed", "features_used": "Different parts of Clique used", "stock_trades": "Share trades",
    "polls_created": "Polls proposed", "circles_joined": "Circles joined or created", "rank_tier": "Rank reached", "days_active": "Days taken part in",
}


def metric(user, name):
    g = progress.state(user)
    if ":" in name:                                            # a goal about one game: "rounds:chicken", "best:tower", "won:chicken"...
        kind, game = name.split(":", 1)
        stat = g["gm"].get(game, {})
        return stat.get("best_x100", 0) / 100 if kind == "best" else stat.get("won_c", 0) / 100 if kind == "won" else int(stat.get(kind, 0))
    if name == "games_tried":
        return len(g["games"])
    if name == "features_used":
        return len(g["features"])
    if name == "rank_tier":
        return rules.rank_for(g["xp"])["tierIndex"]
    return int(g["m"].get(name, 0))


def bump(user, name, n=1):
    g = progress.state(user)
    g["m"][name] = int(g["m"].get(name, 0)) + n


def evaluate(user, now=None, notify=True):
    """Marks every tier whose target has been reached. Returns the tier ids that were newly reached."""
    now = now_ms() if now is None else now
    g = progress.state(user)
    new = []
    for t in rules.milestone_tiers():
        if t["id"] in g["done"]:
            continue
        if metric(user, t["metric"]) >= t["target"]:
            g["done"][t["id"]] = now
            new.append(t["id"])
    for tid in new if notify else []:
        t = next(x for x in rules.milestone_tiers() if x["id"] == tid)
        m = next(x for x in rules.MILESTONES if x["id"] == t["milestone"])
        inbox.push(user, "milestone", "Milestone reached", f"{m['title']}: {_target_text(m, t['target'])}. Claim ${t['money_c'] / 100:,.2f} on the Rank page.", tier=tid)
    return new


def _target_text(m, target):
    if m["metric"] == "rank_tier":
        return f"reach {rules.RANK_TIER_NAMES.get(target, 'a new rank')}"
    kind = m.get("kind", "count")
    if kind == "mult":
        return f"reach {target:g}\u00d7"
    if kind == "money":
        return f"win ${target:,.0f}"
    unit = m["unit"] if target != 1 else m["unit"].rstrip("s")          # "1 bet", "10 bets"
    return f"{target:,} {unit}"


def claim(user, tid, now=None):
    """Pays one reached tier. Raises if it is unknown, not reached yet or already claimed."""
    now = now_ms() if now is None else now
    tiers = {t["id"]: t for t in rules.milestone_tiers()}
    t = tiers.get(tid) if isinstance(tid, str) else None
    if t is None:
        raise bad("That milestone does not exist", 404, code="milestone_not_found")
    g = progress.state(user)
    if tid in g["claimed"]:
        raise bad("You already claimed that reward", 409, code="already_claimed")
    if tid not in g["done"]:
        raise bad("That milestone is not reached yet", code="goal_not_reached")
    with Txn(users=[user]):
        row = None
        if t["money_c"] > 0:
            row = ledger.post(user, "accumulated", t["money_c"] / 100, "milestone", ref=tid, external=True, txid=f"mile:{tid}:{user['id']}",
                              note="Milestone reward")
        g["claimed"][tid] = {"t": now, "c": t["money_c"]}
        got = progress.grant(user, t["xp"], "milestone", f"mile:{tid}", now, label=_title(t))
    return {"id": tid, "account": "accumulated", "amount": t["money_c"] / 100, "xp": got, "ledgerId": row["id"] if row else None}


def _title(t):
    m = next(x for x in rules.MILESTONES if x["id"] == t["milestone"])
    return f"{m['title']} ({_target_text(m, t['target'])})"


def view(user):
    """Every milestone with its tiers: progress, reached, claimed and what is next."""
    g = progress.state(user)
    out = []
    for m in rules.MILESTONES:
        value = metric(user, m["metric"])
        tiers, nxt = [], None
        for n, (target, money, xp) in enumerate(m["tiers"], start=1):
            tid = f"{m['id']}:{n}"
            claimed = tid in g["claimed"]
            reached = tid in g["done"]
            status = "claimed" if claimed else "reached" if reached else "upcoming"
            tier = {"id": tid, "tier": n, "target": target, "money": rules.money_cents(money) / 100, "xp": rules.xp_amount(xp), "status": status,
                    "reachedAt": g["done"].get(tid), "claimedAt": (g["claimed"].get(tid) or {}).get("t"),
                    "label": _target_text(m, target)}
            tiers.append(tier)
            if nxt is None and not reached:
                nxt = tier
        out.append({"id": m["id"], "title": m["title"], "desc": m["desc"], "metric": m["metric"], "unit": m["unit"], "href": m["href"],
                    "group": m.get("group", "general"), "game": m.get("game"), "kind": m.get("kind", "count"),
                    "value": round(value, 2) if isinstance(value, float) else value, "tiers": tiers, "next": nxt, "complete": nxt is None,
                    "claimable": sum(1 for t in tiers if t["status"] == "reached")})
    return {"milestones": out, "account": "accumulated",
            "totals": {"claimable": sum(m["claimable"] for m in out),
                       "claimableMoney": round(sum(t["money"] for m in out for t in m["tiers"] if t["status"] == "reached"), 2),
                       "claimed": sum(1 for m in out for t in m["tiers"] if t["status"] == "claimed"),
                       "tiers": sum(len(m["tiers"]) for m in out)}}


def backfill(user, d):
    """Counts what the older records reliably show, for a person who had been playing before milestones existed.

    From the weekly stats: poll bets (marketBets), rounds (gamesPlayed, which also counts real-money poker sessions), and the
    weeks with any of either. From their round history (the newest 100): which casino games they have tried. From their share
    trades log, the polls they proposed, and the circles they belong to. NOT invented: days taken part in, challenges (none
    existed), XP (rank starts from the first XP earned from now on). Run once, by the migration."""
    g = progress.state(user)
    bets = rounds = weeks = 0
    for wk, s in (user.get("stats") or {}).items():
        mb, gp = int(s.get("marketBets", 0)), int(s.get("gamesPlayed", 0))
        bets += mb
        rounds += gp
        if mb + gp > 0:
            weeks += 1
    games = sorted({h.get("game") for h in user.get("history", []) if h.get("game") in rules.CASINO_GAMES})
    g["m"]["market_bets"] = max(g["m"].get("market_bets", 0), bets)
    g["m"]["casino_rounds"] = max(g["m"].get("casino_rounds", 0), rounds)
    g["m"]["weeks_active"] = max(g["m"].get("weeks_active", 0), weeks)
    g["m"]["stock_trades"] = max(g["m"].get("stock_trades", 0), len(user.get("trades", [])))
    g["m"]["polls_created"] = max(g["m"].get("polls_created", 0), sum(1 for m in d.get("markets", {}).values() if m.get("creatorId") == user["id"]))
    joined = sum(1 for c in d.get("circles", {}).values() if user["id"] in c["members"])
    g["m"]["circles_joined"] = max(g["m"].get("circles_joined", 0), joined)
    for gm in games:
        if gm not in g["games"]:
            g["games"].append(gm)
    feats = []
    if bets:
        feats.append("polls")
    if rounds:
        feats.append("casino")
    if user.get("trades"):
        feats.append("exchange")
    if any(h.get("game") == "poker" for h in user.get("history", [])):
        feats.append("poker")
    if g["m"]["polls_created"]:
        feats.append("create")
    if joined:
        feats.append("circles")
    for f in feats:
        if f not in g["features"]:
            g["features"].append(f)
    new = evaluate(user, now_ms(), notify=False)
    if new:
        inbox.push(user, "milestone", "Milestones unlocked from your history",
                   f"{len(new)} milestone reward{'s' if len(new) != 1 else ''} are ready to claim on the Rank page.")
    return len(new)


def backfill_games(user):
    """Per-game numbers from the round history the older records still hold (the newest 100 rounds): how many, how many were profits, the best
    multiplier, and the capped winnings. Same rules as the live recorder. Poker is not backfilled (a poker session is not a hand). Takes the larger
    of what is there and what the history shows, so running it twice changes nothing. Returns the tiers newly unlocked (nobody is told one by one)."""
    g = progress.state(user)
    cap_c = int(round(economy.GAME_WIN_CREDIT_CAP * 100))
    seen = {}
    for h in user.get("history", []):
        game = h.get("game")
        if game not in rules.GAME_INFO or h.get("bet", 0) + 1e-9 < economy.QUALIFY_MIN_STAKE:
            continue
        box = seen.setdefault(game, {"rounds": 0, "wins": 0, "won_c": 0, "best_x100": 0})
        profit_c = max(0, int(round((h.get("payout", 0) - h["bet"]) * 100)))
        box["rounds"] += 1
        if profit_c > 0:
            box["wins"] += 1
            box["won_c"] += min(profit_c, cap_c)
            if h.get("mult"):
                box["best_x100"] = max(box["best_x100"], int(round(h["mult"] * 100)))
    for game, box in seen.items():
        mine = g["gm"].setdefault(game, {})
        for k, v in box.items():
            mine[k] = max(mine.get(k, 0), v)
    new = evaluate(user, now_ms(), notify=False)
    if new:
        inbox.push(user, "milestone", "More milestones unlocked from your history",
                   f"{len(new)} game milestone reward{'s' if len(new) != 1 else ''} are ready to claim on the Rank page.")
    return len(new)
