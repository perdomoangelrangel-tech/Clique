"""The Stock Exchange: the price engine (coherent, bounded, persistent) and trading (exact, atomic, no free money)."""
import json
import math
import os
import random
import statistics
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                          # noqa: E402
from backend import economy, exchange, ledger, stockengine as se, users   # noqa: E402
from backend.store import db, store                                    # noqa: E402
from backend.util import ApiError, now_ms                              # noqa: E402
from tests.econ import books_balance, mk                               # noqa: E402
from tests.helpers import fresh_store, restore_store_path              # noqa: E402
from tests.test_http import Client                                     # noqa: E402

T0 = 1_800_000_000_000                                                  # a Monday morning, in the future: no real clock involved


def tearDownModule():
    restore_store_path()
    exchange.engine = None


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def new_engine(seed=1, path=None):
    e = se.Engine(path=path, rng=random.Random(seed), clock=lambda: T0)
    e.s = e.fresh(T0)
    return e


def run(e, seconds, step=1, t=None):
    t = e.s["t"] if t is None else t
    for _ in range(int(seconds / step)):
        t += step * 1000
        e.tick(t)
    return t


class TheCompanies(unittest.TestCase):
    def test_ten_fictional_companies_in_several_sectors(self):
        self.assertGreaterEqual(len(se.COMPANIES), 10)
        names = {c["name"] for c in se.COMPANIES}
        self.assertTrue({"Luma Energy", "Brava Foods", "Orbitel Networks", "Nexo Robotics", "Selva Labs", "Atlas Mobility",
                         "Marea Logistics", "Prisma Media", "Cobalt Systems", "Aurora Health"} <= names)
        self.assertGreaterEqual(len(se.SECTORS), 5)
        self.assertEqual(len({c["sym"] for c in se.COMPANIES}), len(se.COMPANIES), "every ticker symbol is different")
        for c in se.COMPANIES:
            self.assertRegex(c["sym"], r"^[A-Z]{4}$")
            self.assertTrue(c["about"] and c["sector"] and 1 < c["price"] < 1000)

    def test_a_fresh_market_starts_every_company_at_its_starting_price(self):
        e = new_engine()
        for c in se.COMPANIES:
            self.assertEqual(e.price(c["sym"]), c["price"])
            self.assertEqual(e.change(c["sym"]), (0.0, 0.0))


