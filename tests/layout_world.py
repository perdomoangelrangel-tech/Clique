"""A small world made to stress layouts: long names, a huge balance, long questions, twelve outcomes, a circle with a very long name, friends, chat,
a loan. Used by the browser checks in tests/test_layout.py (and handy for looking at the screens by hand: see tests/layout/README.md)."""
from backend import activity, challenges, chats, circles, ledger, loans, markets, progress, social, transfers, users
from backend.store import db
from backend.util import DAY_MS, now_ms, week_bounds, week_key

PASSWORD = "testpass123"
LONG_NAME = "the_very_long_name_1"                              # 20 characters: the longest a username can be


def person(name, accum=0, age_days=12):
    u = users.register(name, PASSWORD)
    u["createdAt"] -= age_days * DAY_MS
    u["mail"] = {"addr": f"{name.lower()}@example.com", "verified": True}
    if accum:
        ledger.post(u, "accumulated", accum, "test.setup")
    return u


def seed():
    """Fills the (empty) current store. Returns the people and ids the checks need."""
    chats._slow_down = lambda uid: None                        # (the chat rate limit has nothing to do with layout)
    t = person("tester", 640)
    big = person(LONG_NAME, 131086490.29)                      # the size of the largest real balance
    amy, bob, cat, dan, eve = (person(n, 300) for n in ("amy", "bob", "cat", "dan", "eve"))
    for a, b in ((t, amy), (t, bob), (big, t), (big, amy)):
        social.request(a, b["username"]); social.accept(b, a["id"])
    social.request(dan, "tester")                              # a friend request waiting

    crew = circles.create(t, {"name": "The Crew", "emoji": "\U0001F3AF"})
    long_c = circles.create(big, {"name": "The Extremely Long Named Circle Of Frie", "description": "A circle with a description that goes on and on, to see how the cards and headers cope when somebody writes a paragraph instead of a sentence about it.", "emoji": "\U0001F9E0"})
    for u in (amy, bob, cat, dan, eve, big):
        circles.join_by_code(u, crew["inviteCode"])
    for u in (t, amy, bob):
        circles.join_by_code(u, long_c["inviteCode"])

    q1 = markets.create(amy, {"circleId": crew["id"], "question": "Will the pizza arrive before nine?", "description": "Counts when the doorbell rings."})
    q2 = markets.create(bob, {"circleId": crew["id"], "question": "Will the group chat survive another argument about who left the oven on and whose turn it is to pay for the pizza tonight?", "category": "Life"})
    q3 = markets.create(amy, {"circleId": crew["id"], "question": "Who wins the tournament final on Sunday?", "outcomes": [f"Contestant number {i} with a long name" for i in range(1, 13)]})
    markets.create(bob, {"scope": "site", "question": "Does anybody read this?", "category": "Life"})
    q5 = markets.create(big, {"circleId": long_c["id"], "question": "Which of the very long outcome labels is longest?", "outcomes": ["Short", "Medium length answer here", "An extremely long outcome label, forty"]})
    for u, m, o, amt in ((t, q1, 0, 40), (amy, q1, 1, 80), (bob, q1, 0, 30), (t, q2, 1, 25), (big, q2, 0, 400), (t, q3, 3, 20), (bob, q3, 5, 15), (big, q5, 2, 300)):
        markets.trade(u, db()["markets"][m["id"]], {"outcome": o, "amount": amt, "requestId": f"seed-{u['username']}-{m['id']}-{o}"})

    start, _end = week_bounds(week_key())
    for i, game in enumerate(("dice", "limbo", "chicken")):
        activity.record(t, "casino", f"seed{i}", now=start + i * DAY_MS + 12 * 3600000, amount=5, game=game)
    progress.grant(t, 640, "seed", "seed-xp")
    progress.grant(big, 40000, "seed", "seed-xp")
    ledger.post(t, "weekly", -520, "test.setup")
    t["wk"]["start_c"] = ledger.to_cents(markets.net_worth(t)) + 52000
    loans.borrow(t, 120, "seed-loan-1")
    transfers.set_password(t, PASSWORD, "xfer-pass-1")
    challenges.assign(week_key())

    for u, text in ((amy, "who is up for poker tonight?"), (bob, "always. bring snacks"), (big, "W" * 70),
                    (t, "a long message with a link-like string https://example.com/this/is/a/very/long/path/that/should/never/widen/the/page?and=a&very=long&query=string"), (amy, "short")):
        chats.send(u, "global", text)
    dm = chats.open_dm(t, amy["id"])
    chats.send(amy, dm["id"] if isinstance(dm, dict) else dm, "hey! did you see the new game?")
    chats.create_group(t, "A group chat name that goes on and on ok", [amy["id"], bob["id"]])
    return {"tester": t, "amy": amy, "bob": bob}
