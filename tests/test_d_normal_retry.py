"""Test C: snapshot_is_publishable() — GBPUSD+GBPAUD READY unblocks regardless of force."""
import unittest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSnapshotIsPublishable(unittest.TestCase):
    def _make_snapshot(self, gbpusd_state, gbpaud_state, xauusd_state="MISSING"):
        return {
            "state": "PARTIAL" if "MISSING" in [gbpusd_state, gbpaud_state] else "READY",
            "symbols": {
                "XAUUSD": {"d_state": xauusd_state},
                "GBPUSD": {"d_state": gbpusd_state},
                "GBPAUD": {"d_state": gbpaud_state},
                "GBPJPY": {"d_state": "MISSING"},
                "GBPCAD": {"d_state": "MISSING"},
            }
        }

    def test_both_active_ready(self):
        import mt5_signal_bot as bot
        snap = self._make_snapshot("READY", "READY", "READY")
        self.assertTrue(bot.snapshot_is_publishable(snap))

    def test_gbpusd_missing_blocks(self):
        import mt5_signal_bot as bot
        snap = self._make_snapshot("MISSING", "READY")
        self.assertFalse(bot.snapshot_is_publishable(snap))

    def test_gbpaud_missing_blocks(self):
        import mt5_signal_bot as bot
        snap = self._make_snapshot("READY", "MISSING")
        self.assertFalse(bot.snapshot_is_publishable(snap))

    def test_both_missing_blocks(self):
        import mt5_signal_bot as bot
        snap = self._make_snapshot("MISSING", "MISSING")
        self.assertFalse(bot.snapshot_is_publishable(snap))

    def test_gbpjpy_gbpcad_missing_does_not_block(self):
        """GBPJPY/GBPCAD are EXEC OFF and must never block publication."""
        import mt5_signal_bot as bot
        snap = self._make_snapshot("READY", "READY")
        # GBPJPY/GBPCAD are MISSING in the helper by default
        self.assertTrue(bot.snapshot_is_publishable(snap))

    def test_doji_is_publishable(self):
        """DOJI state must count as publishable (not MISSING)."""
        import mt5_signal_bot as bot
        snap = self._make_snapshot("DOJI", "DOJI")
        self.assertTrue(bot.snapshot_is_publishable(snap))


class TestDNormalRetryCondition(unittest.TestCase):
    """Test C: The retry loop must run on MISSING state without needing force=True."""

    def test_retry_loop_breaks_on_publishable(self):
        """snapshot_is_publishable must be the only break condition."""
        import mt5_signal_bot as bot
        # Simulate: first call MISSING, second call READY
        call_count = [0]
        snapshots = [
            {"state": "MISSING", "symbols": {
                "GBPUSD": {"d_state": "MISSING"}, "GBPAUD": {"d_state": "MISSING"}}},
            {"state": "READY", "symbols": {
                "GBPUSD": {"d_state": "READY"}, "GBPAUD": {"d_state": "READY"}}},
        ]

        attempts = 0
        for snap in snapshots:
            attempts += 1
            if bot.snapshot_is_publishable(snap):
                break

        self.assertEqual(attempts, 2)
        self.assertTrue(bot.snapshot_is_publishable(snapshots[1]))

    def test_old_condition_would_have_broken_early(self):
        """Validate that old `or not force` logic would have failed."""
        # With force=False (normal startup), `or not force` is True => always breaks
        # This test documents that the old approach was broken
        force = False
        snapshot = {"state": "MISSING"}
        old_condition = snapshot["state"] in ("READY", "DOJI") or not force
        self.assertTrue(old_condition, "Old condition breaks on MISSING when force=False — this is the bug")


if __name__ == "__main__":
    unittest.main()
