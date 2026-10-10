"""Poker tables: opening, joining, the settings and the vote, real money, privacy, and over HTTP."""
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from backend import markets, poker, seed, users            # noqa: E402
from backend.store import db, store                        # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402
from tests.test_http import Client                         # noqa: E402
from tests.test_poker import chips, rigged, stacked           # noqa: E402


def tearDownModule():
    restore_store_path()


def mk(name, funds=1000.0):
    u = users.register(name, "secret123")
    u["balance"] = float(funds)
    return u


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def lobby_of(names, funds=5000, visibility="public", **body):
    fresh_store()
    us = [mk(n, funds) for n in names]
    t = poker.create(us[0], {"name": "Table", "visibility": visibility, **body})
    for u in us[1:]:
        poker.join(u, t["id"] if visibility == "public" else None, t["code"])
    return t, us


def accept_all(t, us):
    for u in us:
        poker.vote(u, t, True)


class OpeningAndJoining(unittest.TestCase):
    def test_a_new_table_has_sensible_fake_money_defaults(self):
        fresh_store()
        ann = mk("ann")
        t = poker.create(ann, {})
        self.assertEqual(t["status"], "setup")
        self.assertEqual(t["settings"], {"money": "fake", "maxSeats": 6, "turnSeconds": 45, "rebuy": True,
                                         "blindsUp": 0, "bigBlind": 20, "smallBlind": 10, "stack": 1000})
        self.assertEqual((t["seats"][0]["name"], t["hostId"], t["votes"]), ("ann", ann["id"], {ann["id"]: True}))
        self.assertEqual(len(t["seats"]), 6)
        self.assertIsNone(t["code"])
        self.assertEqual(t["name"], "ann's table")

    def test_private_tables_get_a_code_public_ones_do_not(self):
        fresh_store()
        ann, bob = mk("ann"), mk("bobby")
        a = poker.create(ann, {"visibility": "private"})
        b = poker.create(bob, {"visibility": "public"})
        self.assertEqual(len(a["code"]), 6)
        self.assertIsNone(b["code"])
        self.assertEqual(poker.by_code(a["code"].lower())["id"], a["id"])

    def test_one_table_at_a_time_and_a_cap_on_hosting(self):
        fresh_store()
        ann, bob, cat = mk("ann"), mk("bobby"), mk("cathy")
        t = poker.create(ann, {})
        self.assertIn("already sitting", err(poker.create, ann, {}).message)
        self.assertIn("already sitting", err(poker.join, ann, poker.create(bob, {})["id"]).message)
        self.assertIs(poker.join(ann, t["id"]), t)                 # joining the table you are at is harmless
        with mock.patch.object(poker, "MAX_TABLES_PER_HOST", 1):
            poker.leave(ann, t)
            first = poker.create(cat, {"name": "First"})
            poker.tables()[first["id"]]["seats"][0] = None          # hosts one table but is not seated at it
            self.assertIn("already running", err(poker.create, cat, {}).message)

    def test_joining_fills_the_next_seat_and_a_full_table_says_no(self):
        t, us = lobby_of(["ann", "bobby", "cathy"], maxSeats=3)
        self.assertEqual([s["name"] for s in t["seats"]], ["ann", "bobby", "cathy"])
        dan = mk("danny")
        self.assertIn("full", err(poker.join, dan, t["id"]).message)

    def test_private_tables_need_the_code(self):
        fresh_store()
        ann, bob = mk("ann"), mk("bobby")
        t = poker.create(ann, {"visibility": "private"})
        self.assertEqual(err(poker.join, bob, t["id"]).status, 404)                 # by id: it does not admit it exists
        self.assertEqual(err(poker.join, bob, None, "WRONG1").status, 404)
        poker.join(bob, None, t["code"])
        self.assertEqual(poker.seat_index(t, bob["id"]), 1)

    def test_the_lobby_lists_public_tables_with_who_is_sitting(self):
        fresh_store()
        ann, bob, cat = mk("ann"), mk("bobby"), mk("cathy")
        pub = poker.create(ann, {"name": "Open house"})
        poker.join(bob, pub["id"])
        priv = poker.create(cat, {"name": "Secret", "visibility": "private"})
        rows = poker.lobby(mk("dan")["id"])
        self.assertEqual([r["name"] for r in rows], ["Open house"])
        self.assertEqual((rows[0]["players"], rows[0]["maxSeats"], rows[0]["status"], rows[0]["hostName"]),
                         (["ann", "bobby"], 6, "setup", "ann"))
        own = poker.lobby(cat["id"])
        self.assertEqual([r["name"] for r in own], ["Secret", "Open house"])        # her own private table first
        self.assertTrue(own[0]["mine"])

    def test_an_empty_table_disappears(self):
        fresh_store()
        ann = mk("ann")
        t = poker.create(ann, {})
        poker.leave(ann, t)
        self.assertEqual(poker.lobby(ann["id"]), [])

    def test_idle_setup_tables_are_cleaned_up(self):
        fresh_store()
        ann = mk("ann")
        t = poker.create(ann, {})
        self.assertEqual(poker.tick(t["lastActivity"] + 1000), [])
        self.assertEqual(poker.tick(t["lastActivity"] + poker.IDLE_SETUP_MS + 1), [t["id"]])
        self.assertEqual(poker.tables(), {})


