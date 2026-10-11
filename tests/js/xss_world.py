"""A small world where everything people can type holds HTML that would run if a screen pasted it in unescaped.

Used by tests/js/html_seguro.test.mjs: each payload sets window.xss to its own number when it runs, so a failure says which field
leaked. Run with DATA_DIR pointing at an empty scratch folder:
    DATA_DIR=/tmp/x python -c "from backend.store import store; store.load(); from tests.js import xss_world; xss_world.seed(); store.save()"
"""
import json

from backend import chats, circles, cosmetics, markets, social, users, weekly
from backend.store import db

PASSWORD = "testpass123"


def bad(n):
    return f"<img src=x onerror=xss={n}>"


FIELDS = {
    1: "circle name", 2: "circle description", 3: "market question", 4: "market description", 5: "outcome name",
    6: "comment", 7: "chat message", 8: "group chat name", 9: "punishment", 10: "bio",
}


def seed():
    chats._slow_down = lambda uid: None
    t = users.register("tester", PASSWORD)
    amy = users.register("amy", PASSWORD)
    bob = users.register("bob", PASSWORD)
    for u in (t, amy, bob):
        u["mail"] = {"addr": f"{u['username']}@example.com", "verified": True}
    for a, b in ((t, amy), (bob, amy)):
        social.request(a, b["username"]); social.accept(b, a["id"])

    crew = circles.create(amy, {"name": "Crew " + bad(1), "description": "About us " + bad(2)})
    circles.join_by_code(t, crew["inviteCode"])
    yes_no = markets.create(amy, {"circleId": crew["id"], "question": "Pizza by nine? " + bad(3), "description": "Rules " + bad(4)})
    multi = markets.create(amy, {"circleId": crew["id"], "question": "Who wins it all?", "outcomes": ["Ana " + bad(5), "Beto"]})
    markets.add_comment(amy, db()["markets"][yes_no["id"]], "Easy money " + bad(6))
    markets.trade(t, db()["markets"][yes_no["id"]], {"outcome": 0, "amount": 10, "requestId": "seed-xss-trade-0001"})
    chats.send(amy, "global", "hello " + bad(7))
    chats.create_group(amy, "Group " + bad(8), [t["id"], bob["id"]])
    weekly.add_punishment(amy, db()["circles"][crew["id"]], "Sing " + bad(9))
    cosmetics.customize(amy, {"bio": "Hi " + bad(10)})
    return {"circle": crew["id"], "market": yes_no["id"], "multi": multi["id"]}


if __name__ == "__main__":
    print(json.dumps(seed()))
