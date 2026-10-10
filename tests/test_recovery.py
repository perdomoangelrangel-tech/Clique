"""Getting back to where you were, without trusting the browser about money.

Casino rounds live on the server, so a refresh, a second device or a long absence shows the same round, and starting another one
is refused instead of charging twice. The voice call lives in one page-long module that no screen owns, so changing screens
cannot interrupt it. (What the browser remembers about scroll, tabs, filters and drafts is checked in tests/js.)"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                    # noqa: E402
from backend.store import store                  # noqa: E402
from tests.test_http import Client               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "static", "js")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class ActiveRounds(unittest.TestCase):
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
        phone = Client(self.port)
        self.assertEqual(phone.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})[0], 200)
        laptop = Client(self.port)                                   # the same person, signed in somewhere else
        self.assertEqual(laptop.call("POST", "/api/auth/login", {"username": name, "password": "secret123"})[0], 200)
        return phone, laptop

    def balance(self, c):
        return c.call("GET", "/api/me")[1]["user"]["balance"]

    def test_a_round_started_on_one_device_is_the_same_round_on_another_and_cannot_be_started_twice(self):
        phone, laptop = self.person("roundtrip")
        starts = {"chicken": {"amount": 10, "difficulty": "medium"}, "mines": {"amount": 10, "size": 25, "mines": 3}, "moles": {"amount": 10}}
        for game, body in starts.items():
            before = self.balance(phone)
            st, d = phone.call("POST", f"/api/games/{game}/start", body)
            self.assertEqual(st, 200, (game, d))
            round_id = d["id"]
            seen = laptop.call("GET", "/api/games/state")[1][game]
            self.assertEqual(seen["id"], round_id, f"{game}: the other device sees the same round")
            self.assertEqual(seen["bet"], 10)
            st, d = laptop.call("POST", f"/api/games/{game}/start", body)
            self.assertEqual(st, 400, f"{game}: a second round is refused")
            self.assertIn("already", d["error"])
            self.assertEqual(self.balance(laptop), before - 10, f"{game}: charged once, however many tabs")
            self.assertEqual(phone.call("GET", "/api/games/state")[1][game]["id"], round_id, f"{game}: refreshing keeps the round")
            move = {"chicken": ("step", {}), "mines": ("pick", {"tile": 0}), "moles": ("pick", {"hole": 0})}[game]
            self.assertEqual(laptop.call("POST", f"/api/games/{game}/{move[0]}", move[1])[0], 200)
            if phone.call("GET", "/api/games/state")[1][game]:           # still alive after one move (it can end on a bad one)
                paid = self.balance(phone)
                self.assertEqual(laptop.call("POST", f"/api/games/{game}/cashout", {})[0], 200)
                self.assertGreater(self.balance(phone), paid)
                self.assertEqual(phone.call("POST", f"/api/games/{game}/cashout", {})[0], 400, f"{game}: cashing out twice pays once")
                self.assertEqual(self.balance(laptop), self.balance(phone))
            self.assertIsNone(laptop.call("GET", "/api/games/state")[1][game], f"{game}: finished rounds are gone")
            self.assertIsNone(phone.call("GET", "/api/games/state")[1][game])

    def test_a_blackjack_hand_is_recovered_with_the_same_cards_and_cannot_be_dealt_again(self):
        phone, laptop = self.person("dealtwice")
        before = self.balance(phone)
        st, d = phone.call("POST", "/api/games/blackjack/deal", {"amount": 10})
        self.assertEqual(st, 200, d)
        if d.get("phase") != "player":                              # a natural settles at once: nothing to recover, and nothing more charged
            self.assertIsNone(laptop.call("GET", "/api/games/state")[1]["blackjack"])
            return
        seen = laptop.call("GET", "/api/games/state")[1]["blackjack"]
        self.assertEqual(seen["id"], d["id"])
        self.assertEqual(seen["hands"][0]["cards"], d["hands"][0]["cards"])
        self.assertEqual(laptop.call("POST", "/api/games/blackjack/deal", {"amount": 10})[0], 400)
        self.assertEqual(self.balance(laptop), before - 10)

    def test_nothing_about_money_is_cached_by_the_browser_for_these_screens(self):
        phone, _ = self.person("nocache")
        for path in ("/api/games/state", "/api/me", "/api/store", "/api/week"):
            conn = __import__("http.client").client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            conn.request("GET", path, headers={"Cookie": phone.cookie})
            r = conn.getresponse(); r.read(); conn.close()
            self.assertEqual(r.status, 200, path)
            self.assertIn("no-store", r.getheader("Cache-Control") or "", path)


class VoiceLivesOutsideScreens(unittest.TestCase):
    def test_the_call_is_created_once_by_a_module_the_app_loads_at_startup(self):
        creators = []
        for base, _, files in os.walk(JS):
            for name in files:
                if name.endswith(".js") and "createVoiceCore(" in read("static", "js", os.path.relpath(os.path.join(base, name), JS)) and name != "voicecore.js":
                    creators.append(name)
        self.assertEqual(creators, ["voice.js"])
        self.assertEqual(read("static", "js", "voice.js").count("createVoiceCore("), 1)
        self.assertRegex(read("static", "js", "app.js"), r"(?m)^import \{[^}]*\} from '\./voice\.js';")

    def test_no_screen_builds_peer_connections_or_opens_the_microphone_itself(self):
        for name in os.listdir(os.path.join(JS, "views")) + ["games/hilo.js"]:
            path = os.path.join("views", name) if not name.startswith("games/") else name
            if not path.endswith(".js"):
                continue
            src = read("static", "js", path)
            self.assertNotIn("RTCPeerConnection", src, path)
            self.assertNotIn("getUserMedia", src, path)

    def test_the_dock_sits_outside_the_part_of_the_page_that_changes(self):
        html = read("static", "index.html")
        self.assertRegex(html, r'<div id="app"></div>\s*(?:<[^>]+>\s*)*<div id="voice-dock"')      # a sibling of #app, not inside it
        app = read("static", "js", "app.js")
        self.assertIn("document.createElement('main')", app)          # the router swaps only the <main> of the page...
        self.assertNotIn("getElementById('voice-dock')", app)         # ...and never reaches for the dock

    def test_logging_out_hangs_up(self):
        app = read("static", "js", "app.js")
        self.assertGreaterEqual(app.count("voice.hangUp()"), 2)         # on logout and on losing the session


class BrowserSideLogic(unittest.TestCase):
    """The voice engine and the "get back to where you were" helpers are plain modules; Node runs them against fakes."""

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed: the browser-side tests are skipped")
    def test_node_tests_pass(self):
        r = subprocess.run(["node", "--test", "tests/js/voicecore.test.mjs", "tests/js/viewstate.test.mjs"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-4000:] + r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
