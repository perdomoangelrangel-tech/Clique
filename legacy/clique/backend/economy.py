"""Every number that shapes Clique's economy, in one place. All money is pretend money.

Each value can be overridden with an environment variable of the same name (shown in capitals). Nothing else in the code
has these figures written into it, so changing a price, a reward or a limit means changing it here (or in the
environment) and restarting. ECONOMY.md explains the reasoning behind the starting values.
"""
import json
import os


def _env_float(name, default, low=0.0, high=1e12):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return float(default)
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit(f"{name} must be a number, got {raw!r}")
    if not low <= value <= high:
        raise SystemExit(f"{name} must be between {low:g} and {high:g}")
    return value


def _env_int(name, default, low=0, high=10 ** 9):
    return int(_env_float(name, default, low, high))


def _env_bool(name, default):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ---- the two accounts ---------------------------------------------------------------------------------------------
# WEEKLY account: the chips for this week. Markets, casino games and poker all play from it. It is refilled when a new
#   week starts, and it can never be moved into the accumulated account.
# ACCUMULATED account: what you keep. Weekly rewards land here; the Store and the Stock Exchange spend from it.
# There is deliberately no transfer between the two (see ECONOMY.md for why).

WEEKLY_ALLOCATION = _env_float("WEEKLY_ALLOCATION", _env_float("WEEKLY_BONUS", 1000.0))   # older WEEKLY_BONUS still works

# How a new week treats what is left in the weekly account:
#   reset  (default): the weekly account becomes exactly WEEKLY_ALLOCATION. Leftovers are not carried over, so every week
#          is a fresh, equal start and the leaderboard measures the week and nothing else. Positions you still hold stay
#          yours (see ECONOMY.md, "Pending bets at the end of a week").
#   topup:  WEEKLY_ALLOCATION is added on top of whatever is left (the old "pass Go" behaviour).
WEEKLY_RESET = os.environ.get("WEEKLY_CLOSE_MODE", "reset").strip().lower() != "topup"

# ---- Wednesday bonus ---------------------------------------------------------------------------------------------
# Every week, on Wednesday at 12:00 (the site's time zone), everybody who has an account by then is given this much in the WEEKLY account.
# It is marked external, so it never counts as winnings. 0 turns it off.
MIDWEEK_BONUS = _env_float("MIDWEEK_BONUS", 500.0)

# ---- a vote on added funds ----------------------------------------------------------------------------------------
# Money added with the host's "Add funds" box waits (on hold, not in any account) while everybody else votes. The vote ends as soon as the
# result cannot change, when everybody has voted, or after this many hours, whichever comes first (backend/fundvotes.py).
FUNDS_VOTE_HOURS = _env_float("FUNDS_VOTE_HOURS", 24.0, 0.01, 24 * 30)

# ---- weekly rewards -----------------------------------------------------------------------------------------------
# Paid into the ACCUMULATED account when a week closes, by final position in the circle's weekly leaderboard.
# Position 1 is the first number. Anybody active who finishes below the last listed position gets PARTICIPATION_REWARD.
WEEKLY_REWARDS = [400.0, 250.0, 150.0, 100.0, 50.0]
PARTICIPATION_REWARD = 25.0
if os.environ.get("WEEKLY_REWARDS"):                         # e.g. WEEKLY_REWARDS="400,250,150,100,50"
    try:
        WEEKLY_REWARDS = [float(x) for x in os.environ["WEEKLY_REWARDS"].split(",") if x.strip()]
    except ValueError:
        raise SystemExit("WEEKLY_REWARDS must be a comma-separated list of numbers, like 400,250,150")
    if not WEEKLY_REWARDS or any(x < 0 for x in WEEKLY_REWARDS):
        raise SystemExit("WEEKLY_REWARDS needs at least one amount, and none can be negative")
PARTICIPATION_REWARD = _env_float("PARTICIPATION_REWARD", PARTICIPATION_REWARD)

# "Active" means a real move that week: a bet on a market or a casino round (practice rounds do not count).
REWARD_MIN_MOVES = _env_int("REWARD_MIN_MOVES", 1, 1)
# A circle needs at least this many active members in a week for any reward to be paid.
REWARD_MIN_ACTIVE = _env_int("REWARD_MIN_ACTIVE", 2, 2)
# Rewards are scaled for small circles: with n active members the table is multiplied by
#   min(1, (n - 1) / (REWARD_FULL_AT - 1)), so 2 active members get 25%, 3 get 50%, 4 get 75%, 5 or more get 100%.
REWARD_FULL_AT = _env_int("REWARD_FULL_AT", 5, 2)
# Somebody in several circles is paid for the best of their finishes only, so extra circles cannot be used to farm rewards.
REWARD_MAX_PER_USER_PER_WEEK = _env_int("REWARD_MAX_PER_USER_PER_WEEK", 1, 1)


def reward_scale(active):
    if active < REWARD_MIN_ACTIVE:
        return 0.0
    return min(1.0, (active - 1) / (REWARD_FULL_AT - 1))


