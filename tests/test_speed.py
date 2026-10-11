"""Speed: how files are served (compressed, cached, preloaded) and how the database is written to disk."""
import gzip
import http.client
import json
import os
import posixpath
import re
import sys
import tempfile
import threading
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                    # noqa: E402
from backend import assets, config               # noqa: E402
from backend.store import store                  # noqa: E402
from tests.helpers import fresh_store            # noqa: E402


def slurp(path, mode="rb"):
    with open(path, mode, **({"encoding": "utf-8"} if "b" not in mode else {})) as f:
        return f.read()


def on_disk():
    return json.loads(slurp(store.path, "r"))


def fetch(port, path, headers=None, method="GET", body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body, headers or {})
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r, raw


class FilesAreServedFast(unittest.TestCase):
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

    def test_scripts_are_compressed_for_browsers_that_ask(self):
        r, raw = fetch(self.port, "/js/app.js", {"Accept-Encoding": "gzip, deflate, br"})
        self.assertEqual(r.getheader("Content-Encoding"), "gzip")
        plain = slurp(os.path.join(config.STATIC_DIR, "js", "app.js"))
        self.assertEqual(gzip.decompress(raw), plain)
        self.assertLess(len(raw), len(plain) / 2)
        self.assertIn("javascript", r.getheader("Content-Type"))

    def test_no_compression_unless_asked(self):
        r, raw = fetch(self.port, "/js/app.js")
        self.assertIsNone(r.getheader("Content-Encoding"))
        self.assertEqual(raw, slurp(os.path.join(config.STATIC_DIR, "js", "app.js")))

    def test_pictures_and_fonts_are_not_recompressed(self):
        for p in ("/casino-icons/chicken.png", "/fonts/bricolage-800.woff2"):
            r, raw = fetch(self.port, p, {"Accept-Encoding": "gzip"})
            self.assertIsNone(r.getheader("Content-Encoding"), p)
            self.assertEqual(raw, slurp(os.path.join(config.STATIC_DIR, p.lstrip("/"))))

    def test_an_unchanged_file_costs_a_304(self):
        r, _ = fetch(self.port, "/css/ui.css", {"Accept-Encoding": "gzip"})
        etag = r.getheader("ETag")
        self.assertTrue(etag)
        r2, raw2 = fetch(self.port, "/css/ui.css", {"Accept-Encoding": "gzip", "If-None-Match": etag})
        self.assertEqual((r2.status, raw2), (304, b""))
        self.assertEqual(r2.getheader("ETag"), etag)
        # a different version of the file is sent in full
        r3, raw3 = fetch(self.port, "/css/ui.css", {"Accept-Encoding": "gzip", "If-None-Match": '"stale"'})
        self.assertEqual(r3.status, 200)
        self.assertTrue(raw3)
        # the compressed and the plain copy are different representations, so their tags differ
        r4, _ = fetch(self.port, "/css/ui.css")
        self.assertNotEqual(r4.getheader("ETag"), etag)

    def test_a_connection_survives_a_304(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/css/ui.css")
        r = conn.getresponse(); r.read()
        conn.request("GET", "/css/ui.css", headers={"If-None-Match": r.getheader("ETag")})
        r = conn.getresponse(); self.assertEqual((r.status, r.read()), (304, b""))
        conn.request("GET", "/js/app.js")                                   # same connection, next file
        r = conn.getresponse(); self.assertEqual(r.status, 200); self.assertTrue(r.read())
        conn.close()

    def test_cache_rules(self):
        cc = lambda p: fetch(self.port, p)[0].getheader("Cache-Control")
        self.assertEqual(cc("/js/app.js"), "no-cache")                      # scripts: always check, so deploys show up
        self.assertEqual(cc("/css/ui.css"), "no-cache")
        self.assertEqual(cc("/"), "no-cache")
        self.assertIn("max-age=604800", cc("/fonts/bricolage-800.woff2"))
        self.assertIn("max-age=86400", cc("/casino-icons/small/dice.png"))

    def test_the_page_lists_the_scripts_it_will_need(self):
        _, raw = fetch(self.port, "/")
        html = raw.decode()
        links = re.findall(r'<link rel="modulepreload" href="([^"]+)">', html)
        self.assertIn("/js/app.js", links)
        self.assertIn("/js/views/markets.js", links)
        self.assertLess(html.index("modulepreload"), html.index("</head>"))
        for p in links:                                                     # every one of them is a real file
            self.assertTrue(os.path.isfile(os.path.join(config.STATIC_DIR, p.lstrip("/"))), p)
        # the games are loaded only when somebody opens one
        self.assertFalse([p for p in links if "/games/" in p or "pokertable" in p])

    def test_preload_follows_imports_all_the_way_down(self):
        links = assets.preload_list()
        seen = set(links)
        for p in links:
            src = slurp(os.path.join(config.STATIC_DIR, p.lstrip("/")), "r")
            for spec in re.findall(r"(?:import|export)\s[^'\";]*?from\s*['\"](\.[^'\"]+)['\"]", src):
                self.assertIn(posixpath.normpath(posixpath.join(posixpath.dirname(p), spec)), seen, f"{p} imports {spec}")

    def test_unknown_paths_still_get_the_page_and_cannot_escape_the_folder(self):
        r, raw = fetch(self.port, "/circles/abc")
        self.assertEqual(r.status, 200)
        self.assertIn(b'id="app"', raw)
        r, raw = fetch(self.port, "/../server.py")
        self.assertNotIn(b"ThreadingHTTPServer", raw)

    def test_long_api_answers_are_compressed_and_short_ones_are_not(self):
        a = fetch(self.port, "/api/auth/register", {"Content-Type": "application/json"}, "POST",
                  json.dumps({"username": "speedy", "password": "secret123"}))[0]
        cookie = a.getheader("Set-Cookie").split(";")[0]
        r, raw = fetch(self.port, "/api/me", {"Cookie": cookie, "Accept-Encoding": "gzip"})
        self.assertIsNone(r.getheader("Content-Encoding"))                  # tiny: not worth it
        self.assertEqual(json.loads(raw)["user"]["username"], "speedy")
        r, raw = fetch(self.port, "/api/games/meta", {"Cookie": cookie, "Accept-Encoding": "gzip"})
        if r.getheader("Content-Encoding") == "gzip":
            json.loads(gzip.decompress(raw))
        else:
            json.loads(raw)
        big = {"x": "abc " * 1000}
        h = server.Handler.__new__(server.Handler)
        h.headers = {"Accept-Encoding": "gzip"}
        sent = {}
        h._send = lambda status, body, ctype=None, headers=None: sent.update(body=body, headers=headers)
        h._json(200, big)
        self.assertEqual(sent["headers"]["Content-Encoding"], "gzip")
        self.assertEqual(json.loads(gzip.decompress(sent["body"])), big)


class TheDatabaseIsWrittenCarefully(unittest.TestCase):
    def setUp(self):
        fresh_store()
        store.data["meta"]["n"] = 0
        self.writes = []
        real = os.fsync
        self._real = real
        os.fsync = lambda fd: (self.writes.append(1), real(fd))[1]

    def tearDown(self):
        os.fsync = self._real

    def test_saving_what_is_already_on_disk_does_not_write_again(self):
        store.save()
        self.assertEqual(len(self.writes), 1)
        store.save()
        store.save()
        self.assertEqual(len(self.writes), 1)
        store.data["meta"]["n"] = 1
        store.save()
        self.assertEqual(len(self.writes), 2)
        self.assertEqual(on_disk()["meta"]["n"], 1)

    def test_a_deleted_file_comes_back(self):
        store.save()
        os.remove(store.path)
        store.save()
        self.assertTrue(os.path.exists(store.path))

    def test_a_request_waits_until_its_change_is_on_disk(self):
        store.data["meta"]["n"] = 7
        ticket = store.stage()
        store.commit(ticket)
        self.assertEqual(on_disk()["meta"]["n"], 7)

    def test_pile_ups_share_a_write_and_the_last_change_always_wins(self):
        errors = []

        def worker(i):
            try:
                for k in range(20):
                    n = i * 100 + k
                    ticket = None
                    with server.LOCK:
                        store.data["meta"]["n"] = n
                        store.data["meta"].setdefault("seen", []).append(n)
                        ticket = store.stage()
                    store.commit(ticket)
                    saved = on_disk()
                    if n not in saved["meta"]["seen"]:                  # my own change must be there when I get my answer
                        errors.append((i, k))
            except Exception as e:                                         # pragma: no cover
                errors.append(repr(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        final = on_disk()
        self.assertEqual(sorted(final["meta"]["seen"]), sorted(store.data["meta"]["seen"]))
        self.assertLessEqual(len(self.writes), 8 * 20)                      # and writes were shared, never more than changes

    def test_the_file_is_never_half_written(self):
        store.data["meta"]["blob"] = "x" * 200000
        store.save()
        self.assertFalse(os.path.exists(store.path + ".tmp"))
        self.assertEqual(len(on_disk()["meta"]["blob"]), 200000)


class WatchingAPokerTableDoesNotRewriteTheDatabase(unittest.TestCase):
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

    def call(self, cookie, method, path, body=None):
        r, raw = fetch(self.port, path, {"Cookie": cookie, "Content-Type": "application/json"}, method,
                       json.dumps(body) if body is not None else None)
        return r.status, json.loads(raw)

    def test_polling_a_table_and_reading_chat_marks(self):
        r, _ = fetch(self.port, "/api/auth/register", {"Content-Type": "application/json"}, "POST",
                     json.dumps({"username": "watcher", "password": "secret123"}))
        cookie = r.getheader("Set-Cookie").split(";")[0]
        st, d = self.call(cookie, "POST", "/api/poker/tables", {"name": "Quiet", "visibility": "public", "maxSeats": 4})
        self.assertEqual(st, 200)
        tid = d["table"]["id"]
        writes = []
        real = os.fsync
        os.fsync = lambda fd: (writes.append(1), real(fd))[1]
        try:
            for _ in range(10):
                st, _ = self.call(cookie, "GET", f"/api/poker/tables/{tid}")
                self.assertEqual(st, 200)
        finally:
            os.fsync = real
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
