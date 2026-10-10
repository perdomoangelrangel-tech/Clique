"""Friend-to-friend transfers: who may send to whom, the transfer password and its lock-out, the daily limit, atomic and safe to retry,
conservation of money, and the guarantee that moving money around earns nothing."""
import copy
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

from backend import challenges, circles, economy, inbox, ledger, loans, mailer, milestones, progress, recovery, social, transfers, users, weekly   # noqa: E402
from backend.store import LOCK, db, store                                                                                                           # noqa: E402
from backend.util import ApiError, DAY_MS, day_key, next_day_start_ms, week_bounds, week_key                                                        # noqa: E402
from tests.econ import books_balance, circle_of, mk                                                                                                 # noqa: E402
from tests.helpers import fresh_store, restore_store_path                                                                                           # noqa: E402

HOUR = 3_600_000
START, END = week_bounds(week_key())
NOW = START + 2 * DAY_MS + 12 * HOUR
PW = "xfer-secret-1"
LOGIN = "secret123"


_ROUNDS = users.PBKDF2_ROUNDS


def setUpModule():
    users.PBKDF2_ROUNDS = 1000                 # the same hashing, fewer rounds: these tests hash hundreds of passwords


def tearDownModule():
    users.PBKDF2_ROUNDS = _ROUNDS
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def befriend(a, b):
    social.request(a, b["username"])
    social.accept(b, a["id"])


_rid = [0]


def rid():
    _rid[0] += 1
    return f"request-{_rid[0]:06d}"


def body(to, amount, password=PW, note="", request_id=None, confirm=True):
    return {"to": to["id"], "amount": amount, "password": password, "note": note, "requestId": request_id or rid(), "confirm": confirm}


class Base(unittest.TestCase):
    def setUp(self):
        fresh_store()
        mailer.QUIET = True
        mailer.RECENT.clear()
        inbox.PENDING.clear()
        self.ann = mk("ann", accum=1000)
        self.ben = mk("ben", accum=50)
        self.cat = mk("cat", accum=0)
        befriend(self.ann, self.ben)
        befriend(self.ann, self.cat)
        transfers.set_password(self.ann, LOGIN, PW)

    def send(self, to, amount, **kw):
        return transfers.send(self.ann, body(to, amount, **kw), NOW)

    def total(self):
        return sum(ledger.to_cents(u["accum"]) + ledger.to_cents(u["balance"]) for u in (self.ann, self.ben, self.cat))


class WhoCanReceive(Base):
    def test_an_accepted_mutual_friend_can(self):
        r = self.send(self.ben, 25)
        self.assertEqual((r["receipt"]["amount"], r["receipt"]["status"]), (25.0, "completed"))

    def test_a_pending_request_is_not_friendship(self):
        dan = mk("dan", accum=0)
        social.request(self.ann, dan["username"])                  # asked, not answered
        e = err(transfers.send, self.ann, body(dan, 10), NOW)
        self.assertEqual(e.status, 403)
        self.assertIn("added", e.message)
        self.assertEqual(self.ann["accum"], 1000.0)
        social.accept(dan, self.ann["id"])                         # once they say yes, it is a friendship and it works
        self.assertEqual(transfers.send(self.ann, body(dan, 10), NOW)["receipt"]["amount"], 10.0)

    def test_the_other_person_having_asked_you_is_not_friendship_either(self):
        eve = mk("eve", accum=0)
        social.request(eve, self.ann["username"])
        self.assertEqual(err(transfers.send, self.ann, body(eve, 10), NOW).status, 403)

    def test_sharing_a_circle_is_not_friendship(self):
        fay = mk("fay", accum=0)
        circle_of(self.ann, fay)
        self.assertIn(fay["id"], social.friend_ids(self.ann["id"]), "the friends list does include circle-mates...")
        self.assertEqual(err(transfers.send, self.ann, body(fay, 10), NOW).status, 403, "...but money only goes to friends who added each other")
        self.assertFalse(transfers.are_friends(self.ann["id"], fay["id"]))
        self.assertNotIn(fay["id"], [f["id"] for f in transfers.friends(self.ann)])

    def test_a_friendship_that_ended_cannot_receive(self):
        social.remove(self.ben, self.ann["id"])
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403)
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0))

    def test_removing_the_friend_between_the_review_and_the_send_stops_it(self):
        prev = transfers.preview(self.ann, {"to": self.ben["id"], "amount": 40}, NOW)
        self.assertEqual(prev["amount"], 40.0)
        social.remove(self.ann, self.ben["id"])                    # while the confirmation window was open
        e = err(transfers.send, self.ann, body(self.ben, 40), NOW)
        self.assertEqual(e.status, 403)
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0))
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["sent"], 0.0, "and no allowance was used")

    def test_you_cannot_send_to_yourself(self):
        e = err(transfers.send, self.ann, body(self.ann, 10), NOW)
        self.assertIn("yourself", e.message)

    def test_people_who_do_not_exist_or_cannot_receive_are_refused(self):
        self.assertEqual(err(transfers.send, self.ann, {**body(self.ben, 10), "to": "nobody-here"}, NOW).status, 404)
        self.assertEqual(err(transfers.send, self.ann, {**body(self.ben, 10), "to": None}, NOW).status, 400)
        self.ben["suspended"] = True
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403)
        self.ben.pop("suspended")
        self.ben["deleted"] = True
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403)
        self.ben.pop("deleted")
        self.ann["suspended"] = True
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403, "a suspended sender cannot send either")
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0))

    def test_only_added_friends_are_offered_in_the_list(self):
        names = [f["username"] for f in transfers.friends(self.ann)]
        self.assertEqual(names, ["ben", "cat"])


