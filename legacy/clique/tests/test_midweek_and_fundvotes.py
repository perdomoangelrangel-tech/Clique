"""Two rules about money coming in.

1. The Wednesday bonus (weekly.pay_midweek): every week, from Wednesday 12:00 (the site's time zone), everybody who has an account by then is
   given MIDWEEK_BONUS in the weekly account, once, never as winnings.
2. The vote on added funds (backend/fundvotes.py): what is added with the host's "Add funds" box waits, on hold, for a vote of everybody else,
   and only an approved one reaches an account.
"""
import datetime
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                    # noqa: E402
from backend import config, economy, fundvotes, inbox, ledger, users, weekly   # noqa: E402
from backend.store import db                                     # noqa: E402
from backend.util import ApiError, DAY_MS, TZ, now_ms, week_key  # noqa: E402
from tests import helpers                                        # noqa: E402
from tests.econ import books_balance, circle_of, mk             # noqa: E402
from tests.test_http import Client                               # noqa: E402

HOUR = 3_600_000
PW = config.ADMIN_PASSWORD


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Midweek(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(economy, "MIDWEEK_BONUS", 500.0)          # (the rest of the tests run with it off: see tests/__init__.py)
        patcher.start()
        self.addCleanup(patcher.stop)
        helpers.fresh_store()
        self.week = week_key()
        self.due = weekly.midweek_ms(self.week)
        self.ann, self.ben = mk("ann", weekly=300), mk("ben", weekly=40)

    def pay(self, now=None):
        return weekly.pay_midweek(self.week, now=self.due if now is None else now)

    def test_it_is_due_on_wednesday_at_noon_in_the_sites_time_zone(self):
        local = datetime.datetime.fromtimestamp(self.due / 1000, TZ)
        self.assertEqual((local.weekday(), local.hour, local.minute, local.second), (2, 12, 0, 0))
        self.assertEqual(week_key(self.due), self.week)

    def test_the_amount_that_ships_is_500_and_the_environment_can_change_or_remove_it(self):
        def shipped(**env):
            e = {k: v for k, v in os.environ.items() if k != "MIDWEEK_BONUS"}
            e.update(env)
            r = subprocess.run([sys.executable, "-c", "from backend import economy; print(economy.MIDWEEK_BONUS)"], cwd=ROOT, env=e, capture_output=True, text=True)
            return r.stdout.strip()
        self.assertEqual(shipped(), "500.0")
        self.assertEqual(shipped(MIDWEEK_BONUS="250"), "250.0")
        self.assertEqual(shipped(MIDWEEK_BONUS="0"), "0.0")

    def test_nothing_before_noon_and_everybody_gets_it_at_noon(self):
        self.assertEqual(self.pay(self.due - 1), 0)
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (300.0, 40.0))
        self.assertEqual(self.pay(self.due), 2)
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (300.0 + economy.MIDWEEK_BONUS, 40.0 + economy.MIDWEEK_BONUS))
        self.assertTrue(books_balance(self.ann) and books_balance(self.ben))

    def test_once_a_week_however_often_it_runs_and_also_after_a_restart(self):
        self.pay()
        self.assertEqual(self.pay(self.due + HOUR), 0)
        self.assertEqual(self.pay(self.due + 3 * DAY_MS), 0)
        self.assertEqual(self.ann["balance"], 800.0)
        del db()["meta"]["midweek"]                                  # (as if the week's marker had been lost: each person is marked too)
        self.assertEqual(self.pay(self.due + 2 * HOUR), 0)
        self.assertEqual(self.ann["balance"], 800.0)
        ledger.post(self.ann, "weekly", 1, "test.setup", txid="midweek-" + self.week)
        self.assertEqual(self.ann["balance"], 800.0)                 # (and the ledger row has a fixed id of its own)

    def test_a_server_that_was_off_at_noon_pays_when_it_is_back_in_the_same_week(self):
        self.assertEqual(self.pay(self.due + 30 * HOUR), 2)          # Thursday evening
        self.assertEqual(self.ann["balance"], 800.0)

    def test_it_is_money_from_outside_so_it_is_never_winnings(self):
        c = circle_of(self.ann, self.ben)
        before = {r["user"]["id"]: r["delta"] for r in weekly.standings(c, self.week)}
        self.pay()
        row = ledger.entries(self.ann)[0]
        self.assertEqual((row["reason"], row["amount"], row["external"], row["account"]), ("weekly.midweek", 500.0, True, "weekly"))
        self.assertEqual(self.ann["wk"]["ext_c"], 50000)
        after = {r["user"]["id"]: r["delta"] for r in weekly.standings(c, self.week)}
        self.assertEqual(after, before)

    def test_only_people_who_had_an_account_by_noon_and_are_in_good_standing(self):
        late = mk("late")
        late["createdAt"] = self.due + 60_000
        gone, banned = mk("gone"), mk("banned")
        gone["deleted"], banned["suspended"] = True, True
        self.assertEqual(self.pay(), 2)
        for u in (late, gone, banned):
            self.assertEqual(u["balance"], 1000.0)

    def test_the_person_is_told(self):
        self.pay()
        item = self.ann["inbox"][0]
        self.assertEqual((item["kind"], item["title"]), ("bonus", "Wednesday bonus"))
        self.assertIn("$500.00", item["text"])
        self.assertTrue(any(e["userId"] == self.ann["id"] and e["item"]["kind"] == "bonus" for e in inbox.PENDING))

    def test_zero_turns_it_off(self):
        with mock.patch.object(economy, "MIDWEEK_BONUS", 0.0):
            self.assertEqual(self.pay(self.due + HOUR), 0)
        self.assertEqual(self.ann["balance"], 300.0)

    def test_the_clock_loop_pays_it(self):
        db()["meta"]["week"] = self.week
        db()["meta"]["requirements_from"] = self.week
        with mock.patch.object(weekly, "now_ms", lambda: self.due + 5000):
            self.assertTrue(weekly.tick())
        self.assertEqual(self.ann["balance"], 800.0)
        with mock.patch.object(weekly, "now_ms", lambda: self.due + 6000):
            weekly.tick()
        self.assertEqual(self.ann["balance"], 800.0)

    def test_the_next_weeks_wednesday_is_paid_again(self):
        self.pay()
        nxt = weekly.next_week_key(self.week)
        self.assertEqual(weekly.pay_midweek(nxt, now=weekly.midweek_ms(nxt)), 2)
        self.assertEqual(self.ann["balance"], 1300.0)