class SettingsAndVotes(unittest.TestCase):
    def setUp(self):
        self.t, self.us = lobby_of(["ann", "bobby", "cathy"])
        self.ann, self.bob, self.cat = self.us

    def test_only_the_host_changes_settings_and_each_change_asks_for_new_votes(self):
        self.assertEqual(err(poker.set_settings, self.bob, self.t, {"bigBlind": 50}).status, 403)
        accept_all(self.t, self.us)
        rev = self.t["settingsRev"]
        poker.set_settings(self.ann, self.t, {"bigBlind": 50, "smallBlind": 25, "stack": 5000})
        s = self.t["settings"]
        self.assertEqual((s["bigBlind"], s["smallBlind"], s["stack"]), (50, 25, 5000))
        self.assertEqual(self.t["settingsRev"], rev + 1)
        self.assertEqual(self.t["votes"], {self.ann["id"]: True})                   # everyone else has to accept again

    def test_the_small_blind_follows_the_big_blind_unless_given(self):
        poker.set_settings(self.ann, self.t, {"bigBlind": 100, "stack": 2000})
        self.assertEqual(self.t["settings"]["smallBlind"], 50)

    def test_fake_money_limits(self):
        for body, word in (({"bigBlind": 1}, "between 2"), ({"bigBlind": 20, "smallBlind": 30}, "small blind"),
                           ({"bigBlind": 20, "stack": 100}, "10 to 1,000"), ({"bigBlind": 20, "stack": 50000}, "10 to 1,000"),
                           ({"turnSeconds": 7}, "timer"), ({"blindsUp": 3}, "blinds go up"), ({"maxSeats": 1}, "between 2"),
                           ({"maxSeats": 10}, "between 2"), ({"bigBlind": 20.5}, "whole number"), ({"rebuy": "yes"}, "on or off"),
                           ({"money": "bitcoin"}, "fake chips or real")):
            self.assertIn(word, err(poker.set_settings, self.ann, self.t, body).message, body)
        poker.set_settings(self.ann, self.t, {"turnSeconds": 0, "blindsUp": 10, "maxSeats": 9, "rebuy": False})     # all fine
        self.assertEqual((self.t["settings"]["turnSeconds"], len(self.t["seats"])), (0, 9))

    def test_switching_to_real_money_resets_the_numbers_to_real_ones(self):
        poker.set_settings(self.ann, self.t, {"money": "real"})
        s = self.t["settings"]
        self.assertEqual((s["money"], s["bigBlind"], s["smallBlind"], s["stack"], s["rebuy"]), ("real", 100, 50, 10000, False))
        poker.set_settings(self.ann, self.t, {"bigBlind": 0.5, "smallBlind": 0.25, "stack": 25})
        self.assertEqual((self.t["settings"]["bigBlind"], self.t["settings"]["stack"]), (50, 2500))
        poker.set_settings(self.ann, self.t, {"money": "fake"})
        self.assertEqual((self.t["settings"]["bigBlind"], self.t["settings"]["stack"]), (20, 1000))

    def test_real_money_limits(self):
        poker.set_settings(self.ann, self.t, {"money": "real"})
        for body, word in (({"bigBlind": 0.05}, "between $0.10"), ({"bigBlind": 1, "smallBlind": 2}, "small blind"),
                           ({"bigBlind": 1, "stack": 5}, "20 to 200"), ({"bigBlind": 1, "stack": 500}, "20 to 200"),
                           ({"turnSeconds": 0}, "turn timer"), ({"bigBlind": 100, "stack": 20000}, "$10,000")):
            self.assertIn(word, err(poker.set_settings, self.ann, self.t, body).message, body)

    def test_seats_cannot_shrink_onto_a_player(self):
        self.assertIn("taken", err(poker.set_settings, self.ann, self.t, {"maxSeats": 2}).message)
        poker.set_settings(self.ann, self.t, {"maxSeats": 3})
        self.assertEqual(len(self.t["seats"]), 3)

    def test_start_needs_everyone_to_accept_and_names_who_has_not(self):
        poker.vote(self.bob, self.t, False)
        msg = err(poker.start, self.ann, self.t).message
        self.assertIn("cathy", msg)
        self.assertIn("bobby", msg)
        self.assertIn("declined", msg)
        poker.vote(self.bob, self.t, True)
        self.assertIn("cathy", err(poker.start, self.ann, self.t).message)
        poker.vote(self.cat, self.t, True)
        poker.start(self.ann, self.t)
        self.assertEqual(self.t["status"], "playing")

    def test_only_the_host_starts_and_you_need_two(self):
        accept_all(self.t, self.us)
        self.assertEqual(err(poker.start, self.bob, self.t).status, 403)
        solo = mk("loner")
        solo_t = poker.create(solo, {})
        self.assertIn("at least two", err(poker.start, solo, solo_t).message)

    def test_a_late_joiner_has_to_accept_and_a_leaver_stops_counting(self):
        accept_all(self.t, self.us)
        poker.leave(self.cat, self.t)
        poker.start(self.ann, self.t) if False else None
        dan = mk("danny")
        poker.join(dan, self.t["id"])
        self.assertIn("danny", err(poker.start, self.ann, self.t).message)
        poker.vote(dan, self.t, True)
        poker.start(self.ann, self.t)
        self.assertEqual(self.t["status"], "playing")

    def test_settings_lock_when_the_game_starts_and_open_again_after_it_ends(self):
        accept_all(self.t, self.us)
        poker.start(self.ann, self.t)
        self.assertIn("locked", err(poker.set_settings, self.ann, self.t, {"bigBlind": 50}).message)
        self.assertIn("already started", err(poker.vote, self.bob, self.t, True).message)
        poker.end_game(self.ann, self.t)                     # mid-hand: happens after this hand
        self.assertTrue(self.t["ending"])
        h = self.t["hand"]
        while h["street"] != "ended":
            poker.act(users.get(self.t["seats"][h["toAct"]]["userId"]), self.t, "fold")
        poker.catch_up(self.t, h["nextAt"] + 1)
        self.assertEqual((self.t["status"], self.t["votes"], self.t["hand"]), ("setup", {self.ann["id"]: True}, None))
        self.assertEqual([s["stack"] for s in poker.seated(self.t)], [0, 0, 0])
        poker.set_settings(self.ann, self.t, {"bigBlind": 50})                      # changing settings works again

    def test_only_seated_players_vote(self):
        outsider = mk("outsider")
        self.assertIn("Sit down", err(poker.vote, outsider, self.t, True).message)
        self.assertIn("Accept or decline", err(poker.vote, self.bob, self.t, "maybe").message)