class ThePassword(Base):
    def setUp(self):
        super().setUp()
        self.bob = mk("bobby", accum=500)
        befriend(self.bob, self.ben)

    def test_without_one_nothing_can_be_sent(self):
        self.assertFalse(transfers.has_password(self.bob))
        e = err(transfers.send, self.bob, body(self.ben, 10), NOW)
        self.assertEqual(e.status, 403)
        self.assertIn("Choose a transfer password", e.message)
        self.assertEqual(self.bob["accum"], 500.0)

    def test_setting_it_needs_the_login_password(self):
        e = err(transfers.set_password, self.bob, "wrong-login", PW, now=NOW)
        self.assertEqual(e.status, 403)
        self.assertFalse(transfers.has_password(self.bob))
        self.assertEqual(transfers.set_password(self.bob, LOGIN, PW, now=NOW), "set")
        self.assertTrue(transfers.has_password(self.bob))

    def test_it_cannot_be_the_login_password_or_too_weak(self):
        self.assertIn("different from your login", err(transfers.set_password, self.bob, LOGIN, LOGIN).message)
        self.assertIn("at least 6", err(transfers.set_password, self.bob, LOGIN, "abc").message)
        self.assertIn("at least 6", err(transfers.set_password, self.bob, LOGIN, None).message)
        self.assertIn("too long", err(transfers.set_password, self.bob, LOGIN, "x" * 201).message)
        self.assertFalse(transfers.has_password(self.bob), "no default one is ever made")

    def test_every_single_transfer_asks_for_it_even_while_logged_in(self):
        for pw in (None, "", "wrong-one", 12345):                    # (a fifth wrong one would lock transfers: see the lock-out test)
            e = err(transfers.send, self.ann, body(self.ben, 10, password=pw), NOW)
            self.assertEqual(e.status, 403)
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0))
        transfers.send(self.ann, body(self.ben, 10), NOW)
        err(transfers.send, self.ann, body(self.ben, 10, password=None), NOW)          # the second one needs it again
        self.assertEqual(self.ann["accum"], 990.0)

    def test_the_login_password_is_not_accepted_as_the_transfer_password(self):
        e = err(transfers.send, self.ann, body(self.ben, 10, password=LOGIN), NOW)
        self.assertEqual(e.status, 403)

    def test_changing_it_needs_the_old_one_and_the_login_password(self):
        self.assertEqual(err(transfers.set_password, self.ann, LOGIN, "brand-new-pw", now=NOW).status, 400)       # no way to name neither current nor code
        self.assertEqual(err(transfers.set_password, self.ann, LOGIN, "brand-new-pw", current_password="nope", now=NOW).status, 403)
        self.assertEqual(err(transfers.set_password, self.ann, "bad-login", "brand-new-pw", current_password=PW, now=NOW).status, 403)
        self.assertEqual(transfers.set_password(self.ann, LOGIN, "brand-new-pw", current_password=PW, now=NOW), "changed")
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403, "the old one is dead")
        transfers.send(self.ann, body(self.ben, 10, password="brand-new-pw"), NOW)

    def confirmed_email(self, u, addr="ann@example.com"):
        u["mail"] = {"addr": addr, "verified": True}

    def test_a_forgotten_one_is_reset_with_the_login_password_and_a_code_sent_to_the_confirmed_email(self):
        e = err(transfers.request_reset_code, self.ann, LOGIN)
        self.assertEqual(e.status, 403)
        self.assertIn("confirmed email", e.message)
        self.confirmed_email(self.ann)
        self.assertEqual(err(transfers.request_reset_code, self.ann, "wrong-login").status, 403)
        addr, code = transfers.request_reset_code(self.ann, LOGIN)
        self.assertEqual(addr, "ann@example.com")
        self.assertRegex(code, r"^\d{6}$")
        self.assertEqual(err(transfers.set_password, self.ann, LOGIN, "after-reset-pw", code="000000", now=NOW).status, 403)
        self.assertEqual(err(transfers.set_password, self.ann, "bad-login", "after-reset-pw", code=code, now=NOW).status, 403)
        self.assertEqual(transfers.set_password(self.ann, LOGIN, "after-reset-pw", code=code, now=NOW), "reset")
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 10), NOW).status, 403)
        transfers.send(self.ann, body(self.ben, 10, password="after-reset-pw"), NOW)
        self.assertEqual(err(transfers.set_password, self.ann, LOGIN, "again-again-pw", code=code, now=NOW).status, 403, "a code works once")

    def test_a_site_that_cannot_send_email_says_so_instead_of_pretending(self):
        self.confirmed_email(self.ann)
        with mock.patch.object(mailer, "delivery_on", return_value=False):
            e = err(transfers.request_reset_code, self.ann, LOGIN)
        self.assertEqual(e.status, 503)
        self.assertIn("not switched on", e.message)
        self.assertNotIn("codes", self.ann["xfer"], "and no code was made")

    def test_a_code_expires_and_dies_after_too_many_wrong_guesses(self):
        self.confirmed_email(self.ann)
        _, code = transfers.request_reset_code(self.ann, LOGIN)
        with mock.patch.object(recovery.time, "time", return_value=time.time() + 3600):
            self.assertEqual(err(transfers.set_password, self.ann, LOGIN, "after-reset-pw", code=code, now=NOW).status, 403)
        _, code = transfers.request_reset_code(self.ann, LOGIN)
        for _ in range(recovery.MAX_TRIES):
            err(transfers.set_password, self.ann, LOGIN, "after-reset-pw", code="999999" if code != "999999" else "111111", now=NOW)
        self.assertEqual(err(transfers.set_password, self.ann, LOGIN, "after-reset-pw", code=code, now=NOW).status, 403, "the right code too, once it has been used up")

    def test_there_is_no_way_to_reset_it_without_the_account_password(self):
        self.confirmed_email(self.ann)
        for args in ({"login_password": None}, {"login_password": ""}, {"login_password": "nope"}):
            self.assertEqual(err(transfers.set_password, self.ann, args["login_password"], "new-secret-1", code="123456", now=NOW).status, 403)
            self.assertEqual(err(transfers.request_reset_code, self.ann, args["login_password"]).status, 403)
        self.assertTrue(transfers.has_password(self.ann))
        transfers.send(self.ann, body(self.ben, 10), NOW)           # the old one still works: nothing was changed

    def test_five_wrong_tries_lock_transfers_for_a_while_and_say_so(self):
        for i in range(4):
            e = err(transfers.send, self.ann, body(self.ben, 10, password=f"wrong-{i}"), NOW)
            self.assertEqual(e.status, 403)
            self.assertIn(f"{4 - i} more tr", e.message)
        e = err(transfers.send, self.ann, body(self.ben, 10, password="wrong-5"), NOW)
        self.assertEqual(e.status, 429)
        self.assertIn("locked", e.message)
        self.assertGreater(e.data["retryAfter"], 0)
        e = err(transfers.send, self.ann, body(self.ben, 10, password=PW), NOW + 1000)
        self.assertEqual(e.status, 429, "even the right password is refused while locked")
        self.assertIsNotNone(transfers.view(self.ann, NOW + 1000)["locked"])
        self.assertEqual(self.ann["accum"], 1000.0)
        later = NOW + int(economy.TRANSFER_PW_LOCK_MIN * 60_000) + 1000
        transfers.send(self.ann, body(self.ben, 10), later)
        self.assertIsNone(transfers.view(self.ann, later)["locked"])

    def test_a_right_password_clears_the_count_of_wrong_ones(self):
        for _ in range(4):
            err(transfers.send, self.ann, body(self.ben, 10, password="nope-nope"), NOW)
        transfers.send(self.ann, body(self.ben, 10), NOW)
        for _ in range(4):
            err(transfers.send, self.ann, body(self.ben, 10, password="nope-nope"), NOW)       # four more is still not a lock
        transfers.send(self.ann, body(self.ben, 10), NOW)
        self.assertEqual(self.ann["accum"], 980.0)

    def test_the_lock_and_the_count_survive_a_restart_and_a_new_session(self):
        for _ in range(5):
            try:
                transfers.send(self.ann, body(self.ben, 10, password="nope-nope"), NOW)
            except ApiError:
                pass
        store.save()
        store.load()
        ann = users.get(self.ann["id"])
        users._attempts.clear()
        e = err(transfers.send, ann, body(self.ben, 10), NOW + 1000)
        self.assertEqual(e.status, 429)
        users.make_session(ann["id"])                              # logging in again does not help
        self.assertEqual(err(transfers.send, ann, body(self.ben, 10), NOW + 2000).status, 429)

    def test_it_is_stored_only_as_a_salted_hash_and_never_shown_or_written_anywhere(self):
        transfers.send(self.ann, body(self.ben, 10, note="thanks!"), NOW)
        blob = json.dumps(db())
        self.assertNotIn(PW, blob, "not in the saved data at all")
        self.assertNotIn(PW, json.dumps(transfers.view(self.ann, NOW)))
        pw = self.ann["xfer"]["pw"]
        self.assertEqual(set(pw), {"salt", "hash", "setAt"})
        self.assertNotEqual(pw["hash"], self.ann["hash"], "not the login hash")
        self.assertEqual(pw["hash"], users._hash(PW, pw["salt"]), "made with the same hashing as login passwords")
        other = mk("zed", accum=0)
        transfers.set_password(other, LOGIN, PW)
        self.assertNotEqual(other["xfer"]["pw"]["salt"], pw["salt"])
        self.assertNotEqual(other["xfer"]["pw"]["hash"], pw["hash"], "the same password gets a different hash")
        for text in (json.dumps(ledger.entries(self.ann)), json.dumps(self.ann["activity"]), json.dumps(self.ben.get("inbox", []))):
            self.assertNotIn(PW, text)


