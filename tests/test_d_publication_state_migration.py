"""Test A: Legacy list/set migrates to UNKNOWN_LEGACY + acknowledged=False (not READY).

Regression test for the bug where the old migration path set snapshot_state=READY
on every legacy date, blocking any retry and creating false 'published' state.
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from datetime import date

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()


def _load_state_patched(state_file):
    """Load state with patched _STATE_FILE and broker time so tests run offline."""
    import mt5_signal_bot as bot
    original_sf = bot._STATE_FILE
    try:
        bot._STATE_FILE = state_file
        # Patch _trading_date to return today's date without MT5
        with patch.object(bot, "_trading_date", return_value=date(2026, 7, 31)):
            return bot._load_state()
    finally:
        bot._STATE_FILE = original_sf


def _make_state(tmp, data):
    state_file = os.path.join(tmp, "bot_state.json")
    with open(state_file, "w") as f:
        json.dump(data, f)
    return state_file


class TestDPublicationStateMigration(unittest.TestCase):

    def test_legacy_list_migrates_to_unknown_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp, {
                "date": "2026-07-31",
                "signal_logic_version": 84,
                "d_published_local_dates": ["2026-07-30", "2026-07-29"],
                "sent_today": [],
            })
            result = _load_state_patched(state_file)

        pub_state = result.get("d_publication_state", {})
        self.assertIn("2026-07-30", pub_state)
        self.assertIn("2026-07-29", pub_state)
        self.assertEqual(pub_state["2026-07-30"]["snapshot_state"], "UNKNOWN_LEGACY")
        self.assertFalse(pub_state["2026-07-30"]["dashboard_acknowledged"])
        self.assertEqual(pub_state["2026-07-29"]["snapshot_state"], "UNKNOWN_LEGACY")
        self.assertFalse(pub_state["2026-07-29"]["dashboard_acknowledged"])

    def test_legacy_list_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp, {
                "date": "2026-07-31",
                "signal_logic_version": 84,
                "d_published_local_dates": ["2026-07-30"],
                "sent_today": [],
            })
            result = _load_state_patched(state_file)

        pub_state = result.get("d_publication_state", {})
        meta = pub_state.get("2026-07-30", {})
        self.assertNotEqual(meta.get("snapshot_state"), "READY",
                            "Legacy list entry must NOT be READY")

    def test_new_dict_format_preserved(self):
        existing_meta = {
            "2026-07-30": {
                "snapshot_state": "READY",
                "dashboard_acknowledged": True,
                "schema_version": 2,
                "logic_version": 84,
                "d_schema_version": 6,
                "digest": "abc123456789",
                "last_http_status": 200,
                "active_source_states": {"GBPUSD": "READY", "GBPAUD": "READY"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp, {
                "date": "2026-07-31",
                "signal_logic_version": 84,
                "d_publication_state": existing_meta,
                "sent_today": [],
            })
            result = _load_state_patched(state_file)

        pub_state = result.get("d_publication_state", {})
        self.assertEqual(pub_state, existing_meta)

    def test_empty_state_returns_empty_pub_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "nonexistent.json")
            import mt5_signal_bot as bot
            original = bot._STATE_FILE
            try:
                bot._STATE_FILE = state_file
                with patch.object(bot, "_trading_date", return_value=date(2026, 7, 31)):
                    result = bot._load_state()
            finally:
                bot._STATE_FILE = original
        self.assertEqual(result.get("d_publication_state", {}), {})


if __name__ == "__main__":
    unittest.main()
