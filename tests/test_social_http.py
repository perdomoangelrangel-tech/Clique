"""Friends, presence and chat through the real server: the routes, and who the live updates reach."""
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402
from tests.test_http import Client                         # noqa: E402


class Listener:
    """Holds an event stream open and keeps everything that arrives on it."""

    def __init__(self, port, client):
        self.events, self.stop = [], False
        self.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=6)
        self.conn.request("GET", "/api/stream", headers={"Cookie": client.cookie})
        self.resp = self.conn.getresponse()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        while not self.stop:
            try:
                line = self.resp.fp.readline()
            except Exception:
                return
            if not line:
                return
            if line.startswith(b"data: "):
                self.events.append(json.loads(line[6:]))

    def of(self, kind):
        return [e for e in self.events if e.get("type") == kind]

    def close(self):
        self.stop = True
        self.conn.close()


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.count = 0

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        restore_store_path()

    def setUp(self):
        """Four fresh people for every test, so what one test does never leaks into the next."""
        type(self).count += 1
        self.c, self.me, self.name = {}, {}, {}
        for short in ("ann", "bobby", "cathy", "danny"):
            full = f"{short}{self.count}"
            c = Client(self.port)
            st, d = c.call("POST", "/api/auth/register", {"username": full, "password": "secret123"})
            assert st == 200
            self.c[short], self.me[short], self.name[short] = c, d["user"]["id"], full

    def test_nothing_works_without_logging_in(self):
        anon = Client(self.port)
        for method, path in (("GET", "/api/friends"), ("GET", "/api/chats"), ("GET", "/api/chats/global"), ("POST", "/api/presence"),
                             ("POST", "/api/chats/global/send"), ("POST", "/api/friends/request")):
            self.assertEqual(anon.call(method, path, {"text": "x", "username": "x"})[0], 401, path)

    def test_the_whole_friend_request_conversation(self):
        ann, bob = self.c["ann"], self.c["bobby"]
        st, d = ann.call("POST", "/api/friends/request", {"username": self.name["bobby"]})
        self.assertEqual((st, d["outcome"], [u["username"] for u in d["outgoing"]]), (200, "requested", [self.name["bobby"]]))
        self.assertEqual([u["username"] for u in bob.call("GET", "/api/friends")[1]["incoming"]], [self.name["ann"]])
        self.assertEqual(bob.call("POST", "/api/friends/accept", {"userId": self.me["cathy"]})[0], 404)       # not from her
        st, d = bob.call("POST", "/api/friends/accept", {"userId": self.me["ann"]})
        self.assertEqual((st, d["outcome"], [f["username"] for f in d["friends"]]), (200, "friends", [self.name["ann"]]))
        self.assertEqual([f["username"] for f in ann.call("GET", "/api/friends")[1]["friends"]], [self.name["bobby"]])
        st, d = ann.call("POST", "/api/friends/request", {"username": "nobody_here_x"})
        self.assertEqual((st, d["error"]), (404, "User not found"))
        ann.call("POST", "/api/friends/remove", {"userId": self.me["bobby"]})
        self.assertEqual(ann.call("GET", "/api/friends")[1]["friends"], [])

    def test_presence_shows_friends_what_you_are_doing(self):
        ann, cat = self.c["ann"], self.c["cathy"]
        ann.call("POST", "/api/friends/request", {"username": self.name["cathy"]})
        cat.call("POST", "/api/friends/accept", {"userId": self.me["ann"]})
        self.assertFalse(ann.call("GET", "/api/friends")[1]["friends"][0]["online"])
        self.assertEqual(cat.call("POST", "/api/presence", {"where": {"k": "game", "v": "limbo"}, "visible": True})[0], 200)
        row = ann.call("GET", "/api/friends")[1]["friends"][0]
        self.assertEqual((row["username"], row["online"], row["where"]), (self.name["cathy"], True, "Playing Limbo"))
        cat.call("POST", "/api/friends/hide", {"hide": True})
        self.assertFalse(ann.call("GET", "/api/friends")[1]["friends"][0]["online"])
        cat.call("POST", "/api/friends/hide", {"hide": False})
        ann.call("POST", "/api/friends/remove", {"userId": self.me["cathy"]})

    def test_the_global_chat_end_to_end(self):
        ann, bob = self.c["ann"], self.c["bobby"]
        st, d = ann.call("POST", "/api/chats/global/send", {"text": "  hello   everyone  "})
        self.assertEqual((st, d["message"]["x"], d["message"]["name"]), (200, "hello everyone", self.name["ann"]))
        self.assertEqual(ann.call("POST", "/api/chats/global/send", {"text": ""})[0], 400)
        st, d = bob.call("GET", "/api/chats/global")
        self.assertEqual(d["messages"][-1]["x"], "hello everyone")
        self.assertEqual(d["chat"]["name"], "Everyone")
        n = d["messages"][-1]["n"]
        self.assertEqual(bob.call("GET", f"/api/chats/global?after={n}")[1]["messages"], [])
        st, d = bob.call("POST", "/api/chats/global/read", {"upTo": n})
        self.assertEqual(st, 200)
        self.assertEqual(ann.call("POST", "/api/chats/global/delete", {"n": n})[0], 200)

    def test_live_updates_reach_exactly_the_right_people(self):
        ann, bob, cat, dan = (self.c[n] for n in ("ann", "bobby", "cathy", "danny"))
        st, d = ann.call("POST", "/api/circles", {"name": "Closed", "visibility": "private"})
        circle, code = d["circle"]["id"], d["circle"]["inviteCode"]
        bob.call("POST", "/api/circles/join", {"code": code})
        listeners = {n: Listener(self.port, c) for n, c in (("ann", ann), ("bobby", bob), ("cathy", cat), ("danny", dan))}
        try:
            time.sleep(0.5)
            ann.call("POST", f"/api/chats/circle_{circle}/send", {"text": "circle secret"})
            ann.call("POST", "/api/chats/global/send", {"text": "to everybody"})
            ann.call("POST", "/api/friends/request", {"username": self.name["danny"]})
            time.sleep(0.6)
            texts = {n: [e["msg"]["x"] for e in l.of("chat") if "msg" in e] for n, l in listeners.items()}
            self.assertEqual(sorted(texts["bobby"]), ["circle secret", "to everybody"])        # in the circle: both
            self.assertEqual(texts["ann"].count("circle secret"), 1)
            self.assertEqual(texts["cathy"], ["to everybody"])                                  # outside it: only the open chat
            self.assertEqual(texts["danny"], ["to everybody"])
            self.assertTrue(any(e.get("what") == "requested" and e.get("by") == self.name["ann"] for e in listeners["danny"].of("friends")))
            self.assertEqual(listeners["cathy"].of("friends"), [])                              # nobody else hears about the request
            self.assertEqual(listeners["bobby"].of("friends"), [])
        finally:
            for l in listeners.values():
                l.close()
            dan.call("POST", "/api/friends/decline", {"userId": self.me["ann"]})

    def test_read_receipts_over_the_wire(self):
        ann, bob, cat = self.c["ann"], self.c["bobby"], self.c["cathy"]
        ann.call("POST", "/api/friends/request", {"username": self.name["bobby"]})
        bob.call("POST", "/api/friends/accept", {"userId": self.me["ann"]})
        dm = ann.call("POST", "/api/chats/dm", {"userId": self.me["bobby"]})[1]["chat"]["id"]
        n = ann.call("POST", f"/api/chats/{dm}/send", {"text": "did you see this"})[1]["message"]["n"]
        self.assertEqual(ann.call("GET", f"/api/chats/{dm}")[1]["chat"]["readers"], [])
        self.assertTrue(ann.call("GET", "/api/chats")[1]["receipts"])
        listeners = {k: Listener(self.port, c) for k, c in (("ann", ann), ("bobby", bob), ("cathy", cat))}
        try:
            time.sleep(0.4)
            self.assertEqual(bob.call("POST", f"/api/chats/{dm}/read", {"upTo": n})[0], 200)
            bob.call("POST", f"/api/chats/{dm}/read", {"upTo": n})                              # reading again changes nothing, tells nobody
            time.sleep(0.5)
            got = listeners["ann"].of("seen")
            self.assertEqual([(e["id"], e["u"], e["n"]) for e in got], [(dm, self.me["bobby"], n)])
            self.assertEqual(listeners["cathy"].of("seen"), [])                                  # an outsider hears nothing
            self.assertEqual(listeners["bobby"].of("seen"), [])                                  # and you are not told about yourself
            seen = ann.call("GET", f"/api/chats/{dm}")[1]["chat"]["readers"]
            self.assertEqual([(r["username"], r["n"]) for r in seen], [(self.name["bobby"], n)])
            self.assertEqual(cat.call("GET", f"/api/chats/{dm}")[0], 404)
            st, d = bob.call("POST", "/api/chats/receipts", {"on": False})                       # bob turns his off
            self.assertEqual((st, d), (200, {"receipts": False}))
            n2 = ann.call("POST", f"/api/chats/{dm}/send", {"text": "and this one?"})[1]["message"]["n"]
            bob.call("POST", f"/api/chats/{dm}/read", {"upTo": n2})
            time.sleep(0.5)
            self.assertEqual(len(listeners["ann"].of("seen")), 1)                                # no second event: bob's are off
            self.assertEqual(ann.call("GET", f"/api/chats/{dm}")[1]["chat"]["readers"], [])
            self.assertEqual(bob.call("GET", f"/api/chats/{dm}")[1]["chat"]["readers"], [])      # and he cannot see ann's either
            self.assertEqual(bob.call("POST", "/api/chats/receipts", {"on": "yes"})[0], 400)
            self.assertEqual(cat.call("POST", "/api/chats/receipts", {"on": False})[0], 200)
            self.assertEqual(self.c["danny"].call("POST", "/api/chats/receipts", {})[0], 400)
        finally:
            for l in listeners.values():
                l.close()

    def test_private_chats_over_the_wire(self):
        ann, bob, cat = self.c["ann"], self.c["bobby"], self.c["cathy"]
        for name, c in ((self.name["bobby"], bob), (self.name["cathy"], cat)):
            ann.call("POST", "/api/friends/request", {"username": name})
            c.call("POST", "/api/friends/accept", {"userId": self.me["ann"]})
        st, d = ann.call("POST", "/api/chats/dm", {"userId": self.me["bobby"]})
        dm = d["chat"]["id"]
        self.assertEqual((st, d["chat"]["name"]), (200, self.name["bobby"]))
        self.assertEqual(self.c["danny"].call("POST", "/api/chats/dm", {"userId": self.me["ann"]})[0], 403)   # not friends
        self.assertEqual(ann.call("POST", f"/api/chats/{dm}/send", {"text": "psst"})[0], 200)
        self.assertEqual(cat.call("GET", f"/api/chats/{dm}")[0], 404)
        self.assertEqual(cat.call("POST", f"/api/chats/{dm}/send", {"text": "me too"})[0], 404)
        _, d = bob.call("GET", "/api/chats/unread")
        self.assertEqual(d["total"], 1)
        st, d = ann.call("POST", "/api/chats/group", {"name": "Trio", "members": [self.me["bobby"], self.me["cathy"]]})
        gid = d["chat"]["id"]
        self.assertEqual((st, d["chat"]["name"], d["chat"]["canManage"], len(d["chat"]["people"])), (200, "Trio", True, 3))
        self.assertEqual(ann.call("POST", "/api/chats/group", {"name": "Too small", "members": [self.me["bobby"]]})[0], 400)
        self.assertEqual(self.c["danny"].call("GET", f"/api/chats/{gid}")[0], 404)
        self.assertEqual(bob.call("POST", f"/api/chats/{gid}/rename", {"name": "Hijack"})[0], 403)
        self.assertEqual(ann.call("POST", f"/api/chats/{gid}/members", {"remove": self.me["cathy"]})[0], 200)
        self.assertEqual(cat.call("GET", f"/api/chats/{gid}")[0], 404)
        ids = [r["id"] for r in bob.call("GET", "/api/chats")[1]["chats"]]
        self.assertIn(gid, ids)
        self.assertIn(dm, ids)
        self.assertEqual(bob.call("POST", f"/api/chats/{gid}/leave", {})[0], 200)       # two left became one: the group closes
        self.assertEqual(ann.call("GET", f"/api/chats/{gid}")[0], 404)


if __name__ == "__main__":
    unittest.main()
