"""Regression coverage for the active GBP H1-derived XAUUSD slot matrix."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

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
        self.assertEqual(pair_dirs, {"XAUUSD": "BUY", "GBPUSD": "WAIT", "GBPAUD": "WAIT"})

    def test_h4_uses_gbp_h1_logic_and_stays_deactivated(self) -> None:
        broker_dt = datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc)
        context = {
            "signal": "BUY",
            "entry_time": "04:11",
            "pair_dirs": {"XAUUSD": "BUY"},
        }
        self.assertFalse(hasattr(mt5_signal_bot, "apply_xauusd_m30_logic"))
        with patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=context):
            result = calculate_slot_signal(broker_dt, 4)

        self.assertIn(result["signal"], ("BUY", "SELL"))
        self.assertTrue(result["deactivated"])


if __name__ == "__main__":
    unittest.main()
