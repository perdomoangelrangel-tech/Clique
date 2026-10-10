"""The definitions behind ranks, XP, weekly challenges and milestones, as data in one place.

Nothing else in the code has these numbers written into it. To change a threshold, an amount or a goal, change it here
(or scale everything at once with the REWARD_SCALE, XP_SCALE and RANK_XP_SCALE settings in economy.py). ECONOMY.md
explains the reasoning. All money is pretend money.

WHAT COUNTS. Everything below is driven by "qualifying actions", recorded by the server itself in backend/activity.py:
  polls     a bet on a poll with real money, a stake of at least economy.QUALIFY_MIN_STAKE
  casino    a finished casino round with real money, a stake of at least that much
  exchange  an accepted share trade of at least that much
  poker     being dealt into a hand of poker
  create    proposing a poll
  circle    creating or joining a circle
Practice (demo) play, rejected requests, looking at a page, loans, repayments, transfers and Store purchases never count.
"""
from . import economy

# ---- ranks -----------------------------------------------------------------------------------------------------------
TIERS = [("bronze", "Bronze"), ("silver", "Silver"), ("gold", "Gold"), ("platinum", "Platinum"), ("diamond", "Diamond"),
         ("master", "Master")]
ROMAN = {3: "III", 2: "II", 1: "I"}
# XP needed to reach each step, lowest first: Bronze III, II, I, then Silver III ... Diamond I, then Master (no divisions).
BASE_XP = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200, 4000, 5000, 6200, 7600, 9200, 11000]


_LEVELS = (None, None)                         # (the scale it was built with, the list): rebuilt only if the setting changes


def levels():
    """Every step of the ladder, lowest first, with the XP it takes (RANK_XP_SCALE applied)."""
    global _LEVELS
    if _LEVELS[0] == economy.RANK_XP_SCALE:
        return _LEVELS[1]
    out, i = [], 0
    for t, (key, name) in enumerate(TIERS):
        divs = [3, 2, 1] if key != "master" else [None]
        for d in divs:
            out.append({"index": i, "tierIndex": t, "tier": key, "name": name, "division": d,
                        "label": name if d is None else f"{name} {ROMAN[d]}", "xp": int(round(BASE_XP[i] * economy.RANK_XP_SCALE))})
            i += 1
    _LEVELS = (economy.RANK_XP_SCALE, out)
    return out


def rank_for(xp):
    """Where an XP total puts somebody: tier, division, label, the step they are on and the next one."""
    xp = max(0, int(xp))
    lv = levels()
    cur = lv[0]
    for step in lv:
        if xp >= step["xp"]:
            cur = step
        else:
            break
    nxt = lv[cur["index"] + 1] if cur["index"] + 1 < len(lv) else None
    out = {"index": cur["index"], "tier": cur["tier"], "tierIndex": cur["tierIndex"], "name": cur["name"], "division": cur["division"],
           "label": cur["label"], "xp": xp, "floor": cur["xp"], "next": nxt["xp"] if nxt else None,
           "nextLabel": nxt["label"] if nxt else None, "max": nxt is None}
    out["toNext"] = (nxt["xp"] - xp) if nxt else 0
    out["pct"] = 100 if not nxt else int(100 * (xp - cur["xp"]) / max(1, nxt["xp"] - cur["xp"]))
    return out


# ---- XP -------------------------------------------------------------------------------------------------------------
# "xp" is what one qualifying action is worth, "cap" how many of them are paid per calendar day (after that: nothing,
# so repeating the same thing cannot be farmed). XP_DAILY_CAP stops the sum of all of them. What you stake, win, lose or
# hold never changes the XP. Challenges and milestones pay XP too when they are claimed (see below).
XP_RULES = {
    "polls": {"xp": 5, "cap": 4, "text": "A bet on a poll with real money (once per poll per day)"},
    "casino": {"xp": 2, "cap": 10, "text": "A finished casino round with real money"},
    "exchange": {"xp": 3, "cap": 2, "text": "A share trade on the Exchange"},
    "poker": {"xp": 1, "cap": 6, "text": "Being dealt into a hand of poker"},
    "create": {"xp": 4, "cap": 2, "text": "Proposing a poll"},
}
XP_DAILY_CAP = 60
STEADY_WEEK_DAYS = 3          # active on this many different days in a week...
STEADY_WEEK_XP = 30           # ...earns this at the weekly close
# How many of each action may still add to the lifetime milestone counters in one calendar day.
COUNT_CAPS = {"polls": 10, "casino": 30, "exchange": 6, "poker": 10, "create": 3, "circle": 3}
# Which part of Clique an action belongs to, for "use several different features".
FEATURE_OF = {"polls": "polls", "casino": "casino", "exchange": "exchange", "poker": "poker", "create": "create", "circle": "circles"}
FEATURE_NAMES = {"polls": "polls", "casino": "the casino", "exchange": "the Exchange", "poker": "poker", "create": "proposing polls",
                 "circles": "circles"}