def reward_for_position(position, active):
    """Dollars for finishing `position` (1 = first) in a circle with `active` active members. 0 if nothing is paid."""
    scale = reward_scale(active)
    if scale <= 0:
        return 0.0
    base = WEEKLY_REWARDS[position - 1] if position <= len(WEEKLY_REWARDS) else PARTICIPATION_REWARD
    return round(base * scale, 2)


# ---- the weekly minimum -------------------------------------------------------------------------------------------
# To stay in the weekly challenge a person has to take part: bet in at least WEEKLY_MIN_POLL_BETS poll(s) and play at least
# WEEKLY_MIN_CASINO_BETS casino rounds during the week. Anybody who has not when the week closes loses it automatically: they
# take the week's punishment (as the losers of the week, in place of whoever finished last) and earn no reward.
# Set both to 0 to switch the rule off. Practice (demo) rounds do not count. An account created during the week is exempt
# for that first, partial week. The rule starts with the first week that closes after it was introduced (see ECONOMY.md).
WEEKLY_MIN_POLL_BETS = _env_int("WEEKLY_MIN_POLL_BETS", 1, 0, 1000)
WEEKLY_MIN_CASINO_BETS = _env_int("WEEKLY_MIN_CASINO_BETS", 25, 0, 10000)
WEEKLY_REMIND_H = _env_float("WEEKLY_REMIND_H", 24.0, 0, 24 * 7)      # a reminder goes to people still short this many hours before the week closes (0 = no reminder)

# ---- the account ledger -------------------------------------------------------------------------------------------
LEDGER_KEEP = _env_int("LEDGER_KEEP", 400, 50)               # newest rows kept in full per person; older ones are summed up by week and reason

# ---- store and stock exchange use the ACCUMULATED account --------------------------------------------------------
STOCK_SPREAD_BPS = _env_float("STOCK_SPREAD_BPS", 30.0, 0, 1000)   # total bid/ask gap in basis points (30 = 0.30%); half on each side
STOCK_QUOTE_TTL_S = _env_float("STOCK_QUOTE_TTL_S", 15.0, 1, 600)
STOCK_MAX_SLIPPAGE_BPS = _env_float("STOCK_MAX_SLIPPAGE_BPS", 50.0, 0, 5000)   # how far the price may move between quote and fill
STOCK_MAX_ORDER_SHARES = _env_int("STOCK_MAX_ORDER_SHARES", 100_000, 1)
STOCK_TICK_S = _env_float("STOCK_TICK_S", 1.0, 0.2, 60)
STOCK_SAVE_EVERY_S = _env_float("STOCK_SAVE_EVERY_S", 20.0, 1, 3600)
STOCK_CATCHUP_MAX_S = _env_int("STOCK_CATCHUP_MAX_S", 3 * 86400, 60)   # after a longer outage the market is simulated as if it were only this long

