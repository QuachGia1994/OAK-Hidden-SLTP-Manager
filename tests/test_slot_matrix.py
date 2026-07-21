"""Regression tests for the current XAU-only slot matrix."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot
from mt5_signal_bot import calculate_slot_signal, get_pair_direction


class SlotMatrixTests(unittest.TestCase):
    def test_h3_reverses_the_final_h2_direction(self) -> None:
        broker_dt = datetime(2026, 7, 14, 3, 45, tzinfo=timezone.utc)
        self.assertEqual(calculate_slot_signal(broker_dt, 3)["signal"], "WAIT")

    def test_h10_is_disabled(self) -> None:
        broker_dt = datetime(2026, 7, 14, 10, 45, tzinfo=timezone.utc)
        self.assertEqual(get_pair_direction(10, "BUY", broker_dt), {})
        with patch.object(mt5_signal_bot, "analyze") as analyze:
            self.assertEqual(calculate_slot_signal(broker_dt, 10)["signal"], "WAIT")
        analyze.assert_not_called()

    def test_h2_and_normal_slots_apply_m5_m30_then_xau_m30(self) -> None:
        broker_dt = datetime(2026, 7, 14, 8, 45, tzinfo=timezone.utc)
        with patch.object(
            mt5_signal_bot,
            "analyze",
            side_effect=lambda *_args: {"signal": "BUY", "report": "pattern", "h1_signal": None},
        ), patch.object(
            mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"
        ):
            for hour in (12, 13, 15):
                with self.subTest(hour=hour):
                    result = calculate_slot_signal(broker_dt, hour)
                    self.assertEqual(result["pattern_signal"], "BUY")
                    self.assertEqual(result["signal"], "SELL")
                    self.assertTrue(result["skip_xau_m30"])


if __name__ == "__main__":
    unittest.main()
