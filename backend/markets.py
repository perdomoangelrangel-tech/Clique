"""Markets (the events people bet on), trading, resolution, portfolio."""
import math
import re

from . import activity, circles, config, economy, games, lmsr, loans, poker, users
from .store import db
from .util import bad, clean_text, now_ms, new_id, parse_money, round2

CATEGORY_EMOJI = {"General": "🎲", "Sports": "🏆", "Gaming": "🎮", "Life": "🌱",
                  "Money": "💰", "Dares": "😈", "Music": "🎵", "Other": "✨"}
HIST_MAX = 3000
TRADES_MAX = 500
EPS = 1e-9
MAX_OPEN_PUBLIC = 20       # open site-wide markets one person may have at a time


# ---- lookup helpers ----------------------------------------------------------------

def get(mid):
    m = db()["markets"].get(mid)
    if not m:
        raise bad("Market not found", 404)
    return m


def circle_of(m):
    """The circle a market belongs to, or None for a site-wide market (open to every signed-in person)."""
    cid = m.get("circleId")
    return db()["circles"][cid] if cid else None


def visible(m, viewer):
    c = circle_of(m)
    return bool(viewer) if c is None else circles.can_view(c, viewer)


def _member_or_403(m, user):
    c = circle_of(m)
    if c is not None:
        circles.member_or_403(c, user)


def view_or_404(mid, viewer):
    m = get(mid)
    if not visible(m, viewer):
        raise bad("Market not found", 404)
    return m


def state_of(m):
    if m["status"] != "open":
        return m["status"]
    if m.get("closesAt") and m["closesAt"] <= now_ms():
        return "closed"
    return "open"


def token_of(m, outcome, side):
    n = len(m["outcomes"])
    try:
        i = int(outcome)
    except (TypeError, ValueError):
        raise bad("Pick an outcome")
    if not 0 <= i < n:
        raise bad("Unknown outcome")
    s = "n" if str(side).lower() in ("no", "n") else "y"
    if n == 2 and s == "n":          # NO on a 2-outcome market is just the other outcome
        i, s = 1 - i, "y"
    return i, s, f"{s}{i}"


def token_label(m, token):
    side, i = token[0], int(token[1:])
    name = m["outcomes"][i]
    if len(m["outcomes"]) == 2:
        return name
    return f"{name} · {'Yes' if side == 'y' else 'No'}"


# ---- creating ----------------------------------------------------------------------

def create(user, body):
    if body.get("scope") == "site":
        c = None
        open_public = sum(1 for x in db()["markets"].values()
                          if x["creatorId"] == user["id"] and not x.get("circleId") and x["status"] == "open")
        if open_public >= MAX_OPEN_PUBLIC:
            raise bad(f"You already have {MAX_OPEN_PUBLIC} open public bets. Settle one first.")
    else:
        c = circles.get(body.get("circleId"))
        circles.member_or_403(c, user)
    question = clean_text(body.get("question"), "Question", 5, 160)
    description = ""
    if body.get("description"):
        description = str(body["description"]).strip()[:1000]
    raw = body.get("outcomes")
    if not raw:
        outcomes = ["Yes", "No"]
    else:
        if not isinstance(raw, list) or not 2 <= len(raw) <= 12:
            raise bad("A market needs between 2 and 12 outcomes")
        outcomes = [clean_text(x, "Outcome", 1, 40) for x in raw]
        if len({o.lower() for o in outcomes}) != len(outcomes):
            raise bad("Outcome names must be different")
    category = body.get("category") or "General"
    if category not in config.CATEGORIES:
        category = "General"
    emoji = str(body.get("emoji") or CATEGORY_EMOJI[category]).strip()[:8]
    closes = body.get("closesAt")
    if closes in ("", None, 0):
        closes = None
    else:
        try:
            closes = int(closes)
        except (TypeError, ValueError):
            raise bad("Invalid end date")
        if closes < now_ms() + 60_000:
            raise bad("The end date must be in the future")
        if closes > now_ms() + 5 * 365 * 86400000:
            raise bad("The end date is too far away")
    b = config.MARKET_LIQUIDITY                 # one standard depth; whoever proposes a bet does not get to choose it
    n = len(outcomes)
    m = {
        "id": new_id(), "circleId": c["id"] if c else None, "creatorId": user["id"], "question": question,
        "description": description, "category": category, "emoji": emoji,
        "outcomes": outcomes, "b": b, "q": [0.0] * n, "status": "open",
        "closesAt": closes, "createdAt": now_ms(), "resolvedAt": None, "winner": None,
        "volume": 0.0, "positions": {}, "trades": [], "comments": [],
        "history": [{"t": now_ms(), "p": [1.0 / n] * n}],
    }
    db()["markets"][m["id"]] = m
    users.stat_add(user, "marketsCreated")
    activity.safe_record(user, "create", m["id"])
    return m


# ---- serialising -------------------------------------------------------------------