CASINO_GAMES = ("chicken", "blackjack", "roulette", "limbo", "coinflip", "war", "dice", "mines", "moles", "tower", "hilo", "wheel", "rps")


def xp_amount(x):
    return int(round(x * economy.XP_SCALE))


def money_cents(dollars):
    return int(round(dollars * 100 * economy.REWARD_SCALE))


# ---- weekly challenges ----------------------------------------------------------------------------------------------
# A week gets three challenges for the weekly account and three for the accumulated account. They are picked once, when the
# week is assigned, from the families below; a family appears at most once a week and its tier (the target and the reward) is
# fixed for that week. "fact" names what is counted (see activity.py). Rewards are dollars; "xp" is paid on claim.
FAMILIES = {
    "games": {"account": "weekly", "fact": "games", "title": "Game Sampler", "unit": "games",
              "desc": "Play {t} different casino games this week.", "tiers": [(3, 35), (4, 50), (5, 70)], "xp": 20,
              "href": "#/games", "cta": "Open the casino"},
    "polls": {"account": "weekly", "fact": "polls", "title": "Many Opinions", "unit": "polls",
              "desc": "Bet in {t} different polls this week.", "tiers": [(2, 30), (3, 40), (4, 55)], "xp": 20,
              "href": "#/", "cta": "Browse polls"},
    "days": {"account": "weekly", "fact": "days", "title": "Regular", "unit": "days",
             "desc": "Take part on {t} different days this week.", "tiers": [(3, 40), (4, 55), (5, 70)], "xp": 25,
             "href": "#/", "cta": "Pick something to play"},
    "maker": {"account": "weekly", "fact": "created", "title": "Poll Maker", "unit": "polls proposed",
              "desc": "Propose {t} poll this week.", "tiers": [(1, 35)], "xp": 20, "href": "#/create", "cta": "Propose a poll"},
    "stocks": {"account": "accumulated", "fact": "symbols", "title": "Market Watcher", "unit": "companies",
               "desc": "Trade shares of {t} different companies on the Exchange this week.", "tiers": [(2, 15), (3, 25)], "xp": 15,
               "href": "#/exchange", "cta": "Open the Exchange"},
    "features": {"account": "accumulated", "fact": "features", "title": "Cross-Training", "unit": "parts of Clique",
                 "desc": "Use {t} different parts of Clique this week: polls, the casino, the Exchange, poker, proposing a poll or joining a circle.",
                 "tiers": [(3, 20), (4, 30)], "xp": 15, "href": "#/", "cta": "Start somewhere"},
    "streak": {"account": "accumulated", "fact": "days", "title": "Show Up", "unit": "days",
               "desc": "Take part on {t} different days this week.", "tiers": [(4, 20), (5, 30), (6, 40)], "xp": 15,
               "href": "#/", "cta": "Pick something to play"},
    "cats": {"account": "accumulated", "fact": "cats", "title": "Well Read", "unit": "categories",
             "desc": "Bet in polls from {t} different categories this week.", "tiers": [(2, 15), (3, 25)], "xp": 15,
             "href": "#/", "cta": "Browse polls"},
}
FACT_RULES = {
    "games": "Counts finished casino rounds with real money, one game at a time (stake of at least {min}). Practice rounds do not count.",
    "polls": "Counts bets on polls (stake of at least {min}). Betting again in the same poll does not add to it.",
    "days": "A day counts when you do at least one qualifying thing: a poll bet or casino round of {min} or more, a share trade, a poker hand or proposing a poll.",
    "created": "Counts polls you propose (the first 3 each day count).",
    "symbols": "Counts accepted share trades of {min} or more, once per company (buying or selling).",
    "features": "Counts each part of Clique you use with a qualifying action: polls, the casino, the Exchange, poker, proposing a poll, joining a circle.",
    "cats": "Counts the category of every poll you bet {min} or more in.",
}
POOLS = {"weekly": ("games", "polls", "days", "maker"), "accumulated": ("stocks", "features", "streak", "cats")}
PER_ACCOUNT_CLASSIC = 2                       # two of the general families above, plus the two game-specific ones below, for each account
FACT_LIMITS = {"games": 20, "polls": 60, "days": 7, "cats": 12, "symbols": 12, "features": 6}



