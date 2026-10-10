"""The Stock Exchange's price engine: a shared, persistent simulation of ten fictional companies. All of it is pretend.

How prices move (everything is in real time, volatilities are per square-root-hour):

  return of a company over a step = market factor x its sensitivity ("beta")
                                  + its sector's factor x its sector sensitivity
                                  + its own noise
                                  + a pull back towards its slowly drifting "fair value"
                                  + the lingering effect of recent (simulated) news

  * The market factor and each sector factor have a slowly changing trend (hours) and a slowly changing volatility (hours).
    So there are calm stretches and busy stretches, and companies in the same sector move together.
  * Each company's own noise level also wanders slowly (volatility clustering), and its price is gently pulled towards a fair
    value that itself drifts only a little each day. Prices can never run away: the pull gets stronger the further out they
    are, and hard limits sit beyond it.
  * Prices are a path: each update starts from the previous price. They are never drawn afresh.
  * Occasional fictional events (a product launch, a recall...) give a small immediate jump and a trend that fades over
    about ten minutes. Each one is published as simulated news.

Limits: a price never goes below MIN_PRICE or above MAX_PRICE, never moves more than MAX_STEP in one update (scaled up
for the coarse catch-up steps), never leaves a band around its fair value, and a move of CIRCUIT_MOVE within five minutes
pauses trading in that company for CIRCUIT_PAUSE_S seconds (the price keeps moving, orders are refused).

The state (prices, factors, news, history, candles) is saved to a file every few seconds and when the server stops. After
a restart the market carries on from where it was: the time the server was off is replayed in one-minute steps (up to
STOCK_CATCHUP_MAX_S; a longer outage is treated as that long) so nothing sits frozen and the charts show the gap.

Random numbers: the shared price must not be predictable, so the real engine uses the operating system's secure source.
Tests pass in a seeded generator instead.
"""
import json
import math
import os
import random
import tempfile

from . import economy
from .util import day_start_ms, now_ms

MIN_PRICE, MAX_PRICE = 1.00, 5000.00
MAX_STEP = 0.01                      # largest move of one second's update (1%); coarse catch-up steps may move more, in proportion
CIRCUIT_MOVE, CIRCUIT_PAUSE_S = 0.08, 60
BAND = (0.45, 2.2)                   # a price stays within this multiple of its fair value
CATCHUP_STEP_S = 60

# volatilities are per square-root-hour (a "1.6" means 1.6% over an hour, 3.2% over four hours)
MARKET_VOL = 0.9
SECTOR_VOL = 1.1
FAIR_VOL = 0.10                      # how fast fair value itself wanders
REVERT_PER_H = 1 / 30                # the pull towards fair value, per hour
NEWS_EVERY_MIN = 14                  # on average one event this often, market-wide
NEWS_KEEP = 60

INTERVALS = {"1m": 60_000, "5m": 300_000, "1h": 3_600_000, "1d": None}
CANDLE_KEEP = {"1m": 1440, "5m": 2016, "1h": 720, "1d": 400}
TICKS_KEEP = 3600

