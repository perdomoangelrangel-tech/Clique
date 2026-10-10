"""Transfers from the weekly account to a friend's weekly account, or from the accumulated account to a friend's accumulated account: the sender
chooses. Money never changes account on the way, and weekly chips carry the safeguards that keep the weekly leaderboard honest."""
import copy
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                                            # noqa: E402
from backend import economy, games, inbox, ledger, loans, mailer, markets, progress, social, transfers, users, weekly   # noqa: E402
from backend.store import LOCK, db, store                                                # noqa: E402
from backend.util import ApiError, DAY_MS, next_day_start_ms, prev_week_key, week_bounds, week_key   # noqa: E402
from tests.econ import books_balance, circle_of, mk                                      # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                # noqa: E402
from tests.test_http import Client                                                       # noqa: E402
from tests.test_transfers import LOGIN, NOW, PW, befriend, body, rid                     # noqa: E402

_ROUNDS = users.PBKDF2_ROUNDS
DEFAULT_WEEKLY_LIMIT = economy.TRANSFER_WEEKLY_DAILY_LIMIT              # what the setting is before any test changes it


def setUpModule():
    users.PBKDF2_ROUNDS = 1000


def tearDownModule():
    users.PBKDF2_ROUNDS = _ROUNDS
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def wbody(to, amount, account="weekly", **kw):
    return {**body(to, amount, **kw), "account": account}


class Base(unittest.TestCase):
    def setUp(self):
        fresh_store()
        mailer.QUIET = True
        inbox.PENDING.clear()
        patch = mock.patch.object(economy, "TRANSFER_WEEKLY_DAILY_LIMIT", 5000.0)    # the daily limit has its own tests below; the rest should not run into it
        patch.start()
        self.addCleanup(patch.stop)
        self.ann = mk("ann", weekly=800, accum=1000)
        self.ben = mk("ben", weekly=300, accum=50)
        self.cat = mk("cat", weekly=1000, accum=0)                 # already holds the whole weekly allocation
        befriend(self.ann, self.ben)
        befriend(self.ann, self.cat)
        transfers.set_password(self.ann, LOGIN, PW)

    def send(self, to, amount, account="weekly", **kw):
        return transfers.send(self.ann, wbody(to, amount, account, **kw), NOW)

    def everything(self):
        return sum(ledger.to_cents(u[f]) for u in (self.ann, self.ben, self.cat) for f in ("balance", "accum"))


