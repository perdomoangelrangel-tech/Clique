"""Casino games. The server does all the dealing and rolling (with a secure random source)
and all the money movement, so nobody can cheat from their browser."""
import math

from . import activity, config, ledger, users
from .store import db
from .util import bad, new_id, now_ms, parse_money, rand_below, rand_unit, round2, shuffle

LIMBO_RTP = 0.99
CHICKEN_RTP = 0.97
LIMBO_MAX = 1_000_000.0

REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


# ---- demo bets ---------------------------------------------------------------------
# A practice wallet with its own balance, history and round state. Every game takes "the account
# to play with", so a demo round is the same code on a different dict: it can never touch the
# real balance, the weekly stats or the big-wins feed.

DEMO_START = 1000.0


def demo_account(user):
    d = user.setdefault("demo", {})
    if "balance" not in d:
        d.update({"balance": DEMO_START, "stats": {}, "activity": [], "history": []})
    d["id"] = user["id"] + ":demo"
    d["username"] = user["username"]
    d["isDemo"] = True
    return d


def accum_account(user):
    """The ACCUMULATED account, dressed as a game wallet: what a casino round plays with when the person chooses it. It is a view on the real
    account (every chip goes through the ledger, see users.debit/credit), with its own round state, history and statistics, kept apart from
    the weekly ones: rounds played this way never count for the weekly week (standings, awards, the weekly minimum). They do count for XP,
    challenges and milestones, as any other real-chips round does."""
    a = user.setdefault("accGame", {"history": [], "stats": {}, "activity": []})
    return {"id": user["id"] + ":acc", "username": user["username"], "balance": ledger.balance(user, "accumulated"), "isAcc": True, "_owner": user,
            "history": a["history"], "stats": a["stats"], "activity": a["activity"]}


def account_for(user, demo, acct=None):
    """The wallet a round is played with: the practice one (demo), the accumulated account (acct == "accumulated"), or the weekly one."""
    if demo is True:
        return demo_account(user)
    if acct == "accumulated":
        return accum_account(user)
    if acct not in (None, "weekly"):
        raise bad("Choose the weekly account or the accumulated account", code="invalid_account")
    return user


def demo_reset(user):
    d = demo_account(user)
    db()["games"].pop(d["id"], None)           # any demo round in progress goes too
    d.update({"balance": DEMO_START, "stats": {}, "activity": [], "history": []})
    return d


def _bet(user, value, field="Bet"):
    amount = round2(parse_money(value, field))
    if amount < config.MIN_BET - 1e-9:
        raise bad(f"The minimum bet is ${config.MIN_BET:.2f}", code="bet_below_minimum")
    if amount > user["balance"] + 1e-9:
        raise bad("Not enough funds", code="insufficient_funds")
    return amount


GAME_TITLES = {"hilo": "Hi-Lo", "rps": "Rock Paper Scissors"}          # ids whose plain capitalised form is not the name


def game_title(game):
    return GAME_TITLES.get(game) or game.capitalize()


def _record(user, game, bet, payout, mult, detail=None):
    """Bookkeeping once a round is over: weekly stats, history, big-win feed."""
    profit = round2(payout - bet)
    users.stat_add(user, "gameWagered", bet)
    users.stat_add(user, "gamePnl", profit)
    users.stat_add(user, "gamesPlayed")
    if profit > 0:
        users.stat_max(user, "biggestGameWin", profit)
        if mult:
            users.stat_best(user, "bestMult", mult, game_title(game))
    entry = {"id": new_id(), "t": now_ms(), "game": game, "bet": bet, "payout": payout,
             "mult": mult, "profit": profit, "detail": detail or ""}
    user["history"].insert(0, entry)
    del user["history"][100:]
    users.log(user, "game", profit, f"{game_title(game)}: {'won' if profit > 0 else 'lost' if profit < 0 else 'push'}")
    activity.safe_record(user.get("_owner", user), "casino", entry["id"], amount=bet, game=game, payout=payout, mult=mult)      # progression: real-money rounds only (the demo wallet is ignored there; the accumulated one counts for the person)
    if profit > 0 and (mult or 0) >= 2 and not user.get("isDemo"):      # practice wins don't make the board
        feed = db()["feed"]
        feed.insert(0, {"t": now_ms(), "user": user["username"], "game": game, "mult": mult, "profit": profit})
        del feed[40:]


# ---- Limbo -------------------------------------------------------------------------

def limbo_roll_c():
    """One Limbo result, in cents of a multiplier."""
    c = int(math.floor(LIMBO_RTP / rand_unit() * 100))
    return max(100, min(c, int(LIMBO_MAX * 100)))


def limbo(user, body):
    amount = _bet(user, body.get("amount"))
    target = parse_money(body.get("target"), "Target")
    target_c = int(round(target * 100))
    if target_c < 101 or target_c > int(LIMBO_MAX * 100):
        raise bad("Target must be between 1.01x and 1,000,000x", code="invalid_target")
    users.debit(user, amount)
    result_c = limbo_roll_c()
    win = result_c >= target_c
    target = target_c / 100
    payout = round2(amount * target) if win else 0.0
    if win:
        users.credit(user, payout)
        users.stat_max(user, "limboBest", target)
    _record(user, "limbo", amount, payout, target if win else None, f"target {target:.2f}x, rolled {result_c / 100:.2f}x")
    return {"result": result_c / 100, "target": target, "win": win, "payout": payout,
            "chance": min(98.0, LIMBO_RTP / target * 100), "balance": user["balance"]}


# ---- Roulette ----------------------------------------------------------------------

def _roulette_wins(kind, value, n):
    if kind == "straight":
        return n == value, 36
    if n == 0:
        return False, 0
    table = {
        "red": (n in REDS, 2), "black": (n not in REDS, 2),
        "odd": (n % 2 == 1, 2), "even": (n % 2 == 0, 2),
        "low": (1 <= n <= 18, 2), "high": (19 <= n <= 36, 2),
    }
    if kind in table:
        return table[kind]
    if kind == "dozen":
        return (value - 1) * 12 < n <= value * 12, 3
    if kind == "column":
        return n % 3 == (value % 3), 3
    return False, 0


