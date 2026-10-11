"""The weekly loop: every circle gets a punishment poll, the member with the least currency
at the end of the week gets the winning punishment, and everyone can earn awards."""
import datetime

from . import challenges, circles, config, economy, games, inbox, ledger, loans, markets, progress, users
from .store import db
from .util import (TZ_NAME, bad, clean_text, new_id, next_week_key, now_ms, prev_week_key, round2, valid_week_key,
                   week_bounds, week_key, week_moment_ms)

MAX_PUNISHMENTS_PER_USER = 2

AWARD_DEFS = [
    {"key": "topDog", "name": "Top Dog", "emoji": "👑", "desc": "Holding the most when the week closes"},
    {"key": "hotSeat", "name": "Hot Seat", "emoji": "🔥", "desc": "Worst week in the circle (biggest drop, or smallest gain). Punishment time"},
    {"key": "rocketMan", "name": "Rocket Man", "emoji": "🚀", "desc": "Biggest gain of the week"},
    {"key": "freefall", "name": "Freefall", "emoji": "📉", "desc": "Biggest drop of the week"},
    {"key": "oracle", "name": "The Oracle", "emoji": "🔮", "desc": "Most profit from winning predictions"},
    {"key": "sharpshooter", "name": "Sharpshooter", "emoji": "🎯", "desc": "Best win rate (at least 3 settled bets)"},
    {"key": "whale", "name": "Whale", "emoji": "🐋", "desc": "Placed the biggest single bet"},
    {"key": "highRoller", "name": "High Roller", "emoji": "🎰", "desc": "Wagered the most in the games"},
    {"key": "luckyCharm", "name": "Lucky Charm", "emoji": "🍀", "desc": "Hit the highest game multiplier (x5 or more)"},
    {"key": "cardShark", "name": "Card Shark", "emoji": "🃏", "desc": "Won the most blackjack hands"},
    {"key": "chickenChamp", "name": "Road Warrior", "emoji": "🐔", "desc": "Got the chicken across for the biggest multiplier"},
    {"key": "spinDoctor", "name": "Spin Doctor", "emoji": "🎡", "desc": "Biggest roulette profit"},
    {"key": "houseFavorite", "name": "House Favorite", "emoji": "🏠", "desc": "Donated the most to the casino games"},
    {"key": "badBeat", "name": "Bad Beat", "emoji": "💔", "desc": "Lost the most on a bet that looked like a lock (70¢+)"},
    {"key": "paperHands", "name": "Paper Hands", "emoji": "🧻", "desc": "Lost the most by selling a position early"},
    {"key": "marketMaker", "name": "Market Maker", "emoji": "🧠", "desc": "Proposed the most events"},
    {"key": "chatterbox", "name": "Chatterbox", "emoji": "🗣️", "desc": "Left the most comments"},
    {"key": "degenerate", "name": "Degenerate", "emoji": "🎲", "desc": "Most bets and hands played (10 or more)"},
    {"key": "comebackKid", "name": "Comeback Kid", "emoji": "🧗", "desc": "Climbed the most places in the standings"},
    {"key": "ghost", "name": "Ghost", "emoji": "👻", "desc": "Did absolutely nothing this week"},
]
AWARD_BY_KEY = {a["key"]: a for a in AWARD_DEFS}


def money(x):
    ax = abs(x)
    sign = "-" if x < 0 else ""
    for limit, suffix in ((1e15, None), (1e12, "T"), (1e9, "B"), (1e6, "M")):
        if ax >= limit:
            if suffix is None:
                return f"{sign}${ax:.2e}"
            return f"{sign}${ax / limit:,.2f}{suffix}"
    return f"{sign}${ax:,.2f}"


# ---- standings ---------------------------------------------------------------------
# HOW THE LEADERBOARD WORKS
#   A person's weekly performance is:  what they hold now  -  what they held when the week began  -  anything handed to them.
#   "What they hold" is the weekly account plus everything it is working on (open bets at their cash-out value, stakes in
#   casino rounds still being played, real money at a poker table). "Handed to them" is the weekly refill, a top-up from
#   the host, a voucher, a gift: all marked external in the ledger, so none of it can count as winnings. The accumulated
#   account, the Store and the Stock Exchange are not part of it at all.
#   Order of the table, best first, with fixed tie-breakers so two people can never be ordered by chance:
#     1. higher weekly performance   2. more held at the end   3. account created earlier   4. user id.

def metric(user, cache=None):
    """What the person holds (weekly cash plus what it is working on)."""
    if cache is not None and user["id"] in cache:
        return cache[user["id"]]
    v = markets.net_worth(user)
    if cache is not None:
        cache[user["id"]] = v
    return v


def start_value(user, week):
    snap = db()["snapshots"].get(prev_week_key(week), {})
    return snap.get(user["id"], config.START_BALANCE)


