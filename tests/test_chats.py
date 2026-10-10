"""Chats: the site-wide one, circle chats, direct messages and groups. Who can see what, and what gets through."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import chats, circles, social, users          # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402


def tearDownModule():
    restore_store_path()


def mk(name):
    return users.register(name, "secret123")


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


def befriend(a, b):
    social.request(a, b["username"])
    social.accept(b, a["id"])


def texts(user, chat_id, **kw):
    return [m["x"] for m in chats.history(user, chat_id, **kw)["messages"]]


class Setup(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.ann, self.bob, self.cat, self.dan = mk("ann_x"), mk("bob_x"), mk("cat_x"), mk("dan_x")


class SiteWide(Setup):
    def test_everybody_can_read_and_write_in_the_global_chat(self):
        chat, msg = chats.send(self.ann, "global", "hello world")
        self.assertEqual((msg["n"], msg["u"]), (1, self.ann["id"]))
        self.assertEqual(texts(self.dan, "global"), ["hello world"])
        chats.send(self.dan, "global", "hi ann")
        m = chats.history(self.bob, "global")["messages"]
        self.assertEqual([(x["name"], x["x"]) for x in m], [("ann_x", "hello world"), ("dan_x", "hi ann")])

    def test_notification_goes_to_everybody_for_the_global_chat_and_only_members_elsewhere(self):
        circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        circles.join(self.bob, circle["id"], circle["inviteCode"])
        chat, _ = chats.send(self.ann, "global", "x")
        self.assertIsNone(chats.recipients(chat))
        chat, _ = chats.send(self.ann, "circle_" + circle["id"], "x")
        self.assertEqual(set(chats.recipients(chat)), {self.ann["id"], self.bob["id"]})

    def test_unknown_chat_ids_are_not_found(self):
        for cid in ("nope", "dm_x_y", "group_zzz", "circle_missing", "circle_", "global2"):
            self.assertEqual(err(chats.history, self.ann, cid).status, 404)


class CircleChats(Setup):
    def setUp(self):
        super().setUp()
        self.circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        self.cid = "circle_" + self.circle["id"]
        circles.join(self.bob, self.circle["id"], self.circle["inviteCode"])

    def test_only_members_can_read_or_write(self):
        chats.send(self.ann, self.cid, "secret plans")
        self.assertEqual(texts(self.bob, self.cid), ["secret plans"])
        self.assertEqual(err(chats.history, self.cat, self.cid).status, 404)
        self.assertEqual(err(chats.send, self.cat, self.cid, "let me in").status, 404)

    def test_a_circle_even_a_public_one_keeps_its_chat_for_members(self):
        public = circles.create(self.ann, {"name": "Open", "visibility": "public"})
        chats.send(self.ann, "circle_" + public["id"], "members only")
        self.assertEqual(err(chats.history, self.cat, "circle_" + public["id"]).status, 404)

    def test_joining_gives_access_and_leaving_or_being_kicked_takes_it_away(self):
        chats.send(self.ann, self.cid, "welcome")
        circles.join(self.cat, self.circle["id"], self.circle["inviteCode"])
        self.assertEqual(texts(self.cat, self.cid), ["welcome"])
        circles.leave(self.cat, self.circle["id"])
        self.assertEqual(err(chats.history, self.cat, self.cid).status, 404)
        circles.kick(self.ann, self.circle["id"], self.bob["id"])
        self.assertEqual(err(chats.send, self.bob, self.cid, "hello?").status, 404)

    def test_the_list_has_global_then_each_circle_you_are_in(self):
        rows = {r["id"]: r for r in chats.list_for(self.bob)}
        self.assertEqual(set(rows), {"global", self.cid})
        self.assertEqual((rows[self.cid]["name"], rows[self.cid]["kind"], rows[self.cid]["members"]), ("Crew", "circle", 2))
        self.assertEqual(set(r["id"] for r in chats.list_for(self.cat)), {"global"})

    def test_the_circle_owner_can_clear_messages_but_other_members_cannot(self):
        _, m = chats.send(self.bob, self.cid, "oops")
        _, m2 = chats.send(self.ann, self.cid, "owner says hi")
        self.assertEqual(err(chats.delete_message, self.cat, self.cid, m["n"]).status, 404)      # not even in it
        circles.join(self.cat, self.circle["id"], self.circle["inviteCode"])
        self.assertEqual(err(chats.delete_message, self.cat, self.cid, m["n"]).status, 403)
        chats.delete_message(self.ann, self.cid, m["n"])
        self.assertEqual(texts(self.bob, self.cid), ["owner says hi"])
        self.assertEqual(err(chats.delete_message, self.bob, self.cid, m2["n"]).status, 403)


class Direct(Setup):
    def test_only_friends_can_start_a_direct_chat(self):
        self.assertEqual(err(chats.open_dm, self.ann, self.bob["id"]).status, 403)
        self.assertEqual(err(chats.open_dm, self.ann, "nobody").status, 403)
        befriend(self.ann, self.bob)
        chat = chats.open_dm(self.ann, self.bob["id"])
        self.assertEqual(chat["id"], chats.open_dm(self.bob, self.ann["id"])["id"])             # one chat, whoever opens it
        self.assertEqual(chats.title(chat, self.ann["id"]), "bob_x")
        self.assertEqual(chats.title(chat, self.bob["id"]), "ann_x")

    def test_circle_mates_can_message_each_other_without_adding(self):
        circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        circles.join(self.bob, circle["id"], circle["inviteCode"])
        chat = chats.open_dm(self.ann, self.bob["id"])
        chats.send(self.ann, chat["id"], "hey")
        self.assertEqual(texts(self.bob, chat["id"]), ["hey"])

    def test_nobody_else_can_read_it_or_join_it(self):
        befriend(self.ann, self.bob)
        chat = chats.open_dm(self.ann, self.bob["id"])
        chats.send(self.ann, chat["id"], "just us")
        self.assertEqual(err(chats.history, self.cat, chat["id"]).status, 404)
        self.assertEqual(err(chats.send, self.cat, chat["id"], "me too").status, 404)
        forged = "dm_" + "_".join(sorted([self.cat["id"], self.bob["id"]]))
        self.assertEqual(err(chats.history, self.cat, forged).status, 404)                         # inventing an id gets nothing

    def test_a_direct_chat_appears_in_the_list_with_its_first_message(self):
        befriend(self.ann, self.bob)
        chat = chats.open_dm(self.ann, self.bob["id"])
        self.assertNotIn(chat["id"], [r["id"] for r in chats.list_for(self.bob)])
        chats.send(self.ann, chat["id"], "knock knock")
        row = next(r for r in chats.list_for(self.bob) if r["id"] == chat["id"])
        self.assertEqual((row["name"], row["unread"], row["last"]["x"], row["with"]), ("ann_x", 1, "knock knock", self.ann["id"]))

    def test_after_unfriending_the_old_messages_stay_but_nobody_can_write(self):
        befriend(self.ann, self.bob)
        chat = chats.open_dm(self.ann, self.bob["id"])
        chats.send(self.ann, chat["id"], "remember me")
        social.remove(self.ann, self.bob["id"])
        self.assertEqual(texts(self.bob, chat["id"]), ["remember me"])
        self.assertFalse(chats.history(self.bob, chat["id"])["chat"]["canSend"])
        self.assertEqual(err(chats.send, self.bob, chat["id"], "wait").status, 403)


class Groups(Setup):
    def setUp(self):
        super().setUp()
        for other in (self.bob, self.cat, self.dan):
            befriend(self.ann, other)

    def group(self, name="Poker night", with_=None):
        return chats.create_group(self.ann, name, [(with_ or [self.bob, self.cat])[i]["id"] for i in range(len(with_ or [self.bob, self.cat]))])

    def test_a_group_takes_two_or_more_of_your_friends(self):
        chat = self.group()
        self.assertEqual((chat["kind"], chat["owner"], len(chat["members"])), ("group", self.ann["id"], 3))
        self.assertEqual(chats.title(chat, self.bob["id"]), "Poker night")
        self.assertIn("at least two", err(chats.create_group, self.ann, "x", [self.bob["id"]]).message)
        self.assertIn("at least two", err(chats.create_group, self.ann, "x", [self.bob["id"], self.bob["id"], self.ann["id"]]).message)

    def test_you_can_only_add_friends_and_real_people(self):
        eve = mk("eve_x")
        self.assertIn("not your friend", err(chats.create_group, self.ann, "x", [self.bob["id"], eve["id"]]).message)
        self.assertIn("doesn't exist", err(chats.create_group, self.ann, "x", [self.bob["id"], "ghost"]).message)
        self.assertEqual(err(chats.create_group, self.ann, "x", "bob").status, 400)

    def test_without_a_name_the_group_is_called_after_who_is_in_it(self):
        chat = self.group(name="")
        self.assertEqual(chats.title(chat, self.ann["id"]), "bob_x, cat_x")
        self.assertEqual(chats.title(chat, self.bob["id"]), "ann_x, cat_x")
        big = chats.create_group(self.ann, "", [self.bob["id"], self.cat["id"], self.dan["id"]])
        self.assertEqual(chats.title(big, self.bob["id"]), "ann_x, cat_x, dan_x")

    def test_members_talk_outsiders_cannot_see_a_thing(self):
        chat = self.group()
        chats.send(self.bob, chat["id"], "who is bringing the chips")
        self.assertEqual(texts(self.cat, chat["id"])[-1], "who is bringing the chips")
        self.assertEqual(err(chats.history, self.dan, chat["id"]).status, 404)
        self.assertEqual(err(chats.send, self.dan, chat["id"], "hello").status, 404)

    def test_the_owner_adds_removes_and_renames_and_the_chat_says_so(self):
        chat = self.group()
        chats.add_members(self.ann, chat["id"], [self.dan["id"]])
        self.assertEqual(texts(self.dan, chat["id"])[-1], "ann_x added dan_x")
        chats.rename(self.ann, chat["id"], "High rollers")
        self.assertEqual(chats.title(chat, self.dan["id"]), "High rollers")
        chats.remove_member(self.ann, chat["id"], self.cat["id"])
        self.assertEqual(err(chats.history, self.cat, chat["id"]).status, 404)
        self.assertEqual(texts(self.bob, chat["id"])[-1], "ann_x removed cat_x")

    def test_other_members_cannot_manage_the_group(self):
        chat = self.group()
        self.assertEqual(err(chats.add_members, self.bob, chat["id"], [self.dan["id"]]).status, 403)
        self.assertEqual(err(chats.remove_member, self.bob, chat["id"], self.cat["id"]).status, 403)
        self.assertEqual(err(chats.rename, self.bob, chat["id"], "mine now").status, 403)

    def test_leaving_passes_the_group_on_and_closes_it_when_two_are_not_left(self):
        chat = self.group()
        chats.leave(self.ann, chat["id"])
        self.assertEqual(chat["owner"], self.bob["id"])
        self.assertEqual(texts(self.cat, chat["id"])[-1], "ann_x left")
        self.assertEqual(err(chats.history, self.ann, chat["id"]).status, 404)
        self.assertIsNone(chats.leave(self.cat, chat["id"]))                                          # one person left: it closes
        self.assertEqual(err(chats.history, self.bob, chat["id"]).status, 404)

    def test_you_cannot_leave_a_site_or_circle_chat_or_a_direct_chat(self):
        self.assertIn("only leave a group", err(chats.leave, self.ann, "global").message)
        circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        self.assertIn("leave the circle", err(chats.leave, self.ann, "circle_" + circle["id"]).message)
        dm = chats.open_dm(self.ann, self.bob["id"])
        self.assertIn("only leave a group", err(chats.leave, self.ann, dm["id"]).message)

    def test_group_size_has_a_limit(self):
        with mock.patch.object(chats, "MAX_GROUP", 3):
            chat = self.group()
            self.assertIn("at most", err(chats.add_members, self.ann, chat["id"], [self.dan["id"]]).message)
            self.assertIn("at most", err(chats.create_group, self.ann, "big", [self.bob["id"], self.cat["id"], self.dan["id"]]).message)


class WhatGetsThrough(Setup):
    def test_messages_are_cleaned_up(self):
        for raw, clean in (("  hi   there  ", "hi there"), ("a\n\n\n\nb", "a\n\nb"), ("line one\n   line two  ", "line one\nline two"),
                           ("bell\x07 and\x00 null", "bell and null"), ("evil ‮text", "evil text"), ("<b>not html</b>", "<b>not html</b>")):
            self.assertEqual(chats.clean_message(raw), clean)
        self.assertEqual(chats.clean_message("emoji 👨‍👩‍👧 stay"), "emoji 👨‍👩‍👧 stay")
        for bad in ("", "   \n  ", "\x00\x01", None, 12, ["x"]):
            self.assertEqual(err(chats.clean_message, bad).status, 400)
        self.assertEqual(err(chats.clean_message, "x" * 501).status, 400)
        self.assertEqual(len(chats.clean_message("x" * 500)), 500)

    def test_it_stores_text_exactly_not_markup(self):
        chats.send(self.ann, "global", "<script>alert('x')</script>")
        self.assertEqual(texts(self.bob, "global"), ["<script>alert('x')</script>"])        # the page escapes it when drawing

    def test_nobody_can_flood_a_chat(self):
        sent = 0
        for _ in range(15):
            try:
                chats.send(self.ann, "global", "spam")
                sent += 1
            except ApiError as e:
                self.assertEqual(e.status, 429)
        self.assertEqual(sent, chats.SPEED[0])
        chats.send(self.bob, "global", "but others can still talk")

    def test_only_the_newest_messages_are_kept(self):
        with mock.patch.dict(chats.KEEP, {"global": 5}), mock.patch.object(chats, "SPEED", (999, 1)):
            for i in range(9):
                chats.send(self.ann, "global", f"m{i}")
        self.assertEqual(texts(self.bob, "global"), ["m4", "m5", "m6", "m7", "m8"])

    def test_history_pages_backwards_and_catches_up_forwards(self):
        with mock.patch.object(chats, "PAGE", 4), mock.patch.object(chats, "SPEED", (999, 1)):
            for i in range(1, 11):
                chats.send(self.ann, "global", f"m{i}")
            first = chats.history(self.bob, "global")
            self.assertEqual(([m["x"] for m in first["messages"]], first["more"]), (["m7", "m8", "m9", "m10"], True))
            older = chats.history(self.bob, "global", before=7)
            self.assertEqual(([m["x"] for m in older["messages"]], older["more"]), (["m3", "m4", "m5", "m6"], True))
            oldest = chats.history(self.bob, "global", before=3)
            self.assertEqual(([m["x"] for m in oldest["messages"]], oldest["more"]), (["m1", "m2"], False))
            self.assertEqual(texts(self.bob, "global", after=8), ["m9", "m10"])
            self.assertEqual(texts(self.bob, "global", after=10), [])

    def test_you_can_take_back_your_own_message_and_nobody_elses(self):
        _, m = chats.send(self.ann, "global", "regret")
        self.assertEqual(err(chats.delete_message, self.bob, "global", m["n"]).status, 403)
        chats.delete_message(self.ann, "global", m["n"])
        self.assertEqual(texts(self.bob, "global"), [])
        self.assertEqual(err(chats.delete_message, self.ann, "global", m["n"]).status, 404)

    def test_the_groups_own_notices_cannot_be_deleted(self):
        befriend(self.ann, self.bob)
        befriend(self.ann, self.cat)
        chat = chats.create_group(self.ann, "G", [self.bob["id"], self.cat["id"]])
        self.assertEqual(err(chats.delete_message, self.ann, chat["id"], 1).status, 404)


class ReadReceipts(Setup):
    def setUp(self):
        super().setUp()
        befriend(self.ann, self.bob)
        befriend(self.ann, self.cat)
        self.dm = chats.open_dm(self.ann, self.bob["id"])["id"]

    def readers_of(self, user, chat_id):
        return {r["username"]: r for r in chats.history(user, chat_id)["chat"]["readers"]}

    def test_nobody_has_read_anything_until_they_open_it(self):
        chats.send(self.ann, self.dm, "hello")
        self.assertEqual(self.readers_of(self.ann, self.dm), {})
        _, entry = chats.mark_read(self.bob, self.dm, 1)
        self.assertEqual(entry[0], 1)
        seen = self.readers_of(self.ann, self.dm)["bob_x"]
        self.assertEqual((seen["n"], seen["id"]), (1, self.bob["id"]))
        self.assertGreater(seen["t"], 0)

    def test_the_time_is_when_they_got_there_and_only_moves_when_they_read_more(self):
        chats.send(self.ann, self.dm, "one")
        with mock.patch.object(chats, "now_ms", return_value=1_000):
            chats.mark_read(self.bob, self.dm, 1)
        with mock.patch.object(chats, "now_ms", return_value=9_000):
            _, again = chats.mark_read(self.bob, self.dm, 1)                          # nothing new: the time stays put
        self.assertIsNone(again)
        self.assertEqual(self.readers_of(self.ann, self.dm)["bob_x"]["t"], 1_000)
        chats.send(self.ann, self.dm, "two")
        with mock.patch.object(chats, "now_ms", return_value=20_000):
            chats.mark_read(self.bob, self.dm, 2)
        self.assertEqual((self.readers_of(self.ann, self.dm)["bob_x"]["n"], self.readers_of(self.ann, self.dm)["bob_x"]["t"]), (2, 20_000))

    def test_reading_never_goes_backwards_or_past_what_exists(self):
        for t in ("a", "b", "c"):
            chats.send(self.ann, self.dm, t)
        chats.mark_read(self.bob, self.dm, 3)
        _, back = chats.mark_read(self.bob, self.dm, 1)
        self.assertIsNone(back)
        chats.mark_read(self.cat, "global", 999)                                       # cannot have read what has not been written
        self.assertEqual(self.readers_of(self.ann, self.dm)["bob_x"]["n"], 3)

    def test_writing_counts_as_having_read_what_came_before(self):
        chats.send(self.ann, self.dm, "question?")
        chats.send(self.bob, self.dm, "answer")
        self.assertEqual(self.readers_of(self.ann, self.dm)["bob_x"]["n"], 2)

    def test_you_never_appear_in_your_own_list(self):
        chats.send(self.ann, self.dm, "hi")
        chats.mark_read(self.bob, self.dm, 1)
        self.assertNotIn("ann_x", self.readers_of(self.ann, self.dm))
        self.assertIn("ann_x", self.readers_of(self.bob, self.dm))

    def test_it_goes_both_ways_turn_yours_off_and_you_see_nobody_and_nobody_sees_you(self):
        chats.send(self.ann, self.dm, "hi")
        chats.mark_read(self.bob, self.dm, 1)
        chats.send(self.bob, self.dm, "hi back")
        chats.mark_read(self.ann, self.dm, 2)
        self.assertEqual(set(self.readers_of(self.ann, self.dm)), {"bob_x"})
        chats.set_receipts(self.bob, False)
        self.assertEqual(self.readers_of(self.ann, self.dm), {})                      # ann can no longer see bob's
        self.assertEqual(self.readers_of(self.bob, self.dm), {})                      # and bob cannot see ann's
        self.assertFalse(chats.history(self.bob, self.dm)["chat"]["receipts"])
        chats.set_receipts(self.bob, True)
        self.assertEqual(set(self.readers_of(self.ann, self.dm)), {"bob_x"})          # back on: what was read earlier shows again
        self.assertEqual(set(self.readers_of(self.bob, self.dm)), {"ann_x"})

    def test_receipts_are_on_to_begin_with_and_the_setting_needs_a_real_yes_or_no(self):
        self.assertTrue(chats.receipts_on(self.ann["id"]))
        for junk in ("yes", 1, None, [True]):
            self.assertEqual(err(chats.set_receipts, self.ann, junk).status, 400)
        self.assertTrue(chats.receipts_on(self.ann["id"]))

    def test_groups_show_where_each_person_has_got_to(self):
        group = chats.create_group(self.ann, "Trio", [self.bob["id"], self.cat["id"]])["id"]
        for t in ("one", "two", "three"):
            chats.send(self.ann, group, t)
        chats.mark_read(self.bob, group, 4)                                             # message 1 is the group's own notice
        chats.mark_read(self.cat, group, 3)
        seen = self.readers_of(self.ann, group)
        self.assertEqual((seen["bob_x"]["n"], seen["cat_x"]["n"]), (4, 3))
        self.assertEqual(set(self.readers_of(self.bob, group)), {"ann_x", "cat_x"})
        self.assertEqual(err(chats.history, self.dan, group).status, 404)               # outsiders get nothing at all

    def test_circle_chats_only_list_members_who_really_opened_them(self):
        circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        cid = "circle_" + circle["id"]
        circles.join(self.bob, circle["id"], circle["inviteCode"])
        circles.join(self.cat, circle["id"], circle["inviteCode"])
        chats.send(self.ann, cid, "meeting at nine")
        chats.list_for(self.bob)                                                        # bob only had the chat listed, like a late joiner
        chats.unread_totals(self.cat)
        self.assertEqual(self.readers_of(self.ann, cid), {})
        chats.mark_read(self.bob, cid, 1)
        self.assertEqual(set(self.readers_of(self.ann, cid)), {"bob_x"})
        circles.leave(self.bob, circle["id"])
        self.assertEqual(self.readers_of(self.ann, cid), {})                            # leaving takes you off the list

    def test_the_site_wide_chat_has_no_receipts(self):
        chats.send(self.ann, "global", "hello all")
        chats.mark_read(self.bob, "global", 1)
        self.assertEqual(chats.history(self.ann, "global")["chat"]["readers"], [])
        self.assertEqual(chats.seen_audience(chats.chat_for(self.ann, "global"), self.bob["id"]), [])

    def test_the_live_audience_is_only_the_others_who_share_receipts(self):
        group = chats.create_group(self.ann, "Trio", [self.bob["id"], self.cat["id"]])
        self.assertEqual(set(chats.seen_audience(group, self.bob["id"])), {self.ann["id"], self.cat["id"]})
        chats.set_receipts(self.cat, False)
        self.assertEqual(chats.seen_audience(group, self.bob["id"]), [self.ann["id"]])    # cat gets nothing: hers are off
        self.assertEqual(chats.seen_audience(group, self.cat["id"]), [])                  # and she tells nobody

    def test_records_from_before_receipts_existed_still_work(self):
        social_record = social.rec(self.bob["id"])
        for key in ("receipts", "seenIn"):
            social_record.pop(key, None)
        chats.send(self.ann, self.dm, "old account")
        self.assertEqual(set(self.readers_of(self.bob, self.dm)), {"ann_x"})            # ann wrote it, so ann has read it
        self.assertEqual(self.readers_of(self.ann, self.dm), {})                        # bob has not opened it yet
        chats.mark_read(self.bob, self.dm, 1)
        self.assertEqual(set(self.readers_of(self.ann, self.dm)), {"bob_x"})


class Unread(Setup):
    def test_you_are_not_counted_for_your_own_messages_and_reading_clears_it(self):
        befriend(self.ann, self.bob)
        dm = chats.open_dm(self.ann, self.bob["id"])
        for t in ("one", "two", "three"):
            chats.send(self.ann, dm["id"], t)
        self.assertEqual(chats.unread_totals(self.ann), {"total": 0, "global": 0})
        self.assertEqual(chats.unread_totals(self.bob)["total"], 3)
        chats.mark_read(self.bob, dm["id"], 2)
        self.assertEqual(chats.unread_totals(self.bob)["total"], 1)
        chats.mark_read(self.bob, dm["id"], 99)                                                 # cannot read what has not been written
        self.assertEqual(chats.unread_totals(self.bob)["total"], 0)
        chats.mark_read(self.bob, dm["id"], 1)                                                  # and the pointer never moves back
        self.assertEqual(chats.unread_totals(self.bob)["total"], 0)

    def test_the_busy_site_wide_chat_is_not_in_the_header_count(self):
        chats.list_for(self.bob)                                                                 # bob has now "seen" the chat
        chats.send(self.ann, "global", "anyone here")
        self.assertEqual(chats.unread_totals(self.bob), {"total": 0, "global": 1})

    def test_arriving_late_to_a_busy_chat_does_not_start_you_with_a_pile(self):
        for i in range(5):
            chats.send(self.ann, "global", f"old{i}")
        self.assertEqual(chats.unread_totals(self.cat), {"total": 0, "global": 0})
        chats.send(self.ann, "global", "new")
        self.assertEqual(chats.unread_totals(self.cat)["global"], 1)

    def test_circle_chats_count_for_the_header_and_a_late_joiner_starts_clean(self):
        circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        cid = "circle_" + circle["id"]
        chats.send(self.ann, cid, "before bob")
        circles.join(self.bob, circle["id"], circle["inviteCode"])
        self.assertEqual(chats.unread_totals(self.bob)["total"], 0)
        chats.send(self.ann, cid, "after bob")
        self.assertEqual(chats.unread_totals(self.bob)["total"], 1)

    def test_a_groups_own_notices_are_not_unread_messages(self):
        for other in (self.bob, self.cat):
            befriend(self.ann, other)
        chat = chats.create_group(self.ann, "G", [self.bob["id"], self.cat["id"]])
        chats.rename(self.ann, chat["id"], "Renamed")
        self.assertEqual(chats.unread_totals(self.bob)["total"], 0)
        self.assertEqual(chats.unread_totals(self.ann)["total"], 0)
        chats.send(self.cat, chat["id"], "a real message")
        self.assertEqual(chats.unread_totals(self.bob)["total"], 1)

    def test_a_bad_read_request_is_refused(self):
        self.assertEqual(err(chats.mark_read, self.ann, "global", "3").status, 400)
        self.assertEqual(err(chats.mark_read, self.ann, "global", True).status, 400)


if __name__ == "__main__":
    unittest.main()
