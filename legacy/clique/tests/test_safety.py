"""The tests must never touch the real data folder (the one with the real accounts in it)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config                    # noqa: E402
from backend.store import store               # noqa: E402

REAL = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))


def inside(path, folder):
    return os.path.realpath(path) == folder or os.path.realpath(path).startswith(folder + os.sep)


class TestsStayAwayFromRealData(unittest.TestCase):
    def test_the_data_folder_in_use_is_not_the_real_one(self):
        self.assertFalse(inside(config.DATA_DIR, REAL), f"the tests are using the real data folder: {config.DATA_DIR}")

    def test_the_database_file_in_use_is_not_the_real_one(self):
        self.assertFalse(inside(store.path, REAL), f"the tests are using the real database: {store.path}")

    def test_importing_the_test_package_does_not_load_backend_code_early(self):
        # backend.config reads DATA_DIR when first imported, so tests/__init__.py must not import it (see the comment there).
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "__init__.py")) as f:
            src = f.read()
        self.assertNotRegex(src, r"(?m)^\s*(from|import)\s+backend")


if __name__ == "__main__":
    unittest.main()