class TheDailyLimit(Base):
    def test_it_is_a_documented_default(self):
        self.assertEqual(economy.TRANSFER_DAILY_LIMIT, 250.0)
        lim = transfers.view(self.ann, NOW)["limit"]
        self.assertEqual((lim["daily"], lim["sent"], lim["remaining"]), (250.0, 0.0, 250.0))
        self.assertEqual(lim["resetsAt"], next_day_start_ms(NOW))

    def test_it_counts_everything_sent_to_everybody_that_day(self):
        self.send(self.ben, 100)
        self.send(self.cat, 100)
        lim = transfers.view(self.ann, NOW)["limit"]
        self.assertEqual((lim["sent"], lim["remaining"]), (200.0, 50.0))
        e = err(transfers.send, self.ann, body(self.ben, 60), NOW)
        self.assertEqual(e.status, 403)
        self.assertIn("daily limit", e.message)
        self.assertIn("$50.00", e.message)
        self.send(self.cat, 50)
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 1), NOW).status, 403)
        self.assertEqual(self.ann["accum"], 750.0)

    def test_a_refused_transfer_does_not_use_any_of_it(self):
        for kw in ({"amount": 99999}, {"amount": 0}, {"amount": 10, "password": "wrong-pw"}):
            err(transfers.send, self.ann, body(self.ben, **kw), NOW)
        social.remove(self.ann, self.cat["id"])
        err(transfers.send, self.ann, body(self.cat, 10), NOW)
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["sent"], 0.0)

    def test_receiving_money_does_not_give_the_sender_back_any(self):
        self.send(self.ben, 250)
        transfers.set_password(self.ben, LOGIN, "ben-xfer-pw")
        transfers.send(self.ben, body(self.ann, 40, password="ben-xfer-pw"), NOW)
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["remaining"], 0.0, "ann received 40 but her allowance did not grow")
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 1), NOW).status, 403)

    def test_the_day_is_the_calendar_day_in_the_site_time_zone(self):
        self.send(self.ben, 250)
        edge = next_day_start_ms(NOW)
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 1), edge - 1).status, 403, "the last millisecond of the day")
        transfers.send(self.ann, body(self.ben, 100), edge)                                       # the first of the next
        lim = transfers.view(self.ann, edge)["limit"]
        self.assertEqual((lim["sent"], lim["remaining"], lim["resetsAt"]), (100.0, 150.0, next_day_start_ms(edge)))
        self.assertNotEqual(day_key(edge - 1), day_key(edge))

    def test_it_is_not_reset_by_restarting_logging_in_again_or_changing_friends(self):
        self.send(self.ben, 200)
        store.save()
        store.load()
        ann = users.get(self.ann["id"])
        users.make_session(ann["id"])
        dan = mk("dan", accum=0)
        befriend(ann, dan)
        social.remove(ann, self.ben["id"])
        befriend(ann, users.get(self.ben["id"]))
        self.assertEqual(transfers.view(ann, NOW)["limit"]["remaining"], 50.0)
        self.assertEqual(err(transfers.send, ann, body(dan, 60), NOW).status, 403)

    def test_two_at_once_cannot_slip_past_it(self):
        results = []

        def go(to):
            with LOCK:
                try:
                    transfers.send(self.ann, body(to, 100), NOW)
                    results.append("sent")
                except ApiError as e:
                    results.append(e.status)
        threads = [threading.Thread(target=go, args=(self.ben if i % 2 else self.cat,)) for i in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((results.count("sent"), results.count(403)), (2, 6))
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["sent"], 200.0)
        self.assertEqual(self.ann["accum"], 800.0)

    def test_the_limit_is_a_setting(self):
        with mock.patch.object(economy, "TRANSFER_DAILY_LIMIT", 20.0):
            self.send(self.ben, 20)
            self.assertEqual(err(transfers.send, self.ann, body(self.ben, 1), NOW).status, 403)