def perf_inputs(user, week):
    """(held when the week began, handed over during it), in dollars."""
    wk = user.get("wk") or {}
    if wk.get("week") == week:
        return wk.get("start_c", 0) / 100, wk.get("ext_c", 0) / 100
    return start_value(user, week), user["stats"].get(week, {}).get("deposits", 0)


def moves(user, week):
    s = user["stats"].get(week, {})
    return int(s.get("marketBets", 0) + s.get("gamesPlayed", 0))


# ---- the weekly minimum ------------------------------------------------------------------
# To stay in the challenge a person must bet in at least economy.WEEKLY_MIN_POLL_BETS poll and play at least
# economy.WEEKLY_MIN_CASINO_BETS casino rounds that week (both counted from the weekly stats, real money only). Whoever has not
# when the week CLOSES loses it automatically ("out"): they are the losers of the week, take its punishment in place of whoever
# finished last, are placed below everybody who took part, and earn no reward. While the week is still running the same
# numbers are shown as progress ("short") but change nothing: the live table and the reward estimates ignore them.
#   * Rounds count when they finish, so a round still being played when the week closes counts towards the next one.
#   * An account created during the week is exempt for that first partial week.
#   * The rule only applies to weeks from meta["requirements_from"] on. It is set to the week after the first one this code
#     ran in, so people have a whole week's notice (a database that never recorded one enforces from the start).

def requirements_start():
    return db()["meta"].get("requirements_from")


def requirements(user, week):
    """What `user` had to do in `week`, and how far they got. Nothing here changes anything."""
    s = user["stats"].get(week, {})
    polls, casino = int(s.get("marketBets", 0)), int(s.get("gamesPlayed", 0))
    need_p, need_c = economy.WEEKLY_MIN_POLL_BETS, economy.WEEKLY_MIN_CASINO_BETS
    start, _ = week_bounds(week)
    since = requirements_start()
    enabled = need_p > 0 or need_c > 0
    exempt = user["createdAt"] >= start
    enforced = enabled and (since is None or week >= since)
    short_p, short_c = max(0, need_p - polls), max(0, need_c - casino)
    return {"polls": {"have": polls, "need": need_p}, "casino": {"have": casino, "need": need_c},
            "met": short_p == 0 and short_c == 0, "enabled": enabled, "enforced": enforced, "exempt": exempt,
            "atRisk": enforced and not exempt and (short_p > 0 or short_c > 0)}


def missing_text(req):
    bits = []
    p, c = req["polls"], req["casino"]
    if p["have"] < p["need"]:
        n = p["need"] - p["have"]
        bits.append(f"{n} more poll bet{'' if n == 1 else 's'}")
    if c["have"] < c["need"]:
        n = c["need"] - c["have"]
        bits.append(f"{n} more casino bet{'' if n == 1 else 's'}")
    return " and ".join(bits)


def standings(c, week, members=None, cache=None, final=False):
    """The ordered table. With final=True (a week that is closing) anybody who missed the weekly minimum is marked "out" and
    placed below everybody who took part; otherwise the minimum only shows up as progress in each row's "req"."""
    rows = []
    for uid in (members if members is not None else list(c["members"])):
        u = users.get(uid)
        value = metric(u, cache)
        start, handed = perf_inputs(u, week)
        n = moves(u, week)
        req = requirements(u, week)
        rows.append({"user": users.public(u), "value": value, "start": start, "delta": round2(value - start - handed),
                     "moves": n, "active": n >= economy.REWARD_MIN_MOVES, "created": u["createdAt"],
                     "req": req, "out": bool(final and req["atRisk"])})
    rows.sort(key=lambda r: (r["out"], -ledger.to_cents(r["delta"]), -ledger.to_cents(r["value"]), r["created"], r["user"]["id"]))
    for i, r in enumerate(rows, start=1):
        r["position"] = i
    return rows


def losers_of(rows):
    """Who loses the week: everybody who missed the weekly minimum; if nobody did, whoever had the worst week."""
    out = [r for r in rows if r.get("out")]
    return out if out else bottom(rows)


def bottom(rows):
    """Everyone tied for the worst week. Nobody if the whole circle is tied (or only one member)."""
    if len(rows) < 2:
        return []
    low = min(r["delta"] for r in rows)
    losers = [r for r in rows if abs(r["delta"] - low) < 0.005]
    return [] if len(losers) == len(rows) else losers


# ---- rewards -----------------------------------------------------------------------
# Paid into the accumulated account when the week closes. The amounts are in economy.WEEKLY_REWARDS.
#   * Only active members (at least economy.REWARD_MIN_MOVES bets or casino rounds that week) can earn one, and they are
#     placed among the active members only, so somebody who sat the week out does not take a place.
#   * A circle needs economy.REWARD_MIN_ACTIVE active members, and small circles are paid on a sliding scale.
#   * Somebody in several circles is paid for their best finish only.

