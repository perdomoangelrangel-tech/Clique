"""End-to-end checks through the real HTTP server (cookies, auth, live updates, privacy)."""
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                    # noqa: E402
from backend import config, fundvotes             # noqa: E402
from backend.store import store                  # noqa: E402


class Client:
    def __init__(self, port):
        self.port, self.cookie = port, None

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Content-Type": "application/json", **(headers or {})}
        if self.cookie:
            h["Cookie"] = self.cookie
        conn.request(method, path, json.dumps(body if body is not None else {}) if method != "GET" else None, h)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        sc = r.getheader("Set-Cookie")
        if sc and sc.startswith("sid=") and "Max-Age=0" not in sc:
            self.cookie = sc.split(";")[0]
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw


class HttpFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.data = {}
        store.load()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_full_flow(self):
        a, b = Client(self.port), Client(self.port)
        # auth is required
        self.assertEqual(a.call("GET", "/api/markets")[0], 401)
        self.assertEqual(a.call("POST", "/api/auth/register", {"username": "al", "password": "secret1"})[0], 400)
        st, d = a.call("POST", "/api/auth/register", {"username": "alice", "password": "secret123"})
        self.assertEqual((st, d["user"]["balance"]), (200, 1000.0))
        self.assertEqual(b.call("POST", "/api/auth/register", {"username": "bobby", "password": "secret123"})[0], 200)
        self.assertEqual(a.call("POST", "/api/auth/login", {"username": "alice", "password": "nope-nope"})[0], 401)

        # private circle + market stay invisible to outsiders until they use the code
        _, d = a.call("POST", "/api/circles", {"name": "Secret", "visibility": "private"})
        cid, code = d["circle"]["id"], d["circle"]["inviteCode"]
        _, d = a.call("POST", "/api/markets", {"circleId": cid, "question": "Will the test pass?"})
        mid = d["market"]["id"]
        self.assertEqual(b.call("GET", f"/api/markets/{mid}")[0], 404)
        self.assertEqual(b.call("GET", "/api/markets")[1]["markets"], [])
        self.assertEqual(b.call("GET", "/api/circles")[1]["discover"], [])
        self.assertEqual(b.call("POST", f"/api/circles/{cid}/join", {"code": "WRONG1"})[0], 403)
        self.assertEqual(b.call("POST", "/api/circles/join", {"code": code})[0], 200)
        self.assertEqual(len(b.call("GET", "/api/markets")[1]["markets"]), 1)

        # a bet is deducted and returned to the client
        st, d = b.call("POST", f"/api/markets/{mid}/trade", {"outcome": 0, "amount": 100})
        self.assertEqual((st, d["user"]["balance"]), (200, 900.0))
        st, d = b.call("POST", f"/api/markets/{mid}/trade", {"outcome": 0, "amount": 0.05})
        self.assertEqual(st, 400)
        # funds password: wrong is refused, right adds any amount
        self.assertEqual(b.call("POST", "/api/wallet/deposit", {"amount": 10, "password": "x"})[0], 403)
        st, d = b.call("POST", "/api/wallet/deposit", {"amount": 123456789, "password": config.ADMIN_PASSWORD})
        self.assertEqual((st, d["added"], d["user"]["balance"], d["user"]["onHold"]), (200, 0, 900.0, {"weekly": 123456789.0}))     # on hold: everybody else votes first
        st, d = a.call("GET", "/api/fundvotes")
        self.assertEqual((st, [(v["username"], v["amount"]) for v in d["owed"]]), (200, [("bobby", 123456789.0)]))
        st, d = a.call("POST", f"/api/fundvotes/{d['owed'][0]['id']}/vote", {"favor": True})
        self.assertEqual((st, d["owed"]), (200, []))
        mine = b.call("GET", "/api/fundvotes")[1]["mine"][0]
        self.assertEqual((mine["status"], mine["voted"]), ("open", 1))                      # (the other people in this test world have not voted)
        with server.LOCK:
            fundvotes.tick(now=mine["closesAt"] + 1)                                        # time is up: one in favor and nobody against passes
        st, d = b.call("GET", "/api/me")
        self.assertEqual((st, d["user"]["balance"], "onHold" in d["user"]), (200, 123457689.0, False))
        self.assertEqual(b.call("POST", f"/api/markets/{mid}/trade", {"outcome": 1, "amount": 50000})[0], 200)

    def test_cross_site_and_bad_content_type_blocked(self):
        a = Client(self.port)
        a.call("POST", "/api/auth/register", {"username": "carol", "password": "secret123"})
        st, _ = a.call("POST", "/api/circles", {"name": "Evil"}, {"Origin": "http://evil.example"})
        self.assertEqual(st, 403)
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("POST", "/api/circles", "name=x", {"Content-Type": "application/x-www-form-urlencoded", "Cookie": a.cookie})
        self.assertEqual(conn.getresponse().status, 415)

    def test_a_refused_body_is_read_so_the_connection_keeps_working(self):
        # Rejecting without reading the body made Windows reset the connection before the answer arrived.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/circles", "x" * 50_000, {"Content-Type": "text/plain"})
        r = conn.getresponse()
        self.assertEqual((r.status, r.getheader("Connection")), (415, None))
        r.read()
        conn.request("GET", "/api/me")                                  # the same connection, still usable
        self.assertEqual(conn.getresponse().status, 200)
        conn.close()

    def test_a_refused_body_too_big_to_read_ends_the_connection(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        old = server.DRAIN_LIMIT
        server.DRAIN_LIMIT = 10
        try:
            conn.request("POST", "/api/circles", "x" * 5_000, {"Content-Type": "text/plain"})
            r = conn.getresponse()
            self.assertEqual((r.status, r.getheader("Connection")), (415, "close"))
        finally:
            server.DRAIN_LIMIT = old
            conn.close()

    def test_live_updates_only_reach_members(self):
        owner, member, stranger = Client(self.port), Client(self.port), Client(self.port)
        for c, n in ((owner, "dora"), (member, "eddy"), (stranger, "fred")):
            c.call("POST", "/api/auth/register", {"username": n, "password": "secret123"})
        _, d = owner.call("POST", "/api/circles", {"name": "Closed", "visibility": "private"})
        cid, code = d["circle"]["id"], d["circle"]["inviteCode"]
        member.call("POST", "/api/circles/join", {"code": code})

        got = {}

        def listen(name, c):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
            conn.request("GET", "/api/stream", headers={"Cookie": c.cookie})
            r = conn.getresponse()
            buf = b""
            end = time.time() + 3
            while time.time() < end:
                try:
                    chunk = r.fp.readline()
                except Exception:
                    break
                buf += chunk
                if b"market" in buf:
                    break
            got[name] = buf

        threads = [threading.Thread(target=listen, args=(n, c)) for n, c in (("member", member), ("stranger", stranger))]
        for t in threads:
            t.start()
        time.sleep(0.6)
        owner.call("POST", "/api/markets", {"circleId": cid, "question": "Secret question here?"})
        for t in threads:
            t.join()
        self.assertIn(b"Secret question", got["member"])
        self.assertNotIn(b"Secret question", got["stranger"])


if __name__ == "__main__":
    unittest.main()