class ChoosingTheAccount(Base):
    def test_weekly_to_weekly(self):
        before = self.everything()
        r = self.send(self.ben, 200)
        self.assertEqual((r["receipt"]["account"], r["receipt"]["fromAccount"], r["receipt"]["toAccount"], r["receipt"]["amount"]), ("weekly", "weekly", "weekly", 200.0))
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (600.0, 500.0))
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0), "the accumulated accounts were not touched")
        self.assertEqual(self.everything(), before, "money is conserved")
        self.assertEqual(r["receipt"]["senderBalanceAfter"], 600.0)
        self.assertTrue(books_balance(self.ann) and books_balance(self.ben))

    def test_accumulated_to_accumulated_still_works_and_is_what_you_get_when_you_do_not_say(self):
        r = transfers.send(self.ann, body(self.ben, 100), NOW)
        self.assertEqual((r["receipt"]["account"], self.ann["accum"], self.ben["accum"]), ("accumulated", 900.0, 150.0))
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (800.0, 300.0))
        r = self.send(self.ben, 50, "accumulated")
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (850.0, 200.0))

    def test_the_two_are_separate_what_you_pick_is_what_moves(self):
        self.send(self.ben, 100, "accumulated")
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (800.0, 300.0))
        self.send(self.ben, 100, "weekly")
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (700.0, 400.0))
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (900.0, 150.0))

    def test_there_is_no_way_to_cross_from_one_account_to_the_other(self):
        for extra in ({"toAccount": "accumulated"}, {"to_account": "accumulated"}, {"into": "accumulated"}, {"convert": True}):
            transfers.send(self.ann, {**wbody(self.ben, 10), **extra}, NOW)
        self.assertEqual(self.ben["accum"], 50.0, "weekly money only ever lands in the weekly account")
        self.assertEqual(self.ben["balance"], 340.0)
        for account in ("both", "", None, ["weekly"], 7, "Weekly ", "savings"):
            e = err(transfers.send, self.ann, {**wbody(self.ben, 10), "account": account}, NOW)
            self.assertEqual(e.status, 400, repr(account))
        self.assertEqual((self.ann["balance"], self.ann["accum"]), (760.0, 1000.0), "only the four good ones moved anything")

    def test_both_legs_are_written_in_the_ledger_under_the_chosen_account(self):
        r = self.send(self.ben, 120)["receipt"]
        out = [x for x in ledger.entries(self.ann) if x["reason"] == "transfer.out"][0]
        inn = [x for x in ledger.entries(self.ben) if x["reason"] == "transfer.in"][0]
        self.assertEqual((out["account"], out["amount"], out["external"], out["ref"]), ("weekly", -120.0, True, r["id"]))
        self.assertEqual((inn["account"], inn["amount"], inn["external"], inn["ref"]), ("weekly", 120.0, True, r["id"]))

    def test_the_review_names_the_account_and_the_rule_and_moves_nothing(self):
        p = transfers.preview(self.ann, wbody(self.ben, 150), NOW)
        self.assertEqual((p["account"], p["fromAccount"], p["toAccount"], p["fromLabel"], p["senderBalanceAfter"]), ("weekly", "weekly", "weekly", "Weekly account", 650.0))
        self.assertIn("reset every Monday", p["rule"])
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (800.0, 300.0))
        self.assertEqual(transfers.view(self.ann, NOW)["accounts"]["weekly"]["limit"]["sent"], 0.0)

    def test_the_same_request_id_cannot_be_replayed_for_the_other_account(self):
        request = rid()
        transfers.send(self.ann, wbody(self.ben, 60, request_id=request), NOW)
        again = transfers.send(self.ann, wbody(self.ben, 60, request_id=request), NOW)
        self.assertTrue(again["duplicate"])
        self.assertEqual(self.ann["balance"], 740.0, "a retry sent once")
        e = err(transfers.send, self.ann, wbody(self.ben, 60, "accumulated", request_id=request), NOW)
        self.assertEqual(e.status, 409)
        self.assertEqual((self.ann["balance"], self.ann["accum"]), (740.0, 1000.0))

    def test_the_receiver_is_told_which_account_it_landed_in_and_both_histories_say_so(self):
        inbox.PENDING.clear()
        self.send(self.ben, 40, note="chips for you")
        note = self.ben["inbox"][0]
        self.assertIn("weekly account", note["text"])
        self.assertEqual(note["data"]["account"], "weekly")
        sent = transfers.view(self.ann, NOW)["history"][0]
        got = transfers.view(self.ben, NOW)["history"][0]
        self.assertEqual((sent["account"], sent["dir"], got["account"], got["dir"]), ("weekly", "out", "weekly", "in"))
        self.assertEqual(db()["transfers"][sent["id"]]["account"], "weekly")

    def test_the_page_describes_both_accounts(self):
        v = transfers.view(self.ann, NOW)
        self.assertEqual(set(v["accounts"]), {"weekly", "accumulated"})
        w, a = v["accounts"]["weekly"], v["accounts"]["accumulated"]
        self.assertEqual((w["balance"], w["sendable"], w["enabled"], a["balance"], a["sendable"]), (800.0, 800.0, True, 1000.0, 1000.0))
        self.assertEqual((v["balance"], v["limit"]["daily"]), (1000.0, 250.0), "and what there was before the choice is still there")

    def test_the_old_history_without_an_account_reads_as_accumulated(self):
        transfers.send(self.ann, body(self.ben, 10), NOW)
        for h in self.ann["xfer"]["log"]:
            h.pop("acct", None)
        self.assertEqual(transfers.view(self.ann, NOW)["history"][0]["account"], "accumulated")


