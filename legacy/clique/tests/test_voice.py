"""Voice rooms on the server: who may join, who may be signalled, one room and one tab at a time, cleanup, and the TURN credentials."""
import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                          # noqa: E402
from backend import circles, economy, users, voice                     # noqa: E402
from backend.util import ApiError                                      # noqa: E402
from tests.econ import circle_of, mk                                   # noqa: E402
from tests.helpers import fresh_store, restore_store_path              # noqa: E402
from tests.test_http import Client                                     # noqa: E402
from tests.test_social_http import Listener                            # noqa: E402

SID = lambda n: f"session-{n:04d}"                                     # noqa: E731


def tearDownModule():
    restore_store_path()
    voice.clear()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


class Base(unittest.TestCase):
    def setUp(self):
        fresh_store()
        voice.clear()
        self.a, self.b, self.c, self.out = mk("alice"), mk("bobby"), mk("cindy"), mk("outsider")
        self.crew = circle_of(self.a, self.b, self.c, name="Crew")
        self.other = circle_of(self.a, self.out, name="Other")


class WhoMayEnter(Base):
    def test_only_members_can_join_a_circles_room(self):
        e = err(voice.join, self.out, self.crew["id"], SID(1))
        self.assertEqual(e.status, 403)
        self.assertEqual(voice.people(self.crew["id"]), [])
        voice.join(self.a, self.crew["id"], SID(2))
        self.assertEqual([p["username"] for p in voice.people(self.crew["id"])], ["alice"])

    def test_a_room_that_does_not_exist_is_a_404_and_junk_is_refused(self):
        self.assertEqual(err(voice.join, self.a, "nosuchcircle", SID(1)).status, 404)
        self.assertEqual(err(voice.join, self.a, self.crew["id"], "x").status, 400)
        self.assertEqual(err(voice.join, self.a, self.crew["id"], None).status, 400)
        self.assertEqual(err(voice.join, self.a, self.crew["id"], "has spaces in it").status, 400)

    def test_you_only_see_the_rooms_of_your_own_circles(self):
        voice.join(self.a, self.crew["id"], SID(1))
        voice.join(self.out, self.other["id"], SID(2))
        mine = {r["name"]: [p["username"] for p in r["people"]] for r in voice.rooms_for(self.b)}
        self.assertEqual(mine, {"Crew": ["alice"]})
        theirs = {r["name"]: [p["username"] for p in r["people"]] for r in voice.rooms_for(self.out)}
        self.assertEqual(theirs, {"Other": ["outsider"]})

    def test_a_private_circles_room_is_invisible_to_strangers_even_if_the_circle_is_listed(self):
        self.crew["visibility"] = "public"
        voice.join(self.a, self.crew["id"], SID(1))
        self.assertEqual(voice.rooms_for(self.out), [{"circleId": self.other["id"], "name": "Other", "people": [], "full": False}])

    def test_somebody_removed_from_a_circle_is_out_of_its_room(self):
        voice.join(self.b, self.crew["id"], SID(1))
        circles.kick(self.a, self.crew["id"], self.b["id"])
        self.assertEqual(err(voice.state, self.b, self.crew["id"], SID(1)).status, 403)
        self.assertEqual(err(voice.signal, self.b, self.crew["id"], SID(1), self.a["id"], None, {"type": "ready"}).status, 403)


