"""A vote on added funds.

Whoever uses the host's "Add funds" box (the one that needs the funds password) does not get the money at once. Everybody else is asked, with a
pop-up, whether they are in favor or against, and the money stays on hold (it is in no account, so nobody can spend it) until the vote is over:

  * the vote ends as soon as the result cannot change any more (the lead is bigger than the number of people who have not voted yet), when
    everybody has voted, or after economy.FUNDS_VOTE_HOURS (24 by default), whichever comes first;
  * more in favor than against: the money is added to the account that was chosen, exactly as the box always did (it is external money, so it
    is never winnings). Anything else, a tie and nobody voting included: nothing is added, and nothing was ever taken from anybody;
  * the people asked are everybody who has an account when the request is made, except the person asking and anybody suspended or deleted.
    If there is nobody to ask, the money is added at once;
  * one request at a time per person, and every vote is final. While a vote is open people only see how many have voted, not how; the
    database keeps who voted what for the host.

The password check is the one the box always had (users.check_deposit), so a wrong password never starts a vote.
"""
from . import economy, inbox, users
from .store import db
from .util import bad, new_id, now_ms, round2

HOUR_MS = 3_600_000


def _all():
    return db().setdefault("fundvotes", {})


def _user(uid):
    return db()["users"].get(uid)


def _money(x):
    return f"${x:,.2f}"


def _eligible(proposer):
    return [uid for uid, u in db()["users"].items() if uid != proposer["id"] and not u.get("suspended") and not u.get("deleted")]


def tally(v):
    """(in favor, against, still to vote)."""
    yes = sum(1 for x in v["votes"].values() if x)
    no = len(v["votes"]) - yes
    return yes, no, len(v["voters"]) - len(v["votes"])


def _outcome(v, final):
    """"approved", "rejected", or None while the result could still change. `final`: the time is up (whoever has not voted has not voted)."""
    yes, no, left = tally(v)
    if final or left == 0:
        return "approved" if yes > no else "rejected"
    if yes > no + left:
        return "approved"
    if no >= yes + left:
        return "rejected"
    return None


def open_for(user):
    return next((v for v in _all().values() if v["userId"] == user["id"] and v["status"] == "open"), None)


def propose(user, amount, password, account="weekly"):
    """Starts a vote on adding `amount` to the person's account. Returns the vote (already closed, and the money added, when there was nobody to ask)."""
    amount, account = users.check_deposit(user, amount, password, account)
    if open_for(user):
        raise bad("The funds you added before are still waiting for a vote")
    now = now_ms()
    voters = _eligible(user)
    v = {"id": new_id(), "userId": user["id"], "username": user["username"], "amount": amount, "account": account, "createdAt": now,
         "closesAt": now + int(economy.FUNDS_VOTE_HOURS * HOUR_MS), "voters": voters, "votes": {}, "status": "open"}
    _all()[v["id"]] = v
    if not voters:
        _close(v, "approved")
        return v
    for uid in voters:
        inbox.push(_user(uid), "fundvote", "Vote needed", f"{user['username']} wants to add {_money(amount)}. Are you in favor or against?", vote=v["id"])
    return v


def cast(user, vote_id, favor):
    v = _all().get(vote_id)
    if not v:
        raise bad("There is no such vote", 404)
    if v["status"] != "open":
        raise bad("That vote has already ended")
    if user["id"] not in v["voters"]:
        raise bad("This vote is not for you", 403)
    if user["id"] in v["votes"]:
        raise bad("You have already voted")
    if not isinstance(favor, bool):
        raise bad("Vote in favor or against")
    v["votes"][user["id"]] = favor
    settle(v)
    return v


def settle(v, now=None):
    """Closes the vote if it is over. Returns True if it was closed now."""
    if v["status"] != "open":
        return False
    now = now_ms() if now is None else now
    out = _outcome(v, final=now >= v["closesAt"])
    if out:
        _close(v, out)
        return True
    return False


def _close(v, status):
    v["status"], v["closedAt"] = status, now_ms()
    yes, no, left = tally(v)
    v["result"] = {"inFavor": yes, "against": no, "didNotVote": left}
    asker = _user(v["userId"])
    if status == "approved" and asker is not None:
        users.apply_deposit(asker, v["amount"], v["account"], ref=v["id"], txid=f"fundvote-{v['id']}")
    elif asker is not None:
        users.log(asker, "warn", 0, f"The vote on adding {_money(v['amount'])} did not pass: nothing was added")
    count = f"{yes} in favor, {no} against" + (f", {left} did not vote" if left else "")
    if asker is not None:
        if not v["voters"]:
            inbox.push(asker, "funds", "Funds added", f"There was nobody else to ask. {_money(v['amount'])} is in your {v['account']} account.", vote=v["id"])
        elif status == "approved":
            inbox.push(asker, "funds", "Funds approved", f"The vote passed ({count}). {_money(v['amount'])} is in your {v['account']} account.", vote=v["id"])
        else:
            inbox.push(asker, "funds", "Funds not approved", f"The vote did not pass ({count}). Nothing was added.", vote=v["id"])
    for uid in v["voters"]:
        u = _user(uid)
        if u is not None:
            inbox.push(u, "funds", "Vote ended", f"{v['username']}'s {_money(v['amount'])}: {'approved' if status == 'approved' else 'not approved'} ({count}).", vote=v["id"])


def tick(now=None):
    """Closes every vote whose time is up. Returns True if any was closed."""
    changed = False
    for v in list(_all().values()):
        if settle(v, now):
            changed = True
    return changed


# ---- what the browser is told -------------------------------------------------------------------------------------------------

def _json(v, viewer):
    out = {"id": v["id"], "username": v["username"], "amount": v["amount"], "account": v["account"], "createdAt": v["createdAt"],
           "closesAt": v["closesAt"], "status": v["status"], "voted": len(v["votes"]), "total": len(v["voters"]), "mine": v["userId"] == viewer["id"]}
    if v["status"] != "open":
        out["result"] = v["result"]                                   # how it went is only told once it is over
    return out


def owed(user):
    """The votes still waiting for this person, oldest first."""
    rows = [v for v in _all().values() if v["status"] == "open" and user["id"] in v["voters"] and user["id"] not in v["votes"]]
    rows.sort(key=lambda v: v["createdAt"])
    return [_json(v, user) for v in rows]


def mine(user, limit=5):
    """This person's own requests, newest first (the open one, if there is one, comes first)."""
    rows = [v for v in _all().values() if v["userId"] == user["id"]]
    rows.sort(key=lambda v: (v["status"] == "open", v["createdAt"]), reverse=True)
    return [_json(v, user) for v in rows[:limit]]


def hold(user):
    """Money of this person that is on hold right now, by account (empty when there is none)."""
    out = {}
    for v in _all().values():
        if v["userId"] == user["id"] and v["status"] == "open":
            out[v["account"]] = round2(out.get(v["account"], 0) + v["amount"])
    return out
