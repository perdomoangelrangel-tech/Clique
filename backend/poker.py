"""Texas Hold'em, no limit: live tables where friends play each other.

Everything that matters happens here on the server: the shuffle, who acts, what is legal, the pots,
the winners. The browser only ever sees its own hole cards. Amounts are whole integers ("units"):
one chip in a fake-money game, one cent in a real-money game, so no float ever touches a pot.

A table moves through  setup  ->  playing  ->  (back to setup)  ->  closed.
In setup the host edits the settings and every seated player has to accept them. Real money is only
moved when the host presses start: each player's buy-in leaves their cash and sits in front of them
as a stack, and goes back to their cash the moment they leave."""
import itertools
import secrets

from . import activity, config, users
from .store import db
from .util import bad, clean_text, new_id, now_ms, parse_money, round2, shuffle

RANKS = "23456789TJQKA"
SUITS = "shdc"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

MAX_SEATS = 9
MAX_TABLES_PER_HOST = 2
MAX_TABLES_TOTAL = 60
SHOWDOWN_MS = 8000          # how long a finished hand stays on screen
FOLD_WIN_MS = 4000
RUNOUT_MS = 1800            # between the streets when everyone is all-in
BUST_WAIT_MS = 120_000      # a busted player has this long to rebuy before the seat is freed
IDLE_SETUP_MS = 60 * 60 * 1000
MAX_TIMEOUTS = 3            # this many timed-out turns in a row and you are stood up
LOG_KEEP = 80

FAKE_DEFAULT = {"bigBlind": 20, "smallBlind": 10, "stack": 1000}
REAL_DEFAULT = {"bigBlind": 100, "smallBlind": 50, "stack": 10000}      # cents: $1 / $0.50, $100 buy-in
TURN_FAKE = (0, 15, 30, 45, 60, 90, 120)                                # 0 = no clock
TURN_REAL = (15, 30, 45, 60, 90, 120)
BLINDS_UP = (0, 5, 10, 15, 20)                                          # blinds double every N hands


# ---- hand evaluation ---------------------------------------------------------------