def plan_rewards(circle_rows):
    """circle_rows: {circle id: (circle, ordered rows)}. Fills row["reward"], row["rewardNote"] and returns per-circle
    details. Pure arithmetic over the rows it is given: it changes nothing."""
    cand = {}                                        # user id -> [(cents, -circle created, circle id, row)]
    info = {}
    for cid, (c, rows) in circle_rows.items():
        active = [r for r in rows if r["active"]]                    # took part: sets how many places are paid (the scale)
        placed = [r for r in active if not r.get("out")]            # and, of those, the ones who kept the weekly minimum take the places
        info[cid] = {"active": len(active), "scale": economy.reward_scale(len(active))}
        for r in rows:
            r["reward"], r["rewardNote"], r["rewardPos"] = 0.0, "", None
        for k, r in enumerate(placed, start=1):
            r["rewardPos"] = k
            amount = economy.reward_for_position(k, len(active))
            if amount > 0:
                cand.setdefault(r["user"]["id"], []).append((ledger.to_cents(amount), -c["createdAt"], cid, r))
        for r in rows:
            if r.get("out"):
                r["rewardNote"] = "Lost the week: missed the weekly minimum (%s)" % requirement_summary(r["req"])
            elif not r["active"]:
                r["rewardNote"] = "Needs %d bet%s or casino round%s this week to earn a reward" % (
                    economy.REWARD_MIN_MOVES, "" if economy.REWARD_MIN_MOVES == 1 else "s", "" if economy.REWARD_MIN_MOVES == 1 else "s")
        if info[cid]["scale"] <= 0:
            for r in placed:
                r["rewardNote"] = f"Rewards start when {economy.REWARD_MIN_ACTIVE} members are active"
    for uid, options in cand.items():
        options.sort(key=lambda o: (-o[0], -o[1], o[2]))
        keep = options[:economy.REWARD_MAX_PER_USER_PER_WEEK]
        for option in options:
            if any(option is k for k in keep):
                option[3]["reward"] = option[0] / 100
            else:
                option[3]["rewardNote"] = "Paid for your better finish in another circle"
    return info


def _week_rows(week, members_of=None, only=None, cache=None):
    """Every circle's ordered rows for a week, with rewards planned across all of them."""
    out = {}
    cache = cache if cache is not None else {}
    for c in db()["circles"].values():
        members = members_of(c) if members_of else list(c["members"])
        if not members or (only and c["id"] not in only):
            continue
        out[c["id"]] = (c, standings(c, week, members, cache))
    return out


def requirement_summary(req):
    p, c = req["polls"], req["casino"]
    return f"{p['have']}/{p['need']} poll bets, {c['have']}/{c['need']} casino bets"


def _requirement_rules():
    return {"polls": economy.WEEKLY_MIN_POLL_BETS, "casino": economy.WEEKLY_MIN_CASINO_BETS,
            "from": requirements_start(), "exemptFirstWeek": True}


def rules_snapshot():
    return {"requirements": _requirement_rules(), "rewards": list(economy.WEEKLY_REWARDS), "participation": economy.PARTICIPATION_REWARD,
            "minMoves": economy.REWARD_MIN_MOVES, "minActive": economy.REWARD_MIN_ACTIVE, "fullAt": economy.REWARD_FULL_AT,
            "maxPerUser": economy.REWARD_MAX_PER_USER_PER_WEEK, "account": "accumulated",
            "mode": "reset" if economy.WEEKLY_RESET else "topup", "allocation": economy.WEEKLY_ALLOCATION}


def rewards_pending(week=None):
    """Every reward that has been decided but not yet delivered."""
    out = []
    for c in db()["circles"].values():
        for wk, recap in c["recaps"].items():
            if week and wk != week:
                continue
            for uid, rw in (recap.get("rewards") or {}).items():
                if rw["amount"] > 0 and not rw["paid"]:
                    out.append((c, wk, recap, uid, rw))
    return out


def pay_rewards(week=None):
    """Delivers decided rewards. Safe to run any number of times, in any order, after a crash or a retry: a reward is
    marked paid in the same step as the credit, and the credit itself carries a transaction id."""
    paid = []
    for c, wk, recap, uid, rw in rewards_pending(week):
        u = db()["users"].get(uid)
        if not u:
            continue
        txid = f"reward:{wk}:{c['id']}:{uid}"
        ledger.post(u, "accumulated", rw["amount"] / 100, "weekly.reward", ref=f"{wk}:{c['id']}", txid=txid)
        rw["paid"], rw["txid"], rw["paidAt"] = True, txid, now_ms()
        users.log(u, "reward", rw["amount"] / 100, f"Weekly reward: #{rw['position']} in {c['name']}", c["id"])
        paid.append({"userId": uid, "amount": rw["amount"] / 100, "circle": c["name"], "position": rw["position"], "week": wk})
    return paid


