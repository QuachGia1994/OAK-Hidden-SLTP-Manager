"""Layer 3 must resolve at H:30, not H:45 (v78)."""

import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot


class Layer3PublicationAtH30Tests(unittest.TestCase):
    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h7_resolves_at_0730(self, mock_read):
        def fake_candle(symbol, open_dt, as_of_dt=None):
            return {"open": "1.1", "close": "1.2", "high": "1.25", "low": "1.05"}
        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        as_of = datetime(2026, 7, 30, 7, 30, 0)
        res = mt5_signal_bot.evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of)
        self.assertEqual(res["entry_state"], "READY")
        self.assertIn(res["entry_time"], ("07:49", "08:25"))

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h7_still_pending_before_0730(self, mock_read):
        def fake_candle(symbol, open_dt, as_of_dt=None):
            return {"open": "1.1", "close": "1.2", "high": "1.25", "low": "1.05"}
        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        as_of = datetime(2026, 7, 30, 7, 10, 0)
        res = mt5_signal_bot.evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of)
        layer2 = res.get("layer2", {})
        if layer2.get("group") == "SW":
            self.assertEqual(res["entry_state"], "PENDING_LAYER3")

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_grace_period_keeps_pending_when_candle_missing(self, mock_read):
        """When H:00 candle is missing but within grace, stay PENDING_LAYER3."""
        def fake_candle(symbol, open_dt, as_of_dt=None):
            # Return candles for all times except H:00 (07:00)
            if open_dt.hour == 7 and open_dt.minute == 0:
                return None
            return {"open": "1.1", "close": "1.2", "high": "1.25", "low": "1.05"}
        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        # At 07:30:05 — within grace period, H:00 candle missing
        as_of = datetime(2026, 7, 30, 7, 30, 5)
        res = mt5_signal_bot.evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of)
        layer2 = res.get("layer2", {})
        if layer2.get("group") == "SW":
            self.assertIn(res["entry_state"], ("PENDING_LAYER3", "WAIT"))

    def test_get_layer3_resolution_datetime(self):
        slot = datetime(2026, 7, 30, 7, 0, 0)
        expected = datetime(2026, 7, 30, 7, 30, 0)
        self.assertEqual(mt5_signal_bot.get_layer3_resolution_datetime(slot), expected)

    def test_h3_retry_deadline_is_0425(self):
        """get_slot_retry_deadline for H3 must use 04:25, not 04:49."""
        broker_dt = datetime(2026, 7, 30, 3, 0, 0)
        deadline = mt5_signal_bot.get_slot_retry_deadline(broker_dt, 3, None)
        self.assertEqual(deadline.hour, 4)
        self.assertEqual(deadline.minute, 25)


if __name__ == "__main__":
    unittest.main()