def roulette(user, body):
    bets = body.get("bets")
    if not isinstance(bets, list) or not bets:
        raise bad("Place at least one chip", code="no_bets")
    if len(bets) > 120:
        raise bad("Too many bets", code="too_many_bets")
    clean, total = [], 0.0
    for b in bets:
        if not isinstance(b, dict):
            raise bad("Invalid bet", code="invalid_bet")
        kind = b.get("type")
        value = b.get("value")
        if kind == "straight":
            if not isinstance(value, int) or not 0 <= value <= 36:
                raise bad("Invalid number", code="invalid_bet")
        elif kind in ("dozen", "column"):
            if value not in (1, 2, 3):
                raise bad("Invalid bet", code="invalid_bet")
        elif kind not in ("red", "black", "odd", "even", "low", "high"):
            raise bad("Invalid bet", code="invalid_bet")
        amount = round2(parse_money(b.get("amount"), "Chip"))
        if amount < config.MIN_BET - 1e-9:
            raise bad(f"The minimum chip is ${config.MIN_BET:.2f}", code="bet_below_minimum")
        clean.append((kind, value, amount))
        total += amount
    total = round2(total)
    if total > user["balance"] + 1e-9:
        raise bad("Not enough funds", code="insufficient_funds")
    users.debit(user, total)
    n = rand_below(37)
    payout, wins = 0.0, []
    for kind, value, amount in clean:
        ok, mult = _roulette_wins(kind, value, n)
        if ok:
            payout += amount * mult
            wins.append({"type": kind, "value": value, "amount": amount, "pays": round2(amount * mult)})
    payout = round2(payout)
    if payout:
        users.credit(user, payout)
    users.stat_add(user, "roulettePnl", round2(payout - total))
    color = "green" if n == 0 else ("red" if n in REDS else "black")
    mult = round2(payout / total) if payout else None
    _record(user, "roulette", total, payout, mult, f"number {n}")
    return {"number": n, "color": color, "payout": payout, "total": total, "wins": wins,
            "balance": user["balance"]}


# ---- Blackjack ---------------------------------------------------------------------

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]


def _card_value(r):
    return 11 if r == "A" else 10 if r in ("10", "J", "Q", "K") else int(r)