# ---- goals about one particular game --------------------------------------------------------------------------------
# For every casino game: what it is called, what its rounds are called, and what a round can be measured by.
#   rounds  how many real-money rounds you finished           wins  how many of them ended in a profit
#   best    the biggest multiplier you reached in one round    won   the profit of winning rounds added up (capped per round)
# All of them need a real-money stake of at least economy.QUALIFY_MIN_STAKE. Only a round that was FINISHED counts, "best" needs a win, and
# "rounds", "wins" and "won" stop at the daily cap for casino rounds (COUNT_CAPS). Poker only has "rounds" (hands dealt), and only as a milestone.
GAME_INFO = {
    "chicken": ("Chicken", "rounds"), "blackjack": ("Blackjack", "hands"), "roulette": ("Roulette", "spins"), "limbo": ("Limbo", "rounds"),
    "coinflip": ("Coinflip", "rounds"), "war": ("War", "hands"), "dice": ("Dice", "rolls"), "mines": ("Mines", "rounds"),
    "moles": ("Moles", "rounds"), "tower": ("Tower", "rounds"), "hilo": ("Hi-Lo", "rounds"), "wheel": ("Wheel", "spins"),
    "rps": ("Rock Paper Scissors", "rounds"),
}
# The multiplier goals only make sense for games where the multiplier is yours to push. (milestone targets, weekly challenge targets.)
# Every target is a multiplier the game can really pay: Coinflip pays 1.98, 3.96, 7.92, 15.84... (so 3, 7 and 15 are two, three and four flips in a row),
# Rock Paper Scissors 1.96, 3.92, 7.84, 15.68... the same way, and the Wheel's best segment is 24×.
GAME_BEST = {
    "chicken": ([3, 10, 50], [2, 3, 5]), "tower": ([3, 10, 40], [2, 3, 5]), "mines": ([3, 10, 40], [2, 3, 5]), "moles": ([3, 10, 40], [2, 3, 5]),
    "limbo": ([5, 20, 100], [3, 5, 10]), "coinflip": ([3, 15, 60], [3, 7, 15]), "hilo": ([3, 10, 50], [2, 3, 5]), "rps": ([3, 15, 60], [3, 7, 15]),
    "wheel": ([3, 10, 24], [3, 5, 10]), "dice": ([5, 20, 100], [3, 5, 10]),
}
# The one "signature" goal each game gets as a milestone, next to "play N rounds": chicken is about earning, the card and table games about
# winning, everything else about the multiplier.
SIGNATURE = {g: ("won" if g == "chicken" else "wins" if g in ("blackjack", "roulette", "war") else "best") for g in GAME_INFO}
PLAY_TIERS = {"hands": [(25, 5, 5), (100, 15, 10), (500, 40, 20)], "spins": [(25, 5, 5), (100, 15, 10), (500, 40, 20)]}
PLAY_TIERS_DEFAULT = [(10, 5, 5), (50, 15, 10), (200, 40, 20)]
WINS_TIERS = [(10, 10, 10), (50, 30, 20), (200, 90, 40)]
WON_TIERS = [(50, 10, 10), (250, 40, 20), (1000, 120, 40)]
BEST_MONEY = [(10, 10), (30, 20), (100, 40)]                    # (money, xp) for the three multiplier tiers

