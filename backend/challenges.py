"""Weekly challenges: three for the weekly account and three for the accumulated account, picked once per week.

ASSIGNMENT. When a week is first seen (at the weekly rollover, or the first time anybody asks for it) the server picks its
challenges from the families in rules.py with a fixed, repeatable formula (a hash of the week, nothing random), writes them
into db["challenges"][week] and never changes them: the targets and the rewards are frozen for that week, whatever the settings
say later. Everybody gets the same six.

PROGRESS is not stored as a counter the browser could touch. The server records plain FACTS about what a person did that week
(which casino games, which polls, which days...) every time a qualifying action happens (backend/activity.py), and the progress
of a challenge is read from those facts. A page does not have to be open for any of it.

CLAIMING. A finished challenge is claimed with an explicit button, which pays the reward into the account the challenge names
(weekly or accumulated) as an EXTERNAL credit, so it never counts as winnings or leaderboard performance, and gives its XP. At
the weekly close, completed challenges nobody claimed are credited automatically, once, before the weekly account is reset
(see settle_week); challenges that were not completed simply expire. A claim is all-or-nothing and has a stable transaction id.
"""
import hashlib

from . import economy, inbox, ledger, milestones, progress, rules
from .store import db
from .txn import Txn
from .util import bad, now_ms, week_bounds, week_key

HISTORY_WEEKS = 52


def empty_facts():
    return {"games": [], "polls": [], "days": [], "cats": [], "symbols": [], "features": [], "created": 0, "gm": {}}


def week_state(user, week):
    g = progress.state(user)
    w = g["chal"].get(week)
    if w is None:
        w = g["chal"][week] = {"facts": empty_facts(), "done": {}, "claimed": {}}
        for old in sorted(g["chal"])[:-HISTORY_WEEKS]:
            del g["chal"][old]
    for k, v in empty_facts().items():
        w["facts"].setdefault(k, v)
    return w


def add_fact(user, week, fact, value):
    """Adds `value` to a set-fact (kept small) or counts it. Returns True if it was new."""
    w = week_state(user, week)
    if fact == "created":
        w["facts"]["created"] += 1
        return True
    box = w["facts"][fact]
    if value in box or len(box) >= rules.FACT_LIMITS[fact]:
        return False
    box.append(value)
    return True


def game_fact(user, week, game):
    """This week's numbers for one game: {rounds, wins, best_x100, won_c} (made empty on first use)."""
    return week_state(user, week)["facts"]["gm"].setdefault(game, {})


def _hash_order(seed, items):
    return sorted(items, key=lambda x: hashlib.sha256(f"{seed}:{x}".encode()).hexdigest())


