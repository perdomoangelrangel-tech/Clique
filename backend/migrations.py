"""Changes to the shape of saved data. Each one runs once, never loses money, and writes down what it did.

The database file records which step it has reached (meta.schema), so starting the server any number of times is safe,
and a copy of db.json is made before every start-up (see store.py), so any step can be undone by putting that copy back.
"""
from . import economy, ledger
from .util import now_ms, week_key

SCHEMA = 5


def split_accounts(d):
    """Version 2: one balance becomes two accounts.

    The old balance is the WEEKLY account, up to the weekly allocation (economy.WEEKLY_ALLOCATION, $1,000 to start with).
    Anything above that moves to the ACCUMULATED account, so people who had built up more keep all of it, in the account
    the Store and the Stock Exchange spend from. Someone with less than the allocation keeps it all in the weekly account
    (they get the full allocation at the next refill). Total money is exactly what it was.

    This week's leaderboard is left undisturbed: the move is recorded as money that left the weekly account from outside
    play, so nobody's weekly performance changes because of it."""
    alloc = ledger.to_cents(economy.WEEKLY_ALLOCATION)
    wk = week_key()
    moved_total, people = 0, 0
    from . import weekly                                    # for the previous week's snapshot (where the week started from)
    for u in d["users"].values():
        if "accum" in u:
            continue
        total = ledger.to_cents(u.get("balance", 0.0))
        weekly_part = min(total, alloc)
        accum_part = total - weekly_part
        # where this week's performance should be measured from: the held value at the last close, as before
        start = weekly.start_value(u, wk)
        deposits = u["stats"].get(wk, {}).get("deposits", 0)
        u["balance"] = ledger.to_dollars(weekly_part)
        u["accum"] = ledger.to_dollars(accum_part)
        u["wk"] = {"week": wk, "start_c": ledger.to_cents(start), "ext_c": ledger.to_cents(deposits) - accum_part}
        ledger.opening(u, "weekly", weekly_part, "Balance carried over when the two accounts were introduced")
        ledger.opening(u, "accumulated", accum_part, "Balance carried over when the two accounts were introduced")
        moved_total += accum_part
        people += 1
    d["meta"]["accounts_migration"] = {"at": now_ms(), "people": people, "movedToAccumulated": moved_total / 100,
                                       "allocation": economy.WEEKLY_ALLOCATION}
    return people


def retire_horses(d):
    """Version 3: the Horses game is gone. Anything still riding on a race is paid back, so nobody loses money to the removal.

    A bet on a race that had not been settled yet gets its stake back in full (a real bet into the weekly account, with a
    transaction id so this can never pay twice; a practice bet into the practice wallet). Races already settled are not
    touched: their winnings were paid when they finished. Then the race state is dropped and the horse wins are taken off the
    big-wins board. People's own round history keeps its Horses lines, because that is what happened."""
    h = d.pop("horse", None) or {}
    race = h.get("race") or {}
    refunded_c, bets = 0, 0
    for key, bet in (race.get("bets") or {}).items():
        if bet.get("settled"):
            continue
        uid, _, kind = key.partition(":")
        user = d["users"].get(uid)
        if user is None:
            continue
        stake_c = int(bet["stake_c"])
        if kind == "demo":
            demo = user.get("demo") or {}
            if "balance" in demo:
                demo["balance"] = round(demo["balance"] + stake_c / 100, 2)
        else:
            ledger.post(user, "weekly", ledger.to_dollars(stake_c), "casino.horses", ref=race.get("id"),
                        txid=f"horse:retired:{race.get('id')}:{key}", note="Stake returned when Horses was removed")
            refunded_c += stake_c
        bets += 1
    d["feed"] = [w for w in d.get("feed", []) if w.get("game") != "horses"]
    d["meta"]["horses_retired"] = {"at": now_ms(), "betsRefunded": bets, "refunded": refunded_c / 100}
    return bets


def add_goals(d):
    """Version 4: loans, ranks, weekly challenges, milestones and friend transfers. Purely additive: no balance, position or record
    that exists is changed. New empty containers are added, and each person gets what the old records reliably show:
      * milestone counters (poll bets, casino rounds, weeks taken part in, games tried, share trades, polls proposed, circles),
      * the challenge facts of the week already under way,
    and nothing else. XP starts at 0 (nobody is promoted for the past), days taken part in start at 0, no loan exists."""
    from . import challenges, milestones, progress
    d.setdefault("loans", {})
    d.setdefault("challenges", {})
    d.setdefault("transfers", {})
    wk = week_key()
    n_users = n_tiers = 0
    for u in d["users"].values():
        g = progress.state(u)
        n_tiers += milestones.backfill(u, d)
        challenges.backfill_week(u, d, wk)
        s = (u.get("stats") or {}).get(wk) or {}
        if s.get("marketBets", 0) + s.get("gamesPlayed", 0) > 0:
            g["lastWeek"] = wk                                   # this week is already counted in "weeks taken part in"
        n_users += 1
    d["meta"]["goals_migration"] = {"at": now_ms(), "people": n_users, "milestoneTiersReached": n_tiers}
    return n_users


def add_game_goals(d):
    """Version 5: goals about one game (play N rounds of Blackjack, reach N\u00d7 in Tower, win $N in Chicken...). Additive again: nothing that exists
    changes, and each person's per-game numbers are filled from the round history the old records still hold (never invented). A milestone
    unlocked that way is not paid until the person claims it."""
    from . import milestones, progress
    tiers = 0
    for u in d["users"].values():
        progress.state(u)
        tiers += milestones.backfill_games(u)
    d["meta"]["game_goals_migration"] = {"at": now_ms(), "people": len(d["users"]), "milestoneTiersReached": tiers}
    return tiers


def run(d):
    """Brings loaded data up to date. Returns the list of steps that ran."""
    ran = []
    meta = d.setdefault("meta", {})
    version = meta.get("schema", 1)
    if version < 2:
        split_accounts(d)
        ran.append("split_accounts")
    if version < 3:
        retire_horses(d)
        ran.append("retire_horses")
    if version < 4:
        add_goals(d)
        ran.append("add_goals")
    if version < 5:
        add_game_goals(d)
        ran.append("add_game_goals")
    meta["schema"] = SCHEMA
    return ran
