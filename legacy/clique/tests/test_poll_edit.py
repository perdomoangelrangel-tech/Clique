"""Editing a published poll: who may, what is checked, what is shown first, the history, who is told, and what happens to bets."""
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                          # noqa: E402
from backend import circles, economy, ledger, markets, users           # noqa: E402
from backend.store import db, store                                    # noqa: E402
from backend.util import ApiError, now_ms                              # noqa: E402
from tests.econ import books_balance, circle_of, mk                    # noqa: E402
from tests.helpers import fresh_store, restore_store_path              # noqa: E402
from tests.test_http import Client                                     # noqa: E402

H = 3600 * 1000
DAY = 24 * H


def tearDownModule():
    restore_store_path()


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ApiError as e:
        return e
    raise AssertionError("expected an ApiError")


class Base(unittest.TestCase):
    def setUp(self):
        fresh_store()
        self.owner = mk("owner")
        self.maker = mk("maker")
        self.bettor = mk("bettor")
        self.other = mk("other")
        self.circle = circle_of(self.owner, self.maker, self.bettor, self.other)
        self.m = markets.create(self.maker, {"circleId": self.circle["id"], "question": "Will the cake survive the party?",
                                             "description": "Counts if there is any cake left at midnight.", "closesAt": now_ms() + 3 * DAY})

    def bet(self, who, amount=100, outcome=0):
        return markets.trade(who, self.m, {"outcome": outcome, "amount": amount})

    def edit(self, who=None, **body):
        return markets.edit_apply(who or self.maker, self.m, body)


class WhoMayEdit(Base):
    def test_the_proposer_and_the_circle_owner_may_and_nobody_else(self):
        self.assertTrue(markets.can_edit(self.m, self.maker))
        self.assertTrue(markets.can_edit(self.m, self.owner))
        self.assertFalse(markets.can_edit(self.m, self.bettor))
        self.assertFalse(markets.can_edit(self.m, self.other))
        e = err(self.edit, self.bettor, description="mine now")
        self.assertEqual(e.status, 403)
        self.assertEqual(self.m["description"], "Counts if there is any cake left at midnight.")
        self.assertEqual(self.m.get("edits"), None)
        self.edit(self.owner, description="Counts if cake remains at midnight.")
        self.assertEqual(self.m["version"], 2)

    def test_on_a_public_bet_only_the_proposer_can_edit(self):
        pub = markets.create(self.maker, {"scope": "site", "question": "Will it rain on the picnic?"})
        self.assertTrue(markets.can_edit(pub, self.maker))
        self.assertFalse(markets.can_edit(pub, self.owner))
        self.assertEqual(err(markets.edit_apply, self.owner, pub, {"description": "x"}).status, 403)

    def test_people_who_are_not_in_a_private_circle_can_not_even_see_it(self):
        outsider = mk("outsider")
        self.circle["visibility"] = "private"
        self.assertEqual(err(markets.view_or_404, self.m["id"], outsider).status, 404)

    def test_the_page_is_told_who_can_edit(self):
        self.assertTrue(markets.summary(self.m, self.maker)["canEdit"])
        self.assertTrue(markets.summary(self.m, self.owner)["canEdit"])
        self.assertFalse(markets.summary(self.m, self.bettor)["canEdit"])
        self.assertFalse(markets.summary(self.m, None)["canEdit"])


class WhenItIsAllowed(Base):
    def test_a_settled_or_cancelled_bet_can_not_be_edited_and_says_why(self):
        self.bet(self.bettor)
        markets.resolve(self.maker, self.m, 0)
        paid = {u["username"]: u["balance"] for u in (self.bettor, self.maker)}
        e = err(self.edit, description="Actually it meant something else")
        self.assertEqual(e.status, 409)
        self.assertIn("settled", e.message)
        self.assertIn("can not be reopened", e.message)
        self.assertEqual(self.m["winner"], 0)
        self.assertEqual(self.m["status"], "resolved")
        self.assertEqual({u["username"]: u["balance"] for u in (self.bettor, self.maker)}, paid)
        fresh = markets.create(self.maker, {"circleId": self.circle["id"], "question": "Will this one be cancelled?"})
        markets.cancel(self.maker, fresh)
        e = err(markets.edit_apply, self.maker, fresh, {"description": "x"})
        self.assertEqual(e.status, 409)
        self.assertIn("cancelled", e.message)

    def test_a_bet_whose_time_is_up_but_not_yet_settled_can_still_be_corrected(self):
        self.m["closesAt"] = now_ms() - 1000
        self.assertEqual(markets.state_of(self.m), "closed")
        r = self.edit(closesAt=now_ms() + 2 * DAY)
        self.assertEqual(r["class"], "no_participation")
        self.assertEqual(markets.state_of(self.m), "open")

    def test_nothing_to_change_is_an_error(self):
        self.assertIn("Nothing would change", err(self.edit).message)
        self.assertIn("Nothing would change", err(self.edit, description="Counts if there is any cake left at midnight.").message)
        self.assertIn("Nothing would change", err(self.edit, closesAt=self.m["closesAt"]).message)


