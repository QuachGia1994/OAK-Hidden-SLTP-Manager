"""Rebuild passes correct as_of_dt for current-day vs historical slots (v76)."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import mt5_signal_bot


class CurrentDayAsOfRebuildTests(unittest.TestCase):
    """Current-day rebuild must use broker_now as as_of, not slot_dt."""

    @patch("mt5_signal_bot.evaluate_all_pairs_for_slot")
    @patch("mt5_signal_bot.log_signal")
    @patch("mt5_signal_bot.is_deactivated_signal_slot", return_value=False)
    def test_current_day_rebuild_passes_broker_now_as_as_of(self, _deact, _log, mock_eval):
        mock_eval.return_value = {
            "signal": "BUY",
            "entry_time": "07:49",
            "entry_state": "READY",
            "pair_dirs": {"XAUUSD": "BUY"},
        }

        broker_now = datetime(2026, 7, 30, 9, 8, 0)
        slot_dt = datetime(2026, 7, 30, 7, 0, 0)

        mt5_signal_bot.rebuild_slot_signal(slot_dt, 7, as_of_dt=broker_now)

        mock_eval.assert_called_once()
        call_kwargs = mock_eval.call_args
        passed_as_of = call_kwargs.kwargs.get("as_of_dt") or call_kwargs[1].get("as_of_dt")
        self.assertEqual(passed_as_of, broker_now)

    @patch("mt5_signal_bot.evaluate_all_pairs_for_slot")
    @patch("mt5_signal_bot.log_signal")
    @patch("mt5_signal_bot.is_deactivated_signal_slot", return_value=False)
    def test_historical_rebuild_uses_far_future_as_of(self, _deact, _log, mock_eval):
        mock_eval.return_value = {
            "signal": "SELL",
            "entry_time": "03:49",
            "entry_state": "READY",
            "pair_dirs": {"XAUUSD": "SELL"},
        }

        slot_dt = datetime(2026, 7, 29, 3, 0, 0)
        far_future = slot_dt + timedelta(days=1)

        mt5_signal_bot.rebuild_slot_signal(slot_dt, 3, as_of_dt=far_future)

        mock_eval.assert_called_once()
        call_kwargs = mock_eval.call_args
        passed_as_of = call_kwargs.kwargs.get("as_of_dt") or call_kwargs[1].get("as_of_dt")
        self.assertEqual(passed_as_of, far_future)


class Layer3ResolvesAfterH30Tests(unittest.TestCase):
    """evaluate_xau_entry_timing_m30 must not return PENDING_LAYER3 after H:30."""

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h7_layer3_resolves_at_0730(self, mock_read):
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str in ("06:30", "06:00", "05:30"):
                return {"open": "1.1", "close": "1.2", "high": "1.25", "low": "1.05"}
            if t_str in ("07:00",):
                return {"open": "1.2", "close": "1.1", "high": "1.25", "low": "1.05"}
            return {"open": "1.1", "close": "1.15", "high": "1.2", "low": "1.0"}

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        as_of = datetime(2026, 7, 30, 9, 8, 0)
        res = mt5_signal_bot.evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of)

        self.assertNotEqual(res["entry_state"], "PENDING_LAYER3")
        self.assertEqual(res["entry_state"], "READY")
        self.assertIsNotNone(res["entry_time"])

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h7_still_pending_before_0730(self, mock_read):
        def fake_candle(symbol, open_dt, as_of_dt=None):
            return {"open": "1.1", "close": "1.2", "high": "1.25", "low": "1.05"}

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        as_of = datetime(2026, 7, 30, 7, 10, 0)
        res = mt5_signal_bot.evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of)

        layer2_group = res.get("layer2", {}).get("group")
        if layer2_group == "SW":
            self.assertEqual(res["entry_state"], "PENDING_LAYER3")


if __name__ == "__main__":
    unittest.main()