class ThePriceEngine(unittest.TestCase):
    def test_prices_are_a_path_not_a_fresh_draw_every_second(self):
        e = new_engine(2)
        prev = {s: e.price(s) for s in se.BY_SYM}
        worst = 0.0
        t = T0
        for _ in range(900):
            t += 1000
            e.tick(t)
            for s in se.BY_SYM:
                worst = max(worst, abs(e.price(s) / prev[s] - 1))
                prev[s] = e.price(s)
        self.assertLessEqual(worst, se.MAX_STEP + 0.031, "a normal second moves a price a little (an event may add up to 3%)")
        self.assertLess(statistics.median(abs(e.price(s) / se.BY_SYM[s]["price"] - 1) for s in se.BY_SYM), 0.2)

    def test_every_single_update_respects_the_move_limit(self):
        e = new_engine(3)
        t = T0
        quiet_cap = se.MAX_STEP
        for _ in range(2000):
            before = {s: e.price(s) for s in se.BY_SYM}
            news_before = len(e.s["news"])
            t += 1000
            e.tick(t)
            if len(e.s["news"]) != news_before:
                continue                                                 # an event step may include its small jump
            for s in se.BY_SYM:
                self.assertLessEqual(abs(e.price(s) / before[s] - 1), quiet_cap + 1e-9)

    def test_prices_stay_inside_their_limits_for_a_simulated_month(self):
        e = new_engine(4)
        run(e, 30 * 86400, step=60)
        for s, st in e.s["co"].items():
            fair = math.exp(st["lnf"])
            self.assertGreaterEqual(st["p"], se.MIN_PRICE)
            self.assertLessEqual(st["p"], se.MAX_PRICE)
            self.assertGreaterEqual(st["p"], fair * se.BAND[0] * 0.999)
            self.assertLessEqual(st["p"], fair * se.BAND[1] * 1.001)
            self.assertTrue(math.isfinite(st["p"]))
            for _, p in e.s["ticks"][s]:
                self.assertGreater(p, 0)

    def test_volatility_clusters_calm_and_busy_stretches(self):
        e = new_engine(5)
        t, rets, last = T0, [], e.price("NEXO")
        for _ in range(60 * 24 * 14):                                       # two weeks of one-minute returns
            t += 60_000
            e.tick(t) if False else (e.step(60, t), e._record(t), e.s.__setitem__("t", t))
            rets.append(math.log(e.price("NEXO") / last))
            last = e.price("NEXO")
        sq = [r * r for r in rets]
        mean = statistics.mean(sq)
        num = sum((a - mean) * (b - mean) for a, b in zip(sq, sq[1:]))
        den = sum((a - mean) ** 2 for a in sq)
        self.assertGreater(num / den, 0.02, "big moves tend to follow big moves")

    def test_variance_grows_with_the_time_horizon_like_a_real_price(self):
        ratios = []
        for seed in range(6):
            e = new_engine(10 + seed)
            t, series = T0, []
            for _ in range(60 * 24 * 10):
                t += 60_000
                e.step(60, t)
                series.append(math.log(e.price("ATLS")))
            r1 = [b - a for a, b in zip(series, series[1:])]
            r60 = [series[i + 60] - series[i] for i in range(0, len(series) - 60, 60)]
            ratios.append(statistics.pvariance(r60) / statistics.pvariance(r1) / 60)
        avg = statistics.mean(ratios)
        self.assertGreater(avg, 0.4)
        self.assertLess(avg, 3.0)

    def test_companies_in_one_sector_move_together_more_than_strangers(self):
        e = new_engine(21)
        t = T0
        hist = {s: [] for s in se.BY_SYM}
        last = {s: e.price(s) for s in se.BY_SYM}
        for _ in range(60 * 24 * 20):
            t += 60_000
            e.step(60, t)
            for s in se.BY_SYM:
                hist[s].append(math.log(e.price(s) / last[s]))
                last[s] = e.price(s)

        def corr(a, b):
            ma, mb = statistics.mean(hist[a]), statistics.mean(hist[b])
            num = sum((x - ma) * (y - mb) for x, y in zip(hist[a], hist[b]))
            return num / math.sqrt(sum((x - ma) ** 2 for x in hist[a]) * sum((y - mb) ** 2 for y in hist[b]))
        same, other = [], []
        syms = list(se.BY_SYM)
        for i, a in enumerate(syms):
            for b in syms[i + 1:]:
                (same if se.BY_SYM[a]["sector"] == se.BY_SYM[b]["sector"] else other).append(corr(a, b))
        self.assertGreater(statistics.mean(other), 0.03, "a market factor moves everybody a little")
        self.assertGreater(statistics.mean(same), statistics.mean(other) + 0.05, "sector factors move peers more")

    def test_there_is_no_built_in_up_or_down_drift(self):
        finals = []
        for seed in range(40):
            e = new_engine(100 + seed)
            run(e, 12 * 3600, step=60)
            finals.append(statistics.mean(math.log(e.price(s) / se.BY_SYM[s]["price"]) for s in se.BY_SYM))
        self.assertLess(abs(statistics.mean(finals)), 0.03)

    def test_candles_are_consistent_and_line_up_with_their_intervals(self):
        e = new_engine(6)
        run(e, 4 * 3600, step=5)
        for s in ("LUMA", "NEXO"):
            for iv, rows in e.s["candles"][s].items():
                for r in rows:
                    self.assertLessEqual(r["l"], min(r["o"], r["c"]) + 1e-9)
                    self.assertGreaterEqual(r["h"], max(r["o"], r["c"]) - 1e-9)
                    if iv != "1d":
                        self.assertEqual(r["t"] % se.INTERVALS[iv], 0)
                times = [r["t"] for r in rows]
                self.assertEqual(times, sorted(set(times)))
            five = [r for r in e.s["candles"][s]["5m"][:-1]]
            ones = e.s["candles"][s]["1m"]
            for r in five[1:3]:
                inside = [o for o in ones if r["t"] <= o["t"] < r["t"] + 300_000]
                self.assertAlmostEqual(r["h"], max(o["h"] for o in inside), places=4)
                self.assertAlmostEqual(r["l"], min(o["l"] for o in inside), places=4)
                self.assertAlmostEqual(r["c"], inside[-1]["c"], places=4)

    def test_history_is_kept_in_sensible_amounts(self):
        e = new_engine(7)
        run(e, 3 * 86400, step=30)
        for s in e.s["co"]:
            self.assertLessEqual(len(e.s["ticks"][s]), se.TICKS_KEEP)
            for iv, rows in e.s["candles"][s].items():
                self.assertLessEqual(len(rows), se.CANDLE_KEEP[iv])
        self.assertLessEqual(len(e.s["news"]), se.NEWS_KEEP)
        self.assertLess(len(e.snapshot()), 6_000_000)

    def test_news_is_labelled_simulated_and_not_too_frequent(self):
        e = new_engine(8)
        run(e, 6 * 3600, step=5)
        self.assertGreater(len(e.s["news"]), 5)
        for n in e.s["news"]:
            self.assertTrue(n["simulated"])
            self.assertTrue(n["text"] and n["syms"])
            self.assertTrue(set(n["syms"]) <= set(se.BY_SYM))
        per_company = {}
        for n in sorted((n for n in e.s["news"] if n["scope"] in se.BY_SYM and n["dir"]), key=lambda n: n["t"]):
            last = per_company.get(n["scope"], -10 ** 15)
            self.assertGreaterEqual(n["t"] - last, 600_000)
            per_company[n["scope"]] = n["t"]
        for ev in se.EVENTS:
            self.assertIn(ev[0], list(se.BY_SYM) + se.SECTORS + ["*"])

    def test_a_very_sharp_move_pauses_trading_for_a_moment(self):
        e = new_engine(9)
        t = run(e, 400, step=1)
        e.s["co"]["SELV"]["p"] = round(e.s["co"]["SELV"]["p"] * 1.12, 4)
        e.tick(t + 1000)
        self.assertTrue(e.halted("SELV", t + 1000))
        self.assertFalse(e.halted("AURA", t + 1000))
        self.assertFalse(e.halted("SELV", t + 1000 + se.CIRCUIT_PAUSE_S * 1000 + 1))
        self.assertTrue(any("paused" in n["text"] and "circuit breaker" in n["text"] for n in e.s["news"]))

    def test_the_real_market_uses_secure_unpredictable_randomness(self):
        self.assertIsInstance(se.Engine().rng, random.SystemRandom)