# Weekly challenge targets: (target, reward in dollars for the weekly account). The accumulated account pays ACCOUNT_FACTOR of it, because that
# money is kept while weekly chips are reset every Monday.
WEEKLY_GAME_TARGETS = {"rounds": [(8, 30), (12, 40), (16, 50)], "wins": [(3, 30), (5, 40), (8, 60)], "won": [(20, 30), (35, 40), (50, 60)],
                       "best": [(None, 30), (None, 40), (None, 60)]}
ACCOUNT_FACTOR = {"weekly": 1.0, "accumulated": 0.5}
GAME_FAMILIES = {
    "play": {"account": "weekly", "metric": "rounds", "xp": 15, "title": "{g} Regular", "desc": "Play {t} {unit} of {g} this week.",
             "rule": "Counts finished rounds of {g} played with real money (a stake of at least {min}). Practice rounds do not count."},
    "mult": {"account": "weekly", "metric": "best", "xp": 15, "title": "{g} High Flyer", "desc": "Reach a multiplier of {t}× in a single round of {g} this week.",
             "rule": "Counts the multiplier of a {g} round you finish and win with real money (a stake of at least {min}). Only the multiplier matters, never how much you staked."},
    "wins": {"account": "accumulated", "metric": "wins", "xp": 15, "title": "{g} Winner", "desc": "Win {t} {unit} of {g} this week.",
             "rule": "Counts {g} rounds that ended in a profit, played with real money (a stake of at least {min}). The first 30 casino rounds each day count."},
    "earn": {"account": "accumulated", "metric": "won", "xp": 15, "title": "{g} Earner", "desc": "Win ${t} in {g} this week.",
             "rule": "Adds up the profit of each winning {g} round, up to {cap} per round, so a huge stake does not count for more (a stake of at least {min}). Losses and practice rounds do not count."},
}
GAME_POOLS = {"weekly": ("play", "mult"), "accumulated": ("wins", "earn")}
METRIC_KIND = {"rounds": "count", "wins": "count", "best": "mult", "won": "money"}


def games_for(metric):
    """The games a challenge about `metric` can be set in."""
    return [g for g in GAME_INFO if metric != "best" or g in GAME_BEST]


def weekly_targets(game, metric):
    """[(target, reward dollars)] for a weekly challenge about `game`."""
    if metric == "best":
        return [(t, money) for t, (_, money) in zip(GAME_BEST[game][1], WEEKLY_GAME_TARGETS["best"])]
    return list(WEEKLY_GAME_TARGETS[metric])


def _num(x):
    return int(x) if float(x).is_integer() else x


def game_milestones():
    """The per-game milestones, made from the tables above: play N rounds, and the game's signature goal."""
    out = []
    for gid, (name, unit) in GAME_INFO.items():
        out.append({"id": f"{gid}_play", "group": "game", "game": gid, "kind": "count", "title": f"{name} Regular", "desc": f"Finish rounds of {name} with real money.",
                    "metric": f"rounds:{gid}", "unit": unit, "href": f"#/games/{gid}", "tiers": PLAY_TIERS.get(unit, PLAY_TIERS_DEFAULT)})
        sig = SIGNATURE[gid]
        if sig == "best":
            out.append({"id": f"{gid}_best", "group": "game", "game": gid, "kind": "mult", "title": f"{name} High Flyer", "desc": f"Reach a big multiplier in a single round of {name}.",
                        "metric": f"best:{gid}", "unit": "×", "href": f"#/games/{gid}", "tiers": [(t, m, x) for t, (m, x) in zip(GAME_BEST[gid][0], BEST_MONEY)]})
        elif sig == "wins":
            out.append({"id": f"{gid}_wins", "group": "game", "game": gid, "kind": "count", "title": f"{name} Winner", "desc": f"Win rounds of {name} with real money.",
                        "metric": f"wins:{gid}", "unit": "wins", "href": f"#/games/{gid}", "tiers": WINS_TIERS})
        else:
            out.append({"id": f"{gid}_won", "group": "game", "game": gid, "kind": "money", "title": f"{name} Earner",
                        "desc": f"Win money in {name}: the profit of each winning round counts, up to ${economy.GAME_WIN_CREDIT_CAP:,.0f} a round.",
                        "metric": f"won:{gid}", "unit": "won", "href": f"#/games/{gid}", "tiers": WON_TIERS})
    out.append({"id": "poker_play", "group": "game", "game": "poker", "kind": "count", "title": "Poker Regular", "desc": "Be dealt into hands of poker.",
                "metric": "rounds:poker", "unit": "hands", "href": "#/poker", "tiers": [(10, 5, 5), (100, 15, 10), (500, 40, 20)]})
    return out