# ---- punishment poll ---------------------------------------------------------------

def _poll(c, week):
    return c["punishments"].setdefault(week, [])


def _require_current(week):
    if week != week_key():
        raise bad("That week is over. The poll is closed.", code="week_over")


def add_punishment(user, c, text):
    circles.member_or_403(c, user)
    week = week_key()
    text = clean_text(text, "Punishment", 3, 120)
    poll = _poll(c, week)
    if sum(1 for p in poll if p["authorId"] == user["id"]) >= MAX_PUNISHMENTS_PER_USER:
        raise bad(f"You can suggest up to {MAX_PUNISHMENTS_PER_USER} punishments per week", code="punishment_limit")
    if any(p["text"].lower() == text.lower() for p in poll):
        raise bad("Someone already suggested that one. Go vote for it.", code="punishment_duplicate")
    entry = {"id": new_id(), "text": text, "authorId": user["id"], "t": now_ms(), "votes": [user["id"]]}
    for p in poll:                      # suggesting something counts as your vote
        if user["id"] in p["votes"]:
            p["votes"].remove(user["id"])
    poll.append(entry)
    return entry


def vote(user, c, pid):
    circles.member_or_403(c, user)
    poll = _poll(c, week_key())
    target = next((p for p in poll if p["id"] == pid), None)
    if not target:
        raise bad("Punishment not found", 404, code="punishment_not_found")
    already = user["id"] in target["votes"]
    for p in poll:
        if user["id"] in p["votes"]:
            p["votes"].remove(user["id"])
    if not already:
        target["votes"].append(user["id"])


def delete_punishment(user, c, pid):
    circles.member_or_403(c, user)
    poll = _poll(c, week_key())
    target = next((p for p in poll if p["id"] == pid), None)
    if not target:
        raise bad("Punishment not found", 404, code="punishment_not_found")
    if user["id"] not in (target["authorId"], c["ownerId"]):
        raise bad("Only the author or the circle owner can remove a punishment", 403, code="not_punishment_author")
    poll.remove(target)


def _poll_json(c, week, viewer):
    out = []
    for p in sorted(c["punishments"].get(week, []), key=lambda p: (-len(p["votes"]), p["t"])):
        out.append({"id": p["id"], "text": p["text"], "author": users.public(users.get(p["authorId"])),
                    "votes": len(p["votes"]), "voted": bool(viewer) and viewer["id"] in p["votes"],
                    "voters": [users.get(v)["username"] for v in p["votes"]][:12], "t": p["t"]})
    return out


def _winning_punishment(c, week):
    poll = c["punishments"].get(week, [])
    if not poll:
        return None, "Nobody suggested a punishment this week. Lucky escape."
    ranked = sorted(poll, key=lambda p: (-len(p["votes"]), p["t"]))
    best = ranked[0]
    note = ""
    if not len(best["votes"]):
        note = "No votes were cast, so the first suggestion won."
    elif len(ranked) > 1 and len(ranked[1]["votes"]) == len(best["votes"]):
        note = "Tie on votes. The earlier suggestion won."
    return {"id": best["id"], "text": best["text"], "author": users.public(users.get(best["authorId"])),
            "votes": len(best["votes"])}, note


# ---- awards ------------------------------------------------------------------------

