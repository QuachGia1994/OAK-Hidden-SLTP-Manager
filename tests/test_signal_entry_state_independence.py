"""Signal direction is independent of entry state in D-Direction + Day Mode engine (v80)."""

import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import DayMode


def _d_dirs(xau="BUY", gbpusd="SELL", gbpaud="BUY"):
    return {
        "XAUUSD": {"d_direction": xau, "d_state": "READY", "symbol": "XAUUSD"},
        "GBPUSD": {"d_direction": gbpusd, "d_state": "READY", "symbol": "GBPUSD"},
        "GBPAUD": {"d_direction": gbpaud, "d_state": "READY", "symbol": "GBPAUD"},
        "GBPJPY": {"d_direction": "WAIT", "d_state": "DOJI", "symbol": "GBPJPY"},
        "GBPCAD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPCAD"},
    }


def _pending_timing():
    """Layer 2 SW before H:30 — entry is PENDING_LAYER3."""
    return {
        "entry_time": None,
        "entry_state": "PENDING_LAYER3",
        "entry_candidates": ["07:49", "08:25"],
        "entry_resolution_time": "07:30",
        "layer2": {"group": "SW"},
        "layer3": None,
    }


def _ready_timing(entry_time="07:49"):
    """Layer 3 resolved — entry is READY."""
    return {
        "entry_time": entry_time,
        "entry_state": "READY",
        "entry_candidates": [entry_time],
        "layer1": {"group": "BT"},
        "layer2": {"group": "SW"},
        "layer3": {"group": "SW"},
    }


class SignalEntryIndependenceTests(unittest.TestCase):
    """Signal direction must be READY regardless of entry state."""

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_xau_signal_ready_when_entry_pending(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_pending_timing()),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7, day_mode=mode
            )

        self.assertIsNotNone(result)
        # D=BUY for XAUUSD, H:49 → REVERSE_H1 action, but no H1 candle mock → WAIT
        # Actually entry is PENDING_LAYER3, entry_time=None → entry_branch=None → WAIT
        self.assertEqual(result["pair_entry_states"]["XAUUSD"], "PENDING_LAYER3")
        self.assertIsNone(result["pair_entry_times"]["XAUUSD"])

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_xau_entry_ready_when_layer3_resolves(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_ready_timing("07:49")),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7, day_mode=mode
            )

        # H:49 → REVERSE_H1 action
        self.assertEqual(result["pair_entry_states"]["XAUUSD"], "READY")
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "07:49")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_gbp_pairs_use_own_d_direction(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_ready_timing("07:11")),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7, day_mode=mode
            )

        # H:11 matches DAY_MODE_H11 → KEEP_D
        # GBPUSD D=SELL → KEEP_D → SELL
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(result["pair_signal_states"]["GBPUSD"], "READY")
        self.assertEqual(result["pair_entry_times"]["GBPUSD"], "08:00")


if __name__ == "__main__":
    unittest.main()
