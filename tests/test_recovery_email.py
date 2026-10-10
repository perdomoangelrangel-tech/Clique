"""Email addresses, confirming them, and resetting a forgotten password with a code sent to one."""
import io
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                           # noqa: E402
from backend import config, mailer, recovery, users                    # noqa: E402
from backend.store import db, store                                    # noqa: E402
from backend.util import ApiError                                      # noqa: E402
from tests.helpers import fresh_store, restore_store_path              # noqa: E402
from tests.test_http import Client                                     # noqa: E402


def setUpModule():
    mailer.QUIET = True


def tearDownModule():
    mailer.QUIET = False
    restore_store_path()


def code_in(message):
    return re.search(r"\b(\d{6})\b", message["text"]).group(1)


def last_mail():
    return mailer.RECENT[-1]


# ---------------------------------------------------------------------------------------------------------------------
class Addresses(unittest.TestCase):
    def test_what_counts_as_an_email_address(self):
        for good in ("a@b.co", "  Emi.Raven+clique@Example.COM ", "x_y-z@mail.example.org"):
            self.assertRegex(recovery.normalize_email(good), r"^[^A-Z\s]+@[^A-Z\s]+$")
        self.assertEqual(recovery.normalize_email("  Emi@Example.COM "), "emi@example.com")
        for bad in ("", "   ", "nope", "a@b", "a@@b.com", "a b@c.com", "a@b..com", "@b.com", "a@.com", "a" * 80 + "@b.com", None, 5, ["a@b.com"]):
            with self.assertRaises(ApiError, msg=repr(bad)):
                recovery.normalize_email(bad)

    def test_masking_hides_most_of_somebody_elses_address(self):
        self.assertEqual(mailer.mask("emi@example.com"), "e***@example.com")
        self.assertEqual(mailer.mask("weird"), "***")


# ---------------------------------------------------------------------------------------------------------------------
class FakeService(BaseHTTPRequestHandler):
    seen = []
    answer = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        FakeService.seen.append({"path": self.path, "headers": dict(self.headers), "json": json.loads(body)})
        self.send_response(FakeService.answer)
        self.end_headers()
        self.wfile.write(b'{"id":"x"}' if FakeService.answer < 300 else b'{"message":"nope"}')

    def log_message(self, *a):
        pass