def _outcome_rows(m):
    p = lmsr.prices(m["q"], m["b"])
    pct = lmsr.percentages(p)                      # whole percentages that always add up to exactly 100
    return [{"name": name, "yes": p[i], "no": max(0.0, 1.0 - p[i]), "pct": pct[i]} for i, name in enumerate(m["outcomes"])]


def recent_volume(m, hours=24):
    cutoff = now_ms() - hours * 3600_000
    return sum(t["amount"] for t in m["trades"] if t["t"] >= cutoff)


def summary(m, viewer):
    c = circle_of(m)
    creator = users.get(m["creatorId"])
    return {
        "id": m["id"], "question": m["question"], "description": m["description"],
        "category": m["category"], "emoji": m["emoji"], "outcomes": _outcome_rows(m),
        "binary": len(m["outcomes"]) == 2, "status": state_of(m), "winner": m["winner"],
        "closesAt": m["closesAt"], "createdAt": m["createdAt"], "resolvedAt": m["resolvedAt"],
        "volume": round2(m["volume"]), "volume24h": round2(recent_volume(m)), "traders": len(m["positions"]),
        "comments": len(m["comments"]),
        "scope": "site" if c is None else "circle",
        "circle": None if c is None else {"id": c["id"], "name": c["name"], "emoji": c["emoji"],
                                          "visibility": c["visibility"]},
        "creator": users.public(creator),
        "canManage": bool(viewer) and m["status"] == "open" and (
            viewer["id"] == m["creatorId"] or (c is not None and viewer["id"] == c["ownerId"])),
        "canEdit": bool(viewer) and m["status"] == "open" and can_edit(m, viewer),
        "version": m.get("version", 1), "edited": bool(m.get("edits")),
        "lastEditedAt": m["edits"][-1]["t"] if m.get("edits") else None,
    }


def _downsample(history, limit=400):
    if len(history) <= limit:
        return history
    step = len(history) / limit
    out = [history[int(i * step)] for i in range(limit - 1)]
    out.append(history[-1])
    return out


def _position_row(m, uid, token, pos):
    i, side = int(token[1:]), token[0]
    held = pos["shares"]
    row = {
        "market": m["id"], "question": m["question"], "emoji": m["emoji"], "category": m["category"],
        "token": token,
        "outcome": i, "side": "yes" if side == "y" else "no", "label": token_label(m, token),
        "shares": held, "invested": round2(pos["invested"]),
        "avgPrice": pos["invested"] / held if held > EPS else 0,
        "status": state_of(m), "settled": bool(pos.get("settled")),
        "binary": len(m["outcomes"]) == 2,
        "closes": m.get("closesAt"),
        "version": pos.get("v", 1), "underOldRules": pos.get("v", 1) < m.get("version", 1),
        "withdrawable": bool(pos.get("pre")) and exit_open(m),
    }
    if pos.get("settled"):
        payout = pos.get("payout", 0.0)
        row["value"] = round2(payout)
        row["pnl"] = round2(payout - pos["invested"]) if not pos.get("refunded") else 0.0
        row["refunded"] = bool(pos.get("refunded"))
    elif m["status"] == "open":
        lnp, lnq = lmsr.token_logs(m["q"], m["b"], i, side)
        row["price"] = math.exp(lnp)
        row["value"] = lmsr.floor_cents(lmsr.proceeds_for_shares(lnp, lnq, m["b"], held))      # what cashing out pays right now
        row["pnl"] = round2(row["value"] - pos["invested"])
    return row


def detail(m, viewer):
    out = summary(m, viewer)
    out["history"] = _downsample(m["history"])
    out["rules"] = m["description"]
    mine = []
    if viewer and viewer["id"] in m["positions"]:
        for token, pos in m["positions"][viewer["id"]].items():
            if pos["shares"] > EPS:
                mine.append(_position_row(m, viewer["id"], token, pos))
    out["myPositions"] = mine
    holders = []
    for uid, toks in m["positions"].items():
        who = users.public(users.get(uid))
        for token, pos in toks.items():
            if pos["shares"] > EPS:
                row = _position_row(m, uid, token, pos)
                holders.append({"user": who, "token": token, "label": row["label"], "side": row["side"],
                                "outcome": row["outcome"], "shares": pos["shares"], "invested": row["invested"],
                                "avgPrice": row["avgPrice"], "value": row.get("value"), "pnl": row.get("pnl"),
                                "settled": row["settled"]})
    holders.sort(key=lambda h: (-h["invested"], h["user"]["username"]))
    out["holders"] = holders[:100]
    out["investedTotal"] = round2(sum(h["invested"] for h in holders))
    out["activity"] = [{
        "t": t["t"], "user": users.public(users.get(t["u"])), "kind": t["k"],
        "label": token_label(m, t["token"]), "amount": t["amount"], "shares": t["shares"],
        "price": t["price"],
    } for t in reversed(m["trades"][-60:])]
    out["commentList"] = [{
        "id": c["id"], "t": c["t"], "text": c["text"], "user": users.public(users.get(c["u"])),
    } for c in reversed(m["comments"][-100:])]
    out["balance"] = viewer["balance"] if viewer else 0
    c = circle_of(m)
    out["isMember"] = bool(viewer) and (c is None or circles.is_member(c, viewer))
    out["exit"] = exit_info(m, viewer)
    out["editCount"] = len(m.get("edits") or [])
    return out


