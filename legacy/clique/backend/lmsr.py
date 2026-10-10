"""Automated market maker (LMSR) so every market always has a price, like Polymarket's.

State is a vector q (shares outstanding per outcome) and a liquidity constant b.
price_i = exp(q_i/b) / sum_j exp(q_j/b), and prices always add up to 100%.

The market maker's cash account is C(q) = b * ln(sum_j exp(q_j/b)). Moving from q to q' costs C(q') - C(q), whatever
path is taken, which is why a buy followed by a sell can never beat the market: every dollar paid in comes back out
at the same prices, and all rounding below goes against the trader, never for them.

A "token" is either YES on outcome i (pays $1 if i wins) or NO on outcome i (pays $1 if
anything else wins). Everything below is written in log-space so it stays exact even for
absurdly large bets.
"""
import math

NEG_INF = float("-inf")


def lse(xs):
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


def logaddexp(a, b):
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def prices(q, b):
    l = [x / b for x in q]
    big_l = lse(l)
    return [math.exp(x - big_l) for x in l]


def token_logs(q, b, i, side):
    """Returns (ln P, ln Q): log of the token's price and of its complement (1 - P)."""
    l = [x / b for x in q]
    big_l = lse(l)
    ln_p = l[i] - big_l
    others = [x for j, x in enumerate(l) if j != i]
    ln_r = lse(others) - big_l if others else NEG_INF
    return (ln_p, ln_r) if side == "y" else (ln_r, ln_p)


def token_price(q, b, i, side):
    return math.exp(token_logs(q, b, i, side)[0])


def _ln_expm1(a):
    return a if a > 700 else math.log(math.expm1(a))


def shares_for_amount(ln_p, ln_q, b, amount):
    """How many shares of a token `amount` dollars buys."""
    a = amount / b
    if a <= 0:
        return 0.0
    return b * (logaddexp(_ln_expm1(a), ln_p) - ln_p)


def cost_for_shares(ln_p, ln_q, b, shares):
    return b * logaddexp(ln_q, ln_p + shares / b)


def proceeds_for_shares(ln_p, ln_q, b, shares):
    """Dollars received for selling `shares` of a token back to the market."""
    return -b * logaddexp(ln_q, ln_p - shares / b)


def apply_trade(q, i, side, shares):
    """Moves the market state after `shares` of a token were bought (+) or sold (-)."""
    delta = shares if side == "y" else -shares
    q = list(q)
    q[i] += delta
    lowest = min(q)           # prices only depend on differences, keep the numbers small
    return [x - lowest for x in q]


# ---- the market maker's own bookkeeping, and rounding that never favours the trader ---------------------

CENT_NOISE = 1e-9               # float noise allowed when rounding a dollar amount down to a whole cent


def cost(q, b):
    """C(q): the cash the market maker has taken in for the shares that are out there."""
    return b * lse([x / b for x in q])


def floor_cents(x):
    """Round a dollar amount DOWN to a whole cent (a trader is paid out this way)."""
    return math.floor(x * 100 + CENT_NOISE) / 100


def percentages(probs):
    """Whole-number percentages that always add up to exactly 100 (largest remainder), for showing odds."""
    raw = [max(0.0, p) * 100 for p in probs]
    total = sum(raw) or 1.0
    raw = [x * 100 / total for x in raw]
    floors = [int(math.floor(x + 1e-9)) for x in raw]
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:100 - sum(floors)]:
        floors[i] += 1
    return floors