class OneRoomOneTab(Base):
    def test_joining_another_room_leaves_the_first(self):
        voice.join(self.a, self.crew["id"], SID(1))
        out = voice.join(self.a, self.other["id"], SID(1))
        self.assertEqual(out["changed"], {self.crew["id"], self.other["id"]})
        self.assertEqual(voice.people(self.crew["id"]), [])
        self.assertEqual(voice.room_of(self.a["id"]), self.other["id"])

    def test_a_second_tab_takes_the_call_over_and_the_first_is_told(self):
        voice.join(self.a, self.crew["id"], SID(1))
        out = voice.join(self.a, self.crew["id"], SID(2))
        self.assertEqual(out["replacedSid"], SID(1))
        self.assertEqual(len(voice.people(self.crew["id"])), 1, "still one person, one connection")
        self.assertFalse(voice.leave(self.a, self.crew["id"], SID(1)), "the old tab's goodbye must not hang up the new one")
        self.assertEqual(voice.state(self.a, self.crew["id"], SID(1))["inRoom"], False)
        self.assertEqual(voice.state(self.a, self.crew["id"], SID(2))["inRoom"], True)

    def test_rejoining_with_the_same_tab_is_harmless(self):
        first = voice.join(self.a, self.crew["id"], SID(1))
        again = voice.join(self.a, self.crew["id"], SID(1))
        self.assertIsNone(again["replacedSid"])
        self.assertEqual(len(voice.people(self.crew["id"])), 1)
        self.assertEqual(first["peers"], again["peers"])

    def test_the_joiner_is_told_who_is_already_there_so_they_can_call_them(self):
        voice.join(self.a, self.crew["id"], SID(1))
        out = voice.join(self.b, self.crew["id"], SID(2))
        self.assertEqual(out["peers"], [{"id": self.a["id"], "sid": SID(1), "username": "alice"}])
        self.assertEqual(voice.join(self.a, self.crew["id"], SID(1))["peers"][0]["id"], self.b["id"])

    def test_a_room_holds_a_small_group(self):
        with mock.patch.object(economy, "VOICE_MAX_PEOPLE", 2):
            voice.join(self.a, self.crew["id"], SID(1))
            voice.join(self.b, self.crew["id"], SID(2))
            e = err(voice.join, self.c, self.crew["id"], SID(3))
            self.assertEqual(e.status, 409)
            self.assertIn("full", e.message)
            voice.join(self.a, self.crew["id"], SID(1))                          # somebody already in can always come back
            self.assertTrue(voice.rooms_for(self.c)[0]["full"])
        self.assertTrue(voice.leave(self.a, self.crew["id"], SID(1)))
        self.assertTrue(voice.join(self.c, self.crew["id"], SID(3))["peers"])


class CheckInsAndCleanup(Base):
    def test_mute_and_deafen_show_up_for_everybody_in_the_room(self):
        voice.join(self.a, self.crew["id"], SID(1))
        voice.join(self.b, self.crew["id"], SID(2))
        out = voice.state(self.a, self.crew["id"], SID(1), muted=True)
        self.assertTrue(out["changed"])
        self.assertFalse(voice.state(self.a, self.crew["id"], SID(1), muted=True)["changed"], "no change, no announcement")
        flags = {p["username"]: (p["muted"], p["deaf"]) for p in voice.people(self.crew["id"])}
        self.assertEqual(flags, {"alice": (True, False), "bobby": (False, False)})
        voice.state(self.a, self.crew["id"], SID(1), deaf=True)
        self.assertEqual({p["username"]: (p["muted"], p["deaf"]) for p in voice.people(self.crew["id"])}["alice"], (True, True))

    def test_people_who_go_quiet_are_removed_and_those_who_check_in_stay(self):
        voice.join(self.a, self.crew["id"], SID(1))
        voice.join(self.b, self.crew["id"], SID(2))
        future = time.time() + economy.VOICE_STALE_S - 5
        voice.ROOMS[self.crew["id"]][self.a["id"]]["seen"] = time.time() - economy.VOICE_STALE_S - 1
        self.assertEqual(voice.sweep(), {self.crew["id"]})
        self.assertEqual([p["username"] for p in voice.people(self.crew["id"])], ["bobby"])
        self.assertEqual(voice.sweep(), set())
        voice.state(self.b, self.crew["id"], SID(2))
        self.assertEqual(voice.sweep(future), set())
        self.assertEqual(voice.sweep(time.time() + 3600), {self.crew["id"]})
        self.assertNotIn(self.crew["id"], voice.ROOMS, "an empty room disappears")

    def test_leaving_is_checked_and_idempotent(self):
        voice.join(self.a, self.crew["id"], SID(1))
        self.assertTrue(voice.leave(self.a, self.crew["id"], SID(1)))
        self.assertFalse(voice.leave(self.a, self.crew["id"], SID(1)))
        self.assertEqual(err(voice.leave, self.out, self.crew["id"], SID(9)).status, 403)