def assign(week):
    """The week's challenges, made once. Calling it again returns the same ones."""
    box = db().setdefault("challenges", {})
    if week in box:
        return box[week]
    start, end = week_bounds(week)
    items, used_games = [], set()
    min_stake = f"${economy.QUALIFY_MIN_STAKE:,.2f}"
    for account, pool in rules.POOLS.items():
        for fid in _hash_order(f"{week}:{account}", pool)[:rules.PER_ACCOUNT_CLASSIC]:
            fam = rules.FAMILIES[fid]
            pick = int(hashlib.sha256(f"{week}:tier:{fid}".encode()).hexdigest(), 16) % len(fam["tiers"])
            target, money = fam["tiers"][pick]
            items.append({
                "id": f"{week}:{fid}", "family": fid, "account": account, "title": fam["title"], "desc": fam["desc"].format(t=target),
                "rule": rules.FACT_RULES[fam["fact"]].format(min=min_stake), "fact": fam["fact"], "kind": "count",
                "unit": fam["unit"], "target": target, "reward_c": rules.money_cents(money), "xp": rules.xp_amount(fam["xp"]),
                "href": fam["href"], "cta": fam["cta"], "start": start, "end": end})
        for fid in rules.GAME_POOLS[account]:                  # the game-specific ones: the game and the target are picked by the week's hash
            fam = rules.GAME_FAMILIES[fid]
            metric = fam["metric"]
            options = [g for g in rules.games_for(metric) if g not in used_games] or rules.games_for(metric)
            game = _hash_order(f"{week}:game:{fid}", options)[0]
            used_games.add(game)
            targets = rules.weekly_targets(game, metric)
            target, money = targets[int(hashlib.sha256(f"{week}:tier:{fid}:{game}".encode()).hexdigest(), 16) % len(targets)]
            name, unit = rules.GAME_INFO[game]
            cap = f"${economy.GAME_WIN_CREDIT_CAP:,.0f}"
            items.append({
                "id": f"{week}:{fid}", "family": fid, "account": account, "game": game, "gameName": name, "metric": metric, "kind": rules.METRIC_KIND[metric],
                "title": fam["title"].format(g=name), "desc": fam["desc"].format(t=target, g=name, unit=unit),
                "rule": fam["rule"].format(g=name, min=min_stake, cap=cap), "fact": "gm", "unit": unit if metric in ("rounds", "wins") else ("\u00d7" if metric == "best" else "won"),
                "target": target, "reward_c": rules.money_cents(money * rules.ACCOUNT_FACTOR[account]), "xp": rules.xp_amount(fam["xp"]),
                "href": f"#/games/{game}", "cta": f"Play {name}", "start": start, "end": end})
    box[week] = {"week": week, "assignedAt": now_ms(), "start": start, "end": end, "items": items, "settled": False}
    return box[week]


def _value(item, facts):
    if item.get("game"):                                       # a goal about one game, read from that game's numbers this week
        stat = (facts.get("gm") or {}).get(item["game"], {})
        m = item["metric"]
        return stat.get("best_x100", 0) / 100 if m == "best" else stat.get("won_c", 0) / 100 if m == "won" else stat.get(m, 0)
    v = facts.get(item["fact"], 0)
    return v if isinstance(v, int) else len(v)


def status_of(item, w, now):
    claimed = item["id"] in w["claimed"]
    value = _value(item, w["facts"])
    if claimed:
        return "claimed"
    if value >= item["target"]:
        return "completed"
    if now >= item["end"]:
        return "expired"
    return "in_progress" if value > 0 else "available"


def evaluate(user, week, now=None):
    """Writes down challenges that just reached their target and tells the person. Returns their ids."""
    now = now_ms() if now is None else now
    a = assign(week)
    w = week_state(user, week)
    new = []
    for item in a["items"]:
        if item["id"] not in w["done"] and _value(item, w["facts"]) >= item["target"]:
            w["done"][item["id"]] = now
            new.append(item)
    for item in new:
        milestones.bump(user, "challenges_done")
        dest = "weekly" if item["account"] == "weekly" else "accumulated"
        inbox.push(user, "challenge", "Challenge complete", f"{item['title']}: claim ${item['reward_c'] / 100:,.2f} into your {dest} account.", challenge=item["id"])
    if new:
        milestones.evaluate(user, now)
    return [i["id"] for i in new]


def item_row(item, w, now):
    value = _value(item, w["facts"])
    st = status_of(item, w, now)
    return {"id": item["id"], "family": item["family"], "account": item["account"], "title": item["title"], "desc": item["desc"], "rule": item["rule"],
            "unit": item["unit"], "kind": item.get("kind", "count"), "game": item.get("game"), "gameName": item.get("gameName"),
            "target": item["target"], "progress": round(min(value, item["target"]), 2), "value": round(value, 2), "reward": item["reward_c"] / 100,
            "xp": item["xp"], "status": st, "href": item["href"], "cta": item["cta"], "start": item["start"], "end": item["end"],
            "doneAt": w["done"].get(item["id"]), "claim": w["claimed"].get(item["id"])}