def list_markets(viewer, circle=None, q=None, category=None, status="open", sort="trending"):
    q = (q or "").strip().lower()
    rows = []
    for m in db()["markets"].values():
        if not visible(m, viewer):
            continue
        if circle == "site":
            if m.get("circleId"):
                continue
        elif circle and m.get("circleId") != circle:
            continue
        if category and m["category"] != category:
            continue
        st = state_of(m)
        if status == "open" and st not in ("open", "closed"):
            continue
        if status == "resolved" and st not in ("resolved", "cancelled"):
            continue
        if q:
            hay = (m["question"] + " " + m["description"] + " " + " ".join(m["outcomes"])).lower()
            if q not in hay:
                continue
        rows.append(m)
    if sort == "new":
        rows.sort(key=lambda m: -m["createdAt"])
    elif sort == "ending":
        rows.sort(key=lambda m: (m["closesAt"] is None, m["closesAt"] or 0))
    elif sort == "volume":
        rows.sort(key=lambda m: -m["volume"])
    elif status == "resolved":
        rows.sort(key=lambda m: -(m["resolvedAt"] or 0))
    else:
        rows.sort(key=lambda m: (-recent_volume(m), -m["createdAt"]))
    return [summary(m, viewer) for m in rows]


# ---- trading -----------------------------------------------------------------------

def _require_trading(m, user):
    _member_or_403(m, user)
    st = state_of(m)
    if st == "closed":
        raise bad("Trading has closed for this market. Waiting for the result.")
    if st != "open":
        raise bad("This market is no longer open")


def _number(value, label):
    """A real, finite number from the browser, or a 400."""
    n = parse_money(value, label)
    return n


def _plan(m, user, body):
    """Works out exactly what a buy or a sell would do right now. Changes nothing, so a quote and the trade it leads
    to are the very same calculation. Because the LMSR cost function is path independent, buying and then selling the
    same shares returns exactly what was paid; and every dollar amount paid OUT is rounded down to a whole cent, so a
    round trip, or a pile of tiny sells, can never end up ahead."""
    _require_trading(m, user)
    action = body.get("action", "buy")
    i, side, token = token_of(m, body.get("outcome"), body.get("side", "yes"))
    b, q = m["b"], m["q"]
    ln_p, ln_q = lmsr.token_logs(q, b, i, side)
    price = math.exp(ln_p)
    probs_before = lmsr.prices(q, b)
    pos = m["positions"].get(user["id"], {}).get(token)
    held = pos["shares"] if pos else 0.0

    if action == "buy":
        amount = round2(_number(body.get("amount"), "Amount"))
        if amount < config.MIN_BET - 1e-9:
            raise bad(f"The minimum bet is ${config.MIN_BET:.2f}")
        if amount > user["balance"] + 1e-9:
            raise bad("Not enough funds")
        shares = lmsr.shares_for_amount(ln_p, ln_q, b, amount)
        for _ in range(60):                            # never hand out more than the stake actually pays for (float noise only)
            if not math.isfinite(shares) or lmsr.cost_for_shares(ln_p, ln_q, b, shares) <= amount + 1e-9:
                break
            shares *= 1 - 1e-12
        if not math.isfinite(shares) or shares <= 0:
            raise bad("That amount is too small")
        q2 = lmsr.apply_trade(q, i, side, shares)
        plan = {"action": "buy", "amount": amount, "shares": shares, "heldAfter": held + shares}
    elif action == "sell":
        if held <= EPS:
            raise bad("You don't hold any of these shares")
        if body.get("all") is True:
            shares = held
        else:
            shares = _number(body.get("shares"), "Shares")
        if shares <= 0:
            raise bad("Enter how many shares to sell")
        if shares > held * (1 + 1e-9) + 1e-9:
            raise bad(f"You only hold {held:,.2f} shares")
        if shares >= held - 1e-6:
            shares = held
        amount = lmsr.floor_cents(lmsr.proceeds_for_shares(ln_p, ln_q, b, shares))
        if amount < 0.01:
            raise bad("That's worth less than a cent. Sell more shares, or hold them until the bet is settled.")
        q2 = lmsr.apply_trade(q, i, side, -shares)
        plan = {"action": "sell", "amount": amount, "shares": shares, "heldAfter": max(0.0, held - shares)}
        if shares >= held - EPS:
            plan["heldAfter"] = 0.0
    else:
        raise bad("Unknown action")

    ln_p2, _ = lmsr.token_logs(q2, b, i, side)
    probs_after = lmsr.prices(q2, b)
    plan.update({"token": token, "label": token_label(m, token), "outcome": i, "side": "yes" if side == "y" else "no",
                 "q2": q2, "priceBefore": price, "priceAfter": math.exp(ln_p2), "avgPrice": plan["amount"] / plan["shares"],
                 "held": held, "probsBefore": probs_before, "probsAfter": probs_after,
                 "pctAfter": lmsr.percentages(probs_after), "balanceAfter": round2(user["balance"] + (plan["amount"] if plan["action"] == "sell" else -plan["amount"]))})
    if plan["action"] == "sell":
        plan["basis"] = pos["invested"] * (plan["shares"] / pos["shares"])
        plan["pnl"] = plan["amount"] - plan["basis"]
    return plan