class VoteBase(unittest.TestCase):
    def setUp(self):
        helpers.fresh_store()
        self.ann = mk("ann", weekly=300)
        self.others = [mk(n) for n in ("ben", "cat", "dan", "eve")]
        self.ben, self.cat, self.dan, self.eve = self.others

    def propose(self, amount=5000, account="weekly", who=None):
        return fundvotes.propose(who or self.ann, amount, PW, account)

    def vote(self, v, voter, favor):
        return fundvotes.cast(voter, v["id"], favor)

    def balance(self, u=None, account="weekly"):
        return ledger.balance(u or self.ann, account)


class StartingAVote(VoteBase):
    def test_the_money_is_on_hold_and_everybody_else_is_asked(self):
        v = self.propose(5000)
        self.assertEqual((v["status"], self.balance()), ("open", 300.0))
        self.assertEqual(fundvotes.hold(self.ann), {"weekly": 5000.0})
        self.assertEqual(server.me_json(self.ann)["onHold"], {"weekly": 5000.0})
        for u in self.others:
            owed = fundvotes.owed(u)
            self.assertEqual([(o["username"], o["amount"], o["account"], o["total"]) for o in owed], [("ann", 5000.0, "weekly", 4)])
            item = u["inbox"][0]
            self.assertEqual((item["kind"], item["data"]["vote"]), ("fundvote", v["id"]))
            self.assertIn("$5,000.00", item["text"])
        self.assertEqual(fundvotes.owed(self.ann), [])                    # the person asking is not asked
        self.assertNotIn("fundvote", [i["kind"] for i in self.ann.get("inbox", [])])

    def test_the_hold_is_not_in_any_account_or_net_worth(self):
        self.propose(5000, "accumulated")
        self.assertEqual((self.balance(), self.balance(account="accumulated")), (300.0, 0.0))
        self.assertTrue(books_balance(self.ann))

    def test_a_wrong_password_never_starts_a_vote_or_asks_anybody(self):
        with self.assertRaises(ApiError) as ctx:
            fundvotes.propose(self.ann, 5000, "not the password")
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(db().get("fundvotes", {}), {})
        self.assertEqual([i for u in self.others for i in u.get("inbox", [])], [])

    def test_the_same_checks_as_the_box_always_had(self):
        for args, text in (((0, PW), "greater than 0"), ((config.MAX_DEPOSIT + 1, PW), "Max"), ((5, PW, "savings"), "weekly or the accumulated")):
            with self.assertRaises(ApiError) as ctx:
                fundvotes.propose(self.ann, *args)
            self.assertIn(text, ctx.exception.message)
        self.assertEqual(db().get("fundvotes", {}), {})

    def test_one_request_at_a_time_per_person_but_others_can_ask(self):
        self.propose(100)
        with self.assertRaises(ApiError) as ctx:
            self.propose(200)
        self.assertIn("still waiting", ctx.exception.message)
        self.propose(300, who=self.ben)
        self.assertEqual(len([v for v in db()["fundvotes"].values() if v["status"] == "open"]), 2)

    def test_somebody_who_asks_again_after_the_vote_ended_can(self):
        v = self.propose(100)
        for u in (self.ben, self.cat, self.dan):
            self.vote(v, u, True)
        self.assertEqual(v["status"], "approved")
        self.assertEqual(self.propose(200)["status"], "open")

    def test_suspended_deleted_new_and_the_person_themselves_are_not_voters(self):
        self.eve["suspended"] = True
        self.dan["deleted"] = True
        v = self.propose(100)
        self.assertEqual(sorted(v["voters"]), sorted([self.ben["id"], self.cat["id"]]))
        newcomer = mk("newcomer")
        self.assertEqual(fundvotes.owed(newcomer), [])                      # arrived after the request: not asked
        self.assertEqual(fundvotes.owed(self.eve), [])

    def test_with_nobody_to_ask_the_money_is_added_at_once(self):
        helpers.fresh_store()
        solo = mk("solo", weekly=10)
        v = fundvotes.propose(solo, 700, PW)
        self.assertEqual((v["status"], solo["balance"]), ("approved", 710.0))
        self.assertEqual(solo["inbox"][0]["title"], "Funds added")


