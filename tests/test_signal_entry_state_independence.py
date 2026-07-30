"""XAUUSD signal direction is independent of entry state (v75)."""

import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot


def _gbp_native(symbol, direction="BUY", group="BT"):
    return {
        "symbol": symbol,
        "native_signal": direction,
        "direction": direction,
        "entry_time": None,
        "signal_state": "READY",
        "entry_state": "WAIT",
        "layer1": {"group": group, "base_signal": direction},
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
        with (
            patch.object(mt5_signal_bot, "evaluate_gbp_native_signal_m30",
                         side_effect=lambda s, h, sym, as_of_dt=None: _gbp_native(sym, "BUY")),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_pending_timing()),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(result["pair_signal_states"]["XAUUSD"], "READY")
        self.assertEqual(result["pair_entry_states"]["XAUUSD"], "PENDING_LAYER3")
        self.assertIsNone(result["pair_entry_times"]["XAUUSD"])

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_top_level_signal_is_buy_when_entry_pending(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        with (
            patch.object(mt5_signal_bot, "evaluate_gbp_native_signal_m30",
                         side_effect=lambda s, h, sym, as_of_dt=None: _gbp_native(sym, "SELL")),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_pending_timing()),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7
            )

        self.assertEqual(result["signal"], "SELL")
        self.assertEqual(result["signal_state"], "READY")
        self.assertEqual(result["entry_state"], "PENDING_LAYER3")
        self.assertIsNone(result["entry_time"])

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_xau_entry_ready_when_layer3_resolves(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        with (
            patch.object(mt5_signal_bot, "evaluate_gbp_native_signal_m30",
                         side_effect=lambda s, h, sym, as_of_dt=None: _gbp_native(sym, "BUY")),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_ready_timing("07:49")),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7
            )

        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(result["pair_entry_states"]["XAUUSD"], "READY")
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "07:49")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_gbp_pairs_unaffected_by_xau_entry_state(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        with (
            patch.object(mt5_signal_bot, "evaluate_gbp_native_signal_m30",
                         side_effect=lambda s, h, sym, as_of_dt=None: _gbp_native(sym, "SELL")),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30",
                         return_value=_pending_timing()),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(
                datetime(2026, 7, 30, 7), 7
            )

        self.assertEqual(result["pair_signal_states"]["GBPUSD"], "READY")
        self.assertEqual(result["pair_entry_states"]["GBPUSD"], "READY")
        self.assertEqual(result["pair_entry_times"]["GBPUSD"], "08:00")


if __name__ == "__main__":
    unittest.main()