class Sending(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeService)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        FakeService.seen.clear()
        FakeService.answer = 200
        mailer.RECENT.clear()
        self.cfg = mock.patch.multiple(config, EMAIL_FROM="Clique <hello@example.com>", RESEND_API_KEY="", BREVO_API_KEY="", SMTP_HOST="",
                                       RESEND_URL=self.url + "/resend", BREVO_URL=self.url + "/brevo", PRODUCTION=False)
        self.cfg.start()

    def tearDown(self):
        self.cfg.stop()

    def test_which_service_is_used_follows_the_settings(self):
        self.assertIsNone(mailer.provider())
        with mock.patch.object(config, "SMTP_HOST", "smtp.example.com"):
            self.assertEqual(mailer.provider(), "smtp")
            with mock.patch.object(config, "BREVO_API_KEY", "b"):
                self.assertEqual(mailer.provider(), "brevo")
                with mock.patch.object(config, "RESEND_API_KEY", "r"):
                    self.assertEqual(mailer.provider(), "resend")
        with mock.patch.object(config, "RESEND_API_KEY", "r"), mock.patch.object(config, "EMAIL_FROM", ""):
            self.assertIsNone(mailer.provider(), "without a from address nothing can be sent")

    def test_resend_gets_the_request_it_documents(self):
        with mock.patch.object(config, "RESEND_API_KEY", "re_key"):
            mailer.send("friend@example.com", "Subject here", "Body here")
        (r,) = FakeService.seen
        self.assertEqual(r["path"], "/resend")
        self.assertEqual(r["headers"]["Authorization"], "Bearer re_key")
        self.assertTrue(r["headers"]["User-Agent"].startswith("clique"))
        self.assertEqual(r["json"], {"from": "Clique <hello@example.com>", "to": ["friend@example.com"], "subject": "Subject here", "text": "Body here"})

    def test_brevo_gets_the_request_it_documents(self):
        with mock.patch.object(config, "BREVO_API_KEY", "br_key"):
            mailer.send("friend@example.com", "S", "T")
        (r,) = FakeService.seen
        self.assertEqual((r["path"], {k.lower(): v for k, v in r["headers"].items()}["api-key"]), ("/brevo", "br_key"))
        self.assertEqual(r["json"], {"sender": {"name": "Clique", "email": "hello@example.com"}, "to": [{"email": "friend@example.com"}], "subject": "S", "textContent": "T"})

    def test_smtp_logs_in_and_uses_starttls_by_default(self):
        smtp = mock.MagicMock()
        smtp.__enter__.return_value = smtp
        with mock.patch.multiple(config, SMTP_HOST="smtp.example.com", SMTP_PORT=587, SMTP_USER="u", SMTP_PASSWORD="p", SMTP_SECURITY="starttls"), \
                mock.patch("backend.mailer.smtplib.SMTP", return_value=smtp) as ctor:
            mailer.send("friend@example.com", "S", "T")
        ctor.assert_called_once()
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("u", "p")
        sent = smtp.send_message.call_args[0][0]
        self.assertEqual((sent["To"], sent["Subject"], sent["From"]), ("friend@example.com", "S", "Clique <hello@example.com>"))
        self.assertEqual(sent.get_content().strip(), "T")

    def test_smtp_over_ssl_does_not_also_start_tls(self):
        smtp = mock.MagicMock()
        smtp.__enter__.return_value = smtp
        with mock.patch.multiple(config, SMTP_HOST="smtp.example.com", SMTP_PORT=465, SMTP_USER="", SMTP_PASSWORD="", SMTP_SECURITY="ssl"), \
                mock.patch("backend.mailer.smtplib.SMTP_SSL", return_value=smtp) as ctor:
            mailer.send("friend@example.com", "S", "T")
        ctor.assert_called_once()
        smtp.starttls.assert_not_called()
        smtp.login.assert_not_called()

    def test_a_refusal_or_an_unreachable_service_is_an_error_not_silence(self):
        FakeService.answer = 403
        with mock.patch.object(config, "RESEND_API_KEY", "k"), self.assertRaises(mailer.MailError) as cm:
            mailer.send("a@b.co", "S", "T")
        self.assertIn("403", str(cm.exception))
        with mock.patch.multiple(config, RESEND_API_KEY="k", RESEND_URL="http://127.0.0.1:9/never"), self.assertRaises(mailer.MailError):
            mailer.send("a@b.co", "S", "T")

    def test_a_hosted_copy_with_no_service_cannot_send_and_says_so(self):
        with mock.patch.object(config, "PRODUCTION", True):
            self.assertFalse(mailer.delivery_on())
            with self.assertRaises(mailer.MailError):
                mailer.send("a@b.co", "S", "T")
        self.assertTrue(mailer.delivery_on(), "on your own computer it shows the message instead")

    def test_on_your_own_computer_the_message_is_shown_in_the_terminal_not_sent(self):
        buf = io.StringIO()
        with redirect_stderr(buf), mock.patch.object(mailer, "QUIET", False):
            mailer.send("a@b.co", "Hello", "Code 123456")
        self.assertEqual(mailer.RECENT[-1]["to"], "a@b.co")
        self.assertIn("Code 123456", buf.getvalue())
        self.assertEqual(FakeService.seen, [])

    def test_sending_in_the_background_never_raises_and_never_logs_the_message(self):
        FakeService.answer = 500
        buf = io.StringIO()
        with mock.patch.object(config, "RESEND_API_KEY", "k"), redirect_stderr(buf):
            mailer.send_async("somebody@example.com", "S", "secret code 424242").join(5)
        out = buf.getvalue()
        self.assertIn("s***@example.com", out)
        self.assertNotIn("424242", out)
        self.assertNotIn("somebody@", out)