class WhatCanBeSent(Base):
    def test_amounts_are_checked_on_the_server(self):
        for bad_amount in (0, -5, "abc", None, float("nan"), float("inf"), 10.005, 0.5, "", True, [], {}):
            e = err(transfers.send, self.ann, body(self.ben, bad_amount), NOW)
            self.assertIn(e.status, (400, 403), bad_amount)
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0))
        self.assertEqual(self.send(self.ben, "12.50")["receipt"]["amount"], 12.5)
        self.assertEqual(self.send(self.ben, 0.1 + 0.2 + 0.7)["receipt"]["amount"], 1.0, "floating-point dust is not a reason to refuse")

    def test_only_cash_in_the_accumulated_account_can_go(self):
        poor = mk("poorly", weekly=1000, accum=100)
        befriend(poor, self.ben)
        transfers.set_password(poor, LOGIN, PW)
        e = err(transfers.send, poor, body(self.ben, 150), NOW)
        self.assertIn("accumulated account has $100.00", e.message)
        self.assertEqual((poor["balance"], poor["accum"]), (1000.0, 100.0), "the weekly chips are not an alternative")

    def test_shares_and_other_holdings_are_not_cash(self):
        from backend import exchange
        poor = mk("holder", weekly=1000, accum=100)
        poor.setdefault("positions", {})["NEXO"] = {"sh": 500, "cost_c": 500000, "real_c": 0}
        befriend(poor, self.ben)
        transfers.set_password(poor, LOGIN, PW)
        self.assertEqual(err(transfers.send, poor, body(self.ben, 101), NOW).status, 400)
        transfers.send(poor, body(self.ben, 100), NOW)
        self.assertEqual(poor["accum"], 0.0)

    def test_borrowed_money_can_never_be_sent(self):
        borrower = mk("borrower", weekly=300, accum=0)
        befriend(borrower, self.ben)
        transfers.set_password(borrower, LOGIN, PW)
        loans.borrow(borrower, 200, now=NOW)
        self.assertEqual(borrower["balance"], 500.0)
        e = err(transfers.send, borrower, body(self.ben, 10), NOW)
        self.assertIn("accumulated account has $0.00", e.message)
        self.assertEqual(self.ben["accum"], 50.0)

    def test_a_sender_in_debt_can_still_send_what_is_theirs(self):
        borrower = mk("indebted", weekly=300, accum=100)
        befriend(borrower, self.ben)
        transfers.set_password(borrower, LOGIN, PW)
        loans.borrow(borrower, 200, now=NOW)
        transfers.send(borrower, body(self.ben, 60), NOW)
        self.assertEqual((borrower["accum"], loans.owed(borrower)), (40.0, 200.0), "the loan is repaid from the weekly account only: nothing changes there")

    def test_the_note_is_short_plain_text(self):
        self.assertEqual(self.send(self.ben, 5, note="  lunch   money  ")["receipt"]["note"], "lunch money")
        self.assertIn("at most 80", err(transfers.send, self.ann, body(self.ben, 5, note="x" * 81), NOW).message)
        self.assertIn("must be text", err(transfers.send, self.ann, body(self.ben, 5, note=["x"]), NOW).message)

    def test_it_needs_an_explicit_confirmation_and_a_request_id(self):
        self.assertIn("Confirm", err(transfers.send, self.ann, body(self.ben, 5, confirm=False), NOW).message)
        self.assertIn("Confirm", err(transfers.send, self.ann, {**body(self.ben, 5), "confirm": "yes"}, NOW).message)
        self.assertIn("request id", err(transfers.send, self.ann, {**body(self.ben, 5), "requestId": None}, NOW).message)
        self.assertIn("Invalid request id", err(transfers.send, self.ann, {**body(self.ben, 5), "requestId": "x"}, NOW).message)
        self.assertEqual(self.ann["accum"], 1000.0)

    def test_it_can_be_switched_off(self):
        with mock.patch.object(economy, "TRANSFERS_ENABLED", False):
            self.assertEqual(err(transfers.send, self.ann, body(self.ben, 5), NOW).status, 403)
            self.assertFalse(transfers.view(self.ann, NOW)["enabled"])

    def test_an_account_that_would_overflow_cannot_receive(self):
        self.ben["accum"] = 1e18
        self.assertEqual(err(transfers.send, self.ann, body(self.ben, 5), NOW).status, 403)
        self.assertEqual(self.ann["accum"], 1000.0)

    def test_no_fee_and_the_review_says_so(self):
        p = transfers.preview(self.ann, {"to": self.ben["id"], "amount": 30, "note": "hi"}, NOW)
        self.assertEqual((p["fee"], p["fromAccount"], p["toAccount"]), (0.0, "accumulated", "accumulated"))
        self.assertEqual(p["fromLabel"], "Accumulated account")


