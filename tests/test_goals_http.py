"""Loans, ranks, challenges, milestones, notifications and transfers through the real HTTP server: who may call what, what comes back,
and that a refusal never changes anything (and a wrong transfer password is remembered even though the answer is an error)."""
import json
import os
import sys
import tempfile
import threading
import unittest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                     # noqa: E402
from backend import activity, challenges, ledger, mailer, progress, users, weekly   # noqa: E402
from backend.store import store                                   # noqa: E402
from backend.util import DAY_MS, week_bounds, week_key           # noqa: E402
from tests.helpers import restore_store_path                      # noqa: E402
from tests.test_http import Client                                # noqa: E402

START, END = week_bounds(week_key())
PW = "xfer-secret-1"


def tearDownModule():
    restore_store_path()


class GoalsOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.data = {}
        store.load()
        mailer.QUIET = True
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def person(self, name, age_days=5):
        c = Client(self.port)
        st, d = c.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})
        self.assertEqual(st, 200, d)
        u = users.by_username(name)
        u["createdAt"] -= int(age_days * DAY_MS)
        return c, u

    def friends(self, a, ua, b, ub):
        self.assertEqual(a.call("POST", "/api/friends/request", {"username": ub["username"]})[0], 200)
        self.assertEqual(b.call("POST", "/api/friends/accept", {"userId": ua["id"]})[0], 200)

    # ---- everything needs a log-in
    def test_every_new_endpoint_asks_who_you_are(self):
        anon = Client(self.port)
        for method, path in (("GET", "/api/loans"), ("POST", "/api/loans/borrow"), ("POST", "/api/loans/repay"), ("POST", "/api/loans/quote"),
                             ("GET", "/api/progress"), ("GET", "/api/challenges"), ("POST", "/api/challenges/claim"), ("POST", "/api/milestones/claim"),
                             ("GET", "/api/inbox"), ("POST", "/api/inbox/seen"), ("GET", "/api/transfers"), ("POST", "/api/transfers"),
                             ("POST", "/api/transfers/preview"), ("POST", "/api/transfers/password"), ("POST", "/api/transfers/password/code")):
            self.assertEqual(anon.call(method, path, {})[0], 401, path)

    # ---- loans
    def test_a_loan_from_the_quote_to_the_last_cent(self):
        c, u = self.person("lender1")
        ledger.post(u, "weekly", -700, "test.setup")                # through the ledger, so the books still balance: $300 left
        st, lo = c.call("GET", "/api/loans")
        self.assertEqual(st, 200)
        self.assertTrue(lo["eligible"], lo["reasons"])
        self.assertEqual((lo["available"], lo["active"]), (500.0, None))
        st, q = c.call("POST", "/api/loans/quote", {"amount": 200})
        self.assertEqual((st, q["amount"], q["total"], q["fee"]), (200, 200.0, 200.0, 0.0))
        self.assertEqual(u["balance"], 300.0, "a quote moves nothing")
        st, d = c.call("POST", "/api/loans/borrow", {"amount": 200})
        self.assertEqual(st, 400)
        self.assertIn("Confirm", d["error"])
        st, d = c.call("POST", "/api/loans/borrow", {"amount": 200, "confirm": True, "requestId": "loan-http-0001"})
        self.assertEqual(st, 200, d)
        self.assertEqual((d["received"], d["owed"], d["user"]["weekly"], d["user"]["debt"], d["user"]["netWorth"]), (200.0, 200.0, 500.0, 200.0, 300.0))
        st, again = c.call("POST", "/api/loans/borrow", {"amount": 200, "confirm": True, "requestId": "loan-http-0001"})
        self.assertEqual((st, again["duplicate"], u["balance"]), (200, True, 500.0))
        st, d = c.call("POST", "/api/loans/borrow", {"amount": 50, "confirm": True})
        self.assertEqual(st, 403)
        st, d = c.call("POST", "/api/loans/repay", {"amount": 80, "requestId": "repay-http-0001"})
        self.assertEqual((st, d["paid"], d["owed"], d["closed"]), (200, 80.0, 120.0, False))
        st, d = c.call("POST", "/api/loans/repay", {"amount": "all"})
        self.assertEqual((st, d["paid"], d["closed"], d["user"]["debt"]), (200, 120.0, True, 0.0))
        self.assertEqual(c.call("GET", "/api/loans")[1]["history"][0]["payments"][0]["amount"], 120.0)
        self.assertEqual(ledger.audit(u), {"weekly": 0, "accumulated": 0})

    def test_a_new_account_is_told_why_it_cannot_borrow(self):
        c, u = self.person("fresh1", age_days=0)
        st, lo = c.call("GET", "/api/loans")
        self.assertFalse(lo["eligible"])
        self.assertIn("hours after you join", " ".join(lo["reasons"]))
        st, d = c.call("POST", "/api/loans/borrow", {"amount": 100, "confirm": True})
        self.assertEqual(st, 403)
        self.assertEqual(u["balance"], 1000.0)

    # ---- rank, challenges, milestones and notifications
    def test_rank_challenges_milestones_and_the_inbox(self):
        c, u = self.person("player1")
        me = c.call("GET", "/api/me")[1]["user"]
        self.assertEqual(me["rank"], {"t": "bronze", "d": 3, "l": "Bronze III"})
        self.assertEqual((me["debt"], me["unseen"]), (0.0, 0))
        st, ch = c.call("GET", "/api/challenges")
        self.assertEqual((st, len(ch["weekly"]), len(ch["accumulated"])), (200, 4, 4))
        item = ch["weekly"][0]
        st, d = c.call("POST", "/api/challenges/claim", {"id": item["id"]})
        self.assertEqual(st, 400)
        self.assertIn("not finished", d["error"])
        self.assertEqual(c.call("POST", "/api/challenges/claim", {"id": "nope"})[0], 404)
        for i in range(item["target"] if item["family"] in ("days", "streak") else 1):
            activity.record(u, "casino", f"http-{i}", now=START + (i + 1) * DAY_MS, amount=5, game="dice")
        st, pr = c.call("GET", "/api/progress")
        self.assertEqual(st, 200)
        self.assertGreaterEqual(pr["xp"], 2)
        self.assertEqual(pr["rank"]["label"], "Bronze III")
        self.assertEqual(len(pr["ladder"]), 16)
        self.assertGreaterEqual(len(pr["milestones"]["milestones"]), 10)
        claimable = [t for m in pr["milestones"]["milestones"] for t in m["tiers"] if t["status"] == "reached"]
        self.assertTrue(claimable)
        tier = claimable[0]
        accum = u["accum"]
        st, r = c.call("POST", "/api/milestones/claim", {"id": tier["id"]})
        self.assertEqual((st, r["account"], r["amount"]), (200, "accumulated", tier["money"]))
        self.assertEqual(r["user"]["accum"], accum + tier["money"])
        self.assertEqual(c.call("POST", "/api/milestones/claim", {"id": tier["id"]})[0], 409)
        self.assertEqual(c.call("POST", "/api/milestones/claim", {"id": "zzz:1"})[0], 404)
        st, inb = c.call("GET", "/api/inbox")
        self.assertGreaterEqual(inb["unseen"], 1)
        self.assertEqual(c.call("GET", "/api/me")[1]["user"]["unseen"], inb["unseen"])
        st, seen = c.call("POST", "/api/inbox/seen", {"ids": [inb["items"][0]["id"]]})
        self.assertEqual((st, seen["unseen"]), (200, inb["unseen"] - 1))
        self.assertEqual(c.call("POST", "/api/inbox/seen", {"ids": "all"})[0], 400)
        self.assertEqual(c.call("POST", "/api/inbox/seen", {})[1]["unseen"], 0)

    def test_nobody_can_claim_for_somebody_else(self):
        a, ua = self.person("owner1")
        b, ub = self.person("thief1")
        ch = a.call("GET", "/api/challenges")[1]
        item = ch["accumulated"][0]
        challenges.add_fact(ua, week_key(), "created", 1)
        st, d = b.call("POST", "/api/challenges/claim", {"id": item["id"]})
        self.assertEqual(st, 400)
        self.assertEqual(ub["accum"], 0.0)

    def test_a_rank_is_shown_with_every_member_of_a_circle(self):
        a, ua = self.person("ranked1")
        b, ub = self.person("ranked2")
        progress.grant(ua, 2600, "test", "gold")
        st, d = a.call("POST", "/api/circles", {"name": "Rankers"})
        cid = d["circle"]["id"]
        b.call("POST", "/api/circles/join", {"code": d["circle"]["inviteCode"]})
        st, circle = a.call("GET", f"/api/circles/{cid}")
        ranks = {m["user"]["username"]: m["user"]["rank"]["l"] for m in circle["members"]}
        self.assertEqual(ranks, {"ranked1": "Gold I", "ranked2": "Bronze III"})

    # ---- transfers
    def test_transfers_end_to_end_with_a_wrong_password_remembered_on_disk(self):
        a, ua = self.person("sender1")
        b, ub = self.person("getter1")
        ledger.post(ua, "accumulated", 400, "test.setup")
        # not friends yet, no password yet
        st, tv = a.call("GET", "/api/transfers")
        self.assertEqual((st, tv["passwordSet"], tv["friends"], tv["limit"]["remaining"]), (200, False, [], 250.0))
        self.assertEqual(a.call("POST", "/api/transfers/password", {"loginPassword": "wrong", "newPassword": PW})[0], 403)
        st, d = a.call("POST", "/api/transfers/password", {"loginPassword": "secret123", "newPassword": PW})
        self.assertEqual((st, d["result"], d["transfers"]["passwordSet"]), (200, "set", True))
        self.assertNotIn(PW, json.dumps(d))
        self.friends(a, ua, b, ub)
        tv = a.call("GET", "/api/transfers")[1]
        self.assertEqual([f["username"] for f in tv["friends"]], ["getter1"])
        st, p = a.call("POST", "/api/transfers/preview", {"to": ub["id"], "amount": 75, "note": "hi"})
        self.assertEqual((st, p["amount"], p["senderBalanceAfter"], p["remainingAfter"], p["fee"]), (200, 75.0, 325.0, 175.0, 0.0))
        self.assertEqual(ua["accum"], 400.0)
        # a wrong password: refused, and the count is on DISK even though the answer was an error
        send = {"to": ub["id"], "amount": 75, "note": "hi", "confirm": True, "requestId": "xfer-http-0001"}
        st, d = a.call("POST", "/api/transfers", {**send, "password": "not-it"})
        self.assertEqual(st, 403)
        self.assertIn("4 more", d["error"])
        with open(store.path, "rb") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["users"][ua["id"]]["xfer"]["fails"], 1)
        self.assertEqual(ua["accum"], 400.0)
        st, d = a.call("POST", "/api/transfers", {**send, "password": PW})
        self.assertEqual(st, 200, d)
        self.assertEqual((d["receipt"]["amount"], d["receipt"]["status"], d["user"]["accum"]), (75.0, "completed", 325.0))
        self.assertEqual((ua["accum"], ub["accum"]), (325.0, 75.0))
        st, again = a.call("POST", "/api/transfers", {**send, "password": PW})
        self.assertEqual((st, again["duplicate"], ua["accum"]), (200, True, 325.0))
        got = b.call("GET", "/api/transfers")[1]["history"]
        self.assertEqual([(h["dir"], h["amount"], h["peer"]["username"]) for h in got], [("in", 75.0, "sender1")])
        self.assertEqual(b.call("GET", "/api/inbox")[1]["items"][0]["kind"], "transfer")
        self.assertEqual(a.call("GET", "/api/me")[1]["user"]["accum"], 325.0)

    def test_five_wrong_passwords_lock_it_and_the_lock_is_on_disk(self):
        a, ua = self.person("locker1")
        b, ub = self.person("locked2")
        ledger.post(ua, "accumulated", 100, "test.setup")
        self.friends(a, ua, b, ub)
        a.call("POST", "/api/transfers/password", {"loginPassword": "secret123", "newPassword": PW})
        last = None
        for i in range(5):
            last = a.call("POST", "/api/transfers", {"to": ub["id"], "amount": 5, "password": f"nope-{i}", "confirm": True, "requestId": f"lock-http-{i:04d}"})
        self.assertEqual(last[0], 429)
        self.assertGreater(last[1]["retryAfter"], 0)
        with open(store.path, "rb") as f:
            self.assertGreater(json.load(f)["users"][ua["id"]]["xfer"]["lockUntil"], 0)
        st, d = a.call("POST", "/api/transfers", {"to": ub["id"], "amount": 5, "password": PW, "confirm": True, "requestId": "lock-http-9999"})
        self.assertEqual(st, 429)
        self.assertIsNotNone(a.call("GET", "/api/transfers")[1]["locked"])
        self.assertEqual(ua["accum"], 100.0)

    def test_the_funds_cannot_go_to_somebody_who_is_not_a_friend_over_http_either(self):
        a, ua = self.person("giver1")
        b, ub = self.person("stranger1")
        ledger.post(ua, "accumulated", 100, "test.setup")
        a.call("POST", "/api/transfers/password", {"loginPassword": "secret123", "newPassword": PW})
        st, d = a.call("POST", "/api/transfers", {"to": ub["id"], "amount": 5, "password": PW, "confirm": True, "requestId": "stranger-0001"})
        self.assertEqual(st, 403)
        self.assertEqual((ua["accum"], ub["accum"]), (100.0, 0.0))

    def test_simultaneous_requests_over_the_real_server_pay_and_send_exactly_once(self):
        a, ua = self.person("racer1")
        b, ub = self.person("racer2")
        ledger.post(ua, "accumulated", 600, "test.setup")
        self.friends(a, ua, b, ub)
        a.call("POST", "/api/transfers/password", {"loginPassword": "secret123", "newPassword": PW})
        # eight tabs press Send for $100 at the same moment: the daily limit ($250) lets exactly two through
        results = []

        def send(i):
            c = Client(self.port)
            c.cookie = a.cookie
            results.append(c.call("POST", "/api/transfers", {"to": ub["id"], "amount": 100, "password": PW, "confirm": True, "requestId": f"race-http-{i:04d}"})[0])
        threads = [threading.Thread(target=send, args=(i,)) for i in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((results.count(200), results.count(403)), (2, 6))
        self.assertEqual((ua["accum"], ub["accum"]), (400.0, 200.0))
        self.assertEqual(ledger.audit(ua), {"weekly": 0, "accumulated": 0})
        # and eight claims of the same milestone
        activity.record(ua, "casino", "race-round", now=START + 2 * DAY_MS, amount=5, game="dice")
        accum = ua["accum"]
        claims = []

        def claim():
            c = Client(self.port)
            c.cookie = a.cookie
            claims.append(c.call("POST", "/api/milestones/claim", {"id": "house_guest:1"})[0])
        threads = [threading.Thread(target=claim) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((claims.count(200), claims.count(409)), (1, 7))
        self.assertEqual(ua["accum"], accum + 10.0)

    def test_the_password_reset_by_email_over_http(self):
        a, ua = self.person("forgetful1")
        a.call("POST", "/api/transfers/password", {"loginPassword": "secret123", "newPassword": PW})
        st, d = a.call("POST", "/api/transfers/password/code", {"loginPassword": "secret123"})
        self.assertEqual(st, 403)
        ua["mail"] = {"addr": "forgetful@example.com", "verified": True}
        mailer.RECENT.clear()
        st, d = a.call("POST", "/api/transfers/password/code", {"loginPassword": "secret123"})
        self.assertEqual(st, 200, d)
        import time
        for _ in range(50):
            if mailer.RECENT:
                break
            time.sleep(0.05)
        code = [w for w in mailer.RECENT[-1]["text"].split() if w.isdigit() and len(w) == 6][0]
        st, d = a.call("POST", "/api/transfers/password", {"loginPassword": "secret123", "newPassword": "new-xfer-pw", "code": code})
        self.assertEqual((st, d["result"]), (200, "reset"))


if __name__ == "__main__":
    unittest.main()
