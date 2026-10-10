"""Forgot a password: the funds password lets the site's owner set a new one, and nothing else does."""
import os
import sys
import tempfile
import threading
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                              # noqa: E402
from backend import config, users                          # noqa: E402
from backend.store import db                               # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402
from tests.test_http import Client                         # noqa: E402


def tearDownModule():
    restore_store_path()


def code_of(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e.status
    return None


class ResetPassword(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.ann = users.register("ann_x", "old-password")
        self.bob = users.register("bob_x", "bobs-password")

    def reset(self, name="ann_x", new="brand-new-pw", funds=None, ip="1.1.1.1"):
        return users.reset_password(name, new, config.ADMIN_PASSWORD if funds is None else funds, ip)

    def test_the_funds_password_sets_a_new_password_and_the_old_one_stops_working(self):
        self.reset()
        self.assertEqual(users.login("ann_x", "brand-new-pw")["id"], self.ann["id"])
        self.assertEqual(code_of(users.login, "ann_x", "old-password"), 401)

    def test_the_new_password_is_stored_scrambled_like_any_other(self):
        self.reset(new="plain-text-check")
        self.assertNotIn("plain-text-check", str(db()["users"][self.ann["id"]]))
        self.assertEqual(len(db()["users"][self.ann["id"]]["hash"]), 64)

    def test_a_wrong_funds_password_changes_nothing(self):
        self.assertEqual(code_of(self.reset, funds="not-the-funds-password"), 403)
        self.assertEqual(users.login("ann_x", "old-password")["id"], self.ann["id"])

    def test_the_funds_password_is_checked_before_anything_is_revealed(self):
        self.assertEqual(code_of(self.reset, name="nobody_here", funds="wrong"), 403)       # a stranger learns nothing about usernames
        self.assertEqual(code_of(self.reset, name="nobody_here"), 404)                      # the owner is told

    def test_the_new_password_follows_the_same_rules_as_sign_up(self):
        self.assertEqual(code_of(self.reset, new="short"), 400)
        self.assertEqual(code_of(self.reset, new="x" * 201), 400)
        self.assertEqual(code_of(self.reset, new=12345678), 400)
        self.assertEqual(users.login("ann_x", "old-password")["id"], self.ann["id"])

    def test_other_accounts_are_untouched(self):
        self.reset()
        self.assertEqual(users.login("bob_x", "bobs-password")["id"], self.bob["id"])

    def test_usernames_are_not_case_sensitive_here_either(self):
        self.reset(name="ANN_X")
        self.assertEqual(users.login("ann_x", "brand-new-pw")["id"], self.ann["id"])

    def test_every_open_log_in_on_that_account_ends(self):
        mine, hers = users.make_session(self.ann["id"]), users.make_session(self.bob["id"])
        self.reset()
        self.assertIsNone(users.user_for_token(mine))
        self.assertEqual(users.user_for_token(hers)["id"], self.bob["id"])

    def test_a_lock_out_from_wrong_guesses_ends_with_the_reset(self):
        for i in range(15):                                                                 # many addresses, one account: the per-account lock
            self.assertEqual(code_of(users.login, "ann_x", "wrong-guess", f"9.9.9.{i}"), 401)
        self.assertEqual(code_of(users.login, "ann_x", "old-password", "9.9.8.8"), 429)
        self.reset()
        self.assertEqual(users.login("ann_x", "brand-new-pw", "8.8.8.8")["id"], self.ann["id"])

    def test_guessing_the_funds_password_is_rate_limited(self):
        for _ in range(10):
            self.assertEqual(code_of(self.reset, funds="guess"), 403)
        self.assertEqual(code_of(self.reset, funds="guess"), 429)
        self.assertEqual(code_of(self.reset), 429)                                         # even the right one waits
        self.assertEqual(users.login("ann_x", "old-password")["id"], self.ann["id"])

    def test_the_guessing_budget_is_shared_with_the_add_funds_box(self):
        for i in range(20):                                                                 # different people, different addresses
            self.assertEqual(code_of(self.reset, funds="guess", ip=f"10.0.0.{i}"), 403)
        self.assertEqual(code_of(self.reset, ip="10.0.9.9"), 429)
        self.assertEqual(code_of(users.deposit, self.bob, 5, config.ADMIN_PASSWORD), 429)   # and add-funds is shut too


class OverHttp(unittest.TestCase):
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

    def test_forgot_my_password_end_to_end(self):
        users._attempts.clear()
        c = Client(self.port)
        self.assertEqual(c.call("POST", "/api/auth/register", {"username": "forgetful", "password": "first-password"})[0], 200)
        c.call("POST", "/api/auth/logout", {})
        anon = Client(self.port)                                                            # no log-in needed to ask
        st, d = anon.call("POST", "/api/auth/reset", {"username": "forgetful", "fundsPassword": "nope", "newPassword": "second-password"})
        self.assertEqual((st, d["error"]), (403, "Wrong funds password"))
        st, d = anon.call("POST", "/api/auth/reset", {"username": "forgetful", "fundsPassword": config.ADMIN_PASSWORD, "newPassword": "second-password"})
        self.assertEqual((st, d), (200, {"ok": True, "username": "forgetful"}))
        self.assertEqual(anon.call("POST", "/api/auth/login", {"username": "forgetful", "password": "first-password"})[0], 401)
        st, d = anon.call("POST", "/api/auth/login", {"username": "forgetful", "password": "second-password"})
        self.assertEqual((st, d["user"]["username"]), (200, "forgetful"))
        self.assertNotIn("second-password", str(d))                                        # nothing about passwords comes back


if __name__ == "__main__":
    unittest.main()