class ThePreview(Base):
    def test_it_shows_who_what_which_accounts_and_what_will_be_left(self):
        p = transfers.preview(self.ann, {"to": self.ben["id"], "amount": 70, "note": "hello"}, NOW)
        self.assertEqual((p["to"]["username"], p["amount"], p["note"]), ("ben", 70.0, "hello"))
        self.assertEqual((p["senderBalanceAfter"], p["dailyLimit"], p["sentToday"], p["remainingAfter"]), (930.0, 250.0, 0.0, 180.0))
        self.assertEqual(p["resetsAt"], next_day_start_ms(NOW))

    def test_it_moves_nothing_and_uses_no_allowance_and_needs_no_password_attempt(self):
        for _ in range(10):
            transfers.preview(self.ann, {"to": self.ben["id"], "amount": 70}, NOW)
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (1000.0, 50.0))
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["sent"], 0.0)
        self.assertEqual(self.ann["xfer"]["fails"], 0)
        self.assertEqual(db().get("transfers", {}), {})

    def test_it_refuses_what_the_send_would_refuse(self):
        self.assertEqual(err(transfers.preview, self.ann, {"to": self.ben["id"], "amount": 999}, NOW).status, 403)
        self.assertEqual(err(transfers.preview, self.ann, {"to": self.ann["id"], "amount": 5}, NOW).status, 400)