class WeeklyChipsAndTheLeaderboard(Base):
    def test_sending_or_receiving_chips_changes_nobodys_weekly_result(self):
        c = circle_of(self.ann, self.ben)
        before = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}
        values_before = {r["user"]["username"]: r["value"] for r in weekly.standings(c, week_key())}
        self.send(self.ben, 250)
        after = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}
        values_after = {r["user"]["username"]: r["value"] for r in weekly.standings(c, week_key())}
        self.assertEqual(before, after, "the transfer is an outside credit on both sides")
        self.assertEqual((values_after["ann"], values_after["ben"]), (values_before["ann"] - 250, values_before["ben"] + 250), "what they hold did move")
        self.assertEqual((self.ann["wk"]["ext_c"], self.ben["wk"]["ext_c"]), (-25000, 25000))

    def test_chips_that_arrive_are_not_winnings_and_chips_that_leave_are_not_losses(self):
        c = circle_of(self.ann, self.ben)
        transfers.set_password(self.ben, LOGIN, "ben-xfer-pw")
        for i in range(4):                                         # back and forth
            self.send(self.ben, 100)
            transfers.send(self.ben, wbody(self.ann, 100, password="ben-xfer-pw"), NOW)
        rows = {r["user"]["username"]: r["delta"] for r in weekly.standings(c, week_key())}
        self.assertEqual(rows, {"ann": 0.0, "ben": 0.0})
        self.assertEqual(self.ann["balance"], 800.0)

    def test_it_earns_no_xp_no_challenge_progress_and_no_milestone(self):
        goals = {u["id"]: copy.deepcopy(progress.state(u)) for u in (self.ann, self.ben)}
        stats = {u["id"]: copy.deepcopy(u["stats"]) for u in (self.ann, self.ben)}
        for _ in range(3):
            self.send(self.ben, 20)
        for u in (self.ann, self.ben):
            self.assertEqual(progress.state(u), goals[u["id"]])
            self.assertEqual(u["stats"], stats[u["id"]], "and not a gambling result either")

    def test_the_chips_are_ordinary_weekly_chips_and_reset_with_the_week(self):
        prev = prev_week_key(week_key())
        self.send(self.ben, 200)                                   # ben: 500
        for u in (self.ann, self.ben, self.cat):
            u["wk"]["week"] = prev
        db()["meta"]["week"] = prev
        weekly.tick()
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (1000.0, 1000.0), "both are back at the allocation")
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0), "and nothing went to the accumulated accounts")
        self.assertTrue(books_balance(self.ann) and books_balance(self.ben))