def compute_awards(c, week, rows, members=None):
    members = members if members is not None else list(c["members"])
    S = {uid: users.get(uid)["stats"].get(week, {}) for uid in members}
    name = {r["user"]["id"]: r["user"]["username"] for r in rows}
    delta = {r["user"]["id"]: r["delta"] for r in rows}
    out = []

    def pick(fn, minimum=0, high=True):
        scored = []
        for uid in members:
            v = fn(uid)
            if v is None:
                continue
            ok = v >= minimum if high else v <= minimum
            if ok:
                scored.append((v, uid))
        if not scored:
            return None
        best = max(v for v, _ in scored) if high else min(v for v, _ in scored)
        tied = [uid for v, uid in scored if v == best]
        tied.sort(key=lambda uid: (-delta[uid], name[uid].lower()))
        return tied[0], best

    def give(key, uid, text):
        out.append({"key": key, "userIds": [uid] if isinstance(uid, str) else uid, "value": text})

    if len(rows) >= 2:
        richest = max(rows, key=lambda r: (ledger.to_cents(r["value"]), -r["position"]))
        poorest = min(rows, key=lambda r: ledger.to_cents(r["value"]))
        if richest["value"] > poorest["value"]:
            give("topDog", richest["user"]["id"], money(richest["value"]))
        losers = losers_of(rows)
        if losers:
            give("hotSeat", [r["user"]["id"] for r in losers],
                 "Missed the weekly minimum" if losers[0].get("out") else money(losers[0]["value"]))

    r = pick(lambda u: delta[u], 0.005)
    if r:
        give("rocketMan", r[0], "+" + money(r[1]))
    r = pick(lambda u: delta[u], -0.005, high=False)
    if r:
        give("freefall", r[0], money(r[1]))
    r = pick(lambda u: S[u].get("marketPnl", 0), 0.005)
    if r:
        give("oracle", r[0], "+" + money(r[1]) + " from predictions")

    def rate(u):
        w, l = S[u].get("betsWon", 0), S[u].get("betsLost", 0)
        return (w / (w + l) + (w + l) / 1e6) if w + l >= 3 else None
    r = pick(rate, 0)
    if r:
        w, l = S[r[0]].get("betsWon", 0), S[r[0]].get("betsLost", 0)
        give("sharpshooter", r[0], f"{round(100 * w / (w + l))}% ({w}/{w + l})")

    r = pick(lambda u: S[u].get("biggestBet", 0), 0.1)
    if r:
        give("whale", r[0], money(r[1]) + " on one bet")
    r = pick(lambda u: S[u].get("gameWagered", 0), 0.1)
    if r:
        give("highRoller", r[0], money(r[1]) + " wagered")
    r = pick(lambda u: (S[u].get("bestMult") or {}).get("value"), 5)
    if r:
        best = S[r[0]]["bestMult"]
        give("luckyCharm", r[0], f"x{best['value']:,.2f} on {best['label']}")
    r = pick(lambda u: S[u].get("bjWins", 0), 2)
    if r:
        give("cardShark", r[0], f"{int(r[1])} hands won")
    r = pick(lambda u: S[u].get("chickenBest", 0), 2)
    if r:
        give("chickenChamp", r[0], f"x{r[1]:,.2f} cash-out")
    r = pick(lambda u: S[u].get("roulettePnl", 0), 0.005)
    if r:
        give("spinDoctor", r[0], "+" + money(r[1]))
    r = pick(lambda u: S[u].get("gamePnl", 0) if S[u].get("gamesPlayed", 0) >= 3 else None, -0.005, high=False)
    if r:
        give("houseFavorite", r[0], money(r[1]) + " in games")
    r = pick(lambda u: S[u].get("badBeat", 0), 0.1)
    if r:
        give("badBeat", r[0], money(r[1]) + " gone")
    r = pick(lambda u: S[u].get("paperHandsLoss", 0), 0.1)
    if r:
        give("paperHands", r[0], money(r[1]) + " sold at a loss")
    r = pick(lambda u: S[u].get("marketsCreated", 0), 1)
    if r:
        give("marketMaker", r[0], f"{int(r[1])} event{'s' if r[1] != 1 else ''} proposed")
    r = pick(lambda u: S[u].get("comments", 0), 3)
    if r:
        give("chatterbox", r[0], f"{int(r[1])} comments")
    r = pick(lambda u: S[u].get("marketBets", 0) + S[u].get("gamesPlayed", 0), 10)
    if r:
        give("degenerate", r[0], f"{int(r[1])} plays")

    if len(rows) >= 3:                               # biggest climb in the standings
        start_order = sorted(rows, key=lambda x: (-x["start"], x["user"]["username"].lower()))
        start_rank = {x["user"]["id"]: i for i, x in enumerate(start_order)}
        end_order = sorted(rows, key=lambda x: (-x["value"], x["user"]["username"].lower()))
        end_rank = {x["user"]["id"]: i for i, x in enumerate(end_order)}
        r = pick(lambda u: start_rank[u] - end_rank[u], 2)
        if r:
            give("comebackKid", r[0], f"+{int(r[1])} places")

    def moves(u):
        s = S[u]
        return s.get("marketBets", 0) + s.get("gamesPlayed", 0) + s.get("comments", 0) + s.get("marketsCreated", 0)
    idle = [u for u in members if moves(u) == 0]
    if idle and len(idle) < len(members):
        give("ghost", idle, "0 moves")
    return out


# ---- the weekly view ---------------------------------------------------------------

def _row_json(r):
    return {"user": r["user"], "value": r["value"], "start": r["start"], "delta": r["delta"], "position": r["position"],
            "moves": r.get("moves", 0), "active": r.get("active", True), "reward": r.get("reward", 0.0),
            "rewardNote": r.get("rewardNote", ""), "req": r.get("req"), "out": bool(r.get("out"))}