def view(user, now=None):
    """The Challenges page: this week's six (grouped by the account they pay), and the past weeks."""
    now = now_ms() if now is None else now
    cur = week_key(now)
    a = assign(cur)
    w = week_state(user, cur)
    evaluate(user, cur, now)
    rows = [item_row(i, w, now) for i in a["items"]]
    history = []
    for wk in sorted(db().get("challenges", {}), reverse=True):
        if wk >= cur:
            continue
        past = db()["challenges"][wk]
        pw = (progress.state(user)["chal"].get(wk) or {"facts": empty_facts(), "done": {}, "claimed": {}})
        items = [item_row(i, pw, now) for i in past["items"]]
        if any(r["status"] != "available" for r in items):
            history.append({"week": wk, "items": items, "settled": past["settled"]})
        if len(history) >= 8:
            break
    return {"week": cur, "start": a["start"], "end": a["end"], "now": now,
            "weekly": [r for r in rows if r["account"] == "weekly"], "accumulated": [r for r in rows if r["account"] == "accumulated"],
            "history": history,
            "rules": {"claimRule": "Claim a finished challenge before the week ends. Anything finished and unclaimed when the week closes is credited automatically, once.",
                      "weeklyNote": "Weekly-account rewards are chips for the week they were earned in. Like everything in the weekly account, what is left when the week closes is reset (it can pay off a loan first).",
                      "accumulatedNote": "Accumulated-account rewards are yours to keep, and never reset.",
                      "minStake": economy.QUALIFY_MIN_STAKE}}


def _pay(user, item, now, auto):
    """Credits one finished challenge. All-or-nothing, and the same challenge can never be paid twice."""
    acct = item["account"]
    cid = item["id"]
    w = week_state(user, item["id"].rsplit(":", 1)[0])
    if cid in w["claimed"]:
        raise bad("You already claimed that reward", 409, code="already_claimed")
    with Txn(users=[user]):
        row = ledger.post(user, acct, item["reward_c"] / 100, f"challenge.{acct}", ref=cid, external=True, txid=f"chal:{cid}:{user['id']}",
                          note=item["title"] + (" (credited at the weekly close)" if auto else ""))
        w["claimed"][cid] = {"t": now, "c": item["reward_c"], "account": acct, "auto": bool(auto)}
        xp = progress.grant(user, item["xp"], "challenge", f"chal:{cid}", now, label=item["title"])
    return {"id": cid, "account": acct, "amount": item["reward_c"] / 100, "xp": xp, "auto": bool(auto), "ledgerId": row["id"]}


def claim(user, cid, now=None):
    now = now_ms() if now is None else now
    if not isinstance(cid, str) or ":" not in cid:
        raise bad("That challenge does not exist", 404, code="challenge_not_found")
    week = cid.rsplit(":", 1)[0]
    a = db().get("challenges", {}).get(week)
    item = next((i for i in (a["items"] if a else []) if i["id"] == cid), None)
    if item is None:
        raise bad("That challenge does not exist", 404, code="challenge_not_found")
    w = week_state(user, week)
    if cid in w["claimed"]:
        raise bad("You already claimed that reward", 409, code="already_claimed")
    if now >= item["end"]:
        raise bad("That week is over. Challenges you had finished were credited automatically when it closed.", 409, code="week_over")
    if _value(item, w["facts"]) < item["target"]:
        raise bad("That challenge is not finished yet", code="goal_not_reached")
    if now < item["start"]:
        raise bad("That week has not started", code="week_not_started")
    return _pay(user, item, now, auto=False)