class SafeAndWhole(Base):
    def test_one_transfer_is_one_debit_one_credit_and_money_is_conserved(self):
        before = self.total()
        r = self.send(self.ben, 120.55)
        self.assertEqual(self.total(), before)
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (879.45, 170.55))
        self.assertEqual((self.ann["balance"], self.ben["balance"]), (1000.0, 1000.0), "the weekly accounts are never touched")
        out = [x for x in ledger.entries(self.ann) if x["reason"] == "transfer.out"]
        inn = [x for x in ledger.entries(self.ben) if x["reason"] == "transfer.in"]
        self.assertEqual([(x["account"], x["amount"], x["ref"]) for x in out], [("accumulated", -120.55, r["receipt"]["id"])])
        self.assertEqual([(x["account"], x["amount"], x["ref"]) for x in inn], [("accumulated", 120.55, r["receipt"]["id"])])
        self.assertTrue(out[0]["note"].endswith("ben") and "ann" in inn[0]["note"])
        self.assertTrue(books_balance(self.ann) and books_balance(self.ben))

    def test_a_failure_halfway_leaves_everything_exactly_as_it_was(self):
        real = ledger.post
        calls = {"n": 0}

        def second_leg_fails(user, account, *a, **kw):
            if kw.get("txid", "").startswith("xfer:"):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RuntimeError("the second leg failed")
            return real(user, account, *a, **kw)
        ann_before, ben_before = copy.deepcopy(self.ann), copy.deepcopy(self.ben)
        rows_before = (len(db()["ledger"][self.ann["id"]]), len(db()["ledger"][self.ben["id"]]))
        request = rid()
        with mock.patch.object(ledger, "post", second_leg_fails):
            with self.assertRaises(RuntimeError):
                transfers.send(self.ann, body(self.ben, 80, request_id=request), NOW)
        self.assertEqual(self.ann, ann_before)
        self.assertEqual(self.ben, ben_before)
        self.assertEqual((len(db()["ledger"][self.ann["id"]]), len(db()["ledger"][self.ben["id"]])), rows_before)
        self.assertEqual(db().get("transfers", {}), {})
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["sent"], 0.0, "the allowance was not used")
        transfers.send(self.ann, body(self.ben, 80, request_id=request), NOW)             # the retry goes through
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (920.0, 130.0))

    def test_a_double_click_or_a_retry_sends_once(self):
        request = rid()
        a = transfers.send(self.ann, body(self.ben, 60, request_id=request), NOW)
        b = transfers.send(self.ann, body(self.ben, 60, request_id=request), NOW)
        self.assertEqual((a["duplicate"], b["duplicate"]), (False, True))
        self.assertEqual(a["receipt"]["id"], b["receipt"]["id"])
        self.assertEqual((self.ann["accum"], self.ben["accum"]), (940.0, 110.0))
        self.assertEqual(transfers.view(self.ann, NOW)["limit"]["sent"], 60.0)
        self.assertEqual(len([x for x in ledger.entries(self.ann) if x["reason"] == "transfer.out"]), 1)

    def test_the_retry_after_a_restart_is_still_recognised(self):
        request = rid()
        transfers.send(self.ann, body(self.ben, 60, request_id=request), NOW)
        store.save()
        store.load()
        ann = users.get(self.ann["id"])
        again = transfers.send(ann, body(self.ben, 60, request_id=request), NOW)
        self.assertTrue(again["duplicate"])
        self.assertEqual(users.get(self.ann["id"])["accum"], 940.0)

    def test_the_same_request_id_for_a_different_transfer_is_refused(self):
        request = rid()
        transfers.send(self.ann, body(self.ben, 60, request_id=request), NOW)
        e = err(transfers.send, self.ann, body(self.ben, 61, request_id=request), NOW)
        self.assertEqual(e.status, 409)
        self.assertEqual(self.ann["accum"], 940.0)

    def test_the_receipt_says_what_happened(self):
        r = self.send(self.ben, 33, note="for the pizza")["receipt"]
        self.assertEqual((r["status"], r["amount"], r["fee"], r["note"]), ("completed", 33.0, 0.0, "for the pizza"))
        self.assertEqual((r["to"]["username"], r["from"]["username"], r["fromAccount"], r["toAccount"]), ("ben", "ann", "accumulated", "accumulated"))
        self.assertEqual((r["senderBalanceAfter"], r["remainingToday"]), (967.0, 217.0))
        self.assertTrue(r["id"] and r["t"] == NOW)

    def test_both_people_see_it_in_their_history_and_the_recipient_is_told(self):
        inbox.PENDING.clear()
        r = self.send(self.ben, 33, note="pizza")["receipt"]
        sent = transfers.view(self.ann, NOW)["history"]
        got = transfers.view(self.ben, NOW)["history"]
        self.assertEqual([(h["dir"], h["amount"], h["peer"]["username"], h["note"]) for h in sent], [("out", 33.0, "ben", "pizza")])
        self.assertEqual([(h["dir"], h["amount"], h["peer"]["username"], h["note"]) for h in got], [("in", 33.0, "ann", "pizza")])
        self.assertEqual(sent[0]["id"], got[0]["id"])
        note = self.ben["inbox"][0]
        self.assertEqual(note["kind"], "transfer")
        self.assertIn("ann sent you $33.00", note["title"])
        events = inbox.drain()
        self.assertEqual([(e["userId"], e["item"]["kind"]) for e in events], [(self.ben["id"], "transfer")], "only the recipient is told, once")
        self.assertEqual(self.ann.get("inbox", []), [])

    def test_a_refused_transfer_does_not_notify_anyone(self):
        inbox.PENDING.clear()
        err(transfers.send, self.ann, body(self.ben, 99999), NOW)
        self.assertEqual(inbox.drain(), [])
        self.assertEqual(self.ben.get("inbox", []), [])


