"""All-or-nothing changes to people's money.

Clique runs one request at a time, so two requests never see each other half done. This module protects against the other
failure: a request that fails HALFWAY (a bug, a refusal after the first leg of a transfer, a full account). Wrap the
steps in `with Txn(users=[...], extras=[...]):` and, if anything inside raises, every person, ledger row and record
named is put back exactly as it was before the first step, and the error carries on. Nothing is half applied, and nothing
is saved, because the request is answered with an error.
"""
import copy

from .store import db

_MISSING = object()


class Txn:
    def __init__(self, users=(), extras=()):
        """users: the account records that will change. extras: (container, key) pairs for other records that may be created
        or changed, such as (db()["loans"], loan_id) or (db()["idem"], key)."""
        self.users = list(users)
        self.extras = list(extras)
        self._saved = []

    def __enter__(self):
        d = db()
        self._saved = [(u, copy.deepcopy(u)) for u in self.users]
        self._ledger = {}
        for u in self.users:
            uid = u["id"]
            rows = d.get("ledger", {}).get(uid, _MISSING)
            sums = d.get("ledger_sum", {}).get(uid, _MISSING)
            self._ledger[uid] = (_MISSING if rows is _MISSING else list(rows), _MISSING if sums is _MISSING else copy.deepcopy(sums))
        self._extra = [(box, key, _MISSING if key not in box else copy.deepcopy(box[key])) for box, key in self.extras]
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            return False
        d = db()
        for u, snap in self._saved:
            u.clear()
            u.update(copy.deepcopy(snap))
        for uid, (rows, sums) in self._ledger.items():
            for section, saved in (("ledger", rows), ("ledger_sum", sums)):
                box = d.setdefault(section, {})
                if saved is _MISSING:
                    box.pop(uid, None)
                else:
                    box[uid] = saved
        for box, key, saved in self._extra:
            if saved is _MISSING:
                box.pop(key, None)
            else:
                box[key] = saved
        return False