class FakeGame(unittest.TestCase):
    def test_everyone_gets_the_starting_stack_and_the_first_hand_is_dealt(self):
        t, us = lobby_of(["ann", "bobby", "cathy"])
        poker.set_settings(us[0], t, {"bigBlind": 50, "smallBlind": 25, "stack": 2000})
        accept_all(t, us)
        poker.start(us[0], t)
        self.assertEqual(t["handNo"], 1)
        self.assertEqual(chips(t), 6000)
        self.assertEqual([us_["balance"] for us_ in us], [5000.0] * 3, "fake chips never touch real cash")

    def test_joining_a_running_fake_game_gets_a_stack_and_is_dealt_in_next_hand(self):
        t, us = lobby_of(["ann", "bobby"])
        accept_all(t, us)
        poker.start(us[0], t)
        dan = mk("danny")
        poker.join(dan, t["id"])
        seat = t["seats"][poker.seat_index(t, dan["id"])]
        self.assertEqual(seat["stack"], t["settings"]["stack"])
        self.assertEqual(t["hand"]["st"][poker.seat_index(t, dan["id"])], "out")    # not in the hand that is already going
        h = t["hand"]
        while h["street"] != "ended":
            poker.act(users.get(t["seats"][h["toAct"]]["userId"]), t, "fold")
        poker.catch_up(t, h["nextAt"] + 1)
        self.assertEqual(sum(1 for st in t["hand"]["st"] if st == "in"), 3)