class Signaling(Base):
    def setUp(self):
        super().setUp()
        voice.join(self.a, self.crew["id"], SID(1))
        voice.join(self.b, self.crew["id"], SID(2))
        self.offer = {"type": "offer", "sdp": "v=0..."}

    def test_a_message_goes_to_the_one_person_it_is_for(self):
        ev, to = voice.signal(self.a, self.crew["id"], SID(1), self.b["id"], SID(2), self.offer)
        self.assertEqual(to, self.b["id"])
        self.assertEqual((ev["type"], ev["k"], ev["from"], ev["fromSid"], ev["toSid"], ev["room"], ev["data"]),
                         ("voice", "signal", self.a["id"], SID(1), SID(2), self.crew["id"], self.offer))

    def test_only_people_in_the_same_room_can_message_each_other(self):
        voice.join(self.c, self.crew["id"], SID(3))
        voice.leave(self.c, self.crew["id"], SID(3))
        self.assertEqual(err(voice.signal, self.a, self.crew["id"], SID(1), self.c["id"], None, self.offer).status, 409)
        voice.join(self.out, self.other["id"], SID(4))
        voice.join(self.a, self.crew["id"], SID(1))
        self.assertEqual(err(voice.signal, self.a, self.crew["id"], SID(1), self.out["id"], None, self.offer).status, 409,
                         "somebody in another room can not be called from this one")
        self.assertEqual(err(voice.signal, self.out, self.crew["id"], SID(4), self.a["id"], None, self.offer).status, 403)

    def test_a_message_for_somebodys_old_tab_is_refused(self):
        voice.join(self.b, self.crew["id"], SID(22))
        e = err(voice.signal, self.a, self.crew["id"], SID(1), self.b["id"], SID(2), self.offer)
        self.assertEqual(e.status, 409)
        ev, _ = voice.signal(self.a, self.crew["id"], SID(1), self.b["id"], SID(22), self.offer)
        self.assertEqual(ev["toSid"], SID(22))

    def test_you_can_not_send_as_somebody_elses_tab(self):
        self.assertEqual(err(voice.signal, self.a, self.crew["id"], SID(9), self.b["id"], None, self.offer).status, 409)

    def test_only_setup_messages_of_a_sensible_size_are_passed_on(self):
        for bad_data in (None, "offer", [], {}, {"type": "evil"}, {"type": 5}):
            self.assertEqual(err(voice.signal, self.a, self.crew["id"], SID(1), self.b["id"], None, bad_data).status, 400)
        big = {"type": "offer", "sdp": "x" * (voice.MAX_SIGNAL_BYTES + 1)}
        self.assertEqual(err(voice.signal, self.a, self.crew["id"], SID(1), self.b["id"], None, big).status, 413)
        for kind in voice.SIGNAL_TYPES:
            voice.signal(self.a, self.crew["id"], SID(1), self.b["id"], None, {"type": kind})

    def test_a_flood_of_messages_is_slowed_down(self):
        for _ in range(voice.SIGNALS_PER_10S):
            voice.signal(self.a, self.crew["id"], SID(1), self.b["id"], None, {"type": "candidate", "candidate": {}})
        self.assertEqual(err(voice.signal, self.a, self.crew["id"], SID(1), self.b["id"], None, {"type": "ready"}).status, 429)
        voice.signal(self.b, self.crew["id"], SID(2), self.a["id"], None, {"type": "ready"})            # others are not affected