_QUOTE_KEYS = ("action", "token", "label", "outcome", "side", "amount", "shares", "avgPrice", "priceBefore", "priceAfter",
               "held", "heldAfter", "probsBefore", "probsAfter", "pctAfter", "balanceAfter")


def quote(m, user, body):
    p = _plan(m, user, body)
    out = {k: p[k] for k in _QUOTE_KEYS}
    if p["action"] == "buy":
        out["payout"] = p["shares"]                    # what the shares pay if they win: $1 each
        out["profit"] = p["shares"] - p["amount"]
        out["returnPct"] = (p["shares"] / p["amount"] - 1) * 100
    else:
        out["payout"] = None
        out["pnl"] = p["pnl"]
    return out


def _request_key(user, m, body):
    """An optional id the browser makes up for each press of the button, so a double click or a retry cannot trade twice."""
    rid = body.get("requestId")
    if rid is None:
        return None, None
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", rid):
        raise bad("Invalid request id")
    fingerprint = "|".join(str(x) for x in (m["id"], body.get("action", "buy"), body.get("outcome"), str(body.get("side", "yes")).lower(),
                                             body.get("amount"), body.get("shares"), body.get("all")))
    return f"{user['id']}:{rid}", fingerprint


def _remember(key, fingerprint, result):
    store = db().setdefault("idem", {})
    store[key] = {"t": now_ms(), "fp": fingerprint, "result": result}
    if len(store) > 1000:                              # keep the newest few hundred; a retry comes seconds later, not days
        for old in sorted(store, key=lambda k: store[k]["t"])[:-500]:
            del store[old]


def _check_expectations(p, body):
    """The price may have moved since the person looked at the quote. If the deal got worse than they accepted, say so
    instead of quietly giving them less."""
    moved = "The price moved while you were deciding. Review the new quote and try again."
    if p["action"] == "buy" and body.get("minShares") is not None:
        if p["shares"] + 1e-9 < _number(body["minShares"], "Minimum shares"):
            raise bad(moved, 409)
    if p["action"] == "sell" and body.get("minAmount") is not None:
        if p["amount"] + 1e-9 < _number(body["minAmount"], "Minimum amount"):
            raise bad(moved, 409)


def _result(p):
    return {k: p[k] for k in ("action", "token", "label", "amount", "shares", "avgPrice", "priceBefore", "priceAfter",
                              "probsAfter", "pctAfter", "heldAfter")}


def trade(user, m, body):
    """Buys or sells. Everything is checked first (funds, holdings, market state, the price the person agreed to); only
    then does anything change, and what changes cannot fail halfway. The server runs one request at a time, so two
    trades can never see each other half done."""
    key, fingerprint = _request_key(user, m, body)
    if key:
        seen = db().setdefault("idem", {}).get(key)
        if seen:
            if seen["fp"] != fingerprint:
                raise bad("That request id was already used for a different trade", 409)
            return {**seen["result"], "duplicate": True}
    p = _plan(m, user, body)
    _check_expectations(p, body)
    uid, token = user["id"], p["token"]
    label = token_label(m, token)
    if p["action"] == "buy":
        users.debit(user, p["amount"], "market.buy")                 # the only step that can refuse, and it runs before anything moves
    pos = m["positions"].setdefault(uid, {}).setdefault(token, {"shares": 0.0, "invested": 0.0, "v": m.get("version", 1)})
    if p["action"] == "buy":
        pos["shares"] += p["shares"]
        pos["invested"] += p["amount"]
        users.stat_add(user, "marketBets")
        users.stat_add(user, "marketWagered", p["amount"])
        users.stat_max(user, "biggestBet", p["amount"])
        users.log(user, "buy", -p["amount"], f"Bought {label}: {m['question']}", m["id"])
        activity.safe_record(user, "polls", new_id(), amount=p["amount"], market=m["id"], category=m.get("category"))
    else:
        basis = pos["invested"] * (p["shares"] / pos["shares"])
        users.credit(user, p["amount"], "market.sell")
        if p["shares"] >= pos["shares"] - EPS:
            pos["shares"], pos["invested"] = 0.0, 0.0
        else:
            pos["shares"] -= p["shares"]
            pos["invested"] -= basis
        realized = p["amount"] - basis
        users.stat_add(user, "marketPnl", realized)
        if realized < 0:
            users.stat_add(user, "paperHandsLoss", -realized)
        users.log(user, "sell", p["amount"], f"Sold {label}: {m['question']}", m["id"])
    if pos["shares"] <= EPS:
        del m["positions"][uid][token]
        if not m["positions"][uid]:
            del m["positions"][uid]
    m["q"] = p["q2"]
    m["volume"] += p["amount"]
    m["trades"].append({"t": now_ms(), "u": uid, "k": p["action"], "token": token,
                        "amount": p["amount"], "shares": p["shares"], "price": p["avgPrice"]})
    del m["trades"][:-TRADES_MAX]
    m["history"].append({"t": now_ms(), "p": lmsr.prices(m["q"], m["b"])})
    del m["history"][1:-HIST_MAX]
    result = _result(p)
    if key:
        _remember(key, fingerprint, result)
    return {**result, "duplicate": False}