class CastingVotes(VoteBase):
    def test_votes_are_final_and_only_for_the_people_asked(self):
        v = self.propose(100)
        self.vote(v, self.ben, True)
        with self.assertRaises(ApiError) as ctx:
            self.vote(v, self.ben, False)
        self.assertIn("already voted", ctx.exception.message)
        for who in (self.ann, mk("stranger")):
            with self.assertRaises(ApiError) as ctx:
                self.vote(v, who, True)
            self.assertEqual(ctx.exception.status, 403)
        with self.assertRaises(ApiError):
            fundvotes.cast(self.cat, v["id"], "yes")                       # must be true or false
        with self.assertRaises(ApiError) as ctx:
            fundvotes.cast(self.cat, "nope", True)
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(fundvotes.owed(self.ben), [])                      # nothing left to vote on for the one who voted

    def test_nobody_sees_how_the_others_voted_while_it_is_open(self):
        v = self.propose(100)
        self.vote(v, self.ben, False)
        for who in (self.ann, self.cat):
            rows = fundvotes.mine(who) if who is self.ann else fundvotes.owed(who)
            self.assertEqual((rows[0]["voted"], rows[0]["total"], "result" in rows[0]), (1, 4, False))

    def test_a_vote_that_has_ended_takes_no_more_votes(self):
        v = self.propose(100)
        for u in (self.ben, self.cat, self.dan):
            self.vote(v, u, True)
        with self.assertRaises(ApiError) as ctx:
            self.vote(v, self.eve, True)
        self.assertIn("already ended", ctx.exception.message)