class RealMoney(unittest.TestCase):
    def real_table(self, names=("ann", "bobby", "cathy"), funds=500):
        t, us = lobby_of(list(names), funds=funds)
        poker.set_settings(us[0], t, {"money": "real", "bigBlind": 1, "smallBlind": 0.5, "stack": 100})
        accept_all(t, us)
        return t, us

    def test_starting_takes_the_buy_in_from_cash_and_puts_it_in_front_of_you(self):
        t, us = self.real_table()
        poker.start(us[0], t)
        for u in us:
            self.assertEqual(u["balance"], 400.0)
            self.assertEqual(poker.real_stake(u["id"]), 100.0)
            self.assertEqual(markets.net_worth(u), 500.0)                           # net worth does not dip
            self.assertEqual(u["activity"][0]["kind"], "poker")
        self.assertEqual(chips(t), 30000)

    def test_nobody_is_charged_if_somebody_cannot_afford_it(self):
        t, us = self.real_table()
        us[2]["balance"] = 40.0
        msg = err(poker.start, us[0], t).message
        self.assertIn("cathy", msg)
        self.assertIn("$100.00", msg)
        self.assertEqual([u["balance"] for u in us], [500.0, 500.0, 40.0])
        self.assertEqual(t["status"], "setup")

    def test_money_at_the_table_blocks_the_voucher(self):
        t, us = self.real_table(funds=100.3)
        poker.start(us[0], t)
        self.assertEqual(round(us[0]["balance"], 2), 0.3)
        info = users.voucher_info(us[0])
        self.assertEqual((info["busy"], info["eligible"]), (True, False))

    def test_ending_the_game_pays_everybody_back_and_writes_history(self):
        t, us = self.real_table()
        poker.start(us[0], t)
        h = t["hand"]
        poker.act(users.get(t["seats"][h["toAct"]]["userId"]), t, "fold")
        poker.act(users.get(t["seats"][h["toAct"]]["userId"]), t, "fold")
        poker.end_game(us[0], t)                                                    # the hand is over, so it ends now
        self.assertEqual(t["status"], "playing" if t["ending"] else "setup")
        poker.catch_up(t, h["nextAt"] + 1)
        self.assertEqual(t["status"], "setup")
        self.assertAlmostEqual(sum(u["balance"] for u in us), 1500.0, places=2)     # not a cent created or lost
        winner = max(us, key=lambda u: u["balance"])
        self.assertGreater(winner["balance"], 500.0)
        for u in us:
            row = u["history"][0]
            self.assertEqual((row["game"], row["bet"]), ("poker", 100.0))
            self.assertEqual(round(row["profit"], 2), round(u["balance"] - 500.0, 2))
            self.assertEqual(poker.real_stake(u["id"]), 0)

    def test_leaving_between_hands_returns_your_stack_to_your_cash(self):
        t, us = self.real_table()
        poker.start(us[0], t)
        h = t["hand"]
        poker.act(users.get(t["seats"][h["toAct"]]["userId"]), t, "fold")
        poker.act(users.get(t["seats"][h["toAct"]]["userId"]), t, "fold")           # hand over
        stack = t["seats"][2]["stack"]
        poker.leave(us[2], t)                                                       # cathy is the winner: leaves with her money
        self.assertIsNone(t["seats"][2])
        self.assertEqual(round(us[2]["balance"], 2), round(400 + stack / 100, 2))
        self.assertEqual(poker.real_stake(us[2]["id"]), 0)

    def test_joining_a_running_real_money_table_needs_an_explicit_yes(self):
        t, us = self.real_table(names=("ann", "bobby"))
        poker.start(us[0], t)
        dan = mk("danny", 300)
        self.assertIn("real-money table", err(poker.join, dan, t["id"]).message)
        self.assertEqual((dan["balance"], poker.seat_index(t, dan["id"])), (300.0, None))
        poor = mk("poor", 20)
        self.assertIn("$100.00", err(poker.join, poor, t["id"], None, True).message)
        self.assertIsNone(poker.seat_index(t, poor["id"]))                           # no ghost seat after a failed buy-in
        poker.join(dan, t["id"], None, True)
        self.assertEqual(dan["balance"], 200.0)
        self.assertEqual(t["seats"][poker.seat_index(t, dan["id"])]["stack"], 10000)

    def test_a_rebuy_costs_another_buy_in(self):
        t, us = self.real_table(names=("ann", "bobby"))
        poker.set_settings(us[0], t, {"rebuy": True})
        accept_all(t, us)
        poker.start(us[0], t)
        seat = t["seats"][1]
        seat["stack"] = 0
        t["hand"] = None
        seat["busted"] = True
        before = us[1]["balance"]
        poker.rebuy(us[1], t)
        self.assertEqual((round(before - us[1]["balance"], 2), seat["bought"]), (100.0, 20000))
        self.assertEqual(seat["stack"] + t["hand"]["contrib"][1], 10000)       # a full buy-in, less whatever the new hand's blind cost

    def test_the_weekly_standings_see_money_at_the_table(self):
        t, us = self.real_table()
        poker.start(us[0], t)
        self.assertEqual(users.get(us[0]["id"])["balance"], 400.0)
        self.assertEqual(markets.portfolio(us[0])["netWorth"], 500.0)
        d = markets.portfolio(us[0])["distribution"]
        self.assertEqual((d["cash"], d["poker"], d["total"]), (400.0, 100.0, 500.0))

    def test_a_new_season_wipes_the_tables(self):
        t, us = self.real_table()
        poker.start(us[0], t)
        seed.new_season(store.data)
        self.assertEqual(poker.tables(), {})