def settle_week(week, now=None):
    """The weekly close. Credits every finished-but-unclaimed challenge of `week` (weekly-account rewards go in BEFORE the weekly
    account is reset, so they can pay a loan first; accumulated rewards go to the accumulated account) and leaves the unfinished
    ones to expire. Safe to run again: a paid challenge is skipped, and a repeated credit has the same transaction id. Returns how
    many rewards were credited."""
    now = now_ms() if now is None else now
    a = db().get("challenges", {}).get(week)
    if not a or a.get("settled"):
        return 0
    paid, failed = 0, 0
    for u in list(db()["users"].values()):
        w = (progress.state(u)["chal"].get(week))
        if not w:
            continue
        for item in a["items"]:
            if item["id"] in w["claimed"] or _value(item, w["facts"]) < item["target"]:
                continue
            if item["id"] not in w["done"]:
                evaluate(u, week, now)
            try:
                res = _pay(u, item, now, auto=True)
            except Exception:                                  # one person's problem must not stop everybody else's reward
                import traceback
                traceback.print_exc()
                failed += 1
                continue
            paid += 1
            inbox.push(u, "challenge", "Reward credited at the weekly close",
                       f"{item['title']}: ${res['amount']:,.2f} went into your {'weekly' if item['account'] == 'weekly' else 'accumulated'} account.", challenge=cid_of(item))
    if not failed:
        a["settled"] = True
        a["settledAt"] = now
    return paid


def cid_of(item):
    return item["id"]


def settle_pending(current_week, now=None):
    """Weeks that ended but were not fully settled (a failed attempt): try again. Returns the number of rewards credited."""
    n = 0
    for wk, a in sorted(db().get("challenges", {}).items()):
        if wk < current_week and not a.get("settled"):
            n += settle_week(wk, now)
    return n


def backfill_week(user, d, week):
    """For the week that is already under way when this feature starts: facts the older records reliably show, so a person who has
    been playing since Monday is not told they have done nothing. From their round history (real-money rounds), the buys in the
    trade log of every poll, their share-trade log and the polls they proposed. Nothing is invented; anything the old records
    cannot show simply is not counted."""
    start, end = week_bounds(week)
    uid = user["id"]
    w = week_state(user, week)

    def day(t):
        from .util import day_key
        return day_key(t)
    min_stake = economy.QUALIFY_MIN_STAKE
    for h in user.get("history", []):
        if start <= h.get("t", 0) < end and h.get("game") in rules.CASINO_GAMES and h.get("bet", 0) + 1e-9 >= min_stake:
            add_fact(user, week, "games", h["game"])
            add_fact(user, week, "days", day(h["t"]))
            add_fact(user, week, "features", "casino")
    for m in d.get("markets", {}).values():
        for t in m.get("trades", []):
            if t.get("u") == uid and t.get("k") == "buy" and start <= t.get("t", 0) < end and t.get("amount", 0) + 1e-9 >= min_stake:
                add_fact(user, week, "polls", m["id"])
                add_fact(user, week, "cats", m.get("category") or "General")
                add_fact(user, week, "days", day(t["t"]))
                add_fact(user, week, "features", "polls")
        if m.get("creatorId") == uid and start <= m.get("createdAt", 0) < end:
            add_fact(user, week, "created", 1)
            add_fact(user, week, "days", day(m["createdAt"]))
            add_fact(user, week, "features", "create")
    for t in user.get("trades", []):
        if start <= t.get("t", 0) < end and t.get("total", 0) / 100 + 1e-9 >= min_stake:
            add_fact(user, week, "symbols", t["sym"])
            add_fact(user, week, "days", day(t["t"]))
            add_fact(user, week, "features", "exchange")
    cap_c = int(round(economy.GAME_WIN_CREDIT_CAP * 100))
    for h in user.get("history", []):                            # per-game numbers for the week: the same rules the live recorder uses
        if start <= h.get("t", 0) < end and h.get("game") in rules.GAME_INFO and h.get("bet", 0) + 1e-9 >= min_stake:
            box = game_fact(user, week, h["game"])
            profit_c = max(0, int(round((h.get("payout", 0) - h["bet"]) * 100)))
            box["rounds"] = box.get("rounds", 0) + 1
            if profit_c > 0:
                box["wins"] = box.get("wins", 0) + 1
                box["won_c"] = box.get("won_c", 0) + min(profit_c, cap_c)
                if h.get("mult"):
                    box["best_x100"] = max(box.get("best_x100", 0), int(round(h["mult"] * 100)))
    return w["facts"]
