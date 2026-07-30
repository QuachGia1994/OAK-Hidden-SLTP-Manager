"""XAU timing layers use the user's completed M30 close-time windows."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class TwoLayerM30WindowTests(unittest.TestCase):
    def test_h3_uses_three_close_times_then_four_later_close_times(self) -> None:
        windows = mt5_signal_bot.xau_entry_layer_close_times(datetime(2026, 7, 30, 3))
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer1"]),
            ("02:30", "02:00", "01:30"),
        )
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer2"]),
            ("03:00", "02:30", "02:00", "01:30"),
        )

    def test_h7_uses_two_four_candle_windows_thirty_minutes_apart(self) -> None:
        windows = mt5_signal_bot.xau_entry_layer_close_times(datetime(2026, 7, 30, 7))
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer1"]),
            ("06:00", "05:30", "05:00", "04:30"),
        )
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer2"]),
            ("06:30", "06:00", "05:30", "05:00"),
        )

    def test_mt5_lookup_converts_close_time_to_open_time(self) -> None:
        slot = datetime(2026, 7, 30, 7)
        candle = {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "tick_volume": 1}
        with patch.object(mt5_signal_bot, "read_completed_m30_candle", return_value=candle) as read:
            mt5_signal_bot.evaluate_xau_entry_timing_m30(slot, 7)
        self.assertEqual(
            [call.args for call in read.call_args_list],
            [
                ("XAUUSD", datetime(2026, 7, 30, 4, 0), slot),
                ("XAUUSD", datetime(2026, 7, 30, 4, 30), slot),
                ("XAUUSD", datetime(2026, 7, 30, 5, 0), slot),
                ("XAUUSD", datetime(2026, 7, 30, 5, 30), slot),
                ("XAUUSD", datetime(2026, 7, 30, 6, 0), slot),
            ],
        )


if __name__ == "__main__":
    unittest.main()
