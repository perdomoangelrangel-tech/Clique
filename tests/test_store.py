"""The Store: products, buying from the accumulated account, owning, equipping, and cosmetics that change nothing but looks."""
import http.client
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                                  # noqa: E402
from backend import catalog, config, cosmetics, economy, games, ledger, users, weekly   # noqa: E402
from backend.store import db, store                                            # noqa: E402
from backend.util import ApiError, now_ms, week_key                            # noqa: E402
from tests.econ import books_balance, circle_of, gain, mk                      # noqa: E402
from tests.helpers import fresh_store, restore_store_path                      # noqa: E402
from tests.test_http import Client                                             # noqa: E402


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def read(path):
    with open(os.path.join(config.STATIC_DIR, path), encoding="utf-8") as f:
        return f.read()


class TheCatalog(unittest.TestCase):
    def test_there_are_plenty_of_products_of_every_kind(self):
        paid = [i for i in catalog.CATALOG.values() if i["price"] > 0]
        self.assertGreaterEqual(len(paid), 8)
        kinds = {i["kind"] for i in paid}
        self.assertEqual(kinds, set(catalog.KINDS))
        self.assertEqual(len(catalog.CATALOG), len(catalog.ITEMS), "no two products share an id")

    def test_every_default_is_a_free_product_of_the_right_kind(self):
        for kind, pid in catalog.DEFAULTS.items():
            it = catalog.CATALOG[pid]
            self.assertEqual((it["kind"], it["price"]), (kind, 0))

    def test_every_product_can_actually_be_drawn(self):
        glyphs = set(re.findall(r"^  (\w+): \(\) =>", read("js/art.js"), re.M))
        for it in catalog.CATALOG.values():
            art, kind = it["art"], it["kind"]
            self.assertTrue(it["name"] and it["desc"], it["id"])
            if kind == "avatar" and not art.get("initial"):
                self.assertTrue(os.path.isfile(os.path.join(config.STATIC_DIR, "casino-icons", "small", art["icon"] + ".png")), it["id"])
                self.assertRegex(art["bg"], r"^#[0-9A-Fa-f]{6}$")
            if kind == "frame" and art["style"] != "none":
                self.assertIn(art["style"], ("solid", "double", "dashed"))
                self.assertRegex(art["color"], r"^#[0-9A-Fa-f]{6}$")
                self.assertTrue(1 <= art["width"] <= 6)
            if kind == "badge" and art.get("glyph"):
                self.assertIn(art["glyph"], glyphs, it["id"])
            if kind == "title" and not art.get("none"):
                self.assertTrue(0 < len(art["text"]) <= 24)
            if kind == "banner":
                self.assertIn(art["pattern"], ("plain", "stripes", "dots", "checks", "waves"))
            if kind == "accent":
                self.assertRegex(art["color"], r"^#[0-9A-Fa-f]{6}$")
            if kind == "font":
                self.assertIn(art["family"], catalog.FONTS)

    def test_the_fonts_the_profile_page_can_use_are_all_shipped_with_the_site(self):
        css = read("css/profile.css") if os.path.exists(os.path.join(config.STATIC_DIR, "css", "profile.css")) else ""
        for family in ("Fraunces", "Rubik Mono One"):
            self.assertIn(family, css)
        for fam in catalog.FONTS.values():
            self.assertNotIn("http", fam)
        for f in re.findall(r"url\(([^)]+)\)", css):
            self.assertTrue(f.strip("'\"").startswith("/fonts/"), "fonts are loaded from this site only")

    def test_prices_and_products_can_be_changed_without_touching_code(self):
        with mock.patch.dict(os.environ, {"STORE_OVERRIDES": json.dumps({"frame_gold": {"price": 900}, "badge_flame": {"available": False},
                                                                           "title_new": {"kind": "title", "name": "Legend", "desc": "x", "price": 77, "art": {"text": "Legend"}}})}):
            c = catalog.build()
        self.assertEqual(c["frame_gold"]["price"], 900.0)
        self.assertFalse(c["badge_flame"]["available"])
        self.assertEqual((c["title_new"]["name"], c["title_new"]["price"], c["title_new"]["kind"]), ("Legend", 77.0, "title"))
        self.assertEqual(c["frame_lime"]["price"], catalog.CATALOG["frame_lime"]["price"])
        for bad in ('{"nope": {"price": 1}}', "[1]", "not json", '{"frame_gold": {"price": 1}, "x": 5}'):
            with mock.patch.dict(os.environ, {"STORE_OVERRIDES": bad}):
                with self.assertRaises(SystemExit):
                    catalog.build()

    def test_the_browser_is_told_what_it_needs_and_nothing_secret(self):
        row = catalog.public(catalog.CATALOG["frame_gold"], owned=False)
        self.assertEqual(set(row), {"id", "kind", "name", "desc", "price", "art", "requires", "free", "owned"})


