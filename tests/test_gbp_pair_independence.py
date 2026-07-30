"""GBP pairs use their own D-Direction independently while entry follows H+1:00 schedule (v80)."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot
from mt5_signal_bot import DayMode


def _d_dirs():
    return {
        "XAUUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "XAUUSD"},
        "GBPUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPUSD"},
        "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD"},
        "GBPJPY": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPJPY"},
        "GBPCAD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPCAD"},
    }


def _timing(entry="07:11"):
    return {
        "symbol": "XAUUSD",
        "entry_time": entry,
        "entry_state": "READY" if entry else "WAIT",
        "layer1": {"group": "BT"},
        "layer2": {"group": "BT"},
        "layer3": None,
    }


class GbpPairIndependenceTests(unittest.TestCase):
    def test_signals_are_independent_but_gbp_entries_share_next_hour(self) -> None:
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing()),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 30, 7), 7, day_mode=mode)

        # H:11 matches DAY_MODE_H11 → KEEP_D for all pairs
        # XAUUSD D=BUY → BUY
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        # GBPAUD D=BUY → BUY (independent)
        self.assertEqual(result["pair_dirs"]["GBPAUD"], "BUY")
        # GBPUSD D=SELL → SELL (independent)
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        # Entry times
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "07:11")
        self.assertEqual(result["pair_entry_times"]["GBPUSD"], "08:00")
        self.assertEqual(result["pair_entry_times"]["GBPAUD"], "08:00")
        # Disabled pairs
        self.assertEqual(result["pair_signal_states"]["GBPJPY"], "DISABLED")
        self.assertEqual(result["pair_signal_states"]["GBPCAD"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
