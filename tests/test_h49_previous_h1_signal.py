"""H:49 uses reverse of previous completed H1 candle (v80)."""

import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

import mt5_signal_bot
from mt5_signal_bot import (
    DayMode,
    resolve_primary_signal_action,
    classify_slot_entry_branch,
    evaluate_all_pairs_for_slot,
)


class ResolvePrimaryActionH49Tests(unittest.TestCase):
    def test_h49_returns_reverse_h1(self):
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        action = resolve_primary_signal_action(mode, "H_49")
        self.assertEqual(action, "REVERSE_H1")

    def test_h49_without_mode_still_reverse_h1(self):
        action = resolve_primary_signal_action(None, "H_49")
        self.assertEqual(action, "REVERSE_H1")


class H49SignalEngineTests(unittest.TestCase):
    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_h49_reverses_h1_tang_to_sell(self, mock_clock):
        """H:49 with H1 TANG → SELL (reverse of BUY)."""
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        d_dirs = {
            "XAUUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "XAUUSD"},
            "GBPUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPUSD"},
            "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD"},
            "GBPJPY": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPJPY"},
            "GBPCAD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPCAD"},
        }
        h1_candle = {"open": 2340.0, "close": 2345.0, "high": 2346.0, "low": 2339.0}

        with (
            patch("mt5_signal_bot.calculate_all_d_directions", return_value=d_dirs),
            patch("mt5_signal_bot.evaluate_xau_entry_timing_m30", return_value={
                "entry_time": "07:49", "entry_state": "READY",
                "layer1": {"group": "BT"}, "layer2": {"group": "SW"}, "layer3": {"group": "SW"},
            }),
            patch("mt5_signal_bot.read_previous_h1_candle", return_value=(h1_candle, "TANG")),
        ):
            result = evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 7), 7, day_mode=mode)

        # H1 TANG → reverse → SELL for XAUUSD
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["primary_action"], "REVERSE_H1")
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["primary_source"], "PREVIOUS_COMPLETED_H1")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_h49_reverses_h1_giam_to_buy(self, mock_clock):
        """H:49 with H1 GIAM → BUY (reverse of SELL)."""
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        d_dirs = {
            "XAUUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "XAUUSD"},
            "GBPUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPUSD"},
            "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD"},
            "GBPJPY": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPJPY"},
            "GBPCAD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPCAD"},
        }
        h1_candle = {"open": 2345.0, "close": 2340.0, "high": 2346.0, "low": 2339.0}

        with (
            patch("mt5_signal_bot.calculate_all_d_directions", return_value=d_dirs),
            patch("mt5_signal_bot.evaluate_xau_entry_timing_m30", return_value={
                "entry_time": "07:49", "entry_state": "READY",
                "layer1": {"group": "BT"}, "layer2": {"group": "SW"}, "layer3": {"group": "SW"},
            }),
            patch("mt5_signal_bot.read_previous_h1_candle", return_value=(h1_candle, "GIAM")),
        ):
            result = evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 7), 7, day_mode=mode)

        # H1 GIAM → reverse → BUY
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_h49_h1_doji_waits(self, mock_clock):
        """H:49 with H1 DOJI → WAIT."""
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        d_dirs = {
            "XAUUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "XAUUSD"},
            "GBPUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPUSD"},
            "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD"},
            "GBPJPY": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPJPY"},
            "GBPCAD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPCAD"},
        }
        h1_candle = {"open": 2345.0, "close": 2345.0, "high": 2346.0, "low": 2344.0}

        with (
            patch("mt5_signal_bot.calculate_all_d_directions", return_value=d_dirs),
            patch("mt5_signal_bot.evaluate_xau_entry_timing_m30", return_value={
                "entry_time": "07:49", "entry_state": "READY",
                "layer1": {"group": "BT"}, "layer2": {"group": "SW"}, "layer3": {"group": "SW"},
            }),
            patch("mt5_signal_bot.read_previous_h1_candle", return_value=(h1_candle, "DOJI")),
        ):
            result = evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 7), 7, day_mode=mode)

        self.assertEqual(result["pair_dirs"]["XAUUSD"], "WAIT")


if __name__ == "__main__":
    unittest.main()