class HowItEnds(VoteBase):
    def test_in_favor_by_more_than_the_ones_still_to_vote_ends_it_early_and_adds_the_money(self):
        v = self.propose(5000)
        self.vote(v, self.ben, True)
        self.vote(v, self.cat, True)
        self.assertEqual(v["status"], "open")                              # 2 in favor, 2 still to vote: could still tie
        self.vote(v, self.dan, True)
        self.assertEqual((v["status"], v["result"]), ("approved", {"inFavor": 3, "against": 0, "didNotVote": 1}))
        self.assertEqual(self.balance(), 5300.0)
        self.assertEqual(fundvotes.hold(self.ann), {})
        self.assertNotIn("onHold", server.me_json(self.ann))
        self.assertEqual(fundvotes.owed(self.eve), [])                      # the one who did not vote is no longer asked

    def test_against_by_enough_to_stop_it_ever_passing_ends_it_early_and_adds_nothing(self):
        v = self.propose(5000)
        self.vote(v, self.ben, False)
        self.vote(v, self.cat, False)
        self.assertEqual((v["status"], self.balance()), ("rejected", 300.0))
        self.assertEqual(self.ann["inbox"][0]["title"], "Funds not approved")
        self.assertTrue(books_balance(self.ann))
        self.assertEqual(fundvotes.hold(self.ann), {})

    def test_everybody_voting_a_tie_does_not_pass(self):
        v = self.propose(5000)
        for u, favor in ((self.ben, True), (self.cat, False), (self.dan, True)):
            self.vote(v, u, favor)
        self.assertEqual(v["status"], "open")
        self.vote(v, self.eve, False)
        self.assertEqual((v["status"], self.balance()), ("rejected", 300.0))

    def test_the_last_voter_can_decide_it(self):
        v = self.propose(5000)
        for u, favor in ((self.ben, True), (self.cat, False), (self.dan, True)):
            self.vote(v, u, favor)
        self.assertEqual(v["status"], "open")                              # 2 in favor, 1 against, 1 to go: it could still tie
        self.vote(v, self.eve, True)
        self.assertEqual((v["status"], self.balance()), ("approved", 5300.0))

    def test_two_against_and_one_in_favor_is_already_settled_with_one_to_go(self):
        v = self.propose(5000)
        for u, favor in ((self.ben, True), (self.cat, False), (self.dan, False)):
            self.vote(v, u, favor)
        self.assertEqual(v["status"], "rejected")                          # the last one could only make it a tie

    def test_when_the_time_is_up_more_in_favor_than_against_passes_even_if_not_everyone_voted(self):
        v = self.propose(5000)
        self.vote(v, self.ben, True)
        self.assertFalse(fundvotes.tick(now=v["closesAt"] - 1))
        self.assertTrue(fundvotes.tick(now=v["closesAt"]))
        self.assertEqual((v["status"], v["result"]["didNotVote"], self.balance()), ("approved", 3, 5300.0))

    def test_when_the_time_is_up_with_nobody_voting_nothing_is_added(self):
        v = self.propose(5000)
        fundvotes.tick(now=v["closesAt"] + 1)
        self.assertEqual((v["status"], self.balance()), ("rejected", 300.0))
        self.assertEqual(v["result"], {"inFavor": 0, "against": 0, "didNotVote": 4})

    def test_when_the_time_is_up_a_tie_or_more_against_does_not_pass(self):
        v = self.propose(5000)
        self.vote(v, self.ben, True)
        self.vote(v, self.cat, False)
        fundvotes.tick(now=v["closesAt"] + 1)
        self.assertEqual(v["status"], "rejected")

    def test_the_time_limit_follows_the_setting(self):
        with mock.patch.object(economy, "FUNDS_VOTE_HOURS", 2.0):
            v = self.propose(100)
        self.assertEqual(v["closesAt"] - v["createdAt"], 2 * HOUR)
        self.assertEqual(economy.FUNDS_VOTE_HOURS, 24.0)

    def test_it_closes_only_once_and_pays_only_once(self):
        v = self.propose(5000)
        for u in (self.ben, self.cat, self.dan):
            self.vote(v, u, True)
        fundvotes.tick(now=v["closesAt"] + 1)
        fundvotes.settle(v)
        self.assertEqual(self.balance(), 5300.0)
        self.assertEqual(len([r for r in ledger.entries(self.ann) if r["reason"] == "deposit"]), 1)

    def test_everybody_is_told_how_it_ended(self):
        v = self.propose(5000)
        for u in (self.ben, self.cat, self.dan):
            self.vote(v, u, True)
        for u in self.others:
            self.assertEqual(u["inbox"][0]["title"], "Vote ended")
            self.assertIn("approved", u["inbox"][0]["text"])
        self.assertEqual(self.ann["inbox"][0]["title"], "Funds approved")
        self.assertIn("3 in favor, 0 against", self.ann["inbox"][0]["text"])