def view(c, viewer, week=None):
    cur = week_key()
    week = week if week and valid_week_key(week) else cur
    start, end = week_bounds(week)
    recap = c["recaps"].get(week)
    first = datetime.date.fromisoformat(week)
    last = first + datetime.timedelta(days=6)
    out = {
        "week": week, "start": start, "end": end, "isCurrent": week == cur, "now": now_ms(), "remainingMs": max(0, end - now_ms()),
        "label": f"{first:%b} {first.day} – {last:%b} {last.day}",
        "awardDefs": AWARD_DEFS,
        "weeks": sorted(c["recaps"].keys(), reverse=True),
        "rankBy": "performance",
        "timezone": TZ_NAME,
        "rules": rules_snapshot(),
        "me": None,
    }
    if week == cur:
        near = {cid for cid, other in db()["circles"].items() if set(other["members"]) & set(c["members"])}
        plan = _week_rows(week, only=near)
        info = plan_rewards(plan)
        rows = plan[c["id"]][1]
        out["standings"] = [_row_json(r) for r in rows]
        out["hotSeat"] = [r["user"] for r in bottom(rows)]
        out["poll"] = _poll_json(c, week, viewer)
        out["awards"] = compute_awards(c, week, rows)
        out["provisional"] = True
        out["recap"] = None
        out["activeCount"], out["scale"] = info[c["id"]]["active"], info[c["id"]]["scale"]
    else:
        out["provisional"] = False
        out["recap"] = None
        out["poll"] = _poll_json(c, week, viewer)
        if recap:
            rows = []
            rewards = recap.get("rewards") or {}
            for i, r in enumerate(recap["standings"], start=1):
                u = users.get(r["userId"])
                rw = rewards.get(r["userId"])
                rows.append({"user": users.public(u), "value": r["value"], "start": r["start"], "delta": r["delta"],
                             "position": r.get("position", i), "moves": r.get("moves", 0), "active": r.get("active", True),
                             "reward": (rw["amount"] / 100) if rw else 0.0, "rewardNote": r.get("rewardNote", ""),
                             "rewardPaid": bool(rw and rw["paid"]), "req": r.get("req"), "out": bool(r.get("out"))})
            out["standings"] = rows
            out["hotSeat"] = [users.public(users.get(i)) for i in recap["loserIds"]]
            out["awards"] = recap["awards"]
            out["recap"] = {"punishment": recap["punishment"], "note": recap.get("note", ""),
                            "served": recap.get("served", False), "finalizedAt": recap["finalizedAt"],
                            "reason": recap.get("reason", "last")}
            out["rules"] = recap.get("rules") or out["rules"]
            out["activeCount"], out["scale"] = recap.get("active", 0), recap.get("scale", 0)
        else:
            out["standings"], out["hotSeat"], out["awards"] = [], [], []
            out["activeCount"], out["scale"] = 0, 0
    if viewer:
        mine = next((r for r in out["standings"] if r["user"]["id"] == viewer["id"]), None)
        if mine:
            out["me"] = {"position": mine["position"], "of": len(out["standings"]), "reward": mine["reward"], "delta": mine["delta"],
                         "moves": mine["moves"], "active": mine["active"], "note": mine["rewardNote"],
                         "paid": bool(mine.get("rewardPaid")), "req": mine.get("req"), "out": mine.get("out", False)}
    out["canMarkServed"] = bool(viewer) and (viewer["id"] == c["ownerId"] or
                                             (recap and viewer["id"] in recap.get("loserIds", [])))
    return out


def mark_served(user, c, week):
    recap = c["recaps"].get(week)
    if not recap:
        raise bad("That week hasn't been settled yet", 404, code="week_not_settled")
    if user["id"] != c["ownerId"] and user["id"] not in recap["loserIds"]:
        raise bad("Only the owner or the person being punished can mark this", 403, code="not_allowed")
    recap["served"] = not recap.get("served", False)


def my_week(user):
    """The signed-in person's best current finish across their circles, for the header and the account pages."""
    mine = [c for c in db()["circles"].values() if user["id"] in c["members"]]
    if not mine:
        return None
    week = week_key()
    near = {cid for cid, other in db()["circles"].items() if set(other["members"]) & {user["id"]}}
    plan = _week_rows(week, only=near)
    plan_rewards(plan)
    best = None
    for cid, (c, rows) in plan.items():
        r = next((x for x in rows if x["user"]["id"] == user["id"]), None)
        if not r or len(rows) < 2:
            continue
        cand = {"circle": {"id": cid, "name": c["name"]}, "position": r["position"], "of": len(rows), "reward": r["reward"],
                "delta": r["delta"], "active": r["active"], "note": r["rewardNote"]}
        if best is None or (cand["reward"], -cand["position"]) > (best["reward"], -best["position"]):
            best = cand
    start, end = week_bounds(week)
    return {"week": week, "end": end, "best": best}


# ---- week rollover -----------------------------------------------------------------
EVENTS = []           # what happened during the last tick(), for the server to announce once it has saved


