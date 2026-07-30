import unittest
from datetime import datetime
from unittest.mock import patch
from mt5_signal_bot import (
    get_m30_layer_open_times,
    evaluate_xau_entry_timing_m30,
)

class TwoLayerM30WindowTests(unittest.TestCase):
    def test_h3_uses_three_open_times_for_layer2(self):
        slot_dt = datetime(2026, 7, 30, 3, 0, 0)
        windows = get_m30_layer_open_times(slot_dt)
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer2"]),
            ("02:30", "02:00", "01:30"),
        )
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer3"]),
            ("03:00", "02:30", "02:00"),
        )

    def test_h7_uses_three_open_times_for_layer2_and_3(self):
        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        windows = get_m30_layer_open_times(slot_dt)
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer2"]),
            ("06:30", "06:00", "05:30"),
        )
        self.assertEqual(
            tuple(value.strftime("%H:%M") for value in windows["layer3"]),
            ("07:00", "06:30", "06:00"),
        )

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_mt5_lookup_queries_exact_open_times(self, read):
        read.return_value = None
        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=slot_dt)
        expected_calls = [
            ("XAUUSD", datetime(2026, 7, 30, 5, 30), slot_dt),
            ("XAUUSD", datetime(2026, 7, 30, 6, 0), slot_dt),
            ("XAUUSD", datetime(2026, 7, 30, 6, 30), slot_dt),
        ]
        self.assertEqual([call.args for call in read.call_args_list], expected_calls)

if __name__ == "__main__":
    unittest.main()
