"""Tiny JSON-file database. The whole state lives in memory and is saved atomically after
every change, so a crash can never leave a half-written file."""
import glob
import json
import os
import shutil
import threading
import time

from . import config

LOCK = threading.RLock()


class Store:
    def __init__(self, path):
        self.path = path
        self.data = {}
        self._m = threading.Lock()          # guards the little bookkeeping below, never held while writing to disk
        self._w = threading.Lock()          # one disk write at a time
        self._seq = 0                       # number of the newest snapshot taken
        self._written = 0                   # number of the newest snapshot that is safely on disk
        self._blob = b""                    # the newest snapshot
        self._last = None                   # (path, exactly what is in the file right now)
        self.migrated = []                  # the data migrations that ran at the last load()

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.exists(self.path):
            self._backup()
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        d = self.data
        d.setdefault("meta", {})
        d.setdefault("users", {})          # id -> user
        d.setdefault("usernames", {})      # lowercase name -> id
        d.setdefault("sessions", {})       # sha256(token) -> {userId, expires}
        d.setdefault("circles", {})
        d.setdefault("markets", {})
        d.setdefault("snapshots", {})      # weekKey -> {userId: net worth at week end}
        d.setdefault("games", {})          # userId -> {"blackjack": state, "chicken": state}
        d.setdefault("feed", [])           # recent big game wins
        d.setdefault("poker", {})          # id -> live poker table
        d.setdefault("social", {})         # user id -> friends, requests, read pointers
        d.setdefault("chats", {})          # chat id -> messages
        d.setdefault("idem", {})           # "userId:requestId" -> a trade that already went through
        d.setdefault("ledger", {})         # user id -> newest account movements (see ledger.py)
        d.setdefault("ledger_sum", {})     # user id -> older movements folded by week, account and reason
        from . import migrations           # imported here: the migrations use the modules that use this one
        self.migrated = migrations.run(d)
        return d

    def _backup(self):
        folder = os.path.join(os.path.dirname(self.path), "backups")
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copyfile(self.path, os.path.join(folder, f"db-{stamp}.json"))
        old = sorted(glob.glob(os.path.join(folder, "db-*.json")))[:-15]
        for p in old:
            try:
                os.remove(p)
            except OSError:
                pass

    # Saving is split in two so the slow part (the disk) never holds up everybody else:
    #   stage()  - called while the app lock is held: takes a snapshot of the whole state (fast, memory only)
    #   commit() - called after the lock is released: puts that snapshot (or a newer one) on disk and waits for it
    # A request still only answers once its change is on disk, but other requests keep being served meanwhile, and
    # requests that pile up behind a write share the next one (a snapshot always contains everything before it).
    def stage(self):
        blob = json.dumps(self.data, separators=(",", ":")).encode("utf-8")
        with self._m:
            self._seq += 1
            self._blob = blob
            return self._seq

    def commit(self, ticket):
        with self._w:
            with self._m:
                if self._written >= ticket:        # somebody else's write already included this change
                    return
                blob, seq = self._blob, self._seq
            if self._last != (self.path, blob) or not os.path.exists(self.path):     # nothing new to write? skip the disk entirely
                tmp = self.path + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(blob)
                    f.flush()
                    os.fsync(f.fileno())
                _replace(tmp, self.path)
                self._last = (self.path, blob)
            with self._m:
                self._written = seq

    def save(self):
        """Stage and commit in one go. For the background loops, start-up, shutdown and scripts."""
        self.commit(self.stage())


def _replace(src, dst, tries=50, pause=0.02):
    """os.replace, waiting a moment if the file is busy. On Windows a file that somebody has open for reading cannot be
    replaced (PermissionError); readers only hold it for a moment, so a short retry is enough. Gives up after about a second."""
    for n in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if n == tries - 1:
                raise
            time.sleep(pause)


store = Store(os.path.join(config.DATA_DIR, "db.json"))


def db():
    return store.data