class WhoCanReceiveChips(Base):
    def test_a_friend_can_only_be_topped_up_to_the_weekly_allocation(self):
        e = err(transfers.send, self.ann, wbody(self.ben, 750), NOW)       # ben holds 300: room for 700
        self.assertEqual(e.status, 403)
        self.assertIn("top a friend up", e.message)
        self.assertIn("$700.00", e.message)
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (800.0, 300.0))
        self.send(self.ben, 700)
        self.assertEqual(self.ben["balance"], 1000.0)
        e = err(transfers.send, self.ann, wbody(self.ben, 1), NOW)
        self.assertIn("already holds the whole weekly allocation", e.message)

    def test_somebody_who_already_has_the_allocation_gets_nothing(self):
        e = err(transfers.send, self.ann, wbody(self.cat, 5), NOW)
        self.assertEqual(e.status, 403)
        self.assertEqual(self.cat["balance"], 1000.0)

    def test_what_a_friend_has_riding_on_polls_counts_as_held(self):
        maker = mk("maker")
        m = markets.create(maker, {"scope": "site", "question": "Does it count as held?"})
        markets.trade(self.ben, m, {"outcome": 0, "amount": 200})        # cash 100, a position worth about 200
        room = transfers.receiver_room_c(self.ben, "weekly")
        self.assertAlmostEqual(room / 100, 1000 - 300, delta=1.0)
        self.assertEqual(err(transfers.send, self.ann, wbody(self.ben, 750), NOW).status, 403)

    def test_the_limit_is_a_setting_and_can_be_switched_off(self):
        with mock.patch.object(economy, "TRANSFER_WEEKLY_RECEIVER_PCT", 150.0):
            self.send(self.ben, 800)
            self.assertEqual(self.ben["balance"], 1100.0)
            self.assertEqual(err(transfers.send, self.ann, wbody(self.cat, 1), NOW).status, 400, "ann has nothing left to send")
        with mock.patch.object(economy, "TRANSFER_WEEKLY_RECEIVER_PCT", 0):
            self.assertGreater(transfers.receiver_room_c(self.cat, "weekly"), 10 ** 12)

    def test_the_accumulated_account_has_no_such_limit(self):
        self.send(self.ben, 200, "accumulated")
        self.assertEqual(self.ben["accum"], 250.0)
        self.assertGreater(transfers.receiver_room_c(self.ben, "accumulated"), 10 ** 12, "only the ceiling every account has")


