"""The global ranking: everybody who is registered on the site, by the money in their accumulated account.

Not the weekly leaderboard (that one is per circle, about the week, and resets). This one is lifetime money, the same for everybody who is
signed in. Only the account's cash counts (shares are not cash). People who are suspended or deleted are left out, and so is the practice
wallet, which is not an account. Equal money shares a place ("1, 2, 2, 4"), and people with the same money are listed oldest account first."""
from . import ledger, users
from .store import db


def board(viewer):
    rows = []
    for u in db()["users"].values():
        if u.get("suspended") or u.get("deleted"):
            continue
        rows.append((ledger.balance_c(u, "accumulated"), u))
    rows.sort(key=lambda r: (-r[0], r[1].get("createdAt", 0), r[1]["username"].lower()))      # the richest first: place 1
    people, place, last = [], 0, None
    for i, (c, u) in enumerate(rows):
        if c != last:
            place, last = i + 1, c
        people.append({**users.public(u), "place": place, "accum": c / 100, "isMe": u["id"] == viewer["id"], "since": u.get("createdAt", 0)})
    me = next((p for p in people if p["isMe"]), None)
    return {"people": people, "count": len(people), "myPlace": me["place"] if me else None,
            "richest": people[0]["accum"] if people else 0.0, "poorest": people[-1]["accum"] if people else 0.0}