COMPANIES = [
    {"sym": "LUMA", "name": "Luma Energy", "sector": "Energy", "price": 42.50, "vol": 2.0, "beta": 0.9, "sbeta": 1.0,
     "about": "Runs solar farms, wind parks and a growing fleet of grid batteries across the coast."},
    {"sym": "BRVA", "name": "Brava Foods", "sector": "Consumer", "price": 28.20, "vol": 1.2, "beta": 0.6, "sbeta": 1.0,
     "about": "Snacks, sauces and frozen meals. Nobody loves them and everybody buys them."},
    {"sym": "ORBT", "name": "Orbitel Networks", "sector": "Communications", "price": 64.00, "vol": 1.5, "beta": 0.8, "sbeta": 1.0,
     "about": "Fibre, mobile towers and one very large satellite it keeps promising to launch."},
    {"sym": "NEXO", "name": "Nexo Robotics", "sector": "Technology", "price": 118.40, "vol": 3.2, "beta": 1.4, "sbeta": 1.0,
     "about": "Warehouse robots, kitchen robots and a robot that folds laundry about half the time."},
    {"sym": "SELV", "name": "Selva Labs", "sector": "Healthcare", "price": 23.75, "vol": 3.4, "beta": 1.1, "sbeta": 1.0,
     "about": "A research lab with eleven drugs in trials and one very good press office."},
    {"sym": "ATLS", "name": "Atlas Mobility", "sector": "Transport", "price": 87.10, "vol": 2.2, "beta": 1.0, "sbeta": 1.0,
     "about": "Electric buses, trams and scooters. Mostly on time."},
    {"sym": "MARE", "name": "Marea Logistics", "sector": "Transport", "price": 35.60, "vol": 1.8, "beta": 0.9, "sbeta": 1.0,
     "about": "Ships, ports and trucks. If it is late, it was probably Marea."},
    {"sym": "PRSM", "name": "Prisma Media", "sector": "Communications", "price": 19.90, "vol": 2.6, "beta": 1.2, "sbeta": 1.0,
     "about": "Streaming, podcasts and a magazine nobody admits to reading."},
    {"sym": "COBL", "name": "Cobalt Systems", "sector": "Technology", "price": 156.30, "vol": 2.4, "beta": 1.2, "sbeta": 1.0,
     "about": "Cloud servers and the software that quietly runs half your apps."},
    {"sym": "AURA", "name": "Aurora Health", "sector": "Healthcare", "price": 72.80, "vol": 1.3, "beta": 0.5, "sbeta": 1.0,
     "about": "Clinics, labs and a very popular wellness app. Steady, and proud of it."},
]
BY_SYM = {c["sym"]: c for c in COMPANIES}
SECTORS = sorted({c["sector"] for c in COMPANIES})

# Simulated events. scope is a symbol, a sector or "*" (everyone). jump = immediate move, trend = extra drift (log %/hour at
# the start) that fades with a ten-minute half-life, both in percent.
EVENTS = [
    ("LUMA", +1, "Luma Energy switches on a record-sized solar farm", 0.8, 2.5), ("LUMA", -1, "Luma Energy battery site paused after a safety check", 0.9, 2.5),
    ("BRVA", +1, "Brava Foods' new sauce line sells out in a weekend", 0.6, 1.8), ("BRVA", -1, "Brava Foods recalls one snack line over a labelling mix-up", 0.9, 2.2),
    ("ORBT", +1, "Orbitel Networks wins a big spectrum auction", 0.8, 2.3), ("ORBT", -1, "Orbitel Networks hit by a regional outage", 0.8, 2.0),
    ("NEXO", +1, "Nexo Robotics' laundry-folding demo goes viral", 1.4, 3.8), ("NEXO", -1, "Nexo Robotics delays its flagship robot again", 1.4, 3.6),
    ("SELV", +1, "Selva Labs reports encouraging early trial results", 1.6, 4.2), ("SELV", -1, "Selva Labs trial misses its main target", 1.8, 4.5),
    ("ATLS", +1, "Atlas Mobility lands a city-wide tram contract", 1.0, 2.8), ("ATLS", -1, "Atlas Mobility plant hit by a strike", 1.0, 2.6),
    ("MARE", +1, "Marea Logistics signs a long port deal", 0.8, 2.2), ("MARE", -1, "Marea Logistics ship stuck in a canal, deliveries late", 0.9, 2.4),
    ("PRSM", +1, "Prisma Media's new series tops the charts", 1.2, 3.2), ("PRSM", -1, "Prisma Media's big premiere flops", 1.2, 3.0),
    ("COBL", +1, "Cobalt Systems wins a major cloud contract", 1.0, 2.8), ("COBL", -1, "Cobalt Systems cloud outage annoys clients", 1.1, 2.8),
    ("AURA", +1, "Aurora Health's wellness app passes ten million users", 0.6, 1.6), ("AURA", -1, "Aurora Health faces a pricing inquiry", 0.7, 1.8),
    ("Energy", +1, "Energy demand surges in a heat wave", 0.7, 1.6), ("Energy", -1, "Cheap imports squeeze energy margins", 0.7, 1.6),
    ("Technology", +1, "Tech sector cheers a wave of new orders", 0.8, 1.8), ("Technology", -1, "Regulators open a probe into the tech sector", 0.9, 2.0),
    ("Healthcare", +1, "Health ministry announces a research fund", 0.7, 1.6), ("Healthcare", -1, "Health sector rattled by a drug-pricing proposal", 0.8, 1.8),
    ("Transport", +1, "Fuel costs ease for transport firms", 0.6, 1.4), ("Transport", -1, "Transport firms warn of slower freight", 0.6, 1.4),
    ("Communications", +1, "Communications firms gain as streaming time grows", 0.6, 1.4), ("Communications", -1, "Communications firms face new spectrum fees", 0.6, 1.4),
    ("Consumer", +1, "Consumer confidence climbs", 0.5, 1.2), ("Consumer", -1, "Shoppers cut back on snacks and takeaway", 0.5, 1.2),
    ("*", +1, "Central bank holds rates and markets breathe out", 0.5, 1.1), ("*", -1, "Jittery day on the exchange as traders turn cautious", 0.5, 1.2),
]
NEWS_HALF_LIFE_MIN = 10


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def bucket_start(t, interval):
    if interval == "1d":
        return day_start_ms(t)
    step = INTERVALS[interval]
    return t - t % step