class WhatChipsCanBeSent(Base):
    def test_borrowed_money_is_never_passed_on_what_you_owe_stays_with_you(self):
        ledger.post(self.ann, "weekly", -500, "test.setup")                  # ann holds 300
        loans.borrow(self.ann, 200, now=NOW)                                 # 500 in the account, 200 of it owed
        self.assertEqual((self.ann["balance"], loans.owed(self.ann)), (500.0, 200.0))
        self.assertEqual(transfers.sendable_c(self.ann, "weekly"), 30000)
        e = err(transfers.send, self.ann, wbody(self.ben, 301), NOW)
        self.assertIn("you owe on a loan", e.message)
        self.assertIn("$300.00 can be sent", e.message)
        self.send(self.ben, 300)
        self.assertEqual((self.ann["balance"], loans.owed(self.ann)), (200.0, 200.0), "exactly the debt is left")
        self.assertEqual(err(transfers.send, self.ann, wbody(self.ben, 1), NOW).status, 400)

    def test_somebody_with_no_loan_can_send_all_the_cash(self):
        self.send(self.ben, 700)
        self.assertEqual(self.ann["balance"], 100.0)

    def test_money_riding_on_a_bet_or_a_round_is_not_cash(self):
        games.hilo_start(self.ann, {"amount": 300})                           # 300 is now on the table
        self.assertEqual(self.ann["balance"], 500.0)
        e = err(transfers.send, self.ann, wbody(self.ben, 600), NOW)
        self.assertIn("not cash", e.message)
        self.assertEqual(err(transfers.send, self.ann, wbody(self.ben, 501), NOW).status, 400)
        self.send(self.ben, 500)

    def test_the_loan_itself_is_not_changed_by_chips_moving_around(self):
        ledger.post(self.ann, "weekly", -500, "test.setup")
        loans.borrow(self.ann, 200, now=NOW)
        loan = copy.deepcopy(db()["loans"][self.ann["loanId"]])
        self.send(self.ben, 100)
        self.assertEqual(db()["loans"][self.ann["loanId"]], loan)

    def test_the_defaults_are_the_documented_ones(self):
        self.assertEqual((economy.TRANSFER_DAILY_LIMIT, DEFAULT_WEEKLY_LIMIT, economy.TRANSFER_WEEKLY_RECEIVER_PCT), (250.0, 500.0, 100.0))
        self.assertEqual(economy.TRANSFER_ACCOUNTS, ("weekly", "accumulated"))

    def test_daily_limits_belong_to_each_account_separately(self):
        with mock.patch.object(economy, "TRANSFER_WEEKLY_DAILY_LIMIT", DEFAULT_WEEKLY_LIMIT):
            a = transfers.view(self.ann, NOW)["accounts"]
            self.assertEqual((a["weekly"]["limit"]["daily"], a["accumulated"]["limit"]["daily"]), (500.0, 250.0))
            self.send(self.ben, 250, "accumulated")
            e = err(transfers.send, self.ann, wbody(self.ben, 1, "accumulated"), NOW)
            self.assertIn("daily limit for the accumulated account", e.message)
            self.send(self.ben, 100, "weekly")                                # the weekly allowance is untouched
            a = transfers.view(self.ann, NOW)["accounts"]
            self.assertEqual((a["accumulated"]["limit"]["remaining"], a["weekly"]["limit"]["remaining"]), (0.0, 400.0))
            self.assertEqual((a["accumulated"]["limit"]["sent"], a["weekly"]["limit"]["sent"]), (250.0, 100.0))
            self.assertEqual(err(transfers.send, self.ann, wbody(self.ben, 401), NOW).status, 403)

    def test_the_weekly_limit_follows_its_own_setting_and_the_same_day_boundaries(self):
        with mock.patch.object(economy, "TRANSFER_WEEKLY_DAILY_LIMIT", 40.0):
            self.send(self.ben, 40)
            e = err(transfers.send, self.ann, wbody(self.ben, 1), NOW)
            self.assertIn("daily limit for the weekly account", e.message)
            edge = next_day_start_ms(NOW)
            self.assertEqual(err(transfers.send, self.ann, wbody(self.ben, 1), edge - 1).status, 403)
            transfers.send(self.ann, wbody(self.ben, 5), edge)
            self.assertEqual(transfers.view(self.ann, edge)["accounts"]["weekly"]["limit"]["sent"], 5.0)

    def test_receiving_gives_no_allowance_back_in_either_account(self):
        transfers.set_password(self.ben, LOGIN, "ben-xfer-pw")
        with mock.patch.object(economy, "TRANSFER_WEEKLY_DAILY_LIMIT", 250.0):
            self.send(self.ben, 250)
            transfers.send(self.ben, wbody(self.ann, 50, password="ben-xfer-pw"), NOW)
            self.assertEqual(transfers.view(self.ann, NOW)["accounts"]["weekly"]["limit"]["remaining"], 0.0)

    def test_the_allowance_survives_a_restart(self):
        self.send(self.ben, 100)
        store.save()
        store.load()
        ann = users.get(self.ann["id"])
        self.assertEqual(transfers.view(ann, NOW)["accounts"]["weekly"]["limit"]["sent"], 100.0)

    def test_two_at_once_cannot_slip_past_the_weekly_limit(self):
        results = []

        def go():
            with LOCK:
                try:
                    transfers.send(self.ann, wbody(self.ben, 100), NOW)
                    results.append("sent")
                except ApiError as e:
                    results.append(e.status)
        with mock.patch.object(economy, "TRANSFER_WEEKLY_DAILY_LIMIT", 250.0):
            threads = [threading.Thread(target=go) for _ in range(8)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            self.assertEqual(results.count("sent"), 2, results)
            self.assertEqual(transfers.view(self.ann, NOW)["accounts"]["weekly"]["limit"]["sent"], 200.0)

    def test_an_account_can_be_switched_off(self):
        with mock.patch.object(economy, "TRANSFER_ACCOUNTS", ("accumulated",)):
            e = err(transfers.send, self.ann, wbody(self.ben, 10), NOW)
            self.assertEqual(e.status, 403)
            self.assertIn("switched off", e.message)
            self.assertFalse(transfers.view(self.ann, NOW)["accounts"]["weekly"]["enabled"])
            transfers.send(self.ann, wbody(self.ben, 10, "accumulated"), NOW)
        with mock.patch.object(economy, "TRANSFER_ACCOUNTS", ("weekly",)):
            self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403, "and not choosing now means accumulated, which is off")

    def test_a_failure_halfway_puts_back_everything_including_the_weekly_result_bookkeeping(self):
        real = ledger.post
        calls = {"n": 0}

        def second_fails(user, account, *a, **kw):
            if kw.get("txid", "").startswith("xfer:"):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RuntimeError("the second leg failed")
            return real(user, account, *a, **kw)
        ann_before, ben_before = copy.deepcopy(self.ann), copy.deepcopy(self.ben)
        with mock.patch.object(ledger, "post", second_fails):
            with self.assertRaises(RuntimeError):
                transfers.send(self.ann, wbody(self.ben, 90), NOW)
        self.assertEqual(self.ann, ann_before)
        self.assertEqual(self.ben, ben_before)
        self.assertEqual((self.ann["wk"]["ext_c"], self.ben["wk"]["ext_c"]), (0, 0))
        self.assertEqual(transfers.view(self.ann, NOW)["accounts"]["weekly"]["limit"]["sent"], 0.0)
        self.assertEqual(db().get("transfers", {}), {})


