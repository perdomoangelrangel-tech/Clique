"""Buying and selling shares on the Stock Exchange. Everything here is pretend money, and it all uses the ACCUMULATED account.

How an order works (and why it is safe):
  1. QUOTE. You ask for a price for a number of shares, buying or selling. The server looks at the current price, adds a
     small gap between what it sells at (ask) and buys at (bid), and gives you a quote with an id that is good for
     STOCK_QUOTE_TTL_S seconds and only for you. Nothing has happened yet.
  2. TRADE. You confirm the quote. The server checks the quote is yours, unused and unexpired, looks at the price AGAIN and,
     if it has moved more than STOCK_MAX_SLIPPAGE_BPS since the quote, refuses and hands you a fresh quote instead of
     filling you at a price you did not see. Otherwise it fills at the CURRENT price (never a stale one, so waiting around to
     see which way the market goes gains you nothing).
  3. The cost or proceeds, the account, the position and the transaction record all change in one step. Buying needs enough in
     the accumulated account; selling needs the shares. There is no leverage and no short selling.

Prices are in whole cents and shares are whole shares, so all arithmetic is exact. Buying costs the ask, selling pays the bid,
both rounded in the exchange's favour, so buying and selling straight away always loses a little: there is no way to make
money from rounding or from trading against the same quote.

Trades do not move prices (see ECONOMY.md): the market is the same for everyone and a big order cannot push it around.
"""
import math
import re

from . import activity, economy, ledger, stockengine
from .store import db
from .util import bad, new_id, now_ms

engine = None                         # the shared market; the server creates it (tests make their own)
QUOTES = {}                           # quote id -> quote. Lost on restart, which just means asking again.
TRADES_KEEP = 300


def market():
    if engine is None or engine.s is None:
        raise bad("The exchange is not open yet", 503, code="exchange_closed")
    return engine


# ---- prices ------------------------------------------------------------------------------------------------------

def prices_c(mid):
    """(bid, ask) in cents for a mid price in dollars. Always at least one cent apart; rounded against the customer."""
    half = economy.STOCK_SPREAD_BPS / 2 / 10_000
    mid_c = mid * 100
    bid = math.floor(mid_c * (1 - half) + 1e-9)
    ask = math.ceil(mid_c * (1 + half) - 1e-9)
    if ask - bid < 1:
        ask = bid + 1
    return bid, ask


def _company(sym):
    c = stockengine.BY_SYM.get(sym if isinstance(sym, str) else None)
    if not c:
        raise bad("There is no company with that symbol", 404, code="company_not_found")
    return c


def _positions(user):
    return user.setdefault("pos", {})


def _shares_owned(user, sym):
    return (_positions(user).get(sym) or {}).get("sh", 0)


def parse_shares(value):
    if isinstance(value, bool) or value is None:
        raise bad("Enter how many shares", code="shares_required")
    if isinstance(value, float):
        if not value.is_integer():
            raise bad("Shares are whole numbers", code="invalid_shares")
        value = int(value)
    if isinstance(value, str):
        v = value.strip().replace(",", "")
        if not re.fullmatch(r"\d{1,9}", v):
            raise bad("Shares are whole numbers", code="invalid_shares")
        value = int(v)
    if not isinstance(value, int) or value < 1:
        raise bad("Enter at least 1 share", code="shares_required")
    if value > economy.STOCK_MAX_ORDER_SHARES:
        raise bad(f"The most you can trade at once is {economy.STOCK_MAX_ORDER_SHARES:,} shares", code="order_too_large")
    return value


# ---- quotes ------------------------------------------------------------------------------------------------------

def _purge(now):
    for qid in [q for q, v in QUOTES.items() if v["exp"] < now - 60_000]:
        del QUOTES[qid]
    if len(QUOTES) > 2000:
        for qid in sorted(QUOTES, key=lambda q: QUOTES[q]["t"])[:1000]:
            del QUOTES[qid]


