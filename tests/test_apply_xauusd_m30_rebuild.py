"""Regression coverage for the active GBP H1-derived XAUUSD slot matrix."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import calculate_slot_signal, get_pair_direction


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_h3_is_the_active_logical_early_slot(self) -> None:
        self.assertIn(3, mt5_signal_bot.ACTIVE_HOURS)
        self.assertNotIn(2, mt5_signal_bot.ACTIVE_HOURS)
        self.assertNotIn(5, mt5_signal_bot.ACTIVE_HOURS)

    def test_h3_pair_direction_is_xauusd_only(self) -> None:
        dt = datetime(2026, 7, 9, 2, 45, tzinfo=timezone.utc)
        pair_dirs = get_pair_direction(3, "BUY", dt)
        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs, {"XAUUSD": "BUY", "GBPUSD": "WAIT", "GBPAUD": "WAIT", "GBPJPY": "WAIT", "GBPCAD": "WAIT"})

    def test_h4_is_no_longer_an_active_slot(self) -> None:
        self.assertFalse(hasattr(mt5_signal_bot, "apply_xauusd_m30_logic"))
        self.assertNotIn(4, mt5_signal_bot.ACTIVE_HOURS)
        broker_dt = datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc)
        result = calculate_slot_signal(broker_dt, 4)
        self.assertEqual(result["signal"], "WAIT")
        self.assertNotIn("suppressed", result)


if __name__ == "__main__":
    unittest.main()