class EarnsNothing(Base):
    def test_sending_and_receiving_gives_no_xp_no_progress_and_no_leaderboard_gain(self):
        c = circle_of(self.ann, self.ben)
        transfers.set_password(self.ben, LOGIN, "ben-xfer-pw")
        goals = {u["id"]: copy.deepcopy(progress.state(u)) for u in (self.ann, self.ben)}
        rows_before = {r["user"]["username"]: (r["value"], r["delta"]) for r in weekly.standings(c, week_key())}
        stats_before = {u["id"]: copy.deepcopy(u["stats"]) for u in (self.ann, self.ben)}
        for i in range(6):                                                                  # back and forth, again and again
            transfers.send(self.ann, body(self.ben, 20), NOW + i)
            transfers.send(self.ben, body(self.ann, 20, password="ben-xfer-pw"), NOW + i)
        for u in (self.ann, self.ben):
            self.assertEqual(progress.state(u), goals[u["id"]], "no XP, no counter, no challenge fact, no milestone")
            self.assertEqual(u["stats"], stats_before[u["id"]])
            self.assertEqual(progress.xp_of(u), 0)
        self.assertEqual({r["user"]["username"]: (r["value"], r["delta"]) for r in weekly.standings(c, week_key())}, rows_before)
        self.assertEqual(milestones.view(self.ann)["totals"]["claimed"], 0)

    def test_the_progression_code_is_never_called_by_a_transfer(self):
        with mock.patch("backend.activity.record") as rec, mock.patch("backend.activity.safe_record") as safe, mock.patch("backend.progress.grant") as grant:
            self.send(self.ben, 10)
        safe.assert_not_called()
        rec.assert_not_called()
        grant.assert_not_called()

    def test_reciprocal_transfers_cannot_be_used_to_farm_anything(self):
        transfers.set_password(self.ben, LOGIN, "ben-xfer-pw")
        before = (ledger.to_cents(self.ann["accum"]) + ledger.to_cents(self.ben["accum"]))
        for i in range(10):
            try:
                transfers.send(self.ann, body(self.ben, 25), NOW)
            except ApiError:
                pass
            try:
                transfers.send(self.ben, body(self.ann, 25, password="ben-xfer-pw"), NOW)
            except ApiError:
                pass
        self.assertEqual(ledger.to_cents(self.ann["accum"]) + ledger.to_cents(self.ben["accum"]), before, "money only moved, never appeared")
        self.assertEqual((progress.xp_of(self.ann), progress.xp_of(self.ben)), (0, 0))


if __name__ == "__main__":
    unittest.main()