class SavingAndRestarting(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "market.json")

    def test_a_saved_market_carries_on_exactly_where_it_was(self):
        a = new_engine(1, self.path)
        t = run(a, 1800, step=1)
        self.assertTrue(a.save())
        b = se.Engine(path=self.path, rng=random.Random(99), clock=lambda: t)
        b.load()
        self.assertIsNone(b.catchup, "no time passed, nothing to replay")
        self.assertEqual(json.dumps(a.s, sort_keys=True), json.dumps(b.s, sort_keys=True))
        a.rng, b.rng = random.Random(555), random.Random(555)
        for i in range(120):
            a.tick(t + 1000 * (i + 1))
            b.tick(t + 1000 * (i + 1))
        self.assertEqual({s: a.price(s) for s in se.BY_SYM}, {s: b.price(s) for s in se.BY_SYM})
        self.assertEqual(a.s["candles"]["LUMA"]["1m"], b.s["candles"]["LUMA"]["1m"])

    def test_history_prices_and_news_survive(self):
        a = new_engine(2, self.path)
        t = run(a, 3600, step=2)
        a.save()
        b = se.Engine(path=self.path, rng=random.Random(2), clock=lambda: t)
        b.load()
        for s in se.BY_SYM:
            self.assertEqual(a.price(s), b.price(s))
            self.assertEqual(a.s["ticks"][s], b.s["ticks"][s])
        self.assertEqual(a.s["news"], b.s["news"])

    def test_while_the_server_is_off_the_market_is_replayed_in_one_minute_steps_and_the_gap_is_marked(self):
        a = new_engine(3, self.path)
        t = run(a, 600, step=1)
        a.save()
        later = t + 2 * 3600 * 1000
        b = se.Engine(path=self.path, rng=random.Random(4), clock=lambda: later)
        b.load()
        self.assertEqual((b.catchup["missedSeconds"], b.catchup["replayedSeconds"], b.catchup["capped"]), (7200, 7200, False))
        self.assertEqual(b.s["t"], later)
        flagged = [r for r in b.s["candles"]["LUMA"]["1m"] if r.get("g")]
        self.assertGreaterEqual(len(flagged), 100)
        for s in se.BY_SYM:
            self.assertTrue(se.MIN_PRICE <= b.price(s) <= se.MAX_PRICE)
        self.assertTrue(all(abs(b.s["ticks"][s][i + 1][1] / b.s["ticks"][s][i][1] - 1) < 0.16
                            for s in ("NEXO",) for i in range(len(b.s["ticks"][s]) - 1)))

    def test_a_very_long_outage_is_replayed_for_no_more_than_the_limit(self):
        a = new_engine(5, self.path)
        t = run(a, 300, step=1)
        a.save()
        later = t + 20 * 86400 * 1000
        b = se.Engine(path=self.path, rng=random.Random(6), clock=lambda: later)
        b.load()
        self.assertTrue(b.catchup["capped"])
        self.assertEqual(b.catchup["replayedSeconds"], economy.STOCK_CATCHUP_MAX_S)
        self.assertEqual(b.catchup["missedSeconds"], 20 * 86400)
        rows = b.s["candles"]["LUMA"]["1h"]
        self.assertGreaterEqual(rows[-1]["t"], later - economy.STOCK_CATCHUP_MAX_S * 1000 - 3_600_000)
        for s in se.BY_SYM:
            self.assertTrue(se.MIN_PRICE <= b.price(s) <= se.MAX_PRICE)
        self.assertLess(sum(len(b.s["news"]) for _ in [0]), se.NEWS_KEEP + 1)

    def test_a_missing_or_damaged_file_starts_a_fresh_market_instead_of_failing(self):
        e = se.Engine(path=self.path, rng=random.Random(1), clock=lambda: T0)
        e.load()
        self.assertEqual(e.price("NEXO"), se.BY_SYM["NEXO"]["price"])
        with open(self.path, "w") as f:
            f.write("{not json")
        e2 = se.Engine(path=self.path, rng=random.Random(1), clock=lambda: T0)
        e2.load()
        self.assertEqual(e2.price("NEXO"), se.BY_SYM["NEXO"]["price"])
        with open(self.path, "w") as f:
            json.dump({"v": 1, "co": {"X": {}}}, f)
        e3 = se.Engine(path=self.path, rng=random.Random(1), clock=lambda: T0)
        e3.load()
        self.assertEqual(set(e3.s["co"]), set(se.BY_SYM))

    def test_saving_never_leaves_half_a_file_around(self):
        a = new_engine(1, self.path)
        a.dirty = True
        a.save()
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".part")], [])
        with open(self.path) as f:
            json.load(f)
        self.assertFalse(a.save(), "nothing changed, nothing written")


