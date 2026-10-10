"""Friends, circle-mates as automatic friends, and who is online and what they are doing."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, poker, social, users          # noqa: E402
from backend.util import ApiError                          # noqa: E402
from tests.helpers import fresh_store, restore_store_path  # noqa: E402

T0 = 1_000_000


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


def ids_of(rows):
    return {r["username"] for r in rows}


class Requests(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.ann, self.bob, self.cat = mk("ann_x"), mk("bob_x"), mk("cat_x")

    def test_a_request_waits_until_it_is_answered(self):
        self.assertEqual(social.request(self.ann, "bob_x"), "requested")
        self.assertEqual(ids_of(social.view(self.ann)["outgoing"]), {"bob_x"})
        self.assertEqual(ids_of(social.view(self.bob)["incoming"]), {"ann_x"})
        self.assertEqual(social.view(self.ann)["friends"], [])
        self.assertEqual(social.view(self.bob)["friends"], [])

    def test_accepting_makes_both_of_them_friends_and_clears_the_request(self):
        social.request(self.ann, "bob_x")
        self.assertEqual(social.accept(self.bob, self.ann["id"]), "friends")
        self.assertEqual(ids_of(social.view(self.ann)["friends"]), {"bob_x"})
        self.assertEqual(ids_of(social.view(self.bob)["friends"]), {"ann_x"})
        for u in (self.ann, self.bob):
            v = social.view(u)
            self.assertEqual((v["incoming"], v["outgoing"]), ([], []))
        self.assertTrue(social.is_friend(self.ann["id"], self.bob["id"]) and social.is_friend(self.bob["id"], self.ann["id"]))

    def test_if_they_asked_first_asking_back_is_a_yes(self):
        social.request(self.ann, "bob_x")
        self.assertEqual(social.request(self.bob, "ann_x"), "friends")
        self.assertEqual(ids_of(social.view(self.ann)["friends"]), {"bob_x"})

    def test_declining_and_cancelling_leave_no_friendship_behind(self):
        social.request(self.ann, "bob_x")
        social.decline(self.bob, self.ann["id"])
        self.assertEqual((social.view(self.bob)["incoming"], social.view(self.ann)["outgoing"]), ([], []))
        social.request(self.ann, "cat_x")
        social.cancel(self.ann, self.cat["id"])
        self.assertEqual(social.view(self.cat)["incoming"], [])
        self.assertFalse(social.is_friend(self.ann["id"], self.bob["id"]) or social.is_friend(self.ann["id"], self.cat["id"]))

    def test_only_the_person_asked_can_accept_or_decline(self):
        social.request(self.ann, "bob_x")
        self.assertEqual(err(social.accept, self.cat, self.ann["id"]).status, 404)
        self.assertEqual(err(social.accept, self.ann, self.bob["id"]).status, 404)         # asking is not accepting
        self.assertEqual(err(social.decline, self.cat, self.ann["id"]).status, 404)
        self.assertEqual(err(social.cancel, self.bob, self.ann["id"]).status, 404)

    def test_the_sensible_refusals(self):
        self.assertIn("you", err(social.request, self.ann, "ann_x").message.lower())
        self.assertEqual(err(social.request, self.ann, "nobody_x").status, 404)
        social.request(self.ann, "bob_x")
        self.assertIn("already asked", err(social.request, self.ann, "bob_x").message)
        social.accept(self.bob, self.ann["id"])
        self.assertIn("already friends", err(social.request, self.ann, "bob_x").message)

    def test_usernames_are_found_whatever_the_case(self):
        self.assertEqual(social.request(self.ann, "BOB_X"), "requested")

    def test_removing_a_friend_ends_it_for_both(self):
        social.request(self.ann, "bob_x")
        social.accept(self.bob, self.ann["id"])
        social.remove(self.bob, self.ann["id"])
        self.assertEqual((social.view(self.ann)["friends"], social.view(self.bob)["friends"]), ([], []))
        self.assertIn("didn't add", err(social.remove, self.bob, self.ann["id"]).message)

    def test_there_are_limits_on_waiting_requests_and_how_fast_you_send_them(self):
        with mock.patch.object(social, "MAX_PENDING", 2):
            social.request(self.ann, "bob_x")
            social.request(self.ann, "cat_x")
            dan = mk("dan_x")
            self.assertIn("too many requests", err(social.request, self.ann, "dan_x").message)
            social.cancel(self.ann, self.bob["id"])
            social.request(self.ann, "dan_x")
            self.assertEqual(social.view(dan)["incoming"][0]["username"], "ann_x")
        fresh_store()
        a = mk("spammer")
        for i in range(22):
            mk(f"target{i:02d}")
        codes = []
        for i in range(22):
            try:
                social.request(a, f"target{i:02d}")
                codes.append(200)
            except ApiError as e:
                codes.append(e.status)
        self.assertEqual(codes[:20], [200] * 20)
        self.assertEqual(codes[20:], [429, 429])

    def test_search_finds_names_that_start_with_what_you_typed(self):
        mk("annabel")
        self.assertEqual(social.search(self.ann, "a"), [])                         # too short to bother anybody
        self.assertEqual({u["username"] for u in social.search(self.cat, "an")}, {"ann_x", "annabel"})
        self.assertEqual({u["username"] for u in social.search(self.ann, "an")}, {"annabel"})      # never yourself
        social.request(self.cat, "ann_x")
        self.assertEqual({u["username"] for u in social.search(self.cat, "an")}, {"annabel"})      # nor people already asked
        self.assertLessEqual(len(social.search(self.cat, "b")), 8)


class CircleMates(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.ann, self.bob, self.cat = mk("ann_x"), mk("bob_x"), mk("cat_x")
        self.circle = circles.create(self.ann, {"name": "Crew", "visibility": "private"})
        circles.join(self.bob, self.circle["id"], self.circle["inviteCode"])

    def test_people_in_a_circle_together_are_friends_without_asking(self):
        v = social.view(self.ann)
        self.assertEqual(ids_of(v["friends"]), {"bob_x"})
        row = v["friends"][0]
        self.assertEqual((row["added"], row["circles"]), (False, ["Crew"]))
        self.assertTrue(social.is_friend(self.bob["id"], self.ann["id"]))
        self.assertFalse(social.is_friend(self.ann["id"], self.cat["id"]))

    def test_a_new_member_is_everybodys_friend_and_leaving_ends_it(self):
        circles.join(self.cat, self.circle["id"], self.circle["inviteCode"])
        self.assertEqual(ids_of(social.view(self.cat)["friends"]), {"ann_x", "bob_x"})
        circles.leave(self.cat, self.circle["id"])
        self.assertEqual(social.view(self.cat)["friends"], [])
        self.assertEqual(ids_of(social.view(self.ann)["friends"]), {"bob_x"})

    def test_being_kicked_ends_it_too(self):
        circles.kick(self.ann, self.circle["id"], self.bob["id"])
        self.assertEqual(social.view(self.ann)["friends"], [])

    def test_a_friend_you_added_stays_after_the_circle_is_gone_and_a_circle_mate_cannot_be_removed(self):
        social.request(self.ann, "bob_x")
        social.accept(self.bob, self.ann["id"])
        row = social.view(self.ann)["friends"][0]
        self.assertEqual((row["added"], row["circles"]), (True, ["Crew"]))
        circles.leave(self.bob, self.circle["id"])
        self.assertEqual(ids_of(social.view(self.ann)["friends"]), {"bob_x"})              # still there: they added each other
        circles.join(self.bob, self.circle["id"], self.circle["inviteCode"])
        social.remove(self.ann, self.bob["id"])
        self.assertEqual(ids_of(social.view(self.ann)["friends"]), {"bob_x"})              # the circle keeps them friends
        self.assertIn("share a circle", err(social.remove, self.ann, self.bob["id"]).message)

    def test_every_circle_you_share_is_listed(self):
        other = circles.create(self.bob, {"name": "Work", "visibility": "public"})
        circles.join(self.ann, other["id"])
        self.assertEqual(sorted(social.view(self.ann)["friends"][0]["circles"]), ["Crew", "Work"])


class Presence(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.ann, self.bob, self.cat = mk("ann_x"), mk("bob_x"), mk("cat_x")
        social.request(self.ann, "bob_x")
        social.accept(self.bob, self.ann["id"])

    def bob_as_seen_by_ann(self, now):
        return next(r for r in social.view(self.ann, now)["friends"] if r["username"] == "bob_x")

    def test_nobody_is_online_until_their_browser_says_so(self):
        self.assertFalse(self.bob_as_seen_by_ann(T0)["online"])
        self.assertTrue(social.ping(self.bob, {"k": "markets"}, True, T0))
        row = self.bob_as_seen_by_ann(T0 + 1000)
        self.assertEqual((row["online"], row["where"]), (True, "Browsing markets"))

    def test_what_they_are_doing_is_a_short_fixed_phrase(self):
        for where, text in (({"k": "game", "v": "limbo"}, "Playing Limbo"), ({"k": "game", "v": "blackjack"}, "Playing Blackjack"),
                            ({"k": "game"}, "In the casino lobby"), ({"k": "market"}, "Looking at a bet"),
                            ({"k": "chat"}, "Chatting"), ({"k": "weekly"}, "Checking the weekly"), ({"k": "poker"}, "In the poker room")):
            social.ping(self.bob, where, True, T0)
            self.assertEqual(self.bob_as_seen_by_ann(T0)["where"], text)

    def test_nothing_a_browser_sends_can_put_its_own_words_in_front_of_a_friend(self):
        for junk in ({"k": "<script>alert(1)</script>"}, {"k": "game", "v": "<b>hax</b>"}, "just a string", None, {"k": ["x"]}, 42):
            social.ping(self.bob, junk, True, T0)
            self.assertIn(self.bob_as_seen_by_ann(T0)["where"], ("Around the site", "In the casino lobby"))

    def test_a_table_you_sit_at_is_only_ever_called_poker(self):
        social.ping(self.bob, {"k": "poker"}, True, T0)
        with mock.patch.object(poker, "table_of", return_value={"id": "secret-private-table"}):
            self.assertEqual(self.bob_as_seen_by_ann(T0)["where"], "Playing poker")

    def test_a_hidden_tab_shows_as_away_with_no_activity(self):
        social.ping(self.bob, {"k": "game", "v": "limbo"}, False, T0)
        row = self.bob_as_seen_by_ann(T0)
        self.assertEqual((row["online"], row["away"], row["where"]), (True, True, None))

    def test_two_missed_pings_and_they_are_offline_with_a_last_seen_time(self):
        social.ping(self.bob, {"k": "markets"}, True, T0)
        self.assertTrue(self.bob_as_seen_by_ann(T0 + social.ONLINE_MS - 1)["online"])
        row = self.bob_as_seen_by_ann(T0 + social.ONLINE_MS)
        self.assertEqual((row["online"], row["where"], row["seen"]), (False, None, T0))

    def test_the_sweep_names_whoever_just_went_quiet_once(self):
        social.ping(self.bob, {"k": "markets"}, True, T0)
        social.ping(self.cat, {"k": "markets"}, True, T0 + 60_000)
        self.assertEqual(social.sweep(T0 + 10_000), [])
        self.assertEqual(social.sweep(T0 + social.ONLINE_MS + 1), [self.bob["id"]])
        self.assertEqual(social.sweep(T0 + social.ONLINE_MS + 2), [])
        self.assertEqual(self.bob_as_seen_by_ann(T0 + social.ONLINE_MS + 3)["seen"], T0)         # and remembered when

    def test_only_a_real_change_is_worth_telling_friends_about(self):
        self.assertTrue(social.ping(self.bob, {"k": "markets"}, True, T0))                  # came online
        self.assertFalse(social.ping(self.bob, {"k": "markets"}, True, T0 + 30_000))        # still there
        self.assertTrue(social.ping(self.bob, {"k": "game", "v": "dice"}, True, T0 + 40_000))
        self.assertTrue(social.ping(self.bob, {"k": "game", "v": "dice"}, False, T0 + 50_000))
        self.assertTrue(social.ping(self.bob, {"k": "game", "v": "dice"}, True, T0 + social.ONLINE_MS * 3))   # back after a gap

    def test_appearing_offline_hides_everything_including_last_seen(self):
        social.ping(self.bob, {"k": "markets"}, True, T0)
        social.set_hidden(self.bob, True)
        row = self.bob_as_seen_by_ann(T0 + 1000)
        self.assertEqual((row["online"], row["where"], row["seen"]), (False, None, None))
        self.assertFalse(social.ping(self.bob, {"k": "chat"}, True, T0 + 2000))             # and nobody is told when they move
        social.set_hidden(self.bob, False)
        self.assertTrue(self.bob_as_seen_by_ann(T0 + 3000)["online"])
        self.assertIn("on or off", err(social.set_hidden, self.bob, "yes").message)

    def test_online_people_come_first_and_the_count_is_right(self):
        circles.join(self.cat, circles.create(self.ann, {"name": "Crew", "visibility": "public"})["id"])
        social.ping(self.cat, {"k": "markets"}, True, T0)
        v = social.view(self.ann, T0 + 1000)
        self.assertEqual([r["username"] for r in v["friends"]], ["cat_x", "bob_x"])
        self.assertEqual(v["online"], 1)

    def test_strangers_do_not_show_up_in_anyones_view(self):
        dan = mk("dan_x")
        social.ping(dan, {"k": "markets"}, True, T0)
        self.assertNotIn("dan_x", ids_of(social.view(self.ann, T0)["friends"]))
        self.assertEqual(social.friend_ids(dan["id"]), set())


if __name__ == "__main__":
    unittest.main()
