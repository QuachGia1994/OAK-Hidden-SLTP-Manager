"""Test B: Stale MISSING snapshot is overwritten by a new READY snapshot."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()


class TestDStaleMissingOverwrite(unittest.TestCase):
    def test_is_d_publication_complete_returns_false_for_missing(self):
        import mt5_signal_bot as bot
        stale = {
            "snapshot_state": "MISSING",
            "dashboard_acknowledged": True,
            "digest": "abc123",
            "last_http_status": 200,
            "logic_version": 84,
            "d_schema_version": 6,
        }
        result = bot.is_d_publication_complete(
            stale, logic_version=84, d_schema_version=6
        )
        self.assertFalse(result, "MISSING state must never be complete")

    def test_is_d_publication_complete_returns_false_for_unknown_legacy(self):
        import mt5_signal_bot as bot
        meta = {
            "snapshot_state": "UNKNOWN_LEGACY",
            "dashboard_acknowledged": False,
            "digest": None,
            "last_http_status": None,
            "logic_version": 84,
            "d_schema_version": 6,
        }
        result = bot.is_d_publication_complete(
            meta, logic_version=84, d_schema_version=6
        )
        self.assertFalse(result)

    def test_is_d_publication_complete_returns_false_when_not_acknowledged(self):
        import mt5_signal_bot as bot
        meta = {
            "snapshot_state": "READY",
            "dashboard_acknowledged": False,
            "digest": "abc123",
            "last_http_status": 200,
            "logic_version": 84,
            "d_schema_version": 6,
        }
        self.assertFalse(bot.is_d_publication_complete(meta, logic_version=84, d_schema_version=6))

    def test_is_d_publication_complete_returns_false_without_digest(self):
        import mt5_signal_bot as bot
        meta = {
            "snapshot_state": "READY",
            "dashboard_acknowledged": True,
            "digest": None,
            "last_http_status": 200,
            "logic_version": 84,
            "d_schema_version": 6,
        }
        self.assertFalse(bot.is_d_publication_complete(meta, logic_version=84, d_schema_version=6))

    def test_is_d_publication_complete_true_for_valid_ready(self):
        import mt5_signal_bot as bot
        meta = {
            "snapshot_state": "READY",
            "dashboard_acknowledged": True,
            "digest": "abc1234567890",
            "last_http_status": 200,
            "logic_version": 84,
            "d_schema_version": 6,
        }
        self.assertTrue(bot.is_d_publication_complete(meta, logic_version=84, d_schema_version=6))

    def test_is_d_publication_complete_false_for_old_logic_version(self):
        """Old logic_version in metadata must fail even if everything else looks fine."""
        import mt5_signal_bot as bot
        meta = {
            "snapshot_state": "READY",
            "dashboard_acknowledged": True,
            "digest": "abc1234567890",
            "last_http_status": 200,
            "logic_version": 83,  # old version
            "d_schema_version": 6,
        }
        self.assertFalse(bot.is_d_publication_complete(meta, logic_version=84, d_schema_version=6))


if __name__ == "__main__":
    unittest.main()