def quote(user, body, now=None):
    now = now_ms() if now is None else now
    eng = market()
    c = _company(body.get("symbol"))
    side = body.get("side")
    if side not in ("buy", "sell"):
        raise bad("Choose buy or sell", code="invalid_action")
    shares = parse_shares(body.get("shares"))
    sym = c["sym"]
    if eng.halted(sym, now):
        raise bad(f"Trading in {c['name']} is paused for a moment after a sharp move. Try again shortly.", 409, code="trading_halted")
    owned = _shares_owned(user, sym)
    if side == "sell" and shares > owned:
        raise bad(f"You only own {owned:,} share{'s' if owned != 1 else ''} of {c['name']}", 400, code="not_enough_shares")
    mid = eng.price(sym)
    bid, ask = prices_c(mid)
    px = ask if side == "buy" else bid
    total = shares * px
    have = ledger.balance_c(user, "accumulated")
    q = {"id": new_id(), "uid": user["id"], "sym": sym, "side": side, "shares": shares, "px": px, "t": now,
         "exp": now + int(economy.STOCK_QUOTE_TTL_S * 1000), "used": False}
    _purge(now)
    QUOTES[q["id"]] = q
    out = {"quoteId": q["id"], "symbol": sym, "name": c["name"], "side": side, "shares": shares, "price": px / 100, "mid": round(mid, 4),
           "bid": bid / 100, "ask": ask / 100, "spreadBps": economy.STOCK_SPREAD_BPS, "total": total / 100,
           "expiresAt": q["exp"], "ttlSeconds": economy.STOCK_QUOTE_TTL_S, "maxSlippageBps": economy.STOCK_MAX_SLIPPAGE_BPS,
           "account": "accumulated", "balance": have / 100,
           "balanceAfter": (have - total if side == "buy" else have + total) / 100,
           "canAfford": side == "sell" or have >= total, "owned": owned,
           "ownedAfter": owned + shares if side == "buy" else owned - shares}
    if side == "buy":
        out["worstTotal"] = math.ceil(total * (1 + economy.STOCK_MAX_SLIPPAGE_BPS / 10_000)) / 100
    else:
        out["worstTotal"] = math.floor(total * (1 - economy.STOCK_MAX_SLIPPAGE_BPS / 10_000)) / 100
    return out


# ---- trades ------------------------------------------------------------------------------------------------------

def _request_key(user, request_id):
    if request_id is None:
        return None
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", request_id):
        raise bad("Invalid request id", code="invalid_request_id")
    return f"stocks:{user['id']}:{request_id}"