class DateChecks(Base):
    def test_the_new_time_must_be_in_the_future_and_not_absurd(self):
        for bad_value in (now_ms() - 5000, now_ms() + 60_000, now_ms() + 299_000, "soon", True, [1], {"a": 1}, float("nan")):
            e = err(self.edit, closesAt=bad_value)
            self.assertEqual(e.status, 400, bad_value)
        self.assertIn("too far away", err(self.edit, closesAt=now_ms() + 6 * 365 * DAY).message)
        self.assertEqual(self.m["version"] if "version" in self.m else 1, 1)
        r = self.edit(closesAt=now_ms() + 6 * 60_000)
        self.assertEqual(r["version"], 2)

    def test_an_end_date_can_be_removed_and_added_back(self):
        self.edit(closesAt=None)
        self.assertIsNone(self.m["closesAt"])
        self.edit(closesAt=now_ms() + DAY)
        self.assertTrue(self.m["closesAt"])
        self.assertEqual(self.m["version"], 3)

    def test_the_rules_must_be_text_and_are_kept_to_a_thousand_characters(self):
        self.assertEqual(err(self.edit, description=["no"]).status, 400)
        self.edit(description="x" * 1500)
        self.assertEqual(len(self.m["description"]), 1000)
        self.edit(description="")
        self.assertEqual(self.m["description"], "")


class BeforeAnybodyHasBet(Base):
    def test_a_change_is_simple_versioned_and_logged(self):
        r = self.edit(closesAt=now_ms() + 5 * DAY, description="New rules.")
        self.assertEqual((r["class"], r["version"], r["notified"], r["exitUntil"]), ("no_participation", 2, 0, None))
        self.assertEqual(self.m["description"], "New rules.")
        h = markets.history(self.m, self.bettor)
        self.assertEqual([e["v"] for e in h["edits"]], [1, 2])
        self.assertEqual(h["edits"][1]["by"]["username"], "maker")
        self.assertEqual(set(h["edits"][1]["changes"]), {"closesAt", "description"})
        self.assertIsNone(self.m.get("exit"))

    def test_no_reason_is_needed_but_one_is_kept_if_given(self):
        self.edit(description="A")
        self.edit(description="B", reason="Tidying the wording")
        self.assertEqual([e["reason"] for e in self.m["edits"]], ["", "Tidying the wording"])

    def test_the_proposers_own_bet_does_not_count_as_other_peoples_bets(self):
        self.bet(self.maker)
        r = self.edit(description="Counts only if the cake was chocolate.")
        self.assertEqual(r["class"], "no_participation")
        self.assertNotIn("pre", self.m["positions"][self.maker["id"]]["y0"])