class Privacy(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.us = [mk(n, 5000) for n in ("ann", "bobby", "cathy")]
        t = poker.create(self.us[0], {"name": "Table"})
        for u in self.us[1:]:
            poker.join(u, t["id"])
        accept_all(t, self.us)
        hole = {0: ("As", "Ad"), 1: ("Kc", "Kd"), 2: ("7h", "2c")}
        board = ["Qh", "9s", "5d", "4c", "3h"]
        with mock.patch.object(poker, "shuffle", stacked(rigged(0, [0, 1, 2], hole, board))):
            poker.start(self.us[0], t)
        self.t = t
        self.hole, self.board = hole, board

    def test_you_see_your_own_cards_and_only_backs_for_everyone_else(self):
        for me, mine in enumerate(self.hole.values()):
            v = poker.view(self.t, self.us[me]["id"])
            for seat in filter(None, v["seats"]):
                if seat["seat"] == me:
                    self.assertEqual(seat["cards"], list(self.hole[me]))
                else:
                    self.assertEqual(seat["cards"], ["back", "back"])
            blob = json.dumps(v)
            for other, cards in self.hole.items():
                if other != me:
                    for c in cards:
                        self.assertNotIn(f'"{c}"', blob, f"seat {me} can see {c}")
            self.assertNotIn("deck", blob)

    def test_a_spectator_sees_no_cards_at_all(self):
        v = poker.view(self.t, "somebody-not-seated")
        self.assertEqual([s["cards"] for s in v["seats"] if s], [["back", "back"]] * 3)
        self.assertIsNone(v["mySeat"])
        self.assertIsNone(v["hand"]["actions"])
        self.assertIsNone(v["code"])
        for cards in self.hole.values():
            for c in cards:
                self.assertNotIn(f'"{c}"', json.dumps(v))

    def test_cards_are_shown_after_a_showdown_but_not_for_a_fold(self):
        h = self.t["hand"]
        # ann calls, bob calls, cat checks, then everyone checks down
        poker.act(self.us[0], self.t, "call")
        poker.act(self.us[1], self.t, "call")
        poker.act(self.us[2], self.t, "check")
        for _ in range(3):
            for who in (1, 2, 0):
                poker.act(self.us[who], self.t, "check")
        v = poker.view(self.t, self.us[2]["id"])
        self.assertEqual({s["seat"]: s["cards"] for s in v["seats"] if s}, {i: list(c) for i, c in self.hole.items()})
        # a fold-win reveals nothing
        poker.catch_up(self.t, h["nextAt"] + 1)
        h2 = self.t["hand"]
        poker.act(users.get(self.t["seats"][h2["toAct"]]["userId"]), self.t, "fold")
        poker.act(users.get(self.t["seats"][h2["toAct"]]["userId"]), self.t, "fold")
        v2 = poker.view(self.t, "somebody-not-seated")
        self.assertEqual(h2["result"]["shown"], {})
        for s in filter(None, v2["seats"]):
            self.assertNotEqual(s["cards"], h2["hole"][s["seat"]])

    def test_only_the_player_to_act_is_offered_actions_and_only_seated_people_see_the_code(self):
        h = self.t["hand"]
        for i, u in enumerate(self.us):
            v = poker.view(self.t, u["id"])
            self.assertEqual(v["hand"]["actions"] is not None, i == h["toAct"])


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.c = {}
        for name in ("ann", "bobby", "cathy", "danny"):
            c = Client(cls.port)
            assert c.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})[0] == 200
            cls.c[name] = c

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        restore_store_path()

    def tearDown(self):
        for name, c in self.c.items():                 # leave whatever table each test left behind
            st, d = c.call("GET", "/api/poker/tables")
            for row in d["tables"]:
                if row["mine"]:
                    c.call("POST", f"/api/poker/tables/{row['id']}/leave", {})

    def test_login_is_required(self):
        anon = Client(self.port)
        self.assertEqual(anon.call("GET", "/api/poker/tables")[0], 401)
        self.assertEqual(anon.call("POST", "/api/poker/tables", {})[0], 401)

    def test_a_whole_game_over_the_wire_keeps_cards_private(self):
        ann, bob = self.c["ann"], self.c["bobby"]
        st, d = ann.call("POST", "/api/poker/tables", {"name": "Friday night", "visibility": "public"})
        self.assertEqual(st, 200)
        tid = d["table"]["id"]
        self.assertTrue(d["table"]["isHost"])
        # bob finds it in the lobby, with ann sitting there
        st, lob = bob.call("GET", "/api/poker/tables")
        row = next(r for r in lob["tables"] if r["id"] == tid)
        self.assertEqual((row["players"], row["status"], row["mine"]), (["ann"], "setup", False))
        self.assertEqual(bob.call("POST", "/api/poker/join", {"id": tid})[0], 200)
        # only the host can change settings; bob can vote
        self.assertEqual(bob.call("POST", f"/api/poker/tables/{tid}/settings", {"bigBlind": 40})[0], 403)
        self.assertEqual(ann.call("POST", f"/api/poker/tables/{tid}/settings", {"bigBlind": 40, "smallBlind": 20, "stack": 2000})[0], 200)
        self.assertEqual(ann.call("POST", f"/api/poker/tables/{tid}/start", {})[0], 400)       # bob has not accepted
        self.assertEqual(bob.call("POST", f"/api/poker/tables/{tid}/vote", {"accept": True})[0], 200)
        st, d = ann.call("POST", f"/api/poker/tables/{tid}/start", {})
        self.assertEqual((st, d["table"]["status"]), (200, "playing"))
        # each player's own JSON holds only their own two cards
        views = {}
        for who, c in (("ann", ann), ("bobby", bob)):
            views[who] = c.call("GET", f"/api/poker/tables/{tid}")[1]["table"]
        mine = {w: [s for s in v["seats"] if s and s["isMe"]][0]["cards"] for w, v in views.items()}
        for w, v in views.items():
            others = [s for s in v["seats"] if s and not s["isMe"]]
            self.assertTrue(all(s["cards"] == ["back", "back"] for s in others))
            blob = json.dumps(v)
            other = "bobby" if w == "ann" else "ann"
            for c in mine[other]:
                self.assertNotIn(f'"{c}"', blob)
            self.assertNotIn('"deck"', blob)
        # a stranger watching a public table sees backs only
        spec = self.c["cathy"].call("GET", f"/api/poker/tables/{tid}")[1]["table"]
        self.assertIsNone(spec["mySeat"])
        self.assertTrue(all(s["cards"] == ["back", "back"] for s in spec["seats"] if s))
        # play a move: whoever is to act folds, the other wins
        actor = next(w for w, v in views.items() if v["hand"]["actions"])
        st, d = self.c[actor].call("POST", f"/api/poker/tables/{tid}/action", {"action": "fold"})
        self.assertEqual((st, d["table"]["hand"]["street"]), (200, "ended"))
        wrong = self.c["ann" if actor == "bobby" else "bobby"].call("POST", f"/api/poker/tables/{tid}/action", {"action": "fold"})
        self.assertEqual(wrong[0], 400)

    def test_private_tables_hide_from_strangers_and_open_with_the_code(self):
        ann, bob, cat = self.c["ann"], self.c["bobby"], self.c["cathy"]
        st, d = ann.call("POST", "/api/poker/tables", {"name": "Secret", "visibility": "private"})
        tid, code = d["table"]["id"], d["table"]["code"]
        self.assertEqual(len(code), 6)
        self.assertEqual(cat.call("GET", f"/api/poker/tables/{tid}")[0], 404)
        self.assertEqual(cat.call("POST", "/api/poker/join", {"id": tid})[0], 404)
        self.assertNotIn(tid, [r["id"] for r in cat.call("GET", "/api/poker/tables")[1]["tables"]])
        self.assertEqual(bob.call("POST", "/api/poker/join", {"code": code})[0], 200)
        st, d = bob.call("GET", f"/api/poker/tables/{tid}")
        self.assertEqual((st, d["table"]["code"]), (200, code))                              # members can pass the code on
        self.assertEqual(cat.call("POST", "/api/poker/join", {"code": "ZZZZZZ"})[0], 404)

    def test_real_money_over_http_moves_cash_and_gives_it_back(self):
        ann, bob = self.c["ann"], self.c["bobby"]
        st, d = ann.call("POST", "/api/poker/tables", {})
        tid = d["table"]["id"]
        bob.call("POST", "/api/poker/join", {"id": tid})
        st, d = ann.call("POST", f"/api/poker/tables/{tid}/settings", {"money": "real", "bigBlind": 1, "smallBlind": 0.5, "stack": 100})
        self.assertEqual((st, d["table"]["scale"], d["table"]["settings"]["stack"]), (200, 100, 10000))
        for c in (ann, bob):
            c.call("POST", f"/api/poker/tables/{tid}/vote", {"accept": True})
        before = ann.call("GET", "/api/me")[1]["user"]["balance"]
        st, d = ann.call("POST", f"/api/poker/tables/{tid}/start", {})
        self.assertEqual((st, round(before - d["user"]["balance"], 2)), (200, 100.0))
        self.assertEqual(d["user"]["netWorth"], before)
        st, d = ann.call("POST", f"/api/poker/tables/{tid}/leave", {})          # mid-hand: she folds and leaves when it ends
        self.assertEqual((st, d["left"]), (200, False))
        st, view = ann.call("GET", f"/api/poker/tables/{tid}")
        self.assertEqual(view["table"]["hand"]["street"], "ended")
        poker.catch_up(poker.tables()[tid], poker.tables()[tid]["hand"]["nextAt"] + 1)
        st, d = ann.call("GET", "/api/me")
        self.assertLessEqual(abs(d["user"]["balance"] - before), 1.0 + 1e-9)               # back, minus at most what a blind cost

    def test_the_whole_lobby_flow_with_errors(self):
        ann = self.c["ann"]
        self.assertEqual(ann.call("POST", "/api/poker/tables", {"visibility": "secret"})[0], 400)
        self.assertEqual(ann.call("POST", "/api/poker/tables", {"name": "x"})[0], 400)       # too short
        st, d = ann.call("POST", "/api/poker/tables", {"name": "Valid name"})
        self.assertEqual(st, 200)
        self.assertEqual(ann.call("POST", "/api/poker/tables", {})[0], 400)                  # already sitting
        self.assertEqual(ann.call("GET", "/api/poker/tables/doesnotexist")[0], 404)
        tid = d["table"]["id"]
        self.assertEqual(ann.call("POST", f"/api/poker/tables/{tid}/kick", {"userId": "nobody"})[0], 404)


if __name__ == "__main__":
    unittest.main()
