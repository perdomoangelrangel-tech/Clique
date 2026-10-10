

# SAFETY: nothing in this package may import backend code here. backend.config reads DATA_DIR the moment it is first imported, so
# importing it before a test module has pointed DATA_DIR at its own temporary folder would make the tests use the REAL data folder.
# This default means that even a test module that forgets to set one gets a throw-away folder (tests/test_safety.py checks it).
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("DATA_DIR", _tempfile.mkdtemp())
# Most tests create accounts without an email; the tests for the email rules switch the rule on themselves.
_os.environ.setdefault("EMAIL_REQUIRED", "0")
# The Wednesday bonus (backend/weekly.pay_midweek) is paid by weekly.tick() from Wednesday noon on, so left on it would add $500 to every test that
# runs a weekly close on a Wednesday afternoon or later and break its sums. It is off here; tests/test_midweek_and_fundvotes.py switches it on.
_os.environ.setdefault("MIDWEEK_BONUS", "0")