def trade(user, body, now=None):
    now = now_ms() if now is None else now
    eng = market()
    key = _request_key(user, body.get("requestId"))
    memory = db().setdefault("idem", {})
    if key and key in memory:
        seen = memory[key]
        if seen["fp"] != body.get("quoteId"):
            raise bad("That request id was already used for a different order", 409, code="request_id_reused")
        return {**seen["result"], "duplicate": True}
    q = QUOTES.get(body.get("quoteId")) if isinstance(body.get("quoteId"), str) else None
    if not q or q["uid"] != user["id"]:
        raise bad("That quote was not found. Ask for a new one.", 404, code="quote_not_found")
    if q["used"]:
        raise bad("That quote was already used", 409, code="quote_used")

    def refresh(err):
        err.data = {"quote": quote(user, {"symbol": q["sym"], "side": q["side"], "shares": q["shares"]}, now)}
        return err
    if now > q["exp"]:
        raise refresh(bad("That quote expired. Here is a fresh one.", 409, code="quote_expired"))
    sym, side, shares = q["sym"], q["side"], q["shares"]
    c = stockengine.BY_SYM[sym]
    if eng.halted(sym, now):
        raise bad(f"Trading in {c['name']} is paused for a moment after a sharp move. Try again shortly.", 409, code="trading_halted")
    bid, ask = prices_c(eng.price(sym))
    px = ask if side == "buy" else bid
    if abs(px - q["px"]) * 10_000 > q["px"] * economy.STOCK_MAX_SLIPPAGE_BPS:
        raise refresh(bad("The price moved while you were deciding. Check the new quote.", 409, code="price_moved"))

    total = shares * px
    pos = _positions(user).setdefault(sym, {"sh": 0, "cost_c": 0, "real_c": 0})
    have = ledger.balance_c(user, "accumulated")
    if side == "buy":
        if total > have:
            raise bad(f"Not enough in your accumulated account: this costs ${total / 100:,.2f} and you have ${have / 100:,.2f}", 400, code="insufficient_funds")
    elif shares > pos["sh"]:
        raise bad(f"You only own {pos['sh']:,} share{'s' if pos['sh'] != 1 else ''} of {c['name']}", 400, code="not_enough_shares")
    # everything is checked: from here nothing can fail
    tid = new_id()
    realized = 0
    if side == "buy":
        ledger.post(user, "accumulated", -total / 100, "stocks.buy", ref=sym, txid=f"stk:{tid}")
        pos["sh"] += shares
        pos["cost_c"] += total
    else:
        basis = pos["cost_c"] if shares == pos["sh"] else (pos["cost_c"] * shares + pos["sh"] // 2) // pos["sh"]
        ledger.post(user, "accumulated", total / 100, "stocks.sell", ref=sym, txid=f"stk:{tid}")
        realized = total - basis
        pos["sh"] -= shares
        pos["cost_c"] -= basis
        pos["real_c"] += realized
    q["used"] = True
    rec = {"id": tid, "t": now, "sym": sym, "side": side, "sh": shares, "px": px, "total": total, "mid": round(eng.price(sym), 4)}
    if side == "sell":
        rec["real"] = realized
    log = user.setdefault("trades", [])
    log.insert(0, rec)
    del log[TRADES_KEEP:]
    activity.safe_record(user, "exchange", tid, now=now, amount=total / 100, symbol=sym)
    result = {"tradeId": tid, "symbol": sym, "name": c["name"], "side": side, "shares": shares, "price": px / 100, "total": total / 100,
              "balanceBefore": have / 100, "balanceAfter": ledger.balance(user, "accumulated"), "account": "accumulated",
              "position": _position_row(user, sym), "realized": realized / 100 if side == "sell" else None}
    if key:
        memory[key] = {"t": now, "fp": body.get("quoteId"), "result": result}
        if len(memory) > 1000:
            for old in sorted(memory, key=lambda k: memory[k]["t"])[:-500]:
                del memory[old]
    return {**result, "duplicate": False}


# ---- reading ------------------------------------------------------------------------------------------------------

def _position_row(user, sym):
    eng = market()
    p = _positions(user).get(sym) or {"sh": 0, "cost_c": 0, "real_c": 0}
    bid, _ = prices_c(eng.price(sym))
    value = p["sh"] * bid
    return {"symbol": sym, "name": stockengine.BY_SYM[sym]["name"], "shares": p["sh"], "cost": p["cost_c"] / 100,
            "avgCost": (p["cost_c"] / p["sh"] / 100) if p["sh"] else 0.0, "price": eng.price(sym), "bid": bid / 100,
            "value": value / 100, "unrealized": (value - p["cost_c"]) / 100,
            "unrealizedPct": ((value / p["cost_c"] - 1) * 100) if p["cost_c"] else 0.0, "realized": p["real_c"] / 100}


def portfolio(user):
    market()
    rows = [_position_row(user, sym) for sym in _positions(user) if _positions(user)[sym]["sh"] or _positions(user)[sym]["real_c"]]
    held = [r for r in rows if r["shares"]]
    value = sum(ledger.to_cents(r["value"]) for r in held)
    cost = sum(ledger.to_cents(r["cost"]) for r in held)
    realized = sum(ledger.to_cents(r["realized"]) for r in rows)
    cash = ledger.balance_c(user, "accumulated")
    return {"positions": sorted(held, key=lambda r: -r["value"]), "closed": [r for r in rows if not r["shares"]],
            "cash": cash / 100, "stockValue": value / 100, "invested": cost / 100, "unrealized": (value - cost) / 100,
            "realized": realized / 100, "total": (cash + value) / 100,
            "trades": [_trade_json(t) for t in (user.get("trades") or [])[:50]]}


def _trade_json(t):
    return {"id": t["id"], "t": t["t"], "symbol": t["sym"], "name": stockengine.BY_SYM[t["sym"]]["name"], "side": t["side"],
            "shares": t["sh"], "price": t["px"] / 100, "total": t["total"] / 100, "realized": (t["real"] / 100) if "real" in t else None}


def listing(user):
    eng = market()
    out = []
    now = now_ms()
    for c in stockengine.COMPANIES:
        sym = c["sym"]
        chg, pct = eng.change(sym)
        bid, ask = prices_c(eng.price(sym))
        row = {"symbol": sym, "name": c["name"], "sector": c["sector"], "price": eng.price(sym), "bid": bid / 100, "ask": ask / 100,
               "change": chg, "changePct": pct, "halted": eng.halted(sym, now), "spark": eng.sparkline(sym)}
        pos = _positions(user).get(sym)
        if pos and pos["sh"]:
            row["mine"] = {"shares": pos["sh"], "value": pos["sh"] * bid / 100, "unrealized": (pos["sh"] * bid - pos["cost_c"]) / 100}
        out.append(row)
    return {"stocks": out, "t": eng.s["t"], "simulated": True, "catchup": eng.catchup,
            "news": [_news_json(n) for n in eng.news(limit=8)], "accumulated": ledger.balance(user, "accumulated")}


def _news_json(n):
    return {"id": n["id"], "t": n["t"], "text": n["text"], "dir": n["dir"], "symbols": n["syms"], "simulated": True}


def detail(user, sym, interval="5m", limit=200):
    eng = market()
    c = _company(sym)
    sym = c["sym"]
    if interval not in stockengine.INTERVALS:
        raise bad("Unknown interval", code="invalid_request")
    try:
        limit = max(10, min(1500, int(limit)))
    except (TypeError, ValueError):
        raise bad("Invalid limit", code="invalid_request")
    chg, pct = eng.change(sym)
    hi, lo = eng.hi_lo(sym)
    bid, ask = prices_c(eng.price(sym))
    mine = [_trade_json(t) for t in (user.get("trades") or []) if t["sym"] == sym][:20]
    return {"symbol": sym, "name": c["name"], "sector": c["sector"], "about": c["about"], "price": eng.price(sym), "bid": bid / 100,
            "ask": ask / 100, "change": chg, "changePct": pct, "high24": hi, "low24": lo, "halted": eng.halted(sym),
            "interval": interval, "candles": eng.candles(sym, interval, limit), "ticks": eng.s["ticks"][sym][-600:],
            "news": [_news_json(n) for n in eng.news(sym, 10)], "position": _position_row(user, sym), "trades": mine,
            "accumulated": ledger.balance(user, "accumulated"), "simulated": True, "t": eng.s["t"], "spreadBps": economy.STOCK_SPREAD_BPS}
