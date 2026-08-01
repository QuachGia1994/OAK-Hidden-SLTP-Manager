"""Shared unittest bootstrap for an ephemeral MT4 feed database."""

import atexit
import shutil
import sys
import tempfile
from pathlib import Path

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from repositories import mt4_feed_store


LIVE_DB_PATH = Path(mt4_feed_store.DB_PATH).resolve()
_test_db_directory = None
TEST_DB_PATH = None


def install_isolated_mt4_feed_database() -> Path:
    """Redirect default test providers away from the live MT4 feed database."""
    global _test_db_directory, TEST_DB_PATH
    if TEST_DB_PATH is None:
        _test_db_directory = Path(tempfile.mkdtemp(prefix="robot-sltp-mt4-feed-tests-"))
        TEST_DB_PATH = _test_db_directory / "mt4_feed.db"
        mt4_feed_store.DB_PATH = str(TEST_DB_PATH)
    return TEST_DB_PATH


@atexit.register
def _remove_isolated_feed_database() -> None:
    if _test_db_directory is not None:
        shutil.rmtree(_test_db_directory, ignore_errors=True)