# ---- resolving ---------------------------------------------------------------------

def _manager_or_403(m, user):
    c = circle_of(m)
    if user["id"] != m["creatorId"] and (c is None or user["id"] != c["ownerId"]):
        raise bad("Only the creator of this bet" + ("" if c is None else " or the circle owner") + " can do that", 403)
    if m["status"] != "open":
        raise bad("This market is already settled")


def resolve(user, m, winner):
    _manager_or_403(m, user)
    try:
        w = int(winner)
    except (TypeError, ValueError):
        raise bad("Pick the winning outcome")
    if not 0 <= w < len(m["outcomes"]):
        raise bad("Unknown outcome")
    paid = 0.0
    for uid, toks in m["positions"].items():
        u = users.get(uid)
        for token, pos in toks.items():
            i, side = int(token[1:]), token[0]
            wins = (i == w) if side == "y" else (i != w)
            payout = round2(pos["shares"]) if wins else 0.0
            pos["settled"], pos["payout"] = True, payout
            pnl = payout - pos["invested"]
            users.stat_add(u, "marketPnl", pnl)
            if payout > 0:
                users.credit(u, payout, "market.payout", ref=m["id"])
                paid += payout
                users.stat_add(u, "betsWon")
                users.stat_max(u, "bestWin", pnl)
                users.log(u, "win", payout, f"Won {token_label(m, token)}: {m['question']}", m["id"])
            else:
                users.stat_add(u, "betsLost")
                avg = pos["invested"] / pos["shares"] if pos["shares"] > EPS else 0
                if avg >= 0.7:
                    users.stat_max(u, "badBeat", pos["invested"])
                users.log(u, "loss", 0, f"Lost {token_label(m, token)}: {m['question']}", m["id"])
    m["status"], m["winner"], m["resolvedAt"] = "resolved", w, now_ms()
    return paid


def cancel(user, m):
    _manager_or_403(m, user)
    for uid, toks in m["positions"].items():
        u = users.get(uid)
        for token, pos in toks.items():
            refund = round2(pos["invested"])
            pos["settled"], pos["payout"], pos["refunded"] = True, refund, True
            users.credit(u, refund, "market.refund", ref=m["id"])
            users.log(u, "refund", refund, f"Refund (cancelled): {m['question']}", m["id"])
    m["status"], m["resolvedAt"] = "cancelled", now_ms()


def add_comment(user, m, text):
    _member_or_403(m, user)
    text = clean_text(text, "Comment", 1, 300)
    m["comments"].append({"id": new_id(), "u": user["id"], "t": now_ms(), "text": text})
    del m["comments"][:-300]
    users.stat_add(user, "comments")


# ---- portfolio ---------------------------------------------------------------------

def open_positions_value(uid):
    """What the person has working for them outside their cash: open bets, real money at a poker table, and stakes in
    casino rounds still being played."""
    total = poker.real_stake(uid) + games.escrow(uid)
    for m in db()["markets"].values():
        if m["status"] != "open":
            continue
        toks = m["positions"].get(uid)
        if not toks:
            continue
        for token, pos in toks.items():
            i, side = int(token[1:]), token[0]
            lnp, lnq = lmsr.token_logs(m["q"], m["b"], i, side)
            total += lmsr.proceeds_for_shares(lnp, lnq, m["b"], pos["shares"])
    return total


def net_worth(user):
    """What the person holds: weekly cash plus what their open bets and rounds are worth, MINUS anything they owe on a loan.
    (Borrowing adds exactly what it adds to the debt, so a loan never changes this number; see loans.py.)"""
    return round2(user["balance"] + open_positions_value(user["id"]) - loans.owed(user))