# ---------------------------------------------------------------------------------------------------------------------
class OverHttp(unittest.TestCase):
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

    def setUp(self):
        users._attempts.clear()
        mailer.RECENT.clear()
        self.n = getattr(OverHttp, "_n", 0) + 1
        OverHttp._n = self.n

    def client(self):
        return Client(self.port)

    def signup(self, name=None, email="auto", required=True):
        name = name or f"user{self.n}x{len(db()['users'])}"
        c = self.client()
        body = {"username": name, "password": "secret123"}
        if email == "auto":
            email = f"{name}@example.com"
        if email is not None:
            body["email"] = email
        with mock.patch.object(config, "EMAIL_REQUIRED", required):
            st, d = c.call("POST", "/api/auth/register", body)
        return c, st, d, name

    def confirmed(self, name=None):
        c, st, d, name = self.signup(name)
        self.assertEqual(st, 200, d)
        st, d = c.call("POST", "/api/me/email/verify", {"code": code_in(last_mail())})
        self.assertEqual(st, 200, d)
        return c, name

    # ---- signing up ------------------------------------------------------------------------------------------
    def test_a_new_account_must_give_an_email(self):
        c, st, d, name = self.signup(email=None)
        self.assertEqual(st, 400)
        self.assertIn("email", d["error"].lower())
        self.assertNotIn(name.lower(), db()["usernames"], "and no account is made without one")

    def test_a_blank_or_malformed_email_is_refused_before_any_account_is_made(self):
        for bad in ("", "   ", "nope", "a@b"):
            c, st, d, name = self.signup(email=bad)
            self.assertEqual(st, 400, bad)
            self.assertNotIn(name.lower(), db()["usernames"])

    def test_with_an_email_the_account_is_made_and_a_code_is_sent_to_confirm_it(self):
        c, st, d, name = self.signup(email="Fresh.Face@Example.com")
        self.assertEqual(st, 200)
        self.assertEqual(d["user"]["email"], {"address": "fresh.face@example.com", "verified": False, "pending": None, "needed": False, "delivery": True, "preview": True})
        self.assertEqual(last_mail()["to"], "fresh.face@example.com")
        self.assertRegex(last_mail()["text"], r"\b\d{6}\b")

    def test_the_rule_can_be_switched_off_but_a_given_email_is_still_checked(self):
        c, st, d, name = self.signup(email=None, required=False)
        self.assertEqual(st, 200)
        self.assertTrue(d["user"]["email"]["needed"])
        c, st, d, name = self.signup(email="garbage", required=False)
        self.assertEqual(st, 400)

    def test_an_address_confirmed_on_one_account_cannot_be_used_to_make_another(self):
        mine, name = self.confirmed()
        taken = db()["users"][db()["usernames"][name.lower()]]["mail"]["addr"]
        c, st, d, other = self.signup(email=taken)
        self.assertEqual(st, 409)
        self.assertNotIn(other.lower(), db()["usernames"])

    def test_an_address_that_was_only_typed_in_does_not_block_anybody(self):
        c1, st1, d1, n1 = self.signup(email="shared@example.com")
        c2, st2, d2, n2 = self.signup(email="shared@example.com")
        self.assertEqual((st1, st2), (200, 200))
        st, d = c1.call("POST", "/api/me/email/verify", {"code": code_in(mailer.RECENT[-2])})
        self.assertEqual(st, 200)
        st, d = c2.call("POST", "/api/me/email/verify", {"code": code_in(mailer.RECENT[-1])})
        self.assertEqual(st, 409, "the first to confirm owns it")

    # ---- people who already had an account ---------------------------------------------------------------------
    def test_an_existing_account_with_no_email_is_marked_as_needing_one(self):
        c = self.client()
        users.register("oldtimer", "secret123")                    # made before emails existed
        st, d = c.call("POST", "/api/auth/login", {"username": "oldtimer", "password": "secret123"})
        self.assertEqual(st, 200)
        self.assertTrue(d["user"]["email"]["needed"])
        self.assertIsNone(d["user"]["email"]["address"])
        st, d = c.call("GET", "/api/me")
        self.assertTrue(d["user"]["email"]["needed"])

    def test_adding_the_first_email_needs_no_password_and_then_stops_asking(self):
        users.register("latecomer", "secret123")
        c = self.client()
        c.call("POST", "/api/auth/login", {"username": "latecomer", "password": "secret123"})
        st, d = c.call("POST", "/api/me/email", {"email": "late@example.com"})
        self.assertEqual(st, 200, d)
        self.assertFalse(d["email"]["needed"])
        self.assertFalse(d["email"]["verified"])
        st, d = c.call("POST", "/api/me/email/verify", {"code": code_in(last_mail())})
        self.assertEqual((st, d["email"]["verified"]), (200, True))

    def test_you_must_be_logged_in_to_change_your_email(self):
        c = self.client()
        for path in ("/api/me/email", "/api/me/email/verify", "/api/me/email/resend"):
            self.assertEqual(c.call("POST", path, {"email": "a@b.co", "code": "123456"})[0], 401)

    # ---- confirming ----------------------------------------------------------------------------------------------
    def test_a_wrong_code_does_not_confirm_and_five_wrong_tries_kill_the_code(self):
        c, st, d, name = self.signup()
        real = code_in(last_mail())
        wrong = "000000" if real != "000000" else "111111"
        for _ in range(4):
            self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": wrong})[0], 400)
        self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": wrong})[0], 400)       # the fifth
        self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": real})[0], 400, "even the right one is dead now")
        self.assertFalse(c.call("GET", "/api/me")[1]["user"]["email"]["verified"])

    def test_a_code_expires(self):
        c, st, d, name = self.signup()
        real = code_in(last_mail())
        import time as _t
        with mock.patch("backend.recovery.time.time", return_value=_t.time() + recovery.VERIFY_TTL_S + 5):
            self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": real})[0], 400)

    def test_a_code_works_once(self):
        c, st, d, name = self.signup()
        real = code_in(last_mail())
        self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": real})[0], 200)
        self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": real})[0], 400)

    def test_a_new_code_can_be_asked_for_but_not_in_a_flood(self):
        c, st, d, name = self.signup()
        first = code_in(last_mail())
        st, d = c.call("POST", "/api/me/email/resend")
        self.assertEqual(st, 429, "one was sent a moment ago")
        import time as _t
        with mock.patch("backend.recovery.time.time", return_value=_t.time() + recovery.RESEND_AFTER_S + 1):
            st, d = c.call("POST", "/api/me/email/resend")
        self.assertEqual(st, 200)
        second = code_in(last_mail())
        if first != second:
            self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": first})[0], 400, "the old code is replaced")
        self.assertEqual(c.call("POST", "/api/me/email/verify", {"code": second})[0], 200)

    def test_changing_a_confirmed_email_needs_the_password_and_keeps_the_old_one_until_the_new_one_works(self):
        c, name = self.confirmed()
        old = c.call("GET", "/api/me")[1]["user"]["email"]["address"]
        st, d = c.call("POST", "/api/me/email", {"email": "new.one@example.com"})
        self.assertEqual(st, 403)
        st, d = c.call("POST", "/api/me/email", {"email": "new.one@example.com", "password": "not-my-password"})
        self.assertEqual(st, 403)
        st, d = c.call("POST", "/api/me/email", {"email": "new.one@example.com", "password": "secret123"})
        self.assertEqual(st, 200, d)
        self.assertEqual((d["email"]["address"], d["email"]["verified"], d["email"]["pending"]), (old, True, "new.one@example.com"))
        st, d = c.call("POST", "/api/me/email/verify", {"code": code_in(last_mail())})
        self.assertEqual(st, 200)
        self.assertEqual((d["email"]["address"], d["email"]["verified"], d["email"]["pending"]), ("new.one@example.com", True, None))

    def test_fixing_a_typo_in_an_unconfirmed_email_just_replaces_it(self):
        c, st, d, name = self.signup(email="tpyo@example.com")
        st, d = c.call("POST", "/api/me/email", {"email": "typo@example.com"})
        self.assertEqual((st, d["email"]["address"], d["email"]["verified"]), (200, "typo@example.com", False))
        self.assertEqual(last_mail()["to"], "typo@example.com")

    # ---- forgot password -----------------------------------------------------------------------------------------
    def reset_flow(self, name=None):
        c, name = self.confirmed(name)
        addr = db()["users"][db()["usernames"][name.lower()]]["mail"]["addr"]
        anon = self.client()
        mailer.RECENT.clear()
        st, d = anon.call("POST", "/api/auth/forgot", {"email": addr})
        self.assertEqual(st, 200, d)
        return c, name, addr, anon

    def test_the_whole_reset_works_and_the_old_password_stops_working(self):
        c, name, addr, anon = self.reset_flow()
        mail = last_mail()
        self.assertEqual(mail["to"], addr)
        self.assertIn("password", mail["subject"].lower())
        self.assertEqual(c.call("GET", "/api/me")[1]["user"]["username"], name)         # logged in on one device
        st, d = anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": code_in(mail), "newPassword": "brand-new-pass"})
        self.assertEqual((st, d.get("username")), (200, name), d)
        self.assertIsNone(c.call("GET", "/api/me")[1]["user"], "every login on the account ended")
        self.assertEqual(self.client().call("POST", "/api/auth/login", {"username": name, "password": "secret123"})[0], 401)
        self.assertEqual(self.client().call("POST", "/api/auth/login", {"username": name, "password": "brand-new-pass"})[0], 200)
        self.assertIn("was changed", last_mail()["subject"], "the owner is told")
        self.assertEqual(last_mail()["to"], addr)

    def test_a_reset_code_works_once(self):
        c, name, addr, anon = self.reset_flow()
        code = code_in(last_mail())
        self.assertEqual(anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": code, "newPassword": "first-new-pass"})[0], 200)
        self.assertEqual(anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": code, "newPassword": "second-new-pass"})[0], 400)
        self.assertEqual(self.client().call("POST", "/api/auth/login", {"username": name, "password": "first-new-pass"})[0], 200)

    def test_the_answer_is_the_same_for_an_address_nobody_has(self):
        c, name, addr, anon = self.reset_flow()
        known = anon.call("POST", "/api/auth/forgot", {"email": addr})
        mailer.RECENT.clear()
        unknown = anon.call("POST", "/api/auth/forgot", {"email": "nobody.at.all@example.com"})
        self.assertEqual(known, unknown)
        self.assertEqual(mailer.RECENT, [], "and nothing is sent to a stranger")

    def test_an_address_that_was_never_confirmed_cannot_be_used_to_reset(self):
        c, st, d, name = self.signup(email="unconfirmed@example.com")
        mailer.RECENT.clear()
        st, d = self.client().call("POST", "/api/auth/forgot", {"email": "unconfirmed@example.com"})
        self.assertEqual(st, 200)
        self.assertEqual(mailer.RECENT, [])
        st, d = self.client().call("POST", "/api/auth/reset-by-email", {"email": "unconfirmed@example.com", "code": "123456", "newPassword": "whatever1"})
        self.assertEqual(st, 400)

    def test_a_wrong_code_is_refused_and_five_wrong_tries_kill_the_real_one(self):
        c, name, addr, anon = self.reset_flow()
        real = code_in(last_mail())
        wrong = "000000" if real != "000000" else "111111"
        for _ in range(5):
            st, d = anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": wrong, "newPassword": "attacker-pass"})
            self.assertEqual(st, 400)
        st, d = anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": real, "newPassword": "attacker-pass"})
        self.assertEqual(st, 400, "guessing used the code up")
        self.assertEqual(self.client().call("POST", "/api/auth/login", {"username": name, "password": "secret123"})[0], 200, "the real password still works")

    def test_every_wrong_answer_looks_alike(self):
        c, name, addr, anon = self.reset_flow()
        a = anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": "000000", "newPassword": "some-pass1"})
        b = anon.call("POST", "/api/auth/reset-by-email", {"email": "ghost@example.com", "code": "000000", "newPassword": "some-pass1"})
        c2 = anon.call("POST", "/api/auth/reset-by-email", {"email": "not an email", "code": "000000", "newPassword": "some-pass1"})
        self.assertEqual(a, b)
        self.assertEqual(a, c2)

    def test_a_too_short_new_password_is_refused_without_using_up_the_code(self):
        c, name, addr, anon = self.reset_flow()
        code = code_in(last_mail())
        self.assertEqual(anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": code, "newPassword": "123"})[0], 400)
        self.assertEqual(anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": code, "newPassword": "long-enough-1"})[0], 200)

    def test_resetting_ends_a_lockout_from_too_many_wrong_log_ins(self):
        c, name, addr, anon = self.reset_flow()
        for _ in range(16):
            self.client().call("POST", "/api/auth/login", {"username": name, "password": "wrong-wrong"})
        self.assertEqual(self.client().call("POST", "/api/auth/login", {"username": name, "password": "secret123"})[0], 429)
        self.assertIn("loginname:" + name.lower(), users._attempts)
        anon.call("POST", "/api/auth/reset-by-email", {"email": addr, "code": code_in(last_mail()), "newPassword": "after-lockout-1"})
        self.assertNotIn("loginname:" + name.lower(), users._attempts, "the lock-out on that account is lifted")
        users._attempts.pop("login:127.0.0.1", None)                       # (the separate limit on one network address is not part of this)
        self.assertEqual(self.client().call("POST", "/api/auth/login", {"username": name, "password": "after-lockout-1"})[0], 200)

    def test_one_address_cannot_be_flooded_with_codes_and_the_answer_does_not_change(self):
        c, name, addr, anon = self.reset_flow()                       # the first request is the one inside reset_flow
        answers = [anon.call("POST", "/api/auth/forgot", {"email": addr}) for _ in range(3)]
        self.assertEqual(len({json.dumps(a) for a in answers}), 1)
        self.assertEqual(len([m for m in mailer.RECENT if "password code" in m["subject"]]), 3, "three in an hour, then no more")

    def test_one_place_cannot_ask_over_and_over(self):
        anon = self.client()
        results = [anon.call("POST", "/api/auth/forgot", {"email": f"x{i}@example.com"})[0] for i in range(12)]
        self.assertEqual(results[:10], [200] * 10)
        self.assertEqual(results[10:], [429, 429])

    def test_guessing_at_the_reset_answer_from_one_place_is_limited(self):
        anon = self.client()
        results = [anon.call("POST", "/api/auth/reset-by-email", {"email": "a@b.co", "code": "000000", "newPassword": "some-pass1"})[0] for _ in range(22)]
        self.assertEqual(set(results[:20]), {400})
        self.assertEqual(results[20:], [429, 429])

    def test_a_hosted_site_with_no_email_service_says_it_cannot_do_this(self):
        with mock.patch.object(config, "PRODUCTION", True):
            st, d = self.client().call("POST", "/api/auth/forgot", {"email": "a@b.co"})
        self.assertEqual(st, 503)
        self.assertIn("not switched on", d["error"])

    def test_a_malformed_address_is_a_plain_error(self):
        self.assertEqual(self.client().call("POST", "/api/auth/forgot", {"email": "nonsense"})[0], 400)

    # ---- privacy -------------------------------------------------------------------------------------------------
    def test_nobody_else_ever_sees_an_address_or_a_code(self):
        a, name_a = self.confirmed("privateann")
        b, name_b = self.confirmed("privateben")
        addr_a = db()["users"][db()["usernames"]["privateann"]]["mail"]["addr"]
        a.call("POST", "/api/circles", {"name": "Crew"})
        seen = []
        for path in (f"/api/users/{name_a}", "/api/circles", "/api/friends", "/api/chats", "/api/markets", "/api/games/feed", "/api/week"):
            st, d = b.call("GET", path)
            seen.append(json.dumps(d))
        for blob in seen:
            self.assertNotIn(addr_a, blob)
            self.assertNotIn('"mail"', blob)
        own = json.dumps(a.call("GET", f"/api/users/{name_a}")[1])
        self.assertNotIn(addr_a, own, "not even on your own public profile")

    def test_codes_are_stored_scrambled_not_as_typed(self):
        c, name, addr, anon = self.reset_flow()
        code = code_in(last_mail())
        stored = json.dumps(db()["users"][db()["usernames"][name.lower()]]["mail"])
        self.assertNotIn(code, stored)
        self.assertIn('"h":', stored)

    def test_what_was_confirmed_survives_a_restart(self):
        c, name = self.confirmed()
        store.save()
        with open(store.path) as f:
            saved = json.load(f)
        mail = saved["users"][saved["usernames"][name.lower()]]["mail"]
        self.assertTrue(mail["verified"])


if __name__ == "__main__":
    unittest.main()