class Trading(unittest.TestCase):
    def setUp(self):
        fresh_store()
        exchange.engine = new_engine(1)
        exchange.QUOTES.clear()
        self.u = mk("alice", weekly=1000, accum=10_000)
        self.now = T0 + 5000

    def buy(self, sym, n, **kw):
        q = exchange.quote(self.u, {"symbol": sym, "side": "buy", "shares": n}, self.now)
        return exchange.trade(self.u, {"quoteId": q["quoteId"], **kw}, self.now)

    def sell(self, sym, n, **kw):
        q = exchange.quote(self.u, {"symbol": sym, "side": "sell", "shares": n}, self.now)
        return exchange.trade(self.u, {"quoteId": q["quoteId"], **kw}, self.now)

    # ---- the quote ---------------------------------------------------------------------------------------------
    def test_a_quote_shows_everything_before_you_commit(self):
        q = exchange.quote(self.u, {"symbol": "NEXO", "side": "buy", "shares": 10}, self.now)
        mid = exchange.engine.price("NEXO")
        bid, ask = exchange.prices_c(mid)
        self.assertEqual((q["symbol"], q["side"], q["shares"], q["price"], q["total"]), ("NEXO", "buy", 10, ask / 100, round(10 * ask / 100, 2)))
        self.assertGreater(q["ask"], q["bid"])
        self.assertEqual((q["balance"], q["balanceAfter"], q["canAfford"], q["account"]), (10_000.0, round(10_000 - q["total"], 2), True, "accumulated"))
        self.assertEqual((q["owned"], q["ownedAfter"]), (0, 10))
        self.assertEqual(q["expiresAt"], self.now + int(economy.STOCK_QUOTE_TTL_S * 1000))
        self.assertGreater(q["worstTotal"], q["total"])
        self.assertEqual(self.u["accum"], 10_000.0, "asking changes nothing")

    def test_a_sell_quote_pays_the_bid(self):
        self.buy("ORBT", 5)
        q = exchange.quote(self.u, {"symbol": "ORBT", "side": "sell", "shares": 3}, self.now)
        bid, _ = exchange.prices_c(exchange.engine.price("ORBT"))
        self.assertEqual((q["price"], q["total"], q["ownedAfter"]), (bid / 100, round(3 * bid / 100, 2), 2))
        self.assertLess(q["worstTotal"], q["total"])

    def test_bad_orders_are_refused_with_a_reason(self):
        cases = [({"symbol": "NOPE", "side": "buy", "shares": 1}, 404), ({"symbol": "NEXO", "side": "short", "shares": 1}, 400),
                 ({"symbol": "NEXO", "side": "buy", "shares": 0}, 400), ({"symbol": "NEXO", "side": "buy", "shares": -3}, 400),
                 ({"symbol": "NEXO", "side": "buy", "shares": 1.5}, 400), ({"symbol": "NEXO", "side": "buy", "shares": "abc"}, 400),
                 ({"symbol": "NEXO", "side": "buy", "shares": None}, 400), ({"symbol": "NEXO", "side": "buy", "shares": True}, 400),
                 ({"symbol": "NEXO", "side": "buy", "shares": economy.STOCK_MAX_ORDER_SHARES + 1}, 400), ({"symbol": 5, "side": "buy", "shares": 1}, 404),
                 ({"symbol": "NEXO", "side": "sell", "shares": 1}, 400)]
        for body, status in cases:
            self.assertEqual(err(exchange.quote, self.u, body, self.now).status, status, body)
        self.assertEqual(exchange.parse_shares("12"), 12)
        self.assertEqual(exchange.parse_shares(12.0), 12)

    # ---- buying and selling ------------------------------------------------------------------------------------
    def test_a_buy_is_paid_from_the_accumulated_account_at_the_ask(self):
        mid = exchange.engine.price("COBL")
        _, ask = exchange.prices_c(mid)
        r = self.buy("COBL", 7)
        self.assertEqual((r["price"], r["total"], r["balanceBefore"], r["balanceAfter"], r["account"]), (ask / 100, round(7 * ask / 100, 2), 10_000.0, round(10_000 - 7 * ask / 100, 2), "accumulated"))
        self.assertEqual((self.u["balance"], self.u["accum"]), (1000.0, r["balanceAfter"]), "the weekly account is untouched")
        pos = self.u["pos"]["COBL"]
        self.assertEqual((pos["sh"], pos["cost_c"]), (7, 7 * ask))
        self.assertEqual(r["position"]["avgCost"], ask / 100)
        row = ledger.entries(self.u)[0]
        self.assertEqual((row["account"], row["reason"], row["ref"], row["amount"]), ("accumulated", "stocks.buy", "COBL", -r["total"]))
        self.assertTrue(books_balance(self.u))
        self.assertEqual(exchange.engine.price("COBL"), mid, "a trade does not move the price")

    def test_a_sell_pays_the_bid_and_records_the_gain_or_loss(self):
        self.buy("LUMA", 10)
        cost = self.u["pos"]["LUMA"]["cost_c"]
        exchange.engine.s["co"]["LUMA"]["p"] = round(exchange.engine.price("LUMA") * 1.05, 4)        # the price rises
        bid, _ = exchange.prices_c(exchange.engine.price("LUMA"))
        r = self.sell("LUMA", 4)
        basis = round(cost * 4 / 10)
        self.assertEqual((r["price"], r["total"], r["realized"]), (bid / 100, round(4 * bid / 100, 2), round((4 * bid - basis) / 100, 2)))
        self.assertEqual(self.u["pos"]["LUMA"]["sh"], 6)
        self.assertEqual(self.u["pos"]["LUMA"]["cost_c"], cost - basis)
        r2 = self.sell("LUMA", 6)
        self.assertEqual(self.u["pos"]["LUMA"]["sh"], 0)
        self.assertEqual(self.u["pos"]["LUMA"]["cost_c"], 0, "no cost left over once everything is sold")
        self.assertEqual(self.u["pos"]["LUMA"]["real_c"], 10 * bid - cost)
        self.assertGreater(self.u["pos"]["LUMA"]["real_c"], 0)
        self.assertTrue(books_balance(self.u))

    def test_you_can_not_spend_more_than_you_have_or_sell_more_than_you_own(self):
        poor = mk("poor", weekly=9999, accum=50)
        q = exchange.quote(poor, {"symbol": "NEXO", "side": "buy", "shares": 1}, self.now)
        self.assertFalse(q["canAfford"])
        e = err(exchange.trade, poor, {"quoteId": q["quoteId"]}, self.now)
        self.assertEqual(e.status, 400)
        self.assertIn("Not enough in your accumulated account", e.message)
        self.assertEqual((poor["accum"], poor["balance"]), (50.0, 9999.0), "the weekly account cannot pay for shares")
        self.assertEqual(_shares(poor, "NEXO"), 0)
        self.buy("AURA", 3)
        self.assertEqual(err(exchange.quote, self.u, {"symbol": "AURA", "side": "sell", "shares": 4}, self.now).status, 400)

    def test_the_exact_balance_can_be_spent_but_not_a_cent_more(self):
        _, ask = exchange.prices_c(exchange.engine.price("PRSM"))
        exact = mk("exact", weekly=0, accum=ask * 3 / 100)
        self.assertEqual(self.buy_for(exact, "PRSM", 3)["balanceAfter"], 0.0)
        short = mk("short", weekly=0, accum=(ask * 3 - 1) / 100)
        q = exchange.quote(short, {"symbol": "PRSM", "side": "buy", "shares": 3}, self.now)
        self.assertEqual(err(exchange.trade, short, {"quoteId": q["quoteId"]}, self.now).status, 400)
        self.assertEqual(short["accum"], (ask * 3 - 1) / 100)

    def buy_for(self, user, sym, n):
        q = exchange.quote(user, {"symbol": sym, "side": "buy", "shares": n}, self.now)
        return exchange.trade(user, {"quoteId": q["quoteId"]}, self.now)

    def test_buying_and_straight_away_selling_always_loses(self):
        ledger.post(self.u, "accumulated", 10_000_000, "test.setup")
        for sym in se.BY_SYM:
            for n in (1, 2, 3, 10, 57, 1000):
                before = self.u["accum"]
                self.buy(sym, n)
                self.sell(sym, n)
                self.assertLess(self.u["accum"], before, (sym, n))
                lost_c = ledger.to_cents(before) - ledger.to_cents(self.u["accum"])
                self.assertGreaterEqual(lost_c, n, "at least a cent a share")
                self.assertTrue(books_balance(self.u))

    def test_no_sequence_of_trades_at_one_price_ever_makes_money(self):
        rng = random.Random(3)
        start = ledger.to_cents(self.u["accum"])
        for _ in range(400):
            sym = rng.choice(list(se.BY_SYM))
            own = _shares(self.u, sym)
            if own and rng.random() < 0.5:
                self.sell(sym, rng.randint(1, own))
            else:
                _, ask = exchange.prices_c(exchange.engine.price(sym))
                afford = ledger.balance_c(self.u, "accumulated") // ask
                if afford:
                    self.buy(sym, rng.randint(1, min(afford, 40)))
        for sym in se.BY_SYM:                                               # then cash everything in at the same prices
            if _shares(self.u, sym):
                self.sell(sym, _shares(self.u, sym))
        self.assertLess(ledger.to_cents(self.u["accum"]), start)
        self.assertTrue(books_balance(self.u))

    def test_the_cost_basis_always_adds_up_to_what_was_paid(self):
        rng = random.Random(8)
        paid = sold_basis = 0
        for _ in range(200):
            own = _shares(self.u, "SELV")
            if own and rng.random() < 0.55:
                n = rng.randint(1, own)
                before = self.u["pos"]["SELV"]["cost_c"]
                self.sell("SELV", n)
                sold_basis += before - self.u["pos"]["SELV"]["cost_c"]
            else:
                r = self.buy("SELV", rng.randint(1, 30))
                paid += ledger.to_cents(r["total"])
            exchange.engine.s["co"]["SELV"]["p"] = round(exchange.engine.price("SELV") * rng.uniform(0.97, 1.03), 4)
        self.assertEqual(paid, sold_basis + self.u["pos"]["SELV"]["cost_c"])
        self.assertGreaterEqual(self.u["pos"]["SELV"]["cost_c"], 0)

    # ---- the quote's life --------------------------------------------------------------------------------------
    def test_a_quote_expires_and_you_get_a_fresh_one(self):
        q = exchange.quote(self.u, {"symbol": "NEXO", "side": "buy", "shares": 2}, self.now)
        late = self.now + int(economy.STOCK_QUOTE_TTL_S * 1000) + 1
        e = err(exchange.trade, self.u, {"quoteId": q["quoteId"]}, late)
        self.assertEqual(e.status, 409)
        self.assertIn("expired", e.message)
        self.assertEqual(e.data["quote"]["shares"], 2)
        self.assertNotEqual(e.data["quote"]["quoteId"], q["quoteId"])
        self.assertEqual(_shares(self.u, "NEXO"), 0)
        ok = exchange.trade(self.u, {"quoteId": e.data["quote"]["quoteId"]}, late)
        self.assertEqual(ok["shares"], 2)

    def test_if_the_price_moves_too_far_before_you_confirm_nothing_is_filled(self):
        q = exchange.quote(self.u, {"symbol": "ATLS", "side": "buy", "shares": 5}, self.now)
        exchange.engine.s["co"]["ATLS"]["p"] = round(exchange.engine.price("ATLS") * 1.02, 4)         # +2%: beyond the tolerance
        e = err(exchange.trade, self.u, {"quoteId": q["quoteId"]}, self.now)
        self.assertEqual(e.status, 409)
        self.assertIn("price moved", e.message)
        self.assertGreater(e.data["quote"]["price"], q["price"])
        self.assertEqual((self.u["accum"], _shares(self.u, "ATLS")), (10_000.0, 0))

    def test_a_small_move_fills_at_the_current_price_in_both_directions_so_waiting_gains_nothing(self):
        for factor in (1.003, 0.997):
            fresh_store()
            exchange.QUOTES.clear()
            exchange.engine = new_engine(1)
            u = mk("watcher", weekly=100, accum=10_000)
            q = exchange.quote(u, {"symbol": "ATLS", "side": "buy", "shares": 5}, self.now)
            exchange.engine.s["co"]["ATLS"]["p"] = round(exchange.engine.price("ATLS") * factor, 4)
            current = exchange.quote(u, {"symbol": "ATLS", "side": "buy", "shares": 5}, self.now)
            r = exchange.trade(u, {"quoteId": q["quoteId"]}, self.now)
            self.assertEqual(r["price"], current["price"], "filled at what the market says now, not at the old quote")
            self.assertNotEqual(r["price"], q["price"])

    def test_a_quote_is_one_use_and_belongs_to_one_person(self):
        q = exchange.quote(self.u, {"symbol": "MARE", "side": "buy", "shares": 1}, self.now)
        other = mk("other", accum=5000)
        e = err(exchange.trade, other, {"quoteId": q["quoteId"]}, self.now)
        self.assertEqual(e.status, 404)
        exchange.trade(self.u, {"quoteId": q["quoteId"]}, self.now)
        self.assertEqual(err(exchange.trade, self.u, {"quoteId": q["quoteId"]}, self.now).status, 409)
        self.assertEqual(err(exchange.trade, self.u, {"quoteId": "nope"}, self.now).status, 404)
        self.assertEqual(err(exchange.trade, self.u, {}, self.now).status, 404)
        self.assertEqual(_shares(self.u, "MARE"), 1)

    def test_paused_trading_refuses_orders(self):
        q = exchange.quote(self.u, {"symbol": "SELV", "side": "buy", "shares": 1}, self.now)
        exchange.engine.s["co"]["SELV"]["halt"] = self.now + 30_000
        self.assertEqual(err(exchange.quote, self.u, {"symbol": "SELV", "side": "buy", "shares": 1}, self.now).status, 409)
        self.assertEqual(err(exchange.trade, self.u, {"quoteId": q["quoteId"]}, self.now).status, 409)
        self.assertEqual(self.u["accum"], 10_000.0)

    # ---- duplicates and concurrency ---------------------------------------------------------------------------
    def test_a_retried_order_with_the_same_request_id_fills_once(self):
        q = exchange.quote(self.u, {"symbol": "BRVA", "side": "buy", "shares": 4}, self.now)
        a = exchange.trade(self.u, {"quoteId": q["quoteId"], "requestId": "order-0000001"}, self.now)
        b = exchange.trade(self.u, {"quoteId": q["quoteId"], "requestId": "order-0000001"}, self.now)
        self.assertEqual((a["duplicate"], b["duplicate"]), (False, True))
        self.assertEqual(a["tradeId"], b["tradeId"])
        self.assertEqual(_shares(self.u, "BRVA"), 4)
        self.assertEqual(len([r for r in ledger.entries(self.u) if r["reason"] == "stocks.buy"]), 1)
        q2 = exchange.quote(self.u, {"symbol": "BRVA", "side": "buy", "shares": 4}, self.now)
        self.assertEqual(err(exchange.trade, self.u, {"quoteId": q2["quoteId"], "requestId": "order-0000001"}, self.now).status, 409)
        self.assertEqual(err(exchange.trade, self.u, {"quoteId": q2["quoteId"], "requestId": "x"}, self.now).message, "Invalid request id")

    def test_twenty_people_clicking_the_same_quote_at_once_fill_it_exactly_once(self):
        q = exchange.quote(self.u, {"symbol": "COBL", "side": "buy", "shares": 3}, self.now)
        out = []

        def go():
            try:
                with server.LOCK:
                    out.append(exchange.trade(self.u, {"quoteId": q["quoteId"]}, self.now))
            except ApiError as e:
                out.append(e)
        ts = [threading.Thread(target=go) for _ in range(20)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len([o for o in out if isinstance(o, dict)]), 1)
        self.assertEqual(_shares(self.u, "COBL"), 3)

    def test_many_buyers_and_sellers_at_once_keep_every_cent_accounted_for(self):
        people = [mk(f"trader{i}", weekly=0, accum=5000) for i in range(8)]
        errors = []

        def work(u, seed):
            rng = random.Random(seed)
            try:
                for _ in range(40):
                    sym = rng.choice(["NEXO", "LUMA", "AURA", "PRSM"])
                    with server.LOCK:
                        own = _shares(u, sym)
                        side = "sell" if own and rng.random() < 0.45 else "buy"
                        n = rng.randint(1, own) if side == "sell" else rng.randint(1, 8)
                        try:
                            q = exchange.quote(u, {"symbol": sym, "side": side, "shares": n}, self.now)
                            exchange.trade(u, {"quoteId": q["quoteId"]}, self.now)
                        except ApiError as e:
                            if e.status not in (400, 409):
                                errors.append(e)
            except Exception as e:                                          # pragma: no cover
                errors.append(e)
        ts = [threading.Thread(target=work, args=(u, i)) for i, u in enumerate(people)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errors, [])
        for u in people:
            self.assertGreaterEqual(u["accum"], 0)
            self.assertTrue(books_balance(u))
            spent = sum(t["total"] for t in u.get("trades", []) if t["side"] == "buy")
            got = sum(t["total"] for t in u.get("trades", []) if t["side"] == "sell")
            self.assertEqual(ledger.to_cents(u["accum"]), 500_000 - spent + got)
            for sym, p in u["pos"].items():
                self.assertGreaterEqual(p["sh"], 0)
                self.assertGreaterEqual(p["cost_c"], 0)
                self.assertEqual(p["sh"] == 0, p["cost_c"] == 0)

    # ---- the picture of what you own --------------------------------------------------------------------------
    def test_the_portfolio_values_holdings_at_what_they_would_sell_for(self):
        self.buy("NEXO", 10)
        self.buy("AURA", 20)
        exchange.engine.s["co"]["NEXO"]["p"] = round(exchange.engine.price("NEXO") * 1.1, 4)
        self.sell("AURA", 5)
        p = exchange.portfolio(self.u)
        nexo = [r for r in p["positions"] if r["symbol"] == "NEXO"][0]
        bid, _ = exchange.prices_c(exchange.engine.price("NEXO"))
        self.assertEqual((nexo["shares"], nexo["value"], nexo["bid"]), (10, round(10 * bid / 100, 2), bid / 100))
        self.assertAlmostEqual(nexo["unrealized"], nexo["value"] - nexo["cost"], places=2)
        self.assertAlmostEqual(nexo["avgCost"], nexo["cost"] / 10, places=4)
        self.assertEqual(p["cash"], self.u["accum"])
        self.assertAlmostEqual(p["total"], p["cash"] + p["stockValue"], places=2)
        self.assertAlmostEqual(p["unrealized"], sum(r["unrealized"] for r in p["positions"]), places=2)
        self.assertEqual(len(p["trades"]), 3)
        self.assertEqual(p["trades"][0]["side"], "sell")
        self.assertIsNotNone(p["trades"][0]["realized"])
        self.assertAlmostEqual(p["realized"], p["trades"][0]["realized"], places=2)

    def test_realized_gains_are_kept_after_a_position_is_closed(self):
        self.buy("AURA", 10)
        exchange.engine.s["co"]["AURA"]["p"] = round(exchange.engine.price("AURA") * 1.04, 4)
        self.sell("AURA", 10)
        p = exchange.portfolio(self.u)
        self.assertEqual(p["positions"], [])
        self.assertEqual(p["closed"][0]["symbol"], "AURA")
        self.assertGreater(p["realized"], 0)

    def test_the_stock_account_does_not_touch_the_weekly_leaderboard_or_the_weekly_reset(self):
        from backend import weekly
        from tests.econ import circle_of
        pal = mk("pal")
        crew = circle_of(self.u, pal)
        before = {r["user"]["username"]: (r["delta"], r["value"]) for r in weekly.standings(crew, __import__("backend.util", fromlist=["week_key"]).week_key())}
        self.buy("NEXO", 20)
        after = {r["user"]["username"]: (r["delta"], r["value"]) for r in weekly.standings(crew, __import__("backend.util", fromlist=["week_key"]).week_key())}
        self.assertEqual(before, after)
        accum, shares = self.u["accum"], _shares(self.u, "NEXO")
        weekly.refill_weekly("2999-01-04")
        self.assertEqual((self.u["accum"], _shares(self.u, "NEXO")), (accum, shares))


