"""Profile personalization: appearance settings, picture uploads (checked by content), removal, defaults and persistence."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                          # noqa: E402
from backend import catalog, config, cosmetics, economy, images, ledger, users   # noqa: E402
from backend.store import db, store                                    # noqa: E402
from backend.util import ApiError                                      # noqa: E402
from tests.econ import mk                                              # noqa: E402
from tests.fixtures_images import JPEG, WEBP, WEBP_LL, png             # noqa: E402
from tests.helpers import fresh_store, restore_store_path              # noqa: E402
from tests.test_http import Client                                     # noqa: E402


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


class Pictures(unittest.TestCase):
    """images.inspect: what a picture is, judged from inside the file."""

    def test_real_pictures_of_every_kind_pass(self):
        self.assertEqual(images.inspect(png()), ("png", 64, 64))
        self.assertEqual(images.inspect(png(200, 120)), ("png", 200, 120))
        self.assertEqual(images.inspect(JPEG), ("jpeg", 64, 64))
        self.assertEqual(images.inspect(WEBP), ("webp", 64, 64))
        self.assertEqual(images.inspect(WEBP_LL), ("webp", 64, 64))

    def test_the_claimed_type_must_agree_with_the_bytes(self):
        self.assertEqual(images.inspect(png(), "image/png")[0], "png")
        self.assertEqual(images.inspect(JPEG, "image/jpeg; charset=x")[0], "jpeg")
        self.assertEqual(err(images.inspect, png(), "image/jpeg").status, 400)
        self.assertEqual(err(images.inspect, JPEG, "image/webp").status, 400)

    def test_things_that_are_not_pictures_are_refused(self):
        for data in (b"", b"hello", b"<html><script>alert(1)</script></html>", b"GIF89a" + b"\x00" * 100,
                     b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><script>alert(1)</script></svg>',
                     b"\x00" * 1000, b"MZ" + b"\x00" * 200, b"%PDF-1.4 " + b"x" * 100, b"PK\x03\x04" + b"x" * 100):
            self.assertEqual(err(images.inspect, data).status, 400, data[:12])
        self.assertIn("Choose a picture", err(images.inspect, None).message)

    def test_a_picture_with_a_script_or_anything_else_stuck_on_the_end_is_refused(self):
        self.assertIn("extra data", err(images.inspect, png(trailing=b"<script>alert(1)</script>")).message)
        self.assertEqual(err(images.inspect, JPEG + b"<script>x</script>").status, 400)
        self.assertEqual(err(images.inspect, WEBP + b"hidden").status, 400)
        self.assertEqual(err(images.inspect, png(trailing=b"\x00")).status, 400)

    def test_damaged_pictures_are_refused(self):
        good = png()
        self.assertIn("damaged", err(images.inspect, png(break_crc=True)).message)
        self.assertEqual(err(images.inspect, good[:60]).status, 400)
        self.assertEqual(err(images.inspect, good[:-12]).status, 400, "no end chunk")
        self.assertEqual(err(images.inspect, JPEG[:len(JPEG) // 2]).status, 400)
        self.assertEqual(err(images.inspect, WEBP[:-5]).status, 400)
        self.assertEqual(err(images.inspect, b"\x89PNG\r\n\x1a\n" + b"junk" * 10).status, 400)

    def test_size_in_bytes_and_in_pixels_are_limited(self):
        with mock.patch.object(economy, "AVATAR_MAX_BYTES", 500):
            e = err(images.inspect, png(64, 64, extra_chunks=[(b"tEXt", b"x" * 600)]))
            self.assertEqual(e.status, 413)
            self.assertIn("too big", e.message)
        self.assertIn("too small", err(images.inspect, png(63, 64)).message)
        self.assertIn("too small", err(images.inspect, png(64, 10)).message)
        with mock.patch.object(economy, "AVATAR_MAX_PX", 100):
            self.assertIn("too large", err(images.inspect, png(101, 64)).message)
            self.assertEqual(images.inspect(png(100, 100))[1:], (100, 100))
        self.assertIn("long and thin", err(images.inspect, png(64, 300)).message)

    def test_the_size_in_the_header_is_trusted_only_if_the_picture_is_valid(self):
        # a header that claims 4000x4000 but whose data is nonsense does not get through
        fake = png(4000, 4000)[:100]
        self.assertEqual(err(images.inspect, fake).status, 400)

    def test_animated_pictures_are_refused(self):
        self.assertIn("Animated", err(images.inspect, png(extra_chunks=[(b"acTL", b"\x00\x00\x00\x02\x00\x00\x00\x00")])).message)


class Appearance(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.u = mk("alice", accum=3000)

    def test_free_settings_work_for_everyone(self):
        out = cosmetics.customize(self.u, {"bg": "felt", "banner": "banner_lime", "accent": "accent_cream", "font": "font_mono", "frame": "frame_plain",
                                           "bio": "  Bets on\n\n  everything.  "})
        self.assertEqual((out["bg"], out["slots"]["banner"], out["slots"]["accent"], out["slots"]["font"], out["slots"]["frame"]),
                         ("felt", "banner_lime", "accent_cream", "font_mono", "frame_plain"))
        self.assertEqual(out["bio"], "Bets on everything.")

    def test_locked_items_need_to_be_owned_and_the_server_checks_it(self):
        for field, pid in (("frame", "frame_dashed"), ("badge", "badge_flame"), ("title", "title_oracle"), ("banner", "banner_dots"),
                           ("accent", "accent_gold"), ("font", "font_serif"), ("avatar", "avatar_mole")):
            e = err(cosmetics.customize, self.u, {field: pid})
            self.assertEqual(e.status, 403, field)
        self.assertEqual(cosmetics.profile(self.u)["frame"], "frame_none")
        cosmetics.buy(self.u, "frame_dashed")
        self.assertEqual(cosmetics.customize(self.u, {"frame": "frame_dashed"})["slots"]["frame"], "frame_dashed")

    def test_the_wrong_kind_of_item_for_a_slot_is_refused(self):
        cosmetics.buy(self.u, "badge_flame")
        self.assertIn("not an option", err(cosmetics.customize, self.u, {"frame": "badge_flame"}).message)
        for junk in (None, 5, [], {}, "", "frame_lime; DROP", "../../etc/passwd"):
            self.assertEqual(err(cosmetics.customize, self.u, {"frame": junk}).status in (400, 403), True, repr(junk))

    def test_arbitrary_styling_is_not_accepted(self):
        for body in ({"font": "Comic Sans MS"}, {"font": "url(http://evil.example/x.woff2)"}, {"accent": "#ff0000"}, {"accent": "red; background:url(x)"},
                     {"bg": "#123456"}, {"bg": "url(x)"}, {"css": "body{display:none}"}):
            before = json.dumps(cosmetics.profile(self.u), sort_keys=True)
            try:
                cosmetics.customize(self.u, body)
            except ApiError:
                pass
            self.assertEqual(json.dumps(cosmetics.profile(self.u), sort_keys=True), before, body)
        self.assertNotIn("css", cosmetics.profile(self.u))

    def test_unreadable_colour_combinations_are_refused(self):
        e = err(cosmetics.customize, self.u, {"bg": "paper", "accent": "accent_cream"})
        self.assertIn("hard to read", e.message)
        self.assertEqual(cosmetics.profile(self.u)["bg"], "ink", "nothing was half applied")
        self.assertIn("hard to read", err(cosmetics.customize, self.u, {"bg": "paper"}).message, "paper with the default lime accent")
        out = cosmetics.customize(self.u, {"bg": "paper", "accent": "accent_verm"}) if cosmetics.readable("#FF4B2B", "paper") else None
        for acc in ("accent_lime", "accent_verm", "accent_cream"):
            for bg in catalog.BACKGROUNDS:
                ok = cosmetics.readable(catalog.CATALOG[acc]["art"]["color"], bg)
                if ok:
                    self.assertGreaterEqual(cosmetics.contrast(catalog.CATALOG[acc]["art"]["color"], catalog.BACKGROUNDS[bg]["color"]), 3.0)
        self.assertGreater(cosmetics.contrast("#000000", "#FFFFFF"), 20.9)
        self.assertAlmostEqual(cosmetics.contrast("#777777", "#777777"), 1.0)
        self.assertTrue(out is None or out["bg"] == "paper")

    def test_every_free_accent_is_readable_on_the_default_background(self):
        for it in catalog.CATALOG.values():
            if it["kind"] == "accent":
                self.assertTrue(cosmetics.readable(it["art"]["color"], catalog.DEFAULT_BG), it["id"])

    def test_a_bad_field_changes_nothing_at_all(self):
        cosmetics.buy(self.u, "frame_lime")
        before = json.dumps(cosmetics.profile(self.u), sort_keys=True)
        e = err(cosmetics.customize, self.u, {"frame": "frame_lime", "bg": "felt", "bio": "x" * 500})
        self.assertEqual(e.status, 400)
        self.assertEqual(json.dumps(cosmetics.profile(self.u), sort_keys=True), before)

    def test_bio_is_plain_text_and_short(self):
        out = cosmetics.customize(self.u, {"bio": "<script>alert(1)</script> hi"})
        self.assertEqual(out["bio"], "<script>alert(1)</script> hi", "stored as text; the page always escapes it when drawing")
        self.assertEqual(err(cosmetics.customize, self.u, {"bio": "y" * 141}).status, 400)
        self.assertEqual(cosmetics.customize(self.u, {"bio": ""})["bio"], "")
        self.assertEqual(err(cosmetics.customize, self.u, {"bio": 12}).status, 400)

    def test_reset_puts_everything_back_to_the_defaults_and_keeps_what_you_own(self):
        for pid in ("frame_lime", "badge_flame", "avatar_mole"):
            cosmetics.buy(self.u, pid)
        cosmetics.customize(self.u, {"frame": "frame_lime", "badge": "badge_flame", "avatar": "avatar_mole", "bg": "wine", "bio": "hello"})
        out = cosmetics.customize(self.u, {"reset": True})
        self.assertEqual(out["slots"], {"avatar": "avatar_initial", "frame": "frame_none", "badge": "badge_none", "title": "title_none",
                                        "banner": "banner_plain", "accent": "accent_lime", "font": "font_display"})
        self.assertEqual((out["bg"], out["bio"], out["style"]), ("ink", "", {}))
        self.assertTrue({"frame_lime", "badge_flame", "avatar_mole"} <= set(cosmetics.inventory(self.u)))
        self.assertEqual(cosmetics.customize(self.u, {"frame": "frame_lime"})["slots"]["frame"], "frame_lime", "still yours")

    def test_it_survives_a_restart(self):
        cosmetics.buy(self.u, "frame_lime")
        cosmetics.customize(self.u, {"frame": "frame_lime", "bg": "slate", "bio": "kept"})
        saved = json.dumps(store.data)
        store.data = json.loads(saved)
        store.load()
        u = users.by_username("alice")
        self.assertEqual((cosmetics.profile_json(u)["slots"]["frame"], cosmetics.profile_json(u)["bg"], cosmetics.profile_json(u)["bio"]), ("frame_lime", "slate", "kept"))
        self.assertEqual(users.public(u)["st"]["f"]["color"], "#C6F432")

    def test_accounts_that_never_customized_anything_keep_working(self):
        old = users.register("ancient", "secret123")
        old.pop("profile", None)
        old.pop("inv", None)
        self.assertEqual(cosmetics.profile_json(old)["slots"]["frame"], "frame_none")
        self.assertEqual(users.public(old), {"id": old["id"], "username": "ancient", "rank": {"t": "bronze", "d": 3, "l": "Bronze III"}})
        self.assertTrue(cosmetics.owns(old, "frame_plain"))


class Uploading(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.dir = tempfile.mkdtemp()
        self._patch = mock.patch.object(cosmetics, "UPLOAD_DIR", self.dir)
        self._patch.start()
        self.u = mk("alice", accum=3000)

    def tearDown(self):
        self._patch.stop()

    def files(self):
        return sorted(os.listdir(self.dir))

    def test_upload_replace_and_remove(self):
        out = cosmetics.set_upload(self.u, png(), "image/png")
        self.assertEqual((out["kind"], out["width"], out["height"]), ("png", 64, 64))
        first = self.files()
        self.assertEqual(len(first), 1)
        self.assertRegex(first[0], r"^[a-f0-9]{12}-[a-f0-9]{8}\.png$")
        self.assertTrue(first[0].startswith(self.u["id"]))
        self.assertEqual(out["profile"]["slots"]["avatar"], "upload")
        self.assertEqual(out["profile"]["upload"], "/uploads/avatars/" + first[0])
        self.assertEqual(users.public(self.u)["st"]["u"], first[0])
        cosmetics.set_upload(self.u, JPEG, "image/jpeg")
        second = self.files()
        self.assertEqual(len(second), 1, "the old picture is deleted when replaced")
        self.assertNotEqual(first, second)
        self.assertTrue(second[0].endswith(".jpg"))
        out = cosmetics.remove_upload(self.u)
        self.assertEqual(self.files(), [])
        self.assertEqual((out["slots"]["avatar"], out["upload"]), ("avatar_initial", None))
        self.assertNotIn("u", users.public(self.u).get("st", {}))
        self.assertEqual(err(cosmetics.remove_upload, self.u).status, 400)

    def test_a_bad_upload_changes_nothing_and_leaves_no_file(self):
        cosmetics.set_upload(self.u, png(), "image/png")
        before = (self.files(), json.dumps(cosmetics.profile(self.u), sort_keys=True))
        for data in (b"not a picture", png(trailing=b"<script>"), png(10, 10), png(break_crc=True), b""):
            self.assertEqual(err(cosmetics.set_upload, self.u, data).status in (400, 413), True)
        self.assertEqual((self.files(), json.dumps(cosmetics.profile(self.u), sort_keys=True)), before)

    def test_the_stored_name_is_made_by_the_server_never_by_the_user(self):
        cosmetics.set_upload(self.u, png(), "image/png")
        self.assertRegex(cosmetics.uploaded_file(self.u), cosmetics.FILE_RE)
        self.u["profile"]["upload"] = "../../etc/passwd"
        self.assertIsNone(cosmetics.uploaded_file(self.u), "a tampered name is ignored")
        for name in ("../x.png", "a.png", "abc-def.png", "x" * 12 + "-" + "y" * 8 + ".png", "..%2f..", "", None):
            self.assertIsNone(cosmetics.read_upload(name))

    def test_choosing_the_uploaded_picture_needs_an_upload(self):
        self.assertIn("Upload a picture first", err(cosmetics.customize, self.u, {"avatar": "upload"}).message)
        cosmetics.set_upload(self.u, WEBP, "image/webp")
        cosmetics.customize(self.u, {"avatar": "avatar_initial"})
        self.assertEqual(cosmetics.customize(self.u, {"avatar": "upload"})["slots"]["avatar"], "upload")

    def test_the_uploaded_picture_survives_a_restart(self):
        cosmetics.set_upload(self.u, png(), "image/png")
        name = cosmetics.uploaded_file(self.u)
        store.data = json.loads(json.dumps(store.data))
        store.load()
        u = users.by_username("alice")
        self.assertEqual(cosmetics.uploaded_file(u), name)
        self.assertEqual(cosmetics.read_upload(name)[1], "image/png")

    def test_equipping_a_store_avatar_then_going_back_to_the_upload(self):
        cosmetics.set_upload(self.u, png(), "image/png")
        cosmetics.buy(self.u, "avatar_mole")
        cosmetics.equip(self.u, "avatar_mole")
        st = users.public(self.u)["st"]
        self.assertEqual((st.get("a", {}).get("icon"), "u" in st), ("moles", False))
        cosmetics.customize(self.u, {"avatar": "upload"})
        self.assertTrue(users.public(self.u)["st"]["u"])


class UploadingOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fresh_store()
        cls.dir = tempfile.mkdtemp()
        cls._patch = mock.patch.object(cosmetics, "UPLOAD_DIR", cls.dir)
        cls._patch.start()
        cls.srv = server.Server(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls._patch.stop()
        cls.srv.shutdown()
        cls.srv.server_close()

    def person(self, name):
        c = Client(self.port)
        c.call("POST", "/api/auth/register", {"username": name, "password": "secret123"})
        return c

    def raw(self, client, method, path, data, ctype):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, data, {"Content-Type": ctype, "Cookie": client.cookie or "", **({} if data is not None else {})})
        r = conn.getresponse()
        body = r.read()
        conn.close()
        try:
            return r.status, json.loads(body), r
        except ValueError:
            return r.status, body, r

    def test_upload_view_and_remove_through_the_server(self):
        a, b = self.person("uploader"), self.person("looker")
        st, d, _ = self.raw(a, "POST", "/api/profile/avatar", png(), "image/png")
        self.assertEqual(st, 200)
        url = d["profile"]["upload"]
        self.assertRegex(url, r"^/uploads/avatars/[a-f0-9]{12}-[a-f0-9]{8}\.png$")
        # members can see it, with the right type and strict headers; strangers cannot
        st, body, r = self.raw(b, "GET", url, None, "x")
        self.assertEqual((st, body, r.getheader("Content-Type")), (200, png(), "image/png"))
        self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")
        self.assertIn("immutable", r.getheader("Cache-Control"))
        self.assertEqual(self.raw(Client(self.port), "GET", url, None, "x")[0], 404)
        self.assertEqual(self.raw(b, "GET", "/uploads/avatars/..%2f..%2fserver.py", None, "x")[0], 404)
        self.assertEqual(self.raw(b, "GET", "/uploads/avatars/nothing.png", None, "x")[0], 404)
        # and other people see it in the places lists show people
        st, circ = a.call("POST", "/api/circles", {"name": "Faces", "visibility": "public"})
        cid = circ["circle"]["id"]
        b.call("POST", f"/api/circles/{cid}/join", {})
        st, d = b.call("GET", f"/api/circles/{cid}")
        me = [m for m in d["members"] if m["user"]["username"] == "uploader"][0]
        self.assertEqual("/uploads/avatars/" + me["user"]["st"]["u"], url)
        st, d, _ = self.raw(a, "DELETE", "/api/profile/avatar", None, "application/json")
        self.assertEqual((st, d["profile"]["upload"]), (200, None))
        self.assertEqual(self.raw(b, "GET", url, None, "x")[0], 404, "gone from the server too")

    def test_what_the_server_refuses_over_http(self):
        a = self.person("fussy")
        self.assertEqual(self.raw(a, "POST", "/api/profile/avatar", b"<html>", "image/png")[0], 400)
        self.assertEqual(self.raw(a, "POST", "/api/profile/avatar", png(), "image/jpeg")[0], 400)
        self.assertEqual(self.raw(a, "POST", "/api/profile/avatar", png(), "text/html")[0], 415)
        self.assertEqual(self.raw(a, "POST", "/api/profile/avatar", json.dumps({"x": 1}), "application/json")[0], 415)
        with mock.patch.object(economy, "AVATAR_MAX_BYTES", 40):
            st, d, _ = self.raw(a, "POST", "/api/profile/avatar", png(), "image/png")
            self.assertEqual(st, 413)
        self.assertEqual(self.raw(Client(self.port), "POST", "/api/profile/avatar", png(), "image/png")[0], 401)

    def test_another_site_cannot_upload_for_you(self):
        a = self.person("guarded")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/profile/avatar", png(), {"Content-Type": "image/png", "Cookie": a.cookie, "Origin": "https://evil.example"})
        self.assertEqual(conn.getresponse().status, 403)

    def test_customize_over_http(self):
        a = self.person("styled")
        st, d = a.call("POST", "/api/profile", {"bg": "felt", "bio": "hi"})
        self.assertEqual((st, d["profile"]["bg"]), (200, "felt"))
        self.assertEqual(a.call("POST", "/api/profile", {"frame": "frame_gold"})[0], 403)
        self.assertEqual(a.call("POST", "/api/profile", {"bg": "nope"})[0], 400)
        st, d = a.call("GET", "/api/profile")
        self.assertEqual((d["profile"]["bg"], d["profile"]["bio"]), ("felt", "hi"))
        self.assertIn("display", d["profile"]["fonts"])


if __name__ == "__main__":
    unittest.main()