def hand_value(cards):
    total = sum(_card_value(c["r"]) for c in cards)
    aces = sum(1 for c in cards if c["r"] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def _is_blackjack(cards):
    return len(cards) == 2 and hand_value(cards)[0] == 21


def _games(user):
    return db()["games"].setdefault(user["id"], {})


def escrow(uid):
    """Stakes sitting in rounds that have started but not finished (they have left the weekly account, and come back
    as a payout when the round ends). They count as the player's own money, at what was staked, so a week that closes
    mid-round neither costs nor gains them anything."""
    total = 0.0
    for name, st in (db()["games"].get(uid) or {}).items():
        if isinstance(st, dict):
            total += st.get("totalBet", 0) if name == "blackjack" else st.get("bet", 0)
    return round2(total)


def _draw(st):
    return st["shoe"].pop()


def _bj_json(st, user):
    done = st["phase"] == "done"
    dealer = st["dealer"] if done else [st["dealer"][0], {"hidden": True}]
    hands = []
    for i, h in enumerate(st["hands"]):
        total, soft = hand_value(h["cards"])
        hands.append({"cards": h["cards"], "bet": h["bet"], "total": total, "soft": soft,
                      "status": h["status"], "result": h.get("result"), "payout": h.get("payout", 0),
                      "doubled": h.get("doubled", False), "blackjack": h.get("blackjack", False)})
    out = {"id": st["id"], "phase": st["phase"], "dealer": dealer, "hands": hands, "active": st["active"],
           "dealerTotal": hand_value(st["dealer"])[0] if done else hand_value(st["dealer"][:1])[0],
           "balance": user["balance"], "totalBet": st["totalBet"], "payout": st.get("payout", 0)}
    if not done:
        h = st["hands"][st["active"]]
        two = len(h["cards"]) == 2
        out["canDouble"] = two and user["balance"] + 1e-9 >= h["bet"]
        out["canSplit"] = (two and len(st["hands"]) == 1 and user["balance"] + 1e-9 >= h["bet"]
                           and _card_value(h["cards"][0]["r"]) == _card_value(h["cards"][1]["r"]))
    return out


def _bj_finish(user, st):
    """Dealer plays out, all hands are settled and paid."""
    live = [h for h in st["hands"] if h["status"] != "bust" and not h.get("blackjack")]
    dealer_bj = _is_blackjack(st["dealer"])
    if live and not dealer_bj:
        while hand_value(st["dealer"])[0] < 17:
            st["dealer"].append(_draw(st))
    d_total = hand_value(st["dealer"])[0]
    total_payout = 0.0
    wins = 0
    for h in st["hands"]:
        total = hand_value(h["cards"])[0]
        if h.get("blackjack"):
            h["result"], h["payout"] = ("push", h["bet"]) if dealer_bj else ("blackjack", round2(h["bet"] * 2.5))
        elif h["status"] == "bust":
            h["result"], h["payout"] = "bust", 0.0
        elif dealer_bj:
            h["result"], h["payout"] = "lose", 0.0
        elif d_total > 21 or total > d_total:
            h["result"], h["payout"] = "win", round2(h["bet"] * 2)
        elif total == d_total:
            h["result"], h["payout"] = "push", h["bet"]
        else:
            h["result"], h["payout"] = "lose", 0.0
        total_payout += h["payout"]
        wins += 1 if h["result"] in ("win", "blackjack") else 0
    total_payout = round2(total_payout)
    st["phase"], st["payout"] = "done", total_payout
    if total_payout:
        users.credit(user, total_payout)
    if wins:
        users.stat_add(user, "bjWins", wins)
    mult = round2(total_payout / st["totalBet"]) if total_payout > st["totalBet"] else None
    _record(user, "blackjack", st["totalBet"], total_payout, mult,
            ", ".join(h["result"] for h in st["hands"]))
    _games(user).pop("blackjack", None)


def _bj_advance(user, st):
    st["active"] += 1
    while st["active"] < len(st["hands"]) and st["hands"][st["active"]]["status"] != "playing":
        st["active"] += 1
    if st["active"] >= len(st["hands"]):
        st["active"] = len(st["hands"]) - 1
        _bj_finish(user, st)


def blackjack_deal(user, body):
    g = _games(user)
    if "blackjack" in g:
        raise bad("Finish your current hand first", code="round_in_progress")
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    shoe = [{"r": r, "s": s} for _ in range(6) for r in RANKS for s in SUITS]
    shuffle(shoe)
    st = {"id": new_id(), "shoe": shoe, "phase": "player", "active": 0, "totalBet": amount, "dealer": [],
          "hands": [{"cards": [], "bet": amount, "status": "playing"}]}
    p1, d1, p2, d2 = _draw(st), _draw(st), _draw(st), _draw(st)
    st["hands"][0]["cards"] = [p1, p2]
    st["dealer"] = [d1, d2]
    g["blackjack"] = st
    player_bj = _is_blackjack([p1, p2])
    if player_bj:
        st["hands"][0]["blackjack"] = True
    up = _card_value(d1["r"])
    if (up >= 10 and _is_blackjack(st["dealer"])) or player_bj:
        _bj_finish(user, st)
    return _bj_json(st, user)


def blackjack_action(user, body):
    st = _games(user).get("blackjack")
    if not st or st["phase"] != "player":
        raise bad("No hand in progress", code="no_round_in_progress")
    action = body.get("action")
    h = st["hands"][st["active"]]
    if action == "hit":
        h["cards"].append(_draw(st))
        total = hand_value(h["cards"])[0]
        if total > 21:
            h["status"] = "bust"
            _bj_advance(user, st)
        elif total == 21:
            h["status"] = "stand"
            _bj_advance(user, st)
    elif action == "stand":
        h["status"] = "stand"
        _bj_advance(user, st)
    elif action == "double":
        if len(h["cards"]) != 2:
            raise bad("You can only double on your first two cards", code="invalid_move")
        users.debit(user, h["bet"])
        st["totalBet"] = round2(st["totalBet"] + h["bet"])
        h["bet"] = round2(h["bet"] * 2)
        h["doubled"] = True
        h["cards"].append(_draw(st))
        h["status"] = "bust" if hand_value(h["cards"])[0] > 21 else "stand"
        _bj_advance(user, st)
    elif action == "split":
        if len(st["hands"]) != 1 or len(h["cards"]) != 2 or \
                _card_value(h["cards"][0]["r"]) != _card_value(h["cards"][1]["r"]):
            raise bad("You can't split this hand", code="invalid_move")
        users.debit(user, h["bet"])
        st["totalBet"] = round2(st["totalBet"] + h["bet"])
        c1, c2 = h["cards"]
        aces = c1["r"] == "A"
        h1 = {"cards": [c1, _draw(st)], "bet": h["bet"], "status": "playing"}
        h2 = {"cards": [c2, _draw(st)], "bet": h["bet"], "status": "playing"}
        st["hands"] = [h1, h2]
        st["active"] = 0
        for hh in (h1, h2):
            if aces or hand_value(hh["cards"])[0] == 21:
                hh["status"] = "stand"
        if h1["status"] != "playing":
            st["active"] = -1
            _bj_advance(user, st)
    else:
        raise bad("Unknown action", code="invalid_action")
    return _bj_json(st, user)


# ---- Chicken -----------------------------------------------------------------------

CHICKEN = {
    "easy": {"p": 0.92, "lanes": 24},
    "medium": {"p": 0.85, "lanes": 20},
    "hard": {"p": 0.75, "lanes": 18},
    "hardcore": {"p": 0.60, "lanes": 15},
}


def chicken_mult(difficulty, step):
    p = CHICKEN[difficulty]["p"]
    return math.floor(CHICKEN_RTP / (p ** step) * 100) / 100 if step > 0 else 1.0


def chicken_table(difficulty):
    return [chicken_mult(difficulty, k) for k in range(0, CHICKEN[difficulty]["lanes"] + 1)]


def _chicken_json(st, user, extra=None):
    d = st["difficulty"]
    out = {"id": st["id"], "bet": st["bet"], "difficulty": d, "step": st["step"],
           "lanes": CHICKEN[d]["lanes"], "mults": chicken_table(d), "status": st["status"],
           "mult": chicken_mult(d, st["step"]), "payoutNow": round2(st["bet"] * chicken_mult(d, st["step"])),
           "balance": user["balance"], "chance": CHICKEN[d]["p"]}
    if extra:
        out.update(extra)
    return out


def chicken_state(user):
    st = _games(user).get("chicken")
    return _chicken_json(st, user) if st else None


def chicken_start(user, body):
    g = _games(user)
    if "chicken" in g:
        raise bad("You already have a chicken on the road", code="round_in_progress")
    difficulty = body.get("difficulty", "medium")
    if difficulty not in CHICKEN:
        raise bad("Unknown difficulty", code="invalid_game_option")
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    st = {"id": new_id(), "bet": amount, "difficulty": difficulty, "step": 0, "status": "active"}
    g["chicken"] = st
    return _chicken_json(st, user)


def _chicken_cash(user, st, auto=False):
    payout = round2(st["bet"] * chicken_mult(st["difficulty"], st["step"]))
    users.credit(user, payout)
    mult = chicken_mult(st["difficulty"], st["step"])
    users.stat_max(user, "chickenBest", mult)
    _record(user, "chicken", st["bet"], payout, mult, f"{st['difficulty']}, {st['step']} lanes")
    _games(user).pop("chicken", None)
    st["status"] = "cashed"
    return payout


def chicken_step(user):
    st = _games(user).get("chicken")
    if not st or st["status"] != "active":
        raise bad("Start a game first", code="no_round_in_progress")
    cfg = CHICKEN[st["difficulty"]]
    if rand_unit() > cfg["p"]:
        st["status"] = "dead"
        _record(user, "chicken", st["bet"], 0.0, None, f"{st['difficulty']}, hit on lane {st['step'] + 1}")
        _games(user).pop("chicken", None)
        return _chicken_json(st, user, {"crashed": True, "payout": 0.0})
    st["step"] += 1
    if st["step"] >= cfg["lanes"]:
        payout = _chicken_cash(user, st, auto=True)
        return _chicken_json(st, user, {"crashed": False, "payout": payout, "finished": True})
    return _chicken_json(st, user, {"crashed": False})


def chicken_cashout(user):
    st = _games(user).get("chicken")
    if not st or st["status"] != "active":
        raise bad("Nothing to cash out", code="no_round_in_progress")
    if st["step"] < 1:
        raise bad("Cross at least one lane first", code="cashout_too_early")
    payout = _chicken_cash(user, st)
    return _chicken_json(st, user, {"payout": payout, "finished": True})


# ---- Coinflip ----------------------------------------------------------------------

COIN_RTP = 0.99
COIN_MAX_FLIPS = 10


def coin_mult(flips):
    """Calling `flips` coins in a row: 1.98x for one, 3.96x for two... (99% return)."""
    return math.floor(COIN_RTP * 2 ** flips * 100) / 100


def coinflip(user, body):
    amount = _bet(user, body.get("amount"))
    side = body.get("side")
    if side not in ("heads", "tails"):
        raise bad("Pick heads or tails", code="invalid_move")
    mode = body.get("mode", "classic")
    if mode not in ("classic", "target"):
        raise bad("Unknown mode", code="invalid_game_option")
    flips = 1
    if mode == "target":
        flips = body.get("flips")
        if isinstance(flips, bool) or not isinstance(flips, int) or not 1 <= flips <= COIN_MAX_FLIPS:
            raise bad(f"Pick between 1 and {COIN_MAX_FLIPS} flips in a row", code="invalid_game_option")
    users.debit(user, amount)
    results = []
    for _ in range(flips):                       # stops at the first miss: the rest can't matter
        results.append("heads" if rand_below(2) == 0 else "tails")
        if results[-1] != side:
            break
    win = len(results) == flips and all(r == side for r in results)
    mult = coin_mult(flips)
    payout = round2(amount * mult) if win else 0.0
    if win:
        users.credit(user, payout)
    _record(user, "coinflip", amount, payout, mult if win else None,
            f"{side} x{flips}: {''.join(r[0].upper() for r in results)}")
    return {"results": results, "side": side, "flips": flips, "mult": mult, "win": win, "payout": payout,
            "chance": 100 / 2 ** flips, "balance": user["balance"]}


# ---- Dice --------------------------------------------------------------------------

DICE_RTP = 0.99
DICE_MAX_CHANCE = 9800        # in hundredths of a percent: 98.00%


def dice_odds(direction, target_c):
    """(winning outcomes out of 10,000, multiplier). The roll is 0.00 to 99.99.
    over T wins on a roll >= T (chance 100-T); under T wins on a roll < T (chance T)."""
    count = 10000 - target_c if direction == "over" else target_c
    if not 1 <= count <= DICE_MAX_CHANCE:
        raise bad("The win chance must be between 0.01% and 98%", code="invalid_target")
    return count, math.floor(DICE_RTP * 10000 / count * 10000) / 10000


def dice(user, body):
    amount = _bet(user, body.get("amount"))
    direction = body.get("direction", "over")
    if direction not in ("over", "under"):
        raise bad("Roll over or under", code="invalid_move")
    target = parse_money(body.get("target"), "Target")
    target_c = int(round(target * 100))
    count, mult = dice_odds(direction, target_c)
    users.debit(user, amount)
    roll_c = rand_below(10000)
    win = roll_c >= target_c if direction == "over" else roll_c < target_c
    payout = round2(amount * mult) if win else 0.0
    if win:
        users.credit(user, payout)
    _record(user, "dice", amount, payout, mult if win else None,
            f"{direction} {target_c / 100:.2f}, rolled {roll_c / 100:.2f}")
    return {"roll": roll_c / 100, "direction": direction, "target": target_c / 100, "chance": count / 100,
            "mult": mult, "win": win, "payout": payout, "balance": user["balance"]}


# ---- War ---------------------------------------------------------------------------

WAR_TIE_PAYS = 12             # side bet: the first two cards match in rank (pays 12 to 1)
WAR_COLOUR_TIE_PAYS = 26      # side bet: they match in rank and in colour (pays 26 to 1)
WAR_RANK = {r: i + 2 for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"])}


def _colour(card):
    return "red" if card["s"] in ("H", "D") else "black"


def _side_bet(value, name):
    if value in (None, "", 0):
        return 0.0
    amount = round2(parse_money(value, name))
    if amount < config.MIN_BET - 1e-9:
        raise bad(f"The minimum {name.lower()} is ${config.MIN_BET:.2f}", code="bet_below_minimum")
    return amount


def war(user, body):
    """One card each from a fresh six-deck shoe, higher card wins 1 to 1. On a tie you go to war:
    a matching raise, one more card each, and you win if yours is at least as high (the raise is
    returned). If you can't cover the raise you surrender and get half your bet back."""
    main = _bet(user, body.get("amount"))
    tie_bet = _side_bet(body.get("tie"), "Tie bet")
    colour_bet = _side_bet(body.get("colouredTie"), "Coloured tie bet")
    total = round2(main + tie_bet + colour_bet)
    if total > user["balance"] + 1e-9:
        raise bad("Not enough funds", code="insufficient_funds")
    users.debit(user, total)
    shoe = [{"r": r, "s": s} for _ in range(6) for r in RANKS for s in SUITS]
    shuffle(shoe)
    player, dealer = shoe.pop(), shoe.pop()
    tie = WAR_RANK[player["r"]] == WAR_RANK[dealer["r"]]
    colour_tie = tie and _colour(player) == _colour(dealer)

    wagered, payout, war_round = total, 0.0, None
    if WAR_RANK[player["r"]] > WAR_RANK[dealer["r"]]:
        outcome, payout = "win", round2(main * 2)
    elif not tie:
        outcome = "lose"
    elif user["balance"] + 1e-9 < main:
        outcome, payout = "surrender", round2(main / 2)
    else:
        users.debit(user, main)
        wagered = round2(wagered + main)
        p2, d2 = shoe.pop(), shoe.pop()
        won = WAR_RANK[p2["r"]] >= WAR_RANK[d2["r"]]
        war_round = {"player": p2, "dealer": d2, "raise": main, "win": won}
        outcome, payout = ("warwin", round2(main * 3)) if won else ("warlose", 0.0)
    tie_payout = round2(tie_bet * (WAR_TIE_PAYS + 1)) if tie and tie_bet else 0.0
    colour_payout = round2(colour_bet * (WAR_COLOUR_TIE_PAYS + 1)) if colour_tie and colour_bet else 0.0
    total_payout = round2(payout + tie_payout + colour_payout)
    if total_payout:
        users.credit(user, total_payout)
    mult = round2(total_payout / wagered) if total_payout > wagered else None
    _record(user, "war", wagered, total_payout, mult, outcome + ("+tie" if tie_payout else "") + ("+colour" if colour_payout else ""))
    return {"player": player, "dealer": dealer, "war": war_round, "outcome": outcome, "tie": tie, "colouredTie": colour_tie,
            "bets": {"main": main, "tie": tie_bet, "colouredTie": colour_bet}, "payout": total_payout,
            "wagered": wagered, "tiePayout": tie_payout, "colouredTiePayout": colour_payout,
            "balance": user["balance"]}


# ---- Mines -------------------------------------------------------------------------

MINES_RTP_PCT = 99
MINES_SIZES = (25, 36, 49, 64)
MINES_MAX_MULT = 1_000_000          # a round that cannot go on without passing a million times is paid out on the spot (as in Hi-Lo and Moles)


def mines_mult(size, mines, picks):
    """Multiplier after `picks` safe tiles: RTP / P(that many safe picks), floored to the cent."""
    if picks <= 0:
        return 1.0
    return (MINES_RTP_PCT * 100 * math.comb(size, picks)) // (100 * math.comb(size - mines, picks)) / 100


def mines_table(size, mines):
    _mines_check(size, mines)
    return [mines_mult(size, mines, k) for k in range(0, size - mines + 1)]


def _mines_check(size, mines):
    if isinstance(size, bool) or size not in MINES_SIZES:
        raise bad("Pick a grid size: 25, 36, 49 or 64", code="invalid_game_option")
    if isinstance(mines, bool) or not isinstance(mines, int) or not 1 <= mines <= size - 1:
        raise bad(f"Pick between 1 and {size - 1} mines", code="invalid_game_option")


def _mines_json(st, user, extra=None):
    k = len(st["picked"])
    safe = st["size"] - st["mines"]
    out = {"game": "mines", "id": st["id"], "bet": st["bet"], "size": st["size"], "mines": st["mines"],
           "picked": st["picked"], "status": st["status"], "mult": mines_mult(st["size"], st["mines"], k),
           "nextMult": mines_mult(st["size"], st["mines"], k + 1) if k < safe else None,
           "payoutNow": round2(st["bet"] * mines_mult(st["size"], st["mines"], k)), "balance": user["balance"]}
    if st["status"] != "active":
        out["mineIndices"] = sorted(st["board"])
    if extra:
        out.update(extra)
    return out


def mines_state(user):
    st = _games(user).get("mines")
    return _mines_json(st, user) if st else None


def mines_start(user, body):
    g = _games(user)
    if "mines" in g:
        raise bad("You already have a Mines round going", code="round_in_progress")
    size, mines = body.get("size", 25), body.get("mines", 3)
    _mines_check(size, mines)
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    board = shuffle(list(range(size)))[:mines]
    st = {"id": new_id(), "bet": amount, "size": size, "mines": mines, "board": board, "picked": [], "status": "active"}
    g["mines"] = st
    return _mines_json(st, user)


def _mines_cash(user, st):
    k = len(st["picked"])
    mult = mines_mult(st["size"], st["mines"], k)
    payout = round2(st["bet"] * mult)
    users.credit(user, payout)
    _record(user, "mines", st["bet"], payout, mult, f"{st['mines']} mines in {st['size']}, {k} safe")
    _games(user).pop("mines", None)
    st["status"] = "cashed"
    return payout


def mines_pick(user, body):
    st = _games(user).get("mines")
    if not st or st["status"] != "active":
        raise bad("Start a round first", code="no_round_in_progress")
    tile = body.get("tile")
    if isinstance(tile, bool) or not isinstance(tile, int) or not 0 <= tile < st["size"]:
        raise bad("Pick a tile on the grid", code="invalid_move")
    if tile in st["picked"]:
        raise bad("You already opened that one", code="invalid_move")
    if tile in st["board"]:
        st["status"] = "dead"
        _record(user, "mines", st["bet"], 0.0, None, f"{st['mines']} mines in {st['size']}, hit after {len(st['picked'])}")
        _games(user).pop("mines", None)
        return _mines_json(st, user, {"crashed": True, "hit": tile, "payout": 0.0})
    st["picked"].append(tile)
    k = len(st["picked"])
    if k >= st["size"] - st["mines"] or mines_mult(st["size"], st["mines"], k + 1) > MINES_MAX_MULT:       # (all the safe tiles, or the next one would pay more than the limit)
        payout = _mines_cash(user, st)
        return _mines_json(st, user, {"crashed": False, "finished": True, "payout": payout})
    return _mines_json(st, user, {"crashed": False})


def mines_cashout(user):
    st = _games(user).get("mines")
    if not st or st["status"] != "active":
        raise bad("Nothing to cash out", code="no_round_in_progress")
    if not st["picked"]:
        raise bad("Open at least one tile first", code="cashout_too_early")
    payout = _mines_cash(user, st)
    return _mines_json(st, user, {"payout": payout, "finished": True})


# ---- Moles -------------------------------------------------------------------------

MOLES_HOLES = 7
MOLES_RTP_PCT = 96
MOLES_MAX_MULT_C = 100_000_000      # 1,000,000x, in hundredths
MOLES_MAX_STEPS = 20


def moles_mult(moles, hits):
    """Whack a mole `hits` times in a row. Each round `moles` of the 7 holes hold one, so a round
    is won with chance moles/7. RTP / chance^hits, floored to the cent (3 moles: 2.24x first)."""
    if hits <= 0:
        return 1.0
    return (MOLES_RTP_PCT * MOLES_HOLES ** hits) // (moles ** hits) / 100


def moles_max_steps(moles):
    k = 0
    while k < MOLES_MAX_STEPS and moles_mult(moles, k + 1) * 100 <= MOLES_MAX_MULT_C:
        k += 1
    return k


def moles_table(moles):
    _moles_check(moles)
    return [moles_mult(moles, k) for k in range(0, moles_max_steps(moles) + 1)]


def _moles_check(moles):
    if isinstance(moles, bool) or not isinstance(moles, int) or not 1 <= moles <= MOLES_HOLES - 1:
        raise bad(f"Pick between 1 and {MOLES_HOLES - 1} moles", code="invalid_game_option")


def _moles_json(st, user, extra=None):
    cap = moles_max_steps(st["moles"])
    out = {"game": "moles", "id": st["id"], "bet": st["bet"], "moles": st["moles"], "hits": st["hits"],
           "status": st["status"], "mult": moles_mult(st["moles"], st["hits"]),
           "nextMult": moles_mult(st["moles"], st["hits"] + 1) if st["hits"] < cap else None,
           "payoutNow": round2(st["bet"] * moles_mult(st["moles"], st["hits"])), "holes": MOLES_HOLES,
           "chance": st["moles"] / MOLES_HOLES * 100, "balance": user["balance"]}
    if extra:
        out.update(extra)
    return out


def moles_state(user):
    st = _games(user).get("moles")
    return _moles_json(st, user) if st else None


def moles_start(user, body):
    g = _games(user)
    if "moles" in g:
        raise bad("You already have a Moles round going", code="round_in_progress")
    moles = body.get("moles", 3)
    _moles_check(moles)
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    st = {"id": new_id(), "bet": amount, "moles": moles, "hits": 0, "status": "active"}
    g["moles"] = st
    return _moles_json(st, user)


def _moles_cash(user, st):
    mult = moles_mult(st["moles"], st["hits"])
    payout = round2(st["bet"] * mult)
    users.credit(user, payout)
    _record(user, "moles", st["bet"], payout, mult, f"{st['moles']} moles, {st['hits']} hits")
    _games(user).pop("moles", None)
    st["status"] = "cashed"
    return payout


def moles_pick(user, body):
    st = _games(user).get("moles")
    if not st or st["status"] != "active":
        raise bad("Start a round first", code="no_round_in_progress")
    hole = body.get("hole")
    if isinstance(hole, bool) or not isinstance(hole, int) or not 0 <= hole < MOLES_HOLES:
        raise bad("Pick one of the holes", code="invalid_move")
    popped = sorted(shuffle(list(range(MOLES_HOLES)))[:st["moles"]])      # where the moles are this round
    if hole not in popped:
        st["status"] = "dead"
        _record(user, "moles", st["bet"], 0.0, None, f"{st['moles']} moles, missed after {st['hits']}")
        _games(user).pop("moles", None)
        return _moles_json(st, user, {"crashed": True, "hit": False, "popped": popped, "hole": hole, "payout": 0.0})
    st["hits"] += 1
    if st["hits"] >= moles_max_steps(st["moles"]):
        payout = _moles_cash(user, st)
        return _moles_json(st, user, {"crashed": False, "hit": True, "popped": popped, "hole": hole,
                                      "finished": True, "payout": payout})
    return _moles_json(st, user, {"crashed": False, "hit": True, "popped": popped, "hole": hole})


def moles_cashout(user):
    st = _games(user).get("moles")
    if not st or st["status"] != "active":
        raise bad("Nothing to cash out", code="no_round_in_progress")
    if st["hits"] < 1:
        raise bad("Whack at least one mole first", code="cashout_too_early")
    payout = _moles_cash(user, st)
    return _moles_json(st, user, {"payout": payout, "finished": True})


# ---- Tower -------------------------------------------------------------------------

TOWER_ROWS = 8
TOWER_RTP_PCT = 96
# risk -> (tiles per row, trap tiles per row)
TOWER_RISK = {"easy": (4, 1), "medium": (3, 1), "hard": (2, 1), "expert": (3, 2), "master": (4, 3)}


def tower_mult(risk, rows):
    """Climb `rows` rows: RTP / (safe tiles / tiles)^rows, floored to the cent (easy: 1.28x first)."""
    if rows <= 0:
        return 1.0
    cols, traps = TOWER_RISK[risk]
    return (TOWER_RTP_PCT * cols ** rows) // ((cols - traps) ** rows) / 100


def tower_table(risk):
    if risk not in TOWER_RISK:
        raise bad("Unknown risk level", code="invalid_game_option")
    return [tower_mult(risk, k) for k in range(0, TOWER_ROWS + 1)]


def _tower_json(st, user, extra=None):
    out = {"game": "tower", "id": st["id"], "bet": st["bet"], "risk": st["risk"], "cols": st["cols"],
           "traps": st["traps"], "rows": TOWER_ROWS, "picks": st["picks"], "step": len(st["picks"]),
           "status": st["status"], "mult": tower_mult(st["risk"], len(st["picks"])),
           "nextMult": tower_mult(st["risk"], len(st["picks"]) + 1) if len(st["picks"]) < TOWER_ROWS else None,
           "payoutNow": round2(st["bet"] * tower_mult(st["risk"], len(st["picks"]))), "balance": user["balance"]}
    if st["status"] != "active":
        out["layout"] = st["layout"]
    if extra:
        out.update(extra)
    return out


def tower_state(user):
    st = _games(user).get("tower")
    return _tower_json(st, user) if st else None


def tower_start(user, body):
    g = _games(user)
    if "tower" in g:
        raise bad("You already have a Tower climb going", code="round_in_progress")
    risk = body.get("risk", "easy")
    if risk not in TOWER_RISK:
        raise bad("Unknown risk level", code="invalid_game_option")
    amount = _bet(user, body.get("amount"))
    cols, traps = TOWER_RISK[risk]
    users.debit(user, amount)
    layout = [sorted(shuffle(list(range(cols)))[:traps]) for _ in range(TOWER_ROWS)]      # trap tiles, bottom row first
    st = {"id": new_id(), "bet": amount, "risk": risk, "cols": cols, "traps": traps, "layout": layout,
          "picks": [], "status": "active"}
    g["tower"] = st
    return _tower_json(st, user)


def _tower_cash(user, st):
    k = len(st["picks"])
    mult = tower_mult(st["risk"], k)
    payout = round2(st["bet"] * mult)
    users.credit(user, payout)
    _record(user, "tower", st["bet"], payout, mult, f"{st['risk']}, {k} rows")
    _games(user).pop("tower", None)
    st["status"] = "cashed"
    return payout


def tower_pick(user, body):
    st = _games(user).get("tower")
    if not st or st["status"] != "active":
        raise bad("Start a climb first", code="no_round_in_progress")
    col = body.get("tile")
    if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col < st["cols"]:
        raise bad("Pick a tile on the next row", code="invalid_move")
    row = len(st["picks"])
    if col in st["layout"][row]:
        st["status"] = "dead"
        st["picks"].append(col)
        _record(user, "tower", st["bet"], 0.0, None, f"{st['risk']}, fell on row {row + 1}")
        _games(user).pop("tower", None)
        return _tower_json(st, user, {"crashed": True, "payout": 0.0})
    st["picks"].append(col)
    if len(st["picks"]) >= TOWER_ROWS:
        payout = _tower_cash(user, st)
        return _tower_json(st, user, {"crashed": False, "finished": True, "payout": payout})
    return _tower_json(st, user, {"crashed": False})


def tower_cashout(user):
    st = _games(user).get("tower")
    if not st or st["status"] != "active":
        raise bad("Nothing to cash out", code="no_round_in_progress")
    if not st["picks"]:
        raise bad("Climb at least one row first", code="cashout_too_early")
    payout = _tower_cash(user, st)
    return _tower_json(st, user, {"payout": payout, "finished": True})


# ---- shared ------------------------------------------------------------------------

def profit_summary(user):
    """Casino profit for today, this week and all time (shown in the casino sidebar)."""
    from .util import day_start_ms, week_key
    day_start = day_start_ms()
    stats = user["stats"]
    return {
        "today": round2(sum(h["profit"] for h in user["history"] if h["t"] >= day_start)),
        "week": round2(stats.get(week_key(), {}).get("gamePnl", 0)),
        "total": round2(sum(w.get("gamePnl", 0) for w in stats.values())),
    }


# ---- Hi-Lo ---------------------------------------------------------------------------
# A card is showing. Guess whether the NEXT card is higher or lower (a card of the same rank counts as a win both ways, which is
# why the chance of "higher or same" and "lower or same" add up to more than 100%). Cards are drawn fresh and independently
# (any of 13 ranks, any of 4 suits), so the chance of each guess is exactly (ranks that win) / 13. A guess pays
# 0.96 / chance, rounded DOWN to a hundredth of a multiplier, and the multipliers of a streak multiply together. You can cash
# out after any right guess, and skip a card you do not like (a new one is drawn) without paying anything.
# A guess that cannot lose (an Ace guessing "higher or same", a King guessing "lower or same": every card is at least as high as
# an Ace) is not offered, so every guess that is offered returns at most 96% and there is no free money in skipping for one.

HILO_RTP_X100 = 96
HILO_RANKS = 13
HILO_MAX_SKIPS = 52
HILO_MAX_MULT = 1_000_000                                # a streak that reaches a million times is paid out on the spot
RANK_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}
SUITS = ("S", "H", "D", "C")


def _hilo_card():
    return {"r": rand_below(HILO_RANKS) + 1, "s": SUITS[rand_below(4)]}


def _card_json(c):
    return {"r": RANK_NAMES.get(c["r"], str(c["r"])), "s": c["s"], "n": c["r"]}


def hilo_options(rank):
    """What each guess is worth for a card of this rank: how many ranks win, the chance, and the multiplier (x100, rounded down)."""
    out = {}
    for pick, k in (("higher", HILO_RANKS - rank + 1), ("lower", rank)):
        offered = k < HILO_RANKS
        out[pick] = {"k": k, "chance": k / HILO_RANKS, "offered": offered,
                     "mult_x100": (HILO_RTP_X100 * HILO_RANKS * 100 // (100 * k)) if offered else 0}
    return out


def _hilo_total_x100(steps):
    """The streak's multiplier, as an exact fraction (numerator, denominator): every step is a multiplier in hundredths."""
    num, den = 1, 1
    for m in steps:
        num *= m
        den *= 100
    return num, den


def _hilo_payout_c(bet_c, steps):
    num, den = _hilo_total_x100(steps)
    return bet_c * num // den


def _hilo_json(st, user, extra=None):
    num, den = _hilo_total_x100(st["steps"])
    opts = hilo_options(st["card"]["r"])
    out = {"id": st["id"], "bet": st["bet"], "card": _card_json(st["card"]), "status": st["status"], "wins": len(st["steps"]),
           "mult": num / den if st["steps"] else 1.0, "payoutNow": _hilo_payout_c(int(round(st["bet"] * 100)), st["steps"]) / 100,
           "options": {k: {"chance": v["chance"], "offered": v["offered"], "mult": v["mult_x100"] / 100} for k, v in opts.items()},
           "skipsLeft": HILO_MAX_SKIPS - st["skips"], "history": st["history"][-14:], "balance": user["balance"]}
    if extra:
        out.update(extra)
    return out


def hilo_state(user):
    st = _games(user).get("hilo")
    return _hilo_json(st, user) if st else None


def hilo_start(user, body):
    g = _games(user)
    if "hilo" in g:
        raise bad("You already have a Hi-Lo round going", code="round_in_progress")
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    st = {"id": new_id(), "bet": amount, "card": _hilo_card(), "steps": [], "skips": 0, "history": [], "status": "active"}
    st["history"].append({**_card_json(st["card"]), "t": "start"})
    g["hilo"] = st
    return _hilo_json(st, user)


def _hilo_cash(user, st):
    bet_c = int(round(st["bet"] * 100))
    payout = _hilo_payout_c(bet_c, st["steps"]) / 100
    num, den = _hilo_total_x100(st["steps"])
    mult = (num * 100 // den) / 100                               # rounded DOWN, like the payout: 2.665x is recorded as 2.66x
    users.credit(user, payout)
    users.stat_max(user, "hiloBest", mult)
    _record(user, "hilo", st["bet"], payout, mult, f"{len(st['steps'])} right")
    _games(user).pop("hilo", None)
    st["status"] = "cashed"
    return payout


def hilo_guess(user, body):
    st = _games(user).get("hilo")
    if not st or st["status"] != "active":
        raise bad("Start a round first", code="no_round_in_progress")
    pick = body.get("pick")
    if pick not in ("higher", "lower"):
        raise bad("Guess higher or lower", code="invalid_move")
    opt = hilo_options(st["card"]["r"])[pick]
    if not opt["offered"]:
        raise bad("That guess cannot lose, so it is not offered. Guess the other way, or skip the card.", code="guess_not_offered")
    nxt = _hilo_card()
    cur = st["card"]["r"]
    won = nxt["r"] >= cur if pick == "higher" else nxt["r"] <= cur
    shown = _card_json(nxt)
    if not won:
        _record(user, "hilo", st["bet"], 0.0, None, f"{len(st['steps'])} right, then {pick} missed")
        _games(user).pop("hilo", None)
        st["status"] = "lost"
        st["card"] = nxt
        return _hilo_json(st, user, {"won": False, "next": shown, "payout": 0.0, "pick": pick, "finished": True})
    st["steps"].append(opt["mult_x100"])
    st["card"] = nxt
    st["history"].append({**shown, "t": "win"})
    num, den = _hilo_total_x100(st["steps"])
    if num >= HILO_MAX_MULT * den:
        payout = _hilo_cash(user, st)
        return _hilo_json(st, user, {"won": True, "next": shown, "payout": payout, "pick": pick, "finished": True})
    return _hilo_json(st, user, {"won": True, "next": shown, "pick": pick})


def hilo_skip(user):
    st = _games(user).get("hilo")
    if not st or st["status"] != "active":
        raise bad("Start a round first", code="no_round_in_progress")
    if st["skips"] >= HILO_MAX_SKIPS:
        raise bad("No skips left in this round", code="no_skips_left")
    st["skips"] += 1
    st["card"] = _hilo_card()
    st["history"].append({**_card_json(st["card"]), "t": "skip"})
    return _hilo_json(st, user)


def hilo_cashout(user):
    st = _games(user).get("hilo")
    if not st or st["status"] != "active":
        raise bad("Nothing to cash out", code="no_round_in_progress")
    if not st["steps"]:
        raise bad("Guess right at least once first", code="cashout_too_early")
    payout = _hilo_cash(user, st)
    return _hilo_json(st, user, {"payout": payout, "finished": True})


# ---- Wheel ---------------------------------------------------------------------------
# A wheel of 50 equal segments, each with a multiplier. One spin lands on one segment, chosen uniformly by the server. The risk
# level decides how the segments are shared out: Low has many small wins, Risky has almost no wins and a few huge ones.
# Every table returns exactly 96% (the multipliers, in hundredths, times how many segments have them, add up to 50 x 96).

WHEEL_SEGMENTS = 50
WHEEL_RTP_X100 = 96
WHEEL_RISKS = {                                             # (multiplier x100, how many of the 50 segments)
    "low": [(0, 12), (110, 18), (120, 11), (140, 5), (200, 4)],
    "medium": [(0, 29), (150, 8), (200, 7), (300, 4), (500, 2)],
    "high": [(0, 38), (200, 6), (300, 2), (500, 2), (1000, 2)],
    "risky": [(0, 48), (2400, 2)],
}


def wheel_layout(risk):
    """The 50 multipliers in the order they sit round the wheel, each kind spread as evenly as it can be."""
    placed = []
    for mult, count in WHEEL_RISKS[risk]:
        for i in range(count):
            placed.append(((i + 0.5) / count, mult))
    placed.sort(key=lambda p: (p[0], p[1]))
    return [m for _, m in placed]


def wheel_table(risk):
    return [{"mult": m / 100, "count": c, "chance": c / WHEEL_SEGMENTS} for m, c in WHEEL_RISKS[risk]]


def wheel(user, body):
    risk = body.get("risk")
    if risk not in WHEEL_RISKS:
        raise bad("Pick a risk level", code="invalid_game_option")
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    layout = wheel_layout(risk)
    index = rand_below(WHEEL_SEGMENTS)
    mult_x100 = layout[index]
    payout = (int(round(amount * 100)) * mult_x100 // 100) / 100
    if payout:
        users.credit(user, payout)
    mult = mult_x100 / 100
    if mult > 1:
        users.stat_max(user, "wheelBest", mult)
    _record(user, "wheel", amount, payout, mult if payout > amount else None, f"{risk}, landed on {mult:.2f}x")
    return {"risk": risk, "index": index, "mult": mult, "payout": payout, "win": payout > amount, "balance": user["balance"]}


# ---- Rock Paper Scissors -------------------------------------------------------------
# Beat the house, again and again. Each round you pick rock, paper or scissors and so does the house. A win moves you up the
# ladder, a loss ends it, and a draw is simply played again (it costs nothing and changes nothing). Because draws are replayed,
# every round is a fair coin flip between winning and losing, and the ladder pays 0.98 x 2 for one win, then doubles with every
# win after that: 1.96x, 3.92x, 7.84x, 15.68x... Return to player is 98% at every step. You can cash out after any win.

RPS_RTP_X100 = 98
RPS_MAX_WINS = 10
RPS_MOVES = ("rock", "paper", "scissors")
RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}


def rps_mult_x100(wins):
    return RPS_RTP_X100 * (2 ** wins) if wins > 0 else 100


def rps_ladder():
    return [rps_mult_x100(n) / 100 for n in range(1, RPS_MAX_WINS + 1)]


def _rps_json(st, user, extra=None):
    w = st["wins"]
    out = {"id": st["id"], "bet": st["bet"], "wins": w, "status": st["status"], "mult": rps_mult_x100(w) / 100 if w else 1.0,
           "payoutNow": (int(round(st["bet"] * 100)) * rps_mult_x100(w) // 100) / 100 if w else 0.0,
           "next": rps_mult_x100(w + 1) / 100 if w < RPS_MAX_WINS else None, "draws": st["draws"], "balance": user["balance"]}
    if extra:
        out.update(extra)
    return out


def rps_state(user):
    st = _games(user).get("rps")
    return _rps_json(st, user) if st else None


def rps_start(user, body):
    g = _games(user)
    if "rps" in g:
        raise bad("You already have a Rock Paper Scissors round going", code="round_in_progress")
    amount = _bet(user, body.get("amount"))
    users.debit(user, amount)
    st = {"id": new_id(), "bet": amount, "wins": 0, "draws": 0, "status": "active"}
    g["rps"] = st
    return _rps_json(st, user)


def _rps_cash(user, st):
    mult = rps_mult_x100(st["wins"]) / 100
    payout = (int(round(st["bet"] * 100)) * rps_mult_x100(st["wins"]) // 100) / 100
    users.credit(user, payout)
    users.stat_max(user, "rpsBest", mult)
    _record(user, "rps", st["bet"], payout, mult, f"{st['wins']} won in a row")
    _games(user).pop("rps", None)
    st["status"] = "cashed"
    return payout


def rps_play(user, body):
    st = _games(user).get("rps")
    if not st or st["status"] != "active":
        raise bad("Start a round first", code="no_round_in_progress")
    pick = body.get("pick")
    if pick not in RPS_MOVES:
        raise bad("Pick rock, paper or scissors", code="invalid_move")
    house = RPS_MOVES[rand_below(3)]
    if house == pick:
        st["draws"] += 1
        return _rps_json(st, user, {"result": "draw", "pick": pick, "house": house})
    if RPS_BEATS[pick] != house:
        _record(user, "rps", st["bet"], 0.0, None, f"{st['wins']} won, then lost to {house}")
        _games(user).pop("rps", None)
        st["status"] = "lost"
        return _rps_json(st, user, {"result": "lose", "pick": pick, "house": house, "payout": 0.0, "finished": True})
    st["wins"] += 1
    if st["wins"] >= RPS_MAX_WINS:
        payout = _rps_cash(user, st)
        return _rps_json(st, user, {"result": "win", "pick": pick, "house": house, "payout": payout, "finished": True})
    return _rps_json(st, user, {"result": "win", "pick": pick, "house": house})


def rps_cashout(user):
    st = _games(user).get("rps")
    if not st or st["status"] != "active":
        raise bad("Nothing to cash out", code="no_round_in_progress")
    if st["wins"] < 1:
        raise bad("Win at least one round first", code="cashout_too_early")
    payout = _rps_cash(user, st)
    return _rps_json(st, user, {"payout": payout, "finished": True})


def active_state(user):
    g = _games(user)
    out = {"chicken": chicken_state(user), "blackjack": None, "hilo": hilo_state(user), "rps": rps_state(user), "mines": mines_state(user),
           "moles": moles_state(user), "tower": tower_state(user)}
    if "blackjack" in g:
        out["blackjack"] = _bj_json(g["blackjack"], user)
    return out
