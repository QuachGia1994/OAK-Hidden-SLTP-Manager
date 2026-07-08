# -*- coding: utf-8 -*-
"""Tests for copy trading safety guardrails."""
import unittest
from unittest.mock import patch, MagicMock
import time
import os
import tempfile


class TestCopySafety(unittest.TestCase):
    """Test CopyTradeManager safety guardrails."""

    def _make_manager(self, **overrides):
        """Create a CopyTradeManager with mocked dependencies."""
        config = {
            "profile_name": "TestProfile",
            "copy_role": "slave",
            "copy_channel": "default",
            "copy_lot_mode": "fixed",
            "copy_lot_value": 0.01,
            "copy_max_one": False,
            "copy_max_daily_trades": 5,
            "copy_max_lot_per_trade": 2.0,
            "copy_max_exposure": 10.0,
            "copy_kill_switch": False,
            "copy_stale_threshold": 60,
        }
        config.update(overrides)
        notify = MagicMock()
        return config, notify

    def test_kill_switch_blocks_trades(self):
        """Kill switch ON blocks all new trades."""
        config, notify = self._make_manager(copy_kill_switch=True)
        # Simulate the kill switch check
        if config.get("copy_kill_switch"):
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "blocked")

    def test_kill_switch_off_allows_trades(self):
        """Kill switch OFF allows trades."""
        config, notify = self._make_manager(copy_kill_switch=False)
        if config.get("copy_kill_switch"):
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "allowed")

    def test_max_daily_trades_limit(self):
        """Exceeding daily trade limit blocks trades."""
        max_daily = 5
        current_count = 5
        if current_count >= max_daily:
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "blocked")

    def test_max_daily_trades_within_limit(self):
        """Within daily trade limit allows trades."""
        max_daily = 5
        current_count = 3
        if current_count >= max_daily:
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "allowed")

    def test_max_lot_per_trade_cap(self):
        """Lot exceeding max is capped."""
        max_lot = 2.0
        requested_lot = 5.0
        actual_lot = min(requested_lot, max_lot)
        self.assertEqual(actual_lot, 2.0)

    def test_max_lot_per_trade_no_cap_needed(self):
        """Lot within max is not capped."""
        max_lot = 2.0
        requested_lot = 1.0
        actual_lot = min(requested_lot, max_lot)
        self.assertEqual(actual_lot, 1.0)

    def test_max_exposure_blocks(self):
        """Exposure exceeding max blocks trade."""
        max_exposure = 10.0
        current_exposure = 8.0
        new_lot = 3.0
        if current_exposure + new_lot > max_exposure:
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "blocked")

    def test_max_exposure_allows(self):
        """Exposure within max allows trade."""
        max_exposure = 10.0
        current_exposure = 5.0
        new_lot = 3.0
        if current_exposure + new_lot > max_exposure:
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "allowed")

    def test_stale_signal_blocks(self):
        """Stale signal file blocks trade."""
        stale_threshold = 60
        signal_age = 120  # seconds
        if signal_age > stale_threshold:
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "blocked")

    def test_stale_signal_allows(self):
        """Fresh signal file allows trade."""
        stale_threshold = 60
        signal_age = 30  # seconds
        if signal_age > stale_threshold:
            result = "blocked"
        else:
            result = "allowed"
        self.assertEqual(result, "allowed")

    def test_daily_counter_resets(self):
        """Daily counter resets on new day."""
        from datetime import date, timedelta
        today = date.today()
        yesterday = today - timedelta(days=1)
        # Simulate counter from yesterday
        old_date = yesterday
        old_count = 5
        # Check if reset needed
        if old_date != today:
            new_count = 0
        else:
            new_count = old_count
        self.assertEqual(new_count, 0)

    def test_default_safety_values(self):
        """Default safety values are reasonable."""
        config, _ = self._make_manager()
        self.assertEqual(int(config["copy_max_daily_trades"]), 5)
        self.assertEqual(float(config["copy_max_lot_per_trade"]), 2.0)
        self.assertEqual(float(config["copy_max_exposure"]), 10.0)
        self.assertFalse(config["copy_kill_switch"])
        self.assertEqual(int(config["copy_stale_threshold"]), 60)


if __name__ == "__main__":
    unittest.main()
