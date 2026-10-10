"""The one place a qualifying action is recorded. Called by the server's own code, after an action has really happened.

Every XP award, challenge fact and milestone counter in Clique comes through record(). It is called from: a poll bet that was
accepted (markets.trade), a casino round that finished (games._record), a share trade that went through (exchange.trade), a
poker hand being dealt (poker._start_hand), a poll being proposed (markets.create) and a circle being created or joined
(circles). Nothing a browser sends is ever used as a count, so there is nothing to forge, and a rejected request never reaches
this code at all.

What does NOT come through here, on purpose: loans and repayments, transfers between friends, Store purchases, weekly refills,
rewards of any kind, and practice (demo) play. See rules.py for what each kind is worth and what is capped.

record() is safe to call twice for the same action: each action has an id and is counted once.
"""
from . import challenges, economy, milestones, progress, rules
from .util import day_key, now_ms, week_key

STAKE_KINDS = ("polls", "casino", "exchange")


def safe_record(user, kind, ref, **kw):
    """record() for the places that call it in the middle of something else (a bet that has just been placed). Progression must
    never be able to break a bet, a round or a trade, so a problem here is printed and swallowed."""
    try:
        return record(user, kind, ref, **kw)
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def record(user, kind, ref, *, now=None, amount=None, game=None, market=None, category=None, symbol=None, payout=None, mult=None):
    """Records one qualifying action. Returns a small summary (what was counted, XP given) or None if it did not qualify."""
    if not economy.GOALS_ENABLED or user.get("isDemo") or kind not in rules.COUNT_CAPS:
        return None
    if kind in STAKE_KINDS and (amount is None or amount + 1e-9 < economy.QUALIFY_MIN_STAKE):
        return None                                                    # too small to count (or no real money at stake)
    if kind == "casino" and game not in rules.CASINO_GAMES:
        return None
    now = now_ms() if now is None else now
    g = progress.state(user)
    if not progress.remember(g, f"act:{kind}:{ref}", now):
        return None                                                    # this very action was already recorded
    day, week = day_key(now), week_key(now)
    d = g["day"]
    if d["k"] != day:
        d.update(k=day, n={}, xn={}, mk=[], xp=0)
    counted = d["n"].get(kind, 0) < rules.COUNT_CAPS[kind]
    if kind == "polls":
        counted = counted and market not in d["mk"]                    # a poll counts once a day however many times you buy in it
    out = {"kind": kind, "counted": counted, "xp": 0}

    # ---- the person took part today, and this week
    if g["lastDay"] != day:
        g["lastDay"] = day
        milestones.bump(user, "days_active")
    if g["lastWeek"] != week:
        g["lastWeek"] = week
        milestones.bump(user, "weeks_active")
    feature = rules.FEATURE_OF[kind]
    if feature not in g["features"]:
        g["features"].append(feature)
    challenges.add_fact(user, week, "days", day)
    challenges.add_fact(user, week, "features", feature)

    # ---- what exactly they did
    if kind == "casino":
        challenges.add_fact(user, week, "games", game)
        if game not in g["games"]:
            g["games"].append(game)
        profit_c = max(0, int(round(((payout or 0) - amount) * 100)))              # what the round won (0 for a loss or a push)
        credit_c = min(profit_c, int(round(economy.GAME_WIN_CREDIT_CAP * 100)))     # one round never counts for more than the cap
        best_x100 = int(round(mult * 100)) if (mult and profit_c > 0) else 0       # only a round that WON has a multiplier worth counting
        out["game"] = {"profit_c": profit_c, "credit_c": credit_c, "best_x100": best_x100}
        for box in (g["gm"].setdefault(game, {}), challenges.game_fact(user, week, game)):
            if counted:
                box["rounds"] = box.get("rounds", 0) + 1
                if profit_c > 0:
                    box["wins"] = box.get("wins", 0) + 1
                    box["won_c"] = box.get("won_c", 0) + credit_c
            if best_x100 > box.get("best_x100", 0):
                box["best_x100"] = best_x100
    elif kind == "polls":
        if market:
            challenges.add_fact(user, week, "polls", market)
        if category:
            challenges.add_fact(user, week, "cats", category)
    elif kind == "exchange" and symbol:
        challenges.add_fact(user, week, "symbols", symbol)
    elif kind == "create" and counted:
        challenges.add_fact(user, week, "created", 1)
    elif kind == "poker" and counted:
        box = g["gm"].setdefault("poker", {})
        box["rounds"] = box.get("rounds", 0) + 1

    # ---- the counters that milestones watch, and XP: both stop at their daily caps
    if counted:
        d["n"][kind] = d["n"].get(kind, 0) + 1
        if kind == "polls":
            d["mk"].append(market)
        counter = {"polls": "market_bets", "casino": "casino_rounds", "exchange": "stock_trades", "create": "polls_created"}.get(kind)
        if counter:
            milestones.bump(user, counter)
        if kind == "circle":
            milestones.bump(user, "circles_joined")
        rule = rules.XP_RULES.get(kind)
        if rule and d["xn"].get(kind, 0) < rule["cap"] and d["xp"] < rules.XP_DAILY_CAP:
            amt = min(rules.xp_amount(rule["xp"]), rules.XP_DAILY_CAP - d["xp"])
            if progress.grant(user, amt, kind, f"act:{kind}:{ref}", now, label=rule["text"]):
                d["xn"][kind] = d["xn"].get(kind, 0) + 1
                d["xp"] += amt
                out["xp"] = amt
    challenges.evaluate(user, week, now)
    milestones.evaluate(user, now)
    return out