def finalize_week(week):
    """Closes a week: takes the final snapshot, writes every circle's final leaderboard and decides the rewards, then
    delivers them. Calling it again for the same week changes nothing (a circle that already has its recap is skipped,
    and a reward that was paid is never paid twice)."""
    d = db()
    cache = {}
    d["snapshots"][week] = {uid: metric(u, cache) for uid, u in d["users"].items()}
    _, end = week_bounds(week)
    todo = {}
    for c in d["circles"].values():
        if c["createdAt"] >= end or week in c["recaps"]:
            continue
        members = [uid for uid, joined in c["members"].items() if joined < end]
        if len(members) < 2:
            continue
        todo[c["id"]] = (c, standings(c, week, members, cache, final=True))
    info = plan_rewards(todo)
    for cid, (c, rows) in todo.items():
        members = [r["user"]["id"] for r in rows]
        losers = losers_of(rows)
        by_minimum = bool(losers) and bool(losers[0].get("out"))
        punishment, note = (None, "") if not losers else _winning_punishment(c, week)
        if by_minimum:
            note = ("Lost the week by missing the weekly minimum. " + note).strip()
        rewards = {r["user"]["id"]: {"amount": ledger.to_cents(r["reward"]), "position": r["rewardPos"], "paid": False}
                   for r in rows if r["reward"] > 0}
        c["recaps"][week] = {
            "week": week, "finalizedAt": now_ms(),
            "standings": [{"userId": r["user"]["id"], "value": r["value"], "start": r["start"], "delta": r["delta"],
                           "position": r["position"], "moves": r["moves"], "active": r["active"],
                           "rewardNote": r["rewardNote"], "out": r["out"], "req": r["req"]} for r in rows],
            "loserIds": [r["user"]["id"] for r in losers], "reason": "minimum" if by_minimum else "last",
            "punishment": punishment, "note": note if losers else "Everyone finished level. No punishment this week.",
            "awards": compute_awards(c, week, rows, members), "served": False,
            "rewards": rewards, "rules": rules_snapshot(), "active": info[cid]["active"], "scale": info[cid]["scale"],
        }
    EVENTS.extend({"type": "reward", **p} for p in pay_rewards(week))


def refill_weekly(week):
    """A new week has begun: everybody who was around when it started gets their weekly account set for the week
    (reset to the allocation, or topped up by it, see economy.WEEKLY_RESET) and a fresh starting line for the leaderboard.
    The refill is marked external, so it is never mistaken for winnings. Running it twice for a week does nothing."""
    start, _ = week_bounds(week)
    alloc = ledger.to_cents(economy.WEEKLY_ALLOCATION)
    refilled = 0
    for u in db()["users"].values():
        if u["createdAt"] >= start or (u.get("wk") or {}).get("week") == week:       # joined since, or already done
            continue
        if alloc > 0:                                                                  # an allocation of 0 turns the refill off
            have = ledger.balance_c(u, "weekly")
            target = alloc if economy.WEEKLY_RESET else have + alloc
            if target > have:
                ledger.post(u, "weekly", (target - have) / 100, "weekly.allocation", external=True, ref=week)
            elif target < have:
                ledger.post(u, "weekly", (target - have) / 100, "weekly.expired", external=True, ref=week)
            u["passGo"] = {"week": week, "amount": economy.WEEKLY_ALLOCATION}
            users.log(u, "go", economy.WEEKLY_ALLOCATION, "New week: weekly account refilled")
            refilled += 1
        u["wk"] = {"week": week, "start_c": ledger.to_cents(markets.net_worth(u)), "ext_c": 0}
    return refilled


MIDWEEK_DAY, MIDWEEK_HOUR = 2, 12          # Wednesday (Monday is 0), 12:00 in the site's time zone


def midweek_ms(week):
    """When the Wednesday bonus of a week is due."""
    return week_moment_ms(week, MIDWEEK_DAY, MIDWEEK_HOUR)


def pay_midweek(week, now=None):
    """The Wednesday bonus: from Wednesday 12:00 on, everybody who had an account by then (and is not suspended or deleted) is given
    economy.MIDWEEK_BONUS in the weekly account, once for the week however many times this runs (each person is marked, and the ledger
    row has a fixed transaction id), and also if the server was off at noon (the first run after it is back pays). The money is marked
    external, so it is never mistaken for winnings. Returns how many people were paid."""
    d = db()
    now = now_ms() if now is None else now
    amount = economy.MIDWEEK_BONUS
    if amount <= 0 or d["meta"].get("midweek") == week:
        return 0
    due = midweek_ms(week)
    if now < due:
        return 0
    paid = 0
    for u in d["users"].values():
        if u["createdAt"] >= due or u.get("suspended") or u.get("deleted") or (u.get("midweek") or {}).get("week") == week:
            continue
        ledger.post(u, "weekly", amount, "weekly.midweek", external=True, ref=week, txid=f"midweek-{week}")
        u["midweek"] = {"week": week, "amount": amount}
        users.log(u, "go", amount, "Wednesday bonus: money added to your weekly account")
        inbox.push(u, "bonus", "Wednesday bonus", f"{money(amount)} landed in your weekly account.")
        paid += 1
    d["meta"]["midweek"] = week
    return paid