def eval5(cards):
    """Score exactly five cards. Higher tuples beat lower ones."""
    vals = sorted((RANKS.index(c[0]) + 2 for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    uniq = sorted(set(vals), reverse=True)
    straight = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:               # the wheel: the ace plays low
            straight = 5
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    groups = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    shape = [c for _, c in groups]
    if straight and flush:
        return (8, (straight,))
    if shape == [4, 1]:
        return (7, (groups[0][0], groups[1][0]))
    if shape == [3, 2]:
        return (6, (groups[0][0], groups[1][0]))
    if flush:
        return (5, tuple(vals))
    if straight:
        return (4, (straight,))
    if shape == [3, 1, 1]:
        return (3, tuple(v for v, _ in groups))
    if shape == [2, 2, 1]:
        return (2, tuple(v for v, _ in groups))
    if shape == [2, 1, 1, 1]:
        return (1, tuple(v for v, _ in groups))
    return (0, tuple(vals))


def best_hand(cards):
    """Best five-card hand out of five, six or seven cards."""
    return max(eval5(c) for c in itertools.combinations(cards, 5))


_NAME = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
         11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}
_PLURAL = {2: "Twos", 3: "Threes", 4: "Fours", 5: "Fives", 6: "Sixes", 7: "Sevens", 8: "Eights", 9: "Nines",
           10: "Tens", 11: "Jacks", 12: "Queens", 13: "Kings", 14: "Aces"}


def describe(score):
    cat, tb = score
    if cat == 8:
        return "Royal flush" if tb[0] == 14 else f"Straight flush, {_NAME[tb[0]]} high"
    if cat == 7:
        return f"Four of a kind, {_PLURAL[tb[0]]}"
    if cat == 6:
        return f"Full house, {_PLURAL[tb[0]]} over {_PLURAL[tb[1]]}"
    if cat == 5:
        return f"Flush, {_NAME[tb[0]]} high"
    if cat == 4:
        return f"Straight, {_NAME[tb[0]]} high"
    if cat == 3:
        return f"Three of a kind, {_PLURAL[tb[0]]}"
    if cat == 2:
        return f"Two pair, {_PLURAL[tb[0]]} and {_PLURAL[tb[1]]}"
    if cat == 1:
        return f"Pair of {_PLURAL[tb[0]]}"
    return f"High card, {_NAME[tb[0]]}"


def live_hand(hole, board):
    """What a player is holding right now, for their own screen: a hand name (from the two hole cards on up)
    and, on the flop and turn, any flush or straight draw that is still alive."""
    cards = list(hole) + list(board)
    if len(cards) < 5:
        a, b = (RANKS.index(c[0]) + 2 for c in cards)
        name = f"Pair of {_PLURAL[a]}" if a == b else f"High card, {_NAME[max(a, b)]}"
        return {"name": name, "draws": []}
    best = best_hand(cards)
    draws = []
    if 3 <= len(board) <= 4:
        if best[0] < 5:
            for su in SUITS:
                if sum(1 for c in cards if c[1] == su) == 4 and any(c[1] == su for c in hole):
                    draws.append("Flush draw")
        if best[0] < 4:
            have = {c[0] for c in cards}
            outs = 0
            for r in RANKS:
                if r in have:
                    continue
                probe = cards + [r + "x"]                      # a card of no suit, so it can only make a straight
                on_board = len(board) >= 4 and best_hand(list(board) + [r + "x"])[0] == 4     # the board alone would do it
                if best_hand(probe)[0] == 4 and not on_board:
                    outs += 1
            if outs == 1:
                draws.append("Straight draw")
            elif outs >= 2:
                draws.append("Open-ended straight draw")
    return {"name": describe(best), "draws": draws}


# ---- lookups -----------------------------------------------------------------------

def tables():
    return db().setdefault("poker", {})


def get(tid):
    t = tables().get(tid)
    if not t:
        raise bad("That table is gone", 404, code="table_not_found")
    return t


def seat_index(table, uid):
    for i, s in enumerate(table["seats"]):
        if s and s["userId"] == uid:
            return i
    return None


def table_of(uid):
    for t in tables().values():
        if seat_index(t, uid) is not None:
            return t
    return None


def by_code(code):
    code = str(code or "").strip().upper()
    for t in tables().values():
        if t["code"] and t["code"] == code:
            return t
    return None


def seated(table):
    return [s for s in table["seats"] if s]


def scale_of(table):
    return 100 if table["settings"]["money"] == "real" else 1


def _log(table, msg):
    table["log"].append(msg)
    del table["log"][:-LOG_KEEP]


def _fmt(table, n):
    """An amount the way people say it: 1,250 chips, or $3 / $3.50 for real money (the engine counts cents)."""
    if scale_of(table) == 1:
        return f"{n:,}"
    return f"${n // 100:,}" if n % 100 == 0 else f"${n / 100:,.2f}"


_GLYPH = {"s": "\u2660", "h": "\u2665", "d": "\u2666", "c": "\u2663"}


def _cards(cards):
    return " ".join(("10" if c[0] == "T" else c[0]) + _GLYPH[c[1]] for c in cards)


def _touch(table, now):
    table["v"] += 1
    table["lastActivity"] = now


def _code():
    taken = {t["code"] for t in tables().values() if t["code"]}
    while True:
        c = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if c not in taken:
            return c


def real_stake(uid):
    """Real money this person has at a poker table right now (stack plus what they have bet this hand)."""
    total = 0
    for t in tables().values():
        if t["settings"]["money"] != "real" or t["status"] != "playing":
            continue
        i = seat_index(t, uid)
        if i is None:
            continue
        total += t["seats"][i]["stack"]
        h = t["hand"]
        if h and h["street"] != "ended":
            total += h["contrib"][i]
    return total / 100


# ---- settings ----------------------------------------------------------------------

def default_settings(money="fake"):
    base = {"money": money, "maxSeats": 6, "turnSeconds": 45, "rebuy": True, "blindsUp": 0}
    base.update(FAKE_DEFAULT if money == "fake" else REAL_DEFAULT)
    if money == "real":
        base["rebuy"] = False
    return base


def _units(money, value, label):
    v = parse_money(value, label)
    if money == "fake":
        if v != int(v):
            raise bad(f"{label} has to be a whole number of chips", code="invalid_table_settings")
        return int(v)
    return int(round(v * 100))


def apply_settings(table, body):
    """Validates a settings change and returns the new settings dict (does not store it)."""
    cur = table["settings"]
    money = body.get("money", cur["money"])
    if money not in ("fake", "real"):
        raise bad("Money has to be fake chips or real cash", code="invalid_table_settings")
    s = dict(cur)
    if money != cur["money"]:
        s.update(default_settings(money))
    s["money"] = money
    if "bigBlind" in body:
        s["bigBlind"] = _units(money, body["bigBlind"], "Big blind")
        if "smallBlind" not in body:
            s["smallBlind"] = max(1 if money == "fake" else 5, s["bigBlind"] // 2)
    if "smallBlind" in body:
        s["smallBlind"] = _units(money, body["smallBlind"], "Small blind")
    if "stack" in body:
        s["stack"] = _units(money, body["stack"], "Starting stack" if money == "fake" else "Buy-in")
    if "maxSeats" in body:
        ms = body["maxSeats"]
        if isinstance(ms, bool) or not isinstance(ms, int) or not 2 <= ms <= MAX_SEATS:
            raise bad(f"A table seats between 2 and {MAX_SEATS}", code="invalid_table_settings")
        s["maxSeats"] = ms
    if "turnSeconds" in body:
        s["turnSeconds"] = body["turnSeconds"]
    if "rebuy" in body:
        if not isinstance(body["rebuy"], bool):
            raise bad("Rebuys are on or off", code="invalid_table_settings")
        s["rebuy"] = body["rebuy"]
    if "blindsUp" in body:
        s["blindsUp"] = body["blindsUp"]

    bb, sb, stack = s["bigBlind"], s["smallBlind"], s["stack"]
    if money == "fake":
        if not 2 <= bb <= 1_000_000:
            raise bad("The big blind has to be between 2 and 1,000,000 chips", code="invalid_table_settings")
        if not 1 <= sb <= bb:
            raise bad("The small blind has to be at least 1 chip and no more than the big blind", code="invalid_table_settings")
        if not 10 * bb <= stack <= 1000 * bb:
            raise bad("The starting stack has to be 10 to 1,000 big blinds", code="invalid_table_settings")
        if s["turnSeconds"] not in TURN_FAKE:
            raise bad("Pick a turn timer from the list", code="invalid_table_settings")
    else:
        if not 10 <= bb <= 10_000:
            raise bad("The big blind has to be between $0.10 and $100", code="invalid_table_settings")
        if not 5 <= sb <= bb:
            raise bad("The small blind has to be at least $0.05 and no more than the big blind", code="invalid_table_settings")
        if not 20 * bb <= stack <= 200 * bb or stack > 1_000_000:
            raise bad("The buy-in has to be 20 to 200 big blinds, and at most $10,000", code="invalid_table_settings")
        if s["turnSeconds"] not in TURN_REAL:
            raise bad("Real-money tables need a turn timer of at most 2 minutes", code="invalid_table_settings")
    if s["blindsUp"] not in BLINDS_UP:
        raise bad("Pick how often the blinds go up from the list", code="invalid_table_settings")
    # seats can shrink only if the chairs that disappear are empty
    seats = table["seats"]
    if s["maxSeats"] < len(seats) and any(seats[s["maxSeats"]:]):
        raise bad("Some of the seats you would remove are taken", code="invalid_table_settings")
    return s


# ---- tables ------------------------------------------------------------------------

def create(user, body):
    uid = user["id"]
    if table_of(uid):
        raise bad("You are already sitting at a table. Leave it first.", code="already_seated")
    hosting = sum(1 for t in tables().values() if t["hostId"] == uid)
    if hosting >= MAX_TABLES_PER_HOST:
        raise bad(f"You are already running {MAX_TABLES_PER_HOST} tables", code="too_many_tables")
    if len(tables()) >= MAX_TABLES_TOTAL:
        raise bad("The poker room is full right now. Try again later.", code="poker_room_full")
    vis = body.get("visibility", "public")
    if vis not in ("public", "private"):
        raise bad("A table is public or private", code="invalid_table_settings")
    name = clean_text(body.get("name") or f"{user['username']}'s table", "Table name", 2, 30)
    settings = default_settings("fake")
    now = now_ms()
    t = {"id": new_id(), "code": _code() if vis == "private" else None, "name": name, "visibility": vis,
         "hostId": uid, "createdAt": now, "lastActivity": now, "status": "setup", "settings": settings,
         "settingsRev": 1, "votes": {uid: True}, "seats": [None] * settings["maxSeats"], "hand": None,
         "handNo": 0, "button": -1, "blinds": {"sb": settings["smallBlind"], "bb": settings["bigBlind"]},
         "ending": False, "log": [], "v": 1}
    if "maxSeats" in body:
        t["settings"] = apply_settings(t, {"maxSeats": body["maxSeats"]})
        t["seats"] = [None] * t["settings"]["maxSeats"]
    tables()[t["id"]] = t
    _sit(t, user, 0, now)
    _log(t, f"{user['username']} opened the table")
    return t


def _new_seat(user, now):
    return {"userId": user["id"], "name": user["username"], "stack": 0, "joinedAt": now, "timeouts": 0,
            "leaving": False, "busted": False, "bought": 0, "hands": 0}


def _sit(table, user, idx, now):
    table["seats"][idx] = _new_seat(user, now)


def join(user, table_id=None, code=None, confirm=False):
    uid = user["id"]
    now = now_ms()
    if code:
        table = by_code(code)
        if not table:
            raise bad("No table has that code", 404, code="table_not_found")
    else:
        table = get(table_id)
        if table["visibility"] == "private":
            raise bad("That table is private. You need its code.", 404, code="invite_code_required")
    mine = table_of(uid)
    if mine and mine["id"] != table["id"]:
        raise bad("You are already sitting at another table. Leave it first.", code="already_seated")
    if seat_index(table, uid) is not None:
        return table
    free = next((i for i, s in enumerate(table["seats"]) if s is None), None)
    if free is None:
        raise bad("That table is full", code="table_full")
    s = table["settings"]
    _sit(table, user, free, now)
    seat = table["seats"][free]
    if table["status"] == "playing":
        if s["money"] == "real":
            if not confirm:
                table["seats"][free] = None
                raise bad(f"This is a real-money table. Joining costs a ${s['stack'] / 100:,.2f} buy-in from your cash.", code="confirm_required")
            try:
                _buy_in(table, user, seat, s["stack"])
            except Exception:
                table["seats"][free] = None
                raise
        else:
            seat["stack"] = s["stack"]
        _log(table, f"{user['username']} sat down")
        _maybe_start(table, now)
    else:
        _log(table, f"{user['username']} joined")
    _touch(table, now)
    return table


def _buy_in(table, user, seat, amount):
    cash = amount / 100
    if cash > user["balance"] + 1e-9:
        raise bad(f"You need ${cash:,.2f} in cash to buy in", code="insufficient_funds")
    users.debit(user, cash, "poker")
    users.log(user, "poker", -cash, f"Poker buy-in: {table['name']}")
    seat["stack"] += amount
    seat["bought"] += amount


def _cash_out(table, seat):
    """Real money goes back to the player's cash and the session is written into their history."""
    if table["settings"]["money"] != "real" or seat["bought"] <= 0:
        return
    user = users.get(seat["userId"])
    cash = seat["stack"] / 100
    bought = seat["bought"] / 100
    if cash:
        users.credit(user, cash, "poker")
    users.log(user, "poker", cash, f"Poker cash-out: {table['name']}")
    profit = round2(cash - bought)
    users.stat_add(user, "gameWagered", bought)
    users.stat_add(user, "gamePnl", profit)
    users.stat_add(user, "gamesPlayed")
    if profit > 0:
        users.stat_max(user, "biggestGameWin", profit)
    user["history"].insert(0, {"id": new_id(), "t": now_ms(), "game": "poker", "bet": bought, "payout": cash,
                               "mult": round2(cash / bought) if cash > bought else None, "profit": profit,
                               "detail": f"{seat['hands']} hands at {table['blinds']['sb'] / 100:g}/{table['blinds']['bb'] / 100:g}"})
    del user["history"][100:]
    seat["bought"], seat["stack"] = 0, 0


def _stand_up(table, idx, why="left"):
    seat = table["seats"][idx]
    if seat is None:
        return
    _cash_out(table, seat)
    uid = seat["userId"]
    table["seats"][idx] = None
    table["votes"].pop(uid, None)
    h = table["hand"]
    if h and idx < len(h["st"]) and h["st"][idx] == "folded":
        h["st"][idx] = "out"                      # their money stays in the pot, the chair is just free
    _log(table, f"{seat['name']} {why}")
    if table["hostId"] == uid:
        rest = sorted(seated(table), key=lambda s: s["joinedAt"])
        if rest:
            table["hostId"] = rest[0]["userId"]
            table["votes"][rest[0]["userId"]] = True
            _log(table, f"{rest[0]['name']} is the host now")
    if not seated(table):
        tables().pop(table["id"], None)


def leave(user, table):
    uid = user["id"]
    idx = seat_index(table, uid)
    if idx is None:
        raise bad("You are not at this table", code="not_seated")
    now = now_ms()
    h = table["hand"]
    if h and h["street"] != "ended" and h["st"][idx] in ("in", "allin"):
        # still in the hand: fold now (or when it is their turn) and leave when the hand ends
        table["seats"][idx]["leaving"] = True
        if h["toAct"] == idx:
            _fold(table, idx, now)
        _log(table, f"{table['seats'][idx]['name']} is leaving after this hand")
    else:
        _stand_up(table, idx)
    if table["id"] in tables():
        _touch(table, now)


def kick(user, table, target_id):
    if table["hostId"] != user["id"]:
        raise bad("Only the host can remove someone", 403, code="not_table_host")
    if target_id == user["id"]:
        raise bad("Use leave to leave your own table", code="invalid_action")
    idx = seat_index(table, target_id)
    if idx is None:
        raise bad("They are not at this table", 404, code="not_seated")
    now = now_ms()
    h = table["hand"]
    if h and h["street"] != "ended" and h["st"][idx] in ("in", "allin"):
        table["seats"][idx]["leaving"] = True
        if h["toAct"] == idx:
            _fold(table, idx, now)
        _log(table, f"{table['seats'][idx]['name']} was removed and leaves after this hand")
    else:
        _stand_up(table, idx, "was removed")
    if table["id"] in tables():
        _touch(table, now)


def set_settings(user, table, body):
    if table["hostId"] != user["id"]:
        raise bad("Only the host can change the settings", 403, code="not_table_host")
    if table["status"] != "setup":
        raise bad("The settings are locked once the game starts. End the game to change them.", code="game_in_progress")
    table["settings"] = apply_settings(table, body)
    s = table["settings"]
    seats = table["seats"]
    if s["maxSeats"] > len(seats):
        seats.extend([None] * (s["maxSeats"] - len(seats)))
    elif s["maxSeats"] < len(seats):
        del seats[s["maxSeats"]:]
    table["blinds"] = {"sb": s["smallBlind"], "bb": s["bigBlind"]}
    table["settingsRev"] += 1
    table["votes"] = {user["id"]: True}
    _log(table, f"{user['username']} changed the settings. Everyone has to accept again.")
    _touch(table, now_ms())


def vote(user, table, accept):
    idx = seat_index(table, user["id"])
    if idx is None:
        raise bad("Sit down first", code="not_seated")
    if table["status"] != "setup":
        raise bad("The game has already started", code="game_in_progress")
    if not isinstance(accept, bool):
        raise bad("Accept or decline", code="invalid_vote")
    table["votes"][user["id"]] = accept
    _log(table, f"{user['username']} {'accepted' if accept else 'declined'} the settings")
    _touch(table, now_ms())


def start(user, table):
    if table["hostId"] != user["id"]:
        raise bad("Only the host can start the game", 403, code="not_table_host")
    if table["status"] != "setup":
        raise bad("The game has already started", code="game_in_progress")
    players = seated(table)
    if len(players) < 2:
        raise bad("You need at least two players", code="not_enough_players")
    waiting = [p["name"] for p in players if table["votes"].get(p["userId"]) is not True]
    if waiting:
        declined = [p["name"] for p in players if table["votes"].get(p["userId"]) is False]
        why = f" ({', '.join(declined)} declined)" if declined else ""
        raise bad(f"Everyone has to accept the settings first. Waiting for: {', '.join(waiting)}{why}", code="settings_not_accepted")
    s = table["settings"]
    now = now_ms()
    if s["money"] == "real":
        poor = [p["name"] for p in players if users.get(p["userId"])["balance"] + 1e-9 < s["stack"] / 100]
        if poor:
            raise bad(f"Not enough cash for the ${s['stack'] / 100:,.2f} buy-in: {', '.join(poor)}", code="insufficient_funds")
        for p in players:
            _buy_in(table, users.get(p["userId"]), p, s["stack"])
    else:
        for p in players:
            p["stack"] = s["stack"]
    table["status"] = "playing"
    table["handNo"] = 0
    table["button"] = -1
    table["blinds"] = {"sb": s["smallBlind"], "bb": s["bigBlind"]}
    table["ending"] = False
    _log(table, "The game is on" + (" with real cash" if s["money"] == "real" else " with fake chips"))
    _start_hand(table, now)
    _touch(table, now)


def end_game(user, table):
    if table["hostId"] != user["id"]:
        raise bad("Only the host can end the game", 403, code="not_table_host")
    if table["status"] != "playing":
        raise bad("There is no game to end", code="no_game")
    now = now_ms()
    h = table["hand"]
    if h and h["street"] != "ended":
        table["ending"] = True
        _log(table, "The host is ending the game after this hand")
    else:
        _finish_game(table)
    _touch(table, now)


def _finish_game(table):
    """Everyone cashes out and the table goes back to setup so the settings can change."""
    for i, seat in enumerate(table["seats"]):
        if seat:
            _cash_out(table, seat)
            seat.update({"stack": 0, "busted": False, "leaving": False, "timeouts": 0, "hands": 0})
    table["hand"] = None
    table["status"] = "setup"
    table["ending"] = False
    table["handNo"] = 0
    table["button"] = -1
    s = table["settings"]
    table["blinds"] = {"sb": s["smallBlind"], "bb": s["bigBlind"]}
    table["settingsRev"] += 1
    table["votes"] = {table["hostId"]: True}
    _log(table, "The game is over. Back to the settings.")


def rebuy(user, table):
    idx = seat_index(table, user["id"])
    if idx is None:
        raise bad("You are not at this table", code="not_seated")
    s = table["settings"]
    seat = table["seats"][idx]
    if table["status"] != "playing" or not s["rebuy"]:
        raise bad("Rebuys are off at this table", code="rebuy_not_allowed")
    if seat["stack"] > 0:
        raise bad("You still have chips", code="rebuy_not_allowed")
    h = table["hand"]
    if h and h["street"] != "ended" and h["st"][idx] in ("in", "allin"):
        raise bad("Wait for the hand to finish", code="hand_in_progress")
    if s["money"] == "real":
        _buy_in(table, user, seat, s["stack"])
    else:
        seat["stack"] = s["stack"]
    seat["busted"] = False
    _log(table, f"{seat['name']} rebought")
    now = now_ms()
    _maybe_start(table, now)
    _touch(table, now)


# ---- the hand ----------------------------------------------------------------------

def _order(table, start):
    n = len(table["seats"])
    return [(start + k) % n for k in range(n)]


def _live_seats(table):
    return [i for i, s in enumerate(table["seats"])
            if s and s["stack"] > 0 and not s["leaving"] and not s["busted"]]


def _maybe_start(table, now):
    if table["status"] == "playing" and table["hand"] is None and not table["ending"]:
        _start_hand(table, now)


def _post(h, table, i, amount):
    seat = table["seats"][i]
    pay = min(seat["stack"], amount)
    seat["stack"] -= pay
    h["bets"][i] += pay
    h["contrib"][i] += pay
    if seat["stack"] == 0:
        h["st"][i] = "allin"
    return pay


def _start_hand(table, now):
    live = _live_seats(table)
    if len(live) < 2:
        table["hand"] = None
        return False
    s = table["settings"]
    n = len(table["seats"])
    table["handNo"] += 1
    if s["blindsUp"] and table["handNo"] > 1 and (table["handNo"] - 1) % s["blindsUp"] == 0:
        table["blinds"] = {"sb": table["blinds"]["sb"] * 2, "bb": table["blinds"]["bb"] * 2}
        _log(table, f"Blinds go up to {_fmt(table, table['blinds']['sb'])}/{_fmt(table, table['blinds']['bb'])}")
    bl = table["blinds"]
    nxt = lambda after: next(i for i in _order(table, (after + 1) % n) if i in live)    # noqa: E731
    button = nxt(table["button"])
    table["button"] = button
    if len(live) == 2:
        sb, bb = button, nxt(button)                       # heads-up: the button posts the small blind
    else:
        sb = nxt(button)
        bb = nxt(sb)
    deck = [r + su for r in RANKS for su in SUITS]
    shuffle(deck)
    h = {"no": table["handNo"], "street": "preflop", "button": button, "sb": sb, "bb": bb, "deck": deck, "board": [],
         "hole": [None] * n, "st": ["out"] * n, "bets": [0] * n, "contrib": [0] * n, "acted": [False] * n,
         "currentBet": bl["bb"], "minRaise": bl["bb"], "fullBase": bl["bb"], "toAct": None, "deadline": None,
         "runout": False, "nextAt": None, "result": None, "last": [None] * n}
    for i in live:
        h["st"][i] = "in"
    table["hand"] = h
    for i in _order(table, (button + 1) % n):
        if i in live:
            h["hole"][i] = [deck.pop(), deck.pop()]
            table["seats"][i]["hands"] += 1
            if table["seats"][i].get("userId"):
                activity.safe_record(users.get(table["seats"][i]["userId"]), "poker", f"{table['id']}:{table['handNo']}:{table['seats'][i]['userId']}", now=now)
    _post(h, table, sb, bl["sb"])
    _post(h, table, bb, bl["bb"])
    _log(table, f"Hand {h['no']}. {table['seats'][button]['name']} has the button.")
    first = sb if len(live) == 2 else nxt(bb)
    actor = _next_actor(table, first)
    if actor is None:
        _round_over(table, now)
    else:
        _set_actor(table, actor, now)
    return True


def _next_actor(table, start):
    h = table["hand"]
    for i in _order(table, start):
        if h["st"][i] == "in" and (not h["acted"][i] or h["bets"][i] < h["currentBet"]):
            return i
    return None


def _set_actor(table, i, now):
    h = table["hand"]
    h["toAct"] = i
    secs = table["settings"]["turnSeconds"]
    h["deadline"] = now + secs * 1000 if secs else None


def _live_in_hand(h):
    return [i for i, st in enumerate(h["st"]) if st in ("in", "allin")]


def _legal(table, i):
    """What seat i may do right now, in units."""
    h = table["hand"]
    seat = table["seats"][i]
    stack = seat["stack"]
    to_call = max(0, h["currentBet"] - h["bets"][i])
    max_to = h["bets"][i] + stack
    can_raise = (not h["acted"][i]) and stack > to_call
    min_to = min(h["currentBet"] + h["minRaise"], max_to)
    return {"toCall": min(to_call, stack), "canCheck": to_call == 0, "canCall": to_call > 0,
            "canRaise": can_raise, "minRaiseTo": min_to, "maxRaiseTo": max_to, "currentBet": h["currentBet"]}


def act(user, table, action, amount=None, now=None):
    now = now or now_ms()
    idx = seat_index(table, user["id"])
    h = table["hand"]
    if idx is None:
        raise bad("You are not at this table", code="not_seated")
    if not h or h["street"] == "ended" or h["runout"] or h["toAct"] != idx:
        raise bad("It is not your turn", code="not_your_turn")
    seat = table["seats"][idx]
    legal = _legal(table, idx)
    name = seat["name"]
    if action == "fold":
        _fold(table, idx, now, manual=True)
        _touch(table, now)
        return
    if action == "check":
        if not legal["canCheck"]:
            raise bad("You can't check. There is a bet to call.", code="invalid_move")
        _log(table, f"{name} checks")
        h["last"][idx] = "check"
    elif action == "call":
        if not legal["canCall"]:
            raise bad("There is nothing to call. You can check.", code="invalid_move")
        pay = _post(h, table, idx, legal["toCall"])
        _log(table, f"{name} calls {_fmt(table, pay)}" + (" and is all in" if h["st"][idx] == "allin" else ""))
        h["last"][idx] = "call"
    elif action in ("raise", "allin"):
        target = legal["maxRaiseTo"] if action == "allin" else amount
        if isinstance(target, bool) or not isinstance(target, int):
            raise bad("Pick how much to raise to", code="invalid_move")
        if target <= h["currentBet"]:
            if action == "allin" and legal["toCall"] > 0:          # all in for less than the bet is a call
                pay = _post(h, table, idx, legal["toCall"])
                _log(table, f"{name} calls {_fmt(table, pay)} and is all in")
                h["last"][idx] = "call"
                h["acted"][idx] = True
                seat["timeouts"] = 0
                _after_action(table, idx, now)
                _touch(table, now)
                return
            raise bad(f"Raise to more than {h['currentBet']}", code="invalid_move")
        if not legal["canRaise"]:
            raise bad("You can't raise right now. The betting wasn't re-opened.", code="invalid_move")
        if target > legal["maxRaiseTo"]:
            raise bad(f"You only have {legal['maxRaiseTo'] - h['bets'][idx]} to bet", code="invalid_move")
        if target < legal["minRaiseTo"]:
            raise bad(f"The smallest raise is to {legal['minRaiseTo']}", code="invalid_move")
        prev = h["currentBet"]
        _post(h, table, idx, target - h["bets"][idx])
        h["currentBet"] = target
        size = target - prev
        if size >= h["minRaise"]:
            h["minRaise"] = size                                   # a full raise: everyone else may act again
            h["fullBase"] = target
            _reopen(h, idx)
        elif target - h["fullBase"] >= h["minRaise"]:
            h["fullBase"] = target                                 # small all-ins that add up to a full raise
            _reopen(h, idx)
        verb = "bets" if prev == 0 else "raises to"
        h["last"][idx] = "bet" if prev == 0 else "raise"
        _log(table, f"{name} {verb} {_fmt(table, target)}" + (" and is all in" if h["st"][idx] == "allin" else ""))
    else:
        raise bad("Unknown action", code="invalid_action")
    h["acted"][idx] = True
    seat["timeouts"] = 0
    _after_action(table, idx, now)
    _touch(table, now)


def _reopen(h, raiser):
    for j, st in enumerate(h["st"]):
        if j != raiser and st == "in":
            h["acted"][j] = False
            h["last"][j] = None


def _fold(table, idx, now, manual=False):
    h = table["hand"]
    h["st"][idx] = "folded"
    h["acted"][idx] = True
    if manual:
        table["seats"][idx]["timeouts"] = 0
    _log(table, f"{table['seats'][idx]['name']} folds")
    _after_action(table, idx, now)


def _after_action(table, idx, now):
    h = table["hand"]
    n = len(table["seats"])
    alive = _live_in_hand(h)
    if len(alive) == 1:
        _end_by_fold(table, alive[0], now)
        return
    nxt = _next_actor(table, (idx + 1) % n)
    if nxt is not None:
        _set_actor(table, nxt, now)
    else:
        _round_over(table, now)


def _round_over(table, now):
    h = table["hand"]
    n = len(table["seats"])
    alive = _live_in_hand(h)
    h["toAct"], h["deadline"] = None, None
    if len(alive) == 1:
        _end_by_fold(table, alive[0], now)
        return
    can_act = [i for i in alive if h["st"][i] == "in"]
    if h["street"] == "river":
        _showdown(table, now)
    elif len(can_act) <= 1:
        h["runout"] = True                                         # nobody can bet any more: deal it out
        h["nextAt"] = now + RUNOUT_MS
        _log(table, "All in. Cards on the table.")
    else:
        _deal_street(table)
        actor = _next_actor(table, (h["button"] + 1) % n)
        _set_actor(table, actor, now)


def _deal_street(table):
    h = table["hand"]
    nxt = {"preflop": "flop", "flop": "turn", "turn": "river"}[h["street"]]
    h["deck"].pop()                                                # burn card
    for _ in range(3 if nxt == "flop" else 1):
        h["board"].append(h["deck"].pop())
    h["street"] = nxt
    n = len(table["seats"])
    h["bets"], h["acted"], h["last"] = [0] * n, [False] * n, [None] * n
    h["currentBet"], h["minRaise"], h["fullBase"] = 0, table["blinds"]["bb"], 0
    _log(table, f"{nxt.capitalize()}: {_cards(h['board'])}")


def _runout_step(table, now):
    h = table["hand"]
    if h["street"] == "river":
        _showdown(table, now)
        return
    _deal_street(table)
    h["nextAt"] = now + RUNOUT_MS


def _end_by_fold(table, winner, now):
    h = table["hand"]
    total = sum(h["contrib"])
    table["seats"][winner]["stack"] += total
    h["street"] = "ended"
    h["runout"] = False
    h["toAct"], h["deadline"] = None, None
    h["result"] = {"reason": "fold", "pots": [{"amount": total, "returned": False,
                                               "winners": [{"seat": winner, "amount": total, "hand": None}]}],
                   "shown": {}, "board": list(h["board"])}
    h["nextAt"] = now + FOLD_WIN_MS
    _log(table, f"{table['seats'][winner]['name']} wins {_fmt(table, total)}")


def _build_pots(h):
    """Main pot and side pots from what each seat put in. Folded money stays in, but folded seats can't win it."""
    remaining = list(h["contrib"])
    pots = []
    while any(r > 0 for r in remaining):
        live = [i for i, r in enumerate(remaining) if r > 0 and h["st"][i] in ("in", "allin")]
        if not live:
            if pots:
                pots[-1]["amount"] += sum(remaining)
            break
        level = min(remaining[i] for i in live)
        amount = 0
        for i, r in enumerate(remaining):
            take = min(level, r)
            amount += take
            remaining[i] -= take
        if pots and pots[-1]["eligible"] == live:
            pots[-1]["amount"] += amount
        else:
            pots.append({"amount": amount, "eligible": live})
    return pots


def _showdown(table, now):
    h = table["hand"]
    n = len(table["seats"])
    alive = _live_in_hand(h)
    scores = {i: best_hand(h["hole"][i] + h["board"]) for i in alive}
    order = _order(table, (h["button"] + 1) % n)
    results = []
    for pot in _build_pots(h):
        elig = pot["eligible"]
        if len(elig) == 1:
            winners = elig                                         # an uncalled bet comes back to its owner
        else:
            top = max(scores[i] for i in elig)
            winners = [i for i in elig if scores[i] == top]
        winners.sort(key=order.index)
        share, extra = divmod(pot["amount"], len(winners))
        paid = []
        for k, i in enumerate(winners):
            amt = share + (1 if k < extra else 0)                  # odd chips go to the first seats left of the button
            table["seats"][i]["stack"] += amt
            paid.append({"seat": i, "amount": amt, "hand": describe(scores[i]) if len(elig) > 1 else None})
        results.append({"amount": pot["amount"], "returned": len(elig) == 1, "winners": paid})
    h["street"] = "ended"
    h["runout"] = False
    h["toAct"], h["deadline"] = None, None
    h["result"] = {"reason": "showdown", "pots": results, "board": list(h["board"]),
                   "shown": {str(i): h["hole"][i] for i in alive},
                   "hands": {str(i): describe(scores[i]) for i in alive}}
    h["nextAt"] = now + SHOWDOWN_MS
    for r in results:
        for w in r["winners"]:
            if not r["returned"]:
                _log(table, f"{table['seats'][w['seat']]['name']} wins {_fmt(table, w['amount'])} with {w['hand']}")


def _timeout(table, now):
    h = table["hand"]
    idx = h["toAct"]
    seat = table["seats"][idx]
    seat["timeouts"] += 1
    if seat["timeouts"] >= MAX_TIMEOUTS:
        seat["leaving"] = True
        _log(table, f"{seat['name']} timed out too many times and is out")
    if max(0, h["currentBet"] - h["bets"][idx]) == 0:
        h["acted"][idx] = True
        h["last"][idx] = "check"
        _log(table, f"{seat['name']} checks (out of time)")
        _after_action(table, idx, now)
    else:
        _log(table, f"{seat['name']} is out of time")
        h["st"][idx] = "folded"
        h["acted"][idx] = True
        _after_action(table, idx, now)


def _hand_cleanup(table, now):
    """The pause after a hand is over: stand up leavers and the busted, then deal the next one."""
    s = table["settings"]
    for i, seat in enumerate(list(table["seats"])):
        if seat is None:
            continue
        if seat["leaving"]:
            _stand_up(table, i)
        elif seat["stack"] == 0:
            if s["rebuy"]:
                seat["busted"], seat["bustedAt"] = True, now
                _log(table, f"{seat['name']} is out of chips")
            else:
                _stand_up(table, i, "is out of chips")
    if table["id"] not in tables():
        return
    table["hand"] = None
    if table["ending"]:
        _finish_game(table)
    else:
        _start_hand(table, now)


def _close_idle(table):
    for i in range(len(table["seats"])):
        _stand_up(table, i, "was sent home")
    tables().pop(table["id"], None)


def _advance_once(table, now):
    if table["status"] == "setup":
        if now - table["lastActivity"] > IDLE_SETUP_MS:
            _close_idle(table)
            return True
        return False
    h = table["hand"]
    if h is None:
        if len(_live_seats(table)) >= 2 and not table["ending"]:
            _start_hand(table, now)
            return True
    elif h["street"] == "ended":
        if now >= h["nextAt"]:
            _hand_cleanup(table, now)
            return True
    elif h["runout"]:
        if now >= h["nextAt"]:
            _runout_step(table, now)
            return True
    elif h["toAct"] is not None and h["deadline"] and now >= h["deadline"]:
        _timeout(table, now)
        return True
    for i, seat in enumerate(table["seats"]):
        if seat and seat["busted"] and now - seat.get("bustedAt", now) > BUST_WAIT_MS and (h is None or h["street"] == "ended" or h["st"][i] == "out"):
            _stand_up(table, i, "took too long to rebuy")
            return True
    return False


def catch_up(table, now=None):
    """Runs whatever timers are due (turn clocks, the pause between hands). Returns True if anything changed."""
    now = now or now_ms()
    changed = False
    for _ in range(8):
        tid = table["id"]
        if not _advance_once(table, now):
            break
        changed = True
        if tid not in tables():
            return True
    if changed:
        _touch(table, now)
    return changed


def tick(now=None):
    """Called every second by the server. Returns the ids of the tables that changed."""
    now = now or now_ms()
    out = []
    for table in list(tables().values()):
        tid = table["id"]
        if catch_up(table, now):
            out.append(tid)
    return out


# ---- what each player is allowed to see --------------------------------------------

def _seat_view(table, i, viewer_id):
    seat = table["seats"][i]
    if seat is None:
        return None
    h = table["hand"]
    st = h["st"][i] if h else "out"
    cards = None
    if h and h["hole"][i] and st in ("in", "allin"):
        revealed = h["street"] == "ended" and str(i) in (h["result"] or {}).get("shown", {})
        if seat["userId"] == viewer_id or revealed or (h["runout"] and st in ("in", "allin")):
            cards = h["hole"][i]
        else:
            cards = ["back", "back"]
    elif h and h["street"] == "ended" and str(i) in (h["result"] or {}).get("shown", {}):
        cards = h["result"]["shown"][str(i)]
    return {"seat": i, "userId": seat["userId"], "name": seat["name"], "stack": seat["stack"],
            "bet": h["bets"][i] if h else 0, "status": st, "cards": cards, "isMe": seat["userId"] == viewer_id,
            "last": h["last"][i] if h and st == "in" and h["street"] != "ended" else None,
            "vote": table["votes"].get(seat["userId"]), "timeouts": seat["timeouts"], "busted": seat["busted"],
            "leaving": seat["leaving"], "isHost": seat["userId"] == table["hostId"]}


def view(table, viewer_id, now=None):
    now = now or now_ms()
    s = table["settings"]
    me = seat_index(table, viewer_id)
    h = table["hand"]
    hv = None
    if h:
        hv = {"no": h["no"], "street": h["street"], "board": list(h["board"]), "pot": sum(h["contrib"]),
              "currentBet": h["currentBet"], "toAct": h["toAct"], "deadline": h["deadline"], "runout": h["runout"],
              "button": h["button"], "sb": h["sb"], "bb": h["bb"], "nextAt": h["nextAt"], "result": h["result"],
              "actions": None, "mine": None}
        if me is not None and h["toAct"] == me and not h["runout"] and h["street"] != "ended":
            hv["actions"] = _legal(table, me)
        if me is not None and h["hole"][me] and h["st"][me] in ("in", "allin"):
            hv["mine"] = live_hand(h["hole"][me], h["board"])
    host = next((p for p in seated(table) if p["userId"] == table["hostId"]), None)
    return {"id": table["id"], "name": table["name"], "visibility": table["visibility"], "status": table["status"],
            "hostId": table["hostId"], "hostName": host["name"] if host else "", "ending": table["ending"],
            "code": table["code"] if (me is not None and table["code"]) else None,
            "settings": s, "scale": scale_of(table), "settingsRev": table["settingsRev"],
            "blinds": table["blinds"], "handNo": table["handNo"], "mySeat": me, "isHost": table["hostId"] == viewer_id,
            "seats": [_seat_view(table, i, viewer_id) for i in range(len(table["seats"]))],
            "hand": hv, "log": table["log"][-40:], "serverNow": now, "v": table["v"],
            "votes": {uid: v for uid, v in table["votes"].items()}}


def summary(table, viewer_id):
    s = table["settings"]
    host = next((p for p in seated(table) if p["userId"] == table["hostId"]), None)
    return {"id": table["id"], "name": table["name"], "visibility": table["visibility"], "status": table["status"],
            "money": s["money"], "scale": scale_of(table), "bigBlind": s["bigBlind"], "smallBlind": s["smallBlind"],
            "stack": s["stack"], "maxSeats": s["maxSeats"], "hostName": host["name"] if host else "",
            "players": [p["name"] for p in seated(table)], "handNo": table["handNo"],
            "mine": seat_index(table, viewer_id) is not None, "full": not any(x is None for x in table["seats"])}


def lobby(viewer_id):
    rows = []
    for t in tables().values():
        if t["visibility"] == "public" or seat_index(t, viewer_id) is not None:
            rows.append(summary(t, viewer_id))
    rows.sort(key=lambda r: (not r["mine"], r["status"] != "playing", -len(r["players"]), r["name"].lower()))
    return rows