class WhereTheMoneyGoes(VoteBase):
    def test_the_account_that_was_chosen_gets_it_as_money_from_outside(self):
        v = self.propose(700, "accumulated")
        for u in (self.ben, self.cat, self.dan):
            self.vote(v, u, True)
        self.assertEqual((self.balance(), self.balance(account="accumulated")), (300.0, 700.0))
        row = ledger.entries(self.ann, "accumulated")[0]
        self.assertEqual((row["reason"], row["external"], row["ref"]), ("deposit", True, v["id"]))
        self.assertTrue(books_balance(self.ann))

    def test_weekly_funds_are_never_winnings_and_count_as_a_deposit(self):
        c = circle_of(self.ann, self.ben)
        before = next(r["delta"] for r in weekly.standings(c, week_key()) if r["user"]["id"] == self.ann["id"])
        v = self.propose(5000)
        for u in (self.ben, self.cat, self.dan):
            self.vote(v, u, True)
        after = next(r["delta"] for r in weekly.standings(c, week_key()) if r["user"]["id"] == self.ann["id"])
        self.assertEqual(after, before)
        self.assertEqual(self.ann["stats"][week_key()]["deposits"], 5000.0)
        self.assertEqual(self.ann["activity"][0]["kind"], "deposit")

    def test_the_old_direct_credit_is_still_there_for_the_code_that_needs_it(self):
        users.deposit(self.ann, 50, PW)
        self.assertEqual(self.balance(), 350.0)


class ThroughTheServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helpers.fresh_store()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        helpers.restore_store_path()

    def person(self, name):
        c = Client(self.port)
        self.assertEqual(c.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})[0], 200)
        return c

    def test_the_whole_thing_over_http(self):
        a, b, c = self.person("hal"), self.person("ida"), self.person("jon")
        self.assertEqual(Client(self.port).call("GET", "/api/fundvotes")[0], 401)
        self.assertEqual(a.call("POST", "/api/wallet/deposit", {"amount": 50, "password": "x"})[0], 403)
        self.assertEqual(b.call("GET", "/api/fundvotes")[1]["owed"], [])                              # nothing asked yet
        st, d = a.call("POST", "/api/wallet/deposit", {"amount": 2500, "password": PW, "account": "accumulated"})
        self.assertEqual((st, d["added"], d["vote"]["status"], d["user"]["onHold"]), (200, 0, "open", {"accumulated": 2500.0}))
        self.assertEqual(a.call("POST", "/api/wallet/deposit", {"amount": 1, "password": PW})[0], 400)    # one at a time
        _, bd = b.call("GET", "/api/fundvotes")
        self.assertEqual([(v["username"], v["amount"], v["account"]) for v in bd["owed"]], [("hal", 2500.0, "accumulated")])
        self.assertEqual(a.call("GET", "/api/fundvotes")[1]["owed"], [])
        vid = bd["owed"][0]["id"]
        self.assertEqual(a.call("POST", f"/api/fundvotes/{vid}/vote", {"favor": True})[0], 403)         # not for the one who asked
        self.assertEqual(b.call("POST", f"/api/fundvotes/{vid}/vote", {"favor": "maybe"})[0], 400)
        self.assertEqual(b.call("POST", f"/api/fundvotes/{vid}/vote", {"favor": True})[0], 200)
        self.assertEqual(b.call("POST", f"/api/fundvotes/{vid}/vote", {"favor": False})[0], 400)        # final
        self.assertEqual(a.call("GET", "/api/me")[1]["user"]["accum"], 0.0)                              # still on hold
        st, d = c.call("POST", f"/api/fundvotes/{vid}/vote", {"favor": True})
        self.assertEqual((st, d["owed"]), (200, []))                                                     # 2 in favor of 2: over
        _, me = a.call("GET", "/api/me")
        self.assertEqual((me["user"]["accum"], "onHold" in me["user"]), (2500.0, False))
        _, mine = a.call("GET", "/api/fundvotes")
        self.assertEqual((mine["mine"][0]["status"], mine["mine"][0]["result"]), ("approved", {"inFavor": 2, "against": 0, "didNotVote": 0}))
        self.assertEqual(a.call("POST", f"/api/fundvotes/{vid}/vote", {"favor": True})[0], 400)         # over: "already ended"


if __name__ == "__main__":
    unittest.main()