def distribution(balance, open_rows, uid=None):
    """Where the money is: cash, open positions grouped by market, category and circle, and any poker stack."""
    def grouped(key_of):
        out = {}
        for r in open_rows:
            key, label, extra = key_of(r)
            g = out.setdefault(key, {"key": key, "label": label, "value": 0.0, "invested": 0.0, **extra})
            g["value"] += r.get("value", 0)
            g["invested"] += r["invested"]
        rows = sorted(out.values(), key=lambda g: -g["value"])
        for g in rows:
            g["value"], g["invested"] = round2(g["value"]), round2(g["invested"])
        return rows
    markets_by_id = db()["markets"]

    def circle_key(r):
        c = circle_of(markets_by_id[r["market"]])
        return ("site", "Public", {}) if c is None else (c["id"], c["name"], {"emoji": c["emoji"]})
    invested = round2(sum(r.get("value", 0) for r in open_rows))
    at_poker = round2(poker.real_stake(uid)) if uid else 0.0
    return {
        "cash": round2(balance), "invested": invested, "poker": at_poker, "total": round2(balance + invested + at_poker),
        "byMarket": grouped(lambda r: (r["market"], r["question"], {"emoji": r["emoji"]})),
        "byCategory": grouped(lambda r: (r["category"], r["category"], {})),
        "byCircle": grouped(circle_key),
    }


def portfolio(user):
    open_rows, closed_rows = [], []
    for m in db()["markets"].values():
        toks = m["positions"].get(user["id"])
        if not toks:
            continue
        for token, pos in toks.items():
            row = _position_row(m, user["id"], token, pos)
            (closed_rows if pos.get("settled") else open_rows).append(row)
    open_rows.sort(key=lambda r: -r.get("value", 0))
    closed_rows.sort(key=lambda r: -r.get("value", 0))
    return {
        "balance": user["balance"], "positionsValue": round2(sum(r.get("value", 0) for r in open_rows)),
        "netWorth": net_worth(user), "open": open_rows, "closed": closed_rows[:60],
        "activity": user["activity"][:100], "distribution": distribution(user["balance"], open_rows, user["id"]),
    }


# ---- editing a published poll ------------------------------------------------------------------------------------
# WHO: the person who proposed it, or the owner of the circle it belongs to. WHEN: while it is not settled or cancelled
# (a settled outcome is never reopened or changed here). WHAT: the closing date/time and the rules (the description).
#
# THE POLICY, IN ONE PLACE
#   * Nobody has bet yet: any change is fine. It is saved as a new version and logged.
#   * People have bet (anyone holds a position or has traded):
#       - every change needs a reason, is saved as a new numbered version, and is announced to everybody involved;
#       - changing the closing date is always a MATERIAL change (it can change the answer). So is any rules change the editor
#         does not declare to be a CLARIFICATION (wording only, same meaning), and a declared clarification still needs a reason
#         and is shown to everybody as such;
#       - a material change opens an EXIT WINDOW (EDIT_EXIT_WINDOW_H hours): every holder may withdraw what they had bet under
#         the old rules and get back exactly what they paid, whatever the market price is now. Their old position is marked
#         with the version it was opened under, so nobody's bet is quietly reinterpreted;
#       - the closing time can not be moved earlier than 24 hours from now (people need time to react), and while an exit
#         window is open it can not be moved earlier than the window's end;
#       - only one material change is allowed per poll once people have bet; further edits must be clarifications.
#   * The full history (what changed, from, to, who, when, why, and whether it was material) is public to anyone who can see the poll.

MIN_REASON = 10
REACTION_MS = 24 * 3600 * 1000


def can_edit(m, user):
    c = circle_of(m)
    return bool(user) and (user["id"] == m["creatorId"] or (c is not None and user["id"] == c["ownerId"]))


def participants(m):
    ids = set(m["positions"])
    ids |= {t["u"] for t in m["trades"]}
    return ids


def exit_open(m, now=None):
    until = (m.get("exit") or {}).get("until") or 0
    return until > (now_ms() if now is None else now)


def exit_info(m, viewer):
    e = m.get("exit")
    if not e:
        return None
    now = now_ms()
    mine = []
    if viewer and viewer["id"] in m["positions"]:
        mine = [t for t, p in m["positions"][viewer["id"]].items() if p.get("pre") and p["shares"] > EPS]
    return {"until": e["until"], "open": e["until"] > now, "version": e["version"], "tokens": mine}


def _parse_close(value):
    if value in ("", None, 0):
        return None
    if isinstance(value, bool):
        raise bad("Invalid end date")
    try:
        t = int(value)
    except (TypeError, ValueError):
        raise bad("Invalid end date")
    return t