class ThroughTheServer(unittest.TestCase):
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

    def person(self, name):
        c = Client(self.port)
        self.assertEqual(c.call("POST", "/api/auth/register", {"username": name, "password": LOGIN})[0], 200)
        u = users.by_username(name)
        u["createdAt"] -= 5 * DAY_MS
        return c, u

    def test_choosing_the_account_over_http(self):
        a, ua = self.person("httpsend")
        b, ub = self.person("httpget")
        ledger.post(ub, "weekly", -600, "test.setup")                        # httpget holds 400 chips
        ledger.post(ua, "accumulated", 300, "test.setup")
        a.call("POST", "/api/transfers/password", {"loginPassword": LOGIN, "newPassword": PW})
        self.assertEqual(a.call("POST", "/api/friends/request", {"username": "httpget"})[0], 200)
        self.assertEqual(b.call("POST", "/api/friends/accept", {"userId": ua["id"]})[0], 200)
        tv = a.call("GET", "/api/transfers")[1]
        self.assertEqual((tv["accounts"]["weekly"]["balance"], tv["accounts"]["accumulated"]["balance"]), (1000.0, 300.0))
        st, p = a.call("POST", "/api/transfers/preview", {"to": ub["id"], "amount": 150, "account": "weekly"})
        self.assertEqual((st, p["account"], p["senderBalanceAfter"], p["fromLabel"]), (200, "weekly", 850.0, "Weekly account"))
        send = {"to": ub["id"], "amount": 150, "account": "weekly", "password": PW, "confirm": True, "requestId": "weekly-http-0001"}
        st, d = a.call("POST", "/api/transfers", send)
        self.assertEqual((st, d["receipt"]["account"], d["receipt"]["amount"], d["user"]["weekly"], d["user"]["accum"]), (200, "weekly", 150.0, 850.0, 300.0), d)
        self.assertEqual((ua["balance"], ub["balance"], ua["accum"], ub["accum"]), (850.0, 550.0, 300.0, 0.0))
        st, again = a.call("POST", "/api/transfers", send)
        self.assertEqual((st, again["duplicate"], ua["balance"]), (200, True, 850.0))
        st, d = a.call("POST", "/api/transfers", {**send, "requestId": "weekly-http-0002", "amount": 400})        # over what is left of today's weekly allowance (500)
        self.assertEqual(st, 403)
        self.assertIn("daily limit for the weekly account", d["error"])
        st, d = a.call("POST", "/api/transfers", {**send, "requestId": "weekly-http-0003", "account": "elsewhere"})
        self.assertEqual(st, 400)
        got = b.call("GET", "/api/transfers")[1]["history"][0]
        self.assertEqual((got["dir"], got["account"], got["amount"]), ("in", "weekly", 150.0))
        self.assertEqual(ledger.audit(ua), {"weekly": 0, "accumulated": 0})
        self.assertEqual(ledger.audit(ub), {"weekly": 0, "accumulated": 0})


if __name__ == "__main__":
    unittest.main()