class Engine:
    def __init__(self, path=None, rng=None, clock=None):
        self.path = path
        self.rng = rng or random.SystemRandom()
        self.clock = clock or now_ms
        self.s = None
        self.dirty = False
        self.last_saved = 0
        self.catchup = None                 # what the last start-up had to replay, for the page to say so

    # ---- state ---------------------------------------------------------------------------------------------------
    def fresh(self, now):
        s = {"v": 1, "t": now, "seq": 0, "market": {"mu": 0.0, "x": 0.0},
             "sectors": {k: {"mu": 0.0, "x": 0.0} for k in SECTORS}, "co": {}, "news": [], "impulses": [],
             "ticks": {}, "candles": {}, "next_news": now + 3 * 60_000}
        for c in COMPANIES:
            p = c["price"]
            s["co"][c["sym"]] = {"p": p, "lnf": math.log(p), "x": 0.0, "halt": 0, "do": {"day": day_start_ms(now), "p": p}, "cool": 0}
            s["ticks"][c["sym"]] = [[now, p]]
            s["candles"][c["sym"]] = {iv: [{"t": bucket_start(now, iv), "o": p, "h": p, "l": p, "c": p}] for iv in INTERVALS}
        return s

    def load(self):
        now = self.clock()
        if self.path and os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if saved.get("v") == 1 and set(saved["co"]) == set(BY_SYM):
                    self.s = saved
                    self.catch_up(now)
                    return self.s
            except (OSError, ValueError, KeyError):
                pass                                          # a damaged file: start the market over rather than not at all
        self.s = self.fresh(now)
        self.dirty = True
        return self.s

    def snapshot(self):
        """The state as text. Quick; call it while nothing else is changing the market."""
        return json.dumps(self.s, separators=(",", ":"))

    def write(self, blob):
        """Puts a snapshot on disk (all at once, so a crash can never leave half a file). Slow; needs no lock."""
        if not self.path:
            return False
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".part")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        self.last_saved = self.clock()
        return True

    def save(self, force=False):
        if not self.path or self.s is None or not (self.dirty or force):
            return False
        self.dirty = False
        return self.write(self.snapshot())

    # ---- the simulation ------------------------------------------------------------------------------------------
    def _ou(self, factor, dt_h, tau_h, mu_scale, vol_tau_h, vol_of_vol):
        """Moves a factor's trend and volatility state a little (both revert to normal)."""
        g = self.rng.gauss
        factor["mu"] += -factor["mu"] / tau_h * dt_h + mu_scale * math.sqrt(dt_h) * g(0, 1)
        factor["x"] += -factor["x"] / vol_tau_h * dt_h + vol_of_vol * math.sqrt(dt_h) * g(0, 1)
        factor["x"] = _clamp(factor["x"], -0.7, 1.1)
        factor["mu"] = _clamp(factor["mu"], -0.35, 0.35)

    def _impulse_drift(self, sym, sector, t):
        total = 0.0
        for im in self.s["impulses"]:
            if im["scope"] in ("*", sym, sector):
                total += im["rate"] * 0.5 ** ((t - im["t"]) / 60_000 / NEWS_HALF_LIFE_MIN)
        return total

    def step(self, dt_s, t):
        """Advances the whole market by dt_s seconds, ending at time t. Returns nothing; read prices from state."""
        s, g = self.s, self.rng.gauss
        dt_h = dt_s / 3600
        sq = math.sqrt(dt_h)
        m = s["market"]
        self._ou(m, dt_h, 6.0, 0.12, 3.0, 0.35)
        r_market = (m["mu"] * dt_h + MARKET_VOL * math.exp(m["x"]) * sq * g(0, 1)) / 100
        r_sector = {}
        for k, f in s["sectors"].items():
            self._ou(f, dt_h, 4.0, 0.10, 3.0, 0.30)
            r_sector[k] = (f["mu"] * dt_h + SECTOR_VOL * math.exp(f["x"]) * sq * g(0, 1)) / 100
        cap = MAX_STEP * max(1.0, math.sqrt(dt_s))
        for c in COMPANIES:
            st = s["co"][c["sym"]]
            st["x"] += -st["x"] / 2.0 * dt_h + 0.30 * sq * g(0, 1)
            st["x"] = _clamp(st["x"], -0.7, 1.1)
            st["lnf"] += FAIR_VOL * sq * g(0, 1) / 100
            lnp = math.log(st["p"])
            pull = -(lnp - st["lnf"]) * REVERT_PER_H * dt_h * (1 + 6 * max(0.0, abs(lnp - st["lnf"]) - 0.25))
            noise = c["vol"] * math.exp(st["x"]) * sq * g(0, 1) / 100
            news = self._impulse_drift(c["sym"], c["sector"], t) * dt_h / 100
            r = c["beta"] * r_market + c["sbeta"] * r_sector[c["sector"]] + noise + pull + news
            r = _clamp(r, -cap, cap)
            lnp = _clamp(lnp + r, math.log(MIN_PRICE), math.log(MAX_PRICE))
            lnp = _clamp(lnp, st["lnf"] + math.log(BAND[0]), st["lnf"] + math.log(BAND[1]))
            st["p"] = round(math.exp(lnp), 4)

    def _record(self, t, gap=False):
        s = self.s
        for sym, st in s["co"].items():
            p = st["p"]
            ticks = s["ticks"][sym]
            ticks.append([t, p])
            del ticks[:-TICKS_KEEP]
            if st["do"]["day"] != day_start_ms(t):
                st["do"] = {"day": day_start_ms(t), "p": ticks[-2][1] if len(ticks) > 1 else p}
            for iv, rows in s["candles"][sym].items():
                start = bucket_start(t, iv)
                cur = rows[-1]
                if cur["t"] == start:
                    cur["h"], cur["l"], cur["c"] = max(cur["h"], p), min(cur["l"], p), p
                    if gap:
                        cur["g"] = 1
                else:
                    row = {"t": start, "o": cur["c"], "h": max(cur["c"], p), "l": min(cur["c"], p), "c": p}
                    if gap:
                        row["g"] = 1
                    rows.append(row)
                    del rows[:-CANDLE_KEEP[iv]]

    def _news(self, t, live=True):
        """Maybe starts a simulated event."""
        s = self.s
        s["impulses"] = [i for i in s["impulses"] if t - i["t"] < NEWS_HALF_LIFE_MIN * 6 * 60_000]
        while t >= s["next_news"]:
            when = s["next_news"]
            s["next_news"] = when + int(self.rng.expovariate(1 / (NEWS_EVERY_MIN * 60_000))) + 15_000
            scope, sign, headline, jump, trend = EVENTS[self.rng.randrange(len(EVENTS))]
            if scope in BY_SYM and any(n["scope"] == scope and when - n["t"] < 600_000 for n in s["news"]):
                continue                                      # one event per company every ten minutes at most
            mult = 0.6 + 0.8 * self.rng.random()
            jump, trend = sign * jump * mult, sign * trend * mult
            targets = [c["sym"] for c in COMPANIES if scope in ("*", c["sym"], c["sector"])]
            for sym in targets:
                st = s["co"][sym]
                lnp = math.log(st["p"]) + _clamp(jump / 100, -0.03, 0.03)
                st["p"] = round(_clamp(math.exp(lnp), MIN_PRICE, MAX_PRICE), 4)
            s["impulses"].append({"t": when, "scope": scope, "rate": trend})
            s["news"].insert(0, {"id": f"n{s['seq']}", "t": when, "scope": scope, "text": headline, "dir": sign, "syms": targets,
                                 "size": round(abs(jump), 2), "simulated": True})
            s["seq"] += 1
            del s["news"][NEWS_KEEP:]

    def _circuit(self, t):
        for sym, st in self.s["co"].items():
            if st["halt"] > t or st["cool"] > t:
                continue
            ticks = self.s["ticks"][sym]
            ref = next((p for (tt, p) in reversed(ticks) if t - tt >= 300_000), None)
            if ref and abs(st["p"] / ref - 1) >= CIRCUIT_MOVE:
                st["halt"] = t + CIRCUIT_PAUSE_S * 1000
                st["cool"] = st["halt"] + 300_000
                self.s["news"].insert(0, {"id": f"n{self.s['seq']}", "t": t, "scope": sym, "dir": 0, "syms": [sym], "simulated": True,
                                          "text": f"Trading in {BY_SYM[sym]['name']} paused for {CIRCUIT_PAUSE_S}s after a very sharp move (simulated circuit breaker)"})
                self.s["seq"] += 1

    def tick(self, now=None):
        """One update. Normally called every second; after a longer silence it replays the gap first."""
        now = self.clock() if now is None else now
        if self.s is None:
            self.load()
        s = self.s
        if now <= s["t"]:
            return False
        gap_s = (now - s["t"]) / 1000
        if gap_s > 10:
            self.catch_up(now)
            return True
        self.step(gap_s, now)
        self._news(now)
        self._record(now)
        self._circuit(now)
        s["t"] = now
        self.dirty = True
        return True

    def catch_up(self, now):
        """The server was off (or stalled): replay the missed time in one-minute steps, no further back than the limit.
        If the outage was longer than the limit, the earlier part is simply skipped: the market behaves as if it had only
        been away for the limit, and the charts show the gap."""
        s = self.s
        missed = (now - s["t"]) / 1000
        if missed <= 0:
            return
        replay = min(missed, economy.STOCK_CATCHUP_MAX_S)
        self.catchup = {"missedSeconds": int(missed), "replayedSeconds": int(replay), "from": s["t"], "to": now,
                        "capped": missed > economy.STOCK_CATCHUP_MAX_S}
        t = now - int(replay * 1000)
        s["next_news"] = max(s["next_news"], t)              # no pile of old events landing in one step
        while t < now:
            dt = min(CATCHUP_STEP_S, (now - t) / 1000)
            t += int(dt * 1000)
            self.step(dt, t)
            self._news(t)
            self._record(t, gap=True)
        s["t"] = now
        self.dirty = True

    # ---- reading -------------------------------------------------------------------------------------------------
    def price(self, sym):
        return self.s["co"][sym]["p"]

    def halted(self, sym, now=None):
        now = self.clock() if now is None else now
        return self.s["co"][sym]["halt"] > now

    def change(self, sym):
        """(change since the market day began in dollars, in percent)."""
        st = self.s["co"][sym]
        base = st["do"]["p"]
        return round(st["p"] - base, 4), round((st["p"] / base - 1) * 100, 3) if base else 0.0

    def hi_lo(self, sym):
        rows = self.s["candles"][sym]["1m"][-1440:]
        return max(r["h"] for r in rows), min(r["l"] for r in rows)

    def sparkline(self, sym, points=60):
        ticks = self.s["ticks"][sym]
        if len(ticks) <= points:
            return [p for _, p in ticks]
        step = len(ticks) / points
        return [ticks[int(i * step)][1] for i in range(points - 1)] + [ticks[-1][1]]

    def candles(self, sym, interval, limit=200):
        return self.s["candles"][sym][interval][-limit:]

    def news(self, sym=None, limit=20):
        rows = self.s["news"] if sym is None else [n for n in self.s["news"] if sym in n["syms"]]
        return rows[:limit]