class WhenPeopleHaveBet(Base):
    def setUp(self):
        super().setUp()
        self.bet(self.bettor, 100)
        self.bet(self.other, 60, outcome=1)

    def test_a_reason_is_required_and_nothing_changes_without_one(self):
        e = err(self.edit, description="Changed.")
        self.assertIn("say why", e.message)
        self.assertEqual(err(self.edit, description="Changed.", reason="short").status, 400)
        self.assertEqual(self.m["description"], "Counts if there is any cake left at midnight.")
        self.assertNotIn("edits", self.m)

    def test_changing_the_date_is_always_material(self):
        e = err(self.edit, closesAt=now_ms() + 9 * DAY, reason="The party was moved to next week", kind="clarification")
        self.assertIn("can not be a clarification", e.message)
        r = self.edit(closesAt=now_ms() + 9 * DAY, reason="The party was moved to next week")
        self.assertEqual(r["class"], "material")

    def test_a_wording_fix_declared_as_a_clarification_is_not_material(self):
        r = self.edit(description="Counts if any cake remains at midnight (a single slice is enough).", reason="Making 'any' explicit", kind="clarification")
        self.assertEqual((r["class"], r["notified"]), ("clarification", 2))
        self.assertNotIn("exit", self.m)
        for pos in self.m["positions"].values():
            for p in pos.values():
                self.assertNotIn("pre", p)

    def test_rules_changes_that_are_not_declared_clarifications_are_material(self):
        for kind in (None, "material"):
            fresh = markets.create(self.maker, {"circleId": self.circle["id"], "question": f"Test {kind}?"})
            markets.trade(self.bettor, fresh, {"outcome": 0, "amount": 10})
            r = markets.edit_apply(self.maker, fresh, {"description": "Now it means something new.", "reason": "A very different meaning", "kind": kind})
            self.assertEqual(r["class"], "material")

    def test_a_material_change_opens_an_exit_window_and_marks_what_was_bet_under_the_old_rules(self):
        t0 = now_ms()
        r = self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        self.assertEqual((r["class"], r["notified"]), ("material", 2))
        self.assertAlmostEqual(r["exitUntil"], t0 + 48 * H, delta=5000)
        self.assertTrue(markets.exit_open(self.m))
        pos = self.m["positions"][self.bettor["id"]]["y0"]
        self.assertEqual(pos["pre"], {"sh": pos["shares"], "v": 1})
        rows = markets.detail(self.m, self.bettor)["myPositions"]
        self.assertEqual((rows[0]["version"], rows[0]["underOldRules"], rows[0]["withdrawable"]), (1, True, True))
        self.assertEqual(markets.detail(self.m, self.bettor)["exit"]["open"], True)

    def test_new_bets_after_the_change_are_under_the_new_rules_and_can_not_be_withdrawn(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        late = mk("late")
        circles.join_by_code(late, self.circle["inviteCode"])
        markets.trade(late, self.m, {"outcome": 0, "amount": 50})
        p = self.m["positions"][late["id"]]["y0"]
        self.assertEqual(p["v"], 2)
        self.assertNotIn("pre", p)
        self.assertEqual(err(markets.withdraw, late, self.m, {"token": "y0"}).status, 404)

    def test_a_holder_can_walk_away_at_exactly_what_they_paid(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        pos = self.m["positions"][self.bettor["id"]]["y0"]
        before = self.bettor["balance"]
        q_before = list(self.m["q"])
        out = markets.withdraw(self.bettor, self.m, {"token": "y0"})
        self.assertEqual(out["refunded"], 100.0)
        self.assertEqual(self.bettor["balance"], round(before + 100.0, 2))
        self.assertNotIn(self.bettor["id"], self.m["positions"])
        self.assertLess(self.m["q"][0], q_before[0], "the shares leave the market")
        row = ledger.entries(self.bettor)[0]
        self.assertEqual((row["account"], row["reason"], row["amount"], row["ref"]), ("weekly", "market.withdraw", 100.0, self.m["id"]))
        self.assertTrue(books_balance(self.bettor))
        self.assertEqual(self.m["trades"][-1]["k"], "withdraw")
        self.assertEqual(err(markets.withdraw, self.bettor, self.m, {"token": "y0"}).status, 404, "only once")

    def test_a_retry_of_the_withdrawal_with_the_same_id_refunds_once(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        a = markets.withdraw(self.bettor, self.m, {"token": "y0", "requestId": "withdraw-0001"})
        b = markets.withdraw(self.bettor, self.m, {"token": "y0", "requestId": "withdraw-0001"})
        self.assertEqual((a["duplicate"], b["duplicate"]), (False, True))
        self.assertEqual(len([r for r in ledger.entries(self.bettor) if r["reason"] == "market.withdraw"]), 1)

    def test_what_is_refunded_is_the_cost_not_what_the_price_became(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        self.bet(self.other, 400, outcome=0)                                         # drives the price of YES up
        row = markets.detail(self.m, self.bettor)["myPositions"][0]
        self.assertGreater(row["value"], 100.0)
        out = markets.withdraw(self.bettor, self.m, {"token": "y0"})
        self.assertEqual(out["refunded"], 100.0)

    def test_the_window_closes_and_then_the_bet_stands(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        self.m["exit"]["until"] = now_ms() - 1
        self.assertFalse(markets.exit_open(self.m))
        e = err(markets.withdraw, self.bettor, self.m, {"token": "y0"})
        self.assertEqual(e.status, 409)
        self.assertIn("ended", e.message)
        self.assertTrue(self.m["positions"][self.bettor["id"]]["y0"]["shares"] > 0)
        self.assertFalse(markets.detail(self.m, self.bettor)["myPositions"][0]["withdrawable"])

    def test_the_proposer_can_not_use_the_exit_to_escape_their_own_bad_bet(self):
        self.bet(self.maker, 80)
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        self.assertNotIn("pre", self.m["positions"][self.maker["id"]]["y0"])
        self.assertEqual(err(markets.withdraw, self.maker, self.m, {"token": "y0"}).status, 404)

    def test_only_one_material_change_once_people_have_bet(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        e = err(self.edit, closesAt=now_ms() + 20 * DAY, reason="Moving the date again, sorry")
        self.assertEqual(e.status, 409)
        self.assertIn("only be clarifications", e.message)
        r = self.edit(description="Counts only if the cake was chocolate (any chocolate).", reason="Wording only", kind="clarification")
        self.assertEqual(r["class"], "clarification")
        self.assertEqual(self.m["version"], 3)

    def test_people_need_a_day_to_react_if_the_date_is_brought_forward(self):
        e = err(self.edit, closesAt=now_ms() + 2 * H, reason="Ending it early because of the weather")
        self.assertIn("at least a day", e.message)
        e = err(self.edit, closesAt=now_ms() + 30 * H, reason="Ending it early because of the weather")
        self.assertIn("exit window", e.message)
        r = self.edit(closesAt=now_ms() + 2.5 * DAY, reason="Ending it a little early, the party is Friday")
        self.assertEqual(r["class"], "material")

    def test_existing_bets_balances_and_history_are_untouched_by_an_edit(self):
        before = {u["username"]: (u["balance"], u["accum"]) for u in (self.bettor, self.other, self.maker)}
        shares = {uid: {t: p["shares"] for t, p in toks.items()} for uid, toks in self.m["positions"].items()}
        trades = list(self.m["trades"])
        q = list(self.m["q"])
        self.edit(closesAt=now_ms() + 9 * DAY, description="Moved a week.", reason="The party moved to next week")
        self.assertEqual({u["username"]: (u["balance"], u["accum"]) for u in (self.bettor, self.other, self.maker)}, before)
        self.assertEqual({uid: {t: p["shares"] for t, p in toks.items()} for uid, toks in self.m["positions"].items()}, shares)
        self.assertEqual(self.m["trades"], trades)
        self.assertEqual(self.m["q"], q)
        self.assertEqual(self.m["status"], "open")

    def test_a_clarification_never_gives_anyone_a_way_out(self):
        self.edit(description="Counts if any cake is left at midnight (even crumbs).", reason="Clearer words", kind="clarification")
        self.assertEqual(err(markets.withdraw, self.bettor, self.m, {"token": "y0"}).status, 409)

    def test_the_settlement_after_an_edit_pays_under_the_current_rules_and_nothing_is_lost(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        markets.withdraw(self.bettor, self.m, {"token": "y0"})
        markets.resolve(self.maker, self.m, 1)
        self.assertEqual(self.m["status"], "resolved")
        self.assertGreater(self.other["balance"], 940.0)
        for u in (self.bettor, self.other):
            self.assertTrue(books_balance(u))


class WhoIsTold(Base):
    def setUp(self):
        super().setUp()
        self.bet(self.bettor, 100)
        self.bet(self.other, 60, outcome=1)
        self.lurker = mk("lurker")
        circles.join_by_code(self.lurker, self.circle["inviteCode"])

    def test_everybody_involved_is_told_and_nobody_else(self):
        self.edit(description="Counts only if the cake was chocolate.", reason="Different cake, different bet")
        for u in (self.bettor, self.other):
            note = u["activity"][0]
            self.assertEqual((note["kind"], note["ref"]), ("edit", self.m["id"]))
            self.assertIn("rules", note["text"])
            self.assertIn("material", note["text"])
        self.assertIn("withdraw", self.bettor["activity"][0]["text"])
        self.assertNotEqual(self.maker["activity"][0]["kind"], "edit", "the editor does not notify themselves")
        self.assertNotEqual(self.lurker["activity"][0]["kind"], "edit")

    def test_somebody_who_sold_out_but_traded_is_still_told(self):
        markets.trade(self.bettor, self.m, {"outcome": 0, "action": "sell", "all": True})
        self.edit(closesAt=now_ms() + 9 * DAY, reason="Moving the date for everyone")
        self.assertEqual(self.bettor["activity"][0]["kind"], "edit")
        self.assertNotIn("withdraw", self.bettor["activity"][0]["text"], "they have no bet left to withdraw")

    def test_a_clarification_is_announced_as_one(self):
        self.edit(description="Counts if any cake is left at midnight (even crumbs).", reason="Clearer words", kind="clarification")
        self.assertIn("clarified", self.bettor["activity"][0]["text"])
        self.assertNotIn("material", self.bettor["activity"][0]["text"])


class TheHistory(Base):
    def test_everybody_who_can_see_the_bet_can_read_every_version(self):
        self.bet(self.bettor)
        self.edit(closesAt=now_ms() + 9 * DAY, description="Moved a week.", reason="The party moved to next week")
        self.edit(description="Moved a week (still the same cake).", reason="Wording only", kind="clarification")
        h = markets.history(self.m, self.other)
        self.assertEqual((h["version"], [e["v"] for e in h["edits"]], [e["class"] for e in h["edits"]]), (3, [1, 2, 3], ["created", "material", "clarification"]))
        e2 = h["edits"][1]
        self.assertEqual(e2["by"]["username"], "maker")
        self.assertEqual(e2["reason"], "The party moved to next week")
        self.assertEqual(e2["changes"]["description"]["from"], "Counts if there is any cake left at midnight.")
        self.assertEqual(e2["changes"]["description"]["to"], "Moved a week.")
        self.assertTrue(e2["changes"]["closesAt"]["to"] > e2["changes"]["closesAt"]["from"])
        self.assertTrue(e2["exitUntil"])
        self.assertTrue(e2["t"] >= self.m["createdAt"])
        self.assertEqual(h["policy"]["exitHours"], 48)

    def test_the_bet_is_marked_edited_and_says_when(self):
        self.assertFalse(markets.summary(self.m, self.maker)["edited"])
        self.edit(description="A new wording.")
        s = markets.summary(self.m, self.bettor)
        self.assertEqual((s["edited"], s["version"]), (True, 2))
        self.assertTrue(s["lastEditedAt"])
        self.assertEqual(markets.detail(self.m, self.bettor)["editCount"], 1)

    def test_the_history_survives_a_restart(self):
        self.edit(description="A new wording.", reason="Because")
        saved = __import__("json").dumps(store.data)
        store.data = __import__("json").loads(saved)
        store.load()
        m = store.data["markets"][self.m["id"]]
        self.assertEqual([e["v"] for e in markets.history(m, None)["edits"]], [1, 2])


class ThePreviewShowsExactlyWhatWillHappen(Base):
    def test_before_saving_you_see_the_changes_the_class_the_people_told_and_the_window(self):
        self.bet(self.bettor, 100)
        self.bet(self.other, 60, outcome=1)
        body = {"closesAt": now_ms() + 9 * DAY, "description": "Moved a week.", "reason": "The party moved to next week"}
        p = markets.edit_preview(self.maker, self.m, body)
        self.assertEqual((p["class"], p["version"], p["newVersion"], p["notifyCount"], p["exitHours"]), ("material", 1, 2, 2, 48))
        self.assertEqual(sorted(p["notify"]), ["bettor", "other"])
        self.assertEqual(set(p["changes"]), {"closesAt", "description"})
        self.assertEqual(p["changes"]["description"], {"from": "Counts if there is any cake left at midnight.", "to": "Moved a week."})
        self.assertTrue(p["reasonRequired"])
        self.assertIn("material change", p["note"])
        self.assertEqual(self.m.get("version", 1), 1, "a preview changes nothing")
        self.assertNotIn("edits", self.m)
        self.assertEqual(self.bettor["activity"][0]["kind"], "buy")
        r = markets.edit_apply(self.maker, self.m, body)
        self.assertEqual((r["class"], r["notified"], r["version"]), (p["class"], p["notifyCount"], p["newVersion"]))

    def test_a_preview_applies_the_same_rules_as_a_save(self):
        self.bet(self.bettor, 100)
        e = err(markets.edit_preview, self.maker, self.m, {"description": "x"})
        self.assertIn("say why", e.message)
        self.assertEqual(err(markets.edit_preview, self.bettor, self.m, {"description": "x"}).status, 403)

    def test_a_retry_with_the_same_request_id_saves_once(self):
        a = self.edit(description="One.", requestId="edit-0000001")
        b = self.edit(description="One.", requestId="edit-0000001")
        self.assertEqual((a["duplicate"], b["duplicate"], self.m["version"]), (False, True, 2))
        self.assertEqual(err(self.edit, description="Two.", requestId="bad id").message, "Invalid request id")


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

    def test_edit_preview_history_and_withdraw_through_the_server(self):
        a, b = Client(self.port), Client(self.port)
        a.call("POST", "/api/auth/register", {"username": "proposer", "password": "secret123"})
        b.call("POST", "/api/auth/register", {"username": "gambler", "password": "secret123"})
        st, c = a.call("POST", "/api/circles", {"name": "Edits", "visibility": "public"})
        cid = c["circle"]["id"]
        b.call("POST", f"/api/circles/{cid}/join", {})
        st, m = a.call("POST", "/api/markets", {"circleId": cid, "question": "Will the test pass?", "description": "Rules v1."})
        mid = m["market"]["id"]
        self.assertTrue(m["market"]["canEdit"])
        st, d = b.call("GET", f"/api/markets/{mid}")
        self.assertFalse(d["market"]["canEdit"])
        self.assertEqual(b.call("POST", f"/api/markets/{mid}/edit", {"description": "hijack"})[0], 403)
        b.call("POST", f"/api/markets/{mid}/trade", {"outcome": 0, "amount": 50})
        body = {"description": "Rules v2: now with a twist.", "reason": "The twist matters to the result"}
        st, p = a.call("POST", f"/api/markets/{mid}/edit/preview", body)
        self.assertEqual((st, p["preview"]["class"], p["preview"]["notifyCount"], p["preview"]["exitHours"]), (200, "material", 1, 48))
        st, d = a.call("GET", f"/api/markets/{mid}")
        self.assertEqual(d["market"]["version"], 1, "the preview saved nothing")
        st, r = a.call("POST", f"/api/markets/{mid}/edit", body)
        self.assertEqual((st, r["edit"]["class"], r["market"]["version"], r["market"]["edited"]), (200, "material", 2, True))
        self.assertEqual(r["market"]["rules"], "Rules v2: now with a twist.")
        st, h = b.call("GET", f"/api/markets/{mid}/history")
        self.assertEqual((st, [e["v"] for e in h["edits"]]), (200, [1, 2]))
        self.assertTrue(h["exit"]["open"])
        st, d = b.call("GET", f"/api/markets/{mid}")
        self.assertTrue(d["market"]["myPositions"][0]["withdrawable"])
        st, w = b.call("POST", f"/api/markets/{mid}/withdraw", {"token": d["market"]["myPositions"][0]["token"]})
        self.assertEqual((st, w["refunded"], w["user"]["weekly"]), (200, 50.0, 1000.0))
        self.assertEqual(b.call("POST", f"/api/markets/{mid}/withdraw", {"token": "y0"})[0], 404)
        st, me = b.call("GET", "/api/me")
        st, pf = b.call("GET", "/api/portfolio")
        self.assertTrue([x for x in pf["activity"] if x["kind"] == "edit"])
        self.assertEqual(a.call("POST", f"/api/markets/{mid}/resolve", {"outcome": 0})[0], 200)
        self.assertEqual(a.call("POST", f"/api/markets/{mid}/edit", {"description": "nope"})[0], 409)
        self.assertEqual(Client(self.port).call("GET", f"/api/markets/{mid}/history")[0], 401)


if __name__ == "__main__":
    unittest.main()