def _shares(u, sym):
    return (u.get("pos", {}).get(sym) or {}).get("sh", 0)


class ListingsAndDetails(unittest.TestCase):
    def setUp(self):
        fresh_store()
        exchange.engine = new_engine(2)
        run(exchange.engine, 1800, step=2)
        self.u = mk("alice", accum=5000)

    def test_the_list_has_everything_a_row_needs(self):
        out = exchange.listing(self.u)
        self.assertEqual(len(out["stocks"]), 10)
        self.assertTrue(out["simulated"])
        row = out["stocks"][0]
        self.assertTrue({"symbol", "name", "sector", "price", "bid", "ask", "change", "changePct", "halted", "spark"} <= set(row))
        self.assertTrue(len(row["spark"]) > 10)
        self.assertEqual(out["accumulated"], 5000.0)
        self.assertTrue(all(n["simulated"] for n in out["news"]))

    def test_a_company_page_has_chart_history_news_position_and_transactions(self):
        q = exchange.quote(self.u, {"symbol": "NEXO", "side": "buy", "shares": 3}, T0 + 4000)
        exchange.trade(self.u, {"quoteId": q["quoteId"]}, T0 + 4000)
        d = exchange.detail(self.u, "NEXO", "1m", 100)
        self.assertEqual((d["symbol"], d["name"], d["sector"]), ("NEXO", "Nexo Robotics", "Technology"))
        self.assertTrue(d["about"] and d["simulated"])
        self.assertTrue({"price", "change", "changePct", "high24", "low24", "bid", "ask", "candles", "ticks", "news", "position", "trades"} <= set(d))
        self.assertTrue(0 < len(d["candles"]) <= 100)
        self.assertEqual(d["position"]["shares"], 3)
        self.assertEqual(len(d["trades"]), 1)
        self.assertLessEqual(d["low24"], d["price"] + 1e-9)
        self.assertGreaterEqual(d["high24"], d["price"] - 1e-9)
        for iv in se.INTERVALS:
            self.assertTrue(exchange.detail(self.u, "nexo".upper(), iv, 50)["candles"])
        self.assertEqual(err(exchange.detail, self.u, "NEXO", "1w").status, 400)
        self.assertEqual(err(exchange.detail, self.u, "ZZZZ").status, 404)


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        exchange.engine = se.Engine(rng=random.Random(5))
        exchange.engine.s = exchange.engine.fresh(now_ms())
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_sign_in_is_required(self):
        anon = Client(self.port)
        for method, path in (("GET", "/api/stocks"), ("GET", "/api/stocks/NEXO"), ("POST", "/api/stocks/quote"), ("POST", "/api/stocks/trade"), ("GET", "/api/stocks/portfolio")):
            self.assertEqual(anon.call(method, path, {})[0], 401, path)

    def test_a_whole_trade_through_the_server(self):
        c = Client(self.port)
        c.call("POST", "/api/auth/register", {"username": "marketeer", "password": "secret123"})
        with server.LOCK:
            ledger.post(users.by_username("marketeer"), "accumulated", 2000, "test.setup")
        st, listing = c.call("GET", "/api/stocks")
        self.assertEqual((st, len(listing["stocks"])), (200, 10))
        st, d = c.call("GET", "/api/stocks/nexo?interval=1m")
        self.assertEqual((st, d["symbol"]), (200, "NEXO"))
        st, q = c.call("POST", "/api/stocks/quote", {"symbol": "NEXO", "side": "buy", "shares": 4})
        self.assertEqual((st, q["shares"], q["account"]), (200, 4, "accumulated"))
        st, t = c.call("POST", "/api/stocks/trade", {"quoteId": q["quoteId"], "requestId": "http-order-0001"})
        self.assertEqual((st, t["shares"], t["user"]["weekly"]), (200, 4, 1000.0))
        self.assertAlmostEqual(t["user"]["accum"], 2000 - t["total"], places=2)
        st, again = c.call("POST", "/api/stocks/trade", {"quoteId": q["quoteId"], "requestId": "http-order-0001"})
        self.assertEqual((st, again["duplicate"]), (200, True))
        st, p = c.call("GET", "/api/stocks/portfolio")
        self.assertEqual((st, p["positions"][0]["shares"], p["trades"][0]["side"]), (200, 4, "buy"))
        st, e = c.call("POST", "/api/stocks/quote", {"symbol": "NEXO", "side": "sell", "shares": 5})
        self.assertEqual(st, 400)
        st, q2 = c.call("POST", "/api/stocks/quote", {"symbol": "NEXO", "side": "buy", "shares": 1})
        exchange.engine.s["co"]["NEXO"]["p"] = round(exchange.engine.price("NEXO") * 1.03, 4)
        st, moved = c.call("POST", "/api/stocks/trade", {"quoteId": q2["quoteId"]})
        self.assertEqual(st, 409)
        self.assertIn("quote", moved)
        self.assertGreater(moved["quote"]["price"], q2["price"])


if __name__ == "__main__":
    unittest.main()