class Buying(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("alice", weekly=1000, accum=1000)

    def test_a_purchase_is_paid_from_the_accumulated_account_only(self):
        r = cosmetics.buy(self.u, "frame_lime")
        self.assertEqual((r["paid"], r["before"], r["after"], r["duplicate"]), (150.0, 1000.0, 850.0, False))
        self.assertEqual((self.u["accum"], self.u["balance"]), (850.0, 1000.0), "the weekly account is untouched")
        row = ledger.entries(self.u)[0]
        self.assertEqual((row["account"], row["reason"], row["amount"], row["ref"], row["external"]), ("accumulated", "store.buy", -150.0, "frame_lime", False))
        self.assertIn("frame_lime", cosmetics.inventory(self.u))
        self.assertTrue(books_balance(self.u))

    def test_not_enough_money_buys_nothing_and_says_how_much_is_missing(self):
        self.u["accum"] = 100.0
        ledger.post(self.u, "accumulated", 0, "test")
        poor = mk("poor", weekly=5000, accum=100)
        e = err(cosmetics.buy, poor, "frame_lime")
        self.assertEqual(e.status, 402)
        self.assertIn("$50.00 more", e.message)
        self.assertEqual((poor["accum"], poor["balance"]), (100.0, 5000.0), "weekly money cannot pay for the store")
        self.assertNotIn("frame_lime", cosmetics.inventory(poor))

    def test_it_can_not_be_bought_twice(self):
        cosmetics.buy(self.u, "frame_lime")
        e = err(cosmetics.buy, self.u, "frame_lime")
        self.assertEqual((e.status, e.message), (409, "You already own this"))
        self.assertEqual(self.u["accum"], 850.0)

    def test_a_retry_with_the_same_request_id_returns_the_first_result_without_charging_again(self):
        first = cosmetics.buy(self.u, "avatar_mole", "req-abcdefgh-1")
        again = cosmetics.buy(self.u, "avatar_mole", "req-abcdefgh-1")
        self.assertEqual((first["duplicate"], again["duplicate"]), (False, True))
        self.assertEqual({k: first[k] for k in ("paid", "before", "after")}, {k: again[k] for k in ("paid", "before", "after")})
        self.assertEqual(self.u["accum"], 850.0)
        self.assertEqual(len([r for r in ledger.entries(self.u) if r["reason"] == "store.buy"]), 1)
        self.assertEqual(err(cosmetics.buy, self.u, "avatar_bomb", "req-abcdefgh-1").status, 409, "that id belongs to a different purchase")
        self.assertEqual(err(cosmetics.buy, self.u, "avatar_bomb", "x").message, "Invalid request id")

    def test_a_double_click_from_many_threads_charges_exactly_once(self):
        results = []

        def click():
            try:
                with server.LOCK:
                    results.append(cosmetics.buy(self.u, "frame_dashed"))
            except ApiError as e:
                results.append(e)
        threads = [threading.Thread(target=click) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len([r for r in results if isinstance(r, dict)]), 1)
        self.assertEqual(self.u["accum"], 700.0)
        self.assertTrue(books_balance(self.u))

    def test_the_server_checks_the_product_the_requirement_and_the_sale(self):
        self.assertEqual(err(cosmetics.buy, self.u, "nope").status, 404)
        self.assertEqual(err(cosmetics.buy, self.u, None).status, 404)
        self.assertIn("free", err(cosmetics.buy, self.u, "frame_plain").message)
        e = err(cosmetics.buy, self.u, "frame_gold")
        self.assertEqual(e.status, 403)
        self.assertIn("weekly reward 3 times", e.message)
        self.assertEqual(self.u["accum"], 1000.0)
        with mock.patch.dict(catalog.CATALOG["badge_flame"], {"available": False}):
            self.assertEqual(err(cosmetics.buy, self.u, "badge_flame").status, 409)
        with mock.patch.dict(catalog.CATALOG["badge_bolt"], {"until": now_ms() - 1}):
            self.assertEqual(err(cosmetics.buy, self.u, "badge_bolt").status, 409)

    def test_requirements_unlock_when_met(self):
        young = mk("young", accum=2000, age_days=3)
        self.assertEqual(err(cosmetics.buy, young, "title_veteran").status, 403)
        old = mk("oldtimer", accum=2000, age_days=30)
        self.assertEqual(cosmetics.buy(old, "title_veteran")["paid"], 100.0)
        # three paid weekly rewards unlock the gold frame
        a = mk("winner", accum=2000)
        others = [mk(n) for n in ("bobby", "cindy")]
        crew = circle_of(a, *others)
        gain(a, 50)
        for _ in range(3):
            crew["recaps"].pop(week_key(), None)
            weekly.finalize_week(week_key())
            crew["recaps"][f"2026-0{len(crew['recaps']) + 1}-01"] = crew["recaps"].pop(week_key())
        self.assertEqual(cosmetics.rewards_earned(a), 3)
        self.assertEqual(cosmetics.buy(a, "frame_gold")["paid"], 750.0)

    def test_you_can_not_buy_something_you_do_not_have_to_see(self):
        with mock.patch.dict(catalog.CATALOG["badge_ghost"], {"available": False}):
            names = {i["id"] for i in cosmetics.store_view(self.u)["items"]}
        self.assertNotIn("badge_ghost", names)
        self.assertIn("badge_flame", names)

    def test_the_store_tells_each_person_what_they_own_can_afford_and_are_locked_out_of(self):
        cosmetics.buy(self.u, "frame_lime")
        view = cosmetics.store_view(self.u)
        row = {i["id"]: i for i in view["items"]}
        self.assertEqual((view["accumulated"], view["weekly"]), (850.0, 1000.0))
        self.assertEqual((row["frame_lime"]["owned"], row["frame_lime"]["state"], row["frame_lime"]["bought"] is not None), (True, "owned", True))
        self.assertEqual(row["frame_double"]["state"], None)
        self.assertTrue(row["frame_double"]["affordable"])
        self.assertEqual(row["frame_gold"]["state"], "locked")
        self.assertEqual(row["frame_gold"]["progress"], {"have": 0, "need": 3})
        self.assertIn("weekly reward", row["frame_gold"]["requirementText"])
        self.assertFalse(row["avatar_crown"]["affordable"] and self.u["accum"] < 400)
        self.assertTrue(row["frame_plain"]["owned"] and row["frame_plain"]["free"])


class Equipping(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("alice", accum=2000)

    def test_a_new_account_wears_the_free_defaults(self):
        p = cosmetics.profile_json(self.u)
        self.assertEqual(p["slots"], {"avatar": "avatar_initial", "frame": "frame_none", "badge": "badge_none", "title": "title_none",
                                      "banner": "banner_plain", "accent": "accent_lime", "font": "font_display"})
        self.assertEqual((p["bg"], p["bio"], p["upload"], p["style"]), ("ink", "", None, {}))
        self.assertEqual(users.public(self.u), {"id": self.u["id"], "username": "alice", "rank": {"t": "bronze", "d": 3, "l": "Bronze III"}}, "nothing changed, no look is sent (only the rank everybody has)")

    def test_you_can_only_wear_what_you_own(self):
        e = err(cosmetics.equip, self.u, "frame_lime")
        self.assertEqual(e.status, 403)
        self.assertIn("Store first", e.message)
        cosmetics.buy(self.u, "frame_lime")
        self.assertEqual(cosmetics.equip(self.u, "frame_lime")["slots"]["frame"], "frame_lime")
        self.assertEqual(cosmetics.equip(self.u, "frame_plain")["slots"]["frame"], "frame_plain", "free items need no purchase")
        self.assertEqual(err(cosmetics.equip, self.u, "ghost").status, 404)

    def test_one_item_per_slot_and_unequipping_goes_back_to_the_default(self):
        for pid in ("frame_lime", "frame_double", "badge_flame", "title_oracle"):
            cosmetics.buy(self.u, pid)
        cosmetics.equip(self.u, "frame_lime")
        cosmetics.equip(self.u, "frame_double")
        cosmetics.equip(self.u, "badge_flame")
        cosmetics.equip(self.u, "title_oracle")
        s = cosmetics.profile_json(self.u)["slots"]
        self.assertEqual((s["frame"], s["badge"], s["title"]), ("frame_double", "badge_flame", "title_oracle"))
        self.assertEqual(cosmetics.unequip(self.u, "frame")["slots"]["frame"], "frame_none")
        self.assertEqual(err(cosmetics.unequip, self.u, "hat").message, "Unknown slot")

    def test_what_you_wear_is_what_everybody_sees(self):
        for pid in ("frame_hot", "badge_ghost", "title_whale", "avatar_chicken", "accent_gold"):
            cosmetics.buy(self.u, pid)
            cosmetics.equip(self.u, pid)
        st = users.public(self.u)["st"]
        self.assertEqual(st["a"], {"icon": "chicken", "bg": "#C6F432"})
        self.assertEqual(st["f"]["color"], "#FF4B2B")
        self.assertEqual((st["b"], st["t"], st["c"]), ("ghost", "Whale", "#F2C230"))
        self.assertEqual(users.public(self.u)["st"], users.style_of(self.u["id"]))

    def test_what_you_no_longer_own_is_never_shown(self):
        cosmetics.buy(self.u, "frame_lime")
        cosmetics.equip(self.u, "frame_lime")
        del cosmetics.inventory(self.u)["frame_lime"]               # as if it had been refunded or removed
        self.assertEqual(cosmetics.profile_json(self.u)["slots"]["frame"], "frame_none")
        self.assertNotIn("f", users.public(self.u).get("st", {}))

    def test_cosmetics_never_touch_a_game_outcome_or_a_payout(self):
        plain = mk("plain", weekly=1000)
        dressed = mk("dressed", weekly=1000, accum=5000)
        for pid in ("frame_gold" if False else "frame_hot", "badge_crown", "avatar_crown", "title_whale", "accent_gold"):
            cosmetics.buy(dressed, pid)
            cosmetics.equip(dressed, pid)
        out = []
        for u in (plain, dressed):
            with mock.patch.object(games, "rand_below", lambda n: 7), mock.patch.object(games, "rand_unit", lambda: 0.123):
                a = games.roulette(u, {"bets": [{"type": "red", "amount": 10}]})
                b = games.dice(u, {"amount": 10, "direction": "over", "target": 50})
                c = games.limbo(u, {"amount": 10, "target": 2})
            out.append((a["number"], a["payout"], b["payout"], c["payout"], u["balance"] - 1000))
        self.assertEqual(out[0], out[1])

    def test_nothing_in_the_game_or_money_code_reads_cosmetics(self):
        for name in ("games", "markets", "weekly", "lmsr", "poker", "ledger"):
            with open(os.path.join(config.ROOT, "backend", name + ".py"), encoding="utf-8") as f:
                code = f.read()
            self.assertNotIn("cosmetics", code, name)
            self.assertNotIn("catalog", code, name)


class TheStoreOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def person(self, name):
        c = Client(self.port)
        c.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})
        return c

    def fund(self, name, amount):
        with server.LOCK:
            u = users.by_username(name)
            ledger.post(u, "accumulated", amount, "test.setup")

    def test_buy_equip_and_be_seen_by_somebody_else(self):
        a, b = self.person("shopper"), self.person("viewerx")
        self.fund("shopper", 500)
        st, s = a.call("GET", "/api/store")
        self.assertEqual((st, s["accumulated"], s["weekly"]), (200, 500.0, 1000.0))
        st, r = a.call("POST", "/api/store/buy", {"item": "frame_lime", "requestId": "buy-shopper-0001"})
        self.assertEqual((st, r["paid"], r["after"], r["user"]["accum"], r["user"]["weekly"]), (200, 150.0, 350.0, 350.0, 1000.0))
        self.assertTrue([i for i in r["store"]["items"] if i["id"] == "frame_lime"][0]["owned"])
        st, r2 = a.call("POST", "/api/store/buy", {"item": "frame_lime", "requestId": "buy-shopper-0001"})
        self.assertEqual((st, r2["duplicate"], r2["user"]["accum"]), (200, True, 350.0))
        self.assertEqual(a.call("POST", "/api/store/buy", {"item": "frame_lime"})[0], 409)
        self.assertEqual(a.call("POST", "/api/store/equip", {"item": "frame_double"})[0], 403)
        st, e = a.call("POST", "/api/store/equip", {"item": "frame_lime"})
        self.assertEqual((st, e["profile"]["slots"]["frame"]), (200, "frame_lime"))
        # somebody else sees it in a profile and in a circle list
        st, circ = a.call("POST", "/api/circles", {"name": "Looks", "visibility": "public"})
        cid = circ["circle"]["id"]
        b.call("POST", f"/api/circles/{cid}/join", {})
        st, d = b.call("GET", f"/api/circles/{cid}")
        mine = [m for m in d["members"] if m["user"]["username"] == "shopper"][0]
        self.assertEqual(mine["user"]["st"]["f"]["color"], "#C6F432")
        st, prof = b.call("GET", "/api/users/shopper")
        self.assertEqual(prof["user"]["profile"]["style"]["f"]["color"], "#C6F432")
        self.assertEqual(prof["user"]["profile"]["slots"]["frame"], "frame_lime")

    def test_the_weekly_account_can_not_buy_anything(self):
        c = self.person("broke_in_store")
        st, r = c.call("POST", "/api/store/buy", {"item": "frame_lime"})
        self.assertEqual(st, 402)
        self.assertIn("accumulated account", r["error"])
        st, me = c.call("GET", "/api/me")
        self.assertEqual((me["user"]["weekly"], me["user"]["accum"]), (1000.0, 0.0))

    def test_you_must_be_signed_in(self):
        anon = Client(self.port)
        for method, path in (("GET", "/api/store"), ("POST", "/api/store/buy"), ("POST", "/api/profile"), ("GET", "/api/profile")):
            self.assertEqual(anon.call(method, path, {})[0], 401, path)

    def test_the_circle_chat_and_friend_lists_carry_the_look_too(self):
        a, b = self.person("dressy"), self.person("pal")
        self.fund("dressy", 500)
        a.call("POST", "/api/store/buy", {"item": "avatar_chicken"})
        a.call("POST", "/api/store/equip", {"item": "avatar_chicken"})
        a.call("POST", "/api/friends/request", {"username": "pal"})
        b.call("POST", "/api/friends/accept", {"userId": users.by_username("dressy")["id"]})
        st, fr = b.call("GET", "/api/friends")
        row = [r for r in fr["friends"] if r["username"] == "dressy"][0]
        self.assertEqual(row["st"]["a"]["icon"], "chicken")
        st, ch = b.call("POST", "/api/chats/dm", {"userId": users.by_username("dressy")["id"]})
        st, chat = b.call("GET", f"/api/chats/{ch['chat']['id']}")
        people = {p["username"]: p for p in chat["chat"]["people"]}
        self.assertEqual(people["dressy"]["st"]["a"]["icon"], "chicken")
        self.assertNotIn("st", people["pal"])


if __name__ == "__main__":
    unittest.main()
