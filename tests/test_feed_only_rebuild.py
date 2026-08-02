"""A v88 log rebuild depends on the MT4 feed, not the MT5 execution gateway."""
from unittest.mock import patch
import unittest
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot


class FeedOnlyRebuildTests(unittest.TestCase):
    def test_pushes_a_complete_snapshot_only_after_a_feed_rebuild(self):
        with (
            patch.object(mt5_signal_bot, "rebuild_recent_history", return_value=6) as rebuild,
            patch.object(mt5_signal_bot, "push_to_dashboard") as push,
        ):
            rebuilt = mt5_signal_bot._run_feed_only_rebuild(45)

        self.assertEqual(rebuilt, 6)
        rebuild.assert_called_once_with(days=45, include_weekends=False)
        push.assert_called_once_with(snapshot_complete=True)

    def test_weekend_rebuild_is_forwarded(self):
        with (
            patch.object(mt5_signal_bot, "rebuild_recent_history", return_value=6) as rebuild,
            patch.object(mt5_signal_bot, "push_to_dashboard") as push,
        ):
            rebuilt = mt5_signal_bot._run_feed_only_rebuild(45, include_weekends=True)

        self.assertEqual(rebuilt, 6)
        rebuild.assert_called_once_with(days=45, include_weekends=True)
        push.assert_called_once_with(snapshot_complete=True)

    def test_does_not_publish_stale_records_when_the_feed_cannot_rebuild(self):
        with (
            patch.object(mt5_signal_bot, "rebuild_recent_history", return_value=0),
            patch.object(mt5_signal_bot, "push_to_dashboard") as push,
        ):
            rebuilt = mt5_signal_bot._run_feed_only_rebuild(45)

        self.assertEqual(rebuilt, 0)
        push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