class RelayServers(Base):
    def test_the_default_needs_no_setup_and_uses_public_stun(self):
        out = voice.join(self.a, self.crew["id"], SID(1))
        self.assertTrue(out["ice"][0]["urls"][0].startswith("stun:"))
        self.assertEqual(len(out["ice"]), 1)

    def test_with_a_turn_server_each_person_gets_short_lived_credentials_that_check_out(self):
        with mock.patch.object(economy, "TURN_URL", "turn:turn.example.com:3478,turns:turn.example.com:5349"), \
                mock.patch.object(economy, "TURN_SECRET", "shared-secret-123"), mock.patch.object(economy, "TURN_TTL_S", 600):
            out = voice.join(self.a, self.crew["id"], SID(1))
        turn = out["ice"][-1]
        self.assertEqual(turn["urls"], ["turn:turn.example.com:3478", "turns:turn.example.com:5349"])
        expiry, who = turn["username"].split(":")
        self.assertEqual(who, self.a["id"])
        self.assertAlmostEqual(int(expiry), time.time() + 600, delta=10)
        want = base64.b64encode(hmac.new(b"shared-secret-123", turn["username"].encode(), hashlib.sha1).digest()).decode()
        self.assertEqual(turn["credential"], want)
        self.assertNotIn("shared-secret-123", json.dumps(out, default=list))

    def test_the_servers_are_only_given_to_members(self):
        with mock.patch.object(economy, "TURN_URL", "turn:t.example.com"), mock.patch.object(economy, "TURN_SECRET", "s3cret"):
            self.assertEqual(err(voice.join, self.out, self.crew["id"], SID(1)).status, 403)


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        voice.clear()
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

    def test_everything_needs_a_login(self):
        anon = Client(self.port)
        for method, path in (("GET", "/api/voice/rooms"), ("POST", "/api/voice/join"), ("POST", "/api/voice/leave"),
                             ("POST", "/api/voice/state"), ("POST", "/api/voice/signal")):
            self.assertEqual(anon.call(method, path, {})[0], 401, path)

    def test_two_friends_find_each_other_and_a_stranger_hears_nothing(self):
        a, b, s = self.person("vocalone"), self.person("vocaltwo"), self.person("stranger1")
        st, c = a.call("POST", "/api/circles", {"name": "Voices", "visibility": "private"})
        cid, code = c["circle"]["id"], c["circle"]["inviteCode"]
        b.call("POST", "/api/circles/join", {"code": code})
        la, lb, ls = Listener(self.port, a), Listener(self.port, b), Listener(self.port, s)
        try:
            time.sleep(0.3)
            self.assertEqual(s.call("POST", "/api/voice/join", {"circleId": cid, "sid": SID(9)})[0], 403)
            st, ja = a.call("POST", "/api/voice/join", {"circleId": cid, "sid": SID(1)})
            self.assertEqual((st, ja["peers"], ja["maxPeople"]), (200, [], economy.VOICE_MAX_PEOPLE))
            self.assertTrue(ja["ice"])
            st, jb = b.call("POST", "/api/voice/join", {"circleId": cid, "sid": SID(2)})
            self.assertEqual([p["username"] for p in jb["peers"]], ["vocalone"])
            ids = {p["username"]: p["id"] for p in jb["people"]}
            st, r = b.call("POST", "/api/voice/signal", {"circleId": cid, "sid": SID(2), "to": ids["vocalone"], "toSid": SID(1),
                                                         "data": {"type": "offer", "sdp": "v=0 fake"}})
            self.assertEqual(st, 200)
            time.sleep(0.4)
            got = [e for e in la.of("voice") if e["k"] == "signal"]
            self.assertEqual((len(got), got[0]["data"]["sdp"], got[0]["fromName"]), (1, "v=0 fake", "vocaltwo"))
            self.assertEqual([e for e in lb.of("voice") if e["k"] == "signal"], [], "the sender does not get it back")
            rooms_a = [e for e in la.of("voice") if e["k"] == "room"]
            self.assertTrue(rooms_a and {p["username"] for p in rooms_a[-1]["people"]} == {"vocalone", "vocaltwo"})
            self.assertEqual(ls.of("voice"), [], "somebody outside the circle hears nothing at all")
            st, state = a.call("POST", "/api/voice/state", {"circleId": cid, "sid": SID(1), "muted": True})
            self.assertEqual((st, state["inRoom"]), (200, True))
            time.sleep(0.3)
            last = [e for e in lb.of("voice") if e["k"] == "room"][-1]
            self.assertTrue({p["username"]: p["muted"] for p in last["people"]}["vocalone"])
            st, rooms = s.call("GET", "/api/voice/rooms")
            self.assertEqual(rooms["rooms"], [])
            self.assertEqual(s.call("POST", "/api/voice/signal", {"circleId": cid, "sid": SID(9), "to": ids["vocalone"], "data": {"type": "ready"}})[0], 403)
            a.call("POST", "/api/voice/join", {"circleId": cid, "sid": SID(11)})                   # second tab
            time.sleep(0.3)
            self.assertTrue([e for e in la.of("voice") if e["k"] == "replaced" and e["sid"] == SID(1)])
            st, out = a.call("POST", "/api/voice/leave", {"circleId": cid, "sid": SID(1)})
            self.assertFalse(out["left"])
            st, out = a.call("POST", "/api/voice/leave", {"circleId": cid, "sid": SID(11)})
            self.assertTrue(out["left"])
        finally:
            for l in (la, lb, ls):
                l.close()

    def test_leaving_a_circle_ends_your_call(self):
        a, b = self.person("callera"), self.person("callerb")
        st, c = a.call("POST", "/api/circles", {"name": "Quit", "visibility": "public"})
        cid = c["circle"]["id"]
        b.call("POST", f"/api/circles/{cid}/join", {})
        lb = Listener(self.port, b)
        try:
            time.sleep(0.2)
            b.call("POST", "/api/voice/join", {"circleId": cid, "sid": SID(5)})
            b.call("POST", f"/api/circles/{cid}/leave", {})
            time.sleep(0.3)
            self.assertTrue([e for e in lb.of("voice") if e["k"] == "removed" and e["sid"] == SID(5)])
            self.assertEqual(voice.people(cid), [])
        finally:
            lb.close()


if __name__ == "__main__":
    unittest.main()