def edit_plan(user, m, body, now=None):
    """Works out what an edit would do and whether it is allowed. Changes nothing: the preview and the save are the same
    calculation, so what you are shown is what happens."""
    now = now_ms() if now is None else now
    if not can_edit(m, user):
        raise bad("Only the person who proposed this bet, or the owner of its circle, can edit it", 403)
    if m["status"] == "resolved":
        raise bad("This bet is settled. A settled result can not be reopened or changed.", 409)
    if m["status"] == "cancelled":
        raise bad("This bet was cancelled, so there is nothing left to edit.", 409)
    if not isinstance(body, dict):
        raise bad("Invalid request")
    changes = {}
    if "closesAt" in body:
        new_close = _parse_close(body["closesAt"])
        if new_close != m.get("closesAt"):
            if new_close is not None:
                if new_close < now + economy.EDIT_MIN_LEAD_MS:
                    raise bad("The new closing time must be at least 5 minutes from now")
                if new_close > now + 5 * 365 * 86400000:
                    raise bad("The end date is too far away")
            changes["closesAt"] = {"from": m.get("closesAt"), "to": new_close}
    if "description" in body:
        new_desc = str(body["description"] or "").strip()[:1000] if not isinstance(body["description"], (list, dict)) else None
        if new_desc is None:
            raise bad("The rules must be text")
        if new_desc != (m.get("description") or ""):
            changes["description"] = {"from": m.get("description") or "", "to": new_desc}
    if not changes:
        raise bad("Nothing would change. Edit the date or the rules first.")
    people = participants(m)
    people.discard(user["id"])
    involved = set(people)                  # the editor's own bet is not "somebody else's bet reinterpreted"
    declared = body.get("kind")
    if declared not in (None, "clarification", "material"):
        raise bad("Say whether this is a clarification or a material change")
    reason = body.get("reason")
    reason = " ".join(str(reason).split()) if isinstance(reason, str) else ""
    if len(reason) > 200:
        raise bad("The reason is too long (max 200)")
    plan = {"changes": changes, "participants": len(involved), "affected": sorted(people), "reason": reason, "now": now,
            "positions": sum(1 for p in m["positions"].values() for pos in p.values() if pos["shares"] > EPS), "exitUntil": None}
    if not involved:
        plan["class"], plan["note"] = "no_participation", "Nobody has bet on this yet, so the change affects nobody. It is still saved as a new version."
        return plan
    if len(reason) < MIN_REASON:
        raise bad(f"People have already bet on this, so say why you are changing it (at least {MIN_REASON} characters)")
    only_text = set(changes) == {"description"}
    is_clar = only_text and declared == "clarification"
    if declared == "clarification" and not only_text:
        raise bad("A date change can not be a clarification: it can change the answer. Mark it as a material change.")
    plan["class"] = "clarification" if is_clar else "material"
    if plan["class"] == "material":
        if any(e.get("class") == "material" for e in m.get("edits") or []):
            raise bad("This bet has already had a material change after people bet on it. Further edits can only be clarifications.", 409)
        until = now + int(economy_exit_h() * 3600 * 1000)
        if "closesAt" in changes:
            new_close, old_close = changes["closesAt"]["to"], changes["closesAt"]["from"]
            if new_close is not None and old_close is not None and new_close < old_close:
                if new_close < now + REACTION_MS:
                    raise bad("People who have bet need at least 24 hours to react, so the new closing time must be at least a day from now")
            if new_close is not None and new_close < until and (old_close is None or new_close < old_close):
                raise bad("The closing time can not be earlier than the end of the exit window (%d hours from now)" % round(economy_exit_h()))
        plan["exitUntil"] = until
        plan["note"] = ("This is a material change. Everyone involved is told, and for %d hours anyone who bet under the old rules may "
                        "withdraw that bet and get back exactly what they paid." % round(economy_exit_h()))
    else:
        plan["note"] = "This is a clarification (same meaning, clearer words). Everyone involved is told, and the history shows it as a clarification."
    return plan


def economy_exit_h():
    return economy.EDIT_EXIT_WINDOW_H


def edit_preview(user, m, body):
    plan = edit_plan(user, m, body)
    names = [users.get(uid)["username"] for uid in plan["affected"]][:12]
    return {"version": m.get("version", 1), "newVersion": m.get("version", 1) + 1, "class": plan["class"], "changes": plan["changes"],
            "participants": plan["participants"], "positions": plan["positions"], "notify": names, "notifyCount": len(plan["affected"]),
            "exitUntil": plan["exitUntil"], "exitHours": round(economy_exit_h()) if plan["exitUntil"] else 0, "note": plan["note"],
            "reasonRequired": plan["participants"] > 0, "minReason": MIN_REASON}


