"""Shared test plumbing: every test gets an empty database of its own, whatever ran before it."""
import os
import tempfile

from backend import chats, social, users
from backend.store import store

_ORIGINAL_PATH = store.path


def fresh_store():
    store.path = os.path.join(tempfile.mkdtemp(), "db.json")
    store.data = {}
    store.load()
    store.data.setdefault("meta", {})["requirements_from"] = "9999-12-31"   # the weekly minimum is off unless a test turns it on (tests/test_weekly_minimum.py)
    users._attempts.clear()
    social._presence.clear()
    chats._sent.clear()


def restore_store_path():
    store.path = _ORIGINAL_PATH