def tick():
    """Called every second or so. Closes any week that has ended (final leaderboards, rewards), starts the new one
    (refilled weekly accounts) and delivers any reward that is still owed. Returns True if anything changed."""
    d = db()
    cur = week_key()
    changed = False
    if "requirements_from" not in d["meta"]:             # the weekly minimum starts with the next week: a whole week's notice
        d["meta"]["requirements_from"] = next_week_key(cur)
        changed = True
    last = d["meta"].get("week")
    if last is None:
        d["meta"]["week"] = cur
        return True
    guard = 0
    while last < cur and guard < 600:
        # The order of a weekly close (ECONOMY.md, section 12), every step safe to run twice:
        finalize_week(last)                  # 1-2. snapshots first, so nothing below is in the old week's numbers; final tables; leaderboard rewards
        challenges.settle_week(last)         # 3. finished-but-unclaimed challenges are credited (weekly ones BEFORE the reset, so they can pay a loan)
        loans.collect_at_close(last)         # 4. whatever weekly funds are left are collected toward any loan
        progress.close_week(last)            # 5. the steady-week XP
        last = next_week_key(last)
        refill_weekly(last)                  # 6. the weekly account is reset to the new allocation
        loans.collect_from_allocation(last)  # 7. the share of it that pays a remaining debt is taken before it can be spent
        challenges.assign(last)              # 8. the new week's challenges
        changed = True
        guard += 1
    d["meta"]["week"] = cur
    if cur not in d.get("challenges", {}):
        challenges.assign(cur)
        changed = True
    if challenges.settle_pending(cur):       # a past week whose rewards could not all be credited the first time
        changed = True
    if pay_midweek(cur):                     # Wednesday noon: the bonus for everybody
        changed = True
    if remind_short(cur):
        changed = True
    if rewards_pending():                    # a reward decided earlier that did not get delivered (a failed attempt)
        EVENTS.extend({"type": "reward", **p} for p in pay_rewards())
        changed = True
    return changed


def remind_short(week, now=None):
    """Once per week, WEEKLY_REMIND_H hours before it closes, tells everybody who is still short of the weekly minimum (and would lose
    the week) what they have left to do. Returns how many people were told. Nothing is sent a second time."""
    d = db()
    now = now_ms() if now is None else now
    if economy.WEEKLY_REMIND_H <= 0 or d["meta"].get("reminded") == week:
        return 0
    _, end = week_bounds(week)
    if end - now > economy.WEEKLY_REMIND_H * 3600_000:
        return 0
    d["meta"]["reminded"] = week
    sent, seen = 0, set()
    for c in d["circles"].values():
        for uid, joined in c["members"].items():
            if uid in seen or joined >= end or len([m for m, j in c["members"].items() if j < end]) < 2:
                continue
            u = users.get(uid)
            req = requirements(u, week)
            if not req["atRisk"]:
                continue
            seen.add(uid)
            text = f"Weekly minimum: you still need {missing_text(req)} before the week closes, or you lose the week."
            users.log(u, "warn", 0, text)
            EVENTS.append({"type": "weekwarn", "userId": uid, "week": week, "text": text, "endsAt": end})
            sent += 1
    return sent


def reward_history(user):
    """Every weekly reward this person was given, newest first: where, what position and how much."""
    out = []
    for c in db()["circles"].values():
        for week, recap in c["recaps"].items():
            rw = (recap.get("rewards") or {}).get(user["id"])
            if rw and rw["amount"] > 0:
                out.append({"week": week, "circle": c["name"], "circleId": c["id"], "position": rw["position"], "amount": rw["amount"] / 100,
                            "paid": rw["paid"], "paidAt": rw.get("paidAt")})
    out.sort(key=lambda r: r["week"], reverse=True)
    return out


def trophies(user):
    """All the awards a user has ever won, across circles."""
    counts, recent = {}, []
    for c in db()["circles"].values():
        for week, recap in c["recaps"].items():
            for a in recap["awards"]:
                if user["id"] in a["userIds"]:
                    counts[a["key"]] = counts.get(a["key"], 0) + 1
                    recent.append({"key": a["key"], "week": week, "circle": c["name"], "value": a["value"]})
    recent.sort(key=lambda r: r["week"], reverse=True)
    return counts, recent[:30]