def edit_apply(user, m, body):
    key = None
    rid = body.get("requestId") if isinstance(body, dict) else None
    if rid is not None:
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", rid):
            raise bad("Invalid request id")
        key = f"edit:{user['id']}:{m['id']}:{rid}"
        seen = db().setdefault("idem", {}).get(key)
        if seen:
            return {**seen["result"], "duplicate": True}
    plan = edit_plan(user, m, body)
    now = plan["now"]
    version = m.get("version", 1) + 1
    entry = {"id": new_id(), "v": version, "t": now, "by": user["id"], "reason": plan["reason"], "class": plan["class"],
             "changes": plan["changes"], "participants": plan["participants"]}
    if "closesAt" in plan["changes"]:
        m["closesAt"] = plan["changes"]["closesAt"]["to"]
    if "description" in plan["changes"]:
        m["description"] = plan["changes"]["description"]["to"]
    m["version"] = version
    m.setdefault("edits", []).append(entry)
    if plan["class"] == "material":
        entry["exitUntil"] = plan["exitUntil"]
        m["exit"] = {"until": plan["exitUntil"], "version": version}
        for uid, toks in m["positions"].items():                               # everything held now was bet under the old rules
            if uid == user["id"]:
                continue                                                       # except the editor's own, who chose the change
            for pos in toks.values():
                if pos["shares"] > EPS:
                    pos["pre"] = {"sh": pos["shares"], "v": version - 1}
    what = " and ".join({"closesAt": "closing time", "description": "rules"}[k] for k in plan["changes"])
    label = {"material": "changed (material)", "clarification": "clarified", "no_participation": "edited"}[plan["class"]]
    for uid in plan["affected"]:
        u = db()["users"].get(uid)
        if u:
            users.log(u, "edit", 0, f"The {what} of \"{m['question'][:60]}\" were {label}" + (": you can withdraw your bet at cost for a while" if plan["class"] == "material" and uid in m["positions"] else ""), m["id"])
    result = {"version": version, "class": plan["class"], "notified": len(plan["affected"]), "entry": entry["id"], "exitUntil": plan["exitUntil"]}
    if key:
        memory = db().setdefault("idem", {})
        memory[key] = {"t": now, "fp": key, "result": result}
    return {**result, "duplicate": False}


def history(m, viewer):
    """The public record of every change: oldest first, then the current version."""
    out = [{"v": 1, "t": m["createdAt"], "by": users.public(users.get(m["creatorId"])), "kind": "created", "reason": "", "changes": {},
            "class": "created"}]
    for e in m.get("edits") or []:
        out.append({"v": e["v"], "t": e["t"], "by": users.public(users.get(e["by"])), "kind": "edit", "reason": e["reason"],
                    "class": e["class"], "changes": e["changes"], "participants": e["participants"], "exitUntil": e.get("exitUntil")})
    return {"version": m.get("version", 1), "edits": out, "exit": exit_info(m, viewer),
            "policy": {"exitHours": round(economy_exit_h()), "minReason": MIN_REASON, "reactionHours": 24}}


def withdraw(user, m, body):
    """During the exit window after a material change: take back a bet made under the old rules, at exactly what was paid."""
    _member_or_403(m, user)
    rid = body.get("requestId")
    key = None
    if rid is not None:
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", rid):
            raise bad("Invalid request id")
        key = f"withdraw:{user['id']}:{m['id']}:{rid}"
        seen = db().setdefault("idem", {}).get(key)
        if seen:
            return {**seen["result"], "duplicate": True}
    if m["status"] != "open":
        raise bad("This market is no longer open", 409)
    if not exit_open(m):
        raise bad("The exit window for this change has ended", 409)
    toks = m["positions"].get(user["id"], {})
    token = body.get("token")
    pos = toks.get(token) if isinstance(token, str) else None
    if not pos or not pos.get("pre") or pos["shares"] <= EPS:
        raise bad("You have no bet from before the change to withdraw", 404)
    shares = min(pos["pre"]["sh"], pos["shares"])
    basis = round2(pos["invested"] * (shares / pos["shares"])) if shares < pos["shares"] - EPS else round2(pos["invested"])
    i, side = int(token[1:]), token[0]
    m["q"] = lmsr.apply_trade(m["q"], i, side, -shares)
    users.credit(user, basis, "market.withdraw", ref=m["id"])
    if shares >= pos["shares"] - EPS:
        pos["shares"], pos["invested"] = 0.0, 0.0
    else:
        pos["shares"] -= shares
        pos["invested"] -= basis
    pos.pop("pre", None)
    label = token_label(m, token)
    users.log(user, "refund", basis, f"Withdrew at cost after the rules changed: {m['question']}", m["id"])
    if pos["shares"] <= EPS:
        del m["positions"][user["id"]][token]
        if not m["positions"][user["id"]]:
            del m["positions"][user["id"]]
    m["trades"].append({"t": now_ms(), "u": user["id"], "k": "withdraw", "token": token, "amount": basis, "shares": shares,
                        "price": basis / shares if shares else 0})
    del m["trades"][:-TRADES_MAX]
    m["history"].append({"t": now_ms(), "p": lmsr.prices(m["q"], m["b"])})
    del m["history"][1:-HIST_MAX]
    result = {"refunded": basis, "shares": shares, "label": label, "balance": user["balance"]}
    if key:
        db().setdefault("idem", {})[key] = {"t": now_ms(), "fp": key, "result": result}
    return {**result, "duplicate": False}