# ---- milestones -----------------------------------------------------------------------------------------------------
# Lifetime goals. Every tier pays money into the ACCUMULATED account (and XP) once, when claimed. They never reset.
# The rank milestones pay money only, so reaching a rank can never feed more XP back into the rank (no loop).
MILESTONES = [
    {"id": "predictor", "title": "Predictor", "desc": "Place bets on polls.", "metric": "market_bets", "unit": "bets", "href": "#/",
     "tiers": [(1, 10, 10), (10, 25, 20), (50, 75, 40), (200, 200, 80)]},
    {"id": "house_guest", "title": "House Guest", "desc": "Finish casino rounds.", "metric": "casino_rounds", "unit": "rounds", "href": "#/games",
     "tiers": [(1, 10, 10), (25, 25, 20), (150, 75, 40), (600, 200, 80)]},
    {"id": "sampler", "title": "Game Sampler", "desc": "Try different casino games.", "metric": "games_tried", "unit": "games", "href": "#/games",
     "tiers": [(3, 20, 15), (7, 50, 30), (13, 150, 60)]},
    {"id": "regular", "title": "Regular", "desc": "Take part in different weeks.", "metric": "weeks_active", "unit": "weeks", "href": "#/",
     "tiers": [(1, 15, 10), (4, 50, 30), (12, 150, 60), (26, 400, 120)]},
    {"id": "challenger", "title": "Challenger", "desc": "Complete weekly challenges.", "metric": "challenges_done", "unit": "challenges", "href": "#/challenges",
     "tiers": [(1, 15, 10), (5, 50, 30), (20, 150, 60), (50, 400, 120)]},
    {"id": "explorer", "title": "Explorer", "desc": "Use different parts of Clique.", "metric": "features_used", "unit": "parts", "href": "#/",
     "tiers": [(3, 20, 15), (5, 50, 30), (6, 100, 50)]},
    {"id": "trader", "title": "Trader", "desc": "Trade shares on the Exchange.", "metric": "stock_trades", "unit": "trades", "href": "#/exchange",
     "tiers": [(1, 10, 10), (10, 40, 20), (50, 120, 40)]},
    {"id": "bookmaker", "title": "Poll Maker", "desc": "Propose polls.", "metric": "polls_created", "unit": "polls", "href": "#/create",
     "tiers": [(1, 15, 10), (5, 50, 25), (20, 150, 50)]},
    {"id": "joiner", "title": "Part of a Circle", "desc": "Create or join a circle.", "metric": "circles_joined", "unit": "circles", "href": "#/circles",
     "tiers": [(1, 10, 10)]},
    {"id": "climber", "title": "Climber", "desc": "Reach higher ranks.", "metric": "rank_tier", "unit": "rank", "href": "#/progress",
     "tiers": [(1, 50, 0), (2, 100, 0), (3, 250, 0), (4, 500, 0), (5, 1000, 0)]},
    {"id": "dedicated", "title": "Dedicated", "desc": "Take part on different days, over time.", "metric": "days_active", "unit": "days", "href": "#/",
     "tiers": [(7, 30, 15), (30, 100, 40), (100, 300, 100)]},
]
RANK_TIER_NAMES = {1: "Silver", 2: "Gold", 3: "Platinum", 4: "Diamond", 5: "Master"}
for _m in MILESTONES:
    _m.setdefault("group", "general")
    _m.setdefault("kind", "count")
MILESTONES += game_milestones()


def milestone_tiers():
    """Every milestone tier flattened: [{id, milestone, tier number, target, money_c, xp}]. The id is stable ("predictor:2")."""
    out = []
    for m in MILESTONES:
        for n, (target, money, xp) in enumerate(m["tiers"], start=1):
            out.append({"id": f"{m['id']}:{n}", "milestone": m["id"], "tier": n, "target": target, "money_c": money_cents(money),
                        "xp": xp_amount(xp), "metric": m["metric"]})
    return out