# ---- voice rooms --------------------------------------------------------------------------------------------------
VOICE_MAX_PEOPLE = _env_int("VOICE_MAX_PEOPLE", 8, 2, 16)
VOICE_STALE_S = _env_int("VOICE_STALE_S", 35, 10, 600)
# STUN/TURN servers, as JSON, e.g. [{"urls":"stun:stun.l.google.com:19302"}]. TURN is only needed for people behind
# strict networks. Alternatively set TURN_URL + TURN_SECRET (a coturn "use-auth-secret" server) and short-lived
# credentials are made for each person.
_default_ice = [{"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]}]
try:
    ICE_SERVERS = json.loads(os.environ["ICE_SERVERS"]) if os.environ.get("ICE_SERVERS") else _default_ice
except ValueError:
    raise SystemExit("ICE_SERVERS must be valid JSON")
TURN_URL = os.environ.get("TURN_URL", "").strip()                # e.g. turn:turn.example.com:3478
TURN_SECRET = os.environ.get("TURN_SECRET", "").strip()
TURN_TTL_S = _env_int("TURN_TTL_S", 3600, 60)

# ---- editing a published poll -------------------------------------------------------------------------------------
EDIT_MIN_LEAD_MS = 5 * 60_000                                    # a new closing time must be at least this far ahead
EDIT_EXIT_WINDOW_H = _env_float("EDIT_EXIT_WINDOW_H", 48.0, 0, 24 * 30)   # how long holders can walk away at cost after a material change

# ---- profile pictures ---------------------------------------------------------------------------------------------
AVATAR_MAX_BYTES = _env_int("AVATAR_MAX_BYTES", 1_500_000, 10_000, 20_000_000)
AVATAR_MIN_PX, AVATAR_MAX_PX = 64, 4096


# ======================================================================================================================
# Loans, ranks, weekly challenges, milestones and friend transfers (ECONOMY.md, sections 7 to 11, explains every one).
# All of it is pretend money. The definitions of ranks, XP, challenges and milestones are data in backend/rules.py; the
# numbers below are the knobs, each with an environment variable of the same name.
# ======================================================================================================================

# ---- loans (they land in the WEEKLY account, and are repaid from it) -----------------------------------------------
LOANS_ENABLED = _env_bool("LOANS_ENABLED", True)
LOAN_MIN = _env_float("LOAN_MIN", 10.0, 1, 1e6)                              # smallest loan
LOAN_MAX_PCT_OF_ALLOCATION = _env_float("LOAN_MAX_PCT_OF_ALLOCATION", 50.0, 1, 100)   # one loan is at most this share of the weekly allocation (500 of 1,000)
LOAN_FEE = _env_float("LOAN_FEE", 0.0, 0, 1e6)                               # a fixed amount per loan, always shown before you borrow. 0 = interest-free
LOAN_CUTOFF_H = _env_float("LOAN_CUTOFF_H", 24.0, 0, 24 * 6)                 # no new loans in the last this-many hours of the week
LOAN_MIN_ACCOUNT_AGE_H = _env_float("LOAN_MIN_ACCOUNT_AGE_H", 24.0, 0, 24 * 365)   # a brand-new account cannot borrow yet
LOAN_MAX_PER_WEEK = _env_int("LOAN_MAX_PER_WEEK", 2, 1, 50)                  # loans started in one week, repaid or not
# A loan you did not manage to repay before the week closed stays owed. Of the NEXT weekly allocation, this share goes to it
# first, and the rest is yours to spend (so a debt can never leave you with nothing to play with).
LOAN_ALLOC_REPAY_PCT = _env_float("LOAN_ALLOC_REPAY_PCT", 50.0, 1, 100)

# ---- ranks, XP, challenges, milestones ----------------------------------------------------------------------------
GOALS_ENABLED = _env_bool("GOALS_ENABLED", True)
# An action only counts (for XP, challenges and milestones) when real money was at stake and the stake was at least this much.
# Practice (demo) rounds, rejected requests and merely looking at a page never count.
QUALIFY_MIN_STAKE = _env_float("QUALIFY_MIN_STAKE", 1.0, 0.1, 1e6)
REWARD_SCALE = _env_float("REWARD_SCALE", 1.0, 0, 100)                       # multiplies every challenge and milestone money reward
XP_SCALE = _env_float("XP_SCALE", 1.0, 0, 100)                               # multiplies every XP award (not the thresholds)
RANK_XP_SCALE = _env_float("RANK_XP_SCALE", 1.0, 0.01, 100)                  # multiplies every rank threshold (2 = twice as slow)
# "Win $X in a game" goals add up the profit of each winning round, but a single round never counts for more than this, so a huge stake
# is not a faster way to reach the goal (it would only be a bigger risk). Goals about a multiplier ignore the stake entirely.
GAME_WIN_CREDIT_CAP = _env_float("GAME_WIN_CREDIT_CAP", 25.0, 1, 1e6)

# ---- friend-to-friend transfers (weekly to weekly, or accumulated to accumulated: the sender chooses) --------------
TRANSFERS_ENABLED = _env_bool("TRANSFERS_ENABLED", True)
# Which accounts money can be sent FROM. Money always arrives in the SAME account it left (weekly to weekly, accumulated to accumulated): there is
# no option anywhere to turn one into the other.
_names = [a.strip() for a in os.environ.get("TRANSFER_ACCOUNTS", "weekly,accumulated").lower().split(",") if a.strip()]
if not _names or any(a not in ("weekly", "accumulated") for a in _names):
    raise SystemExit("TRANSFER_ACCOUNTS must list weekly and/or accumulated, for example weekly,accumulated")
TRANSFER_ACCOUNTS = tuple(a for a in ("weekly", "accumulated") if a in _names)
TRANSFER_DAILY_LIMIT = _env_float("TRANSFER_DAILY_LIMIT", 250.0, 1, 1e9)     # most a person can send from their ACCUMULATED account in one calendar day
TRANSFER_WEEKLY_DAILY_LIMIT = _env_float("TRANSFER_WEEKLY_DAILY_LIMIT", 500.0, 1, 1e9)   # the same, for the WEEKLY account (its own allowance: half the weekly allocation)
# Weekly chips can only top a friend up to this share of the weekly allocation (100 = up to the allocation, like a loan), never above it, so
# friends cannot pool chips into one account to play with more than everybody else. 0 switches this limit off.
TRANSFER_WEEKLY_RECEIVER_PCT = _env_float("TRANSFER_WEEKLY_RECEIVER_PCT", 100.0, 0, 1000)
TRANSFER_MIN = _env_float("TRANSFER_MIN", 1.0, 0.01, 1e6)
TRANSFER_NOTE_MAX = _env_int("TRANSFER_NOTE_MAX", 80, 0, 500)
TRANSFER_PW_MAX_FAILS = _env_int("TRANSFER_PW_MAX_FAILS", 5, 1, 100)         # wrong transfer passwords in a row before a lock-out
TRANSFER_PW_LOCK_MIN = _env_float("TRANSFER_PW_LOCK_MIN", 15.0, 1, 24 * 60)  # how long the lock-out lasts
TRANSFER_CODE_MIN = _env_float("TRANSFER_CODE_MIN", 15.0, 1, 24 * 60)        # how long an emailed reset code works
